#!/usr/bin/env python3
"""
validate_targets_config.py — pre-flight validator for a case's targets.yaml.

Catches the configuration pitfalls of the generic observation↔simulation comparison
(snapshot + time series, user-selectable cost; docs/24_Generic_Obs_Comparison_Plan.md)
BEFORE a screening run, where several of them otherwise fail silently (a target is just
dropped, or a skill score is degenerate, or one target dominates the composite cost).

Checks (level in [ERROR, WARN]):

  Schema
    S1  target has neither `observed` nor `observations`            ERROR
    S2  target has BOTH `observed` (scalar) and `observations`      WARN  (scalar ignored as the match value)
    S3  snapshot target but no top-level time_year/time_month       ERROR (no anchor -> wrong fallback)
  Resolution
    R1  target name not PFT<id>_<var> / unknown variable family     ERROR (silently dropped at runtime)
  Time matching
    T1  a month (time_month / point month / window month) not 1..12 ERROR
    T2  an observation point's year < year_start (negative index)   ERROR
    T3  a resolved timestep index >= n_times (out of range)         ERROR (target dropped)
    T4  duplicate resolved timesteps within one target              WARN
  Cost
    C1  a target cost_method not in VALID_ERROR_METHODS             ERROR
    C2  cost_config.error_method not in VALID_ERROR_METHODS         ERROR
    C3  cost_config.aggregation_method not in VALID_AGGREGATION...  ERROR
  Arity
    A1  skill score (nse/kge/correlation) on a target with <2 points ERROR (undefined on 1 point)
  Scale
    M1  rmsre/mean aggregation mixing relative + absolute metrics   WARN  (one target can dominate)
  Values
    V1  relative metric with observed <= 0 (or a point value <= 0)  ERROR (division by ~0)
    V2  uncertainty <= 0                                            WARN
  Data (only when a sample NC is available)
    D1  a target's resolved NC variable absent in the sample NC     WARN  (target would be dropped)

Usage:
    python tools/validate_targets_config.py [--targets PATH] [--year-start N]
        [--year-end N] [--n-times N] [--data-dir DIR] [--strict]

If --targets is omitted it resolves via tools.targets_loader.resolve_targets_yaml
($A2MC_VALIDATION_TARGETS or $A2MC_USE_CASE_DIR/validation/targets.yaml). If --data-dir
is given, a sample *_all_variables_monthly_*.nc is introspected for n_times + variable
presence (and year_start/year_end inferred from its filename when not supplied).
Exit code: 1 if any ERROR (or any WARN under --strict), else 0.

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.cost_functions import (
    VALID_ERROR_METHODS, VALID_AGGREGATION_METHODS, SKILL_SCORE_METHODS,
    RELATIVE_METHODS, ABSOLUTE_METHODS,
)
from tools.targets_loader import (
    parse_targets_yaml, parse_cost_config, parse_time_anchor, resolve_targets_yaml,
)
from tools.evaluate_case import _parse_target_specs, resolve_obs_index_windows
from tools.extract_ecosystem_series import parse_ecosystem_specs
from tools.extract_land_series import parse_land_specs


@dataclass
class Finding:
    level: str   # "ERROR" | "WARN"
    code: str
    target: str
    message: str


def _months_ok(months) -> bool:
    return all(isinstance(m, int) and 1 <= m <= 12 for m in months)


def introspect_sample_nc(data_dir: Path):
    """
    Return (year_start, year_end, n_times, variable_names) from a sample
    *_all_variables_monthly_{y0}_{y1}.nc in data_dir, or (None, None, None, None).
    """
    try:
        import netCDF4 as nc
    except ImportError:
        return None, None, None, None
    ncs = sorted(Path(data_dir).glob("*_all_variables_monthly_*.nc"))
    if not ncs:
        return None, None, None, None
    sample = ncs[0]
    y0 = y1 = None
    m = re.search(r"_all_variables_monthly_(\d+)_(\d+)\.nc$", sample.name)
    if m:
        y0, y1 = int(m.group(1)), int(m.group(2))
    n_times = None
    var_names = set()
    try:
        with nc.Dataset(str(sample), "r") as ds:
            var_names = set(ds.variables.keys())
            if "time" in ds.dimensions:
                n_times = ds.dimensions["time"].size
            else:
                for v in ds.variables.values():
                    if v.ndim == 2 and 156 in v.shape:
                        n_times = [d for d in v.shape if d != 156][0]
                        break
    except Exception:
        pass
    return y0, y1, n_times, var_names


def validate_targets_config(
    yaml_path,
    year_start: int = 1901,
    year_end: Optional[int] = None,
    n_times: Optional[int] = None,
    sample_var_names: Optional[set] = None,
) -> List[Finding]:
    """Run all checks; return a list of Findings (empty == fully clean)."""
    yaml_path = Path(yaml_path)
    findings: List[Finding] = []

    with open(yaml_path, "r") as f:
        raw = yaml.safe_load(f) or {}
    raw_targets: Dict[str, dict] = raw.get("targets", {}) or {}

    targets = parse_targets_yaml(yaml_path)
    cost_cfg = parse_cost_config(yaml_path)
    anchor_year, anchor_month = parse_time_anchor(yaml_path)
    # PFT/SZPF (nc_var, pft_id, factor) + ecosystem (site_var, factor) + land/snow/soil
    # (nc_var, level, selector, factor) specs; all expose the nc_var at [0], so R1
    # membership + the sample-var check below work for any level.
    specs = {**_parse_target_specs(targets), **parse_ecosystem_specs(targets),
             **parse_land_specs(targets)}

    if n_times is None and year_end is not None:
        n_times = (year_end - year_start + 1) * 12

    global_method = cost_cfg.get("error_method", "relative_error")
    agg_method = cost_cfg.get("aggregation_method", "rmsre")

    # --- Cost config (global) ---
    if global_method not in VALID_ERROR_METHODS:
        findings.append(Finding("ERROR", "C2", "-",
            f"cost_config.error_method '{global_method}' not in {VALID_ERROR_METHODS}"))
    if agg_method not in VALID_AGGREGATION_METHODS:
        findings.append(Finding("ERROR", "C3", "-",
            f"cost_config.aggregation_method '{agg_method}' not in {VALID_AGGREGATION_METHODS}"))

    # --- T1: top-level anchor month range ---
    if anchor_month is not None and not _months_ok([anchor_month]):
        findings.append(Finding("ERROR", "T1", "-",
            f"time_month {anchor_month} not in 1..12"))

    # collect effective methods for the scale check
    effective_methods = {}

    for name, spec in raw_targets.items():
        has_obs_scalar = spec.get("observed") is not None
        has_series = "observations" in spec
        t = targets.get(name)

        # --- Schema ---
        if not has_obs_scalar and not has_series:
            findings.append(Finding("ERROR", "S1", name,
                "target has neither `observed` nor `observations`"))
            continue
        if has_obs_scalar and has_series:
            findings.append(Finding("WARN", "S2", name,
                "target has BOTH `observed` and `observations`; scalar is ignored as the match value"))
        if has_obs_scalar and not has_series and (anchor_year is None or anchor_month is None):
            findings.append(Finding("ERROR", "S3", name,
                "snapshot target but no top-level time_year/time_month anchor "
                "(would fall back to the screening config's legacy anchor)"))

        # --- Resolution ---
        if name not in specs:
            findings.append(Finding("ERROR", "R1", name,
                "target name does not resolve to an NC variable — use PFT<id>_<vartype> "
                "(PFT10_leaf), ECO_<var> (ECO_gpp), SNOW_<var> (SNOW_snowdp), or "
                "SOIL_<var>_<N>cm / _L<n> (SOIL_tsoi_10cm), with a known variable"))

        # effective cost method
        method = (spec.get("cost_method") or global_method)
        effective_methods[name] = method
        if spec.get("cost_method") and spec["cost_method"] not in VALID_ERROR_METHODS:
            findings.append(Finding("ERROR", "C1", name,
                f"cost_method '{spec['cost_method']}' not in {VALID_ERROR_METHODS}"))

        if t is None:
            continue
        n_points = t.n_points

        # --- Arity ---
        if method in SKILL_SCORE_METHODS and n_points < 2:
            findings.append(Finding("ERROR", "A1", name,
                f"cost_method '{method}' is a skill score (needs >=2 points) but this "
                f"target has {n_points} point(s)"))

        # --- Values ---
        if (t.uncertainty is not None) and t.uncertainty <= 0:
            findings.append(Finding("WARN", "V2", name,
                f"uncertainty {t.uncertainty} <= 0"))
        if method in RELATIVE_METHODS:
            vals = list(t.obs_values)
            if any((v is None) or (v <= 0) for v in vals):
                findings.append(Finding("ERROR", "V1", name,
                    f"relative metric '{method}' with a non-positive observed value {vals} "
                    f"(division by ~0)"))

        # --- Time matching ---
        windows = resolve_obs_index_windows(t, year_start)
        # Month-range check (points + windows)
        if t.observations:
            for p in t.observations:
                if not _months_ok([p.month]) or not _months_ok(p.window):
                    findings.append(Finding("ERROR", "T1", name,
                        f"observation month/window out of 1..12: month={p.month}, window={p.window}"))
                if p.year < year_start:
                    findings.append(Finding("ERROR", "T2", name,
                        f"observation year {p.year} < year_start {year_start} (negative timestep index)"))
        if windows:
            flat = [idx for w in windows for idx in w]
            if n_times is not None and any(idx >= n_times for idx in flat):
                findings.append(Finding("ERROR", "T3", name,
                    f"resolved timestep index out of range (max idx {max(flat)} >= n_times {n_times})"))
            # one resolved value per point (mean over its window); duplicates across points
            point_first = [w[0] for w in windows]
            if len(set(point_first)) != len(point_first):
                findings.append(Finding("WARN", "T4", name,
                    "duplicate observation timesteps within this target"))

        # --- Data cross-check ---
        if sample_var_names is not None and name in specs:
            nc_var = specs[name][0]
            if nc_var not in sample_var_names:
                findings.append(Finding("WARN", "D1", name,
                    f"resolved variable '{nc_var}' not present in sample NC (target would be dropped)"))

    # --- Scale consistency (M1) ---
    if agg_method in ("rmsre", "rms", "mean"):
        used = set(effective_methods.values())
        if (used & set(RELATIVE_METHODS)) and (used & set(ABSOLUTE_METHODS)):
            findings.append(Finding("WARN", "M1", "-",
                f"aggregation '{agg_method}' mixes relative ({sorted(used & set(RELATIVE_METHODS))}) "
                f"and absolute ({sorted(used & set(ABSOLUTE_METHODS))}) metrics across targets; "
                "absolute-unit errors can dominate the composite cost"))

    return findings


def _print_report(findings: List[Finding], yaml_path: Path) -> None:
    print(f"\nValidating targets config: {yaml_path}")
    print("-" * 78)
    if not findings:
        print("  ✓ No issues found.")
    else:
        for f in sorted(findings, key=lambda x: (x.level != "ERROR", x.code)):
            mark = "✗" if f.level == "ERROR" else "!"
            print(f"  {mark} [{f.level:<5} {f.code}] {f.target}: {f.message}")
    n_err = sum(1 for f in findings if f.level == "ERROR")
    n_warn = sum(1 for f in findings if f.level == "WARN")
    print("-" * 78)
    print(f"  {n_err} error(s), {n_warn} warning(s)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a case's targets.yaml (pre-flight).")
    ap.add_argument("--targets", default=None, help="Path to targets.yaml (else auto-resolve)")
    ap.add_argument("--year-start", type=int, default=None, help="Simulation start year (default 1901 or inferred from NC)")
    ap.add_argument("--year-end", type=int, default=None, help="Simulation end year (to bound timestep range)")
    ap.add_argument("--n-times", type=int, default=None, help="Number of monthly timesteps (overrides inference)")
    ap.add_argument("--data-dir", default=None, help="Extract dir; a sample NC is introspected for n_times + variables")
    ap.add_argument("--strict", action="store_true", help="Treat warnings as failures (exit 1)")
    args = ap.parse_args()

    yaml_path = args.targets or resolve_targets_yaml()
    if not yaml_path or not Path(yaml_path).exists():
        print("ERROR: no targets.yaml found (pass --targets or set "
              "$A2MC_VALIDATION_TARGETS / $A2MC_USE_CASE_DIR).", file=sys.stderr)
        return 2

    year_start, year_end, n_times = args.year_start, args.year_end, args.n_times
    sample_vars = None
    if args.data_dir:
        y0, y1, nt, vnames = introspect_sample_nc(Path(args.data_dir))
        if year_start is None:
            year_start = y0
        if year_end is None:
            year_end = y1
        if n_times is None:
            n_times = nt
        sample_vars = vnames
    if year_start is None:
        year_start = 1901

    findings = validate_targets_config(
        yaml_path, year_start=year_start, year_end=year_end,
        n_times=n_times, sample_var_names=sample_vars,
    )
    _print_report(findings, Path(yaml_path))

    n_err = sum(1 for f in findings if f.level == "ERROR")
    n_warn = sum(1 for f in findings if f.level == "WARN")
    if n_err or (args.strict and n_warn):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
