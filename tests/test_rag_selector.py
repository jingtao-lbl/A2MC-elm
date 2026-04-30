"""
test_rag_selector.py - Unit tests for the RAG profile selector and bump classifier.

Per docs/22 Chunk A. Covers `classify_bump_tier()` returning a
`BumpClassification` with both tier ('T1' / 'T2' / 'T3') and
epoch distance.

Run via:
    python -m pytest tests/test_rag_selector.py -v

Or via the dedicated harness:
    python scripts/verify_mode_aware.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_TOOLS = _REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from rag_selector import (  # noqa: E402
    BumpClassification,
    RAGSelection,
    classify_bump_tier,
)


def _make_selection(mode: str, epoch_distance=None) -> RAGSelection:
    """Build a minimal RAGSelection for classifier tests.

    Only the fields read by `classify_bump_tier()` are populated; everything
    else is left at dataclass defaults. The classifier reads `mode` and
    `epoch_distance`.
    """
    return RAGSelection(
        mode=mode,
        profile_name=None,
        milestone=None,
        user_api_epoch=None,
        milestone_api_epoch=None,
        epoch_distance=epoch_distance,
    )


class TestClassifyBumpTier(unittest.TestCase):
    """Six fixtures spanning the three tiers and various distances."""

    def test_t1_exact_epoch_sha_matches(self):
        """exact_epoch + sha matches -> T1, distance 0."""
        sel = _make_selection("exact_epoch", epoch_distance=0)
        result = classify_bump_tier(sel, user_param_sha_matches=True)
        self.assertIsInstance(result, BumpClassification)
        self.assertEqual(result.tier, "T1")
        self.assertEqual(result.epoch_distance, 0)

    def test_t2_exact_epoch_sha_differs(self):
        """exact_epoch + sha differs -> T2, distance 0."""
        sel = _make_selection("exact_epoch", epoch_distance=0)
        result = classify_bump_tier(sel, user_param_sha_matches=False)
        self.assertEqual(result.tier, "T2")
        self.assertEqual(result.epoch_distance, 0)

    def test_t2_close_enough_within_epoch(self):
        """close_enough mode -> T2 (within-epoch drift)."""
        sel = _make_selection("close_enough", epoch_distance=0)
        result = classify_bump_tier(sel, user_param_sha_matches=False)
        self.assertEqual(result.tier, "T2")
        self.assertEqual(result.epoch_distance, 0)

    def test_t3_one_major_step(self):
        """forward / backward / no_match with distance 100 -> T3, distance 100.

        api-43-1 -> api-44-0 = (1*100 + 0) per `_epoch_distance` formula.
        Within the v2.98 auto-rebuild threshold (100).
        """
        sel = _make_selection("forward", epoch_distance=100)
        result = classify_bump_tier(sel, user_param_sha_matches=False)
        self.assertEqual(result.tier, "T3")
        self.assertEqual(result.epoch_distance, 100)

    def test_t3_distant_jump(self):
        """T3 with distance 1200 -> T3, distance preserved.

        api-31-0 -> api-43-1 = (12*100 + 1) per `_epoch_distance`.
        Above the v2.98 auto-rebuild threshold; orchestrator must abort
        and emit prompt-pack instead.
        """
        sel = _make_selection("forward", epoch_distance=1201)
        result = classify_bump_tier(sel, user_param_sha_matches=False)
        self.assertEqual(result.tier, "T3")
        self.assertEqual(result.epoch_distance, 1201)

    def test_t3_no_match_distance_unknown(self):
        """no_match with epoch_distance=None -> T3, distance defaults to 0.

        Selector failed to compute distance (e.g., epoch parsing failed).
        Classifier must not crash; returns 0 so orchestrator's threshold
        check defaults to "auto-rebuild" (caller may override).
        """
        sel = _make_selection("no_match", epoch_distance=None)
        result = classify_bump_tier(sel, user_param_sha_matches=False)
        self.assertEqual(result.tier, "T3")
        self.assertEqual(result.epoch_distance, 0)

    def test_to_dict_serialization(self):
        """BumpClassification.to_dict() is JSON-friendly for logging."""
        bc = BumpClassification(tier="T2", epoch_distance=0)
        self.assertEqual(bc.to_dict(), {"tier": "T2", "epoch_distance": 0})


if __name__ == "__main__":
    unittest.main()
