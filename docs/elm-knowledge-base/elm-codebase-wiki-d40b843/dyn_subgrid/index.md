---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# `dyn_subgrid/` — Dynamic Subgrid Area Changes

`components/elm/src/dyn_subgrid/` is the collection of modules that let ELM
change the weights of its patches, columns, and landunits during a run while
remaining conservative for water, energy, carbon, nitrogen, and phosphorus. It
covers prescribed land-use change, crop-area change, wood harvest, glacier area
from CISM, FATES-driven vegetation weight updates, FATES LUH2 land-use change,
and IAC / EHC (Integrated Assessment Component / E3SM Human Coupling) weight
updates.

## 1. The eighteen modules (plus `dynEDMod` bridge)

| # | File | Role |
|---|---|---|
| 1 | `dynSubgridDriverMod.F90` | Top-level driver; sequences every other module (`dyn_subgrid/dynSubgridDriverMod.F90:74-360`). Now contains two private routines `dyn_iac_init` (`:409-462`) and `set_iac_veg_weights` (`:465-553`) for the IAC path. |
| 2 | `dynSubgridControlMod.F90` | Namelist `dynamic_subgrid` state: `flanduse_timeseries`, `do_transient_pfts`, `do_transient_crops`, `do_harvest`, testing flags (`dyn_subgrid/dynSubgridControlMod.F90:37-60`). Adds an IAC mutual-exclusion check inside `read_namelist` (`:158-169`). |
| 3 | `dynFileMod.F90` | `dyn_file_type`: a `file_desc_t` plus a `time_info_type` (`dyn_subgrid/dynFileMod.F90:17-86`) |
| 4 | `dynTimeInfoMod.F90` | `time_info_type`: tracks the two time samples that bracket the current model year and advances them each step (`dyn_subgrid/dynTimeInfoMod.F90:21-62`) |
| 5 | `dynVarTimeInterpMod` / `dynVarTimeUninterpMod` (`.F90.in`) | Generic containers for interpolated vs. step-wise time-varying variables; instantiated via `do_genf90` |
| 6 | `dynpftFileMod.F90` | Reads `PCT_NAT_PFT` from the land-use file, interpolates in time, and writes `veg_pp%wtcol` (`dyn_subgrid/dynpftFileMod.F90:29-297`). The natural-veg filter now uses `veg_pp%is_on_soil_col(p)` (`:286`). |
| 7 | `dyncropFileMod.F90` | Reads `PCT_CROP`, `PCT_CFT`, `FERTNITRO_CFT`, `FERTPHOSP_CFT`; writes crop landunit and CFT weights plus fertilizer streams (`dyn_subgrid/dyncropFileMod.F90:26-223`) |
| 8 | `dynHarvestMod.F90` | Reads five `HARVEST_*` streams, applies `CNHarvest` to the CN code paths, and publishes per-PFT harvest rates to FATES (`dyn_subgrid/dynHarvestMod.F90:39-857`). Module variable renamed `do_harvest → do_cn_harvest` and changed to `public` (`:83`); woody-PFT detection now uses `pftvarcon::woody` (`:381`). |
| 9 | `dynPriorWeightsMod.F90` | Lightweight snapshot type that records `veg_pp%wtcol` and `col_pp%active` before the updates so downstream code can see the "before" state (`dyn_subgrid/dynPriorWeightsMod.F90:26-91`) |
| 10 | `dynLandunitAreaMod.F90` | Reconciles landunit weights after dynamic-code and CISM updates, by growing natural veg or shrinking in a fixed priority order (`dyn_subgrid/dynLandunitAreaMod.F90:36-165`) |
| 11 | `dynPatchStateUpdaterMod.F90` | `patch_state_updater_type`: `set_old_patch_weights` / `set_new_patch_weights` / `update_patch_state` (`dyn_subgrid/dynPatchStateUpdaterMod.F90:50-434`) |
| 12 | `dynColumnStateUpdaterMod.F90` | `column_state_updater_type` with four "fill" strategies for state adjustment across column area changes (`dyn_subgrid/dynColumnStateUpdaterMod.F90:107-928`) |
| 13 | `dynColumnTemplateMod.F90` | Finds a "template" column (usually first active natural veg in the gridcell) to seed newly-active columns (`dyn_subgrid/dynColumnTemplateMod.F90:34-169`) |
| 14 | `dynInitColumnsMod.F90` | `initialize_new_columns`: copies state from the template into columns that just became active (`dyn_subgrid/dynInitColumnsMod.F90:27-294`) |
| 15 | `dynSubgridAdjustmentsMod.F90` | Per-level "adjustment" routines that apply the updaters to specific C/N/P state variables (`dyn_subgrid/dynSubgridAdjustmentsMod.F90:40-1658`). `dyn_col_ns_Adjustments` (`:810-1186`) handles ~17 additional FAN nitrogen pools — see Section 5. |
| 16 | `dynConsBiogeophysMod.F90` | `dyn_hwcontent_init` / `dyn_hwcontent_final`: snapshots gridcell total liquid, ice, and heat content before/after weight updates and emits correction fluxes (`dyn_subgrid/dynConsBiogeophysMod.F90:37-343`) |
| 17 | `dynConsBiogeochemMod.F90` | `dyn_cnbal_patch` / `dyn_cnbal_column`: closes the C, N, P balance for vegetation and soil pools when patches / columns shrink or grow (`dyn_subgrid/dynConsBiogeochemMod.F90:42-1126`) |
| 18 | `dynFATESLandUseChangeMod.F90` | **NEW** at d40b8431. Reads the LUH2 (Land Use Harmonization v2) dataset and publishes 12 land-use state, 108 land-use transition, and 5 wood-harvest fields per gridcell to FATES (`dyn_subgrid/dynFATESLandUseChangeMod.F90:1-268`). Gated by `use_fates_luh` and `fates_harvest_mode`. See `dyn_subgrid/fates_land_use_change.md`. |
| — | `dynEDMod.F90` | Bridge to FATES: copies `veg_pp%wt_ed` into `veg_pp%wtcol` for columns under FATES control (`dyn_subgrid/dynEDMod.F90:16-43`) |

