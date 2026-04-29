---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Fire (CN-fire and FATES-fire factory)

ELM supports two disjoint fire paths:

1. **CN-fire** — the Li and Levis process-based fire model
   (`biogeochem/FireMod.F90`), used with `use_cn = .true.` and
   `use_fates = .false.`. ELM-native fire code.
2. **FATES fire** — a polymorphic backend dispatching to one of several FATES
   SPITFIRE data configurations at run time. The abstract base and concrete
   wrappers live in `biogeochem/FireMethodType.F90`,
   `biogeochem/FireDataBaseType.F90`, `biogeochem/FATESFireBase.F90`,
   `biogeochem/FATESFireDataMod.F90`, `biogeochem/FATESFireFactoryMod.F90`,
   and `biogeochem/FATESFireNoDataMod.F90`. The actual SPITFIRE physics lives
   inside FATES.

## Files in scope

| File | Role |
|---|---|
| `FireMod.F90` | CN-fire process model (Li and Levis 2012/2013/2014). |
| `FireMethodType.F90` | Abstract base class `fire_method_type` with deferred `FireInit_interface` / `FireInterp_interface`. |
| `FireDataBaseType.F90` | Abstract `fire_base_type` extending `fire_method_type`; owns lightning, population-density, and GDP data streams. |
| `FATESFireBase.F90` | Abstract `fates_fire_base_type` extending `fire_base_type`; adds deferred `GetLight24`, `GetGDP`, and accumulation interfaces. |
| `FATESFireDataMod.F90` | Concrete `fates_fire_data_type` — uses lightning and population density streams. |
| `FATESFireNoDataMod.F90` | Concrete `fates_fire_no_data_type` — no data streams. |
| `FATESFireFactoryMod.F90` | Factory that allocates the right concrete type based on `fates_spitfire_mode`. |

## CN-fire (`FireMod.F90`)

### Public surface (d40b8431 line numbers)

```
FireInit    (FireMod.F90:84)     -- initializes HDM and lightning streams (unless CPL_BYPASS)
FireInterp  (FireMod.F90:101)    -- interpolates HDM/LNFM streams per time step
FireArea    (FireMod.F90:116)    -- computes column burned area fraction
FireFluxes  (FireMod.F90:671)    -- applies burned area to C/N/P pools and generates fire emissions
```

The line shift in `FireFluxes` (648 -> 671) reflects the additional
trait-flag-based PFT identification logic now embedded in `FireArea`.

`FireInit` / `FireInterp` wrap the private `hdm_init` / `hdm_interp` /
`lnfm_init` / `lnfm_interp` routines which use `shr_strdata_mod` to read
lightning frequency (`forc_lnfm`) and human population density (`forc_hdm`).
Under `CPL_BYPASS`, fields are read directly from the atmosphere coupler.

### Reference

Implementation and parameter tuning follow Li et al. (2012a, 2012b),
Li et al. (2013), and Li et al. (2014), calibrated against the 20th-century
transient runs at f19_g16 with CLM4.5.

### Trait-based PFT identification (REWRITTEN at d40b8431)

`FireArea` and the surrounding loops use `pftvarcon` trait flags directly
rather than named constants. The `use` block at `FireMod.F90:130-131`:

```fortran
use pftvarcon, only: noveg, woody, graminoid, iscft, crop
use pftvarcon, only: climatezone, needleleaf, evergreen
```

Tropical-tree identification example (at `:386-406`):

```fortran
! broadleaf evergreen tropical tree
if( (needleleaf(veg_pp%itype(p)) == 0 .and. &
     evergreen(veg_pp%itype(p)) == 1 .and. &
     climatezone(veg_pp%itype(p)) == 1 .and. &
     woody(veg_pp%itype(p)) == 1.0_r8) .and. ...

! broadleaf deciduous tropical tree
if( (needleleaf(veg_pp%itype(p)) == 0 .and. &
     evergreen(veg_pp%itype(p)) == 0 .and. &
     climatezone(veg_pp%itype(p)) == 1 .and. &
     woody(veg_pp%itype(p)) == 1.0_r8) .and. ...
```

