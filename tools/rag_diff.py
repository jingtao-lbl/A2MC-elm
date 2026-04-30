#!/usr/bin/env python3
"""
rag_diff.py - Compare two A2MC RAG/GraphRAG profiles and emit a Markdown diff report.

Compares four dimensions (v0.1 scope, retrieval semantics deferred):
    1. Parameter inventory (graph parameter nodes)
    2. Graph structure (node/edge counts by type)
    3. Wiki content (file-level adds/removes/diffs with Jaccard similarity)
    4. Parameter file structure (names, defaults, dimensions)

Read-only on inputs; only writes the output Markdown report.

Usage
-----
    python tools/rag_diff.py \
        --profile-a-graph Offline/rag_scratch/api-31-0/graph.json \
        --profile-a-wiki  docs/fates-knowledge-base/fates-codebase-wiki-e85d997 \
        --profile-a-param docs/fates-knowledge-base/fates_params_info.cdl \
        --profile-a-name  api-31-0 \
        --profile-b-graph rag/fates_knowledge_graph.json \
        --profile-b-wiki  docs/fates-knowledge-base/fates-codebase-wiki-e027a40 \
        --profile-b-param docs/fates-knowledge-base/fates_params_info_e027a40.json \
        --profile-b-name  api-43-1 \
        --output docs/a2mc_reference/rag_diff_api-31-0_vs_api-43-1.md

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# A2MC import: parameter parser handles .cdl, .json, .nc
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from rag.parameter_parser import FATESParameterParser
except ImportError as e:
    print(f"ERROR: cannot import FATESParameterParser ({e}). Run from A2MC repo root.",
          file=sys.stderr)
    sys.exit(1)


# =============================================================================
# Data classes
# =============================================================================

@dataclass
class Profile:
    name: str
    graph_path: Path
    wiki_root: Path
    param_path: Path


# =============================================================================
# Graph loading
# =============================================================================

def load_graph(path: Path) -> dict:
    """Load NetworkX node-link JSON graph."""
    with open(path) as f:
        return json.load(f)


def node_type_of(node: dict) -> str:
    """Resolve node_type, falling back to ID prefix if missing."""
    nt = node.get("node_type") or node.get("type")
    if nt:
        return nt
    nid = node.get("id", "")
    if ":" in nid:
        prefix = nid.split(":", 1)[0]
        return prefix.capitalize()
    return "?"


def edge_type_of(edge: dict) -> str:
    """Resolve edge relation type."""
    return edge.get("relation_type") or edge.get("type") or "?"


def parameter_nodes(graph: dict) -> Dict[str, dict]:
    """Return mapping of parameter name -> node for nodes typed Parameter."""
    out = {}
    for n in graph.get("nodes", []):
        nt = node_type_of(n)
        nid = n.get("id", "")
        is_param = nt == "Parameter" or nid.startswith("parameter:")
        if is_param:
            name = n.get("name") or nid.split(":", 1)[-1]
            out[name] = n
    return out


# =============================================================================
# Dimension 1: parameter inventory diff
# =============================================================================

def find_renames(only_a: List[str], only_b: List[str],
                 threshold: float = 0.7) -> List[Tuple[str, str, float]]:
    """
    Match each name in only_a to its best partner in only_b (and vice versa).
    Only flag pairs where the match is mutually best AND similarity >= threshold.
    """
    if not only_a or not only_b:
        return []

    def best_match(name: str, candidates: List[str]) -> Tuple[Optional[str], float]:
        best, best_score = None, 0.0
        for c in candidates:
            s = SequenceMatcher(None, name, c).ratio()
            if s > best_score:
                best, best_score = c, s
        return best, best_score

    a_to_b = {a: best_match(a, only_b) for a in only_a}
    b_to_a = {b: best_match(b, only_a) for b in only_b}

    renames = []
    for a, (b_match, score_a) in a_to_b.items():
        if b_match is None or score_a < threshold:
            continue
        # mutual best?
        b_partner, score_b = b_to_a.get(b_match, (None, 0.0))
        if b_partner == a and score_b >= threshold:
            renames.append((a, b_match, round(score_a, 3)))
    # de-dup (mutual pairs)
    return sorted(set(renames), key=lambda x: -x[2])


def diff_parameter_inventory(graph_a: dict, graph_b: dict) -> dict:
    pa = parameter_nodes(graph_a)
    pb = parameter_nodes(graph_b)

    set_a = set(pa.keys())
    set_b = set(pb.keys())

    only_a = sorted(set_a - set_b)
    only_b = sorted(set_b - set_a)
    common = sorted(set_a & set_b)

    renames = find_renames(only_a, only_b, threshold=0.7)

    # Drop renamed pairs from "only" lists for cleaner reporting
    renamed_a = {r[0] for r in renames}
    renamed_b = {r[1] for r in renames}
    only_a_pure = [x for x in only_a if x not in renamed_a]
    only_b_pure = [x for x in only_b if x not in renamed_b]

    return {
        "count_a": len(set_a),
        "count_b": len(set_b),
        "added": only_b_pure,  # in B not A
        "removed": only_a_pure,
        "renamed": renames,
        "common": common,
        "nodes_a": pa,
        "nodes_b": pb,
    }


# =============================================================================
# Dimension 2: graph structure diff
# =============================================================================

def diff_graph_structure(graph_a: dict, graph_b: dict) -> dict:
    nodes_a = graph_a.get("nodes", [])
    nodes_b = graph_b.get("nodes", [])
    edges_a = graph_a.get("links", graph_a.get("edges", []))
    edges_b = graph_b.get("links", graph_b.get("edges", []))

    # Counts
    nt_a = Counter(node_type_of(n) for n in nodes_a)
    nt_b = Counter(node_type_of(n) for n in nodes_b)
    et_a = Counter(edge_type_of(e) for e in edges_a)
    et_b = Counter(edge_type_of(e) for e in edges_b)

    # Untyped fraction caveat
    untyped_a = nt_a.get("?", 0)
    untyped_b = nt_b.get("?", 0)

    # Per-type added/removed nodes (by id)
    by_type_a: Dict[str, Set[str]] = defaultdict(set)
    by_type_b: Dict[str, Set[str]] = defaultdict(set)
    for n in nodes_a:
        by_type_a[node_type_of(n)].add(n.get("id", ""))
    for n in nodes_b:
        by_type_b[node_type_of(n)].add(n.get("id", ""))

    node_changes = {}
    for t in sorted(set(by_type_a) | set(by_type_b)):
        added = by_type_b.get(t, set()) - by_type_a.get(t, set())
        removed = by_type_a.get(t, set()) - by_type_b.get(t, set())
        node_changes[t] = {"added": len(added), "removed": len(removed)}

    # Per-type added/removed edges (by source-relation-target triple)
    def edge_key(e):
        return (e.get("source"), edge_type_of(e), e.get("target"))

    set_ea = {edge_key(e) for e in edges_a}
    set_eb = {edge_key(e) for e in edges_b}
    edges_added_by_type = Counter()
    edges_removed_by_type = Counter()
    for k in set_eb - set_ea:
        edges_added_by_type[k[1]] += 1
    for k in set_ea - set_eb:
        edges_removed_by_type[k[1]] += 1

    return {
        "node_total_a": len(nodes_a),
        "node_total_b": len(nodes_b),
        "edge_total_a": len(edges_a),
        "edge_total_b": len(edges_b),
        "node_types_a": nt_a,
        "node_types_b": nt_b,
        "edge_types_a": et_a,
        "edge_types_b": et_b,
        "untyped_a": untyped_a,
        "untyped_b": untyped_b,
        "node_changes_per_type": node_changes,
        "edges_added_by_type": edges_added_by_type,
        "edges_removed_by_type": edges_removed_by_type,
    }


# =============================================================================
# Dimension 3: wiki content diff
# =============================================================================

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> Set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text)}


def jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def collect_wiki_files(root: Path) -> Dict[str, Path]:
    """Walk wiki directory and return {relpath: abspath} for .md files."""
    out = {}
    if not root.exists():
        return out
    for p in root.rglob("*.md"):
        rel = str(p.relative_to(root))
        out[rel] = p
    return out


def safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def diff_wiki(profile_a: Profile, profile_b: Profile) -> dict:
    files_a = collect_wiki_files(profile_a.wiki_root)
    files_b = collect_wiki_files(profile_b.wiki_root)

    rels_a = set(files_a)
    rels_b = set(files_b)
    only_a = sorted(rels_a - rels_b)
    only_b = sorted(rels_b - rels_a)
    both = sorted(rels_a & rels_b)

    # Renames among only_a / only_b (path similarity)
    rename_pairs = find_renames(only_a, only_b, threshold=0.6)

    # For files in both: compare jaccard + line counts
    in_both_metrics = []
    jaccards = []
    for rel in both:
        text_a = safe_read_text(files_a[rel])
        text_b = safe_read_text(files_b[rel])
        toks_a = tokenize(text_a)
        toks_b = tokenize(text_b)
        j = jaccard(toks_a, toks_b)
        lines_a = text_a.count("\n") + (1 if text_a and not text_a.endswith("\n") else 0)
        lines_b = text_b.count("\n") + (1 if text_b and not text_b.endswith("\n") else 0)
        in_both_metrics.append({
            "path": rel,
            "lines_a": lines_a,
            "lines_b": lines_b,
            "jaccard": round(j, 3),
        })
        jaccards.append(j)

    avg_jaccard = sum(jaccards) / len(jaccards) if jaccards else 0.0

    # Line counts for added/removed files
    only_a_info = []
    for rel in only_a:
        text = safe_read_text(files_a[rel])
        lines = text.count("\n")
        only_a_info.append({"path": rel, "lines": lines})
    only_b_info = []
    for rel in only_b:
        text = safe_read_text(files_b[rel])
        lines = text.count("\n")
        only_b_info.append({"path": rel, "lines": lines})

    return {
        "count_a": len(files_a),
        "count_b": len(files_b),
        "only_a": only_a_info,
        "only_b": only_b_info,
        "in_both": in_both_metrics,
        "renames": rename_pairs,
        "avg_jaccard": round(avg_jaccard, 3),
    }


def jaccard_verdict(j: float) -> str:
    if j < 0.5:
        return "Major rewrite"
    if j < 0.85:
        return "Minor edit"
    return "Cosmetic"


# =============================================================================
# Dimension 4: parameter file structure diff
# =============================================================================

def parse_param_file(path: Path) -> Tuple[Dict[str, "FATESParameter"], str]:  # noqa: F821
    parser = FATESParameterParser(str(path))
    return parser.parse(), parser.format


def _default_repr(val) -> str:
    """Compact representation of a default value for table display."""
    if val is None:
        return ""
    try:
        # Numpy array-like
        if hasattr(val, "tolist"):
            v = val.tolist()
        else:
            v = val
        s = repr(v)
        if len(s) > 60:
            s = s[:57] + "..."
        return s
    except Exception:
        return str(val)[:60]


def _values_equal(a, b) -> bool:
    """Loose equality check for default values across formats."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        import numpy as np
        arr_a = np.asarray(a)
        arr_b = np.asarray(b)
        if arr_a.shape != arr_b.shape:
            return False
        if arr_a.dtype.kind in "fc" or arr_b.dtype.kind in "fc":
            return bool(np.allclose(arr_a, arr_b, equal_nan=True))
        return bool((arr_a == arr_b).all())
    except Exception:
        return repr(a) == repr(b)


