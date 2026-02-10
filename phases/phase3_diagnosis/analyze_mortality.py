#!/usr/bin/env python3
"""
Phase 3 Diagnosis: Analyze Mortality Time Series

Extract and analyze mortality patterns by component:
- Hydraulic failure (drought stress)
- Carbon starvation (insufficient carbon)
- Fire mortality
- Background mortality (senescence)

Useful for detecting vegetation collapse patterns and diagnosing causes.

Usage (Python API):
    from phases.phase3_diagnosis import extract_mortality_timeseries

    result = extract_mortality_timeseries(
        data_files={'ADSP': 'adsp.nc', 'RGSP': 'rgsp.nc', 'TRANS': 'trans.nc'},
        pft_ids=[7, 9, 10]
    )

Usage (CLI):
    python -m phases.phase3_diagnosis.analyze_mortality \\
        --adsp-file /path/to/adsp.nc \\
        --rgsp-file /path/to/rgsp.nc \\
        --trans-file /path/to/trans.nc \\
        --pft-ids 7 9 10

Author: Jing Tao with Claude
Adapted from: plot_mortality_timeseries_dsp2x.py (December 2025)
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

# Mortality variable names and display labels
MORTALITY_VARS = {
    'total': 'FATES_MORTALITY_CFLUX_PF',
    'hydraulic': 'FATES_MORTALITY_HYDRO_CFLUX_PF',
    'cstarvation': 'FATES_MORTALITY_CSTARV_CFLUX_PF',
    'fire': 'FATES_MORTALITY_FIRE_CFLUX_PF'
}

# Unit conversion: kg C/m²/s to g C/m²/yr
KG_TO_G = 1000
SEC_PER_YEAR = 365 * 24 * 3600  # ELM uses no-leap-year calendar
FLUX_SCALE = KG_TO_G * SEC_PER_YEAR


def extract_mortality_timeseries(
    data_files: Dict[str, str],
    pft_ids: List[int]
) -> Dict:
    """
    Extract mortality components across all simulation phases.

    Args:
        data_files: Dict mapping phase name to file path
                    e.g., {'ADSP': 'adsp.nc', 'RGSP': 'rgsp.nc', 'TRANS': 'trans.nc'}
        pft_ids: List of PFT IDs to extract

    Returns:
        Dict with mortality data:
        {
            'time': array,  # Combined time axis
            'phases': {'ADSP': (0, 2400), ...},  # Index ranges per phase
            'pft_data': {
                7: {
                    'total': array,
                    'hydraulic': array,
                    'cstarvation': array,
                    'fire': array
                },
                ...
            }
        }
    """
    try:
        import netCDF4 as nc
    except ImportError:
        logger.error("netCDF4 required")
        return {}

    result = {
        'time': [],
        'phases': {},
        'pft_data': {pft_id: {} for pft_id in pft_ids}
    }

    phase_data = {}
    time_offset = 0
    current_idx = 0

    for phase, file_path in data_files.items():
        if not Path(file_path).exists():
            logger.warning(f"File not found: {file_path}")
            continue

        with nc.Dataset(file_path, 'r') as ds:
            n_time = ds.dimensions['time'].size

            # Create time axis for this phase
            phase_time = np.arange(n_time) / 12 + time_offset + 1
            time_offset += n_time / 12

            # Record phase bounds
            result['phases'][phase] = (current_idx, current_idx + n_time)
            current_idx += n_time

            # Store time
            phase_data[phase] = {'time': phase_time}

            # Extract mortality for each PFT
            for pft_id in pft_ids:
                pft_idx = pft_id - 1  # 0-indexed

                if pft_id not in phase_data[phase]:
                    phase_data[phase][pft_id] = {}

                for mort_type, var_name in MORTALITY_VARS.items():
                    if var_name in ds.variables:
                        arr = ds.variables[var_name][:]
                        # Handle dimensions: (time, pft) or (time, pft, spatial)
                        if arr.ndim == 3:
                            mort_data = arr[:, pft_idx, 0] * FLUX_SCALE
                        elif arr.ndim == 2:
                            mort_data = arr[:, pft_idx] * FLUX_SCALE
                        else:
                            mort_data = np.zeros(n_time)

                        phase_data[phase][pft_id][mort_type] = mort_data

    # Concatenate all phases
    all_time = []
    for phase in data_files.keys():
        if phase in phase_data:
            all_time.append(phase_data[phase]['time'])

    if all_time:
        result['time'] = np.concatenate(all_time)

        for pft_id in pft_ids:
            for mort_type in MORTALITY_VARS.keys():
                arrays = []
                for phase in data_files.keys():
                    if phase in phase_data and pft_id in phase_data[phase]:
                        arr = phase_data[phase][pft_id].get(mort_type, None)
                        if arr is not None:
                            arrays.append(arr)
                if arrays:
                    result['pft_data'][pft_id][mort_type] = np.concatenate(arrays)

    return result


def detect_mortality_events(
    mortality_data: Dict,
    pft_id: int,
    threshold_std: float = 2.0
) -> List[Dict]:
    """
    Detect significant mortality events (spikes/crashes).

    Args:
        mortality_data: Output from extract_mortality_timeseries()
        pft_id: PFT to analyze
        threshold_std: Number of standard deviations above mean to flag

    Returns:
        List of detected events with timing and magnitude
    """
    events = []

    pft_data = mortality_data.get('pft_data', {}).get(pft_id, {})
    time = mortality_data.get('time', [])

    if 'total' not in pft_data or len(time) == 0:
        return events

    total_mort = pft_data['total']
    mean_mort = np.nanmean(total_mort)
    std_mort = np.nanstd(total_mort)

    threshold = mean_mort + threshold_std * std_mort

    # Find exceedances
    above_threshold = total_mort > threshold

    # Group consecutive months into events
    in_event = False
    event_start = 0

    for i, above in enumerate(above_threshold):
        if above and not in_event:
            in_event = True
            event_start = i
        elif not above and in_event:
            in_event = False
            # Record event
            event_end = i
            event_mort = total_mort[event_start:event_end]

            events.append({
                'start_idx': event_start,
                'end_idx': event_end,
                'start_time': float(time[event_start]),
                'end_time': float(time[event_end - 1]) if event_end > 0 else float(time[event_start]),
                'duration_months': event_end - event_start,
                'peak_mortality': float(np.max(event_mort)),
                'mean_mortality': float(np.mean(event_mort)),
                'severity': float(np.max(event_mort) / std_mort) if std_mort > 0 else 0
            })

    # Handle event that extends to end
    if in_event:
        event_end = len(total_mort)
        event_mort = total_mort[event_start:event_end]
        events.append({
            'start_idx': event_start,
            'end_idx': event_end,
            'start_time': float(time[event_start]),
            'end_time': float(time[-1]),
            'duration_months': event_end - event_start,
            'peak_mortality': float(np.max(event_mort)),
            'mean_mortality': float(np.mean(event_mort)),
            'severity': float(np.max(event_mort) / std_mort) if std_mort > 0 else 0
        })

    return events


def diagnose_mortality_causes(
    mortality_data: Dict,
    pft_id: int,
    year_range: Optional[Tuple[int, int]] = None
) -> Dict:
    """
    Analyze which mortality component dominates for a PFT.

    Args:
        mortality_data: Output from extract_mortality_timeseries()
        pft_id: PFT to analyze
        year_range: Optional (start_year, end_year) to focus on

    Returns:
        Dict with cause analysis
    """
    result = {
        'pft_id': pft_id,
        'components': {},
        'dominant_cause': None,
        'findings': []
    }

    pft_data = mortality_data.get('pft_data', {}).get(pft_id, {})
    time = mortality_data.get('time', [])

    if not pft_data or len(time) == 0:
        return result

    # Filter by year range if specified
    if year_range:
        start_yr, end_yr = year_range
        mask = (time >= start_yr) & (time <= end_yr)
    else:
        mask = np.ones(len(time), dtype=bool)

    # Analyze each component
    for mort_type in ['total', 'hydraulic', 'cstarvation', 'fire']:
        if mort_type in pft_data:
            data = pft_data[mort_type][mask]
            result['components'][mort_type] = {
                'mean': float(np.nanmean(data)),
                'max': float(np.nanmax(data)),
                'std': float(np.nanstd(data)),
                'total': float(np.nansum(data))
            }

    # Determine dominant cause
    component_means = {}
    for comp in ['hydraulic', 'cstarvation', 'fire']:
        if comp in result['components']:
            component_means[comp] = result['components'][comp]['mean']

    if component_means:
        dominant = max(component_means, key=component_means.get)
        result['dominant_cause'] = dominant

        total_mean = sum(component_means.values())
        if total_mean > 0:
            result['cause_fractions'] = {
                k: v / total_mean for k, v in component_means.items()
            }

            # Generate findings
            if result['cause_fractions'].get('hydraulic', 0) > 0.5:
                result['findings'].append({
                    'type': 'critical',
                    'message': f"Hydraulic failure dominates mortality ({result['cause_fractions']['hydraulic']*100:.0f}%)"
                })
            if result['cause_fractions'].get('cstarvation', 0) > 0.5:
                result['findings'].append({
                    'type': 'critical',
                    'message': f"Carbon starvation dominates mortality ({result['cause_fractions']['cstarvation']*100:.0f}%)"
                })

    return result


def get_mortality_summary_for_ai(
    mortality_data: Dict,
    pft_ids: List[int]
) -> str:
    """
    Generate a text summary suitable for AI reasoning.

    Args:
        mortality_data: Output from extract_mortality_timeseries()
        pft_ids: List of PFT IDs to summarize

    Returns:
        Formatted string summary
    """
    lines = []
    lines.append("=== Mortality Analysis Summary ===")
    lines.append("")

    phases = mortality_data.get('phases', {})
    if phases:
        lines.append(f"Phases analyzed: {list(phases.keys())}")
        lines.append("")

    for pft_id in pft_ids:
        lines.append(f"--- PFT{pft_id} ---")

        causes = diagnose_mortality_causes(mortality_data, pft_id)
        if causes.get('dominant_cause'):
            lines.append(f"  Dominant cause: {causes['dominant_cause']}")

        fractions = causes.get('cause_fractions', {})
        if fractions:
            lines.append("  Cause breakdown:")
            for cause, frac in sorted(fractions.items(), key=lambda x: -x[1]):
                lines.append(f"    - {cause}: {frac*100:.1f}%")

        events = detect_mortality_events(mortality_data, pft_id)
        if events:
            lines.append(f"  Mortality events detected: {len(events)}")
            for i, event in enumerate(events[:3]):  # Top 3
                lines.append(f"    Event {i+1}: year {event['start_time']:.1f}-{event['end_time']:.1f}, "
                           f"severity {event['severity']:.1f} std")

        for finding in causes.get('findings', []):
            lines.append(f"  {finding['type'].upper()}: {finding['message']}")

        lines.append("")

    return "\n".join(lines)


def main():
    """CLI interface for mortality analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze mortality time series by component"
    )
    parser.add_argument('--adsp-file',
                        help='Path to ADSP phase NetCDF file')
    parser.add_argument('--rgsp-file',
                        help='Path to RGSP phase NetCDF file')
    parser.add_argument('--trans-file',
                        help='Path to TRANS phase NetCDF file')
    parser.add_argument('--nc-file',
                        help='Single NetCDF file (alternative to phase files)')
    parser.add_argument('--pft-ids', type=int, nargs='+', required=True,
                        help='PFT IDs to analyze')
    parser.add_argument('--output', '-o',
                        help='Output JSON file (default: stdout)')
    parser.add_argument('--text', action='store_true',
                        help='Output text summary instead of JSON')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Build data files dict
    if args.nc_file:
        data_files = {'single': args.nc_file}
    else:
        data_files = {}
        if args.adsp_file:
            data_files['ADSP'] = args.adsp_file
        if args.rgsp_file:
            data_files['RGSP'] = args.rgsp_file
        if args.trans_file:
            data_files['TRANS'] = args.trans_file

    if not data_files:
        print("ERROR: At least one data file required")
        sys.exit(1)

    mortality_data = extract_mortality_timeseries(data_files, args.pft_ids)

    if args.text:
        print(get_mortality_summary_for_ai(mortality_data, args.pft_ids))
    elif args.output:
        # Convert numpy arrays to lists for JSON
        output = {
            'phases': mortality_data.get('phases', {}),
            'pft_analysis': {}
        }
        for pft_id in args.pft_ids:
            output['pft_analysis'][pft_id] = {
                'causes': diagnose_mortality_causes(mortality_data, pft_id),
                'events': detect_mortality_events(mortality_data, pft_id)
            }
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Results written to: {args.output}")
    else:
        output = {
            'phases': mortality_data.get('phases', {}),
            'pft_analysis': {}
        }
        for pft_id in args.pft_ids:
            output['pft_analysis'][pft_id] = {
                'causes': diagnose_mortality_causes(mortality_data, pft_id),
                'events': detect_mortality_events(mortality_data, pft_id)
            }
        print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
