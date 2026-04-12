---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Phenology (ELM-native)

This document describes the ELM-native phenology implementation, used when
`use_cn = .true.` and `use_fates = .false.`. FATES has its own phenology
implementation that replaces this path entirely — see the FATES wiki for that
code. ELM-native phenology drives leaf, fine-root, stem, and coarse-root
phenological fluxes (onset and offset), computes `tlai/tsai/htop/hbot` from
carbon pools, and supports a prescribed-LAI "satellite phenology" mode that
bypasses prognostic allocation.

## Files in scope

| File | Purpose |
|---|---|
| `biogeochem/PhenologyMod.F90` | Main prognostic CN phenology driver (~3598 lines) |
| `biogeochem/PhenologyFluxLimitMod.F90` | Post-allocation flux limiter to prevent negative C/N/P pools |
| `biogeochem/SatellitePhenologyMod.F90` | Prescribed monthly LAI / SAI / canopy-height mode |
| `biogeochem/VegStructUpdateMod.F90` | Diagnose `tlai/tsai/htop/hbot` from leaf/deadstem C |
| `biogeochem/CNPhenologyBeTRMod.F90` | Near-duplicate of `PhenologyMod.F90` wired to the BeTR (reactive-transport) BGC path |

## Entry point and routine map

The public driver is `Phenology` in `PhenologyMod.F90`:

```
Phenology                               (PhenologyMod.F90:261)
├── PhenologyClimate                    (PhenologyMod.F90:430)
├── CNEvergreenPhenology                (PhenologyMod.F90:522)
├── CNSeasonDecidPhenology              (PhenologyMod.F90:572)
├── CNStressDecidPhenology              (PhenologyMod.F90:907)
├── CropPlantDate        (if num_pcropp > 0)       (PhenologyMod.F90:2393)
├── CropPhenology        (if doalb .and. num_pcropp > 0)  (PhenologyMod.F90:1394)
├── PerennialCropPhenology (if doalb .and. num_ppercropp > 0) (PhenologyMod.F90:1950)
├── CNOnsetGrowth                       (PhenologyMod.F90:2587)
├── CNCropHarvest         (if num_pcropp > 0)      (PhenologyMod.F90:2740)
├── CNPerennialCropHarvest (if num_ppercropp > 0)  (PhenologyMod.F90:2852)
├── CNOffsetLitterfall                  (PhenologyMod.F90:2950)
├── CNBackgroundLitterfall              (PhenologyMod.F90:3152)
└── CNLivewoodTurnover                  (PhenologyMod.F90:3252)
```

Each `CN*Phenology` subroutine filters by a binary PFT flag (`evergreen`,
`season_decid`, `stress_decid`) read from `veg_vp`
(`biogeochem/PhenologyMod.F90:546,603,950`), so the three leaf-habit branches
run only for the PFTs they apply to. The same onset/offset
counters (`onset_flag`, `onset_counter`, `offset_flag`, `offset_counter`) and
growth-rate variables (`bglfr_leaf`, `bglfr_froot`, `bgtr`, `lgsf`) are used
across branches (`biogeochem/PhenologyMod.F90:291-347`).

## `PhenologyInit` and parameter sources

`PhenologyInit` (`biogeochem/PhenologyMod.F90:350`) caches time-invariant
parameters read by `readPhenolParams` (`biogeochem/PhenologyMod.F90:131`) from
the netCDF parameter file. They populate `PhenolParamsInst` of type
`PnenolParamsType` (`biogeochem/PhenologyMod.F90:57-75`):

| Param | Meaning |
|---|---|
| `crit_dayl` | critical day length for senescence (seasonal deciduous) |
| `crit_dayl_stress` | critical day length for stress-deciduous onset/offset |
| `cumprec_onset` | 10-day cumulative precipitation threshold for onset |
| `ndays_on` / `ndays_off` | length (days) of the onset / offset period |
| `fstor2tran` | fraction of storage to flush into the transfer pool at onset |
| `crit_onset_fdd` | freezing-degree-days threshold that must be accumulated before GDD accumulation can start |
| `crit_onset_swi` | wet-day threshold before onset can trigger |
| `soilpsi_on` / `soilpsi_off` | wet / dry soil water-potential thresholds |
| `crit_offset_fdd` / `crit_offset_swi` | cold / dry stress counters for offset |
| `lwtop` | live-wood annual turnover fraction |

