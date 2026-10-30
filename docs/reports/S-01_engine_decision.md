# S-01 — Engine decision: UPBGE 0.50 (Blender 5.0.1) vs 0.44.x

**Status: OPEN — matrix INCOMPLETE (no runs recorded).** The pin in
`docs/03_TECH_ARCHITECTURE.md` §2 is **unchanged** (`____`); a human owner approves the final
version. This file is scored by humans pasting the output of one probe component, so it stays cheap
to run on three machines.

Scope of the spike (docs/10 P1.1): Python Components, `aud`, `blenderplayer` launch, tic rates and
physics at 60 Hz on both candidate versions. Not in scope: asset export, publishing add-on (S-06),
rendering quality presets (docs/03 §7 is unchanged by this spike).

---

## 1. Artefacts in this PR

| Item | Path | What it does |
|---|---|---|
| Scene generator | `tools/blender/gen_spike_engine.py` | Builds the probe scene (dynamic box on a plane, animated cube, camera, overlay HUD camera + collection, `SpikeProbe` component) and saves `game/spike_engine.blend`. |
| Probe component | `src/rr/glue/spike_probe.py` | One check per feature, writes `spike_*.json`, prints a ready-made matrix row. |
| Grading helpers | `src/rr/core/spike.py` + `tests/test_spike.py` | Pure pass/fail/skip grading and markdown row formatting (unit-tested). |
| Test tone | `assets/audio/sfx/SFX_ToneTest_01.ogg` | Own-made 440 Hz, 1.0 s mono Vorbis; provenance row `AUD_SPIKE_TONE_01`. |
| Launcher | `tools/run_game.py` | Exports `game/` and `src/` on `PYTHONPATH` (best effort — Blender may ignore it without `--python-use-system-env`, hence VERIFY; the generator also puts `game/` on `sys.path` for registration). |

The `.blend` is **not committed by this PR**: it can only be produced on a machine with UPBGE
installed, and (see §6) it may need one manual component attachment. Generate it once per machine,
then commit one canonical copy through Git LFS (`git lfs lock game/spike_engine.blend`) so the
other humans can just run it.

---

## 2. How to run (exact commands)

One run = generate, launch, read the JSON row. ~3 minutes per version per machine.
Do **0.50 first** on all three machines; only run 0.44 if §5 says it is needed (or if 0.50 fails).

### 2.0 Before the first run (all machines)

1. Download the **stable** release (never a weekly alpha): <https://github.com/UPBGE/upbge/releases>.
   0.50 = Blender 5.0.1 base, 0.44.x = Blender 4.4.x base. Extract anywhere; no installer.
2. Record what you installed — we do not have hashes in the repo yet (`docs/03` §2 is a placeholder):

   ```powershell
   # Windows
   Get-FileHash .\upbge-0.50-windows-x64.zip -Algorithm SHA256
   ```
   ```bash
   # Linux
   sha256sum upbge-0.50-linux-x64.tar.xz
   ```

   Put the exact release asset URL, filename and SHA-256 in §3.2.

### 2.1 P1 — Windows, Aspire, PowerShell, Windows Python

```powershell
git switch main
git pull
$env:UPBGE_PATH = "C:\tools\upbge-0.50-windows-x64"      # folder with blender.exe + blenderplayer.exe
python scripts/check_env.py

# 1) Generate the scene WINDOWED (component creation must not run in -b, see section 6)
& "$env:UPBGE_PATH\blender.exe" --python tools/blender/gen_spike_engine.py -- --out game/spike_engine.blend
# expect: [gen] COMPONENTS: ATTACHED  (if MANUAL, see section 6.2, then re-save the .blend)

# 2) Run the probe in blenderplayer (the shipping path)
$env:RR_SPIKE_MACHINE = "P1"
$env:RR_SPIKE_SECONDS = "12"
$env:RR_SPIKE_OUT     = "spike_P1_0.50.json"
python tools/run_game.py game/spike_engine.blend

# 3) Result: paste the two [spike] table lines into section 3.1
Get-Content spike_P1_0.50.json
```

