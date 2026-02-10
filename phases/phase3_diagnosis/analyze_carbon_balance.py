#!/usr/bin/env python3
"""
Carbon Balance Analysis for A2MC Phase 3 Diagnosis

Analyzes cumulative GPP vs maintenance respiration to detect carbon deficits.
When MR exceeds GPP, the plant accumulates a carbon deficit that prevents growth.
This tool identifies these bottleneck periods.

Usage (Python API):
    from phases.phase3_diagnosis import (
        analyze_carbon_balance,
        detect_carbon_bottleneck,
        get_carbon_summary_for_ai
    )

    # Analyze carbon balance
    results = analyze_carbon_balance(
        data=cnp_diagnostics_df,
        focus_year=2007,
        reference_doy=127  # MODIS leaf-on DOY
    )

    # Get AI-ready summary
    summary = get_carbon_summary_for_ai(results)

Usage (CLI):
    python -m phases.phase3_diagnosis.analyze_carbon_balance \\
        --data cnp_diagnostics.csv \\
        --focus-year 2007 \\
        --reference-doy 127 \\
        --output carbon_balance_results.json

Author: Jing Tao with Claude
Created: February 2026
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DeficitPeriod:
    """Represents a period where MR > GPP (carbon deficit)."""
    start_doy: int
    end_doy: int
    duration: int  # days
    cumulative_deficit: float  # g C/m²
    mean_daily_deficit: float  # g C/m²/day


@dataclass
class CarbonBalanceResults:
    """Complete carbon balance analysis results."""
    focus_year: int
    deficit_periods: list  # List of DeficitPeriod
    total_deficit: float  # g C/m² (max cumulative deficit)
    deficit_at_reference: Optional[float]  # Deficit at reference DOY
    crossover_doy: Optional[int]  # DOY when cumulative GPP > cumulative MR
    bottleneck_detected: bool
    spring_stats: dict  # Statistics for spring period
    summary_metrics: dict
    visualization_path: Optional[str] = None


# =============================================================================
# CARBON BALANCE ANALYSIS
# =============================================================================

def calculate_cumulative_fluxes(
    data: pd.DataFrame,
    gpp_col: str = "FATES_GPP",
    mr_col: str = "FATES_MAINT_RESP",
    npp_col: str = "FATES_NPP"
) -> pd.DataFrame:
    """
    Calculate cumulative carbon fluxes.

    Parameters
    ----------
    data : pd.DataFrame
        Daily data with GPP, MR, NPP columns
    gpp_col : str
        Column name for GPP
    mr_col : str
        Column name for maintenance respiration
    npp_col : str
        Column name for NPP

    Returns
    -------
    pd.DataFrame
        Data with added cumulative columns
    """
    result = data.copy()

    result['cumulative_gpp'] = result[gpp_col].cumsum()
    result['cumulative_mr'] = result[mr_col].cumsum()

    if npp_col in result.columns:
        result['cumulative_npp'] = result[npp_col].cumsum()

    # Carbon deficit: positive means MR has exceeded GPP
    result['carbon_deficit'] = result['cumulative_mr'] - result['cumulative_gpp']

    return result


def detect_deficit_periods(
    data: pd.DataFrame,
    min_duration: int = 5
) -> list:
    """
    Detect continuous periods of carbon deficit.

    Parameters
    ----------
    data : pd.DataFrame
        Data with 'doy' and 'carbon_deficit' columns
    min_duration : int
        Minimum number of days to count as a deficit period

    Returns
    -------
    list
        List of DeficitPeriod objects
    """
    periods = []

    # Find where deficit is positive (MR > GPP cumulatively)
    in_deficit = data['carbon_deficit'] > 0

    # Track deficit periods
    start_idx = None
    for i, (idx, row) in enumerate(data.iterrows()):
        if in_deficit.iloc[i] and start_idx is None:
            start_idx = i
        elif not in_deficit.iloc[i] and start_idx is not None:
            # Period ended
            end_idx = i - 1
            duration = end_idx - start_idx + 1
            if duration >= min_duration:
                period_data = data.iloc[start_idx:end_idx+1]
                periods.append(DeficitPeriod(
                    start_doy=int(period_data['doy'].iloc[0]),
                    end_doy=int(period_data['doy'].iloc[-1]),
                    duration=duration,
                    cumulative_deficit=float(period_data['carbon_deficit'].max()),
                    mean_daily_deficit=float(
                        (period_data['cumulative_mr'].diff() - period_data['cumulative_gpp'].diff()).mean()
                    )
                ))
            start_idx = None

    # Check if still in deficit at end
    if start_idx is not None:
        period_data = data.iloc[start_idx:]
        duration = len(period_data)
        if duration >= min_duration:
            periods.append(DeficitPeriod(
                start_doy=int(period_data['doy'].iloc[0]),
                end_doy=int(period_data['doy'].iloc[-1]),
                duration=duration,
                cumulative_deficit=float(period_data['carbon_deficit'].max()),
                mean_daily_deficit=float(
                    (period_data['cumulative_mr'].diff() - period_data['cumulative_gpp'].diff()).mean()
                )
            ))

    return periods


def find_crossover_doy(data: pd.DataFrame) -> Optional[int]:
    """
    Find the DOY when cumulative GPP first exceeds cumulative MR.

    Parameters
    ----------
    data : pd.DataFrame
        Data with 'doy', 'cumulative_gpp', 'cumulative_mr'

    Returns
    -------
    int or None
        DOY of crossover, or None if GPP never exceeds MR
    """
    crossover_mask = data['cumulative_gpp'] > data['cumulative_mr']
    if crossover_mask.any():
        first_idx = crossover_mask.idxmax()
        return int(data.loc[first_idx, 'doy'])
    return None


def calculate_spring_stats(
    data: pd.DataFrame,
    start_doy: int = 100,
    end_doy: int = 140,
    gpp_col: str = "FATES_GPP",
    mr_col: str = "FATES_MAINT_RESP"
) -> dict:
    """
    Calculate statistics for the spring period.

    Parameters
    ----------
    data : pd.DataFrame
        Daily data
    start_doy : int
        Start of spring period
    end_doy : int
        End of spring period
    gpp_col : str
        Column for GPP
    mr_col : str
        Column for MR

    Returns
    -------
    dict
        Spring statistics
    """
    spring_data = data[(data['doy'] >= start_doy) & (data['doy'] <= end_doy)]

    if len(spring_data) == 0:
        return {"error": "No data in spring period"}

    mean_gpp = float(spring_data[gpp_col].mean())
    mean_mr = float(spring_data[mr_col].mean())
    daily_deficit = mean_mr - mean_gpp

    return {
        "period": f"DOY {start_doy}-{end_doy}",
        "n_days": len(spring_data),
        "mean_daily_gpp": mean_gpp,
        "mean_daily_mr": mean_mr,
        "daily_deficit": daily_deficit,
        "deficit_positive": daily_deficit > 0
    }


def analyze_carbon_balance(
    data: pd.DataFrame,
    focus_year: Optional[int] = None,
    reference_doy: Optional[int] = None,
    spring_period: tuple = (100, 140),
    gpp_col: str = "FATES_GPP",
    mr_col: str = "FATES_MAINT_RESP",
    npp_col: str = "FATES_NPP"
) -> CarbonBalanceResults:
    """
    Analyze carbon balance to detect growth bottlenecks.

    This is the main entry point for carbon balance analysis.

    Parameters
    ----------
    data : pd.DataFrame
        CNP diagnostics data with GPP, MR, NPP columns and 'year', 'doy' columns
    focus_year : int, optional
        Year to analyze. If None, uses first year in data.
    reference_doy : int, optional
        Reference DOY for comparison (e.g., MODIS leaf-on at 127)
    spring_period : tuple
        (start_doy, end_doy) for spring statistics
    gpp_col : str
        Column name for GPP
    mr_col : str
        Column name for maintenance respiration
    npp_col : str
        Column name for NPP

    Returns
    -------
    CarbonBalanceResults
        Complete analysis results

    Example
    -------
    >>> results = analyze_carbon_balance(
    ...     data=cnp_df,
    ...     focus_year=2007,
    ...     reference_doy=127  # MODIS leaf-on
    ... )
    >>> print(f"Carbon deficit at MODIS leaf-on: {results.deficit_at_reference:.1f} g C/m²")
    >>> if results.bottleneck_detected:
    ...     print("Carbon bottleneck detected - plants cannot grow!")
    """
    # Filter to focus year
    if focus_year is None:
        focus_year = int(data['year'].iloc[0])

    year_data = data[data['year'] == focus_year].copy()

    if len(year_data) == 0:
        raise ValueError(f"No data for year {focus_year}")

    # Calculate cumulative fluxes
    year_data = calculate_cumulative_fluxes(year_data, gpp_col, mr_col, npp_col)

    # Detect deficit periods
    deficit_periods = detect_deficit_periods(year_data)

    # Find crossover DOY
    crossover_doy = find_crossover_doy(year_data)

    # Calculate deficit at reference DOY
    deficit_at_reference = None
    if reference_doy is not None:
        ref_idx = (year_data['doy'] - reference_doy).abs().idxmin()
        if ref_idx is not None:
            deficit_at_reference = float(year_data.loc[ref_idx, 'carbon_deficit'])

    # Calculate total deficit (maximum cumulative)
    total_deficit = float(year_data['carbon_deficit'].max())

    # Spring statistics
    spring_stats = calculate_spring_stats(
        year_data, spring_period[0], spring_period[1], gpp_col, mr_col
    )

    # Detect bottleneck
    # Bottleneck = significant deficit at reference time OR late crossover
    bottleneck_detected = False
    if deficit_at_reference is not None and deficit_at_reference > 10:
        bottleneck_detected = True
    if crossover_doy is not None and reference_doy is not None:
        if crossover_doy > reference_doy + 30:
            bottleneck_detected = True

    # Summary metrics
    summary_metrics = {
        "total_cumulative_gpp": float(year_data['cumulative_gpp'].iloc[-1]),
        "total_cumulative_mr": float(year_data['cumulative_mr'].iloc[-1]),
        "max_cumulative_deficit": total_deficit,
        "n_deficit_periods": len(deficit_periods),
        "total_deficit_days": sum(p.duration for p in deficit_periods),
        "crossover_doy": crossover_doy,
        "reference_doy": reference_doy,
        "deficit_at_reference": deficit_at_reference
    }

    return CarbonBalanceResults(
        focus_year=focus_year,
        deficit_periods=deficit_periods,
        total_deficit=total_deficit,
        deficit_at_reference=deficit_at_reference,
        crossover_doy=crossover_doy,
        bottleneck_detected=bottleneck_detected,
        spring_stats=spring_stats,
        summary_metrics=summary_metrics
    )


def detect_carbon_bottleneck(
    data: pd.DataFrame,
    focus_year: Optional[int] = None,
    threshold_deficit: float = 10.0
) -> dict:
    """
    Quick check for carbon bottleneck.

    Simpler than full analyze_carbon_balance(), just checks if
    there's a significant carbon deficit.

    Parameters
    ----------
    data : pd.DataFrame
        CNP diagnostics data
    focus_year : int, optional
        Year to check
    threshold_deficit : float
        Minimum deficit (g C/m²) to count as bottleneck

    Returns
    -------
    dict
        {"bottleneck": bool, "max_deficit": float, "crossover_doy": int or None}
    """
    if focus_year is None:
        focus_year = int(data['year'].iloc[0])

    year_data = data[data['year'] == focus_year].copy()
    year_data = calculate_cumulative_fluxes(year_data)

    max_deficit = float(year_data['carbon_deficit'].max())
    crossover_doy = find_crossover_doy(year_data)

    return {
        "bottleneck": max_deficit > threshold_deficit,
        "max_deficit": max_deficit,
        "crossover_doy": crossover_doy
    }


# =============================================================================
# AI SUMMARY
# =============================================================================

def get_carbon_summary_for_ai(results: CarbonBalanceResults) -> str:
    """
    Generate a summary string suitable for AI reasoning context.

    Parameters
    ----------
    results : CarbonBalanceResults
        Results from analyze_carbon_balance()

    Returns
    -------
    str
        Formatted summary for inclusion in AI prompts
    """
    lines = [
        "## Carbon Balance Analysis",
        "",
        f"**Year:** {results.focus_year}",
        f"**Bottleneck Detected:** {'YES' if results.bottleneck_detected else 'No'}",
        ""
    ]

    # Summary metrics
    m = results.summary_metrics
    lines.extend([
        "### Cumulative Fluxes (End of Year)",
        f"- Total GPP: {m['total_cumulative_gpp']:.1f} g C/m²",
        f"- Total MR: {m['total_cumulative_mr']:.1f} g C/m²",
        f"- Max Deficit: {m['max_cumulative_deficit']:.1f} g C/m²",
        ""
    ])

    # Reference DOY comparison
    if results.deficit_at_reference is not None:
        lines.extend([
            f"### At Reference DOY ({m['reference_doy']})",
            f"- Carbon Deficit: {results.deficit_at_reference:.1f} g C/m²",
        ])
        if results.crossover_doy is not None:
            gap = results.crossover_doy - m['reference_doy']
            lines.append(f"- GPP Exceeds MR: DOY {results.crossover_doy} ({gap:+d} days from reference)")
        else:
            lines.append("- GPP Never Exceeds MR in this year!")
        lines.append("")

    # Spring statistics
    s = results.spring_stats
    if "error" not in s:
        lines.extend([
            f"### Spring Period ({s['period']})",
            f"- Mean Daily GPP: {s['mean_daily_gpp']:.4f} g C/m²/day",
            f"- Mean Daily MR: {s['mean_daily_mr']:.4f} g C/m²/day",
            f"- Daily Deficit: {s['daily_deficit']:.4f} g C/m²/day",
            ""
        ])

    # Deficit periods
    if results.deficit_periods:
        lines.extend([
            "### Deficit Periods (MR > GPP)",
            ""
        ])
        for i, p in enumerate(results.deficit_periods, 1):
            lines.append(
                f"{i}. DOY {p.start_doy}-{p.end_doy} ({p.duration} days): "
                f"Cumulative deficit {p.cumulative_deficit:.1f} g C/m²"
            )
        lines.append("")

    # Key insight
    if results.bottleneck_detected:
        lines.extend([
            "### KEY INSIGHT",
            "",
            "**Carbon bottleneck detected!** The model accumulates a carbon deficit where",
            "maintenance respiration exceeds GPP. This prevents growth allocation.",
            ""
        ])
        if results.deficit_at_reference and results.summary_metrics.get('reference_doy'):
            lines.append(
                f"At reference DOY {m['reference_doy']}, when real plants are growing, "
                f"the model has a carbon deficit of {results.deficit_at_reference:.1f} g C/m²."
            )

    return "\n".join(lines)


def results_to_dict(results: CarbonBalanceResults) -> dict:
    """
    Convert results to a dictionary for JSON serialization.

    Parameters
    ----------
    results : CarbonBalanceResults
        Results from analyze_carbon_balance()

    Returns
    -------
    dict
        JSON-serializable dictionary
    """
    return {
        "focus_year": results.focus_year,
        "bottleneck_detected": results.bottleneck_detected,
        "total_deficit": results.total_deficit,
        "deficit_at_reference": results.deficit_at_reference,
        "crossover_doy": results.crossover_doy,
        "spring_stats": results.spring_stats,
        "summary_metrics": results.summary_metrics,
        "deficit_periods": [
            {
                "start_doy": p.start_doy,
                "end_doy": p.end_doy,
                "duration": p.duration,
                "cumulative_deficit": p.cumulative_deficit,
                "mean_daily_deficit": p.mean_daily_deficit
            }
            for p in results.deficit_periods
        ],
        "visualization_path": results.visualization_path
    }


# =============================================================================
# VISUALIZATION (optional)
# =============================================================================

def plot_carbon_balance(
    data: pd.DataFrame,
    results: CarbonBalanceResults,
    output_path: Optional[str] = None,
    gpp_col: str = "FATES_GPP",
    mr_col: str = "FATES_MAINT_RESP",
    npp_col: str = "FATES_NPP"
) -> Optional[str]:
    """
    Create visualization for carbon balance analysis.

    Parameters
    ----------
    data : pd.DataFrame
        CNP diagnostics data (full or single year)
    results : CarbonBalanceResults
        Analysis results
    output_path : str, optional
        Path to save plot. If None, displays interactively.
    gpp_col, mr_col, npp_col : str
        Column names

    Returns
    -------
    str or None
        Path to saved figure, or None if displayed
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("Warning: matplotlib not available for plotting")
        return None

    # Filter to focus year if needed
    if 'year' in data.columns:
        year_data = data[data['year'] == results.focus_year].copy()
    else:
        year_data = data.copy()

    # Calculate cumulative if not present
    if 'cumulative_gpp' not in year_data.columns:
        year_data = calculate_cumulative_fluxes(year_data, gpp_col, mr_col, npp_col)

    # Create figure
    fig, ax = plt.subplots(figsize=(14, 8))

    # Plot cumulative fluxes
    ax.plot(year_data['doy'], year_data['cumulative_gpp'], 'g-',
            label='Cumulative GPP', linewidth=3)
    ax.plot(year_data['doy'], year_data['cumulative_mr'], 'r-',
            label='Cumulative Maintenance Respiration', linewidth=3)

    if 'cumulative_npp' in year_data.columns:
        ax.plot(year_data['doy'], year_data['cumulative_npp'], 'b--',
                label='Cumulative NPP', linewidth=2, alpha=0.7)

    # Fill carbon deficit
    ax.fill_between(
        year_data['doy'],
        year_data['cumulative_gpp'],
        year_data['cumulative_mr'],
        where=(year_data['cumulative_mr'] > year_data['cumulative_gpp']),
        alpha=0.3, color='red',
        label='Cumulative Carbon Deficit'
    )

    # Add reference DOY line
    ref_doy = results.summary_metrics.get('reference_doy')
    if ref_doy is not None:
        ax.axvline(ref_doy, color='purple', linestyle='-.', linewidth=2.5,
                   label=f'Reference DOY ({ref_doy})')

        # Annotate deficit at reference
        if results.deficit_at_reference is not None:
            ref_idx = (year_data['doy'] - ref_doy).abs().idxmin()
            ax.annotate(
                f'Deficit: {results.deficit_at_reference:.1f} g C/m²',
                xy=(ref_doy, results.deficit_at_reference),
                xytext=(ref_doy + 20, results.deficit_at_reference + 5),
                fontsize=11, fontweight='bold', color='red',
                arrowprops=dict(arrowstyle='->', color='red', lw=2)
            )

    # Add crossover DOY line
    if results.crossover_doy is not None:
        ax.axvline(results.crossover_doy, color='blue', linestyle=':', linewidth=2,
                   alpha=0.7)
        ax.annotate(
            f'GPP > MR\n(DOY {results.crossover_doy})',
            xy=(results.crossover_doy, 0),
            xytext=(results.crossover_doy + 10, 10),
            fontsize=10, color='blue',
            arrowprops=dict(arrowstyle='->', color='blue', lw=1.5)
        )

    # Labels
    ax.set_xlabel('Day of Year', fontsize=14, fontweight='bold')
    ax.set_ylabel('Cumulative Carbon (g C/m²)', fontsize=14, fontweight='bold')
    ax.set_title(
        f'Carbon Balance Analysis - Year {results.focus_year}\n'
        f'{"BOTTLENECK DETECTED" if results.bottleneck_detected else "No bottleneck"}',
        fontsize=15, fontweight='bold'
    )
    ax.legend(loc='upper left', fontsize=11)
    ax.grid(True, alpha=0.4, linestyle='--')
    ax.set_xlim(50, 250)
    ax.axhline(0, color='black', linestyle='-', linewidth=1, alpha=0.3)

    # Add statistics text box
    s = results.spring_stats
    if "error" not in s:
        stats_text = f'''Spring Statistics ({s["period"]}):
  Mean daily GPP: {s["mean_daily_gpp"]:.4f} g C/m²/day
  Mean daily MR:  {s["mean_daily_mr"]:.4f} g C/m²/day
  Daily deficit:  {s["daily_deficit"]:.4f} g C/m²/day

Summary:
  Max cumulative deficit: {results.total_deficit:.1f} g C/m²
  GPP exceeds MR at: {"DOY " + str(results.crossover_doy) if results.crossover_doy else "NEVER"}'''

        ax.text(0.98, 0.55, stats_text, transform=ax.transAxes,
                fontsize=10, verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        return output_path
    else:
        plt.show()
        return None


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Analyze carbon balance to detect growth bottlenecks"
    )
    parser.add_argument(
        "--data", required=True,
        help="Path to CNP diagnostics CSV file"
    )
    parser.add_argument(
        "--focus-year", type=int,
        help="Year to analyze (default: first year in data)"
    )
    parser.add_argument(
        "--reference-doy", type=int,
        help="Reference DOY for comparison (e.g., MODIS leaf-on)"
    )
    parser.add_argument(
        "--spring-period",
        default="100-140",
        help="Spring period as 'start-end' (default: 100-140)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file for results"
    )
    parser.add_argument(
        "--plot",
        help="Output path for diagnostic plot"
    )

    args = parser.parse_args()

    # Load data
    print(f"Loading data from {args.data}...")
    data = pd.read_csv(args.data)

    # Parse spring period
    spring_parts = args.spring_period.split("-")
    spring_period = (int(spring_parts[0]), int(spring_parts[1]))

    # Run analysis
    print("Analyzing carbon balance...")
    results = analyze_carbon_balance(
        data=data,
        focus_year=args.focus_year,
        reference_doy=args.reference_doy,
        spring_period=spring_period
    )

    # Print summary
    print("\n" + "="*80)
    print(get_carbon_summary_for_ai(results))
    print("="*80)

    # Save results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results_to_dict(results), f, indent=2)
        print(f"\nResults saved to {args.output}")

    # Create plot
    if args.plot:
        plot_path = plot_carbon_balance(
            data=data,
            results=results,
            output_path=args.plot
        )
        if plot_path:
            print(f"Plot saved to {plot_path}")


if __name__ == "__main__":
    main()
