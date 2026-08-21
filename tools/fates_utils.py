"""
FATES Data Utilities for A2MC

This module provides utilities for working with FATES output data:
- PFT and SZPF dimension mapping
- Data aggregation across size classes
- Unit conversion helpers

FATES Output Dimension Levels:
- Site-level (1D): (time,) - Gridcell-aggregated (e.g., FATES_GPP)
- PFT-level (2D): (fates_levpft, time) - By PFT, 12 levels (e.g., FATES_LEAFC_PF)
- SZPF-level (2D): (fates_levscpf, time) - By size×PFT, 156 levels (e.g., FATES_PUPTAKE_SZPF)

Author: A2MC Framework
"""

import numpy as np
from typing import Tuple, Dict

# =============================================================================
# FATES Dimension Configuration
# =============================================================================

# FALLBACK ONLY — number of history size classes (nlevsclass) in the SZPF/levscpf
# dimension. This is NOT a fixed FATES constant: it is len(fates_history_sizeclass_bin_edges)
# in the parameter file (13 in the common default, but configurable). Always prefer the
# file-derived value — get_n_size_classes(ds) from a NetCDF `fates_levscls` dim, or
# get_n_size_classes_from_file() from the param file. This constant is the last resort.
N_SIZE_CLASSES = 13


def get_n_szpf_levels(fates_pft: int, n_size_classes: int = None) -> int:
    """Total SZPF (levscpf) levels = n_size_classes × fates_pft.

    ``n_size_classes`` defaults to the module fallback; pass the file-derived value
    (``get_n_size_classes*``) whenever available.
    """
    nsc = n_size_classes if n_size_classes is not None else N_SIZE_CLASSES
    return nsc * fates_pft


def get_n_size_classes(ds) -> int:
    """Number of history size classes (nlevsclass) read from an open NetCDF dataset.

    Reads the file's OWN size-class dimension (``fates_levscls`` / ``fates_scls`` /
    ``levscls``) — self-describing, no hardcoded 13. Returns None if absent.
    """
    for cand in ('fates_levscls', 'fates_scls', 'levscls'):
        if cand in ds.dimensions:
            return len(ds.dimensions[cand])
    return None


def get_n_size_classes_from_file(param_file: str) -> int:
    """Number of history size classes from a param file's ``fates_history_sizeclass_bin_edges``.

    That array's length IS nlevsclass. Raises if the param key is absent.
    """
    import json
    from pathlib import Path
    p = Path(param_file)
    if p.suffix == '.json':
        with open(p) as f:
            params = json.load(f)['parameters']
        for k in ('fates_history_sizeclass_bin_edges', 'fates_history_size_bin_edges'):
            if k in params:
                return len(params[k]['data'])
        raise KeyError(f"no fates_history_sizeclass_bin_edges in {p.name}")
    # NetCDF param file: read the dimension length
    import netCDF4 as _nc
    with _nc.Dataset(str(p), 'r') as ds:
        for cand in ('fates_history_size_bins', 'fates_size_bins'):
            if cand in ds.dimensions:
                return len(ds.dimensions[cand])
    raise KeyError(f"no size-class bin dimension in {p.name}")


_NSC_CACHE = {}


def get_n_size_classes_from_config(default: int = None) -> int:
    """nlevsclass derived from ``A2MC_BASE_PARAM_FILE`` (cached); fallback ``N_SIZE_CLASSES``.

    Used when no NetCDF dataset is at hand (e.g. a missing-file placeholder); a present
    file should use :func:`get_n_size_classes` instead.
    """
    import os
    default = N_SIZE_CLASSES if default is None else default
    pf = os.environ.get('A2MC_BASE_PARAM_FILE', '')
    if not pf:
        return default
    if pf not in _NSC_CACHE:
        try:
            _NSC_CACHE[pf] = get_n_size_classes_from_file(pf)
        except Exception:
            _NSC_CACHE[pf] = default
    return _NSC_CACHE[pf]


