#!/usr/bin/env python3
"""Generate the F-05 baseline benchmark scenes (UPBGE, bpy only).

Run it with the pinned build, in the *normal* (non-background) executable:

    "$UPBGE_PATH/blender" --python tools/bench/make_baseline_scenes.py
    "$UPBGE_PATH/blender" --python tools/bench/make_baseline_scenes.py -- --only empty --only 100k

Why not ``blender -b``: on UPBGE 0.50 Linux, creating a Python Component from a
background session crashes the process (SIGSEGV). The component is therefore
created from the GUI context: the work is deferred with a timer so a real
window/viewport exists, and ``bpy.ops.logic.python_component_create`` is called
under an explicit context override. The ``bge_netlogic`` add-on is disabled for
the run because its depsgraph handler raises on a windowless context and used to
take the process down with it.

Scenes produced (deterministic, no gameplay content):

===========================  ==============================================
``empty.blend``              no renderable geometry, camera + sun only
``bench100k.blend``          224x224 quad grid -> 100,352 triangles
``bench250k_shadow.blend``   354x354 quad grid -> 250,632 triangles + a
                             shadow-casting sun
===========================  ==============================================

Triangle counts are measured after triangulation and written to
``game/bench/scenes.json`` next to the generated files.

The generated ``.blend`` files are build artefacts: they are git-ignored and
regenerated on demand (see ``.gitignore``); the generator and its manifest are
what get committed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "game" / "bench"
COMPONENT_MODULE = "rr_components.BenchRecorder"
COMPONENT_OBJECT = "BenchRoot"

#: label -> (grid segments per side, casts shadows)
SCENES = {
    "empty": (0, False),
    "100k": (224, False),
    "250k": (354, True),
}
SCENE_FILENAMES = {
    "empty": "empty.blend",
    "100k": "bench100k.blend",
    "250k": "bench250k_shadow.blend",
}


def parse_args(argv):
    """Parse the arguments that follow Blender's ``--`` separator."""
    ap = argparse.ArgumentParser(prog="make_baseline_scenes.py")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--only", action="append", choices=sorted(SCENES),
                    help="generate only this scene (repeatable)")
    ap.add_argument("--template", default=None,
                    help="open this .blend (which already carries the BenchRecorder "
                         "component) instead of building the component programmatically "
                         "and re-saving it as every scene")
    ap.add_argument("--uncapped", action="store_true",
                    help="author the scenes with vsync OFF and use_frame_rate off so the run "
                         "measures headroom instead of sitting at the panel refresh rate")
    ap.add_argument("--suffix", default=None,
                    help="file-name suffix for this scene set (default: '' or '_uncapped' "
                         "with --uncapped)")
    return ap.parse_args(argv)


# -- geometry ---------------------------------------------------------------

def grid_triangles(segments: int) -> int:
    """Exact triangle count of a ``segments x segments`` quad grid."""
    return 2 * segments * segments


def build_grid_mesh(segments: int, size: float = 40.0):
    """Create a deterministic, gently displaced triangulated grid mesh."""
    import bmesh
    import bpy

    half = size / 2.0
    step = size / segments if segments else 0.0

    bm = bmesh.new()
    verts = []
    for row in range(segments + 1):
        y = -half + row * step
        for col in range(segments + 1):
            x = -half + col * step
            # Deterministic ripple: same input, same mesh, every run.
            z = math.sin(x * 0.45) * math.cos(y * 0.35) * 0.6
            verts.append(bm.verts.new((x, y, z)))
    bm.verts.ensure_lookup_table()

    stride = segments + 1
    for row in range(segments):
        for col in range(segments):
            a = verts[row * stride + col]
            b = verts[row * stride + col + 1]
            c = verts[(row + 1) * stride + col + 1]
            d = verts[(row + 1) * stride + col]
            bm.faces.new((a, b, c, d))

    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.normal_update()

    mesh = bpy.data.meshes.new("RR_BenchGrid")
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def count_triangles(mesh) -> int:
    """Triangles of a mesh, counting n-gons after triangulation as n-2."""
    return sum(len(poly.vertices) - 2 for poly in mesh.polygons)


