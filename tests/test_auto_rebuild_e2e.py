"""
test_auto_rebuild_e2e.py - End-to-end integration tests for the orchestrator
auto-rebuild path.

Per docs/22 Chunk F. Drives the full call chain — `select_rag` →
`classify_bump_tier` → `handle_drift` — at the orchestrator's
`_check_rag_alignment()` granularity to verify Chunk D's wiring composes
correctly with Chunks A + B + C.

Heavy operations (T2 / T3 rebuild subprocesses, full wiki regen) are
mocked. The integration angle is "does the call chain reach the right
branch with the right args" — the per-component correctness is unit-
tested elsewhere (test_rag_selector, test_rag_refresh,
test_validator_gate, test_auto_rebuild).

Run via:
    python -m unittest tests.test_auto_rebuild_e2e -v
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_TOOLS = _REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from rag_selector import RAGSelection  # noqa: E402


def _orchestrator_module():
    """Import orchestrator.py fresh per test (so env-var changes take effect)."""
    if "orchestrator" in sys.modules:
        del sys.modules["orchestrator"]
    return importlib.import_module("orchestrator")


def _build_orchestrator(tmp_state_dir: Path):
    """Construct a minimal CalibrationOrchestrator for hook-only testing.

    State path is forced to a tmp file so the orchestrator's state-loader
    doesn't try to read the cwd as a state file (which fails outside of
    a real run).
    """
    orch_mod = _orchestrator_module()
    state_file = tmp_state_dir / "workflow_state.json"
    config = orch_mod.Config(
        use_memory=False,
        use_reasoning=False,
        max_iterations=1,
        output_dir=str(tmp_state_dir),
        state_file=str(state_file),
    )
    return orch_mod.CalibrationOrchestrator(config)


@unittest.skipUnless(
    os.environ.get("A2MC_MODEL_PATH"),
    "A2MC_MODEL_PATH not set; skipping e2e orchestrator hook",
)
class TestOrchestratorHookE2E(unittest.TestCase):
    """The fixtures exercise the call chain through `_check_rag_alignment`.

    Pattern: build the orchestrator OUTSIDE the patch context (happy path
    against live api-43-1; ctor's hook call is a no-op on no-drift). Then
    enter the patch context and call `orch._check_rag_alignment()`
    explicitly to exercise drift paths in isolation.
    """

    def setUp(self):
        self.tmp_state = Path(tempfile.mkdtemp(prefix="orch_e2e_"))
        # Ctor runs the hook against the live api-43-1 (no drift).
        self.orch = _build_orchestrator(self.tmp_state)

    def tearDown(self):
        shutil.rmtree(self.tmp_state, ignore_errors=True)

    def test_no_drift_happy_path(self):
        """Live api-43-1 checkout: rebuild_required=False, hook returns
        cleanly and sets A2MC_RAG_ACTIVE without invoking the drift handler."""
        with patch("auto_rebuild.handle_drift") as mock_handler:
            self.orch._check_rag_alignment()
        self.assertEqual(os.environ.get("A2MC_RAG_ACTIVE"), "api-43-1")
        mock_handler.assert_not_called()

    def test_t2_drift_with_flag_unset_returns_cleanly(self):
        """Synthetic T2 drift + flag unset: hook returns cleanly with
        warning, no exception, no rebuild subprocess."""
        synthetic = RAGSelection(
            mode="exact_epoch",
            profile_name="api-43-1",
            milestone=None,
            user_api_epoch="43.1",
            milestone_api_epoch="43.1",
            epoch_distance=0,
            rebuild_required=True,
        )
        with patch("rag_selector.select_rag", return_value=synthetic), \
             patch.dict(os.environ, {"A2MC_RAG_AUTO_REBUILD": "false"}), \
             patch("auto_rebuild._auto_rebuild_with_gate") as mock_rebuild:
            self.orch._check_rag_alignment()  # must not raise
        mock_rebuild.assert_not_called()

    def test_t3_distant_aborts_with_runtimeerror(self):
        """Synthetic T3-distant + flag set: orchestrator raises RuntimeError
        wrapping DriftHandlerError; subprocess invoked with --mode prompt-pack."""
        synthetic = RAGSelection(
            mode="forward",
            profile_name="api-43-1",
            milestone=None,
            user_api_epoch="55.0",
            milestone_api_epoch="43.1",
            epoch_distance=1200,  # well above the default 100 threshold
            rebuild_required=True,
        )
        # Replace auto_rebuild's `subprocess` reference rather than patching
        # the global `subprocess.run`, which would also intercept the git
        # calls inside model_version._detect_component.
        import auto_rebuild as auto_rebuild_mod
        fake_subprocess = MagicMock()
        fake_subprocess.run.return_value = MagicMock(returncode=0)
        with patch("rag_selector.select_rag", return_value=synthetic), \
             patch.dict(os.environ, {"A2MC_RAG_AUTO_REBUILD": "true"}), \
             patch.object(auto_rebuild_mod, "subprocess", fake_subprocess):
            with self.assertRaises(RuntimeError) as ctx:
                self.orch._check_rag_alignment()
        self.assertIn("[RAG alignment]", str(ctx.exception))
        self.assertIn("exceeds auto threshold", str(ctx.exception))
        self.assertTrue(fake_subprocess.run.called)
        cmd = fake_subprocess.run.call_args[0][0]
        self.assertIn("--mode", cmd)
        self.assertEqual(cmd[cmd.index("--mode") + 1], "prompt-pack")

    def test_t2_drift_with_flag_set_invokes_rebuild_path(self):
        """Synthetic T2 + flag set: orchestrator invokes auto-rebuild path.
        We mock the whole rebuild-with-gate to a Green return."""
        synthetic = RAGSelection(
            mode="exact_epoch",
            profile_name="api-43-1",
            milestone=None,
            user_api_epoch="43.1",
            milestone_api_epoch="43.1",
            epoch_distance=0,
            rebuild_required=True,
        )
        with patch("rag_selector.select_rag", return_value=synthetic), \
             patch.dict(os.environ, {"A2MC_RAG_AUTO_REBUILD": "true"}), \
             patch("auto_rebuild._auto_rebuild_with_gate",
                   return_value="[mocked Green]") as mock_rebuild:
            self.orch._check_rag_alignment()  # must not raise
        mock_rebuild.assert_called_once()

    def test_no_match_aborts_without_calling_handler(self):
        """sel.mode=='no_match' branch: orchestrator logs error and
        returns without invoking handle_drift (no basis to rebuild from)."""
        synthetic = RAGSelection(
            mode="no_match",
            profile_name=None,
            milestone=None,
            user_api_epoch="99.99",
            milestone_api_epoch=None,
            epoch_distance=None,
            rebuild_required=False,
        )
        with patch("rag_selector.select_rag", return_value=synthetic), \
             patch("auto_rebuild.handle_drift") as mock_handler:
            self.orch._check_rag_alignment()
        mock_handler.assert_not_called()


if __name__ == "__main__":
    unittest.main()
