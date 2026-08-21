"""`remind-calibration-discipline.py` — did the offline state follow the work?

Ported from `adapter-kit` (handoff 20260819g). Silence is asserted at least as
hard as firing: this watches the MAIN working loop, so a hook that over-fires
gets muted and is then worth nothing.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "remind-calibration-discipline.py"


def run(path, root, **extra):
    p = {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": "x"}, **extra}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(p),
                          capture_output=True, text=True,
                          env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"})


class TestRemindCalibrationDiscipline(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(dir=REPO / "tmp"))
        (self.root / "tools").mkdir()
        # the validator imports this sibling; omitting it makes the validator CRASH,
        # which the hook then (correctly) treats as "our tool broke" and stays silent.
        for f in ("check_workflow_state_offline.py", "workflow_state_offline.py"):
            src = REPO / "tools" / f
            if src.is_file():
                shutil.copy(src, self.root / "tools")
        self.mem = self.root / "use_cases" / "ELM-FATES_Site" / "memory"
        (self.mem / "logs").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _state(self, updated_at, phase=None):
        """Built from the REAL state, so "valid" means what the validator means.

        A hand-invented minimal dict is not valid to `check_workflow_state_offline.py`,
        which made the silent-when-valid assertion fail for a fixture reason rather
        than a hook reason.
        """
        real = json.loads((REPO / "use_cases" / "ELM-FATES_Kougarok" / "memory"
                           / "workflow_state_offline_r01.json").read_text())
        real["updated_at"] = updated_at
        if phase is not None:
            real["phase"] = phase
        f = self.mem / "workflow_state_offline_r01.json"
        f.write_text(json.dumps(real))
        return f

    def _log(self, stem):
        f = self.mem / "logs" / stem
        f.write_text("x")
        return f

    def test_fires_when_work_is_newer_than_the_state(self):
        self._state("2026-08-10")
        r = run(self._log("20260819a_phase5_testing_r01.md"), self.root)
        self.assertTrue(r.stdout.strip(), "stale state produced no reminder")
        msg = json.loads(r.stdout)["hookSpecificOutput"]["systemMessage"]
        self.assertIn("20260819", msg)          # both dates named
        self.assertIn("2026-08-10", msg)
        self.assertIn("calibration-discipline", msg)

    def test_silent_when_the_state_kept_up(self):
        self._state("2026-08-20")
        self.assertEqual(run(self._log("20260819a_phase5_testing_r01.md"), self.root).stdout.strip(), "")

    def test_silent_on_a_BACKWARDS_phase_move(self):
        """The false positive this design exists to avoid.

        A Phase-6 -> Phase-0 redesign moves the phase BACKWARDS, so a phase6 log
        beside a `design` state is CORRECT. Comparing phase numbers would flag it;
        comparing timestamps does not.
        """
        self._state("2026-08-20", phase="design")
        self.assertEqual(run(self._log("20260819a_phase6_refinement_r01.md"), self.root).stdout.strip(), "")

    def test_silent_when_the_case_runs_no_offline_loop(self):
        self.assertEqual(run(self._log("20260819a_phase5_testing_r01.md"), self.root).stdout.strip(), "")

    def test_silent_on_a_repeat(self):
        self._state("2026-08-10")
        log = self._log("20260819a_phase5_testing_r01.md")
        self.assertTrue(run(log, self.root).stdout.strip())
        self.assertEqual(run(log, self.root).stdout.strip(), "", "re-emitted on an unchanged condition")

    def test_written_state_valid_is_silent_and_invalid_fires(self):
        good = self._state("2026-08-20")
        self.assertEqual(run(good, self.root).stdout.strip(), "")
        good.write_text("{ not valid json")
        out = run(good, self.root).stdout.strip()
        self.assertTrue(out, "invalid state produced no reminder")
        self.assertIn("INVALID", json.loads(out)["hookSpecificOutput"]["systemMessage"])

    def test_silent_when_the_validator_is_missing_or_the_write_failed(self):
        self._state("2026-08-10")
        log = self._log("20260819a_phase5_testing_r01.md")
        self.assertEqual(run(log, self.root, tool_response={"success": False}).stdout.strip(), "")
        (self.root / "tools" / "check_workflow_state_offline.py").unlink()
        self.assertEqual(run(self.mem / "workflow_state_offline_r01.json", self.root).stdout.strip(), "")

    def test_silent_when_the_VALIDATOR_ITSELF_CRASHES(self):
        """A crashed validator is not a failing check.

        Reporting "state invalid" over a Python traceback cries wolf about the
        user's data because OUR tool broke. Reproduced by removing the sibling
        module the validator imports — which is exactly how this surfaced.
        """
        self._state("2026-08-20")
        (self.root / "tools" / "workflow_state_offline.py").unlink(missing_ok=True)
        state = self.mem / "workflow_state_offline_r01.json"
        state.write_text("{ not valid json")
        self.assertEqual(run(state, self.root).stdout.strip(), "")

    def test_silent_on_unrelated_write_and_unparseable_payload(self):
        self._state("2026-08-10")
        self.assertEqual(run(self.root / "README.md", self.root).stdout.strip(), "")
        r = subprocess.run([sys.executable, str(HOOK)], input="not json",
                           capture_output=True, text=True,
                           env={"CLAUDE_PROJECT_DIR": str(self.root), "PATH": "/usr/bin:/bin"})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
