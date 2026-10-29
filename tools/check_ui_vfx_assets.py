#!/usr/bin/env python3
"""Pure-Python checker for the generated UI/VFX atlases (docs/04 sections 3-5).

Validation logic (sizes, power-of-two, alpha presence, atlas-map bounds, seam
jump, additive brightness) is written against plain Python data structures so it
is unit-testable without Pillow. Pillow is imported lazily and is only used to
decode pixels from disk.

Usage: python tools/check_ui_vfx_assets.py [--root .]
Exit code 1 if any check fails.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

try:  # only needed to decode pixels; the checks below stay importable without it
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

MAX_DIM = 2048  # docs/04 s4: power-of-two, <= 2048
VISIBLE_ALPHA = 32  # a pixel is "visible" from here on
ADDITIVE_MIN_LUMA = 150  # no dark pixels may carry alpha (additive would darken)
SEAM_RATIO_LIMIT = 1.5  # seam jump may exceed the worst interior step by <= 50%


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

    `pixels` yields (r, g, b, a) tuples. Used for the additive-friendly rule:
    any pixel that contributes light must be bright enough not to darken.
    """
    min_lum = 255
    count = 0
    for r, g, b, a in pixels:
        if a >= VISIBLE_ALPHA:
            count += 1
            lum = max(r, g, b)
            min_lum = min(min_lum, lum)
    return min_lum, count


def additive_errors(min_lum: int, count: int,
                    threshold: int = ADDITIVE_MIN_LUMA) -> list[str]:
    if count == 0:
        return ["no visible pixels at all"]
    if min_lum < threshold:
        return [f"darkest visible pixel has max-channel {min_lum} < {threshold} "
                "(would darken under additive blending)"]
    return []


# --- Pillow-dependent loading ------------------------------------------------------


def _load(path: Path):
    if Image is None:
        raise RuntimeError("Pillow is required to load images: pip install pillow")
    return Image.open(path).convert("RGBA")


def _luma_rows(img) -> list[list[int]]:
    lum = img.convert("L")
    w, h = lum.size
    data = lum.tobytes()
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
    ui_img = _load(root / EXPECTED["ui_atlas"])
    ui_w, ui_h = ui_img.size
    report("ui atlas dimensions", check_dimensions(ui_w, ui_h), f"{ui_w}x{ui_h}")
    report("ui atlas alpha used", has_used_alpha(ui_img.getchannel("A").tobytes()))

    ui_map = json.loads((root / EXPECTED["ui_json"]).read_text(encoding="utf-8"))
    entries = ui_map["icons"]
    report("ui atlas map in bounds", atlas_map_errors(entries, ui_w, ui_h),
           f"{len(entries)} icons")
    with (root / EXPECTED["ui_csv"]).open(encoding="utf-8") as fh:
        csv_rows = list(csv.DictReader(fh))
    csv_match = [{k: int(v) if k != "name" else v for k, v in r.items()} for r in csv_rows]
    report("ui csv matches json", [] if csv_match == entries else ["CSV rows differ from JSON icons"])

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
    sp_img = _load(root / EXPECTED["splash"])
    sp_w, sp_h = sp_img.size
    report("splash dimensions", check_dimensions(sp_w, sp_h), f"{sp_w}x{sp_h}")
    report("splash alpha used", has_used_alpha(sp_img.getchannel("A").tobytes()))
    sp_map = json.loads((root / EXPECTED["splash_json"]).read_text(encoding="utf-8"))
    fs = sp_map["frame_size"][0]
    frame_errors = []
    if sp_map["grid"] != [4, 4] or fs != 128 or sp_w != 512:
        frame_errors.append(f"unexpected layout {sp_map['grid']} frame {fs} atlas {sp_w}")
    # frame 0 must burst (bright visible pixels), frame 15 must have faded out
    f0 = _cell_rgba(sp_img, 0, 0, fs, fs)
    if alpha_usage_stats(px[3] for px in f0)["visible"] < 64:
        frame_errors.append("frame 0 has almost no visible pixels")
    f15 = _cell_rgba(sp_img, 3 * fs, 3 * fs, fs, fs)
    if alpha_usage_stats(px[3] for px in f15)["visible"] > 0:
        frame_errors.append("frame 15 has not fully faded")
    report("splash frame layout + fade", frame_errors)
    lum, cnt = min_visible_luminance(_rgba_tuples(sp_img.tobytes()))
    report("splash additive-friendly", additive_errors(lum, cnt),
           f"min visible max-channel {lum} over {cnt} px")

    # --- wake strip ----------------------------------------------------------------
    wk_img = _load(root / EXPECTED["wake"])
    wk_w, wk_h = wk_img.size
    report("wake dimensions", check_dimensions(wk_w, wk_h), f"{wk_w}x{wk_h}")
    report("wake alpha used", has_used_alpha(wk_img.getchannel("A").tobytes()))
    rows = _luma_rows(wk_img)
    v = seam_metrics(rows)
    report("wake tileable along length (vertical seam)",
           tileable_errors(v), f"seam {v['seam']:.1f} interior {v['interior']:.1f} ratio {v['ratio']:.2f}")
    cols = _luma_rows(wk_img.transpose(Image.Transpose.ROTATE_90))
    hz = seam_metrics(cols)
    report("wake tileable across width (horizontal seam)", tileable_errors(hz),
           f"seam {hz['seam']:.1f} interior {hz['interior']:.1f} ratio {hz['ratio']:.2f}")
    lum, cnt = min_visible_luminance(_rgba_tuples(wk_img.tobytes()))
    report("wake additive-safe", additive_errors(lum, cnt),
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
