---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Soil Temperature and the Thermal Column

This document covers the subsurface thermal column in ELM, the heat conduction solver, phase change, permafrost/active layer tracking (with new ice-wedge polygon and excess-ice extensions when `use_polygonal_tundra = .true.`), the optional T- and density-dependent snow thermal conductivity (when `use_T_rho_dependent_snowthk = .true.`), and the linear algebra utilities used to invert the discretized heat equation.

## Scope

- `biogeophys/SoilTemperatureMod.F90` (4840 lines at `d40b8431`, up from 4783 at `60d9aad`) — the Crank-Nicholson heat diffusion solver. Adds the T-rho snow conductivity branch.
- `biogeophys/TemperatureType.F90` — the `temperature_type` derived type holding column/patch/landunit temperatures.
- `biogeophys/ActiveLayerMod.F90` (266 lines at `d40b8431`, up from ~158 at `60d9aad`) — active layer thickness with polygonal-tundra extensions and excess-ice subsidence.
- `biogeophys/TridiagonalMod.F90` — scalar and multi-RHS tridiagonal solvers and the coupled `Trisim` solver. Unchanged at `d40b8431`.
- `biogeophys/BandDiagonalMod.F90` — LAPACK `dgbsv` band solver wrapper for pentadiagonal systems. Unchanged.

## Governing equation

ELM solves 1D vertical heat conduction in the snow/standing-water/soil column

```
    dT     d        dT
 Cv --- = -- ( k  ----- )  +  S(z)
    dt    dz        dz
```

where `Cv` is the volumetric heat capacity `[J m^-3 K^-1]`, `k` is thermal conductivity `[W m^-1 K^-1]`, and `S` represents absorbed shortwave inside snow/soil layers. Discretized with the Crank-Nicholson method, this becomes a tridiagonal (or banded) system solved every time step (`biogeophys/SoilTemperatureMod.F90:152-707`). Boundary conditions:

- Top: `F = Rnet - Hg - LEg` (net radiation minus ground sensible and latent heat).
- Bottom: `F = 0` at the base of the soil column (zero heat flux).

Time stepping uses the Crank-Nicholson factor `cnfac` (from `elm_varcon`), which weights the implicit versus explicit contributions to diffusive fluxes at the interfaces.

## Top-level driver: `SoilTemperature`

Signature (`biogeophys/SoilTemperatureMod.F90:152-154`):

```
subroutine SoilTemperature(bounds, num_urbanl, filter_urbanl, num_nolakec, filter_nolakec,
     atm2lnd_vars, urbanparams_vars, canopystate_vars,
     solarabs_vars, soilstate_vars, energyflux_vars)
```

The routine operates over the non-lake column filter and produces the updated `col_es%t_soisno(c, -nlevsno+1:nlevgrnd)` array plus `t_h2osfc`, `t_grnd`, `xmf`, and `t_building`. The internal call chain:

1. `SoilThermProp` — compute `tk`, `cv`, and `tk_h2osfc` (`biogeophys/SoilTemperatureMod.F90:812-1079`).
2. `ComputeGroundHeatFluxAndDeriv` — net heat flux `hs` and derivative `dhsdT` at the upper boundary (`biogeophys/SoilTemperatureMod.F90:1696-1954`).
3. `ComputeHeatDiffFluxAndFactor` — heat-diffusion flux `fn` at interfaces and pre-factor `fact = dt/Cv` (`biogeophys/SoilTemperatureMod.F90:1957-2048`).
4. `SetRHSVec` and `SetMatrix` — assemble the banded Crank-Nicholson system for urban and non-urban columns separately (`biogeophys/SoilTemperatureMod.F90:2051-2172`, plus a family of variants `SetRHSVec_Snow`, `SetRHSVec_Soil`, `SetRHSVec_SoilUrban`, etc.).
5. `SolveTemperature` — calls `BandDiagonal` (`biogeophys/SoilTemperatureMod.F90:712-809`).
6. `PhaseChange_beta` — latent-heat based phase change correction (private helper, declared at `SoilTemperatureMod.F90:122`).
7. `PhaseChangeH2osfc` — handles freezing of surface ponded water (`biogeophys/SoilTemperatureMod.F90:1082-1290`).

