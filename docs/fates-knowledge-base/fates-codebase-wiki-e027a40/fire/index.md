# Fire Dynamics: SPITFIRE

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `fire/SFMainMod.F90` (driver, 643 lines)
- `fire/SFEquationsMod.F90` (pure-function math library, 664 lines)
- `fire/SFParamsMod.F90` (global SF parameters and JSON loader)
- `fire/SFFireWeatherMod.F90` (abstract `fire_weather` class)
- `fire/SFNesterovMod.F90` (`nesterov_index` extension)
- `fire/FatesFuelMod.F90` (`fuel_type` object on each patch)
- `fire/FatesFuelClassesMod.F90` (`fuel_classes` enum object)
- `fire/FatesRxFireMod.F90` (prescribed-fire classifier)
- `main/EDPftvarcon.F90`
- `main/EDParamsMod.F90`
- `main/EDMainMod.F90`
- `main/FatesConstantsMod.F90` (dewpoint constants, unit conversions)
- `main/FatesInterfaceTypesMod.F90` (`hlm_use_managed_fire`)

## Purpose and Scope

This document is the top-level overview of the SPITFIRE (SPread and InTensity of FIRE) module in FATES. SPITFIRE simulates daily wildfire danger, ignition, spread, fuel consumption, direct fire effects on vegetation, and (api.41+) optional managed (prescribed) fire. It is based on Thonicke et al. 2010 and Venevsky et al. 2002, with a Rothermel (1972) rate-of-spread core and Peterson & Ryan (1986) cambial-heating effects.

Sub-topics:
- `ignition.md` — fire weather (Nesterov Index), Fire Danger Index, lightning and anthropogenic ignitions
- `spread.md` — fuel characteristics, Rothermel rate of spread, area burnt, fire intensity
- `effects.md` — crown scorching, crown damage, cambial damage, post-fire mortality
- `managed_fire.md` — prescribed (rx) fire capability (api.41+)

For other disturbance types see `core-dynamics/patch_dynamics.md` and `logging/index.md`. For non-fire mortality see `plant-physiology/mortality.md`.

## Model Integration and Execution

SPITFIRE is executed once per day inside `ed_ecosystem_dynamics` via the `DailyFireModel` driver `(fire/SFMainMod.F90:46-69)`, called from `(main/EDMainMod.F90:224)`. The whole pipeline is guarded by `hlm_spitfire_mode > hlm_sf_nofire_def` `(fire/SFMainMod.F90:58)`. The fire model is also bypassed when the entire site is a single bareground patch (`(main/EDMainMod.F90:223)`); inside each subroutine, individual bareground patches are skipped via `nocomp_pft_label /= nocomp_bareground`.

Sources: `(main/EDMainMod.F90:215-225)`, `(fire/SFMainMod.F90:46-69)`

### Fire Model Modes

The integer `hlm_spitfire_mode` selects the ignition source configuration `(fire/SFMainMod.F90:16-20)`:

| Mode constant | Description | Ignition source |
|---|---|---|
| `hlm_sf_nofire_def` | Fire disabled | none |
| `hlm_sf_scalar_lightning_def` | Scalar lightning | `ED_val_nignitions` parameter |
| `hlm_sf_successful_ignitions_def` | Prescribed successful ignitions | external data, `FDI = 1` forced |
| `hlm_sf_anthro_ignitions_def` | Lightning + anthropogenic | external lightning + population density (Li et al. 2012) |

A separate HLM namelist flag `hlm_use_managed_fire` `(main/FatesInterfaceTypesMod.F90:105)` toggles the prescribed-fire pipeline. It is orthogonal to `hlm_spitfire_mode`: rx fire requires SPITFIRE to be on, but operates on its own classifier (see `managed_fire.md`).

## Fire Execution Pipeline

Inside `DailyFireModel`, eight subroutines run in a fixed order. Each reads state produced by earlier steps `(fire/SFMainMod.F90:58-67)`:

