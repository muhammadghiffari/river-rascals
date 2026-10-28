"""Load game/main.blend and prove its contents. Run with: blender -b game/main.blend --python ...

This is the evidence that the scene exists and loads, independent of whichever
build pass wrote it. Opening the file is itself part of the check: a corrupt or
half-written .blend fails before any assertion runs. Prints VERIFY_OK with the
measurements on success, VERIFY_FAIL with the reasons otherwise.
"""
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
CFG = json.loads((ROOT / "game/settings/prototype.json").read_text())

REQUIRED = ["PrototypeRoot", "RF_RaftT1", "RF_RaftVisual", "RF_Oar_L", "RF_Oar_R",
            "Cam_Main", "UI_HudText", "UI_PromptText", "EN_RiverStrip",
            "EN_OriginalVegetation", "VX_RiverRipples", "EN_Sun"]
problems = []
report = {}


def check(condition, message):
    if not condition:
        problems.append(message)


scene = bpy.context.scene
objects = {obj.name: obj for obj in scene.objects}
report["file"] = bpy.data.filepath
report["scene"] = scene.name
report["object_count"] = len(objects)

for name in REQUIRED:
    check(name in objects, f"missing object {name}")
rocks = sorted(n for n in objects if n.startswith("PR_RockObstacle_"))
report["rock_obstacles"] = len(rocks)
check(len(rocks) >= 9, f"expected at least 9 rock obstacles, found {len(rocks)}")

# --- raft body: physics contract that rr.core.prototype assumes -------------
body = objects.get("RF_RaftT1")
if body is None:
    problems.append("RF_RaftT1 absent, cannot check physics")
else:
    game = body.game
    report["raft"] = {
        "physics_type": game.physics_type, "mass": game.mass,
        "bounds": game.collision_bounds_type, "lock_rot_x": game.lock_rotation_x,
        "lock_rot_y": game.lock_rotation_y, "lock_rot_z": game.lock_rotation_z,
        "no_sleeping": game.use_sleep, "ghost": game.use_ghost,
        "dimensions": list(body.dimensions),
    }
    check(game.physics_type == "RIGID_BODY", f"raft physics is {game.physics_type}")
    check(abs(game.mass - CFG["mass"]) < 1e-3, f"raft mass {game.mass} != {CFG['mass']}")
    check(game.collision_bounds_type == "BOX", f"raft bounds {game.collision_bounds_type}")
    check(game.lock_rotation_x and game.lock_rotation_y, "roll/pitch are not locked")
    check(not game.lock_rotation_z, "yaw must stay free for steering")
    check(game.use_sleep, "raft may sleep mid-river (use_sleep must be True)")
    check(not game.use_ghost, "raft must collide, not ghost")
    for axis, key in enumerate(("raft_width", "raft_length", "raft_height")):
        check(abs(body.dimensions[axis] - CFG[key]) < 1e-3,
              f"raft {key} is {body.dimensions[axis]:.4f}, expected {CFG[key]:.4f}")

visual = objects.get("RF_RaftVisual")
if visual is not None:
    report["raft_visual_parent"] = visual.parent.name if visual.parent else None
    check(visual.parent is body, "RF_RaftVisual is not parented to the body")
    # The hull must be a uniform scale of the original GLB, not the old squash.
    source = (11.964097023010254, 23.645095825195312, 4.30204439163208)
    ratios = [visual.dimensions[i] / source[i] for i in range(3)]
    report["visual_scale_ratios"] = ratios
    check(max(ratios) - min(ratios) < 1e-4,
          f"hull is non-uniformly scaled (distorted): {ratios}")

for name in ("RF_Oar_L", "RF_Oar_R"):
    oar = objects.get(name)
    if oar is not None:
        check(oar.parent is body, f"{name} is not parented to the raft body")

for name in rocks:
    rock = objects[name]
    check(rock.game.physics_type == "STATIC", f"{name} physics {rock.game.physics_type}")
    check(rock.game.collision_bounds_type == "CONVEX_HULL",
          f"{name} bounds {rock.game.collision_bounds_type}")

# --- HUD text is runtime-writable ------------------------------------------
for name in ("UI_HudText", "UI_PromptText"):
    text = objects.get(name)
    if text is not None:
        check(text.type == "FONT", f"{name} is {text.type}, not FONT")
        check(text.parent is objects.get("Cam_Main"), f"{name} is not parented to the camera")

# --- logic bricks ----------------------------------------------------------
root = objects.get("PrototypeRoot")
if root is None:
    problems.append("PrototypeRoot absent, cannot check logic")
else:
    sensors = {s.name: s for s in root.game.sensors}
    controllers = {c.name: c for c in root.game.controllers}
    report["sensors"] = {n: s.type for n, s in sensors.items()}
    report["controllers"] = {n: (c.mode, getattr(c, "module", None)) for n, c in controllers.items()}
    check(bool(sensors), "PrototypeRoot has no sensor: the game loop will never tick")
    check(bool(controllers), "PrototypeRoot has no controller")
    sensor = sensors.get("Tick")
    controller = controllers.get("Prototype")
    if sensor is None or controller is None:
        problems.append("expected a 'Tick' sensor and a 'Prototype' controller")
    else:
        check(sensor.type == "ALWAYS", f"Tick sensor is {sensor.type}")
        check(sensor.use_pulse_true_level, "Tick sensor does not pulse every frame")
        check(controller.mode == "MODULE", f"controller mode is {controller.mode}")
        check(controller.module == "prototype_entry.tick",
              f"controller module is {controller.module!r}")
        check(controller in list(sensor.controllers), "sensor is not linked to the controller")
        entry = ROOT / "game" / "prototype_entry.py"
        check(entry.is_file(), f"controller target missing on disk: {entry}")

# --- scene/game settings ---------------------------------------------------
gs = scene.game_settings
report["game_settings"] = {"fps": gs.fps, "gravity": gs.physics_gravity,
                           "resolution": [gs.resolution_x, gs.resolution_y],
                           "physics_engine": gs.physics_engine, "exit_key": gs.exit_key}
check(gs.fps == 60, f"logic fps is {gs.fps}, expected 60")
check(abs(gs.physics_gravity - 9.81) < 1e-4, f"gravity is {gs.physics_gravity}")
check(gs.physics_engine == "BULLET", f"physics engine is {gs.physics_engine}")
check(scene.camera is not None, "scene has no active camera")

tris = sum(sum(len(poly.vertices) - 2 for poly in obj.data.polygons)
           for obj in scene.objects if obj.type == "MESH")
report["scene_triangles"] = tris
check(tris < 250000, f"{tris} triangles exceeds the Tier B budget of 250000")

report["problems"] = problems
if problems:
    print("VERIFY_FAIL " + json.dumps(report, indent=2), flush=True)
    sys.exit(1)
print("VERIFY_OK " + json.dumps(report), flush=True)