### 2.2 P2 — Windows, Tier A (ASUS V16)

Same as §2.1 with `$env:RR_SPIKE_MACHINE = "P2"` and `spike_P2_0.50.json`.
Run it **plugged in**, performance power mode, 1080p — same rules as docs/16.

### 2.3 P3 — Linux laptop

```bash
git switch main && git pull
export UPBGE_PATH="$HOME/tools/upbge-0.50-linux-x64"
python scripts/check_env.py

"$UPBGE_PATH/blender" --python tools/blender/gen_spike_engine.py -- --out game/spike_engine.blend
# 0.50 Linux is the build that segfaults when components are created via bpy in -b;
# if the windowed run also crashes here, regenerate with --no-components and attach manually (6.2).

export RR_SPIKE_MACHINE=P3 RR_SPIKE_SECONDS=12 RR_SPIKE_OUT=spike_P3_0.50.json
python tools/run_game.py game/spike_engine.blend
cat spike_P3_0.50.json
```

### 2.4 If `blenderplayer` does not start

Fallback that still tests every feature — it opens the file in the editor, so **press `P`** (or
Render ▸ Start Game) to start the embedded player:

```bash
python tools/run_game.py game/spike_engine.blend --editor
```

Record which launcher you used in §3.2; `blenderplayer` is the shipping path (docs/03 §13).

### 2.5 Optional: other version (0.44.x)

Repeat §2.1–2.3 with `UPBGE_PATH` pointing at the 0.44.x build and file names `spike_<machine>_0.44.json`.
Keep both builds side by side; do not overwrite the 0.50 folder.

---

## 3. Test matrix (feature × version × machine)

`PASS`/`FAIL`/`SKIP` comes straight from the probe (`[spike] <check> <status>`), so the table is
data, not opinion. `SKIP` means "feature absent in this build" — it is a finding, not a failure.
Fill one row per (version, machine).

**Matrix status: INCOMPLETE.** No probe rows have been recorded. The required rows are **0.50 and
0.44.x on Tier A (P2 ASUS) and Tier C (P3 Linux laptop)**; this report also asks for P1's machine row,
but that extra row does not substitute for the Tier A/C rows. Issue #9 stays open until the required
rows exist and the pin block in `docs/03` §2 is filled.

### 3.0 Machine labels

