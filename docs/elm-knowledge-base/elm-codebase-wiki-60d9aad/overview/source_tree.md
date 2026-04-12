---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Source Tree Layout

This page describes the directory layout of `components/elm/src/` at commit `60d9aad`. The tree contains 239 Fortran modules (`.F90`), one shared `CMakeLists.txt`, one `README.unit_testing` note, and the `external_models/` and `.ipynb_checkpoints/` subtrees that are excluded from this wiki.

## Directory diagram

```
components/elm/src/
├── CMakeLists.txt
├── README.unit_testing
├── biogeochem/          (74 .F90)   C/N/P/CH4/VOC/fire/crop biogeochemistry
├── biogeophys/          (54 .F90)   Energy, radiation, temperature, hydrology, snow, lake, urban
├── cpl/                 ( 6 .F90)   MCT/ESMF coupler entry points; field import/export
├── data_types/          (12 .F90)   Gridcell/topounit/landunit/column/vegetation derived types
├── dyn_subgrid/         (17 .F90)   Transient land cover: pftdyn, crop, harvest, FATES coupling
├── external_models/     (excluded — FATES source, documented separately)
├── main/                (63 .F90)   Driver, init/final, control flags, subgrid bookkeeping, I/O
└── utils/               (13 .F90)   Time manager, SPMD, domain, orbital, namelist helpers
```

**Total** `.F90` files in scope: **239** across 7 subdirectories.

## `main/` — driver, initialization, and shared bookkeeping (63 files)

The `main/` directory owns the **top-level calling sequence** and the **shared bookkeeping** that the other subsystems depend on. It includes:

- **Driver and lifecycle.** `elm_driver.F90` (the `elm_drv` entry point called every timestep; `main/elm_driver.F90:197`), `elm_initializeMod.F90` (`initialize1`/`initialize2`; `main/elm_initializeMod.F90:54,452`), `elm_finalizeMod.F90`, `elm_instMod.F90` (instantiation of physics-state derived types), and `elm_instance.F90` (multi-instance bookkeeping).
- **Global control and constants.** `elm_varctl.F90` (run-control flags such as `use_cn`, `use_fates`, `use_pflotran`), `elm_varcon.F90` (physical constants), `elm_varpar.F90` (vertical and PFT parameters), `elm_varsur.F90` (surface boundary data), `controlMod.F90` (namelist reader), `timeinfoMod.F90` (shared time-step variables).
- **Subgrid bookkeeping.** `decompMod.F90`, `decompInitMod.F90` (clumped domain decomposition), `subgridMod.F90`, `subgridAveMod.F90`, `subgridWeightsMod.F90`, `subgridRestMod.F90`, `initSubgridMod.F90`, `initGridCellsMod.F90`, `initVerticalMod.F90`, `filterMod.F90` (patch/column filters), `reweightMod.F90` (changes when subgrid weights change), plus the `*_varcon.F90` index modules (`landunit_varcon.F90`, `column_varcon.F90`, `topounit_varcon.F90`).
- **Accessors for subgrid levels.** `ColumnMod.F90`, `LandunitMod.F90`, `PatchMod.F90` hold procedures that unpack or apply state at a given subgrid level.
- **I/O.** `histFileMod.F90`, `histGPUMod.F90`, `restFileMod.F90` (history tapes and restart), `surfrdMod.F90`, `surfrdUtilsMod.F90` (surface dataset reading), `ndepStreamMod.F90`, `pdepStreamMod.F90`, `fanStreamMod.F90` (deposition streams), `organicFileMod.F90`, `paramUtilMod.F90`, `readParamsMod.F90`, `initInterp.F90` (initial-condition interpolation).
- **Coupling glue.** `atm2lndMod.F90`/`atm2lndType.F90`, `lnd2atmMod.F90`/`lnd2atmType.F90`, `glc2lndMod.F90`, `lnd2glcMod.F90`, `glcDiagnosticsMod.F90`, `elmfates_interfaceMod.F90`, `elmfates_paraminterfaceMod.F90`, `elm_interface_bgcType.F90`, `elm_interface_dataType.F90`, `elm_interface_thType.F90`, `elm_interface_funcsMod.F90`, `elm_interface_pflotranMod.F90`, `init_hydrology.F90`.
- **Utilities specific to main.** `abortutils.F90`, `accumulMod.F90`, `perfMod_GPU.F90`, `GetGlobalValuesMod.F90`, `FuncPedotransferMod.F90`, `pftvarcon.F90`, `soilorder_varcon.F90`, `SoilorderConType.F90`.

