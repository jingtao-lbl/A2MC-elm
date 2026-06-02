#!/usr/bin/env python3
"""
extract_ADSP_RGSP_slim.py — fast 2-variable extractor for spinup phases.

The production `tools/extract_monthly_variables_FATES.py` pulls 155
variables per case which is the right thing for general-purpose Phase 1
work but ~75x more I/O than the combined-axis preview plot needs. This
slim variant pulls just FATES_LEAFC_SZPF and FATES_FROOTC_SZPF for the
ADSP and RGSP phases, then writes them to the same canonical filename
the production extractor would have used so plot_all_extracted.py finds
them without modification.

Skip-if-exists: any case that already has the canonical NC (e.g. the
~288 ADSP cases that completed via the full extractor before this
switch) is left alone. The plot script reads only the 2 vars it needs;
those existing files have all 155 vars including the 2 we care about.

Promoted from use_cases/Kougarok/analysis/ to tools/ on 2026-05-31 so both
ONLINE Phase 0 (orchestrator-driven Morris ensembles) and OFFLINE Phase-0-
mimic submissions can reuse it without a per-site copy. It is fully env-var-
driven (A2MC_CASE_NAME_PATTERN / A2MC_ENSEMBLE_OUTPUT / A2MC_EXTRACTED_DATA)
so nothing about it is Kougarok-specific.

Usage:
    source a2mc_config.sh
    source use_cases/<site>/config/<site>_config_rN.sh   # any round config
    python tools/extract_ADSP_RGSP_slim.py [CASE_FILE] [N_PARALLEL]
"""
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import netCDF4 as nc

PHASES = [
    ('ADSP', 1, 200),
    ('RGSP', 201, 400),
]
TARGET_VARS = ['FATES_LEAFC_SZPF', 'FATES_FROOTC_SZPF']


def _resolve_paths():
    pat = os.environ.get('A2MC_CASE_NAME_PATTERN')
    ens_out = os.environ.get('A2MC_ENSEMBLE_OUTPUT')
    extracted = os.environ.get('A2MC_EXTRACTED_DATA')
    if not pat or not ens_out or not extracted:
        raise RuntimeError(
            "ERROR: A2MC_CASE_NAME_PATTERN / A2MC_ENSEMBLE_OUTPUT / "
            "A2MC_EXTRACTED_DATA must be set. Source a2mc_config.sh and the "
            "active round config (use_cases/<site>/config/<site>_config_rN.sh) "
            "first.")
    return pat, ens_out, extracted


def _extract_one(args):
    case_num, suffix, y0, y1, case_pattern, ensemble_output, extracted_data = args
    case_name = case_pattern.format(N=case_num, PHASE=suffix)
    run_dir = Path(ensemble_output) / case_name / 'run'
    out_file = (Path(extracted_data) /
                f'{case_name}_all_variables_monthly_{y0}_{y1}.nc')

    # Skip if already extracted (either by the full extractor earlier or
    # by a previous run of this slim script).
    if out_file.exists():
        return case_num, suffix, 'skipped'

    # ELM writes one yearly history file per simulation year, each
    # containing 12 monthly time records. Sort lexicographically — the
    # filename embeds YYYY-MM-DD so that's chronological.
    files = sorted(run_dir.glob(f'{case_name}.elm.h0.*.nc'))
    n_expected = y1 - y0 + 1
    if len(files) < n_expected:
        return case_num, suffix, f'missing_files({len(files)}/{n_expected})'

    # Read just the two variables we need from each yearly file, plus
    # template metadata from the first file for output schema.
    leaf_chunks = []
    froot_chunks = []
    template_dims = None
    template_var_dims = {}
    try:
        for i, f in enumerate(files):
            with nc.Dataset(f, 'r') as ds:
                if i == 0:
                    # Capture per-variable dim names + sizes for output schema
                    for v in TARGET_VARS:
                        if v not in ds.variables:
                            return case_num, suffix, f'missing_var:{v}'
                        var = ds.variables[v]
                        template_var_dims[v] = list(var.dimensions)
                    template_dims = {
                        d: ds.dimensions[d].size
                        for v in TARGET_VARS
                        for d in ds.variables[v].dimensions
                    }
                leaf_chunks.append(np.asarray(ds.variables['FATES_LEAFC_SZPF'][:]))
                froot_chunks.append(np.asarray(ds.variables['FATES_FROOTC_SZPF'][:]))
    except Exception as e:
        return case_num, suffix, f'read_error:{e}'

    # Concatenate along the time axis (axis 0 in the original layout)
    leaf_full = np.concatenate(leaf_chunks, axis=0)
    froot_full = np.concatenate(froot_chunks, axis=0)
    n_time = leaf_full.shape[0]

    # Write a slim NetCDF that mimics the production layout for the two
    # variables. plot_all_extracted's loader squeezes singleton dims and
    # transposes to (n_szpf, n_time), so as long as the dims are right it
    # doesn't matter that the file has only 2 data variables.
    out_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with nc.Dataset(out_file, 'w', format='NETCDF4') as ds_out:
            # Time dim spans the concatenated record
            ds_out.createDimension('time', n_time)
            # Re-use other dim sizes from the template (lndgrid, fates_levscpf, etc.)
            for d, size in template_dims.items():
                if d == 'time':
                    continue
                if d not in ds_out.dimensions:
                    ds_out.createDimension(d, size)

            for v_name, arr in [('FATES_LEAFC_SZPF', leaf_full),
                                ('FATES_FROOTC_SZPF', froot_full)]:
                out_var = ds_out.createVariable(
                    v_name, 'f4', tuple(template_var_dims[v_name]),
                    zlib=True, complevel=1)
                out_var[:] = arr
    except Exception as e:
        # If write fails, scrub partial output so a future rerun is clean
        try:
            out_file.unlink()
        except FileNotFoundError:
            pass
        return case_num, suffix, f'write_error:{e}'

    return case_num, suffix, 'ok'


