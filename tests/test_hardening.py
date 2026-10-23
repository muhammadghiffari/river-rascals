"""Guards for the first-setup hardening: pre-push hook behaviour and secret/bypass permission rules."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts" / "hooks" / "pre-push"
ZERO = "0" * 40
SHA = "1" * 40


class HookTests(unittest.TestCase):
    """Runs the hook with a stub `git-lfs` first on PATH, so only the hook's own logic is tested."""

    def setUp(self):
        self.sh = shutil.which("sh")
        if not self.sh:
            self.skipTest("no POSIX sh available")
        self.tmp = tempfile.TemporaryDirectory()
        self.capture = Path(self.tmp.name) / "lfs_stdin.txt"
        stub = Path(self.tmp.name) / "git-lfs"
        stub.write_text(f'#!/bin/sh\ncat > "{self.capture}"\nexit 0\n', encoding="utf-8")
        stub.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, remote_ref, remote_sha, extra_env=None):
        env = {**os.environ, "PATH": self.tmp.name + os.pathsep + os.environ["PATH"]}
        env.pop("RR_ALLOW_MAIN_PUSH", None)
        env.update(extra_env or {})
        line = f"refs/heads/x {SHA} {remote_ref} {remote_sha}\n"
        return subprocess.run([self.sh, str(HOOK), "origin", "url"], input=line, text=True,
                              capture_output=True, env=env), line

    def test_blocks_existing_main(self):
        r, _ = self.run_hook("refs/heads/main", SHA)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.capture.exists())  # LFS never reached on a blocked push

    def test_allows_first_creation_of_main(self):
        self.assertEqual(self.run_hook("refs/heads/main", ZERO)[0].returncode, 0)

    @unittest.skipIf(os.name == "nt", "no .exe stub for git-lfs on Windows; covered by Linux CI")
    def test_allows_feature_branch_and_forwards_input_to_lfs(self):
        r, line = self.run_hook("refs/heads/feat/x", SHA)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.capture.read_text(encoding="utf-8"), line)

    def test_human_override(self):
        r, _ = self.run_hook("refs/heads/main", SHA, {"RR_ALLOW_MAIN_PUSH": "1"})
        self.assertEqual(r.returncode, 0)


class LfsHookTests(unittest.TestCase):
    def test_lfs_hooks_present_and_bootstrap_skips_repo_hooks(self):
        for h in ("pre-push", "post-checkout", "post-commit", "post-merge"):
            self.assertIn("git lfs", (ROOT / "scripts" / "hooks" / h).read_text(encoding="utf-8"), h)
        boot = (ROOT / "scripts" / "bootstrap_github.py").read_text(encoding="utf-8")
        self.assertIn('"lfs", "install", "--skip-repo"', boot)


class PermissionTests(unittest.TestCase):
    def test_secret_dump_and_hook_bypass_rules(self):
        bash = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))["permission"]["bash"]
        self.assertEqual(bash["printenv*"], "ask")
        self.assertEqual(bash["env"], "ask")
        self.assertEqual(bash["git * --no-verify*"], "deny")


class EnvScriptTests(unittest.TestCase):
    def test_check_env_reports_git_identity(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_env.py")],
                           capture_output=True, text=True)
        self.assertIn("git config user.name", r.stdout)
        self.assertIn("git config user.email", r.stdout)


if __name__ == "__main__":
    unittest.main()
