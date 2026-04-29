---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# ELM Biogeophysics Subsystem Overview

The biogeophysics subsystem under `components/elm/src/biogeophys/` contains **54 Fortran source files** (`*.F90`) that compute the coupled exchange of energy, water, momentum, and trace gases between the land surface (soil, snow, vegetation, lake, urban, glacier, and ocean-coupled surfaces) and the atmosphere. Relative to ELM's overall structure, this is the "physics" layer that runs every time step regardless of whether biogeochemistry (BGC), CN, CNP, or FATES is active.

When FATES is enabled (`use_fates = .true.`), the biogeophysics layer still drives radiation, aerodynamic resistances, and the canopy energy-balance solver; it simply hands off leaf-level photosynthesis and stomatal conductance to FATES rather than to the ELM-native `PhotosynthesisMod`. The relevant call sites are `wrap_photosynthesis` at `CanopyFluxesMod.F90:911`, `wrap_btran` at `CanopyFluxesMod.F90:591`, and `wrap_hydraulics_drive` at `CanopyFluxesMod.F90:1322`.

## What lives in biogeophys

The 54 modules group into **twelve functional clusters**:

| Cluster | Key modules | What it computes |
|---|---|---|
| Radiation and albedo | `SurfaceAlbedoMod`, `SurfaceRadiationMod`, `SnowSnicarMod`, `SolarAbsorbedType`, `SurfaceAlbedoType` | Two-stream canopy radiation, SNICAR snow optics, absorbed SW by vegetation/ground/snow layers, slope/aspect-corrected cosine of incidence (`cosinc_col`) when `use_finetop_rad = .true.` |
| Surface fluxes (veg) | `CanopyFluxesMod`, `BareGroundFluxesMod`, `SoilFluxesMod` | Sensible, latent, momentum fluxes for vegetated and bare-soil patches; leaf temperature solve |
| Surface fluxes (lake) | `LakeFluxesMod`, `LakeTemperatureMod`, `LakeHydrologyMod`, `LakeStateType`, `LakeCon` | Lake-surface energy and water budget |
| Surface fluxes (urban) | `UrbanFluxesMod`, `UrbanRadiationMod`, `UrbanAlbedoMod`, `UrbanParamsType` | Urban canyon radiation, turbulent fluxes over roof/walls/road |
| Photosynthesis | `PhotosynthesisMod`, `PhotosynthesisType` | Farquhar/Ball-Berry leaf photosynthesis (ELM-native; bypassed when `use_fates = .true.`) |
| Canopy hydrology/temperature | `CanopyHydrologyMod`, `CanopyStateType`, `CanopyTemperatureMod`, `RootBiophysMod`, `QSatMod`, `DaylengthMod` | Canopy interception, wet fraction, ground-surface relative humidity, root profiles, saturation vapor pressure |
| Aerodynamics and resistances | `FrictionVelocityMod`, `FrictionVelocityType`, `SurfaceResistanceMod`, `SoilMoistStressMod` | Monin-Obukhov similarity, soil-evap beta, transpiration wetness factor (btran) |
| Soil thermal | `SoilTemperatureMod`, `ActiveLayerMod`, `TemperatureType`, `TridiagonalMod`, `BandDiagonalMod` | Heat diffusion through soil/snow/litter column, permafrost active layer (with ice-wedge polygon and excess-ice extensions when `use_polygonal_tundra`) |
| Soil water | `SoilHydrologyMod`, `SoilHydrologyType`, `SoilStateType`, `SoilWaterMovementMod`, `SoilWaterRetentionCurveMod`, `SoilWaterRetentionCurveClappHornberg1978Mod`, `SoilWaterRetentionCurveFactoryMod`, `HydrologyDrainageMod`, `HydrologyNoDrainageMod` | Richards' equation, Clapp-Hornberger retention curve, drainage, runoff, ocean-lateral coupling (`Drainage_To_OCN` when `use_ocn_lnd_one_way`), IM2 hillslope hydrology when `use_IM2_hillslope_hydrology` |
| Snow | `SnowHydrologyMod`, `SnowSnicarMod` | Multi-layer snow mass, compaction, melt, layer (de)combination, SNICAR optics; firn percolation/compaction when `use_firn_percolation_and_compaction` |
| Aerosol and erosion | `AerosolMod`, `AerosolType`, `SedYieldMod`, `SedFluxType` | Aerosol deposition onto snow, soil erosion by water |
| State types and conservation | `WaterStateType`, `WaterfluxType`, `EnergyFluxType`, `TotalWaterAndHeatMod`, `WaterBudgetMod`, `BalanceCheckMod` | Prognostic/diagnostic water and energy state containers; column-level conservation checks |