See the [`core/index.md`](../core/index.md) subsystem page for the calling-tree walkthrough.

## `biogeophys/` — physical climate of the land surface (54 files)

`biogeophys/` implements the **biogeophysical** physics. It owns the energy balance, radiation transfer, surface resistances, canopy and soil temperature, snow physics, soil hydrology (including Richards-equation solution), lake thermodynamics, and urban heat and moisture budgets.

Major functional groupings:

- **Energy balance and fluxes.** `BareGroundFluxesMod.F90`, `CanopyFluxesMod.F90`, `CanopyTemperatureMod.F90`, `SoilFluxesMod.F90`, `SoilTemperatureMod.F90`, `FrictionVelocityMod.F90`, `QSatMod.F90`, `DaylengthMod.F90`, `BalanceCheckMod.F90`, `TotalWaterAndHeatMod.F90`, `WaterBudgetMod.F90`.
- **Radiation.** `SurfaceAlbedoMod.F90`, `SurfaceRadiationMod.F90`, `SnowSnicarMod.F90`, `UrbanAlbedoMod.F90`, `UrbanRadiationMod.F90`.
- **Hydrology.** `CanopyHydrologyMod.F90`, `SnowHydrologyMod.F90`, `SoilHydrologyMod.F90`, `SoilWaterMovementMod.F90`, `SoilWaterRetentionCurveMod.F90` (abstract base) with the Clapp-Hornberg 1978 implementation and factory, `HydrologyDrainageMod.F90`, `HydrologyNoDrainageMod.F90`, `SoilMoistStressMod.F90`, `SurfaceResistanceMod.F90`, `RootBiophysMod.F90`.
- **Lake and urban.** `LakeCon.F90`, `LakeTemperatureMod.F90`, `LakeFluxesMod.F90`, `LakeHydrologyMod.F90`, `UrbanFluxesMod.F90`, `UrbanParamsType.F90`.
- **Aerosols and erosion.** `AerosolMod.F90`, `AerosolType.F90`, `SedYieldMod.F90`, `SedFluxType.F90`.
- **Numerical solvers.** `TridiagonalMod.F90`, `BandDiagonalMod.F90`, `ActiveLayerMod.F90`.
- **State derived types.** `CanopyStateType.F90`, `EnergyFluxType.F90`, `FrictionVelocityType.F90`, `PhotosynthesisType.F90`, `SoilHydrologyType.F90`, `SoilStateType.F90`, `SolarAbsorbedType.F90`, `SurfaceAlbedoType.F90`, `TemperatureType.F90`, `WaterStateType.F90`, `WaterfluxType.F90`, `LakeStateType.F90`, plus `PhotosynthesisMod.F90` (the A-gs computation itself).

See [`biogeophys/index.md`](../biogeophys/index.md) for the subsystem walkthrough.

## `biogeochem/` — carbon, nitrogen, phosphorus, methane, fire, crop (74 files)

`biogeochem/` contains ELM's ecosystem biogeochemistry. The module naming follows a few strong conventions:

