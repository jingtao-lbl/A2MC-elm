---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Dyn Subgrid — Weight Updates, State Updates, and Conservation

This document covers the set of `dyn_subgrid/` modules that run **after** a
file reader or coupling call has staged new primitive weights:

- `dynLandunitAreaMod` — reconciles landunit weights so they sum to 1 per
  topounit
- `dynPatchStateUpdaterMod` — patch-level "dwt" bookkeeping and
  state-with-fluxes updates
- `dynColumnStateUpdaterMod` — column-level state updater with four "fill"
  strategies
- `dynColumnTemplateMod` — templates for newly-active columns
- `dynInitColumnsMod` — copies state from the template into a newly-active
  column
- `dynSubgridAdjustmentsMod` — C/N/P adjustment routines per level (now
  including ~17 FAN nitrogen pools in `dyn_col_ns_Adjustments`)
- `dynSubgridDriverMod` — the two-pass driver that sequences all of the
  above (plus the IAC private routines `dyn_iac_init` and
  `set_iac_veg_weights`)
- `dynConsBiogeochemMod` — C/N/P conservation closures for patches and columns
- `dynConsBiogeophysMod` — water/energy conservation via dynbal fluxes
- `dynEDMod` — FATES bridge that copies `veg_pp%wt_ed` into `veg_pp%wtcol`

For the file reader modules (`dynFileMod`, `dynpftFileMod`, `dyncropFileMod`,
`dynHarvestMod`, `dynTimeInfoMod`, `dynPriorWeightsMod`,
`dynSubgridControlMod`) see `dyn_subgrid/transient_landuse.md`. For the FATES
LUH2 reader (`dynFATESLandUseChangeMod`) and the IAC / EHC pathway (the
`dyn_iac_init` and `set_iac_veg_weights` routines plus the `iac2lnd_vars`
update in Pass B), see `dyn_subgrid/fates_land_use_change.md`. For the overall
two-pass architecture see `dyn_subgrid/index.md`.

## 1. `dynLandunitAreaMod` — landunit reconciliation

Source: `dyn_subgrid/dynLandunitAreaMod.F90`.

### 1.1 `update_landunit_weights(bounds)`

For every topounit in the bounds (`dyn_subgrid/dynLandunitAreaMod.F90:36-88`):

1. Read all nine possible landunit weights from `lun_pp%wttopounit` via
   `top_pp%landunit_indices(ltype, t)`. Missing landunits get a weight of 0.
2. Call `update_landunit_weights_one_topounit` to rebalance them.
3. Write the rebalanced weights back into `lun_pp%wttopounit`. Non-zero weight
   on a non-existent landunit is a fatal error
   (`dyn_subgrid/dynLandunitAreaMod.F90:80-83`).

### 1.2 `update_landunit_weights_one_topounit(landunit_weights)`

In-place reconciliation (`dyn_subgrid/dynLandunitAreaMod.F90:92-165`):

- If the sum of all nine weights is within `1.e-14` of 1, do nothing.
- If the sum is `< 1`, add the deficit to `istsoil`. This is the "fallback to
  natural vegetation" rule.
- If the sum is `> 1`, remove the excess in a fixed priority order:

  ```fortran
  decrease_order(8) = (/ istsoil, istcrop, isturb_md, isturb_hd, &
                         isturb_tbd, istwet, istdlak, istice /)
  ```

  `istice_mec` is **deliberately excluded** so that CISM's coupled area is
  untouched. The comment at `dyn_subgrid/dynLandunitAreaMod.F90:117-126` warns
  that this means only one landunit at a time can be excluded from the
  priority list — otherwise the reconciliation would be ambiguous.

- After the reductions, the final sum must equal 1 to within `1.e-14`, or an
  error is printed. Note this is only a `print *` (not `endrun`) in the code.

## 2. `dynPatchStateUpdaterMod` — patch-level updater

Source: `dyn_subgrid/dynPatchStateUpdaterMod.F90`.

### 2.1 Type and snapshot methods

`patch_state_updater_type` (`dyn_subgrid/dynPatchStateUpdaterMod.F90:50-87`)
stores per-patch arrays:

| Field | Meaning |
|---|---|
| `pwtgcell_old(:)` | Prior patch weight on gridcell |
| `pwtgcell_new(:)` | New patch weight on gridcell |
| `cwtgcell_old(:)` | Prior column weight on gridcell |
| `dwt(:)` | `pwtgcell_new - pwtgcell_old` |
| `growing_old_fraction(:)` | `pwtgcell_old / pwtgcell_new`, valid only for growing patches |
| `growing_new_fraction(:)` | `dwt / pwtgcell_new`, valid only for growing patches |

Note that the IAC pathway also writes `veg_pp%wtgcell_iac` (declared on
`VegetationType`, not in `dyn_subgrid/`) which is read inside `dyn_iac_init`
and `set_iac_veg_weights` to drive the IAC weight update. See
`dyn_subgrid/fates_land_use_change.md` Section 2.

`set_old_patch_weights(this, bounds)`
(`dyn_subgrid/dynPatchStateUpdaterMod.F90:151-175`) captures the prior state.

`set_new_patch_weights(this, bounds)`
(`dyn_subgrid/dynPatchStateUpdaterMod.F90:178-210`) reads the post-update
`veg_pp%wtgcell` and fills `dwt`, `growing_old_fraction`, and
`growing_new_fraction`. Shrinking and constant patches get
`growing_old_fraction=1`, `growing_new_fraction=0` as safe defaults.

### 2.2 `update_patch_state` — the core state update

Source: `dyn_subgrid/dynPatchStateUpdaterMod.F90:213-290`.

For each patch, three cases:

- **`dwt > 0` (growing)**:
  ```
  var = var * growing_old_fraction(p)
  if (present(seed)) var = var + seed * growing_new_fraction(p)
  if (present(seed_addition)) seed_addition += seed * dwt(p)
  ```
  The patch state is diluted by the ratio of its old area to its new area,
  then optionally a "seed" amount is added at the rate the new area appears.

- **`dwt < 0` (shrinking)**:
  ```
  flux_out_grc_area += var * dwt(p)
  flux_out_col_area += var * (dwt(p) / cwtgcell_old(c))
  ```
  The vacated area's mass is accumulated as a flux out (negative because `dwt`
  is negative), reported either in gridcell-mean units or in column-mean units
  using the prior column weight.

- **`dwt = 0`**: no change.

The comment at `dyn_subgrid/dynPatchStateUpdaterMod.F90:235-243` emphasizes
that `flux_out_col_area` must be applied to column state **before** the column
state updater runs — otherwise the normalization by `cwtgcell_old` would be
wrong.

### 2.3 `update_patch_state_partition_flux_by_type`

Source: `dyn_subgrid/dynPatchStateUpdaterMod.F90:293-350`.

Wrapper that calls `update_patch_state` and then splits the resulting
`total_flux_out` into two fluxes (`flux1_out`, `flux2_out`) according to a
PFT-type lookup table `flux1_fraction_by_pft_type(0:)`. This is how
conversion fluxes are partitioned between product pools (for example
`pprod10` vs `pprod100`) in `dyn_cnbal_patch`.

### 2.4 Query helpers

`old_weight_was_zero`, `patch_grew`, and `patch_initiating`
(`dyn_subgrid/dynPatchStateUpdaterMod.F90:353-432`) return per-patch logical
arrays for "was zero last step", "grew this step", and "transitioned from
zero to non-zero this step" respectively. `dyn_cnbal_patch` uses
`patch_initiating` to seed new patches with a reasonable amount of leaf /
deadstem C, N, and P.

## 3. `dynColumnStateUpdaterMod` — column-level updater

Source: `dyn_subgrid/dynColumnStateUpdaterMod.F90`.

### 3.1 Type and prior-state capture

`column_state_updater_type` (`dyn_subgrid/dynColumnStateUpdaterMod.F90:120-152`)
owns:

- `cwtgcell_old(:)`, `cwtgcell_new(:)`, `area_gained_col(:)` — column weights
  and per-column `dwt_col`
- `natveg_template_col(:)` — for each column, a template column chosen at the
  time of `set_old_column_weights` from the natural veg landunit
- `any_changes(nclumps)` — clump-local "did anything change" flag so the
  updater can short-circuit on clumps with no weight changes

`set_old_column_weights` (`dyn_subgrid/dynColumnStateUpdaterMod.F90:213-241`)
stores `col_pp%wtgcell` and calls `template_col_from_natveg_array` on the
**prior** `col_pp%active` flags so that a newly-active column does not pick
itself as a template.