A namelist-selectable PETSc thermal model (`petsc_thermal_model = 1`) is available via `init_soil_temperature` (`biogeophys/SoilTemperatureMod.F90:134-149`); by default `thermal_model = default_thermal_model = 0`.

## Thermal properties: `SoilThermProp`

Located at `biogeophys/SoilTemperatureMod.F90:812-1079`. Three property calculations:

### Soil thermal conductivity (Farouki 1981 / Johansen)

For unfrozen soils the Kersten number is `dke = max(0, log10(satw) + 1)`, for frozen soils `dke = satw`. The saturated conductivity is `dksat = tkmg * tkwat^(fl*watsat) * tkice^((1-fl)*watsat)`, and the final layer value is

```
thk(c,j) = dke*dksat + (1 - dke)*tkdry(c,j)
```

(`SoilTemperatureMod.F90:937`). Urban walls, roofs and roads use separately-read `tk_wall`, `tk_roof`, `tk_improad` from `urbanparams_vars`.

### Snow thermal conductivity (Jordan 1991 or T-rho-dependent)

At `d40b8431`, `SoilThermProp` selects between two snow thermal-conductivity formulations based on `use_T_rho_dependent_snowthk` (`SoilTemperatureMod.F90:955-987`). Default off; default behavior matches the wiki at `60d9aad` (Jordan 1991).

```fortran
if (use_T_rho_dependent_snowthk) then
   if (snl(c)+1 < 1 .AND. (j >= snl(c)+1) .AND. (j <= 0)) then
      bw(c,j) = (h2osoi_ice(c,j) + h2osoi_liq(c,j)) / (frac_sno(c) * dz(c,j))

      do i = 1, 5
         k_snw_vals(i) = k_snw_coe1(i) * (bw(c,j)/rho_ice)**2 &
                       - k_snw_coe2(i) * (bw(c,j)/rho_ice)   &
                       + k_snw_coe3(i)
      end do

      ! interpolate in T between adjacent anchors
      do i = 1, size(k_snw_tmps) - 1
         if (k_snw_tmps(i) <= t_soisno(c,j) .and. t_soisno(c,j) <= k_snw_tmps(i+1)) then
            thk(c,j) = k_snw_vals(i) + (t_soisno(c,j) - k_snw_tmps(i)) &
                                     * (k_snw_vals(i+1) - k_snw_vals(i)) &
                                     / (k_snw_tmps(i+1) - k_snw_tmps(i))
         end if
      end do
      ! edge-case clamping
      if (t_soisno(c,j) < k_snw_tmps(1))    thk(c,j) = k_snw_vals(1)
      if (t_soisno(c,j) > k_snw_tmps(5))    thk(c,j) = k_snw_vals(5)
   end if
else
   ! Original Jordan (1991) formulation
   if (snl(c)+1 < 1 .AND. (j >= snl(c)+1) .AND. (j <= 0)) then
      bw(c,j) = (h2osoi_ice(c,j) + h2osoi_liq(c,j)) / (frac_sno(c) * dz(c,j))
      thk(c,j) = tkair + (7.75e-5*bw + 1.105e-6*bw^2) * (tkice - tkair)
   end if
end if
```

The five temperature anchor points and the per-anchor density-dependent quadratic coefficients are module-scope `data` arrays at `SoilTemperatureMod.F90:864-867`:

```
k_snw_tmps = (/223, 248, 263, 268, 273/)        ! K
k_snw_coe1 = (/2.564, 2.172, 1.985, 1.883, 1.776/)
k_snw_coe2 = (/-0.059, 0.015, 0.073, 0.107, 0.147/)
k_snw_coe3 = (/0.0205, 0.0252, 0.0336, 0.0386, 0.0455/)
```

This is calibration-relevant for permafrost / cold-snow simulations and is a useful tuning lever for A2MC at sites with significant cold-season snow regimes.

### Interface conductivity

Uses the harmonic-mean flux-matching formula `tk(c,j) = thk(c,j)*thk(c,j+1)*(z(j+1)-z(j)) / (thk(c,j)*(z(j+1)-zi(j)) + thk(c,j+1)*(zi(j)-z(j)))` for non-urban columns. Urban walls/roofs/impervious-road use separately-read tabulated conductivities.

