#!/usr/bin/env python3
"""
Phase 2 Screening: Ensemble Biomass Visualization

Generic plotting module for visualizing ensemble simulation results against
validation targets. Creates N_PFTs × N_vars panel figures showing:
- Top N ensemble members as thin purple lines
- Best NRMSE case highlighted in red
- Most-targets-met case highlighted in blue
- Observations with uncertainty bars and ±tolerance range boxes

Designed to be called by the AI orchestrator during Phase 2 screening or
interactively for offline analysis.

Usage (from orchestrator or AI):
    from phases.phase2_screening.plot_screening import plot_ensemble_biomass

    fig_path = plot_ensemble_biomass(
        data_dir="/path/to/extracted_data",
        ranked_cases=[{'case_num': 1386, 'composite_nrmse': 0.45, 'n_satisfied': 3}, ...],
        targets={'PFT10_leaf': {'observed': 82.65, 'uncertainty': 0.2}, ...},
        pft_ids=[7, 9, 10],
        output_path="/path/to/output/ensemble_biomass.png"
    )

Usage (standalone):
    python plot_screening.py --data-dir /path/to/data --top-n 100

Author: Jing Tao with Claude
Created: February 2026
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

# HPC-safe backend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

logger = logging.getLogger(__name__)

# Default figure DPI (match plot_diagnostics.py)
FIGURE_DPI = 600

# PFT labels come from the base param file's fates_pftname via
# tools.fates_utils.get_pft_display_names() — no hardcoded api-version-specific map.

# Variable configurations
VARIABLE_CONFIGS = {
    'leaf': {
        'nc_var': 'FATES_LEAFC_SZPF',
        'factor': 1000,  # kg/m² to g/m²
        'unit': 'Leaf C (g C m$^{-2}$)',
        'title': 'Leaf Biomass',
    },
    'fineroot': {
        'nc_var': 'FATES_FROOTC_SZPF',
        'factor': 1000,
        'unit': 'Fineroot C (g C m$^{-2}$)',
        'title': 'Fineroot Biomass',
    },
}

# Color scheme
ENSEMBLE_COLOR = [0.7, 0.6, 1.0]  # light purple
ENSEMBLE_ALPHA = 0.5
ENSEMBLE_LINEWIDTH = 1

BEST_NRMSE_COLOR = 'red'
BEST_NRMSE_LINEWIDTH = 3

BEST_TARGETS_COLOR = 'blue'
BEST_TARGETS_LINEWIDTH = 3


# =============================================================================
# Data Loading Helpers
# =============================================================================

def _get_case_name_pattern():
    """Get case name pattern from A2MC config or environment."""
    import os
    try:
        from tools.config import config as a2mc_config
        return a2mc_config.CASE_NAME_PATTERN
    except ImportError:
        prefix = os.environ.get('A2MC_ENSEMBLE_PREFIX', '')
        return os.environ.get(
            'A2MC_CASE_NAME_PATTERN', f"{prefix}{{N}}_{{PHASE}}")


def _build_case_regex(case_pattern: str) -> re.Pattern:
    """Build regex to extract case number from filenames."""
    marker = '___CASENUM___'
    template = case_pattern.format(N=marker, PHASE='TRANS')
    escaped = re.escape(template)
    regex_str = escaped.replace(marker, r'(\d+)') + '_all_variables_monthly'
    return re.compile(regex_str)


def get_available_cases(data_dir: Path, case_pattern: str = None) -> List[int]:
    """Scan directory to find all available case numbers."""
    if case_pattern is None:
        case_pattern = _get_case_name_pattern()

    pattern = _build_case_regex(case_pattern)
    cases = []
    for f in data_dir.glob('*_all_variables_monthly_*.nc'):
        match = pattern.search(f.name)
        if match:
            cases.append(int(match.group(1)))
    return sorted(cases)


def load_nc_timeseries(
    case_num: int,
    var_name: str,
    data_dir: Path,
    case_pattern: str = None,
    year_start: int = 1901,
    year_end: int = 2019,
    file_pattern: str = '{case_name}_all_variables_monthly_{year_start}_{year_end}.nc'
) -> np.ndarray:
    """Load SZPF timeseries from extracted NetCDF file."""
    try:
        import netCDF4 as nc
    except ImportError:
        return None

    if case_pattern is None:
        case_pattern = _get_case_name_pattern()

    case_name = case_pattern.format(N=case_num, PHASE='TRANS')
    nc_file = data_dir / file_pattern.format(
        case_name=case_name,
        year_start=year_start,
        year_end=year_end
    )

    n_months = (year_end - year_start + 1) * 12

    if nc_file.exists():
        try:
            with nc.Dataset(nc_file, 'r') as ds:
                if var_name in ds.variables:
                    data = ds.variables[var_name][:]
                    data = np.squeeze(data)
                    if data.ndim == 2:
                        # Ensure shape is (n_szpf, n_time)
                        if data.shape[1] == 156:
                            data = data.T
                        return data
        except Exception:
            pass

    return np.full((156, n_months), np.nan)


def get_pft_timeseries(data: np.ndarray, pft_id: int, factor: float = 1000) -> np.ndarray:
    """Sum SZPF data across size classes for a given PFT, apply unit factor."""
    from tools.fates_utils import get_szpf_range
    start, end = get_szpf_range(pft_id)
    return np.sum(data[start:end + 1, :], axis=0) * factor


# =============================================================================
# Ranking Helpers
# =============================================================================

def rank_cases_by_nrmse(
    data_dir: Path,
    available_cases: List[int],
    targets: Dict[str, Dict],
    pft_ids: List[int],
    variables: List[str] = None,
    case_pattern: str = None,
    year_start: int = 1901,
    year_end: int = 2019,
    obs_year: int = 2016,
    obs_month: int = 7,
) -> List[Dict]:
    """
    Rank all cases by composite NRMSE against targets.

    Parameters
    ----------
    data_dir : Path
        Directory with extracted NetCDF files
    available_cases : list of int
        Case numbers to evaluate
    targets : dict
        Target dict: {target_key: {'observed': float, 'uncertainty': float}}
        Keys like 'PFT7_leaf', 'PFT10_fineroot', etc.
    pft_ids : list of int
        PFT IDs to evaluate
    variables : list of str
        Variable types to check (default: ['leaf', 'fineroot'])
    case_pattern : str, optional
        Case name pattern (auto-detected if None)
    year_start, year_end : int
        Simulation year range
    obs_year, obs_month : int
        Observation timestep

    Returns
    -------
    list of dict
        Ranked results, sorted by composite NRMSE (lowest first)
    """
    if variables is None:
        variables = ['leaf', 'fineroot']
    if case_pattern is None:
        case_pattern = _get_case_name_pattern()

    obs_idx = (obs_year - year_start) * 12 + obs_month - 1
    results = []

    for i, case_num in enumerate(available_cases):
        if (i + 1) % 100 == 0:
            logger.info(f"  Ranking case {i+1}/{len(available_cases)}...")

        # Load data for all variable types
        case_vars = {}
        valid = True
        for var_type in variables:
            var_config = VARIABLE_CONFIGS.get(var_type)
            if not var_config:
                continue
            data = load_nc_timeseries(
                case_num, var_config['nc_var'], data_dir,
                case_pattern=case_pattern,
                year_start=year_start, year_end=year_end
            )
            if np.all(np.isnan(data)):
                valid = False
                break
            case_vars[var_type] = data

        if not valid:
            continue

        # Compute per-target NRMSE
        nrmse_values = {}
        simulated_values = {}
        n_satisfied = 0
        n_total = 0

        for pft_id in pft_ids:
            for var_type in variables:
                target_key = f'PFT{pft_id}_{var_type}'
                target_info = targets.get(target_key)
                if target_info is None:
                    continue

                var_config = VARIABLE_CONFIGS[var_type]
                data = case_vars[var_type]
                ts = get_pft_timeseries(data, pft_id, factor=var_config['factor'])
                sim_val = ts[obs_idx]

                obs_val = target_info['observed']
                nrmse = abs(sim_val - obs_val) / obs_val if obs_val != 0 else float('inf')
                nrmse_values[target_key] = nrmse
                simulated_values[target_key] = sim_val

                tolerance = target_info.get('uncertainty', 0.2)
                if obs_val * (1 - tolerance) <= sim_val <= obs_val * (1 + tolerance):
                    n_satisfied += 1
                n_total += 1

        if not nrmse_values:
            continue

        composite_nrmse = np.sqrt(np.mean(np.array(list(nrmse_values.values()))**2))

        results.append({
            'case_num': case_num,
            'composite_nrmse': composite_nrmse,
            'n_satisfied': n_satisfied,
            'n_total': n_total,
            'nrmse_individual': nrmse_values,
            'simulated': simulated_values,
        })

    return sorted(results, key=lambda x: x['composite_nrmse'])


# =============================================================================
# Main Plotting Function
# =============================================================================

def plot_ensemble_biomass(
    data_dir: str,
    ranked_cases: List[Dict],
    targets: Dict[str, Dict],
    pft_ids: List[int],
    output_path: Optional[str] = None,
    variables: List[str] = None,
    pft_names: Optional[Dict[int, str]] = None,
    top_n: int = 100,
    case_pattern: str = None,
    year_start: int = 1901,
    year_end: int = 2019,
    obs_year: int = 2016,
    obs_month: int = 7,
    plot_year_start: int = 2010,
    plot_year_end: int = 2019,
    title_suffix: str = "",
    obs_uncertainty: Optional[Dict[str, float]] = None,
) -> Optional[str]:
    """
    Plot ensemble biomass timeseries with best cases highlighted.

    Creates an N_PFTs × N_vars panel figure showing ensemble spread,
    best NRMSE case (red), most-targets-met case (blue), and observations.

    Parameters
    ----------
    data_dir : str
        Directory containing extracted NetCDF files
    ranked_cases : list of dict
        Cases sorted by NRMSE. Each dict must have:
        - 'case_num': int
        - 'composite_nrmse': float
        - 'n_satisfied': int
    targets : dict
        Target definitions: {target_key: {'observed': float, 'uncertainty': float}}
        Keys like 'PFT7_leaf', 'PFT10_fineroot'.
        Optional 'obs_uncertainty' key for asymmetric error bars.
    pft_ids : list of int
        PFT IDs for rows (e.g., [7, 9, 10])
    output_path : str, optional
        Full path to save figure. If None, saves to data_dir.
    variables : list of str, optional
        Variable types for columns (default: ['leaf', 'fineroot'])
    pft_names : dict, optional
        PFT ID to display name mapping
    top_n : int
        Number of top cases to plot (default: 100)
    case_pattern : str, optional
        Case name pattern (auto-detected from config if None)
    year_start, year_end : int
        Simulation year range
    obs_year, obs_month : int
        Observation timestep (for marker placement)
    plot_year_start, plot_year_end : int
        Year range to display on x-axis
    title_suffix : str
        Extra text to append to the figure title
    obs_uncertainty : dict, optional
        Per-target observation uncertainty (standard error/deviation) for
        error bars, separate from the tolerance range. Keys match target keys.
        If not provided, error bars show ±tolerance range.

    Returns
    -------
    str or None
        Path to saved figure, or None if plotting failed
    """
    if variables is None:
        variables = ['leaf', 'fineroot']
    if pft_names is None:
        from tools.fates_utils import get_pft_display_names
        pft_names = get_pft_display_names()
    if case_pattern is None:
        case_pattern = _get_case_name_pattern()

    data_dir = Path(data_dir)
    n_pfts = len(pft_ids)
    n_vars = len(variables)

    # Determine best cases
    cases_to_plot = [r['case_num'] for r in ranked_cases[:top_n]]
    if not cases_to_plot:
        logger.warning("No cases to plot")
        return None

    best_nrmse_case = ranked_cases[0]['case_num']
    best_nrmse_value = ranked_cases[0]['composite_nrmse']

    # Find case with most targets satisfied (tie-break by NRMSE)
    max_satisfied = max(r['n_satisfied'] for r in ranked_cases[:top_n])
    best_satisfied_cases = [r for r in ranked_cases[:top_n] if r['n_satisfied'] == max_satisfied]
    best_targets_case = min(best_satisfied_cases, key=lambda x: x['composite_nrmse'])['case_num']
    n_total = ranked_cases[0].get('n_total', len(pft_ids) * len(variables))

    # Time indices
    obs_idx = (obs_year - year_start) * 12 + obs_month - 1
    plot_start_idx = (plot_year_start - year_start) * 12
    plot_end_idx = (plot_year_end - year_start + 1) * 12
    n_months_plot = plot_end_idx - plot_start_idx

    # Pre-load timeseries for all cases
    logger.info(f"Loading timeseries for {len(cases_to_plot)} cases...")
    case_data = {}
    for case_num in cases_to_plot:
        var_data = {}
        valid = True
        for var_type in variables:
            var_config = VARIABLE_CONFIGS.get(var_type)
            if not var_config:
                continue
            data = load_nc_timeseries(
                case_num, var_config['nc_var'], data_dir,
                case_pattern=case_pattern,
                year_start=year_start, year_end=year_end
            )
            if np.all(np.isnan(data)):
                valid = False
                break
            var_data[var_type] = data
        if valid:
            case_data[case_num] = var_data

    logger.info(f"Loaded data for {len(case_data)} cases")

    if not case_data:
        logger.warning("No valid case data loaded")
        return None

    # Create figure
    try:
        fig, axes = plt.subplots(n_pfts, n_vars, figsize=(7 * n_vars, 4 * n_pfts))
        fig.patch.set_facecolor('white')

        # Handle single-row or single-column case
        if n_pfts == 1 and n_vars == 1:
            axes = np.array([[axes]])
        elif n_pfts == 1:
            axes = axes[np.newaxis, :]
        elif n_vars == 1:
            axes = axes[:, np.newaxis]

        for col_idx, var_type in enumerate(variables):
            var_config = VARIABLE_CONFIGS.get(var_type, {})
            for row_idx, pft_id in enumerate(pft_ids):
                ax = axes[row_idx, col_idx]
                target_key = f'PFT{pft_id}_{var_type}'
                target_info = targets.get(target_key, {})
                obs_mean = target_info.get('observed', None)
                tolerance = target_info.get('uncertainty', 0.2)

                labeled_best_nrmse = False
                labeled_best_targets = False

                for case_num in cases_to_plot:
                    if case_num not in case_data:
                        continue

                    data = case_data[case_num].get(var_type)
                    if data is None:
                        continue

                    ts = get_pft_timeseries(data, pft_id, factor=var_config.get('factor', 1000))
                    plot_ts = ts[plot_start_idx:plot_end_idx]

                    # Style: best NRMSE = red, best targets = blue, others = purple
                    if case_num == best_nrmse_case:
                        color = BEST_NRMSE_COLOR
                        lw = BEST_NRMSE_LINEWIDTH
                        alpha = 1.0
                        zorder = 100
                        label = f'Best NRMSE (#{case_num})' if not labeled_best_nrmse else None
                        labeled_best_nrmse = True
                    elif case_num == best_targets_case and best_targets_case != best_nrmse_case:
                        color = BEST_TARGETS_COLOR
                        lw = BEST_TARGETS_LINEWIDTH
                        alpha = 1.0
                        zorder = 99
                        label = f'Most targets (#{case_num}, {max_satisfied}/{n_total})' if not labeled_best_targets else None
                        labeled_best_targets = True
                    else:
                        color = ENSEMBLE_COLOR
                        lw = ENSEMBLE_LINEWIDTH
                        alpha = ENSEMBLE_ALPHA
                        zorder = 50
                        label = None

                    ax.plot(plot_ts, color=color, linewidth=lw, alpha=alpha,
                            label=label, zorder=zorder)

                # Plot observation marker and uncertainty
                if obs_mean is not None:
                    obs_plot_idx = obs_idx - plot_start_idx

                    # ±tolerance validation range box
                    valid_low = obs_mean * (1 - tolerance)
                    valid_high = obs_mean * (1 + tolerance)
                    box_width = n_months_plot * 0.03
                    rect = Rectangle(
                        (obs_plot_idx - box_width / 2, valid_low),
                        box_width, valid_high - valid_low,
                        facecolor='yellow', edgecolor='darkorange',
                        alpha=0.4, linewidth=2, zorder=200,
                        label=f'±{int(tolerance*100)}% Obs. Range' if (row_idx == 0 and col_idx == 0) else None
                    )
                    ax.add_patch(rect)

                    # Error bar (observation uncertainty if provided, else tolerance)
                    if obs_uncertainty and target_key in obs_uncertainty:
                        uncert = obs_uncertainty[target_key]
                    else:
                        uncert = obs_mean * tolerance
                    ax.plot([obs_plot_idx, obs_plot_idx],
                            [obs_mean - uncert, obs_mean + uncert],
                            'k-', linewidth=3, zorder=201)

                    # Observation diamond
                    ax.plot(obs_plot_idx, obs_mean, 'kd', linewidth=3, markersize=12,
                            markerfacecolor='k', zorder=202,
                            label='Obs' if (row_idx == 0 and col_idx == 0) else None)

                # Format axes
                ax.set_xlim([0, n_months_plot])
                tick_positions = np.arange(0, n_months_plot, 12)
                tick_labels = np.arange(plot_year_start, plot_year_end + 1)
                ax.set_xticks(tick_positions)
                ax.set_xticklabels(tick_labels, fontsize=12)

                if row_idx == 0:
                    ax.set_title(var_config.get('title', var_type.capitalize()),
                                 fontweight='bold', fontsize=16)
                if col_idx == 0:
                    pft_label = pft_names.get(pft_id, f'PFT#{pft_id}')
                    ax.set_ylabel(f'{pft_label}\n{var_config.get("unit", "")}',
                                  fontweight='bold', fontsize=14)
                else:
                    ax.set_ylabel(var_config.get('unit', ''), fontsize=14)

                if row_idx == n_pfts - 1:
                    ax.set_xlabel('Year', fontweight='bold', fontsize=14)

                ax.grid(True, alpha=0.3)
                ax.tick_params(axis='both', labelsize=12)

                # Legend in top-left panel only
                if row_idx == 0 and col_idx == 0:
                    ax.legend(loc='upper left', fontsize=11, framealpha=0.9)

        # Suptitle
        title_parts = [f'Top {len(cases_to_plot)} Cases']
        title_parts.append(f'Best NRMSE: #{best_nrmse_case} ({best_nrmse_value:.4f})')
        if best_targets_case != best_nrmse_case:
            title_parts.append(f'Most targets: #{best_targets_case} ({max_satisfied}/{n_total})')
        if title_suffix:
            title_parts.append(title_suffix)
        fig.suptitle(' | '.join(title_parts), fontweight='bold', fontsize=14, y=0.98)

        plt.tight_layout(rect=[0, 0, 1, 0.96])

        # Save
        if output_path is None:
            output_path = str(data_dir / 'ensemble_biomass_top_cases.png')
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=FIGURE_DPI, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"Saved ensemble biomass figure: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"Failed to plot ensemble biomass: {e}")
        import traceback
        logger.error(traceback.format_exc())
        plt.close('all')
        return None


# =============================================================================
# Convenience: All-in-one (scan, rank, plot)
# =============================================================================

def plot_ensemble_biomass_from_dir(
    data_dir: str,
    targets: Dict[str, Dict],
    pft_ids: List[int],
    output_path: Optional[str] = None,
    top_n: int = 100,
    **kwargs
) -> Optional[str]:
    """
    Convenience function: scan directory, rank cases, and plot.

    Combines get_available_cases + rank_cases_by_nrmse + plot_ensemble_biomass.

    Parameters
    ----------
    data_dir : str
        Directory containing extracted NetCDF files
    targets : dict
        Target definitions: {target_key: {'observed': float, 'uncertainty': float}}
    pft_ids : list of int
        PFT IDs for rows
    output_path : str, optional
        Path to save figure
    top_n : int
        Number of top cases to plot
    **kwargs
        Additional keyword arguments passed to plot_ensemble_biomass()

    Returns
    -------
    str or None
        Path to saved figure
    """
    data_dir = Path(data_dir)
    case_pattern = kwargs.get('case_pattern', _get_case_name_pattern())
    variables = kwargs.get('variables', ['leaf', 'fineroot'])
    year_start = kwargs.get('year_start', 1901)
    year_end = kwargs.get('year_end', 2019)
    obs_year = kwargs.get('obs_year', 2016)
    obs_month = kwargs.get('obs_month', 7)

    # Scan for cases
    available_cases = get_available_cases(data_dir, case_pattern)
    if not available_cases:
        logger.warning(f"No cases found in {data_dir}")
        return None

    logger.info(f"Found {len(available_cases)} cases, ranking...")

    # Rank
    ranked = rank_cases_by_nrmse(
        data_dir, available_cases, targets, pft_ids,
        variables=variables, case_pattern=case_pattern,
        year_start=year_start, year_end=year_end,
        obs_year=obs_year, obs_month=obs_month
    )

    if not ranked:
        logger.warning("No valid cases after ranking")
        return None

    logger.info(f"Ranked {len(ranked)} cases. Best: #{ranked[0]['case_num']} "
                f"(NRMSE={ranked[0]['composite_nrmse']:.4f})")

    # Plot
    return plot_ensemble_biomass(
        data_dir=str(data_dir),
        ranked_cases=ranked,
        targets=targets,
        pft_ids=pft_ids,
        output_path=output_path,
        top_n=top_n,
        **kwargs
    )


# =============================================================================
# Standalone CLI
# =============================================================================

def main():
    """Standalone CLI entry point."""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description='Plot ensemble biomass timeseries with best cases highlighted')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='Directory containing extracted NetCDF files')
    parser.add_argument('--output-path', type=str, default=None,
                        help='Path to save the figure')
    parser.add_argument('--top-n', type=int, default=100,
                        help='Number of top cases to plot (default: 100)')
    parser.add_argument('--plot-years', type=str, default='2010-2019',
                        help='Year range to plot (default: 2010-2019)')
    args = parser.parse_args()

    # Get data directory
    if args.data_dir:
        data_dir = args.data_dir
    else:
        try:
            from tools.config import config as a2mc_config
            data_dir = a2mc_config.EXTRACTED_DATA
        except ImportError:
            # No silent personal-path fallback: without config there is nothing
            # sensible to guess, and guessing sends the run at someone else's disk.
            raise SystemExit(
                "tools.config unavailable and --data-dir not given.\n"
                "  Run from the repo root with the configs sourced, or pass --data-dir."
            )

    # Parse plot years
    plot_years = args.plot_years.split('-')
    plot_year_start = int(plot_years[0])
    plot_year_end = int(plot_years[1]) if len(plot_years) > 1 else plot_year_start

    # Load site targets (try importing from screen_ensemble)
    try:
        from phases.phase2_screening.screen_ensemble import load_kougarok_targets
        from tools.optimize_function import Target
        raw_targets = load_kougarok_targets()
        targets = {
            name: {'observed': t.observed, 'uncertainty': t.uncertainty}
            for name, t in raw_targets.items()
        }
    except ImportError:
        print("Warning: Could not load targets from screen_ensemble, using defaults")
        targets = {
            'PFT7_leaf': {'observed': 24.55, 'uncertainty': 0.2},
            'PFT7_fineroot': {'observed': 174.25, 'uncertainty': 0.2},
            'PFT9_leaf': {'observed': 124.7, 'uncertainty': 0.2},
            'PFT9_fineroot': {'observed': 187.35, 'uncertainty': 0.2},
            'PFT10_leaf': {'observed': 82.65, 'uncertainty': 0.2},
            'PFT10_fineroot': {'observed': 382.05, 'uncertainty': 0.2},
        }

    pft_ids = [7, 9, 10]

    fig_path = plot_ensemble_biomass_from_dir(
        data_dir=data_dir,
        targets=targets,
        pft_ids=pft_ids,
        output_path=args.output_path,
        top_n=args.top_n,
        plot_year_start=plot_year_start,
        plot_year_end=plot_year_end,
    )

    if fig_path:
        print(f"\nSaved figure: {fig_path}")
    else:
        print("\nERROR: Failed to generate figure")


if __name__ == '__main__':
    main()
