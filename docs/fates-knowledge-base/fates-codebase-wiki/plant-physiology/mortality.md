# Mortality Processes

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/EDMortalityFunctionsMod.F90` (mechanistic mortality rates, derivative)
- `biogeochem/EDLoggingMortalityMod.F90` (harvest mortality)
- `biogeochem/EDCohortDynamicsMod.F90` (`terminate_cohort`, `SendCohortToLitter`)
- `main/EDPftvarcon.F90` (`freezetol`, PFT mortality parameters)
- `biogeochem/DamageMainMod.F90` (`GetDamageMortality`)

</details>

## Purpose and Scope

This document describes the mortality mechanisms in FATES computed by `mortality_rates()` (`EDMortalityFunctionsMod.F90:51-230`) and integrated by `Mortality_Derivative()` (`:234` onward). Mortality reduces cohort number density `cohort%n` directly for understory and non-woody cohorts, and generates disturbance (new patches) for a fraction of canopy woody mortality controlled by `fates_mortality_disturbance_fraction`.

For crown damage class dynamics, see `crown_damage.md`. For litter transfers from dead cohorts, see `litter.md`.

## Seven Mechanistic Mortality Components + Logging

`mortality_rates()` computes seven fractional mortality rates (fraction per year) plus logging is computed separately in `LoggingMortality_frac()`:

| Code variable | Description | Key parameters | Source lines |
|---|---|---|---|
| `bmort` | Background (baseline intrinsic risk) | `fates_mort_bmort` | `:139` |
| `cmort` | Carbon starvation | `fates_mort_scalar_cstarvation` | `:167-191` |
| `hmort` | Hydraulic failure | `fates_mort_scalar_hydrfailure`, `fates_mort_hf_sm_threshold`, `fates_mort_hf_flc_threshold` | `:141-164` |
| `frmort` | Freezing stress | `fates_mort_scalar_coldstress`, `fates_mort_freezetol` | `:199-203` |
| `smort` | Size senescence (logistic) | `fates_mort_ip_size_senescence`, `fates_mort_r_size_senescence` | `:99-110` |
| `asmort` | Age senescence (logistic) | `fates_mort_ip_age_senescence`, `fates_mort_r_age_senescence` | `:112-124` |
| `dgmort` | Crown damage mortality | from `DamageMainMod%GetDamageMortality` | `:127-131` |
| `lmort_*` | Logging (direct/collateral/infra) | Harvest parameters | `EDLoggingMortalityMod.F90` |

The freezing-tolerance parameter is **`fates_mort_freezetol`** (internal name `freezetol`), not `fates_frzleaftol`. Verified at `EDPftvarcon.F90:372,813` and `:815` where it is loaded into `this%freezetol`.

## Mortality Equations

### Background

PFT constant. `bmort = EDPftvarcon_inst%bmort(pft)` (`:139`).

### Carbon Starvation

`:167-191`. When dbh > 0, compute `target_leaf_c = bleaf(dbh, pft, crowndamage, canopy_trim, elongf_leaf=1, ...)` (i.e., the leaf carbon assuming fully flushed). Then

```
frac = f( target_leaf_c, store_c )        ! via storage_fraction_of_target
cmort = max( 0, mort_scalar_cstarvation * (1 - frac) )    if frac < 1
cmort = 0                                                if frac >= 1
```

The fully-flushed target is deliberate so that drought/cold-deciduous plants without leaves are not mis-classified as non-starving.

### Hydraulic Failure

Two branches at `:144-164`:

**With plant hydraulics (`hlm_use_planthydro == itrue`)**: compute the minimum fraction of max conductivity across aboveground, transporting-root, and absorbing-root compartments, convert to fractional loss `flc = 1 - min_fmc`, and if `flc >= hf_flc_threshold` use a linear ramp:

```
hmort = (flc - hf_flc_threshold) / (1 - hf_flc_threshold) * mort_scalar_hydrfailure
```

**Without plant hydraulics**: simpler proxy via `btran_ft`:

```
if ( btran_ft(pft) <= hf_sm_threshold ) then
   hmort = mort_scalar_hydrfailure
else
   hmort = 0
