# CNP Allocation and Nutrient Dynamics

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
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
- `biogeochem/FatesCohortMod.F90`
- `biogeophys/FatesPlantRespPhotosynthMod.F90`
- `biogeophys/EDAccumulateFluxesMod.F90`
- `main/FatesConstantsMod.F90`
- `main/FatesInterfaceTypesMod.F90`

## Purpose and Scope

This document describes the Carbon-Nitrogen-Phosphorus (CNP) allocation hypothesis in FATES PARTEH (`prt_cnp_flex_allom_hyp = 2`). The CNP hypothesis extends the carbon-only hypothesis to simultaneously track 18 state variables (6 organs x 3 elements) and to dynamically adjust the leaf-to-fine-root target biomass ratio (`l2fr`) via a PID controller that responds to the relative fill level of the carbon and nutrient storage pools — when the controller is active (see "PID Gating" below).

For the carbon-only hypothesis see [Carbon-Only Allocation](./carbon_only.md). For the soil-plant uptake interface and competition modes see [Soil-Plant Nutrient Interface](./soil_plant_interface.md). For the PARTEH framework see [PARTEH: Plant Allocation System](./index.md).

CNP allocation is a calibration-critical module. The following sections are structured to correctly represent the algorithm as it exists in source, with explicit pointers to each subroutine and line range.

## High-Level Flow for One Daily Call

The CNP hypothesis runs exactly **once per plant per day**, inside a single call to `prt%DailyPRT(phase=1)` (see `DailyPRT` Semantics below). During that one call, the routine `DailyPRTAllometricCNP` in `PRTAllometricCNPMod.F90:374-711` executes the following internal steps in order:

| Internal step (wiki label) | What it does | Subroutine | Source-comment label |
|---|---|---|---|
| Step 0 | Compute carbon allometry targets (`target_c`, `target_dcdd`) for every organ from current DBH | inline (lines 489-501) | "Step 1" (line 504) |
| Step 0.5 | Move any carbon storage above target and **all** nutrient storage into the daily `c_gain`/`n_gain`/`p_gain` pool | inline (lines 538-546) | "Step 0" (line 533) |
| Step 1 (Prioritized Replacement) | Replenish tissues up to current allometric targets in priority order, settle the carbon-balance sign (storage draw or storage deposit), and top up nutrients to the growth-minimum stoichiometry | `CNPPrioritizedReplacement` (lines 947-1280) | "Step 2" (line 550) |
| Step 2 (Stature Growth) | Project nutrient-equivalent carbon, choose the limiter, integrate a stature-growth step along the allometric curve (Euler), then push nutrients onto the newly built tissues | `CNPStatureGrowth` (lines 1285-1830) | "Step 3" (line 573) |
| Step 3 (Allocate Remainder) | Refill nutrient storage up to `target * (1 + store_ovrflw_frac)`, conditionally call the PID `CNPAdjustFRootTargets` to update `l2fr`, then put remaining carbon into storage overflow (burn/exude/retain), then zero or report efflux | `CNPAllocateRemainder` (lines 1834-2015), `CNPAdjustFRootTargets` (lines 733-874) | "Step 3" (line 598) |
| Cleanup | Update `net_alloc` diagnostics, call `TrimFineRoot` to forcefully shrink fine-roots if `l2fr` dropped | `TrimFineRoot` (lines 878-943) | n/a |

The wiki uses cleaner step numbering (0/0.5/1/2/3) than the source comments. The source comments label internal blocks at lines 504, 533, 550, 573, 598 with "Step 1, Step 0, Step 2, Step 3, Step 3" — a numbering that is locally inconsistent (the third Allocate-Remainder block also reads "Step 3"). Treat the wiki labels as canonical for cross-referencing.

Sources: `(parteh/PRTAllometricCNPMod.F90:374-711,947-1280,1285-1830,1834-2015)`

## `DailyPRT` Semantics: What `phase` Really Means

`EDMainMod::ed_integrate_state_variables` calls `prt%DailyPRT(phase)` three times per cohort with `phase = 1, 2, 3` (`main/EDMainMod.F90:615, 618, 634`). This is **not** the "three-phase CNP allocation". It exists to give the damage module its own entry points. The CNP routine is not yet compatible with damage and therefore ignores all calls except the first:

```fortran
! PRTAllometricCNPMod.F90:434-437
! Phasing is only used to accomodate the
! damage module. Since this is incompatible with CNP
! Ignore all subsequent calls after the first
if (phase.ne.1) return
```

Consequence: **for CNP, the entire three-step internal algorithm (Prioritized Replacement -> Stature Growth -> Allocate Remainder) runs inside a single `DailyPRT(phase=1)` call via sequential internal calls** at `PRTAllometricCNPMod.F90:554, 579, 603`. The word "phase" in this document refers to the three internal steps, not to the `DailyPRT` argument.

Sources: `(parteh/PRTAllometricCNPMod.F90:434-437,554,579,603)`, `(main/EDMainMod.F90:615,618,634)`

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

