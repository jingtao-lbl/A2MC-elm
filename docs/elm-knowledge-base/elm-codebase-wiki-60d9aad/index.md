---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# ELM Codebase Wiki (commit `60d9aad`)

This wiki is a purpose-built, source-grounded reference for the **E3SM Land Model (ELM)** as it exists in the `components/elm/src/` tree at commit `60d9aad` of the E3SM_FATES working tree. It is intentionally narrow: only the 239 Fortran modules that compose ELM itself. FATES, the atmosphere/ocean components, CIME, and the E3SM driver are **out of scope** and live in other wikis.

Every file reference in this wiki is anchored by path and line number against the pinned source tree.

## How to use this wiki

- **Read the overview first** (`overview/index.md`) — it sets out what ELM is, the seven source subsystems, and the subgrid hierarchy (gridcell → topounit → landunit → column → patch).
- **Use the directory map** (`overview/source_tree.md`) to locate files by subsystem and understand how the 239 `.F90` files partition across `biogeochem/`, `biogeophys/`, `main/`, `data_types/`, `dyn_subgrid/`, `utils/`, and `cpl/`.
- **Consult the module inventory** (`reference/module_inventory.md`) for a one-line description of every module (used as a fast lookup when you just need to know what a file is for).
- **Drill into a subsystem** via the subsystem indexes linked below once those pages exist. Subsystem pages give calling sequences, key types, and parameter lists.

## Navigation

### Top-level sections

| Section | Path | Purpose |
|---|---|---|
| Overview | [`overview/index.md`](overview/index.md) | What ELM is, its 7 subsystems, subgrid hierarchy, optional engines (FATES, PFLOTRAN, BeTR, FAN) |
| Source tree | [`overview/source_tree.md`](overview/source_tree.md) | Directory layout of `components/elm/src/` with file counts and subsystem descriptions |
| Module inventory | [`reference/module_inventory.md`](reference/module_inventory.md) | Full table of all 239 `.F90` modules with one-line descriptions |

### Subsystem indexes

| Subsystem | Path | F90 files | Subject area |
|---|---|---|---|
| Core / main | [`core/index.md`](core/index.md) | 63 | Driver (`elm_drv`), initialization/finalization, control flags, subgrid accessors, history/restart I/O, coupling glue |
| Biogeophysics | [`biogeophys/index.md`](biogeophys/index.md) | 54 | Energy balance, radiation, canopy/soil/snow/lake temperature and hydrology, aerosols |
| Biogeochemistry | [`biogeochem/index.md`](biogeochem/index.md) | 74 | C/N/P cycles, allocation, phenology, decomposition, fire, crop, CH4, VOC, dust |
| Dynamic subgrid | [`dyn_subgrid/index.md`](dyn_subgrid/index.md) | 17 | Transient land cover (pftdyn, harvest, crop), state conservation across weight changes |
| Data types | `data_types/` | 12 | Gridcell/topounit/landunit/column/vegetation derived types (structure + instance containers) |
| Utilities | `utils/` | 13 | Time manager, SPMD, domain, orbital, namelist helpers |
| Coupler interface | `cpl/` | 6 | MCT and ESMF driver entry points, import/export of coupler fields |

## Entry points at a glance

A short cheat sheet of the most useful file locations to bookmark when reading the source:

| What | File | Key symbol / line |
|---|---|---|
| Coupler-facing init (MCT) | `cpl/lnd_comp_mct.F90` | `subroutine lnd_init_mct` (`cpl/lnd_comp_mct.F90:63`) |
| Coupler-facing run (MCT) | `cpl/lnd_comp_mct.F90` | `subroutine lnd_run_mct` (`cpl/lnd_comp_mct.F90:415`) |
| Phase-one init | `main/elm_initializeMod.F90` | `subroutine initialize1` (`main/elm_initializeMod.F90:54`) |
| Phase-two init | `main/elm_initializeMod.F90` | `subroutine initialize2` (`main/elm_initializeMod.F90:452`) |
| Per-timestep driver | `main/elm_driver.F90` | `subroutine elm_drv` (`main/elm_driver.F90:197`) |
| Run-control flags | `main/elm_varctl.F90` | e.g. `use_fates` (`main/elm_varctl.F90:222`), `use_cn` (`:354`), `use_pflotran` (`:454`) |
| Physical constants | `main/elm_varcon.F90` | `subroutine elm_varcon_init` |
| Namelist reader | `main/controlMod.F90` | `subroutine control_init` |
| Subgrid instantiation | `main/elm_initializeMod.F90:342-362` | `grc_pp%Init`, `top_pp%Init`, `lun_pp%Init`, `col_pp%Init`, `veg_pp%Init` |
| FATES interface | `main/elmfates_interfaceMod.F90` | `ELMFatesGlobals1`, `ELMFatesGlobals2` |
| PFLOTRAN interface | `main/elm_interface_pflotranMod.F90` | (state exchange glue) |

## Scope and conventions

- **Source pin.** All citations use paths relative to `components/elm/src/`, e.g. `(main/elm_driver.F90:197)` refers to the `subroutine elm_drv` declaration. If a line number is given, it is verified against commit `60d9aad`.
- **No cross-component content.** If you are looking for the atmosphere model, the coupler/driver internals, CIME case machinery, MPAS, or FATES internals, this is the wrong wiki. ELM's interface *to* FATES is documented here (`main/elmfates_interfaceMod.F90`); FATES internals are not.
- **Optional engines.** ELM supports several compile/run-time alternative engines whose glue code lives in this tree:
  - **FATES** vegetation demography — enabled via `use_fates` (`main/elm_varctl.F90:222`); interface in `main/elmfates_interfaceMod.F90`.
  - **PFLOTRAN** reactive transport — enabled via `use_pflotran` (`main/elm_varctl.F90:454`); glue in `main/elm_interface_pflotranMod.F90`.
  - **BeTR** generic tracer transport — enabled via `use_betr` (`main/elm_varctl.F90:245`); BeTR-aware BGC variants live in `biogeochem/` with `BeTR` in the filename.
  - **FAN** (Flow of Agricultural Nitrogen) — enabled via `use_fan` (`main/elm_varctl.F90:372`); modules in `biogeochem/FanMod.F90` and `biogeochem/FanUpdateMod.F90`.
- **Subgrid hierarchy.** ELM adds a **topounit** level between gridcell and landunit that is not present in CLM5 (`data_types/TopounitType.F90:1`, initialized in `main/elm_initializeMod.F90:350`). The full hierarchy is: `gridcell → topounit → landunit → column → patch`.

## File counts

| Subdirectory | `.F90` files |
|---|---:|
| `biogeochem/` | 74 |
| `biogeophys/` | 54 |
| `main/` | 63 |
| `data_types/` | 12 |
| `dyn_subgrid/` | 17 |
| `utils/` | 13 |
| `cpl/` | 6 |
| **Total** | **239** |

(See [`reference/module_inventory.md`](reference/module_inventory.md) for the full listing.)

## What this wiki is not

- **Not an E3SM wiki.** See the user's separate E3SM wiki for the full coupled system.
- **Not a FATES wiki.** FATES has its own source tree under `external_models/` and its own wiki.
- **Not a user manual.** Namelist variable descriptions, build instructions, and case configuration are documented in E3SM's `bld/namelist_files/` and CIME, not here.
- **Not a research paper.** Citations are to code locations, not to the scientific literature.

## Source of truth

When the wiki and the source disagree, **the source wins**. The source pin is the commit hash given in every document's front matter. If you update the wiki, update the source pin and re-verify the citations.
