#!/usr/bin/env python3
"""Ecosystem-level (site-scalar) calibration-target extraction — the ECO_<var> path.

Kept SEPARATE from the per-PFT SZPF extractor (`tools/evaluate_case.extract_case_series`):
an ecosystem target is a gridcell/site scalar (GPP, LAI, ET) read as a 1-D `(time,)`
series with NO PFT/SZPF slicing. Same call signature as `extract_case_series`, so the
dispatcher (`evaluate_case.extract_all_series`) treats every level uniformly, and the
result feeds the same generic scoring (`tools/cost_functions`).

Target key grammar: `ECO_<var>` (e.g. `ECO_gpp`, `ECO_lai`, `ECO_eflx_lh_tot`, `ECO_nee`).
`<var>` resolves FATES-first through the variable-family registry
(`tools/fates_output_variables`) to `family.site_var` (`ECO_gpp` -> `FATES_GPP`,
`ECO_lai` -> `FATES_LAI`), then falls back to the ELM ecosystem registry
(`tools/elm_ecosystem_variables`) for ELM-side fluxes/states (`ECO_eflx_lh_tot` ->
`EFLX_LH_TOT`, `ECO_nee` -> `NEE`). A leading `fates_` on `<var>` is stripped.

Author: Jing Tao with Claude on Perlmutter.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

try:
    import netCDF4 as nc
    HAS_NETCDF = True
except ImportError:  # pragma: no cover
    HAS_NETCDF = False

from tools.fates_output_variables import resolve_target_name, get_variable_family
from tools.elm_ecosystem_variables import resolve_elm_eco_var

logger = logging.getLogger(__name__)

ECO_KEY = re.compile(r"ECO_(\w+)$")


def parse_ecosystem_specs(targets) -> Dict[str, Tuple[str, float]]:
    """Parse `ECO_<var>` target names into `{name: (site_nc_var, factor)}`.

    Resolution order per key: (1) the FATES variable-family registry (a family with a
    `site_var`); (2) the ELM ecosystem registry (`tools/elm_ecosystem_variables`) for
    ELM-side fluxes/states. Names that match neither are skipped (so a PFT/soil key is
    naturally ignored here).
    """
    specs: Dict[str, Tuple[str, float]] = {}
    for tname in targets:
        m = ECO_KEY.match(tname)
        if not m:
            continue
        var_type = m.group(1).lower()
        # An ECO_ target may be written with the FATES variable prefix
        # (`ECO_fates_gpp`) as well as the bare family name (`ECO_gpp`); strip a
        # leading `fates_` so both resolve to the same family (-> FATES_GPP).
        if var_type.startswith("fates_"):
            var_type = var_type[len("fates_"):]

        nc_var = None
        factor = 1.0
        # (1) FATES vegetation family (site_var)
        try:
            fam = get_variable_family(resolve_target_name(var_type))
            if fam.site_var:
                nc_var, factor = fam.site_var, fam.validation_factor
        except KeyError:
            pass
        # (2) ELM ecosystem flux/state registry
        if nc_var is None:
            try:
                nc_var, _units, factor = resolve_elm_eco_var(var_type)
            except KeyError:
                logger.debug(f"Unknown ecosystem variable '{var_type}' in target {tname}")
                continue

        specs[tname] = (nc_var, factor)
    return specs


def extract_ecosystem_series(
    nc_file: Path,
    targets: Dict,
    windows_by_target: Dict[str, List[List[int]]],
) -> Dict[str, np.ndarray]:
    """Per-observation-point simulated values for `ECO_<var>` targets (1-D site read).

    Mirrors `extract_case_series`: for each target, average the site variable over each
    window's monthly indices, apply the family factor. Returns `{name: array(n_points,)}`
    in validation units. Non-`ECO_` targets are ignored; missing vars / out-of-range
    indices are skipped (same semantics as the SZPF extractor).
    """
    if not HAS_NETCDF:
        raise ImportError("netCDF4 is required.  Install with: pip install netCDF4")

    nc_path = Path(nc_file)
    if not nc_path.exists():
        logger.warning(f"NC file not found: {nc_path}")
        return {}

    specs = parse_ecosystem_specs(targets)
    if not specs:
        return {}

    simulated: Dict[str, np.ndarray] = {}
    loaded: Dict[str, np.ndarray] = {}
    try:
        with nc.Dataset(str(nc_path), "r") as ds:
            for tname, (nc_var, factor) in specs.items():
                windows = windows_by_target.get(tname)
                if not windows:
                    logger.debug(f"No timestep window for target {tname}; skipping")
                    continue

                if nc_var not in loaded:
                    if nc_var not in ds.variables:
                        logger.debug(f"Variable {nc_var} not in {nc_path.name}")
                        continue
                    data = np.squeeze(np.asarray(ds.variables[nc_var][:], dtype=float))
                    if data.ndim == 2:
                        # A spatial axis survived squeeze (e.g. multiple gridcells); the
                        # site series is the long (time) axis — take gridcell 0.
                        logger.warning(f"{nc_var} shape {data.shape} after squeeze; "
                                       f"using gridcell 0 as the site series.")
                        data = data[:, 0] if data.shape[0] >= data.shape[1] else data[0, :]
                    elif data.ndim != 1:
                        logger.warning(f"Skipping {nc_var}: not a 1-D site series (ndim={data.ndim})")
                        continue
                    loaded[nc_var] = data

                data = loaded.get(nc_var)
                if data is None:
                    continue

                all_idxs = [int(k) for w in windows for k in w]
                if any(k < 0 or k >= len(data) for k in all_idxs):
                    logger.warning(f"obs index out of range for {nc_var} "
                                   f"(n_times={len(data)}, windows={windows})")
                    continue

                point_vals = []
                for window in windows:
                    per_t = [float(data[int(k)]) for k in window]
                    point_vals.append(float(np.nanmean(per_t)) * factor)
                simulated[tname] = np.array(point_vals, dtype=float)
    except Exception as e:  # pragma: no cover
        logger.error(f"Failed to read {nc_path}: {e}")

    return simulated
