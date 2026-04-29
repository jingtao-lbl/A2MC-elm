# Phenology and Leaf Dynamics

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/EDPhysiologyMod.F90` (main phenology, `phenology()`, `phenology_leafonoff()`, `satellite_phenology()`)
- `biogeochem/FatesAllometryMod.F90` (target biomass, `tree_lai`, `tree_sai`, `tree_lai_sai`)
- `main/EDParamsMod.F90` (global phenology parameters, `soil_tfrz_thresh`)
- `main/EDPftvarcon.F90` (PFT phenology parameters, `phen_cold_size_threshold`, `phenflush_fraction`)
- `main/EDTypesMod.F90` (status constants, memory windows)
- `main/FatesConstantsMod.F90` (`leaves_on/off/shedding`, habit constants `ievergreen`, `ihard_season_decid`, `ihard_stress_decid`, `isemi_stress_decid`)
- `parteh/PRTParametersMod.F90` (`phen_leaf_habit(:)`, drought params, `leaf_long(:,:)`, `leaf_long_ustory(:,:)`)
- `parteh/PRTParamsFATESMod.F90` (loaders for `fates_phen_mindaysoff`, `fates_turnover_leaf_canopy`, `fates_turnover_leaf_ustory`)
- `parameter_files/fates_params_default.json` (ground-truth defaults; was `.cdl` at e85d997)

</details>

## Purpose and Scope

This document describes the phenology system in FATES at e027a40 that determines the seasonal timing of leaf flushing and abscission for different plant functional types (PFTs). The system operates in two stages each day. First, `phenology()` (`EDPhysiologyMod.F90:900`) updates site-level cold-deciduous state and the PFT-level `elong_factor`. Second, `phenology_leafonoff()` (`EDPhysiologyMod.F90:1534`) translates those states into actual leaf/fine-root/stem transfers from storage carbon at the cohort level.

For photosynthesis, see `../biophysics/photosynthesis.md`. For allocation, see `parteh/` (topic 06).

## Phenological Strategies (single-integer habit, e027a40)

**Important refactor since e85d997.** The two flag parameters `fates_phen_season_decid` and `fates_phen_stress_decid` no longer exist. They have been collapsed into a single PFT integer parameter `fates_phen_leaf_habit` with values defined in `main/FatesConstantsMod.F90:75-105`:

| Habit value | Constant (`FatesConstantsMod.F90`) | Numeric | Semantics |
|---|---|---|---|
| Evergreen | `ievergreen` (`:75`) | 1 | `elong_factor = 1` at all times. No phenology-driven leaf transitions. |
| Cold (hard season) deciduous | `ihard_season_decid` (`:83`) | 2 | Site-level GDD/NCD state machine in `phenology()`; `elong_factor` is 0 or 1 |
| Drought hard-deciduous | `ihard_stress_decid` (`:90`) | 3 | Per-PFT moisture state machine; `elong_factor` is 0 or 1 |
| Drought semi-deciduous | `isemi_stress_decid` (`:97`) | 4 | Per-PFT; `elong_factor` may take intermediate values in `[elongf_min, 1]` |

`prt_params%phen_leaf_habit(:)` is declared as `integer, allocatable` in `parteh/PRTParametersMod.F90:14-22` and loaded from `fates_phen_leaf_habit` in `parteh/PRTParamsFATESMod.F90`. All phenology dispatch in the code now uses `select case (prt_params%phen_leaf_habit(ipft))`.

Default `fates_phen_leaf_habit` per PFT (from `parameter_files/fates_params_default.json:1146-1152`): `[1, 1, 2, 1, 3, 2, 1, 3, 2, 1, 2, 2, 3, 3]` for the 14 PFTs. Note PFT#11 = `broadleaf_colddecid_arctic_shrub` defaults to value 2 (cold deciduous). PFT#10 = `broadleaf_evergreen_arctic_shrub` defaults to 1 (evergreen).

**Two dispatch sites** that any reader of e85d997-era documentation should re-anchor to e027a40:

1. The "drought" outer dispatch in `phenology()` selects on `phen_leaf_habit(ipft)` against `ihard_stress_decid` and `isemi_stress_decid` (`EDPhysiologyMod.F90:1291`).
2. The "cold" inner dispatch in the `case default` arm selects again on `phen_leaf_habit(ipft)` against `ievergreen` and `ihard_season_decid` (`EDPhysiologyMod.F90:1510-1521`). Cold-deciduous flag `ihard_season_decid=2` is the explicit code path; there is no longer an implicit "season_decid=1" interpretation.

The same single-integer dispatch is used in `phenology_leafonoff()` at `EDPhysiologyMod.F90:1611-1632` to choose flush/shed conditions per PFT habit.

Sources: `EDPhysiologyMod.F90:900-1525, 1534-1760`; `FatesConstantsMod.F90:75-105`; `parteh/PRTParametersMod.F90:14-22`.

## State Constants and Memory Windows

Cold and drought status flags (`cstatus`, `dstatus`) are defined in `EDTypesMod.F90:99-108`:

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

Two fixed memory windows (`EDTypesMod.F90:85, 94`) control how phenology reads the environment:

- `numWaterMem = 10` days (window for the rolling soil-moisture average used by drought phenology)
- `num_vegtemp_mem = 10` days (window over which cold days are counted against `phen_ncolddayslim`)

The `leaves_on=2`, `leaves_off=1`, `leaves_shedding=3` cohort status codes are defined at `FatesConstantsMod.F90:66-71` and set in `phenology_leafonoff()`.

## Cold Deciduous Phenology

### GDD Threshold Equation (Botta et al. 2000)

`phenology()` at `EDPhysiologyMod.F90:1040` computes the growing-degree-day threshold each day as:

```
gdd_threshold = ED_val_phen_a + ED_val_phen_b * exp(ED_val_phen_c * nchilldays)
```

where `nchilldays` is the number of chilling days accumulated since the start of the counting window (day 270 NH, day 120 SH; `EDPhysiologyMod.F90:1019-1025`). Each day with mean vegetation temperature below `phen_chilltemp` (default 5 deg C) increments `nchilldays` (`EDPhysiologyMod.F90:1034-1036`). Botta et al. 2000 (Global Change Biology, 6:709-725) is cited in the comments at `EDPhysiologyMod.F90:992`.

### Default parameter values (verified against fates_params_default.json)

The following defaults come directly from `parameter_files/fates_params_default.json:2000-2046`:

| JSON key | Internal name | Default | Units | Description |
|---|---|---|---|---|
| `fates_phen_gddthresh_a` | `ED_val_phen_a` | **-68** | unitless | GDD threshold intercept |
| `fates_phen_gddthresh_b` | `ED_val_phen_b` | **638** | unitless | GDD threshold multiplier |
| `fates_phen_gddthresh_c` | `ED_val_phen_c` | **-0.01** | unitless | GDD threshold exponent (NEGATIVE) |
| `fates_phen_chilltemp` | `ED_val_phen_chiltemp` | 5.0 | deg C | Threshold below which a day counts as a chilling day |
| `fates_phen_coldtemp` | `ED_val_phen_coldtemp` | 7.5 | deg C | Threshold below which a day counts as a cold day for leaf-drop |
| `fates_phen_mindayson` | `ED_val_phen_mindayson` | **90** | days | Minimum duration leaves must remain on before drop is permitted |
| `fates_phen_ncolddayslim` | `ED_val_phen_ncolddayslim` | 5 | days | Cold-day count within the 10-day `num_vegtemp_mem` window that triggers leaf drop |

Source: `parameter_files/fates_params_default.json:2000-2046`. Default values are unchanged from e85d997; only the file format (JSON, not CDL) and line numbers are different.

### Mechanism: more chilling means LESS accumulated warmth is required

Because `phen_c = -0.01 < 0`, the exponential `exp(phen_c * nchilldays)` decays as `nchilldays` increases. With default values:

| `nchilldays` | `gdd_threshold = -68 + 638 * exp(-0.01 * nchilldays)` |
|---|---|
| 0 | 570.0 |
| 50 | 318.9 |
| 100 | 166.7 |
| 150 | 74.4 |
| 200 | 18.5 |
| 300 | -36.2 (effectively zero, flushing immediately once any GDD accumulates) |

The mechanistic interpretation: more chilling days means the plant requires less accumulated warmth before flushing. Arctic sites with 150+ chilling days will produce very small GDD thresholds under defaults. This logic carries forward unchanged from e85d997.

### Cold Leaf-On Trigger

Cold leaf flushing occurs at `EDPhysiologyMod.F90:1112-1121` when all of the following hold:

1. `cstatus` is either `phen_cstat_iscold` or `phen_cstat_nevercold`
2. `grow_deg_days > gdd_threshold`
3. `cndaysleafoff > ED_val_phen_mindayson` (at least 90 days since last leaf drop under defaults)
4. `nchilldays >= 1` (prevents warm-climate plants from ever flushing a cold-deciduous PFT)

On success, `cstatus` is set to `phen_cstat_notcold`, the leaf-on date is recorded, and `grow_deg_days` is zeroed until the next counting season.

### Cold Leaf-Off Trigger

Cold leaf shedding (`EDPhysiologyMod.F90:1138-1153`) requires:

1. `cstatus == phen_cstat_notcold`
2. `model_day_int > num_vegtemp_mem` (at least 10 days into the simulation)
3. `ncolddays > ED_val_phen_ncolddayslim` where `ncolddays` counts days below `ED_val_phen_coldtemp` within the 10-day `vegtemp_memory` buffer
4. `cndaysleafon > ED_val_phen_mindayson`

On trigger, `cstatus` is set to `phen_cstat_iscold` and `grow_deg_days` is reset.

### 400-day Cold-Lifespan Cap

A second leaf-off path at `EDPhysiologyMod.F90:1162-1171` forces `cstatus = phen_cstat_nevercold` when a cold-deciduous PFT has been flushed for more than 400 days. In warm climates where `nchilldays` never increments this effectively prevents re-emergence.

## Drought Deciduous Phenology

`phenology()` iterates over PFTs at `EDPhysiologyMod.F90:1180-1525`. Three PFT parameters (via `prt_params`) govern drought phenology for each PFT:

| Parameter (JSON key) | Internal | Units | Role |
|---|---|---|---|
| `fates_phen_drought_threshold` | `phen_drought_threshold(ipft)` | m3/m3 or mm | Abscission threshold. Sign-dependent: if positive, volumetric water content; if negative, soil matric potential (mm) |
| `fates_phen_moist_threshold` | `phen_moist_threshold(ipft)` | m3/m3 or mm | Upper (re-flushing) threshold, only used by semi-deciduous PFTs |
| `fates_phen_mindaysoff` (was `fates_phen_doff_time`) | `phen_doff_time(ipft)` | days | Minimum leaves-off duration before forced re-flushing. Default 100 days for all 14 PFTs (`fates_params_default.json:1153-1158`). Loaded into the same internal name `phen_doff_time` at `parteh/PRTParamsFATESMod.F90:91-93`. |
| `fates_phen_fnrt_drop_fraction` | `phen_fnrt_drop_fraction(ipft)` | fraction | Fine-root drop fraction relative to leaves (used in `phenology_leafonoff`) |
| `fates_phen_stem_drop_fraction` | `phen_stem_drop_fraction(ipft)` | fraction | Stem drop fraction relative to leaves (non-woody PFTs) |

**Important: `fates_nonhydro_smpso` and `fates_nonhydro_smpsc` are NOT drought-phenology parameters.** These are stomatal-conductance (btran) thresholds and do not appear in `phenology()` (verified by grep against `EDPhysiologyMod.F90`; they are present in JSON at `:1109-1124` only as stomatal thresholds).

### Soil Moisture Memory

Each PFT maintains a 10-day rolling average of soil liquid volume (`liqvol_memory`) and matric potential (`smp_memory`), weighted by the root fraction in each layer excluding the thin topmost layer (`EDPhysiologyMod.F90:1188-1238`). Both moisture quantities are stored so the threshold can be interpreted in either volumetric or matric-potential mode.

The threshold check chooses between the two memories based on the sign of `phen_drought_threshold`:

```fortran
if ( phen_drought_threshold >= 0. ) then
   smoist_below_threshold = mean_10day_liqvol < phen_drought_threshold
