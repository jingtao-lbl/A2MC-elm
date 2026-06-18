#!/usr/bin/env python3
"""Apply a global parameter override to every FATES parameter file in a directory.

A2MC's `generate_parameter_files.py` produces one parameter file per ensemble
case that encodes the Morris/Sobol/LHS draws of all sampled parameters.
`create_subset_replay.py` extends this by copying a *ranked subset* of those
files and applying a single global override per file
(e.g., `fates_cnp_prescribed_puptake=1.0`).

This script is the **full-ensemble** equivalent of subset_replay: take ALL
per-case parameter files from a source dir, copy each to a destination dir,
and apply the same override(s) in place. No ranking, no source workflow_state
JSON required.

Format support (v2.100+): per-file format is auto-detected via
`tools/modify_fates_parameters.detect_format()`. Source files can be either
NetCDF (api-31 and earlier) or JSON (api-43+). The destination format
matches the source — `shutil.copy2()` preserves bytes, then the override
is applied through the format-appropriate backend.

Override semantics: set EVERY element of the named parameter to the given
scalar value. Same behavior as the NC original: per-PFT, per-organ, etc.
distinctions are NOT preserved — the override is global across all
dimensions of the parameter.

Use case (R5 design, May 2026): R3/R4 already produced 4890 per-case Morris
NCs. R5 wants the SAME Morris X matrix but with prescribed P uptake enabled
— i.e., the same files with `fates_cnp_prescribed_puptake=1.0` baked in.
This script produces R5's per-case files in ~3-5 minutes without re-running
Morris.

Usage:
    python phases/phase0_design/apply_param_override.py \\
        --source-dir /path/to/source_param_dir \\
        --dest-dir   /path/to/dest_param_dir \\
        --pattern    "fates_params_..._En{N}.nc" \\
        --range      1-4890 \\
        --override   fates_cnp_prescribed_puptake=1.0

    # JSON inputs (api-43+):
    python phases/phase0_design/apply_param_override.py \\
        --source-dir /path/to/source_json_dir \\
        --dest-dir   /path/to/dest_json_dir \\
        --pattern    "fates_params_..._En{N}.json" \\
        --range      1-4890 \\
        --override   fates_cnp_prescribed_puptake=1.0

    # Multiple overrides:
    python phases/phase0_design/apply_param_override.py ... \\
        --override fates_cnp_prescribed_puptake=1.0 \\
        --override fates_cnp_prescribed_nuptake=1.0

    # Limit to first 10 for testing:
    python phases/phase0_design/apply_param_override.py ... --range 1-10

    # Verify-only mode (don't write, just check what's in source files):
    python phases/phase0_design/apply_param_override.py ... --verify-only

Exit codes:
    0 - success
    1 - any file failed to copy / apply override
    2 - setup error (missing source dir, bad pattern, etc.)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
import time
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path

import netCDF4 as nc
import numpy as np

# Bring tools/ onto sys.path so we can reuse the format detector
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.modify_fates_parameters import detect_format  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_range(range_str: str) -> list[int]:
    """Parse '1-100,200,300-310' into a sorted list of case numbers."""
    cases = set()
    for token in range_str.split(','):
        token = token.strip()
        if not token:
            continue
        if '-' in token:
            lo, hi = token.split('-', 1)
            cases.update(range(int(lo), int(hi) + 1))
        else:
            cases.add(int(token))
    return sorted(cases)


def parse_override(override: str) -> tuple[str, float]:
    """Parse 'param=value' into (param, value)."""
    if '=' not in override:
        raise ValueError(f"Override must be 'param=value', got: {override}")
    key, val = override.split('=', 1)
    return key.strip(), float(val.strip())


def src_path(source_dir: Path, pattern: str, case_num: int) -> Path:
    """Build the source path for a given case number."""
    return source_dir / pattern.replace('{N}', str(case_num))


def dst_path(dest_dir: Path, pattern: str, case_num: int) -> Path:
    """Build the destination path for a given case number."""
    return dest_dir / pattern.replace('{N}', str(case_num))


# --- NC backend (original behavior) ----------------------------------------

def _apply_in_place_nc(nc_file: Path, overrides: dict[str, float]) -> dict:
    """Open NC in r+ mode and set each override. Returns per-override result."""
    result = {}
    with nc.Dataset(str(nc_file), 'r+') as ds:
        for key, val in overrides.items():
            if key not in ds.variables:
                result[key] = {'status': 'missing_var', 'old': None, 'new': val}
                continue
            old_arr = ds.variables[key][:].copy()
            ds.variables[key][:] = val
            new_arr = ds.variables[key][:]
            result[key] = {
                'status': 'applied',
                'old_first': float(old_arr.flatten()[0]),
                'old_all_match': bool((old_arr == old_arr.flatten()[0]).all()),
                'new': float(new_arr.flatten()[0]),
                'shape': list(new_arr.shape),
            }
    return result


def _inspect_nc(nc_file: Path, override_keys: list[str]) -> dict:
    """Verify-only inspect: read current values without modifying the file."""
    snapshot = {}
    with nc.Dataset(str(nc_file), 'r') as ds:
        for key in override_keys:
            if key in ds.variables:
                arr = ds.variables[key][:]
                snapshot[key] = {
                    'first': float(arr.flatten()[0]),
                    'all_match': bool((arr == arr.flatten()[0]).all()),
                    'shape': list(arr.shape),
                }
            else:
                snapshot[key] = {'status': 'missing_var'}
    return snapshot


# --- JSON backend (v2.100, api-43+) ----------------------------------------

def _fill_value(data, val):
    """Recursively replace every scalar in a nested list with `val`."""
    if isinstance(data, list):
        return [_fill_value(x, val) for x in data]
    return val


def _apply_in_place_json(json_file: Path, overrides: dict[str, float]) -> dict:
    """Open JSON, set every element of each override param to its scalar value."""
    result = {}
    with json_file.open('r') as f:
        doc = json.load(f)
    params = doc.get('parameters', doc)  # graceful for older shapes
    for key, val in overrides.items():
        if key not in params:
            result[key] = {'status': 'missing_var', 'old': None, 'new': val}
            continue
        old_data = params[key].get('data')
        # Compute introspection info from the existing data
        old_arr = np.array(old_data) if old_data is not None else np.array([])
        old_first = float(old_arr.flatten()[0]) if old_arr.size else float('nan')
        old_all_match = bool((old_arr == old_arr.flatten()[0]).all()) if old_arr.size else True
        # Replace every element with the scalar
        new_data = _fill_value(old_data, val) if isinstance(old_data, list) else val
        params[key]['data'] = new_data
        result[key] = {
            'status': 'applied',
            'old_first': old_first,
            'old_all_match': old_all_match,
            'new': float(val),
            'shape': list(old_arr.shape),
        }
    with json_file.open('w') as f:
        json.dump(doc, f, indent=2)
    return result


def _inspect_json(json_file: Path, override_keys: list[str]) -> dict:
    """Verify-only inspect of JSON: read current values without modifying."""
    snapshot = {}
    with json_file.open('r') as f:
        doc = json.load(f)
    params = doc.get('parameters', doc)
    for key in override_keys:
        if key not in params:
            snapshot[key] = {'status': 'missing_var'}
            continue
        data = params[key].get('data')
        arr = np.array(data) if data is not None else np.array([])
        if arr.size == 0:
            snapshot[key] = {'first': float('nan'), 'all_match': True, 'shape': []}
        else:
            snapshot[key] = {
                'first': float(arr.flatten()[0]),
                'all_match': bool((arr == arr.flatten()[0]).all()),
                'shape': list(arr.shape),
            }
    return snapshot


# --- Format-dispatching public API -----------------------------------------

def apply_in_place(param_file: Path, overrides: dict[str, float]) -> dict:
    """Dispatch to the NC or JSON backend based on file format."""
    fmt = detect_format(param_file)
    if fmt == 'json':
        return _apply_in_place_json(param_file, overrides)
    return _apply_in_place_nc(param_file, overrides)


def inspect(param_file: Path, override_keys: list[str]) -> dict:
    """Verify-only inspect, dispatched on file format."""
    fmt = detect_format(param_file)
    if fmt == 'json':
        return _inspect_json(param_file, override_keys)
    return _inspect_nc(param_file, override_keys)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def process_one(args) -> dict:
    """Worker: copy + apply override for one case. Returns a result dict."""
    case_num, source_dir, dest_dir, pattern, overrides, verify_only = args
    src = src_path(source_dir, pattern, case_num)
    dst = dst_path(dest_dir, pattern, case_num)
    if not src.is_file():
        return {'case_num': case_num, 'status': 'src_missing', 'src': str(src)}
    if verify_only:
        try:
            snapshot = inspect(src, list(overrides.keys()))
            return {'case_num': case_num, 'status': 'verified', 'snapshot': snapshot}
        except Exception as e:
            return {'case_num': case_num, 'status': 'verify_error', 'error': str(e)}
    try:
        shutil.copy2(src, dst)
        applied = apply_in_place(dst, overrides)
        return {'case_num': case_num, 'status': 'ok', 'applied': applied}
    except Exception as e:
        return {'case_num': case_num, 'status': 'error', 'error': str(e),
                'src': str(src), 'dst': str(dst)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy parameter files from source dir, apply global "
                    "overrides, write to dest dir. NC or JSON (auto-detected).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--source-dir', type=Path, required=True,
                        help="Directory containing source per-case parameter files")
    parser.add_argument('--dest-dir', type=Path, required=True,
                        help="Directory to write modified per-case parameter files")
    parser.add_argument('--pattern', type=str, required=True,
                        help="Filename pattern with {N} placeholder, "
                             "e.g., 'fates_params_..._En{N}.nc' or "
                             "'fates_params_..._En{N}.json'")
    parser.add_argument('--range', type=str, required=True,
                        help="Case range, e.g., '1-4890' or '1-100,500,1000-1010'")
    parser.add_argument('--override', action='append', required=True,
                        help="Override in 'param=value' form. Can be repeated.")
    parser.add_argument('--parallel', type=int, default=16,
                        help="Number of parallel workers (default 16)")
    parser.add_argument('--verify-only', action='store_true',
                        help="Don't copy/write; just inspect source files for the override vars")
    parser.add_argument('--manifest', type=Path, default=None,
                        help="Path to write a JSON manifest "
                             "(default: {dest_dir}/override_manifest.json)")
    args = parser.parse_args()

    # --- Parse + validate ---
    cases = parse_range(args.range)
    if not cases:
        logger.error("No cases in range")
        return 2
    overrides = {}
    for o in args.override:
        try:
            k, v = parse_override(o)
            overrides[k] = v
        except ValueError as e:
            logger.error(str(e))
            return 2
    if not args.source_dir.is_dir():
        logger.error(f"Source dir not found: {args.source_dir}")
        return 2
    if not args.verify_only:
        args.dest_dir.mkdir(parents=True, exist_ok=True)

    # --- Banner ---
    logger.info("=" * 70)
    logger.info(f"{'VERIFY MODE' if args.verify_only else 'APPLY MODE'}")
    logger.info("=" * 70)
    logger.info(f"Source dir:  {args.source_dir}")
    logger.info(f"Dest dir:    {args.dest_dir if not args.verify_only else '(N/A in verify mode)'}")
    logger.info(f"Pattern:     {args.pattern}")
    logger.info(f"Cases:       {len(cases)} (first 5: {cases[:5]}, last 5: {cases[-5:]})")
    logger.info(f"Overrides:   {overrides}")
    logger.info(f"Parallel:    {args.parallel}")
    logger.info("=" * 70)

    # --- Process ---
    t0 = time.time()
    tasks = [(n, args.source_dir, args.dest_dir, args.pattern, overrides, args.verify_only)
             for n in cases]
    results = []
    with Pool(processes=args.parallel) as pool:
        for i, res in enumerate(pool.imap_unordered(process_one, tasks, chunksize=8)):
            results.append(res)
            if (i + 1) % 200 == 0 or (i + 1) == len(cases):
                elapsed = time.time() - t0
                logger.info(f"  {i + 1}/{len(cases)}  elapsed={elapsed:.1f}s")

    # --- Tally + early-exit reporting ---
    by_status = {}
    for r in results:
        by_status.setdefault(r['status'], 0)
        by_status[r['status']] += 1
    logger.info(f"\nResult tally: {by_status}")

    failures = [r for r in results if r['status'] not in ('ok', 'verified')]
    if failures:
        logger.error(f"Found {len(failures)} failure(s). First 5:")
        for r in failures[:5]:
            logger.error(f"  case {r['case_num']}: {r}")

    # --- Spot-check first result for sanity ---
    if results:
        sample = next((r for r in results if r['status'] in ('ok', 'verified')), None)
        if sample:
            logger.info(f"\nSpot-check (case {sample['case_num']}):")
            for k, v in sample.get('applied', sample.get('snapshot', {})).items():
                logger.info(f"  {k}: {v}")

    # --- Write manifest ---
    if not args.verify_only:
        manifest_path = args.manifest or (args.dest_dir / 'override_manifest.json')
        manifest = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'source_dir': str(args.source_dir),
            'dest_dir': str(args.dest_dir),
            'pattern': args.pattern,
            'n_cases': len(cases),
            'n_ok': by_status.get('ok', 0),
            'n_failed': sum(v for k, v in by_status.items() if k not in ('ok', 'verified')),
            'overrides': overrides,
            'failures': failures[:50],
            'elapsed_sec': round(time.time() - t0, 2),
        }
        with manifest_path.open('w') as f:
            json.dump(manifest, f, indent=2, default=str)
        logger.info(f"\nManifest written: {manifest_path}")

    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
