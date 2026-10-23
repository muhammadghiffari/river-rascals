# 10 — Phase Prompts (copy-paste ready)

How to use: open OpenCode in the repo root → pick the **Agent** → paste the **Prompt** → agent must end with the report format in `AGENTS.md`. Replace `<…>` placeholders. Prompts are English (agent-facing). Effort = reasoning effort from `09`.
Common footer appended to every prompt (already implied by AGENTS.md): *"Work on a branch, small commits, open a PR linking the issue, run tests, paste evidence, mark unverified bge calls as VERIFY, ask if blocked."*

Quick index: P0 Foundation · P1 Tech spikes · P2 Vertical slice · P3 Assets & animation · P4 Gameplay systems · P5 Audio/VFX/UI polish · P6 QA & performance · P7 Security & release · Recurring prompts.

---
## PHASE 0 — Foundation & governance (M0, week 1) — Owner P1
### P0.1 Repo bootstrap — `builder` · medium
```text
Follow docs/00_START_HERE_AGENT.md sections 1-4 exactly. Confirm owner/repo/visibility/teammate usernames with the human before running anything that creates or invites. Run bootstrap_github.py with --dry-run first, show me the commands, then run for real. After bootstrapping verify CI is green, LFS works, issues/milestones exist, and fix problems via PRs (never push to main once protection is on). Finish with the Day-1 report from section 7.
```
### P0.2 CI & quality gates hardening — `builder` · medium
```text
Issue F-02. Review .github/workflows/ci.yml, pyproject.toml and tests. Make CI fast (<3 min), add pip caching, add a job that runs `python tools/validate_assets.py --help` smoke (no Blender required), and a CODEOWNERS update using real usernames. Keep ruff rules as is unless they fail on existing code. Provide before/after run times and a link to the green run.
```
### P0.3 Docs reconcile — `architect` · high
```text
Read all docs/ and prompts/. List contradictions, missing decisions, and unrealistic assumptions (scope, timeline, hardware) as a table with severity. Propose fixes as a PR editing docs only (no code). Do not change product pillars. Flag anything that needs a human decision in an issue labelled `blocked`.
```

