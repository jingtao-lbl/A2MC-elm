# Fire Effects on Vegetation

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `fire/SFMainMod.F90`
- `fire/SFParamsMod.F90`
- `main/EDPftvarcon.F90`
- `biogeophys/FatesAllometryMod.F90`

## Purpose and Scope

This document describes how the SPITFIRE fire model translates fire behavior into vegetation mortality for individual plant cohorts. It covers the three sequential processes executed inside `fire_model` after fire spread and intensity have been computed: (1) **crown scorching** — the vertical height reached by convective heat above the flame front, (2) **crown damage** — the fraction of each cohort's crown consumed by flames, and (3) **cambial damage** — heat penetration through bark to kill the cambium layer. The three are then combined into a single post-fire mortality rate (`currentCohort%fire_mort`) that feeds the disturbance framework.

For the upstream processes that precede vegetation effects, see `ignition.md` and `spread.md`. For how fire mortality feeds into patch creation, see `core-dynamics/patch_dynamics.md`.

## Execution Sequence

All four fire-effects subroutines are called once per day from `fire_model`, in strict order `(fire/SFMainMod.F90:109-112)`:

```
crown_scorching       -> Scorch_ht(pft)            (patch level)
crown_damage          -> fraction_crown_burned     (cohort level)
cambial_damage_kill   -> cambial_mort              (cohort level)
post_fire_mortality   -> crownfire_mort, fire_mort (cohort level)
```

A patch only enters the effects pipeline when `currentPatch%fire == 1` (fire intensity exceeded `SF_val_fire_threshold` in `area_burnt_intensity`). Otherwise all cohort fire-effect variables remain at zero. Inside each subroutine, bareground no-competition patches are also skipped (`nocomp_pft_label .ne. nocomp_bareground`), and calculations are performed only for woody cohorts (`prt_params%woody(pft) == itrue`).

Sources: `(fire/SFMainMod.F90:80-115)`

## Crown Scorching

The `crown_scorching` subroutine `(fire/SFMainMod.F90:890-951)` computes a per-PFT scorch height for each patch using Van Wagner (1973) / Byram (1959):

```
Scorch_ht(pft) = fire_alpha_SH(pft) * FI^0.667
```

Where:
- `Scorch_ht(pft)` — scorch height for cohorts of PFT `pft` on the patch (m)
- `fire_alpha_SH(pft)` — PFT-specific scorch-height coefficient, parameter `fates_fire_alpha_SH` in the FATES parameter file, stored in `EDPftvarcon_inst%fire_alpha_SH`
- `FI` — patch-level fire intensity (kW/m) from `area_burnt_intensity`
- The `0.667` exponent (≈ 2/3) is the Byram (1959) flame-height relation

The routine first sums aboveground tree biomass on the patch by iterating the cohort list `(fire/SFMainMod.F90:915-929)` using `leaf_c + allom_agb_frac*(sapw_c + struct_c)` as the per-cohort contribution. If `tree_ag_biomass > 0` and the PFT is woody, `Scorch_ht(pft)` is set by the formula above; otherwise it is zero `(fire/SFMainMod.F90:931-943)`. `Scorch_ht` is indexed by PFT rather than cohort because all cohorts of the same PFT share the same allometric scorch response.

Sources: `(fire/SFMainMod.F90:890-951)`

## Crown Damage

The `crown_damage` subroutine `(fire/SFMainMod.F90:954-1018)` converts `Scorch_ht(pft)` into a per-cohort `fraction_crown_burned` using Thonicke et al. 2010 Eq. 17. Crown depth is obtained from the allometry routine `CrownDepth(height, pft, crown_depth)` `(fire/SFMainMod.F90:981)`, and canopy bottom is `height - crown_depth`.

Three scenarios `(fire/SFMainMod.F90:983-1003)`:

| Scenario | Condition | `fraction_crown_burned` |
|---|---|---|
| No damage | `Scorch_ht < height - crown_depth` | `0.0` |
| Partial damage | `height - crown_depth ≤ Scorch_ht < height` | `(Scorch_ht - (height - crown_depth)) / crown_depth` |
| Total damage | `Scorch_ht ≥ height` | `1.0` |

The result is clipped to `[0, 1]` `(fire/SFMainMod.F90:1003)`. Non-woody cohorts (grasses) are skipped and keep `fraction_crown_burned = 0`; their fire response is handled separately via litter/aboveground biomass consumption rather than crown damage.

Sources: `(fire/SFMainMod.F90:954-1018)`, `(biogeophys/FatesAllometryMod.F90)`

## Cambial Damage

The `cambial_damage_kill` subroutine `(fire/SFMainMod.F90:1021-1071)` implements the Peterson and Ryan (1986) cambial heating model (Thonicke 2010 Eqs. 19–21). For each woody cohort:

**Bark thickness** (Thonicke 2010 Eq. 21) `(fire/SFMainMod.F90:1046)`:

```
bt = bark_scaler(pft) * dbh                 [cm]
```

where `bark_scaler` is PFT-specific (parameter `fates_fire_bark_scaler`, `EDPftvarcon_inst%bark_scaler`) and `dbh` is cohort diameter at breast height.

**Critical time to kill cambium** (Thonicke 2010 Eq. 20) `(fire/SFMainMod.F90:1048)`:

```
tau_c = 2.9 * bt^2                          [min]
```