### Volumetric heat capacity

```
cv(c,j) = csol(c,j)*(1 - watsat(c,j))*dz(c,j)
        + h2osoi_ice(c,j)*cpice + h2osoi_liq(c,j)*cpliq
```

(`SoilTemperatureMod.F90:1046`). Special cases: urban walls/roofs/impervious-road use tabulated `cv_*` values; wetland and ice columns use the pure water/ice heat capacity. The branch at `SoilTemperatureMod.F90:680-684` uses `col_pp%is_soil(c) .or. col_pp%is_crop(c)` (the new accessor pattern).

## Flux and factor assembly: `ComputeHeatDiffFluxAndFactor`

`biogeophys/SoilTemperatureMod.F90:1957-2048`. For each interface below a snow-layer column this routine computes:

- `fact(c,j) = dtime / cv(c,j)`.
- `fn(c,j) = tk(c,j)*(t_soisno(c,j+1) - t_soisno(c,j)) / (z(c,j+1) - z(c,j))`.
- At the top soil layer a capacitance correction is applied with `capr` (CLM capacity-ratio constant from `elm_varcon`).
- Urban sunwall/shadewall/roof columns use a prescribed internal building temperature as the bottom boundary, yielding `fn(c,nlevurb) = tk * (t_building - cnfac*t_soisno) / (zi-z)` (`SoilTemperatureMod.F90:2024`).
- Non-urban bottom layer uses `fn(c,nlevgrnd) = eflx_bot(c)` — a prescribed geothermal flux from `col_ef%eflx_bot`.

## Phase change

`PhaseChange_beta` (private; declared at `SoilTemperatureMod.F90:122`) applies the enthalpy-based freeze/thaw correction after each temperature update. It diagnoses `imelt_col(c,j)` (0/1/2 for none/melt/freeze — stored on `temperature_type`) and decrements ice or liquid pools by `xmf`, the latent heat consumed during the step. `PhaseChangeH2osfc` (`SoilTemperatureMod.F90:1082-1290`) handles freezing of standing surface water and moves the newly-formed ice to the bottom snow layer when appropriate.

## Permafrost and the active layer: `ActiveLayerMod`

`biogeophys/ActiveLayerMod.F90` defines the single public routine `alt_calc` (`ActiveLayerMod.F90:30-264`, 235 lines of body, up from ~110 at `60d9aad`). The routine scans `t_soisno(c, nlevgrnd)` from the bottom upward and finds the first unfrozen layer (`ActiveLayerMod.F90:139-144`). The active-layer depth is then a linear interpolation between the lowest thawed node and the layer below it to find where `T = TKFRZ`:

```
alt(c) = z1 + (t1 - TKFRZ)*(z2 - z1) / (t1 - t2)
```

(`ActiveLayerMod.F90:152`). Annual-maximum rollover happens on January 1 for northern columns and July 1 for southern columns (`ActiveLayerMod.F90:99-123`).

### New tracked maxima at d40b8431

The routine maintains six column-level outputs on `canopystate_vars` at `d40b8431` (was three at `60d9aad`):

| Field | Updated when | Reset behavior |
|---|---|---|
| `alt_col`, `alt_indx_col` | Every time step | — |
| `altmax_col`, `altmax_indx_col` | Whenever `alt > altmax` | Zeroed annually (Jan 1 NH, Jul 1 SH) |
| `altmax_lastyear_col`, `altmax_lastyear_indx_col` | Annual rollover from `altmax` | — |
| **`altmax_1989_col`, `altmax_1989_indx_col`** *(new)* | When `year == 1989` and `use_polygonal_tundra` (`ActiveLayerMod.F90:178-181`) | — (frozen at the 1989 baseline) |
| **`altmax_ever_col`, `altmax_ever_indx_col`** *(new)* | Whenever `alt > altmax_ever` (`ActiveLayerMod.F90:165-173`) | Set to zero in spinup mode (`spinup_state /= 0`) |

The `altmax_1989` baseline is a hard-coded reference year for tracking changes in polygonal ground; `altmax_ever` is the all-time maximum thaw depth since simulation start. Both are restart-wired in `CanopyStateType.F90:619-630`.

