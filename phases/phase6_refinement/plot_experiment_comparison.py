#!/usr/bin/env python3
"""
Phase 6: Experiment Comparison Plot

Compare experiment cases against a baseline, with validation targets.
Reuses data-loading and PFT aggregation from plot_screening.py.

Creates an N_PFTs x N_vars panel figure showing:
- Baseline case as a black dashed line
- Each experiment as a distinct colored solid line
- Observations with error bars and tolerance range boxes

Usage (from orchestrator or Python):
    from phases.phase6_refinement.plot_experiment_comparison import plot_experiment_comparison

    fig_path = plot_experiment_comparison(
        data_dir="/path/to/extracted_data",
        baseline_case="322",
        experiment_cases=["322_c0_exp1", "322_c0_exp2", ...],
        targets={'PFT10_leaf': {'observed': 82.65, 'uncertainty': 0.2}, ...},
        pft_ids=[7, 9, 10],
    )

Usage (standalone):
    python phases/phase6_refinement/plot_experiment_comparison.py \
        --baseline 322 \
        --experiments 322_c0_exp1 322_c0_exp2 322_c0_exp3 322_c0_exp4 322_c0_exp5 \
        --plot-years 2010-2019

Author: Jing Tao with Claude
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Ensure repo root is on sys.path so "from phases..." and "from tools..." work
_repo_root = str(Path(__file__).resolve().parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from phases.phase2_screening.plot_screening import (
    VARIABLE_CONFIGS,
    _get_case_name_pattern,
    load_nc_timeseries,
    get_pft_timeseries,
    FIGURE_DPI,
)

logger = logging.getLogger(__name__)

# Experiment color palette (tab10 colormap)
EXPERIMENT_CMAP = plt.cm.tab10


def load_nc_timeseries_by_name(
    case_id: str,
    var_name: str,
    data_dir: Path,
    case_pattern: str = None,
    year_start: int = 1901,
    year_end: int = 2019,
    file_pattern: str = '{case_name}_all_variables_monthly_{year_start}_{year_end}.nc',
) -> np.ndarray:
    """
    Load SZPF timeseries for a string case identifier (e.g., '322_c0_exp1').

    Unlike load_nc_timeseries(case_num: int), this accepts arbitrary string IDs
    for experiment cases whose names aren't purely numeric.
    """
    try:
        import netCDF4 as nc
    except ImportError:
        return None

    if case_pattern is None:
        case_pattern = _get_case_name_pattern()

    case_name = case_pattern.format(N=case_id, PHASE='TRANS')
    nc_file = data_dir / file_pattern.format(
        case_name=case_name,
        year_start=year_start,
        year_end=year_end,
    )

    n_months = (year_end - year_start + 1) * 12

    if nc_file.exists():
        try:
            with nc.Dataset(nc_file, 'r') as ds:
                if var_name in ds.variables:
                    data = ds.variables[var_name][:]
                    data = np.squeeze(data)
                    if data.ndim == 2:
                        if data.shape[1] == 156:
                            data = data.T
                        return data
        except Exception:
            pass

    return np.full((156, n_months), np.nan)


def _load_case_data(
    case_id: str,
    variables: List[str],
    data_dir: Path,
    case_pattern: str,
    year_start: int,
    year_end: int,
    is_numeric: bool = False,
) -> Optional[Dict[str, np.ndarray]]:
    """Load all variable data for a single case. Returns None if any variable fails."""
    var_data = {}
    for var_type in variables:
        var_config = VARIABLE_CONFIGS.get(var_type)
        if not var_config:
            continue

        if is_numeric:
            data = load_nc_timeseries(
                int(case_id), var_config['nc_var'], data_dir,
                case_pattern=case_pattern,
                year_start=year_start, year_end=year_end,
            )
        else:
            data = load_nc_timeseries_by_name(
                case_id, var_config['nc_var'], data_dir,
                case_pattern=case_pattern,
                year_start=year_start, year_end=year_end,
            )
        if np.all(np.isnan(data)):
            return None
        var_data[var_type] = data
    return var_data


def _compute_targets_met(
    case_data: Dict[str, np.ndarray],
    targets: Dict[str, Dict],
    pft_ids: List[int],
    variables: List[str],
    obs_idx: int,
) -> int:
    """Count how many validation targets a case meets."""
    n_met = 0
    for pft_id in pft_ids:
        for var_type in variables:
            target_key = f'PFT{pft_id}_{var_type}'
            target_info = targets.get(target_key)
            if target_info is None:
                continue
            var_config = VARIABLE_CONFIGS[var_type]
            data = case_data.get(var_type)
            if data is None:
                continue
            ts = get_pft_timeseries(data, pft_id, factor=var_config['factor'])
            sim_val = ts[obs_idx]
            obs_val = target_info['observed']
            tolerance = target_info.get('uncertainty', 0.2)
            if obs_val * (1 - tolerance) <= sim_val <= obs_val * (1 + tolerance):
                n_met += 1
    return n_met


def plot_experiment_comparison(
    data_dir: str,
    baseline_case: str,
    experiment_cases: List[str],
    targets: Dict[str, Dict],
    pft_ids: List[int],
    output_path: Optional[str] = None,
    variables: List[str] = None,
    pft_names: Optional[Dict[int, str]] = None,
    experiment_labels: Optional[Dict[str, str]] = None,
    case_pattern: str = None,
    year_start: int = 1901,
    year_end: int = 2019,
    obs_year: int = 2016,
    obs_month: int = 7,
    plot_year_start: int = 2010,
    plot_year_end: int = 2019,
    title: str = "",
    obs_uncertainty: Optional[Dict[str, float]] = None,
) -> Optional[str]:
    """
    Plot experiment comparison: baseline vs experiments with validation targets.

    Parameters
    ----------
    data_dir : str
        Directory containing extracted NetCDF files.
    baseline_case : str
        Baseline case identifier (e.g., "322").
    experiment_cases : list of str
        Experiment case identifiers (e.g., ["322_c0_exp1", ...]).
    targets : dict
        {target_key: {'observed': float, 'uncertainty': float}}.
    pft_ids : list of int
        PFT IDs for rows (e.g., [7, 9, 10]).
    output_path : str, optional
        Path to save figure. Auto-generated if None.
    variables : list of str
        Variable types for columns (default: ['leaf', 'fineroot']).
    pft_names : dict, optional
        PFT ID to display name mapping.
    experiment_labels : dict, optional
        {case_id: display_label} overrides for legend.
    case_pattern : str, optional
        Case name pattern (auto-detected if None).
    year_start, year_end : int
        Simulation year range.
    obs_year, obs_month : int
        Observation timestep.
    plot_year_start, plot_year_end : int
        Year range to display.
    title : str
        Custom title (auto-generated if empty).
    obs_uncertainty : dict, optional
        Per-target observation uncertainty (e.g., obs_std) for error bars,
        separate from the validation tolerance range. Keys match target keys.
        If not provided, error bars fall back to ±tolerance range.

    Returns
    -------
    str or None
        Path to saved figure, or None on failure.
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

    obs_idx = (obs_year - year_start) * 12 + obs_month - 1
    plot_start_idx = (plot_year_start - year_start) * 12
    plot_end_idx = (plot_year_end - year_start + 1) * 12
    n_months_plot = plot_end_idx - plot_start_idx

    # Load baseline (try numeric first, then string)
    baseline_is_numeric = baseline_case.isdigit()
    baseline_data = _load_case_data(
        baseline_case, variables, data_dir, case_pattern,
        year_start, year_end, is_numeric=baseline_is_numeric,
    )
    if baseline_data is None:
        logger.error(f"Could not load baseline case {baseline_case}")
        return None

    baseline_met = _compute_targets_met(
        baseline_data, targets, pft_ids, variables, obs_idx)

    # Load experiments
    exp_data = {}
    exp_targets_met = {}
    for case_id in experiment_cases:
        data = _load_case_data(
            case_id, variables, data_dir, case_pattern,
            year_start, year_end, is_numeric=False,
        )
        if data is not None:
            exp_data[case_id] = data
            exp_targets_met[case_id] = _compute_targets_met(
                data, targets, pft_ids, variables, obs_idx)
        else:
            logger.warning(f"Could not load experiment case {case_id}")

    if not exp_data:
        logger.error("No experiment data loaded")
        return None

    n_total = len(pft_ids) * len(variables)

    # Create figure
    try:
        fig, axes = plt.subplots(n_pfts, n_vars, figsize=(7 * n_vars, 4 * n_pfts))
        fig.patch.set_facecolor('white')

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
                factor = var_config.get('factor', 1000)

                # Plot baseline
                bl_ts = get_pft_timeseries(
                    baseline_data[var_type], pft_id, factor=factor)
                plot_ts = bl_ts[plot_start_idx:plot_end_idx]
                label = f'Baseline #{baseline_case} ({baseline_met}/{n_total})' if (row_idx == 0 and col_idx == 0) else None
                ax.plot(plot_ts, color='black', linewidth=2.5, linestyle='--',
                        alpha=0.9, zorder=90, label=label)

                # Plot experiments
                for exp_idx, case_id in enumerate(experiment_cases):
                    if case_id not in exp_data:
                        continue
                    color = EXPERIMENT_CMAP(exp_idx % 10)
                    ts = get_pft_timeseries(
                        exp_data[case_id][var_type], pft_id, factor=factor)
                    plot_ts = ts[plot_start_idx:plot_end_idx]

                    if experiment_labels and case_id in experiment_labels:
                        disp_name = experiment_labels[case_id]
                    else:
                        # Show short name: c0_exp1
                        parts = case_id.split('_', 1)
                        disp_name = parts[1] if len(parts) > 1 else case_id
                    met = exp_targets_met.get(case_id, '?')
                    exp_label = f'{disp_name} ({met}/{n_total})' if (row_idx == 0 and col_idx == 0) else None
                    ax.plot(plot_ts, color=color, linewidth=2, alpha=0.85,
                            zorder=95 + exp_idx, label=exp_label)

                # Observation marker, tolerance box, and uncertainty error bar
                if obs_mean is not None:
                    obs_plot_idx = obs_idx - plot_start_idx

                    # ±tolerance validation range box (yellow)
                    valid_low = obs_mean * (1 - tolerance)
                    valid_high = obs_mean * (1 + tolerance)
                    box_width = n_months_plot * 0.03
                    rect = Rectangle(
                        (obs_plot_idx - box_width / 2, valid_low),
                        box_width, valid_high - valid_low,
                        facecolor='yellow', edgecolor='darkorange',
                        alpha=0.4, linewidth=2, zorder=200,
                        label=f'\u00b1{int(tolerance*100)}% Obs. Range' if (row_idx == 0 and col_idx == 0) else None
                    )
                    ax.add_patch(rect)

                    # Error bar: prefer obs_std (real obs uncertainty) over tolerance
                    if obs_uncertainty and target_key in obs_uncertainty:
                        uncert = obs_uncertainty[target_key]
                    else:
                        uncert = obs_mean * tolerance
                    ax.plot([obs_plot_idx, obs_plot_idx],
                            [obs_mean - uncert, obs_mean + uncert],
                            'k-', linewidth=3, zorder=201)
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

                # Legend in top-left panel
                if row_idx == 0 and col_idx == 0:
                    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)

        # Title
        if not title:
            title_parts = [f'Baseline #{baseline_case} vs {len(exp_data)} Experiments']
            # Best experiment
            if exp_targets_met:
                best_id = max(exp_targets_met, key=exp_targets_met.get)
                best_met = exp_targets_met[best_id]
                parts = best_id.split('_', 1)
                best_short = parts[1] if len(parts) > 1 else best_id
                title_parts.append(f'Best: {best_short} ({best_met}/{n_total})')
            title = ' | '.join(title_parts)

        fig.suptitle(title, fontweight='bold', fontsize=14, y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])

        # Save — default to phase_results/{session_id}/phase6_refinement/ under use case dir
        if output_path is None:
            try:
                from tools.config import config as _cfg
                _results_dir = _cfg.phase_results_dir('phase6_refinement')
            except (ImportError, AttributeError):
                _results_dir = data_dir
            output_path = str(_results_dir / f'experiment_comparison_{baseline_case}.png')
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=FIGURE_DPI, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"Saved experiment comparison figure: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"Failed to plot experiment comparison: {e}")
        import traceback
        logger.error(traceback.format_exc())
        plt.close('all')
        return None


