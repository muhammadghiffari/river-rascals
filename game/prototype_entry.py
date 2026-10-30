"""Engine-facing gameplay loop for the Catalna playable slice.

`tools/blender/build_prototype.py` wires an Always sensor on `PrototypeRoot` to
`prototype_entry.tick`, so UPBGE calls `tick` once per logic frame (60 Hz). This
module is the only place that touches `bge`: it reads input, asks
`rr.core.prototype` for forces and lifecycle decisions, applies them to the
Bullet body, drives the follow camera and HUD text, and fires audio cues from
real gameplay events. Rules stay in `rr.core` so they remain unit-testable.

This file lives next to the .blend so UPBGE can import it; it adds ../src to
sys.path the same way `rr_components.py` does.

VERIFY: every `bge` interaction here until exercised in the pinned UPBGE build.
"""
import json
import math
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, os.pardir, "src"))
for _path in (_HERE, _SRC):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bge

from rr.core.oar import Oar, OarConfig, OarPhase
from rr.core.prototype import (
    Prototype,
    PrototypeConfig,
    TeleportGuard,
    controls,
    frame_forces,
    hud_text,
    prompt_text,
)
from rr.core.prototype_audio import EVENTS, MODE_LOOPS
from rr.glue.prototype_audio import PrototypeAudio

ROOT = os.path.abspath(os.path.join(_HERE, os.pardir))
SETTINGS = os.path.join(ROOT, "game", "settings", "prototype.json")

BODY_NAME = "RF_RaftT1"
CAMERA_NAME = "Cam_Main"
HUD_NAME = "UI_HudText"
PROMPT_NAME = "UI_PromptText"

# Logical action -> bge.events attribute. Resolved by name so a renamed or
# missing key constant degrades into "that action is unavailable", not a crash.
KEY_EVENTS = {
    "A": "AKEY", "D": "DKEY", "S": "SKEY",
    "LEFT": "LEFTARROWKEY", "RIGHT": "RIGHTARROWKEY", "DOWN": "DOWNARROWKEY",
    "START": "ENTERKEY", "PAUSE": "PKEY", "MENU": "ESCKEY", "QUIT": "QKEY",
}
PADDLE_KEYS = frozenset({"A", "D", "S", "LEFT", "RIGHT", "DOWN"})

CAMERA_OFFSET = (0.0, -10.5, 6.5)   # metres behind/above the raft, matches the builder's aim
CAMERA_LAG = 0.18                   # seconds to close most of the gap to the ideal position
CAMERA_SWAY = 0.45                  # how much of the raft's lateral offset the camera follows
SPLASH_SPEED = 2.6                  # m/s relative to the current before spray is audible
BANK_SPRING = 4000.0                # N/m pushing the raft off the bank
BANK_DAMPING = 600.0                # N*s/m opposing outward motion at the bank
# Normalised screen rectangle (x0, y0, x1, y1) covering the centred prompt text.
PROMPT_RECT = (0.28, 0.58, 0.72, 0.82)

# Smoke mode mirrors tools/run_game.py --smoke: autopaddle for a fixed time, write
# measurements, quit. It is the only way to get runtime evidence without a human
# at the keyboard, so it stays in the shipping module but is inert unless asked for.
SMOKE = os.environ.get("RR_SMOKE") == "1"
SMOKE_SECONDS = float(os.environ.get("RR_SMOKE_SECONDS") or 12.0)
SMOKE_OUT = os.environ.get("RR_SMOKE_OUT") or ""
SMOKE_MENU_SECONDS = 2.0            # menu idle before the scripted start; see smoke_step

_SESSION = None
_DISABLED = object()


def load_config(path=SETTINGS):
    """Tunables are data: the same JSON feeds the scene builder and the runtime."""
    with open(path, encoding="utf-8") as handle:
        return PrototypeConfig(**json.load(handle))


