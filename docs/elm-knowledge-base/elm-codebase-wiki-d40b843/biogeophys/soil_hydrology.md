---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Soil Hydrology: Richards Equation, Retention Curves, Infiltration, Drainage, Ocean Coupling

This document describes ELM's subsurface water cycle — the retention curve polymorphism, the Zeng-Decker (2009) soil water movement solver, the water table / aquifer treatment, surface runoff and infiltration (with polygonal-tundra and IM2 hillslope-hydrology branches), subsurface drainage, the new ocean-lateral drainage path, and the state types that hold hydrologic state.

## Scope

- `biogeophys/SoilWaterRetentionCurveMod.F90` — abstract base class for retention curves. Unchanged at `d40b8431`.
- `biogeophys/SoilWaterRetentionCurveClappHornberg1978Mod.F90` — the Clapp-Hornberger 1978 implementation. Unchanged.
- `biogeophys/SoilWaterRetentionCurveFactoryMod.F90` — allocator that selects the concrete implementation. Unchanged.
- `biogeophys/SoilWaterMovementMod.F90` — Richards equation solver (Zeng-Decker 2009) and VSFM dispatch. Unchanged at the algorithm level.
- `biogeophys/SoilHydrologyMod.F90` (2484 lines at `d40b8431`, up from 2111 at `60d9aad`) — surface runoff, infiltration, water table, drainage, **`Drainage_To_OCN` (new)**, VSFM drainage, VIC mapping. `Infiltration` and `SurfaceRunoff` extended for polygonal-tundra and IM2 hillslope branches.
- `biogeophys/SoilHydrologyType.F90` — non-VIC and VIC hydrologic state.
- `biogeophys/SoilStateType.F90` — time-constant and slowly-varying soil properties.
- `biogeophys/HydrologyDrainageMod.F90` — wrapper that calls `Drainage` and (optionally) `Drainage_To_OCN`. **Signature changed**: now takes `ocn2lnd_vars`.
- `biogeophys/HydrologyNoDrainageMod.F90` — wrapper that calls `SnowWater`, `SurfaceRunoff`, `Infiltration`, `SoilWater`. **Signature changed**: now takes `ocn2lnd_vars`.

## Governing equation

ELM solves the vertical Richards equation:

```
 d wat      d    d wat d psi
 ----- = - -- [ k(----- ----- - 1) ] + S
   dt      dz      dz  d wat
```

where `wat` is volumetric water content `[mm^3/mm^3]`, `psi` is the matric potential `[mm]`, `k` is hydraulic conductivity `[mm/s]`, and `S` is a source/sink term (root uptake, infiltration, recharge). Linearization yields a tridiagonal system solved with `Tridiagonal` from `biogeophys/TridiagonalMod.F90`.

## Retention curve polymorphism

`SoilWaterRetentionCurveMod.F90` defines an abstract base class `soil_water_retention_curve_type` with three deferred procedures:

| Procedure | Purpose |
|---|---|
| `soil_hk` | Compute hydraulic conductivity `hk` and `d hk / d s` |
| `soil_suction` | Compute matric potential `smp` and `d smp / d s` |
| `soil_suction_inverse` | Solve for `s` given a target `smp` |

### Clapp-Hornberger 1978

`SoilWaterRetentionCurveClappHornberg1978Mod.F90` extends the base type:

- Hydraulic conductivity (line 67): `hk = imped * hksat * s^(2*bsw + 3)`
- Matric potential (line 98): `smp = -smpsat * s^(-bsw)`
- Inverse (line 128): `s_target = (-smp_target / smpsat)^(-1/bsw)`

`smpsat` is the minimum soil suction (positive) `[mm]`, `bsw` is the Clapp-Hornberger "b" pore-size-distribution exponent, `hksat` is the saturated hydraulic conductivity `[mm/s]`, and `imped` is an impedance factor applied for frozen soils.

### Factory dispatch

`SoilWaterRetentionCurveFactoryMod.F90:22-58` provides `create_soil_water_retention_curve()`. The method is hard-coded to `"clapphornberg_1978"` (line 41). There is currently no van Genuchten class in the repo.

`SoilWaterMovementMod.F90:550-566` **inlines** the Clapp-Hornberger equations directly rather than calling the factory object — the polymorphic class exists but is not dispatched from the main solver path.

## Main driver: `SoilWater`

Signature (`biogeophys/SoilWaterMovementMod.F90:82-83`):

```
subroutine SoilWater(bounds, num_hydrologyc, filter_hydrologyc,
     num_urbanc, filter_urbanc, soilhydrology_vars, soilstate_vars, dt)
```

