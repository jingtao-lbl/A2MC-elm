# Fire Spread and Intensity

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `fire/SFMainMod.F90` (driver routines)
- `fire/SFEquationsMod.F90` (pure-function math library)
- `fire/FatesFuelMod.F90` (`fuel_type` object on each patch)
- `fire/FatesFuelClassesMod.F90` (`fuel_classes` enum)
- `fire/SFFireWeatherMod.F90` (effective wind speed)
- `fire/SFParamsMod.F90`

## Purpose and Scope

This document describes how the SPITFIRE module in FATES computes daily fire spread and intensity. These calculations form the Rothermel (1972) fire spread core adapted from Thonicke et al. 2010. Topics covered:

- Fuel characteristic calculations (loading, moisture, bulk density, surface-area-to-volume ratio, moisture of extinction)
- Effective wind speed at the fire front (now site-aggregated, not per patch)
- Rate of spread (forward and backward) using the Rothermel equation
- Surface fuel consumption and fire residence time
- Wildfire ellipse, area burnt, and fire-line intensity
- Wildfire vs prescribed-fire classification (intensity branching)

For fire weather indices, ignition counts, and mode selection see `ignition.md`. For the translation of fire intensity and residence time into per-cohort mortality see `effects.md`. For the prescribed-fire side branch, see `managed_fire.md`.

## Execution Order

The spread-and-intensity subroutines run inside `DailyFireModel` `(fire/SFMainMod.F90:60-66)`:

```
UpdateFireWeather             -> fireWeather%effective_windspeed (site)
                                 fireWeather%rx_flag             (site)
UpdateFuelCharacteristics     -> currentPatch%fuel%* (loading, frac_loading,
                                 effective_moisture, bulk_density_notrunks,
                                 SAV_notrunks, MEF_notrunks, average_moisture_notrunks)
CalculateSurfaceRateOfSpread  -> currentPatch%ROS_front, ROS_back              (per patch)
CalculateSurfaceFireIntensity -> currentPatch%fuel%frac_burnt, TFC_ROS, tau_l,
                                 FI; classify nonrx_fire vs rx_fire             (per patch)
CalculateAreaBurnt            -> currentPatch%FD, nonrx_frac_burnt              (wildfire only)
CalculateRxFireAreaBurnt      -> currentPatch%rx_frac_burnt; finalize fire,
                                 frac_burnt                                     (per patch)
```

Each patch is processed independently inside the per-patch loops; bareground patches are skipped via `nocomp_pft_label /= nocomp_bareground` in every routine.

## Fuel Characteristics

### Fuel Size Classes

SPITFIRE uses `num_fuel_classes = 6` fuel size classes. Indices are accessed through type-bound functions on the typed enum object `fuel_classes` `(fire/FatesFuelClassesMod.F90:10-29)`:

| Index | Accessor | Description |
|---|---|---|
| 1 | `fuel_classes%twigs()` | Twigs (fine CWD; ~1-h time-lag) |
| 2 | `fuel_classes%small_branches()` | Small branches (~10-h) |
| 3 | `fuel_classes%large_branches()` | Large branches (~100-h) |
| 4 | `fuel_classes%trunks()` | Trunks (~1000-h; excluded from ROS and intensity) |
| 5 | `fuel_classes%dead_leaves()` | Dead leaves / fine litter |
| 6 | `fuel_classes%live_grass()` | Live grass |

The 1h/10h/100h/1000h "time-lag" labels are interpretive (from Thonicke 2010 / Rothermel 1972), not encoded in source. Index 2 (small branches) now has a public accessor; in older versions it was unnamed and accessed via array slicing.

### `fuel_type` Object

Per-patch fuel state is held in a `fuel_type` object `(fire/FatesFuelMod.F90:15-40)` attached as `currentPatch%fuel`:

| Member | Units | Description |
|---|---|---|
| `loading(num_fuel_classes)` | kgC/m² | Per-class fuel loading |
| `frac_loading(num_fuel_classes)` | – | Per-class fraction of total fuel |
| `effective_moisture(num_fuel_classes)` | – | Per-class moisture / MEF |
| `frac_burnt(num_fuel_classes)` | – | Per-class fraction burnt |
| `non_trunk_loading` | kgC/m² | Total fuel excluding trunks |
| `bulk_density_notrunks` | kg/m³ | Weighted-average bulk density (no trunks) |
| `SAV_notrunks` | cm⁻¹ | Weighted-average SAV (no trunks) |
| `MEF_notrunks` | – | Weighted-average MEF (no trunks) |
| `average_moisture_notrunks` | – | Weighted-average fuel moisture (no trunks) |

Type-bound methods: `Init`, `Fuse` (patch fusion), `UpdateLoading`, `SumLoading`, `CalculateFractionalLoading`, `UpdateFuelMoisture`, `AverageBulkDensity_NoTrunks`, `AverageSAV_NoTrunks`, `CalculateFuelBurnt`, `CalculateResidenceTime` `(fire/FatesFuelMod.F90:29-39)`.

### Fuel Loading

`UpdateFuelCharacteristics` `(fire/SFMainMod.F90:145-191)` updates loading from litter pools `(fire/SFMainMod.F90:171-173)`:

```
fuel%UpdateLoading(sum(litter%leaf_fines), litter%ag_cwd(1), litter%ag_cwd(2),
                   litter%ag_cwd(3), litter%ag_cwd(4), patch%livegrass)
```

`SumLoading` aggregates `non_trunk_loading`; `CalculateFractionalLoading` divides each class by the total to give `frac_loading`.

### Fuel Moisture

Per-class fuel moisture follows Thonicke 2010 Eq. 6 — exponential decay with the fire-weather index `(fire/FatesFuelMod.F90:240-267)`:

```
alpha_FMC(c)   = SF_val_SAV(c) / SF_val_drying_ratio       (c != live_grass)
moisture(c)    = exp(-alpha_FMC(c) * fire_weather_index)
```

Live grass uses the **twigs SAV** rather than its own SAV `(fire/FatesFuelMod.F90:256-263)`:

```
alpha_FMC(live_grass) = SF_val_SAV(twigs) / SF_val_drying_ratio
```

The source comment at `(fire/FatesFuelMod.F90:259)` notes "live grass has same SAV as dead grass, but retains more moisture with this calculation." All classes (including trunks) get the same exponential drying for bookkeeping, but trunks are excluded from spread/intensity calculations.

### Moisture of Extinction

Per-class MEF is computed inline by the helper `MoistureOfExtinction` `(fire/FatesFuelMod.F90:271-313)` following Peterson & Ryan 1986 Eq. 27:

```
MEF(c) = MEF_a - MEF_b * log(SAV(c))     with MEF_a = 0.524, MEF_b = 0.066
```

The source comment lists approximate MEFs from Thonicke 2010 SAV values: twigs = 0.355, small branches = 0.44, large branches = 0.525, trunks = 0.63, dead leaves = 0.248, live grass = 0.248.

`effective_moisture(c) = moisture(c) / MEF(c)` is computed inside `UpdateFuelMoisture` `(fire/FatesFuelMod.F90:221)`.

### Patch-Level Averages (No Trunks)

`AverageBulkDensity_NoTrunks` `(fire/FatesFuelMod.F90:317-345)` and `AverageSAV_NoTrunks` `(fire/FatesFuelMod.F90:349-377)` compute weighted averages over all non-trunk classes:

```
bulk_density_notrunks = sum_{c != trunks} frac_loading(c) * SF_val_FBD(c)
SAV_notrunks          = sum_{c != trunks} frac_loading(c) * SF_val_SAV(c)
```

`average_moisture_notrunks` and `MEF_notrunks` are summed analogously inside `UpdateFuelMoisture` `(fire/FatesFuelMod.F90:223-227)`. Note: these use `frac_loading` directly (which sums to 1 across all six classes including trunks), so the fractions do not renormalize after excluding trunks. This is a simplification compared to older SPITFIRE code that explicitly divided by `(1 - frac_loading(trunks))`.

Sources: `(fire/FatesFuelMod.F90)`, `(fire/SFMainMod.F90:145-191)`

