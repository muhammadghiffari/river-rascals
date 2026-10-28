"""Gameplay wiring tests for game/prototype_entry.py.

A fake `bge` lets the real adapter run headlessly, so force application,
collision damage, audio cues and mode changes are exercised rather than assumed.
This is NOT a claim that UPBGE runtime behaviour was verified.
"""
import importlib
import importlib.util
import math
import sys
import unittest
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

KEY_CODES = {
    "AKEY": 1, "DKEY": 2, "SKEY": 3, "LEFTARROWKEY": 4, "RIGHTARROWKEY": 5,
    "DOWNARROWKEY": 6, "ENTERKEY": 7, "PKEY": 8, "ESCKEY": 9, "QKEY": 10,
    "LEFTMOUSE": 11,
}


class Vec:
    """Minimal stand-in for mathutils.Vector covering what the adapter uses."""

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __getitem__(self, index):
        return (self.x, self.y, self.z)[index]

    def __mul__(self, scalar):
        return Vec(self.x * scalar, self.y * scalar, self.z * scalar)

    @property
    def length(self):
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)


def _as_vec(value):
    return value if isinstance(value, Vec) else Vec(*value)


class Orientation:
    def __init__(self, yaw=0.0):
        self.yaw = yaw

    def to_euler(self):
        return Vec(0.0, 0.0, self.yaw)


def _as_orientation(value):
    """BGE turns an assigned 3x3 sequence into a Matrix; mirror that here."""
    if isinstance(value, Orientation):
        return value
    rows = [list(row) for row in value]
    return Orientation(math.atan2(rows[1][0], rows[0][0]))


class FakeBody:
    """Records applied forces/torques instead of integrating them."""

    def __init__(self, y):
        self._position = Vec(0.0, y, 0.31)
        self._linear = Vec()
        self._angular_local = Vec()
        self._angular_world = Vec()
        self._orientation = Orientation()
        self.collisionCallbacks = []
        self.forces = []
        self.torques = []

    worldPosition = property(lambda self: self._position,
                             lambda self, v: setattr(self, "_position", _as_vec(v)))
    worldLinearVelocity = property(lambda self: self._linear,
                                   lambda self, v: setattr(self, "_linear", _as_vec(v)))
    localAngularVelocity = property(lambda self: self._angular_local,
                                    lambda self, v: setattr(self, "_angular_local", _as_vec(v)))
    worldAngularVelocity = property(lambda self: self._angular_world,
                                    lambda self, v: setattr(self, "_angular_world", _as_vec(v)))
    worldOrientation = property(lambda self: self._orientation,
                                lambda self, v: setattr(self, "_orientation", _as_orientation(v)))

    def applyForce(self, vector, local):
        self.forces.append(tuple(vector))

    def applyTorque(self, vector, local):
        self.torques.append(tuple(vector))


class FakeText:
    def __init__(self):
        self.text = ""


class FakeCamera:
    def __init__(self):
        self._position = Vec(0.0, -6.5, 6.5)

    worldPosition = property(lambda self: self._position,
                             lambda self, v: setattr(self, "_position", _as_vec(v)))


class FakeHandle:
    status = 1

    def stop(self):
        self.status = 0


class FakeDevice:
    def __init__(self):
        self.played = []

    def lock(self):
        pass

    def unlock(self):
        pass

    def play(self, sound):
        self.played.append(sound)
        return FakeHandle()


