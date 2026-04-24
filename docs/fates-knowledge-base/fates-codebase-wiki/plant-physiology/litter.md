# Litter Production and Turnover

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/FatesLitterMod.F90` (litter type + `ncwd`/`ndcmpy` constants, `adjust_SF_CWD_frac`)
- `biogeochem/EDPhysiologyMod.F90` (`CWDInput`, `PreDisturbanceIntegrateLitter`, `CWDOut`)
- `biogeochem/EDCohortDynamicsMod.F90` (`SendCohortToLitter`)
- `parteh/PRTLossFluxesMod.F90` (`PRTMaintTurnover`, `PRTDeciduousTurnover`, `PRTBurnLosses`, `PRTDamageLosses`)

</details>

## Purpose and Scope

This document describes how plant biomass becomes litter in FATES, including maintenance turnover, deciduous abscission, damage losses, fire losses, and cohort mortality transfers. For mortality rates that drive whole-cohort transfers see `mortality.md`. For nutrient retranslocation that accompanies abscission see `parteh/soil_plant_interface.md`.

## Litter Pool Structure

`FatesLitterMod.F90` defines:

- `ncwd = 4` (number of coarse woody debris size classes, `FatesLitterMod.F90:48`)
- `ndcmpy = 3` (number of fine-litter decomposability classes, `:51`)
- `ilabile = 1`, `icellulose = 2`, `ilignin = 3` (`:54-56`)

| Pool category | Spatial resolution | Size/chemistry dimensions | Purpose |
|---|---|---|---|
| Above-ground CWD | Patch-level | `ncwd` size classes | Standing and fallen large wood |
| Below-ground CWD | By soil layer | `ncwd` size classes | Coarse root debris |
| Leaf fine litter | Patch-level | `ndcmpy` decomposability classes | Leaf and reproductive litter |
| Root fine litter | By soil layer | `ndcmpy` decomposability classes | Fine-root litter |
| Seed bank | Patch-level | By PFT | Viable seeds for recruitment |

Decomposability partitioning of leaf/fineroot litter is determined by `GetDecompyFrac(pft, organ, dcmpy)` in `EDPftvarcon.F90`.

## Litter Production Pathways

1. **Maintenance turnover** (continuous): `PRTMaintTurnover()` in `parteh/PRTLossFluxesMod.F90` applies daily background losses for leaves, fine roots, and woody tissues according to `leaf_long`, `froot_long`, and branchfall parameters.
2. **Deciduous turnover** (event): `PRTDeciduousTurnover()` handles leaf/fineroot/stem abscission triggered by `phenology_leafonoff`. Applied to large fractions at once. See `phenology.md`.
3. **Damage losses**: `PRTDamageLosses()` transfers biomass from the crown fraction lost during a damage event (see `crown_damage.md`).
4. **Fire losses**: `PRTBurnLosses()` consumes biomass during fire events. Uniform `mass_fraction` across elements in an organ, tracked separately in `prt%variables(i_var)%burned`.
5. **Cohort mortality transfer**: `SendCohortToLitter()` in `EDCohortDynamicsMod.F90` transfers all biomass from a specified number of plants in a dead cohort to patch-level litter pools.

## Retranslocation During Turnover

Turnover (both maintenance and deciduous) retains nutrients back to storage before the carbon is released to litter. The retained fractions come from:

- `prt_params%turnover_nitr_retrans(ipft, i_organ)`
- `prt_params%turnover_phos_retrans(ipft, i_organ)`

**The array indexing is PFT-first, organ-second.** Retranslocation applies to leaves and fine roots; carbon is never retranslocated (always goes to litter).

## Maintenance Turnover Details

`PRTMaintTurnover()` applies daily fractional losses:

| Tissue | Loss rate source |
|---|---|
| Evergreen leaves | `1 / (ndays_per_year * leaf_long(ipft, age_class))` |
| Fine roots | `1 / (ndays_per_year * root_long(ipft))` |
| Branchfall from stems | Allometric/PFT-dependent |

## Cohort Mortality Transfer

`SendCohortToLitter()`:

- Operates on an absolute number of plants `nplant`, not on the whole cohort
- Transfers all organs (leaf, fnrt, sapw, store, struct, repro) for all elements (C, N, P)
- Does NOT modify per-plant PARTEH pools; only reduces `cohort%n`
- CWD size-class distribution is adjusted by cohort dbh via `adjust_SF_CWD_frac(dbh, ncwd, SF_val_CWD_frac, SF_val_CWD_frac_adj)` in `FatesLitterMod.F90:439-493`, which gives smaller plants more weight in smaller CWD classes

## CWD Input and Fragmentation

`CWDInput()` in `EDPhysiologyMod.F90` aggregates turnover fluxes into the site-level litter pool inputs. The daily sequence is:

1. Each PARTEH organ computes its turnover, retranslocation, burned, damaged fluxes
2. `CWDInput` sums losses by pool class and transfers them to `leaf_fines_in`, `root_fines_in`, `ag_cwd_in`, `bg_cwd_in`
3. `PreDisturbanceIntegrateLitter()` updates litter state variables
4. `CWDOut()` computes fragmentation fluxes to soil BGC using a `fragmentation_scaler` (temperature and moisture dependent)
5. `frag_out` accumulates into `site_mass` for mass balance checks

## Mass Balance

Each PARTEH variable tracks multiple flux components:

| Flux | Sign | Meaning |
|---|---|---|
| `net_alloc` | + gain, - loss | Net allocation (includes retranslocation in) |
| `turnover` | + | Mass sent to litter |
| `burned` | + | Mass consumed by fire |
| `damaged` | + | Mass lost to damage |

`CheckMassConservation` methods verify daily balance. `site_massbal_type` accumulates `frag_out`, inputs, and losses for each element; `TotalBalanceCheck` is called at multiple points in `EDMainMod` to catch drift.

## Code Entry Points

| Function | Location | Purpose |
|---|---|---|
| `PRTMaintTurnover` | `parteh/PRTLossFluxesMod.F90` | Continuous maintenance turnover |
| `PRTDeciduousTurnover` | `parteh/PRTLossFluxesMod.F90` | Event-based abscission |
| `PRTDamageLosses` | `parteh/PRTLossFluxesMod.F90` | Damage-driven loss |
| `PRTBurnLosses` | `parteh/PRTLossFluxesMod.F90` | Fire-driven loss |
| `SendCohortToLitter` | `EDCohortDynamicsMod.F90` | Whole-cohort mortality transfer |
| `CWDInput` | `EDPhysiologyMod.F90` | Aggregate flux-to-pool inputs |
| `PreDisturbanceIntegrateLitter` | `EDPhysiologyMod.F90` | Integrate litter state |
| `CWDOut` | `EDPhysiologyMod.F90` | Fragmentation flux out |
| `adjust_SF_CWD_frac` | `FatesLitterMod.F90:439-493` | DBH-dependent CWD size partitioning |
