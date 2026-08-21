#!/usr/bin/env python3
"""
Phase 3 Diagnosis: Read Case Parameters

Read parameter values from Morris ensemble files or FATES NetCDF parameter files.
Provides the actual parameter values that the AI needs for accurate diagnosis.

Usage (Python API):
    from phases.phase3_diagnosis import read_case_parameters

    params = read_case_parameters(
        case_id=2678,
        morris_file="/path/to/morris_params.txt",
        param_names=["l2fr_ini_9", "pid_kp_10", ...]
    )

Usage (CLI):
    python -m phases.phase3_diagnosis.read_case_parameters \\
        --case-id 2678 \\
        --morris-file /path/to/morris_params.txt \\
        --param-names-file /path/to/param_names.txt \\
        --output params.json

Author: Jing Tao with Claude
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)


def _is_new_param_list(path: str) -> bool:
    """True if `path` is the docs/37 explicit-column CSV (header starts with `fates_name`)."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                return ',' in line and line.split(',')[0].strip() == 'fates_name'
    except OSError:
        return False
    return False


def load_param_names(param_names_file: str) -> List[str]:
    """
    Load parameter names (in Morris-column order) from a parameter list file.

    Supports:
    1. docs/37 CSV → the canonical_ids (`fates_name#p{pft}#o{organ}`).
    2. Simple: one parameter name per line (must contain underscore like 'alpha_ptase_7')
    3. Tabular .txt: No<TAB>FullName<TAB>ShortName<TAB>... (extracts ShortName from column 2)

    Args:
        param_names_file: Path to file with parameter names

    Returns:
        List of parameter names
    """
    if _is_new_param_list(param_names_file):
        from tools.param_spec import load_param_spec
        return [s.canonical_id for s in load_param_spec(param_names_file)]

    names = []
    has_tabs = False

    # First pass: detect if file is tabular (has tab-delimited data rows)
    with open(param_names_file, 'r') as f:
        for line in f:
            if '\t' in line:
                parts = line.split('\t')
                if len(parts) >= 3:
                    try:
                        int(parts[0])
                        has_tabs = True
                        break
                    except ValueError:
                        continue

    # Second pass: extract parameter names
    with open(param_names_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if has_tabs:
                # Tabular format: only process tab-delimited lines with numeric first column
                if '\t' in line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        try:
                            int(parts[0])  # Check if first column is a number
                            # Use column 2 (short name with PFT suffix) e.g., "alpha_ptase_7"
                            short_name = parts[2].strip()
                            if short_name and not short_name.startswith('Symbol'):
                                names.append(short_name)
                        except ValueError:
                            continue
            else:
                # Simple format: one parameter name per line
                parts = line.split()
                if parts:
                    first_word = parts[0]
                    # Must contain underscore to be a parameter name
                    if '_' in first_word and first_word[0].isalpha():
                        names.append(first_word)
    return names


def load_param_bounds(bounds_file: str) -> List[Tuple[float, float]]:
    """
    Load parameter bounds from a SALib problem file or bounds file.

    Supports formats:
    1. SALib format: "  1. param_name    [lower, upper]"
    2. Simple format: "lower upper" per line
    3. Tabular format: "No<TAB>Name<TAB>ShortName<TAB>Lower<TAB>Upper<TAB>..."

    Args:
        bounds_file: Path to file with bounds

    Returns:
        List of (lower, upper) tuples
    """
    import re
    # docs/37 CSV → bounds straight from the loader (column order = canonical order).
    if _is_new_param_list(bounds_file):
        from tools.param_spec import load_param_spec
        return [(s.lower, s.upper) for s in load_param_spec(bounds_file)]

    bounds = []

    with open(bounds_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Try SALib format: [lower, upper] in brackets
            bracket_match = re.search(r'\[([-\d.eE+]+),\s*([-\d.eE+]+)\]', line)
            if bracket_match:
                try:
                    lower = float(bracket_match.group(1))
                    upper = float(bracket_match.group(2))
                    bounds.append((lower, upper))
                    continue
                except ValueError:
                    pass

            # Try tabular format: No<TAB>...<TAB>Lower<TAB>Upper<TAB>...
            if '\t' in line:
                parts = line.split('\t')
                if len(parts) >= 5:
                    try:
                        int(parts[0])  # Check first column is a number
                        lower = float(parts[3])
                        upper = float(parts[4])
                        bounds.append((lower, upper))
                        continue
                    except (ValueError, IndexError):
                        pass

            # Try simple format: lower upper
            parts = line.split()
            if len(parts) >= 2:
                try:
                    lower = float(parts[0])
                    upper = float(parts[1])
                    bounds.append((lower, upper))
                except ValueError:
                    continue

    return bounds


def read_case_parameters(
    case_id: int,
    morris_file: str,
    param_names: Union[List[str], str],
    param_bounds: Optional[Union[List[Tuple[float, float]], str]] = None
) -> Dict[str, float]:
    """
    Read all parameter values for a specific Morris ensemble case.

    Args:
        case_id: Case number (1-indexed, e.g., 2678)
        morris_file: Path to Morris ensemble parameter file (tab/space delimited)
        param_names: List of parameter names OR path to file with names
        param_bounds: Optional bounds for normalization info

    Returns:
        Dict mapping parameter name to value, e.g.:
        {
            'l2fr_ini_9': 1.0,
            'pid_kp_10': 0.001,
            ...
        }
    """
    # Load parameter names if given as file path
    if isinstance(param_names, str):
        param_names = load_param_names(param_names)

    # Load Morris parameter matrix
    morris_params = np.loadtxt(morris_file)

    # Validate case ID
    n_cases = morris_params.shape[0]
    if case_id < 1 or case_id > n_cases:
        raise ValueError(f"Invalid case_id {case_id}. Must be between 1 and {n_cases}")

    # Convert to 0-indexed
    case_idx = case_id - 1
    case_values = morris_params[case_idx, :]

    # Validate dimensions
    if len(param_names) != len(case_values):
        logger.warning(
            f"Parameter count mismatch: {len(param_names)} names vs "
            f"{len(case_values)} values. Using min of both."
        )

    # Build result dict
    n_params = min(len(param_names), len(case_values))
    result = {}
    for i in range(n_params):
        name = param_names[i].strip()
        result[name] = float(case_values[i])

    return result


def get_parameter_for_case(
    case_id: int,
    parameter_name: str,
    morris_file: str,
    param_names: Union[List[str], str]
) -> float:
    """
    Get a single parameter value for a specific case.

    Args:
        case_id: Case number (1-indexed)
        parameter_name: Name of parameter to get
        morris_file: Path to Morris ensemble file
        param_names: List of parameter names or path to file

    Returns:
        Parameter value

    Raises:
        KeyError: If parameter not found
    """
    params = read_case_parameters(case_id, morris_file, param_names)

    # Try exact match first
    if parameter_name in params:
        return params[parameter_name]

    # Try stripping whitespace
    parameter_name = parameter_name.strip()
    if parameter_name in params:
        return params[parameter_name]

    # Try case-insensitive match
    for name, value in params.items():
        if name.lower() == parameter_name.lower():
            return value

    raise KeyError(f"Parameter '{parameter_name}' not found in case {case_id}")


def read_parameter_file(
    param_file: str,
    parameters: List[str],
    pft: Optional[int] = None
) -> Dict[str, float]:
    """
    Read specific parameters from a FATES NetCDF parameter file.

    Args:
        param_file: Path to FATES parameter NetCDF file
        parameters: List of parameter names to read
        pft: Optional PFT ID (1-indexed) to extract for PFT-dimensioned params

    Returns:
        Dict mapping parameter name to value
    """
    try:
        import netCDF4 as nc
    except ImportError:
        logger.error("netCDF4 required for reading parameter files")
        return {}

    result = {}

    with nc.Dataset(param_file, 'r') as ds:
        for param_name in parameters:
            nc_name = param_name
            # docs/37 canonical_id (fates_name#p{pft}#o{organ}) → the fates variable + its pft.
            if '#' in param_name:
                segs = param_name.split('#')
                nc_name = segs[0]
                for seg in segs[1:]:
                    if seg.startswith('p') and seg[1:].isdigit():
                        pft = int(seg[1:])
            # Handle shorthand names (e.g., "l2fr_ini_9" -> "fates_alloc_l2fr_ini")
            # Try with fates_ prefix first
            elif not nc_name.startswith('fates_'):
                # Check if there's a PFT suffix
                if param_name[-1].isdigit() and '_' in param_name:
                    # Extract base name and PFT
                    parts = param_name.rsplit('_', 1)
                    base_name = parts[0]
                    param_pft = int(parts[1])

                    # Try various prefixes
                    for prefix in ['fates_', 'fates_cnp_', 'fates_alloc_', 'fates_leaf_']:
                        test_name = prefix + base_name
                        if test_name in ds.variables:
                            nc_name = test_name
                            pft = param_pft
                            break

            if nc_name not in ds.variables:
                logger.warning(f"Parameter {param_name} (tried {nc_name}) not found in file")
                continue

            var = ds.variables[nc_name]

            # Check dimensions
            if 'fates_pft' in var.dimensions:
                if pft is not None:
                    # Extract value for specific PFT (0-indexed in file)
                    pft_idx = pft - 1
                    value = float(var[pft_idx])
                else:
                    # Return array as list
                    value = var[:].tolist()
            else:
                value = float(var[:])

            result[param_name] = value

    return result


def get_parameters_with_bounds(
    case_id: int,
    morris_file: str,
    param_names: Union[List[str], str],
    param_bounds: Union[List[Tuple[float, float]], str]
) -> Dict[str, Dict]:
    """
    Get parameters with their bounds and position within range.

    Args:
        case_id: Case number (1-indexed)
        morris_file: Path to Morris ensemble file
        param_names: Parameter names or file path
        param_bounds: Parameter bounds or file path

    Returns:
        Dict with detailed info per parameter:
        {
            'l2fr_ini_9': {
                'value': 1.0,
                'lower': 0.01,
                'upper': 2.96,
                'position': 0.34,  # 0-1 normalized position
                'at_lower': False,
                'at_upper': False
            },
            ...
        }
    """
    # Load names and bounds
    if isinstance(param_names, str):
        param_names = load_param_names(param_names)
    if isinstance(param_bounds, str):
        param_bounds = load_param_bounds(param_bounds)

    # Get case values
    params = read_case_parameters(case_id, morris_file, param_names)

    result = {}
    for i, (name, value) in enumerate(params.items()):
        if i < len(param_bounds):
            lower, upper = param_bounds[i]
            param_range = upper - lower

            if param_range > 0:
                position = (value - lower) / param_range
            else:
                position = 0.5

            result[name] = {
                'value': value,
                'lower': lower,
                'upper': upper,
                'position': position,
                'at_lower': position < 0.01,  # Within 1% of lower
                'at_upper': position > 0.99   # Within 1% of upper
            }
        else:
            result[name] = {
                'value': value,
                'lower': None,
                'upper': None,
                'position': None,
                'at_lower': False,
                'at_upper': False
            }

    return result


def main():
    """CLI interface for reading case parameters."""
    parser = argparse.ArgumentParser(
        description="Read parameter values from Morris ensemble cases"
    )
    parser.add_argument('--case-id', type=int, required=True,
                        help='Case number (1-indexed)')
    parser.add_argument('--morris-file', required=True,
                        help='Path to Morris parameter file')
    parser.add_argument('--param-names-file', required=True,
                        help='Path to parameter names file')
    parser.add_argument('--param-bounds-file',
                        help='Path to parameter bounds file (optional)')
    parser.add_argument('--output', '-o',
                        help='Output JSON file (default: stdout)')
    parser.add_argument('--parameter', '-p',
                        help='Get single parameter value')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.parameter:
        # Get single parameter
        value = get_parameter_for_case(
            args.case_id,
            args.parameter,
            args.morris_file,
            args.param_names_file
        )
        print(f"{args.parameter}: {value}")
    else:
        # Get all parameters
        if args.param_bounds_file:
            result = get_parameters_with_bounds(
                args.case_id,
                args.morris_file,
                args.param_names_file,
                args.param_bounds_file
            )
        else:
            result = read_case_parameters(
                args.case_id,
                args.morris_file,
                args.param_names_file
            )

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Parameters written to: {args.output}")
        else:
            print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
