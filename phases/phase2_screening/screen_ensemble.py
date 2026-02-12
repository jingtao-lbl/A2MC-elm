#!/usr/bin/env python3
"""
Screen Ensemble - A2MC Phase 2 Screening Module

Loads ensemble simulation outputs, ranks against validation targets,
and returns structured results for Phase 3 (Diagnosis).

Integrates with:
  - tools/optimize_function.py for ranking
  - tools/cost_functions.py for error metrics
  - tools/phase_logger.py for logging
  - reasoning.py for AI analysis

Usage:
    # As module (from orchestrator)
    from phases.phase2_screening.screen_ensemble import screen_ensemble
    result = screen_ensemble(data_dir, targets, top_n=100)

    # Standalone
    python screen_ensemble.py

Created: Jing Tao with Claude, January 2026
"""

import numpy as np
from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import json
import pickle
import hashlib

# NetCDF support
try:
    import netCDF4 as nc
    HAS_NETCDF = True
except ImportError:
    HAS_NETCDF = False

# A2MC imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from tools.optimize_function import (
        Target, OptimizationConfig, OptimizationResult,
        optimize_ensemble, save_optimization_results
    )
    from tools.cost_functions import CostFunction, ObservationType, aggregate_costs
    from tools.fates_utils import get_szpf_range, aggregate_szpf_by_pft
    from tools.fates_output_variables import resolve_target_name, get_variable_family, VAR_FACTORS
except ImportError as e:
    print(f"Warning: Could not import A2MC tools: {e}")


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ScreeningConfig:
    """Configuration for ensemble screening"""
    # Data location
    data_dir: Path = None
    case_pattern: str = ''  # Set from A2MC_CASE_NAME_PATTERN or default
    file_pattern: str = '{case_name}_all_variables_monthly_{year_start}_{year_end}.nc'

    # Time settings
    year_start: int = 1901
    year_end: int = 2019
    obs_year: int = 2016
    obs_month: int = 7  # July

    # PFT settings
    pfts: List[int] = field(default_factory=lambda: [7, 9, 10])
    pft_names: Dict[int, str] = field(default_factory=lambda: {
        7: 'Evergreen Shrub',
        9: 'Deciduous Shrub',
        10: 'Graminoid'
    })

    # Variables to extract
    variables: List[str] = field(default_factory=lambda: ['FATES_LEAFC_SZPF', 'FATES_FROOTC_SZPF'])
    var_factors: Dict[str, float] = field(default_factory=lambda: {
        'FATES_LEAFC_SZPF': 1000,  # kg/m² to g/m²
        'FATES_FROOTC_SZPF': 1000
    })

    # Optimization settings
    error_method: str = 'relative_error'
    aggregation_method: str = 'rmsre'
    tolerance: float = 0.2
    top_n: int = 100

    def __post_init__(self):
        """Initialize case_pattern from A2MC config if not set."""
        if not self.case_pattern:
            import os
            try:
                from tools.config import config as a2mc_config
                self.case_pattern = a2mc_config.CASE_NAME_PATTERN
                # Debug: show where pattern came from
                env_val = os.environ.get('A2MC_CASE_NAME_PATTERN', '')
                if env_val:
                    print(f"  case_pattern from env: '{env_val}'")
                else:
                    print(f"  case_pattern from default (A2MC_CASE_NAME_PATTERN not set): '{self.case_pattern}'")
                    print(f"    A2MC_ENSEMBLE_PREFIX='{os.environ.get('A2MC_ENSEMBLE_PREFIX', '')}'")
            except ImportError:
                prefix = os.environ.get('A2MC_ENSEMBLE_PREFIX', '')
                self.case_pattern = os.environ.get(
                    'A2MC_CASE_NAME_PATTERN', f"{prefix}{{N}}_{{PHASE}}")

    @property
    def obs_idx(self) -> int:
        """Index of observation timestep (0-based)"""
        return (self.obs_year - self.year_start) * 12 + self.obs_month - 1


