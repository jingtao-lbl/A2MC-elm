#!/usr/bin/env python3
"""
Evaluate a Single Case Against Validation Targets

Shared utility for extracting simulated target values from an extracted
NetCDF file and computing error metrics against observations.

Used by:
    - phases/phase2_screening/screen_ensemble.py (bulk: 4890 cases)
    - phases/phase5_testing/monitor_experiments.py (single experiment case)
    - Any future script that needs to evaluate a case

The core function `extract_case_values()` handles:
    1. Opening the NC file
    2. For each target, determining the SZPF variable and PFT
    3. Reading SZPF data at the observation timestep
    4. Aggregating across size classes per PFT
    5. Applying unit conversion (validation_factor)

Author: Jing Tao with Claude
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from tools.fates_utils import get_szpf_range
from tools.fates_output_variables import resolve_target_name, get_variable_family

try:
    import netCDF4 as nc
    HAS_NETCDF = True
except ImportError:
    nc = None
    HAS_NETCDF = False

logger = logging.getLogger(__name__)


def resolve_obs_index_windows(target, year_start: int) -> Optional[List[List[int]]]:
    """
    Resolve a target's observation points to monthly timestep index-windows.

    Returns one window per observation point — a window is a list of 0-based monthly
    timestep indices whose simulated monthly means are averaged for that point. A
    snapshot target yields one window; a time-series target yields one per point.

    Returns None when the target carries no per-point spec (``target.observations``
    is None), so the caller falls back to a single externally-supplied window
    (``ScreeningConfig.obs_idxs``), preserving legacy snapshot behavior.

    idx(year, month) = (year - year_start) * 12 + (month - 1)
    """
    obs = getattr(target, "observations", None)
    if not obs:
        return None
    return [[(p.year - year_start) * 12 + (m - 1) for m in p.window] for p in obs]


def extract_case_series(
    nc_file: Path,
    targets: Dict,
    windows_by_target: Dict[str, List[List[int]]],
) -> Dict[str, np.ndarray]:
    """
    Extract per-observation-point simulated values for each target.

    This is the shared SZPF-reading core for both the snapshot and time-series
    comparison paths (see docs/24_Generic_Obs_Comparison_Plan.md).

    Args:
        nc_file: Path to the extracted NetCDF file
            (``{case}_all_variables_monthly_{y0}_{y1}.nc``; SZPF vars (time,156) or (156,time)).
        targets: Validation target dict; only the key *name* is used to resolve the
            variable / PFT (``Target`` object or plain dict both work).
        windows_by_target: ``{target name -> list of timestep-index windows}``. Each
            window is a list of 0-based monthly indices whose SZPF-summed values are
            **averaged** to produce that observation point's simulated value. A snapshot
            target has one window; a time-series target has one per point. Built by the
            caller (e.g. ``resolve_obs_index_windows`` for per-target specs, or a single
            fallback window for legacy snapshots).

    Returns:
        ``{target name -> np.ndarray of shape (n_points,)}`` in validation units.
        Targets whose variable is missing, or any of whose indices are out of range,
        are omitted (same skip semantics as before).
    """
    if not HAS_NETCDF:
        raise ImportError("netCDF4 is required.  Install with: pip install netCDF4")

    nc_path = Path(nc_file)
    if not nc_path.exists():
        logger.warning(f"NC file not found: {nc_path}")
        return {}

    target_specs = _parse_target_specs(targets)
    if not target_specs:
        return {}

    needed_vars: Dict[str, np.ndarray] = {}  # nc_var -> loaded (156, n_times) data
    simulated: Dict[str, np.ndarray] = {}

    try:
        with nc.Dataset(str(nc_path), "r") as ds:
            for tname, (nc_var, pft_id, factor) in target_specs.items():
                windows = windows_by_target.get(tname)
                if not windows:
                    logger.debug(f"No timestep window for target {tname}; skipping")
                    continue

                # Lazy-load each NC variable once, normalized to (156, n_times)
                if nc_var not in needed_vars:
                    if nc_var not in ds.variables:
                        logger.debug(f"Variable {nc_var} not in {nc_path.name}")
                        continue
                    data = np.asarray(ds.variables[nc_var][:])
                    data = np.squeeze(data)
                    if data.ndim == 2:
                        if data.shape[1] == 156:
                            data = data.T
                        elif data.shape[0] != 156:
                            logger.warning(
                                f"Unexpected shape for {nc_var}: {data.shape}"
                            )
                            continue
                    else:
                        logger.debug(
                            f"Skipping {nc_var}: expected 2D, got ndim={data.ndim}"
                        )
                        continue
                    needed_vars[nc_var] = data

                data = needed_vars.get(nc_var)
                if data is None:
                    continue

                # Validate every index across all of this target's windows.
                all_idxs = [int(k) for w in windows for k in w]
                if any(k < 0 or k >= data.shape[1] for k in all_idxs):
                    logger.warning(
                        f"obs index out of range for {nc_var} "
                        f"(n_times={data.shape[1]}, windows={windows})"
                    )
                    continue

                # One value per observation point: SZPF-sum per timestep, mean over
                # that point's window, then unit conversion.
                szpf_start, szpf_end = get_szpf_range(pft_id)
                point_vals = []
                for window in windows:
                    per_t = [float(np.nansum(data[szpf_start : szpf_end + 1, int(k)]))
                             for k in window]
                    point_vals.append(float(np.mean(per_t)) * factor)
                simulated[tname] = np.array(point_vals, dtype=float)

    except Exception as e:
        logger.error(f"Failed to read {nc_path}: {e}")

    return simulated


def extract_case_values(
    nc_file: Path,
    targets: Dict,
    obs_idx: int,
) -> Dict[str, float]:
    """
    Legacy scalar API: one simulated value per target at ``obs_idx``.

    ``obs_idx`` may be a single int OR a sequence of indices to AVERAGE (e.g.
    [July, August] means). Backward-compatible thin wrapper over
    :func:`extract_case_series` (single window per target). Returns
    ``{target name -> float}``; targets that could not be extracted are omitted.

    Used by single-case evaluation (Phase 5) and cross-round comparison; the bulk
    screening path uses :func:`extract_case_series` with per-target windows.
    """
    idxs = ([int(obs_idx)] if isinstance(obs_idx, (int, np.integer))
            else [int(k) for k in obs_idx])
    windows_by_target = {name: [idxs] for name in (targets or {})}
    series = extract_case_series(nc_file, targets, windows_by_target)
    return {name: float(arr[0]) for name, arr in series.items()}


def evaluate_case(
    nc_file: Path,
    targets: Dict,
    obs_idx: int,
) -> Dict:
    """
    Full evaluation: extract values, compute errors, count satisfied.

    Convenience wrapper around ``extract_case_values`` + cost functions.

    Args:
        nc_file: Path to extracted NetCDF.
        targets: Validation targets ``{name: Target}``.
        obs_idx: 0-based observation timestep index.

    Returns:
        Dict with ``targets_met``, ``total_targets``, ``composite_cost``,
        ``individual_errors``, ``per_target``, ``satisfied``.
    """
    from tools.cost_functions import (
        CostFunction, ObservationType, aggregate_costs,
        count_targets_satisfied,
    )

    simulated = extract_case_values(nc_file, targets, obs_idx)

    if not simulated:
        return {
            "targets_met": 0,
            "total_targets": len(targets),
            "composite_cost": float("inf"),
            "individual_errors": {},
            "per_target": {},
            "satisfied": {},
            "error": "No simulated values could be extracted",
        }

    # Build observed dict
    observed: Dict[str, float] = {}
    for tname in simulated:
        t = targets[tname]
        observed[tname] = t.observed if hasattr(t, "observed") else t.get("observed", 0)

    # Per-target relative errors
    cost_fn = CostFunction(method="relative_error", obs_type=ObservationType.SNAPSHOT)
    individual_errors: Dict[str, float] = {}
    per_target: Dict[str, Dict] = {}

    for tname in simulated:
        sim_val = simulated[tname]
        obs_val = observed[tname]
        rel_error = cost_fn.compute(sim_val, obs_val).value

        individual_errors[tname] = rel_error
        per_target[tname] = {
            "simulated": round(sim_val, 2),
            "observed": round(obs_val, 2),
            "relative_error": round(rel_error, 4),
            "bias": round(sim_val - obs_val, 2),
            "within_20pct": rel_error <= 0.2,
        }

    # Composite cost
    composite_cost = aggregate_costs(individual_errors, method="rmsre")

    # Count satisfied
    n_satisfied, n_total, satisfied_dict = count_targets_satisfied(
        simulated, observed, tolerance=0.2
    )

    return {
        "targets_met": n_satisfied,
        "total_targets": n_total,
        "composite_cost": round(composite_cost, 4),
        "individual_errors": {k: round(v, 4) for k, v in individual_errors.items()},
        "per_target": per_target,
        "satisfied": satisfied_dict,
        "simulated_values": {k: round(v, 2) for k, v in simulated.items()},
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_target_specs(
    targets: Dict,
) -> Dict[str, Tuple[str, int, float]]:
    """
    Parse target names into ``(nc_var, pft_id, validation_factor)`` triples.

    Supports target names like ``"PFT7_leaf"``, ``"PFT10_fineroot"``, etc.

    Returns:
        ``{target_name: (nc_var, pft_id, factor)}``
    """
    specs: Dict[str, Tuple[str, int, float]] = {}

    for tname in targets:
        match = re.match(r"PFT(\d+)_(\w+)", tname)
        if not match:
            logger.debug(f"Could not parse target name: {tname}")
            continue

        pft_id = int(match.group(1))
        var_type = match.group(2).lower()

        # Resolve through the variable-family registry
        canonical = resolve_target_name(var_type)
        try:
            family = get_variable_family(canonical)
        except KeyError:
            logger.debug(f"Unknown variable type '{var_type}' in target {tname}")
            continue

        nc_var = family.szpf_var or family.pft_var
        if not nc_var:
            logger.debug(f"No SZPF/PFT variable for {canonical} (target {tname})")
            continue

        factor = family.validation_factor
        specs[tname] = (nc_var, pft_id, factor)

    return specs


def find_extracted_nc(
    case_name: str,
    search_dirs: List[Path],
) -> Optional[Path]:
    """
    Locate the extracted NC file for a case across multiple directories.

    Tries progressively looser glob patterns until a match is found.

    Args:
        case_name: Case name string (e.g., ``"Kougarok_ELM-FATES_PtCNPEn322_TRANS"``).
        search_dirs: Ordered list of directories to search.

    Returns:
        Path to the first matching NC file, or ``None``.
    """
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        # Exact match
        matches = list(search_dir.glob(f"{case_name}_all_variables_monthly_*.nc"))
        if matches:
            return matches[0]

        # Substring match
        matches = list(search_dir.glob(f"*{case_name}*_all_variables_monthly_*.nc"))
        if matches:
            return matches[0]

        # Subdirectory match
        for subdir in [search_dir / case_name, search_dir / "extracted"]:
            if subdir.exists():
                matches = list(subdir.glob("*_all_variables_monthly_*.nc"))
                if matches:
                    return matches[0]

    return None
