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

# Number of size classes in SZPF dimension (FATES default: 13)
N_SIZE_CLASSES = 13


def get_n_szpf_levels(fates_pft: int) -> int:
    """Calculate total SZPF levels for a given number of PFTs."""
    return N_SIZE_CLASSES * fates_pft


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


# =============================================================================
# SZPF Index Mapping Functions
# =============================================================================

def get_szpf_range(pft_id: int, fates_pft: int = 12) -> Tuple[int, int]:
    """
    Get the SZPF index range (inclusive) for a given PFT.

    SZPF dimension is arranged as:
    [PFT1_size1, PFT1_size2, ..., PFT1_size13, PFT2_size1, ..., PFTn_size13]

    Parameters
    ----------
    pft_id : int
        PFT number (1 to fates_pft)
    fates_pft : int, optional
        Total number of PFTs in the configuration (default: 12)

    Returns
    -------
    tuple
        (start_index, end_index) - 0-based, inclusive

    Examples
    --------
    >>> get_szpf_range(1)
    (0, 12)
    >>> get_szpf_range(7)
    (78, 90)
    >>> get_szpf_range(12)
    (143, 155)
    >>> get_szpf_range(14, fates_pft=14)
    (169, 181)
    """
    if not 1 <= pft_id <= fates_pft:
        raise ValueError(f"PFT ID must be 1-{fates_pft}, got {pft_id}")

    # SZPF indices: (pft_id - 1) * 13 to (pft_id - 1) * 13 + 12
    start = (pft_id - 1) * N_SIZE_CLASSES
    end = start + N_SIZE_CLASSES - 1
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
    - kg m-2 s-1 → g m-2 yr-1: multiply by 1000 * 31557600 (seconds per year)
    - kg m-2 s-1 → g m-2 day-1: multiply by 1000 * 86400
    """
    SECONDS_PER_DAY = 86400
    SECONDS_PER_YEAR = 31557600  # 365.25 days

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
