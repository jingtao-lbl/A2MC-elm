#!/usr/bin/env python3
"""
Phase 3 Diagnosis: Diagnose PFT Limitations

Test hypotheses about what's limiting a PFT's performance:
1. Allocation dynamics (L2FR response)
2. Nutrient limitation (N/P starvation)
3. Light competition (shading by other PFTs)
4. Storage dynamics (carbon buffering)

Usage (Python API):
    from phases.phase3_diagnosis import run_pft_diagnosis

    result = run_pft_diagnosis(
        nc_file="/path/to/output.nc",
        pft_id=10,
        targets={'leaf': 82.7, 'froot': 382.1},
        comparison_pfts=[7, 9]
    )

Usage (CLI):
    python -m phases.phase3_diagnosis.diagnose_pft_limitations \\
        --nc-file /path/to/output.nc \\
        --pft-id 10 \\
        --targets '{"leaf": 82.7, "froot": 382.1}'

Author: Jing Tao with Claude
Adapted from: diagnose_pft10_limitations.py (December 2025)
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

try:
    from tools.fates_utils import get_szpf_range, aggregate_szpf_by_pft
except ImportError:
    # Fallback implementations
    def get_szpf_range(pft_id: int, fates_pft: int = 12) -> Tuple[int, int]:
        """Get SZPF index range for a PFT."""
        start = (pft_id - 1) * 13
        end = start + 12
        return start, end

    def aggregate_szpf_by_pft(szpf_data: np.ndarray, pft_id: int, fates_pft: int = 12) -> np.ndarray:
        """Sum SZPF data across size classes for a given PFT."""
        start, end = get_szpf_range(pft_id, fates_pft)
        return np.sum(szpf_data[:, start:end+1], axis=1)

logger = logging.getLogger(__name__)


def load_netcdf_data(nc_file: str, pft_ids: List[int]) -> Dict:
    """
    Load relevant variables from NetCDF output file.

    Args:
        nc_file: Path to NetCDF file
        pft_ids: List of PFT IDs to load data for

    Returns:
        Dict with loaded data arrays
    """
    try:
        import netCDF4 as nc
    except ImportError:
        logger.error("netCDF4 required for loading data")
        return {}

    data = {'pft_data': {}}

    with nc.Dataset(nc_file, 'r') as ds:
        # Get time dimension
        data['time'] = ds.variables['time'][:]
        n_time = len(data['time'])

        # Site-level variables
        site_vars = ['FATES_LAI', 'FATES_GPP', 'FATES_NPP', 'FATES_L2FR']
        for var_name in site_vars:
            if var_name in ds.variables:
                arr = ds.variables[var_name][:]
                # Handle spatial dimension
                if arr.ndim > 1:
                    arr = arr[:, 0]
                data[var_name] = arr

        # PFT-level variables (fates_levpft dimension)
        pf_vars = ['FATES_LEAFC_PF', 'FATES_STOREC_PF', 'FATES_GPP_PF',
                   'FATES_NPP_PF', 'FATES_L2FR_CANOPY_REC_PF', 'FATES_L2FR_USTORY_REC_PF']

        for pft_id in pft_ids:
            pft_idx = pft_id - 1  # 0-indexed
            data['pft_data'][pft_id] = {}

            for var_name in pf_vars:
                if var_name in ds.variables:
                    arr = ds.variables[var_name][:]
                    if arr.ndim >= 2:
                        if arr.ndim == 3:
                            data['pft_data'][pft_id][var_name] = arr[:, pft_idx, 0]
                        else:
                            data['pft_data'][pft_id][var_name] = arr[:, pft_idx]

        # SZPF-level variables
        szpf_vars = ['FATES_LEAFC_SZPF', 'FATES_FROOTC_SZPF',
                     'FATES_LEAF_ALLOC_SZPF', 'FATES_FROOT_ALLOC_SZPF',
                     'FATES_NDEMAND_SZPF', 'FATES_PDEMAND_SZPF',
                     'FATES_NUPTAKE_SZPF', 'FATES_PUPTAKE_SZPF']

        for pft_id in pft_ids:
            start, end = get_szpf_range(pft_id)

            for var_name in szpf_vars:
                if var_name in ds.variables:
                    arr = ds.variables[var_name][:]
                    if arr.ndim == 3:
                        # Sum across size classes for this PFT
                        data['pft_data'][pft_id][var_name] = np.sum(arr[:, start:end+1, 0], axis=1)
                    elif arr.ndim == 2:
                        data['pft_data'][pft_id][var_name] = np.sum(arr[:, start:end+1], axis=1)

    return data


def analyze_allocation_dynamics(
    data: Dict,
    pft_id: int,
    targets: Dict[str, float]
) -> Dict:
    """
    Test Hypothesis: Is allocation responding dynamically or locked?

    Analyzes L2FR (leaf-to-fine-root ratio) dynamics and compares actual
    biomass ratios to targets.

    Args:
        data: Output from load_netcdf_data()
        pft_id: PFT ID to analyze
        targets: Dict with 'leaf' and 'froot' target values (g C/m²)

    Returns:
        Dict with allocation analysis results
    """
    result = {
        'hypothesis': 'Allocation dynamics',
        'pft_id': pft_id,
        'findings': []
    }

    pft_data = data.get('pft_data', {}).get(pft_id, {})

    # Check L2FR canopy/understory
    if 'FATES_L2FR_CANOPY_REC_PF' in pft_data:
        l2fr_canopy = pft_data['FATES_L2FR_CANOPY_REC_PF']
        result['l2fr_canopy'] = {
            'mean': float(np.nanmean(l2fr_canopy)),
            'std': float(np.nanstd(l2fr_canopy)),
            'min': float(np.nanmin(l2fr_canopy)),
            'max': float(np.nanmax(l2fr_canopy))
        }

        # Check if L2FR varies (indicates dynamic response)
        cv = result['l2fr_canopy']['std'] / max(result['l2fr_canopy']['mean'], 1e-10)
        result['l2fr_canopy']['cv'] = float(cv)

        if cv < 0.1:
            result['findings'].append({
                'type': 'warning',
                'message': f'L2FR nearly constant (CV={cv:.3f}), allocation may be locked'
            })

    # Calculate actual L2FR from biomass
    if 'FATES_LEAFC_SZPF' in pft_data and 'FATES_FROOTC_SZPF' in pft_data:
        leaf_c = pft_data['FATES_LEAFC_SZPF'] * 1000  # kg to g
        froot_c = pft_data['FATES_FROOTC_SZPF'] * 1000

        # Avoid division by zero
        froot_safe = np.where(froot_c > 0, froot_c, np.nan)
        actual_l2fr = leaf_c / froot_safe

        result['actual_l2fr'] = {
            'mean': float(np.nanmean(actual_l2fr)),
            'std': float(np.nanstd(actual_l2fr)),
            'min': float(np.nanmin(actual_l2fr)),
            'max': float(np.nanmax(actual_l2fr))
        }

        # Get final period values (last 12 months)
        final_leaf = float(np.mean(leaf_c[-12:]))
        final_froot = float(np.mean(froot_c[-12:]))

        result['biomass'] = {
            'leaf': final_leaf,
            'froot': final_froot,
            'actual_l2fr': final_leaf / max(final_froot, 1e-10)
        }

        # Compare to targets
        if 'leaf' in targets and 'froot' in targets:
            target_l2fr = targets['leaf'] / targets['froot']
            result['target_comparison'] = {
                'target_leaf': targets['leaf'],
                'target_froot': targets['froot'],
                'target_l2fr': target_l2fr,
                'leaf_error_pct': 100 * (final_leaf - targets['leaf']) / targets['leaf'],
                'froot_error_pct': 100 * (final_froot - targets['froot']) / targets['froot']
            }

            if final_leaf < targets['leaf'] * 0.5:
                result['findings'].append({
                    'type': 'critical',
                    'message': f"Leaf biomass severely low ({final_leaf:.1f} vs target {targets['leaf']:.1f})"
                })

            if final_froot > targets['froot'] * 2:
                result['findings'].append({
                    'type': 'warning',
                    'message': f"Fine root biomass high ({final_froot:.1f} vs target {targets['froot']:.1f})"
                })

    return result


def analyze_nutrient_limitation(
    data: Dict,
    pft_id: int
) -> Dict:
    """
    Test Hypothesis: Is PFT nutrient limited (N or P)?

    Compares nutrient demand to uptake to identify limitation.

    Args:
        data: Output from load_netcdf_data()
        pft_id: PFT ID to analyze

    Returns:
        Dict with nutrient limitation analysis results
    """
    result = {
        'hypothesis': 'Nutrient limitation',
        'pft_id': pft_id,
        'findings': []
    }

    pft_data = data.get('pft_data', {}).get(pft_id, {})

    # Unit conversion: kg/m²/s to kg/m²/year
    seconds_per_year = 365 * 24 * 3600  # ELM uses no-leap-year calendar

    # Nitrogen analysis
    if 'FATES_NDEMAND_SZPF' in pft_data:
        n_demand = pft_data['FATES_NDEMAND_SZPF'] * seconds_per_year  # Annual

        result['nitrogen'] = {
            'demand_mean': float(np.nanmean(n_demand)),
            'demand_max': float(np.nanmax(n_demand))
        }

        if 'FATES_NUPTAKE_SZPF' in pft_data:
            n_uptake = pft_data['FATES_NUPTAKE_SZPF'] * seconds_per_year
            n_ratio = np.where(n_demand > 0, n_uptake / n_demand, 1.0)

            result['nitrogen']['uptake_mean'] = float(np.nanmean(n_uptake))
            result['nitrogen']['supply_demand_ratio'] = float(np.nanmean(n_ratio))

            if np.nanmean(n_ratio) < 0.8:
                result['findings'].append({
                    'type': 'critical',
                    'message': f"N limitation detected (uptake/demand = {np.nanmean(n_ratio):.2f})"
                })
            elif np.nanmean(n_ratio) < 0.95:
                result['findings'].append({
                    'type': 'warning',
                    'message': f"Moderate N limitation (uptake/demand = {np.nanmean(n_ratio):.2f})"
                })

    # Phosphorus analysis
    if 'FATES_PDEMAND_SZPF' in pft_data:
        p_demand = pft_data['FATES_PDEMAND_SZPF'] * seconds_per_year

        result['phosphorus'] = {
            'demand_mean': float(np.nanmean(p_demand)),
            'demand_max': float(np.nanmax(p_demand))
        }

        if 'FATES_PUPTAKE_SZPF' in pft_data:
            p_uptake = pft_data['FATES_PUPTAKE_SZPF'] * seconds_per_year
            p_ratio = np.where(p_demand > 0, p_uptake / p_demand, 1.0)

            result['phosphorus']['uptake_mean'] = float(np.nanmean(p_uptake))
            result['phosphorus']['supply_demand_ratio'] = float(np.nanmean(p_ratio))

            if np.nanmean(p_ratio) < 0.8:
                result['findings'].append({
                    'type': 'critical',
                    'message': f"P limitation detected (uptake/demand = {np.nanmean(p_ratio):.2f})"
                })
            elif np.nanmean(p_ratio) < 0.95:
                result['findings'].append({
                    'type': 'warning',
                    'message': f"Moderate P limitation (uptake/demand = {np.nanmean(p_ratio):.2f})"
                })

    # Determine primary limitation
    n_ratio = result.get('nitrogen', {}).get('supply_demand_ratio', 1.0)
    p_ratio = result.get('phosphorus', {}).get('supply_demand_ratio', 1.0)

    if n_ratio < p_ratio and n_ratio < 0.95:
        result['primary_limitation'] = 'nitrogen'
    elif p_ratio < n_ratio and p_ratio < 0.95:
        result['primary_limitation'] = 'phosphorus'
    elif n_ratio < 0.95 and p_ratio < 0.95:
        result['primary_limitation'] = 'co-limited'
    else:
        result['primary_limitation'] = 'none'

    return result


def analyze_light_competition(
    data: Dict,
    pft_ids: List[int]
) -> Dict:
    """
    Test Hypothesis: Is there inter-PFT light competition?

    Compares GPP and leaf biomass between PFTs to assess competition.

    Args:
        data: Output from load_netcdf_data()
        pft_ids: List of PFT IDs to compare

    Returns:
        Dict with light competition analysis results
    """
    result = {
        'hypothesis': 'Light competition',
        'pft_ids': pft_ids,
        'findings': [],
        'pft_comparison': {}
    }

    for pft_id in pft_ids:
        pft_data = data.get('pft_data', {}).get(pft_id, {})

        pft_result = {'pft_id': pft_id}

        # GPP analysis
        if 'FATES_GPP_PF' in pft_data:
            gpp = pft_data['FATES_GPP_PF']
            # Convert kg C/m²/s to g C/m²/day
            gpp_daily = gpp * 86400 * 1000
            pft_result['gpp_daily_mean'] = float(np.nanmean(gpp_daily))
            pft_result['gpp_daily_max'] = float(np.nanmax(gpp_daily))

        # Leaf biomass
        if 'FATES_LEAFC_SZPF' in pft_data:
            leaf_c = pft_data['FATES_LEAFC_SZPF'] * 1000  # to g/m²
            pft_result['leaf_c_mean'] = float(np.nanmean(leaf_c))

        result['pft_comparison'][pft_id] = pft_result

    # Compare PFTs if we have multiple
    if len(pft_ids) >= 2:
        gpps = []
        for pft_id in pft_ids:
            gpp = result['pft_comparison'].get(pft_id, {}).get('gpp_daily_mean', 0)
            gpps.append((pft_id, gpp))

        gpps.sort(key=lambda x: x[1], reverse=True)

        if len(gpps) >= 2 and gpps[1][1] > 0:
            ratio = gpps[0][1] / gpps[1][1]
            if ratio > 5:
                result['findings'].append({
                    'type': 'critical',
                    'message': f"Strong competition: PFT{gpps[0][0]} >> PFT{gpps[1][0]} (GPP ratio {ratio:.1f})"
                })
            elif ratio > 2:
                result['findings'].append({
                    'type': 'warning',
                    'message': f"Moderate competition: PFT{gpps[0][0]} > PFT{gpps[1][0]} (GPP ratio {ratio:.1f})"
                })

        result['dominant_pft'] = gpps[0][0] if gpps else None

    return result


def analyze_allocation_rates(
    data: Dict,
    pft_id: int
) -> Dict:
    """
    Analyze actual allocation rates (not just L2FR target).

    Args:
        data: Output from load_netcdf_data()
        pft_id: PFT ID to analyze

    Returns:
        Dict with allocation rate analysis
    """
    result = {
        'hypothesis': 'Allocation rates',
        'pft_id': pft_id,
        'findings': []
    }

    pft_data = data.get('pft_data', {}).get(pft_id, {})

    # Unit conversion: kg C/m²/s to g C/m²/year
    scale = 365 * 24 * 3600 * 1000  # ELM: no-leap-year calendar

    if 'FATES_LEAF_ALLOC_SZPF' in pft_data:
        leaf_alloc = pft_data['FATES_LEAF_ALLOC_SZPF'] * scale
        result['leaf_allocation'] = {
            'mean': float(np.nanmean(leaf_alloc)),
            'max': float(np.nanmax(leaf_alloc))
        }

    if 'FATES_FROOT_ALLOC_SZPF' in pft_data:
        froot_alloc = pft_data['FATES_FROOT_ALLOC_SZPF'] * scale
        result['froot_allocation'] = {
            'mean': float(np.nanmean(froot_alloc)),
            'max': float(np.nanmax(froot_alloc))
        }

    # Calculate allocation L2FR
    if 'leaf_allocation' in result and 'froot_allocation' in result:
        if result['froot_allocation']['mean'] > 0:
            alloc_l2fr = result['leaf_allocation']['mean'] / result['froot_allocation']['mean']
            result['allocation_l2fr'] = float(alloc_l2fr)

            if alloc_l2fr < 0.5:
                result['findings'].append({
                    'type': 'warning',
                    'message': f"Low allocation L2FR ({alloc_l2fr:.2f}) - root-biased"
                })

    return result


def run_pft_diagnosis(
    nc_file: str,
    pft_id: int,
    targets: Dict[str, float],
    comparison_pfts: Optional[List[int]] = None
) -> Dict:
    """
    Run all diagnostic tests for a PFT.

    Args:
        nc_file: Path to NetCDF output file
        pft_id: PFT ID to diagnose
        targets: Dict with 'leaf' and 'froot' target values (g C/m²)
        comparison_pfts: Other PFTs to compare for competition analysis

    Returns:
        Comprehensive diagnosis result
    """
    # Determine all PFTs to load
    pft_ids = [pft_id]
    if comparison_pfts:
        pft_ids = list(set(pft_ids + comparison_pfts))

    # Load data
    data = load_netcdf_data(nc_file, pft_ids)

    if not data.get('pft_data'):
        return {
            'pft_id': pft_id,
            'error': 'Failed to load data from NetCDF file',
            'nc_file': nc_file
        }

    result = {
        'pft_id': pft_id,
        'nc_file': nc_file,
        'targets': targets,
        'hypotheses_tested': [],
        'all_findings': [],
        'summary': {}
    }

    # Test each hypothesis
    alloc = analyze_allocation_dynamics(data, pft_id, targets)
    result['hypotheses_tested'].append(alloc)
    result['all_findings'].extend(alloc.get('findings', []))

    nutrient = analyze_nutrient_limitation(data, pft_id)
    result['hypotheses_tested'].append(nutrient)
    result['all_findings'].extend(nutrient.get('findings', []))

    if comparison_pfts:
        competition = analyze_light_competition(data, pft_ids)
        result['hypotheses_tested'].append(competition)
        result['all_findings'].extend(competition.get('findings', []))

    rates = analyze_allocation_rates(data, pft_id)
    result['hypotheses_tested'].append(rates)
    result['all_findings'].extend(rates.get('findings', []))

    # Summarize
    critical = [f for f in result['all_findings'] if f.get('type') == 'critical']
    warnings = [f for f in result['all_findings'] if f.get('type') == 'warning']

    result['summary'] = {
        'critical_issues': len(critical),
        'warnings': len(warnings),
        'primary_issues': [f['message'] for f in critical],
        'nutrient_limitation': nutrient.get('primary_limitation', 'unknown')
    }

    return result


def get_diagnosis_summary_for_ai(diagnosis: Dict) -> str:
    """
    Generate a text summary suitable for AI reasoning.

    Args:
        diagnosis: Output from run_pft_diagnosis()

    Returns:
        Formatted string summary
    """
    lines = []
    lines.append(f"=== PFT{diagnosis['pft_id']} Diagnosis Summary ===")
    lines.append("")

    summary = diagnosis.get('summary', {})
    lines.append(f"Critical issues: {summary.get('critical_issues', 0)}")
    lines.append(f"Warnings: {summary.get('warnings', 0)}")
    lines.append(f"Primary nutrient limitation: {summary.get('nutrient_limitation', 'unknown')}")
    lines.append("")

    if summary.get('primary_issues'):
        lines.append("Critical Issues:")
        for issue in summary['primary_issues']:
            lines.append(f"  - {issue}")
        lines.append("")

    for hypo in diagnosis.get('hypotheses_tested', []):
        lines.append(f"--- {hypo.get('hypothesis', 'Unknown')} ---")
        for finding in hypo.get('findings', []):
            prefix = "CRITICAL:" if finding['type'] == 'critical' else "Warning:"
            lines.append(f"  {prefix} {finding['message']}")
        lines.append("")

    return "\n".join(lines)


def main():
    """CLI interface for PFT diagnosis."""
    parser = argparse.ArgumentParser(
        description="Diagnose PFT limitations (allocation, nutrients, competition)"
    )
    parser.add_argument('--nc-file', required=True,
                        help='Path to NetCDF output file')
    parser.add_argument('--pft-id', type=int, required=True,
                        help='PFT ID to diagnose (1-indexed)')
    parser.add_argument('--targets', required=True,
                        help='JSON string or file with targets {"leaf": X, "froot": Y}')
    parser.add_argument('--comparison-pfts', type=int, nargs='+',
                        help='Other PFT IDs for competition analysis')
    parser.add_argument('--output', '-o',
                        help='Output JSON file (default: stdout)')
    parser.add_argument('--text', action='store_true',
                        help='Output text summary instead of JSON')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Parse targets
    if args.targets.startswith('{'):
        targets = json.loads(args.targets)
    else:
        with open(args.targets) as f:
            targets = json.load(f)

    result = run_pft_diagnosis(
        args.nc_file,
        args.pft_id,
        targets,
        args.comparison_pfts
    )

    if args.text:
        print(get_diagnosis_summary_for_ai(result))
    elif args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Results written to: {args.output}")
    else:
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
