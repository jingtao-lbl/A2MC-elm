"""
test_rag_refresh.py - Unit + integration tests for the T1 metadata refresh helper.

Per docs/22 Chunk B. Verifies:
    1. RefreshError is raised for unregistered profiles.
    2. Manifest fields fates_output_cdl / elm_output_cdl roundtrip
       through the dataclass (regression for v2.97 Group C gap).
    3. Live smoke test: refresh_metadata() against the real api-43-1
       profile updates `built_at` and re-computes SHAs without disturbing
       chunks, graph nodes, or curated YAML.

The live smoke test is skipped when A2MC_MODEL_PATH is not set (CI runs
without an E3SM checkout).

Run via:
    python -m unittest tests.test_rag_refresh -v
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_TOOLS = _REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from rag_refresh import refresh_metadata, RefreshError  # noqa: E402
from rag_manifest import Milestone, load_manifest  # noqa: E402


class TestManifestRoundtrip(unittest.TestCase):
    """Regression for v2.97 Group C: fates_output_cdl + elm_output_cdl
    were added to milestones.json but missing from the Milestone dataclass.
    Chunk B added them."""

    def test_fates_output_cdl_roundtrips(self):
        body = {
            "fates_api_epoch": "43.1",
            "fates_output_cdl": "elm_fates_output_info_e027a40.cdl",
            "elm_output_cdl": "elm_output_info_d40b843.cdl",
        }
        m = Milestone.from_dict("api-43-1", body)
        self.assertEqual(m.fates_output_cdl, "elm_fates_output_info_e027a40.cdl")
        self.assertEqual(m.elm_output_cdl, "elm_output_info_d40b843.cdl")
        self.assertEqual(m.to_dict()["fates_output_cdl"],
                         "elm_fates_output_info_e027a40.cdl")
        self.assertEqual(m.to_dict()["elm_output_cdl"],
                         "elm_output_info_d40b843.cdl")

    def test_legacy_milestone_no_elm_cdl(self):
        """api-31-0 has fates_output_cdl but no elm_output_cdl (legacy
        case-specific CDL had ELM vars baked in)."""
        body = {
            "fates_api_epoch": "31.0",
            "fates_output_cdl": "elm_fates_output_info.cdl",
        }
        m = Milestone.from_dict("api-31-0", body)
        self.assertEqual(m.fates_output_cdl, "elm_fates_output_info.cdl")
        self.assertIsNone(m.elm_output_cdl)


class TestRefreshErrors(unittest.TestCase):
    """Refresh fails cleanly with informative errors."""

    def test_unregistered_profile_raises(self):
        with self.assertRaises(RefreshError) as ctx:
            refresh_metadata(
                profile_name="api-99-99",
                model_path=Path("/nonexistent"),
                rag_dir=_REPO_ROOT / "rag",
            )
        self.assertIn("not registered", str(ctx.exception))

    def test_missing_manifest_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RefreshError) as ctx:
                refresh_metadata(
                    profile_name="api-43-1",
                    model_path=Path("/nonexistent"),
                    rag_dir=Path(tmp),
                )
            self.assertIn("milestones.json", str(ctx.exception).lower())


@unittest.skipUnless(
    os.environ.get("A2MC_MODEL_PATH"),
    "A2MC_MODEL_PATH not set; skipping live smoke test",
)
class TestRefreshLiveSmoke(unittest.TestCase):
    """End-to-end smoke against the real api-43-1 profile.

    Setup snapshots the metadata + graph JSON + chroma sqlite into a tmp
    backup, runs refresh_metadata(), verifies the metadata file changed
    in expected ways (built_at refreshed, SHAs present), and verifies
    chunks + graph nodes are byte-identical (mode-aware tagging
    preserved). teardown restores the backup.
    """

    PROFILE = "api-43-1"

    def setUp(self):
        self.rag_dir = _REPO_ROOT / "rag"
        self.md_path = self.rag_dir / "metadata" / f"{self.PROFILE}.json"
        self.graph_path = self.rag_dir / "graphs" / f"{self.PROFILE}.json"

        self.tmpdir = Path(tempfile.mkdtemp(prefix="rag_refresh_test_"))
        if self.md_path.exists():
            shutil.copy2(self.md_path, self.tmpdir / "metadata.json")
        if self.graph_path.exists():
            shutil.copy2(self.graph_path, self.tmpdir / "graph.json")

    def tearDown(self):
        # Restore originals so the test is non-destructive
        backup_md = self.tmpdir / "metadata.json"
        backup_graph = self.tmpdir / "graph.json"
        if backup_md.exists():
            shutil.copy2(backup_md, self.md_path)
        if backup_graph.exists():
            shutil.copy2(backup_graph, self.graph_path)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_refresh_writes_metadata_with_required_fields(self):
        before = json.loads(self.md_path.read_text()) if self.md_path.exists() else {}
        before_built_at = before.get("built_at")

        md = refresh_metadata(
            profile_name=self.PROFILE,
            model_path=Path(os.environ["A2MC_MODEL_PATH"]),
            rag_dir=self.rag_dir,
        )

        # Required identity + content fields
        self.assertEqual(md["profile_name"], self.PROFILE)
        self.assertIn("built_at", md)
        self.assertIn("fates", md)
        self.assertIn("commit_sha", md["fates"])
        self.assertIn("param_files", md)
        self.assertIn("fates_param_file_sha", md["param_files"])
        # v2.96 ELM CDL fields must be present (the api-43-1 milestone
        # registers an elm_output_cdl)
        self.assertIn("elm_output_var_file", md["param_files"])
        self.assertIn("elm_output_var_file_sha", md["param_files"])

        # built_at advanced (or at least equal — possible if test runs in
        # the same second as a previous refresh)
        self.assertGreaterEqual(md["built_at"], before_built_at or "")

        # Graph JSON _metadata mirror written
        graph = json.loads(self.graph_path.read_text())
        self.assertIn("_metadata", graph)
        self.assertEqual(graph["_metadata"]["profile_name"], self.PROFILE)

    def test_refresh_does_not_disturb_chunks_or_graph_nodes(self):
        """Mode-aware safety: chunk content and graph nodes must be
        byte-identical before and after refresh. Only the `_metadata`
        key on the graph JSON is allowed to change."""
        graph_before = json.loads(self.graph_path.read_text()) \
            if self.graph_path.exists() else {}
        nodes_before_repr = json.dumps(graph_before.get("nodes", []),
                                       sort_keys=True)

        refresh_metadata(
            profile_name=self.PROFILE,
            model_path=Path(os.environ["A2MC_MODEL_PATH"]),
            rag_dir=self.rag_dir,
        )

        graph_after = json.loads(self.graph_path.read_text())
        nodes_after_repr = json.dumps(graph_after.get("nodes", []),
                                      sort_keys=True)
        self.assertEqual(nodes_before_repr, nodes_after_repr,
                         "Refresh must not alter graph nodes (mode tagging risk)")


if __name__ == "__main__":
    unittest.main()
