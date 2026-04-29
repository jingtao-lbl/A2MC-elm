---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Code Architecture and Design Patterns

## Purpose and Scope

This page documents the software architecture, design patterns, and coding conventions used in the FATES codebase at commit `e027a40` (tag `sci.1.91.1_api.43.1.0`). It provides developers with a technical understanding of how the code is organized, how major subsystems interact, and what patterns are used to achieve modularity and extensibility.

For information about specific subsystems:

- [Module Organization](modules.md) — directory structure, naming conventions, key modules
- [Linked List Data Structures](linked_lists.md) — doubly-linked patch and cohort lists
- [PARTEH Extensibility Framework](parteh_framework.md) — pluggable allocation hypotheses

## Top-Level Object Model

### Fates Interface Type

The top-level object that connects FATES to host land models (HLMs) is `fates_interface_type`, declared at `main/FatesInterfaceMod.F90:138-172`. It holds:

| Field | Type | Purpose |
| --- | --- | --- |
| `nsites` | `integer` | Number of FATES sites managed by this interface instance (`main/FatesInterfaceMod.F90:144`) |
| `sites(:)` | `type(ed_site_type), pointer` | Array of site state (root of the linked-list hierarchy) (`:146`) |
| `bc_in(:)` | `type(bc_in_type), allocatable` | Inputs from HLM to FATES (per site) (`:156`) |
| `bc_out(:)` | `type(bc_out_type), allocatable` | Outputs from FATES to HLM (per site) (`:161`) |
| `bc_pconst` | `type(bc_pconst_type)` | Parameter constants shared with HLM (single instance) (`:169`) |

`fates_interface_type` therefore owns the complete vegetation state tree and the host-model boundary-condition arrays.

### Vegetation Data Structure Hierarchy

FATES organizes vegetation into a three-level hierarchy:

```
fates_interface_type
   └── sites(:)  : ed_site_type                  (main/EDTypesMod.F90:325)
          └── oldest_patch -> ... -> youngest_patch : fates_patch_type  (biogeochem/FatesPatchMod.F90:64)
                 └── tallest -> ... -> shortest : fates_cohort_type     (biogeochem/FatesCohortMod.F90:61)
```

Patches within a site are held in a doubly-linked list ordered by patch age; cohorts within a patch are held in a doubly-linked list ordered by height. This design enables dynamic creation and deletion without array reallocation, efficient insertion at arbitrary positions, and natural ordering for age-based and height-based operations. See [Linked List Data Structures](linked_lists.md) for pointer field details.

Source files:

- `main/EDTypesMod.F90:325-329` (`ed_site_type` with `oldest_patch` at `:328` and `youngest_patch` at `:329`)
- `biogeochem/FatesPatchMod.F90:64-271` (`fates_patch_type` with `tallest`, `shortest`, `older`, `younger` at `:67-70`)
- `biogeochem/FatesCohortMod.F90:61-301` (`fates_cohort_type` with `taller`, `shorter` at `:64-65`)

## Boundary Condition Architecture

FATES communicates with host land models through three boundary condition types declared in `main/FatesInterfaceTypesMod.F90`:

| BC Type | Direction | Purpose |
| --- | --- | --- |
| `bc_in_type` | HLM → FATES | Environmental forcing and soil state (e.g., radiation, soil moisture, soil temperature, lightning) |
| `bc_out_type` | FATES → HLM | Vegetation state and fluxes to soil (e.g., LAI, canopy height, litter fluxes, root fractions) |
| `bc_pconst_type` | FATES → HLM | Parameter constants the HLM needs at startup (one-time transfer) |

The interface module allocates per-site arrays of `bc_in_type` and `bc_out_type` through `allocate_bcin` (`main/FatesInterfaceMod.F90:443`) and `allocate_bcout` (`main/FatesInterfaceMod.F90:623`). A single `bc_pconst` instance is held directly on the interface type (`main/FatesInterfaceMod.F90:169`) and is allocated and populated by `allocate_bcpconst` (`:236`) and `set_bcpconst` (`:258`).

This three-channel pattern keeps host-model coupling explicit, makes FATES portable across HLMs (ELM and CTSM at present), and separates the read-only forcing stream from the output stream.