def main():
    """Standalone CLI entry point."""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description='Plot experiment comparison: baseline vs experiments')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='Directory containing extracted NetCDF files')
    parser.add_argument('--baseline', type=str, required=True,
                        help='Baseline case identifier (e.g., 322)')
    parser.add_argument('--experiments', type=str, nargs='+', required=True,
                        help='Experiment case identifiers (e.g., 322_c0_exp1 ...)')
    parser.add_argument('--output-path', type=str, default=None,
                        help='Path to save figure')
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
        except (ImportError, AttributeError):
            data_dir = os.environ.get('A2MC_EXTRACTED_DATA', '')
            if not data_dir:
                print("ERROR: --data-dir required (or set A2MC_EXTRACTED_DATA)")
                return

    # Parse plot years
    plot_years = args.plot_years.split('-')
    plot_year_start = int(plot_years[0])
    plot_year_end = int(plot_years[1]) if len(plot_years) > 1 else plot_year_start

    # Load targets
    try:
        from phases.phase2_screening.screen_ensemble import load_kougarok_targets
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

    fig_path = plot_experiment_comparison(
        data_dir=data_dir,
        baseline_case=args.baseline,
        experiment_cases=args.experiments,
        targets=targets,
        pft_ids=pft_ids,
        output_path=args.output_path,
        plot_year_start=plot_year_start,
        plot_year_end=plot_year_end,
    )

    if fig_path:
        print(f"\nSaved figure: {fig_path}")
    else:
        print("\nERROR: Failed to generate figure")


if __name__ == '__main__':
    main()
