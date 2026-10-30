# P0 props export evidence — 2026-10-30

## Deliverables

Generator: `tools/blender/gen_p0_props.py`; pure geometry:
`src/rr/core/prop_geometry.py`; tests: `tests/test_prop_geometry.py`.

Original procedural geometry and an original shared 16-stripe packed palette
(`T_P0Palette_BC`, 512x512 PNG) with one `MT_ToonBase` two-band, normal-directed
material. No external assets or third-party geometry. The imported
`assets/props/PR_RockLarge.blend` and its texture are untouched; the original
boulder alternatives carry an explicit `_Own` suffix so appending both libraries
cannot silently merge object names. `_Own` is a documented naming deviation from
`docs/04` `<PREFIX>_<Name>[_LODn|_COL]`; the repository validator accepts it.

Exact exported file list (strict limits are the `ASSET_LIST.csv` row budgets,
which are tighter than the generic validator's PR=3000 limit):

| File under `assets/props/` | Visible tris | Collider tris | Strict limit | Bones / sockets |
| --- | ---: | ---: | ---: | --- |
| PR_Coin_01.blend | 172 | 0 | 200 | 0 / 0 |
| PR_GoldenFish_01.blend | 176 | 0 | 400 | 0 / 0 |
| PR_Buoy_01.blend | 220 | 76 | 300 | 0 / 0 |
| PR_Buoy_02.blend | 220 | 76 | 300 | 0 / 0 |
| PR_Log_01.blend | 412 | 116 | 600 | 0 / 0 |
| PR_Log_02.blend | 412 | 116 | 600 | 0 / 0 |
| PR_Log_03.blend | 412 | 116 | 600 | 0 / 0 |
| PR_RockSmall_01..03.blend | 76 / 84 / 92 | same as visible | 300 | 0 / 0 |
| PR_RockMed_01..03.blend | 76 / 84 / 92 | same as visible | 600 | 0 / 0 |
| PR_RockLarge_01_Own..03_Own.blend | 76 / 84 / 92 | same as visible | 1200 | 0 / 0 |
| PR_Signpost_01..03.blend | 52 each | 0 | 300 | 0 / 0 |
| PR_CheckpointArch_01.blend | 140 | 0 | 1500 | 4 / 0 |
| PR_FinishGate_01.blend | 140 | 0 | 2000 | 4 / 2 confetti |

Measured dimensions: small rocks 1.18–1.33 x 1.05–1.10 x 0.55–0.69 m, medium
2.14–2.42 x 1.90–2.00 x 1.00–1.25 m, large 3.53–4.00 x 3.14–3.30 x 1.65–2.06 m.
All visible meshes have a base pivot at z = 0, are X/Y centred, have identity
location/rotation/scale, flat shading, one `PaletteUV` layer whose loops sample
palette cell centres, and exactly one `MT_ToonBase` material. Logs use a capsule
collider, rocks a closed convex-hull collider, buoys a convex hull. The
checkpoint spans an 8 m passage and the finish gate 10 m, with posts outside the
passage. Both carry a 4-bone flutter rig with normalized banner weights;
the finish gate exposes `Socket_Confetti_1` / `Socket_Confetti_N1`.

## Commands and observed results

Working directory: repository root. `UPBGE_PATH` selected Blender 5.0.1.

1. RED before implementation: the prop geometry test module failed because
   `rr.core.prop_geometry` did not exist; implementation followed.
2. `python -m unittest discover -s tests -p test_prop_geometry.py -v` —
   `Ran 5 tests`, `OK`.
3. `python tools/blender/gen_p0_props.py --replace-locked` — exit 0, printed
   `PROP_VERIFIED` for all 21 assets and `P0_PROPS_COMPLETE`. The host verifies
   `git lfs locks --verify --json`, acquires any missing own locks, and only then
   starts Blender. Saving uses a session-only `save_version = 0`, so no `.blend1`
   artifacts remain.
4. `python tools/blender/gen_p0_props.py --verify-only` — exit 0 after the
   canonical palette contract was applied; stale exports failed earlier on the
   palette image name, which is why regeneration was required.
5. Independent read-only audit (separate script, not the generator) reopened all
   21 libraries and measured evaluated triangles, bounds, UV layers, colour
   attributes, vertex groups, images and worlds. Results match the table above;
   every library carries one packed 512x512 PNG.
6. `python tools/validate_assets.py assets/props` — all props passed; the whole
   `assets` run reported `34/34 passed`.
7. `ruff check src/rr/core/prop_geometry.py tests/test_prop_geometry.py tools/blender/gen_p0_props.py`
   — `All checks passed!`.

## Not verified / VERIFY

- Human P2 silhouette, palette/two-band appearance, acorn emblem, fish pose, log
  knots and moss masks; no previews were rendered.
- Runtime collision group/margin setup, coin bob hookup, banner action playback
  and deformation, confetti socket use, and Tier B frame-time impact.
- Collectible/hazard behaviour is runtime scope; these libraries deliberately
  contain no game properties or sensor logic.
- Provenance and repository-wide gates are recorded by the parent.
- The imported Quaternius rock's QAL/CC0 question remains open and is not
  resolved or reused by these original alternatives.

## Risks & next step

Triangles are well inside every strict row budget; the coin has only 28 spare
triangles, so future detail must replace geometry rather than add it. No
performance claim follows from budget compliance. Next: human art review and a
disposable UPBGE test-scene pass before any level integration.