else
   smoist_below_threshold = mean_10day_smp    < phen_drought_threshold
end if
```

### Hard Drought-Deciduous State Machine

`EDPhysiologyMod.F90:1292-1392`. For `phen_leaf_habit(ipft) == ihard_stress_decid`, the state machine uses an `if/elseif` cascade that allows at most one transition per day:

1. **Leaf-on, drought-wetness**: if soil was above threshold for a prolonged off-period -- flush
2. **Leaf-on, timeout**: if leaves have been off for more than a year -- force flush
3. **Leaf-on, exceed-min-off**: if leaves have been off long enough in a wet environment -- flush
4. **Leaf-off, prolonged on**: leaves have exceeded `ndays_pft_leaf_lifespan` -- force drop
5. **Leaf-off, moisture**: leaves on for at least `dleafon_drycheck = 100` days (`EDPhysiologyMod.F90:175`) AND soil now below threshold -- drop

`ndays_pft_leaf_lifespan` is `nint(ndays_per_year * min(decid_leaf_long_max, sum(prt_params%leaf_long(ipft,:))))` with `decid_leaf_long_max = 1.0` year (`EDPhysiologyMod.F90:177, 1272`). Note this uses the canopy `leaf_long` array; understory cohorts (which use `leaf_long_ustory`) inherit the same lifespan via this site-level computation.

The minimum off-period for forced re-flush is `min_daysoff_dforcedflush = 30` (`EDPhysiologyMod.F90:180`). A 30-day tolerance `dd_offon_toler` (`:188`) is used for the "last flush was about one year ago" window.

### Semi Drought-Deciduous Gradual Elongation

`EDPhysiologyMod.F90:1399-1500`. For `phen_leaf_habit(ipft) == isemi_stress_decid`, the elongation factor is a linear interpolation between `phen_drought_threshold` and `phen_moist_threshold`, clamped to `[elongf_min, 1]`:

```
elongf_1st = elongf_min + (1 - elongf_min) *
             ( moisture - phen_drought_threshold ) /
             ( phen_moist_threshold - phen_drought_threshold )
