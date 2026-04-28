---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/{Ecosim_datatype, APIs, APIData}/`
**Last verified:** 2026-04-24
---

# APIs Subsystem

## What this subsystem is

EcoSIM separates its physics kernels (plant BGC, microbial BGC, solute chemistry, canopy radiation) from the shared column-level globals in `f90src/Ecosim_datatype/`. The **APIs subsystem** is the thin coupling layer that sits between the two. It contains:

- `f90src/APIs/` (7 F90 files) — the **call-surface** layer. Each module exposes one or two `*Send` / `*Recv` (or `Send` + driver + `Recv`) routines that copy data into / out of a private scratch structure and then invoke the physics kernel.
- `f90src/APIData/` (1 F90 file, `PlantAPIData.F90`) — the **data-container** layer. Holds module-level derived-type instances (`plt_site`, `plt_biom`, `plt_rbgc`, ...) that the plant physics modules read and write instead of touching the `*DataType` globals directly.

The two form a **producer/consumer boundary**:

```
 column globals in              APIs/*Send              plant / micro / geochem
 Ecosim_datatype/*DataType   ───────────────►   APIData/PlantAPIData derived-types
                             ◄───────────────
                               APIs/*Recv
                                                 ───────►  physics kernel reads
                                                 ◄───────  physics kernel writes
```

## Architectural intent

1. **Physics modules never `use` `SoilBGCDataType` / `SoilWaterDataType` / etc. directly.** Instead, plant code `use`s `PlantAPIData`, and the microbial kernel reads its forcings through `micforctype` / `micsttype` / `micfluxtype` passed as arguments. Grep across `f90src/Plant_bgc/` confirms this: every plant module there `use`s `PlantAPIData` (verified via `grep -rn "use PlantAPIData"`).
2. **The API modules are where unit/index translation happens.** `PlantAPISend` (`PlantAPI.F90:727`) and `PlantAPIRecv` (`PlantAPI.F90:48`) are long copy-in / copy-out routines. `MicAPISend` / `MicAPIRecv` do the same per soil layer (`MicBGCAPI.F90:155-595`). `GeochemAPISend` / `GeochemAPIRecv` do it per layer for solute chemistry (`GeochemAPI.F90:154-369`).
3. **Seams for substitution.** Because each kernel reads only its API-data container, a caller can swap physics implementations (e.g. run plant code standalone, or replace a kernel with a prescribed-phenology shortcut) by swapping the send/recv wrapper. The `ldo_sp_mode` branch in `PlantMod.F90:54-90` is a live example.
4. **Reduced compilation coupling.** Because plant physics does not `use` the soil globals, changing a soil data module does not force plant kernels to recompile. The CMake dependency chain (`f90src/APIs/CMakeLists.txt`) places `APIData` under `Plant_bgc`, and `APIs` on top.

## Navigation

| Doc | Covers |
|---|---|
| [`api_layer.md`](api_layer.md) | The 7 `.F90` files in `f90src/APIs/`: `PlantMod`, `PlantAPI`, `PlantCanAPI`, `PlantAPI4Uptake`, `MicBGCAPI`, `GeochemAPI`, `SurfPhysAPI`. Public subroutines, what each wraps, how the main loop invokes them. |
| [`api_data.md`](api_data.md) | `f90src/APIData/PlantAPIData.F90`: the 12 plant-facing derived types, their 12 module-level singleton instances (`plt_site`, `plt_biom`, ...), lifecycle, and rationale for being separate from `Ecosim_datatype/`. |

## Quick reference: call surface

| Public entry | Defined in | Called from |
|---|---|---|
| `PlantModel(yearIJ, NHW, NHE, NVN, NVS)` | `PlantMod.F90:33` | `ATSUtils/ATSEcoSIMAdvanceMod.F90:343` |
| `PlantCanopyRadsModel(I,J,NY,NX,DepthSurfWatIce)` | `PlantMod.F90:118` | `Modelforc/Hour1Mod.F90:201`, `ATSUtils/ATSEcoSIMAdvanceMod.F90:296` |
| `MicrobeModel(I,J,NHW,NHE,NVN,NVS)` | `MicBGCAPI.F90:78` | (no current caller in tree; see `api_layer.md` note) |
| `MicAPI_Init()` / `MicAPI_cleanup()` | `MicBGCAPI.F90:55` / `:66` | `Main/InitEcoSIM.F90:29`, `Main/EcoSIMDesctruct.F90:54` |
| `soluteModel(I,J,NHW,NHE,NVN,NVS)` | `GeochemAPI.F90:23` | (no current caller in tree) |
| `InitPlantAPIData()` / `DestructPlantAPIData()` | `APIData/PlantAPIData.F90:1734` / `:1790` | `Ecosim_mods/InitAllocMod.F90:48`, `Main/EcoSIMDesctruct.F90:43` |

The call-site survey above was produced by `grep -rn "call PlantModel|call MicrobeModel|call soluteModel|call PlantCanopyRadsModel"` across `f90src/`. Two entry points (`MicrobeModel`, `soluteModel`) currently have no in-tree caller; they are staged for a reorganization of the top-level driver (the subsystem is live, but invocation from the main scenario loop has not yet landed on this pin).
