---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Mass Balance Checking

**Relevant source files:**
- `main/EDMainMod.F90` (`TotalBalanceCheck`, 1198 lines)
- `main/ChecksBalancesMod.F90` (`SiteMassStock`, `PatchMassStock`, 380 lines)
- `main/EDTypesMod.F90` (`site_massbal_type`, 859 lines)
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/EDLoggingMortalityMod.F90`

## Purpose and Scope

FATES includes a runtime conservation-checking system that verifies mass closure for each active element (C, N, P) at every site. The check sums stocks (biomass + litter + seeds), compares the change since the previous check against the sum of all fluxes accumulated over the same interval, and aborts the run if the fractional error exceeds `10e-6`. The check runs at multiple points throughout `ed_ecosystem_dynamics` and `ed_update_site` so that imbalances can be localized to a specific phase (recruitment, growth, patch spawning, fusion, termination, canopy structure).

For context on where these fluxes are populated, see [History Update Pipeline](history/pipeline.md) and the logging/fire topics. For details on how stocks are saved across restarts, see [Restart System](restart.md).

## Conservation Principle

For each element the routine enforces:

```
(sum of stocks now)  -  (sum of stocks at previous check)
   ==  (flux_in)  -  (flux_out)     (within 10e-6 fractional tolerance)
```

If this does not hold, `TotalBalanceCheck` writes a detailed diagnostic block to `fates_log` and calls `endrun`. The check is skipped entirely in satellite-phenology mode (`hlm_use_sp .eq. itrue`), because SP mode prescribes vegetation state rather than simulating it prognostically.

Sources: `(main/EDMainMod.F90:928-1127)`

## TotalBalanceCheck: Location and Invocation

**The routine is defined in `main/EDMainMod.F90:928-1127`** as `subroutine TotalBalanceCheck(currentSite, call_index, is_restarting)`. It is declared `private` to `EDMainMod` (line 131) and is not in `ChecksBalancesMod`. `ChecksBalancesMod.F90` contains only the public stock routines `SiteMassStock` and `PatchMassStock`, which `TotalBalanceCheck` calls internally via `SiteMassStock` on line 998 to compute the current site-level total.

```fortran
subroutine TotalBalanceCheck (currentSite, call_index, is_restarting )
   type(ed_site_type) , intent(inout) :: currentSite
   integer            , intent(in)    :: call_index
   logical, optional  , intent(in)    :: is_restarting   ! NEW at e027a40
   ...
   call SiteMassStock(currentSite, el, total_stock, &
                      biomass_stock, litter_stock, seed_stock)
   ...
