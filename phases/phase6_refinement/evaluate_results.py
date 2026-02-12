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
                    experiment_id=exp.get("name", "unknown"),
                    base_case=exp.get("base_case", "unknown"),
                    modifications=exp.get("modifications", []),
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
