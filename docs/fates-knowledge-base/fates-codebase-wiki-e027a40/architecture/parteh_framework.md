---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# PARTEH Extensibility Framework

## Purpose and Scope

This document describes the extensibility architecture of the Plant Allocation and Reactive Transport Extensible Hypotheses (PARTEH) framework at commit `e027a40` (tag `sci.1.91.1_api.43.1.0`). PARTEH is designed as a pluggable subsystem that allows multiple allocation hypotheses to coexist in a single FATES build, enabling scientific experimentation with different theories of plant carbon and nutrient allocation.

This page focuses on the framework design and on how to add a new allocation hypothesis. For an overview of how PARTEH fits into the rest of FATES, see [Code Architecture and Design Patterns](index.md). For the two existing hypotheses (carbon-only and CNP), consult `parteh/PRTAllometricCarbonMod.F90` and `parteh/PRTAllometricCNPMod.F90` directly.

## Core Design Principles

PARTEH implements a polymorphic object-oriented framework in Fortran 2003:

- A base type `prt_vartypes` defines the data layout and the procedure interface shared by every hypothesis.
- Each hypothesis is a separate module that extends the base type.
- Each cohort holds a polymorphic `class(prt_vartypes), pointer` to whichever concrete type is active for the run.
- A module-level singleton `prt_global` holds variable-registration metadata and is repointed at the active hypothesis during initialization.

Sources: `parteh/PRTGenericMod.F90:232-396`.

## Class Hierarchy

The base type `prt_vartypes` is declared at `parteh/PRTGenericMod.F90:232-278`. Its data members are `variables(:)` (allocatable array of `prt_vartype` — state and flux arrays), plus three boundary-condition arrays `bc_inout(:)`, `bc_in(:)`, `bc_out(:)` of type `prt_bctype`, and a scalar `ode_opt_step`.

The contained procedures split into two groups. Four extendable procedures have stub base implementations that each hypothesis is expected to override (`parteh/PRTGenericMod.F90:245-248`): `DailyPRT => DailyPRTBase`, `FastPRT => FastPRTBase`, `DamageRecovery => DamageRecoveryBase`, and `GetNutrientTarget => GetNutrientTargetBase`. The remaining procedures are declared `non_overridable` and shared across all hypotheses (`parteh/PRTGenericMod.F90:252-270`):

```
InitAllocate, InitPRTVartype, FlushBCs,
InitializeInitialConditions, CheckInitialConditions,
RegisterBCIn, RegisterBCOut, RegisterBCInout,
GetState, GetBiomass, GetTurnover, GetBurned, GetHerbivory, GetNetAlloc,
ZeroRates, CheckMassConservation,
DeallocatePRTVartypes, WeightedFusePRTVartypes, CopyPRTVartypes
```

`AgeLeaves` (declared at `:273` without `non_overridable`) is generic but leaves the door open for a hypothesis-specific override. Two new accessors at e027a40 are `GetBiomass` (declaration at `:261`, implementation at `parteh/PRTGenericMod.F90:1062-1089`) and `GetHerbivory` (declaration at `:264`, implementation at `:1169-1198`); both are `non_overridable`.

`prt_vartypes` is not declared with the Fortran `abstract` keyword. It is abstract in intent only: the default implementations of `DailyPRT`, `FastPRT`, and `DamageRecovery` are stub routines that call `endrun` with messages such as "Daily PRT Allocation must be extended" (`parteh/PRTGenericMod.F90:1258-1289`). `GetNutrientTargetBase` similarly aborts with a message at `:1419-1433`. Any hypothesis that fails to override these procedures aborts the run the first time allocation or nutrient targeting is attempted.

### Nested Data Types

Two smaller types are referenced by `prt_vartypes`:

- `prt_vartype` (`parteh/PRTGenericMod.F90:179-199`) — holds the mass state and fluxes for one plant pool. At e027a40 this includes a new `herbivory(:)` field at `:192`.
- `prt_bctype` (`parteh/PRTGenericMod.F90:208-213`) — holds a scalar-pointer pair (`rval`, `ival`) used to register boundary conditions by reference.

### Existing Hypotheses

Two concrete hypothesis modules extend `prt_vartypes`:

| Hypothesis | Type | Source | Hypothesis constant |
| --- | --- | --- | --- |
| Carbon-only allometric | `callom_prt_vartypes` | `parteh/PRTAllometricCarbonMod.F90:136-143` | `prt_carbon_allom_hyp = 1` |
| CNP flexible allometric | `cnp_allom_prt_vartypes` | `parteh/PRTAllometricCNPMod.F90:254-270` | `prt_cnp_flex_allom_hyp = 2` |

