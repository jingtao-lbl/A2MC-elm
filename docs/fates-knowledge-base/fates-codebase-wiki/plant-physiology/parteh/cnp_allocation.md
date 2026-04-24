# CNP Allocation and Nutrient Dynamics

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `parteh/PRTAllometricCNPMod.F90`
- `parteh/PRTLossFluxesMod.F90`
- `parteh/PRTGenericMod.F90`
- `parteh/PRTParamsFATESMod.F90`
- `parteh/PRTParametersMod.F90`
- `main/EDPftvarcon.F90`
- `main/EDMainMod.F90`
- `biogeochem/EDPhysiologyMod.F90`
- `biogeochem/FatesSoilBGCFluxMod.F90`
- `biogeophys/FatesPlantRespPhotosynthMod.F90`
- `main/FatesConstantsMod.F90`

## Purpose and Scope

This document describes the Carbon-Nitrogen-Phosphorus (CNP) allocation hypothesis in FATES PARTEH (`prt_cnp_flex_allom_hyp = 2`). The CNP hypothesis extends the carbon-only hypothesis to simultaneously track 18 state variables (6 organs × 3 elements) and to dynamically adjust the leaf-to-fine-root target biomass ratio (`l2fr`) via a PID controller that responds to the relative fill level of the carbon and nutrient storage pools.

For the carbon-only hypothesis see [Carbon-Only Allocation](./carbon_only.md). For the soil-plant uptake interface and competition modes see [Soil-Plant Nutrient Interface](./soil_plant_interface.md). For the PARTEH framework see [PARTEH: Plant Allocation System](./index.md).

CNP allocation is a calibration-critical module. The following sections are structured to correctly represent the algorithm as it exists in source, with explicit pointers to each subroutine and line range. Several prior descriptions in the older wiki misrepresented the phase flow, the location of retranslocation, and the boundary condition table. Those errors have been corrected here.

## High-Level Flow for One Daily Call

The CNP hypothesis runs exactly **once per plant per day**, inside a single call to `prt%DailyPRT(phase=1)` (see `DailyPRT` Semantics below). During that one call, the routine `DailyPRTAllometricCNP` in `PRTAllometricCNPMod.F90:370-707` executes the following internal steps in order:

| Internal step | What it does | Subroutine |
|---|---|---|
| Step 0 | Compute carbon allometry targets (`target_c`, `target_dcdd`) for every organ from current DBH | inline, calls `bleaf`/`bfineroot`/`bsap_allom`/`bstore_allom`/`bagw_allom`/`bbgw_allom`/`bdead_allom` |
| Step 0.5 | Move any carbon storage above target and **all** nutrient storage into the daily `c_gain`/`n_gain`/`p_gain` pool | inline (lines 534-542) |
| Step 1 (Prioritized Replacement) | Replenish tissues up to current allometric targets in priority order, settle the carbon-balance sign (storage draw or storage deposit), and top up nutrients to the growth-minimum stoichiometry | `CNPPrioritizedReplacement` (lines 943-1276) |
| Step 2 (Stature Growth) | Project nutrient-equivalent carbon, choose the limiter, integrate a stature-growth step along the allometric curve (RKF45 or Euler), then push nutrients onto the newly built tissues | `CNPStatureGrowth` (lines 1281-1826) |
| Step 3 (Allocate Remainder) | Refill nutrient storage up to `target * (1 + store_ovrflw_frac)`, call the PID `CNPAdjustFRootTargets` to update `l2fr`, then put remaining carbon into storage overflow (burn/exude/retain), then zero or report efflux | `CNPAllocateRemainder` (lines 1830-2012), `CNPAdjustFRootTargets` (lines 729-870) |
| Cleanup | Update `net_alloc` diagnostics, call `TrimFineRoot` to forcefully shrink fine-roots if `l2fr` dropped | `TrimFineRoot` (lines 874-939) |

Sources: `(parteh/PRTAllometricCNPMod.F90:370-707)`, `(parteh/PRTAllometricCNPMod.F90:943-1276)`, `(parteh/PRTAllometricCNPMod.F90:1281-1826)`, `(parteh/PRTAllometricCNPMod.F90:1830-2012)`

## `DailyPRT` Semantics: What `phase` Really Means

`EDMainMod::ed_integrate_state_variables` calls `prt%DailyPRT(phase)` three times per cohort with `phase = 1, 2, 3` (`main/EDMainMod.F90:582,585,601`). This is **not** the "three-phase CNP allocation" — it exists to give the damage module its own entry points. The CNP routine is not yet compatible with damage and therefore ignores all calls except the first:

