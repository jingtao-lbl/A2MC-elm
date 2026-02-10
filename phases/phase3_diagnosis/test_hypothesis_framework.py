#!/usr/bin/env python3
"""
Test Hypothesis Framework for A2MC Phase 3 Diagnosis

Provides structured hypothesis testing with quantified metrics.
Supports Phase 4 "skip testing" path by testing hypotheses against
existing ensemble data.

Usage (Python API):
    from phases.phase3_diagnosis import (
        test_hypotheses,
        create_hypothesis,
        get_hypothesis_summary_for_ai
    )

    # Define hypotheses
    hypotheses = [
        create_hypothesis(
            id="H1",
            name="Low Storage C",
            description="Insufficient storage at cold transition to support leaf flush",
            mechanism="Storage_Allocation",
            test_metric="storage_deficit",
            threshold=50.0,
            threshold_type="greater_than"
        ),
        create_hypothesis(
            id="H2",
            name="High Respiration Cost",
            description="Respiration consumes too much NPP",
            mechanism="Autotrophic_Respiration",
            test_metric="total_resp_fraction",
            threshold=0.6,
            threshold_type="greater_than"
        )
    ]

    # Test against data
    results = test_hypotheses(
        data=cnp_diagnostics_df,
        hypotheses=hypotheses,
        focus_period=(100, 180),  # DOY range
        pft_id=10
    )

Usage (CLI):
    python -m phases.phase3_diagnosis.test_hypothesis_framework \\
        --data cnp_diagnostics.csv \\
        --hypotheses hypothesis_config.yaml \\
        --pft 10 \\
        --focus-doy 100-180

Author: Jing Tao with Claude
Created: February 2026
"""

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Hypothesis:
    """Represents a testable hypothesis about model behavior."""
    id: str
    name: str
    description: str
    mechanism: str  # FATES mechanism (e.g., PID_Controller, Storage_Allocation)
    test_metric: str  # Metric to compute (e.g., storage_deficit, resp_fraction)
    threshold: float  # Value for confirmation/rejection
    threshold_type: str = "greater_than"  # greater_than, less_than, between
    threshold_upper: Optional[float] = None  # For "between" type
    related_params: list = field(default_factory=list)  # Parameters that might affect this
    affected_targets: list = field(default_factory=list)  # Targets this explains


@dataclass
class HypothesisResult:
    """Result of testing a single hypothesis."""
    hypothesis: Hypothesis
    supported: bool
    confidence: float
    metric_value: float
    evidence: str
    severity: str  # CONFIRMED, PARTIAL, REJECTED
    details: dict = field(default_factory=dict)


@dataclass
class HypothesisTestResults:
    """Complete results from testing multiple hypotheses."""
    results: list  # List of HypothesisResult
    summary: dict
    primary_hypothesis: Optional[str] = None
    recommendations: list = field(default_factory=list)
    visualization_path: Optional[str] = None


# =============================================================================
# HYPOTHESIS CREATION
# =============================================================================

def create_hypothesis(
    id: str,
    name: str,
    description: str,
    mechanism: str,
    test_metric: str,
    threshold: float,
    threshold_type: str = "greater_than",
    threshold_upper: Optional[float] = None,
    related_params: Optional[list] = None,
    affected_targets: Optional[list] = None
) -> Hypothesis:
    """
    Create a hypothesis object for testing.

    Parameters
    ----------
    id : str
        Unique identifier (e.g., "H1", "H2")
    name : str
        Short descriptive name
    description : str
        Full description of the hypothesis
    mechanism : str
        FATES mechanism being tested (e.g., PID_Controller, Storage_Allocation,
        ECA_Competition, Carbon_Starvation, Root_Distribution)
    test_metric : str
        Metric to compute. Supported metrics:
        - storage_deficit: (storage_target - actual_storage)
        - storage_ratio: actual_storage / storage_target
        - total_resp_fraction: AUTORESP / GPP
        - maint_resp_fraction: MAINT_RESP / GPP
        - growth_resp_fraction: GROWTH_RESP / GPP
        - n_ratio: N_available / N_demand
        - n_deficit: N_demand - N_available
        - alloc_ratio: FROOT_ALLOC / LEAF_ALLOC
        - storage_alloc_fraction: STORE_ALLOC / NPP
        - l2fr: L2FR ratio
    threshold : float
        Value for confirmation/rejection
    threshold_type : str
        How to compare: "greater_than", "less_than", "between"
    threshold_upper : float, optional
        Upper bound for "between" comparison
    related_params : list, optional
        Parameters that might affect this mechanism
    affected_targets : list, optional
        Validation targets this hypothesis explains

    Returns
    -------
    Hypothesis
        The hypothesis object ready for testing
    """
    return Hypothesis(
        id=id,
        name=name,
        description=description,
        mechanism=mechanism,
        test_metric=test_metric,
        threshold=threshold,
        threshold_type=threshold_type,
        threshold_upper=threshold_upper,
        related_params=related_params or [],
        affected_targets=affected_targets or []
    )