```

with `elongf_min = 0.05` (`EDPhysiologyMod.F90:192`). Guardrails prevent oscillation: when leaves have only recently come on (`dndaysleafon <= dleafon_drycheck`), `elong_factor` cannot decrease; when leaves have recently dropped, the first-guess moisture-based factor cannot immediately re-flush. Partial shedding sets `dstatus = phen_dstat_pshed` without resetting the clocks.

### Default cold-deciduous case (case default arm)

`EDPhysiologyMod.F90:1500-1525` is the `case default` arm of the outer `select case (phen_leaf_habit(ipft))`, which handles non-drought-deciduous habits. Inside this arm, an inner `select case (phen_leaf_habit(ipft))` dispatches to:

- `case (ievergreen)` -- `elong_factor = 1.0` always
- `case (ihard_season_decid)` -- `elong_factor = 0` when `cstatus` is `phen_cstat_nevercold` or `phen_cstat_iscold`, else 1

This is the explicit cold-deciduous code path that replaces the legacy `season_decid=1` interpretation.

## phenology_leafonoff: Flush and Shed Mechanics

`phenology_leafonoff()` (`EDPhysiologyMod.F90:1534-1760`) is called from `phenology()` and converts the site/PFT elongation factors into actual carbon transfers at the cohort level.

The is-flushing-time / is-shedding-time block at `EDPhysiologyMod.F90:1611-1632` dispatches on `phen_leaf_habit(ipft)`:

- `case (ihard_season_decid)`: cold flush when `cstatus == phen_cstat_notcold` and cohort `status_coh == leaves_off`; cold shed when `cstatus` is back to cold and cohort has leaves and is woody or larger than `phen_cold_size_threshold(ipft)`.
- `case (ihard_stress_decid, isemi_stress_decid)`: drought flush when `dstatus(ipft)` is `moiston` or `timeon`; drought shed when `dstatus(ipft)` is `moistoff`, `timeoff`, or `pshed`.
- `case (ievergreen)`: never flushes or sheds.

### Cohort-Level Elongation Factors

`EDPhysiologyMod.F90:1645-1651`:

```fortran
currentCohort%efleaf_coh = currentSite%elong_factor(ipft)
currentCohort%effnrt_coh = 1.0_r8 - (1.0_r8 - currentCohort%efleaf_coh) * fnrt_drop_fraction
currentCohort%efstem_coh = 1.0_r8 - (1.0_r8 - currentCohort%efleaf_coh) * stem_drop_fraction
```

Fine-root and stem effective elongation factors are blends, with `fnrt_drop_fraction = prt_params%phen_fnrt_drop_fraction(ipft)` and `stem_drop_fraction = prt_params%phen_stem_drop_fraction(ipft)`. If the drop fraction is 0, that tissue is not impacted by phenology at all. If it is 1, the tissue tracks leaf elongation exactly.

### Storage-to-Tissue Transfer on Flush

`EDPhysiologyMod.F90:1683-1688`. Target biomass for each tissue is computed via `bleaf`, `bfineroot`, `bsap_allom`, `bagw_allom`, `bbgw_allom`, `bdead_allom` scaled by the effective elongation factors. Tissue deficits relative to targets are summed into `total_deficit_c`. The fraction of storage that will actually be drawn down is:

```fortran
store_c_transfer_frac = min( EDPftvarcon_inst%phenflush_fraction(ipft) * &
                             total_deficit_c / store_c, &
                             1.0_r8 - carbon_store_buffer )