```fortran
! PRTAllometricCNPMod.F90:430-433
! Phasing is only used to accomodate the
! damage module. Since this is incompatible with CNP
! Ignore all subsequent calls after the first
if (phase.ne.1) return
```

Consequence: **for CNP, the entire three-step internal algorithm (Prioritized Replacement → Stature Growth → Allocate Remainder) runs inside a single `DailyPRT(phase=1)` call via sequential internal calls** at `PRTAllometricCNPMod.F90:550,575,599`. The word "phase" in this document refers to the three internal steps, not to the `DailyPRT` argument.

Sources: `(parteh/PRTAllometricCNPMod.F90:430-433)`, `(parteh/PRTAllometricCNPMod.F90:550,575,599)`, `(main/EDMainMod.F90:582,585,601)`

## State Variables

The CNP class `cnp_allom_prt_vartypes` extends `prt_vartypes` and tracks 18 pools (`num_vars = 18`). Local indices are assigned at `PRTAllometricCNPMod.F90:86-108`:

| Local index | Name | Organ | Element |
|---|---|---|---|
| 1 | `leaf_c_id` | leaf | C12 (age-stratified, up to `max_nleafage = 4` bins) |
| 2 | `fnrt_c_id` | fine root | C12 |
| 3 | `sapw_c_id` | sapwood | C12 |
| 4 | `store_c_id` | storage | C12 |
| 5 | `repro_c_id` | reproduction | C12 |
| 6 | `struct_c_id` | structure | C12 |
| 7-12 | `*_n_id` | leaf, fnrt, sapw, store, repro, struct | nitrogen |
| 13-18 | `*_p_id` | leaf, fnrt, sapw, store, repro, struct | phosphorus |

Each `prt_vartype` stores `val` (current mass, kg), `val0` (mass at start of control period), `net_alloc` (cumulative allocation flux over the period), `turnover`, `burned`, `damaged`. Leaves are the only organ with age-discretized positions; all other organs use position 1 only. Allocation and growth always act on position 1 (the youngest leaf bin).

Sources: `(parteh/PRTAllometricCNPMod.F90:86-108)`, `(parteh/PRTGenericMod.F90:179-200)`

## Retranslocation: Happens BEFORE `DailyPRT`, not inside CNP

The retranslocation step (moving nutrients from senescing leaves/fine-roots into the storage pool before the tissue mass leaves the plant) is **not** executed inside `DailyPRTAllometricCNP`. It is executed earlier in the daily loop, in the turnover routines.

Caller sequence in `EDMainMod::ed_integrate_state_variables`:

```
1. call PRTMaintTurnover(...)                       [EDMainMod.F90:535]
2. (retranslocation happens inside MaintTurnoverSimpleRetranslocation)
3. currentCohort%daily_n_gain = daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily  [EDMainMod.F90:550-551]
4. call currentCohort%prt%DailyPRT(phase=1)         [EDMainMod.F90:582]
      └── DailyPRTAllometricCNP runs the 3-step algorithm
```

Separately, for deciduous leaf-drop events, `EDPhysiologyMod::phenology` calls `PRTDeciduousTurnover` at `EDPhysiologyMod.F90:1736-1747`, which dispatches to `DeciduousTurnoverSimpleRetranslocation` in `PRTLossFluxesMod.F90:503-626`.

Both retranslocation paths implement the same rule: a fraction `retrans` of the nutrient (not carbon) mass that would otherwise leave the plant is instead added to the storage pool's `val` and `net_alloc`, and the remaining `(1 - retrans) * turnover` is sent to the turnover/litter flux:

```fortran
! PRTLossFluxesMod.F90:571-617, maintenance path analogous
retrans = prt_params%turnover_nitr_retrans(ipft, organ_param_id(organ_id))   ! or phos
turnover_mass       = (1.0 - retrans) * mass_fraction * val(i_pos)
retranslocated_mass =  retrans        * mass_fraction * val(i_pos)

val(i_pos)                        -= (turnover_mass + retranslocated_mass)
turnover(i_pos)                   += turnover_mass
val(store_var, i_store_pos)       += retranslocated_mass
net_alloc(store_var, i_store_pos) += retranslocated_mass
```

Because retranslocation runs **before** `DailyPRT`, the storage pools that `DailyPRTAllometricCNP` sees at Step 0.5 already contain the retranslocated nutrient. When Step 0.5 then drains all nutrient storage into `n_gain`/`p_gain`, the retranslocated nutrient is re-entered into that day's allocation pool alongside any fresh soil uptake. This is the mechanism by which retranslocated mass "cycles back" into growth.