def get_default_hypotheses(pft_id: int = 10) -> list:
    """
    Return a set of common hypotheses for CNP allocation issues.

    These are the typical hypotheses for Arctic graminoid/shrub calibration
    issues seen at Kougarok. Customize for your site.

    Parameters
    ----------
    pft_id : int
        PFT ID to include in parameter names

    Returns
    -------
    list
        List of Hypothesis objects
    """
    return [
        create_hypothesis(
            id="H1",
            name="Low Storage C",
            description="Insufficient storage C at cold transition to support instant leaf flush",
            mechanism="Storage_Allocation",
            test_metric="storage_deficit",
            threshold=50.0,
            threshold_type="greater_than",
            related_params=[f"alloc_storage_cushion_{pft_id}"],
            affected_targets=[f"leaf_pft{pft_id}", f"froot_pft{pft_id}"]
        ),
        create_hypothesis(
            id="H2",
            name="High Respiration Cost",
            description="Respiration consumes too much GPP, leaving insufficient NPP for growth",
            mechanism="Autotrophic_Respiration",
            test_metric="total_resp_fraction",
            threshold=0.6,
            threshold_type="greater_than",
            related_params=["maintresp_nonleaf_baserate"],
            affected_targets=[f"abg_pft{pft_id}"]
        ),
        create_hypothesis(
            id="H3",
            name="N Limitation",
            description="High N demand prevents leaf growth",
            mechanism="ECA_Competition",
            test_metric="n_ratio",
            threshold=0.5,
            threshold_type="less_than",
            related_params=[f"stoich_nitr_leaf_{pft_id}", f"cnp_vmax_no3_{pft_id}"],
            affected_targets=[f"leaf_pft{pft_id}"]
        ),
        create_hypothesis(
            id="H4",
            name="Root Over-Allocation",
            description="PID controller over-allocates to roots at expense of leaves",
            mechanism="PID_Controller",
            test_metric="alloc_ratio",
            threshold=5.0,
            threshold_type="greater_than",
            related_params=[f"cnp_pid_kp_{pft_id}"],
            affected_targets=[f"leaf_pft{pft_id}", f"froot_pft{pft_id}"]
        ),
        create_hypothesis(
            id="H5",
            name="Storage Dominates Allocation",
            description="Storage replenishment consumes most NPP, acting as growth gatekeeper",
            mechanism="Storage_Allocation",
            test_metric="storage_alloc_fraction",
            threshold=0.6,
            threshold_type="greater_than",
            related_params=[f"alloc_storage_cushion_{pft_id}"],
            affected_targets=[f"leaf_pft{pft_id}", f"froot_pft{pft_id}", f"abg_pft{pft_id}"]
        )
    ]


# =============================================================================
# METRIC CALCULATION
# =============================================================================

