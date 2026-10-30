#!/usr/bin/env python3
"""Run the F-05 baseline scenes through ``blenderplayer`` and keep the results.

Examples::

    # Tier C baseline, both target resolutions, 60 s per scene
    python tools/bench/run_baseline.py --res 1280x720 --res 1366x768 --preset low

    # one scene, background soak on the heaviest scene (5 minutes)
    python tools/bench/run_baseline.py --res 1366x768 --scenes 250k --soak 300

    # try the discrete GPU (DRI_PRIME=1); the actual renderer is still read
    # from the player's own GL_RENDERER line
    python tools/bench/run_baseline.py --res 1280x720 --dgpu

Launch flags (all **before** the ``.blend`` path — ``blenderplayer`` treats any
trailing option as a file name):

* windowed   ``blenderplayer -w <w> <h> <scene>.blend``
* fullscreen ``blenderplayer -f <w> <h> 32 60 <scene>.blend``

``blenderplayer`` has no duration flag; the recording window comes from the
environment (``RR_BENCH_SECONDS`` / ``RR_BENCH_WARMUP``) which the
``BenchRecorder`` component reads.

A scene only counts as measured when the component actually wrote a result file
whose ``ok`` is true. Missing or unreadable results are reported as failures and
make the process exit non-zero — this runner never synthesises numbers.

Results land in ``docs/reports/bench/<machine>_<scene>_<res>.json`` next to a
``logs/`` directory holding the captured player output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENES = {
    # label -> (blend file, is the shadow-casting heavy scene)
    "empty": ("empty.blend", False),
    "100k": ("bench100k.blend", False),
    "250k": ("bench250k_shadow.blend", True),
}
DEFAULT_SCENE_DIR = REPO_ROOT / "game" / "bench"
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "reports" / "bench"

DEFAULT_SECONDS = 60.0
DEFAULT_WARMUP = 3.0
SOAK_SECONDS = 300.0
DEFAULT_RESOLUTIONS = ("1280x720", "1366x768")

GL_PATTERNS = {
    "gl_vendor": re.compile(r"^GL_VENDOR:\s*(.+?)\s*$", re.MULTILINE),
    "gl_renderer": re.compile(r"^GL_RENDERER:\s*(.+?)\s*$", re.MULTILINE),
    "gl_version": re.compile(r"^GL_VERSION:\s*(.+?)\s*$", re.MULTILINE),
}


def default_machine_label() -> str:
    """Stable machine label: hostname, qualified with the DMI product name when the
    hostname is a generic default (``localhost``/``localhost.localdomain``)."""
    host = slugify(socket.gethostname())
    if not host.startswith("localhost"):
        return host
    try:
        product = Path("/sys/devices/virtual/dmi/id/product_name").read_text(
            encoding="utf-8", errors="replace").strip()
    except OSError:
        return host
    return f"{host}_{slugify(product)}" if product else host


def slugify(value: str) -> str:
    """Filesystem-safe, stable label."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").lower()
    return cleaned or "unknown"


def parse_resolution(text: str) -> tuple[int, int]:
    """Parse ``1280x720`` into ints, raising ``ValueError`` when malformed."""
    match = re.fullmatch(r"\s*(\d+)\s*[xX*]\s*(\d+)\s*", str(text))
    if not match:
        raise ValueError(f"bad resolution {text!r}; expected e.g. 1280x720")
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        raise ValueError(f"bad resolution {text!r}; dimensions must be positive")
    return width, height


def find_player() -> str:
    """Locate ``blenderplayer`` from ``UPBGE_PATH`` (never a bare PATH guess first)."""
    base = os.environ.get("UPBGE_PATH")
    if base:
        for name in ("blenderplayer", "blenderplayer.exe"):
            candidate = Path(base) / name
            if candidate.exists():
                return str(candidate)
    found = shutil.which("blenderplayer")
    if found:
        return found
    raise SystemExit("Cannot find 'blenderplayer'. Set UPBGE_PATH to the UPBGE folder.")