Parameters:

| Parameter | Allowed organs | Valid range | Source validation |
|---|---|---|---|
| `fates_cnp_turnover_nitr_retrans` | leaf, fnrt (+ store conceptually, organ id-dependent) | [0, 1] | `PRTParamsFATESMod.F90:1316-1365` |
| `fates_cnp_turnover_phos_retrans` | leaf, fnrt | [0, 1] | `PRTParamsFATESMod.F90:1316-1365` |

The parameter file must set `turnover_*_retrans` to **exactly zero** for sapwood and structure. The validation routine will abort the run if any non-zero value is supplied for sapw or struct (`PRTParamsFATESMod.F90:1319-1348`). Only leaves and fine roots (and, for the organ-param id that maps to the retained nutrient pool, storage) may carry a non-zero retranslocation fraction.

Sources: `(parteh/PRTLossFluxesMod.F90:461-626)` (deciduous), `(parteh/PRTLossFluxesMod.F90:630-870)` (maintenance), `(main/EDMainMod.F90:535,550-551,582)`, `(biogeochem/EDPhysiologyMod.F90:1736-1747)`, `(parteh/PRTParamsFATESMod.F90:1316-1365)`

## Step 0.5: Transfer Storage Into the Daily Pool

At the top of `DailyPRTAllometricCNP`, carbon storage **above** its allometric target and **all** nitrogen and phosphorus storage are transferred into the day's gain pools, which the rest of the routine will spend down:

```fortran
! PRTAllometricCNPMod.F90:534-542
store_flux = max(0, store_c_val - target_c(store_organ))
c_gain = c_gain + store_flux
store_c_val = store_c_val - store_flux

n_gain = n_gain + sum(store_n_val(:))
store_n_val(:) = 0

p_gain = p_gain + sum(store_p_val(:))
store_p_val(:) = 0
```

Carbon storage is only **partially** drained (only the amount above allometry). Nutrient storage is fully drained every day. This is why retranslocation accumulates into storage and then immediately re-enters the allocation pool.

Sources: `(parteh/PRTAllometricCNPMod.F90:528-542)`

## Step 1: `CNPPrioritizedReplacement`

Runs at `PRTAllometricCNPMod.F90:943-1276`. Does four things in order:

1. **Identify priority-1 organs** from `prt_params%alloc_priority(ipft, :)` (parameter `fates_alloc_organ_priority`). Leaves are excluded from the priority-1 list when leaves are off or shedding, and also when the PFT is not evergreen (to prevent accidental re-flushing). Only priority-1 organs receive carbon for maintenance-turnover replacement in this block.

2. **Pay maintenance turnover for priority-1 organs.** The demand is

    ```
    sum_c_demand = leaf_stor_priority(ipft) × sum(turnover(:))
    ```

   (summed over priority-1 organs). The actual flux is capped by what is available in storage plus carbon gain: `sum_c_flux = max(0, min(sum_c_demand, store_c + c_gain))`. Distribution to each priority-1 organ is proportional to its share of the demand (lines 1070-1099).

3. **Top up nitrogen and phosphorus** for priority-1 organs to their growth-minimum stoichiometry target (`GetNutrientTarget(..., stoich_growth_min)`), via `ProportionalNutrAllocation`, drawing from `n_gain` and `p_gain` respectively (lines 1102-1127).

4. **Handle the carbon-balance sign** (lines 1130-1158). If `c_gain < 0` after step 2, storage pays the deficit (`store_c_val -= |c_gain|`, `c_gain := 0`). If `c_gain > 0`, a fraction of the remainder is placed into storage using a saturating function:

    ```
    store_target_fraction = store_c_val / target_c(store_organ)
    store_demand          = max(c_gain * (exp(-store_target_fraction**4) - exp(-1)), 0)
    store_c_flux          = min(store_below_target, store_demand)
    ```

   This causes storage to receive a large fraction of `c_gain` when nearly empty and a vanishing share when near target.

5. **Loop over remaining priority levels 1..n_max_priority**, filling each organ up to `target_c(organ)` and then up to its nutrient stoichiometry. Storage has a **hard-coded** priority level of 2 (inserted at line 1179). All other organ priority levels come from `prt_params%alloc_priority(ipft, :)`. Carbon is transferred proportionally to deficit within each priority level; nutrients follow via `ProportionalNutrAllocation` (lines 1171-1270).

After Step 1, all carbon pools are at or above their allometric targets, carbon balance is ≥ 0, and remaining `c_gain`/`n_gain`/`p_gain` are available for stature growth.

