---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# `dyn_subgrid/` — Dynamic Subgrid Area Changes

`components/elm/src/dyn_subgrid/` is the collection of modules that let ELM change
the weights of its patches, columns, and landunits during a run while remaining
conservative for water, energy, carbon, nitrogen, and phosphorus. It covers
prescribed land-use change, crop-area change, wood harvest, glacier area from
CISM, and FATES-driven vegetation weight updates.

## 1. The seventeen modules

| # | File | Role |
|---|---|---|
| 1 | `dynSubgridDriverMod.F90` | Top-level driver; sequences every other module (`dyn_subgrid/dynSubgridDriverMod.F90:44-319`) |
| 2 | `dynSubgridControlMod.F90` | Namelist `dynamic_subgrid` state: `flanduse_timeseries`, `do_transient_pfts`, `do_transient_crops`, `do_harvest`, testing flags (`dyn_subgrid/dynSubgridControlMod.F90:37-62`) |
| 3 | `dynFileMod.F90` | `dyn_file_type`: a `file_desc_t` plus a `time_info_type` (`dyn_subgrid/dynFileMod.F90:17-86`) |
| 4 | `dynTimeInfoMod.F90` | `time_info_type`: tracks the two time samples that bracket the current model year and advances them each step (`dyn_subgrid/dynTimeInfoMod.F90:21-62`) |
| 5 | `dynVarTimeInterpMod` / `dynVarTimeUninterpMod` (`.F90.in`) | Generic containers for interpolated vs. step-wise time-varying variables; instantiated via `do_genf90` |
| 6 | `dynpftFileMod.F90` | Reads `PCT_NAT_PFT` from the land-use file, interpolates in time, and writes `veg_pp%wtcol` (`dyn_subgrid/dynpftFileMod.F90:29-297`) |
| 7 | `dyncropFileMod.F90` | Reads `PCT_CROP`, `PCT_CFT`, `FERTNITRO_CFT`, `FERTPHOSP_CFT`; writes crop landunit and CFT weights plus fertilizer streams (`dyn_subgrid/dyncropFileMod.F90:26-223`) |
| 8 | `dynHarvestMod.F90` | Reads five `HARVEST_*` streams, applies `CNHarvest` to the CN code paths, and publishes per-PFT harvest rates to FATES (`dyn_subgrid/dynHarvestMod.F90:39-853`) |
| 9 | `dynPriorWeightsMod.F90` | Lightweight snapshot type that records `veg_pp%wtcol` and `col_pp%active` before the updates so downstream code can see the "before" state (`dyn_subgrid/dynPriorWeightsMod.F90:26-91`) |
| 10 | `dynLandunitAreaMod.F90` | Reconciles landunit weights after dynamic-code and CISM updates, by growing natural veg or shrinking in a fixed priority order (`dyn_subgrid/dynLandunitAreaMod.F90:36-165`) |
| 11 | `dynPatchStateUpdaterMod.F90` | `patch_state_updater_type`: `set_old_patch_weights` / `set_new_patch_weights` / `update_patch_state` (`dyn_subgrid/dynPatchStateUpdaterMod.F90:50-434`) |
| 12 | `dynColumnStateUpdaterMod.F90` | `column_state_updater_type` with four "fill" strategies for state adjustment across column area changes (`dyn_subgrid/dynColumnStateUpdaterMod.F90:107-928`) |
| 13 | `dynColumnTemplateMod.F90` | Finds a "template" column (usually first active natural veg in the gridcell) to seed newly-active columns (`dyn_subgrid/dynColumnTemplateMod.F90:34-169`) |
| 14 | `dynInitColumnsMod.F90` | `initialize_new_columns`: copies state from the template into columns that just became active (`dyn_subgrid/dynInitColumnsMod.F90:27-294`) |
| 15 | `dynSubgridAdjustmentsMod.F90` | Per-level "adjustment" routines that apply the updaters to specific C/N/P state variables (`dyn_subgrid/dynSubgridAdjustmentsMod.F90:40-1397`) |
| 16 | `dynConsBiogeophysMod.F90` | `dyn_hwcontent_init` / `dyn_hwcontent_final`: snapshots gridcell total liquid, ice, and heat content before/after weight updates and emits correction fluxes (`dyn_subgrid/dynConsBiogeophysMod.F90:37-343`) |
| 17 | `dynConsBiogeochemMod.F90` | `dyn_cnbal_patch` / `dyn_cnbal_column`: closes the C, N, P balance for vegetation and soil pools when patches / columns shrink or grow (`dyn_subgrid/dynConsBiogeochemMod.F90:42-1126`) |
| — | `dynEDMod.F90` | Bridge to FATES: copies `veg_pp%wt_ed` into `veg_pp%wtcol` for columns under FATES control (`dyn_subgrid/dynEDMod.F90:16-43`) |

## 2. Two-pass design

`dynSubgrid_driver` (`dyn_subgrid/dynSubgridDriverMod.F90:138-319`) executes **two
logical passes** through the hierarchy each time step so that state updates have
access to both the old and the new weights.

### Pass A — capture prior state (lines 212-229)

