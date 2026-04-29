---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Crops (CropMod, CropType, CropHarvestPoolsMod)

This document covers the ELM prognostic crop pathway. Active only when
`use_crop = .true.` (`main/elm_varctl.F90:390`), which also sets
`crop_prog = .true.` inside `elm_varpar`. Crops are modeled as additional PFTs
(`nc3crop`, `nc3irrig`, `ncorn`, `nsoybean`, `nscereal`, `nwcereal`, irrigated
variants, and the perennial bioenergy PFTs `nmiscanthus`, `nswitchgrass` plus
their irrigated variants) inside the normal CN subgrid. Crop-specific state
and routines are kept in three files; phenology, harvest, and planting-date
logic live inside `PhenologyMod.F90`.

| File | Role |
|---|---|
| `biogeochem/CropType.F90` | `crop_type` object holding per-patch crop state, history registration, init/restart/update. |
| `biogeochem/CropMod.F90` | Two utility routines: reference-ET calculation (`calculate_eto`) and planting-month selection (`plant_month`). |
| `biogeochem/CropHarvestPoolsMod.F90` | 1-year column-level harvest pool `prod1c/n/p` with first-order decay. |
| `biogeochem/PhenologyMod.F90` | `CropPhenology`, `PerennialCropPhenology`, `CropPlantDate`, `vernalization`, `coldtolerance`, `CNCropHarvest`, `CNPerennialCropHarvest`, `CropPhenologyInit`. |

## `crop_type` -- per-patch state (winter-wheat fields are NEW at d40b8431)

Defined in `biogeochem/CropType.F90:34`. Existing fields (per the 60d9aad
inventory) plus **ten new winter-wheat hardening fields** allocated at
`CropType.F90:141-150`:

```fortran
allocate(this%rateh_patch       (begp:endp)) ; this%rateh_patch       (:) = spval  ! cold hardening rate
allocate(this%rated_patch       (begp:endp)) ; this%rated_patch       (:) = spval  ! dehardening rate
allocate(this%rates_patch       (begp:endp)) ; this%rates_patch       (:) = spval  ! low-temperature loss
allocate(this%rater_patch       (begp:endp)) ; this%rater_patch       (:) = spval  ! respiration-under-snow loss
allocate(this%lt50_patch        (begp:endp)) ; this%lt50_patch        (:) = spval  ! lethal temperature at 50% damaged (deg C)
allocate(this%fsurv_patch       (begp:endp)) ; this%fsurv_patch       (:) = spval  ! winter wheat survival rate
allocate(this%accfsurv_patch    (begp:endp)) ; this%accfsurv_patch    (:) = spval  ! accumulated daily survival rate
allocate(this%countfsurv_patch  (begp:endp)) ; this%countfsurv_patch  (:) = spval  ! count of accumulated days
allocate(this%wdd_patch         (begp:endp)) ; this%wdd_patch         (:) = spval  ! winter weighted cumulated degree days
allocate(this%tcrown_patch      (begp:endp)) ; this%tcrown_patch      (:) = spval  ! crown temperature (K)
```

These fields drive the new `coldtolerance` subroutine in `PhenologyMod.F90:2393`
(see `phenology.md` and below).

Other key fields (existing):

- `croplive_patch (:)` -- true while planted and not harvested.
- `cropplant_patch (:)` -- true once planted at least once this year.
- `nyrs_crop_active_patch (:)` -- years the crop has been active on this
  patch.
- `harvdate_patch (:)` -- day of year of harvest (999 if not harvested yet).
- `fertnitro_patch (:)`, `fertphosp_patch (:)` -- max N and P fertilizer.
- `gddplant_patch (:)` -- accumulated GDD since planting.
- `gddtsoi_patch (:)` -- GDD from top soil-layer temperature.
- `crpyld_patch (:)` -- crop yield (bu/acre).
- `dmyield_patch (:)` -- dry matter yield (t/ha).
- `vf_patch (:)` -- vernalization factor for cereals (0-1).
- `cphase_patch (:)` -- growth phase index.
- `latbaset_patch (:)` -- latitude-varying base T for GDD.
- `plantmonth_patch (:)`, `plantday_patch (:)`, `harvday_patch (:)`.
- Monthly seasonality: `xt_patch(:,1:12)`, `xp_patch(:,1:12)`, EWMAs
  `xt_bar_patch`, `xp_bar_patch`, prior-year `prev_xt_bar_patch`,
  `prev_xp_bar_patch`, ratio `p2ETo_patch`, `p2ETo_bar_patch`,
  `prev_p2ETo_bar_patch`, `P2E_rm_patch`, `ETo_patch`.
- `cvt_patch`, `cvp_patch` -- coefficients of variation for the planting-month
  classifier.

Module-level constants for the planting-month classifier (`CropType.F90:27-29`):
`tcvp = 0.4`, `tcvt = 0.01`, `cst = 283` K.

### Type-bound procedures

- `Init` -> `InitAllocate`, and when `crop_prog = .true.`, `InitHistory` and
  `InitCold`. `InitHistory` registers 1D and 2D history fields including the
  new `RATEH`, `RATED`, `RATES`, `RATER`, `LT50`, `FSURV`, `WDD`, `TCROWN`
  for winter-wheat diagnostics.
