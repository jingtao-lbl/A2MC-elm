# Fire Effects on Vegetation

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `fire/SFMainMod.F90` (`CalculatePostFireMortality`)
- `fire/SFEquationsMod.F90` (`ScorchHeight`, `CrownFractionBurnt`, `BarkThickness`, `CriticalResidenceTime`, `CambialMortality`, `cambial_mort`, `CrownFireMortality`, `TotalFireMortality`)
- `main/EDPftvarcon.F90`
- `biogeophys/FatesAllometryMod.F90` (`CrownDepth`)

## Purpose and Scope

This document describes how the SPITFIRE fire model translates fire behavior into vegetation mortality for individual plant cohorts. It covers four sequential calculations performed inside `CalculatePostFireMortality` after fire spread, intensity, and patch-level wildfire-vs-prescribed-fire classification have been completed:

1. **Crown scorching** — vertical height reached by convective heat above the flame front
2. **Crown damage** — fraction of each cohort's crown consumed
3. **Cambial damage** — heat penetration through bark to kill the cambium layer
4. **Total fire mortality** — independent-events combination of crown and cambial kills

The total mortality `currentCohort%fire_mort` feeds the disturbance framework.

For the upstream processes that precede vegetation effects, see `ignition.md` and `spread.md`. For the prescribed-fire path that also triggers this mortality pipeline, see `managed_fire.md`. For how fire mortality feeds into patch creation, see `core-dynamics/patch_dynamics.md`.

## Execution Sequence

All four fire-effects calculations now happen inside a **single subroutine**, `CalculatePostFireMortality` `(fire/SFMainMod.F90:568-639)`. (Older SPITFIRE versions split this across four separate subroutines `crown_scorching`, `crown_damage`, `cambial_damage_kill`, `post_fire_mortality`; the math is unchanged but the routine boundary collapsed.)

Per-patch loop body when `currentPatch%fire == 1` `(fire/SFMainMod.F90:585-636)`:

```
loop over PFTs:
    Scorch_ht(pft) = ScorchHeight(fire_alpha_SH(pft), patch%FI)   if woody else 0
loop over cohorts:
    zero fire_mort, crownfire_mort, cambial_mort, fraction_crown_burned
    if woody:
        CrownDepth(height, pft, crown_depth)
        fraction_crown_burned = CrownFractionBurnt(Scorch_ht(pft), height, crown_depth)
        cambial_mort          = CambialMortality(bark_scaler(pft), dbh, patch%tau_l)
        crownfire_mort        = CrownFireMortality(crown_kill(pft), fraction_crown_burned)
        fire_mort             = TotalFireMortality(crownfire_mort, cambial_mort)
```

### Trigger Condition

A patch enters the effects pipeline when `currentPatch%fire == 1` `(fire/SFMainMod.F90:588)`. Since `patch%fire = nonrx_fire + rx_fire` `(fire/SFMainMod.F90:549)`, **both wildfire AND prescribed fire trigger cohort-level fire mortality**. This is a behavior change from older SPITFIRE versions where the trigger was effectively the wildfire `FI > SF_val_fire_threshold` test only — a low-intensity prescribed fire that is below the wildfire threshold but inside the rx FI window now still drives crown scorch and cambial mortality.

Inside the routine, bareground no-competition patches are skipped (`nocomp_pft_label /= nocomp_bareground`), and per-cohort calculations are performed only for woody cohorts (`prt_params%woody(pft) == itrue`). Non-woody (grass) cohorts are explicitly zeroed each timestep.

Sources: `(fire/SFMainMod.F90:568-639)`

## Crown Scorching

For each woody PFT, scorch height is computed via the pure function `ScorchHeight(alpha_SH, FI)` `(fire/SFEquationsMod.F90:482-501)` (Van Wagner 1973 / Byram 1959; Thonicke 2010 Eq. 16):

```
if FI < nearzero:
    Scorch_ht = 0
else:
    Scorch_ht = alpha_SH * FI^0.667
```

- `Scorch_ht(pft)` — scorch height for cohorts of PFT `pft` on the patch (m)
- `alpha_SH = EDPftvarcon_inst%fire_alpha_SH(pft)`, parameter `fates_fire_alpha_SH` (PFT-specific, declared at `(main/EDPftvarcon.F90:151)`, loaded at `(main/EDPftvarcon.F90:441-443)`)
- `FI` — patch-level fire intensity (kW/m); for prescribed fire this is `patch%FI = patch%rx_FI`
- The `0.667` exponent (≈ 2/3) is the Byram (1959) flame-height relation

`Scorch_ht` is indexed by PFT rather than cohort because all cohorts of the same PFT share the same allometric scorch response. Non-woody PFTs are forced to zero `(fire/SFMainMod.F90:594-597)`.

