# 17 - Verification Status (automated vs manual)
Last automated run: 2026-10-23 (Linux sandbox, Python 3.12, OpenCode 1.19.4). No UPBGE, Blender, GitHub account or model gateway was available.

## 1. Verified automatically (re-run these yourself)
| Check | Command | Result |
|---|---|---|
| Unit + repo-consistency + physics-target + spike-grading tests | `python -m unittest discover -s tests` and `python -m pytest -q` | 42 passed |
| Lint (same as CI) | `ruff check src tests tools scripts game` | clean |
| Syntax of all Python incl. bge/bpy scripts | `python -m compileall -q src tools scripts game` | OK (syntax only, not behaviour) |
| JSON validity | backlog + opencode.json | OK |
| OpenCode config | `opencode debug config`, `opencode agent list` (v1.19.4) | 10 agents, effective permissions as intended; example provider config parses |
| GitHub bootstrap | `python scripts/bootstrap_github.py --repo X/y --dry-run` | prints 6 milestones, 20 labels, 56 issues; labels/milestones in backlog all exist in the script |
| Data | 56 backlog, 83 assets, 64 audio, all with prompts | OK |

## 2. NOT verified (do not assume)
- Every `bge.*` / `bpy` / `aud` call in `src/rr/glue`, `game/rr_components.py`, `tools/blender/*`, `tools/run_game.py` (marked VERIFY).
- S-01 engine spike: `tools/blender/gen_spike_engine.py`, `src/rr/glue/spike_probe.py` and the test matrix in `docs/reports/S-01_engine_decision.md` remain **undecided / incomplete** (no engine pin approved). P2's run (2026-10-26, Catalna, ASUS V16 Tier A, UPBGE 0.50, `blenderplayer`, branch `scratch/s01-p2`) executed all 7 start checks + `tic_rates`, `physics`, `fps` with exit 0 and no `gpu.shader` errors. **OPEN FINDINGS:** `tic_rates` FAIL (`logic=60.0 physics=0.0` — getter returned 0.0, cause unconfirmed); `physics` FAIL (`z=3.00 fell=0.00` — box never fell; scene has RIGID_BODY mass 5, BOX, Bullet, gravity 9.81; cause unconfirmed); `fps` avg=200050.1 is a first-sample artifact, not an engine failure. JSON `"tic"` is the setpoint (60/60), not a measurement. The S-01 matrix, conclusions and engine pin remain unchanged until: physics cause isolated, fixed probe re-run on P1 and P2, and the 0.44.x rows exist. Recorded as OPEN FINDINGS, not pass or fail of 0.50. Windowed component registration is untested; background registration is a known 0.50 Linux segfault. `docs/03` overlay API wording was corrected against the UPBGE docs, not by running it.
- Raft feel, buoyancy coupling with Bullet, performance on any laptop.
- Blender MCP with UPBGE (S-04), env var names for `mcp-for-blender`.
- Real bootstrap (repo creation, branch protection on a private free repo, LFS quota), CI run on GitHub.
- Models `Greg/*` and whether the gateway honours `reasoningEffort`.
- Physics targets only paper-checked (`docs/07` section 11).

## 3. Manual checklist for the agents (per machine, during M0/M1)
1. Download the pinned **stable** UPBGE (0.50, Blender 5.0.1; not weekly alpha), extract anywhere, set `UPBGE_PATH` to the folder containing `blenderplayer`/`blender`; run `python scripts/check_env.py` until READY.
2. Record version + SHA-256 in `docs/03` section 2 (S-01).
3. Run the S-01 spike probe out of `docs/reports/S-01_engine_decision.md` §2.1–2.3: generate the scene **windowed**, export the `RR_SPIKE_*` variables, then launch it in `blenderplayer` through `run_game.py`. Do **not** add `--smoke` here — the spike is driven by `RR_SPIKE_*`, while `--smoke` only sets `RR_SMOKE`/`RR_SMOKE_SECONDS`/`RR_SMOKE_OUT` and then exits with `SMOKE FAIL: no result file written` because the spike scene carries no smoke component:
   ```bash
   "$UPBGE_PATH/blender" --python tools/blender/gen_spike_engine.py -- --out game/spike_engine.blend
   export RR_SPIKE_MACHINE=P3 RR_SPIKE_SECONDS=12 RR_SPIKE_OUT=spike_P3_0.50.json   # Windows: $env:RR_SPIKE_*
   python tools/run_game.py game/spike_engine.blend
   cat spike_P3_0.50.json
   ```
   Then fix each `VERIFY` item found, replacing guesses with facts, in small PRs.
4. P2: Blender MCP check (`docs/08` section 8). P3: fill `docs/16` and baseline scenes.
5. Real bootstrap only after the dry-run output is reviewed (`docs/00` section 3).
Rule: report any failure honestly; never mark VERIFY items done without the command output.

## 4. Provenance of this pack
Rebuilt in a continuation session from the command history of the original session (packet Appendix A), then audited. Fixes made during that audit are listed in `CHANGELOG.md`.