Sources: `(parteh/PRTAllometricCNPMod.F90:943-1276)`, `(parteh/PRTAllometricCNPMod.F90:1074-1076)` (leaf_stor_priority demand)

## Step 2: `CNPStatureGrowth`

Runs at `PRTAllometricCNPMod.F90:1281-1826`. Grows DBH along the allometric curve, simultaneously growing all carbon pools that remain active after fusion masking.

### Equivalent-Carbon Limiter

Before integrating, the routine projects how much carbon it can actually spend given the nutrient supply. It calls `EstimateGrowthNC(this, target_c, target_dcdd, state_mask, avg_nc, avg_pc)` (`PRTAllometricCNPMod.F90:2465-2578`), which computes the `target_dcdd`-weighted average N:C and P:C ratios across all growing organs (including reproduction, leaf, fine root, sapwood, structure, storage). The stature-growth carbon is then:

```fortran
! PRTAllometricCNPMod.F90:1562-1590
neq_cgain = n_gain / avg_nc        ! how much C the N pool can support at growth stoichiometry
peq_cgain = p_gain / avg_pc        ! how much C the P pool can support

if c_gain < neq_cgain:
    if c_gain < peq_cgain:  c_gstature = c_gain;     limiter = c_limited
    else:                   c_gstature = peq_cgain;  limiter = p_limited
else:
    if neq_cgain < peq_cgain: c_gstature = neq_cgain; limiter = n_limited
    else:                     c_gstature = peq_cgain; limiter = p_limited
```

This is the "equivalent carbon" method: `c_gstature` is the minimum carbon among C, N-equivalent, and P-equivalent, which becomes the growth-step mass. Note that `limiter` is first assigned using loose thresholds on `c_gain`, `n_gain`, `p_gain` at lines 1385-1392, then **immediately overwritten to 0** at line 1394, then reassigned inside the `grow_lim_estNP` branch. Readers inspecting `bc_out(acnp_bc_out_id_limiter)` should know the final value comes from the `grow_lim_estNP` block, not from the earlier threshold test.

### Integration

With `c_gstature` in hand, stature growth integrates the C pools plus DBH along the allometric curve. The active integrator is Euler (`ODESolve = 2`, hard-coded at line 1363). An adaptive step attempt is made at each iteration; the state is advanced and `CheckIntegratedAllometries` verifies pools remain within `max_trunc_error` of their current allometric targets (lines 1620-1712). On failure the step is halved and retried, up to `max_substeps = 300`. Exceeding that aborts with a diagnostic dump of pool values, targets, and elongation factors (lines 1716-1757).

The integrator updates `state_array`, which includes `leaf_id, fnrt_id, sapw_id, store_id, struct_id, repro_id, dbh_id`. After convergence, a proportional correction forces the total carbon flux to exactly equal `c_gstature` (lines 1680-1710), then DBH is committed.

### Post-Integration Nutrient Allocation

After growth, N and P are deposited on the newly built tissues proportional to their demand vs the growth-min stoichiometry. Reproduction is prioritized via an optional first pass (when `prioritize_repro_nutr_growth = .true.`, lines 1772-1788) before the general proportional call (lines 1797-1821).

If any limiting resource is effectively tapped out (`c_gain <= calloc_abs_error`, `n_gain <= 0.1*calloc_abs_error`, or `p_gain <= 0.02*calloc_abs_error`) or leaves are off/shedding, stature growth is skipped entirely (lines 1404-1409).

Sources: `(parteh/PRTAllometricCNPMod.F90:1281-1826)`, `(parteh/PRTAllometricCNPMod.F90:2465-2578)`

## Step 3: `CNPAllocateRemainder` and PID Fine-Root Adjustment

Runs at `PRTAllometricCNPMod.F90:1830-2012`. Responsibilities:

1. **Fill nutrient storage toward the overflow target.** For every organ, compute the nutrient deficit against `GetNutrientTarget(..., stoich_growth_min)`. For the storage organ specifically, the target is inflated:

    ```fortran
    ! PRTAllometricCNPMod.F90:1879-1882
    if (l2g_organ_list(i) == store_organ) then
       target_n = target_n * (1 + prt_params%store_ovrflw_frac(ipft))
       target_p = target_p * (1 + prt_params%store_ovrflw_frac(ipft))
    end if
    ```

   `ProportionalNutrAllocation` then distributes remaining `n_gain` and `p_gain` proportional to these deficits. Note that `store_ovrflw_frac` is used as `target * (1 + f)`, which **inflates** the storage target rather than allowing an additional overflow on top.

