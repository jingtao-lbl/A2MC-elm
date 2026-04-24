---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Soil Hydrology: Richards Equation, Retention Curves, Infiltration, Drainage

This document describes ELM's subsurface water cycle - the retention curve polymorphism, the Zeng-Decker (2009) soil water movement solver, the water table / aquifer treatment, surface runoff and infiltration, subsurface drainage, and the state types that hold hydrologic state.

## Scope

- `biogeophys/SoilWaterRetentionCurveMod.F90` - abstract base class for retention curves.
- `biogeophys/SoilWaterRetentionCurveClappHornberg1978Mod.F90` - the Clapp-Hornberger 1978 implementation.
- `biogeophys/SoilWaterRetentionCurveFactoryMod.F90` - allocator that selects the concrete implementation.
- `biogeophys/SoilWaterMovementMod.F90` - Richards equation solver (Zeng-Decker 2009) and VSFM dispatch.
- `biogeophys/SoilHydrologyMod.F90` - surface runoff, infiltration, water table, drainage, VIC mapping.
- `biogeophys/SoilHydrologyType.F90` - non-VIC and VIC hydrologic state.
- `biogeophys/SoilStateType.F90` - time-constant and slowly-varying soil properties.
- `biogeophys/HydrologyDrainageMod.F90` - wrapper that calls `Drainage` and updates column water balance.
- `biogeophys/HydrologyNoDrainageMod.F90` - wrapper that calls `SnowWater`, `SurfaceRunoff`, `Infiltration`, `SoilWater` (no drainage step).

## Governing equation

ELM solves the vertical Richards equation. The solver header documents it explicitly (`biogeophys/SoilWaterMovementMod.F90:231-246`):

```
 d wat      d    d wat d psi
 ----- = - -- [ k(----- ----- - 1) ] + S
   dt      dz      dz  d wat
```

where `wat` is volumetric water content `[mm^3/mm^3]`, `psi` is the matric potential `[mm]`, `k` is hydraulic conductivity `[mm/s]`, and `S` is a source/sink term (root uptake, infiltration, recharge). The time rate of change per layer is
```
d wat(j) / dt * dz = qin[n+1] - qout[n+1] + S(j)
```
(`biogeophys/SoilWaterMovementMod.F90:253`). Linearization of `qin`, `qout` in `d wat` about the current state (`biogeophys/SoilWaterMovementMod.F90:247-260`) yields a tridiagonal system
```
r_j = a_j * d_wat[j-1] + b_j * d_wat[j] + c_j * d_wat[j+1]
```
solved with `Tridiagonal` from `biogeophys/TridiagonalMod.F90`.

## Retention curve polymorphism

`biogeophys/SoilWaterRetentionCurveMod.F90` defines an abstract base class `soil_water_retention_curve_type` (lines 15-26) with three deferred procedures:

| Procedure | Purpose |
|---|---|
| `soil_hk` | Compute hydraulic conductivity `hk` and `d hk / d s` |
| `soil_suction` | Compute matric potential `smp` and `d smp / d s` |
| `soil_suction_inverse` | Solve for `s` given a target `smp` |

The abstract interfaces at `biogeophys/SoilWaterRetentionCurveMod.F90:45-96` pass `hksat`, `imped`, `s`, `bsw`, `smpsat` - quantities specific to Clapp-Hornberger - so adding a van Genuchten implementation would likely require expanding this interface (noted in the module-header comment block, `biogeophys/SoilWaterRetentionCurveMod.F90:28-44`).

### Clapp-Hornberger 1978

`biogeophys/SoilWaterRetentionCurveClappHornberg1978Mod.F90` extends the base type. The governing equations are:

- Hydraulic conductivity (`biogeophys/SoilWaterRetentionCurveClappHornberg1978Mod.F90:67`):
  ```
  hk = imped * hksat * s^(2*bsw + 3)
  dhkds = (2*bsw + 3) * hk / s
  ```
