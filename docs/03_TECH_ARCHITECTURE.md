# 03 — Technical Architecture (TDD)

## 1. Principles
1. **Core/glue split**: pure Python in `src/rr/core` (tested, no engine imports); thin UPBGE adapters in `src/rr/glue`.
2. **Data over code**: tunables in JSON/component args; no magic numbers.
3. **Fixed timestep**: 60 Hz logic and physics (`bge.logic.setLogicTicRate(60)`, `setPhysicsTicRate(60)`).
4. **Observable**: structured logs, smoke test, debug overlays.
5. **Conflict-resistant repo**: many small `.blend` files, one owner at a time, LFS locks.

## 2. Engine & version pinning (decision pending spike S-01)
Facts gathered at handover time: UPBGE **0.50** is built on **Blender 5.0.1** (released January 2026; adds experimental GPU skinning, fast AddObject via dupli-base, 2D filter refactor). The previous stable line was UPBGE 0.44 (Blender 4.4.x), and 0.36 (Blender 3.6). UPBGE is a community fork with a small contributor base.
**Recommendation**: evaluate 0.50 first (newest features, long-term support) and keep 0.44.x as the fallback. Pick **one** version for all three machines; record version, URL and SHA-256 here after S-01:
```
UPBGE version: ____   Blender base: ____   URL: ____   SHA256: ____   Decided: ____ by ____
```
**S-01 status (2026-10-24)**: probe scene, component and test matrix prepared — `docs/reports/S-01_engine_decision.md`. Pin unchanged; the matrix must be filled on Tier A/B (and optionally C) before this block is completed. Known 0.50 Linux issue: creating a Python Component via `bpy` in `blender -b` segfaults, so scene generation is windowed (`tools/blender/gen_spike_engine.py` refuses background component creation).
Never upgrade the pinned engine without a PR that re-runs smoke tests on both hardware tiers.
**Re-checked 2026-10-23**: 0.50 (Blender 5.0.1, Jan 2026) is still the latest *stable* release. The UPBGE repo also publishes automated **weekly alpha** builds (0.52/0.53 Alpha at the time of writing) — these are pre-releases and must **not** be pinned. Pin by release URL + SHA-256, not by "latest".

## 3. Repository layout
```
river-rascals/
  AGENTS.md  opencode.json  pyproject.toml  CHANGELOG.md
  docs/            specs (this folder)         prompts/   agent + asset + audio prompts
  backlog/         issue source                scripts/   repo/GitHub/env tooling
  tools/           run_game, validators, bpy scripts
  src/rr/core/     PURE logic + tests          src/rr/glue/  UPBGE components
  game/            runtime .blend scenes + rr_components.py shim
  assets/          source .blend, textures, audio, PROVENANCE.csv
  tests/           unit tests (+ future integration)
  builds/          (git-ignored) exported builds
```

## 4. Runtime architecture
```
 Input devices ─▶ InputMap (core) ─▶ PlayerSlots ─▶ Oar state machines (core)
                                                      │ thrust/torque
 River (core) ──flow──▶ RaftPhysics (glue) ◀── waves (core)
                          │ forces on Bullet body
 Events (core EventBus) ◀─┴─▶ Hazards · Collectibles · Checkpoints · HUD · Audio · VFX
 Save (core) ◀──▶ Game state ◀──▶ Settings (quality presets)
```
- **Scenes**: `main.blend` (boot/menu), one level scene per chapter, `hud.blend` linked as an **overlay collection** with its own camera — `KX_Scene.addOverlayCollection(kxCamera, collection)` / `removeOverlayCollection(collection)`; overlay *scenes* no longer exist since UPBGE 0.3 (API verified in S-01, see `docs/reports/S-01_engine_decision.md` §6.3; costs one extra render pass).
- **Components** (UPBGE `KX_PythonComponent`): `RiverLoader`, `RaftPhysics`, `RaftOars`, `SmokeTest` (exist), plus `Hazard*`, `Collectible`, `Checkpoint`, `GameDirector`, `HudController`, `MusicDirector` (to build).
- **Game state machine**: `Boot → Menu → ChapterLoad → Countdown → Playing ⇄ Paused → (Sunk → Respawn) → Finish → Results → Workshop`.
- **Event names** (core bus): `coin_collected`, `fish_collected`, `hull_damaged`, `hull_repaired`, `checkpoint_reached`, `player_overboard`, `player_rescued`, `raft_sunk`, `chapter_finished`, `hazard_entered`, `music_state_changed`.

## 5. Authoring contracts in `.blend` scenes
| Item | Contract |
|---|---|
| River centerline | empties `RiverPt.000…NNN` (spacing ≤ 8 m), property `width` per point |
| Water surface | one mesh `EN_RiverStrip_<ch>` with `MT_Water`; physics water level = property `water_level` on `RiverRoot` empty |
| Raft | `RF_RaftT1` with children `BuoySample.00..05`, `RF_Oar_L/R`, `Seat.0..3` |
| Checkpoints | empties `Checkpoint.NN` (property `s` optional; otherwise computed by projection) |
| Hazards | empties `Hazard_<Type>.NN` with properties (`radius`, `strength`) + visual instance |
| Collectibles | empties `Coin.NN`, `Fish.NN` (spawn markers; pooled visuals) |
| Camera | `Cam_Main` with component `ChaseCamera` |
Validation script (to build in V-01): `tools/validate_scene.py` checks the contracts and prints missing items.

