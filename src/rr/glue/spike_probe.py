"""S-01 engine probe component (spike artefact, not shipping gameplay).

Runs one status check per engine feature the UPBGE pin decision needs, writes
`spike_result.json` and prints a markdown row for
`docs/reports/S-01_engine_decision.md`.

Scene contract (built by tools/blender/gen_spike_engine.py):
  * SpikeBox       dynamic box above SpikeGround (gravity + collision check)
  * SpikeAnim      non-physics cube with action "SpikeBounce" (playAction check)
  * SpikeHudCam    camera + collection "SpikeHud" (overlay check)
  * SpikeProbeRoot this component
Env: RR_SPIKE_MACHINE=P1|P2|P3, RR_SPIKE_SECONDS, RR_SPIKE_OUT, RR_SPIKE_HOLD=1,
     RR_SPIKE_OGG (override test tone path).

API facts used here are from the UPBGE Python API docs (bge.logic tic rates,
KX_Scene.addOverlayCollection(kxCamera, collection), KX_2DFilterManager.addFilter,
playAction keyword names, aud.Device/Sound/Handle). Every call below is still
VERIFY: no agent has run it inside UPBGE yet; humans record the outcome in the
S-01 matrix.
"""
import json
import os
import sys
import time
import traceback
from collections import OrderedDict

import bge

from rr.core.spike import (
    FAIL,
    PASS,
    SKIP,
    compute_fps_stats,
    matrix_header,
    matrix_row,
    summarize,
    vector_magnitude,
)

DEFAULT_SOUND = "//../assets/audio/sfx/SFX_ToneTest_01.ogg"


