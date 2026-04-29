---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Phenology (ELM-native)

This document describes the ELM-native phenology implementation, used when
`use_cn = .true.` and `use_fates = .false.`. FATES has its own phenology
implementation that replaces this path entirely. ELM-native phenology drives
leaf, fine-root, stem, and coarse-root phenological fluxes (onset and offset),
computes `tlai/tsai/htop/hbot` from carbon pools, and supports a prescribed-LAI
"satellite phenology" mode that bypasses prognostic allocation.

`PhenologyMod.F90` grew from 3598 -> 3754 lines between 60d9aad and d40b8431
(+156 lines), almost entirely from the new winter-wheat survival routine
`coldtolerance` (`:2393-2518`) and the additional crop-state plumbing in
`CropPhenology` and `vernalization`.

## Files in scope

| File | Purpose |
|---|---|
| `biogeochem/PhenologyMod.F90` | Main prognostic CN phenology driver (3754 lines) |
| `biogeochem/PhenologyFluxLimitMod.F90` | Post-allocation flux limiter to prevent negative C/N/P pools |
| `biogeochem/SatellitePhenologyMod.F90` | Prescribed monthly LAI / SAI / canopy-height mode |
| `biogeochem/VegStructUpdateMod.F90` | Diagnose `tlai/tsai/htop/hbot` from leaf/deadstem C |
| `biogeochem/CNPhenologyBeTRMod.F90` | Near-duplicate of `PhenologyMod.F90` wired to the BeTR (reactive-transport) BGC path |

## Entry point and routine map (d40b8431 line numbers)

The public driver is `Phenology` in `PhenologyMod.F90`:

```
Phenology                                (PhenologyMod.F90:261)
├── PhenologyClimate                     (PhenologyMod.F90:435)
├── CNEvergreenPhenology                 (PhenologyMod.F90:527)
├── CNSeasonDecidPhenology               (PhenologyMod.F90:577)
├── CNStressDecidPhenology               (PhenologyMod.F90:912)
├── CropPlantDate         (if num_pcropp > 0)         (PhenologyMod.F90:2521)
├── CropPhenology         (if doalb .and. num_pcropp > 0)   (PhenologyMod.F90:1399)
├── PerennialCropPhenology (if doalb .and. num_ppercropp > 0) (PhenologyMod.F90:1992)
├── CNOnsetGrowth                        (PhenologyMod.F90:2724)
├── CNCropHarvest         (if num_pcropp > 0)        (PhenologyMod.F90:2877)
├── CNPerennialCropHarvest (if num_ppercropp > 0)    (PhenologyMod.F90:2987)
├── CNOffsetLitterfall                   (PhenologyMod.F90:3106)
├── CNBackgroundLitterfall               (PhenologyMod.F90:3308)
└── CNLivewoodTurnover                   (PhenologyMod.F90:3408)
```

Plus the new winter-wheat hardening helper invoked from inside
`CropPhenology`:

```
coldtolerance                            (PhenologyMod.F90:2393)
```

`coldtolerance` is called only for winter temperate cereal patches and
implements the Lu et al. 2017 / Bergjord et al. 2008 frost-tolerance model.
See "Winter-wheat survival" below.

`CNLitterToColumn` (`PhenologyMod.F90:3527`, public entry, called from
`EcosystemDynNoLeaching2`) aggregates patch-level litterfall to column
decomposition layers using `leaf_prof`, `froot_prof`, `croot_prof`, and
`stem_prof`.

Each `CN*Phenology` subroutine filters by a binary PFT flag (`evergreen`,
`season_decid`, `stress_decid`) read from `veg_vp`. The same onset/offset
counters (`onset_flag`, `onset_counter`, `offset_flag`, `offset_counter`) and
growth-rate variables (`bglfr_leaf`, `bglfr_froot`, `bgtr`, `lgsf`) are used
across branches.

## `PhenologyInit` and parameter sources

`PhenologyInit(bounds)` (`PhenologyMod.F90:354-432`) caches time-invariant
parameters read by `readPhenolParams` (`:131-258`) from the netCDF parameter
file. They populate `PhenolParamsInst` of type `PnenolParamsType`.