## 6. Physics settings (see 07)
Bullet via UPBGE; units metres; gravity −9.81; raft dynamic with box/convex collider; water is **not** a collider (buoyancy is forces); banks are static meshes with a collision margin ≥ 0.05; collision groups per 07 §5.

## 7. Rendering & quality presets
| Setting | Low (Tier B default) | Medium | High (Tier A default) |
|---|---|---|---|
| Render scale | 75 % | 100 % | 100 % |
| Shadows | blob/fake or 1 cascade 1024 | 2 cascades 2048 | 3 cascades 2048 |
| SSR/AO/bloom (2D filters) | off | bloom | bloom + AO |
| Water | 2 waves, no refraction | 3 waves, depth tint | 3 waves, foam, depth |
| Particle density | 40 % | 70 % | 100 % |
| Foliage sway | off | on | on |
| Draw distance | 120 m | 180 m | 250 m |
Preset values live in `game/settings/presets.json` (to create in V-09). Render in EEVEE-based UPBGE viewport; **prefer baked/unlit-toon materials** for cheapness. VERIFY which settings are runtime-changeable via `bge.render` / scene properties.

## 8. Performance techniques
LODs for trees/rocks (note: objects with modifiers/shape keys cannot have LODs per community reports — apply modifiers, avoid shape keys); object pooling for coins/particles; UPBGE 0.50 **fast AddObject** (dupli-base) for spawners; instancing via collection instances where supported; **GPU skinning** is experimental — test on both tiers before relying on it; keep bone count ≤ 25 per character; limit active lights (1 sun + ≤ 4 points); shared palette material to cut draw calls; avoid per-frame allocations in Python (reuse `Vector`s).

## 9. Audio
`aud` module: one `aud.Device`, 4 mixer buses by volume factors (music/sfx/ambience/ui) applied at play time; 3D-positioned SFX use `Handle.location` with listener = camera. Adaptive music: 3 stems playing in sync, volumes crossfaded by `MusicDirector` over 1.5 s. Details: `06`.

## 10. Save / settings / logging
`rr.core.save` — versioned JSON, atomic writes, corrupt-file backup. Location: user data dir (`%APPDATA%/RiverRascals` on Windows, `~/.local/share/RiverRascals` on Linux). Logs: rotating text logs (5 × 1 MB) in the same dir; diagnostic bundle zip (FR-23).

## 11. Testing strategy
| Level | What | Tool | Where |
|---|---|---|---|
| Unit | core logic | unittest/pytest | CI |
| Static | lint, compile, JSON validity, secret grep | ruff, compileall | CI |
| Asset | naming/budgets | `tools/validate_assets.py` (needs Blender) | local + manual CI later |
| Smoke | scripted autopaddle run with fps report | `tools/run_game.py --smoke` | local on both tiers |
| Manual | playtests | checklist in 13 | weekly |
UPBGE cannot run on GitHub-hosted runners without a build; a **self-hosted runner** on the ASUS V16 is a post-M2 optional upgrade.

## 12. Online co-op (stretch, design now, build later)
Bullet is not deterministic across machines ⇒ **host-authoritative**: host simulates physics; clients send input (oar press, direction) at 30 Hz and receive raft snapshots (pos/rot/vel) at 20 Hz with interpolation. Keep `InputMap` and `Oar` state machines input-driven (already true) to make this feasible. Transport (Python sockets/UDP or a library) decided in R-05.

## 13. Build & distribution
`blenderplayer` runs `.blend` files; exporting a self-contained build (publishing addon or manual folder packaging) is spike **S-06** (a community report notes the publishing addon errored on UPBGE 4.4 at some point — test early). Output zip under `builds/` named `RiverRascals_<version>_win64.zip`; Linux optional.

## 14. Security & privacy
No networking, no telemetry; saves are local JSON, parsed defensively; MCP/Blender automation limited to dev machines (08).

## 15. Decision log (append)
| Date | Decision | Why | By |
|---|---|---|---|
| handover | Seated slots instead of free-roam on raft | stability + scope | architect |
| handover | Local co-op first, shared camera | no split-screen cost | architect |
| handover | Core/glue split with unit tests | UPBGE cannot be tested in CI | architect |
| continuation | Pin stable UPBGE only (0.50 or 0.44.x); never weekly alphas | stability for 3 machines | continuation session |
| continuation | OpenCode access control via `permission` (not deprecated `tools`); read-only agents get a bash allowlist; direct pushes to `main` denied | verified against OpenCode 1.19.4 effective rules | continuation session |
| continuation | Blender MCP package is `mcp-for-blender` | upstream rename, verified 2026-10-23 | continuation session |
