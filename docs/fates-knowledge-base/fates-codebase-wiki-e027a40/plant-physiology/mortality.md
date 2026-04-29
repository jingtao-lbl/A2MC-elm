# Mortality Processes

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/EDMortalityFunctionsMod.F90` (mechanistic mortality rates, derivative, `get_thaw_layer_index`)
- `biogeochem/EDLoggingMortalityMod.F90` (harvest mortality)
- `biogeochem/EDCohortDynamicsMod.F90` (`terminate_cohort`, `SendCohortToLitter`)
- `main/EDPftvarcon.F90` (`freezetol`, `mort_upthresh_cstarvation`, PFT mortality parameters)
- `main/EDParamsMod.F90` (`soil_tfrz_thresh`, `mortality_disturbance_fraction`)
- `main/FatesConstantsMod.F90` (`cstarvation_model_lin`, `cstarvation_model_exp`)
- `main/FatesInterfaceTypesMod.F90` (`hlm_mort_cstarvation_model`)
- `biogeochem/DamageMainMod.F90` (`GetDamageMortality`)

</details>

## Purpose and Scope

This document describes the mortality mechanisms in FATES at e027a40 computed by `mortality_rates()` (`EDMortalityFunctionsMod.F90:59`) and integrated by `Mortality_Derivative()` (`:289`). Mortality reduces cohort number density `cohort%n` directly for understory and non-woody cohorts, and generates disturbance (new patches) for a fraction of canopy woody mortality controlled by `mortality_disturbance_fraction`.

For crown damage class dynamics, see `crown_damage.md`. For litter transfers from dead cohorts, see `litter.md`.

## What Changed Since e85d997

Two material refactors of mortality at e027a40:

1. **Carbon-starvation mortality is now selectable between linear and exponential models** via the host-land-model switch `hlm_mort_cstarvation_model`. A new per-PFT parameter `fates_mort_upthresh_cstarvation` (default 1.0 for all 14 PFTs) replaces the previously hard-coded "1" in the linear formula.
2. **Non-hydro hydraulic-failure mortality is now a linear ramp**, gated by deciduous dormancy and frozen-soil checks. Previously a hard step. The frozen-soil gate uses `get_thaw_layer_index` and `soil_tfrz_thresh = -2.0 deg C` (`EDParamsMod.F90:74`), which is highly material for high-latitude sites that previously saw winter `hmort` hits.

Both refactors are documented in detail below.

## Seven Mechanistic Mortality Components + Logging

`mortality_rates()` (`EDMortalityFunctionsMod.F90:59`) computes seven fractional mortality rates (fraction per year) plus logging is computed separately in `LoggingMortality_frac()`:

| Code variable | Description | Key parameters | Source lines |
|---|---|---|---|
| `bmort` | Background (baseline intrinsic risk) | `fates_mort_bmort` | `:160` |
| `cmort` | Carbon starvation (linear OR exponential) | `fates_mort_scalar_cstarvation`, `fates_mort_upthresh_cstarvation`, `hlm_mort_cstarvation_model` | `:202-241` |
| `hmort` | Hydraulic failure (linear ramp; frozen-soil/dormancy gated in non-hydro) | `fates_mort_scalar_hydrfailure`, `fates_mort_hf_sm_threshold`, `fates_mort_hf_flc_threshold`, `soil_tfrz_thresh` | `:163-200` |
| `frmort` | Freezing stress | `fates_mort_scalar_coldstress`, `fates_mort_freezetol` | `:251-256` |
| `smort` | Size senescence (logistic) | `fates_mort_ip_size_senescence`, `fates_mort_r_size_senescence` | `:131-141` |
| `asmort` | Age senescence (logistic) | `fates_mort_ip_age_senescence`, `fates_mort_r_age_senescence` | `:144-156` |
| `dgmort` | Crown damage mortality | from `DamageMainMod%GetDamageMortality` | `:151-156` |
| `lmort_*` | Logging (direct/collateral/infra) | Harvest parameters | `EDLoggingMortalityMod.F90` |

The freezing-tolerance parameter is **`fates_mort_freezetol`** (internal name `freezetol`). Verified at `EDPftvarcon.F90:56` (declaration) and `:329-331` (load). NOT `fates_frzleaftol`. JSON entry at `parameter_files/fates_params_default.json:1013-1019`.

## Mortality Equations

### Background

PFT constant. `bmort = EDPftvarcon_inst%bmort(cohort_in%pft)` (`:160`).

### Carbon Starvation (selectable model, e027a40)

`EDMortalityFunctionsMod.F90:202-241`. When `cohort_in%dbh > 0`, compute the fully-flushed leaf target:

```fortran
call bleaf(cohort_in%dbh, cohort_in%pft, cohort_in%crowndamage, &
           cohort_in%canopy_trim, 1.0_r8, target_leaf_c)
