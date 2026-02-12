#!/usr/bin/env python3
"""
Phase 3 Diagnosis: Compare Simulated vs Observed Targets

Compare model output to validation targets (biomass, fluxes, etc.).
Calculate error metrics and identify which targets are failing.

Usage (Python API):
    from phases.phase3_diagnosis import compare_biomass_targets

    result = compare_biomass_targets(
        nc_file="/path/to/output.nc",
        targets={
            'PFT7': {'leaf': 24.6, 'froot': 174.2},
            'PFT9': {'leaf': 124.7, 'froot': 187.3},
            'PFT10': {'leaf': 82.7, 'froot': 382.1}
        },
        time_index=-1  # Last timestep
    )

Usage (CLI):
    python -m phases.phase3_diagnosis.compare_targets \\
        --nc-file /path/to/output.nc \\
        --targets-file /path/to/targets.json

Author: Jing Tao with Claude
Adapted from: compare_biomass_*.py scripts (December 2025)
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

from tools.fates_output_variables import resolve_target_name, get_variable_family, TARGET_VAR_MAPPING
from tools.fates_utils import get_szpf_range

logger = logging.getLogger(__name__)


def extract_target_values(
    nc_file: str,
    targets: Dict[str, Dict[str, float]],
    time_index: Optional[int] = None,
    time_range: Optional[Tuple[int, int]] = None
) -> Dict:
    """
    Extract simulated values for comparison with targets.

    Args:
        nc_file: Path to NetCDF output file
        targets: Target definition dict:
                 {'PFT7': {'leaf': 24.6, 'froot': 174.2}, ...}
        time_index: Specific time index to use (e.g., -1 for last)
        time_range: Optional (start, end) indices for averaging

    Returns:
        Dict with simulated values per PFT and target
    """
    try:
        import netCDF4 as nc
    except ImportError:
        logger.error("netCDF4 required")
        return {}

    result = {}

    with nc.Dataset(nc_file, 'r') as ds:
        n_time = ds.dimensions['time'].size

        # Determine time indices
        if time_range:
            t_start, t_end = time_range
            t_start = max(0, t_start)
            t_end = min(n_time, t_end)
        elif time_index is not None:
            if time_index < 0:
                time_index = n_time + time_index
            t_start, t_end = time_index, time_index + 1
        else:
            # Default: last 12 months
            t_start = max(0, n_time - 12)
            t_end = n_time

        for pft_key, pft_targets in targets.items():
            # Parse PFT ID from key (e.g., 'PFT7' -> 7)
            if pft_key.upper().startswith('PFT'):
                pft_id = int(pft_key[3:])
            else:
                try:
                    pft_id = int(pft_key)
                except ValueError:
                    logger.warning(f"Cannot parse PFT ID from {pft_key}")
                    continue

            pft_idx = pft_id - 1
            result[pft_key] = {'pft_id': pft_id}

            for target_name, target_value in pft_targets.items():
                # Resolve alias and get variable name from registry
                canonical = resolve_target_name(target_name)
                var_name = TARGET_VAR_MAPPING.get(canonical)
                if var_name is None:
                    # Try direct variable name (e.g., user passed 'FATES_LEAFC_SZPF')
                    var_name = target_name

                if var_name not in ds.variables:
                    logger.warning(f"Variable {var_name} not found for target {target_name}")
                    continue

                arr = ds.variables[var_name][:]

                # Extract based on variable dimensions
                if 'SZPF' in var_name:
                    # Sum across size classes for this PFT
                    szpf_start, szpf_end = get_szpf_range(pft_id)
                    if arr.ndim == 3:
                        data = np.sum(arr[t_start:t_end, szpf_start:szpf_end+1, 0], axis=1)
                    else:
                        data = np.sum(arr[t_start:t_end, szpf_start:szpf_end+1], axis=1)
                    # Convert kg to g
                    simulated = float(np.mean(data)) * 1000
                elif '_PF' in var_name:
                    # PFT-level variable
                    if arr.ndim == 3:
                        data = arr[t_start:t_end, pft_idx, 0]
                    else:
                        data = arr[t_start:t_end, pft_idx]
                    simulated = float(np.mean(data)) * 1000  # Assume kg to g
                else:
                    # Site-level variable
                    if arr.ndim >= 2:
                        data = arr[t_start:t_end, 0]
                    else:
                        data = arr[t_start:t_end]
                    simulated = float(np.mean(data))

                result[pft_key][target_name] = {
                    'simulated': simulated,
                    'observed': target_value
                }

    return result


def calculate_target_metrics(
    extracted: Dict,
    uncertainty: Optional[Dict] = None
) -> Dict:
    """
    Calculate error metrics for each target.

    Args:
        extracted: Output from extract_target_values()
        uncertainty: Optional dict of uncertainty values per target

    Returns:
        Dict with metrics per PFT and target
    """
    result = {}

    for pft_key, pft_data in extracted.items():
        if not isinstance(pft_data, dict):
            continue

        result[pft_key] = {'pft_id': pft_data.get('pft_id')}

        for target_name, values in pft_data.items():
            if target_name == 'pft_id':
                continue
            if not isinstance(values, dict):
                continue

            sim = values.get('simulated')
            obs = values.get('observed')

            if sim is None or obs is None:
                continue

            # Calculate metrics
            abs_error = sim - obs
            if obs != 0:
                rel_error = abs_error / obs
                rel_error_pct = rel_error * 100
            else:
                rel_error = float('inf') if sim != 0 else 0
                rel_error_pct = rel_error * 100 if rel_error != float('inf') else 0

            # Check if within uncertainty
            unc = uncertainty.get(pft_key, {}).get(target_name) if uncertainty else None
            within_uncertainty = False
            if unc is not None:
                within_uncertainty = abs(abs_error) <= unc

            result[pft_key][target_name] = {
                'simulated': sim,
                'observed': obs,
                'absolute_error': abs_error,
                'relative_error': rel_error,
                'relative_error_pct': rel_error_pct,
                'uncertainty': unc,
                'within_uncertainty': within_uncertainty,
                'status': 'pass' if within_uncertainty else ('good' if abs(rel_error_pct) < 20 else 'fail')
            }

    return result


def compare_biomass_targets(
    nc_file: str,
    targets: Dict[str, Dict[str, float]],
    time_index: Optional[int] = None,
    uncertainty: Optional[Dict] = None,
    pft_ids: Optional[List[int]] = None
) -> Dict:
    """
    Compare simulated biomass to observation targets.

    Main function for target comparison, combining extraction and metrics.

    Args:
        nc_file: Path to NetCDF output file
        targets: Target values per PFT: {'PFT7': {'leaf': 24.6, ...}, ...}
        time_index: Specific time index (default: average last 12 months)
        uncertainty: Optional uncertainty values for pass/fail determination
        pft_ids: Optional list of PFT IDs to include (default: all in targets)

    Returns:
        Comprehensive comparison result
    """
    # Filter targets by PFT if specified
    if pft_ids:
        targets = {k: v for k, v in targets.items()
                   if any(str(p) in k for p in pft_ids)}

    # Extract simulated values
    extracted = extract_target_values(nc_file, targets, time_index)

    # Calculate metrics
    metrics = calculate_target_metrics(extracted, uncertainty)

    # Summary statistics
    all_targets = []
    passing = 0
    failing = 0

    for pft_key, pft_metrics in metrics.items():
        for target_name, target_metrics in pft_metrics.items():
            if target_name == 'pft_id':
                continue
            if isinstance(target_metrics, dict):
                all_targets.append({
                    'pft': pft_key,
                    'target': target_name,
                    **target_metrics
                })
                if target_metrics.get('status') in ['pass', 'good']:
                    passing += 1
                else:
                    failing += 1

    result = {
        'nc_file': nc_file,
        'metrics': metrics,
        'all_targets': all_targets,
        'summary': {
            'total_targets': len(all_targets),
            'passing': passing,
            'failing': failing,
            'pass_rate': passing / max(len(all_targets), 1) * 100
        },
        'failing_targets': [t for t in all_targets if t.get('status') == 'fail']
    }

    return result


def load_targets_from_file(targets_file: str) -> Dict:
    """
    Load target definitions from JSON or text file.

    Supports formats:
    - JSON: {'PFT7': {'leaf': 24.6, 'froot': 174.2}, ...}
    - Text: "PFT7_leaf 24.6\nPFT7_froot 174.2\n..."

    Args:
        targets_file: Path to targets file

    Returns:
        Dict of targets
    """
    file_path = Path(targets_file)

    if file_path.suffix == '.json':
        with open(file_path) as f:
            return json.load(f)

    # Parse text file
    targets = {}
    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if len(parts) >= 2:
                key = parts[0]
                value = float(parts[1])

                # Parse key (e.g., "PFT7_leaf" or "leaf_pft7")
                if '_' in key:
                    key_parts = key.split('_')
                    if key_parts[0].upper().startswith('PFT'):
                        pft = key_parts[0]
                        target = '_'.join(key_parts[1:])
                    elif key_parts[-1].lower().startswith('pft'):
                        pft = key_parts[-1].upper()
                        target = '_'.join(key_parts[:-1])
                    else:
                        continue

                    if pft not in targets:
                        targets[pft] = {}
                    targets[pft][target] = value

    return targets


def get_target_summary_for_ai(comparison: Dict) -> str:
    """
    Generate text summary suitable for AI reasoning.

    Args:
        comparison: Output from compare_biomass_targets()

    Returns:
        Formatted string summary
    """
    lines = []
    lines.append("=== Target Comparison Summary ===")
    lines.append("")

    summary = comparison.get('summary', {})
    lines.append(f"Total targets: {summary.get('total_targets', 0)}")
    lines.append(f"Passing: {summary.get('passing', 0)}")
    lines.append(f"Failing: {summary.get('failing', 0)}")
    lines.append(f"Pass rate: {summary.get('pass_rate', 0):.1f}%")
    lines.append("")

    # Group by PFT
    metrics = comparison.get('metrics', {})
    for pft_key in sorted(metrics.keys()):
        pft_metrics = metrics[pft_key]
        if not isinstance(pft_metrics, dict):
            continue

        lines.append(f"--- {pft_key} ---")
        for target_name, data in pft_metrics.items():
            if target_name == 'pft_id':
                continue
            if not isinstance(data, dict):
                continue

            status = data.get('status', 'unknown')
            status_marker = "PASS" if status in ['pass', 'good'] else "FAIL"
            lines.append(f"  {target_name}: {data.get('simulated', '?'):.1f} vs "
                        f"{data.get('observed', '?'):.1f} "
                        f"({data.get('relative_error_pct', 0):.1f}%) [{status_marker}]")
        lines.append("")

    # Failing targets detail
    failing = comparison.get('failing_targets', [])
    if failing:
        lines.append("Failing Targets (need attention):")
        for t in failing:
            lines.append(f"  - {t['pft']}:{t['target']}: "
                        f"{t.get('simulated', '?'):.1f} vs {t.get('observed', '?'):.1f} "
                        f"({t.get('relative_error_pct', 0):.1f}% error)")
        lines.append("")

    return "\n".join(lines)


def main():
    """CLI interface for target comparison."""
    parser = argparse.ArgumentParser(
        description="Compare simulated values to observation targets"
    )
    parser.add_argument('--nc-file', required=True,
                        help='Path to NetCDF output file')
    parser.add_argument('--targets', required=True,
                        help='JSON string or file with targets')
    parser.add_argument('--uncertainty-file',
                        help='JSON file with uncertainty values')
    parser.add_argument('--time-index', type=int,
                        help='Time index to use (-1 for last)')
    parser.add_argument('--pft-ids', type=int, nargs='+',
                        help='Specific PFT IDs to compare')
    parser.add_argument('--output', '-o',
                        help='Output JSON file')
    parser.add_argument('--text', action='store_true',
                        help='Output text summary')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Load targets
    if args.targets.startswith('{'):
        targets = json.loads(args.targets)
    else:
        targets = load_targets_from_file(args.targets)

    # Load uncertainty if provided
    uncertainty = None
    if args.uncertainty_file:
        with open(args.uncertainty_file) as f:
            uncertainty = json.load(f)

    result = compare_biomass_targets(
        args.nc_file,
        targets,
        args.time_index,
        uncertainty,
        args.pft_ids
    )

    if args.text:
        print(get_target_summary_for_ai(result))
    elif args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Results written to: {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
