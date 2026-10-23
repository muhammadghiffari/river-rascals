# 01 — Product Requirements Document (PRD)
Working title: **River Rascals** · Version 1.0 (handover) · Owners: P1 (tech), P3 (design) · Status: approved for M0/M1

## 1. Vision
A **cozy-chaotic** co-op rafting adventure. Players paddle a wobbly raft down charming rivers, laughing at near-misses, collecting treasures and reaching the finish together. It must be instantly readable, forgiving, funny, and beautiful in a stylised low-poly way.

### Design pillars
1. **Cozy chaos** – failure is funny, never punishing; warm visuals/audio.
2. **Teamwork in your hands** – each paddler controls one side; coordination = fun (and comic miscoordination).
3. **Readable physics** – exaggerated, stable, predictable; the raft never "explodes".
4. **Short, replayable runs** – 4–8 minute chapters, drop-in/drop-out.
5. **Original charm** – own characters (otters), own world, own music.

### Reference and differentiation
Inspired by the co-op rafting genre exemplified by *Oar'some Adventures* (cozy/chaotic rafting for 1–8 players, per its public store listing). We differ by: otter cast, chapter structure, assist modes, raft upgrade/cosmetic progression, adaptive music, and a **local-first** co-op scope (1–4 players on one PC). We do not copy names, art, characters, level layouts, audio or text.

## 2. Audience & platform
- Players 8+ (PEGI 3–7-style content), families, friends groups, casual streamers.
- **Windows 10/11 x64 (primary)**, Linux x64 (secondary, best effort). macOS: out of scope.
- Input: keyboard (shared), gamepads (up to 4). Mouse for menus.
- Languages: English (default), Bahasa Indonesia.

## 3. Scope tiers
| Tier | Content | Target |
|---|---|---|
| **MVP / Vertical slice (M2)** | Ch1 Sleepy Creek complete; raft T1; otter; rocks, logs, coins, golden fish; checkpoints; HUD; save; solo + keyboard 2P | week 7 |
| **Alpha (M3)** | Ch1–3; local co-op 2–4 with join/leave; AI crew; whirlpool + waterfall; upgrades/cosmetics; adaptive music; VFX v1; EN/ID | week 13 |
| **Beta (M4)** | Ch1–5; night + storm chapters; accessibility; balance; full audio; intro/credits | week 17 |
| **v1.0 (M5)** | Release candidate on 2+ machines, licence-clean | week 20 |
| **Stretch** | Online co-op (host-authoritative), photo mode, workshop-style raft paint, extra chapters | post v1.0 |

Honest scope note: the phrase "AAA" in the kickoff is interpreted as **AAA-grade process** (specs, CI, reviews, profiling, QA gates) with **indie-scale content** that three people plus AI can deliver. UPBGE, a small community engine, and a 3-person team cannot ship AAA content volume or fidelity.

## 4. Functional requirements (FR) — each has acceptance criteria (AC)
| ID | Requirement | AC |
|---|---|---|
| FR-01 | Raft floats stably on a wave-displaced water surface | At rest bobs ≤ ±5 cm; no drift > 0.1 m/min without current; 10 min stable |
| FR-02 | River current moves raft and objects along the centerline | Idle raft in centre reaches ≈ flow speed ±15 % within 8 s |
| FR-03 | Each oar controlled by one input; stroke = dip → pull → recover | Right oar yaws raft left, left oar yaws right; both = straight |
| FR-04 | Solo play controls both oars; co-op assigns one oar/player; AI crew fills empty oars | 1–4 humans + AI to fill 4 slots |
| FR-05 | Back-paddle modifier reverses thrust | Raft decelerates and reverses |
| FR-06 | Obstacles: rocks, logs, buoys with impact feedback | Impact speed → damage curve; audio+VFX fire |
| FR-07 | Hull integrity with repair at checkpoints | 3 damage visual states; never hard-fail; "sink" = respawn at checkpoint |
| FR-08 | Overboard: players can be knocked off, swim, climb back | Return within ≤ 8 s; rope-throw rescue speeds it |
| FR-09 | Hazards: current booster, whirlpool, rapids turbulence, waterfall drop, beaver dam | Each chapter lists its hazard set (GDD §6) |
| FR-10 | Collectibles: coins, golden fish, cosmetic unlocks | Counters on HUD; persisted |
| FR-11 | Checkpoints and respawn | Respawn ≤ 3 s at last checkpoint with grace period |
| FR-12 | Chapters 1–5 each completable in 4–8 min | Verified by playtest timings |
| FR-13 | HUD: hull, coins, fish, progress bar, player join prompts | Readable at 1080p and 720p; scale option |
| FR-14 | Menus: main, pause, settings (audio, video preset, language, controls), chapter select | All navigable by gamepad and keyboard |
| FR-15 | Save/load: progress, currency, cosmetics, best times, settings | Atomic writes; corrupt-file recovery; versioned migration |
| FR-16 | Progression: raft tiers T1–T3 and cosmetics | Coins spent in a workshop UI |
| FR-17 | Quality presets Low/Medium/High | Presets change render scale, shadows, 2D filters, particle density |
| FR-18 | Adaptive music (calm/rhythm/danger stems) | Crossfade ≤ 2 s without pops |
| FR-19 | Localization EN/ID | Runtime switch, no clipped text |
| FR-20 | Assist options: slower river, extra hull, no-damage, big prompts | Toggles in settings, saved |
| FR-21 | Input remap and gamepad hot-plug | Remap persisted; hot-plug does not crash |
| FR-22 | Smoke-test mode for automation | `--smoke` run returns JSON with fps and distance |
| FR-23 | Local diagnostics bundle (logs, settings, hardware) | One menu button; no network upload |
| FR-24 | Tutorial teaches paddle, steer, avoid, cooperate | 3 new testers pass in ≤ 3 min |

