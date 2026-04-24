# Fire Spread and Intensity

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `fire/SFMainMod.F90`
- `fire/SFParamsMod.F90`
- `biogeochem/FatesLitterMod.F90`

## Purpose and Scope

This document describes how the SPITFIRE module in FATES computes daily fire spread and intensity. These calculations form the Rothermel (1972) fire spread core adapted from Thonicke et al. 2010. Topics covered:

- Fuel characteristic calculations (moisture, bulk density, surface-area-to-volume ratio, moisture of extinction)
- Wind effect on the effective windspeed at the fire front
- Rate of spread (forward and backward) using the Rothermel equation
- Ground fuel consumption and fire residence time
- Fire ellipse, area burnt, and fire line intensity

For fire danger indices, ignition counts, and mode selection see `ignition.md`. For the translation of fire intensity and residence time into per-cohort mortality see `effects.md`.

## Execution Order

The spread-and-intensity subroutines run back-to-back inside `fire_model` `(fire/SFMainMod.F90:104-108)`:

```
wind_effect              -> effect_wspeed            (patch)
charecteristics_of_fuel  -> fuel_bulkd, fuel_sav,
                            fuel_mef, fuel_eff_moist,
                            fuel_frac, litter_moisture (patch)
rate_of_spread           -> ROS_front, ROS_back      (patch)
ground_fuel_consumption  -> burnt_frac_litter,
                            TFC_ROS, tau_l           (patch)
area_burnt_intensity     -> FDI, NF, NF_successful,
                            FD, frac_burnt, FI, fire (site + patch)
```

Each patch is processed independently; bareground patches are skipped via the `nocomp_pft_label .ne. nocomp_bareground` guard in every routine.

## Fuel Characteristics

### Fuel Size Classes

SPITFIRE uses `NFSC = 6` fuel size classes. The named integer constants come from `biogeochem/FatesLitterMod.F90` and are imported by `SFMainMod` `(fire/SFMainMod.F90:30-36)`:

| Index | Constant | Description |
|---|---|---|
| 1 | `TW_SF` | Twigs (fine CWD) |
| 2 | — (no named constant) | Small branches |
| 3 | `LB_SF` | Large branches |
| 4 | `TR_SF` | Trunks (coarse CWD; excluded from ROS) |
| 5 | `DL_SF` | Dead leaves / fine litter |
| 6 | `LG_SF` | Live grass |

Index 2 has no named constant; small branches are accessed via array ranges like `tw_sf:lb_sf`. The 1h/10h/100h/1000h "time-lag" labels commonly attached to indices 1–4 are interpretive (from Thonicke 2010 / Rothermel), not written in FATES source.

### Fuel Moisture

`charecteristics_of_fuel` `(fire/SFMainMod.F90:177-344)` computes per-class fuel moisture (Thonicke 2010 Eq. 6) using an exponential decay with the accumulated Nesterov Index `(fire/SFMainMod.F90:260-280)`:

```
alpha_FMC(c)   = SF_val_SAV(c) / SF_val_drying_ratio     (c = tw..dl)
fuel_moisture(c) = exp(-alpha_FMC(c) * acc_NI)
fuel_moisture(lg_sf) = exp(-(SF_val_SAV(tw_sf)/SF_val_drying_ratio) * acc_NI)
```

Live grass uses the twigs SAV but retains more moisture because of species biology: the `fuel_moisture` formulation is the same exponential form but live grass has its own weighting. Trunks get the same exponential drying as other CWD classes for bookkeeping, but are excluded from spread calculations.

### Moisture of Extinction

Peterson & Ryan 1986 Eq. 27 `(fire/SFMainMod.F90:260)`:

```
MEF(c) = 0.524 - 0.066 * log(SF_val_SAV(c))        (for c = 1..nfsc)
```

The code comment notes that propagating Thonicke 2010 SAV values through this equation yields approximate MEFs of 0.355 (twigs), 0.44 (small branches), 0.525 (large branches), 0.63 (trunks), 0.248 (dead leaves), 0.248 (live grass).

The relative litter moisture used downstream is the ratio `fuel_moisture / MEF` per class `(fire/SFMainMod.F90:305-308)`:

```
litter_moisture(c) = fuel_moisture(c) / MEF(c)
```

### Patch-Level Averages

`charecteristics_of_fuel` computes averaged properties over classes 1–3 and 5–6, then rescales to exclude trunks `(fire/SFMainMod.F90:282-302)`:

