---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Plant_bgc, Prescribed_pheno}/`
**Last verified:** 2026-04-24
---

# Plant Biogeochemistry Subsystem

This subsystem handles all living-plant processes in EcoSIM: phenology, photosynthesis,
stomatal conductance, carbon/nutrient allocation, branch/leaf/stalk/root growth,
respiration (maintenance + growth), nutrient and O2 uptake, nodule (N-fixing) biochemistry,
gas exchange through roots, senescence, litterfall, and mechanical disturbance (fire,
grazing, tillage, harvest). The alternative "prescribed phenology" mode bypasses dynamic
phenology and uses externally supplied LAI/SAI and root profiles instead.

All dynamic plant state lives in the `plt_*` derived types (`plt_pheno`, `plt_morph`,
`plt_biom`, `plt_photo`, `plt_rad`, `plt_ew`, `plt_rbgc`, `plt_bgcr`, `plt_allom`,
`plt_distb`, `plt_site`) declared under `f90src/Ecosim_datatype/` and exposed through
`PlantAPIData` (see `data_types/index.md`). Most routines in this subsystem read state via
Fortran `associate(...)` blocks that alias these components.

## 1. Source-file inventory

### `f90src/Plant_bgc/` (24 files)

| File | Public entities | Purpose |
|---|---|---|
| `ExtractsMod.F90` | `extracts` | Aggregates soil-plant C/N/P exchanges from `UPTAKE` and `GROSUB` and dispatches them to the redistribution layer (`f90src/Plant_bgc/ExtractsMod.F90:1-24`). |
| `GrosubsMod.F90` | `GrowPlants` | Top-level "do all plant biological transformations" routine: stages growth, calls per-plant/per-branch/root routines, reallocates reserves, accumulates state, moves live-to-dead (`GrosubsMod.F90:51-109`). |
| `InitPlantMod.F90` | `StartPlants`, `InitPlantPhenoMorphoBio`, `InitRootMychorMorphoBio` | First-time allocation of plant state on planting or (re)seeding. Zeros morphology, phenology, and root/mycorrhiza arrays. |
| `InitVegBGC.F90` | `InitIrradianceGeometry` | Pre-computes solar-geometry tables (sky azimuth/zenith sines and cosines) used by canopy radiation at runtime. |
| `LitterFallMod.F90` | `ResetDeadPlant`, `ReSeedPlants`, `SetDeadPlant` | Manages the transition of plant organs to litter pools, dead-plant reset between seasons, and re-emergence of annuals from seed (`LitterFallMod.F90:18-48`). |
| `NoduleBGCMod.F90` | `CanopyNoduleBiochemistry`, `RootNodulBiochemistry` | N2 fixation and nodule C/N/P dynamics, called from canopy (canopy-residing nodules on bryophytes/lichens etc.) and from roots (`NoduleBGCMod.F90:20, 416`). |
| `NutUptakeMod.F90` | `PlantNutientO2Uptake`, `ZeroNutrientUptake` | Nutrient (NH4, NO3, H2PO4, solutes) and O2 uptake kinetics at the root-soil interface. Uses the `SoluteUptakeByPlantRoots` machinery from `PlantMathFuncMod.F90`. |
| `PhotoSynsMod.F90` | `ComputeGPP` | Canopy gross primary production. Dispatches each active node to C3 or C4 photosynthesis and sums CO2 fixation and carbohydrate production (`PhotoSynsMod.F90:12, 437-552`). |
| `PlantBalMod.F90` | `SumPlantBiome`, `SumPlantBiomStates`, `SumRootBiome`, `SumPlantBranchBiome`, `EnterPlantBalance`, `ExitPlantBalance`, `SumPlantRootGas`, `SumRootAR`, `CheckPlantBalanceZ`, `SumLitfallBlg`, `SumCanopyBiome`, `SumLitfallAbg` | Mass-balance machinery for the plant subsystem: total biome element inventory, enter/exit balance brackets per-timestep, litterfall accounting, and the diagnostic `CheckPlantBalanceZ` used during debugging. |
| `PlantBranchMod.F90` | `GrowOneBranch` | The arithmetic heart of the plant submodel. 4,096 lines. Allocates non-structural C/N/P across branch morphological units (leaf, petiole-sheath, stalk, reserve, husk, ear, grain), performs growth and maintenance respiration, remobilization/senescence, grain filling, and calls photosynthesis. Houses 22 internal subroutines (`PlantBranchMod.F90:22, 35`). |
| `PlantDebugMod.F90` | `PrintRootTracer` | Debug-print helper for root tracer state. |
| `PlantDisturbByFireMod.F90` | `StageRootRemovalByFire`, `RemoveRootByFire`, `AbvGrndLiterFallByFire`, `AbvgBiomRemovalByFire`, `ApplyBiomRemovalByFire`, `InitPlantFireMod` | Fire-specific disturbance: above-ground loss, root removal, fire-induced litter fall (`PlantDisturbByFireMod.F90:14-19`). |
| `PlantDisturbByGrazingMod.F90` | `AbvgBiomRemovalByGrazing`, `RemoveStandDeadByGrazing`, `ApplyBiomRemovalByGrazing`, `CutBranchNonstalByGrazing`, `GrazingPlant` | Grazer removal: splits removal among leaves, standing-dead, and petiole-sheath; preserves non-structural carbon for regrowth. |
| `PlantDisturbByTillageMod.F90` | `RemoveBiomByTillage` | Mechanical tillage effects on roots and residues. |
| `PlantDisturbsMod.F90` | `RemoveBiomassByDisturbance`, `InitPlantDisturbance`, `StageDisturbances` | Dispatch layer for mechanical disturbances (harvest, thinning, tillage, fire, grazing, herbivory). Coordinates the `*Removal`/`*Litr` accumulators and calls disturbance-specific modules (`PlantDisturbsMod.F90:40-42`). |
| `PlantMathFuncMod.F90` | `calc_plant_maint_tempf`, `calc_leave_grow_tempf`, `fRespWatSens`, `SoluteUptakeByPlantRoots`, `get_FDM`, misc. helpers | Temperature functions (Arrhenius with high/low-T inactivation), turgor-sensitivity functions, and the canonical Michaelis-Menten solute-uptake helper shared across nutrient and gas uptake. Declares `PlantSoluteUptakeConfig_type`. |
| `PlantNonstElmDynMod.F90` | `PlantNonstElmTransfer`, `SeasonStoreShootTransfer`, `StalkRsrvShootNonstTransfer`, `StalkRsrvRootNonstTransfer`, `RepleteLowSeaStorByRoot`, `RepleteSeaStoreByStalk` | Non-structural C/N/P transfer pathways between pools (leaf-petiole, stalk reserve, seasonal storage, root). Implements the reserve buffer logic that separates slow seasonal storage from fast in-branch reserve. |
| `PlantPhenolMod.F90` | `PhenologyUpdate` | Top-level phenology driver. Classifies each branch as evergreen, cold-deciduous, drought-deciduous, or cold+drought, advances day-length/heat-sum accumulators, and sets `iPlantCalendar_brch` stages (Emerge, InitFloral, Jointing, Elongation, Heading, Anthesis, SeedFill, etc.) (`PlantPhenolMod.F90:36-91`). |
| `RootGasMod.F90` | `RootSoilGasExchange` | Physical/biochemical gas exchange between root interior and soil solution for O2, CO2, CH4, and other tracer gases. O2 and CO2 are biochemically active; others undergo pure physical partitioning. |
| `RootMod.F90` | `RootBGCModel` | Root biogeochemistry driver. Grows primary and secondary root axes (including mycorrhizal axes when `Myco_pft>0`), applies the root cytokinin feedback, manages primary-root remobilization, and calls nodule biochemistry. 3,853 lines. |
| `StomatesMod.F90` | `StomatalDynamics`, `PhotosynsDiag` | Pre-photosynthesis diagnostic (Vcmax25/Vomax25/Jmax25 from leaf protein/chl/Rubisco pools) and the stomatal-resistance solver. Houses the C3 and C4 per-leaf Farquhar-type carboxylation kernels. |
| `SurfaceRadiationMod.F90` | `CanopyConditionModel` | Canopy-layer discretization, leaf/stem area distribution by zenith sector, direct/diffuse short-wave and PAR radiation transfer, and boundary-layer properties (`SurfaceRadiationMod.F90:31-56`). |
| `UptakePars.F90` | parameters only | Tunables used by root water/nutrient uptake (convergence tolerances, min PFT fraction, boundary-layer resistances, wood modulus, N/P inhibition constants, exudation rate constants). |
| `UptakesMod.F90` | `RootUptakes`, `InitUptake` | Top-level canopy-to-atmosphere and root-to-soil exchange driver. Calls `PhotosynsDiag` + `StomatalDynamics`, updates canopy water balance, solves root water and nutrient uptake, and invokes `PlantNutientO2Uptake` and `RootSoilGasExchange`. |

### `f90src/Prescribed_pheno/` (1 file)

| File | Public entities | Purpose |
|---|---|---|
| `PrescribePhenolMod.F90` | `GetRootProfile`, `SetCanopyProfile`, `PrescribePhenologyInterp` | Used when `ldo_sp_mode=.true.`. Interpolates monthly LAI and SAI to the current day (`PrescribePhenolMod.F90:196-313`), distributes leaf/stem area uniformly through canopy layers and zenith sectors, and installs a CLM-style beta-function root profile by biome type (`PrescribePhenolMod.F90:315-363`, beta and fine-root totals from Jackson et al. 1997). Overrides everything that `PlantPhenolMod`, `RootBGCModel`, and `GrosubsMod` would otherwise compute. |

## 2. Top-level call flow

The plant subsystem is driven from `f90src/APIs/PlantMod.F90`. Two paths exist:

### Dynamic mode (`ldo_sp_mode=.false.`)

```
PlantModel                                      (APIs/PlantMod.F90:32)
  PrepLandscapeGrazing                          (Disturbances)
  DO NX, NY:
    PlantAPISend                                (APIs/PlantAPI.F90:48)     ! copy col -> plt_*
    EnterPlantBalance                           (PlantBalMod)              ! open mass-balance bracket
    PhenologyUpdate                             (PlantPhenolMod.F90:36)    ! stages, leafout/leafoff accumulators
    ROOTUPTAKES                                 (UptakesMod.F90:41)        ! canopy stomata + root uptake
      PhotosynsDiag                             (StomatesMod.F90:23)       ! Vcmax25/Jmax25 from protein pools
      StomatalDynamics                          (StomatesMod.F90:194)      ! min stomatal R + canopy Ci
      ... root water + nutrient uptake + root gas exchange
    GROWPLANTS                                  (GrosubsMod.F90:51)        ! actual growth
      DO NZ (active PFTs):
        GrowOnePlant                            (GrosubsMod.F90:238)
          StagePlantForGrowth                   (GrosubsMod.F90:309)       ! wood fractions, T fns, turgor fns
          DO NB (branches):
            GrowOneBranch                       (PlantBranchMod.F90:35)
              CalcPartitionCoeff                (PlantBranchMod.F90:538)   ! growth-stage partitioning
              ComputeGPP                        (PhotoSynsMod.F90:437)     ! node-level C3/C4 GPP
              ComputRAutoAfEmergence /          (PlantBranchMod.F90:3047,
              ComputRAutoB4Emergence             3243)                     ! maintenance + growth resp
              BranchBiomAllocate                (PlantBranchMod.F90:313)   ! C/N/P to organs
              UpdateBranchAllometry             (PlantBranchMod.F90:422)
              GrowLeavesOnBranch                (PlantBranchMod.F90:3446)
              GrowPetolShethOnBranch            (PlantBranchMod.F90:3531)
              GrowStalkOnBranch                 (PlantBranchMod.F90:3615)
              AllocateLeaf2CanopyLayers         (PlantBranchMod.F90:1672)
              RemobilizeLeafLayers              (PlantBranchMod.F90:1311)
              SenescenceBranch                  (PlantBranchMod.F90:3878)
              GrainFillOnBranch                 (PlantBranchMod.F90:2042)
              CanopyNoduleBiochemistry          (NoduleBGCMod.F90:20)      ! for N-fixing canopy nodules
          RootBGCModel                          (RootMod.F90:24)           ! per-plant root growth
            RootBiochemistry                    (RootMod.F90:143)
            GrowRootMycoAxes / Grow1stRootAxes /
            Grow2ndRootAxes / SecondaryGrowthZone
            CytoKininDynamics                   (RootMod.F90:2957)
            RootNodulBiochemistry               (NoduleBGCMod.F90:416)
          PlantNonstElmTransfer                 (PlantNonstElmDynMod)
        RemoveBiomassByDisturbance              (PlantDisturbsMod.F90:261)
        ResetDeadPlant                          (LitterFallMod.F90:18)
      LiveDeadTransformation                    (GrosubsMod.F90:112)
    EXTRACTs                                    (ExtractsMod.F90)          ! aggregate C/N/P exchanges
    DO NZ: ReSeedPlants                          (LitterFallMod.F90)        ! annuals germinate
    ExitPlantBalance                            (PlantBalMod)              ! close mass-balance bracket
    PlantAPIRecv                                (APIs/PlantAPI.F90:727)    ! copy plt_* -> col
