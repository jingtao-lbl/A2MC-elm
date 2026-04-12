---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# ELM Biogeophysics Subsystem Overview

The biogeophysics subsystem under `components/elm/src/biogeophys/` contains **54 Fortran source files** (`*.F90`) that compute the coupled exchange of energy, water, momentum, and trace gases between the land surface (soil, snow, vegetation, lake, urban, and glacier surfaces) and the atmosphere. Relative to ELM's overall structure, this is the "physics" layer that runs every time step regardless of whether biogeochemistry (BGC), CN, CNP, or FATES is active.

When FATES is enabled (`use_fates = .true.`), the biogeophysics layer still drives radiation, aerodynamic resistances, and the canopy energy-balance solver; it simply hands off leaf-level photosynthesis and stomatal conductance to FATES rather than to the ELM-native `PhotosynthesisMod`.

## What lives in biogeophys

The 54 modules group into **twelve functional clusters**:

| Cluster | Key modules | What it computes |
|---|---|---|
| Radiation and albedo | `SurfaceAlbedoMod`, `SurfaceRadiationMod`, `SnowSnicarMod`, `SolarAbsorbedType`, `SurfaceAlbedoType` | Two-stream canopy radiation, SNICAR snow optics, absorbed SW by vegetation/ground/snow layers |
| Surface fluxes (veg) | `CanopyFluxesMod`, `BareGroundFluxesMod`, `SoilFluxesMod` | Sensible, latent, momentum fluxes for vegetated and bare-soil patches; leaf temperature solve |
| Surface fluxes (lake) | `LakeFluxesMod`, `LakeTemperatureMod`, `LakeHydrologyMod`, `LakeStateType`, `LakeCon` | Lake-surface energy and water budget |
| Surface fluxes (urban) | `UrbanFluxesMod`, `UrbanRadiationMod`, `UrbanAlbedoMod`, `UrbanParamsType` | Urban canyon radiation, turbulent fluxes over roof/walls/road |
| Photosynthesis | `PhotosynthesisMod`, `PhotosynthesisType` | Farquhar/Ball-Berry leaf photosynthesis (ELM-native; bypassed when `use_fates=.true.`) |
| Canopy hydrology/temperature | `CanopyHydrologyMod`, `CanopyStateType`, `CanopyTemperatureMod`, `RootBiophysMod`, `QSatMod`, `DaylengthMod` | Canopy interception, wet fraction, ground-surface relative humidity, root profiles, saturation vapor pressure |
| Aerodynamics and resistances | `FrictionVelocityMod`, `FrictionVelocityType`, `SurfaceResistanceMod`, `SoilMoistStressMod` | Monin-Obukhov similarity, soil-evap beta, transpiration wetness factor (btran) |
| Soil thermal | `SoilTemperatureMod`, `ActiveLayerMod`, `TemperatureType`, `TridiagonalMod`, `BandDiagonalMod` | Heat diffusion through soil/snow/litter column, permafrost active layer |
| Soil water | `SoilHydrologyMod`, `SoilHydrologyType`, `SoilStateType`, `SoilWaterMovementMod`, `SoilWaterRetentionCurveMod`, `SoilWaterRetentionCurveClappHornberg1978Mod`, `SoilWaterRetentionCurveFactoryMod`, `HydrologyDrainageMod`, `HydrologyNoDrainageMod` | Richards' equation, Clapp-Hornberger retention curve, drainage, runoff |
| Snow | `SnowHydrologyMod`, `SnowSnicarMod` | Multi-layer snow mass, compaction, melt, layer (de)combination, SNICAR optics |
| Aerosol and erosion | `AerosolMod`, `AerosolType`, `SedYieldMod`, `SedFluxType` | Aerosol deposition onto snow, soil erosion by water |
| State types and conservation | `WaterStateType`, `WaterfluxType`, `EnergyFluxType`, `TotalWaterAndHeatMod`, `WaterBudgetMod`, `BalanceCheckMod` | Prognostic/diagnostic water and energy state containers; column-level conservation checks |

Module counts verified via `ls components/elm/src/biogeophys/*.F90 | wc -l` (54).

## Data flow (one time step)

```
t_n (start) ──► SurfaceAlbedo ──► SurfaceRadiation ──► CanopyTemperature
                (next step's       (absorbed SW                │
                 albedo & radiation by veg + ground,           │
                 transfer profile)  sets sabv, sabg)           ▼
                                                       CanopyFluxes (vegetated patches)
                                                        ├── FrictionVelocity (Monin-Obukhov)
                                                        ├── Photosynthesis (Farquhar/Ball-Berry)
                                                        └── solves t_veg Newton-Raphson
                                                       BareGroundFluxes (non-veg patches)
                                                       LakeFluxes / UrbanFluxes (special LUs)
                                                              │
                                                              ▼
                                                       SoilFluxes ──► SoilTemperature
                                                       (ground T         (multi-layer
                                                        update)           heat solve)
                                                              │
                                                              ▼
                                                       CanopyHydrology ──► SnowHydrology
                                                        (interception,      (compaction,
                                                         throughfall,       melt, layers)
                                                         dew)
                                                              │
                                                              ▼
                                                       SoilHydrology (Richards, drainage)
                                                       BalanceCheck (conservation)
                                                              │
                                                              ▼
                                                            t_{n+1}
```

