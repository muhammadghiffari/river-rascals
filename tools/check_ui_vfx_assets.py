#!/usr/bin/env python3
"""Pure-Python checker for the generated UI/VFX atlases (docs/04 sections 3-5).

Validation logic (sizes, power-of-two, alpha presence, atlas-map bounds, wake
seam jump on the alpha channel, transparent-pixel RGB energy, JSON pixel-hash
vs decoded PNG) is written against plain Python data structures so it is
unit-testable without Pillow.
Pillow is imported lazily and is only used to decode pixels from disk.

Usage: python tools/check_ui_vfx_assets.py [--root .]
Exit code 1 if any check fails.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path, PurePosixPath

try:  # only needed to decode pixels; the checks below stay importable without it
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

MAX_DIM = 2048  # docs/04 s4: power-of-two, <= 2048
VFX_MAX_DIM = 512  # docs/04 s4: "VFX sprite ... atlas <= 512"
VISIBLE_ALPHA = 32  # a pixel is "visible" from here on
SEAM_RATIO_LIMIT = 1.5  # seam jump may exceed the worst interior step by <= 50%
TEXTURE_NAME_RE = re.compile(r"^T_[A-Za-z0-9_]+_(BC|E|A)\.png$")


# --- Pure checks -----------------------------------------------------------------


def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def check_dimensions(w: int, h: int, max_dim: int = MAX_DIM) -> list[str]:
    """Return a list of violations for docs/04 s4 texture size rules."""
    errors = []
    if not is_power_of_two(w):
        errors.append(f"width {w} is not power-of-two")
    if not is_power_of_two(h):
        errors.append(f"height {h} is not power-of-two")
    if w > max_dim or h > max_dim:
        errors.append(f"{w}x{h} exceeds max {max_dim}")
    return errors


def alpha_usage_stats(alphas) -> dict[str, int]:
    """Count transparent (<VISIBLE_ALPHA), visible and opaque pixels. Pure."""
    stats = {"transparent": 0, "visible": 0, "opaque": 0}
    for a in alphas:
        if a < VISIBLE_ALPHA:
            stats["transparent"] += 1
        else:
            stats["visible"] += 1
            if a >= 248:
                stats["opaque"] += 1
    return stats


def has_used_alpha(alphas) -> list[str]:
    """'no unused alpha' (docs/04 s4): alpha channel must actually do work."""
    stats = alpha_usage_stats(alphas)
    errors = []
    if stats["transparent"] == 0:
        errors.append("alpha channel is fully opaque (unused alpha)")
    if stats["visible"] == 0:
        errors.append("image is fully transparent")
    return errors


def atlas_map_errors(entries: list[dict], w: int, h: int) -> list[str]:
    """Atlas map entries must be named and inside the atlas, without overlap."""
    errors = []
    seen_cells: dict[str, tuple[int, int, int, int]] = {}
    names: set[str] = set()
    for e in entries:
        name = e.get("name", "")
        if not name or not name.replace("_", "").isalnum():
            errors.append(f"bad icon name {name!r}")
        if name in names:
            errors.append(f"duplicate icon name {name!r}")
        names.add(name)
        x, y, ew, eh = e.get("x", -1), e.get("y", -1), e.get("w", 0), e.get("h", 0)
        if x < 0 or y < 0 or x + ew > w or y + eh > h:
            errors.append(f"{name}: cell {x},{y},{ew}x{eh} out of atlas bounds {w}x{h}")
            continue
        for other, cell in seen_cells.items():
            if x < cell[0] + cell[2] and cell[0] < x + ew and y < cell[1] + cell[3] \
                    and cell[1] < y + eh:
                errors.append(f"{name}: overlaps {other} at {cell}")
        seen_cells[name] = (x, y, ew, eh)
    return errors


def texture_naming_errors(rel_path: str, atlas_ref: str | None = None) -> list[str]:
    """docs/04 s3/s5: T_<Name>_<Type>.png under its class folder (ui or vfx). Pure.

    `atlas_ref` is the file name recorded in the atlas JSON's "atlas" field, if
    any; it must match the PNG actually on disk.
    """
    errors = []
    p = PurePosixPath(rel_path.replace("\\", "/"))
    folder = p.parent.as_posix()
    if folder not in ("assets/ui", "assets/vfx"):
        errors.append(f"{p.name} must live in assets/ui or assets/vfx (found {folder or '.'})")
    if not TEXTURE_NAME_RE.match(p.name):
        errors.append(f"{p.name} does not match T_<Name>_<Type>.png "
                      "(docs/04 s3: types BC, E, A)")
    if atlas_ref is not None and atlas_ref != p.name:
        errors.append(f"atlas JSON references {atlas_ref!r} but the PNG on disk is {p.name!r}")
    return errors


def seam_metrics(rows: list[list[int]]) -> dict[str, float]:
    """Wrap-around seam vs interior steps along axis 0. Pure.

    `rows` is a sequence of scanlines (each a sequence of numbers). Returns the
    maximum absolute seam jump (last row vs first row), the maximum absolute
    interior step between adjacent rows, and their ratio (inf if interior is 0).
    """
    if len(rows) < 2:
        raise ValueError("need at least 2 rows")
    seam = max(abs(a - b) for a, b in zip(rows[-1], rows[0], strict=True))
    interior = 0
    for i in range(len(rows) - 1):
        step = max(abs(a - b) for a, b in zip(rows[i], rows[i + 1], strict=True))
        interior = max(interior, step)
    ratio = math.inf if interior == 0 else seam / interior
    return {"seam": seam, "interior": interior, "ratio": ratio}


def tileable_errors(metrics: dict[str, float], limit: float = SEAM_RATIO_LIMIT) -> list[str]:
    errors = []
    if metrics["ratio"] > limit:
        errors.append(
            f"seam jump {metrics['seam']:.1f} vs worst interior step "
            f"{metrics['interior']:.1f} (ratio {metrics['ratio']:.2f} > {limit})")
    return errors


def min_visible_luminance(pixels) -> tuple[int, int]:
    """(min luminance, count) over pixels whose alpha >= VISIBLE_ALPHA. Pure.

    `pixels` yields (r, g, b, a) tuples. Informational only: bright visible
    pixels are nice to have for additive sprites, but the gate that catches
    real additive hazards is transparent_rgb_energy below.
    """
    min_lum = 255
    count = 0
    for r, g, b, a in pixels:
        if a >= VISIBLE_ALPHA:
            count += 1
            lum = max(r, g, b)
            min_lum = min(min_lum, lum)
    return min_lum, count


def transparent_rgb_energy(pixels) -> int:
    """Sum of RGB channel values over fully transparent (alpha == 0) pixels. Pure.

    Alpha-multiplied additive (SRC_ALPHA, ONE) contributes nothing there, but
    under raw ADD (ONE, ONE) any RGB energy hidden behind alpha == 0 hazes the
    whole quad - the real additive hazard a minimum-luminance rule on visible
    pixels can never catch.
    """
    return sum(r + g + b for r, g, b, a in pixels if a == 0)


def transparent_bleed_errors(energy: int, documented: bool) -> list[str]:
    """RGB energy behind alpha == 0 must be zero, or documented in the JSON."""
    if energy == 0:
        return []
    if documented:
        return []
    return [f"transparent pixels (alpha == 0) carry RGB energy {energy}: under raw "
            "ADD blending they would haze the quad. Zero RGB where alpha == 0 or "
            "document the bleed with a transparent_rgb_bleed note in the atlas JSON"]


def pixel_sha256(img) -> str:
    """sha256 over the DECODED RGBA pixels (stable across zlib/Pillow builds)."""
    return hashlib.sha256(img.convert("RGBA").tobytes()).hexdigest()


def pixel_hash_errors(img, meta: dict, label: str) -> list[str]:
    """The atlas JSON's recorded meta must describe exactly this PNG's pixels.

    PNG bytes legitimately differ between zlib/Pillow builds; decoded pixels
    may not. `meta` must carry pixel_hash plus the pillow/numpy versions that
    rendered it (informational, but their presence is what makes the hash
    auditable on another machine).
    """
    errors = []
    for key in ("pillow_version", "numpy_version"):
        if not meta.get(key):
            errors.append(f"atlas JSON is missing {key} (regenerate with the generator)")
    recorded = meta.get("pixel_hash")
    if not recorded or not isinstance(recorded, str):
        errors.append("atlas JSON is missing pixel_hash (regenerate with the generator)")
        return errors
    actual = pixel_sha256(img)
    if actual != recorded:
        errors.append(
            f"pixel_hash mismatch on {label}: JSON records {recorded[:16]}... "
            f"but the PNG decodes to {actual[:16]}... (stale JSON or different image)")
    return errors


# --- Pillow-dependent loading ------------------------------------------------------


def _load_or_fail(root: Path, rel: str, bad: list[str]):
    """Decode a PNG, turning unreadable/unopenable files into FAIL lines.

    Returns None instead of raising so one bad file cannot traceback the whole
    run: an unfetched Git LFS pointer (the file starts with the LFS pointer
    text) and anything PIL cannot decode both become plain FAIL lines. The LFS
    check needs no Pillow, so it also works on Pillow-less machines (CI).
    """
    p = root / rel
    try:
        head = p.open("rb").read(100)
    except OSError as exc:
        bad.append(f"FAIL {rel}: cannot read file ({exc})")
        return None
    if head.startswith(b"version https://git-lfs"):
        bad.append(f"FAIL {rel}: unfetched Git LFS pointer (run: git lfs pull)")
        return None
    if Image is None:
        bad.append(f"FAIL {rel}: Pillow is required to decode images (pip install pillow)")
        return None
    try:
        with Image.open(p) as img:
            return img.convert("RGBA")
    except Exception as exc:  # noqa: BLE001 - any decode failure is a FAIL line, not a crash
        bad.append(f"FAIL {rel}: PIL cannot decode ({type(exc).__name__}: {exc})")
        return None


def _alpha_rows(img) -> list[bytes]:
    """Alpha scanlines for the wake seam gate. Pure.

    The gate must NOT read luma: RGB is zeroed behind alpha == 0 (the additive
    gate), so luma jumps at every alpha edge and the worst interior step is the
    silhouette itself, which deadens the seam/interior ratio (0.00 on a wake
    whose wrap is torn). Alpha is the foam silhouette the tiling actually
    repeats, so the seam/interior ratio is computed on it.
    """
    a = img.getchannel("A")
    w, h = a.size
    data = a.tobytes()
    return [data[y * w:(y + 1) * w] for y in range(h)]


def _rgba_tuples(raw: bytes):
    """Yield (r, g, b, a) tuples from raw RGBA bytes (version-proof, no getdata)."""
    return (tuple(raw[i:i + 4]) for i in range(0, len(raw), 4))


def _cell_rgba(img, x: int, y: int, w: int, h: int):
    return _rgba_tuples(img.crop((x, y, x + w, y + h)).tobytes())


# --- Orchestration -----------------------------------------------------------------

EXPECTED = {
    "ui_atlas": "assets/ui/T_UI_IconSet_A.png",
    "ui_json": "assets/ui/T_UI_IconSet_A.json",
    "ui_csv": "assets/ui/T_UI_IconSet_A.csv",
    "splash": "assets/vfx/T_VX_Splash_A.png",
    "splash_json": "assets/vfx/T_VX_Splash_A.json",
    "wake": "assets/vfx/T_VX_Wake_A.png",
    "wake_json": "assets/vfx/T_VX_Wake_A.json",
}


def run_checks(root: Path) -> tuple[list[str], list[str]]:
    """Returns (passed, failed) message lines."""
    ok: list[str] = []
    bad: list[str] = []

    def report(name: str, errors: list[str], detail: str = "") -> None:
        line = f"{name}: {detail}" if detail else name
        (ok if not errors else bad).append(("PASS " if not errors else "FAIL ") + line)
        bad.extend(f"       {e}" for e in errors)

    for _key, rel in EXPECTED.items():
        p = root / rel
        if not p.is_file():
            bad.append(f"FAIL missing {rel}")
    if bad:
        return ok, bad

    # --- UI icon atlas ---------------------------------------------------------
    ui_img = _load_or_fail(root, EXPECTED["ui_atlas"], bad)
    if ui_img is not None:
        ui_w, ui_h = ui_img.size
        report("ui atlas naming + folder",
               texture_naming_errors(EXPECTED["ui_atlas"]), f"{EXPECTED['ui_atlas']}")
        report("ui atlas dimensions", check_dimensions(ui_w, ui_h), f"{ui_w}x{ui_h}")
        report("ui atlas alpha used", has_used_alpha(ui_img.getchannel("A").tobytes()))

        ui_map = json.loads((root / EXPECTED["ui_json"]).read_text(encoding="utf-8"))
        report("ui atlas json naming", texture_naming_errors(EXPECTED["ui_atlas"],
                                                             ui_map.get("atlas")),
               f"json atlas ref {ui_map.get('atlas')!r}")
        report("ui atlas pixel hash", pixel_hash_errors(ui_img, ui_map, "T_UI_IconSet_A"),
               f"pillow {ui_map.get('pillow_version')} / numpy {ui_map.get('numpy_version')}")
        entries = ui_map["icons"]
        report("ui atlas map in bounds", atlas_map_errors(entries, ui_w, ui_h),
               f"{len(entries)} icons")
        with (root / EXPECTED["ui_csv"]).open(encoding="utf-8") as fh:
            csv_rows = list(csv.DictReader(fh))
        csv_match = [{k: int(v) if k != "name" else v for k, v in r.items()} for r in csv_rows]
        report("ui csv matches json",
               [] if csv_match == entries else ["CSV rows differ from JSON icons"])

        for e in entries:
            cell = _cell_rgba(ui_img, e["x"], e["y"], e["w"], e["h"])
            stats = alpha_usage_stats(px[3] for px in cell)
            errs = []
            if stats["visible"] == 0:
                errs.append(f"icon {e['name']} cell has no visible pixels")
            if stats["transparent"] == 0:
                errs.append(f"icon {e['name']} cell has no transparent pixels (not an icon cut-out)")
            report(f"icon {e['name']}", errs,
                   f"{stats['visible']} visible px")

    # --- splash sheet ------------------------------------------------------------
    sp_img = _load_or_fail(root, EXPECTED["splash"], bad)
    if sp_img is not None:
        sp_w, sp_h = sp_img.size
        report("splash naming + folder", texture_naming_errors(EXPECTED["splash"]),
               f"{EXPECTED['splash']}")
        # docs/04 s4: VFX sprite atlas <= 512 (tighter than the global 2048)
        report("splash dimensions", check_dimensions(sp_w, sp_h, max_dim=VFX_MAX_DIM),
               f"{sp_w}x{sp_h} (VFX atlas limit {VFX_MAX_DIM})")
        report("splash alpha used", has_used_alpha(sp_img.getchannel("A").tobytes()))
        sp_map = json.loads((root / EXPECTED["splash_json"]).read_text(encoding="utf-8"))
        report("splash json naming", texture_naming_errors(EXPECTED["splash"],
                                                           sp_map.get("atlas")),
               f"json atlas ref {sp_map.get('atlas')!r}")
        report("splash pixel hash", pixel_hash_errors(sp_img, sp_map, "T_VX_Splash_A"),
               f"pillow {sp_map.get('pillow_version')} / numpy {sp_map.get('numpy_version')}")
        fs = sp_map["frame_size"][0]
        frame_errors = []
        if sp_map["grid"] != [4, 4] or fs != 128 or sp_w != 512:
            frame_errors.append(f"unexpected layout {sp_map['grid']} frame {fs} atlas {sp_w}")
        # the blank padding frame must be explicit in the JSON, not a surprise
        if sp_map.get("frames_used") != 15 or sp_map.get("last_frame_empty") is not True:
            frame_errors.append(
                "splash JSON must declare frames_used 15 and last_frame_empty true "
                "(the 4x4 sheet's last slot is blank padding)")
        # frame 0 must burst (bright visible pixels), frame 15 must have faded out
        f0 = _cell_rgba(sp_img, 0, 0, fs, fs)
        if alpha_usage_stats(px[3] for px in f0)["visible"] < 64:
            frame_errors.append("frame 0 has almost no visible pixels")
        f15 = _cell_rgba(sp_img, 3 * fs, 3 * fs, fs, fs)
        if alpha_usage_stats(px[3] for px in f15)["visible"] > 0:
            frame_errors.append("frame 15 has not fully faded")
        report("splash frame layout + fade", frame_errors)
        sp_energy = transparent_rgb_energy(_rgba_tuples(sp_img.tobytes()))
        report("splash transparent-pixel RGB energy",
               transparent_bleed_errors(sp_energy,
                                        bool(sp_map.get("transparent_rgb_bleed"))),
               f"{sp_energy} behind alpha == 0")
        lum, cnt = min_visible_luminance(_rgba_tuples(sp_img.tobytes()))
        report("splash min visible brightness (informational)", [],
               f"min visible max-channel {lum} over {cnt} px")

    # --- wake strip ----------------------------------------------------------------
    wk_img = _load_or_fail(root, EXPECTED["wake"], bad)
    if wk_img is not None:
        wk_w, wk_h = wk_img.size
        report("wake naming + folder", texture_naming_errors(EXPECTED["wake"]),
               f"{EXPECTED['wake']}")
        report("wake dimensions", check_dimensions(wk_w, wk_h, max_dim=VFX_MAX_DIM),
               f"{wk_w}x{wk_h} (VFX atlas limit {VFX_MAX_DIM})")
        report("wake alpha used", has_used_alpha(wk_img.getchannel("A").tobytes()))
        wk_map = json.loads((root / EXPECTED["wake_json"]).read_text(encoding="utf-8"))
        report("wake json naming", texture_naming_errors(EXPECTED["wake"],
                                                         wk_map.get("atlas")),
               f"json atlas ref {wk_map.get('atlas')!r}")
        report("wake pixel hash", pixel_hash_errors(wk_img, wk_map, "T_VX_Wake_A"),
               f"pillow {wk_map.get('pillow_version')} / numpy {wk_map.get('numpy_version')}")
        rows = _alpha_rows(wk_img)
        v = seam_metrics(rows)
        report("wake tileable along length (vertical seam)",
               tileable_errors(v),
               f"alpha seam {v['seam']:.1f} interior {v['interior']:.1f} ratio {v['ratio']:.2f}")
        cols = _alpha_rows(wk_img.transpose(Image.Transpose.ROTATE_90))
        hz = seam_metrics(cols)
        report("wake tileable across width (horizontal seam)", tileable_errors(hz),
               f"alpha seam {hz['seam']:.1f} interior {hz['interior']:.1f} ratio {hz['ratio']:.2f}")
        wk_energy = transparent_rgb_energy(_rgba_tuples(wk_img.tobytes()))
        report("wake transparent-pixel RGB energy",
               transparent_bleed_errors(wk_energy,
                                        bool(wk_map.get("transparent_rgb_bleed"))),
               f"{wk_energy} behind alpha == 0")
        lum, cnt = min_visible_luminance(_rgba_tuples(wk_img.tobytes()))
        report("wake min visible brightness (informational)", [],
               f"min visible max-channel {lum} over {cnt} px")

    return ok, bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", type=Path)
    a = ap.parse_args(argv)
    ok, bad = run_checks(a.root)
    for line in ok + bad:
        print(line)
    n_pass = len([line for line in ok if line.startswith("PASS")])
    n_fail = len([line for line in bad if line.startswith("FAIL")])
    print(f"\n{n_pass} passed, {n_fail} failed")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
