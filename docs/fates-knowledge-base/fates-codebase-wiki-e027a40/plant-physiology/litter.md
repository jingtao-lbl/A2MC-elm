# Litter Production and Turnover

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/FatesLitterMod.F90` (litter type + `ncwd`/`ndcmpy` constants, `adjust_SF_CWD_frac`)
- `biogeochem/EDPhysiologyMod.F90` (`CWDInput`, `PreDisturbanceIntegrateLitter`, `CWDOut`, `GenerateDamageAndLitterFluxes`)
- `biogeochem/EDCohortDynamicsMod.F90` (`SendCohortToLitter`)
- `parteh/PRTLossFluxesMod.F90` (`PRTMaintTurnover`, `PRTDeciduousTurnover`, `PRTBurnLosses`, `PRTDamageLosses`)
- `parteh/PRTParametersMod.F90` (`leaf_long(:,:)`, `leaf_long_ustory(:,:)`, retranslocation arrays)
- `parteh/PRTParamsFATESMod.F90` (loaders for `fates_turnover_leaf_canopy`, `fates_turnover_leaf_ustory`)

</details>

## Purpose and Scope

This document describes how plant biomass becomes litter in FATES at e027a40, including maintenance turnover, deciduous abscission, damage losses, fire losses, and cohort mortality transfers. For mortality rates that drive whole-cohort transfers see `mortality.md`. For nutrient retranslocation that accompanies abscission see `parteh/soil_plant_interface.md` (topic 06).

## What Changed Since e85d997

- **Leaf turnover is now split between canopy and understory cohorts.** The legacy `fates_turnover_leaf` parameter is gone. Two new JSON keys replace it: `fates_turnover_leaf_canopy` (loaded into `prt_params%leaf_long`) and `fates_turnover_leaf_ustory` (loaded into `prt_params%leaf_long_ustory`). Maintenance turnover selects between them based on cohort canopy position.

## Litter Pool Structure

`biogeochem/FatesLitterMod.F90:48-56` defines:

- `ncwd = 4` (number of coarse woody debris size classes, `:48`)
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

1. **Maintenance turnover** (continuous): `PRTMaintTurnover()` in `parteh/PRTLossFluxesMod.F90` applies daily background losses for leaves, fine roots, and woody tissues according to `leaf_long`/`leaf_long_ustory`, `root_long`, and branchfall parameters. See "Maintenance Turnover Details" below.
2. **Deciduous turnover** (event): `PRTDeciduousTurnover()` handles leaf/fineroot/stem abscission triggered by `phenology_leafonoff`. Applied to large fractions at once. See `phenology.md`.
3. **Damage losses**: `PRTDamageLosses()` transfers biomass from the crown fraction lost during a damage event (see `crown_damage.md`).
4. **Fire losses**: `PRTBurnLosses()` consumes biomass during fire events. Uniform `mass_fraction` across elements in an organ, tracked separately in `prt%variables(i_var)%burned`.
5. **Cohort mortality transfer**: `SendCohortToLitter()` in `EDCohortDynamicsMod.F90` transfers all biomass from a specified number of plants in a dead cohort to patch-level litter pools.

## Retranslocation During Turnover

Turnover (both maintenance and deciduous) retains nutrients back to storage before the carbon is released to litter. The retained fractions come from:

- `prt_params%turnover_nitr_retrans(ipft, i_organ)`
- `prt_params%turnover_phos_retrans(ipft, i_organ)`

**The array indexing is PFT-first, organ-second.** Retranslocation applies to leaves and fine roots; carbon is never retranslocated (always goes to litter).

## Maintenance Turnover Details (canopy/ustory split, e027a40)

`PRTMaintTurnover()` in `parteh/PRTLossFluxesMod.F90` selects between two leaf-longevity arrays at `:745-756`:

```fortran
if (icanlayer .eq. 1) then
   ! Canopy cohort
   aclass_sen_id = size(prt_params%leaf_long(ipft,:))
   leaf_long = prt_params%leaf_long(ipft, aclass_sen_id)
else
   ! Understory cohort
   aclass_sen_id = size(prt_params%leaf_long_ustory(ipft,:))
   leaf_long = prt_params%leaf_long_ustory(ipft, aclass_sen_id)
end if

if ( leaf_long > nearzero .and. prt_params%phen_leaf_habit(ipft) == ievergreen ) then
   if (is_drought) then
      base_turnover(leaf_organ) = years_per_day / (leaf_long * senleaf_long_fdrought(ipft))
   else
      base_turnover(leaf_organ) = years_per_day / leaf_long
   end if