GDP / population-density factors split shrubs+grasses from trees via the
ternary `woody` flag (`:429-441`):

```fortran
if( woody(veg_pp%itype(p)) == 2.0_r8 .or. &        ! shrub
    graminoid(veg_pp%itype(p)) == 1 )then           ! grass
   ! ... shrub-and-grass form of lgdp/lgdp1/lpop ...
else if (woody(veg_pp%itype(p)) == 1.0_r8) then    ! tree
   ! ... tree form ...
end if
```

Cropland tests use `iscft(ivt(p))` instead of `ivt > nc4_grass`/`>= npcropmin`.

### `FireArea` — fractional burned area

`FireArea` aggregates vegetation pools to the column (`p2c` of `totvegc`,
`leafc`, `deadstemc`), then computes three contributions to burned area:

**1. Crop fire (`baf_crop`).** Fires allowed on cropland (`iscft` based) when:

- `kmo == abm_lf(c)` (prescribed agricultural burn month for the column),
- no current-time-step precipitation,
- crop has not already burned this year (`burndate(p) >= 999`),
- patch has nonzero `wtcol`,
- `forc_t >= Tkfrz`.

```
fhd  = 0.04 + 0.96 * exp(-pi * sqrt(hdmlf / 350))      ! human density factor
fgdp = 0.01 + 0.99 * exp(-pi * (gdp_lf / 10))          ! GDP factor
fb   = max(0, min(1, (fuelc_crop - lfuel)/(ufuel - lfuel)))
baf_crop(c) += (cropfire_a1 / secsphr) * fb * fhd * fgdp * wtcol
```

with `cropfire_a1 = 0.3` (`:157`), `lfuel = 75` (`:151`), `ufuel = 1050`
g C/m^2 (`:152`).

**2. Peat fire (`baf_peatf`).** Applied to peatland fraction `peatf_lf`, split
by `borealat = 40 deg` (`:72`):

- Non-boreal: `baf_peatf = non_boreal_peatfire_c/secsphr * max(0, min(1,
  (4 - prec60*secspday)/4))^2 * peatf_lf * (1 - fsat)` with
  `non_boreal_peatfire_c = 0.001` (`:164`).
- Boreal: `baf_peatf = boreal_peatfire_c/secsphr * exp(-pi * (wf2 / 0.3)) *
  max(0, min(1, (tsoi17 - Tkfrz)/10)) * peatf_lf * (1 - fsat)` with
  `boreal_peatfire_c = 4.2e-5` (`:161`).

**3. Non-crop non-peat fire.** For non-cropland columns (`cropf_col < 1`) not
dominated by tropical forest (`trotr1_col + trotr2_col <= 0.6`), the main Li
and Levis expression is computed:

- Fuel available: `fuelc = totlitc + totvegc_col - rootc_col -
  fuelc_crop*cropf_col` plus CWD pools from `decomp_cpools_vr(c, :, i_cwd)`
  integrated over depth. Accelerated-spinup uses `spinup_factor(i_cwd)` for the
  CWD contribution.
- Fuel combustibility: `fb = (fuelc - lfuel)/(ufuel - lfuel)` clipped to [0,1].
- Moisture term: `fire_m = exp(-pi*(wf/0.69)^2) * (1 - RH_factor) *
  min(1, exp(pi*(T - Tkfrz)/10))`. `wf` is top-5 cm soil water as fraction of
  whc.
- Ignition density: `lh = 0.0035 * 6.8 * hdmlf^0.43 / 30 / 24` (anthropogenic),
  `fs = 1 - (0.01 + 0.98*exp(-0.025*hdmlf))` (suppression),
  `ig = (lh + forc_lnfm/(5.16 + 2.16*cos(3*lat))*0.25)*(1 - fs)*(1 - cropf)`.
- Fire counts: `nfire = ig/secsphr * fb * fire_m * lgdp_col`.
- Length-to-breadth ratio: `Lb_lf = 1 + 10*(1 - exp(-0.06 * wind))`.
- Spread combustibility `spread_m` from column-averaged `btran`, `wtlf`,
  `forc_rh`.
