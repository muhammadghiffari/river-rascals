# Blender MCP Asset Prompt Library (generated from docs/reference/ASSET_LIST.csv)

Agent: `techart` · Model: Greg/deepseek-v4-pro · Effort: medium · MCP: `blender` (enable only for this agent)
Escalate a single hard asset (complex rig, shader math) to `Greg/kimi-k3` high.

## How to use
1. Open a **working copy** in Blender/UPBGE, start the Blender MCP addon (docs/08).
2. In OpenCode switch to `techart`, paste **MASTER PREAMBLE**, then paste one **ASSET PROMPT** below.
3. Review the viewport render, run `python tools/validate_assets.py <file>`, add `assets/PROVENANCE.csv` row, open PR.

## MASTER PREAMBLE (paste once per session)
```text
You are the technical artist for River Rascals, a cozy low-poly stylised co-op rafting game on UPBGE.
Read docs/04_ASSET_BIBLE_AND_PIPELINE.md and docs/05_ANIMATION_SPEC.md first.
STYLE: soft stylised low-poly, chunky readable silhouettes, warm saturated palette from assets/materials/palette (or the palette in docs/04),
no photoreal textures, flat/gradient colour via a shared palette texture, 2-band toon shading, no tiny details under 2 cm.
SCALE/AXES: 1 unit = 1 m, +Y forward, +X right, +Z up, origin at the object's logical pivot, apply all transforms, no negative scale.
TOPOLOGY: quads where deformation matters, triangles ok on rigid props, no n-gons, no internal faces, normals outward, no loose geometry.
NAMING: <PREFIX>_<Name>[_LODn|_COL]; collision meshes end with _COL; empties for sockets named Socket_<Purpose>.
MATERIALS: reuse MT_ToonBase with the shared palette texture whenever possible; max 2 materials per asset.
BUDGETS: respect tris_budget given in the asset line; textures power-of-two, max 2048, prefer palette atlases.
SAFETY: work only inside the current Blender file; do not access the network except for explicitly allowed CC0 sources (Poly Haven, Kenney);
never read/write files outside the repo working copy; save a checkpoint (File > Save As ..._vNN.blend) before any destructive step.
PROCESS: (1) restate the spec and list assumptions, (2) block out with primitives, (3) refine, (4) UV + materials, (5) add collision/sockets/rig as specified,
(6) report triangle count, dimensions, material list via get_scene_info, (7) render a 3-view turntable preview, (8) list anything you could not do.
Never claim success without reporting measured numbers.
```

## OUTPUT CONTRACT (append to every asset prompt)
```text
Deliver: saved .blend at assets/<category folder>/<ID>.blend, measured tris vs budget, bounding box in metres, material list,
list of sockets/empties, preview renders, and a PROVENANCE row (source=generated in Blender by agent, licence=project-owned).
```

## ASSET PROMPTS
Each block below = one prompt. Replace nothing; paste as-is after the preamble.


### Character