Inside a per-clump OMP region, for each clump:

1. `dyn_hwcontent_init` — snapshots liquid water, ice water, heat content, and
   liquid-water temperature at the gridcell level into `grc_ws%liq1`, `grc_ws%ice1`,
   `grc_es%heat1`, `grc_es%liquid_water_temp1`
   (`dyn_subgrid/dynConsBiogeophysMod.F90:47-97`).
2. `set_prior_weights(prior_weights, bounds_clump)` — copies `veg_pp%wtcol` into
   `prior_weights%pwtcol` and `col_pp%active` into `prior_weights%cactive`
   (`dyn_subgrid/dynPriorWeightsMod.F90:69-89`).
3. `set_old_patch_weights(patch_state_updater, bounds_clump)` — copies
   `veg_pp%wtgcell` and `col_pp%wtgcell` into the updater object
   (`dyn_subgrid/dynPatchStateUpdaterMod.F90:151-175`).
4. `set_old_column_weights(column_state_updater, bounds_clump)` — analogous copy
   of `col_pp%wtgcell` and, crucially, computes the template column for every
   column using the prior `col_pp%active` flags
   (`dyn_subgrid/dynColumnStateUpdaterMod.F90`).

### Pass B — I/O-bound updates (lines 231-245, processor-level, outside OMP)

Some weight-update sources must run outside the clump-threaded region because
they do PIO reads. `dynSubgrid_driver` therefore drops out of OMP and calls:

1. `dynpft_interp(bounds_proc)` if `do_transient_pfts` — reads `PCT_NAT_PFT`,
   interpolates in time, and writes into `veg_pp%wtcol` for natural veg patches.
2. `dyncrop_interp(bounds_proc, crop_vars)` if `do_transient_crops` — reads
   `PCT_CROP`, `PCT_CFT`, `FERTNITRO_CFT`, `FERTPHOSP_CFT`, writes into the crop
   landunit weight, CFT weights, and fertilizer state.
3. `dynHarvest_interp_harvest_types(bounds_proc)` if `do_harvest` — advances the
   five harvest streams; no weights change here because harvest acts by shifting
   mass between pools.

### Pass C — per-clump weight updates, conservation, and state adjustments (lines 251-316)

Re-entering an OMP region, for each clump:

1. `dyn_ED(bounds_clump)` if `use_fates` — copies `veg_pp%wt_ed` into
   `veg_pp%wtcol` for every active natural veg column
   (`dyn_subgrid/dynEDMod.F90:22-42`).
2. `glc2lnd_vars%update_glc2lnd(bounds_clump)` if `create_glacier_mec_landunit` —
   pulls CISM's new `frac_grc` and `topo_grc` into `lun_pp%wttopounit` and
   `col_pp%wtlunit` (see `core/glacier_interface.md`).
3. `dynSubgrid_wrapup_weight_changes(bounds_clump, glc2lnd_vars)` — the heart of
   the subgrid plumbing:
   - `update_landunit_weights(bounds_clump)` (`dyn_subgrid/dynLandunitAreaMod.F90:36-88`)
     reconciles landunit weights that come from several sources (transient
     pfts, crops, glacier, and the surface dataset) so they sum to 1 on every
     topounit. Excess is removed in a fixed priority order; deficit is added to
     `istsoil`.
   - `compute_higher_order_weights` re-computes every derived
     weight.
   - `reweight_wrapup` runs `set_active`, two `check_weights` passes, and
     `setFilters` (`main/reweightMod.F90:28-56`).
4. `set_new_patch_weights(patch_state_updater, bounds_clump)` — records the new
   `veg_pp%wtgcell`, plus the `dwt`, `growing_old_fraction`, and
   `growing_new_fraction` the subsequent state updates will use
   (`dyn_subgrid/dynPatchStateUpdaterMod.F90:178-210`).
5. `set_new_column_weights(column_state_updater, bounds_clump, nc)` — analogous
   for columns.
6. `set_subgrid_diagnostic_fields(bounds_clump)` — refreshes the `PCT_LANDUNIT`,
   `PCT_NAT_PFT`, `PCT_CFT`, `PCT_GLC_MEC` history diagnostics.
7. `initialize_new_columns(bounds_clump, prior_weights%cactive, soilhydrology_vars)` —
   for every column that was inactive last step and is active now, copies state
   from a template column (`dyn_subgrid/dynInitColumnsMod.F90:27-76`).
8. `dyn_hwcontent_final(bounds_clump, …, dt)` — re-measures liquid water, ice, and
   heat, and stores them in `grc_ws%liq2`, `grc_ws%ice2`, `grc_es%heat2`. It then
   computes `delta_liq`, `delta_ice`, `delta_heat` per gridcell and emits them as
   `dynbal` correction fluxes so the coupler can keep the water / energy budgets
   closed (`dyn_subgrid/dynConsBiogeophysMod.F90:100-343`).
9. **CN path** (`use_cn`): `dyn_cnbal_patch` and the matching dynamic-patch
   `CarbonStateUpdateDynPatch`, `NitrogenStateUpdateDynPatch`, and
   `PhosphorusStateUpdateDynPatch` calls transfer root/seed litter C/N/P into the
   decomposer pools; `dyn_cnbal_column` then balances the column-level pools.
