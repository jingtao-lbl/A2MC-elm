# Logging and Land Use

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `biogeochem/EDLoggingMortalityMod.F90`
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

The `IsItLoggingTime` subroutine determines whether logging should be enacted at the current dynamics step by comparing model time to the scalar parameter `logging_event_code`. It sets the module-level flag `logging_time`, which gates all downstream logging mortality calculations.

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

Sources: `(biogeochem/EDLoggingMortalityMod.F90:106-193)`, `(main/EDMainMod.F90:196-255)`

## Logging Mortality Types

FATES tracks four cohort-level logging fractions. The first three are killing fractions; the fourth is a degradation fraction that transfers surviving trees to a secondary patch without killing them.

### Direct Logging Mortality (`lmort_direct`)

Direct mortality applies to woody cohorts in the canopy layer (`canopy_layer .eq. 1`) whose DBH satisfies `dbh >= logging_dbhmin` and, if `logging_dbhmax` is set (i.e., `< fates_check_param_set`), `dbh < logging_dbhmax`. For harvestable cohorts with `harvest_tag == 0`:

```
lmort_direct = harvest_rate * logging_direct_frac
```

For non-harvestable cohorts or unsuccessful harvests (`harvest_tag /= 0`), `lmort_direct = 0`. Non-woody plants are never subject to direct logging.

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

Sources: `(biogeochem/EDLoggingMortalityMod.F90:198-346)`

## Harvest Modes: Area-Based vs. Carbon-Based

Two harvest modes are selected from host boundary conditions. If `hlm_use_lu_harvest == ifalse`, FATES falls back to a standalone mode where `harvest_rate = 1.0` (the full cohort area) is used at each logging event.

### Area-Based Harvest

When `hlm_use_lu_harvest == itrue .and. hlm_harvest_units == hlm_harvest_area_fraction`, the host supplies harvest rates as gridcell-level fractions split across five LUH2 categories: `HARVEST_VH1` (primary forest), `HARVEST_VH2` (primary non-forest), `HARVEST_SH1` (secondary mature forest), `HARVEST_SH2` (secondary young forest), and `HARVEST_SH3` (secondary non-forest). `get_harvest_rate_area` maps these to a per-patch `harvest_rate` by selecting categories that match the patch's `anthro_disturbance_label` and secondary age, and by normalizing by the site primary/secondary fractions. In this mode `harvest_tag(:) = 2` (not applicable).

### Carbon-Based Harvest

When `hlm_use_lu_harvest == itrue .and. hlm_harvest_units == hlm_harvest_carbon`, harvest targets are specified as carbon mass. Before the cohort loop, `get_harvestable_carbon` sums merchantable bole carbon across patches per LUH2 category. `get_harvest_rate_carbon` then converts the target to an area-based `harvest_rate` and assigns each category a `harvest_tag` indicating success (`0`), insufficient carbon (`1`), or not applicable (`2`).

Sources: `(biogeochem/EDLoggingMortalityMod.F90:243-291, 351-680)`

## Primary vs. Secondary Patches

Each patch carries an `anthro_disturbance_label` (`primaryforest` or `secondaryforest`) and, if anthropogenically disturbed, an `age_since_anthro_disturbance`. The patch spawning logic in `EDPatchDynamicsMod` uses these fields to decide whether new patches inherit the primary label:

- Donor patch is **primary** and disturbance type is **not logging** (`i_disturbance_type .ne. dtype_ilog`): new patch is **primary**.
- Donor patch is **primary** and disturbance type **is logging**: new patch is **secondary** (primary→secondary transition).
- Donor patch is **secondary** (any disturbance type): new patch is **secondary**.

Secondary patches are further classified by age, using the parameter `secondary_age_threshold` (from `FatesConstantsMod`):

- **Secondary young**: `age_since_anthro_disturbance < secondary_age_threshold`
- **Secondary mature**: `age_since_anthro_disturbance >= secondary_age_threshold`

The threshold value is **94 years**, based on the average age of global 1900s-era secondary land from Hurtt et al. (2011). This value is documented directly in the source (`secondary_age_threshold = 94._fates_r8`, see note below); it is not user-tunable via the FATES parameter file.

Sources: `(main/FatesConstantsMod.F90:126-128)`, `(biogeochem/EDPatchDynamicsMod.F90:497-538)`

## Harvest Application in the Patch Dynamics Loop

Harvest rates calculated per cohort contribute to the patch-level disturbance rate via the `disturbance_rates` loop. Cohort logging fractions (`lmort_direct`, `lmort_collateral`, `lmort_infra`) are weighted by crown area to form the logging contribution to the patch's disturbance rate. For patches with non-closed canopies, an additional interstitial-area term is added so that inter-crown ground area is also transferred to the new patch (this is where the `l_degrad` fraction is accounted for).