@dataclass
class ScreeningResult:
    """Results from ensemble screening"""
    # Core results
    optimization_result: OptimizationResult
    simulated: Dict[str, np.ndarray]

    # Metadata
    n_available_cases: int
    n_valid_cases: int
    case_numbers: List[int]

    # Derived statistics
    best_case_num: int = 0
    best_cost: float = 0.0
    max_satisfied_count: int = 0

    # Analysis results (added by AI)
    ai_analysis: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'n_available_cases': self.n_available_cases,
            'n_valid_cases': self.n_valid_cases,
            'best_case_num': self.best_case_num,
            'best_cost': self.best_cost,
            'max_satisfied_count': self.max_satisfied_count,
            'top_10_cases': self.get_top_cases(10),
            'targets_satisfied_distribution': self.get_satisfied_distribution(),
            'ai_analysis': self.ai_analysis
        }

    def get_top_cases(self, n: int = 10) -> List[Dict]:
        """Get top N cases with details"""
        result = self.optimization_result
        cases = []
        for i, idx in enumerate(result.ranked_indices[:n]):
            case = {
                'rank': i + 1,
                'case_num': self.case_numbers[idx],
                'cost': float(result.composite_cost[idx]),
                'n_satisfied': int(result.n_satisfied[idx]),
                'simulated': {name: float(self.simulated[name][idx])
                             for name in self.simulated.keys()}
            }
            cases.append(case)
        return cases

    def get_satisfied_distribution(self) -> Dict[int, int]:
        """Distribution of targets satisfied"""
        dist = {}
        n_targets = len(self.optimization_result.targets)
        for n in range(n_targets + 1):
            count = int(np.sum(self.optimization_result.n_satisfied == n))
            dist[n] = count
        return dist


# =============================================================================
# Data Loading Functions
# =============================================================================



def get_available_cases(data_dir: Path, config: ScreeningConfig) -> List[int]:
    """Scan directory to find all available case numbers."""
    cases = []
    # Build regex from configurable case name pattern
    marker = '___CASENUM___'
    template = config.case_pattern.format(N=marker, PHASE='TRANS')
    escaped = re.escape(template)
    regex_str = escaped.replace(marker, r'(\d+)') + '_all_variables_monthly'
    pattern = re.compile(regex_str)

    nc_files = list(data_dir.glob('*_all_variables_monthly_*.nc'))
    if not nc_files:
        print(f"  DEBUG: No NC files matching glob '*_all_variables_monthly_*.nc' in {data_dir}")
        print(f"  DEBUG: Directory exists: {data_dir.exists()}, is_dir: {data_dir.is_dir()}")
        # Try listing any files to diagnose
        any_files = list(data_dir.iterdir())[:5] if data_dir.is_dir() else []
        print(f"  DEBUG: First 5 entries in dir: {[f.name for f in any_files]}")
    else:
        print(f"  DEBUG: case_pattern='{config.case_pattern}', regex='{regex_str}'")
        print(f"  DEBUG: {len(nc_files)} NC files found, sample: {nc_files[0].name}")

    for f in nc_files:
        match = pattern.search(f.name)
        if match:
            cases.append(int(match.group(1)))

    return sorted(cases)


def load_nc_timeseries(case_num: int, var_name: str, config: ScreeningConfig) -> np.ndarray:
    """Load timeseries from NetCDF file."""
    case_name = config.case_pattern.format(N=case_num, PHASE='TRANS')
    nc_file = config.data_dir / config.file_pattern.format(
        case_name=case_name,
        year_start=config.year_start,
        year_end=config.year_end
    )

    n_months = (config.year_end - config.year_start + 1) * 12

    if nc_file.exists():
        try:
            with nc.Dataset(nc_file, 'r') as ds:
                if var_name in ds.variables:
                    data = ds.variables[var_name][:]
                    data = np.squeeze(data)
                    if data.ndim == 2:
                        if data.shape[1] == 156:
                            data = data.T
                    else:
                        return np.full((156, n_months), np.nan)
                    return data
        except Exception:
            pass

    return np.full((156, n_months), np.nan)