## 2. Two-pass design

`dynSubgrid_driver` (`dyn_subgrid/dynSubgridDriverMod.F90:157-360`) executes
**three logical passes** through the hierarchy each time step. Pass A captures
prior state, Pass B does I/O-bound updates outside OMP, and Pass C reconciles
weights and updates state inside OMP.

The signature now takes `iac2lnd_vars` as an `inout` argument
(`dyn_subgrid/dynSubgridDriverMod.F90:225`) — old callers that ended at
`crop_vars` need updating.

### Pass A — capture prior state (lines 244-258, clump-level inside OMP)

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

### Pass B — I/O-bound updates (lines 264-286, processor-level, outside OMP)

Some weight-update sources must run outside the clump-threaded region because
they do PIO reads or coupler-side updates. `dynSubgrid_driver` therefore drops
out of OMP and calls (in order):

1. `dynpft_interp(bounds_proc)` if `get_do_transient_pfts()` — reads
   `PCT_NAT_PFT`, interpolates in time, and writes into `veg_pp%wtcol` for
   natural veg patches.
2. `dyncrop_interp(bounds_proc, crop_vars)` if `get_do_transient_crops()` —
   reads `PCT_CROP`, `PCT_CFT`, `FERTNITRO_CFT`, `FERTPHOSP_CFT`, writes into
   the crop landunit weight, CFT weights, and fertilizer state.
3. `dynHarvest_interp_harvest_types(bounds_proc)` if `get_do_harvest() .or.
   fates_harvest_mode == fates_harvest_hlmlanduse` — advances the five harvest
   streams; no weights change here because harvest acts by shifting mass
   between pools. Note the gate is now overloaded with the FATES
   `landuse_timeseries` mode (`dyn_subgrid/dynSubgridDriverMod.F90:272`).