def calculate_metric(
    data: pd.DataFrame,
    metric: str,
    pft_id: int = 10,
    params: Optional[dict] = None
) -> pd.Series:
    """
    Calculate a diagnostic metric from CNP diagnostics data.

    Parameters
    ----------
    data : pd.DataFrame
        CNP diagnostics data with columns like FATES_LEAFC_PF_PFT10, FATES_GPP, etc.
    metric : str
        Metric to calculate (see create_hypothesis docstring for list)
    pft_id : int
        PFT ID for PFT-specific variables
    params : dict, optional
        Parameter values (e.g., {'alloc_storage_cushion': 1.2})

    Returns
    -------
    pd.Series
        Calculated metric values
    """
    params = params or {}

    # Get column suffixes
    pft_suffix = f"_PFT{pft_id}"

    # Helper to get column with fallback
    def get_col(base, pft_specific=False):
        if pft_specific:
            col = f"{base}{pft_suffix}"
            if col in data.columns:
                return data[col]
            # Try without PFT suffix
            if base in data.columns:
                return data[base]
        else:
            if base in data.columns:
                return data[base]
        raise KeyError(f"Column {base} not found in data")

    # Calculate metrics
    if metric == "storage_deficit":
        storage_cushion = params.get("alloc_storage_cushion", 1.2)
        leaf_c = get_col("FATES_LEAFC_PF", pft_specific=True)
        store_c = get_col("FATES_STOREC_PF", pft_specific=True)
        storage_target = leaf_c * storage_cushion
        return np.maximum(0, storage_target - store_c)

    elif metric == "storage_ratio":
        storage_cushion = params.get("alloc_storage_cushion", 1.2)
        leaf_c = get_col("FATES_LEAFC_PF", pft_specific=True)
        store_c = get_col("FATES_STOREC_PF", pft_specific=True)
        storage_target = leaf_c * storage_cushion
        return store_c / (storage_target + 1e-10)

    elif metric == "total_resp_fraction":
        autoresp = get_col("FATES_AUTORESP")
        gpp = get_col("FATES_GPP")
        return autoresp / (gpp + 1e-10)

    elif metric == "maint_resp_fraction":
        maint_resp = get_col("FATES_MAINT_RESP")
        gpp = get_col("FATES_GPP")
        return maint_resp / (gpp + 1e-10)

    elif metric == "growth_resp_fraction":
        growth_resp = get_col("FATES_GROWTH_RESP")
        gpp = get_col("FATES_GPP")
        return growth_resp / (gpp + 1e-10)

    elif metric == "n_ratio":
        stoich_n = params.get("stoich_nitr_leaf", 0.02)
        leaf_c = get_col("FATES_LEAFC_PF", pft_specific=True)
        store_n = get_col("FATES_STOREN")
        n_demand = leaf_c * stoich_n * 2  # For doubling
        return store_n / (n_demand + 1e-10)

    elif metric == "n_deficit":
        stoich_n = params.get("stoich_nitr_leaf", 0.02)
        leaf_c = get_col("FATES_LEAFC_PF", pft_specific=True)
        store_n = get_col("FATES_STOREN")
        n_demand = leaf_c * stoich_n * 2
        return np.maximum(0, n_demand - store_n)

    elif metric == "alloc_ratio":
        froot_alloc = get_col("FATES_FROOT_ALLOC")
        leaf_alloc = get_col("FATES_LEAF_ALLOC")
        return froot_alloc / (leaf_alloc + 1e-10)

    elif metric == "storage_alloc_fraction":
        store_alloc = get_col("FATES_STORE_ALLOC")
        npp = get_col("FATES_NPP")
        return store_alloc / (npp + 1e-10)

    elif metric == "l2fr":
        return get_col("FATES_L2FR")

    else:
        raise ValueError(f"Unknown metric: {metric}")


def evaluate_threshold(
    value: float,
    threshold: float,
    threshold_type: str,
    threshold_upper: Optional[float] = None
) -> tuple:
    """
    Evaluate if a value meets a threshold condition.

    Returns
    -------
    tuple
        (meets_threshold, severity)
        severity is one of: CONFIRMED, PARTIAL, REJECTED
    """
    if threshold_type == "greater_than":
        if value > threshold * 1.5:
            return True, "CONFIRMED"
        elif value > threshold:
            return True, "PARTIAL"
        elif value > threshold * 0.8:
            return False, "PARTIAL"
        else:
            return False, "REJECTED"

    elif threshold_type == "less_than":
        if value < threshold * 0.5:
            return True, "CONFIRMED"
        elif value < threshold:
            return True, "PARTIAL"
        elif value < threshold * 1.2:
            return False, "PARTIAL"
        else:
            return False, "REJECTED"

    elif threshold_type == "between":
        if threshold_upper is None:
            raise ValueError("threshold_upper required for 'between' type")
        if threshold <= value <= threshold_upper:
            return True, "CONFIRMED"
        elif threshold * 0.8 <= value <= threshold_upper * 1.2:
            return False, "PARTIAL"
        else:
            return False, "REJECTED"

    else:
        raise ValueError(f"Unknown threshold_type: {threshold_type}")


# =============================================================================
# HYPOTHESIS TESTING
# =============================================================================

