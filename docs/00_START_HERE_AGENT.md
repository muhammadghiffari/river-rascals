# 00 — START HERE (Agent Handover Runbook)

Audience: the **repo owner's agent (P1)**, who sets everything up first. Teammates' agents follow `12_GIT_WORKFLOW_AND_GITHUB_SETUP.md` §7–8 afterwards.
Read `AGENTS.md` first. Total time for this runbook: ~1–2 hours.

## 0. Context in 60 seconds
Original cozy-chaotic co-op rafting game (genre inspiration: *Oar'some Adventures*, a 1–8 player rafting game by Haymaker Games — we do **not** reuse its name, art, characters or levels). Engine **UPBGE**, code **Python**, agents via **OpenCode**, MCP for Blender. Team of 3 humans + agents. Hardware: P2 = ASUS V16 (strong), P3 = mid-spec laptop, P1 = owner's machine.
This pack contains: PRD/GDD/specs, backlog (56 issues), OpenCode config (10 agents), prompts, tested pure-Python core + repo checks (28 tests), UPBGE glue scaffold (**unverified**), and tooling.

## 1. Preconditions (stop and ask the human if any fails)
Run `python scripts/check_env.py`. Required: git, git-lfs, gh (authenticated), Python ≥ 3.10. Recommended: uv, opencode, node.
- `gh auth status` must show a logged-in account with `repo` scope. If not: ask the human to run `gh auth login`.
- `git config --get user.name` and `user.email` must be set (the bootstrap commit fails silently without them). If not: ask the human to run `git config --global user.name "..."` and `git config --global user.email "..."`.
- Confirm with the human: **GitHub owner/org + repo name** (default `river-rascals`), **visibility** (private default), **teammate GitHub usernames** (P2, P3).

## 2. Unpack and sanity check
```bash
unzip river-rascals-handover.zip && cd river-rascals
python -m unittest discover -s tests -v      # expect: Ran 28 tests ... OK
python -m compileall -q src tools scripts game
python -c "import json;json.load(open('opencode.json'));json.load(open('backlog/backlog.json'));print('json ok')"
```

## 3. Bootstrap GitHub (dry run first)
```bash
python scripts/bootstrap_github.py --repo OWNER/river-rascals --visibility private --collaborators USER_P2,USER_P3 --dry-run
# review the printed commands, then:
python scripts/bootstrap_github.py --repo OWNER/river-rascals --visibility private --collaborators USER_P2,USER_P3
```
What it does: `git lfs install` → init/commit → create repo + push `main` → labels → milestones → invite collaborators (push permission) → try branch protection (requires `test` check; **private repos on the free plan may refuse – that is OK, record it**) → create 56 issues from `backlog/backlog.json`.

## 4. Post-bootstrap checks (all must pass)
0. Enable the local push guard: `git config core.hooksPath scripts/hooks` (then `python scripts/check_env.py` shows it as OK).
1. `gh run list --limit 3` → CI workflow `ci` is green on `main`. If red: fix with a PR (`fix/ci-…`), never skip.
2. `git lfs ls-files` works; `.gitattributes` contains LFS rules. Add a tiny test: `git lfs track` shows patterns.
3. `.github/CODEOWNERS`: replace `@p1 @p2 @p3` with real usernames (PR).
4. `gh issue list --limit 100 | wc -l` ≥ 56; milestones M0–M5 exist.
5. Create the GitHub Project board (docs/11 §5) and add all issues.
6. Enable Dependabot alerts / secret scanning if the plan allows (Settings → Code security).
7. Record in `docs/12` §10 "Setup log": date, repo URL, protection status, LFS quota note.

## 5. Configure OpenCode for P1
1. Put keys in environment variables (never in files): `GATEWAY_API_KEY` (for the `Greg/*` provider as configured in your OpenCode), optional `GITHUB_TOKEN`.
2. Run `opencode` in the repo root; run `opencode mcp list` and confirm `context7` connects. `blender` only connects when Blender is running with the addon (P2’s job).
3. Verify agents load: open OpenCode’s agent picker and confirm `architect, builder, gameplay, techart` are listed; `@reviewer`, `@qa`, `@debugger`, `@security`, `@docs`, `@release` are invocable.
4. `opencode.json` was loaded and resolved without errors by OpenCode 1.19.4 (10 agents; `reasoningEffort` is normalised into each agent's `options`). If **your** version rejects a key, consult its docs, fix the config in a PR, and note it in `docs/09`. Define the `Greg` provider in your **global** OpenCode config (example: `docs/reference/opencode_global_config.example.jsonc`); personal per-machine overrides go in the git-ignored `.opencode/opencode.jsonc` (`docs/08` §5).

## 6. Start Phase 0 → 1 work (in this order)
| Order | Issue | Agent / effort | Prompt |
|---|---|---|---|
| 1 | F-02, F-03, F-06 | builder / medium | docs/10 §P0.2–P0.3 |
| 2 | S-01 UPBGE version pin (with P2, P3 running on their machines) | gameplay / high | docs/10 §P1.1 |
| 3 | S-02, S-03 raft + oars + smoke test | gameplay / high | docs/10 §P1.2–P1.3 |
Do not start M2 (vertical slice) until all `risk:high` M1 spikes have a recorded decision.

## 7. Day-1 report (post as a GitHub issue comment on F-01 and tell the human)
```
Repo URL / default branch / visibility:
Protection status:
CI status (link):
LFS status + quota note:
Issues/milestones created (counts):
Collaborators invited (names) / accepted:
OpenCode agents verified (list) / MCP status:
Problems + fixes:
Next 3 actions:
```

## 8. Rules of engagement (summary of AGENTS.md)
No force-push, no direct `main` pushes after protection is on, no secrets in git, no unverified claims, ask when blocked. Commit early, in small Conventional Commits.

## 8b. First thing after bootstrap: UPBGE runtime verification
UPBGE is a portable package, so the machine owners' agents verify it locally: see `docs/17_VERIFICATION_STATUS.md` section 3 (checklist and exact commands). Do this during spikes S-01 to S-03.

## 9. Known unknowns (be honest in your reports)
- UPBGE 0.50 (Blender 5.0.1) Python/API behaviour was **not** executed by the authors of this pack: every `bge.*` call is a hypothesis until spike S-02/S-03 passes.
- Blender MCP + UPBGE compatibility is unverified (spike S-04). The package **has** been renamed upstream (`blender-mcp` → `mcp-for-blender`, verified 2026-10-23) and `opencode.json` uses the new name; re-check PyPI before installing in case it changed again.
- Pin the **stable** UPBGE 0.50 (Blender 5.0.1) or 0.44.x only. UPBGE also publishes weekly **alpha** builds (0.52/0.53 at the time of writing): never pin or test the pack against those.
- Exact specs of the ASUS V16 and the mid laptop are unknown; fill `docs/16`.
- `opencode.json` was validated against OpenCode 1.19.4 only (config load + effective permission rules). It has **not** been run against a live model/gateway: model IDs (`Greg/…`) come from the team's gateway catalogue and are unverified here.