---
## PHASE 1 — Technical spikes (M1, weeks 2-3) — Owners P1 (engine/physics), P2 (assets/MCP), P3 (build/hardware)
### P1.1 S-01 Pin UPBGE version — `gameplay` · high (human runs on all three machines; agent writes the test scenes + report)
```text
Goal: decide between UPBGE 0.50 (Blender 5.0.1 base) and 0.44.x as the single pinned engine version. Create game/spike_engine.blend-generation script (tools/blender/gen_spike_engine.py) that builds a scene with: a dynamic box on a plane, a Python Component loaded via game/rr_components.py, an aud audio test (play one OGG, adjust volume, 3D location), logic/physics tic rate set to 60, a 2D-filter toggle, and printing of fps via bge.logic.getAverageFrameRate().
Write docs/reports/S-01_engine_decision.md with a test matrix (feature x version x machine), results pasted by humans, known bugs, and a recommendation with rationale. Resolve every VERIFY in src/rr/glue that relates to component loading, tic rates, aud, playAction signature, overlay scenes. Do not change the pinned version without human approval.
Acceptance: matrix complete for both candidate versions on Tier A and Tier B machines; decision + URL + SHA256 recorded in docs/03 §2.
```
### P1.2 S-02 Raft buoyancy — `gameplay` · high
```text
Goal: make the raft float stably in UPBGE using rr.core.buoyancy and rr.core.waves via src/rr/glue/raft.py (RaftPhysics).
1) Generate a test scene with tools/blender/gen_raft_blockout.py (fix it if needed) plus a water plane and RiverRoot empty with water_level.
2) Validate bge semantics: applyForce/applyTorque accumulation per physics step, getVelocity(point), worldOrientation use. Write a tiny experiment script that logs numbers and put the findings in docs/07 §8 (update rule 3).
3) Tune stiffness/damping/F_max to reach PH-01 and PH-02 acceptance (docs/07 §9). Keep tunables in game/settings/physics.json loaded at start.
4) Add scripted smoke checks for PH-01..PH-03. Do not edit rr.core without updating tests.
Deliver: PR with evidence (numbers: draft, bob amplitude, drift), updated spec, resolved VERIFY items. If physics is unstable after two tuning rounds, stop and escalate to @debugger with logs.
```
### P1.3 S-03 Oars + river flow + smoke test — `gameplay` · high
```text
Goal: complete the loop: RiverLoader builds the River from RiverPt.* empties, RaftOars drives thrust/torque, SmokeTest runs autopaddle and writes smoke_result.json, tools/run_game.py returns exit code 0 on success.
Build a 120 m test river scene (curved, widths 8-12 m) via a bpy generator. Verify PH-03/PH-04 numbers. Report fps from the smoke test on this machine. Add unit tests for any new pure logic (e.g., bank push-back). Update docs if a spec value changes.
```
### P1.4 S-04/S-05 Blender MCP + asset scripts — `techart` · medium (P2's machine)
```text
Follow docs/08 §8. Then run tools/blender/gen_raft_blockout.py and tools/validate_assets.py against the real Blender/UPBGE build, fix both scripts until RF_RaftT1.blend generates and validates, and test appending it into a UPBGE scene. Report: Blender/UPBGE versions, whether the MCP addon works inside UPBGE (yes/no + errors), fallback decision (author in vanilla Blender?), and fixes made. Update docs/04 §6 if the portable-assets rule needs changes.
```
### P1.5 S-06 Standalone build — `builder` · medium (P3's machine with the agent)
```text
Goal: produce a runnable standalone build of the spike scene and run it on this (mid-spec) laptop from a clean folder. Try (a) blenderplayer-based packaging, (b) UPBGE game publishing add-on if available. Document exact steps, folder structure, file size, and failures in docs/15 §Build. Add tools/package_build.py that automates the successful method (zip to builds/, git-ignored). Record fps with run_game.py --smoke.
```
### P1.6 S-07 Water shader — `techart` · medium; escalate to `gameplay` high if math mismatch
```text
Create MT_Water: 3 summed waves in the shader exactly mirroring rr.core.waves.DEFAULT_WAVES (amplitude, wavelength, speed, direction), depth tint, foam near edges, optional flow scrolling. Expose presets Low/Med/High. Provide a test that samples the shader-equivalent function in Python at 20 points and compares with wave_height (tolerance 3 cm). Measure fps cost per preset on Tier A and Tier B. Report numbers.
```
### P1.7 Model benchmark (docs/09 §6) — `qa` · low (orchestrates), runs tasks via each model
```text
Prepare benchmark tasks T1-T6 as branches from the same commit with acceptance tests where possible, a results table template in docs/reports/model_benchmark.md and a script that records time-to-green. Do not run paid models without the human's go-ahead; list estimated cost first.
```

---
## PHASE 2 — Vertical slice (M2, weeks 4-7)
### P2.1 V-01/V-02 River + raft tuning — `gameplay` · high
```text
Productionise the river system and tune the raft per docs/07. Implement bank push-back and off-river recovery as pure functions in rr.core (unit-tested), integrate in glue, add physics.json tunables, scripted tests PH-01..PH-08 as smoke scenarios with pass/fail output. Report numbers vs acceptance table. Escalate to @debugger with logs after two failed tuning rounds.
```
### P2.2 V-03 Camera — `gameplay` · medium
```text
Implement ChaseCamera (component): follows raft with smoothing, look-ahead along river tangent, speed-based pull-back, bank avoidance via ray casts, impact shake (damped noise, scalable by settings). Pure math (smoothing, damping, look-ahead) in rr/core/camera_math.py with tests. Provide a debug toggle for free camera.
```
### P2.3 V-04 Input and players — `gameplay` · high
```text
Design and implement the input abstraction: devices (keyboard sets, up to 4 gamepads) -> PlayerSlots (join/leave) -> oar assignment (solo = both oars, co-op = one oar each, AI fills empty). Pure logic in rr/core/input_map.py (bindings, dead zones, slot assignment) with thorough unit tests. Glue reads bge inputs. Handle gamepad hot-plug without crashing. Use findings from spike S-08.
```
### P2.4 V-05/V-06 Hazards — `gameplay` · high
```text
Implement rock damage, hull integrity, floating logs, current boosters per docs/07 §7. Core: damage curve, invulnerability timer, hull state machine (hearts, repair, sink) in rr/core/hull.py with tests. Glue: collision sensors -> events on the EventBus (hull_damaged, raft_sunk). Hook audio/VFX through events only (no direct calls). Provide a hazard test strip scene.
```
### P2.5 V-07/V-08 Collectibles, checkpoints, save — `gameplay` · medium
```text
Implement coins and golden fish (pooled, sensor-based), checkpoint arches with repair, respawn flow, and save/load via rr.core.save (extend SaveData if needed with migration + tests). Settings persist. Verify save survives restart and a corrupted file.
```
### P2.6 V-09 HUD/menus/presets — `gameplay` · medium
```text
Build the overlay HUD scene and menus per docs/02 §11: hearts, coins, fish, progress bar, join prompts, pause menu, settings (audio buses, language placeholder, quality presets from docs/03 §7, assist toggles). All navigable by gamepad and keyboard. Presets must change render scale/shadows/filters/particles at runtime (VERIFY which are changeable). Provide screenshots in the PR.
```
### P2.7 V-10 Chapter 1 blockout — `architect` · high (design) then `builder` · medium (generation scripts)
```text
Design Chapter 1 "Sleepy Creek": 4-minute river with beat sheet (docs/02 §15 tutorial beats), centreline coordinates, width profile, hazard/collectible placements, checkpoint positions, camera moments. Output: docs/levels/ch01.md + a machine-readable JSON (game/levels/ch01.json). Then write tools/blender/gen_level_from_json.py to build the blockout scene (river points, banks as simple meshes, placeholders) so levels are reproducible. Provide a top-down diagram (SVG or ASCII) in the doc.
```
### P2.8 V-15 Vertical-slice playtest — `qa` · low + human P3
```text
Prepare the playtest kit: docs/reports/vs_playtest_template.md (questions from docs/02 §16, timing, bug capture), run smoke tests on both machines, compile fps/1% low numbers, and draft the Go/No-Go summary for M3 with evidence. Do not decide Go/No-Go; present data.
```

