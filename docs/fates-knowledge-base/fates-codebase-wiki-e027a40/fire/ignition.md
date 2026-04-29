# Fire Danger and Ignition

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `fire/SFMainMod.F90`
- `fire/SFFireWeatherMod.F90` (abstract `fire_weather` class)
- `fire/SFNesterovMod.F90` (`nesterov_index` extension)
- `fire/SFParamsMod.F90`
- `main/EDParamsMod.F90`
- `main/EDPftvarcon.F90`
- `main/FatesConstantsMod.F90`
- `parameter_files/fates_params_default.json`

## Purpose and Scope

This document describes how FATES computes daily fire weather and determines the number of potential fire ignitions per unit area using the SPITFIRE module. Fire weather is represented by a polymorphic `fire_weather` class (currently extended only by `nesterov_index`), and the derived Fire Danger Index (`FDI`) is used together with lightning ignitions (always) and optionally anthropogenic ignitions (Li et al. 2012). The outputs of this step — `fireWeather%fire_weather_index`, `currentSite%fdi`, `currentSite%NF` — feed downstream into fuel moisture, rate of spread, and area burnt.

For spread and intensity calculations see `spread.md`. For vegetation effects see `effects.md`. For prescribed-fire weather thresholds and the rx classifier see `managed_fire.md`.

## Overview

Fire weather and ignition execute at the site level inside the daily `DailyFireModel` driver `(fire/SFMainMod.F90:46-69)`. The data flow is:

```
UpdateFireWeather             -> updates fireWeather%fire_weather_index (Nesterov NI)
                                 updates fireWeather%rx_flag (rx burn window)
                                 updates fireWeather%effective_windspeed (site-level)
UpdateFuelCharacteristics     -> uses fire_weather_index for fuel moisture (per patch)
CalculateIgnitionsandFDI      -> computes FDI from fire_weather_index
                                 computes NF (lightning [+ anthropogenic])
... (subsequent steps)
CalculateSurfaceFireIntensity -> patch-level wildfire vs rx classification (gated on FI threshold)
                                 NF_successful is incremented per wildfire patch
```

In contrast to earlier SPITFIRE versions, the daily-update routine that owns NI is `UpdateFireWeather`, and the FDI is computed in a separate step `CalculateIgnitionsandFDI`.

## Fire Weather Class

Fire-weather state is held on a polymorphic class pointer `currentSite%fireWeather` `(main/EDTypesMod.F90:453)` of abstract type `fire_weather` `(fire/SFFireWeatherMod.F90:9-22)`:

```
type, abstract, public :: fire_weather
  real(r8) :: fire_weather_index   ! e.g., accumulated Nesterov Index
  real(r8) :: effective_windspeed  ! site wind, attenuated by tree/grass cover [m/min]
  integer  :: rx_flag              ! prescribed-fire burn-window flag [0/1]
contains
  procedure(initialize_fire_weather), deferred :: Init
  procedure(update_fire_weather),     deferred :: UpdateIndex
  procedure :: UpdateEffectiveWindSpeed
  procedure :: UpdateRxfireBurnWindow
end type
```

The default extension is `nesterov_index` `(fire/SFNesterovMod.F90:12-19)`, which provides the Init and UpdateIndex bindings. The class hierarchy is the architectural seam for future fire-weather indices (e.g., Canadian FWI) — adding a new index means writing a new extension and pointing `currentSite%fireWeather` at it during initialization.

## Nesterov Index

### Daily Update

`UpdateFireWeather` `(fire/SFMainMod.F90:73-141)` pulls daily-mean temperature, precipitation, relative humidity, and wind from the oldest vegetated patch's boundary conditions, then calls `currentSite%fireWeather%UpdateIndex(temp_C, precip, rh, wind)` `(fire/SFMainMod.F90:127)`. For the Nesterov extension this dispatches to `update_nesterov_index` `(fire/SFNesterovMod.F90:42-68)`:

```
if precip > min_precip_thresh:                      ! reset NI if it rains
    fire_weather_index = 0
else:
    t_dew = dewpoint(temp_C, rh)                    ! Lawrence 2005 Eq. 8
    fire_weather_index = fire_weather_index + calc_nesterov_index(temp_C, t_dew)
```

with

```
calc_nesterov_index(T, T_dew) = max(0, (T - T_dew) * T)              (T in degrees C)
```

`(fire/SFNesterovMod.F90:72-85)`. The rainfall reset threshold is the module-level constant `min_precip_thresh = 3.0_r8` mm/day `(fire/SFNesterovMod.F90:21)`.

### Dewpoint Formulation