def diff_param_files(profile_a: Profile, profile_b: Profile) -> dict:
    pa, fmt_a = parse_param_file(profile_a.param_path)
    pb, fmt_b = parse_param_file(profile_b.param_path)

    set_a = set(pa)
    set_b = set(pb)
    added = sorted(set_b - set_a)
    removed = sorted(set_a - set_b)
    common = sorted(set_a & set_b)

    changed_default = []
    changed_dims = []
    for name in common:
        a_p = pa[name]
        b_p = pb[name]
        if not _values_equal(a_p.default_values, b_p.default_values):
            changed_default.append({
                "name": name,
                "a": _default_repr(a_p.default_values),
                "b": _default_repr(b_p.default_values),
            })
        if list(a_p.dimensions) != list(b_p.dimensions):
            changed_dims.append({
                "name": name,
                "a": ", ".join(a_p.dimensions) or "(scalar)",
                "b": ", ".join(b_p.dimensions) or "(scalar)",
            })

    return {
        "format_a": fmt_a,
        "format_b": fmt_b,
        "count_a": len(pa),
        "count_b": len(pb),
        "added": [{"name": n, "default": _default_repr(pb[n].default_values),
                   "dims": ", ".join(pb[n].dimensions) or "(scalar)",
                   "units": pb[n].units} for n in added],
        "removed": [{"name": n, "default": _default_repr(pa[n].default_values)} for n in removed],
        "changed_default": changed_default,
        "changed_dims": changed_dims,
    }


