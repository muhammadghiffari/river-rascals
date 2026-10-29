"""Exit-code contract of tools/run_game.py, verified with a stub engine (no UPBGE needed)."""
import contextlib
import importlib.util
import io
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
RUN_GAME = ROOT / "tools" / "run_game.py"

_spec = importlib.util.spec_from_file_location("rr_run_game", RUN_GAME)
run_game = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_game)

# 0xC0000005, the classic Windows access-violation exit status. POSIX keeps only the low
# 8 bits of a child exit status, so the stub's exit lands on 0x05 there.
CRASH_STATUS = 3221225477
CRASH_STATUS_POSIX = CRASH_STATUS & 0xFF

# Stub engine: the scenario is encoded in the "blend" filename the runner passes as argv[1].
# The report is written only when the runner asks for one (RR_SMOKE_OUT, i.e. --smoke mode).
STUB_GAME = """\
import json
import os
import sys

scenario = os.path.basename(sys.argv[1])
out = os.environ.get("RR_SMOKE_OUT")


def report(ok):
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"ok": ok}, fh)


if scenario == "ok0.blend":
    report(True)
elif scenario == "exit3.blend":
    report(True)
    sys.exit(3)
elif scenario == "exit3_noreport.blend":
    sys.exit(3)
elif scenario == "crash.blend":
    sys.exit(%d)
elif scenario == "badjson.blend":
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write("{not json")
elif scenario == "notok.blend":
    report(False)
elif scenario == "silent.blend":
    pass
else:
    sys.exit(99)
sys.exit(0)
""" % CRASH_STATUS


class FmtExitCodeTests(unittest.TestCase):
    def test_windows_crash_status_shows_decimal_and_hex(self):
        self.assertEqual(run_game.fmt_exit_code(CRASH_STATUS), "3221225477 (0xC0000005)")

    def test_small_code_is_zero_padded_hex(self):
        self.assertEqual(run_game.fmt_exit_code(3), "3 (0x00000003)")

    def test_negative_signal_code_prints_as_is(self):
        self.assertEqual(run_game.fmt_exit_code(-11), "-11")


class SmokeTimeoutTests(unittest.TestCase):
    """The timeout path without spawning anything: subprocess.run is mocked."""

    def test_smoke_timeout_returns_2(self):
        bin_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bin_dir, ignore_errors=True)
        (Path(bin_dir) / "blenderplayer").touch()  # find_exe only checks existence
        argv = ["run_game.py", "dummy.blend", "--smoke"]
        expired = subprocess.TimeoutExpired(cmd="blenderplayer", timeout=1.0)
        with mock.patch.object(run_game.sys, "argv", argv), \
                mock.patch.dict(os.environ, {"UPBGE_PATH": bin_dir}), \
                mock.patch.object(run_game.subprocess, "run", side_effect=expired):
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                rc = run_game.main()
        self.assertEqual(rc, 2)
        self.assertIn("SMOKE FAIL: timeout", captured.getvalue())


class StubEngineTests(unittest.TestCase):
    """End-to-end through the real script with a stub blenderplayer built on sys.executable."""

    def setUp(self):
        if os.name != "posix" or not shutil.which("sh"):
            self.skipTest("executable stub engine requires a POSIX shell")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin_dir = Path(self.tmp.name) / "bin"
        self.bin_dir.mkdir()
        stub = self.bin_dir / "stub_game.py"
        stub.write_text(STUB_GAME, encoding="utf-8")
        launcher = self.bin_dir / "blenderplayer"
        launcher.write_text(
            "#!/bin/sh\nexec %s %s \"$@\"\n" % (shlex.quote(sys.executable), shlex.quote(str(stub))),
            encoding="utf-8",
        )
        launcher.chmod(0o755)

    def run_runner(self, scenario, *extra):
        env = {**os.environ, "UPBGE_PATH": str(self.bin_dir)}
        return subprocess.run(
            [sys.executable, str(RUN_GAME), scenario + ".blend", *extra],
            cwd=self.tmp.name, env=env, text=True, capture_output=True, timeout=120,
        )

    def test_smoke_ok_exit0(self):
        done = self.run_runner("ok0", "--smoke")
        self.assertEqual(done.returncode, 0)
        self.assertIn('"ok": true', done.stdout)

    def test_smoke_report_ok_but_engine_exit3(self):
        done = self.run_runner("exit3", "--smoke")
        self.assertEqual(done.returncode, 1)
        self.assertIn("SMOKE FAIL: engine exited with code 3 (0x00000003)", done.stdout)

    def test_smoke_engine_crash(self):
        done = self.run_runner("crash", "--smoke")
        self.assertEqual(done.returncode, 1)
        self.assertIn(
            "SMOKE FAIL: engine exited with code %d (0x%08X)" % (CRASH_STATUS_POSIX, CRASH_STATUS_POSIX),
            done.stdout,
        )

    def test_smoke_engine_exit3_without_report_still_reports_the_crash(self):
        done = self.run_runner("exit3_noreport", "--smoke")
        self.assertEqual(done.returncode, 1)
        self.assertIn("SMOKE FAIL: engine exited with code 3 (0x00000003)", done.stdout)

    def test_smoke_report_not_ok(self):
        done = self.run_runner("notok", "--smoke")
        self.assertEqual(done.returncode, 1)
        self.assertIn('"ok": false', done.stdout)

    def test_smoke_malformed_json(self):
        done = self.run_runner("badjson", "--smoke")
        self.assertEqual(done.returncode, 2)
        self.assertIn("SMOKE FAIL: unreadable result", done.stdout)
        self.assertNotIn("Traceback", done.stderr)

    def test_smoke_no_report_file(self):
        done = self.run_runner("silent", "--smoke")
        self.assertEqual(done.returncode, 2)
        self.assertIn("SMOKE FAIL: no result file written", done.stdout)

    def test_plain_exit0(self):
        done = self.run_runner("ok0")
        self.assertEqual(done.returncode, 0)

    def test_plain_exit3_passthrough(self):
        done = self.run_runner("exit3")
        self.assertEqual(done.returncode, 3)
        self.assertIn("note: engine exited with code 3 (0x00000003)", done.stderr)

    def test_plain_crash_passthrough(self):
        done = self.run_runner("crash")
        self.assertEqual(done.returncode, CRASH_STATUS_POSIX)
        self.assertIn(
            "note: engine exited with code %d (0x%08X)" % (CRASH_STATUS_POSIX, CRASH_STATUS_POSIX),
            done.stderr,
        )


if __name__ == "__main__":
    unittest.main()