def float_height(cfg):
    """Resting z where the heave spring balances weight, so spawns do not bounce."""
    return cfg.raft_height / 2.0 - cfg.mass * 9.81 / cfg.stiffness


def resting_bounds(cfg):
    """Accepted idle z band: the wave band around `float_height`, plus heave lag.

    The water surface itself moves +/- `wave_amplitude` around the resting
    height, and the heave damping term can hold the hull
    `damping * amplitude * frequency / stiffness` (4.2 mm here) away from that
    band. Both numbers are derived from the existing heave constants, so this
    quotes the code's own resting-height constants instead of adding a tolerance.
    """
    rest = float_height(cfg)
    wave = cfg.wave_amplitude
    lag = cfg.damping * wave * cfg.wave_frequency / cfg.stiffness
    return rest - wave - lag, rest + wave + lag


class Session:
    """One prototype run: owns engine objects, gameplay state and audio."""

    def __init__(self, scene):
        self.disabled = False
        try:
            self._initialize(scene)
        except Exception:  # noqa: BLE001 - engine callback must not flood logs
            self.disable()

    def disable(self):
        """Disable this session and report the current exception exactly once."""
        if not self.disabled:
            self.disabled = True
            traceback.print_exc()

    def _initialize(self, scene):
        self.scene = scene
        self.cfg = load_config()
        self.game = Prototype(self.cfg)
        self.audio = PrototypeAudio(ROOT)
        self.body = scene.objects[BODY_NAME]
        self.camera = scene.objects.get(CAMERA_NAME)
        self.hud = scene.objects.get(HUD_NAME)
        self.prompt = scene.objects.get(PROMPT_NAME)
        oar_cfg = OarConfig()
        self.oars = (Oar(-1, oar_cfg), Oar(+1, oar_cfg))
        self.held = set()
        self.hover_latched = False
        self.mouse_latched = False
        self._text_setters = {}
        self.teleport_guard = TeleportGuard()
        self.last_splash = float("-inf")
        self.smoke = ({"frames": 0, "seconds": 0.0, "max_y": self.cfg.start_y,
                       "max_speed": 0.0, "min_z": 1e9, "max_z": -1e9,
                       "menu_frames": 0, "menu_min_z": 1e9, "menu_max_z": -1e9}
                      if SMOKE else None)
        self.body.collisionCallbacks.append(self.on_collision)
        self.place_body(self.cfg.start_y)
        self.audio.set_mode("menu")
        self.write_hud(0.0)

    # ---------------- input ----------------

    def poll_keys(self):
        """Return (held, newly pressed). Edges are derived here, not from bge queues."""
        keyboard = bge.logic.keyboard
        down = set()
        for action, attribute in KEY_EVENTS.items():
            code = getattr(bge.events, attribute, None)
            if code is None:
                continue
            try:
                if keyboard.inputs[code].active:
                    down.add(action)
            except (KeyError, IndexError):
                continue
        edges = down - self.held
        self.held = down
        return down, edges

    def poll_pointer(self):
        """Mouse over the prompt gives a real hover cue; a click there confirms."""
        if self.game.mode not in ("menu", "complete"):
            self.hover_latched = False
            self.mouse_latched = False
            return False
        mouse = getattr(bge.logic, "mouse", None)
        if mouse is None:
            return False
        x, y = mouse.position
        x0, y0, x1, y1 = PROMPT_RECT
        over = x0 <= x <= x1 and y0 <= y <= y1
        if over and not self.hover_latched:
            self.audio.event("hover")
        self.hover_latched = over
        code = getattr(bge.events, "LEFTMOUSE", None)
        pressed = False
        if code is not None:
            try:
                pressed = bool(mouse.inputs[code].active)
            except (KeyError, IndexError):
                pressed = False
        clicked = over and pressed and not self.mouse_latched
        self.mouse_latched = pressed
        return clicked

    # ---------------- lifecycle ----------------

    def handle_commands(self, edges, confirmed):
        if "QUIT" in edges:
            self.audio.event("click")
            self.audio.close()
            bge.logic.endGame()
            return
        if "MENU" in edges and self.game.mode != "menu":
            self.audio.event("click")
            self.game.command("menu")
            self.place_body(self.cfg.start_y)
            return
        if "PAUSE" in edges and self.game.mode in ("playing", "paused"):
            self.audio.event("click")
            self.game.command("pause")
            return
        if ("START" in edges or confirmed) and self.game.mode in ("menu", "complete"):
            self.audio.event("click")
            action = "restart" if self.game.mode == "complete" else "start"
            if self.game.command(action):
                self.place_body(self.cfg.start_y)

    def place_body(self, y):
        """Teleport and settle: docs/07 section 8 rule 4 requires zeroed velocities."""
        body = self.body
        body.worldPosition = (0.0, y, float_height(self.cfg))
        body.worldOrientation = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        body.worldLinearVelocity = (0.0, 0.0, 0.0)
        body.worldAngularVelocity = (0.0, 0.0, 0.0)
        self.teleport_guard.reset()
        self.last_splash = float("-inf")

    # ---------------- driving ----------------

    def drive(self, dt, down):
        """Stroke and steer. Playing only: thrust must not exist in other modes."""
        left_down, right_down, direction = controls(down)
        before = tuple(oar.phase for oar in self.oars)
        outputs = (self.oars[0].update(dt, left_down, direction),
                   self.oars[1].update(dt, right_down, direction))
        self.stroke_audio(before, tuple(oar.phase for oar in self.oars))
        self.apply_forces(sum(out.thrust for out in outputs),
                          sum(out.torque_z for out in outputs))
        self.contain_banks()
        self.clamp_motion()
        self.splash_audio(tuple(self.body.worldLinearVelocity))

    def apply_forces(self, thrust, paddle_torque):
        """One force step for the current mode; `rr.core.prototype` owns the split."""
        body = self.body
        world, torque = frame_forces(
            self.cfg,
            self.game.mode,
            body.worldPosition.z,
            tuple(body.worldLinearVelocity),
            body.worldOrientation.to_euler().z,
            body.localAngularVelocity.z,
            thrust,
            paddle_torque,
            self.game.elapsed,
        )
        body.applyForce(world, False)
        body.applyTorque((0.0, 0.0, torque), False)

    def contain_banks(self):
        """Keep the raft in the water without a hard wall: a damped spring push."""
        cfg = self.cfg
        limit = cfg.bank_x - cfg.raft_width / 2.0
        x = self.body.worldPosition.x
        overshoot = abs(x) - limit
        if overshoot <= 0.0:
            return
        sign = 1.0 if x > 0.0 else -1.0
        outward = max(0.0, sign * self.body.worldLinearVelocity.x)
        push = min(cfg.max_force, BANK_SPRING * overshoot + BANK_DAMPING * outward)
        self.body.applyForce((-sign * push, 0.0, 0.0), False)

    def clamp_motion(self):
        """docs/07 section 8 rule 1: bound speed and spin every step."""
        cfg = self.cfg
        body = self.body
        velocity = body.worldLinearVelocity
        speed = velocity.length
        if speed > cfg.max_speed:
            body.worldLinearVelocity = velocity * (cfg.max_speed / speed)
        spin = body.localAngularVelocity
        if abs(spin.z) > cfg.max_spin:
            body.localAngularVelocity = (spin.x, spin.y, math.copysign(cfg.max_spin, spin.z))

    # ---------------- audio from real events ----------------

    def stroke_audio(self, before, after):
        for old, new in zip(before, after, strict=True):
            if old is new:
                continue
            if new is OarPhase.DIP:
                self.audio.event("paddle_dip")
            elif new is OarPhase.PULL:
                self.audio.event("paddle")
            elif new is OarPhase.RECOVER and old is OarPhase.PULL:
                self.audio.event("paddle_exit")

    def splash_audio(self, velocity):
        relative = abs(velocity[1] - self.cfg.flow_speed)
        if ((relative > SPLASH_SPEED or abs(velocity[0]) > SPLASH_SPEED)
                and self.game.elapsed - self.last_splash >= EVENTS["splash"].cooldown):
            self.last_splash = self.game.elapsed
            self.audio.event("splash")

    def on_collision(self, other, point=None, normal=None):
        """Bullet contact callback. Only registered impacts make a sound."""
        if self.disabled:
            return
        try:
            self._collision()
        except Exception:  # noqa: BLE001 - engine callback must not flood logs
            self.disable()

    def _collision(self):
        if self.game.mode != "playing":
            return
        hits = self.game.hits
        damage = self.game.impact(self.body.worldLinearVelocity.length)
        if self.game.hits == hits:
            return
        self.audio.event("bump_hard" if damage >= 1 else "bump_soft")

    # ---------------- presentation ----------------

    def follow_camera(self, dt):
        if self.camera is None:
            return
        target = self.body.worldPosition
        desired = (target.x * CAMERA_SWAY + CAMERA_OFFSET[0],
                   target.y + CAMERA_OFFSET[1],
                   CAMERA_OFFSET[2])
        current = self.camera.worldPosition
        blend = min(1.0, dt / CAMERA_LAG)
        self.camera.worldPosition = [current[i] + (desired[i] - current[i]) * blend
                                     for i in range(3)]

    def _text_setter(self, obj):
        """Find a way to write this font object's string, or None.

        UPBGE builds disagree here. This build's KX_FontObject exposes no `text`
        attribute at all (verified: the only name-matching members are
        disableRigidBody/enableRigidBody), so fall back to the wrapped Blender
        datablock, which is the documented escape hatch.
        """
        for name in ("text", "string"):
            if hasattr(obj, name):
                return lambda value, name=name: setattr(obj, name, value)
        data = getattr(getattr(obj, "blenderObject", None), "data", None)
        if data is not None and hasattr(data, "body"):
            return lambda value: setattr(data, "body", value)
        print(f"[rr] no HUD text setter on {type(obj).__name__}; members: "
              f"{sorted(a for a in dir(obj) if not a.startswith('__'))}", flush=True)
        return None

    def _set_text(self, obj, value):
        if obj is None:
            return
        key = id(obj)
        if key not in self._text_setters:
            self._text_setters[key] = self._text_setter(obj)
        setter = self._text_setters[key]
        if setter is None:
            return
        try:
            setter(value)
        except Exception as exc:   # noqa: BLE001 - the HUD must never break gameplay
            self._text_setters[key] = None
            print(f"[rr] HUD text write failed: {type(exc).__name__}: {exc}", flush=True)

    def write_hud(self, speed):
        self._set_text(self.hud, hud_text(self.game, speed))
        self._set_text(self.prompt, prompt_text(self.game))

    # ---------------- smoke mode ----------------

    def smoke_step(self, dt):
        """Autopaddle and record what actually happened inside UPBGE.

        The menu is idled first (SMOKE_MENU_SECONDS): Bullet keeps gravity on in
        every mode, so a heave force that only runs while playing shows up as a
        falling raft here instead of passing unnoticed, as it did before.
        """
        probe = self.smoke
        probe["frames"] += 1
        probe["seconds"] += dt
        position = self.body.worldPosition
        if self.game.mode == "menu":
            probe["menu_frames"] += 1
            probe["menu_min_z"] = min(probe["menu_min_z"], position.z)
            probe["menu_max_z"] = max(probe["menu_max_z"], position.z)
            if probe["seconds"] < SMOKE_MENU_SECONDS:
                return set()
            self.game.command("start")
            self.place_body(self.cfg.start_y)
            position = self.body.worldPosition
        probe["max_y"] = max(probe["max_y"], position.y)
        probe["max_speed"] = max(probe["max_speed"], self.body.worldLinearVelocity.length)
        probe["min_z"] = min(probe["min_z"], position.z)
        probe["max_z"] = max(probe["max_z"], position.z)
        if probe["seconds"] < SMOKE_SECONDS:
            return {"A", "D"}
        audio = self.audio
        low, high = resting_bounds(self.cfg)
        menu_ok = (probe["menu_frames"] > 0
                   and low <= probe["menu_min_z"] <= probe["menu_max_z"] <= high)
        report = {
            "ok": (probe["frames"] > 60
                   and menu_ok
                   and probe["max_y"] - self.cfg.start_y > 1.0
                   and audio.error_count == 0
                   and self.game.mode in ("playing", "complete")),
            "frames": probe["frames"], "seconds": round(probe["seconds"], 3),
            "mode": self.game.mode, "hull": self.game.hull, "hits": self.game.hits,
            "progress": round(self.game.progress, 4),
            "start_y": self.cfg.start_y, "max_y": round(probe["max_y"], 3),
            "distance_m": round(probe["max_y"] - self.cfg.start_y, 3),
            "max_speed_mps": round(probe["max_speed"], 3),
            "z_range": [round(probe["min_z"], 4), round(probe["max_z"], 4)],
            "menu_seconds": SMOKE_MENU_SECONDS,
            "menu_frames": probe["menu_frames"],
            "menu_z_range": ([round(probe["menu_min_z"], 4), round(probe["menu_max_z"], 4)]
                             if probe["menu_frames"] else None),
            "menu_ok": menu_ok,
            "rest_z_bounds": [round(low, 4), round(high, 4)],
            "audio_played": dict(audio.played_counts),
            "audio_dropped": dict(audio.dropped_counts),
            "audio_modes": dict(audio.mode_counts),
            "audio_errors": audio.error_count,
            "audio_error_samples": list(audio.errors)[:5],
            "audio_device": audio.device is not None,
            "auditioned": False,
        }
        text = json.dumps(report, indent=2)
        print("PROTOTYPE_SMOKE " + json.dumps(report), flush=True)
        if SMOKE_OUT:
            try:
                with open(SMOKE_OUT, "w", encoding="utf-8") as handle:
                    handle.write(text + "\n")
            except OSError as exc:
                print(f"PROTOTYPE_SMOKE_WRITE_FAILED {exc}", flush=True)
        self.audio.close()
        bge.logic.endGame()
        return set()

    # ---------------- frame ----------------

    def update(self):
        dt = 1.0 / max(bge.logic.getLogicTicRate(), 1.0)
        if self.smoke is not None:
            down = self.smoke_step(dt)
        else:
            down, edges = self.poll_keys()
            self.handle_commands(edges, self.poll_pointer())
        if self.teleport_guard.step():
            # Bullet keeps integrating in every mode, so heave must be applied
            # outside "playing" too; only strokes and steering are playing-only.
            if self.game.mode == "playing":
                self.drive(dt, down & PADDLE_KEYS)
            else:
                self.apply_forces(0.0, 0.0)
        self.game.advance(dt, self.body.worldPosition.y)
        if self.game.respawn_pending:
            self.place_body(self.game.checkpoint_y)
            self.game.respawned()
            self.audio.event("splash")
        if self.game.mode in MODE_LOOPS:
            self.audio.set_mode(self.game.mode)
        self.follow_camera(dt)
        self.write_hud(self.body.worldLinearVelocity.length)


def tick(controller):
    """Always-sensor entry point. Builds the session on the first frame."""
    global _SESSION
    if _SESSION is _DISABLED:
        return
    try:
        if _SESSION is None:
            _SESSION = Session(controller.owner.scene)
        if not _SESSION.disabled:
            _SESSION.update()
    except Exception:  # noqa: BLE001 - engine callback must not flood logs
        if _SESSION is None:
            _SESSION = _DISABLED
            traceback.print_exc()
        else:
            _SESSION.disable()