**CH_OtterBase** - phase 2 - owner P2
```text
Create asset CH_OtterBase: Hero otter (chibi, 3 heads tall).
Budget: 6000 triangles max (LODs if listed). Texture: palette 512. Variants: 4 colourways via palette swap.
Spec: Friendly otter, big round head, short limbs, thick tail, paddle-ready seated pose compatible. Clean quad topology, deformation-friendly shoulders/elbows. 25-bone rig per docs/05.
Save to: assets/characters/CH_OtterBase.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**CH_OtterHats** - phase 3 - owner P2
```text
Create asset CH_OtterHats: Hat set: sun hat, beanie, tricorn, flower crown.
Budget: 600 triangles max (LODs if listed). Texture: palette. Variants: 4 items.
Spec: Four separate meshes parented to head bone, each <=600 tris, readable silhouette.
Save to: assets/characters/CH_OtterHats.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**CH_OtterEyewear** - phase 3 - owner P2
```text
Create asset CH_OtterEyewear: Goggles and round glasses.
Budget: 300 triangles max (LODs if listed). Texture: palette. Variants: 2 items.
Spec: Two accessories attached to head bone; transparent lenses via simple alpha-clip material.
Save to: assets/characters/CH_OtterEyewear.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**CH_OtterNeck** - phase 3 - owner P2
```text
Create asset CH_OtterNeck: Scarf and bandana.
Budget: 400 triangles max (LODs if listed). Texture: palette. Variants: 2 items.
Spec: Two neck accessories with 2-bone flutter chain for cheap secondary motion.
Save to: assets/characters/CH_OtterNeck.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**CH_BearNPC** - phase 3 - owner P2
```text
Create asset CH_BearNPC: Bear fisherman NPC.
Budget: 7000 triangles max (LODs if listed). Texture: palette 512. Variants: 1.
Spec: Large friendly bear, fishing pose, belly-forward silhouette, 20-bone rig.
Save to: assets/characters/CH_BearNPC.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**CH_BeaverNPC** - phase 3 - owner P2
```text
Create asset CH_BeaverNPC: Beaver builder NPC.
Budget: 5000 triangles max (LODs if listed). Texture: palette 512. Variants: 1.
Spec: Beaver with hard hat, flat tail, simple rig; carries a log.
Save to: assets/characters/CH_BeaverNPC.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**CH_HeronNPC** - phase 3 - owner P2
```text
Create asset CH_HeronNPC: Heron ambient bird.
Budget: 3000 triangles max (LODs if listed). Texture: palette 256. Variants: 1.
Spec: Tall wading bird, long neck 6-bone chain, idle/fly-off animation.
Save to: assets/characters/CH_HeronNPC.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**CH_FrogAmbient** - phase 3 - owner P2
```text
Create asset CH_FrogAmbient: Frog on lily pad.
Budget: 1500 triangles max (LODs if listed). Texture: palette 128. Variants: 1.
Spec: Cartoon frog, croak jaw bone, jump.
Save to: assets/characters/CH_FrogAmbient.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**CH_DuckFlock** - phase 3 - owner P2
```text
Create asset CH_DuckFlock: Duck (instanced flock).
Budget: 500 triangles max (LODs if listed). Texture: palette 128. Variants: 3 colours.
Spec: Tiny duck, one bone, swim bob; designed for dupli-base spawning.
Save to: assets/characters/CH_DuckFlock.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**CH_FishSchool** - phase 3 - owner P2
```text
Create asset CH_FishSchool: Fish (instanced school).
Budget: 300 triangles max (LODs if listed). Texture: palette 128. Variants: 3 colours.
Spec: Tiny fish silhouette, 2-bone tail sway.
Save to: assets/characters/CH_FishSchool.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**CH_Dragonfly** - phase 3 - owner P2
```text
Create asset CH_Dragonfly: Dragonfly (billboard-ish).
Budget: 200 triangles max (LODs if listed). Texture: palette 128. Variants: 1.
Spec: Two crossed wing quads + body, shader wing flutter.
Save to: assets/characters/CH_Dragonfly.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```


### Raft

