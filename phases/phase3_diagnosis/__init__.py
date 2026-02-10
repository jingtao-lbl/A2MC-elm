"""
Phase 3: Diagnosis

AI-driven root cause analysis of model-data mismatch.
Provides diagnostic tools for:
- Parameter analysis (reading, edge detection, comparison)
- PFT limitation diagnosis (allocation, nutrients, competition)
- Mortality analysis (component breakdown, event detection)
- Nutrient pool dynamics (depletion, uptake vs demand)
- Nutrient mass balance (full N/P budget closure, PFT competition)
- Vegetation collapse detection ("Perfect Storm" patterns)
- Target comparison (simulated vs observed)
- Hypothesis testing (structured hypothesis evaluation)
- Carbon balance analysis (GPP vs MR bottleneck detection)

These tools are designed to be called by the orchestrator during
diagnosis phase to provide actual data to the AI reasoning system.

High-Level API (for orchestrator):
    from phases.phase3_diagnosis import run_diagnosis, DiagnosisConfig, DiagnosisResult
    result = run_diagnosis(screening_data, config)

Low-Level API (for custom analysis):
    from phases.phase3_diagnosis import (
        read_case_parameters,
        check_parameters_at_edge,
        run_pft_diagnosis,
        extract_mortality_timeseries,
        analyze_nutrient_depletion,
        detect_vegetation_collapse,
        compare_biomass_targets,
        test_hypotheses,
        analyze_carbon_balance,
        extract_nutrient_budget,
        calculate_budget_closure,
        analyze_pft_competition
    )
"""

# High-level API (for orchestrator)
from .run_diagnosis import (
    run_diagnosis,
    run_diagnosis_for_orchestrator,
    DiagnosisConfig,
    DiagnosisResult
)

# Parameter reading and analysis
from .read_case_parameters import (
    read_case_parameters,
    read_parameter_file,
    get_parameter_for_case,
    get_parameters_with_bounds,
    load_param_names,
    load_param_bounds
)

# Edge parameter detection (parameters at Morris bounds)
from .check_edge_parameters import (
    check_parameters_at_edge,
    categorize_edge_parameters,
    get_edge_summary_for_ai,
    identify_redesign_candidates
)

# Case parameter comparison
from .compare_case_parameters import (
    compare_cases,
    get_largest_differences,
    get_comparison_summary_for_ai,
    compare_multiple_cases,
    find_consistent_differences
)

# PFT limitation diagnosis
from .diagnose_pft_limitations import (
    analyze_allocation_dynamics,
    analyze_nutrient_limitation,
    analyze_light_competition,
    analyze_allocation_rates,
    run_pft_diagnosis,
    get_diagnosis_summary_for_ai
)

# Mortality analysis
from .analyze_mortality import (
    extract_mortality_timeseries,
    detect_mortality_events,
    diagnose_mortality_causes,
    get_mortality_summary_for_ai
)

# Nutrient pool analysis
from .analyze_nutrient_pools import (
    extract_p_pools,
    extract_n_pools,
    analyze_nutrient_depletion,
    compare_uptake_vs_demand,
    get_nutrient_summary_for_ai
)

# Vegetation collapse detection
from .detect_collapse import (
    detect_vegetation_collapse,
    extract_vegc_timeseries,
    analyze_collapse_causes,
    detect_perfect_storm_pattern,
    get_collapse_summary_for_ai
)

# Target comparison
from .compare_targets import (
    compare_biomass_targets,
    calculate_target_metrics,
    extract_target_values,
    load_targets_from_file,
    get_target_summary_for_ai
)

# Hypothesis testing framework
from .test_hypothesis_framework import (
    test_hypotheses,
    test_single_hypothesis,
    create_hypothesis,
    get_default_hypotheses,
    get_hypothesis_summary_for_ai,
    Hypothesis,
    HypothesisResult,
    HypothesisTestResults,
    results_to_dict as hypothesis_results_to_dict,
    plot_hypothesis_diagnostics
)

# Carbon balance analysis
from .analyze_carbon_balance import (
    analyze_carbon_balance,
    detect_carbon_bottleneck,
    calculate_cumulative_fluxes,
    detect_deficit_periods,
    get_carbon_summary_for_ai,
    CarbonBalanceResults,
    DeficitPeriod,
    results_to_dict as carbon_results_to_dict,
    plot_carbon_balance
)

# Nutrient mass balance analysis
from .analyze_nutrient_balance import (
    extract_nutrient_budget,
    calculate_budget_closure,
    analyze_pft_competition,
    identify_nutrient_sinks,
    get_balance_summary_for_ai,
    NutrientBudget,
    BudgetClosure,
    PFTCompetition,
    NutrientSinks,
    results_to_dict as nutrient_balance_results_to_dict,
)

__all__ = [
    # High-level API
    'run_diagnosis',
    'run_diagnosis_for_orchestrator',
    'DiagnosisConfig',
    'DiagnosisResult',

    # Parameter reading
    'read_case_parameters',
    'read_parameter_file',
    'get_parameter_for_case',
    'get_parameters_with_bounds',
    'load_param_names',
    'load_param_bounds',

    # Edge parameters
    'check_parameters_at_edge',
    'categorize_edge_parameters',
    'get_edge_summary_for_ai',
    'identify_redesign_candidates',

    # Case comparison
    'compare_cases',
    'get_largest_differences',
    'get_comparison_summary_for_ai',
    'compare_multiple_cases',
    'find_consistent_differences',

    # PFT diagnosis
    'analyze_allocation_dynamics',
    'analyze_nutrient_limitation',
    'analyze_light_competition',
    'analyze_allocation_rates',
    'run_pft_diagnosis',
    'get_diagnosis_summary_for_ai',

    # Mortality
    'extract_mortality_timeseries',
    'detect_mortality_events',
    'diagnose_mortality_causes',
    'get_mortality_summary_for_ai',

    # Nutrient pools
    'extract_p_pools',
    'extract_n_pools',
    'analyze_nutrient_depletion',
    'compare_uptake_vs_demand',
    'get_nutrient_summary_for_ai',

    # Collapse detection
    'detect_vegetation_collapse',
    'extract_vegc_timeseries',
    'analyze_collapse_causes',
    'detect_perfect_storm_pattern',
    'get_collapse_summary_for_ai',

    # Target comparison
    'compare_biomass_targets',
    'calculate_target_metrics',
    'extract_target_values',
    'load_targets_from_file',
    'get_target_summary_for_ai',

    # Hypothesis testing
    'test_hypotheses',
    'test_single_hypothesis',
    'create_hypothesis',
    'get_default_hypotheses',
    'get_hypothesis_summary_for_ai',
    'Hypothesis',
    'HypothesisResult',
    'HypothesisTestResults',
    'hypothesis_results_to_dict',
    'plot_hypothesis_diagnostics',

    # Carbon balance
    'analyze_carbon_balance',
    'detect_carbon_bottleneck',
    'calculate_cumulative_fluxes',
    'detect_deficit_periods',
    'get_carbon_summary_for_ai',
    'CarbonBalanceResults',
    'DeficitPeriod',
    'carbon_results_to_dict',
    'plot_carbon_balance',

    # Nutrient mass balance
    'extract_nutrient_budget',
    'calculate_budget_closure',
    'analyze_pft_competition',
    'identify_nutrient_sinks',
    'get_balance_summary_for_ai',
    'NutrientBudget',
    'BudgetClosure',
    'PFTCompetition',
    'NutrientSinks',
    'nutrient_balance_results_to_dict',
]
