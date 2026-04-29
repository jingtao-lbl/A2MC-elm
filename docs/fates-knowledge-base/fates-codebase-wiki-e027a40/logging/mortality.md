---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Logging Mortality

**Relevant source files:**
- `biogeochem/EDLoggingMortalityMod.F90` (1308 lines)
- `biogeochem/EDMortalityFunctionsMod.F90`
- `biogeochem/EDCohortDynamicsMod.F90`
- `main/EDMainMod.F90`
- `main/EDParamsMod.F90`

## Purpose and Scope

This page documents the cohort-level application of logging mortality in FATES. It describes the four logging fractions set on each cohort by `LoggingMortality_frac`, how those fractions are applied to canopy versus understory cohorts, and how logging-driven biomass is routed to litter, CWD, and wood-product pools during patch spawning.

For the harvest-rate conversion step that precedes these fractions, see [Harvest Rate Calculations](harvest_rates.md). For the overall logging workflow, see [Logging and Land Use](index.md).

## Logging Fractions

The subroutine `LoggingMortality_frac` is called per cohort from inside `disturbance_rates`. Once `logging_time` has been set to `.true.` (or a transition-from-potential-vegetation event is in progress) it sets four fields on the cohort:

| Fraction | Type | Cohorts affected | Formula |
|---|---|---|---|
| `lmort_direct` | Killing | Canopy-layer woody cohorts with `dbh >= logging_dbhmin`, optionally `dbh < logging_dbhmax`, and `cur_harvest_tag .ne. fates_insufficient_for_harvest_debt` | `harvest_rate * logging_direct_frac` |
| `lmort_collateral` | Killing | Canopy-layer woody cohorts | `harvest_rate * logging_collateral_frac` |
| `lmort_infra` | Killing | All plants with `dbh < logging_dbhmax_infra` (canopy and understory) | `harvest_rate * logging_mechanical_frac` |
| `l_degrad` | Non-killing transfer | Canopy layer only | `harvest_rate - (lmort_direct + lmort_infra + lmort_collateral)` |

Direct, collateral, and infrastructure fractions sum to the portion of the canopy-area harvest rate that actually kills trees. `l_degrad` is the residual — the fraction of disturbed area whose trees survive but are moved to a newly spawned secondary patch during `spawn_patches`. Understory cohorts have `l_degrad = 0` by construction.

Non-woody plants can only be affected through `lmort_infra`; they have `lmort_direct = lmort_collateral = 0`.

The same routine also handles the special "transition from potential vegetation to land-use mode on day one" path, in which the targeted area transfer for the historical land-use replay can produce `lmort_direct = harvest_rate` directly on woody cohorts and `l_degrad = harvest_rate` on canopy-layer non-woody cohorts in primary patches (`EDLoggingMortalityMod.F90:399-419`).

Sources: `(biogeochem/EDLoggingMortalityMod.F90:208-421)`

## Event Gating

`LoggingMortality_frac` is reached via the following gating sequence:

1. `IsItLoggingTime` returns immediately with `logging_time = .false.` if `hlm_use_logging .eq. ifalse` (line 138). This is the new top-level switch at e027a40.
2. Otherwise `logging_time` is set based on `logging_event_code` (see [Logging and Land Use](index.md) for the full event-code table).
3. Inside `LoggingMortality_frac`, harvest rates are computed only when `logging_time .eq. .true.` (or during the historical-land-use bootstrap on the first day).

Site-level diagnostic accumulators (`delta_litter_stock`, `delta_biomass_stock`, `delta_individual`) are reset inside `IsItLoggingTime` whenever an event fires, so these variables report per-event changes rather than cumulative totals.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:116-203)`, `(main/EDMainMod.F90:179)`

## Canopy vs. Understory Application

Canopy and understory logging mortality take different paths through the model, because only canopy mortality creates new patches.

**Canopy (`canopy_layer == 1`):** `lmort_direct + lmort_collateral + lmort_infra` is combined with other disturbance sources in `disturbance_rates`, weighted by crown area, to produce the patch-level logging contribution to the disturbance rate. This rate drives `spawn_patches`, which creates a newly disturbed secondary patch and transfers donor biomass through `logging_litter_fluxes`. The survivors on the `l_degrad` fraction are also moved to the new patch, without mortality.

**Understory:** Because understory disturbance does not create new patches, the understory logging fractions (currently just `lmort_infra` for small plants) are applied directly as a daily mortality rate via `Mortality_Derivative` in `EDMortalityFunctionsMod.F90`. The relevant path in `Mortality_Derivative` converts the annual fraction to a daily rate and adds it to the cohort's total `dndt` alongside background, hydraulic, carbon-starvation, senescence, and fire mortality.

## Litter, CWD, and Wood Products

When a new patch is spawned because of logging, `logging_litter_fluxes` (called from `spawn_patches`) partitions the biomass of killed cohorts:

- **Fine pools (leaves, fine roots, storage, reproductive tissue):** Moved into leaf and root fine litter, distributed between donor and new patches by `harvest_litter_localization` (default `0.0` for uniform per-area split).
- **Stem wood (sapwood + structural):** Split into above- and below-ground fractions by `allom_agb_frac`, then distributed across CWD size classes via `SF_val_CWD_frac` adjusted for the cohort's DBH by `adjust_SF_CWD_frac`. Below-ground CWD is further distributed across soil layers by the cohort root profile.
- **Above-ground bole from directly logged cohorts only:** A fraction `logging_export_frac` is exported to `site_mass%wood_product_harvest(pft)` (per-PFT, for mass-balance tracking) and `currentSite%resources_management%trunk_product_site` (for diagnostics). The remainder `(1 - logging_export_frac)` enters the largest CWD size class in the new patch. Wood product from land-use-change disturbance is bookkept separately into `wood_product_landusechange(pft)`.

Collateral and infrastructure victims do not contribute to wood product — only direct harvests are exported.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:773-1182)`, `(main/EDTypesMod.F90:297-299)`

