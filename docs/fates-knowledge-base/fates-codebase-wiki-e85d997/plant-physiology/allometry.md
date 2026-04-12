# Allometric Relationships

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/FatesAllometryMod.F90` (all core allometry routines)
- `main/EDPftvarcon.F90` and `parteh/PRTParamsFATESMod.F90` (parameter access)
- `biogeochem/DamageMainMod.F90` (`GetCrownReduction` called from bleaf/bagw/carea)
- `parameter_files/fates_params_default.cdl`

</details>

## Purpose and Scope

This document describes the allometric relationships in FATES that map diameter at breast height (dbh) to height and to organ biomass pools (leaf, fineroot, sapwood, above-/below-ground wood, structural dead wood, storage, crown area, LAI, SAI). All routines live in `biogeochem/FatesAllometryMod.F90`. Each allometric function takes a PFT-level mode flag (`allom_hmode`, `allom_lmode`, `allom_amode`, `allom_smode`, `allom_fmode`, `allom_cmode`, `allom_stmode`) that dispatches to one of several available functional forms.

## Dispatch Wrappers

Each top-level allometric function reads its mode flag from `prt_params` and calls the appropriate low-level routine.

| Wrapper | Location | Dispatches on |
|---|---|---|
| `h_allom` | `FatesAllometryMod.F90:333-366` | `allom_hmode` |
| `h2d_allom` | `FatesAllometryMod.F90:296-331` | inverse of `h_allom` |
| `bagw_allom` | `FatesAllometryMod.F90:372-434` | `allom_amode` |
| `blmax_allom` | `FatesAllometryMod.F90:440-470` | `allom_lmode` |
| `carea_allom` | `FatesAllometryMod.F90:476-550` | `allom_lmode` (shares leaf exponent) |
| `bleaf` | `FatesAllometryMod.F90:554-610` | wraps `blmax_allom` + trim + damage + `elongf_leaf` |
| `bsap_allom` | `FatesAllometryMod.F90:922-1017` | `allom_smode` |
| `bbgw_allom` | `FatesAllometryMod.F90:1025-1051` | `allom_cmode` (BGW from AGW) |
| `bfineroot` | `FatesAllometryMod.F90:1057-1117` | `allom_fmode` |
| `bstore_allom` | `FatesAllometryMod.F90:1124-1162` | `allom_stmode` |
| `bdead_allom` | `FatesAllometryMod.F90:1170-1220` | derived from bagw/bbgw/bsap |
| `tree_lai` | `FatesAllometryMod.F90:636-761` | exponential SLA profile via `decay_coeff_kn` |
| `tree_sai` | `FatesAllometryMod.F90:765-827` | multiplier on target LAI |
| `ForceDBH` | `FatesAllometryMod.F90:2439-2587` | iterative root-finder on target bdead |
| `CheckIntegratedAllometries` | `FatesAllometryMod.F90:163-293` | consistency check |

## Height Allometry

`h_allom` (`FatesAllometryMod.F90:333-366`) selects one of five modes based on `prt_params%allom_hmode(ipft)`. All modes cap height at `allom_dbh_maxheight`. The actual formulas are as follows.

### Mode 1: O'Brien et al. 1995 (`d2h_obrien`)

`FatesAllometryMod.F90:1670-1693`. **This is a power law, not an asymptotic exponential.**

```
h = 10 ** ( log10(min(d, dbh_maxh)) * p1 + p2 )
  = 10 ** p2  *  d ** p1       (for d < dbh_maxh)
