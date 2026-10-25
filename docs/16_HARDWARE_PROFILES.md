# 16 — Hardware Profiles & Machine Status
Authors did **not** have the exact specs; each owner fills their row in week 1 (F-04/F-05).

Tiers are defined in `13_QA_PERFORMANCE_PLAN.md` §2. **P3 is Tier C** (Linux floor-spec, iGPU, 720p/native);
the Tier B 1080p baseline belongs to the separate Acer Aspire machine and Tier A to the ASUS V16.

| Field | P1 Aspire A515-45, Windows (Tier B) | P2 ASUS V16, Windows (Tier A) | P3 — HP ZBook 14 G2 (Tier C, Linux floor-spec) |
|---|---|---|---|
| Model | | ASUS V16 (exact model: ) | HP ZBook 14 G2 (product A3009D410303, board 2216, notebook) |
| OS / version | | | Ubuntu 26.04.1 LTS, x86_64 (kernel 7.0.0-38-generic, Mesa 26.0.8 for the active iGPU; glxinfo reports Mesa 26.0.8) |
| CPU | | | Intel Core i7-5600U, 2 cores / 4 threads |
| GPU (dedicated/iGPU) + driver | | | iGPU Intel HD Graphics 5500 (i915) + dGPU AMD Radeon R7 M260X (amdgpu). **UPBGE renders on the Intel iGPU** (measured, see notes) |
| VRAM / shared | | | dGPU 1 GiB dedicated (`mem_info_vram_total` = 1,073,741,824 B); iGPU uses shared system RAM — `glxinfo -B` reports "Video memory: 14879 MB, Unified memory: yes", which is **shared system RAM, not dedicated VRAM** (the i915 driver exposes no dedicated-VRAM figure) |
| RAM | | | 14.5 GiB (MemTotal 15,236,760 kB; documented as "14 GiB") |
| Storage free (SSD/HDD) | | | 38.6 GiB free of 56.1 GiB on `/` (`/dev/sdb1`, reported rotational by the kernel) |
| Display res/refresh | | | 1366×768 @ 59.80 Hz, internal eDP-1 (no external display attached) |
| Power mode used for tests | plugged-in, high performance (always record) | | **plugged in (AC online), platform profile `balanced`, governor `schedutil`** — the profile was *not* switched to `performance` for the F-05 runs; see the limitation note below |

## P3 (F-05) notes — Tier C, updated 2026-10-24
- **Classification.** i7-5600U (2C/4T, 15 W Broadwell-U), Intel HD Graphics 5500 iGPU, 1366×768 panel: below the
  Tier B definition (1080p target), so P3 is scored against the **optional Tier C target in `13` §2** — Low, 720p,
  ≥ 24 fps. The Tier B 1080p baseline belongs to the Acer Aspire machine and Tier A to the ASUS V16; no 1080p run was
  attempted on this laptop.
- **Engine used (observed, not yet a project pin).** UPBGE 0.50, self-reported `Blender 5.0.1`, built 2026-01-03, from
  `$UPBGE_PATH` = `/home/hicesse/portable_apps/upbge-0.50-linux-x64`. Installer archive
  `~/Downloads/upbge-0.50-linux-x64.tar.xz`, SHA-256 `21d535641cbab1751766737cd9958bae120cd161cf7f0c86f5d5df6dca868314`.
  This is an environment fact only — the pin stays pending with S-01 (`03` §2).