`set_new_column_weights` (`dyn_subgrid/dynColumnStateUpdaterMod.F90:244-275`)
stores the new gridcell weights, computes `area_gained_col`, and sets
`any_changes(clump_index) = .true.` if any column's weight changed.

### 3.2 Four update strategies

The module offers four public update methods (see the block comment at
`dyn_subgrid/dynColumnStateUpdaterMod.F90:22-90`):

| Method | Use when |
|---|---|
| `update_column_state_no_special_handling` | State variable is valid on every landunit; or you want mass under a shrinking column to stay frozen in place beneath the growing special column |
| `update_column_state_fill_special_using_natveg` | Special landunits contribute mass equal to the state on the first natural veg column in the gridcell |
| `update_column_state_fill_using_fixed_values` | Each special landunit type has its own fixed contribution value; pass `FILLVAL_USE_EXISTING_VALUE = spval` to preserve the existing value |
| `update_column_state_fill_special_using_fixed_value` | Convenience wrapper when the single fixed value applies to all special landunits |

Every strategy accepts optional `fractional_area_old` and `fractional_area_new`
arguments for cases like inundated-fraction-scaled state variables, and emits
an optional per-column `adjustment(:)` diagnostic plus an inout
`non_conserved_mass_grc(:)` accumulator so multiple state variables can share
a single "mass that left the gridcell" tally.

All four methods eventually call the private
`update_column_state_with_optional_fractions` → `update_column_state` pathway
(`dyn_subgrid/dynColumnStateUpdaterMod.F90:339-928`), which enforces a
conservation tolerance of `1.e-12` kg/m² per call.

## 4. `dynColumnTemplateMod` — template lookup

Source: `dyn_subgrid/dynColumnTemplateMod.F90`.

Two public functions with identical semantics at different resolutions
(`dyn_subgrid/dynColumnTemplateMod.F90:30-165`):

- `template_col_from_landunit(bounds, c_target, landunit_type, cactive)` —
  returns the index of the first active column on the given landunit type in
  `c_target`'s gridcell, or `TEMPLATE_NONE_FOUND` (= `ispval`) if none exists.
  The caller is expected to pass `cactive` from the **prior** time step so
  the template is something that was already alive before the current step
  started. The body uses `col_pp%is_soil(c)` (`:33`) instead of the older
  `col_pp%itype(c) == istsoil` predicate; the semantics are unchanged.
- `template_col_from_natveg_array(bounds, cactive, c_templates)` — array
  version that calls the single-column function with `landunit_type=istsoil`.

The code path inside `template_col_from_landunit` walks columns under the
matching landunit with `do while`, stopping on the first active entry.

## 5. `dynInitColumnsMod` — seeding newly-active columns

Source: `dyn_subgrid/dynInitColumnsMod.F90`.

`initialize_new_columns(bounds, cactive_prior, soilhydrology_vars)`
(`dyn_subgrid/dynInitColumnsMod.F90:44-76`) walks every column. If the column
is active now but was inactive last step, it calls
`initial_template_col_dispatcher` to find a template column and then
`copy_state(c, c_template, soilhydrology_vars)` to copy a curated subset of
state variables. If no template exists, a warning is printed and the column
continues with whatever defaults were loaded at allocation.

The private helpers at `dyn_subgrid/dynInitColumnsMod.F90:80-294` dispatch:

- `initial_template_col_soil` — natural vegetation column: look for any other
  active natural veg column in the same topounit first, then anywhere in the
  gridcell.
- `initial_template_col_crop` — crop column: walk crop columns in the same
  topounit / gridcell.
- `initial_template_col_dispatcher` — picks the correct helper based on the
  landunit type of the target column.

`copy_state` copies a short list of soil hydrology and column energy-state
variables; the exact list is maintained inline in the subroutine.

## 6. `dynSubgridAdjustmentsMod` — per-level C/N/P adjustments

Source: `dyn_subgrid/dynSubgridAdjustmentsMod.F90` (1658 lines at d40b8431).

Six public entry points (`dyn_subgrid/dynSubgridAdjustmentsMod.F90:40-46`):