2. **Call `CNPAdjustFRootTargets`** to update the PID controller state and `l2fr` (see next subsection). This is the only call site of the PID controller in the CNP module. During spinup's carbon-only adjustment period it is conditionally skipped (`PRTAllometricCNPMod.F90:1908-1913`).

3. **Park remaining carbon in storage overflow** (lines 1920-1961). The compile-time constant `store_c_overflow` (hard-coded at line 219 to `burn_c_store_overflow`) selects the fate:

    | Value | Meaning | Behavior |
    |---|---|---|
    | `burn_c_store_overflow` (default, **hard-coded**) | Park up to inflated target, respire the rest via `resp_excess` | lines 1929-1944 |
    | `exude_c_store_overflow` | Park up to inflated target; excess remains in `c_gain` for subsequent efflux | lines 1946-1957 |
    | `retain_c_store_overflow` | Put all remaining carbon into storage without cap | lines 1922-1927 |

    **This is not user-configurable via namelist or parameter file.** It is a Fortran `integer, parameter :: store_c_overflow = burn_c_store_overflow` at line 219. Changing it requires editing source and recompiling.

4. **Report effluxes** (lines 1990-2005). Under coupled nutrient uptake, any non-zero `n_gain`, `p_gain`, or `c_gain` at this point is assigned to `n_efflux`, `p_efflux`, `c_efflux` and zeroed. Under prescribed nutrient uptake, N and P effluxes are forced to zero; the remainder in `n_gain`/`p_gain` is re-interpreted as how much was actually consumed (see lines 688-697).

### PID Controller: `CNPAdjustFRootTargets`

Runs at `PRTAllometricCNPMod.F90:729-870`. This is a PID controller on the leaf-to-fine-root biomass scalar `l2fr`. Its process variable is the logarithm of the maximum of the relative carbon-to-nutrient storage ratios:

```
store_c_act   = max(0.001 * store_c_max, GetState(store, C) + bc_in(netdc))
store_n_act   = max(0.001 * store_n_max, GetState(store, N) + bc_inout(netdn))   ! inclusive of today's uptake
store_p_act   = max(0.001 * store_p_max, GetState(store, P) + bc_inout(netdp))

cn_ratio      = (store_c_act / store_c_max) / (store_n_act / store_n_max)
cp_ratio      = (store_c_act / store_c_max) / (store_p_act / store_p_max)

cx_logratio   = SafeLog( max(cp_ratio, cn_ratio) )      ! one-sided branches if N or P prescribed
```

When `cx_logratio > 0`, carbon storage is relatively fuller than nutrient storage (nutrient-limited); when `cx_logratio < 0`, nutrient storage is relatively fuller than carbon storage (carbon-limited). The controller output is:

```fortran
! PRTAllometricCNPMod.F90:838-858
cx_int     = cx_int + cx_logratio                          ! integral term (reset on sign change)
ema_dcxdt  = pid_drv_wgt * (cx_logratio - cx0) + (1 - pid_drv_wgt) * ema_dcxdt    ! derivative EMA, pid_drv_wgt = 1/20
cx0        = cx_logratio

l2fr_delta = pid_kp(ipft) * cx_logratio + &
             pid_ki(ipft) * cx_int      + &
             pid_kd(ipft) * ema_dcxdt

l2fr = max(l2fr_min, l2fr + l2fr_delta)                    ! l2fr_min = 0.01
```

**Higher `l2fr`** means a larger target fine-root biomass at a given leaf biomass (more roots per leaf), which is the response to positive `cx_logratio` (nutrient limitation). **Lower `l2fr`** means fewer roots per leaf, the response to carbon limitation.

### PID State Persists Across Days via `bc_inout`

The three PID state variables (`cx_int`, `cx0`, `ema_dcxdt`) are **not** stored as local Fortran scalars. They live in the cohort's `bc_inout` boundary condition array and are therefore checkpointed and restart-consistent alongside other cohort state:

```fortran
! PRTAllometricCNPMod.F90:161-163
integer, public, parameter :: acnp_bc_inout_id_cx_int   = 6
integer, public, parameter :: acnp_bc_inout_id_cx0      = 7
integer, public, parameter :: acnp_bc_inout_id_emadcxdt = 8

! lines 761-763
cx_int    => this%bc_inout(acnp_bc_inout_id_cx_int)%rval
cx0       => this%bc_inout(acnp_bc_inout_id_cx0)%rval
ema_dcxdt => this%bc_inout(acnp_bc_inout_id_emadcxdt)%rval
```

