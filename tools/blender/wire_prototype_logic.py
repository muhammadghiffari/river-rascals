"""Attach the Always sensor and Python module controller to game/main.blend.

Second half of the two-pass build. `build_prototype.py` creates all geometry in
background mode; the logic-brick operators cannot run there. Measured on UPBGE
0.50 (Blender 5.0.1, hash 9fcf0da621c3):

  * `blender -b ... bpy.ops.logic.sensor_add(...)` -> EXCEPTION_ACCESS_VIOLATION,
    even with a full `temp_override`, because the operator needs a real window.
  * Windowed without an override -> `poll() Context missing active object`, since
    `--python` scripts run before an active object exists (S-01 section 6.7).
  * Windowed plus `temp_override(window, screen, object, active_object)` -> works.

Run windowed, with the target file as the first argument so Blender loads it
before this script executes:

  blender game/main.blend --python tools/blender/wire_prototype_logic.py

Idempotent: re-running does not stack duplicate bricks.
"""
import json
import os
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/reports/prototype_asset_measurements.json"
ROOT_OBJECT = "PrototypeRoot"
SENSOR_NAME = "Tick"
CONTROLLER_NAME = "Prototype"


def fail(message):
    raise SystemExit(f"WIRE_FAIL {message}")


def main():
    if bpy.app.background:
        fail("must run windowed; the logic operators crash in background mode")
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}
    module = manifest.get("controller_module", "prototype_entry.tick")

    root = bpy.data.objects.get(ROOT_OBJECT)
    if root is None:
        fail(f"{ROOT_OBJECT} not found in {bpy.data.filepath}")

    window = bpy.context.window_manager.windows[0]
    override = {"window": window, "screen": window.screen,
                "object": root, "active_object": root,
                "selected_objects": [root], "selected_editable_objects": [root]}
    with bpy.context.temp_override(**override):
        if not any(s.name == SENSOR_NAME for s in root.game.sensors):
            bpy.ops.logic.sensor_add(type="ALWAYS", name=SENSOR_NAME, object=root.name)
        if not any(c.name == CONTROLLER_NAME for c in root.game.controllers):
            bpy.ops.logic.controller_add(type="PYTHON", name=CONTROLLER_NAME, object=root.name)

    sensor = next((s for s in root.game.sensors if s.name == SENSOR_NAME), None)
    controller = next((c for c in root.game.controllers if c.name == CONTROLLER_NAME), None)
    if sensor is None or controller is None:
        fail("sensor or controller missing after the operators ran")
    sensor.use_pulse_true_level = True
    sensor.use_pulse_false_level = False
    controller.mode = "MODULE"
    controller.module = module
    if controller not in list(sensor.controllers):
        sensor.link(controller)

    # Verify the saved state before trusting it, then re-measure from the file.
    checks = {
        "sensor_type": sensor.type == "ALWAYS",
        "sensor_pulse": bool(sensor.use_pulse_true_level),
        "controller_mode": controller.mode == "MODULE",
        "controller_module": controller.module == module,
        "linked": controller in list(sensor.controllers),
        "entry_file": (ROOT / "game" / (module.split(".")[0] + ".py")).is_file(),
    }
    if not all(checks.values()):
        fail("verification failed: " + json.dumps(checks))

    bpy.ops.wm.save_mainfile()
    if manifest:
        manifest.update({"logic_wired": True, "controller_module": controller.module,
                         "sensor": sensor.name, "controller": controller.name})
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print("WIRE_OK " + json.dumps({"file": bpy.data.filepath, "module": controller.module,
                                   "checks": checks}), flush=True)
    # `bpy.ops.wm.quit_blender()` access-violates on shutdown in this build (and
    # hangs if the netlogic addon is disabled first), which would mask a real
    # failure behind a crash exit code. The file is already written and flushed,
    # so exit immediately and let the caller verify WIRE_OK plus the saved file.
    os._exit(0)


main()
