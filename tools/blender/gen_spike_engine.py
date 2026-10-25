"""Generate `game/spike_engine.blend` for spike S-01 (engine feature probe).

Scene: dynamic box on a static plane, an animated cube (playAction), a camera,
an overlay HUD camera + collection, and the SpikeProbe Python Component from
`game/rr_components.py` (checks tic rates, aud, 2D filter, overlay, fps).

Run it in a dedicated WINDOWED process (the script clears the open scene):

    <upbge>/blender --python tools/blender/gen_spike_engine.py -- --out game/spike_engine.blend

If registration fails or crashes on a build, generate geometry only and attach
the component by hand once (Game Object Properties > Python Component > Add:
`rr_components.SpikeProbe`), then save the file and commit it through Git LFS:

    <upbge>/blender -b --python tools/blender/gen_spike_engine.py -- --no-components

The `[gen] COMPONENTS:` line reports attachment after the scene has been saved.

Reported Windows UPBGE 0.50 / Blender 5.0.1 evidence: context fields exist at
startup and after a 1 s timer, but add_cube fails after read_factory_settings
with missing active_object/object; headless generation succeeds. Context
invalidation by the reset is a hypothesis, NOT a confirmed root cause. See
docs/reports/S-01_engine_decision.md section 6.7. Cleanup and object creation
now use the data API; no active_object/object lookup is needed for construction.
Probe timing, units and gravity are explicit; graphics settings are untouched.

Headless construction/save/reopen validated on Windows UPBGE 0.50 / Blender
5.0.1 (see section 6.7). VERIFY: windowed execution, python_component_register
and actual gameplay/physics, action playback, overlay, audio and filter probes.
Background component registration stays opt-in because P3 reported a segfault.
"""
from __future__ import annotations

import argparse
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPONENT = "rr_components.SpikeProbe"
HUD_COLLECTION = "SpikeHud"

# Outward-facing quads of a cube whose vertices are listed -x-y-z first, then +z.
CUBE_QUADS = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
              (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


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


def reset_scene() -> bpy.types.Scene:
    """Empty the open file through the data API, keeping the live context valid.

    Avoid reloading the startup file mid-script (suspected context invalidation;
    section 6.7 of the S-01 report). Keep the current scene and master collection.
    """
    scene = bpy.context.scene
    scene.animation_data_clear()

    for other_scene in list(bpy.data.scenes):
        if other_scene != scene:
            bpy.data.scenes.remove(other_scene)

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    for collection in list(bpy.data.collections):
        if collection != scene.collection:
            bpy.data.collections.remove(collection)

    for datablocks in (bpy.data.meshes, bpy.data.cameras, bpy.data.lights,
                       bpy.data.curves, bpy.data.materials, bpy.data.actions):
        for datablock in list(datablocks):
            datablocks.remove(datablock)

    scene.world = None
    for world in list(bpy.data.worlds):
        bpy.data.worlds.remove(world)

    return scene


def prepare_scene(scene: bpy.types.Scene) -> None:
    """Set every scene setting the probe reads or relies on."""
    scene.name = "SpikeEngine"
    scene.render.fps = 60
    scene.render.fps_base = 1.0
    scene.frame_start = 1
    scene.frame_end = 120
    scene.frame_current = 1
    scene.use_gravity = True
    scene.gravity = (0.0, 0.0, -9.81)
    scene.unit_settings.scale_length = 1.0
    scene.game_settings.physics_engine = "BULLET"
    scene.game_settings.physics_gravity = 9.81
    scene.game_settings.fps = 60
    scene.world = bpy.data.worlds.new("World")
    scene.world.color = (0.05, 0.06, 0.08)


def new_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def add_material(obj: bpy.types.Object, name: str, colour: tuple[float, float, float, float]) -> None:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = colour
    obj.data.materials.append(mat)


def cube_mesh(name: str, size: tuple[float, float, float]) -> bpy.types.Mesh:
    """Box with `size` baked into the vertices, so no scale is left to apply."""
    half_x, half_y, half_z = (dim / 2.0 for dim in size)
    verts = [(-half_x, -half_y, -half_z), (half_x, -half_y, -half_z),
             (half_x, half_y, -half_z), (-half_x, half_y, -half_z),
             (-half_x, -half_y, half_z), (half_x, -half_y, half_z),
             (half_x, half_y, half_z), (-half_x, half_y, half_z)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], [list(quad) for quad in CUBE_QUADS])
    mesh.validate()
    mesh.update()
    return mesh


def add_cube(name: str, size: tuple[float, float, float],
             location: tuple[float, float, float],
             collection: bpy.types.Collection) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, cube_mesh(name, size))
    obj.location = location
    collection.objects.link(obj)
    return obj


