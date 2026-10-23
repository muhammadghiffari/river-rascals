# Audio Generation Prompt Library (generated from docs/reference/AUDIO_LIST.csv)

Coding models cannot produce audio. Use an external generator or sourced CC0 libraries, then have `qa`/`builder` integrate.
Recommended order: (1) CC0 libraries first (Kenney, Freesound CC0 filter, OpenGameArt CC0, Sonniss GDC bundles - check each licence),
(2) AI SFX generator (e.g. ElevenLabs sound effects) for missing items, (3) AI/composed music (e.g. Suno/Udio) or a human composer.
**Before commercial use read the tool's current terms** (output ownership, commercial rights, plan requirements) and log it in `assets/PROVENANCE.csv`
(tool, plan, date, exact prompt, terms URL).

## Technical targets
- SFX: mono 44.1 kHz OGG Vorbis (q5), peak <= -3 dBFS, trim silence, 5 ms fades, 3D-positioned SFX must be mono.
- Ambience/music: stereo 44.1 kHz OGG, loops must be seamless (verify in Audacity: crossfade tail->head), music target ~ -18 LUFS integrated, ambience ~ -24 LUFS.
- File names exactly equal the ID, e.g. `SFX_PaddleDip_01.ogg`. Folders: assets/audio/{sfx,ambience,music,ui}/.
- Generate 3-5 candidates per item; keep the best 1-4 variations as noted.

## Prompt suffix for every SFX generation
`, game sound effect, clean, no background noise, no music, no voice, dry, high quality`

## Prompt suffix for every music generation
`, instrumental, no vocals, loopable, consistent tempo and key, cozy adventure game soundtrack, clean mix with headroom`
For stems: generate stem A first, then request the others with the same BPM/key text; if the tool cannot do stems, generate a full mix and ask a human to arrange (or use a stem splitter) - never ship stems that drift.

## Audio items


### SFX

| ID | Prio | Dur (s) | Loop | Prompt | Notes |
|---|---|---|---|---|---|
| SFX_PaddleDip | P0 | 0.4 | no | Wooden oar blade dipping into river water, soft plop, close mic, no music, dry | 3 variations |
| SFX_PaddlePull | P0 | 0.8 | no | Wooden oar pulling through water, smooth swoosh with light bubbling, close mic | 3 variations |
| SFX_PaddleExit | P0 | 0.5 | no | Oar lifting out of water, short drip cascade, light splash | 3 variations |
| SFX_RaftCreak | P0 | 1.2 | no | Wooden raft logs creaking under weight with rope tension, gentle | 4 variations, random pitch |
| SFX_RaftBumpSoft | P0 | 0.5 | no | Soft thud of wooden raft bumping a mossy rock, muffled | 3 variations |
| SFX_RaftBumpHard | P0 | 0.8 | no | Heavy wood impact on stone with splintering crack, short, punchy | 3 variations |
| SFX_RaftBreak | P1 | 1.0 | no | Wooden planks cracking and snapping, mid-intensity, cartoonish | 2 |
| SFX_RaftRepair | P1 | 1.2 | no | Cartoon hammering and rope tying, cheerful | 2 |
| SFX_SplashSmall | P0 | 0.6 | no | Small water splash, light droplets, bright | 4 |
| SFX_SplashBig | P0 | 1.2 | no | Large splash of a body falling into river, dull plunge then bubbles | 3 |
| SFX_WaterRushLoop | P0 | 8.0 | yes | Whitewater rapids rushing, seamless loop, no voices, no music | stereo |
| SFX_WaterfallLoop | P1 | 8.0 | yes | Large waterfall roar with mist hiss, seamless loop | stereo |
| SFX_WhirlpoolLoop | P1 | 6.0 | yes | Water swirling gurgling whirlpool, hollow, seamless loop | 3D |
| SFX_RopeThrow | P1 | 0.7 | no | Rope whipping through air, light whoosh | 2 |
| SFX_RopeGrab | P1 | 0.4 | no | Hand grabbing rope, tight squeak | 2 |
| SFX_CoinPickup | P0 | 0.5 | no | Cheerful bright coin chime, cartoon, short, ascending | pitch up on streak |
| SFX_FishPickup | P0 | 0.9 | no | Magical sparkle shimmer with a splashy flop, joyful | 1 |
| SFX_Checkpoint | P0 | 1.5 | no | Warm triumphant fanfare of three notes on wooden flute and marimba, short | 1 |
| SFX_Finish | P0 | 3.0 | no | Cozy celebratory sting, acoustic guitar, flute and shaker, resolves major, 3 seconds | 1 |
| SFX_Fail | P1 | 2.0 | no | Gentle comedic descending trombone and bubbles, not harsh | 1 |
| SFX_OtterChirp | P0 | 0.5 | no | Cute otter chirp squeak, playful, high pitched, no human words | 6 variations |
| SFX_OtterPanic | P0 | 0.8 | no | Cartoon otter alarmed squeal, short | 4 |
| SFX_OtterCheer | P1 | 1.0 | no | Group of cute otters cheering with chirps, joyful | 3 |
| SFX_OtterSplashOut | P1 | 0.9 | no | Wet climbing onto wooden raft, dripping, scramble | 2 |
| SFX_Emote | P2 | 0.5 | no | Cute pop and bubble sounds for emotes, 4 distinct | 4 |
| SFX_BoostZone | P1 | 1.0 | no | Water surge whoosh speeding up, rising | 1 |
| SFX_LogBonk | P1 | 0.6 | no | Hollow wooden log bonk, cartoon | 3 |
| SFX_BearGrowlFriendly | P2 | 1.2 | no | Big friendly bear low chuckle rumble, cartoon | 2 |
| SFX_BeaverChop | P2 | 1.0 | no | Small teeth gnawing wood, rhythmic | 2 |
| SFX_HeronFlap | P2 | 1.0 | no | Large bird wings flapping taking off from water | 2 |
| SFX_Frog | P2 | 0.6 | no | Cute frog croak ribbit | 3 |
| SFX_Thunder | P2 | 4.0 | no | Distant rolling thunder, soft, no sharp crack | 3 |
| SFX_RainLoop | P2 | 10.0 | yes | Gentle rain on river and leaves, seamless loop | stereo |
| SFX_LanternFlicker | P3 | 3.0 | yes | Soft flame flicker loop, very quiet | 1 |

