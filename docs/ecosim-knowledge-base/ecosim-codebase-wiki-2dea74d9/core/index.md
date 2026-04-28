---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** core orchestration: `f90src/{Main, Ecosim_mods, Modelconfig, Modelpars, Mesh, Utils, Minimath, DebugTools}/`
**Last verified:** 2026-04-24
---

# Core Orchestration and Infrastructure

This section covers the top-level orchestration layer that wires together the ELM-FATES... correction, the EcoSIM biogeochemistry model. These modules do not themselves implement plant or soil biogeochemistry. They set up the grid, allocate model state, read configuration, march time, initialize each year, and cleanly tear everything down at shutdown. Everything else in the codebase (plant BGC, microbial BGC, geochemistry, hydrothermal transport, APIs) plugs into the entry points defined here.

The eight subdirectories under this "core" umbrella separate concerns roughly as follows.

| Directory | Role | Key entry points |
|---|---|---|
| `Main/` | Whole-simulation setup and teardown | `InitModules`, `DestructEcoSIM` |
| `Ecosim_mods/` | Annual and cold-start initialization of soil, plant, chemistry state | `InitAlloc`, `starts` + `startsim`, `startq`, `starte` |
| `Modelconfig/` | Compile-time constants, run-mode flags, tracer/element IDs | `EcoSIMConfig`, `EcoSIMCtrlMod`, `TracerIDMod`, `ElmIDMod`, `EcoSIMSolverPar` |
| `Modelpars/` | Scientific parameter tables (microbes, plants, solutes, tracer props) | `EcoSiMParDataMod` (`micpar`, `pltpar`), `NitroPars`, `SoluteParMod`, `ChemTracerParsMod`, `TracerPropMod` |
| `Mesh/` | Horizontal/vertical grid layout and column/pft indexing | `SetMesh`, `SetMeshATS`, `GridConsts` |
| `Utils/` | Precision kinds, physical constants, timing, logging, netCDF I/O helpers | `data_kind_mod`, `EcosimConst`, `UnitMod`, `abortutils`, `ncdio_pio`, `ecosim_Time_Mod` |
| `Minimath/` | Safe arithmetic, sparse BLAS-like ops, small physical functions | `MiniMathMod`, `MiniFuncMod`, `LinearAlgebraMod` |
| `DebugTools/` | Verbose print helpers gated by `lverb` | `DebugToolMod` |

## Documentation map

| File | What it covers |
|---|---|
| [main_orchestration.md](main_orchestration.md) | `Main/InitEcoSIM.F90`, `Main/EcoSIMDesctruct.F90` and the four `Ecosim_mods/` initialization drivers (`InitAllocMod`, `StarteMod`, `StartqMod`, `StartsMod`) — the actual call sequence from driver entry through per-year init |
| [model_config.md](model_config.md) | `Modelconfig/` (run-mode flags, simulation type, solver sub-cycle counts, chemical-element IDs, tracer IDs) and `Modelpars/` (microbial parameter table object `micpar`, plant parameter table object `pltpar`, nitrogen kinetic parameters, solute equilibrium constants, tracer diffusivities/solubilities) |
| [grid_and_mesh.md](grid_and_mesh.md) | `Mesh/GridConsts.F90` (`JX`, `JY`, `JZ`, `JP`, `bounds_type`) and `Mesh/GridMod.F90` (`SetMesh`, `SetMeshATS`, `get_col`, `get_pft`) — how the landscape rectangle is discretized and how column/pft linear indices are derived |
| [utilities.md](utilities.md) | `Utils/` (14 files: kinds, constants, time type, file I/O, netCDF wrapper, logging, timer, unit conversion, IEEE NaN/Inf), `Minimath/` (3 files), `DebugTools/` (1 file) |

## The "big picture" flow

The main driver (`drivers/ecosim/ecosim.F90`) executes the following ordered sequence. All named routines below are documented in the sub-docs.

```
ecosim.F90 (driver)
  ├─ namelist_to_buffer        [Utils/fileUtil.F90]
  ├─ readnamelist              [drivers/ecosim/EcoSIMAPI.F90]
  ├─ SetMesh(NHW,NVN,NHE,NVS)  [Mesh/GridMod.F90]                  ── establish JX,JY,JZ,JP and bounds
  ├─ InitModules()             [Main/InitEcoSIM.F90]               ── allocate state for every subsystem
  │    └─ InitAlloc()          [Ecosim_mods/InitAllocMod.F90]      ── 30+ per-subsystem Init* calls
  ├─ write_modelconfig, set_sim_type, etimer%update_sim_len
  ├─ hist_htapes_build                                             [IO]
  ├─ get_clm_years                                                 [ClimReadMod]
  ├─ loop NN1=1..nperiods:
  │    ├─ set_ecosim_solver(NPXS, NPYS, NCYC_LITR, NCYC_SNOW)      [Ecosim_mods/StartsMod.F90]
  │    └─ per-year loop:
  │         └─ AdvanceModelOneYear(NHW,NHE,NVN,NVS,nlend)          [drivers/ecosim/EcoSIMAPI.F90]
  │              ├─ STARTS(...)  [StartsMod]        ── on year boundary
  │              ├─ STARTQ(...)  [StartqMod]        ── on year boundary (if plant_model)
  │              ├─ STARTE(...)  [StarteMod]        ── on year boundary (if soichem_model)
  │              └─ day/hour loop with DAY, HOUR1, WATSUB, ...
  ├─ regressiontest (if do_rgres)
  └─ DestructEcoSIM()          [Main/EcoSIMDesctruct.F90]          ── ~35 per-subsystem Destruct* calls
```

Callers: `drivers/ecosim/ecosim.F90:10-23, 87-156` wires `SetMesh`, `InitModules`, `set_ecosim_solver`, `AdvanceModelOneYear`, and `DestructEcoSIM`. `AdvanceModelOneYear` at `drivers/ecosim/EcoSIMAPI.F90:321-460+` calls `STARTS`, `STARTQ`, `STARTE` (`drivers/ecosim/EcoSIMAPI.F90:328-330, 383, 399, 408`).

An alternative entry path exists for ATS coupling via `f90src/ATSUtils/ATSEcoSIMInitMod.F90` and `ATSEcoSIMAdvanceMod.F90`, which use `SetMeshATS` in place of `SetMesh` and call `startsim` + `set_ecosim_solver` directly. That path is documented in the APIs section of the wiki, not here.

## Key invariants to remember

- `InitAlloc()` is the single entry point for memory allocation of all state data types. If you add a new `*DataType` module with its own `Init*`/`Destruct*`, you wire it in at `Ecosim_mods/InitAllocMod.F90` and `Main/EcoSIMDesctruct.F90` — not in the driver.
- The globals `micpar` and `pltpar` (declared in `Modelpars/EcoSiMParDataMod.F90`) are the canonical parameter tables. Subsystems `use EcoSiMParDataMod, only: micpar, pltpar` instead of redefining.
- `bounds` (declared in `Mesh/GridConsts.F90`) is the canonical grid-bounds object. Functions like `get_col(NY,NX)` and `get_pft(NZ,NY,NX)` in `Mesh/GridMod.F90` produce the linearized column/pft indices used elsewhere.
- `salt_model`, `plant_model`, `microbial_model`, `soichem_model`, `ats_cpl_mode` (all in `EcoSIMCtrlMod`) gate optional subsystems at init time. Changing their defaults affects both allocation and per-year re-initialization.
