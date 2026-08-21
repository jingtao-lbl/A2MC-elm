#!/usr/bin/env python3
"""Shared readers for the level-dispatched extractors (ecosystem / land site / profile).

Factored out so the site-scalar read (1-D `(time,)`) and the window→point reduction are
written once and reused by `extract_ecosystem_series` (ECO_), `extract_land_series`
(SNOW_/SOIL_ site + the depth-selected profile series), rather than duplicated per module.

Author: Jing Tao with Claude on Perlmutter.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Vertical dimensions a soil/snow variable may carry (ELM history 2-D subscripts).
VERTICAL_DIMS = ("levgrnd", "levsoi", "levsno", "levlak", "levtot")

# Fallback ELM soil node depths (m) for `levgrnd` (15 layers) when the coordinate
# variable is absent from the NC. Standard CLM/ELM exponential soil discretization.
LEVGRND_NODE_DEPTHS_M = [
    0.0071006, 0.0279250, 0.0622586, 0.1188651, 0.2121934, 0.3660658, 0.6197585,
    1.0380273, 1.7276353, 2.8646071, 4.7391566, 7.8297664, 12.9253206, 21.3264717,
    35.1776199,
]


def _read_masked(var) -> np.ndarray:
    """Read a NetCDF var as float with fill/spval -> NaN (masked array or |x|>=1e30)."""
    raw = var[:]
    data = raw.filled(np.nan).astype(float) if np.ma.isMaskedArray(raw) else np.asarray(raw, dtype=float)
    data[np.abs(data) >= 1e30] = np.nan   # ELM spval (~1e36) safety net
    return data


def read_site_1d(ds, nc_var: str) -> Optional[np.ndarray]:
    """Read a site/gridcell variable as a 1-D `(time,)` array (or None if unusable).

    Fill/spval -> NaN. Squeezes size-1 dims; if a spatial axis survives (multiple
    gridcells) takes gridcell 0 (the long axis is time). Returns None if not 1-D.
    """
    if nc_var not in ds.variables:
        logger.debug(f"Variable {nc_var} not in dataset")
        return None
    data = np.squeeze(_read_masked(ds.variables[nc_var]))
    if data.ndim == 2:
        logger.warning(f"{nc_var} shape {data.shape} after squeeze; using gridcell 0.")
        data = data[:, 0] if data.shape[0] >= data.shape[1] else data[0, :]
    elif data.ndim != 1:
        logger.warning(f"Skipping {nc_var}: not a 1-D site series (ndim={data.ndim})")
        return None
    return data


def windows_to_points(
    data1d: np.ndarray,
    windows: List[List[int]],
    factor: float,
    label: str = "",
) -> Optional[np.ndarray]:
    """Reduce a 1-D `(time,)` series to one value per observation point.

    Each window is a list of monthly indices; the point value is their mean × factor.
    Returns None if any index is out of range (same skip semantics as the SZPF path).
    """
    all_idxs = [int(k) for w in windows for k in w]
    if any(k < 0 or k >= len(data1d) for k in all_idxs):
        logger.warning(f"obs index out of range for {label} (n_times={len(data1d)}, windows={windows})")
        return None
    pts = []
    for window in windows:
        per_t = [float(data1d[int(k)]) for k in window]
        pts.append(float(np.nanmean(per_t)) * factor)
    return np.array(pts, dtype=float)


def read_profile_layer(ds, nc_var: str, selector) -> Optional[np.ndarray]:
    """Read a depth/layer-resolved var `(time, vert)` and return ONE layer as `(time,)`.

    Vertical-coordinate-agnostic (`levgrnd` soil, `levsno` snow, `levsoi`). Fill/spval -> NaN.
    `selector`:
      ('index', n)   -- 1-based layer (fixed; NOT meaningful for dynamic snow layers)
      ('depth', cm)  -- nearest node depth (needs a depth coordinate; soil only)
      ('surface',)   -- the shallowest EXISTING layer per timestep (first non-NaN); for
                        dynamic snow this is the top snow layer regardless of layer count
      ('bottom',)    -- the deepest output layer (last index); for snow the bottom snow
                        layer (always present when snow exists in the default ELM layout)
    Returns None if unusable.
    """
    if nc_var not in ds.variables:
        logger.debug(f"Variable {nc_var} not in dataset")
        return None
    var = ds.variables[nc_var]
    surviving = [name for ax, name in enumerate(var.dimensions) if var.shape[ax] != 1]
    data = np.squeeze(_read_masked(var))
    if data.ndim != 2:
        logger.warning(f"Skipping {nc_var}: expected a 2-D (time, vert) var, got ndim={data.ndim}")
        return None
    dims = surviving if len(surviving) == 2 else [None, None]  # dim names, best-effort
    # Orient to (time, vert). Prefer dim NAMES (robust even if n_times is small); fall back
    # to "the vertical axis is the smaller one" only when names are unavailable.
    vert_axis = next((i for i, d in enumerate(dims) if isinstance(d, str) and d in VERTICAL_DIMS), None)
    if vert_axis == 0 or (vert_axis is None and data.shape[0] < data.shape[1]):
        data = data.T
        dims = list(reversed(dims))
    n_vert = data.shape[1]
    vdim = next((d for d in dims if isinstance(d, str) and d in VERTICAL_DIMS), None)

    kind = selector[0]
    if kind == "bottom":
        return data[:, -1]
    if kind == "surface":
        out = np.full(data.shape[0], np.nan)
        finite = np.isfinite(data)
        for t in range(data.shape[0]):
            js = np.nonzero(finite[t])[0]
            if js.size:
                out[t] = data[t, js[0]]
        return out
    if kind == "index":
        idx = int(selector[1]) - 1  # 1-based -> 0-based
    else:  # 'depth' in cm -> nearest node depth (m)
        depth_m = float(selector[1]) / 100.0
        coord = None
        if vdim and vdim in ds.variables:
            coord = np.asarray(ds.variables[vdim][:], dtype=float)
        elif vdim in (None, "levgrnd") and n_vert == len(LEVGRND_NODE_DEPTHS_M):
            coord = np.asarray(LEVGRND_NODE_DEPTHS_M, dtype=float)
        if coord is None:
            logger.warning(f"{nc_var}: no depth coordinate for '{vdim}' — use a layer index "
                           f"(_L<n>) or surface/bottom instead of a depth (_<N>cm).")
            return None
        idx = int(np.argmin(np.abs(coord[:n_vert] - depth_m)))
    if idx < 0 or idx >= n_vert:
        logger.warning(f"{nc_var}: layer index {idx} out of range (n_vert={n_vert})")
        return None
    return data[:, idx]
