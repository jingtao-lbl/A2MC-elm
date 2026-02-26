#!/usr/bin/env python3
"""
Phase 3 Run Diagnostic Scripts — Gather actual data for diagnosis

Extracted from orchestrator.py _run_diagnostic_scripts().
Runs edge-parameter checks, PFT diagnostics, and generates figures.

Author: Jing Tao with Claude
"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def run_diagnostic_scripts(
    screening_data: Dict,
    targets_config=None,
    calibration_round: int = 1,
    experiment_count: int = 0,
    skip_testing_count: int = 0,
    skip_figures: bool = False,
) -> Optional[object]:
    """
    Run Phase 3 diagnostic scripts to gather actual data.

    This function calls the diagnosis scripts to:
    1. Read actual parameter values for the best case
    2. Check which parameters are at sampling bounds
    3. Compare best case with other top cases
    4. Run PFT-specific diagnostics (if NC file available)

    Args:
        screening_data: Screening results from Phase 2
        targets_config: Config.targets object (has .biomass attribute).
            If None, targets are loaded from screening module.
        calibration_round: Current calibration round (for plot filename prefix)
        experiment_count: Current experiment count (for plot filename prefix)
        skip_testing_count: Current skip-testing count (for plot filename prefix)
        skip_figures: If True, skip figure generation (already analyzed)

    Returns:
        DiagnosisResult with parameter values, edge analysis, etc.
        Returns None if diagnostic tools unavailable or fail.
    """
    # Check availability
    try:
        from phases.phase3_diagnosis import run_diagnosis_for_orchestrator
    except ImportError:
        logger.warning("Diagnosis tools not available")
        return None

    try:
        from tools.config import config as a2mc_config
        from dataclasses import asdict

        # Get paths from config
        morris_file = a2mc_config.ENSEMBLE_MATRIX_FILE
        param_names_file = a2mc_config.PARAM_LIST_FILE
        param_bounds_file = a2mc_config.SALIB_PROBLEM_FILE

        # Validate paths exist
        if not morris_file or not Path(morris_file).exists():
            logger.warning(f"Morris file not found: {morris_file}")
            return None
        if not param_names_file or not Path(param_names_file).exists():
            logger.warning(f"Param names file not found: {param_names_file}")
            return None

        # Get PFT IDs from config or use defaults
        pft_ids = []
        pft_str = os.environ.get('A2MC_PFTS', '7,9,10')
        if pft_str:
            pft_ids = [int(p.strip()) for p in pft_str.split(',')]

        # Get targets from config, falling back to screening targets
        targets = None
        if targets_config is not None and hasattr(targets_config, 'biomass'):
            targets = asdict(targets_config).get('biomass', {})
        if not targets:
            # Build targets dict from screening module's target definitions
            try:
                from phases.phase2_screening.screen_ensemble import load_kougarok_targets
                screening_targets = load_kougarok_targets()
                # Convert {PFT7_leaf: Target(...)} -> {PFT7: {leaf: obs_val}}
                targets = {}
                for tname, tobj in screening_targets.items():
                    parts = tname.split('_', 1)  # e.g. 'PFT7_leaf' -> ['PFT7', 'leaf']
                    if len(parts) == 2:
                        pft_key, var_name = parts
                        if pft_key not in targets:
                            targets[pft_key] = {}
                        targets[pft_key][var_name] = tobj.observed
                if targets:
                    logger.info(f"Loaded {sum(len(v) for v in targets.values())} targets from screening module")
            except Exception as e:
                logger.warning(f"Could not load screening targets: {e}")

        # Get NC file path for best case (if available)
        nc_file = None
        best_case = screening_data.get('best_case', {})
        if best_case:
            case_id = best_case.get('case_id', best_case.get('case_num'))
            if case_id:
                extracted_dir = a2mc_config.EXTRACTED_DATA
                if extracted_dir and Path(extracted_dir).exists():
                    pattern = f"*En{case_id}_*all_variables*.nc"
                    nc_files = list(Path(extracted_dir).glob(pattern))
                    if nc_files:
                        nc_file = str(nc_files[0])
                        logger.info(f"Found NC file for case {case_id}: {nc_file}")

        # Also resolve NC file for lowest_cost_case (if different from best_case)
        nc_file_lowest = None
        lowest_cost = screening_data.get('lowest_cost_case', {})
        lowest_cost_id = lowest_cost.get('case_id', lowest_cost.get('case_num'))
        best_case_id = best_case.get('case_id', best_case.get('case_num')) if best_case else None
        if lowest_cost_id and lowest_cost_id != best_case_id:
            extracted_dir = a2mc_config.EXTRACTED_DATA
            if extracted_dir and Path(extracted_dir).exists():
                pattern = f"*En{lowest_cost_id}_*all_variables*.nc"
                nc_files_lc = list(Path(extracted_dir).glob(pattern))
                if nc_files_lc:
                    nc_file_lowest = str(nc_files_lc[0])
                    logger.info(f"Found NC file for lowest_cost case {lowest_cost_id}: {nc_file_lowest}")

        # Compute plot output directory (phase_results, not logs)
        plot_output_dir = None
        plot_filename_prefix = ""
        if skip_figures:
            logger.info("Skipping figure generation (case already analyzed in previous cycle)")
        elif a2mc_config.USE_CASE_DIR:
            plot_output_dir = str(
                Path(a2mc_config.USE_CASE_DIR) / "memory" / "phase_results" / "phase3_diagnosis"
            )
            # Build filename prefix from iteration context
            rr = calibration_round
            ee = experiment_count
            sc = skip_testing_count
            ii = sc + 1  # 1-based inner loop counter
            plot_filename_prefix = f"r{rr:02d}_c{ee:02d}_iter{ii:02d}_"

        # Run diagnosis for best case
        result = run_diagnosis_for_orchestrator(
            screening_data=screening_data,
            morris_file=morris_file,
            param_names_file=param_names_file,
            param_bounds_file=param_bounds_file if param_bounds_file and Path(param_bounds_file).exists() else None,
            nc_file=nc_file,
            targets=targets,
            pft_ids=pft_ids,
            top_cases_for_comparison=5,
            plot_output_dir=plot_output_dir,
            plot_filename_prefix=plot_filename_prefix + f"case{best_case_id}_" if best_case_id else plot_filename_prefix,
            verbose=True
        )

        # Also run PFT diagnosis for lowest_cost_case (generates comparative figures)
        if nc_file_lowest and plot_output_dir:
            try:
                lc_screening = screening_data.copy()
                lc_screening['best_case'] = lowest_cost
                lc_prefix = plot_filename_prefix + f"case{lowest_cost_id}_"

                lc_result = run_diagnosis_for_orchestrator(
                    screening_data=lc_screening,
                    morris_file=morris_file,
                    param_names_file=param_names_file,
                    param_bounds_file=param_bounds_file if param_bounds_file and Path(param_bounds_file).exists() else None,
                    nc_file=nc_file_lowest,
                    targets=targets,
                    pft_ids=pft_ids,
                    top_cases_for_comparison=0,
                    plot_output_dir=plot_output_dir,
                    plot_filename_prefix=lc_prefix,
                    verbose=False
                )
                # Merge figure paths from lowest_cost diagnosis into main result
                if lc_result and hasattr(lc_result, 'figure_paths'):
                    for fp in lc_result.figure_paths:
                        if fp and Path(fp).exists():
                            result.figure_paths.append(fp)
                    logger.info(f"Added {len(lc_result.figure_paths)} figures from lowest_cost case {lowest_cost_id}")
            except Exception as e:
                logger.warning(f"Could not run diagnosis for lowest_cost case {lowest_cost_id}: {e}")

        return result

    except Exception as e:
        logger.error(f"Error running diagnostic scripts: {e}")
        import traceback
        traceback.print_exc()
        return None