## Integration with Other Mortality

The logging fractions feed into `Mortality_Derivative`, which composes the daily `dndt` from:

- background mortality
- hydraulic failure
- carbon starvation (with a continuous component, see `FATES_MORT_CSTARV_CONT_CFLUX_PF`)
- freezing
- senescence
- fire (split at e027a40 into wildfire and prescribed-fire variants — see [Model Output and Diagnostics](../output/index.md))
- logging (understory contribution only; canopy logging goes through the disturbance path)
- cambial burn / crown scorch / impact (for damaged cohorts)

The `fates_mortality_disturbance_fraction` parameter (from the FATES parameter file, typically `1.0`) sets what fraction of canopy mortality feeds disturbance rather than remaining as direct number-density loss. This parameter is not logging-specific — it applies to all canopy mortality sources.

## Parameter Summary

The following parameters are read from the FATES parameter file. Initial Fortran values in `EDParamsMod.F90` are `nan`, so users must consult the parameter file in use for actual values. Typical CMIP-era defaults (illustrative, not code-level):

| Parameter | Typical default (parameter file) | Units | Role |
|---|---|---|---|
| `logging_event_code` | varies | — | Timing of logging events |
| `logging_dbhmin` | 50.0 | cm | Minimum DBH for direct harvest |
| `logging_dbhmax` | unset | cm | Maximum DBH for direct harvest (optional) |
| `logging_dbhmax_infra` | 35.0 | cm | DBH threshold below which `lmort_infra` is applied |
| `logging_direct_frac` | 0.15 | fraction | Direct mortality fraction (`× harvest_rate`) |
| `logging_collateral_frac` | 0.05 | fraction | Canopy collateral fraction (`× harvest_rate`) |
| `logging_mechanical_frac` | 0.05 | fraction | Infrastructure mortality fraction (`× harvest_rate`) |
| `logging_export_frac` | 0.8 | fraction | Fraction of directly harvested bole exported off-site |
| `logging_coll_under_frac` | — | fraction | Understory collateral fraction (used in `logging_litter_fluxes`) |
| `fates_mortality_disturbance_fraction` | 1.0 | fraction | Fraction of canopy mortality that spawns disturbance |

Defaults above are illustrative parameter-file values from CMIP-era runs. The actual code-level initializers in `EDParamsMod` are `nan`.

## Code Entity Reference

Primary subroutines in `biogeochem/EDLoggingMortalityMod.F90` at e027a40:

| Subroutine | Lines | Role |
|---|---|---|
| `IsItLoggingTime` | 116-203 | Test whether current dynamics step is a logging event; gates on `hlm_use_logging` first |
| `LoggingMortality_frac` | 208-421 | Set `lmort_direct`, `lmort_collateral`, `lmort_infra`, `l_degrad` on a cohort |
| `get_harvest_rate_area` | 426-526 | Area-based conversion from HLM harvest rates to per-patch `harvest_rate` |
| `get_harvestable_carbon` | 531-628 | Sum merchantable bole carbon per LUH2 category |
| `get_harvest_rate_carbon` | 632-769 | Carbon-based conversion to area rate; set `harvest_tag` |
| `logging_litter_fluxes` | 773-1182 | Move biomass to litter/CWD/wood product during patch spawn |
| `UpdateHarvestC` | 1187-1237 | Update cohort harvested-carbon bookkeeping |
| `get_harvest_debt` | 1239-1306 | Accumulate shortfall when carbon target cannot be met |

Integration points:

- `Mortality_Derivative` in `biogeochem/EDMortalityFunctionsMod.F90` — understory logging application
- `ed_ecosystem_dynamics` in `main/EDMainMod.F90` (line 179 calls `IsItLoggingTime`; line 229 calls `disturbance_rates`)
- `disturbance_rates` in `biogeochem/EDPatchDynamicsMod.F90` — canopy disturbance contribution
- `spawn_patches` in `biogeochem/EDPatchDynamicsMod.F90` — invokes `logging_litter_fluxes`

Sources: `(biogeochem/EDLoggingMortalityMod.F90:1-1308)`
