# Mass Balance Checking

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `main/EDMainMod.F90` (`TotalBalanceCheck`)
- `main/ChecksBalancesMod.F90` (`SiteMassStock`, `PatchMassStock`)
- `main/EDTypesMod.F90` (`site_massbal_type`)
- `biogeochem/EDPatchDynamicsMod.F90`
- `biogeochem/EDLoggingMortalityMod.F90`

## Purpose and Scope

FATES includes a runtime conservation-checking system that verifies mass closure for each active element (C, N, P) at every site. The check sums stocks (biomass + litter + seeds), compares the change since the previous check against the sum of all fluxes accumulated over the same interval, and aborts the run if the fractional error exceeds `10e-6`. The check runs at multiple points throughout `ed_ecosystem_dynamics` so that imbalances can be localized to a specific phase (recruitment, growth, patch spawning, fusion, termination, canopy structure).

For context on where these fluxes are populated, see [History Update Pipeline](history/pipeline.md) and the logging/fire topics. For details on how stocks are saved across restarts, see [Restart System](restart.md).

## Conservation Principle

For each element the routine enforces:

```
(sum of stocks now)  -  (sum of stocks at previous check)
   ==  (flux_in)  -  (flux_out)     (within 10e-6 fractional tolerance)
```

If this does not hold, `TotalBalanceCheck` writes a detailed diagnostic block to `fates_log` and calls `endrun`. The check is skipped entirely in satellite-phenology mode (`hlm_use_sp .eq. itrue`), because SP mode prescribes vegetation state rather than simulating it prognostically.

Sources: `(main/EDMainMod.F90:847-1024)`

## TotalBalanceCheck: Location and Invocation

**The routine is defined in `main/EDMainMod.F90`, lines 847–1024**, as `subroutine TotalBalanceCheck(currentSite, call_index)`. It is declared `private` to `EDMainMod` (line 124) and is not in `ChecksBalancesMod`. `ChecksBalancesMod.F90` contains only two public routines, `SiteMassStock` and `PatchMassStock`, which `TotalBalanceCheck` calls internally via `SiteMassStock` on line 905 to compute the current site-level total.

```fortran
  subroutine TotalBalanceCheck (currentSite, call_index)
     ...
     call SiteMassStock(currentSite, el, total_stock, &
                        biomass_stock, litter_stock, seed_stock)
     ...
  end subroutine TotalBalanceCheck
```

Sources: `(main/EDMainMod.F90:93, 124, 847-1024)`, `(main/ChecksBalancesMod.F90:32-125)`

## Call Points in the Daily Dynamics Loop

`TotalBalanceCheck` is called with a `call_index` that identifies the phase at which the check is being performed. `final_check_id = -1` is declared at `EDMainMod.F90:129` as a module-level parameter.

| `call_index` | Location in `ed_ecosystem_dynamics` | Purpose |
|---|---|---|
| `0` | Start of `ed_ecosystem_dynamics`, line 196 | Zero accumulators; set baseline `old_stock = 0` |
| `1` | After first cohort termination pass, line 255 | Verify cohort creation and mortality bookkeeping |
| `2` | After second cohort termination pass, line 277 | Verify additional cohort cleanup |
| `3` | After `spawn_patches`, line 294 | Verify mass transfer during disturbance-induced patch spawning |
| `4` | After `fuse_patches`, line 309 | Verify area-weighted patch fusion conservation |
| `5` | After `terminate_patches`, line 315 | Verify patch termination conservation |
| `6` | After `canopy_spread` in `ed_update_site`, line 794 | Verify canopy structure adjustments |
| `-1` | Final check, line 800 (`final_check_id`) | Final verification before timestep completion; updates `old_stock` for next day |

The `final_check_id = -1` call path is special: at this index the routine records `site_mass%old_stock = total_stock` and `site_mass%err_fates = net_flux - change_in_stock` so that the following day's baseline is the closing stock of today.

Sources: `(main/EDMainMod.F90:129, 196-315, 794-800, 1015-1020)`

## site_massbal_type Data Structure

Each site holds one `site_massbal_type` per active element (typically C, N, P). These are populated by the accumulator code throughout `ed_ecosystem_dynamics` and read by `TotalBalanceCheck`. Key fields (from `main/EDTypesMod.F90`):

| Field | Meaning | Units |
|---|---|---|
| `old_stock` | Total stock at the previous final check | `kg / site` |
| `err_fates` | Accumulated error carried forward | `kg / site` |
| `gpp_acc` | Accumulated GPP flux in | `kg / site / day` |
| `aresp_acc` | Accumulated autotrophic respiration out | `kg / site / day` |
| `net_root_uptake` | Net nutrient uptake (includes fixation; negative for efflux) | `kg / site / day` |
| `seed_in` | Mass added via external seed dispersal | `kg / site / day` |
| `seed_out` | Mass exported via seed rain (placeholder) | `kg / site / day` |
| `frag_out` | Litter/CWD fragmentation handed to the host soil BGC | `kg / site / day` |
| `wood_product` | Mass exported as wood products (logging) | `kg / site / day` |
| `burn_flux_to_atm` | Mass lost to atmosphere via fire | `kg / site / day` |
| `flux_generic_in` | Generic input flux (e.g., prescribed initialization) | `kg / site / day` |
| `flux_generic_out` | Generic output flux (e.g., prescribed physiology mode) | `kg / site / day` |
| `patch_resize_err` | Residual from patch area precision loss | `kg / site / day` |

