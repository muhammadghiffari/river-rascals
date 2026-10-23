# 12 — Git Workflow & GitHub Setup

## 1. Branching (trunk-based)
`main` is always playable-ish and CI-green. Short-lived branches (≤ 3 days): `feat/…`, `fix/…`, `art/<asset-id>`, `audio/…`, `docs/…`, `chore/…`, `spike/…`. Squash-merge PRs. Tags `vMAJOR.MINOR.PATCH` (0.x before the vertical slice is signed off).

## 2. Commit convention
Conventional Commits: `feat(raft): add buoyancy sampling`, `fix(river): clamp projection at ends`, `art(raft): RF_RaftT1 blockout`, `docs: …`, `chore(ci): …`, `test: …`. Subject ≤ 72 chars, imperative, body explains why.

## 3. Pull requests
Template auto-fills. Required: linked issue, test evidence, VERIFY list, screenshots/GIF for visual changes, CI green, ≥ 1 approving review (human) — the `@reviewer` agent is an *additional* reviewer, not a substitute. Self-merge allowed only for docs-only changes by the owner.

## 4. Git LFS
`.gitattributes` tracks `.blend`, images, audio, video, fonts, fbx/glb, zip. First-time per machine: `git lfs install`. After clone: `git lfs pull`. Check: `git lfs ls-files`. **Never commit large binaries before LFS is installed on that machine** (history rewrite is painful). CI checks that files > 5 MB are LFS.
**Quota (verified 2026-10-23 against GitHub Docs "About billing for Git Large File Storage")**: GitHub Free/Pro include **10 GiB storage + 10 GiB download bandwidth per month**, max **2 GB per LFS file**. Metered beyond that; with a $0 budget (default) LFS downloads are blocked until the next billing cycle. Every `git lfs pull` by a teammate **and every CI run that pulls LFS** (our CI uses `lfs: false`, keep it so) counts against the repository owner's bandwidth. Re-check the numbers before relying on them. Mitigations: keep raw sources (PSD, 4K renders, long WAV masters) **outside git** (shared drive), commit game-ready OGG/PNG only, prune old `_vNN.blend` checkpoints (keep them local), avoid committing `*.blend1`, consider buying a GitHub data pack or hosting Git+LFS on an alternative (Gitea/GitLab) if limits bite. The owner's agent should check quota monthly (`gh api` / billing page) and log it in §10.

## 5. `.blend` collaboration rules
Binary ⇒ no merges. (1) One asset per file; levels link assets rather than embedding. (2) Before editing: `git pull`, `git lfs lock assets/props/PR_Log.blend`; after merge: `git lfs unlock …`. (3) `git lfs locks` shows who holds what. (4) Never "resolve" a `.blend` conflict by guessing: pick one side, re-apply the other's change manually. (5) Keep file sizes small: purge orphans, no packed huge textures, no undo history bloat (File ▸ Clean Up).
(`lockable` is set in `.gitattributes` for `*.blend`; locking requires LFS lock support on the host — GitHub supports it.)

## 6. CI
Workflow `ci` (lint, unit tests, compile, JSON validity, secret grep, LFS size gate). Required status check: `test`. Local pre-push habit: `python -m unittest discover -s tests && ruff check .`.
**Branch protection**: scripted by `bootstrap_github.py`; on private repos with the free plan GitHub may refuse; then rely on the team rule "PR + review" and consider making the repo public, upgrading, or moving to rulesets if available. Record status in §10.
**Local guard (always do this, any plan):** `git config core.hooksPath scripts/hooks` enables `scripts/hooks/pre-push`, which blocks direct pushes to `main`/`master` even when GitHub protection is unavailable. First-time branch creation is allowed so bootstrap still works. Humans-only emergency override: `RR_ALLOW_MAIN_PUSH=1`. The same folder also carries the Git LFS hooks (LFS cannot install its own while `core.hooksPath` is set); never run `git lfs update --force` here, and use `git lfs install --skip-repo` if you must re-run install.

## 7. Onboarding P2 / P3 (after the owner's agent finished docs/00)
1. Accept the GitHub invitation (email or GitHub → Notifications).
2. Install: Git, **Git LFS**, GitHub CLI (`gh`), Python ≥ 3.10, `uv`, Node (for npx-based tools if needed), OpenCode, **the pinned UPBGE build** (extract anywhere, set `UPBGE_PATH`).
3. `gh auth login` (HTTPS, browser). Then:
```bash
git lfs install
gh repo clone OWNER/river-rascals && cd river-rascals
git lfs pull
python scripts/check_env.py
python -m unittest discover -s tests
```
4. Set env vars (never in files): `UPBGE_PATH`, `GATEWAY_API_KEY` (as your OpenCode provider requires), optional `GITHUB_TOKEN`.
5. Configure OpenCode provider `Greg` in your **global** config per your gateway docs (template: `docs/reference/opencode_global_config.example.jsonc`); optional personal overrides in the git-ignored `.opencode/opencode.jsonc`; run `opencode` in the repo; confirm agents list; `opencode mcp list`.
6. P2 only: Blender MCP setup (`docs/08` §3). P3 only: fill `docs/16`, run the baseline scenes.
7. Pick your first issue from the board (P2: F-04; P3: F-05) → branch → PR.

## 8. Daily commands
```bash
git switch main && git pull --rebase           # start of day
git switch -c feat/<short-desc>                # new work
git add -A && git commit -m "feat(x): ..."     # small commits
git push -u origin HEAD && gh pr create --fill # open PR
gh pr checks --watch                           # wait for CI
gh pr merge --squash --delete-branch           # after approval
```
Never: `git push --force`, committing `.env`, working on `main`.

## 9. Releases
`git tag -a vX.Y.Z -m "…"` → `python tools/package_build.py` (after S-06) → upload zip to GitHub Release (`gh release create`) with checksums and notes (P7.3). Only after `15_RELEASE_CHECKLIST.md` GO.

## 10. Setup log (owner's agent fills)
| Date | Item | Result / evidence |
|---|---|---|
| | Repo URL, visibility | |
| | Branch protection status | |
| | LFS quota (storage/bandwidth) | |
| | CI first green run | |
| | Collaborators accepted | |

## 11. Backups
Repo is the source of truth; additionally P1 keeps a monthly `git bundle` + LFS objects copy on an external drive/cloud (`git bundle create ../rr.bundle --all`; `git lfs fetch --all`).

## 12. Troubleshooting
| Problem | Fix |
|---|---|
| `.blend` shows as tiny text file | LFS not pulled: `git lfs pull` |
| "This repository is over its data quota" | see §4 mitigations; wait for monthly reset or buy data pack |
| Push rejected by protection | open a PR instead |
| CI red on lint | `ruff check . --fix` then review |
| Can't lock file | someone holds it: `git lfs locks`; ask them to unlock |
| gh not authenticated | `gh auth login`; check `gh auth status` |
