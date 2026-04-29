# Managed (Prescribed) Fire

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `fire/FatesRxFireMod.F90` (`is_prescribed_burn`)
- `fire/SFFireWeatherMod.F90` (`UpdateRxfireBurnWindow`)
- `fire/SFMainMod.F90` (`UpdateFireWeather`, `CalculateSurfaceFireIntensity`, `CalculateRxFireAreaBurnt`, `CalculatePostFireMortality`)
- `fire/SFParamsMod.F90` (13 `SF_val_rxfire_*` parameters)
- `main/FatesInterfaceTypesMod.F90` (`hlm_use_managed_fire`)
- `main/FatesInterfaceMod.F90` (namelist plumbing)
- `main/EDTypesMod.F90` (site-level `rxfire_area_*` trackers)
- `biogeochem/FatesPatchMod.F90` (patch-level `rx_*` and `nonrx_*` fields)

## Purpose and Scope

This document covers the prescribed (managed, "rx") fire capability added at api.41 and present at e027a40. Prescribed fire is a side branch of the daily SPITFIRE pipeline that lets the model represent intentional, low-intensity burns that occur during a user-defined weather window and within user-defined fuel-load and intensity ranges. It runs alongside the existing wildfire branch and writes to a parallel set of patch-level fields. Crucially, **patches that experience a prescribed fire trigger the same cohort-level mortality pipeline as patches with a wildfire** (see `effects.md`), even though their fire intensity is below the wildfire `SF_val_fire_threshold`.

This document is new at e027a40; older wiki revisions (including e85d997) did not document the rx capability.

## Activation

Prescribed fire is gated by an HLM namelist flag, separate from `hlm_spitfire_mode`:

| Flag | Declared | Set via namelist | Notes |
|---|---|---|---|
| `hlm_use_managed_fire` | `(main/FatesInterfaceTypesMod.F90:105)` | `use_managed_fire` `(main/FatesInterfaceMod.F90:2018-2021)` | 0 = off, 1 = on; requires SPITFIRE on |

When `hlm_use_managed_fire == 0`, `UpdateRxfireBurnWindow` returns immediately `(fire/SFFireWeatherMod.F90:94)` and `fireWeather%rx_flag` stays at 0, so all rx-related branches inside `CalculateSurfaceFireIntensity` and `CalculateRxFireAreaBurnt` are skipped.

## Daily Pipeline

```
UpdateFireWeather               -> updates fireWeather%rx_flag (site burn-window)
UpdateFuelCharacteristics       -> (no rx-specific work)
CalculateIgnitionsandFDI        -> (no rx-specific work)
CalculateSurfaceRateOfSpread    -> (no rx-specific work)
CalculateSurfaceFireIntensity   -> rxfire fuel-load filter
                                   is_prescribed_burn classifier (FI window + ignition state)
                                   sets currentPatch%rx_fire and rx_FI
CalculateAreaBurnt              -> wildfire only (does not touch rx fields)
CalculateRxFireAreaBurnt        -> site-fraction filter
                                   sets currentPatch%rx_frac_burnt
                                   finalizes currentPatch%fire and frac_burnt
CalculatePostFireMortality      -> triggered by patch%fire == 1 (includes rx)
```

### Step 1 — Burn Window

`UpdateRxfireBurnWindow` `(fire/SFFireWeatherMod.F90:73-112)` is called from `UpdateFireWeather` `(fire/SFMainMod.F90:130-132)` and sets `fireWeather%rx_flag`:

```
if hlm_use_managed_fire == 0:
    return                                    ! rx_flag stays 0
t_check  = (T   - temp_low)*(T   - temp_up)
rh_check = (RH  - rh_low)*(RH  - rh_up)
ws_check = (WS  - wind_low)*(WS - wind_up)
if t_check <= 0 .and. rh_check <= 0 .and. ws_check <= 0:
    rx_flag = 1
else:
    rx_flag = 0
```

The product test `(x - low)*(x - up) <= 0` is true exactly when `low <= x <= up`. The six bounds come from `SF_val_rxfire_tpup`, `_tplw`, `_rhup`, `_rhlw`, `_wdup`, `_wdlw` (see parameter table). All thresholds are PFT-independent and site-uniform.

