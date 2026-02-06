#!/usr/bin/env python3
"""
Phase 3 Diagnosis: Compare Parameters Between Cases

Compare parameter differences between any two Morris ensemble cases.
Useful for understanding what makes one case perform better than another.

Usage (Python API):
    from phases.phase3_diagnosis import compare_cases

    diff_df = compare_cases(
        case1_id=2678,
        case2_id=845,
        morris_file="/path/to/morris_params.txt",
        param_names=["l2fr_ini_9", ...],
        param_bounds=[(0.01, 2.96), ...],
        top_n=20
    )

Usage (CLI):
    python -m phases.phase3_diagnosis.compare_case_parameters \\
        --case1 2678 --case2 845 \\
        --morris-file /path/to/morris_params.txt \\
        --param-names-file /path/to/param_names.txt \\
        --param-bounds-file /path/to/bounds.txt \\
        --top 20

Author: Jing Tao with Claude
Adapted from: compare_two_cases_parameters.py (December 2025)
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

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


def compare_cases(
    case1_id: int,
    case2_id: int,
    morris_file: str,
    param_names: Union[List[str], str],
    param_bounds: Union[List[Tuple[float, float]], str],
    top_n: int = 20
) -> Dict:
    """
    Compare parameters between two Morris ensemble cases.

    Args:
        case1_id: First case number (1-indexed)
        case2_id: Second case number (1-indexed)
        morris_file: Path to Morris parameter file
        param_names: List of parameter names or path to file
        param_bounds: List of (lower, upper) tuples or path to file
        top_n: Number of top differences to highlight

    Returns:
        Dict with comparison results:
        {
            'case1_id': 2678,
            'case2_id': 845,
            'top_differences': [
                {
                    'parameter': 'l2fr_ini_9',
                    'case1_value': 1.0,
                    'case2_value': 0.5,
                    'abs_diff': 0.5,
                    'pct_of_range': 17.0,
                    'lower_bound': 0.01,
                    'upper_bound': 2.96
                },
                ...
            ],
            'all_differences': [...],
            'summary': {
                'total_params': 138,
                'params_with_diff': 120,
                'max_pct_diff': 45.2,
                'mean_pct_diff': 12.3
            }
        }
    """
    # Load names and bounds if file paths
    if isinstance(param_names, str):
        param_names = load_param_names(param_names)
    if isinstance(param_bounds, str):
        param_bounds = load_param_bounds(param_bounds)

    # Get case values
    case1_params = read_case_parameters(case1_id, morris_file, param_names)
    case2_params = read_case_parameters(case2_id, morris_file, param_names)

    differences = []

    for i, name in enumerate(param_names):
        name = name.strip()
        if name not in case1_params or name not in case2_params:
            continue

        val1 = case1_params[name]
        val2 = case2_params[name]
        abs_diff = abs(val1 - val2)

        if i < len(param_bounds):
            lower, upper = param_bounds[i]
            param_range = upper - lower
            if param_range > 0:
                pct_of_range = (abs_diff / param_range) * 100
            else:
                pct_of_range = 0
        else:
            lower, upper = None, None
            pct_of_range = 0

        differences.append({
            'parameter': name,
            'case1_value': val1,
            'case2_value': val2,
            'abs_diff': abs_diff,
            'pct_of_range': pct_of_range,
            'lower_bound': lower,
            'upper_bound': upper
        })

    # Sort by percentage of range (largest first)
    differences.sort(key=lambda x: x['pct_of_range'], reverse=True)

    # Calculate summary stats
    pct_diffs = [d['pct_of_range'] for d in differences if d['pct_of_range'] > 0]

    result = {
        'case1_id': case1_id,
        'case2_id': case2_id,
        'top_differences': differences[:top_n],
        'all_differences': differences,
        'summary': {
            'total_params': len(param_names),
            'params_with_diff': sum(1 for d in differences if d['abs_diff'] > 0),
            'max_pct_diff': max(pct_diffs) if pct_diffs else 0,
            'mean_pct_diff': np.mean(pct_diffs) if pct_diffs else 0
        }
    }

    return result


def get_largest_differences(
    comparison: Dict,
    top_n: int = 20,
    min_pct: float = 0.0
) -> List[Dict]:
    """
    Get the top N parameters with largest difference as fraction of range.

    Args:
        comparison: Output from compare_cases()
        top_n: Number of top differences to return
        min_pct: Minimum percentage difference to include

    Returns:
        List of parameter difference dicts
    """
    diffs = [d for d in comparison['all_differences']
             if d['pct_of_range'] >= min_pct]
    return diffs[:top_n]


def get_comparison_summary_for_ai(comparison: Dict) -> str:
    """
    Generate a text summary suitable for AI reasoning.

    Args:
        comparison: Output from compare_cases()

    Returns:
        Formatted string summary
    """
    lines = []
    lines.append(f"=== Case {comparison['case1_id']} vs Case {comparison['case2_id']} ===")
    lines.append("")

    summary = comparison['summary']
    lines.append(f"Total parameters: {summary['total_params']}")
    lines.append(f"Parameters with differences: {summary['params_with_diff']}")
    lines.append(f"Max difference: {summary['max_pct_diff']:.1f}% of range")
    lines.append(f"Mean difference: {summary['mean_pct_diff']:.1f}% of range")
    lines.append("")

    lines.append("Top 10 Differences (by % of range):")
    lines.append("-" * 60)

    for d in comparison['top_differences'][:10]:
        lines.append(f"  {d['parameter']:<40}: "
                    f"{d['case1_value']:>10.4g} vs {d['case2_value']:>10.4g} "
                    f"({d['pct_of_range']:.1f}%)")

    return "\n".join(lines)


def compare_cases_to_dataframe(comparison: Dict):
    """
    Convert comparison result to pandas DataFrame.

    Args:
        comparison: Output from compare_cases()

    Returns:
        pandas DataFrame (or None if pandas not available)
    """
    if not HAS_PANDAS:
        logger.warning("pandas not available, returning None")
        return None

    return pd.DataFrame(comparison['all_differences'])


def compare_multiple_cases(
    case_ids: List[int],
    reference_case: int,
    morris_file: str,
    param_names: Union[List[str], str],
    param_bounds: Union[List[Tuple[float, float]], str]
) -> Dict[int, Dict]:
    """
    Compare multiple cases against a reference case.

    Args:
        case_ids: List of case IDs to compare
        reference_case: The reference case ID
        morris_file: Path to Morris parameter file
        param_names: Parameter names or path to file
        param_bounds: Parameter bounds or path to file

    Returns:
        Dict mapping case_id to comparison result
    """
    results = {}
    for case_id in case_ids:
        if case_id != reference_case:
            results[case_id] = compare_cases(
                reference_case,
                case_id,
                morris_file,
                param_names,
                param_bounds
            )
    return results


def find_consistent_differences(
    comparisons: Dict[int, Dict],
    threshold_pct: float = 10.0
) -> List[Dict]:
    """
    Find parameters that consistently differ across multiple case comparisons.

    Args:
        comparisons: Output from compare_multiple_cases()
        threshold_pct: Minimum percentage difference to count

    Returns:
        List of parameters that frequently appear in top differences
    """
    param_counts = {}

    for case_id, comp in comparisons.items():
        for diff in comp['top_differences']:
            if diff['pct_of_range'] >= threshold_pct:
                name = diff['parameter']
                if name not in param_counts:
                    param_counts[name] = {
                        'count': 0,
                        'mean_pct_diff': 0,
                        'cases': []
                    }
                param_counts[name]['count'] += 1
                param_counts[name]['mean_pct_diff'] += diff['pct_of_range']
                param_counts[name]['cases'].append(case_id)

    # Calculate means and sort
    result = []
    for name, data in param_counts.items():
        data['parameter'] = name
        data['mean_pct_diff'] /= data['count']
        result.append(data)

    result.sort(key=lambda x: x['count'], reverse=True)
    return result


def main():
    """CLI interface for case comparison."""
    parser = argparse.ArgumentParser(
        description="Compare parameters between Morris ensemble cases"
    )
    parser.add_argument('--case1', type=int, required=True,
                        help='First case number (1-indexed)')
    parser.add_argument('--case2', type=int, required=True,
                        help='Second case number (1-indexed)')
    parser.add_argument('--morris-file', required=True,
                        help='Path to Morris parameter file')
    parser.add_argument('--param-names-file', required=True,
                        help='Path to parameter names file')
    parser.add_argument('--param-bounds-file', required=True,
                        help='Path to parameter bounds file')
    parser.add_argument('--top', type=int, default=20,
                        help='Number of top differences to show (default: 20)')
    parser.add_argument('--output', '-o',
                        help='Output JSON file (default: stdout)')
    parser.add_argument('--text', action='store_true',
                        help='Output text summary instead of JSON')
    parser.add_argument('--csv',
                        help='Output CSV file (requires pandas)')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    result = compare_cases(
        args.case1,
        args.case2,
        args.morris_file,
        args.param_names_file,
        args.param_bounds_file,
        args.top
    )

    if args.text:
        print(get_comparison_summary_for_ai(result))
    elif args.csv:
        if HAS_PANDAS:
            df = compare_cases_to_dataframe(result)
            df.to_csv(args.csv, index=False)
            print(f"CSV written to: {args.csv}")
        else:
            print("ERROR: pandas required for CSV output")
            sys.exit(1)
    elif args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Results written to: {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