end if
```

Two consequences:
- The same evergreen plant has different leaf longevity (and therefore different daily turnover rate) when it is in the canopy vs in the understory.
- Maintenance turnover is only applied to evergreen PFTs (`phen_leaf_habit == ievergreen`). Deciduous PFTs lose leaves through `PRTDeciduousTurnover` driven by phenology, not through `PRTMaintTurnover`.

| Tissue | Loss rate source (canopy) | Loss rate source (understory) |
|---|---|---|
| Evergreen leaves | `1 / (ndays_per_year * leaf_long(ipft, age_class))` | `1 / (ndays_per_year * leaf_long_ustory(ipft, age_class))` |
| Fine roots | `1 / (ndays_per_year * root_long(ipft))` | same |
| Branchfall from stems | Allometric/PFT-dependent (`branch_long(ipft)`) | same |

Parameter declarations at `parteh/PRTParametersMod.F90:46-53`:

```fortran
real(r8), allocatable :: leaf_long(:,:)         ! Leaf turnover time (longevity) (pft x age-class)
real(r8), allocatable :: leaf_long_ustory(:,:)  ! As above but for understory trees
```

Loaders at `parteh/PRTParamsFATESMod.F90:351-357`:

```fortran
param_p => pstruct%GetParamFromName('fates_turnover_leaf_canopy')
allocate(prt_params%leaf_long(num_pft, num_ageclass))
call Transp2dReal(param_p%r_data_2d, prt_params%leaf_long)

param_p => pstruct%GetParamFromName('fates_turnover_leaf_ustory')
allocate(prt_params%leaf_long_ustory(num_pft, num_ageclass))
call Transp2dReal(param_p%r_data_2d, prt_params%leaf_long_ustory)
```

JSON entries at `parameter_files/fates_params_default.json:1538-1552`. Note: setting `fates_turnover_leaf` (the legacy name) in a parameter file at e027a40 will trigger a "parameter not found" error from the JSON loader.

A second canopy/ustory selection occurs in `parteh/PRTGenericMod.F90:1386-1392` for leaf-age-class promotion logic, with the same canopy-vs-understory dispatch.

### Fine root turnover

Fine-root maintenance turnover is driven by `fates_turnover_fnrt` (PFT-level, units 1/yr), loaded into `prt_params%root_long`. Unlike leaves, fine roots have a single rate (no canopy/understory split) and are turned over both for evergreen and deciduous PFTs. The vertical allocation of the resulting fine-root litter follows the cohort root profile (see `plant-physiology/allometry.md` "Fine root vertical profile" — uses `fates_allom_fnrt_prof_a` and `fates_allom_fnrt_prof_b` for the two-parameter exponential form).

## Cohort Mortality Transfer

`SendCohortToLitter()` (`biogeochem/EDCohortDynamicsMod.F90`):

- Operates on an absolute number of plants `nplant`, not on the whole cohort
- Transfers all organs (leaf, fnrt, sapw, store, struct, repro) for all elements (C, N, P)
- Does NOT modify per-plant PARTEH pools; only reduces `cohort%n`
- CWD size-class distribution is adjusted by cohort dbh via `adjust_SF_CWD_frac(dbh, ncwd, SF_val_CWD_frac, SF_val_CWD_frac_adj)` in `FatesLitterMod.F90:441-505`, which gives smaller plants more weight in smaller CWD classes (cutoffs: `lb_max_diam = 7.6 cm`, `sb_max_diam = 2.5 cm`, `twig_max_diam = 0.6 cm`; `:60-62`).

## CWD Input and Fragmentation

`CWDInput()` in `EDPhysiologyMod.F90:2802` aggregates turnover fluxes into the site-level litter pool inputs. The daily sequence is:

1. Each PARTEH organ computes its turnover, retranslocation, burned, damaged fluxes
2. `CWDInput` sums losses by pool class and transfers them to `leaf_fines_in`, `root_fines_in`, `ag_cwd_in`, `bg_cwd_in`
3. `PreDisturbanceIntegrateLitter()` (`EDPhysiologyMod.F90:506`) updates litter state variables
4. `CWDOut()` (`EDPhysiologyMod.F90:3247`) computes fragmentation fluxes to soil BGC using a `fragmentation_scaler` (temperature and moisture dependent; `:3174`)
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
| `PRTMaintTurnover` | `parteh/PRTLossFluxesMod.F90` (around `:710`+) | Continuous maintenance turnover (canopy/ustory split at `:745-756`) |
| `PRTDeciduousTurnover` | `parteh/PRTLossFluxesMod.F90` | Event-based abscission |
| `PRTDamageLosses` | `parteh/PRTLossFluxesMod.F90` | Damage-driven loss |
| `PRTBurnLosses` | `parteh/PRTLossFluxesMod.F90` | Fire-driven loss |
| `SendCohortToLitter` | `EDCohortDynamicsMod.F90` | Whole-cohort mortality transfer |
| `CWDInput` | `EDPhysiologyMod.F90:2802` | Aggregate flux-to-pool inputs |
| `PreDisturbanceIntegrateLitter` | `EDPhysiologyMod.F90:506` | Integrate litter state |
| `CWDOut` | `EDPhysiologyMod.F90:3247` | Fragmentation flux out |
| `adjust_SF_CWD_frac` | `FatesLitterMod.F90:441` | DBH-dependent CWD size partitioning |