- Final: `farea_burned = min(1, (g0*spread_m*fsr_col*fd_col/1000)^2 * lgdp1
  * lpop * nfire * pi * Lb_lf + baf_crop + baf_peatf)` with `g0 = 0.05`.

**4. Tropical-forest / deforestation fire.** When the column is dominated by
broadleaf tropical evergreen or deciduous trees (`trotr1_col + trotr2_col >
0.6`) and `transient_landcover` is active, the deforestation-fire pathway
replaces the main model with a moisture-and-clearing-rate expression
parameterized by `cli_scale = 0.035 /day`, precipitation over 60-day and
10-day windows, and the change in tropical-forest fraction `dtrotr_col`.

### `FireFluxes` — C, N, and P effects

After `farea_burned` is known for each column, `FireFluxes(num_soilc,
filter_soilc, num_soilp, filter_soilp, cnstate_vars)` (`:671-1483`)
distributes the burned area over vegetation and litter pools and accumulates
emissions. Per-PFT combustion completeness `cc_*` and per-pool
mortality-by-fire fractions `fm_*` come from `pftvarcon`: `cc_leaf`,
`cc_lstem`, `cc_dstem`, `cc_other`, `fm_leaf`, `fm_lstem`, `fm_other`,
`fm_root`, `fm_lroot`, `fm_droot`. For each vegetation C pool, fire sends a
portion to the atmosphere (combusted) and a portion to litter (killed but
not combusted). Same for N and P with pool-specific completeness rules.

The routine also sinks litter and CWD via `farea_burned`, handles
accelerated-spinup fuel adjustments, and updates `lfc`, `lfc2` for transient
land-cover runs.

Outputs per column: `farea_burned` (/sec), `baf_crop`, `baf_peatf`, `fbac`,
`fbac1`, `nfire`, `fsr_col`, `fd_col`, and per-pool fire emission fluxes into
`col_cf` / `col_nf` / `col_pf`.

### Control flag

`use_nofire` (`main/elm_varctl.F90:382`) turns CN-fire off entirely.

## FATES fire factory

When `use_fates = .true.`, FATES-internal SPITFIRE owns the fire process. ELM
provides the data-ingestion layer via a polymorphism hierarchy.

### Class hierarchy

```
fire_method_type                         (FireMethodType.F90:16)
  abstract base
  defers: FireInit_interface(this, bounds, NLFilename)
          FireInterp_interface(this, bounds)
      |
      v
fire_base_type                           (FireDataBaseType.F90:30)
  abstract extends fire_method_type
  owns:  forc_lnfm, forc_hdm, gdp_lf_col, sdat_hdm, sdat_lnfm
  impl:  FireInit  => BaseFireInit
  impl:  FireInterp                      (FireDataBaseType.F90:124)
  defers: need_lightning_and_popdens()
      |
      v
fates_fire_base_type                     (FATESFireBase.F90:19)
  abstract extends fire_base_type
  defers: GetLight24(this), GetGDP(this)
          InitAccBuffer, InitAccVars, UpdateAccVars
          need_lightning_and_popdens
      |
      |----------> fates_fire_data_type       (FATESFireDataMod.F90:23)
      |              - has lnfm24(:) daily lightning data
      |              - need_lightning_and_popdens = .true.
      |
      `----------> fates_fire_no_data_type    (FATESFireNoDataMod.F90:23)
                     - has only a sentinel lnfm24_nodata(:) = spval
                     - need_lightning_and_popdens = .false.
                     - GetLight24 / GetGDP call endrun (must not be used)