- `dyn_veg_cs_Adjustments` — adjust vegetation carbon state
- `dyn_col_cs_Adjustments` — adjust column carbon state
- `dyn_veg_ns_Adjustments` — vegetation nitrogen state
- `dyn_col_ns_Adjustments` — column nitrogen state (now ~377 lines including
  ~17 FAN N pools; `:810-1186`)
- `dyn_veg_ps_Adjustments` — vegetation phosphorus state
- `dyn_col_ps_Adjustments` — column phosphorus state

Each routine takes a landunit, column, and patch index `(l, c, p)`, the
`prior_weights` snapshot, and a `patch_state_updater`. Internally they call
`update_patch_state` / `update_patch_state_partition_flux_by_type` from
`dynPatchStateUpdaterMod` (for vegetation pools) or
`update_column_state_no_special_handling` from `dynColumnStateUpdaterMod` (for
column pools), passing in the specific variables they own — leaf, fine root,
live / dead stem, live / dead coarse root, storage, retranslocation pools,
etc. — along with per-PFT seed and conversion parameters.

Two module-scalar "seed" constants sit at the top of the file
(`dyn_subgrid/dynSubgridAdjustmentsMod.F90:36-38`):

```
real(r8), parameter :: npool_seed_param = 0.1_r8
real(r8), parameter :: ppool_seed_param = 0.01_r8
```

These set the amount of N and P that is seeded per unit of new leaf C when a
growing patch is initialised — the companion of the C seed values that come
from `pftvarcon`.

### 6.1 FAN N-pool inventory in `dyn_col_ns_Adjustments`

`dyn_col_ns_Adjustments` (`:810-1186`) handles the column nitrogen state. The
associate block (`:833-865`) names every pool it touches. After the legacy
decomposer pools (`decomp_npools_vr`, `ntrunc_vr`, `sminn_vr`, `smin_nh4_vr`,
`smin_no3_vr`, `:870-918`) and the three product pools (`prod1n`, `prod10n`,
`prod100n`, `:919-951`), the routine adjusts the following FAN (Flow of
Agricultural Nitrogen — fertilizer / manure / TAN) pools, in source order:

| # | Pool | Lines | Description |
|---|------|-------|-------------|
| 1 | `fan_totn` | `:953-961` | Total FAN nitrogen bookkeeping |
| 2 | `tan_g1` | `:963-971` | TAN (total ammoniacal nitrogen) grazing pool 1 |
| 3 | `tan_g2` | `:973-981` | TAN grazing pool 2 |
| 4 | `tan_g3` | `:983-991` | TAN grazing pool 3 |
| 5 | `tan_s0` | `:993-1001` | TAN soil pool 0 |
| 6 | `tan_s1` | `:1003-1011` | TAN soil pool 1 |
| 7 | `tan_s2` | `:1013-1021` | TAN soil pool 2 |
| 8 | `tan_s3` | `:1023-1031` | TAN soil pool 3 |
| 9 | `tan_f1` | `:1033-1041` | TAN flux pool 1 |
| 10 | `tan_f2` | `:1043-1051` | TAN flux pool 2 |
| 11 | `tan_f3` | `:1053-1061` | TAN flux pool 3 |
| 12 | `tan_f4` | `:1063-1071` | TAN flux pool 4 |
| 13 | `fert_u1` | `:1073-1081` | Urea fertilizer pool 1 |
| 14 | `fert_u2` | `:1083-1091` | Urea fertilizer pool 2 |
| 15 | `manure_u_grz` | `:1093-1101` | Grazing manure, urinary fraction |
| 16 | `manure_a_grz` | `:1103-1111` | Grazing manure, available fraction |
| 17 | `manure_r_grz` | `:1113-1121` | Grazing manure, residual fraction |
| 18 | `manure_u_app` | `:1123-1131` | Applied manure, urinary fraction |
| 19 | `manure_a_app` | `:1133-1141` | Applied manure, available fraction |
| 20 | `manure_r_app` | `:1143-1151` | Applied manure, residual fraction |
| 21 | `manure_tan_stored` | `:1153-1161` | Stored manure TAN |
| 22 | `manure_n_stored` | `:1163-1171` | Stored manure total N |
| 23 | `fan_grz_fract` | `:1173-1181` | FAN grazing fraction |

