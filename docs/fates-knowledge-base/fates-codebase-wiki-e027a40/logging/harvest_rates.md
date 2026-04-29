---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Harvest Rate Calculations

**Relevant source files:**
- `biogeochem/EDLoggingMortalityMod.F90` (1308 lines)
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

Mode selection is gated by three host flags in this order: `hlm_use_logging` (the new top-level on/off, see [Logging and Land Use](index.md)), `hlm_use_lu_harvest`, and `hlm_harvest_units`. If `hlm_use_logging .eq. ifalse`, no harvest fires regardless of the other two. When logging is enabled and an event is otherwise scheduled:

```
if (hlm_use_lu_harvest == ifalse) then
   harvest_rate = 1.0   ! standalone FATES mode; harvest the entire cohort area
else if (hlm_use_lu_harvest == itrue .and. hlm_harvest_units == hlm_harvest_area_fraction) then
   call get_harvest_rate_area(...)
else if (hlm_use_lu_harvest == itrue .and. hlm_harvest_units == hlm_harvest_carbon) then
   call get_harvest_rate_carbon(...)
end if
```

Sources: `(biogeochem/EDLoggingMortalityMod.F90:288-344)`

## LUH2 Harvest Categories

The host supplies harvest rates across five LUH2 land-use categories. These map to FATES patches via the `land_use_label` and patch age. **FATES applies `secondary_age_threshold = 94` years** (declared as a Fortran `parameter` in `FatesConstantsMod.F90:150`, based on Hurtt et al. (2011) average global secondary-land age). The threshold is not user-tunable via the parameter file.

The two driver naming conventions are accepted by `get_harvest_rate_area`. The classic CLM/ELM surface-file column is the first set; the direct-LUH2 driver column is the second:

| Surface-file name | LUH2 direct name | Description | Target patch label | Age criterion |
|---|---|---|---|---|
| `HARVEST_VH1` | `primf_harv` | Primary forest harvest | `primaryland` | n/a |
| `HARVEST_VH2` | `primn_harv` | Primary non-forest harvest | `primaryland` | n/a |
| `HARVEST_SH1` | `secmf_harv` | Secondary mature forest harvest | `secondaryland` | `age_since_anthro_disturbance >= 94 yr` |
| `HARVEST_SH2` | `secyf_harv` | Secondary young forest harvest | `secondaryland` | `age_since_anthro_disturbance < 94 yr` |
| `HARVEST_SH3` | `secnf_harv` | Secondary non-forest harvest | `secondaryland` | treated as young (`< 94 yr`) |

Sources: `(biogeochem/EDLoggingMortalityMod.F90:454-477)`, `(main/FatesConstantsMod.F90:150)`

## Area-Based Harvest (`get_harvest_rate_area`)

In area-based mode, the HLM supplies annual harvest rates per LUH2 category. `get_harvest_rate_area` selects the rate(s) matching the patch's `land_use_label` (and age for SH1/SH2), and normalizes by the site primary or secondary fraction so that a gridcell-scale target becomes a patch-scale rate.

Conceptual normalization (with `frac_not_bareground = sum(state_vector(:))`):

```
primary patches:   harvest_rate = sum(VH1, VH2) / max(frac_site_primary / frac_not_bareground, fates_tiny)
secondary patches: harvest_rate = sum(SH1 or SH2, SH3) /
                                  max((frac_site_secondary / frac_not_bareground) * young_or_mature_fraction, fates_tiny)
```

(The denominator is `frac_not_bareground` because harvest rates are reported per non-bare-ground area, not per gridcell.) Each `harvest_rate` is then capped at 1.0.

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

When in area-based mode, `harvest_tag(:) = fates_bypass_harvest_debt` (value `2`, not applicable) for all categories, because debt tracking only makes sense in carbon-based mode.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:426-526)`

## Carbon-Based Harvest

### Harvestable Carbon (`get_harvestable_carbon`)

Called at the site level before the cohort loop, `get_harvestable_carbon` sums merchantable bole carbon available for harvest across all patches and all LUH2 categories. Harvestable cohort carbon is computed as:

```
harvestable_cohort_c = (sapw_m + struct_m) * allom_agb_frac * SF_val_CWD_frac(ncwd) * n
```

where `sapw_m` and `struct_m` are the cohort's sapwood and structural carbon per plant, `allom_agb_frac` is the above-ground fraction, `SF_val_CWD_frac(ncwd)` restricts to the largest CWD size class (merchantable wood), and `n` is plant density. Cohorts that fail the DBH size criteria for direct harvest contribute zero.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:531-628)`

### Area Rate Conversion (`get_harvest_rate_carbon`)

`get_harvest_rate_carbon` converts the carbon target to an area-based `harvest_rate` by dividing the target by the harvestable carbon for the relevant LUH2 category. It also sets per-category `harvest_tag` values:

| `harvest_tag` value | Symbolic name | Meaning |
|---|---|---|
| `0` | `fates_no_harvest_debt` | Sufficient carbon; target fully met |
| `1` | `fates_insufficient_for_harvest_debt` | Insufficient carbon; shortfall accumulated into harvest debt (see below) |
| `2` | `fates_bypass_harvest_debt` | Category does not apply to this cohort (e.g., VH categories on a secondary patch) |

Sources: `(biogeochem/EDLoggingMortalityMod.F90:632-769)`

## Harvest Debt (`get_harvest_debt`)

When a carbon-based request cannot be fully satisfied, `get_harvest_debt` records the shortfall into `currentSite%resources_management%harvest_debt` (total across categories) and `harvest_debt_sec` (secondary-specific). This allows the debt to be tracked across timesteps and, in principle, paid down in future events. The diagnostics `FATES_HARVEST_DEBT` and `FATES_HARVEST_DEBT_SEC` (units `kg C`) report these accumulators on the history file.

Sources: `(biogeochem/EDLoggingMortalityMod.F90:1239-1306)`, `(biogeochem/EDPatchDynamicsMod.F90)`

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

Sources: `(biogeochem/EDLoggingMortalityMod.F90:355-419)`, `(biogeochem/EDPatchDynamicsMod.F90)`

## Non-Canopy Area Adjustment

Because logging disturbs an area larger than the crown footprint alone, `disturbance_rates` adds an interstitial-area contribution in patches whose canopy is not closed. This ensures that the area transferred to a newly spawned secondary patch reflects the harvested ground area, not just the crown projection.

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

Sources: `(main/FatesConstantsMod.F90:150)`
