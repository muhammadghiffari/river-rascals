# River Rascals (working title)

Cozy-chaotic, physics-based co-op rafting adventure on **UPBGE** (Python). Local co-op 1-4 players first; online is a stretch goal.
Team: 3 humans (P1 lead/tech, P2 art/tech-art, P3 design/audio/QA) + AI agents driven by **OpenCode**.
All original IP; genre inspiration only.

## Start here
- Agent handover runbook: `docs/00_START_HERE_AGENT.md` (the owner's agent runs this first)
- What is verified and what is NOT: `docs/17_VERIFICATION_STATUS.md`
- Rules for every agent: `AGENTS.md`

## Quick start
```bash
python scripts/check_env.py
python -m unittest discover -s tests -v     # pytest also works
python scripts/bootstrap_github.py --repo OWNER/river-rascals --collaborators USER_P2,USER_P3 --dry-run
```
UPBGE is portable: download the pinned stable build, extract anywhere, set `UPBGE_PATH` to its folder.

## Documents
| # | Doc | # | Doc |
|---|---|---|---|
| 01 | PRD | 10 | Phase prompts (per phase, with model + effort) |
| 02 | GDD | 11 | Team plan, task split, RACI |
| 03 | Technical architecture | 12 | Git workflow and GitHub setup |
| 04 | Asset bible and pipeline | 13 | QA and performance plan |
| 05 | Animation spec | 14 | Risk register |
| 06 | Audio spec | 15 | Release checklist |
| 07 | Physics spec | 16 | Hardware profiles |
| 08 | MCP best practices | 17 | Verification status |
| 09 | Model routing and reasoning | | |

Generated data: `backlog/backlog.json` (56 issues), `docs/reference/ASSET_LIST.csv` (83), `docs/reference/AUDIO_LIST.csv` (64);
prompt libraries in `prompts/`. Licence: not chosen yet (open decision for P1; until then all rights reserved).