```

Two semantic points:

1. **`phenflush_fraction` is a scalar on the deficit/store ratio, not directly the fraction of storage used.** When `total_deficit_c << store_c` (small deficit, abundant storage), only a tiny fraction `phenflush_fraction * deficit/store` is drawn down. When deficit is comparable to storage, the product approaches 1.
2. **The hard cap comes from `carbon_store_buffer = 0.10`**, a file-local parameter at `EDPhysiologyMod.F90:1583`. This caps storage drawdown at `1 - 0.10 = 0.9`, regardless of `phenflush_fraction`.

The transfer is then applied per organ, proportional to each organ's share of the total deficit, via `PRTPhenologyFlush(currentCohort%prt, ipft, <organ>, store_c_transfer_frac * <deficit>/total_deficit_c)`. For non-woody PFTs, sapwood and structural wood are also flushed from storage; for woody PFTs only leaf and fineroot are.

### Shedding

The effective drop fraction for each tissue is `1 - target_tissue_c / tissue_c`, clamped to `[0, 1]`. `PRTDeciduousTurnover` is called for leaves and fine roots; for non-woody PFTs, sapwood and structural wood are also dropped. Carbon is not retranslocated; nutrient retranslocation (N and P) is controlled by `prt_params%turnover_nitr_retrans(ipft, i_organ)` and `prt_params%turnover_phos_retrans(ipft, i_organ)` (PFT index is first, organ second).

## Elongation Factor and Allometric Targets

`elong_factor` enters every allometric target through the `efleaf`, `effnrt`, `efstem` arguments to `bleaf`, `bfineroot`, `bagw_allom`, `bbgw_allom`, `bsap_allom`. Cold-deciduous PFTs use 0 or 1 only, so target biomass steps between zero and the full allometric value on flush/shed days, producing the abrupt LAI jumps documented in calibration notes for Arctic sites.

Semi-deciduous PFTs (`isemi_stress_decid`) produce intermediate targets by virtue of `elong_factor in (0, 1)`. For cold-deciduous PFTs, adding a gradual-elongation option would require modifying the cold-state code path in the inner `select case` of the `case default` arm (`EDPhysiologyMod.F90:1510-1521`).

## Satellite Phenology Mode

`satellite_phenology()` (`EDPhysiologyMod.F90:1768-1884`) is an alternative mode selected by the host-land-model flag `use_fates_sp`. It takes prescribed LAI time series from the driver and bypasses the prognostic GDD/NCD/moisture state machine entirely. Used for evaluation runs where phenology uncertainty should be removed.

## Key Phenology Functions

| Function | Location | Purpose |
|---|---|---|
| `phenology()` | `EDPhysiologyMod.F90:900` | Updates site-level cold state + PFT-level `elong_factor` (single-integer habit dispatch) |
| `phenology_leafonoff()` | `EDPhysiologyMod.F90:1534` | Applies flush/shed to cohort carbon pools |
| `satellite_phenology()` | `EDPhysiologyMod.F90:1768` | Prescribed-LAI alternative mode |
| `trim_canopy()` | `EDPhysiologyMod.F90:598` | Linear-regression canopy trimming based on bottom-layer carbon balance |
| `bleaf` | `FatesAllometryMod.F90:580` | Target leaf biomass given dbh, crown damage, canopy_trim, `elongf_leaf` |
| `blmax_allom` | `FatesAllometryMod.F90:449` | Maximum allometric leaf biomass |
| `bfineroot` | `FatesAllometryMod.F90:1146` | Target fine-root biomass (uses `effnrt`) |
| `tree_lai` | `FatesAllometryMod.F90:667` | `function`. Converts leaf carbon to LAI with `DecayCoeffVcmax`-driven SLA profile |
| `tree_sai` | `FatesAllometryMod.F90:800` | `function`. Stem area index with new signature including `treelai`, `vcmax25top`, `call_id` |
| `tree_lai_sai` | `FatesAllometryMod.F90:839` | New public wrapper that calls `tree_lai` then `tree_sai` and applies VAI capping |
| `PRTPhenologyFlush` | `parteh/PRTLossFluxesMod.F90` | Transfers storage carbon to an organ during flush |
| `PRTDeciduousTurnover` | `parteh/PRTLossFluxesMod.F90` | Abscises leaf/fineroot/stem material to litter |

## Phenology Parameters (verified against fates_params_default.json)

### Global (non-PFT) parameters

| Internal | JSON key | Default | JSON line |
|---|---|---|---|
| `ED_val_phen_a` | `fates_phen_gddthresh_a` | -68 | 2018 |
| `ED_val_phen_b` | `fates_phen_gddthresh_b` | 638 | 2025 |
| `ED_val_phen_c` | `fates_phen_gddthresh_c` | -0.01 | 2032 |
| `ED_val_phen_chiltemp` | `fates_phen_chilltemp` | 5.0 deg C | 2004 |
| `ED_val_phen_coldtemp` | `fates_phen_coldtemp` | 7.5 deg C | 2011 |
| `ED_val_phen_mindayson` | `fates_phen_mindayson` | 90 days | 2039 |
| `ED_val_phen_ncolddayslim` | `fates_phen_ncolddayslim` | 5 days | 2046 |

### PFT-specific phenology parameters (e027a40)

| JSON key | Internal | Units | Role | Notes |
|---|---|---|---|---|
| `fates_phen_leaf_habit` | `phen_leaf_habit(ipft)` | integer flag | 1=evergreen, 2=hard cold-deciduous, 3=hard stress-deciduous, 4=semi-deciduous | NEW (replaces `fates_phen_season_decid` + `fates_phen_stress_decid`). Default `[1,1,2,1,3,2,1,3,2,1,2,2,3,3]` |
| `fates_phen_flush_fraction` | `phenflush_fraction(ipft)` | fraction | Scalar on `deficit/store` ratio in flush | `null` for evergreen PFTs, 0.5 for deciduous |
| `fates_phen_cold_size_threshold` | `phen_cold_size_threshold(ipft)` | cm | Minimum dbh for non-woody PFTs to drop leaves on cold | Default 0.0 for all 14 PFTs |
| `fates_phen_drought_threshold` | `phen_drought_threshold(ipft)` | m3/m3 or mm (sign-dependent) | Drought abscission threshold | Default `-152957.4` mm (matric potential) |
| `fates_phen_moist_threshold` | `phen_moist_threshold(ipft)` | m3/m3 or mm | Semi-deciduous upper threshold | Default `-122365.9` mm |
| `fates_phen_mindaysoff` | `phen_doff_time(ipft)` | days | Minimum leaves-off duration for drought PFTs | RENAMED from `fates_phen_doff_time`. Default 100 days for all 14 PFTs |
| `fates_phen_fnrt_drop_fraction` | `phen_fnrt_drop_fraction(ipft)` | fraction | Fine-root drop relative to leaves | Default 0.0 |
| `fates_phen_stem_drop_fraction` | `phen_stem_drop_fraction(ipft)` | fraction | Stem drop relative to leaves (non-woody) | Default 0.0 |

Sources: `parameter_files/fates_params_default.json:1126-1175`; `EDPftvarcon.F90` and `parteh/PRTParamsFATESMod.F90` for loaders.

### Removed parameters (do NOT use)

These JSON keys EXIST IN OLDER VERSIONS but are GONE at e027a40. Setting them in a parameter file will produce a "parameter not found" error from the JSON loader:

- `fates_phen_season_decid` -- replaced by `fates_phen_leaf_habit`
- `fates_phen_stress_decid` -- replaced by `fates_phen_leaf_habit`
- `fates_phen_doff_time` -- renamed to `fates_phen_mindaysoff`

### Hardcoded constants worth knowing

| Constant | Value | Location | Meaning |
|---|---|---|---|
| `numWaterMem` | 10 days | `EDTypesMod.F90:85` | Window for soil moisture memory in drought phenology |
| `num_vegtemp_mem` | 10 days | `EDTypesMod.F90:94` | Window over which cold days are counted against `phen_ncolddayslim` |
| `carbon_store_buffer` | 0.10 | `EDPhysiologyMod.F90:1583` | 1 minus this is the maximum fraction of storage that may be drawn down in flush |
| `dleafon_drycheck` | 100 days | `EDPhysiologyMod.F90:175` | Minimum leaves-on before a dryness re-check can drop leaves |
| `min_daysoff_dforcedflush` | 30 days | `EDPhysiologyMod.F90:180` | Minimum leaves-off before a timing-based re-flush is allowed |
| `dd_offon_toler` | 30 days | `EDPhysiologyMod.F90:188` | Tolerance for "one year since last flush" windows |
| `elongf_min` | 0.05 | `EDPhysiologyMod.F90:192` | Minimum semi-deciduous elongation factor |
| `decid_leaf_long_max` | 1.0 year | `EDPhysiologyMod.F90:177` | Maximum leaf lifespan for drought-deciduous PFTs |
| 400-day cap | 400 days | `EDPhysiologyMod.F90:1163` | Cold-deciduous lifespan cap that promotes plant to `phen_cstat_nevercold` |