Module count verified via `ls components/elm/src/biogeophys/*.F90 | wc -l` (54 at `d40b8431`, identical to `60d9aad`).

## New namelist features at d40b8431

Five namelist switches added between `60d9aad` and `d40b8431` thread invasive code paths through the biogeophysics modules. All five default to `.false.`, so out-of-the-box behavior matches the prior version.

| Flag | Defined at | What it activates |
|---|---|---|
| `use_finetop_rad` | `elm_varctl.F90:404` | Slope/aspect-corrected cosine of solar incidence (`cosinc_col`) used by SNICAR, surface albedo, surface radiation, soil fluxes, urban radiation, and longwave under canopy |
| `use_polygonal_tundra` | `elm_varctl.F90:418` | Ice-wedge polygon (IWP) landunits (`ilowcenpoly`, `iflatcenpoly`, `ihighcenpoly`), `excess_ice` tracking, microtopographic relief in `ActiveLayerMod`, `altmax_1989` and `altmax_ever` fields |
| `use_IM2_hillslope_hydrology` | `elm_varctl.F90:482` | Subgrid hillslope lateral flow between columns/topounits (`qflx_from_uphill`, `qflx_to_downhill`); NGEE-Arctic infrastructure |
| `use_ocn_lnd_one_way` | `elm_varctl.F90:578` | Ocean-to-land coupling. New `ocn2lnd_vars` argument threaded through `HydrologyDrainage`, `HydrologyNoDrainage`, `Infiltration`, `Drainage`; new public routine `Drainage_To_OCN` (`SoilHydrologyMod.F90:1776-1986`) |
| `use_firn_percolation_and_compaction` | `elm_varctl.F90:394` | Firn-mode percolation, compaction, snow-cap mass scaling, refreeze grain radius. Replaces `use_extrasnowlayers` at most use sites; both flags now coexist |
| `use_T_rho_dependent_snowthk` | `elm_varctl.F90:399` | T- and density-dependent snow thermal conductivity in `SoilThermProp` (alternative to Jordan 1991) |

Two API generalizations also propagate through the layer:

- `crop()`, `nfixer()`, `iscft()` PFT-attribute accessors (in `pftvarcon`) replace the hard-coded `nsoybean`, `nsoybeanirrig`, `nc4_grass` PFT-index comparisons. Affects `CanopyFluxesMod.F90:900-901, 941-942` and `SedYieldMod.F90:221, 269`.
- Column-type accessors `col_pp%is_soil(c)`, `col_pp%is_crop(c)`, `col_pp%is_lake(c)` and patch-level `veg_pp%is_on_soil_col(p)`, `veg_pp%is_on_crop_col(p)` replace `lun_pp%itype(l) == istsoil`/`istcrop`/`istdlak` checks across most modules. For hybrid landunits (notably ice-wedge polygon landunits, which contain soil columns under a polygon landunit type), the new `is_*` accessors return `true` while the old landunit-type comparison would return `false`.

## Data flow (one time step)