Each pool gets its own `update_column_state_no_special_handling` call against
the column-state updater, and the per-column `adjustment_one_level(begc:endc)`
output accumulates into `col_ns%dyn_nbal_adjustments(begc:endc)` so that
`dyn_cnbal_column` sees the full N delta. Auditing the N budget after a
`dyn_subgrid` reweight on an FAN-active gridcell requires including all of
these pools — they are only zero if FAN is inactive on the column.

## 7. `dynSubgridDriverMod` — the two-pass sequencer

Source: `dyn_subgrid/dynSubgridDriverMod.F90`.

Three public entry points:

- `dynSubgrid_init(bounds, glc2lnd_vars, crop_vars)` (lines 74-154) — builds
  `prior_weights`, `patch_state_updater`, `column_state_updater`, opens the
  dynamic files if their flags are set, runs the first `_interp` pass, calls
  `dyn_iac_init` if `iac_present`, and wraps up weight changes per clump.
- `dynSubgrid_driver(bounds_proc, …, iac2lnd_vars)` (lines 157-360) —
  executes the time-step dynamics in the three passes laid out in
  `dyn_subgrid/index.md`: Pass A captures prior state (clump-level), Pass B
  does the I/O-bound interpolation (proc-level, outside OMP), and Pass C
  reconciles weights, reruns `reweight_wrapup`, adjusts state, and closes the
  biogeophys and biogeochem budgets. The signature now ends with
  `iac2lnd_vars` (`:225`), used in Pass B at `:284-286`.
- `dynSubgrid_wrapup_weight_changes(bounds_clump, glc2lnd_vars)`
  (lines 363-406) — the reusable building block that reconciles landunit
  weights, computes higher-order weights, and calls `reweight_wrapup`. **When
  `iac_present`** it now runs `reweight_wrapup` once early (`:394-395`),
  invokes `set_iac_veg_weights(bounds_clump)` (`:396`) to overwrite all four
  levels of patch weights from `veg_pp%wtgcell_iac`, then runs
  `reweight_wrapup` again at the end (`:403`). When `.not. iac_present`,
  only the final `reweight_wrapup` runs.

The module also defines two private routines `dyn_iac_init` (`:409-462`) and
`set_iac_veg_weights` (`:465-553`) for the IAC / EHC path — see
`dyn_subgrid/fates_land_use_change.md` Section 2.

Pass C also calls `CarbonStateUpdateDynPatch`, `NitrogenStateUpdateDynPatch`,
and `PhosphorusStateUpdateDynPatch` from the state-update modules
(`dyn_subgrid/dynSubgridDriverMod.F90:340-347`). These transfer root / seed
litter C, N, and P that `dyn_cnbal_patch` accumulated into the decomposer
pools.

## 8. `dynConsBiogeophysMod` — water and energy conservation

Source: `dyn_subgrid/dynConsBiogeophysMod.F90`.

Two public subroutines and two private helpers.

### 8.1 `dyn_hwcontent_init(...)` — before weights change

Source: `dyn_subgrid/dynConsBiogeophysMod.F90:47-97`.

Calls `dyn_water_content` to compute per-gridcell `liquid_mass` and
`ice_mass`, and `dyn_heat_content` to compute per-gridcell `heat_grc` and
`liquid_water_temp_grc`. The results are stored in `grc_ws%liq1`,
`grc_ws%ice1`, `grc_es%heat1`, `grc_es%liquid_water_temp1`.

### 8.2 `dyn_hwcontent_final(..., dtime)` — after weights change

Source: `dyn_subgrid/dynConsBiogeophysMod.F90:100-197`.

Computes the same four quantities into the `*2` slots, then:

```
delta_liq(g)  = liq2(g)  - liq1(g)
delta_ice(g)  = ice2(g)  - ice1(g)
delta_heat(g) = heat2(g) - heat1(g)
grc_wf%qflx_liq_dynbal(g) = delta_liq(g) / dtime
grc_wf%qflx_ice_dynbal(g) = delta_ice(g) / dtime
grc_ef%eflx_dynbal(g)     = delta_heat(g) / dtime
```

These "dynbal" fluxes are sent to the coupler and compensate for the change
in gridcell-mean water and heat content that is due purely to the
redistribution of area among subgrid patches, not to any physical process.
Setting `for_testing_zero_dynbal_fluxes=.true.` (testing only) zeros them,
which **breaks conservation** but lets tests with unrealistic daily weight
changes run without crashing CAM
(`dyn_subgrid/dynConsBiogeophysMod.F90:159-164`).