| Param | Meaning |
|---|---|
| `crit_dayl` | critical day length for senescence (seasonal deciduous) |
| `crit_dayl_stress` | critical day length for stress-deciduous onset/offset |
| `cumprec_onset` | 10-day cumulative precipitation threshold for onset |
| `ndays_on` / `ndays_off` | length (days) of the onset / offset period |
| `fstor2tran` | fraction of storage to flush into transfer pool at onset |
| `crit_onset_fdd` | freezing-degree-days threshold |
| `crit_onset_swi` | wet-day threshold before onset |
| `soilpsi_on` / `soilpsi_off` | wet / dry soil water-potential thresholds |
| `crit_offset_fdd` / `crit_offset_swi` | cold / dry stress counters |
| `lwtop` | live-wood annual turnover fraction |

`PhenologyInit` converts `lwtop` from an annual fraction to a per-second rate
(`:401`) and calls `CropPhenologyInit(bounds)` (`:407`) if `crop_prog` is set.

## `PhenologyClimate` — slowly varying climate state

`PhenologyClimate` (`:435-524`) accumulates a `fracday`-weighted running mean
2 m air temperature (`tempavg_t2m`) and, for prognostic crops only, maintains
20-year running means of growing-degree days with base 0, 8, and 10 deg C
(`gdd020`, `gdd820`, `gdd1020`).

## Evergreen branch (`CNEvergreenPhenology`)

For PFTs with `evergreen(ivt) == 1`, sets background leaf and fine-root
litterfall rates as the reciprocal of leaf and fine-root longevity:

```
bglfr_leaf(p)  = 1 / (leaf_long(ivt(p))  * dayspyr * secspday)
bglfr_froot(p) = 1 / (froot_long(ivt(p)) * dayspyr * secspday)
```

`bgtr = 0` and `lgsf = 0` for evergreens.

## Seasonal-deciduous branch (`CNSeasonDecidPhenology`)

Applies to PFTs with `season_decid(ivt) == 1`. Implements the Biome-BGC v4.1.2
algorithm (`:577-909`). One growing season per year is enforced by gating GDD
accumulation on the solstices. Onset triggers when
`onset_gdd > exp(4.8 + 0.13 * (annavg_t2m(p) - Tkfrz))`, fraction `fstor2tran`
of every storage pool is moved into the transfer pool. Offset triggers past
summer solstice when day length drops below `crit_dayl`.

## Stress-deciduous branch (`CNStressDecidPhenology`)

Applies to grasses and drought-deciduous trees (`stress_decid(ivt) == 1`)
(`:912-1396`). Multiple growing seasons per year possible. Joint wet-and-warm
criterion via `onset_fdd`, GDD, and `onset_swi` (top-3 layer
`soilpsi >= soilpsi_on`). Minimum day length test against `crit_dayl_stress`.
Precipitation gate `cumprec_onset` runs only when `nu_com == 'RD'`.

Stress deciduous also computes a "long growing season factor" (`lgsf`) based
on `days_active`.

## Crop phenology

`CropPhenology` (`:1399-1989`) and `PerennialCropPhenology` (`:1992-2234`)
implement the AgroIBIS-derived prognostic crop pathway. Run only on the albedo
time step (`doalb`). Planting date is chosen by `CropPlantDate`
(`:2521-2721`) with vernalization handled by `vernalization` (`:2311-2389`).

After planting, GDD accumulation relative to planting drives leaf emergence
(`lfemerg`), grain fill (`grnfill`), and harvest (`mxmat`); vertical root
growth driven by `huigrain`. `CropType` in `biogeochem/CropType.F90` holds the
per-patch state.

`CropPhenologyInit(bounds)` is at `:2237-2308`.

### Winter-wheat survival (NEW at d40b8431) — `coldtolerance` (`:2393-2518`)

Called only for winter temperate cereal patches inside `CropPhenology`. The
routine implements the Lu et al. (2017) winter-wheat survival model based on
Bergjord et al. (2008) frost-tolerance. It uses ten new patch fields exposed
on `crop_type` (`CropType.F90:41-50, 141-150`):

