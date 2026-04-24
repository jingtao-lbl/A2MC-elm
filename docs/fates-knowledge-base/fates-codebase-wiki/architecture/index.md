---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Code Architecture and Design Patterns

## Purpose and Scope

This page documents the software architecture, design patterns, and coding conventions used in the FATES codebase at commit `e85d997`. It provides developers with a technical understanding of how the code is organized, how major subsystems interact, and what patterns are used to achieve modularity and extensibility.

For information about specific subsystems:

- [Module Organization](modules.md) — directory structure, naming conventions, key modules
- [Linked List Data Structures](linked_lists.md) — doubly-linked patch and cohort lists
- [PARTEH Extensibility Framework](parteh_framework.md) — pluggable allocation hypotheses

## Top-Level Object Model

### Fates Interface Type

The top-level object that connects FATES to host land models (HLMs) is `fates_interface_type`, declared in `main/FatesInterfaceMod.F90:125-159`. It holds:

| Field | Type | Purpose |
| --- | --- | --- |
| `nsites` | `integer` | Number of FATES sites managed by this interface instance |
| `sites(:)` | `type(ed_site_type), pointer` | Array of site state (root of the linked-list hierarchy) |
| `bc_in(:)` | `type(bc_in_type), allocatable` | Inputs from HLM to FATES (per site) |
| `bc_out(:)` | `type(bc_out_type), allocatable` | Outputs from FATES to HLM (per site) |
| `bc_pconst` | `type(bc_pconst_type)` | Parameter constants shared with HLM (single instance) |

`fates_interface_type` therefore owns the complete vegetation state tree and the host-model boundary-condition arrays (`main/FatesInterfaceMod.F90:131-156`).

### Vegetation Data Structure Hierarchy

FATES organizes vegetation into a three-level hierarchy:

```
fates_interface_type
   └── sites(:)  : ed_site_type                  (main/EDTypesMod.F90:231)
          └── oldest_patch -> ... -> youngest_patch : fates_patch_type  (biogeochem/FatesPatchMod.F90:35)
                 └── tallest -> ... -> shortest : fates_cohort_type     (biogeochem/FatesCohortMod.F90:60)
```

Patches within a site are held in a doubly-linked list ordered by patch age; cohorts within a patch are held in a doubly-linked list ordered by height. This design enables dynamic creation and deletion without array reallocation, efficient insertion at arbitrary positions, and natural ordering for age-based and height-based operations. See [Linked List Data Structures](linked_lists.md) for pointer field details.

Source files:

- `main/EDTypesMod.F90:231-235` (`ed_site_type` with `oldest_patch` and `youngest_patch`)
- `biogeochem/FatesPatchMod.F90:35-41` (`fates_patch_type` with `tallest`, `shortest`, `older`, `younger`)
- `biogeochem/FatesCohortMod.F90:60-64` (`fates_cohort_type` with `taller`, `shorter`)

## Boundary Condition Architecture

FATES communicates with host land models through three boundary condition types declared in `main/FatesInterfaceTypesMod.F90`:

| BC Type | Direction | Purpose |
| --- | --- | --- |
| `bc_in_type` | HLM → FATES | Environmental forcing and soil state (e.g., radiation, soil moisture, soil temperature, lightning) |
| `bc_out_type` | FATES → HLM | Vegetation state and fluxes to soil (e.g., LAI, canopy height, litter fluxes, root fractions) |
| `bc_pconst_type` | FATES → HLM | Parameter constants the HLM needs at startup (one-time transfer) |

The interface module allocates per-site arrays of `bc_in_type` and `bc_out_type` through `allocate_bcin` (`main/FatesInterfaceMod.F90:412`) and `allocate_bcout` (`main/FatesInterfaceMod.F90:569`). A single `bc_pconst` instance is held directly on the interface type (`main/FatesInterfaceMod.F90:156`), since parameter constants do not vary by site.

This three-channel pattern keeps host-model coupling explicit, makes FATES portable across HLMs (ELM and CTSM at present), and separates the read-only forcing stream from the output stream.

## PARTEH: Extensible Allocation Framework

PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses) uses a Fortran 2003 class hierarchy to allow multiple allocation hypotheses to coexist in a single build.

### Class Hierarchy

The base class is `prt_vartypes` in `parteh/PRTGenericMod.F90:233-277`. Although it is not declared with the Fortran `abstract` keyword, it functions as abstract in intent: its base implementations of `DailyPRT`, `FastPRT`, and `DamageRecovery` call `endrun` with messages such as "Daily PRT Allocation must be extended" (`parteh/PRTGenericMod.F90:1185-1216`). Any hypothesis that fails to override these procedures aborts the run.

