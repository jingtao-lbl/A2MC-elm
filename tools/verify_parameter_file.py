#!/usr/bin/env python3
"""
Verify FATES Parameter File Against Ensemble Matrix

Extracts parameter values from a NetCDF parameter file and compares
with the corresponding row in the ensemble matrix file.

This script parses the parameter list file directly to ensure correct ordering.

Configuration is loaded from environment variables (source a2mc_config.sh).

Usage:
    python verify_parameter_file.py --ensemble 1
    python verify_parameter_file.py --ensemble 100 --verbose
    python verify_parameter_file.py --sample 20  # Check 20 random files

Created: December 30, 2025
"""

import argparse
import netCDF4 as nc
import numpy as np
from pathlib import Path
import os

# Import configuration - auto-detects HPC vs local
try:
    from config import config
    ENSEMBLE_MATRIX_FILE = config.ENSEMBLE_MATRIX_FILE
    PARAM_LIST_FILE = config.PARAM_LIST_FILE
    PARAM_FILE_DIR = config.PARAM_DIR
    TOTAL_ENSEMBLE = config.TOTAL_ENSEMBLE
except ImportError:
    # Fallback to environment variables
    ENSEMBLE_MATRIX_FILE = os.environ.get('A2MC_ENSEMBLE_MATRIX_FILE', '')
    PARAM_LIST_FILE = os.environ.get('A2MC_PARAM_LIST_FILE', '')
    PARAM_FILE_DIR = os.environ.get('A2MC_PARAM_DIR', '')
    TOTAL_ENSEMBLE = int(os.environ.get('A2MC_TOTAL_ENSEMBLE', '0'))


