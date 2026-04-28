---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** core orchestration: `f90src/{Main, Ecosim_mods, Modelconfig, Modelpars, Mesh, Utils, Minimath, DebugTools}/`
**Last verified:** 2026-04-24
---

# Main Orchestration: Startup, Year Initialization, Shutdown

This doc covers the two modules in `f90src/Main/` and the four modules in `f90src/Ecosim_mods/`. Together they own the full initialization and shutdown path for an EcoSIM run: one-shot memory allocation, grid/tracer setup, then per-year reinitialization of soil state (`starts`), plant state (`startq`), and chemistry state (`starte`), and finally orderly deallocation of every state store.

None of these routines implement biogeochemistry. They allocate and wire the subsystems that do.

## 1. `f90src/Main/InitEcoSIM.F90` — `InitModules()`

Module `InitEcoSIM` declares a single public entry, `InitModules()` (f90src/Main/InitEcoSIM.F90:12, body at :15-59). The driver calls it exactly once per run, immediately after `SetMesh` has populated `bounds`, `JX`, `JY`, `JZ`, etc.

`InitModules()` executes 11 calls in fixed order (f90src/Main/InitEcoSIM.F90:34-57):

| # | Call | Target module | Purpose |
|---|---|---|---|
| 1 | `InitAlloc()` | `Ecosim_mods/InitAllocMod.F90` | Allocate every state data type (see section 3 below) |
| 2 | `ReadPlantTraitTable()` | `Plant_bgc/PlantInfoMod.F90` | Read PFT trait file — only when `plant_model .and. .not. ats_cpl_mode` (f90src/Main/InitEcoSIM.F90:37) |
| 3 | `units%Initailize()` | `Utils/UnitMod.F90` | Populate the `units` unit-conversion singleton |
| 4 | `InitPlantDisturbance` | `Disturbances/PlantDisturbsMod` | Fire/harvest disturbance state |
| 5 | `InitUptake` | `Plant_bgc/UptakesMod` | Root uptake working arrays |
| 6 | `initNitro` | `Microbial_bgc/SoilBGCNLayMod` | Nitrogen cycling working arrays |
| 7 | `InitRedist` | `Transport/RedistMod` | Redistribution fluxes |
| 8 | `InitErosion` | `Disturbances/ErosionMod` | Sediment/erosion state |
| 9 | `InitHour1(micpar%NumOfLitrCmplxs)` | `Modelforc/Hour1Mod.F90:73` | Hourly driver state; passes number of litter-microbial complexes |
| 10 | `InitTranspNoSalt` | `Transport/TranspNoSaltMod` | No-salt transport working arrays |
| 11 | `hist_ecosim%Init(bounds)` | `IOutils/HistDataType` | History-output buffers |
| 12 | `MicAPI_Init` | `APIs/MicBGCAPI` | Microbial BGC API state |

Ordering notes: `InitAlloc` must come first because every later Init* expects the data types it covers to already be allocated. `ReadPlantTraitTable` depends on `plant_model` and `ats_cpl_mode` from `EcoSIMCtrlMod`. The `micpar%NumOfLitrCmplxs` value passed to `InitHour1` is set inside `InitAlloc → InitSOMBGC` earlier in this same routine (transitively through `InitAllocMod`).

## 2. `f90src/Main/EcoSIMDesctruct.F90` — `DestructEcoSIM`

Note: the filename intentionally reads `EcoSIMDesctruct.F90` (typo preserved). Module name: `EcoSIMDesctruct`; public entry: `DestructEcoSIM` (f90src/Main/EcoSIMDesctruct.F90:7, body at :10-136).

It is called exactly once at the end of `drivers/ecosim/ecosim.F90:156`. It executes ~35 `Destruct*` calls covering every subsystem allocated during `InitModules`. The order is not reverse-of-allocation in general, but follows a rough "consumers before providers" pattern — e.g., `DestructMicrobialData` before `DestructSOMData`, since the microbial data types reference litter/SOM complex counts set up in SOM init.

Notable teardown entries (f90src/Main/EcoSIMDesctruct.F90:57-135):

- `MicAPI_cleanup` (first, line 57) mirrors `MicAPI_Init` last in `InitModules`.
- Plant API data (`DestructPlantAPIData`, line 77), plant management (`DestructPlantMngmtData`, line 79), plant rates (`DestructPlantRates`, line 81).
- Transport: `DestructTranspNoSalt` is gated by `if(.not.salt_model)` (line 89-91) — matches the allocation in `InitAlloc`.
- `CleanUpTracerIDs` (line 135, `use TracerIDMod`) deallocates `trcs_names` and `tracerSolc_max`.

If a new state type is added to the model, its matching `Destruct*` must be appended here — failing to do so will leak memory on model exit (harmless for short runs, but noticeable for coupled/test harnesses that repeatedly init and destruct).

## 3. `f90src/Ecosim_mods/InitAllocMod.F90` — `InitAlloc()`