`PhenologyInit` also converts `lwtop` from an annual fraction to a per-second
rate (`biogeochem/PhenologyMod.F90:396`) and calls `CropPhenologyInit` if
`crop_prog` is set (`biogeochem/PhenologyMod.F90:402`).

## `PhenologyClimate` — slowly varying climate state

`PhenologyClimate` (`biogeochem/PhenologyMod.F90:430`) accumulates a
`fracday`-weighted running mean 2 m air temperature (`tempavg_t2m`) and, for
prognostic crops only, maintains 20 year running means of growing-degree days
with base 0, 8, and 10 °C (`gdd020`, `gdd820`, `gdd1020`). Those are reset on
Jan 1 of the first active year and updated with `yravg = 20` once per year
(`biogeochem/PhenologyMod.F90:500-515`).

## Evergreen branch (`CNEvergreenPhenology`)

For every PFT with `evergreen(ivt) == 1`, the module sets background leaf and
fine-root litterfall rates as the reciprocal of leaf and fine-root longevity
(converted to per-second) and sets `bgtr = 0` and `lgsf = 0`
(`biogeochem/PhenologyMod.F90:559-565`):

```
bglfr_leaf(p)  = 1 / (leaf_long(ivt(p))  * dayspyr * secspday)
bglfr_froot(p) = 1 / (froot_long(ivt(p)) * dayspyr * secspday)
```

These rates drive `CNBackgroundLitterfall`, the constant, year-round leaf and
root turnover for needleleaf and broadleaf evergreens.

## Seasonal-deciduous branch (`CNSeasonDecidPhenology`)

Applies to PFTs with `season_decid(ivt) == 1` (temperate broadleaf deciduous
trees, boreal deciduous trees). The branch implements the classical
Biome-BGC v4.1.2 algorithm (`biogeochem/PhenologyMod.F90:572-904`). One growing
season per year is enforced by gating GDD accumulation on the solstices:

1. Dormant period. `dormant_flag = 1`. Background rates are zero. A
   winter-summer-solstice flag `ws_flag` is derived from
   `dayl(g) >= prev_dayl(g)` (`biogeochem/PhenologyMod.F90:726`). Once
   `ws_flag == 1` the GDD counter is armed (`onset_gddflag = 1`), and if the
   sum passes the summer solstice without reaching the threshold the flag is
   cleared so onset cannot trigger until the next winter solstice
   (`biogeochem/PhenologyMod.F90:818-832`).
2. GDD accumulation. With the flag armed and soil above freezing,
   `onset_gdd` is incremented by `(soilt - Tkfrz) * fracday` using the top-3
   soil layer temperature (`biogeochem/PhenologyMod.F90:837-840`).
3. Onset trigger. The critical GDD sum is a Biome-BGC exponential in annual
   mean 2 m temperature
   (`biogeochem/PhenologyMod.F90:723`):

   ```
   crit_onset_gdd = exp(4.8 + 0.13 * (annavg_t2m(p) - Tkfrz))
   ```

   When `onset_gdd > crit_onset_gdd`, the code sets `onset_flag = 1`, clears
   the dormancy flag, arms `onset_counter = ndays_on * secspday`, and moves a
   fraction `fstor2tran` of every storage pool (leaf, froot, livestem,
   deadstem, livecroot, deadcroot, gresp, plus N and P analogs) into the
   matching transfer pool (`biogeochem/PhenologyMod.F90:843-885`). The
   transfer-to-displayed flux is then set in `CNOnsetGrowth`.
4. Offset trigger. Once `ws_flag == 0` (past summer solstice), a day length
   below `crit_dayl` sets `offset_flag = 1` and arms `offset_counter =
   ndays_off * secspday` (`biogeochem/PhenologyMod.F90:890-895`).
5. Counter decrement. Each step decrements the counters; when the onset
   counter reaches zero all transfer pools and transfer-flux fields are zeroed
   and the branch re-enters active display growth
   (`biogeochem/PhenologyMod.F90:755-810`). When the offset counter reaches
   zero the branch re-enters dormancy and resets litterfall memories
   (`biogeochem/PhenologyMod.F90:733-752`).

