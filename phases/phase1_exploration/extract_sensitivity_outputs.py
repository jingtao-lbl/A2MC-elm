#!/usr/bin/env python3
"""
Extract Y Matrix (Model Outputs) for Morris Sensitivity Analysis

Phase 1: EXPLORATION - Extract aggregated outputs from ensemble simulations.

This script extracts biomass and other outputs from completed ELM-FATES simulations
and aggregates them into Y matrices suitable for SALib Morris analysis.

Output Format:
    Each output file is a text matrix with shape (n_cases × n_pfts):
    - Row i = Case i (ensemble member)
    - Column j = PFT j (e.g., PFT7, PFT9, PFT10)

Aggregation Modes:
    - last_n_years: Mean of last N years of simulation (default: last 10)
    - validation_period: Mean over specified year range (e.g., 2010-2019)
    - observation_years: Mean of specific years when observations were collected
    - observation_months: Values at exact observation year-months (for RMSRE)

Usage:
    # Extract last 10-year mean (default)
    python extract_sensitivity_outputs.py --output-var leaf_biomass --cases 1-4890

    # Extract mean over specific validation period
    python extract_sensitivity_outputs.py --output-var fineroot_biomass \\
        --validation-period 2010 2019 --cases 1-4890

    # Extract at observation months (for exact comparison)
    python extract_sensitivity_outputs.py --output-var leaf_biomass \\
        --observation-months "2016-07,2017-07,2018-07" --cases 1-4890

    # Resume from last completed case
    python extract_sensitivity_outputs.py --output-var leaf_biomass \\
        --resume --cases 1-4890

Author: Jing Tao, A2MC Framework
Date: 2026-01-19
"""

import argparse
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
import numpy as np

# Try to import xarray (may not be available on all systems)
try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False
    print("Warning: xarray not available, using netCDF4 directly")

try:
    import netCDF4 as nc
    HAS_NETCDF4 = True
except ImportError:
    HAS_NETCDF4 = False

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from tools.config import config
except ImportError:
    config = None
    print("Warning: A2MC config not available")

try:
    from tools.fates_output_variables import OUTPUT_VARIABLES
    from tools.fates_utils import get_szpf_range, N_SIZE_CLASSES
except ImportError:
    OUTPUT_VARIABLES = None
    print("Warning: Could not import fates_output_variables or fates_utils")


# =============================================================================
# CONFIGURATION
# =============================================================================

# Default PFT configuration (Kougarok: Arctic tundra with 3 PFTs)
DEFAULT_PFTS = {
    'PFT7': {'index': 6, 'name': 'Evergreen_Shrub'},
    'PFT9': {'index': 8, 'name': 'Deciduous_Shrub'},
    'PFT10': {'index': 9, 'name': 'Arctic_Graminoid'},
}

N_PFTS_FATES = 12  # Total PFTs in FATES parameter file


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_case_range(case_spec: str) -> List[int]:
    """
    Parse case specification into list of case numbers.

    Supports:
    - Single number: "123"
    - Range: "1-100"
    - Comma-separated: "1,5,10,20"
    - Mixed: "1-10,15,20-30"
    """
    cases = []
    for part in case_spec.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-')
            cases.extend(range(int(start), int(end) + 1))
        else:
            cases.append(int(part))
    return sorted(set(cases))


def get_szpf_indices_for_pft(pft_id: int, n_size_classes: int = 13) -> Tuple[int, int]:
    """Get SZPF index range for a PFT. Delegates to tools.fates_utils.get_szpf_range."""
    return get_szpf_range(pft_id)


def get_case_path(case_num: int, ensemble_output: str, case_prefix: str,
                  phase: str = 'TRANS') -> Path:
    """Get path to case output directory."""
    pattern = os.environ.get('A2MC_CASE_NAME_PATTERN', f"{case_prefix}{{N}}_{{PHASE}}")
    case_name = pattern.format(N=case_num, PHASE=phase)
    return Path(ensemble_output) / case_name / 'run'