class Harness:
    """Builds the fake engine, imports the adapter fresh and drives frames."""

    def __init__(self):
        self.body = FakeBody(4.0)
        self.camera = FakeCamera()
        self.hud, self.prompt = FakeText(), FakeText()
        self.scene = SimpleNamespace(objects={
            "RF_RaftT1": self.body, "Cam_Main": self.camera,
            "UI_HudText": self.hud, "UI_PromptText": self.prompt,
        })
        self.keyboard = SimpleNamespace(inputs=defaultdict(lambda: SimpleNamespace(active=False)))
        self.mouse = SimpleNamespace(position=(0.5, 0.95),
                                     inputs=defaultdict(lambda: SimpleNamespace(active=False)))
        self.ended = []
        self.device = FakeDevice()
        self.bge = SimpleNamespace(
            logic=SimpleNamespace(keyboard=self.keyboard, mouse=self.mouse,
                                  getLogicTicRate=lambda: 60.0,
                                  endGame=lambda: self.ended.append(True)),
            events=SimpleNamespace(**KEY_CODES),
        )
        self.aud = SimpleNamespace(Device=lambda: self.device, Sound=lambda path: path)
        self.patch = patch.dict(sys.modules, {"bge": self.bge, "aud": self.aud})
        self.patch.start()
        sys.modules.pop("prototype_entry", None)
        spec = importlib.util.spec_from_file_location(
            "prototype_entry", ROOT / "game" / "prototype_entry.py")
        self.module = importlib.util.module_from_spec(spec)
        sys.modules["prototype_entry"] = self.module
        spec.loader.exec_module(self.module)
        self.session = self.module.Session(self.scene)

    def stop(self):
        self.session.audio.close()
        sys.modules.pop("prototype_entry", None)
        self.patch.stop()

    def hold(self, *names):
        for code in KEY_CODES.values():
            self.keyboard.inputs[code].active = False
        for name in names:
            self.keyboard.inputs[KEY_CODES[name]].active = True

    def frames(self, count=1):
        for _ in range(count):
            self.session.update()

    def cues(self, prefix):
        return [p for p in self.device.played if prefix in p]


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.addCleanup(self.h.stop)

    def test_starts_in_menu_with_menu_music_and_prompt(self):
        self.assertEqual(self.h.session.game.mode, "menu")
        self.assertTrue(self.h.cues("music/MUS_Menu_01.ogg"))
        self.assertIn("RIVER RASCALS", self.h.prompt.text)

    def test_enter_starts_play_and_swaps_to_river_loops(self):
        self.h.hold("ENTERKEY")
        self.h.frames()
        self.assertEqual(self.h.session.game.mode, "playing")
        self.assertTrue(self.h.cues("ambience/AMB_Creek_01.ogg"))
        self.assertTrue(self.h.cues("sfx/SFX_WaterRushLoop_01.ogg"))
        self.assertEqual(self.h.prompt.text, "")

    def test_paddling_pushes_forward_and_plays_the_stroke(self):
        self.h.hold("ENTERKEY")
        self.h.frames()
        self.h.hold("AKEY")
        self.h.frames(20)
        self.assertTrue(self.h.cues("SFX_PaddleDip"), "dip cue never fired")
        self.assertTrue(self.h.cues("SFX_PaddlePull"), "pull cue never fired")
        self.assertGreater(max(f[1] for f in self.h.body.forces), 0.0)
        self.h.hold()
        self.h.frames(3)
        self.assertTrue(self.h.cues("SFX_PaddleExit"), "exit cue never fired")

    def test_registered_collision_damages_hull_and_sounds_once(self):
        self.h.hold("ENTERKEY")
        self.h.frames()
        self.h.body.worldLinearVelocity = (0.0, 4.0, 0.0)
        self.assertEqual(len(self.h.body.collisionCallbacks), 1)
        self.h.body.collisionCallbacks[0](object())
        self.assertLess(self.h.session.game.hull, self.h.session.game.cfg.max_hull)
        self.assertEqual(len(self.h.cues("SFX_RaftBumpHard")), 1)
        self.h.body.collisionCallbacks[0](object())   # inside the impact cooldown
        self.assertEqual(len(self.h.cues("SFX_RaftBumpHard")), 1)

    def test_reaching_the_finish_completes_and_restarts(self):
        self.h.hold("ENTERKEY")
        self.h.frames()
        self.h.body.worldPosition = (0.0, self.h.session.game.cfg.finish_y, 0.31)
        self.h.frames()
        self.assertEqual(self.h.session.game.mode, "complete")
        self.assertIn("FINISH", self.h.prompt.text)
        self.h.hold()
        self.h.frames()
        self.h.hold("ENTERKEY")
        self.h.frames()
        self.assertEqual(self.h.session.game.mode, "playing")
        self.assertEqual(self.h.body.worldPosition.y, self.h.session.game.cfg.start_y)

    def test_pause_silences_loops_and_freezes_elapsed(self):
        self.h.hold("ENTERKEY")
        self.h.frames()
        self.h.hold()
        self.h.frames()
        self.h.hold("PKEY")
        self.h.frames()
        self.assertEqual(self.h.session.game.mode, "paused")
        self.assertEqual(self.h.session.audio.loops, [])
        elapsed = self.h.session.game.elapsed
        self.h.hold()
        self.h.frames(10)
        self.assertEqual(self.h.session.game.elapsed, elapsed)
        self.assertIn("PAUSED", self.h.prompt.text)

    def test_bank_contact_pushes_back_towards_the_water(self):
        self.h.hold("ENTERKEY")
        self.h.frames()
        self.h.body.worldPosition = (self.h.session.game.cfg.bank_x, 20.0, 0.31)
        self.h.body.forces.clear()
        self.h.frames()
        self.assertTrue(any(f[0] < 0 for f in self.h.body.forces), "no inward bank force")

    def test_speed_and_spin_are_clamped(self):
        cfg = self.h.session.game.cfg
        self.h.hold("ENTERKEY")
        self.h.frames()
        self.h.body.worldLinearVelocity = (0.0, 99.0, 0.0)
        self.h.body.localAngularVelocity = (0.0, 0.0, 12.0)
        self.h.frames()
        self.assertLessEqual(self.h.body.worldLinearVelocity.length, cfg.max_speed + 1e-6)
        self.assertLessEqual(abs(self.h.body.localAngularVelocity.z), cfg.max_spin + 1e-6)

    def test_quit_ends_the_game_and_closes_audio(self):
        self.h.hold("QKEY")
        self.h.frames()
        self.assertEqual(self.h.ended, [True])
        self.assertTrue(self.h.session.audio.closed)

    def test_mouse_over_prompt_hovers_and_click_starts(self):
        self.h.mouse.position = (0.5, 0.7)
        self.h.frames()
        self.assertTrue(self.h.cues("UI_Hover"), "hover cue never fired")
        self.h.mouse.inputs[KEY_CODES["LEFTMOUSE"]].active = True
        self.h.frames()
        self.assertEqual(self.h.session.game.mode, "playing")

    def test_hud_reports_live_state(self):
        self.h.hold("ENTERKEY")
        self.h.frames()
        self.h.body.worldLinearVelocity = (0.0, 3.0, 0.0)
        self.h.frames()
        self.assertIn("PLAYING", self.h.hud.text)
        self.assertIn("hull [#####]", self.h.hud.text)
        self.assertIn("3.0 m/s", self.h.hud.text)

    def test_camera_follows_the_raft_downstream(self):
        self.h.hold("ENTERKEY")
        self.h.frames()
        before = self.h.camera.worldPosition.y
        self.h.body.worldPosition = (0.0, 100.0, 0.31)
        self.h.frames(60)
        self.assertGreater(self.h.camera.worldPosition.y, before)
        self.assertAlmostEqual(self.h.camera.worldPosition.y, 100.0 - 10.5, delta=1.0)


