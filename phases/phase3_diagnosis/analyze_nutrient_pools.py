#!/usr/bin/env python3
"""
Phase 3 Diagnosis: Analyze Nutrient Pool Dynamics

Extract and analyze nutrient (P, N) pool time series to detect:
- Nutrient depletion patterns
- Uptake vs demand imbalances
- Pool transitions across simulation phases

Key insight from P_Desorption analysis: Fast P release can cause P loss
via leaching if plants can't uptake fast enough, leading to ecosystem collapse.

Usage (Python API):
    from phases.phase3_diagnosis import extract_p_pools, analyze_nutrient_depletion

    pools = extract_p_pools(
        data_files={'ADSP': 'adsp.nc', 'TRANS': 'trans.nc'},
        variables=['SMINP', 'LABILEP', 'SECONDP']
    )

    depletion = analyze_nutrient_depletion(pools, phase='TRANS')

Usage (CLI):
    python -m phases.phase3_diagnosis.analyze_nutrient_pools \\
        --adsp-file /path/to/adsp.nc \\
        --trans-file /path/to/trans.nc \\
        --pft-ids 7 9 10

Author: Jing Tao with Claude
Created from: P_Desorption_Drought_Analysis patterns (December 2025)
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)

# Common P pool variables
P_POOL_VARS = [
    'SMINP',     # Soil mineral P (primary available pool)
    'LABILEP',   # Labile P (readily available)
    'SECONDP',   # Secondary P (sorbed, slower release)
    'OCCLUDEDP', # Occluded P (very slow weathering)
    'SOLUTIONP', # Solution P
]

# Common N pool variables
N_POOL_VARS = [
    'SMIN_NH4_vr',  # Soil mineral ammonium (vertical)
    'SMIN_NO3_vr',  # Soil mineral nitrate (vertical)
    'SMINN',        # Total soil mineral N
]

# Unit conversion
G_PER_KG = 1000


def extract_p_pools(
    data_files: Dict[str, str],
    variables: Optional[List[str]] = None
) -> Dict:
    """
    Extract P pool time series across simulation phases.

    Args:
        data_files: Dict mapping phase name to file path
        variables: List of P pool variable names (default: standard set)

    Returns:
        Dict with pool data:
        {
            'time': combined time array,
            'phases': {phase: (start_idx, end_idx)},
            'pools': {var_name: array}
        }
    """
    try:
        import netCDF4 as nc
    except ImportError:
        logger.error("netCDF4 required")
        return {}

    if variables is None:
        variables = P_POOL_VARS

    result = {
        'time': [],
        'phases': {},
        'pools': {var: [] for var in variables}
    }

    time_offset = 0
    current_idx = 0

    for phase, file_path in data_files.items():
        if not Path(file_path).exists():
            logger.warning(f"File not found: {file_path}")
            continue

        with nc.Dataset(file_path, 'r') as ds:
            n_time = ds.dimensions['time'].size

            # Create time axis
            phase_time = np.arange(n_time) / 12 + time_offset + 1
            time_offset += n_time / 12

            result['phases'][phase] = (current_idx, current_idx + n_time)
            current_idx += n_time

            result['time'].append(phase_time)

            # Extract each variable
            for var in variables:
                if var in ds.variables:
                    arr = ds.variables[var][:]
                    # Handle dimensions - sum over vertical/spatial if needed
                    if arr.ndim == 3:  # (time, level, spatial)
                        arr = np.sum(arr[:, :, 0], axis=1)  # Sum over levels
                    elif arr.ndim == 2:  # (time, spatial) or (time, level)
                        if ds.variables[var].dimensions[1] in ['levdcmp', 'levsoi']:
                            arr = np.sum(arr, axis=1)
                        else:
                            arr = arr[:, 0]
                    result['pools'][var].append(arr)
                else:
                    result['pools'][var].append(np.zeros(n_time))

    # Concatenate
    if result['time']:
        result['time'] = np.concatenate(result['time'])
        for var in variables:
            if result['pools'][var]:
                result['pools'][var] = np.concatenate(result['pools'][var])

    return result


def analyze_nutrient_depletion(
    pool_data: Dict,
    phase: Optional[str] = None,
    threshold_pct: float = 50.0
) -> Dict:
    """
    Analyze nutrient pool depletion patterns.

    Args:
        pool_data: Output from extract_p_pools() or extract_n_pools()
        phase: Specific phase to analyze (None for all)
        threshold_pct: Threshold for significant depletion (%)

    Returns:
        Dict with depletion analysis
    """
    result = {
        'phase': phase or 'all',
        'pool_changes': {},
        'depleted_pools': [],
        'findings': []
    }

    time = pool_data.get('time', [])
    pools = pool_data.get('pools', {})
    phases = pool_data.get('phases', {})

    if len(time) == 0:
        return result

    # Determine index range
    if phase and phase in phases:
        start_idx, end_idx = phases[phase]
    else:
        start_idx, end_idx = 0, len(time)

    for var_name, data in pools.items():
        if not isinstance(data, np.ndarray) or len(data) == 0:
            continue

        # Get values at start and end of period
        period_data = data[start_idx:end_idx]
        if len(period_data) < 2:
            continue

        initial = float(np.mean(period_data[:12]))  # First year mean
        final = float(np.mean(period_data[-12:]))   # Last year mean

        if initial > 0:
            change_pct = (final - initial) / initial * 100
        else:
            change_pct = 0

        result['pool_changes'][var_name] = {
            'initial': initial,
            'final': final,
            'change_pct': change_pct,
            'depleted': change_pct < -threshold_pct
        }

        if change_pct < -threshold_pct:
            result['depleted_pools'].append(var_name)
            result['findings'].append({
                'type': 'critical',
                'message': f"{var_name} depleted by {abs(change_pct):.1f}% "
                          f"({initial:.2f} -> {final:.2f})"
            })

    # Check for total P depletion pattern (P_Desorption paradox)
    sminp_change = result['pool_changes'].get('SMINP', {}).get('change_pct', 0)
    secondp_change = result['pool_changes'].get('SECONDP', {}).get('change_pct', 0)

    if sminp_change < -80 and secondp_change < -80:
        result['findings'].append({
            'type': 'critical',
            'message': "P Desorption Paradox pattern: Both SMINP and SECONDP severely depleted. "
                      "Fast P release may have exceeded plant uptake capacity."
        })

    return result


def compare_uptake_vs_demand(
    nc_file: str,
    pft_id: int,
    nutrient: str = 'P'
) -> Dict:
    """
    Compare nutrient uptake to demand for a PFT.

    Args:
        nc_file: Path to NetCDF file
        pft_id: PFT ID (1-indexed)
        nutrient: 'P' for phosphorus, 'N' for nitrogen

    Returns:
        Dict with uptake/demand analysis
    """
    try:
        import netCDF4 as nc
    except ImportError:
        return {}

    result = {
        'pft_id': pft_id,
        'nutrient': nutrient,
        'findings': []
    }

    # Determine variable names based on nutrient
    if nutrient.upper() == 'P':
        demand_var = 'FATES_PDEMAND_SZPF'
        uptake_var = 'FATES_PUPTAKE_SZPF'
    else:
        demand_var = 'FATES_NDEMAND_SZPF'
        uptake_var = 'FATES_NUPTAKE_SZPF'

    # Get SZPF index range for this PFT
    start_idx = (pft_id - 1) * 13
    end_idx = start_idx + 13

    with nc.Dataset(nc_file, 'r') as ds:
        # Unit conversion: kg/m²/s to g/m²/year
        scale = G_PER_KG * 365 * 24 * 3600  # ELM uses no-leap-year calendar

        if demand_var in ds.variables:
            demand_data = ds.variables[demand_var][:]
            if demand_data.ndim == 3:
                demand = np.sum(demand_data[:, start_idx:end_idx, 0], axis=1) * scale
            else:
                demand = np.sum(demand_data[:, start_idx:end_idx], axis=1) * scale

            result['demand'] = {
                'mean': float(np.nanmean(demand)),
                'max': float(np.nanmax(demand)),
                'total': float(np.nansum(demand))
            }

        if uptake_var in ds.variables:
            uptake_data = ds.variables[uptake_var][:]
            if uptake_data.ndim == 3:
                uptake = np.sum(uptake_data[:, start_idx:end_idx, 0], axis=1) * scale
            else:
                uptake = np.sum(uptake_data[:, start_idx:end_idx], axis=1) * scale

            result['uptake'] = {
                'mean': float(np.nanmean(uptake)),
                'max': float(np.nanmax(uptake)),
                'total': float(np.nansum(uptake))
            }

        # Calculate ratio if we have both
        if 'demand' in result and 'uptake' in result:
            demand_mean = result['demand']['mean']
            uptake_mean = result['uptake']['mean']

            if demand_mean > 0:
                ratio = uptake_mean / demand_mean
                result['supply_demand_ratio'] = ratio

                if ratio < 0.5:
                    result['findings'].append({
                        'type': 'critical',
                        'message': f"Severe {nutrient} limitation: uptake/demand = {ratio:.2f}"
                    })
                elif ratio < 0.8:
                    result['findings'].append({
                        'type': 'warning',
                        'message': f"Moderate {nutrient} limitation: uptake/demand = {ratio:.2f}"
                    })
                elif ratio < 0.95:
                    result['findings'].append({
                        'type': 'info',
                        'message': f"Mild {nutrient} limitation: uptake/demand = {ratio:.2f}"
                    })
                else:
                    result['findings'].append({
                        'type': 'info',
                        'message': f"{nutrient} demand mostly satisfied: uptake/demand = {ratio:.2f}"
                    })

    return result


def extract_n_pools(
    data_files: Dict[str, str],
    variables: Optional[List[str]] = None
) -> Dict:
    """
    Extract N pool time series across simulation phases.

    Args:
        data_files: Dict mapping phase name to file path
        variables: List of N pool variable names

    Returns:
        Same structure as extract_p_pools()
    """
    if variables is None:
        variables = N_POOL_VARS

    return extract_p_pools(data_files, variables)


def get_nutrient_summary_for_ai(
    pool_data: Dict,
    depletion_analysis: Dict,
    pft_analyses: Dict[int, Dict]
) -> str:
    """
    Generate text summary suitable for AI reasoning.

    Args:
        pool_data: Output from extract_p_pools()
        depletion_analysis: Output from analyze_nutrient_depletion()
        pft_analyses: Dict mapping PFT ID to uptake/demand analysis

    Returns:
        Formatted string summary
    """
    lines = []
    lines.append("=== Nutrient Pool Analysis Summary ===")
    lines.append("")

    # Pool changes
    changes = depletion_analysis.get('pool_changes', {})
    if changes:
        lines.append("Pool Changes:")
        for var, data in changes.items():
            status = "DEPLETED" if data['depleted'] else "stable"
            lines.append(f"  {var}: {data['initial']:.2f} -> {data['final']:.2f} "
                        f"({data['change_pct']:.1f}%) [{status}]")
        lines.append("")

    # Findings
    findings = depletion_analysis.get('findings', [])
    if findings:
        lines.append("Findings:")
        for f in findings:
            lines.append(f"  {f['type'].upper()}: {f['message']}")
        lines.append("")

    # PFT uptake/demand
    if pft_analyses:
        lines.append("PFT Uptake vs Demand:")
        for pft_id, analysis in pft_analyses.items():
            ratio = analysis.get('supply_demand_ratio', 'N/A')
            if isinstance(ratio, float):
                lines.append(f"  PFT{pft_id}: {analysis['nutrient']} ratio = {ratio:.2f}")
            for f in analysis.get('findings', []):
                lines.append(f"    {f['message']}")
        lines.append("")

    return "\n".join(lines)


def main():
    """CLI interface for nutrient pool analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze nutrient pool dynamics (P and N)"
    )
    parser.add_argument('--adsp-file', help='Path to ADSP phase NetCDF')
    parser.add_argument('--rgsp-file', help='Path to RGSP phase NetCDF')
    parser.add_argument('--trans-file', help='Path to TRANS phase NetCDF')
    parser.add_argument('--nc-file', help='Single NetCDF file')
    parser.add_argument('--pft-ids', type=int, nargs='+',
                        help='PFT IDs for uptake/demand analysis')
    parser.add_argument('--nutrient', choices=['P', 'N'], default='P',
                        help='Nutrient to analyze')
    parser.add_argument('--output', '-o', help='Output JSON file')
    parser.add_argument('--text', action='store_true',
                        help='Output text summary')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Build data files dict
    data_files = {}
    if args.nc_file:
        data_files = {'single': args.nc_file}
    else:
        if args.adsp_file:
            data_files['ADSP'] = args.adsp_file
        if args.rgsp_file:
            data_files['RGSP'] = args.rgsp_file
        if args.trans_file:
            data_files['TRANS'] = args.trans_file

    if not data_files:
        print("ERROR: At least one data file required")
        sys.exit(1)

    # Extract pools
    if args.nutrient == 'P':
        pool_data = extract_p_pools(data_files)
    else:
        pool_data = extract_n_pools(data_files)

    # Analyze depletion
    depletion = analyze_nutrient_depletion(pool_data)

    # Analyze uptake/demand per PFT
    pft_analyses = {}
    if args.pft_ids:
        # Use TRANS file for uptake/demand (most relevant)
        uptake_file = args.trans_file or args.nc_file or list(data_files.values())[-1]
        for pft_id in args.pft_ids:
            pft_analyses[pft_id] = compare_uptake_vs_demand(
                uptake_file, pft_id, args.nutrient
            )

    if args.text:
        print(get_nutrient_summary_for_ai(pool_data, depletion, pft_analyses))
    elif args.output:
        result = {
            'depletion_analysis': depletion,
            'pft_analyses': pft_analyses
        }
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Results written to: {args.output}")
    else:
        result = {
            'depletion_analysis': depletion,
            'pft_analyses': pft_analyses
        }
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
