# 13 — QA & Performance Plan

## 1. Test pyramid
Unit (core logic, every PR) → static gates (lint/compile/JSON/secrets/LFS) → asset validation (naming/budgets) → **smoke** (`run_game.py --smoke`, per feature PR touching gameplay, and weekly on both tiers) → manual playtests (weekly) → soak (before beta/release: 60 min).

## 2. Hardware tiers
| Tier | Machine | Preset | Target |
|---|---|---|---|
| A | ASUS V16 | High, 1080p | ≥ 60 fps avg, 1% low ≥ 45 |
| B | Acer Aspire A515-45 (P1) | Low/Medium, 1080p (scale ≥ 75 %) | ≥ 30 fps avg, 1% low ≥ 24 (re-baseline after F-05) |
| C (optional) | any older laptop/iGPU | Low, 720p | ≥ 24 fps |
Budgets: see `04` §4 and `03` §7. Metrics recorded per milestone in `docs/reports/perf_<milestone>.md` with a table: scene, preset, resolution, fps avg/min/p5, RAM, VRAM, draw calls, tris.

## 3. Profiling method
In UPBGE: `bge.render.showFramerate(True)`, `showProfile(True)`, `showProperties(True)` (VERIFY in S-01); GPU/CPU stats via Blender statistics; OS tools (Task Manager/GPU-Z/MSI Afterburner/`nvidia-smi`). Always profile a **standalone build** (not the editor viewport) for final numbers. Method: reproduce → measure → change one thing → re-measure → record. Common suspects: shadows, 2D filters, transparent overdraw (water, foam, particles), many lights, skinned meshes, Python per-frame allocations, physics collider complexity.

## 4. Smoke test
`python tools/run_game.py game/<scene>.blend --smoke --seconds 20` ⇒ JSON `{fps_avg, fps_min, fps_p5, distance_moved_m, ok}`. Pass: `ok:true` and fps ≥ tier target. Add scenario variants for PH-01..PH-09.

## 5. Playtest protocol (weekly, P3 leads)
Script: 5-min brief → play chapter without help → observe silently (timestamps of confusion/fun/frustration) → 5 questions (GDD §16) → bug list. Record: completion time, sinks, collects, quits. Minimum 3 people per milestone; include one non-gamer.

## 6. Bug severity & process
S1 crash/data loss/blocker · S2 major feature broken/physics explosion · S3 minor/visual · S4 polish. Issue template: repro steps, expected/actual, build/commit, hardware tier, log/video, severity. Fix SLA: S1 immediately, S2 within the week, others scheduled. Every S1/S2 gets a **regression test** where feasible.

## 7. Regression checklist (run before each milestone tag)
Boot → menu → settings change persists → play Ch1 start to finish solo → 2P keyboard → pause/resume → sink & respawn → collect all fish → save/quit/reload → corrupt save recovery → quality preset switch mid-run → alt-tab → resolution change → gamepad hot-plug → 30-min run no memory growth > 200 MB.

## 8. Accessibility checklist
- [ ] Color-blind safe: never rely on red/green alone; icons + shapes
- [ ] Text ≥ 24 px at 1080p, scalable; high-contrast option
- [ ] Subtitles/visual cues for key audio cues (hit, checkpoint, hazard warning)
- [ ] Full remap, gamepad + keyboard, no hold-only actions without alternative toggle
- [ ] Assist modes available and persisted
- [ ] Camera shake and motion intensity sliders; no strobing > 3 Hz
- [ ] Volume sliders per bus

## 9. Compatibility
Windows 10/11 x64 required; test GPUs: Nvidia, AMD, Intel iGPU at least once before beta; Linux smoke on one machine if time allows. Display: 1080p, 1440p, 720p, windowed/fullscreen, 16:9 and 16:10 (ASUS V16 panel is 16:10-class — verify actual).

## 10. Milestone exit criteria
| Milestone | Exit |
|---|---|
| M1 | all risk:high spikes decided; smoke test runs on all 3 machines |
| M2 | Ch1 completable; 5 testers; fps tier targets met; no S1/S2 |
| M3 | Ch1–3; co-op 4 players 30 min; fps targets; ≤ 5 open S2 |
| M4 | all chapters; accessibility checklist; no open S1/S2 |
| M5 | release checklist GO |