# =============================================================================
# Sanity verdict
# =============================================================================

_API_VERSION_RE = re.compile(r"api[-_.]?(\d+)[-_.]?(\d+)?", re.IGNORECASE)


def parse_api_version(name: str) -> Optional[Tuple[int, int]]:
    """Extract (major, minor) from a profile name like 'api-43-1' or 'api.31.0'."""
    m = _API_VERSION_RE.search(name)
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2)) if m.group(2) else 0
    return (major, minor)


def scale_thresholds(name_a: str, name_b: str) -> Tuple[Dict[str, int], int]:
    """Scale Yellow/Red thresholds based on API version distance.

    Returns ({added_y, added_r, removed_y, removed_r, renamed_y}, api_distance).
    Default thresholds (api_distance <= 1) match the original plan §4.9.
    Multi-major bumps relax 'removed' and 'renamed' bands proportionally.
    """
    base = {"added_y": 50, "added_r": 100, "removed_y": 5,
            "removed_r": 100, "renamed_y": 5}
    va = parse_api_version(name_a)
    vb = parse_api_version(name_b)
    if not (va and vb):
        return base, 0
    api_distance = abs(va[0] - vb[0])
    if api_distance <= 1:
        return base, api_distance
    # Scale: each major bump roughly +5 'removed' and +5 'renamed' headroom.
    # Reflects empirical observation that api.31->api.43 (12 majors) drops
    # ~14 params from real source-side renames, with no quality concern.
    scaled = dict(base)
    scaled["removed_y"] = base["removed_y"] + 5 * api_distance
    scaled["renamed_y"] = base["renamed_y"] + 5 * api_distance
    return scaled, api_distance


