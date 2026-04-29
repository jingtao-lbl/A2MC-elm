# Allometric Relationships

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/FatesAllometryMod.F90` (all core allometry routines)
- `biogeophys/LeafBiophysicsMod.F90` (`DecayCoeffVcmax` -- replaces `decay_coeff_kn`)
- `main/EDPftvarcon.F90` and `parteh/PRTParamsFATESMod.F90` (parameter access)
- `biogeochem/DamageMainMod.F90` (`GetCrownReduction` called from `bleaf`, `bagw_allom`, `carea_allom`)
- `parameter_files/fates_params_default.json` (was `.cdl` at e85d997)

</details>

## Purpose and Scope

This document describes the allometric relationships in FATES at e027a40 that map diameter at breast height (dbh) to height and to organ biomass pools (leaf, fineroot, sapwood, above-/below-ground wood, structural dead wood, storage, crown area, LAI, SAI). All wrapper routines live in `biogeochem/FatesAllometryMod.F90`. Each allometric function takes a PFT-level mode flag (`allom_hmode`, `allom_lmode`, `allom_amode`, `allom_smode`, `allom_fmode`, `allom_cmode`, `allom_stmode`) that dispatches to one of several available functional forms.

## What Changed Since e85d997

- **`bagw_allom` gained two AGB modes.** Modes 4 and 5 are NEW: `dh2bagw_3pwr` (three-parameter power) and `dh2bagw_3pwr_grass` (grass-specific three-parameter power, Gao et al. 2024). Modes 1-3 unchanged.
- **`tree_lai` LAI canopy-decay coefficient refactored.** `decay_coeff_kn(pft, vcmax25top)` no longer exists. Replaced by `DecayCoeffVcmax(vcmax25top, leafn_vert_scaler_coeff1, leafn_vert_scaler_coeff2)` from `biogeophys/LeafBiophysicsMod.F90:2040`. Two new per-PFT parameters drive the decay: `fates_leafn_vert_scaler_coeff1` and `fates_leafn_vert_scaler_coeff2`.
- **`tree_sai` is now a `function`** (was a subroutine) with an expanded signature: `tree_sai(pft, dbh, crowndamage, canopy_trim, elongf_stem, c_area, nplant, cl, canopy_lai, treelai, vcmax25top, call_id)`. The formula is preserved.
- **New public wrapper `tree_lai_sai`** at `FatesAllometryMod.F90:839` that calls `tree_lai` then `tree_sai` and applies VAI capping. Caller code that needs both LAI and SAI together should use this wrapper.
- **`tree_lai` is now a `function`** at line 667 (was a subroutine).
- **Line numbers across all wrappers have shifted.** `bbgw_allom` and `ForceDBH` moved by ~90 and ~550 lines respectively.

## Dispatch Wrappers

Each top-level allometric function reads its mode flag from `prt_params` and calls the appropriate low-level routine. All locations are at e027a40.

| Wrapper | Location | Dispatches on |
|---|---|---|
| `h_allom` | `FatesAllometryMod.F90:336` | `allom_hmode` |
| `h2d_allom` | `FatesAllometryMod.F90:299` | inverse of `h_allom` |
| `bagw_allom` | `FatesAllometryMod.F90:375` | `allom_amode` (5 modes at e027a40) |
| `blmax_allom` | `FatesAllometryMod.F90:449` | `allom_lmode` |
| `carea_allom` | `FatesAllometryMod.F90:495` | `allom_lmode` (shares leaf exponent) |
| `bleaf` | `FatesAllometryMod.F90:580` | wraps `blmax_allom` + trim + damage + `elongf_leaf` |
| `tree_lai` (function) | `FatesAllometryMod.F90:667` | exponential SLA profile via `DecayCoeffVcmax` |
| `tree_sai` (function) | `FatesAllometryMod.F90:800` | multiplier on target LAI; expanded signature |
| `tree_lai_sai` (new) | `FatesAllometryMod.F90:839` | public wrapper that pairs `tree_lai` + `tree_sai` and caps VAI |
| `bsap_allom` | `FatesAllometryMod.F90:990` | `allom_smode` |
| `bbgw_allom` | `FatesAllometryMod.F90:1114` | `allom_cmode` (BGW from AGW) |
| `bfineroot` | `FatesAllometryMod.F90:1146` | `allom_fmode` |
| `bstore_allom` | `FatesAllometryMod.F90:1213` | `allom_stmode` |
| `bdead_allom` | `FatesAllometryMod.F90:1259` | derived from bagw/bbgw/bsap |
| `CheckIntegratedAllometries` | `FatesAllometryMod.F90:166` | consistency check |
| `ForceDBH` | `FatesAllometryMod.F90:2989` | iterative root-finder on target bdead |

## Height Allometry

`h_allom` (`FatesAllometryMod.F90:336`) selects one of five modes based on `prt_params%allom_hmode(ipft)`. All modes cap height at `allom_dbh_maxheight`. Mode dispatch:

```fortran
case (1)   ! "obrien"
case (2)   ! "poorter06"
case (3)   ! "2parameter power function h=a*d^b"
case (4)   ! "chave14"
case (5)   ! Martinez-Cano
```

(`FatesAllometryMod.F90:351-364`)

### Mode 1: O'Brien et al. 1995 (`d2h_obrien`)

`FatesAllometryMod.F90:1986`. **This is a power law, not an asymptotic exponential.**

```
h = 10 ** ( log10(min(d, dbh_maxh)) * p1 + p2 )
  = 10 ** p2  *  d ** p1       (for d < dbh_maxh)