def test_single_hypothesis(
    data: pd.DataFrame,
    hypothesis: Hypothesis,
    focus_period: Optional[tuple] = None,
    pft_id: int = 10,
    params: Optional[dict] = None
) -> HypothesisResult:
    """
    Test a single hypothesis against the data.

    Parameters
    ----------
    data : pd.DataFrame
        CNP diagnostics data with 'doy' column
    hypothesis : Hypothesis
        The hypothesis to test
    focus_period : tuple, optional
        (start_doy, end_doy) to focus analysis
    pft_id : int
        PFT ID for PFT-specific calculations
    params : dict, optional
        Parameter values for metric calculation

    Returns
    -------
    HypothesisResult
        Test result with evidence
    """
    # Filter to focus period if specified
    if focus_period is not None:
        start_doy, end_doy = focus_period
        period_data = data[(data['doy'] >= start_doy) & (data['doy'] <= end_doy)]
    else:
        period_data = data

    # Calculate metric
    try:
        metric_series = calculate_metric(period_data, hypothesis.test_metric, pft_id, params)
        metric_value = float(metric_series.mean())
    except (KeyError, ValueError) as e:
        return HypothesisResult(
            hypothesis=hypothesis,
            supported=False,
            confidence=0.0,
            metric_value=np.nan,
            evidence=f"Could not calculate metric: {e}",
            severity="REJECTED",
            details={"error": str(e)}
        )

    # Evaluate threshold
    meets_threshold, severity = evaluate_threshold(
        metric_value,
        hypothesis.threshold,
        hypothesis.threshold_type,
        hypothesis.threshold_upper
    )

    # Calculate confidence based on how strongly threshold is met/not met
    if hypothesis.threshold_type == "greater_than":
        ratio = metric_value / hypothesis.threshold if hypothesis.threshold > 0 else 0
        if meets_threshold:
            confidence = min(0.95, 0.5 + 0.3 * (ratio - 1))
        else:
            confidence = max(0.05, 0.5 - 0.3 * (1 - ratio))
    elif hypothesis.threshold_type == "less_than":
        ratio = hypothesis.threshold / metric_value if metric_value > 0 else 0
        if meets_threshold:
            confidence = min(0.95, 0.5 + 0.3 * (ratio - 1))
        else:
            confidence = max(0.05, 0.5 - 0.3 * (1 - ratio))
    else:
        confidence = 0.7 if meets_threshold else 0.3

    # Generate evidence text
    evidence = _generate_evidence_text(
        hypothesis, metric_value, meets_threshold, severity, focus_period
    )

    # Additional details
    details = {
        "metric_mean": float(metric_value),
        "metric_std": float(metric_series.std()) if len(metric_series) > 1 else 0,
        "metric_min": float(metric_series.min()),
        "metric_max": float(metric_series.max()),
        "n_days": len(period_data),
        "threshold": hypothesis.threshold,
        "threshold_type": hypothesis.threshold_type
    }

    return HypothesisResult(
        hypothesis=hypothesis,
        supported=meets_threshold,
        confidence=confidence,
        metric_value=metric_value,
        evidence=evidence,
        severity=severity,
        details=details
    )


def _generate_evidence_text(
    hypothesis: Hypothesis,
    metric_value: float,
    meets_threshold: bool,
    severity: str,
    focus_period: Optional[tuple]
) -> str:
    """Generate human-readable evidence text."""
    period_text = f"DOY {focus_period[0]}-{focus_period[1]}" if focus_period else "full year"

    if hypothesis.threshold_type == "greater_than":
        compare = ">" if meets_threshold else "<"
        evidence = (
            f"{hypothesis.name}: Mean {hypothesis.test_metric} = {metric_value:.3f} "
            f"{compare} threshold {hypothesis.threshold:.3f} during {period_text}. "
        )
    elif hypothesis.threshold_type == "less_than":
        compare = "<" if meets_threshold else ">"
        evidence = (
            f"{hypothesis.name}: Mean {hypothesis.test_metric} = {metric_value:.3f} "
            f"{compare} threshold {hypothesis.threshold:.3f} during {period_text}. "
        )
    else:
        evidence = (
            f"{hypothesis.name}: Mean {hypothesis.test_metric} = {metric_value:.3f} "
            f"({'within' if meets_threshold else 'outside'} threshold range) during {period_text}. "
        )

    if severity == "CONFIRMED":
        evidence += f"→ {hypothesis.id} CONFIRMED: Strong evidence for {hypothesis.mechanism}."
    elif severity == "PARTIAL":
        if meets_threshold:
            evidence += f"→ {hypothesis.id} PARTIAL: Some evidence for {hypothesis.mechanism}."
        else:
            evidence += f"→ {hypothesis.id} PARTIAL: Weak evidence, borderline case."
    else:
        evidence += f"→ {hypothesis.id} REJECTED: {hypothesis.mechanism} unlikely to be the cause."

    return evidence


