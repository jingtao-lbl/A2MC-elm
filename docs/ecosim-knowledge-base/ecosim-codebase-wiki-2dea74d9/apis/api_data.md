---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Ecosim_datatype, APIs, APIData}/`
**Last verified:** 2026-04-24
---

# API Data Layer: `f90src/APIData/`

## Files

A single file, wrapped in its own CMake library (`f90src/APIData/CMakeLists.txt:1-9`):

| File | Line count | Role |
|---|---|---|
| `PlantAPIData.F90` | 2179 | Plant-facing derived types, their module-level singleton instances, and their lifecycle routines. |

The library sits between `Ecosim_datatype/` and `Plant_bgc/` in the dependency graph. Plant physics modules `use PlantAPIData` to read and write their own state / flux containers, instead of reaching into the shared globals in `f90src/Ecosim_datatype/`. `grep -rn "use PlantAPIData" f90src/Plant_bgc/` shows 22 plant-kernel modules depend on this layer.

## Why separate from `Ecosim_datatype/`?

The `*DataType` modules in `Ecosim_datatype/` hold the model's **authoritative column-by-column state** as flat, module-level `allocatable` arrays (see `../data_types/index.md` for the full survey). Those arrays are written by every subsystem: plant, microbe, soil physics, transport, geochem, fire, tillage. That makes them a natural shared-memory region for the outer driver, but a poor API boundary for a single subsystem:

1. **Ownership is unclear at a sub-system level.** Plant kernels should not modify `trcg_gasml_vr` directly; they should declare exactly which fluxes they produce.
2. **Shape mismatch.** Plant kernels operate on one column at a time over all PFTs, branches, nodes, root axes, canopy layers. The global `_col`/`_vr`/`_pft` arrays are indexed by `(NY, NX)` on the outermost dimensions; plant kernels want PFT-first slices of length `JP1` rather than `(:, NY, NX)`.
3. **Compilation coupling.** If every plant file `use`d every `*DataType`, any change to a soil array shape would force every plant module to recompile.

`PlantAPIData` solves these by defining twelve domain-scoped derived types (`plant_siteinfo_type`, `plant_biom_type`, ...), each holding just the fields that plant kernels need, typically as `pointer` slices with the `(NY, NX)` outer dimensions already collapsed. The per-column `PlantAPISend` (`../apis/api_layer.md` §2) copies data in; the physics kernels read/write the `plt_*` singletons; `PlantAPIRecv` copies results back out.

## Module structure

`PlantAPIData.F90` layout:

- **Public scalar configuration pointers** (`PlantAPIData.F90:14-29`): 17 `integer, pointer` scalars (`NumGrowthStages`, `MaxNumRootAxes`, `MaxNumBranches`, `JP1`, `NumOfSkyAzimuthSects1`, `jcplx`, `NumOfLeafAzimuthSectors1`, `NumCanopyLayers1`, `JZ1`, `NumLeafZenithSectors1`, `MaxNodesPerBranch1`, `jsken`, `NumLitterGroups`, `NumOfPlantMorphUnits`, `NumOfPlantLitrCmplxs`, `jroots`) that alias into `pltpar` (from `EcoSiMParDataMod`). Associated in `InitPlantAPIData` at `PlantAPIData.F90:1738-1755`.
- **Twelve public derived types** (see the table below), each with a `contains / procedure, public :: Init / Destroy` type-bound-procedure pair.
- **Twelve module-level singleton instances** (`PlantAPIData.F90:910-921`), each declared `public, target`.
- **Lifecycle driver subroutines** (`InitPlantAPIData`, `DestructPlantAPIData`, plus twelve `plt_<x>_init` / `plt_<x>_destroy` bodies).

## The twelve derived types

| Type | Defined at | Instance | Purpose |
|---|---|---|---|
| `plant_siteinfo_type` | `PlantAPIData.F90:32-94` | `plt_site` | Column-level site info: latitude (`ALAT`), altitude (`ALT`), mean annual air temperature (`ATCA`), atmospheric CO2/O2 concentrations (`CO2E`, `OXYE`, `CCO2EI_gperm3`), wind measurement height, daylengths, column indices (`NU`, `NL`, `NK`, `NP`, `NP0`, `MaxNumRootLays`), Koppen zone, active-plant count, numerical thresholds (`ZERO`, `ZEROS`, `ZEROS2`). Also holds pointer-array aliases to surface-to-layer geometry (`DLYR3`, `AREA3`, `CumSoilThickness_vr`), plant populations (`PPI_pft`, `PPatSeeding_pft`, `PPX_pft`, `PlantPopulation_pft`), active-pft flag, atmospheric gas vector (`AtmGasc(idg_beg:idg_NH3)`), and subcycle-resolved soil water/air/tortuosity (`VLWatMicPM_vr(60,0:JZ1)`). |
| `plant_photosyns_type` | `PlantAPIData.F90:96-167` | `plt_photo` | Photosynthesis parameters and state per PFT, branch, canopy node. Vmax references (`VmaxSpecRubCarboxyRef_pft`, `VmaxRubOxyRef_pft`, `VmaxPEPCarboxyRef_pft`), Km's (`XKCO2_pft`, `XKO2_pft`, `Km4PEPCarboxy_pft`), C3/C4 branch rates, leaf aqueous/gaseous CO2/O2 concentrations, stomatal and cuticle resistances, chlorophyll/protein partitioning, per-node carboxylation rates (`CO2lmtRubiscoCarboxyRate_node(:,:,:)` etc.), and per-sector sunlit leaf area (`LeafAreaSunlit_zsec(:,:,:,:,:)`). |
| `plant_radiation_type` | `PlantAPIData.F90:169-214` | `plt_rad` | Canopy radiation state and fluxes: net radiation, longwave/shortwave partitions at canopy and ground, fraction of PAR absorbed by canopy, ecosystem-level `Eco_NetRad_col`. |
| `plant_morph_type` | `PlantAPIData.F90:216-358` | `plt_morph` | Canopy/branch/root morphology: canopy height, stem area, leaf+stalk area, per-canopy-layer leaf C, per-branch node counts, per-PFT canopy layer depth profile. Large because morphology needs fine-grained (PFT, branch, node, canopy-layer) indexing. |
| `plant_pheno_type` | `PlantAPIData.F90:360-442` | `plt_pheno` | Phenological timers and flags: growing-degree-day accumulators, pre-anthesis / anthesis / grain-fill switches, senescence timing, leaf appearance / node initiation state. |
| `plant_soilchem_type` | `PlantAPIData.F90:444-475` | `plt_soilchem` | **Soil-to-plant interface**: layer-resolved soil conditions the root kernel needs — SOM fraction (`FracBulkSOMC_vr`), bulk density (`SoilBulkDensity_vr`), porosity (`VLSoilPoreMicP_vr`), micropore water/ice (`VLWatMicP_vr`, `VLiceMicP_vr`), gas and solute concentrations (`trc_solcl_vr`, `trcg_gascl_vr`, `trcs_solml_vr`), diffusivities (`GasDifcT_vr`, `SoluteDifusvtyT_vr`), DOM pools (`DOM_MicP_vr`, `DOM_MicP_drib_vr`). Effectively a read-only "soil as seen by roots" snapshot. |
| `plant_allometry_type` | `PlantAPIData.F90:477-524` | `plt_allom` | PFT allometric constants and element ratios: N:C / P:C ratios for root, nodule, leaf, sheath, stalk, grain, ear, husk, reserve (`rNCRoot_pft`, `rPCRoot_pft`, `rNCLeaf_pft`, `rPCGrain_pft`, ...), growth yields (`RootBiomGrosYld_pft`, `LeafBiomGrowthYld_pft`, ...), and litter-allocation fractions (`FracLeafShethElmAlloc2Litr`, `FracRootElmAllocm`, `FracWoodStalkElmAlloc2Litr`). |
| `plant_biom_type` | `PlantAPIData.F90:526-627` | `plt_biom` | Plant biomass pools at per-PFT, per-branch, per-node, per-root-axis, per-layer resolution: `TotBegVegE_pft` / `TotEndVegE_pft`, leaf protein (`LeafProteinC_brch`, `LeafProteinCperm2LA_pft`), standing dead (`StandingDeadStrutElms_col`), root biomass elements (`RootMycoMassElm_pvr(:,:,:,:)`), primary/secondary root structural axes (`RootMyco1stStrutElms_rpvr`, `RootMyco2ndStrutElms_rpvr`, `Root1stActStructElms_rpvr`, `Root1stLigStructElms_rpvr`), canopy-layer leaf C. |
| `plant_ew_type` | `PlantAPIData.F90:629-703` | `plt_ew` | Plant energy-and-water state: leaf/canopy water potentials, turgor pressures, canopy heat storage, heat-flux partitions, atmospheric forcing shards used by the plant canopy (TairK, VPA, wind, snow depth, PRESS). |
| `plant_disturb_type` | `PlantAPIData.F90:705-740` | `plt_distb` | Disturbance state: harvest chemical-element accounting (`EcoHavstElmnt_CumYr_col`), fertilizer application vectors (`FERT(ifert_plant_manuC:...)`), tillage fraction, fire / grazing records. |
| `plant_bgcrate_type` | `PlantAPIData.F90:742-817` | `plt_bgcr` | Plant BGC rate tallies per column: NEE, NPP, autotrophic respiration, net biome productivity cumulator (`Eco_NBP_CumYr_col`, `Eco_AutoR_CumYr_col`), litterfall (`LitrFallStrutElms_col`), ecosystem respiration coefficient (`ECO_ER_col`), canopy gross CO2 fixation. |
| `plant_rootbgc_type` | `PlantAPIData.F90:819-908` | `plt_rbgc` | Root biogeochemistry: root-soil solute uptake vectors (`trcs_Soil2plant_uptake_vr`, `trcs_Soil2plant_uptake_pvr`), per-nutrient demand pairs (band vs non-band) for NH4/NO3/H2PO4/H1PO4, Michaelis-Menten coefficients (`VmaxNH4Root_pft`/`_pvr`, `KmNH4Root_pft`/`_pvr`, `CMinNH4Root_pft`, and same for NO3, H2PO4, H1PO4 — see `PlantAPIData.F90:832-868`), N2 fixation (root + canopy), root-soil CO2 and O2 flux channels (`RCO2Emis2Root_rpvr`, `RootO2Uptk_pvr`, `RootO2Dmnd4Resp_pvr`), root internal gas content (`trcg_rootml_pvr`, `trcs_rootml_pvr`), cytokinin concentrations (`Cytokinin1stConc_rpvr`, `Cytokinin2ndConc_rpvr`), cumulative N/P uptake (`RootUptk_N_CumYr_pft`, `RootUptk_P_CumYr_pft`). |

All twelve declarations end with the same idiom:

```fortran
  contains
    procedure, public :: Init    => plt_<x>_init
    procedure, public :: Destroy => plt_<x>_destroy
  end type <name>
