#!/usr/bin/env python3
"""
FATES Parameter Modification Tool

Modifies specific parameters in a FATES parameter NetCDF file and creates a new file.
Supports both absolute values and percentage changes.

Usage:
    python modify_fates_parameters.py --input input.nc --output output.nc --param param_name --pft 10 --value 0.5
    python modify_fates_parameters.py --input input.nc --output output.nc --param param_name --pft 10 --percent +40

Notes: For non-PFT-dependent (global) parameters, use --pft 0
Example:
Or use the config file method:
    python modify_fates_parameters.py --input input.nc --output output.nc --config modifications.yaml

    python modify_fates_parameters.py \
    --input /Users/jingtao/Desktop/Work/NGEE-Arctic/Kougarok/FATESparameterfiles/fates_params_NonPrescribed_EnPlantTraitsCNPparam138_Morris/fates_params_api25.5.0_12pft_c230710__PtCNP_En3643_mod4.nc \
    --output /Users/jingtao/Desktop/Work/NGEE-Arctic/Kougarok/FATESparameterfiles/fates_params_NonPrescribed_EnPlantTraitsCNPparam138_Morris/fates_params_api25.5.0_12pft_c230710__PtCNP_En3643_mod5a.nc \
     --param fates_alloc_storage_cushion \
     --pft 10 \
     --value 3.0 \
     --verify

Created: December 9, 2025
"""

import argparse
import logging
import netCDF4 as nc
import numpy as np
import re
import shutil
import sys
from pathlib import Path

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


def resolve_parameter_name(name, pft=None, organ=None, param_lookup=None):
    """
    Resolve a parameter name (shorthand or full) to (fates_name, pft, organ).

    Resolution order:
    1. If name is in param_lookup → use lookup values (shorthand resolution)
    2. If name starts with 'fates_' → pass through as full name
    3. Otherwise → return as-is (caller will get a clear NetCDF error)

    Explicit pft/organ arguments override lookup values when provided.

    Args:
        name: Parameter name (shorthand like 'vmax_ptase_10' or full like 'fates_cnp_eca_vmax_ptase')
        pft: Explicit PFT index (overrides lookup if not None)
        organ: Explicit organ index (overrides lookup if not None)
        param_lookup: Dict from build_param_lookup(), or None to skip lookup

    Returns:
        tuple: (fates_name, pft, organ) where pft is int (0=global) and organ is int or None
    """
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

    Parameters:
    -----------
    input_file : str or Path
        Path to input NetCDF parameter file
    output_file : str or Path
        Path to output NetCDF parameter file
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


def verify_modifications(nc_file, expected_modifications, verbose=True):
    """
    Verify that modifications were applied correctly.

    Parameters:
    -----------
    nc_file : str or Path
        Path to modified NetCDF file
    expected_modifications : list of dict
        Expected modifications (same format as create_modified_parameter_file)
    verbose : bool
        Print verification results

    Returns:
    --------
    all_correct : bool
        True if all modifications verified correctly
    """
    if verbose:
        print(f"\nVerifying modifications in {Path(nc_file).name}:")

    with nc.Dataset(nc_file, 'r') as ncfile:
        all_correct = True
        for mod in expected_modifications:
            param = mod['param']
            pft = mod.get('pft', 0)
            expected_value = mod.get('expected_value', None)

            # Get array index (0-based)
            array_index = (pft - 1) if pft > 0 else None

            # Get variable
            var = ncfile.variables[param]

            # Get actual value
            if array_index is not None:
                actual_value = float(var[array_index])
            else:
                actual_value = float(var[:])

            # Check if matches expected
            if expected_value is not None:
                is_correct = np.isclose(actual_value, expected_value, rtol=1e-6)
                status = "✓" if is_correct else "✗"

                if verbose:
                    print(f"  {status} {param}[PFT {pft}]: {actual_value:.6e} (expected: {expected_value:.6e})")

                if not is_correct:
                    all_correct = False
            else:
                if verbose:
                    print(f"  ℹ {param}[PFT {pft}]: {actual_value:.6e} (not verified)")

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
  # Increase storage cushion by 40% for PFT 10
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
