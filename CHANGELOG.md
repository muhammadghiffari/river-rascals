# Changelog
All notable changes to River Rascals. Format: Keep a Changelog; versioning: SemVer (0.x until vertical slice done).

## [Unreleased]
- Initial handover pack: PRD, GDD, architecture, specs, prompts, OpenCode config, core logic + tests, tooling.
- Continuation: fixed ruff errors (CI would have failed), `check_env.py` false-positive for git-lfs, read-only agents now truly read-only, direct push to `main` denied, Blender MCP package renamed to `mcp-for-blender`, migrated `tools` to `permission`, corrected local-override docs (`.opencode/opencode.jsonc`), added repo-consistency and physics-target tests, README, cost log, verification status.
- Hardening pass (first-setup audit): `scripts/hooks/pre-push` blocks direct pushes to main on any plan; `check_env.py` now requires git user.name/email; `opencode.json` asks before `env`/`printenv`, denies `--no-verify`; CI pins ruff/pytest and has a timeout; added Dependabot for Actions; docs/12 LFS quota updated to verified 10 GiB/10 GiB.
- S-01 engine spike: added `tools/blender/gen_spike_engine.py` + `rr_components.SpikeProbe` + `rr.core.spike` grading (unit-tested), a generated-tone `aud` fixture, and the 0.50-vs-0.44 test matrix in `docs/reports/S-01_engine_decision.md`. `docs/03` §4 now names the real overlay API (collection + camera, not overlay scene). The pin is unchanged pending human runs.
- Fix: `core.hooksPath` blocked Git LFS from installing its hooks (`git lfs install` conflict). `scripts/hooks` now also provides the LFS pre-push/post-checkout/post-commit/post-merge hooks, and `bootstrap_github.py` uses `git lfs install --skip-repo`. Never run `git lfs update --force` in this repo (it would overwrite the main-push guard).
