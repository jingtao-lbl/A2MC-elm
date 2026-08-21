#!/usr/bin/env python3
"""Generate a parameter sample for Phase 0.

Reads a parameter list with bounds, runs the requested sampling design,
and writes:

  1. The N_cases x P sample matrix (one row per ensemble case, one column per parameter)
  2. The SALib problem definition (parameter names + bounds, human-readable)

Auto-detects the parameter list header so it works with both the existing
A2MC-style files (multi-line preamble, 'Symbol/Short and PFT#' column) and
a minimal 3-column format that a first-time user might write:

    name<TAB>lower<TAB>upper
    param1     0.1   1.0
    param2     0.5   2.0

All paths default to env vars set in $A2MC_SITE_CONFIG. Pass
--param-list-file / --output-matrix / --output-problem to override.

Three sampling methods are supported via --method. P below = number of
active parameters (the full list, or the subset when --screened-params
is used).

=== Morris (--method morris)
    One-at-a-time elementary effects screening. Good for ranking
    parameter importance (mu*, sigma) cheaply, even at high P.

    Knobs:
      --trajectories T  (default: $A2MC_N_TRAJECTORIES or 30)
      --num-levels K    (default: 8)
      --seed S          (default: 123)

    Sample count: N_cases = T * (P + 1)
      e.g., T=30, P=162 -> 30 * 163 = 4890 cases

    Output is consumed by phases/phase1_exploration/morris_sensitivity_analysis.py
    to compute mu, mu*, sigma per parameter.

    Example:
      python create_parameter_sample.py --method morris --trajectories 30 --num-levels 8

=== Sobol (--method sobol)
    Saltelli's variance-decomposition design, yields first-order (S_i),
    total-effect (S_Ti), and (optionally) second-order (S_ij) Sobol
    indices. Strong on parameter interaction structure; expensive at high P.

    Knobs:
      --n-samples N        (default: 1024 = 2^10)
      --seed S             (default: 123; passed to skip_values for sequence offset)
      --no-second-order    (skip S_ij; halves the sample count)

    Sample count: N_cases = N * (2P + 2)              [default; with S_ij]
                 N_cases = N * (P  + 2)              [--no-second-order]
      e.g., N=1024, P=162 -> 1024 * 326 = 333824 cases (full)
      e.g., N=1024, P=20  -> 1024 *  42 =  43008 cases (after screening)

    N should be a power of 2 (2^10..2^14 typical) for the Sobol' sequence
    to retain its low-discrepancy property. Non-power-of-2 N still works
    but degrades convergence and triggers a warning.

    For high-P problems (like Kougarok's 162), pair --method sobol with
    --screened-params FILE (top-K from a prior Morris mu* ranking) to
    keep the sample count tractable.

    Example:
      python create_parameter_sample.py --method sobol --n-samples 1024 \\
          --screened-params top20_from_morris.txt

=== LHS (--method lhs)
    Latin Hypercube — stratified random sample, ensures uniform coverage
    of each parameter's bound range. Good general-purpose design; no
    special structure for sensitivity decomposition.

    Knobs:
      --n-samples N  (default: 1024)
      --seed S       (default: 123)

    Sample count: N_cases = N
      e.g., N=1024, P=162 -> 1024 cases

    Example:
      python create_parameter_sample.py --method lhs --n-samples 1024

=== Screening (Sobol/LHS only): --screened-params FILE
    File lists parameter names (one per line, # comments) that should
    vary. All other parameters take their Default_Value (or midpoint of
    bounds, if no default column). The output matrix still has all P
    columns so downstream tooling (generate_parameter_files.py) is
    unchanged — non-screened columns are simply constant.

=== Defaults from environment
    --method               $A2MC_SAMPLING_SCHEME  (default: 'morris')
    --trajectories         $A2MC_N_TRAJECTORIES   (default: 30)
    --param-list-file      $A2MC_PARAM_LIST_FILE
    --output-matrix        $A2MC_ENSEMBLE_MATRIX_FILE
    --output-problem       $A2MC_SALIB_PROBLEM_FILE

=== Typical first-time-user invocation
    source a2mc_config.sh
    source use_cases/<site>/config/<round>_config.sh
    python phases/phase0_design/create_parameter_sample.py
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

# Make `from tools.* import ...` resolve when this file is run as a script (repo root on sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# SALib is the sampling backend. Import lazily so --help works without it.


# ---------------------------------------------------------------------------
# Parameter list parsing
# ---------------------------------------------------------------------------

def _detect_header_row(path: Path) -> int:
    """Return the 0-based line index of the header row.

    The header is the first line that contains both 'Lower_Bound' and
    'Upper_Bound' (case-insensitive match also accepts 'lower'/'upper').
    Raises ValueError if no header is found.
    """
    with path.open() as f:
        for i, line in enumerate(f):
            lower = line.lower()
            has_lower = ('lower_bound' in lower) or ('lower' in lower.split())
            has_upper = ('upper_bound' in lower) or ('upper' in lower.split())
            if has_lower and has_upper:
                return i
    raise ValueError(
        f"Could not find a header row containing 'Lower_Bound' and 'Upper_Bound' "
        f"in {path}. Expected the first 'real' (non-preamble) line to be a "
        f"tab- or comma-separated header."
    )


def _detect_delimiter(line: str) -> str:
    """Pick the most likely delimiter from a header line (tab beats comma)."""
    if '\t' in line:
        return '\t'
    if ',' in line:
        return ','
    return r'\s+'  # whitespace fallback


def _find_name_column(columns: list[str]) -> str:
    """Find the parameter-name column among common variants.

    Tries (in order): exact match on common names, then any column whose
    name starts with 'symbol' or 'name'.
    """
    candidates = [
        'name', 'Name', 'parameter', 'Parameter',
        'Symbol/Short and PFT#', 'symbol_pft', 'symbol',
    ]
    for c in candidates:
        if c in columns:
            return c
    for col in columns:
        lc = col.lower()
        if lc.startswith('symbol') or lc.startswith('name') or lc.startswith('parameter'):
            return col
    raise ValueError(
        f"Could not find a parameter-name column among {columns}. "
        f"Expected one of: name, parameter, 'Symbol/Short and PFT#'."
    )


def _find_bound_columns(columns: list[str]) -> Tuple[str, str]:
    """Find the lower/upper bound columns by common name variants."""
    lower_candidates = ['Lower_Bound', 'lower_bound', 'lower', 'min', 'Min']
    upper_candidates = ['Upper_Bound', 'upper_bound', 'upper', 'max', 'Max']
    lower = next((c for c in lower_candidates if c in columns), None)
    upper = next((c for c in upper_candidates if c in columns), None)
    if lower is None or upper is None:
        raise ValueError(
            f"Could not find both lower and upper bound columns among {columns}. "
            f"Expected pairs like (Lower_Bound, Upper_Bound) or (lower, upper)."
        )
    return lower, upper


def _is_new_format(path: Path) -> bool:
    """True for the docs/37 explicit-column CSV (fates_name,pft,organ,...) vs the legacy
    shorthand list. Detected by the header carrying the fates_name + pft + organ columns."""
    try:
        with path.open() as f:
            header = f.readline()
    except OSError:
        return False
    cols = {c.strip().lower() for c in header.replace('\t', ',').split(',')}
    return {'fates_name', 'pft', 'organ'}.issubset(cols)


def parse_param_list(path: Path) -> Tuple[list[str], np.ndarray, np.ndarray]:
    """Parse a parameter list file into (names, lower, upper) arrays.

    For the new explicit-column CSV (docs/37) the canonical loader is the sole parser and
    `names` are canonical ids. For the legacy shorthand list, auto-detect header/delimiter/
    columns (names = the shorthand). Filters non-data rows.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Parameter list file not found: {path}")

    # docs/37 explicit-column CSV → canonical loader (single source of truth)
    if _is_new_format(path):
        from tools.param_spec import load_param_spec
        specs = load_param_spec(path)
        names = [s.canonical_id for s in specs]
        lower = np.array([s.lower for s in specs], dtype=float)
        upper = np.array([s.upper for s in specs], dtype=float)
        if not names:
            raise ValueError(f"No parameters parsed from {path}")
        return names, lower, upper

    skiprows = _detect_header_row(path)
    with path.open() as f:
        header_line = ''
        for i, line in enumerate(f):
            if i == skiprows:
                header_line = line
                break
    delim = _detect_delimiter(header_line)

    df = pd.read_csv(path, sep=delim, skiprows=skiprows, engine='python')
    df.columns = [c.strip() for c in df.columns]

    name_col = _find_name_column(list(df.columns))
    lower_col, upper_col = _find_bound_columns(list(df.columns))

    # Coerce bounds to numeric; rows with non-numeric bounds become NaN and are dropped
    df[lower_col] = pd.to_numeric(df[lower_col], errors='coerce')
    df[upper_col] = pd.to_numeric(df[upper_col], errors='coerce')
    df = df.dropna(subset=[lower_col, upper_col, name_col]).reset_index(drop=True)

    names = [str(n).strip() for n in df[name_col].tolist()]
    lower = df[lower_col].to_numpy(dtype=float)
    upper = df[upper_col].to_numpy(dtype=float)

    # Sanity checks
    if len(names) == 0:
        raise ValueError(f"No parameters parsed from {path}")
    if any(l >= u for l, u in zip(lower, upper)):
        bad = [(n, l, u) for n, l, u in zip(names, lower, upper) if l >= u]
        raise ValueError(
            f"Found {len(bad)} parameters with lower >= upper. "
            f"First offender: {bad[0]}"
        )

    return names, lower, upper