def launch_flags(mode: str, width: int, height: int, all_frames: bool = False) -> list[str]:
    """Player flags for one run (must precede the .blend path).

    ``-g fixedtime`` is the player's documented "Enable all frames" switch: it
    lifts the vsync/frame-rate cap at runtime, which is how headroom (rather than
    "sitting at the panel refresh rate") is measured without editing the scenes.
    """
    flags: list[str] = []
    if all_frames:
        flags += ["-g", "fixedtime"]
    if mode == "fullscreen":
        flags += ["-f", str(width), str(height), "32", "60"]
    else:
        flags += ["-w", str(width), str(height)]
    return flags


def load_scene_manifest(scene_dir: Path, suffix: str) -> dict:
    """Read the generator's manifest so the authored frame-rate cap is recorded
    from the scenes themselves rather than assumed from the runner flags."""
    name = "scenes.json" if not suffix else f"scenes{suffix}.json"
    path = Path(scene_dir) / name
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_gl_block(text: str) -> dict[str, str | None]:
    """Pull the player's GL identity out of its stdout."""
    parsed = {}
    for key, pattern in GL_PATTERNS.items():
        match = pattern.search(text or "")
        parsed[key] = match.group(1) if match else None
    return parsed


def build_env(base_env, *, seconds, warmup, out_path, scene_label, preset, resolution, dgpu):
    env = dict(base_env)
    env.update({
        "RR_BENCH": "1",
        "RR_BENCH_SECONDS": str(seconds),
        "RR_BENCH_WARMUP": str(warmup),
        "RR_BENCH_OUT": str(out_path),
        "RR_BENCH_SCENE": scene_label,
        "RR_BENCH_RES": resolution,
    })
    if preset:
        env["RR_BENCH_PRESET"] = preset
    else:
        env.pop("RR_BENCH_PRESET", None)
    if dgpu:
        env["DRI_PRIME"] = "1"
    else:
        env.pop("DRI_PRIME", None)
    return env


