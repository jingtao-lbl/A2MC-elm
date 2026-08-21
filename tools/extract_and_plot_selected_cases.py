#!/usr/bin/env python3
"""
extract_and_plot_selected_cases.py — extract + V0-check + overlay-plot a SMALL
set of selected experiment cases (a Morris base case + N suffixed variants),
without touching the production Phase-1/5/6 extraction tooling.

Why this exists
---------------
`tools/extract_monthly_variables_FATES.py` is the production extractor. Its
`process_case()` resolves a `{base}_{suffix}` case id correctly, but its
`main()` / `run_monthly_extraction()` PRE-FLIGHT (first-case variable detection
+ skip-checks) is intentionally gated on the substring `_exp` because that is
the Phase 5/6 orchestrator's experiment-suffix convention. An offline
experiment that uses a different suffix (e.g. a parameter-sweep tag) is NOT
`_exp`-named, so the production CLI aborts during pre-flight. **Do not change
the extractor** — that pre-flight is wired to Phase 5/6 and editing it risks
breaking the orchestrator on this pinned (api-31-0) branch.

Instead, this driver:
  * builds the correct full case names itself,
  * does its OWN variable detection from the first selected case,
  * calls the extractor's reusable `process_case()` (the correct code path),
  * writes into a DEDICATED extract dir (keeps the Morris extract dir clean).

It is fully generic: nothing about any particular experiment is hardcoded.
Pass the base case number and the list of variant suffixes (or full case ids).

Subcommands
-----------
  extract   Extract TRANS (or any phase) for the selected cases into a dir.
  v0check   Compare a control variant's extracted NC against a reference NC
            (the Morris base case's extract) — the reproducibility hard gate.
  plot      Overlay the selected cases' leaf/fineroot vs validation targets.

Usage
-----
  source a2mc_config.sh
  source use_cases/<site>/config/<site>_config_r<N>.sh

  # 1. extract 8 variants of base 1304 into a dedicated dir
  python tools/extract_and_plot_selected_cases.py extract \
      --base 1304 --suffixes clump00 clump01 clump02 clump03 \
                              clump04 clump05 clump06 clump07 \
      --ensemble-output "$A2MC_ENSEMBLE_OUTPUT" \
      --extract-dir ~/<Exp>_Extract \
      --parallel 8

  # 2. V0 reproducibility gate: control vs the Morris base case's extract
  python tools/extract_and_plot_selected_cases.py v0check \
      --control-case-id 1304_clump00 \
      --extract-dir ~/<Exp>_Extract \
      --ref-nc "$A2MC_EXTRACTED_DATA/Kougarok_ELM-FATES_PtCNPEn1304PrescP_TRANS_all_variables_monthly_1901_2019.nc"

  # 3. overlay plot (one line per selected case)
  python tools/extract_and_plot_selected_cases.py plot \
      --base 1304 --suffixes clump00 clump01 ... clump07 \
      --extract-dir ~/<Exp>_Extract \
      --output use_cases/<site>/analysis/<Exp>_overlay.png

Author: Jing Tao with Claude on Perlmutter
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np

# A2MC root on path so `tools.*` and the analysis plotter import cleanly.
_A2MC_ROOT = Path(__file__).resolve().parents[1]
if str(_A2MC_ROOT) not in sys.path:
    sys.path.insert(0, str(_A2MC_ROOT))
if str(_A2MC_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(_A2MC_ROOT / "tools"))


# ---------------------------------------------------------------------------
# Helpers shared across subcommands
# ---------------------------------------------------------------------------

def _build_case_ids(base, suffixes, case_ids):
    """Return the list of `{base}_{suffix}` case ids the user selected.

    Either an explicit `--case-ids` list, or `--base` + `--suffixes`. Kept
    generic: a "suffix" is whatever experiment tag the caller chose."""
    if case_ids:
        return list(case_ids)
    if base is None or not suffixes:
        raise SystemExit("ERROR: provide either --case-ids, or --base + --suffixes")
    return [f"{base}_{s}" for s in suffixes]


def _resolve_case_name(case_pattern, case_id, phase):
    """Build the on-disk case name for a `{base}_{suffix}` id.

    Mirrors the partition `process_case()` uses: the leading integer goes in the
    pattern's {N} slot, the rest joins the phase as {PHASE}. So
    `1304_clump00` + TRANS -> ...PtCNPEn1304PrescP_clump00_TRANS (suffix sits
    between PrescP and _TRANS, which is exactly why it never collides with the
    Morris `*PrescP_TRANS_*` glob)."""
    sid = str(case_id)
    leading, sep, rest = sid.partition("_")
    if sep and leading.isdigit() and rest:
        return case_pattern.format(N=leading, PHASE=f"{rest}_{phase}")
    return case_pattern.format(N=sid, PHASE=phase)


def _get_case_pattern():
    pat = os.environ.get("A2MC_CASE_NAME_PATTERN")
    if not pat:
        prefix = os.environ.get("A2MC_ENSEMBLE_PREFIX", "")
        pat = f"{prefix}{{N}}_{{PHASE}}"
    return pat


def _obs_index(year_start, obs_year, obs_month):
    return (obs_year - year_start) * 12 + (obs_month - 1)


def _load_targets(targets_yaml):
    import yaml
    with open(targets_yaml) as f:
        doc = yaml.safe_load(f)
    obs_year = int(doc.get("time_year", 2016))
    obs_month = int(doc.get("time_month", 7))
    targets = {}
    for name, spec in doc["targets"].items():
        targets[name] = {
            "pft": int(spec["pft"]),
            "variable": spec["variable"],
            "observed": float(spec["observed"]),
            "uncertainty": float(spec.get("uncertainty", 0.2)),
        }
    return targets, obs_year, obs_month


def _pft_value_from_nc(nc_path, var_name, pft_id, obs_idx, factor=1000.0):
    """Sum SZPF var across size classes for one PFT at one month index.

    Reads an extracted *_all_variables_monthly_*.nc directly by path (so it
    works for suffixed case names that the plotter's case-number loader can't
    address). Returns g C/m**2."""
    import netCDF4 as nc
    from tools.fates_utils import get_szpf_range
    start, end = get_szpf_range(pft_id)
    with nc.Dataset(nc_path, "r") as ds:
        if var_name not in ds.variables:
            return np.nan
        data = np.squeeze(ds.variables[var_name][:])  # (time, 156) or (156, time)
        if data.ndim != 2:
            return np.nan
        if data.shape[0] == 156:  # (156, time)
            col = data[:, obs_idx]
        else:                      # (time, 156)
            col = data[obs_idx, :]
    return float(np.sum(col[start:end + 1]) * factor)


def _composite_nrmse(nc_path, targets, obs_idx):
    """RMSRE of (sim-obs)/obs across all targets for one extracted NC."""
    rel = []
    sims = {}
    for key, t in targets.items():
        sim = _pft_value_from_nc(nc_path, t["variable"], t["pft"], obs_idx)
        sims[key] = sim
        obs = t["observed"]
        rel.append(abs(sim - obs) / obs if obs else float("inf"))
    comp = float(np.sqrt(np.mean(np.array(rel) ** 2))) if rel else float("inf")
    return comp, sims


# ---------------------------------------------------------------------------
# Subcommand: extract
# ---------------------------------------------------------------------------

def cmd_extract(args):
    """Extract selected cases via the production extractor's process_case(),
    overriding only the module-level I/O globals (never editing the file)."""
    import xarray as xr
    import extract_monthly_variables_FATES as ext

    case_pattern = _get_case_pattern()
    ensemble_output = args.ensemble_output or os.environ.get("A2MC_ENSEMBLE_OUTPUT")
    if not ensemble_output:
        raise SystemExit("ERROR: --ensemble-output or A2MC_ENSEMBLE_OUTPUT required")
    case_ids = _build_case_ids(args.base, args.suffixes, args.case_ids)
    extract_dir = Path(args.extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    # Override the extractor's module globals (these are read at call time by
    # get_history_files / process_case). This is the supported way to redirect
    # I/O without touching the extractor's wired-in Phase 5/6 pre-flight.
    ext.BASE_INPUT_DIR = Path(ensemble_output)
    ext.OUTPUT_DIR = extract_dir
    ext.START_YEAR = args.year_start
    ext.END_YEAR = args.year_end
    ext.CASE_SUFFIX = args.phase

    print("=" * 70)
    print("SELECTED-CASE EXTRACTION")
    print(f"  cases:          {case_ids}")
    print(f"  ensemble dir:   {ensemble_output}")
    print(f"  extract dir:    {extract_dir}")
    print(f"  phase / years:  {args.phase} {args.year_start}-{args.year_end}")
    print("=" * 70)

    # Detect available variables from the FIRST selected case's first history
    # file (our own pre-flight — bypasses the extractor's _exp-gated detection).
    first_name = _resolve_case_name(case_pattern, case_ids[0], args.phase)
    first_files = ext.get_history_files(first_name, args.year_start, args.year_start)
    if not first_files:
        raise SystemExit(f"ERROR: no history files for first case {first_name}")
    ds = xr.open_dataset(first_files[0], decode_times=False)
    allv = list(ds.variables.keys())
    avail = dict(
        site=[v for v in ext.SITE_LEVEL_VARS if v in allv],
        levgrnd=[v for v in ext.LEVGRND_VARS if v in allv],
        levsoi=[v for v in ext.LEVSOI_VARS if v in allv],
        levsno=[v for v in ext.LEVSNO_VARS if v in allv],
        levdcmp=[v for v in ext.LEVDCMP_VARS if v in allv],
        levelem=[v for v in ext.LEVELEM_VARS if v in allv],
        pft=[v for v in ext.PFT_LEVEL_VARS if v in allv],
        szpf=[v for v in ext.SZPF_VARS if v in allv],
    )
    ds.close()
    print(f"  detected vars:  site={len(avail['site'])} pft={len(avail['pft'])} "
          f"szpf={len(avail['szpf'])}")

    # Skip cases already extracted.
    todo = []
    for cid in case_ids:
        cname = _resolve_case_name(case_pattern, cid, args.phase)
        out = extract_dir / f"{cname}_all_variables_monthly_{args.year_start}_{args.year_end}.nc"
        (print(f"  skip (exists):  {cname}") if out.exists() else todo.append(cid))
    if not todo:
        print("All selected cases already extracted. Nothing to do.")
        return 0

    ok, failed = [], []
    if args.parallel > 1 and len(todo) > 1:
        from multiprocessing import Pool
        # The module's worker reads ext._available_vars; set before fork so the
        # children inherit it (same mechanism the extractor's own batch path uses).
        ext._available_vars = avail
        with Pool(processes=args.parallel) as pool:
            for cid, success in pool.imap_unordered(ext._extract_case_worker, todo):
                (ok if success else failed).append(cid)
                print(f"  {'OK  ' if success else 'FAIL'} {cid}")
    else:
        for cid in todo:
            success = ext.process_case(
                cid, avail["site"], avail["levgrnd"], avail["levsoi"],
                avail["levsno"], avail["levdcmp"], avail["levelem"],
                avail["pft"], avail["szpf"])
            (ok if success else failed).append(cid)
            print(f"  {'OK  ' if success else 'FAIL'} {cid}")

    print(f"\nExtraction done: {len(ok)} OK, {len(failed)} failed")
    if failed:
        print(f"  failed: {failed}")
    return 0 if not failed else 1


# ---------------------------------------------------------------------------
# Subcommand: v0check
# ---------------------------------------------------------------------------

def cmd_v0check(args):
    """Reproducibility hard gate: the control variant (byte-for-byte param copy
    of the base case) must reproduce the Morris base case's NRMSE within machine
    noise. If it doesn't, build/env/seed drift exists — variants are not
    interpretable until resolved."""
    case_pattern = _get_case_pattern()
    targets_yaml = args.targets or str(
        Path(os.environ.get("A2MC_USE_CASE_DIR", _A2MC_ROOT / "use_cases" / "Kougarok"))
        / "validation" / "targets.yaml")
    targets, obs_year, obs_month = _load_targets(targets_yaml)
    obs_idx = _obs_index(args.year_start, obs_year, obs_month)

    ctrl_name = _resolve_case_name(case_pattern, args.control_case_id, args.phase)
    ctrl_nc = Path(args.extract_dir) / \
        f"{ctrl_name}_all_variables_monthly_{args.year_start}_{args.year_end}.nc"
    ref_nc = Path(args.ref_nc)

    if not ctrl_nc.exists():
        raise SystemExit(f"ERROR: control NC not found: {ctrl_nc}")
    if not ref_nc.exists():
        raise SystemExit(f"ERROR: reference NC not found: {ref_nc}")

    ctrl_comp, ctrl_sims = _composite_nrmse(ctrl_nc, targets, obs_idx)
    ref_comp, ref_sims = _composite_nrmse(ref_nc, targets, obs_idx)
    delta = abs(ctrl_comp - ref_comp)

    print("=" * 70)
    print("V0 REPRODUCIBILITY CHECK")
    print(f"  control : {ctrl_nc.name}")
    print(f"  ref     : {ref_nc.name}")
    print(f"  obs     : {obs_year}-{obs_month:02d}  (idx {obs_idx})")
    print("-" * 70)
    print(f"  {'target':<16} {'control':>12} {'reference':>12} {'rel.diff':>10}")
    max_rel = 0.0
    for key in targets:
        c, r = ctrl_sims[key], ref_sims[key]
        rd = abs(c - r) / abs(r) if r else float("inf")
        max_rel = max(max_rel, rd if np.isfinite(rd) else max_rel)
        print(f"  {key:<16} {c:>12.4f} {r:>12.4f} {rd:>10.2%}")
    print("-" * 70)
    print(f"  composite NRMSE  control={ctrl_comp:.6f}  ref={ref_comp:.6f}  "
          f"delta={delta:.6f}")
    print(f"  max per-target rel.diff = {max_rel:.2%}")
    print(f"  gate: delta <= {args.tol}")
    passed = delta <= args.tol
    print(f"\n  RESULT: {'PASS' if passed else 'FAIL'} "
          f"(delta={delta:.6f} {'<=' if passed else '>'} {args.tol})")
    if not passed:
        print("  -> Do NOT trust the variants. Investigate build/env/seed drift "
              "(same FATES build? same param file? same forcing?).")
    return 0 if passed else 2


# ---------------------------------------------------------------------------
# Subcommand: plot
# ---------------------------------------------------------------------------

def cmd_plot(args):
    """Overlay the selected cases (one colored line per case) for each
    (PFT, variable) panel, against the validation targets. Generic: labels are
    the case suffixes the caller passed, nothing experiment-specific."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import netCDF4 as nc
    from tools.fates_utils import (
        aggregate_szpf_by_pft, get_n_size_classes_from_config, get_szpf_dim_length,
    )

    case_pattern = _get_case_pattern()
    targets_yaml = args.targets or str(
        Path(os.environ.get("A2MC_USE_CASE_DIR", _A2MC_ROOT / "use_cases" / "Kougarok"))
        / "validation" / "targets.yaml")
    targets, obs_year, obs_month = _load_targets(targets_yaml)

    case_ids = _build_case_ids(args.base, args.suffixes, args.case_ids)
    pft_ids = [int(p) for p in args.pfts.split(",")]
    var_specs = [("leaf", "FATES_LEAFC_SZPF", "Leaf C (g C m$^{-2}$)"),
                 ("fineroot", "FATES_FROOTC_SZPF", "Fineroot C (g C m$^{-2}$)")]

    ys, ye = args.year_start, args.year_end
    n_months = (ye - ys + 1) * 12
    pstart = (args.plot_year_start - ys) * 12
    pend = (args.plot_year_end - ys + 1) * 12
    obs_idx = _obs_index(ys, obs_year, obs_month)

    n_sc = get_n_size_classes_from_config()

    def load_series(nc_path, var, pft_id):
        with nc.Dataset(nc_path, "r") as ds:
            if var not in ds.variables:
                return None
            slen = get_szpf_dim_length(ds, var)     # file-derived levscpf length (None if absent)
            data = np.squeeze(ds.variables[var][:])
            if data.ndim != 2:
                return None
            if slen and data.shape[1] == slen:
                data = data.T                        # (time, levscpf) -> (levscpf, time)
            elif slen and data.shape[0] == slen:
                pass                                  # already (levscpf, time)
            elif data.shape[1] == 156:                # legacy fallback: undescribed 12-PFT file
                data = data.T
                slen = 156
        fates_pft = (slen or data.shape[0]) // n_sc
        ts = aggregate_szpf_by_pft(data, pft_id, axis=0, fates_pft=fates_pft) * 1000.0
        return ts if ts.shape[0] == n_months else None

    cmap = plt.get_cmap("viridis")
    colors = [cmap(i / max(1, len(case_ids) - 1)) for i in range(len(case_ids))]

    fig, axes = plt.subplots(len(pft_ids), len(var_specs),
                             figsize=(7 * len(var_specs), 4 * len(pft_ids)))
    axes = np.atleast_2d(axes)
    if len(var_specs) == 1:
        axes = axes.reshape(len(pft_ids), 1)

    def _is_baseline(cid, label):
        return args.baseline is not None and (str(cid) == args.baseline or label == args.baseline)

    if args.baseline is not None and not any(
            _is_baseline(cid, str(cid).partition("_")[2] or str(cid)) for cid in case_ids):
        print(f"  WARN --baseline '{args.baseline}' matches none of the selected cases "
              f"(by id or suffix) — plotting all as colored variants.")

    for ci, cid in enumerate(case_ids):
        cname = _resolve_case_name(case_pattern, cid, args.phase)
        ncf = Path(args.extract_dir) / \
            f"{cname}_all_variables_monthly_{ys}_{ye}.nc"
        if not ncf.exists():
            print(f"  WARN missing: {ncf.name}")
            continue
        label = str(cid).partition("_")[2] or str(cid)  # the suffix
        base = _is_baseline(cid, label)
        # baseline drawn distinctly (black dashed, thicker, on top); variants colored solid
        style = dict(color="black", linestyle="--", linewidth=2.4, alpha=1.0, zorder=6) if base \
            else dict(color=colors[ci], linestyle="-", linewidth=1.6, alpha=0.9, zorder=3)
        plot_label = f"{label} (baseline)" if base else label
        for col, (vt, vnc, _u) in enumerate(var_specs):
            for row, pid in enumerate(pft_ids):
                ts = load_series(ncf, vnc, pid)
                if ts is None:
                    continue
                axes[row, col].plot(np.arange(pend - pstart), ts[pstart:pend],
                                    label=plot_label, **style)

    # Obs markers + axis cosmetics
    for col, (vt, vnc, unit) in enumerate(var_specs):
        for row, pid in enumerate(pft_ids):
            ax = axes[row, col]
            key = f"PFT{pid}_{vt}"
            t = targets.get(key)
            if t:
                opx = obs_idx - pstart
                obs, tol = t["observed"], t["uncertainty"]
                ax.axhspan(obs * (1 - tol), obs * (1 + tol), xmin=0, xmax=1,
                           color="gold", alpha=0.18, zorder=0)
                # The obs point is calendar-anchored (targets.yaml time_year/time_month);
                # it only has a real x-position when this phase's years ARE calendar years
                # (TRANS). For a spin-up phase (ADSP/RGSP) opx falls wildly outside the
                # plotted window (obs_year - a spin-up "year 1" is not a real time delta),
                # and plotting it there force-expands the x-axis and crushes the real data
                # into an unreadable sliver -- skip the point (keep the +/-20% band, which
                # is phase-independent) rather than draw a physically meaningless position.
                if 0 <= opx <= (pend - pstart):
                    ax.plot(opx, obs, "kd", markersize=11, zorder=10,
                            label="Obs" if (row == 0 and col == 0) else None)
            ticks = np.arange(0, pend - pstart, 12)
            ax.set_xticks(ticks)
            ax.set_xticklabels(np.arange(args.plot_year_start, args.plot_year_end + 1),
                               fontsize=10)
            ax.grid(True, alpha=0.3)
            if row == 0:
                ax.set_title(var_specs[col][0].capitalize(), fontweight="bold")
            if col == 0:
                ax.set_ylabel(f"PFT#{pid}\n{unit}", fontweight="bold")
            if row == len(pft_ids) - 1:
                ax.set_xlabel("Year", fontweight="bold")
    axes[0, 0].legend(loc="upper left", fontsize=8, framealpha=0.9, ncol=2)
    fig.suptitle(args.title or f"Selected cases ({len(case_ids)}) vs targets",
                 fontweight="bold", fontsize=14, y=0.99)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.output, dpi=args.dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved overlay plot: {args.output}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_selection(sp):
        sp.add_argument("--base", type=int, default=None,
                        help="Base Morris case number (e.g. 1304)")
        sp.add_argument("--suffixes", nargs="+", default=None,
                        help="Variant suffixes (e.g. clump00 clump01 ...)")
        sp.add_argument("--case-ids", nargs="+", default=None,
                        help="Explicit case ids (e.g. 1304_clump00); overrides --base/--suffixes")
        sp.add_argument("--phase", default="TRANS", help="Phase suffix (default TRANS)")
        sp.add_argument("--year-start", type=int, default=1901)
        sp.add_argument("--year-end", type=int, default=2019)

    pe = sub.add_parser("extract", help="Extract selected cases into a dir")
    add_selection(pe)
    pe.add_argument("--ensemble-output", default=None,
                    help="Dir holding the case run dirs (default $A2MC_ENSEMBLE_OUTPUT)")
    pe.add_argument("--extract-dir", required=True, help="Dedicated output dir for NCs")
    pe.add_argument("--parallel", type=int, default=8)
    pe.set_defaults(func=cmd_extract)

    pv = sub.add_parser("v0check", help="Control-vs-reference reproducibility gate")
    pv.add_argument("--control-case-id", required=True, help="e.g. 1304_clump00")
    pv.add_argument("--extract-dir", required=True)
    pv.add_argument("--ref-nc", required=True, help="Morris base case's extracted TRANS NC")
    pv.add_argument("--targets", default=None, help="targets.yaml (default site config)")
    pv.add_argument("--tol", type=float, default=0.005, help="Max |delta composite NRMSE|")
    pv.add_argument("--phase", default="TRANS")
    pv.add_argument("--year-start", type=int, default=1901)
    pv.add_argument("--year-end", type=int, default=2019)
    pv.set_defaults(func=cmd_v0check)

    pp = sub.add_parser("plot", help="Overlay selected cases vs targets")
    add_selection(pp)
    pp.add_argument("--extract-dir", required=True)
    pp.add_argument("--output", required=True)
    pp.add_argument("--targets", default=None)
    pp.add_argument("--pfts", default="10,11,12",
                    help="Comma-separated calibrated PFT ids (default: Kougarok api-43 arctic — "
                         "evergreen shrub 10, deciduous shrub 11, graminoid 12; were 7/9/10 on api-31)")
    pp.add_argument("--plot-year-start", type=int, default=2010)
    pp.add_argument("--plot-year-end", type=int, default=2019)
    pp.add_argument("--title", default=None)
    pp.add_argument("--dpi", type=int, default=200)
    pp.add_argument("--baseline", default=None,
                    help="Case id OR suffix to dash-highlight as the baseline "
                         "(black dashed, drawn on top) — the others stay colored solid. "
                         "Mirrors the online plot_experiment_comparison baseline styling.")
    pp.set_defaults(func=cmd_plot)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