# ---------------------------------------------------------------------------
# Sampling backends
# ---------------------------------------------------------------------------

def sample_morris(
    problem: dict,
    trajectories: int,
    num_levels: int,
    seed: int,
) -> np.ndarray:
    """Generate a Morris sample. Returns shape (trajectories * (P+1), P)."""
    from SALib.sample.morris import sample as morris_sample  # lazy import
    X = morris_sample(
        problem,
        N=trajectories,
        num_levels=num_levels,
        optimal_trajectories=None,
        local_optimization=False,
        seed=seed,
    )
    return X


def sample_sobol(
    problem: dict,
    n_samples: int,
    seed: int,
    calc_second_order: bool = True,
) -> np.ndarray:
    """Generate a Saltelli-Sobol sample. Returns shape (N*(2P+2), P)
    if calc_second_order else (N*(P+2), P).
    """
    # SALib 1.5.2 ships TWO Sobol samplers, and only the current one has a seed:
    #   SALib.sample.sobol.sample     (problem, N, *, calc_second_order, scramble,
    #                                  skip_values, seed)   <- current
    #   SALib.sample.saltelli.sample  (problem, N, calc_second_order, skip_values)
    #                                                       <- legacy, DeprecationWarning
    # This called the legacy path and passed `skip_values=seed`. `skip_values` is a
    # Sobol-sequence OFFSET, not a seed: it must be a power of two >= N, so a seed
    # like 42 either errors or silently shifts the sequence instead of seeding it.
    # `np.random.seed()` did not rescue it either — the Sobol generator does not
    # draw from numpy's global RNG. The design was effectively unseeded.
    from SALib.sample.sobol import sample as sobol_sample  # lazy import
    X = sobol_sample(
        problem,
        N=n_samples,
        calc_second_order=calc_second_order,
        scramble=True,
        seed=seed,
    )
    return X