When diagnosing odd PID behavior, read or overwrite these three fields on the cohort's `prt%bc_inout` pointer. A sign-flip of `cx_logratio` resets `cx_int` to the new `cx_logratio` value to avoid integrator wind-up (lines 841-844). If both N and P are in prescribed-uptake mode, the controller short-circuits and zeros all three PID state variables (lines 817-822).

After the PID update, the routine recomputes `target_c(fnrt_organ)` using the new `l2fr` via `bfineroot` (line 867), and returns. On return to `DailyPRTAllometricCNP`, `TrimFineRoot` (lines 874-939) is called to forcefully remove fine-root biomass if the new target has dropped below the current pool.

Sources: `(parteh/PRTAllometricCNPMod.F90:729-870)`, `(parteh/PRTAllometricCNPMod.F90:161-163)`, `(parteh/PRTAllometricCNPMod.F90:874-939)`

## Boundary Conditions

The CNP class declares `num_bc_inout = 8`, `num_bc_in = 10`, `num_bc_out = 4` at `PRTAllometricCNPMod.F90:164,180,191`. All eight inout, ten input, and four output BCs are listed below.

### Input-Output BCs (`bc_inout`)

| Index | Constant | Description | Bound in `FatesCohortMod.F90` to |
|---|---|---|---|
| 1 | `acnp_bc_inout_id_dbh` | Diameter at breast height (cm) | `ccohort%dbh` |
| 2 | `acnp_bc_inout_id_resp_excess` | Respiration of excess (burned) storage (kgC/day) | `ccohort%resp_excess` |
| 3 | `acnp_bc_inout_id_l2fr` | Leaf-to-fine-root target biomass scalar (dimensionless) | `ccohort%l2fr` |
| 4 | `acnp_bc_inout_id_netdn` | Day's N pool: `daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily` (kgN/day) | `ccohort%daily_n_gain` |
| 5 | `acnp_bc_inout_id_netdp` | Day's P pool: `daily_p_gain` (kgP/day) | `ccohort%daily_p_gain` |
| 6 | `acnp_bc_inout_id_cx_int` | **PID integral term** (log-ratio, persistent) | `ccohort%cx_int` |
| 7 | `acnp_bc_inout_id_cx0` | **PID previous-step log ratio** (persistent) | `ccohort%cx0` |
| 8 | `acnp_bc_inout_id_emadcxdt` | **PID EMA of log-ratio derivative** (persistent, smoothing constant `pid_drv_wgt = 1/20`) | `ccohort%ema_dcxdt` |

The last three inout BCs are the PID state variables. They persist from day to day via the cohort structure and are restart-consistent. Diagnostic tooling that inspects PID behavior should read them directly from `ccohort%prt%bc_inout`.

Note on BC index 4: The wiki previously described this as "`daily_nh4_uptake + daily_no3_uptake`". The actual source value (`EDMainMod.F90:550-551`) is `daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily`, so symbiotic N fixation enters allocation through this BC on the same footing as soil uptake.

### Input BCs (`bc_in`)

| Index | Constant | Description |
|---|---|---|
| 1 | `acnp_bc_in_id_pft` | PFT index (integer) |
| 2 | `acnp_bc_in_id_ctrim` | Canopy trimming factor [0-1] (real) |
| 3 | `acnp_bc_in_id_lstat` | Leaf phenology status (`leaves_on`/`leaves_off`/`leaves_shedding`, integer) |
| 4 | `acnp_bc_in_id_netdc` | Net daily C balance (NPP after MR, kgC/day) |
| 5 | `acnp_bc_in_id_nc_repro` | Reproductive tissue N:C stoichiometry (real) |
| 6 | `acnp_bc_in_id_pc_repro` | Reproductive tissue P:C stoichiometry (real) |
| 7 | `acnp_bc_in_id_cdamage` | Crown damage class (integer) |
| 8 | `acnp_bc_in_id_efleaf` | **Leaf elongation factor [0-1]** (phenology gate) |
| 9 | `acnp_bc_in_id_effnrt` | **Fine-root elongation factor [0-1]** |
| 10 | `acnp_bc_in_id_efstem` | **Stem elongation factor [0-1]** |

The three elongation-factor inputs are consumed inside the allometry calls (`bleaf`, `bfineroot`, `bsap_allom`, `bagw_allom`, `bbgw_allom`) to scale target biomass based on phenological stage. The CNP routine never stores or modifies them.

### Output BCs (`bc_out`)

