# Phenology and Leaf Dynamics

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/EDPhysiologyMod.F90` (main phenology)
- `biogeochem/FatesAllometryMod.F90` (target biomass, tree_lai/sai)
- `main/EDParamsMod.F90` (global phenology parameters)
- `main/EDPftvarcon.F90` (PFT phenology parameters)
- `main/EDTypesMod.F90` (status constants, memory windows)
- `main/FatesConstantsMod.F90` (leaves_on / leaves_off / stress_decid flags)
- `parameter_files/fates_params_default.cdl` (ground-truth defaults)

</details>

## Purpose and Scope

This document describes the phenology system in FATES that determines the seasonal timing of leaf flushing and abscission for different plant functional types (PFTs). The system operates in two stages each day. First, `phenology()` (`EDPhysiologyMod.F90:909-1525`) updates site-level cold-deciduous state and the PFT-level `elong_factor`. Second, `phenology_leafonoff()` (`EDPhysiologyMod.F90:1529-1760`) translates those states into actual leaf/fine-root/stem transfers from storage carbon at the cohort level.

For photosynthesis, see `../biophysics/photosynthesis.md`. For allocation, see `parteh/index.md`.

## Phenological Strategies

FATES supports three strategies, selected per PFT through two flag parameters (`fates_phen_season_decid`, `fates_phen_stress_decid`):

| Strategy | Parameter switch | Semantics |
|---|---|---|
| Evergreen | `season_decid=0` and `stress_decid=0` | `elong_factor = 1` at all times |
| Cold deciduous | `season_decid=1` | Shared site-level GDD/NCD state machine in `phenology()`; `elong_factor` is 0 or 1 |
| Drought hard-deciduous | `stress_decid = ihard_stress_decid` | Per-PFT state machine; `elong_factor` is 0 or 1 |
| Drought semi-deciduous | `stress_decid = isemi_stress_decid` | Per-PFT; `elong_factor` may take intermediate values in `[0, 1]` |

The integer constants `ihard_stress_decid` and `isemi_stress_decid` are defined in `FatesConstantsMod.F90` and used in `EDPhysiologyMod.F90:1285-1495`.

Sources: `EDPhysiologyMod.F90:1110-1520`, `EDPftvarcon.F90`.

## State Constants and Memory Windows

Cold and drought status flags (`cstatus`, `dstatus`) are defined in `EDTypesMod.F90:93-102`:

| Constant | Value | Meaning |
|---|---|---|
| `phen_cstat_nevercold` | 0 | Site has never experienced a cold day; cold-deciduous PFTs will not flush without at least one chilling day |
| `phen_cstat_iscold` | 1 | Site is in cold state, leaves should be off |
| `phen_cstat_notcold` | 2 | Site is in warm state, leaves allowed on |
| `phen_dstat_timeoff` | 0 | Drought: leaves forced off by timing |
| `phen_dstat_moistoff` | 1 | Drought: leaves off from moisture |
| `phen_dstat_moiston` | 2 | Drought: leaves on from moisture |
| `phen_dstat_timeon` | 3 | Drought: leaves forced on by timing |
| `phen_dstat_pshed` | 4 | Drought: partial shedding (semi-deciduous) |

Two fixed memory windows (`EDTypesMod.F90:79,88`) control how phenology reads the environment:

- `num_vegtemp_mem = 10` days (window over which cold days are counted against `phen_ncolddayslim`)
- `numWaterMem = 10` days (window for the rolling soil-moisture average used by drought phenology)

The `leaves_on`, `leaves_off`, and `leaves_shedding` cohort status codes are defined in `FatesConstantsMod.F90` and set in `phenology_leafonoff()` below.

## Cold Deciduous Phenology

### GDD Threshold Equation (Botta et al. 2000)

`phenology()` at `EDPhysiologyMod.F90:1037` computes the growing-degree-day threshold each day as:

```
gdd_threshold = phen_a + phen_b * exp(phen_c * nchilldays)
```

where `nchilldays` is the number of chilling days accumulated since the start of the counting window (day 270 in the Northern Hemisphere, day 120 in the Southern). Each day with mean vegetation temperature below `phen_chilltemp` (default 5 deg C) increments `nchilldays` (`EDPhysiologyMod.F90:1031-1033`). The equation is attributed to Botta et al. 2000 (Global Change Biology, 6:709-725) in the source comments at `EDPhysiologyMod.F90:999`.

### Correct default parameter values (verified against CDL)

The following defaults come directly from `parameter_files/fates_params_default.cdl:1700-1712`:

| CDL name | Internal name | Default | Units | Description |
|---|---|---|---|---|
| `fates_phen_gddthresh_a` | `ED_val_phen_a` | **-68** | unitless | GDD threshold intercept |
| `fates_phen_gddthresh_b` | `ED_val_phen_b` | **638** | unitless | GDD threshold multiplier |
| `fates_phen_gddthresh_c` | `ED_val_phen_c` | **-0.01** | unitless | GDD threshold exponent (NEGATIVE) |
| `fates_phen_chilltemp` | `ED_val_phen_chiltemp` | 5.0 | deg C | Threshold below which a day counts as a chilling day |
| `fates_phen_coldtemp` | `ED_val_phen_coldtemp` | 7.5 | deg C | Threshold below which a day counts as a cold day for leaf-drop |
| `fates_phen_mindayson` | `ED_val_phen_mindayson` | **90** | days | Minimum duration leaves must remain on before drop is permitted |
| `fates_phen_ncolddayslim` | `ED_val_phen_ncolddayslim` | 5 | days | Cold-day count within the 10-day `num_vegtemp_mem` window that triggers leaf drop |

Sources: `EDParamsMod.F90:62-68`, `fates_params_default.cdl:1700-1712`.

### Mechanism: more chilling means LESS accumulated warmth is required

Because `phen_c = -0.01 < 0`, the exponential `exp(phen_c * nchilldays)` **decays** as `nchilldays` increases. With default values:

| `nchilldays` | `gdd_threshold = -68 + 638 * exp(-0.01 * nchilldays)` |
|---|---|
| 0 | 570.0 |
| 50 | 318.9 |
| 100 | 166.7 |
| 150 | 74.4 |
| 200 | 18.5 |
| 300 | -36.2 (effectively zero, flushing immediately once any GDD accumulates) |

The correct mechanistic interpretation is: **more chilling days means the plant requires less accumulated warmth before flushing**. Arctic sites with 150+ chilling days will produce very small GDD thresholds under defaults, consistent with the observed too-early leaf-on behavior documented in `Program/phenology_fates/PHENOLOGY_CALIBRATION_RESULTS.md`.

This is the opposite of the direction implied by the previous wiki version, which asserted "more chilling requires more warmth".

### Cold Leaf-On Trigger

Cold leaf flushing occurs at `EDPhysiologyMod.F90:1110-1119` when all of the following hold:

1. `cstatus` is either `phen_cstat_iscold` or `phen_cstat_nevercold`
2. `grow_deg_days > gdd_threshold`
3. `cndaysleafoff > phen_mindayson` (at least 90 days since last leaf drop under defaults)
4. `nchilldays >= 1` (prevents warm-climate plants from ever flushing a cold-deciduous PFT)

On success, `cstatus` is set to `phen_cstat_notcold`, the leaf-on date is recorded, and `grow_deg_days` is zeroed until the next counting season.

### Cold Leaf-Off Trigger

Cold leaf shedding (`EDPhysiologyMod.F90:1132-1147`) requires:

1. `cstatus == phen_cstat_notcold`
2. `model_day_int > num_vegtemp_mem` (at least 10 days into the simulation)
3. `ncolddays > phen_ncolddayslim` where `ncolddays` counts days below `phen_coldtemp` within the 10-day `vegtemp_memory` buffer
4. `cndaysleafon > phen_mindayson`

On trigger, `cstatus` is set to `phen_cstat_iscold` and `grow_deg_days` is reset.

### 400-day Cold-Lifespan Cap

A second leaf-off path at `EDPhysiologyMod.F90:1155-1167` forces `cstatus = phen_cstat_nevercold` when a cold-deciduous PFT has been flushed for more than 400 days. In warm climates where `nchilldays` never increments this effectively prevents re-emergence.

## Drought Deciduous Phenology

`phenology()` iterates over PFTs at `EDPhysiologyMod.F90:1173-1520`. Three PFT parameters (via `prt_params`) govern drought phenology for each PFT:

| Parameter (CDL) | Internal | Units | Role |
|---|---|---|---|
| `fates_phen_drought_threshold` | `phen_drought_threshold(ipft)` | m3/m3 or mm | Abscission threshold. **Sign-dependent**: if positive, volumetric water content; if negative, soil matric potential (mm) |
| `fates_phen_moist_threshold` | `phen_moist_threshold(ipft)` | m3/m3 or mm | Upper (re-flushing) threshold, only used by semi-deciduous PFTs |
| `fates_phen_doff_time` | `phen_doff_time(ipft)` | days | Minimum leaves-off duration before forced re-flushing |
| `fates_phen_fnrt_drop_fraction` | `phen_fnrt_drop_fraction(ipft)` | fraction | Fine-root drop fraction relative to leaves (used in `phenology_leafonoff`) |
| `fates_phen_stem_drop_fraction` | `phen_stem_drop_fraction(ipft)` | fraction | Stem drop fraction relative to leaves (non-woody PFTs) |

**Important: `fates_nonhydro_smpso` and `fates_nonhydro_smpsc` are NOT drought-phenology parameters.** These are the stomatal-conductance (btran) thresholds and do not appear in `phenology()` (verified by grep against `EDPhysiologyMod.F90`).

### Soil Moisture Memory

Each PFT maintains a 10-day rolling average of soil liquid volume (`liqvol_memory`) and matric potential (`smp_memory`), weighted by the root fraction in each layer excluding the thin topmost layer (`EDPhysiologyMod.F90:1181-1232`). Both moisture quantities are stored so the threshold can be interpreted in either volumetric or matric-potential mode.

The threshold check at `EDPhysiologyMod.F90:1235-1241` chooses between the two memories based on the sign of `phen_drought_threshold`:

```fortran
if ( phen_drought_threshold >= 0. ) then
   smoist_below_threshold = mean_10day_liqvol < phen_drought_threshold