```
t_n (start) ──► SurfaceAlbedo ──► SurfaceRadiation ──► CanopyTemperature
                (next step's       (absorbed SW                │
                 albedo & radiation by veg + ground,           │
                 transfer profile;  sets sabv, sabg)           │
                 cosinc_col when                               ▼
                 use_finetop_rad)                       CanopyFluxes (vegetated patches)
                                                        ├── FrictionVelocity (Monin-Obukhov)
                                                        ├── Photosynthesis (Farquhar/Ball-Berry)
                                                        │     or alm_fates%wrap_photosynthesis
                                                        └── solves t_veg Newton-Raphson
                                                       BareGroundFluxes (non-veg patches)
                                                       LakeFluxes / UrbanFluxes (special LUs)
                                                              │
                                                              ▼
                                                       SoilFluxes ──► SoilTemperature
                                                       (ground T         (multi-layer
                                                        update;           heat solve;
                                                        slope-corrected   T-rho snow
                                                        when             conductivity
                                                        use_finetop_rad)  when
                                                                          use_T_rho_dependent_snowthk)
                                                              │
                                                              ▼
                                                       CanopyHydrology ──► SnowHydrology
                                                        (interception,      (compaction,
                                                         throughfall,       melt, layers;
                                                         dew)               firn physics
                                                                            when use_firn_*)
                                                              │
                                                              ▼
                                                       SoilHydrology (Richards, drainage,
                                                                      Drainage_To_OCN when
                                                                      use_ocn_lnd_one_way,
                                                                      IM2 hillslope when
                                                                      use_IM2_hillslope_hydrology)
                                                       BalanceCheck (conservation)
                                                              │
                                                              ▼
                                                            t_{n+1}
```

## Per-topic documents

| Doc | Scope |
|---|---|
| [radiation.md](radiation.md) | Surface albedo, two-stream canopy radiation, SNICAR snow optics, absorbed SW partitioning; `cosinc_col` slope-correction |
| [canopy_fluxes.md](canopy_fluxes.md) | Canopy, bare-ground, urban, lake turbulent fluxes; Monin-Obukhov; Farquhar/Ball-Berry photosynthesis (ELM-native path); slope-corrected `eflx_soil_grnd` |
| [canopy_hydrology.md](canopy_hydrology.md) | Canopy interception, wet fraction, root profiles, `QSat`, daylength, canopy state container with new `altmax_1989`, `altmax_ever` |
| [snow.md](snow.md) | Multi-layer snow model, compaction, layer combination/division, snow aging; firn-mode constants |
| [soil_temperature.md](soil_temperature.md) | Soil/snow/litter heat diffusion, phase change, active layer with polygonal-tundra extensions; T-rho snow conductivity |
| [soil_hydrology.md](soil_hydrology.md) | Richards' equation, Clapp-Hornberger retention, drainage, runoff; `Drainage_To_OCN` and IM2 hillslope flow |
| [lake.md](lake.md) | Lake-specific thermodynamics and hydrology |
| [urban.md](urban.md) | Urban canyon radiation and fluxes |
| [aerosol_and_erosion.md](aerosol_and_erosion.md) | Aerosol deposition, sediment erosion |
| [conservation.md](conservation.md) | `WaterStateType`, `EnergyFluxType`, `BalanceCheckMod`, `TotalWaterAndHeatMod`; updated water-balance equation with six new flux terms |

## FATES vs ELM-native split

`use_fates` (a namelist variable read in `elm_varctl`) selects which path provides leaf-level rates:

- **`use_fates = .false.`** — `CanopyFluxesMod` calls `Photosynthesis` (or `PhotosynthesisHydraulicStress`) in `PhotosynthesisMod` once per sunlit/shaded stream. This is the legacy CLM4.5/CLM5 path.
- **`use_fates = .true.`** — `CanopyFluxesMod` calls `alm_fates%wrap_photosynthesis(...)` instead (`biogeophys/CanopyFluxesMod.F90:911`), skipping both `Photosynthesis` and `Fractionation`. Radiation, Monin-Obukhov, and the leaf-temperature Newton iteration still come from ELM's biogeophysics layer.

ELM at `d40b8431` is paired with FATES at commit `e027a40` (sci.1.91.1_api.43.1.0). The carbon and stocks coupling routines `wrap_FatesAtmosphericCarbonFluxes` and `wrap_FatesCarbonStocks` are called from `EcosystemDynMod.F90:268-269`.

Everything documented in [radiation.md](radiation.md), [canopy_fluxes.md](canopy_fluxes.md) (except the Farquhar equations section), [canopy_hydrology.md](canopy_hydrology.md), and [snow.md](snow.md) applies regardless of whether FATES is active.

## Key shared data containers

