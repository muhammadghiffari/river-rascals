# game/

Runtime `.blend` scenes live here (managed by Git LFS), plus `rr_components.py`.

Planned scene files (see docs/03_TECH_ARCHITECTURE.md):
- `main.blend`       – boot + main menu scene
- `ch01_sleepy_creek.blend` ... `ch05_thunder_falls.blend` – level scenes (link assets from ../assets)
- `hud.blend`        – overlay scene for HUD

One owner per .blend at a time. Use `git lfs lock game/<file>.blend` before editing.