Both constants are declared at `parteh/PRTGenericMod.F90:69-70`.

The carbon-only extension overrides `DailyPRT` (renamed `DailyPRTAllometricCarbon`) and `FastPRT` (renamed `FastPRTAllometricCarbon`) at `parteh/PRTAllometricCarbonMod.F90:140-141`. The CNP extension additionally overrides `GetNutrientTarget` (`parteh/PRTAllometricCNPMod.F90:260` → `GetNutrientTargetCNP`) and adds CNP-specific procedures `CNPPrioritizedReplacement`, `CNPStatureGrowth`, `EstimateGrowthNC`, `CNPAdjustFRootTargets`, `CNPAllocateRemainder`, `GetDeficit`, and `TrimFineRoot` (`parteh/PRTAllometricCNPMod.F90:263-269`).

Each cohort holds a polymorphic pointer to the active object:

```fortran
class(prt_vartypes), pointer :: prt
```

declared at `biogeochem/FatesCohortMod.F90:71`.

## Variable Organization System

### Organs and Elements

PARTEH uses a standardized taxonomy of plant organs and chemical elements. The integer IDs are declared as module parameters at `parteh/PRTGenericMod.F90:78-107`:

| ID | Organ | ID | Element |
| --- | --- | --- | --- |
| 1 | `leaf_organ` | 1 | `carbon12_element` |
| 2 | `fnrt_organ` (fine root) | 2 | `carbon13_element` |
| 3 | `sapw_organ` (sapwood) | 3 | `carbon14_element` |
| 4 | `store_organ` (storage) | 4 | `nitrogen_element` |
| 5 | `repro_organ` (reproductive) | 5 | `phosphorus_element` |
| 6 | `struct_organ` (dead structure) | 6 | `potassium_element` |

`num_organ_types = 6` at `parteh/PRTGenericMod.F90:78` and `num_element_types = 6` at `:93`. ID 0 on either axis is reserved for "all" or "irrelevant".

### Variable Registration and the sp_organ_map Table

Each hypothesis registers its variables by `(organ_id, element_id)` tuple. Registration uses `RegisterVarInGlobal` (`parteh/PRTGenericMod.F90:448-484`), which writes into the mapping table on `prt_global_type`, declared at `parteh/PRTGenericMod.F90:366` as

```fortran
integer, dimension(0:num_organ_types, 0:num_element_types) :: sp_organ_map
```

A lookup like `prt_global%sp_organ_map(leaf_organ, carbon12_element)` returns the variable index for leaf carbon under the active hypothesis.

In the CNP hypothesis, `InitPRTGlobalAllometricCNP` (`parteh/PRTAllometricCNPMod.F90:293-368`) calls `RegisterVarInGlobal` 18 times — six organ-carbon pairs, six organ-nitrogen pairs, and six organ-phosphorus pairs (lines 336-355). The carbon-only hypothesis (`parteh/PRTAllometricCarbonMod.F90:169-255`) registers only the six carbon variables (lines 237-242).

The conceptual layout of the mapping table:

|                  | Carbon (1) | Nitrogen (4) | Phosphorus (5) |
| --- | --- | --- | --- |
| Leaf (1)         | `leaf_c_id`   | `leaf_n_id`   | `leaf_p_id`   |
| Fine Root (2)    | `fnrt_c_id`   | `fnrt_n_id`   | `fnrt_p_id`   |
| Sapwood (3)      | `sapw_c_id`   | `sapw_n_id`   | `sapw_p_id`   |
| Storage (4)      | `store_c_id`  | `store_n_id`  | `store_p_id`  |
| Reproduction (5) | `repro_c_id`  | `repro_n_id`  | `repro_p_id`  |
| Structure (6)    | `struct_c_id` | `struct_n_id` | `struct_p_id` |

In the CNP hypothesis all 18 slots are populated; in the carbon-only hypothesis only the first column is populated and N/P columns stay zero. Index 0 on either axis is reserved for "all" or "irrelevant".

## State Variables and Boundary Conditions

### State Variables (`prt_vartype`)

`prt_vartype` holds the per-pool mass state and fluxes (`parteh/PRTGenericMod.F90:179-199`):

| Field | Type | Meaning |
| --- | --- | --- |
| `val(:)` | `real(r8), pointer` | Instantaneous state [kg] |
| `val0(:)` | `real(r8), allocatable` | State at start of control period [kg] |
| `net_alloc(:)` | `real(r8), allocatable` | Net allocation/transport over control period [kg] |
| `turnover(:)` | `real(r8), allocatable` | Losses to litter [kg] |
| `burned(:)` | `real(r8), allocatable` | Losses to fire [kg] |
| `damaged(:)` | `real(r8), allocatable` | Losses to damage [kg] |
| `herbivory(:)` | `real(r8), allocatable` | Losses to herbivory [kg] (NEW at e027a40) |

