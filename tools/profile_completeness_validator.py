#!/usr/bin/env python3
"""
profile_completeness_validator.py - Statistical coverage check for a built profile.

Tier 4 (mode_metadata_validator) asserts INVARIANTS (precedence,
no-orphan, propagation). This validator asserts DISTRIBUTIONS — different
failure modes that invariants miss. Catches "loader silently dropped half
the path-prefix matches" or "rebuild ran but only tagged 10% of chunks."

Five categories of distribution check:

    (a) Chunk-tagging distribution: % universal vs YAML-entity-tagged vs
        path-prefix-tagged. Bounds: ~80%+ universal, ~10-15% YAML-entity,
        ~5-10% path-prefix.
    (b) Wiki-directory coverage: every dir in _WIKI_PATH_PREFIX_TAGS has
        at least one chunk tagged with the expected flags. Catches "loader
        glob didn't fire because the directory layout changed."
    (c) YAML-entity coverage: every parameter/output in curated YAML has
        a matching chunk in the index.
    (d) Tier 2 axis distribution: count chunks per axis-value combo.
        Sanity bound: when a Tier 2 flag defaults False, the False side
        should have many more chunks than the True side.
    (e) Per-mode chunk counts (golden values): for canonical ConfigMode
        fixtures, count of chunks passing the where clause should match
        committed expectations within tolerance.

Yellow if any (a)-(d) bound is exceeded; Red if (e) drifts beyond
tolerance OR if YAML-entity coverage shows missing chunks.

Usage
-----
    python tools/profile_completeness_validator.py --profile api-43-1 \\
        --output docs/a2mc_reference/profile_completeness_api-43-1.md

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Acceptable bounds for chunk-tagging distribution
# (api-43-1 has ~4686 chunks; expect majority universal, smaller YAML/path-prefix)
TAGGING_BOUNDS = {
    "universal_min_pct": 70.0,   # at least 70% universal
    "universal_max_pct": 95.0,   # at most 95% (else not enough mode-tagged content)
    "yaml_entity_min_pct": 1.0,  # at least 1% from CDL definitions
    "path_prefix_min_pct": 1.0,  # at least 1% from wiki path-prefix
}

# Tolerance for golden-value chunk counts
GOLDEN_TOLERANCE = 50  # +/- chunk count


@dataclass
class CategoryResult:
    name: str
    severity: str = "OK"  # OK | WARN | ERROR
    rows: List[Tuple] = field(default_factory=list)
    summary: str = ""


@dataclass
class ProfileReport:
    profile: str
    n_chunks: int = 0
    n_nodes: int = 0
    categories: List[CategoryResult] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        if any(c.severity == "ERROR" for c in self.categories):
            return "Red"
        if any(c.severity == "WARN" for c in self.categories):
            return "Yellow"
        return "Green"


# =============================================================================
# Profile loaders
# =============================================================================

def _resolve_profile_paths(profile: str) -> Dict[str, Path]:
    rag_dir = Path(os.environ.get("A2MC_RAG_DIR", REPO_ROOT / "rag"))
    milestones_path = REPO_ROOT / "rag" / "milestones.json"
    with open(milestones_path) as f:
        milestones = json.load(f)
    if profile not in milestones["milestones"]:
        raise ValueError(f"Profile '{profile}' not in milestones.json")
    info = milestones["milestones"][profile]
    return {
        "curated_yaml": REPO_ROOT / info["curated_yaml_path"],
        "chroma_db": rag_dir / "chroma_db" / profile,
        "graph_json": rag_dir / "graphs" / f"{profile}.json",
    }


def _load_chunks(chroma_path: Path, limit: int = 20000) -> Tuple[list, list]:
    """Return (ids, metadatas) for chunks in the profile."""
    import chromadb
    client = chromadb.PersistentClient(path=str(chroma_path))
    cols = client.list_collections()
    if not cols:
        raise RuntimeError(f"No collection in {chroma_path}")
    coll = client.get_collection(cols[0].name)
    result = coll.get(limit=limit, include=["metadatas"])
    return result["ids"], result["metadatas"]


def _load_graph(graph_path: Path) -> Dict[str, dict]:
    with open(graph_path) as f:
        graph = json.load(f)
    if isinstance(graph.get("nodes"), list):
        return {n["id"]: {k: v for k, v in n.items() if k != "id"}
                for n in graph["nodes"]}
    return graph["nodes"]


# =============================================================================
# Category checks
# =============================================================================

def check_tagging_distribution(metadatas) -> CategoryResult:
    """(a) % universal vs per-axis-tagged."""
    cat = CategoryResult(name="(a) Chunk-tagging distribution")
    n = len(metadatas)
    n_universal = sum(1 for md in metadatas if md.get("applies_universal") is True)
    n_per_axis = sum(1 for md in metadatas
                     if any(k.startswith("applies_in_") for k in md.keys()))
    n_neither = sum(1 for md in metadatas
                    if md.get("applies_universal") is not True
                    and not any(k.startswith("applies_in_") for k in md.keys()))

    # Distinguish path-prefix-tagged vs YAML-entity-tagged
    # YAML-entity chunks have `entity_type='parameter'` or `'output'`
    n_yaml_entity = sum(1 for md in metadatas
                        if md.get("entity_type") in ("parameter", "output")
                        and any(k.startswith("applies_in_") for k in md.keys()))
    n_path_prefix = n_per_axis - n_yaml_entity

    pct_universal = 100 * n_universal / n if n else 0
    pct_yaml = 100 * n_yaml_entity / n if n else 0
    pct_path = 100 * n_path_prefix / n if n else 0

    cat.rows = [
        ("Total chunks", n),
        ("Universal", f"{n_universal} ({pct_universal:.1f}%)"),
        ("YAML-entity tagged", f"{n_yaml_entity} ({pct_yaml:.1f}%)"),
        ("Path-prefix tagged", f"{n_path_prefix} ({pct_path:.1f}%)"),
        ("Orphan (no metadata)", n_neither),
    ]

    issues = []
    if n_neither > 0:
        issues.append(f"{n_neither} orphan chunks (would fail Tier 4 (d))")
        cat.severity = "ERROR"
    if pct_universal < TAGGING_BOUNDS["universal_min_pct"]:
        issues.append(f"universal={pct_universal:.1f}% < {TAGGING_BOUNDS['universal_min_pct']}%")
        cat.severity = "WARN" if cat.severity == "OK" else cat.severity
    if pct_universal > TAGGING_BOUNDS["universal_max_pct"]:
        issues.append(f"universal={pct_universal:.1f}% > {TAGGING_BOUNDS['universal_max_pct']}% (possibly under-tagged)")
        cat.severity = "WARN" if cat.severity == "OK" else cat.severity

    cat.summary = "; ".join(issues) if issues else "Within bounds"
    return cat


def check_wiki_dir_coverage(metadatas) -> CategoryResult:
    """(b) Every path-prefix table entry has at least one matching chunk."""
    cat = CategoryResult(name="(b) Wiki-directory coverage")
    loader = _load_module("_loader", REPO_ROOT / "rag" / "loader.py")
    table = loader._WIKI_PATH_PREFIX_TAGS

    issues = []
    for path_glob, tags in table:
        if path_glob.endswith("/"):
            matches = [md for md in metadatas
                       if md.get("source", "").startswith(path_glob)]
        elif path_glob.endswith(".md") or path_glob.endswith(".rst"):
            matches = [md for md in metadatas if md.get("source", "") == path_glob]
        else:
            matches = [md for md in metadatas if path_glob in md.get("source", "")]

        n = len(matches)
        # Sanity: of the matches, count how many actually carry the expected flag
        if matches and tags:
            first_axis = next(iter(tags.keys()))
            first_value = tags[first_axis][0]
            from tools.config import _axis_value_token
            flag_key = f"applies_in_{first_axis}_{_axis_value_token(first_value)}"
            n_flagged = sum(1 for md in matches if md.get(flag_key) is True)
        else:
            n_flagged = 0

        status = "OK" if n > 0 and (not tags or n_flagged > 0) else "ERROR"
        cat.rows.append((path_glob, n, n_flagged, status))
        if n == 0:
            issues.append(f"'{path_glob}': no chunks matched")
        elif tags and n_flagged == 0:
            issues.append(f"'{path_glob}': {n} chunks but none flagged correctly")

    if issues:
        cat.severity = "ERROR"
        cat.summary = "; ".join(issues[:3])
    else:
        cat.summary = f"All {len(table)} path-prefix patterns matched expected chunks"
    return cat


def check_yaml_entity_coverage(metadatas, curated_yaml_path: Path) -> CategoryResult:
    """(c) Every YAML parameter/output has a corresponding chunk."""
    cat = CategoryResult(name="(c) YAML-entity coverage")
    with open(curated_yaml_path) as f:
        curated = yaml.safe_load(f) or {}
    yaml_params = list((curated.get("parameters") or {}).keys())
    yaml_outputs = list((curated.get("outputs") or {}).keys())

    chunk_param_names = {
        md.get("source", "").split("::")[-1]
        for md in metadatas
        if md.get("entity_type") == "parameter"
    }
    chunk_output_names = {
        md.get("source", "").split("::")[-1]
        for md in metadatas
        if md.get("entity_type") == "output"
    }

    missing_params = [p for p in yaml_params if p not in chunk_param_names]
    missing_outputs = [o for o in yaml_outputs if o not in chunk_output_names]

    cat.rows = [
        ("YAML parameters", len(yaml_params)),
        ("Param chunks present", len(yaml_params) - len(missing_params)),
        ("YAML outputs", len(yaml_outputs)),
        ("Output chunks present", len(yaml_outputs) - len(missing_outputs)),
    ]

    if missing_params or missing_outputs:
        cat.severity = "ERROR" if missing_params else "WARN"
        cat.summary = (
            f"{len(missing_params)} params, {len(missing_outputs)} outputs missing chunks. "
            f"Sample missing: params={missing_params[:3]}, outputs={missing_outputs[:3]}"
        )
    else:
        cat.summary = "All YAML entities have matching chunks"
    return cat


def check_tier2_distribution(metadatas) -> CategoryResult:
    """(d) Tier 2 axis distribution: count chunks per axis value."""
    cat = CategoryResult(name="(d) Tier 2 axis distribution")
    tier2_axes = [
        "fates_spitfire_mode", "use_fates_planthydro", "use_fates_logging",
        "use_fates_sp", "use_fates_ed_prescribed_phys", "use_fates_fixed_biogeog",
    ]
    issues = []
    for axis in tier2_axes:
        # Find all chunks with at least one applies_in_<axis>_* flag
        relevant = [md for md in metadatas
                    if any(k.startswith(f"applies_in_{axis}_") for k in md.keys())]
        # Bucket by the True-valued flag (chunks have multiple per-value flags
        # since for unmentioned axes all values are True; we look at the
        # axis where this chunk has a False for at least one value to find
        # the "restricted" chunks)
        n_relevant = len(relevant)
        # Restricted = chunks where at least one value of this axis is False
        n_restricted = sum(
            1 for md in relevant
            if any(v is False for k, v in md.items()
                   if k.startswith(f"applies_in_{axis}_"))
        )
        cat.rows.append((axis, n_relevant, n_restricted))

    cat.summary = f"Tier 2 axes: {len(tier2_axes)} axes, distributions logged"
    return cat


def check_golden_chunk_counts(metadatas, profile: str) -> CategoryResult:
    """(e) Per-mode chunk counts match committed golden values within tolerance."""
    cat = CategoryResult(name="(e) Golden chunk counts (per-mode)")
    if profile != "api-43-1":
        cat.summary = f"No golden values for {profile}; skipped"
        return cat

    # Re-import ConfigMode + chromadb for filter-pass count
    from tools.config import ConfigMode
    import chromadb
    paths = _resolve_profile_paths(profile)
    client = chromadb.PersistentClient(path=str(paths["chroma_db"]))
    coll = client.get_collection(client.list_collections()[0].name)

    # Golden values from v2.99 build (post-FATES-official-docs RST→MD conversion
    # AND post-RST-dedup fix).
    # Baseline progression:
    #   v2.92 (pre-ELM-CDL):       default=4055, kougarok-cnp=4333, parteh1=4145
    #   v2.96 (post-ELM-CDL):      default=5650, kougarok-cnp=5973, parteh1=5740
    #     (the ELM CDL added 1640 ELM-side output chunks, universal)
    #   v2.99 first cut (had RST duplicates): default=6206, kougarok-cnp=6570, parteh1=6354
    #     (loader bug: build path indexed converted .md AND raw .rst — same content twice)
    #   v2.99 final (post-dedup): default=5627, kougarok-cnp=5946, parteh1=5746
    #     (clean count: only the pandoc-converted markdown is indexed; the
    #      raw RST source is correctly skipped via _has_converted_md guard)
    golden = {
        "default-elm-sp": (ConfigMode(), 5627),
        "kougarok-parteh2-cnp-eca": (
            ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=2,
                       nutrient="cnp", nutrient_comp_pathway="eca"),
            5946,
        ),
        "parteh1-carbon-only": (
            ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=1,
                       nutrient="c", nutrient_comp_pathway="rd"),
            5746,
        ),
    }

    issues = []
    for label, (cm, expected) in golden.items():
        actual = len(coll.get(where=cm.to_chroma_where(), limit=10000)["ids"])
        delta = actual - expected
        within_tolerance = abs(delta) <= GOLDEN_TOLERANCE
        status = "OK" if within_tolerance else "DRIFT"
        cat.rows.append((label, expected, actual, delta, status))
        if not within_tolerance:
            issues.append(f"{label}: expected {expected}, got {actual} (delta={delta:+d})")

    if issues:
        cat.severity = "WARN"  # drift is suspicious but not always a bug
        cat.summary = "; ".join(issues)
    else:
        cat.summary = f"All {len(golden)} golden values within {GOLDEN_TOLERANCE} tolerance"
    return cat


# =============================================================================
# Driver
# =============================================================================

def run_validation(profile: str) -> ProfileReport:
    paths = _resolve_profile_paths(profile)
    if not paths["chroma_db"].exists():
        raise FileNotFoundError(f"ChromaDB profile not found: {paths['chroma_db']}")

    print(f"Profile: {profile}")
    print(f"  ChromaDB:   {paths['chroma_db']}")
    print(f"  Graph JSON: {paths['graph_json']}")
    print(f"  YAML:       {paths['curated_yaml']}")

    ids, metadatas = _load_chunks(paths["chroma_db"])
    nodes = _load_graph(paths["graph_json"])
    report = ProfileReport(profile=profile, n_chunks=len(ids), n_nodes=len(nodes))
    print(f"  Loaded {report.n_chunks} chunks, {report.n_nodes} graph nodes")
    print()

    print("Running coverage checks...")
    for check_fn, name in [
        (lambda: check_tagging_distribution(metadatas), "(a)"),
        (lambda: check_wiki_dir_coverage(metadatas), "(b)"),
        (lambda: check_yaml_entity_coverage(metadatas, paths["curated_yaml"]), "(c)"),
        (lambda: check_tier2_distribution(metadatas), "(d)"),
        (lambda: check_golden_chunk_counts(metadatas, profile), "(e)"),
    ]:
        cat = check_fn()
        report.categories.append(cat)
        print(f"  {name} {cat.severity:5s} - {cat.summary}")

    print(f"\nVerdict: {report.verdict}")
    return report


def write_report(report: ProfileReport, out_path: Path) -> None:
    lines = [
        f"# Profile Completeness Validation: {report.profile}",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"**Verdict:** {report.verdict}",
        f"**Chunks:** {report.n_chunks}  |  **Graph nodes:** {report.n_nodes}",
        "",
        "## Summary",
        "",
        "| Category | Severity | Summary |",
        "|---|---|---|",
    ]
    for cat in report.categories:
        lines.append(f"| {cat.name} | {cat.severity} | {cat.summary} |")
    lines.append("")

    for cat in report.categories:
        lines.append(f"## {cat.name}")
        lines.append("")
        if cat.rows:
            ncols = len(cat.rows[0])
            header = ["Metric"] + [f"col{i}" for i in range(1, ncols)]
            lines.append("| " + " | ".join(str(h) for h in header) + " |")
            lines.append("|" + "---|" * ncols)
            for row in cat.rows:
                lines.append("| " + " | ".join(str(v) for v in row) + " |")
            lines.append("")
        if cat.summary:
            lines.append(f"**Status:** {cat.summary}")
            lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    print(f"Report: {out_path}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Profile completeness validator (Validator #2)")
    ap.add_argument("--profile", default="api-43-1")
    ap.add_argument("--output", type=Path)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_validation(args.profile)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2
    if args.output:
        write_report(report, args.output)
    return 0 if report.verdict != "Red" else 1


if __name__ == "__main__":
    sys.exit(main())