## Wind Effect (Site-Level)

`UpdateFireWeather` computes a single site-level effective wind speed via `CalculateTreeGrassAreaSite` `(main/EDTypesMod.F90:731-762)` to get site-aggregated tree, grass, and bare fractions, then calls `currentSite%fireWeather%UpdateEffectiveWindSpeed` `(fire/SFFireWeatherMod.F90:51-71)`:

```
effective_windspeed = wind_speed_m_per_min * (tree_fraction*0.4 + (grass_fraction + bare_fraction)*0.6)
```

The factors `wind_atten_treed = 0.4` and `wind_atten_grass = 0.6` `(fire/SFFireWeatherMod.F90:58-59)` represent the surface-roughness attenuations.

The source comment at `(fire/SFMainMod.F90:79-80)` explains the design choice: "Currently we use tree and grass fraction averaged over whole grid (site) to prevent extreme divergence." This is a change from older versions where `wind_effect` ran per patch. In `CalculateAreaBurnt`, the patch-level `tree_fraction_patch = currentPatch%total_tree_area / currentPatch%area` is still used inside the length-to-breadth ratio `(fire/SFMainMod.F90:485-486)`.

Sources: `(fire/SFFireWeatherMod.F90:51-71)`, `(fire/SFMainMod.F90:73-141)`, `(main/EDTypesMod.F90:731-762)`

## Rate of Spread

`CalculateSurfaceRateOfSpread` `(fire/SFMainMod.F90:267-347)` calls pure functions in `SFEquationsMod` to assemble the Rothermel (1972) ROS as laid out in Thonicke et al. 2010 Appendix A.

### Packing Ratio

```
beta       = currentPatch%fuel%bulk_density_notrunks / SF_val_part_dens     (Rothermel Eq. 31)
beta_op    = OptimumPackingRatio(SAV_notrunks)        = 0.200395 * SAV^(-0.8189)    (A6)
beta_ratio = beta / beta_op                           (or 0 if beta_op < nearzero)
```

`OptimumPackingRatio` `(fire/SFEquationsMod.F90:48-69)`. Mineral content is then removed from the non-trunk loading `(fire/SFMainMod.F90:313-314)`:

```
fuel%non_trunk_loading = fuel%non_trunk_loading * (1 - SF_val_miner_total)
```

### Heat of Pre-ignition

`HeatofPreignition(fuel_moisture)` `(fire/SFEquationsMod.F90:197-218)`:

```
q_ig = 581 + 2594 * fuel_moisture     [kJ/kg]
```

Thonicke 2010 Eq. A4 / Rothermel 1972 Eq. 12 (converted from Btu/lb to kJ/kg).

### Wind Coefficient

`WindFactor(wind_speed, beta_ratio, SAV)` `(fire/SFEquationsMod.F90:246-275)`:

```
b        = 0.15988 * SAV^0.54            (Thonicke A7)
c        = 7.47    * exp(-0.8711 * SAV^0.55)   (A8)
e        = 0.715   * exp(-0.01094 * SAV)       (A9, Rothermel Eq. 50 coefficient)
phi_wind = c * (3.281 * effective_windspeed)^b * beta_ratio^(-e)   (A5)
```

The factor `3.281` converts wind speed from m/min to ft/min for compatibility with the original Rothermel formulation.

### Propagating Flux and Effective Heating Number

`PropagatingFlux(beta, SAV)` `(fire/SFEquationsMod.F90:279-296)`:

```
xi  = exp((0.792 + 3.7597 * SAV^0.5) * (beta + 0.1)) / (192 + 7.9095 * SAV)   (A2)
```

`EffectiveHeatingNumber(SAV)` `(fire/SFEquationsMod.F90:222-242)`:

```
eps = exp(-4.528 / SAV)     (A3, returns 0 if SAV < nearzero)
```

### Reaction Intensity

`ReactionIntensity(fuel_loading, SAV, beta_ratio, moisture, MEF)` `(fire/SFEquationsMod.F90:158-193)` chains three helpers:

```
max_reaction_vel = MaximumReactionVelocity(SAV) = 1 / (0.0591 + 2.926 * SAV^(-1.5))     (Rothermel Eq. 36)
opt_reaction_vel = OptimumReactionVelocity(max_reaction_vel, SAV, beta_ratio)
                 = max_reaction_vel * beta_ratio^a * exp(a*(1-beta_ratio))               (Eq. 38)
   with a       = 8.9033 * SAV^(-0.7913)                                                 (Table A1)
moist_coeff      = MoistureCoefficient(moisture, MEF)
                 = max(0, 1 - 2.59*mw + 5.11*mw^2 - 3.52*mw^3)
   with mw      = moisture / MEF
i_r              = opt_reaction_vel * fuel_loading * SF_val_fuel_energy * moist_coeff * SF_val_miner_damp
                                                                                         [kJ/m^2/min]
```

The `fuel_loading` argument is `non_trunk_loading / 0.45` (kgC/m² → kgBiomass/m²) `(fire/SFMainMod.F90:317)`.

### Forward and Backward ROS

`ForwardRateOfSpread` `(fire/SFEquationsMod.F90:300-324)`:

```
if bulk_density <= 0 .or. eps <= 0 .or. q_ig <= 0:
    ROS_front = 0
else:
    ROS_front = (i_r * xi * (1 + phi_wind)) / (bulk_density * eps * q_ig)      [m/min]
```

`BackwardRateOfSpread` `(fire/SFEquationsMod.F90:328-344)`:

```
ROS_back = ROS_front * exp(-0.012 * site%wind)                                  [m/min]
```

Backward ROS uses the **raw** site wind (m/min), not `effective_windspeed`, reflecting that backing fires are less sheltered by surface roughness `(fire/SFMainMod.F90:339-341)`.

Sources: `(fire/SFMainMod.F90:267-347)`, `(fire/SFEquationsMod.F90:48-344)`

## Surface Fuel Consumption and Residence Time

`CalculateSurfaceFireIntensity` `(fire/SFMainMod.F90:351-444)` calls two type-bound methods on `currentPatch%fuel`.

### Per-Class Burnt Fraction

`CalculateFuelBurnt(fuel_consumed)` `(fire/FatesFuelMod.F90:381-438)` computes a piecewise burnt fraction as a function of `effective_moisture` (Thonicke 2010 Eq. B1). Using `m = effective_moisture(c)`:

| Moisture range | `frac_burnt(c)` |
|---|---|
| `m <= SF_val_min_moisture(c)` | `1.0` |
| `SF_val_min_moisture(c) < m <= SF_val_mid_moisture(c)` | `SF_val_low_moisture_Coeff(c) - SF_val_low_moisture_Slope(c)*m`, clipped to `[0, 1]` |
| `SF_val_mid_moisture(c) < m <= 1.0` | `SF_val_mid_moisture_Coeff(c) - SF_val_mid_moisture_Slope(c)*m`, clipped to `[0, 1]` |
| `m > 1.0` | `0.0` |

Live grass is then capped at `max_grass_frac = 0.8` `(fire/FatesFuelMod.F90:400, 427-429)`, and every burnt fraction is reduced by mineral content `(fire/FatesFuelMod.F90:432)`:

```
frac_burnt(live_grass) = min(0.8, frac_burnt(live_grass))
frac_burnt(:)          = frac_burnt(:) * (1 - SF_val_miner_total)
fuel_consumed(c)       = frac_burnt(c) * loading(c)                            [kgC/m^2]
```

### Total Fuel Consumed in ROS (`TFC_ROS`)

Trunks are excluded from the fuel consumed by spreading fire `(fire/SFMainMod.F90:388)`:

```
TFC_ROS = sum(fuel_consumed) - fuel_consumed(fuel_classes%trunks())            [kgC/m^2]
```

### Fire Residence Time

`CalculateResidenceTime(tau_l)` `(fire/FatesFuelMod.F90:442-471)` follows Peterson & Ryan 1986 / Thonicke 2010:

```
tau_l = sum_{c != trunks} 39.4 * (frac_loading(c) * non_trunk_loading / 0.45 / 10) *
        (1 - (1 - frac_burnt(c))^0.5)
tau_l = min(8.0, tau_l)                                                         [min]
```