def get_n_pft_from_file(param_file: str) -> int:
    """
    Total number of PFTs in a FATES parameter file, read from ``fates_pftname``.

    This is the authoritative PFT count for the run — NEVER hardcode it. It follows
    the model: if FATES changes its PFT system (adds/removes PFTs), the count updates
    automatically because it comes from the actual parameter file the model reads.

    Parameters
    ----------
    param_file : str
        Path to the FATES base parameter file (.json or .nc).

    Returns
    -------
    int
        Number of PFTs (length of ``fates_pftname``).
    """
    return len(get_pft_names_from_file(param_file))


_SZPF_TOTAL_CACHE = {}


def get_szpf_total_from_config(default: int = 156) -> int:
    """
    Total SZPF levels (= nlevsclass × n_pft) derived from the run's base param file.

    Reads ``A2MC_BASE_PARAM_FILE`` and derives BOTH factors from it — n_pft from
    ``fates_pftname`` and nlevsclass from ``fates_history_sizeclass_bin_edges`` — so it
    tracks whatever PFT AND size-class configuration the run actually uses, nothing
    hardcoded. Cached per file path. Used only as the placeholder shape when a NetCDF file
    is missing; a present file self-describes via :func:`get_szpf_dim_length`.

    Parameters
    ----------
    default : int
        Fallback if ``A2MC_BASE_PARAM_FILE`` is unset/unreadable (legacy 12-PFT × 13 = 156).

    Returns
    -------
    int
        SZPF total level count.
    """
    import os
    pf = os.environ.get('A2MC_BASE_PARAM_FILE', '')
    if not pf:
        return default
    if pf not in _SZPF_TOTAL_CACHE:
        try:
            _SZPF_TOTAL_CACHE[pf] = get_n_szpf_levels(
                get_n_pft_from_file(pf), get_n_size_classes_from_config()
            )
        except Exception:
            _SZPF_TOTAL_CACHE[pf] = default
    return _SZPF_TOTAL_CACHE[pf]


def get_szpf_dim_length(ds, var_name: str = None) -> int:
    """
    SZPF dimension length (= N_SIZE_CLASSES × n_pft) read from an open NetCDF dataset.

    Robust replacement for the historical hardcoded ``156`` (= 13 × 12 PFTs): it reads
    the file's OWN size×PFT dimension so it is correct for any PFT count (12, 14, …) and
    any future FATES PFT-system change — nothing is assumed.

    Resolution order:
    1. A dataset dimension named ``fates_levscpf`` / ``fates_scpf`` / ``levscpf`` (authoritative).
    2. If ``var_name`` is given, its non-time, >1-length dimension.
    3. ``None`` if neither is found.

    Parameters
    ----------
    ds : netCDF4.Dataset
        Open dataset.
    var_name : str, optional
        SZPF variable whose dimensions to inspect as a fallback.

    Returns
    -------
    int or None
        The SZPF dimension length, or None if it cannot be determined.
    """
    for cand in ('fates_levscpf', 'fates_scpf', 'levscpf'):
        if cand in ds.dimensions:
            return len(ds.dimensions[cand])
    if var_name is not None and var_name in ds.variables:
        for dname in ds.variables[var_name].dimensions:
            if 'time' in dname.lower():
                continue
            size = len(ds.dimensions[dname])
            if size > 1:
                return size
    return None