## Retranslocation: Happens BEFORE `DailyPRT`, not inside CNP

The retranslocation step (moving nutrients from senescing leaves/fine-roots into the storage pool before the tissue mass leaves the plant) is **not** executed inside `DailyPRTAllometricCNP`. It is executed earlier in the daily loop, in the turnover routines.

Caller sequence in `EDMainMod::ed_integrate_state_variables`:

```
1. call PRTMaintTurnover(...)                       [EDMainMod.F90:568]
2. (retranslocation happens inside MaintTurnoverSimpleRetranslocation, PRTLossFluxesMod.F90:652)
3. currentCohort%daily_n_gain = daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily   [EDMainMod.F90:583-584]
4. call currentCohort%prt%DailyPRT(phase=1)         [EDMainMod.F90:615]
      |-- DailyPRTAllometricCNP runs the 3-step algorithm
```

Separately, for deciduous leaf-drop events, `EDPhysiologyMod::phenology_leafonoff` calls `PRTDeciduousTurnover` at `EDPhysiologyMod.F90:1739-1750`, which dispatches to `DeciduousTurnoverSimpleRetranslocation` in `PRTLossFluxesMod.F90:505-628`.

Both retranslocation paths implement the same rule. A fraction `retrans` of the nutrient (not carbon) mass that would otherwise leave the plant is instead added to the storage pool's `val` and `net_alloc`, and the remaining `(1 - retrans) * turnover` is sent to the turnover/litter flux:

```fortran
! PRTLossFluxesMod.F90:573-619, maintenance path analogous (lines 632-866)
if (element_id == carbon12_element)   retrans = 0
if (element_id == nitrogen_element)   retrans = prt_params%turnover_nitr_retrans(ipft, organ_param_id(organ_id))
if (element_id == phosphorus_element) retrans = prt_params%turnover_phos_retrans(ipft, organ_param_id(organ_id))

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
| `fates_cnp_turnover_nitr_retrans` | leaf, fnrt (and storage where its organ_param_id maps to a tracked pool) | [0, 1] | `PRTParamsFATESMod.F90:989-1054` |
| `fates_cnp_turnover_phos_retrans` | leaf, fnrt | [0, 1] | `PRTParamsFATESMod.F90:989-1054` |

The parameter file must set `turnover_*_retrans` to **exactly zero** for sapwood and structure. The validation routine will abort the run if any non-zero value is supplied for sapw or struct (`PRTParamsFATESMod.F90:992-1011`). Carbon retrans must also be zero across all organs (lines 1014-1031). All other organs must lie in `[0, 1]` (lines 1037-1054).

Sources: `(parteh/PRTLossFluxesMod.F90:505-628)` (deciduous), `(parteh/PRTLossFluxesMod.F90:632-870)` (maintenance), `(main/EDMainMod.F90:568,583-584,615)`, `(biogeochem/EDPhysiologyMod.F90:1739-1750)`, `(parteh/PRTParamsFATESMod.F90:989-1054)`

## Step 0.5: Transfer Storage Into the Daily Pool

At the top of `DailyPRTAllometricCNP`, carbon storage **above** its allometric target and **all** nitrogen and phosphorus storage are transferred into the day's gain pools, which the rest of the routine will spend down:

```fortran
! PRTAllometricCNPMod.F90:538-546
store_flux = max(0, store_c_val - target_c(store_organ))
c_gain = c_gain + store_flux
store_c_val = store_c_val - store_flux

n_gain = n_gain + sum(store_n_val(:))
store_n_val(:) = 0

