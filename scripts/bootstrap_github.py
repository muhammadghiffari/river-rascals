#!/usr/bin/env python3
"""One-shot GitHub bootstrap for the repo owner's agent.

Usage:
  python scripts/bootstrap_github.py --repo OWNER/river-rascals --visibility private \
      --collaborators alice,bob [--dry-run] [--skip-issues]

Idempotent where possible. Requires: git, git-lfs, gh (authenticated: `gh auth login`).
Prints every command. NEVER prints tokens. Branch protection on PRIVATE repos needs a paid
GitHub plan; the script reports and continues if the API refuses.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABELS = {
    "type:feature": "0e8a16", "type:bug": "d73a4a", "type:art": "5319e7", "type:audio": "1d76db",
    "type:docs": "0075ca", "type:infra": "fbca04", "type:spike": "c5def5", "type:qa": "bfdadc",
    "area:physics": "ededed", "area:gameplay": "ededed", "area:ui": "ededed", "area:level": "ededed",
    "area:animation": "ededed", "area:tools": "ededed", "area:release": "ededed",
    "owner:P1": "ff9f1c", "owner:P2": "2ec4b6", "owner:P3": "e71d36",
    "risk:high": "b60205", "blocked": "000000", "agent-ready": "0e8a16",
}
MILESTONES = [
    "M0 Foundation", "M1 Tech Spikes", "M2 Vertical Slice",
    "M3 Alpha", "M4 Beta", "M5 Release",
]


def run(cmd, dry, check=True, capture=False):
    print("$", " ".join(cmd))
    if dry:
        return None
    r = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=capture)
    if check and r.returncode != 0:
        print(r.stderr if capture else "", file=sys.stderr)
        sys.exit(f"command failed: {' '.join(cmd)}")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="OWNER/NAME")
    ap.add_argument("--visibility", choices=["private", "public"], default="private")
    ap.add_argument("--collaborators", default="", help="comma-separated GitHub usernames")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-issues", action="store_true")
    a = ap.parse_args()
    d = a.dry_run

    run(["git", "lfs", "install", "--skip-repo"], d)
    if not (ROOT / ".git").exists():
        run(["git", "init", "-b", "main"], d)
    run(["git", "add", "-A"], d)
    run(["git", "commit", "-m", "chore: initial project scaffold from handover pack"], d, check=False)

    exists = run(["gh", "repo", "view", a.repo], d, check=False, capture=True)
    if d or (exists and exists.returncode != 0):
        run(["gh", "repo", "create", a.repo, f"--{a.visibility}", "--source", ".",
             "--remote", "origin", "--push"], d)
    else:
        print("repo exists; pushing")
        run(["git", "push", "-u", "origin", "main"], d, check=False)

    for name, color in LABELS.items():
        run(["gh", "label", "create", name, "--color", color, "--force", "--repo", a.repo],
            d, check=False)
    for m in MILESTONES:
        run(["gh", "api", f"repos/{a.repo}/milestones", "-f", f"title={m}"],
            d, check=False, capture=True)

    for user in [u.strip() for u in a.collaborators.split(",") if u.strip()]:
        run(["gh", "api", "-X", "PUT", f"repos/{a.repo}/collaborators/{user}",
             "-f", "permission=push"], d, check=False)

    protection = {
        "required_status_checks": {"strict": True, "contexts": ["test"]},
        "enforce_admins": False,
        "required_pull_request_reviews": {"required_approving_review_count": 1},
        "restrictions": None,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    if d:
        print("$ gh api -X PUT repos/%s/branches/main/protection  (JSON body omitted in dry-run)" % a.repo)
    else:
        p = subprocess.run(
            ["gh", "api", "-X", "PUT", f"repos/{a.repo}/branches/main/protection", "--input", "-"],
            input=json.dumps(protection), text=True, capture_output=True, cwd=ROOT)
        print("branch protection:", "OK" if p.returncode == 0 else
              "SKIPPED (plan limitation or missing permission): " + p.stderr.strip()[:200])

    if not a.skip_issues:
        issue_cmd = [sys.executable, "scripts/create_issues.py", "--repo", a.repo]
        run(issue_cmd + (["--dry-run"] if d else []), False)
    print("\nBootstrap finished. Next: verify CI is green on main, then notify teammates (docs/12).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
