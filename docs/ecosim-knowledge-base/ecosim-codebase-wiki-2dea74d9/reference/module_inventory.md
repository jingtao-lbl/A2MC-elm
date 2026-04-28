---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/` + `drivers/` (full repo)
**Last verified:** 2026-04-24
---

# Module Inventory

Every Fortran source file under `f90src/` and `drivers/` at commit `2dea74d9`. One row per file. 182 rows under `f90src/` and 28 under `drivers/` for a total of 210. Descriptions come from the in-file `!DESCRIPTION:` block when present, otherwise from the module's first public interface or the dominant content signature (e.g., the kinds of allocatable arrays declared). For richer context, navigate to the subsystem wiki page linked from the [top-level index](../index.md).

---

## `f90src/Main/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Main/InitEcoSIM.F90` | `InitEcoSIM` | Initialize the EcoSIM data structures; `InitModules` chains `InitAlloc`, plant trait load, `units%Initailize`, `InitPlantDisturbance`, `InitUptake`, `initNitro`, `InitRedist`, `InitErosion`, `InitHour1`, `InitTranspNoSalt`, `hist_ecosim%Init`, `MicAPI_Init` (`f90src/Main/InitEcoSIM.F90:34-57`). |
| `f90src/Main/EcoSIMDesctruct.F90` | `EcoSIMDesctruct` | Tear-down routine; `public :: DestructEcoSIM`, called at program end from `drivers/ecosim/ecosim.F90:156`. |

## `f90src/Ecosim_mods/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Ecosim_mods/InitAllocMod.F90` | `InitAllocMod` | Orchestrates allocation of all `Ecosim_datatype/` field arrays; `public :: InitAlloc`. |
| `f90src/Ecosim_mods/StartsMod.F90` | `StartsMod` | "Code to initalize soil variables" (file comment); also exports `set_ecosim_solver` used by `drivers/ecosim/ecosim.F90:125`. |
| `f90src/Ecosim_mods/StartqMod.F90` | `StartqMod` | Initialize plant variables; `public :: startq` (wrapped entry for ecosys-style plant startup). |
| `f90src/Ecosim_mods/StarteMod.F90` | `StarteMod` | "INITIALIZES ALL SOIL CHEMISTRY VARIABLES. The top layer is initialized every year to accommodate changes in boundary conditions (irrigation, rainfall, manure application) every year" (`f90src/Ecosim_mods/StarteMod.F90`). |

## `f90src/Mesh/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Mesh/GridConsts.F90` | `GridConsts` | Shared grid constants (`bounds`, `JP`, etc.) imported throughout the tree. |
| `f90src/Mesh/GridMod.F90` | `GridMod` | Sets up the horizontal rectangular mesh; `public :: SetMesh, SetMeshATS` (standalone vs ATS entry points). |

## `f90src/Modelconfig/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Modelconfig/EcoSIMConfig.F90` | `EcoSIMConfig` | Run-level toggles: `transport_on`, `column_mode`, `do_instequil`, `is_first_year`, plus `case_name`, `start_date`, `is_restart` (`f90src/Modelconfig/EcoSIMConfig.F90`). |
| `f90src/Modelconfig/EcoSIMCtrlMod.F90` | `EcoSIMCtrlMod` | Run-time control state: `salt_model`, `plant_model`, `microbial_model`, `soichem_model`, `idebug_day`, `etimer`, file paths (`pft_file_in`, `clm_hour_file_in`, ...). |
| `f90src/Modelconfig/EcoSIMSolverPar.F90` | `EcoSIMSolverPar` | Solver time steps and substep counts: `dts_wat`, `dts_sno`, `dt_watvap`, `oscal_test`. |
| `f90src/Modelconfig/TracerIDMod.F90` | `TracerIDMod` | Numeric IDs for gas/aqueous tracers (`ids_NO2B`, `ids_NO2`, `idg_O2`, …); `public :: CleanUpTracerIDs`. |
| `f90src/Modelconfig/ElmIDMod.F90` | `ElmIDMod` | Chemical element IDs (`f90src/Modelconfig/ElmIDMod.F90:1` "Chemical element ids"). |

## `f90src/Modelpars/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Modelpars/EcoSiMParDataMod.F90` | `EcoSiMParDataMod` | Exports shared parameter containers `type(plant_bgc_par_type) :: pltpar` and `type(MicParType) :: micpar`. |
| `f90src/Modelpars/PlantBGCPars.F90` | `PlantBGCPars` | Plant allocation/respiration parameters (`FracHour4LeafoffRemob`, `PART2LEAF_MIN`, `VMXC`, ...). |
| `f90src/Modelpars/MicBGCPars.F90` | `MicBGCPars` | Defines microbial parameters (file comment: "define microbial parameters"). |
| `f90src/Modelpars/NitroPars.F90` | `NitroPars` | "Code defining parameters for nitro" (`f90src/Modelpars/NitroPars.F90` DESCRIPTION block). |
| `f90src/Modelpars/ChemTracerParsMod.F90` | `ChemTracerParsMod` | Gas/aqueous diffusivities per tracer (`ARSG`, `ARSL`, `CGSG`, `CLSG`, ...). |
| `f90src/Modelpars/SoluteParMod.F90` | `SoluteParMod` | Equilibrium constants (`DPH2O` for H2O dissociation, `SPALO` for Al(OH)3, `SPFEO` for Fe(OH)3, urea inhibitor constants `RUreaInhibtorConst`). |
| `f90src/Modelpars/TracerPropMod.F90` | `TracerPropMod` | Tracer physical properties; `public :: gas_solubility, GramPerHr2umolPerSec, GasSechenovConst, MolecularWeight`. |
| `f90src/Modelpars/MicrobeConfigMod.F90` | `MicrobeConfigMod` | `public :: ReadMicrobeNamelist` — parses the microbial-parameter namelist. |

## `f90src/Ecosim_datatype/` (all hold allocatable, target global state)

| File | Module | Purpose |
|---|---|---|
| `f90src/Ecosim_datatype/AqueChemDatatype.F90` | `AqueChemDatatype` | Aqueous chemistry state: soil Al/Fe/Ca/Mg content (`CAL_vr`, `CFE_vr`, `CCA_vr`, `CMG_vr`, ...). |
| `f90src/Ecosim_datatype/BalanceCheckDataType.F90` | `BalanceCheckDataType` | Balance closure errors: `WaterErr_col`, `HeatErr_col`, `EcoElmErr_col`, `PlantElmErr_col`. |
| `f90src/Ecosim_datatype/CanopyDataType.F90` | `CanopyDataType` | Canopy state: `LAI_col`, `canopy_growth_pft`, `StomatalStress_pft`, `CanopyPARalbedo_pft`. |
| `f90src/Ecosim_datatype/CanopyRadDataType.F90` | `CanopyRadDataType` | Canopy radiation state: leaf-angle sines/cosines (`SineLeafAngle`, `CosineLeafAngle`), indirect-radiation terms (`OMEGA`, `OMEGX`). |
| `f90src/Ecosim_datatype/ChemTranspDataType.F90` | `ChemTranspDataType` | Chemical transport state: `TScal4Difsvity_vr`, `DISP_3D`, `GasDifcT_vr`. |
| `f90src/Ecosim_datatype/ClimForcDataType.F90` | `ClimForcDataType` | Climate forcing state including OTC scalars (`srad_scalar_col`, `EMS_Modify_Scalar_col`) and reference soil temperature (`TKS_ref_vr`). |
| `f90src/Ecosim_datatype/EcoSIMCtrlDataType.F90` | `EcoSIMCtrlDataType` | Zero-initial reference arrays: `ZEROS`, `ZERO4Groth_pft`, `ZERO4Uptk_pft`, `ZERO4LeafVar_pft`. |
| `f90src/Ecosim_datatype/EcoSIMHistMod.F90` | `EcoSIMHistMod` | History-tape data types; "data types of plant characteristics" (`f90src/Ecosim_datatype/EcoSIMHistMod.F90:1`). |
| `f90src/Ecosim_datatype/EcoSimSumDataType.F90` | `EcoSimSumDataType` | Column-to-landscape aggregates: `SurfGas_lnd`, `PlantElemntStoreLandscape`. |
| `f90src/Ecosim_datatype/EcosimBGCFluxType.F90` | `EcosimBGCFluxType` | "Ecosystm fluxes for C, N, and P budget" (`f90src/Ecosim_datatype/EcosimBGCFluxType.F90:1`). |
| `f90src/Ecosim_datatype/FertilizerDataType.F90` | `FertilizerDataType` | Fertilizer pools: `FertN_mole_soil_vr`, `FertN_mole_Band_vr`, `FertP_mole_soil_vr`, `FertP_mole_band_vr`. |
| `f90src/Ecosim_datatype/FlagDataType.F90` | `FlagDataType` | Integer flags: `IYTYP`, `iSoilDisturbType_col`, `KoppenClimZone_col`, `iIrrigOpt_col`. |
| `f90src/Ecosim_datatype/GridDataType.F90` | `GridDataType` | Grid geometry: `CumDepz2LayBottom_vr`, `DLYR_3D`, `DLYRI_3D`, `XDPTH_3D`. |
| `f90src/Ecosim_datatype/IrrigationDataType.F90` | `IrrigationDataType` | Irrigation state: `IIRRA`, `RRIG`, `WDPTH`, `IrrigSubsurf_col`. |
| `f90src/Ecosim_datatype/LandSurfDataType.F90` | `LandSurfDataType` | Surface roughness and displacement: `SoilSurfRoughness_col`, `ZeroPlaneDisplacem_col`, `RoughnessLength_col`. |
| `f90src/Ecosim_datatype/MicrobialDataType.F90` | `MicrobialDataType` | Microbial state: `mBiomeHeter_vr` (heterotroph biomass), O2 demand, DOC/acetate uptake (`RO2DmndHetert_vr`, `RDOCUptkHeter_vr`, `RAcetateUptkHeter_vr`). |
| `f90src/Ecosim_datatype/NumericalAuxMod.F90` | `NumericalAuxMod` | "Auxillary variable for implementing the numerical dribbling" (`f90src/Ecosim_datatype/NumericalAuxMod.F90` DESCRIPTION). |
| `f90src/Ecosim_datatype/PlantDataRateType.F90` | `PlantDataRateType` | Plant rate state: `CanopyGrosRCO2_pft` (autotrophic respiration), `Eco_NEE_col`, `NH3Dep2Can_pft`. |
| `f90src/Ecosim_datatype/PlantMgmtDataType.F90` | `PlantMgmtDataType` | Management state: `THIN_pft`, `FracBiomHarvsted`, `CanopyCutProxy_pft`, `NP_col`. |
| `f90src/Ecosim_datatype/PlantTraitDataType.F90` | `PlantTraitDataType` | "Data types of plant trait characteristics that cannot be grouped into canopy or roots" (`f90src/Ecosim_datatype/PlantTraitDataType.F90:1`). |
| `f90src/Ecosim_datatype/PlantTraitTableMod.F90` | `PlantTraitTableMod` | Tabular trait fields: `iEmbryophyteType_pft_tab`, `iPlantPhotosynsType_pft_tab`, `iPlantRootProfile_tab`, `xylemPhi_mean_tab`. |
| `f90src/Ecosim_datatype/RootDataType.F90` | `RootDataType` | "Data types of plant characteristics" for root variables (`f90src/Ecosim_datatype/RootDataType.F90:1`). |
| `f90src/Ecosim_datatype/SOMDataType.F90` | `SOMDataType` | Soil organic matter state: initial litter C/N/P (`RSC_vr`, `RSN_vr`, `RSP_vr`), fractional pools (`CFOSC_vr`). |
| `f90src/Ecosim_datatype/SedimentDataType.F90` | `SedimentDataType` | Sediment state: `TSED_col` (erosion rate), `SoilDetachability4Erosion1`, `CER_col`. |
| `f90src/Ecosim_datatype/SnowDataType.F90` | `SnowDataType` | Snow state: `VLSnowHeatCapM_snvr`, `WatFlowInSnowM_snvr`, `DrySnoFlxByRedistM_2DH`, `NewSnowDens_col`. |
| `f90src/Ecosim_datatype/SoilBGCDataType.F90` | `SoilBGCDataType` | Soil BGC state (large module; substrates and microbial interface arrays). |
| `f90src/Ecosim_datatype/SoilHeatDataType.F90` | `SoilHeatDatatype` | Soil heat state: `TKS_vr` (soil temperature), `TLIceThawMicP_vr`, `TLPhaseChangeHeat2Soi_vr`. |
| `f90src/Ecosim_datatype/SoilPhysDataType.F90` | `SoilPhysDataType` | Soil physics state: `SLOPE_col` (4-direction slope), `SoilSurfDepZ_col`, `FieldCapacity_vr`, `WiltPoint_vr`. |
| `f90src/Ecosim_datatype/SoilPropertyDataType.F90` | `SoilPropertyDataType` | Soil property state: `CORGCI_vr` (organic C content), `POROSI_vr`, `SoilFracAsMacPt0_vr`, `CSAND_vr`. |
| `f90src/Ecosim_datatype/SoilWaterDataType.F90` | `SoilWaterDataType` | Soil water state: `TXGridSurfRunoff_2DH`, `THeatXGridBySurfRunoff_2DH`, `iPondBotLev_col`, `DVLiceMi...` fields. |
| `f90src/Ecosim_datatype/SurfLitterDataType.F90` | `SurfLitterDataType` | Surface litter state: `BulkDensLitR`, `PARR_col` (boundary layer conductance), `iLitrType_col`, `XTillCorp_col`. |
| `f90src/Ecosim_datatype/SurfSoilDataType.F90` | `SurfSoilDataType` | Surface fractional cover: `FracSurfAsSnow_col`, `FracSurfSnoFree_col`, `FracSurfBareSoil_col`, plus surface longwave `LWRadBySurf_col`. |

## `f90src/APIData/`

| File | Module | Purpose |
|---|---|---|
| `f90src/APIData/PlantAPIData.F90` | `PlantAPIData` | "Initialize data type for plant_radiation_type" — holds data types that cross the plant API boundary. |

## `f90src/APIs/`

| File | Module | Purpose |
|---|---|---|
| `f90src/APIs/GeochemAPI.F90` | `GeochemAPI` | "THIS SUBROUTINE CALCULATES ALL SOLUTE TRANSFORMATIONS"; `public :: soluteModel`. |
| `f90src/APIs/MicBGCAPI.F90` | `MicBGCAPI` | `public :: MicrobeModel, MicAPI_Init, MicAPI_cleanup` — entry point for the microbial BGC subsystem. |
| `f90src/APIs/PlantAPI.F90` | `PlantAPI` | "Interface to integrate the plant model"; `public :: PlantAPISend, PlantAPIRecv`. |
| `f90src/APIs/PlantAPI4Uptake.F90` | `PlantAPI4Uptake` | "Interface to integrate the plant model for prescribed phenology"; `public :: PlantUptakeAPISend, PlantUPtakeAPIRecv`. |
| `f90src/APIs/PlantCanAPI.F90` | `PlantCanAPI` | "Interface to integrate the plant model" (canopy-focused); `public :: PlantAPICanMSend, PlantAPICanMRecv`. |
| `f90src/APIs/PlantMod.F90` | `PlantMod` | Library-side plant driver; `public :: PlantModel, PlantCanopyRadsModel`. Called from `drivers/ecosim/EcoSIMAPI.F90:69`. |
| `f90src/APIs/SurfPhysAPI.F90` | `SurfPhysAPI` | Stub (empty contains block) at `f90src/APIs/SurfPhysAPI.F90:1-13`; the real implementation lives at `f90src/HydroTherm/SurfPhys/SurfPhysAPI.F90`. |

## `f90src/ATSUtils/`

| File | Module | Purpose |
|---|---|---|
| `f90src/ATSUtils/ATSCPLMod.F90` | `ATSCPLMod` | ATS coupling state holders and top-level ATS entry orchestration. |
| `f90src/ATSUtils/ATSEcoSIMAdvanceMod.F90` | `ATSEcoSIMAdvanceMod` | Per-step advance from ATS; `public :: RunEcoSIMSurfaceBalance`. |
| `f90src/ATSUtils/ATSEcoSIMInitMod.F90` | `ATSEcoSIMInitMod` | ATS init helpers; `public :: THETRX, Init_EcoSIM_Soil`. |
| `f90src/ATSUtils/ATSUtilsMod.F90` | `ATSUtilsMod` | `public :: ComputeDatefromATS` — converts ATS time stamps into EcoSIM dates. |
| `f90src/ATSUtils/BGC_containers.F90` | `BGCContainers_module` | `BGCState`, `BGCProperties`, `BGCSizes` derived types; adapted from Alquimia (`f90src/ATSUtils/BGC_containers.F90:2-5`). |
| `f90src/ATSUtils/SharedDataMod.F90` | `SharedDataMod` | Scratch data for ATS hand-off: atmospheric gases `atm_n2`/`atm_o2`/`atm_co2`, `a_csand`/`a_CSILT`/`a_BKDSI`/`a_LDENS` arrays (`f90src/ATSUtils/SharedDataMod.F90:15-20`). |
| `f90src/ATSUtils/c_f_interface_module.F90` | `c_f_interface_module` | Fortran/C interop helpers (adapted from Alquimia, `f90src/ATSUtils/c_f_interface_module.F90:2`). |
| `f90src/ATSUtils/ecosim_wrappers.F90` | (no module statement) | Compiler-neutral wrappers around the EcoSIM F90 driver entry points; "There needs to be a wrapper for the eocsim f90 driver as there are differences between how gfortran and intel compilers" (`f90src/ATSUtils/ecosim_wrappers.F90:1`). |

## `f90src/Balances/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Balances/ErosionBalMod.F90` | `ErosionBalMod` | Erosion bookkeeping; `public :: SinkSediments`. |
| `f90src/Balances/LateralTranspMod.F90` | `LateralTranspMod` | Cross-grid lateral transport; `public :: XGridTranspt`. |
| `f90src/Balances/RedistDataMod.F90` | `RedistDataMod` | Shared buffers for the redistribution step. |
| `f90src/Balances/RedistMod.F90` | `RedistMod` | Final state-update step from accumulated fluxes; `public :: redist, InitRedist` (called from `drivers/ecosim/EcoSIMAPI.F90:113`). |
| `f90src/Balances/RunoffBalMod.F90` | `RunoffBalMod` | Runoff solute accounting; `public :: XGridBoundSolutesRunoff`. |
| `f90src/Balances/SoilLayerDynMod.F90` | `SoilLayerDynMod` | "Subroutines to do soil relayering" (`f90src/Balances/SoilLayerDynMod.F90` DESCRIPTION). |
| `f90src/Balances/TillageMixMod.F90` | `TillageMixMod` | Tillage mixing of soil layers; `public :: ApplyTillageMixing`. |

## `f90src/ModelDiags/`

| File | Module | Purpose |
|---|---|---|
| `f90src/ModelDiags/BalancesMod.F90` | `BalancesMod` | Column balance checks; `public :: BegCheckBalances` (called at start of each step via `drivers/ecosim/EcoSIMAPI.F90`, see `EndCheckBalances` at `:119`). |
| `f90src/ModelDiags/HydrologyDiagMod.F90` | `HydrologyDiagMod` | Water-table depth diagnostic; `public :: DiagWaterTBLDepz`. |
| `f90src/ModelDiags/SoilDiagsMod.F90` | `SoilDiagsMod` | Soil gas pressure diagnostic; `public :: DiagSoilGasPressure` (called from `drivers/ecosim/EcoSIMAPI.F90:117`). |

## `f90src/DebugTools/`

| File | Module | Purpose |
|---|---|---|
| `f90src/DebugTools/DebugToolMod.F90` | `DebugToolMod` | `public :: PrintInfo` (plus `DebugPrint`); used for conditional trace output throughout `EcoSIMAPI`. |

## `f90src/Disturbances/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Disturbances/EcosysWarmingMod.F90` | `EcosysWarmingMod` | "Code to do ecosystem warming. E.g. soil warming, atmospheric warming, snow exclusion. Example warming configurations include..." (`f90src/Disturbances/EcosysWarmingMod.F90` DESCRIPTION block). |
| `f90src/Disturbances/ErosionMod.F90` | `ErosionMod` | Sediment detachment/deposition driver; `public :: erosion, InitErosion`. Called from `drivers/ecosim/EcoSIMAPI.F90:106`. |
| `f90src/Disturbances/FertilizerMod.F90` | `FertilizerMod` | `public :: ApplyFertilizerAtNoon` — applies fertilizer events mid-day. |
| `f90src/Disturbances/FireMod.F90` | `FireMod` | Fire events; `public :: config_fire, check_fire`. `config_fire` is called from `drivers/ecosim/EcoSIMAPI.F90:294`. |
| `f90src/Disturbances/PlantDisturbMod.F90` | `PlantDisturbMod` | "Code to apply distance to plants" (`f90src/Disturbances/PlantDisturbMod.F90` DESCRIPTION). |
| `f90src/Disturbances/SoilDisturbMod.F90` | `SoilDisturbMod` | `public :: SOMRemovalByDisturbance` — removes SOM pools during disturbance. |

## `f90src/Geochem/Box_chem/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Geochem/Box_chem/ChemEquilibriaMod.F90` | `ChemEquilibriaMod` | "Code to solve equilibrium chemistry, without the salt equilbrium. The solver assumes prescribed pH, and therefore [OH(-)]" (`f90src/Geochem/Box_chem/ChemEquilibriaMod.F90` DESCRIPTION). |
| `f90src/Geochem/Box_chem/GeoChemMathMod.F90` | `GeoChemMathMod` | Math helpers specific to the geochemistry solver (activity coefficients, bracketing). |
| `f90src/Geochem/Box_chem/InitSoluteMod.F90` | `InitSoluteMod` | Solute-module initialization; `public :: InitSoluteModel, InitSoluteProperty`. |
| `f90src/Geochem/Box_chem/SaltChemEquilibriaMod.F90` | `SaltChemEquilibriaMod` | Salt-mode equilibrium chemistry solver; `public :: SaltChemEquilibria`. |
| `f90src/Geochem/Box_chem/SoluteChemDataType.F90` | `SoluteChemDataType` | `chem_var_type` and `solute_flx_type` derived types plus instance holders. |

## `f90src/Geochem/Layers_chem/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Geochem/Layers_chem/SoluteMod.F90` | `SoluteMod` | Column-profile geochemistry driver; `public :: UreaHydrolysis, UpdateSoilFertlizer`. |

## `f90src/HydroTherm/CanopyPhys/`

| File | Module | Purpose |
|---|---|---|
| `f90src/HydroTherm/CanopyPhys/CanopyHydroMod.F90` | `CanopyHydroMod` | Canopy interception; `public :: CanopyInterceptPrecip`. |

## `f90src/HydroTherm/PhysData/`

| File | Module | Purpose |
|---|---|---|
| `f90src/HydroTherm/PhysData/HydroThermData.F90` | `HydroThermData` | Shared hydro-thermal working arrays; `public :: InitHydroThermData, DestructHydroThermData`. |
| `f90src/HydroTherm/PhysData/PhysPars.F90` | `PhysPars` | Physical parameters: `RAM` (min boundary-layer resistance), `MinSnowDepth` (min snow depth for full cover). |
| `f90src/HydroTherm/PhysData/SoilPhysParaMod.F90` | `SoilPhysParaMod` | Soil physics parameters; `public :: SetDeepSoil, CalcSoilThermConductivity`. |

## `f90src/HydroTherm/SnowPhys/`

| File | Module | Purpose |
|---|---|---|
| `f90src/HydroTherm/SnowPhys/SnowBalanceMod.F90` | `SnowBalanceMod` | `public :: SnowMassUpdate` (called from `redist`), `SnowpackLayering` (called after `SnowMassUpdate`). |
| `f90src/HydroTherm/SnowPhys/SnowPhysData.F90` | `SnowPhysData` | Snow-physics working buffers; `public :: InitSnowPhysData, DestructSnowPhysData`. |
| `f90src/HydroTherm/SnowPhys/SnowPhysMod.F90` | `SnowPhysMod` | "The snow model" (`f90src/HydroTherm/SnowPhys/SnowPhysMod.F90` DESCRIPTION). |
| `f90src/HydroTherm/SnowPhys/SnowTransportMod.F90` | `SnowTransportMod` | "Code to do water and tracer transport in snowpack" (file comment); `public :: SaltPercolThruSnow, DiagSnowChemMass`. |

## `f90src/HydroTherm/SoilPhys/`

| File | Module | Purpose |
|---|---|---|
| `f90src/HydroTherm/SoilPhys/SoilHydroParaMod.F90` | `SoilHydroParaMod` | `public :: GetSoilHydraulicVars, SoilHydroProperty` — hydraulic parameterization. |
| `f90src/HydroTherm/SoilPhys/WatsubDataMod.F90` | `WatsubDataMod` | `public :: InitWatsubData` — allocates working buffers for `watsub`. |
| `f90src/HydroTherm/SoilPhys/WatsubMod.F90` | `WatsubMod` | "Do water and enerby balance calculation. The module diagnoses the mass and energy fluxes associated with soil/snow water (vapor, liquid and ice) and energy, and updates ..." (`f90src/HydroTherm/SoilPhys/WatsubMod.F90` DESCRIPTION). Called from `drivers/ecosim/EcoSIMAPI.F90:54`. |

## `f90src/HydroTherm/SurfPhys/`

| File | Module | Purpose |
|---|---|---|
| `f90src/HydroTherm/SurfPhys/SurfLitterPhysMod.F90` | `SurfLitterPhysMod` | Surface-litter energy balance; `public :: SurfLitREnergyBalanceM, UpdateLitRPhys`. |
| `f90src/HydroTherm/SurfPhys/SurfPhysAPI.F90` | `SurfPhysAPI` | Surface-physics API shim (actual module named `SurfPhysAPI`; public contents live in adjacent modules). |
| `f90src/HydroTherm/SurfPhys/SurfPhysData.F90` | `SurfPhysData` | Surface-physics buffers including `VapXAir2TopLay` (vapor flux from canopy air to top soil layer); `public :: InitSurfPhysData, DestructSurfPhysData`. |
| `f90src/HydroTherm/SurfPhys/SurfPhysMod.F90` | `SurfPhysMod` | "Code for doing surface physics" (`f90src/HydroTherm/SurfPhys/SurfPhysMod.F90` file comment). |

## `f90src/IOutils/`

| File | Module | Purpose |
|---|---|---|
| `f90src/IOutils/ClimReadMod.F90` | `ClimReadMod` | Climate forcing reader; `public :: ReadClim` (also exports `read_soil_warming_Tref`). |
| `f90src/IOutils/ForcWriterMod.F90` | `ForcWriterMod` | Optional writer for the BGC forcing cache; `public :: WriteBBGCForc`. |
| `f90src/IOutils/HistDataType.F90` | `HistDataType` | "This module is an intermediate step to support ascii output. When output is done with netcdf, no id is needed." (`f90src/IOutils/HistDataType.F90` comment). |
| `f90src/IOutils/HistFileMod.F90` | `HistFileMod` | History tape management (`hist_htapes_build`, `hist_nhtfrq`, `hist_mfilt`, `hist_fincl1`, ...). Called from `drivers/ecosim/ecosim.F90:115`. |
| `f90src/IOutils/MicrobeInfoMod.F90` | `MicrobeInfoMod` | "Define microbial parameters" — reader/loader for the microbial parameter table. |
| `f90src/IOutils/PlantInfoMod.F90` | `PlantInfoMod` | "Code to read plant information" (`f90src/IOutils/PlantInfoMod.F90` DESCRIPTION); exports `ReadPlantTraitTable` used by `InitModules`. |
| `f90src/IOutils/ReadManagementMod.F90` | `ReadManagementMod` | `public :: ReadManagementFiles` — parses soil/plant management input files. |
| `f90src/IOutils/RestartMod.F90` | `RestartMod` | "Code to write restart/check point files" (`f90src/IOutils/RestartMod.F90` DESCRIPTION); exports `get_restart_date`. |
| `f90src/IOutils/bhistMod.F90` | `bhistMod` | `#include "shr_assert.h"` based history helpers (column-level history writing). |
| `f90src/IOutils/readimod.F90` | `readiMod` | "THIS SUBROUTINE READS ALL SOIL AND TOPOGRAPHIC INPUT FILES" (`f90src/IOutils/readimod.F90` DESCRIPTION). Entry point `readi` called from `drivers/ecosim/ecosim.F90`. |
| `f90src/IOutils/readsmod.F90` | `readsmod` | `public :: ReadClimSoilForcing` — climate + soil forcing reader. |
| `f90src/IOutils/restUtilMod.F90` | `restUtilMod` | `public :: restartvar` — generic NetCDF restart variable read/write wrapper. |