The commented-out `AdjustDeltaHeatForDeltaLiq` and `*_dribbler` calls
(`dyn_subgrid/dynConsBiogeophysMod.F90:175-195`) are remnants of an earlier
"dribble" scheme that spread the correction over several time steps; the
current code does it in one step.

### 8.3 Private helpers

- `dyn_water_content(...)` (`dyn_subgrid/dynConsBiogeophysMod.F90:200-249`) —
  calls `ComputeLiqIceMassNonLake` and `ComputeLiqIceMassLake` at the column
  level and averages to gridcell using `c2g` with the `unity` scale.
- `dyn_heat_content(...)` (`dyn_subgrid/dynConsBiogeophysMod.F90:253-341`) —
  computes column heat content with `ComputeHeatNonLake` and
  `ComputeHeatLake`. Heat content is relative to 0 °C (= `heat_base_temp`),
  with liquid water carrying the latent heat of fusion. The weighted
  liquid-water temperature is computed from `heat_liquid_grc / cv_liquid_grc`.

## 9. `dynConsBiogeochemMod` — C, N, P conservation

Source: `dyn_subgrid/dynConsBiogeochemMod.F90`.

Two public entry points:

- `dyn_cnbal_patch(bounds, num_soilp_with_inactive, filter_soilp_with_inactive,
  num_soilc_with_inactive, filter_soilc_with_inactive, prior_weights,
  patch_state_updater, canopystate_vars, photosyns_vars, cnstate_vars,
  veg_cs, c13_veg_cs, c14_veg_cs, veg_ns, veg_ps, dt)`
  (`dyn_subgrid/dynConsBiogeochemMod.F90:54-1100+`)
- `dyn_cnbal_column(bounds, nc, column_state_updater, col_cs, c13_col_cs,
  c14_col_cs, col_ns, col_ps)` (elsewhere in the same file)

`dyn_cnbal_patch` works on the **inactive + active** soil patch filter so it
can visit patches that just became inactive. For each such patch it computes
`dwt = veg_pp%wtcol(p) - prior_weights%pwtcol(p)` and then:

- **Growing patches** (`dwt > 0`): compute seed amounts (`dwt_leafc_seed`,
  `dwt_deadstemc_seed`, `dwt_npool_seed`, `dwt_ppool_seed`, matching C13 /
  C14 / N / P arrays) by multiplying per-PFT seed rates from `pftvarcon` by
  `dwt` and `ComputeSeedAmounts`.
- **Shrinking patches** (`dwt < 0`): compute the per-patch litter / product
  fluxes by calling `update_patch_state` with a combination of
  `flux_out_col_area` (for root/stem → litter within the same column) and
  `flux_out_grc_area` (for aboveground wood → 10-yr and 100-yr product pools
  with partitioning parameters `pconv`, `pprod10`, `pprod100` from
  `pftvarcon`).

Local scratch arrays `dwt_leafc_seed`, `dwt_frootc_to_litter`,
`dwt_livecrootc_to_litter`, `dwt_deadcrootc_to_litter`, `conv_cflux`,
`prod10_cflux`, `prod100_cflux`, `crop_product_cflux`, and the matching
N and P versions (`dyn_subgrid/dynConsBiogeochemMod.F90:99-132`) accumulate
these contributions per patch.

After the patch loop, `dyn_cnbal_patch` calls the matching
`dyn_veg_cs_Adjustments`, `dyn_veg_ns_Adjustments`, `dyn_veg_ps_Adjustments`
routines from `dynSubgridAdjustmentsMod` to apply the accumulated fluxes to
each specific state variable. C13 and C14 branches exist only when
`use_c13` / `use_c14` is true and allocate their per-patch arrays at runtime.

`dyn_cnbal_column` performs the column-level counterpart, using
`column_state_updater` to distribute column-level mass across changing column
weights and calling `dyn_col_cs_Adjustments`, `dyn_col_ns_Adjustments`, and
`dyn_col_ps_Adjustments`. The N closure now includes the ~17 FAN pools
listed in Section 6.1 above; an audit that omits them will not balance on an
FAN-active gridcell.