def sample_lhs(problem: dict, n_samples: int, seed: int) -> np.ndarray:
    """Generate a Latin Hypercube sample. Returns shape (N, P)."""
    from SALib.sample.latin import sample as latin_sample  # lazy import
    X = latin_sample(problem, N=n_samples, seed=seed)
    return X


# ---------------------------------------------------------------------------
# Screening (Sobol/LHS on a parameter subset, with defaults for the rest)
# ---------------------------------------------------------------------------

def load_screened_params(path: Path) -> list[str]:
    """Read a screened-params file (one parameter name per line, '#' comments).

    Returns the list of active parameter names in file order.
    """
    if not path.is_file():
        raise FileNotFoundError(f"Screened params file not found: {path}")
    active = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        active.append(line)
    if not active:
        raise ValueError(f"No parameter names in {path} (only blanks/comments)")
    return active


def _find_default_column(columns: list[str]) -> str | None:
    """Find a 'Default_Value' column (variants: default, Default, default_value)."""
    for c in ['Default_Value', 'default_value', 'Default', 'default']:
        if c in columns:
            return c
    return None


def parse_defaults(path: Path, names: list[str], lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    """Return a default value for each parameter, in `names` order.

    Uses a `Default_Value` column if present in the parameter list file,
    else falls back to the midpoint of (lower, upper) for missing entries.
    """
    # docs/37 explicit-column CSV → canonical loader, defaults keyed by canonical id
    if _is_new_format(path):
        from tools.param_spec import load_param_spec
        by_id = {s.canonical_id: s.default for s in load_param_spec(path)}
        return np.array([by_id.get(n, (lo + hi) / 2.0)
                         for n, lo, hi in zip(names, lower, upper)], dtype=float)

    skiprows = _detect_header_row(path)
    with path.open() as f:
        header_line = next(line for i, line in enumerate(f) if i == skiprows)
    delim = _detect_delimiter(header_line)
    df = pd.read_csv(path, sep=delim, skiprows=skiprows, engine='python')
    df.columns = [c.strip() for c in df.columns]
    name_col = _find_name_column(list(df.columns))
    default_col = _find_default_column(list(df.columns))

    # Filter to parameter rows (same logic as parse_param_list)
    lower_col, upper_col = _find_bound_columns(list(df.columns))
    df[lower_col] = pd.to_numeric(df[lower_col], errors='coerce')
    df[upper_col] = pd.to_numeric(df[upper_col], errors='coerce')
    df = df.dropna(subset=[lower_col, upper_col, name_col]).reset_index(drop=True)

    if default_col is None:
        # No default column: midpoint
        return (lower + upper) / 2.0

    df[default_col] = pd.to_numeric(df[default_col], errors='coerce')
    file_defaults = dict(zip(df[name_col].astype(str).str.strip(), df[default_col]))
    out = np.empty(len(names))
    for i, name in enumerate(names):
        v = file_defaults.get(name)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            out[i] = (lower[i] + upper[i]) / 2.0
        else:
            out[i] = float(v)
    return out


def apply_screening(
    X_active: np.ndarray,
    active_names: list[str],
    all_names: list[str],
    defaults: np.ndarray,
) -> np.ndarray:
    """Expand an N x len(active) sample into an N x len(all_names) matrix.

    Active columns receive the sampled values; non-active columns receive
    the default for each parameter.
    """
    name_to_idx = {n: i for i, n in enumerate(all_names)}
    missing = [n for n in active_names if n not in name_to_idx]
    if missing:
        raise ValueError(
            f"Screened-params file lists {len(missing)} parameter(s) not in "
            f"the parameter list. First missing: {missing[:5]}"
        )
    n_cases = X_active.shape[0]
    X_full = np.tile(defaults, (n_cases, 1))
    for j_active, name in enumerate(active_names):
        X_full[:, name_to_idx[name]] = X_active[:, j_active]
    return X_full


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def write_matrix(X: np.ndarray, path: Path) -> None:
    """Write the N x P sample matrix as whitespace-separated floats."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, X)


def write_problem_text(
    path: Path,
    method: str,
    method_args: dict,
    names: list[str],
    lower: np.ndarray,
    upper: np.ndarray,
) -> None:
    """Write the SALib problem definition in the text format that
    `phases/phase1_exploration/morris_sensitivity_analysis.py::load_salib_problem_from_file`
    reads.
    """
    n = len(names)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as f:
        f.write(f"SALib Problem Definition - {n} Parameters ({method})\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"num_vars: {n}\n\n")
        f.write(f"Method: {method}\n")
        for k, v in method_args.items():
            f.write(f"  {k}: {v}\n")
        f.write("\n")
        f.write("Parameter names:\n")
        for i, name in enumerate(names, 1):
            f.write(f"  {i:3d}. {name}\n")
        f.write("\nBounds:\n")
        for i, (name, lo, up) in enumerate(zip(names, lower, upper), 1):
            f.write(f"  {i:3d}. {name:30s}  [{lo:.6g}, {up:.6g}]\n")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Phase 0 parameter sample (Morris/Sobol/LHS).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--method', default=os.environ.get('A2MC_SAMPLING_SCHEME', 'morris'),
                        choices=['morris', 'sobol', 'lhs'],
                        help="Sampling method (default: $A2MC_SAMPLING_SCHEME or 'morris')")
    parser.add_argument('--trajectories', type=int, default=None,
                        help="[morris] Number of trajectories (default: $A2MC_N_TRAJECTORIES or 30)")
    parser.add_argument('--num-levels', type=int, default=8,
                        help="[morris] Number of grid levels (default: 8)")
    parser.add_argument('--n-samples', type=int, default=1024,
                        help="[sobol/lhs] Number of samples (default: 1024 = 2^10). "
                             "For Sobol, N should be a power of 2 (typically 2^10..2^14) so the "
                             "underlying Sobol sequence retains its low-discrepancy properties. "
                             "LHS has no such requirement.")
    parser.add_argument('--seed', type=int, default=123,
                        help="Random seed (default: 123)")
    parser.add_argument('--no-second-order', action='store_true',
                        help="[sobol] Skip second-order indices (smaller sample: N*(P+2) instead of N*(2P+2))")
    parser.add_argument('--screened-params', type=Path, default=None,
                        help="[sobol/lhs] File listing parameter names (one per line) to keep active. "
                             "Non-listed parameters take their Default_Value (or midpoint if no default).")
    parser.add_argument('--param-list-file', type=Path, default=None,
                        help="Parameter list file (default: $A2MC_PARAM_LIST_FILE)")
    parser.add_argument('--output-matrix', type=Path, default=None,
                        help="Output sample matrix path (default: $A2MC_ENSEMBLE_MATRIX_FILE)")
    parser.add_argument('--output-problem', type=Path, default=None,
                        help="Output SALib problem path (default: $A2MC_SALIB_PROBLEM_FILE)")
    parser.add_argument('--dry-run', action='store_true',
                        help="Parse inputs and report what would be done; don't write outputs")
    args = parser.parse_args()

    # ----- resolve inputs from env vars -----
    param_list = args.param_list_file or _env_path('A2MC_PARAM_LIST_FILE')
    out_matrix = args.output_matrix or _env_path('A2MC_ENSEMBLE_MATRIX_FILE')
    out_problem = args.output_problem or _env_path('A2MC_SALIB_PROBLEM_FILE')

    missing = []
    if param_list is None:
        missing.append('$A2MC_PARAM_LIST_FILE (or --param-list-file)')
    if out_matrix is None:
        missing.append('$A2MC_ENSEMBLE_MATRIX_FILE (or --output-matrix)')
    if out_problem is None:
        missing.append('$A2MC_SALIB_PROBLEM_FILE (or --output-problem)')
    if missing:
        print("ERROR: missing required path(s):", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        print("\nSource your site config first:", file=sys.stderr)
        print("  source a2mc_config.sh", file=sys.stderr)
        print("  source use_cases/<site>/config/<round>_config.sh", file=sys.stderr)
        return 2

    trajectories = args.trajectories
    if trajectories is None:
        env_n = os.environ.get('A2MC_N_TRAJECTORIES', '')
        trajectories = int(env_n) if env_n.isdigit() else 30

    # ----- parse parameter list -----
    print(f"Reading parameter list: {param_list}")
    names, lower, upper = parse_param_list(param_list)
    n_params = len(names)
    print(f"  -> parsed {n_params} parameters")

    # Build the SALib problem — either over all parameters, or over the
    # screened subset when --screened-params is given (sobol/lhs only).
    if args.screened_params is not None:
        if args.method == 'morris':
            print("ERROR: --screened-params is only supported for sobol/lhs.", file=sys.stderr)
            print("       Morris already does its own one-at-a-time sweep over all parameters.", file=sys.stderr)
            return 2
        active_names = load_screened_params(args.screened_params)
        print(f"Screening: {len(active_names)} active parameters from {args.screened_params}")
        missing = [n for n in active_names if n not in names]
        if missing:
            print(f"ERROR: {len(missing)} screened parameter(s) not in the parameter list. "
                  f"First missing: {missing[:5]}", file=sys.stderr)
            return 2
        name_to_idx = {n: i for i, n in enumerate(names)}
        active_idx = [name_to_idx[n] for n in active_names]
        active_lower = lower[active_idx]
        active_upper = upper[active_idx]
        sampling_problem = {
            'num_vars': len(active_names),
            'names': active_names,
            'bounds': [[lo, up] for lo, up in zip(active_lower, active_upper)],
        }
        defaults = parse_defaults(param_list, names, lower, upper)
        print(f"  -> non-screened parameters take Default_Value or midpoint")
    else:
        active_names = names
        sampling_problem = {
            'num_vars': n_params,
            'names': names,
            'bounds': [[lo, up] for lo, up in zip(lower, upper)],
        }
        defaults = None

    # Predicted sample count (printed in each method's branch below).
    # Sample count is determined by the method's own knobs:
    #   morris: trajectories * (p_eff + 1)
    #   sobol:  n_samples * (2*p_eff + 2)   [or n_samples * (p_eff + 2) with --no-second-order]
    #   lhs:    n_samples
    # where p_eff = number of parameters being sampled (full count, or
    # the active subset when --screened-params is used).
    p_eff = sampling_problem['num_vars']
    if args.method == 'morris':
        predicted = trajectories * (p_eff + 1)
    elif args.method == 'sobol':
        predicted = args.n_samples * (2 * p_eff + 2) if not args.no_second_order else args.n_samples * (p_eff + 2)
    else:  # lhs
        predicted = args.n_samples

    # ----- sample -----
    method_args = {}
    if args.method == 'morris':
        method_args = {
            'trajectories': trajectories,
            'num_levels': args.num_levels,
            'seed': args.seed,
        }
        print(f"Sampling: Morris, N={trajectories} trajectories, num_levels={args.num_levels}, seed={args.seed}")
        print(f"  -> expected sample count: {trajectories} x ({p_eff}+1) = {predicted}")
        if args.dry_run:
            print("[DRY RUN] would generate Morris sample.")
            return 0
        X = sample_morris(sampling_problem, trajectories, args.num_levels, args.seed)
    elif args.method == 'sobol':
        calc_second = not args.no_second_order
        method_args = {
            'n_samples': args.n_samples,
            'seed': args.seed,
            'calc_second_order': calc_second,
        }
        # Sobol' sequence has its low-discrepancy property when N = 2^k.
        # Non-power-of-2 N still produces a valid sample, but convergence
        # of the Sobol indices degrades.
        n = args.n_samples
        is_pow2 = n > 0 and (n & (n - 1)) == 0
        if not is_pow2:
            import math
            nearest_lo = 1 << int(math.log2(n))
            nearest_hi = nearest_lo << 1
            print(f"WARNING: --n-samples {n} is not a power of 2. For Sobol, "
                  f"prefer 2^k (e.g., {nearest_lo} or {nearest_hi}). "
                  f"Non-power-of-2 N produces a valid sample but with degraded "
                  f"low-discrepancy properties.", file=sys.stderr)
        size_formula = f"{args.n_samples}*(2*{p_eff}+2)" if calc_second else f"{args.n_samples}*({p_eff}+2)"
        print(f"Sampling: Sobol (Saltelli), N={args.n_samples}, calc_second_order={calc_second}, seed={args.seed}")
        print(f"  -> expected sample count: {size_formula} = {predicted}")
        if args.dry_run:
            print("[DRY RUN] would generate Sobol sample.")
            return 0
        X = sample_sobol(sampling_problem, args.n_samples, args.seed, calc_second_order=calc_second)
    elif args.method == 'lhs':
        method_args = {'n_samples': args.n_samples, 'seed': args.seed}
        print(f"Sampling: LHS, N={args.n_samples}, seed={args.seed}")
        if args.dry_run:
            print(f"[DRY RUN] would generate LHS sample, {predicted} cases.")
            return 0
        X = sample_lhs(sampling_problem, args.n_samples, args.seed)
    else:
        raise AssertionError(f"unreachable method: {args.method}")

    # If screened, expand back to full parameter count
    if defaults is not None:
        X = apply_screening(X, active_names, names, defaults)
        method_args['screened_params'] = str(args.screened_params)
        method_args['n_active'] = len(active_names)

    n_cases = X.shape[0]
    print(f"  -> generated {n_cases} cases x {X.shape[1]} parameters")

    # ----- write outputs -----
    print(f"Writing sample matrix: {out_matrix}")
    write_matrix(X, out_matrix)
    print(f"  -> sha256: {_sha256(out_matrix)[:16]}...")

    print(f"Writing SALib problem: {out_problem}")
    write_problem_text(out_problem, args.method, method_args, names, lower, upper)

    print()
    print("=" * 60)
    print("Sampling complete.")
    print("=" * 60)
    print(f"  parameters:  {n_params}")
    print(f"  cases:       {n_cases}")
    print(f"  method:      {args.method}")
    print(f"  matrix:      {out_matrix}")
    print(f"  problem:     {out_problem}")
    print()
    print("Next step: materialize per-case parameter NetCDF files")
    print("  python phases/phase0_design/create_parameter_files.py")
    return 0


def _env_path(var: str) -> Path | None:
    v = os.environ.get(var)
    return Path(v) if v else None


if __name__ == '__main__':
    sys.exit(main())
