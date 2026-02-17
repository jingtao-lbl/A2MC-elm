#!/usr/bin/env python3
"""
Phase 3 Comparative Analysis — Evaluate best_case vs lowest_cost_case

Extracted from orchestrator.py _build_comparative_analysis().
Pure function (no orchestrator state dependency).

Author: Jing Tao with Claude
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


def build_comparative_analysis(screening_data: Dict) -> Dict:
    """Build comparative evaluation of best_case vs lowest_cost_case.

    Evaluates each reference case against targets using both ±20% tolerance
    and obs_std-based ranges. This gives the AI a richer picture of which
    case is a better starting point for refinement.

    Args:
        screening_data: Screening results containing best_case, lowest_cost_case,
            and best_cases (top N list with per-target values)

    Returns:
        Dict with per-case evaluation including std-range satisfaction
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

    if result:
        logger.info(f"Comparative analysis: best_case meets "
                   f"{result.get('best_case', {}).get('targets_met_20pct', '?')}/20pct, "
                   f"{result.get('best_case', {}).get('targets_met_std', '?')}/std; "
                   f"lowest_cost meets "
                   f"{result.get('lowest_cost_case', {}).get('targets_met_20pct', '?')}/20pct, "
                   f"{result.get('lowest_cost_case', {}).get('targets_met_std', '?')}/std")

    return result
