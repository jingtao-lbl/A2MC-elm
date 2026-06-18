#!/usr/bin/env python3
"""
Cost Functions for A2MC Calibration

This module provides a library of error metrics and cost functions for comparing
simulated outputs against observations. Supports different observation types:
  - Snapshot: Single-point comparison (e.g., peak-season biomass)
  - Time series: Multi-point temporal comparison (e.g., monthly LAI)
  - Profile: Vertically resolved comparison (e.g., soil temperature by depth)

Terminology (correct usage):
  - RE (Relative Error): |sim - obs| / obs (single point)
  - RMSE: sqrt(mean((sim - obs)²)) (time series / profile)
  - NRMSE: RMSE / normalization_factor (normalized RMSE)
  - RMSRE: sqrt(mean(RE²)) (Root Mean Square Relative Error, for combining REs)
  - MAE: mean(|sim - obs|) (Mean Absolute Error)
  - Bias: mean(sim - obs) (signed error)
  - NSE: Nash-Sutcliffe Efficiency (1 = perfect, 0 = mean predictor, <0 = worse)
  - KGE: Kling-Gupta Efficiency (1 = perfect)

Usage:
    from tools.cost_functions import CostFunction, ObservationType, aggregate_costs

    # For snapshot observations (single value per target)
    cost_fn = CostFunction(method='relative_error')
    error = cost_fn.compute(simulated=150.0, observed=174.2)

    # For time series observations
    cost_fn = CostFunction(method='rmse', obs_type=ObservationType.TIME_SERIES)
    error = cost_fn.compute(simulated=sim_array, observed=obs_array)

    # Aggregate multiple target errors into single cost
    total_cost = aggregate_costs(errors, method='rmsre')

Author: Jing Tao
Created: January 2026
"""

import numpy as np
from enum import Enum
from typing import Union, List, Dict, Optional, Callable
from dataclasses import dataclass, field


class ObservationType(Enum):
    """Type of observation data structure"""
    SNAPSHOT = "snapshot"           # Single value (e.g., peak biomass)
    TIME_SERIES = "time_series"     # Temporal sequence (e.g., monthly GPP)
    PROFILE = "profile"             # Vertical profile (e.g., soil T by depth)
    PROFILE_TIME_SERIES = "profile_time_series"  # Profile over time


class SpatialLevel(Enum):
    """Spatial aggregation level of the data"""
    GRIDCELL = "gridcell"   # Site-level aggregate (1D)
    PFT = "pft"             # By plant functional type (2D)
    SZPF = "szpf"           # Size class × PFT (2D)
    SOIL_LAYER = "soil"     # By soil layer (2D)


class NormalizationMethod(Enum):
    """Normalization method for NRMSE"""
    MEAN = "mean"           # Divide by mean of observations
    RANGE = "range"         # Divide by (max - min) of observations
    STD = "std"             # Divide by standard deviation
    OBSERVED = "observed"   # Divide by observed value (for single point)


@dataclass
class ErrorMetric:
    """Container for error computation result"""
    value: float
    method: str
    obs_type: ObservationType
    n_points: int = 1
    details: Dict = field(default_factory=dict)


# =============================================================================
# Metric registries (single source of truth; consumed by CostFunction,
# aggregate_costs, to_cost, and tools/validate_targets_config.py)
# =============================================================================
# Per-target error metrics accepted by CostFunction.
VALID_ERROR_METHODS = (
    'relative_error', 'rmse', 'nrmse', 'mae', 'bias',
    'relative_bias', 'nse', 'kge', 'correlation',
)
# Across-target composite aggregation methods accepted by aggregate_costs.
VALID_AGGREGATION_METHODS = ('rmsre', 'rms', 'mean', 'weighted_mean', 'max', 'sum')
# Skill scores are "higher = better" (1.0 = perfect); to_cost flips them to a cost.
# They are also undefined/degenerate on a single point (need >= 2).
SKILL_SCORE_METHODS = ('nse', 'kge', 'correlation')
# Relative metrics divide by the observed value (sensitive to observed ~ 0); absolute
# metrics carry the data's units (mixing the two under rmsre/mean lets one target dominate).
RELATIVE_METHODS = ('relative_error', 'relative_bias')
ABSOLUTE_METHODS = ('rmse', 'nrmse', 'mae', 'bias')