end subroutine TotalBalanceCheck
```

The optional `is_restarting` argument is new at e027a40. When `.true.`, both `flux_in` and `flux_out` are forced to zero before the comparison, so a restart day does not trigger a spurious imbalance against the cleared accumulators (lines 1001-1004). The `final_check_id = -1` self-update of `old_stock` is also gated on `.not. l_is_restarting` (line 1119).

Sources: `(main/EDMainMod.F90:131, 136, 928-1127)`, `(main/ChecksBalancesMod.F90:45-78)`

## Call Points in the Daily Dynamics Loop

`TotalBalanceCheck` is called with a `call_index` that identifies the phase at which the check is being performed. `final_check_id = -1` is declared at `EDMainMod.F90:136` as a module-level parameter.

| `call_index` | Location in source | Purpose |
|---|---|---|
| `0` | `ed_ecosystem_dynamics`, line 201 | Zero accumulators; set baseline `old_stock = 0` |
| `1` | After first cohort termination pass, line 266 | Verify cohort creation and mortality bookkeeping |
| `2` | After second cohort termination pass, line 289 | Verify additional cohort cleanup |
| `3` | After `spawn_patches`, line 307 | Verify mass transfer during disturbance-induced patch spawning |
| `4` | After `fuse_patches`, line 322 | Verify area-weighted patch fusion conservation |
| `5` | After `terminate_patches`, line 329 | Verify patch termination conservation |
| `6` | After `canopy_spread` in `ed_update_site`, line 855 | Verify canopy structure adjustments. Passes `is_restarting=is_restarting` |
| `-1` (`final_check_id`) | After `canopy_structure` in `ed_update_site`, line 861 | Final verification before timestep completion; updates `old_stock` for next day. Passes `is_restarting=is_restarting` |

Both calls 6 and `-1` propagate the host's `is_restarting` flag from the surrounding `ed_update_site(currentSite, bc_in, bc_out, is_restarting)` invocation. The `final_check_id = -1` call path additionally records `site_mass%old_stock = total_stock` and `site_mass%err_fates = net_flux - change_in_stock` so that the following day's baseline is the closing stock of today (only when not restarting).

Sources: `(main/EDMainMod.F90:136, 201, 266, 289, 307, 322, 329, 855, 861, 1119-1122)`

## site_massbal_type Data Structure

Each site holds one `site_massbal_type` per active element (typically C, N, P). These are populated by the accumulator code throughout `ed_ecosystem_dynamics` and read by `TotalBalanceCheck`. At e027a40 several fields are arrays:

| Field | Shape | Meaning | Units |
|---|---|---|---|
| `old_stock` | scalar | Total stock at the previous final check | `kg / site` |
| `err_fates` | scalar | Total mass balance error for FATES processes | `kg / site` |
| `gpp_acc` | scalar | Accumulated GPP flux in | `kg / site / day` |
| `aresp_acc` | scalar | Accumulated autotrophic respiration out | `kg / site / day` |
| `net_root_uptake` | scalar | Net nutrient uptake (includes fixation; negative for efflux) | `kg / site / day` |
| `seed_in` | scalar | Mass added via external seed dispersal | `kg / site / day` |
| `seed_out` | scalar | Mass exported via seed rain (placeholder) | `kg / site / day` |
| `frag_out` | scalar | Litter/CWD fragmentation handed to the host soil BGC | `kg / site / day` |
| **`wood_product_harvest(maxpft)`** | array | Per-PFT mass exported as wood product from logging harvest (NEW at e027a40 — split from the old scalar `wood_product`) | `kg / site / day` |
| **`wood_product_landusechange(maxpft)`** | array | Per-PFT mass exported as wood product from land-use change (NEW) | `kg / site / day` |
| **`burn_flux_to_atm(n_dist_types)`** | array | Per-disturbance-type mass lost to atmosphere via fire (NEW shape — was a scalar at e85d997) | `kg / site / day` |
| `flux_generic_in` | scalar | Generic input flux (e.g., prescribed initialization) | `kg / site / day` |
| `flux_generic_out` | scalar | Generic output flux (e.g., prescribed physiology mode) | `kg / site / day` |
| `patch_resize_err` | scalar | Residual from patch area precision loss (treated as flux_in) | `kg / site / day` |
| **`herbivory_flux_out`** | scalar | Mass loss to grazing/browsing by herbivores (NEW at e027a40) | `kg / site / day` |

`TotalBalanceCheck` forms `flux_in` and `flux_out` directly from these fields (lines 1005-1019):

```fortran
flux_in  = site_mass%seed_in + &
           site_mass%net_root_uptake + &
           site_mass%gpp_acc + &
           site_mass%flux_generic_in + &
           site_mass%patch_resize_err

flux_out = sum(site_mass%wood_product_harvest(:)) + &
           sum(site_mass%wood_product_landusechange(:)) + &
           sum(site_mass%burn_flux_to_atm(:)) + &
           site_mass%seed_out + &
           site_mass%flux_generic_out + &
           site_mass%frag_out + &
           site_mass%aresp_acc + &
           site_mass%herbivory_flux_out
