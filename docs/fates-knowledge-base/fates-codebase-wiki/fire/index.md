# Fire Dynamics: SPITFIRE

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `fire/SFMainMod.F90`
- `fire/SFParamsMod.F90`
- `main/EDParamsMod.F90`
- `main/EDPftvarcon.F90`
- `main/EDMainMod.F90`
- `biogeochem/FatesLitterMod.F90`

## Purpose and Scope

This document is the top-level overview of the SPITFIRE (SPread and InTensity of FIRE) module in FATES. SPITFIRE simulates daily wildfire danger, ignition, spread, fuel consumption, and direct fire effects on vegetation. It is based on Thonicke et al. 2010 and Venevsky et al. 2002, with a Rothermel (1972) rate-of-spread core and Peterson & Ryan (1986) cambial-heating effects.

Sub-topics:
- `ignition.md` — Nesterov Index, Fire Danger Index, lightning and anthropogenic ignitions
- `spread.md` — fuel characteristics, Rothermel rate of spread, area burnt, fire intensity
- `effects.md` — crown scorching, crown damage, cambial damage, post-fire mortality

For other disturbance types see `core-dynamics/patch_dynamics.md` and `logging/index.md`. For non-fire mortality see `plant-physiology/mortality.md`.

## Model Integration and Execution

SPITFIRE is executed once per day inside `ed_ecosystem_dynamics` via the `fire_model` driver `(fire/SFMainMod.F90:80-115)`. The whole pipeline is guarded by `hlm_spitfire_mode > hlm_sf_nofire_def` — setting `hlm_spitfire_mode = hlm_sf_nofire_def` turns fire off entirely. Bareground no-competition patches are skipped in every step (`nocomp_pft_label .ne. nocomp_bareground`).

Sources: `(main/EDMainMod.F90:210-219)`, `(fire/SFMainMod.F90:80-115)`

### Fire Model Modes

The integer `hlm_spitfire_mode` selects the ignition source configuration `(fire/SFMainMod.F90:15-19, 731-768)`:

| Mode constant | Description | Ignition source |
|---|---|---|
| `hlm_sf_nofire_def` | Fire disabled | none |
| `hlm_sf_scalar_lightning_def` | Scalar lightning | `ED_val_nignitions` parameter |
| `hlm_sf_successful_ignitions_def` | Prescribed successful ignitions | external data, `FDI = 1` forced |
| `hlm_sf_anthro_ignitions_def` | Lightning + anthropogenic | lightning data + population density (Li et al. 2012) |

## Fire Execution Pipeline

Inside `fire_model`, ten subroutines run in a fixed order. Each reads state produced by earlier steps `(fire/SFMainMod.F90:102-114)`:

| Step | Subroutine | Purpose | Source |
|---|---|---|---|
| 1 | `fire_danger_index` | Update Nesterov Index `acc_NI` | `(fire/SFMainMod.F90:118-173)` |
| 2 | `wind_effect` | Compute `effect_wspeed` from canopy cover | `(fire/SFMainMod.F90:348-446)` |
| 3 | `charecteristics_of_fuel` | Fuel moisture, bulk density, SAV, MEF | `(fire/SFMainMod.F90:177-344)` |
| 4 | `rate_of_spread` | Rothermel forward and backward ROS | `(fire/SFMainMod.F90:449-592)` |
| 5 | `ground_fuel_consumption` | Burnt fraction per fuel class, `tau_l`, `TFC_ROS` | `(fire/SFMainMod.F90:595-683)` |
| 6 | `area_burnt_intensity` | `FDI`, ignitions `NF`, fire ellipse, `frac_burnt`, `FI`, `fire` flag | `(fire/SFMainMod.F90:687-885)` |
| 7 | `crown_scorching` | `Scorch_ht(pft)` per patch | `(fire/SFMainMod.F90:890-951)` |
| 8 | `crown_damage` | `fraction_crown_burned` per cohort | `(fire/SFMainMod.F90:954-1018)` |
| 9 | `cambial_damage_kill` | `cambial_mort` per cohort | `(fire/SFMainMod.F90:1021-1071)` |
| 10 | `post_fire_mortality` | `crownfire_mort`, `fire_mort` per cohort | `(fire/SFMainMod.F90:1074-1119)` |