def test_hypotheses(
    data: pd.DataFrame,
    hypotheses: Optional[list] = None,
    focus_period: Optional[tuple] = None,
    pft_id: int = 10,
    params: Optional[dict] = None
) -> HypothesisTestResults:
    """
    Test multiple hypotheses against the data.

    This is the main entry point for hypothesis testing.

    Parameters
    ----------
    data : pd.DataFrame
        CNP diagnostics data with columns like FATES_LEAFC_PF_PFT10, FATES_GPP, etc.
        Must have a 'doy' column for day of year.
    hypotheses : list, optional
        List of Hypothesis objects to test. If None, uses get_default_hypotheses().
    focus_period : tuple, optional
        (start_doy, end_doy) to focus analysis (e.g., (100, 180) for spring)
    pft_id : int
        PFT ID for PFT-specific variables and default hypotheses
    params : dict, optional
        Parameter values (e.g., {'alloc_storage_cushion': 1.2})

    Returns
    -------
    HypothesisTestResults
        Complete test results with summary and recommendations

    Example
    -------
    >>> results = test_hypotheses(
    ...     data=cnp_df,
    ...     focus_period=(100, 180),
    ...     pft_id=10
    ... )
    >>> print(results.summary)
    >>> for r in results.results:
    ...     print(f"{r.hypothesis.id}: {r.severity} (confidence: {r.confidence:.2f})")
    """
    if hypotheses is None:
        hypotheses = get_default_hypotheses(pft_id)

    # Test each hypothesis
    results = []
    for h in hypotheses:
        result = test_single_hypothesis(data, h, focus_period, pft_id, params)
        results.append(result)

    # Find primary hypothesis (highest confidence confirmed)
    confirmed = [r for r in results if r.supported]
    if confirmed:
        primary = max(confirmed, key=lambda r: r.confidence)
        primary_id = primary.hypothesis.id
    else:
        primary_id = None

    # Generate summary
    summary = {
        "total_tested": len(results),
        "confirmed": sum(1 for r in results if r.severity == "CONFIRMED"),
        "partial": sum(1 for r in results if r.severity == "PARTIAL"),
        "rejected": sum(1 for r in results if r.severity == "REJECTED"),
        "primary_hypothesis": primary_id,
        "focus_period": focus_period,
        "pft_id": pft_id
    }

    # Generate recommendations
    recommendations = _generate_recommendations(results, primary_id)

    return HypothesisTestResults(
        results=results,
        summary=summary,
        primary_hypothesis=primary_id,
        recommendations=recommendations
    )


def _generate_recommendations(results: list, primary_id: Optional[str]) -> list:
    """Generate recommendations based on test results."""
    recommendations = []

    # Sort by confidence
    confirmed = sorted(
        [r for r in results if r.supported],
        key=lambda r: r.confidence,
        reverse=True
    )

    for r in confirmed:
        h = r.hypothesis
        if h.related_params:
            param_str = ", ".join(h.related_params)
            recommendations.append({
                "hypothesis": h.id,
                "action": f"Modify {param_str}",
                "mechanism": h.mechanism,
                "confidence": r.confidence,
                "priority": "high" if r.confidence > 0.7 else "medium"
            })

    # If no confirmed, suggest investigating rejected ones more
    if not confirmed:
        partial = [r for r in results if r.severity == "PARTIAL"]
        if partial:
            recommendations.append({
                "hypothesis": "general",
                "action": "Re-examine partial hypotheses with more data",
                "mechanism": "unknown",
                "confidence": 0.3,
                "priority": "medium"
            })

    return recommendations


# =============================================================================
# AI SUMMARY
# =============================================================================