| Index | Constant | Description |
|---|---|---|
| 1 | `acnp_bc_out_id_cefflux` | Daily carbon exudation [kgC] |
| 2 | `acnp_bc_out_id_nefflux` | Daily nitrogen exudation [kgN] |
| 3 | `acnp_bc_out_id_pefflux` | Daily phosphorus exudation [kgP] |
| 4 | `acnp_bc_out_id_limiter` | Growth limiter flag (`0=cnp_co_limited`, `1=c_limited`, `2=n_limited`, `3=p_limited`) |

`limiter` is reported by `CNPStatureGrowth` after the equivalent-carbon calculation; see the caveat about the mid-routine reset at line 1394.

Sources: `(parteh/PRTAllometricCNPMod.F90:155-192)`, `(main/EDMainMod.F90:550-551)`

## Nutrient Limitation Flag

`bc_out%limiter` reports which element is limiting growth during the current `CNPStatureGrowth` pass:

| Constant | Value | Meaning |
|---|---|---|
| `cnp_limited` | 0 | Co-limited or no single element flagged |
| `c_limited` | 1 | Carbon tapped first |
| `n_limited` | 2 | N-equivalent carbon is smallest |
| `p_limited` | 3 | P-equivalent carbon is smallest |

Declared at `PRTAllometricCNPMod.F90:224-227`. Note: at line 1394 `limiter` is forcibly reset to 0 **before** the equivalent-carbon branch assigns the final value, so the final reported value always comes from the `grow_lim_estNP` block if stature growth proceeds. If stature growth is skipped (no C, no N, or no P left after step 1), `limiter` retains whatever was set at line 1386-1392 then possibly overridden at line 1394.

## Symbiotic N Fixation

Symbiotic N fixation is **not** implemented in `PRTAllometricCNPMod`. It is computed inside `FatesPlantRespPhotosynthMod::RootLayerNFixation` at `biogeophys/FatesPlantRespPhotosynthMod.F90:965-1017`, accumulated daily on `ccohort%sym_nfix_daily` via `EDAccumulateFluxesMod`, then folded into `daily_n_gain` in `EDMainMod.F90:550-551` before `DailyPRT(phase=1)` is called.

The governing formula (Houlton et al. 2008, Fisher et al. 2010) uses `prt_params%nfix_mresp_scfrac(ft)` (CDL name: `fates_cnp_nfix1`), applied as a scale factor on fine-root maintenance respiration:

```fortran
! FatesPlantRespPhotosynthMod.F90:1004-1014
fnrt_mr_nfix_layer  = fnrt_mr_layer * prt_params%nfix_mresp_scfrac(ft)
c_cost_nfix         = s_fix * ( exp(a_fix + b_fix * (t_soil - tfrz) * (1 - 0.5*(t_soil - tfrz)/c_fix)) - 2 )
c_spent_nfix        = fnrt_mr_nfix_layer * dtime
nfix_layer          = c_spent_nfix / c_cost_nfix
```

Where `s_fix = -6.25`, `a_fix = -3.62`, `b_fix = 0.27`, `c_fix = 25.15` (temperature-response constants from Houlton et al. 2008).

Sources: `(biogeophys/FatesPlantRespPhotosynthMod.F90:965-1017)`, `(main/EDMainMod.F90:550-551,757)`

## Key Parameters

