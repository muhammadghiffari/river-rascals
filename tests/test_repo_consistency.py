"""Repo-level consistency checks: backlog vs bootstrap, prompt coverage, OpenCode permissions, check_env."""
import csv
import fnmatch
import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _flatten(perm):
    rules = []
    for key, val in perm.items():
        if isinstance(val, str):
            rules.append((key, "*", val))
        else:
            rules.extend((key, pat, act) for pat, act in val.items())
    return rules


def decide(cfg, agent, tool, arg="*"):
    """Emulates OpenCode: global rules then agent rules, last matching rule wins, default allow."""
    rules = _flatten(cfg["permission"]) + _flatten(cfg["agent"][agent].get("permission", {}))
    result = "allow"
    for perm, pat, act in rules:
        if fnmatch.fnmatchcase(tool, perm) and fnmatch.fnmatchcase(arg, pat):
            result = act
    return result


class BacklogTests(unittest.TestCase):
    def test_backlog_matches_bootstrap(self):
        bg = _load("scripts/bootstrap_github.py", "bg")
        items = json.loads((ROOT / "backlog/backlog.json").read_text(encoding="utf-8"))
        self.assertEqual(len(items), len({i["id"] for i in items}))
        self.assertEqual(len(items), len({i["title"] for i in items}))
        for it in items:
            self.assertIn(it["milestone"], bg.MILESTONES)
            for lb in [*it["labels"], f"owner:{it['owner']}"]:
                self.assertIn(lb, bg.LABELS, it["id"])

    def test_prompt_coverage(self):
        with open(ROOT / "docs/reference/ASSET_LIST.csv", encoding="utf-8") as f:
            assets = list(csv.DictReader(f))
        with open(ROOT / "docs/reference/AUDIO_LIST.csv", encoding="utf-8") as f:
            audio = list(csv.DictReader(f))
        ap = (ROOT / "prompts/asset_prompts_blender.md").read_text(encoding="utf-8")
        up = (ROOT / "prompts/audio_prompts.md").read_text(encoding="utf-8")
        self.assertEqual((len(assets), len(audio)), (83, 64))
        self.assertEqual([r["id"] for r in assets if r["id"] not in ap], [])
        self.assertEqual([r["id"] for r in audio if r["id"] not in up], [])


class OpenCodeConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))

    def test_agents_have_prompts_and_provider_model_ids(self):
        self.assertEqual(len(self.cfg["agent"]), 10)
        for name, a in self.cfg["agent"].items():
            self.assertRegex(a["model"], r"^[^/]+/.+")
            m = re.match(r"\{file:\./(.+)\}", a["prompt"])
            self.assertTrue(m and (ROOT / m.group(1)).exists(), name)
        self.assertNotIn("tools", self.cfg)  # deprecated; use permission

    def test_read_only_agents(self):
        for ag in ("reviewer", "security"):
            self.assertEqual(decide(self.cfg, ag, "edit"), "deny")
            self.assertEqual(decide(self.cfg, ag, "bash", "sed -i s/a/b/ f"), "deny")
            self.assertEqual(decide(self.cfg, ag, "bash", "git push origin feat/x"), "deny")
            self.assertEqual(decide(self.cfg, ag, "bash", "git diff HEAD"), "allow")

    def test_main_push_and_force_denied(self):
        for cmd in ("git push origin main", "git push --force origin x", "gh repo delete a/b"):
            self.assertEqual(decide(self.cfg, "builder", "bash", cmd), "deny", cmd)
        self.assertEqual(decide(self.cfg, "builder", "bash", "git push origin feat/main-menu"), "allow")

    def test_blender_mcp_only_for_techart(self):
        for ag in self.cfg["agent"]:
            want = "allow" if ag == "techart" else "deny"
            self.assertEqual(decide(self.cfg, ag, "blender_get_scene_info"), want, ag)
        self.assertEqual(self.cfg["mcp"]["blender"]["command"], ["uvx", "mcp-for-blender"])


class CheckEnvTests(unittest.TestCase):
    def test_nonzero_exit_is_not_ok(self):
        ce = _load("scripts/check_env.py", "ce")
        self.assertTrue(ce.ver([sys.executable, "-c", "import sys; sys.exit(1)"]).startswith("error"))
        self.assertIsNone(ce.ver(["definitely-not-a-real-command-xyz"]))
        self.assertTrue(ce.ver([sys.executable, "--version"]).startswith("Python"))

    def test_resolves_bare_name_through_path(self):
        # Windows npm shims are .cmd files; ver() must go through shutil.which to find them.
        ce = _load("scripts/check_env.py", "ce")
        name = "cmd" if sys.platform == "win32" else "sh"
        self.assertIsNotNone(ce.ver([name, "-c", "exit 0"]))


if __name__ == "__main__":
    unittest.main()