Note that the FDI itself is updated inside `area_burnt_intensity`, not inside `fire_danger_index`; `fire_danger_index` only accumulates `acc_NI`.

## Fire Danger and Ignition

### Nesterov Index

`acc_NI` accumulates daily with temperature and dewpoint depression and resets when rainfall exceeds 3 mm/day `(fire/SFMainMod.F90:160-171)`:

```
if rainfall > 3 mm/day : acc_NI = 0
else : d_NI = max(0, (T - T_dewpoint) * T)      (T in Celsius)
       acc_NI = acc_NI + d_NI
```

Dewpoint is obtained from a Magnus–Tetens formulation using parameters `SF_val_fdi_a` and `SF_val_fdi_b`. The calculation uses meteorological forcing from the oldest vegetated patch `(fire/SFMainMod.F90:146-158)`.

### Fire Danger Index

`FDI` is derived from `acc_NI` inside `area_burnt_intensity` using Venevsky et al. 2002 Eq. 7 `(fire/SFMainMod.F90:731-738)`:

```
if mode == hlm_sf_successful_ignitions_def:
    FDI = 1
else:
    FDI = 1 - exp(-SF_val_fdi_alpha * acc_NI)
```

### Ignition Sources

Total ignition count per km² per day `NF` combines lightning and, optionally, anthropogenic ignitions `(fire/SFMainMod.F90:748-768)`. See `ignition.md` for the detailed formulas.

## Fuel Characterization

SPITFIRE uses `NFSC = 6` fuel size classes. Index constants are declared in `FatesLitterMod.F90` — only five are named constants (`tw_sf=1`, `lb_sf=3`, `tr_sf=4`, `dl_sf=5`, `lg_sf=6`); index 2 (small branches) has no named constant and is accessed via array ranges such as `tw_sf:lb_sf` `(fire/SFMainMod.F90:30-36)`.

| Index | Symbol | Description |
|---|---|---|
| 1 | `tw_sf` | Twigs (fine CWD) |
| 2 | — | Small branches |
| 3 | `lb_sf` | Large branches |
| 4 | `tr_sf` | Trunks (excluded from ROS) |
| 5 | `dl_sf` | Dead leaves / fine litter |
| 6 | `lg_sf` | Live grass |

Fuel properties `fuel_bulkd`, `fuel_sav`, `fuel_mef`, `fuel_eff_moist` are weighted averages over classes `tw_sf:lb_sf` plus `dl_sf` and `lg_sf`, with a correction factor `1/(1 - fuel_frac(tr_sf))` that re-normalizes to exclude the trunk fraction `(fire/SFMainMod.F90:282-309)`. Trunks contribute to fuel consumption accounting but do not affect ROS or intensity.

Sources: `(fire/SFMainMod.F90:177-344)`

## Fire Spread, Area, and Intensity

### Rothermel Rate of Spread

`rate_of_spread` implements the Rothermel (1972) forward ROS `(fire/SFMainMod.F90:576-581)`:

```
ROS_front = (I_R * xi * (1 + phi_wind)) / (fuel_bulkd * eps * q_ig)
ROS_back  = ROS_front * exp(-0.012 * wind)                     (/min * min)
```

See `spread.md` for the full set of intermediate quantities (`beta`, `beta_op`, `q_ig`, `phi_wind`, reaction velocity, moisture damping).

### Area Burnt

`area_burnt_intensity` computes the fire ellipse using a length-to-breadth ratio `lb` that depends on wind speed and tree cover fraction `(fire/SFMainMod.F90:803-814)`. Daily area burnt per km² is:

```
size_of_fire = (pi / (4 * lb)) * (df + db)^2          (Arora & Boer 2005 Eq. 14)
AB           = size_of_fire * NF * FDI
frac_burnt   = min(0.99, AB / 1e6)
```

### Fire Intensity

Fire line intensity `FI` (kW/m) is `(fire/SFMainMod.F90:854-859)`:

```
W   = TFC_ROS / 0.45                              (kgC/m^2 to kgBiomass/m^2)
ROS = ROS_front / 60                              (m/min to m/s)
FI  = SF_val_fuel_energy * W * ROS                (kJ/kg * kg/m^2 * m/s = kW/m)
```

