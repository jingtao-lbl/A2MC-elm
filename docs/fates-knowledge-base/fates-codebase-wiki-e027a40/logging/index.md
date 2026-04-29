---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Logging and Land Use

**Relevant source files:**
- `biogeochem/EDLoggingMortalityMod.F90` (1308 lines)
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/EDMortalityFunctionsMod.F90`
- `main/EDMainMod.F90`
- `main/EDParamsMod.F90`
- `main/EDTypesMod.F90`
- `main/FatesConstantsMod.F90`

## Purpose and Scope

This document describes the FATES implementation of anthropogenic disturbances through logging and land use change. It covers the timing of logging events, the four mortality/degradation fractions that describe logging impacts on vegetation, harvest rate calculations in both area-based and carbon-based modes, wood product export, and the integration of logging disturbances into the patch dynamics framework.

Related topics:

- [Harvest Rate Calculations](harvest_rates.md) — area- and carbon-based harvest rate derivation
- [Logging Mortality](mortality.md) — cohort-level application of logging fractions

For natural disturbances (fire and treefall) see the fire and core-dynamics topics.

## Logging Event Timing

The `IsItLoggingTime` subroutine determines whether logging should be enacted at the current dynamics step. At e027a40 the routine has two gating conditions: first the `hlm_use_logging` host flag, and then a comparison of model time to the scalar parameter `logging_event_code`. It sets the module-level flag `logging_time`, which gates all downstream logging mortality calculations.

The host-flag gate is the first executable statement in `IsItLoggingTime`:

```fortran
logging_time = .false.
icode = int(logging_event_code)

! this is true for either hlm harvest or fates logging
if(hlm_use_logging.eq.ifalse) return
```

If `hlm_use_logging .eq. ifalse`, `logging_time` stays `.false.` and the routine returns immediately, regardless of `logging_event_code`. This is independent of the separate `hlm_use_lu_harvest` switch documented below; both gates can disable logging.

Event-code semantics (from `IsItLoggingTime`):

| Code | Meaning |
|------|---------|
| `1` | Logging turned off; `logging_time=.false.` |
| `2` | First model day only (`hlm_model_day .eq. 1`) |
| `3` | Every day |
| `4` | First day of each month (`hlm_current_day .eq. 1`) |
| `-1` to `-365` (`< 0 .and. > -366`) | Specific day-of-year (`hlm_day_of_year .eq. abs(icode)`) |
| `> 10000` | Specific date encoded as `YYYYMMDD` |

Any other integer value triggers an error and run termination. When a logging event fires, `IsItLoggingTime` also zeroes the site-level diagnostic accumulators `delta_litter_stock`, `delta_biomass_stock`, and `delta_individual` so that the event-scale changes can be reported.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:116-203)`, `(main/EDMainMod.F90:179, 201-329)`

## Logging Mortality Types

FATES tracks four cohort-level logging fractions. The first three are killing fractions; the fourth is a degradation fraction that transfers surviving trees to a secondary patch without killing them.

### Direct Logging Mortality (`lmort_direct`)

Direct mortality applies to woody cohorts whose DBH satisfies `dbh >= logging_dbhmin` and, if `logging_dbhmax` is set (i.e., `< fates_check_param_set`), `dbh < logging_dbhmax`. For harvestable cohorts (`cur_harvest_tag` is `fates_no_harvest_debt` or `fates_bypass_harvest_debt`):

```
lmort_direct = harvest_rate * logging_direct_frac
```

For non-harvestable cohorts or unsuccessful carbon-based harvests (`cur_harvest_tag .eq. fates_insufficient_for_harvest_debt`), `lmort_direct = 0`. Non-woody plants are never subject to direct logging.

### Collateral Damage Mortality (`lmort_collateral`)

Collateral damage represents canopy trees felled as a side effect of harvesting target trees. For woody canopy-layer cohorts:

```
lmort_collateral = harvest_rate * logging_collateral_frac   (canopy_layer == 1)
lmort_collateral = 0.0                                      (understory)
```

Understory collateral effects are handled separately during `logging_litter_fluxes` (when biomass is moved from the donor to the newly spawned patch), not in `LoggingMortality_frac`.

### Infrastructure Mortality (`lmort_infra`)

Infrastructure mortality represents vegetation destroyed by roads, skid trails, and machinery. It applies to all plants (woody and non-woody) below a DBH threshold:

```
lmort_infra = harvest_rate * logging_mechanical_frac   (dbh < logging_dbhmax_infra)
lmort_infra = 0.0                                      (dbh >= logging_dbhmax_infra)
```

Infrastructure mortality is applied to both canopy and understory layers.

### Forest Degradation Fraction (`l_degrad`)

Degradation is the fraction of canopy area that is disturbed but does not kill trees. Surviving canopy trees in this area are transferred to a newly spawned secondary patch without mortality. It is computed residually, in the canopy layer only:

```
l_degrad = harvest_rate - (lmort_direct + lmort_infra + lmort_collateral)   (canopy)
l_degrad = 0.0                                                              (understory)
```

