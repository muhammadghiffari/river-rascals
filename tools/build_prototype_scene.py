#!/usr/bin/env python3
"""Build, wire and verify game/main.blend with the pinned UPBGE build.

Three passes, because this UPBGE build cannot do all of it in one:

  1. geometry   `blender -b   --python tools/blender/build_prototype.py`
  2. logic      `blender      --python tools/blender/wire_prototype_logic.py`  (windowed)
  3. verify     `blender -b main.blend --python tools/blender/verify_prototype_scene.py`

Pass 2 must be windowed: `bpy.ops.logic.sensor_add` access-violates under `-b`.
Pass 2 also exits via `os._exit`, so its exit code is not evidence. Success is
decided by the stdout markers and by pass 3 re-opening the saved file.

Usage (set UPBGE_PATH to the folder holding blender/blenderplayer):
  python tools/build_prototype_scene.py
  python tools/build_prototype_scene.py --verify-only
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_game import find_exe, host_path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BLEND = ROOT / "game/main.blend"
BUILD = ROOT / "tools/blender/build_prototype.py"
WIRE = ROOT / "tools/blender/wire_prototype_logic.py"
VERIFY = ROOT / "tools/blender/verify_prototype_scene.py"
NOISE = ("LogicNode", "Bricky", "addon_utils", "bge_netlogic", "DeprecationWarning",
         "use_nodes", "Registering", "Unregistering", "Removing Game", "_old_selected",
         "active_object", "mod.register", "Traceback (most recent call last)",
         "AttributeError", "During handling")


def run(label: str, argv: list[str], marker: str) -> tuple[bool, str]:
    print(f"--- {label}: {' '.join(argv)}")
    done = subprocess.run(argv, capture_output=True, text=True)
    interesting = [line for line in (done.stdout + done.stderr).splitlines()
                   if line.strip() and not any(noise in line for noise in NOISE)]
    for line in interesting[-12:]:
        print("   ", line)
    found = any(marker in line for line in interesting)
    print(f"    exit={done.returncode} marker({marker})={'yes' if found else 'NO'}")
    return found, "\n".join(interesting)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    blender = find_exe("blender")
    print(f"blender: {blender}")

    if not args.verify_only:
        built, _ = run("1/3 geometry (background)",
                       [blender, "-b", "--factory-startup", "--python-exit-code", "1",
                        "--python", host_path(BUILD, blender)],
                       "PROTOTYPE_ASSETS")
        if not built or not BLEND.is_file():
            print("FAILED: geometry pass did not produce game/main.blend")
            return 1
        wired, _ = run("2/3 logic bricks (windowed)",
                       [blender, host_path(BLEND, blender), "--factory-startup",
                        "--python", host_path(WIRE, blender)],
                       "WIRE_OK")
        if not wired:
            print("FAILED: logic wiring pass did not report WIRE_OK")
            return 1

    if not BLEND.is_file():
        print("FAILED: game/main.blend does not exist")
        return 1
    ok, output = run("3/3 verify saved scene (background)",
                     [blender, "-b", host_path(BLEND, blender), "--factory-startup",
                      "--python-exit-code", "1", "--python", host_path(VERIFY, blender)],
                     "VERIFY_OK")
    if not ok:
        print("FAILED: saved scene did not verify")
        for line in output.splitlines():
            if "VERIFY_FAIL" in line or '"problems"' in line:
                print("   ", line)
        return 1
    size = BLEND.stat().st_size
    print(f"OK: game/main.blend built, wired and verified ({size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
