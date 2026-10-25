# game/

Runtime `.blend` scenes live here (managed by Git LFS), plus `rr_components.py`.

Planned scene files (see docs/03_TECH_ARCHITECTURE.md):
- `main.blend`       – boot + main menu scene
- `ch01_sleepy_creek.blend` ... `ch05_thunder_falls.blend` – level scenes (link assets from ../assets)
- `hud.blend`        – HUD overlay collection (not an overlay scene; see docs/03 §4)
- `spike_engine.blend` – S-01 engine probe scene, **generated** (not hand-authored):

```bash
# windowed: Python Component creation segfaults in `blender -b` on 0.50 Linux
"$UPBGE_PATH/blender" --python tools/blender/gen_spike_engine.py -- --out game/spike_engine.blend
python tools/run_game.py game/spike_engine.blend          # see docs/reports/S-01_engine_decision.md
```

If `[gen] COMPONENTS: MANUAL` is printed, attach `rr_components.SpikeProbe` to `SpikeProbeRoot`
once (Game Object Properties ▸ Python Component ▸ Add), save, then commit the file through LFS.

One owner per .blend at a time. Use `git lfs lock game/<file>.blend` before editing.
