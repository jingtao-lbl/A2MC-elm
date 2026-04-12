---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Canopy Water, Temperature, and Support Utilities

This document covers the patch-level canopy hydrology pipeline — interception, throughfall, wet fraction, dew, irrigation bypass, surface-water fraction — plus the ground-temperature initialization step, the `canopystate_type` container, and a handful of shared utilities (saturation vapor pressure, root profile, daylength) that feed the larger flux and BGC machinery.

| Module | Role |
|---|---|
| `CanopyHydrologyMod` (`biogeophys/CanopyHydrologyMod.F90`) | Interception, throughfall, canopy-runoff, `fwet`, `fdry`, `frac_h2osfc`, new-snow layer initialization, irrigation delivery |
| `CanopyStateType` (`biogeophys/CanopyStateType.F90`) | `canopystate_type` container for LAI/SAI (actual and snow-buried), sunlit/shaded profiles, canopy height, displacement, leaf-width, vegetation water potential |
| `CanopyTemperatureMod` (`biogeophys/CanopyTemperatureMod.F90`) | First pass at ground-surface humidity and ground temperature before the canopy-flux Newton iteration; called from `Biogeophysics1` |
| `RootBiophysMod` (`biogeophys/RootBiophysMod.F90`) | `init_vegrootfr` — Zeng (2001) two-parameter exponential root profile |
| `QSatMod` (`biogeophys/QSatMod.F90`) | Flatau et al. (1992) polynomial approximation for saturation vapor pressure and its `T` derivative |
| `DaylengthMod` (`biogeophys/DaylengthMod.F90`) | Elemental `daylength(lat, decl)` function and gridcell update routines used by CN/CNP phenology |

## Public subroutines

| Subroutine | Purpose |
|---|---|
| `CanopyHydrology_readnl(NLFilename)` (`biogeophys/CanopyHydrologyMod.F90:53`) | Reads the `clm_canopyhydrology_inparm` namelist block |
| `CanopyHydrology(bounds, num_nolakec, filter_nolakec, num_nolakep, filter_nolakep, atm2lnd_vars, canopystate_vars, aerosol_vars)` (`biogeophys/CanopyHydrologyMod.F90:100`) | Main hydrology driver — interception, throughfall, dew accumulation, surface water, new-snow capping, irrigation, and the `FracWet` / `FracH2OSfc` sub-calls |
| `CanopyTemperature(bounds, num_nolakec, filter_nolakec, num_nolakep, filter_nolakep, atm2lnd_vars, canopystate_vars, soilstate_vars, frictionvel_vars, energyflux_vars)` (`biogeophys/CanopyTemperatureMod.F90:44`) | Computes `qg`, `qred`, `t_grnd`, roughness lengths, and the effective `thm` before `CanopyFluxes` runs |
| `init_vegrootfr(bounds, nlevsoi, nlevgrnd, nlev2bed, rootfr)` (`biogeophys/RootBiophysMod.F90:34`) | Populates the per-patch, per-layer root fraction using the Zeng (2001) profile |
| `init_rootprof()` (`biogeophys/RootBiophysMod.F90:23`) | Selects the root profile method (hardcoded to `zeng_2001_root`) |
| `QSat(T, p, es, esdT, qs, qsdT)` (`biogeophys/QSatMod.F90:63`) | Saturation vapor pressure and saturation specific humidity with temperature derivatives |
| `rhoSat(T, rho, rhodT)` (`biogeophys/QSatMod.F90:129`) | Saturated vapor density variant |
| `daylength(lat, decl)` (`biogeophys/DaylengthMod.F90:28`) | Returns daylength in seconds for given latitude and solar declination (both radians) |
| `InitDaylength(bounds, declin, declinm1)` (`biogeophys/DaylengthMod.F90:85`) | Initialize current and previous daylength fields |
| `UpdateDaylength(bounds, declin)` (`biogeophys/DaylengthMod.F90:120`) | Daily update of `dayl_patch` and `prev_dayl_patch` on the gridcell type |

Private: `FracWet` (`CanopyHydrologyMod.F90:721`), `FracH2OSfc` (`CanopyHydrologyMod.F90:776`), `zeng2001_rootfr` (`RootBiophysMod.F90:78`).

## CanopyHydrology driver