## `f90src/Mesh/` — see above

## `f90src/Microbial_bgc/Box_Micmodel/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Microbial_bgc/Box_Micmodel/MicAutoCplxFGMod.F90` | `MicAutoCPLXMod` | Autotroph functional group dynamics; `public :: ActiveAutotrophs, AutotrophAnabolicUpdate`. |
| `f90src/Microbial_bgc/Box_Micmodel/MicBGCFGMod.F90` | `MicBGCMod` | "Codes to do soil biological transfOMBioResduations" [sic] — core single-layer soil microbial dynamics; exports `SoilBGCOneLayer`. |
| `f90src/Microbial_bgc/Box_Micmodel/MicFluxTypeMod.F90` | `MicFluxTypeMod` | `micfluxtype` derived type (microbial fluxes). |
| `f90src/Microbial_bgc/Box_Micmodel/MicForcTypeMod.F90` | `MicForcTypeMod` | `micforctype` derived type (microbial forcing/context). |
| `f90src/Microbial_bgc/Box_Micmodel/MicStateTraitTypeMod.F90` | `MicStateTraitTypeMod` | `micsttype` derived type (microbial state and traits). |
| `f90src/Microbial_bgc/Box_Micmodel/MicrobMathFuncMod.F90` | `MicrobMathFuncMod` | Microbial math helpers (kinetic function evaluations). |
| `f90src/Microbial_bgc/Box_Micmodel/MicrobeDiagTypes.F90` | `MicrobeDiagTypes` | "Accumulative flux diagnostics; fraction diagnostics, used for substrate competition/uptake" — `Cumlate_Flux_Diag_type`, `Microbe_Diag_type`. |

