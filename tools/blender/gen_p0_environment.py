"""Export only new original P0 libraries; lock every output before Blender runs.

Run with normal Python. --verify-only reopens and checks existing deliverables.
Uses UPBGE_PATH/find_exe; never edits scene graphics or existing assets.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from math import sin
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools"), str(Path(__file__).parent)]

from run_game import find_exe

from rr.core.environment_geometry import PALETTE, Mesh, bank, bush, palette_uv, pine, river_strip

OUTPUT = ROOT / "assets" / "environment"
NAMES = ([f"EN_PineTree_{i:02}" for i in range(1, 4)]
         + [f"EN_Bush_{i:02}" for i in range(1, 4)]
         + [f"EN_BankTile_{i:02}" for i in range(1, 5)]
         + ["EN_RiverStrip", "EN_SkyDay"])


def make_object(name: str, source: Mesh, material: object, collection: object) -> object:
    """Translate indexed mesh and attributes without operators or transforms."""
    import bpy

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(source.vertices, [], source.faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    mesh.materials.append(material)
    uv = mesh.uv_layers.new(name="FlowUV" if source.uv else "PaletteUV")
    for polygon, color in zip(mesh.polygons, source.colors, strict=True):
        for index in polygon.loop_indices:
            uv.data[index].uv = (source.uv[mesh.loops[index].vertex_index] if source.uv
                                 else palette_uv(color))
    if source.sway:
        colors = mesh.color_attributes.new(name="Sway", type="FLOAT_COLOR", domain="POINT")
        for entry, weight in zip(colors.data, source.sway, strict=True):
            entry.color = (weight, weight, weight, 1)
        obj["VERIFY"] = "Sway shader and LOD selection hookup in runtime scene"
    if source.foam:
        group = obj.vertex_groups.new(name="FoamAnchor")
        group.add(source.foam, 1., "REPLACE")
        obj["placement_z"] = -.3
    return obj


def export(name: str, replace: bool = False) -> None:
    import bpy
    from environment_materials import sky, toon

    path = OUTPUT / f"{name}.blend"
    if path.exists() and not replace:
        raise FileExistsError(f"Refusing overwrite: {path}")
    if name == "EN_SkyDay":
        bpy.data.libraries.write(str(path), {sky()}, fake_user=True)
        return
    collection = bpy.data.collections.new(name)
    material = toon()
    if name.startswith("EN_PineTree"):
        variant = int(name[-2:]) - 1
        make_object(name, pine(variant), material, collection)
        low = make_object(name + "_LOD1", pine(variant, True), material, collection)
        low.hide_render = True
        low.hide_viewport = True
    elif name.startswith("EN_Bush"):
        make_object(name, bush(int(name[-2:]) - 1), material, collection)
    elif name.startswith("EN_BankTile"):
        source = bank(int(name[-2:]) - 1)
        make_object(name, source, material, collection)
        collider = make_object(name + "_COL", source, material, collection)
        collider.hide_render, collider.display_type = True, "WIRE"
        collider["VERIFY"] = "Static mesh collision group/margin hookup in runtime scene"
    else:
        # Geometry-only reference: deliberately not a claim of MT_Water completion.
        water = bpy.data.materials.new("MT_Water")
        water["VERIFY"] = "Reference only: wave/depth/foam/flow shader runtime scope separate"
        points = tuple((1.5 * sin(i / 8), float(i)) for i in range(49))
        obj = make_object(name, river_strip(points), water, collection)
        obj["VERIFY"] = water["VERIFY"]
    bpy.data.libraries.write(str(path), {collection}, fake_user=True)


def verify(name: str) -> dict:
    """Reopen actual saved datablocks; fail closed on strict per-row limits."""
    import bpy

    path = OUTPUT / f"{name}.blend"
    with bpy.data.libraries.load(str(path)) as (source, target):
        target.collections = source.collections
        target.worlds = source.worlds
    collections = target.collections
    objects = [obj for collection in collections for obj in collection.all_objects]
    result = {}
    if name == "EN_SkyDay":
        assert not objects and len(target.worlds) == 1
        world = target.worlds[0]
        assert world.use_nodes and any(n.type == "VALTORGB" for n in world.node_tree.nodes)
        assert all(scene.world != world for scene in bpy.data.scenes)
        return {name: {"triangles": 0, "world": True, "scene_assigned": False}}
    expected = 2 if name.startswith(("EN_PineTree", "EN_BankTile")) else 1
    assert len(objects) == expected, (name, len(objects))
    assert len({material for obj in objects for material in obj.data.materials}) <= 2
    for collection in collections:
        bpy.context.scene.collection.children.link(collection)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        mesh = obj.data
        mesh.calc_loop_triangles()
        tris = len(mesh.loop_triangles)
        # These library objects intentionally have no modifiers/shape keys:
        # evaluated geometry equals the saved mesh, with no hidden subdivision.
        assert not obj.modifiers and not mesh.shape_keys
        evaluated = obj.evaluated_get(depsgraph).data
        evaluated.calc_loop_triangles()
        assert len(evaluated.loop_triangles) == tris
        budget = (200 if "_LOD1" in obj.name or "Bush" in obj.name else
                  800 if "PineTree" in obj.name else 1500 if "BankTile" in obj.name else 3000)
        assert 0 < tris <= budget, (obj.name, tris, budget)
        assert all(triangle.area > 1e-10 for triangle in mesh.loop_triangles)
        assert tuple(obj.location) == (0, 0, 0) and tuple(obj.scale) == (1, 1, 1)
        assert tuple(obj.rotation_euler) == (0, 0, 0)
        assert len(mesh.materials) == 1 and mesh.uv_layers.active
        uv = mesh.uv_layers.active.data
        if name != "EN_RiverStrip":
            assert mesh.materials[0].name.startswith("MT_ToonBase")
            textures = [n.image for n in mesh.materials[0].node_tree.nodes if n.type == "TEX_IMAGE"]
            assert len(textures) == 1 and textures[0].packed_file
            assert textures[0].file_format == "PNG"
            assert textures[0].name == "T_P0Palette_BC"
            assert tuple(textures[0].size) == (512, 512)
            pixels = textures[0].pixels[:]
            for row in (0, 256, 511):
                for stripe, color in enumerate(PALETTE):
                    expected = tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))
                    for column in (stripe * 32, stripe * 32 + 16, stripe * 32 + 31):
                        offset = (row * 512 + column) * 4
                        assert all(abs(pixels[offset + i] - expected[i]) < .005 for i in range(3))
            assert all(abs(v.uv.y - .5) < 1e-6 for v in uv)
            assert all(abs(v.uv.x * 16 % 1 - .5) < 1e-6 for v in uv)
            assert min(v.co.z for v in mesh.vertices) == 0
        else:
            assert mesh.materials[0].name.startswith("MT_Water")
            assert "VERIFY" in mesh.materials[0]
            assert max(v.uv.y for v in uv) > 48
        if "PineTree" in name:
            weights = [c.color[0] for c in mesh.color_attributes["Sway"].data]
            assert min(weights) == 0 and max(weights) == 1
        if "BankTile" in name:
            group = obj.vertex_groups["FoamAnchor"].index
            anchors = [v for v in mesh.vertices if any(g.group == group for g in v.groups)]
            assert len(anchors) == 9
            assert all(abs(v.co.z - .3) < 1e-6 for v in anchors)
            assert min(v.co.z for v in mesh.vertices if v.co.z > 1e-6) >= .3 - 1e-6
            edge_uses = {}
            for polygon in mesh.polygons:
                for edge in polygon.edge_keys:
                    edge_uses[edge] = edge_uses.get(edge, 0) + 1
            assert all(count == 2 for count in edge_uses.values()), "bank must be closed"
        result[obj.name] = {"triangles": tris, "budget": budget, "uv": mesh.uv_layers.active.name,
                            "materials": len(mesh.materials), "identity_transform": True}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--replace-locked", action="store_true",
                        help="Explicitly regenerate outputs after verifying own LFS locks")
    args = parser.parse_args()
    if not args.verify_only:
        for name in NAMES:
            if (OUTPUT / f"{name}.blend").exists() and not args.replace_locked:
                raise FileExistsError(name)
        # Confirm existing own locks through the server, otherwise acquire them.
        locks = subprocess.run(["git", "lfs", "locks", "--verify", "--json"], cwd=ROOT,
                               check=True, capture_output=True, text=True)
        ours = {entry["path"] for entry in json.loads(locks.stdout).get("ours", [])}
        for name in NAMES:
            path = f"assets/environment/{name}.blend"
            if path not in ours:
                subprocess.run(["git", "lfs", "lock", path], cwd=ROOT, check=True)
        OUTPUT.mkdir(parents=True, exist_ok=True)
    executable = find_exe("blender")
    for name in NAMES:
        subprocess.run([executable, "-b", "--python-exit-code", "1", "--python", __file__,
                        "--", ("verify" if args.verify_only else
                                "replace" if args.replace_locked else "export"), name], cwd=ROOT, check=True)


if __name__ == "__main__":
    if "--" in sys.argv:
        operation, asset = sys.argv[sys.argv.index("--") + 1:]
        if operation in ("export", "replace"):
            export(asset, replace=operation == "replace")
        else:
            print("[environment] " + json.dumps(verify(asset), sort_keys=True))
    else:
        main()