def add_ground(collection: bpy.types.Collection) -> bpy.types.Object:
    ground = add_cube("SpikeGround", (20.0, 20.0, 0.2), (0.0, 0.0, -0.1), collection)
    add_material(ground, "MT_SpikeGround", (0.25, 0.35, 0.3, 1.0))
    ground.game.physics_type = "STATIC"
    ground.game.collision_bounds_type = "BOX"
    return ground


def add_box(collection: bpy.types.Collection) -> bpy.types.Object:
    box = add_cube("SpikeBox", (1.0, 1.0, 1.0), (0.0, 0.0, 3.0), collection)
    add_material(box, "MT_SpikeBox", (0.8, 0.45, 0.2, 1.0))
    box.game.physics_type = "RIGID_BODY"
    box.game.mass = 5.0
    box.game.collision_bounds_type = "BOX"
    box.game.use_collision_bounds = True
    return box


def add_animated_cube(collection: bpy.types.Collection) -> bpy.types.Object:
    """Playback target for the playAction signature check (no physics)."""
    anim = add_cube("SpikeAnim", (0.6, 0.6, 0.6), (2.0, 0.0, 1.0), collection)
    add_material(anim, "MT_SpikeAnim", (0.3, 0.6, 0.8, 1.0))
    anim.game.physics_type = "NO_COLLISION"
    scene = bpy.context.scene
    # frame_set first: it re-evaluates the action and would overwrite the value we
    # are about to key, leaving a flat action.
    scene.frame_set(1)
    anim.location.z = 1.0
    anim.keyframe_insert(data_path="location", frame=1)
    scene.frame_set(20)
    anim.location.z = 2.0
    anim.keyframe_insert(data_path="location", frame=20)
    scene.frame_set(1)
    if anim.animation_data and anim.animation_data.action:
        anim.animation_data.action.name = "SpikeBounce"
    return anim


def add_camera(collection: bpy.types.Collection) -> bpy.types.Object:
    cam = bpy.data.objects.new("SpikeCam", bpy.data.cameras.new("SpikeCam"))
    cam.location = (9.0, -9.0, 6.0)
    direction = Vector((0.0, 0.0, 1.0)) - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def add_light(collection: bpy.types.Collection) -> bpy.types.Object:
    light = bpy.data.lights.new("SpikeSun", type="SUN")
    light.energy = 3.0
    sun = bpy.data.objects.new("SpikeSun", light)
    sun.location = (4.0, -4.0, 8.0)
    collection.objects.link(sun)
    return sun


def add_probe_root(collection: bpy.types.Collection) -> bpy.types.Object:
    probe = bpy.data.objects.new("SpikeProbeRoot", None)
    probe.empty_display_type = "PLAIN_AXES"
    collection.objects.link(probe)
    return probe


def add_hud() -> tuple[bpy.types.Collection, bpy.types.Object]:
    """Overlay camera + collection, the UPBGE 0.3+ replacement for overlay scenes."""
    collection = new_collection(HUD_COLLECTION)

    cam_data = bpy.data.cameras.new("SpikeHudCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 10.0
    cam = bpy.data.objects.new("SpikeHudCam", cam_data)
    cam.location = (0.0, 0.0, 10.0)
    collection.objects.link(cam)

    text_data = bpy.data.curves.new("SpikeHudLabel", type="FONT")
    text_data.body = "S-01 HUD"
    text_data.size = 0.8
    text_data.align_x = "CENTER"
    label = bpy.data.objects.new("SpikeHudLabel", text_data)
    label.location = (-3.0, -0.5, 0.0)
    collection.objects.link(label)
    return collection, cam


def attach_component(obj: bpy.types.Object, component: str) -> bool:
    """Component creation is the one step that still needs a real operator + context."""
    view_layer = bpy.context.view_layer
    view_layer.update()
    for other in view_layer.objects:
        other.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj
    try:
        result = bpy.ops.logic.python_component_register(component_name=component)
    except Exception as exc:  # noqa: BLE001 - report, do not abort the scene
        print("[gen] COMPONENT FAILED: %s: %s" % (type(exc).__name__, exc))
        return False
    ok = "FINISHED" in result
    print("[gen] python_component_register(%s) -> %s" % (component, sorted(result)))
    return ok


def build(args: argparse.Namespace) -> bool:
    # The component module lives in game/; make it importable for the register operator.
    game_dir = os.path.join(ROOT, "game")
    if game_dir not in sys.path:
        sys.path.insert(0, game_dir)

    scene = reset_scene()
    prepare_scene(scene)

    game = new_collection("SpikeEngine")
    add_ground(game)
    add_box(game)
    add_animated_cube(game)
    add_camera(game)
    add_light(game)
    probe = add_probe_root(game)

    hud_collection, _hud_cam = add_hud()

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
    attached = build(args)
    rc = 0 if (attached or args.no_components) else 2
    if not args.keep_open:
        bpy.ops.wm.quit_blender()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
