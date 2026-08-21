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

from tools.fates_utils import (
    get_szpf_range, get_szpf_dim_length, get_n_size_classes,
    get_n_size_classes_from_config,
)
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
            (``{case}_all_variables_monthly_{y0}_{y1}.nc``; SZPF vars (time, n_szpf) or
            (n_szpf, time), where n_szpf = nlevsclass × n_pft, both read from the file, not assumed).
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
            # nlevsclass (size-class block width) and the SZPF total read from the file
            # itself — NOT hardcoded 13/156. Correct for any PFT/size-class configuration.
            n_sc = get_n_size_classes(ds) or get_n_size_classes_from_config()
            szpf_len = get_szpf_dim_length(ds)
            # Total PFT count = total / nlevsclass, for the get_szpf_range bound check.
            n_pft = szpf_len // n_sc if (szpf_len and n_sc) else None

            for tname, (nc_var, pft_id, factor) in target_specs.items():
                windows = windows_by_target.get(tname)
                if not windows:
                    logger.debug(f"No timestep window for target {tname}; skipping")
                    continue

                # Lazy-load each NC variable once, normalized to (n_szpf, n_times)
                if nc_var not in needed_vars:
                    if nc_var not in ds.variables:
                        logger.debug(f"Variable {nc_var} not in {nc_path.name}")
                        continue
                    # Resolve the SZPF length per-variable if the dataset-level probe
                    # failed (fall back to the axis divisible by n_sc).
                    slen = szpf_len or get_szpf_dim_length(ds, nc_var)
                    data = np.asarray(ds.variables[nc_var][:])
                    data = np.squeeze(data)
                    if data.ndim == 2:
                        if slen is not None:
                            if data.shape[1] == slen:
                                data = data.T
                            elif data.shape[0] != slen:
                                logger.warning(
                                    f"Unexpected shape for {nc_var}: {data.shape} "
                                    f"(expected an axis of length {slen})"
                                )
                                continue
                        else:
                            # No SZPF dim metadata: SZPF axis is the one divisible by
                            # nlevsclass (file/config-derived n_sc, not a hardcoded 13).
                            if data.shape[1] % n_sc == 0 and data.shape[0] % n_sc != 0:
                                data = data.T
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
                szpf_start, szpf_end = get_szpf_range(
                    pft_id, fates_pft=(n_pft or pft_id), n_size_classes=n_sc
                )
                point_vals = []
                for window in windows:
                    per_t = [float(np.nansum(data[szpf_start : szpf_end + 1, int(k)]))
                             for k in window]
                    point_vals.append(float(np.mean(per_t)) * factor)
                simulated[tname] = np.array(point_vals, dtype=float)

    except Exception as e:
        logger.error(f"Failed to read {nc_path}: {e}")

    return simulated


def classify_target_level(name: str) -> str:
    """Route a target key to its extraction level: 'pft' (PFT<id>_<var>, SZPF),
    'ecosystem' (ECO_<var>, site scalar), 'soil' (SOIL_<var>, depth profile), or
    'unknown'. Used by the dispatcher + the validator."""
    if re.match(r"PFT\d+_", name):
        return "pft"
    if name.startswith("ECO_"):
        return "ecosystem"
    if name.startswith("SOIL_"):
        return "soil"
    if name.startswith("SNOW_"):
        return "snow"
    return "unknown"