# -- scene assembly ---------------------------------------------------------

def reset_scene(resolution=(1280, 720), fps=60, uncapped=False):
    """Start from an empty factory scene with engine settings applied.

    The frame-rate cap is pinned explicitly (``use_frame_rate`` + ``vsync`` on) so
    every generated scene measures the same "as shipped" configuration: a number
    equal to the panel refresh rate then means "at cap", not "headroom".
    """
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    settings = scene.game_settings
    settings.resolution_x, settings.resolution_y = resolution
    settings.fps = fps
    settings.use_frame_rate = not uncapped
    # vsync is an enum ('OFF'/'ON'/'ADAPTIVE') on UPBGE 0.50, not a bool.
    settings.vsync = "OFF" if uncapped else "ON"
    return scene


def add_camera(scene, location=(0.0, -26.0, 14.0), rotation=(1.05, 0.0, 0.0)):
    import bpy

    camera = bpy.data.objects.new("BenchCamera", bpy.data.cameras.new("BenchCamera"))
    camera.location = location
    camera.rotation_euler = rotation
    scene.collection.objects.link(camera)
    scene.camera = camera
    return camera


def add_sun(scene, cast_shadows: bool):
    import bpy

    light = bpy.data.lights.new("BenchSun", type="SUN")
    light.energy = 3.0
    light.use_shadow = bool(cast_shadows)
    sun = bpy.data.objects.new("BenchSun", light)
    sun.location = (8.0, -12.0, 18.0)
    sun.rotation_euler = (0.7, 0.25, 0.6)
    scene.collection.objects.link(sun)
    return sun


def add_bench_root(scene):
    """Empty object that carries the recording component."""
    import bpy

    root = bpy.data.objects.new(COMPONENT_OBJECT, None)
    scene.collection.objects.link(root)
    return root


def attach_component(root, component_name: str = COMPONENT_MODULE) -> bool:
    """Attach a Python Component from the GUI context.

    Returns True when the object ends up with exactly that component. The
    operator needs an active object *and* a real area, so the caller must have a
    window (i.e. never run this under ``blender -b``).
    """
    import bpy

    for obj in bpy.context.scene.collection.objects:
        obj.select_set(False)
    root.select_set(True)
    bpy.context.view_layer.objects.active = root

    window = bpy.context.window_manager.windows[0]
    area = next((a for a in window.screen.areas if a.type == "VIEW_3D"),
                window.screen.areas[0])

    with bpy.context.temp_override(window=window, screen=window.screen, area=area,
                                   scene=bpy.context.scene,
                                   view_layer=bpy.context.view_layer,
                                   object=root, active_object=root):
        result = bpy.ops.logic.python_component_create(component_name=component_name)

    components = list(root.game.components)
    ok = "FINISHED" in result and any(c.name == "BenchRecorder" for c in components)
    print("[bench] component attach -> %s, %d component(s) on %s"
          % (result, len(components), root.name))
    for component in components:
        print("[bench]   %s (module %s)" % (component.name, component.module))
    return ok


def save_scene(path: Path) -> None:
    import bpy

    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


# -- generation -------------------------------------------------------------

def scene_filename(label: str, suffix: str = "") -> str:
    """Scene file name for *label*, optionally suffixed (e.g. ``_uncapped``)."""
    name = SCENE_FILENAMES[label]
    if not suffix:
        return name
    stem, dot, extension = name.rpartition(".")
    return f"{stem}{suffix}{dot}{extension}"