| Step | Subroutine | Purpose | Source |
|---|---|---|---|
| 1 | `UpdateFireWeather` | Update fire weather index, rx burn-window flag, effective wind speed | `(fire/SFMainMod.F90:73-141)` |
| 2 | `UpdateFuelCharacteristics` | Fuel loading, moisture, bulk density, SAV (per-patch `fuel_type`) | `(fire/SFMainMod.F90:145-191)` |
| 3 | `CalculateIgnitionsandFDI` | Site-level FDI and ignition count `NF` | `(fire/SFMainMod.F90:195-263)` |
| 4 | `CalculateSurfaceRateOfSpread` | Rothermel forward and backward ROS per patch | `(fire/SFMainMod.F90:267-347)` |
| 5 | `CalculateSurfaceFireIntensity` | Per-patch fuel consumption, residence time, FI; classifies wildfire vs rx fire | `(fire/SFMainMod.F90:351-444)` |
| 6 | `CalculateAreaBurnt` | Wildfire ellipse, duration, `nonrx_frac_burnt` | `(fire/SFMainMod.F90:448-504)` |
| 7 | `CalculateRxFireAreaBurnt` | Prescribed-fire site-level area filter, `rx_frac_burnt`; finalize `patch%fire` | `(fire/SFMainMod.F90:508-564)` |
| 8 | `CalculatePostFireMortality` | Per-cohort scorch height, crown burn fraction, cambial mortality, total fire mortality | `(fire/SFMainMod.F90:568-639)` |

The mathematical content of every step is implemented as pure functions in `fire/SFEquationsMod.F90` (`OptimumPackingRatio`, `MaximumReactionVelocity`, `OptimumReactionVelocity`, `MoistureCoefficient`, `ReactionIntensity`, `HeatofPreignition`, `EffectiveHeatingNumber`, `WindFactor`, `PropagatingFlux`, `ForwardRateOfSpread`, `BackwardRateOfSpread`, `FireDuration`, `LengthToBreadth`, `FireSize`, `AreaBurnt`, `FireIntensity`, `ScorchHeight`, `CrownFractionBurnt`, `BarkThickness`, `CriticalResidenceTime`, `CambialMortality`, `cambial_mort`, `CrownFireMortality`, `TotalFireMortality`) and as type-bound methods on `fuel_type` (`fire/FatesFuelMod.F90`).

## Fire Danger and Ignition

### Fire Weather Index (Nesterov)

Daily fire-weather state lives on a polymorphic class pointer `currentSite%fireWeather` `(main/EDTypesMod.F90:453)` of abstract type `fire_weather` `(fire/SFFireWeatherMod.F90:9-22)`. The default extension is `nesterov_index` `(fire/SFNesterovMod.F90:12-19)`, which stores the running Nesterov Index in `fireWeather%fire_weather_index`.

Update rule (Nesterov 1968 / Thonicke 2010 Eq. 5) `(fire/SFNesterovMod.F90:42-68, 72-85)`:

```
if precip > 3 mm/day:           fire_weather_index = 0       (reset)
else:                           d_NI = max(0, (T - T_dew) * T)
                                fire_weather_index = fire_weather_index + d_NI
```

Dewpoint is now obtained via Lawrence (2005) Eq. 8 with hard-coded constants `dewpoint_a = 17.62` and `dewpoint_b = 243.12` from `(main/FatesConstantsMod.F90:314-315)`. These were parameters in earlier versions but are no longer tunable.

The abstract `fire_weather` class also owns `effective_windspeed` and the prescribed-fire burn-window flag `rx_flag`, both updated in `UpdateFireWeather`.

### Fire Danger Index

`FDI` is computed at the start of `CalculateIgnitionsandFDI` `(fire/SFMainMod.F90:226-236)` using Venevsky et al. 2002 Eq. 7:

```
if mode == hlm_sf_successful_ignitions_def:
    FDI = 1
else:
    FDI = 1 - exp(-SF_val_fdi_alpha * fireWeather%fire_weather_index)
```