Sources: `(fire/SFMainMod.F90:591-598)`, `(fire/SFEquationsMod.F90:482-501)`

## Crown Damage

`CrownFractionBurnt(SH, height, crown_depth)` `(fire/SFEquationsMod.F90:505-524)` converts `Scorch_ht(pft)` into a per-cohort `fraction_crown_burned` (Thonicke et al. 2010 Eq. 17). Crown depth is obtained from the allometry routine `CrownDepth(height, pft, crown_depth)` `(biogeophys/FatesAllometryMod.F90)` called at `(fire/SFMainMod.F90:612)`.

Three scenarios:

| Scenario | Condition | `fraction_crown_burned` |
|---|---|---|
| No damage | `SH < height - crown_depth` | `0.0` |
| Partial damage | `height - crown_depth <= SH < height` | `(SH - height + crown_depth) / crown_depth` |
| Total damage | `SH >= height` | `1.0` |

The implementation computes `(SH - height + crown_depth) / crown_depth` and clips to `[0, 1]` `(fire/SFEquationsMod.F90:520-521)`. If `crown_depth < nearzero` the result is forced to 0. Non-woody cohorts are skipped at the calling site `(fire/SFMainMod.F90:609)` and keep `fraction_crown_burned = 0`; their fire response is handled separately via litter / aboveground biomass consumption rather than crown damage.

Sources: `(fire/SFMainMod.F90:611-614)`, `(fire/SFEquationsMod.F90:505-524)`

## Cambial Damage

`CambialMortality(bark_scaler, dbh, tau_l)` `(fire/SFEquationsMod.F90:566-594)` implements the Peterson and Ryan (1986) cambial heating model (Thonicke 2010 Eqs. 19–21). For each woody cohort:

**Bark thickness** (Thonicke 2010 Eq. 21), via `BarkThickness(bark_scalar, dbh)` `(fire/SFEquationsMod.F90:528-546)`:

```
bt = bark_scalar * dbh                              [cm]
```

with `bark_scalar = EDPftvarcon_inst%bark_scaler(pft)`, parameter `fates_fire_bark_scaler` (PFT-specific, declared at `(main/EDPftvarcon.F90:61)`, loaded at `(main/EDPftvarcon.F90:337-339)`). The function aborts via `endrun` if the result is `< nearzero` `(fire/SFEquationsMod.F90:541-544)` — a defensive check against pathological parameter sets.

**Critical time to kill cambium** (Thonicke 2010 Eq. 20), via `CriticalResidenceTime(bark_thickness)` `(fire/SFEquationsMod.F90:550-562)`:

```
tau_c = 2.9 * bt^2                                  [min]
```

**Cambial mortality probability** (Thonicke 2010 Eq. 19) as a piecewise function of `tau_r = tau_l / tau_c`, where `tau_l` is the fire residence time (min) computed in `CalculateResidenceTime` (see `spread.md`). Implemented in helper function `cambial_mort(tau_r)` `(fire/SFEquationsMod.F90:598-617)`:

```
if  tau_r >= 2.0                          ->  cambial_mort = 1.0
else if  0.22 < tau_r < 2.0               ->  cambial_mort = 0.563 * tau_r - 0.125
else                                      ->  cambial_mort = 0.0
```

At the `tau_r = 0.22` cutoff the linear branch evaluates to `≈ 0` (`0.563 * 0.22 - 0.125 ≈ -0.001`); at `tau_r = 2.0` it reaches `1.001`, giving a continuous 0-to-1 ramp that saturates at 1. Both `CambialMortality` and the lower-level `cambial_mort` are public exports `(fire/SFEquationsMod.F90:37, 41)`; `cambial_mort` takes pre-computed `tau_r` directly and is convenient for unit tests or diagnostic scripts.

The calculation is applied only to woody cohorts; grasses retain `cambial_mort = 0` (zeroed at `(fire/SFMainMod.F90:607)`).

Sources: `(fire/SFMainMod.F90:620-621)`, `(fire/SFEquationsMod.F90:528-617)`

## Post-Fire Mortality

`CrownFireMortality(crown_kill, fraction_crown_burned)` and `TotalFireMortality(crownfire_mort, cambial_damage_mort)` combine crown and cambial damage into a single per-cohort mortality fraction.

**Crown-fire mortality** `(fire/SFEquationsMod.F90:621-636)`, Thonicke 2010 Eq. 22:

```
crownfire_mort = crown_kill * fraction_crown_burned^3
                 (clipped to [nearzero, 1])
```

