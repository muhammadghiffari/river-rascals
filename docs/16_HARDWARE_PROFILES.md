# 16 — Hardware Profiles & Machine Status
Authors did **not** have the exact specs; each owner fills their row in week 1 (F-04/F-05).
Tiers are defined in `13_QA_PERFORMANCE_PLAN.md` §2. **P3 is Tier C** (Linux floor-spec, iGPU, 720p/native); the Tier B 1080p baseline belongs to the separate Acer Aspire machine and Tier A to the ASUS V16. This classification is aligned with upstream `main` post-#65 (PR #65/#67); the filled F-04/F-05 profile rows live there.

| Field | P1 — Acer Aspire A515-45, Windows (Tier B) | P2 — ASUS V16 (Tier A) | P3 — HP ZBook 14 G2 (Tier C, Linux floor-spec) |
|---|---|---|---|
| Model | | ASUS V16 (exact model: ) | |
| OS / version | | | |
| CPU | | | |
| GPU (dedicated/iGPU) + driver | | | |
| VRAM / shared | | | |
| RAM | | | |
| Storage free (SSD/HDD) | | | |
| Display res/refresh | | | |
| Power mode used for tests | plugged-in, high performance (always record) | | |

## Baseline scenes (record in each machine's build)
These 1080p rows are the **Tier B (P1 Aspire)** and Tier A baselines and are measured on those machines; P3 (Tier C) targets the optional Tier C goal instead (Low, 720p, ≥ 24 fps avg — `13` §2) and never runs 1080p.
| Scene | Preset | Res | fps avg | fps min | notes |
|---|---|---|---|---|---|
| Empty scene | Low | 1080p | | | |
| 100k tris static | Low | 1080p | | | |
| 250k tris + 1 sun shadow | Low/Med | 1080p | | | |
| Raft + water + 20 props (S-07) | Low/Med/High | 1080p | | | |

## Interpretation rules
- If Tier B average < 30 fps on the 250k-tri scene at Low ⇒ reduce scene budgets in `04` §4 and set 720p/75 % default for Low.
- Tier C (P3): optional target is ≥ 24 fps avg at 720p on Low (`13` §2).
- Laptops throttle: test plugged in, record temps if possible, run ≥ 5 minutes.

## MCP status (P2 fills)
| Item | Value |
|---|---|
| Blender/UPBGE version | |
| MCP package + version | |
| Addon works in UPBGE? | |
| Fallback used? | |
| Issues/workarounds | |
