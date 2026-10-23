# 02 — Game Design Document (GDD)

## 1. Elevator pitch
"Otter friends, one wobbly raft, a river full of surprises. Paddle together, dodge boulders, grab golden fish, and try not to fall in — you will."

## 2. Core loop
Paddle & steer → read the river → dodge/hit things (funny feedback) → collect coins & golden fish → reach checkpoints (repair, save) → finish chapter → spend coins in the Workshop (raft tiers, cosmetics) → next chapter.

## 3. Controls
| Action | Keyboard (solo) | Gamepad (per player) |
|---|---|---|
| Left oar stroke (hold) | A | Left trigger (solo) / A button (co-op, side by seat) |
| Right oar stroke (hold) | D | Right trigger (solo) / A button (co-op) |
| Back-paddle modifier | S (hold) | Left stick down / B held |
| Sweep/steer fine control | — | Left stick X biases thrust ±20 % (accessibility option off by default) |
| Emote wheel | 1–4 | D-pad |
| Interact / throw rope | E | X |
| Pause | Esc | Start |
Keyboard co-op (2 players): P1 `A/D/S`, P2 `←/→/↓`. Remap in settings (FR-21).

**Stroke model**: press & hold = oar dips (0.15 s, no thrust) → pulls (thrust ramps in 0.2 s, max 0.9 s) → release = recover (0.25 s). Mashing is inefficient; rhythm wins. Values in `src/rr/core/oar.py`.

## 4. The raft
- Footprint 3.2 × 2.4 m, 4 seats (2 per side), 6 buoyancy sample points.
- Players are **seated in slots** (not free-roaming) → avoids physics-on-moving-platform issues. Players can be **knocked overboard** by hazards/bumps (becomes a floating swimmer with a simple capsule), swim toward the raft, **climb back** at a rail slot, or be rescued with a thrown rope.
- Hull integrity (hearts): 5 on T1. Damage by impact speed. Repair at checkpoints. At 0 hearts: "sink gag" → respawn at last checkpoint with 1.5 s invulnerability; coins kept, time not penalised heavily.
- Tiers: **T1** logs (starter) · **T2** planks+barrels (+1 heart, +10 % thrust) · **T3** expedition (+2 hearts, +lantern, better stability). Costs: T2 150 coins, T3 400 coins.

## 5. Camera
Chase camera behind raft with look-ahead along river tangent, smoothed; pulls back slightly with speed; auto-avoids banks; shake on impacts (settings-scalable); dedicated cinematic cameras at waterfall and finish.

## 6. Chapters
| # | Name | Mood | Length | Hazards introduced | New mechanic |
|---|---|---|---|---|---|
| 1 | **Sleepy Creek** | sunny, gentle | 4 min | rocks, buoys, floating logs, current booster | paddling, steering, checkpoints |
| 2 | **Pine Rapids** | energetic | 5–6 min | rapids turbulence, branching channels, beaver dam | cooperation on narrow gaps |
| 3 | **Misty Canyon** | mysterious fog | 6 min | log gates, narrow walls, **waterfall drop** (small), whirlpool | timing, rope rescue |
| 4 | **Lantern Lagoon** | calm night | 5 min | lily pads (slow zones), fireflies puzzle path, heron | light-guided navigation |
| 5 | **Thunder Falls** | stormy finale | 7–8 min | all hazards, big waterfall, storm waves | everything together |
Each chapter: 3–5 checkpoints, 40–80 coins, 3 golden fish (hidden/risky spots), 1 cosmetic reward, 2 "moments" (scripted funny events, e.g. bear catches a fish and tosses it onto the raft).

## 7. Hazards and rules
| Hazard | Behaviour | Counterplay |
|---|---|---|
| Rock | Impact damage ∝ speed² above 1.5 m/s | steer early, back-paddle |
| Log | moving obstacle; low damage; can push raft | angle through gaps |
| Rapids | noisy lateral force ±150 N, speed +30 % | straight line, sync strokes |
| Current booster | +1.5 m/s for 3 s | aim for it (reward) |
| Whirlpool | radial pull + torque; escape needs both sides pulling | back-paddle opposite side |
| Waterfall drop | scripted: lock to rails 2 s, camera shake, splash, brief swim chance | brace emote gives bonus coins |
| Beaver dam | gap in middle | align with gap |
| Lily pads | drag ×2 zone | go around |

## 8. Co-op & AI
- Drop-in/drop-out: press A on an unused pad to join; a free oar seat is taken; leaving hands the oar to AI.
- **AI crew** policy: stays in rhythm at 60 % efficiency, avoids over-correction, follows a "preferred line" along river centre with random mistakes (comedic).
- Local: shared screen, shared raft = no split-screen needed (huge cost saver).
- Stretch: online (host-authoritative) — see TDD §12.

## 9. Progression & economy
Coins from chapters (~60 avg), golden fish (3 per chapter) unlock cosmetics, best times saved per chapter. No microtransactions, no timers, no loot boxes.

## 10. Difficulty & assists
Base difficulty tuned for first-time players to finish Ch1 with 0–2 sinks. Assist toggles: **Calm River** (−25 % flow), **Sturdy Raft** (+2 hearts), **No Damage**, **Auto Align** (gentle steering help), **Big Prompts**. Assists never lock achievements/cosmetics.

## 11. UI/UX
- HUD (top): hull hearts, coin counter, golden fish (0/3), progress bar with checkpoint flags. Join prompts bottom corners.
- Style: rounded, chunky, hand-lettered; 9-slice panels; large icons; text ≥ 24 px at 1080p.
- Menus: Main (Play, Workshop, Settings, Quit) · Chapter Select · Pause (Resume, Settings, Restart from checkpoint, Quit).
- Feedback hierarchy: sound + animation + small camera shake before text.

## 12. Narrative (light)
Tiny story told in-engine: the Rascals follow a legendary golden fish downstream to the Thunder Falls festival. 5 short scripted beats, no dialogue (chirps + visual gags) → no VO, no translation burden except UI text.

## 13. Art direction (summary — full in 04)
Soft low-poly, saturated warm palette, toon 2-band shading, gentle outlines optional, water with readable foam, strong silhouettes, golden-hour default lighting.

## 14. Audio direction (summary — full in 06)
Acoustic folk (ukulele, guitar, marimba, fiddle), adaptive stems, tactile wooden/water SFX, cute otter chirps, loud-but-friendly feedback.

## 15. Tutorial (Ch1 beats)
1. Both oars tutorial prompt → 2. Steer around a buoy line → 3. Back-paddle to avoid a rock → 4. Coin line → 5. Checkpoint teaches repair → 6. Join prompt demo for a second player.

## 16. Playtest questions (P3 owns)
Is steering understandable in 30 s? Is failure funny rather than annoying? Is co-op communication happening? Where do players get stuck? Does anything look unreadable on the mid-spec laptop?
