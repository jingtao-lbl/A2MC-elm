#!/usr/bin/env python3
"""
Phase 3 AI Diagnosis — Claude API and rule-based diagnosis

Extracted from orchestrator.py: _diagnose_with_claude, _diagnose_rule_based.

Author: Jing Tao with Claude
"""

import logging
from dataclasses import asdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def diagnose_with_claude(
    diagnosis_input: Dict,
    reasoning_module,
    screening_data: Dict,
    exploration_data: Optional[Dict] = None,
) -> Dict:
    """Use Claude API for diagnosis with diagnostic script context.

    Args:
        diagnosis_input: Dict with screening_results, sensitivity_rankings,
            targets, iteration, diagnostic_data, diagnostic_images, etc.
        reasoning_module: ReasoningModule instance for Claude API calls.
        screening_data: Full screening data from state (for prior insights).
        exploration_data: Optional exploration data (for prior insights).

    Returns:
        Diagnosis dict with failing_targets, likely_causes, etc.
    """
    try:
        # Enrich results with diagnostic data if available
        results = diagnosis_input["screening_results"].copy()
        diagnostic_data = diagnosis_input.get("diagnostic_data")

        if diagnostic_data:
            # Add diagnostic context to results for AI reasoning
            results["diagnostic_context"] = {
                "parameters": diagnostic_data.parameters if hasattr(diagnostic_data, 'parameters') else {},
                "edge_summary": diagnostic_data.edge_summary if hasattr(diagnostic_data, 'edge_summary') else "",
                "redesign_candidates": diagnostic_data.redesign_candidates if hasattr(diagnostic_data, 'redesign_candidates') else [],
                "target_summary": diagnostic_data.target_summary if hasattr(diagnostic_data, 'target_summary') else "",
                "pft_summary": diagnostic_data.pft_summary if hasattr(diagnostic_data, 'pft_summary') else "",
                "combined_summary": diagnostic_data.get_ai_context() if hasattr(diagnostic_data, 'get_ai_context') else ""
            }
            logger.info("Added diagnostic context to Claude reasoning")

        # Check for additional diagnostic context from requested diagnostics
        additional_context = diagnosis_input.get("diagnostic_context")
        if additional_context:
            # Merge with existing diagnostic context
            if "diagnostic_context" not in results:
                results["diagnostic_context"] = {}
            results["diagnostic_context"]["requested_diagnostics_results"] = additional_context
            if additional_context.get('_combined_summary'):
                results["diagnostic_context"]["additional_analysis"] = additional_context['_combined_summary']
            logger.info("Added requested diagnostics context to Claude reasoning")

        # Add hypothesis test results from Skip Testing path
        hypothesis_tests = diagnosis_input.get("hypothesis_tests", [])
        if hypothesis_tests:
            results["hypothesis_test_results"] = hypothesis_tests
            logger.info(f"Added {len(hypothesis_tests)} hypothesis test results to Claude reasoning")

        # Add previous hypotheses for context (strip non-serializable fields)
        previous_hypotheses = diagnosis_input.get("previous_hypotheses", [])
        if previous_hypotheses:
            clean_hypotheses = []
            for h in previous_hypotheses:
                if isinstance(h, dict):
                    clean_hypotheses.append({k: v for k, v in h.items()
                                             if not k.startswith('_')})
                else:
                    clean_hypotheses.append(h)
            results["previous_hypotheses"] = clean_hypotheses
            logger.info(f"Added {len(clean_hypotheses)} previous hypotheses to Claude reasoning")

        # Add cumulative insights from skip-testing cycles for cross-cycle synthesis
        cumulative_insights = diagnosis_input.get("cumulative_insights", [])
        if cumulative_insights:
            # Build a structured summary for AI consumption
            insights_summary = []
            for ins in cumulative_insights:
                insights_summary.append({
                    'cycle': ins.get('cycle'),
                    'hypothesis': ins.get('hypothesis_name'),
                    'supported': ins.get('hypothesis_supported'),
                    'confidence': ins.get('confidence'),
                    'parameters_tested': ins.get('parameters_tested', []),
                    'key_insights': ins.get('key_insights', ''),
                })
            results["cumulative_skip_testing_insights"] = {
                'total_cycles': len(cumulative_insights),
                'insights': insights_summary,
                'instruction': (
                    "IMPORTANT: These are accumulated findings from previous skip-testing cycles. "
                    "Build on these insights rather than repeating the same analyses. "
                    "Identify patterns across cycles, refine hypotheses based on what was "
                    "supported/rejected, and propose NEW directions not yet explored."
                )
            }
            logger.info(f"Added {len(cumulative_insights)} cumulative insights to Claude reasoning")

        # Add comparative analysis to results for AI reasoning
        comparative_analysis = diagnosis_input.get("comparative_analysis")
        if comparative_analysis:
            results["comparative_analysis"] = comparative_analysis
            logger.info("Added comparative case analysis to Claude reasoning")

        # Add evidence ledger context for focused hypothesis-driven diagnosis (Iter 2+)
        evidence_ledger_ctx = diagnosis_input.get("evidence_ledger_context")
        if evidence_ledger_ctx:
            results["evidence_ledger_context"] = evidence_ledger_ctx
            logger.info("Added evidence ledger context to Claude reasoning")

        # Add previous phase log (full Markdown from Phase 2 or previous Phase 3)
        previous_phase_log = diagnosis_input.get("previous_phase_log")
        if previous_phase_log:
            results["previous_phase_log"] = previous_phase_log
            logger.info(f"Added previous phase log ({len(previous_phase_log)} chars) to Claude reasoning")

        # Add previous phase AI insights so diagnosis builds on earlier analysis
        prior_insights = []
        # Screening AI analysis (Phase 2)
        screening_ai = screening_data.get("ai_analysis", "")
        if screening_ai:
            prior_insights.append(
                f"### Phase 2 Screening Analysis\n\n{screening_ai}"
            )
        # Exploration AI analysis (Phase 1) - if stored
        exploration_ai = (exploration_data or {}).get("ai_analysis", "")
        if exploration_ai:
            prior_insights.append(
                f"### Phase 1 Exploration Analysis\n\n{exploration_ai}"
            )
        if prior_insights:
            results["previous_phase_insights"] = (
                "## Previous Phase AI Insights\n\n"
                "IMPORTANT: The following insights were generated by earlier phases. "
                "Build on these observations — do NOT ignore or contradict them without "
                "explicit evidence.\n\n"
                + "\n\n".join(prior_insights)
            )
            logger.info(f"Added {len(prior_insights)} previous phase insights to Claude reasoning")

        # Get diagnostic images for multimodal analysis
        diagnostic_images = diagnosis_input.get("diagnostic_images", [])

        diagnosis = reasoning_module.diagnose(
            results=results,
            targets=diagnosis_input["targets"],
            sensitivity_rankings=diagnosis_input["sensitivity_rankings"],
            iteration=diagnosis_input["iteration"],
            diagnostic_images=diagnostic_images if diagnostic_images else None
        )
        return asdict(diagnosis) if hasattr(diagnosis, '__dict__') else diagnosis
    except Exception as e:
        logger.error(f"Claude diagnosis failed: {e}")
        return diagnose_rule_based(diagnosis_input)