| Field | Units | Meaning |
|---|---|---|
| `rateh_patch(p)` | 1/dt | increase of tolerance caused by cold hardening |
| `rated_patch(p)` | 1/dt | loss of tolerance caused by dehardening |
| `rates_patch(p)` | 1/dt | loss of tolerance caused by low temperature |
| `rater_patch(p)` | 1/dt | loss of tolerance caused by respiration under snow |
| `lt50_patch(p)` | deg C | lethal temperature at 50% of individuals damaged |
| `fsurv_patch(p)` | 0-1 | winter-wheat survival rate |
| `accfsurv_patch(p)` | 0-1 | accumulated daily survival rate |
| `countfsurv_patch(p)` | count | accumulator denominator |
| `wdd_patch(p)` | deg C * day | weighted cumulated degree days |
| `tcrown_patch(p)` | K | crown temperature |

Module-level constants inside `coldtolerance` (Lu et al. 2017):

```fortran
real(r8), parameter :: Hparam = 0.0093   ! Bergjord 2008
real(r8), parameter :: Dparam = 2.7e-5   ! Bergjord 2008
real(r8), parameter :: Sparam = 1.9
real(r8), parameter :: Rparam = 0.54
real(r8), parameter :: T_S_max = 12.5
real(r8), parameter :: lt50max = -23
```

The vernalization factor (`vf_patch`) now applies only after leaf emergence
(diff against 60d9aad in `CropType.F90` and the vernalization callsite in
`CropPhenology`).

## `CNOnsetGrowth`, `CNOffsetLitterfall`, `CNBackgroundLitterfall`, `CNLivewoodTurnover`

These four routines run unconditionally after all branch tests and translate
the phenology state variables into actual C/N/P fluxes:

- `CNOnsetGrowth` (`:2724-2874`) — pushes transfer-pool C/N/P into displayed
  pools over `ndays_on` days.
- `CNOffsetLitterfall` (`:3106-3305`) — converts displayed leaf and fine-root
  C/N/P into litter over `ndays_off` days, with the previous time step's
  litterfall flux used to enforce a consistent ramp.
- `CNBackgroundLitterfall` (`:3308-3405`) — applies the PFT-specific
  `bglfr_leaf` and `bglfr_froot` rates to displayed pools.
- `CNLivewoodTurnover` (`:3408-3524`) — converts a fraction `lwtop` (per-second)
  of livestem and livecroot C/N/P into deadstem and deadcroot pools.

Finally `CNLitterToColumn` (`:3527-3679`, public) and
`CNCropHarvestPftToColumn` (`:3682-3752`) aggregate patch-level fluxes to
column decomposition layers using `leaf_prof`, `froot_prof`, `croot_prof`,
`stem_prof`.

## `PhenologyFluxLimitMod` — keeping pools positive

`phenology_flux_limiter` is called by the BGC driver after phenology has
proposed onset/offset and background fluxes. It constructs a sparse flux
network per patch and runs `carbon_flux_limiter`, `nitrogen_flux_limiter`, and
`phosphorus_flux_limiter` for the main element pools plus, when enabled, C13
and C14 analogues. Uses `LSparseMatMod`'s `flux_correction` operator to scale
down any flux that would drive a state variable negative within one time
step.

## Satellite phenology (prescribed LAI)

`SatellitePhenologyMod.F90` provides the "SP" alternative where LAI, SAI,
canopy top height, and canopy bottom height are prescribed from monthly input
files. Active when `use_cn = .false.` or `use_fates_sp = .true.`.

Key entry points:

- `SatellitePhenologyInit` — allocate month-pair buffers (`mlai2t`, `msai2t`,
  `mhvt2t`, `mhvb2t`).
- `interpMonthlyVeg` — decides whether to read two new months.
- `readMonthlyVegetation` — I/O routine for monthly LAI/SAI/height arrays.
- `SatellitePhenology` — interpolates between bracketing months. If
  `use_lai_streams = .true.`, `tlai` comes from `lai_interp` via
  `shr_strdata`. Applies snow burial via
  `ol = min(max(snow_depth - hbot, 0), htop - hbot)`. In FATES-SP mode,
  `elai`/`esai` are intentionally NOT written here; FATES IFP-indexed fields
  take over.

## `VegStructUpdate` — diagnose canopy from C pools

`VegStructUpdate` (`biogeochem/VegStructUpdateMod.F90`) runs on the radiation
time step in the prognostic path. Implements:

- Leaf area: `tlai(p) = slatop * leafc` or, when `dsladlai > 0`,
  `tlai(p) = (slatop/dsladlai) * (exp(leafc * dsladlai) - 1)`
  (Thornton & Zimmerman 2007 Eq 3).
- Stem area: Zeng et al. 2002 formula
  `tsai(p) = max(alpha*tsai_old + max(tlai_old - tlai, 0), tsai_min)`.
- Tree / shrub height: `htop = (3*deadstemc*taper^2 / (pi*stocking*dwood))^(1/3)`
  with `taper=200` for trees, `taper=10` for shrubs, `stocking=1000 stems/ha`.
  At d40b8431 the trees-vs-shrubs branching uses `woody == 1.0_r8` and
  `woody == 2.0_r8` (ternary flag).
- Crop height: `htop = ztopmx * min(tlai/(laimx-1), 1)^2`.
- Grass height: `htop = max(0.25, tlai * 0.25)`.
- Snow burial: identical to `SatellitePhenology`, with short-vegetation using
  Wang & Zeng (2007) partial burial.

## BeTR variant

`CNPhenologyBeTRMod.F90` is a near-copy of `PhenologyMod.F90` used when ELM is
coupled to the BeTR reactive-transport tracer system. It exposes the same
public interfaces (`CNPhenologyInit`, `CNPhenology`, `readCNPhenolBeTRParams`)
and the same internal routines. Differences are limited to the specific tracer
state objects it updates via the `CNBeTR` indexing.

## Control-flag summary (with d40b8431 line numbers)

| Flag | File | Effect on phenology |
|---|---|---|
| `use_cn` | `main/elm_varctl.F90:388` | Enables `PhenologyMod.F90` prognostic path. |
| `use_fates` | `main/elm_varctl.F90:227` | Turns off ELM-native phenology; FATES owns the leaf habit. |
| `use_fates_sp` | `main/elm_varctl.F90:248` | Satellite phenology inside FATES. Skips `elai`/`esai` overwrite in `SatellitePhenology`. |
| `use_lai_streams` | `main/elm_varctl.F90:286` | In SP mode, pulls `tlai` from a named LAI stream. |
| `use_crop` | `main/elm_varctl.F90:390` | Enables prognostic crop pathway. |
| `nu_com` | `main/elm_varctl.F90` | Selects CNP vs RD nutrient competition. The stress-deciduous precipitation gate (`cumprec_onset`) runs only in RD mode. |

About a dozen other FATES-related flags are declared in
`main/elm_varctl.F90:227-256`:

- `fates_spitfire_mode` (`:228`) — integer SPITFIRE mode (see `fire.md`).
- `use_fates_managed_fire` (`:229`) — managed-fire toggle.
- `fates_harvest_mode` (`:230`) — replaces the deleted `use_fates_logging`.
- `fates_stomatal_model` (`:232`) — Ball-Berry vs Medlyn.
- `fates_leafresp_model` (`:234`) — Ryan vs Atkin.
- `fates_cstarvation_model` (`:235`) — linear vs exponential.
- `fates_hydro_solver` (`:237`) — 1D Taylor vs 2D Picard vs 2D Newton.
- `fates_radiation_model` (`:238`) — Norman vs two-stream.
- `fates_electron_transport_model` (`:239`) — FvCB vs JB.
- `use_fates_luh` (`:249`), `use_fates_lupft` (`:250`),
  `use_fates_potentialveg` (`:251`), `use_fates_daylength_factor` (`:252`).

`use_fates_logging` was REMOVED at d40b8431 (replaced by `fates_harvest_mode`).

## Contrast with FATES phenology

ELM-native phenology and FATES phenology implement the same biological
concepts (cold and stress deciduous onset and offset, background litterfall,
live-wood turnover), but the implementations are disjoint code paths. FATES
has its own cohort-resolved GDD accumulator, its own onset and offset
counters, and its own set of phenology parameters on the FATES parameter file.
Switching between `use_cn` and `use_fates` replaces the entire phenology
subsystem. The parameters documented here (`crit_dayl`, `crit_dayl_stress`,
`fstor2tran`, `ndays_on`, `ndays_off`, `crit_onset_fdd`, `crit_offset_swi`,
`lwtop`, `cumprec_onset`) do not apply when FATES is active.