## PARTEH: Extensible Allocation Framework

PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses) uses a Fortran 2003 class hierarchy to allow multiple allocation hypotheses to coexist in a single build.

### Class Hierarchy

The base class is `prt_vartypes` declared at `parteh/PRTGenericMod.F90:232-278`. Although it is not declared with the Fortran `abstract` keyword, it functions as abstract in intent: its base implementations of `DailyPRT`, `FastPRT`, and `DamageRecovery` call `endrun` with messages such as "Daily PRT Allocation must be extended" (`parteh/PRTGenericMod.F90:1258-1289`). Any hypothesis that fails to override these procedures aborts the run.

Each hypothesis extends `prt_vartypes`:

- Carbon-only hypothesis: `callom_prt_vartypes` (`parteh/PRTAllometricCarbonMod.F90:136-143`) overrides `DailyPRT` and `FastPRT`.
- CNP hypothesis: `cnp_allom_prt_vartypes` (`parteh/PRTAllometricCNPMod.F90:254-270`) additionally overrides `GetNutrientTarget` and adds CNP-specific procedures (`CNPPrioritizedReplacement`, `CNPStatureGrowth`, `EstimateGrowthNC`, `CNPAdjustFRootTargets`, `CNPAllocateRemainder`, `GetDeficit`, `TrimFineRoot`).

Each cohort holds a polymorphic pointer to a `prt_vartypes` object:

```fortran
class(prt_vartypes), pointer :: prt
```

declared at `biogeochem/FatesCohortMod.F90:71`. The concrete type is chosen at cohort creation by `InitPRTObject` (`biogeochem/EDCohortDynamicsMod.F90:230`), driven by the `hlm_parteh_mode` configuration flag.

### Hypothesis Selection Constants

The selection constants are declared at `parteh/PRTGenericMod.F90:69-70`:

```fortran
integer, parameter, public :: prt_carbon_allom_hyp   = 1
integer, parameter, public :: prt_cnp_flex_allom_hyp = 2
```

Each hypothesis module allocates its own singleton mapping object and points the module-level `prt_global` pointer at it. For example, `parteh/PRTAllometricCarbonMod.F90:160` declares `class(prt_global_type), public, target, allocatable :: prt_global_ac` and `:251` sets `prt_global => prt_global_ac`. The CNP equivalent is `prt_global_acnp` at `parteh/PRTAllometricCNPMod.F90:282`, with the assignment `prt_global => prt_global_acnp` at `:365`.

See [PARTEH Extensibility Framework](parteh_framework.md) for the variable-registration pattern, the `sp_organ_map` lookup, and how to add a new hypothesis.

## Module Organization Patterns

### Functional Separation and Layering

FATES source files are organized by functional responsibility under directories `main/`, `biogeochem/`, `biogeophys/`, `fire/`, `parteh/`, and `radiation/` (see [Module Organization](modules.md) for the full directory inventory and the role of each). The layering runs roughly:

```
FatesInterfaceMod (main/)          ← HLM coupling, daily/sub-daily entry points
    │
    ├── EDMainMod (main/)           ← daily dynamics orchestration
    │      └── ed_ecosystem_dynamics (main/EDMainMod.F90:148)
    │
    ├── EDPhysiologyMod (biogeochem/)   ← phenology, recruitment, trim, litter
    │
    ├── EDPatchDynamicsMod (biogeochem/)  ← disturbance, patch create/fuse/terminate
    │
    ├── EDCohortDynamicsMod (biogeochem/) ← cohort create, terminate, fuse
    │
    ├── PARTEH (parteh/)            ← allocation and reactive transport
    │
    └── Radiation (radiation/)      ← canopy two-stream and Norman radiative transfer
```

### Naming Conventions