The control period is typically one day. Mass conservation must hold per pool:

```
val - val0  ==  net_alloc + turnover + burned + damaged + herbivory   (within tolerance)
```

This relationship is enforced automatically by `CheckMassConservation` (`parteh/PRTGenericMod.F90:954-1021`), which is a `non_overridable` TBP on `prt_vartypes` (declared at `parteh/PRTGenericMod.F90:267`). Because it is `non_overridable`, a hypothesis cannot accidentally weaken or skip the mass-balance check.

### Boundary Condition Channels

`prt_vartypes` exposes three boundary condition channels built from `prt_bctype` pointers (`parteh/PRTGenericMod.F90:235-237`):

- `bc_in(:)` — read-only inputs (e.g., PFT index, canopy trim, leaf phenology status).
- `bc_inout(:)` — read + write state (e.g., DBH, carbon balance).
- `bc_out(:)` — write-only outputs (e.g., nutrient efflux, limitation factors).

These are registered by the hypothesis modules through `RegisterBCIn`, `RegisterBCInout`, and `RegisterBCOut` (all declared `non_overridable` at `parteh/PRTGenericMod.F90:257-259`). The cohort passes pointers to the actual underlying scalars, so the PARTEH object reads and writes cohort state without copies.

## The `prt_global` Singleton

The module-level pointer `class(prt_global_type), pointer, public :: prt_global` is declared at `parteh/PRTGenericMod.F90:396`. Each hypothesis owns its own allocatable `prt_global_type` instance and repoints `prt_global` at it during initialization:

- Carbon-only: `prt_global_ac` declared at `parteh/PRTAllometricCarbonMod.F90:160`, allocated and populated inside `InitPRTGlobalAllometricCarbon` (`:169-255`), then `prt_global => prt_global_ac` at `:251`.
- CNP: `prt_global_acnp` declared at `parteh/PRTAllometricCNPMod.F90:282`, allocated at `:310`, then `prt_global => prt_global_acnp` at `:365`.

Because both concrete instances and `prt_global` are class pointers, downstream code that uses `prt_global%sp_organ_map(...)` or `prt_global%num_vars` does not need to know which hypothesis is active.

## Integration with FATES

### Object Instantiation

Each cohort's `prt` member is declared as `class(prt_vartypes), pointer :: prt` at `biogeochem/FatesCohortMod.F90:71`, and is allocated and typed by `InitPRTObject` (`biogeochem/EDCohortDynamicsMod.F90:230-279`), which selects the concrete type based on `hlm_parteh_mode` (a `select case` at `biogeochem/EDCohortDynamicsMod.F90:253` dispatches between the two hypothesis constants). After allocation, `InitPRTBoundaryConditions` (a type-bound procedure on `fates_cohort_type`, declared at `biogeochem/FatesCohortMod.F90:297`) registers the per-cohort boundary conditions on the object.

### Call Sequence During Dynamics

During the daily dynamics loop, the host walks the patch/cohort linked lists and invokes `cohort%prt%DailyPRT(phase)` on each cohort (dispatched to either `DailyPRTAllometricCarbon` or `DailyPRTAllometricCNP` through Fortran polymorphism). The `phase` argument lets a hypothesis split work into subphases — at present, Phase 1 is the main allocation logic applied to all cohorts and Phase 2 is the damage module integration (only if tree damage is enabled). The interface admits additional phases in the future.

At sub-daily cadence, the equivalent entry point is `FastPRT` (carbon: `FastPRTAllometricCarbon` at `parteh/PRTAllometricCarbonMod.F90:1256-1267`; CNP: `FastPRTAllometricCNP` at `parteh/PRTAllometricCNPMod.F90:2019-2029`).

## Generic Helper Functions

### State Access

`GetState`, `GetBiomass`, `GetTurnover`, `GetBurned`, `GetHerbivory`, and `GetNetAlloc` are non_overridable functions on `prt_vartypes` (declarations at `parteh/PRTGenericMod.F90:260-265`). Implementations:

| Function | Implementation |
| --- | --- |
| `GetState` | `parteh/PRTGenericMod.F90:1025-1058` |
| `GetBiomass` | `parteh/PRTGenericMod.F90:1062-1089` (NEW at e027a40) |
| `GetTurnover` | `parteh/PRTGenericMod.F90:1094-1129` |
| `GetBurned` | `parteh/PRTGenericMod.F90:1133-1165` |
| `GetHerbivory` | `parteh/PRTGenericMod.F90:1169-1198` (NEW at e027a40) |
| `GetNetAlloc` | `parteh/PRTGenericMod.F90:1202-1235` |