`docs/16_HARDWARE_PROFILES.md` records P2 = ASUS V16 = Tier A and **P3 = mid-spec laptop =
Tier C** (HP ZBook 14 G2; post-#65, aligned on this branch), with P1's Aspire = Tier B. This report
uses the machine labels P1/P2/P3 and does not assign a different tier to P3. The full hardware rows
in `docs/16` were filled upstream post-#65 (PR #65/#67); this branch aligns the tier labels only.

### 3.1 Feature grid

| Check | What it proves | 0.50 / P2 ASUS (A) | 0.50 / P1 Aspire (Win) | 0.50 / P3 Linux | 0.44 / P2 ASUS (A) | 0.44 / P1 Aspire (Win) | 0.44 / P3 Linux |
|---|---|---|---|---|---|---|---|
| `component` | `KX_PythonComponent` loads through `game/rr_components.py` | | | | | | |
| `tic_rates` | `setLogicTicRate(60)` / `setPhysicsTicRate(60)` read back as 60 | | | | | | |
| `physics` | dynamic box falls and comes to rest (Bullet runs, gravity −Z) | | | | | | |
| `aud_play` | `aud.Device()` + `aud.Sound.file()` + `device.play()` | | | | | | |
| `aud_volume` | `Handle.volume` write/read-back | | | | | | |
| `aud_3d` | `Handle.location` / `relative` / distance settings (docs/06 §5) | | | | | | |
| `filter2d` | `scene.filterManager.addFilter(RAS_2DFILTER_GRAYSCALE)` + remove | | | | | | |
| `overlay` | `scene.addOverlayCollection(kxCamera, collection)` + remove | | | | | | |
| `play_action` | positional `playAction(name, start_frame, end_frame, …, blend_mode=)`; keyword support is recorded in notes (non-gating) | | | | | | |
| `fps` | `bge.logic.getAverageFrameRate()` ≥ 30 on this trivial scene | | | | | | |

### 3.2 Run log (one row per machine/version)

| Version | Machine | Release asset URL | SHA-256 | Launcher | fps avg / min | Probe `summary.ok` | Notes |
|---|---|---|---|---|---|---|---|
| 0.50 | P2 ASUS (Tier A) | | | blenderplayer | | | |
| 0.50 | P1 Aspire (Windows) | | | blenderplayer | | | |
| 0.50 | P3 Linux laptop | | | blenderplayer | | | |
| 0.44.x | P2 ASUS (Tier A) | | | blenderplayer | | | |
| 0.44.x | P1 Aspire (Windows) | | | blenderplayer | | | |
| 0.44.x | P3 Linux laptop | | | blenderplayer | | | |

### 3.3 Paste space (raw rows, in case the table above gets mangled)

```text
# python tools/run_game.py prints these; paste them here verbatim
| Version | Machine | component | tic_rates | physics | aud_play | aud_volume | aud_3d | filter2d | overlay | play_action | fps | fps_avg |
```

---

## 4. What each check decides, and the `VERIFY` it closes

| Check | Decision it unlocks | If it fails |
|---|---|---|
| `component` | Whole architecture (docs/03 §4): every gameplay system is a component. | **Blocker** for that build. No component = no code path; drop the version. |
| `tic_rates` | Fixed 60 Hz logic/physics (docs/07 §1, §8.3). | Use scene-property rates or accept variable step — spec change, escalate. |
| `physics` | Bullet present and simulating (S-02 depends on it). | Blocker for the raft spike. |
| `aud_play` | Audio plays at all via `aud` (docs/06 §2, §6). | Fall back to Sound actuators (worse for music stems); affects V-11. |
| `aud_volume` | Per-bus mix (music/sfx/ambience/ui) implemented with `Handle.volume`. | Mixer needs `Sound.volume()` filters per play call — more allocations, restructure `audio_mix`. |
| `aud_3d` | 3D SFX with listener = camera (docs/06 §5). | Non-spatial only — loses hazard/waterfall direction cues. |
| `filter2d` | Runtime quality-preset switching (docs/03 §7 bloom/AO toggles, V-09). | Presets must be baked per scene or changed via materials only. Note: 2D filters do **not** work in "viewport render" mode. |
| `overlay` | HUD as a second render pass (docs/03 §4). | HUD becomes camera-parented geometry in the main scene; costs scene complexity. |
| `play_action` | Procedural animation (oars, paddles, `playAction` in glue, docs/05). | Animation must be via Action actuator or baked NLA. |
| `fps` | Baseline sanity only (trivial scene, ≥ 30). Real budgets are docs/13, measured in S-07/V-02, **not** here. | Investigate driver/vsync before blaming the engine. |

Resolved-by-docs (before any run), so the probe is checking behaviour, not guessing names:

| Question | Answer | Source |
|---|---|---|
| How to add a component from Python? | `bpy.ops.logic.python_component_register(component_name="module.Class")` (UI: Game Object Properties ▸ Python Component ▸ Add) | UPBGE API `bpy.ops.logic` |
| Tic rate API | `bge.logic.setLogicTicRate/setPhysicsTicRate(get…)` | UPBGE API `bge.logic` |
| `playAction` signature | `playAction(name, start_frame, end_frame, layer=0, priority=0, blendin=0, play_mode=…, layer_weight=0.0, ipo_flags=0, speed=1.0, blend_mode=…)` | UPBGE API `KX_GameObject` |
| Is there an "overlay scene"? | **No** since 0.3 — overlay **collections**: `scene.addOverlayCollection(kxCamera, bpy_collection)`. docs/03 §4 wording corrected in this PR. | UPBGE API `KX_Scene`, release notes 0.3.0 |
| 2D filter API | `scene.filterManager.addFilter(index, bge.logic.RAS_2DFILTER_*)`, `.removeFilter(index)`, `.getFilter(index)` | UPBGE API `KX_2DFilterManager` |
| `aud` API | `aud.Device()`, `aud.Sound.file(path)` (renamed from `Factory`), `device.play(sound) -> Handle`, `Handle.volume/location/relative/status` | UPBGE API `aud` |

Everything above is **documentation-verified, not run here**: this PR was prepared in a Linux
sandbox with no UPBGE/Blender and no GPU. The probe remains `VERIFY` until §3 is filled; do not
delete the `VERIFY` markers in `src/rr/glue/spike_probe.py` before that.

---

## 5. Is 0.44 worth testing? (cost vs decisive features)

Cost per machine: second ~300–400 MB download + extract, a second `UPBGE_PATH`, one generator run,
one probe run, plus re-checking the manual component step if 0.50 needed it. Realistically
**30–45 min per machine, ~2 h total** — noticeable, not expensive, but it also doubles the
maintenance surface (two builds on three laptops until the pin is recorded).

Recommendation (a **P1 decision**, not this PR's): **time-box 0.44 to one machine (P1) and only the
decisive checks below**, unless 0.50 fails on a feature that a second build could plausibly fix:

| Priority | Check | Why decisive |
|---|---|---|
| 1 | `component` | Everything we build is a component; 0.50 reportedly segfaults in `-b` (P3) — if windowed registration is also fragile, 0.44 is the safer pin. |
| 2 | `tic_rates` | The whole physics spec assumes a fixed 60 Hz step; a build that silently ignores the setter invalidates docs/07. |
| 3 | `aud_play` + `aud_3d` | Music stems and hazard cues are core to the cozy-chaotic feel; `aud` has changed names across versions (`Factory` → `Sound`). |
| 4 | `play_action` | Signature drifted historically (`blend_mode` added); catches glue written for the wrong build. |
| 5 | `overlay` + `filter2d` | Both are HUD/preset features we can redesign if missing (camera-parented HUD, baked presets), so they are *not* pin-decisive. |
| 6 | `physics` + `fps` | Bullet is the same library in both; fps on a trivial scene says nothing about docs/13 budgets. |

If 0.50 passes checks 1–4 on P2 and on both P1/P3, P1 may still **time-box or skip** the 0.44 runs
as a risk-reduction choice. A skipped or partial 0.44 run does **not** satisfy the `docs/10` P1.1
acceptance ("matrix complete for both candidate versions on Tier A and Tier B"): the matrix stays
**INCOMPLETE**, and issue #9 must stay open. Note: that quoted wording comes from `docs/10` §P1.1 and
is stale — it predates #65, and post-#65 `docs/16` puts P3 on Tier C and Tier B on P1's Aspire, so
"Tier A and Tier B" no longer names the same two machines as §3.1; which machines the acceptance
actually requires is a P1 decision. Record the exception and the exact rows still to run;
only a complete 0.50 + 0.44 matrix on the required tiers closes the acceptance. The 0.50 Linux `-b`
crash stays a known issue (§6.1) because our workflow does not need `-b` component creation:
generation is windowed, CI never runs Blender.

---

## 6. Known issues found while preparing this spike

### 6.1 0.50 Linux: creating a Python Component via `bpy` in `blender -b` segfaults (P3)

Reported by P3 on the 0.50 Linux build — **not reproduced by this PR** (no log/issue link in the repo yet; add one when available): `bpy.ops.logic.python_component_register(...)` in background mode kills the process. Consequences, already handled in the generator:

- `tools/blender/gen_spike_engine.py` **refuses** to register components in background mode unless
  `--allow-background-components` is passed explicitly.
- Geometry generation in `-b` is unaffected, so CI/asset tooling can still build scenes headlessly.
- Workaround if windowed registration is unavailable: generate with `--no-components`, then attach
  once by hand.

### 6.2 Manual component attachment (fallback path)

1. Generate with `--no-components` (or let a failed registration pass).
2. Open `game/spike_engine.blend` in the UPBGE build.
3. Select `SpikeProbeRoot` → **Game Object Properties** (the game tab) → **Python Component** →
   **Add** → type `rr_components.SpikeProbe` → OK.
4. Save (`Ctrl+S`). The file now carries the component; commit via LFS once for everyone.
5. Re-run §2. Verify the panel lists `SpikeProbe` and the properties `Machine`, `Seconds`, …

`game/rr_components.py` must stay next to the `.blend`; `tools/run_game.py` also puts `game/` and
`src/` on `PYTHONPATH` for `blenderplayer`.

### 6.3 Overlay is a collection, not a scene (docs/03 §4 corrected)

UPBGE 0.3 removed overlay *scenes*; `addOverlayCollection(kxCamera, collection)` takes a **bpy
Collection** and a **KX_Camera**. Two practical consequences:

- `hud.blend` cannot be "added as an overlay scene"; the HUD must become a linked collection with
  its own camera (separate `.blend` can still be linked, but community reports describe pain with
  linked overlay collections and duplicated instances — test before V-09 commits to it).
- Overlay = one extra full render pass. On Tier C (P3's laptop) this is a real cost for the HUD, so HUD draw
  calls stay a budget item for docs/13 (no budget changed by this spike).

### 6.4 2D filters are unavailable in "viewport render" mode

If the project ever selects viewport rendering, `filter2d` and `overlay` both stop working
(UPBGE 0.3.0 release notes). The probe reports `filter2d=fail`/`overlay=skip` in that mode — record
it as a configuration finding, not an engine failure.

### 6.5 `aud` class names differ across versions

Older builds expose `aud.Factory`/`aud.device()`; current builds expose `aud.Sound`/`aud.Device()`.
The probe tries `aud.Sound.file(path)` and falls back to `aud.Sound(path)`; if a build only has
`Factory`, `aud_play` fails with `AttributeError` — that is exactly the signal we want to see in the
matrix, and it would mean rewriting `rr.glue.audio` for that build.

### 6.6 Generator caveats

- The probe is attached to an **empty** (`SpikeProbeRoot`); if a build refuses components on empties,
  move it to `SpikeBox` (identical result) — record it in §3.2 notes.
- `SpikeAnim` uses `keyframe_insert` (slot-aware in Blender 4.4+/5.x) instead of building an Action
  by hand, so the `SpikeBounce` action exists in both candidates.
- `blenderplayer` shows no console on Windows by default. If no JSON appears, run the `--editor`
  variant (§2.4) or start the game from the UI and read the System Console.

### 6.7 Windows startup context and data-API generator repair

**User-observed evidence (Windows UPBGE 0.50 / Blender 5.0.1):**

- Windowed `blender.exe --python gen_spike_engine.py` failed in `add_cube()` with
  `Context has no attribute active_object`; changing that lookup to `object` also failed.
- A separate windowed probe found `window`, `screen`, `scene`, `view_layer`,
  `active_object` and `object` populated both at script start and after a 1 s timer.
- The old generator called `bpy.ops.wm.read_factory_settings(use_empty=True)` at line 185,
  before object creation at line 196. Add-ons unregistered/registered and the log reported
  `LogicNodeTree already registered` before the traceback.
- The old headless generator with `--no-components` succeeded, saved a scene and printed
  `[gen] COMPONENTS: MANUAL`.

**Assessment:** these observations support context invalidation by the mid-script factory
reset, rather than a missing context at launch. They do **not** isolate the reset as the
root cause; a before/after windowed reproduction is still **VERIFY**. The `object` lookup
substitution was not a verified fix. This checkout had no uncommitted edits when the
requested `~/gen_spike_local.patch` was saved (empty patch).

**Repair:** no factory reload or object-creation operators. Data-API cleanup removes objects,
mesh/camera/light/curve/material/action datablocks and extra collections, retaining the current
scene and its master collection. Objects link directly to `SpikeEngine` or `SpikeHud`; box
vertices carry final dimensions and object scales remain one. Timing (60 fps, base 1,
frames 1–120), unit scale 1, Bullet and gravity 9.81 are explicit. No quality presets,
resolution/render scale, tier targets or budgets changed; graphics settings are inherited.
Only component registration, saving and quitting still use operators. Component selection uses
`view_layer.objects.active` and `select_set`; `--no-components` and the background-registration
refusal (unless `--allow-background-components`) remain intact.

**Agent-run validation (2026-10-24, Windows PowerShell):** the requested WSL/Lenovo installation
paths are absent on this machine. Used the local UPBGE 0.50 at `$env:UPBGE_PATH` instead;
the WSL/`wslpath -w` invocation remains **VERIFY**. No `.blend` was saved into the repo.

```powershell
& "$env:UPBGE_PATH\blender.exe" -b --python-exit-code 1 --python tools/blender/gen_spike_engine.py -- --out "$env:LOCALAPPDATA\Temp\opencode\spike_test.blend" --no-components
# Separate process: read-only inventory/assertions (temporary validation script, not a repo tool).
& "$env:UPBGE_PATH\blender.exe" -b "$env:LOCALAPPDATA\Temp\opencode\spike_test.blend" --python-exit-code 1 --python "$env:LOCALAPPDATA\Temp\opencode\inspect_spike.py"
```

Both exited 0. Generator output (absolute output path abbreviated):

```text
Blender 5.0.1 (hash 9fcf0da621c3 built 2026-01-03 20:19:37)
[gen] components skipped (--no-components)
Info: Saved as "spike_test.blend"
[gen] scene: SpikeGround, SpikeBox, SpikeAnim(SpikeBounce), SpikeCam, SpikeSun, SpikeProbeRoot, SpikeHud/SpikeHudCam+SpikeHudLabel
[gen] COMPONENTS: MANUAL
```

Saved-file inventory from the second process (not just the generator's printed list):

| Object | Type | Collection | Location | Mesh dimensions |
|---|---|---|---|---|
| SpikeGround | MESH | SpikeEngine | (0, 0, -0.1) | (20, 20, 0.2) |
| SpikeBox | MESH | SpikeEngine | (0, 0, 3) | (1, 1, 1) |
| SpikeAnim | MESH | SpikeEngine | (2, 0, 1) | (0.6, 0.6, 0.6) |
| SpikeCam | CAMERA | SpikeEngine | (9, -9, 6) | — |
| SpikeSun | LIGHT | SpikeEngine | (4, -4, 8) | — |
| SpikeProbeRoot | EMPTY | SpikeEngine | (0, 0, 0) | — |
| SpikeHudCam | CAMERA | SpikeHud | (0, 0, 10) | — |
| SpikeHudLabel | FONT | SpikeHud | (-3, -0.5, 0) | — |

Assertions passed: exactly eight objects/two collections; unit object scales; outward box
faces; three material assignments; stored physics/mass/collision settings; active camera,
sun and HUD settings; `SpikeBounce` z=1 at frame 1 and z=2 at frame 20; explicit timing,
gravity and unit scale; zero components (expected with `--no-components`). This checks
construction and stored data, **not gameplay**.

Regression checks in `tests/test_spike_generator.py` cover the operator allowlist, baked
box dimensions/winding and explicit non-graphics settings. The settings test initially failed
on inherited `fps_base=1.001` and passed after the repair. Engine imports are stubbed for these
unit tests; they do not establish UPBGE compatibility.

- `ruff check src tests tools scripts game` → `All checks passed!`
- `python -m compileall -q src tools game` → exit 0.
- `python -m unittest discover -s tests` → 61 tests, `OK`. Verified 2026-10-30 on Windows 11
  (Python 3.12.10) at this branch (tests identical to 2b71d3a): `OK (skipped=1)` — the skip is
  `test_hardening.HookTests.test_allows_feature_branch_and_forwards_input_to_lfs`, skipped on Windows
  by design since #60 (`skipIf(os.name == "nt")`, covered by Linux CI); a no-skip `OK` is Linux-only.
  Supersedes the earlier `47 tests, OK (skipped=1)`.

**Manual windowed test — VERIFY until the owner reports output:** from the repo root, launch
a **new** UPBGE process, never run this generator in a session with unsaved work:

```powershell
& "$env:UPBGE_PATH\blender.exe" --python-exit-code 1 --python tools/blender/gen_spike_engine.py -- --out "$env:LOCALAPPDATA\Temp\opencode\spike_windowed.blend" --keep-open
```

Success requires `[gen] COMPONENTS: ATTACHED`, a saved-file message and `SpikeProbe` listed
on `SpikeProbeRoot`. `MANUAL` or `COMPONENT FAILED` means attachment was **not** verified.
If registration crashes, regenerate with `-b ... --no-components` (as above); attach
`rr_components.SpikeProbe` by hand per §6.2 and save only the temporary file. For reopening
temporary files, make `game/` and `src/` importable first (they are not beside that `.blend`):

```powershell
$env:PYTHONPATH = "$((Resolve-Path game).Path);$((Resolve-Path src).Path);$env:PYTHONPATH"
& "$env:UPBGE_PATH\blender.exe" "$env:LOCALAPPDATA\Temp\opencode\spike_test.blend"
```

Windowed generation/registration, manual attachment, runtime probe checks and the WSL
command have **not** been run by this agent. None of the S-01 feature-matrix cells is closed
by this headless validation. No commit/push is authorized by these instructions.

### 6.8 P2 probe run — OPEN FINDINGS (2026-10-26, Catalna, ASUS V16, UPBGE 0.50)

Branch `scratch/s01-p2`; JSON `spike_P2_0.50_run1.json` written to an absolute path; exit 0;
no `gpu.shader` errors. All 7 start checks + `tic_rates`, `physics`, `fps` ran.

**These are OPEN FINDINGS, not a pass or fail verdict for 0.50 on Tier A.** The matrix row for
0.50/P2 stays blank until the physics cause is isolated, the fixed probe is re-run on P1 and P2,
and the 0.44.x rows exist.

#### Finding F-1 — `tic_rates` FAIL: `getPhysicsTicRate()` returned 0.0

- Probe note: `logic=60.0 physics=0.0 (wanted 60/60)`.
- `setPhysicsTicRate(60)` was called in `start()`; the getter returned 0.0 at t≥0.5 s.
- The JSON `"tic"` field (`{"logic": 60.0, "physics": 60.0}`) is the **setpoint**, not a measurement.
- Hypotheses (unconfirmed, in priority order):
  - (a) `getPhysicsTicRate()` returns 0 before the first Bullet step completes — the setter is
    queued and the getter reflects the pre-init value; probe at 0.5 s may be too early.
  - (b) The getter API changed or was removed in UPBGE 0.50.
  - (c) Bullet was not active (would also explain Finding F-2).
- **Next step:** rerun with the updated probe diagnostics (recording exact getter value and timing).
  Do not move the matrix cell from blank to FAIL or PASS until the cause is confirmed.

#### Finding F-2 — `physics` FAIL: box never fell (`z=3.00`, `fell=0.00`)

- Observed outcome: `z=3.00 start_z=3.00 fell=0.00` — box never fell.
- Saved scene: `SpikeBox` RIGID_BODY, mass 5, BOX collision, Bullet physics engine, gravity 9.81.
- Velocity measurement unconfirmed: raw JSON and transcript are not available locally; the pre-fix probe calculated speed using `len(vel)` (which evaluates to dimension 3 for `mathutils.Vector`), so any prior assertion of `|v|=0.00` is unverified.
- The updated probe records `vx`, `vy`, `vz` separately on the next run, enabling disambiguation:
  - `vz<0` → gravity on correct axis, probe timing issue (fell value too small at t=3 s).
  - `vy≠0, vz≈0` → gravity acting on wrong axis (+Y forward, not −Z up).
  - all `v≈0` → Bullet not running / physics not ticking; root cause shared with F-1.
- **Next step:** fix-probe rerun on P1 and P2 with velocity components to isolate the physics cause.

#### Finding F-3 — `fps` artifact: avg=200050.1, min=0.0, n=25

- `getAverageFrameRate()` returned avg=200050.1, min=0.0, n=25.
- This is junk (first-sample artifact; same ~1e6 outlier seen by hicesse on Linux).
- It is **not an engine failure**; it is a sampling artifact from calling `getAverageFrameRate()`
  at t≈0 before the estimator has frame history.
- **Not recorded as a pass or fail of the `fps` check** for 0.50 on Tier A.

---

## 7. Decision rules and provisional recommendation

**Pass bar for the pin:** `component`, `tic_rates`, `physics`, `aud_play` PASS on the same version on
**all three machines** (P2, P1, P3; `docs/16` post-#65 records P2 = Tier A and P3 = Tier C); `aud_3d` and
`play_action` PASS on at least one machine; `overlay` and `filter2d` MAY be SKIP (redesignable);
fps ≥ 30 on the trivial scene everywhere it runs.

`fps` is graded PASS when the **median** of the used samples is ≥ 30 after dropping every sample
before 1.0 s plus non-finite and non-positive values (`src/rr/core/spike.py::compute_fps_stats`) —
criterion changed after the P2 run; earlier artifacts used avg.

**Provisional recommendation (not a decision):** pin **0.50** if the bar is met — it is the newest
stable line, has the fast-AddObject and GPU-skinning work the asset/perf plans want (docs/03 §8),
and the only known defect so far (background component creation) does not affect the shipping
workflow. Keep **0.44.x** as the fallback for S-02/S-03 if raft physics destabilises on the Blender
5 base (risk R-01 already says "switch to 0.44 if 0.50 blocks by M1 end").

**Escalate to the human owner (P1) instead of switching unilaterally if:** any of `component`,
`tic_rates`, `physics`, `aud_play` fails on 0.50 on Tier A or Tier C (P2 or P3), or the 0.50 Linux
build cannot run the probe at all.

**Pin block (docs/03 §2) — fill only after approval:**

```text
UPBGE version: ____   Blender base: ____
URL: ____   SHA256: ____
Decided: ____ (date) by ____  — approved by P1
Re-run smoke on: Tier A ____  Tier B ____  Tier C ____
```

---

## 8. Results log

| Date | Who | Version | Machine | Outcome |
|---|---|---|---|---|
| 2026-10-24 | gameplay agent | — | Linux sandbox | Generator + probe + grading tests written; **no UPBGE available, nothing run**. |
| 2026-10-26 | P2 (Catalna) | 0.50 (Blender 5.0.1) | ASUS V16 (Tier A, Windows, `blenderplayer`) | **Full probe run** on `scratch/s01-p2` branch. All 7 start checks ran. JSON written to absolute path; exit 0; no `gpu.shader` errors. **OPEN FINDINGS — not yet pass/fail of 0.50 on Tier A:** (1) `tic_rates` FAIL: `logic=60.0 physics=0.0` — getter returned 0.0; cause unconfirmed (see §6.8). (2) `physics` FAIL: `z=3.00 start_z=3.00 fell=0.00` — box never fell despite scene having RIGID_BODY mass=5, BOX, Bullet, gravity=9.81; cause unconfirmed (see §6.8). (3) `fps avg=200050.1 min=0.0 n=25` — junk; first-sample `getAverageFrameRate()` artifact, same ~1e6 outlier seen on Linux (not an engine failure). JSON `"tic"` field records the **setpoint** (60/60), not a measurement. Matrix cell for 0.50/P2 stays blank until the physics cause is isolated, the fixed probe is re-run on P1 and P2, and the 0.44.x rows exist. |
