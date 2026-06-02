#!/usr/bin/env python3
"""
Clumping_Index Experiment — Variant Param File Generator
=========================================================

Implements the 8-variant clumping-index sweep from
`memory/dev_logs/20260519e_Phase4_Clumping_Index_Verification_Experiment_Plan.md`
on base case #1304, with the MODIS satellite anchor (CI = 0.78 at Kougarok per
`memory/ana_logs/20260526b_FATES_Clumping_Index_Literature_Search.md` §4).

Convention (per `memory/dev_logs/20260528b_H1_Case_Naming_Convention_Mistake_And_Mitigation.md`
+ `feedback_phase5_case_naming_convention` auto-memory):
- Base case number preserved: param file = fates_params_..._En1304_clump{00..07}.nc
- Case names (downstream): Kougarok_ELM-FATES_PtCNPEn1304PrescP_clump{00..07}_{PHASE}
- Dedicated param dir (per `20260519e` §"HPC submission details"):
    /global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_clumping_exp_20260528/
  This keeps the variants OFF the R5 Morris param dir.

Variant matrix (from `20260519e`, with MODIS anchor noted in clump02):
    clump00: control (PFT9=0.90, PFT7=0.85, PFT10=0.75 — defaults)
    clump01: PFT9=0.80 (just above MODIS landscape mean of 0.78)
    clump02: PFT9=0.70 (at MODIS lower bound + species-correction headroom — SATELLITE-ANCHORED)
    clump03: PFT9=0.60
    clump04: PFT9=0.50
    clump05: combined PFT7+PFT9=0.60 (max effect)
    clump06: asymmetry — PFT10=0.50 only (H2 falsification: should be inert)
    clump07: anti-correlation — PFT9=1.00 (H1 falsification: PFT10 should drop further)

Pre-committed thresholds (per `20260519e` §"Verification"):
    H1 confirmed: PFT10_leaf_ratio >= 5.0 in any of clump02/03/04
    H2 confirmed: clump06 PFT10_leaf_ratio < 1.5
    H3 confirmed: clump02-04 PFT9_leaf_ratio > 0.7

Author: Jing Tao with Claude on Perlmutter
Created: 2026-05-28 (replaces canceled `tools/h1_generate_variants.py`)
"""
import os
import sys
from pathlib import Path
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.modify_fates_parameters import create_modified_parameter_file


# Source param file (R5 case #1304's per-case Morris param NC)
SOURCE_PARAM_DIR = Path(os.environ.get("A2MC_PARAM_DIR",
    "/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_PrescribedP_EnPlantTraitsCNPparam162"))

# Dedicated dir for the clumping experiment param files (per 20260519e)
TARGET_PARAM_DIR = Path(
    "/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_clumping_exp_20260528")

PARAM_PATTERN = "fates_params_api25.5.0_12pft_c230710__PtCNP162_En{N}.nc"

BASE_CASE = 1304

# Variant matrix from 20260519e — list of (variant_id, [(pft, value), ...]) overrides on
# fates_rad_leaf_clumping_index. Empty overrides list = control (pure copy).
VARIANTS = [
    ("clump00", []),                              # control (defaults)
    ("clump01", [(9, 0.80)]),                     # mild PFT9 reduction
    ("clump02", [(9, 0.70)]),                     # MODIS-anchored — satellite landscape mean - species correction
    ("clump03", [(9, 0.60)]),                     # aggressive
    ("clump04", [(9, 0.50)]),                     # max single-PFT reduction
    ("clump05", [(7, 0.60), (9, 0.60)]),          # combined max effect
    ("clump06", [(10, 0.50)]),                    # asymmetry (PFT10 own Ω — should be inert)
    ("clump07", [(9, 1.00)]),                     # anti-correlation falsification
]


def main():
    if not SOURCE_PARAM_DIR.exists():
        sys.exit(f"SOURCE_PARAM_DIR not found: {SOURCE_PARAM_DIR}")

    TARGET_PARAM_DIR.mkdir(parents=True, exist_ok=True)

    in_file = SOURCE_PARAM_DIR / PARAM_PATTERN.replace("{N}", str(BASE_CASE))
    if not in_file.exists():
        sys.exit(f"Base case file missing: {in_file}")

    print(f"Source param dir:  {SOURCE_PARAM_DIR}")
    print(f"Target param dir:  {TARGET_PARAM_DIR}")
    print(f"Base case:         #{BASE_CASE} ({in_file.name})")
    print(f"Variants:          {len(VARIANTS)} (clump00 .. clump07)")
    print()

    manifest_rows = []
    for variant_id, overrides in VARIANTS:
        # Output filename follows the case-suffix convention: En1304_clump00.nc, etc.
        out_name = PARAM_PATTERN.replace("{N}", str(BASE_CASE)).replace(".nc", f"_{variant_id}.nc")
        out_file = TARGET_PARAM_DIR / out_name

        if not overrides:
            # Control: pure byte-for-byte copy of En1304
            shutil.copy2(in_file, out_file)
            print(f"  [{variant_id}] copy(En{BASE_CASE}) -> {out_name}  (no override)")
        else:
            mods = [{"param": "fates_rad_leaf_clumping_index", "pft": pft, "value": val}
                    for pft, val in overrides]
            create_modified_parameter_file(in_file, out_file, mods, verbose=False)
            ov_str = ", ".join(f"PFT{p}={v}" for p, v in overrides)
            print(f"  [{variant_id}] En{BASE_CASE} + {ov_str:35s} -> {out_name}")

        manifest_rows.append((variant_id, overrides, out_name))

    # Write manifest
    manifest_path = Path("tmp/clumping_exp_manifest_20260528.tsv")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        f.write("variant_id\tbase_case\toverrides\tnc_file\n")
        for variant_id, overrides, nc_name in manifest_rows:
            ov_str = ";".join(f"PFT{p}={v}" for p, v in overrides) or "control"
            f.write(f"{variant_id}\t{BASE_CASE}\t{ov_str}\t{nc_name}\n")

    print()
    print(f"✓ 8 param files written to {TARGET_PARAM_DIR}")
    print(f"✓ Manifest: {manifest_path}")
    print()
    print("Next: run tools/clumping_exp_submit.sh to launch all 8 variants.")


if __name__ == "__main__":
    main()