def find_history_files(case_dir: Path, case_name: str,
                       start_year: int, end_year: int) -> List[Path]:
    """Find all monthly history files for a case within year range."""
    files = []
    for year in range(start_year, end_year + 1):
        # Pattern: case.elm.h0.YYYY-MM-DD-00000.nc
        year_files = sorted(case_dir.glob(f'{case_name}.elm.h0.{year:04d}-??-??-00000.nc'))
        files.extend(year_files)
    return sorted(files)


# =============================================================================
# EXTRACTION FUNCTIONS
# =============================================================================

def extract_variable_from_case(
    case_num: int,
    var_config: Dict,
    pfts: Dict,
    ensemble_output: str,
    case_prefix: str,
    start_year: int,
    end_year: int,
    aggregation: str = 'mean',
    observation_months: Optional[List[str]] = None
) -> Optional[np.ndarray]:
    """
    Extract and aggregate a variable from a single case.

    Args:
        case_num: Case number
        var_config: Variable configuration dict
        pfts: PFT configuration dict
        ensemble_output: Path to ensemble output directory
        case_prefix: Case name prefix
        start_year: Start year for extraction
        end_year: End year for extraction
        aggregation: 'mean', 'sum', or 'last'
        observation_months: List of YYYY-MM strings for exact extraction

    Returns:
        Array of shape (n_pfts,) with aggregated values, or None if failed
    """
    pattern = os.environ.get('A2MC_CASE_NAME_PATTERN', f"{case_prefix}{{N}}_{{PHASE}}")
    case_name = pattern.format(N=case_num, PHASE='TRANS')
    case_dir = Path(ensemble_output) / case_name / 'run'

    if not case_dir.exists():
        return None

    # Find history files
    history_files = find_history_files(case_dir, case_name, start_year, end_year)
    if not history_files:
        return None

    # Determine which variable to extract (prefer PFT-level, fallback to SZPF)
    pft_var = var_config.get('pft_var')
    szpf_var = var_config.get('szpf_var')
    site_var = var_config.get('site_var')

    # Initialize result array
    n_pfts = len(pfts)
    pft_values = np.full(n_pfts, np.nan)

    try:
        # Open files and extract data
        all_data = []
        all_times = []

        for file_path in history_files:
            if HAS_XARRAY:
                ds = xr.open_dataset(file_path, decode_times=False)

                # Try to extract PFT-level variable
                if pft_var and pft_var in ds.variables:
                    # Shape: (time, fates_levpft, lndgrid)
                    data = ds[pft_var].values
                    for i, (pft_name, pft_info) in enumerate(pfts.items()):
                        pft_idx = pft_info['index']
                        if data.ndim == 3:
                            all_data.append(data[:, pft_idx, 0])
                        elif data.ndim == 2:
                            all_data.append(data[:, pft_idx])

                # Fallback to SZPF variable
                elif szpf_var and szpf_var in ds.variables:
                    # Shape: (time, fates_levscpf, lndgrid)
                    szpf_data = ds[szpf_var].values

                    for i, (pft_name, pft_info) in enumerate(pfts.items()):
                        pft_id = int(pft_name.replace('PFT', ''))
                        start_idx, end_idx = get_szpf_indices_for_pft(pft_id)

                        if szpf_data.ndim == 3:
                            # Sum across size classes
                            pft_sum = np.nansum(szpf_data[:, start_idx:end_idx+1, 0], axis=1)
                        else:
                            pft_sum = np.nansum(szpf_data[:, start_idx:end_idx+1], axis=1)

                        if i == 0:
                            all_data = [[] for _ in range(n_pfts)]
                        all_data[i].extend(pft_sum.tolist())

                ds.close()

            elif HAS_NETCDF4:
                # Direct netCDF4 access
                ds = nc.Dataset(str(file_path), 'r')

                if pft_var and pft_var in ds.variables:
                    data = ds.variables[pft_var][:]
                    for i, (pft_name, pft_info) in enumerate(pfts.items()):
                        pft_idx = pft_info['index']
                        if i >= len(all_data):
                            all_data.append([])
                        if data.ndim == 3:
                            all_data[i].extend(data[:, pft_idx, 0].tolist())
                        elif data.ndim == 2:
                            all_data[i].extend(data[:, pft_idx].tolist())

                elif szpf_var and szpf_var in ds.variables:
                    szpf_data = ds.variables[szpf_var][:]

                    for i, (pft_name, pft_info) in enumerate(pfts.items()):
                        pft_id = int(pft_name.replace('PFT', ''))
                        start_idx, end_idx = get_szpf_indices_for_pft(pft_id)

                        if i >= len(all_data):
                            all_data.append([])

                        if szpf_data.ndim == 3:
                            pft_sum = np.nansum(szpf_data[:, start_idx:end_idx+1, 0], axis=1)
                        else:
                            pft_sum = np.nansum(szpf_data[:, start_idx:end_idx+1], axis=1)

                        all_data[i].extend(pft_sum.tolist())

                ds.close()

        # Aggregate across time
        if all_data:
            for i in range(n_pfts):
                if isinstance(all_data[i], list) and len(all_data[i]) > 0:
                    data_array = np.array(all_data[i])
                    if aggregation == 'mean':
                        pft_values[i] = np.nanmean(data_array)
                    elif aggregation == 'sum':
                        pft_values[i] = np.nansum(data_array)
                    elif aggregation == 'last':
                        pft_values[i] = data_array[-1]
                elif isinstance(all_data[i], np.ndarray):
                    if aggregation == 'mean':
                        pft_values[i] = np.nanmean(all_data[i])
                    elif aggregation == 'sum':
                        pft_values[i] = np.nansum(all_data[i])
                    elif aggregation == 'last':
                        pft_values[i] = all_data[i][-1]

        return pft_values

    except Exception as e:
        print(f"    Error extracting case {case_num}: {e}")
        return None


