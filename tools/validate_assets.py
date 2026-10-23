#!/usr/bin/env python3
"""Run tools/blender/validate_blend.py over every .blend in assets/ using UPBGE/Blender headless.

Usage: python tools/validate_assets.py [--budget-file docs/budgets.json] [paths...]
Exit code 1 if any asset fails.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_game import find_exe  # noqa: E402

SCRIPT = Path(__file__).parent / "blender" / "validate_blend.py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=["assets"])
    a = ap.parse_args()
    blender = find_exe("blender")
    files: list[Path] = []
    for p in a.paths:
        pp = Path(p)
        files += [pp] if pp.is_file() else sorted(pp.rglob("*.blend"))
    if not files:
        print("No .blend files found - nothing to validate.")
        return 0
    failed = 0
    for f in files:
        r = subprocess.run([blender, "-b", str(f), "--python", str(SCRIPT)],
                           capture_output=True, text=True)
        lines = [ln for ln in r.stdout.splitlines() if ln.startswith("[validate]")]
        status = "OK  " if r.returncode == 0 and not any("FAIL" in ln for ln in lines) else "FAIL"
        failed += status == "FAIL"
        print(f"{status} {f}")
        for ln in lines:
            print("   ", ln)
    print(f"{len(files) - failed}/{len(files)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
