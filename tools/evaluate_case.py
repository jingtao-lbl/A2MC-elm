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


def extract_case_values(
    nc_file: Path,
    targets: Dict,
    obs_idx: int,
) -> Dict[str, float]:
    """
    Extract simulated values for each target from a single extracted NC file.

    This is the shared core: read SZPF data, aggregate by PFT, apply unit
    conversion.  Both bulk-screening and single-experiment evaluation call
    this so the logic is never duplicated.

    Args:
        nc_file: Path to the extracted NetCDF file.
            Expected format: ``{case}_all_variables_monthly_{y0}_{y1}.nc``
            with SZPF variables of shape ``(time, 156)`` or ``(156, time)``.
        targets: Validation target dict.
            Keys are target names like ``"PFT7_leaf"`` or ``"PFT10_fineroot"``.
            Values can be:
              - ``Target`` objects (with ``.observed`` attribute)
              - plain dicts (with ``"observed"`` key)
              - any object (only the *key name* is used to determine the
                variable / PFT; the observed value is not needed here)
        obs_idx: 0-based index of the observation timestep in the monthly
            time dimension. May also be a sequence of indices, in which case the
            per-PFT value is the MEAN across those timesteps (e.g. [July, August]
            means to match a late-July point sample against monthly-mean output).

    Returns:
        Dict mapping target name → simulated value (in validation units,
        e.g., g C m⁻²).  Targets that could not be extracted are omitted.
    """
    if not HAS_NETCDF:
        raise ImportError("netCDF4 is required.  Install with: pip install netCDF4")

    nc_path = Path(nc_file)
    if not nc_path.exists():
        logger.warning(f"NC file not found: {nc_path}")
        return {}

    # --- Determine which SZPF variables we need for the given targets ---
    target_specs = _parse_target_specs(targets)
    if not target_specs:
        return {}

    # Collect unique NC variables needed
    needed_vars: Dict[str, np.ndarray] = {}  # nc_var -> loaded data

    simulated: Dict[str, float] = {}

    try:
        with nc.Dataset(str(nc_path), "r") as ds:
            for tname, (nc_var, pft_id, factor) in target_specs.items():
                # Lazy-load each NC variable once
                if nc_var not in needed_vars:
                    if nc_var not in ds.variables:
                        logger.debug(f"Variable {nc_var} not in {nc_path.name}")
                        continue
                    data = np.asarray(ds.variables[nc_var][:])
                    data = np.squeeze(data)
                    if data.ndim == 2:
                        # Ensure shape is (n_szpf_levels, n_times)
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

                # obs_idx may be a single int OR a sequence of timestep indices
                # to AVERAGE. Averaging consecutive months (e.g. July+August
                # means) better matches a single late-month point measurement
                # than one monthly mean does. Validate all requested indices.
                idxs = ([int(obs_idx)] if isinstance(obs_idx, (int, np.integer))
                        else [int(k) for k in obs_idx])
                if any(k < 0 or k >= data.shape[1] for k in idxs):
                    logger.warning(
                        f"obs_idx {obs_idx} out of range for {nc_var} "
                        f"(n_times={data.shape[1]})"
                    )
                    continue

                # Aggregate SZPF across size classes for this PFT, then mean
                # over the requested timestep(s).
                szpf_start, szpf_end = get_szpf_range(pft_id)
                per_t = [float(np.nansum(data[szpf_start : szpf_end + 1, k]))
                         for k in idxs]
                simulated[tname] = float(np.mean(per_t)) * factor

    except Exception as e:
        logger.error(f"Failed to read {nc_path}: {e}")

    return simulated


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