The `/ 0.45 / 10` converts from kgC/m² to gBiomass/cm² (factor 0.45 for C → biomass, factor 10 for kg/m² → g/cm²). `tau_l` is capped at 8 minutes per Peterson & Ryan's literature survey, and is consumed downstream by `CambialMortality` (see `effects.md`).

Sources: `(fire/FatesFuelMod.F90:381-471)`, `(fire/SFMainMod.F90:383-388)`

## Fire Intensity and Wildfire/Rx Classification

`CalculateSurfaceFireIntensity` `(fire/SFMainMod.F90:351-444)` computes `FI` unconditionally for every patch with ignition or rx burn-window flag, then uses the threshold check to **classify** the fire type.

### Initialization

```
FI               = 0
nonrx_fire = 0,    rx_fire = 0
nonrx_FI   = 0,    rx_FI   = 0
```
`(fire/SFMainMod.F90:391-395)`.

### Compute FI

`(fire/SFMainMod.F90:397-402)`:

```
has_ignition = (currentSite%NF > 0)
if has_ignition .or. fireWeather%rx_flag == 1:
    FI = FireIntensity(TFC_ROS / 0.45, ROS_front / 60.0)        [kW/m]
```

`FireIntensity(fuel_consumed, ros)` `(fire/SFEquationsMod.F90:464-478)` is simply

```
FireIntensity = SF_val_fuel_energy * fuel_consumed * ros        (Thonicke Eq. 15)
```

with `fuel_consumed` in kg/m² (biomass) and `ros` in m/s.

### Classify

`(fire/SFMainMod.F90:403-429)`:

```
fi_check          = (FI > SF_val_fire_threshold)
rxfire_fuel_check = (SF_val_rxfire_fuel_min < non_trunk_loading < SF_val_rxfire_fuel_max)

if rx_flag == 1 .and. rxfire_fuel_check:
    rxfire_area_fuel += currentPatch%area
    is_rxfire = is_prescribed_burn(FI, NF, SF_val_rxfire_min_threshold,
                                    SF_val_rxfire_max_threshold, SF_val_fire_threshold)
    if is_rxfire:
        rxfire_area_fi += currentPatch%area
        rx_fire = 1
    else if has_ignition .and. fi_check:
        nonrx_fire = 1
else if has_ignition .and. fi_check:
    nonrx_fire = 1
```

`is_prescribed_burn` is documented in `managed_fire.md`. After classification:

```
if nonrx_fire == 1:
    NF_successful += NF * FDI * (currentPatch%area / AREA)
    nonrx_FI = FI
else if rx_fire == 1:
    rx_FI = FI
```

## Wildfire Area Burnt

`CalculateAreaBurnt` `(fire/SFMainMod.F90:448-504)` runs only for patches with `nonrx_fire == 1`.

### Fire Duration

`FireDuration(FDI)` `(fire/SFEquationsMod.F90:348-363)`, Thonicke 2010 Eq. 14:

```
FD = (SF_val_max_durat + 1) / (1 + SF_val_max_durat * exp(SF_val_durat_slope * FDI))   [min]
```

Higher `FDI` → longer-burning fires.

### Length-to-Breadth Ratio

`LengthToBreadth(effective_windspeed, tree_fraction)` `(fire/SFEquationsMod.F90:367-399)`. Below 1 km/hr effective wind the fire is circular (`lb = 1`). Otherwise:

**Forest fuels** (`tree_fraction > 0.55`, CFFBPS Eq. 79):
```
lb = 1 + 8.729 * (1 - exp(-0.03 * windspeed_km_hr))^2.155
```

**Grassland fuels** (`tree_fraction <= 0.55`, CFFBPS Eq. 80 with Wotton et al. 2009 typo correction):
```
lb = 1.1 * windspeed_km_hr^0.464
```

`tree_fraction` here is the **patch-level** value `currentPatch%total_tree_area / currentPatch%area` `(fire/SFMainMod.F90:485)`, not the site-aggregated tree fraction used to compute `effective_windspeed`.

