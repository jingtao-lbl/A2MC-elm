---
**Source pin:** ELM source at E3SM commit `d40b8431` (master HEAD, 2026-04-24)
**FATES pairing:** FATES at commit `e027a40` (sci.1.91.1_api.43.1.0, the api-43-1 milestone)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES — documented separately at `docs/fates-knowledge-base/fates-codebase-wiki-e027a40/`) and build helpers (`*.F90.in`, `*.pl`, `*.h`)
**Last verified:** 2026-04-26
---

# ELM Codebase Wiki (commit `d40b8431`)

This wiki is a purpose-built, source-grounded reference for the **E3SM Land Model (ELM)** as it exists in the `components/elm/src/` tree at commit `d40b8431` of the E3SM_FATES_api43-1 working tree. It is intentionally narrow: only the **242 Fortran modules** that compose ELM itself. FATES, the atmosphere/ocean components, CIME, and the E3SM driver are **out of scope** and live in other wikis.

This wiki is the canonical ELM reference for the A2MC `api-43-1` milestone. Built 2026-04-26 from a complete audit + rewrite of the prior `60d9aad` wiki against d40b8431 source. The companion `60d9aad` wiki at `elm-codebase-wiki-60d9aad/` is retained for Kougarok manuscript reproducibility.

Every file reference in this wiki is anchored by path and line number against the pinned source tree.

## What changed at d40b8431 (vs. 60d9aad)

The most calibration-relevant ELM-side changes:

| Change | Impact |
|---|---|
| **`elmfates_paraminterfaceMod.F90` and `FatesReadPFTs` DELETED** | FATES does its own JSON parameter loading at api.43+. Old 3-step parameter handoff (`FatesInterfaceInit → FatesReadPFTs → ELMFatesGlobals2`) collapsed to 2 steps. |
| **`alm_fates%init` is 3-arg** | New signature `init(this, bounds_proc, flandusepftdat)`. 2-arg calls don't compile. |
| **New per-timestep callbacks** | `wrap_FatesAtmosphericCarbonFluxes` and `wrap_FatesCarbonStocks` (called from `EcosystemDynMod.F90:268-269`); plus `col_cf%ZeroForFatesRR`, `alm_fates%UpdateLitterFluxes`, `wrap_WoodProducts`. |
| **~10 new FATES-related ELM namelist flags** | `fates_radiation_model`, `fates_stomatal_model`, `fates_leafresp_model`, `fates_cstarvation_model`, `fates_hydro_solver`, `fates_electron_transport_model`, `use_fates_luh`/`lupft`/`potentialveg`/`daylength_factor`, `use_fates_managed_fire`, `fates_harvest_mode`. (`use_fates_logging` REMOVED.) |
| **New `dynFATESLandUseChangeMod.F90`** | Owns LUH2 land-use forcing into FATES (12 LUH2 states, 108 transitions, 5 `fates_harvest_mode` enum values). Gated by `use_fates_luh` flag. |
| **CN/CNP allocation refactor** | `Allocation3_PlantCNPAlloc` no longer exists; split into `PlantCNPAlloc_RD` and `PlantCNPAlloc_ECAMIC` dispatched on `nu_com`, plus 7 new helper subroutines. |
| **N/P subroutine signatures broke** | `NitrogenDeposition` (7→2 args), `NitrogenLeaching`/`PhosphorusLeaching`/`PhosphorusBiochemMin` (`bounds` arg removed), `NitrogenFert` (+2 perennial-crop args), `RootDynamics` (`dt` is explicit arg). |
| **New ocean coupling** | `Drainage_To_OCN` (210 lines), `ocn2lnd_vars` arg threaded through `Drainage`/`Infiltration`/`HydrologyDrainage`. Water balance equation gained 6 new flux terms. |
| **Ice-wedge polygon (IWP) + IM2 hillslope hydrology** | NGEE-Arctic features. New state on `canopystate_type` (`altmax_1989`, `altmax_ever`) and `col_ws` (`excess_ice`, `iwp_microrel`, `iwp_subsidence`, `frac_melted`). |
| **`use_extrasnowlayers` decoupled from firn physics** | New `use_firn_percolation_and_compaction` flag is what controls firn behavior at most use sites. |
| **`cpl/lnd_comp_esmf.F90` REMOVED** | `cpl/` is now 5 files (was 6). |
| **New IAC + MOAB integrations** | `iac2lndMod.F90`, `lnd2iacMod.F90`, `ocn2lndType.F90`, `MOABGridType.F90` added. |

## How to use this wiki

- **Read the overview first** (`overview/index.md`) — what ELM is, its 7 source subsystems, the subgrid hierarchy.
- **Use the source tree map** (`overview/source_tree.md`) to locate files by subsystem.
- **Consult the module inventory** (`reference/module_inventory.md`) for one-line descriptions of every module.
- **Drill into a subsystem** via the subsystem indexes below.
- **For ELM↔FATES boundary** questions: start at `core/fates_interface.md`.

## Navigation

### Top-level sections

