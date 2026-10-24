"""Generate `game/spike_engine.blend` for spike S-01 (engine feature probe).

Scene: dynamic box on a static plane, an animated cube (playAction), a camera,
an overlay HUD camera + collection, and the SpikeProbe Python Component from
`game/rr_components.py` (checks tic rates, aud, 2D filter, overlay, fps).

Run it WINDOWED (component registration through bpy segfaults in `blender -b` on
the Linux 0.50 build, found by P3):

    <upbge>/blender --python tools/blender/gen_spike_engine.py -- --out game/spike_engine.blend

If registration fails or crashes on a build, generate geometry only and attach
the component by hand once (Game Object Properties > Python Component > Add:
`rr_components.SpikeProbe`), then save the file and commit it through Git LFS:

    blender -b --python tools/blender/gen_spike_engine.py -- --no-components

The `[gen] COMPONENTS:` line reports attachment; a saved scene is always written.
"""
from __future__ import annotations

import argparse
import os
import sys

import bpy
from mathutils import Vector

COMPONENT = "rr_components.SpikeProbe"
HUD_COLLECTION = "SpikeHud"


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="gen_spike_engine.py")
    ap.add_argument("--out", default="game/spike_engine.blend")
    ap.add_argument("--no-components", action="store_true",
                    help="skip Python Component registration (headless-safe)")
    ap.add_argument("--allow-background-components", action="store_true",
                    help="try registration in `blender -b` (known to crash on 0.50 Linux)")
    ap.add_argument("--keep-open", action="store_true", help="do not quit when done")
    return ap.parse_args(argv)


def activate_collection(collection: bpy.types.Collection) -> None:
    """Make `collection` receive objects created by bpy.ops."""
    def find(layer):
        if layer.collection == collection:
            return layer
        for child in layer.children:
            hit = find(child)
            if hit:
                return hit
        return None

    layer = find(bpy.context.view_layer.layer_collection)
    if layer is None:
        raise RuntimeError("collection %s is not linked to the scene" % collection.name)
    bpy.context.view_layer.active_layer_collection = layer


def new_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def add_material(obj: bpy.types.Object, name: str, colour: tuple[float, float, float, float]) -> None:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = colour
    obj.data.materials.append(mat)


def add_cube(name: str, size: tuple[float, float, float],
             location: tuple[float, float, float]) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(scale=True)
    return obj


def add_ground() -> bpy.types.Object:
    ground = add_cube("SpikeGround", (20.0, 20.0, 0.2), (0.0, 0.0, -0.1))
    add_material(ground, "MT_SpikeGround", (0.25, 0.35, 0.3, 1.0))
    ground.game.physics_type = "STATIC"
    ground.game.collision_bounds_type = "BOX"
    return ground


def add_box() -> bpy.types.Object:
    box = add_cube("SpikeBox", (1.0, 1.0, 1.0), (0.0, 0.0, 3.0))
    add_material(box, "MT_SpikeBox", (0.8, 0.45, 0.2, 1.0))
    box.game.physics_type = "RIGID_BODY"
    box.game.mass = 5.0
    box.game.collision_bounds_type = "BOX"
    box.game.use_collision_bounds = True
    return box


def add_animated_cube() -> bpy.types.Object:
    """Playback target for the playAction signature check (no physics)."""
    anim = add_cube("SpikeAnim", (0.6, 0.6, 0.6), (2.0, 0.0, 1.0))
    add_material(anim, "MT_SpikeAnim", (0.3, 0.6, 0.8, 1.0))
    anim.game.physics_type = "NO_COLLISION"
    anim.location.z = 1.0
    bpy.context.scene.frame_set(1)
    anim.keyframe_insert(data_path="location", frame=1)
    anim.location.z = 2.0
    bpy.context.scene.frame_set(20)
    anim.keyframe_insert(data_path="location", frame=20)
    anim.location.z = 1.0
    bpy.context.scene.frame_set(1)
    if anim.animation_data and anim.animation_data.action:
        anim.animation_data.action.name = "SpikeBounce"
    return anim


def add_camera() -> bpy.types.Object:
    bpy.ops.object.camera_add(location=(9.0, -9.0, 6.0))
    cam = bpy.context.active_object
    cam.name = "SpikeCam"
    direction = Vector((0.0, 0.0, 1.0)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def add_light() -> None:
    bpy.ops.object.light_add(type="SUN", location=(4.0, -4.0, 8.0))
    sun = bpy.context.active_object
    sun.name = "SpikeSun"
    sun.data.energy = 3.0


def add_hud() -> tuple[bpy.types.Collection, bpy.types.Object]:
    """Overlay camera + collection, the UPBGE 0.3+ replacement for overlay scenes."""
    collection = new_collection(HUD_COLLECTION)
    activate_collection(collection)
    bpy.ops.object.camera_add(location=(0.0, 0.0, 10.0))
    cam = bpy.context.active_object
    cam.name = "SpikeHudCam"
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 10.0
    bpy.ops.object.text_add(location=(-3.0, -0.5, 0.0))
    label = bpy.context.active_object
    label.name = "SpikeHudLabel"
    label.data.body = "S-01 HUD"
    label.data.size = 0.8
    label.data.align_x = "CENTER"
    return collection, cam


def attach_component(obj: bpy.types.Object, component: str) -> bool:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    try:
        result = bpy.ops.logic.python_component_register(component_name=component)
    except Exception as exc:  # noqa: BLE001 - report, do not abort the scene
        print("[gen] COMPONENT FAILED: %s: %s" % (type(exc).__name__, exc))
        return False
    ok = "FINISHED" in result
    print("[gen] python_component_register(%s) -> %s" % (component, sorted(result)))
    return ok


def build(args: argparse.Namespace) -> bool:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "SpikeEngine"
    scene.render.fps = 60
    scene.frame_end = 120
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.color = (0.05, 0.06, 0.08)

    game = new_collection("SpikeEngine")
    activate_collection(game)
    add_ground()
    add_box()
    add_animated_cube()
    add_camera()
    add_light()

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.0, 0.0, 0.0))
    probe = bpy.context.active_object
    probe.name = "SpikeProbeRoot"

    hud_collection, _hud_cam = add_hud()
    activate_collection(game)

    attached = False
    if args.no_components:
        print("[gen] components skipped (--no-components)")
    elif bpy.app.background and not args.allow_background_components:
        print("[gen] components skipped: background mode is known to segfault on 0.50 Linux")
        print("[gen] rerun windowed, or attach by hand: Game Object Properties > Python Component > "
              "Add > %s on SpikeProbeRoot" % COMPONENT)
    else:
        attached = attach_component(probe, COMPONENT)
        if not attached:
            print("[gen] attach by hand: Game Object Properties > Python Component > Add > %s"
                  % COMPONENT)

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("[gen] saved %s" % out)
    print("[gen] scene: SpikeGround, SpikeBox, SpikeAnim(SpikeBounce), SpikeCam, SpikeSun, "
          "SpikeProbeRoot, %s/SpikeHudCam+SpikeHudLabel" % hud_collection.name)
    print("[gen] COMPONENTS: %s" % ("ATTACHED" if attached else "MANUAL"))
    return attached


def main() -> int:
    args = parse_args()
    build(args)
    if not args.keep_open:
        bpy.ops.wm.quit_blender()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
