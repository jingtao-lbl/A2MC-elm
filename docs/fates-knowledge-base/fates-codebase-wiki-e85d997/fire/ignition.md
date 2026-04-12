# Fire Danger and Ignition

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `fire/SFMainMod.F90`
- `fire/SFParamsMod.F90`
- `main/EDParamsMod.F90`
- `main/EDPftvarcon.F90`
- `parameter_files/fates_params_default.cdl`

## Purpose and Scope

This document describes how FATES computes daily fire danger and determines the number of potential fire ignitions per unit area using the SPITFIRE module. Fire danger is represented by the Nesterov Index (`acc_NI`) and derived Fire Danger Index (`FDI`), and ignitions come from lightning (always) and optionally from anthropogenic sources following Li et al. 2012. The outputs of this step — `acc_NI`, `FDI`, `NF` — feed directly into fuel moisture, rate of spread, and area burnt.

For spread and intensity calculations see `spread.md`. For vegetation effects see `effects.md`.

## Overview

Fire danger and ignition execute at the site level inside the daily `fire_model` driver `(fire/SFMainMod.F90:80-115)`. The data flow is:

```
fire_danger_index       -> updates acc_NI
charecteristics_of_fuel -> uses acc_NI for fuel moisture
...
area_burnt_intensity    -> computes FDI from acc_NI
                           computes NF (lightning [+ anthropogenic])
                           computes NF_successful from patch FI threshold
```

Note that the subroutine named `fire_danger_index` only accumulates `acc_NI`. The actual `FDI` calculation happens inside `area_burnt_intensity` `(fire/SFMainMod.F90:731-738)`.

## Nesterov Index

### Daily Update

The `fire_danger_index` subroutine `(fire/SFMainMod.F90:118-173)` updates `currentSite%acc_NI` each day using daily-mean temperature, precipitation, and relative humidity from the oldest vegetated patch. Dewpoint is recovered from a Magnus–Tetens formulation:

```
yipsolon = (SF_val_fdi_a * T) / (SF_val_fdi_b + T) + log(max(1, rh)/100)
T_dew    = (SF_val_fdi_b * yipsolon) / (SF_val_fdi_a - yipsolon)
```

where `T` is in Celsius, `rh` is relative humidity in %, and `SF_val_fdi_a`, `SF_val_fdi_b` are the standard Magnus–Tetens constants (typical CDL values 17.27 and 237.3). The daily NI increment follows Nesterov 1968 (Thonicke 2010 Eq. 5) `(fire/SFMainMod.F90:160-171)`:

```
if rainfall > 3 mm/day:
    d_NI = 0
    acc_NI = 0                  (reset)
else:
    d_NI = max(0, (T - T_dew) * T)
acc_NI = acc_NI + d_NI
```

The accumulated `acc_NI` persists across days and is also used inside `charecteristics_of_fuel` to drive the exponential decay of fuel moisture with drying time `(fire/SFMainMod.F90:266-280)`.

### Site-Level Patch Selection

`acc_NI` is calculated once per site using the forcing from a single patch. The oldest patch is used by default; in no-competition mode, if the oldest patch is bareground, the next younger (vegetated) patch is used instead `(fire/SFMainMod.F90:146-152)`. This is a simplification — the model does not currently compute a separate `acc_NI` per patch.

Sources: `(fire/SFMainMod.F90:118-173)`

## Fire Danger Index

`FDI` is computed at the start of `area_burnt_intensity` `(fire/SFMainMod.F90:731-738)`:

```
if hlm_spitfire_mode == hlm_sf_successful_ignitions_def:
    FDI                   = 1
    cloud_to_ground_strikes = 1
else:
    FDI                   = 1 - exp(-SF_val_fdi_alpha * acc_NI)
    cloud_to_ground_strikes = cg_strikes
```

This is Venevsky et al. 2002 Eq. 7 (a modification of Thonicke 2010 Eq. 8). With the typical `SF_val_fdi_alpha = 0.000337` the code comment reports the approximate bands `FDI ≈ 0.1` (low), `0.3` (moderate), `0.75` (high), and `1.0` (extreme) `(fire/SFMainMod.F90:729-730)`. The value is stored in `currentSite%FDI` and is later multiplied into both area-burnt and duration calculations.

Sources: `(fire/SFMainMod.F90:731-738)`, `(fire/SFParamsMod.F90)`

## Ignition Sources

The total ignition count `currentSite%NF` (count per km² per day) is computed per site after FDI `(fire/SFMainMod.F90:748-768)`:

```
NF_lightning = lightning source (see below)
NF           = NF_lightning
if mode == hlm_sf_anthro_ignitions_def:
    NF = NF + NF_anthropogenic
```

### Lightning Ignitions

The lightning branch has two modes `(fire/SFMainMod.F90:750-754)`:

**Scalar mode** (`hlm_sf_scalar_lightning_def`):
```
NF_lightning = ED_val_nignitions * years_per_day * cloud_to_ground_strikes
```
where `ED_val_nignitions` is the annual lightning strike rate (count/km²/yr) from the parameter file, `years_per_day = 1/365` (or similar; the exact conversion constant used in the call), and `cloud_to_ground_strikes` comes from `cg_strikes`.