### Step 2 — FI Window and Patch Classification

Inside `CalculateSurfaceFireIntensity` `(fire/SFMainMod.F90:351-444)`, the FI is computed unconditionally on any patch with `has_ignition .or. fireWeather%rx_flag == 1` `(fire/SFMainMod.F90:399-402)`. Then a fuel-load check is applied `(fire/SFMainMod.F90:406-407)`:

```
rxfire_fuel_check = (SF_val_rxfire_fuel_min < fuel%non_trunk_loading < SF_val_rxfire_fuel_max)
```

If both `rx_flag == 1` and `rxfire_fuel_check`, the site-level burnable area tracker `currentSite%rxfire_area_fuel` accumulates this patch's area `(fire/SFMainMod.F90:412)`, then the classifier is called `(fire/SFMainMod.F90:416-417)`:

```
is_rxfire = is_prescribed_burn(FI, NF, SF_val_rxfire_min_threshold,
                                 SF_val_rxfire_max_threshold, SF_val_fire_threshold)
```

`is_prescribed_burn` `(fire/FatesRxFireMod.F90:18-49)` returns true if **either** of two conditions holds:

```
within_rx_FI_range = (rx_min_FI < FI < rx_max_FI)
rx_man = within_rx_FI_range .and. NF < nearzero                ! human-only ignition
rx_hyb = within_rx_FI_range .and. FI < wildfire_FI_thresh .and. NF > nearzero
                                                                ! low-FI hybrid (lightning + human)
is_prescribed_burn = rx_man .or. rx_hyb
```

So a patch is classified as prescribed fire when its FI falls inside the rx window AND **either** there are no lightning ignitions (purely human), OR there are lightning ignitions but the FI is below the wildfire threshold (hybrid).

If `is_rxfire`, `currentPatch%rx_fire = 1`, `currentPatch%rx_FI = FI`, and `rxfire_area_fi` accumulates the patch area `(fire/SFMainMod.F90:419-421)`. Otherwise the patch falls through to the wildfire branch (`nonrx_fire = 1` if the wildfire threshold is also met).

A wildfire and a prescribed fire **cannot co-exist on the same patch** by design — code aborts via `endrun` if both flags ever get set `(fire/SFMainMod.F90:554-559)`.

### Step 3 — Site-Fraction Filter and Burnt Fraction

`CalculateRxFireAreaBurnt` `(fire/SFMainMod.F90:508-564)` applies the final site-level filter:

```
total_burnable_frac = currentSite%rxfire_area_fi / AREA       ! aggregated from step 2
loop over patches:
    patch%fire       = 0
    patch%frac_burnt = 0
    patch%rx_frac_burnt = 0
    if patch%rx_fire == 1 .and. total_burnable_frac >= SF_val_rxfire_min_frac:
        rxfire_area_final += patch%area
        patch%rx_frac_burnt = min(0.99, SF_val_rxfire_AB / total_burnable_frac)
    else:
        patch%rx_fire = 0           ! revoke rx classification
        patch%rx_FI   = 0
    ! finalize combined patch fields
    patch%fire        = patch%nonrx_fire + patch%rx_fire
    patch%frac_burnt  = patch%nonrx_frac_burnt + patch%rx_frac_burnt
    if patch%fire > 1:
        endrun  ! wildfire and rx fire on same patch — not allowed
```

Three things to note:

1. `SF_val_rxfire_AB` is a target daily burned fraction (0.01 = 1% by default). The actual patch-level `rx_frac_burnt` is `SF_val_rxfire_AB / total_burnable_frac`, capped at 0.99 — i.e., the user-specified daily burn capacity is distributed evenly across all rx-eligible patches.
2. If the site-level burnable fraction is below `SF_val_rxfire_min_frac` (default 0.1 = 10%), no rx fire happens — the rx classification on every patch is revoked.
3. The combined `patch%fire` flag is only finalized here, after the site-level filter. This is the flag that gates `CalculatePostFireMortality` (see `effects.md`).

### Step 4 — Cohort Mortality

