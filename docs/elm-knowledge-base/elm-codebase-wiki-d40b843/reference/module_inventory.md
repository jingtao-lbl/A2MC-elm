---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Module Inventory

This page lists every Fortran module (`.F90` file) in `components/elm/src/` at commit `d40b8431`, grouped by subdirectory. Each entry is a one-line description derived from the module's top-of-file `!DESCRIPTION:` comment. When no such comment exists, the description is taken from the first substantive comment line in the file, or, as a last resort, derived from the module's name and first type declaration.

**Scope:** `components/elm/src/` excluding `external_models/` (FATES), `.ipynb_checkpoints/`, and build helpers (`.F90.in` genf90 templates, `.pl` Perl scripts, `.h` C headers). Excluded helpers at d40b8431 are: `main/findHistFields.pl`, `main/ncdio_pio.F90.in`, `dyn_subgrid/dynVarMod.F90.in`, `dyn_subgrid/dynVarTimeInterpMod.F90.in`, `dyn_subgrid/dynVarTimeUninterpMod.F90.in`, `utils/restUtilMod.F90.in`, and `utils/dtypes.h`.

**Total:** 242 files across 7 subdirectories.

| Subdirectory | Files | Subject area |
|---|---:|---|
| [`main/`](#main-65-files) | 65 | Driver, initialization/finalization, control flags, subgrid bookkeeping, history/restart I/O, coupling glue (atm/glc/ocn/iac) |
| [`cpl/`](#cpl-5-files) | 5 | MCT driver entry point, import/export of coupler fields, topounit downscaling |
| [`data_types/`](#data_types-13-files) | 13 | Gridcell/topounit/landunit/column/vegetation derived types and instance containers (incl. MOAB grid type) |
| [`dyn_subgrid/`](#dyn_subgrid-18-files) | 18 | Transient land cover (pftdyn, harvest, crop, FATES land-use), state conservation across weight changes |
| [`biogeophys/`](#biogeophys-54-files) | 54 | Energy balance, radiation, canopy/soil/snow/lake temperature and hydrology, aerosols |
| [`biogeochem/`](#biogeochem-74-files) | 74 | C/N/P cycles, allocation, phenology, decomposition, fire, crop, CH4, VOC, dust, erosion |
| [`utils/`](#utils-13-files) | 13 | Time manager, SPMD, domain, orbital parameters, namelist and file helpers |

---

## main/ (65 files)

| Module | Purpose |
|---|---|
| `ColumnMod.F90` | Column-level accessor routines for sub-grid unpacking |
| `FuncPedotransferMod.F90` | Pedotransfer functions for soil hydraulic and thermal properties |
| `GetGlobalValuesMod.F90` | Obtain and Write Global Index information |
| `LandunitMod.F90` | Landunit-level accessor routines for sub-grid unpacking |
| `PatchMod.F90` | Patch (PFT) level accessor routines for sub-grid unpacking |
| `SoilorderConType.F90` | Soil order (Pedologic order) parameter container type |
| `abortutils.F90` | Abort the model for abnormal termination |
| `accumulMod.F90` | This module contains generic subroutines that can be used to |
| `atm2lndMod.F90` | Handle atm2lnd forcing |
| `atm2lndType.F90` | Handle atm2lnd, lnd2atm mapping |
| `column_varcon.F90` | Module containing landunit indices and associated variables and routines. |
| `controlMod.F90` | Module which initializes run control variables. The following possible |
| `decompInitMod.F90` | Module provides a descomposition into a clumped data structure which can |
| `decompMod.F90` | Module provides a descomposition into a clumped data structure which can |
| `elm_driver.F90` | This module provides the main ELM driver physics calling sequence.  Most |
| `elm_finalizeMod.F90` | ELM cleanup and finalization routines |
| `elm_initializeMod.F90` | Performs land model initialization |
| `elm_instMod.F90` | initialize elm data types |
| `elm_instance.F90` | ELM multi-instance bookkeeping (land component id per instance) |
| `elm_interface_bgcType.F90` | ELM-BGC interface derived type (coupling buffer) |
| `elm_interface_dataType.F90` | ELM-TH/BGC interface derived type (coupling buffer) |
| `elm_interface_funcsMod.F90` | ELM interface functions for coupling to alternative BGC/TH engines |
| `elm_interface_pflotranMod.F90` | ELM-PFLOTRAN coupling interface (state exchange) |
| `elm_interface_thType.F90` | ELM Thermal-Hydrology interface derived type |
| `elm_varcon.F90` | Module containing various model constants. |
| `elm_varctl.F90` | Module containing run control variables |
| `elm_varpar.F90` | Module containing CLM parameters |
| `elm_varsur.F90` | Module containing 2-d surface boundary data information |
| `elmfates_interfaceMod.F90` | This module contains various functions and definitions to aid in the |
| `fanStreamMod.F90` | Contains methods for reading in FAN nitrogen deposition (in the form of manure) data file |
| `filterMod.F90` | Patch/column filters for masked computations |
| `glc2lndMod.F90` | Handle arrays used for exchanging data from glc to clm. |
| `glcDiagnosticsMod.F90` | Computes and outputs a number of glacier-related diagnostic quantities |
| `histFileMod.F90` | Module containing methods to for CLM history file handling. |
| `histGPUMod.F90` | GPU mappings for history tape field positions |
| `iac2lndMod.F90` | Handle coupled data from iac for use in clm; iac is on the same grid as clm (per-pft frac and harvest fraction arrays) |
| `initGridCellsMod.F90` | Initializes sub-grid mapping for each land grid cell. This module handles the high |
| `initInterp.F90` | Interpolate initial conditions file from one resolution and/or landmask |
| `initSubgridMod.F90` | Lower-level routines for initializing the subgrid structure. This module is shared |
| `initVerticalMod.F90` | Initialize vertical components of column datatype |
| `init_hydrology.F90` | Hydrology initialization entry point |
| `landunit_varcon.F90` | Module containing landunit indices and associated variables and routines. |
| `lnd2atmMod.F90` | Handle lnd2atm mapping |
| `lnd2atmType.F90` | Handle atm2lnd, lnd2atm mapping |
| `lnd2glcMod.F90` | Handle arrays used for exchanging data from land model to glc |
| `lnd2iacMod.F90` | Arrays for exchanging data from land model to iac (per-pft hr, npp, pftwgt on grid) |
| `ndepStreamMod.F90` | Contains methods for reading in nitrogen deposition data file |
| `ocn2lndType.F90` | Handle ocn2lnd, lnd2ocn mapping (coastal inundation fraction, sea surface height on gridcells) |
| `organicFileMod.F90` | Contains methods for reading in organic matter data file which has |
| `paramUtilMod.F90` | module that deals with reading parameter files |
| `pdepStreamMod.F90` | Contains methods for reading in phosphorus deposition data file |
| `perfMod_GPU.F90` | GPU performance instrumentation wrappers |
| `pftvarcon.F90` | Module containing vegetation constants and method to |
| `readParamsMod.F90` | Read parameters |
| `restFileMod.F90` | Reads from or writes to/ the CLM restart file. |
| `reweightMod.F90` | Top level driver for things that happen when subgrid weights are changed. This is in |
| `soilorder_varcon.F90` | Module containing vegetation constants and method to |
| `subgridAveMod.F90` | Utilities to perfrom subgrid averaging |
| `subgridMod.F90` | sub-grid data and mapping types and modules |
| `subgridRestMod.F90` | Read/write subgrid structure from/to the restart file |
| `subgridWeightsMod.F90` | Handles modifications, error-checks and diagnostics related to changing subgrid weights |
| `surfrdMod.F90` | Contains methods for reading in surface data file and determining |
| `surfrdUtilsMod.F90` | Contains utility methods that can be used when reading surface datasets or similar |
| `timeinfoMod.F90` | Shared time-step variables (nstep, dtime, day/year counters) |
| `topounit_varcon.F90` | Module containing topounit indices and associated variables and routines. |

## cpl/ (5 files)

| Module | Purpose |
|---|---|
| `elm_cpl_indices.F90` | Indices for fields passed between ELM and coupler |
| `lnd_comp_mct.F90` | MCT-based land component interface to the E3SM driver |
| `lnd_disagg_forc.F90` | Disaggregate gridcell forcing to topounits |
| `lnd_downscale_atm_forcing.F90` | Downscale atmospheric forcing by topographic gradients |
| `lnd_import_export.F90` | Import/export routines between ELM state and coupler fields |

## data_types/ (13 files)

| Module | Purpose |
|---|---|
| `CNStateType.F90` | CN state type (includes crop prognostic flags like cropplant/harvdate) |
| `ColumnDataType.F90` | Column data type allocation and initialization |
| `ColumnType.F90` | Column data type allocation and initialization |
| `GridcellDataType.F90` | Gridcell data type allocation and initialization |
| `GridcellType.F90` | Gridcell data type allocation |
| `LandunitDataType.F90` | Landunit data type allocation and initialization |
| `LandunitType.F90` | Landunit data type allocation |
| `MOABGridType.F90` | MOAB (Mesh-Oriented datABase) ELM grid-cell type, ghost-region mesh I/O via iMOAB; built only when `HAVE_MOAB` is defined |
| `TopounitDataType.F90` | Topounit data type allocation and initialization |
| `TopounitType.F90` | Topounit derived type; ELM subgrid hierarchy: gridcell->topounit->landunit->column->patch |
| `VegetationDataType.F90` | Vegetation data type allocation and initialization |
| `VegetationPropertiesType.F90` | PFT-level vegetation properties type (traits, allometry, phenology) |
| `VegetationType.F90` | Vegetation data type allocation |

## dyn_subgrid/ (18 files)

| Module | Purpose |
|---|---|
| `dynColumnStateUpdaterMod.F90` | Class for adjusting column-level state variables due to transient column areas. |
| `dynColumnTemplateMod.F90` | Routines for finding a template column to use for the state variables on some other |
| `dynConsBiogeochemMod.F90` | Conservation of C & N with dynamic land cover |
| `dynConsBiogeophysMod.F90` | Conservation of water & energy with dynamic land cover |
| `dynEDMod.F90` | Dynamic FATES/ED coupling for transient subgrid updates |
| `dynFATESLandUseChangeMod.F90` | Handle reading of the land use harmonization (LUH2) dataset (transitions, states, wood-harvest area/mass) for FATES |
| `dynFileMod.F90` | Contains a derived type that is essentially a file_desc_t, but also adds a |
| `dynHarvestMod.F90` | Handle reading of the harvest data, as well as the state updates that happen as a |
| `dynInitColumnsMod.F90` | Handle initialization of columns that just switched from inactive to active |
| `dynLandunitAreaMod.F90` | Handle dynamic landunit weights |
| `dynPatchStateUpdaterMod.F90` | Class for adjusting patch-level (aboveground) state variables due to transient patch |
| `dynPriorWeightsMod.F90` | Defines a derived type and associated methods for working with prior subgrid weights |
| `dynSubgridAdjustmentsMod.F90` | Holds the methods for adjusting state variables at each sub-grid level, |
| `dynSubgridControlMod.F90` | Defines a class for storing and querying control flags related to dynamic subgrid |
| `dynSubgridDriverMod.F90` | High-level routines for dynamic subgrid areas (prescribed transient Patches and |
| `dynTimeInfoMod.F90` | Contains a derived type and associated methods for storing and working with time |
| `dyncropFileMod.F90` | Handle reading of the dataset that specifies transient areas the crop landunit as |
| `dynpftFileMod.F90` | Handle reading of the pftdyn dataset, which specifies transient areas of natural Patches |

## biogeophys/ (54 files)

| Module | Purpose |
|---|---|
| `ActiveLayerMod.F90` | Module holding routines for calculation of active layer dynamics |
| `AerosolMod.F90` | Column-integrated aerosol mass calculation and deposition |
| `AerosolType.F90` | Aerosol derived type (dust, black carbon, organic carbon masses) |
| `BalanceCheckMod.F90` | Water and energy balance check. |
| `BandDiagonalMod.F90` | Band Diagonal matrix solution |
| `BareGroundFluxesMod.F90` | Compute sensible and latent fluxes and their derivatives with respect |
| `CanopyFluxesMod.F90` | Performs calculation of leaf temperature and surface fluxes. |
| `CanopyHydrologyMod.F90` | Calculation of |
| `CanopyStateType.F90` | Canopy state variables (LAI, SAI, canopy heights, btran) |
| `CanopyTemperatureMod.F90` | CanopyFluxes calculates the leaf temperature and the leaf fluxes, |
| `DaylengthMod.F90` | Computes daylength |
| `EnergyFluxType.F90` | Surface and canopy energy flux variables |
| `FrictionVelocityMod.F90` | Calculation of the friction velocity, relation for potential |
| `FrictionVelocityType.F90` | Friction velocity and roughness length state |
| `HydrologyDrainageMod.F90` | Calculates soil/snow hydrology with drainage (subsurface runoff) |
| `HydrologyNoDrainageMod.F90` | Calculate snow and soil temperatures including phase change |
| `LakeCon.F90` | Module containing constants and parameters for the Lake code |
| `LakeFluxesMod.F90` | Calculates surface fluxes and temperature for lakes. |
| `LakeHydrologyMod.F90` | Calculation of Lake Hydrology. Full hydrology, aerosol deposition, etc. of snow layers is |
| `LakeStateType.F90` | Lake data types and associated procesures |
| `LakeTemperatureMod.F90` | Calculates surface fluxes and temperature for lakes. |
| `PhotosynthesisMod.F90` | Leaf photosynthesis and stomatal conductance calculation as described by |
| `PhotosynthesisType.F90` | Photosynthesis-related state (includes ED hooks) |
| `QSatMod.F90` | Computes saturation mixing ratio and the change in saturation |
| `RootBiophysMod.F90` | module contains subroutine for root biophysics |
| `SedFluxType.F90` | Hold sediment, POC, PON and POP dynamic fluxes induced by soil erosion |
| `SedYieldMod.F90` | Calculate the sediment flux caused by soil erosion documented in |
| `SnowHydrologyMod.F90` | Calculate snow hydrology. |
| `SnowSnicarMod.F90` | Calculate albedo of snow containing impurities |
| `SoilFluxesMod.F90` | Updates surface fluxes based on the new ground temperature. |
| `SoilHydrologyMod.F90` | Calculate soil hydrology |
| `SoilHydrologyType.F90` | Soil hydrology state variables (non-VIC) |
| `SoilMoistStressMod.F90` | Calculates soil moisture stress for plant gpp and transpiration |
| `SoilStateType.F90` | Soil physical state (sand/clay/organic matter, hydraulic props) |
| `SoilTemperatureMod.F90` | Calculates snow and soil temperatures including phase change |
| `SoilWaterMovementMod.F90` | Soil water flow solver (Richards equation) |
| `SoilWaterRetentionCurveClappHornberg1978Mod.F90` | Implementation of soil_water_retention_curve_type using the Clapp-Hornberg 1978 |
| `SoilWaterRetentionCurveFactoryMod.F90` | Factory to create an instance of soil_water_retention_curve_type. This module figures |
| `SoilWaterRetentionCurveMod.F90` | Abstract base class for functions to compute soil water retention curve |
| `SolarAbsorbedType.F90` | Solar absorbed/reflected radiation state |
| `SurfaceAlbedoMod.F90` | Performs surface albedo calculations |
| `SurfaceAlbedoType.F90` | Surface albedo state (snow, soil, glacier albice) |
| `SurfaceRadiationMod.F90` | Calculate solar fluxes absorbed by vegetation and ground surface |
| `SurfaceResistanceMod.F90` | Module holding routines for calculation of surface resistances of the different tracers |
| `TemperatureType.F90` | Column, canopy, and surface temperature state |
| `TotalWaterAndHeatMod.F90` | Routines for computing total column water and heat contents |
| `TridiagonalMod.F90` | Tridiagonal matrix solution |
| `UrbanAlbedoMod.F90` | Calculate solar and longwave radiation, and turbulent fluxes for urban landunit |
| `UrbanFluxesMod.F90` | Calculate solar and longwave radiation, and turbulent fluxes for urban landunit |
| `UrbanParamsType.F90` | Urban Constants |
| `UrbanRadiationMod.F90` | Calculate solar and longwave radiation, and turbulent fluxes for urban landunit |
| `WaterBudgetMod.F90` | Water budget tracking and global closure checks |
| `WaterStateType.F90` | Hydrology state variables (snow, soil moisture, ice) |
| `WaterfluxType.F90` | Water flux state variables (evaporation, runoff, transpiration) |

## biogeochem/ (74 files)

| Module | Purpose |
|---|---|
| `AllocationMod.F90` | Module holding routines used in allocation model for coupled carbon |
| `AnnualUpdateMod.F90` | Module for updating annual summation variables |
| `C14DecayMod.F90` | Module for 14-carbon flux variable update, non-mortality fluxes. |
| `CH4Mod.F90` | Module holding routines to calculate methane fluxes |
| `CH4varcon.F90` | Module containing CH4 parameters and logical switches and routine to read constants from CLM namelist. |
| `CNAllocationBetrMod.F90` | Module holding routines used in allocation model for coupled carbon |
| `CNBeTRIndicatorMod.F90` | BeTR indicator variables for coupled BGC |
| `CNCarbonFluxType.F90` | Carbon flux variable derived type (column/patch levels) |
| `CNCarbonStateType.F90` | Carbon state variable derived type (column/patch levels) |
| `CNDecompCascadeConType.F90` | Decomposition Cascade Type |
| `CNEcosystemDynBetrMod.F90` | BeTR-coupled ecosystem dynamics driver |
| `CNGapMortalityBeTRMod.F90` | Module holding routines used in gap mortality for coupled carbon |
| `CNNStateUpdate1BeTRMod.F90` | Module for nitrogen state variable updates, non-mortality fluxes. |
| `CNNStateUpdate2BeTRMod.F90` | Module for nitrogen state variable update, mortality fluxes. |
| `CNNStateUpdate3BeTRMod.F90` | Module for nitrogen state variable update, mortality fluxes. |
| `CNNitrogenFluxType.F90` | Nitrogen flux variable derived type |
| `CNNitrogenStateType.F90` | Nitrogen state variable derived type |
| `CNPBudgetMod.F90` | C, N, P budget tracking and mass balance accumulators |
| `CNPhenologyBeTRMod.F90` | Module holding routines used in phenology model for coupled carbon |
| `CarbonIsoFluxMod.F90` | Module for carbon isotopic flux variable update, non-mortality fluxes. |
| `CarbonStateUpdate1Mod.F90` | Module for carbon state variable update, non-mortality fluxes. |
| `CarbonStateUpdate2Mod.F90` | Module for carbon state variable update, mortality fluxes. |
| `CarbonStateUpdate3Mod.F90` | Module for carbon state variable update, mortality fluxes. |
| `ChemStateType.F90` | Column-level chemical state variables |
| `ComputeSeedMod.F90` | Module to compute seed amounts for new patch areas |
| `CropHarvestPoolsMod.F90` | Calculate loss fluxes from crop harvest pools, and update product pool state variables |
| `CropMod.F90` | Module holding routines used in crop model |
| `CropType.F90` | Module containing variables needed for the crop model |
| `DUSTMod.F90` | Routines in this module calculate Dust mobilization and dry deposition for dust. |
| `DecompCascadeBGCMod.F90` | Sets the coeffiecients used in the decomposition cascade submodel. |
| `DecompCascadeCNMod.F90` | Sets the coeffiecients used in the decomposition cascade submodel. |
| `DryDepVelocity.F90` | Dry deposition velocity calculation for gas-phase species |
| `EcosystemBalanceCheckMod.F90` | Module for carbon mass balance checking. |
| `EcosystemDynMod.F90` | Ecosystem dynamics: phenology, vegetation |
| `ErosionMod.F90` | Calculate erosion induced soil particulate C, N and P fluxes |
| `FATESFireBase.F90` | Abstract base class for FATES fire data object |
| `FATESFireDataMod.F90` | module for FATES to obtain fire inputs from data |
| `FATESFireFactoryMod.F90` | Factory to create an instance of fire_method_type. This module figures |
| `FATESFireNoDataMod.F90` | module for FATES when not obtaining fire inputs from data |
| `FanMod.F90` | This module implements the physical parameterizations of the FANv2 (Flow of |
| `FanUpdateMod.F90` | This module interfaces the FAN (Flow of Agricultural Nitrogen) process model with |
| `FireDataBaseType.F90` | Module for fire data base type as an extension of the fire method type |
| `FireMethodType.F90` | Abstract base class for functions to implement fire model and data  for |
| `FireMod.F90` | module for fire dynamics |
| `GapMortalityMod.F90` | Module holding routines used in gap mortality for coupled carbon |
| `GrowthRespMod.F90` | Module for growth respiration fluxes, |
| `LSparseMatMod.F90` | sparse matrix capability |
| `MEGANFactorsMod.F90` | Manages input of MEGAN emissions factors from netCDF file |
| `MaintenanceRespMod.F90` | Module holding maintenance respiration routines for coupled carbon |
| `NitrifDenitrifMod.F90` | Calculate nitrification and denitrification rates |
| `NitrogenDynamicsMod.F90` | Module for mineral nitrogen dynamics (deposition, fixation, leaching) |
| `NitrogenStateUpdate1Mod.F90` | Module for nitrogen state variable updates, non-mortality fluxes. |
| `NitrogenStateUpdate2Mod.F90` | Module for nitrogen state variable update, mortality fluxes. |
| `NitrogenStateUpdate3Mod.F90` | Module for nitrogen state variable update, mortality fluxes. |
| `PhenologyFluxLimitMod.F90` | limit the allocation fluxes resulting from pheonology |
| `PhenologyMod.F90` | Module holding routines used in phenology model for coupled carbon |
| `PhosphorusDynamicsMod.F90` | Module for inorganic phosphorus dynamics |
| `PhosphorusFluxType.F90` | Phosphorus flux variable derived type |
| `PhosphorusStateType.F90` | Phosphorus state variable derived type |
| `PhosphorusStateUpdate1Mod.F90` | Module for phosphorus state variable updates, non-mortality fluxes. |
| `PhosphorusStateUpdate2Mod.F90` | Module for phosphorus state variable update, mortality fluxes. |
| `PhosphorusStateUpdate3Mod.F90` | Module for phosphorus state variable update, mortality fluxes. |
| `PlantMicKineticsMod.F90` | Plant-microbe nutrient uptake kinetics |
| `PrecisionControlMod.F90` | controls on very low values in critical state variables |
| `RootDynamicsMod.F90` | Module holding routines used for determining fine root distribution for all pfts. |
| `SatellitePhenologyMod.F90` | CLM Satelitte Phenology model (SP) ecosystem dynamics (phenology, vegetation). |
| `SharedParamsMod.F90` | Shared parameter container for BGC modules |
| `SoilLittDecompMod.F90` | Module holding routines used in litter and soil decomposition model |
| `SoilLittVertTranspMod.F90` | calculate vertical mixing of all decomposing C and N pools |
| `SpeciesMod.F90` | Module holding information about different species available in the CN code (C, C13, |
| `VOCEmissionMod.F90` | Volatile organic compound emission |
| `VegStructUpdateMod.F90` | Module for vegetation structure updates (LAI, SAI, htop, hbot) |
| `VerticalProfileMod.F90` | Module holding routines for vertical discretization of C and N inputs into deocmposing pools |
| `WoodProductsMod.F90` | Calculate loss fluxes from wood products pools, and update product pool state variables |

## utils/ (13 files)

| Module | Purpose |
|---|---|
| `AnnualFluxDribbler.F90` | Defines a class for handling fluxes that are generated once per year (e.g., due to |
| `SimpleMathMod.F90` | Simple array math helpers |
| `domainLateralMod.F90` | Lateral domain connectivity for lateral flows (PETSc-based) |
| `domainMod.F90` | Module containing 2-d global surface boundary data information |
| `elm_nlUtilsMod.F90` | Utilities to handle namelists. |
| `elm_time_manager.F90` | ELM time manager (driven from CESM/E3SM driver) |
| `elm_varorb.F90` | Orbital parameters passed to shr_orb (eccentricity, obliquity) |
| `fileutils.F90` | Module containing file I/O utilities |
| `getdatetime.F90` | Generic date/time routine |
| `quadraticMod.F90` | Quadratic equation solver utility |
| `seq_drydep_mod_elm.F90` | Module for handling dry depostion of tracers. |
| `spmdGathScatMod.F90` | Perform SPMD gather and scatter operations. |
| `spmdMod.F90` | SPMD initialization |

---

## Drift summary vs 60d9aad

This page is the d40b8431 rewrite of the 60d9aad inventory. Net change: **239 → 242 `.F90` files** (two removals, five additions). All seven subdirectory groupings and all subject-area summaries remain valid.

| Change | File | Subdir | Source line |
|---|---|---|---|
| Removed | `lnd_comp_esmf.F90` | `cpl/` | (no longer present at d40b8431) |
| Removed | `elmfates_paraminterfaceMod.F90` | `main/` | (no longer present at d40b8431) |
| Added | `iac2lndMod.F90` | `main/` | `main/iac2lndMod.F90:1` |
| Added | `lnd2iacMod.F90` | `main/` | `main/lnd2iacMod.F90:1` |
| Added | `ocn2lndType.F90` | `main/` | `main/ocn2lndType.F90:1` |
| Added | `MOABGridType.F90` | `data_types/` | `data_types/MOABGridType.F90:3` (guarded by `#ifdef HAVE_MOAB`) |
| Added | `dynFATESLandUseChangeMod.F90` | `dyn_subgrid/` | `dyn_subgrid/dynFATESLandUseChangeMod.F90:1` |

Per-subdirectory counts at d40b8431: `main/` 65, `cpl/` 5, `data_types/` 13, `dyn_subgrid/` 18, `biogeophys/` 54, `biogeochem/` 74, `utils/` 13. Total 242.
