# Batch 2 phase 1: original props and environment

## Scope and baseline

User approved starting from `ba46e73` on `feat/props-env`: there were no prior
Batch 2 generators, no uncommitted files and no remote branch of that name.
Implementation follows `docs/plans/2026-10-30-props-env.md` and the existing
docs/04 art brief plus tighter `docs/reference/ASSET_LIST.csv` row budgets.
Only P0 props/environment geometry libraries are covered. Materials/characters,
runtime wiring and later-chapter river strips are separate work.
`PR_ReedCluster` is intentionally excluded: its inventory phase is 2, but it is
not in the requested docs/04 section 11 P0 list. Batch number is not inventory phase.

The existing imported `PR_RockLarge.blend` and texture are preserved. Original
rock alternatives do not resolve or reuse its disputed QAL/CC0 source.

## Baseline verification

- `python -m unittest discover -s tests`: 191 tests, OK, 1 skipped.
- `ruff check .`: All checks passed.
- `python tools/validate_assets.py assets`: 3/3 passed (existing assets only).
- Authoring executable selected by `tools/run_game.py`: Blender 5.0.1.
- `git check-attr filter lockable` confirmed `.blend` LFS and lockable attributes.
- New provenance regression test was run before adding records: correctly failed
  for all 15 missing original P0 families and absence of own-work records.

## Acceptance gates

The repository validator only applies generic PR=3000 and EN=4000 limits.
Its green result alone **does not prove** tree/rock/inventory compliance.
Generator checks and pure tests must enforce the unchanged tighter row limits,
including PineTree LOD1 <=200, Bush <=200 and Coin <=200.
All new deliverables need eight-column provenance with tool path and CC0 own work.

Independent preflight review additionally requires aggregate evaluated geometry
counts, positive unit scales (the stock validator can accept all-negative unit
scale), actual palette UV layers, matching LODs, named foam/sway data, open arch
passages, real banner weights and unique original-rock object names. Collider
counts must be reported separately; file provenance must not imply validation
that only a custom property asserts.

## Manual verification required (VERIFY)

1. P2: open each original library, inspect silhouette at 20/30 m and scale beside
   the 3.2 m raft; confirm palette appearance and original art direction.
2. P2: inspect checkpoint banner bone deformation and confetti sockets; check
   chain stubs, acorn emblem, fish pose, log knots and moss masks visually.
3. P2/P3: append assets into a disposable UPBGE test scene, not `game/main.blend`.
   Verify collider contacts and clearance, coin bob hookup, tree LOD switching
   and sway, bank tile seams/foam anchors, river UV flow and water shader hookup.
4. P3: verify SkyDay shader appearance in UPBGE without altering presets/settings;
   measure scene draw calls, tris and fps on Tier B under existing docs/13 targets.
5. Attach preview renders to a future PR. No render/quality settings were changed
   to create previews during this task.

Runtime and visual acceptance remain PARTIAL until those checks are evidenced;
generator/export completion must not be described as full asset production DONE.