## Stress-deciduous branch (`CNStressDecidPhenology`)

Applies to grasses and drought-deciduous trees (`stress_decid(ivt) == 1`).
This branch allows multiple growing seasons per year and can fall back to an
"essentially evergreen" habit with a deciduous leaf longevity when no stress
trigger fires (`biogeochem/PhenologyMod.F90:907-924`). The onset criterion is
a layered wet/cold test (`biogeochem/PhenologyMod.F90:1157-1210`):

1. During dormancy, `onset_fdd` counts freezing-degree days. Once it exceeds
   `crit_onset_fdd`, the GDD accumulator is armed and `onset_swi` is reset
   (`biogeochem/PhenologyMod.F90:1164-1176`).
2. GDD accumulation uses the same top-3 soil temperature formulation as the
   seasonal-deciduous branch.
3. `onset_swi` counts days with top-3 `soilpsi >= soilpsi_on`. When
   `onset_swi > crit_onset_swi`, `onset_flag` is set; the flag is then
   overridden to zero if the freeze trigger has fired and the GDD sum is
   still below `crit_onset_gdd`, enforcing a joint wet-and-warm criterion
   (`biogeochem/PhenologyMod.F90:1191-1200`).
4. Minimum day length. `onset_flag` is cleared if
   `dayl(g) <= crit_dayl_stress` (`biogeochem/PhenologyMod.F90:1203`).
5. Precipitation gate (RD mode only). If the cumulative 10-day precipitation
   is below `cumprec_onset`, onset is suppressed; the comment cites
   Dahlin et al., Biogeosciences 2015
   (`biogeochem/PhenologyMod.F90:1207-1210`). This test runs only when
   `nu_com == 'RD'` (soilorder / RD nutrient competition mode).

Storage-to-transfer flushing on onset uses the same `fstor2tran` logic as the
seasonal branch (`biogeochem/PhenologyMod.F90:1230-1258`). Offset is driven
by sustained water stress (`offset_swi`), freezing days (`offset_fdd`), or
short day length (`crit_dayl_stress`) (`biogeochem/PhenologyMod.F90:1268-1303`).
Stress deciduous also computes a "long growing season factor" (`lgsf`) based on
`days_active`, which scales the background litterfall and transfer rates once
the PFT has been active longer than one year
(`biogeochem/PhenologyMod.F90:1323-1338`).

## Crop phenology

`CropPhenology` (`biogeochem/PhenologyMod.F90:1394`) and
`PerennialCropPhenology` (`biogeochem/PhenologyMod.F90:1950`) implement the
AgroIBIS-derived prognostic crop pathway. They run only on the albedo time
step (`doalb`) and only for patches flagged as prognostic crops
(`num_pcropp`, `num_ppercropp`). Planting date is chosen by `CropPlantDate`
(`biogeochem/PhenologyMod.F90:2393`) with vernalization handled by
`vernalization` (`biogeochem/PhenologyMod.F90:2251`). After planting, GDD
accumulation relative to planting drives leaf emergence (`lfemerg`), grain
fill (`grnfill`), and harvest (`mxmat`), with vertical root growth driven by
`huigrain` (the fraction of HUI needed to reach vegetative maturity); the
latter is consumed in `RootDynamicsMod` (see `biogeochem/mortality.md`).
`CropType` in `biogeochem/CropType.F90` holds the per-patch state
(`croplive_patch`, `harvdate_patch`, `gddplant_patch`, …).

## `CNOnsetGrowth`, `CNOffsetLitterfall`, `CNBackgroundLitterfall`, `CNLivewoodTurnover`

These four routines are called unconditionally after all branch tests and
translate the phenology state variables into actual C/N/P fluxes:

- `CNOnsetGrowth` (`biogeochem/PhenologyMod.F90:2587`) pushes transfer-pool
  carbon, nitrogen, and phosphorus into displayed pools over `ndays_on`
  days, distributed linearly in time by decrementing `onset_counter`.
- `CNOffsetLitterfall` (`biogeochem/PhenologyMod.F90:2950`) converts displayed
  leaf and fine-root C/N/P into litter over `ndays_off` days, with the
  previous time step's litterfall flux (`prev_leafc_to_litter`,
  `prev_frootc_to_litter`) used to enforce a consistent ramp.