def generate(out_dir: Path, labels, template: Path | None,
             uncapped: bool = False, suffix: str = "") -> dict:
    """Build every requested scene and return the manifest."""
    import bpy

    manifest = {
        "generated_by": "tools/bench/make_baseline_scenes.py",
        "engine": "UPBGE " + bpy.app.version_string,
        "triangle_counting": "sum(len(polygon.vertices) - 2) after bmesh triangulation",
        "component_module": COMPONENT_MODULE,
        "frame_rate_cap": ("use_frame_rate=False, vsync=OFF (uncapped headroom set)" if uncapped
                           else "use_frame_rate=True, vsync=ON (pinned in the generator)"),
        "suffix": suffix,
        "template": str(template) if template else None,
        "scenes": [],
    }

    for label in labels:
        segments, cast_shadows = SCENES[label]
        target = out_dir / scene_filename(label, suffix)

        if template:
            bpy.ops.wm.open_mainfile(filepath=str(template))
            scene = bpy.context.scene
            if not any(obj.name == COMPONENT_OBJECT for obj in scene.collection.objects):
                root = add_bench_root(scene)
                if not attach_component(root):
                    raise RuntimeError("could not attach the component to the template scene")
        else:
            scene = reset_scene(uncapped=uncapped)
            add_camera(scene)
            add_sun(scene, cast_shadows)
            root = add_bench_root(scene)
            for obj in scene.collection.objects:
                if obj.name not in (COMPONENT_OBJECT, "BenchCamera", "BenchSun"):
                    obj.select_set(False)
            if not attach_component(root):
                raise RuntimeError(
                    "python_component_create did not attach BenchRecorder; "
                    "build game/bench/bench_template.blend by hand (see docs/16)"
                )

        triangles = 0
        if segments:
            mesh = build_grid_mesh(segments)
            grid = bpy.data.objects.new("BenchGrid", mesh)
            scene.collection.objects.link(grid)
            triangles = count_triangles(mesh)
            expected = grid_triangles(segments)
            if triangles != expected:
                raise RuntimeError(f"{label}: {triangles} triangles, expected {expected}")
            print("[bench] %s: %dx%d grid -> %d triangles" % (label, segments, segments, triangles))
        else:
            print("[bench] %s: no renderable geometry" % label)

        save_scene(target)
        print("[bench] saved %s" % target)
        manifest["scenes"].append({
            "label": label,
            "file": scene_filename(label, suffix),
            "triangles": triangles,
            "grid_segments": segments,
            "sun_casts_shadows": cast_shadows,
        })

    return manifest


def main(argv=None) -> int:
    import bpy

    if bpy.app.background:
        print("[bench] refusing to run in background mode: creating a Python Component "
              "that way segfaults on UPBGE 0.50 Linux. Run without -b/--background.",
              file=sys.stderr)
        return 2

    args_after_separator = (
        sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    )
    args = parse_args(argv if argv is not None else args_after_separator)
    out_dir = Path(args.out_dir).expanduser()

    def run():
        try:
            labels = args.only or ["empty", "100k", "250k"]
            suffix = args.suffix if args.suffix is not None else ("_uncapped" if args.uncapped else "")
            manifest = generate(
                out_dir, labels,
                Path(args.template).expanduser() if args.template else None,
                uncapped=args.uncapped, suffix=suffix,
            )
            manifest_path = out_dir / ("scenes.json" if not suffix else f"scenes{suffix}.json")
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            print("[bench] manifest -> %s" % manifest_path)
            print("[bench] DONE %s" % json.dumps([s["label"] for s in manifest["scenes"]]))
        except Exception as exc:  # noqa: BLE001 - report and exit non-zero
            print("[bench] FAILED: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
        finally:
            bpy.ops.wm.quit_blender()
        return None

    # Defer until a window and a 3D viewport exist.
    bpy.app.timers.register(run, first_interval=1.0)
    return 0


def _disable_netlogic() -> None:
    """Disable the BGE netlogic add-on before anything else touches the scene."""
    import addon_utils

    try:
        addon_utils.disable("bge_netlogic", default_set=False)
        print("[bench] bge_netlogic disabled for this run")
    except Exception as exc:  # noqa: BLE001 - best effort
        print("[bench] could not disable bge_netlogic: %s" % exc)


if __name__ == "__main__":
    _disable_netlogic()
    # NB: never raise SystemExit from a `--python` script — Blender treats it as
    # "quit now" and the deferred timer never runs. Only the background guard,
    # which has nothing to defer, exits directly.
    _RC = main()
    if _RC:
        sys.exit(_RC)
