---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Soil Temperature and the Thermal Column

This document covers the subsurface thermal column in ELM, the heat conduction solver, phase change, permafrost/active layer tracking, and the linear algebra utilities used to invert the discretized heat equation.

## Scope

- `biogeophys/SoilTemperatureMod.F90` - the Crank-Nicholson heat diffusion solver.
- `biogeophys/TemperatureType.F90` - the `temperature_type` derived type holding column/patch/landunit temperatures.
- `biogeophys/ActiveLayerMod.F90` - active layer thickness (thawed layer depth) for permafrost columns.
- `biogeophys/TridiagonalMod.F90` - scalar and multi-RHS Tridiagonal solvers and the coupled `Trisim` solver.
- `biogeophys/BandDiagonalMod.F90` - LAPACK `dgbsv` band solver wrapper for pentadiagonal systems.

## Governing equation

ELM solves 1D vertical heat conduction in the snow/standing-water/soil column

```
    dT     d        dT
 Cv --- = -- ( k  ----- )  +  S(z)
    dt    dz        dz
```

where `Cv` is the volumetric heat capacity `[J m^-3 K^-1]`, `k` is thermal conductivity `[W m^-1 K^-1]`, and `S` represents absorbed shortwave inside snow/soil layers. Discretized with the Crank-Nicholson method, this becomes a tridiagonal (or banded) system solved every time step (`biogeophys/SoilTemperatureMod.F90:149-709`). The header comment block at `biogeophys/SoilTemperatureMod.F90:154-171` states the boundary conditions explicitly:

- Top: `F = Rnet - Hg - LEg` (net radiation minus ground sensible and latent heat).
- Bottom: `F = 0` at the base of the soil column (zero heat flux).

Time stepping uses the Crank-Nicholson factor `cnfac` (from `elm_varcon`), which weights the implicit versus explicit contributions to diffusive fluxes at the interfaces. See the use of `cnfac` at `biogeophys/SoilTemperatureMod.F90:1967`.

## Top-level driver: `SoilTemperature`

Signature (`biogeophys/SoilTemperatureMod.F90:150-152`):

```
subroutine SoilTemperature(bounds, num_urbanl, filter_urbanl, num_nolakec, filter_nolakec,
     atm2lnd_vars, urbanparams_vars, canopystate_vars,
     solarabs_vars, soilstate_vars, energyflux_vars)
```

The routine operates over the non-lake column filter and produces the updated `col_es%t_soisno(c, -nlevsno+1:nlevgrnd)` array plus `t_h2osfc`, `t_grnd`, `xmf`, and `t_building`. The call chain inside is (see comments `biogeophys/SoilTemperatureMod.F90:45-52`):

1. `SoilThermProp` - compute `tk`, `cv`, and `tk_h2osfc` (`biogeophys/SoilTemperatureMod.F90:382-386`).
2. `ComputeGroundHeatFluxAndDeriv` - net heat flux `hs` and derivative `dhsdT` at the upper boundary (`biogeophys/SoilTemperatureMod.F90:392-400`).
3. `ComputeHeatDiffFluxAndFactor` - heat-diffusion flux `fn` at interfaces and pre-factor `fact = dt/Cv` (`biogeophys/SoilTemperatureMod.F90:406-412`).
4. `SetRHSVec` and `SetMatrix` - assemble the banded Crank-Nicholson system for urban and non-urban columns separately.
5. `SolveTemperature` - calls `BandDiagonal` from `biogeophys/SoilTemperatureMod.F90:802-805`.
6. `PhaseChange_beta` - latent-heat based phase change correction (`biogeophys/SoilTemperatureMod.F90:1262`).
7. `PhaseChangeH2osfc` - handles freezing of surface ponded water (`biogeophys/SoilTemperatureMod.F90:1049-1052`).

A namelist-selectable PETSc thermal model (`petsc_thermal_model = 1`) is available via `init_soil_temperature` (`biogeophys/SoilTemperatureMod.F90:132-147`); by default `thermal_model = default_thermal_model = 0`.

## Thermal properties: `SoilThermProp`

Located at `biogeophys/SoilTemperatureMod.F90:812-1046`. It implements three property calculations:

- Soil thermal conductivity follows Farouki (1981) / Johansen. For unfrozen soils the Kersten number is `dke = max(0, log10(satw) + 1)` and for frozen soils `dke = satw` (`biogeophys/SoilTemperatureMod.F90:921-924`). The saturated conductivity is `dksat = tkmg * tkwat^(fl*watsat) * tkice^((1-fl)*watsat)` (`biogeophys/SoilTemperatureMod.F90:928`), and the final layer value is
  ```
  thk(c,j) = dke*dksat + (1 - dke)*tkdry(c,j)
  ```
  (`biogeophys/SoilTemperatureMod.F90:929`).