else
   smoist_below_threshold = mean_10day_smp    < phen_drought_threshold
end if
```

### Hard Drought-Deciduous State Machine

`EDPhysiologyMod.F90:1285-1392`. For `stress_decid == ihard_stress_decid`, the state machine uses an `if/elseif` cascade that allows at most one transition per day:

1. **Leaf-on, drought-wetness**: if soil was above threshold for a prolonged off-period -- flush
2. **Leaf-on, timeout**: if leaves have been off for more than a year -- force flush
3. **Leaf-on, exceed-min-off**: if leaves have been off long enough in a wet environment -- flush
4. **Leaf-off, prolonged on**: leaves have exceeded `ndays_pft_leaf_lifespan` -- force drop
5. **Leaf-off, moisture**: leaves on for at least `dleafon_drycheck = 100` days (`EDPhysiologyMod.F90:171`) AND soil now below threshold -- drop

`ndays_pft_leaf_lifespan` is `nint(ndays_per_year * min(decid_leaf_long_max, sum(leaf_long(ipft,:))))` with `decid_leaf_long_max = 1.0` year (`EDPhysiologyMod.F90:173,1266-1268`).

The minimum off-period for forced re-flush is `min_daysoff_dforcedflush = 30` (`EDPhysiologyMod.F90:176`). A 30-day tolerance `dd_offon_toler` (`:184`) is used for the "last flush was about one year ago" window.

### Semi Drought-Deciduous Gradual Elongation

`EDPhysiologyMod.F90:1393-1492`. For `stress_decid == isemi_stress_decid`, the elongation factor is a linear interpolation between `phen_drought_threshold` and `phen_moist_threshold`, clamped to `[elongf_min, 1]`:

```
elongf_1st = elongf_min + (1 - elongf_min) *
             ( moisture - phen_drought_threshold ) /
             ( phen_moist_threshold - phen_drought_threshold )