Module `InitAllocMod` has two public routines: `InitAlloc` and the helper `InitPlantMorphSize` (f90src/Ecosim_mods/InitAllocMod.F90:9, body at :11-150 and :152-187).

`InitAlloc()` performs the one-time memory allocation for every `*DataType` / `*Mod` that stores persistent state. It is invoked from `InitModules()` (see section 1) and must precede every other init. The sequence (f90src/Ecosim_mods/InitAllocMod.F90:65-148) is:

```
InitSOMBGC                       ! soil-organic-matter scaffolding (drives micpar sizing)
InitPlantMorphSize               ! copy PFT morph sizes from GridConsts into pltpar
if (plant_model) InitPlantTraitTable(pltpar, NumGrowthStages, MaxNumRootAxes)
InitGridData                     ! per-layer and per-column grid arrays
InitTracerIDs(salt_model)        ! populate idg_*, ids_*, idsalt_*, idsp_*, idx_* integer indices
InitLandSurfData
InitEcoSIMCtrlData
InitCanopyData / InitCanopyRad
InitAquaChem
InitPlantMngmtData
InitPlantRates(micpar%NumOfPlantLitrCmplxs, pltpar%jroots)
InitSoilProperty / InitWatsub / InitSurfLitter(micpar%NumOfLitrCmplxs)
InitSedimentData / InitSoilWater / InitIrrigation
InitPlantAPIData
InitMicrobialData
InitChemTranspData(salt_model)
InitSoilBGCData(pltpar%NumOfPlantLitrCmplxs)
InitSOMData(micpar%NumOfLitrCmplxs)
InitFertilizerData
InitPlantTraits(pltpar%NumOfPlantLitrCmplxs)
InitFlagData / InitEcoSimSum / InitRootData(2) / InitClimForcData
InitEcosimBGCFluxData / InitSnowData / InitEcoSIMHistData
InitSoilHeatData / InitSurfSoilData / InitHydroThermData
InitSnowPhysData / InitSoilPhysData
InitNumericAux
if (salt_model) InitSoluteProperty
InitSoilWarming
InitBalanceCheckData
```

Two side-effects are easy to miss:

- `InitSOMBGC` (called first) is what populates `micpar` (the `MicParType` singleton from `Modelpars/EcoSiMParDataMod.F90`) with counts like `NumOfLitrCmplxs`, `NumOfPlantLitrCmplxs`, `k_woody_comp`, `k_fine_comp`, `k_manure`, `k_POM`, `k_humus`. Downstream calls consume these values.
- `InitPlantMorphSize()` (f90src/Ecosim_mods/InitAllocMod.F90:152-187) copies fixed-size plant morphology counts (`JZ`, `NumCanopyLayers`, `JP`, `NumOfLeafAzimuthSectors`, `NumOfSkyAzimuthSects`, `NumLeafZenithSectors`, `MaxNodesPerBranch`, `MaxNumBranches`, `MaxNumRootAxes`, `NumGrowthStages`, `NumOfPlantMorphUnits`, `NMaxRootSegs`, `NumLitterGroups=5`) from `GridConsts` module-level constants into `pltpar`, and also copies kinetic-component indices (`iprotein`, `icarbhyro`, `icellulos`, `ilignin`, `k_woody_comp`, `k_fine_comp`) from `micpar` into `pltpar` (:164-173). This mirroring lets plant code use `pltpar` as a one-stop shop without reaching into `micpar`.

## 4. `f90src/Ecosim_mods/StartsMod.F90` — Per-year soil init (`starts`, `startsim`, `set_ecosim_solver`)

`StartsMod` exports three public routines (f90src/Ecosim_mods/StartsMod.F90:66-68):

### `starts(NHW, NHE, NVN, NVS)` — line 71

Called from `AdvanceModelOneYear` at `drivers/ecosim/EcoSIMAPI.F90:383` on the first time step of the simulation (condition `ymdhs(1:4)==frectyp%ymdhs0(1:4)`). Initializes all soil state variables: layer counts, bulk densities, porosity, water content, temperature, and related derived quantities for each `(NY,NX)` column.

Key private helpers inside `starts` (found by grep at :71-979):

- `InitSoilVars(NHW,NHE,NVN,NVS,ALTZG,LandScape1stSoiLayDepth)` — :223
- `InitSoilProfile(NY,NX,LandScape1stSoiLayDepth)` — :334
- `initFertArrays(NY,NX)` — :549
- `InitGridElevation(NHW,NHE,NVN,NVS,YSIN,YCOS,SkyAzimuthAngle,ALTY)` — :601
- `InitControlParms` — :730
- `InitAccumulators()` — :779
- `InitHGrid(NY,NX)` — :866
- `InitLayerDepths(NY,NX)` — :882

### `set_ecosim_solver(NPXS1, NPYS1, NCYC_LITR, NCYC_SNOW)` — line 978