- Snow conductivity follows Jordan (1991): `thk = tkair + (7.75e-5*bw + 1.105e-6*bw^2) * (tkice - tkair)` at `biogeophys/SoilTemperatureMod.F90:951`, with `bw` the snow bulk density `(ice+liq) / (frac_sno*dz)`.
- Interface conductivity uses the harmonic-mean flux-matching formula `tk(c,j) = thk(c,j)*thk(c,j+1)*(z(j+1)-z(j)) / (thk(c,j)*(z(j+1)-zi(j)) + thk(c,j+1)*(zi(j)-z(j)))` at `biogeophys/SoilTemperatureMod.F90:965-966` for non-urban columns. Urban walls, roofs and roads use separately-read `tk_wall`, `tk_roof`, `tk_improad` from `urbanparams_vars`.

Volumetric heat capacity combines soil solids plus the phase-dependent water content:
```
cv(c,j) = csol(c,j)*(1 - watsat(c,j))*dz(c,j)
        + h2osoi_ice(c,j)*cpice + h2osoi_liq(c,j)*cpliq
```
(`biogeophys/SoilTemperatureMod.F90:1013`). Special cases: urban walls/roofs/impervious-road use tabulated `cv_*` values; wetland and ice columns use the pure water/ice heat capacity.

## Flux and factor assembly: `ComputeHeatDiffFluxAndFactor`

`biogeophys/SoilTemperatureMod.F90:1900-1991`. For each interface below a snow-layer column this routine computes:

- `fact(c,j) = dtime / cv(c,j)`, a time-step/heat-capacity pre-factor (`biogeophys/SoilTemperatureMod.F90:1956`).
- `fn(c,j) = tk(c,j)*(t_soisno(c,j+1) - t_soisno(c,j)) / (z(c,j+1) - z(c,j))` (`biogeophys/SoilTemperatureMod.F90:1957`).
- At the top soil layer a capacitance correction `dz(c,j) / (0.5*(z(c,j)-zi(c,j-1) + capr*(z(c,j+1)-zi(c,j-1))))` is applied (`biogeophys/SoilTemperatureMod.F90:1974`); `capr` is the standard CLM capacity-ratio constant from `elm_varcon`.
- Urban sunwall/shadewall/roof columns use a prescribed internal building temperature as the bottom boundary, yielding `fn(c,nlevurb) = tk * (t_building - cnfac*t_soisno) / (zi-z)` (`biogeophys/SoilTemperatureMod.F90:1967`).
- Non-urban bottom layer uses `fn(c,nlevgrnd) = eflx_bot(c)` - a prescribed geothermal flux from `col_ef%eflx_bot` (`biogeophys/SoilTemperatureMod.F90:1982`).

## Phase change

`Phasechange_beta` (`biogeophys/SoilTemperatureMod.F90:1262`) applies the enthalpy-based freeze/thaw correction after each temperature update. It diagnoses `imelt_col(c,j)` (0/1/2 for none/melt/freeze - stored on `temperature_type`, `biogeophys/TemperatureType.F90:91`) and decrements ice or liquid pools by `xmf` (`col_ef%xmf`), which is the latent heat consumed during the step. `PhaseChangeH2osfc` (`biogeophys/SoilTemperatureMod.F90:1049-1261`) handles freezing of standing surface water and moves the newly-formed ice to the bottom snow layer when appropriate.

## Permafrost and the active layer: `ActiveLayerMod`

`biogeophys/ActiveLayerMod.F90:28-158` defines the single public routine `alt_calc`. It scans `t_soisno(c, nlevgrnd)` from the bottom upward and finds the first unfrozen layer (`biogeophys/ActiveLayerMod.F90:120-131`). The active layer depth is then a linear interpolation between the lowest thawed node and the layer below it to find where `T = TKFRZ`:
```
alt(c) = z1 + (t1 - TKFRZ)*(z2 - z1) / (t1 - t2)
```
(`biogeophys/ActiveLayerMod.F90:139`). The routine maintains three outputs on `canopystate_vars`: the instantaneous `alt_col`, the annual maximum `altmax_col`, and the prior-year maximum `altmax_lastyear_col`. On January 1 for northern columns and July 1 for southern columns the annual max is rolled over (`biogeophys/ActiveLayerMod.F90:86-110`). The rooting-memory-based root profile in CN uses `altmax_lastyear_col` as an input (cross-link to the biogeochem soil pool vertical mixing docs).

## Temperature state: `temperature_type`

Defined at `biogeophys/TemperatureType.F90:23-120`. Selected members:

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

The module also holds 10-day/24-hr/10-min temperature running means (`t_a10_patch`, `t_veg24_patch`, `t_ref2m_*`) consumed by phenology, crop, and human-comfort diagnostics (`biogeophys/TemperatureType.F90:43-80`).

## Tridiagonal utilities: `TridiagonalMod`

`biogeophys/TridiagonalMod.F90` provides a generic `Tridiagonal` interface with three implementations:

- `Tridiagonal_sr` - scalar RHS, single tracer (`biogeophys/TridiagonalMod.F90:25-101`).
- `Tridiagonal_mr` - multi-RHS for tracer transport (`biogeophys/TridiagonalMod.F90:104-188`).
- `Tridiagonal_sr_with_var_bottom` - per-column variable `jbot` for variable-depth soil columns (`biogeophys/TridiagonalMod.F90:327-405`).

All three implement the standard Thomas algorithm: forward elimination accumulates `bet(ci)` and `gam(ci,j)`, then a back-substitution loop writes the solution. Filters support `is_col_active` to skip inactive columns. The scalar version inside the `j` loop computes `bet(ci) = b(ci,j) - a(ci,j) * gam(ci,j)` and `u(ci,j) = (r(ci,j) - a(ci,j)*u(ci,j-1)) / bet(ci)` (`biogeophys/TridiagonalMod.F90:81-82`).

`Trisim` (`biogeophys/TridiagonalMod.F90:191-324`) solves two coupled tridiagonal systems of the form
```
A1*W1(j-1) + B1*W1(j) + C1*W1(j+1) = D1*W2(j) + E1
A2*W2(j-1) + B2*W2(j) + C2*W2(j+1) = D2*W1(j) + E2
```
following Deshpande and Giddens (1977). This solver is used for the hydraulic-redistribution-coupled soil water equation when hydraulic stress is active; it is declared in `TridiagonalMod` but not used by `SoilTemperature` directly.

## Banded solver: `BandDiagonalMod`

`biogeophys/BandDiagonalMod.F90:27-219` wraps LAPACK `dgbsv` for the pentadiagonal system produced by `SoilTemperature` when standing surface water couples to snow and soil layers. The storage layout comment at `biogeophys/BandDiagonalMod.F90:159-164` documents the LAPACK compact band layout `AB(KL+KU+1+i-j, j) = A(i,j)`. Given `nband`, `kl = ku = (nband-1)/2 = 2`, so ELM is using a pentadiagonal LAPACK solve to accommodate the extra row for `t_h2osfc`. The actual LAPACK call is at `biogeophys/BandDiagonalMod.F90:195`: `call dgbsv(n, kl, ku, 1, ab, m, ipiv, result, n, info)`. A non-zero `info` triggers `stop` with the offending column index and band matrix printed to `iulog`.

`SolveTemperature` (`biogeophys/SoilTemperatureMod.F90:710-809`) hands the assembled `bmatrix`, `rvector`, `jtop`, and `jbot` to `BandDiagonal`; see the call at `biogeophys/SoilTemperatureMod.F90:802-804`.

## Interfaces with other subsystems

- **Canopy fluxes** - `SoilTemperature` consumes `veg_ef%cgrnd`, `veg_ef%dlrad`, `eflx_sh_grnd`, `eflx_lwrad_net`, and partitioned `sabg_{soil,snow}` coming out of `CanopyFluxesMod` / `SurfaceRadiationMod` (see associate block `biogeophys/SoilTemperatureMod.F90:258-294`). The surface boundary condition `hs_top = sabg + dlrad + (1-emg)*lwrad_in - emg*sb*T^4 - eflx_sh_tot - eflx_lh_tot` is assembled inside `ComputeGroundHeatFluxAndDeriv` (`biogeophys/SoilTemperatureMod.F90:1653`). See `biogeophys/canopy_fluxes.md` for the surface-layer partitioning that feeds this.
- **Snow hydrology** - snow mass, density, layer thicknesses, and layer-integrated absorbed shortwave (`sabg_lyr_patch`) are read from `col_ws` and `solarabs_vars`. Phase change and resulting water fluxes are written back to `h2osoi_liq`, `h2osoi_ice`, and `h2osno_col`.
- **Albedo / SNICAR** - melt/freeze diagnosed here feeds `imelt_col`, which in turn drives snow-grain-radius evolution in `SnowSnicarMod` and thus the snow albedo in `SurfaceAlbedoMod`.
- **Active layer feedback to CN** - `altmax_lastyear_col` from `ActiveLayerMod` is used in soil biogeochemistry to set a dynamic rooting bound, altering decomposition and root respiration in permafrost columns.
- **Lake thermal column** - the lake temperature solver in `LakeTemperatureMod` uses the same `Tridiagonal` machinery; see `biogeophys/lake.md`.

## Notes on numerics

- `thin_sfclayer = 1.0e-6_r8` (`biogeophys/SoilTemperatureMod.F90:124`) is the threshold below which standing surface water is treated as negligible (`c_h2osfc`, `dz_h2osfc` clipped to `thin_sfclayer`, `biogeophys/SoilTemperatureMod.F90:418-424`).
- Each snow/soil Crank-Nicholson sub-matrix (`SetMatrix_Snow*`, `SetMatrix_Soil*`) has urban and non-urban variants to handle the building-interior boundary condition cleanly - see the ~30 `SetMatrix_*` subroutines publicly exported from `SoilTemperatureMod` for unit testing.
- The module uses OpenACC `!$acc routine seq` declarations throughout, so every subroutine in the thermal path is GPU-offload-eligible.