```

with `elongf_min = 0.05` (`EDPhysiologyMod.F90:188`). Guardrails prevent oscillation: when leaves have only recently come on (`dndaysleafon <= dleafon_drycheck`), `elong_factor` cannot decrease; when leaves have recently dropped, the first-guess moisture-based factor cannot immediately re-flush. Partial shedding sets `dstatus = phen_dstat_pshed` without resetting the clocks.

## phenology_leafonoff: Flush and Shed Mechanics

`phenology_leafonoff()` (`EDPhysiologyMod.F90:1529-1760`) is called from `phenology()` and converts the site/PFT elongation factors into actual carbon transfers at the cohort level.

### Cohort-Level Elongation Factors

Lines 1639-1648:

```fortran
currentCohort%efleaf_coh = currentSite%elong_factor(ipft)
currentCohort%effnrt_coh = 1 - (1 - efleaf_coh) * fnrt_drop_fraction
currentCohort%efstem_coh = 1 - (1 - efleaf_coh) * stem_drop_fraction
```

Fine-root and stem effective elongation factors are blends, with `fnrt_drop_fraction = prt_params%phen_fnrt_drop_fraction(ipft)` and `stem_drop_fraction = prt_params%phen_stem_drop_fraction(ipft)`. If the drop fraction is 0, that tissue is not impacted by phenology at all. If it is 1, the tissue tracks leaf elongation exactly.

### Flush/Shed Decision

Lines 1608-1632. For cold-deciduous PFTs, flushing happens when the site has just moved from `iscold/nevercold` to `notcold` and the cohort still has `status_coh == leaves_off`. Shedding happens when `cstatus` is back to cold and `status_coh == leaves_on` and the plant is either woody or large enough (`dbh > phen_cold_size_threshold(ipft)`).

For drought hard-deciduous and semi-deciduous PFTs, flushing is triggered when `dstatus(ipft)` is `moiston` or `timeon`, and shedding when it is `moistoff`, `timeoff`, or `pshed`.

### Storage-to-Tissue Transfer on Flush

Lines 1671-1710. Target biomass for each tissue is computed via `bleaf`, `bfineroot`, `bsap_allom`, `bagw_allom`, `bbgw_allom`, `bdead_allom` scaled by the effective elongation factors. Tissue deficits relative to targets are summed into `total_deficit_c`. The fraction of storage that will actually be drawn down is (`EDPhysiologyMod.F90:1684-1686`):

```fortran
store_c_transfer_frac = min( phenflush_fraction * total_deficit_c / store_c,
                             1.0 - carbon_store_buffer )
