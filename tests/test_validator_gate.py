"""
test_validator_gate.py - Smoke tests for the in-process validator gate
(`scripts/verify_mode_aware.py:run_all_validators`).

Per docs/22 Chunk C. Verifies the orchestrator's post-rebuild gate
returns the expected dict shape and a unified verdict that matches
what the CLI harness would produce for the same profile.

Run via:
    python -m unittest tests.test_validator_gate -v
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _import_harness():
    """Import scripts/verify_mode_aware.py by file path. Required because
    scripts/ is not a Python package."""
    spec = importlib.util.spec_from_file_location(
        "verify_mode_aware",
        _REPO_ROOT / "scripts" / "verify_mode_aware.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(
    os.environ.get("A2MC_MODEL_PATH"),
    "A2MC_MODEL_PATH not set; skipping live validator gate smoke",
)
class TestRunAllValidatorsLive(unittest.TestCase):
    """Live smoke against api-43-1. The current main branch should be
    Green; if not, the orchestrator gate would (correctly) reject any
    rebuild."""

    def test_returns_unified_dict_shape(self):
        harness = _import_harness()
        result = harness.run_all_validators(profile_name="api-43-1")

        # Top-level shape
        self.assertIn("verdict", result)
        self.assertIn(result["verdict"], ("Green", "Red"))
        self.assertIn("details", result)

        # All 6 layers present (include_smoke=True default)
        for layer in ("fixtures", "smoke", "tier4", "snapshot",
                      "completeness", "cross_milestone"):
            self.assertIn(layer, result["details"])

    def test_quick_mode_skips_smoke(self):
        """include_smoke=False omits fixtures + smoke layers (faster
        gate when only profile content needs checking)."""
        harness = _import_harness()
        result = harness.run_all_validators(
            profile_name="api-43-1", include_smoke=False
        )
        self.assertNotIn("fixtures", result["details"])
        self.assertNotIn("smoke", result["details"])
        # Per-profile validators still run
        self.assertIn("tier4", result["details"])
        self.assertIn("snapshot", result["details"])
        self.assertIn("completeness", result["details"])
        self.assertIn("cross_milestone", result["details"])

    def test_current_main_is_green(self):
        """Precondition for the orchestrator gate to be useful: main is
        currently expected to be Green. If this fails, fix that first
        before the auto-rebuild path lands."""
        harness = _import_harness()
        result = harness.run_all_validators(profile_name="api-43-1")
        self.assertEqual(
            result["verdict"], "Green",
            f"main is not Green; layer details: "
            f"{ {k: v.get('verdict', v) for k, v in result['details'].items()} }",
        )


if __name__ == "__main__":
    unittest.main()