def get_hypothesis_summary_for_ai(results: HypothesisTestResults) -> str:
    """
    Generate a summary string suitable for AI reasoning context.

    Parameters
    ----------
    results : HypothesisTestResults
        Results from test_hypotheses()

    Returns
    -------
    str
        Formatted summary for inclusion in AI prompts
    """
    lines = [
        "## Hypothesis Test Results",
        "",
        f"Period: DOY {results.summary['focus_period'][0]}-{results.summary['focus_period'][1]}"
            if results.summary.get('focus_period') else "Period: Full year",
        f"PFT: {results.summary['pft_id']}",
        "",
        "| Hypothesis | Name | Severity | Confidence | Metric Value |",
        "|------------|------|----------|------------|--------------|"
    ]

    for r in results.results:
        lines.append(
            f"| {r.hypothesis.id} | {r.hypothesis.name} | {r.severity} | "
            f"{r.confidence:.2f} | {r.metric_value:.3f} |"
        )

    lines.extend([
        "",
        "### Evidence Summary",
        ""
    ])

    for r in results.results:
        lines.append(f"- {r.evidence}")

    if results.primary_hypothesis:
        lines.extend([
            "",
            f"**Primary Hypothesis:** {results.primary_hypothesis}",
            ""
        ])

    if results.recommendations:
        lines.extend([
            "### Recommendations",
            ""
        ])
        for rec in results.recommendations:
            lines.append(
                f"- [{rec['priority'].upper()}] {rec['action']} "
                f"(based on {rec['hypothesis']}, confidence {rec['confidence']:.2f})"
            )

    return "\n".join(lines)


def results_to_dict(results: HypothesisTestResults) -> dict:
    """
    Convert results to a dictionary for JSON serialization.

    Parameters
    ----------
    results : HypothesisTestResults
        Results from test_hypotheses()

    Returns
    -------
    dict
        JSON-serializable dictionary
    """
    return {
        "summary": results.summary,
        "primary_hypothesis": results.primary_hypothesis,
        "results": [
            {
                "hypothesis_id": r.hypothesis.id,
                "hypothesis_name": r.hypothesis.name,
                "mechanism": r.hypothesis.mechanism,
                "supported": r.supported,
                "severity": r.severity,
                "confidence": r.confidence,
                "metric_value": r.metric_value,
                "evidence": r.evidence,
                "details": r.details
            }
            for r in results.results
        ],
        "recommendations": results.recommendations,
        "visualization_path": results.visualization_path
    }


# =============================================================================
# VISUALIZATION (optional)
# =============================================================================