## `f90src/Microbial_bgc/Layers_Micmodel/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Microbial_bgc/Layers_Micmodel/InitSOMBGCMod.F90` | `InitSOMBGCMOD` | `public :: InitSOMVars, InitSOMProfile` — initial SOM pool allocation per soil layer. |
| `f90src/Microbial_bgc/Layers_Micmodel/SoilBGCNLayMod.F90` | `SoilBGCNLayMod` | "Codes to do soil biological transformations" (layered driver); exports `InitNitro`, `DownwardMixOM`, `sumMicBiomLayL`. |

## `f90src/Minimath/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Minimath/LinearAlgebraMod.F90` | `LinearAlgebraMod` | "Code to do linear algebra" — small-matrix solvers. |
| `f90src/Minimath/MiniFuncMod.F90` | `MiniFuncMod` | "Compute coefficient for air-water gas transfer" (file comment). |
| `f90src/Minimath/MiniMathMod.F90` | `minimathmod` | "Some small subroutines/function to do safe math." Exports `addone`, `AZMAX1`, `AZERO`, `AZERO1`, `safe_adb`, `real_truncate`, `isLeap`. |

## `f90src/Modelconfig/` — see above

## `f90src/Modelforc/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Modelforc/DayMod.F90` | `DayMod` | `public :: day` — daily reinitialization stage. |
| `f90src/Modelforc/Hour1Mod.F90` | `Hour1Mod` | `public :: hour1` — sub-daily forcing stage; called from `drivers/ecosim/EcoSIMAPI.F90:47`. |
| `f90src/Modelforc/WthrMod.F90` | `WthrMod` | `public :: PrepHourlyWeather` — prepares hourly weather from input forcing. |
| `f90src/Modelforc/YearMod.F90` | `YearMod` | `public :: SetAnnualAccumlators` — resets annual accumulators. |