**RF_RaftT1** - phase 2 - owner P2
```text
Create asset RF_RaftT1: Raft tier 1 (logs + rope).
Budget: 6000 triangles max (LODs if listed). Texture: palette 1024. Variants: damage states x3.
Spec: 3.2m x 2.4m x 0.4m (Y,X,Z). Round logs lashed with rope, four seat slots as empties, 6 BuoySample empties, COL box. Origin at centre of mass.
Save to: assets/raft/RF_RaftT1.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**RF_RaftT2** - phase 3 - owner P2
```text
Create asset RF_RaftT2: Raft tier 2 (planks + barrels).
Budget: 7500 triangles max (LODs if listed). Texture: palette 1024. Variants: damage x3.
Spec: Same footprint, plank deck, side barrels for float, small flag.
Save to: assets/raft/RF_RaftT2.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**RF_RaftT3** - phase 4 - owner P2
```text
Create asset RF_RaftT3: Raft tier 3 (expedition raft).
Budget: 8000 triangles max (LODs if listed). Texture: palette 1024. Variants: damage x3.
Spec: Reinforced with metal bands, lantern posts, canopy option.
Save to: assets/raft/RF_RaftT3.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**RF_Oar** - phase 2 - owner P2
```text
Create asset RF_Oar: Oar (left/right via mirror).
Budget: 500 triangles max (LODs if listed). Texture: palette 256. Variants: 1.
Spec: Wooden oar 1.6 m, blade flat, pivot at oarlock; separate mesh for animation.
Save to: assets/raft/RF_Oar.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**RF_SeatSlot** - phase 2 - owner P2
```text
Create asset RF_SeatSlot: Seat/oarlock fittings.
Budget: 300 triangles max (LODs if listed). Texture: palette. Variants: 1.
Spec: Four oarlocks and thwarts.
Save to: assets/raft/RF_SeatSlot.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**RF_Mast** - phase 3 - owner P2
```text
Create asset RF_Mast: Mast and flag.
Budget: 600 triangles max (LODs if listed). Texture: palette. Variants: 3 flags.
Spec: Short mast, cloth flag with 4-bone flutter.
Save to: assets/raft/RF_Mast.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**RF_Lantern** - phase 4 - owner P2
```text
Create asset RF_Lantern: Raft lantern.
Budget: 400 triangles max (LODs if listed). Texture: palette + emissive. Variants: 1.
Spec: Hanging lantern with emissive glass.
Save to: assets/raft/RF_Lantern.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**RF_BarrelCargo** - phase 3 - owner P2
```text
Create asset RF_BarrelCargo: Cargo barrels and sacks.
Budget: 400 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Strap-on cargo props.
Save to: assets/raft/RF_BarrelCargo.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**RF_RopeCoil** - phase 3 - owner P2
```text
Create asset RF_RopeCoil: Rope coil and throw rope.
Budget: 400 triangles max (LODs if listed). Texture: palette. Variants: 1.
Spec: Coiled rope prop plus straight rope segment for rescue throw.
Save to: assets/raft/RF_RopeCoil.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```


### Prop