p_gain = p_gain + sum(store_p_val(:))
store_p_val(:) = 0
```

Carbon storage is only **partially** drained (only the amount above allometry). Nutrient storage is fully drained every day. This is why retranslocation accumulates into storage and then immediately re-enters the allocation pool.

Note also that lines 471-479 force `n_gain` and `p_gain` to `1.e3 kg` (effectively unlimited) when `n_uptake_mode == prescribed_n_uptake` or `p_uptake_mode == prescribed_p_uptake`. At e027a40 the JSON defaults `fates_cnp_prescribed_nuptake = fates_cnp_prescribed_puptake = 0.0` mean coupled mode is the default operational path; prescribed mode is an experimental opt-in (see [Soil-Plant Interface](./soil_plant_interface.md)).

Sources: `(parteh/PRTAllometricCNPMod.F90:471-479,538-546)`

## Step 1: `CNPPrioritizedReplacement`

Runs at `PRTAllometricCNPMod.F90:947-1280`. Does five things in order:

1. **Identify priority-1 organs** from `prt_params%alloc_priority(ipft, :)` (parameter `fates_alloc_organ_priority`). Leaves are excluded from the priority-1 list when leaves are off or shedding, and also when the PFT is not evergreen (to prevent accidental re-flushing). Only priority-1 organs receive carbon for maintenance-turnover replacement in this block.

2. **Pay maintenance turnover for priority-1 organs.** The demand is

    ```
    sum_c_demand = leaf_stor_priority(ipft) x sum(turnover(:))
    ```

   (summed over priority-1 organs). The actual flux is capped by what is available in storage plus carbon gain: `sum_c_flux = max(0, min(sum_c_demand, store_c + c_gain))`. Distribution to each priority-1 organ is proportional to its share of the demand.

3. **Top up nitrogen and phosphorus** for priority-1 organs to their growth-minimum stoichiometry target (`GetNutrientTarget(..., stoich_growth_min)`), via `ProportionalNutrAllocation`, drawing from `n_gain` and `p_gain` respectively.

4. **Handle the carbon-balance sign.** If `c_gain < 0` after step 2, storage pays the deficit. If `c_gain > 0`, a fraction of the remainder is placed into storage using a saturating function:

    ```
    store_target_fraction = store_c_val / target_c(store_organ)
    store_demand          = max(c_gain * (exp(-store_target_fraction**4) - exp(-1)), 0)
    store_c_flux          = min(store_below_target, store_demand)
    ```

   This causes storage to receive a large fraction of `c_gain` when nearly empty and a vanishing share when near target.

5. **Loop over remaining priority levels 1..n_max_priority**, filling each organ up to `target_c(organ)` and then up to its nutrient stoichiometry. Storage has a **hard-coded** priority level of 2 (independent of the `fates_alloc_organ_priority` parameter for storage). All other organ priority levels come from `prt_params%alloc_priority(ipft, :)`. Carbon is transferred proportionally to deficit within each priority level. Nutrients follow via `ProportionalNutrAllocation`.

After Step 1, all carbon pools are at or above their allometric targets, carbon balance is >= 0, and remaining `c_gain`/`n_gain`/`p_gain` are available for stature growth.

Sources: `(parteh/PRTAllometricCNPMod.F90:947-1280)`

## Step 2: `CNPStatureGrowth`

Runs at `PRTAllometricCNPMod.F90:1285-1830`. Grows DBH along the allometric curve, simultaneously growing all carbon pools that remain active after fusion masking.

### Equivalent-Carbon Limiter

Before integrating, the routine projects how much carbon it can actually spend given the nutrient supply. It calls `EstimateGrowthNC(this, target_c, target_dcdd, state_mask, avg_nc, avg_pc)` (`PRTAllometricCNPMod.F90:2461-2579`), which computes the `target_dcdd`-weighted average N:C and P:C ratios across all growing organs (including reproduction, leaf, fine root, sapwood, structure, storage). The stature-growth carbon is then:

```fortran
! PRTAllometricCNPMod.F90 (within CNPStatureGrowth, grow_lim_estNP branch)
neq_cgain = n_gain / avg_nc        ! how much C the N pool can support at growth stoichiometry
peq_cgain = p_gain / avg_pc        ! how much C the P pool can support

if c_gain < neq_cgain:
    if c_gain < peq_cgain:  c_gstature = c_gain;     limiter = c_limited
    else:                   c_gstature = peq_cgain;  limiter = p_limited
else:
    if neq_cgain < peq_cgain: c_gstature = neq_cgain; limiter = n_limited
    else:                     c_gstature = peq_cgain; limiter = p_limited
