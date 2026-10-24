#!/usr/bin/env python3
"""Launch the game (or a smoke test) with the pinned UPBGE build.

Env: UPBGE_PATH = folder containing `blenderplayer` and `blender` (see docs/12).
Examples:
  python tools/run_game.py game/main.blend
  python tools/run_game.py game/ch01_sleepy_creek.blend --smoke --seconds 20
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_exe(name: str) -> str:
    base = os.environ.get("UPBGE_PATH")
    candidates = [name, name + ".exe"]
    if base:
        for c in candidates:
            p = Path(base) / c
            if p.exists():
                return str(p)
    for c in candidates:
        found = shutil.which(c)
        if found:
            return found
    sys.exit(f"Cannot find '{name}'. Set UPBGE_PATH to the UPBGE folder.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("blend")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--editor", action="store_true", help="open in Blender instead of blenderplayer")
    a = ap.parse_args()

    env = os.environ.copy()
    # Python Components live in game/rr_components.py and import rr.* from src/.
    # VERIFY: blenderplayer/Blender may ignore PYTHONPATH unless started with
    # --python-use-system-env; this is a best-effort hint, and the generator also
    # inserts game/ on sys.path when registering the component.
    root = Path(__file__).resolve().parent.parent
    env["PYTHONPATH"] = os.pathsep.join(
        [str(root / "game"), str(root / "src"), env.get("PYTHONPATH", "")]).strip(os.pathsep)
    out = Path("smoke_result.json")
    if a.smoke:
        env.update(RR_SMOKE="1", RR_SMOKE_SECONDS=str(a.seconds), RR_SMOKE_OUT=str(out))
        out.unlink(missing_ok=True)
    exe = find_exe("blender" if a.editor else "blenderplayer")
    timeout = a.seconds + 60 if a.smoke else None
    try:
        subprocess.run([exe, a.blend], env=env, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        print("SMOKE FAIL: timeout")
        return 2
    if a.smoke:
        if not out.exists():
            print("SMOKE FAIL: no result file written")
            return 2
        rep = json.loads(out.read_text())
        print(json.dumps(rep, indent=2))
        return 0 if rep.get("ok") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