- `CNBackgroundLitterfall` (`biogeochem/PhenologyMod.F90:3152`) applies the
  PFT-specific `bglfr_leaf` and `bglfr_froot` rates to the displayed pools,
  producing the steady background turnover active in evergreen and stress
  deciduous (via `lgsf`) branches.
- `CNLivewoodTurnover` (`biogeochem/PhenologyMod.F90:3252`) converts a
  fraction `lwtop` (per-second) of livestem and livecroot C/N/P into
  deadstem and deadcroot pools, driving long-term wood biomass growth.

Finally, `CNLitterToColumn` (`biogeochem/PhenologyMod.F90:3371`, public entry)
aggregates all patch-level phenology litter fluxes to the column decomposition
layers using `leaf_prof`, `froot_prof`, `croot_prof`, and `stem_prof`.

## `PhenologyFluxLimitMod` — keeping pools positive

`phenology_flux_limiter` (`biogeochem/PhenologyFluxLimitMod.F90:519`) is called
by the orchestrating BGC driver after phenology has proposed onset/offset and
background fluxes. It constructs a sparse flux network per patch and then
runs `carbon_flux_limiter`, `nitrogen_flux_limiter`, and
`phosphorus_flux_limiter` (`biogeochem/PhenologyFluxLimitMod.F90:588, 822,
1006`) for the main element pools plus, when enabled, C13 and C14 analogues
(`biogeochem/PhenologyFluxLimitMod.F90:562-572`). The limiter uses the
`LSparseMatMod` `flux_correction` operator to scale down any flux that would
drive a state variable negative within one time step. This module is
responsible for ensuring that phenology's storage-to-transfer flush and
background litterfall do not create negative leaf, fine-root, livewood, or
deadwood states after combining with allocation, growth respiration, and
mortality fluxes.

## Satellite phenology (prescribed LAI)

`SatellitePhenologyMod.F90` provides the "SP" alternative where LAI, SAI,
canopy top height and canopy bottom height are prescribed from monthly input
files instead of being computed from prognostic leaf C. It is active when
`use_cn = .false.` (no BGC) or explicitly for FATES-SP
(`use_fates_sp = .true.`); the file gates on
`use_lai_streams` (`biogeochem/SatellitePhenologyMod.F90:19`) and
`use_fates_sp` (`biogeochem/SatellitePhenologyMod.F90:308, 383`).

Key entry points (`biogeochem/SatellitePhenologyMod.F90`):

- `SatellitePhenologyInit` — allocate month-pair buffers
  (`mlai2t`, `msai2t`, `mhvt2t`, `mhvb2t`).
- `interpMonthlyVeg` (`:409`) — decides whether to read two new months.
- `readMonthlyVegetation` (`:565`) — I/O routine for the monthly LAI / SAI /
  height arrays from the surface dataset.
- `SatellitePhenology` (`:299`) — interpolates between the bracketing months
  with time weights `timwt(1)`, `timwt(2)` to produce `tlai(p)`, `tsai(p)`,
  `htop(p)`, `hbot(p)`. If `use_lai_streams = .true.`, `tlai` instead comes
  from `lai_interp` (`:199`) which uses `shr_strdata` to pull from a named
  LAI stream. The routine then applies snow burial via
  `ol = min(max(snow_depth - hbot, 0), htop - hbot)`
  (`biogeochem/SatellitePhenologyMod.F90:375-376`) and sets `elai/esai` to
  zero whenever they fall below 0.05 (`:389-390`). In FATES-SP mode
  (`use_fates_sp`), `elai` and `esai` are intentionally not written here; the
  FATES IFP-indexed fields take over (`:383-386`).

## `VegStructUpdate` — diagnose canopy from C pools

`VegStructUpdate` (`biogeochem/VegStructUpdateMod.F90:31`) runs on the
radiation time step in the prognostic path to update `tlai`, `tsai`, `htop`,
`hbot`, `elai`, and `esai` from current carbon state. It implements:

- Leaf area: `tlai(p) = slatop * leafc` or, when `dsladlai > 0`,
  `tlai(p) = (slatop/dsladlai) * (exp(leafc * dsladlai) - 1)`, i.e. Thornton
  and Zimmerman (2007) Eq 3 (`biogeochem/VegStructUpdateMod.F90:137-142`).