- **Renderer, measured not inferred.** The player's own output is authoritative:
  `GL_VENDOR: Intel`, `GL_RENDERER: Mesa Intel(R) HD Graphics 5500 (BDW GT2)`, `GL_VERSION: 4.6 (Core Profile) Mesa 26.0.8-1ubuntu0.3`;
  in-engine `bge.logic.getGraphicsCardVendor()` returns `Intel`. The Radeon is installed but unused in this configuration
  (`DRI_PRIME` unset).
  `glxinfo -B` (GLX/XWayland) also names the Intel iGPU while `eglinfo` names the AMD `radeonsi` device as the EGL default,
  and neither tool says what the engine used — only the player's `GL_RENDERER` does. Same trap with subsystem ids: the board
  reports `2216` (the Intel device's PCI subsystem is `103C:2216`) while the AMD device's subsystem is `103C:2259`; Mesa calls
  the AMD part `Radeon R7 M260 Series (radeonsi, oland)` where `lspci` says `Opal PRO [Radeon R7 M260X]` (both `1002:6605`).
- **Resolution: windowed is clamped, fullscreen is exact.** Measured on this Wayland compositor:
  a windowed request for 1280×720 produced **1280×699**, a windowed 1366×768 produced **1299×699**, and a 1920×1080 request
  produced 1299×699. Launching the player fullscreen (`-f <w> <h> 32 60`) produced the **exact** requested surface
  (1280×720 and 1366×768, both verified from `bge.render.getWindowWidth/Height`). `tools/bench/run_baseline.py` therefore
  defaults to fullscreen; every result records requested **and** actual size plus a `resolution_verified` flag.
- **Frame-rate cap is on.** The generated scenes pin `use_frame_rate = True` and `vsync = "ON"` (an enum on UPBGE 0.50, not a bool),
  so the as-shipped numbers sit at the 59.80 Hz panel rate. A result equal to the panel rate means **"at cap", not headroom** —
  60.0 fps does not mean the machine could go faster. Passing the player's `-g fixedtime` ("Enable all frames") was tested and
  does **not** lift the cap on this build (measured: 60.0 fps with the flag). To measure headroom, the generator authors a second
  scene set with `use_frame_rate = False` / `vsync = OFF` (`--uncapped`, file suffix `_uncapped`).
- **Python Components cannot be created under `blender -b` on this build** (SIGSEGV). Components are therefore attached from the
  normal GUI executable with the work deferred to a timer and `bpy.ops.logic.python_component_create(component_name=...)` under
  `bpy.context.temp_override(...)`; `bge_netlogic` is disabled for generator runs. This is recorded as **R-18** in `14`. Reading
  components in `-b` is safe. The generator also supports `--template game/bench/bench_template.blend` (a GUI-saved scene that
  already carries the component) as a fallback.
- **The generated `.blend` files are build artefacts, not sources.** `game/bench/*.blend` is git-ignored on purpose
  (LFS quota, R-06); regenerate with
  `"$UPBGE_PATH/blender" --python tools/bench/make_baseline_scenes.py` (add `-- --uncapped` for the headroom set).
  Tracked inputs are the generator, the component, and the manifests `game/bench/scenes.json` / `scenes_uncapped.json`.
- **Limitations of this profile run.** (a) The runs used the `balanced` platform profile (plugged in), not `performance`, so they
  are not the fastest this machine can do; (b) package temperature was around 71 °C at run time and was not logged per run;
  (c) no 5-minute soak was run; only 60 s measured windows; (d) draw-call counts were not captured.

## Tier C baseline results — P3, 2026-10-24
Method: `BenchRecorder` (`src/rr/glue/bench.py`) samples `time.perf_counter()` deltas per frame; 3 s warmup discarded on
cumulative frame time, then a 60 s measured window. Metrics per `src/rr/core/benchstats.py`: `fps_avg` = frames ÷ measured
time, `fps_min` = 1 ÷ longest frame, `1% low` = 1 ÷ p99 frame time, percentiles linearly interpolated (type-7),
`stutter` = frames strictly longer than 2× the median frame. Resolution is read from the engine, never assumed.

Command (exact flags):
```
python tools/bench/run_baseline.py --res 1280x720 --res 1366x768 --preset low \
    --seconds 60 --warmup 3 --machine p3_zbook14g2
# per run: blenderplayer -f <w> <h> 32 60 game/bench/<scene>.blend
```

### As shipped (vsync + frame-rate cap ON)
| Scene | Tris | Requested | Actual (verified) | fps avg | 1% low | fps min | p50 ms | p99 ms | max ms | Stutters | Frames |
|---|---|---|---|---|---|---|---|---|---|---|---|
| empty | 0 | 1280x720 | 1280x720 (yes) | 59.7 | 57.1 | 27.6 | 16.7 | 17.5 | 36.2 | 3 | 3539 |
| empty | 0 | 1366x768 | 1366x768 (yes) | 59.6 | 55.2 | 19.8 | 16.7 | 18.1 | 50.5 | 6 | 3536 |
| 100k | 100,352 | 1280x720 | 1280x720 (yes) | 59.7 | 57.7 | 20.6 | 16.7 | 17.3 | 48.5 | 4 | 3541 |
| 100k | 100,352 | 1366x768 | 1366x768 (yes) | 59.9 | 59.4 | 21.5 | 16.7 | 16.8 | 46.6 | 2 | 3550 |
| 250k | 250,632 | 1280x720 | 1280x720 (yes) | 59.9 | 59.7 | 18.2 | 16.7 | 16.7 | 55.0 | 3 | 3553 |
| 250k | 250,632 | 1366x768 | 1366x768 (yes) | 59.9 | 59.8 | 20.1 | 16.7 | 16.7 | 49.6 | 2 | 3555 |
| 250k — optional dGPU run (Radeon R7 M260X, `DRI_PRIME=1`; **not** the Tier C baseline) | 250,632 | 1280x720 | 1280x720 (yes) | 59.8 | 58.6 | 23.8 | 16.7 | 17.1 | 42.1 | 3 | 3331 |

All six runs sit at the panel rate (~59.8 Hz): the optional Tier C target (≥ 24 fps avg, Low, 720p) is met, but these
numbers separate **"nothing is wrong"** from **"how much room is left"** only poorly. The low `fps_min` values (18–28 fps) are a
single long frame each (max 36–55 ms, i.e. one hitch during the 60 s window), not a sustained drop — visible as `stutter_count`
2–6 while the 1% low stays 55–60 fps.

### Headroom (`--uncapped` scene set: `use_frame_rate = False`, `vsync = OFF`)
| Scene | Tris | Requested | Actual (verified) | fps avg | 1% low | fps min | p50 ms | p99 ms | max ms | Stutters | Frames |
|---|---|---|---|---|---|---|---|---|---|---|---|
| empty | 0 | 1280x720 | 1280x720 (yes) | 168.1 | 133.5 | 56.9 | 5.8 | 7.5 | 17.6 | 7 | 9973 |
| empty | 0 | 1366x768 | 1366x768 (yes) | 141.7 | 87.2 | 20.2 | 6.8 | 11.5 | 49.5 | 35 | 8407 |
| 100k | 100,352 | 1280x720 | 1280x720 (yes) | 161.6 | 117.6 | 37.9 | 6.0 | 8.5 | 26.4 | 9 | 9579 |
| 100k | 100,352 | 1366x768 | 1366x768 (yes) | 141.5 | 101.3 | 30.8 | 6.8 | 9.9 | 32.4 | 14 | 8385 |
| 250k | 250,632 | 1280x720 | 1280x720 (yes) | 160.3 | 115.0 | 38.3 | 6.0 | 8.7 | 26.1 | 12 | 9481 |
| 250k | 250,632 | 1366x768 | 1366x768 (yes) | 140.5 | 105.0 | 42.8 | 6.9 | 9.5 | 23.4 | 7 | 8329 |

Reading: at 720p the empty scene reaches 168.1 fps and the 250k-triangle + shadow scene 160.3 fps (1% low 115–134 fps), i.e.
about 2.8× the panel cap, so the cap — not the GPU — is what limits the as-shipped numbers. At native 1366×768 average fps drops to
140.5–141.7 (1% low 87–105 fps): the 1366×768 surface has ~14 % more pixels than 720p and the frame cost rises ~16–18 %. The 100k
and 250k scenes are nearly indistinguishable from empty on this GPU (168.1 → 161.6 → 160.3 fps at 720p), which is expected for a
static, single-material grid lit by one sun: fill rate dominates over triangle count at these sizes, and the 250k scene's
shadow-casting sun costs almost nothing attributable here. Any content that meaningfully loads the iGPU will need the real game
scene (S-07 water, props) rather than these probes.

Result files (all with `"ok": true`, `resolution_verified: true`, `gpu_renderer` = the Intel iGPU above):
`docs/reports/bench/p3_zbook14g2_{empty,100k,250k}_{1280x720,1366x768}.json` (capped) and
`docs/reports/bench/p3_zbook14g2_uncapped_{...}.json` (headroom). Player logs are under `docs/reports/bench/logs/`.

## Baseline scenes (still to record: Tier A + the Tier B 1080p rows)
These rows are the **Tier B (P1 Aspire)** and Tier A baselines, and will be measured on the P1 Aspire, 1920x1080 verified; P3 (Tier C) is measured above and never runs 1080p.
| Scene | Preset | Res | fps avg | fps min | notes |
|---|---|---|---|---|---|
| Empty scene | Low | 1080p | | | |
| 100k tris static | Low | 1080p | | | |
| 250k tris + 1 sun shadow | Low/Med | 1080p | | | |
| Raft + water + 20 props (S-07) | Low/Med/High | 1080p | | | |

**Status:** Tier C (P3) baseline is complete for the three synthetic scenes at 1280×720 and 1366×768, capped and uncapped.
The 1080p rows above remain empty for Tier B — an empty cell is **not** a pass. Metric definitions to record with each number:
actual window size, tri count, vsync/`use_frame_rate` cap state, and frame-time-based min/1% low (per-second
`getAverageFrameRate()` sampling cannot produce a 1% low — see issue #66).

## Interpretation rules
- Tier B: if average < 30 fps on the 250k-tri scene at Low ⇒ reduce scene budgets in `04` §4 and set 720p/75 % default for Low.
- Tier C (P3): optional target is ≥ 24 fps avg at 720p on Low (`13` §2). Currently met with large margin while capped; use the
  uncapped table to judge regressions, since the capped numbers cannot fall until the machine drops below ~59 fps.
- Laptops throttle: test plugged in, record temps if possible, run ≥ 5 minutes (not done yet for P3; 60 s windows only).

## MCP status (P2 fills)
| Item | Value |
|---|---|
| Blender/UPBGE version | |
| MCP package + version | |
| Addon works in UPBGE? | |
| Fallback used? | |
| Issues/workarounds | |
