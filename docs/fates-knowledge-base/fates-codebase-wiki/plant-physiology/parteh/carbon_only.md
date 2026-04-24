# Carbon-Only Allocation

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `parteh/PRTAllometricCarbonMod.F90`
- `parteh/PRTGenericMod.F90`
- `parteh/PRTLossFluxesMod.F90`
- `parteh/PRTParametersMod.F90`
- `biogeochem/FatesAllometryMod.F90`
- `main/EDMainMod.F90`

## Purpose and Scope

The carbon-only allocation hypothesis (`prt_carbon_allom_hyp = 1`) is the simpler of FATES' two PARTEH hypotheses. It tracks only carbon (no nitrogen or phosphorus state), allocates daily net carbon balance to tissues in a priority order, and grows DBH along the allometric curve once the tissue-replacement and storage-refill stages are complete.

For the CNP allocation hypothesis, see [CNP Allocation and Nutrient Dynamics](./cnp_allocation.md). For the framework overview, see [PARTEH: Plant Allocation System](./index.md).

## Hypothesis Overview

Key characteristics:

- All biomass pools contain only carbon (C12). No nitrogen or phosphorus state is kept.
- Growth is constrained by allometric relationships between DBH and target biomass for each tissue.
- Allocation priorities favor tissue-turnover replacement first, then storage, then leaves/fine-roots/sapwood to target, then structure, then stature growth.
- DBH is integrated alongside the carbon pools during stature growth via an ODE solver (Euler by default, RKF45 optionally).
- No nutrient limitation, no uptake from soil, no retranslocation (`retrans = 0` for carbon in `PRTLossFluxesMod`).

The class is `callom_prt_vartypes`, extending `prt_vartypes`. Selection is controlled by the host-model variable `hlm_parteh_mode`.

Sources: `(parteh/PRTAllometricCarbonMod.F90:1-143)`, `(parteh/PRTGenericMod.F90:69-70)`

## State Variables

| Local index | Name | Symbol | Positions |
|---|---|---|---|
| 1 | `leaf_c_id` | leaf C | 1..`nleafage` (up to `max_nleafage = 4`) |
| 2 | `fnrt_c_id` | fine-root C | 1 |
| 3 | `sapw_c_id` | sapwood C | 1 |
| 4 | `store_c_id` | storage C | 1 |
| 5 | `repro_c_id` | reproduction C | 1 |
| 6 | `struct_c_id` | structure C | 1 |

Only leaves are age-stratified; new allocation always flows into position 1 (the youngest bin). The DBH slot is added as index 7 (`dbh_id`) for the purpose of the integration step (`num_intgr_vars = 7`).

Sources: `(parteh/PRTAllometricCarbonMod.F90:76-90)`

## Boundary Conditions

### Input-Output (`bc_inout`)

| Index | Constant | Symbol | Units |
|---|---|---|---|
| 1 | `ac_bc_inout_id_dbh` | DBH | cm |
| 2 | `ac_bc_inout_id_netdc` | `carbon_balance` (daily NPP-MR) | kgC |

### Input-Only (`bc_in`)

| Index | Constant | Symbol | Type |
|---|---|---|---|
| 1 | `ac_bc_in_id_pft` | PFT index | integer |
| 2 | `ac_bc_in_id_ctrim` | canopy trim factor [0-1] | real |
| 3 | `ac_bc_in_id_lstat` | leaf status (`leaves_on`/`leaves_off`/`leaves_shedding`) | integer |
| 4 | `ac_bc_in_id_cdamage` | crown damage class | integer |
| 5 | `ac_bc_in_id_efleaf` | leaf elongation factor [0-1] | real |
| 6 | `ac_bc_in_id_effnrt` | fine-root elongation factor [0-1] | real |
| 7 | `ac_bc_in_id_efstem` | stem elongation factor [0-1] | real |

Elongation factors gate the allometric target calculations during non-fully-expanded phenology stages.

Sources: `(parteh/PRTAllometricCarbonMod.F90:99-118)`