class CostFunction:
    """
    Flexible cost function for model-observation comparison.

    Supports multiple error metrics and observation types.

    Parameters
    ----------
    method : str
        Error metric to use. Options:
        - 'relative_error' or 're': |sim - obs| / obs (for snapshots)
        - 'rmse': Root Mean Square Error (for time series/profiles)
        - 'nrmse': Normalized RMSE
        - 'mae': Mean Absolute Error
        - 'bias': Mean signed error (sim - obs)
        - 'relative_bias': (sim - obs) / obs
        - 'nse': Nash-Sutcliffe Efficiency
        - 'kge': Kling-Gupta Efficiency
        - 'correlation': Pearson correlation coefficient

    obs_type : ObservationType
        Type of observation data. Default: SNAPSHOT (Single value)

    normalization : NormalizationMethod
        How to normalize NRMSE. Default: MEAN

    weights : array-like, optional
        Weights for each point (time step or depth layer)
    """

    # Method aliases for convenience
    METHOD_ALIASES = {
        're': 'relative_error',
        'nre': 'relative_error',
        'normalized_error': 'relative_error',
    }

    def __init__(
        self,
        method: str = 'relative_error',
        obs_type: ObservationType = ObservationType.SNAPSHOT,
        normalization: NormalizationMethod = NormalizationMethod.MEAN,
        weights: Optional[np.ndarray] = None
    ):
        # Resolve aliases
        method = self.METHOD_ALIASES.get(method.lower(), method.lower())

        self.method = method
        self.obs_type = obs_type
        self.normalization = normalization
        self.weights = weights

        # Validate method
        if method not in VALID_ERROR_METHODS:
            raise ValueError(f"Unknown method '{method}'. Valid: {VALID_ERROR_METHODS}")

    def compute(
        self,
        simulated: Union[float, np.ndarray],
        observed: Union[float, np.ndarray],
        uncertainty: Optional[Union[float, np.ndarray]] = None
    ) -> ErrorMetric:
        """
        Compute error metric between simulated and observed values.

        Parameters
        ----------
        simulated : float or array
            Simulated value(s)
        observed : float or array
            Observed value(s)
        uncertainty : float or array, optional
            Observation uncertainty (for weighting)

        Returns
        -------
        ErrorMetric
            Container with error value, method info, and details
        """
        # Convert to numpy arrays
        sim = np.atleast_1d(np.asarray(simulated, dtype=float))
        obs = np.atleast_1d(np.asarray(observed, dtype=float))

        # Validate shapes
        if sim.shape != obs.shape:
            raise ValueError(f"Shape mismatch: sim {sim.shape} vs obs {obs.shape}")

        n_points = sim.size

        # Compute the selected metric
        if self.method == 'relative_error':
            value = self._relative_error(sim, obs)
        elif self.method == 'rmse':
            value = self._rmse(sim, obs)
        elif self.method == 'nrmse':
            value = self._nrmse(sim, obs)
        elif self.method == 'mae':
            value = self._mae(sim, obs)
        elif self.method == 'bias':
            value = self._bias(sim, obs)
        elif self.method == 'relative_bias':
            value = self._relative_bias(sim, obs)
        elif self.method == 'nse':
            value = self._nse(sim, obs)
        elif self.method == 'kge':
            value = self._kge(sim, obs)
        elif self.method == 'correlation':
            value = self._correlation(sim, obs)
        else:
            raise ValueError(f"Method '{self.method}' not implemented")

        # Build details
        details = {
            'simulated_mean': float(np.mean(sim)),
            'observed_mean': float(np.mean(obs)),
        }
        if n_points > 1:
            details['simulated_std'] = float(np.std(sim))
            details['observed_std'] = float(np.std(obs))

        return ErrorMetric(
            value=float(value),
            method=self.method,
            obs_type=self.obs_type,
            n_points=n_points,
            details=details
        )

    def _relative_error(self, sim: np.ndarray, obs: np.ndarray) -> float:
        """
        Relative Error: |sim - obs| / obs

        For single point (snapshot), returns scalar.
        For multiple points, returns mean relative error.
        """
        if np.any(obs == 0):
            raise ValueError("Cannot compute relative error when observed = 0")

        re = np.abs(sim - obs) / np.abs(obs)

        if self.weights is not None:
            return float(np.average(re, weights=self.weights))
        return float(np.mean(re))

    def _rmse(self, sim: np.ndarray, obs: np.ndarray) -> float:
        """
        Root Mean Square Error: sqrt(mean((sim - obs)²))
        """
        squared_errors = (sim - obs) ** 2

        if self.weights is not None:
            mse = np.average(squared_errors, weights=self.weights)
        else:
            mse = np.mean(squared_errors)

        return float(np.sqrt(mse))

    def _nrmse(self, sim: np.ndarray, obs: np.ndarray) -> float:
        """
        Normalized RMSE: RMSE / normalization_factor
        """
        rmse = self._rmse(sim, obs)

        if self.normalization == NormalizationMethod.MEAN:
            norm = np.mean(obs)
        elif self.normalization == NormalizationMethod.RANGE:
            norm = np.max(obs) - np.min(obs)
            if norm == 0:
                norm = np.mean(obs)  # Fallback if constant
        elif self.normalization == NormalizationMethod.STD:
            norm = np.std(obs)
            if norm == 0:
                norm = np.mean(obs)  # Fallback if constant
        elif self.normalization == NormalizationMethod.OBSERVED:
            norm = np.mean(obs)
        else:
            norm = np.mean(obs)

        if norm == 0:
            raise ValueError("Cannot normalize: normalization factor is 0")

        return float(rmse / norm)

    def _mae(self, sim: np.ndarray, obs: np.ndarray) -> float:
        """
        Mean Absolute Error: mean(|sim - obs|)
        """
        ae = np.abs(sim - obs)

        if self.weights is not None:
            return float(np.average(ae, weights=self.weights))
        return float(np.mean(ae))

    def _bias(self, sim: np.ndarray, obs: np.ndarray) -> float:
        """
        Bias (signed): mean(sim - obs)

        Positive = overestimation, Negative = underestimation
        """
        diff = sim - obs

        if self.weights is not None:
            return float(np.average(diff, weights=self.weights))
        return float(np.mean(diff))

    def _relative_bias(self, sim: np.ndarray, obs: np.ndarray) -> float:
        """
        Relative Bias: (sim - obs) / obs

        For multiple points, returns mean relative bias.
        """
        if np.any(obs == 0):
            raise ValueError("Cannot compute relative bias when observed = 0")

        rb = (sim - obs) / obs

        if self.weights is not None:
            return float(np.average(rb, weights=self.weights))
        return float(np.mean(rb))

    def _nse(self, sim: np.ndarray, obs: np.ndarray) -> float:
        """
        Nash-Sutcliffe Efficiency

        NSE = 1 - sum((sim - obs)²) / sum((obs - obs_mean)²)

        Returns:
            1.0 = perfect match
            0.0 = model is as good as using the mean
            <0  = model is worse than using the mean
        """
        obs_mean = np.mean(obs)
        ss_res = np.sum((sim - obs) ** 2)
        ss_tot = np.sum((obs - obs_mean) ** 2)

        if ss_tot == 0:
            # Constant observation - NSE undefined
            return 1.0 if ss_res == 0 else -np.inf

        return float(1.0 - ss_res / ss_tot)

    def _kge(self, sim: np.ndarray, obs: np.ndarray) -> float:
        """
        Kling-Gupta Efficiency

        KGE = 1 - sqrt((r-1)² + (α-1)² + (β-1)²)

        Where:
            r = correlation coefficient
            α = std(sim) / std(obs)  (variability ratio)
            β = mean(sim) / mean(obs)  (bias ratio)

        Returns:
            1.0 = perfect match
            <1  = worse performance
        """
        # Correlation
        if np.std(obs) == 0 or np.std(sim) == 0:
            r = 0.0
        else:
            r = np.corrcoef(sim, obs)[0, 1]

        # Variability ratio
        if np.std(obs) == 0:
            alpha = 1.0 if np.std(sim) == 0 else np.inf
        else:
            alpha = np.std(sim) / np.std(obs)

        # Bias ratio
        if np.mean(obs) == 0:
            beta = 1.0 if np.mean(sim) == 0 else np.inf
        else:
            beta = np.mean(sim) / np.mean(obs)

        kge = 1.0 - np.sqrt((r - 1)**2 + (alpha - 1)**2 + (beta - 1)**2)

        return float(kge)

    def _correlation(self, sim: np.ndarray, obs: np.ndarray) -> float:
        """
        Pearson correlation coefficient

        Returns value in [-1, 1], where 1 = perfect positive correlation
        """
        if np.std(obs) == 0 or np.std(sim) == 0:
            return 0.0

        return float(np.corrcoef(sim, obs)[0, 1])


