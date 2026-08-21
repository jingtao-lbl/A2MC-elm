"""`remind-setup-stage.py` — fires on a stage TRANSITION, silent otherwise.

Ported from `adapter-kit` (handoff 20260819f Part 2). A reminder has two ways
to be useless: never firing, and firing so often it gets muted. Both are tested.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "remind-setup-stage.py"


def run(payload, root):
    r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True,
                       env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"})
    return r


def write_payload(path):
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": "x"}}


class TestRemindSetupStage(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(dir=REPO / "tmp"))
        (self.root / "tools").mkdir()
        shutil.copy(REPO / "tools" / "check_setup_ready.py", self.root / "tools")
        (self.root / "use_cases" / "TEMPLATE").mkdir(parents=True)
        # a partially-built case: config present, everything else missing
        c = self.root / "use_cases" / "ELM-FATES_Site"
        (c / "config").mkdir(parents=True)
        (c / "config" / "elm-fates_site_config.sh").write_text("x")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_fires_on_a_boundary_write_naming_skill_and_specific_gaps(self):
        r = run(write_payload(str(self.root / "use_cases/ELM-FATES_Site/validation/targets.yaml")),
                self.root)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.strip(), "boundary write produced no reminder")
        msg = json.loads(r.stdout)["hookSpecificOutput"]["systemMessage"]
        self.assertIn("setup-discipline", msg)          # the definition of done
        self.assertIn("calibration_rounds.yaml", msg)   # a SPECIFIC gap, not a nudge
        self.assertIn("check_setup_ready.py", msg)      # the runnable audit

    def test_silent_on_a_repeat_of_the_same_call(self):
        """Transition, not state — a run of writes inside one stage stays quiet."""
        p = write_payload(str(self.root / "use_cases/ELM-FATES_Site/validation/targets.yaml"))
        first = run(p, self.root)
        self.assertTrue(first.stdout.strip())
        second = run(p, self.root)
        self.assertEqual(second.stdout.strip(), "", "re-emitted on an unchanged state")

    def test_silent_on_preview_and_unrelated_and_failed(self):
        cases = {
            "dry-run": {"tool_name": "Bash",
                        "tool_input": {"command": "bash scripts/setup_clone.sh --dry-run"}},
            "unrelated write": write_payload(str(self.root / "README.md")),
            "failed action": {**write_payload(
                str(self.root / "use_cases/ELM-FATES_Site/validation/targets.yaml")),
                "tool_response": {"success": False}},
        }
        for name, p in cases.items():
            with self.subTest(name):
                self.assertEqual(run(p, self.root).stdout.strip(), "")

    def test_silent_and_never_raises_when_the_gate_is_missing(self):
        d = Path(tempfile.mkdtemp(dir=REPO / "tmp"))
        try:
            r = run(write_payload(str(d / "use_cases/X/validation/targets.yaml")), d)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout.strip(), "")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_silent_on_an_unparseable_payload(self):
        r = subprocess.run([sys.executable, str(HOOK)], input="not json",
                           capture_output=True, text=True,
                           env={"CLAUDE_PROJECT_DIR": str(self.root), "PATH": "/usr/bin:/bin"})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