def main() -> int:
    case_file = (sys.argv[1] if len(sys.argv) > 1
                 else '/global/homes/j/jingtao/A2MC/tmp/completed_cases_20260505_124406.txt')
    n_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 16

    case_pattern, ensemble_output, extracted_data = _resolve_paths()
    if not Path(case_file).exists():
        print(f"ERROR: case file not found: {case_file}")
        return 1

    cases = [int(line.strip()) for line in open(case_file)
             if line.strip().isdigit()]
    print(f"Cases:       {len(cases)} from {case_file}")
    print(f"Ensemble:    {ensemble_output}")
    print(f"Output:      {extracted_data}")
    print(f"Vars:        {', '.join(TARGET_VARS)}")
    print(f"Workers:     {n_workers}")
    print()

    # Build full task list (one (case, phase) pair = one task), pre-skipping
    # cases whose canonical NC already exists. Reports exactly how many will
    # actually be processed.
    tasks = []
    skipped = 0
    for c in cases:
        for suffix, y0, y1 in PHASES:
            case_name = case_pattern.format(N=c, PHASE=suffix)
            out_file = (Path(extracted_data) /
                        f'{case_name}_all_variables_monthly_{y0}_{y1}.nc')
            if out_file.exists():
                skipped += 1
                continue
            tasks.append((c, suffix, y0, y1, case_pattern,
                          ensemble_output, extracted_data))

    print(f"Tasks: {len(tasks)} to process, {skipped} already on disk (skipped)")
    if not tasks:
        print("Nothing to do.")
        return 0

    t0 = time.time()
    results = {'ok': 0, 'skipped': 0, 'failed': []}
    completed = 0
    with Pool(processes=n_workers) as pool:
        for case_num, suffix, status in pool.imap_unordered(
                _extract_one, tasks, chunksize=2):
            completed += 1
            if status in ('ok', 'skipped'):
                results[status] += 1
            else:
                results['failed'].append((case_num, suffix, status))
            if completed % 100 == 0 or completed == len(tasks):
                elapsed = time.time() - t0
                rate = completed / elapsed if elapsed > 0 else 0
                eta_min = (len(tasks) - completed) / rate / 60 if rate > 0 else 0
                print(f"  {completed}/{len(tasks)}  ok={results['ok']}  "
                      f"fail={len(results['failed'])}  rate={rate:.1f}/s  "
                      f"ETA={eta_min:.1f}min", flush=True)

    print(f"\nDone: ok={results['ok']}, "
          f"skipped={results['skipped']}, failed={len(results['failed'])}")
    if results['failed'][:5]:
        print(f"First failures: {results['failed'][:5]}")
    return 0 if not results['failed'] else 0  # Don't fail process for individual case errors


if __name__ == '__main__':
    sys.exit(main())