`CanopyHydrology` (`biogeophys/CanopyHydrologyMod.F90:100`) runs once per time step, **before** `CanopyFluxes`, to update the canopy water store `h2ocan` and to deliver precipitation (minus interception) to the ground. In-source description at `CanopyHydrologyMod.F90:105-113`:

> Calculation of
>  (1) water storage of intercepted precipitation
>  (2) direct throughfall and canopy drainage of precipitation
>  (3) the fraction of foliage covered by water and the fraction of foliage that is dry and transpiring.
>  (4) snow layer initialization if the snow accumulation exceeds 10 mm.

### Interception and throughfall

For vegetated soil/crop/wetland patches where `frac_veg_nosno(p) == 1` and precipitation is falling (`CanopyHydrologyMod.F90:294-335`):

```
fracsnow = forc_snow / (forc_snow + forc_rain)
fracrain = forc_rain / (forc_snow + forc_rain)

! Max canopy water storage [mm]
h2ocanmx = dewmx(p) * (elai(p) + esai(p))

! Coefficient of interception (fraction of incident precip intercepted)
fpi = 0.25 * (1 - exp(-0.5*(elai + esai)))       ! capped at 25 %

! Direct throughfall [mm/s]
qflx_through_snow = forc_snow * (1 - fpi)
qflx_through_rain = forc_rain * (1 - fpi)

! Intercepted precipitation [mm/s]
qflx_prec_intr    = (forc_snow + forc_rain) * fpi

! Canopy water update
h2ocan = max(0, h2ocan + dtime * qflx_prec_intr)

! Check for excess over max capacity
xrun = (h2ocan - h2ocanmx) / dtime
if (xrun > 0) then
   qflx_candrip = xrun
   h2ocan       = h2ocanmx
end if
```

`dewmx` (maximum allowed dew, mm) is a PFT parameter exposed on `canopystate_type::dewmx_patch` and read from the vegetation-properties file during initialization. The `(LAI+SAI)` dependence implicitly treats rain and snow storage capacity as equal, an approximation acknowledged in the in-source comment at `CanopyHydrologyMod.F90:300-304`.

### Precipitation onto the ground

`qflx_prec_grnd_rain` and `qflx_prec_grnd_snow` depend on whether the patch is vegetated or not (`CanopyHydrologyMod.F90:351-369`):

- **Unvegetated** (`frac_veg_nosno == 0`): rain and snow fall directly to the ground.
- **Vegetated**: ground-reaching rain = direct throughfall + `qflx_candrip*fracrain`; same pattern for snow. `qflx_leafdrip = qflx_candrip * fracrain` — this is the liquid-phase canopy drip used by some aerosol scavenging calculations.
- **Urban sunwall / shadewall**: no interception, no throughfall — all inputs are zero, because these column types do not see precipitation.

### Irrigation delivery

When `n_irrig_steps_left(p) > 0`, `qflx_irrig = irrig_rate` and the counter decrements (`CanopyHydrologyMod.F90:372-378`). Irrigation water **bypasses the canopy** and is added directly to the ground in the subsequent water-balance code. With `tw_irr = .true.` (two-way coupling to MOSART), the routine distinguishes surface-water irrigation (`qflx_surf_irrig`, arriving on a time-step lag) from groundwater pumping irrigation (`qflx_grnd_irrig`, same time step as demand), and optionally tops up any deficit via `qflx_over_supply`. The trigger time and maximum duration are enforced by `CanopyFluxes` (`irrig_start_time`, `irrig_length` at `CanopyFluxesMod.F90:143-151`).

### Dew and evaporation reconciliation

`CanopyHydrology` does not compute evaporation — that happens in `CanopyFluxes` once `t_veg` is known. What `CanopyHydrology` does is **initialize** `h2ocan` by accumulating intercepted precipitation and dew. `CanopyFluxes` later subtracts `qflx_evap_veg * dtime` from `h2ocan`, clipping at zero.

### New-snow layer initialization

When a patch without snow layers accumulates more than 10 mm of incremental SWE in a single step, `CanopyHydrology` (via a call to `NewSnowBulkDensity` from `SnowHydrologyMod`) triggers creation of the first snow layer with the appropriate fresh-snow density (see [snow.md](snow.md) for the density formulation and subsequent layer management).