store_c = cohort_in%prt%GetState(store_organ, carbon12_element)
call storage_fraction_of_target(target_leaf_c, store_c, frac)
```

The `1.0_r8` for `elongf_leaf` makes the target the fully-flushed leaf carbon, deliberate so that drought/cold-deciduous plants without leaves are not mis-classified as non-starving.

Then dispatch on `hlm_mort_cstarvation_model`:

```fortran
select case (hlm_mort_cstarvation_model)
case (cstarvation_model_lin)   ! = 1
   cmort = mort_scalar_cstarvation(pft) * &
           max(0.0_r8, (mort_upthresh_cstarvation(pft) - frac) / mort_upthresh_cstarvation(pft))
case (cstarvation_model_exp)   ! = 2
   cmort = mort_scalar_cstarvation(pft) * &
           exp(- frac / mort_upthresh_cstarvation(pft))
case default
   call endrun(...)   ! Invalid carbon starvation model
end select
```

Constants `cstarvation_model_lin = 1` and `cstarvation_model_exp = 2` are at `FatesConstantsMod.F90:168-169`. The host-land-model switch `hlm_mort_cstarvation_model` is declared at `FatesInterfaceTypesMod.F90:165` and must be set explicitly (initial value `unset_int` at `FatesInterfaceMod.F90:1566` triggers an error if left unset, see `:1877-1879`).

The new per-PFT parameter `fates_mort_upthresh_cstarvation` is loaded into `EDPftvarcon_inst%mort_upthresh_cstarvation` at `EDPftvarcon.F90:509-511`. Default 1.0 for all 14 PFTs (`parameter_files/fates_params_default.json:1097-1103`).

**Behavioral notes:**
- In the linear model, `cmort` is zero when `frac >= mort_upthresh_cstarvation(pft)` and reaches `mort_scalar_cstarvation(pft)` when `frac = 0`. With the default `mort_upthresh_cstarvation = 1`, this reduces exactly to the legacy `mort_scalar_cstarvation * max(0, 1 - frac)` formula.
- In the exponential model, `mort_upthresh_cstarvation(pft)` acts as the e-folding scale: smaller values produce faster decay of `cmort` with increasing `frac`.

A guard at `:240-242` zeros `cmort` when it falls below `nearzero`.

### Hydraulic Failure (linear ramp, frozen-soil gated)

`EDMortalityFunctionsMod.F90:163-200`. Two branches:

**With plant hydraulics (`hlm_use_planthydro == itrue`)**: compute the minimum fraction of max conductivity across aboveground, transporting-root, and absorbing-root compartments, convert to fractional loss `flc = 1 - min_fmc`, and if `flc >= hf_flc_threshold` use a linear ramp (`:172-178`):

```fortran
hmort = (flc - hf_flc_threshold) / (1.0_r8 - hf_flc_threshold) * &
         EDPftvarcon_inst%mort_scalar_hydrfailure(cohort_in%pft)
```

**Without plant hydraulics (`:180-200`)** -- this is the path materially refactored from e85d997. The hard step function is gone. Now there are three required conditions plus a linear ramp:

```fortran
call get_thaw_layer_index(site_in, cohort_in, bc_in, max_soil_ind)

if ( (.not. is_decid_dormant) .and. &
     ( btran_ft(cohort_in%pft) <= hf_sm_threshold ) .and. &
     ( ( minval(bc_in%t_soisno_sl(1:max_soil_ind)) - tfrz ) > soil_tfrz_thresh ) ) then
   hmort = EDPftvarcon_inst%mort_scalar_hydrfailure(cohort_in%pft) * &
           ((hf_sm_threshold - btran_ft(cohort_in%pft)) / hf_sm_threshold)
else
   hmort = 0.0_r8
