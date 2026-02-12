#!/usr/bin/env python3
"""
Phase 3 Diagnosis: Diagnostic Plotting Module

Creates publication-quality diagnostic figures for PFT diagnosis results.
Figures are saved to use_cases/{site}/memory/phase_results/phase3_diagnosis/.

Functions:
    plot_pft_diagnosis()         - 6-panel composite figure (main entry point)
    plot_biomass_trajectories()  - Fine root + leaf biomass time series
    plot_nutrient_limitation()   - P (or N) uptake/demand ratio
    plot_light_competition()     - GPP ratio between PFTs
    plot_allocation_dynamics()   - L2FR seasonal dynamics
    plot_allocation_rates()      - Leaf vs froot allocation rates
    plot_mortality_components()  - Stacked area mortality by component per PFT
    plot_p_mass_balance()        - 6-panel P mass balance overview from NetCDF

Usage:
    from phases.phase3_diagnosis.plot_diagnostics import plot_pft_diagnosis

    fig_path = plot_pft_diagnosis(
        data=data,           # from load_netcdf_data()
        diagnosis=result,    # from run_pft_diagnosis()
        pft_id=10,
        targets={'leaf': 82.7, 'froot': 382.1},
        comparison_pfts=[7, 9],
        output_dir="use_cases/Kougarok/memory/phase_results/phase3_diagnosis/"
    )

Author: Jing Tao with Claude
Created: February 2026
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# HPC-safe backend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

# Default figure DPI
FIGURE_DPI = 600

# ELM no-leap-year calendar
SECONDS_PER_YEAR = 365 * 86400
DAYS_PER_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _make_year_axis(n_months: int, start_year: int = None) -> np.ndarray:
    """Create a fractional year array from monthly time index."""
    if start_year is None:
        start_year = int(os.environ.get('A2MC_TRANS_START_YEAR', '1901'))
    return start_year + np.arange(n_months) / 12.0


def _stats_box(ax, text: str, loc: str = 'upper right'):
    """Add a statistics text box to an axis."""
    ha = 'right' if 'right' in loc else 'left'
    va = 'top' if 'upper' in loc else 'bottom'
    x = 0.98 if 'right' in loc else 0.02
    y = 0.97 if 'upper' in loc else 0.03
    ax.text(x, y, text, transform=ax.transAxes,
            fontsize=8, verticalalignment=va, horizontalalignment=ha,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))


# =============================================================================
# Individual plot functions
# =============================================================================

def plot_biomass_trajectories(
    data: Dict,
    pft_id: int,
    targets: Dict[str, float],
    output_path: Optional[str] = None,
    start_year: int = None
) -> Optional[str]:
    """
    Plot fine root and leaf biomass time series with target lines.

    Args:
        data: Output from load_netcdf_data()
        pft_id: PFT ID to plot
        targets: Dict with 'leaf' and/or 'froot' targets (g C/m²)
        output_path: Full path to save figure. If None, returns None.
        start_year: Transient start year (default from env)

    Returns:
        Path to saved figure, or None
    """
    pft_data = data.get('pft_data', {}).get(pft_id, {})
    if not pft_data:
        logger.warning(f"No data for PFT#{pft_id}")
        return None

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    panels = [
        ('FATES_FROOTC_SZPF', 'froot', 'Fine Root Biomass', axes[0]),
        ('FATES_LEAFC_SZPF', 'leaf', 'Leaf Biomass', axes[1]),
    ]

    for var_name, target_key, title, ax in panels:
        if var_name not in pft_data:
            ax.text(0.5, 0.5, f'{var_name} not available',
                    transform=ax.transAxes, ha='center')
            continue

        biomass = pft_data[var_name] * 1000  # kg/m² → g C/m²
        years = _make_year_axis(len(biomass), start_year)

        ax.plot(years, biomass, 'b-', linewidth=1.5, label=f'PFT#{pft_id}')

        if target_key in targets:
            target_val = targets[target_key]
            ax.axhline(target_val, color='red', linestyle='--', linewidth=2,
                       label=f'Target: {target_val:.1f} g C/m²')

        # Stats for final 12 months
        final_mean = float(np.mean(biomass[-12:])) if len(biomass) >= 12 else float(np.mean(biomass))
        stats = f'Final year mean: {final_mean:.1f} g C/m²'
        if target_key in targets:
            err_pct = 100 * (final_mean - targets[target_key]) / targets[target_key]
            stats += f'\nError: {err_pct:+.1f}%'
        _stats_box(ax, stats)

        ax.set_xlabel('Year')
        ax.set_ylabel('Biomass (g C/m²)')
        ax.set_title(f'{title} — PFT#{pft_id}')
        ax.legend(loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3, linestyle='--')

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches='tight')
        plt.close(fig)
        return output_path
    plt.close(fig)
    return None


def plot_nutrient_limitation(
    data: Dict,
    pft_id: int,
    output_path: Optional[str] = None,
    start_year: int = None
) -> Optional[str]:
    """
    Plot P (or N) uptake/demand ratio time series.

    Args:
        data: Output from load_netcdf_data()
        pft_id: PFT ID to plot
        output_path: Full path to save figure
        start_year: Transient start year

    Returns:
        Path to saved figure, or None
    """
    pft_data = data.get('pft_data', {}).get(pft_id, {})
    if not pft_data:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))

    has_data = False
    for demand_var, uptake_var, color, label in [
        ('FATES_PDEMAND_SZPF', 'FATES_PUPTAKE_SZPF', 'purple', 'P uptake/demand'),
        ('FATES_NDEMAND_SZPF', 'FATES_NUPTAKE_SZPF', 'green', 'N uptake/demand'),
    ]:
        if demand_var in pft_data and uptake_var in pft_data:
            demand = pft_data[demand_var]
            uptake = pft_data[uptake_var]
            ratio = np.where(demand > 0, uptake / demand, np.nan)
            years = _make_year_axis(len(ratio), start_year)

            ax.plot(years, ratio, color=color, linewidth=1.2, label=label, alpha=0.8)
            has_data = True

    if not has_data:
        plt.close(fig)
        return None

    # Reference lines
    ax.axhline(1.0, color='gray', linestyle='--', linewidth=1.5, alpha=0.7, label='No limitation')
    ax.axhline(0.0, color='red', linestyle='-', linewidth=1, alpha=0.5)
    ax.fill_between(ax.get_xlim(), 0, 0, alpha=0)  # dummy to get xlim
    xlim = ax.get_xlim()
    ax.fill_between([xlim[0], xlim[1]], -0.05, 0.0, color='red', alpha=0.1, label='Starvation zone')
    ax.set_xlim(xlim)

    ax.set_xlabel('Year')
    ax.set_ylabel('Uptake / Demand Ratio')
    ax.set_title(f'Nutrient Limitation Severity — PFT#{pft_id}')
    ax.legend(loc='upper right', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_ylim(-0.05, max(1.5, ax.get_ylim()[1]))

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches='tight')
        plt.close(fig)
        return output_path
    plt.close(fig)
    return None


def plot_light_competition(
    data: Dict,
    pft_ids: List[int],
    output_path: Optional[str] = None,
    start_year: int = None
) -> Optional[str]:
    """
    Plot GPP ratio between PFTs over time.

    Args:
        data: Output from load_netcdf_data()
        pft_ids: PFT IDs to compare (at least 2)
        output_path: Full path to save figure
        start_year: Transient start year

    Returns:
        Path to saved figure, or None
    """
    if len(pft_ids) < 2:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))

    has_data = False
    colors = plt.cm.Set1(np.linspace(0, 1, max(len(pft_ids), 3)))

    # Plot absolute GPP for each PFT
    gpp_series = {}
    for i, pft_id in enumerate(pft_ids):
        pft_data = data.get('pft_data', {}).get(pft_id, {})
        if 'FATES_GPP_PF' in pft_data:
            gpp = pft_data['FATES_GPP_PF'] * 86400 * 1000  # kg/m²/s → g C/m²/day
            gpp_series[pft_id] = gpp
            years = _make_year_axis(len(gpp), start_year)
            ax.plot(years, gpp, color=colors[i], linewidth=1.2,
                    label=f'PFT#{pft_id}', alpha=0.8)
            has_data = True

    if not has_data:
        plt.close(fig)
        return None

    # Add stats
    if len(gpp_series) >= 2:
        ids = list(gpp_series.keys())
        means = {pid: float(np.nanmean(gpp)) for pid, gpp in gpp_series.items()}
        dominant = max(means, key=means.get)
        stats_lines = [f'Mean GPP (g C/m²/day):']
        for pid in ids:
            marker = ' *' if pid == dominant else ''
            stats_lines.append(f'  PFT#{pid}: {means[pid]:.3f}{marker}')
        _stats_box(ax, '\n'.join(stats_lines))

    ax.set_xlabel('Year')
    ax.set_ylabel('GPP (g C/m²/day)')
    ax.set_title('Light Competition — GPP by PFT')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches='tight')
        plt.close(fig)
        return output_path
    plt.close(fig)
    return None


def plot_allocation_dynamics(
    data: Dict,
    pft_id: int,
    output_path: Optional[str] = None,
    start_year: int = None
) -> Optional[str]:
    """
    Plot L2FR seasonal dynamics (site-level and PFT-level).

    Args:
        data: Output from load_netcdf_data()
        pft_id: PFT ID to plot
        output_path: Full path to save figure
        start_year: Transient start year

    Returns:
        Path to saved figure, or None
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    has_data = False

    # Site-level L2FR
    if 'FATES_L2FR' in data:
        l2fr_site = data['FATES_L2FR']
        years = _make_year_axis(len(l2fr_site), start_year)
        ax.plot(years, l2fr_site, 'k-', linewidth=1.2, label='Site-level L2FR', alpha=0.6)
        has_data = True

    # PFT-level canopy L2FR
    pft_data = data.get('pft_data', {}).get(pft_id, {})
    if 'FATES_L2FR_CANOPY_REC_PF' in pft_data:
        l2fr_canopy = pft_data['FATES_L2FR_CANOPY_REC_PF']
        years = _make_year_axis(len(l2fr_canopy), start_year)
        ax.plot(years, l2fr_canopy, 'b-', linewidth=1.5,
                label=f'PFT#{pft_id} Canopy L2FR')
        has_data = True

        # Stats
        mean_val = float(np.nanmean(l2fr_canopy))
        cv = float(np.nanstd(l2fr_canopy) / max(mean_val, 1e-10))
        _stats_box(ax, f'Mean L2FR: {mean_val:.3f}\nCV: {cv:.3f}')

    # PFT-level understory L2FR
    if 'FATES_L2FR_USTORY_REC_PF' in pft_data:
        l2fr_ustory = pft_data['FATES_L2FR_USTORY_REC_PF']
        years = _make_year_axis(len(l2fr_ustory), start_year)
        ax.plot(years, l2fr_ustory, 'c--', linewidth=1.2,
                label=f'PFT#{pft_id} Understory L2FR', alpha=0.7)

    if not has_data:
        plt.close(fig)
        return None

    ax.set_xlabel('Year')
    ax.set_ylabel('L2FR (leaf:fineroot ratio)')
    ax.set_title(f'L2FR Allocation Dynamics — PFT#{pft_id}')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches='tight')
        plt.close(fig)
        return output_path
    plt.close(fig)
    return None