Each hypothesis extends `prt_vartypes`:

- Carbon-only hypothesis: `callom_prt_vartypes` (`parteh/PRTAllometricCarbonMod.F90:136-143`) overrides `DailyPRT` and `FastPRT`.
- CNP hypothesis: `cnp_allom_prt_vartypes` (`parteh/PRTAllometricCNPMod.F90:250-266`) additionally overrides `GetNutrientTarget` and adds CNP-specific procedures (`CNPPrioritizedReplacement`, `CNPStatureGrowth`, `EstimateGrowthNC`, `CNPAdjustFRootTargets`, `CNPAllocateRemainder`, `GetDeficit`, `TrimFineRoot`).

Each cohort holds a polymorphic pointer to a `prt_vartypes` object:

```fortran
class(prt_vartypes), pointer :: prt
```

declared in `biogeochem/FatesCohortMod.F90:70`. The concrete type is chosen at cohort creation by `InitPRTObject` (`biogeochem/EDCohortDynamicsMod.F90:293`), driven by the `hlm_parteh_mode` configuration flag.

### Hypothesis Selection Constants

The selection constants are declared in `parteh/PRTGenericMod.F90:69-70`:

```fortran
integer, parameter, public :: prt_carbon_allom_hyp   = 1
integer, parameter, public :: prt_cnp_flex_allom_hyp = 2
```

Each hypothesis module allocates its own singleton mapping object and points the module-level `prt_global` pointer at it. For example, `PRTAllometricCarbonMod.F90:160` declares `class(prt_global_type), public, target, allocatable :: prt_global_ac` and line 251 sets `prt_global => prt_global_ac`. The CNP equivalent is in `PRTAllometricCNPMod.F90:278` (`prt_global_acnp`) and `:361`.

See [PARTEH Extensibility Framework](parteh_framework.md) for the variable-registration pattern, the `sp_organ_map` lookup, and how to add a new hypothesis.

## Module Organization Patterns

### Functional Separation and Layering

FATES source files are organized by functional responsibility under directories `main/`, `biogeochem/`, `biogeophys/`, `fire/`, and `parteh/` (see [Module Organization](modules.md) for the full directory inventory and the role of each). The layering runs roughly:

```
FatesInterfaceMod (main/)          ← HLM coupling, daily/sub-daily entry points
    │
    ├── EDMainMod (main/)           ← daily dynamics orchestration
    │      └── ed_ecosystem_dynamics (main/EDMainMod.F90:141)
    │
    ├── EDPhysiologyMod (biogeochem/)   ← phenology, recruitment, trim, litter
    │
    ├── EDPatchDynamicsMod (biogeochem/)  ← disturbance, patch create/fuse/terminate
    │
    ├── EDCohortDynamicsMod (biogeochem/) ← cohort create, terminate, fuse
    │
    └── PARTEH (parteh/)            ← allocation and reactive transport
```

### Naming Conventions

| Pattern | Purpose | Examples |
| --- | --- | --- |
| `ED*Mod.F90` | Ecosystem-demography core logic (historical naming) | `EDMainMod.F90`, `EDPhysiologyMod.F90`, `EDCohortDynamicsMod.F90` |
| `Fates*Mod.F90` | FATES-specific modules (newer naming) | `FatesInterfaceMod.F90`, `FatesAllometryMod.F90`, `FatesCohortMod.F90`, `FatesPatchMod.F90` |
| `PRT*Mod.F90` | PARTEH allocation system | `PRTGenericMod.F90`, `PRTAllometricCarbonMod.F90`, `PRTAllometricCNPMod.F90` |
| `SF*Mod.F90` | SPITFIRE fire model | `SFMainMod.F90`, `SFParamsMod.F90` |
| `*TypesMod.F90` | Type definitions only | `EDTypesMod.F90`, `FatesInterfaceTypesMod.F90` |
| `*ParamsMod.F90` | Parameter definition/storage | `EDParamsMod.F90`, `SFParamsMod.F90`, `PRTParametersMod.F90` |

## Parameter System Architecture

### Two-Phase Parameter Loading

Parameter reading is driven by `FatesReadParameters` in `main/FatesInterfaceMod.F90:2399-2428`, which is called from `SetFatesGlobalElements1` (`main/FatesInterfaceMod.F90:737-804`). After parameters are read, `FatesReportParameters` (`main/FatesInterfaceMod.F90:1964`) logs the active values.

Parameters are stored in singleton instances:

- PFT parameters: `EDPftvarcon_inst` of type `EDPftvarcon_type`, declared in `main/EDPftvarcon.F90:290`.
- PARTEH parameters: `prt_params` of type `prt_param_type`, declared in `parteh/PRTParametersMod.F90:188`.
- Global scalars: `EDParamsMod.F90` (e.g., `nclmax`, `nlevleaf`, `maxpft`, `maxSWb`).
- Fire parameters: singleton in `fire/SFParamsMod.F90`.

All are read-only after initialization and accessed from any module via `use` statements.

## Type-Bound Procedure Pattern

FATES uses Fortran 2003 type-bound procedures (TBPs) to attach methods to derived types.

The type-bound procedures declared on `fates_cohort_type` (`biogeochem/FatesCohortMod.F90:275-284`) are:

```fortran
contains
    procedure :: Init
    procedure :: NanValues
    procedure :: ZeroValues
    procedure :: Create
    procedure :: Copy
    procedure :: FreeMemory
    procedure :: CanUpperUnder
    procedure :: InitPRTBoundaryConditions
    procedure :: UpdateCohortBioPhysRates
    procedure :: Dump
```

Usage examples from inside the codebase include `call currentCohort%Dump()` for diagnostic printing and `call newCohort%Copy(donor)` during patch spawning. Note that cohort fusion and termination are not type-bound procedures: `fuse_cohorts`, `create_cohort`, `terminate_cohorts`, and `terminate_cohort` are all module-level public subroutines in `biogeochem/EDCohortDynamicsMod.F90` (at lines 694, 160, 347, and 464 respectively).

Similarly, `fates_patch_type` declares its TBPs in `biogeochem/FatesPatchMod.F90:222-230` (`Init`, `NanValues`, `ZeroValues`, `InitRunningMeans`, `InitLitter`, `Create`, `FreeMemory`, `Dump`, `CheckVars`).

Advantages of the TBP pattern:

- Methods live with the data they operate on (encapsulation).
- Namespace is managed by the type (`cohort%Dump` vs. a free-floating `Dump`).
- Polymorphism is supported: base-class methods can be overridden by extended types, as in PARTEH (`DailyPRT => DailyPRTAllometricCarbon` in `parteh/PRTAllometricCarbonMod.F90:140`).

## Pointer vs Allocatable Arrays

FATES uses Fortran pointers for self-referential linked-list types and allocatable arrays for fixed-size contiguous buffers. Patch and cohort linked-list fields are declared `type(...), pointer` (for example `taller`, `shorter` in `biogeochem/FatesCohortMod.F90:63-64`, and `older`, `younger`, `tallest`, `shortest` in `biogeochem/FatesPatchMod.F90:38-41`). Boundary-condition arrays on the interface type are declared `type(...), allocatable` (e.g., `bc_in(:)` at `main/FatesInterfaceMod.F90:143`).

Rationale:

- Pointers are required for self-referential types and support a null state via `null()` and `associated()`.
- Allocatables offer better performance for contiguous arrays and give automatic deallocation on scope exit.

## Mass Balance Checking Pattern

FATES uses ubiquitous mass-balance checks as a defensive-programming discipline. On the PARTEH side, the base-class routine `CheckMassConservation` is declared `non_overridable` on `prt_vartypes` (`parteh/PRTGenericMod.F90:266`) and implemented at `parteh/PRTGenericMod.F90:946-1011`. It verifies, per variable and per position, that

```
val - val0  ==  net_alloc + turnover + burned + damaged  (within tolerance)
```

using the state-and-flux fields described in [PARTEH Extensibility Framework](parteh_framework.md). Because the routine is `non_overridable`, every hypothesis inherits it automatically, and new hypotheses cannot accidentally weaken the mass-balance contract.

## Summary of Design Patterns

| Pattern | Implementation | Purpose |
| --- | --- | --- |
| Strategy | `prt_vartypes` base + `callom_prt_vartypes` / `cnp_allom_prt_vartypes` extensions | Swappable allocation algorithms |
| Singleton | `prt_global` (PRTGenericMod.F90:395), `EDPftvarcon_inst`, `prt_params` | Shared read-only parameter and mapping state |
| Linked List | Patches (age-ordered), cohorts (height-ordered) | Dynamic vegetation structure |
| Two-Phase Init | Register variables → receive parameters | Flexible parameter loading |
| Boundary Condition | `bc_in`, `bc_out`, `bc_pconst` | Clean separation of HLM coupling channels |
| Template Method | `DailyPRT` / `FastPRT` base-to-override | Algorithm skeleton with hypothesis-specific steps |
| Defensive Mass Balance | `CheckMassConservation` (non_overridable TBP) | Runtime conservation enforcement |

Sources: files listed in each section, and the directory inventory under `main/`, `biogeochem/`, `biogeophys/`, `fire/`, and `parteh/`.