Dewpoint is calculated by the function `dewpoint(temp_C, rh)` `(fire/SFNesterovMod.F90:89-107)` using **Lawrence (2005) Eq. 8** (https://doi.org/10.1175/BAMS-86-2-225):

```
yipsolon = log(max(1, rh)/100) + (dewpoint_a * T) / (dewpoint_b + T)
T_dew    = (dewpoint_b * yipsolon) / (dewpoint_a - yipsolon)
```

with hard-coded constants `dewpoint_a = 17.62` and `dewpoint_b = 243.12` `(main/FatesConstantsMod.F90:314-315)`. **These are no longer parameters** — older SPITFIRE versions exposed `SF_val_fdi_a`, `SF_val_fdi_b` (Magnus–Tetens with values 17.27 / 237.3); these have been removed. The numerical change of ~2% in each constant is small but not negligible for tuning.

### Site-Level Patch Selection

`fire_weather_index` is calculated once per site using the forcing from a single patch — by default the oldest patch, with a fallback to the next younger patch when the oldest is bareground (`nocomp_pft_label == nocomp_bareground`) `(fire/SFMainMod.F90:109-115)`. The model does not currently compute a separate index per patch.

Sources: `(fire/SFMainMod.F90:73-141)`, `(fire/SFNesterovMod.F90:42-107)`

## Fire Danger Index

`FDI` is computed at the start of `CalculateIgnitionsandFDI` `(fire/SFMainMod.F90:226-236)`:

```
if hlm_spitfire_mode == hlm_sf_successful_ignitions_def:
    currentSite%FDI         = 1
    cloud_to_ground_strikes = 1
else:
    currentSite%FDI         = 1 - exp(-SF_val_fdi_alpha * fireWeather%fire_weather_index)
    cloud_to_ground_strikes = cg_strikes
```

This is Venevsky et al. 2002 Eq. 7 (a modification of Thonicke 2010 Eq. 8). The source comment `(fire/SFMainMod.F90:225)` describes approximate bands `FDI ≈ 0.1` low, `0.3` moderate, `0.75` high, `1.0` extreme — annotated for historical `SF_val_fdi_alpha = 0.000337`. Note that the **JSON parameter file default for `fates_fire_fdi_alpha` is now 0.00037** `(parameter_files/fates_params_default.json:1762-1767)`, slightly higher than the value in the source comment, so the empirical FDI bands shift mildly in proportion. The value is stored in `currentSite%fdi` `(main/EDTypesMod.F90:450)` and is later multiplied into both area-burnt and duration calculations.

Sources: `(fire/SFMainMod.F90:226-236)`, `(fire/SFParamsMod.F90:21, 183-184)`

## Ignition Sources

The total ignition count `currentSite%NF` (count per km² per day) is computed per site after FDI `(fire/SFMainMod.F90:247-261)`:

```
NF_lightning = lightning source (see below)
NF           = NF_lightning
if mode == hlm_sf_anthro_ignitions_def:
    NF = NF + anthro_ignitions
```

### Lightning Ignitions

The lightning branch has two modes `(fire/SFMainMod.F90:247-252)`:

**Scalar mode** (`hlm_sf_scalar_lightning_def`):
```
NF_lightning = ED_val_nignitions * years_per_day * cloud_to_ground_strikes
```
where `ED_val_nignitions` is the annual lightning strike rate (count/km²/yr) loaded from `fates_fire_nignitions` `(main/EDParamsMod.F90:331-332)`, `years_per_day = 1/365` `(main/FatesConstantsMod.F90:303)`, and `cloud_to_ground_strikes` comes from `cg_strikes`.

**External lightning data mode** (any other ignition mode):
```
NF_lightning = bc_in%lightning24(iofp) * cloud_to_ground_strikes
```
where `bc_in%lightning24(iofp)` provides daily observed lightning strike counts per km² from the host land model boundary condition at the index of the oldest (vegetated) FATES patch. When mode is `hlm_sf_successful_ignitions_def`, `cloud_to_ground_strikes` is forced to 1.0 earlier, so every incoming observation is treated as a successful ignition.

### Anthropogenic Ignitions

When `hlm_spitfire_mode == hlm_sf_anthro_ignitions_def`, human ignitions following Li et al. (2012) are added `(fire/SFMainMod.F90:256-261)`:

```
anthro_ignitions = igns_per_person_month * 6.8 * pop_density^0.43 / approx_days_per_month
NF               = NF_lightning + anthro_ignitions
```

with module-local parameter constants `(fire/SFMainMod.F90:218-219)`:
```
igns_per_person_month = 0.0035    ! ignitions per person per month (Li et al. 2012 alpha)
approx_days_per_month = 30.0      ! days per month
```

- `0.0035` is the Li et al. 2012 potential human ignition counts per person per month (formerly `pot_hmn_ign_counts_alpha`).
- `6.8` is the Li et al. 2012 multiplier.
- `^0.43` is the Li et al. 2012 power-law exponent on population density; combined with the `6.8` multiplier this produces the saturation behavior of human ignitions at high population densities.
- `pop_density` comes from the host land model boundary condition `bc_in%pop_density(iofp)` (people per km²).

The four constants `0.0035`, `6.8`, `0.43`, `30` are not tunable — they are hard-coded in the source.

Sources: `(fire/SFMainMod.F90:218-219, 247-261)`

## Successful Wildfires

After surface ROS, fuel consumption, and fire-line intensity have been computed per patch in `CalculateSurfaceFireIntensity`, a patch is classified as a successful wildfire when `currentPatch%FI > SF_val_fire_threshold` AND there is at least one ignition AND the patch is not classified as rx fire `(fire/SFMainMod.F90:423-429)`:

```
fi_check     = (FI > SF_val_fire_threshold)
has_ignition = (NF > 0)
if (rx classification false) .and. has_ignition .and. fi_check:
    nonrx_fire  = 1
    NF_successful += NF * FDI * (currentPatch%area / AREA)
    nonrx_FI    = FI
```

Only patches crossing the intensity threshold and not occupied by rx fire contribute to `currentSite%NF_successful`, and each patch contributes weighted by its area fraction. Note that **`FI` is computed unconditionally** for every patch with ignition or rx-burn-window flag `(fire/SFMainMod.F90:399-402)`; the threshold check is used only to classify the fire type, not to gate FI calculation.

Sources: `(fire/SFMainMod.F90:399-438)`

## Key Variables and Parameters

### Site-Level State

| Variable | Units | Source | Description |
|---|---|---|---|
| `currentSite%fireWeather%fire_weather_index` | varies | `main/EDTypesMod.F90:453` | Index value (e.g., Nesterov accumulated) |
| `currentSite%fireWeather%effective_windspeed` | m/min | same | Wind attenuated by tree/grass cover |
| `currentSite%fireWeather%rx_flag` | 0/1 | same | Prescribed-fire burn-window flag |
| `currentSite%fdi` | – | `main/EDTypesMod.F90:450` | Fire Danger Index (0–1) |
| `currentSite%NF` | count/km²/day | `main/EDTypesMod.F90:451` | Daily total ignitions |
| `currentSite%NF_successful` | count | `main/EDTypesMod.F90:452` | Area-weighted count of successful wildfires |
| `currentSite%wind` | m/min | `main/EDTypesMod.F90:449` | Raw site wind (used by `BackwardRateOfSpread`) |

### Parameters

| Name | Source | Default | Notes |
|---|---|---|---|
| `SF_val_fdi_alpha` | JSON `fates_fire_fdi_alpha`, `fire/SFParamsMod.F90:21, 183-184` | **0.00037** | FDI sensitivity (Venevsky 2002 Eq. 7) |
| `SF_val_fire_threshold` | JSON `fates_fire_threshold`, `fire/SFParamsMod.F90:29, 207-208` | 50 kW/m | Wildfire vs no-fire classifier |
| `ED_val_nignitions` | JSON `fates_fire_nignitions`, `main/EDParamsMod.F90:331-332` | 0.0–0.04 | Annual lightning count per km² (scalar mode) |
| `cg_strikes` | JSON `fates_fire_cg_strikes`, `main/EDParamsMod.F90:295-296` | 0.2 | Cloud-to-ground fraction |
| `dewpoint_a`, `dewpoint_b` | hard-coded `main/FatesConstantsMod.F90:314-315` | 17.62, 243.12 | Lawrence 2005 Eq. 8 (no longer tunable) |
| `min_precip_thresh` | hard-coded `fire/SFNesterovMod.F90:21` | 3.0 mm/day | NI rainfall reset threshold |
| `igns_per_person_month` | hard-coded `fire/SFMainMod.F90:218` | 0.0035 | Li et al. 2012 anthropogenic alpha |
| `approx_days_per_month` | hard-coded `fire/SFMainMod.F90:219` | 30.0 | Days per month |

All `SF_val_*` scalars in `SFParamsMod` initialize to NaN and are populated from the JSON parameter file `(fire/SFParamsMod.F90:125-165, 169-276)`; defaults cited reflect `parameter_files/fates_params_default.json`.

## SPITFIRE Mode Constants

`hlm_spitfire_mode` is imported from `FatesInterfaceTypesMod` `(fire/SFMainMod.F90:16-20)`. The four mode constants are:

| Mode | Description |
|---|---|
| `hlm_sf_nofire_def` | Fire disabled — `DailyFireModel` skips all subroutines |
| `hlm_sf_scalar_lightning_def` | Lightning from `ED_val_nignitions` scalar |
| `hlm_sf_successful_ignitions_def` | External successful-ignitions data, forces `FDI = 1` and `cg = 1` |
| `hlm_sf_anthro_ignitions_def` | Lightning data + Li et al. 2012 anthropogenic ignitions |

Prescribed (managed) fire is controlled separately by the HLM namelist flag `hlm_use_managed_fire` (see `managed_fire.md`).

Sources: `(fire/SFMainMod.F90:15-20, 226-261)`, `(main/FatesInterfaceTypesMod.F90:105)`