## Daily Allocation: `DailyPRTAllometricCarbon`

The main routine is `DailyPRTAllometricCarbon(this, phase)` in `PRTAllometricCarbonMod.F90:260-977`. Unlike CNP, the carbon-only hypothesis actually uses the `phase` argument. It dispatches on it via a single Fortran `select case (phase)` with exactly **three** case branches: `case(1)`, `case(2)`, and `case(3)` (lines 524-949). Source comments label internal sub-blocks inside those three cases with Roman numerals (III, IV, V, VI, VII, VIII); the following subsections preserve those labels.

Hence "three-phase" is the correct count. The older wiki labeling of "five phases" referred to Roman-numeral sub-blocks, not to the actual `select case (phase)` dispatch.

Sources: `(parteh/PRTAllometricCarbonMod.F90:524)` (`select case (phase)`)

### Step 0 (before dispatch): Allometric Targets

Before the `select case`, the routine computes current allometric targets for every organ from DBH, PFT, canopy trim, crown damage, and the three elongation factors (lines ~442-500):

```
call bleaf(dbh, ipft, crowndamage, canopy_trim, elongf_leaf, target_leaf_c)
call bfineroot(dbh, ipft, canopy_trim, l2fr, elongf_fnrt, target_fnrt_c)
call bsap_allom(...); call bagw_allom(...); call bbgw_allom(...)
call bdead_allom(...); call bstore_allom(...)
```

If the PFT is drought-deciduous and currently dormant (`is_hydecid_dormant`), tissue targets (leaf, fine-root, sapwood, structure) are zeroed and any positive carbon balance is steered directly to storage at lines 511-517. This check runs before dispatch.

Sources: `(parteh/PRTAllometricCarbonMod.F90:442-517)`

### `case(1)` — Replace Turnover, Settle Carbon-Balance Sign

Two sub-blocks (III and IV) execute inside `case(1)`:

**Sub-block III (lines 531-584): Pay leaf/fine-root turnover.** Demand is

```
leaf_c_demand = leaf_stor_priority(ipft) * sum(turnover(leaf, :))    ! evergreen
fnrt_c_demand = leaf_stor_priority(ipft) * turnover(fnrt, 1)
```

with special cases for drought-deciduous dormant state (both demands zero) and cold-deciduous/drought-deciduous leaves-on state (leaf demand zero, fnrt demand set to maintain fine roots). The routine spends up to `store_c + carbon_balance` on these demands proportionally:

```
allocation_factor = min(1, (store_c + carbon_balance) / total_c_demand)
leaf_c_flux       = leaf_c_demand * allocation_factor
fnrt_c_flux       = fnrt_c_demand * allocation_factor
```

`leaf_c(iexp_leaf)` and `fnrt_c` are updated and `carbon_balance` is reduced. If the pulled demand pushed `carbon_balance` below zero, the deficit is made up from storage in sub-block IV (below).

**Sub-block IV (lines 586-613): Reconcile negative balance or deposit to storage.**

- If `carbon_balance < 0`: storage covers the deficit. `store_c_flux = carbon_balance` (negative); `store_c += store_c_flux`.
- If `carbon_balance ≥ 0`: deposit some of the positive balance into storage using the same saturating function as CNP (lines 603-611):

    ```
    store_below_target    = max(0, target_store_c - store_c)
    store_target_fraction = max(0, store_c / target_store_c)
    store_c_flux          = min(store_below_target, carbon_balance * max(exp(-store_target_fraction^4) - exp(-1), 0))
    ```

    The exponential weighting pushes a large share to storage when storage is near empty and a vanishing share when near target.

Therefore `case(1)` is **not** only the negative-balance branch. It handles turnover replacement and both signs of carbon balance, in the same `DailyPRT` call.

Sources: `(parteh/PRTAllometricCarbonMod.F90:525-613)`

### `case(2)` — Push Live Pools Toward Allometric Targets

Three sub-blocks execute inside `case(2)`:

- **V (lines 615-645):** Bring leaves and fine-roots up to target by proportional allocation, using `leaf_below_target = max(0, target_leaf_c - sum(leaf_c))` and similarly for `fnrt`.
- **VI (lines 647-681):** Push all live pools (leaf, fnrt, sapw, store) proportionally toward their below-target amounts, using one shared allocation factor. Structure is excluded here.
- **VII (lines 683-700):** If carbon remains, replenish the structural pool directly to its below-target amount.

Fusion can leave pools above target; any such pool is not reduced — it just waits for the other pools to catch up.

Sources: `(parteh/PRTAllometricCarbonMod.F90:615-700)`

### `case(3)` — Stature Growth

Two sub-blocks execute inside `case(3)`:

- **VII ½ (lines 702-715):** If the plant is semi-deciduous and shedding leaves but still has positive `carbon_balance`, stash the whole carbon balance into storage (even above target) and skip growth. This avoids building new tissue when the plant is in a leaf-shedding regime.
- **VIII (lines 718-947):** Integrate all carbon pools and DBH along the allometric curve. An adaptive integrator (`RKF45` or Euler) advances the seven-element state vector `c_pool = [leaf, fnrt, sapw, store, repro, struct, dbh]`, with a `c_mask` that excludes pools already above target. After each step, `CheckIntegratedAllometries` verifies the step stayed on allometry; if not, the step is halved and retried. `max_substeps = 300` iterations are allowed before the run aborts with a diagnostic dump.

On success, the integrated pool deltas are corrected by a proportional factor `flux_adj = carbon_balance / total_flux` to guarantee exact mass conservation, then committed to the state (lines 900-933). `dbh` is updated at line 933.

Sources: `(parteh/PRTAllometricCarbonMod.F90:702-947)`

### After Dispatch: Flux Diagnostics

After `select case`, the routine accumulates `net_alloc` on each pool as `new - old`:

```fortran
! PRTAllometricCarbonMod.F90:951-971
this%variables(leaf_c_id)%net_alloc(icd) += (leaf_c(icd) - leaf_c0(icd))
! ... similar for fnrt, sapw, store, repro, struct
```

This feeds the `CheckMassConservation` diagnostic and the NPP accumulators in `FatesSoilBGCFluxMod::PrepCH4BCs`.

Sources: `(parteh/PRTAllometricCarbonMod.F90:951-977)`

## Allometric Functions Used

| Function | Purpose | Primary inputs |
|---|---|---|
| `bleaf` | Target leaf biomass | dbh, ipft, crowndamage, canopy_trim, elongf_leaf |
| `bfineroot` | Target fine-root biomass | dbh, ipft, canopy_trim, l2fr, elongf_fnrt |
| `bsap_allom` | Target sapwood biomass | dbh, ipft, crowndamage, canopy_trim, elongf_stem |
| `bstore_allom` | Target storage biomass | dbh, ipft, crowndamage, canopy_trim |
| `bagw_allom` | Above-ground woody biomass target | dbh, ipft, crowndamage, elongf_stem |
| `bbgw_allom` | Below-ground woody biomass target | dbh, ipft, elongf_stem |
| `bdead_allom` | Structural biomass target | agw, bgw, sapw, ipft |
| `h_allom` | Height from DBH | dbh, ipft |

For carbon-only, `l2fr` is the **static** parameter `prt_params%allom_l2fr(ipft)`. CNP plants instead modify `l2fr` dynamically through the PID controller.

Sources: `(biogeochem/FatesAllometryMod.F90)`, `(parteh/PRTAllometricCarbonMod.F90:442-500)`

## Integration With FATES Daily Loop

Inside `EDMainMod::ed_integrate_state_variables`:

```
1. call PRTMaintTurnover(...)            [line 535, retrans is zero for C]
2. call currentCohort%prt%DailyPRT(phase=1)   [line 582, executes case(1)]
3. call currentCohort%prt%DailyPRT(phase=2)   [line 585, executes case(2)]
4. (damage module runs between phase=2 and phase=3 if enabled)
5. call currentCohort%prt%DailyPRT(phase=3)   [line 601, executes case(3)]
```

