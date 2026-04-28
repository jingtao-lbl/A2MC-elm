---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Ecosim_datatype, APIs, APIData}/`
**Last verified:** 2026-04-24
---

# Ecosim_datatype: State and Flux Data Layer

## Purpose

`f90src/Ecosim_datatype/` holds the central, column-/grid-oriented state and flux arrays that the rest of EcoSIM reads and writes. It is the module layer that sits between the low-level utilities (`Utils`, `Modelconfig`, `Minimath`, `Mesh`) and every physics module (plant BGC, microbial BGC, hydrothermal, transport, geochem). Almost every physics module `use`s several of these modules.

Despite the suffix `DataType` in many filenames, this layer is **not built from Fortran derived types**. It is organized as a set of **module-level `allocatable` arrays** (`real(r8),target,allocatable :: X(:,:,:)` and friends), with a per-module pair of `Init*Data` / `Destruct*Data` subroutines. The `target` attribute is used because other layers (notably the APIs layer, `f90src/APIs/` and `f90src/APIData/`) point into these arrays via pointer components of derived types to avoid tight coupling. Derived types do appear, but they are the exception rather than the rule in this directory.

## Module pattern

The following is the representative layout for modules in this directory, taken from `SoilBGCDataType` (`f90src/Ecosim_datatype/SoilBGCDataType.F90:1-419`):

```fortran
module SoilBGCDataType
  use data_kind_mod, only : r8 => DAT_KIND_R8
  use GridConsts                                 ! JX, JY, JZ, JD, JV, JH, JP, ...
  use ElmIDMod, only : NumPlantChemElms          ! element indices (C, N, P, ...)
  use TracerIDMod                                ! idg_*, ids_*, idom_* tracer indices
  use EcoSIMConfig, only : jcplx => jcplxc, jsken => jskenc
  implicit none
  character(len=*), private, parameter :: mod_filename = __FILE__

  real(r8),target,allocatable :: CNH4_vr(:,:,:)     !soil NH4 content, [mg kg-1]
  real(r8),target,allocatable :: CNO3_vr(:,:,:)     !soil NO3 content, [mg kg-1]
  ! ... many more arrays, each with an inline comment containing units ...

  private :: InitAllocate
contains

  subroutine InitSoilBGCData(NumOfPlantLitrCmplxs)
    integer, intent(in) :: NumOfPlantLitrCmplxs
    call InitAllocate(NumOfPlantLitrCmplxs)
  end subroutine InitSoilBGCData

  subroutine InitAllocate(NumOfPlantLitrCmplxs)
    allocate(CNH4_vr(JZ,JY,JX));     CNH4_vr = 0._r8
    ! ... one allocate + zero-init per array ...
  end subroutine InitAllocate

  subroutine DestructSoilBGCData
    use abortutils, only : destroy
    call destroy(CNH4_vr)
    ! ... one destroy per array ...
  end subroutine DestructSoilBGCData