def get_pft_names_from_file(param_file: str) -> Dict[int, str]:
    """
    Read PFT names from a FATES parameter file (NetCDF or JSON).

    Parameters
    ----------
    param_file : str
        Path to FATES parameter file (.nc or .json)

    Returns
    -------
    dict
        Dictionary mapping PFT ID (1-based) to PFT name

    Examples
    --------
    >>> pft_names = get_pft_names_from_file('fates_params.nc')
    >>> print(pft_names[1])
    'broadleaf_evergreen_tropical_tree'
    """
    import json
    from pathlib import Path

    path = Path(param_file)

    if path.suffix == '.json':
        with open(path, 'r') as f:
            data = json.load(f)
        names = data['parameters']['fates_pftname']['data']
        return {i: name for i, name in enumerate(names, 1)}

    elif path.suffix == '.nc':
        try:
            import netCDF4 as nc
            ds = nc.Dataset(path, 'r')
            # fates_pftname is a character array
            pftname_var = ds.variables['fates_pftname']
            names = [''.join(c.decode() if isinstance(c, bytes) else c
                            for c in row).strip()
                     for row in pftname_var[:]]
            ds.close()
            return {i: name for i, name in enumerate(names, 1)}
        except Exception as e:
            raise ValueError(f"Failed to read PFT names from {path}: {e}")

    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")


def get_pft_display_names(param_file: str = None) -> Dict[int, str]:
    """
    Friendly plot/legend labels ``{pft_id: 'PFT#<id> <fates_pftname>'}`` for a run's PFTs.

    Derived from the base parameter file's ``fates_pftname`` (``$A2MC_BASE_PARAM_FILE`` when
    ``param_file`` is not given), so labels are correct for whatever FATES PFT system the run
    uses. There is deliberately NO hardcoded, api-version-specific fallback (PFT identity is
    not stable across versions — api-31 arctic PFTs were 7/9/10, api-43 are 10/11/12); if the
    base file can't be resolved this raises so a caller either sets it or passes explicit
    labels, rather than mislabeling a figure. [[feedback_verify_pft_identity_across_versions]]
    """
    import os
    from pathlib import Path as _Path
    pf = param_file or os.environ.get('A2MC_BASE_PARAM_FILE', '')
    if not pf or not _Path(pf).exists():
        raise RuntimeError(
            f"Cannot resolve PFT display names: A2MC_BASE_PARAM_FILE is unset or missing "
            f"({pf!r}). Set it (source the site config) so labels come from fates_pftname, "
            f"or pass an explicit pft_names dict — there is no hardcoded fallback."
        )
    return {i: f"PFT#{i} {name}" for i, name in get_pft_names_from_file(pf).items()}


# =============================================================================
# SZPF Index Mapping Functions
# =============================================================================

def get_szpf_range(pft_id: int, fates_pft: int = 12,
                   n_size_classes: int = None) -> Tuple[int, int]:
    """
    Get the SZPF (levscpf) index range (inclusive, 0-based) for a given PFT.

    The FATES levscpf dimension is PFT-major with contiguous size-class blocks
    (verified against FATES source ``main/FatesInterfaceMod.F90``: the map is built
    ``do ipft: do isc:`` → index ``(ipft-1)*nlevsclass + isc``), i.e. arranged as
    ``[PFT1_sc1..PFT1_scK, PFT2_sc1..PFT2_scK, ...]`` where K = nlevsclass. (The FATES
    wiki's ``(size_class-1)*numpft + pft`` formula is a wiki error — the source is PFT-major.)

    Parameters
    ----------
    pft_id : int
        PFT number (1 to fates_pft).
    fates_pft : int, optional
        Total number of PFTs (bound check only; default 12). Pass the file-derived count.
    n_size_classes : int, optional
        nlevsclass = the size-class block width. Defaults to the module fallback
        ``N_SIZE_CLASSES``; ALWAYS pass the file-derived value (``get_n_size_classes(ds)``
        or ``len(fates_history_sizeclass_bin_edges)``) — it is NOT a fixed FATES constant.

    Returns
    -------
    tuple
        (start_index, end_index) - 0-based, inclusive.

    Examples
    --------
    >>> get_szpf_range(1)
    (0, 12)
    >>> get_szpf_range(12)
    (143, 155)
    >>> get_szpf_range(12, fates_pft=14)   # 14-PFT file, same slice (PFT-major)
    (143, 155)
    >>> get_szpf_range(2, n_size_classes=10)  # non-default size-class count
    (10, 19)
    """
    nsc = n_size_classes if n_size_classes is not None else N_SIZE_CLASSES
    if not 1 <= pft_id <= fates_pft:
        raise ValueError(f"PFT ID must be 1-{fates_pft}, got {pft_id}")

    start = (pft_id - 1) * nsc
    end = start + nsc - 1
    return (start, end)


