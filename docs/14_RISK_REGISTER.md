# 14 — Risk Register
Scoring: Likelihood (L) and Impact (I) 1–5; Score = L×I. Review weekly (R3).

| ID | Risk | L | I | Score | Mitigation | Owner | Trigger/Contingency |
|---|---|---|---|---|---|---|---|
| R-01 | UPBGE 0.50 API/behaviour differs from assumptions; instability on Blender 5 base | 4 | 4 | 16 | Spike S-01/S-02 early; keep 0.44 fallback; core/glue split limits blast radius | P1 | If 0.50 blocks by M1 end ⇒ switch to 0.44 |
| R-02 | Raft physics unstable/not fun | 3 | 5 | 15 | Spec + tests + scenarios PH-01..09; clamps; righting torque; tuning sessions | P1 | Escalate debugger; simplify to kinematic-assisted raft |
| R-03 | Blender MCP incompatible with UPBGE or renamed/changed | 3 | 3 | 9 | Portable assets rule; author in vanilla Blender; bpy scripts without MCP | P2 | Drop MCP, use scripts via CLI |
| R-04 | Standalone export/packaging fails | 3 | 5 | 15 | Spike S-06 in M1; try both methods | P3 | Ship as "UPBGE + .blend" bundle with launcher script |
| R-05 | Tier B performance below target | 4 | 4 | 16 | Budgets, presets, early baselines, LODs, fake shadows, render scale | P3/P1 | Lower visual scope, 720p default on Low |
| R-06 | LFS quota exhausted / repo bloat | 4 | 3 | 12 | Keep raw files out; prune; monitor; data pack | P1 | Move LFS to alternate host |
| R-07 | `.blend` merge conflicts / lost work | 3 | 4 | 12 | Locks, small files, backups, ownership map | P1 | Restore from LFS history/bundle |
| R-08 | AI-generated art/audio licence issues | 3 | 5 | 15 | PROVENANCE, terms check, prefer CC0/own-made | P1 | Replace asset; audit R-02 task |
| R-09 | Agent hallucination / unverified claims | 4 | 3 | 12 | Verify-before-claim rule, VERIFY markers, independent review, smoke tests | all | Add test; escalate |
| R-10 | Model cost overrun (Astra ×42) | 3 | 3 | 9 | Routing rules, weekly cost log, caps | P1 | Downshift defaults |
| R-11 | Scope creep ("AAA") | 5 | 4 | 20 | PRD tiers, cut order, one-in-one-out rule | P1/P3 | Cut list |
| R-12 | Team availability / burnout | 3 | 4 | 12 | 10–15 h cap, buffer weeks, clear ownership | all | Re-plan |
| R-13 | Character art quality from LLM tooling is weak | 4 | 3 | 12 | Human cleanup, CC0 bases, simpler style | P2 | Switch to simpler stylisation |
| R-14 | Gamepad/co-op input issues in UPBGE | 3 | 3 | 9 | Spike S-08, abstraction layer | P1 | Keyboard-only co-op for v1 |
| R-15 | Secret leakage (tokens in repo/config) | 2 | 5 | 10 | env vars, ignore rules, CI grep, security review | P1 | Rotate tokens immediately |
| R-16 | Blender MCP socket abused (unauthenticated) | 2 | 4 | 8 | localhost only, stop when idle, isolated session | P2 | Disable MCP |
| R-17 | Trademark/name conflict for title | 3 | 3 | 9 | Check before publishing; keep "River Rascals" as working title | P3 | Rename |