def get_pft_value_at_obs(data: np.ndarray, pft_id: int, obs_idx: int, factor: float = 1000) -> float:
    """Extract PFT-specific value at observation timestep."""
    szpf_start, szpf_end = get_szpf_range(pft_id)
    return np.sum(data[szpf_start:szpf_end + 1, obs_idx]) * factor


def _get_cache_path(data_dir: Path, targets: Dict[str, Target], config: ScreeningConfig) -> Path:
    """Generate cache file path based on data directory and config."""
    # Create hash of target names and config to detect changes
    target_names = sorted(targets.keys())
    config_str = f"{config.obs_year}_{config.obs_month}_{target_names}"
    config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]
    return data_dir / f".screening_cache_{config_hash}.pkl"


def _is_cache_valid(cache_path: Path, data_dir: Path) -> bool:
    """Check if cache is valid (exists, not older than data, and covers all files)."""
    if not cache_path.exists():
        return False

    cache_mtime = cache_path.stat().st_mtime

    # Check if any NC files are newer than cache
    nc_files = list(data_dir.glob("*.nc"))
    for nc_file in nc_files:
        if nc_file.stat().st_mtime > cache_mtime:
            return False  # Data changed since cache was created

    # Check if cache covers all available NC files
    if nc_files:
        try:
            with open(cache_path, 'rb') as f:
                cached = pickle.load(f)
            n_cached = len(cached.get('case_numbers', []))
            if n_cached < len(nc_files):
                return False  # New files added since cache was created
        except Exception:
            return False

    return True


def load_ensemble_simulated(
    data_dir: Path,
    targets: Dict[str, Target],
    config: ScreeningConfig,
    verbose: bool = True,
    use_cache: bool = True
) -> Tuple[Dict[str, np.ndarray], List[int]]:
    """
    Load simulated values for all cases in ensemble.

    Args:
        data_dir: Directory containing extracted NetCDF files
        targets: Validation targets
        config: Screening configuration
        verbose: Print progress messages
        use_cache: If True, use cached data if available (default: True)

    Returns:
        simulated: {target_name: array of values for each case}
        case_numbers: List of case numbers (for mapping indices to case IDs)
    """
    # Check for cached data
    cache_path = _get_cache_path(data_dir, targets, config)
    if use_cache and _is_cache_valid(cache_path, data_dir):
        if verbose:
            print(f"Loading cached data from {cache_path.name}...")
        try:
            with open(cache_path, 'rb') as f:
                cached = pickle.load(f)
            n_cached = len(cached['case_numbers'])
            if n_cached == 0:
                if verbose:
                    print(f"  Cache contains 0 cases (stale), reloading from files...")
            else:
                if verbose:
                    print(f"  Loaded {n_cached} cases from cache")
                return cached['simulated'], cached['case_numbers']
        except Exception as e:
            if verbose:
                print(f"  Cache load failed ({e}), reloading from files...")

    available_cases = get_available_cases(data_dir, config)

    if verbose:
        print(f"Found {len(available_cases)} cases in {data_dir.name}")

    # Initialize storage
    simulated = {name: [] for name in targets.keys()}
    case_numbers = []

    # Shared evaluation utility (same logic used by Phase 5 experiment evaluation)
    from tools.evaluate_case import extract_case_values

    # Process each case
    for i, case_num in enumerate(available_cases):
        if verbose and (i + 1) % 100 == 0:
            print(f"  Processing case {i+1}/{len(available_cases)}...")

        # Build NC file path for this case
        case_name = config.case_pattern.format(N=case_num, PHASE='TRANS')
        nc_file = config.data_dir / config.file_pattern.format(
            case_name=case_name,
            year_start=config.year_start,
            year_end=config.year_end
        )

        if not nc_file.exists():
            continue

        # Extract all target values from this case's NC file
        case_values = extract_case_values(nc_file, targets, config.obs_idx)

        # Skip if no values extracted (invalid/corrupt file)
        if not case_values:
            continue

        # Append values for each target (NaN for any missing)
        for name in targets:
            simulated[name].append(case_values.get(name, np.nan))

        case_numbers.append(case_num)

    # Convert to arrays
    simulated = {name: np.array(values) for name, values in simulated.items()}

    if verbose:
        print(f"  Loaded {len(case_numbers)} valid cases")

    # Save to cache for future runs
    if use_cache:
        try:
            cache_path = _get_cache_path(data_dir, targets, config)
            with open(cache_path, 'wb') as f:
                pickle.dump({'simulated': simulated, 'case_numbers': case_numbers}, f)
            if verbose:
                print(f"  Saved cache to {cache_path.name}")
        except Exception as e:
            if verbose:
                print(f"  Warning: Could not save cache ({e})")

    return simulated, case_numbers