- `InitAccBuffer`, `InitAccVars`, `UpdateAccVars` -- manage 20-year GDD running
  means and seasonality classifier (via `accumulMod`).
- `Restart` -- read/write crop state for restarts.
- `CropIncrementYear(this, num_pcropp, filter_pcropp, num_ppercropp,
  filter_ppercropp)` (`:730-775`) -- year-boundary bookkeeping. **At d40b8431
  this signature gained `num_ppercropp, filter_ppercropp`** (perennial-crop
  filter); call sites that pass only the prognostic-crop filter will not
  compile.
- `checkDates` (private, nopass) -- sanity check on planting/harvest dates.

## `CropMod.F90` -- reference ET and planting month

Two public subroutines (`biogeochem/CropMod.F90:18-19`):

### `calculate_eto(T, rn, g, p, rh, u, dt, eto)` (`CropMod.F90:28-90`)

Implements FAO Penman-Monteith reference evapotranspiration (`ETo`,
mm/timestep):

```
ETo = (0.408*Δ*(Rn - G) + γ*(900/(T+273))*u*(es - ea)) / (Δ + γ*(1 + 0.34*u))
```

Constants (`c1=0.408`, `c3=0.34`, `c4=900`, `c5=237.3`, `esc1=0.6108`,
`esc2=17.27`, `dc1=4098`, `gc1=0.000665`) are the standard FAO-56 values.

### `plant_month(p, cvt, cvp, temp, p2e, minplantjday, plantmonth)` (`CropMod.F90:93-146`)

Chooses the planting month based on seasonality of temperature and
precipitation:

- If `cvp > tcvp`:
  - `cvt >= tcvt`: both T and P seasonality. If there is a cold season
    (`min(temp) < cst = 283 K`), plant when monthly temperature exceeds the
    PFT's `planttemp` past `minplantjday`; otherwise plant in the month that
    maximizes `maxloc(p2e)`.
  - `cvt < tcvt`: precipitation seasonality only -- plant in `maxloc(p2e)`.
- `cvt > tcvt` only: temperature seasonality -- plant when criterion is met.
- Neither seasonal: plant in month 1 (tropical default).

Called once per year from `CropPlantDate` (`PhenologyMod.F90:2521`).

## Crop phenology in `PhenologyMod.F90`

### `CropPhenologyInit` (`PhenologyMod.F90:2237-2308`)

Called from `PhenologyInit` when `crop_prog`. Sets up vernalization constants
`p1d`, `p1v`, `hti`, `tbase`, the `minplantjday`, `maxplantjday` arrays by PFT
and hemisphere, and the hemisphere mapping `inhemi(:)`.

### `CropPhenology` (`PhenologyMod.F90:1399-1989`)

Called once per day (`doalb` time step) for each prognostic-crop patch. The
AgroIBIS-style day-by-day phenology driver. Logical flow:

1. Determine Julian day, compute GDD increment relative to PFT base
   temperature. Pre-planting GDD uses `t_ref2m`; `gddtsoi` uses top-2-layer
   soil temperature.
2. If not yet planted and the planting window is open, check
   `a5tmin > minplanttemp(ivt)`, `t10 > planttemp(ivt)`, soil moisture
   between `minwet` and `maxwet`, no rainfall today (`minrain = 0.1`). If all
   met, set `croplive = .true.`, record `idop` and `plantday`, zero
   `gddplant`, `gddtsoi`, `vf`, and running min/max T buffers.
3. **Vernalization (winter cereals).** Now applies only AFTER leaf emergence
   (changed from 60d9aad — vernalization factor accumulates only during the
   active-leaf phase, see CropType.F90 diff hunk near line 692-717).
   `vernalization(p, ...)` runs for all winter cereals to update `vf`.
4. **`coldtolerance(p, cnstate_vars, crop_vars)` (`PhenologyMod.F90:2393-2518`,
   NEW at d40b8431).** Implements the Lu et al. (2017) winter-wheat survival
   model based on Bergjord et al. (2008) frost tolerance. Uses Hardening
   parameters `Hparam=0.0093`, `Dparam=2.7e-5`, `Sparam=1.9`, `Rparam=0.54`,
   `T_S_max=12.5` deg C, `lt50max=-23` deg C. Outputs into the new
   `crop_vars%rateh_patch`, `rated_patch`, `rates_patch`, `rater_patch`,
   `lt50_patch`, `fsurv_patch`, `accfsurv_patch`, `countfsurv_patch`,
   `wdd_patch`, `tcrown_patch` fields.
5. Update `gddplant` and `gddtsoi`. Check progression through phenological
   phases (`cphase`):
   - Leaf emergence at `hui > huileaf * gddmaturity` (`lfemerg`).
   - Grain fill at `hui > huigrain * gddmaturity` (`grnfill`).
   - Harvest when `hui > gddmaturity` or `nyrs_crop_active` exceeds
     `mxmat(ivt)`.
