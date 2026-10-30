#!/usr/bin/env python3
"""Deterministic generator for original 2D UI/VFX assets (docs/04 sections 3-5, 9).

Generates from scratch (no downloaded content), with fixed seeds and supersampled
drawing. Decoded pixels are reproducible; committed PNG bytes are NOT guaranteed
to be identical across machines (different zlib/Pillow builds compress
differently), so every atlas JSON records the pillow/numpy versions used and a
sha256 of the DECODED RGBA pixels, which the checker verifies against the PNG:

  assets/ui/T_UI_IconSet_A.png    1024x1024 RGBA icon atlas (128 px cells)
  assets/ui/T_UI_IconSet_A.json   atlas map: name, x, y, w, h (+ meta)
  assets/ui/T_UI_IconSet_A.csv    same map in CSV form
  assets/vfx/T_VX_Splash_A.png     512x512 RGBA 4x4 sprite sheet (128 px frames)
  assets/vfx/T_VX_Splash_A.json    frame map + blend assumption (additive)
  assets/vfx/T_VX_Wake_A.png       256x256 RGBA foam strip, tileable on both axes
  assets/vfx/T_VX_Wake_A.json      tiling/blend notes

Docs/04 rules honoured here:
  - Naming: textures are `T_<Name>_<Type>.png`; type `A` because every atlas uses
    its alpha channel (sprites/icons composite over the scene). "No unused alpha"
    therefore does not bite: alpha is load-bearing in all three atlases.
  - Folders: assets/ui and assets/vfx (docs/04 section 5).
  - Sizes: power-of-two, <= 2048 (docs/04 section 4: VFX sprite atlas <= 512, so
    splash is 512 and wake is 256; UI_IconSet row in ASSET_LIST.csv says atlas 1024).

Blend assumptions (documented per docs/04 "no baked light unless documented"):
  - VX_Splash: intended for ADDITIVE blending. RGB is bright foam/white wherever
    alpha > 0 (no dark fringes), so adding RGB scaled by alpha only ever brightens.
  - VX_Wake: intended for ALPHA blending (soft foam over water); it is also
    additive-safe for the same brightness reason.

Pure helpers (numpy only, no Pillow) are importable by tests: icon_atlas_layout,
splash_droplets, splash_intensity_field, wake_intensity_field, periodic_noise,
downsample_mean. Pillow is imported lazily-guarded; rendering functions raise a
clear error when it is missing.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

try:  # Pillow is only needed to render/write images, not for the pure helpers.
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - exercised implicitly by CI without PIL
    Image = None
    ImageDraw = None

# --- Fixed configuration (tunables are data, not magic numbers) -----------------

SEED = 20261029  # fixed; never derive from time/random module

ICON_NAMES = (
    "coin",
    "fish",
    "heart_full",
    "heart_empty",
    "flag",
    "gamepad",
    "gear",
    "speaker_on",
    "speaker_off",
)
ICON_SIZE = 128
ICONS_PER_ROW = 8
UI_ATLAS_SIZE = 1024
ICON_SS = 4  # supersampling factor for vector-drawn icons

SPLASH_GRID = 4  # 4x4 frames
SPLASH_FRAME_SIZE = 128
SPLASH_ATLAS_SIZE = SPLASH_GRID * SPLASH_FRAME_SIZE  # 512
SPLASH_SS = 2  # field is analytic and smooth; 2x is enough
SPLASH_FRAMES = SPLASH_GRID * SPLASH_GRID  # 16
SPLASH_DURATION_S = 0.55
SPLASH_DROPLETS = 26
SPLASH_GRAVITY = 140.0  # px/s^2 in 128-unit frame space, +Y is down

WAKE_SIZE = 256

# docs/04 section 1 palette (initial art-direction palette, verbatim colours).
PALETTE = {
    "river_teal": (63, 184, 175),    # 3FB8AF
    "deep_water": (31, 111, 139),    # 1F6F8B
    "foam": (244, 251, 255),         # F4FBFF
    "wood": (176, 122, 74),          # B07A4A
    "gold": (255, 201, 60),          # FFC93C
    "coral": (255, 111, 89),         # FF6F59
    "ui_cream": (255, 244, 220),     # FFF4DC
    "ui_ink": (45, 42, 50),          # 2D2A32
}

SPLASH_TINT_LOW = (191, 231, 242)   # bright foam-blue; stays bright for additive
SPLASH_TINT_HIGH = (255, 255, 255)
WAKE_TINT_LOW = (222, 244, 250)
WAKE_TINT_HIGH = (255, 255, 255)


def darken(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    """Deterministically derive a darker outline colour from a palette entry."""
    return tuple(max(0, min(255, round(c * factor))) for c in rgb)


# --- Pure: UI icon atlas layout ------------------------------------------------


def icon_atlas_layout(
    names: tuple[str, ...] = ICON_NAMES,
    icon_size: int = ICON_SIZE,
    per_row: int = ICONS_PER_ROW,
    atlas_size: int = UI_ATLAS_SIZE,
) -> list[dict]:
    """Row-major cell positions for the icon atlas (pure)."""
    if atlas_size % icon_size or icon_size * per_row > atlas_size:
        raise ValueError("atlas_size must be a multiple of icon_size and wide enough")
    rows = math.ceil(len(names) / per_row)
    if rows * icon_size > atlas_size:
        raise ValueError("icons do not fit in the atlas")
    entries = []
    for i, name in enumerate(names):
        entries.append({
            "name": name,
            "x": (i % per_row) * icon_size,
            "y": (i // per_row) * icon_size,
            "w": icon_size,
            "h": icon_size,
        })
    return entries


def heart_polygon(n: int = 72) -> list[tuple[float, float]]:
    """Classic parametric heart in unit space (x in [-1,1], y up in ~[-1,1]). Pure."""
    pts = []
    for i in range(n):
        t = 2.0 * math.pi * i / n
        x = 16.0 * math.sin(t) ** 3
        y = 13.0 * math.cos(t) - 5.0 * math.cos(2 * t) - 2.0 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 16.0, y / 17.0))
    return pts


def gear_polygon(teeth: int = 8, r_inner: float = 0.62, r_outer: float = 0.90,
                 tooth_half_deg: float = 13.0, samples_tip: int = 7,
                 samples_valley: int = 5) -> list[tuple[float, float]]:
    """Cog outline in unit space (radius 1.0 = icon half-extent). Pure."""
    step = 360.0 / teeth
    valley_half = step / 2.0 - tooth_half_deg
    pts: list[tuple[float, float]] = []
    for i in range(teeth):
        a_c = i * step
        for j in range(samples_tip):
            a = math.radians(a_c - tooth_half_deg + 2 * tooth_half_deg * j / (samples_tip - 1))
            pts.append((r_outer * math.sin(a), -r_outer * math.cos(a)))
        for j in range(samples_valley):
            a = math.radians(a_c + tooth_half_deg + 2 * valley_half * j / (samples_valley - 1))
            pts.append((r_inner * math.sin(a), -r_inner * math.cos(a)))
    return pts


# --- Pure: splash simulation ----------------------------------------------------


def splash_droplets(seed: int = SEED, n: int = SPLASH_DROPLETS) -> dict[str, np.ndarray]:
    """Deterministic droplet parameters (angles, speeds, radii) for the burst."""
    rng = np.random.default_rng(seed)
    angles = rng.uniform(0.0, 2.0 * np.pi, n)
    u = rng.uniform(0.0, 1.0, n)
    speeds = 22.0 + 78.0 * u ** 0.8  # bias towards a few fast outliers
    radii = 3.2 + 3.8 * rng.uniform(0.0, 1.0, n)
    return {"angles": angles, "speeds": speeds, "radii": radii}


def _ease_out(u: float) -> float:
    return 1.0 - (1.0 - u) ** 2


def splash_intensity_field(frame: int, size: int, n_frames: int = SPLASH_FRAMES,
                           duration_s: float = SPLASH_DURATION_S,
                           gravity: float = SPLASH_GRAVITY,
                           droplets: dict[str, np.ndarray] | None = None,
                           ) -> np.ndarray:
    """Intensity [0,1] of one splash frame at `size`x`size` pixels. Pure numpy.

    Geometry lives in 128-unit frame space and is scaled by size/128, so callers
    can render supersampled fields and downsample afterwards.
    """
    if droplets is None:
        droplets = splash_droplets()
    s = size / SPLASH_FRAME_SIZE
    u = frame / (n_frames - 1)
    t = u * duration_s
    cx = cy = size / 2.0
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    r = np.hypot(xx - cx, yy - cy) / s  # 128-unit space

    # central flash: bright blob that widens and dies quickly
    core = (1.0 - u) ** 2.2 * np.exp(-(r / (16.0 * (1.0 - u) + 3.5)) ** 2)
    # expanding ring (the crown)
    ring_r = 6.0 + 52.0 * _ease_out(u)
    ring_w = 7.0 - 2.5 * u
    ring = 0.85 * (1.0 - u) ** 1.6 * np.exp(-((r - ring_r) / ring_w) ** 2)

    field = core + ring
    fade = (1.0 - u) ** 1.35
    ang, spd, rad = droplets["angles"], droplets["speeds"], droplets["radii"]
    for a, v, rd in zip(ang, spd, rad, strict=True):
        px = cx + (v * math.cos(a) * t) * s
        py = cy + (v * math.sin(a) * t + 0.5 * gravity * t * t) * s
        sigma = rd * (0.8 + 0.7 * u) * s
        d2 = (xx - px) ** 2 + (yy - py) ** 2
        field = field + fade * np.exp(-d2 / (2.0 * sigma * sigma))
    return np.clip(field, 0.0, 1.0)


def downsample_mean(field: np.ndarray, factor: int) -> np.ndarray:
    """Exact box-filter downsample by an integer factor. Pure numpy."""
    h, w = field.shape
    if h % factor or w % factor:
        raise ValueError("field dimensions must be divisible by the factor")
    return field.reshape(h // factor, factor, w // factor, factor).mean(axis=(1, 3))


def tint_by_intensity(intensity: np.ndarray, low: tuple[int, int, int],
                      high: tuple[int, int, int]) -> np.ndarray:
    """Map an [0,1] field to HxWx3 uint8 RGB, lerping low->high. Pure numpy."""
    i = np.clip(intensity, 0.0, 1.0)[..., None]
    lo = np.array(low, dtype=np.float64)
    hi = np.array(high, dtype=np.float64)
    return (lo + (hi - lo) * i).round().astype(np.uint8)


# --- Pure: wake strip ------------------------------------------------------------


def periodic_noise(size: int, seed: int, waves: int = 5) -> np.ndarray:
    """Smooth noise that is exactly periodic on both axes (integer wavenumbers)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:size, 0:size].astype(np.float64)
    val = np.zeros_like(x)
    for _ in range(waves):
        kx = int(rng.integers(-6, 7))
        ky = int(rng.integers(-6, 7))
        if kx == 0 and ky == 0:
            kx = 1
        amp = float(rng.uniform(0.4, 1.0))
        phase = float(rng.uniform(0.0, 2.0 * np.pi))
        val += amp * np.sin(2.0 * np.pi * (kx * x + ky * y) / size + phase)
    val -= val.min()
    rng_max = val.max()
    return val / rng_max if rng_max > 0 else val