end if
```

Three new gates compared with e85d997:

1. **`is_decid_dormant`** (declared at `:104`, set at `:115-118`). For deciduous PFTs (`phen_leaf_habit` is one of `ihard_season_decid`, `ihard_stress_decid`, `isemi_stress_decid`), if the cohort `status_coh == leaves_off`, the cohort is exempt from hydraulic-failure mortality. Reasoning (per source comment `:108-113`): plants without leaves cannot die of hydraulic failure.
2. **Frozen-soil gate.** `hmort` is calculated only when `(min(t_soisno_sl(1:max_soil_ind)) - tfrz) > soil_tfrz_thresh`. The threshold `soil_tfrz_thresh = -2.0_r8 deg C` is at `EDParamsMod.F90:74`. The helper `get_thaw_layer_index()` at `EDMortalityFunctionsMod.F90:412-451` returns the deepest layer in which a cumulative root fraction of 0.75 (`hmort_thaw_frac_threshold`, hardcoded at `:435`) is reached; soils above that index must be thawed for hmort to fire. `btran` itself is zero for frozen layers, so a step function would have generated spurious winter mortality for high-latitude sites.
3. **Linear ramp.** `hmort` linearly increases from 0 to `mort_scalar_hydrfailure(pft)` as `btran_ft` falls from `hf_sm_threshold` to 0. Was a hard step at e85d997.

**Implication for Arctic sites:** the e85d997 step-function description over-estimated winter mortality both because of frozen-layer false triggers and because dormant cold-deciduous plants are now exempt. Calibrating `hf_sm_threshold` and `mort_scalar_hydrfailure` against the e85d997 description will be off.

### Freezing Stress

`EDMortalityFunctionsMod.F90:251-256`. A 5-degree linear ramp from no mortality to full:

```fortran
temp_dep_fraction = max(0.0_r8, min(1.0_r8, &
                    1.0_r8 - (temp_in_C - EDPftvarcon_inst%freezetol(cohort_in%pft)) / frost_mort_buffer))
frmort = EDPftvarcon_inst%mort_scalar_coldstress(cohort_in%pft) * temp_dep_fraction
```

with `frost_mort_buffer = 5.0_r8` declared as a local parameter at `EDMortalityFunctionsMod.F90:103`. So `frmort` reaches `mort_scalar_coldstress` when `temp_in_C = freezetol - 5` or below, zero when `temp_in_C >= freezetol`. `temp_in_C = mean_temp - tfrz` is computed at `:249`.

Default `fates_mort_freezetol` per PFT (`parameter_files/fates_params_default.json:1013-1019`): `[2.5, -55.0, -80.0, -30.0, 2.5, -80.0, -60.0, -10.0, -80.0, -71.0, -95.0, -89.0, -20.0, 2.5]`. Note the new arctic-shrub PFTs 10 (`broadleaf_evergreen_arctic_shrub`) and 11 (`broadleaf_colddecid_arctic_shrub`) at -71 and -95 deg C, and PFT#12 (`arctic_c3_grass`) at -89 deg C.

### Size Senescence

`EDMortalityFunctionsMod.F90:131-141`. Logistic function, only active if `mort_ip_size_senescence(pft) < fates_check_param_set`:

```fortran
smort = 1.0_r8 / (1.0_r8 + exp(-1.0_r8 * mort_r_size_senescence * (cohort_in%dbh - mort_ip_size_senescence)))
```

Defaults are `null` for all 14 PFTs (off). Sets `smort = 0` when off.

### Age Senescence

`EDMortalityFunctionsMod.F90:144-156`. Same logistic form using cohort age:

```fortran
asmort = 1.0_r8 / (1.0_r8 + exp(-1.0_r8 * mort_r_age_senescence * (cohort_in%coage - mort_ip_age_senescence)))
```

Defaults are `null` for all 14 PFTs (off).

### Damage Mortality

`EDMortalityFunctionsMod.F90:151-156`. Delegated:

```fortran
if (hlm_use_tree_damage == itrue) then
   call GetDamageMortality(cohort_in%crowndamage, cohort_in%pft, dgmort)
else
   dgmort = 0.0_r8
