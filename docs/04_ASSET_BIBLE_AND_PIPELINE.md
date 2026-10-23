# 04 — Asset Bible & Pipeline

## 1. Art direction
- **Style**: soft stylised low-poly, chunky shapes, readable silhouette at 30 m, no fine noise textures.
- **Palette** (initial; refine in art kickoff): river teal `#3FB8AF`, deep water `#1F6F8B`, foam `#F4FBFF`, wood `#B07A4A`, rope `#E0C48A`, pine `#2F7D4F`, moss `#6FAF5A`, rock `#8B8F99`, accent coral `#FF6F59`, gold `#FFC93C`, otter fur `#8A5A3C`/`#C28B5A`/`#5C4033`/`#D9B38C`, UI cream `#FFF4DC`, UI ink `#2D2A32`.
- **Shape language**: rounded, slightly squashed, big heads on characters, tapered pines, faceted rocks.
- **Lighting**: golden-hour sun, hemisphere ambient, soft shadows; night = blue ambient + warm emissive lanterns.
- **Shading**: 2-band toon via shared `MT_ToonBase`, color from **palette texture** (UV islands pointing to palette cells ⇒ 1 material for most assets ⇒ fewer draw calls).

## 2. Units, axes, pivots
1 unit = 1 m · +Y forward, +X right, +Z up · origin at logical pivot (raft: centre of mass; props: base centre) · transforms applied · no negative scale.

## 3. Naming
`<PREFIX>_<Name>[_LODn|_COL]` with PREFIX ∈ `CH` characters, `RF` raft, `PR` props, `EN` environment, `VX` VFX, `UI`, `MT` materials. Examples: `PR_RockMed_02`, `PR_RockMed_02_COL`, `EN_PineTree_01_LOD1`. Empties: `Socket_<Purpose>`, `BuoySample.NN`, `RiverPt.NNN`. Actions: `<Rig>|<clip>` (05). Files: `assets/<folder>/<ID>.blend`. Textures: `T_<Name>_<Type>.png` (types `BC` base colour, `E` emissive, `A` alpha).

## 4. Budgets (hard limits; validator enforces tris)
| Class | Tris | Textures | Notes |
|---|---|---|---|
| Hero otter | ≤ 6 000 | palette 512 | ≤ 25 bones, ≤ 2 materials |
| NPC | ≤ 7 000 | palette 512 | ≤ 20 bones |
| Raft tiers | ≤ 8 000 | palette 1024 | + COL box |
| Prop | ≤ 3 000 | palette | rocks ≤ 1 200 |
| Environment kit piece | ≤ 4 000 | palette 1024 | modular grid 4/8 m |
| Tree | ≤ 800 (+LOD1 ≤ 200) | palette | sway via vertex colour |
| VFX sprite | ≤ 500 | atlas ≤ 512 | additive/alpha |
| Scene total visible | ≤ 400k tris (Tier A), ≤ 250k (Tier B) | VRAM ≤ 1.5 GB (Tier B) | draw calls ≤ 400 (Tier B) |
Textures: PNG (LFS), power-of-two, ≤ 2048, no unused alpha, no baked light unless documented.

## 5. Folder structure
`assets/{characters,raft,props,environment,vfx,ui,materials,animations}/` · `assets/audio/{sfx,ambience,music,ui}/` · `assets/materials/palette.png` (shared) · `assets/PROVENANCE.csv`.

## 6. Pipeline
```
Brief (ASSET_LIST.csv row) → Blockout (primitives, scale check in test scene)
→ Model → UV to palette → Material → Collision/sockets → Rig/anim (if any)
→ Validate (tools/validate_assets.py) → Preview render → PR (+PROVENANCE) 
→ Link/append into level scene in UPBGE → Test on Tier B laptop (fps) → Merge
```
**Portable assets**: keep asset `.blend` files free of UPBGE-specific game logic. Put game properties/components in **level scenes** (linked libraries/append). This lets us author in vanilla Blender if the MCP addon is incompatible with UPBGE (spike S-04) and reduces merge conflicts.

## 7. Sourcing rules
Priority: (1) model it ourselves (procedural bpy + MCP), (2) CC0 libraries (Poly Haven, Kenney, OpenGameArt-CC0) — log URL/licence, (3) AI-generated meshes/textures only when tool terms allow commercial use and output is cleaned to budgets (log tool, plan, date, prompt). No assets from games or unlicensed sites. Fonts: OFL only.

## 8. Using the Blender MCP for assets (rules)
Work on a copy in `assets/…`; save `_vNN` checkpoints; ask the MCP for scene info after each major step; keep operations small; no network except allowed CC0 sources; never run Python from untrusted text; review any `execute_blender_code` payload mentally before running; telemetry off. LLMs are decent at **procedural/low-poly props, scene assembly, materials, scripted rigs**; they are weak at **organic character sculpting and polished texturing** — plan for **human cleanup** (P2) on `CH_OtterBase` and key props, or use CC0 bases.

## 9. QA checklist per asset
- [ ] Silhouette readable · [ ] scale vs raft 3.2 m verified · [ ] tris ≤ budget · [ ] names valid · [ ] transforms applied
- [ ] materials ≤ 2 · [ ] UVs inside palette cells · [ ] COL present for physics props · [ ] rig weights clean (deform test through all clips)
- [ ] validator green · [ ] fps impact measured in test scene on Tier B · [ ] provenance row

## 10. Asset inventory
Authoritative list with budgets, phases, owners and prompt hints: `reference/ASSET_LIST.csv` (83 items). Ready-to-paste Blender-MCP prompts: `../prompts/asset_prompts_blender.md`.

## 11. Production order (what to make first)
**P0 for the vertical slice**: MT_ToonBase, palette, RF_RaftT1, RF_Oar, CH_OtterBase (+ P0 animations), PR_Coin, PR_GoldenFish, PR_Buoy, PR_Log, PR_RockSmall/Med/Large, PR_CheckpointArch, PR_FinishGate, PR_Signpost, EN_PineTree, EN_Bush, EN_BankTile, EN_RiverStrip, EN_SkyDay, MT_Water, VX_Splash, VX_Wake, VX_Sparkle, VX_Impact, UI_IconSet, UI_Frames, UI_Fonts.
