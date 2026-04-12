# PARTEH: Plant Allocation System

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `parteh/PRTGenericMod.F90`
- `parteh/PRTAllometricCarbonMod.F90`
- `parteh/PRTAllometricCNPMod.F90`
- `parteh/PRTLossFluxesMod.F90`
- `parteh/PRTParamsFATESMod.F90`
- `parteh/PRTParametersMod.F90`
- `main/FatesConstantsMod.F90`
- `main/EDMainMod.F90`
- `biogeochem/EDPhysiologyMod.F90`
- `biogeochem/EDCohortDynamicsMod.F90`
- `biogeochem/FatesSoilBGCFluxMod.F90`

## Purpose and Scope

PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses) is FATES' framework for managing plant carbon (and optionally nitrogen and phosphorus) allocation and the associated loss fluxes. It is intentionally built as an extensible object system: a common `prt_vartypes` base class defines state, boundary conditions, and mass-conservation bookkeeping; hypothesis modules (`PRTAllometricCarbonMod`, `PRTAllometricCNPMod`) extend it with their daily allocation algorithm.

This page covers:

- The class hierarchy, state-variable model, and boundary-condition plumbing
- The two available allocation hypotheses and when each is selected
- Where in the daily loop PARTEH runs and how it is called
- Loss fluxes (maintenance turnover, deciduous drop, phenology flush, burn, damage) and their retranslocation wiring
- Nutrient acquisition interface at a high level (detail is in the companion docs)

See [Carbon-Only Allocation](./carbon_only.md), [CNP Allocation and Nutrient Dynamics](./cnp_allocation.md), and [Soil-Plant Nutrient Interface](./soil_plant_interface.md) for the per-hypothesis details.

## Architecture

### Allocation Hypotheses

Two hypothesis identifiers are defined at `PRTGenericMod.F90:69-70`:

```fortran
integer, parameter, public :: prt_carbon_allom_hyp   = 1
integer, parameter, public :: prt_cnp_flex_allom_hyp = 2
```

The host model selects one via `hlm_parteh_mode`. `InitPRTObject()` (in `EDCohortDynamicsMod`) allocates the corresponding extended class for each new cohort.

| Aspect | Carbon-Only (`prt_carbon_allom_hyp`) | CNP Flexible (`prt_cnp_flex_allom_hyp`) |
|---|---|---|
| Class | `callom_prt_vartypes` | `cnp_allom_prt_vartypes` |
| Module | `PRTAllometricCarbonMod` | `PRTAllometricCNPMod` |
| State variables | 6 C pools × organs (leaf age-stratified) | 18 pools (6 organs × 3 elements) |
| Nutrient limitation | None | N and P can limit growth via equivalent-C method |
| Leaf-to-fine-root ratio | Fixed parameter `allom_l2fr` | Dynamic via PID controller |
| Stoichiometry | Implicit (not tracked) | Explicit, per organ, with growth-min targets |
| Exudation | None | C/N/P can be exuded when in excess |
| Retranslocation | None (`retrans = 0` for C) | N and P re-absorbed into storage on turnover |

Sources: `(parteh/PRTGenericMod.F90:69-70)`, `(parteh/PRTAllometricCarbonMod.F90:1-90)`, `(parteh/PRTAllometricCNPMod.F90:1-90)`

### Class Hierarchy and Extended Methods

`prt_vartypes` is the base (`PRTGenericMod.F90:233-277`). It holds:

- `variables(:)` — state variables (each is a `prt_vartype` with `val`, `val0`, `net_alloc`, `turnover`, `burned`, `damaged`)
- `bc_in(:)`, `bc_inout(:)`, `bc_out(:)` — boundary condition arrays

Overridable type-bound procedures (each hypothesis provides its own implementation):

| Procedure | Role |
|---|---|
| `DailyPRT(phase)` | Daily allocation entry point |
| `FastPRT` | Fast-timestep processes (empty stub in both hypotheses) |
| `DamageRecovery` | Damage-module specific |
| `GetNutrientTarget` | Per-organ, per-element target mass |

Generic non-overridable procedures (`InitAllocate`, `InitPRTVartype`, `RegisterBCIn`, `GetState`, `SetState`, `CheckMassConservation`, `WeightedFusePRTVartypes`, etc.) operate on any hypothesis.