---
## PHASE 3 — Assets & animation (starts in M1, peaks M2–M3) — Owner P2 (+agent `techart`)
Use the **MASTER PREAMBLE** and per-asset prompts in `prompts/asset_prompts_blender.md` (83 assets) and the animation prompts in `docs/05 §7`.
### P3.1 Art kickoff — `architect` · high (human P2 decides)
```text
Using docs/04 art direction, propose 3 distinct stylistic directions for River Rascals (palette, shape language, shading) as a short brief each with reference descriptions (no copyrighted references by name beyond generic genres) and trade-offs for performance on a mid-spec laptop. Recommend one. Then specify the shared palette texture layout (grid of cells with hex values) so assets can UV into it. Output docs/art/art_kickoff.md; P2 chooses.
```
### P3.2 Palette + MT_ToonBase — `techart` · medium
```text
Generate assets/materials/palette.png (e.g. 16x16 cells, 16x16 px each) from the hex list in docs/04 via a Python script (tools/make_palette.py, Pillow if available else pure-PNG writer), and build MT_ToonBase (2-band toon shading, palette lookup by UV). Provide a test scene with a sphere per palette cell. Report fps cost of 200 instances.
```
### P3.3 Asset batches — `techart` · medium (one prompt per row of ASSET_LIST.csv)
Batch order: **B1** raft/oars/seat → **B2** otter + rig + P0 anims → **B3** props P0 → **B4** env kit v1 → **B5** VFX sprites → **B6** NPCs/props P1–P2 → **B7** chapter kits (cliffs/canyon/night/storm) → **B8** UI art.
```text
Batch <B#>: create the assets listed below in order. For each asset paste-run the matching prompt from prompts/asset_prompts_blender.md (including OUTPUT CONTRACT). After each asset: validate (tools/validate_assets.py), save, commit on branch art/<asset-id>. Stop after 3 assets and wait for human review before continuing. Assets: <IDs>.
```
### P3.4 Asset review — `reviewer` · high
```text
Review PR <n> (assets). Use docs/04 §9 checklist. Run or request validator output, inspect names, tris, materials, UV usage of the palette, collision/sockets, rig deformation notes, provenance row. Return APPROVE/CHANGES REQUESTED with a table. Note anything that needs human visual judgement.
```