**PR_Coin** - phase 2 - owner P2
```text
Create asset PR_Coin: Floating coin.
Budget: 200 triangles max (LODs if listed). Texture: palette. Variants: 1.
Spec: Chunky coin with acorn emblem, bobbing.
Save to: assets/props/PR_Coin.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_GoldenFish** - phase 2 - owner P2
```text
Create asset PR_GoldenFish: Golden fish collectible.
Budget: 400 triangles max (LODs if listed). Texture: palette+emissive. Variants: 1.
Spec: Stylised golden fish leaping pose.
Save to: assets/props/PR_GoldenFish.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_Buoy** - phase 2 - owner P2
```text
Create asset PR_Buoy: Buoy marker.
Budget: 300 triangles max (LODs if listed). Texture: palette. Variants: 2.
Spec: Red/white buoy with chain stub.
Save to: assets/props/PR_Buoy.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_Log** - phase 2 - owner P2
```text
Create asset PR_Log: Floating log obstacle.
Budget: 600 triangles max (LODs if listed). Texture: palette. Variants: 3 sizes.
Spec: Cylindrical log with knots, COL capsule.
Save to: assets/props/PR_Log.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_LilyPad** - phase 3 - owner P2
```text
Create asset PR_LilyPad: Lily pad cluster.
Budget: 150 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Flat leaf discs with flower, alpha-clip free.
Save to: assets/props/PR_LilyPad.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_ReedCluster** - phase 2 - owner P2
```text
Create asset PR_ReedCluster: Reed/cattail cluster.
Budget: 300 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Crossed-card reeds, wind sway vertex colours.
Save to: assets/props/PR_ReedCluster.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_RockSmall** - phase 2 - owner P2
```text
Create asset PR_RockSmall: Rock small.
Budget: 300 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Faceted low-poly river rock, COL convex.
Save to: assets/props/PR_RockSmall.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_RockMed** - phase 2 - owner P2
```text
Create asset PR_RockMed: Rock medium.
Budget: 600 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Medium rock, COL convex hull.
Save to: assets/props/PR_RockMed.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_RockLarge** - phase 2 - owner P2
```text
Create asset PR_RockLarge: Rock large / boulder.
Budget: 1200 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Boulder with moss patches via vertex colour.
Save to: assets/props/PR_RockLarge.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_RockCluster** - phase 3 - owner P2
```text
Create asset PR_RockCluster: Boulder cluster.
Budget: 2500 triangles max (LODs if listed). Texture: palette. Variants: 2.
Spec: Group of rocks for rapids.
Save to: assets/props/PR_RockCluster.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_Driftwood** - phase 3 - owner P2
```text
Create asset PR_Driftwood: Driftwood.
Budget: 500 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Branchy driftwood.
Save to: assets/props/PR_Driftwood.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_DockSection** - phase 3 - owner P2
```text
Create asset PR_DockSection: Dock section.
Budget: 800 triangles max (LODs if listed). Texture: palette. Variants: 2.
Spec: Modular dock planks and posts.
Save to: assets/props/PR_DockSection.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_BridgeWood** - phase 3 - owner P2
```text
Create asset PR_BridgeWood: Wooden bridge.
Budget: 3000 triangles max (LODs if listed). Texture: palette. Variants: 2.
Spec: Spans 14 m, clearance 3 m, rope rails.
Save to: assets/props/PR_BridgeWood.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_Cabin** - phase 3 - owner P2
```text
Create asset PR_Cabin: Riverside cabin.
Budget: 3000 triangles max (LODs if listed). Texture: palette 512. Variants: 2.
Spec: Cosy cabin with chimney.
Save to: assets/props/PR_Cabin.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_Tent** - phase 3 - owner P2
```text
Create asset PR_Tent: Camp tent.
Budget: 600 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Triangular tent.
Save to: assets/props/PR_Tent.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_Campfire** - phase 3 - owner P2
```text
Create asset PR_Campfire: Campfire.
Budget: 400 triangles max (LODs if listed). Texture: palette+emissive. Variants: 1.
Spec: Log ring, fire card particles hook.
Save to: assets/props/PR_Campfire.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_Signpost** - phase 2 - owner P2
```text
Create asset PR_Signpost: Signpost.
Budget: 300 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Directional arrows, readable at 20 m.
Save to: assets/props/PR_Signpost.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_LanternPost** - phase 4 - owner P2
```text
Create asset PR_LanternPost: Lantern post.
Budget: 400 triangles max (LODs if listed). Texture: palette+emissive. Variants: 1.
Spec: Riverbank lantern.
Save to: assets/props/PR_LanternPost.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_Mailbox** - phase 3 - owner P2
```text
Create asset PR_Mailbox: Whimsical mailbox.
Budget: 300 triangles max (LODs if listed). Texture: palette. Variants: 1.
Spec: Easter-egg prop.
Save to: assets/props/PR_Mailbox.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_CheckpointArch** - phase 2 - owner P2
```text
Create asset PR_CheckpointArch: Checkpoint arch with banner.
Budget: 1500 triangles max (LODs if listed). Texture: palette 512. Variants: 1.
Spec: Spans the river 8 m, cloth banner with flutter bones.
Save to: assets/props/PR_CheckpointArch.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_FinishGate** - phase 2 - owner P2
```text
Create asset PR_FinishGate: Finish gate.
Budget: 2000 triangles max (LODs if listed). Texture: palette 512. Variants: 1.
Spec: Larger arch, confetti hook points.
Save to: assets/props/PR_FinishGate.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_BeaverDam** - phase 3 - owner P2
```text
Create asset PR_BeaverDam: Beaver dam obstacle.
Budget: 2500 triangles max (LODs if listed). Texture: palette. Variants: 1.
Spec: Gap in the middle, COL pieces.
Save to: assets/props/PR_BeaverDam.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_WaterfallLip** - phase 3 - owner P2
```text
Create asset PR_WaterfallLip: Waterfall lip rocks.
Budget: 3000 triangles max (LODs if listed). Texture: palette. Variants: 2.
Spec: Rock lips framing waterfall.
Save to: assets/props/PR_WaterfallLip.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**PR_WhirlpoolDisc** - phase 3 - owner P2
```text
Create asset PR_WhirlpoolDisc: Whirlpool visual disc.
Budget: 800 triangles max (LODs if listed). Texture: shader. Variants: 1.
Spec: Spiral disc mesh for shader, radius 6 m.
Save to: assets/props/PR_WhirlpoolDisc.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```


### Environment

**EN_PineTree** - phase 2 - owner P2
```text
Create asset EN_PineTree: Pine tree.
Budget: 800 triangles max (LODs if listed). Texture: palette. Variants: 3 variants + LOD1 200.
Spec: Stylised tapered pine, wind sway vertex colours.
Save to: assets/environment/EN_PineTree.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_BirchTree** - phase 3 - owner P2
```text
Create asset EN_BirchTree: Birch tree.
Budget: 700 triangles max (LODs if listed). Texture: palette. Variants: 2.
Spec: White trunk, leaf clusters.
Save to: assets/environment/EN_BirchTree.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_Bush** - phase 2 - owner P2
```text
Create asset EN_Bush: Bush.
Budget: 200 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Rounded bush.
Save to: assets/environment/EN_Bush.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_Fern** - phase 3 - owner P2
```text
Create asset EN_Fern: Fern.
Budget: 120 triangles max (LODs if listed). Texture: palette. Variants: 2.
Spec: Cross cards.
Save to: assets/environment/EN_Fern.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_Flowers** - phase 3 - owner P2
```text
Create asset EN_Flowers: Flower patches.
Budget: 150 triangles max (LODs if listed). Texture: palette. Variants: 4.
Spec: Colour accents.
Save to: assets/environment/EN_Flowers.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_Mushrooms** - phase 3 - owner P2
```text
Create asset EN_Mushrooms: Mushroom cluster.
Budget: 200 triangles max (LODs if listed). Texture: palette. Variants: 3.
Spec: Cute red/white caps.
Save to: assets/environment/EN_Mushrooms.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_CliffModular** - phase 3 - owner P2
```text
Create asset EN_CliffModular: Modular cliff pieces.
Budget: 2000 triangles max (LODs if listed). Texture: palette 1024. Variants: 6 pieces.
Spec: Snap on 4 m grid, tileable edges.
Save to: assets/environment/EN_CliffModular.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_CanyonWall** - phase 3 - owner P2
```text
Create asset EN_CanyonWall: Canyon wall modules.
Budget: 3000 triangles max (LODs if listed). Texture: palette 1024. Variants: 6 pieces.
Spec: Layered rock strata, snap on 8 m grid.
Save to: assets/environment/EN_CanyonWall.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_BankTile** - phase 2 - owner P2
```text
Create asset EN_BankTile: Riverbank tiles.
Budget: 1500 triangles max (LODs if listed). Texture: palette 1024. Variants: 4 tiles.
Spec: Shore transition tiles with foam anchor edge verts.
Save to: assets/environment/EN_BankTile.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_MountainBackdrop** - phase 3 - owner P2
```text
Create asset EN_MountainBackdrop: Mountain backdrop.
Budget: 2000 triangles max (LODs if listed). Texture: palette 512. Variants: 3.
Spec: Distant silhouettes, unlit.
Save to: assets/environment/EN_MountainBackdrop.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_CloudCards** - phase 3 - owner P2
```text
Create asset EN_CloudCards: Cloud cards.
Budget: 100 triangles max (LODs if listed). Texture: alpha 512. Variants: 4.
Spec: Billboard clouds.
Save to: assets/environment/EN_CloudCards.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_SkyDay** - phase 2 - owner P2
```text
Create asset EN_SkyDay: Sky gradient day.
Budget: 0 triangles max (LODs if listed). Texture: shader. Variants: 1.
Spec: Gradient sky; no HDRI needed.
Save to: assets/environment/EN_SkyDay.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_SkyDusk** - phase 3 - owner P2
```text
Create asset EN_SkyDusk: Sky gradient dusk.
Budget: 0 triangles max (LODs if listed). Texture: shader. Variants: 1.
Spec: Warm gradient.
Save to: assets/environment/EN_SkyDusk.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_SkyNight** - phase 4 - owner P2
```text
Create asset EN_SkyNight: Sky night with stars.
Budget: 0 triangles max (LODs if listed). Texture: shader. Variants: 1.
Spec: Star field shader.
Save to: assets/environment/EN_SkyNight.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_SkyStorm** - phase 4 - owner P2
```text
Create asset EN_SkyStorm: Sky storm.
Budget: 0 triangles max (LODs if listed). Texture: shader. Variants: 1.
Spec: Dark clouds gradient.
Save to: assets/environment/EN_SkyStorm.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_RiverStrip** - phase 2 - owner P2
```text
Create asset EN_RiverStrip: River surface strip mesh.
Budget: 3000 triangles max (LODs if listed). Texture: shader. Variants: 1 per chapter.
Spec: Subdivided ribbon following centerline, UV along flow.
Save to: assets/environment/EN_RiverStrip.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_Waterfall** - phase 3 - owner P2
```text
Create asset EN_Waterfall: Waterfall mesh.
Budget: 1500 triangles max (LODs if listed). Texture: shader. Variants: 1.
Spec: Vertical sheet with scrolling flow shader.
Save to: assets/environment/EN_Waterfall.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**EN_GrassCards** - phase 3 - owner P2
```text
Create asset EN_GrassCards: Grass cards.
Budget: 100 triangles max (LODs if listed). Texture: alpha 512. Variants: 3.
Spec: Cross cards.
Save to: assets/environment/EN_GrassCards.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```


