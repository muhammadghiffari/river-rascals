"""Rebuild game/main.blend in UPBGE background; source libraries are read-only.

Acquire `git lfs lock game/main.blend` before running. No component registration
or editor context is needed: an Always sensor drives a Python module controller.
"""
import hashlib
import json
import math
import random
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / "game/settings/prototype.json").read_text())
RNG = random.Random(2317)
SOURCES = ["assets/raft/RF_RaftT1.blend", "assets/raft/RF_Oar.blend",
           "assets/props/PR_RockLarge.blend"]
# Single source of truth for the controller target; the windowed wiring pass
# reads it back out of the manifest so the two passes cannot drift apart.
CONTROLLER_MODULE = "prototype_entry.tick"


def material(name, color, emission=0.18):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = 0.82
    bsdf.inputs["Emission Color"].default_value = (*color, 1)
    bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def physics(obj, kind="NO_COLLISION", bounds="BOX"):
    obj.game.physics_type = kind
    if kind != "NO_COLLISION":
        obj.game.use_collision_bounds = True
        obj.game.collision_bounds_type = bounds
        obj.game.collision_margin = 0.05
    return obj


def cube(name, location, size, mat, solid=False):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    physics(obj, "STATIC" if solid else "NO_COLLISION")
    return obj


def cone(name, location, radius, depth, mat, vertices=7, top=0):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius, radius2=top,
                                  depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    physics(obj)
    return obj


def join(objects, name):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    objects[0].name = name
    return objects[0]


def load_meshes(path):
    with bpy.data.libraries.load(str(ROOT / path), link=False) as (source, target):
        target.objects = [name for name in source.objects if not name.endswith("_COL")
                          and not name.startswith("BuoySample")]
    result = []
    for obj in target.objects:
        if obj.type == "MESH":
            bpy.context.scene.collection.objects.link(obj)
            obj.parent = None
            physics(obj)
            result.append(obj)
    return result