```

Compared to e85d997, three things changed:

1. The old scalar `wood_product` is **gone**. It is replaced by two per-PFT arrays — `wood_product_harvest(maxpft)` and `wood_product_landusechange(maxpft)` — that are summed at the call site. This separates harvest-driven from land-use-change-driven wood product, exposed in history as `FATES_HARVEST_WOODPROD_C_FLUX` and `FATES_LUCHANGE_WOODPROD_C_FLUX`.
2. `burn_flux_to_atm` is now a `(n_dist_types)` array (the same disturbance-type axis as `currentSite%disturbance_rates_*`), summed with `sum(...)`. The bc_out flow `bc_out%fire_closs_to_atm_si = sum(site_mass%burn_flux_to_atm(:)) * area_inv * days_per_sec` (line 921) demonstrates the new shape.
3. A new `herbivory_flux_out` term has been added to `flux_out` so that grazing/browsing losses do not break closure. The bc_out flow is `bc_out%grazing_closs_to_atm_si = site_mass%herbivory_flux_out * area_inv * days_per_sec` (line 922).

`patch_resize_err` is still treated as an input: numerical slop from patch resizing is absorbed into `flux_in` so that the check does not fail on expected floating-point residuals from very small patches.

Sources: `(main/EDMainMod.F90:1005-1019, 921-922)`, `(main/EDTypesMod.F90:263-318)`

## Stock Calculation

Stocks at a given `call_index` are computed by `SiteMassStock` in `main/ChecksBalancesMod.F90:45-78`, which loops over every patch, calls `PatchMassStock(currentPatch, el, patch_biomass, patch_seed, patch_litter)`, and aggregates. `PatchMassStock` (lines 82-128) sums cohort biomass weighted by per-plant number density and patch area, plus per-patch litter and seed pools.

| Stock component | Calculation | Units |
|---|---|---|
| `biomass_stock` | Σ over cohorts: `organ_mass × n × patch_area / AREA`, for leaf/fnrt/sapw/struct/store/repro | `kg / site` |
| `litter_stock` | Σ over patches: `(AG_CWD + BG_CWD + leaf_fines + root_fines) × patch_area / AREA` | `kg / site` |
| `seed_stock` | Σ over patches and PFTs: `(seed_bank + germinated_seed) × patch_area / AREA` | `kg / site` |
| `total_stock` | `biomass_stock + litter_stock + seed_stock` | `kg / site` |

The `/ AREA` normalization expresses stocks per site of notional area `AREA = 10000 m²`.

Sources: `(main/ChecksBalancesMod.F90:45-128)`

## Error Tolerance and Reporting

At each call index, after summing flux_in, flux_out, and change_in_stock, the routine computes:

```fortran
error      = abs(net_flux - change_in_stock)
error_frac = error / abs(total_stock)   ! when change_in_stock > 0
```

If `error_frac > 10e-6` (or `error` is NaN), the routine dumps: element type, error fraction, absolute error, call index, all `flux_in`/`flux_out` components (now including `wood_product_harvest(:)`, `wood_product_landusechange(:)`, `burn_flux_to_atm(:)`, and `herbivory_flux_out`), biomass/litter/seed subtotals, previous `old_stock`, and site lat/lon. If `print_cohorts = .true.` (a module-private logical), it additionally walks every patch and cohort and prints per-organ biomass plus element-specific per-cohort fluxes (NH4/NO3/N efflux/N fixation for nitrogen, P gain/efflux for phosphorus, C efflux for carbon). It then calls `endrun`.

Sources: `(main/EDMainMod.F90:1032-1112)`

## Common Causes of Imbalances

When a mass-balance error surfaces, the `call_index` in the error block narrows the window:

| Failing `call_index` | Likely cause |
|---|---|
| Between 0 and 1 | Recruitment stoichiometry mismatch, or a PARTEH allocation step is not conserving mass |
| 1 or 2 | Cohort termination fluxes not accounted for |
| 3 | Patch spawning: biomass transfer into the new patch during `logging_litter_fluxes`, fire `fire_litter_fluxes`, or treefall does not match what left the donor (now also covers the per-PFT wood product split) |
| 4 | Area-weighted averaging during `fuse_patches` introduces precision error beyond `patch_resize_err` |
| 5 | `terminate_patches` did not transfer all litter/CWD out of the dying patch |
| 6 | `canopy_spread` or `ed_update_site` touched stocks outside the accumulator path |
| `-1` | Final check after `canopy_structure`; ignored on restart days |

## Interaction with PARTEH

PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses) has its own internal conservation checks via `CheckMassConservation`, called during daily allocation. Those checks are independent of `TotalBalanceCheck` — they verify within-plant conservation, while `TotalBalanceCheck` verifies site-scale conservation across all plants, litter, and seeds. A failure inside PARTEH typically produces its own error message before the next `TotalBalanceCheck` call index is reached.

## Bypass Conditions

`TotalBalanceCheck` skips the whole body when `hlm_use_sp .eq. itrue` (satellite phenology mode), since prescribed vegetation state does not track carbon prognostically (line 988). On restart days, the check still runs, but `flux_in` and `flux_out` are zeroed (lines 1001-1004), and the `final_check_id` self-update of `old_stock` is skipped (line 1119). All other running modes (ED, with or without CNP, with or without hydraulics, with or without fire, with or without logging) run the full check at every call index.

Sources: `(main/EDMainMod.F90:988, 1001-1004, 1119)`