```

This is the "equivalent carbon" method. `c_gstature` is the minimum carbon among C, N-equivalent, and P-equivalent, which becomes the growth-step mass. Note that `limiter` is first assigned using loose thresholds on `c_gain`, `n_gain`, `p_gain`, then **immediately overwritten to 0** at line 1398 (`limiter = 0` reset), then reassigned inside the `grow_lim_estNP` branch. Readers inspecting `bc_out(acnp_bc_out_id_limiter)` should know the final value comes from the `grow_lim_estNP` block, not from the earlier threshold test.

### Integration

With `c_gstature` in hand, stature growth integrates the C pools plus DBH along the allometric curve. The active integrator is Euler (`ODESolve = 2`, hard-coded in `CNPStatureGrowth`). An adaptive step attempt is made at each iteration. The state is advanced and `CheckIntegratedAllometries` verifies pools remain within `max_trunc_error` of their current allometric targets. On failure the step is halved and retried, up to `max_substeps = 300`. Exceeding that aborts with a diagnostic dump of pool values, targets, and elongation factors.

The integrator updates `state_array`, which includes `leaf_id, fnrt_id, sapw_id, store_id, struct_id, repro_id, dbh_id`. After convergence, a proportional correction forces the total carbon flux to exactly equal `c_gstature`, then DBH is committed.

### Post-Integration Nutrient Allocation

After growth, N and P are deposited on the newly built tissues proportional to their demand vs the growth-min stoichiometry. Reproduction is prioritized via an optional first pass (when `prioritize_repro_nutr_growth = .true.`, set as a module parameter at `PRTAllometricCNPMod.F90:243`) before the general proportional call.

If any limiting resource is effectively tapped out (`c_gain <= calloc_abs_error`, `n_gain <= 0.1*calloc_abs_error`, or `p_gain <= 0.02*calloc_abs_error`) or leaves are off/shedding, stature growth is skipped entirely.

Sources: `(parteh/PRTAllometricCNPMod.F90:1285-1830,2461-2579)`

## Step 3: `CNPAllocateRemainder` and PID Fine-Root Adjustment

This step is the canonical **storage allocation** entry point in CNP PARTEH: any leftover daily carbon (after Steps 1 and 2 have replenished tissues and grown stature) is directed into the storage organ, with the overflow target inflated by `store_ovrflw_frac` so that storage can build up across multiple days. Runs at `PRTAllometricCNPMod.F90:1834-2015`. Responsibilities:

1. **Fill nutrient storage toward the overflow target.** For every organ, compute the nutrient deficit against `GetNutrientTarget(..., stoich_growth_min)`. For the storage organ specifically, the target is inflated:

    ```fortran
    ! PRTAllometricCNPMod.F90:1882-1885
    if (l2g_organ_list(i) == store_organ) then
       target_n = target_n * (1 + prt_params%store_ovrflw_frac(ipft))
       target_p = target_p * (1 + prt_params%store_ovrflw_frac(ipft))
    end if
    ```

   `ProportionalNutrAllocation` then distributes remaining `n_gain` and `p_gain` proportional to these deficits. Note that `store_ovrflw_frac` is used as `target * (1 + f)`, which **inflates** the storage target rather than allowing an additional overflow on top.

2. **Conditionally call `CNPAdjustFRootTargets`** to update the PID controller state and `l2fr` (see "PID Gating at e027a40" below).

3. **Park remaining carbon in storage overflow** (lines 1923-1964). The compile-time constant `store_c_overflow` (hard-coded at line 223 to `burn_c_store_overflow`) selects the fate:

    | Value | Meaning | Behavior |
    |---|---|---|
    | `burn_c_store_overflow` (default, **hard-coded**) | Park up to inflated target, respire the rest via `resp_excess` | lines 1932-1947 |
    | `exude_c_store_overflow` | Park up to inflated target; excess remains in `c_gain` for subsequent efflux | lines 1949-1962 |
    | `retain_c_store_overflow` | Put all remaining carbon into storage without cap | lines 1925-1930 |

    **This is not user-configurable via namelist or parameter file.** It is a Fortran `integer, parameter :: store_c_overflow = burn_c_store_overflow` at line 223. Changing it requires editing source and recompiling.

4. **Report effluxes** (lines 1993-2008). Under coupled nutrient uptake, any non-zero `n_gain`, `p_gain`, or `c_gain` at this point is assigned to `n_efflux`, `p_efflux`, `c_efflux` and zeroed. Under prescribed nutrient uptake, N and P effluxes are forced to zero. The remainder in `n_gain`/`p_gain` is re-interpreted as how much was actually consumed (see `DailyPRTAllometricCNP` lines 692-701).

### PID Gating at e027a40 (BEHAVIOR CHANGED)

At e027a40 the PID call site `CNPAdjustFRootTargets` is **only invoked when at least one nutrient is in coupled-uptake mode AND the host model is not supplementing that nutrient**:

```fortran
! PRTAllometricCNPMod.F90:1909-1915 (intent shown; see source-level note below)
! turn on the dynamic L2FR if either nutrient in not being supplemented
limiting_p = ((p_uptake_mode .eq. coupled_p_uptake) .and. (hlm_phosphorus_suppl .eq. ifalse))
limiting_n = ((n_uptake_mode .eq. coupled_n_uptake) .and. (hlm_nitrogen_suppl .eq. ifalse))

if (limiting_p .or. limiting_n) then
   call this%CNPAdjustFRootTargets(target_c,target_dcdd)
