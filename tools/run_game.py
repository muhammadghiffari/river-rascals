#!/usr/bin/env python3
"""Launch the game (or a smoke test) with the pinned UPBGE build.

Env: UPBGE_PATH = folder containing `blenderplayer` and `blender` (see docs/12).

Exit codes:
  0      success (smoke verdict ok:true with a clean engine exit; plain run exit 0)
  1      smoke failed (engine exited non-zero, or the report says ok:false)
  2      no smoke verdict possible (timeout, no report file, unreadable report)
  other  plain run: the child's own exit status passes through unchanged
         (e.g. a Windows crash status such as 3221225477 / 0xC0000005; POSIX
         keeps only the low 8 bits of any child exit status)

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


def fmt_exit_code(code: int) -> str:
    """Exit status in decimal plus hex, e.g. '3221225477 (0xC0000005)'; signals print as '-11'."""
    return f"{code} (0x{code:08X})" if code >= 0 else str(code)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("blend")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--editor", action="store_true", help="open in Blender instead of blenderplayer")
    a = ap.parse_args()

    env = os.environ.copy()
    out = Path("smoke_result.json")
    if a.smoke:
        env.update(RR_SMOKE="1", RR_SMOKE_SECONDS=str(a.seconds), RR_SMOKE_OUT=str(out))
        out.unlink(missing_ok=True)
    exe = find_exe("blender" if a.editor else "blenderplayer")
    timeout = a.seconds + 60 if a.smoke else None
    try:
        result = subprocess.run([exe, a.blend], env=env, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        print("SMOKE FAIL: timeout")
        return 2
    if a.smoke:
        if result.returncode != 0:
            print(f"SMOKE FAIL: engine exited with code {fmt_exit_code(result.returncode)}")
            return 1
        if not out.exists():
            print("SMOKE FAIL: no result file written")
            return 2
        try:
            rep = json.loads(out.read_text())
        except (OSError, ValueError):
            print("SMOKE FAIL: unreadable result")
            return 2
        if not isinstance(rep, dict):
            print("SMOKE FAIL: unreadable result")
            return 2
        print(json.dumps(rep, indent=2))
        return 0 if rep.get("ok") else 1
    if result.returncode != 0:
        print(f"note: engine exited with code {fmt_exit_code(result.returncode)}", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