end if
```

## Prescribed Physiology Mode

`EDMortalityFunctionsMod.F90:260-269`. When `hlm_use_ed_prescribed_phys == itrue`, all mechanistic mortality is disabled:

```
bmort = prescribed_mortality_canopy    if canopy_layer == 1
bmort = prescribed_mortality_understory otherwise
cmort = hmort = frmort = 0
```

Defaults at `parameter_files/fates_params_default.json:1051-1064`: `prescribed_mortality_canopy = 0.0194`, `prescribed_mortality_understory = 0.025` (uniform across the 14 PFTs).

## Mortality Derivative and Disturbance Generation

`Mortality_Derivative()` (`EDMortalityFunctionsMod.F90:289-381`) combines all rates and converts from fractional-per-year to number-density-per-day using `hlm_freq_day`. The critical distinction is between disturbance-generating and non-disturbance-generating mortality.

**Non-disturbance-generating** (directly reduces `cohort%n`, litter stays in the same patch):
- All understory cohort mortality
- All mortality of non-woody plants (determined by `ExemptTreefallDist()` at `:384-409`, which exempts any cohort whose PFT has `prt_params%woody == ifalse`)

**Disturbance-generating** (creates new patches via `spawn_patches()`):
- Fraction `mortality_disturbance_fraction` of canopy woody mortality (`:374`)
- Canopy logging mortality (direct + collateral + infrastructure)

## Integration with Daily Dynamics

Mortality rates are calculated and applied during `ed_integrate_state_variables()`. Dead biomass is transferred to litter via `SendCohortToLitter()` (`EDCohortDynamicsMod.F90`) for terminated cohorts, and to coarse woody debris for canopy disturbance.

## Key Parameters

| JSON key | Internal | Units | Role |
|---|---|---|---|
| `fates_mort_bmort` | `bmort(pft)` | yr^-1 | Background rate. Default 0.014 (most PFTs); 0.016 PFT#10, 0.01 PFT#11 |
| `fates_mort_scalar_cstarvation` | `mort_scalar_cstarvation(pft)` | yr^-1 | Max carbon starvation rate. Default 0.6 (most PFTs); 0.57 PFT#11 |
| `fates_mort_upthresh_cstarvation` | `mort_upthresh_cstarvation(pft)` | unitless | Upper threshold for `frac` above which linear cmort = 0; e-folding scale for exponential cmort. Default 1.0 (all PFTs). NEW at e027a40. |
| `fates_mort_scalar_hydrfailure` | `mort_scalar_hydrfailure(pft)` | yr^-1 | Max hydraulic failure rate. Default 0.6 (most); 0.8 PFT#11 |
| `fates_mort_hf_sm_threshold` | `hf_sm_threshold(pft)` | unitless | `btran` threshold for hydraulic failure (non-hydro mode). Default 1e-06 (all) |
| `fates_mort_hf_flc_threshold` | `hf_flc_threshold(pft)` | fraction | FLC threshold (hydro mode). Default 0.5 |
| `fates_mort_scalar_coldstress` | `mort_scalar_coldstress(pft)` | yr^-1 | Max freezing rate. Default 3.0 (most); 3.5 PFT#11; 2.3 PFT#12 |
| **`fates_mort_freezetol`** | `freezetol(pft)` | deg C | Freezing tolerance temperature (NOT `fates_frzleaftol`). Defaults span +2.5 to -95 deg C across 14 PFTs |
| `fates_mort_ip_size_senescence` | `mort_ip_size_senescence(pft)` | cm | Size-senescence inflection dbh. Default `null` (off) |
| `fates_mort_r_size_senescence` | `mort_r_size_senescence(pft)` | cm^-1 | Size-senescence rate |
| `fates_mort_ip_age_senescence` | `mort_ip_age_senescence(pft)` | years | Age-senescence inflection age. Default `null` (off) |
| `fates_mort_r_age_senescence` | `mort_r_age_senescence(pft)` | yr^-1 | Age-senescence rate |
| `fates_mort_disturb_frac` | `mortality_disturbance_fraction` | fraction | Fraction of canopy woody mortality that generates disturbance |
| `soil_tfrz_thresh` | `soil_tfrz_thresh` | deg C | Soil temperature threshold below which non-hydro hmort is suppressed. Hardcoded -2.0 in `EDParamsMod.F90:74` |

## Code Entry Points

| Function | Location | Purpose |
|---|---|---|
| `mortality_rates` | `EDMortalityFunctionsMod.F90:59` | Compute all seven component rates |
| `Mortality_Derivative` | `EDMortalityFunctionsMod.F90:289` | Integrate rates into number-density derivative |
| `ExemptTreefallDist` | `EDMortalityFunctionsMod.F90:384` | Test whether cohort is exempt from disturbance generation (woody flag) |
| `get_thaw_layer_index` | `EDMortalityFunctionsMod.F90:412` | Returns deepest soil layer index up to 75% cumulative root fraction; non-hydro hmort gate |
| `LoggingMortality_frac` | `EDLoggingMortalityMod.F90` | Compute logging mortality rates |
| `terminate_cohort` | `EDCohortDynamicsMod.F90` | Remove dead cohort |
| `SendCohortToLitter` | `EDCohortDynamicsMod.F90` | Transfer cohort biomass to litter pools |
