---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/` + `drivers/` (full repo)
**Last verified:** 2026-04-24
---

# Source Tree

A directory-by-directory tour of the EcoSIM repository at commit `2dea74d9`. File counts reflect `*.F90` / `*.f90` sources only (headers, CMake files, and notebooks are not counted). Total Fortran source: 182 files under `f90src/` + 28 files under `drivers/` = 210 files.

## Top-level layout

| Path | Contents |
|---|---|
| `f90src/` | EcoSIM core library. 23 top-level subdirectories, some with nested subfolders. 182 F90 files total. |
| `drivers/` | Executables and test programs. 8 subdirectories. 28 F90 files total. |
| `CMakeLists.txt` | Top-level CMake entry point. Declares project `ecosim`, version 0.1.0 (`CMakeLists.txt:6-9`). |
| `build_EcoSIM.sh` | Convenience shell script that configures and builds the project (`README.md:15`). |
| `Makefile` | Thin GNU Make wrapper (top-level convenience targets). |
| `README.md` | Top-level user-facing README with build instructions. |
| `cmake/` | `Modules/` (CMake helpers `set_up_platform`, `set_up_compilers`) and `Templates/` (`ecosim.cmake.in`). |
| `3rd-partylibs/` | Submodules for `hdf5/`, `netcdf-c/`, `netcdf-fortran/`, `zlib/` plus local `CMakeLists.txt`. Built when `ATS_ECOSIM` is not set. |
| `docker/` | `ubuntu-compiler.dockerfile` for building in a containerized Ubuntu image. |
| `python_tools/` | Analysis, diagnostics, and parameter-editor notebooks/scripts (~40 `.ipynb` / `.py` files). Not compiled. |
| `input_data/` | Default parameter NetCDF/CSV inputs: microbial parameters, PFT parameter tables, historic atmospheric GHG series. |
| `examples/` | Self-contained example runs (one directory per site: `Fen/`, `blodgett/`, `bare_soil/`, `RiceUSTWT/`, `DaLake/`, `Pond/`, `FireCA/`, `dryland_maize/`, `lake/`, `climeConst/`, `sample/`). Each contains input namelists and forcing. |
| `tests/` | Namelist fixtures and management NetCDF files used by `regression-tests/` and `drivers/tools/` (e.g., `example_nl`, `histtest_nl`, `pft_mgmnt_nl`, `pft_mgmt_Blodgett_v0_ex10.nc`). |
| `regression-tests/` | Python-based regression harness (`rtest_ecosim.py`, `mtest`, `Makefile`, `tests/` data). |
| `nc_config/` | NetCDF template configuration files. |

## `f90src/` subsystems

Counts below include nested subdirectories (e.g., `Geochem/Box_chem/` + `Geochem/Layers_chem/` = Geochem total). For the exhaustive module inventory, see [`reference/module_inventory.md`](../reference/module_inventory.md).

| Subsystem | Files | Purpose |
|---|---|---|
| `APIData/` | 1 | Data types exchanged through plant APIs (`PlantAPIData.F90`: "initialize data type for plant_radiation_type"). |
| `APIs/` | 7 | Thin wrappers that drivers and `EcoSIMAPI` call (`PlantMod`, `GeochemAPI`, `MicBGCAPI`, `PlantAPI`, `PlantAPI4Uptake`, `PlantCanAPI`, `SurfPhysAPI`). |
| `ATSUtils/` | 8 | ATS-coupling layer. Derived types, Fortran/C interop, scratch buffers, and a compiler-neutral wrapper. |
| `Balances/` | 7 | Column-scale bookkeeping: `RedistMod` (state update from fluxes), `RunoffBalMod`, `ErosionBalMod`, `LateralTranspMod`, `SoilLayerDynMod` (soil relayering), `TillageMixMod`, `RedistDataMod`. |
| `DebugTools/` | 1 | `DebugToolMod.F90` — `PrintInfo`/`DebugPrint` helpers used throughout. |
| `Disturbances/` | 6 | `FireMod`, `ErosionMod`, `FertilizerMod`, `SoilDisturbMod`, `PlantDisturbMod`, `EcosysWarmingMod` (soil/atmospheric/snow-exclusion warming, `f90src/Disturbances/EcosysWarmingMod.F90`). |
| `Ecosim_datatype/` | 32 | Field modules holding all allocatable state arrays (soil, canopy, snow, plant traits, fertilizer, grid, flags, SOM, sediment, surface, balance checks, history, etc.). See [`data_types/`](../data_types/index.md). |
| `Ecosim_mods/` | 4 | Historical ecosys-derived initialization: `InitAllocMod` (orchestrator), `StartsMod` ("code to initalize soil variables"), `StartqMod` (plant-side initialization; `public :: startq`), `StarteMod` ("INITIALIZES ALL SOIL CHEMISTRY VARIABLES"). |
| `Geochem/` | 6 | Split: `Box_chem/` (5 files: `ChemEquilibriaMod`, `SaltChemEquilibriaMod`, `GeoChemMathMod`, `InitSoluteMod`, `SoluteChemDataType`) + `Layers_chem/` (1 file: `SoluteMod` with `UreaHydrolysis`, `UpdateSoilFertlizer`). |
| `HydroTherm/` | 15 | Split into 4 nested subsystems: `CanopyPhys/` (1: `CanopyHydroMod`, `CanopyInterceptPrecip`), `PhysData/` (3: shared `HydroThermData`, `PhysPars`, `SoilPhysParaMod`), `SnowPhys/` (4: `SnowPhysMod`, `SnowBalanceMod`, `SnowTransportMod`, `SnowPhysData`), `SoilPhys/` (3: `WatsubMod` — water/energy balance, `WatsubDataMod`, `SoilHydroParaMod`), `SurfPhys/` (4: `SurfPhysMod`, `SurfLitterPhysMod`, `SurfPhysData`, `SurfPhysAPI`). |
| `IOutils/` | 12 | Namelist parsing, climate reading, management reading, restart, history tapes, and low-level file helpers. Includes `readimod` (site/topo input), `readsmod` (climate + soil forcing), `ClimReadMod`, `ReadManagementMod`, `MicrobeInfoMod`, `PlantInfoMod` (plant trait table reader), `RestartMod`, `HistFileMod`, `HistDataType`, `bhistMod`, `restUtilMod`, `ForcWriterMod`. |
| `Main/` | 2 | `InitEcoSIM.F90` (`InitModules`) and `EcoSIMDesctruct.F90` (`DestructEcoSIM`). |
| `Mesh/` | 2 | `GridConsts.F90` (shared constants), `GridMod.F90` (`SetMesh`/`SetMeshATS`). |
| `Microbial_bgc/` | 9 | Split: `Box_Micmodel/` (7 files: `MicBGCFGMod` — single-layer soil biological transformations, `MicAutoCplxFGMod` — autotroph complex, plus `MicFluxTypeMod`, `MicForcTypeMod`, `MicStateTraitTypeMod`, `MicrobMathFuncMod`, `MicrobeDiagTypes`) + `Layers_Micmodel/` (2 files: `SoilBGCNLayMod` — layered soil BGC, `InitSOMBGCMod`). |
| `Minimath/` | 3 | `LinearAlgebraMod`, `MiniFuncMod` (air-water gas transfer coefficient), `MiniMathMod` (safe-math helpers). |
| `ModelDiags/` | 3 | `BalancesMod.F90` (`BegCheckBalances`, `EndCheckBalances`), `HydrologyDiagMod.F90` (`DiagWaterTBLDepz`), `SoilDiagsMod.F90` (`DiagSoilGasPressure`). |
| `Modelconfig/` | 5 | Run-time config scalars: `EcoSIMCtrlMod` (`salt_model`, `plant_model`, `microbial_model`, etc.), `EcoSIMConfig` (`transport_on`, `column_mode`, `do_instequil`), `EcoSIMSolverPar` (solver timesteps `dts_wat`, `dts_sno`, `dt_watvap`), `TracerIDMod` (tracer numeric IDs), `ElmIDMod` ("Chemical element ids"). |
| `Modelforc/` | 4 | In-simulation forcing orchestration: `DayMod` (daily reinit), `Hour1Mod` (`hour1` sub-daily stage), `WthrMod` (`PrepHourlyWeather`), `YearMod` (`SetAnnualAccumlators`). |
| `Modelpars/` | 8 | Parameter modules: `EcoSiMParDataMod` (exports `pltpar`, `micpar`), `PlantBGCPars`, `MicBGCPars`, `NitroPars` ("code defining parameters for nitro"), `ChemTracerParsMod` (gas/aqueous diffusivities), `SoluteParMod` (equilibrium constants `DPH2O`, `SPALO`, `SPFEO`, ...), `TracerPropMod` (`gas_solubility`, `MolecularWeight`, `GasSechenovConst`), `MicrobeConfigMod` (reads microbial namelist). |
| `Plant_bgc/` | 24 | Largest module group. Photosynthesis (`PhotoSynsMod:ComputeGPP`), stomata (`StomatesMod:StomatalDynamics`), uptake (`UptakesMod:RootUptakes`, `NutUptakeMod`), allocation/growth (`GrosubsMod`, `PlantNonstElmDynMod`), phenology (`PlantPhenolMod`), canopy radiation (`SurfaceRadiationMod:CanopyConditionModel`, `InitVegBGC`), root model (`RootMod:RootBGCModel`, `RootGasMod`), nodule BGC (`NoduleBGCMod`), litterfall (`LitterFallMod`), branch dynamics (`PlantBranchMod`), initialization (`InitPlantMod:StartPlants`), mass balance (`PlantBalMod`), debug (`PlantDebugMod`), disturbance effects (`PlantDisturbsMod`, `PlantDisturbByFireMod`, `PlantDisturbByGrazingMod`, `PlantDisturbByTillageMod`), plant-level aggregation (`ExtractsMod`), plant math (`PlantMathFuncMod`), uptake parameters (`UptakePars`). |
| `Prescribed_pheno/` | 1 | `PrescribePhenolMod.F90` (`GetRootProfile`, `SetCanopyProfile`) — prescribed-phenology alternative to dynamic plant model. |
| `Transport/` | 8 | Split: `Nonsalt/` (5: `TranspNoSaltMod` outer, `TranspNoSaltFastMod` — surface gaseous diffusion/advection/dissolution, `TranspNoSaltSlowMod`, `InitNoSaltTransportMod`, `TranspNoSaltDataMod`) + `Salt/` (3: `TranspSaltMod`, `IngridTranspMod`, `TranspSaltDataMod`). |
| `Utils/` | 14 | Cross-cutting utilities: `data_kind_mod`, `data_const_mod`, `EcoSimConst`, `ModelStatusType`, `UnitMod` (unit conversion), `StrToolsMod` (`parse_var_val_string`), `fileUtil` (file-open with error check), `abortutils` (`endrun`, `iulog`), `ecosim_log_mod` (shared logging variables), `ecosim_time_mod` (time marching), `ncdio_pio` (NetCDF I/O), `shr_infnan_mod` (IEEE NaN/Inf tests, auto-generated), `TestMod` (regression test harness), `timings` (runtime timing). Also contains two small C sources: `clock.c` and `getfilename.c`. |

## `drivers/` subsystems

| Path | Files | Purpose |
|---|---|---|
| `drivers/ecosim/` | 2 | Production standalone executable. `ecosim.F90` is the `program main`; `EcoSIMAPI.F90` exposes `AdvanceModelOneYear`, `readnamelist`, `regressiontest`, `write_modelconfig`, plus the internal `Run_EcoSIM_one_step` subsystem sequence (`drivers/ecosim/EcoSIMAPI.F90:35`). |
| `drivers/ATSEcoSIM/` | 1 | `ATSEcoSIM_test.F90` — program `EcoATSTest`, smoke-tests the coupling path with `BGCState`/`BGCProperties`/`BGCSizes`. |
| `drivers/aquachem/` | 3 | `aquachem.F90` (program `main`) + `AquachemMod.F90` (exports `initmodel`, `getvarlist`, `getvarllen`, `runchem`) + `AquaSaltChemMod.F90` (salt mode). |
| `drivers/boxsbgc/` | 5 | `batchsbgc.F90` (program `main`, "Single layer model") + `batchmod` (batch-mode configuration) + `ChemMod` (`RunModel_nosalt`) + `ForcTypeMod` (forcing type) + `MicIDMod` (microbial IDs). |
| `drivers/boxshared/` | 1 | `ChemIDMod.F90` — shared chemistry IDs (`getvarlist_nosalt`) used by batch chemistry drivers. |
| `drivers/mockbatch/` | 2 | `mockdriver.F90` (program `main`) + `MockMod.F90` — minimal-dependency mock. |
| `drivers/plantbgc/` | 2 | `plantdriver.F90` (program `main`) + `PlantMod.F90` — standalone plant BGC harness. |
| `drivers/tools/` | 12 | 12 small test programs (see [overview](index.md#4-standalone-test-tools-driverstools) and [`reference/module_inventory.md`](../reference/module_inventory.md) for the per-program description). |

## Notes on the layout

- **Why two `PlantMod.F90` files?** The driver-only `drivers/plantbgc/PlantMod.F90` (module `PlantMod`, `public :: getvarllen`, `getvarlist`, `initmodel`) is a batch-driver wrapper. The library `f90src/APIs/PlantMod.F90` (module `PlantMod`, `public :: PlantModel`, `PlantCanopyRadsModel`) is the API consumed by `EcoSIMAPI`. They share the module name but live in different directories and are compiled into different targets.
- **Why two `SurfPhysAPI.F90` files?** `f90src/APIs/SurfPhysAPI.F90` is an empty stub (`f90src/APIs/SurfPhysAPI.F90:1-13`); the real contents live in `f90src/HydroTherm/SurfPhys/SurfPhysAPI.F90`. The stub is kept to preserve a dependency anchor at the `APIs/` layer.
- **Why `*DataMod.F90` vs `*DataType.F90`?** Files ending in `DataType` (under `Ecosim_datatype/`) hold `allocatable, target` field arrays shared across the model (column/layer/PFT state). Files ending in `DataMod` (under `Transport/`, `HydroTherm/`, `Balances/`) usually hold transient working buffers owned by that subsystem, not global state.
- **Subsystem API files:** Each subsystem tends to expose a small number of public subroutines through an explicit `Mod` file (e.g., `WatsubMod:watsub`, `TranspNoSaltMod:TranspNoSalt`, `RedistMod:redist`) and keep its internals (fast-path, slow-path, data) in sibling `*FastMod.F90` / `*SlowMod.F90` / `*DataMod.F90` files.

## Where to go next

- [`reference/module_inventory.md`](../reference/module_inventory.md) — every F90 module with a one-line description.
- Subsystem-specific sections linked from the [top-level index](../index.md).