- Matric potential (`biogeophys/SoilWaterRetentionCurveClappHornberg1978Mod.F90:98`):
  ```
  smp = -smpsat * s^(-bsw)
  dsmpds = -bsw * smp / s
  ```
- Inverse relation (`biogeophys/SoilWaterRetentionCurveClappHornberg1978Mod.F90:128`):
  ```
  s_target = (-smp_target / smpsat)^(-1/bsw)
  ```

`smpsat` is the minimum soil suction (positive) `[mm]`, `bsw` is the Clapp-Hornberger "b" pore-size-distribution exponent, `hksat` is the saturated hydraulic conductivity `[mm/s]`, and `imped` is an impedance factor applied for frozen soils.

### Factory dispatch

`biogeophys/SoilWaterRetentionCurveFactoryMod.F90:22-58` provides `create_soil_water_retention_curve()`. The method is **hard-coded** to `"clapphornberg_1978"` (`biogeophys/SoilWaterRetentionCurveFactoryMod.F90:41`), with a `select case` that `endrun`s on any other string; the inline comment notes this should eventually come from namelist. There is currently no van Genuchten class in the repo.

Note that `biogeophys/SoilWaterMovementMod.F90:550-566` **inlines** the Clapp-Hornberger equations directly rather than calling the factory object - the polymorphic class exists but is not dispatched from the main solver path. The inline inversion `smp(c,j) = -sucsat(c,j)*s_node^(-bsw(c,j))` at line 550 and `dsmpdw(c,j) = -bsw(c,j)*smp(c,j)/(s_node*watsat(c,j))` at line 556 mirror the polymorphic `soil_suction` routine.

## Main driver: `SoilWater`

Signature (`biogeophys/SoilWaterMovementMod.F90:82-83`):

```
subroutine SoilWater(bounds, num_hydrologyc, filter_hydrologyc,
     num_urbanc, filter_urbanc, soilhydrology_vars, soilstate_vars, dt)
```

`SoilWater` dispatches on `soilroot_water_method` (`biogeophys/SoilWaterMovementMod.F90:130-157`):

- `zengdecker_2009 = 0` (default) calls `soilwater_zengdecker2009`.
- `vsfm = 1` calls the PETSc-based variably-saturated flow model through `EMI_Driver(EM_ID_VSFM, EM_VSFM_SOIL_HYDRO_STAGE, ...)` (guarded by `USE_PETSC_LIB`).

`init_soilwater_movement` (`biogeophys/SoilWaterMovementMod.F90:49-79`) reads the `use_vsfm` and `use_var_soil_thick` namelist flags and sets `zengdecker_2009_with_var_soil_thick = .true.` if variable soil thickness is enabled.

## `soilwater_zengdecker2009`

Found at `biogeophys/SoilWaterMovementMod.F90:204`. This is the canonical ELM solver. Key steps:

1. **Unit conversion** - depths are converted from meters to millimeters (`biogeophys/SoilWaterMovementMod.F90:387-406`). `zmm`, `dzmm`, `zimm`, `zwtmm` are the mm-valued local arrays.
2. **`jwt` computation** - find the layer index of the first unsaturated layer (just above the water table) (`biogeophys/SoilWaterMovementMod.F90:414-431`). `jwt(c) = 0` if `zwt` is in the top layer.
3. **Ice fraction and impedance** - `vol_ice(c,j) = min(watsat, h2osoi_ice/(dz*denice))`, `icefrac(c,j) = vol_ice/watsat` (`biogeophys/SoilWaterMovementMod.F90:396-397`). Frozen soil suppresses `hk` via an `imped` factor.
4. **Equilibrium moisture profile** - compute `vol_eq(c,j)` and `zq(c,j)` (equilibrium matric potential) under the assumption of hydrostatic balance relative to the water table. This yields a correction `dzq = zq(j+1) - zq(j)` subtracted from the `smp` gradient when computing fluxes (`biogeophys/SoilWaterMovementMod.F90:583-622`).
5. **Inline Clapp-Hornberger** - per-layer conductivity and potential:
   ```
   hk(c,j)  = imped(c,j) * hksat(c,j) * s_node^(2*bsw(c,j) + 3)
   smp(c,j) = -sucsat(c,j) * s_node^(-bsw(c,j))
   ```
   (`biogeophys/SoilWaterMovementMod.F90:550`). `smp` is clipped at `smpmin(c)`.
