---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Crops (CropMod, CropType, CropHarvestPoolsMod)

This document covers the ELM prognostic crop pathway. It is active only
when `use_crop = .true.` (`main/elm_varctl.F90:356`), which also sets
`crop_prog = .true.` inside `elm_varpar`. Crops are modeled as additional
PFTs (`nc3crop`, `nc3irrig`, `ncorn`, `nsoybean`, `nscereal`, `nwcereal`,
and their irrigated variants, and the perennial bioenergy PFTs
`nmiscanthus`, `nswitchgrass`, and their irrigated variants) inside the
normal CN subgrid. The crop-specific state and routines are kept in three
files; the phenology, harvest, and planting-date logic live inside
`PhenologyMod.F90`.

| File | Role |
|---|---|
| `biogeochem/CropType.F90` | `crop_type` object holding per-patch crop state, history registration, init/restart/update. |
| `biogeochem/CropMod.F90` | Two utility routines: reference-ET calculation and planting-month selection. |
| `biogeochem/CropHarvestPoolsMod.F90` | 1-year column-level harvest pool `prod1c/n/p` with first-order decay. |
| `biogeochem/PhenologyMod.F90` | `CropPhenology`, `PerennialCropPhenology`, `CropPlantDate`, `vernalization`, `CNCropHarvest`, `CNPerennialCropHarvest`, `CropPhenologyInit`. |

## `crop_type` — per-patch state

Defined in `biogeochem/CropType.F90:34`. Key fields
(`biogeochem/CropType.F90:37-70`):

- `croplive_patch (:)` — true while planted and not harvested.
- `cropplant_patch (:)` — true once planted at least once this year.
- `nyrs_crop_active_patch (:)` — years the crop has been active on this
  patch, used to gate the 20-year GDD running means in `PhenologyClimate`.
- `harvdate_patch (:)` — day of year of harvest this year (999 if not
  harvested yet).
- `fertnitro_patch (:)`, `fertphosp_patch (:)` — max N and P fertilizer
  to apply (kg/m²). Seeded from `fert_cft` / `fert_p_cft` in `InitCold`.
- `gddplant_patch (:)` — accumulated GDD since planting.
- `gddtsoi_patch (:)` — accumulated GDD from top soil-layer temperature
  (used as a soil-temperature criterion for planting).
- `crpyld_patch (:)` — crop yield (bu/acre).
- `dmyield_patch (:)` — dry matter yield (t/ha).
- `vf_patch (:)` — vernalization factor for cereals (0–1).
- `cphase_patch (:)` — growth phase index.
- `latbaset_patch (:)` — optional latitude-varying base temperature for
  GDD accumulation.
- `plantmonth_patch (:)`, `plantday_patch (:)`, `harvday_patch (:)` —
  scheduled planting month, planting day of year, harvest day of year.
- Monthly seasonality diagnostics: `xt_patch(:,1:12)`, `xp_patch(:,1:12)`
  (monthly T and P), their exponentially weighted moving averages
  `xt_bar_patch`, `xp_bar_patch`, prior-year values
  `prev_xt_bar_patch`, `prev_xp_bar_patch`, and the
  precipitation-to-reference-ET ratio `p2ETo_patch`, `p2ETo_bar_patch`,
  `prev_p2ETo_bar_patch`, `P2E_rm_patch` (4-month running sum), `ETo_patch`.
- `cvt_patch`, `cvp_patch` — coefficients of variation of monthly
  temperature and precipitation.

Module-level constants for the planting-month classifier
(`biogeochem/CropType.F90:27-29`): `tcvp = 0.4`, `tcvt = 0.01`,
`cst = 283` K.

Type-bound procedures (`biogeochem/CropType.F90:72-84`):
- `Init` → `InitAllocate`, and when `crop_prog = .true.`, `InitHistory`
  and `InitCold`. `InitHistory` registers 1D and 2D history fields for
  `FERTNITRO`, `FERTPHOSP`, `GDDPLANT`, `GDDTSOI`, `CRPYLD`, `DMYIELD`,
  `CVT`, `CVP`, `PLANTMONTH`, `PLANTDAY`, `HARVESTDAY`, and the
  monthly seasonality arrays (`XT`, `XP`, `XT_BAR`, `XP_bar`,
  `P2ETO`, `P2ETO_bar`, `P2E_rm`, `ETO`).