def to_cost(value: float, method: str) -> float:
    """
    Convert a raw metric value to a minimizable COST (lower = better, ~0 = perfect).

    Error metrics are already costs and pass through unchanged. Skill scores
    (nse, kge, correlation) are mapped to ``1 - value`` so a perfect score (1.0)
    becomes cost 0 and worse scores become larger costs — directly comparable with,
    and aggregatable alongside, error-metric costs.
    """
    if method in SKILL_SCORE_METHODS:
        return 1.0 - value
    return value


def aggregate_costs(
    errors: Union[List[float], List[ErrorMetric], Dict[str, float]],
    method: str = 'rmsre',
    weights: Optional[Union[List[float], Dict[str, float]]] = None
) -> float:
    """
    Aggregate multiple error values into a single cost.

    Parameters
    ----------
    errors : list or dict
        Individual error values for each target.
        Can be list of floats, list of ErrorMetric, or dict {target: error}

    method : str
        Aggregation method:
        - 'rmsre': Root Mean Square (Relative) Error = sqrt(mean(e²))
        - 'mean': Simple mean
        - 'weighted_mean': Weighted mean (requires weights)
        - 'max': Maximum error (worst case)
        - 'sum': Sum of errors

    weights : list or dict, optional
        Weights for each error. Must match structure of errors.

    Returns
    -------
    float
        Aggregated cost value

    Examples
    --------
    >>> errors = [0.1, 0.2, 0.15, 0.3, 0.1, 0.25]  # 6 targets
    >>> aggregate_costs(errors, method='rmsre')
    0.195  # sqrt(mean([0.01, 0.04, 0.0225, 0.09, 0.01, 0.0625]))

    >>> errors = {'leaf_pft7': 0.1, 'leaf_pft9': 0.2, 'froot_pft10': 0.3}
    >>> weights = {'leaf_pft7': 1.0, 'leaf_pft9': 1.0, 'froot_pft10': 2.0}
    >>> aggregate_costs(errors, method='weighted_mean', weights=weights)
    """
    # Extract values from different input formats
    if isinstance(errors, dict):
        keys = list(errors.keys())
        values = np.array([errors[k] for k in keys])
        if weights is not None and isinstance(weights, dict):
            w = np.array([weights.get(k, 1.0) for k in keys])
        else:
            w = weights
    elif isinstance(errors, list) and len(errors) > 0 and isinstance(errors[0], ErrorMetric):
        values = np.array([e.value for e in errors])
        w = weights
    else:
        values = np.array(errors)
        w = weights

    if w is not None:
        w = np.array(w)
        if len(w) != len(values):
            raise ValueError(f"Weights length {len(w)} != errors length {len(values)}")

    # Compute aggregation
    method = method.lower()

    if method == 'rmsre' or method == 'rms':
        # Root Mean Square (of errors, which may already be relative)
        if w is not None:
            return float(np.sqrt(np.average(values**2, weights=w)))
        return float(np.sqrt(np.mean(values**2)))

    elif method == 'mean':
        if w is not None:
            return float(np.average(values, weights=w))
        return float(np.mean(values))

    elif method == 'weighted_mean':
        if w is None:
            raise ValueError("weighted_mean requires weights")
        return float(np.average(values, weights=w))

    elif method == 'max':
        return float(np.max(values))

    elif method == 'sum':
        if w is not None:
            return float(np.sum(values * w))
        return float(np.sum(values))

    else:
        raise ValueError(f"Unknown aggregation method: {method}")