6. On harvest, set `offset_flag = 1`, `offset_counter = 1 * secspday`, which
   triggers `CNCropHarvest` later in the same driver.
7. Update `bglfr_leaf`, `bglfr_froot`, `bgtr` to zero during active growing
   season.
8. Apply fertilizer over `ndays_on = 21` days starting at emergence.

### `PerennialCropPhenology` (`PhenologyMod.F90:1992-2234`)

Variant for the perennial bioenergy crops (miscanthus, switchgrass) that can
be harvested but survive between years. Identical GDD framework, retains root
and crown pools across harvest, resets only leaves and stem.

### `CNCropHarvest` (`PhenologyMod.F90:2877-2984`)

Runs during the offset period of a prognostic-crop patch and, on the last
step of the offset counter, computes harvest-to-product fluxes:

```fortran
t1 = 1 / dt
hrv_leafc_to_prod1c(p)     = presharv(ivt) * (t1*leafc(p)     + cpool_to_leafc(p))
hrv_livestemc_to_prod1c(p) = presharv(ivt) * (t1*livestemc(p) + cpool_to_livestemc(p))
hrv_grainc_to_prod1c(p)    = t1*grainc(p) + cpool_to_grainc(p)
! N and P analogs with the same presharv factor
```

`presharv(ivt)` (from `pftvarcon`) is the residue-harvested fraction. Grain
is removed in full. `fyield(ivt)` converts harvested grain C to bushels per
acre and `cgrain = 0.50` to dry-matter yield t/ha for the `CRPYLD` and
`DMYIELD` history fields.

The routine sets `cropplant = .false.`, `croplive = .false.`, updates
`harvday_patch`, and calls `CNCropHarvestPftToColumn` (`:3682-3752`) to
aggregate the patch-level harvest fluxes to column.

### `CNPerennialCropHarvest` (`PhenologyMod.F90:2987-3103`)

Harvests only the above-ground fraction for perennials; roots and crown
persist.

## Crop harvest pool -- `CropHarvestPoolsMod`

`CropHarvestPools(num_soilc, filter_soilc, dt)`
(`biogeochem/CropHarvestPoolsMod.F90:28`) is the 1-year first-order decay of
column-level `prod1c`, `prod1n`, `prod1p` pools.

```
kprod1 = 7.2e-9    ! ~90% loss over 1 year
prod1c_loss(c)  = prod1c(c)  * kprod1
prod1c(c)      += (hrv_cropc_to_prod1c(c) - prod1c_loss(c)) * dt
```

Same pattern applies to C13 and C14 when those tracers are active. The
`iscft` test now gates the per-patch contributions inside the routine
(replacing `ivt >= npcropmin` per the `pftvarcon` refactor).

This is the crop-residue counterpart to the 10-year and 100-year
`WoodProducts` pools — see `mortality.md`. `CropHarvestPools` runs
unconditionally at `EcosystemDynNoLeaching2:798` (when `.not. use_fates`) and
`:815` (when `use_fates`); it is not gated by FATES.

## Crop residues and litter

Residues that are not harvested (fraction `1 - presharv(ivt)`) and all root C
are routed to litter through the normal `CNOffsetLitterfall` pathway, using
the same `leaf_prof`, `froot_prof`, `croot_prof`, `stem_prof` vertical
distribution as natural PFTs (via `CNLitterToColumn`,
`PhenologyMod.F90:3527`).

## Fertilizer application

Fertilizer N and P are delivered over a fixed number of days after emergence:
amounts come from `crop_vars%fertnitro_patch`, `fertphosp_patch`, seeded from
the surface file (`fert_cft`, `fert_p_cft`) in `InitCold`. Fertilizer
contributes to `ndep_col` / `pdep_col` and is accounted for in the CNP budget
separately from atmospheric deposition. The FAN coupling is gated by
`fan_to_bgc_crop`.

## What the crop pathway does not do

- Prognostic crop rotation -- a single crop PFT per patch, no within-year
  rotation. Across-year rotation can be approximated by transient landcover.
- Explicit tillage impacts on soil C.
- Irrigation scheduling within the crop module. Irrigation comes from
  `IrrigationMod` and is gated by irrigated-crop PFTs.
- Cultivar-specific yield equations.

## Control flag and conditional execution (with d40b8431 line numbers)

| Flag | File | Role |
|---|---|---|
| `use_crop` | `main/elm_varctl.F90:390` | Turns on prognostic crops. Sets `crop_prog`. |
| `crop_prog` | `elm_varpar` | Gates `CropPhenologyInit`, `InitHistory`/`InitCold` in `CropType%Init`, and the crop branches. |
| `fan_to_bgc_crop` | `main/elm_varctl.F90` | If true, FAN ammonia-to-N fluxes feed BGC via the crop module. |
| `spinup_state` | `main/elm_varctl.F90` | Accelerated-spinup mode. |

When `use_crop = .false.`, `CropType%Init` still allocates the `crop_type`
object but only calls `InitAllocate`; `InitHistory` and `InitCold` are
skipped, and `CropPhenology` is never called because `num_pcropp = 0`.