def detect_bulk_node_additions(graph_struct: Optional[dict],
                               threshold: int = 500) -> List[str]:
    """Detect node-type deltas large enough to suggest a structural rebuild
    (e.g., the v2.96 ELM-output extraction added ~1640 Output nodes to api-43-1).

    Returns a list of context notes — these are *informational*, not verdict
    escalations. They steer the reader toward checking metadata
    (elm_output_var_file_sha, fates_param_file_sha) before treating a large
    add as drift.
    """
    if not graph_struct:
        return []
    notes = []
    for t, ch in sorted(graph_struct.get("node_changes_per_type", {}).items()):
        added = ch.get("added", 0)
        if added >= threshold:
            hint = (f"{added} '{t}' nodes added in B. This is large enough "
                    f"to suggest a structural rebuild rather than an upstream "
                    f"source change.")
            if t.lower() == "output":
                hint += (" If diffing across the v2.96 boundary, check "
                         "`param_files.elm_output_var_file` in both profile "
                         "metadata — v2.96+ ingests an ELM-side output CDL "
                         "(~1640 fields) that older builds lack.")
            notes.append(hint)
    return notes


def sanity_verdict(param_inv: dict, wiki: dict,
                   profile_a_name: str = "",
                   profile_b_name: str = "",
                   graph_struct: Optional[dict] = None) -> Tuple[str, List[str]]:
    """Return (verdict, notes) per plan thresholds, scaled by API distance."""
    added = len(param_inv["added"])
    removed = len(param_inv["removed"])
    renamed = len(param_inv["renamed"])
    avg_j = wiki["avg_jaccard"]

    # Fraction of files with near-zero similarity (< 0.1)
    near_zero = sum(1 for f in wiki["in_both"] if f["jaccard"] < 0.1)
    near_zero_frac = near_zero / len(wiki["in_both"]) if wiki["in_both"] else 0.0

    th, api_distance = scale_thresholds(profile_a_name, profile_b_name)
    verdict = "Green"
    notes = []

    if added > th["added_r"] or removed > th["removed_r"] or near_zero_frac > 0.5:
        verdict = "Red"
    elif added > th["added_y"] or removed > th["removed_y"] \
            or renamed > th["renamed_y"] or avg_j <= 0.5:
        verdict = "Yellow"

    if api_distance >= 2:
        notes.append(
            f"Profile names indicate {api_distance}-major API distance; "
            f"thresholds scaled (Yellow at >{th['removed_y']} removed, "
            f">{th['renamed_y']} renamed)."
        )
    if added > th["added_y"]:
        notes.append(f"{added} parameters added (threshold {th['added_y']} for Yellow, {th['added_r']} for Red).")
    if removed > th["removed_y"]:
        notes.append(f"{removed} parameters removed (threshold {th['removed_y']} for Yellow, {th['removed_r']} for Red).")
    if renamed > th["renamed_y"]:
        notes.append(f"{renamed} likely renames (threshold {th['renamed_y']} for Yellow).")
    if avg_j <= 0.5:
        notes.append(f"Wiki avg Jaccard {avg_j:.2f} is at or below 0.5 (Yellow threshold).")
    if near_zero_frac > 0.5:
        notes.append(
            f"{near_zero_frac*100:.0f}% of shared wiki files have near-zero similarity "
            f"(Red threshold > 50%); regen may have broken alignment."
        )

    # Bulk-node-add context (e.g., v2.96 ELM-output extraction). Informational only.
    notes.extend(detect_bulk_node_additions(graph_struct))

    if verdict == "Green" and not any("nodes added in B" in n for n in notes):
        notes.append("All thresholds within Green band; safe to proceed.")

    return verdict, notes