`TotalBalanceCheck` forms `flux_in` and `flux_out` directly from these fields (lines 909–920):

```fortran
flux_in  = seed_in + net_root_uptake + gpp_acc + flux_generic_in + patch_resize_err
flux_out = wood_product + burn_flux_to_atm + seed_out + flux_generic_out + frag_out + aresp_acc
```

Note that `patch_resize_err` is treated as an input: numerical slop from patch resizing is absorbed into `flux_in` so that the check does not fail on expected floating-point residuals from very small patches.

Sources: `(main/EDMainMod.F90:901-922)`, `(main/EDTypesMod.F90:174-224)`

## Stock Calculation

Stocks at a given `call_index` are computed by `SiteMassStock` in `main/ChecksBalancesMod.F90:42-75`, which loops over every patch, calls `PatchMassStock(currentPatch, el, patch_biomass, patch_seed, patch_litter)`, and aggregates. `PatchMassStock` (lines 79–125) sums cohort biomass weighted by per-plant number density and patch area, plus per-patch litter and seed pools.

| Stock component | Calculation | Units |
|---|---|---|
| `biomass_stock` | Σ over cohorts: `organ_mass × n × patch_area / AREA`, for leaf/fnrt/sapw/struct/store/repro | `kg / site` |
| `litter_stock` | Σ over patches: `(AG_CWD + BG_CWD + leaf_fines + root_fines) × patch_area / AREA` | `kg / site` |
| `seed_stock` | Σ over patches and PFTs: `(seed_bank + germinated_seed) × patch_area / AREA` | `kg / site` |
| `total_stock` | `biomass_stock + litter_stock + seed_stock` | `kg / site` |

The `/ AREA` normalization expresses stocks per site of notional area `AREA = 10000 m²`.

Sources: `(main/ChecksBalancesMod.F90:42-125)`

## Error Tolerance and Reporting

At each call index, after summing flux_in, flux_out, and change_in_stock, the routine computes:

```fortran
error      = abs(net_flux - change_in_stock)
error_frac = error / abs(total_stock)   ! when change_in_stock > 0
```

If `error_frac > 10e-6` (or `error` is NaN), the routine dumps: element type, error fraction, absolute error, call index, all `flux_in`/`flux_out` components, biomass/litter/seed subtotals, previous `old_stock`, and site lat/lon. If `print_cohorts = .true.` (a module-private logical), it additionally walks every patch and cohort and prints per-organ biomass plus element-specific per-cohort fluxes (NH4/NO3/N efflux/N fixation for nitrogen, P gain/efflux for phosphorus, C efflux for carbon). It then calls `endrun`.

Sources: `(main/EDMainMod.F90:922-1010)`

## Common Causes of Imbalances

When a mass-balance error surfaces, the `call_index` in the error block narrows the window:

| Failing `call_index` | Likely cause |
|---|---|
| Between 0 and 1 | Recruitment stoichiometry mismatch, or a PARTEH allocation step is not conserving mass |
| 1 or 2 | Cohort termination fluxes not accounted for |
| 3 | Patch spawning: biomass transfer into the new patch during `logging_litter_fluxes`, fire `fire_litter_fluxes`, or treefall does not match what left the donor |
| 4 | Area-weighted averaging during `fuse_patches` introduces precision error beyond `patch_resize_err` |
| 5 | `terminate_patches` didn't transfer all litter/CWD out of the dying patch |
| 6 | `canopy_spread` or `ed_update_site` touched stocks outside the accumulator path |

Sources: `(main/EDMainMod.F90:196-800)`

## Interaction with PARTEH

PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses) has its own internal conservation checks via `CheckMassConservation`, called during daily allocation. Those checks are independent of `TotalBalanceCheck` — they verify within-plant conservation, while `TotalBalanceCheck` verifies site-scale conservation across all plants, litter, and seeds. A failure inside PARTEH typically produces its own error message before the next `TotalBalanceCheck` call index is reached.

## Bypass Conditions

`TotalBalanceCheck` skips the whole body when `hlm_use_sp .eq. itrue` (satellite phenology mode), since prescribed vegetation state does not track carbon prognostically. This is the only bypass — all other running modes (ED, with or without CNP, with or without hydraulics, with or without fire, with or without logging) run the check at every call index.

Sources: `(main/EDMainMod.F90:894)`