```

(see e.g. `PlantAPIData.F90:91-94` for `plant_siteinfo_type`, `:521-524` for `plant_allometry_type`, `:905-908` for `plant_rootbgc_type`).

## Module-level singleton instances

Declared together at `PlantAPIData.F90:910-921`:

```fortran
type(plant_siteinfo_type) , public, target :: plt_site      ! site info
type(plant_rootbgc_type)  , public, target :: plt_rbgc      ! root bgc
type(plant_bgcrate_type)  , public, target :: plt_bgcr      ! bgc reaction
type(plant_disturb_type)  , public, target :: plt_distb     ! plant disturbance type
type(plant_ew_type)       , public, target :: plt_ew        ! plant energy and water type
type(plant_allometry_type), public, target :: plt_allom     ! plant allometric parameters
type(plant_biom_type)     , public, target :: plt_biom      ! plant biomass variables
type(plant_soilchem_type) , public, target :: plt_soilchem  ! soil bgc interface with plant root
type(plant_pheno_type)    , public, target :: plt_pheno     ! plant phenology
type(plant_morph_type)    , public, target :: plt_morph     ! plant morphology
type(plant_radiation_type), public, target :: plt_rad       ! plant radiation type
type(plant_photosyns_type), public, target :: plt_photo     ! plant photosynthesis type
```

Plant modules in `f90src/Plant_bgc/` `use PlantAPIData` and then reference these singletons directly (e.g. `plt_site%ALT`, `plt_biom%RootMycoMassElm_pvr`, `plt_rbgc%VmaxNH4Root_pvr`). This is the same pattern as the `*DataType` modules' module-level arrays, but scoped to plant data and routed through an explicit `Send`/`Recv` boundary.

## Lifecycle

### `InitPlantAPIData()` (`PlantAPIData.F90:1734-1782`)

1. Associate the 17 public scalar pointers with the corresponding `pltpar%*` fields (`PlantAPIData.F90:1738-1755`). This lets every derived-type `Init` below use symbols like `JZ1`, `JP1`, `NumCanopyLayers1`, `jcplx`, `jsken`, `NumOfPlantLitrCmplxs` in its `allocate` shape arguments without itself knowing about `pltpar`.
2. Call `Init` on each of the twelve singletons in sequence:

   ```fortran
   call plt_site%Init()
   call plt_rbgc%Init()
   call plt_bgcr%Init()
   call plt_pheno%Init()
   call plt_ew%Init()
   call plt_distb%Init()
   call plt_allom%Init()
   call plt_biom%Init()
   call plt_soilchem%Init()
   call plt_rad%Init()
   call plt_photo%Init()
   call plt_morph%Init()
   ```
3. Call the empty placeholder `InitAllocate()` (`PlantAPIData.F90:1784-1788`).

Each `plt_<x>_init(this)` body is a long list of `allocate(this%<field>(...))` calls followed by `this%<field> = spval`, for example `plt_site_Init` at `PlantAPIData.F90:1117-1143` allocates 22 pointer components sized in terms of `JZ1`, `JP1`, `NumPlantChemElms`, `idg_beg:idg_NH3`, and the magic 60 (subcycle count).

Entry point: `InitPlantAPIData` is called from `f90src/Ecosim_mods/InitAllocMod.F90:48` during EcoSIM initialization.

### `DestructPlantAPIData()` (`PlantAPIData.F90:1790-1817`)

Calls `Destroy` on each of the twelve singletons. Many of the per-type destroy bodies are stubs (e.g. `plt_site_destroy` at `PlantAPIData.F90:1145-1151` is empty — deallocation is left to process exit).

Entry point: `DestructPlantAPIData` is called from `f90src/Main/EcoSIMDesctruct.F90:43`.

## How this layer is used in practice

### By the APIs layer (`f90src/APIs/`)

- `PlantAPISend` / `PlantAPIRecv` in `PlantAPI.F90` copy between `Ecosim_datatype/` globals and the twelve `plt_*` singletons. Line counts of those routines (1525 for `Send`, 674 for `Recv`) reflect how many fields are being moved.
- `PlantAPICanMSend` / `PlantAPICanMRecv` in `PlantCanAPI.F90` do the same but only for the subset of `plt_*` fields needed by canopy radiation.
- `PlantUptakeAPISend` / `PlantUPtakeAPIRecv` in `PlantAPI4Uptake.F90` populate the subset needed for prescribed-phenology root uptake.

### By the plant physics kernels (`f90src/Plant_bgc/`)

22 modules `use PlantAPIData` directly (from `grep -rn "use PlantAPIData" f90src/Plant_bgc/`), including `StomatesMod`, `PlantPhenolMod`, `grosubsMod`, `UptakesMod`, `NutUptakeMod`, `RootMod`, `RootGasMod`, `PlantBranchMod`, `PlantBalMod`, `LitterFallMod`, `PlantNonstElmDynMod`, `NoduleBGCMod`, `PhotoSynsMod`, `ExtractsMod`, `SurfaceRadiationMod`, `InitPlantMod`, `PlantMathFuncMod`, `PlantDebugMod`, `PlantDisturbByGrazingMod`, `PlantDisturbByFireMod`, `PlantDisturbByTillageMod`, `PlantDisturbsMod`. These kernels treat the `plt_*` singletons as the authoritative plant-side state for the duration of one column's `PlantModel` iteration.

## Citations

All line numbers verified by `Read` against `/Users/jingtao/Desktop/Work/SourceCode/EcoSIM/EcoSIM/f90src/APIData/PlantAPIData.F90` at commit `2dea74d9`:

- Scalar pointers: `PlantAPIData.F90:14-29`
- `plant_siteinfo_type`: `PlantAPIData.F90:32-94`; `plt_site_Init`: `:1117-1143`
- `plant_photosyns_type`: `PlantAPIData.F90:96-167`
- `plant_radiation_type`: `PlantAPIData.F90:169-214`
- `plant_morph_type`: `PlantAPIData.F90:216-358`
- `plant_pheno_type`: `PlantAPIData.F90:360-442`
- `plant_soilchem_type`: `PlantAPIData.F90:444-475`
- `plant_allometry_type`: `PlantAPIData.F90:477-524`
- `plant_biom_type`: `PlantAPIData.F90:526-627`
- `plant_ew_type`: `PlantAPIData.F90:629-703`
- `plant_disturb_type`: `PlantAPIData.F90:705-740`
- `plant_bgcrate_type`: `PlantAPIData.F90:742-817`
- `plant_rootbgc_type`: `PlantAPIData.F90:819-908`
- Singleton instance declarations: `PlantAPIData.F90:910-921`
- `InitPlantAPIData`: `PlantAPIData.F90:1734-1782`
- `DestructPlantAPIData`: `PlantAPIData.F90:1790-1817`
- Init caller: `f90src/Ecosim_mods/InitAllocMod.F90:48`
- Destruct caller: `f90src/Main/EcoSIMDesctruct.F90:43`
