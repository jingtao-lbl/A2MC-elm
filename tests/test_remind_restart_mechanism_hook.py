"""`remind-restart-mechanism` must fire on a hand-rolled restart and stay quiet otherwise.

The mistake it exists for (2026-08-20, reflection `20260820a_*`): restarting a
timed-out case by opening `xmlquery CONTINUE_RUN` and composing a plan by hand,
instead of `tools/restart_experiment_case.py`. This project resumes via
`finidat` + `RUN_STARTDATE` + `STOP_N`; `CONTINUE_RUN` is the generic-CIME
instinct and is wrong here.

The quiet cases matter as much as the firing ones. `CONTINUE_RUN` is NOT a safe
discriminator on its own: `tools/model_evolution/build_v0_case_via_clone.sh:114`
legitimately runs `./xmlchange CONTINUE_RUN=...` for a V0 continuation segment,
and a hook that cried wolf on every V0 check would be trained away.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOOK = REPO / ".claude" / "hooks" / "remind-restart-mechanism.py"


def run(cmd, tool_name="Bash"):
    """Return the hook's additionalContext, or '' if it stayed silent."""
    payload = {"tool_name": tool_name, "tool_input": {"command": cmd}}
    p = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                       capture_output=True, text=True)
    assert p.returncode == 0, f"hook exited {p.returncode}: {p.stderr}"
    if not p.stdout.strip():
        return ""
    return json.loads(p.stdout)["hookSpecificOutput"].get("additionalContext", "")


class TestFires(unittest.TestCase):
    def test_the_exact_mistake(self):
        """The command that started the 2026-08-20 correction."""
        self.assertIn("restart_experiment_case.py",
                      run("./xmlquery CONTINUE_RUN,STOP_N,RUN_STARTDATE,JOB_WALLCLOCK_TIME"))

    def test_xmlchange_continue_run(self):
        self.assertIn("NOT CONTINUE_RUN", run("./xmlchange CONTINUE_RUN=TRUE"))

    def test_handrolled_startdate_plus_finidat(self):
        """Composing the correct mechanism by hand instead of via the tool."""
        out = run("./xmlchange RUN_STARTDATE=0361-01-01 && "
                  "sed -i '/^finidat/d' user_nl_elm")
        self.assertIn("restart_experiment_case.py", out)

    def test_message_states_trans_exclusion(self):
        out = run("./xmlquery CONTINUE_RUN")
        self.assertIn("NEVER TRANS", out)


class TestQuiet(unittest.TestCase):
    def test_v0_continuation_is_legitimate(self):
        """build_v0_case_via_clone.sh really does set CONTINUE_RUN -- must not fire."""
        self.assertEqual("", run("bash tools/model_evolution/build_v0_case_via_clone.sh "
                                 "--continue-run 5 --case-dir foo"))

    def test_reading_docs_about_the_rule(self):
        """A read is not an act: grepping for CONTINUE_RUN must stay silent."""
        self.assertEqual("", run("git grep -n CONTINUE_RUN -- tools/"))
        self.assertEqual("", run("grep -rn 'CONTINUE_RUN' .claude/skills/"))

    def test_the_correct_tool(self):
        self.assertEqual("", run("python tools/restart_experiment_case.py "
                                 "--case-dir /path/to/case --execute"))

    def test_replaying_a_generated_restart_script(self):
        """A generated restart_*.sh doing the finidat edits IS the right mechanism."""
        self.assertEqual("", run("bash restart_RGnone_RGSP_20260820.sh"))

    def test_dry_run(self):
        self.assertEqual("", run("./xmlchange CONTINUE_RUN=TRUE --dry-run"))

    def test_unrelated_cime_use(self):
        self.assertEqual("", run("./xmlquery RUNDIR,CASEROOT"))

    def test_non_bash_tool(self):
        self.assertEqual("", run("./xmlquery CONTINUE_RUN", tool_name="Write"))

    def test_unparseable_payload_is_silent(self):
        p = subprocess.run([sys.executable, str(HOOK)], input="not json",
                           capture_output=True, text=True)
        self.assertEqual(0, p.returncode)
        self.assertEqual("", p.stdout.strip())


if __name__ == "__main__":
    unittest.main()