Sources: `(parteh/PRTGenericMod.F90:233-277)`

### State Variable Model

Every plant pool (e.g. leaf carbon, fine-root nitrogen) is a `prt_vartype` that tracks:

- `val(:)` — current mass, kg
- `val0(:)` — mass at the start of the control period
- `net_alloc(:)` — cumulative allocation flux over the period (kg)
- `turnover(:)` — cumulative turnover loss over the period (kg)
- `burned(:)`, `damaged(:)` — cumulative losses to disturbance

Mass-balance constraint, checked by `CheckMassConservation` in `PRTGenericMod`:

```
val ≈ val0 + net_alloc − turnover − burned − damaged
```

Leaves are the only pool with multiple positions (`icd = 1..max_nleafage`, typically 4). Every allocation flux is added at position 1 (the youngest age class); `AgeLeaves` rotates leaves between age classes.

Sources: `(parteh/PRTGenericMod.F90:179-200)`, `(parteh/PRTGenericMod.F90:146)` (`max_nleafage`)

### Organs and Elements

| Organ ID | Name | Purpose |
|---|---|---|
| 1 | `leaf_organ` | Photosynthetic tissue, age-stratified |
| 2 | `fnrt_organ` | Fine roots, nutrient uptake surface |
| 3 | `sapw_organ` | Sapwood (live wood, transport) |
| 4 | `store_organ` | Non-structural C/N/P reserves |
| 5 | `repro_organ` | Seeds, fruits |
| 6 | `struct_organ` | Dead structural biomass (heartwood + structure) |

| Element ID | Name |
|---|---|
| 1 | `carbon12_element` |
| 4 | `nitrogen_element` |
| 5 | `phosphorus_element` |

The global `prt_global%sp_organ_map(organ, element)` mapping lets hypothesis-neutral routines look up a variable index from an organ/element pair.

Sources: `(parteh/PRTGenericMod.F90:78-108)`, `(parteh/PRTGenericMod.F90:354-392)`

## Daily Call Sequence

For each cohort, during `EDMainMod::ed_integrate_state_variables`, the following happens **before** any `DailyPRT` call:

```
1. call PRTMaintTurnover(prt, ft, is_drought)                    [EDMainMod.F90:535]
     └── maintenance turnover + retranslocation into storage
2. daily_n_gain = daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily   [EDMainMod.F90:550-551]
3. daily_p_gain already set (from UnPackNutrientAquisitionBCs)
```

Then `DailyPRT` is called three times with `phase = 1, 2, 3`:

```fortran
if (.not. newly_recovered) call prt%DailyPRT(phase=1)   [EDMainMod.F90:582]
call prt%DailyPRT(phase=2)                              [EDMainMod.F90:585]
  ...
call prt%DailyPRT(phase=3)                              [EDMainMod.F90:601]
```

**Important:** The three `DailyPRT(phase)` calls exist to accommodate the damage module, which does not yet interoperate with CNP. The behavior is:

- **Carbon-only hypothesis** (`DailyPRTAllometricCarbon`): dispatches on `phase` via `select case (phase)` with three branches `case(1)`, `case(2)`, `case(3)`. See [Carbon-Only Allocation](./carbon_only.md).
- **CNP hypothesis** (`DailyPRTAllometricCNP`): `if (phase .ne. 1) return` at line 433. All three internal CNP allocation steps (Prioritized Replacement → Stature Growth → Allocate Remainder) execute inside the single `phase=1` call, via sequential calls to the three `CNP*` routines. The `phase=2` and `phase=3` invocations are no-ops for CNP.

Do not confuse the `phase` argument with the "three-step CNP allocation"; they are unrelated concepts that share a word.

The deciduous leaf-drop path runs elsewhere in the daily loop, inside `EDPhysiologyMod::phenology` at `EDPhysiologyMod.F90:1736-1747`, which calls `PRTDeciduousTurnover` and `PRTPhenologyFlush` **outside** of `DailyPRT`.

Sources: `(main/EDMainMod.F90:530-615)`, `(parteh/PRTAllometricCNPMod.F90:430-433)`, `(biogeochem/EDPhysiologyMod.F90:1690-1749)`