---
## PHASE 4 — Gameplay systems & world (M3, weeks 8–13)
### P4.1 Whirlpool + waterfall — `gameplay` · high (waterfall: escalate to `architect` for the state-machine design first)
```text
Implement whirlpool (docs/07 §7 law) as a pure force function with tests plus a glue HazardWhirlpool component with debug gizmo. For the waterfall drop implement a scripted sequence state machine (APPROACH -> LOCK_PATH -> DROP -> SPLASH -> RESTORE) in rr/core/waterfall.py with tests; glue handles kinematic path and restore with velocity clamp. Provide a 50-run automated test scenario (PH-09) with pass/fail summary.
```
### P4.2 AI crew paddlers — `gameplay` · high
```text
Implement CrewAI: given river sample (lateral offset, heading error, upcoming hazard flags) output oar presses and direction each tick. Policy: PD controller on heading to preferred line, 60 % efficiency, rhythmic strokes, random comedic mistakes with probability p (configurable), never both oars back-paddling. Pure code in rr/core/crew_ai.py with property-style tests (never NaN, bounded, converges to centreline in a straight channel simulation). Provide a headless simulation harness `tools/sim_raft.py` using core physics approximations to run 1000 trials.
```
### P4.3 Local co-op — `gameplay` · high; review by `architect` (risk:high)
```text
Implement 2-4 player local co-op: join/leave mid-run, seat assignment (left/right balance), oar ownership, AI fill/hand-back, per-player HUD pip, rescue interaction (rope). Extend input_map tests for join/leave sequences (fuzz at least 1000 random event sequences: no exceptions, always valid assignment). Manual test script for 4 gamepads in the PR.
```
### P4.4 Progression & workshop — `gameplay` · medium
```text
Implement coins economy, raft tiers T1-T3 and cosmetics unlocks per docs/02 §4 and §9: data in game/settings/progression.json, pure logic in rr/core/progression.py (purchase validation, unlock rules) with tests, Workshop UI per docs/02 §11, save migration to SaveData v3 with tests (old saves load).
```
### P4.5 Level production — `architect` · high (design) + `builder` · medium (generators)
```text
Design chapter <N> per docs/02 §6 with beat sheet, centreline JSON, hazard/collectible/checkpoint placement, pacing curve (intensity per 10 s), camera moments. Output docs/levels/chN.md + game/levels/chN.json. Check feasibility: length, flow speed and expected completion time via tools/sim_raft.py. Flag risks for Tier B performance (set dressing density).
```
### P4.6 Tutorial — `gameplay` · medium
```text
Implement the tutorial per docs/02 §15 as a data-driven step list (rr/core/tutorial.py state machine with tests): triggers, prompts (localised keys), completion conditions, skip option. Glue shows prompts via HUD. Provide a checklist for 3-tester validation.
```

---
## PHASE 5 — Rendering, audio, VFX, UI, cinematic (M3–M4)
### P5.1 Audio system — see `docs/06 §10` — `gameplay` · high
### P5.2 Audio sourcing & integration — human P3 sources; agent integrates — `qa` · low / `builder` · medium
```text
Integrate audio files found in assets/audio/** according to AUDIO_LIST.csv: verify file names/IDs, formats (OGG, mono/stereo), durations, loudness (script tools/check_audio.py using Python's wave/ogg libs if available, otherwise report manual steps), missing items by priority, and generate a table of gaps. Hook P0 events -> sounds via a data file game/settings/audio_events.json (event name -> sound ids, volume, pitch jitter).
```
### P5.3 VFX system — `techart` · medium (assets/shaders) + `gameplay` · medium (spawner)
```text
Implement a pooled VFX spawner driven by EventBus events (splash, wake, foam, sparkle, impact, confetti) using UPBGE 0.50 fast AddObject (dupli-base) if S-01 confirmed it works, else classic AddObject with pooling. Particle budgets per docs/03 §7 presets. Measure fps with VFX stress scene on both tiers.
```
### P5.4 Water & lighting polish — `techart` · medium; escalate `gameplay` high for shader math
```text
Improve MT_Water: foam at rocks/banks via distance mask (baked vertex colour or UV), subtle depth tint, flow-direction scrolling matched to River flow speed; keep wave math in sync with rr.core.waves. Add three lighting presets (day, dusk, night) with fog colour. Verify Low preset >= 30 fps on Tier B in chapter 1.
```
### P5.5 Cinematic intro & credits — `techart` · medium + human P2
```text
Build a 30-45 s in-engine intro cinematic using scripted camera paths (keyframed actions) and existing assets, skippable, with music hook. Provide a storyboard in docs/art/intro_storyboard.md first (6-8 shots), wait for human approval, then implement. Ensure fps stays stable on Tier B.
```
### P5.6 Localization — `docs` · low + `builder` · medium
```text
Extract all UI strings into game/locale/en.json and id.json with keys; implement rr/core/i18n.py (lookup with fallback to English, tests), runtime switching, font coverage check. Provide missing-key report tool.
```