```
fuel_bulkd     = sum(fuel_frac(tw..lb) * SF_val_FBD(tw..lb))
               + sum(fuel_frac(dl..lg) * SF_val_FBD(dl..lg))
fuel_sav       = similar sum over SF_val_SAV
fuel_mef       = similar sum over MEF
fuel_eff_moist = similar sum over fuel_moisture

# rescale so that trunk fraction does not dilute
fuel_bulkd     = fuel_bulkd     / (1 - fuel_frac(tr_sf))
fuel_sav       = fuel_sav       / (1 - fuel_frac(tr_sf))
fuel_mef       = fuel_mef       / (1 - fuel_frac(tr_sf))
fuel_eff_moist = fuel_eff_moist / (1 - fuel_frac(tr_sf))
```

Per-class fuel fractions are taken from the litter pools `(fire/SFMainMod.F90:230-250)`:

```
sum_fuel                = sum(leaf_fines) + sum(ag_cwd) + livegrass
fuel_frac(dl_sf)        = sum(leaf_fines) / sum_fuel
fuel_frac(tw_sf:tr_sf)  = ag_cwd(:) / sum_fuel
fuel_frac(lg_sf)        = livegrass / sum_fuel
```

### Key State Variables After `charecteristics_of_fuel`

| Variable | Units | Description |
|---|---|---|
| `sum_fuel` | kgC/m² | Total fuel load |
| `fuel_frac(1:6)` | – | Fraction of total fuel in each class |
| `fuel_bulkd` | kg/m³ | Weighted-average bulk density |
| `fuel_sav` | cm⁻¹ | Weighted-average SAV |
| `fuel_mef` | – | Weighted-average MEF |
| `fuel_eff_moist` | – | Weighted-average effective moisture |
| `litter_moisture(1:6)` | – | Per-class relative moisture |

Sources: `(fire/SFMainMod.F90:177-344)`

## Wind Effect

`wind_effect` `(fire/SFMainMod.F90:348-446)` converts host-model wind (converted to m/min at `(fire/SFMainMod.F90:381)`) into an effective wind speed at the fire front. Tree and grass fractions are computed from cohort crown areas, with grass capped to `1 - tree_fraction` to avoid double-counting under canopy `(fire/SFMainMod.F90:425)`. Effective wind speed per patch `(fire/SFMainMod.F90:439)`:

```
effect_wspeed = wind * (0.4*tree_fraction + 0.6*(grass_fraction + bare_fraction))
```

The factors `0.4` (trees) and `0.6` (grass/bare) represent 60% and 40% reductions from the host-model wind, respectively, reflecting surface roughness.

Sources: `(fire/SFMainMod.F90:348-446)`

## Rate of Spread

`rate_of_spread` `(fire/SFMainMod.F90:449-592)` implements the Rothermel (1972) fire spread model as laid out in Thonicke et al. 2010 Appendix A.

### Packing Ratio

```
beta      = fuel_bulkd / SF_val_part_dens               (A6)
beta_op   = 0.200395 * fuel_sav^(-0.8189)               (A6, optimum)
beta_ratio = beta / beta_op
```

Mineral content is first removed from `sum_fuel` via `sum_fuel = sum_fuel * (1 - SF_val_miner_total)` `(fire/SFMainMod.F90:484)` for the reaction-intensity calculation.

### Heat of Pre-ignition

Thonicke 2010 Eq. A4 / Rothermel 1972 Eq. 12 (converted from Btu/lb to kJ/kg) `(fire/SFMainMod.F90:514)`:

```
q_ig = 581 + 2594 * fuel_eff_moist                      [kJ/kg]
```

### Wind Coefficient

Thonicke 2010 Eqs. A5, A7, A8, A9 `(fire/SFMainMod.F90:520-538)`:

```
b        = 0.15988 * fuel_sav^0.54
c        = 7.47    * exp(-0.8711 * fuel_sav^0.55)
e        = 0.715   * exp(-0.01094 * fuel_sav)
phi_wind = c * (3.281 * effect_wspeed)^b * beta_ratio^(-e)
```

The factor `3.281` converts wind speed from m/min to ft/min for compatibility with the original Rothermel formulation.

### Propagating Flux and Effective Heating Number

Thonicke 2010 Eqs. A2, A3 `(fire/SFMainMod.F90:518, 544-545)`:

```
eps = exp(-4.528 / fuel_sav)
xi  = exp((0.792 + 3.7597 * fuel_sav^0.5) * (beta + 0.1))
      / (192 + 7.9095 * fuel_sav)
```

### Reaction Intensity

Thonicke 2010 Table A1 / Rothermel 1972 Eqs. 36, 38 `(fire/SFMainMod.F90:549-570)`:

```
a              = 8.9033 * fuel_sav^(-0.7913)
a_beta         = exp(a * (1 - beta_ratio))
reaction_v_max = 1 / (0.0591 + 2.926 * fuel_sav^(-1.5))
reaction_v_opt = reaction_v_max * beta_ratio^a * a_beta

mw_weight  = fuel_eff_moist / fuel_mef
moist_damp = max(0, 1 - 2.59*mw_weight + 5.11*mw_weight^2 - 3.52*mw_weight^3)

ir = reaction_v_opt * (sum_fuel / 0.45) * SF_val_fuel_energy
     * moist_damp * SF_val_miner_damp        [kJ/m^2/min]
```

The `/0.45` converts `kgC/m²` to `kgBiomass/m²`.

### Forward and Backward ROS

Thonicke 2010 Eqs. 9, 10 `(fire/SFMainMod.F90:574-585)`:

```
if fuel_bulkd <= 0 or eps <= 0 or q_ig <= 0:
    ROS_front = 0
else:
    ROS_front = (ir * xi * (1 + phi_wind)) / (fuel_bulkd * eps * q_ig)  [m/min]
ROS_back = ROS_front * exp(-0.012 * currentSite%wind)                   [m/min]
```

Backward ROS uses the **raw** site wind, not `effect_wspeed`, reflecting that backing fires are less sheltered by surface roughness.

Sources: `(fire/SFMainMod.F90:449-592)`

## Ground Fuel Consumption

`ground_fuel_consumption` `(fire/SFMainMod.F90:595-683)` computes the burnt fraction of each fuel class as a piecewise linear function of relative moisture `(fire/SFMainMod.F90:622-644)`. Using `m` as shorthand for `litter_moisture(c)`:

| Moisture range | `burnt_frac_litter(c)` |
|---|---|
| `m ≤ SF_val_min_moisture(c)` | `1.0` |
| `SF_val_min_moisture(c) < m ≤ SF_val_mid_moisture(c)` | `SF_val_low_moisture_Coeff(c) - SF_val_low_moisture_Slope(c)*m`, clipped to `[0, 1]` |
| `SF_val_mid_moisture(c) < m ≤ 1.0` | `SF_val_mid_moisture_Coeff(c) - SF_val_mid_moisture_Slope(c)*m`, clipped to `[0, 1]` |
| `m ≥ 1.0` | `0.0` |

Live grass is capped at 0.8 to prevent complete removal `(fire/SFMainMod.F90:647)`, and every burnt fraction is then reduced by mineral content `(fire/SFMainMod.F90:650)`:

```
burnt_frac_litter(lg_sf) = min(0.8, burnt_frac_litter(lg_sf))
burnt_frac_litter(:)     = burnt_frac_litter(:) * (1 - SF_val_miner_total)
```

### Total Fuel Consumed in ROS

Per-class ground fuel consumption is computed `(fire/SFMainMod.F90:654-657)`:

```
FC_ground(tw..tr) = burnt_frac_litter(tw..tr) * litt_c%ag_cwd(tw..tr)
FC_ground(dl_sf)  = burnt_frac_litter(dl_sf)  * sum(leaf_fines)
FC_ground(lg_sf)  = burnt_frac_litter(lg_sf)  * livegrass
```

Only fuels affecting ROS are summed into `TFC_ROS` (trunks excluded) `(fire/SFMainMod.F90:676)`:

```
TFC_ROS = sum(FC_ground) - FC_ground(tr_sf)              [kgC/m^2]
```

### Fire Residence Time

Peterson & Ryan 1986 / Thonicke 2010, per fuel class and then summed `(fire/SFMainMod.F90:666-672)`:

```
tau_b(c)      = 39.4 * (fuel_frac(c) * sum_fuel / 0.45 / 10)
                * (1 - (1 - burnt_frac_litter(c))^0.5)
tau_b(tr_sf)  = 0
tau_l         = min(8, sum_c tau_b(c))                   [min]
```

The `/ 0.45 / 10` converts from `kgC/m²` to `gBiomass/cm²` (factor 0.45 for C → biomass, factor 10 for kg/m² → g/cm²). `tau_l` is capped at 8 minutes per Peterson & Ryan's literature survey, and is consumed downstream by `cambial_damage_kill` in `effects.md`.

Sources: `(fire/SFMainMod.F90:595-683)`

## Area Burnt and Fire Intensity

`area_burnt_intensity` `(fire/SFMainMod.F90:687-885)` combines fire danger, ignition counts, ROS, residence time, and fuel consumption into daily area burnt and fire line intensity per patch.