```

Both terminal types inherit shared lightning/population/GDP fields and the
default `FireInit` / `FireInterp` from `fire_base_type`, so the distinction is
only in whether the SPITFIRE module will ask for `GetLight24` and `GetGDP` at
run time.

### Factory

`create_fates_fire_data_method` (`biogeochem/FATESFireFactoryMod.F90:38`)
allocates the right concrete type based on `fates_spitfire_mode`
(`main/elm_varctl.F90:228`). Public integer constants in the factory module:

| Value | Symbol | Meaning |
|---|---|---|
| 0 | `no_fire` | No fire. |
| 1 | `scalar_lightning` | Fixed scalar lightning (no stream read). |
| 2 | `lightning_from_data` | Lightning read from stream. |
| 3 | `successful_ignitions` | Filtered by successful ignitions. |
| 4 | `anthro_ignitions` | Plus anthropogenic ignition data. |
| 5 | `anthro_suppression` | Plus anthropogenic suppression. |

The factory maps these to concrete types:

```fortran
case (no_fire : scalar_lightning)          ! 0, 1
   allocate(fates_fire_no_data_type :: fates_fire_data_method)
case (lightning_from_data : anthro_suppression)  ! 2, 3, 4, 5
   allocate(fates_fire_data_type   :: fates_fire_data_method)
case default
   endrun with "unknown method"
```

Modes 0 and 1 use the no-data wrapper; modes 2-5 wire in `shr_strdata`
lightning and population density streams.

### How it plugs in

The ELM driver allocates a `class(fates_fire_base_type)` pointer, invokes
`create_fates_fire_data_method` to populate it, and passes the object into
FATES where SPITFIRE's routines call `need_lightning_and_popdens()`,
`GetLight24()`, and `GetGDP()` as deferred virtual methods. The
`need_lightning_and_popdens` flag is what SPITFIRE uses to decide whether to
even try reading lightning and GDP; the no-data variant returns `.false.` and
calls `endrun` from the unused getters to catch any code path that tries to
use them by mistake.

### `FireDataBaseType.BaseFireInit` and interp

`BaseFireInit` (`FireDataBaseType.F90:84`) allocates `gdp_lf_col` and sets up
the lightning and human-population streams via `lnfm_init` and `hdm_init`. It
is the default `FireInit` for both `fates_fire_data_type` and
`fates_fire_no_data_type`.

### Managed-fire and harvest integration (NEW at d40b8431)

Two related namelist flags govern FATES fire/harvest behavior:

- `use_fates_managed_fire` (`elm_varctl.F90:229`) — turn on managed fire.
- `fates_harvest_mode` (`elm_varctl.F90:230`) — character string with five
  modes (see namelist_definitions). **REPLACES** the deleted
  `use_fates_logging` flag from 60d9aad.

Code that hard-coded `use_fates_logging` against the older ELM tree must be
ported to test `fates_harvest_mode` instead.

## Which path runs?

Dispatch decided at the top-level BGC driver by `use_fates`, `use_cn`,
`use_nofire`, and `fates_spitfire_mode`:

| `use_cn` | `use_fates` | `use_nofire` | `fates_spitfire_mode` | Path |
|---|---|---|---|---|
| T | F | F | -- | `FireMod.F90` CN-fire |
| T | F | T | -- | No fire (CN-fire skipped) |
| F | T | -- | 0 | FATES SPITFIRE, `fates_fire_no_data_type`, no fire |
| F | T | -- | 1 | FATES SPITFIRE, `fates_fire_no_data_type`, scalar lightning |
| F | T | -- | 2-5 | FATES SPITFIRE, `fates_fire_data_type`, with streams |
| F | F | -- | -- | No vegetation dynamics, no fire |

FATES and CN-fire are mutually exclusive: when `use_fates = .true.`, the
ELM-native CN ecosystem dynamics driver (which owns `FireArea`/`FireFluxes`)
is not invoked, and all vegetation-mass loss from fire happens inside FATES
via SPITFIRE.

## What is and is not in ELM's tree

- Owned by ELM (this directory): CN-fire physics (`FireMod.F90`), the
  lightning/human-density/GDP data streams, the abstract interface, and the
  factory that decides which FATES fire wrapper to allocate.
- Owned by FATES (not in scope): SPITFIRE physics, the definition of what
  "lightning from data" actually does to per-cohort mortality, crown-fire
  promotion, fire intensity calculation. Those live under
  `external_models/fates/` and are documented in the FATES codebase wiki.