4. `dynFatesLandUseInterp(bounds_proc)` if `use_fates_luh .and. .not.
   use_fates_potentialveg` (`:276-278`) — populates `landuse_states`,
   `landuse_transitions`, and `landuse_harvest` from the LUH2 dataset for FATES
   to consume. See `dyn_subgrid/fates_land_use_change.md`.
5. `iac2lnd_vars%update_iac2lnd(bounds_proc)` if `iac_present` (`:284-286`) —
   pulls IAC / EHC weights into `veg_pp%wtgcell_iac` for later use by
   `set_iac_veg_weights`. See `dyn_subgrid/fates_land_use_change.md`.

### Pass C — per-clump weight updates, conservation, and state adjustments (lines 292-358)

Re-entering an OMP region, for each clump:

1. `dyn_ED(bounds_clump)` if `use_fates` — copies `veg_pp%wt_ed` into
   `veg_pp%wtcol` for every active natural veg column
   (`dyn_subgrid/dynEDMod.F90:22-42`, called at
   `dyn_subgrid/dynSubgridDriverMod.F90:296-298`).
2. `glc2lnd_vars%update_glc2lnd(bounds_clump)` if `create_glacier_mec_landunit` —
   pulls CISM's new `frac_grc` and `topo_grc` into `lun_pp%wttopounit` and
   `col_pp%wtlunit` (see `core/glacier_interface.md`).
3. `dynSubgrid_wrapup_weight_changes(bounds_clump, glc2lnd_vars)` — the heart of
   the subgrid plumbing (`dyn_subgrid/dynSubgridDriverMod.F90:363-406`):
   - `update_landunit_weights(bounds_clump)`
     (`dyn_subgrid/dynLandunitAreaMod.F90:36-88`) reconciles landunit weights
     that come from several sources (transient pfts, crops, glacier, IAC, and
     the surface dataset) so they sum to 1 on every topounit. Excess is removed
     in a fixed priority order; deficit is added to `istsoil`.
   - `compute_higher_order_weights` re-computes every derived weight.
   - **If `iac_present`**: a first `reweight_wrapup` call (`:394-395`) so the
     active flags are correct, then `set_iac_veg_weights(bounds_clump)`
     (`:396`) overwrites all four levels of `veg_pp` weights from
     `veg_pp%wtgcell_iac`. This branch did not exist in `60d9aad`.
   - `reweight_wrapup` (always; `:403`) runs `set_active`, two `check_weights`
     passes, and `setFilters` (`main/reweightMod.F90:28-56`).
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
8. `dyn_hwcontent_final(bounds_clump, …, dt)` — re-measures liquid water, ice,
   and heat, and stores them in `grc_ws%liq2`, `grc_ws%ice2`, `grc_es%heat2`. It
   then computes `delta_liq`, `delta_ice`, `delta_heat` per gridcell and emits
   them as `dynbal` correction fluxes so the coupler can keep the water /
   energy budgets closed
   (`dyn_subgrid/dynConsBiogeophysMod.F90:100-343`).
9. **CN path** (`use_cn`): `dyn_cnbal_patch` and the matching dynamic-patch
   `CarbonStateUpdateDynPatch`, `NitrogenStateUpdateDynPatch`, and
   `PhosphorusStateUpdateDynPatch` calls
   (`dyn_subgrid/dynSubgridDriverMod.F90:340-347`) transfer root/seed litter
   C/N/P into the decomposer pools.
10. **FATES path** (`use_fates`): `dyn_cnbal_column` still runs with the FATES
    column C/N/P state so that mass balance is closed across column area
    changes, even though FATES owns the patch-level carbon itself
    (`:351-355`).

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
| dynpft_interp              (PCT_NAT_PFT  -> veg_pp%wtcol)                    |
| dyncrop_interp             (PCT_CROP, PCT_CFT, fertilizer)                   |
| dynHarvest_interp          (HARVEST_* streams; gated by do_harvest OR        |
|                             fates_harvest_mode == 'landuse_timeseries')      |
| dynFatesLandUseInterp      (LUH2: 12 states + 108 transitions + 5 harvest)   |
|                             (gated by use_fates_luh)                          |
| iac2lnd_vars%update_iac2lnd (EHC weights -> veg_pp%wtgcell_iac)              |
|                             (gated by iac_present)                            |
+------------------------------------------------------------------------------+
                 |
                 v
