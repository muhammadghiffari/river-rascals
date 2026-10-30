# 11 — Team Plan, Task Split & RACI

## 1. Roles (3 humans + agents)
| Role | Person | Machine | Primary responsibilities | Agents mostly used |
|---|---|---|---|---|
| **P1 — Lead / Tech / Gameplay code** | Repo owner | owner's machine | GitHub setup, CI, architecture, engine pin, physics & gameplay code, integration, merges, releases, cost tracking | architect, builder, gameplay, debugger, release |
| **P2 — Art / Tech-Art / Animation** | Friend A | **ASUS V16 (Tier A, strong)** | Blender MCP, all 3D assets, rigs, animation, shaders, VFX sprites, perf profiling at High preset, intro cinematic | techart, reviewer (asset), docs |
| **P3 — Design / Level / UI / Audio / QA** | Friend B | **mid-spec laptop (Tier C per `docs/16` post-#65)** | GDD upkeep, level design & placement, HUD/menu implementation (with agents), audio sourcing/integration, playtests, Tier C perf baselines, build verification | qa, gameplay (UI), architect (level docs), docs |
Everyone: reviews at least 2 PRs/week (human sanity check on top of `@reviewer`), keeps issues updated, runs `check_env.py` weekly.

## 2. Hardware roles
- **ASUS V16 (P2)**: authoring + heaviest rendering tests; target "High" preset ≥ 60 fps; optional **self-hosted GitHub runner** later. Do not treat it as the performance baseline.
- **Mid-spec laptop (P3)**: **the performance truth**. Every milestone must pass here. Fill `16_HARDWARE_PROFILES.md` in week 1.
- **P1 machine**: coding + physics tuning; must also run smoke tests.

## 3. RACI (R=does, A=accountable, C=consulted, I=informed)
| Area | P1 | P2 | P3 |
|---|---|---|---|
| Repo, CI, branching, releases | **A/R** | I | C |
| Engine version & build/export | **A** | C | **R** (build tests) |
| Raft physics, input, hazards, co-op code | **A/R** | C | C |
| Level design (docs + placement) | C | C | **A/R** |
| 3D assets, rigs, animation, shaders | C | **A/R** | C (fps tests) |
| VFX (sprites + spawner) | R (spawner) | **A/R** (assets) | C |
| UI/HUD/menus | C | C (art) | **A/R** (with gameplay agent) |
| Audio (sourcing, mix, integration) | R (system code) | I | **A/R** |
| QA, playtests, perf reports | C | C (Tier A) | **A/R** |
| Docs upkeep | R | R | **A** (GDD) / P1 (tech docs) |
| Security & licence audit | **A/R** | C | C |
| Cost tracking of model usage | **A/R** | I | I |

## 4. Weekly cadence (suggested)
Mon 20 min planning (R3 prompt) · daily async handoff notes (R1) · Wed mid-week sync 15 min (blockers) · **Fri playtest + build** (P3 runs smoke + notes) · Sat/Sun buffer. Demo video every 2 weeks to keep motivation high.

## 5. Project board & flow
GitHub Project columns: **Backlog → Ready (agent-ready) → In progress → In review → Done**. Issue labels: `type:*`, `area:*`, `owner:P1/P2/P3`, `risk:high`, `blocked`, `agent-ready`. WIP limit: max 2 in progress per person. An issue is **Ready** only with goal + acceptance criteria + suggested agent.
Workflow: pick issue → branch → agent does work → local tests → PR → `@reviewer` + human review → CI green → squash merge → close issue → note in handoff.

## 6. Timeline (20 weeks) and who does what
| Wk | Milestone | P1 | P2 | P3 |
|---|---|---|---|---|
| 1 | M0 | F-01/02/03/06 repo, CI, onboarding | F-04 UPBGE + MCP smoke | F-05 hardware profile + baselines |
| 2–3 | M1 | S-01, S-02, S-03, S-07 | S-04, S-05, art kickoff, palette/MT_ToonBase | S-06 build export, S-08 gamepad, benchmark prep |
| 4–5 | M2 | V-01, V-02, V-04 | V-11 raft/oars, V-12 otter start | V-10 Ch1 blockout, V-09 HUD start |
| 6–7 | M2 | V-03, V-05, V-06, V-08 | V-12 anims, V-13 env kit, VX | V-07, V-09, V-14 audio v1, **V-15 playtest** |
| 8–9 | M3 | A-03 whirlpool, A-04 waterfall | A-12 props, A-08 NPCs | A-01 Ch2, A-13 tutorial |
| 10–11 | M3 | A-06 co-op, A-05 AI crew | A-10 VFX, RF T2 | A-02 Ch3, A-11 localization |
| 12–13 | M3 | A-07 progression, A-09 music | RF T3, anims P1 | audio pass 2, alpha playtest |
| 14–15 | M4 | B-03 perf, B-08 logging | B-01 assets night, B-07 intro | B-01 Ch4, B-04 accessibility |
| 16–17 | M4 | B-05 balance, bugfix | B-02 storm assets | B-02 Ch5, B-06 mix, B-09 bug bash |
| 18 | M5 | R-01 RC build | polish/bug art | R-03 store assets, clean-install tests |
| 19 | M5 | R-02 audit, fixes | fixes | regression playthroughs |
| 20 | M5 | R-04 release | | |
**Cut order if late**: stretch → Ch4/Ch5 polish → extra cosmetics → AI crew sophistication → never cut core raft feel, stability, checkpoints/save.

## 7. Ownership map (merge-conflict avoidance)
| Path | Owner |
|---|---|
| `src/`, `tests/`, `tools/`(non-blender), `scripts/`, `.github/`, `opencode.json`, `docs/03,07,08,09,12` | P1 |
| `assets/**` (except audio/ui), `tools/blender/`, `docs/04,05` | P2 |
| `assets/audio/**`, `assets/ui/**`, `game/levels/`, `docs/02,06,13,14,15` | P3 |
| `game/*.blend` | one person at a time via `git lfs lock`; level `.blend` = P3, `main.blend`/`hud.blend` = P1/P3 coordinate in chat |
Cross-area edits: open an issue/PR and tag the owner.

## 8. Communication
One chat group (Discord/WhatsApp), GitHub issues for decisions, `docs/` for durable knowledge, handoff notes (R1). Decisions that change scope/cost go to the decision log in `03 §15`.

## 9. Definition of Done (team)
Acceptance met · tests/smoke evidence · docs updated · PR reviewed by agent + human · merged green · issue closed with a one-line outcome.

## 10. Wellbeing/workload guardrails
Cap ~10–15 h/week/person; no crunch weeks; if two consecutive weeks slip, re-plan (R3) instead of pushing harder.
