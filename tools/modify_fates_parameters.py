#!/usr/bin/env python3
"""
FATES Parameter Modification Tool

Modifies specific parameters in a FATES parameter file (NetCDF `.nc` or JSON `.json` — the format is
auto-detected by extension/magic bytes; api-31 uses NetCDF, api-43+ uses JSON) and creates a new file.
Supports both absolute values and percentage changes.

Usage:
    python modify_fates_parameters.py --input input.json --output output.json --param param_name --pft 10 --value 0.5
    python modify_fates_parameters.py --input input.nc --output output.nc --param param_name --pft 10 --percent +40

Notes: For non-PFT-dependent (global) parameters, use --pft 0
Or use the config file method:
    python modify_fates_parameters.py --input input.json --output output.json --config modifications.yaml

Example:
    python modify_fates_parameters.py \
    --input  "$A2MC_PARAM_DIR/fates_params_<...>_En3643.json" \
    --output "$A2MC_PARAM_DIR/fates_params_<...>_En3643_mod.json" \
     --param fates_alloc_storage_cushion \
     --pft 10 \
     --value 3.0 \
     --verify

Created: December 9, 2025
"""

import argparse
import json
import logging
import netCDF4 as nc
import numpy as np
import re
import shutil
import sys
from pathlib import Path


# =============================================================================
# Format detection (v2.100: api-43+ JSON support)
# =============================================================================