def within_tolerance(
    simulated: float,
    observed: float,
    tolerance: float = 0.2,
    tolerance_type: str = 'relative'
) -> bool:
    """
    Check if simulated value is within tolerance of observed.

    Parameters
    ----------
    simulated : float
        Simulated value
    observed : float
        Observed value
    tolerance : float
        Tolerance threshold. Default 0.2 (20%)
    tolerance_type : str
        'relative': |sim - obs| / obs <= tolerance
        'absolute': |sim - obs| <= tolerance

    Returns
    -------
    bool
        True if within tolerance
    """
    if tolerance_type == 'relative':
        if observed == 0:
            return simulated == 0
        return abs(simulated - observed) / abs(observed) <= tolerance
    elif tolerance_type == 'absolute':
        return abs(simulated - observed) <= tolerance
    else:
        raise ValueError(f"Unknown tolerance_type: {tolerance_type}")


def count_targets_satisfied(
    simulated: Dict[str, float],
    observed: Dict[str, float],
    tolerance: float = 0.2,
    tolerance_type: str = 'relative'
) -> tuple:
    """
    Count how many targets are within tolerance.

    Parameters
    ----------
    simulated : dict
        {target_name: simulated_value}
    observed : dict
        {target_name: observed_value}
    tolerance : float
        Tolerance threshold (default 0.2 = 20%)
    tolerance_type : str
        'relative' or 'absolute'

    Returns
    -------
    n_satisfied : int
        Number of targets within tolerance
    n_total : int
        Total number of targets
    satisfied : dict
        {target_name: bool} for each target
    """
    satisfied = {}
    for name in observed.keys():
        if name in simulated:
            satisfied[name] = within_tolerance(
                simulated[name], observed[name], tolerance, tolerance_type
            )
        else:
            satisfied[name] = False

    n_satisfied = sum(satisfied.values())
    n_total = len(observed)

    return n_satisfied, n_total, satisfied