Called from the driver at `drivers/ecosim/ecosim.F90:125` once per forcing period (inside the `NN1` loop). It sets the sub-cycle counts in `Modelconfig/EcoSIMSolverPar.F90` (see `model_config.md`). This is how a user dials up/down the within-hour iteration count for different forcing resolutions.

### `startsim(NHW, NHE, NVN, NVS)` — line 1012

An aggregate convenience wrapper (body at :1012-?). It invokes `ComputeSoilHydroPars` and `SetDeepSoil` over every column, then calls `InitControlParms`, `InitIrradianceGeometry`, `InitGridElevation`, `InitAccumulators`, and sets the initial `ATKS_col=242.0` (f90src/Ecosim_mods/StartsMod.F90:1026-1046). It is used by the ATS-coupled driver (`drivers/ATSEcoSIM/...` → `ATSUtils/ATSEcoSIMInitMod.F90:147`) to stand in for the combined `SetMesh`+`starts` path when mesh info comes from ATS.

## 5. `f90src/Ecosim_mods/StartqMod.F90` — Per-year plant init (`startq`)

Module `StartqMod`; single public entry `startq(NHWQ, NHEQ, NVNQ, NVSQ, NZ1Q, NZ2Q)` (f90src/Ecosim_mods/StartqMod.F90:30, body at :33-end).

Called from `AdvanceModelOneYear` at `drivers/ecosim/EcoSIMAPI.F90:399` whenever a new year begins and `plant_model` is true. The two extra arguments `NZ1Q,NZ2Q` select a PFT index range; the driver passes `1, JP` (all PFTs). For each `(NX, NY, NZ)` the routine initializes: shoot growth variables (`IsPlantActive_pft`, `iYearPlanting_pft`, `PPI`, `PPX`, clumping factor `CF`, `ClumpFactorInit_pft`), cuticular resistances (`H2OCuticleResist_pft`, `CO2CuticleResist_pft`), N:C and P:C ratios (`CNWS`, `rProteinC2LeafP_pft`, `RootProteinCMax_pft`), and C3/C4 intercellular O2 (`O2I`) (f90src/Ecosim_mods/StartqMod.F90:46-60).

Many plant modules (e.g., `Plant_bgc/PlantBranchMod.F90`, `PhotoSynsMod.F90`, `RootMod.F90`) retain comments referencing "from startq.f" for the variables they consume — a useful backward-search term.

## 6. `f90src/Ecosim_mods/StarteMod.F90` — Per-year chemistry init (`starte`)

Module `StarteMod`; single public entry `starte(NHW, NHE, NVN, NVS)` (f90src/Ecosim_mods/StarteMod.F90:36, body at :39-end).

Called from `AdvanceModelOneYear` at `drivers/ecosim/EcoSIMAPI.F90:408` whenever a new year begins and `soichem_model` is true. It initializes cation and anion concentrations in three "K" contexts — K=1 precipitation, K=2 irrigation, K=3 soil (f90src/Ecosim_mods/StarteMod.F90:56-58). Per column, it sets gas concentrations (`CCO2M`, `CCH4M`, `COXYM`, `CZ2GM`, `CZ2OM`) from the atmospheric-gas column arrays divided by the appropriate atomic weight (f90src/Ecosim_mods/StarteMod.F90:63-67), reads ambient `ATCA`, then iterates over 366 days × soil layers × litter/manure/POM complexes (`K=micpar%k_fine_comp,micpar%k_POM`) and sets nutrient concentrations for irrigation (`CN4Z`, `CNOZ`, `CPOZ` and, under `salt_model`, 8 salt ions) and rain-water chemistry via `PHQ(I,NY,NX)` (f90src/Ecosim_mods/StarteMod.F90:71-100).

The doc header notes (f90src/Ecosim_mods/StarteMod.F90:41-46): the top soil layer is re-initialized every year so that year-varying boundary conditions (irrigation, rainfall, manure application) take effect; deeper layers are initialized only in the first year.

## 7. Overall call sequence (compressed)

```
drivers/ecosim/ecosim.F90 : main
  SetMesh                   ── establish landscape rectangle (Mesh/GridMod.F90)
  InitModules               ── Main/InitEcoSIM.F90
    InitAlloc               ── Ecosim_mods/InitAllocMod.F90 (25+ Init* calls)
    (+10 more subsystem Init calls)
  per forcing period:
    set_ecosim_solver       ── Ecosim_mods/StartsMod.F90
    per year:
      AdvanceModelOneYear   ── drivers/ecosim/EcoSIMAPI.F90
        STARTS                ── year boundary (soil init)
        STARTQ                ── year boundary + plant_model (plant init)
        STARTE                ── year boundary + soichem_model (chemistry init)
        per day, per hour:    DAY, SetAnnualAccumlators, HOUR1, ...
  DestructEcoSIM            ── Main/EcoSIMDesctruct.F90 (~35 Destruct* calls)
```