Sources: `(biogeochem/EDLoggingMortalityMod.F90:208-421)`

## Harvest Modes: Area-Based vs. Carbon-Based

Two harvest modes are selected from host boundary conditions. If `hlm_use_lu_harvest == ifalse` (and a logging event is otherwise scheduled), FATES falls back to a standalone mode where `harvest_rate = 1.0` (the full cohort area) is used.

### Area-Based Harvest

When `hlm_use_lu_harvest == itrue .and. hlm_harvest_units == hlm_harvest_area_fraction`, the host supplies harvest rates as gridcell-level fractions split across five LUH2 categories. The CLM/ELM surface-file names are `HARVEST_VH1` (primary forest), `HARVEST_VH2` (primary non-forest), `HARVEST_SH1` (secondary mature forest), `HARVEST_SH2` (secondary young forest), `HARVEST_SH3` (secondary non-forest). The direct-LUH2 driver names are `primf_harv`, `primn_harv`, `secmf_harv`, `secyf_harv`, `secnf_harv` (both naming conventions are accepted; see `get_harvest_rate_area`). `get_harvest_rate_area` maps these to a per-patch `harvest_rate` by selecting categories that match the patch's `land_use_label` and secondary age, and by normalizing by the site primary/secondary fractions. In this mode `harvest_tag(:) = fates_bypass_harvest_debt` (not applicable).

### Carbon-Based Harvest

When `hlm_use_lu_harvest == itrue .and. hlm_harvest_units == hlm_harvest_carbon`, harvest targets are specified as carbon mass. Before the cohort loop, `get_harvestable_carbon` sums merchantable bole carbon across patches per LUH2 category. `get_harvest_rate_carbon` then converts the target to an area-based `harvest_rate` and assigns each category a `harvest_tag` indicating success (`fates_no_harvest_debt`, value `0`), insufficient carbon (`fates_insufficient_for_harvest_debt`, value `1`), or not applicable (`fates_bypass_harvest_debt`, value `2`).

Sources: `(biogeochem/EDLoggingMortalityMod.F90:288-344, 426-769)`

## Primary vs. Secondary Patches and the Land-Use Label Space

Each patch carries a `land_use_label` and, if anthropogenically disturbed, an `age_since_anthro_disturbance`. The patch spawning logic in `EDPatchDynamicsMod` uses these fields to decide how new patches inherit the label.

The label space at e027a40 is broader than primary/secondary alone, reflecting the e027a40 land-use restructuring. The five non-bareground labels are `primaryland`, `secondaryland`, `pastureland`, `rangeland`, `cropland` (size of the `current_fates_landuse_state_vector(n_landuse_cats)` array, which is `n_landuse_cats = 5`). The matching `nocomp_bareground_land` label is used for explicitly bare patches. The new LU-dimensioned history variables (`FATES_GPP_LU`, `FATES_NPP_LU`, `FATES_VEGC_LU`, `FATES_PATCHAREA_LU`, etc.) are indexed across this same `fates_levlanduse=5` axis (see [Model Output and Diagnostics](../output/index.md)).

Secondary patches are further classified by age, using the parameter `secondary_age_threshold` (from `FatesConstantsMod`):

- **Secondary young**: `age_since_anthro_disturbance < secondary_age_threshold`
- **Secondary mature**: `age_since_anthro_disturbance >= secondary_age_threshold`

The threshold value is **94 years**, based on the average age of global 1900s-era secondary land from Hurtt et al. (2011). It is declared as a Fortran `parameter`:

```fortran
real(fates_r8), parameter, public :: secondary_age_threshold = 94._fates_r8
```

It is not user-tunable via the FATES parameter file.

Sources: `(main/FatesConstantsMod.F90:150)`, `(biogeochem/EDLoggingMortalityMod.F90:462-475)`

## Harvest Application in the Patch Dynamics Loop

Harvest rates calculated per cohort contribute to the patch-level disturbance rate via the `disturbance_rates` loop. Cohort logging fractions (`lmort_direct`, `lmort_collateral`, `lmort_infra`) are weighted by crown area to form the logging contribution to the patch's disturbance rate. For patches with non-closed canopies, an additional interstitial-area term is added so that inter-crown ground area is also transferred to the new patch (this is where the `l_degrad` fraction is accounted for).

If the sum of all disturbance types would exceed 100% of patch area, FATES proportionally rescales them. The final disturbance rate drives `spawn_patches`, which creates the secondary patch that receives disturbed biomass.

## Litter and Product Fluxes

When logging disturbance spawns a new patch, `logging_litter_fluxes` partitions biomass from the donor to the new patch across litter, CWD, and wood product pools.

### Biomass Partitioning

- **Leaves, fine roots, storage, reproductive pools** are sent to fine-litter pools (`leaf_fines`, `root_fines`, etc.) and distributed between donor and new patches controlled by `harvest_litter_localization` (default 0.0 = uniform per-area split; 1.0 = all into new patch).
- **Sapwood + structural wood** is split into above-ground and below-ground fractions using `allom_agb_frac`, then further split across CWD size classes using `SF_val_CWD_frac` adjusted for cohort DBH via `adjust_SF_CWD_frac`. Below-ground CWD is distributed across soil layers using the cohort root profile.
- **Above-ground boles from directly logged trees** are additionally partially exported as wood product.