| Parameter | Fortran field | Allocation role |
|---|---|---|
| `fates_cnp_pid_kp` | `prt_params%pid_kp(ipft)` | PID proportional gain on `cx_logratio` |
| `fates_cnp_pid_ki` | `prt_params%pid_ki(ipft)` | PID integral gain on `cx_int` |
| `fates_cnp_pid_kd` | `prt_params%pid_kd(ipft)` | PID derivative gain on `ema_dcxdt` |
| `fates_cnp_store_ovrflw_frac` | `prt_params%store_ovrflw_frac(ipft)` | Inflates storage nutrient/carbon target to `target * (1 + f)` in `CNPAllocateRemainder` and in `stoich_max` queries |
| `fates_cnp_turnover_nitr_retrans` | `prt_params%turnover_nitr_retrans(ipft, organ_param_id)` | N retranslocation fraction on turnover (leaf, fnrt only; must be 0 for sapw/struct) |
| `fates_cnp_turnover_phos_retrans` | `prt_params%turnover_phos_retrans(ipft, organ_param_id)` | P retranslocation fraction on turnover |
| `fates_cnp_vmax_nh4` | `EDPftvarcon_inst%vmax_nh4(pft)` | Max NH4 uptake per fine-root C [kgN/kgC/s] |
| `fates_cnp_vmax_no3` | `EDPftvarcon_inst%vmax_no3(pft)` | Max NO3 uptake per fine-root C [kgN/kgC/s] |
| `fates_cnp_vmax_p` | `EDPftvarcon_inst%vmax_p(pft)` | Max P uptake per fine-root C [kgP/kgC/s] |
| `fates_cnp_prescribed_nuptake` | `EDPftvarcon_inst%prescribed_nuptake(pft)` | Fraction of demand satisfied under prescribed N uptake |
| `fates_cnp_prescribed_puptake` | `EDPftvarcon_inst%prescribed_puptake(pft)` | Declared but **not consumed** in `UnPackNutrientAquisitionBCs` — P prescribed uptake uses `prescribed_nuptake` as the scaling factor (see `FatesSoilBGCFluxMod.F90:202`). This is likely a source-level issue, not a documentation issue. |
| `fates_cnp_nitr_store_ratio` | `prt_params%nitr_store_ratio(ipft)` | Storage N target as fraction of tissue N (used by `StorageNutrientTarget`) |
| `fates_cnp_phos_store_ratio` | `prt_params%phos_store_ratio(ipft)` | Storage P target as fraction of tissue P |
| `fates_cnp_nfix1` | `prt_params%nfix_mresp_scfrac(ft)` | Sym N fixation scale on fine-root maintenance respiration |
| `fates_stoich_nitr` | `prt_params%nitr_stoich_p1(ipft, organ_param_id)` | Growth-min N:C per organ |
| `fates_stoich_phos` | `prt_params%phos_stoich_p1(ipft, organ_param_id)` | Growth-min P:C per organ |
| `fates_alloc_organ_priority` | `prt_params%alloc_priority(ipft, :)` | Priority level for each organ in `CNPPrioritizedReplacement`. Storage is hard-coded to priority 2 independent of this parameter. |
| `fates_alloc_storage_cushion` | `prt_params%cushion(ipft)` | Allometric multiplier on storage target |
| `fates_alloc_store_priority_frac` | `prt_params%leaf_stor_priority(ipft)` | Fraction of turnover demand to prepay at priority 1 |

Sources: `(parteh/PRTParamsFATESMod.F90:268-621)`, `(main/EDPftvarcon.F90)` (vmax/prescribed/decompmicc fields), `(biogeochem/FatesSoilBGCFluxMod.F90:155-225)`

## Design Notes for Calibration

- **Trust the subroutine names, not the argument.** `DailyPRT(phase)` is called three times per day but CNP ignores all but `phase=1`. All CNP work happens inside a single `DailyPRTAllometricCNP` invocation.
- **Retranslocation is upstream of allocation.** If a hypothesis involves "retranslocation changes the allocation step", remember that the CNP routine sees retranslocation only as pre-filled nutrient storage, which Step 0.5 drains into `n_gain`/`p_gain`. There is no separate retranslocation path inside `CNPPrioritizedReplacement`.
- **PID state is persistent.** An aggressive `pid_kp` can drive `l2fr` to one extreme and leave `cx_int` wound up. Reading `cx_int`, `cx0`, `ema_dcxdt` from the restart file is the fastest way to diagnose runaway `l2fr` trajectories.
- **`store_c_overflow` is compile-time.** The default and only behavior without a source rebuild is `burn_c_store_overflow`, which routes unspendable carbon into `resp_excess` and increments the exudation counters to zero. `exude_` and `retain_` paths require editing `PRTAllometricCNPMod.F90:219`.
- **`store_ovrflw_frac` inflates the storage target** rather than letting storage build beyond the allometric value. A larger `store_ovrflw_frac` raises the ceiling at which storage parks extra C/N/P in Step 3 **and** pushes the growth-min storage nutrient target higher in Step 1 (via the `GetNutrientTarget` stoich_max branch used in the overflow check).
- **`fates_alloc_organ_priority`** only influences priority level 1 onwards for non-storage organs; storage's priority is hard-coded to level 2 at `PRTAllometricCNPMod.F90:1178-1181`.
- **Sapwood and structure retranslocation must be zero.** `PRTParamsFATESMod.F90:1319-1348` will abort the run otherwise.

Sources: `(parteh/PRTAllometricCNPMod.F90:1178-1181)`, `(parteh/PRTAllometricCNPMod.F90:1879-1882)`, `(parteh/PRTAllometricCNPMod.F90:1922-1944)`, `(parteh/PRTAllometricCNPMod.F90:219)`, `(parteh/PRTParamsFATESMod.F90:1319-1348)`
