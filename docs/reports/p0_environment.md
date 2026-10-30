# P0 environment export evidence — 2026-10-30

## Deliverables

Generator: `tools/blender/gen_p0_environment.py`; material helper:
`tools/blender/environment_materials.py`; pure core:
`src/rr/core/environment_geometry.py`; tests:
`tests/test_environment_geometry.py`.

Original procedural geometry and original shared 16-cell packed palette using the
project's palette colours. No external assets. Each foliage/bank library carries
one packed palette and shared `MT_ToonBase` two-band, normal-directed material.
Libraries contain collections/datablocks, not game scenes. Sky is a standalone
world datablock and has zero mesh geometry; it is not assigned to a scene.

Exact exported file list (parent supplies provenance for these and all four
source/test files above, plus this report):

| File under `assets/environment/` | Actual triangles | Strict limit |
| --- | ---: | ---: |
| EN_PineTree_01.blend | 204 + LOD1 80 | 800 + 200 |
| EN_PineTree_02.blend | 204 + LOD1 80 | 800 + 200 |
| EN_PineTree_03.blend | 204 + LOD1 80 | 800 + 200 |
| EN_Bush_01.blend | 132 | 200 |
| EN_Bush_02.blend | 132 | 200 |
| EN_Bush_03.blend | 132 | 200 |
| EN_BankTile_01.blend | 114 + COL 114 | 1500 (228 including COL) |
| EN_BankTile_02.blend | 114 + COL 114 | 1500 (228 including COL) |
| EN_BankTile_03.blend | 114 + COL 114 | 1500 (228 including COL) |
| EN_BankTile_04.blend | 114 + COL 114 | 1500 (228 including COL) |
| EN_RiverStrip.blend | 768 | 3000 |
| EN_SkyDay.blend | 0 | 0 |

Pine LOD objects are hidden in the authoring collection; runtime selection is
separate. `Sway` POINT float vertex colour stores normalized height squared.
Banks 01/02 are 4m long, 03/04 are 8m long, all 4m wide. Nine `FoamAnchor`
vertices run along each shore. Closed colliders match the transition profile,
minimum thickness 0.3m; base origin is z=0, placement metadata z=-0.3 puts shore
anchors at water level. End cross-sections match for Y-axis tiling.
River is a 48m gently curving example with 49 centreline samples, eight cross
segments and cumulative-distance V coordinates; core accepts other centrelines.

## Commands and observed results

Working directory: repository root.

1. RED before implementation:
   `$env:PYTHONPATH='src'; python -m unittest discover -s tests -p test_environment_geometry.py -v`
   — `Ran 1 test`, `FAILED (errors=1)`, missing `rr.core.environment_geometry`.
2. During development the seam test found ordering differed between equivalent
   endpoint vertex sets; comparison corrected to sorted geometric coordinates.
3. Same scoped unittest command after implementation — `Ran 6 tests`, `OK`.
4. `python -c "from tools.run_game import find_exe; print(find_exe('blender'))"`
   resolved the `UPBGE_PATH`-selected Blender 5.0.1 executable.
5. `git lfs lock assets/environment/EN_PineTree_01.blend` — locked.
6. `python tools/blender/gen_p0_environment.py` — exit 0. Generator checked
   `git lfs locks --verify --json`, acquired all eleven remaining locks before
   any export, then exported all twelve files. No overwrite or backup-save path
   is used (`bpy.data.libraries.write`). Locks remain for parent/merge handling.
7. `python tools/blender/gen_p0_environment.py --verify-only` — exit 0; reopened
   all twelve saved libraries in fresh headless processes. Counts above measured
   via `calc_loop_triangles`, not estimated. All mesh objects had one material,
   identity location/rotation/scale and nonzero triangle areas; palette UV cell
   centres and packed image, Sway 0..1, FoamAnchor count/height, river FlowUV and
   named MT_Water reference were checked. Sky world unassigned, zero mesh objects.
8. `python -m ruff check src/rr/core/environment_geometry.py tests/test_environment_geometry.py tools/blender/gen_p0_environment.py tools/blender/environment_materials.py`
   — initial run found two style issues (strict zip/import ordering), corrected;
   final rerun: `All checks passed!` (exit 0).
9. Final scoped unittest rerun: `Ran 6 tests in 0.004s`, `OK`.
10. Canonical palette reconciliation: the shared palette contract is 16 vertical
    stripes in a packed 512x512 PNG, cell UV `((index+0.5)/16, 0.5)`. After the
    contract update the stale exports failed `--verify-only` on the palette image
    name; they were regenerated with
    `python tools/blender/gen_p0_environment.py --replace-locked` (own locks
    verified first, no backups) and `--verify-only` passed 12/12 afterwards.
11. Final `python tools/blender/gen_p0_environment.py --verify-only` rerun after
    stronger preflight checks — exit 0, all twelve libraries passed. Evaluated
    dependency-graph triangle counts equal saved counts; no modifiers/shape keys;
    entire asset material set <=2; packed palette format PNG, 512x512 power-of-two;
    bank manifold edge use exactly two and minimum positive height >=0.3m.
    Directory inventory contains exactly the twelve `.blend` deliverables above,
    no `.blend1` or temporary exports.
12. Repository gate run by parent: `python tools/validate_assets.py assets` —
    all 34 libraries passed, including the twelve environment libraries.

Executable banner: Blender 5.0.1, hash `9fcf0da621c3`, built 2026-01-03.
User startup logs register BlenderMCP addon; this task used only local command-line
Python, no MCP calls/socket. No scene graphics settings were changed.

## Not verified / VERIFY

- Human P2 silhouette, palette/two-band appearance, bank seam appearance and sky
  gradient direction/appearance; previews were not rendered.
- Runtime tree LOD selection/sway, foam placement, collision group/margins,
  river/physics wave matching, sky world assignment, Tier B frame-time impact.
- `MT_Water` is a named reference only, explicitly marked VERIFY on material and
  object. Water wave/depth/foam/flow shader implementation is separate scope.
- Repository-wide validator/tests/lint and eight-column provenance are parent
  responsibilities. Parent-owned intentionally-red provenance test excluded.
- Original-code/asset licensing and AI tool terms note are recorded by parent.

## Risks & next step

Fixed normal-direction toon lighting is authoring-ready but needs human/runtime
appearance review. No performance claims follow from triangle-budget compliance.
Next: parent registers provenance and runs the repository asset gate.