def extract_all_series(
    nc_file: Path,
    targets: Dict,
    windows_by_target: Dict[str, List[List[int]]],
) -> Dict[str, np.ndarray]:
    """Level-dispatched extraction: run each level's OWN extractor and merge the results.

    The per-PFT SZPF path (`extract_case_series`) is unchanged; the ecosystem site-scalar
    path lives in its own module (`tools/extract_ecosystem_series`); soil profiles will be
    a third module. Each extractor self-selects its own key family, so passing the full
    `targets` dict to each is safe. All feed the same generic scoring downstream.
    """
    out = extract_case_series(nc_file, targets, windows_by_target)  # PFT/SZPF (unchanged)
    try:
        from tools.extract_ecosystem_series import extract_ecosystem_series
        out.update(extract_ecosystem_series(nc_file, targets, windows_by_target))
    except Exception as e:
        logger.error(f"ecosystem-level extraction failed: {e}")
    try:
        from tools.extract_land_series import extract_land_series
        out.update(extract_land_series(nc_file, targets, windows_by_target))  # SNOW_/SOIL_
    except Exception as e:
        logger.error(f"land (snow/soil) extraction failed: {e}")
    return out


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
    series = extract_all_series(nc_file, targets, windows_by_target)
    return {name: float(arr[0]) for name, arr in series.items()}


def _tget(t, key, default=None):
    """Read ``key`` from a Target object (attr) or a plain dict, else ``default``."""
    if hasattr(t, key):
        return getattr(t, key, default)
    if isinstance(t, dict):
        return t.get(key, default)
    return default


def _obs_array(target) -> np.ndarray:
    """Observed values for a target as an array (length n_points; length-1 for a snapshot).

    Handles a ``Target`` object (``obs_values`` property), a plain dict with an
    ``observations`` list, or a scalar ``observed``.
    """
    ov = _tget(target, "obs_values", None)
    if ov is not None:
        return np.asarray(ov, dtype=float)
    obs_list = _tget(target, "observations", None)
    if obs_list:
        return np.asarray(
            [(p.value if hasattr(p, "value") else p.get("value")) for p in obs_list],
            dtype=float)
    return np.array([_tget(target, "observed", 0)], dtype=float)


