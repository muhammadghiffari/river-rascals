"""Create a blockout raft with correct names, sample empties and collider.

Run in Blender/UPBGE:  blender -b --python tools/blender/gen_raft_blockout.py -- out.blend
Result: RF_RaftT1 (visual), RF_RaftT1_COL (box), 6x BuoySample.NN empties parented to the raft.
UNVERIFIED scaffold: check in spike S-05.
"""
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "RF_RaftT1.blend"
bpy.ops.wm.read_factory_settings(use_empty=True)

L, W, H = 3.2, 2.4, 0.4  # metres: length (Y), width (X), height (Z)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
raft = bpy.context.active_object
raft.name = "RF_RaftT1"
raft.scale = (W, L, H)
bpy.ops.object.transform_apply(scale=True)
mat = bpy.data.materials.new("MT_RaftWood")
mat.diffuse_color = (0.55, 0.38, 0.22, 1.0)
raft.data.materials.append(mat)

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
col = bpy.context.active_object
col.name = "RF_RaftT1_COL"
col.scale = (W, L, H)
bpy.ops.object.transform_apply(scale=True)
col.display_type = "WIRE"
col.parent = raft

pts = [(-W / 2 + 0.2, -L / 2 + 0.2), (W / 2 - 0.2, -L / 2 + 0.2),
       (-W / 2 + 0.2, 0.0), (W / 2 - 0.2, 0.0),
       (-W / 2 + 0.2, L / 2 - 0.2), (W / 2 - 0.2, L / 2 - 0.2)]
for i, (x, y) in enumerate(pts):
    bpy.ops.object.empty_add(type="SPHERE", radius=0.08, location=(x, y, -H / 2))
    e = bpy.context.active_object
    e.name = "BuoySample.%02d" % i
    e.parent = raft

bpy.ops.wm.save_as_mainfile(filepath=out)
print("[gen] saved", out)
