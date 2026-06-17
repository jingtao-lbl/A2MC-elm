#!/usr/bin/env python3
"""
Ensemble case visualization — whole-ensemble biomass vs validation targets.

Generic plotting tool for any A2MC site/round. Creates N_PFTs × N_vars panel
figures showing:
- All (or top-N) ensemble members as thin purple lines (the cloud)
- Best NRMSE case highlighted in red
- Most-targets-met case highlighted in blue
- Observations with uncertainty bars and ±tolerance range boxes

Produces the `R{N}_{combined,TRANS}_{count}cases_ensemble.png` figures. Reads the
round's `*_all_variables_monthly_*.nc` from `$A2MC_EXTRACTED_DATA`; site specifics
(PFT ids/names, targets, case-name pattern, output dir) come from config + CLI,
so the same tool serves every round and site.

Usage (standalone):
    source a2mc_config.sh; source use_cases/<site>/config/<round_config>.sh
    python tools/plot_ensemble_cases.py --combined          # 519-yr ADSP+RGSP+TRANS axis
    python tools/plot_ensemble_cases.py --plot-years 2010-2019   # TRANS-only
    # optional overrides: --pft-ids 7,9,10  --round-label R4  --output-dir <dir>

Library use:
    from tools.plot_ensemble_cases import plot_ensemble_biomass_from_dir

History: generalized from use_cases/Kougarok/analysis/plot_all_extracted.py
(which is now a thin shim → this module) so it is reusable + discoverable in tools/.
Author: Jing Tao with Claude
Created: February 2026 (moved to tools/ + generalized June 2026)
"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Make A2MC root importable so `from tools.* import ...` works regardless of
# cwd when this script is invoked by absolute path. __file__ is at
# A2MC/tools/plot_ensemble_cases.py — one parent up.
_A2MC_ROOT = Path(__file__).resolve().parents[1]
if str(_A2MC_ROOT) not in sys.path:
    sys.path.insert(0, str(_A2MC_ROOT))

import numpy as np

# HPC-safe backend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle

logger = logging.getLogger(__name__)

# Default figure DPI (match plot_diagnostics.py)
FIGURE_DPI = 600

# Default PFT names
DEFAULT_PFT_NAMES = {
    7: 'PFT#7 Evergreen Shrub',
    8: 'PFT#8 Hydrodecid. Shrub',
    9: 'PFT#9 Deciduous Shrub',
    10: 'PFT#10 Graminoid',
}

# Variable configurations
VARIABLE_CONFIGS = {
    'leaf': {
        'nc_var': 'FATES_LEAFC_SZPF',
        'factor': 1000,  # kg/m² to g/m²
        'unit': 'Leaf C (g C m$^{-2}$)',
        'title': 'Leaf Biomass',
    },
    'fineroot': {
        'nc_var': 'FATES_FROOTC_SZPF',
        'factor': 1000,
        'unit': 'Fineroot C (g C m$^{-2}$)',
        'title': 'Fineroot Biomass',
    },
}

# Color scheme
# Alpha and linewidth dialed down vs the Phase-2 screening defaults: with all
# extracted cases (~2700+ lines) at alpha=0.5 the ensemble cloud saturates
# to solid purple. Lower values let density gradients stay readable.
ENSEMBLE_COLOR = [0.7, 0.6, 1.0]  # light purple
ENSEMBLE_ALPHA = 0.05
ENSEMBLE_LINEWIDTH = 0.3

# Phase configurations.
# - TRANS_ONLY: just the 1901-2019 transient (the production preview).
# - COMBINED: the full 519-year history — 200 yr ADSP + 200 yr RGSP + 119 yr
#   TRANS — concatenated on a single simulation-year axis.
TRANS_ONLY_PHASES = [('TRANS', 1901, 2019)]
COMBINED_PHASES = [
    ('ADSP', 1, 200),
    ('RGSP', 201, 400),
    ('TRANS', 1901, 2019),
]


def _phases_total_months(phases):
    return sum((y1 - y0 + 1) * 12 for _, y0, y1 in phases)


def _obs_index_in_phases(phases, obs_year, obs_month):
    """Return the month index of (obs_year, obs_month) in the concatenated
    phase axis. Raises ValueError if obs_year is not within any phase."""
    cum = 0
    for _, y0, y1 in phases:
        if y0 <= obs_year <= y1:
            return cum + (obs_year - y0) * 12 + (obs_month - 1)
        cum += (y1 - y0 + 1) * 12
    raise ValueError(f"obs_year={obs_year} not contained in phases {phases}")

BEST_NRMSE_COLOR = 'red'
BEST_NRMSE_LINEWIDTH = 3

BEST_TARGETS_COLOR = 'blue'
BEST_TARGETS_LINEWIDTH = 3


# =============================================================================
# Data Loading Helpers
# =============================================================================

def _get_case_name_pattern():
    """Get case name pattern from A2MC config or environment."""
    import os
    try:
        from tools.config import config as a2mc_config
        return a2mc_config.CASE_NAME_PATTERN
    except ImportError:
        prefix = os.environ.get('A2MC_ENSEMBLE_PREFIX', '')
        return os.environ.get(
            'A2MC_CASE_NAME_PATTERN', f"{prefix}{{N}}_{{PHASE}}")


def _build_case_regex(case_pattern: str) -> re.Pattern:
    """Build regex to extract case number from filenames."""
    marker = '___CASENUM___'
    template = case_pattern.format(N=marker, PHASE='TRANS')
    escaped = re.escape(template)
    regex_str = escaped.replace(marker, r'(\d+)') + '_all_variables_monthly'
    return re.compile(regex_str)


def get_available_cases(data_dir: Path, case_pattern: str = None,
                        mtime_after_epoch: Optional[float] = None) -> List[int]:
    """Scan directory to find all available case numbers.

    If mtime_after_epoch is set, skip NCs with mtime <= that epoch. Used to
    exclude stale leftover NCs from prior calibration rounds whose filenames
    match the current pattern but whose data is not part of the current
    ensemble. Current R4 (ADSPSupNP) uses a different filename pattern, so
    this is mainly for deprecated PrescP-pattern rounds (e.g. the 2026-04-13
    subset_replay+PrescP variant that was pre-R5 lineage).
    """
    if case_pattern is None:
        case_pattern = _get_case_name_pattern()

    pattern = _build_case_regex(case_pattern)
    cases = []
    for f in data_dir.glob('*_all_variables_monthly_*.nc'):
        if mtime_after_epoch is not None:
            try:
                if f.stat().st_mtime <= mtime_after_epoch:
                    continue
            except OSError:
                continue
        match = pattern.search(f.name)
        if match:
            cases.append(int(match.group(1)))
    return sorted(cases)


def load_nc_timeseries(
    case_num: int,
    var_name: str,
    data_dir: Path,
    case_pattern: str = None,
    year_start: int = 1901,
    year_end: int = 2019,
    file_pattern: str = '{case_name}_all_variables_monthly_{year_start}_{year_end}.nc',
    phase: str = 'TRANS',
) -> np.ndarray:
    """Load SZPF timeseries from extracted NetCDF file for one (case, phase)."""
    try:
        import netCDF4 as nc
    except ImportError:
        return None

    if case_pattern is None:
        case_pattern = _get_case_name_pattern()

    case_name = case_pattern.format(N=case_num, PHASE=phase)
    nc_file = data_dir / file_pattern.format(
        case_name=case_name,
        year_start=year_start,
        year_end=year_end
    )

    n_months = (year_end - year_start + 1) * 12

    if nc_file.exists():
        try:
            with nc.Dataset(nc_file, 'r') as ds:
                if var_name in ds.variables:
                    data = ds.variables[var_name][:]
                    data = np.squeeze(data)
                    if data.ndim == 2:
                        # Ensure shape is (n_szpf, n_time)
                        if data.shape[1] == 156:
                            data = data.T
                        # Fast path: time series already has the expected length
                        if data.shape[1] == n_months:
                            return data
                        # Short path: some yearly file(s) were skipped by the
                        # extractor (partial-write artifacts). Use the NC's
                        # time coord to place each actual monthly sample at
                        # its correct canonical month index, NaN-fill gaps.
                        # ELM uses noleap calendar; time is days since
                        # {year_start}-01-01. End-of-month days follow the
                        # fixed 31,28,31,30,31,30,31,31,30,31,30,31 schedule.
                        if 'time' in ds.variables:
                            t = np.asarray(ds.variables['time'][:], dtype=np.float64)
                            month_days = np.array(
                                [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31],
                                dtype=np.int32,
                            )
                            canonical = np.cumsum(
                                np.tile(month_days, year_end - year_start + 1)
                            ).astype(np.float64)
                            # Each t value should match a canonical end-of-month day exactly.
                            # Use searchsorted; tolerance applied for float robustness.
                            idx = np.searchsorted(canonical, t)
                            valid = (idx < n_months) & (np.abs(canonical[np.minimum(idx, n_months-1)] - t) < 1.0)
                            if valid.sum() == data.shape[1]:
                                out = np.full((156, n_months), np.nan, dtype=data.dtype)
                                out[:, idx[valid]] = data[:, valid]
                                return out
        except Exception:
            pass

    return np.full((156, n_months), np.nan)


def load_combined_timeseries(
    case_num: int,
    var_name: str,
    data_dir: Path,
    phases: List,
    case_pattern: str = None,
) -> np.ndarray:
    """Load and concatenate (case, var) timeseries across all phases on the
    time axis. Returns shape (156, total_months)."""
    parts = []
    for suffix, y0, y1 in phases:
        arr = load_nc_timeseries(
            case_num, var_name, data_dir,
            case_pattern=case_pattern,
            year_start=y0, year_end=y1,
            phase=suffix,
        )
        parts.append(arr)
    return np.concatenate(parts, axis=1)


def get_pft_timeseries(data: np.ndarray, pft_id: int, factor: float = 1000) -> np.ndarray:
    """Sum SZPF data across size classes for a given PFT, apply unit factor."""
    from tools.fates_utils import get_szpf_range
    start, end = get_szpf_range(pft_id)
    return np.sum(data[start:end + 1, :], axis=0) * factor


# =============================================================================
# Bulk parallel loading (cache)
# =============================================================================

# Top-level worker for multiprocessing.Pool. Must be module-level (picklable).
# netCDF4-python isn't thread-safe against this HDF5 build (segfaults under
# ThreadPoolExecutor), so we use processes instead.
#
# The worker reduces the raw (n_szpf, n_months) array down to per-PFT summed
# timeseries inside the worker BEFORE returning. With pft_ids=[7,9,10] and
# factor=1000, we go from 156 size-pft bins back to 3 PFT lines, dropping the
# returned payload 52x. This matters for large ensembles: at 4890 cases ×
# 2 vars × (156 × 6228 × 4) the parent-side cache is 38 GB; the per-PFT
# reduction shrinks it to ~700 MB and keeps the parent within memory bounds
# on a NERSC login node.
def _load_one_case_var(args):
    case_num, var_type, nc_var, data_dir, case_pattern, phases, pft_ids, factor = args
    raw = load_combined_timeseries(
        case_num, nc_var, Path(data_dir),
        phases=phases,
        case_pattern=case_pattern,
    )
    # Reduce SZPF to per-PFT summed timeseries (apply unit factor).
    from tools.fates_utils import get_szpf_range
    pft_ts = {}
    for pft_id in pft_ids:
        start, end = get_szpf_range(pft_id)
        pft_ts[pft_id] = (np.sum(raw[start:end + 1, :], axis=0) * factor).astype(np.float32)
    del raw
    return case_num, var_type, pft_ts


def _load_all_case_data(
    available_cases: List[int],
    data_dir: Path,
    variables: List[str],
    case_pattern: str,
    pft_ids: List[int],
    phases: List = None,
    n_workers: int = 16,
) -> Dict[int, Dict[str, Dict[int, np.ndarray]]]:
    """
    Bulk-load every (case, variable) timeseries in parallel and return a cache.

    The Phase-2 production script loads each NC twice (rank phase + plot
    phase) and serially. With 2729 cases × 2 vars that's ~10,900 sequential
    NC opens on Lustre — about 25 minutes. Loading once in parallel via
    multiprocessing and sharing the cache with both phases cuts that to a
    few minutes.
    """
    from multiprocessing import Pool

    if phases is None:
        phases = TRANS_ONLY_PHASES

    tasks = []
    for case_num in available_cases:
        for var_type in variables:
            var_config = VARIABLE_CONFIGS.get(var_type)
            if var_config:
                factor = var_config.get('factor', 1000)
                tasks.append((case_num, var_type, var_config['nc_var'],
                              str(data_dir), case_pattern, phases,
                              list(pft_ids), factor))

    cache: Dict[int, Dict[str, Dict[int, np.ndarray]]] = {c: {} for c in available_cases}

    logger.info(f"Loading {len(tasks)} (case, var) timeseries in parallel "
                f"({n_workers} processes, per-PFT reduction in worker)...")
    completed = 0
    with Pool(processes=n_workers) as pool:
        for case_num, var_type, pft_ts in pool.imap_unordered(
                _load_one_case_var, tasks, chunksize=8):
            cache[case_num][var_type] = pft_ts
            completed += 1
            if completed % 1000 == 0:
                logger.info(f"  Loaded {completed}/{len(tasks)}")

    # Drop cases where any required variable came back all-NaN
    invalid = []
    for c, vd in cache.items():
        for var_type, pft_ts in vd.items():
            if any(arr is None or np.all(np.isnan(arr)) for arr in pft_ts.values()):
                invalid.append(c)
                break
    for c in invalid:
        cache.pop(c, None)
    if invalid:
        logger.info(f"  Dropped {len(invalid)} cases with NaN data")
    logger.info(f"  Cache ready: {len(cache)} cases")
    return cache


# =============================================================================
# Ranking Helpers
# =============================================================================

def rank_cases_by_nrmse(
    data_dir: Path,
    available_cases: List[int],
    targets: Dict[str, Dict],
    pft_ids: List[int],
    variables: List[str] = None,
    case_pattern: str = None,
    year_start: int = 1901,
    year_end: int = 2019,
    obs_year: int = 2016,
    obs_month: int = 7,
    case_data: Optional[Dict[int, Dict[str, np.ndarray]]] = None,
    phases: Optional[List] = None,
) -> List[Dict]:
    """
    Rank all cases by composite NRMSE against targets.

    Parameters
    ----------
    data_dir : Path
        Directory with extracted NetCDF files
    available_cases : list of int
        Case numbers to evaluate
    targets : dict
        Target dict: {target_key: {'observed': float, 'uncertainty': float}}
        Keys like 'PFT7_leaf', 'PFT10_fineroot', etc.
    pft_ids : list of int
        PFT IDs to evaluate
    variables : list of str
        Variable types to check (default: ['leaf', 'fineroot'])
    case_pattern : str, optional
        Case name pattern (auto-detected if None)
    year_start, year_end : int
        Simulation year range
    obs_year, obs_month : int
        Observation timestep

    Returns
    -------
    list of dict
        Ranked results, sorted by composite NRMSE (lowest first)
    """
    if variables is None:
        variables = ['leaf', 'fineroot']
    if case_pattern is None:
        case_pattern = _get_case_name_pattern()

    # In single-phase TRANS-only mode, obs_idx is the calendar offset within
    # year_start..year_end. In multi-phase mode, it's the cumulative month
    # index across all phases.
    if phases and len(phases) > 1:
        obs_idx = _obs_index_in_phases(phases, obs_year, obs_month)
    else:
        obs_idx = (obs_year - year_start) * 12 + obs_month - 1
    # Average obs_month + the following month (Jul+Aug) for the best-NRMSE
    # comparison, matching screening (ScreeningConfig.obs_months default [7, 8]).
    obs_idxs = [obs_idx, obs_idx + 1]
    results = []

    for i, case_num in enumerate(available_cases):
        if (i + 1) % 500 == 0:
            logger.info(f"  Ranking case {i+1}/{len(available_cases)}...")

        # Cache hit: skip the per-case NC opens (the bulk loader already
        # validated the arrays and dropped NaN-only cases).
        if case_data is not None:
            case_vars = case_data.get(case_num)
            if case_vars is None:
                continue
        else:
            # Legacy path: load on demand (used when caller did not pre-load).
            case_vars = {}
            valid = True
            for var_type in variables:
                var_config = VARIABLE_CONFIGS.get(var_type)
                if not var_config:
                    continue
                data = load_nc_timeseries(
                    case_num, var_config['nc_var'], data_dir,
                    case_pattern=case_pattern,
                    year_start=year_start, year_end=year_end
                )
                if np.all(np.isnan(data)):
                    valid = False
                    break
                case_vars[var_type] = data

            if not valid:
                continue

        # Compute per-target NRMSE
        nrmse_values = {}
        simulated_values = {}
        n_satisfied = 0
        n_total = 0

        for pft_id in pft_ids:
            for var_type in variables:
                target_key = f'PFT{pft_id}_{var_type}'
                target_info = targets.get(target_key)
                if target_info is None:
                    continue

                var_config = VARIABLE_CONFIGS[var_type]
                data = case_vars[var_type]
                # Cache stores per-PFT timeseries directly; no SZPF reduction needed.
                if isinstance(data, dict):
                    ts = data.get(pft_id)
                    if ts is None:
                        continue
                else:
                    ts = get_pft_timeseries(data, pft_id, factor=var_config['factor'])
                sim_val = float(np.mean([ts[k] for k in obs_idxs
                                         if 0 <= k < len(ts)]))

                obs_val = target_info['observed']
                nrmse = abs(sim_val - obs_val) / obs_val if obs_val != 0 else float('inf')
                nrmse_values[target_key] = nrmse
                simulated_values[target_key] = sim_val

                tolerance = target_info.get('uncertainty', 0.2)
                if obs_val * (1 - tolerance) <= sim_val <= obs_val * (1 + tolerance):
                    n_satisfied += 1
                n_total += 1

        if not nrmse_values:
            continue

        composite_nrmse = np.sqrt(np.mean(np.array(list(nrmse_values.values()))**2))

        results.append({
            'case_num': case_num,
            'composite_nrmse': composite_nrmse,
            'n_satisfied': n_satisfied,
            'n_total': n_total,
            'nrmse_individual': nrmse_values,
            'simulated': simulated_values,
        })

    return sorted(results, key=lambda x: x['composite_nrmse'])


# =============================================================================
# Main Plotting Function
# =============================================================================

def plot_ensemble_biomass(
    data_dir: str,
    ranked_cases: List[Dict],
    targets: Dict[str, Dict],
    pft_ids: List[int],
    output_path: Optional[str] = None,
    variables: List[str] = None,
    pft_names: Optional[Dict[int, str]] = None,
    top_n: int = 100,
    case_pattern: str = None,
    year_start: int = 1901,
    year_end: int = 2019,
    obs_year: int = 2016,
    obs_month: int = 7,
    plot_year_start: int = 2010,
    plot_year_end: int = 2019,
    title_suffix: str = "",
    obs_uncertainty: Optional[Dict[str, float]] = None,
    case_data: Optional[Dict[int, Dict[str, np.ndarray]]] = None,
    phases: Optional[List] = None,
) -> Optional[str]:
    """
    Plot ensemble biomass timeseries with best cases highlighted.

    Creates an N_PFTs × N_vars panel figure showing ensemble spread,
    best NRMSE case (red), most-targets-met case (blue), and observations.

    Parameters
    ----------
    data_dir : str
        Directory containing extracted NetCDF files
    ranked_cases : list of dict
        Cases sorted by NRMSE. Each dict must have:
        - 'case_num': int
        - 'composite_nrmse': float
        - 'n_satisfied': int
    targets : dict
        Target definitions: {target_key: {'observed': float, 'uncertainty': float}}
        Keys like 'PFT7_leaf', 'PFT10_fineroot'.
        Optional 'obs_uncertainty' key for asymmetric error bars.
    pft_ids : list of int
        PFT IDs for rows (e.g., [7, 9, 10])
    output_path : str, optional
        Full path to save figure. If None, saves to data_dir.
    variables : list of str, optional
        Variable types for columns (default: ['leaf', 'fineroot'])
    pft_names : dict, optional
        PFT ID to display name mapping
    top_n : int
        Number of top cases to plot (default: 100)
    case_pattern : str, optional
        Case name pattern (auto-detected from config if None)
    year_start, year_end : int
        Simulation year range
    obs_year, obs_month : int
        Observation timestep (for marker placement)
    plot_year_start, plot_year_end : int
        Year range to display on x-axis
    title_suffix : str
        Extra text to append to the figure title
    obs_uncertainty : dict, optional
        Per-target observation uncertainty (standard error/deviation) for
        error bars, separate from the tolerance range. Keys match target keys.
        If not provided, error bars show ±tolerance range.

    Returns
    -------
    str or None
        Path to saved figure, or None if plotting failed
    """
    if variables is None:
        variables = ['leaf', 'fineroot']
    if pft_names is None:
        pft_names = DEFAULT_PFT_NAMES
    if case_pattern is None:
        case_pattern = _get_case_name_pattern()

    data_dir = Path(data_dir)
    n_pfts = len(pft_ids)
    n_vars = len(variables)

    # Determine best cases
    cases_to_plot = [r['case_num'] for r in ranked_cases[:top_n]]
    if not cases_to_plot:
        logger.warning("No cases to plot")
        return None

    best_nrmse_case = ranked_cases[0]['case_num']
    best_nrmse_value = ranked_cases[0]['composite_nrmse']

    # Find case with most targets satisfied (tie-break by NRMSE)
    max_satisfied = max(r['n_satisfied'] for r in ranked_cases[:top_n])
    best_satisfied_cases = [r for r in ranked_cases[:top_n] if r['n_satisfied'] == max_satisfied]
    best_targets_case = min(best_satisfied_cases, key=lambda x: x['composite_nrmse'])['case_num']
    n_total = ranked_cases[0].get('n_total', len(pft_ids) * len(variables))

    # Time indices.
    # Single-phase (TRANS-only) mode keeps the original calendar-year window.
    # Multi-phase mode plots the entire concatenated history (no clipping)
    # and computes obs_idx via cumulative phase offsets.
    multi_phase = phases is not None and len(phases) > 1
    if multi_phase:
        obs_idx = _obs_index_in_phases(phases, obs_year, obs_month)
        plot_start_idx = 0
        plot_end_idx = _phases_total_months(phases)
    else:
        obs_idx = (obs_year - year_start) * 12 + obs_month - 1
        plot_start_idx = (plot_year_start - year_start) * 12
        plot_end_idx = (plot_year_end - year_start + 1) * 12
    n_months_plot = plot_end_idx - plot_start_idx

    # Pre-load timeseries for the cases we'll plot.
    # If the caller passed a cache (parallel-loaded once and shared with the
    # ranking step), filter it down to cases_to_plot and skip the per-case NC
    # opens here. Otherwise fall back to the legacy serial load.
    if case_data is not None:
        case_data = {c: case_data[c] for c in cases_to_plot if c in case_data}
        logger.info(f"Using pre-loaded cache: {len(case_data)} of "
                    f"{len(cases_to_plot)} requested cases present")
    else:
        logger.info(f"Loading timeseries for {len(cases_to_plot)} cases (no cache)...")
        case_data = {}
        for case_num in cases_to_plot:
            var_data = {}
            valid = True
            for var_type in variables:
                var_config = VARIABLE_CONFIGS.get(var_type)
                if not var_config:
                    continue
                data = load_nc_timeseries(
                    case_num, var_config['nc_var'], data_dir,
                    case_pattern=case_pattern,
                    year_start=year_start, year_end=year_end
                )
                if np.all(np.isnan(data)):
                    valid = False
                    break
                var_data[var_type] = data
            if valid:
                case_data[case_num] = var_data
        logger.info(f"Loaded data for {len(case_data)} cases")

    if not case_data:
        logger.warning("No valid case data loaded")
        return None

    # Create figure
    try:
        logger.info(f"Creating figure ({n_pfts}x{n_vars}, multi_phase={multi_phase}, "
                    f"n_months_plot={n_months_plot}, len(cases_to_plot)={len(cases_to_plot)})")
        fig, axes = plt.subplots(n_pfts, n_vars, figsize=(7 * n_vars, 4 * n_pfts))
        fig.patch.set_facecolor('white')

        # Handle single-row or single-column case
        if n_pfts == 1 and n_vars == 1:
            axes = np.array([[axes]])
        elif n_pfts == 1:
            axes = axes[np.newaxis, :]
        elif n_vars == 1:
            axes = axes[:, np.newaxis]

        for col_idx, var_type in enumerate(variables):
            var_config = VARIABLE_CONFIGS.get(var_type, {})
            for row_idx, pft_id in enumerate(pft_ids):
                ax = axes[row_idx, col_idx]
                target_key = f'PFT{pft_id}_{var_type}'
                target_info = targets.get(target_key, {})
                obs_mean = target_info.get('observed', None)
                tolerance = target_info.get('uncertainty', 0.2)

                # Two-pass plotting:
                #   1. Collect all ensemble (non-highlighted) lines into a
                #      single LineCollection — matplotlib chokes silently when
                #      asked to manage thousands of individual Line2D objects
                #      across multiple panels (observed at 2729 cases × 6
                #      panels in multi-phase mode). LineCollection lets matplotlib
                #      render them in one pass with shared style.
                #   2. Plot the two highlighted cases (best NRMSE, best targets)
                #      individually so they get legend entries.
                ensemble_segments = []
                x_axis = np.arange(plot_end_idx - plot_start_idx)
                best_nrmse_ts = None
                best_targets_ts = None
                for case_num in cases_to_plot:
                    if case_num not in case_data:
                        continue
                    data = case_data[case_num].get(var_type)
                    if data is None:
                        continue
                    # Per-PFT cache (compact) vs raw SZPF (legacy)
                    if isinstance(data, dict):
                        ts = data.get(pft_id)
                        if ts is None:
                            continue
                    else:
                        ts = get_pft_timeseries(data, pft_id,
                                                factor=var_config.get('factor', 1000))
                    plot_ts = ts[plot_start_idx:plot_end_idx]
                    if case_num == best_nrmse_case:
                        best_nrmse_ts = plot_ts
                    elif case_num == best_targets_case and best_targets_case != best_nrmse_case:
                        best_targets_ts = plot_ts
                    else:
                        ensemble_segments.append(np.column_stack([x_axis, plot_ts]))

                if ensemble_segments:
                    lc = LineCollection(
                        ensemble_segments,
                        colors=[ENSEMBLE_COLOR],
                        linewidths=ENSEMBLE_LINEWIDTH,
                        alpha=ENSEMBLE_ALPHA,
                        zorder=50,
                    )
                    ax.add_collection(lc)

                if best_nrmse_ts is not None:
                    ax.plot(best_nrmse_ts, color=BEST_NRMSE_COLOR,
                            linewidth=BEST_NRMSE_LINEWIDTH, alpha=1.0,
                            label=f'Best NRMSE (#{best_nrmse_case})',
                            zorder=100)
                if best_targets_ts is not None:
                    ax.plot(best_targets_ts, color=BEST_TARGETS_COLOR,
                            linewidth=BEST_TARGETS_LINEWIDTH, alpha=1.0,
                            label=f'Most targets (#{best_targets_case}, '
                                  f'{max_satisfied}/{n_total})',
                            zorder=99)
                # LineCollection doesn't autoscale axes; we'll set y-limits from
                # the data after this loop completes for this panel.
                if ensemble_segments or best_nrmse_ts is not None or best_targets_ts is not None:
                    all_y = []
                    for seg in ensemble_segments:
                        all_y.append(seg[:, 1])
                    if best_nrmse_ts is not None:
                        all_y.append(best_nrmse_ts)
                    if best_targets_ts is not None:
                        all_y.append(best_targets_ts)
                    if all_y:
                        y_concat = np.concatenate(all_y)
                        finite = y_concat[np.isfinite(y_concat)]
                        if finite.size:
                            y_min = float(np.min(finite))
                            y_max = float(np.max(finite))
                            margin = 0.05 * (y_max - y_min) if y_max > y_min else max(abs(y_max), 1) * 0.1
                            ax.set_ylim(y_min - margin, y_max + margin)

                # Plot observation marker and uncertainty
                if obs_mean is not None:
                    # Center the marker on the Jul+Aug averaging window (obs_idx
                    # and obs_idx+1), matching the best-NRMSE comparison.
                    obs_plot_idx = (obs_idx + 0.5) - plot_start_idx

                    # ±tolerance validation range box
                    valid_low = obs_mean * (1 - tolerance)
                    valid_high = obs_mean * (1 + tolerance)
                    box_width = n_months_plot * 0.03
                    rect = Rectangle(
                        (obs_plot_idx - box_width / 2, valid_low),
                        box_width, valid_high - valid_low,
                        facecolor='yellow', edgecolor='darkorange',
                        alpha=0.4, linewidth=2, zorder=200,
                        label=f'±{int(tolerance*100)}% Obs. Range' if (row_idx == 0 and col_idx == 0) else None
                    )
                    ax.add_patch(rect)

                    # Error bar (observation uncertainty if provided, else tolerance)
                    if obs_uncertainty and target_key in obs_uncertainty:
                        uncert = obs_uncertainty[target_key]
                    else:
                        uncert = obs_mean * tolerance
                    ax.plot([obs_plot_idx, obs_plot_idx],
                            [obs_mean - uncert, obs_mean + uncert],
                            'k-', linewidth=3, zorder=201)

                    # Observation diamond
                    ax.plot(obs_plot_idx, obs_mean, 'kd', linewidth=3, markersize=12,
                            markerfacecolor='k', zorder=202,
                            label='Obs' if (row_idx == 0 and col_idx == 0) else None)

                # Format axes — single calendar axis vs multi-phase sim axis
                ax.set_xlim([0, n_months_plot])
                if multi_phase:
                    # Hybrid axis: spinup phases (ADSP, RGSP) labeled with
                    # simulation years; TRANS phase labeled with calendar
                    # years (1920, 1960, 2000) since that's how the
                    # validation window is naturally read.
                    tick_positions = []
                    tick_labels = []
                    cum = 0
                    for suffix, y0, y1 in phases:
                        span = (y1 - y0 + 1) * 12
                        if suffix == 'TRANS':
                            cand = [c for c in (1920, 1960, 2000) if y0 <= c <= y1]
                        else:
                            # Spinup phases (ADSP, RGSP): label every 50
                            # simulation years, but exclude y1 (the phase
                            # boundary, already marked by the dashed
                            # vertical), so RGSP's "400" doesn't crowd
                            # TRANS's "1920".
                            step = 50
                            cand = list(range(((y0 // step) + 1) * step,
                                              y1, step))
                            if y0 == 1:
                                cand.insert(0, 1)
                        for yr in cand:
                            pos = cum + (yr - y0) * 12
                            # Suppress ticks too close to the previous one
                            # (e.g. RGSP "400" abutting TRANS phase boundary).
                            if tick_positions and pos - tick_positions[-1] < 24:
                                continue
                            tick_positions.append(pos)
                            tick_labels.append(str(yr))
                        cum += span
                    ax.set_xticks(tick_positions)
                    ax.set_xticklabels(tick_labels, fontsize=11)
                    # Phase boundary lines + per-phase labels at the top
                    cum = 0
                    for p_idx, (suffix, y0, y1) in enumerate(phases):
                        span = (y1 - y0 + 1) * 12
                        if p_idx > 0:
                            ax.axvline(cum, color='gray', linestyle='--',
                                       linewidth=1, alpha=0.6, zorder=1)
                        if row_idx == 0:
                            ax.text(cum + span / 2, ax.get_ylim()[1] * 0.96,
                                    suffix, ha='center', va='top',
                                    fontsize=9, color='gray', alpha=0.85)
                        cum += span
                else:
                    tick_positions = np.arange(0, n_months_plot, 12)
                    tick_labels = np.arange(plot_year_start, plot_year_end + 1)
                    ax.set_xticks(tick_positions)
                    ax.set_xticklabels(tick_labels, fontsize=12)

                if row_idx == 0:
                    ax.set_title(var_config.get('title', var_type.capitalize()),
                                 fontweight='bold', fontsize=16)
                if col_idx == 0:
                    pft_label = pft_names.get(pft_id, f'PFT#{pft_id}')
                    ax.set_ylabel(f'{pft_label}\n{var_config.get("unit", "")}',
                                  fontweight='bold', fontsize=14)
                else:
                    ax.set_ylabel(var_config.get('unit', ''), fontsize=14)

                if row_idx == n_pfts - 1:
                    xlbl = ('Simulation Year (ADSP, RGSP) / Calendar Year (TRANS)'
                            if multi_phase else 'Year')
                    ax.set_xlabel(xlbl, fontweight='bold', fontsize=14)

                ax.grid(True, alpha=0.3)
                ax.tick_params(axis='both', labelsize=12)

                # Legend in top-left panel only
                if row_idx == 0 and col_idx == 0:
                    ax.legend(loc='upper left', fontsize=11, framealpha=0.9)

        # Suptitle: report the actual count plotted (no "Top N" framing — this
        # script always plots every available case).
        title_parts = [f'All {len(cases_to_plot)} Extracted Cases']
        title_parts.append(f'Best NRMSE: #{best_nrmse_case} ({best_nrmse_value:.4f})')
        if best_targets_case != best_nrmse_case:
            title_parts.append(f'Most targets: #{best_targets_case} ({max_satisfied}/{n_total})')
        if title_suffix:
            title_parts.append(title_suffix)
        fig.suptitle(' | '.join(title_parts), fontweight='bold', fontsize=14, y=0.98)

        plt.tight_layout(rect=[0, 0, 1, 0.96])

        # Save. Drop the DPI for the multi-phase rendering — at 600 DPI a
        # 519-year × 2729-line figure tries to allocate a multi-GB raster
        # buffer and matplotlib can die silently. 150 DPI is plenty for
        # screen viewing of a preview.
        if output_path is None:
            output_path = str(data_dir / 'ensemble_biomass_all_cases.png')
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        save_dpi = 150 if multi_phase else FIGURE_DPI
        logger.info(f"  saving to {output_path} (dpi={save_dpi}) ...")
        plt.savefig(output_path, dpi=save_dpi, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"Saved ensemble biomass figure: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"Failed to plot ensemble biomass: {e}")
        import traceback
        logger.error(traceback.format_exc())
        plt.close('all')
        return None


# =============================================================================
# Convenience: All-in-one (scan, rank, plot)
# =============================================================================

def plot_ensemble_biomass_from_dir(
    data_dir: str,
    targets: Dict[str, Dict],
    pft_ids: List[int],
    output_path: Optional[str] = None,
    top_n: int = 100,
    mtime_after_epoch: Optional[float] = None,
    **kwargs
) -> Optional[str]:
    """
    Convenience function: scan directory, rank cases, and plot.

    Combines get_available_cases + rank_cases_by_nrmse + plot_ensemble_biomass.

    Parameters
    ----------
    data_dir : str
        Directory containing extracted NetCDF files
    targets : dict
        Target definitions: {target_key: {'observed': float, 'uncertainty': float}}
    pft_ids : list of int
        PFT IDs for rows
    output_path : str, optional
        Path to save figure
    top_n : int
        Number of top cases to plot
    **kwargs
        Additional keyword arguments passed to plot_ensemble_biomass()

    Returns
    -------
    str or None
        Path to saved figure
    """
    data_dir = Path(data_dir)
    case_pattern = kwargs.get('case_pattern', _get_case_name_pattern())
    variables = kwargs.get('variables', ['leaf', 'fineroot'])
    year_start = kwargs.get('year_start', 1901)
    year_end = kwargs.get('year_end', 2019)
    obs_year = kwargs.get('obs_year', 2016)
    obs_month = kwargs.get('obs_month', 7)
    phases = kwargs.pop('phases', None) or TRANS_ONLY_PHASES

    # Scan for cases
    available_cases = get_available_cases(data_dir, case_pattern,
                                          mtime_after_epoch=mtime_after_epoch)
    if not available_cases:
        logger.warning(f"No cases found in {data_dir}")
        return None

    logger.info(f"Found {len(available_cases)} cases.")
    if len(phases) > 1:
        logger.info(f"Multi-phase mode: {[p[0] for p in phases]} "
                    f"({_phases_total_months(phases)} months total)")

    # Bulk parallel pre-load — done once, shared between rank and plot phases.
    n_workers = kwargs.pop('n_workers', 16)
    case_data = _load_all_case_data(
        available_cases, data_dir, variables,
        case_pattern=case_pattern,
        pft_ids=pft_ids,
        phases=phases,
        n_workers=n_workers,
    )

    # Rank (using cache)
    ranked = rank_cases_by_nrmse(
        data_dir, available_cases, targets, pft_ids,
        variables=variables, case_pattern=case_pattern,
        year_start=year_start, year_end=year_end,
        obs_year=obs_year, obs_month=obs_month,
        case_data=case_data,
        phases=phases,
    )

    if not ranked:
        logger.warning("No valid cases after ranking")
        return None

    logger.info(f"Ranked {len(ranked)} cases. Best: #{ranked[0]['case_num']} "
                f"(NRMSE={ranked[0]['composite_nrmse']:.4f})")

    # Plot (also using cache — avoids the second read of every NC)
    kwargs['case_data'] = case_data
    kwargs['phases'] = phases

    return plot_ensemble_biomass(
        data_dir=str(data_dir),
        ranked_cases=ranked,
        targets=targets,
        pft_ids=pft_ids,
        output_path=output_path,
        top_n=top_n,
        **kwargs
    )


# =============================================================================
# Standalone CLI
# =============================================================================

def main():
    """Standalone CLI entry point."""
    import argparse
    import os

    # Surface logger.info() messages so the parallel-load and ranking progress
    # is visible. Without this, the script appears to "hang" during the bulk
    # NC load — the tool silently skips logger.info by default.
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    parser = argparse.ArgumentParser(
        description='Plot every extracted ensemble case against validation targets')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='Directory containing extracted NetCDF files')
    parser.add_argument('--output-path', type=str, default=None,
                        help='Path to save the figure')
    parser.add_argument('--top-n', type=int, default=0,
                        help='Number of cases to plot (default: 0 = all available)')
    parser.add_argument('--plot-years', type=str, default='2010-2019',
                        help='Calendar-year range to plot (default: 2010-2019). '
                             'Ignored when --combined is set.')
    parser.add_argument('--combined', action='store_true',
                        help='Concatenate ADSP (yr 1-200) + RGSP (yr 201-400) + '
                             'TRANS (1901-2019) onto a single 519-year simulation '
                             'axis. Requires ADSP and RGSP NetCDFs to exist in '
                             'A2MC_EXTRACTED_DATA — run extract_ADSP_RGSP.py first.')
    parser.add_argument('--mtime-after', type=str, default=None,
                        help='Skip NCs with mtime <= this timestamp '
                             '(e.g. "2026-05-12 18:00:00" or "2026-05-12"). '
                             'Use to exclude stale leftover NCs from prior rounds.')
    parser.add_argument('--pft-ids', type=str, default=None,
                        help='Comma-separated PFT ids to plot (default 7,9,10). '
                             'One panel row per PFT.')
    parser.add_argument('--round-label', type=str, default=None,
                        help='Label for the auto-output filename, e.g. R4 '
                             '(default: derived from A2MC_ENSEMBLE_NAME suffix).')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Directory for the auto-named output figure '
                             '(default: $A2MC_USE_CASE_DIR/analysis).')
    args = parser.parse_args()

    # Resolve --mtime-after to epoch (local timezone, matching shell `find -newermt`)
    mtime_after_epoch = None
    if args.mtime_after:
        from datetime import datetime
        try:
            try:
                dt = datetime.strptime(args.mtime_after, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(args.mtime_after, "%Y-%m-%d")
            mtime_after_epoch = dt.timestamp()
            print(f"mtime filter: skip NCs with mtime <= {args.mtime_after} "
                  f"(epoch {mtime_after_epoch:.0f})")
        except ValueError as e:
            print(f"ERROR: --mtime-after format must be 'YYYY-MM-DD' or "
                  f"'YYYY-MM-DD HH:MM:SS', got '{args.mtime_after}': {e}")
            return

    # Get data directory. Prefer $A2MC_EXTRACTED_DATA — the canonical source set
    # by the site config — over the tools.config import path, which only works
    # when this script is run from the A2MC root with the package on sys.path.
    if args.data_dir:
        data_dir = args.data_dir
    elif os.environ.get('A2MC_EXTRACTED_DATA'):
        data_dir = os.environ['A2MC_EXTRACTED_DATA']
    else:
        try:
            from tools.config import config as a2mc_config
            data_dir = a2mc_config.EXTRACTED_DATA
        except ImportError:
            print("ERROR: $A2MC_EXTRACTED_DATA not set. "
                  "Source a2mc_config.sh and the site config first, "
                  "or pass --data-dir explicitly.")
            return

    # Parse plot years
    plot_years = args.plot_years.split('-')
    plot_year_start = int(plot_years[0])
    plot_year_end = int(plot_years[1]) if len(plot_years) > 1 else plot_year_start

    # Load site targets from the canonical YAML.
    # Each target carries an `original_std` field (field-measurement standard
    # deviation), which the production Phase-2 plot uses for the tall obs error
    # bar — distinct from the ±20% acceptance box. We mirror that here so the
    # preview plot matches reference figures (e.g.,
    # memory/phase_results/20260413_173425/phase2_screening/...).
    import yaml
    yaml_path = (Path(os.environ.get('A2MC_USE_CASE_DIR',
                       str(_A2MC_ROOT / 'use_cases' / 'Kougarok')))
                 / 'validation' / 'targets.yaml')
    with open(yaml_path) as f:
        yaml_doc = yaml.safe_load(f)
    targets = {}
    obs_uncertainty = {}
    for name, spec in yaml_doc['targets'].items():
        targets[name] = {
            'observed': float(spec['observed']),
            'uncertainty': float(spec['uncertainty']),
        }
        if 'original_std' in spec and spec['original_std'] is not None:
            obs_uncertainty[name] = float(spec['original_std'])
    print(f"Loaded {len(targets)} targets from {yaml_path}")
    print(f"  with {len(obs_uncertainty)} obs_std values for error bars")

    pft_ids = [int(x) for x in args.pft_ids.split(',')] if args.pft_ids else [7, 9, 10]

    phases = COMBINED_PHASES if args.combined else TRANS_ONLY_PHASES

    # top_n=0 means "plot every available case" — discover the count from the
    # data directory and pass it through. This makes "all extracted" the
    # default behavior without needing to know the count up-front.
    if args.top_n <= 0:
        from pathlib import Path as _P
        n_available = len(get_available_cases(_P(data_dir),
                                              mtime_after_epoch=mtime_after_epoch))
        if n_available == 0:
            print(f"ERROR: No extracted cases found in {data_dir}")
            return
        print(f"Discovered {n_available} extracted cases — plotting all of them.")
        top_n = n_available
    else:
        top_n = args.top_n

    # Default output filename uses the round + axis-mode + case count
    # convention so successive runs at different snapshots/rounds don't
    # silently overwrite each other (see memory: feedback_plot_filename_convention).
    if args.output_path is None:
        # round label: --round-label wins; else derive from the ensemble-name suffix
        if args.round_label:
            round_id = args.round_label
        else:
            ensemble_name = os.environ.get('A2MC_ENSEMBLE_NAME', '')
            if ensemble_name.endswith('_ADSPSupNP'):
                round_id = 'R4'
            elif ensemble_name.endswith('_RGSPsuplP'):
                round_id = 'R3'
            elif ensemble_name.endswith('_PrescribedP'):
                round_id = 'R4PrescP'
            elif 'Morris' in ensemble_name:
                round_id = 'R2'
            else:
                round_id = 'ensemble'
        axis_mode = 'combined' if args.combined else 'TRANS'
        out_name = f'{round_id}_{axis_mode}_{top_n}cases_ensemble.png'
        # output dir: --output-dir wins; else $A2MC_USE_CASE_DIR/analysis; else CWD
        if args.output_dir:
            out_dir = Path(args.output_dir)
        elif os.environ.get('A2MC_USE_CASE_DIR'):
            out_dir = Path(os.environ['A2MC_USE_CASE_DIR']) / 'analysis'
        else:
            out_dir = Path.cwd()
        out_dir.mkdir(parents=True, exist_ok=True)
        args.output_path = str(out_dir / out_name)
        print(f"Output path (default): {args.output_path}")

    fig_path = plot_ensemble_biomass_from_dir(
        data_dir=data_dir,
        targets=targets,
        pft_ids=pft_ids,
        output_path=args.output_path,
        top_n=top_n,
        mtime_after_epoch=mtime_after_epoch,
        plot_year_start=plot_year_start,
        plot_year_end=plot_year_end,
        obs_uncertainty=obs_uncertainty if obs_uncertainty else None,
        phases=phases,
    )

    if fig_path:
        print(f"\nSaved figure: {fig_path}")
    else:
        print("\nERROR: Failed to generate figure")


if __name__ == '__main__':
    main()