# =============================================================================
# Main Screening Function
# =============================================================================

def screen_ensemble(
    data_dir: Path,
    targets: Dict[str, Target],
    config: Optional[ScreeningConfig] = None,
    top_n: int = 100,
    verbose: bool = True
) -> ScreeningResult:
    """
    Screen ensemble against validation targets.

    This is the main entry point for Phase 2 screening.

    Parameters
    ----------
    data_dir : Path
        Directory containing ensemble simulation outputs
    targets : Dict[str, Target]
        Validation targets (from site configuration)
    config : ScreeningConfig, optional
        Screening configuration
    top_n : int
        Number of top sets to return
    verbose : bool
        Print progress

    Returns
    -------
    ScreeningResult
        Structured results including rankings, statistics, and analysis

    Example
    -------
    >>> from phases.phase2_screening.screen_ensemble import screen_ensemble
    >>> from tools.optimize_function import Target
    >>>
    >>> targets = {
    ...     'PFT7_leaf': Target('PFT7_leaf', observed=24.6, uncertainty=0.2),
    ...     'PFT10_fineroot': Target('PFT10_fineroot', observed=382.1, uncertainty=0.2),
    ... }
    >>> result = screen_ensemble(data_dir, targets, top_n=50)
    >>> print(f"Best case: #{result.best_case_num}, cost: {result.best_cost:.4f}")
    """
    if not HAS_NETCDF:
        raise ImportError("netCDF4 required for screening. Install with: pip install netCDF4")

    # Setup config
    config = config or ScreeningConfig()
    config.data_dir = Path(data_dir)
    config.top_n = top_n

    if verbose:
        print("\n" + "=" * 60)
        print("A2MC PHASE 2: ENSEMBLE SCREENING")
        print("=" * 60)
        print(f"Data directory: {data_dir}")
        print(f"Targets: {len(targets)}")

    # Load simulated data
    if verbose:
        print("\nLoading ensemble data...")

    available_cases = get_available_cases(config.data_dir, config)
    simulated, case_numbers = load_ensemble_simulated(
        config.data_dir, targets, config, verbose=verbose
    )

    n_valid = len(case_numbers)

    if n_valid == 0:
        raise ValueError("No valid cases found!")

    if verbose:
        print(f"\nValid cases: {n_valid} / {len(available_cases)}")

    # Configure optimization
    opt_config = OptimizationConfig(
        error_method=config.error_method,
        aggregation_method=config.aggregation_method,
        tolerance=config.tolerance,
        n_top=top_n,
        verbose=verbose
    )

    # Run optimization
    if verbose:
        print("\nRunning optimization...")

    opt_result = optimize_ensemble(simulated, targets, opt_config)

    # Get best case
    best_idx = opt_result.best_index
    best_case_num = case_numbers[best_idx]
    best_cost = opt_result.best_cost
    max_satisfied = int(np.max(opt_result.n_satisfied))

    # Build result
    result = ScreeningResult(
        optimization_result=opt_result,
        simulated=simulated,
        n_available_cases=len(available_cases),
        n_valid_cases=n_valid,
        case_numbers=case_numbers,
        best_case_num=best_case_num,
        best_cost=best_cost,
        max_satisfied_count=max_satisfied
    )

    # Print summary
    if verbose:
        print("\n" + "=" * 60)
        print("SCREENING COMPLETE")
        print("=" * 60)
        print(f"Best case: #{best_case_num}")
        print(f"  Composite cost (RMSRE): {best_cost:.6f}")
        print(f"  Targets satisfied: {opt_result.n_satisfied[best_idx]}/{len(targets)}")
        print(f"\nMax targets satisfied in ensemble: {max_satisfied}/{len(targets)}")

        # Top 10
        print("\nTop 10 cases:")
        print(f"{'Rank':<6} {'Case':<8} {'Cost':<12} {'Satisfied'}")
        print("-" * 40)
        for i, idx in enumerate(opt_result.ranked_indices[:10]):
            print(f"{i+1:<6} {case_numbers[idx]:<8} {opt_result.composite_cost[idx]:<12.6f} "
                  f"{opt_result.n_satisfied[idx]}/{len(targets)}")

    return result