```

Canopy radiation/geometry runs separately through `PlantCanopyRadsModel`
(`APIs/PlantMod.F90:119-134`), which wraps `CanopyConditionModel`
(`SurfaceRadiationMod.F90:31`). It is invoked at a different stage of the main-loop
(typically hourly after solar-zenith updates) rather than inside `PlantModel`.

### Prescribed-phenology mode (`ldo_sp_mode=.true.`)

```
PlantModel:
  PlantUptakeAPISend
  ROOTUPTAKES            ! same as above; upstream LAI/SAI come from PrescribePhenologyInterp
  extracts
  PlantUPtakeAPIRecv

PlantCanopyRadsModel:
  CanopyConditionModel
    SetCanopyProfile     ! PrescribePhenolMod.F90:132 -- uses prescribed LAI/SAI
    SurfaceRadiation
```

In SP mode the dynamic-phenology module, `GrowPlants`, live-dead transformation, and
balance bracketing are all skipped. `PrescribePhenologyInterp`
(`PrescribePhenolMod.F90:196`) is responsible for writing `tlai_day_pft`,
`tsai_day_pft`, `CanopyHeight_pft`, and the beta-profile root pools upstream.

## 3. Three-tier phenology / morphology hierarchy

EcoSIM organizes each PFT as:

```
PFT (NZ)                                      indexed 1..NP
 ├── branches (NB=1..NumOfBranches_pft)       one main + lateral branches per PFT
 │    ├── morph units (ibrch_leaf, ibrch_petole, ibrch_stalk,
 │    │                ibrch_resrv, ibrch_husk, ibrch_ear, ibrch_grain)
 │    └── nodes (K=1..MaxNodesPerBranch1)     each node carries its own leaf+petiole
 └── roots
      ├── primary axes (1..NumAxesPerPrimRoot_pft)
      └── secondary axes, each layered vertically over soil layers L
           and split into plant roots (N=ipltroot) and mycorrhizae (N=2) if Myco_pft>0
