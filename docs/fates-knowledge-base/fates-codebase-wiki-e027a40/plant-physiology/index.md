# Plant Growth and Physiology

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/EDPhysiologyMod.F90` (phenology, canopy trim, litter input, damage generation)
- `biogeochem/EDMortalityFunctionsMod.F90` (mechanistic mortality, frozen-soil thaw helper)
- `biogeochem/FatesAllometryMod.F90` (size-biomass scaling)
- `biogeochem/FatesLitterMod.F90` (litter types + constants)
- `biogeochem/DamageMainMod.F90` (crown damage)
- `main/EDMainMod.F90` (`ed_ecosystem_dynamics` master loop)
- `main/EDParamsMod.F90` (`soil_tfrz_thresh`, `nclmax`, ED phenology globals)
- `main/FatesConstantsMod.F90` (phenology habit constants `ievergreen`, `ihard_season_decid`, `ihard_stress_decid`, `isemi_stress_decid`; carbon-starvation model constants)
- `parteh/` (PARTEH allocation; see `parteh/index.md` — owned by topic 06)

</details>

## Purpose and Scope

This section documents plant-level growth and physiological processes in FATES at e027a40: phenology, allocation, allometric relationships, mortality, crown damage, and litter production. These processes operate on individual cohorts each day within `ed_ecosystem_dynamics` (`main/EDMainMod.F90`).

For canopy structure and light competition see `../canopy-structure/`. For biophysical processes (photosynthesis, hydraulics) see `../biophysics/`.

## What Changed Since e85d997

Material refactors that this section reflects:

- **Single integer phenology habit.** The two flags `fates_phen_season_decid` and `fates_phen_stress_decid` no longer exist. They were collapsed into one PFT integer `fates_phen_leaf_habit`, with values from `FatesConstantsMod.F90` (`ievergreen=1`, `ihard_season_decid=2`, `ihard_stress_decid=3`, `isemi_stress_decid=4`). All phenology dispatch is now `select case (prt_params%phen_leaf_habit(ipft))`.
- **Renamed phenology parameter.** `fates_phen_doff_time` is now `fates_phen_mindaysoff` (loaded into the same internal name `phen_doff_time`).
- **Leaf turnover split by canopy position.** `fates_turnover_leaf` was replaced by two parameters: `fates_turnover_leaf_canopy` (loaded into `prt_params%leaf_long`) and `fates_turnover_leaf_ustory` (loaded into `prt_params%leaf_long_ustory`).
- **Hydraulic-failure mortality (non-hydro path) is now a linear ramp**, gated by deciduous dormancy and frozen-soil checks (`get_thaw_layer_index`, `soil_tfrz_thresh = -2 deg C`). Hugely material for high-latitude sites.
- **Carbon-starvation mortality is selectable.** Choose between linear and exponential models via `hlm_mort_cstarvation_model` (constants `cstarvation_model_lin=1`, `cstarvation_model_exp=2`). New per-PFT parameter `fates_mort_upthresh_cstarvation` (default 1.0 for all PFTs).
- **Allometry gained two AGB modes.** `bagw_allom` now dispatches modes 1-5: 4 = `dh2bagw_3pwr`, 5 = `dh2bagw_3pwr_grass`.
- **LAI canopy-decay coefficient refactored.** `decay_coeff_kn` no longer exists. `tree_lai` and `bsap_allom` now call `DecayCoeffVcmax(vcmax25top, leafn_vert_scaler_coeff1, leafn_vert_scaler_coeff2)` from `biogeophys/LeafBiophysicsMod.F90`. Two new per-PFT parameters: `fates_leafn_vert_scaler_coeff1`, `fates_leafn_vert_scaler_coeff2`.
- **`tree_sai` signature expanded** with `treelai`, `vcmax25top`, `call_id`. A new public wrapper `tree_lai_sai` enforces capping after both are computed.
- **PFT count is 14, not 12.** New positions PFT#10 = `broadleaf_evergreen_arctic_shrub`, PFT#11 = `broadleaf_colddecid_arctic_shrub`. `arctic_c3_grass` is now PFT#12 (was PFT#10 at e85d997).
- **Parameter file is JSON, not CDL.** Loader uses `JSONRead + FatesTransferParameters`. Default file is `parameter_files/fates_params_default.json`.
- **`nclmax = 3`** at `main/EDParamsMod.F90:75` (was 2 at e85d997).

The 14 default PFT names from `parameter_files/fates_params_default.json:73`:

```
1  broadleaf_evergreen_tropical_tree
2  needleleaf_evergreen_extratrop_tree
3  needleleaf_colddecid_extratrop_tree
4  broadleaf_evergreen_extratrop_tree
5  broadleaf_hydrodecid_tropical_tree
6  broadleaf_colddecid_extratrop_tree
7  broadleaf_evergreen_extratrop_shrub
8  broadleaf_hydrodecid_extratrop_shrub
9  broadleaf_colddecid_extratrop_shrub
10 broadleaf_evergreen_arctic_shrub
11 broadleaf_colddecid_arctic_shrub
12 arctic_c3_grass
13 cool_c3_grass
14 c4_grass
```

For Arctic-site narrative, the new dedicated arctic-shrub PFTs (10, 11) are the natural targets. Default `fates_phen_leaf_habit` for these PFTs is `[1, 2]` (evergreen, hard cold-deciduous) at `parameter_files/fates_params_default.json:1152`.

## Daily Plant Physiology Workflow

1. **Phenology** -- `phenology()` (`EDPhysiologyMod.F90:900`) updates site cold state and per-PFT elongation factors; `phenology_leafonoff()` (`EDPhysiologyMod.F90:1534`) applies storage-to-tissue flushing or abscission at the cohort level
2. **Canopy trimming** -- `trim_canopy()` (`EDPhysiologyMod.F90:598`) optimizes `canopy_trim` based on the carbon balance of the bottom `nll` leaf layers
3. **Allocation** -- PARTEH integrates target allometries with available photosynthate (and, in CNP mode, nutrient uptake). See `parteh/`.
4. **Mortality** -- `mortality_rates()` (`EDMortalityFunctionsMod.F90:59`) and `Mortality_Derivative()` (`:289`) compute seven component rates per cohort
5. **Damage** -- `GenerateDamageAndLitterFluxes()` (`EDPhysiologyMod.F90:258`) creates damaged sub-cohorts when `IsItDamageTime()` returns true
6. **Litter fluxes** -- `CWDInput()` (`EDPhysiologyMod.F90:2802`), `PreDisturbanceIntegrateLitter()` (`:506`), `CWDOut()` (`:3247`) move mass from plant pools through litter to soil BGC

## Phenology

See `phenology.md` for full details. Four habit values are supported, dispatched on `prt_params%phen_leaf_habit(ipft)`:

| Habit value (constant) | Numeric | Semantics |
|---|---|---|
| `ievergreen` | 1 | `elong_factor = 1` always; no leaf turnover-driven phenology |
| `ihard_season_decid` | 2 | Site-level GDD/NCD state machine in `phenology()`; `elong_factor` in {0, 1} |
| `ihard_stress_decid` | 3 | Per-PFT moisture state machine; `elong_factor` in {0, 1} |
| `isemi_stress_decid` | 4 | Per-PFT; `elong_factor` may take any value in `[elongf_min, 1]` |

Constants are defined at `main/FatesConstantsMod.F90:75-105`. The legacy logic that treated cold-deciduous as `season_decid=1` is gone; cold-deciduous is now an explicit code path keyed on `ihard_season_decid`.

Default GDD threshold parameters remain `phen_a = -68`, `phen_b = 638`, `phen_c = -0.01` (Botta et al. 2000), verified from `parameter_files/fates_params_default.json:2014-2034`. The formula is `gdd_threshold = phen_a + phen_b * exp(phen_c * nchilldays)` -- because `phen_c` is negative, more chilling days produces a LOWER threshold and therefore earlier flushing. Default `phen_mindayson = 90 days`.

### Phenology State Constants

| Constant | Value | Location | Meaning |
|---|---|---|---|
| `phen_cstat_nevercold` | 0 | `EDTypesMod.F90:99` | Site has not experienced a cold period |
| `phen_cstat_iscold` | 1 | `EDTypesMod.F90:101` | Site currently cold, leaves off |
| `phen_cstat_notcold` | 2 | `EDTypesMod.F90:102` | Site warm, leaves allowed |
| `phen_dstat_timeoff` | 0 | `EDTypesMod.F90:104` | Drought: leaves off by timing |
| `phen_dstat_moistoff` | 1 | `EDTypesMod.F90:105` | Drought: off from moisture |
| `phen_dstat_moiston` | 2 | `EDTypesMod.F90:106` | Drought: on from moisture |
| `phen_dstat_timeon` | 3 | `EDTypesMod.F90:107` | Drought: forced on by timing |
| `phen_dstat_pshed` | 4 | `EDTypesMod.F90:108` | Drought: partial shedding |

`leaves_on=2`, `leaves_off=1`, `leaves_shedding=3` cohort status codes are at `FatesConstantsMod.F90:66-71`. Habit constants `ievergreen=1`, `ihard_season_decid=2`, `ihard_stress_decid=3`, `isemi_stress_decid=4` are at `FatesConstantsMod.F90:75-105`.

## PARTEH Allocation

PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses) is FATES' modular allocation framework. Two hypotheses are implemented:

- **Carbon-only** (`prt_carbon_allom_hyp = 1`): strict allometric targets
- **CNP flexible** (`prt_cnp_flex_allom_hyp = 2`): allows deviation from allometric targets based on nutrient availability; uses a PID controller to adjust `l2fr`. The PID gate at e027a40 is `(coupled_*_uptake .and. .not. hlm_*_suppl)` (carried from the API-43 audit baseline).

### Organ and Element Identifiers

Organ IDs (global constants in `parteh/PRTGenericMod.F90`):

- `leaf_organ = 1`
- `fnrt_organ = 2`
- `sapw_organ = 3`
- `store_organ = 4`
- `repro_organ = 5`
- `struct_organ = 6`

Element IDs:

- `carbon12_element = 1`
- `nitrogen_element = 4`
- `phosphorus_element = 5`

See `parteh/index.md` for PARTEH details (owned by topic 06).

## Allometric Relationships

See `allometry.md` for full details. FATES uses dbh as the primary size variable and derives height and all organ biomass pools through allometric functions. Each PFT selects its mode via `allom_hmode`, `allom_lmode`, `allom_amode`, `allom_smode`, `allom_fmode`, `allom_cmode`, `allom_stmode`. All wrappers live in `biogeochem/FatesAllometryMod.F90`:

| Wrapper | Location |
|---|---|
| `h_allom` | `FatesAllometryMod.F90:336` |
| `h2d_allom` | `FatesAllometryMod.F90:299` |
| `bagw_allom` | `FatesAllometryMod.F90:375` |
| `blmax_allom` | `FatesAllometryMod.F90:449` |
| `carea_allom` | `FatesAllometryMod.F90:495` |
| `bleaf` | `FatesAllometryMod.F90:580` |
| `tree_lai` | `FatesAllometryMod.F90:667` (now a `function`) |
| `tree_sai` | `FatesAllometryMod.F90:800` (now a `function`, expanded signature) |
| `tree_lai_sai` (new wrapper) | `FatesAllometryMod.F90:839` |
| `bsap_allom` | `FatesAllometryMod.F90:990` |
| `bbgw_allom` | `FatesAllometryMod.F90:1114` |
| `bfineroot` | `FatesAllometryMod.F90:1146` |
| `bstore_allom` | `FatesAllometryMod.F90:1213` |
| `bdead_allom` | `FatesAllometryMod.F90:1259` |
| `CheckIntegratedAllometries` | `FatesAllometryMod.F90:166` |
| `ForceDBH` | `FatesAllometryMod.F90:2989` |

`bagw_allom` now supports five AGB modes (modes 4 and 5 are new since e85d997).

## Mortality

See `mortality.md` for full details. `mortality_rates()` (`EDMortalityFunctionsMod.F90:59`) computes seven component fractional rates: background, carbon starvation (linear OR exponential), hydraulic failure (now linear, frozen-soil/dormancy gated), freezing stress, size senescence, age senescence, and crown damage. Logging is computed separately in `LoggingMortality_frac()`. `Mortality_Derivative()` (`:289`) integrates them and assigns a fraction of canopy woody mortality to disturbance generation.

The freezing-tolerance parameter is `fates_mort_freezetol` (internal `freezetol`), declared at `EDPftvarcon.F90:56` and loaded at `:329-331`. NOT `fates_frzleaftol`.

## Crown Damage

See `crown_damage.md`. Activated by `hlm_use_tree_damage`. `GenerateDamageAndLitterFluxes()` (`EDPhysiologyMod.F90:258`) creates damaged sub-cohorts each damage event; `DamageRecovery()` moves them back to lower classes over time. Damage is passed through `bleaf`, `bagw_allom`, `carea_allom` so allometric targets reflect damage.

## Litter Production

See `litter.md`. Litter pools have `ncwd = 4` coarse woody debris classes and `ndcmpy = 3` fine-litter decomposability classes (`ilabile`, `icellulose`, `ilignin`), verified in `FatesLitterMod.F90:48-56`.

Litter sources: maintenance turnover (`PRTMaintTurnover`), deciduous abscission (`PRTDeciduousTurnover`), damage losses (`PRTDamageLosses`), fire losses (`PRTBurnLosses`), and whole-cohort mortality transfer (`SendCohortToLitter`). Maintenance turnover at e027a40 selects `prt_params%leaf_long(ipft, age_class)` for canopy cohorts vs `prt_params%leaf_long_ustory(ipft, age_class)` for understory cohorts (`parteh/PRTLossFluxesMod.F90:745-756`). Nutrients are retranslocated through `turnover_nitr_retrans(ipft, i_organ)` and `turnover_phos_retrans(ipft, i_organ)` (PFT first, organ second). Carbon is never retranslocated.

## Cross-References

- `phenology.md` -- full phenology state machine (single-integer habit dispatch), parameter defaults, flush/shed semantics
- `allometry.md` -- all mode formulas for height, leaf, woody (5 AGB modes), sapwood, fineroot, crown area, LAI, SAI; `DecayCoeffVcmax` refactor
- `mortality.md` -- mortality rate equations including selectable carbon-starvation model and frozen-soil-aware non-hydro hmort; disturbance generation
- `crown_damage.md` -- damage class dynamics and allometry interaction
- `litter.md` -- litter pool structure, turnover fluxes, canopy/ustory leaf longevity split, retranslocation
- `parteh/index.md` -- PARTEH allocation framework (topic 06)
