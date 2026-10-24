# 17 - Verification Status (automated vs manual)
Last automated run: 2026-10-23 (Linux sandbox, Python 3.12, OpenCode 1.19.4). No UPBGE, Blender, GitHub account or model gateway was available.

## 1. Verified automatically (re-run these yourself)
| Check | Command | Result |
|---|---|---|
| Unit + repo-consistency + physics-target tests | `python -m unittest discover -s tests` and `python -m pytest -q` | 28 passed |
| Lint (same as CI) | `ruff check src tests tools scripts game` | clean |
| Syntax of all Python incl. bge/bpy scripts | `python -m compileall -q src tools scripts game` | OK (syntax only, not behaviour) |
| JSON validity | backlog + opencode.json | OK |
| OpenCode config | `opencode debug config`, `opencode agent list` (v1.19.4) | 10 agents, effective permissions as intended; example provider config parses |
| GitHub bootstrap | `python scripts/bootstrap_github.py --repo X/y --dry-run` | prints 6 milestones, 20 labels, 56 issues; labels/milestones in backlog all exist in the script |
| Data | 56 backlog, 83 assets, 64 audio, all with prompts | OK |

## 2. NOT verified (do not assume)
- Every `bge.*` / `bpy` call in `src/rr/glue`, `game/rr_components.py`, `tools/blender/*`, `tools/run_game.py` (marked VERIFY).
- Raft feel, buoyancy coupling with Bullet, performance on any laptop.
- Blender MCP with UPBGE (S-04): addon installs and registers in UPBGE 0.50, env var names confirmed for `mcp-for-blender` 2.2.4 (2026-10-24); the MCP socket round-trip (create/delete cube from OpenCode) is still unverified.
- Real bootstrap (repo creation, branch protection on a private free repo, LFS quota), CI run on GitHub.
- Models `Greg/*` and whether the gateway honours `reasoningEffort`.
- Physics targets only paper-checked (`docs/07` section 11).

## 3. Manual checklist for the agents (per machine, during M0/M1)
1. Download the pinned **stable** UPBGE (0.50, Blender 5.0.1; not weekly alpha), extract anywhere, set `UPBGE_PATH` to the folder containing `blenderplayer`/`blender`; run `python scripts/check_env.py` until READY.
2. Record version + SHA-256 in `docs/03` section 2 (S-01).
3. Generate/open the spike scene, run `python tools/run_game.py game/<scene>.blend --smoke --seconds 20`; fix each `VERIFY` item found, replacing guesses with facts, in small PRs.
4. P2: Blender MCP check (`docs/08` section 8). P3: fill `docs/16` and baseline scenes.
5. Real bootstrap only after the dry-run output is reviewed (`docs/00` section 3).
Rule: report any failure honestly; never mark VERIFY items done without the command output.

## 4. Provenance of this pack
Rebuilt in a continuation session from the command history of the original session (packet Appendix A), then audited. Fixes made during that audit are listed in `CHANGELOG.md`.