The FDI is stored in `currentSite%fdi` `(main/EDTypesMod.F90:450)` and feeds both area-burnt and duration calculations.

### Ignition Sources

Total ignition count per km² per day `currentSite%NF` combines lightning and, optionally, anthropogenic ignitions `(fire/SFMainMod.F90:247-261)`. See `ignition.md` for the detailed formulas.

## Fuel Characterization

SPITFIRE uses `num_fuel_classes = 6` fuel size classes. Indices are now exposed through a typed enum object `fuel_classes` `(fire/FatesFuelClassesMod.F90:10-29)` rather than free named constants:

| Index | Accessor | Description |
|---|---|---|
| 1 | `fuel_classes%twigs()` | Twigs (fine CWD, ~1-h time-lag) |
| 2 | `fuel_classes%small_branches()` | Small branches (~10-h) |
| 3 | `fuel_classes%large_branches()` | Large branches (~100-h) |
| 4 | `fuel_classes%trunks()` | Trunks (~1000-h, excluded from ROS) |
| 5 | `fuel_classes%dead_leaves()` | Dead leaves / fine litter |
| 6 | `fuel_classes%live_grass()` | Live grass |

Per-patch fuel state is encapsulated in a `fuel_type` object `(fire/FatesFuelMod.F90:15-40)` attached as `currentPatch%fuel`. Members include `loading`, `frac_loading`, `effective_moisture`, `frac_burnt`, `non_trunk_loading`, `bulk_density_notrunks`, `SAV_notrunks`, `MEF_notrunks`, `average_moisture_notrunks`. Fuel properties used by ROS exclude trunks; the `_notrunks` averages renormalize over classes 1–3, 5, 6.

Sources: `(fire/FatesFuelMod.F90)`, `(fire/SFMainMod.F90:145-191)`, `(fire/SFMainMod.F90:267-347)`

## Fire Spread, Area, and Intensity

### Rothermel Rate of Spread

`CalculateSurfaceRateOfSpread` `(fire/SFMainMod.F90:267-347)` calls `SFEquationsMod` pure functions to assemble the Rothermel (1972) forward ROS:

```
ROS_front = (i_r * xi * (1 + phi_wind)) / (bulk_density_notrunks * eps * q_ig)   [m/min]
ROS_back  = ROS_front * exp(-0.012 * site%wind)                                  [m/min]
```

`ROS_back` uses the **raw** site wind in m/min `(fire/SFMainMod.F90:340-341)`, not `effective_windspeed`. See `spread.md` for the full set of intermediate quantities (`beta`, `beta_op`, `q_ig`, `phi_wind`, reaction velocity, moisture damping).

### Area Burnt (Wildfire)

`CalculateAreaBurnt` `(fire/SFMainMod.F90:448-504)` runs only when `currentPatch%nonrx_fire == 1`. It computes the fire ellipse using a length-to-breadth ratio `lb` from `LengthToBreadth(effective_windspeed, tree_fraction_patch)` `(fire/SFMainMod.F90:486)`:

```
fire_size  = (pi / (4 * lb)) * (df + db)^2          (Arora & Boer 2005 Eq. 14)
area_burnt = fire_size * NF * FDI                                  [m^2/km^2]
nonrx_frac_burnt = min(0.99, area_burnt / 1e6)
```

Patch-level tree fraction `tree_fraction_patch = currentPatch%total_tree_area / currentPatch%area` is the only quantity in this routine that is not site-aggregated.

### Fire Intensity

Fire-line intensity `FI` (kW/m) is computed unconditionally for any patch with ignition or rx-burn-window flag inside `CalculateSurfaceFireIntensity` `(fire/SFMainMod.F90:399-402)`:

```
FI = SF_val_fuel_energy * (TFC_ROS / 0.45) * (ROS_front / 60)   [kJ/kg * kg/m^2 * m/s = kW/m]
```