6. **Tridiagonal assembly** - for each interior node, the fluxes are
   ```
   qin(c,j)  = -hk(c,j-1) * ((smp(c,j)   - smp(c,j-1)) - dzq) / (zmm(c,j)  - zmm(c,j-1))
   qout(c,j) = -hk(c,j)   * ((smp(c,j+1) - smp(c,j))   - dzq) / (zmm(c,j+1) - zmm(c,j))
   ```
   (`biogeophys/SoilWaterMovementMod.F90:605-616`). The RHS is `rmx(c,j) = qin - qout - qflx_rootsoi_col(c,j)`.
7. **Top boundary** - `qin(c,1) = qflx_infl(c)` supplied by `Infiltration` (`biogeophys/SoilWaterMovementMod.F90:586`).
8. **Bottom + aquifer boundary** - if the water table is in the column (`j > jwt(c)`), the bottom layer has `qout = 0`. If the water table is below the column, an 11th "aquifer" layer is added with smp computed from an averaged saturation, and `qout(j+1) = 0` enforces the zero-flow bottom boundary (`biogeophys/SoilWaterMovementMod.F90:624-711`). The aquifer layer recharge becomes `qcharge`, written out after the tridiagonal solve.
9. **Tridiagonal solve** - `call Tridiagonal(bounds, 1, nlevsoi+1, ...)` or the variable-bottom variant if `use_var_soil_thick` (`biogeophys/SoilWaterMovementMod.F90:723-741`).
10. **Root water uptake** - `qflx_rootsoi_col(c,j)` is constructed by `Compute_EffecRootFrac_And_VertTranSink` (`biogeophys/SoilWaterMovementMod.F90:1047`). Two implementations are dispatched:
    - `_Default` (`biogeophys/SoilWaterMovementMod.F90:1142`) - transpiration partitioned by `rootr` (effective root fraction).
    - `_HydStress` (`biogeophys/SoilWaterMovementMod.F90:1264`) - plant hydraulic stress model with explicit root/soil conductance.

## Surface runoff and infiltration: `SoilHydrologyMod`

Five public routines (`biogeophys/SoilHydrologyMod.F90:31-36`):

- `SurfaceRunoff` - TOPMODEL-style saturation-excess runoff (`biogeophys/SoilHydrologyMod.F90:42`).
- `Infiltration` - partitions incoming water into infiltration vs. ponding and runoff (`biogeophys/SoilHydrologyMod.F90:256`).
- `WaterTable` - diagnoses the water table depth prior to drainage (`biogeophys/SoilHydrologyMod.F90:637`).
- `Drainage` - topographic baseflow and excess-water drainage (`biogeophys/SoilHydrologyMod.F90:976`).
- `DrainageVSFM` - PETSc VSFM-compatible drainage variant (`biogeophys/SoilHydrologyMod.F90:1616`).
- `ELMVICMap` - maps between ELM layers and VIC sublayers (`biogeophys/SoilHydrologyMod.F90:2026`).

`SurfaceRunoff` uses a decay factor `fff` (from `hkdepth_col`), the saturated fraction `fsat`, and the maximum saturated area `wtfact` to compute `qflx_surf`. The VIC and non-VIC variants differ mainly in how `fsat` is computed - VIC uses `top_moist`, `top_max_moist`, `top_ice` aggregated across VIC sublayers.

`Infiltration` consumes `qflx_top_soil` (output of `SurfaceRunoff`) and the column's `qinmax` (from `SurfaceRunoff`) and computes the actual infiltration `qflx_infl` that feeds the top boundary of `SoilWater`. It also handles impervious urban road columns (which cannot infiltrate) and pervious urban road columns with reduced infiltration capacity.