Note the **cube** on `fraction_crown_burned`. `crown_kill = EDPftvarcon_inst%crown_kill(pft)`, parameter `fates_fire_crown_kill` (PFT-specific, declared at `(main/EDPftvarcon.F90:62)`, loaded at `(main/EDPftvarcon.F90:341-343)`). This parameter replaces what some earlier wiki versions called `crown_damage_mort`.

**Joint-probability combination** `(fire/SFEquationsMod.F90:640-660)`, Thonicke 2010 Eq. 18:

```
if crownfire_mort > 1 .or. cambial_damage_mort > 1:
    fire_mort = 1
else:
    fire_mort = crownfire_mort + cambial_damage_mort - crownfire_mort * cambial_damage_mort
fire_mort = clip(fire_mort, nearzero, 1)
```

This is the standard independent-events union probability `P(A ∪ B) = P(A) + P(B) - P(A) P(B)`, **not** a linear sum. The subtraction term prevents double-counting cohorts killed by both mechanisms. The result is the fraction of individuals in the cohort killed by fire on that day, stored in `currentCohort%fire_mort` `(fire/SFMainMod.F90:628-629)`.

For non-woody cohorts (grasses), `fire_mort` is left at 0 `(fire/SFMainMod.F90:605)` — grass mode of death is removal of leaves, handled upstream through litter consumption inside `CalculateFuelBurnt` (`fire/FatesFuelMod.F90:381-438`), not through this mortality channel.

Sources: `(fire/SFMainMod.F90:624-629)`, `(fire/SFEquationsMod.F90:621-660)`

## PFT Parameters Controlling Fire Effects

| Parameter file name | Fortran field | Field decl | Loader | Used in |
|---|---|---|---|---|
| `fates_fire_alpha_SH` | `EDPftvarcon_inst%fire_alpha_SH(:)` | `main/EDPftvarcon.F90:151` | `:441-443` | scorch height |
| `fates_fire_bark_scaler` | `EDPftvarcon_inst%bark_scaler(:)` | `main/EDPftvarcon.F90:61` | `:337-339` | cambial mortality |
| `fates_fire_crown_kill` | `EDPftvarcon_inst%crown_kill(:)` | `main/EDPftvarcon.F90:62` | `:341-343` | crown-fire mortality |

PFT dimension is now 14 (was 12 at e85d997). There is no `crown_damage_mort` parameter in `EDPftvarcon` or the JSON parameter file at e027a40.

## Cohort- and Patch-Level State Variables Written by This Pipeline

| Variable | Level | Set in | Description |
|---|---|---|---|
| `currentPatch%Scorch_ht(pft)` | patch | `CalculatePostFireMortality` | Per-PFT scorch height (m) |
| `currentCohort%fraction_crown_burned` | cohort | `CalculatePostFireMortality` | Fraction of crown consumed (0–1) |
| `currentCohort%cambial_mort` | cohort | `CalculatePostFireMortality` | Cambial kill probability (0–1) |
| `currentCohort%crownfire_mort` | cohort | `CalculatePostFireMortality` | Crown-scorch kill probability (0–1) |
| `currentCohort%fire_mort` | cohort | `CalculatePostFireMortality` | Total fire mortality fraction per day (0–1) |

`fire_mort` is subsequently consumed by the disturbance-rate calculation in `EDPatchDynamicsMod` to determine the area and composition of fire-generated patches. Only canopy-layer cohorts contribute to disturbance-generating mortality at that downstream step; the effects pipeline itself has no canopy-layer check.

Sources: `(fire/SFMainMod.F90:568-639)`, `(biogeochem/FatesCohortMod.F90)`, `(biogeochem/FatesPatchMod.F90)`

## Mathematical Summary

```
Scorch_ht(pft)        = fire_alpha_SH(pft) * FI^0.667                    (woody only)

fraction_crown_burned = 0                                if SH < height - crown_depth
                      = (SH - height + crown_depth)      if height - crown_depth <= SH < height
                        / crown_depth
                      = 1                                if SH >= height

bt                    = bark_scaler(pft) * dbh
tau_c                 = 2.9 * bt^2
cambial_mort          = 0                              if tau_l/tau_c <= 0.22
                      = 0.563*(tau_l/tau_c) - 0.125    if 0.22 < tau_l/tau_c < 2
                      = 1                              if tau_l/tau_c >= 2

crownfire_mort        = crown_kill(pft) * fraction_crown_burned^3
fire_mort             = crownfire_mort + cambial_mort
                        - crownfire_mort * cambial_mort
```

All formulas operate on patches with `currentPatch%fire == 1`, which now includes both wildfire and prescribed fire.

Sources: `(fire/SFMainMod.F90:568-639)`, `(fire/SFEquationsMod.F90:482-660)`
