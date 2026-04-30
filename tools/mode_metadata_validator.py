#!/usr/bin/env python3
"""
mode_metadata_validator.py - Tier 4 of the RAG validation triangle.

Validates that the chain from curated YAML `applies_in:` blocks to ChromaDB
chunk metadata to NetworkX graph node attrs is intact. This is the layer
that catches silent breakage between the schema (validated by Tier 2 yaml
validator), the build process, and the retrieved data.

Five assertion classes:

    (a) YAML-entity propagation: every YAML entry with `applies_in:` has
        matching `applies_in_*` flags on its corresponding chunk(s) and
        graph node.
    (b) Path-prefix propagation: every wiki chunk whose source matches a
        loader path-prefix entry carries the table's expected flags.
    (c) Precedence invariant: NO chunk or graph node has both
        `applies_universal: True` AND any `applies_in_*` flag.
    (d) No-orphan invariant: every chunk and graph node has either
        `applies_universal: True` OR per-axis flags.
    (e) Graph-chunk consistency: where a YAML entity has a chunk AND a
        graph node, their applies_in_* flags agree.

Read-only on inputs; only writes a Markdown report (and exits non-zero on
ERROR rows for CI integration).

Usage
-----
    python tools/mode_metadata_validator.py \\
        --profile api-43-1 \\
        --output docs/a2mc_reference/mode_metadata_validation_api-43-1.md

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


# Repo-relative imports without triggering rag/__init__.py side effects
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Lazy load to avoid pulling chromadb / networkx at module import time
_cfg = _load_module("_cfg", REPO_ROOT / "tools" / "config.py")
ALL_AXIS_VALUES = _cfg.ALL_AXIS_VALUES
build_applies_in_flags = _cfg.build_applies_in_flags
_axis_value_token = _cfg._axis_value_token


@dataclass
class AssertionResult:
    """One assertion outcome for the report."""
    severity: str  # "OK" | "WARN" | "ERROR"
    category: str  # one of (a)-(e) above
    target: str    # entity name or chunk id
    message: str


@dataclass
class ValidatorReport:
    rows: List[AssertionResult] = field(default_factory=list)

    def ok(self, category: str, target: str, msg: str = ""):
        self.rows.append(AssertionResult("OK", category, target, msg))

    def warn(self, category: str, target: str, msg: str):
        self.rows.append(AssertionResult("WARN", category, target, msg))

    def error(self, category: str, target: str, msg: str):
        self.rows.append(AssertionResult("ERROR", category, target, msg))

    @property
    def n_ok(self) -> int:
        return sum(1 for r in self.rows if r.severity == "OK")

    @property
    def n_warn(self) -> int:
        return sum(1 for r in self.rows if r.severity == "WARN")

    @property
    def n_error(self) -> int:
        return sum(1 for r in self.rows if r.severity == "ERROR")

    @property
    def verdict(self) -> str:
        if self.n_error:
            return "Red"
        if self.n_warn:
            return "Yellow"
        return "Green"


# =============================================================================
# Profile resolution
# =============================================================================

def resolve_profile_paths(profile: str, rag_dir: Optional[Path] = None) -> Dict[str, Path]:
    """Resolve the file paths for a given milestone profile.

    Reads ``rag/milestones.json`` to find the profile's curated YAML, then
    derives chroma_db / graph paths under ``$A2MC_RAG_DIR`` (or the repo's
    ``rag/`` if unset).
    """
    rag_dir = rag_dir or (REPO_ROOT / "rag")
    milestones_path = REPO_ROOT / "rag" / "milestones.json"
    with open(milestones_path) as f:
        milestones = json.load(f)
    if profile not in milestones["milestones"]:
        raise ValueError(
            f"Profile '{profile}' not in {milestones_path}; "
            f"available: {list(milestones['milestones'])}"
        )
    info = milestones["milestones"][profile]
    return {
        "profile": profile,
        "curated_yaml": REPO_ROOT / info["curated_yaml_path"],
        "chroma_db": rag_dir / "chroma_db" / profile,
        "graph_json": rag_dir / "graphs" / f"{profile}.json",
        "metadata_json": rag_dir / "metadata" / f"{profile}.json",
        "fates_wiki": REPO_ROOT / "docs" / "fates-knowledge-base" / info["fates_wiki_subdir"],
    }


# =============================================================================
# Assertion suite
# =============================================================================

def assert_yaml_entity_propagation(
    curated: dict, coll, graph: dict, report: ValidatorReport
) -> None:
    """(a) Every YAML entity with applies_in: has matching chunk + graph flags."""
    parameters = curated.get("parameters") or {}
    mechanisms = curated.get("mechanisms") or {}
    outputs = curated.get("outputs") or {}

    # Parameters: chunk = `param_def::<name>`; graph node = `parameter:<name>`
    for name, entry in parameters.items():
        applies_in = (entry or {}).get("applies_in")
        if applies_in is None:
            continue  # universal entries checked separately
        expected = build_applies_in_flags(applies_in)

        # Chunk metadata
        chunk_id = f"param_def::{name}"
        chunk = coll.get(ids=[chunk_id], include=["metadatas"])
        if not chunk["ids"]:
            report.warn("(a)YAML-chunk", chunk_id,
                        f"YAML entity tagged but no chunk found")
        else:
            md = chunk["metadatas"][0]
            mismatches = _compare_flags(expected, md)
            if mismatches:
                report.error("(a)YAML-chunk", chunk_id,
                             f"chunk metadata mismatch: {mismatches[:3]}")
            else:
                report.ok("(a)YAML-chunk", chunk_id, "flags match YAML")

        # Graph node
        node_id = f"parameter:{name}"
        if node_id in graph["nodes"]:
            node_attrs = graph["nodes"][node_id]
            mismatches = _compare_flags(expected, node_attrs)
            if mismatches:
                report.error("(a)YAML-graph", node_id,
                             f"graph node attrs mismatch: {mismatches[:3]}")
            else:
                report.ok("(a)YAML-graph", node_id, "node attrs match YAML")
        else:
            report.warn("(a)YAML-graph", node_id, "graph node not found")

    # Mechanisms: graph node only (mechanisms have no per-name chunks in CDL)
    for name, entry in mechanisms.items():
        applies_in = (entry or {}).get("applies_in")
        if applies_in is None:
            continue
        expected = build_applies_in_flags(applies_in)
        node_id = f"mechanism:{name}"
        if node_id in graph["nodes"]:
            node_attrs = graph["nodes"][node_id]
            mismatches = _compare_flags(expected, node_attrs)
            if mismatches:
                report.error("(a)YAML-graph", node_id,
                             f"mechanism node attrs mismatch: {mismatches[:3]}")
            else:
                report.ok("(a)YAML-graph", node_id, "mechanism node attrs match YAML")
        else:
            report.warn("(a)YAML-graph", node_id, "mechanism node not found")

    # Outputs (mode-tagged outputs in YAML; chunk = `output_def::<name>`)
    for name, entry in outputs.items():
        applies_in = (entry or {}).get("applies_in")
        if applies_in is None:
            continue
        expected = build_applies_in_flags(applies_in)
        chunk_id = f"output_def::{name}"
        chunk = coll.get(ids=[chunk_id], include=["metadatas"])
        if not chunk["ids"]:
            continue  # auto-extracted-only, no chunk to check
        md = chunk["metadatas"][0]
        mismatches = _compare_flags(expected, md)
        if mismatches:
            report.error("(a)YAML-chunk", chunk_id,
                         f"output chunk metadata mismatch: {mismatches[:3]}")
        else:
            report.ok("(a)YAML-chunk", chunk_id, "output flags match YAML")


def assert_path_prefix_propagation(coll, report: ValidatorReport) -> None:
    """(b) Every wiki chunk whose source matches a path-prefix has expected flags."""
    # Lazy load loader to access the table
    loader = _load_module("_loader", REPO_ROOT / "rag" / "loader.py")
    table = loader._WIKI_PATH_PREFIX_TAGS
    path_prefix_tags = loader.path_prefix_tags

    # Sample a few chunks per pattern (we don't need to check ALL chunks)
    SAMPLES_PER_PATTERN = 2
    for path_glob, expected_block in table:
        expected_flags = build_applies_in_flags(expected_block)
        # Find chunks whose source matches this pattern
        # We use a coarse 'source' substring match. Chunks may not exist for
        # all patterns (e.g. dirs with no .md files); skip warn-only.
        try:
            if path_glob.endswith("/"):
                # Directory prefix: pull a sample, filter by source startswith
                all_chunks = coll.get(limit=20000, include=["metadatas"])
                matching = [
                    (cid, md) for cid, md in zip(
                        all_chunks["ids"], all_chunks["metadatas"]
                    )
                    if md.get("source", "").startswith(path_glob)
                ][:SAMPLES_PER_PATTERN]
            elif path_glob.endswith(".md") or path_glob.endswith(".rst"):
                # Specific file
                result = coll.get(
                    where={"source": path_glob},
                    include=["metadatas"], limit=SAMPLES_PER_PATTERN,
                )
                matching = list(zip(result["ids"], result["metadatas"]))
            else:
                # Filename prefix substring; use limit and filter
                all_chunks = coll.get(limit=20000, include=["metadatas"])
                matching = [
                    (cid, md) for cid, md in zip(
                        all_chunks["ids"], all_chunks["metadatas"]
                    )
                    if path_glob in md.get("source", "")
                ][:SAMPLES_PER_PATTERN]
        except Exception as e:
            report.warn("(b)PathPrefix", path_glob, f"query error: {e}")
            continue

        if not matching:
            report.warn("(b)PathPrefix", path_glob,
                        f"no chunks matched pattern (table entry may be obsolete)")
            continue

        for cid, md in matching:
            mismatches = _compare_flags(expected_flags, md)
            if mismatches:
                report.error("(b)PathPrefix", cid,
                             f"path-prefix '{path_glob}' chunk mismatch: {mismatches[:3]}")
            else:
                report.ok("(b)PathPrefix", cid,
                          f"matches pattern '{path_glob}'")


def assert_precedence_invariant(coll, graph: dict, report: ValidatorReport) -> None:
    """(c) NO chunk or node has both applies_universal=True AND any applies_in_* flag."""
    # Sample chunks
    sample = coll.get(limit=5000, include=["metadatas"])
    violations = 0
    for cid, md in zip(sample["ids"], sample["metadatas"]):
        is_universal = md.get("applies_universal") is True
        has_per_axis = any(k.startswith("applies_in_") for k in md.keys())
        if is_universal and has_per_axis:
            violations += 1
            if violations <= 5:
                report.error("(c)Precedence", cid,
                             "chunk has BOTH applies_universal=True AND applies_in_* flags")
    if violations == 0:
        report.ok("(c)Precedence", "<sample>",
                  f"no precedence violations across {len(sample['ids'])} chunks")
    elif violations > 5:
        report.error("(c)Precedence", "<sample>",
                     f"+{violations - 5} additional violations not shown")

    # Graph nodes
    g_violations = 0
    for nid, attrs in graph["nodes"].items():
        is_universal = attrs.get("applies_universal") is True
        has_per_axis = any(k.startswith("applies_in_") for k in attrs.keys())
        if is_universal and has_per_axis:
            g_violations += 1
            if g_violations <= 5:
                report.error("(c)Precedence-graph", nid,
                             "graph node has BOTH applies_universal AND applies_in_*")
    if g_violations == 0:
        report.ok("(c)Precedence-graph", "<all>",
                  f"no precedence violations across {len(graph['nodes'])} nodes")


def assert_no_orphan_invariant(coll, graph: dict, report: ValidatorReport) -> None:
    """(d) Every chunk and graph node has either applies_universal=True OR per-axis flags."""
    sample = coll.get(limit=5000, include=["metadatas"])
    orphans = 0
    for cid, md in zip(sample["ids"], sample["metadatas"]):
        is_universal = md.get("applies_universal") is True
        has_per_axis = any(k.startswith("applies_in_") for k in md.keys())
        if not is_universal and not has_per_axis:
            orphans += 1
            if orphans <= 5:
                report.error("(d)NoOrphan", cid, "chunk has no mode metadata")
    if orphans == 0:
        report.ok("(d)NoOrphan", "<sample>",
                  f"no orphan chunks across {len(sample['ids'])} sampled")
    elif orphans > 5:
        report.error("(d)NoOrphan", "<sample>",
                     f"+{orphans - 5} additional orphan chunks not shown")

    # Graph nodes
    g_orphans = 0
    for nid, attrs in graph["nodes"].items():
        is_universal = attrs.get("applies_universal") is True
        has_per_axis = any(k.startswith("applies_in_") for k in attrs.keys())
        if not is_universal and not has_per_axis:
            g_orphans += 1
            if g_orphans <= 5:
                report.error("(d)NoOrphan-graph", nid, "graph node has no mode metadata")
    if g_orphans == 0:
        report.ok("(d)NoOrphan-graph", "<all>",
                  f"no orphan nodes across {len(graph['nodes'])} graph nodes")


def assert_graph_chunk_consistency(
    curated: dict, coll, graph: dict, report: ValidatorReport
) -> None:
    """(e) For YAML entities with both chunk + graph node, flags agree."""
    parameters = curated.get("parameters") or {}
    for name, entry in parameters.items():
        applies_in = (entry or {}).get("applies_in")
        if applies_in is None:
            continue
        chunk_id = f"param_def::{name}"
        node_id = f"parameter:{name}"
        chunk = coll.get(ids=[chunk_id], include=["metadatas"])
        if not chunk["ids"] or node_id not in graph["nodes"]:
            continue
        chunk_md = chunk["metadatas"][0]
        node_attrs = graph["nodes"][node_id]
        # Compare per-axis flags
        per_axis_keys = [k for k in chunk_md if k.startswith("applies_in_")]
        diffs = []
        for k in per_axis_keys:
            if chunk_md.get(k) != node_attrs.get(k):
                diffs.append((k, chunk_md.get(k), node_attrs.get(k)))
        if diffs:
            report.error("(e)Graph-Chunk", name,
                         f"flag disagreement: {diffs[:3]}")
        else:
            report.ok("(e)Graph-Chunk", name, "flags agree")


def _compare_flags(expected: Dict[str, bool], actual: Dict) -> List[Tuple[str, bool, object]]:
    """Return list of (flag_name, expected_value, actual_value) for mismatches."""
    diffs = []
    for k, v_exp in expected.items():
        v_act = actual.get(k)
        if v_act != v_exp:
            diffs.append((k, v_exp, v_act))
    return diffs


# =============================================================================
# Driver
# =============================================================================

def run_validation(profile: str, rag_dir: Optional[Path] = None) -> ValidatorReport:
    """Run the full Tier 4 assertion suite against a built profile."""
    paths = resolve_profile_paths(profile, rag_dir)

    if not paths["chroma_db"].exists():
        raise FileNotFoundError(f"ChromaDB profile not found: {paths['chroma_db']}")
    if not paths["graph_json"].exists():
        raise FileNotFoundError(f"Graph JSON not found: {paths['graph_json']}")
    if not paths["curated_yaml"].exists():
        raise FileNotFoundError(f"Curated YAML not found: {paths['curated_yaml']}")

    print(f"Profile: {profile}")
    print(f"  Curated YAML: {paths['curated_yaml']}")
    print(f"  ChromaDB:     {paths['chroma_db']}")
    print(f"  Graph JSON:   {paths['graph_json']}")

    # Load curated YAML
    with open(paths["curated_yaml"]) as f:
        curated = yaml.safe_load(f)

    # Load graph (NetworkX node-link JSON)
    with open(paths["graph_json"]) as f:
        graph_raw = json.load(f)
    # Normalize to {nodes: {id: attrs}}
    if isinstance(graph_raw.get("nodes"), list):
        graph = {"nodes": {n["id"]: {k: v for k, v in n.items() if k != "id"}
                            for n in graph_raw["nodes"]}}
    else:
        graph = graph_raw

    # Open ChromaDB collection
    import chromadb
    client = chromadb.PersistentClient(path=str(paths["chroma_db"]))
    # Find the collection (we use 'fates_knowledge' by convention)
    collections = client.list_collections()
    if not collections:
        raise RuntimeError(f"No collections in {paths['chroma_db']}")
    coll = client.get_collection(collections[0].name)

    print(f"\nValidation suite running against {coll.count()} chunks, {len(graph['nodes'])} nodes...")

    report = ValidatorReport()

    print("  (a) YAML-entity propagation...")
    assert_yaml_entity_propagation(curated, coll, graph, report)

    print("  (b) Path-prefix propagation...")
    assert_path_prefix_propagation(coll, report)

    print("  (c) Precedence invariant...")
    assert_precedence_invariant(coll, graph, report)

    print("  (d) No-orphan invariant...")
    assert_no_orphan_invariant(coll, graph, report)

    print("  (e) Graph-chunk consistency...")
    assert_graph_chunk_consistency(curated, coll, graph, report)

    print(f"\nResults: {report.n_ok} OK, {report.n_warn} WARN, {report.n_error} ERROR")
    print(f"Verdict: {report.verdict}")

    return report


def write_report(report: ValidatorReport, out_path: Path, profile: str) -> None:
    out: List[str] = [
        f"# Mode-Metadata Validation: {profile} (Tier 4)",
        "",
        f"**Generated:** {datetime.utcnow().isoformat(timespec='seconds')}Z",
        "",
        f"**Profile:** `{profile}`",
        f"**Verdict:** {report.verdict}",
        "",
        f"- OK: {report.n_ok}",
        f"- WARN: {report.n_warn}",
        f"- ERROR: {report.n_error}",
        "",
        "---",
        "",
    ]

    # Group rows by category
    cats = {}
    for r in report.rows:
        cats.setdefault(r.category, []).append(r)

    for cat in sorted(cats):
        rows = cats[cat]
        n_err = sum(1 for r in rows if r.severity == "ERROR")
        n_warn = sum(1 for r in rows if r.severity == "WARN")
        n_ok = sum(1 for r in rows if r.severity == "OK")
        out.append(f"## {cat} ({n_ok} OK, {n_warn} WARN, {n_err} ERROR)")
        out.append("")
        # Show errors and warnings in detail; OK rows summarized
        for r in rows:
            if r.severity != "OK":
                out.append(f"- **[{r.severity}]** `{r.target}` — {r.message}")
        if n_ok and not (n_err or n_warn):
            out.append(f"All {n_ok} assertions pass.")
        out.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out))
    print(f"Report written: {out_path}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Tier 4 mode-metadata validator")
    ap.add_argument("--profile", default="api-43-1",
                    help="Milestone profile to validate (default: api-43-1)")
    ap.add_argument("--rag-dir", type=Path, default=None,
                    help="Override RAG directory (default: $A2MC_RAG_DIR or repo/rag)")
    ap.add_argument("--output", type=Path,
                    help="Path for Markdown report (default: stdout-only)")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_validation(args.profile, args.rag_dir)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2

    if args.output:
        write_report(report, args.output, args.profile)
    else:
        # Always summarize errors/warnings to stderr for CI
        for r in report.rows:
            if r.severity != "OK":
                print(f"[{r.severity}] {r.category} {r.target}: {r.message}",
                      file=sys.stderr)

    return 0 if report.n_error == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