`SoilWater` dispatches on `soilroot_water_method`:

- `zengdecker_2009 = 0` (default) calls `soilwater_zengdecker2009` (`SoilWaterMovementMod.F90:204`).
- `vsfm = 1` calls the PETSc-based variably-saturated flow model (guarded by `USE_PETSC_LIB`).

`init_soilwater_movement` (`SoilWaterMovementMod.F90:49-79`) reads the `use_vsfm` and `use_var_soil_thick` namelist flags and sets `zengdecker_2009_with_var_soil_thick = .true.` if variable soil thickness is enabled.

## `soilwater_zengdecker2009`

Found at `biogeophys/SoilWaterMovementMod.F90:204-847`. This is the canonical ELM solver. Unchanged at `d40b8431`. Key steps:

1. Unit conversion — depths from meters to millimeters.
2. `jwt` — find the layer index of the first unsaturated layer (just above the water table).
3. Ice fraction and impedance.
4. Equilibrium moisture profile.
5. Inline Clapp-Hornberger per-layer conductivity and potential (line 550).
6. Tridiagonal assembly with `qin`, `qout`, source `-qflx_rootsoi_col`.
7. Top boundary `qin(c,1) = qflx_infl(c)` from `Infiltration`.
8. Bottom + aquifer boundary handling.
9. Tridiagonal solve.
10. Root water uptake from `Compute_EffecRootFrac_And_VertTranSink` (`SoilWaterMovementMod.F90:1047-1140`).

## SoilHydrologyMod public API

At `d40b8431` `SoilHydrologyMod` exports **six** public routines (`SoilHydrologyMod.F90:33-38`); `Drainage_To_OCN` is new at `d40b8431`:

| Routine | Entry line | Purpose |
|---|---|---|
| `SurfaceRunoff` | `SoilHydrologyMod.F90:44-290` | TOPMODEL-style saturation-excess runoff. New polygon and IM2-hillslope branches. |
| `Infiltration` | `SoilHydrologyMod.F90:293-743` | Partitions incoming water into infiltration vs. ponding and runoff. **Signature changed** (now takes `ocn2lnd_vars`). |
| `WaterTable` | `SoilHydrologyMod.F90:746-1082` | Diagnoses the water table depth prior to drainage. |
| `Drainage` | `SoilHydrologyMod.F90:1085-1773` | Topographic baseflow and excess-water drainage. |
| **`Drainage_To_OCN`** *(new at d40b8431)* | `SoilHydrologyMod.F90:1776-1986` | Land-to-ocean lateral subsurface flow when `use_ocn_lnd_one_way = .true.` |
| `DrainageVSFM` | `SoilHydrologyMod.F90:1989-2396` | PETSc VSFM-compatible drainage variant. |
| `ELMVICMap` | `SoilHydrologyMod.F90:2399-2482` | Maps between ELM layers and VIC sublayers. |

## `SurfaceRunoff` — polygon and IM2 branches

`SurfaceRunoff` (`biogeophys/SoilHydrologyMod.F90:44-290`) uses a decay factor `fff` (from `hkdepth_col`), the saturated fraction `fsat`, and the maximum saturated area `wtfact` to compute `qflx_surf`. Two extensions at `d40b8431`:

### Polygon-ground zero-runoff branch

For ice-wedge polygon landunits, surface runoff is zeroed (`SoilHydrologyMod.F90:205-220`):

```fortran
do fc = 1, num_hydrologyc
   c = filter_hydrologyc(fc)
   l = col_pp%landunit(c)
   ! no qflx_surf in polygonal ground
   if (lun_pp%ispolygon(l)) then
      qflx_surf(c) = 0._r8
   else
      ! standard saturation-excess
      if (origflag == 1) then
         qflx_surf(c) = fcov(c) * qflx_top_soil(c)
      else
         qflx_surf(c) = fsat(c) * qflx_top_soil(c)
      endif
   endif
end do
```

This is consistent with the polygonal-tundra physics in `ActiveLayerMod` (see [soil_temperature.md](soil_temperature.md)), where surface water is captured in polygon depressions rather than running off downslope.

### IM2 hillslope hydrology block

When `use_IM2_hillslope_hydrology = .true.`, lateral-from-uphill water is added to `qflx_top_soil` after the per-column runoff is computed (`SoilHydrologyMod.F90:260-286`):