def detect_format(path) -> str:
    """Detect parameter file format. Returns 'json' or 'netcdf'.

    Detection order:
      1. File extension (`.json` -> json; `.nc` / `.nc4` / `.cdf` -> netcdf)
      2. Magic bytes (HDF5 / netCDF3 -> netcdf; leading `{` -> json)

    Raises ValueError if the format can't be determined.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in (".nc", ".nc4", ".cdf"):
        return "netcdf"
    # Fallback: peek at first bytes
    try:
        with open(p, "rb") as f:
            head = f.read(8)
    except OSError as e:
        raise ValueError(f"Cannot read {p} for format detection: {e}")
    if head.startswith(b"\x89HDF") or head[:3] == b"CDF":
        return "netcdf"
    stripped = head.lstrip()
    if stripped.startswith(b"{"):
        return "json"
    raise ValueError(
        f"Cannot detect parameter file format for {p} (suffix={suffix!r}, "
        f"first bytes={head!r}). Expected .json or .nc/.nc4/.cdf."
    )

logger = logging.getLogger(__name__)

# Organ name → 1-based index mapping (matches modify_parameter() convention)
ORGAN_NAME_TO_INDEX = {
    'leaf': 1,
    'fineroot': 2,
    'sapwood': 3,
    'storage': 4,
}


def build_param_lookup(param_list_file):
    """
    Parse a parameter list file and build a shorthand → resolution dict.

    The parameter list file has tab-separated columns:
        No  ELM-FATES_name  Shorthand  Lower  Upper  Default  Description

    Returns:
        dict: shorthand → {'fates_name': str, 'pft': int, 'organ': int or None}
              pft is 1-based (7, 9, 10, etc.) or 0 for global parameters.
              organ is 1-based (1=leaf, 2=fineroot, 3=sapwood, 4=storage) or None.
    """
    lookup = {}
    param_list_file = Path(param_list_file)

    if not param_list_file.exists():
        raise FileNotFoundError(f"Parameter list file not found: {param_list_file}")

    with open(param_list_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('='):
                continue

            parts = line.split('\t')
            if len(parts) < 4:
                continue

            try:
                int(parts[0])  # Column number — skip non-data lines
            except ValueError:
                continue

            fates_name = parts[1].strip()
            shorthand = parts[2].strip()

            # Extract PFT from shorthand suffix (_7, _9, _10, etc.)
            pft = 0
            pft_match = re.search(r'_(\d+)$', shorthand)
            if pft_match:
                pft = int(pft_match.group(1))

            # Extract organ from shorthand — only when organ name immediately precedes PFT suffix
            # e.g., stoich_nitr_leaf_7 → organ=leaf, but alloc_storage_cushion_7 → no organ
            organ = None
            if pft_match:
                pft_suffix = pft_match.group(0)  # e.g., "_10"
                for organ_name, organ_idx in ORGAN_NAME_TO_INDEX.items():
                    if shorthand.endswith(f'_{organ_name}{pft_suffix}'):
                        organ = organ_idx
                        break

            lookup[shorthand] = {
                'fates_name': fates_name,
                'pft': pft,
                'organ': organ,
            }

    return lookup


def _is_new_param_list_format(param_file) -> bool:
    """True if `param_file` is the docs/37 explicit-column CSV (header starts with `fates_name`)."""
    try:
        with open(param_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                return ',' in line and line.split(',')[0].strip() == 'fates_name'
    except OSError:
        return False
    return False


def _organ_for_return(organ_list):
    """Loader organ list → the resolve_parameter_name return form: [] → None, [x] → x,
    [1,2] (retrans) → list (so design_experiments broadcasts to both slots)."""
    if not organ_list:
        return None
    if len(organ_list) == 1:
        return organ_list[0]
    return list(organ_list)


def _resolve_from_specs(name, pft, organ, specs):
    """Resolve (name, pft, organ) against docs/37 loader specs → (fates_name, pft, organ).

    `name` may be a canonical_id or a bare fates_name. An explicit organ passes through; if
    omitted, it is taken from the (unique) matching spec — retrans → [1,2] (broadcast), a single
    organ → its int; an ambiguous organ-dimensioned param (e.g. stoich leaf+fineroot) raises.
    """
    target_pft = pft if pft is not None else 0
    for s in specs:
        if s.canonical_id == name:
            return (s.fates_name, s.pft, organ if organ is not None else _organ_for_return(s.organ))
    if organ is not None:
        return (name, target_pft, organ)
    matches = [s for s in specs if s.fates_name == name and s.pft == target_pft]
    if not matches:
        return (name, target_pft, organ)
    if len(matches) == 1:
        return (name, target_pft, _organ_for_return(matches[0].organ))
    organs = sorted({o for m in matches for o in m.organ})
    raise ValueError(
        f"Parameter '{name}' PFT {target_pft} is organ-dependent but no organ was specified. "
        f"Available organs: {organs}. The hypothesis must include the 'organ' field "
        f"(1=leaf, 2=fineroot, 3=sapwood, 4=structure).")


def resolve_parameter_name(name, pft=None, organ=None, param_lookup=None, specs=None):
    """
    Resolve a parameter name (shorthand or full) to (fates_name, pft, organ).

    Resolution order:
    1. If `specs` (docs/37 loader specs) is given → resolve against canonical identity.
    2. If name is in param_lookup → use lookup values (shorthand resolution)
    3. If name starts with 'fates_' → pass through as full name
    4. Otherwise → return as-is (caller will get a clear NetCDF error)

    Explicit pft/organ arguments override lookup values when provided.

    Args:
        name: Parameter name (canonical_id / shorthand / full FATES name)
        pft: Explicit PFT index (overrides lookup if not None)
        organ: Explicit organ index (overrides lookup if not None)
        param_lookup: Dict from build_param_lookup() (legacy .txt), or None
        specs: List[ParamSpec] from load_param_spec() (new CSV), or None

    Returns:
        tuple: (fates_name, pft, organ) where pft is int (0=global) and organ is
               int, list[int] (retrans → [1,2] for leaf+fineroot), or None
    """
    if specs is not None:
        return _resolve_from_specs(name, pft, organ, specs)

    resolved_name = name
    resolved_pft = pft if pft is not None else 0
    resolved_organ = organ

    if param_lookup and name in param_lookup:
        entry = param_lookup[name]
        resolved_name = entry['fates_name']
        if pft is None:
            resolved_pft = entry['pft']
        if organ is None:
            resolved_organ = entry['organ']
    elif name.startswith('fates_') and param_lookup and organ is None:
        # Full FATES name passed — try reverse lookup to find organ info.
        # This handles cases where AI proposes e.g. 'fates_stoich_phos' without
        # specifying organ, but the param_lookup has organ-specific entries like
        # 'stoich_phos_leaf_10' that map to the same fates_name.
        target_pft = pft if pft is not None else 0
        matching_organs = set()
        for entry in param_lookup.values():
            if entry['fates_name'] == name and entry['pft'] == target_pft and entry['organ'] is not None:
                matching_organs.add(entry['organ'])

        if len(matching_organs) == 1:
            resolved_organ = matching_organs.pop()
            organ_names = {v: k for k, v in ORGAN_NAME_TO_INDEX.items()}
            logger.info(f"Auto-resolved organ for '{name}' PFT {target_pft}: "
                        f"organ={resolved_organ} ({organ_names.get(resolved_organ, '?')})")
        elif len(matching_organs) > 1:
            # Multiple organs found.
            # For retrans params: same value applies to leaf+fineroot (senescing
            # tissues only), so return both organs as a list.
            RETRANS_PARAMS = {
                'fates_cnp_turnover_nitr_retrans',
                'fates_cnp_turnover_phos_retrans',
            }
            if name in RETRANS_PARAMS:
                resolved_organ = sorted(matching_organs)  # [1, 2]
                organ_names = {v: k for k, v in ORGAN_NAME_TO_INDEX.items()}
                organs_str = ', '.join(f"{o}={organ_names.get(o, '?')}" for o in resolved_organ)
                logger.info(f"Retrans param '{name}' PFT {target_pft}: "
                            f"auto-resolved to organs [{organs_str}] (senescing tissues)")
            else:
                # Non-retrans: cannot guess, require explicit specification
                organ_names = {v: k for k, v in ORGAN_NAME_TO_INDEX.items()}
                organs_str = ', '.join(f"{o}={organ_names.get(o, '?')}" for o in sorted(matching_organs))
                raise ValueError(
                    f"Parameter '{name}' PFT {target_pft} is organ-dependent but no organ "
                    f"was specified. Available organs: {organs_str}. "
                    f"The AI hypothesis must include 'organ' field "
                    f"(1=leaf, 2=fineroot, 3=sapwood, 4=storage)."
                )
    elif not name.startswith('fates_'):
        # Not in lookup and not a full FATES name — warn but pass through
        logger.warning(f"Parameter '{name}' not found in lookup and doesn't start with 'fates_'. "
                       f"Passing through as-is.")

    return (resolved_name, resolved_pft, resolved_organ)


def modify_parameter(nc_file, param_name, pft_index, new_value=None, percent_change=None, organ=None, verbose=True):
    """
    Modify a single parameter in the NetCDF file.

    Parameters:
    -----------
    nc_file : netCDF4.Dataset
        Open NetCDF dataset in write mode
    param_name : str
        Name of the parameter (e.g., 'fates_alloc_storage_cushion', 'fates_stoich_nitr')
    pft_index : int
        PFT index (1-based, will be converted to 0-based for array indexing)
        Use 0 or 'global' for non-PFT-specific parameters
    new_value : float, optional
        New absolute value for the parameter
    percent_change : float, optional
        Percentage change (e.g., +40 for 40% increase, -50 for 50% decrease)
    organ : int, optional
        Organ index (1-based, will be converted to 0-based for array indexing)
        Use for 2D parameters like fates_stoich_nitr(organ, pft)
        Organ indices: 1=leaf, 2=fineroot, 3=sapwood, 4=storage
    verbose : bool
        Print modification details

    Returns:
    --------
    old_value : float
        Original value before modification
    new_value : float
        New value after modification
    """
    # Convert PFT index from 1-based to 0-based
    if pft_index > 0:
        pft_array_index = pft_index - 1
    else:
        pft_array_index = None  # Global parameter

    # Convert organ index from 1-based to 0-based
    if organ is not None and organ > 0:
        organ_array_index = organ - 1
    else:
        organ_array_index = None

    # Get the variable
    if param_name not in nc_file.variables:
        raise ValueError(f"Parameter '{param_name}' not found in file. Available: {list(nc_file.variables.keys())}")

    var = nc_file.variables[param_name]

    # Get old value based on dimensions
    if len(var.shape) == 0:  # Scalar variable
        old_value = float(var[:])
    elif len(var.shape) == 1:  # 1D array (PFT-specific)
        if pft_array_index is not None:
            old_value = float(var[pft_array_index])
        else:
            old_value = float(var[:])
    elif len(var.shape) == 2:  # 2D array (organ×PFT or leafage×PFT or similar)
        # Check dimensions to determine indexing order
        dim_names = var.dimensions
        if 'fates_plant_organs' in dim_names and 'fates_pft' in dim_names:
            # Dimensions are (organ, pft)
            organ_dim_idx = dim_names.index('fates_plant_organs')
            pft_dim_idx = dim_names.index('fates_pft')

            if organ_array_index is None or pft_array_index is None:
                raise ValueError(f"Parameter '{param_name}' requires both organ and pft indices. "
                               f"Dimensions: {dim_names}, shape: {var.shape}")

            if organ_dim_idx == 0 and pft_dim_idx == 1:
                # (organ, pft) ordering
                old_value = float(var[organ_array_index, pft_array_index])
            elif organ_dim_idx == 1 and pft_dim_idx == 0:
                # (pft, organ) ordering - less common but check
                old_value = float(var[pft_array_index, organ_array_index])
            else:
                raise ValueError(f"Unexpected dimension ordering for {param_name}: {dim_names}")
        elif 'fates_leafage_class' in dim_names and 'fates_pft' in dim_names:
            # Dimensions are (leafage_class, pft) - treat as PFT-specific with leafage=0
            # This applies to fates_leaf_vcmax25top, fates_turnover_leaf, etc.
            leafage_dim_idx = dim_names.index('fates_leafage_class')
            pft_dim_idx = dim_names.index('fates_pft')

            if pft_array_index is None:
                raise ValueError(f"Parameter '{param_name}' requires pft index. "
                               f"Dimensions: {dim_names}, shape: {var.shape}")

            if leafage_dim_idx == 0 and pft_dim_idx == 1:
                # (leafage, pft) ordering - use leafage index 0
                old_value = float(var[0, pft_array_index])
            elif leafage_dim_idx == 1 and pft_dim_idx == 0:
                # (pft, leafage) ordering
                old_value = float(var[pft_array_index, 0])
            else:
                raise ValueError(f"Unexpected dimension ordering for {param_name}: {dim_names}")
        else:
            raise ValueError(f"Parameter '{param_name}' has 2D shape {var.shape} but unexpected dimensions: {dim_names}")
    else:
        raise ValueError(f"Parameter '{param_name}' has unsupported dimensions: shape={var.shape}, dims={var.dimensions}")

    # Calculate new value
    if new_value is not None:
        final_value = new_value
    elif percent_change is not None:
        multiplier = 1.0 + (percent_change / 100.0)
        final_value = old_value * multiplier
    else:
        raise ValueError("Must provide either new_value or percent_change")

    # Set new value based on dimensions
    if len(var.shape) == 0:  # Scalar
        var[:] = final_value
    elif len(var.shape) == 1:  # 1D array
        if pft_array_index is not None:
            var[pft_array_index] = final_value
        else:
            var[:] = final_value
    elif len(var.shape) == 2:  # 2D array
        dim_names = var.dimensions
        if 'fates_plant_organs' in dim_names and 'fates_pft' in dim_names:
            organ_dim_idx = dim_names.index('fates_plant_organs')
            pft_dim_idx = dim_names.index('fates_pft')

            if organ_dim_idx == 0 and pft_dim_idx == 1:
                var[organ_array_index, pft_array_index] = final_value
            elif organ_dim_idx == 1 and pft_dim_idx == 0:
                var[pft_array_index, organ_array_index] = final_value
        elif 'fates_leafage_class' in dim_names and 'fates_pft' in dim_names:
            leafage_dim_idx = dim_names.index('fates_leafage_class')
            pft_dim_idx = dim_names.index('fates_pft')

            if leafage_dim_idx == 0 and pft_dim_idx == 1:
                # (leafage, pft) ordering - use leafage index 0
                var[0, pft_array_index] = final_value
            elif leafage_dim_idx == 1 and pft_dim_idx == 0:
                # (pft, leafage) ordering
                var[pft_array_index, 0] = final_value

    # Print verbose output
    if verbose:
        organ_str = f", organ {organ}" if organ is not None else ""
        if percent_change is not None:
            print(f"  {param_name}[PFT {pft_index}{organ_str}]: {old_value:.6e} → {final_value:.6e} ({percent_change:+.1f}%)")
        else:
            change_pct = ((final_value - old_value) / old_value * 100) if old_value != 0 else 0
            print(f"  {param_name}[PFT {pft_index}{organ_str}]: {old_value:.6e} → {final_value:.6e} ({change_pct:+.1f}%)")

    return old_value, final_value


def create_modified_parameter_file(input_file, output_file, modifications, verbose=True):
    """
    Create a new parameter file with specified modifications.

    Format-detecting dispatcher (v2.100+). Reads the input file's format
    via detect_format() and routes to the matching backend:
        netcdf -> _create_modified_nc()  (legacy api-31 milestones)
        json   -> _create_modified_json() (api-43+ milestones)

    Public API is stable — callers don't need to know which format the
    backend uses. Same `modifications` list shape works for both.

    Parameters:
    -----------
    input_file : str or Path
        Path to input parameter file (.nc or .json)
    output_file : str or Path
        Path to output parameter file (extension must match input)
    modifications : list of dict
        List of modifications, each dict containing:
        - 'param': parameter name (e.g., 'fates_alloc_storage_cushion', 'fates_stoich_nitr')
        - 'pft': PFT index (1-12, or 0 for global)
        - 'organ': organ index (1-4, optional, for 2D parameters)
                   1=leaf, 2=fineroot, 3=sapwood, 4=storage
        - 'value': new absolute value (optional)
        - 'percent': percentage change (optional, e.g., +40, -50)
    verbose : bool
        Print progress information

    Example:
    --------
    modifications = [
        {'param': 'fates_alloc_storage_cushion', 'pft': 10, 'percent': +40},
        {'param': 'fates_allom_d2bl1', 'pft': 10, 'percent': +40},
        {'param': 'fates_stoich_nitr', 'pft': 9, 'organ': 1, 'value': 0.058},  # leaf N:C
    ]
    """
    input_file = Path(input_file)
    output_file = Path(output_file)

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    fmt = detect_format(input_file)
    if fmt == "json":
        return _create_modified_json(input_file, output_file, modifications, verbose=verbose)
    return _create_modified_nc(input_file, output_file, modifications, verbose=verbose)


def _modify_json_param(params_doc, param_name, pft_index,
                       new_value=None, percent_change=None,
                       organ=None, verbose=True):
    """JSON twin of modify_parameter().

    Operates on the loaded JSON document (dict). Handles the same 4 access
    patterns as the NetCDF path:
      - scalar: dims == []
      - 1D PFT: dims == ["fates_pft"]
      - 2D organ × PFT: dims contains both "fates_plant_organs" and "fates_pft"
      - 2D leafage × PFT: dims contains both "fates_leafage_class" and "fates_pft"
        (uses leafage index 0, same as NC path)

    Returns (old_value, new_value). Modifies params_doc in place.

    Index convention matches NC path: pft_index and organ are 1-based on
    input, converted to 0-based for array indexing.
    """
    # PFT / organ 1-based -> 0-based
    pft_array_index = pft_index - 1 if pft_index > 0 else None
    organ_array_index = organ - 1 if organ is not None and organ > 0 else None

    # Look up the parameter
    params = params_doc.get("parameters", {})
    if param_name not in params:
        # Provide a hint of what's available
        available = list(params.keys())
        sample = ", ".join(available[:5])
        raise ValueError(
            f"Parameter {param_name!r} not found in JSON parameter file. "
            f"Available (first 5 of {len(available)}): {sample}..."
        )

    var = params[param_name]
    dims = var.get("dims", []) or []
    data = var.get("data")

    # Read old value based on dim signature
    if not dims or dims == ["scalar"]:
        # Scalar
        if isinstance(data, list):
            old_value = float(data[0]) if data else 0.0
        else:
            old_value = float(data)
    elif dims == ["fates_pft"]:
        if pft_array_index is None:
            old_value = float(data[0])  # use index 0 for "global" reads
        else:
            old_value = float(data[pft_array_index])
    elif "fates_plant_organs" in dims and "fates_pft" in dims:
        organ_dim_idx = dims.index("fates_plant_organs")
        pft_dim_idx = dims.index("fates_pft")
        if organ_array_index is None or pft_array_index is None:
            raise ValueError(
                f"Parameter {param_name!r} requires both organ and pft indices. "
                f"dims={dims}"
            )
        if organ_dim_idx == 0 and pft_dim_idx == 1:
            old_value = float(data[organ_array_index][pft_array_index])
        elif organ_dim_idx == 1 and pft_dim_idx == 0:
            old_value = float(data[pft_array_index][organ_array_index])
        else:
            raise ValueError(
                f"Unexpected dim ordering for {param_name!r}: {dims}"
            )
    elif "fates_leafage_class" in dims and "fates_pft" in dims:
        leafage_dim_idx = dims.index("fates_leafage_class")
        pft_dim_idx = dims.index("fates_pft")
        if pft_array_index is None:
            raise ValueError(
                f"Parameter {param_name!r} requires pft index. dims={dims}"
            )
        # Use leafage=0 (same as NC path)
        if leafage_dim_idx == 0 and pft_dim_idx == 1:
            old_value = float(data[0][pft_array_index])
        elif leafage_dim_idx == 1 and pft_dim_idx == 0:
            old_value = float(data[pft_array_index][0])
        else:
            raise ValueError(
                f"Unexpected dim ordering for {param_name!r}: {dims}"
            )
    else:
        raise ValueError(
            f"Parameter {param_name!r} has unsupported dims: {dims}"
        )

    # Compute new value
    if new_value is not None:
        final_value = new_value
    elif percent_change is not None:
        final_value = old_value * (1.0 + percent_change / 100.0)
    else:
        raise ValueError("Must provide either new_value or percent_change")

    # Write back, mirroring the dim signature
    if not dims or dims == ["scalar"]:
        if isinstance(data, list):
            data[0] = final_value
        else:
            var["data"] = final_value
    elif dims == ["fates_pft"]:
        if pft_array_index is None:
            # Set all PFTs to the same value (rare but supported)
            for i in range(len(data)):
                data[i] = final_value
        else:
            data[pft_array_index] = final_value
    elif "fates_plant_organs" in dims and "fates_pft" in dims:
        organ_dim_idx = dims.index("fates_plant_organs")
        pft_dim_idx = dims.index("fates_pft")
        if organ_dim_idx == 0 and pft_dim_idx == 1:
            data[organ_array_index][pft_array_index] = final_value
        elif organ_dim_idx == 1 and pft_dim_idx == 0:
            data[pft_array_index][organ_array_index] = final_value
    elif "fates_leafage_class" in dims and "fates_pft" in dims:
        leafage_dim_idx = dims.index("fates_leafage_class")
        pft_dim_idx = dims.index("fates_pft")
        if leafage_dim_idx == 0 and pft_dim_idx == 1:
            data[0][pft_array_index] = final_value
        elif leafage_dim_idx == 1 and pft_dim_idx == 0:
            data[pft_array_index][0] = final_value

    if verbose:
        organ_str = f", organ {organ}" if organ is not None else ""
        change_pct = ((final_value - old_value) / old_value * 100) if old_value != 0 else 0
        print(f"  {param_name}[PFT {pft_index}{organ_str}]: "
              f"{old_value:.6e} → {final_value:.6e} ({change_pct:+.1f}%)")

    return old_value, final_value


def _create_modified_json(input_file, output_file, modifications, verbose=True):
    """JSON backend for create_modified_parameter_file.

    Reads the input JSON, applies each modification via _modify_json_param,
    writes the result to output_file. Same `modifications` list shape as
    the NetCDF path.

    Behavior parity with _create_modified_nc:
      - Returns a list of result dicts (param/pft/old_value/new_value/change_pct).
      - Verbose output mirrors the NC path's format.
      - Does NOT enforce cross-parameter constraints (PFT#9 nfix1,
        slamax floor, prescribed_uptake=0); those are caller-side concerns
        handled by phases/phase0_design/generate_parameter_files.py.
    """
    # Read template
    if verbose:
        print(f"\nReading {input_file.name} (JSON)")
    with open(input_file) as f:
        params_doc = json.load(f)

    if verbose:
        print(f"\nApplying {len(modifications)} modifications:")

    results = []
    for mod in modifications:
        param = mod['param']
        pft = mod.get('pft', 0)
        organ = mod.get('organ', None)
        value = mod.get('value', None)
        percent = mod.get('percent', None)

        old_val, new_val = _modify_json_param(
            params_doc, param, pft,
            new_value=value,
            percent_change=percent,
            organ=organ,
            verbose=verbose
        )

        result = {
            'param': param,
            'pft': pft,
            'old_value': old_val,
            'new_value': new_val,
            'change_pct': ((new_val - old_val) / old_val * 100) if old_val != 0 else 0
        }
        if organ is not None:
            result['organ'] = organ
        results.append(result)

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(params_doc, f, indent=2)

    if verbose:
        print(f"\n✓ Successfully created: {output_file}")
        print(f"  File size: {output_file.stat().st_size / 1024:.1f} KB")

    return results


def _create_modified_nc(input_file, output_file, modifications, verbose=True):
    """NetCDF backend for create_modified_parameter_file.

    Existing pre-v2.100 logic, lifted into a private function so the
    public dispatcher can route format. Behavior unchanged — any
    regression here is a regression of the existing NC pipeline.
    """
    # Copy input file to output file
    if verbose:
        print(f"\nCopying {input_file.name} → {output_file.name}")
    shutil.copy2(input_file, output_file)

    # Open output file in write mode and apply modifications
    if verbose:
        print(f"\nApplying {len(modifications)} modifications:")

    with nc.Dataset(output_file, 'r+') as ncfile:
        results = []
        for mod in modifications:
            param = mod['param']
            pft = mod.get('pft', 0)
            organ = mod.get('organ', None)
            value = mod.get('value', None)
            percent = mod.get('percent', None)

            old_val, new_val = modify_parameter(
                ncfile, param, pft,
                new_value=value,
                percent_change=percent,
                organ=organ,
                verbose=verbose
            )

            result = {
                'param': param,
                'pft': pft,
                'old_value': old_val,
                'new_value': new_val,
                'change_pct': ((new_val - old_val) / old_val * 100) if old_val != 0 else 0
            }
            if organ is not None:
                result['organ'] = organ

            results.append(result)

    if verbose:
        print(f"\n✓ Successfully created: {output_file}")
        print(f"  File size: {output_file.stat().st_size / 1024:.1f} KB")

    return results


def _read_json_param_value(var, pft_index, organ):
    """Read a JSON param entry's current value at (pft_index, organ) — both 1-based
    (pft 0/None = global, organ None = non-organ). Mirrors the dim-signature read logic
    of _modify_json_param so verify and modify agree exactly."""
    pft_ai = (pft_index - 1) if pft_index and pft_index > 0 else None
    organ_ai = (organ - 1) if organ is not None and organ > 0 else None
    dims = var.get("dims", []) or []
    data = var.get("data")
    if not dims or dims == ["scalar"]:
        return float(data[0]) if isinstance(data, list) and data else float(data)
    if dims == ["fates_pft"]:
        return float(data[0]) if pft_ai is None else float(data[pft_ai])
    if "fates_plant_organs" in dims and "fates_pft" in dims:
        if organ_ai is None or pft_ai is None:
            raise ValueError(f"organ+pft required for organ-dimensioned param; dims={dims}")
        return (float(data[organ_ai][pft_ai]) if dims.index("fates_plant_organs") == 0
                else float(data[pft_ai][organ_ai]))
    if "fates_leafage_class" in dims and "fates_pft" in dims:
        return (float(data[0][pft_ai]) if dims.index("fates_leafage_class") == 0
                else float(data[pft_ai][0]))
    raise ValueError(f"unsupported dims for JSON verify: {dims}")


def _verify_json(param_file, expected_modifications, verbose=True):
    """JSON twin of verify_modifications (api-43+ `.json` parameter files)."""
    if verbose:
        print(f"\nVerifying modifications in {Path(param_file).name}:")
    with open(param_file) as f:
        params = json.load(f).get("parameters", {})
    all_correct = True
    for mod in expected_modifications:
        param = mod['param']
        pft = mod.get('pft', 0)
        organ = mod.get('organ', None)
        expected_value = mod.get('expected_value', mod.get('value', None))
        organ_str = f", organ {organ}" if organ is not None else ""
        if param not in params:
            if verbose:
                print(f"  ✗ {param}: not found in JSON parameter file")
            all_correct = False
            continue
        actual_value = _read_json_param_value(params[param], pft, organ)
        if expected_value is not None:
            is_correct = np.isclose(actual_value, expected_value, rtol=1e-6)
            if verbose:
                print(f"  {'✓' if is_correct else '✗'} {param}[PFT {pft}{organ_str}]: "
                      f"{actual_value:.6e} (expected: {expected_value:.6e})")
            if not is_correct:
                all_correct = False
        elif verbose:
            print(f"  ℹ {param}[PFT {pft}{organ_str}]: {actual_value:.6e} (not verified)")
    if verbose:
        print("\n✓ All modifications verified successfully" if all_correct
              else "\n✗ Some modifications did not match expected values")
    return all_correct


def verify_modifications(nc_file, expected_modifications, verbose=True):
    """
    Verify that modifications were applied correctly (NetCDF `.nc` or JSON `.json`).

    Parameters:
    -----------
    nc_file : str or Path
        Path to modified parameter file (.nc or .json — format auto-detected).
    expected_modifications : list of dict
        Expected modifications. Each dict uses `param`, `pft`, optional `organ`, and the
        expected value under either `expected_value` or `value` (so the SAME mods list
        passed to create_modified_parameter_file can be passed here to verify).
    verbose : bool
        Print verification results

    Returns:
    --------
    all_correct : bool
        True if all modifications verified correctly
    """
    # api-43+ JSON files: delegate to the JSON reader (this function was NetCDF-only).
    if detect_format(nc_file) == "json":
        return _verify_json(nc_file, expected_modifications, verbose=verbose)

    if verbose:
        print(f"\nVerifying modifications in {Path(nc_file).name}:")

    with nc.Dataset(nc_file, 'r') as ncfile:
        all_correct = True
        for mod in expected_modifications:
            param = mod['param']
            pft = mod.get('pft', 0)
            organ = mod.get('organ', None)
            expected_value = mod.get('expected_value', mod.get('value', None))

            # Get array indices (0-based)
            pft_array_index = (pft - 1) if pft > 0 else None
            organ_array_index = (organ - 1) if organ is not None and organ > 0 else None

            # Get variable
            var = ncfile.variables[param]

            # Get actual value based on dimensions (mirrors modify_parameter logic)
            if len(var.shape) == 0:
                actual_value = float(var[:])
            elif len(var.shape) == 1:
                if pft_array_index is not None:
                    actual_value = float(var[pft_array_index])
                else:
                    actual_value = float(var[:])
            elif len(var.shape) == 2:
                dim_names = var.dimensions
                if 'fates_plant_organs' in dim_names and 'fates_pft' in dim_names:
                    organ_dim_idx = dim_names.index('fates_plant_organs')
                    pft_dim_idx = dim_names.index('fates_pft')
                    if organ_dim_idx == 0 and pft_dim_idx == 1:
                        actual_value = float(var[organ_array_index, pft_array_index])
                    else:
                        actual_value = float(var[pft_array_index, organ_array_index])
                elif 'fates_leafage_class' in dim_names and 'fates_pft' in dim_names:
                    leafage_dim_idx = dim_names.index('fates_leafage_class')
                    pft_dim_idx = dim_names.index('fates_pft')
                    if leafage_dim_idx == 0 and pft_dim_idx == 1:
                        actual_value = float(var[0, pft_array_index])
                    else:
                        actual_value = float(var[pft_array_index, 0])
                else:
                    actual_value = float(var[pft_array_index])
            else:
                actual_value = float(var[pft_array_index])

            # Check if matches expected
            organ_str = f", organ {organ}" if organ is not None else ""
            if expected_value is not None:
                is_correct = np.isclose(actual_value, expected_value, rtol=1e-6)
                status = "✓" if is_correct else "✗"

                if verbose:
                    print(f"  {status} {param}[PFT {pft}{organ_str}]: {actual_value:.6e} (expected: {expected_value:.6e})")

                if not is_correct:
                    all_correct = False
            else:
                if verbose:
                    print(f"  ℹ {param}[PFT {pft}{organ_str}]: {actual_value:.6e} (not verified)")

    if verbose:
        if all_correct:
            print("\n✓ All modifications verified successfully")
        else:
            print("\n✗ Some modifications did not match expected values")

    return all_correct


def main():
    parser = argparse.ArgumentParser(
        description='Modify FATES parameter NetCDF files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Increase storage cushion by 40%% for PFT 10
  %(prog)s --input base.nc --output mod.nc --param fates_alloc_storage_cushion --pft 10 --percent +40

  # Set absolute value for PID gain for PFT 10
  %(prog)s --input base.nc --output mod.nc --param fates_cnp_pid_kp --pft 10 --value 0.0015

  # Set leaf N:C ratio for PFT 9 (2D parameter: organ 1=leaf)
  %(prog)s --input base.nc --output mod.nc --param fates_stoich_nitr --pft 9 --organ 1 --value 0.058

  # Modify global parameter (non-PFT-specific)
  %(prog)s --input base.nc --output mod.nc --param fates_maintresp_nonleaf_baserate --pft 0 --value 1.30e-07

  # Apply multiple modifications from Python script
  See create_modified_parameter_file() function for programmatic use.
        """
    )

    parser.add_argument('--input', '-i', required=True,
                        help='Input FATES parameter file (.nc)')
    parser.add_argument('--output', '-o', required=True,
                        help='Output FATES parameter file (.nc)')
    parser.add_argument('--param', '-p',
                        help='Parameter name (e.g., fates_alloc_storage_cushion, fates_stoich_nitr)')
    parser.add_argument('--pft', type=int,
                        help='PFT index (1-12, or 0 for global parameters)')
    parser.add_argument('--organ', type=int,
                        help='Organ index (1-4, for 2D parameters): 1=leaf, 2=fineroot, 3=sapwood, 4=storage')
    parser.add_argument('--value', type=float,
                        help='New absolute value')
    parser.add_argument('--percent', type=float,
                        help='Percentage change (e.g., +40, -50)')
    parser.add_argument('--verify', action='store_true',
                        help='Verify modifications after applying')
    parser.add_argument('--quiet', '-q', action='store_true',
                        help='Suppress output messages')

    args = parser.parse_args()

    # Check that either value or percent is provided
    if args.param is not None:
        if args.value is None and args.percent is None:
            parser.error("Must provide either --value or --percent")
        if args.value is not None and args.percent is not None:
            parser.error("Cannot provide both --value and --percent")
        if args.pft is None:
            parser.error("Must provide --pft when using --param")

    verbose = not args.quiet

    # Single modification mode
    if args.param is not None:
        modifications = [{
            'param': args.param,
            'pft': args.pft,
        }]
        if args.organ is not None:
            modifications[0]['organ'] = args.organ
        if args.value is not None:
            modifications[0]['value'] = args.value
        if args.percent is not None:
            modifications[0]['percent'] = args.percent

        results = create_modified_parameter_file(
            args.input, args.output, modifications, verbose=verbose
        )

        if args.verify:
            expected = [{
                'param': args.param,
                'pft': args.pft,
                'expected_value': results[0]['new_value']
            }]
            if args.organ is not None:
                expected[0]['organ'] = args.organ
            verify_modifications(args.output, expected, verbose=verbose)
    else:
        parser.error("Must provide --param (or use programmatic interface for multiple modifications)")


if __name__ == '__main__':
    main()