| Section | Path | Purpose |
|---|---|---|
| Overview | [`overview/index.md`](overview/index.md) | What ELM is, its 7 subsystems, subgrid hierarchy, optional engines |
| Source tree | [`overview/source_tree.md`](overview/source_tree.md) | Directory layout with file counts and subsystem descriptions |
| Module inventory | [`reference/module_inventory.md`](reference/module_inventory.md) | Full table of all 242 `.F90` modules with one-line descriptions |

### Subsystem indexes

| Subsystem | Path | F90 files | Subject area |
|---|---|---|---|
| Core / main | [`core/index.md`](core/index.md) | 65 | Driver, init/finalization, control flags, subgrid accessors, history/restart, **FATES coupling glue** |
| Biogeophysics | [`biogeophys/index.md`](biogeophys/index.md) | 54 | Energy balance, radiation, canopy/soil/snow/lake T+H2O, aerosols, **new ocean drainage**, **IWP** |
| Biogeochemistry | [`biogeochem/index.md`](biogeochem/index.md) | 74 | C/N/P cycles, allocation (RD vs ECAMIC), phenology, decomposition, fire, crop, CH4, VOC, dust |
| Dynamic subgrid | [`dyn_subgrid/index.md`](dyn_subgrid/index.md) | 18 | Transient land cover, **new FATES LUH2 land-use change**, IAC coupling, FAN N pools |
| Data types | `data_types/` | 13 | Gridcell/topounit/landunit/column/vegetation derived types; new `MOABGridType.F90` |
| Utilities | `utils/` | 13 | Time manager, SPMD, domain, orbital, namelist helpers |
| Coupler interface | `cpl/` | 5 | MCT entry point, import/export of coupler fields (ESMF entry was removed) |

### ELM↔FATES boundary docs (high-priority for A2MC)

The api-43-1 milestone is a coordinated ELM+FATES pair. These docs document the boundary contract:

- [`core/fates_interface.md`](core/fates_interface.md) — ELM-side FATES interface module (`elmfates_interfaceMod.F90`); `alm_fates%init` 3-arg signature; new `wrap_*` callbacks
- [`core/namelist_and_control.md`](core/namelist_and_control.md) — ~10 new FATES-related namelist flags
- [`dyn_subgrid/fates_land_use_change.md`](dyn_subgrid/fates_land_use_change.md) — new `dynFATESLandUseChangeMod` for LUH2 forcing into FATES
- [`biogeochem/index.md`](biogeochem/index.md) — `wrap_FatesAtmosphericCarbonFluxes`, `wrap_FatesCarbonStocks`, `wrap_WoodProducts` calls

## Entry points at a glance

A cheat sheet of the most useful file locations to bookmark when reading source at d40b8431:

| What | File | Key symbol / line |
|---|---|---|
| Coupler-facing init (MCT) | `cpl/lnd_comp_mct.F90` | `subroutine lnd_init_mct` (`cpl/lnd_comp_mct.F90:58`) |
| Coupler-facing run (MCT) | `cpl/lnd_comp_mct.F90` | `subroutine lnd_run_mct` (`cpl/lnd_comp_mct.F90:437`) |
| Phase-one init | `main/elm_initializeMod.F90` | `subroutine initialize1` (`main/elm_initializeMod.F90:62`) |
| Phase-two init | `main/elm_initializeMod.F90` | `subroutine initialize2` (`main/elm_initializeMod.F90:503`) |
| Phase-three init (NEW) | `main/elm_initializeMod.F90` | `subroutine initialize3` (`main/elm_initializeMod.F90:1146`) — VSFM + PETSc thermal model wiring via EMI |
| Per-timestep driver | `main/elm_driver.F90` | `subroutine elm_drv` (`main/elm_driver.F90:207`) |
| Run-control flags | `main/elm_varctl.F90` | `use_fates` (`:227`), `use_cn` (`:388`), etc. |
| Namelist reader | `main/controlMod.F90` | `subroutine control_init` |
| FATES interface | `main/elmfates_interfaceMod.F90` (lowercase!) | `alm_fates%init` (`:824`), `wrap_FatesAtmosphericCarbonFluxes` (`:272, body 2771-2816`), `wrap_FatesCarbonStocks` (`:273, body 2820-2858`) |
| FATES land-use change | `dyn_subgrid/dynFATESLandUseChangeMod.F90` | New file; `landuse_states/transitions/harvest` arrays |
| New ocean drainage | `biogeophys/HydrologyDrainage.F90` | `subroutine Drainage_To_OCN` |

## Scope and conventions

- **Pinned commit:** every cited line resolves against `d40b8431` of E3SM master.
- **FATES out of scope** here — documented separately at `docs/fates-knowledge-base/fates-codebase-wiki-e027a40/`. ELM↔FATES boundary contracts (callbacks, namelist flags, type signatures) ARE in scope.
- **Build helpers excluded:** `*.F90.in`, `*.pl`, `*.h` files in `src/` are excluded from the 242 module count.
- **Filename casing matters:** `main/elmfates_interfaceMod.F90` is lowercase. Older docs / old wikis that used a CamelCase form of this filename are wrong.

**Last verified:** 2026-04-26