- `InitAccBuffer`, `InitAccVars`, `UpdateAccVars` — manage the accumulated
  fields needed for the 20-year GDD running means and the seasonality
  classifier (via `accumulMod`).
- `Restart` — read/write crop state for restarts.
- `CropIncrementYear` — year-boundary bookkeeping.
- `checkDates` (private, nopass) — sanity check on planting/harvest
  dates.

## `CropMod.F90` — reference ET and planting month

Two public subroutines (`biogeochem/CropMod.F90:18-19`):

### `calculate_eto(T, rn, g, p, rh, u, dt, eto)` (`biogeochem/CropMod.F90:28`)

Implements the FAO Penman-Monteith reference evapotranspiration
(`ETo`, mm/timestep):

```
ETo = (0.408*Δ*(Rn - G) + γ*(900/(T+273))*u*(es - ea)) / (Δ + γ*(1 + 0.34*u))
```

where `Δ` is the saturation vapor pressure slope, `γ` is the psychrometric
constant, `es` uses Tetens 1930, and the constants (`c1=0.408`, `c3=0.34`,
`c4=900`, `c5=237.3`, `esc1=0.6108`, `esc2=17.27`, `dc1=4098`,
`gc1=0.000665`) are the standard FAO-56 values. The result is fed into
`p2ETo_patch` each time step so the driver can maintain the
precipitation-to-ET ratio used by the planting-month classifier.

### `plant_month(p, cvt, cvp, temp, p2e, minplantjday, plantmonth)` (`biogeochem/CropMod.F90:93`)

Chooses the planting month based on seasonality of temperature and
precipitation:

- If `cvp > tcvp`:
  - `cvt >= tcvt`: both temperature and precipitation seasonality. If
    there is a cold season (`min(temp) < cst = 283 K`), plant as soon as
    average monthly temperature exceeds the PFT's `planttemp` and the
    month is past `minplantjday`; otherwise plant in the month that
    maximizes `maxloc(p2e)`.
  - `cvt < tcvt`: precipitation seasonality only — plant in the
    `maxloc(p2e)` month.
- `cvt > tcvt` only: temperature seasonality — plant as soon as the
  temperature criterion is satisfied.
- Neither seasonal: plant in month 1 (tropical default).

This function is called once per year from `CropPlantDate`
(`biogeochem/PhenologyMod.F90:2393`), which computes `cvt`, `cvp`, and
the 4-month-sum `P2E_rm`, and then passes them in.

## Crop phenology in `PhenologyMod.F90`

### `CropPhenologyInit` (`biogeochem/PhenologyMod.F90:2173`)

Called from `PhenologyInit` when `crop_prog` is true. Sets up the
vernalization constants `p1d`, `p1v`, `hti`, `tbase`, the
`minplantjday`, `maxplantjday` arrays by PFT and hemisphere, and the
hemisphere mapping `inhemi(:)`. The constants differ for winter vs
spring cereals, and the hemisphere determines whether the planting
window wraps around the year.

### `CropPhenology` (`biogeochem/PhenologyMod.F90:1394`)

Called once per day (`doalb` time step) for each prognostic-crop patch.
This is the AgroIBIS-style day-by-day phenology driver. The logical flow
inside the patch loop
(`biogeochem/PhenologyMod.F90:1394-1949`) is:

1. Determine the Julian day and compute the GDD increment relative to
   the PFT base temperature (`latbaset_patch` if requested, otherwise a
   constant from `pftvarcon`). The pre-planting GDD uses 2 m air
   temperature (`t_ref2m`) while `gddtsoi` uses top-2-layer soil
   temperature.
