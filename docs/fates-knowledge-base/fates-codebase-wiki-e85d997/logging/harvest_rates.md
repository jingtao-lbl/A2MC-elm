# Harvest Rate Calculations

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `biogeochem/EDLoggingMortalityMod.F90`
- `biogeochem/EDPatchDynamicsMod.F90`
- `main/EDMainMod.F90`
- `main/EDParamsMod.F90`
- `main/FatesConstantsMod.F90`

## Purpose and Scope

This page documents how FATES converts external land-use change inputs (from the host land model) or FATES-internal parameters into per-cohort harvest rates used by `LoggingMortality_frac`. Two modes are supported: area-based, where the host supplies fractions of vegetated area to be harvested, and carbon-based, where the host supplies carbon mass targets that FATES must convert to an area rate.

Related topics:

- [Logging and Land Use](index.md) — overall logging workflow
- [Logging Mortality](mortality.md) — cohort-level mortality application
- [Mass Balance Checking](../output/mass_balance.md) — conservation verification around harvest events

## Mode Selection

Mode selection is controlled by two host flags: `hlm_use_lu_harvest` and `hlm_harvest_units`.

```
if (hlm_use_lu_harvest == ifalse) then
   harvest_rate = 1.0   ! standalone FATES mode; harvest the entire cohort area
else if (hlm_use_lu_harvest == itrue .and. hlm_harvest_units == hlm_harvest_area_fraction) then
   call get_harvest_rate_area(...)
else if (hlm_use_lu_harvest == itrue .and. hlm_harvest_units == hlm_harvest_carbon) then
   call get_harvest_rate_carbon(...)
end if
```

Sources: `(biogeochem/EDLoggingMortalityMod.F90:243-291)`

## LUH2 Harvest Categories

The host supplies harvest rates across five LUH2 land-use categories. These map to FATES patches via the `anthro_disturbance_label` and patch age. **FATES applies `secondary_age_threshold = 94` years** (declared as a Fortran `parameter` in `FatesConstantsMod.F90:126`, based on Hurtt et al. (2011) average global secondary-land age). The threshold is not user-tunable via the parameter file.

| Category | Description | Target patch label | Age criterion |
|---|---|---|---|
| `HARVEST_VH1` | Primary forest harvest | `primaryforest` | n/a |
| `HARVEST_VH2` | Primary non-forest harvest | `primaryforest` | n/a |
| `HARVEST_SH1` | Secondary mature forest harvest | `secondaryforest` | `age_since_anthro_disturbance >= 94 yr` |
| `HARVEST_SH2` | Secondary young forest harvest | `secondaryforest` | `age_since_anthro_disturbance < 94 yr` |
| `HARVEST_SH3` | Secondary non-forest harvest | `secondaryforest` | treated as young (`< 94 yr`) |

Sources: `(biogeochem/EDLoggingMortalityMod.F90:258-266)`, `(main/FatesConstantsMod.F90:126-128)`

## Area-Based Harvest (`get_harvest_rate_area`)

In area-based mode, the HLM supplies annual harvest rates per LUH2 category. `get_harvest_rate_area` selects the rate(s) matching the patch's `anthro_disturbance_label` (and age for SH1/SH2), and normalizes by the site primary or secondary fraction so that a gridcell-scale target becomes a patch-scale rate.

Conceptual normalization:

```
primary patches:   harvest_rate = sum(VH1, VH2) / max(frac_site_primary,    nearzero)
secondary patches: harvest_rate = sum(SH1 or SH2, SH3) / max(1 - frac_site_primary, nearzero)
```

(If only 20% of a site is primary forest, a 10% gridcell-scale request on primary land becomes a 50% patch-scale rate.)

### Temporal Scaling

Annual LUH2 rates must be scaled to the dynamics step based on `logging_event_code`:

| Event code | Frequency | Scaling applied to annual rate |
|---|---|---|
| `1` | Off | `harvest_rate = 0` |
| `2` | First day only | Applied once, no scaling |
| `3` | Every day | Divide by `hlm_days_per_year` |
| `4` | First day of each month | Divide by `months_per_year` |
| `-1` to `-365` | Annual, specific DOY | Applied once per year, no scaling |
| `> 10000` | One-time event (`YYYYMMDD`) | Applied once, no scaling |