```

with `p1 = allom_d2h1`, `p2 = allom_d2h2`. The BCI default values cited in the source comments are `p1 = 0.64`, `p2 = 0.37`. The derivative is `dhdd = p1 * 10**p2 * d**(p1 - 1)`.

### Mode 2: Poorter et al. 2006 (`d2h_poorter2006`)

`FatesAllometryMod.F90:1877`. Weibull asymptote:

```
h = p1 * ( 1 - exp( p2 * min(d, dbh_maxh)**p3 ) )
```

with `p1 = h_max`, `p2 < 0`, `p3 > 0`. Three parameters.

### Mode 3: 2-parameter power (`d2h_2pwr`)

`FatesAllometryMod.F90:1926`. Used for initialization and temperate species:

```
h = p1 * min(d, dbh_maxh) ** p2
```

### Mode 4: Chave et al. 2014 (`d2h_chave2014`)

`FatesAllometryMod.F90:1813`. Log-quadratic with an environmental stress factor E baked into p1:

```
h = exp( p1 + p2 * log(d) + p3 * log(d)**2 )   (for d < dbh_maxh)
```

### Mode 5: Martinez-Cano et al. 2016 (`d2h_martcano`)

`FatesAllometryMod.F90:2013`. **This is a three-parameter Michaelis-Menten, not a "height-capped variant".**

```
h = ( p1 * d**p2 ) / ( p3 + d**p2 )
```

with `p1 = h_max`, `p2 = shape exponent`, `p3 = half-saturation`. Originally fit at BCI by Martinez-Cano et al. 2016.

All five modes share the maximum-height cap at `dbh_maxh`; that cap is not what distinguishes Martinez-Cano from the others.

## Leaf Biomass Allometry

`blmax_allom` (`FatesAllometryMod.F90:449`) dispatches on `allom_lmode`. **All three modes return kgC (divided by `c2b`).** Actual leaf biomass `bleaf` additionally applies canopy trim, crown damage, and `elongf_leaf`.

### Mode 1: Saldarriaga (`d2blmax_salda`)

`FatesAllometryMod.F90:1522`. Three-parameter plus wood density:

```
blmax = p1 * min(d, dbh_maxh) ** p2 * rho ** p3
```

(Note: `c2b` is accepted as an argument but not used in the Saldarriaga form -- `blmax` is already carbon.)

### Mode 2: 2-parameter power (`d2blmax_2pwr`)

`FatesAllometryMod.F90:1555`. Uncapped power law:

```
blmax = ( p1 * d ** p2 ) / c2b
```

### Mode 3: Height-capped 2-parameter power (`dh2blmax_2pwr`)

`FatesAllometryMod.F90:1583`. **Does NOT include height despite its name** (the `dh` prefix is a historical misnomer -- height is never used). Same form as mode 2 but capped at `dbh_maxh`:

```
blmax = ( p1 * min(d, dbh_maxh) ** p2 ) / c2b
```

The derivative is zero once `d >= dbh_maxh`, so large trees do not add leaf mass.

Note: two additional `blmax`-related routines exist in the source (`dh2blmax_3pwr` at `:1625` and `dh2blmax_3pwr_grass` at `:1736`) that are NOT dispatched by `blmax_allom` itself; they are used internally for special cases.

### Wrapper: `bleaf`

`FatesAllometryMod.F90:580`. `bleaf` calls `blmax_allom` then applies:

1. Canopy trim multiplier `canopy_trim` (0-1, set by `trim_canopy()`)
2. Crown damage via `GetCrownReduction` from `DamageMainMod.F90`
3. Phenological scaling by `elongf_leaf` (0-1)

## Above-Ground Woody Biomass (5 modes at e027a40)

`bagw_allom` (`FatesAllometryMod.F90:375`) dispatches on `allom_amode`. The dispatch block (`:404-418`):

```fortran
select case(allom_amode)
case (1) ! "salda"
   call dh2bagw_salda(...)
