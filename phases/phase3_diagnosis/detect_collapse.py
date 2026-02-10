#!/usr/bin/env python3
"""
Phase 3 Diagnosis: Detect Vegetation Collapse Patterns

Detect periods of significant vegetation loss and analyze potential causes.
Implements "Perfect Storm" pattern detection from P_Desorption analysis.

Key patterns:
- Rapid vegetation carbon loss (>50% in short period)
- Correlated mortality spikes
- Nutrient pool depletion preceding collapse
- Drought/moisture stress correlation

Usage (Python API):
    from phases.phase3_diagnosis import detect_vegetation_collapse

    collapses = detect_vegetation_collapse(
        vegc_data=vegetation_carbon_array,
        time=time_array,
        threshold_pct=50.0
    )

Usage (CLI):
    python -m phases.phase3_diagnosis.detect_collapse \\
        --nc-file /path/to/output.nc \\
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


def detect_vegetation_collapse(
    vegc_data: np.ndarray,
    time: np.ndarray,
    threshold_pct: float = 50.0,
    window_years: float = 10.0
) -> List[Dict]:
    """
    Detect periods of significant vegetation loss.

    Args:
        vegc_data: Vegetation carbon time series (g C/m²)
        time: Time array (years)
        threshold_pct: Minimum loss percentage to flag (default 50%)
        window_years: Rolling window for loss calculation (default 10 years)

    Returns:
        List of collapse events with timing and magnitude
    """
    collapses = []

    if len(vegc_data) < 12 or len(time) < 12:
        return collapses

    # Convert to numpy arrays if needed
    vegc = np.asarray(vegc_data)
    t = np.asarray(time)

    # Calculate rolling maximum (peak biomass before potential decline)
    window_months = int(window_years * 12)
    rolling_max = np.zeros_like(vegc)

    for i in range(len(vegc)):
        start = max(0, i - window_months)
        rolling_max[i] = np.max(vegc[start:i+1])

    # Calculate loss from rolling maximum
    with np.errstate(divide='ignore', invalid='ignore'):
        loss_pct = np.where(rolling_max > 0,
                           (rolling_max - vegc) / rolling_max * 100,
                           0)

    # Find periods where loss exceeds threshold
    above_threshold = loss_pct > threshold_pct

    # Group consecutive months into collapse events
    in_collapse = False
    collapse_start = 0

    for i, above in enumerate(above_threshold):
        if above and not in_collapse:
            in_collapse = True
            collapse_start = i
        elif not above and in_collapse:
            in_collapse = False
            # Record collapse
            collapse_end = i

            # Calculate collapse metrics
            start_vegc = float(rolling_max[collapse_start])
            end_vegc = float(vegc[collapse_end - 1])
            min_vegc = float(np.min(vegc[collapse_start:collapse_end]))
            max_loss = float(np.max(loss_pct[collapse_start:collapse_end]))

            collapses.append({
                'start_idx': collapse_start,
                'end_idx': collapse_end,
                'start_time': float(t[collapse_start]),
                'end_time': float(t[collapse_end - 1]),
                'duration_months': collapse_end - collapse_start,
                'duration_years': (collapse_end - collapse_start) / 12,
                'start_vegc': start_vegc,
                'end_vegc': end_vegc,
                'min_vegc': min_vegc,
                'max_loss_pct': max_loss,
                'recovery': end_vegc > min_vegc * 1.1  # 10% recovery from minimum
            })

    # Handle ongoing collapse at end of time series
    if in_collapse:
        collapse_end = len(vegc)
        start_vegc = float(rolling_max[collapse_start])
        end_vegc = float(vegc[-1])
        min_vegc = float(np.min(vegc[collapse_start:collapse_end]))
        max_loss = float(np.max(loss_pct[collapse_start:collapse_end]))

        collapses.append({
            'start_idx': collapse_start,
            'end_idx': collapse_end,
            'start_time': float(t[collapse_start]),
            'end_time': float(t[-1]),
            'duration_months': collapse_end - collapse_start,
            'duration_years': (collapse_end - collapse_start) / 12,
            'start_vegc': start_vegc,
            'end_vegc': end_vegc,
            'min_vegc': min_vegc,
            'max_loss_pct': max_loss,
            'recovery': False,
            'ongoing': True
        })

    return collapses


def extract_vegc_timeseries(
    data_files: Dict[str, str],
    pft_ids: List[int]
) -> Dict:
    """
    Extract vegetation carbon time series from NetCDF files.

    Args:
        data_files: Dict mapping phase to file path
        pft_ids: List of PFT IDs to extract

    Returns:
        Dict with vegc data per PFT
    """
    try:
        import netCDF4 as nc
    except ImportError:
        return {}

    result = {
        'time': [],
        'phases': {},
        'pft_vegc': {pft: [] for pft in pft_ids}
    }

    time_offset = 0
    current_idx = 0

    for phase, file_path in data_files.items():
        if not Path(file_path).exists():
            continue

        with nc.Dataset(file_path, 'r') as ds:
            n_time = ds.dimensions['time'].size

            phase_time = np.arange(n_time) / 12 + time_offset + 1
            time_offset += n_time / 12

            result['phases'][phase] = (current_idx, current_idx + n_time)
            current_idx += n_time

            result['time'].append(phase_time)

            # Try different vegetation carbon variable names
            vegc_vars = ['FATES_VEGC_PF', 'FATES_STOREC_PF', 'FATES_LEAFC_PF']

            for pft_id in pft_ids:
                pft_idx = pft_id - 1

                # Try to get total vegetation C
                for var_name in vegc_vars:
                    if var_name in ds.variables:
                        arr = ds.variables[var_name][:]
                        if arr.ndim == 3:
                            vegc = arr[:, pft_idx, 0] * 1000  # kg to g
                        elif arr.ndim == 2:
                            vegc = arr[:, pft_idx] * 1000
                        else:
                            continue

                        if var_name == 'FATES_VEGC_PF':
                            # This is total, use it
                            result['pft_vegc'][pft_id].append(vegc)
                            break
                        elif var_name == 'FATES_LEAFC_PF':
                            # Use leaf as proxy if total not available
                            result['pft_vegc'][pft_id].append(vegc)
                            break

    # Concatenate
    if result['time']:
        result['time'] = np.concatenate(result['time'])
        for pft in pft_ids:
            if result['pft_vegc'][pft]:
                result['pft_vegc'][pft] = np.concatenate(result['pft_vegc'][pft])

    return result


def analyze_collapse_causes(
    data_files: Dict[str, str],
    collapse_period: Tuple[float, float],
    pft_ids: List[int]
) -> Dict:
    """
    Analyze what caused vegetation collapse during a specific period.

    Checks:
    - Mortality components (hydraulic, C starvation)
    - Nutrient pools (depletion)
    - Storage carbon (reserves)

    Args:
        data_files: Dict mapping phase to file path
        collapse_period: (start_year, end_year) of collapse
        pft_ids: PFT IDs involved

    Returns:
        Dict with cause analysis
    """
    try:
        import netCDF4 as nc
    except ImportError:
        return {}

    result = {
        'collapse_period': collapse_period,
        'pft_ids': pft_ids,
        'causes': {},
        'findings': []
    }

    start_year, end_year = collapse_period

    # Use the file that covers the collapse period (usually TRANS)
    # Find appropriate file
    nc_file = None
    for phase, fpath in data_files.items():
        if phase in ['TRANS', 'transient', 'single']:
            nc_file = fpath
            break
    if nc_file is None and data_files:
        nc_file = list(data_files.values())[-1]

    if nc_file is None or not Path(nc_file).exists():
        return result

    with nc.Dataset(nc_file, 'r') as ds:
        n_time = ds.dimensions['time'].size

        # Assume TRANS starts at year 1901 for index calculation
        # This is a simplification - should be configurable
        trans_start_year = 1901
        start_idx = max(0, int((start_year - trans_start_year) * 12))
        end_idx = min(n_time, int((end_year - trans_start_year) * 12))

        if start_idx >= end_idx:
            return result

        # Analyze mortality during collapse
        mort_vars = {
            'hydraulic': 'FATES_MORTALITY_HYDRO_CFLUX_PF',
            'cstarvation': 'FATES_MORTALITY_CSTARV_CFLUX_PF',
            'fire': 'FATES_MORTALITY_FIRE_CFLUX_PF'
        }

        scale = 1000 * 365 * 24 * 3600  # kg/m²/s to g/m²/yr (ELM: no leap years)

        for pft_id in pft_ids:
            pft_idx = pft_id - 1
            result['causes'][pft_id] = {'mortality': {}}

            for mort_name, var_name in mort_vars.items():
                if var_name in ds.variables:
                    arr = ds.variables[var_name][:]
                    if arr.ndim == 3:
                        mort = arr[start_idx:end_idx, pft_idx, 0] * scale
                    else:
                        mort = arr[start_idx:end_idx, pft_idx] * scale

                    result['causes'][pft_id]['mortality'][mort_name] = {
                        'mean': float(np.nanmean(mort)),
                        'max': float(np.nanmax(mort)),
                        'total': float(np.nansum(mort))
                    }

            # Determine dominant mortality
            mort_means = {k: v['mean'] for k, v in
                         result['causes'][pft_id]['mortality'].items()}
            if mort_means:
                dominant = max(mort_means, key=mort_means.get)
                result['causes'][pft_id]['dominant_mortality'] = dominant

                if dominant == 'hydraulic':
                    result['findings'].append({
                        'type': 'critical',
                        'pft': pft_id,
                        'message': f"PFT{pft_id}: Hydraulic failure dominated collapse"
                    })
                elif dominant == 'cstarvation':
                    result['findings'].append({
                        'type': 'critical',
                        'pft': pft_id,
                        'message': f"PFT{pft_id}: Carbon starvation dominated collapse"
                    })

            # Check storage carbon (low storage = vulnerability)
            if 'FATES_STOREC_PF' in ds.variables:
                arr = ds.variables['FATES_STOREC_PF'][:]
                if arr.ndim == 3:
                    storec = arr[start_idx:end_idx, pft_idx, 0] * 1000
                else:
                    storec = arr[start_idx:end_idx, pft_idx] * 1000

                result['causes'][pft_id]['storage_c'] = {
                    'mean': float(np.nanmean(storec)),
                    'min': float(np.nanmin(storec))
                }

                if np.nanmin(storec) < 1.0:  # Less than 1 g C/m²
                    result['findings'].append({
                        'type': 'critical',
                        'pft': pft_id,
                        'message': f"PFT{pft_id}: Storage C depleted during collapse"
                    })

    return result


def detect_perfect_storm_pattern(
    vegc_data: Dict,
    mortality_data: Optional[Dict] = None,
    nutrient_data: Optional[Dict] = None,
    pft_id: int = None
) -> Dict:
    """
    Detect the "Perfect Storm" pattern: coincident drought + P depletion + C starvation.

    This pattern was identified in the P_Desorption analysis where multiple
    stressors combined to cause ecosystem collapse.

    Args:
        vegc_data: Vegetation carbon data
        mortality_data: Optional mortality analysis output
        nutrient_data: Optional nutrient pool analysis output
        pft_id: Specific PFT to analyze

    Returns:
        Dict with Perfect Storm detection results
    """
    result = {
        'detected': False,
        'components': [],
        'severity': 'none',
        'findings': []
    }

    # Check for vegetation collapse
    if pft_id and pft_id in vegc_data.get('pft_vegc', {}):
        vegc = vegc_data['pft_vegc'][pft_id]
        time = vegc_data.get('time', [])

        if isinstance(vegc, np.ndarray) and len(vegc) > 0:
            collapses = detect_vegetation_collapse(vegc, time)
            if collapses:
                result['components'].append('vegetation_collapse')
                result['collapse_events'] = collapses

    # Check for nutrient depletion (if provided)
    if nutrient_data:
        depleted = nutrient_data.get('depleted_pools', [])
        if 'SMINP' in depleted or 'SECONDP' in depleted:
            result['components'].append('p_depletion')

    # Check for mortality spikes (if provided)
    if mortality_data and pft_id:
        pft_analysis = mortality_data.get('pft_analysis', {}).get(pft_id, {})
        causes = pft_analysis.get('causes', {})
        if causes.get('dominant_cause') in ['hydraulic', 'cstarvation']:
            result['components'].append(f"{causes['dominant_cause']}_mortality")

    # Determine if Perfect Storm pattern
    n_components = len(result['components'])
    if n_components >= 3:
        result['detected'] = True
        result['severity'] = 'critical'
        result['findings'].append({
            'type': 'critical',
            'message': f"PERFECT STORM pattern detected: {', '.join(result['components'])}"
        })
    elif n_components >= 2:
        result['detected'] = True
        result['severity'] = 'warning'
        result['findings'].append({
            'type': 'warning',
            'message': f"Partial Perfect Storm pattern: {', '.join(result['components'])}"
        })

    return result


def get_collapse_summary_for_ai(
    vegc_data: Dict,
    pft_ids: List[int]
) -> str:
    """
    Generate text summary suitable for AI reasoning.

    Args:
        vegc_data: Output from extract_vegc_timeseries()
        pft_ids: PFT IDs to summarize

    Returns:
        Formatted string summary
    """
    lines = []
    lines.append("=== Vegetation Collapse Detection Summary ===")
    lines.append("")

    time = vegc_data.get('time', [])

    for pft_id in pft_ids:
        pft_vegc = vegc_data.get('pft_vegc', {}).get(pft_id, [])

        lines.append(f"--- PFT{pft_id} ---")

        if isinstance(pft_vegc, np.ndarray) and len(pft_vegc) > 0:
            collapses = detect_vegetation_collapse(pft_vegc, time)

            if collapses:
                lines.append(f"  Collapse events detected: {len(collapses)}")
                for i, c in enumerate(collapses):
                    ongoing = " (ONGOING)" if c.get('ongoing') else ""
                    recovery = " - recovering" if c.get('recovery') else ""
                    lines.append(f"    Event {i+1}: years {c['start_time']:.1f}-{c['end_time']:.1f}")
                    lines.append(f"      Duration: {c['duration_years']:.1f} years")
                    lines.append(f"      Loss: {c['max_loss_pct']:.1f}% "
                               f"({c['start_vegc']:.1f} -> {c['min_vegc']:.1f} g C/m²)"
                               f"{ongoing}{recovery}")
            else:
                lines.append("  No collapse events detected")

            # Basic stats
            lines.append(f"  VegC range: {np.min(pft_vegc):.1f} - {np.max(pft_vegc):.1f} g C/m²")
        else:
            lines.append("  No vegetation carbon data available")

        lines.append("")

    return "\n".join(lines)


def main():
    """CLI interface for collapse detection."""
    parser = argparse.ArgumentParser(
        description="Detect vegetation collapse patterns"
    )
    parser.add_argument('--adsp-file', help='Path to ADSP phase NetCDF')
    parser.add_argument('--rgsp-file', help='Path to RGSP phase NetCDF')
    parser.add_argument('--trans-file', help='Path to TRANS phase NetCDF')
    parser.add_argument('--nc-file', help='Single NetCDF file')
    parser.add_argument('--pft-ids', type=int, nargs='+', required=True,
                        help='PFT IDs to analyze')
    parser.add_argument('--threshold', type=float, default=50.0,
                        help='Loss threshold percentage (default: 50)')
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

    # Extract vegetation carbon
    vegc_data = extract_vegc_timeseries(data_files, args.pft_ids)

    if args.text:
        print(get_collapse_summary_for_ai(vegc_data, args.pft_ids))
    else:
        result = {'pft_collapses': {}}
        time = vegc_data.get('time', [])

        for pft_id in args.pft_ids:
            pft_vegc = vegc_data.get('pft_vegc', {}).get(pft_id, [])
            if isinstance(pft_vegc, np.ndarray):
                collapses = detect_vegetation_collapse(
                    pft_vegc, time, args.threshold
                )
                result['pft_collapses'][pft_id] = collapses

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Results written to: {args.output}")
        else:
            print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
