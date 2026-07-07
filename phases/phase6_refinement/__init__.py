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
    generate_comparison_plot,
    all_experiments_unreliable,
)

# Plotting requires matplotlib/numpy — lazy import to avoid breaking
# the package on systems without these dependencies (e.g., local dev)
try:
    from phases.phase6_refinement.plot_experiment_comparison import (
        plot_experiment_comparison,
    )
except ImportError:
    plot_experiment_comparison = None

__all__ = [
    'evaluate_experiments',
    'classify_outcome',
    'determine_refinement_action',
    'generate_comparison_plot',
    'all_experiments_unreliable',
    'plot_experiment_comparison',
]
