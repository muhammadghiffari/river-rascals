"""Headless check that the MCP for Blender addon loads in this Blender/UPBGE build.

Run via:
  & "$env:UPBGE_PATH\blender.exe" -b --factory-startup --python tools/blender/probe_mcp_addon.py

Proves (docs/08 section 3 step 3, spike S-04): the addon module is importable and
`addon_enable` registers its panel, operators and scene properties, then
unregisters cleanly. It does NOT open the MCP socket, so it says nothing about
the OpenCode <-> addon round-trip (that needs Blender open plus `opencode mcp list`).
`--factory-startup` keeps the enable in memory: userpref.blend is not written.
Prints lines starting with [probe]; exit code 1 when the addon cannot be enabled.
"""
import sys

import bpy

MOD = "blender_mcp"


def report(label, value):
    print("[probe] %s = %s" % (label, value))


def enable(module_name):
    """Enable the addon and report whether it actually registered."""
    report("version_string", bpy.app.version_string)
    report("pre_enabled", module_name in bpy.context.preferences.addons)
    try:
        bpy.ops.preferences.addon_enable(module=module_name)
    except Exception as exc:  # noqa: BLE001 - any failure is the result we report
        report("enable_result", "FAIL %s: %s" % (type(exc).__name__, exc))
        return False
    enabled = module_name in bpy.context.preferences.addons
    report("enable_result", "OK" if enabled else "FAIL not in preferences.addons")
    report("has_panel_class", hasattr(bpy.types, "BLENDERMCP_PT_Panel"))
    report("has_start_operator", hasattr(bpy.ops.blendermcp, "start_server"))
    report("has_auto_start_property", hasattr(bpy.types.Scene, "blendermcp_auto_start_server"))
    return enabled


def shutdown(module_name):
    """Drop the deferred auto-start timer.

    The addon classes are left registered: Blender unregisters them at exit, and
    calling `unregister()` ourselves makes Blender's own cleanup raise a
    harmless "may not be registered" traceback.
    """
    module = sys.modules.get(module_name)
    if module is None:
        return
    try:
        module._blendermcp_unregister_auto_start()
        report("auto_start_timer", "cleared")
    except Exception as exc:  # noqa: BLE001
        report("auto_start_timer", "FAIL %s: %s" % (type(exc).__name__, exc))


def main():
    ok = enable(MOD)
    shutdown(MOD)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