### VFX

**VX_Splash** - phase 2 - owner P2
```text
Create asset VX_Splash: Splash particle sprite sheet.
Budget: 8 triangles max (LODs if listed). Texture: atlas 512. Variants: 1.
Spec: 4x4 sprite sheet, additive-friendly.
Save to: assets/vfx/VX_Splash.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**VX_Wake** - phase 2 - owner P2
```text
Create asset VX_Wake: Wake trail strip.
Budget: 100 triangles max (LODs if listed). Texture: atlas 256. Variants: 1.
Spec: V-shaped foam trail.
Save to: assets/vfx/VX_Wake.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**VX_FoamRing** - phase 2 - owner P2
```text
Create asset VX_FoamRing: Foam ring decal.
Budget: 8 triangles max (LODs if listed). Texture: 256. Variants: 1.
Spec: Foam around rocks.
Save to: assets/vfx/VX_FoamRing.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**VX_Bubbles** - phase 3 - owner P2
```text
Create asset VX_Bubbles: Bubbles sprite.
Budget: 8 triangles max (LODs if listed). Texture: 128. Variants: 1.
Spec: Bubble set.
Save to: assets/vfx/VX_Bubbles.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**VX_Fireflies** - phase 4 - owner P2
```text
Create asset VX_Fireflies: Firefly particles.
Budget: 8 triangles max (LODs if listed). Texture: 128. Variants: 1.
Spec: Glow dot.
Save to: assets/vfx/VX_Fireflies.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**VX_Leaves** - phase 3 - owner P2
```text
Create asset VX_Leaves: Falling leaves.
Budget: 8 triangles max (LODs if listed). Texture: atlas 256. Variants: 1.
Spec: Leaf sprites.
Save to: assets/vfx/VX_Leaves.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**VX_Mist** - phase 3 - owner P2
```text
Create asset VX_Mist: Mist cards.
Budget: 8 triangles max (LODs if listed). Texture: 256. Variants: 1.
Spec: Soft fog sheets.
Save to: assets/vfx/VX_Mist.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**VX_Rain** - phase 4 - owner P2
```text
Create asset VX_Rain: Rain streaks.
Budget: 8 triangles max (LODs if listed). Texture: 128. Variants: 1.
Spec: Streak sprite + splash.
Save to: assets/vfx/VX_Rain.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**VX_Sparkle** - phase 2 - owner P2
```text
Create asset VX_Sparkle: Collect sparkle.
Budget: 8 triangles max (LODs if listed). Texture: 128. Variants: 1.
Spec: Star sparkle.
Save to: assets/vfx/VX_Sparkle.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**VX_Impact** - phase 2 - owner P2
```text
Create asset VX_Impact: Impact wood chips/dust.
Budget: 8 triangles max (LODs if listed). Texture: atlas 256. Variants: 1.
Spec: Debris sprites.
Save to: assets/vfx/VX_Impact.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**VX_Confetti** - phase 3 - owner P2
```text
Create asset VX_Confetti: Confetti.
Budget: 8 triangles max (LODs if listed). Texture: 128. Variants: 1.
Spec: Celebration.
Save to: assets/vfx/VX_Confetti.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```