case (2) ! "2par_pwr"
   call d2bagw_2pwr(...)
case (3) ! "chave14"
   call dh2bagw_chave2014(...)
case (4) ! 3par_pwr   (NEW at e027a40)
   call dh2bagw_3pwr(...)
case (5) ! 3par_pwr_grass   (NEW at e027a40)
   call dh2bagw_3pwr_grass(...)
end select
```

### Mode 1: Saldarriaga (`dh2bagw_salda`)

`FatesAllometryMod.F90:2307`. Function of dbh, height, wood density, and four parameters. Called after `h_allom(d, ipft, h, dhdd)`.

### Mode 2: 2-parameter power (`d2bagw_2pwr`)

`FatesAllometryMod.F90:2256`. `bagw = (p1 * d**p2) / c2b`.

### Mode 3: Chave 2014 (`dh2bagw_chave2014`)

`FatesAllometryMod.F90:2059`. Standard Chave biomass equation involving wood density, diameter, and height.

### Mode 4: 3-parameter power (`dh2bagw_3pwr`) -- NEW at e027a40

`FatesAllometryMod.F90:2114`. Intermediate between Saldarriaga and Chave, with wood-density exponent independent of plant size:

```
bagw = p1 * (d * d * h)**p2 * wood_density**p3 / c2b
```

with derivative `dbagwdd = p2 * bagw * (2/d + dhdd/h)`. Citations: Chave et al. 2014, Saldarriaga et al. 1988.

### Mode 5: Three-parameter power for grass (`dh2bagw_3pwr_grass`) -- NEW at e027a40

`FatesAllometryMod.F90:2193`. Grass/herbaceous form using basal diameter and height as separate predictors:

```
bagw = p1 * (d**p2) * (h**p3) / c2b
```

with derivative `dbagwdd = p2 * bagw / d + p3 * bagw * dhdd / h`. Citation: Gao, Koven, and Kueppers 2024, "Allometric relationships and trade-offs in 11 common Mediterranean-climate grasses", Ecological Applications.

### Damage and elongation post-processing

All five modes are then scaled by `elongf_stem` (phenology) and optionally by a crown-damage reduction applied to the branch fraction only (`FatesAllometryMod.F90:421-440`).

## Below-Ground Woody Biomass

`bbgw_allom` (`FatesAllometryMod.F90:1114`). For supported modes, `bbgw` is computed as a fixed fraction of total woody biomass determined by `allom_agb_frac`:

```
bbgw = elongf_stem * bagw * (1 - allom_agb_frac) / allom_agb_frac
```

## Sapwood and Structural Biomass

| Function | Location | Role |
|---|---|---|
| `bsap_allom` | `FatesAllometryMod.F90:990` | Sapwood biomass via sapwood area, LA per SA ratio, and `elongf_stem`. Internally calls `DecayCoeffVcmax` at `:950-952`. |
| `bdead_allom` | `FatesAllometryMod.F90:1259` | Structural (dead-wood) biomass as `bagw + bbgw - bsap` |

Sapwood area is derived from target leaf area via `allom_la_per_sa_int + allom_la_per_sa_slp * h`.

## Fine Root Allometry

`bfineroot` (`FatesAllometryMod.F90:1146`). Fine-root target is proportional to leaf target through the leaf-to-fineroot ratio `l2fr`:

```
bfr = l2fr * blmax(d) * canopy_trim * effnrt_coh
```

For carbon-only allocation `l2fr` is a fixed PFT parameter `allom_l2fr`. For CNP allocation, `l2fr` is a dynamically updated cohort state adjusted by the PID controller in PARTEH (`parteh/PRTAllometricCNPMod.F90`). The minimum is `l2fr_min` (0.01) to prevent numerical issues.

### Fine root vertical profile

Fine-root mass is distributed across soil layers via a PFT-level dispatcher (`set_root_fraction` at `FatesAllometryMod.F90:2772`) that selects one of three functional forms based on `prt_params%fnrt_prof_type(ft)`:

| Type | Routine | Parameter usage |
|---|---|---|
| 1 | `exponential_1p_root_profile` (`FatesAllometryMod.F90:2839`) | uses `fates_allom_fnrt_prof_a` only |
| 2 | `jackson_beta_root_profile` | uses `fates_allom_fnrt_prof_a` as the Jackson β |
| 3 | `exponential_2p_root_profile` (`FatesAllometryMod.F90:2860`) | uses **both** `fates_allom_fnrt_prof_a` and `fates_allom_fnrt_prof_b` |

The two-parameter exponential form (type 3) is the most flexible and is the typical choice for arctic PFTs where the steepness of the rooting profile differs from the depth scale. Higher `fates_allom_fnrt_prof_a` shifts mass toward the surface; `fates_allom_fnrt_prof_b` controls the depth-scale relaxation. Profiles are normalized to integrate to 1.

`fates_turnover_fnrt` (PFT-level, units 1/yr) is the inverse of fine-root lifespan, used by the maintenance-turnover machinery to compute fine-root flux to the litter pool. See `plant-physiology/litter.md` for the litter side.

## Crown Area

`carea_allom` (`FatesAllometryMod.F90:495`) uses the leaf-biomass exponent `allom_d2bl2` plus `allom_blca_expnt_diff` to derive a dbh exponent for crown area, optionally capping `d` at `dbh_maxh` (for modes 1 and 3) or not (mode 2). Crown damage is applied via `GetCrownReduction`.

## Storage Carbon Target

`bstore_allom` (`FatesAllometryMod.F90:1213`). Sizes storage carbon target as a PFT-dependent fraction of target leaf biomass. For CNP allocation, storage is additionally sized for N and P stoichiometry (see `parteh/cnp_allocation.md`, topic 06).

## LAI and SAI (refactored at e027a40)

### `tree_lai` (function)

`FatesAllometryMod.F90:667`. Now declared as `real(r8) function` (was a subroutine). Converts leaf carbon per cohort into leaf-area index, accounting for an exponential SLA profile with canopy depth:

```
sla(depth) = slatop * exp( -kn * (canopy_lai_above + x) )
```

capped at `slamax`. **The decay coefficient `kn` is now computed via `DecayCoeffVcmax`, not `decay_coeff_kn`.** At `FatesAllometryMod.F90:720-722`:

```fortran
kn = DecayCoeffVcmax(vcmax25top, &
                     prt_params%leafn_vert_scaler_coeff1(pft), &
                     prt_params%leafn_vert_scaler_coeff2(pft))