---
## PHASE 6 — QA, performance, compatibility (M4)
### P6.1 Daily QA triage — `qa` · low
```text
Run: unit tests, ruff, asset validation, smoke test on this machine. Summarise results in a table (pass/fail, numbers: fps avg/min/p5, distance). For each failure: classify (test/product/env), minimal repro, proposed owner and label, and open/update issues. Do not fix; produce triage.
```
### P6.2 Performance pass — `gameplay` · high (+ human profiling data)
```text
Input: profiler screenshots/logs from Tier B (bge.render.showProfile / showFramerate, Blender GPU stats). Identify the top 3 costs, propose fixes ranked by gain/risk (LODs, pooling, fast AddObject, shadow budget, filter cost, draw-call merging, texture sizes), implement the top one, and re-measure. Never optimise without before/after numbers. Update docs/13 budgets with measured reality.
```
### P6.3 Hard bug — `debugger` · high
```text
Bug: <title/link>. Repro steps: <steps>. Evidence: <logs/video>. Follow the debugging method in your system prompt (>= 3 hypotheses, test each with evidence). Deliver the root cause, minimal fix, regression test (core-level if possible), and prevention note. Do not widen scope.
```
### P6.4 Accessibility audit — `reviewer` · high
```text
Audit against docs/13 accessibility checklist (colour-blind safety, text size, subtitles for audio cues, remap, assist modes, motion/shake options, flashing). List violations with screenshots/locations and fixes ranked by effort.
```

---
## PHASE 7 — Security, build & release (M5)
### P7.1 Security & licence audit — `security` · high (2nd opinion `Greg/claude-opus-5-5` high)
```text
Audit the repo: secrets (git history too), CI permissions, dependencies, MCP configuration (Blender socket, remote servers, token scopes), asset licences vs assets/PROVENANCE.csv (every asset file must have a row; flag AI-generated assets lacking a terms note), fonts (OFL), save-file parsing robustness, build contents (no dev files or tokens in the zip). Output a findings table with severity, evidence, fix; block release on critical/high.
```
### P7.2 Release readiness — `release` · high
```text
Run docs/15_RELEASE_CHECKLIST.md end-to-end. For each item give status + evidence link/number. Produce GO/NO-GO. For GO, output exact commands: version bump, CHANGELOG update, tag, build via tools/package_build.py, checksum, upload steps. Do not tag or upload without explicit human confirmation.
```
### P7.3 Release notes — `docs` · low
```text
Write release notes for vX.Y.Z from merged PRs/issues since the last tag (gh CLI), grouped: New, Improved, Fixed, Known issues. Friendly tone, no jargon, max 400 words. Update CHANGELOG.md.
```

---
## RECURRING PROMPTS
### R1 Daily handoff (any agent, end of session)
```text
Write a 10-line handoff note: what changed (PR links), what is in progress (branch), decisions made, open questions, next 3 steps, anything that blocks others. Post as a comment on the main issue.
```
### R2 PR review — `reviewer` · high
```text
Review PR <n> against issue <m>. Follow your system prompt. Check core/glue layering, tests, tick-rate assumptions, per-frame allocations, unverified bge calls, budgets, naming. Return verdict + blocking list + suggestions + what you could not verify.
```
### R3 Weekly planning — `architect` · medium
```text
Look at open issues, milestone burndown and last week's reports. Propose next week's plan for P1/P2/P3 (max 3 items each, with agent/effort), identify risks and cut candidates, and update the project board labels. Keep within the milestone date; if it slips, propose what to cut first (stretch, then polish, never core feel).
```
### R4 Physics tuning session — `gameplay` · high (human at the keyboard)
```text
We are tuning "feel". I'll describe what I experience; you propose ONE change at a time to values in physics.json with the expected effect and a rollback value, record each change and the observation in docs/reports/tuning_log.md, and stop after 5 iterations to summarise. Never change code during tuning unless a bug is found.
```
### R5 Spike report writer — `docs` · low
```text
Turn the raw notes/logs I paste into a concise spike report: question, method, results (table), decision, consequences, follow-ups. Do not invent numbers; mark missing data TBD.
```
### R6 Issue breakdown — `architect` · high
```text
Break epic <title> into agent-ready issues (<= 1 day each): goal, context links, acceptance criteria, out-of-scope, suggested agent/effort, test plan. Output as JSON compatible with backlog/backlog.json so scripts/create_issues.py can import it.
```