`CalculatePostFireMortality` `(fire/SFMainMod.F90:568-639)` runs on patches with `currentPatch%fire == 1`. Since `patch%fire = nonrx_fire + rx_fire`, a successful prescribed fire (with patch-level `FI` typically in the `[SF_val_rxfire_min_threshold, SF_val_fire_threshold)` range, i.e., **below** the wildfire threshold) now drives the same crown-scorch and cambial-mortality calculations as a wildfire. See `effects.md` for the mathematics. The intensity used inside the mortality formulas is the unsplit `patch%FI` (= `rx_FI` for an rx patch, `nonrx_FI` for a wildfire patch).

This is a behavior change relative to old SPITFIRE: previously, only patches above the wildfire threshold experienced cohort fire mortality. Now, even a low-intensity prescribed fire kills woody cohorts in proportion to its `FI` and `tau_l`.

## Parameters

All 13 `SF_val_rxfire_*` parameters are declared at `(fire/SFParamsMod.F90:41-52)`, initialized to NaN at `(fire/SFParamsMod.F90:152-163)`, and loaded from the JSON parameter file at `(fire/SFParamsMod.F90:240-274)`.

| JSON parameter name | Fortran field | Default | Units | Purpose |
|---|---|---|---|---|
| `fates_rxfire_temp_upthreshold` | `SF_val_rxfire_tpup` | 30.0 | °C | Burn-window upper temperature |
| `fates_rxfire_temp_lwthreshold` | `SF_val_rxfire_tplw` | 5.0 | °C | Burn-window lower temperature |
| `fates_rxfire_rh_upthreshold` | `SF_val_rxfire_rhup` | 55.0 | % | Burn-window upper RH |
| `fates_rxfire_rh_lwthreshold` | `SF_val_rxfire_rhlw` | 30.0 | % | Burn-window lower RH |
| `fates_rxfire_wind_upthreshold` | `SF_val_rxfire_wdup` | 10.0 | m/s | Burn-window upper wind speed |
| `fates_rxfire_wind_lwthreshold` | `SF_val_rxfire_wdlw` | 2.0 | m/s | Burn-window lower wind speed |
| `fates_rxfire_min_threshold` | `SF_val_rxfire_min_threshold` | 50.0 | kW/m | Minimum FI for rx fire |
| `fates_rxfire_max_threshold` | `SF_val_rxfire_max_threshold` | 500.0 | kW/m | Maximum FI for rx fire |
| `fates_rxfire_fuel_min` | `SF_val_rxfire_fuel_min` | 0.5 | kgC/m² | Minimum non-trunk fuel load |
| `fates_rxfire_fuel_max` | `SF_val_rxfire_fuel_max` | 1.5 | kgC/m² | Maximum non-trunk fuel load |
| `fates_rxfire_AB` | `SF_val_rxfire_AB` | 0.01 | fraction/day | Daily burn capacity (target) |
| `fates_rxfire_min_frac` | `SF_val_rxfire_min_frac` | 0.1 | fraction | Minimum site burnable fraction |

Defaults verified against `parameter_files/fates_params_default.json:2063-2145`.

A few sanity-relevant interactions:

- The rx FI window `[min_threshold, max_threshold] = [50, 500]` overlaps the wildfire threshold `SF_val_fire_threshold = 50` at the lower end. Combined with the `is_prescribed_burn` logic, this means low-FI patches with no lightning go to rx, and low-FI patches with lightning (`FI < wildfire_threshold`) also go to rx (the "hybrid" branch); only patches with `FI >= wildfire_threshold` AND lightning go to wildfire.
- The rx fuel window `[0.5, 1.5]` kgC/m² is narrow and prevents prescribed burns on patches that are either fuel-starved or fuel-overloaded.
- `SF_val_rxfire_AB = 0.01` (1% of site area per day, prorated across rx-eligible patches) is a target rate that effectively caps the rx pipeline. Realized burned area is also capped per patch at 0.99.

## Site-Level Trackers

Three site-level fields track rx-eligible area at three filtering stages `(main/EDTypesMod.F90:455-457)`:

| Field | Updated in | Stage |
|---|---|---|
| `currentSite%rxfire_area_fuel` | `CalculateSurfaceFireIntensity:412` | After fuel-load filter |
| `currentSite%rxfire_area_fi` | `CalculateSurfaceFireIntensity:420` | After FI filter (`is_prescribed_burn` true) |
| `currentSite%rxfire_area_final` | `CalculateRxFireAreaBurnt:541` | After site-fraction filter |

