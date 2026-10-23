#!/usr/bin/env python3
"""Create GitHub issues from backlog/backlog.json using the gh CLI.

Usage: python scripts/create_issues.py --repo OWNER/NAME [--dry-run] [--only M1]
Skips issues whose exact title already exists (safe to re-run).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BACKLOG = Path(__file__).resolve().parent.parent / "backlog" / "backlog.json"


def existing_titles(repo: str) -> set[str]:
    r = subprocess.run(["gh", "issue", "list", "--repo", repo, "--state", "all", "--limit", "500",
                        "--json", "title"], capture_output=True, text=True)
    return {i["title"] for i in json.loads(r.stdout or "[]")} if r.returncode == 0 else set()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="", help="milestone prefix filter, e.g. M1")
    a = ap.parse_args()
    items = json.loads(BACKLOG.read_text(encoding="utf-8"))
    have = set() if a.dry_run else existing_titles(a.repo)
    made = 0
    for it in items:
        if a.only and not it["milestone"].startswith(a.only):
            continue
        if it["title"] in have:
            print("skip (exists):", it["title"])
            continue
        body = it["body"] + (
            f"\n\n---\nID: {it['id']} | Suggested agent: `{it['agent']}` | Owner: {it['owner']}"
        )
        cmd = ["gh", "issue", "create", "--repo", a.repo, "--title", it["title"], "--body", body,
               "--milestone", it["milestone"]]
        for lb in it["labels"] + [f"owner:{it['owner']}"]:
            cmd += ["--label", lb]
        print("$ gh issue create ...", it["id"], it["title"])
        if not a.dry_run:
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print("  FAILED:", r.stderr.strip()[:200], file=sys.stderr)
                continue
        made += 1
    print(f"{made} issue(s) {'would be ' if a.dry_run else ''}created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