## `f90src/Modelpars/` — see above

## `f90src/Plant_bgc/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Plant_bgc/ExtractsMod.F90` | `ExtractsMod` | "THIS SUBROUTINE AGGREGATES ALL SOIL-PLANT C,N,P EXCHANGES FROM 'UPTAKE' AMD 'GROSUB' AND SENDS RESULTS TO 'REDIST'" (`f90src/Plant_bgc/ExtractsMod.F90` DESCRIPTION). |
| `f90src/Plant_bgc/GrosubsMod.F90` | `grosubsMod` | "Module for plant biological transformations" — allocation/growth. |
| `f90src/Plant_bgc/InitPlantMod.F90` | `InitPlantMod` | `public :: StartPlants, InitPlantPhenoMorphoBio` — plant-side startup. |
| `f90src/Plant_bgc/InitVegBGC.F90` | `InitVegBGC` | `public :: InitIrradianceGeometry` — canopy radiation geometry initialization. |
| `f90src/Plant_bgc/LitterFallMod.F90` | `LitterFallMod` | `public :: ResetDeadPlant, ReSeedPlants` — litterfall and re-seeding. |
| `f90src/Plant_bgc/NoduleBGCMod.F90` | `NoduleBGCMod` | Nodule (N-fixation) BGC; `public :: CanopyNoduleBiochemistry, RootNodulBiochemistry`. |
| `f90src/Plant_bgc/NutUptakeMod.F90` | `NutUptakeMod` | `public :: PlantNutientO2Uptake, ZeroNutrientUptake` — nutrient + O2 uptake top-level. |
| `f90src/Plant_bgc/PhotoSynsMod.F90` | `PhotoSynsMod` | `public :: ComputeGPP` — canopy photosynthesis / GPP. |
| `f90src/Plant_bgc/PlantBalMod.F90` | `PlantBalMod` | "Code to do mass balance calculation for plant bgc" (file comment). |
| `f90src/Plant_bgc/PlantBranchMod.F90` | `PlantBranchMod` | "Module for plant biological transformations" — branch-level dynamics. |
| `f90src/Plant_bgc/PlantDebugMod.F90` | `PlantDebugMod` | `public :: PrintRootTracer` — plant-side debug print helpers. |
| `f90src/Plant_bgc/PlantDisturbByFireMod.F90` | `PlantDisturbByFireMod` | `public :: StageRootRemovalByFire, RemoveRootByFire`. |
| `f90src/Plant_bgc/PlantDisturbByGrazingMod.F90` | `PlantDisturbByGrazingMod` | `public :: AbvgBiomRemovalByGrazing, RemoveStandDeadByGrazing`. `GY`/`GZ` partition grazed material between removal and respiration (file comment). |
| `f90src/Plant_bgc/PlantDisturbByTillageMod.F90` | `PlantDisturbByTillageMod` | `public :: RemoveBiomByTillage`. |
| `f90src/Plant_bgc/PlantDisturbsMod.F90` | `PlantDisturbsMod` | "Code to apply distance to plants" (`f90src/Plant_bgc/PlantDisturbsMod.F90` DESCRIPTION); `public :: InitPlantDisturbance`. |
| `f90src/Plant_bgc/PlantMathFuncMod.F90` | `PlantMathFuncMod` | Plant-side math helpers (curve fits, logistic functions). |
| `f90src/Plant_bgc/PlantNonstElmDynMod.F90` | `PlantNonstElmDynMod` | Non-structural C/N/P dynamics; `public :: PlantNonstElmTransfer, SeasonStoreShootTransfer`. |
| `f90src/Plant_bgc/PlantPhenolMod.F90` | `PlantPhenolMod` | "Code to do plant phenology" (`f90src/Plant_bgc/PlantPhenolMod.F90` DESCRIPTION). |
| `f90src/Plant_bgc/RootGasMod.F90` | `RootGasMod` | `public :: RootSoilGasExchange` — root-soil gas exchange. |
| `f90src/Plant_bgc/RootMod.F90` | `RootMod` | `public :: RootBGCModel` — root biogeochemistry driver. |
| `f90src/Plant_bgc/StomatesMod.F90` | `stomatesMod` | `public :: StomatalDynamics, PhotosynsDiag` — stomatal conductance and photosynthesis diagnostics. |
| `f90src/Plant_bgc/SurfaceRadiationMod.F90` | `SurfaceRadiationMod` | `public :: CanopyConditionModel` — canopy radiation/condition solver. |
| `f90src/Plant_bgc/UptakePars.F90` | `UptakePars` | Uptake parameters: `MaxIterNum` (max cycles in water-uptake convergence), etc. |
| `f90src/Plant_bgc/UptakesMod.F90` | `UptakesMod` | "THIS subroutine CALCULATES EXCHANGES OF ENERGY, C, N AND P BETWEEN THE CANOPY AND THE ATMOSPHERE AND BETWEEN ROOTS AND THE SOIL" (`f90src/Plant_bgc/UptakesMod.F90` DESCRIPTION); `public :: RootUptakes, InitUptake`. |