# =============================================================================
# Convenience functions for common use cases
# =============================================================================

def compute_snapshot_cost(
    simulated: Dict[str, float],
    observed: Dict[str, float],
    method: str = 'relative_error',
    aggregation: str = 'rmsre'
) -> tuple:
    """
    Compute cost for snapshot (single-point) observations.

    This is the most common use case: comparing peak-season biomass,
    annual totals, or other single-value targets.

    Parameters
    ----------
    simulated : dict
        {target_name: simulated_value}
    observed : dict
        {target_name: observed_value}
    method : str
        Error metric per target. Default 'relative_error'
    aggregation : str
        How to combine errors. Default 'rmsre'

    Returns
    -------
    total_cost : float
        Aggregated cost
    individual_errors : dict
        {target_name: error_value}

    Example
    -------
    >>> sim = {'leaf_pft7': 30.0, 'leaf_pft9': 100.0, 'froot_pft10': 300.0}
    >>> obs = {'leaf_pft7': 24.6, 'leaf_pft9': 124.7, 'froot_pft10': 382.1}
    >>> cost, errors = compute_snapshot_cost(sim, obs)
    >>> print(f"Total cost: {cost:.3f}")
    >>> print(f"Individual errors: {errors}")
    """
    cost_fn = CostFunction(method=method, obs_type=ObservationType.SNAPSHOT)

    individual_errors = {}
    for name, obs_val in observed.items():
        if name in simulated:
            result = cost_fn.compute(simulated[name], obs_val)
            individual_errors[name] = result.value

    total_cost = aggregate_costs(individual_errors, method=aggregation)

    return total_cost, individual_errors


def compute_timeseries_cost(
    simulated: Dict[str, np.ndarray],
    observed: Dict[str, np.ndarray],
    method: str = 'nrmse',
    aggregation: str = 'mean'
) -> tuple:
    """
    Compute cost for time series observations.

    Parameters
    ----------
    simulated : dict
        {target_name: simulated_array}
    observed : dict
        {target_name: observed_array}
    method : str
        Error metric per target. Default 'nrmse'
    aggregation : str
        How to combine errors. Default 'mean'

    Returns
    -------
    total_cost : float
        Aggregated cost
    individual_errors : dict
        {target_name: error_value}
    """
    cost_fn = CostFunction(method=method, obs_type=ObservationType.TIME_SERIES)

    individual_errors = {}
    for name, obs_arr in observed.items():
        if name in simulated:
            result = cost_fn.compute(simulated[name], obs_arr)
            individual_errors[name] = result.value

    total_cost = aggregate_costs(individual_errors, method=aggregation)

    return total_cost, individual_errors