| Pattern | Purpose | Examples |
| --- | --- | --- |
| `ED*Mod.F90` | Ecosystem-demography core logic (historical naming) | `EDMainMod.F90`, `EDPhysiologyMod.F90`, `EDCohortDynamicsMod.F90` |
| `Fates*Mod.F90` | FATES-specific modules (newer naming) | `FatesInterfaceMod.F90`, `FatesAllometryMod.F90`, `FatesCohortMod.F90`, `FatesPatchMod.F90`, `FatesNormanRadMod.F90`, `FatesRadiationDriveMod.F90`, `FatesLandUseChangeMod.F90` |
| `PRT*Mod.F90` | PARTEH allocation system | `PRTGenericMod.F90`, `PRTAllometricCarbonMod.F90`, `PRTAllometricCNPMod.F90` |
| `SF*Mod.F90` | SPITFIRE fire model | `SFMainMod.F90`, `SFParamsMod.F90`, `SFEquationsMod.F90`, `SFFireWeatherMod.F90`, `SFNesterovMod.F90` |
| `*Types*Mod` (suffix) | Type definitions only | `EDTypesMod.F90`, `FatesInterfaceTypesMod.F90` |
| `*Params*Mod` (suffix) | Parameter definition/storage | `EDParamsMod.F90`, `SFParamsMod.F90`, `PRTParametersMod.F90`, `FatesLeafBiophysParamsMod.F90` |

## Parameter System Architecture

### JSON-Based Parameter Loading

At e027a40, FATES reads parameters from a JSON file (the legacy CDL format has been replaced). Parameter loading is driven from `SetFatesGlobalElements1` at `main/FatesInterfaceMod.F90:792-893`, which calls (`:825-841`):

1. `JSONSetInvalid(...)` — set a sentinel value for missing/null entries
2. `JSONSetLogInit(...)` — wire up the logger
3. `JSONRead(paramfile, pstruct)` — parse the JSON file into a generic `params_type` structure (declared in `main/JSONParameterUtilsMod.F90:189-251`)
4. `FatesTransferParameters()` (`main/FatesInterfaceMod.F90:2675-2694`) — copy parameters from the generic struct into typed primitive arrays. This wrapper calls in order: `TransferParamsGeneric`, `TransferParamsSpitFire`, `TransferParamsPRT`, `TransferParamsLeafBiophys`, `TransferParamsPFT`.

The legacy two-phase `FatesReadParameters`/`FatesReportParameters` pair has been removed at e027a40. The legacy "synchronized parameters" module that existed in earlier tags is also gone; parameter synchronization is now handled by `main/JSONParameterUtilsMod.F90` together with `main/FatesParametersInterface.F90`.

Parameters are stored in singleton instances:

- PFT parameters: `EDPftvarcon_inst` of type `EDPftvarcon_type`, declared at `main/EDPftvarcon.F90:291`.
- PARTEH parameters: `prt_params` of type `prt_param_type`, declared at `parteh/PRTParametersMod.F90:195`.
- Global scalars: `main/EDParamsMod.F90` (e.g., `nclmax = 3` at `:76`, `maxpft = 16` at `:91`, `nlevleaf`, `maxSWb`).
- Fire parameters: singleton in `fire/SFParamsMod.F90`.

All are read-only after initialization and accessed from any module via `use` statements.

## Type-Bound Procedure Pattern

FATES uses Fortran 2003 type-bound procedures (TBPs) to attach methods to derived types.

The type-bound procedures declared on `fates_cohort_type` (`biogeochem/FatesCohortMod.F90:287-299`) are:

```fortran
contains

procedure :: Init
procedure :: NanValues
procedure :: ZeroValues
procedure :: Create
procedure :: Copy
procedure :: FreeMemory
procedure :: CanUpperUnder
procedure, public :: SumMortForHistory
procedure :: InitPRTBoundaryConditions
procedure :: UpdateCohortBioPhysRates
procedure :: Dump
```

`SumMortForHistory` (line 296) is new at e027a40 and aggregates per-cohort mortality components for history output. Cohort fusion, creation, and termination remain module-level public subroutines in `biogeochem/EDCohortDynamicsMod.F90`: `create_cohort` at `:123`, `terminate_cohorts` at `:283`, `terminate_cohort` at `:413`, and `fuse_cohorts` at `:648`. `InitPRTObject` (`:230`) is also module-level.

