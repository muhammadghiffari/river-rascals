# 13 — QA & Performance Plan

## 1. Test pyramid
Unit (core logic, every PR) → static gates (lint/compile/JSON/secrets/LFS) → asset validation (naming/budgets) → **smoke** (`run_game.py --smoke`, per feature PR touching gameplay, and weekly on both tiers) → manual playtests (weekly) → soak (before beta/release: 60 min).

## 2. Hardware tiers
| Tier | Machine | Preset | Target |
|---|---|---|---|
| A | ASUS V16 | High, 1080p | ≥ 60 fps avg, 1% low ≥ 45 |
| B | mid-spec laptop | Low/Medium, 1080p (scale ≥ 75 %) | ≥ 30 fps avg, 1% low ≥ 24 (re-baseline after F-05) |
| C (optional) | any older laptop/iGPU | Low, 720p | ≥ 24 fps |
Budgets: see `04` §4 and `03` §7. Metrics recorded per milestone in `docs/reports/perf_<milestone>.md` with a table: scene, preset, resolution, fps avg/min/p5, RAM, VRAM, draw calls, tris.

## 3. Profiling method
In UPBGE: `bge.render.showFramerate(True)`, `showProfile(True)`, `showProperties(True)` (VERIFY in S-01); GPU/CPU stats via Blender statistics; OS tools (Task Manager/GPU-Z/MSI Afterburner/`nvidia-smi`). Always profile a **standalone build** (not the editor viewport) for final numbers. Method: reproduce → measure → change one thing → re-measure → record. Common suspects: shadows, 2D filters, transparent overdraw (water, foam, particles), many lights, skinned meshes, Python per-frame allocations, physics collider complexity.

## 4. Smoke test
`python tools/run_game.py game/<scene>.blend --smoke --seconds 20` ⇒ JSON
`{seconds, warmup_s, fps_avg, fps_min, p1_low_fps, frame_time_ms {p50, p95, p99, max}, stutter_count, frames_measured, measured_s, fps_crosscheck {samples, post_warmup_samples, min_fps, median_fps, mean_post_warmup_fps, max_fps}, expect_movement, distance_moved_m, moved_ok, ok}`.
Frame-time stats come from per-frame `perf_counter` deltas summarized by `rr.core.benchstats` after discarding `warmup_s` of cumulative frame time (configure via `RR_SMOKE_WARMUP`, default 3 s); `fps_crosscheck` is only an additive cross-check of per-second `getAverageFrameRate()` samples (median + post-warmup mean; sample count and `max_fps` stay visible so one outlier cannot hide in the mean). `ok` = performance gate (frames measured) AND, when `expect_movement` is true, `moved_ok` (distance > 1 m). Static scenes set `RR_SMOKE_EXPECT_MOVEMENT=0` and pass on performance alone. The old `fps_p5` key is gone; use `frame_time_ms.p95` and `p1_low_fps`.
Pass: `ok:true` and fps ≥ tier target. Add scenario variants for PH-01..PH-09.

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