### UI

**UI_IconSet** - phase 2 - owner P3
```text
Create asset UI_IconSet: HUD icon set.
Budget: 2000 triangles max (LODs if listed). Texture: atlas 1024. Variants: 1.
Spec: Coin, fish, hull hearts, flag, pad, gear, speaker (vector -> PNG, 128 px).
Save to: assets/ui/UI_IconSet.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**UI_Logo** - phase 3 - owner P3
```text
Create asset UI_Logo: Game logo.
Budget: 0 triangles max (LODs if listed). Texture: 2048. Variants: 1.
Spec: Chunky hand-lettered logo; own design.
Save to: assets/ui/UI_Logo.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**UI_Frames** - phase 2 - owner P3
```text
Create asset UI_Frames: HUD frames and buttons.
Budget: 0 triangles max (LODs if listed). Texture: atlas 1024. Variants: 1.
Spec: 9-slice panels, button states.
Save to: assets/ui/UI_Frames.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**UI_MenuBG** - phase 3 - owner P2
```text
Create asset UI_MenuBG: Main menu background scene.
Budget: 3000 triangles max (LODs if listed). Texture: palette. Variants: 1.
Spec: Cosy river vista, parallax layers.
Save to: assets/ui/UI_MenuBG.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**UI_Fonts** - phase 2 - owner P3
```text
Create asset UI_Fonts: Fonts (OFL only).
Budget: 0 triangles max (LODs if listed). Texture: ttf. Variants: 2.
Spec: One display + one body font, cover EN/ID, record licence.
Save to: assets/ui/UI_Fonts.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```