```

`DecayCoeffVcmax` is defined at `biogeophys/LeafBiophysicsMod.F90:2040-2073`:

```fortran
function DecayCoeffVcmax(vcmax25top, slope_param, intercept_param) result(decay_coeff_vcmax)
   ...
   decay_coeff_vcmax = exp(slope_param * vcmax25top - intercept_param)
end function
```

Two new per-PFT parameters drive the decay (declared at `parteh/PRTParametersMod.F90:62-63`):

| JSON key | Internal | Default | Role |
|---|---|---|---|
| `fates_leafn_vert_scaler_coeff1` | `leafn_vert_scaler_coeff1(pft)` | 0.00963 (BCI) | Slope, multiplies `vcmax25top` |
| `fates_leafn_vert_scaler_coeff2` | `leafn_vert_scaler_coeff2(pft)` | 2.43 (BCI) | Intercept, subtracted from `slope * vcmax25top` |

JSON entries at `parameter_files/fates_params_default.json:943-957`.

The `tree_lai` function still has two cases depending on whether `leafc_per_unitarea` is small enough to stay within the exponential regime or large enough to spill into a linear regime at `sla_max` (`FatesAllometryMod.F90:744-789`).

The same `DecayCoeffVcmax` call appears in `bsap_allom` at `:950-952`, and twice in `biogeophys/FatesPlantRespPhotosynthMod.F90` at `:551-553, 610-612`.

### `tree_sai` (function, expanded signature)

`FatesAllometryMod.F90:800`. Now declared as `real(r8) function` with the signature:

```fortran
real(r8) function tree_sai(pft, dbh, crowndamage, canopy_trim, elongf_stem, c_area, nplant, &
                           cl, canopy_lai, treelai, vcmax25top, call_id)