## Per-topic documents

| Doc | Scope |
|---|---|
| [radiation.md](radiation.md) | Surface albedo, two-stream canopy radiation, SNICAR snow optics, absorbed SW partitioning |
| [canopy_fluxes.md](canopy_fluxes.md) | Canopy, bare-ground, urban, lake turbulent fluxes; Monin-Obukhov; Farquhar/Ball-Berry photosynthesis (ELM-native path) |
| [canopy_hydrology.md](canopy_hydrology.md) | Canopy interception, wet fraction, root profiles, `QSat`, daylength, canopy state container |
| [snow.md](snow.md) | Multi-layer snow model, compaction, layer combination/division, snow aging (links to SNICAR) |
| [soil_temperature.md](soil_temperature.md) | Soil/snow/litter heat diffusion, phase change, active layer (produced by companion agent) |
| [soil_hydrology.md](soil_hydrology.md) | Richards' equation, Clapp-Hornberger retention, drainage, runoff (companion agent) |
| [lake.md](lake.md) | Lake-specific thermodynamics and hydrology (companion agent) |
| [urban.md](urban.md) | Urban canyon radiation and fluxes (companion agent) |
| [aerosol_and_erosion.md](aerosol_and_erosion.md) | Aerosol deposition, sediment erosion (companion agent) |
| [conservation.md](conservation.md) | `WaterStateType`, `EnergyFluxType`, `BalanceCheckMod`, `TotalWaterAndHeatMod` (companion agent) |

## FATES vs ELM-native split

`use_fates` (a namelist variable read in `elm_varctl`) selects which path provides leaf-level rates:

- **`use_fates = .false.`** — `CanopyFluxesMod` calls `Photosynthesis` (or `PhotosynthesisHydraulicStress`) in `PhotosynthesisMod` once per sunlit/shaded stream. This is the legacy CLM4.5/CLM5 path.
- **`use_fates = .true.`** — `CanopyFluxesMod` calls `alm_fates%wrap_photosynthesis(...)` instead (`biogeophys/CanopyFluxesMod.F90:880`), skipping both `Photosynthesis` and `Fractionation`. Radiation, Monin-Obukhov, and the leaf-temperature Newton iteration still come from ELM's biogeophysics layer.

Everything documented in [radiation.md](radiation.md), [canopy_fluxes.md](canopy_fluxes.md) (except the Farquhar equations section), [canopy_hydrology.md](canopy_hydrology.md), and [snow.md](snow.md) applies regardless of whether FATES is active.

## Key shared data containers

These `type, public` containers are read and written by multiple biogeophys modules. They are documented alongside the algorithms that own them.

| Container | Defined in | Used by |
|---|---|---|
| `surfalb_type` | `SurfaceAlbedoType.F90:59` | Radiation, canopy fluxes, photosynthesis |
| `solarabs_type` | `SolarAbsorbedType.F90:16` | Radiation -> canopy fluxes (absorbed SW) |
| `canopystate_type` | `CanopyStateType.F90` | Radiation, fluxes, hydrology, BGC |
| `frictionvel_type` | `FrictionVelocityType.F90` | Canopy fluxes, bare-ground fluxes, dust |
| `photosyns_type` | `PhotosynthesisType.F90` | Photosynthesis, canopy fluxes |
| `energyflux_type` | `EnergyFluxType.F90:19` | Fluxes, soil temperature, conservation |
| `waterflux_type` | `WaterfluxType.F90:20` | Hydrology, fluxes, conservation |

## Calling cadence

- **Every time step:** `SurfaceRadiation` -> `CanopyTemperature` -> `CanopyFluxes`/`BareGroundFluxes`/`UrbanFluxes`/`LakeFluxes` -> `SoilFluxes` -> `SoilTemperature` -> `CanopyHydrology` -> `SnowHydrology` -> `SoilHydrology`.
- **Every time step, but one step ahead:** `SurfaceAlbedo` is called with `nextsw_cday` to stage albedos for the next incoming radiation step (`SurfaceAlbedoMod.F90:59`).
- **Daily (accumulator):** Daylength updates used by CN/CNP phenology (`DaylengthMod.F90`).

This staging is why the Newton-Raphson leaf temperature solve in `CanopyFluxes` uses `t_grnd` from the previous step (see note in `CanopyFluxesMod.F90:77-78`).

## Conventions across the subsystem

- Grid hierarchy: `gridcell -> topounit -> landunit -> column -> patch/pft`. Biogeophysics operates mostly at patch and column levels, using `filter_nolakec`, `filter_nolakep`, `filter_vegsol`, etc., to skip landunits that need special treatment (lake, urban, glacier).
- Two-band radiation: `numrad = 2` (1 = VIS, 2 = NIR), set in `elm_varpar`.
- Snow: up to 5 layers by default, or 16 with `use_extrasnowlayers = .true.` (`SnowHydrologyMod.F90:626`).
- Energy closure: every flux routine writes into `energyflux_vars`; `BalanceCheckMod` verifies at the end of the time step.

For algorithmic details see the per-topic documents listed above.