```

Two important semantic points that the previous wiki got wrong:

1. **`phenflush_fraction` is a scalar on the deficit/store ratio, not directly the fraction of storage used.** When `total_deficit_c << store_c` (small deficit, abundant storage), only a tiny fraction `phenflush_fraction * deficit/store` is drawn down. When deficit is comparable to storage, the product approaches 1.
2. **The hard cap comes from `carbon_store_buffer = 0.10`**, a file-local parameter at `EDPhysiologyMod.F90:1579`. This caps storage drawdown at `1 - 0.10 = 0.9`, regardless of `phenflush_fraction`. The previous wiki described `phenflush_fraction = 0.5` as "the maximum fraction"; in practice `store_c_transfer_frac` is never allowed to exceed 0.9.

The transfer is then applied per organ, proportional to each organ's share of the total deficit, via `PRTPhenologyFlush(currentCohort%prt, ipft, <organ>, store_c_transfer_frac * deficit/total_deficit_c)`. For non-woody PFTs, sapwood and structural wood are also flushed from storage; for woody PFTs only leaf and fineroot are.

### Shedding

Lines 1715-1749. The effective drop fraction for each tissue is `1 - target_tissue_c / tissue_c`, clamped to `[0, 1]`. `PRTDeciduousTurnover` is called for leaves and fine roots; for non-woody PFTs, sapwood and structural wood are also dropped. Carbon is not retranslocated; nutrient retranslocation (N and P) is controlled by `prt_params%turnover_nitr_retrans(ipft, i_organ)` and `prt_params%turnover_phos_retrans(ipft, i_organ)` (note: PFT index is first, organ second).

## Elongation Factor and Allometric Targets

`elong_factor` enters every allometric target through the `efleaf`, `effnrt`, `efstem` arguments to `bleaf`, `bfineroot`, `bagw_allom`, `bbgw_allom`, `bsap_allom`. Cold-deciduous PFTs use 0 or 1 only, so target biomass steps between zero and the full allometric value on flush/shed days, producing the abrupt LAI jumps documented in the Kougarok phenology calibration notes.

Semi-deciduous PFTs produce intermediate targets by virtue of `elong_factor in (0, 1)`. For cold-deciduous PFTs, adding a gradual-elongation option would require modifying the cold branch of `phenology()` at `EDPhysiologyMod.F90:1510-1515` (which currently hard-codes 0 or 1).

## Satellite Phenology Mode

`satellite_phenology()` (`EDPhysiologyMod.F90:1764-1884`) is an alternative mode selected by the host-land-model flag `use_fates_sp`. It takes prescribed LAI time series from the driver and bypasses the prognostic GDD/NCD/moisture state machine entirely. Used for evaluation runs where phenology uncertainty should be removed.

## Key Phenology Functions

| Function | Location | Purpose |
|---|---|---|
| `phenology()` | `EDPhysiologyMod.F90:909-1525` | Updates site-level cold state + PFT-level `elong_factor` |
| `phenology_leafonoff()` | `EDPhysiologyMod.F90:1529-1760` | Applies flush/shed to cohort carbon pools |
| `satellite_phenology()` | `EDPhysiologyMod.F90:1764-1884` | Prescribed-LAI alternative mode |
| `trim_canopy()` | `EDPhysiologyMod.F90:597-906` | Linear-regression canopy trimming based on bottom-layer carbon balance |
| `bleaf` | `FatesAllometryMod.F90:554-610` | Target leaf biomass given dbh, crown damage, canopy_trim, `elongf_leaf` |
| `blmax_allom` | `FatesAllometryMod.F90:440-470` | Maximum allometric leaf biomass |
| `bfineroot` | `FatesAllometryMod.F90:1057-1117` | Target fine-root biomass (uses `effnrt`) |
| `tree_lai` | `FatesAllometryMod.F90:636-761` | Converts leaf carbon to LAI with nitrogen-scaling SLA |
| `tree_sai` | `FatesAllometryMod.F90:765-827` | Converts target LAI to SAI via `allom_sai_scaler(pft) * elongf_stem * target_lai` |
| `PRTPhenologyFlush` | `parteh/PRTLossFluxesMod.F90` | Transfers storage carbon to an organ during flush |
| `PRTDeciduousTurnover` | `parteh/PRTLossFluxesMod.F90` | Abscises leaf/fineroot/stem material to litter |

## Phenology Parameters (Verified Against fates_params_default.cdl)

### Global (non-PFT) parameters

| Internal | CDL name | Default | Line in CDL |
|---|---|---|---|
| `ED_val_phen_a` | `fates_phen_gddthresh_a` | -68 | 1704 |
| `ED_val_phen_b` | `fates_phen_gddthresh_b` | 638 | 1706 |
| `ED_val_phen_c` | `fates_phen_gddthresh_c` | -0.01 | 1708 |
| `ED_val_phen_chiltemp` | `fates_phen_chilltemp` | 5.0 deg C | 1700 |
| `ED_val_phen_coldtemp` | `fates_phen_coldtemp` | 7.5 deg C | 1702 |
| `ED_val_phen_mindayson` | `fates_phen_mindayson` | 90 days | 1710 |
| `ED_val_phen_ncolddayslim` | `fates_phen_ncolddayslim` | 5 days | 1712 |

### PFT-specific phenology parameters

| CDL name | Internal | Units | Role |
|---|---|---|---|
| `fates_phen_season_decid` | `season_decid(ipft)` | flag | 1 if cold-deciduous |
| `fates_phen_stress_decid` | `stress_decid(ipft)` | flag | 0 evergreen, `ihard_stress_decid`, or `isemi_stress_decid` |
| `fates_phen_flush_fraction` | `phenflush_fraction(ipft)` | fraction | Scalar on `deficit/store` ratio in flush (see above for semantics) |
| `fates_phen_cold_size_threshold` | `phen_cold_size_threshold(ipft)` | cm | Minimum dbh for non-woody PFTs to drop leaves on cold |
| `fates_phen_drought_threshold` | `phen_drought_threshold(ipft)` | m3/m3 or mm (sign-dependent) | Drought abscission threshold |
| `fates_phen_moist_threshold` | `phen_moist_threshold(ipft)` | m3/m3 or mm | Semi-deciduous upper threshold |
| `fates_phen_doff_time` | `phen_doff_time(ipft)` | days | Minimum leaves-off duration for drought PFTs |
| `fates_phen_fnrt_drop_fraction` | `phen_fnrt_drop_fraction(ipft)` | fraction | Fine-root drop relative to leaves |
| `fates_phen_stem_drop_fraction` | `phen_stem_drop_fraction(ipft)` | fraction | Stem drop relative to leaves (non-woody) |

Sources: `EDPftvarcon.F90` throughout; `fates_params_default.cdl:443-469,1354-1376`.

### Hardcoded constants worth knowing

| Constant | Value | Location | Meaning |
|---|---|---|---|
| `num_vegtemp_mem` | 10 days | `EDTypesMod.F90:88` | Window over which cold days are counted against `phen_ncolddayslim` |
| `numWaterMem` | 10 days | `EDTypesMod.F90:79` | Window for soil moisture memory in drought phenology |
| `carbon_store_buffer` | 0.10 | `EDPhysiologyMod.F90:1579` | 1 minus this is the maximum fraction of storage that may be drawn down in flush |
| `dleafon_drycheck` | 100 days | `EDPhysiologyMod.F90:171` | Minimum leaves-on before a dryness re-check can drop leaves |
| `min_daysoff_dforcedflush` | 30 days | `EDPhysiologyMod.F90:176` | Minimum leaves-off before a timing-based re-flush is allowed |
| `dd_offon_toler` | 30 days | `EDPhysiologyMod.F90:184` | Tolerance for "one year since last flush" windows |
| `elongf_min` | 0.05 | `EDPhysiologyMod.F90:188` | Minimum semi-deciduous elongation factor |
| `decid_leaf_long_max` | 1.0 year | `EDPhysiologyMod.F90:173` | Maximum leaf lifespan for drought-deciduous PFTs |
| 400-day cap | 400 days | `EDPhysiologyMod.F90:1156` | Cold-deciduous lifespan cap that promotes plant to `phen_cstat_nevercold` |