class ResourceTests(unittest.TestCase):
    """Every cue the policy can select must resolve to a real file on disk."""

    def test_every_event_variation_exists(self):
        from rr.core.prototype_audio import EVENTS

        missing = []
        for name, spec in EVENTS.items():
            for index in range(1, spec.variations + 1):
                path = ROOT / "assets" / "audio" / f"{spec.prefix}_{index:02d}.ogg"
                if not path.is_file():
                    missing.append(f"{name} -> {path.relative_to(ROOT)}")
        self.assertEqual(missing, [])

    def test_every_mode_loop_exists(self):
        from rr.core.prototype_audio import MODE_LOOPS

        missing = [f"{mode} -> {path}" for mode, loops in MODE_LOOPS.items()
                   for path, _ in loops if not (ROOT / "assets" / "audio" / path).is_file()]
        self.assertEqual(missing, [])

    def test_settings_file_matches_the_config_dataclass(self):
        import dataclasses
        import json

        from rr.core.prototype import PrototypeConfig

        data = json.loads((ROOT / "game/settings/prototype.json").read_text())
        names = {field.name for field in dataclasses.fields(PrototypeConfig)}
        self.assertEqual(set(data), names)
        PrototypeConfig(**data)

    def test_build_and_wiring_passes_agree_on_the_controller_target(self):
        build = (ROOT / "tools/blender/build_prototype.py").read_text()
        self.assertIn('CONTROLLER_MODULE = "prototype_entry.tick"', build)
        self.assertIn('"controller_module": CONTROLLER_MODULE', build)
        # The geometry pass must not try to add logic bricks: that crashes in -b.
        # Comments may name the operator, so inspect code lines only.
        code = "\n".join(line.split("#")[0] for line in build.splitlines())
        self.assertNotIn("bpy.ops.logic.", code)
        wire = (ROOT / "tools/blender/wire_prototype_logic.py").read_text()
        self.assertIn("bpy.ops.logic.sensor_add", wire)
        self.assertIn("bpy.ops.logic.controller_add", wire)
        self.assertIn("temp_override", wire)

    def test_controller_target_module_exposes_tick(self):
        entry = ROOT / "game/prototype_entry.py"
        self.assertTrue(entry.is_file())
        self.assertIn("def tick(controller)", entry.read_text())


if __name__ == "__main__":
    unittest.main()