def extract_ensemble_outputs(
    output_var: str,
    cases: List[int],
    ensemble_output: str,
    case_prefix: str,
    pfts: Dict,
    start_year: int = 2010,
    end_year: int = 2019,
    aggregation: str = 'mean',
    output_file: Optional[str] = None,
    resume: bool = False,
    progress_file: Optional[str] = None
) -> np.ndarray:
    """
    Extract outputs for all cases in ensemble.

    Args:
        output_var: Variable name (e.g., 'leaf_biomass')
        cases: List of case numbers
        ensemble_output: Path to ensemble output directory
        case_prefix: Case name prefix
        pfts: PFT configuration dict
        start_year: Start year for aggregation
        end_year: End year for aggregation
        aggregation: Aggregation method
        output_file: Path to save Y matrix
        resume: Resume from progress file if exists
        progress_file: Path to progress tracking file

    Returns:
        Y matrix with shape (n_cases, n_pfts)
    """
    if output_var not in OUTPUT_VARIABLES:
        raise ValueError(f"Unknown output variable: {output_var}")

    var_config = OUTPUT_VARIABLES[output_var]
    n_cases = len(cases)
    n_pfts = len(pfts)

    # Initialize Y matrix
    Y = np.full((n_cases, n_pfts), np.nan)

    # Check for resume
    start_idx = 0
    if resume and progress_file and Path(progress_file).exists():
        try:
            Y_partial = np.loadtxt(progress_file)
            if Y_partial.shape == (n_cases, n_pfts):
                # Find first row with all NaN
                for i in range(n_cases):
                    if np.all(np.isnan(Y_partial[i, :])):
                        start_idx = i
                        break
                Y = Y_partial
                print(f"Resuming from case index {start_idx} (case #{cases[start_idx]})")
        except Exception as e:
            print(f"Could not resume from progress file: {e}")

    # Extract each case
    print(f"\nExtracting {output_var} for {n_cases} cases...")
    print(f"  Variable: {var_config['description']}")
    print(f"  Period: {start_year}-{end_year}")
    print(f"  Aggregation: {aggregation}")
    print(f"  PFTs: {list(pfts.keys())}")
    print()

    successful = 0
    failed = 0

    for i, case_num in enumerate(cases):
        if i < start_idx:
            if not np.all(np.isnan(Y[i, :])):
                successful += 1
            continue

        # Progress indicator
        if (i + 1) % 100 == 0 or i == 0:
            print(f"  Processing case {i+1}/{n_cases} (case #{case_num})...")

        result = extract_variable_from_case(
            case_num=case_num,
            var_config=var_config,
            pfts=pfts,
            ensemble_output=ensemble_output,
            case_prefix=case_prefix,
            start_year=start_year,
            end_year=end_year,
            aggregation=aggregation
        )

        if result is not None:
            Y[i, :] = result
            successful += 1
        else:
            failed += 1

        # Save progress periodically
        if progress_file and (i + 1) % 500 == 0:
            np.savetxt(progress_file, Y, fmt='%.10e')
            print(f"    Progress saved ({successful} successful, {failed} failed)")

    # Save final output
    if output_file:
        np.savetxt(output_file, Y, fmt='%.10e')
        print(f"\nSaved Y matrix: {output_file}")

    print(f"\nExtraction complete:")
    print(f"  Successful: {successful}/{n_cases}")
    print(f"  Failed: {failed}/{n_cases}")
    print(f"  NaN rate: {np.sum(np.isnan(Y)) / Y.size * 100:.1f}%")

    return Y


