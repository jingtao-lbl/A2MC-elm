"""
Phase 6: Refinement

Evaluate experiment results against hypotheses.
Extract lessons and update adaptive memory.
Assess convergence and decide next iteration.
"""

from phases.phase6_refinement.evaluate_results import (
    evaluate_experiments,
    classify_outcome,
    determine_refinement_action,
)

__all__ = [
    'evaluate_experiments',
    'classify_outcome',
    'determine_refinement_action',
]