2. If not yet planted and the planting window is open, check that
   `a5tmin > minplanttemp(ivt)` (5-day running mean min temperature
   above PFT-specific minimum) and `t10 > planttemp(ivt)` (10-day
   running mean 2 m temperature above PFT-specific minimum). Require
   soil moisture `h2osoi_vol` between `minwet` and `maxwet` and no
   rainfall today (`minrain = 0.1`). If all criteria are met, set
   `croplive = .true.`, record `idop` and `plantday`, zero `gddplant`,
   `gddtsoi`, `vf`, and the running min/max T buffers.
3. If planted and live, call `vernalization(p, ...)` for winter cereals
   (cereal-specific) to update `vf`. The vernalization factor reduces
   the effective GDD requirement for winter wheat depending on accumulated
   cold hardening `hdidx` and the cumulative vernalization days `cumvd`
   (`biogeochem/PhenologyMod.F90:2251-2392`).
4. Update `gddplant` and `gddtsoi` each step. Check progression through
   phenological phases (`cphase`):
   - Leaf emergence at `hui > huileaf * gddmaturity` (see `lfemerg`).
   - Grain fill at `hui > huigrain * gddmaturity` (see `grnfill`).
   - Harvest when `hui > gddmaturity` or `nyrs_crop_active` exceeds
     `mxmat(ivt)` (maximum time-since-planting in days).
5. On harvest, set `offset_flag = 1` and `offset_counter = 1 * secspday`
   (the crop offset takes one day), which triggers `CNCropHarvest` later
   in the same driver.
6. Update `bglfr_leaf`, `bglfr_froot`, `bgtr` to zero during the active
   growing season — crop litterfall is produced by harvest, not by a
   background rate.
7. Apply fertilizer. `fertnitro` is distributed over `ndays_on = 21` days
   starting at emergence (`biogeochem/PhenologyMod.F90` — the constant
   `ndays_on` is scoped to the crop branch here and is distinct from the
   non-crop `PhenolParamsInst%ndays_on`).

### `PerennialCropPhenology` (`biogeochem/PhenologyMod.F90:1950`)

A variant for the perennial bioenergy crops (miscanthus, switchgrass) that
can be harvested but survive between years. Identical GDD framework, but
retains root and crown pools across harvest and resets only leaves and
stem.

### `CNCropHarvest` (`biogeochem/PhenologyMod.F90:2740`)

Runs during the offset period of a prognostic-crop patch and, on the last
step of the offset counter, computes harvest-to-product fluxes
(`biogeochem/PhenologyMod.F90:2812-2841`):

```
t1 = 1 / dt
hrv_leafc_to_prod1c(p)     = presharv(ivt) * (t1*leafc(p)     + cpool_to_leafc(p))
hrv_livestemc_to_prod1c(p) = presharv(ivt) * (t1*livestemc(p) + cpool_to_livestemc(p))
hrv_grainc_to_prod1c(p)    = t1*grainc(p) + cpool_to_grainc(p)
! N and P analogs with the same presharv factor
```

`presharv(ivt)` (from `pftvarcon`, "proportion of residue harvested") is
a PFT-specific fraction of above-ground residue removed at harvest; the
remainder goes to litter via the usual offset litterfall. Grain is
removed in full. `fyield(ivt)` converts harvested grain C to bushels per
acre (via `convfact(ivt)`) and to dry-matter yield t/ha (via the
`cgrain = 0.50` C fraction) for the history fields `CRPYLD` and
`DMYIELD` (`biogeochem/PhenologyMod.F90:2817-2818`).

The routine also sets `cropplant = .false.`, `croplive = .false.`,
updates `harvday_patch`, and calls `CNCropHarvestPftToColumn`
(`biogeochem/PhenologyMod.F90:3526`) to aggregate the patch-level
harvest fluxes to the column in `hrv_cropc_to_prod1c`, 
`hrv_cropn_to_prod1n`, `hrv_cropp_to_prod1p` on `col_cf`/`col_nf`/`col_pf`.

### `CNPerennialCropHarvest` (`biogeochem/PhenologyMod.F90:2852`)

Harvests only the above-ground fraction for perennials; roots and crown
persist.

## Crop harvest pool — `CropHarvestPoolsMod`