def plot_allocation_rates(
    data: Dict,
    pft_id: int,
    output_path: Optional[str] = None,
    start_year: int = None
) -> Optional[str]:
    """
    Plot leaf vs fine root allocation rates over time.

    Args:
        data: Output from load_netcdf_data()
        pft_id: PFT ID to plot
        output_path: Full path to save figure
        start_year: Transient start year

    Returns:
        Path to saved figure, or None
    """
    pft_data = data.get('pft_data', {}).get(pft_id, {})

    fig, ax = plt.subplots(figsize=(10, 5))

    has_data = False
    # Convert kg C/m²/s → g C/m²/yr
    scale = SECONDS_PER_YEAR * 1000

    if 'FATES_LEAF_ALLOC_SZPF' in pft_data:
        leaf_alloc = pft_data['FATES_LEAF_ALLOC_SZPF'] * scale
        years = _make_year_axis(len(leaf_alloc), start_year)
        ax.plot(years, leaf_alloc, 'g-', linewidth=1.5, label='Leaf allocation')
        has_data = True

    if 'FATES_FROOT_ALLOC_SZPF' in pft_data:
        froot_alloc = pft_data['FATES_FROOT_ALLOC_SZPF'] * scale
        years = _make_year_axis(len(froot_alloc), start_year)
        ax.plot(years, froot_alloc, 'brown', linewidth=1.5, label='Fine root allocation')
        has_data = True

    if not has_data:
        plt.close(fig)
        return None

    # Stats
    stats_lines = []
    if 'FATES_LEAF_ALLOC_SZPF' in pft_data:
        leaf_mean = float(np.nanmean(pft_data['FATES_LEAF_ALLOC_SZPF'] * scale))
        stats_lines.append(f'Leaf alloc mean: {leaf_mean:.1f} g C/m²/yr')
    if 'FATES_FROOT_ALLOC_SZPF' in pft_data:
        froot_mean = float(np.nanmean(pft_data['FATES_FROOT_ALLOC_SZPF'] * scale))
        stats_lines.append(f'Froot alloc mean: {froot_mean:.1f} g C/m²/yr')
    if len(stats_lines) == 2:
        ratio = leaf_mean / max(froot_mean, 1e-10)
        stats_lines.append(f'Alloc L2FR: {ratio:.2f}')
    if stats_lines:
        _stats_box(ax, '\n'.join(stats_lines))

    ax.set_xlabel('Year')
    ax.set_ylabel('Allocation Rate (g C/m²/yr)')
    ax.set_title(f'Allocation Rates — PFT#{pft_id}')
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3, linestyle='--')

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches='tight')
        plt.close(fig)
        return output_path
    plt.close(fig)
    return None