end if
```

Two new module-level flags `hlm_nitrogen_suppl` and `hlm_phosphorus_suppl` (imported from `FatesInterfaceTypesMod` at `PRTAllometricCNPMod.F90:76-77`) feed this gate. They are written by `UnPackNutrientAquisitionBCs` (`FatesSoilBGCFluxMod.F90:140-150`) from the new `nitr_suppl, phos_suppl` arguments passed by the host. See [Soil-Plant Interface](./soil_plant_interface.md) for the full unpack signature.

**Calibration consequences**:

- Under prescribed-uptake mode (either N or P), `limiting_*` is `.false.` for that nutrient. If both are prescribed, the PID is skipped entirely and `l2fr` is frozen at its current value.
- Under HLM nutrient supplementation (e.g. supplemental-N spinup runs), the corresponding `hlm_*_suppl` flag is `.true.`, which also disables the PID for that nutrient.
- Under standard coupled CNP runs (no supplementation), the PID runs as before.
- A2MC calibration runs that toggle `prescribed_nuptake` or `prescribed_puptake` to non-zero values to test prescribed mode will silently freeze `l2fr`. Reading `cx_int`, `cx0`, `ema_dcxdt` from the restart file will show no movement.

**Source-level note (functionally inert today, fragile)**: the actual source at `PRTAllometricCNPMod.F90:1911` reads `limiting_n = ((n_uptake_mode .eq. coupled_p_uptake) .and. ...)`, comparing `n_uptake_mode` against `coupled_p_uptake` instead of `coupled_n_uptake`. Both constants are defined as integer `2` in `FatesConstantsMod.F90:114, 119`, so the gate evaluates correctly today, but the intent is `coupled_n_uptake`. If those constants ever diverge, the N-side gate will silently break. The block above shows the corrected intent for clarity.

Sources: `(parteh/PRTAllometricCNPMod.F90:76-77,1909-1915)`, `(biogeochem/FatesSoilBGCFluxMod.F90:140-150)`, `(main/FatesConstantsMod.F90:113-119)`

### PID Controller: `CNPAdjustFRootTargets`

When the gate above admits the call, the controller runs at `PRTAllometricCNPMod.F90:733-874`. It is a PID controller on the leaf-to-fine-root biomass scalar `l2fr`. Its process variable is the logarithm of the maximum of the relative carbon-to-nutrient storage ratios:

```
store_c_act   = max(0.001 * store_c_max, GetState(store, C) + bc_in(netdc))
store_n_act   = max(0.001 * store_n_max, GetState(store, N) + bc_inout(netdn))   ! inclusive of today's uptake
store_p_act   = max(0.001 * store_p_max, GetState(store, P) + bc_inout(netdp))

cn_ratio      = (store_c_act / store_c_max) / (store_n_act / store_n_max)
cp_ratio      = (store_c_act / store_c_max) / (store_p_act / store_p_max)

cx_logratio   = SafeLog( max(cp_ratio, cn_ratio) )      ! one-sided branches if N or P prescribed
```

When `cx_logratio > 0`, carbon storage is relatively fuller than nutrient storage (nutrient-limited). When `cx_logratio < 0`, nutrient storage is relatively fuller than carbon storage (carbon-limited). The controller output is:

```fortran
! PRTAllometricCNPMod.F90:842-868
cx_int     = cx_int + cx_logratio                          ! integral term (reset on sign change)
ema_dcxdt  = pid_drv_wgt * (cx_logratio - cx0) + (1 - pid_drv_wgt) * ema_dcxdt    ! derivative EMA, pid_drv_wgt = 1/20
cx0        = cx_logratio

l2fr_delta = pid_kp(ipft) * cx_logratio + &
             pid_ki(ipft) * cx_int      + &
             pid_kd(ipft) * ema_dcxdt

l2fr = max(l2fr_min, l2fr + l2fr_delta)                    ! l2fr_min = 0.01
```

**Higher `l2fr`** means a larger target fine-root biomass at a given leaf biomass (more roots per leaf), which is the response to positive `cx_logratio` (nutrient limitation). **Lower `l2fr`** means fewer roots per leaf, the response to carbon limitation.

If both N and P are in prescribed-uptake mode, the controller short-circuits and zeros all three PID state variables (lines 821-826). At e027a40 this branch is unreachable in practice because the outer gate at lines 1909-1915 already prevents the call when neither nutrient is coupled-and-not-supplemented. The internal short-circuit remains as a defensive null-state.

A sign-flip of `cx_logratio` resets `cx_int` to the new `cx_logratio` value to avoid integrator wind-up (lines 845-849).

After the PID update, the routine recomputes `target_c(fnrt_organ)` using the new `l2fr` via `bfineroot` (line 871). On return to `DailyPRTAllometricCNP`, `TrimFineRoot` (lines 878-943) is called to forcefully remove fine-root biomass if the new target has dropped below the current pool.

### PID State Persists Across Days via `bc_inout`

The three PID state variables (`cx_int`, `cx0`, `ema_dcxdt`) are **not** stored as local Fortran scalars. They live in the cohort's `bc_inout` boundary condition array and are therefore checkpointed and restart-consistent alongside other cohort state:

```fortran
! PRTAllometricCNPMod.F90:165-167
integer, public, parameter :: acnp_bc_inout_id_cx_int   = 6
integer, public, parameter :: acnp_bc_inout_id_cx0      = 7
integer, public, parameter :: acnp_bc_inout_id_emadcxdt = 8

