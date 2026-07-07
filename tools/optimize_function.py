#!/usr/bin/env python3
"""
Optimize Parameter Sets Using Multi-Target Cost Function

This script ranks parameter sets (e.g., from sensitivity analysis) based on
a composite cost function comparing simulated outputs against observations.

Terminology:
  - RE (Relative Error): |sim - obs| / obs (per-target error for snapshot data)
  - RMSRE (Root Mean Square Relative Error): sqrt(mean(RE²)) (composite cost)
  - These are NOT called NRMSE (which requires multi-point RMSE calculation)

Supports:
  - Snapshot observations (single value per target, e.g., peak biomass)
  - Multiple PFTs or gridcell-level targets
  - Configurable cost functions via cost_functions.py module

Usage:
  # As module
  from tools.optimize_function import optimize_ensemble
  results = optimize_ensemble(simulated_data, observed_targets, config)

  # As standalone script (uses Kougarok configuration)
  python optimize_function.py

Created: December 2025
Updated: January 2026 - Corrected terminology (RE/RMSRE), made generic
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union
import json

# Import cost functions from the new module
try:
    from .cost_functions import (
        CostFunction, ObservationType, aggregate_costs, to_cost,
        compute_snapshot_cost, count_targets_satisfied, within_tolerance
    )
except ImportError:
    from cost_functions import (
        CostFunction, ObservationType, aggregate_costs, to_cost,
        compute_snapshot_cost, count_targets_satisfied, within_tolerance
    )


# =============================================================================
# Configuration Classes
# =============================================================================

@dataclass
class ObsPoint:
    """
    One observation point in time for a target.

    A snapshot target has exactly one ObsPoint; a time-series target has several.
    `months` is the optional per-point averaging window (list of month numbers whose
    simulated monthly means are averaged to match this point) — defaults to [month].
    The matching layer resolves (year, month/months) to monthly timestep index(es).
    """
    year: int
    month: int
    value: float
    months: Optional[List[int]] = None     # averaging window; None => [month]
    uncertainty: Optional[float] = None     # None => fall back to Target.uncertainty

    @property
    def window(self) -> List[int]:
        return self.months if self.months else [self.month]


@dataclass
class Target:
    """Single calibration target (snapshot or time series)."""
    name: str
    observed: float = None    # snapshot value; for a series, == observations[0].value (display/back-compat)
    uncertainty: float = 0.2  # Relative uncertainty (default ±20%)
    weight: float = 1.0       # Weight in composite cost
    units: str = ""
    description: str = ""
    obs_std: float = None     # Observed standard deviation (for error bars)
    # Generic observation model. When None, this is a SNAPSHOT target whose single
    # timestep is supplied externally (ScreeningConfig time anchor) — legacy behavior.
    # When set, the target is self-contained: each ObsPoint carries its own time spec
    # and value, so snapshot (len 1) and time series (len N) share one code path.
    observations: Optional[List[ObsPoint]] = None
    # Per-target cost metric override; None => OptimizationConfig.error_method.
    cost_method: Optional[str] = None

    @property
    def n_points(self) -> int:
        """Number of observation points (1 for a snapshot)."""
        return len(self.observations) if self.observations else 1

    @property
    def is_time_series(self) -> bool:
        return self.n_points > 1

    @property
    def obs_values(self) -> np.ndarray:
        """Observed values as an array (length n_points; length-1 for snapshot)."""
        if self.observations:
            return np.array([p.value for p in self.observations], dtype=float)
        return np.array([self.observed], dtype=float)

    @property
    def min_acceptable(self) -> float:
        return self.observed * (1 - self.uncertainty)

    @property
    def max_acceptable(self) -> float:
        return self.observed * (1 + self.uncertainty)


@dataclass
class OptimizationConfig:
    """Configuration for ensemble optimization"""
    # Error metric per target
    error_method: str = 'relative_error'  # Options: relative_error, rmse, mae, etc.

    # Aggregation method for composite cost
    aggregation_method: str = 'rmsre'  # Options: rmsre, mean, max, weighted_mean

    # Tolerance for "satisfied" determination
    tolerance: float = 0.2
    tolerance_type: str = 'relative'  # relative or absolute

    # Number of top sets to select
    n_top: int = 50

    # Output settings
    output_dir: Optional[Path] = None
    save_plots: bool = True
    verbose: bool = True


@dataclass
class OptimizationResult:
    """Results from ensemble optimization"""
    ranked_indices: np.ndarray          # Sorted indices (0-based, best first)
    composite_cost: np.ndarray          # Cost for each parameter set
    individual_errors: Dict[str, np.ndarray]  # Per-target errors
    n_satisfied: np.ndarray             # Number of targets satisfied per set
    config: OptimizationConfig
    targets: Dict[str, Target]
    # Optional map from array position -> real case/parameter-set number.
    # MUST be provided when the loaded ensemble is NOT the complete contiguous
    # block 1..N (e.g. a partial ensemble with gaps). When None, set IDs fall
    # back to (position+1), which is only correct for a complete ensemble.
    case_numbers: Optional[np.ndarray] = None

    @property
    def n_sets(self) -> int:
        return len(self.composite_cost)

    @property
    def best_index(self) -> int:
        """0-based index of best set"""
        return int(self.ranked_indices[0])

    def _idx_to_set_id(self, idx) -> int:
        """Map a 0-based array position to its real set/case ID."""
        if self.case_numbers is not None:
            return int(np.asarray(self.case_numbers)[idx])
        return int(idx) + 1

    @property
    def best_set_id(self) -> int:
        """Real ID of best set (case number / row in parameter file)"""
        return self._idx_to_set_id(self.best_index)

    @property
    def best_cost(self) -> float:
        return float(self.composite_cost[self.best_index])

    def get_top_indices(self, n: Optional[int] = None) -> np.ndarray:
        """Get top N indices (0-based)"""
        n = n or self.config.n_top
        return self.ranked_indices[:n]

    def get_top_set_ids(self, n: Optional[int] = None) -> np.ndarray:
        """Get top N real set IDs (case numbers). Falls back to position+1
        only when case_numbers is unset (complete contiguous ensemble)."""
        idx = self.get_top_indices(n)
        if self.case_numbers is not None:
            return np.asarray(self.case_numbers)[idx]
        return idx + 1


# =============================================================================
# Core Optimization Functions
# =============================================================================

def optimize_ensemble(
    simulated: Dict[str, np.ndarray],
    targets: Dict[str, Target],
    config: Optional[OptimizationConfig] = None
) -> OptimizationResult:
    """
    Optimize ensemble by ranking parameter sets against targets.

    Parameters
    ----------
    simulated : dict
        {target_name: array of simulated values (n_sets,)}
    targets : dict
        {target_name: Target object with observed value and uncertainty}
    config : OptimizationConfig, optional
        Optimization settings

    Returns
    -------
    OptimizationResult
        Contains ranked indices, costs, and statistics

    Example
    -------
    >>> simulated = {
    ...     'leaf_pft7': sim_array_4170,
    ...     'froot_pft10': sim_array_4170,
    ... }
    >>> targets = {
    ...     'leaf_pft7': Target('leaf_pft7', observed=24.6, uncertainty=0.2),
    ...     'froot_pft10': Target('froot_pft10', observed=382.1, uncertainty=0.2),
    ... }
    >>> result = optimize_ensemble(simulated, targets)
    >>> print(f"Best set: #{result.best_set_id}, cost: {result.best_cost:.4f}")
    """
    config = config or OptimizationConfig()

    # Validate inputs
    target_names = list(targets.keys())
    n_sets = None
    for name in target_names:
        if name not in simulated:
            raise ValueError(f"Target '{name}' not in simulated data")
        if n_sets is None:
            n_sets = len(simulated[name])
        elif len(simulated[name]) != n_sets:
            raise ValueError(f"Inconsistent array lengths for '{name}'")

    if config.verbose:
        print(f"Optimizing {n_sets} parameter sets against {len(targets)} targets")
        print(f"  Error method: {config.error_method}")
        print(f"  Aggregation: {config.aggregation_method}")

    # Calculate individual errors for each target.
    # sim_values has shape (n_sets, n_points): one observation point for a snapshot
    # target, several for a time series. Each target may pick its own cost metric
    # (target.cost_method) and is scored SNAPSHOT (1 point) or TIME_SERIES (N points);
    # CostFunction.compute reduces the per-point obs/sim arrays to one error per set.
    individual_errors = {}
    for name, target in targets.items():
        sim_values = np.atleast_2d(np.asarray(simulated[name]))
        if sim_values.shape[0] == 1 and n_sets != 1:
            sim_values = sim_values.T  # tolerate a stored (n_sets,) 1-D array
        obs_vals = target.obs_values
        method = target.cost_method or config.error_method
        otype = ObservationType.SNAPSHOT if target.n_points == 1 else ObservationType.TIME_SERIES
        cost_fn = CostFunction(method=method, obs_type=otype)
        errors = np.zeros(n_sets)
        for i in range(n_sets):
            # to_cost flips skill scores (nse/kge/correlation; higher=better) into a
            # minimizable cost; error metrics pass through. Keeps ranking "lower=better".
            errors[i] = to_cost(cost_fn.compute(sim_values[i], obs_vals).value, method)
        individual_errors[name] = errors

    # Calculate composite cost for each set
    composite_cost = np.zeros(n_sets)
    weights = {name: targets[name].weight for name in target_names}

    for i in range(n_sets):
        errors_i = {name: individual_errors[name][i] for name in target_names}
        composite_cost[i] = aggregate_costs(
            errors_i,
            method=config.aggregation_method,
            weights=weights if config.aggregation_method == 'weighted_mean' else None
        )

    # Count satisfied targets for each set.
    # Snapshot: keep the exact relative/absolute within_tolerance check on the single
    # value (identical to legacy behavior). Time series: a point-wise tolerance is
    # ill-defined, so the target counts as satisfied when its computed error metric is
    # within tolerance (interpreted in that metric's units).
    n_satisfied = np.zeros(n_sets, dtype=int)
    for i in range(n_sets):
        for name, target in targets.items():
            if target.n_points == 1:
                sim_scalar = float(np.asarray(simulated[name][i]).ravel()[0])
                ok = within_tolerance(
                    sim_scalar, target.observed,
                    config.tolerance, config.tolerance_type
                )
            else:
                ok = individual_errors[name][i] <= config.tolerance
            if ok:
                n_satisfied[i] += 1

    # Rank by composite cost (lowest = best)
    ranked_indices = np.argsort(composite_cost)

    if config.verbose:
        print(f"\nResults:")
        print(f"  Best cost: {composite_cost[ranked_indices[0]]:.6f}")
        print(f"  Worst cost: {composite_cost[ranked_indices[-1]]:.6f}")
        print(f"  Sets with all targets satisfied: {np.sum(n_satisfied == len(targets))}")

    return OptimizationResult(
        ranked_indices=ranked_indices,
        composite_cost=composite_cost,
        individual_errors=individual_errors,
        n_satisfied=n_satisfied,
        config=config,
        targets=targets
    )


def save_optimization_results(
    result: OptimizationResult,
    simulated: Dict[str, np.ndarray],
    output_dir: Path,
    prefix: str = "optimization"
):
    """
    Save optimization results to files.

    Generates:
      - {prefix}_results.txt: Full ranked results
      - {prefix}_top{N}_indices.txt: Top N set IDs (1-based)
      - {prefix}_summary.txt: Summary statistics
      - {prefix}_statistics.png: Diagnostic plots
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    n_sets = result.n_sets
    n_targets = len(result.targets)
    target_names = list(result.targets.keys())

    # -------------------------------------------------------------------------
    # 1. Full results file
    # -------------------------------------------------------------------------
    results_file = output_dir / f"{prefix}_results.txt"
    with open(results_file, 'w') as f:
        f.write(f"# Optimization Results\n")
        f.write(f"# Method: {result.config.error_method} + {result.config.aggregation_method}\n")
        f.write(f"# Targets: {n_targets}\n")
        f.write(f"# Sets: {n_sets}\n")
        f.write(f"#\n")
        f.write(f"# Terminology:\n")
        f.write(f"#   RE = Relative Error = |sim - obs| / obs\n")
        f.write(f"#   Composite = RMSRE = sqrt(mean(RE^2))\n")
        f.write(f"#\n")

        # Header
        header = ["Rank", "Set_ID", "Composite", "N_satisfied"]
        for name in target_names:
            header.append(f"RE_{name}")
        for name in target_names:
            header.append(f"Sim_{name}")
        f.write("\t".join(header) + "\n")

        # Data rows
        for rank, idx in enumerate(result.ranked_indices, start=1):
            set_id = result._idx_to_set_id(idx)
            row = [
                str(rank),
                str(set_id),
                f"{result.composite_cost[idx]:.6f}",
                str(result.n_satisfied[idx])
            ]
            for name in target_names:
                row.append(f"{result.individual_errors[name][idx]:.6f}")
            for name in target_names:
                # simulated[name][idx] is a per-point array (length 1 for a snapshot).
                # Report the scalar for a snapshot; the point-mean for a time series.
                sim_pts = np.asarray(simulated[name][idx]).ravel()
                sim_repr = sim_pts[0] if sim_pts.size == 1 else float(np.nanmean(sim_pts))
                row.append(f"{sim_repr:.2f}")
            f.write("\t".join(row) + "\n")

    print(f"✓ Saved: {results_file}")

    # -------------------------------------------------------------------------
    # 2. Top N indices file
    # -------------------------------------------------------------------------
    n_top = result.config.n_top
    indices_file = output_dir / f"{prefix}_top{n_top}_indices.txt"
    top_ids = result.get_top_set_ids(n_top)

    with open(indices_file, 'w') as f:
        f.write(f"# Top {n_top} parameter set IDs (real case numbers)\n")
        f.write(f"# (mapped through case_numbers when the ensemble is partial;\n")
        f.write(f"#  position+1 only when case_numbers is unset / complete ensemble)\n")
        for set_id in top_ids:
            f.write(f"{int(set_id)}\n")

    print(f"✓ Saved: {indices_file}")

    # -------------------------------------------------------------------------
    # 3. Summary file
    # -------------------------------------------------------------------------
    summary_file = output_dir / f"{prefix}_summary.txt"
    with open(summary_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("OPTIMIZATION SUMMARY\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Configuration:\n")
        f.write(f"  Error method: {result.config.error_method}\n")
        f.write(f"  Aggregation: {result.config.aggregation_method}\n")
        f.write(f"  Tolerance: ±{result.config.tolerance*100:.0f}%\n")
        f.write(f"  Total sets: {n_sets}\n")
        f.write(f"  Targets: {n_targets}\n\n")

        # Best set
        best_idx = result.best_index
        f.write(f"Best Parameter Set: #{result.best_set_id}\n")
        f.write(f"  Composite cost: {result.best_cost:.6f}\n")
        f.write(f"  Targets satisfied: {result.n_satisfied[best_idx]}/{n_targets}\n\n")

        # Top N statistics
        top_indices = result.get_top_indices(n_top)
        top_costs = result.composite_cost[top_indices]
        top_satisfied = result.n_satisfied[top_indices]

        f.write(f"Top {n_top} Statistics:\n")
        f.write(f"  Cost range: {top_costs.min():.6f} - {top_costs.max():.6f}\n")
        f.write(f"  Mean cost: {top_costs.mean():.6f}\n")
        f.write(f"  Median cost: {np.median(top_costs):.6f}\n\n")

        f.write(f"Distribution of targets satisfied in top {n_top}:\n")
        for n in range(n_targets + 1):
            count = np.sum(top_satisfied == n)
            pct = count / n_top * 100
            f.write(f"  {n}/{n_targets}: {count:3d} sets ({pct:5.1f}%)\n")
        f.write("\n")

        # Targets
        f.write("=" * 80 + "\n")
        f.write("VALIDATION TARGETS\n")
        f.write("=" * 80 + "\n\n")

        for name, target in result.targets.items():
            f.write(f"{name}:\n")
            f.write(f"  Observed: {target.observed:.2f} {target.units}\n")
            f.write(f"  Range: {target.min_acceptable:.2f} - {target.max_acceptable:.2f}\n")
            f.write(f"  Weight: {target.weight}\n\n")

        # Top 10 detail
        f.write("=" * 80 + "\n")
        f.write("TOP 10 PARAMETER SETS\n")
        f.write("=" * 80 + "\n\n")

        for i in range(min(10, n_sets)):
            idx = result.ranked_indices[i]
            set_id = result._idx_to_set_id(idx)
            f.write(f"Rank {i+1}: Set #{set_id}\n")
            f.write(f"  Composite cost: {result.composite_cost[idx]:.6f}\n")
            f.write(f"  Targets satisfied: {result.n_satisfied[idx]}/{n_targets}\n\n")

            for name, target in result.targets.items():
                sim = simulated[name][idx]
                obs = target.observed
                err = result.individual_errors[name][idx]
                ok = "✓" if target.min_acceptable <= sim <= target.max_acceptable else "✗"
                f.write(f"    {name:25s}: RE={err:6.3f}, Sim={sim:8.2f}, Obs={obs:8.2f} {ok}\n")
            f.write("\n")

    print(f"✓ Saved: {summary_file}")

    # -------------------------------------------------------------------------
    # 4. Diagnostic plots
    # -------------------------------------------------------------------------
    if result.config.save_plots:
        plot_file = output_dir / f"{prefix}_statistics.png"
        _plot_optimization_statistics(result, plot_file)
        print(f"✓ Saved: {plot_file}")


def _plot_optimization_statistics(result: OptimizationResult, output_file: Path):
    """Create diagnostic plots for optimization results"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    n_sets = result.n_sets
    n_targets = len(result.targets)
    n_top = result.config.n_top

    # 1. Histogram of composite cost
    ax = axes[0, 0]
    ax.hist(result.composite_cost, bins=50, edgecolor='black', alpha=0.7)
    ax.axvline(result.best_cost, color='red', linestyle='--', lw=2,
               label=f'Best: {result.best_cost:.3f}')
    ax.axvline(result.composite_cost[result.ranked_indices[n_top-1]],
               color='orange', linestyle='--', lw=2,
               label=f'Rank {n_top}: {result.composite_cost[result.ranked_indices[n_top-1]]:.3f}')
    ax.set_xlabel('Composite Cost (RMSRE)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Frequency', fontsize=14)
    ax.set_title(f'Distribution of Composite Cost (All {n_sets} Sets)', fontsize=14, fontweight='bold')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)

    # 2. Targets satisfied distribution
    ax = axes[0, 1]
    bins = np.arange(-0.5, n_targets + 1.5, 1)
    counts, _ = np.histogram(result.n_satisfied, bins=bins)
    x_pos = np.arange(n_targets + 1)
    colors = plt.cm.RdYlGn(np.linspace(0, 1, n_targets + 1))
    bars = ax.bar(x_pos, counts, color=colors, edgecolor='black', alpha=0.8)

    ax.set_xlabel(f'Targets Satisfied (of {n_targets})', fontsize=14, fontweight='bold')
    ax.set_ylabel('Frequency', fontsize=14)
    ax.set_title(f'Target Satisfaction (All {n_sets} Sets)', fontsize=14, fontweight='bold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f'{i}/{n_targets}' for i in range(n_targets + 1)])
    ax.grid(True, alpha=0.3, axis='y')

    for i, count in enumerate(counts):
        pct = count / n_sets * 100
        ax.text(i, count + n_sets*0.01, f'{count}\n({pct:.1f}%)',
               ha='center', va='bottom', fontsize=10, fontweight='bold')

    # 3. Cost vs rank (top 500)
    ax = axes[1, 0]
    n_show = min(500, n_sets)
    top_indices = result.ranked_indices[:n_show]
    top_costs = result.composite_cost[top_indices]
    ax.plot(np.arange(1, n_show+1), top_costs, 'o-', markersize=3, alpha=0.7)
    ax.axhline(y=0.2, color='green', linestyle='--', lw=2, label='Cost = 0.2')
    ax.axhline(y=0.3, color='orange', linestyle='--', lw=2, label='Cost = 0.3')
    ax.axhline(y=0.5, color='red', linestyle='--', lw=2, label='Cost = 0.5')
    ax.set_xlabel('Rank', fontsize=14, fontweight='bold')
    ax.set_ylabel('Composite Cost (RMSRE)', fontsize=14)
    ax.set_title(f'Cost vs Rank (Top {n_show} Sets)', fontsize=14, fontweight='bold')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)

    # 4. Top N targets satisfied
    ax = axes[1, 1]
    top_satisfied = result.n_satisfied[result.ranked_indices[:n_top]]
    counts, _ = np.histogram(top_satisfied, bins=bins)
    bars = ax.bar(x_pos, counts, color=colors, edgecolor='black', alpha=0.8)

    ax.set_xlabel(f'Targets Satisfied (of {n_targets})', fontsize=14, fontweight='bold')
    ax.set_ylabel('Frequency', fontsize=14)
    ax.set_title(f'Target Satisfaction (Top {n_top} Sets)', fontsize=14, fontweight='bold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f'{i}/{n_targets}' for i in range(n_targets + 1)])
    ax.grid(True, alpha=0.3, axis='y')

    for i, count in enumerate(counts):
        if count > 0:
            pct = count / n_top * 100
            ax.text(i, count + 0.5, f'{count}\n({pct:.0f}%)',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)


# =============================================================================
# Kougarok-Specific Configuration (Example)
# =============================================================================

def load_kougarok_targets() -> Dict[str, Target]:
    """
    Load validation targets for Kougarok Arctic site.

    Returns 6 biomass targets: leaf + fineroot for 3 PFTs.
    """
    return {
        'PFT7_leaf': Target(
            name='PFT7_leaf',
            observed=24.6,
            uncertainty=0.2,
            units='g C/m²',
            description='Evergreen shrub leaf biomass'
        ),
        'PFT7_fineroot': Target(
            name='PFT7_fineroot',
            observed=174.2,
            uncertainty=0.2,
            units='g C/m²',
            description='Evergreen shrub fine root biomass'
        ),
        'PFT9_leaf': Target(
            name='PFT9_leaf',
            observed=124.7,
            uncertainty=0.2,
            units='g C/m²',
            description='Deciduous shrub leaf biomass'
        ),
        'PFT9_fineroot': Target(
            name='PFT9_fineroot',
            observed=187.3,
            uncertainty=0.2,
            units='g C/m²',
            description='Deciduous shrub fine root biomass'
        ),
        'PFT10_leaf': Target(
            name='PFT10_leaf',
            observed=82.7,
            uncertainty=0.2,
            units='g C/m²',
            description='Arctic graminoid leaf biomass'
        ),
        'PFT10_fineroot': Target(
            name='PFT10_fineroot',
            observed=382.1,
            uncertainty=0.2,
            units='g C/m²',
            description='Arctic graminoid fine root biomass'
        ),
    }


def load_kougarok_simulated(data_dir: Path) -> Dict[str, np.ndarray]:
    """
    Load simulated biomass from ensemble for Kougarok (SITE-SPECIFIC EXAMPLE).

    This function is specific to the Kougarok use case. For other sites,
    implement a similar loader or use the generic optimize_ensemble() API.

    Expects files (site-specific naming):
      - LeafBiomass_{site}_obsid.txt or similar
      - FineRootBiomass_{site}_obsid.txt or similar
    """
    # Site-specific file patterns - adjust for your use case
    leaf_file = data_dir / 'MorrisLeafBiomass_UpdatedModel_138param_obsid.txt'
    fineroot_file = data_dir / 'MorrisFineRootBiomass_UpdatedModel_138param_obsid.txt'

    leaf_data = np.loadtxt(leaf_file)      # (4170, 3)
    fineroot_data = np.loadtxt(fineroot_file)  # (4170, 3)

    # Column mapping: 0=PFT7, 1=PFT9, 2=PFT10
    pft_cols = {7: 0, 9: 1, 10: 2}

    simulated = {}
    for pft_num, col in pft_cols.items():
        simulated[f'PFT{pft_num}_leaf'] = leaf_data[:, col]
        simulated[f'PFT{pft_num}_fineroot'] = fineroot_data[:, col]

    return simulated


# =============================================================================
# Main (Kougarok Example)
# =============================================================================

def main():
    """Run optimization for Kougarok (example usage)"""
    print("\n" + "=" * 80)
    print("A2MC ENSEMBLE OPTIMIZATION")
    print("=" * 80)
    print("\nSite: Kougarok, Alaska")
    print("Targets: 6 biomass (leaf + fineroot × 3 PFTs)")
    print("Method: Relative Error (RE) + RMSRE aggregation")

    # Paths - Auto-detect HPC vs local
    try:
        from config import config as a2mc_config
        data_dir = Path(a2mc_config.LOCAL_DATA_DIR) / 'Program'
        output_dir = data_dir / 'OptimizationLeafRoot' / 'results'
    except ImportError:
        import os
        home = os.environ.get('HOME', '~')
        data_dir = Path(f'{home}/Desktop/Work/NGEE-Arctic/Kougarok/Program')
        output_dir = data_dir / 'OptimizationLeafRoot' / 'results'

    # Load data
    print("\n" + "-" * 40)
    print("Loading data...")
    targets = load_kougarok_targets()
    simulated = load_kougarok_simulated(data_dir)

    n_sets = len(list(simulated.values())[0])
    print(f"  Loaded {n_sets} parameter sets")
    print(f"  Loaded {len(targets)} targets")

    # Configure optimization
    config = OptimizationConfig(
        error_method='relative_error',  # RE = |sim - obs| / obs
        aggregation_method='rmsre',     # RMSRE = sqrt(mean(RE²))
        tolerance=0.2,
        n_top=50,
        output_dir=output_dir,
        save_plots=True,
        verbose=True
    )

    # Run optimization
    print("\n" + "-" * 40)
    print("Running optimization...")
    result = optimize_ensemble(simulated, targets, config)

    # Save results
    print("\n" + "-" * 40)
    print("Saving results...")
    save_optimization_results(result, simulated, output_dir, prefix='leafroot')

    # Summary
    print("\n" + "=" * 80)
    print("OPTIMIZATION COMPLETE")
    print("=" * 80)
    print(f"\nBest parameter set: #{result.best_set_id}")
    print(f"  Composite cost (RMSRE): {result.best_cost:.6f}")
    print(f"  Targets satisfied: {result.n_satisfied[result.best_index]}/{len(targets)}")

    top_ids = result.get_top_set_ids(10)
    print(f"\nTop 10 set IDs: {list(top_ids)}")

    print("\n" + "=" * 80 + "\n")


if __name__ == '__main__':
    main()