### UI

| ID | Prio | Dur (s) | Loop | Prompt | Notes |
|---|---|---|---|---|---|
| UI_Click | P0 | 0.15 | no | Soft wooden click, tiny | 1 |
| UI_Hover | P0 | 0.1 | no | Very soft tick, subtle | 1 |
| UI_Confirm | P0 | 0.4 | no | Positive two-note marimba blip | 1 |
| UI_Back | P0 | 0.3 | no | Soft descending two-note blip | 1 |
| UI_Join | P1 | 0.7 | no | Happy rising chime with a splash, playful | 1 |
| UI_Leave | P1 | 0.6 | no | Soft falling blip | 1 |
| UI_Pause | P1 | 0.4 | no | Muffled low-pass whoosh in | 1 |
| UI_Unlock | P2 | 1.2 | no | Sparkling reveal chime | 1 |

### Ambience

| ID | Prio | Dur (s) | Loop | Prompt | Notes |
|---|---|---|---|---|---|
| AMB_Creek | P0 | 60.0 | yes | Gentle creek, birds chirping, light breeze through pines, no voices, seamless loop 60s | stereo |
| AMB_Pines | P1 | 60.0 | yes | Forest wind, distant rapids, woodpecker occasionally, seamless loop | stereo |
| AMB_Canyon | P2 | 60.0 | yes | Canyon echo wind, dripping water, low drones subtle, seamless loop | stereo |
| AMB_Lagoon | P2 | 60.0 | yes | Night crickets, frogs, soft water lapping, owl once, seamless loop | stereo |
| AMB_Thunder | P2 | 60.0 | yes | Storm wind, big waterfall roar background, seamless loop | stereo |
| AMB_Menu | P1 | 60.0 | yes | Warm campsite evening, soft fire crackle, crickets, seamless loop | stereo |

### Music

| ID | Prio | Dur (s) | Loop | Prompt | Notes |
|---|---|---|---|---|---|
| MUS_Menu | P1 | 90.0 | yes | Cozy acoustic folk instrumental, fingerpicked acoustic guitar, ukulele, soft hand percussion, warm, 92 BPM, loopable, no vocals, adventure-in-nature mood | stereo, seamless loop |
| MUS_Ch1_Base | P0 | 96.0 | yes | Gentle playful acoustic instrumental, ukulele and light marimba, 100 BPM, sunny, loopable, no vocals | stem A - always playing |
| MUS_Ch1_Rhythm | P0 | 96.0 | yes | Same key and tempo as base 100 BPM: shaker, cajon, hand claps, upbeat, loopable, no vocals | stem B - active near hazards |
| MUS_Ch1_Danger | P1 | 96.0 | yes | Same key and tempo 100 BPM: urgent strings pizzicato, toms, rising tension but still playful, loopable | stem C - rapids/danger |
| MUS_Ch2_Base | P1 | 96.0 | yes | Energetic folk instrumental, banjo and fiddle, 118 BPM, forest rapids adventure, loopable, no vocals | A |
| MUS_Ch2_Rhythm | P1 | 96.0 | yes | Same key/tempo 118 BPM: foot stomps, snare brushes, mandolin chops, loopable | B |
| MUS_Ch2_Danger | P2 | 96.0 | yes | Same key/tempo 118 BPM: driving percussion, fiddle runs, intense, loopable | C |
| MUS_Ch3_Base | P2 | 96.0 | yes | Mysterious misty canyon, soft piano, cello and flute, 84 BPM, echoing, loopable, no vocals | A |
| MUS_Ch3_Rhythm | P2 | 96.0 | yes | Same key/tempo 84 BPM: low frame drum, shakers, pulsing pizzicato | B |
| MUS_Ch3_Danger | P2 | 96.0 | yes | Same key/tempo 84 BPM: tense cello ostinato, taiko hits | C |
| MUS_Ch4_Base | P3 | 120.0 | yes | Dreamy lullaby, kalimba, soft pads, celesta, 70 BPM, peaceful night, loopable, no vocals | calm chapter, no stems |
| MUS_Ch5_Base | P3 | 96.0 | yes | Epic but cozy adventure orchestral-folk, strings, brass, acoustic guitar, 126 BPM, loopable, no vocals | A |
| MUS_Ch5_Rhythm | P3 | 96.0 | yes | Same key/tempo 126 BPM: big drums, shakers, claps | B |
| MUS_Ch5_Danger | P3 | 96.0 | yes | Same key/tempo 126 BPM: full tension brass stabs, rapid strings | C |
| MUS_Victory | P1 | 12.0 | no | Joyful acoustic celebration, ukulele, flute, claps, resolves, 12 seconds | 1 |
| MUS_Credits | P3 | 120.0 | no | Warm reprise of a folk adventure theme with guitar and strings, gentle | 1 |