class SpikeProbe(bge.types.KX_PythonComponent):
    args = OrderedDict([
        ("Machine", ""),              # P1 | P2 | P3; else RR_SPIKE_MACHINE
        ("Seconds", 12.0),
        ("Logic Tic Rate", 60.0),
        ("Physics Tic Rate", 60.0),
        ("Test Sound", ""),           # empty -> assets/audio/sfx test tone
        ("Hold Open", False),         # keep the window open for manual poking
    ])

    # -- lifecycle ---------------------------------------------------------
    def start(self, args):
        self.checks = {}
        self.notes = []
        self.samples = []
        self.physics_diagnostics = []
        self.update_count = 0
        self.next_physics_after_check = False
        self.measured_logic = None
        self.measured_physics = None
        self.done = False
        self.t0 = time.time()
        self.next_sample = 0.5
        self.duration = float(os.environ.get("RR_SPIKE_SECONDS", args["Seconds"]))
        self.machine = os.environ.get("RR_SPIKE_MACHINE", args["Machine"]) or "?"
        self.hold = os.environ.get("RR_SPIKE_HOLD", "1" if args["Hold Open"] else "0") == "1"
        self.want_logic = float(args["Logic Tic Rate"])
        self.want_physics = float(args["Physics Tic Rate"])
        self.scene = bge.logic.getCurrentScene()
        self.box = self._object("SpikeBox")
        self.start_z = (
            getattr(self.box.worldPosition, "z", self.box.worldPosition[2])
            if self.box is not None and hasattr(self.box, "worldPosition")
            else 0.0
        )
        self.aud_handle = None

        try:
            bge.logic.setLogicTicRate(self.want_logic)
            bge.logic.setPhysicsTicRate(self.want_physics)
        except Exception as exc:  # noqa: BLE001 - record, never abort the probe
            self._note("set_tics", "%s: %s" % (type(exc).__name__, exc))

        self._record_physics_diag("start")

        self._check("component", self._probe_component)
        self._check("play_action", self._probe_play_action)
        self._check("filter2d", self._probe_filter2d)
        self._check("overlay", self._probe_overlay)
        self._check("aud_play", self._probe_aud_play)
        self._check("aud_volume", self._probe_aud_volume)
        self._check("aud_3d", self._probe_aud_3d)
        self._sample_fps()
        print("[spike] engine %s on %s, %d checks recorded"
              % (self._version(), self.machine, len(self.checks)))
        self._write_json(status="partial")

    def update(self):
        if self.done:
            return
        self.update_count += 1
        elapsed = time.time() - self.t0

        if self.update_count == 1:
            print("[spike] update #1 started at t=%.3fs" % elapsed)
            self._write_json(status="partial", log=True)

        if self.next_physics_after_check:
            self._record_physics_diag("post_check_update")
            self.next_physics_after_check = False
            self._write_json(status="partial", log=True)

        if elapsed >= self.next_sample:
            self._sample_fps()
            if "physics" in self.checks:
                self._record_physics_diag("post_check_sample")
            self.next_sample += 0.5
            self._write_json(status="partial", log=False)

        if "tic_rates" not in self.checks and elapsed >= 0.5:
            self._check("tic_rates", self._probe_tic_rates)
            self._write_json(status="partial", log=True)

        if "physics" not in self.checks and elapsed >= 3.0:
            self._check("physics", self._probe_physics)
            self.next_physics_after_check = True
            self._write_json(status="partial", log=True)

        if elapsed >= self.duration:
            self._check("fps", self._probe_fps)
            self._finish()

    # -- checks ------------------------------------------------------------
    def _probe_component(self):
        if not hasattr(bge.types, "KX_PythonComponent"):
            return FAIL, "bge.types.KX_PythonComponent missing"
        return PASS, "class loaded via rr_components.SpikeProbe, args=%d" % len(self.args)

    def _probe_tic_rates(self):
        logic = bge.logic.getLogicTicRate()
        physics = bge.logic.getPhysicsTicRate()
        self.measured_logic = float(logic) if logic is not None else None
        self.measured_physics = float(physics) if physics is not None else None
        ok = (
            self.measured_logic is not None
            and self.measured_physics is not None
            and abs(self.measured_logic - self.want_logic) < 0.6
            and abs(self.measured_physics - self.want_physics) < 0.6
        )
        # VERIFY: on UPBGE 0.50 Windows P2 run, getPhysicsTicRate() returned 0.0 even
        # though setPhysicsTicRate(60) was called in start().  Three hypotheses:
        # (a) getter returns 0 before first Bullet step (probe fires at t≥0.5 s, but
        #     Bullet may initialise later); (b) the getter API changed or was removed;
        # (c) Bullet disabled (would also explain physics FAIL below).
        # Record the raw value so the next run can distinguish them.
        physics_zero_note = ""
        if self.measured_physics == 0.0:
            physics_zero_note = (
                "; physics=0.0 — possible causes: getter uninitialized before first "
                "physics step, API change, or Bullet disabled; see §6.8"
            )
        note = "measured: logic=%.1f physics=%.1f (setpoint: logic=%.0f physics=%.0f)%s" % (
            self.measured_logic if self.measured_logic is not None else -1.0,
            self.measured_physics if self.measured_physics is not None else -1.0,
            self.want_logic,
            self.want_physics,
            physics_zero_note,
        )
        return (PASS if ok else FAIL), note

    def _record_physics_diag(self, tag: str = ""):
        elapsed = time.time() - self.t0
        fresh_box = self._object("SpikeBox")
        cached_box = self.box
        box_match = (
            (cached_box is fresh_box)
            if (cached_box is not None and fresh_box is not None)
            else False
        )
        target = fresh_box or cached_box

        owner_obj = getattr(self, "object", None)
        owner_name = (
            getattr(owner_obj, "name", "unknown")
            if owner_obj is not None
            else "none"
        )

        pos = (
            [round(float(v), 4) for v in target.worldPosition]
            if target is not None and hasattr(target, "worldPosition")
            else None
        )
        vel = (
            [round(float(v), 4) for v in target.worldLinearVelocity]
            if target is not None and hasattr(target, "worldLinearVelocity")
            else None
        )
        speed = (
            round(vector_magnitude(target.worldLinearVelocity), 4)
            if target is not None and hasattr(target, "worldLinearVelocity")
            else None
        )

        phys_tic = None
        if hasattr(bge.logic, "getPhysicsTicRate"):
            try:
                phys_tic = float(bge.logic.getPhysicsTicRate())
            except Exception:  # noqa: BLE001
                phys_tic = None

        entry = {
            "tag": tag,
            "elapsed": round(elapsed, 4),
            "update_count": self.update_count,
            "owner": owner_name,
            "physics_tic_rate": phys_tic,
            "box_cached_id": id(cached_box) if cached_box is not None else None,
            "box_fresh_id": id(fresh_box) if fresh_box is not None else None,
            "box_match": box_match,
            "position": pos,
            "velocity": vel,
            "speed": speed,
        }
        self.physics_diagnostics.append(entry)
        print(
            "[spike] diag [%s] t=%.3fs update=%d owner=%s match=%s pos=%s vel=%s tic=%s"
            % (tag, entry["elapsed"], entry["update_count"], owner_name, box_match, pos, vel, phys_tic)
        )
        return entry

    def _probe_physics(self):
        diag = self._record_physics_diag("check")
        if not self.box:
            return FAIL, "no SpikeBox in scene"
        z = getattr(self.box.worldPosition, "z", self.box.worldPosition[2])
        vel = self.box.worldLinearVelocity
        speed = vector_magnitude(vel)
        fell = self.start_z - z
        ok = fell > 1.5 and z < 1.0 and speed < 0.5
        # VERIFY: on UPBGE 0.50 Windows P2 run, box stayed at z=3.00 (fell=0.00).
        # Record vx/vy/vz and diagnostics to disambiguate on the next run:
        #   vz<0 and vx,vy≈0 → gravity correct axis, timing; check fell at later t.
        #   vy≠0 and vz≈0 → gravity on +Y (forward) not -Z (up); generator needs
        #     scene.game_settings.physics_gravity direction check.
        #   all v≈0 → Bullet not running; root cause shared with tic_rates FAIL.
        note = (
            "z=%.2f start_z=%.2f fell=%.2f |v|=%.2f "
            "vx=%.2f vy=%.2f vz=%.2f (updates=%d elapsed=%.2fs owner=%s match=%s phys_tic=%s)"
        ) % (
            z,
            self.start_z,
            fell,
            speed,
            vel[0],
            vel[1],
            vel[2],
            diag["update_count"],
            diag["elapsed"],
            diag["owner"],
            diag["box_match"],
            diag["physics_tic_rate"],
        )
        return (PASS if ok else FAIL), note

    def _probe_play_action(self):
        obj = self._object("SpikeAnim")
        if not obj:
            return FAIL, "no SpikeAnim in scene (setup gap, not an engine feature)"
        # The positional form is the API contract; keyword support is recorded but
        # must not decide the feature (bge methods need not accept keywords).
        obj.playAction("SpikeBounce", 1, 20, 0, 0, 0,
                       bge.logic.KX_ACTION_MODE_LOOP, 0.0, 0, 1.0,
                       bge.logic.KX_ACTION_BLEND_BLEND)
        name = obj.getActionName(0)
        playing = obj.isPlayingAction(0)
        obj.stopAction(0)
        positional_ok = name == "SpikeBounce" and bool(playing)
        # Keyword support is informational only: any exception here (not just
        # TypeError) must not decide the feature.
        keyword = "no"
        try:
            obj.playAction(name="SpikeBounce", start_frame=1, end_frame=20,
                           play_mode=bge.logic.KX_ACTION_MODE_PLAY,
                           blend_mode=bge.logic.KX_ACTION_BLEND_BLEND, speed=1.0)
            keyword = "yes"
            obj.stopAction(0)
        except Exception as exc:  # noqa: BLE001 - reported, never gating
            keyword = "rejected (%s: %s)" % (type(exc).__name__, exc)
        note = "positional name=%r playing=%s -> %s; keywords=%s" % (
            name, playing, "PASS" if positional_ok else "FAIL", keyword)
        return (PASS if positional_ok else FAIL), note

    def _probe_filter2d(self):
        manager = self.scene.filterManager
        manager.addFilter(0, bge.logic.RAS_2DFILTER_GRAYSCALE)
        added = manager.getFilter(0) is not None
        manager.removeFilter(0)
        removed = manager.getFilter(0) is None
        note = "gray=1.0; add=%s remove=%s (viewport-render mode disables 2D filters)" % (
            added, removed)
        return (PASS if added and removed else FAIL), note

    def _probe_overlay(self):
        try:
            import bpy  # noqa: PLC0415 - runtime only; module import must stay light
        except ImportError as exc:
            return SKIP, "bpy unavailable in this launcher (%s)" % exc

        collection = bpy.data.collections.get("SpikeHud")
        camera = self._object("SpikeHudCam")
        if collection is None or camera is None:
            return SKIP, "scene has no SpikeHud collection / SpikeHudCam"
        self.scene.addOverlayCollection(camera, collection)
        self.scene.removeOverlayCollection(collection)
        return PASS, "addOverlayCollection/removeOverlayCollection(kxCamera, collection)"

    def _probe_aud_play(self):
        import aud  # noqa: PLC0415 - must not be imported while the UI loads the class

        self.aud_device = aud.Device()
        path = os.environ.get("RR_SPIKE_OGG") or bge.logic.expandPath(DEFAULT_SOUND)
        try:
            sound = aud.Sound.file(path)
        except AttributeError:
            sound = aud.Sound(path)
        self.aud_handle = self.aud_device.play(sound)
        return PASS, "device=%s rate=%s path=%s" % (
            type(self.aud_device).__name__, self.aud_device.rate, path)

    def _probe_aud_volume(self):
        if self.aud_handle is None:
            return FAIL, "no handle (aud_play failed)"
        self.aud_handle.volume = 0.3
        readback = float(self.aud_handle.volume)
        self.aud_handle.volume = 1.0
        ok = abs(readback - 0.3) < 1e-3
        return (PASS if ok else FAIL), "set 0.3 read %.3f" % readback

    def _probe_aud_3d(self):
        if self.aud_handle is None:
            return FAIL, "no handle (aud_play failed)"
        camera = self.scene.active_camera
        if camera is not None:
            self.aud_device.listener_location = tuple(camera.worldPosition)
        self.aud_handle.relative = False
        self.aud_handle.location = (3.0, 0.0, 1.0)
        self.aud_handle.distance_reference = 5.0
        self.aud_handle.distance_maximum = 60.0
        pos = tuple(self.aud_handle.location)
        ok = abs(pos[0] - 3.0) < 1e-3 and self.aud_handle.relative is False
        return (PASS if ok else FAIL), "location read %s relative=%s" % (
            tuple(round(v, 2) for v in pos), self.aud_handle.relative)

    def _probe_fps(self):
        stats = compute_fps_stats(self.samples)
        return stats["status"], str(stats["note"])

    # -- reporting ---------------------------------------------------------
    def _sample_fps(self):
        try:
            elapsed = time.time() - self.t0
            self.samples.append((elapsed, float(bge.logic.getAverageFrameRate())))
        except Exception as exc:  # noqa: BLE001
            self._note("fps", "%s: %s" % (type(exc).__name__, exc))

    def _write_json(self, status: str, log: bool = True):
        fps_stats = compute_fps_stats(self.samples)
        summary = summarize(self.checks)
        payload = {
            "status": status,
            "machine": self.machine,
            "engine": {
                "version": self._version(),
                "platform": sys.platform,
                "python": sys.version.split()[0],
            },
            "window": self._window(),
            "tic": {
                "setpoint": {"logic": self.want_logic, "physics": self.want_physics},
                "measured": {
                    "logic": self.measured_logic,
                    "physics": self.measured_physics,
                },
            },
            "checks": self.checks,
            "summary": summary,
            "fps": {
                "avg": fps_stats["avg"],
                "min": fps_stats["min"],
                "median": fps_stats["median"],
                "n": fps_stats["n"],
                "raw_n": fps_stats["raw_n"],
                "dropped_n": fps_stats["dropped_n"],
                "raw_max": fps_stats["raw_max"],
                "status": fps_stats["status"],
            },
            "notes": list(self.notes),
            "physics_diagnostics": list(self.physics_diagnostics),
        }
        out = os.environ.get("RR_SPIKE_OUT", "spike_result.json")
        try:
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            if log:
                print("[spike] wrote %s (status: %s)" % (os.path.abspath(out), status))
        except OSError as exc:
            print("[spike] could not write %s: %s" % (out, exc))

    def _finish(self):
        self.done = True
        self._record_physics_diag("finish")
        self._write_json(status="complete", log=True)
        fps_stats = compute_fps_stats(self.samples)
        summary = summarize(self.checks)
        for line in ("", matrix_header(), matrix_row(
                self._version(), self.machine, self.checks, float(fps_stats["avg"])), ""):
            print("[spike] " + line)
        print("[spike] summary %s" % json.dumps(summary, sort_keys=True))
        if not self.hold:
            bge.logic.endGame()

    def _version(self):
        app = getattr(bge, "app", None)

        def first(*names):
            for name in names:
                value = getattr(app, name, None) if app else None
                if isinstance(value, str):
                    return value
                if isinstance(value, (tuple, list)) and value:
                    return ".".join(str(part) for part in value)
            return None

        upbge = first("upbge_version_string", "upbge_version")
        blender = first("version_string", "version")
        if upbge and blender:
            return "%s (Blender %s)" % (upbge, blender)
        return upbge or blender or "?"

    def _window(self):
        try:
            return [bge.render.getWindowWidth(), bge.render.getWindowHeight()]
        except Exception:  # noqa: BLE001
            return None

    # -- helpers -----------------------------------------------------------
    def _object(self, name):
        try:
            return self.scene.objects[name]
        except KeyError:
            return None

    def _note(self, check, text):
        self.notes.append("%s: %s" % (check, text))
        print("[spike] note %s: %s" % (check, text))

    def _check(self, name, fn):
        try:
            status, note = fn()
        except Exception as exc:  # noqa: BLE001 - a spike records, it does not crash
            status, note = FAIL, "%s: %s" % (type(exc).__name__, exc)
            self.notes.append("%s: %s" % (name, traceback.format_exc(limit=2)))
        self.checks[name] = status
        if note:
            self.notes.append("%s: %s" % (name, note))
        print("[spike] %-11s %-4s %s" % (name, status, note or ""))