## Canopy wet and dry fractions — `FracWet`

`FracWet` (`biogeophys/CanopyHydrologyMod.F90:721`) partitions leaf + stem area into "wet" (intercepted water or snow on the surface) and "dry" (available to transpire) fractions:

```
vegt  = frac_veg_nosno * (elai + esai)
fwet  = min( ((1/dewmx)/vegt * h2ocan)^(2/3), 1 )          ! Eq. 7.64 CLM4 tech note
fdry  = (1 - fwet) * elai / (elai + esai)
```

(`biogeophys/CanopyHydrologyMod.F90:754-770`). `fwet` is assigned to `veg_ws%fwet` and `fdry` to `veg_ws%fdry`. Both are zero when the patch has no non-snow vegetation.

`fwet` has three major downstream uses:
1. **Radiation**: `TwoStream` in `SurfaceAlbedoMod` blends leaf optical properties with bulk snow when `t_veg <= tfrz`, using `fwet` as the snow-cover proxy (`biogeophys/SurfaceAlbedoMod.F90:1314-1322`, see [radiation.md](radiation.md)).
2. **Canopy fluxes**: `rpp` (the fraction of potential evaporation actually evaporated from wet surfaces) and `rppdry` (the portion actually transpired) in `CanopyFluxes` are computed from `fwet`/`fdry`, setting the trade-off between transpiration and interception-loss evaporation.
3. **BGC**: Wet-leaf fraction affects some dry-deposition and nitrogen-fixation parameterizations.

## Surface water fraction — `FracH2OSfc`

`FracH2OSfc` (`biogeophys/CanopyHydrologyMod.F90:776`) computes the fraction `frac_h2osfc` of each soil column covered by ponded surface water, given `h2osfc` and a microtopography `sigma`. It is called from `CanopyHydrology` and solves iteratively for the surface-water depth `d` that satisfies

```
h2osfc = sigma * [d * erf(d/(sigma*sqrt(2))) + sigma/sqrt(2*pi) * exp(-d^2/(2*sigma^2))] / sqrt(2*pi) ...
```

using a Newton step on `(fd, dfdd)`. The optional `no_update` argument lets callers query `frac_h2osfc` without mutating the state. The resulting `frac_h2osfc` is used by the three-way ground-surface partitioning (snow, bare soil, surface water) in `CanopyFluxes`, `SoilFluxes`, and `CanopyTemperature`.

## `CanopyTemperature` — ground-surface pre-step

`CanopyTemperature` (`biogeophys/CanopyTemperatureMod.F90:44`) is the pre-flux step historically known as `Biogeophysics1`. In-source description (`CanopyTemperatureMod.F90:48-68`):

> Leaf temperature
> Foliage energy conservation is given by the foliage energy budget equation:
>     Rnet - Hf - LEf = 0
> The equation is solved by Newton-Raphson iteration, in which this iteration includes the calculation of the photosynthesis and stomatal resistance, and the integration of turbulent flux profiles. The sensible and latent heat transfer between foliage and atmosphere and ground is linked by the equations:
>     Ha = Hf + Hg and Ea = Ef + Eg

Despite that comment, the actual Newton-Raphson loop lives in `CanopyFluxes`; `CanopyTemperature` performs the **pre-computation** that must happen before `CanopyFluxes` and `BareGroundFluxes` can start:

1. **`qg` (ground specific humidity)** — uses `QSat` to get saturation at `t_grnd`, then scales by `qred` (soil surface relative humidity from the Clapp-Hornberger matric potential on the top soil layer):
   ```
   qsatg, dqsatg/dT   = QSat(t_grnd, forc_pbot)
   qred               = exp(psit * gravity / (rwat * t_grnd))
   qg                 = qred * qsatg
   ```
   For snow, `qred = 1` and the ground is treated as a moist surface at `t_snow`.

2. **Roughness lengths** — sets `z0mg`, `z0hg`, `z0qg` based on `zlnd` (soil), `zsno` (snow), or urban-specific values; for vegetated patches they become `z0mv`, `z0hv`, `z0qv` after accounting for displacement height `displa` and canopy height `htop`.

3. **Longwave incident on the ground under the canopy** and the `air`/`bir`/`cir` coefficients that linearize the canopy longwave balance — used as constants throughout the `CanopyFluxes` Newton iteration.