### Fire Duration

Thonicke 2010 Eq. 14 `(fire/SFMainMod.F90:785-786)`:

```
FD = (SF_val_max_durat + 1)
     / (1 + SF_val_max_durat * exp(SF_val_durat_slope * FDI))  [min]
```

Higher `FDI` → longer-burning fires. Typical CDL defaults: `SF_val_max_durat ≈ 240 min`, `SF_val_durat_slope ≈ -10`.

### Length-to-Breadth Ratio

Fires spread in an ellipse with wind along the major axis. The length-to-breadth ratio `lb` depends on wind speed and vegetation type `(fire/SFMainMod.F90:803-814)`. Below 1 km/hr effective wind the fire is circular (`lb = 1`). Otherwise:

**Forest fuels** (`tree_fraction > 0.55`, CFFBPS Eq. 79):
```
lb = 1 + 8.729 * (1 - exp(-0.03 * effect_wspeed_kmh))^2.155
```

**Grassland fuels** (`tree_fraction ≤ 0.55`, CFFBPS Eq. 80 with Wotton et al. 2009 typo correction):
```
lb = 1.1 * effect_wspeed_kmh^0.464
```

where `effect_wspeed_kmh = effect_wspeed * 0.06` converts m/min to km/hr.

### Fire Size and Area Burnt

Arora & Boer 2005 Eq. 14 + Thonicke 2010 Eq. 1 `(fire/SFMainMod.F90:820-844)`:

```
db           = ROS_back  * FD                             [m]
df           = ROS_front * FD                             [m]
size_of_fire = (pi / (4 * lb)) * (df + db)^2              [m^2]
AB           = size_of_fire * NF * FDI                    [m^2 per km^2 per day]
frac_burnt   = min(0.99, AB / 1e6)
```

The 0.99 cap prevents a single-day complete patch consumption.

### Fire Line Intensity

Thonicke 2010 Eq. 15 `(fire/SFMainMod.F90:854-859)`:

```
ROS = ROS_front / 60                              [m/min -> m/s]
W   = TFC_ROS   / 0.45                            [kgC/m^2 -> kgBiomass/m^2]
FI  = SF_val_fuel_energy * W * ROS                [kJ/kg * kg/m^2 * m/s = kW/m]
```

### Fire Flag

Only fires exceeding `SF_val_fire_threshold` (default 50 kW/m) are considered successful `(fire/SFMainMod.F90:866-876)`:

```
if FI > SF_val_fire_threshold:
    fire          = 1
    NF_successful += NF * FDI * (currentPatch%area / AREA)
else:
    fire = 0, FD = 0, frac_burnt = 0
```

Sources: `(fire/SFMainMod.F90:687-885)`

## Key Patch-Level State Variables

| Variable | Units | Set by |
|---|---|---|
| `fuel_bulkd` | kg/m³ | `charecteristics_of_fuel` |
| `fuel_sav` | cm⁻¹ | `charecteristics_of_fuel` |
| `fuel_mef` | – | `charecteristics_of_fuel` |
| `fuel_eff_moist` | – | `charecteristics_of_fuel` |
| `fuel_frac(1:6)` | – | `charecteristics_of_fuel` |
| `litter_moisture(1:6)` | – | `charecteristics_of_fuel` |
| `effect_wspeed` | m/min | `wind_effect` |
| `ROS_front`, `ROS_back` | m/min | `rate_of_spread` |
| `burnt_frac_litter(1:6)` | – | `ground_fuel_consumption` |
| `TFC_ROS` | kgC/m² | `ground_fuel_consumption` |
| `tau_l` | min | `ground_fuel_consumption` |
| `FD` | min | `area_burnt_intensity` |
| `frac_burnt` | – | `area_burnt_intensity` |
| `FI` | kW/m | `area_burnt_intensity` |
| `fire` | 0/1 | `area_burnt_intensity` |

Sources: `(fire/SFMainMod.F90:80-885)`

## Integration with Other Fire Components

**Upstream (from `ignition.md`):**
- `acc_NI` → fuel moisture and `FDI`
- `NF` lightning/anthropogenic ignition counts
- Host-model wind, temperature, humidity, precipitation
- Litter pools (`leaf_fines`, `ag_cwd`, `livegrass`)

**Downstream (to `effects.md`):**
- `FI` drives scorch height (and thus crown damage)
- `tau_l` drives cambial damage
- `frac_burnt` weights area-integrated impacts in patch dynamics
- Fuel consumption drives litter pool depletion

Sources: `(fire/SFMainMod.F90:80-115)`