```

The internal formula at `:832` is unchanged:

```fortran
target_lai = tree_lai(target_bleaf, pft, c_area, nplant, cl, canopy_lai, vcmax25top)
tree_sai   = elongf_stem * prt_params%allom_sai_scaler(pft) * target_lai
```

**The controlling parameter remains `fates_allom_sai_scaler`, not `fates_phen_stem_drop_fraction`.** The `elongf_stem` factor carries phenology information, computed upstream in `phenology_leafonoff` from `phen_stem_drop_fraction` and `elong_factor`. `target_lai` is computed from `bleaf(d, ..., elongf_leaf=1.0)` (fully flushed) then passed through `tree_lai`, so SAI uses the fully flushed target leaf area regardless of current phenology.

Anyone porting calling code based on the e85d997 signature will fail to compile because of the new arguments (`treelai`, `vcmax25top`, `call_id`).

### `tree_lai_sai` (new public wrapper)

`FatesAllometryMod.F90:839`. The recommended public entry point that pairs LAI and SAI:

```fortran
subroutine tree_lai_sai(leaf_c, pft, c_area, nplant, cl, canopy_lai, vcmax25top, &
                        dbh, crowndamage, canopy_trim, elongf_stem, call_id, &
                        treelai, treesai)
```

It calls `tree_lai`, then `tree_sai`, then applies VAI capping if `do_vai_capping = .true.`:

```fortran
if ((treelai + treesai) > sum(dinc_vai)) then
   treelai = sum(dinc_vai) * (1 - prt_params%allom_sai_scaler(pft)) - nearzero
   treesai = sum(dinc_vai) * prt_params%allom_sai_scaler(pft) - nearzero
end if
```

Use this wrapper rather than calling `tree_lai` and `tree_sai` separately when both quantities are needed for a cohort.

## CheckIntegratedAllometries

`FatesAllometryMod.F90:166`. Verifies that integrated biomass pools match diagnosed allometric targets within tolerance to prevent accumulation of numerical error in the PARTEH ODE integration.

## ForceDBH

`FatesAllometryMod.F90:2989`. Iterative root-finder (bisection) that adjusts `d` to match a target `bdead` pool. Used in cohort fusion, damage recovery, and whenever the state is updated externally and allometric quantities must be re-synced. **Note:** location moved from line 2439 (e85d997) to 2989 (e027a40) -- a ~550-line shift.

## Key Allometry Parameters

| Parameter group | Typical keys (JSON prefix `fates_`) | Used in |
|---|---|---|
| Height | `allom_hmode`, `allom_d2h1`, `allom_d2h2`, `allom_d2h3`, `allom_dbh_maxheight` | `h_allom` |
| Leaf | `allom_lmode`, `allom_d2bl1`, `allom_d2bl2`, `allom_d2bl3`, `slatop`, `slamax` | `blmax_allom`, `tree_lai` |
| Crown area | `allom_d2ca_coefficient_min`, `allom_d2ca_coefficient_max`, `allom_blca_expnt_diff` | `carea_allom` |
| Above-ground wood | `allom_amode` (1-5), `allom_agb1`..`allom_agb4`, `wood_density`, `allom_agb_frac` | `bagw_allom` |
| Sapwood | `allom_smode`, `allom_la_per_sa_int`, `allom_la_per_sa_slp` | `bsap_allom` |
| Fine root | `allom_fmode`, `allom_l2fr` | `bfineroot` |
| Storage | `allom_stmode` | `bstore_allom` |
| SAI | `allom_sai_scaler` | `tree_sai` |
| LAI canopy decay (NEW) | `leafn_vert_scaler_coeff1`, `leafn_vert_scaler_coeff2` | `tree_lai`, `bsap_allom`, `FatesPlantRespPhotosynthMod` |
| Conversions | `c2b`, `wood_density` | all |

## Integration With PARTEH

Allometric targets drive the growth ODE integration in `parteh/PRTAllometricCarbonMod.F90` (carbon-only) or `parteh/PRTAllometricCNPMod.F90` (CNP). Each day the allocator solves for `d` such that integrated pools match allometric targets, within the constraint of available photosynthate and, for CNP, nutrient uptake. See `parteh/index.md` for details (topic 06).
