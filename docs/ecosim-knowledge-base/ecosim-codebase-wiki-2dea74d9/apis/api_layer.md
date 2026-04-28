---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Ecosim_datatype, APIs, APIData}/`
**Last verified:** 2026-04-24
---

# APIs Layer: `f90src/APIs/`

Seven F90 files, built into the `APIs` CMake library (`f90src/APIs/CMakeLists.txt:1-9`). Each module is the thin coupling between `Ecosim_datatype/` globals and a physics kernel.

Dependency-wise (per the CMake `target_include_directories` in `f90src/APIs/CMakeLists.txt`), this library sees `Ecosim_datatype/`, `APIData/`, `Plant_bgc/`, `Microbial_bgc/{Box_Micmodel,Layers_Micmodel}`, `HydroTherm/`, `Disturbances/`, `Balances/`, `Transport/Nonsalt`, `Mesh/`, `Minimath/`, `DebugTools/`, `Modelpars/`, `Modelconfig/`, and `Utils/`. That top-of-stack placement is deliberate: every other layer is a potential dependency, because the API is where everything is stitched together.

---

## 1. `PlantMod.F90` (133 lines)

**Role:** top-level plant driver. Not an API in the "send/recv" sense; this is the module that the outer timestep loop calls to "run the plant model for one hour at one column". It orchestrates the three plant APIs (`PlantAPI`, `PlantCanAPI`, `PlantAPI4Uptake`) plus the plant physics kernels from `f90src/Plant_bgc/`.

**Public subroutines** (`PlantMod.F90:28-29`):

- `PlantModel(yearIJ, NHW, NHE, NVN, NVS)` — per-step driver over columns.
- `PlantCanopyRadsModel(I, J, NY, NX, DepthSurfWatIce)` — separate radiation-only driver.

**Call pattern** (`PlantMod.F90:33-98`):

```fortran
DO NX = NHW, NHE
  DO NY = NVN, NVS
    if (ldo_sp_mode) then
      ! Prescribed phenology path
      call PlantUptakeAPISend(I, J, NY, NX)   ! PlantAPI4Uptake
      CALL ROOTUPTAKES(yearIJ)
      call extracts(I, J)
      call PlantUPtakeAPIRecv(I, J, NY, NX)   ! PlantAPI4Uptake
    else
      ! Full plant model path
      call PlantAPISend(I, J, NY, NX)         ! PlantAPI
      call EnterPlantBalance(...)
      CALL PhenologyUpdate(I, J)              ! f90src/Plant_bgc/PlantPhenolMod
      CALL ROOTUPTAKES(yearIJ)                ! f90src/Plant_bgc/UptakesMod
      CALL GROWPLANTS(yearIJ)                 ! f90src/Plant_bgc/grosubsMod
      CALL EXTRACTs(I, J)                     ! f90src/Plant_bgc/ExtractsMod
      DO NZ = 1, NP_col(NY,NX)
        call ReSeedPlants(I, J, NZ)           ! f90src/Plant_bgc/LitterFallMod
      ENDDO
      call ExitPlantBalance(...)
      call PlantAPIRecv(I, J, NY, NX)         ! PlantAPI
    endif
  ENDDO