## `f90src/Prescribed_pheno/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Prescribed_pheno/PrescribePhenolMod.F90` | `PrescribePhenolMod` | Prescribed-phenology mode; `public :: GetRootProfile, SetCanopyProfile`. |

## `f90src/Transport/Nonsalt/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Transport/Nonsalt/InitNoSaltTransportMod.F90` | `InitNoSaltTransportMod` | `public :: InitTranspNoSaltModel, BackCopyStateVars`. |
| `f90src/Transport/Nonsalt/TranspNoSaltDataMod.F90` | `TranspNoSaltDataMod` | Working buffers for non-salt transport. |
| `f90src/Transport/Nonsalt/TranspNoSaltFastMod.F90` | `TranspNoSaltFastMod` | "Surface soil gaseous diffusion, advection, dissolution & volatilization" (file comment). |
| `f90src/Transport/Nonsalt/TranspNoSaltMod.F90` | `TranspNoSaltMod` | Outer non-salt transport driver; `public :: TranspNoSalt, InitTranspNoSalt, DestructTranspNoSalt`. Called from `drivers/ecosim/EcoSIMAPI.F90:87`. |
| `f90src/Transport/Nonsalt/TranspNoSaltSlowMod.F90` | `TranspNoSaltSlowMod` | Slow-path solute advection; `public :: TransptSlowNoSaltM, BubbleEffluxM`. |

