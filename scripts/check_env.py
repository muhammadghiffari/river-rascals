#!/usr/bin/env python3
"""Verify a machine is ready for River Rascals development. Safe to run repeatedly."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys

REQUIRED = {"git": ["git", "--version"], "git-lfs": ["git", "lfs", "version"],
            "gh": ["gh", "--version"], "python": [sys.executable, "--version"]}
RECOMMENDED = {"uv": ["uv", "--version"], "opencode": ["opencode", "--version"],
               "node": ["node", "--version"]}


def ver(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        out = (r.stdout or r.stderr).strip().splitlines()
        first = out[0] if out else ""
        # A non-zero exit means the tool (or git subcommand) is not really usable,
        # e.g. `git lfs version` prints "'lfs' is not a git command" and exits 1.
        return f"error: {first}" if r.returncode != 0 else first
    except Exception as e:  # noqa: BLE001
        return None if isinstance(e, FileNotFoundError) else f"error: {e}"


def main() -> int:
    print(f"OS: {platform.platform()}  Python: {platform.python_version()}")
    bad = 0
    for group, tools, must in (("REQUIRED", REQUIRED, True), ("RECOMMENDED", RECOMMENDED, False)):
        print(f"\n{group}")
        for name, cmd in tools.items():
            v = ver(cmd)
            ok = v is not None and not v.startswith("error")
            print(f"  [{'OK' if ok else ('MISSING' if must else 'warn')}] {name}: {v}")
            bad += (not ok) and must
    print("\nGIT IDENTITY (bootstrap commit fails without it)")
    for key in ("user.name", "user.email"):
        r = subprocess.run(["git", "config", "--get", key], capture_output=True, text=True)
        ok = r.returncode == 0 and bool(r.stdout.strip())
        print(f"  [{'OK' if ok else 'MISSING'}] git config {key}")
        bad += not ok
    hp = subprocess.run(["git", "config", "--get", "core.hooksPath"], capture_output=True, text=True)
    print(f"  [{'OK' if hp.stdout.strip() == 'scripts/hooks' else 'warn'}] core.hooksPath "
          "(run: git config core.hooksPath scripts/hooks)")
    print("\nUPBGE")
    base = os.environ.get("UPBGE_PATH")
    if base and any(os.path.exists(os.path.join(base, n)) for n in ("blenderplayer", "blenderplayer.exe")):
        print(f"  [OK] UPBGE_PATH={base}")
    else:
        print("  [MISSING] set UPBGE_PATH to the folder containing blenderplayer(.exe) and blender(.exe)")
        bad += 1
    print("\nENV (names only, values never printed)")
    for k in ("GITHUB_TOKEN", "GATEWAY_API_KEY"):
        print(f"  [{'set' if os.environ.get(k) else 'unset'}] {k}")
    if shutil.which("gh"):
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        print(f"\ngh auth: {'logged in' if r.returncode == 0 else 'NOT logged in (run: gh auth login)'}")
    print("\nResult:", "READY" if not bad else f"{bad} blocking issue(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