**Cambial mortality probability** (Thonicke 2010 Eq. 19) as a piecewise function of the ratio `tau_l / tau_c`, where `tau_l` is the fire residence time (min) computed in `ground_fuel_consumption` `(fire/SFMainMod.F90:1050-1058)`:

```
if  tau_l/tau_c >= 2.0                   ->  cambial_mort = 1.0
else if  tau_l/tau_c >  0.22             ->  cambial_mort = 0.563 * (tau_l/tau_c) - 0.125
else                                     ->  cambial_mort = 0.0
```

At the `0.22` cutoff the linear branch evaluates to zero (`0.563 * 0.22 - 0.125 ≈ -0.001`), and at `tau_l/tau_c = 2.0` it reaches exactly `1.001`, giving a continuous 0-to-1 ramp that saturates at 1. The calculation is applied only to woody cohorts; grasses retain `cambial_mort = 0`.

Sources: `(fire/SFMainMod.F90:1021-1071)`

## Post-Fire Mortality

The `post_fire_mortality` subroutine `(fire/SFMainMod.F90:1074-1119)` combines crown and cambial damage into a single per-cohort mortality fraction assuming the two mortality mechanisms act as **independent events**. For each woody cohort `(fire/SFMainMod.F90:1097-1104)`:

**Crown-fire mortality** (Thonicke 2010 Eq. 22):

```
crownfire_mort = crown_kill(pft) * fraction_crown_burned^3
```

Note the **cube** on `fraction_crown_burned`. `crown_kill(pft)` is a PFT-specific scaler on fire death from crown scorch, parameter `fates_fire_crown_kill` in the FATES parameter file (`EDPftvarcon_inst%crown_kill`). This parameter replaces what the earlier wiki incorrectly referred to as `crown_damage_mort`.

**Joint-probability combination** (Thonicke 2010 Eq. 18):

```
fire_mort = max(0, min(1,
              crownfire_mort + cambial_mort - crownfire_mort * cambial_mort))
```

This is the standard independent-events union probability `P(A ∪ B) = P(A) + P(B) - P(A) P(B)`, **not** a linear sum. The subtraction term prevents double-counting cohorts killed by both mechanisms. The result is the fraction of individuals in the cohort killed by fire on that day, stored in `currentCohort%fire_mort`.

For non-woody cohorts (grasses) `fire_mort` is set explicitly to zero `(fire/SFMainMod.F90:1106)` — grass mode of death is removal of leaves, which is handled upstream through litter consumption in `ground_fuel_consumption`, not through this mortality channel.

Sources: `(fire/SFMainMod.F90:1074-1119)`

## PFT Parameters Controlling Fire Effects

| Parameter file name | Fortran field | Description | Used in |
|---|---|---|---|
| `fates_fire_alpha_SH` | `EDPftvarcon_inst%fire_alpha_SH` | Scorch-height coefficient `α_SH` (Byram/Van Wagner) | `crown_scorching` |
| `fates_fire_bark_scaler` | `EDPftvarcon_inst%bark_scaler` | DBH-to-bark-thickness scaler (cm/cm) | `cambial_damage_kill` |
| `fates_fire_crown_kill` | `EDPftvarcon_inst%crown_kill` | Scaler on crown-scorch mortality (`crown_kill` in Thonicke Eq. 22) | `post_fire_mortality` |

Registration: `(main/EDPftvarcon.F90:380-386)` (Register), `(main/EDPftvarcon.F90:821-827)` (Retrieve). There is no `crown_damage_mort` parameter in EDPftvarcon or the CDL file at commit `e85d997`.

## Cohort- and Patch-Level State Variables Written by This Pipeline

| Variable | Level | Set in | Description |
|---|---|---|---|
| `Scorch_ht(pft)` | patch | `crown_scorching` | Per-PFT scorch height (m) |
| `fraction_crown_burned` | cohort | `crown_damage` | Fraction of crown consumed (0–1) |
| `cambial_mort` | cohort | `cambial_damage_kill` | Cambial kill probability (0–1) |
| `crownfire_mort` | cohort | `post_fire_mortality` | Crown-scorch kill probability (0–1) |
| `fire_mort` | cohort | `post_fire_mortality` | Total fire mortality fraction per day (0–1) |

`fire_mort` is subsequently consumed by the disturbance-rate calculation in `EDPatchDynamicsMod` to determine the area and composition of fire-generated patches. Only canopy-layer cohorts contribute to disturbance-generating mortality at that downstream step; the effects pipeline itself has no canopy-layer check.

Sources: `(fire/SFMainMod.F90:890-1119)`, `(biogeochem/FatesCohortMod.F90)`, `(biogeochem/FatesPatchMod.F90)`

## Mathematical Summary

```
Scorch_ht(pft)        = fire_alpha_SH(pft) * FI^0.667

fraction_crown_burned = piecewise in (Scorch_ht, height, crown_depth)

bt                    = bark_scaler(pft) * dbh
tau_c                 = 2.9 * bt^2
cambial_mort          = 0                             if tau_l/tau_c <= 0.22
                      = 0.563*(tau_l/tau_c) - 0.125   if 0.22 < tau_l/tau_c < 2
                      = 1                             if tau_l/tau_c >= 2

crownfire_mort        = crown_kill(pft) * fraction_crown_burned^3
fire_mort             = crownfire_mort + cambial_mort
                        - crownfire_mort * cambial_mort
```

Sources: `(fire/SFMainMod.F90:890-1119)`
