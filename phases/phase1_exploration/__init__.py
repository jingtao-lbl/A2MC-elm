"""
Phase 1: Exploration

Run sensitivity ensemble on HPC (NERSC Perlmutter).
Create cases, submit jobs, monitor completion.

High-Level API (for orchestrator):
    from phases.phase1_exploration import (
        analyze_existing_ensemble,
        run_monthly_extraction,
        run_y_matrix_extraction,
        run_morris_sensitivity_analysis,
        build_sensitivity_summary,
    )
"""

from .analyze_ensemble import (
    analyze_existing_ensemble,
    run_monthly_extraction,
    run_y_matrix_extraction,
    run_morris_sensitivity_analysis,
    build_sensitivity_summary,
)

__all__ = [
    'analyze_existing_ensemble',
    'run_monthly_extraction',
    'run_y_matrix_extraction',
    'run_morris_sensitivity_analysis',
    'build_sensitivity_summary',
]
