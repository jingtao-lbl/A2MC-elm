#!/usr/bin/env python3
"""
Phase 3 Diagnosis: Check Parameters at Edge of Morris Bounds

Identify parameters that are at or very close to their Morris sampling bounds.
This indicates potential parameter space limitations - if optimal parameters
are at bounds, the sampling range may need expansion.

Usage (Python API):
    from phases.phase3_diagnosis import check_parameters_at_edge

    result = check_parameters_at_edge(
        case_id=2678,
        morris_file="/path/to/morris_params.txt",
        param_names=["l2fr_ini_9", "pid_kp_10", ...],
        param_bounds=[(0.01, 2.96), ...],
        threshold_pct=1.0
    )

Usage (CLI):
    python -m phases.phase3_diagnosis.check_edge_parameters \\
        --case-id 2678 \\
        --morris-file /path/to/morris_params.txt \\
        --param-names-file /path/to/param_names.txt \\
        --param-bounds-file /path/to/bounds.txt

Author: Jing Tao with Claude
Adapted from: check_parameters_at_edge.py (December 2025)
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from phases.phase3_diagnosis.read_case_parameters import (
    load_param_names,
    load_param_bounds,
    read_case_parameters
)

logger = logging.getLogger(__name__)


# Parameter categories for grouping
PARAMETER_CATEGORIES = {
    'CNP_vmax': ['vmax_nh4', 'vmax_no3', 'vmax_p', 'vmax_ptase'],
    'CNP_km': ['km_nh4', 'km_no3', 'km_p', 'km_ptase'],
    'CNP_other': ['alpha_ptase', 'microb_bio', 'nfix1'],
    'Retranslocation': ['nitr_retrans', 'phos_retrans'],
    'PID_controller': ['pid_kp', 'pid_ki', 'pid_kd'],
    'Allocation': ['alloc_storage_cushion', 'alloc_store_priority_frac', 'l2fr_ini'],
    'Stoichiometry_N': ['stoich_nitr_leaf', 'stoich_nitr_fineroot'],
    'Stoichiometry_P': ['stoich_phos_leaf', 'stoich_phos_fineroot'],
    'Allometry': ['allom_d2bl1', 'allom_d2bl2', 'allom_agb2', 'allom_agb3',
                  'allom_d2h1', 'allom_d2h2', 'allom_dbh_maxheight',
                  'allom_d2ca_coefficient_min'],
    'Mortality': ['mort_scalar_hydrfailure', 'mort_scalar_cstarvation',
                  'mort_scalar_coldstress', 'mort_bmort', 'mort_hf_sm_threshold',
                  'mort_freezetol'],
    'Phenology': ['phen_mindaysoff', 'phen_chilltemp', 'phen_coldtemp',
                  'phen_ncolddayslim', 'phen_gddthresh_c'],
    'Recruitment': ['recruit_height_min', 'recruit_seed_alloc', 'frag_seed_decay',
                    'recruit_seed_germination_rate', 'recruit_seed_supplement',
                    'recruit_init_density'],
    'Leaf_traits': ['leaf_slatop', 'leaf_vcmax25top', 'grperc'],
    'Maintenance_respiration': ['maintresp_nonleaf_baserate']
}


def check_parameters_at_edge(
    case_id: int,
    morris_file: str,
    param_names: Union[List[str], str],
    param_bounds: Union[List[Tuple[float, float]], str],
    threshold_pct: float = 1.0
) -> Dict:
    """
    Check which parameters in a Morris case are at their sampling bounds.

    Args:
        case_id: Case number (1-indexed)
        morris_file: Path to Morris parameter file
        param_names: List of parameter names or path to file
        param_bounds: List of (lower, upper) tuples or path to file
        threshold_pct: Threshold for "at bound" (default: within 1% of range)

    Returns:
        Dict with structure:
        {
            'case_id': 2678,
            'threshold_pct': 1.0,
            'at_lower': [
                {
                    'index': 1,
                    'name': 'alpha_ptase_7',
                    'value': 0.255,
                    'lower_bound': 0.25,
                    'upper_bound': 0.75,
                    'dist_pct': 0.5
                },
                ...
            ],
            'at_upper': [...],
            'summary': {
                'total_parameters': 138,
                'at_lower_count': 5,
                'at_upper_count': 3,
                'total_at_bounds': 8,
                'pct_at_bounds': 5.8
            }
        }
    """
    # Load names and bounds if file paths
    if isinstance(param_names, str):
        param_names = load_param_names(param_names)
    if isinstance(param_bounds, str):
        param_bounds = load_param_bounds(param_bounds)

    # Get case values
    params = read_case_parameters(case_id, morris_file, param_names)

    at_lower = []
    at_upper = []

    for i, (name, value) in enumerate(params.items()):
        if i >= len(param_bounds):
            continue

        lower, upper = param_bounds[i]
        param_range = upper - lower

        if param_range <= 0:
            continue

        # Calculate distances to bounds as percentage of range
        dist_to_lower = (value - lower) / param_range * 100
        dist_to_upper = (upper - value) / param_range * 100

        param_info = {
            'index': i + 1,
            'name': name.strip(),
            'value': value,
            'lower_bound': lower,
            'upper_bound': upper
        }

        # Check if at lower bound
        if dist_to_lower <= threshold_pct:
            param_info['dist_pct'] = dist_to_lower
            at_lower.append(param_info.copy())

        # Check if at upper bound
        if dist_to_upper <= threshold_pct:
            param_info['dist_pct'] = dist_to_upper
            at_upper.append(param_info.copy())

    result = {
        'case_id': case_id,
        'threshold_pct': threshold_pct,
        'at_lower': at_lower,
        'at_upper': at_upper,
        'summary': {
            'total_parameters': len(params),
            'at_lower_count': len(at_lower),
            'at_upper_count': len(at_upper),
            'total_at_bounds': len(at_lower) + len(at_upper),
            'pct_at_bounds': 100 * (len(at_lower) + len(at_upper)) / max(len(params), 1)
        }
    }

    return result


def categorize_edge_parameters(edge_result: Dict) -> Dict[str, Dict]:
    """
    Group edge parameters by their functional category.

    Args:
        edge_result: Output from check_parameters_at_edge()

    Returns:
        Dict mapping category name to {at_lower: [...], at_upper: [...]}
    """
    categories = {cat: {'at_lower': [], 'at_upper': []} for cat in PARAMETER_CATEGORIES}
    categories['Other'] = {'at_lower': [], 'at_upper': []}

    def get_category(param_name: str) -> str:
        """Find category for a parameter."""
        param_base = param_name.strip()
        # Remove PFT suffix for matching
        if param_base[-1].isdigit() and '_' in param_base:
            param_base = '_'.join(param_base.split('_')[:-1])

        for cat, patterns in PARAMETER_CATEGORIES.items():
            for pattern in patterns:
                if param_base.startswith(pattern) or pattern in param_base:
                    return cat
        return 'Other'

    # Categorize lower bound params
    for param in edge_result.get('at_lower', []):
        cat = get_category(param['name'])
        categories[cat]['at_lower'].append(param)

    # Categorize upper bound params
    for param in edge_result.get('at_upper', []):
        cat = get_category(param['name'])
        categories[cat]['at_upper'].append(param)

    # Remove empty categories
    return {cat: data for cat, data in categories.items()
            if data['at_lower'] or data['at_upper']}


def get_edge_summary_for_ai(edge_result: Dict) -> str:
    """
    Generate a text summary suitable for AI reasoning.

    Args:
        edge_result: Output from check_parameters_at_edge()

    Returns:
        Formatted string summary
    """
    lines = []
    lines.append(f"=== Case {edge_result['case_id']} Parameter Edge Analysis ===")
    lines.append(f"Threshold: {edge_result['threshold_pct']}% of range")
    lines.append("")

    summary = edge_result['summary']
    lines.append(f"Summary: {summary['at_lower_count']} at lower, "
                f"{summary['at_upper_count']} at upper "
                f"({summary['pct_at_bounds']:.1f}% of {summary['total_parameters']} params)")
    lines.append("")

    if edge_result['at_lower']:
        lines.append("Parameters at LOWER bound (may need lower range):")
        for p in edge_result['at_lower']:
            lines.append(f"  - {p['name']}: {p['value']:.6g} (bound: {p['lower_bound']:.6g})")
    else:
        lines.append("No parameters at lower bound.")

    lines.append("")

    if edge_result['at_upper']:
        lines.append("Parameters at UPPER bound (may need higher range):")
        for p in edge_result['at_upper']:
            lines.append(f"  - {p['name']}: {p['value']:.6g} (bound: {p['upper_bound']:.6g})")
    else:
        lines.append("No parameters at upper bound.")

    # Categorize
    categorized = categorize_edge_parameters(edge_result)
    if categorized:
        lines.append("")
        lines.append("By Category:")
        for cat, data in categorized.items():
            count = len(data['at_lower']) + len(data['at_upper'])
            if count > 0:
                lines.append(f"  {cat}: {count} params at bounds")

    return "\n".join(lines)


def identify_redesign_candidates(edge_result: Dict) -> List[Dict]:
    """
    Identify parameters that are candidates for range expansion (Phase 0 redesign).

    A parameter is a redesign candidate if it's at a bound AND the bound
    direction suggests the optimal value may be outside the sampled range.

    Args:
        edge_result: Output from check_parameters_at_edge()

    Returns:
        List of parameters with suggested range expansion direction
    """
    candidates = []

    for param in edge_result.get('at_lower', []):
        candidates.append({
            'name': param['name'],
            'current_bound': param['lower_bound'],
            'current_value': param['value'],
            'direction': 'decrease_lower',
            'suggestion': f"Consider lowering lower bound from {param['lower_bound']:.6g}"
        })

    for param in edge_result.get('at_upper', []):
        candidates.append({
            'name': param['name'],
            'current_bound': param['upper_bound'],
            'current_value': param['value'],
            'direction': 'increase_upper',
            'suggestion': f"Consider raising upper bound from {param['upper_bound']:.6g}"
        })

    return candidates


def main():
    """CLI interface for edge parameter analysis."""
    parser = argparse.ArgumentParser(
        description="Check which parameters are at Morris sampling bounds"
    )
    parser.add_argument('--case-id', type=int, required=True,
                        help='Case number (1-indexed)')
    parser.add_argument('--morris-file', required=True,
                        help='Path to Morris parameter file')
    parser.add_argument('--param-names-file', required=True,
                        help='Path to parameter names file')
    parser.add_argument('--param-bounds-file', required=True,
                        help='Path to parameter bounds file')
    parser.add_argument('--threshold', type=float, default=1.0,
                        help='Threshold percentage (default: 1.0)')
    parser.add_argument('--output', '-o',
                        help='Output JSON file (default: stdout)')
    parser.add_argument('--text', action='store_true',
                        help='Output text summary instead of JSON')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = check_parameters_at_edge(
        args.case_id,
        args.morris_file,
        args.param_names_file,
        args.param_bounds_file,
        args.threshold
    )

    if args.text:
        print(get_edge_summary_for_ai(result))
    elif args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Results written to: {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