## `f90src/Transport/Salt/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Transport/Salt/IngridTranspMod.F90` | `IngridTranspMod` | Within-grid salt transport; `public :: GetSaltTranspFlxM, SaltFall2Snowpack`. |
| `f90src/Transport/Salt/TranspSaltDataMod.F90` | `TranspSaltDataMod` | Working buffers for salt transport. |
| `f90src/Transport/Salt/TranspSaltMod.F90` | `TranspSaltMod` | Outer salt transport driver; `public :: TranspSalt`. Called from `drivers/ecosim/EcoSIMAPI.F90:96` when `salt_model` is true. |

## `f90src/Utils/`

| File | Module | Purpose |
|---|---|---|
| `f90src/Utils/EcoSimConst.F90` | `EcosimConst` | Fundamental constants (`Tref`, `LtHeatIceMelt`, geometric constants). |
| `f90src/Utils/ModelStatusType.F90` | `ModelStatusType` | `model_status_type` derived type; `public :: create_model_status_type`. |
| `f90src/Utils/StrToolsMod.F90` | `StrToolsMod` | `public :: parse_var_val_string, are_strings_equal_icase` — string utilities. |
| `f90src/Utils/TestMod.F90` | `TestMod` | "Codes to do regression tests" (`f90src/Utils/TestMod.F90` DESCRIPTION); exports `regression`. |
| `f90src/Utils/UnitMod.F90` | `UnitMod` | "Code for unit conversion" (`f90src/Utils/UnitMod.F90` file comment); exports `units`. |
| `f90src/Utils/abortutils.F90` | `abortutils` | `public :: endrun, check_bool, iulog` — safe abort and the global log unit. |
| `f90src/Utils/data_const_mod.F90` | `data_const_mod` | Mathematical constants (`DAT_CONST_PI`, ...). |
| `f90src/Utils/data_kind_mod.F90` | `data_kind_mod` | Kind definitions (`DAT_KIND_R8`, `yearIJ_type`). |
| `f90src/Utils/ecosim_log_mod.F90` | `ecosim_log_mod` | "Low-level shared variables for logging. Also, routines for generating log file messages." |
| `f90src/Utils/ecosim_time_mod.F90` | `ecosim_Time_Mod` | "The module contains subroutine to march the time" (`f90src/Utils/ecosim_time_mod.F90` DESCRIPTION); exports `ecosim_time_dat_type`, `getdow`, `get_steps_from_ymdhs`. |
| `f90src/Utils/fileUtil.F90` | `fileUtil` | "Check existence of a file" / "subroutines for file open with error check"; exports `namelist_to_buffer`, `ecosim_namelist_buffer_size`. |
| `f90src/Utils/ncdio_pio.F90` | `ncdio_pio` | "Generic interfaces to write fields to netcdf files (stand alone version)" (`f90src/Utils/ncdio_pio.F90` DESCRIPTION); exports `ncd_pio_openfile`, `ncd_nowrite`. |
| `f90src/Utils/shr_infnan_mod.F90` | `shr_infnan_mod` | Auto-generated IEEE NaN/Inf checks; `public :: shr_infnan_isnan, shr_infnan_isinf` (file header notes it was generated with `genf90.pl`). |
| `f90src/Utils/timings.F90` | `timings` | "Code to do runtime timing" (`f90src/Utils/timings.F90` DESCRIPTION); exports `start_timer`, `end_timer`. |

