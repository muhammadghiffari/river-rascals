# 05 — Animation Specification

## 1. Technical standard
30 fps authoring · action names `<Rig>|<clip>` e.g. `Otter|paddle_R_pull` · root bone stays at origin (no root motion) · all clips loop-safe where marked · bone names English, `.L/.R` suffix · apply armature scale = 1 · export-free (UPBGE reads `.blend` actions directly).
**UPBGE playback**: `KX_GameObject.playAction(name, start, end, layer, priority, blendin, play_mode, layer_weight, ipo_flags, speed)` (VERIFY signature in S-01); layers: 0 = locomotion/pose, 1 = oar action, 2 = reactions/emotes (additive-style via layer weight), 3 = face texture swap. Blend-in 3–6 frames. Prefer GPU skinning only after S-01/B-03 test.

## 2. Otter rig (≤ 25 bones)
`root → hips → spine → chest → neck → head(+jaw)`, `shoulder.L/R → upper_arm → forearm → hand(paw)`, `thigh.L/R → shin` (seated pose uses only hips/thighs), `tail.01–03` (chain), `ear.L/R` (optional). Face: **texture-swap eyes/mouth** (no shape keys) via UV offset on a face quad/material property → cheap and LOD-friendly.
Oar attach: `Socket_Oar.L/.R` on hands; the oar itself is animated by the raft (`RF_Oar` pivot at oarlock) so strokes read even if character animation is simple.

## 3. Clip list (priority P0 = vertical slice; P1 = alpha; P2 = beta)
| Clip | Frames | Loop | Prio | Notes |
|---|---|---|---|---|
| Otter\|seated_idle | 60 | yes | P0 | breathing, tail sway |
| Otter\|paddle_L_dip | 6 | no | P0 | oar enters water |
| Otter\|paddle_L_pull | 20 | no (held, clamp) | P0 | torso rotates |
| Otter\|paddle_L_recover | 8 | no | P0 | |
| Otter\|paddle_R_dip / pull / recover | 6/20/8 | no | P0 | mirror of L |
| Otter\|paddle_back_L / R | 20 | no | P1 | back-paddle |
| Otter\|panic | 24 | yes | P0 | arms up, eyes wide |
| Otter\|celebrate | 36 | no | P0 | paws up, tail wag |
| Otter\|bump_react | 12 | no | P0 | lean + recover |
| Otter\|fall_overboard | 18 | no | P1 | flung out |
| Otter\|swim_loop | 30 | yes | P1 | doggy paddle |
| Otter\|climb_in | 24 | no | P1 | pull up onto rail |
| Otter\|rope_throw | 20 | no | P1 | |
| Otter\|rope_catch | 16 | no | P1 | |
| Otter\|emote_wave / cheer / laugh / brace | 24/30/30/18 | no | P2 | |
| Otter\|sit_sad | 40 | yes | P2 | after sinking |
| Raft\|flag_flutter | 40 | yes | P1 | |
| Raft\|damage_pop | 10 | no | P1 | board jumps |
| Bear\|fish_idle / catch / toss | 80/30/30 | idle loop | P1 | Ch2 gag |
| Beaver\|carry_loop / chop | 40/24 | yes | P1 | |
| Heron\|stand_idle / fly_off | 90/40 | idle loop | P2 | |
| Frog\|idle_croak / jump | 60/20 | idle loop | P2 | |
| Duck\|swim_bob | 30 | yes | P2 | one bone |
| Fish\|swim | 24 | yes | P2 | |
| Props: Banner\|flutter, Waterwheel\|spin, Lantern\|sway | 40/60/60 | yes | P1 | |
Stroke clips are **driven by the oar state machine phase** (`DIP→PULL→RECOVER`); the pull clip is held at its last pose while the button is held; recover plays on release.

## 4. Procedural motion (cheap, physics-driven)
Raft sway comes from physics (no clip). Characters: add small tilt based on raft angular velocity (in glue, clamp ±8°). Camera shake via damped noise. Oars: rotate pivot by oar phase (dip −25°, pull sweep, recover lift).

## 5. Quality bar
Exaggerated, readable poses, anticipation on impacts, overlapping tail/ears, no foot sliding (seated), no clip longer than needed, mirrored clips verified. Deform test: play every clip at 2× speed and check mesh intersections.

## 6. Workflow & ownership
P2 owns rig and clips. Agent (`techart`) can script rigging (bone creation, weights from automatic weights then cleanup) and generate **keyframe-based clips via bpy** (pose libraries); human polishes timing. Validate: `tools/validate_assets.py` + manual playback test scene `game/anim_test.blend`.

## 7. Animation prompt templates (Agent: `techart`, Model: deepseek-v4-pro/medium; hard rigging bugs → kimi-k3/high)
**Rig prompt**
```text
Open assets/characters/CH_OtterBase.blend. Create an armature named Otter following docs/05_ANIMATION_SPEC.md §2 (<=25 bones, names exactly as listed).
Parent the mesh with automatic weights, then report vertices with >4 influences and fix. Add Socket_Oar.L/.R empties parented to the hand bones.
Create a test pose set (A-pose, seated pose) and verify no collapsed geometry. Report bone count, weight issues fixed, and screenshots of both poses.
```
**Clip prompt (repeat per clip)**
```text
Create action "Otter|<clip>" for armature Otter: <frames> frames at 30 fps, loop=<yes/no>.
Motion description: <describe: e.g. torso rotates 20 degrees toward the pulling side, arms sweep back, tail counter-sways>.
Rules: root bone does not move; hold key poses with ease-in/out; first and last frame match if looped; no keyframes on bones that don't move.
Verify by stepping through frames and checking mesh intersections. Report key pose frame numbers and any problems.
```
**Integration prompt (Agent: gameplay, kimi-k3/medium)**
```text
Add a component PlayerAnimator in src/rr/glue that maps OarPhase (core) to playAction calls per docs/05 §1 layer scheme, with blend-in values in args.
Keep the mapping table in src/rr/core/anim_map.py (pure, unit-tested). Mark bge calls VERIFY until run in UPBGE.
```