def get_pft_index(pft_id: int, fates_pft: int = 12) -> int:
    """
    Convert PFT ID to 0-based array index for PFT-level variables.

    Parameters
    ----------
    pft_id : int
        PFT number (1 to fates_pft)
    fates_pft : int, optional
        Total number of PFTs in the configuration (default: 12)

    Returns
    -------
    int
        0-based array index

    Examples
    --------
    >>> get_pft_index(1)
    0
    >>> get_pft_index(7)
    6
    >>> get_pft_index(12)
    11
    """
    if not 1 <= pft_id <= fates_pft:
        raise ValueError(f"PFT ID must be 1-{fates_pft}, got {pft_id}")
    return pft_id - 1


# =============================================================================
# Data Aggregation Functions
# =============================================================================

def aggregate_szpf_by_pft(
    szpf_data: np.ndarray,
    pft_id: int,
    axis: int = 0,
    fates_pft: int = 12
) -> np.ndarray:
    """
    Sum SZPF data across size classes for a given PFT.

    This function aggregates size-class × PFT (SZPF) level data to PFT level
    by summing across the 13 size classes for a specific PFT.

    Parameters
    ----------
    szpf_data : np.ndarray
        SZPF-level data. Expected shapes:
        - (n_szpf, time) if axis=0 (SZPF dimension first)
        - (time, n_szpf) if axis=1 (SZPF dimension second)
        where n_szpf = 13 * fates_pft
    pft_id : int
        PFT number (1 to fates_pft)
    axis : int, optional
        Axis along which SZPF dimension is located. Default 0.
    fates_pft : int, optional
        Total number of PFTs in the configuration (default: 12)

    Returns
    -------
    np.ndarray
        1D array with summed values for the PFT across all size classes

    Examples
    --------
    >>> # SZPF data shape (156, 240) - 156 SZPF levels (12 PFTs), 240 months
    >>> pft10_total = aggregate_szpf_by_pft(szpf_data, pft_id=10, axis=0)
    >>> pft10_total.shape
    (240,)

    >>> # For 14-PFT configuration (182 SZPF levels)
    >>> pft14_total = aggregate_szpf_by_pft(szpf_data, pft_id=14, axis=0, fates_pft=14)
    """
    szpf_start, szpf_end = get_szpf_range(pft_id, fates_pft=fates_pft)

    if axis == 0:
        # SZPF dimension is first: (n_szpf, time, ...)
        result = np.sum(szpf_data[szpf_start:szpf_end+1, ...], axis=0)
    elif axis == 1:
        # SZPF dimension is second: (time, n_szpf, ...)
        result = np.sum(szpf_data[:, szpf_start:szpf_end+1, ...], axis=1)
    else:
        raise ValueError(f"axis must be 0 or 1, got {axis}")

    # Ensure clean array (remove any extra dimensions)
    return np.squeeze(np.asarray(result))


