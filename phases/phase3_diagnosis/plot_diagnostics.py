#!/usr/bin/env python3
"""
Phase 3 Diagnosis: Diagnostic Plotting Module

Creates publication-quality diagnostic figures for PFT diagnosis results.
Figures are saved to use_cases/{site}/memory/phase_results/phase3_diagnosis/.

Functions:
    plot_pft_diagnosis()       - 6-panel composite figure (main entry point)
    plot_biomass_trajectories() - Fine root + leaf biomass time series
    plot_nutrient_limitation()  - P (or N) uptake/demand ratio
    plot_light_competition()    - GPP ratio between PFTs
    plot_allocation_dynamics()  - L2FR seasonal dynamics
    plot_allocation_rates()     - Leaf vs froot allocation rates

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