They let any caller retrieve pool values by `(organ_id, element_id, position_id)` — `GetState` returns `val(position_id)`, `GetTurnover` returns `turnover(position_id)`, and so on. Each function translates `(organ_id, element_id)` to a variable index through `prt_global%sp_organ_map`, then reads the corresponding entry in the per-plant `variables(:)` array. The write-side counterpart `SetState` (`parteh/PRTGenericMod.F90:1292-1341`) is a module-level subroutine used for initialization with the same lookup pattern.

### Mass Balance Checking

`CheckMassConservation` (`parteh/PRTGenericMod.F90:954-1021`) walks the `variables(:)` array and verifies per-pool mass closure including the new herbivory flux. Because it is `non_overridable`, the conservation contract cannot be weakened by a derived type.

## Loss Flux Handling

`parteh/PRTLossFluxesMod.F90` provides generic helpers for loss events — turnover (deciduous leaf fall, fine-root turnover), burn losses, damage losses, herbivory losses — that work across all hypotheses by using the organ/element ID translation. Retranslocation (e.g., nitrogen and phosphorus recovered from senescing leaves and fine roots) is handled within these helpers so that hypothesis modules do not duplicate the retranslocation bookkeeping.

## Parameter Requirements

Each hypothesis uses parameters from the FATES parameter file (now JSON; loaded via `JSONParameterUtilsMod` and dispatched by `FatesTransferParameters` — see [Module Organization](modules.md)) and reads them via the singleton `prt_params` (of type `prt_param_type`, declared at `parteh/PRTParametersMod.F90:195`). Allocation routines access values such as stoichiometric ratios and turnover rates through `prt_params%...`. The CNP hypothesis additionally consumes parameters related to nutrient targets, retranslocation fractions, and root prioritization.

## Adding a New Hypothesis

To add a new allocation hypothesis, following the pattern established by `PRTAllometricCarbonMod.F90` and `PRTAllometricCNPMod.F90`:

| Step | Action | Files |
| --- | --- | --- |
| 1 | Create a new module under `parteh/`, modeled after `PRTAllometricCarbonMod.F90` and `PRTAllometricCNPMod.F90` | `parteh/` |
| 2 | Add a new hypothesis ID constant next to `prt_carbon_allom_hyp` and `prt_cnp_flex_allom_hyp` | `parteh/PRTGenericMod.F90:69-70` |
| 3 | Declare a type `extends(prt_vartypes)` and a `prt_global_type` singleton | Your module |
| 4 | Implement `InitPRTGlobalMyHypothesis` that calls `RegisterVarInGlobal` for each variable and repoints `prt_global` | Your module |
| 5 | Override `DailyPRT`, `FastPRT`, and (if tracking nutrients) `GetNutrientTarget` | Your module |
| 6 | Add a case for the new mode to `InitPRTObject` | `biogeochem/EDCohortDynamicsMod.F90:230` (`select case` at `:253`) |
| 7 | Call `InitPRTGlobalMyHypothesis` from host model startup | `main/FatesInterfaceMod.F90` |
| 8 | Add parameter entries to the JSON parameter file and the parameter transfer pipeline | `parameter_files/`, `parteh/PRTParametersMod.F90`, `parteh/PRTParamsFATESMod.F90`, `main/JSONParameterUtilsMod.F90`, `main/FatesInterfaceMod.F90:2675-2694` (`FatesTransferParameters`) |
| 9 | Add namelist options and tests | Host model, `functional_unit_testing/`, `testing/` |

Because the base-class stubs (`DailyPRTBase`, `FastPRTBase`, `DamageRecoveryBase`, `GetNutrientTargetBase`) all call `endrun` and `CheckMassConservation` is `non_overridable`, a new hypothesis will either run with full mass conservation or abort immediately on the first call to an unimplemented procedure.

Sources: `parteh/PRTGenericMod.F90:69-396`, `parteh/PRTGenericMod.F90:1258-1289` (Daily/Fast/DamageRecovery stubs), `parteh/PRTGenericMod.F90:1419-1433` (`GetNutrientTargetBase` stub), `parteh/PRTGenericMod.F90:954-1021` (mass balance), `parteh/PRTAllometricCarbonMod.F90:136-255`, `parteh/PRTAllometricCNPMod.F90:254-368`, `biogeochem/FatesCohortMod.F90:71`, `biogeochem/EDCohortDynamicsMod.F90:230-279`, `parteh/PRTLossFluxesMod.F90`, `parteh/PRTParametersMod.F90:195`.