## 5. Non-functional requirements (NFR)
| ID | Requirement | Target |
|---|---|---|
| NFR-01 | Performance Tier A (ASUS V16) | 1080p, ≥ 60 fps High preset, 1% low ≥ 45 |
| NFR-02 | Performance Tier B (mid-spec laptop) | ≥ 30 fps Low/Medium at 1080p (or render scale ≤ 75 %), 1% low ≥ 24; **targets re-baselined after F-05** |
| NFR-03 | Memory | ≤ 3 GB RAM, ≤ 2 GB VRAM on Low |
| NFR-04 | Build size | ≤ 1.5 GB uncompressed v1.0 |
| NFR-05 | Load time | ≤ 15 s Tier B cold start of a chapter |
| NFR-06 | Stability | 0 crashes in 60-min soak; no unhandled Python exception in log |
| NFR-07 | Determinism of core logic | Unit-tested pure functions; fixed 60 Hz tick |
| NFR-08 | Accessibility | Colour-blind-safe cues, subtitles for audio cues, remap, assist modes |
| NFR-09 | Licensing | 100 % assets traceable in PROVENANCE.csv with compatible licences |
| NFR-10 | Security/privacy | No network calls, no telemetry in v1.0; no secrets in repo |

## 6. Content scope (v1.0)
5 chapters · 4 playable otter colourways + 12 accessories · 3 raft tiers · ~25 props · ~18 environment items · ~11 VFX · 3 NPC species + ambient fauna · 5 ambiences · ~16 music tracks/stems · ~50 SFX. Full inventory with budgets: `reference/ASSET_LIST.csv`, `reference/AUDIO_LIST.csv`.

## 7. Success metrics
- Vertical slice: 5 external testers finish Ch1; ≥ 4 say they would play again; median run 4–6 min.
- Alpha: co-op session of 4 for 30 min without crash.
- Beta: avg completion rate per chapter ≥ 70 %; no open S1/S2 bugs.
- v1.0: passes `15_RELEASE_CHECKLIST.md` with evidence.

## 8. Milestones
M0 Foundation (wk 1) · M1 Tech Spikes (wk 2–3) · M2 Vertical Slice (wk 4–7) · M3 Alpha (wk 8–13) · M4 Beta (wk 14–17) · M5 Release (wk 18–20). Owners and weekly plan: `11_TEAM_PLAN_RACI.md`.

## 9. Assumptions, dependencies, constraints
- UPBGE 0.50 (Blender 5.0.1) or 0.44 will be pinned after spike S-01; Python Components and `aud` work as documented.
- Team capacity ≈ 10–15 h/week per human; AI agents do most code and procedural asset work; **humans make art-direction, level-feel, audio-selection and playtest decisions**.
- Gateway models/pricing as in `09_MODEL_ROUTING_AND_REASONING.md`; costs monitored weekly.
- No budget for paid engines/assets; free/CC0/own-made only. AI-generated audio/images allowed only if the tool's terms permit commercial use (recorded).

## 10. Out of scope (v1.0)
Online multiplayer, mobile/console ports, mod tools, voice acting, procedural level generation, DLC.

## 11. Risks (top 5; full list in 14)
UPBGE API/stability · physics instability · Blender MCP/UPBGE incompatibility · LFS quota & .blend merge conflicts · scope creep.

## 12. Open questions
Final title/trademark check · music: AI-generated vs human composer · exact Tier B hardware numbers · will we pursue online co-op after v1.0?
