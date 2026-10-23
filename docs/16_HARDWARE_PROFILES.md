# 16 — Hardware Profiles & Machine Status
Authors did **not** have the exact specs; each owner fills their row in week 1 (F-04/F-05).

| Field | P1 machine | P2 — ASUS V16 (Tier A) | P3 — mid-spec laptop (Tier B) |
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
| Scene | Preset | Res | fps avg | fps min | notes |
|---|---|---|---|---|---|
| Empty scene | Low | 1080p | | | |
| 100k tris static | Low | 1080p | | | |
| 250k tris + 1 sun shadow | Low/Med | 1080p | | | |
| Raft + water + 20 props (S-07) | Low/Med/High | 1080p | | | |

## Interpretation rules
- If Tier B average < 30 fps on the 250k-tri scene at Low ⇒ reduce scene budgets in `04` §4 and set 720p/75 % default for Low.
- Laptops throttle: test plugged in, record temps if possible, run ≥ 5 minutes.

## MCP status (P2 fills)
| Item | Value |
|---|---|
| Blender/UPBGE version | |
| MCP package + version | |
| Addon works in UPBGE? | |
| Fallback used? | |
| Issues/workarounds | |