Note: `f90src/Utils/` also contains two non-Fortran sources, `clock.c` and `getfilename.c`, plus the header `dtypes.h`. They are built by `f90src/Utils/CMakeLists.txt` as C helpers.

---

## `drivers/ecosim/`

| File | Module / Program | Purpose |
|---|---|---|
| `drivers/ecosim/ecosim.F90` | `program main` | Top-level standalone driver; reads the namelist, sets up the mesh, runs year-by-year via `AdvanceModelOneYear` (`drivers/ecosim/ecosim.F90:140`). |
| `drivers/ecosim/EcoSIMAPI.F90` | `EcoSIMAPI` | "Read control namelist" + step driver; exports `AdvanceModelOneYear`, `readnamelist`, `regressiontest`, `write_modelconfig` (`drivers/ecosim/EcoSIMAPI.F90:29-31`). |

## `drivers/ATSEcoSIM/`

| File | Module / Program | Purpose |
|---|---|---|
| `drivers/ATSEcoSIM/ATSEcoSIM_test.F90` | `program EcoATSTest` | ATS-coupling smoke test; builds `BGCState`/`BGCProperties`/`BGCSizes` and exercises `ATSCPLMod`. |

## `drivers/aquachem/`

| File | Module / Program | Purpose |
|---|---|---|
| `drivers/aquachem/aquachem.F90` | `program main` | Standalone aqueous-chemistry driver. |
| `drivers/aquachem/AquachemMod.F90` | `AquachemMod` | Aqueous-chemistry module; `public :: getvarlist, initmodel, getvarllen, runchem`. |
| `drivers/aquachem/AquaSaltChemMod.F90` | `AquaSaltChemMod` | Salt-mode extension; `public :: Init_geochem_salt, getvarlist_salt, initmodel_salt, RunModel_salt`. |

