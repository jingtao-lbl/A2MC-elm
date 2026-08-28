#!/usr/bin/env python3
"""A2MC Model Evolution — V0-at-equality comparison.

Generalizes the phen_split #17 V0-check's compare_v0.py
(use_cases/ELM-FATES_Kougarok/memory/phase_results/20260712_phen_split_v0_api43/compare_v0.py) into a
site-agnostic tool with two comparison modes:

  netcdf  Compare the latest monthly history file (*.elm.h0.*.nc) in each run directory.
          Requires a run long enough to cross a history-write boundary (a TRANS chain
          normally is). Key science variables must match EXACTLY (max|A-B| == 0); a broad
          sweep over all shared non-"_PF" variables flags anything unexpected.

  log     Compare the per-timestep lnd.log stream directly (gzip-aware — CIME compresses a
          COMPLETED run's logs). Use this when the run is too short to write history/restart
          output (e.g. a 5-day segment) — lnd.log's periodic diagnostic prints
          are the only science-output stream available. Strips known non-deterministic lines
          (wall-clock timestamps, memory highwater/usage, DATE/TIME banners) before diffing,
          since those legitimately differ run-to-run without indicating a science difference.

  auto (default)  Try netcdf first (if both dirs have *.elm.h0.*.nc); fall back to log.

Usage:
  python compare_v0.py <A_dir> <B_dir> [--mode auto|netcdf|log] [--key-vars v1,v2,...]

Author: Jing Tao with Claude on Perlmutter
"""
import argparse
import glob
import gzip
import os
import re
import sys

DEFAULT_KEY_VARS = [
    "FATES_LEAFC", "FATES_FROOTC", "FATES_VEGC_ABOVEGROUND",
    "FATES_STOREC", "FATES_SAPWOODC", "FATES_STRUCTC", "FATES_NPP", "FATES_GPP",
]

# Lines that legitimately differ run-to-run without indicating a science difference —
# wall-clock timestamps, process memory usage (allocator-dependent), throughput.
NONDETERMINISTIC_PATTERNS = [
    r"wall clock =",
    r"memory_write:",
    r"DATE \d\d/\d\d/\d\d TIME",
    r"memory dealloc in MB is",
    r"Memory block size conversion",
    r"simulated years / cmp-day",
    r"pes min memory",
    r"pes max memory",
]


def latest_h0(run_dir):
    fs = sorted(glob.glob(os.path.join(run_dir, "*.elm.h0.*.nc")))
    return fs[-1] if fs else None


def _open_maybe_gz(path):
    if path.endswith(".gz"):
        with gzip.open(path, "rt") as f:
            return f.readlines()
    with open(path) as f:
        return f.readlines()


def latest_lnd_log(run_dir):
    fs = sorted(glob.glob(os.path.join(run_dir, "lnd.log.*")))
    return fs[-1] if fs else None


