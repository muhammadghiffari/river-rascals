# 07 — Physics Specification (authoritative)

All values are **initial tunables** derived on paper and validated only by the unit tests in `tests/test_core.py` (e.g. equilibrium ≈ m·g at 0.12 m draft). They MUST be validated and tuned in UPBGE during spikes S-02/S-03 and task V-02.

## 1. Conventions
Units: metres, kilograms, seconds, newtons. Axes: +X right, +Y forward, +Z up (Blender). Gravity −9.81 m/s². Fixed 60 Hz logic & physics. Water level default z = 0 (property `water_level` on `RiverRoot`).

## 2. Raft rigid body
| Property | Value | Rationale |
|---|---|---|
| Collider | box 2.4 (X) × 3.2 (Y) × 0.4 (Z) m, margin ≥ 0.04 | stable, cheap |
| Mass | 300 kg | readable inertia |
| Yaw inertia (approx.) | m(L²+W²)/12 ≈ 400 kg·m² | for tuning torque/drag |
| Linear/angular damping (Bullet) | 0.05 / 0.3 | extra stability |
| Sleep | disabled | never sleeps mid-river |
| Draft target | 0.12 m | equilibrium |
Lock rotation tendencies: add a **righting torque** if roll/pitch > 20° (soft limit) so it never flips.

## 3. Buoyancy (rr.core.buoyancy)
6 sample points at (±1.0, −1.4/0/+1.4, −0.2 relative to centre). Per sample: `F = clamp(k·depth − c·v_z, 0, F_max)` upward at the sample point (force + torque about centre of mass).
`k = 4000 N/m, c = 450 N·s/m, F_max = 1500 N` (derivation: 6·k·0.12 ≈ m·g; c ≈ 0.5 of critical damping for 50 kg per sample).
Water height: `rr.core.waves.wave_height(x,y,t,base)` — sum of 3 sines, total amplitude ≤ 0.095 m; **the water shader must reproduce the same function** (S-07) so visuals match physics.

## 4. Drag and current
Relative velocity `v_rel = v_raft − flow(x,y)` in raft-local axes. Quadratic drag: forward `C_y = 90 N·s²/m²`, lateral `C_x = 400` (keel effect), yaw drag `250 N·m·s/rad`; scaled by submerged fraction. Flow: `rr.core.river.River.flow_at` — centreline tangent × `base_speed` × profile `1 − (1−edge)·r²` (r = |lateral|/half-width), zero outside banks. Defaults: base_speed 2.0 m/s (Ch1), edge 0.35. Target terminal speed with two oars ≈ flow + 1.5–2.5 m/s relative.

## 5. Collision groups
| Group | Bit | Collides with |
|---|---|---|
| Raft | 1 | Static, Hazard, Collectible(trigger), Swimmer |
| Static (banks, rocks) | 2 | Raft, Swimmer, Log |
| Hazard volumes/triggers | 3 | Raft, Swimmer (sensor only) |
| Collectible (sensor) | 4 | Raft |
| Swimmer (overboard otter) | 5 | Static, Raft (soft) |
| Log (dynamic obstacle) | 6 | Static, Raft |
Players on the raft are **not** physics bodies (seated slots, parented). Collectibles/hazard zones use **sensors/ghost objects**, not solid colliders.

## 6. Oars (rr.core.oar)
Stroke: DIP 0.15 s → PULL (ramp 0.2 s, max 0.9 s) → RECOVER 0.25 s. Thrust: `max_thrust = 350 N` per oar along +Y at the raft centre plus torque `side·lever·thrust` (lever 1.0 m; right oar ⇒ +Z torque ⇒ turns left). Back-paddle: direction −1 ⇒ negative thrust. Co-op: up to 4 oars (2 per side) with the same code.
Targets: two oars straight from rest ⇒ ≥ 2.0 m/s relative in ≤ 6 s; one side only ⇒ 180° turn in ≈ 5–7 s; recover/dip makes continuous mashing ≈ 60–70 % as effective as rhythmic holding.

## 7. Hazards
| Hazard | Law | Initial values |
|---|---|---|
| Rock impact | `damage = 0` if v ≤ 1.5, else `ceil((v−1.5)/1.2)` hearts (cap 2/hit); impulse restitution 0.2 | invulnerable 0.8 s after hit |
| Rapids | lateral noise force `A·n(t,x)` | A = 150 N, flow ×1.3 |
| Booster | add velocity along flow | +1.5 m/s over 3 s |
| Whirlpool | radial inward `F_r = s·(1 − d/R)` + tangential torque | R = 6 m, s = 600 N, torque 250 N·m |
| Log | dynamic cylinder, mass 80 kg, buoyant | drift with flow |
| Lily pads | drag ×2 inside zone | |
| Waterfall | scripted: switch to kinematic path for 2 s, restore dynamic at splash height with velocity clamp ≤ 4 m/s | avoids explosive contacts |

## 8. Stability rules (apply always)
1. Never apply forces larger than `F_max_total = 6·1500 N` per tick; clamp velocities (`|v| ≤ 12 m/s`, `|ω| ≤ 3 rad/s`).
2. Use box/convex colliders; avoid thin triangle-mesh colliders for dynamic bodies; bank meshes get ≥ 0.3 m thickness.
3. Apply forces once per physics step (logic = physics = 60 Hz). VERIFY accumulation semantics in S-02.
4. After teleports/respawns zero velocities and wait 2 frames before enabling forces.
5. Keep mass ratios within 1:20 for interacting dynamic bodies.
6. Log `|v|`, `|ω|`, max sample depth each second in debug builds.

## 9. Test scenarios (implement as scripted smoke tests in V-02)
| ID | Scenario | Pass criteria |
|---|---|---|
| PH-01 | Idle in still water 60 s | bob ≤ ±5 cm, no drift > 0.1 m |
| PH-02 | Idle in current, centre | speed within 15 % of flow after 8 s |
| PH-03 | Both oars held 10 s | ≥ 2.0 m/s relative; no yaw drift > 5° |
| PH-04 | Right oar only 5 s | turns left ≥ 90° and ≤ 200° |
| PH-05 | Rock hit at 3 m/s | no tunnelling; damage per table; no spin > 3 rad/s |
| PH-06 | Hit bank at 4 m/s | bounces back into river; no stuck > 2 s |
| PH-07 | Whirlpool escape with 2 oars | escape in ≤ 10 s |
| PH-08 | 10-minute soak with random oars | no NaNs, no flip, speed bounded |
| PH-09 | Waterfall drop ×50 | 0 stuck/launch events |

## 10. Debug & tuning
Debug overlay (F3): speed, flow, draft, sample forces, oar phases, tick rate. Tunables loaded from `game/settings/physics.json` (create in V-02) with hot-reload key F5 in debug builds.

## 11. Paper-check of targets (headless, NOT UPBGE)
Method: 1-D forward + yaw integration at 60 Hz using the real `rr.core.oar.Oar`, mass 300 kg, yaw inertia 400, drag C_y 90, yaw drag 250 (section 4). Encoded in `tests/test_physics_targets.py`.
| Target | Result | Verdict |
|---|---|---|
| PH-03 both oars held, still water | first >= 2.0 m/s at ~2.1 s; ~2.2 m/s at 10 s | passes but **marginal** (stroke cycle makes speed oscillate near 2.0): re-tune in UPBGE |
| PH-04 right oar only 5 s | ~168 deg; 180 deg at ~5.3 s | consistent with 90-200 deg and 5-7 s |
This does not validate Bullet behaviour, buoyancy coupling, sampling-point torque or waves; those remain spike S-02/S-03/V-02 work.
