# 06 — Audio Specification

## 1. Goals
Warm, tactile, funny. Audio must carry feedback (hits, strokes, collects) so players read the game even when visuals are busy. No voice-over: otter **chirps** and music do the emotion.

## 2. Mix architecture
| Bus | Content | Default volume | Ducking |
|---|---|---|---|
| Music | stems, jingles | 0.7 | −6 dB under big SFX stings (200 ms attack, 800 ms release) |
| SFX | paddle, impacts, hazards, otters | 1.0 | — |
| Ambience | loops per chapter | 0.6 | — |
| UI | menu sounds | 0.8 | — |
Implemented as per-bus volume multipliers in `aud` (VERIFY handle volume/`aud.Device` features in S-01). Master volume + each bus configurable in Settings and saved.

## 3. Technical format
- SFX: mono, 44.1 kHz, OGG Vorbis q5; peak ≤ −3 dBFS; trimmed; fades 5 ms. 3D SFX must be mono.
- Ambience/Music: stereo OGG, seamless loops; music ≈ −18 LUFS integrated, ambience ≈ −24 LUFS, SFX peaks balanced by ear against music.
- Naming = ID + variation: `SFX_PaddleDip_01.ogg`. Randomise pitch ±6 % and pick variations without immediate repeats.

## 4. Adaptive music
Three synchronous stems per chapter: **A base** (always), **B rhythm** (active when moving fast / near hazards), **C danger** (rapids, whirlpool, sinking). `MusicDirector` computes target volumes from game state and crossfades over 1.5 s. Stems share BPM/key/length (96 s = clean bars). Stings: checkpoint, finish, fail duck the music. Ch4 is single-layer calm.
State table: `calm → A=1,B=0,C=0` · `busy → A=1,B=1,C=0` · `danger → A=0.8,B=1,C=1` · `sunk → fade all to 0.2 for 2 s`.

## 5. 3D audio
Listener = main camera. Distance model inverse, reference 5 m, max 60 m. Water loops attached to hazards (waterfall, whirlpool) with cone off. Raft sounds are non-spatial (centre) to remain clear.

## 6. Implementation checklist (to build)
`rr.core.audio_mix` (pure: bus math, ducking envelopes, stem weights, no-repeat picker — unit-tested) → `rr.glue.audio` (aud playback) → `MusicDirector` component → settings integration.

## 7. Asset inventory & prompts
64 items with durations, loop flags, priorities and **generator prompts**: `reference/AUDIO_LIST.csv`; paste-ready tables in `../prompts/audio_prompts.md`.

## 8. Sourcing workflow
1. P3 reviews the P0 list. 2. Try CC0 libraries first. 3. Generate missing SFX with an AI SFX tool using the provided prompts (3–5 takes each). 4. Music: (a) human composer/friend, (b) AI music tool, (c) CC0/royalty-free with permissive licence. 5. Edit loops in Audacity/Reaper; normalise; export OGG. 6. Add PROVENANCE rows (tool, plan, date, prompt, terms URL). 7. PR with a short preview video.
**Legal**: verify each tool's current terms for commercial use *before* shipping. If terms are unclear, treat the asset as non-shippable and replace it.

## 9. QA
Loop-click test, clipping test (no peaks > 0 dBFS in-game), ducking test, volume balance on laptop speakers **and** headphones, mono-compatibility, no audio on pause except UI.

## 10. Prompt to implement the audio system (Agent: gameplay, kimi-k3, high)
```text
Implement the audio system per docs/06_AUDIO_SPEC.md. Deliver (1) src/rr/core/audio_mix.py with pure functions: bus_gain(master,bus), duck_envelope(t,...), stem_weights(state), pick_variation(last_index,n,rng); (2) unit tests; (3) src/rr/glue/audio.py using the aud module with graceful fallback (log + no-op) when aud is unavailable; (4) MusicDirector component that crossfades stems in sync; (5) a debug overlay listing active handles. Mark every aud call VERIFY until run in UPBGE. Report test output.
```