```fortran
if (use_IM2_hillslope_hydrology) then
   ! 1. zero the topounit sum of column weights
   do fc = 1, num_hydrologyc
      c = filter_hydrologyc(fc)
      t = col_pp%topounit(c)
      top_pp%uphill_wt(t) = 0._r8
   end do
   ! 2. sum the relevant column weights
   do fc = 1, num_hydrologyc
      c = filter_hydrologyc(fc)
      t = col_pp%topounit(c)
      top_pp%uphill_wt(t) = top_pp%uphill_wt(t) + col_pp%wttopounit(c)
   end do
   ! 3. distribute uphill flow to soil/crop/pervious-road columns
   do fc = 1, num_hydrologyc
      c = filter_hydrologyc(fc)
      t = col_pp%topounit(c)
      qflx_from_uphill(c) = (col_pp%wttopounit(c)/top_pp%uphill_wt(t)) &
                          * (frac_from_uphill * top_ws%from_uphill(t)) / dtime
      qflx_top_soil(c) = qflx_top_soil(c) + qflx_from_uphill(c)
   end do
endif
```

`top_ws%from_uphill(t)` is a topounit-level water store. `frac_from_uphill` is a tunable fraction (from `elm_varcon`) that controls how aggressively uphill water is delivered. This is the active NGEE-Arctic subgrid hillslope flow infrastructure, paired with the `qflx_to_downhill` sink computed in `HydrologyDrainage`.

The VIC and non-VIC variants of `SurfaceRunoff` differ mainly in how `fsat` is computed — VIC uses `top_moist`, `top_max_moist`, `top_ice` aggregated across VIC sublayers (`SoilHydrologyMod.F90:160-178`).

## `Infiltration` — new `ocn2lnd_vars` argument

Signature at `d40b8431` (`SoilHydrologyMod.F90:293-307`):

```fortran
subroutine Infiltration(bounds, num_hydrologyc, filter_hydrologyc, num_urbanc, filter_urbanc, &
     atm2lnd_vars, ocn2lnd_vars, lnd2atm_vars, energyflux_vars, soilhydrology_vars, soilstate_vars, dtime)
```

The new `ocn2lnd_vars` argument (immediately after `atm2lnd_vars`) carries `ocn2lnd_vars%ssh_grc(g)` (gridcell sea surface height) for use by the polygon-tundra and ocean-lateral path. Prior signature did not include this argument; callers in `HydrologyNoDrainage` and `HydrologyDrainage` have been updated.

`Infiltration` consumes `qflx_top_soil` (output of `SurfaceRunoff`) and the column's `qinmax` (from `SurfaceRunoff`) and computes the actual infiltration `qflx_infl` that feeds the top boundary of `SoilWater`. It also handles impervious urban road columns (which cannot infiltrate) and pervious urban road columns with reduced infiltration capacity. New in `Infiltration` at `d40b8431` is the import of the polygon landunit identifiers from `landunit_varcon` (`SoilHydrologyMod.F90:307`): `istsoil, istcrop, ilowcenpoly, iflatcenpoly, ihighcenpoly`.

## `Drainage`

`Drainage` (`biogeophys/SoilHydrologyMod.F90:1085-1773`) implements the Niu et al. SIMTOP-style sub-surface runoff. The baseflow has two components:

- `rsub_top` — topographic control on saturated-zone flow, decaying exponentially with water table depth below `zwt` via `fff`.
- `rsub_bot` — bottom drainage when the water table is below the column.

Excess water `xs(c)` is then removed from layers starting at the bottom to reach the `watmin` floor. The `qflx_drain` sink, plus a `qflx_to_downhill` redistribution component (when `use_IM2_hillslope_hydrology`), close the column subsurface budget.

## `Drainage_To_OCN` (new at d40b8431)

`Drainage_To_OCN` (`biogeophys/SoilHydrologyMod.F90:1776-1986`, ~210 lines) implements lateral subsurface flow between coastal land columns and the ocean. Activated when `use_ocn_lnd_one_way = .true.`. Signature:

```fortran
subroutine Drainage_To_OCN(bounds, num_hydrologyc, filter_hydrologyc, &
     soilhydrology_vars, soilstate_vars, ocn2lnd_vars, dtime)
```

### Algorithm

For each column on the hydrology filter (`SoilHydrologyMod.F90:1833-1982`):

