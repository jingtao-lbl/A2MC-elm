#!/usr/bin/env python3
"""
Phase 3 Comparative Analysis — Evaluate best_case vs lowest_cost_case

Extracted from orchestrator.py _build_comparative_analysis().
Pure function (no orchestrator state dependency).

Author: Jing Tao with Claude
"""

import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def build_comparative_analysis(screening_data: Dict) -> Dict:
    """Build comparative evaluation of best_case, lowest_cost_case, and
    all high-satisfaction alternatives.

    Evaluates each reference case against targets using both ±20% tolerance
    and obs_std-based ranges. Also identifies ALL top-10 cases that tie with
    best_case on n_satisfied, so the AI can consider alternative starting
    points instead of fixating on a single case.

    Args:
        screening_data: Screening results containing best_case, lowest_cost_case,
            and best_cases (top N list with per-target values)

    Returns:
        Dict with per-case evaluation including std-range satisfaction and
        high_satisfaction_cases list
    """
    from tools.cost_functions import within_tolerance

    # Load screening targets (which have obs_std)
    try:
        from phases.phase2_screening.screen_ensemble import load_kougarok_targets
        screening_targets = load_kougarok_targets()
    except Exception as e:
        logger.warning(f"Could not load screening targets for comparative analysis: {e}")
        return {}

    best_case = screening_data.get('best_case', {})
    lowest_cost = screening_data.get('lowest_cost_case', {})
    top_cases = screening_data.get('best_cases', [])

    def _evaluate_case(case_id, case_info):
        """Evaluate a single case against all targets."""
        # Find the case's per-target values in the top_cases list
        case_data = None
        for tc in top_cases:
            cid = tc.get('case_num', tc.get('case_id'))
            if cid == case_id:
                case_data = tc
                break

        if not case_data:
            return None

        per_target = {}
        targets_met_20pct = 0
        targets_met_std = 0

        for target_name, target_obj in screening_targets.items():
            # Per-target error is stored in top_cases as 'errors' dict or individual keys
            sim_value = case_data.get('simulated', {}).get(target_name)
            error = case_data.get('errors', {}).get(target_name)

            # Check ±20% tolerance
            within_20pct = False
            within_std = False
            if sim_value is not None:
                within_20pct = within_tolerance(sim_value, target_obj.observed, 0.2)
                # Check obs_std-based range (absolute tolerance: obs ± obs_std)
                if target_obj.obs_std is not None and target_obj.obs_std > 0:
                    within_std = within_tolerance(
                        sim_value, target_obj.observed,
                        tolerance=target_obj.obs_std,
                        tolerance_type='absolute'
                    )
                else:
                    within_std = within_20pct  # fallback to ±20% if no std
            elif error is not None:
                # Use error value to reconstruct
                within_20pct = abs(error) <= 0.2

            if within_20pct:
                targets_met_20pct += 1
            if within_std:
                targets_met_std += 1

            per_target[target_name] = {
                'observed': target_obj.observed,
                'obs_std': target_obj.obs_std,
                'simulated': sim_value,
                'relative_error': error,
                'within_20pct': within_20pct,
                'within_std': within_std,
            }

        return {
            'case_id': case_id,
            'rmsre': case_info.get('composite_rmsre', case_info.get('composite_nrmse')),
            'targets_met_20pct': targets_met_20pct,
            'targets_met_std': targets_met_std,
            'total_targets': len(screening_targets),
            'per_target': per_target,
        }

    result = {}
    if best_case.get('case_id'):
        eval_best = _evaluate_case(best_case['case_id'], best_case)
        if eval_best:
            result['best_case'] = eval_best

    if lowest_cost.get('case_id'):
        eval_lowest = _evaluate_case(lowest_cost['case_id'], lowest_cost)
        if eval_lowest:
            result['lowest_cost_case'] = eval_lowest

    # Find ALL top-10 cases that tie with best_case on n_satisfied.
    # The AI should consider these as alternative starting points, not
    # fixate on the single best_case (which wins ties by lowest cost).
    best_n_satisfied = best_case.get('targets_met', 0)
    best_case_id = best_case.get('case_id')
    high_sat_cases = []
    for tc in top_cases:
        cid = tc.get('case_num', tc.get('case_id'))
        if tc.get('n_satisfied', 0) >= best_n_satisfied and cid != best_case_id:
            eval_alt = _evaluate_case(cid, {
                'composite_rmsre': tc.get('cost'),
                'targets_met': tc.get('n_satisfied', 0)
            })
            if eval_alt:
                high_sat_cases.append(eval_alt)

    if high_sat_cases:
        result['high_satisfaction_cases'] = high_sat_cases
        alt_ids = [str(c['case_id']) for c in high_sat_cases]
        logger.info(f"Found {len(high_sat_cases)} alternative high-satisfaction case(s): "
                    f"#{', #'.join(alt_ids)} (same {best_n_satisfied} targets met)")

        # Add parameter differences between best_case and each alternative.
        # This lets the AI see WHAT causes complementary performance.
        if best_case_id:
            _add_parameter_diffs(result, best_case_id, high_sat_cases)

    if result:
        logger.info(f"Comparative analysis: best_case #{best_case_id} meets "
                   f"{result.get('best_case', {}).get('targets_met_20pct', '?')}/20pct, "
                   f"{result.get('best_case', {}).get('targets_met_std', '?')}/std; "
                   f"lowest_cost meets "
                   f"{result.get('lowest_cost_case', {}).get('targets_met_20pct', '?')}/20pct, "
                   f"{result.get('lowest_cost_case', {}).get('targets_met_std', '?')}/std")

    return result


def _add_parameter_diffs(result: Dict, best_case_id: int,
                         high_sat_cases: List[Dict]) -> None:
    """Add top parameter differences between best_case and each alternative.

    Modifies each entry in high_sat_cases in-place by adding a
    'param_diffs_vs_best' key with the top 15 parameter differences.
    Also adds the diffs to result['parameter_comparisons'] for easy access.
    """
    try:
        from tools.config import config as a2mc_config
        morris_file = a2mc_config.ENSEMBLE_MATRIX_FILE
        param_names_file = a2mc_config.PARAM_LIST_FILE
        param_bounds_file = a2mc_config.SALIB_PROBLEM_FILE
    except Exception as e:
        logger.debug(f"Could not load config for parameter comparison: {e}")
        return

    if not morris_file or not Path(morris_file).exists():
        logger.debug(f"Morris file not found: {morris_file}")
        return

    try:
        from phases.phase3_diagnosis.compare_case_parameters import compare_cases
    except ImportError:
        logger.debug("compare_case_parameters not available")
        return

    comparisons = {}
    for alt_case in high_sat_cases:
        alt_id = alt_case['case_id']
        try:
            diff = compare_cases(
                case1_id=int(best_case_id),
                case2_id=int(alt_id),
                morris_file=morris_file,
                param_names=param_names_file,
                param_bounds=param_bounds_file,
                top_n=15
            )
            top_diffs = diff.get('top_differences', [])
            alt_case['param_diffs_vs_best'] = top_diffs
            comparisons[f"best#{best_case_id}_vs_alt#{alt_id}"] = {
                'case1': best_case_id,
                'case2': alt_id,
                'top_diffs': top_diffs,
                'summary': diff.get('summary', {}),
            }
            logger.info(f"Parameter comparison #{best_case_id} vs #{alt_id}: "
                        f"{len(top_diffs)} top differences")
        except Exception as e:
            logger.warning(f"Could not compare parameters #{best_case_id} vs #{alt_id}: {e}")

    if comparisons:
        result['parameter_comparisons'] = comparisons