If the sum of all disturbance types would exceed 100% of patch area, FATES proportionally rescales them. The final disturbance rate drives `spawn_patches`, which creates the secondary patch that receives disturbed biomass.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:204-538)`

## Litter and Product Fluxes

When logging disturbance spawns a new patch, `logging_litter_fluxes` partitions biomass from the donor to the new patch across litter, CWD, and wood product pools.

### Biomass Partitioning

- **Leaves, fine roots, storage, reproductive pools** are sent to fine-litter pools (`leaf_fines`, `root_fines`, etc.) and distributed between donor and new patches controlled by `harvest_litter_localization` (default 0.0 = uniform per-area split; 1.0 = all into new patch).
- **Sapwood + structural wood** is split into above-ground and below-ground fractions using `allom_agb_frac`, then further split across CWD size classes using `SF_val_CWD_frac` adjusted for cohort DBH via `adjust_SF_CWD_frac`. Below-ground CWD is distributed across soil layers using the cohort root profile.
- **Above-ground boles from directly logged trees** are additionally partially exported as wood product.

### Wood Product Export

For directly logged cohorts only, a fraction `logging_export_frac` of the above-ground bole carbon is exported and accumulated into `site_mass%wood_product` (for mass balance) and `currentSite%resources_management%trunk_product_site` (for diagnostics). The remainder `(1 - logging_export_frac)` enters the largest coarse-woody-debris size class on-site.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:684-1092)`

## Harvest Debt

In carbon-based mode the host may request more biomass than is currently harvestable. `get_harvest_debt` accumulates the shortfall per LUH2 category into `currentSite%resources_management%harvest_debt` (and `harvest_debt_sec` for secondary-specific tracking). The `harvest_tag` set earlier by `get_harvest_rate_carbon` gates debt attribution:

| `harvest_tag` | Meaning |
|---|---|
| `0` | Sufficient harvestable carbon; debt not accumulated |
| `1` | Insufficient carbon; shortfall added to harvest debt |
| `2` | Not applicable (area-based mode, or category does not match this cohort) |

Sources: `(biogeochem/EDLoggingMortalityMod.F90:540-680, 1137-1204)`

## Integration with the Daily Dynamics Loop

Within `ed_ecosystem_dynamics`, the logging pathway runs in this order each dynamics step: `IsItLoggingTime` is called first to set the `logging_time` flag and reset event accumulators, harvestable carbon is computed at the site level (if carbon-based), cohort-level logging fractions are set via `LoggingMortality_frac`, the disturbance loop aggregates per-patch disturbance rates, and `spawn_patches` creates new secondary patches while `logging_litter_fluxes` moves biomass. Mass balance checks at call indices 0–6 and `-1` bracket these operations (see [Mass Balance Checking](../output/mass_balance.md)).

Sources: `(main/EDMainMod.F90:141-317)`, `(biogeochem/EDLoggingMortalityMod.F90:1-1206)`

## Key Data Structures

### Site-level resource management

`ed_resources_management_type` (in `EDTypesMod.F90`) tracks site-scale logging diagnostics including `trunk_product_site`, `harvest_debt`, `harvest_debt_sec`, `delta_litter_stock`, `delta_biomass_stock`, and `delta_individual`.

### Cohort-level logging fractions

Each `fates_cohort_type` carries the per-cohort fractions set by `LoggingMortality_frac`: `lmort_direct`, `lmort_collateral`, `lmort_infra`, and `l_degrad`. These feed into `Mortality_Derivative` (in `EDMortalityFunctionsMod.F90`) and into the disturbance loop.

### Site- and patch-level disturbance tracking

`currentSite%disturbance_rates_primary_to_primary`, `disturbance_rates_primary_to_secondary`, and `disturbance_rates_secondary_to_secondary` are each sized to `N_DIST_TYPES` (treefall, fire, logging) and record the site-aggregated rates used for history output.

Sources: `(main/EDTypesMod.F90)`, `(biogeochem/EDPatchDynamicsMod.F90:470-538)`

## Parameter Reference

Parameters declared in `EDParamsMod.F90` (read from the FATES parameter file; Fortran defaults are `nan`, so values below are the typical parameter-file defaults for CMIP-style runs):

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

The secondary land age threshold `secondary_age_threshold = 94` years is a Fortran `parameter` in `FatesConstantsMod.F90` and is not exposed through the parameter file.

Sources: `(main/EDParamsMod.F90:268-378)`, `(main/FatesConstantsMod.F90:126-128)`
