#!/usr/bin/env python3
"""
Compare Top Cases from 162-Parameter Morris Ensemble (4890 cases)

Ranks all available cases by composite NRMSE (6 outputs: leaf + fineroot × 3 PFTs)
and plots a 3x2 panel figure showing all 6 biomass comparisons.

Outputs:
    - leafroot_optimization_results.txt (all cases ranked)
    - 3x2 panel figure (leaf and fineroot for 3 PFTs)

Usage:
    python compare_biomass_topcases.py
    python compare_biomass_topcases.py --top-n 20

Author: Jing Tao
Date: January 2026
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for HPC compatibility
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from pathlib import Path
import netCDF4 as nc
import argparse
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, for tools.*
from tools.fates_utils import (
    get_szpf_range, get_szpf_dim_length, get_szpf_total_from_config,
    get_n_size_classes_from_config,
)

# =============================================================================
# Configuration
# =============================================================================

# Years
YEAR_START = 1901
YEAR_END = 2019
PLOT_YEAR_START = 2010
PLOT_YEAR_END = 2019

# Observation year and month
OBS_YEAR = 2016
OBS_MONTH = 7  # July
OBS_IDX = (OBS_YEAR - YEAR_START) * 12 + OBS_MONTH - 1  # 0-indexed

# Data directory - Auto-detect HPC vs local
# Both from config. `get_results_dir()` / `get_figures_dir()` never existed on
# A2MCConfig, so this raised AttributeError at import — which `except ImportError`
# cannot catch, making the fallback below unreachable dead code that hid a hard
# crash. ENSEMBLE_OUTPUT is exactly what `get_results_dir()/ENSEMBLE_NAME` meant;
# FIGURES_DIR is new (there was no config-backed figures location).
from tools.config import config as a2mc_config
DATA_DIR = Path(a2mc_config.ENSEMBLE_OUTPUT)
OUTPUT_DIR = Path(a2mc_config.FIGURES_DIR)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = OUTPUT_DIR / 'results'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

picture_name = 'Compare_Top50Cases_New162Params_4890Ensemble_LeafFroot_3x2.png'

# Case naming pattern - from A2MC config
import os as _os
try:
    from tools.config import config as _a2mc_config
    CASE_PATTERN = _a2mc_config.CASE_NAME_PATTERN
except ImportError:
    _prefix = _os.environ.get('A2MC_ENSEMBLE_PREFIX', '')
    CASE_PATTERN = _os.environ.get(
        'A2MC_CASE_NAME_PATTERN', f"{_prefix}{{N}}_{{PHASE}}")
FILE_PATTERN = '{case_name}_all_variables_monthly_{year_start}_{year_end}.nc'

# Variable settings
LEAF_CONFIG = {
    'nc_var': 'FATES_LEAFC_SZPF',
    'factor': 1000,  # kg/m² to g/m²
    'unit': 'Leaf C (g C m$^{-2}$)',
    'obs_mean': np.array([49.1, 249.4, 165.3]) * 0.5,  # [24.55, 124.7, 82.65]
    'obs_uncert': np.array([58.2, 94.4, 112.6]) * 0.5,  # [29.1, 47.2, 56.3]
}

FROOT_CONFIG = {
    'nc_var': 'FATES_FROOTC_SZPF',
    'factor': 1000,
    'unit': 'Fineroot C (g C m$^{-2}$)',
    'obs_mean': np.array([348.5, 374.7, 764.1]) * 0.5,  # [174.25, 187.35, 382.05]
    'obs_uncert': np.array([428.0, 240.8, 534.1]) * 0.5,  # [214.0, 120.4, 267.05]
}

# Validation targets for 6-output composite NRMSE
VALIDATION_TARGETS = {
    # Leaf observations (g C/m²)
    'PFT10_leaf_observed': 49.1 * 0.5,
    'PFT11_leaf_observed': 249.4 * 0.5,
    'PFT12_leaf_observed': 165.3 * 0.5,
    # Fineroot observations (g C/m²)
    'PFT10_fineroot_observed': 348.5 * 0.5,
    'PFT11_fineroot_observed': 374.7 * 0.5,
    'PFT12_fineroot_observed': 764.1 * 0.5,
    # ±20% ranges for leaf
    'PFT10_leaf_min': 49.1 * 0.5 * 0.8,
    'PFT10_leaf_max': 49.1 * 0.5 * 1.2,
    'PFT11_leaf_min': 249.4 * 0.5 * 0.8,
    'PFT11_leaf_max': 249.4 * 0.5 * 1.2,
    'PFT12_leaf_min': 165.3 * 0.5 * 0.8,
    'PFT12_leaf_max': 165.3 * 0.5 * 1.2,
    # ±20% ranges for fineroot
    'PFT10_fineroot_min': 348.5 * 0.5 * 0.8,
    'PFT10_fineroot_max': 348.5 * 0.5 * 1.2,
    'PFT11_fineroot_min': 374.7 * 0.5 * 0.8,
    'PFT11_fineroot_max': 374.7 * 0.5 * 1.2,
    'PFT12_fineroot_min': 764.1 * 0.5 * 0.8,
    'PFT12_fineroot_max': 764.1 * 0.5 * 1.2,
}

# FATES PFT mapping for size-class x PFT dimension (156 levels)
FATES_PFTMAP_LEVSCPF = np.array([
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12
])

# PFTs to analyze
PFT_LIST = [10, 11, 12]
PFT_NAMES = [
    'PFT#10 Evergreen Shrub',
    'PFT#11 Deciduous Shrub',
    'PFT#12 Graminoid'
]

# Color scheme
DEFAULT_COLOR = [0.7, 0.6, 1.0]  # light purple
DEFAULT_ALPHA = 0.5
DEFAULT_LINEWIDTH = 1

BEST_COLOR = 'red'
BEST_ALPHA = 1.0
BEST_LINEWIDTH = 3


# =============================================================================
# Helper Functions
# =============================================================================

def get_available_cases(data_dir):
    """Scan directory to find all available case numbers."""
    cases = []
    # Build regex from configurable case name pattern
    marker = '___CASENUM___'
    template = CASE_PATTERN.format(N=marker, PHASE='TRANS')
    escaped = re.escape(template)
    regex_str = escaped.replace(marker, r'(\d+)') + '_all_variables_monthly'
    pattern = re.compile(regex_str)

    for f in data_dir.glob('*_all_variables_monthly_*.nc'):
        match = pattern.search(f.name)
        if match:
            cases.append(int(match.group(1)))

    return sorted(cases)


def load_nc_timeseries(case_num, var_name, data_dir, year_start=1901, year_end=2019):
    """Load timeseries from NetCDF file."""
    case_name = CASE_PATTERN.format(N=case_num, PHASE='TRANS')
    nc_file = data_dir / FILE_PATTERN.format(
        case_name=case_name,
        year_start=year_start,
        year_end=year_end
    )

    n_months = (year_end - year_start + 1) * 12
    # SZPF total + nlevsclass from the run's base param file (not hardcoded 156/13);
    # a present file is oriented by its own dimension.
    szpf_total = get_szpf_total_from_config()
    n_sc = get_n_size_classes_from_config()

    if nc_file.exists():
        try:
            with nc.Dataset(nc_file, 'r') as ds:
                if var_name in ds.variables:
                    slen = get_szpf_dim_length(ds, var_name) or szpf_total
                    data = ds.variables[var_name][:]
                    data = np.squeeze(data)
                    if data.ndim == 2:
                        if data.shape[1] == slen or (
                            data.shape[1] % n_sc == 0
                            and data.shape[0] % n_sc != 0
                        ):
                            data = data.T
                    else:
                        return np.full((slen, n_months), np.nan)
                    return data
                else:
                    pass
        except Exception as e:
            pass

    return np.full((szpf_total, n_months), np.nan)


def get_pft_value_at_obs(data, pft_id, obs_idx, factor=1000):
    """Extract PFT-specific value at observation timestep."""
    # Contiguous SZPF slice for this PFT. nlevsclass from the base param file; PFT count
    # = rows / nlevsclass — both model-derived, correct for any FATES PFT/size config.
    n_sc = get_n_size_classes_from_config()
    s, e = get_szpf_range(pft_id, fates_pft=data.shape[0] // n_sc, n_size_classes=n_sc)
    return np.sum(data[s:e + 1, obs_idx]) * factor


def calculate_nrmse(simulated, observed):
    """NRMSE = |simulated - observed| / observed"""
    return np.abs(simulated - observed) / observed


def calculate_composite_nrmse(sim_leaf, sim_froot, targets):
    """
    Calculate composite NRMSE across all 6 outputs.
    Composite NRMSE = sqrt(mean(NRMSE_1^2 + ... + NRMSE_6^2))
    """
    nrmse_individual = {}

    for pft_id in PFT_LIST:
        key_leaf = f'PFT{pft_id}_leaf'
        obs_leaf = targets[f'{key_leaf}_observed']
        nrmse_individual[key_leaf] = calculate_nrmse(sim_leaf[pft_id], obs_leaf)

        key_froot = f'PFT{pft_id}_fineroot'
        obs_froot = targets[f'{key_froot}_observed']
        nrmse_individual[key_froot] = calculate_nrmse(sim_froot[pft_id], obs_froot)

    nrmse_array = np.array([
        nrmse_individual['PFT10_leaf'],
        nrmse_individual['PFT10_fineroot'],
        nrmse_individual['PFT11_leaf'],
        nrmse_individual['PFT11_fineroot'],
        nrmse_individual['PFT12_leaf'],
        nrmse_individual['PFT12_fineroot'],
    ])

    composite_nrmse = np.sqrt(np.mean(nrmse_array**2))

    return composite_nrmse, nrmse_individual


def check_within_uncertainty(sim_leaf, sim_froot, targets):
    """Check which outputs fall within ±20% uncertainty range."""
    within_range = {}

    for pft_id in PFT_LIST:
        key_leaf = f'PFT{pft_id}_leaf'
        min_val = targets[f'{key_leaf}_min']
        max_val = targets[f'{key_leaf}_max']
        within_range[key_leaf] = min_val <= sim_leaf[pft_id] <= max_val

        key_froot = f'PFT{pft_id}_fineroot'
        min_val = targets[f'{key_froot}_min']
        max_val = targets[f'{key_froot}_max']
        within_range[key_froot] = min_val <= sim_froot[pft_id] <= max_val

    n_satisfied = sum(within_range.values())

    return n_satisfied, within_range


def rank_all_cases(data_dir, available_cases, targets):
    """Load data for all cases and calculate rankings."""
    print("\n" + "="*80)
    print("Loading data and calculating rankings...")
    print("="*80)

    results = []

    for i, case_num in enumerate(available_cases):
        if (i + 1) % 50 == 0:
            print(f"  Processing case {i+1}/{len(available_cases)}...")

        leaf_data = load_nc_timeseries(case_num, 'FATES_LEAFC_SZPF', data_dir, YEAR_START, YEAR_END)
        froot_data = load_nc_timeseries(case_num, 'FATES_FROOTC_SZPF', data_dir, YEAR_START, YEAR_END)

        if np.all(np.isnan(leaf_data)) or np.all(np.isnan(froot_data)):
            continue

        sim_leaf = {}
        sim_froot = {}
        for pft_id in PFT_LIST:
            sim_leaf[pft_id] = get_pft_value_at_obs(leaf_data, pft_id, OBS_IDX, factor=1000)
            sim_froot[pft_id] = get_pft_value_at_obs(froot_data, pft_id, OBS_IDX, factor=1000)

        composite_nrmse, nrmse_individual = calculate_composite_nrmse(sim_leaf, sim_froot, targets)
        n_satisfied, _ = check_within_uncertainty(sim_leaf, sim_froot, targets)

        results.append({
            'case_num': case_num,
            'composite_nrmse': composite_nrmse,
            'n_satisfied': n_satisfied,
            'sim_leaf': sim_leaf,
            'sim_froot': sim_froot,
            'nrmse_individual': nrmse_individual,
        })

    print(f"  Processed {len(results)} valid cases out of {len(available_cases)} available")

    ranked_results = sorted(results, key=lambda x: x['composite_nrmse'])

    return results, ranked_results


def save_optimization_results(ranked_results, targets, output_file):
    """Save optimization results to file."""
    print(f"\nSaving results to {output_file}...")

    with open(output_file, 'w') as f:
        f.write("# Leaf + Fine Root Optimization Results (6 outputs)\n")
        f.write("# 162-Parameter Morris Ensemble\n")
        f.write("# Ranked by composite NRMSE (lowest = best)\n")
        f.write("# Date: January 2026\n")
        f.write("#\n")
        f.write("# Columns:\n")
        f.write("#   1. Rank\n")
        f.write("#   2. Case_Num\n")
        f.write("#   3. Composite_NRMSE\n")
        f.write("#   4. N_outputs_satisfied (0-6)\n")
        f.write("#   5-10. Individual NRMSE\n")
        f.write("#   11-16. Simulated values (g C/m²)\n")
        f.write("#\n")

        f.write("Rank\tCase_Num\tComposite_NRMSE\tN_satisfied\t")
        f.write("NRMSE_PFT10_leaf\tNRMSE_PFT10_fineroot\t")
        f.write("NRMSE_PFT11_leaf\tNRMSE_PFT11_fineroot\t")
        f.write("NRMSE_PFT12_leaf\tNRMSE_PFT12_fineroot\t")
        f.write("Sim_PFT10_leaf\tSim_PFT10_fineroot\t")
        f.write("Sim_PFT11_leaf\tSim_PFT11_fineroot\t")
        f.write("Sim_PFT12_leaf\tSim_PFT12_fineroot\n")

        for rank, r in enumerate(ranked_results, start=1):
            f.write(f"{rank}\t{r['case_num']}\t{r['composite_nrmse']:.6f}\t{r['n_satisfied']}\t")

            for key in ['PFT10_leaf', 'PFT10_fineroot', 'PFT11_leaf',
                       'PFT11_fineroot', 'PFT12_leaf', 'PFT12_fineroot']:
                f.write(f"{r['nrmse_individual'][key]:.6f}\t")

            f.write(f"{r['sim_leaf'][7]:.2f}\t{r['sim_froot'][7]:.2f}\t")
            f.write(f"{r['sim_leaf'][9]:.2f}\t{r['sim_froot'][9]:.2f}\t")
            f.write(f"{r['sim_leaf'][10]:.2f}\t{r['sim_froot'][10]:.2f}\n")

    print(f"✓ Saved: {output_file}")


# =============================================================================
# Main Processing
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Compare biomass for top cases from 162-param ensemble')
    parser.add_argument('--top-n', type=int, default=50,
                        help='Number of top cases to plot (default: 50)')
    parser.add_argument('--skip-ranking', action='store_true',
                        help='Skip ranking calculation (use first N cases)')
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("COMPARE CASES FROM 162-PARAMETER MORRIS ENSEMBLE")
    print("6-Output Composite NRMSE (Leaf + Fineroot × 3 PFTs)")
    print("=" * 80)
    print()

    # Get available cases
    available_cases = get_available_cases(DATA_DIR)
    print(f"Found {len(available_cases)} cases in {DATA_DIR.name}")

    if not available_cases:
        print("ERROR: No cases found!")
        return

    # Rank all cases
    if not args.skip_ranking:
        results, ranked_results = rank_all_cases(DATA_DIR, available_cases, VALIDATION_TARGETS)

        results_file = RESULTS_DIR / 'leafroot_optimization_results.txt'
        save_optimization_results(ranked_results, VALIDATION_TARGETS, results_file)

        # Print top 10
        print("\n" + "="*80)
        print("TOP 10 RANKED CASES")
        print("="*80)
        print(f"{'Rank':<6s} {'Case':<8s} {'Comp_NRMSE':<12s} {'Satisfied':<10s}")
        print("-" * 40)
        for i, r in enumerate(ranked_results[:10], start=1):
            print(f"{i:<6d} {r['case_num']:<8d} {r['composite_nrmse']:<12.6f} {r['n_satisfied']:<10d}/6")

        best_case = ranked_results[0]['case_num']
        best_nrmse = ranked_results[0]['composite_nrmse']
        print(f"\nBest case: #{best_case} (Composite NRMSE = {best_nrmse:.6f})")

        cases_to_plot = [r['case_num'] for r in ranked_results[:args.top_n]]
    else:
        cases_to_plot = available_cases[:args.top_n]
        best_case = cases_to_plot[0]
        best_nrmse = None
        print(f"Skipping ranking, using first {len(cases_to_plot)} available cases")

    print(f"\nPlotting {len(cases_to_plot)} cases")

    # Time indices
    n_months_total = (YEAR_END - YEAR_START + 1) * 12
    plot_start_idx = (PLOT_YEAR_START - YEAR_START) * 12
    plot_end_idx = (PLOT_YEAR_END - YEAR_START + 1) * 12
    n_months_plot = plot_end_idx - plot_start_idx

    print(f"Plot period: {PLOT_YEAR_START}-{PLOT_YEAR_END} ({n_months_plot} months)")

    # Create 3x2 figure (rows=PFTs, cols=leaf/froot)
    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    fig.patch.set_facecolor('white')

    # Column configs
    col_configs = [
        ('leaf', LEAF_CONFIG),
        ('froot', FROOT_CONFIG)
    ]

    # Pre-load all timeseries data for cases to plot
    print("\nLoading timeseries data for plotting...")
    case_data = {}
    for case_num in cases_to_plot:
        leaf_ts = load_nc_timeseries(case_num, LEAF_CONFIG['nc_var'], DATA_DIR, YEAR_START, YEAR_END)
        froot_ts = load_nc_timeseries(case_num, FROOT_CONFIG['nc_var'], DATA_DIR, YEAR_START, YEAR_END)
        if not np.all(np.isnan(leaf_ts)) and not np.all(np.isnan(froot_ts)):
            case_data[case_num] = {'leaf': leaf_ts, 'froot': froot_ts}

    print(f"Loaded data for {len(case_data)} cases")

    # Plot each panel
    for col_idx, (var_type, var_config) in enumerate(col_configs):
        for row_idx, (pft_id, pft_name) in enumerate(zip(PFT_LIST, PFT_NAMES)):
            ax = axes[row_idx, col_idx]

            obs_mean = var_config['obs_mean'][row_idx]
            obs_uncert = var_config['obs_uncert'][row_idx]
            obs_low = obs_mean - obs_uncert
            obs_high = obs_mean + obs_uncert
            valid_low = obs_mean * 0.8
            valid_high = obs_mean * 1.2

            plotted_count = 0
            labeled_best = False

            for case_num in cases_to_plot:
                if case_num not in case_data:
                    continue

                data = case_data[case_num][var_type]

                n_sc = get_n_size_classes_from_config()
                if data.shape[0] % n_sc != 0:
                    continue

                s, e = get_szpf_range(pft_id, fates_pft=data.shape[0] // n_sc, n_size_classes=n_sc)
                plotdata = np.sum(data[s:e + 1, :], axis=0) * var_config['factor']

                # Best case in red, others in light purple (no label for others)
                if case_num == best_case:
                    color = BEST_COLOR
                    linewidth = BEST_LINEWIDTH
                    alpha = BEST_ALPHA
                    zorder = 100
                    if not labeled_best:
                        label = f'Best (#{case_num})'
                        labeled_best = True
                    else:
                        label = None
                else:
                    color = DEFAULT_COLOR
                    linewidth = DEFAULT_LINEWIDTH
                    alpha = DEFAULT_ALPHA
                    zorder = 50
                    label = None  # No label for other cases

                ax.plot(plotdata[plot_start_idx:plot_end_idx],
                       color=color, linewidth=linewidth, alpha=alpha,
                       label=label, zorder=zorder)

                plotted_count += 1

            # Plot observation
            obs_plot_idx = OBS_IDX - plot_start_idx

            # ±20% validation range box
            box_width = n_months_plot * 0.03
            box_height = valid_high - valid_low
            rect = Rectangle((obs_plot_idx - box_width/2, valid_low),
                            box_width, box_height,
                            facecolor='yellow', edgecolor='darkorange',
                            alpha=0.4, linewidth=2, zorder=200,
                            label='±20% Range' if (row_idx == 0 and col_idx == 0) else None)
            ax.add_patch(rect)

            # Error bar
            ax.plot([obs_plot_idx, obs_plot_idx],
                   [obs_low, obs_high],
                   'k-', linewidth=3, zorder=201)

            # Observation point
            ax.plot(obs_plot_idx, obs_mean,
                   'kd', linewidth=3, markersize=12,
                   markerfacecolor='k', zorder=202,
                   label='Obs' if (row_idx == 0 and col_idx == 0) else None)

            # Format subplot
            ax.set_xlim([0, n_months_plot])

            # X-axis ticks
            tick_positions = np.arange(0, n_months_plot, 12)
            tick_labels = np.arange(PLOT_YEAR_START, PLOT_YEAR_END + 1)
            ax.set_xticks(tick_positions)
            ax.set_xticklabels(tick_labels, fontsize=12)

            # Title for top row only
            if row_idx == 0:
                col_title = 'Leaf Biomass' if var_type == 'leaf' else 'Fineroot Biomass'
                ax.set_title(col_title, fontweight='bold', fontsize=16)

            # Y-label for left column only
            if col_idx == 0:
                ax.set_ylabel(f'{pft_name}\n({var_config["unit"]})', fontweight='bold', fontsize=14)
            else:
                ax.set_ylabel(var_config['unit'], fontsize=14)

            # X-label for bottom row only
            if row_idx == 2:
                ax.set_xlabel('Year', fontweight='bold', fontsize=14)

            ax.grid(True, alpha=0.3)
            ax.tick_params(axis='both', labelsize=12)

            # Legend only in top-left panel
            if row_idx == 0 and col_idx == 0:
                ax.legend(loc='upper left', fontsize=12, framealpha=0.9)

    # Add overall title with best case info
    if best_nrmse is not None:
        fig.suptitle(f'Top {len(cases_to_plot)} Cases | Best: #{best_case} (Composite NRMSE = {best_nrmse:.4f})',
                    fontweight='bold', fontsize=16, y=0.98)
    else:
        fig.suptitle(f'Top {len(cases_to_plot)} Cases',
                    fontweight='bold', fontsize=16, y=0.98)

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # Save figure
    output_file = OUTPUT_DIR / picture_name
    plt.savefig(output_file, dpi=600, bbox_inches='tight')
    print(f"\nSaved figure: {output_file}")

    print("\n" + "=" * 80)
    print("COMPLETE!")
    print("=" * 80)

    # Note: plt.show() removed for HPC compatibility (Agg backend)


if __name__ == '__main__':
    main()