A fire only proceeds if `FI > SF_val_fire_threshold` (default 50 kW/m). Otherwise `fire = 0`, `FD = 0`, `frac_burnt = 0` `(fire/SFMainMod.F90:866-876)`.

### Fire Duration

`(fire/SFMainMod.F90:785-786)`:

```
FD = (SF_val_max_durat + 1) / (1 + SF_val_max_durat * exp(SF_val_durat_slope * FDI))
```

## Fire Effects on Vegetation

See `effects.md` for the full formulas. Summary of the four-step cascade once `fire = 1` `(fire/SFMainMod.F90:890-1119)`:

```
Scorch_ht(pft)        = fire_alpha_SH(pft) * FI^0.667
fraction_crown_burned = piecewise( Scorch_ht, height, crown_depth )
bt                    = bark_scaler(pft) * dbh
tau_c                 = 2.9 * bt^2
cambial_mort          = piecewise( tau_l / tau_c )
crownfire_mort        = crown_kill(pft) * fraction_crown_burned^3
fire_mort             = crownfire_mort + cambial_mort
                        - crownfire_mort * cambial_mort            (joint probability)
```

The joint-probability form assumes crown-scorch kill and cambial kill are independent events. All effects subroutines iterate the cohort linked list and apply only to woody cohorts (`prt_params%woody(pft) == itrue`). There is no `canopy_layer` check and no "impact mortality from falling trees" inside `fire/SFMainMod.F90`; any secondary understory disturbance is handled downstream in `EDPatchDynamicsMod` as part of patch spawning, not inside SPITFIRE effects code.

## Key Parameters

### Global (`SFParamsMod` / CDL, not hard-coded)

`SFParamsMod.F90` declares global scalars and initializes them to NaN `(fire/SFParamsMod.F90:24-161)`; the actual values come from the CDL parameter file. Commonly used ones:

- `SF_val_fdi_alpha` — FDI sensitivity to Nesterov Index (typical CDL default 0.000337, Venevsky 2002)
- `SF_val_fire_threshold` — minimum fire line intensity (typical 50 kW/m)
- `SF_val_max_durat`, `SF_val_durat_slope` — fire-duration sigmoidal shape
- `SF_val_miner_total` — mineral content fraction (Rothermel)
- `SF_val_fuel_energy` — fuel heat content (kJ/kg)
- `SF_val_part_dens` — fuel particle density (Rothermel)
- `SF_val_drying_ratio` — fuel drying ratio (fuel moisture model)
- `SF_val_SAV(NFSC)`, `SF_val_FBD(NFSC)` — per-class SAV and bulk density
- `SF_val_min_moisture(NFSC)`, `SF_val_mid_moisture(NFSC)` and low/mid coefficients and slopes — fuel consumption curves

### PFT-Specific (`EDPftvarcon`)

| Parameter file name | Fortran field | Role |
|---|---|---|
| `fates_fire_alpha_SH` | `fire_alpha_SH` | scorch-height coefficient |
| `fates_fire_bark_scaler` | `bark_scaler` | DBH-to-bark-thickness scaler |
| `fates_fire_crown_kill` | `crown_kill` | crown-scorch mortality scaler |

Registration in `EDPftvarcon.F90` lines `380-386` (register) and `821-827` (retrieve).

### EDParams

- `ED_val_nignitions` — annual lightning ignitions per km² (scalar-lightning mode)
- `cg_strikes` — cloud-to-ground fraction

Sources: `(fire/SFParamsMod.F90)`, `(main/EDPftvarcon.F90:52-53, 146, 380-386, 821-827)`, `(main/EDParamsMod.F90:57-84)`

## Integration with the Disturbance Framework

Cohort-level `fire_mort` values are consumed by `EDPatchDynamicsMod` to build the fire disturbance rate (`dtype_ifire`), which drives `spawn_patches` for newly created burned patches `(main/EDMainMod.F90:218-223)`. Fire-killed biomass enters litter pools through the standard mortality pathway.

Sources: `(main/EDMainMod.F90:218-223)`, `(biogeochem/EDPatchDynamicsMod.F90)`