## `drivers/boxsbgc/`

| File | Module / Program | Purpose |
|---|---|---|
| `drivers/boxsbgc/batchsbgc.F90` | `program main` | "Single layer model" batch driver for soil BGC. |
| `drivers/boxsbgc/batchmod.F90` | `batchmod` | "Configure the batch mode of the soil bgc" (`drivers/boxsbgc/batchmod.F90` DESCRIPTION). |
| `drivers/boxsbgc/ChemMod.F90` | `ChemMod` | Chemistry module for the box driver; `public :: RunModel_nosalt`. |
| `drivers/boxsbgc/ForcTypeMod.F90` | `ForcTypeMod` | Forcing derived type used by the box driver. |
| `drivers/boxsbgc/MicIDMod.F90` | `MicIDMod` | Microbial IDs used by the box driver. |

## `drivers/boxshared/`

| File | Module / Program | Purpose |
|---|---|---|
| `drivers/boxshared/ChemIDMod.F90` | `ChemIDMod` | Shared chemistry variable IDs; `public :: getvarlist_nosalt`. |

## `drivers/mockbatch/`

| File | Module / Program | Purpose |
|---|---|---|
| `drivers/mockbatch/mockdriver.F90` | `program main` | Minimal-dependency mock driver (for CI smoke tests). |
| `drivers/mockbatch/MockMod.F90` | `MockMod` | Mock module; `public :: getvarllen, getvarlist, initmodel`. |

## `drivers/plantbgc/`

| File | Module / Program | Purpose |
|---|---|---|
| `drivers/plantbgc/plantdriver.F90` | `program main` | Standalone plant-BGC driver. |
| `drivers/plantbgc/PlantMod.F90` | `PlantMod` (driver-local, not the `f90src/APIs` one) | Exposes `getvarllen`, `getvarlist`, `initmodel` for plant BGC batch runs. |

## `drivers/tools/`

| File | Module / Program | Purpose |
|---|---|---|
| `drivers/tools/ClimReader.F90` | `program ClimReader` | Standalone climate-file reader (uses `ClimReadMod`). |
| `drivers/tools/ClimTransformer.F90` | `program ClimTransformer` | Climate-array reshaping / transformation utility (`ClimReadMod`, `ClimForcDataType`). |
| `drivers/tools/EcoATSTest.F90` | `program EcoATSTest` | ATS coupling smoke test via `ATSCPLMod`. |
| `drivers/tools/EcoATSTest_old.F90` | `program EcoATSTest` | Older variant of the ATS smoke test (retained for reference). |
| `drivers/tools/GridReader.F90` | `program GridReader` | Reads the grid NetCDF file via `ncdio_pio`. |
| `drivers/tools/HFileTest.F90` | `program HFileTest` | Smoke-tests `HistFileMod` history tape handling. |
| `drivers/tools/NamelistTest.F90` | `program NamelistTest` | Smoke-tests namelist parsing with `etimer`. |
| `drivers/tools/PlantManagementReader.F90` | `program PlantManagementReader` | Tests plant-management file reading (`PlantInfoMod`). |
| `drivers/tools/SoilManagementReader.F90` | `program SoilManagementReader` | Tests soil-management file reading (`ReadManagementMod`). |
| `drivers/tools/SoilWarmReadTest.F90` | `program SoilWarmReadTest` | Tests `read_soil_warming_Tref` in `ClimReadMod`. |
| `drivers/tools/etimerTest.F90` | `program etimerTest` | Walks the `etimer` time manager (`ecosim_time_mod`). |
| `drivers/tools/restartTest.F90` | `program restartTest` | Restart round-trip test using `RestartMod` and `HistFileMod`. |

---

## Coverage and caveats

- All 210 F90 sources are enumerated. Some modules are small (single public symbol, e.g., `f90src/DebugTools/DebugToolMod.F90`), in which case the description restates the public symbol in context.
- Several files had no top-of-file DESCRIPTION block. Their purpose was inferred from (a) the module's first `public ::` line, (b) declared derived types, or (c) the pattern of allocatable field arrays they contain. Those inferences are explicit (e.g., "Canopy state: `LAI_col`, ...") so a reader can verify them against the source without re-reading this document.
- The stub file `f90src/APIs/SurfPhysAPI.F90` (13 lines) is intentional; its companion `f90src/HydroTherm/SurfPhys/SurfPhysAPI.F90` holds the real API.
- Two non-Fortran sources under `f90src/Utils/` (`clock.c`, `getfilename.c`) are not listed in the inventory, since this document is limited to Fortran modules. They are compiled by the subsystem's CMakeLists.txt.
