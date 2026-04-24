# Plant Growth and Physiology

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/EDPhysiologyMod.F90` (phenology, canopy trim, litter input, damage generation)
- `biogeochem/EDMortalityFunctionsMod.F90` (mechanistic mortality)
- `biogeochem/FatesAllometryMod.F90` (size-biomass scaling)
- `biogeochem/FatesLitterMod.F90` (litter types + constants)
- `biogeochem/DamageMainMod.F90` (crown damage)
- `main/EDMainMod.F90` (`ed_ecosystem_dynamics` master loop)
- `parteh/` (PARTEH allocation)

</details>

## Purpose and Scope

This section documents plant-level growth and physiological processes in FATES: phenology, allocation, allometric relationships, mortality, crown damage, and litter production. These processes operate on individual cohorts each day within `ed_ecosystem_dynamics` (`main/EDMainMod.F90`).

For canopy structure and light competition see `../canopy-structure/index.md`. For biophysical processes (photosynthesis, hydraulics) see `../biophysics/index.md`.

## Daily Plant Physiology Workflow

1. **Phenology** -- `phenology()` (`EDPhysiologyMod.F90:909-1525`) updates site cold state and per-PFT elongation factors, then `phenology_leafonoff()` (`:1529-1760`) applies storage-to-tissue flushing or abscission at the cohort level
2. **Canopy trimming** -- `trim_canopy()` (`EDPhysiologyMod.F90:597-906`) optimizes `canopy_trim` based on the carbon balance of the bottom `nll` leaf layers
3. **Allocation** -- PARTEH integrates target allometries with available photosynthate (and, in CNP mode, nutrient uptake)
4. **Mortality** -- `mortality_rates()` + `Mortality_Derivative()` compute seven component rates per cohort
5. **Damage** -- `GenerateDamageAndLitterFluxes` creates damaged sub-cohorts when `IsItDamageTime` returns true
6. **Litter fluxes** -- `CWDInput`, `PreDisturbanceIntegrateLitter`, `CWDOut` move mass from plant pools through litter to soil BGC

## Phenology

See `phenology.md` for full details. Three strategies are supported:

- **Evergreen** (`season_decid=0` and `stress_decid=0`): `elong_factor = 1` always
- **Cold deciduous** (`season_decid=1`): shared site-level GDD/NCD state machine with `elong_factor` in {0, 1}
- **Drought deciduous** (`stress_decid = ihard_stress_decid` or `isemi_stress_decid`): per-PFT state machine; hard variant uses {0, 1}, semi uses gradual values

Default GDD threshold parameters are `phen_a = -68`, `phen_b = 638`, `phen_c = -0.01` (Botta et al. 2000; verified from `parameter_files/fates_params_default.cdl:1704-1708`). The formula is `gdd_threshold = phen_a + phen_b * exp(phen_c * nchilldays)` -- because `phen_c` is negative, more chilling days produces a LOWER threshold and therefore earlier flushing. This is relevant to Arctic sites. Default `phen_mindayson = 90 days`, not 30.

### Phenology State Constants

| Constant | Value | Location | Meaning |
|---|---|---|---|
| `phen_cstat_nevercold` | 0 | `EDTypesMod.F90:93` | Site has not experienced a cold period |
| `phen_cstat_iscold` | 1 | `EDTypesMod.F90:95` | Site currently cold, leaves off |
| `phen_cstat_notcold` | 2 | `EDTypesMod.F90:96` | Site warm, leaves allowed |
| `phen_dstat_timeoff` | 0 | `EDTypesMod.F90:98` | Drought: leaves off by timing |
| `phen_dstat_moistoff` | 1 | `EDTypesMod.F90:99` | Drought: off from moisture |
| `phen_dstat_moiston` | 2 | `EDTypesMod.F90:100` | Drought: on from moisture |
| `phen_dstat_timeon` | 3 | `EDTypesMod.F90:101` | Drought: forced on by timing |
| `phen_dstat_pshed` | 4 | `EDTypesMod.F90:102` | Drought: partial shedding |

`leaves_on`, `leaves_off`, and `leaves_shedding` cohort status codes plus `ihard_stress_decid`, `isemi_stress_decid` are defined in `FatesConstantsMod.F90`.

## PARTEH Allocation

PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses) is FATES' modular allocation framework. Two hypotheses are implemented:

- **Carbon-only** (`prt_carbon_allom_hyp = 1`): strict allometric targets
- **CNP flexible** (`prt_cnp_flex_allom_hyp = 2`): allows deviation from allometric targets based on nutrient availability; uses a PID controller to adjust `l2fr`

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

See `parteh/index.md` for PARTEH details.

## Allometric Relationships

See `allometry.md` for full details. FATES uses dbh as the primary size variable and derives height and all organ biomass pools through allometric functions. Each PFT selects its mode via `allom_hmode`, `allom_lmode`, `allom_amode`, `allom_smode`, `allom_fmode`, `allom_cmode`, `allom_stmode`. The wrapper functions live in:

| Wrapper | Location |
|---|---|
| `h_allom` / `h2d_allom` | `FatesAllometryMod.F90:296-366` |
| `bagw_allom` | `FatesAllometryMod.F90:372-434` |
| `blmax_allom` | `FatesAllometryMod.F90:440-470` |
| `carea_allom` | `FatesAllometryMod.F90:476-550` |
| `bleaf` | `FatesAllometryMod.F90:554-610` |
| `tree_lai` | `FatesAllometryMod.F90:636-761` |
| `tree_sai` | `FatesAllometryMod.F90:765-827` |
| `bsap_allom` | `FatesAllometryMod.F90:922-1017` |
| `bbgw_allom` | `FatesAllometryMod.F90:1025-1051` |
| `bfineroot` | `FatesAllometryMod.F90:1057-1117` |
| `bstore_allom` | `FatesAllometryMod.F90:1124-1162` |
| `bdead_allom` | `FatesAllometryMod.F90:1170-1220` |
| `CheckIntegratedAllometries` | `FatesAllometryMod.F90:163-293` |
| `ForceDBH` | `FatesAllometryMod.F90:2439-2587` |

## Mortality

See `mortality.md` for full details. `mortality_rates()` (`EDMortalityFunctionsMod.F90:51-230`) computes seven component fractional rates: background, carbon starvation, hydraulic failure, freezing stress, size senescence, age senescence, and crown damage. Logging is computed separately in `LoggingMortality_frac()`. `Mortality_Derivative()` (`:234-323`) integrates them and assigns a fraction of canopy woody mortality to disturbance generation.

Notable: the freezing-tolerance parameter is `fates_mort_freezetol` (internal `freezetol`), not `fates_frzleaftol`.

## Crown Damage

See `crown_damage.md`. Activated by `hlm_use_tree_damage`. `GenerateDamageAndLitterFluxes` creates damaged sub-cohorts each damage event; `DamageRecovery` moves them back to lower classes over time. Damage is passed to `bleaf`, `bagw_allom`, `carea_allom` so allometric targets reflect damage.

## Litter Production

See `litter.md`. Litter pools have `ncwd = 4` coarse woody debris classes and `ndcmpy = 3` fine-litter decomposability classes (`ilabile`, `icellulose`, `ilignin`), verified in `FatesLitterMod.F90:48-56`.

Litter sources: maintenance turnover (`PRTMaintTurnover`), deciduous abscission (`PRTDeciduousTurnover`), damage losses (`PRTDamageLosses`), fire losses (`PRTBurnLosses`), and whole-cohort mortality transfer (`SendCohortToLitter`). Nutrients are retranslocated through `turnover_nitr_retrans(ipft, i_organ)` and `turnover_phos_retrans(ipft, i_organ)` (PFT first, organ second). Carbon is never retranslocated.

## Cross-References

- `phenology.md` -- full phenology state machine, parameter defaults, flush/shed semantics
- `allometry.md` -- all mode formulas for height, leaf, woody, sapwood, fineroot, crown area, LAI, SAI
- `mortality.md` -- mortality rate equations and disturbance generation
- `crown_damage.md` -- damage class dynamics and allometry interaction
- `litter.md` -- litter pool structure, turnover fluxes, retranslocation
- `parteh/index.md` -- PARTEH allocation framework