ENDDO
```

`PlantCanopyRadsModel` (`PlantMod.F90:118-131`) is a smaller wrapper: `PlantAPICanMSend` → `CanopyConditionModel` (from `SurfaceRadiationMod`, in `Plant_bgc/`) → `PlantAPICanMRecv`. It is called once per hourly step from `f90src/Modelforc/Hour1Mod.F90:201` and from `ATSUtils/ATSEcoSIMAdvanceMod.F90:296` in the ATS-coupled path.

**Callers:** `f90src/ATSUtils/ATSEcoSIMAdvanceMod.F90:343` (`call PlantModel(...)` guarded by `ldo_sp_mode`) and the two call-sites above for `PlantCanopyRadsModel`.

---

## 2. `PlantAPI.F90` (1527 lines)

**Role:** full-plant-model send/recv. By far the largest API module, because it translates the column-level globals in `Ecosim_datatype/` into the ~12 plant-facing derived types (`plt_site`, `plt_morph`, `plt_biom`, `plt_ew`, ...) defined in `APIData/PlantAPIData.F90`.

**Public subroutines** (`PlantAPI.F90:41-42`):

- `PlantAPISend(I, J, NY, NX)` — copy column globals → `plt_*` instances. Defined at `PlantAPI.F90:727-1525`.
- `PlantAPIRecv(I, J, NY, NX)` — copy `plt_*` instances → column globals. Defined at `PlantAPI.F90:48-722`.

**Physics wrapped:** the plant-BGC pipeline in `f90src/Plant_bgc/` (phenology, photosynthesis, nonstructural-element dynamics, root uptake, growth, litterfall, disturbance). All of those kernels `use PlantAPIData` rather than `Ecosim_datatype/*DataType` directly.

**Data pushed (Send, illustrative sample from `PlantAPI.F90:48` backwards read + in-code writes):** snow / canopy / atmospheric forcings (`SnowDepth_col`, `TairK_col`, `VPA_col`), surface fluxes (`RawIsoTAtm2CanopySinkZ_col`, `LWRadSky_col`, `LWRadGrnd_col`), grid altitude (`ALT_col`), surface roughness (`RoughnessLength_col`, `ZeroPlaneDisplacem_col`), column layer indices (`NU_col`, `NL_col`, `NP_col`), and many more. The receive side copies back aggregate state — `plt_site%NumActivePlants → NumActivePlants_col`, `plt_bgcr%Eco_NBP_CumYr_col → Eco_NBP_CumYr_col`, `plt_rad%Eco_NetRad_col → Eco_NetRad_col`, harvest, litterfall, canopy latent/sensible heat, fertilization events, etc. (see `PlantAPI.F90:60-97` for ~40 representative copies).

**Dependencies (`use`):** `PlantAPIData`, plus ~20 `*DataType` modules in `Ecosim_datatype/` (see `PlantAPI.F90:11-35`).

---

## 3. `PlantCanAPI.F90` (242 lines)

**Role:** dedicated send/recv for the canopy-radiation-only sub-driver (`PlantCanopyRadsModel` in `PlantMod`).

**Public subroutines** (`PlantCanAPI.F90:40-41`):

- `PlantAPICanMSend(NY, NX)` — `PlantCanAPI.F90:46-172`. Pushes the minimum set of forcings needed by `CanopyConditionModel`: `KoppenClimZone`, plant count, surface layer index, numerical thresholds (`ZEROS`, `ZERO`), canopy morphology (`StemArea_col`, `CanopyLeafArea_col`), and atmospheric inputs (`SnowDepth_col`, `TairK_col`, ...).
- `PlantAPICanMRecv(NY, NX)` — `PlantCanAPI.F90:176-241`. Pulls back the updated radiation state.

**Physics wrapped:** `CanopyConditionModel` in `f90src/Plant_bgc/SurfaceRadiationMod.F90`.

**Why separate from `PlantAPI`:** it runs at a different timestep cadence (inside the hourly radiation update in `Hour1Mod.F90`), and most of the plant state (`plt_biom`, `plt_bgcr`, ...) does not need to be refreshed. Keeping it small avoids the cost of the full `PlantAPISend`.

---

## 4. `PlantAPI4Uptake.F90` (260 lines)

**Role:** send/recv for the **prescribed-phenology** path. When `ldo_sp_mode=.true.`, EcoSIM bypasses internal phenology and growth, and only runs root uptake plus diagnostic aggregation.

**Public subroutines** (`PlantAPI4Uptake.F90:41-42`):

- `PlantUptakeAPISend(I, J, NY, NX)` — `PlantAPI4Uptake.F90:47-210`. Pushes forcing + prescribed leaf/stalk area (`LeafStalkArea_col`, `CanopyLeafArea_col`) and the minimum column/layer indices (`NU_col`, `NL_col`, `NK_col`, `NP0_col`, `NP_col`) into `plt_site`, plus atmospheric and radiation forcings into `plt_ew` / `plt_rad` / `plt_morph`. Comments in the code (e.g. `PlantAPI4Uptake.F90:58` "set as phenology input") document which fields are driven externally in this mode.
- `PlantUPtakeAPIRecv(I, J, NY, NX)` — `PlantAPI4Uptake.F90:213-258`. Pulls back the uptake-related state only.

**Physics wrapped:** `ROOTUPTAKES` (in `f90src/Plant_bgc/UptakesMod.F90`) and `extracts` (in `f90src/Plant_bgc/ExtractsMod.F90`).

**Why separate from `PlantAPI`:** the prescribed-phenology path reads fewer fields (no phenology-internal state is pushed, no growth state is pulled), so the wrapper is ~6x shorter than `PlantAPISend`/`Recv`. Both share the same `plt_*` containers, so physics code is unchanged.

---

## 5. `MicBGCAPI.F90` (596 lines)

**Role:** per-layer send/recv around the single-layer microbial-BGC kernel. Unlike the plant API, this one does the send/recv inside a layer loop instead of once per column, because microbial state is allocated per soil layer and the kernel operates on one layer at a time.

**Public subroutines** (`MicBGCAPI.F90:48-50`):

- `MicAPI_Init()` — `MicBGCAPI.F90:55-64`. Calls `micfor%Init()`, `micstt%Init()`, `micflx%Init()` on the module-level singletons declared at `MicBGCAPI.F90:40-43`. Called from `f90src/Main/InitEcoSIM.F90:29`.
- `MicAPI_cleanup()` — `MicBGCAPI.F90:66-76`. Matching destructor, called from `f90src/Main/EcoSIMDesctruct.F90:54`.
- `MicrobeModel(I, J, NHW, NHE, NVN, NVS)` — `MicBGCAPI.F90:78-135`. Driver that loops `NX, NY, L`, calls `sumMicBiomLayL` to snapshot biomass, calls `MicBGC1Layer` to advance one layer, re-snapshots, accumulates, then runs layer-mixing (`DownwardMixOM`) and disturbance-driven SOM removal (`SOMRemovalByDisturbance`).

**Internal helper** `MicBGC1Layer(I, J, L, NY, NX)` (`MicBGCAPI.F90:139-152`):

```fortran
micfor%L = L
call MicAPISend(I, J, L, NY, NX, micfor, micstt, micflx)
call SoilBGCOneLayer(I, J, micfor, micstt, micflx, naqfdiag, nmicdiag)
call MicAPIRecv(I, J, L, NY, NX, micfor, micstt, micflx, naqfdiag, nmicdiag)
```

So the classic send → kernel → recv pattern is per-layer here.

**Data pushed (Send):** per-layer forcings into `micfor` — litter-layer flag (`micfor%litrm = (L==0)`), surface flag, `VLWatMicP_vr(0,NY,NX)`, atmospheric gas concentrations (`AtmGasCgperm3_col`), irrigation/rainfall gas concentrations, layer volumes and heat capacities (see `MicBGCAPI.F90:177-200` for the opening set; the full list runs to line 407). Also snapshots microbial state into `micstt` and fluxes into `micflx`.

**Physics wrapped:** `SoilBGCOneLayer` in `f90src/Microbial_bgc/Box_Micmodel/MicBGCMod.F90`.

**Callers:** `MicAPI_Init` and `MicAPI_cleanup` are wired in (see above). `MicrobeModel` itself has no in-tree caller on this pin (verified via `grep -rn "call MicrobeModel" f90src/`). The subsystem is built and initialized, but the scenario driver does not yet call it on 2dea74d9.

---

## 6. `GeochemAPI.F90` (371 lines)

**Role:** per-layer send/recv around the solute/geochemistry equilibrium solver. Same pattern as `MicBGCAPI` but for aqueous chemistry.

**Public subroutines** (`GeochemAPI.F90:19`):

- `soluteModel(I, J, NHW, NHE, NVN, NVS)` — `GeochemAPI.F90:23-150`. Zeros a local `chem_var_type` record (`GeochemAPI.F90:40-91`, ~50 fields from `ZMG`, `ZNA`, ..., through `ZCA2PB`, `ZMG1PB`), then loops over `NX, NY, L` and calls the solute solver for each active layer.

**Internal helpers:**

- `GeochemAPISend(L, NY, NX, chemvar, solflx)` — `GeochemAPI.F90:154-256`. Copies `trcx_solml_vr`, `PH_vr`, `CAL_vr`, `CFE_vr`, `VLWatMicPM_vr`, and (if `salt_model` is on) the full `trcSalt_solml_vr(idsalt_*, L, NY, NX)` set into `chemvar`.
- `GeochemAPIRecv(L, NY, NX, solflx)` — `GeochemAPI.F90:260-369`. Copies the solve results back out.

**Physics wrapped:** `SoluteMod` in `f90src/Geochem/` (called from within `soluteModel`, along with `UpdateFertilizerBand` and `UpdateSurfResidueSolute`).

**Dependencies (`use`):** `SoluteChemDataType` (`solute_flx_type`, `chem_var_type`), `AqueChemDatatype`, `SoilBGCDataType`, `SOMDataType`, `SoilPropertyDataType`, `SoilWaterDataType`, `GridDataType`, plus `SoluteMod`.

**Callers:** none in-tree on this pin (same status as `MicrobeModel`). `public :: soluteModel` is declared but not called yet; the subsystem compiles and is ready for integration into the driver.

---

## 7. `SurfPhysAPI.F90` (13 lines)

**Role:** placeholder. Full module body:

```fortran
module SurfPhysAPI
  use data_kind_mod, only : r8 => DAT_KIND_R8
  implicit none
  private
  character(len=*), parameter :: mod_filename = __FILE__
contains
end module SurfPhysAPI
```

No public subroutines, no types. Included in the `APIs` CMake library (`CMakeLists.txt:7`) so the build target exists, but it is a stub that anticipates a future surface-physics send/recv counterpart to `MicBGCAPI` and `GeochemAPI`. Worth noting in this doc because its empty state is a reliable signal that the "surface energy / water" physics is **not** yet routed through an API boundary — those modules still `use` the `*DataType` globals directly in the current codebase.

---

## Summary: the three send/recv patterns

| Pattern | Used by | Granularity | Why |
|---|---|---|---|
| Column-level single-shot | `PlantAPI`, `PlantCanAPI`, `PlantAPI4Uptake` | One send / one recv per column, per step | Plant state is column-scoped (PFT, branch, node arrays) and persists across layers. One copy round-trip amortizes the cost over the whole plant kernel. |
| Layer-level, argument-passed | `MicBGCAPI` (`MicAPISend`/`Recv` take `micfor/micstt/micflx` as args), `GeochemAPI` (same, with `chemvar/solflx`) | One send / kernel / recv per soil layer, inside a layer loop | Microbial and solute kernels operate on one layer at a time; passing the scratch structs explicitly makes the per-layer data flow visible and avoids stale module-level state. |
| Driver-only | `PlantMod` | No send/recv; orchestrates the other APIs | `PlantMod` is a composition layer, not a data-translation layer. |
