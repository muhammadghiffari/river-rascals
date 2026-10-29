"""Read-only source measurements; run with UPBGE --background --python."""
import json
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
for relative in ("assets/raft/RF_RaftT1.blend", "assets/raft/RF_Oar.blend",
                 "assets/props/PR_RockLarge.blend"):
    with bpy.data.libraries.load(str(ROOT / relative), link=False) as (source, target):
        target.objects = source.objects
    for obj in target.objects:
        if obj.type == "MESH":
            points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            print("ASSET", json.dumps({"file": relative, "name": obj.name,
                  "dimensions": list(obj.dimensions), "location": list(obj.location),
                  "bounds": [[min(p[i] for p in points), max(p[i] for p in points)]
                             for i in range(3)]}))
print("GAME", [p.identifier for p in bpy.context.scene.game_settings.bl_rna.properties])
bpy.ops.import_scene.gltf(filepath=str(ROOT / "assets/_source/quaternius/Raft_Hgf0R8s4Uo.glb"))
for obj in bpy.context.selected_objects:
    if obj.type == "MESH":
        print("ORIGINAL", obj.name, list(obj.dimensions))