### Excess-ice and ice-wedge polygon physics (`use_polygonal_tundra`)

When `use_polygonal_tundra = .true.`, `alt_calc` runs a substantially extended block (`ActiveLayerMod.F90:175-259`) that tracks excess-ice melt, layer subsidence, and ice-wedge polygon (IWP) microtopography. The relevant column-level state lives on `col_ws` (defined in `ColumnDataType.F90:175-180`):

| Field | Shape | Meaning |
|---|---|---|
| `excess_ice` | `(:, nlevgrnd)` | Per-layer excess ground-ice content (0 to 1) |
| `frac_melted` | `(:, nlevgrnd)` | Fraction of each layer that has ever thawed (0 to 1) — used to track non-recurring excess-ice removal |
| `iwp_microrel` (alias `rmax`) | `(:)` | IWP microtopographic relief [m] |
| `iwp_exclvol` (alias `vexc`) | `(:)` | IWP excluded volume [m] |
| `iwp_ddep` (alias `ddep`) | `(:)` | IWP depression depth [m] |
| `iwp_subsidence` (alias `subsidence`) | `(:)` | Cumulative IWP ground subsidence [m] |

The mechanics: each step `alt_calc` builds a `melt_profile(j)` array by checking, for each layer at or above `k_frz`, whether the active-layer thickness `alt(c)` has reached deeper than `altmax_ever(c)` and updating `frac_melted(c,j)`. Excess ice in newly-thawed sublayers is liberated and added to the per-layer `melt_profile`. Subsidence accumulates the integral of `melt_profile * dzsoi` only when `year >= 1989 .and. altmax_ever(c) >= altmax_1989(c)` (`ActiveLayerMod.F90:233-235`), and is clamped at 0.4 m (`:238`). Polygon-type-specific microtopography updates follow at `ActiveLayerMod.F90:241-258`:

```fortran
if (lun_pp%ispolygon(col_pp%landunit(c))) then
   if (polygontype == ilowcenpoly) then    ! low-centered polygons
      rmax = 0.4
      vexc = 0.2
      ddep = max(0.05, 0.15 - 0.25*subsidence)
   elseif (polygontype == iflatcenpoly) then  ! flat-centered
      rmax = min(0.4,  0.1  + 0.75*subsidence)
      vexc = min(0.2,  0.05 + 0.375*subsidence)
      ddep = min(0.05, 0.01 + 0.1*subsidence)
   elseif (polygontype == ihighcenpoly) then  ! high-centered
      rmax = 0.4
      vexc = 0.2
      ddep = 0.05
   endif
endif
```

`ilowcenpoly`, `iflatcenpoly`, `ihighcenpoly` are imported from `landunit_varcon` (`ActiveLayerMod.F90:17`).

## Temperature state: `temperature_type`

Defined at `biogeophys/TemperatureType.F90:23-`. Selected members:

| Member | Grain | Shape | Meaning |
|---|---|---|---|
| `t_soisno_col` | column | `(-nlevsno+1:nlevgrnd)` | Snow/soil temperature [K], primary solver output |
| `t_ssbef_col` | column | `(-nlevsno+1:nlevgrnd)` | Snow/soil temperature at previous time step |
| `t_h2osfc_col` | column | `(:)` | Standing surface water temperature |
| `t_grnd_col` | column | `(:)` | Effective ground (surface) temperature |
| `t_grnd_r_col` / `t_grnd_u_col` | column | `(:)` | Rural/urban ground temperature |
| `t_lake_col` | column | `(1:nlevlak)` | Lake water temperature (see `lake.md`) |
| `t_building_lun` | landunit | `(:)` | Internal building temperature [K] |
| `imelt_col` | column | `(-nlevsno+1:nlevgrnd)` | Phase-change flag (0 none / 1 melt / 2 freeze) |
| `xmf_col` | column | `(:)` | Total latent heat of phase change of ground water |
| `fact_col` | column | `(-nlevsno+1:nlevgrnd)` | `dt/Cv` pre-factor retained between routines |
| `hc_soisno_col` | column | `(:)` | Soil plus snow heat content [MJ m^-2] |

The module also holds 10-day/24-hr/10-min temperature running means consumed by phenology, crop, and human-comfort diagnostics.

