# AGENTS.md — Rules for every AI agent working on River Rascals

> OpenCode loads this file automatically. Read it fully, then read the doc referenced by your task.

## Project in one paragraph
**River Rascals** (working title) is a cozy-chaotic, physics-based co-op rafting adventure for 1–4 local players
(online co-op is a stretch goal). Engine: **UPBGE** (pinned version in `docs/03_TECH_ARCHITECTURE.md`), game code in **Python**,
assets in **Blender/UPBGE**. Team: 3 humans (P1 lead/tech, P2 art/tech-art, P3 design/audio/QA) + AI agents. Genre inspiration: the
cozy-chaotic co-op rafting genre (e.g. *Oar'some Adventures*). We build **original** characters, art, audio and levels. Never copy
third-party IP, assets or code that lacks a compatible licence.

## Source of truth (read in this order)
`docs/01_PRD.md` → `docs/02_GDD.md` → `docs/03_TECH_ARCHITECTURE.md` → `docs/07_PHYSICS_SPEC.md` → task-specific doc.
Prompts per phase: `docs/10_PHASE_PROMPTS.md`. Model/effort routing: `docs/09_MODEL_ROUTING_AND_REASONING.md`.

## Hard rules
1. **Layering**: `src/rr/core/` = pure Python, NO `bge`/`bpy`/`mathutils`/`aud` imports, 100 % unit-testable. `src/rr/glue/` = thin UPBGE adapters. Logic never lives in glue.
2. **Verify before claiming**: run tests/lint/smoke; paste real output summaries. Anything touching `bge` that you could not run is marked `VERIFY` in code and in the PR.
3. **Conventions**: +X right, +Y forward, +Z up, 1 unit = 1 m, 60 Hz logic & physics. Names per `docs/04_*`. Tunables are data, not magic numbers.
4. **Git**: branch `type/short-desc` (`feat/`, `fix/`, `art/`, `docs/`, `chore/`), Conventional Commits, small PRs, CI green, never push to `main`, never force-push, never rewrite shared history. `.blend` and audio/texture files go through Git LFS; lock a `.blend` before editing (`git lfs lock <path>`), unlock after merge.
5. **Secrets**: never commit tokens/keys/`.env`; never print them; use environment variables (`GITHUB_TOKEN`, `GATEWAY_API_KEY`). If you see a secret in the repo, stop and report.
6. **MCP safety**: Blender MCP runs arbitrary Python inside Blender and its socket is unauthenticated. Use it only in a working copy under `assets/`, localhost only, telemetry off, save before risky operations. Only the `techart` agent uses it.
7. **Assets**: CC0/own-made only. Every external asset gets a row in `assets/PROVENANCE.csv` (source URL, author, licence, date). AI-generated assets: record tool + prompt + terms-of-service note.
8. **Performance budgets** (`docs/13_QA_PERFORMANCE_PLAN.md`) are requirements, not suggestions.
9. **Scope discipline**: do only what the issue asks. Note extra ideas as new issues.
10. **Ask the human** when: credentials/permissions are missing, a destructive action is needed, requirements conflict, or a decision changes scope/cost.

## Definition of Done (code)
- [ ] Acceptance criteria in the issue met · [ ] unit tests added/updated and passing · [ ] lint clean · [ ] smoke test run if gameplay-affecting
- [ ] docs updated · [ ] PR description filled (what/why/how tested/risks/VERIFY items) · [ ] independent review (`@reviewer`) for risk:high

## Definition of Done (asset)
- [ ] Matches style + naming + budgets · [ ] `python tools/validate_assets.py <file>` passes · [ ] provenance row added · [ ] preview render attached to PR
- [ ] Tested in a UPBGE scene on the mid-spec laptop (P3) for fps impact

## Commands
```
python scripts/check_env.py                      # machine readiness
python -m unittest discover -s tests -v          # core unit tests (pytest also works)
python tools/run_game.py game/<scene>.blend      # play
python tools/run_game.py game/<scene>.blend --smoke --seconds 20
python tools/validate_assets.py assets           # asset budget/naming gate
```

## Required report format (end of every task)
```
## Report
Done: <what changed, files>
Verified: <exact commands run + results>
Not verified / VERIFY: <list>
Risks & assumptions: <list>
Next suggested step: <one item>
```

## Model escalation (summary)
Default `builder` (deepseek-v4-pro, medium). Escalate to `gameplay` (kimi-k3) for complex features, to `debugger`/`architect` (gpt-6-astra) only after two failed attempts or for design decisions. Use `@reviewer` for independent review, `@qa` for test runs.
