"""
Phase 2: Screening

Rank ensemble members against validation targets.
Identify top parameter sets and analyze error patterns.

Scripts:
    screen_ensemble.py - Main screening workflow
    compare_biomass_topcases.py - Compare top cases against observations
    plot_screening.py - Generic ensemble biomass visualization

High-Level API:
    from phases.phase2_screening import (
        screen_ensemble, ScreeningConfig, ScreeningResult,
        plot_ensemble_biomass, plot_ensemble_biomass_from_dir,
    )
"""

# Screening
from .screen_ensemble import (
    screen_ensemble,
    ScreeningConfig,
    ScreeningResult,
    load_kougarok_targets,
)

# Ensemble visualization
from .plot_screening import (
    plot_ensemble_biomass,
    plot_ensemble_biomass_from_dir,
    rank_cases_by_nrmse,
)

__all__ = [
    'screen_ensemble',
    'ScreeningConfig',
    'ScreeningResult',
    'load_kougarok_targets',
    'plot_ensemble_biomass',
    'plot_ensemble_biomass_from_dir',
    'rank_cases_by_nrmse',
]