- **Three-stage state updates** for each element. Carbon, nitrogen, and phosphorus each have three update stages: non-mortality (stage 1), mortality (stage 2), and harvest/products (stage 3). Hence `CarbonStateUpdate1Mod.F90`, `CarbonStateUpdate2Mod.F90`, `CarbonStateUpdate3Mod.F90`, and parallel modules for N (`NitrogenStateUpdate{1,2,3}Mod.F90`) and P (`PhosphorusStateUpdate{1,2,3}Mod.F90`).
- **BeTR variants** for tracer-transport coupling. When `use_betr` is true, the BeTR-aware modules (`CNAllocationBetrMod.F90`, `CNEcosystemDynBetrMod.F90`, `CNPhenologyBeTRMod.F90`, `CNGapMortalityBeTRMod.F90`, `CNNStateUpdate{1,2,3}BeTRMod.F90`) replace the default modules.
- **Decomposition cascade.** `DecompCascadeBGCMod.F90` and `DecompCascadeCNMod.F90` set up the transition coefficients; `SoilLittDecompMod.F90` runs the column-level decomposition; `SoilLittVertTranspMod.F90` handles vertical mixing; `VerticalProfileMod.F90` sets the vertical input profiles.
- **Phenology and allocation.** `PhenologyMod.F90`, `PhenologyFluxLimitMod.F90`, `AllocationMod.F90`, `GrowthRespMod.F90`, `MaintenanceRespMod.F90`, `GapMortalityMod.F90`, `RootDynamicsMod.F90`, `VegStructUpdateMod.F90`, `AnnualUpdateMod.F90`, `EcosystemDynMod.F90`, `SatellitePhenologyMod.F90`, `ComputeSeedMod.F90`, `CNDecompCascadeConType.F90`, `SpeciesMod.F90`.
- **Nitrogen and phosphorus dynamics.** `NitrogenDynamicsMod.F90`, `NitrifDenitrifMod.F90`, `PhosphorusDynamicsMod.F90`, `PlantMicKineticsMod.F90`, `CarbonIsoFluxMod.F90`, `C14DecayMod.F90`, `PrecisionControlMod.F90`, `CNBeTRIndicatorMod.F90`.
- **Crop.** `CropMod.F90`, `CropType.F90`, `CropHarvestPoolsMod.F90`, `WoodProductsMod.F90`, `CNStateType.F90` (crop prognostic state such as cropplant/harvdate), `FanMod.F90`, `FanUpdateMod.F90`.
- **Fire.** `FireMod.F90`, `FireMethodType.F90`, `FireDataBaseType.F90`, `FATESFireBase.F90`, `FATESFireDataMod.F90`, `FATESFireFactoryMod.F90`, `FATESFireNoDataMod.F90`.
- **Methane and erosion and VOC and dust.** `CH4Mod.F90`, `CH4varcon.F90`, `VOCEmissionMod.F90`, `MEGANFactorsMod.F90`, `DUSTMod.F90`, `DryDepVelocity.F90`, `ErosionMod.F90`.
- **State and budget types.** `CNCarbonStateType.F90`, `CNCarbonFluxType.F90`, `CNNitrogenStateType.F90`, `CNNitrogenFluxType.F90`, `PhosphorusStateType.F90`, `PhosphorusFluxType.F90`, `ChemStateType.F90`, `EcosystemBalanceCheckMod.F90`, `CNPBudgetMod.F90`, `SharedParamsMod.F90`, `LSparseMatMod.F90`.

See [`biogeochem/index.md`](../biogeochem/index.md) for the subsystem walkthrough.

## `dyn_subgrid/` — transient land cover (17 files)

`dyn_subgrid/` handles everything that happens when subgrid weights change between timesteps: reading transient datasets, adjusting weights, and conserving mass and energy as columns and patches gain or lose area.

- **Dataset readers.** `dynFileMod.F90`, `dynpftFileMod.F90`, `dyncropFileMod.F90`, `dynHarvestMod.F90`.
- **Driver and control.** `dynSubgridDriverMod.F90` (top-level), `dynSubgridControlMod.F90`, `dynTimeInfoMod.F90`.
- **Weight update and state adjustment.** `dynLandunitAreaMod.F90`, `dynPriorWeightsMod.F90`, `dynColumnStateUpdaterMod.F90`, `dynColumnTemplateMod.F90`, `dynInitColumnsMod.F90`, `dynPatchStateUpdaterMod.F90`, `dynSubgridAdjustmentsMod.F90`.
- **Conservation.** `dynConsBiogeochemMod.F90` (C & N conservation), `dynConsBiogeophysMod.F90` (water & energy conservation).
- **FATES coupling.** `dynEDMod.F90`.

See [`dyn_subgrid/index.md`](../dyn_subgrid/index.md) for the subsystem walkthrough.

## `data_types/` — derived-type skeletons for subgrid levels (12 files)

`data_types/` holds the **derived types** that define ELM's subgrid memory layout. Each of the five subgrid levels has a `*Type.F90` module (physical-properties side) and a `*DataType.F90` module (state/flux-variable instances):

| Level | Type (structure) | Instance container |
|---|---|---|
| Gridcell | `GridcellType.F90` | `GridcellDataType.F90` |
| Topounit | `TopounitType.F90` | `TopounitDataType.F90` |
| Landunit | `LandunitType.F90` | `LandunitDataType.F90` |
| Column | `ColumnType.F90` | `ColumnDataType.F90` |
| Vegetation (patch) | `VegetationType.F90` | `VegetationDataType.F90` |

