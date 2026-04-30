"""
test_auto_rebuild.py - Tests for the orchestrator's drift dispatcher
(``tools/auto_rebuild.py``).

Per docs/22 Chunk D. Tier dispatch coverage:
    - T1 always auto (live metadata refresh against api-43-1)
    - T2 + flag unset -> warn-and-continue (no subprocess, no exception)
    - T2 + flag set -> subprocess + validator gate (mocked)
    - T3 near (distance <= threshold) + flag set -> same as T2 (mocked)
    - T3 distant (distance > threshold) -> prompt-pack + raise (mocked)
    - Validator gate Red -> rollback + raise (mocked rebuild + Red gate)

Run via:
    python -m unittest tests.test_auto_rebuild -v
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_TOOLS = _REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from auto_rebuild import (  # noqa: E402
    handle_drift, DriftHandlerError, _snapshot_profile, _delete_snapshot,
    _read_t3_threshold,
)
from rag_selector import RAGSelection, BumpClassification  # noqa: E402


def _make_selection(profile: str, mode: str, rebuild_required: bool = True,
                    epoch_distance=None) -> RAGSelection:
    return RAGSelection(
        mode=mode, profile_name=profile, milestone=None,
        user_api_epoch=None, milestone_api_epoch=None,
        epoch_distance=epoch_distance, rebuild_required=rebuild_required,
    )


# =============================================================================
# T1: live in-process refresh
# =============================================================================

@unittest.skipUnless(
    os.environ.get("A2MC_MODEL_PATH"),
    "A2MC_MODEL_PATH not set; skipping T1 live refresh",
)
class TestT1Refresh(unittest.TestCase):
    """T1 always runs regardless of flag. Live test against api-43-1."""

    def setUp(self):
        rag_dir = _REPO_ROOT / "rag"
        self.md_path = rag_dir / "metadata" / "api-43-1.json"
        self.graph_path = rag_dir / "graphs" / "api-43-1.json"
        self.tmpdir = Path(tempfile.mkdtemp(prefix="auto_rebuild_t1_"))
        if self.md_path.exists():
            shutil.copy2(self.md_path, self.tmpdir / "md.json")
        if self.graph_path.exists():
            shutil.copy2(self.graph_path, self.tmpdir / "graph.json")

    def tearDown(self):
        if (self.tmpdir / "md.json").exists():
            shutil.copy2(self.tmpdir / "md.json", self.md_path)
        if (self.tmpdir / "graph.json").exists():
            shutil.copy2(self.tmpdir / "graph.json", self.graph_path)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_t1_runs_without_flag(self):
        """T1 is always-auto. Flag unset -> still runs."""
        sel = _make_selection("api-43-1", "exact_epoch", rebuild_required=True)
        cls = BumpClassification(tier="T1", epoch_distance=0)
        msg = handle_drift(
            sel, cls,
            model_path=Path(os.environ["A2MC_MODEL_PATH"]),
            rag_dir=_REPO_ROOT / "rag",
            repo_root=_REPO_ROOT,
            auto_rebuild=False,
        )
        self.assertIn("T1 metadata refresh complete", msg)


# =============================================================================
# T2 + T3-near: flag-gated, mocked subprocess + gate
# =============================================================================

class TestFlagGatedTiers(unittest.TestCase):
    """T2 and T3-near both follow the same path. Flag must be set; otherwise
    warn-and-continue without invoking subprocess."""

    def _no_op_kwargs(self):
        return dict(
            model_path=Path("/fake/checkout"),
            rag_dir=_REPO_ROOT / "rag",
            repo_root=_REPO_ROOT,
        )

    def test_t2_flag_unset_warns_only(self):
        sel = _make_selection("api-43-1", "exact_epoch")
        cls = BumpClassification(tier="T2", epoch_distance=0)
        with patch("auto_rebuild._auto_rebuild_with_gate") as mock_rebuild:
            msg = handle_drift(sel, cls, auto_rebuild=False, **self._no_op_kwargs())
        mock_rebuild.assert_not_called()
        self.assertIn("A2MC_RAG_AUTO_REBUILD is not set", msg)

    def test_t3_near_flag_unset_warns_only(self):
        sel = _make_selection("api-43-1", "forward", epoch_distance=100)
        cls = BumpClassification(tier="T3", epoch_distance=100)
        with patch("auto_rebuild._auto_rebuild_with_gate") as mock_rebuild:
            msg = handle_drift(sel, cls, auto_rebuild=False, **self._no_op_kwargs())
        mock_rebuild.assert_not_called()
        self.assertIn("A2MC_RAG_AUTO_REBUILD is not set", msg)

    def test_t2_flag_set_invokes_rebuild_and_gate(self):
        sel = _make_selection("api-43-1", "exact_epoch")
        cls = BumpClassification(tier="T2", epoch_distance=0)
        with patch("auto_rebuild._auto_rebuild_with_gate",
                   return_value="[mocked rebuild Green]") as mock_rebuild:
            msg = handle_drift(sel, cls, auto_rebuild=True, **self._no_op_kwargs())
        mock_rebuild.assert_called_once()
        self.assertEqual(msg, "[mocked rebuild Green]")

    def test_t3_near_flag_set_invokes_rebuild_and_gate(self):
        sel = _make_selection("api-43-1", "forward", epoch_distance=100)
        cls = BumpClassification(tier="T3", epoch_distance=100)
        with patch("auto_rebuild._auto_rebuild_with_gate",
                   return_value="[mocked T3-near rebuild Green]") as mock_rebuild:
            msg = handle_drift(sel, cls, auto_rebuild=True, **self._no_op_kwargs())
        mock_rebuild.assert_called_once()
        self.assertEqual(msg, "[mocked T3-near rebuild Green]")


# =============================================================================
# T3 distant: never auto, always abort
# =============================================================================

class TestT3DistantAbort(unittest.TestCase):
    """T3 with epoch_distance > threshold raises regardless of flag."""

    def _kwargs(self):
        return dict(
            model_path=Path("/fake/checkout"),
            rag_dir=_REPO_ROOT / "rag",
            repo_root=_REPO_ROOT,
        )

    def test_t3_distant_with_flag_set_still_aborts(self):
        sel = _make_selection("api-43-1", "forward", epoch_distance=1201)
        cls = BumpClassification(tier="T3", epoch_distance=1201)
        # Patch the prompt-pack subprocess to a no-op success.
        with patch("auto_rebuild.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            with self.assertRaises(DriftHandlerError) as ctx:
                handle_drift(sel, cls, auto_rebuild=True, **self._kwargs())
        self.assertIn("exceeds auto threshold", str(ctx.exception))
        # Subprocess invoked with --mode prompt-pack
        cmd_args = mock_run.call_args[0][0]
        self.assertIn("--mode", cmd_args)
        self.assertEqual(cmd_args[cmd_args.index("--mode") + 1], "prompt-pack")

    def test_t3_distant_threshold_env_override(self):
        """Lowering threshold makes distance=100 distant too."""
        sel = _make_selection("api-43-1", "forward", epoch_distance=100)
        cls = BumpClassification(tier="T3", epoch_distance=100)
        with patch.dict(os.environ, {"A2MC_RAG_T3_AUTO_DISTANCE": "50"}):
            with patch("auto_rebuild.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                with self.assertRaises(DriftHandlerError) as ctx:
                    handle_drift(sel, cls, auto_rebuild=True, **self._kwargs())
        self.assertIn("exceeds auto threshold 50", str(ctx.exception))


# =============================================================================
# Validator gate Red -> rollback path
# =============================================================================

class TestValidatorGateRedTriggersRollback(unittest.TestCase):
    """When the rebuild subprocess succeeds but validators say Red, the
    handler must roll back from the snapshot and raise."""

    def setUp(self):
        # Fake rag_dir tree so snapshot/rollback have somewhere to go
        self.tmp = Path(tempfile.mkdtemp(prefix="rollback_test_"))
        for sub in ("chroma_db/api-43-1", "graphs", "metadata"):
            (self.tmp / sub).mkdir(parents=True, exist_ok=True)
        (self.tmp / "chroma_db" / "api-43-1" / "marker.txt").write_text("ORIGINAL")
        (self.tmp / "graphs" / "api-43-1.json").write_text('{"nodes": []}')
        (self.tmp / "metadata" / "api-43-1.json").write_text('{"version": 1}')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_red_verdict_rolls_back_to_snapshot(self):
        sel = _make_selection("api-43-1", "exact_epoch")
        cls = BumpClassification(tier="T2", epoch_distance=0)

        def fake_rebuild(profile, model_path, repo_root):
            # Simulate rebuild overwriting the chroma marker
            (self.tmp / "chroma_db" / profile / "marker.txt").write_text("BROKEN")

        with patch("auto_rebuild._run_rebuild_subprocess",
                   side_effect=fake_rebuild), \
             patch("auto_rebuild._run_validator_gate",
                   return_value={"verdict": "Red", "details": {}}):
            with self.assertRaises(DriftHandlerError) as ctx:
                handle_drift(
                    sel, cls,
                    model_path=Path("/fake"),
                    rag_dir=self.tmp,
                    repo_root=_REPO_ROOT,
                    auto_rebuild=True,
                )

        self.assertIn("validator gate", str(ctx.exception).lower())
        # Snapshot restored: marker is ORIGINAL again
        marker = self.tmp / "chroma_db" / "api-43-1" / "marker.txt"
        self.assertEqual(marker.read_text(), "ORIGINAL")
        # Failed dir exists for forensics
        failed_dirs = list((self.tmp / "chroma_db").glob("api-43-1.failed_*"))
        self.assertEqual(len(failed_dirs), 1)
        self.assertTrue((failed_dirs[0] / "marker.txt").read_text() == "BROKEN")


# =============================================================================
# Threshold env var
# =============================================================================

class TestThresholdEnvVar(unittest.TestCase):

    def test_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("A2MC_RAG_T3_AUTO_DISTANCE", None)
            self.assertEqual(_read_t3_threshold(), 100)

    def test_override(self):
        with patch.dict(os.environ, {"A2MC_RAG_T3_AUTO_DISTANCE": "250"}):
            self.assertEqual(_read_t3_threshold(), 250)

    def test_invalid_falls_back(self):
        with patch.dict(os.environ, {"A2MC_RAG_T3_AUTO_DISTANCE": "not_a_number"}):
            self.assertEqual(_read_t3_threshold(), 100)


# =============================================================================
# Snapshot + delete primitives
# =============================================================================

class TestSnapshotPrimitives(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="snapshot_test_"))
        for sub in ("chroma_db/api-43-1", "graphs", "metadata"):
            (self.tmp / sub).mkdir(parents=True, exist_ok=True)
        (self.tmp / "chroma_db" / "api-43-1" / "marker.txt").write_text("X")
        (self.tmp / "graphs" / "api-43-1.json").write_text("{}")
        (self.tmp / "metadata" / "api-43-1.json").write_text("{}")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_snapshot_creates_previous_siblings(self):
        paths = _snapshot_profile(self.tmp, "api-43-1")
        self.assertTrue(paths["chroma_dst"].is_dir())
        self.assertTrue((paths["chroma_dst"] / "marker.txt").exists())
        self.assertTrue(paths["graph_dst"].exists())
        self.assertTrue(paths["md_dst"].exists())

    def test_delete_snapshot_removes_previous(self):
        paths = _snapshot_profile(self.tmp, "api-43-1")
        _delete_snapshot(paths)
        self.assertFalse(paths["chroma_dst"].exists())
        self.assertFalse(paths["graph_dst"].exists())
        self.assertFalse(paths["md_dst"].exists())


if __name__ == "__main__":
    unittest.main()
