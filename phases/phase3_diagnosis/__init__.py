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
- Ensemble-level hypothesis tests (P limitation cascade, root turnover impact)

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

# Diagnostic plotting
from .plot_diagnostics import (
    plot_pft_diagnosis,
    plot_biomass_trajectories,
    plot_nutrient_limitation,
    plot_light_competition,
    plot_allocation_dynamics,
    plot_allocation_rates,
    plot_mortality_components,
    plot_p_mass_balance,
)

# Ensemble-level hypothesis tests (promoted from generated/)
from .test_p_limitation_cascade import (
    test_hypothesis as test_p_limitation_cascade,
)

from .test_root_turnover_impact import (
    test_hypothesis as test_root_turnover_impact,
)


def discover_ensemble_tests():
    """
    Auto-discover promoted ensemble test scripts in this directory.

    Scans for test_*.py files that define a test_hypothesis() function
    with the standard signature (param_matrix, y_outputs, screening_data, config).

    Returns:
        Dict mapping tool name to metadata:
        {
            'test_p_cascade': {
                'module': 'phases.phase3_diagnosis.test_p_cascade',
                'description': 'Test P limitation cascade ...',
                'hypothesis': 'Arctic P-Cascade Relief Hypothesis',
            },
            ...
        }
    """
    import importlib
    import re
    _dir = Path(__file__).parent

    tools = {}
    for script in sorted(_dir.glob("test_*.py")):
        # Skip __init__, framework, and generated/
        if script.name in ('__init__.py', 'test_hypothesis_framework.py'):
            continue

        tool_name = script.stem  # e.g., 'test_p_cascade'

        # Quick check: file must contain 'def test_hypothesis('
        content = script.read_text()
        if 'def test_hypothesis(' not in content:
            continue

        # Extract metadata from docstring
        description = ''
        hypothesis = ''
        doc_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if doc_match:
            docstring = doc_match.group(1).strip()
            for line in docstring.split('\n'):
                line = line.strip()
                if line.startswith('Description:'):
                    description = line.replace('Description:', '').strip()
                elif line.startswith('Hypothesis:'):
                    hypothesis = line.replace('Hypothesis:', '').strip()
            # Fallback: use first line of docstring
            if not description:
                first_line = docstring.split('\n')[0].strip().rstrip('.')
                if first_line and not first_line.startswith('Auto-generated'):
                    description = first_line

        tools[tool_name] = {
            'module': f'phases.phase3_diagnosis.{tool_name}',
            'description': description or f'Ensemble-level hypothesis test ({tool_name})',
            'hypothesis': hypothesis,
        }

    return tools


def load_ensemble_test(tool_name: str):
    """
    Dynamically import and return the test_hypothesis function for a tool.

    Args:
        tool_name: e.g., 'test_p_cascade'

    Returns:
        The test_hypothesis callable, or None if not found.
    """
    import importlib
    try:
        module = importlib.import_module(f'phases.phase3_diagnosis.{tool_name}')
        fn = getattr(module, 'test_hypothesis', None)
        if fn is None:
            _logger.warning(f"Module {tool_name} has no test_hypothesis function")
        return fn
    except ImportError as e:
        _logger.debug(f"Could not import {tool_name}: {e}")
        return None


import logging as _logging
from pathlib import Path
_logger = _logging.getLogger(__name__)


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

    # Diagnostic plotting
    'plot_pft_diagnosis',
    'plot_biomass_trajectories',
    'plot_nutrient_limitation',
    'plot_light_competition',
    'plot_allocation_dynamics',
    'plot_allocation_rates',
    'plot_mortality_components',
    'plot_p_mass_balance',

    # Ensemble-level hypothesis tests
    'test_p_limitation_cascade',
    'test_root_turnover_impact',

    # Discovery API
    'discover_ensemble_tests',
    'load_ensemble_test',
]
