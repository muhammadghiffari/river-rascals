# 11 — Team Plan, Task Split & RACI

## 1. Roles (3 humans + agents)
| Role | Person | Machine | Primary responsibilities | Agents mostly used |
|---|---|---|---|---|
| **P1 — Lead / Tech / Gameplay code** | Repo owner | owner's machine | GitHub setup, CI, architecture, engine pin, physics & gameplay code, integration, merges, releases, cost tracking | architect, builder, gameplay, debugger, release |
| **P2 — Art / Tech-Art / Animation** | Friend A | **ASUS V16 (Tier A, strong)** | Blender MCP, all 3D assets, rigs, animation, shaders, VFX sprites, perf profiling at High preset, intro cinematic | techart, reviewer (asset), docs |
| **P3 — Design / Level / UI / Audio / QA** | Friend B | **mid-spec laptop (Tier B baseline)** | GDD upkeep, level design & placement, HUD/menu implementation (with agents), audio sourcing/integration, playtests, Tier B perf baselines, build verification | qa, gameplay (UI), architect (level docs), docs |
Everyone: reviews at least 2 PRs/week (human sanity check on top of `@reviewer`), keeps issues updated, runs `check_env.py` weekly.

## 2. Hardware roles
- **ASUS V16 (P2)**: authoring + heaviest rendering tests; target "High" preset ≥ 60 fps; optional **self-hosted GitHub runner** later. Do not treat it as the performance baseline.
- **Mid-spec laptop (P3)**: **the performance truth**. Every milestone must pass here. Fill `16_HARDWARE_PROFILES.md` in week 1.
- **P1 machine**: coding + physics tuning; must also run smoke tests.

## 3. Working tools (both acceptable)
Any agent role in `docs/09` may be run through **OpenCode or Hermes**; both are acceptable clients and neither is
required. What matters is the *model* and the review rule in §6, not the client. Personal client settings
(credentials, private model/agent wiring) stay local and uncommitted; the shared repo-level `opencode.json`, when
present, is P1-owned per §9 and is not a review target for unrelated doc/design PRs.

## 4. RACI (R=does, A=accountable, C=consulted, I=informed)
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

## 5. Weekly cadence (agreed)
One fixed weekly rhythm from M0 onward. Times are team-local; if a slot has to move, move it within the same week —
do not skip it. Sat/Sun stay free (see §12).

| Day | Slot | Activity | Owner | Output |
|---|---|---|---|---|
| Mon | 20 min | **Weekly sync / planning** (R3 prompt) | P1 runs, all attend | board: Ready column filled, ≤ 3 items per person, risks + cut candidates named |
| Wed | 15 min | **Mid-week sync** — blockers only, no status theatre | P1 | blocker issues labelled `blocked`, decision or escalation |
| Fri | 20 min | **Review sweep** — close the review rotation (§6), merge green PRs | rotation reviewer | PRs merged or sent back with a reason |
| Fri | 45 min | **Weekly playtest + build** (see below) | P3 runs, all play | `docs/reports/playtest_YYYY-MM-DD.md`, issues for bugs, fps table on Tier B |
| daily | async | Handoff note (R1) on the active issue | whoever worked last | 10 lines: changed / in progress / decisions / blockers / next 3 |
| every 2 wk | 10 min | Demo video + milestone burndown check | P1 | link posted in chat |

**Weekly playtest rules**
1. **One playtest per week** from M1 onward, even when the build is rough — a blockout with placeholders counts, a
   missing playtest does not.
2. The playtest needs only: a build that boots, the checklist from `docs/02 §16`, 20–30 minutes, and notes written
   down the same day. No polish required.
3. **P3's mid-spec laptop is the performance truth** — the fps table in the notes comes from there, not from P2's
   ASUS V16.
4. If Friday is impossible, move the playtest to Thursday of the same week; never skip two weeks in a row.
5. Every bug found becomes an issue a human can reproduce (build + steps + expected/actual), not a chat message.

## 6. PR review: rotation and model-family rule
**Human rotation** (every PR, no exceptions — the agent `@reviewer` is *additional*, not a substitute):

| PR author | Required human reviewer |
|---|---|
| P1 | P3 |
| P2 | P1 |
| P3 | P2 |