def extract_pft_data(
    pft_data: np.ndarray,
    pft_id: int,
    axis: int = 0,
    fates_pft: int = 12
) -> np.ndarray:
    """
    Extract data for a specific PFT from PFT-level variables.

    Parameters
    ----------
    pft_data : np.ndarray
        PFT-level data with shape (fates_pft, time) or (time, fates_pft)
    pft_id : int
        PFT number (1 to fates_pft)
    axis : int, optional
        Axis along which PFT dimension is located. Default 0.
    fates_pft : int, optional
        Total number of PFTs in the configuration (default: 12)

    Returns
    -------
    np.ndarray
        1D array with data for the specified PFT

    Examples
    --------
    >>> # PFT data shape (12, 240) - 12 PFTs, 240 months
    >>> pft10_data = extract_pft_data(pft_data, pft_id=10, axis=0)
    >>> pft10_data.shape
    (240,)
    """
    pft_idx = get_pft_index(pft_id, fates_pft=fates_pft)

    if axis == 0:
        result = pft_data[pft_idx, ...]
    elif axis == 1:
        result = pft_data[:, pft_idx, ...]
    else:
        raise ValueError(f"axis must be 0 or 1, got {axis}")

    return np.squeeze(np.asarray(result))


# =============================================================================
# Unit Conversion Helpers
# =============================================================================

def convert_flux_to_annual(
    flux_data: np.ndarray,
    from_unit: str = 'kg m-2 s-1',
    to_unit: str = 'g m-2 yr-1'
) -> np.ndarray:
    """
    Convert flux data between common FATES units.

    Parameters
    ----------
    flux_data : np.ndarray
        Flux data to convert
    from_unit : str
        Source unit (default: 'kg m-2 s-1')
    to_unit : str
        Target unit (default: 'g m-2 yr-1')

    Returns
    -------
    np.ndarray
        Converted flux data

    Notes
    -----
    Common conversions:
    - kg m-2 s-1 → g m-2 yr-1: multiply by 1000 * 31536000 (seconds per year)
    - kg m-2 s-1 → g m-2 day-1: multiply by 1000 * 86400
    """
    SECONDS_PER_DAY = 86400
    SECONDS_PER_YEAR = 31536000  # 365 days (ELM uses no-leap-year calendar)

    conversion_factors = {
        ('kg m-2 s-1', 'g m-2 yr-1'): 1000 * SECONDS_PER_YEAR,
        ('kg m-2 s-1', 'g m-2 day-1'): 1000 * SECONDS_PER_DAY,
        ('kg m-2', 'g m-2'): 1000,
        ('kg C m-2', 'g C m-2'): 1000,
    }

    key = (from_unit, to_unit)
    if key not in conversion_factors:
        raise ValueError(f"Unknown conversion: {from_unit} → {to_unit}")

    return flux_data * conversion_factors[key]


# =============================================================================
# NetCDF Helper Functions
# =============================================================================

def get_variable_info(ds, var_name: str) -> Dict[str, str]:
    """
    Get metadata for a NetCDF variable.

    Parameters
    ----------
    ds : netCDF4.Dataset
        Open NetCDF dataset
    var_name : str
        Variable name

    Returns
    -------
    dict
        Dictionary with 'units', 'long_name', 'dimensions', 'shape'
    """
    if var_name not in ds.variables:
        raise ValueError(f"Variable '{var_name}' not found in dataset")

    var = ds.variables[var_name]
    return {
        'units': getattr(var, 'units', 'unknown'),
        'long_name': getattr(var, 'long_name', 'unknown'),
        'dimensions': var.dimensions,
        'shape': var.shape,
    }


def identify_dimension_level(ds, var_name: str) -> str:
    """
    Identify the FATES dimension level of a variable.

    Parameters
    ----------
    ds : netCDF4.Dataset
        Open NetCDF dataset
    var_name : str
        Variable name

    Returns
    -------
    str
        One of: 'site', 'pft', 'szpf', 'unknown'
    """
    if var_name not in ds.variables:
        raise ValueError(f"Variable '{var_name}' not found in dataset")

    dims = ds.variables[var_name].dimensions

    if 'fates_levscpf' in dims:
        return 'szpf'
    elif 'fates_levpft' in dims:
        return 'pft'
    elif 'time' in dims and len(dims) <= 2:
        return 'site'
    else:
        return 'unknown'