```

with `p1 = allom_d2h1`, `p2 = allom_d2h2`. The BCI default values cited in the source comments are `p1 = 0.64`, `p2 = 0.37`. The derivative is `dhdd = p1 * 10**p2 * d**(p1 - 1)`.

### Mode 2: Poorter et al. 2006 (`d2h_poorter2006`)

`FatesAllometryMod.F90:1561-1606`. Weibull asymptote:

```
h = p1 * ( 1 - exp( p2 * min(d, dbh_maxh)**p3 ) )
```

with `p1 = h_max`, `p2 < 0`, `p3 > 0`. Three parameters.

### Mode 3: 2-parameter power (`d2h_2pwr`)

`FatesAllometryMod.F90:1610-1666`. Used for initialization and temperate species:

```
h = p1 * min(d, dbh_maxh) ** p2
```

### Mode 4: Chave et al. 2014 (`d2h_chave2014`)

`FatesAllometryMod.F90:1497-1557`. Log-quadratic with an environmental stress factor E baked into p1:

```
h = exp( p1 + p2 * log(d) + p3 * log(d)**2 )   (for d < dbh_maxh)
```

### Mode 5: Martinez-Cano et al. 2016 (`d2h_martcano`)

`FatesAllometryMod.F90:1697-1741`. **This is a three-parameter Michaelis-Menten, not a "height-capped variant".**

```
h = ( p1 * d**p2 ) / ( p3 + d**p2 )
```

with `p1 = h_max`, `p2 = shape exponent`, `p3 = half-saturation`. Originally fit at BCI by Martinez-Cano et al. 2016.

All five modes share the maximum-height cap at `dbh_maxh`; that cap is not what distinguishes Martinez-Cano from the others.

## Leaf Biomass Allometry

`blmax_allom` (`FatesAllometryMod.F90:440-470`) dispatches on `allom_lmode`. **All three modes return kgC (divided by `c2b`).** Actual leaf biomass `bleaf` additionally applies canopy trim, crown damage, and `elongf_leaf`.

### Mode 1: Saldarriaga (`d2blmax_salda`)

`FatesAllometryMod.F90:1394-1423`. Three-parameter plus wood density:

```
blmax = p1 * min(d, dbh_maxh) ** p2 * rho ** p3
```

(Note: `c2b` is accepted as an argument but not used in the Saldarriaga form -- `blmax` is already carbon.)

### Mode 2: 2-parameter power (`d2blmax_2pwr`)

`FatesAllometryMod.F90:1427-1451`. Uncapped power law:

```
blmax = ( p1 * d ** p2 ) / c2b
```

### Mode 3: Height-capped 2-parameter power (`dh2blmax_2pwr`)

`FatesAllometryMod.F90:1455-1491`. **Does NOT include height despite its name** (the `dh` prefix is a historical misnomer -- height is never used). Same form as mode 2 but capped at `dbh_maxh`:

```
blmax = ( p1 * min(d, dbh_maxh) ** p2 ) / c2b
```

The derivative is zero once `d >= dbh_maxh`, so large trees do not add leaf mass.

### Wrapper: `bleaf`

`FatesAllometryMod.F90:554-610`. `bleaf` calls `blmax_allom` then applies:

1. Canopy trim multiplier `canopy_trim` (0-1, set by `trim_canopy()`)
2. Crown damage via `GetCrownReduction` from `DamageMainMod.F90`
3. Phenological scaling by `elongf_leaf` (0-1)

## Above-Ground Woody Biomass

`bagw_allom` (`FatesAllometryMod.F90:372-434`) dispatches on `allom_amode`:

### Mode 1: Saldarriaga (`dh2bagw_salda`)

`FatesAllometryMod.F90:1845-1904`. Function of dbh, height, wood density, and four parameters. Called after `h_allom(d, ipft, h, dhdd)`.

### Mode 2: 2-parameter power (`d2bagw_2pwr`)

`FatesAllometryMod.F90:1794-1843`. `bagw = (p1 * d**p2) / c2b`.

### Mode 3: Chave 2014 (`dh2bagw_chave2014`)

`FatesAllometryMod.F90:1743-1792`. Standard Chave biomass equation involving wood density, diameter, and height.

All three are then scaled by `elongf_stem` (phenology) and optionally by a crown-damage reduction applied to the branch fraction only (`FatesAllometryMod.F90:416-430`).

## Below-Ground Woody Biomass

`bbgw_allom` (`FatesAllometryMod.F90:1025-1051`). For supported modes, `bbgw` is computed as a fixed fraction of total woody biomass determined by `allom_agb_frac`:

```
bbgw = elongf_stem * bagw * (1 - allom_agb_frac) / allom_agb_frac
```

## Sapwood and Structural Biomass

| Function | Location | Role |
|---|---|---|
| `bsap_allom` | `FatesAllometryMod.F90:922-1017` | Sapwood biomass via sapwood area, LA per SA ratio, and `elongf_stem` |
| `bdead_allom` | `FatesAllometryMod.F90:1170-1220` | Structural (dead-wood) biomass as `bagw + bbgw - bsap` |

Sapwood area is derived from target leaf area via `allom_la_per_sa_int + allom_la_per_sa_slp * h`.

## Fine Root Allometry

`bfineroot` (`FatesAllometryMod.F90:1057-1117`). Fine-root target is proportional to leaf target through the leaf-to-fineroot ratio `l2fr`:

```
bfr = l2fr * blmax(d) * canopy_trim * effnrt_coh
```

For carbon-only allocation `l2fr` is a fixed PFT parameter `allom_l2fr`. For CNP allocation, `l2fr` is a dynamically updated cohort state adjusted by the PID controller in `parteh/PRTAllometricCNPMod.F90` (`CNPAdjustFRootTargets`). The minimum is `l2fr_min` (0.01) to prevent numerical issues.

## Crown Area

`carea_allom` (`FatesAllometryMod.F90:476-550`) uses the leaf-biomass exponent `allom_d2bl2` plus `allom_blca_expnt_diff` to derive a dbh exponent for crown area, optionally capping `d` at `dbh_maxh` (for modes 1 and 3) or not (mode 2). Crown damage is applied via `GetCrownReduction`.

## Storage Carbon Target

`bstore_allom` (`FatesAllometryMod.F90:1124-1162`). Sizes storage carbon target as a PFT-dependent fraction of target leaf biomass. For CNP allocation, storage is additionally sized for N and P stoichiometry (see `parteh/cnp_allocation.md`).

## LAI and SAI

### `tree_lai`

`FatesAllometryMod.F90:636-761`. Converts leaf carbon per cohort into leaf-area index, accounting for an exponential SLA profile with canopy depth:

```
sla(depth) = slatop * exp( -kn * (canopy_lai_above + x) )
```

capped at `slamax`. The decay coefficient `kn` comes from `decay_coeff_kn(pft, vcmax25top)`. There are two cases depending on whether `leafc_per_unitarea` is small enough to stay within the exponential regime or large enough to spill into a linear regime at `sla_max` (`FatesAllometryMod.F90:714-754`).

### `tree_sai`

`FatesAllometryMod.F90:765-827`. Stem area index is a simple multiple of target (fully flushed) leaf area:

```fortran
tree_sai = elongf_stem * prt_params%allom_sai_scaler(pft) * target_lai
```

(`FatesAllometryMod.F90:797`). **The controlling parameter is `fates_allom_sai_scaler`, not `fates_phen_stem_drop_fraction`.** The `elongf_stem` factor does carry phenology information, but it is computed upstream in `phenology_leafonoff` from `phen_stem_drop_fraction` and `elong_factor`, not passed directly here. `target_lai` is computed from `bleaf(d, ..., elongf_leaf=1.0)` then passed through `tree_lai`, so SAI uses the fully flushed target leaf area regardless of current phenology.

## CheckIntegratedAllometries

`FatesAllometryMod.F90:163-293`. Verifies that integrated biomass pools match diagnosed allometric targets within tolerance to prevent accumulation of numerical error in the PARTEH ODE integration.

## ForceDBH

`FatesAllometryMod.F90:2439-2587`. Iterative root-finder (bisection) that adjusts `d` to match a target `bdead` pool. Used in cohort fusion, damage recovery, and whenever the state is updated externally and allometric quantities must be re-synced.

## Key Allometry Parameters

| Parameter group | Typical keys (CDL prefix `fates_`) | Used in |
|---|---|---|
| Height | `allom_hmode`, `allom_d2h1`, `allom_d2h2`, `allom_d2h3`, `allom_dbh_maxheight` | `h_allom` |
| Leaf | `allom_lmode`, `allom_d2bl1`, `allom_d2bl2`, `allom_d2bl3`, `slatop`, `slamax` | `blmax_allom`, `tree_lai` |
| Crown area | `allom_d2ca_coefficient_min`, `allom_d2ca_coefficient_max`, `allom_blca_expnt_diff` | `carea_allom` |
| Above-ground wood | `allom_amode`, `allom_agb1`..`allom_agb4`, `wood_density`, `allom_agb_frac` | `bagw_allom` |
| Sapwood | `allom_smode`, `allom_la_per_sa_int`, `allom_la_per_sa_slp` | `bsap_allom` |
| Fine root | `allom_fmode`, `allom_l2fr` | `bfineroot` |
| Storage | `allom_stmode` | `bstore_allom` |
| SAI | `allom_sai_scaler` | `tree_sai` |
| Conversions | `c2b`, `wood_density` | all |

## Integration With PARTEH

Allometric targets drive the growth ODE integration in `parteh/PRTAllometricCarbonMod.F90` (carbon-only) or `parteh/PRTAllometricCNPMod.F90` (CNP). Each day the allocator solves for `d` such that integrated pools match allometric targets, within the constraint of available photosynthate and, for CNP, nutrient uptake. See `parteh/index.md` for details.