In addition, `VegetationPropertiesType.F90` holds PFT-level parameters (traits, allometry, phenology) and `CNStateType.F90` holds CN-specific state shared across levels (including crop prognostic variables). The topounit level is ELM-specific — see `TopounitType.F90:1-7` for the documented hierarchy note.

## `utils/` — framework utilities (13 files)

`utils/` contains cross-cutting helpers that are not tied to any one physics subsystem:

- `elm_time_manager.F90` — time-step bookkeeping driven from the coupler.
- `spmdMod.F90`, `spmdGathScatMod.F90` — SPMD initialization and gather/scatter primitives.
- `domainMod.F90`, `domainLateralMod.F90` — surface-domain bookkeeping and lateral connectivity (PETSc-based lateral flow).
- `elm_varorb.F90` — orbital parameters passed to `shr_orb`.
- `elm_nlUtilsMod.F90`, `fileutils.F90`, `getdatetime.F90` — namelist/file/datetime helpers.
- `seq_drydep_mod_elm.F90` — ELM-local copy of the shared dry-deposition driver.
- `quadraticMod.F90`, `SimpleMathMod.F90`, `AnnualFluxDribbler.F90` — numerical utilities (quadratic solver, array math, once-per-year flux dribbling).

## `cpl/` — coupler interface (6 files)

`cpl/` is ELM's interface to the external coupler. It is deliberately thin and contains only what the coupler sees:

- **Driver entry points.** `lnd_comp_mct.F90` (MCT path; see `cpl/lnd_comp_mct.F90:63,415,670` for init/run/final) and `lnd_comp_esmf.F90` (ESMF path).
- **Field exchange.** `lnd_import_export.F90` routes coupler fields into ELM state and ELM state out to coupler fields. `elm_cpl_indices.F90` holds the field-index table.
- **Topounit disaggregation/downscaling.** `lnd_disagg_forc.F90` spreads gridcell forcing across topounits, and `lnd_downscale_atm_forcing.F90` applies topographic gradients (e.g., temperature lapse rates, precipitation scaling) to atmospheric forcing for each topounit.

Neither the coupler itself nor CIME are in scope for this wiki.

## Build and other non-source files

The `components/elm/src/` root also contains:

- **`CMakeLists.txt`** — the CMake file that collects sources from each subdirectory and hands them to the CIME build. Not documented here; consult CIME for build details.
- **`README.unit_testing`** — a one-line note describing how to run the ELM unit-test suite (its contents are effectively a single `run_tests.py` invocation using the CIME unit-testing tool). Unit tests proper live outside `src/` and are also out of scope.

## Naming conventions

A few conventions recur throughout the tree and are worth internalizing:

- **`*Mod.F90`** — a procedural module that exposes one or more physics subroutines. Most files end in `Mod.F90`.
- **`*Type.F90`** — a module whose primary purpose is defining a derived type (often a state or flux container). Examples in `data_types/`, `biogeophys/`, and `biogeochem/`.
- **`*DataType.F90`** — an instance-container module that allocates and initializes the variables of a derived type defined in the matching `*Type.F90`. Only used in `data_types/` for the five subgrid levels.
- **`*StateUpdate{1,2,3}Mod.F90`** — the three-stage state update pattern for C, N, and P (non-mortality, mortality, harvest/product).
- **`*Betr*.F90` or `*BeTR*.F90`** — the BeTR-coupled variant of a module, activated by `use_betr`.
- **`FATESFire*.F90`** — the ELM-side interface between FATES's fire model and the ELM fire-data framework.
- **`*varcon.F90`** — a module holding module-level constants or index sets (e.g., `landunit_varcon.F90`, `column_varcon.F90`, `topounit_varcon.F90`, `soilorder_varcon.F90`, `pftvarcon.F90`).

## Excluded subtrees

- **`external_models/`** — FATES source code. Documented in the separate FATES wiki.
- **`.ipynb_checkpoints/`** — Jupyter autosave artefacts; stale and ignored.

## Pointer to the full inventory

For a complete, one-line description of every module in every subdirectory, see [`../reference/module_inventory.md`](../reference/module_inventory.md).