def _wrap_dist(v: np.ndarray, size: int) -> np.ndarray:
    """Signed distance on a torus: map differences into [-size/2, size/2)."""
    return (v + size / 2.0) % size - size / 2.0


def wake_intensity_field(size: int = WAKE_SIZE, seed: int = SEED) -> np.ndarray:
    """Foam intensity [0,1] of the V-shaped wake strip. Pure numpy.

    The V arms run at exactly 45 degrees from the apex at (size/2, 0), so both
    arms are continuous across the vertical wrap; every modulation uses integer
    cycle counts over `size`, making the field tileable on BOTH axes.
    """
    y, x = np.mgrid[0:size, 0:size].astype(np.float64)
    cx = size / 2.0
    # arm centrelines: x = cx +/- y (mod size), i.e. 45-degree V
    d_r = _wrap_dist(x - (cx + y), size)
    d_l = _wrap_dist(x - (cx - y), size)

    # all y-dependent parameters use integer cycles over `size` -> periodic
    mod = 0.62 + 0.38 * (0.5 + 0.5 * np.sin(2 * np.pi * 6 * y / size + 0.9))
    sigma = 9.5 + 3.5 * np.sin(2 * np.pi * 2 * y / size + 2.1)
    band_r = np.exp(-(d_r / sigma) ** 2) * mod * 0.95
    band_l = np.exp(-(d_l / sigma) ** 2) * mod * 0.95

    # soft haze around the apex (torus distance, so it wraps too)
    dx = _wrap_dist(x - cx, size)
    dy = np.minimum(y, size - y)
    haze = 0.32 * np.exp(-(dx * dx + dy * dy) / (2.0 * 30.0 ** 2))

    noise = periodic_noise(size, seed + 1)
    bands = np.clip(band_r + band_l, 0.0, 1.0)
    foam = 1.05 * (band_r + band_l) + haze + 0.5 * noise * (0.25 + 0.75 * bands)
    return np.clip(foam, 0.0, 1.0)