4. **`thm`** — virtual potential temperature at the forcing height, corrected for the difference in heights `forc_hgt_t` and `forc_hgt_u`.

After `CanopyTemperature` returns, `CanopyFluxes` (and, in parallel, `BareGroundFluxes`, `UrbanFluxes`, `LakeFluxes`) can run using the stored `qg`, `t_grnd`, and roughness lengths.

## Root profile — `init_vegrootfr`

`RootBiophysMod::init_vegrootfr` (`biogeophys/RootBiophysMod.F90:34`) populates `rootfr(p, 1:nlevgrnd)` at initialization time using the Zeng (2001) two-parameter model:

```
Y(d) = 1 - 0.5 * (exp(-a*d) + exp(-b*d))          ! cumulative root fraction above depth d
```

implemented per layer as (`biogeophys/RootBiophysMod.F90:119-123`):

```
rootfr(p,lev) = 0.5 * ( exp(-a * zi(c,lev-1))
                       + exp(-b * zi(c,lev-1))
                       - exp(-a * zi(c,lev))
                       - exp(-b * zi(c,lev)) )
```

with `roota_par(pft)` and `rootb_par(pft)` read from the parameter file, and `zi(c,lev)` being the column's layer-interface depth. For FATES vegetation, `init_vegrootfr` skips the patch (`RootBiophysMod.F90:115` — `if (...) .and. .not. veg_pp%is_fates(p)`), and FATES populates its own root profile during initialization.

When `use_var_soil_thick = .true.` and the bedrock level `nlev2bed` is shallower than `nlevsoi`, `init_vegrootfr` **renormalizes** `rootfr` so the total over the non-bedrock layers sums to 1, preventing roots from being placed into the impermeable bedrock layers (`biogeophys/RootBiophysMod.F90:132-138`).

Currently only `zeng_2001_root` is implemented; placeholder branches for `jackson_1996_root` and `schenk_jackson_2002_root` exist but `endrun` when selected (`RootBiophysMod.F90:60-72`).

## Saturation vapor pressure — `QSat`

`QSat` (`biogeophys/QSatMod.F90:63`) provides the Flatau et al. (1992, *J. Appl. Meteor.* 31, 1507–1513) 8th-order polynomial approximation for saturation vapor pressure `es(T)` and its derivative `d es/dT`. Two polynomial branches are used depending on sign of `T_limit = T - 273.15`:

```
if (td >= 0) then                  ! Liquid-water saturation (above 0 C)
   es   = a0 + td*(a1 + td*(a2 + ... + td*a8)) ...                ! QSatMod.F90:96-100
   esdT = b0 + td*(b1 + td*(b2 + ... + td*b8)) ...
else                               ! Ice saturation (below 0 C)
   es   = c0 + td*(c1 + td*(c2 + ... + td*c8))                    ! QSatMod.F90:103-107
   esdT = d0 + td*(d1 + td*(d2 + ... + td*d8))
end if
```

Both branches are clamped to `-75 <= T_limit <= 100` C (`QSatMod.F90:91-92`). Units are Pa for `es` and Pa/K for `esdT`. The specific humidity output (`QSatMod.F90:116-121`) is the standard form using the ratio of molecular weights (0.622):

```
vp    = 1 / (p - 0.378 * es)
qs    = es * 0.622 * vp
qsdT  = esdT * 0.622 * vp^2 * p
```

`QSat` is called from:
- `CanopyTemperature` — to seed `qg` and `dqg/dT` at the ground
- `CanopyFluxes` — once before the iteration and again after each Newton step to rebuild `qsatl(p)` at the new leaf temperature (`biogeophys/CanopyFluxesMod.F90:1102`)
- `BareGroundFluxes`, `UrbanFluxes`, `LakeFluxes`, `SoilFluxes` — each for its own surface

This makes `QSat` by far the most frequently-called low-level utility in the biogeophysics layer; it is intentionally kept as a pure, `$acc routine seq` subroutine so it can run on the device.

`rhoSat` (`biogeophys/QSatMod.F90:129`) is a variant that returns saturation vapor density `rho = es / (rwat * T)` with its `T` derivative — used in a few specialized lake and snow places but not in the canopy Newton loop.

## Daylength — `DaylengthMod`