- Stem area: the Zeng et al. 2002 formula
  `tsai(p) = max(alpha*tsai_old + max(tlai_old - tlai, 0), tsai_min)` with
  `tsai_alpha` and `tsai_min` hard-wired by crop vs non-crop and scaled to
  the radiation time step (`biogeochem/VegStructUpdateMod.F90:151-160`).
- Tree / shrub height: a hard-wired allometry
  `htop = (3*deadstemc*taper^2 / (pi*stocking*dwood))^(1/3)` with
  `taper=200` for trees, `taper=10` for shrubs, and
  `stocking=1000 stems/ha`; during accelerated-spinup the dead-stem mass is
  multiplied by `spinup_mortality_factor` before the cube root
  (`biogeochem/VegStructUpdateMod.F90:162-183`). `htop` is capped below
  `forc_hgt_u / (displar + z0mr) - 3 m` to keep it below the forcing height
  and floored at 0.01 m to avoid divide-by-zero after fire mortality.
- Crop height: `htop = ztopmx * min(tlai/(laimx-1), 1)^2` with running peak
  `htmx` and a stubble override after harvest
  (`biogeochem/VegStructUpdateMod.F90:197-221`).
- Grass height: `htop = max(0.25, tlai * 0.25)` with the same upper cap.
- Snow burial: identical to `SatellitePhenology` — fraction buried by snow
  depth, with short-vegetation (shrubs and grasses) using the
  Wang and Zeng (2007) parametrization that allows partial burial between
  `hbot` and `htop` (`biogeochem/VegStructUpdateMod.F90:249-267`).

## BeTR variant

`CNPhenologyBeTRMod.F90` is a near-copy of `PhenologyMod.F90` used when ELM is
coupled to the BeTR reactive-transport tracer system. It exposes the same
public interfaces (`CNPhenologyInit`, `CNPhenology`, `readCNPhenolBeTRParams`
at `biogeochem/CNPhenologyBeTRMod.F90:48-50`) and the same internal routines
(`CNEvergreenPhenology`, `CNSeasonDecidPhenology`, `CNStressDecidPhenology`,
`CropPhenology`, `CNOnsetGrowth`, `CNOffsetLitterfall`, ...). Differences are
limited to the specific tracer state objects it updates via the `CNBeTR`
indexing. Both paths produce the same C/N/P phenology semantics; the BeTR
module is selected by the higher-level ecosystem-dynamics driver, not by a
phenology-level flag.

## Control-flag summary

| Flag | File | Effect on phenology |
|---|---|---|
| `use_cn` | `main/elm_varctl.F90:354` | Enables `PhenologyMod.F90` prognostic path. |
| `use_fates` | `main/elm_varctl.F90:222` | Turns off ELM-native phenology; FATES owns the leaf habit. |
| `use_fates_sp` | `main/elm_varctl.F90:233` | Satellite phenology inside FATES. Skips `elai`/`esai` overwrite in `SatellitePhenology`. |
| `use_lai_streams` | `main/elm_varctl.F90:252` | In SP mode, pulls `tlai` from a named LAI stream rather than the surface dataset. |
| `use_crop` | `main/elm_varctl.F90:356` | Enables prognostic crop pathway (`crop_prog`, `CropPhenologyInit`). |
| `nu_com` | `main/elm_varctl.F90` | Selects CNP vs RD nutrient competition; only in RD mode does the stress-deciduous precipitation gate (`cumprec_onset`) run. |

## Contrast with FATES phenology

ELM-native phenology and FATES phenology implement the same biological
concepts (cold and stress deciduous onset and offset, background litterfall,
live-wood turnover), but the implementations are disjoint code paths. FATES
has its own cohort-resolved GDD accumulator, its own onset and offset
counters, and its own set of phenology parameters on the FATES parameter
file. Consequently, switching between `use_cn` and `use_fates` replaces the
entire phenology subsystem: the parameters documented here
(`crit_dayl`, `crit_dayl_stress`, `fstor2tran`, `ndays_on`, `ndays_off`,
`crit_onset_fdd`, `crit_offset_swi`, `lwtop`, `cumprec_onset`) do not apply
when FATES is active. For the FATES phenology pathway, see the FATES
codebase wiki.