# --- Rendering (Pillow required below this line) --------------------------------


def _require_pillow() -> None:
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required for rendering: pip install pillow")


def _outlined_polygon(d, pts, fill, outline, width):
    """Chunky soft-rounded outline: stroke the path, then fill over its inner half."""
    d.line(pts + [pts[0]], fill=outline, width=width, joint="curve")
    d.polygon(pts, fill=fill)


def _dot(d, xy, r, fill):
    x, y = xy
    d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def _heart_pts(scale: float, cx: float, cy: float) -> list[tuple[float, float]]:
    return [(cx + px * scale, cy - py * scale) for px, py in heart_polygon()]


def _draw_coin(d, s: int) -> None:  # s = supersampled canvas size (512)
    gold = PALETTE["gold"]
    m = s * 0.125
    d.ellipse((m, m, s - m, s - m), fill=gold, outline=darken(gold, 0.72), width=s // 26)
    ring_m = s * 0.235
    d.ellipse((ring_m, ring_m, s - ring_m, s - ring_m),
              outline=(255, 224, 138), width=s // 36)
    c = s / 2
    r = s * 0.115
    d.polygon([(c, c - s * 0.205), (c + r, c), (c, c + s * 0.205), (c - r, c)],
              fill=PALETTE["ui_cream"])


def _draw_fish(d, s: int) -> None:
    gold = PALETTE["gold"]
    dark = darken(gold, 0.72)
    w = s // 26
    # tail (drawn first, body overlaps its root)
    _outlined_polygon(d, [(s * 0.17, s * 0.5), (s * 0.40, s * 0.32), (s * 0.40, s * 0.68)],
                      dark, dark, w)
    # dorsal fin
    _outlined_polygon(d, [(s * 0.46, s * 0.34), (s * 0.58, s * 0.20), (s * 0.66, s * 0.34)],
                      dark, dark, w)
    # body
    _outlined_polygon(d, [(s * 0.36, s * 0.5), (s * 0.85, s * 0.33), (s * 0.92, s * 0.5),
                          (s * 0.85, s * 0.67)], gold, dark, w)
    # gill + mouth
    d.arc((s * 0.58, s * 0.34, s * 0.78, s * 0.66), start=250, end=290, fill=dark,
          width=s // 40)
    d.arc((s * 0.80, s * 0.40, s * 0.92, s * 0.60), start=280, end=330, fill=dark,
          width=s // 44)
    # eye
    _dot(d, (s * 0.755, s * 0.435), s * 0.048, PALETTE["ui_ink"])
    _dot(d, (s * 0.77, s * 0.42), s * 0.016, PALETTE["foam"])


def _draw_heart(d, s: int, full: bool) -> None:
    coral = PALETTE["coral"]
    dark = darken(coral, 0.72)
    pts = _heart_pts(s * 0.29, s * 0.5, s * 0.535)
    if full:
        _outlined_polygon(d, pts, coral, dark, s // 13)
        d.ellipse((s * 0.33, s * 0.27, s * 0.44, s * 0.345), fill=(255, 214, 205))
    else:
        d.line(pts + [pts[0]], fill=dark, width=s // 13, joint="curve")


def _draw_flag(d, s: int) -> None:
    teal = PALETTE["river_teal"]
    dark = darken(teal, 0.72)
    # pole with a gold finial
    pr = s * 0.03
    d.rounded_rectangle((s * 0.225 - pr, s * 0.115, s * 0.225 + pr, s * 0.90),
                        radius=pr, fill=PALETTE["wood"], outline=darken(PALETTE["wood"], 0.7),
                        width=s // 51)
    _dot(d, (s * 0.225, s * 0.115), s * 0.045, PALETTE["gold"])
    # pennant with a gentle sag
    pts = [(s * 0.25, s * 0.17), (s * 0.82, s * 0.335), (s * 0.79, s * 0.40),
           (s * 0.25, s * 0.535)]
    _outlined_polygon(d, pts, teal, dark, s // 26)


def _draw_gamepad(d, s: int) -> None:
    deep = PALETTE["deep_water"]
    ink = PALETTE["ui_ink"]
    cream = PALETTE["ui_cream"]
    d.rounded_rectangle((s * 0.13, s * 0.335, s * 0.87, s * 0.69), radius=s * 0.175,
                        fill=deep, outline=ink, width=s // 32)
    # d-pad cross
    d.rounded_rectangle((s * 0.315, s * 0.455, s * 0.485, s * 0.505), radius=s * 0.02,
                        fill=cream)
    d.rounded_rectangle((s * 0.355, s * 0.415, s * 0.445, s * 0.545), radius=s * 0.02,
                        fill=cream)
    # action buttons
    _dot(d, (s * 0.695, s * 0.44), s * 0.048, PALETTE["coral"])
    _dot(d, (s * 0.775, s * 0.585), s * 0.048, PALETTE["gold"])
    # start dots
    _dot(d, (s * 0.55, s * 0.475), s * 0.012, cream)
    _dot(d, (s * 0.585, s * 0.55), s * 0.012, cream)


def _draw_gear(d, s: int) -> None:
    cream = PALETTE["ui_cream"]
    ink = PALETTE["ui_ink"]
    scale = s * 0.5
    pts = [(s * 0.5 + px * scale, s * 0.5 + py * scale) for px, py in gear_polygon()]
    _outlined_polygon(d, pts, cream, ink, s // 26)
    _dot(d, (s * 0.5, s * 0.5), s * 0.145, ink)
    # punch a transparent centre hole
    d.ellipse((s * 0.5 - s * 0.11, s * 0.5 - s * 0.11, s * 0.5 + s * 0.11, s * 0.5 + s * 0.11),
              fill=(0, 0, 0, 0))


def _draw_speaker(d, s: int, on: bool) -> None:
    cream = PALETTE["ui_cream"]
    ink = PALETTE["ui_ink"]
    teal = PALETTE["river_teal"]
    w = s // 30
    # cone first so the box overlaps the joint
    cone = [(s * 0.37, s * 0.445), (s * 0.50, s * 0.35), (s * 0.50, s * 0.65),
            (s * 0.37, s * 0.555)]
    d.line(cone + [cone[0]], fill=ink, width=w, joint="curve")
    d.polygon(cone, fill=cream)
    d.rounded_rectangle((s * 0.21, s * 0.42, s * 0.375, s * 0.58), radius=s * 0.03,
                        fill=cream, outline=ink, width=w)
    if on:
        d.arc((s * 0.48, s * 0.40, s * 0.62, s * 0.60), start=-55, end=55, fill=teal,
              width=s // 34)
        d.arc((s * 0.52, s * 0.33, s * 0.74, s * 0.67), start=-55, end=55, fill=teal,
              width=s // 34)
    else:
        x0, y0, x1, y1 = s * 0.56, s * 0.40, s * 0.78, s * 0.60
        lw = s // 22
        col = PALETTE["coral"]
        d.line((x0, y0, x1, y1), fill=col, width=lw)
        d.line((x1, y0, x0, y1), fill=col, width=lw)
        for px, py in ((x0, y0), (x1, y1), (x1, y0), (x0, y1)):
            _dot(d, (px, py), lw / 2, col)


_ICON_DRAWERS = {
    "coin": _draw_coin,
    "fish": _draw_fish,
    "heart_full": lambda d, s: _draw_heart(d, s, full=True),
    "heart_empty": lambda d, s: _draw_heart(d, s, full=False),
    "flag": _draw_flag,
    "gamepad": _draw_gamepad,
    "gear": _draw_gear,
    "speaker_on": lambda d, s: _draw_speaker(d, s, on=True),
    "speaker_off": lambda d, s: _draw_speaker(d, s, on=False),
}


def render_icon(name: str, icon_size: int = ICON_SIZE, ss: int = ICON_SS) -> "Image.Image":
    """Draw one icon supersampled, then downsample to icon_size."""
    _require_pillow()
    big = icon_size * ss
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _ICON_DRAWERS[name](d, big)
    return img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)


def render_icon_atlas() -> tuple["Image.Image", list[dict]]:
    entries = icon_atlas_layout()
    atlas = Image.new("RGBA", (UI_ATLAS_SIZE, UI_ATLAS_SIZE), (0, 0, 0, 0))
    for e in entries:
        icon = render_icon(e["name"])
        atlas.paste(icon, (e["x"], e["y"]))
    return atlas, entries


def render_splash_sheet() -> "Image.Image":
    """4x4 sheet of splash frames; analytic field at 2x, box-downsampled."""
    _require_pillow()
    droplets = splash_droplets()
    sheet = Image.new("RGBA", (SPLASH_ATLAS_SIZE, SPLASH_ATLAS_SIZE), (0, 0, 0, 0))
    for f in range(SPLASH_FRAMES):
        field = splash_intensity_field(
            f, SPLASH_FRAME_SIZE * SPLASH_SS, droplets=droplets)
        small = downsample_mean(field, SPLASH_SS)
        rgb = tint_by_intensity(small, SPLASH_TINT_LOW, SPLASH_TINT_HIGH)
        alpha = (small * 255 * 0.95).round().astype(np.uint8)
        frame = Image.fromarray(np.dstack([rgb, alpha]), "RGBA")
        sheet.paste(frame, ((f % SPLASH_GRID) * SPLASH_FRAME_SIZE,
                            (f // SPLASH_GRID) * SPLASH_FRAME_SIZE))
    return sheet


def render_wake_strip() -> "Image.Image":
    _require_pillow()
    field = wake_intensity_field(WAKE_SIZE)
    rgb = tint_by_intensity(field, WAKE_TINT_LOW, WAKE_TINT_HIGH)
    alpha = (field * 255 * 0.92).round().astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


# --- Metadata writers ------------------------------------------------------------


def pixel_sha256(img: "Image.Image") -> str:
    """sha256 over the DECODED RGBA pixels (stable across zlib/Pillow builds)."""
    return hashlib.sha256(img.convert("RGBA").tobytes()).hexdigest()


def _atlas_meta(png_path: Path) -> dict:
    """Render provenance for one atlas: tool versions + decoded-pixel hash.

    Re-opens the PNG from disk so the hash always describes the bytes actually
    written, not the in-memory render.
    """
    _require_pillow()
    with Image.open(png_path) as img:
        return {
            "pillow_version": Image.__version__,
            "numpy_version": np.__version__,
            "pixel_hash": pixel_sha256(img),
        }


UI_JSON_META = {
    "generated_by": "tools/gen_ui_vfx_assets.py",
    "seed": SEED,
    "naming": "docs/04 s3: T_<Name>_<Type>.png; type A = alpha is load-bearing",
    "blend": "straight alpha",
}


def write_atlas_maps(entries: list[dict], ui_dir: Path, vfx_dir: Path) -> None:
    ui_json = {
        "atlas": "T_UI_IconSet_A.png",
        "size": [UI_ATLAS_SIZE, UI_ATLAS_SIZE],
        "icon_size": ICON_SIZE,
        **UI_JSON_META,
        **_atlas_meta(ui_dir / "T_UI_IconSet_A.png"),
        "icons": entries,
    }
    (ui_dir / "T_UI_IconSet_A.json").write_text(json.dumps(ui_json, indent=2) + "\n",
                                                encoding="utf-8")
    with (ui_dir / "T_UI_IconSet_A.csv").open("w", newline="", encoding="utf-8") as fh:
        wtr = csv.writer(fh)
        wtr.writerow(["name", "x", "y", "w", "h"])
        wtr.writerows([e["name"], e["x"], e["y"], e["w"], e["h"]] for e in entries)

    splash_json = {
        "atlas": "T_VX_Splash_A.png",
        "size": [SPLASH_ATLAS_SIZE, SPLASH_ATLAS_SIZE],
        "frame_size": [SPLASH_FRAME_SIZE, SPLASH_FRAME_SIZE],
        "grid": [SPLASH_GRID, SPLASH_GRID],
        "frames": SPLASH_FRAMES,
        "suggested_fps": 30,
        "generated_by": "tools/gen_ui_vfx_assets.py",
        "seed": SEED,
        "blend": ("ADDITIVE assumed: RGB adds light scaled by alpha; every pixel "
                  "with alpha > 0 is bright foam/white by construction, so it can "
                  "only brighten the scene. Also usable with straight alpha."),
        **_atlas_meta(vfx_dir / "T_VX_Splash_A.png"),
        "frame_map": [
            {"frame": f, "x": (f % SPLASH_GRID) * SPLASH_FRAME_SIZE,
             "y": (f // SPLASH_GRID) * SPLASH_FRAME_SIZE,
             "w": SPLASH_FRAME_SIZE, "h": SPLASH_FRAME_SIZE}
            for f in range(SPLASH_FRAMES)
        ],
    }
    (vfx_dir / "T_VX_Splash_A.json").write_text(json.dumps(splash_json, indent=2) + "\n",
                                                encoding="utf-8")

    wake_json = {
        "atlas": "T_VX_Wake_A.png",
        "size": [WAKE_SIZE, WAKE_SIZE],
        "tileable": "both axes (V arms at 45 deg from apex; integer-cycle modulation)",
        "generated_by": "tools/gen_ui_vfx_assets.py",
        "seed": SEED,
        "blend": ("ALPHA blend assumed (foam over water); additive-safe too because "
                  "RGB is bright wherever alpha > 0."),
        **_atlas_meta(vfx_dir / "T_VX_Wake_A.png"),
    }
    (vfx_dir / "T_VX_Wake_A.json").write_text(json.dumps(wake_json, indent=2) + "\n",
                                              encoding="utf-8")


# --- Contact sheet (scratch output, never committed) ------------------------------


def build_contact_sheet(out_path: Path) -> None:
    """Compose everything onto one opaque sheet for a human/agent visual check."""
    _require_pillow()
    cream = PALETTE["ui_cream"] + (255,)
    deep = PALETTE["deep_water"] + (255,)
    water = (44, 141, 158, 255)
    pad = 24
    icon_atlas, entries = render_icon_atlas()
    icons_small = [(e["name"], icon_atlas.crop((e["x"], e["y"], e["x"] + e["w"],
                                                e["y"] + e["h"])).resize((64, 64)))
                   for e in entries]

    w = 4 * pad + 8 * 64 + 8
    sheet = Image.new("RGBA", (w, 1450), cream)
    d = ImageDraw.Draw(sheet)

    def icon_rows(y0: int, bg_note: str) -> None:
        for i, (name, ic) in enumerate(icons_small):
            x = pad + (i % 8) * (64 + 1)
            y = y0 + (i // 8) * 76
            sheet.paste(ic, (x, y), ic)
            d.text((x, y + 64), name[:10], fill=PALETTE["ui_ink"])
        d.text((pad, y0 + 160), bg_note, fill=PALETTE["ui_ink"])

    icon_rows(pad + 12, "UI_IconSet on cream (9 icons, 128 px cells shown at 64)")
    # same icons on deep background
    rect_y = pad + 200
    d.rectangle((0, rect_y, w, rect_y + 186), fill=deep)
    for i, (_name, ic) in enumerate(icons_small):
        x = pad + (i % 8) * (64 + 1)
        y = rect_y + 10 + (i // 8) * 76
        sheet.paste(ic, (x, y), ic)
    d.text((pad, rect_y + 168), "same icons on deep water bg", fill=PALETTE["foam"])

    # splash sheet on deep bg
    y2 = rect_y + 210
    d.rectangle((0, y2, w, y2 + 560), fill=deep)
    splash = render_splash_sheet()
    sheet.paste(splash, (pad, y2 + 20), splash)
    d.text((pad + 540, y2 + 30), "VX_Splash 4x4 (512, 128 px frames)", fill=PALETTE["foam"])

    # wake tiled 2x2 on water bg to eyeball seams
    y3 = y2 + 580
    d.rectangle((0, y3, w, y3 + 560), fill=water)
    wake = render_wake_strip()
    for ty in range(2):
        for tx in range(2):
            big = wake.resize((256, 256))
            sheet.paste(big, (pad + tx * 256, y3 + 20 + ty * 256), big)
    d.text((pad + 540, y3 + 30), "VX_Wake tiled 2x2 (seams should vanish)",
           fill=PALETTE["foam"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(out_path, "PNG")


# --- CLI ---------------------------------------------------------------------------


def generate_all(root: Path) -> list[Path]:
    _require_pillow()
    ui_dir = root / "assets" / "ui"
    vfx_dir = root / "assets" / "vfx"
    ui_dir.mkdir(parents=True, exist_ok=True)
    vfx_dir.mkdir(parents=True, exist_ok=True)

    atlas, entries = render_icon_atlas()
    atlas_path = ui_dir / "T_UI_IconSet_A.png"
    atlas.save(atlas_path, "PNG")

    splash_path = vfx_dir / "T_VX_Splash_A.png"
    render_splash_sheet().save(splash_path, "PNG")

    wake_path = vfx_dir / "T_VX_Wake_A.png"
    render_wake_strip().save(wake_path, "PNG")

    write_atlas_maps(entries, ui_dir, vfx_dir)
    written = [atlas_path, ui_dir / "T_UI_IconSet_A.json", ui_dir / "T_UI_IconSet_A.csv",
               splash_path, vfx_dir / "T_VX_Splash_A.json",
               wake_path, vfx_dir / "T_VX_Wake_A.json"]
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", type=Path, help="repo root (default cwd)")
    ap.add_argument("--contact-sheet", type=Path, default=None,
                    help="also write a contact sheet PNG here (scratch, do not commit)")
    a = ap.parse_args(argv)
    written = generate_all(a.root)
    for p in written:
        print(f"wrote {p}")
    if a.contact_sheet:
        build_contact_sheet(a.contact_sheet)
        print(f"wrote contact sheet {a.contact_sheet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