`fates_patch_type` declares a substantially expanded TBP set at `biogeochem/FatesPatchMod.F90:250-269` (18 procedures). New at e027a40 are `NanDynamics`, `ZeroDynamics`, `ReAllocateDynamics`, `CountCohorts`, `ValidateCohorts`, `InsertCohort`, `SortCohorts`, `UpdateTreeGrassArea`, and `UpdateLiveGrass`. The cohort-list operations `CountCohorts`, `InsertCohort`, and `SortCohorts` were previously module-level subroutines in `EDCohortDynamicsMod` (named `count_cohorts`, `insert_cohort`, `sort_cohorts`); they have been promoted to patch type-bound procedures. Call sites use the new pattern, for example `call patchptr%InsertCohort(newCohort)` at `biogeochem/EDCohortDynamicsMod.F90:224`, `call currentPatch%SortCohorts()` at `main/EDMainMod.F90:272`, and `call currentPatch%CountCohorts()` at `main/EDMainMod.F90:877`. See [Linked List Data Structures](linked_lists.md) for the full traversal patterns.

Advantages of the TBP pattern:

- Methods live with the data they operate on (encapsulation).
- Namespace is managed by the type (`cohort%Dump` vs. a free-floating `Dump`).
- Polymorphism is supported: base-class methods can be overridden by extended types, as in PARTEH (`DailyPRT => DailyPRTAllometricCarbon` at `parteh/PRTAllometricCarbonMod.F90:140`).

## Pointer vs Allocatable Arrays

FATES uses Fortran pointers for self-referential linked-list types and allocatable arrays for fixed-size contiguous buffers. Patch and cohort linked-list fields are declared `type(...), pointer` (`taller`, `shorter` at `biogeochem/FatesCohortMod.F90:64-65`; `older`, `younger`, `tallest`, `shortest` at `biogeochem/FatesPatchMod.F90:67-70`). Boundary-condition arrays on the interface type are declared `type(...), allocatable` (e.g., `bc_in(:)` at `main/FatesInterfaceMod.F90:156`).

Rationale:

- Pointers are required for self-referential types and support a null state via `null()` and `associated()`.
- Allocatables offer better performance for contiguous arrays and give automatic deallocation on scope exit.

## Mass Balance Checking Pattern

FATES uses ubiquitous mass-balance checks as a defensive-programming discipline. On the PARTEH side, the base-class routine `CheckMassConservation` is declared `non_overridable` at `parteh/PRTGenericMod.F90:267` and implemented at `parteh/PRTGenericMod.F90:954-1021`. It verifies, per variable and per position, that

```
val - val0  ==  net_alloc + turnover + burned + damaged + herbivory  (within tolerance)
```

using the state-and-flux fields described in [PARTEH Extensibility Framework](parteh_framework.md). The `herbivory` flux (declared on `prt_vartype` at `parteh/PRTGenericMod.F90:192`) was added at e027a40 alongside the `GetHerbivory` accessor. Because `CheckMassConservation` is `non_overridable`, every hypothesis inherits it automatically, and new hypotheses cannot accidentally weaken the mass-balance contract.

## Summary of Design Patterns

| Pattern | Implementation | Purpose |
| --- | --- | --- |
| Strategy | `prt_vartypes` base + `callom_prt_vartypes` / `cnp_allom_prt_vartypes` extensions | Swappable allocation algorithms |
| Singleton | `prt_global` (`parteh/PRTGenericMod.F90:396`), `EDPftvarcon_inst`, `prt_params` | Shared read-only parameter and mapping state |
| Linked List | Patches (age-ordered), cohorts (height-ordered) | Dynamic vegetation structure |
| JSON Parameter Loading | `JSONRead` + `FatesTransferParameters` | Parse JSON, dispatch to typed parameter primitives |
| Boundary Condition | `bc_in`, `bc_out`, `bc_pconst` | Clean separation of HLM coupling channels |
| Template Method | `DailyPRT` / `FastPRT` base-to-override | Algorithm skeleton with hypothesis-specific steps |
| Defensive Mass Balance | `CheckMassConservation` (non_overridable TBP) | Runtime conservation enforcement |

Sources: files listed in each section, and the directory inventory under `main/`, `biogeochem/`, `biogeophys/`, `fire/`, `parteh/`, and `radiation/`.