# =============================================================================
# Kougarok-Specific Target Loading (Site Configuration)
# =============================================================================

def load_kougarok_targets() -> Dict[str, Target]:
    """
    Load validation targets for Kougarok site.

    Observations from July 2016 field campaign.
    """
    return {
        'PFT7_leaf': Target(
            name='PFT7_leaf',
            observed=24.55,  # 49.1 * 0.5 (dry mass to C)
            uncertainty=0.2,
            units='g C/m²',
            description='Evergreen shrub leaf biomass'
        ),
        'PFT7_fineroot': Target(
            name='PFT7_fineroot',
            observed=174.25,  # 348.5 * 0.5
            uncertainty=0.2,
            units='g C/m²',
            description='Evergreen shrub fine root biomass'
        ),
        'PFT9_leaf': Target(
            name='PFT9_leaf',
            observed=124.7,  # 249.4 * 0.5
            uncertainty=0.2,
            units='g C/m²',
            description='Deciduous shrub leaf biomass'
        ),
        'PFT9_fineroot': Target(
            name='PFT9_fineroot',
            observed=187.35,  # 374.7 * 0.5
            uncertainty=0.2,
            units='g C/m²',
            description='Deciduous shrub fine root biomass'
        ),
        'PFT10_leaf': Target(
            name='PFT10_leaf',
            observed=82.65,  # 165.3 * 0.5
            uncertainty=0.2,
            units='g C/m²',
            description='Arctic graminoid leaf biomass'
        ),
        'PFT10_fineroot': Target(
            name='PFT10_fineroot',
            observed=382.05,  # 764.1 * 0.5
            uncertainty=0.2,
            units='g C/m²',
            description='Arctic graminoid fine root biomass'
        ),
    }


# =============================================================================
# Main
# =============================================================================

def main():
    """Run screening for Kougarok ensemble"""
    import argparse

    parser = argparse.ArgumentParser(description='Screen ensemble against targets')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='Directory containing simulation outputs')
    parser.add_argument('--top-n', type=int, default=100,
                        help='Number of top cases to report')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Directory for output files')
    args = parser.parse_args()

    # Get data directory
    if args.data_dir:
        data_dir = Path(args.data_dir)
    else:
        # Default Kougarok path
        import os
        home = os.environ.get('HOME', '/Users/jingtao')
        data_dir = Path(f'{home}/Desktop/Work/NGEE-Arctic/Kougarok/Results_PlantTraitsCNPEnsemble_wModPval_noADSP2/Kougarok_PlantTraitsCNPEnsemble162_Morris')

    # Load targets
    targets = load_kougarok_targets()

    # Run screening
    result = screen_ensemble(data_dir, targets, top_n=args.top_n)

    # Save results if output dir specified
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        save_optimization_results(
            result.optimization_result,
            result.simulated,
            output_dir,
            prefix='screening'
        )

        # Save structured result for phase logging
        with open(output_dir / 'screening_result.json', 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

        print(f"\nResults saved to: {output_dir}")

    return result


if __name__ == '__main__':
    main()