`DaylengthMod` provides the geometric daylength used by the CN/CNP phenology. The central function is (`biogeophys/DaylengthMod.F90:28-81`):

```fortran
elemental real(r8) function daylength(lat, decl)
   ! both inputs in radians
   temp = -sin(lat) * sin(decl) / (cos(lat) * cos(decl))
   temp = clamp(temp, -1, 1)
   daylength = 2 * secs_per_radian * acos(temp)
end function
```

with `secs_per_radian = 13750.9871` — the number of seconds per radian of hour angle (86400 / (2π)). Latitudes within `epsilon` of ±π/2 are offset slightly to avoid `cos(lat) = 0` (`DaylengthMod.F90:53-57`).

`UpdateDaylength(bounds, declin)` (`DaylengthMod.F90:120`) is called daily from the main time-step loop. It iterates over all gridcells and stores current and previous day's daylength on `grc_pp`, which are then used by `CNPhenology` to compute day-length accumulation and trigger leaf-on for temperate and boreal deciduous types.

## `canopystate_type` container

Declared at `biogeophys/CanopyStateType.F90:35`, the `canopystate_type` holds everything that is "the canopy" — structural state that persists across time steps and is read by radiation, fluxes, and BGC:

- **Vegetation area**: `tlai_patch`, `tsai_patch` (raw, no snow burial), `elai_patch`, `esai_patch` (after burial), `tlai_hist_patch`, `tsai_hist_patch` (satellite-phenology mode).
- **Sunlit/shaded split**: `laisun_patch`, `laisha_patch`, `laisun_z_patch(:,:)`, `laisha_z_patch(:,:)`, `fsun_patch`, `fsun24_patch`, `fsun240_patch` (24-hr and 240-hr running means used by the nitrogen-allocation code).
- **Canopy architecture**: `htop_patch`, `hbot_patch`, `displa_patch`, `dleaf_patch`, `frac_veg_nosno_patch`, `frac_veg_nosno_alb_patch`.
- **Surface hydraulics**: `dewmx_patch`, `lbl_rsc_h2o_patch` (laminar boundary layer resistance for water over dry leaf), `vegwp_patch(:,nvegwcs)` (vegetation water matric potential when `use_hydrstress = .true.`).
- **Permafrost active layer**: `alt_col`, `alt_indx_col`, `altmax_col`, `altmax_lastyear_col`, `altmax_indx_col`, `altmax_lastyear_indx_col` (used by `ActiveLayerMod`).

Two module-level logicals, `perchroot` and `perchroot_alt` (`biogeophys/CanopyStateType.F90:25-29`), switch how `btran` treats frozen soil:

- `perchroot = .false.`, `perchroot_alt = .false.` — the standard root-weighted `btran` over all layers.
- `perchroot = .true.` — exclude frozen layers from the root-weighting before normalization.
- `perchroot_alt = .true.` — use the two-year rolling active layer (`altmax`) as the root domain.

Both are set from namelist in `SoilMoistStressMod::set_perchroot_opt` (`biogeophys/SoilMoistStressMod.F90:57`) and consumed in `calc_root_moist_stress` (see [canopy_fluxes.md](canopy_fluxes.md)).

## Cross-links

- `dewmx`, `elai`, `esai`, `fwet`, `fdry` are produced here and consumed in [radiation.md](radiation.md) (two-stream leaf property blending) and [canopy_fluxes.md](canopy_fluxes.md) (potential-evaporation split).
- `h2ocan` caps the interception evaporation flux in `CanopyFluxesMod.F90:1081-1092`.
- `qflx_prec_grnd_snow` flows into [snow.md](snow.md) as the input to `SnowWater`.
- `rootfr` is used by `SoilMoistStressMod::calc_root_moist_stress` (see [canopy_fluxes.md](canopy_fluxes.md)) to weight the `btran` sum and distribute the transpiration sink across soil layers in Richards' equation.
- `dayl_patch` from `DaylengthMod` is used by CN/CNP phenology in `biogeochem/CNPhenologyMod.F90` and A2MC's FATES phenology calibration workflow (see `use_cases/Kougarok/memory/gained_knowledge/discoveries.json` for the corresponding mechanistic insights).
- `QSat` is the lowest-level utility shared across every surface-flux driver.