These are initialized to 0 at the start of each daily call (in different routines) and accumulate across patches within the day. They are useful for diagnostics and for understanding why a given patch did or did not burn.

## Patch-Level Fields

Patch-level fire state is split into a wildfire side (`nonrx_*`) and a prescribed-fire side (`rx_*`), with finalized combined fields `(biogeochem/FatesPatchMod.F90:224-240)`:

| Field | Type | Description |
|---|---|---|
| `nonrx_fire` | real(r8) (0 or 1) | Wildfire flag |
| `nonrx_fi` | real(r8) | Wildfire fire intensity (kW/m) |
| `nonrx_frac_burnt` | real(r8) | Wildfire burnt fraction |
| `rx_fire` | integer (0 or 1) | Prescribed-fire flag |
| `rx_fi` | real(r8) | Prescribed-fire intensity (kW/m) |
| `rx_frac_burnt` | real(r8) | Prescribed-fire burnt fraction |
| `fire` | integer (0 or 1) | Combined trigger = `nonrx_fire + rx_fire` |
| `fi` | real(r8) | Combined fire intensity (used by `CalculatePostFireMortality`) |
| `frac_burnt` | real(r8) | Combined burnt fraction = `nonrx_frac_burnt + rx_frac_burnt` |
| `fd` | real(r8) | Fire duration (wildfire only — not set for rx) |

Note that `nonrx_fire` is declared as `real(r8)` in the patch type while `rx_fire` is `integer`; the addition `nonrx_fire + rx_fire` is performed in mixed precision at `(fire/SFMainMod.F90:549)`. The classifier-vs-flag tests inside `CalculateSurfaceFireIntensity` use `currentPatch%nonrx_fire == itrue` and `currentPatch%rx_fire == itrue` `(fire/SFMainMod.F90:432, 436)`.

## Worked Example

Consider a temperate grassland site with the default rx parameters and a typical summer day.

1. **Burn window:** `T = 22 °C`, `RH = 40%`, `wind = 5 m/s` → all three checks pass → `rx_flag = 1`.
2. **Patch with wildfire-class fuel:** `non_trunk_loading = 1.0` kgC/m² (passes `[0.5, 1.5]`), `FI` computed = `120` kW/m, `NF = 0.05` from lightning. `is_prescribed_burn`: `within_rx_FI_range = (50 < 120 < 500) = true`, `rx_man = false` (NF > 0), `rx_hyb = (FI < 50) = false`. So `is_rxfire = false`, falls through to `nonrx_fire = 1` (wildfire).
3. **Patch with low-FI human-ignition:** same fuel, `FI = 80` kW/m, `NF = 0` (no lightning). `is_rxfire = (50 < 80 < 500) .and. true = true`. `rx_fire = 1`, `rx_FI = 80`.
4. **Patch with low-FI hybrid:** same fuel, `FI = 30` kW/m, `NF = 0.02`. `within_rx_FI_range = (50 < 30) = false`, so `is_rxfire = false`. `fi_check = (30 > 50) = false`, so `nonrx_fire = 0` either. No fire.
5. **Site-level filter:** `total_burnable_frac = rxfire_area_fi / AREA`. If this is, say, 0.3 (≥ `SF_val_rxfire_min_frac = 0.1`), then `rx_frac_burnt = min(0.99, 0.01 / 0.3) = 0.033` on every rx-eligible patch.
6. **Mortality:** the rx patch (case 3) has `fire = 1`, enters `CalculatePostFireMortality`, and woody cohorts experience scorch + cambial damage at `FI = 80` kW/m.

## Sources

- `fire/SFMainMod.F90:73-141, 351-444, 508-564, 568-639`
- `fire/SFFireWeatherMod.F90:73-112`
- `fire/FatesRxFireMod.F90`
- `fire/SFParamsMod.F90:41-52, 152-163, 240-274`
- `main/FatesInterfaceTypesMod.F90:105`
- `main/FatesInterfaceMod.F90:1553, 1810-1811, 2018-2021`
- `main/EDTypesMod.F90:454-457`
- `biogeochem/FatesPatchMod.F90:224-240`
- `parameter_files/fates_params_default.json:2063-2145`
