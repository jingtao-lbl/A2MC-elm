# FATES Parameter List API-Migration Audit

- **Parameter list:** `~/Desktop/Work/NGEE-Arctic/Kougarok/Program/A2MC/use_cases/Kougarok/parameters/FATES_Parameter_List_Full_162_Finalized.txt`
- **Target api JSON:** `~/Desktop/Work/SourceCode/ELM_FATES/E3SM_FATES_api43-1/components/elm/src/external_models/fates/parameter_files/fates_params_default.json`
- **Param list entries:** 162 (across all PFTs)
- **Unique parameter names in list:** 56
- **Parameters available in api JSON:** 311

## Summary

- ✅ Present in api: **55 / 56**
- ❌ Missing from api: **1 / 56**

---

## Missing parameters with suggested replacements

Each row shows a parameter that's in your list but NOT in the target api JSON. The "Suggestions" column shows up to 5 api param names with similar spelling — review each, since some renames split one old param into multiple new ones (e.g., canopy/understory variants).

| # | Missing param | Suggested replacement(s) |
|---|---|---|
| 1 | `fates_turnover_leaf` | `fates_turnover_leaf_ustory`<br>`fates_turnover_leaf_canopy`<br>`fates_turnover_fnrt`<br>`fates_turnover_branch`<br>`fates_turnover_senleaf_fdrought` |

---

## Migration approach

1. For each missing param, decide:
   - **Same semantic intent kept**: replace the name in the list
     (e.g., `fates_turnover_leaf` → `fates_turnover_leaf_canopy`).
   - **Split into multiple**: add one entry per replacement
     (e.g., separate `_canopy` and `_ustory` variants if the
     old semantics need both).
   - **Removed without replacement**: drop the entry; document
     the decision in the param-list file's preamble.

2. Re-run this audit; expect zero missing.
3. Run the v2.100 Phase 0 pipeline:
   ```bash
   python phases/phase0_design/create_parameter_sample.py --method morris --trajectories 30 \
       --param-list-file <updated-list> \
       --output-matrix samples.txt
   python phases/phase0_design/generate_parameter_files.py # materializer auto-detects JSON
   ```