**External lightning data mode** (default for all other ignition modes):
```
NF_lightning = bc_in%lightning24(iofp) * cloud_to_ground_strikes
```
where `bc_in%lightning24(iofp)` provides daily observed lightning strike counts per km² from the host land model boundary condition at the index of the oldest (vegetated) fates patch. When mode is `hlm_sf_successful_ignitions_def`, `cloud_to_ground_strikes` is forced to 1.0 earlier so that every incoming observation is treated as a successful ignition.

### Anthropogenic Ignitions

When `hlm_spitfire_mode == hlm_sf_anthro_ignitions_def`, human ignitions following Li et al. (2012) are added `(fire/SFMainMod.F90:761-767)`:

```
anthro_ign_count = 0.0035 * 6.8 * pop_density^0.43 / 30
NF               = NF_lightning + anthro_ign_count
```

Where:
- `0.0035` is `pot_hmn_ign_counts_alpha`, a hard-coded local parameter representing the Li et al. 2012 potential human ignition counts in ignitions per person per month `(fire/SFMainMod.F90:721)`.
- `6.8` is the Li et al. 2012 multiplier.
- `^0.43` is the Li et al. 2012 power-law exponent on population density; together with the `6.8` multiplier it produces the saturation behaviour of human ignitions at high population densities.
- `pop_density` comes from the host land model boundary condition `bc_in%pop_density(iofp)` (people per km²).
- `30` is the approximate conversion from monthly to daily rate.

The two previous coefficients (`6.8` and `^0.43`) are not tunable — they are literal constants in the source and only apply in this ignition mode.

Sources: `(fire/SFMainMod.F90:721-722, 748-768)`

## Successful Fires

After ROS, ground fuel consumption, and fire-line intensity have been computed per patch, a patch is counted as having a successful fire when `currentPatch%FI > SF_val_fire_threshold` `(fire/SFMainMod.F90:866-876)`:

```
if FI > SF_val_fire_threshold:
    fire                     = 1
    NF_successful += NF * FDI * (currentPatch%area / AREA)
else:
    fire = 0, FD = 0, frac_burnt = 0
```

Only patches crossing the intensity threshold contribute to `currentSite%NF_successful`, and each patch contributes weighted by its area fraction.

Sources: `(fire/SFMainMod.F90:727, 866-876)`

## Key Variables and Parameters

### Site-Level State

| Variable | Units | Description |
|---|---|---|
| `currentSite%acc_NI` | °C² | Accumulated Nesterov Index |
| `currentSite%FDI` | – | Fire Danger Index (0–1) |
| `currentSite%NF` | count/km²/day | Daily total ignitions (lightning + anthropogenic) |
| `currentSite%NF_successful` | count | Area-weighted count of successful fires |

Defined in `biogeochem/EDTypesMod.F90`.

### Parameters

| Name | Source | Notes |
|---|---|---|
| `SF_val_fdi_alpha` | `SFParamsMod.F90` / CDL | FDI sensitivity (typ. 0.000337) |
| `SF_val_fdi_a` | `SFParamsMod.F90` / CDL | Magnus–Tetens a (typ. 17.27) |
| `SF_val_fdi_b` | `SFParamsMod.F90` / CDL | Magnus–Tetens b (typ. 237.3) |
| `SF_val_fire_threshold` | `SFParamsMod.F90` / CDL | Minimum FI for a successful fire (typ. 50 kW/m) |
| `ED_val_nignitions` | `EDParamsMod.F90` (`main/EDParamsMod.F90:57`) | Annual lightning count per km² |
| `cg_strikes` | `EDParamsMod.F90` (`main/EDParamsMod.F90:83-84`) | Cloud-to-ground fraction |
| `pot_hmn_ign_counts_alpha` | local, hard-coded `(fire/SFMainMod.F90:721)` | 0.0035 ign/person/month |

All `SF_val_*` scalars in `SFParamsMod` initialize to NaN and are populated from the CDL parameter file; the numerical defaults cited above reflect the standard `fates_params_default.cdl`.

## SPITFIRE Mode Constants

`hlm_spitfire_mode` is imported from `FatesInterfaceTypesMod` `(fire/SFMainMod.F90:15-19)`. The four mode constants are:

| Mode | Description |
|---|---|
| `hlm_sf_nofire_def` | Fire disabled — `fire_model` never enters the pipeline |
| `hlm_sf_scalar_lightning_def` | Lightning from `ED_val_nignitions` scalar |
| `hlm_sf_successful_ignitions_def` | External successful-ignitions data, forces `FDI = 1` and `cg = 1` |
| `hlm_sf_anthro_ignitions_def` | Lightning data + Li et al. 2012 anthropogenic ignitions |

Sources: `(fire/SFMainMod.F90:15-19, 731-768)`, `(FatesInterfaceTypesMod.F90)`