When in area-based mode, `harvest_tag(:) = 2` (not applicable) for all categories, because debt tracking only makes sense in carbon-based mode.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:351-432)`

## Carbon-Based Harvest

### Harvestable Carbon (`get_harvestable_carbon`)

Called at the site level before the cohort loop, `get_harvestable_carbon` sums merchantable bole carbon available for harvest across all patches and all LUH2 categories. Harvestable cohort carbon is computed as:

```
harvestable_cohort_c = (sapw_m + struct_m) * allom_agb_frac * SF_val_CWD_frac(ncwd) * n
```

where `sapw_m` and `struct_m` are the cohort's sapwood and structural carbon per plant, `allom_agb_frac` is the above-ground fraction, `SF_val_CWD_frac(ncwd)` restricts to the largest CWD size class (merchantable wood), and `n` is plant density. Cohorts that fail the DBH size criteria for direct harvest contribute zero.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:437-536)`

### Area Rate Conversion (`get_harvest_rate_carbon`)

`get_harvest_rate_carbon` converts the carbon target to an area-based `harvest_rate` by dividing the target by the harvestable carbon for the relevant LUH2 category. It also sets per-category `harvest_tag` values:

| `harvest_tag` | Meaning |
|---|---|
| `0` | Sufficient carbon; target fully met |
| `1` | Insufficient carbon; shortfall accumulated into harvest debt (see below) |
| `2` | Category does not apply to this cohort (e.g., VH categories on a secondary patch) |

Sources: `(biogeochem/EDLoggingMortalityMod.F90:540-680)`

## Harvest Debt (`get_harvest_debt`)

When a carbon-based request cannot be fully satisfied, `get_harvest_debt` records the shortfall into `currentSite%resources_management%harvest_debt` (total across categories) and `harvest_debt_sec` (secondary-specific). This allows the debt to be tracked across timesteps and, in principle, paid down in future events.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:1137-1204)`, `(biogeochem/EDPatchDynamicsMod.F90)`

## From Harvest Rate to Disturbance

The `harvest_rate` returned by the mode-specific functions feeds into `LoggingMortality_frac`, which sets the per-cohort fractions `lmort_direct`, `lmort_collateral`, `lmort_infra`, and `l_degrad`. These fractions are then consumed by `disturbance_rates` (in `EDPatchDynamicsMod.F90`) to compute patch-level disturbance rates, and by `Mortality_Derivative` (in `EDMortalityFunctionsMod.F90`) for understory treatment.

For canopy-layer cohorts:

```
lmort_direct      = harvest_rate * logging_direct_frac     (if harvestable and woody)
lmort_collateral  = harvest_rate * logging_collateral_frac (if woody)
lmort_infra       = harvest_rate * logging_mechanical_frac (if dbh < logging_dbhmax_infra)
l_degrad          = harvest_rate - (lmort_direct + lmort_infra + lmort_collateral)
```

For understory cohorts, only `lmort_infra` (for sufficiently small trees) and, for non-woody plants, infrastructure mortality are set by this routine; other understory effects flow through `logging_litter_fluxes` during patch spawning.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:295-344)`, `(biogeochem/EDPatchDynamicsMod.F90:204-538)`, `(biogeochem/EDMortalityFunctionsMod.F90:234-323)`

## Non-Canopy Area Adjustment

Because logging disturbs an area larger than the crown footprint alone, `disturbance_rates` adds an interstitial-area contribution in patches whose canopy is not closed. This ensures that the area transferred to a newly spawned secondary patch reflects the harvested ground area, not just the crown projection.

Sources: `(biogeochem/EDPatchDynamicsMod.F90:204-538)`

## Parameters Controlling Harvest Rates

Parameters declared in `main/EDParamsMod.F90` (initial Fortran values are `nan`; real defaults come from the FATES parameter file):

| Parameter | Role |
|---|---|
| `logging_dbhmin` | Minimum DBH for direct harvest (cm) |
| `logging_dbhmax` | Maximum DBH for direct harvest (cm); effectively disabled if `>= fates_check_param_set` |
| `logging_direct_frac` | Fraction of the harvest rate applied as direct mortality |
| `logging_collateral_frac` | Fraction applied as collateral damage |
| `logging_mechanical_frac` | Fraction applied as infrastructure mortality |
| `logging_dbhmax_infra` | DBH below which infrastructure mortality applies |
| `logging_export_frac` | Fraction of directly harvested bole exported as wood product |
| `logging_event_code` | Event-timing code (see timing table) |

Constant in `main/FatesConstantsMod.F90`:

| Constant | Value | Role |
|---|---|---|
| `secondary_age_threshold` | `94.0` years | Boundary between `HARVEST_SH1` (mature) and `HARVEST_SH2`/`SH3` (young) |

Sources: `(main/EDParamsMod.F90:268-378)`, `(main/FatesConstantsMod.F90:126-128)`