! lines 765-767
cx_int    => this%bc_inout(acnp_bc_inout_id_cx_int)%rval
cx0       => this%bc_inout(acnp_bc_inout_id_cx0)%rval
ema_dcxdt => this%bc_inout(acnp_bc_inout_id_emadcxdt)%rval
```

These BCs are bound to cohort fields `ccohort%cx_int, ccohort%cx0, ccohort%ema_dcxdt` in `FatesCohortMod.F90:909-911` via `RegisterBCInOut`. When diagnosing odd PID behavior, read or overwrite these three fields on the cohort's `prt%bc_inout` pointer.

Sources: `(parteh/PRTAllometricCNPMod.F90:733-874,165-167)`, `(parteh/PRTAllometricCNPMod.F90:878-943)`, `(biogeochem/FatesCohortMod.F90:909-911)`

## Boundary Conditions

The CNP class declares `num_bc_inout = 8`, `num_bc_in = 10`, `num_bc_out = 4` at `PRTAllometricCNPMod.F90:168, 184, 195`. All eight inout, ten input, and four output BCs are listed below.

### Input-Output BCs (`bc_inout`)

| Index | Constant | Description | Bound in `FatesCohortMod.F90` to |
|---|---|---|---|
| 1 | `acnp_bc_inout_id_dbh` | Diameter at breast height (cm) | `ccohort%dbh` (line 906) |
| 2 | `acnp_bc_inout_id_resp_excess` | Respiration of excess (burned) storage (kgC/day) | `ccohort%resp_excess_hold` (line 907) |
| 3 | `acnp_bc_inout_id_l2fr` | Leaf-to-fine-root target biomass scalar (dimensionless) | `ccohort%l2fr` (line 908) |
| 4 | `acnp_bc_inout_id_netdn` | Day's N pool: `daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily` (kgN/day) | `ccohort%daily_n_gain` (line 913) |
| 5 | `acnp_bc_inout_id_netdp` | Day's P pool: `daily_p_gain` (kgP/day) | `ccohort%daily_p_gain` (line 914) |
| 6 | `acnp_bc_inout_id_cx_int` | **PID integral term** (log-ratio, persistent) | `ccohort%cx_int` (line 909) |
| 7 | `acnp_bc_inout_id_cx0` | **PID previous-step log ratio** (persistent) | `ccohort%cx0` (line 911) |
| 8 | `acnp_bc_inout_id_emadcxdt` | **PID EMA of log-ratio derivative** (persistent, smoothing constant `pid_drv_wgt = 1/20`) | `ccohort%ema_dcxdt` (line 910) |

The last three inout BCs are the PID state variables. They persist from day to day via the cohort structure and are restart-consistent. Diagnostic tooling that inspects PID behavior should read them directly from `ccohort%prt%bc_inout`.

Note on BC index 4: `daily_n_gain` is computed at `EDMainMod.F90:583-584` as `daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily`. Symbiotic N fixation enters allocation through this BC on the same footing as soil uptake.

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
| 4 | `acnp_bc_out_id_limiter` | Growth limiter flag (`0=cnp_limited`, `1=c_limited`, `2=n_limited`, `3=p_limited`) |

`limiter` is reported by `CNPStatureGrowth` after the equivalent-carbon calculation (see the caveat about the mid-routine reset to 0 at line 1398).

Sources: `(parteh/PRTAllometricCNPMod.F90:159-195)`, `(main/EDMainMod.F90:583-584)`, `(biogeochem/FatesCohortMod.F90:906-914)`

## Nutrient Limitation Flag

`bc_out%limiter` reports which element is limiting growth during the current `CNPStatureGrowth` pass:

| Constant | Value | Meaning |
|---|---|---|
| `cnp_limited` | 0 | Co-limited or no single element flagged |
| `c_limited` | 1 | Carbon tapped first |
| `n_limited` | 2 | N-equivalent carbon is smallest |
| `p_limited` | 3 | P-equivalent carbon is smallest |

Declared at `PRTAllometricCNPMod.F90:228-231`. Note: `limiter` is forcibly reset to 0 (`limiter = 0`) **before** the equivalent-carbon branch assigns the final value, so the final reported value always comes from the `grow_lim_estNP` block if stature growth proceeds. If stature growth is skipped (no C, no N, or no P left after step 1), `limiter` retains the reset value.

## Symbiotic N Fixation

Symbiotic N fixation is **not** implemented in `PRTAllometricCNPMod`. It is computed inside `FatesPlantRespPhotosynthMod::RootLayerNFixation` at `biogeophys/FatesPlantRespPhotosynthMod.F90:1154-1206`. Per-cohort accumulation goes through `ccohort%sym_nfix_tstep` (set at line 1014), then daily summing in `EDAccumulateFluxesMod.F90:85` (`ccohort%sym_nfix_daily = ccohort%sym_nfix_daily + ccohort%sym_nfix_tstep`), then folding into `daily_n_gain` at `EDMainMod.F90:583-584` before `DailyPRT(phase=1)` is called.

The governing formula (Houlton et al. 2008, Fisher et al. 2010) uses `prt_params%nfix_mresp_scfrac(ft)` (JSON parameter name: `fates_cnp_nfix1`), applied as a scale factor on fine-root maintenance respiration:

```fortran
! FatesPlantRespPhotosynthMod.F90:1193-1203
fnrt_mr_nfix_layer  = fnrt_mr_layer * prt_params%nfix_mresp_scfrac(ft)
c_cost_nfix         = s_fix * ( exp(a_fix + b_fix * (t_soil - tfrz) * (1 - 0.5*(t_soil - tfrz)/c_fix)) - 2 )
c_spent_nfix        = fnrt_mr_nfix_layer * dtime
nfix_layer          = c_spent_nfix / c_cost_nfix
```

Where `s_fix = -6.25`, `a_fix = -3.62`, `b_fix = 0.27`, `c_fix = 25.15` (temperature-response constants from Houlton et al. 2008, declared as `parameter` at lines 1187-1190).

Sources: `(biogeophys/FatesPlantRespPhotosynthMod.F90:1010,1014,1154-1206)`, `(biogeophys/EDAccumulateFluxesMod.F90:85)`, `(main/EDMainMod.F90:583-584)`

## Key Parameters

| Parameter (JSON name) | Fortran field | Allocation role |
|---|---|---|
| `fates_cnp_pid_kp` | `prt_params%pid_kp(ipft)` | PID proportional gain on `cx_logratio` |
| `fates_cnp_pid_ki` | `prt_params%pid_ki(ipft)` | PID integral gain on `cx_int` |
| `fates_cnp_pid_kd` | `prt_params%pid_kd(ipft)` | PID derivative gain on `ema_dcxdt` |
| `fates_cnp_store_ovrflw_frac` | `prt_params%store_ovrflw_frac(ipft)` | Inflates storage nutrient/carbon target to `target * (1 + f)` in `CNPAllocateRemainder` |
| `fates_cnp_turnover_nitr_retrans` | `prt_params%turnover_nitr_retrans(ipft, organ_param_id)` | N retranslocation fraction on turnover (leaf, fnrt only; must be 0 for sapw/struct) |
| `fates_cnp_turnover_phos_retrans` | `prt_params%turnover_phos_retrans(ipft, organ_param_id)` | P retranslocation fraction on turnover |
| `fates_cnp_vmax_nh4` | `EDPftvarcon_inst%vmax_nh4(pft)` | Max NH4 uptake per fine-root C [kgN/kgC/s] |
| `fates_cnp_vmax_no3` | `EDPftvarcon_inst%vmax_no3(pft)` | Max NO3 uptake per fine-root C [kgN/kgC/s] |
| `fates_cnp_vmax_p` | `EDPftvarcon_inst%vmax_p(pft)` | Max P uptake per fine-root C [kgP/kgC/s] |
| `fates_cnp_prescribed_nuptake` | `EDPftvarcon_inst%prescribed_nuptake(pft)` | Fraction of demand satisfied under prescribed N uptake (default `0.0` = coupled mode at e027a40) |
| `fates_cnp_prescribed_puptake` | `EDPftvarcon_inst%prescribed_puptake(pft)` | Declared but **not consumed** in `UnPackNutrientAquisitionBCs` — the prescribed-P branch at `FatesSoilBGCFluxMod.F90:221` uses `prescribed_nuptake` as the scaling factor instead. Likely a long-standing source bug. |
| `fates_cnp_nitr_store_ratio` | `prt_params%nitr_store_ratio(ipft)` | Storage N target as fraction of tissue N (used by `StorageNutrientTarget`) |
| `fates_cnp_phos_store_ratio` | `prt_params%phos_store_ratio(ipft)` | Storage P target as fraction of tissue P |
| `fates_cnp_nfix1` | `prt_params%nfix_mresp_scfrac(ft)` | Sym N fixation scale on fine-root maintenance respiration |
| `fates_stoich_nitr` | `prt_params%nitr_stoich_p1(ipft, organ_param_id)` | Growth-min N:C per organ |
| `fates_stoich_phos` | `prt_params%phos_stoich_p1(ipft, organ_param_id)` | Growth-min P:C per organ |
| `fates_alloc_organ_priority` | `prt_params%alloc_priority(ipft, :)` | Priority level for each organ in `CNPPrioritizedReplacement`. Storage is hard-coded to priority 2 independent of this parameter. |
| `fates_alloc_storage_cushion` | `prt_params%cushion(ipft)` | Allometric multiplier on storage target |
| `fates_alloc_store_priority_frac` | `prt_params%leaf_stor_priority(ipft)` | Fraction of turnover demand to prepay at priority 1 |

### ECA Parameter Family (NEW at e027a40)

The parameter file at e027a40 introduces a JSON-namespaced ECA parameter family. These are loaded from the parameter JSON file via `EDPftvarcon.F90:649-691`:

| JSON parameter | Fortran field | Notes / units |
|---|---|---|
| `fates_cnp_eca_decompmicc` | `EDPftvarcon_inst%decompmicc(pft)` | **Renamed from `fates_cnp_decompmicc` at e85d997.** Per-PFT decomposer biomass [gC/m3] used in the depth-attenuation function for ECA. Default 280.0. |
| `fates_cnp_eca_alpha_ptase` | `EDPftvarcon_inst%eca_alpha_ptase(pft)` | INACTIVE (long_name: "KEEP AT 0"). Validation at `EDPftvarcon.F90:1044` aborts if non-zero. |
| `fates_cnp_eca_lambda_ptase` | `EDPftvarcon_inst%eca_lambda_ptase(pft)` | INACTIVE (long_name: "KEEP AT 0"). Validation at `EDPftvarcon.F90:1038` aborts if non-zero. |
| `fates_cnp_eca_km_nh4` | `EDPftvarcon_inst%eca_km_nh4(pft)` | Half-saturation for NH4 uptake (ECA) [gN/m3]. Default 0.14. |
| `fates_cnp_eca_km_no3` | `EDPftvarcon_inst%eca_km_no3(pft)` | Half-saturation for NO3 uptake (ECA) [gN/m3]. Default 0.27. |
| `fates_cnp_eca_km_p` | `EDPftvarcon_inst%eca_km_p(pft)` | Half-saturation for P uptake (ECA) [gP/m3]. Default 0.1. |
| `fates_cnp_eca_km_ptase` | `EDPftvarcon_inst%eca_km_ptase(pft)` | Half-saturation for biochemical P [gP/m3]. Default 1.0. |
| `fates_cnp_eca_vmax_ptase` | `EDPftvarcon_inst%eca_vmax_ptase(pft)` | Maximum production rate for biochemical P [gP/m2/s]. Default 5e-09. |
| `fates_cnp_eca_plant_escalar` | (scalar parameter, `fates_params_default.json:1685`) | Scaling factor for plant fine-root biomass to nutrient carrier enzyme abundance. Default 1.25e-05. |

**Calibration warning**: A2MC parameter sampling tables that key on the e85d997 name `fates_cnp_decompmicc` will fail at e027a40 because the JSON key is now `fates_cnp_eca_decompmicc`. Update sampling tables accordingly. The Fortran field `EDPftvarcon_inst%decompmicc(pft)` is unchanged; only the JSON key moved into the new namespace.

Sources: `(parteh/PRTParamsFATESMod.F90:268-621)`, `(main/EDPftvarcon.F90:649-691,996-1046)`, `(biogeochem/FatesSoilBGCFluxMod.F90:155-225)`, `(parameter_files/fates_params_default.json:397-549,1685)`

## Design Notes for Calibration

- **Trust the subroutine names, not the argument.** `DailyPRT(phase)` is called three times per day but CNP ignores all but `phase=1`. All CNP work happens inside a single `DailyPRTAllometricCNP` invocation.
- **Retranslocation is upstream of allocation.** If a hypothesis involves "retranslocation changes the allocation step", remember that the CNP routine sees retranslocation only as pre-filled nutrient storage, which Step 0.5 drains into `n_gain`/`p_gain`. There is no separate retranslocation path inside `CNPPrioritizedReplacement`.
- **PID gating changed at e027a40.** The L2FR PID controller only runs when at least one nutrient is in coupled-uptake mode AND the host is not supplementing that nutrient. Toggling `prescribed_nuptake/puptake` to non-zero or running with HLM nutrient supplementation freezes `l2fr` silently. Verify by reading `cx_int`, `cx0`, `ema_dcxdt` from the restart file — if all three stay at their initial values, the PID is gated off.
- **Coupled is the default.** At e027a40 the JSON defaults `fates_cnp_prescribed_nuptake = fates_cnp_prescribed_puptake = 0.0` make coupled-uptake the default operational mode (the long_name explicitly marks prescribed mode as "experimental"). The e85d997 wiki gotcha "Verify You Are Not in Prescribed-Uptake Mode" is now inverted — coupled is the default; prescribed is the opt-in.
- **PID state is persistent.** An aggressive `pid_kp` can drive `l2fr` to one extreme and leave `cx_int` wound up. Reading `cx_int`, `cx0`, `ema_dcxdt` from the restart file is the fastest way to diagnose runaway `l2fr` trajectories.
- **`store_c_overflow` is compile-time.** The default and only behavior without a source rebuild is `burn_c_store_overflow`, which routes unspendable carbon into `resp_excess` and increments the exudation counters to zero. `exude_` and `retain_` paths require editing `PRTAllometricCNPMod.F90:223`.
- **`store_ovrflw_frac` inflates the storage target** rather than letting storage build beyond the allometric value. A larger `store_ovrflw_frac` raises the ceiling at which storage parks extra C/N/P in Step 3 **and** pushes the growth-min storage nutrient target higher in Step 1.
- **`fates_alloc_organ_priority`** only influences priority level 1 onwards for non-storage organs; storage's priority is hard-coded to level 2.
- **Sapwood and structure retranslocation must be zero.** `PRTParamsFATESMod.F90:992-1011` will abort the run otherwise.
- **Parameter rename**: any A2MC ensemble that sampled `fates_cnp_decompmicc` at e85d997 must rename to `fates_cnp_eca_decompmicc` at e027a40. The new ECA family also adds 8 new sampleable parameters.

Sources: `(parteh/PRTAllometricCNPMod.F90:223,1882-1885,1909-1915,1925-1947)`, `(parteh/PRTParamsFATESMod.F90:992-1011)`