# =============================================================================
# Markdown rendering
# =============================================================================

def md_table(headers: List[str], rows: List[List[str]]) -> str:
    if not rows:
        return "_(none)_\n"
    out = "| " + " | ".join(headers) + " |\n"
    out += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for r in rows:
        out += "| " + " | ".join(str(c) for c in r) + " |\n"
    return out


def render_report(profile_a: Profile, profile_b: Profile,
                  param_inv: dict, graph_struct: dict,
                  wiki: dict, param_files: dict,
                  verdict: str, verdict_notes: List[str]) -> str:
    ts = datetime.now().isoformat(timespec="seconds")

    out = []
    out.append(f"# RAG Comparison: {profile_a.name} vs {profile_b.name}\n")
    out.append(f"**Generated:** {ts}\n")
    out.append(f"**Profile A:** {profile_a.name}")
    out.append(f"- Graph: `{profile_a.graph_path}`")
    out.append(f"- Wiki: `{profile_a.wiki_root}`")
    out.append(f"- Parameter file: `{profile_a.param_path}`\n")
    out.append(f"**Profile B:** {profile_b.name}")
    out.append(f"- Graph: `{profile_b.graph_path}`")
    out.append(f"- Wiki: `{profile_b.wiki_root}`")
    out.append(f"- Parameter file: `{profile_b.param_path}`\n")
    out.append("---\n")

    # Sanity assessment
    out.append("## Sanity assessment\n")
    out.append("Per `docs/18_ELM_FATES_Version_Association_Plan.md` §4.9 thresholds:\n")
    out.append("- **Green**: 10-50 params added, 0-5 params removed, 0-5 renamed, "
               "wiki avg Jaccard > 0.5 -> proceed")
    out.append("- **Yellow**: 50+ added OR 5+ removed OR many low-similarity rewrites -> review")
    out.append("- **Red**: >100 added/removed OR >50% files near zero similarity -> wiki regen broke\n")
    out.append(f"This diff: **{verdict}**\n")
    out.append(f"- Params added: {len(param_inv['added'])}")
    out.append(f"- Params removed: {len(param_inv['removed'])}")
    out.append(f"- Params renamed: {len(param_inv['renamed'])}")
    out.append(f"- Wiki avg Jaccard: {wiki['avg_jaccard']:.3f}\n")
    for n in verdict_notes:
        out.append(f"- {n}")
    out.append("")

    # ----- Section 1: Parameter inventory -----
    out.append("## 1. Parameter Inventory\n")
    out.append(f"- Profile A ({profile_a.name}): {param_inv['count_a']} parameters")
    out.append(f"- Profile B ({profile_b.name}): {param_inv['count_b']} parameters\n")

    out.append(f"### Added in B (only in B): {len(param_inv['added'])} params\n")
    rows = []
    for name in param_inv["added"][:200]:
        node = param_inv["nodes_b"].get(name, {})
        cat = node.get("category", "")
        units = node.get("units", "")
        rows.append([name, cat, units])
    out.append(md_table(["Parameter", "Category", "Units"], rows))
    if len(param_inv["added"]) > 200:
        out.append(f"_(truncated; showing first 200 of {len(param_inv['added'])})_\n")

    out.append(f"### Removed in B (only in A): {len(param_inv['removed'])} params\n")
    rows = []
    for name in param_inv["removed"][:200]:
        node = param_inv["nodes_a"].get(name, {})
        cat = node.get("category", "")
        units = node.get("units", "")
        rows.append([name, cat, units])
    out.append(md_table(["Parameter", "Category", "Units"], rows))
    if len(param_inv["removed"]) > 200:
        out.append(f"_(truncated; showing first 200 of {len(param_inv['removed'])})_\n")

    out.append(f"### Renamed (fuzzy match, similarity >= 0.7): {len(param_inv['renamed'])}\n")
    out.append(md_table(
        ["Old (A)", "New (B)", "Similarity"],
        [[a, b, f"{s:.2f}"] for a, b, s in param_inv["renamed"]],
    ))

    out.append(f"### Common (in both): {len(param_inv['common'])} parameters\n")

    # ----- Section 2: Graph structure -----
    out.append("## 2. Graph Structure\n")
    if graph_struct["untyped_a"] or graph_struct["untyped_b"]:
        out.append(f"_Note: untyped nodes — A: {graph_struct['untyped_a']}, "
                   f"B: {graph_struct['untyped_b']}. Type inferred from ID prefix where possible._\n")

    out.append("### Node counts\n")
    nt_a = graph_struct["node_types_a"]
    nt_b = graph_struct["node_types_b"]
    all_types = sorted(set(nt_a) | set(nt_b))
    rows = []
    for t in all_types:
        a, b = nt_a.get(t, 0), nt_b.get(t, 0)
        rows.append([t, a, b, f"{b - a:+d}"])
    rows.append(["**Total**", graph_struct["node_total_a"], graph_struct["node_total_b"],
                 f"{graph_struct['node_total_b'] - graph_struct['node_total_a']:+d}"])
    out.append(md_table(["Node type", "A", "B", "Δ"], rows))

    out.append("### Edge counts\n")
    et_a = graph_struct["edge_types_a"]
    et_b = graph_struct["edge_types_b"]
    all_etypes = sorted(set(et_a) | set(et_b))
    rows = []
    for t in all_etypes:
        a, b = et_a.get(t, 0), et_b.get(t, 0)
        rows.append([t, a, b, f"{b - a:+d}"])
    rows.append(["**Total**", graph_struct["edge_total_a"], graph_struct["edge_total_b"],
                 f"{graph_struct['edge_total_b'] - graph_struct['edge_total_a']:+d}"])
    out.append(md_table(["Edge type", "A", "B", "Δ"], rows))

    out.append("### Per-type node adds/removes\n")
    rows = []
    for t in sorted(graph_struct["node_changes_per_type"]):
        ch = graph_struct["node_changes_per_type"][t]
        if ch["added"] == 0 and ch["removed"] == 0:
            continue
        rows.append([t, ch["added"], ch["removed"]])
    out.append(md_table(["Node type", "Added in B", "Removed in B"], rows))

    out.append("### Per-type edge adds/removes\n")
    rows = []
    e_added = graph_struct["edges_added_by_type"]
    e_removed = graph_struct["edges_removed_by_type"]
    all_e = sorted(set(e_added) | set(e_removed))
    for t in all_e:
        if e_added.get(t, 0) == 0 and e_removed.get(t, 0) == 0:
            continue
        rows.append([t, e_added.get(t, 0), e_removed.get(t, 0)])
    out.append(md_table(["Edge type", "Added in B", "Removed in B"], rows))

    # ----- Section 3: Wiki content -----
    out.append("## 3. Wiki Content\n")
    out.append(f"- Profile A wiki: {wiki['count_a']} files at `{profile_a.wiki_root}`")
    out.append(f"- Profile B wiki: {wiki['count_b']} files at `{profile_b.wiki_root}`")
    out.append(f"- Average Jaccard for files in both: **{wiki['avg_jaccard']:.3f}**\n")

    out.append(f"### Files added in B: {len(wiki['only_b'])}\n")
    rows = [[f["path"], f["lines"]] for f in wiki["only_b"][:200]]
    out.append(md_table(["Path", "Lines"], rows))
    if len(wiki["only_b"]) > 200:
        out.append(f"_(truncated; showing first 200 of {len(wiki['only_b'])})_\n")

    out.append(f"### Files removed in B: {len(wiki['only_a'])}\n")
    rows = [[f["path"], f["lines"]] for f in wiki["only_a"][:200]]
    out.append(md_table(["Path", "Lines"], rows))
    if len(wiki["only_a"]) > 200:
        out.append(f"_(truncated; showing first 200 of {len(wiki['only_a'])})_\n")

    out.append(f"### Likely wiki renames (path similarity >= 0.6): {len(wiki['renames'])}\n")
    out.append(md_table(
        ["Old (A)", "New (B)", "Similarity"],
        [[a, b, f"{s:.2f}"] for a, b, s in wiki["renames"]],
    ))

    out.append(f"### Files in both: {len(wiki['in_both'])}\n")
    out.append("Top 20 most-changed (least similar first):\n")
    sorted_both = sorted(wiki["in_both"], key=lambda f: f["jaccard"])
    rows = []
    for f in sorted_both[:20]:
        rows.append([
            f["path"],
            f"{f['lines_a']}->{f['lines_b']}",
            f"{f['jaccard']:.3f}",
            jaccard_verdict(f["jaccard"]),
        ])
    out.append(md_table(["Path", "Lines A->B", "Jaccard", "Verdict"], rows))

    # ----- Section 4: Parameter file -----
    out.append("## 4. Parameter File\n")
    out.append(f"- Profile A: `{profile_a.param_path}` ({param_files['format_a']}, "
               f"{param_files['count_a']} parameters)")
    out.append(f"- Profile B: `{profile_b.param_path}` ({param_files['format_b']}, "
               f"{param_files['count_b']} parameters)\n")

    out.append(f"### Parameters added: {len(param_files['added'])}\n")
    rows = [[p["name"], p["default"], p["dims"], p["units"]]
            for p in param_files["added"][:200]]
    out.append(md_table(["Parameter", "Default", "Dims", "Units"], rows))
    if len(param_files["added"]) > 200:
        out.append(f"_(truncated; showing first 200 of {len(param_files['added'])})_\n")

    out.append(f"### Parameters removed: {len(param_files['removed'])}\n")
    rows = [[p["name"], p["default"]] for p in param_files["removed"][:200]]
    out.append(md_table(["Parameter", "Last default (A)"], rows))
    if len(param_files["removed"]) > 200:
        out.append(f"_(truncated; showing first 200 of {len(param_files['removed'])})_\n")

    out.append(f"### Parameters with changed defaults: {len(param_files['changed_default'])}\n")
    rows = [[p["name"], p["a"], p["b"]] for p in param_files["changed_default"][:200]]
    out.append(md_table(["Parameter", "A default", "B default"], rows))
    if len(param_files["changed_default"]) > 200:
        out.append(f"_(truncated; showing first 200 of {len(param_files['changed_default'])})_\n")

    out.append(f"### Parameters with changed dimensions: {len(param_files['changed_dims'])}\n")
    rows = [[p["name"], p["a"], p["b"]] for p in param_files["changed_dims"][:200]]
    out.append(md_table(["Parameter", "A dims", "B dims"], rows))

    # ----- Interpretation -----
    out.append("---\n")
    out.append("## Interpretation\n")
    if verdict == "Green":
        out.append(f"Overall verdict: **GREEN — proceed.** The diff is within the safe band "
                   f"(see Sanity assessment). Profile B (`{profile_b.name}`) appears to be a "
                   f"clean evolution of Profile A (`{profile_a.name}`): "
                   f"{len(param_inv['added'])} parameters added, "
                   f"{len(param_inv['removed'])} removed, "
                   f"{len(param_inv['renamed'])} renamed, with wiki content largely preserved "
                   f"(avg Jaccard {wiki['avg_jaccard']:.2f}).\n")
    elif verdict == "Yellow":
        out.append(f"Overall verdict: **YELLOW — review before adopting.** "
                   f"At least one threshold tripped. Reasons: "
                   + " ".join(verdict_notes) + "\n")
    else:
        out.append(f"Overall verdict: **RED — investigate.** "
                   f"This is a large divergence and likely indicates a regen problem. "
                   f"Reasons: " + " ".join(verdict_notes) + "\n")

    out.append("**Where to look first:**\n")
    out.append("- Section 1 (parameter inventory) for additions/removals tied to the model "
               "version bump.")
    out.append("- Section 3 (wiki content) for the top-20 most-changed files; major rewrites "
               "may indicate restructured documentation or shifted file paths.")
    out.append("- Section 4 (parameter file) for default-value drifts, which directly affect "
               "calibration starting points.\n")

    out.append("**v0.1 scope note:** Retrieval semantics dimension (5) is not yet implemented "
               "— it requires running embedding queries against both ChromaDB stores and "
               "comparing top-k overlap. Add when ready to validate downstream RAG behavior.\n")

    return "\n".join(out)


