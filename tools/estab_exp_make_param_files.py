#!/usr/bin/env python3
"""
PFT10 Establishment Experiment — Variant Param File Generator
==============================================================

Implements the 6-variant PFT10-allocation experiment from
`memory/dev_logs/20260531c_Offline_Experiment_Plan_PFT10_Establishment.md`,
grounded in the completed-case donor analysis
`memory/ana_logs/20260531b_R5_Completed_Case_PFT10_Tradeoff_Analysis.md`.

Base case = #488 (the only completed R5 case satisfying BOTH PFT9_leaf and
PFT10_leaf within +-20%, but failing PFT10 fineroot: 4.1 vs 382 g/m2). The
experiment transplants the *active, PFT10-specific* allocation parameters from
the 4 PFT10-fineroot donor cases (3704/3705/3703/4326) onto case 488, to test
whether PFT10 fineroot can be rescued WITHOUT losing the two leaf targets
(i.e. break the 3/6 joint-target ceiling), or confirm 3/6 as a structural
equifinality ceiling.

Why allocation (not metabolism / P-uptake / phenology):
- R5 prescribes P uptake (fates_cnp_prescribed_puptake=1.0 + FATES patch) ->
  the P-ECA kinetics family is INERT. No P-uptake param is a lever.
- vcmax25top_10 correlates -0.235 with PFT10 (backwards); no supply lever.
- phen_gddthresh_c is SHARED across all PFTs + super-sensitive, AND case 488
  already shares the donors' value -> not a usable, PFT10-specific lever.
- The only active + PFT10-specific lever class is allocation.

Convention (per feedback_phase5_case_naming_convention auto-memory):
- Base case number preserved: param file = fates_params_..._En488_estab0X.nc
- Case names (downstream): Kougarok_ELM-FATES_PtCNPEn488PrescP_estab0X_{PHASE}
- Dedicated param dir keeps variants OFF the R5 Morris param dir.

Variant matrix (donor-anchored medians, all PFT10 = pft index 10 1-based):
    estab00: control (pure copy of En488)
    estab01: l2fr_ini_10            9.879 -> 3.6   (less leaf-biased allocation)
    estab02: store_priority_frac_10 0.987 -> 0.57  (de-prioritize storage)
    estab03: turnover_fnrt_10       4.357 -> 1.8  AND fnrt_prof_a_10 5.75 -> 14
    estab04: estab01+02+03 combined (full donor allocation transplant)
    estab05: storage_cushion_10     0.686 -> 3.15  ALONE (falsifier)

Pre-committed success (per 20260531c):
    H1 confirmed: any variant reaches >= 4/6 targets, with PFT10 fineroot rising
                  toward 382 while PFT10 leaf stays >= 66 (0.8x) and PFT9 leaf >= 100.
    H2 (ceiling): if NO variant exceeds 3/6 -> structural equifinality ceiling.

Author: Jing Tao with Claude on Perlmutter
Created: 2026-06-04
"""
import os
import sys
from pathlib import Path
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.modify_fates_parameters import create_modified_parameter_file, verify_modifications

# Source param file (R5 case #488's per-case Morris param NC)
SOURCE_PARAM_DIR = Path(os.environ.get("A2MC_PARAM_DIR",
    "/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_PrescribedP_EnPlantTraitsCNPparam162"))

# Dedicated dir for this experiment's param files (keeps variants OFF the Morris dir)
TARGET_PARAM_DIR = Path(
    "/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_estab_exp_20260604")

PARAM_PATTERN = "fates_params_api25.5.0_12pft_c230710__PtCNP162_En{N}.nc"

BASE_CASE = 488
PFT10 = 10  # 1-based pft index expected by modify_fates_parameters

# Variant matrix — list of (variant_id, [mod dicts]). Empty list = control (pure copy).
# Each mod dict: {'param': fates_name, 'pft': 10, 'value': donor_median}
VARIANTS = [
    ("estab00", []),  # control
    ("estab01", [{"param": "fates_allom_l2fr",               "pft": PFT10, "value": 3.6}]),
    ("estab02", [{"param": "fates_alloc_store_priority_frac", "pft": PFT10, "value": 0.57}]),
    ("estab03", [{"param": "fates_turnover_fnrt",             "pft": PFT10, "value": 1.8},
                 {"param": "fates_allom_fnrt_prof_a",         "pft": PFT10, "value": 14.0}]),
    ("estab04", [{"param": "fates_allom_l2fr",               "pft": PFT10, "value": 3.6},
                 {"param": "fates_alloc_store_priority_frac", "pft": PFT10, "value": 0.57},
                 {"param": "fates_turnover_fnrt",             "pft": PFT10, "value": 1.8},
                 {"param": "fates_allom_fnrt_prof_a",         "pft": PFT10, "value": 14.0}]),
    ("estab05", [{"param": "fates_alloc_storage_cushion",     "pft": PFT10, "value": 3.15}]),
]


def main():
    if not SOURCE_PARAM_DIR.exists():
        sys.exit(f"SOURCE_PARAM_DIR not found: {SOURCE_PARAM_DIR}")

    in_file = SOURCE_PARAM_DIR / PARAM_PATTERN.replace("{N}", str(BASE_CASE))
    if not in_file.exists():
        sys.exit(f"Base case file missing: {in_file}")

    TARGET_PARAM_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Source param dir:  {SOURCE_PARAM_DIR}")
    print(f"Target param dir:  {TARGET_PARAM_DIR}")
    print(f"Base case:         #{BASE_CASE} ({in_file.name})")
    print(f"Variants:          {len(VARIANTS)} (estab00 .. estab05)")
    print()

    manifest_rows = []
    all_ok = True
    for variant_id, mods in VARIANTS:
        out_name = PARAM_PATTERN.replace("{N}", str(BASE_CASE)).replace(".nc", f"_{variant_id}.nc")
        out_file = TARGET_PARAM_DIR / out_name

        if not mods:
            shutil.copy2(in_file, out_file)
            print(f"  [{variant_id}] copy(En{BASE_CASE}) -> {out_name}  (control, no override)")
        else:
            create_modified_parameter_file(in_file, out_file, mods, verbose=False)
            # Step 7a — programmatic verification (HARD GATE)
            ok = verify_modifications(out_file, mods, verbose=True)
            all_ok = all_ok and ok
            ov_str = ", ".join(f"{m['param'].replace('fates_','')}[PFT{m['pft']}]={m['value']}" for m in mods)
            status = "OK" if ok else "VERIFY-FAILED"
            print(f"  [{variant_id}] {status}: {ov_str}")

        manifest_rows.append((variant_id, mods, out_name))

    manifest_path = Path("tmp/estab_exp_manifest_20260604.tsv")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        f.write("variant_id\tbase_case\toverrides\tnc_file\n")
        for variant_id, mods, nc_name in manifest_rows:
            ov_str = ";".join(f"{m['param']}[PFT{m['pft']}]={m['value']}" for m in mods) or "control"
            f.write(f"{variant_id}\t{BASE_CASE}\t{ov_str}\t{nc_name}\n")

    print()
    if not all_ok:
        sys.exit("VERIFICATION FAILED — do NOT submit. Fix the generator and re-run.")
    print(f"OK: {len(VARIANTS)} param files written + verified in {TARGET_PARAM_DIR}")
    print(f"OK: manifest -> {manifest_path}")
    print()
    print("Next: tools/estab_exp_submit.sh (after a manual ncdump spot-check, Step 7c).")


if __name__ == "__main__":
    main()
