#!/usr/bin/env python3
"""Apply a global parameter override to every FATES parameter NC in a directory.

A2MC's `create_morris_ensemble.py` produces one parameter NC per Morris case
that encodes the Morris draws of all sampled parameters. `create_subset_replay.py`
extends this by copying a *ranked subset* of those NCs and applying a single
global override per file (e.g., fates_cnp_prescribed_puptake=1.0).

This script is the **full-ensemble** equivalent of subset_replay: take ALL
per-case NCs from a source dir, copy each to a destination dir, and apply the
same override(s) in place. No ranking, no source workflow_state JSON required.

Use case (R5 design, May 2026): R3/R4 already produced 4890 per-case Morris
NCs in `fates_params_NonPrescribed_EnPlantTraitsCNPparam162_Morris/`. R5 wants
the SAME Morris X matrix but with prescribed P uptake enabled — i.e., the
same NCs with `fates_cnp_prescribed_puptake=1.0` baked in. This script
produces R5's per-case NCs in ~3-5 minutes without re-running Morris.

Usage:
    python phases/phase0_design/apply_param_override.py \\
        --source-dir /path/to/source_nc_dir \\
        --dest-dir   /path/to/dest_nc_dir \\
        --pattern    "fates_params_..._En{N}.nc" \\
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
    """Build the source NC path for a given case number."""
    return source_dir / pattern.replace('{N}', str(case_num))


def dst_path(dest_dir: Path, pattern: str, case_num: int) -> Path:
    """Build the destination NC path for a given case number."""
    return dest_dir / pattern.replace('{N}', str(case_num))


def apply_in_place(nc_file: Path, overrides: dict[str, float]) -> dict:
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
        # Just inspect the source; don't copy or write
        try:
            with nc.Dataset(str(src), 'r') as ds:
                snapshot = {}
                for key in overrides:
                    if key in ds.variables:
                        arr = ds.variables[key][:]
                        snapshot[key] = {
                            'first': float(arr.flatten()[0]),
                            'all_match': bool((arr == arr.flatten()[0]).all()),
                            'shape': list(arr.shape),
                        }
                    else:
                        snapshot[key] = {'status': 'missing_var'}
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
        description="Copy NCs from source dir, apply global overrides, write to dest dir.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--source-dir', type=Path, required=True,
                        help="Directory containing source per-case NCs")
    parser.add_argument('--dest-dir', type=Path, required=True,
                        help="Directory to write modified per-case NCs")
    parser.add_argument('--pattern', type=str, required=True,
                        help="NC filename pattern with {N} placeholder, "
                             "e.g., 'fates_params_..._En{N}.nc'")
    parser.add_argument('--range', type=str, required=True,
                        help="Case range, e.g., '1-4890' or '1-100,500,1000-1010'")
    parser.add_argument('--override', action='append', required=True,
                        help="Override in 'param=value' form. Can be repeated.")
    parser.add_argument('--parallel', type=int, default=16,
                        help="Number of parallel workers (default 16)")
    parser.add_argument('--verify-only', action='store_true',
                        help="Don't copy/write; just inspect source NCs for the override vars")
    parser.add_argument('--manifest', type=Path, default=None,
                        help="Path to write a JSON manifest (default: {dest_dir}/override_manifest.json)")
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
            'failures': failures[:50],  # cap at 50 to keep manifest readable
            'elapsed_sec': round(time.time() - t0, 2),
        }
        with manifest_path.open('w') as f:
            json.dump(manifest, f, indent=2, default=str)
        logger.info(f"\nManifest written: {manifest_path}")

    return 0 if not failures else 1


if __name__ == '__main__':
    sys.exit(main())
