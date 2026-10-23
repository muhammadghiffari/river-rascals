# 09 — Model Routing & Reasoning Effort

Source: the team's gateway catalogue and the earlier routing brainstorm. **Important**: gateway stats (TPS, "success request") measure *request health*, not coding success; the ranking below is a **starting hypothesis** to be validated by the internal benchmark in §6. Multipliers are gateway cost ratios as provided.

## 1. Agents → model → effort
| Agent (mode) | Model | Effort | Temp | Cost × | Use for |
|---|---|---|---|---|---|
| `architect` (primary) | Greg/gpt-6-astra | **high** (xhigh only for a blocking design) | 0.2 | 42 | PRD/GDD/TDD changes, trade-offs, task breakdown, hard decisions |
| `builder` (primary, **default**) | Greg/deepseek-v4-pro | **medium** | 0.2 | 1.15 | infra, CI, tools, core logic, tests, refactors, scripts |
| `gameplay` (primary) | Greg/kimi-k3 | **high** (medium for routine features) | 0.2 | 6 | complex features, UPBGE glue, physics integration, co-op, UI logic |
| `techart` (primary) | Greg/deepseek-v4-pro (+ Blender MCP) | **medium** | 0.3 | 1.15 | bpy scripts, procedural assets, rigs, shaders, validators |
| `debugger` (sub) | Greg/gpt-6-astra | **high** | 0.1 | 42 | only after 2 failed fix attempts or cross-module root causes |
| `reviewer` (sub, read-only) | Greg/kimi-k3 | **high** | 0.1 | 6 | independent review (different family than builder/techart) |
| `qa` (sub) | Greg/deepseek-v4-flash | **low** | 0.1 | cheap | run tests/smoke, triage, unit tests, lint fixes |
| `security` (sub, read-only) | Greg/gpt-6-astra (2nd opinion: Greg/claude-opus-5-5) | **high** | 0.1 | 42 | pre-release audit, MCP/permissions, licences |
| `docs` (sub) | Greg/glm-5.2 | **low** | 0.3 | 1.25 | docs, changelog, release notes |
| `release` (sub) | Greg/gpt-6-astra | **high** | 0.1 | 42 | GO/NO-GO gate |
Model IDs are exactly as in the gateway catalogue (`Greg/…`). Alternatives to benchmark: `Greg/gpt-6-sol` (×30) and `gregv4/gpt-6.1-sol` (×10) — **different provider IDs, test separately**; `Greg/deepseek-v4.1-flash` for iterative error-fix loops; `Greg/glm-5.3-flash`/`Greg/kimi-k2.8` for fast visual iteration; `Greg/claude-opus-5-5` (×32, slow 21.6 TPS) for deep review/diagram/screenshot analysis.

## 2. Effort ladder (how to choose)
| Effort | When | Examples |
|---|---|---|
| low | mechanical, well-specified | run tests, rename, docs, lint |
| medium | normal implementation with clear spec | new core function + tests, script, CI fix |
| high | ambiguity, multi-module, physics/gameplay feel, reviews | raft physics glue, co-op input, release gate |
| xhigh | rare, blocking, architecture-level | engine-version decision analysis, networking design |
`reasoningEffort` is set per agent in `opencode.json`. Verified with OpenCode 1.19.4: unknown agent keys are normalised into the agent's `options` (so it is passed through to the provider SDK). Whether the **gateway** honours it is unverified; if it ignores or rejects it, switch to the provider's own parameter name per the OpenCode provider docs and record it here. Access control uses the `permission` map (the older `tools` map is deprecated). Override ad hoc by switching agent, not by editing config.

## 3. Routing rules
1. Start with `builder`. Switch to `gameplay` when the task touches `bge` glue, physics feel, input/co-op, or exceeds ~3 files of new logic.
2. **Two-strike rule**: two failed attempts at the same problem ⇒ `debugger`. Two failed at a design question ⇒ `architect`.
3. **Independent review**: implementer ≠ reviewer model family (deepseek ↔ kimi). `risk:high` PRs (physics core, save format, build/release, MCP config, co-op) also get `security` or `architect` review.
4. Never run `architect`/`debugger`/`release` for edits < 20 lines or for formatting.
5. Cheap-first for exploration: `qa`/`builder` locate and summarise; escalate with the summary, not the whole repo.
6. Art: `techart` produces; a human (P2) approves visuals — models cannot judge "cozy".

## 4. Per-phase routing
| Phase | Primary | Companion / reviewer |
|---|---|---|
| P0 Foundation & governance | builder (infra), architect (docs reconcile) | reviewer |
| P1 Tech spikes | gameplay (high) | architect for decisions; reviewer |
| P2 Vertical slice | gameplay (core), builder (routine), techart (assets) | reviewer, qa |
| P3 Assets & animation | techart | reviewer (checklist), human art direction |
| P4 Gameplay systems | gameplay | architect (design), reviewer |
| P5 Audio/VFX/UI polish | gameplay (audio system, UI), techart (VFX, shaders) | qa |
| P6 QA & performance | qa (triage), builder (fixes) | debugger for hard bugs, gameplay for physics |
| P7 Security & release | security + release | builder for fixes |

## 5. Budget guardrails
Weekly cap suggestion (adjust): Astra-class calls ≤ 10 % of tokens; kimi-k3 ≤ 30 %; the rest on deepseek/glm/flash. Track in a `docs/reports/cost_log.md` (weekly: tokens/cost per agent). If Astra usage exceeds cap, review whether tasks were mis-routed.

## 6. Internal benchmark to confirm/replace this table (run in M1, ~1 day)
Same repo snapshot, same instructions, same tools for each candidate. Tasks: (T1) implement `CheckpointTracker` extension with tests; (T2) fix a seeded bug in `river.project` boundary case; (T3) write a `validate_scene.py` checker; (T4) design review of hazards spec; (T5) glue component from spec (unverifiable in CI ⇒ reviewed by human); (T6) bpy script generating a prop within budget.
| Metric | Weight |
|---|---|
| Acceptance tests pass | 35 % |
| Correctness & regression | 25 % |
| Patch quality in review | 15 % |
| Tool use & execution accuracy | 10 % |
| Cost | 10 % |
| Latency | 5 % |
Record human interventions, time-to-green, gateway cost. Update §1 via PR with the data. **Do not treat 100 % request success as coding success.**

## 7. Reference notes
The team's earlier brainstorm document cites a game-construction benchmark for coding agents (SWE-Game, arXiv, Sept 2026, Godot tasks; **not independently re-verified by the authors of this pack**) reporting that even top agents scored below 60/100 on game construction categories, with missed requirements and wrong gameplay logic common — evidence for our **runtime verification + review gates** approach rather than trusting one unattended agent.