# =============================================================================
# CLI
# =============================================================================

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--profile-a-graph", required=True, type=Path)
    p.add_argument("--profile-a-wiki", required=True, type=Path)
    p.add_argument("--profile-a-param", required=True, type=Path)
    p.add_argument("--profile-a-name", required=True)
    p.add_argument("--profile-b-graph", required=True, type=Path)
    p.add_argument("--profile-b-wiki", required=True, type=Path)
    p.add_argument("--profile-b-param", required=True, type=Path)
    p.add_argument("--profile-b-name", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)

    profile_a = Profile(args.profile_a_name, args.profile_a_graph,
                        args.profile_a_wiki, args.profile_a_param)
    profile_b = Profile(args.profile_b_name, args.profile_b_graph,
                        args.profile_b_wiki, args.profile_b_param)

    # Validate inputs
    for label, path in [
        ("profile-a-graph", profile_a.graph_path),
        ("profile-a-wiki", profile_a.wiki_root),
        ("profile-a-param", profile_a.param_path),
        ("profile-b-graph", profile_b.graph_path),
        ("profile-b-wiki", profile_b.wiki_root),
        ("profile-b-param", profile_b.param_path),
    ]:
        if not path.exists():
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            return 2

    print(f"[rag_diff] Loading graphs...", file=sys.stderr)
    graph_a = load_graph(profile_a.graph_path)
    graph_b = load_graph(profile_b.graph_path)

    print(f"[rag_diff] Diffing parameter inventory...", file=sys.stderr)
    param_inv = diff_parameter_inventory(graph_a, graph_b)

    print(f"[rag_diff] Diffing graph structure...", file=sys.stderr)
    graph_struct = diff_graph_structure(graph_a, graph_b)

    print(f"[rag_diff] Diffing wiki content...", file=sys.stderr)
    wiki = diff_wiki(profile_a, profile_b)

    print(f"[rag_diff] Diffing parameter files...", file=sys.stderr)
    param_files = diff_param_files(profile_a, profile_b)

    print(f"[rag_diff] Computing verdict...", file=sys.stderr)
    verdict, notes = sanity_verdict(param_inv, wiki,
                                    profile_a.name, profile_b.name,
                                    graph_struct=graph_struct)

    print(f"[rag_diff] Rendering report...", file=sys.stderr)
    report = render_report(profile_a, profile_b, param_inv, graph_struct,
                           wiki, param_files, verdict, notes)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"[rag_diff] Wrote {args.output}", file=sys.stderr)
    print(f"[rag_diff] Verdict: {verdict}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
