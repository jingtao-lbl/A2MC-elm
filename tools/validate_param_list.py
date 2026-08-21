#!/usr/bin/env python3
"""
Validate a FATES parameter-list CSV against the model parameter file (docs/37).

Generalizes `use_cases/*/parameters/api43_migration_audit.md`: every `fates_name` must
exist in the target model param file, and the `organ` column must be consistent with the
model's `fates_plant_organs` dimension. Run this before sampling / after editing a list.

Checks:
  1. Every `fates_name` exists in the model param file (api-43 JSON / api-31 CDL-derived JSON).
  2. `organ` is set  iff  the model param is organ-dimensioned (`fates_plant_organs` in dims);
     catches both the "missing organ on a 2D param" and the "spurious organ on a 1D param" bugs.
  3. Canonical ids unique (enforced by the loader; surfaced here).
  4. lower < upper (error); default within [lower, upper] (warning).

Usage:
  python tools/validate_param_list.py <param_list.csv> --model-json <fates_params_default.json>
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.param_spec import load_param_spec


def _model_param_dims(json_path):
    """{fates_name: [dim, ...]} from a FATES JSON param file."""
    doc = json.load(open(json_path))
    params = doc.get("parameters", doc)
    out = {}
    for name, e in params.items():
        if isinstance(e, dict):
            out[name] = e.get("dims") or e.get("dimensions") or []
    return out


def _pft_names(json_path):
    """{pft_id(1-based): fates_pftname} from a FATES JSON param file, or {} if absent."""
    doc = json.load(open(json_path))
    params = doc.get("parameters", doc)
    pn = params.get("fates_pftname")
    if not pn:
        return {}
    return {i: (n.strip() if isinstance(n, str) else n) for i, n in enumerate(pn.get("data", []), start=1)}


def validate(csv_path, json_path):
    from tools.param_transforms import DERIVED_TRANSFORMS
    specs = load_param_spec(csv_path)
    dims = _model_param_dims(json_path)
    problems, warnings = [], []
    for s in specs:
        # bounds sanity applies to every row, including virtual coords
        if s.lower >= s.upper:
            problems.append(f"BOUNDS: {s.canonical_id} lower>=upper ({s.lower}, {s.upper})")
        if not (s.lower <= s.default <= s.upper):
            warnings.append(
                f"DEFAULT out of bounds: {s.canonical_id} default={s.default} not in [{s.lower},{s.upper}]")
        if s.is_virtual:
            continue  # not a model param; its native write-targets are checked below
        d = dims.get(s.fates_name)
        if d is None:
            problems.append(f"MISSING: '{s.fates_name}' not in the model param file")
            continue
        organ_dimd = "fates_plant_organs" in d
        if organ_dimd and not s.organ:
            problems.append(
                f"ORGAN: '{s.fates_name}' is organ-dimensioned {d} but the pft{s.pft} row has no organ")
        if s.organ and not organ_dimd:
            problems.append(
                f"ORGAN: '{s.fates_name}' row has organ={s.organ} but the model param is not "
                f"organ-dimensioned {d}")

    # Derived-parameter groups: native write-targets must exist in the model, and the bounds must
    # statically guarantee feasibility (e.g. seed sum <= 1 for every sampled point).
    certificates = []
    active = {(s.transform_group, s.pft) for s in specs if s.is_virtual}
    for group in sorted({g for g, _ in active}):
        for native in DERIVED_TRANSFORMS[group].native_names():
            if native not in dims:
                problems.append(
                    f"MISSING: derived group '{group}' writes '{native}', not in the model param file")
    for group, pft in sorted(active):
        t = DERIVED_TRANSFORMS[group]
        cs = {s.fates_name: s for s in specs if s.is_virtual and s.transform_group == group and s.pft == pft}
        lo = {c: cs[c].lower for c in t.coords}
        hi = {c: cs[c].upper for c in t.coords}
        ok, msg = t.certify_bounds(lo, hi)
        certificates.append((group, pft, ok, msg))
        if not ok:
            problems.append(f"FEASIBILITY: derived '{group}' pft{pft}: {msg}")
    return specs, problems, warnings, certificates


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="param-list CSV")
    ap.add_argument("--model-json", required=True, help="FATES fates_params_default.json (target milestone)")
    a = ap.parse_args()

    specs, problems, warnings, certificates = validate(a.csv, a.model_json)
    n_virtual = sum(1 for s in specs if s.is_virtual)
    print(f"Param list: {a.csv}")
    print(f"  {len(specs)} rows ({n_virtual} virtual derived-param coords), "
          f"{len({s.fates_name for s in specs if not s.is_virtual})} unique model fates_names, "
          f"{sum(1 for s in specs if s.is_organ)} organ-dimensioned rows")
    # PFT-identity report — surfaces api-version PFT drift (a mis-mapped pft silently misapplies values)
    pft_names = _pft_names(a.model_json)
    used_pfts = sorted({s.pft for s in specs if s.pft})
    if pft_names and used_pfts:
        print("  PFT identities (from the model file's fates_pftname):")
        for p in used_pfts:
            print(f"    PFT#{p:<2d} = {pft_names.get(p, '?? out of range')}")
    for group, pft, ok, msg in certificates:
        print(f"  {'✔' if ok else '✘'} derived '{group}' pft{pft}: {msg}")
    for w in warnings:
        print(f"  ⚠ {w}")
    if problems:
        for p in problems:
            print(f"  ✘ {p}")
        print(f"\n✘ {len(problems)} problem(s)")
        return 1
    print("✔ valid — all names present, organ dims consistent, bounds sane")
    return 0


if __name__ == "__main__":
    sys.exit(main())