def parse_parameter_list():
    """
    Parse the parameter list file to get the exact ordering and mapping.

    Returns:
    --------
    list of dict: Each dict contains:
        - col: 1-based column number
        - fates_name: FATES variable name
        - short_name: short parameter name
        - pft: PFT number (7, 9, 10) or None
        - organ: 'leaf' or 'fineroot' or None
    """
    params = []

    with open(PARAM_LIST_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('\t')
            if len(parts) < 4:
                continue

            try:
                col = int(parts[0])
            except ValueError:
                continue

            fates_name = parts[1]
            short_name = parts[2]

            # Determine PFT from short_name
            pft = None
            if short_name.endswith('_7'):
                pft = 7
            elif short_name.endswith('_9'):
                pft = 9
            elif short_name.endswith('_10'):
                pft = 10

            # Determine organ from short_name
            organ = None
            if 'stoich_nitr_leaf' in short_name or 'stoich_phos_leaf' in short_name:
                organ = 'leaf'
            elif 'stoich_nitr_fineroot' in short_name or 'stoich_phos_fineroot' in short_name:
                organ = 'fineroot'

            params.append({
                'col': col,
                'fates_name': fates_name,
                'short_name': short_name,
                'pft': pft,
                'organ': organ
            })

    return params


def extract_value_from_nc(ds, param_info):
    """
    Extract a parameter value from NetCDF file based on param_info.

    Returns:
    --------
    tuple: (value, error_message)
        - value: float if successful, None if failed
        - error_message: None if successful, str if failed
    """
    fates_name = param_info['fates_name']
    pft = param_info['pft']
    organ = param_info['organ']
    short_name = param_info['short_name']

    if fates_name not in ds.variables:
        return None, f"not found: {fates_name}"

    var = ds.variables[fates_name]
    pft_idx = pft - 1 if pft else None

    try:
        # Scalar variable
        if len(var.shape) == 0:
            return float(var[:]), None

        # 1D variable (fates_pft)
        elif len(var.shape) == 1:
            if pft_idx is not None:
                return float(var[pft_idx]), None
            else:
                # Scalar stored as 1D array with single element
                return float(var[0]), None

        # 2D variable
        elif len(var.shape) == 2:
            dim_names = var.dimensions

            # (fates_plant_organs, fates_pft) - stoich and retrans parameters
            if 'fates_plant_organs' in dim_names and 'fates_pft' in dim_names:
                organ_dim = dim_names.index('fates_plant_organs')

                # Determine organ index
                if organ == 'leaf':
                    organ_idx = 0
                elif organ == 'fineroot':
                    organ_idx = 1
                else:
                    organ_idx = 0  # Default to leaf for retrans

                if organ_dim == 0:
                    return float(var[organ_idx, pft_idx]), None
                else:
                    return float(var[pft_idx, organ_idx]), None

            # (fates_leafage_class, fates_pft) - vcmax25top, turnover_leaf
            elif 'fates_leafage_class' in dim_names and 'fates_pft' in dim_names:
                leafage_dim = dim_names.index('fates_leafage_class')
                if leafage_dim == 0:
                    return float(var[0, pft_idx]), None
                else:
                    return float(var[pft_idx, 0]), None

            else:
                return None, f"unknown 2D dims: {dim_names}"

    except Exception as e:
        return None, str(e)

    return None, "unknown shape"


def verify_parameter_file(ensemble_num, ensemble_data, param_list, verbose=False):
    """
    Verify a single parameter file against ensemble matrix.

    Returns:
    --------
    tuple: (n_matched, n_mismatched, n_skipped, mismatches)
    """
    # Try to find the parameter file - support multiple naming patterns
    param_file = None
    patterns = [
        f"fates_params_*_En{ensemble_num}.nc",
        f"*_En{ensemble_num}.nc",
    ]
    for pattern in patterns:
        matches = list(Path(PARAM_FILE_DIR).glob(pattern))
        if matches:
            param_file = matches[0]
            break

    if param_file is None:
        param_file = Path(PARAM_FILE_DIR) / f"fates_params_En{ensemble_num}.nc"

    if not param_file.exists():
        print(f"ERROR: Parameter file not found: {param_file}")
        return 0, 0, 0, []

    # Get ensemble row (0-based indexing)
    ensemble_row = ensemble_data[ensemble_num - 1, :]

    n_matched = 0
    n_mismatched = 0
    n_skipped = 0
    mismatches = []

    with nc.Dataset(param_file, 'r') as ds:
        for param_info in param_list:
            col = param_info['col']
            short_name = param_info['short_name']
            expected = ensemble_row[col - 1]  # col is 1-based

            actual, error = extract_value_from_nc(ds, param_info)

            if actual is None:
                n_skipped += 1
                if verbose:
                    print(f"  SKIP [{col:3d}] {short_name}: {error}")
                continue

            # Compare values with tolerance
            if np.isclose(expected, actual, rtol=1e-5, atol=1e-10):
                n_matched += 1
                if verbose:
                    print(f"  OK   [{col:3d}] {short_name}: {actual:.6e} == {expected:.6e}")
            else:
                n_mismatched += 1
                mismatches.append((col, short_name, expected, actual))
                if verbose:
                    print(f"  FAIL [{col:3d}] {short_name}: {actual:.6e} != {expected:.6e}")

    return n_matched, n_mismatched, n_skipped, mismatches


def main():
    parser = argparse.ArgumentParser(description='Verify FATES parameter files against ensemble matrix')
    parser.add_argument('--ensemble', '-e', type=int, help='Ensemble number to verify')
    parser.add_argument('--sample', '-s', type=int, default=0, help='Sample N random files')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')

    args = parser.parse_args()

    if not args.ensemble and args.sample == 0:
        parser.error("Must specify --ensemble N or --sample N")

    # Verify configuration
    if not ENSEMBLE_MATRIX_FILE:
        print("ERROR: A2MC_ENSEMBLE_MATRIX_FILE not set. Source config first.")
        return
    if not PARAM_LIST_FILE:
        print("ERROR: A2MC_PARAM_LIST_FILE not set. Source config first.")
        return

    # Parse parameter list
    print("Parsing parameter list...")
    param_list = parse_parameter_list()
    print(f"  Found {len(param_list)} parameters")

    # Load ensemble matrix
    print("Loading ensemble matrix...")
    ensemble_data = np.loadtxt(ENSEMBLE_MATRIX_FILE)
    print(f"  Loaded: {ensemble_data.shape[0]} sets × {ensemble_data.shape[1]} parameters")

    print("\n" + "=" * 80)
    print("PARAMETER FILE VERIFICATION")
    print("=" * 80)

    if args.ensemble:
        # Verify single file
        print(f"\nVerifying ensemble {args.ensemble}...")
        n_matched, n_mismatched, n_skipped, mismatches = verify_parameter_file(
            args.ensemble, ensemble_data, param_list, verbose=args.verbose
        )

        print(f"\n--- Results for Ensemble {args.ensemble} ---")
        print(f"  Matched:    {n_matched}")
        print(f"  Mismatched: {n_mismatched}")
        print(f"  Skipped:    {n_skipped}")

        if mismatches:
            print("\n  Mismatches:")
            for col, name, expected, actual in mismatches:
                print(f"    [{col:3d}] {name}: expected {expected:.6e}, got {actual:.6e}")

        status = "PASS" if n_mismatched == 0 and n_skipped == 0 else "FAIL"
        print(f"\n  Status: {status}")

    elif args.sample > 0:
        # Sample random files - use ensemble size from data
        n_total = ensemble_data.shape[0]
        ensembles = sorted(np.random.choice(range(1, n_total + 1), size=min(args.sample, n_total), replace=False))

        print(f"\nVerifying {len(ensembles)} random files...")

        total_matched = 0
        total_mismatched = 0
        total_skipped = 0
        files_with_issues = []

        for en in ensembles:
            n_matched, n_mismatched, n_skipped, mismatches = verify_parameter_file(
                en, ensemble_data, param_list, verbose=False
            )

            total_matched += n_matched
            total_mismatched += n_mismatched
            total_skipped += n_skipped

            if mismatches or n_skipped > 0:
                files_with_issues.append((en, n_matched, n_mismatched, n_skipped, mismatches))

            if args.verbose or n_mismatched > 0:
                status = "PASS" if n_mismatched == 0 and n_skipped == 0 else "FAIL"
                print(f"  En{en}: matched={n_matched}, mismatched={n_mismatched}, skipped={n_skipped} [{status}]")

        print(f"\n--- Summary for {len(ensembles)} files ---")
        print(f"  Total matched:    {total_matched}")
        print(f"  Total mismatched: {total_mismatched}")
        print(f"  Total skipped:    {total_skipped}")

        if files_with_issues and total_mismatched > 0:
            print(f"\n  Files with mismatches: {len([f for f in files_with_issues if f[2] > 0])}")
            for en, matched, mismatched, skipped, mismatches in files_with_issues[:5]:
                if mismatched > 0:
                    print(f"    Ensemble {en}:")
                    for col, name, expected, actual in mismatches[:3]:
                        print(f"      [{col:3d}] {name}: expected {expected:.6e}, got {actual:.6e}")

        status = "PASS" if total_mismatched == 0 and total_skipped == 0 else "FAIL"
        print(f"\n  Overall Status: {status}")


if __name__ == '__main__':
    main()
