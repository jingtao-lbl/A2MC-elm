#!/usr/bin/env python3
"""
Phase 6: Evaluate Experiment Results

Evaluate experiments against hypotheses, extract lessons, and determine
next action. This module was extracted from orchestrator.py to keep
phase-specific evaluation logic in the phase folder.

The orchestrator retains loop control (phase transitions, counter updates,
convergence decisions).

Author: Jing Tao with Claude
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


def classify_outcome(targets_met: int, total_targets: int) -> str:
    """Classify experiment outcome for memory recording."""
    if targets_met >= total_targets:
        return "SUCCESS"
    elif targets_met >= total_targets * 0.75:
        return "PARTIAL_SUCCESS"
    elif targets_met <= total_targets * 0.25:
        return "FAILED"
    else:
        return "MARGINAL"


def evaluate_experiments(
    experiments: List[Dict],
    total_targets: int = 6,
    reasoning_module: Optional[Any] = None,
    memory_manager: Optional[Any] = None,
    auto_learn: bool = True
) -> Dict:
    """
    Evaluate experiment results and extract lessons.

    Args:
        experiments: List of experiment dicts with 'results' and 'name'
        total_targets: Total number of validation targets
        reasoning_module: ReasoningModule for lesson extraction (optional)
        memory_manager: MemoryManager for recording outcomes (optional)
        auto_learn: Whether to auto-extract lessons

    Returns:
        Dict with:
            - best_experiment: Dict or None
            - best_targets_met: int
            - total_targets: int
            - outcomes: List of per-experiment outcomes
    """
    latest_experiments = [e for e in experiments if e.get("status") != "skipped"]

    if not latest_experiments:
        logger.warning("No experiments to evaluate!")
        return {
            'best_experiment': None,
            'best_targets_met': 0,
            'total_targets': total_targets,
            'outcomes': [],
            'no_experiments': True
        }

    best_exp = None
    best_targets_met = 0
    outcomes = []

    for exp in latest_experiments:
        results = exp.get("results", {})
        targets_met = results.get("targets_met", 0)
        outcome = classify_outcome(targets_met, total_targets)

        logger.info(f"  {exp['name']}: {targets_met}/{total_targets} targets met")

        exp_outcome = {
            'experiment_name': exp.get('name', 'unknown'),
            'targets_met': targets_met,
            'outcome': outcome
        }

        # Extract lesson via reasoning module
        if reasoning_module and auto_learn:
            try:
                lesson = reasoning_module.extract_lesson(
                    experiment=exp,
                    results=results,
                    outcome=outcome
                )
                if lesson:
                    logger.info(f"    Lesson extracted: {lesson.get('lesson', 'N/A')[:50]}...")
                    exp_outcome['lesson'] = lesson
            except Exception as e:
                logger.debug(f"Could not extract lesson: {e}")

        # Update experiment outcome in memory
        if memory_manager and auto_learn:
            try:
                memory_manager.record_experiment(
                    experiment=exp,
                    results=results,
                    outcome=outcome
                )
            except Exception as e:
                logger.debug(f"Could not update experiment in memory: {e}")

        outcomes.append(exp_outcome)

        if targets_met > best_targets_met:
            best_targets_met = targets_met
            best_exp = exp

    return {
        'best_experiment': best_exp,
        'best_targets_met': best_targets_met,
        'total_targets': total_targets,
        'outcomes': outcomes,
        'no_experiments': False
    }


def determine_refinement_action(
    best_targets_met: int,
    total_targets: int,
    prev_best_targets: int
) -> Dict:
    """
    Determine the next action based on refinement results.

    Args:
        best_targets_met: Targets met by best experiment
        total_targets: Total target count
        prev_best_targets: Previous best experiment targets met

    Returns:
        Dict with 'action', 'hypothesis_status', 'description'
    """
    if best_targets_met >= total_targets:
        return {
            'action': 'converge',
            'hypothesis_status': 'CONFIRMED',
            'description': f'CONVERGE (all targets met!)'
        }
    elif best_targets_met > prev_best_targets:
        return {
            'action': 'iterate',
            'hypothesis_status': 'PARTIAL_SUCCESS',
            'description': f'ITERATE (progress: {best_targets_met}/{total_targets})'
        }
    else:
        return {
            'action': 'revise_hypothesis',
            'hypothesis_status': 'FAILED',
            'description': f'REVISE HYPOTHESIS (no improvement: {best_targets_met}/{total_targets})'
        }


def generate_comparison_plot(
    experiments: List[Dict],
    screening_data: Dict,
    iteration: int,
    pft_ids: List[int] = None,
) -> Optional[str]:
    """Generate baseline vs experiment comparison plot.

    Args:
        experiments: List of experiment dicts (must have case_name, iteration).
        screening_data: Screening data with best_case info.
        iteration: Current iteration number.
        pft_ids: PFT IDs (default: [7, 9, 10]).

    Returns:
        Path to saved figure, or None if generation failed.
    """
    import os
    from pathlib import Path

    try:
        from phases.phase6_refinement.plot_experiment_comparison import (
            plot_experiment_comparison
        )
        from tools.config import config as a2mc_config
    except ImportError as e:
        logger.warning(f"Cannot generate comparison plot (missing dependency): {e}")
        return None

    # Get baseline case ID
    baseline_id = str(screening_data.get('best_case', {}).get('case_id', ''))
    if not baseline_id:
        logger.info("No baseline case ID in screening data; skipping comparison plot")
        return None

    # Get experiment case names for current iteration
    exp_case_names = [
        exp["case_name"]
        for exp in experiments
        if exp.get("iteration") == iteration and exp.get("case_name")
    ]
    if not exp_case_names:
        logger.info("No experiment case names found; skipping comparison plot")
        return None

    # Load targets
    try:
        from phases.phase2_screening.screen_ensemble import load_kougarok_targets
        raw_targets = load_kougarok_targets()
        targets = {
            name: {'observed': t.observed, 'uncertainty': t.uncertainty}
            for name, t in raw_targets.items()
        }
    except Exception:
        logger.warning("Could not load targets for comparison plot")
        return None

    # Output path
    fig_dir = a2mc_config.phase_results_dir("phase6_refinement")
    fig_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(fig_dir / f"experiment_comparison_{baseline_id}.png")

    logger.info(f"Generating baseline vs experiment comparison plot...")
    logger.info(f"  Baseline: #{baseline_id}, Experiments: {len(exp_case_names)}")

    try:
        fig_path = plot_experiment_comparison(
            data_dir=str(a2mc_config.EXTRACTED_DATA),
            baseline_case=baseline_id,
            experiment_cases=exp_case_names,
            targets=targets,
            pft_ids=pft_ids or [7, 9, 10],
            output_path=output_path,
        )
        if fig_path:
            logger.info(f"  Comparison plot: {fig_path}")
        return fig_path
    except Exception as e:
        logger.warning(f"Comparison plot generation failed: {e}")
        return None