# =============================================================================
# HIGH-LEVEL API FOR ORCHESTRATOR
# =============================================================================

def run_extraction(
    output_vars: List[str] = None,
    cases: List[int] = None,
    start_year: int = 2010,
    end_year: int = 2019,
    aggregation: str = 'mean',
    output_dir: str = None,
    resume: bool = True
) -> Dict[str, Any]:
    """
    Run Y matrix extraction for Morris sensitivity analysis.

    This is the high-level API for calling from the orchestrator.

    Args:
        output_vars: List of variables to extract (default: leaf, fineroot, abg)
        cases: List of case numbers (default: 1 to TOTAL_ENSEMBLE from config)
        start_year: Start year for aggregation
        end_year: End year for aggregation
        aggregation: Aggregation method ('mean', 'sum', 'last')
        output_dir: Directory to save Y matrices (default: from config)
        resume: Resume from progress files if they exist

    Returns:
        Dict with extraction results and file paths
    """
    from tools.config import config as a2mc_config

    # Defaults
    if output_vars is None:
        output_vars = ['leaf_biomass', 'fineroot_biomass', 'abg_biomass']

    if cases is None:
        n_cases = int(a2mc_config.TOTAL_ENSEMBLE)
        cases = list(range(1, n_cases + 1))

    if output_dir is None:
        output_dir = Path(a2mc_config.USE_CASE_DIR) / "memory" / "phase_results" / "phase1_exploration"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get config values
    ensemble_output = a2mc_config.ENSEMBLE_OUTPUT
    case_prefix = a2mc_config.ENSEMBLE_PREFIX

    print("=" * 70)
    print("Y Matrix Extraction for Morris Sensitivity Analysis")
    print("=" * 70)
    print(f"Variables: {output_vars}")
    print(f"Cases: {len(cases)} ({min(cases)} to {max(cases)})")
    print(f"Period: {start_year}-{end_year}")
    print(f"Aggregation: {aggregation}")
    print(f"Ensemble output: {ensemble_output}")
    print(f"Output directory: {output_dir}")
    print("=" * 70)

    results = {
        'status': 'completed',
        'output_vars': output_vars,
        'n_cases': len(cases),
        'period': f"{start_year}-{end_year}",
        'y_matrix_files': {},
        'statistics': {}
    }

    pfts = DEFAULT_PFTS

    for output_var in output_vars:
        print(f"\n--- Extracting {output_var} ---")

        # Output file name
        var_name = output_var.replace('_', '')
        output_file = output_dir / f"Morris{var_name.title()}_{len(cases)}cases_{start_year}_{end_year}.txt"
        progress_file = output_dir / f".progress_{output_var}_{len(cases)}.txt"

        # Check if already extracted
        if output_file.exists() and not resume:
            print(f"  Already exists: {output_file}")
            results['y_matrix_files'][output_var] = str(output_file)
            continue

        try:
            Y = extract_ensemble_outputs(
                output_var=output_var,
                cases=cases,
                ensemble_output=ensemble_output,
                case_prefix=case_prefix,
                pfts=pfts,
                start_year=start_year,
                end_year=end_year,
                aggregation=aggregation,
                output_file=str(output_file),
                resume=resume,
                progress_file=str(progress_file)
            )

            results['y_matrix_files'][output_var] = str(output_file)

            # Compute statistics
            stats = {}
            pft_names = list(pfts.keys())
            for i, pft in enumerate(pft_names):
                col_data = Y[:, i]
                valid = ~np.isnan(col_data)
                stats[pft] = {
                    'n_valid': int(np.sum(valid)),
                    'n_total': len(col_data),
                    'mean': float(np.nanmean(col_data)) if np.any(valid) else None,
                    'std': float(np.nanstd(col_data)) if np.any(valid) else None
                }
            results['statistics'][output_var] = stats

            # Clean up progress file if complete
            valid_rate = 1 - np.sum(np.isnan(Y)) / Y.size
            if valid_rate > 0.95 and progress_file.exists():
                progress_file.unlink()

        except Exception as e:
            print(f"  Error extracting {output_var}: {e}")
            results['status'] = 'partial'
            continue

    print("\n" + "=" * 70)
    print("Extraction Summary")
    print("=" * 70)
    for var, path in results['y_matrix_files'].items():
        print(f"  {var}: {path}")

    return results