`Drainage` implements the Niu et al. SIMTOP-style sub-surface runoff. The baseflow has two components:
- `rsub_top` - topographic control on saturated-zone flow, decaying exponentially with water table depth below `zwt` via `fff`.
- `rsub_bot` - bottom drainage when the water table is below the column.
Excess water `xs(c)` is then removed from layers starting at the bottom to reach the `watmin` floor.

## Water-movement state: `soilhydrology_type`

Defined in `biogeophys/SoilHydrologyType.F90:28-80`. Selected members:

| Member | Grain | Purpose |
|---|---|---|
| `zwt_col` | column | Water table depth `[m]` |
| `zwts_col` | column | Shallower of two water-table depths when perched table is present |
| `zwt_perched_col` | column | Perched water table depth |
| `wa_col` | column | Water in the unconfined aquifer `[mm]` |
| `qcharge_col` | column | Aquifer recharge `[mm/s]` |
| `fracice_col`, `icefrac_col` | column, level | Fractional impermeability and ice fraction |
| `fcov_col`, `fsat_col` | column | Fractional impermeable area and saturated-fraction area |
| `frost_table_col` | column | Depth of the frozen front |
| `hkdepth_col`, `fover` | column, gridcell | Decay factors for hydraulic conductivity and saturation fraction |
| `b_infil_col`, `ds_col`, `dsmax_col`, `Wsvic_col` | column | VIC parameters |
| `porosity_col`, `depth_col`, `vic_elm_fract_col` | column | VIC layer geometry |
| `moist_col`, `max_moist_col`, `i_0_col`, `ice_col` | column | VIC sublayer moisture state |
| `h2osfcflag`, `origflag` | scalar | Namelist switches for surface water and legacy hydrology |

VIC-specific arrays are allocated with `nlayer`/`nlayert` dimensions; the non-VIC arrays use `nlevgrnd`. Initialization (`InitAllocate`, `biogeophys/SoilHydrologyType.F90:101-160`) sets everything to `spval` so that unused fields are trivially diagnosable.

## Soil property state: `soilstate_type`

Defined at `biogeophys/SoilStateType.F90:36-105`. Selected hydraulic properties (all on column, typically `(nlevgrnd)` unless noted):

| Member | Meaning |
|---|---|
| `hksat_col`, `hksat_min_col` | Saturated hydraulic conductivity and its mineral-only component |
| `watsat_col` | Saturation volumetric water content (porosity) |
| `watdry_col`, `watopt_col` | Wilting and optimal soil water contents used by `btran` |
| `watfc_col`, `watmin_col` | Field capacity, minimum volumetric water content |
| `sucsat_col`, `sucmin_col` | Clapp-Hornberger minimum suction and clipping value |
| `bsw_col` | Clapp-Hornberger "b" |
| `smp_l_col`, `hk_l_col` | Layer-resolved matric potential and conductivity written out by the solver |
| `smpmin_col` | Minimum allowable `smp` for btran |
| `soilpsi_col` | Soil water potential in each layer `[MPa]` for CN |
| `eff_porosity_col` | `watsat - vol_ice` |
| `rootr_patch`, `rootr_col` | Effective root fraction per layer |
| `root_conductance_patch`, `soil_conductance_patch`, `k_soil_root_patch` | Hydraulic-stress conductances |
| `thk_col`, `tkmg_col`, `tkdry_col`, `tksatu_col`, `csol_col` | Thermal properties (consumed by `SoilTemperature`) |
| `tillage_col`, `litho_col` | Erosion inputs (used by `SedYieldMod`) |

`soilpsi_col` is updated every timestep in `HydrologyNoDrainage` using `psi = -sucsat*(h2osoi_liqvol/watsat)^(-bsw)` with `e_ice` ice impedance, and forms the primary soil-water-potential input to N/P uptake and decomposition.

## Drainage wrappers

`HydrologyDrainageMod.F90` (301 lines). `HydrologyDrainage` (`biogeophys/HydrologyDrainageMod.F90:38`) is the Phase-2 hydrology driver:

1. Optional `ELMVICMap` when `use_vichydro` is true.
2. `Drainage` if not using VSFM.
3. BeTR pre/post-diagnostic flux retrievals (guarded by `use_betr`).
4. Update `h2osoi_vol` for each layer and compute `endwb(c) = h2ocan + h2osno + h2osfc + wa + sum(h2osoi_ice + h2osoi_liq)` for the column water budget closure (`biogeophys/HydrologyDrainageMod.F90:157-195`).

`HydrologyNoDrainageMod.F90` (628 lines). `HydrologyNoDrainage` (`biogeophys/HydrologyNoDrainageMod.F90:40`) is the Phase-1 driver run earlier in the timestep. Its calling sequence is documented at `biogeophys/HydrologyNoDrainageMod.F90:52-62`:

```
-> SnowWater            change of snow mass, snow water onto soil
-> SurfaceRunoff        surface runoff
-> Infiltration         infiltration into surface soil layer
-> SoilWater            soil water movement between layers
     -> Tridiagonal     tridiagonal matrix solution
-> Drainage             subsurface runoff  [deferred to HydrologyDrainage]
-> SnowCompaction       compaction of snow layers
-> CombineSnowLayers
-> DivideSnowLayers
```

`HydrologyNoDrainage` also updates `soilpsi_col`, `eff_porosity_col`, and the derived 10 cm / 17 cm soil liquid+ice diagnostics, and handles the FAN (ammonia volatilization) diagnostic save of `h2osoi_liq` in the top layer before/after soil water movement.

## Interfaces with other subsystems

- **Canopy fluxes** - `qflx_rootsoi_col` is the transpiration sink term fed into `SoilWater`. It is filled by `Compute_EffecRootFrac_And_VertTranSink` from the transpiration `qflx_tran_veg` and the `rootr` distribution. `soilpsi_col` produced in `HydrologyNoDrainage` feeds back into the canopy `btran` water-stress factor that scales stomatal conductance in `CanopyFluxesMod`; see `biogeophys/canopy_fluxes.md`.
- **Snow hydrology** - `SnowWater` (called from `HydrologyNoDrainage`) determines `qflx_top_soil`, the top boundary for `SurfaceRunoff` and `Infiltration`. Snow melt appears as part of `qflx_top_soil`.
- **Soil thermal** - `h2osoi_liq`, `h2osoi_ice` and `soilpsi_col` are inputs to `SoilThermProp` in `SoilTemperatureMod` (thermal conductivity and heat capacity). Frozen liquid produces latent heat that modifies `h2osoi_liq/ice` via `Phasechange_beta`.
- **Biogeochemistry** - `soilpsi_col`, `soilliq_col`, `soilice_col`, `watfc_col` drive decomposition temperature/moisture limiters in the CN decomposition cascade (see `CNDecompCascade*`).
- **Lake hydrology** - lake soil layers share `soilstate_type`; lake-specific soil water is handled by `LakeHydrologyMod`. See `biogeophys/lake.md`.

## Notes and gotchas

- Length units: `SoilWater` works in millimeters internally while `SoilTemperature` works in meters. The Richards solver converts `z`, `dz`, `zi` to `zmm`, `dzmm`, `zimm` at the top of `soilwater_zengdecker2009` (`biogeophys/SoilWaterMovementMod.F90:387-406`).
- `origflag` (`soilhydrology_vars%origflag`) selects legacy versus updated expressions for a few quantities (`dsmpdw` expression, `s_node` averaging) - see `biogeophys/SoilWaterMovementMod.F90:555-559` and `biogeophys/SoilHydrologyMod.F90` SurfaceRunoff.
- `use_var_soil_thick` forces the aquifer layer into a purely passive mass-conservation role (`biogeophys/SoilWaterMovementMod.F90:678-709`), and triggers the variable-bottom `Tridiagonal_sr_with_var_bottom` solver.
- The factory-style retention curve machinery is wired but not actively called by `soilwater_zengdecker2009`, which inlines Clapp-Hornberger for performance / GPU offload.