The threshold check `FI > SF_val_fire_threshold` (default 50 kW/m) is then used to **classify** the fire as wildfire (`nonrx_fire = 1`) vs prescribed (`rx_fire = 1`) vs no-fire `(fire/SFMainMod.F90:403-429)`. This differs from older SPITFIRE versions where the threshold gated `FI` itself.

### Fire Duration (Wildfire)

`(fire/SFEquationsMod.F90:348-363)`:

```
FD = (SF_val_max_durat + 1) / (1 + SF_val_max_durat * exp(SF_val_durat_slope * FDI))   [min]
```

## Fire Effects on Vegetation

See `effects.md` for the full formulas. Summary of the four-step cascade once `currentPatch%fire == 1` (which now includes both wildfire AND prescribed fire) `(fire/SFMainMod.F90:588-633)`:

```
Scorch_ht(pft)        = fire_alpha_SH(pft) * FI^0.667
fraction_crown_burned = piecewise(Scorch_ht, height, crown_depth)
bt                    = bark_scaler(pft) * dbh
tau_c                 = 2.9 * bt^2
cambial_mort          = piecewise(tau_l / tau_c)
crownfire_mort        = crown_kill(pft) * fraction_crown_burned^3
fire_mort             = crownfire_mort + cambial_mort
                        - crownfire_mort * cambial_mort            (joint probability)
```

The trigger condition `patch%fire == 1` is `nonrx_fire + rx_fire` `(fire/SFMainMod.F90:549)`, so cohort-level fire mortality fires for both wildfire and prescribed fire. Both pathways use the same `FI` (stored unsplit in `patch%FI`) and the same `tau_l`. All effects iterate the cohort linked list and apply only to woody cohorts (`prt_params%woody(pft) == itrue`); non-woody cohorts are zeroed each timestep `(fire/SFMainMod.F90:604-607)`.

## Key Parameters

### Global (`SFParamsMod`, loaded from JSON parameter file)

`SFParamsMod` declares global scalars and initializes them to NaN `(fire/SFParamsMod.F90:21-52, 125-165)`; values come from the JSON parameter file `(fire/SFParamsMod.F90:169-276)`. Commonly used:

- `SF_val_fdi_alpha` — FDI sensitivity, JSON key `fates_fire_fdi_alpha` (default **0.00037**, `(fire/SFParamsMod.F90:183-184)`)
- `SF_val_fire_threshold` — minimum wildfire FI, JSON key `fates_fire_threshold` (default 50 kW/m)
- `SF_val_max_durat`, `SF_val_durat_slope` — fire-duration sigmoidal shape
- `SF_val_miner_total`, `SF_val_miner_damp` — mineral content / damping (Rothermel)
- `SF_val_fuel_energy` — fuel heat content (kJ/kg)
- `SF_val_part_dens` — fuel particle density
- `SF_val_drying_ratio` — fuel drying ratio
- `SF_val_SAV(num_fuel_classes)`, `SF_val_FBD(num_fuel_classes)` — per-class SAV and bulk density
- `SF_val_min_moisture`, `SF_val_mid_moisture`, low/mid moisture coefficients and slopes — fuel consumption curves
- `SF_val_rxfire_*` (13 scalars) — prescribed-fire window, intensity, fuel, area limits (see `managed_fire.md`)

### Hard-coded constants (no longer tunable)

- `dewpoint_a = 17.62`, `dewpoint_b = 243.12` `(main/FatesConstantsMod.F90:314-315)` — Lawrence 2005 Eq. 8 coefficients (replaces `SF_val_fdi_a/b`)
- `min_precip_thresh = 3.0` mm/day for NI rainfall reset `(fire/SFNesterovMod.F90:21)`
- `igns_per_person_month = 0.0035`, `approx_days_per_month = 30.0` `(fire/SFMainMod.F90:218-219)` — Li et al. 2012 anthropogenic ignition constants

### PFT-Specific (`EDPftvarcon`)