### Material

**MT_ToonBase** - phase 2 - owner P2
```text
Create asset MT_ToonBase: Toon base material (palette lookup).
Budget: 0 triangles max (LODs if listed). Texture: palette. Variants: 1.
Spec: Shared palette texture, 2-band shading, optional rim; single material for most props.
Save to: assets/materials/MT_ToonBase.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**MT_Water** - phase 2 - owner P2
```text
Create asset MT_Water: Water material.
Budget: 0 triangles max (LODs if listed). Texture: shader. Variants: 3 presets.
Spec: Wave sum matching rr.core.waves, depth tint, foam at edges, flow scroll.
Save to: assets/materials/MT_Water.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**MT_FoliageSway** - phase 3 - owner P2
```text
Create asset MT_FoliageSway: Foliage wind sway.
Budget: 0 triangles max (LODs if listed). Texture: shader. Variants: 1.
Spec: Vertex-colour driven sway.
Save to: assets/materials/MT_FoliageSway.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**MT_Foam** - phase 3 - owner P2
```text
Create asset MT_Foam: Foam/flow material.
Budget: 0 triangles max (LODs if listed). Texture: shader. Variants: 1.
Spec: Scrolling foam bands.
Save to: assets/materials/MT_Foam.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```

**MT_SkyGradient** - phase 2 - owner P2
```text
Create asset MT_SkyGradient: Sky gradient shader.
Budget: 0 triangles max (LODs if listed). Texture: shader. Variants: 4.
Spec: Top/horizon colours, sun glow.
Save to: assets/materials/MT_SkyGradient.blend
Follow MASTER PREAMBLE and OUTPUT CONTRACT.
```