10. **FATES path** (`use_fates`): `dyn_cnbal_column` still runs with the FATES
    column C/N/P state so that mass balance is closed across column area changes,
    even though FATES owns the patch-level carbon itself.

### Summary diagram

```
+-------------------- Pass A: capture prior state (clump-level) ---------------+
| dyn_hwcontent_init (liq1, ice1, heat1)                                        |
| set_prior_weights (pwtcol, cactive)                                           |
| set_old_patch_weights  (pwtgcell_old, cwtgcell_old)                           |
| set_old_column_weights (cwtgcell_old, natveg_template_col)                    |
+------------------------------------------------------------------------------+
                 |
                 v
+-------------------- Pass B: I/O updates (proc-level, outside OMP) ----------+
| dynpft_interp      (PCT_NAT_PFT  -> veg_pp%wtcol)                             |
| dyncrop_interp     (PCT_CROP, PCT_CFT, fertilizer)                            |
| dynHarvest_interp  (HARVEST_* streams)                                        |
+------------------------------------------------------------------------------+
                 |
                 v
+-------------------- Pass C: weight & state updates (clump-level) -----------+
| dyn_ED             (FATES wt_ed -> veg_pp%wtcol)                              |
| update_glc2lnd     (CISM frac, topo -> lun_pp, col_pp)                        |
| dynSubgrid_wrapup_weight_changes                                              |
|   update_landunit_weights  (sum to 100% on every topounit)                    |
|   compute_higher_order_weights                                                |
|   reweight_wrapup (set_active, check_weights x 2, setFilters)                 |
| set_new_patch_weights  (dwt, growing fractions)                               |
| set_new_column_weights (dwt_col, area_gained_col)                             |
| set_subgrid_diagnostic_fields (PCT_* history)                                 |
| initialize_new_columns (template copy into newly-active columns)              |
| dyn_hwcontent_final (liq2, ice2, heat2, dynbal fluxes)                        |
| dyn_cnbal_patch  + CarbonStateUpdateDynPatch  + N/P variants                  |
| dyn_cnbal_column  (col_cs, col_ns, col_ps close)                              |
+------------------------------------------------------------------------------+
```

## 3. How the three concerns are separated

- **Weight updates** live in `dynLandunitAreaMod`, `dynpftFileMod`,
  `dyncropFileMod`, `dynEDMod`, and (via `glc2lnd_vars%update_glc2lnd`)
  `glc2lndMod`. None of these modules touches biogeophysical or biogeochemical
  state directly.
- **State updates** live in `dynPatchStateUpdaterMod`,
  `dynColumnStateUpdaterMod`, `dynColumnTemplateMod`, `dynInitColumnsMod`, and
  `dynSubgridAdjustmentsMod`. They take the prior and new weights as inputs and
  produce per-pool adjustments plus the "flux out" terms that get folded into
  conservation accounting.
- **Conservation** is handled by `dynConsBiogeophysMod` (water / energy) and
  `dynConsBiogeochemMod` (C / N / P). Each of these takes a complete "before" and
  "after" snapshot at the gridcell level and either distributes a correction flux
  (water, energy) or transfers mass between live vegetation, product pools, and
  litter pools (C / N / P) so that the total content of the gridcell remains
  consistent with what biogeophysics expects.

## 4. Namelist and control flow

All behaviour is gated by the `dynamic_subgrid` namelist
(`dyn_subgrid/dynSubgridControlMod.F90:126-180`):

- `flanduse_timeseries` — path to the transient land-use NetCDF file
- `do_transient_pfts` — enable natural-PFT area changes
- `do_transient_crops` — enable crop-area and CFT changes
- `do_harvest` — enable wood harvest streams
- `for_testing_allow_non_annual_changes` — lift the "only at year boundary"
  error check (testing-only)
- `for_testing_zero_dynbal_fluxes` — zero the dynbal water / energy correction
  fluxes (testing-only; breaks conservation)

`dynSubgridControl_init` (`dyn_subgrid/dynSubgridControlMod.F90:70-93`) reads the
namelist; `check_namelist_consistency` enforces the combinations that are allowed
given `use_cn`, `use_crop`, and `use_fates`.

## 5. Where to read next

- For the transient land-use file I/O details (`dynFileMod`,
  `dynPriorWeightsMod`, `dynpftFileMod`, `dyncropFileMod`, `dynHarvestMod`,
  `dynTimeInfoMod`, `dynSubgridControlMod`), see
  `dyn_subgrid/transient_landuse.md`.
- For the weight reconciliation and state / conservation routines
  (`dynLandunitAreaMod`, `dynPatchStateUpdaterMod`, `dynColumnStateUpdaterMod`,
  `dynColumnTemplateMod`, `dynInitColumnsMod`, `dynSubgridAdjustmentsMod`,
  `dynSubgridDriverMod`, `dynConsBiogeochemMod`, `dynConsBiogeophysMod`,
  `dynEDMod`), see `dyn_subgrid/weight_updates_and_conservation.md`.
