"""Phase-6 data-reliability gate (v2.109, ported from demo dev_log 20260519a).

An experiment whose data is unreliable (silent extraction failure → phantom 0/N
reading) must NOT be auto-learned (it would poison memory with a bogus "this
parameter set fails" lesson), and a cycle in which EVERY experiment is unreliable
must be flagged so the orchestrator refuses to advance on phantom data.

Reliability is read from signals Phase 5 (monitor_experiments.py) already stamps:
extraction_status == 'extracted' AND no results['error'] AND non-empty results['metrics'].

Run: python -m unittest tests.test_phase6_reliability_gate -v
"""

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from phases.phase6_refinement import evaluate_experiments, all_experiments_unreliable


def _exp(name, extraction_status, results):
    return {"name": name, "case_name": name, "status": "completed",
            "extraction_status": extraction_status, "results": results}


class TestReliabilityGate(unittest.TestCase):
    def _outcomes(self, experiments):
        return evaluate_experiments(
            experiments, total_targets=6,
            reasoning_module=None, memory_manager=None, auto_learn=True,
        )["outcomes"]

    def test_reliable_experiment_not_skipped(self):
        o = self._outcomes([_exp("good", "extracted",
                                  {"targets_met": 3, "metrics": {"PFT10_leaf": 0.1}})])[0]
        self.assertTrue(o["data_reliable"])
        self.assertNotIn("skipped_auto_learn", o)

    def test_extraction_failure_is_unreliable(self):
        o = self._outcomes([_exp("bad", "extraction_failed", {"error": "boom"})])[0]
        self.assertFalse(o["data_reliable"])
        self.assertTrue(o["skipped_auto_learn"])

    def test_extracted_but_empty_metrics_is_unreliable(self):
        # phantom: status says extracted but no usable metrics → not reliable
        o = self._outcomes([_exp("phantom", "extracted",
                                  {"targets_met": 0, "metrics": {}})])[0]
        self.assertFalse(o["data_reliable"])
        self.assertTrue(o["skipped_auto_learn"])

    def test_all_unreliable_true_when_all_skipped(self):
        outcomes = self._outcomes([
            _exp("b1", "extraction_failed", {"error": "x"}),
            _exp("b2", "simulated_no_output", {"metrics": {}}),
        ])
        self.assertTrue(all_experiments_unreliable(outcomes))

    def test_all_unreliable_false_when_one_good(self):
        outcomes = self._outcomes([
            _exp("b1", "extraction_failed", {"error": "x"}),
            _exp("g1", "extracted", {"targets_met": 2, "metrics": {"a": 1}}),
        ])
        self.assertFalse(all_experiments_unreliable(outcomes))

    def test_empty_outcomes_not_unreliable(self):
        self.assertFalse(all_experiments_unreliable([]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