# =============================================================================
# Main composite figure
# =============================================================================

def plot_pft_diagnosis(
    data: Dict,
    diagnosis: Dict,
    pft_id: int,
    targets: Dict[str, float],
    comparison_pfts: List[int],
    output_dir: str,
    filename_prefix: str = ""
) -> Optional[str]:
    """
    Create a 6-panel composite diagnostic figure for a PFT.

    Panels:
        A. Fine Root Biomass trajectory (with target)
        B. Leaf Biomass trajectory (with target)
        C. Nutrient Limitation severity (uptake/demand ratio)
        D. Light Competition (GPP by PFT)
        E. L2FR Seasonal Dynamics (site + PFT level)
        F. Allocation Rates (leaf vs froot)

    Args:
        data: Output from load_netcdf_data()
        diagnosis: Output from run_pft_diagnosis()
        pft_id: PFT ID being diagnosed
        targets: Dict with 'leaf' and/or 'froot' targets (g C/m²)
        comparison_pfts: Other PFT IDs for competition panel
        output_dir: Directory to save figure
        filename_prefix: Prefix for figure filename (e.g., "r02_exp01_iter01_")

    Returns:
        Path to saved figure, or None if plotting fails
    """
    try:
        pft_data = data.get('pft_data', {}).get(pft_id, {})
        if not pft_data:
            logger.warning(f"No data for PFT#{pft_id}, skipping plot")
            return None

        start_year = int(os.environ.get('A2MC_TRANS_START_YEAR', '1901'))

        fig, axes = plt.subplots(3, 2, figsize=(16, 14))
        fig.suptitle(f'PFT#{pft_id} Diagnostic Overview', fontsize=16, fontweight='bold', y=0.98)

        # --- Panel A: Fine Root Biomass ---
        ax = axes[0, 0]
        if 'FATES_FROOTC_SZPF' in pft_data:
            biomass = pft_data['FATES_FROOTC_SZPF'] * 1000
            years = _make_year_axis(len(biomass), start_year)
            ax.plot(years, biomass, 'b-', linewidth=1.2, label=f'PFT#{pft_id}')
            if 'froot' in targets:
                ax.axhline(targets['froot'], color='red', linestyle='--',
                           linewidth=2, label=f"Target: {targets['froot']:.1f}")
            final = float(np.mean(biomass[-12:])) if len(biomass) >= 12 else float(np.mean(biomass))
            stats = f'Final yr mean: {final:.1f}'
            if 'froot' in targets:
                stats += f'\nError: {100*(final - targets["froot"])/targets["froot"]:+.1f}%'
            _stats_box(ax, stats)
        ax.set_title('A. Fine Root Biomass', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('Biomass (g C/m²)')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # --- Panel B: Leaf Biomass ---
        ax = axes[0, 1]
        if 'FATES_LEAFC_SZPF' in pft_data:
            biomass = pft_data['FATES_LEAFC_SZPF'] * 1000
            years = _make_year_axis(len(biomass), start_year)
            ax.plot(years, biomass, 'g-', linewidth=1.2, label=f'PFT#{pft_id}')
            if 'leaf' in targets:
                ax.axhline(targets['leaf'], color='red', linestyle='--',
                           linewidth=2, label=f"Target: {targets['leaf']:.1f}")
            final = float(np.mean(biomass[-12:])) if len(biomass) >= 12 else float(np.mean(biomass))
            stats = f'Final yr mean: {final:.1f}'
            if 'leaf' in targets:
                stats += f'\nError: {100*(final - targets["leaf"])/targets["leaf"]:+.1f}%'
            _stats_box(ax, stats)
        ax.set_title('B. Leaf Biomass', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('Biomass (g C/m²)')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # --- Panel C: Nutrient Limitation ---
        ax = axes[1, 0]
        has_nutrient = False
        for nutrient_name, demand_var, uptake_var, color in [
            ('P', 'FATES_PDEMAND_SZPF', 'FATES_PUPTAKE_SZPF', 'purple'),
            ('N', 'FATES_NDEMAND_SZPF', 'FATES_NUPTAKE_SZPF', 'green'),
        ]:
            if demand_var in pft_data and uptake_var in pft_data:
                demand = pft_data[demand_var]
                uptake = pft_data[uptake_var]
                ratio = np.where(demand > 0, uptake / demand, np.nan)
                years = _make_year_axis(len(ratio), start_year)
                ax.plot(years, ratio, color=color, linewidth=1.0,
                        label=f'{nutrient_name} uptake/demand', alpha=0.8)
                has_nutrient = True
        if has_nutrient:
            ax.axhline(1.0, color='gray', linestyle='--', linewidth=1.5,
                       alpha=0.6, label='No limitation')
            xlim = ax.get_xlim()
            ax.fill_between([xlim[0], xlim[1]], -0.05, 0.0,
                            color='red', alpha=0.1, label='Starvation zone')
            ax.set_xlim(xlim)
            ax.set_ylim(-0.05, max(1.5, ax.get_ylim()[1]))

            # Primary limitation from diagnosis
            primary = diagnosis.get('summary', {}).get('nutrient_limitation', 'unknown')
            _stats_box(ax, f'Primary limitation: {primary}')
        ax.set_title(f'C. Nutrient Limitation — PFT#{pft_id}', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('Uptake / Demand Ratio')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # --- Panel D: Light Competition ---
        ax = axes[1, 1]
        all_pft_ids = sorted(set([pft_id] + comparison_pfts))
        colors_d = plt.cm.Set1(np.linspace(0, 1, max(len(all_pft_ids), 3)))
        has_gpp = False
        gpp_means = {}
        for i, pid in enumerate(all_pft_ids):
            pid_data = data.get('pft_data', {}).get(pid, {})
            if 'FATES_GPP_PF' in pid_data:
                gpp = pid_data['FATES_GPP_PF'] * 86400 * 1000  # → g C/m²/day
                years = _make_year_axis(len(gpp), start_year)
                ax.plot(years, gpp, color=colors_d[i], linewidth=1.2,
                        label=f'PFT#{pid}', alpha=0.8)
                gpp_means[pid] = float(np.nanmean(gpp))
                has_gpp = True
        if has_gpp and gpp_means:
            dominant = max(gpp_means, key=gpp_means.get)
            stats_lines = ['Mean GPP (g C/m²/d):']
            for pid in all_pft_ids:
                if pid in gpp_means:
                    marker = ' *' if pid == dominant else ''
                    stats_lines.append(f'  PFT#{pid}: {gpp_means[pid]:.3f}{marker}')
            _stats_box(ax, '\n'.join(stats_lines))
        ax.set_title('D. Light Competition — GPP by PFT', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('GPP (g C/m²/day)')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # --- Panel E: L2FR Dynamics ---
        ax = axes[2, 0]
        if 'FATES_L2FR' in data:
            l2fr_site = data['FATES_L2FR']
            years = _make_year_axis(len(l2fr_site), start_year)
            ax.plot(years, l2fr_site, 'k-', linewidth=1.0, label='Site-level', alpha=0.5)
        if 'FATES_L2FR_CANOPY_REC_PF' in pft_data:
            l2fr_can = pft_data['FATES_L2FR_CANOPY_REC_PF']
            years = _make_year_axis(len(l2fr_can), start_year)
            ax.plot(years, l2fr_can, 'b-', linewidth=1.5,
                    label=f'PFT#{pft_id} Canopy')
            mean_val = float(np.nanmean(l2fr_can))
            cv = float(np.nanstd(l2fr_can) / max(mean_val, 1e-10))
            _stats_box(ax, f'Mean: {mean_val:.3f}\nCV: {cv:.3f}')
        if 'FATES_L2FR_USTORY_REC_PF' in pft_data:
            l2fr_ust = pft_data['FATES_L2FR_USTORY_REC_PF']
            years = _make_year_axis(len(l2fr_ust), start_year)
            ax.plot(years, l2fr_ust, 'c--', linewidth=1.0,
                    label=f'PFT#{pft_id} Understory', alpha=0.7)
        ax.set_title(f'E. L2FR Dynamics — PFT#{pft_id}', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('L2FR')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # --- Panel F: Allocation Rates ---
        ax = axes[2, 1]
        scale = SECONDS_PER_YEAR * 1000
        has_alloc = False
        if 'FATES_LEAF_ALLOC_SZPF' in pft_data:
            leaf_alloc = pft_data['FATES_LEAF_ALLOC_SZPF'] * scale
            years = _make_year_axis(len(leaf_alloc), start_year)
            ax.plot(years, leaf_alloc, 'g-', linewidth=1.5, label='Leaf allocation')
            has_alloc = True
        if 'FATES_FROOT_ALLOC_SZPF' in pft_data:
            froot_alloc = pft_data['FATES_FROOT_ALLOC_SZPF'] * scale
            years = _make_year_axis(len(froot_alloc), start_year)
            ax.plot(years, froot_alloc, color='brown', linewidth=1.5,
                    label='Fine root allocation')
            has_alloc = True
        if has_alloc:
            stats_lines = []
            if 'FATES_LEAF_ALLOC_SZPF' in pft_data:
                lm = float(np.nanmean(pft_data['FATES_LEAF_ALLOC_SZPF'] * scale))
                stats_lines.append(f'Leaf: {lm:.1f} g C/m²/yr')
            if 'FATES_FROOT_ALLOC_SZPF' in pft_data:
                fm = float(np.nanmean(pft_data['FATES_FROOT_ALLOC_SZPF'] * scale))
                stats_lines.append(f'Froot: {fm:.1f} g C/m²/yr')
            if len(stats_lines) == 2:
                ratio = lm / max(fm, 1e-10)
                stats_lines.append(f'Alloc L2FR: {ratio:.2f}')
            _stats_box(ax, '\n'.join(stats_lines))
        ax.set_title(f'F. Allocation Rates — PFT#{pft_id}', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('Allocation (g C/m²/yr)')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # Save
        fig.tight_layout(rect=[0, 0, 1, 0.96])

        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        filename = f"{filename_prefix}pft{pft_id}_diagnosis.png"
        output_path = str(output_dir_path / filename)
        fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"Saved diagnostic figure: {output_path}")
        return output_path

    except Exception as e:
        logger.warning(f"Failed to create diagnostic plot for PFT#{pft_id}: {e}")
        plt.close('all')
        return None


# =============================================================================
# Mortality Components Plot
# =============================================================================

def plot_mortality_components(
    mortality_data: Dict,
    pft_ids: List[int],
    output_path: Optional[str] = None,
    title_suffix: str = ""
) -> Optional[str]:
    """
    Plot mortality component breakdown (stacked area) for each PFT.

    Creates one subplot per PFT, stacking hydraulic, C starvation, and fire
    mortality fluxes over time. Vertical dashed lines mark phase boundaries
    (ADSP/RGSP/TRANS).

    Args:
        mortality_data: Output from extract_mortality_timeseries()
                        Keys: 'time', 'phases', 'pft_data'
        pft_ids: PFT IDs to plot (one subplot each)
        output_path: Full path to save figure. If None, returns None.
        title_suffix: Optional suffix for figure title (e.g., "Case 3930")

    Returns:
        Path to saved figure, or None
    """
    time = mortality_data.get('time', np.array([]))
    phases = mortality_data.get('phases', {})
    pft_all = mortality_data.get('pft_data', {})

    if len(time) == 0 or not pft_ids:
        logger.warning("No mortality data to plot")
        return None

    n_pfts = len(pft_ids)
    fig, axes = plt.subplots(n_pfts, 1, figsize=(12, 4.5 * n_pfts), squeeze=False)

    component_colors = {
        'hydraulic': '#CC0000',      # red
        'cstarvation': '#FF8C00',    # dark orange
        'fire': '#6A0DAD',           # purple
    }
    component_labels = {
        'hydraulic': 'Hydraulic',
        'cstarvation': 'C Starvation',
        'fire': 'Fire',
    }
    component_order = ['hydraulic', 'cstarvation', 'fire']

    for row, pft_id in enumerate(pft_ids):
        ax = axes[row, 0]
        pft_data = pft_all.get(pft_id, {})

        # Build arrays for stacking
        stack_arrays = []
        stack_labels = []
        stack_colors = []
        for comp in component_order:
            if comp in pft_data and len(pft_data[comp]) == len(time):
                arr = np.clip(pft_data[comp], 0, None)  # no negatives for stacking
                stack_arrays.append(arr)
                stack_labels.append(component_labels[comp])
                stack_colors.append(component_colors[comp])

        if stack_arrays:
            ax.stackplot(time, *stack_arrays, labels=stack_labels,
                         colors=stack_colors, alpha=0.85)
        else:
            ax.text(0.5, 0.5, f'No mortality data for PFT#{pft_id}',
                    transform=ax.transAxes, ha='center', fontsize=12)

        # Phase boundary lines
        for phase_name, (start_idx, end_idx) in phases.items():
            if start_idx > 0 and start_idx < len(time):
                ax.axvline(time[start_idx], color='gray', linestyle='--',
                           linewidth=1, alpha=0.6)

        # Stats box: dominant cause in final 120 months (10 years)
        if stack_arrays:
            n_final = min(120, len(time))
            final_means = {}
            for comp, arr in zip(component_order, stack_arrays):
                final_means[comp] = float(np.mean(arr[-n_final:]))
            total = sum(final_means.values())
            if total > 0:
                stats_lines = ['Final 10yr mean:']
                for comp in component_order:
                    if comp in final_means:
                        pct = 100 * final_means[comp] / total
                        stats_lines.append(
                            f'  {component_labels.get(comp, comp)}: '
                            f'{final_means[comp]:.1f} ({pct:.0f}%)')
                _stats_box(ax, '\n'.join(stats_lines))

        ax.set_title(f'PFT{pft_id}: Mortality Components', fontsize=13, fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('C Flux (g C m$^{-2}$ yr$^{-1}$)')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.2, linestyle='--')
        ax.set_xlim(time[0], time[-1])

    suptitle = 'Mortality Components by PFT'
    if title_suffix:
        suptitle += f' — {title_suffix}'
    fig.suptitle(suptitle, fontsize=15, fontweight='bold', y=1.01)
    fig.tight_layout()

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches='tight')
        plt.close(fig)
        logger.info(f"Saved mortality plot: {output_path}")
        return output_path
    plt.close(fig)
    return None


# =============================================================================
# P Mass Balance Plot
# =============================================================================

def plot_p_mass_balance(
    nc_file: str,
    output_path: Optional[str] = None,
    title_suffix: str = ""
) -> Optional[str]:
    """
    Plot 6-panel P mass balance overview from a NetCDF output file.

    Panels:
        A. Soil Inorganic P Pools (line plot: SMINP, LABILEP, SECONDP, OCCLP, PRIMP)
        B. Stacked Soil Inorganic P (area plot: same pools, stacked)
        C. Litter P Pools (LITR1P, LITR2P, LITR3P, total)
        D. Plant P and Soil Organic P (FATES_VEGP, FATES_STOREP, Total SOM P)
        E. P Fluxes (uptake, efflux, leaching, deposition)
        F. Total Ecosystem P Budget (total ecosystem, total inorganic, total SOM)

    Reads directly from NetCDF (does NOT require pre-extracted NutrientBudget).

    Args:
        nc_file: Path to NetCDF output file (can be multi-phase concatenated
                 or single-phase)
        output_path: Full path to save figure. If None, returns None.
        title_suffix: Optional suffix for figure title (e.g., "Case 2678")

    Returns:
        Path to saved figure, or None
    """
    try:
        import netCDF4 as nc
    except ImportError:
        logger.error("netCDF4 required for P mass balance plot")
        return None

    try:
        ds = nc.Dataset(nc_file, 'r')
    except Exception as e:
        logger.error(f"Cannot open {nc_file}: {e}")
        return None

    try:
        n_time = ds.dimensions['time'].size
        # Real calendar year axis (e.g., 1901-2019)
        sim_year = _make_year_axis(n_time)

        def _read(var_name):
            """Read a variable, collapsing spatial dims, handling missing."""
            if var_name not in ds.variables:
                return np.zeros(n_time)
            arr = ds.variables[var_name][:]
            if hasattr(arr, 'filled'):
                arr = arr.filled(0.0)
            if arr.ndim == 1:
                return arr
            elif arr.ndim == 2:
                dims = ds.variables[var_name].dimensions
                if len(dims) == 2 and dims[1] in ('levdcmp', 'levsoi', 'levgrnd'):
                    return np.sum(arr, axis=1)
                return arr[:, 0]
            elif arr.ndim == 3:
                return np.sum(arr[:, :, 0], axis=1)
            return arr

        def _to_g(arr, source='ELM'):
            """Convert pool: FATES kg/m2 → g/m2, ELM already g/m2."""
            return arr * 1000.0 if source == 'FATES' else arr.copy()

        def _flux_to_g_yr(arr, source='ELM'):
            """Convert flux to g/m2/yr (approximate: mean rate × 365 × 86400).
            ELM: g/m2/s, FATES: kg/m2/s."""
            scale = 365 * 86400
            if source == 'FATES':
                scale *= 1000.0
            return arr * scale

        # ---- Read pools (g/m2) ----
        sminp = _read('SMINP')
        labilep = _read('LABILEP')
        secondp = _read('SECONDP')
        occlp = _read('OCCLP')
        primp = _read('PRIMP')

        # Litter P: try site-level first, then _vr (per-layer, summed by _read)
        litr1p = _read('LITR1P')
        if np.all(litr1p == 0):
            litr1p = _read('LITR1P_vr')
        litr2p = _read('LITR2P')
        if np.all(litr2p == 0):
            litr2p = _read('LITR2P_vr')
        litr3p = _read('LITR3P')
        if np.all(litr3p == 0):
            litr3p = _read('LITR3P_vr')
        total_litrp = litr1p + litr2p + litr3p

        vegp = _to_g(_read('FATES_VEGP'), 'FATES')
        storep = _to_g(_read('FATES_STOREP'), 'FATES')
        # Total SOM P: try TOTSOMP, then site-level SOIL*P, then _vr variants
        totsomp = _read('TOTSOMP')
        if np.all(totsomp == 0):
            totsomp = _read('SOIL1P') + _read('SOIL2P') + _read('SOIL3P') + _read('SOIL4P')
        if np.all(totsomp == 0):
            totsomp = (_read('SOIL1P_vr') + _read('SOIL2P_vr')
                       + _read('SOIL3P_vr') + _read('SOIL4P_vr'))

        # ---- Read fluxes (g/m2/yr) ----
        p_uptake = _flux_to_g_yr(_read('FATES_PUPTAKE'), 'FATES')
        p_efflux = _flux_to_g_yr(_read('FATES_PEFFLUX'), 'FATES')
        sminp_leached = _flux_to_g_yr(_read('SMINP_LEACHED'), 'ELM')
        # ELM SMINP→Plant (same as FATES uptake from ELM side)
        elm_sminp_to_plant = _flux_to_g_yr(_read('SMINP_TO_PLANT'), 'ELM')

        # ---- Ecosystem totals ----
        total_inorganic = sminp + labilep + secondp + occlp + primp
        total_ecosystem = total_inorganic + total_litrp + totsomp + vegp + storep

        # ---- Create figure ----
        fig, axes = plt.subplots(3, 2, figsize=(16, 14))
        suptitle = 'P Mass Balance Time Series'
        if title_suffix:
            suptitle += f': {title_suffix}'
        fig.suptitle(suptitle, fontsize=15, fontweight='bold', y=0.98)

        # --- Panel A: Soil Inorganic P Pools (lines) ---
        ax = axes[0, 0]
        ax.plot(sim_year, sminp, 'c-', linewidth=1.2, label='SMINP (mineral)')
        ax.plot(sim_year, labilep, color='orange', linewidth=1.2, label='LABILEP (labile)')
        ax.plot(sim_year, secondp, 'r-', linewidth=1.2, label='SECONDP (secondary)')
        ax.plot(sim_year, occlp, color='brown', linewidth=1.2, label='OCCLP (occluded)')
        ax.plot(sim_year, primp, color='teal', linewidth=1.2, label='PRIMP (primary)')
        ax.set_title('A. Soil Inorganic P Pools', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('P Pool (g P m$^{-2}$)')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # --- Panel B: Stacked Soil Inorganic P ---
        ax = axes[0, 1]
        ax.stackplot(sim_year, primp, occlp, secondp, labilep, sminp,
                     labels=['PRIMP', 'OCCLP', 'SECONDP', 'LABILEP', 'SMINP'],
                     colors=['teal', 'brown', 'red', 'orange', 'cyan'],
                     alpha=0.7)
        ax.plot(sim_year, total_inorganic, 'k-', linewidth=1.5, label='Total')
        ax.set_title('B. Stacked Soil Inorganic P', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('P Pool (g P m$^{-2}$)')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # --- Panel C: Litter P Pools ---
        ax = axes[1, 0]
        ax.plot(sim_year, litr1p, 'b-', linewidth=1.2, label='LITR1P (labile)')
        ax.plot(sim_year, litr2p, color='orange', linewidth=1.2, label='LITR2P (cellulose)')
        ax.plot(sim_year, litr3p, 'r-', linewidth=1.2, label='LITR3P (lignin)')
        ax.plot(sim_year, total_litrp, 'k--', linewidth=1.5, label='Total Litter P')
        # Flag if litter P is accumulating
        if len(total_litrp) > 24:
            initial_litr = float(np.mean(total_litrp[:12]))
            final_litr = float(np.mean(total_litrp[-12:]))
            if final_litr > initial_litr * 2:
                ax.annotate('P ACCUMULATING!', xy=(sim_year[-1], final_litr),
                            fontsize=10, color='red', fontweight='bold',
                            ha='right', va='bottom',
                            bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.9))
        ax.set_title('C. Litter P Pools (WHERE P ACCUMULATES!)', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('P Pool (g P m$^{-2}$)')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # --- Panel D: Plant P and Soil Organic P ---
        ax = axes[1, 1]
        ax.plot(sim_year, vegp, 'g-', linewidth=1.2, label='Vegetation P')
        ax.plot(sim_year, storep, color='orange', linewidth=1.2, label='Storage P')
        if not np.all(totsomp == 0):
            ax.plot(sim_year, totsomp, 'r-', linewidth=1.2, label='Total SOM P')
        ax.set_title('D. Plant P and Soil Organic P', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('P Pool (g P m$^{-2}$)')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # --- Panel E: P Fluxes ---
        ax = axes[2, 0]
        ax.plot(sim_year, p_uptake, 'c-', linewidth=1.2, label='FATES P uptake')
        if not np.all(elm_sminp_to_plant == 0):
            ax.plot(sim_year, elm_sminp_to_plant, color='orange', linewidth=1.0,
                    label='ELM SMINP→Plant', alpha=0.7)
        ax.plot(sim_year, p_efflux, 'r-', linewidth=1.0, label='FATES P efflux', alpha=0.7)
        ax.plot(sim_year, sminp_leached, color='purple', linewidth=1.0,
                label='SMINP leached', alpha=0.7)
        ax.set_title('E. P Fluxes', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('P Flux (g P m$^{-2}$ yr$^{-1}$)')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        # --- Panel F: Total Ecosystem P Budget ---
        ax = axes[2, 1]
        ax.plot(sim_year, total_ecosystem, 'b-', linewidth=1.5, label='Total Ecosystem P')
        ax.plot(sim_year, total_inorganic, color='orange', linewidth=1.2,
                label='Total Inorganic P')
        if not np.all(totsomp == 0):
            ax.plot(sim_year, totsomp, 'r-', linewidth=1.2, label='Total SOM P')
        # Stats box
        if len(total_ecosystem) > 24:
            initial_eco = float(np.mean(total_ecosystem[:12]))
            final_eco = float(np.mean(total_ecosystem[-12:]))
            delta = final_eco - initial_eco
            pct = 100 * delta / initial_eco if initial_eco > 0 else 0
            _stats_box(ax, f'Initial: {initial_eco:.1f} g P/m²\n'
                          f'Final: {final_eco:.1f} g P/m²\n'
                          f'Δ: {delta:.1f} g P/m² ({pct:.1f}%)',
                       loc='upper left')
        ax.set_title('F. Total Ecosystem P Budget', fontweight='bold')
        ax.set_xlabel('Year')
        ax.set_ylabel('P Pool (g P m$^{-2}$)')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3, linestyle='--')

        fig.tight_layout(rect=[0, 0, 1, 0.96])

        ds.close()

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches='tight')
            plt.close(fig)
            logger.info(f"Saved P mass balance plot: {output_path}")
            return output_path
        plt.close(fig)
        return None

    except Exception as e:
        ds.close()
        logger.warning(f"Failed to create P mass balance plot: {e}")
        plt.close('all')
        return None