def main():
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCES}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "CatalnaCreek"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.game_settings.resolution_x, scene.game_settings.resolution_y = 1280, 720
    scene.game_settings.fps = 60
    scene.game_settings.use_frame_rate = True
    scene.game_settings.vsync = "ON"
    scene.game_settings.show_mouse = True
    scene.game_settings.exit_key = "F12"
    scene.game_settings.physics_gravity = 9.81
    scene.world = bpy.data.worlds.new("EN_SkyDay")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.25, 0.4, 0.48, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.7
    scene.view_settings.view_transform = "Standard"

    grass = material("MT_Meadow", (0.26, 0.46, 0.19))
    bank = material("MT_Sand", (0.67, 0.53, 0.3))
    water = material("MT_Water", (0.035, 0.38, 0.43), 0.35)
    foam = material("MT_Foam", (0.46, 0.8, 0.75), 0.5)
    pine = material("MT_Pine", (0.075, 0.26, 0.14))
    leaf = material("MT_Leaf", (0.32, 0.49, 0.15))
    trunk = material("MT_Trunk", (0.24, 0.13, 0.075))
    coral = material("MT_Coral", (0.95, 0.24, 0.12))
    cream = material("MT_Cream", (0.98, 0.86, 0.55))

    cube("EN_RiverStrip", (0, 96, -0.12), (22, 232, 0.2), water)
    for side in (-1, 1):
        cube(f"EN_Bank_{side}", (side * 14, 96, -0.65), (6, 232, 2), bank, True)
        cube(f"EN_Meadow_{side}", (side * 29, 96, -0.35), (30, 232, 2), grass)
    # Original procedural trees and shrubs, joined into material batches.
    plants = []
    for side in (-1, 1):
        for index in range(37):
            x = side * RNG.uniform(14, 28)
            y = index * 6 - 12 + RNG.uniform(-2, 2)
            height = RNG.uniform(3.5, 6.8)
            plants.append(cone("EN_Trunk", (x, y, height / 2), 0.22, height, trunk, top=0.13))
            for tier in range(3):
                plants.append(cone("EN_Pine", (x, y, height * (0.52 + tier * 0.19)),
                                   height * (0.32 - tier * 0.055), height * 0.5, pine))
            bx = side * RNG.uniform(11.8, 13.5)
            plants.append(cone("EN_Bush", (bx, y + 1, 0.8), 0.9, 1.2, leaf, top=0.3))
    join(plants, "EN_OriginalVegetation")
    foam_parts = []
    for _index in range(95):
        foam_parts.append(cube("VX_Ripple", (RNG.uniform(-10, 10), RNG.uniform(-15, 205), 0.015),
                               (RNG.uniform(0.4, 1.5), 0.045, 0.012), foam))
    join(foam_parts, "VX_RiverRipples")

    hull = load_meshes(SOURCES[0])[0]
    hull.name = "RF_RaftVisual"
    original_dimensions = list(hull.dimensions)
    # Undo the approved asset's documented nonuniform squash, recovering the
    # original GLB aspect ratio; then use one 4.8m-long rubber-raft scale.
    hull.dimensions = (CFG["raft_width"], CFG["raft_length"], CFG["raft_height"])
    bpy.context.view_layer.objects.active = hull
    bpy.ops.object.select_all(action="DESELECT")
    hull.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    hull.location = (0, 0, 0)
    body = cube("RF_RaftT1", (0, CFG["start_y"], 0.32),
                (CFG["raft_width"], CFG["raft_length"], CFG["raft_height"]), coral)
    physics(body, "RIGID_BODY")
    body.game.mass = CFG["mass"]
    # rr.core.prototype models heave and yaw only, so Bullet must not roll or pitch
    # the hull. docs/07 section 2 also keeps the raft awake for the whole run:
    # "No Sleeping" (use_sleep) disables auto-deactivation.
    body.game.lock_rotation_x = True
    body.game.lock_rotation_y = True
    body.game.use_sleep = True
    body.game.damping = 0.03
    body.game.rotation_damping = 0.1
    body.game.use_ghost = False
    body.game.use_actor = True
    body.hide_render = True
    hull.parent = body
    oar = load_meshes(SOURCES[1])[0]
    oar.name = "RF_Oar_R"
    oar.parent = body
    oar.location = (1.0, 0.0, 0.35)
    oar.rotation_euler = (0, 0.3, -0.25)
    left = oar.copy()
    left.name = "RF_Oar_L"
    scene.collection.objects.link(left)
    left.location = (-1, 0, 0.35)
    left.rotation_euler = (0, 0.3, math.pi + 0.25)

    rocks = load_meshes(SOURCES[2])
    layout = [(0, 24), (-6, 38), (5, 50), (-4, 65), (6, 80),
              (-6, 105), (5, 122), (-4, 140), (6, 158)]
    for i, (x, y) in enumerate(layout):
        source = rocks[i % len(rocks)]
        obj = source.copy()
        scene.collection.objects.link(obj)
        obj.name = f"PR_RockObstacle_{i:02}"
        obj.location = (x, y, -0.3)
        obj.scale = (0.8, 0.8, 0.8)
        obj.rotation_euler.z = i * 0.7
        physics(obj, "STATIC", "CONVEX_HULL")
    for obj in rocks:
        bpy.data.objects.remove(obj, do_unlink=True)

    for name, y, mat in (("Checkpoint", 90, cream), ("Finish", CFG["finish_y"], coral)):
        for side in (-1, 1):
            cone(f"PR_{name}Post_{side}", (side * 9, y, 2), 0.18, 4.3, trunk, top=0.18)
        cube(f"PR_{name}Banner", (0, y, 4), (18.3, 0.18, 0.65), mat)
        for i in range(12):
            cone(f"PR_{name}Pennant_{i}", (-8.25 + i * 1.5, y, 3.4), 0.35, 0.7, mat, 3)

    sun_data = bpy.data.lights.new("EN_Sun", "SUN")
    sun_data.energy = 2.0
    sun_data.angle = 0.15
    sun = bpy.data.objects.new("EN_Sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (0.5, -0.4, -0.6)
    # Follow camera: prototype_entry.CAMERA_OFFSET slides this rig along the river,
    # so the rest pose must already frame the raft with the water ahead visible.
    camera = bpy.data.objects.new("Cam_Main", bpy.data.cameras.new("Cam_Main"))
    scene.collection.objects.link(camera)
    camera.location = (0, CFG["start_y"] - 10.5, 6.5)
    aim = Vector((0, CFG["start_y"] + 8, 0))
    camera.rotation_euler = (aim - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 35
    camera.data.clip_end = 260
    scene.camera = camera

    # HUD text parented in camera space. Identity parent-inverse keeps the local
    # offsets below in camera coordinates; Blender text faces +Z, the camera looks
    # down -Z, so a child at negative local z faces the lens. At z=-2 with a 35mm
    # lens on a 36mm sensor the visible half-extents are x 1.027 and y 0.578.
    hud_objects = []
    for name, location, size, align, initial in (
        ("UI_HudText", (-0.96, 0.54, -2.0), 0.045, "LEFT", "MENU"),
        ("UI_PromptText", (0.0, -0.09, -2.0), 0.060, "CENTER", "RIVER RASCALS"),
    ):
        bpy.ops.object.text_add(location=(0, 0, 0))
        text = bpy.context.object
        text.name = name
        text.data.name = name
        text.data.body = initial
        text.data.size = size
        text.data.align_x = align
        text.data.align_y = "TOP"
        text.data.materials.append(cream)
        physics(text)
        text.parent = camera
        text.matrix_parent_inverse = Matrix.Identity(4)
        text.location = location
        text.rotation_euler = (0, 0, 0)
        hud_objects.append(text)

    root = bpy.data.objects.new("PrototypeRoot", None)
    scene.collection.objects.link(root)
    # The Always sensor and Python controller are NOT added here. In this UPBGE
    # build `bpy.ops.logic.sensor_add` dereferences null in `-b` (access violation)
    # and its poll needs a real window, while the object-creation operators above
    # need the background context (S-01 section 6.7). Geometry is therefore built
    # headless and `tools/blender/wire_prototype_logic.py` attaches the logic
    # bricks in a second, windowed pass. `tools/build_prototype_scene.py` runs both.
    for image in bpy.data.images:
        if image.source == "FILE":
            image.pack()
    scene.render.image_settings.file_format = "PNG"
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "game/main.blend"))
    tris = sum(sum(len(poly.vertices) - 2 for poly in obj.data.polygons)
               for obj in scene.objects if obj.type == "MESH")
    # The approved asset was squashed non-uniformly to a historical 2.4x3.2x0.4 box.
    # Rescaling it to the configured rubber-raft size must restore a single uniform
    # factor against the original GLB, otherwise the hull is visibly distorted again.
    source_wlh = (11.964097023010254, 23.645095825195312, 4.30204439163208)
    runtime_wlh = (CFG["raft_width"], CFG["raft_length"], CFG["raft_height"])
    ratios = [runtime_wlh[i] / source_wlh[i] for i in range(3)]
    assert max(ratios) - min(ratios) < 1e-6, f"raft scale is not uniform: {ratios}"
    manifest = {"source_sha256": hashes, "approved_raft_dimensions": original_dimensions,
                "original_glb_dimensions_xyz": [11.964097023010254, 4.30204439163208, 23.645095825195312],
                "source_width_length_height": list(source_wlh),
                "runtime_width_length_height": list(runtime_wlh),
                "uniform_scale_from_source": sum(ratios) / 3,
                "runtime_raft_dimensions": list(hull.dimensions), "scene_triangles": tris,
                "scene_objects": len(scene.objects), "rock_obstacles": len(layout),
                "hud_objects": [obj.name for obj in hud_objects],
                "controller_module": CONTROLLER_MODULE,
                "logic_wired": False,
                "vegetation": "original seeded procedural geometry, seed 2317"}
    assert tris < 250000
    assert hashes == {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SOURCES}
    out = ROOT / "docs/reports/prototype_asset_measurements.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print("PROTOTYPE_ASSETS", json.dumps(manifest))


if __name__ == "__main__":
    main()