## Tridiagonal utilities: `TridiagonalMod`

`biogeophys/TridiagonalMod.F90` provides a generic `Tridiagonal` interface with three implementations:

- `Tridiagonal_sr` — scalar RHS, single tracer (`biogeophys/TridiagonalMod.F90:25-101`).
- `Tridiagonal_mr` — multi-RHS for tracer transport.
- `Tridiagonal_sr_with_var_bottom` — per-column variable `jbot` for variable-depth soil columns.

All three implement the standard Thomas algorithm. `Trisim` solves two coupled tridiagonal systems following Deshpande and Giddens (1977) and is used for the hydraulic-redistribution-coupled soil water equation when hydraulic stress is active. Module unchanged at `d40b8431`.

## Banded solver: `BandDiagonalMod`

`biogeophys/BandDiagonalMod.F90` wraps LAPACK `dgbsv` for the pentadiagonal system produced by `SoilTemperature` when standing surface water couples to snow and soil layers. With `nband = 5`, `kl = ku = 2`, ELM uses a pentadiagonal LAPACK solve to accommodate the extra row for `t_h2osfc`. The actual call is `BandDiagonalMod.F90:195`: `call dgbsv(n, kl, ku, 1, ab, m, ipiv, result, n, info)`. A non-zero `info` triggers `stop` with the offending column index and band matrix printed to `iulog`. Module unchanged.

`SolveTemperature` (`biogeophys/SoilTemperatureMod.F90:712-809`) hands the assembled `bmatrix`, `rvector`, `jtop`, and `jbot` to `BandDiagonal`.

## Interfaces with other subsystems

- **Canopy fluxes** — `SoilTemperature` consumes `veg_ef%cgrnd`, `veg_ef%dlrad`, `eflx_sh_grnd`, `eflx_lwrad_net`, and partitioned `sabg_{soil,snow}` coming out of `CanopyFluxesMod` / `SurfaceRadiationMod`. The surface boundary condition `hs_top = sabg + dlrad + (1-emg)*lwrad_in - emg*sb*T^4 - eflx_sh_tot - eflx_lh_tot` is assembled inside `ComputeGroundHeatFluxAndDeriv`. See `biogeophys/canopy_fluxes.md`.
- **Snow hydrology** — snow mass, density, layer thicknesses, and layer-integrated absorbed shortwave (`sabg_lyr_patch`) are read from `col_ws` and `solarabs_vars`. Phase change and resulting water fluxes are written back to `h2osoi_liq`, `h2osoi_ice`, and `h2osno_col`. The T-rho snow conductivity (when active) consumes the same `bw(c,j) = (h2osoi_ice + h2osoi_liq)/(frac_sno*dz)` density that drives the SnowCompaction physics in [snow.md](snow.md).
- **Albedo / SNICAR** — melt/freeze diagnosed here feeds `imelt_col`, which in turn drives snow-grain-radius evolution in `SnowSnicarMod` and thus the snow albedo in `SurfaceAlbedoMod`.
- **Active layer feedback to CN** — `altmax_lastyear_col` from `ActiveLayerMod` is used in soil biogeochemistry to set a dynamic rooting bound, altering decomposition and root respiration in permafrost columns.
- **Polygonal-tundra coupling** — `excess_ice`, `iwp_subsidence`, and `frac_melted` written by `alt_calc` feed back into `SoilHydrologyMod::SurfaceRunoff` (which zeroes `qflx_surf` over polygon landunits — see [soil_hydrology.md](soil_hydrology.md)).
- **Lake thermal column** — the lake temperature solver in `LakeTemperatureMod` uses the same `Tridiagonal` machinery; see `biogeophys/lake.md`.

## Notes on numerics

- `thin_sfclayer = 1.0e-6_r8` (`biogeophys/SoilTemperatureMod.F90:126`) is the threshold below which standing surface water is treated as negligible.
- Each snow/soil Crank-Nicholson sub-matrix has urban and non-urban variants to handle the building-interior boundary condition cleanly — see the family of `SetMatrix_*` and `SetRHSVec_*` subroutines.
- The module uses OpenACC `!$acc routine seq` declarations throughout, so every subroutine in the thermal path is GPU-offload-eligible.
