# Crown Damage and Recovery

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/DamageMainMod.F90` (`GetCrownReduction`, `GetDamageFrac`, `GetDamageMortality`, `IsItDamageTime`)
- `biogeochem/EDPhysiologyMod.F90` (`GenerateDamageAndLitterFluxes`, around line 256 and following)
- `biogeochem/EDCohortDynamicsMod.F90` (`DamageRecovery`)
- `biogeochem/EDMortalityFunctionsMod.F90` (`dgmort` term)
- `biogeochem/FatesAllometryMod.F90` (damage-aware `bleaf`, `bagw_allom`, `carea_allom`)

</details>

## Purpose and Scope

Crown damage represents physical injury to plant crowns from storms, impacts, or other disturbances. Damaged plants survive but lose a fraction of leaves, branches, and crown area, and carry elevated mortality. The system is activated by the host-model flag `hlm_use_tree_damage == itrue`.

For the damage-mortality term `dgmort` itself, see `mortality.md`.

## State Variables

| Variable | Location | Description |
|---|---|---|
| `cohort%crowndamage` | `fates_cohort_type` | Integer damage class in `[1, nlevdamage]`; 1 = undamaged |
| `nlevdamage` | `FatesInterfaceTypesMod` | Total number of damage classes |
| `hlm_use_tree_damage` | `FatesInterfaceTypesMod` | Global enable flag |
| `damage_time` | local | Whether damage occurs on the current dynamics timestep |

## Damage Timing and Triggering

`IsItDamageTime()` in `DamageMainMod.F90` determines whether damage should occur during a given dynamics timestep. When true, `GenerateDamageAndLitterFluxes()` (`EDPhysiologyMod.F90`) splits existing cohorts into damaged and undamaged sub-cohorts and transfers biomass to litter pools.

## Damage Class Transitions

`GetDamageFrac(pft, from_class, to_class, frac)` returns the fraction of a cohort transitioning between two damage classes. `GetCrownReduction(class_diff, reduction)` returns the fractional crown loss for a given class jump. Class 1 has no reduction; higher classes have progressively larger reductions.

## Biomass Loss on Damage Event

`GenerateDamageAndLitterFluxes()` partitions biomass losses by organ and by whether the organ is in the crown:

| Organ | Loss fraction | Rationale |
|---|---|---|
| Leaf | `crown_loss_frac` | Crown-resident; lost with the damaged crown fraction |
| Reproductive | `crown_loss_frac` | Crown-resident |
| Sapwood | `branch_loss_frac` | Branch-only, computed below |
| Storage | `branch_loss_frac` | Branch-resident |
| Structural | `branch_loss_frac` | Branch-resident |
| Fine roots | 0 | Not affected by crown damage |

Where `branch_loss_frac = crown_loss_frac * branch_frac * agb_frac`, with `branch_frac = param_derived%branch_frac(ipft)` (fraction of AGBW in branches vs bole) and `agb_frac = prt_params%allom_agb_frac(ipft)` (fraction of total woody biomass above ground).

## Damage Effects on Allometry

The allometry routines accept a `crowndamage` argument and call `GetCrownReduction(crowndamage, crown_reduction)` internally (`FatesAllometryMod.F90`, in `bleaf`, `bagw_allom`, and `carea_allom`). Damaged cohorts thus have lower target leaf biomass, lower target AGBW (via branch reduction), and lower crown area than undamaged cohorts of the same dbh.

## Damage-Dependent Mortality

`mortality_rates()` in `EDMortalityFunctionsMod.F90:127-131` calls `GetDamageMortality(crowndamage, pft, dgmort)` when `hlm_use_tree_damage == itrue`. Higher damage classes return higher mortality rates. `dgmort` adds to the other mortality terms in `Mortality_Derivative()`.

## Damage Recovery

`DamageRecovery()` in `EDCohortDynamicsMod.F90` allows damaged plants to recover over time by creating new cohorts in lower damage classes. Recovery depends on time since damage, resource availability, and PFT recovery parameters. When a cohort has just been created through recovery (`newly_recovered == .true.`), certain daily calculations are bypassed to avoid double-counting:

| Operation | Bypassed? | Reason |
|---|---|---|
| Mortality calculation | Yes | Inherited from donor cohort |
| NPP/GPP/Resp accumulation | Yes | Inherited |
| Maintenance turnover | Yes | Inherited |
| PARTEH phase 1 (replace) | Yes | Allocation priorities already set |
| PARTEH phase 2 (stature) | No | Targets have changed |
| PARTEH phase 3 (remainder) | No | Growth can proceed |

## Litter Transfer

Damaged biomass is transferred to fine litter and coarse woody debris pools, partitioned by decomposability (`GetDecompyFrac`) for fine litter and by size class (`adjust_SF_CWD_frac`) for CWD.

## Integration With Other Systems

- **Fire**: Crown scorching translates to damage class transitions (see `fire/effects.md`).
- **Logging**: `lmort_collateral` represents partial collateral damage rather than death.
- **Patch dynamics**: Damage state is preserved when a cohort is transferred to a new patch during disturbance.
- **PARTEH**: Reduced targets via damage-aware `bleaf`, `bsap_allom`, `bstore_allom` drive reallocation that can slowly repair damage.

## Code Entry Points

| Function | Location | Purpose |
|---|---|---|
| `IsItDamageTime` | `DamageMainMod.F90` | Per-timestep damage trigger |
| `GenerateDamageAndLitterFluxes` | `EDPhysiologyMod.F90` (near `GenerateDamageAndLitterFluxes` subroutine) | Create damaged cohorts + litter transfer |
| `GetCrownReduction` | `DamageMainMod.F90` | Class difference to crown fraction lost |
| `GetDamageFrac` | `DamageMainMod.F90` | Transition fraction between classes |
| `GetDamageMortality` | `DamageMainMod.F90` | Mortality rate for a class |
| `DamageRecovery` | `EDCohortDynamicsMod.F90` | Create recovered cohorts in lower classes |
| `PRTDamageLosses` | `parteh/PRTLossFluxesMod.F90` | Apply damage losses to PARTEH pools |