1. **Find `jwt`** — the layer above the water table.
2. **Find `jss`** — the layer above the sea surface height (SSH) in the column. Computed from `ocn2lnd_vars%ssh_grc(g)` and `ldomain%topo(g) - zi(c,j)`.
3. **Compute ice impedance** integrated over the saturated zone: `imped = 10^(-e_ice * (icefracsum/dzsum))`.
4. **Compute Fan et al. (2007) e-folding length** `f` from topographic slope: `f = 1` for steep terrain, `f = 20/(1 + 125*topo_slope)` otherwise (`SoilHydrologyMod.F90:1869-1873`).
5. **Compute transmissivities `T1`, `T2`** of saturated portion of the soil column above and below SSH/ZWT, using `1.e-3 * hksat(c,j) * cellclay_col(c,j)` per layer (clay-fraction-weighted) (`SoilHydrologyMod.F90:1885-1903`).
6. **Compute lateral flux** to ocean:

   ```
   head        = topo(g) - zwt(c) - ssh(g)
   qflx_lnd2ocn(c) = imped * 2 * (T1 + T2) * head / (frac(g) * area(g) * 1e6) * 1e3   ! [mm H2O/s]
   ```

   Positive `qflx_lnd2ocn` means land-to-ocean; negative means ocean-to-land. Set to zero when `topo - ssh > 80 m` (land is far above sea level, no exchange).
7. **Remove water** from either the aquifer layer (when WT is below the column) or from soil layers (when WT is within the column), updating `wa(c)`, `zwt(c)`, and `h2osoi_liq(c,j)` using a specific-yield calculation `s_y = watsat * (1 - (1 + 1e3*zwt/sucsat)^(-1/bsw))`. Both rising and deepening water-table cases are handled (`SoilHydrologyMod.F90:1924-1980`).

### Outputs

- `col_wf%qflx_lnd2ocn(c)` — lateral land-to-ocean flow (mm H2O/s). Used in the water balance equation in `BalanceCheckMod` (see [conservation.md](conservation.md)).
- Updates to `col_ws%h2osoi_liq(c,nlevsoi)`, `col_ws%wa(c)`, `soilhydrology_vars%zwt_col(c)`.

The companion sink `col_wf%qflx_h2oocn_drain` (drainage from inundation that goes to ocean) and `col_wf%qflx_ice_runoff_xs` are also new flux fields used in the closed water-balance equation.

## `HydrologyDrainage` and `HydrologyNoDrainage` — new `ocn2lnd_vars` argument

`HydrologyDrainage` (`biogeophys/HydrologyDrainageMod.F90:38-44`) at `d40b8431` is the Phase-2 hydrology driver. Its signature now includes `ocn2lnd_vars`:

```fortran
subroutine HydrologyDrainage(bounds,           &
     num_nolakec, filter_nolakec,              &
     num_hydrologyc, filter_hydrologyc,        &
     num_urbanc, filter_urbanc,                &
     num_do_smb_c, filter_do_smb_c,            &
     atm2lnd_vars, glc2lnd_vars, ocn2lnd_vars, &  ! ocn2lnd_vars is new at d40b8431
     soilhydrology_vars, soilstate_vars )
```

The body:

1. Optional `ELMVICMap` when `use_vichydro` is true.
2. `Drainage` if not using VSFM.
3. `Drainage_To_OCN` when `use_ocn_lnd_one_way = .true.`.
4. IM2 `qflx_to_downhill` redistribution when `use_IM2_hillslope_hydrology`.
5. BeTR pre/post-diagnostic flux retrievals (guarded by `use_betr`).
6. Update `h2osoi_vol` for each layer and compute `endwb(c) = h2ocan + h2osno + h2osfc + wa + sum(h2osoi_ice + h2osoi_liq)` for the column water budget closure.

`HydrologyNoDrainage` (`biogeophys/HydrologyNoDrainageMod.F90:47-50`) is the Phase-1 driver; its signature also added `ocn2lnd_vars`. Its calling sequence:

```
-> SnowWater            change of snow mass, snow water onto soil
-> SurfaceRunoff        surface runoff (with polygon and IM2 branches)
-> Infiltration         infiltration into surface soil layer (with ocn2lnd_vars)
-> SoilWater            soil water movement between layers
     -> Tridiagonal     tridiagonal matrix solution
-> Drainage             subsurface runoff [deferred to HydrologyDrainage]
-> SnowCompaction       compaction of snow layers (firn-aware when use_firn_*)
-> CombineSnowLayers
-> DivideSnowLayers
```

`HydrologyNoDrainage` also updates `soilpsi_col`, `eff_porosity_col`, and the derived 10 cm / 17 cm soil liquid+ice diagnostics, and handles the FAN (ammonia volatilization) diagnostic save of `h2osoi_liq` in the top layer before/after soil water movement. Branches at `HydrologyNoDrainageMod.F90:303` use `use_firn_percolation_and_compaction` (instead of `use_extrasnowlayers`); the soil/crop accessor at line 454 is `col_pp%is_soil(c) .or. col_pp%is_crop(c)`.