## Loss Fluxes (`PRTLossFluxesMod`)

`PRTLossFluxesMod.F90` provides six public routines:

| Routine | Trigger | Retranslocation? |
|---|---|---|
| `PRTMaintTurnover` | Daily, inside `ed_integrate_state_variables`, before `DailyPRT` | Yes (evergreen) |
| `PRTDeciduousTurnover` | Leaf-drop event, inside `phenology` | Yes (deciduous) |
| `PRTPhenologyFlush` | Leaf-flush event, inside `phenology`, transfers storage → leaves/fnrt | n/a (flush, not loss) |
| `PRTBurnLosses` | Fire, non-lethal losses | No |
| `PRTDamageLosses` | Damage module | No |
| `PRTReproRelease` | Seed dispersal | No |

Turnover mass is tracked separately from damage/burn mass in the `turnover(:)`, `burned(:)`, `damaged(:)` fields of each `prt_vartype`, so the mass-balance diagnostic can apportion losses correctly.

### Retranslocation

Both `PRTMaintTurnover` (evergreen maintenance) and `PRTDeciduousTurnover` (event drop) use the same retranslocation formula:

```
turnover_mass       = (1 - retrans) * base_turnover * val(i_pos)
retranslocated_mass =  retrans      * base_turnover * val(i_pos)

val(i_pos)                        -= (turnover_mass + retranslocated_mass)
turnover(i_pos)                   += turnover_mass
val(store_var, 1)                 += retranslocated_mass
net_alloc(store_var, 1)           += retranslocated_mass
```

For carbon, `retrans = 0` always. For nitrogen, `retrans = prt_params%turnover_nitr_retrans(ipft, organ_param_id(organ))`. Phosphorus is analogous. The parameter validation in `PRTParamsFATESMod.F90:1316-1365` requires retranslocation to be exactly **zero** for sapwood and structure and in `[0, 1]` for other organs.

Because `PRTMaintTurnover` runs **before** `DailyPRT` within the same daily timestep, the retranslocated nutrient accumulates in the storage pool before the CNP allocation routine reads it. `DailyPRTAllometricCNP` then drains all nutrient storage into the day's `n_gain`/`p_gain` pool as its first action (`PRTAllometricCNPMod.F90:534-542`), so retranslocated mass is implicitly available for same-day re-allocation.

Sources: `(parteh/PRTLossFluxesMod.F90:503-870)`, `(parteh/PRTParamsFATESMod.F90:1316-1365)`, `(parteh/PRTAllometricCNPMod.F90:534-542)`

## Nutrient Acquisition Interface (Summary)

FATES plants acquire N and P through `FatesSoilBGCFluxMod`, which is called before `DailyPRT`:

- `PrepNutrientAquisitionBCs(csite, bc_in, bc_out)` — writes the root biomass profile and decomposer estimate (if using ECA) into `bc_out`, and sets `bc_out%num_plant_comps` (the competitor count).
- `UnPackNutrientAquisitionBCs(sites, bc_in)` — reads the host's `plant_nh4_uptake_flux`, `plant_no3_uptake_flux`, `plant_p_uptake_flux` arrays back onto each cohort's `daily_nh4_uptake`, `daily_no3_uptake`, `daily_p_gain`.

Two independent knobs govern how FATES passes nutrients to and from the host soil BGC model:

### Decomposer Math: `hlm_nu_com`

This is a string setting that the host model sets to `"RD"` (Relative Demand) or `"ECA"` (Equilibrium Chemistry Approximation).

- **RD**: Nutrient partitioning is proportional to plant demand. `bc_out%decompmicc` is not populated.
- **ECA**: FATES must also provide a decomposer microbial biomass estimate per soil layer, using a depth-attenuation function parameterized by `EDPftvarcon_inst%decompmicc(pft)`, `decompmicc_lambda = 2.5`, `decompmicc_zmax = 0.07 m`.

This is the decomposer-competition math in the host. It is **independent** of the competitor-count setting below.

### Competitor Count: `fates_np_comp_scaling`

This integer flag is defined in `FatesConstantsMod.F90:94-125` and controls how many plant "competitors" FATES hands to the host BGC:

| Value | Name | Competitor count |
|---|---|---|
| 1 | `coupled_np_comp_scaling` | One competitor per cohort (`bc_out%num_plant_comps = total_cohorts`) |
| 2 | `trivial_np_comp_scaling` | One competitor total (all plants pooled) |

Under RD, if `fates_np_comp_scaling == trivial_np_comp_scaling`, `PrepNutrientAquisitionBCs` takes a fast path at `FatesSoilBGCFluxMod.F90:440-446` that sets `num_plant_comps = 1` and returns early. Under ECA, and for all coupled-scaling cases, the full cohort loop runs (lines 453-515). **Coupled scaling with RD is a valid configuration**, and ECA honors both scaling choices. The old wiki conflated these two axes into a single column.

### Uptake Mode: `n_uptake_mode` / `p_uptake_mode`

Orthogonal to the above. These are set in `EDParamsMod` and take values `prescribed_n_uptake` (or `_p_uptake`) or `coupled_n_uptake` (or `_p_uptake`).

- **Prescribed**: `daily_nh4_uptake = fnrt_c * vmax_nh4 * prescribed_nuptake * sec_per_day`, no feedback from host soil BGC. Inside `DailyPRTAllometricCNP`, the day's n_gain is overwritten to 1e3 kg (effectively unlimited) and the amount actually used is reported back on the same BC (`PRTAllometricCNPMod.F90:470-475, 688-697`).
- **Coupled**: `daily_nh4_uptake = bc_in%plant_nh4_uptake_flux(icomp, 1) * kg_per_g * AREA / ccohort%n`, comes from the host BGC.

P is analogous. Note: `UnPackNutrientAquisitionBCs` reuses `prescribed_nuptake` as the P scaling factor at `FatesSoilBGCFluxMod.F90:202` — `prescribed_puptake` is declared in the parameter file but **not consumed** anywhere in the uptake unpack routine. This is a source-level note, not a wiki error.

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:102-518)`, `(main/FatesConstantsMod.F90:94-125)`, `(parteh/PRTAllometricCNPMod.F90:470-475,688-697)`

## Integration With Cohort Lifecycle

### Cohort Creation

`InitPRTObject()` in `EDCohortDynamicsMod` allocates the appropriate extended class (`callom_prt_vartypes` or `cnp_allom_prt_vartypes`) based on `hlm_parteh_mode`, then calls the generic `InitPRTVartype()` to lay out state arrays and register boundary conditions. Each `RegisterBCInOut` call (for example in `FatesCohortMod.F90`) pairs a BC index with a target pointer on the cohort struct.

For CNP, the PID state variables (`cx_int`, `cx0`, `ema_dcxdt`) are each registered as `bc_inout` entries, which means they are persistent fields on the cohort, written back via pointer aliases during `CNPAdjustFRootTargets`, and checkpointed with the rest of the cohort state.

### Cohort Fusion

`WeightedFusePRTVartypes()` (`PRTGenericMod.F90`) merges two cohorts' PARTEH objects using weighted averages on every state variable and every flux accumulator. Mass conservation is preserved across the fusion because `val0`, `net_alloc`, `turnover`, `burned`, `damaged` are all averaged by the same weights as `val`.

Sources: `(biogeochem/EDCohortDynamicsMod.F90:293-342)`, `(parteh/PRTGenericMod.F90)`

## Summary

PARTEH decouples allocation hypothesis code from the rest of FATES by isolating everything in the `prt_vartypes` base class and its extended children. New hypotheses can be added by extending the class and implementing `DailyPRT`, `FastPRT`, `DamageRecovery`, and `GetNutrientTarget`. The current supported hypotheses are:

- Carbon-only (simpler, runs three sub-blocks split across `phase=1,2,3` of `DailyPRT`)
- CNP flexible (richer, runs three internal CNP steps inside a single `phase=1` call; uses a PID controller on `l2fr`)

See the per-hypothesis documents for algorithm detail.

Sources: `(parteh/PRTGenericMod.F90:1-280)`, `(parteh/PRTAllometricCarbonMod.F90:1-90)`, `(parteh/PRTAllometricCNPMod.F90:1-90)`