| Parameter file name | Fortran field | Role | Loader |
|---|---|---|---|
| `fates_fire_alpha_SH` | `fire_alpha_SH(:)` | scorch-height coefficient | `(main/EDPftvarcon.F90:441-443)` |
| `fates_fire_bark_scaler` | `bark_scaler(:)` | DBH-to-bark-thickness scaler | `(main/EDPftvarcon.F90:337-339)` |
| `fates_fire_crown_kill` | `crown_kill(:)` | crown-scorch mortality scaler | `(main/EDPftvarcon.F90:341-343)` |

Field declarations: `(main/EDPftvarcon.F90:61-62, 151)`. PFT dimension is now 14 (was 12 at e85d997).

### EDParams (`EDParamsMod`)

| Parameter file name | Fortran field | Role | Loader |
|---|---|---|---|
| `fates_fire_nignitions` | `ED_val_nignitions` | annual lightning ignitions per km² (scalar mode) | `(main/EDParamsMod.F90:331-332)` |
| `fates_fire_cg_strikes` | `cg_strikes` | cloud-to-ground fraction | `(main/EDParamsMod.F90:295-296)` |
| `fates_fire_active_crown_fire` | `active_crown_fire` (logical) | placeholder flag for active crown fire (default 0) | `(main/EDParamsMod.F90:292-293)` |

`active_crown_fire` is loaded but is not currently consumed inside the `fire/` module; it is wired only as a logical flag for future use.

## Site-Level Fire State (`ed_site_type`, `main/EDTypesMod.F90:447-457`)

| Field | Units | Description |
|---|---|---|
| `wind` | m/min | Daily site wind (raw, used by `BackwardRateOfSpread`) |
| `fdi` | – | Fire Danger Index (0–1) |
| `NF` | count/km²/day | Total daily ignitions |
| `NF_successful` | count | Area-weighted successful wildfires (cumulative on site) |
| `fireWeather` | class pointer | Polymorphic `fire_weather` extension (default `nesterov_index`) |
| `rx_flag` | 0/1 | Site-level field; in practice burn-window state lives on `fireWeather%rx_flag` |
| `rxfire_area_fuel` | m² | Burnable area after rx-fuel filter (per day) |
| `rxfire_area_fi` | m² | Burnable area after rx-FI filter (per day) |
| `rxfire_area_final` | m² | Burnable area after site-fraction filter (per day) |

## Patch-Level Fire State (`fates_patch_type`, `biogeochem/FatesPatchMod.F90:224-240`)

| Field | Units | Description |
|---|---|---|
| `ros_front`, `ros_back` | m/min | Forward / backward Rothermel ROS |
| `tau_l` | min | Lethal-heating residence time (capped at 8 min) |
| `fi` | kW/m | Combined fire intensity (rx or wildfire) |
| `fire` | 0/1 | `nonrx_fire + rx_fire` (mortality trigger) |
| `fd` | min | Wildfire duration |
| `frac_burnt` | 0–1 | `nonrx_frac_burnt + rx_frac_burnt` |
| `nonrx_fire`, `nonrx_fi`, `nonrx_frac_burnt` | – | Wildfire-specific subset |
| `rx_fire`, `rx_fi`, `rx_frac_burnt` | – | Prescribed-fire-specific subset |
| `Scorch_ht(pft)` | m | Per-PFT scorch height |
| `fuel` | object | `fuel_type` (loading, moisture, frac_burnt, etc.) |

A consistency check `(fire/SFMainMod.F90:554-559)` aborts if both wildfire and rx fire are set on the same patch.

## Integration with the Disturbance Framework

Cohort-level `fire_mort` values are consumed by `EDPatchDynamicsMod` to build the fire disturbance rate (`dtype_ifire`), which drives `spawn_patches` for newly created burned patches `(main/EDMainMod.F90:227-229)`. Fire-killed biomass enters litter pools through the standard mortality pathway.

Sources: `(main/EDMainMod.F90:215-229)`, `(biogeochem/EDPatchDynamicsMod.F90)`