def compare_netcdf(a_dir, b_dir, key_vars):
    import numpy as np
    import netCDF4 as nc

    fa, fb = latest_h0(a_dir), latest_h0(b_dir)
    print(f"A: {os.path.basename(fa)}")
    print(f"B: {os.path.basename(fb)}")
    da, db = nc.Dataset(fa), nc.Dataset(fb)

    print("\n=== KEY SCIENCE VARIABLES (require max|A-B| == 0) ===")
    n_ok = 0
    n_bad = 0
    for v in key_vars:
        if v not in da.variables or v not in db.variables:
            print(f"  {v:28s} : (absent in one file — skip)")
            continue
        A = np.asarray(da[v][:], float)
        B = np.asarray(db[v][:], float)
        if A.shape != B.shape:
            print(f"  {v:28s} : SHAPE DIFF {A.shape} vs {B.shape}  <-- INVESTIGATE")
            n_bad += 1
            continue
        d = float(np.nanmax(np.abs(A - B))) if A.size else 0.0
        tag = "OK (exact)" if d == 0.0 else ("bit-noise" if d < 1e-12 else "**DIFF**")
        if d > 1e-12:
            n_bad += 1
        else:
            n_ok += 1
        print(f"  {v:28s} : max|A-B| = {d:.3e}   {tag}")

    print("\n=== BROAD SWEEP (all shared numeric vars; _PF diagnostics excluded) ===")
    shared = [v for v in da.variables if v in db.variables]
    nonzero = []
    for v in shared:
        if v.endswith("_PF"):
            continue
        try:
            A = np.asarray(da[v][:], float)
            B = np.asarray(db[v][:], float)
        except Exception:
            continue
        if A.shape != B.shape or A.size == 0:
            continue
        d = float(np.nanmax(np.abs(A - B)))
        if d > 1e-12:
            nonzero.append((v, d))
    if nonzero:
        print(f"  {len(nonzero)} non-_PF vars differ > 1e-12:")
        for v, d in sorted(nonzero, key=lambda x: -x[1])[:30]:
            print(f"    {v:32s} max|A-B| = {d:.3e}")
    else:
        print("  ALL shared non-_PF variables match within 1e-12.")

    passed = n_bad == 0 and not nonzero
    print(f"\nkey vars: {n_ok} exact/bit-noise, {n_bad} differing; broad-sweep non-_PF diffs: {len(nonzero)}")
    return passed


def compare_log(a_dir, b_dir):
    fa, fb = latest_lnd_log(a_dir), latest_lnd_log(b_dir)
    if not fa or not fb:
        raise SystemExit(f"no lnd.log.* files in {a_dir if not fa else b_dir}")
    print(f"A: {os.path.basename(fa)}")
    print(f"B: {os.path.basename(fb)}")

    lines_a = _open_maybe_gz(fa)
    lines_b = _open_maybe_gz(fb)

    pat = re.compile("|".join(NONDETERMINISTIC_PATTERNS))
    filt_a = [l for l in lines_a if not pat.search(l)]
    filt_b = [l for l in lines_b if not pat.search(l)]

    print(f"\n=== lnd.log COMPARISON (non-deterministic lines stripped) ===")
    print(f"A: {len(lines_a)} raw lines, {len(filt_a)} after stripping")
    print(f"B: {len(lines_b)} raw lines, {len(filt_b)} after stripping")

    if filt_a == filt_b:
        print("  lnd.log MATCHES exactly (after stripping non-deterministic lines).")
        return True

    print("  lnd.log DIFFERS — first mismatches:")
    n_shown = 0
    for i, (la, lb) in enumerate(zip(filt_a, filt_b)):
        if la != lb:
            print(f"    line {i}: A={la.rstrip()!r}  B={lb.rstrip()!r}")
            n_shown += 1
            if n_shown >= 20:
                print("    ... (further diffs suppressed)")
                break
    if len(filt_a) != len(filt_b):
        print(f"  ALSO: line-count differs ({len(filt_a)} vs {len(filt_b)}) — one run likely stopped early.")
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a_dir", help="Run directory A (e.g. the fix/off case)")
    ap.add_argument("b_dir", help="Run directory B (e.g. the baseline/parent case)")
    ap.add_argument("--mode", choices=["auto", "netcdf", "log"], default="auto")
    ap.add_argument("--key-vars", default=None,
                     help="Comma-separated science variables requiring exact equality "
                          f"(default: {','.join(DEFAULT_KEY_VARS)})")
    args = ap.parse_args()

    key_vars = args.key_vars.split(",") if args.key_vars else DEFAULT_KEY_VARS

    mode = args.mode
    if mode == "auto":
        mode = "netcdf" if (latest_h0(args.a_dir) and latest_h0(args.b_dir)) else "log"
        print(f"[auto-detected mode: {mode}]")

    if mode == "netcdf":
        passed = compare_netcdf(args.a_dir, args.b_dir, key_vars)
    else:
        passed = compare_log(args.a_dir, args.b_dir)

    verdict = "PASS (V0-at-equality)" if passed else "FAIL — investigate diffs above"
    print(f"\n=== VERDICT: {verdict} ===")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