```

Morph-unit identifiers `ibrch_*`, phenology-calendar identifiers `ipltcal_*`, phenology
type `iphenotyp_*`, photosynthesis type `ic3_photo`/`ic4_photo`, and growth-habit type
`iplt_annual`/`iplt_perennial`/`iplt_bryophyte`/`iplt_grasslike`/`iplt_treelike` are all
declared in `f90src/Modelconfig/ElmIDMod.F90:40-170`.

## 4. State and flux types

All persistent state accessed by these modules is defined in
`f90src/Ecosim_datatype/` and re-exported through `PlantAPIData`
(`f90src/APIData/PlantAPIData.F90`). The pointer-alias convention is:

| Alias | Data type | Contents |
|---|---|---|
| `plt_pheno` | `PlantTraitDataType` | Phenology state, calendar, growth-stage flags, temperature offsets |
| `plt_morph` | `PlantTraitDataType` | Morphology: leaf/stem/node counts, canopy and root geometry |
| `plt_biom` | `PlantTraitDataType` | Biomass (element-resolved) for canopy/root/branch pools |
| `plt_photo` | `CanopyRadDataType`/`PlantTraitDataType` | Photosynthesis parameters and per-leaf pools |
| `plt_rad` | `CanopyRadDataType` | Radiation: PAR, transmittance, layer/sector geometry |
| `plt_ew` | `CanopyDataType` | Energy/water: canopy temperature, water potential, turgor |
| `plt_rbgc` / `plt_bgcr` | `PlantDataRateType` | Plant-BGC rates and accumulators (respiration, fixation, exudation) |
| `plt_allom` | `PlantTraitDataType` | Allometric parameters (rNC, rPC, growth yields) |
| `plt_distb` | `PlantMgmtDataType` | Disturbance/management state |
| `plt_site` | `PlantMgmtDataType` | Site/grid-level totals (NP, population, landscape stores) |
| `plt_soilchem` | `SoilBGCDataType` | Linkage to soil-BGC litter complexes |

See `data_types/index.md` for the per-component field catalog.

## 5. Sub-docs

- [`growth_and_allocation.md`](growth_and_allocation.md) — carbon and N/P allocation to
  branch morph units and to roots; wood vs. non-wood partitioning; size-structured
  growth of leaves/stalk/reserves/grain.
- [`phenology.md`](phenology.md) — evergreen/deciduous/drought-deciduous phenology,
  day-length and heat-sum accumulators, growth-stage calendar, disturbance, and
  prescribed-phenology mode.
- [`photosynthesis_and_respiration.md`](photosynthesis_and_respiration.md) — Grant-1989
  Farquhar-type C3 and C4 photosynthesis, stomatal conductance solved by Ci-diffusion
  iteration, canopy maintenance and growth respiration.
