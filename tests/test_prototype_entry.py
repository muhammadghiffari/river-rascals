"""Gameplay wiring tests for game/prototype_entry.py.

A fake `bge` lets the real adapter run headlessly, so force application,
collision damage, audio cues and mode changes are exercised rather than assumed.
This is NOT a claim that UPBGE runtime behaviour was verified.
"""
import contextlib
import importlib
import importlib.util
import io
import math
import sys
import unittest
from collections import defaultdict
from pathlib import Path, PurePosixPath, PureWindowsPath
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
    """Builds the fake engine, loads the adapter and drives frames.

    Teardown is registered with the test case's `addCleanup` as soon as each
    patch goes live, so a failure part-way through construction still reverts
    `sys.modules`. Previously a raise between `patch.start()` and cleanup
    registration leaked the fake `bge`/`aud` into every later test.
    """

    def __init__(self, cleanup):
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
        patcher = patch.dict(sys.modules, {"bge": self.bge, "aud": self.aud})
        patcher.start()
        cleanup(patcher.stop)
        # A private module object per test, rather than mutating the import
        # cache: module globals such as `_SESSION` and the cached HUD setters
        # start clean every time and nothing has to be deleted afterwards.
        spec = importlib.util.spec_from_file_location(
            "prototype_entry", ROOT / "game" / "prototype_entry.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.session = self.module.Session(self.scene)
        cleanup(self.session.audio.close)

    def hold(self, *names):
        for code in KEY_CODES.values():
            self.keyboard.inputs[code].active = False
        for name in names:
            self.keyboard.inputs[KEY_CODES[name]].active = True

    def frames(self, count=1):
        for _ in range(count):
            self.session.update()

    def cues(self, fragment):
        """Find played cues by logical path, independent of host separator.

        The adapter hands `aud` a native filesystem path, so on Windows the
        recorded string is `...\\audio\\music\\MUS_Menu_01.ogg`. Matching a
        forward-slash fragment against that raw string never succeeds, which is
        why only the slash-bearing assertions failed there.
        """
        return [p for p in self.device.played if fragment in p.replace("\\", "/")]


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness(self.addCleanup)

    def test_splash_events_follow_policy_cooldown(self):
        session = self.h.session
        from rr.core.prototype_audio import EVENTS

        with patch.object(session.audio, "event") as event:
            session.game.elapsed = 0
            session.splash_audio((0, 10, 0))
            session.game.elapsed = EVENTS["splash"].cooldown / 2
            session.splash_audio((0, 10, 0))
            session.game.elapsed = EVENTS["splash"].cooldown
            session.splash_audio((0, 10, 0))
        self.assertEqual(event.call_count, 2)

    def test_tick_failure_is_logged_once_and_disables_session(self):
        module = self.h.module
        module._SESSION = self.h.session
        controller = SimpleNamespace(owner=SimpleNamespace(scene=self.h.scene))
        output = io.StringIO()
        with patch.object(self.h.session, "update", side_effect=RuntimeError("frame failed")) as update:
            with contextlib.redirect_stderr(output):
                module.tick(controller)
                module.tick(controller)
        self.assertEqual(update.call_count, 1)
        self.assertEqual(output.getvalue().count("Traceback (most recent call last)"), 1)

    def test_initialization_failure_is_logged_once(self):
        module = self.h.module
        controller = SimpleNamespace(owner=SimpleNamespace(scene=SimpleNamespace(objects={})))
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            module.tick(controller)
            module.tick(controller)
        self.assertEqual(output.getvalue().count("Traceback (most recent call last)"), 1)

    def test_collision_failure_is_logged_once_and_disables_tick(self):
        module = self.h.module
        module._SESSION = self.h.session
        self.h.session.game.mode = "playing"
        controller = SimpleNamespace(owner=SimpleNamespace(scene=self.h.scene))
        output = io.StringIO()
        with patch.object(self.h.session.game, "impact", side_effect=RuntimeError("bad collision")) as impact:
            with contextlib.redirect_stderr(output):
                self.h.session.on_collision(None)
                self.h.session.on_collision(None)
                module.tick(controller)
        self.assertEqual(impact.call_count, 1)
        self.assertEqual(output.getvalue().count("Traceback (most recent call last)"), 1)

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
        self.h.frames(2)
        self.h.body.worldPosition = (self.h.session.game.cfg.bank_x, 20.0, 0.31)
        self.h.body.forces.clear()
        self.h.frames()
        self.assertTrue(any(f[0] < 0 for f in self.h.body.forces), "no inward bank force")

    def test_speed_and_spin_are_clamped(self):
        cfg = self.h.session.game.cfg
        self.h.hold("ENTERKEY")
        self.h.frames(2)
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

    def test_cue_matching_is_separator_independent(self):
        """A Windows-flavoured path must still match its logical cue."""
        self.h.device.played.append("C:\\repo\\assets\\audio\\music\\MUS_Menu_01.ogg")
        self.assertTrue(self.h.cues("music/MUS_Menu_01.ogg"))


class PathFlavourTests(unittest.TestCase):
    """The adapter hands `aud` a native path, so cue assertions must normalise.

    Regression for the two tests that failed only on Windows. `PrototypeAudio`
    builds `Path(root) / "assets" / "audio" / "music/MUS_Menu_01.ogg"`, which
    renders with backslashes there. Fragments without a separator
    (`"SFX_PaddleDip"`) matched anyway, which is why exactly the three
    slash-bearing assertions broke and nothing else did.
    """

    def _play_menu(self, flavour):
        from rr.glue import prototype_audio as glue

        device = FakeDevice()
        aud = SimpleNamespace(Device=lambda: device, Sound=lambda path: path)
        with patch.dict(sys.modules, {"aud": aud}), patch.object(glue, "Path", flavour):
            audio = glue.PrototypeAudio("C:/repo")
            self.addCleanup(audio.close)
            audio.set_mode("menu")
        self.assertEqual(audio.error_count, 0, list(audio.errors))
        self.assertEqual(len(device.played), 1)
        return device.played[0]

    def test_windows_paths_use_backslashes_and_still_resolve(self):
        played = self._play_menu(PureWindowsPath)
        self.assertIn("\\", played)
        # The pre-fix assertion style silently failed on exactly this string.
        self.assertNotIn("music/MUS_Menu_01.ogg", played)
        self.assertIn("music/MUS_Menu_01.ogg", played.replace("\\", "/"))

    def test_posix_paths_are_unaffected(self):
        played = self._play_menu(PurePosixPath)
        self.assertNotIn("\\", played)
        self.assertIn("music/MUS_Menu_01.ogg", played)


class IsolationTests(unittest.TestCase):
    """Teardown must be deterministic, with no import-cache surgery."""

    def test_construction_failure_still_reverts_sys_modules(self):
        baseline = {name: name in sys.modules for name in ("bge", "aud")}
        cleanups = []
        with patch.object(importlib.util, "module_from_spec", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                Harness(cleanups.append)
        self.assertTrue(cleanups, "no cleanup was registered before the failure")
        for undo in reversed(cleanups):
            undo()
        self.assertEqual({name: name in sys.modules for name in ("bge", "aud")}, baseline)

    def test_harness_does_not_touch_the_import_cache(self):
        before = "prototype_entry" in sys.modules
        cleanups = []
        harness = Harness(cleanups.append)
        self.assertIsNone(harness.module.__dict__.get("_SESSION"))
        self.assertEqual("prototype_entry" in sys.modules, before,
                         "the harness must not register its private module globally")
        for undo in reversed(cleanups):
            undo()


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