def evaluate_case(
    nc_file: Path,
    targets: Dict,
    obs_idx: int,
    error_method: str = "relative_error",
    aggregation_method: str = "rmsre",
    tolerance: float = 0.2,
    year_start: Optional[int] = None,
) -> Dict:
    """
    Full evaluation: extract values, compute the cost, count satisfied targets.

    Handles **all target variants** — a snapshot (one value), a **time series** or several
    time snapshots (a target's ``observations`` list of N points), and several stocks (each a
    separate target). When ``year_start`` is given, each target's own per-point time windows
    are resolved (``resolve_obs_index_windows``) and multi-point targets are scored on ALL
    their points via ``extract_case_series`` + ``ObservationType.TIME_SERIES`` — the same path
    the ensemble screening (``optimize_function``/``screen_ensemble``) uses, so both agree.

    **Honors the cost configuration** — each target's own ``cost_method`` overrides
    ``error_method``; ``aggregation_method`` combines per-target costs (``weighted_mean`` uses
    each target's ``weight``); ``tolerance`` sets the "satisfied" threshold.

    Defaults (``year_start=None`` + the legacy metrics) reproduce the snapshot-only
    relative_error + rmsre + ±20% behavior byte-for-byte, so existing callers are unchanged.

    Args:
        nc_file: Path to extracted NetCDF.
        targets: Validation targets ``{name: Target}`` (Target objects or plain dicts). A
            target may carry ``cost_method``, ``weight``, and an ``observations`` list (series).
        obs_idx: 0-based observation timestep index (int, or a sequence to average) — the
            snapshot fallback window used for targets with no per-point spec.
        error_method: default cost metric for targets without their own ``cost_method``.
        aggregation_method: how per-target costs combine (``rmsre``/``mean``/``weighted_mean``/…).
        tolerance: relative tolerance for the "satisfied" count (default ±20%).
        year_start: first simulated year, needed to map a series target's (year, month) points
            to timestep indices. When None, every target is scored as a single-point snapshot.

    Returns:
        Dict with ``targets_met``, ``total_targets``, ``composite_cost``, ``cost_config``,
        ``individual_errors`` (per-target ranking cost), ``per_target``, ``satisfied``.
    """
    from tools.cost_functions import (
        CostFunction, ObservationType, aggregate_costs, to_cost,
    )

    idxs = ([int(obs_idx)] if isinstance(obs_idx, (int, np.integer))
            else [int(k) for k in obs_idx])

    # Per-target timestep windows + aligned observed arrays: a target's own per-point spec
    # (time series / several snapshots) when year_start is known, else a single snapshot window.
    windows_by_target: Dict[str, List[List[int]]] = {}
    obs_by_target: Dict[str, np.ndarray] = {}
    for tname, target in (targets or {}).items():
        w = resolve_obs_index_windows(target, year_start) if year_start is not None else None
        if w is not None:
            windows_by_target[tname] = w
            obs_by_target[tname] = _obs_array(target)
        else:
            windows_by_target[tname] = [idxs]
            obs_by_target[tname] = np.array([_tget(target, "observed", 0)], dtype=float)

    series = extract_all_series(nc_file, targets, windows_by_target)

    if not series:
        return {
            "targets_met": 0,
            "total_targets": len(targets),
            "composite_cost": float("inf"),
            "individual_errors": {},
            "per_target": {},
            "satisfied": {},
            "error": "No simulated values could be extracted",
        }

    individual_errors: Dict[str, float] = {}
    weights: Dict[str, float] = {}
    satisfied: Dict[str, bool] = {}
    per_target: Dict[str, Dict] = {}

    for tname, sim_arr in series.items():
        sim_arr = np.asarray(sim_arr, dtype=float)
        obs_arr = np.asarray(obs_by_target[tname], dtype=float)
        if sim_arr.shape != obs_arr.shape:
            logger.warning(f"{tname}: sim/obs point count mismatch "
                           f"({sim_arr.shape} vs {obs_arr.shape}); skipping")
            continue
        target = targets[tname]
        n_points = int(obs_arr.size)
        otype = (ObservationType.SNAPSHOT if n_points == 1
                 else ObservationType.TIME_SERIES)

        method = _tget(target, "cost_method", None) or error_method
        cost = to_cost(CostFunction(method, otype).compute(sim_arr, obs_arr).value, method)
        # DISPLAY relative error: exact for a snapshot, mean per-point RE for a series.
        rel_error = CostFunction("relative_error", otype).compute(sim_arr, obs_arr).value

        individual_errors[tname] = cost
        weights[tname] = float(_tget(target, "weight", 1.0) or 1.0)
        satisfied[tname] = bool(rel_error <= tolerance)
        per_target[tname] = {
            "simulated": (round(float(sim_arr[0]), 2) if n_points == 1
                          else [round(float(x), 2) for x in sim_arr]),
            "observed": (round(float(obs_arr[0]), 2) if n_points == 1
                         else [round(float(x), 2) for x in obs_arr]),
            "relative_error": round(float(rel_error), 4),  # scalar; always relative (display)
            "cost": round(float(cost), 4),                 # the configured-metric ranking cost
            "cost_method": method,
            "n_points": n_points,
            "obs_type": "snapshot" if n_points == 1 else "time_series",
            "bias": round(float(np.mean(sim_arr - obs_arr)), 2),
            "within_20pct": bool(rel_error <= 0.2),         # kept for backward compat
            "within_tolerance": bool(rel_error <= tolerance),
        }

    composite_cost = aggregate_costs(
        individual_errors,
        method=aggregation_method,
        weights=weights if aggregation_method == "weighted_mean" else None,
    )

    return {
        "targets_met": sum(satisfied.values()),
        "total_targets": len(series),
        "composite_cost": round(composite_cost, 4),
        "cost_config": {"error_method": error_method,
                        "aggregation_method": aggregation_method,
                        "tolerance": tolerance},
        "individual_errors": {k: round(v, 4) for k, v in individual_errors.items()},
        "per_target": per_target,
        "satisfied": satisfied,
        "simulated_values": {
            k: (round(float(v[0]), 2) if np.asarray(v).size == 1
                else [round(float(x), 2) for x in np.asarray(v)])
            for k, v in series.items()},
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