# =============================================================================
# MAIN (command-line interface)
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Extract Y matrix for Morris sensitivity analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Extract leaf biomass for all 4890 cases
    python extract_sensitivity_outputs.py --output-var leaf_biomass --cases 1-4890

    # Extract fineroot biomass with specific validation period
    python extract_sensitivity_outputs.py --output-var fineroot_biomass \\
        --validation-period 2010 2019 --cases 1-4890

    # Extract last 5 years mean
    python extract_sensitivity_outputs.py --output-var leaf_biomass \\
        --last-n-years 5 --cases 1-4890

    # Resume interrupted extraction
    python extract_sensitivity_outputs.py --output-var leaf_biomass \\
        --cases 1-4890 --resume

Available output variables:
    leaf_biomass     - Leaf carbon by PFT (FATES_LEAFC_PF or FATES_LEAFC_SZPF)
    fineroot_biomass - Fine root carbon by PFT (FATES_FROOTC_PF or FATES_FROOTC_SZPF)
    abg_biomass      - Aboveground biomass by PFT (FATES_VEGC_ABOVEGROUND_SZPF)
    total_vegc       - Total vegetation carbon by PFT (FATES_VEGC_SZPF)
    gpp              - Gross primary production by PFT (FATES_GPP_PF)
    npp              - Net primary production by PFT (FATES_NPP_SZPF)
    lai              - Leaf area index (site-level only)
        """
    )

    parser.add_argument('--output-var', type=str, required=True,
                        choices=list(OUTPUT_VARIABLES.keys()),
                        help='Output variable to extract')
    parser.add_argument('--cases', type=str, required=True,
                        help='Case numbers (e.g., "1-4890" or "1,5,10,20-30")')
    parser.add_argument('--validation-period', type=int, nargs=2, default=[2010, 2019],
                        metavar=('START', 'END'),
                        help='Year range for aggregation (default: 2010 2019)')
    parser.add_argument('--last-n-years', type=int, default=None,
                        help='Use last N years instead of validation period')
    parser.add_argument('--aggregation', type=str, default='mean',
                        choices=['mean', 'sum', 'last'],
                        help='Aggregation method (default: mean)')
    parser.add_argument('--output-dir', type=str, default='.',
                        help='Directory to save output files')
    parser.add_argument('--output-file', type=str, default=None,
                        help='Output file name (default: Morris{Var}_{n}cases.txt)')
    parser.add_argument('--ensemble-output', type=str, default=None,
                        help='Path to ensemble output directory (default: from config)')
    parser.add_argument('--case-prefix', type=str, default=None,
                        help='Case name prefix (default: from config)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from progress file if exists')
    parser.add_argument('--pft-config', type=str, default=None,
                        help='JSON file with PFT configuration')

    args = parser.parse_args()

    # Parse case numbers
    cases = parse_case_range(args.cases)
    print(f"Cases to process: {len(cases)} (from {min(cases)} to {max(cases)})")

    # Get configuration
    if config is not None and config.is_configured():
        ensemble_output = args.ensemble_output or config.ENSEMBLE_OUTPUT
        case_prefix = args.case_prefix or config.ENSEMBLE_PREFIX
    else:
        ensemble_output = args.ensemble_output
        case_prefix = args.case_prefix

    if not ensemble_output or not case_prefix:
        print("Error: Must provide --ensemble-output and --case-prefix")
        print("       Or source A2MC config: source use_cases/Kougarok/config/kougarok_config.sh")
        sys.exit(1)

    # Determine year range
    if args.last_n_years:
        # Assuming TRANS phase ends at 2019
        end_year = 2019
        start_year = end_year - args.last_n_years + 1
    else:
        start_year, end_year = args.validation_period

    # PFT configuration
    pfts = DEFAULT_PFTS
    if args.pft_config:
        import json
        with open(args.pft_config, 'r') as f:
            pfts = json.load(f)

    # Output file
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.output_file:
        output_file = output_dir / args.output_file
    else:
        var_name = args.output_var.replace('_', '')
        output_file = output_dir / f"Morris{var_name.title()}_{len(cases)}cases_{start_year}_{end_year}.txt"

    progress_file = output_dir / f".progress_{args.output_var}_{len(cases)}.txt"

    print("\n" + "=" * 70)
    print("Extract Y Matrix for Morris Sensitivity Analysis")
    print("=" * 70)
    print(f"Output variable: {args.output_var}")
    print(f"Cases: {len(cases)} ({min(cases)} to {max(cases)})")
    print(f"Year range: {start_year}-{end_year}")
    print(f"Aggregation: {args.aggregation}")
    print(f"Ensemble output: {ensemble_output}")
    print(f"Case prefix: {case_prefix}")
    print(f"Output file: {output_file}")
    print("=" * 70)

    # Extract outputs
    Y = extract_ensemble_outputs(
        output_var=args.output_var,
        cases=cases,
        ensemble_output=ensemble_output,
        case_prefix=case_prefix,
        pfts=pfts,
        start_year=start_year,
        end_year=end_year,
        aggregation=args.aggregation,
        output_file=str(output_file),
        resume=args.resume,
        progress_file=str(progress_file)
    )

    # Print summary statistics
    print("\n" + "=" * 70)
    print("Y Matrix Statistics")
    print("=" * 70)
    pft_names = list(pfts.keys())
    for i, pft in enumerate(pft_names):
        col_data = Y[:, i]
        valid = ~np.isnan(col_data)
        print(f"  {pft}:")
        print(f"    Valid values: {np.sum(valid)}/{len(col_data)}")
        if np.any(valid):
            print(f"    Mean: {np.nanmean(col_data):.6f}")
            print(f"    Std:  {np.nanstd(col_data):.6f}")
            print(f"    Min:  {np.nanmin(col_data):.6f}")
            print(f"    Max:  {np.nanmax(col_data):.6f}")
    print("=" * 70)

    # Clean up progress file if complete
    if progress_file and Path(progress_file).exists():
        valid_rate = 1 - np.sum(np.isnan(Y)) / Y.size
        if valid_rate > 0.95:  # >95% complete
            Path(progress_file).unlink()
            print(f"Removed progress file (extraction complete)")


if __name__ == '__main__':
    main()