### Wood Product Export (per-PFT, harvest vs. land-use-change split)

For directly logged cohorts, a fraction `logging_export_frac` of the above-ground bole carbon is exported and accumulated into the per-PFT `site_mass%wood_product_harvest(maxpft)` array (for mass balance) and `currentSite%resources_management%trunk_product_site` (for diagnostics). The remainder `(1 - logging_export_frac)` enters the largest coarse-woody-debris size class on-site. Wood product associated with land-use-change disturbance (forest converted to a new land-use label, not a logging harvest event) is accumulated into the parallel `wood_product_landusechange(maxpft)` array. This split is preserved in mass balance (see `flux_out` formula in [Mass Balance Checking](../output/mass_balance.md)) and exposed in the history variables `FATES_HARVEST_WOODPROD_C_FLUX` and `FATES_LUCHANGE_WOODPROD_C_FLUX`.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:773-1182)`, `(main/EDTypesMod.F90:297-299)`

## Harvest Debt

In carbon-based mode the host may request more biomass than is currently harvestable. `get_harvest_debt` accumulates the shortfall per LUH2 category into `currentSite%resources_management%harvest_debt` (and `harvest_debt_sec` for secondary-specific tracking). The `harvest_tag` set earlier by `get_harvest_rate_carbon` gates debt attribution:

| `harvest_tag` value | Symbolic name | Meaning |
|---|---|---|
| `0` | `fates_no_harvest_debt` | Sufficient harvestable carbon; debt not accumulated |
| `1` | `fates_insufficient_for_harvest_debt` | Insufficient carbon; shortfall added to harvest debt |
| `2` | `fates_bypass_harvest_debt` | Not applicable (area-based mode, or category does not match this cohort) |

Sources: `(biogeochem/EDLoggingMortalityMod.F90:632-769, 1239-1306)`

## Integration with the Daily Dynamics Loop

Within `ed_ecosystem_dynamics`, `IsItLoggingTime` is called first (line 179) to set the `logging_time` flag and reset event accumulators. Cohort-level logging fractions are then set inside `disturbance_rates` (called at line 229), which calls `LoggingMortality_frac` per cohort. The disturbance loop aggregates per-patch disturbance rates and, in `spawn_patches`, creates new secondary patches while `logging_litter_fluxes` moves biomass. Mass balance checks at call indices 0–6 and `final_check_id = -1` bracket these operations (see [Mass Balance Checking](../output/mass_balance.md)).

Sources: `(main/EDMainMod.F90:179, 201, 229-329)`, `(biogeochem/EDLoggingMortalityMod.F90:1-1306)`

## Key Data Structures

### Site-level resource management

`ed_resources_management_type` (in `EDTypesMod.F90`) tracks site-scale logging diagnostics including `trunk_product_site`, `harvest_debt`, `harvest_debt_sec`, `delta_litter_stock`, `delta_biomass_stock`, and `delta_individual`.

### Site-level mass balance, per-PFT wood product

`site_massbal_type` carries the wood-product fluxes split into `wood_product_harvest(maxpft)` and `wood_product_landusechange(maxpft)`, the burn flux as `burn_flux_to_atm(n_dist_types)`, and a herbivory loss `herbivory_flux_out` (see [Mass Balance Checking](../output/mass_balance.md) for the full field list).

### Cohort-level logging fractions

Each `fates_cohort_type` carries the per-cohort fractions set by `LoggingMortality_frac`: `lmort_direct`, `lmort_collateral`, `lmort_infra`, and `l_degrad`. These feed into `Mortality_Derivative` (in `EDMortalityFunctionsMod.F90`) and into the disturbance loop.

Sources: `(main/EDTypesMod.F90:263-318)`

## Parameter Reference

Parameters declared in `EDParamsMod.F90` (read from the FATES parameter file; Fortran defaults are `nan`, so values below come from the parameter file in use):

| Parameter | Purpose |
|---|---|
| `logging_event_code` | Timing of logging events (see table above) |
| `logging_dbhmin` | Minimum DBH for direct harvest |
| `logging_dbhmax` | Maximum DBH for direct harvest (disabled if `>= fates_check_param_set`) |
| `logging_dbhmax_infra` | DBH below which infrastructure mortality applies |
| `logging_direct_frac` | Direct-harvest fraction per event |
| `logging_collateral_frac` | Collateral-damage fraction per event |
| `logging_coll_under_frac` | Understory collateral fraction (applied in `logging_litter_fluxes`) |
| `logging_mechanical_frac` | Infrastructure mortality fraction |
| `logging_export_frac` | Fraction of directly harvested bole exported as wood product |

The secondary land age threshold `secondary_age_threshold = 94` years is a Fortran `parameter` in `FatesConstantsMod.F90:150` and is not exposed through the parameter file.