def compute_profile_cost(
    simulated: np.ndarray,
    observed: np.ndarray,
    depths: Optional[np.ndarray] = None,
    method: str = 'rmse',
    depth_weights: str = 'uniform'
) -> float:
    """
    Compute cost for vertically-resolved profile observations.

    Useful for soil temperature profiles, soil moisture by layer, etc.

    Parameters
    ----------
    simulated : array
        Simulated values by depth (n_layers,) or (n_layers, n_times)
    observed : array
        Observed values by depth
    depths : array, optional
        Depth of each layer (for depth-weighting)
    method : str
        Error metric. Default 'rmse'
    depth_weights : str
        'uniform': Equal weight per layer
        'thickness': Weight by layer thickness
        'exponential': Exponentially decreasing with depth

    Returns
    -------
    float
        Profile-integrated error
    """
    sim = np.atleast_1d(simulated)
    obs = np.atleast_1d(observed)

    # Compute weights
    n_layers = len(obs)
    if depth_weights == 'uniform' or depths is None:
        weights = None
    elif depth_weights == 'thickness':
        # Weight by layer thickness (difference between depths)
        if len(depths) != n_layers:
            raise ValueError("depths must match number of layers")
        # Assume depths are layer centers, compute thickness
        thickness = np.diff(depths, prepend=0)
        weights = thickness / np.sum(thickness)
    elif depth_weights == 'exponential':
        # Exponentially decreasing weights with depth
        if depths is None:
            layer_idx = np.arange(n_layers)
        else:
            layer_idx = depths
        weights = np.exp(-layer_idx / np.max(layer_idx))
        weights = weights / np.sum(weights)
    else:
        weights = None

    cost_fn = CostFunction(
        method=method,
        obs_type=ObservationType.PROFILE,
        weights=weights
    )

    result = cost_fn.compute(sim, obs)
    return result.value


# =============================================================================
# Summary of available functions (for reference)
# =============================================================================

AVAILABLE_METHODS = """
Error Metrics (per-target):
  - relative_error (re): |sim - obs| / obs  [best for snapshots]
  - rmse: sqrt(mean((sim - obs)²))  [best for time series]
  - nrmse: RMSE / mean(obs)  [normalized, good for comparing across targets]
  - mae: mean(|sim - obs|)  [less sensitive to outliers than RMSE]
  - bias: mean(sim - obs)  [signed, shows over/underestimation]
  - relative_bias: mean((sim - obs) / obs)  [signed relative error]
  - nse: Nash-Sutcliffe Efficiency  [1=perfect, 0=mean, <0=bad]
  - kge: Kling-Gupta Efficiency  [1=perfect, considers correlation+variability+bias]
  - correlation: Pearson r  [pattern matching only, ignores magnitude]

Aggregation Methods (combining multiple targets):
  - rmsre: sqrt(mean(error²))  [standard for multi-objective]
  - mean: simple average
  - weighted_mean: weighted average
  - max: worst-case error
  - sum: total error

Observation Types:
  - SNAPSHOT: Single value (e.g., peak biomass, annual GPP)
  - TIME_SERIES: Temporal sequence (e.g., monthly LAI, daily GPP)
  - PROFILE: Vertical profile (e.g., soil T by layer, root biomass by depth)
  - PROFILE_TIME_SERIES: Profile evolving over time

Spatial Levels:
  - GRIDCELL: Site-level (e.g., total GPP)
  - PFT: By plant functional type (e.g., leaf biomass per PFT)
  - SZPF: Size class × PFT (e.g., P uptake by size and PFT)
  - SOIL_LAYER: By soil layer (e.g., soil moisture by depth)
"""


if __name__ == '__main__':
    # Quick test / demonstration
    print("A2MC Cost Functions Module")
    print("=" * 60)
    print(AVAILABLE_METHODS)

    # Example: Snapshot comparison
    print("\nExample: Snapshot biomass comparison")
    print("-" * 40)

    simulated = {
        'leaf_pft7': 30.0,
        'leaf_pft9': 100.0,
        'leaf_pft10': 70.0,
        'froot_pft7': 150.0,
        'froot_pft9': 200.0,
        'froot_pft10': 300.0,
    }

    observed = {
        'leaf_pft7': 24.6,
        'leaf_pft9': 124.7,
        'leaf_pft10': 82.7,
        'froot_pft7': 174.2,
        'froot_pft9': 187.3,
        'froot_pft10': 382.1,
    }

    cost, errors = compute_snapshot_cost(simulated, observed)
    print(f"Total cost (RMSRE): {cost:.4f}")
    print("\nIndividual relative errors:")
    for name, err in errors.items():
        print(f"  {name}: {err:.4f}")

    # Check tolerance
    n_sat, n_tot, satisfied = count_targets_satisfied(simulated, observed, tolerance=0.2)
    print(f"\nTargets within ±20%: {n_sat}/{n_tot}")
    for name, ok in satisfied.items():
        print(f"  {name}: {'✓' if ok else '✗'}")