These `type, public` containers are read and written by multiple biogeophys modules. They are documented alongside the algorithms that own them.

| Container | Defined in | Used by |
|---|---|---|
| `surfalb_type` | `SurfaceAlbedoType.F90:59` | Radiation, canopy fluxes, photosynthesis. Adds `cosinc_col(:)` at line 62 (active when `use_finetop_rad = .true.`) |
| `solarabs_type` | `SolarAbsorbedType.F90:16` | Radiation -> canopy fluxes (absorbed SW). Adds `fsr_vis_d_patch`, `fsr_vis_i_patch` history fields at lines 57-58 |
| `canopystate_type` | `CanopyStateType.F90:36` | Radiation, fluxes, hydrology, BGC. Adds `altmax_1989_col`, `altmax_ever_col`, `altmax_1989_indx_col`, `altmax_ever_indx_col` at lines 68-71. Adds `InitAccBuffer`, `InitAccVars`, `UpdateAccVars` procedures at lines 85-87 |
| `frictionvel_type` | `FrictionVelocityType.F90:44` | Canopy fluxes, bare-ground fluxes, dust. Adds `num_iter_patch`, `rah_above_patch`, `rah_below_patch` (and `raw_*`, `ustar_patch`, `obu_patch`, `vpd_patch` etc.) for history output at lines 44-58 |
| `photosyns_type` | `PhotosynthesisType.F90:30` | Photosynthesis, canopy fluxes. Adds `vcmax25_top_patch` history field |
| `energyflux_type` | `EnergyFluxType.F90:19` | Fluxes, soil temperature, conservation. Adds `btran_min_patch`, `btran_min_inst_patch` daily-min accumulator at lines 92-93 (with `InitAccBuffer`, `InitAccVars`, `UpdateAccVars` procedures at lines 133-135) |
| `waterflux_type` | `WaterfluxType.F90:20` | Hydrology, fluxes, conservation. Adds `qflx_lnd2ocn`, `qflx_h2oocn_drain`, `qflx_from_uphill`, `qflx_to_downhill`, `qflx_ice_runoff_xs`, `qflx_glcice_diag`, `qflx_glcice_frz_diag` |

## Calling cadence

- **Every time step:** `SurfaceRadiation` -> `CanopyTemperature` -> `CanopyFluxes`/`BareGroundFluxes`/`UrbanFluxes`/`LakeFluxes` -> `SoilFluxes` -> `SoilTemperature` -> `CanopyHydrology` -> `SnowHydrology` -> `SoilHydrology` (with `Drainage_To_OCN` when `use_ocn_lnd_one_way`).
- **Every time step, but one step ahead:** `SurfaceAlbedo` is called with `nextsw_cday` to stage albedos for the next incoming radiation step (`SurfaceAlbedoMod.F90:59`).
- **Daily (accumulator):** Daylength updates used by CN/CNP phenology (`DaylengthMod.F90`). Daily-min `btran` accumulator (`EnergyFluxType%UpdateAccVars`).

This staging is why the Newton-Raphson leaf temperature solve in `CanopyFluxes` uses `t_grnd` from the previous step.

## Conventions across the subsystem

- Grid hierarchy: `gridcell -> topounit -> landunit -> column -> patch/pft`. Biogeophysics operates mostly at patch and column levels, using `filter_nolakec`, `filter_nolakep`, `filter_vegsol`, etc., to skip landunits that need special treatment (lake, urban, glacier, ice-wedge polygon).
- Two-band radiation: `numrad = 2` (1 = VIS, 2 = NIR), set in `elm_varpar`.
- Snow: up to 5 layers by default, or 16 with `use_extrasnowlayers = .true.` (`SnowHydrologyMod.F90:849, 1044`). **Note:** at `d40b8431`, `use_extrasnowlayers` only controls layer count; the substantive firn physics (compaction, percolation, refreeze grain radius, snow-cap aerosol scaling) is now gated on `use_firn_percolation_and_compaction`.
- Energy closure: every flux routine writes into `energyflux_vars`; `BalanceCheckMod` verifies at the end of the time step.

For algorithmic details see the per-topic documents listed above.