So P1 reviews P2's PRs, P2 reviews P3's, P3 reviews P1's. Each person is therefore both author and reviewer in the
cycle, which keeps review load even at ~2 PRs/week/person. If the rotating reviewer is unavailable for more than
24 h, the third person reviews rather than letting the PR stall — note the substitution in the PR.

**AI-authored PRs** (`risk:high` included):
1. **A PR written by an AI model must be reviewed by a different model family than the author.** DeepSeek-written
   work is reviewed by a Kimi or GLM/Claude-class model, Kimi-written work by DeepSeek/GLM, and so on — see
   `docs/09 §3`, rule 3. Same-family self-review does not count, however green CI is.
2. Every AI PR body must state **author model + reviewer model + client** (OpenCode or Hermes), plus what was run
   and what is marked `VERIFY`.
3. The human in rotation still reviews it. Model review catches layering/tests; humans catch "is this the game we
   wanted".
4. `risk:high` PRs (physics core, save format, build/release, MCP config, co-op) additionally get `security` or
   `architect` review before merge.

## 7. Project board, Definition of Ready & flow
Board: **River Rascals** — https://github.com/users/muhammadghiffari/projects/2 (owner `muhammadghiffari`).
Columns, in order: **Backlog → Ready → In progress → In review → Done**. Every open issue is on the board in
`Backlog` by default; moving a card is the only status anyone needs to check.
Labels: `type:*`, `area:*`, `owner:P1/P2/P3`, `risk:high`, `blocked`, `agent-ready`. WIP limit: **max 2 cards in
progress per person** (a card is in progress once its branch exists).

### Definition of Ready (DoR)
An issue may move **Backlog → Ready** only when all of these are true:
- [ ] **Goal** in one sentence, and it is worth doing now (not "nice to have").
- [ ] **Context** links: the doc section (`docs/…§…`) and any related issue/PR.
- [ ] **Acceptance criteria** as checkboxes that a reviewer can verify — no "works well".
- [ ] **Out of scope** stated, so the assignee does not wander.
- [ ] **Suggested agent + effort** from `docs/09`, and a human **owner** (`owner:P1/P2/P3`).
- [ ] **Sized to ≤ ~1 day** of agent work; larger issues are split first (R6 prompt).
- [ ] **Dependencies** resolved, or the issue labelled `blocked` with the blocker named.
- [ ] **No open human decision** (scope, cost, licence, art direction) left inside the task.
- [ ] `risk:high` issues name the **reviewer** required in §6.
An agent must not start work on a card that is still in Backlog; promoting it to Ready is the human's commit that
the task is specified. If a card turns out under-specified mid-work, stop and report rather than inventing scope.

Workflow: pick Ready issue → branch → agent does work → local tests → PR → `@reviewer` (different model family) +
human in rotation → CI green → squash merge → close issue → note in handoff.

## 8. Timeline (20 weeks) and who does what
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

## 9. Ownership map (merge-conflict avoidance)
| Path | Owner |
|---|---|
| `src/`, `tests/`, `tools/`(non-blender), `scripts/`, `.github/`, `opencode.json`, `docs/03,07,08,09,12` | P1 |
| `assets/**` (except audio/ui), `tools/blender/`, `docs/04,05` | P2 |
| `assets/audio/**`, `assets/ui/**`, `game/levels/`, `docs/02,06,13,14,15` | P3 |
| `game/*.blend` | one person at a time via `git lfs lock`; level `.blend` = P3, `main.blend`/`hud.blend` = P1/P3 coordinate in chat |
Cross-area edits: open an issue/PR and tag the owner.

## 10. Communication
One chat group (Discord/WhatsApp), GitHub issues for decisions, `docs/` for durable knowledge, handoff notes (R1). Decisions that change scope/cost go to the decision log in `03 §15`.

## 11. Definition of Done (team)
Acceptance met · tests/smoke evidence · docs updated · PR reviewed by `@reviewer` of a **different model family** than
the author and by the human in the §6 rotation · merged green · issue closed with a one-line outcome.

## 12. Wellbeing/workload guardrails
Cap ~10–15 h/week/person; no crunch weeks; if two consecutive weeks slip, re-plan (R3) instead of pushing harder.