Deciduous leaf drop and leaf flush run in `EDPhysiologyMod::phenology` independently of `DailyPRT` (call sites at `EDPhysiologyMod.F90:1692-1749`). They invoke `PRTDeciduousTurnover` (which for carbon-only just subtracts `(1-retrans) * mass_fraction * val` from the pool and adds it to the turnover diagnostic, with `retrans = 0`) and `PRTPhenologyFlush` (which transfers a fraction of storage into leaves or fine roots as part of spring leaf-out).

Sources: `(main/EDMainMod.F90:535-601)`, `(biogeochem/EDPhysiologyMod.F90:1692-1749)`, `(parteh/PRTLossFluxesMod.F90:461-870)`

## Integration Method

The ODE integrator is chosen by a hard-coded switch at `PRTAllometricCarbonMod.F90:405-406`:

```fortran
integer, parameter :: ODESolve = 2   ! 1 = RKF45, 2 = Euler
```

With `ODESolve = 2`, each integration attempt first tries to span the whole `carbon_balance` in one Euler step, then validates with `CheckIntegratedAllometries`. If the allometry check fails, the step is halved and retried. `max_substeps = 300` iterations max. RKF45 is available but not the default.

Sources: `(parteh/PRTAllometricCarbonMod.F90:405-406,829-836)`

## Loss Fluxes in Carbon-Only Mode

The carbon-only hypothesis uses the same `PRTLossFluxesMod` routines as CNP, but with `retrans = 0` for the carbon element branch (`PRTLossFluxesMod.F90:571-575` and `:775-776`). Practically:

- **Evergreen maintenance turnover** (`PRTMaintTurnover`): Drains `val(i_pos)` by `base_turnover(organ) * val`, routes all of it to the `turnover(i_pos)` diagnostic, and adds nothing back to storage.
- **Deciduous leaf drop** (`PRTDeciduousTurnover`): Drains the specified `mass_fraction` of leaf (and fnrt, sapw, struct for non-woody) and routes all of it to turnover.
- **Leaf flush** (`PRTPhenologyFlush`): Transfers a fraction `c_store_transfer_frac` of storage C into the target organ (leaf or fnrt or, for non-woody, sapw/struct).

No nutrient is retranslocated because the carbon-only hypothesis has no nutrient state.

Sources: `(parteh/PRTLossFluxesMod.F90:73-277,461-870)`

## Key Parameters

| Parameter | Role |
|---|---|
| `allom_hmode`, `allom_lmode`, etc. | Select which allometry function form to use for each relationship |
| `allom_d2h1..3`, `allom_d2bl1..3`, `allom_agb1..3` | Allometry coefficients |
| `allom_l2fr` | Fixed leaf-to-fine-root biomass ratio (carbon-only; CNP overrides this) |
| `wood_density`, `c2b`, `allom_agb_frac` | Tissue property coefficients |
| `leaf_long`, `root_long` | Turnover timescales (years) |
| `season_decid`, `stress_decid` | Phenology flags |
| `leaf_stor_priority` | Fraction of tissue turnover demand paid at priority 1 in sub-block III |

Sources: `(parteh/PRTParametersMod.F90)`, `(biogeochem/FatesAllometryMod.F90)`

## Summary

The carbon-only hypothesis runs its daily allocation in three dispatches of `DailyPRT(phase)` with `phase = 1, 2, 3`. Each dispatch executes one `case` of a single `select case (phase)` in `DailyPRTAllometricCarbon`. The branches do, respectively: turnover replacement and carbon-balance reconciliation; tissue refill toward allometric targets; stature growth via numerical integration along the allometric curve. The carbon-only hypothesis lacks nutrient state, so the PID controller and equivalent-carbon limiter used by CNP are absent; `l2fr` is a fixed PFT parameter.

Sources: `(parteh/PRTAllometricCarbonMod.F90:260-977)`