end module SoilBGCDataType
```

Key conventions visible across the directory:

- **Naming suffixes encode rank / scope.**
  - `_vr` = vertically resolved, `(:,:,:)` shaped `(JZ,JY,JX)` or `(0:JZ,JY,JX)` — layer-by-column fields (e.g. `CNH4_vr` at `SoilBGCDataType.F90:14`, `TKS_vr` at `SoilHeatDataType.F90:1`).
  - `_col` = column-aggregated, `(:,:)` shaped `(JY,JX)` (e.g. `BandDepthNH4_col` at `SoilBGCDataType.F90:99`, `NetCO2Flx2Canopy_col` at `CanopyDataType.F90:59`).
  - `_pft` / `_pvr` / `_brch` / `_node` / `_raxes` / `_snvr` / `_clyr` = indexed by plant functional type, plant-vertical, branch, node, root-axis, snow-vertical, canopy-layer respectively (e.g. `CanopyGrosRCO2_pft` at `PlantDataRateType.F90:12`, `VLSnowHeatCapM_snvr` at `SnowDataType.F90:1`).
  - `_2DH`, `_3D` = lateral 2-D / 3-D transport fluxes (e.g. `WaterFlowSoiMicP_3D` at `SoilBGCDataType.F90:109`, `TXGridSurfRunoff_2DH` at `SoilWaterDataType.F90:1`).
  - `_CumYr`, `_cumflx`, `_beg` = cumulative totals, cumulative fluxes, beginning-of-timestep snapshots (e.g. `FertN_Flx_CumYr_col` at `SoilBGCDataType.F90:55`, `trcg_TotalMass_beg_col` at `SoilBGCDataType.F90:37`).
- **State vs flux is separated by prefix, not by module.** `R*` / `*_flx*` names are rates / fluxes (`RCH4ProdHydrog_vr`, `GasHydroLoss_flx_col`); un-prefixed or mass-like names are state (`trcs_solml_vr`, `trcg_gasml_vr`). State and its matching fluxes usually live in the same module.
- **Units are carried in inline Fortran comments**, not as code-level attributes. Common units: `[g d-2]`, `[g d-2 h-1]`, `[m3 d-2]`, `[MJ d-2 h-1]`, `[mol d-2]`, `[K]`, `[-]`. The `d-2` means "per cell (decimeter squared footprint)" in the EcoSIM grid convention.
- **Tracer-indexed arrays** use the ID ranges defined in `TracerIDMod` (`idg_beg:idg_end` for gases, `ids_beg:ids_end` for solutes, `idom_beg:idom_end` for DOM kinds, `ids_nut_beg:ids_nuts_end` for nutrient solutes). See `SoilBGCDataType.F90:158-184` for typical `allocate(X(idg_beg:idg_NH3, ...))` patterns.
- **Derived types appear only where richer semantics are needed**, for example `EcoSIMHistMod` carries history-file metadata via `CHARACTER(len=16)` arrays (`EcoSIMHistMod.F90:2-60`) and `PlantTraitTableMod` carries integer PFT trait tables indexed by a single `_tab` dimension (`PlantTraitTableMod.F90:1-60`). Most other modules are flat.
- **Lifecycle:** each module exports an `Init*Data`-style allocator and a `Destruct*Data` deallocator. These are called from top-level init/destruct drivers in `f90src/Ecosim_mods/InitAllocMod.F90` and `f90src/Main/EcoSIMDesctruct.F90`.

Because the arrays are module-level globals, any physics module that does `use SoilBGCDataType` has direct read/write access. This is the canonical EcoSIM "shared state" pattern. The separate `APIs/` and `APIData/` layers (see `../apis/index.md`) exist to decouple the plant and microbial physics modules from these globals.

## Files by domain (32 total)

File counts and line counts reflect the pin.

### Plant state and fluxes (7 files)

| File | Line count | One-line description |
|---|---|---|
| `PlantTraitDataType.F90` | 556 | PFT-level trait arrays (photosynthetic type, allocation fractions, allometric coefficients, Vmax references, leaf/root angles). Some integer PFT traits such as `Myco_pft` (`PlantTraitDataType.F90:1`). |
| `PlantTraitTableMod.F90` | 386 | Lookup tables indexed by PFT-id for discrete plant traits (`iEmbryophyteType_pft_tab`, `iPlantPhotosynsType_pft_tab`, `iPlantRootProfile_tab`, `iPlantPhenolPattern_tab`). Loaded once from plant parameter files. |
| `PlantDataRateType.F90` | 428 | PFT- and root-resolved rates: canopy respiration, NEE, N2-fixation, root nutrient uptake demands (`RootNH4DmndSoil_pvr`, `RootH2PO4DmndSoil_pvr`), root-soil exudation fluxes, fire emissions. Central hub for plant-to-soil and plant-to-atmosphere exchange. |
| `CanopyDataType.F90` | 583 | Canopy energy/radiation/photosynthesis state: LAI, stomatal resistances, leaf intracellular CO2/O2, Vmax per canopy node, canopy PAR/SW absorption, longwave emission. |
| `CanopyRadDataType.F90` | 90 | Canopy radiation geometry: leaf-angle sines/cosines (`SineLeafAngle`), sky/leaf azimuth factors (`OMEGA`), scattering flags (`iScatteringDiffus`). |
| `RootDataType.F90` | 410 | Root morphology and state by primary root axis and layer: axis count (`NumPrimeRootAxes_pft`), deepest tip layer (`NRoot1stTipLay_raxes`), alive flags (`isPlantRootAlive_pft`). |
| `PlantMgmtDataType.F90` | 110 | Plant management state: presence flag (`flag_active_pft`), thinning (`THIN_pft`), harvest efficiency (`FracBiomHarvsted`), harvest type (`iHarvstType_pft`), cut proxy (`CanopyCutProxy_pft`). |

### Soil biogeochemistry and microbes (4 files)

| File | Line count | One-line description |
|---|---|---|
| `SoilBGCDataType.F90` | 419 | Largest state module: soil tracer masses (`trcs_solml_vr`, `trcs_soHml_vr`, `trcg_gasml_vr`), DOM pools, microbial production/uptake (`trcs_RMicbUptake_vr`), CH4/N2O production rates (`RCH4ProdHydrog_vr`, `RDen_NO2toN2O_vr`), pH/CEC/AEC, hydrological and surface fluxes, fertilizer band geometry. |
| `MicrobialDataType.F90` | 181 | Microbial biomass and demand by heterotroph group: `mBiomeHeter_vr` (6-D), aqueous O2 demand (`RO2DmndHetert_vr`), substrate demands per microbial guild (DOC, acetate, NH4, etc.). |
| `SOMDataType.F90` | 150 | Soil organic matter initial pools (`RSC_vr`, `RSN_vr`, `RSP_vr`) and fractionation across kinetic components (`CFOSC_vr`, `CNOSC_vr`). |
| `AqueChemDatatype.F90` | 231 | Aqueous geochemistry bulk contents: `CAL_vr`, `CFE_vr`, `CCA_vr`, `CMG_vr`, plus precipitates / exchangeable pools feeding the `GeochemAPI` solute solver. |

### Soil physics, hydrology, heat (4 files)

| File | Line count | One-line description |
|---|---|---|
| `SoilPhysDataType.F90` | 114 | Soil hydraulic properties: slope (`SLOPE_col`), field capacity / wilting point (`FieldCapacity_vr`, `WiltPoint_vr`), saturated hydraulic conductivity (`SatHydroCondVert_vr`), soil surface depth. |
| `SoilPropertyDataType.F90` | 121 | Static soil properties: initial organic C (`CORGCI_vr`), porosity (`POROSI_vr`), texture (`CSAND_vr`, `CSILT_vr`), macropore fraction (`SoilFracAsMacPt0_vr`). |
| `SoilHeatDataType.F90` | 91 | Soil thermal state and phase-change flux accumulators: `TKS_vr` (soil temperature [K]), `TLIceThawMicP_vr`, `TLPhaseChangeHeat2Soi_vr`, `XPhaseChangeHeatL_snvr`. |
| `SoilWaterDataType.F90` | 349 | Soil water state/flux incl. macro- and micropore water, ponding (`iPondFlag_col`, `iPondBotLev_col`), grid-crossing surface runoff (`TXGridSurfRunoff_2DH`), ice volume changes. |

### Surface, snow, land-surface (4 files)

| File | Line count | One-line description |
|---|---|---|
| `SurfSoilDataType.F90` | 84 | Bare-soil/snow surface fractions (`FracSurfAsSnow_col`, `FracSurfBareSoil_col`), ground longwave emission (`LWRadBySurf_col`), net surface radiation. |
| `SurfLitterDataType.F90` | 105 | Surface litter layer: bulk density (`BulkDensLitR`), litter type (`iLitrType_col`), tillage incorporation factor (`XTillCorp_col`), litter-to-soil water transfer (`WatFLoLitr2SoilM_col`). |
| `SnowDataType.F90` | 258 | Snowpack state: volumetric heat capacity (`VLSnowHeatCapM_snvr`), snow water flux (`WatFlowInSnowM_snvr`), wind-redistribution flux (`DrySnoFlxByRedistM_2DH`), soil + snow albedo. |
| `LandSurfDataType.F90` | 86 | Aerodynamic roughness / displacement: `SoilSurfRoughness_col`, `ZeroPlaneDisplacem_col`, `RoughnessLength_col`, wind-measurement height. |

### Transport and chemistry coupling (2 files)

| File | Line count | One-line description |
|---|---|---|
| `ChemTranspDataType.F90` | 114 | Temperature-scaled diffusivities used by transport: `GasDifcT_vr`, `SoluteDifusvtyT_vr`, `O2AquaDiffusvity`, dispersivity scalar (`DISP_3D`). |
| `SedimentDataType.F90` | 122 | Erosion/sediment state: total erosion rate (`TSED_col`), detachment coefficients (`SoilDetachability4Erosion1/2`), detachment shape parameter (`XER_col`). |

### Flux aggregates and balance checks (3 files)

| File | Line count | One-line description |
|---|---|---|
| `EcosimBGCFluxType.F90` | 97 | Column-level ecosystem fluxes for I/O and history: `Eco_NetRad_col`, `Eco_Heat_Latent_col`, `Eco_Heat_Sens_col`, `Eco_GPP_CumYr_col`. |
| `EcoSimSumDataType.F90` | 68 | Landscape-level (1-D, indexed by element) scalars: `SurfGas_lnd`, `PlantElemntStoreLandscape`. Aggregates used for whole-domain reporting. |
| `BalanceCheckDataType.F90` | 39 | Per-column closure errors written by the balance check framework: `WaterErr_col`, `HeatErr_col`, `EcoElmErr_col`, `PlantElmErr_col`. |

### Forcing and management (4 files)

| File | Line count | One-line description |
|---|---|---|
| `ClimForcDataType.F90` | 341 | Atmospheric / climate forcing and warming-experiment scalars: shortwave scalar (`srad_scalar_col`), emissivity modifier (`EMS_Modify_Scalar_col`), reference temperature profile (`TKS_ref_vr`), ecosystem absorbed SW (`Eco_RadSW_col`). |
| `FertilizerDataType.F90` | 75 | Fertilizer N and P applied to broadcast vs banded compartments (`FertN_mole_soil_vr`, `FertN_mole_Band_vr`, `FertP_mole_soil_vr`, `FertP_mole_band_vr`), tillage mixing fraction (`DepzCorp_col`). |
| `IrrigationDataType.F90` | 242 | Irrigation scheduling and application rates: auto-irrigation dates (`IIRRA`), application rate (`RRIG`), surface / subsurface irrigation (`IrrigSurface_col`, `IrrigSubsurf_col`). |
| `FlagDataType.F90` | 74 | Integer control / disturbance flags: fertilizer release type (`IYTYP`), soil disturbance type (`iSoilDisturbType_col`), Koppen zone (`KoppenClimZone_col`), irrigation option (`iIrrigOpt_col`), soil-profile reset flag (`iResetSoilProf_col`). |

### Grid, control, auxiliary (4 files)

| File | Line count | One-line description |
|---|---|---|
| `GridDataType.F90` | 94 | Geometric grid arrays: depth-to-layer-bottom (`CumDepz2LayBottom_vr`), layer thickness (`DLYR_3D`), cross-section / inter-cell distance (`XDPTH_3D`), layer midpoint depth (`SoilDepthMidLay_vr`). |
| `EcoSIMCtrlDataType.F90` | 66 | Runtime control scalars (time-step subcycle counts `NPX`,`NPY`; scenario start/end day `IBEGIN`/`IEND`/`ILAST`; current year `iYearCurrent`) plus small zero-padding arrays (`ZEROS`, `ZERO4Uptk_pft`, ...) used as numerical guards. The only module here with an explicit `save`-free public scalar set plus minimal allocatables. |
| `EcoSIMHistMod.F90` | 60 | History / parameter-file name tables: `DATAP(:,:,:)`, `DATAM(:,:,:)`, `DATAZ(:,:,:)` as `CHARACTER(len=16)` arrays mapping (day, NY, NX) to scenario files. Unusual in this directory for being a pure character-array module. |
| `NumericalAuxMod.F90` | 42 | Two "dribble" buffers used by the transport solver to smooth sub-time-step fluxes: `trcs_solml_drib_vr`, `DOM_MicP_drib_vr`. Intentionally tiny; kept separate so both transport and source modules can share without circular `use`. |

## Conventions at a glance

- All arrays are **module-level**, `target`, `allocatable`, and paired with an `Init*Data` / `Destruct*Data` subroutine.
- Shape follows the `(tracer, layer, NY, NX)` / `(layer, NY, NX)` / `(NY, NX)` rank hierarchy with lower-bound zero for the top soil layer when surface-litter is needed (e.g. `allocate(CPO4B_vr(0:JZ,JY,JX))` at `SoilBGCDataType.F90:189`).
- Shared lower/upper tracer bounds come from `TracerIDMod` (`ids_beg`, `ids_end`, `idg_beg`, `idg_end`, `idom_beg`, `idom_end`, `ids_NH4`, `ids_NH4B`, `ids_NO3`, `ids_NO3B`, `ids_H1PO4`, `ids_H1PO4B`, ...).
- Element indices (C, N, P, ...) come from `ElmIDMod` as `NumPlantChemElms`.
- PFT trait table variables carry a `_tab` suffix (see `PlantTraitTableMod.F90`) and are always 1-D (keyed on PFT id).

## Typical consumer pattern

A physics module (see for example `f90src/Plant_bgc/GrosubsMod.F90` or `f90src/Microbial_bgc/Box_Micmodel/MicBGCMod.F90`) will:

1. `use` several `*DataType` modules to get direct access to `_col` / `_vr` / `_pft` arrays.
2. Read state (e.g. `TKS_vr(L,NY,NX)`, `trcs_solml_vr(ids_NH4,L,NY,NX)`).
3. Compute rates and write into flux arrays (e.g. `RCH4ProdHydrog_vr(L,NY,NX)`, `RootNH4Uptake_pft(NZ,NY,NX)`).

For the plant and microbial physics modules, direct access is intentionally routed through the `PlantAPIData` and per-layer micro-types instead (see `../apis/index.md` and `../apis/api_data.md`), so that those physics modules can be compiled and evolved without depending on every `*DataType` module here.