## 10. `dynEDMod` — FATES bridge

Source: `dyn_subgrid/dynEDMod.F90`.

The only entry point is `dyn_ED(bounds)`
(`dyn_subgrid/dynEDMod.F90:22-42`), a 20-line routine that walks every patch
in the bounds and, for active `istsoil` columns only, copies
`veg_pp%wt_ed(p)` (the weight FATES publishes back to ELM) into
`veg_pp%wtcol(p)`. Patches that are neither `is_veg` nor `is_bareground` get
`wtcol = 0`. This call runs at
`dyn_subgrid/dynSubgridDriverMod.F90:296-298`, before `update_glc2lnd` and
before `dynSubgrid_wrapup_weight_changes`.

`dyn_ED` is the FATES-side weight-publication path that complements the
LUH2-driven land-use change handled by `dynFATESLandUseChangeMod` (which
publishes `landuse_states`, `landuse_transitions`, and `landuse_harvest` for
FATES to consume but does **not** modify `veg_pp%wtcol` itself). See
`dyn_subgrid/fates_land_use_change.md` Section 1.

## 11. How everything interlocks

```
New weights written (dynpft_interp, dyncrop_interp, dyn_ED, update_glc2lnd,
                     iac2lnd_vars%update_iac2lnd → set_iac_veg_weights)
                                |
                                v
update_landunit_weights         (sum to 1 on every topounit)
                                |
                                v
compute_higher_order_weights    (wtgcell, wttopounit, wtlunit chain)
                                |
                                v
[if iac_present] reweight_wrapup + set_iac_veg_weights                    
                                |
                                v
reweight_wrapup                 (set_active; check_weights x 2; setFilters)
                                |
                                v
set_new_patch_weights           (dwt, growing_old/new_fraction)
set_new_column_weights          (area_gained_col, any_changes)
                                |
                                v
set_subgrid_diagnostic_fields   (PCT_* history arrays)
                                |
                                v
initialize_new_columns          (template copy into newly-active columns)
                                |
                                v
dyn_hwcontent_final             (grc_ws%liq2, grc_es%heat2 -> dynbal fluxes)
                                |
                                v
dyn_cnbal_patch                 (veg C/N/P + C13/C14 with seed and product pools)
CarbonStateUpdateDynPatch
NitrogenStateUpdateDynPatch
PhosphorusStateUpdateDynPatch
                                |
                                v
dyn_cnbal_column                (col C/N/P close, including 17 FAN N pools)
```

The conservation guarantees are:

- **Water and energy** — `dyn_hwcontent_final` emits per-gridcell
  `qflx_liq_dynbal`, `qflx_ice_dynbal`, and `eflx_dynbal` whose integrals over
  the time step equal the change in `liq1→liq2`, `ice1→ice2`, and
  `heat1→heat2`. These are fed back through the coupler so the atmosphere
  sees a closed budget even though individual columns grew or shrank.
- **Carbon** — the patch updater diverts shrinking patches' leaf / storage /
  stem C into `pprod10`, `pprod100`, and the crop product pool according to
  PFT parameters, while routing root / coarse-root C into the column litter
  decomposer pools. Growing patches are seeded with a small `leafc_seed +
  deadstemc_seed` so they start in a physically reasonable state rather than
  from zero.
- **Nitrogen and phosphorus** — the same accounting machinery as carbon, with
  the fixed seed constants `npool_seed_param=0.1` and `ppool_seed_param=0.01`
  (`dyn_subgrid/dynSubgridAdjustmentsMod.F90:36-37`). N and P partitioning
  between product pools uses the same `pconv`, `pprod10`, `pprod100`
  constants from `pftvarcon`. The N closure now also includes ~17 FAN pools
  (`dyn_subgrid/dynSubgridAdjustmentsMod.F90:953-1181`).
- **Column-level closure** — for any state variable that exists on columns
  (soil carbon, soil nitrogen, etc.), `update_column_state` inside
  `dyn_cnbal_column` asserts that the total mass per gridcell changes by no
  more than `1.e-12` kg/m² due to the update
  (`dyn_subgrid/dynColumnStateUpdaterMod.F90:317`).

If any of these checks fails, the run aborts with an `endrun` call, which is
the design contract: conservation violations are bugs, not warnings.