end if
```

### Freezing Stress

`:199-203`. A 5-degree linear ramp from no mortality to full:

```fortran
temp_dep_fraction = max(0, min(1, 1 - (temp_in_C - freezetol(pft)) / frost_mort_buffer))
frmort            = mort_scalar_coldstress(pft) * temp_dep_fraction
```

with `frost_mort_buffer = 5.0_r8` declared as a local parameter at `EDMortalityFunctionsMod.F90:92`. So `frmort` reaches `mort_scalar_coldstress` when `temp_in_C = freezetol - 5` or below, zero when `temp_in_C >= freezetol`.

### Size Senescence

`:99-110`. Logistic function, only active if `mort_ip_size_senescence(pft) < fates_check_param_set`:

```
smort = 1 / ( 1 + exp( -mort_r_size_senescence * (dbh - mort_ip_size_senescence) ) )
```

### Age Senescence

`:112-124`. Same logistic form using cohort age:

```
asmort = 1 / ( 1 + exp( -mort_r_age_senescence * (coage - mort_ip_age_senescence) ) )
```

### Damage Mortality

`:127-131`. Delegated:

```fortran
if (hlm_use_tree_damage == itrue) then
   call GetDamageMortality(cohort_in%crowndamage, cohort_in%pft, dgmort)
else
   dgmort = 0.0_r8
end if
```

## Prescribed Physiology Mode

`:207-217`. When `hlm_use_ed_prescribed_phys == itrue`, all mechanistic mortality is disabled:

```
bmort = prescribed_mortality_canopy    if canopy_layer == 1
bmort = prescribed_mortality_understory otherwise
cmort = hmort = frmort = 0
```

## Mortality Derivative and Disturbance Generation

`Mortality_Derivative()` (`EDMortalityFunctionsMod.F90:234-323`) combines all rates and converts from fractional-per-year to number-density-per-day using `hlm_freq_day`. The critical distinction is between disturbance-generating and non-disturbance-generating mortality.

**Non-disturbance-generating** (directly reduces `cohort%n`, litter stays in the same patch):
- All understory cohort mortality
- All mortality of non-woody plants (determined by `ExemptTreefallDist()` at `:327-351`)

**Disturbance-generating** (creates new patches via `spawn_patches()`):
- Fraction `fates_mortality_disturbance_fraction` of canopy woody mortality
- Canopy logging mortality (direct + collateral + infrastructure)

## Integration with Daily Dynamics

Mortality rates are calculated and applied during `ed_integrate_state_variables()`. Dead biomass is transferred to litter via `SendCohortToLitter()` (`EDCohortDynamicsMod.F90`) for terminated cohorts, and to coarse woody debris for canopy disturbance.

## Key Parameters

| CDL name | Internal | Units | Role |
|---|---|---|---|
| `fates_mort_bmort` | `bmort(pft)` | yr^-1 | Background rate |
| `fates_mort_scalar_cstarvation` | `mort_scalar_cstarvation(pft)` | yr^-1 | Max carbon starvation rate |
| `fates_mort_scalar_hydrfailure` | `mort_scalar_hydrfailure(pft)` | yr^-1 | Max hydraulic failure rate |
| `fates_mort_hf_sm_threshold` | `hf_sm_threshold(pft)` | - | `btran` threshold for hydraulic failure (non-hydro mode) |
| `fates_mort_hf_flc_threshold` | `hf_flc_threshold(pft)` | fraction | FLC threshold (hydro mode) |
| `fates_mort_scalar_coldstress` | `mort_scalar_coldstress(pft)` | yr^-1 | Max freezing rate |
| **`fates_mort_freezetol`** | `freezetol(pft)` | deg C | Freezing tolerance temperature |
| `fates_mort_ip_size_senescence` | `mort_ip_size_senescence(pft)` | cm | Size-senescence inflection dbh |
| `fates_mort_r_size_senescence` | `mort_r_size_senescence(pft)` | cm^-1 | Size-senescence rate |
| `fates_mort_ip_age_senescence` | `mort_ip_age_senescence(pft)` | years | Age-senescence inflection age |
| `fates_mort_r_age_senescence` | `mort_r_age_senescence(pft)` | yr^-1 | Age-senescence rate |
| `fates_mortality_disturbance_fraction` | global | fraction | Fraction of canopy woody mortality that generates disturbance |

## Code Entry Points

| Function | Location | Purpose |
|---|---|---|
| `mortality_rates` | `EDMortalityFunctionsMod.F90:51-230` | Compute all seven component rates |
| `Mortality_Derivative` | `EDMortalityFunctionsMod.F90:234-323` | Integrate rates into number-density derivative |
| `ExemptTreefallDist` | `EDMortalityFunctionsMod.F90:327-351` | Test whether cohort is exempt from disturbance generation |
| `LoggingMortality_frac` | `EDLoggingMortalityMod.F90` | Compute logging mortality rates |
| `terminate_cohort` | `EDCohortDynamicsMod.F90` | Remove dead cohort |
| `SendCohortToLitter` | `EDCohortDynamicsMod.F90` | Transfer cohort biomass to litter pools |