### Fire Size and Area Burnt

`FireSize(lb, ros_back, ros_forward, FD)` `(fire/SFEquationsMod.F90:403-433)` computes the area of the ellipse (Arora & Boer 2005 Eq. 14):

```
df         = ros_forward * FD                                                   [m]
db         = ros_back    * FD                                                   [m]
fire_size  = (pi / (4*lb)) * (df + db)^2                                        [m^2]
```

`AreaBurnt(fire_size, NF, FDI)` `(fire/SFEquationsMod.F90:437-460)`, Thonicke 2010 Eq. 1:

```
area_burnt        = fire_size * NF * FDI                                        [m^2/km^2/day]
nonrx_frac_burnt  = min(0.99, area_burnt / m2_per_km2)
```

`m2_per_km2 = 1.0e6` `(main/FatesConstantsMod.F90:259)`. The `0.99` cap (`max_frac_burnt`) prevents single-day complete patch consumption `(fire/SFMainMod.F90:468)`.

## Patch-Level State Variables

| Variable | Units | Set by |
|---|---|---|
| `currentPatch%fuel%loading(:)` | kgC/m² | `UpdateFuelCharacteristics` |
| `currentPatch%fuel%frac_loading(:)` | – | `UpdateFuelCharacteristics` |
| `currentPatch%fuel%effective_moisture(:)` | – | `UpdateFuelCharacteristics` |
| `currentPatch%fuel%non_trunk_loading` | kgC/m² | `UpdateFuelCharacteristics` |
| `currentPatch%fuel%bulk_density_notrunks` | kg/m³ | `UpdateFuelCharacteristics` |
| `currentPatch%fuel%SAV_notrunks` | cm⁻¹ | `UpdateFuelCharacteristics` |
| `currentPatch%fuel%MEF_notrunks` | – | `UpdateFuelCharacteristics` |
| `currentPatch%fuel%average_moisture_notrunks` | – | `UpdateFuelCharacteristics` |
| `currentPatch%fuel%frac_burnt(:)` | – | `CalculateSurfaceFireIntensity` |
| `currentPatch%ROS_front`, `ROS_back` | m/min | `CalculateSurfaceRateOfSpread` |
| `currentPatch%TFC_ROS` | kgC/m² | `CalculateSurfaceFireIntensity` |
| `currentPatch%tau_l` | min | `CalculateSurfaceFireIntensity` |
| `currentPatch%FI`, `nonrx_FI`, `rx_FI` | kW/m | `CalculateSurfaceFireIntensity` |
| `currentPatch%nonrx_fire`, `rx_fire` | 0/1 | `CalculateSurfaceFireIntensity` |
| `currentPatch%FD` | min | `CalculateAreaBurnt` |
| `currentPatch%nonrx_frac_burnt` | – | `CalculateAreaBurnt` |
| `currentPatch%rx_frac_burnt` | – | `CalculateRxFireAreaBurnt` |
| `currentPatch%fire`, `frac_burnt` | – | `CalculateRxFireAreaBurnt` (sum of rx + nonrx) |

## Integration with Other Fire Components

**Upstream (from `ignition.md`):**
- `fireWeather%fire_weather_index` → fuel moisture
- `fireWeather%effective_windspeed` → ROS, length-to-breadth
- `fireWeather%rx_flag` → enables FI computation even without ignition
- `currentSite%FDI` → area burnt, fire duration
- `currentSite%NF` → area burnt, wildfire-vs-rx classification
- Litter pools (`leaf_fines`, `ag_cwd`, `livegrass`) → fuel loading

**Downstream (to `effects.md`):**
- `currentPatch%FI` drives scorch height (and thus crown damage)
- `currentPatch%tau_l` drives cambial damage
- `currentPatch%fire == 1` (wildfire OR rx fire) gates the post-fire mortality pipeline
- `currentPatch%frac_burnt` weights area-integrated impacts in patch dynamics
- Fuel consumption drives litter pool depletion

Sources: `(fire/SFMainMod.F90:46-69)`, `(fire/SFEquationsMod.F90)`, `(fire/FatesFuelMod.F90)`