+-------------------- Pass C: weight & state updates (clump-level) -----------+
| dyn_ED             (FATES wt_ed -> veg_pp%wtcol)                              |
| update_glc2lnd     (CISM frac, topo -> lun_pp, col_pp)                        |
| dynSubgrid_wrapup_weight_changes                                              |
|   update_landunit_weights        (sum to 100% on every topounit)              |
|   compute_higher_order_weights                                                |
|   if (iac_present): reweight_wrapup + set_iac_veg_weights                    |
|   reweight_wrapup (set_active, check_weights x 2, setFilters)                 |
| set_new_patch_weights  (dwt, growing fractions)                               |
| set_new_column_weights (dwt_col, area_gained_col)                             |
| set_subgrid_diagnostic_fields (PCT_* history)                                 |
| initialize_new_columns (template copy into newly-active columns)              |
| dyn_hwcontent_final (liq2, ice2, heat2, dynbal fluxes)                        |
| dyn_cnbal_patch  + CarbonStateUpdateDynPatch  + N/P variants                  |
| dyn_cnbal_column  (col_cs, col_ns, col_ps close, including 17 FAN N pools)    |
+------------------------------------------------------------------------------+
```

## 3. How the three concerns are separated

- **Weight updates** live in `dynLandunitAreaMod`, `dynpftFileMod`,
  `dyncropFileMod`, `dynEDMod`, `dynFATESLandUseChangeMod` (publishes only;
  consumed by FATES), the IAC routines `dyn_iac_init` /
  `set_iac_veg_weights` inside `dynSubgridDriverMod`, and (via
  `glc2lnd_vars%update_glc2lnd`) `glc2lndMod`. None of these modules touches
  biogeophysical or biogeochemical state directly.
- **State updates** live in `dynPatchStateUpdaterMod`,
  `dynColumnStateUpdaterMod`, `dynColumnTemplateMod`, `dynInitColumnsMod`, and
  `dynSubgridAdjustmentsMod`. They take the prior and new weights as inputs and
  produce per-pool adjustments plus the "flux out" terms that get folded into
  conservation accounting.
- **Conservation** is handled by `dynConsBiogeophysMod` (water / energy) and
  `dynConsBiogeochemMod` (C / N / P). Each of these takes a complete "before"
  and "after" snapshot at the gridcell level and either distributes a
  correction flux (water, energy) or transfers mass between live vegetation,
  product pools, and litter pools (C / N / P) so that the total content of the
  gridcell remains consistent with what biogeophysics expects.

## 4. Namelist and control flow

All file-based behaviour is gated by the `dynamic_subgrid` namelist
(`dyn_subgrid/dynSubgridControlMod.F90:126-184`):

- `flanduse_timeseries` — path to the transient land-use NetCDF file
- `do_transient_pfts` — enable natural-PFT area changes
- `do_transient_crops` — enable crop-area and CFT changes
- `do_harvest` — enable wood harvest streams
- `for_testing_allow_non_annual_changes` — lift the "only at year boundary"
  error check (testing-only)
- `for_testing_zero_dynbal_fluxes` — zero the dynbal water / energy correction
  fluxes (testing-only; breaks conservation)

`dynSubgridControl_init` (`dyn_subgrid/dynSubgridControlMod.F90:70-93`) reads
the namelist; `check_namelist_consistency` enforces the combinations that are
allowed given `use_cn`, `use_crop`, and `use_fates`.

A separate IAC mutual-exclusion check inside `read_namelist`
(`:158-169`) aborts the run if `iac_present` is set together with any of
`do_harvest`, `do_transient_pfts`, `do_transient_crops`, or a non-empty
`flanduse_timeseries`.

The FATES LUH2 path is gated by two `elm_varctl` flags, **not** by the
`dynamic_subgrid` namelist:

- `use_fates_luh` (`main/elm_varctl.F90:249`, default `.false.`)
- `use_fates_potentialveg` (`main/elm_varctl.F90:251`, default `.false.`)
- `fates_harvest_mode` (`main/elm_varctl.F90:230`, character string; sentinel
  values defined in `dynFATESLandUseChangeMod.F90:33-37`)

Note that calling `get_do_harvest()` alone is no longer sufficient to
determine whether `dynHarvest_interp_harvest_types` runs in Pass B — the gate
is now `get_do_harvest() .or. fates_harvest_mode == fates_harvest_hlmlanduse`.

## 5. FAN N pools in `dyn_col_ns_Adjustments`

`dynSubgridAdjustmentsMod::dyn_col_ns_Adjustments` (`:810-1186`) now adjusts
~17 additional column-N state variables when the FAN (Flow of Agricultural
Nitrogen — fertilizer / manure / TAN) module is active. After the
`prod1n / prod10n / prod100n` adjustments (the only N pools in the older
tree), it adds `update_column_state_no_special_handling` calls for:

- `fan_totn` (`:953-961`)
- `tan_g1`, `tan_g2`, `tan_g3` — TAN (total ammoniacal nitrogen) grazing pools
  (`:963-991`)
- `tan_s0`, `tan_s1`, `tan_s2`, `tan_s3` — TAN soil pools (`:993-1031`)
- `tan_f1`, `tan_f2`, `tan_f3`, `tan_f4` — TAN flux pools (`:1033-1071`)
- `fert_u1`, `fert_u2` — urea fertilizer pools (`:1073-1091`)
- `manure_u_grz`, `manure_a_grz`, `manure_r_grz` — grazing manure (urinary /
  available / residual) (`:1093-1121`)
- `manure_u_app`, `manure_a_app`, `manure_r_app` — applied manure (`:1123-1151`)
- `manure_tan_stored`, `manure_n_stored` — stored manure (`:1153-1171`)
- `fan_grz_fract` — FAN grazing fraction (`:1173-1181`)

Each pool's adjustment accumulates into `col_ns%dyn_nbal_adjustments` so that
the column-N closure in `dyn_cnbal_column` includes them. Auditing the N
budget after a `dyn_subgrid` reweight on an FAN-active gridcell requires
including all of these pools, not just the legacy `prod*n` and decomposer
pools. See `dyn_subgrid/weight_updates_and_conservation.md` Section 6 for the
full inventory.

## 6. Where to read next

- For the transient land-use file I/O details (`dynFileMod`,
  `dynPriorWeightsMod`, `dynpftFileMod`, `dyncropFileMod`, `dynHarvestMod`,
  `dynTimeInfoMod`, `dynSubgridControlMod`), see
  `dyn_subgrid/transient_landuse.md`.
- For the FATES LUH2 reader and the IAC / EHC pathway
  (`dynFATESLandUseChangeMod`, `dyn_iac_init`, `set_iac_veg_weights`, the
  `iac2lnd_vars` argument, the `use_fates_luh` / `fates_harvest_mode` /
  `iac_present` namelist gates), see `dyn_subgrid/fates_land_use_change.md`.
- For the weight reconciliation and state / conservation routines
  (`dynLandunitAreaMod`, `dynPatchStateUpdaterMod`, `dynColumnStateUpdaterMod`,
  `dynColumnTemplateMod`, `dynInitColumnsMod`, `dynSubgridAdjustmentsMod`,
  `dynSubgridDriverMod`, `dynConsBiogeochemMod`, `dynConsBiogeophysMod`,
  `dynEDMod`), see `dyn_subgrid/weight_updates_and_conservation.md`.
