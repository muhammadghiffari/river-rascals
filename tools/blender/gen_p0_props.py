"""Export original P0 props. Host invocation locks ALL paths before starting Blender.

Run: python tools/blender/gen_p0_props.py
Audit existing exports: python tools/blender/gen_p0_props.py --verify-only
Regenerate own locked exports: python tools/blender/gen_p0_props.py --replace-locked
Requires UPBGE_PATH; no scene graphics settings are changed.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from rr.core.prop_geometry import PALETTE, build_props  # noqa: E402


def host():
    from tools.run_game import find_exe

    if not os.environ.get("UPBGE_PATH"):
        raise RuntimeError("Set UPBGE_PATH to the approved UPBGE executable directory")
    exe = find_exe("blender")
    if "--verify-only" in sys.argv:
        subprocess.run([exe, "--background", "--python-exit-code", "1", "--python",
                        str(Path(__file__).resolve()), "--", "--worker", "--verify-only"],
                       cwd=ROOT, check=True)
        return
    paths = [Path("assets/props") / (p.name + ".blend") for p in build_props()]
    replace = "--replace-locked" in sys.argv
    for path in paths:
        if (ROOT / path).exists() and not replace:
            raise FileExistsError(f"Refusing to overwrite {path}")
    locks = subprocess.run(["git", "lfs", "locks", "--verify", "--json"], cwd=ROOT,
                           check=True, capture_output=True, text=True)
    ours = {lock["path"] for lock in json.loads(locks.stdout).get("ours", [])}
    for path in paths:
        if path.as_posix() not in ours:
            subprocess.run(["git", "lfs", "lock", path.as_posix()], cwd=ROOT, check=True)
    subprocess.run([exe, "--background", "--python-exit-code", "1", "--python",
                    str(Path(__file__).resolve()), "--", "--worker"]
                   + (["--replace-locked"] if replace else []), cwd=ROOT, check=True)


def palette_material(bpy):
    image = bpy.data.images.new("T_P0Palette_BC", width=512, height=512, alpha=False)
    row = []
    for color in PALETTE:
        row.extend(([int(color[i:i+2], 16)/255 for i in (0, 2, 4)] + [1])*32)
    image.pixels = row*512
    image.pack()
    material = bpy.data.materials.new("MT_ToonBase")
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Closest"
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "PaletteUV"
    links.new(uv.outputs["UV"], tex.inputs["Vector"])
    geometry = nodes.new("ShaderNodeNewGeometry")
    dot = nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = (.35, -.45, .82)
    links.new(geometry.outputs["Normal"], dot.inputs[0])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.name = "TwoBand"
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = (.52, .52, .52, 1)
    ramp.color_ramp.elements[1].position = .25
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    links.new(dot.outputs["Value"], ramp.inputs["Fac"])
    tint = nodes.new("ShaderNodeVertexColor")
    tint.layer_name = "MossTint"
    multiply = nodes.new("ShaderNodeMixRGB")
    multiply.blend_type = "MULTIPLY"
    multiply.inputs[0].default_value = 1
    links.new(tex.outputs["Color"], multiply.inputs[1])
    links.new(tint.outputs["Color"], multiply.inputs[2])
    shade = nodes.new("ShaderNodeMixRGB")
    shade.blend_type = "MULTIPLY"
    shade.inputs[0].default_value = 1
    links.new(multiply.outputs[0], shade.inputs[1])
    links.new(ramp.outputs["Color"], shade.inputs[2])
    emission = nodes.new("ShaderNodeEmission")
    links.new(shade.outputs[0], emission.inputs["Color"])
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(emission.outputs[0], output.inputs["Surface"])
    material["shading_note"] = "Original palette; two fixed normal-light bands, unlit toon"
    return material


def add_mesh(bpy, spec, material, collection):
    mesh = bpy.data.meshes.new(spec.name)
    mesh.from_pydata(spec.vertices, [], spec.faces)
    mesh.update()
    obj = bpy.data.objects.new(spec.name, mesh)
    collection.objects.link(obj)
    if spec.collider:
        obj.hide_render = True
        obj.display_type = "WIRE"
        return obj
    mesh.materials.append(material)
    mesh.uv_layers.new(name="PaletteUV")
    tint = mesh.color_attributes.new(name="MossTint", type="FLOAT_COLOR", domain="CORNER")
    # Adding CustomData attributes invalidates previously returned layer references.
    uv = mesh.uv_layers["PaletteUV"]
    top = max(v[2] for v in spec.vertices)
    for face, color in zip(mesh.polygons, spec.colors, strict=True):
        for loop in face.loop_indices:
            uv.data[loop].uv = ((color+.5)/16, .5)
            v = mesh.vertices[mesh.loops[loop].vertex_index].co
            moss = spec.moss and v.z > top*.55 and v.x + .45*v.y > -.25
            tint.data[loop].color = (.58, .95, .44, 1) if moss else (1, 1, 1, 1)
    return obj


def add_rig(bpy, prop, collection):
    armature = bpy.data.armatures.new(prop.name + "_Rig")
    rig = bpy.data.objects.new(prop.name + "_Rig", armature)
    collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    previous = None
    for name, head, tail in prop.bones:
        bone = armature.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if previous:
            bone.parent = previous
            bone.use_connect = True
        previous = bone
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.select_set(False)
    banner = bpy.data.objects[prop.name + "_Banner"]
    modifier = banner.modifiers.new("BannerFlutter", "ARMATURE")
    modifier.object = rig
    groups = [banner.vertex_groups.new(name=name) for name, _, _ in prop.bones]
    left = prop.bones[0][1][0]
    width = prop.clearance/4
    for vertex in banner.data.vertices:
        position = max(0, min(3, (vertex.co.x-left)/width-.5))
        lo, hi = int(position), min(3, int(position)+1)
        fraction = position-lo
        groups[lo].add([vertex.index], 1-fraction, "REPLACE")
        if hi != lo and fraction:
            groups[hi].add([vertex.index], fraction, "REPLACE")
    for i, pose in enumerate(rig.pose.bones):
        pose.rotation_mode = "XYZ"
        for frame in (1, 16, 31, 46, 61):
            pose.rotation_euler[0] = .065*math.sin((frame-1)*math.tau/60+i*.7)
            pose.keyframe_insert("rotation_euler", frame=frame, group=pose.name)
    rig.animation_data.action.name = prop.name + "_Rig|flutter"
    # VERIFY: action playback/deformation in UPBGE and final art review.
    rig["VERIFY_runtime"] = "Connect flutter action in level; inspect deformation on Tier B"


def verify(bpy, prop):
    """Validate actual reopened data, not just planned triangle counts."""
    total = 0
    evaluated_total = 0
    materials = set()
    visible = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for spec in prop.meshes:
        obj = bpy.data.objects[spec.name]
        assert tuple(obj.location) == (0, 0, 0), obj.name
        assert tuple(obj.rotation_euler) == (0, 0, 0), obj.name
        assert tuple(obj.scale) == (1, 1, 1), obj.name
        mesh = obj.data
        mesh.calc_loop_triangles()
        assert len(mesh.loop_triangles) == spec.tris, obj.name
        assert len(mesh.vertices) == len(spec.vertices)
        for vertex, expected in zip(mesh.vertices, spec.vertices, strict=True):
            assert all(abs(vertex.co[i]-expected[i]) < 1e-5 for i in range(3))
        if spec.collider:
            assert obj.hide_render
            assert obj["collision_shape"] == prop.collision
            continue
        total += len(mesh.loop_triangles)
        evaluated = obj.evaluated_get(depsgraph)
        evaluated_mesh = evaluated.to_mesh()
        evaluated_mesh.calc_loop_triangles()
        evaluated_total += len(evaluated_mesh.loop_triangles)
        evaluated.to_mesh_clear()
        materials.update(material.name for material in mesh.materials)
        visible.extend(v.co[:] for v in mesh.vertices)
        assert len(mesh.materials) == 1
        assert mesh.materials[0].name == "MT_ToonBase"
        assert not any(p.use_smooth for p in mesh.polygons)
        for face, color in zip(mesh.polygons, spec.colors, strict=True):
            for loop in face.loop_indices:
                uv = mesh.uv_layers["PaletteUV"].data[loop].uv
                assert abs(uv.x-(color+.5)/16) < 1e-6 and abs(uv.y-.5) < 1e-6
        if spec.moss:
            colors = {tuple(c.color) for c in mesh.color_attributes["MossTint"].data}
            assert len(colors) == 2
    assert total <= prop.budget
    assert evaluated_total <= prop.budget
    assert len(materials) <= 2
    assert abs(min(v[2] for v in visible)) < 1e-6
    for axis in (0, 1):
        assert abs(min(v[axis] for v in visible)+max(v[axis] for v in visible)) < 1e-5
    image = bpy.data.images["T_P0Palette_BC"]
    assert tuple(image.size) == (512, 512)
    assert image.packed_file
    assert image.packed_file.data[:8] == b"\x89PNG\r\n\x1a\n"
    for i, color in enumerate(PALETTE):
        pixel = (256*512+i*32+16)*4
        expected = [int(color[j:j+2], 16)/255 for j in (0, 2, 4)]
        assert all(abs(image.pixels[pixel+j]-expected[j]) < .005 for j in range(3))
    assert len(bpy.data.materials) == 1
    ramp = bpy.data.materials[0].node_tree.nodes["TwoBand"].color_ramp
    assert ramp.interpolation == "CONSTANT" and len(ramp.elements) == 2
    if prop.bones:
        rig = bpy.data.objects[prop.name + "_Rig"]
        assert len(rig.data.bones) == 4
        assert rig.animation_data.action is not None
        banner = bpy.data.objects[prop.name + "_Banner"]
        for v in banner.data.vertices:
            assert abs(sum(g.weight for g in v.groups)-1) < 1e-6
    for name, pos in prop.sockets:
        assert all(abs(bpy.data.objects[name].location[i]-pos[i]) < 1e-6 for i in range(3))
    return {"asset": prop.name, "triangles": total, "evaluated_triangles": evaluated_total,
            "budget": prop.budget,
            "collider_triangles": sum(m.tris for m in prop.meshes if m.collider),
            "material": "MT_ToonBase", "palette_uv": True, "base_pivot": True,
            "bones": len(prop.bones), "sockets": len(prop.sockets)}


def worker():
    import bpy

    # Session-only: never leave .blend1 backups in the asset library.
    bpy.context.preferences.filepaths.save_version = 0
    reports = []
    for prop in build_props():
        path = ROOT / "assets" / "props" / (prop.name + ".blend")
        if "--verify-only" in sys.argv:
            bpy.ops.wm.open_mainfile(filepath=str(path))
            report = verify(bpy, prop)
            reports.append(report)
            print("PROP_VERIFIED " + json.dumps(report), flush=True)
            continue
        if path.exists() and "--replace-locked" not in sys.argv:
            raise FileExistsError(path)
        # New standalone library; preserve the startup scene's graphics settings.
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for collection in list(bpy.data.collections):
            bpy.data.collections.remove(collection)
        for pool in (bpy.data.meshes, bpy.data.armatures, bpy.data.actions,
                     bpy.data.materials, bpy.data.images):
            for item in list(pool):
                pool.remove(item)
        collection = bpy.data.collections.new(prop.name)
        bpy.context.scene.collection.children.link(collection)
        material = palette_material(bpy)
        for mesh in prop.meshes:
            obj = add_mesh(bpy, mesh, material, collection)
            if mesh.collider:
                obj["collision_shape"] = prop.collision
                obj["VERIFY_runtime"] = "Configure Bullet collider in level scene"
        if prop.bones:
            add_rig(bpy, prop, collection)
        for name, position in prop.sockets:
            obj = bpy.data.objects.new(name, None)
            collection.objects.link(obj)
            obj.location = position
            obj.empty_display_size = .3
        collection["generator"] = "tools/blender/gen_p0_props.py"
        collection["original_work"] = "Original procedural River Rascals prop; no external assets"
        collection["VERIFY_runtime"] = "Collision/collectible bob/action hooks and Tier B pending"
        verify(bpy, prop)
        bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=True)
        bpy.ops.wm.open_mainfile(filepath=str(path))
        report = verify(bpy, prop)
        reports.append(report)
        print("PROP_VERIFIED " + json.dumps(report), flush=True)
    print("P0_PROPS_COMPLETE " + json.dumps(reports), flush=True)


if __name__ == "__main__":
    if "--worker" in sys.argv:
        worker()
    else:
        host()