## Water-movement state: `soilhydrology_type`

Defined in `biogeophys/SoilHydrologyType.F90:28-`. Selected members:

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

## Soil property state: `soilstate_type`

Defined at `biogeophys/SoilStateType.F90:36-`. Selected hydraulic properties (all on column, typically `(nlevgrnd)` unless noted):

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
| `ar_col` | **New at d40b8431**: anisotropic ratio `(begc:endc, nlevgrnd)`, default 25.0 |
| `cellclay_col`, `cellsand_col`, `cellgrvl_col` | Soil texture per layer (used by `Drainage_To_OCN` and `SedYieldMod`) |

`soilpsi_col` is updated every timestep in `HydrologyNoDrainage` using `psi = -sucsat*(h2osoi_liqvol/watsat)^(-bsw)` with `e_ice` ice impedance, and forms the primary soil-water-potential input to N/P uptake and decomposition.

## Interfaces with other subsystems

- **Canopy fluxes** — `qflx_rootsoi_col` is the transpiration sink term fed into `SoilWater`. It is filled by `Compute_EffecRootFrac_And_VertTranSink` from the transpiration `qflx_tran_veg` and the `rootr` distribution. `soilpsi_col` produced in `HydrologyNoDrainage` feeds back into the canopy `btran` water-stress factor that scales stomatal conductance in `CanopyFluxesMod`; see `biogeophys/canopy_fluxes.md`.
- **Snow hydrology** — `SnowWater` (called from `HydrologyNoDrainage`) determines `qflx_top_soil`, the top boundary for `SurfaceRunoff` and `Infiltration`. Snow melt appears as part of `qflx_top_soil`.
- **Soil thermal** — `h2osoi_liq`, `h2osoi_ice` and `soilpsi_col` are inputs to `SoilThermProp` in `SoilTemperatureMod` (thermal conductivity and heat capacity). Frozen liquid produces latent heat that modifies `h2osoi_liq/ice` via `Phasechange_beta`.
- **Polygonal-tundra physics** — `SurfaceRunoff` reads `lun_pp%ispolygon(l)` (set by `use_polygonal_tundra`) to zero `qflx_surf` over polygon columns; this couples to `excess_ice`, `iwp_subsidence`, `frac_melted`, `iwp_microrel` updated by `ActiveLayerMod` (see [soil_temperature.md](soil_temperature.md)).
- **Ocean coupling** — `Drainage_To_OCN` reads `ocn2lnd_vars%ssh_grc(g)` and writes `qflx_lnd2ocn`. The water balance check in `BalanceCheckMod` (see [conservation.md](conservation.md)) consumes `qflx_lnd2ocn`, `qflx_h2oocn_drain`, and `qflx_ice_runoff_xs`.
- **IM2 hillslope hydrology** — `SurfaceRunoff` produces `qflx_from_uphill`; `HydrologyDrainage` (or its companion) produces `qflx_to_downhill`. Both feed the topounit-level `top_ws%from_uphill(t)` accumulator updated in `BalanceCheckMod` (see [conservation.md](conservation.md)).
- **Biogeochemistry** — `soilpsi_col`, `soilliq_col`, `soilice_col`, `watfc_col` drive decomposition temperature/moisture limiters in the CN decomposition cascade (see `CNDecompCascade*`).
- **Lake hydrology** — lake soil layers share `soilstate_type`; lake-specific soil water is handled by `LakeHydrologyMod`. See `biogeophys/lake.md`.

## Notes and gotchas

- Length units: `SoilWater` works in millimeters internally while `SoilTemperature` works in meters. The Richards solver converts `z`, `dz`, `zi` to `zmm`, `dzmm`, `zimm` at the top of `soilwater_zengdecker2009`.
- `origflag` (`soilhydrology_vars%origflag`) selects legacy versus updated expressions for a few quantities (`dsmpdw` expression, `s_node` averaging) — see `SoilWaterMovementMod.F90:555-559` and `SurfaceRunoff` in `SoilHydrologyMod`.
- `use_var_soil_thick` forces the aquifer layer into a purely passive mass-conservation role and triggers the variable-bottom `Tridiagonal_sr_with_var_bottom` solver.
- The factory-style retention curve machinery is wired but not actively called by `soilwater_zengdecker2009`, which inlines Clapp-Hornberger for performance / GPU offload.
- `use_ocn_lnd_one_way` is independent of `use_polygonal_tundra` and `use_IM2_hillslope_hydrology`. Default behavior with all three flags off is identical to the prior version's algebra (with renumbered subroutine line citations).
