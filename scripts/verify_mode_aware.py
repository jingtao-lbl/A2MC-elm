#!/Library/Frameworks/Python.framework/Versions/3.10/bin/python3
"""
verify_mode_aware.py - Mode-aware RAG retrieval verification harness.

Runs the fixture suite at `tests/test_mode_filters.py` plus a real-index
end-to-end smoke test (kb_source filter against the active milestone),
and writes a Markdown report to
`docs/a2mc_reference/mode_aware_verification.md`.

Mirrors `verify_phase4.py` in shape. Doc 20 §4.7.

Usage:
    python scripts/verify_mode_aware.py
    python scripts/verify_mode_aware.py --output /tmp/mode_aware.md

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))


# =============================================================================
# Run unittest fixtures programmatically
# =============================================================================

def run_fixtures() -> dict:
    """Run tests/test_mode_filters.py and capture results."""
    from tests import test_mode_filters

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(test_mode_filters)

    stream = StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    result = runner.run(suite)

    return {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        "failure_details": [
            {"name": str(t), "msg": msg.split("\n")[0]}
            for t, msg in result.failures
        ],
        "error_details": [
            {"name": str(t), "msg": msg.split("\n")[0]}
            for t, msg in result.errors
        ],
        "log": stream.getvalue(),
    }


# =============================================================================
# Real-index smoke test (post-rebuild)
# =============================================================================

def run_real_index_smoke() -> dict:
    """Smoke-test kb_source filter against the live api-43-1 index."""
    tests = []

    try:
        os.environ.setdefault("A2MC_RAG_DIR", str(_REPO_ROOT / "rag"))
        os.environ.setdefault("A2MC_RAG_ACTIVE", "api-43-1")
        from rag.vector_store import FATESVectorStore
        store = FATESVectorStore()
    except Exception as e:
        return {"tests": [{"name": "vector store init", "result": False, "detail": str(e)}]}

    # 1. Distribution check
    try:
        all_meta = store.collection.get(include=["metadatas"], limit=10000)
        from collections import Counter
        counter = Counter(m.get("kb_source", "MISSING") for m in all_meta["metadatas"])
        n_total = len(all_meta["metadatas"])
        n_fates = counter.get("fates", 0)
        n_elm = counter.get("elm", 0)
        n_missing = counter.get("MISSING", 0) + counter.get("", 0)
        ok = n_fates > 0 and n_elm > 0 and n_missing == 0
        tests.append({
            "name": "kb_source populated on all chunks (no MISSING/empty)",
            "result": ok,
            "detail": f"total={n_total}, fates={n_fates}, elm={n_elm}, missing/empty={n_missing}",
        })
    except Exception as e:
        tests.append({"name": "kb_source distribution", "result": False, "detail": str(e)})
        return {"tests": tests}

    # 2. Filter test: phenology query with kb=fates returns only FATES chunks
    try:
        res = store.query("phenology", n_results=5, kb_source="fates")
        sources = {r.get("kb_source", "?") for r in res}
        ok = len(res) > 0 and sources == {"fates"}
        tests.append({
            "name": "kb_source='fates' returns only FATES chunks",
            "result": ok,
            "detail": f"got {len(res)} results, kb_sources={sources}",
        })
    except Exception as e:
        tests.append({"name": "kb=fates filter", "result": False, "detail": str(e)})

    # 3. Filter test: kb=elm returns only ELM chunks
    try:
        res = store.query("phenology", n_results=5, kb_source="elm")
        sources = {r.get("kb_source", "?") for r in res}
        ok = len(res) > 0 and sources == {"elm"}
        tests.append({
            "name": "kb_source='elm' returns only ELM chunks",
            "result": ok,
            "detail": f"got {len(res)} results, kb_sources={sources}",
        })
    except Exception as e:
        tests.append({"name": "kb=elm filter", "result": False, "detail": str(e)})

    # 4. No filter returns mixed
    try:
        res = store.query("phenology", n_results=10)
        sources = {r.get("kb_source", "?") for r in res}
        ok = len(res) > 0 and "fates" in sources  # at least FATES present (ELM may not surface in top-10)
        tests.append({
            "name": "no filter returns mixed kb_sources",
            "result": ok,
            "detail": f"got {len(res)} results, kb_sources={sources}",
        })
    except Exception as e:
        tests.append({"name": "no filter", "result": False, "detail": str(e)})

    # 5. ConfigMode integration: kb_source filter follows bgc_mode
    try:
        from tools.config import ConfigMode
        # Default ELM (bgc_mode='sp') -> use_fates=False -> filters to 'elm'
        default_elm = ConfigMode()
        ok = default_elm.kb_source_filter() == "elm"
        tests.append({
            "name": "ConfigMode default (bgc=sp -> ELM-only) -> kb_source_filter() == 'elm'",
            "result": ok,
            "detail": f"got {default_elm.kb_source_filter()!r}",
        })
        # FATES-on config -> no kb_source filter (both ELM and FATES allowed)
        fates_on = ConfigMode(bgc_mode="fates", use_fates=True, parteh_mode=2,
                              nutrient="cnp", nutrient_comp_pathway="eca")
        ok2 = fates_on.kb_source_filter() is None
        tests.append({
            "name": "ConfigMode(bgc_mode='fates') -> kb_source_filter() = None",
            "result": ok2,
            "detail": f"got {fates_on.kb_source_filter()!r}",
        })
    except Exception as e:
        tests.append({"name": "ConfigMode integration", "result": False, "detail": str(e)})

    return {"tests": tests}


# =============================================================================
# Render report
# =============================================================================

def render_report(fixtures: dict, smoke: dict, output_path: Path,
                  tier4: Optional[dict] = None,
                  snapshot: Optional[dict] = None,
                  completeness: Optional[dict] = None,
                  cross_milestone: Optional[dict] = None) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# Mode-Aware Retrieval Verification Report\n",
        f"**Generated:** {ts}\n",
        "Doc 20 Phase A + Phase B verification. Runs the unittest fixture suite at "
        "`tests/test_mode_filters.py` plus a real-index smoke test (kb_source + mode-aware "
        "filter end-to-end) plus the Tier 4 mode-metadata validator (Doc 21 Chunk B.3.5).\n",
        "---\n",
    ]

    # Fixture results
    lines.append("## Fixture suite (`tests/test_mode_filters.py`)\n")
    lines.append(f"- Tests run:   {fixtures['tests_run']}")
    lines.append(f"- Passed:      {fixtures['passed']}")
    lines.append(f"- Skipped:     {fixtures['skipped']} (Phase B placeholders)")
    lines.append(f"- Failures:    {fixtures['failures']}")
    lines.append(f"- Errors:      {fixtures['errors']}\n")
    if fixtures["failure_details"]:
        lines.append("### Failures")
        for f in fixtures["failure_details"]:
            lines.append(f"- `{f['name']}`: {f['msg']}")
        lines.append("")
    if fixtures["error_details"]:
        lines.append("### Errors")
        for e in fixtures["error_details"]:
            lines.append(f"- `{e['name']}`: {e['msg']}")
        lines.append("")

    # Smoke results
    lines.append("## Real-index smoke (active RAG profile)\n")
    lines.append("| Test | Result | Detail |")
    lines.append("|---|---|---|")
    pass_count = 0
    for t in smoke.get("tests", []):
        mark = "PASS" if t["result"] else "FAIL"
        if t["result"]:
            pass_count += 1
        lines.append(f"| {t['name']} | {mark} | {t['detail']} |")
    lines.append("")
    lines.append(f"**{pass_count}/{len(smoke['tests'])} smoke tests pass.**\n")

    # Tier 4 results
    if tier4 is not None:
        lines.append("## Tier 4 mode-metadata validator (Doc 21 Chunk B.3.5)\n")
        if "error" in tier4:
            lines.append(f"- Status: {tier4['verdict']}")
            lines.append(f"- Detail: {tier4['error']}\n")
        else:
            lines.append(f"- Verdict: **{tier4['verdict']}**")
            lines.append(f"- OK:    {tier4['n_ok']}")
            lines.append(f"- WARN:  {tier4['n_warn']}")
            lines.append(f"- ERROR: {tier4['n_error']}\n")
            lines.append("Asserts:")
            lines.append("- (a) YAML-entity flags propagated to chunks + graph nodes")
            lines.append("- (b) Path-prefix flags applied to wiki chunks")
            lines.append("- (c) Precedence invariant (no chunk has both universal AND per-axis)")
            lines.append("- (d) No-orphan invariant (every chunk has mode metadata)")
            lines.append("- (e) Graph-chunk consistency for YAML-tagged entities\n")

    # Validator #1: snapshot
    if snapshot is not None:
        lines.append("## Validator #1: snapshot (end-to-end integration)\n")
        if "error" in snapshot:
            lines.append(f"- Status: {snapshot['verdict']}")
            lines.append(f"- Detail: {snapshot['error']}\n")
        else:
            lines.append(f"- Verdict: **{snapshot['verdict']}**")
            lines.append(f"- Fixtures: {snapshot['n_pass']}/{snapshot['fixtures']} pass\n")
            lines.append("Captures real Phase 3 prompt context for 5 ConfigMode "
                         "fixtures and asserts mode block + filter both fire correctly.\n")

    # Validator #2: profile completeness
    if completeness is not None:
        lines.append("## Validator #2: profile completeness (statistical coverage)\n")
        if "error" in completeness:
            lines.append(f"- Status: {completeness['verdict']}")
            lines.append(f"- Detail: {completeness['error']}\n")
        else:
            lines.append(f"- Verdict: **{completeness['verdict']}**")
            lines.append(f"- Chunks: {completeness['n_chunks']}  |  "
                         f"Nodes: {completeness['n_nodes']}\n")
            lines.append("| Category | Severity | Summary |")
            lines.append("|---|---|---|")
            for name, sev, summary in completeness.get("category_summaries", []):
                lines.append(f"| {name} | {sev} | {summary[:80]} |")
            lines.append("")

    # Validator #3: cross-milestone consistency
    if cross_milestone is not None:
        lines.append("## Validator #3: cross-milestone consistency\n")
        if "error" in cross_milestone:
            lines.append(f"- Status: {cross_milestone['verdict']}")
            lines.append(f"- Detail: {cross_milestone['error']}\n")
        else:
            lines.append(f"- Verdict: **{cross_milestone['verdict']}**")
            lines.append(f"- Profiles compared: {', '.join(cross_milestone['profiles'])}")
            lines.append(f"- Drift: {cross_milestone['n_drift']}  |  "
                         f"Coverage warnings: {cross_milestone['n_warn']}\n")

    # Overall
    fixtures_ok = (fixtures["failures"] == 0 and fixtures["errors"] == 0)
    smoke_ok = pass_count == len(smoke["tests"])
    tier4_ok = (tier4 is None) or tier4.get("verdict") in ("Green", "Yellow", "Skipped")
    snapshot_ok = (snapshot is None) or snapshot.get("verdict") in ("Green", "Skipped")
    completeness_ok = (completeness is None) or completeness.get("verdict") in ("Green", "Yellow", "Skipped")
    cross_ok = (cross_milestone is None) or cross_milestone.get("verdict") in ("Green", "Yellow", "Skipped")
    lines.append("---\n")
    lines.append("## Overall\n")
    lines.append(f"- Fixtures:                 {'PASS' if fixtures_ok else 'FAIL'}")
    lines.append(f"- Smoke:                    {'PASS' if smoke_ok else 'FAIL'}")
    if tier4 is not None:
        lines.append(f"- Tier 4 (metadata):        {tier4.get('verdict', 'Skipped')}")
    if snapshot is not None:
        lines.append(f"- Validator #1 (snapshot):  {snapshot.get('verdict', 'Skipped')}")
    if completeness is not None:
        lines.append(f"- Validator #2 (coverage):  {completeness.get('verdict', 'Skipped')}")
    if cross_milestone is not None:
        lines.append(f"- Validator #3 (x-milestone): {cross_milestone.get('verdict', 'Skipped')}")
    overall = "GREEN" if (fixtures_ok and smoke_ok and tier4_ok
                          and snapshot_ok and completeness_ok and cross_ok) else "RED"
    lines.append(f"- Phase A+B status: **{overall}**")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_tier4_validator(profile: str) -> dict:
    """Run the Tier 4 mode-metadata validator (Doc 21 Chunk B.3.5).

    Returns a dict with {n_ok, n_warn, n_error, verdict} or {error: ...} on failure.
    """
    try:
        # Ensure tools/ on path; verify_mode_aware.py already adds repo root
        from tools.mode_metadata_validator import run_validation
        report = run_validation(profile)
        return {
            "n_ok": report.n_ok,
            "n_warn": report.n_warn,
            "n_error": report.n_error,
            "verdict": report.verdict,
        }
    except FileNotFoundError as e:
        return {"error": f"Profile artifacts missing: {e}", "verdict": "Skipped"}
    except Exception as e:
        return {"error": str(e), "verdict": "Error"}


def run_snapshot_validator(profile: str) -> dict:
    """Validator #1: end-to-end snapshot test of mode-aware retrieval.

    Captures the AI's actual prompt context for 5 fixture ConfigModes and
    asserts mode block + filter both fire correctly. The only validator
    that exercises the full chain (env vars → ConfigMode → reasoning →
    retriever → ChromaDB → rendered output).
    """
    try:
        from tools.snapshot_validator import run_all_fixtures
        results = run_all_fixtures(profile)
        n_pass = sum(1 for r in results if r.passed)
        n_fail = len(results) - n_pass
        verdict = "Green" if n_fail == 0 else "Red"
        return {
            "n_pass": n_pass, "n_fail": n_fail,
            "verdict": verdict, "fixtures": len(results),
        }
    except Exception as e:
        return {"error": str(e), "verdict": "Error"}


def run_completeness_validator(profile: str) -> dict:
    """Validator #2: profile statistical coverage check.

    Five categories: chunk-tagging distribution, wiki-dir coverage,
    YAML-entity coverage, Tier 2 axis distribution, golden chunk counts.
    """
    try:
        from tools.profile_completeness_validator import run_validation
        report = run_validation(profile)
        return {
            "verdict": report.verdict,
            "n_chunks": report.n_chunks,
            "n_nodes": report.n_nodes,
            "category_summaries": [
                (c.name, c.severity, c.summary) for c in report.categories
            ],
        }
    except Exception as e:
        return {"error": str(e), "verdict": "Error"}


def run_cross_milestone_validator() -> dict:
    """Validator #3: cross-milestone YAML consistency.

    Compares applies_in: tagging across all active (non-legacy) milestones
    plus the canonical YAML. Catches drift where a parameter's tagging
    diverges across profile YAMLs.
    """
    try:
        from tools.cross_milestone_validator import run_validation
        report = run_validation(include_legacy=False)
        return {
            "verdict": report.verdict,
            "profiles": report.profiles,
            "n_drift": report.n_drift,
            "n_warn": report.n_warn,
        }
    except RuntimeError as e:
        # Need ≥2 profiles; skip gracefully if only canonical exists
        return {"error": str(e), "verdict": "Skipped"}
    except Exception as e:
        return {"error": str(e), "verdict": "Error"}


# =============================================================================
# In-process entry point for orchestrator validator gate (v2.98 Chunk C)
# =============================================================================

def run_all_validators(profile_name: str = "api-43-1",
                       *, include_smoke: bool = True) -> dict:
    """Run all five validation layers in-process and return a unified verdict.

    Used by the orchestrator's auto-rebuild path (docs/22 Chunk D) as a
    post-rebuild gate: a Red verdict triggers rollback to the previous
    profile snapshot.

    Args:
        profile_name: milestone profile to validate (default ``"api-43-1"``).
        include_smoke: when True (default), runs the unit fixture suite and
            real-index smoke tests in addition to the four named validators.
            Set False for a faster gate when only the rebuilt profile's
            content needs checking.

    Returns:
        ``{'verdict': 'Green' | 'Red', 'details': {layer_name: {...}}}``
        where ``layer_name`` covers ``fixtures``, ``smoke``, ``tier4``,
        ``snapshot``, ``completeness``, ``cross_milestone``. Each layer's
        sub-dict matches what the per-layer ``run_*`` function returns.

    Verdict rules mirror ``main()`` exactly:
        - fixtures: PASS iff failures == 0 and errors == 0
        - smoke: PASS iff every test result is True
        - tier4 / completeness / cross_milestone: PASS for verdicts in
          {Green, Yellow, Skipped} (Yellow is informational, not blocking)
        - snapshot: PASS only for {Green, Skipped} (snapshot Yellow is
          treated as Red because it indicates a real fixture mismatch)
    """
    details: dict = {}
    layer_oks: list[bool] = []

    if include_smoke:
        details["fixtures"] = run_fixtures()
        layer_oks.append(
            details["fixtures"]["failures"] == 0
            and details["fixtures"]["errors"] == 0
        )
        details["smoke"] = run_real_index_smoke()
        smoke_pass = sum(1 for t in details["smoke"]["tests"] if t["result"])
        layer_oks.append(smoke_pass == len(details["smoke"]["tests"]))

    details["tier4"] = run_tier4_validator(profile_name)
    layer_oks.append(details["tier4"].get("verdict") in ("Green", "Yellow", "Skipped"))

    details["snapshot"] = run_snapshot_validator(profile_name)
    layer_oks.append(details["snapshot"].get("verdict") in ("Green", "Skipped"))

    details["completeness"] = run_completeness_validator(profile_name)
    layer_oks.append(details["completeness"].get("verdict") in ("Green", "Yellow", "Skipped"))

    details["cross_milestone"] = run_cross_milestone_validator()
    layer_oks.append(
        details["cross_milestone"].get("verdict") in ("Green", "Yellow", "Skipped")
    )

    return {
        "verdict": "Green" if all(layer_oks) else "Red",
        "details": details,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Verify mode-aware retrieval (Doc 20 Phase A + Phase B)."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "docs" / "a2mc_reference" / "mode_aware_verification.md",
        help="Markdown report output path",
    )
    parser.add_argument(
        "--profile",
        default="api-43-1",
        help="Milestone profile for Tier 4 validator (default: api-43-1)",
    )
    args = parser.parse_args()

    print("Running fixture suite...")
    fixtures = run_fixtures()
    print(f"  {fixtures['passed']}/{fixtures['tests_run']} pass "
          f"({fixtures['skipped']} skipped, "
          f"{fixtures['failures']} fail, {fixtures['errors']} error)")

    print("Running real-index smoke tests...")
    smoke = run_real_index_smoke()
    smoke_pass = sum(1 for t in smoke["tests"] if t["result"])
    print(f"  {smoke_pass}/{len(smoke['tests'])} pass")

    print(f"Running Tier 4 mode-metadata validator (profile={args.profile})...")
    tier4 = run_tier4_validator(args.profile)
    if "error" in tier4:
        print(f"  Tier 4: {tier4['verdict']} ({tier4['error']})")
    else:
        print(f"  Tier 4: {tier4['verdict']} "
              f"(OK={tier4['n_ok']} WARN={tier4['n_warn']} ERROR={tier4['n_error']})")

    print(f"Running Validator #1 (snapshot, profile={args.profile})...")
    snapshot = run_snapshot_validator(args.profile)
    if "error" in snapshot:
        print(f"  Snapshot: {snapshot['verdict']} ({snapshot['error']})")
    else:
        print(f"  Snapshot: {snapshot['verdict']} "
              f"({snapshot['n_pass']}/{snapshot['fixtures']} fixtures pass)")

    print(f"Running Validator #2 (profile completeness, profile={args.profile})...")
    completeness = run_completeness_validator(args.profile)
    if "error" in completeness:
        print(f"  Completeness: {completeness['verdict']} ({completeness['error']})")
    else:
        print(f"  Completeness: {completeness['verdict']}")

    print("Running Validator #3 (cross-milestone consistency)...")
    cross_milestone = run_cross_milestone_validator()
    if "error" in cross_milestone:
        print(f"  Cross-milestone: {cross_milestone['verdict']} ({cross_milestone['error']})")
    else:
        print(f"  Cross-milestone: {cross_milestone['verdict']} "
              f"({cross_milestone['n_drift']} drift, {cross_milestone['n_warn']} coverage warnings)")

    render_report(
        fixtures, smoke, args.output,
        tier4=tier4, snapshot=snapshot,
        completeness=completeness, cross_milestone=cross_milestone,
    )
    print(f"\nReport: {args.output}")

    fixtures_ok = (fixtures["failures"] == 0 and fixtures["errors"] == 0)
    smoke_ok = smoke_pass == len(smoke["tests"])
    tier4_ok = tier4.get("verdict") in ("Green", "Yellow", "Skipped")
    snapshot_ok = snapshot.get("verdict") in ("Green", "Skipped")
    completeness_ok = completeness.get("verdict") in ("Green", "Yellow", "Skipped")
    cross_ok = cross_milestone.get("verdict") in ("Green", "Yellow", "Skipped")
    if not (fixtures_ok and smoke_ok and tier4_ok
            and snapshot_ok and completeness_ok and cross_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()