def diagnose_rule_based(diagnosis_input: Dict) -> Dict:
    """Honest fallback when AI reasoning is unavailable.

    Returns a placeholder diagnosis that does NOT invent mechanisms or
    recommend parameters. Mechanistic root-cause analysis requires a working
    AI provider — operators should rerun with one configured.

    Args:
        diagnosis_input: Dict with iteration and other context.

    Returns:
        Diagnosis dict with failing_targets, likely_causes, etc.
    """
    logger.warning(
        "AI reasoning unavailable — returning placeholder diagnosis with "
        "no mechanisms or parameter recommendations. Check earlier log lines "
        "for 'Claude diagnosis failed' or reasoning module init errors."
    )

    # Extract real failing target names from input if available
    failing_targets: List[str] = []
    targets = diagnosis_input.get("targets") or {}
    if isinstance(targets, dict):
        for k, v in targets.items():
            if isinstance(v, dict):
                for organ in v.keys():
                    failing_targets.append(f"{k}_{organ}")
            else:
                failing_targets.append(str(k))

    return {
        "iteration": diagnosis_input.get("iteration"),
        "failing_targets": failing_targets,
        "likely_causes": [
            "AI reasoning unavailable — no automated diagnosis performed. "
            "Rerun orchestrator with a working AI provider (verify "
            "A2MC_AI_PROVIDER and the corresponding API key are set) for "
            "mechanistic root-cause analysis."
        ],
        "parameter_recommendations": [],
        "cross_pft_conflicts": [],
        "confidence": 0.0,
        "reasoning": (
            "Placeholder fallback: AI reasoning module is unavailable or its "
            "diagnose() call raised an exception. This fallback intentionally "
            "does not invent mechanisms or parameter directions. Search the "
            "orchestrator run log for 'Claude diagnosis failed' to identify "
            "the underlying cause."
        )
    }