def run_one(*, player, scene_path, resolution, mode, seconds, warmup, preset,
            out_dir, machine, scene_label, dgpu, timeout_extra, log_dir,
            all_frames=False, scene_cap=None, scene_suffix="") -> dict:
    """Run a single scene/resolution pair. Returns a status record."""
    width, height = parse_resolution(resolution)
    res_label = f"{width}x{height}"
    stem = f"{machine}_{scene_label}_{res_label}"

    raw_path = out_dir / f".{stem}.raw.json"
    result_path = out_dir / f"{stem}.json"
    log_path = log_dir / f"{stem}.log"

    for stale in (raw_path, result_path):
        stale.unlink(missing_ok=True)

    flags = launch_flags(mode, width, height, all_frames=all_frames)
    command = [player, *flags, str(scene_path)]
    env = build_env(os.environ, seconds=seconds, warmup=warmup, out_path=raw_path,
                    scene_label=scene_label, preset=preset, resolution=res_label, dgpu=dgpu)
    timeout = warmup + seconds + timeout_extra

    record = {
        "scene": scene_label,
        "resolution": res_label,
        "mode": mode,
        "command": command,
        "flags": " ".join(flags),
        "duration_s": seconds,
        "warmup_s": warmup,
        "timeout_s": timeout,
        "dgpu_requested": bool(dgpu),
        "fixedtime_flag_passed": bool(all_frames),
        "scene_suffix": scene_suffix,
        "scene_frame_rate_cap": scene_cap,
        "result_path": str(result_path),
        "log_path": str(log_path),
        "ok": False,
        "failure": None,
    }

    print(f"[bench] {stem}: {' '.join(command)}", flush=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(command, env=env, capture_output=True, text=True,
                                   timeout=timeout, check=False)
        stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        exit_code = None
        timed_out = True
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", "replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")

    log_path.write_text(
        " ".join(command) + "\n"
        + f"exit_code={exit_code} timed_out={timed_out}\n"
        + "----- stdout -----\n" + stdout
        + "\n----- stderr -----\n" + stderr,
        encoding="utf-8",
    )

    gl = parse_gl_block(stdout)
    record.update(gl)
    record["exit_code"] = exit_code
    record["timed_out"] = timed_out

    if timed_out:
        record["failure"] = f"player did not exit within {timeout:.0f}s"
        return record
    if not raw_path.exists():
        record["failure"] = ("no result file was written; the component did not run "
                             "(see the log for import or scene errors)")
        return record

    try:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        record["failure"] = f"result file is unreadable: {exc}"
        return record

    if not payload.get("ok"):
        record["failure"] = "component reported ok=false (no frames measured)"
        return record

    payload["gpu_renderer"] = gl.get("gl_renderer")
    payload["gl_vendor"] = gl.get("gl_vendor")
    payload["gl_version"] = gl.get("gl_version")
    payload["runner"] = {
        "command": command,
        "flags": " ".join(flags),
        "mode": mode,
        "exit_code": exit_code,
        "log": str(log_path.relative_to(REPO_ROOT)) if log_path.is_relative_to(REPO_ROOT) else str(log_path),
        "duration_s": seconds,
        "warmup_s": warmup,
        "gpu_selection_requested": "DRI_PRIME=1" if dgpu else "default (no DRI_PRIME)",
        "scene_frame_rate_cap": scene_cap
        if scene_cap else "unknown (no scene manifest found)",
        "fixedtime_flag_passed": bool(all_frames),
        "scene_suffix": scene_suffix,
        "gpu_selection_verified": None,
        "renderer_source": "blenderplayer stdout GL_RENDERER",
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    notes = list(payload.get("notes") or [])
    if dgpu:
        notes.append(
            "DRI_PRIME=1 was requested for this run; whether that selected the discrete GPU "
            "is NOT verified — compare gpu_renderer against a no-flag run"
        )
    else:
        notes.append("no GPU-selection environment was set (DRI_PRIME unset)")
    uncapped_scenes = bool(scene_cap and "vsync=OFF" in scene_cap)
    if uncapped_scenes:
        notes.append(
            "scenes authored uncapped (use_frame_rate off, vsync=OFF): these are headroom numbers, "
            "not the as-shipped capped frame rate"
        )
    else:
        notes.append(
            "scenes authored with vsync + use_frame_rate on: a result equal to the panel refresh rate "
            "means 'at cap', not 'headroom' (see the *uncapped* scene set for headroom)"
        )
    if all_frames:
        notes.append(
            "'-g fixedtime' was passed to the player; VERIFIED it does not lift the vsync cap on "
            "UPBGE 0.50 Linux, so the numbers below still reflect the scene's own cap setting"
        )
    payload["notes"] = notes

    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    raw_path.unlink(missing_ok=True)

    record["ok"] = True
    record["payload"] = payload
    return record


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--res", action="append", dest="resolutions",
                    help=f"resolution WxH (repeatable; default {', '.join(DEFAULT_RESOLUTIONS)})")
    ap.add_argument("--preset", default=None, help="quality preset label recorded in the result")
    ap.add_argument("--seconds", type=float, default=DEFAULT_SECONDS,
                    help=f"measured seconds per scene (default {DEFAULT_SECONDS:.0f})")
    ap.add_argument("--warmup", type=float, default=DEFAULT_WARMUP,
                    help=f"warmup seconds discarded per scene (default {DEFAULT_WARMUP:.0f})")
    ap.add_argument("--soak", type=float, default=None,
                    help=f"additional {SOAK_SECONDS:.0f}s run of the 250k scene only")
    ap.add_argument("--scenes", default="empty,100k,250k",
                    help="comma-separated subset of empty,100k,250k (order is always the baseline order)")
    ap.add_argument("--machine", default=None,
                    help="machine label for file names (default: sanitized hostname)")
    ap.add_argument("--scene-dir", default=str(DEFAULT_SCENE_DIR))
    ap.add_argument("--scene-suffix", default="",
                    help="suffix of the scene files to run, e.g. '_uncapped' "
                         "(see make_baseline_scenes.py --uncapped)")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--mode", choices=("windowed", "fullscreen"), default="fullscreen",
                    help="player presentation mode (default fullscreen: on a 1366x768 Wayland "
                         "compositor a windowed request is clamped, e.g. 1366x768 -> 1299x699, "
                         "while fullscreen measured the exact requested surface)")
    ap.add_argument("--dgpu", action="store_true", help="run with DRI_PRIME=1")
    ap.add_argument("--all-frames", action="store_true",
                    help="pass the player's '-g fixedtime' ('Enable all frames'). VERIFIED on UPBGE "
                         "0.50 Linux this does NOT lift the vsync cap; measure headroom with the "
                         "generator's --uncapped scenes instead")
    ap.add_argument("--timeout-extra", type=float, default=120.0,
                    help="seconds added to warmup+duration before the player is killed")
    args = ap.parse_args(argv)

    resolutions = args.resolutions or list(DEFAULT_RESOLUTIONS)
    for res in resolutions:
        parse_resolution(res)  # fail fast on typos

    requested = [s.strip() for s in args.scenes.split(",") if s.strip()]
    unknown = [s for s in requested if s not in SCENES]
    if unknown:
        raise SystemExit(f"unknown scene(s): {', '.join(unknown)} (choose from {', '.join(SCENES)})")
    ordered = [s for s in SCENES if s in requested]

    player = find_player()
    machine = slugify(args.machine) if args.machine else default_machine_label()
    scene_dir = Path(args.scene_dir)
    manifest = load_scene_manifest(scene_dir, args.scene_suffix)
    scene_cap = manifest.get("frame_rate_cap")
    if manifest:
        print(f"[bench] scene manifest: {len(manifest.get('scenes') or [])} scene(s), "
              f"cap={scene_cap}")
    else:
        print("[bench] warning: no scene manifest found; the authored frame-rate cap is unknown")
    out_dir = Path(args.out_dir)
    log_dir = out_dir / "logs"
    # A killed run can leave a half-written ".raw.json" behind; those are never
    # results, so clear them before planning a new set.
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob(".*.raw.json"):
        stale.unlink(missing_ok=True)

    print(f"[bench] machine={machine} player={player} mode={args.mode} "
          f"scene_suffix={args.scene_suffix or '(none)'} "
          f"dgpu={'yes' if args.dgpu else 'no'} seconds={args.seconds:g} warmup={args.warmup:g} "
          f"cap={'lifted (-g fixedtime)' if args.all_frames else 'as authored'}")

    plan = []
    for scene in ordered:
        blend, _heavy = SCENES[scene]
        for res in resolutions:
            plan.append((scene, res, args.seconds))
    if args.soak:
        heavy = [s for s in ordered if SCENES[s][1]]
        if heavy:
            for res in resolutions:
                plan.append((heavy[0], res, args.soak))
        else:
            print("[bench] --soak ignored: the 250k scene is not in this run")

    failures = []
    for scene, res, seconds in plan:
        blend_name = SCENES[scene][0]
        if args.scene_suffix:
            stem, dot, extension = blend_name.rpartition(".")
            blend_name = f"{stem}{args.scene_suffix}{dot}{extension}"
        blend = scene_dir / blend_name
        if not blend.exists():
            print(f"[bench] FAIL {scene}: missing scene {blend} "
                  f"(run tools/bench/make_baseline_scenes.py)", flush=True)
            failures.append(f"{scene}@{res}: missing scene file")
            continue
        record = run_one(
            player=player, scene_path=blend, resolution=res, mode=args.mode,
            seconds=seconds, warmup=args.warmup, preset=args.preset,
            out_dir=out_dir, machine=machine, scene_label=scene, dgpu=args.dgpu,
            timeout_extra=args.timeout_extra, log_dir=log_dir, all_frames=args.all_frames,
            scene_cap=scene_cap, scene_suffix=args.scene_suffix,
        )
        if record["ok"]:
            payload = record["payload"]
            stats = payload["stats"]
            print("[bench] OK   %-5s %-9s avg=%.1f 1%%low=%.1f min=%.1f -> %s (actual %s, %s)"
                  % (scene, res, stats["fps_avg"] or 0.0, stats["p1_low_fps"] or 0.0,
                     stats["fps_min"] or 0.0, record["result_path"],
                     payload.get("actual_resolution"), payload.get("gpu_renderer")), flush=True)
        else:
            print(f"[bench] FAIL {scene}@{res}: {record['failure']}", flush=True)
            failures.append(f"{scene}@{res}: {record['failure']}")

    total = len(plan)
    print(f"[bench] {total - len(failures)}/{total} runs produced results")
    if failures:
        print("[bench] failures:")
        for item in failures:
            print(f"[bench]   - {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
