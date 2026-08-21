"""A skill that declares reciprocal skills must be named back by each of them.

WHY: `plotting` claimed ten skills applied its conventions; six never mentioned it.
A one-directional claim is invisible from the side that MATTERS — the skill that
should have loaded it — so figures got produced without `plotting` rule 8 (open the
rendered PNG and look at it) ever running.

Each named failure mode is exercised, not just the happy path. Adapter-kit's first
implementation made mode 2 UNREACHABLE by intersecting parsed tokens with the known
skill set — a check that cannot fail, inside a checker written to prevent exactly
that — and only per-mode testing found it.
"""
import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "_csr", REPO / "tools" / "check_skill_registry.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestSkillReciprocity(unittest.TestCase):
    def setUp(self):
        self.m = _mod()
        self.disk = self.m.skills_on_disk()

    def test_the_repo_currently_satisfies_the_invariant(self):
        self.assertEqual(self.m.reciprocity_check(self.disk), [])

    def test_mode1_declared_skill_does_not_name_the_declarer_back(self):
        d = dict(self.disk)
        d["phase0-design"] = d["phase0-design"].replace("`plotting`", "`plottingX`")
        self.assertTrue(any("never names" in p for p in self.m.reciprocity_check(d)))

    def test_mode2_declared_skill_does_not_exist(self):
        """Unreachable in the first upstream implementation — see module docstring."""
        d = dict(self.disk)
        d["plotting"] = d["plotting"].replace("`markdown-to-pdf`", "`no-such-skill`")
        self.assertTrue(any("not a skill" in p for p in self.m.reciprocity_check(d)))

    def test_mode3_no_skill_declares_reciprocity_at_all(self):
        """The anti-silent-pass guard.

        Without it, rewording the marker leaves the loop iterating over nothing and
        reporting success — the failure mode of any check keyed on a label another
        file writes.
        """
        d = {k: v.replace(self.m.RECIPROCAL_MARK, "**Related:**")
             for k, v in self.disk.items()}
        self.assertTrue(any("no skill declares" in p for p in self.m.reciprocity_check(d)))

    def test_plotting_is_reachable_from_every_skill_that_makes_figures(self):
        """The concrete regression: a figure-producing skill that never loads plotting."""
        for s in ("phase0-design", "phase3-diagnosis", "scientific-analysis",
                  "summarize-calibration-round", "compare-calibration-rounds"):
            with self.subTest(s):
                self.assertIn("`plotting`", self.disk[s],
                              f"{s} makes figures but never names plotting")


if __name__ == "__main__":
    unittest.main()
