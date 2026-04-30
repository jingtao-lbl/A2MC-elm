"""
A2MC Tools Package

Shared utilities for the A2MC framework (used by multiple phases):
- config: Central configuration (reads from a2mc_config.sh environment)
- cost_functions: Error metrics (RE, RMSE, NSE, KGE)
- optimize_function: Ensemble ranking against targets
- fates_utils: FATES data utilities (PFT/SZPF mapping, aggregation)
- modify_fates_parameters: NetCDF parameter file modification
- verify_parameter_file: Parameter verification utility
- phase_logger: Site-specific Markdown logging to use_cases/{site}/memory/logs/
- workflow_status: Master workflow status tracker to memory/workflow_log.json
- extract_monthly_variables_FATES: Simulation output extraction
- diagnose_ensemble_status: Monitor ensemble completion
- evaluate_case: Shared case evaluation against validation targets
- extract_knowledge: Knowledge extraction from logs

Phase-specific scripts are in phases/phase{N}_{name}/ folders.
"""

from pathlib import Path

TOOLS_DIR = Path(__file__).parent

# NOTE (v2.93, 2026-04-30): Removed `from .config import config, ...` line.
# Importing `config` (the A2MCConfig() singleton) at the package level
# shadowed the `tools.config` submodule, breaking `import tools.config as
# cfg_mod` in `tools/case_parser.py`. All callers already use the explicit
# `from tools.config import config` (or `import config as a2mc_config`)
# form, so removing the package-level shortcut is safe.
#
# If you need the singleton, use:
#     from tools.config import config            # the A2MCConfig instance
#     from tools.config import config as cfg     # alias for clarity

# Import key functions from fates_output_variables for convenient access
from .fates_output_variables import (
    resolve_target_name,
    get_variable_family,
    get_fates_variable,
    get_validation_factor,
    get_preferred_level,
    list_families,
    TARGET_VAR_MAPPING,
    OUTPUT_VARIABLES,
    VAR_FACTORS,
)

# Import key functions from fates_utils for convenient access
from .fates_utils import (
    # Constants
    N_SIZE_CLASSES,
    # Helper functions
    get_n_szpf_levels,
    get_pft_names_from_file,
    # Index mapping functions
    get_szpf_range,
    get_pft_index,
    # Data aggregation functions
    aggregate_szpf_by_pft,
    extract_pft_data,
    # Unit conversion
    convert_flux_to_annual,
    # NetCDF helpers
    get_variable_info,
    identify_dimension_level,
)

# Import evaluate_case for convenient access
try:
    from .evaluate_case import extract_case_values, evaluate_case, find_extracted_nc
except ImportError:
    extract_case_values = None
    evaluate_case = None
    find_extracted_nc = None

# Expose key functions when tools are imported as modules
__all__ = [
    # Tools (scripts)
    'modify_fates_parameters',
    'verify_parameter_file',
    'extract_monthly_variables_FATES',
    'phase_logger',
    'workflow_status',
    'cost_functions',
    'optimize_function',
    # FATES output variable registry
    'resolve_target_name',
    'get_variable_family',
    'get_fates_variable',
    'get_validation_factor',
    'get_preferred_level',
    'list_families',
    'TARGET_VAR_MAPPING',
    'OUTPUT_VARIABLES',
    'VAR_FACTORS',
    # FATES utilities - Constants
    'N_SIZE_CLASSES',
    # FATES utilities - Functions
    'get_n_szpf_levels',
    'get_pft_names_from_file',
    'get_szpf_range',
    'get_pft_index',
    'aggregate_szpf_by_pft',
    'extract_pft_data',
    'convert_flux_to_annual',
    'get_variable_info',
    'identify_dimension_level',
    # Evaluate case
    'extract_case_values',
    'evaluate_case',
    'find_extracted_nc',
]
