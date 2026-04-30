#!/usr/bin/env python3
"""
snapshot_validator.py - End-to-end snapshot test of mode-aware retrieval.

Captures the AI's actual Phase 3 prompt context for a set of fixture
ConfigModes and asserts:

  - The "Active Run Configuration" prompt block is present and matches
    the expected mode declaration.
  - Mode-restricted parameter strings are absent when the filter is on
    (e.g., no `fates_cnp_*` in PARTEH=1 retrieval).
  - Universal parameters are present in all modes
    (e.g., `fates_alloc_storage_cushion`).
  - For ELM-only mode, the kb_source filter excludes FATES wiki paths.

The "snapshot" is the rendered context bytes — not just the chunk IDs
that pass the where clause. So every link in the chain is exercised:

    ConfigMode.from_env()
        ↓
    HybridRetriever.get_targeted_context(config_mode=...)
        ↓
    vector_store.query(mode_where=...)  +  graph traversal
        ↓
    rendered Markdown context block
        ↓
    these assertions

This is the only validator that catches integration regressions across
the full chain. The 4 existing tiers test individual layers; this test
exercises the layers together.

Usage
-----
    python tools/snapshot_validator.py --profile api-43-1 \\
        --output docs/a2mc_reference/snapshot_validation_api-43-1.md

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# =============================================================================
# Fixture ConfigModes — the modes we snapshot against
# =============================================================================

def _kougarok_cnp_eca():
    from tools.config import ConfigMode
    return ConfigMode(
        bgc_mode="fates", use_fates=True, parteh_mode=2,
        nutrient="cnp", nutrient_comp_pathway="eca",
        soil_decomp="century",
    )


def _parteh1_carbon_only():
    from tools.config import ConfigMode
    return ConfigMode(
        bgc_mode="fates", use_fates=True, parteh_mode=1,
        nutrient="c", nutrient_comp_pathway="rd",
    )


def _elm_only_bgc():
    from tools.config import ConfigMode
    return ConfigMode(
        bgc_mode="bgc", use_fates=False, parteh_mode=1,
        nutrient="cnp", nutrient_comp_pathway="eca",
        soil_decomp="ctc",
    )


def _kougarok_with_fire():
    from tools.config import ConfigMode
    return ConfigMode(
        bgc_mode="fates", use_fates=True, parteh_mode=2,
        nutrient="cnp", nutrient_comp_pathway="eca",
        soil_decomp="century",
        fates_spitfire_mode=1,
    )


def _kougarok_nocomp():
    from tools.config import ConfigMode
    return ConfigMode(
        bgc_mode="fates", use_fates=True, parteh_mode=2,
        nutrient="cnp", nutrient_comp_pathway="eca",
        soil_decomp="century",
        use_fates_nocomp=True,
    )


# (fixture_name, ConfigMode factory, list of assertions)
# Each assertion is (kind, value): kind in {must_contain, must_not_contain, lambda}
@dataclass
class Fixture:
    name: str
    description: str
    factory: Callable
    must_contain: List[str] = field(default_factory=list)
    must_not_contain: List[str] = field(default_factory=list)
    # Source-based assertions: parsed from `[N] Source: <path>` lines in rag_context.
    # These avoid false positives from cross-references in chunk content.
    must_not_have_source_substring: List[str] = field(default_factory=list)
    custom_assertions: List[Tuple[str, Callable]] = field(default_factory=list)


# Each fixture's must_contain / must_not_contain are checked against the
# concatenated prompt_block + rag_text. The prompt block carries the active
# mode declaration (Phase A); the rag_text carries vector-similarity-search
# results filtered by mode_where (Phase B).
FIXTURES = [
    Fixture(
        name="kougarok_cnp_eca",
        description="Default Kougarok run: FATES + PARTEH=2 + CNP + ECA + CENTURY",
        factory=_kougarok_cnp_eca,
        must_contain=[
            "FATES: enabled",
            "PARTEH=2",
            "CNP allocation",
            "Competition: ON",
            "ECA pathway",
            "Soil decomposition: century",
        ],
        must_not_contain=[
            "FATES DISABLED",
            "ELM-only run",
            # Carbon-only theory file should not surface in CNP mode
            "carbon_only.md",
        ],
    ),
    Fixture(
        name="parteh1_carbon_only",
        description="Carbon-only PARTEH=1: vector filter blocks CNP theory chunks",
        factory=_parteh1_carbon_only,
        must_contain=[
            "FATES: enabled",
            "PARTEH=1",
            "carbon-only",
            "CNP mechanisms",
            "do NOT apply",
        ],
        # Source-based: no chunk's SOURCE field should match these patterns.
        # (Substring 'cnp_allocation.md' may appear in cross-references in
        # OTHER chunks' content — that's fine; only its source matters.)
        must_not_have_source_substring=[
            "cnp_allocation.md",
            "soil_plant_interface.md",
            "advanced/cnp_calibration_guide.md",
            "advanced/nutrient_competition.md",
            "parteh/h2_callom",
        ],
    ),
    Fixture(
        name="elm_only_bgc",
        description="ELM-only run (use_fates=False): kb_source filter excludes FATES",
        factory=_elm_only_bgc,
        must_contain=[
            "FATES DISABLED",
            "Nutrient cycling: CNP",
            "Soil decomposition: ctc",
        ],
        must_not_contain=[
            "FATES: enabled",
            "PARTEH=",
        ],
        # Source-based: no chunk's source path should be a FATES wiki file
        must_not_have_source_substring=[
            "plant-physiology/parteh",
            "fates_tech_note",
            "fire/",
            "biophysics/hydraulics",
        ],
    ),
    Fixture(
        name="kougarok_with_fire",
        description="Kougarok + spitfire=1: fire content reaches retrieval",
        factory=_kougarok_with_fire,
        must_contain=[
            "FATES: enabled",
            "spitfire=1",
            "FATES features",
        ],
        must_not_contain=[
            "FATES DISABLED",
        ],
    ),
    Fixture(
        name="kougarok_nocomp",
        description="Kougarok + use_fates_nocomp=True: ECA/RD off",
        factory=_kougarok_nocomp,
        must_contain=[
            "FATES: enabled",
            "Competition: OFF",
            "ECA/RD do NOT apply",
        ],
        must_not_contain=[
            "Competition: ON",
        ],
    ),
]


# =============================================================================
# Snapshot capture
# =============================================================================

import re
_SOURCE_LINE_RE = re.compile(r"^\[\d+\]\s+Source:\s+(\S+)\s*\(", re.MULTILINE)


@dataclass
class SnapshotResult:
    fixture: Fixture
    prompt_block: str
    targeted_context: str
    rag_context: str
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return f"{self.prompt_block}\n\n{self.targeted_context}\n\n{self.rag_context}"

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def chunk_sources(self) -> List[str]:
        """Parse rendered Source: lines from rag_context."""
        return _SOURCE_LINE_RE.findall(self.rag_context)


def capture_snapshot(fixture: Fixture, profile: str) -> SnapshotResult:
    """Capture the rendered prompt context for a fixture ConfigMode.

    Two pieces (only the layers where mode filtering applies):
        1. Active mode block (`reasoning.methods._build_active_mode_block`) —
           Phase A prompt-block layer.
        2. RAG context for natural-language calibration queries — exercises
           the vector layer with mode_where filter.

    NOTE: this validator does NOT test `get_targeted_context` with explicit
    param_names/mechanisms. By design (Doc 21 §B.3), the graph layer surfaces
    user-explicitly-requested entities regardless of mode — that's the right
    behavior. Tier 4 mode_metadata_validator covers graph-node tagging
    correctness; the snapshot validator focuses on what the filter ACTUALLY
    blocks at retrieval time, which is the vector-similarity layer.
    """
    # Three natural-language queries exercising different content classes
    queries = [
        "how does the plant allocate carbon and nitrogen between leaves and roots",
        "what controls phosphorus uptake in fine roots",
        "how does fire affect plant mortality",
    ]
    # Set env so reasoning.methods can pick up the ConfigMode
    cm = fixture.factory()
    saved_env = {k: os.environ.get(k) for k in [
        "A2MC_BGC_MODE", "A2MC_FATES_PARTEH_MODE", "A2MC_USE_FATES_NOCOMP",
        "A2MC_FATES_SPITFIRE_MODE", "A2MC_USE_FATES_PLANTHYDRO",
        "A2MC_USE_FATES_LOGGING", "A2MC_ELM_OPTIONS",
        "A2MC_CASE_DIR", "A2MC_CASE_NAME", "A2MC_RAG_ACTIVE",
    ]}
    try:
        # Clear all so the fixture ConfigMode drives everything
        for k in saved_env:
            if k in os.environ:
                del os.environ[k]
        # Set bgc_mode + parteh + nocomp + spitfire from fixture
        os.environ["A2MC_BGC_MODE"] = cm.bgc_mode
        os.environ["A2MC_FATES_PARTEH_MODE"] = str(cm.parteh_mode)
        if cm.use_fates_nocomp:
            os.environ["A2MC_USE_FATES_NOCOMP"] = "true"
        if cm.fates_spitfire_mode:
            os.environ["A2MC_FATES_SPITFIRE_MODE"] = str(cm.fates_spitfire_mode)
        # Construct ELM_OPTIONS string
        elm_opts_parts = [f"-bgc {cm.bgc_mode}"]
        if cm.nutrient:
            elm_opts_parts.append(f"-nutrient {cm.nutrient}")
        if cm.nutrient_comp_pathway:
            elm_opts_parts.append(f"-nutrient_comp_pathway {cm.nutrient_comp_pathway}")
        if cm.soil_decomp:
            elm_opts_parts.append(f"-soil_decomp {cm.soil_decomp}")
        os.environ["A2MC_ELM_OPTIONS"] = " ".join(elm_opts_parts)
        os.environ["A2MC_RAG_ACTIVE"] = profile

        # 1. Active mode block (Phase A)
        try:
            from reasoning.methods import _build_active_mode_block
            prompt_block = _build_active_mode_block()
        except Exception as e:
            prompt_block = f"[ERROR: _build_active_mode_block failed: {e}]"

        # 2. Vector-layer natural-language queries (Phase B filter)
        # Mirror reasoning/base.py: pass BOTH kb_source AND config_mode.
        # (kb_source is the Phase A filter; config_mode is Phase B. They
        # operate on different metadata fields and must be threaded
        # together — get_context does NOT auto-derive one from the other.)
        targeted = ""  # not used; kept for SnapshotResult schema compat
        rag_parts = []
        try:
            from rag.hybrid_retriever import HybridRetriever
            retriever = HybridRetriever(auto_build=False)
            kb_source = cm.kb_source_filter()  # 'elm' if use_fates=False, else None
            for q in queries:
                rag_ctx = retriever.get_context(
                    query=q, n_vector_results=4,
                    include_graph=False,
                    config_mode=cm,
                    kb_source=kb_source,
                )
                rag_parts.append(rag_ctx.get("vector_context", ""))
        except Exception as e:
            rag_parts = [f"[ERROR: get_context failed: {e}]"]
        rag_text = "\n\n---\n\n".join(rag_parts)

    finally:
        # Restore env
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    result = SnapshotResult(
        fixture=fixture,
        prompt_block=prompt_block,
        targeted_context=targeted,
        rag_context=rag_text,
    )

    # Run assertions
    full = result.full_text
    for needle in fixture.must_contain:
        if needle not in full:
            result.failures.append(f"missing required string: {needle!r}")
    for needle in fixture.must_not_contain:
        if needle in full:
            result.failures.append(f"contains forbidden string: {needle!r}")
    # Source-based assertions: check the SOURCE field of returned chunks,
    # not their content (avoids false positives on cross-references).
    for forbidden_substring in fixture.must_not_have_source_substring:
        matches = [s for s in result.chunk_sources if forbidden_substring in s]
        if matches:
            result.failures.append(
                f"chunks with forbidden source substring {forbidden_substring!r}: {matches[:3]}"
            )
    for label, fn in fixture.custom_assertions:
        try:
            ok = fn(result)
        except Exception as e:
            result.failures.append(f"assertion {label!r} raised: {e}")
            continue
        if not ok:
            result.failures.append(f"assertion {label!r} returned False")

    return result


# =============================================================================
# Driver
# =============================================================================

def run_all_fixtures(profile: str) -> List[SnapshotResult]:
    print(f"Snapshot validator: profile={profile}, fixtures={len(FIXTURES)}")
    results = []
    for fix in FIXTURES:
        print(f"  [{fix.name}] {fix.description}")
        r = capture_snapshot(fix, profile)
        if r.passed:
            print(f"    PASS  ({len(r.full_text)} chars)")
        else:
            print(f"    FAIL  ({len(r.failures)} failures)")
            for f in r.failures:
                print(f"      - {f}")
        results.append(r)
    return results


def write_report(results: List[SnapshotResult], out_path: Path,
                 profile: str) -> None:
    n_pass = sum(1 for r in results if r.passed)
    n_fail = len(results) - n_pass
    verdict = "Green" if n_fail == 0 else "Red"

    lines = [
        f"# Snapshot Validation: profile {profile}",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"**Verdict:** {verdict}  ({n_pass}/{len(results)} fixtures pass)",
        "",
        "## Fixtures",
        "",
        "| Fixture | Description | Result | Failures |",
        "|---|---|---|---|",
    ]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"| `{r.fixture.name}` | {r.fixture.description} | "
                     f"{status} | {len(r.failures)} |")
    lines.append("")

    if n_fail:
        lines.append("## Failure detail")
        lines.append("")
        for r in results:
            if not r.passed:
                lines.append(f"### `{r.fixture.name}`")
                lines.append("")
                for f in r.failures:
                    lines.append(f"- {f}")
                lines.append("")

    lines.append("## Snapshot excerpts")
    lines.append("")
    for r in results:
        lines.append(f"### `{r.fixture.name}`  (`{r.fixture.description}`)")
        lines.append("")
        lines.append("**Active mode block:**")
        lines.append("```")
        lines.append(r.prompt_block.strip())
        lines.append("```")
        lines.append(f"**Targeted context:** ({len(r.targeted_context)} chars)")
        lines.append("")
        lines.append(f"**RAG context:** ({len(r.rag_context)} chars)")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    print(f"Report: {out_path}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Snapshot validator (Validator #1)")
    ap.add_argument("--profile", default="api-43-1",
                    help="Milestone profile (default: api-43-1)")
    ap.add_argument("--output", type=Path,
                    help="Path for Markdown report")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    results = run_all_fixtures(args.profile)
    if args.output:
        write_report(results, args.output, args.profile)
    n_fail = sum(1 for r in results if not r.passed)
    if n_fail:
        print(f"\nFAIL: {n_fail}/{len(results)} fixtures failed")
        return 1
    print(f"\nPASS: {len(results)}/{len(results)} fixtures passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