`CropHarvestPools` (`biogeochem/CropHarvestPoolsMod.F90:28`) is the
1-year first-order decay of the column-level `prod1c`, `prod1n`, `prod1p`
pools that receive harvest inputs (`hrv_cropc_to_prod1c` and friends).

```
kprod1 = 7.2e-9    ! ~90% loss over 1 year
prod1c_loss(c)  = prod1c(c)  * kprod1
prod1c(c)      += (hrv_cropc_to_prod1c(c) - prod1c_loss(c)) * dt
```

(`biogeochem/CropHarvestPoolsMod.F90:50-102`). The same pattern applies
to C13 and C14 when those tracers are active.

This is the crop-residue counterpart to the 10-year and 100-year
`WoodProducts` pools (`biogeochem/WoodProductsMod.F90`) — see
`biogeochem/mortality.md`. Combined, these three product pools are
ELM's way of tracking carbon removed from the ecosystem on multi-year
time scales.

## Crop residues and litter

Residues that are not harvested (fraction `1 - presharv(ivt)` of
above-ground C) and all root C are routed to litter through the normal
`CNOffsetLitterfall` pathway, using the same `leaf_prof`, `froot_prof`,
`croot_prof`, `stem_prof` vertical distribution as natural PFTs
(via `CNLitterToColumn`, `biogeochem/PhenologyMod.F90:3371`). Because
crop root profiles can shift dramatically through the growing season via
`RootDynamicsMod` (see `biogeochem/mortality.md`), harvested residues
can end up concentrated in shallower layers early in the season and
deeper layers near senescence.

## Fertilizer application

Fertilizer N and P are delivered over a fixed number of days after
emergence: the amounts come from `crop_vars%fertnitro_patch`,
`fertphosp_patch`, which are seeded from the surface file
(`fert_cft`, `fert_p_cft`) in `InitCold`
(`biogeochem/CropType.F90:291-398`). Fertilizer contributes to
`ndep_col` / `pdep_col` pathways and is accounted for in the CNP budget
separately from atmospheric deposition. The FAN (ammonia-to-N flux)
coupling is gated by `fan_to_bgc_crop` in `elm_varctl`
(`biogeochem/PhenologyMod.F90:1408`).

## What the crop pathway does not do

- Prognostic crop rotation — a single crop PFT per patch, no rotation
  within a year. Rotation across years can be approximated by
  dynamically changing the PFT weight via transient landcover.
- Explicit tillage impacts on soil C. Crop turnover is handled through
  the standard litter and harvest-pool pathways.
- Irrigation scheduling from fields within the crop module. Irrigation is
  applied from `IrrigationMod` outside the biogeochem tree and is gated
  by the irrigated-crop PFT (`nc3irrig`, `ncornirrig`, `nscerealirrig`,
  `nwcerealirrig`, `nsoybeanirrig`, `nmiscanthusirrig`,
  `nswitchgrassirrig`).
- Cultivar-specific yield equations. `fyield` and `presharv` are
  single-value-per-PFT and do not adjust for region or year.

## Control flag and conditional execution

| Flag | File | Role |
|---|---|---|
| `use_crop` | `main/elm_varctl.F90:356` | Turns on prognostic crops. Sets `crop_prog` (in `elm_varpar`). |
| `crop_prog` | `elm_varpar` | Gates `CropPhenologyInit`, `InitHistory`/`InitCold` in `CropType%Init`, and the crop branches of `CropPhenology`/`CropPlantDate` inside the phenology driver. |
| `fan_to_bgc_crop` | `main/elm_varctl.F90` | If true, FAN ammonia-to-N fluxes feed the BGC model via the crop module. |
| `spinup_state` | `main/elm_varctl.F90` | Accelerated-spinup mode; for crops, mostly unused but `VegStructUpdateMod` pulls through to adjust stem height on deadstem. |

When `use_crop = .false.`, `CropType%Init` still allocates the `crop_type`
object but only calls `InitAllocate`; `InitHistory` and `InitCold` are
skipped (`biogeochem/CropType.F90:105-108`) and `CropPhenology` is never
called because `num_pcropp = 0`.
