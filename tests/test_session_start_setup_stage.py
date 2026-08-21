"""SessionStart names the setup stage — and stays silent once setup is done.

Ported from `adapter-kit` (handoff 20260819f Part 1). Three properties, each
its own test, because a reminder has two ways to be useless: never firing, and
firing when it should not.
"""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _hook():
    spec = importlib.util.spec_from_file_location(
        "_ss_hook", REPO / ".claude" / "hooks" / "session-start.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # safe: main() is guarded
    return m


class TestSetupStage(unittest.TestCase):
    def setUp(self):
        self.hook = _hook()
        self.tmp = Path(tempfile.mkdtemp(dir=REPO / "tmp"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _clone(self, *, configured):
        (self.tmp / "tools").mkdir()
        shutil.copy(REPO / "tools" / "check_setup_ready.py", self.tmp / "tools")
        (self.tmp / "use_cases").mkdir()
        (self.tmp / "use_cases" / "TEMPLATE").mkdir()
        if configured:
            (self.tmp / "a2mc_config.sh").write_text('export A2MC_MODEL_PATH="/x"\n')
            (self.tmp / "use_cases" / "ELM-FATES_Site").mkdir()
        return self.tmp

    def _run(self, root):
        lines = []
        self.hook.setup_stage(str(root), lines)
        return lines

    def test_fires_on_an_unconfigured_clone_and_names_the_skill(self):
        lines = self._run(self._clone(configured=False))
        self.assertTrue(lines, "stage-1 clone produced no reminder")
        msg = "\n".join(lines)
        self.assertIn("SETUP STAGE 1", msg)
        self.assertIn("a2mc-init", msg)          # the skill to start with
        self.assertIn("setup-discipline", msg)   # its definition of done
        self.assertIn("check_setup_ready.py", msg)  # the runnable audit

    def test_silent_once_configured(self):
        self.assertEqual(self._run(self._clone(configured=True)), [])

    def test_silent_when_config_is_merely_UNSOURCED(self):
        """The regression this port hit first.

        A hook runs with no site config sourced, so A2MC_MODEL_PATH is unset.
        Reading that as 'unconfigured' made the reminder fire on every session
        of an already-configured clone — the fastest way to train a reader to
        skip it. `_detect_stage` falls back to the DISK signal instead.
        """
        root = self._clone(configured=True)
        import os
        for var in ("A2MC_MODEL_PATH", "A2MC_USE_CASE_DIR", "A2MC_SITE_CONFIG"):
            os.environ.pop(var, None)
        self.assertEqual(self._run(root), [])

    def test_never_raises(self):
        """A hook that raises costs every session, not just the one it helps."""
        for build in ("no_tools", "empty"):
            with self.subTest(build):
                d = Path(tempfile.mkdtemp(dir=REPO / "tmp"))
                try:
                    if build == "no_tools":
                        (d / "use_cases").mkdir()
                    self.assertEqual(self._run(d), [])
                finally:
                    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
