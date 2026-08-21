#!/usr/bin/env python3
"""ELM land-column (snow + soil) calibration-target extraction — SNOW_/SOIL_ keys.

Separate from the FATES SZPF path (`evaluate_case.extract_case_series`) and the FATES
ecosystem path (`extract_ecosystem_series`). Routes each SNOW_/SOIL_ target by the
variable's registered SHAPE (`tools/land_output_variables`):

  - `site`    -> a 1-D `(time,)` gridcell scalar (SNOWDP, H2OSNO, FSNO)   [read_site_1d]
  - `profile` -> a depth/layer-resolved var, one layer selected            [read_profile_layer]
                 (`SOIL_tsoi_10cm` = nearest node to 10 cm; `SOIL_tsoi_L3` = layer 3)

Same call signature as the other extractors, so `evaluate_case.extract_all_series`
dispatches uniformly and the result feeds the same generic scoring.

Author: Jing Tao with Claude on Perlmutter.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

try:
    import netCDF4 as nc
    HAS_NETCDF = True
except ImportError:  # pragma: no cover
    HAS_NETCDF = False

from tools.land_output_variables import parse_land_target_key, resolve_land_var
from tools.extract_site_common import read_site_1d, read_profile_layer, windows_to_points

logger = logging.getLogger(__name__)


def parse_land_specs(targets) -> Dict[str, Tuple[str, str, object, float]]:
    """`{name: (nc_var, level, selector, factor)}` for resolvable SNOW_/SOIL_ keys.

    Enforces shape/selector consistency: a `site` var must carry NO depth/layer suffix; a
    `profile` var MUST carry one (`_<N>cm` or `_L<n>`). Inconsistent or unknown keys are
    skipped (so the caller's other-level keys are naturally ignored here).
    """
    specs: Dict[str, Tuple[str, str, object, float]] = {}
    for tname in targets:
        parsed = parse_land_target_key(tname)
        if parsed is None:
            continue
        shorthand, selector = parsed
        try:
            nc_var, level, vcoord, _units, factor = resolve_land_var(shorthand)
        except KeyError:
            logger.debug(f"Unknown land variable '{shorthand}' in target {tname}")
            continue
        if level == "site" and selector is not None:
            logger.warning(f"{tname}: '{shorthand}' is a site-level var — drop the depth/layer suffix")
            continue
        if level == "profile" and selector is None:
            logger.warning(f"{tname}: '{shorthand}' is layer-resolved — add _surface/_bottom, "
                           f"a layer (_L<n>), or a depth (_<N>cm for soil)")
            continue
        if vcoord == "levsno" and selector[0] in ("depth",):
            logger.warning(f"{tname}: snow layers are DYNAMIC (no fixed depth) — use _surface or "
                           f"_bottom (or _L<n>), not a depth (_<N>cm)")
            continue
        specs[tname] = (nc_var, level, selector, factor)
    return specs


def extract_land_series(
    nc_file: Path,
    targets: Dict,
    windows_by_target: Dict[str, List[List[int]]],
) -> Dict[str, np.ndarray]:
    """Per-observation-point simulated values for SNOW_/SOIL_ targets.

    `{name: array(n_points,)}` in validation units. Non-land targets ignored; missing
    vars / out-of-range indices skipped (same semantics as the other extractors).
    """
    if not HAS_NETCDF:
        raise ImportError("netCDF4 is required.  Install with: pip install netCDF4")

    nc_path = Path(nc_file)
    if not nc_path.exists():
        logger.warning(f"NC file not found: {nc_path}")
        return {}

    specs = parse_land_specs(targets)
    if not specs:
        return {}

    simulated: Dict[str, np.ndarray] = {}
    try:
        with nc.Dataset(str(nc_path), "r") as ds:
            for tname, (nc_var, level, selector, factor) in specs.items():
                windows = windows_by_target.get(tname)
                if not windows:
                    logger.debug(f"No timestep window for target {tname}; skipping")
                    continue
                if level == "site":
                    data = read_site_1d(ds, nc_var)
                else:
                    data = read_profile_layer(ds, nc_var, selector)
                if data is None:
                    continue
                pts = windows_to_points(data, windows, factor, label=tname)
                if pts is not None:
                    simulated[tname] = pts
    except Exception as e:  # pragma: no cover
        logger.error(f"Failed to read {nc_path}: {e}")

    return simulated