def plot_hypothesis_diagnostics(
    data: pd.DataFrame,
    results: HypothesisTestResults,
    pft_id: int = 10,
    output_path: Optional[str] = None,
    cold_doy: Optional[float] = None,
    lai_doy: Optional[float] = None
) -> Optional[str]:
    """
    Create diagnostic visualization for hypothesis testing.

    Parameters
    ----------
    data : pd.DataFrame
        CNP diagnostics data
    results : HypothesisTestResults
        Test results
    pft_id : int
        PFT ID
    output_path : str, optional
        Path to save plot. If None, displays interactively.
    cold_doy : float, optional
        Cold status transition DOY (for annotation)
    lai_doy : float, optional
        LAI leaf-on DOY (for annotation)

    Returns
    -------
    str or None
        Path to saved figure, or None if displayed
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Warning: matplotlib not available for plotting")
        return None

    # Create 5-panel figure like original script
    fig, axes = plt.subplots(5, 1, figsize=(14, 16), sharex=True)
    fig.suptitle(f'Hypothesis Testing Diagnostics - PFT#{pft_id}', fontsize=14, fontweight='bold')

    # Plot 1: Storage C
    ax = axes[0]
    if 'FATES_STOREC_PF' in data.columns or f'FATES_STOREC_PF_PFT{pft_id}' in data.columns:
        store_col = f'FATES_STOREC_PF_PFT{pft_id}' if f'FATES_STOREC_PF_PFT{pft_id}' in data.columns else 'FATES_STOREC_PF'
        ax.plot(data['doy'], data[store_col], 'b-', label='Storage C', linewidth=2)
    ax.set_ylabel('Storage C\n(g C/m²)')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_title('H1: Storage C Status', fontweight='bold')

    # Plot 2: Respiration
    ax = axes[1]
    if 'FATES_GPP' in data.columns:
        ax.plot(data['doy'], data['FATES_GPP'], 'g-', label='GPP', linewidth=2)
    if 'FATES_NPP' in data.columns:
        ax.plot(data['doy'], data['FATES_NPP'], 'b-', label='NPP', linewidth=2)
    if 'FATES_MAINT_RESP' in data.columns:
        ax.plot(data['doy'], data['FATES_MAINT_RESP'], 'r-', label='Maint Resp', linewidth=1.5)
    ax.set_ylabel('C Fluxes\n(g C/m²/day)')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_title('H2: Respiration Costs', fontweight='bold')

    # Plot 3: N availability
    ax = axes[2]
    if 'FATES_STOREN' in data.columns:
        ax.plot(data['doy'], data['FATES_STOREN'], 'b-', label='N Available', linewidth=2)
    ax.set_ylabel('N Pools\n(g N/m²)')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_title('H3: N Limitation', fontweight='bold')

    # Plot 4: L2FR
    ax = axes[3]
    if 'FATES_L2FR' in data.columns:
        ax.plot(data['doy'], data['FATES_L2FR'], 'k-', label='L2FR', linewidth=2)
    ax.axhline(1.0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    ax.set_ylabel('L2FR Ratio')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_title('H4: Root Over-Allocation (PID)', fontweight='bold')
    ax.set_ylim(0, 10)

    # Plot 5: LAI and Allocation
    ax = axes[4]
    if 'FATES_LAI' in data.columns:
        ax.plot(data['doy'], data['FATES_LAI'], 'g-', label='LAI', linewidth=2)
    ax.set_xlabel('Day of Year')
    ax.set_ylabel('LAI (m²/m²)')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_title('LAI Response', fontweight='bold')

    # Add vertical lines for phenology markers
    for ax in axes:
        if cold_doy is not None:
            ax.axvline(cold_doy, color='green', linestyle=':', linewidth=2, alpha=0.7)
        if lai_doy is not None:
            ax.axvline(lai_doy, color='orange', linestyle=':', linewidth=2, alpha=0.7)

    plt.xlim(50, 250)
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        return output_path
    else:
        plt.show()
        return None


# =============================================================================
# CLI
# =============================================================================

def load_hypotheses_from_yaml(yaml_path: str) -> list:
    """Load hypothesis definitions from YAML file."""
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML required for loading hypothesis config")

    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    hypotheses = []
    for h_config in config.get("hypotheses", []):
        hypotheses.append(create_hypothesis(**h_config))

    return hypotheses


def main():
    parser = argparse.ArgumentParser(
        description="Test hypotheses against CNP diagnostics data"
    )
    parser.add_argument(
        "--data", required=True,
        help="Path to CNP diagnostics CSV file"
    )
    parser.add_argument(
        "--hypotheses",
        help="Path to hypothesis config YAML (optional, uses defaults if not provided)"
    )
    parser.add_argument(
        "--pft", type=int, default=10,
        help="PFT ID for analysis (default: 10)"
    )
    parser.add_argument(
        "--focus-doy",
        help="Focus period as 'start-end' (e.g., '100-180')"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file for results"
    )
    parser.add_argument(
        "--plot",
        help="Output path for diagnostic plot"
    )

    args = parser.parse_args()

    # Load data
    print(f"Loading data from {args.data}...")
    data = pd.read_csv(args.data)

    # Parse focus period
    focus_period = None
    if args.focus_doy:
        parts = args.focus_doy.split("-")
        focus_period = (int(parts[0]), int(parts[1]))

    # Load or create hypotheses
    if args.hypotheses:
        hypotheses = load_hypotheses_from_yaml(args.hypotheses)
    else:
        hypotheses = get_default_hypotheses(args.pft)

    # Test hypotheses
    print(f"Testing {len(hypotheses)} hypotheses...")
    results = test_hypotheses(
        data=data,
        hypotheses=hypotheses,
        focus_period=focus_period,
        pft_id=args.pft
    )

    # Print summary
    print("\n" + "="*80)
    print(get_hypothesis_summary_for_ai(results))
    print("="*80)

    # Save results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results_to_dict(results), f, indent=2)
        print(f"\nResults saved to {args.output}")

    # Create plot
    if args.plot:
        plot_path = plot_hypothesis_diagnostics(
            data=data,
            results=results,
            pft_id=args.pft,
            output_path=args.plot
        )
        if plot_path:
            print(f"Plot saved to {plot_path}")


if __name__ == "__main__":
    main()
