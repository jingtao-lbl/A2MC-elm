---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Fire (CN-fire and FATES-fire factory)

ELM supports two disjoint fire paths:

1. **CN-fire** — the Li and Levis process-based fire model
   (`biogeochem/FireMod.F90`), used with `use_cn = .true.` and
   `use_fates = .false.`. This is the ELM-native fire code.
2. **FATES fire** — a polymorphic backend that lets ELM dispatch to one of
   several FATES SPITFIRE data configurations at run time. The abstract base
   and concrete wrappers live in
   `biogeochem/FireMethodType.F90`, `biogeochem/FireDataBaseType.F90`,
   `biogeochem/FATESFireBase.F90`, `biogeochem/FATESFireDataMod.F90`,
   `biogeochem/FATESFireFactoryMod.F90`, and
   `biogeochem/FATESFireNoDataMod.F90`. The actual SPITFIRE physics lives
   inside FATES and is out of scope for this document.

## Files in scope

| File | Role |
|---|---|
| `FireMod.F90` | CN-fire process model (Li and Levis 2012/2013/2014). |
| `FireMethodType.F90` | Abstract base class `fire_method_type` with deferred `FireInit` / `FireInterp`. |
| `FireDataBaseType.F90` | Abstract `fire_base_type` that extends `fire_method_type` and owns the shared lightning, population-density, and GDP data streams. |
| `FATESFireBase.F90` | Abstract `fates_fire_base_type` that extends `fire_base_type`; adds deferred `GetLight24`, `GetGDP`, and accumulation interfaces. |
| `FATESFireDataMod.F90` | Concrete `fates_fire_data_type` — uses lightning and population density streams. |
| `FATESFireNoDataMod.F90` | Concrete `fates_fire_no_data_type` — no data streams; returns `need_lightning_and_popdens = .false.`. |
| `FATESFireFactoryMod.F90` | Factory that allocates the right concrete type based on `fates_spitfire_mode`. |

The FATES-fire files exist entirely inside ELM's source tree even though the
underlying fire physics runs inside FATES. They form a thin dispatch layer so
ELM can hand FATES either "no lightning/population data" or "read lightning
and population density from shr_strdata streams" without knowing which
SPITFIRE mode is in effect.

## CN-fire (`FireMod.F90`)

### Public surface

```
FireInit    (FireMod.F90:83)    -- initializes HDM and lightning streams (unless CPL_BYPASS)
FireInterp  (FireMod.F90:100)   -- interpolates HDM/LNFM streams per time step
FireArea    (FireMod.F90:115)   -- computes column burned area fraction
FireFluxes  (FireMod.F90:648)   -- applies burned area to C/N/P pools and generates fire emissions
```

`FireInit` / `FireInterp` wrap the private `hdm_init` / `hdm_interp` /
`lnfm_init` / `lnfm_interp` routines which use `shr_strdata_mod` to read
Lightning frequency (`forc_lnfm`) and human population density
(`forc_hdm`). Under the `CPL_BYPASS` configuration these calls are skipped
because the fields are read directly from the atmosphere coupler
(`FireMod.F90:193-196`, `282-292`).

### Reference

Implementation and parameter tuning follow
Li et al. (2012a, 2012b), Li et al. (2013), and
Li et al. (2014)
(`biogeochem/FireMod.F90:4-12`), calibrated against the 20th-century
transient runs at f19_g16 with CLM4.5.

### `FireArea` — fractional burned area

`FireArea` aggregates vegetation pools to the column (`p2c` of `totvegc`,
`leafc`, `deadstemc`), then computes three contributions to burned area
(`FireMod.F90:280-632`):

**1. Crop fire (`baf_crop`).** Fires are allowed on croplands
(`veg_pp%itype > nc4_grass`) when:

- `kmo == abm_lf(c)` (the prescribed agricultural burn month for the column),
- no current-time-step precipitation,
- the crop has not already burned this year (`burndate(p) >= 999`),
- the patch has nonzero `wtcol`, and
- `forc_t >= Tkfrz`.

Then (`FireMod.F90:494-512`):

```
fhd  = 0.04 + 0.96 * exp(-pi * sqrt(hdmlf / 350))      ! human density factor
fgdp = 0.01 + 0.99 * exp(-pi * (gdp_lf / 10))          ! GDP factor
fb   = max(0, min(1, (fuelc_crop - lfuel)/(ufuel - lfuel)))
baf_crop(c) += (cropfire_a1 / secsphr) * fb * fhd * fgdp * wtcol
```

where `cropfire_a1 = 0.3`, `lfuel = 75`, `ufuel = 1050` g C/m² are from
Li et al. 2014 (`FireMod.F90:150-156`).

**2. Peat fire (`baf_peatf`).** Applied to the peatland fraction
`peatf_lf`, split by a latitude threshold `borealat = 40°`
(`FireMod.F90:72, 520-532`):

- Non-boreal (|lat| < 40°):
  `baf_peatf = non_boreal_peatfire_c/secsphr * max(0, min(1, (4 - prec60*secspday)/4))^2 * peatf_lf * (1 - fsat)`
  with `non_boreal_peatfire_c = 0.001`.
- Boreal:
  `baf_peatf = boreal_peatfire_c/secsphr * exp(-pi * (wf2 / 0.3)) * max(0, min(1, (tsoi17 - Tkfrz)/10)) * peatf_lf * (1 - fsat)`
  with `boreal_peatfire_c = 4.2e-5`.

**3. Non-crop non-peat fire.** For non-cropland columns (`cropf_col < 1`)
that are not dominated by tropical forest (`trotr1_col + trotr2_col ≤ 0.6`),
the main Li and Levis expression is computed
(`FireMod.F90:562-596`):

- Fuel available: `fuelc = totlitc + totvegc_col - rootc_col - fuelc_crop*cropf_col`
  plus CWD pools from `decomp_cpools_vr(c, :, i_cwd)` integrated over
  depth. Accelerated-spinup uses `spinup_factor(i_cwd)` to rescale the CWD
  contribution (`FireMod.F90:562-574`).
- Fuel combustibility: `fb = (fuelc - lfuel)/(ufuel - lfuel)` clipped to
  [0,1].
- Moisture term: `fire_m = exp(-pi*(wf/0.69)^2) * (1 - RH_factor) *
  min(1, exp(pi*(T - Tkfrz)/10))`. `wf` is top-5 cm soil water as a
  fraction of whc (`FireMod.F90:206`).
- Ignition density: `lh = 0.0035 * 6.8 * hdmlf^0.43 / 30 / 24` (anthropogenic
  ignitions), `fs = 1 - (0.01 + 0.98*exp(-0.025*hdmlf))` (suppression),
  `ig = (lh + forc_lnfm/(5.16 + 2.16*cos(3*lat))*0.25)*(1 - fs)*(1 - cropf)`.
- Fire counts: `nfire = ig/secsphr * fb * fire_m * lgdp_col`.
- Length-to-breadth ratio (wind elongation):
  `Lb_lf = 1 + 10*(1 - exp(-0.06 * wind))`.
- Spread combustibility `spread_m` from column-averaged `btran`, `wtlf`,
  `forc_rh`.
- Final: `farea_burned = min(1, (g0*spread_m*fsr_col*fd_col/1000)^2 * lgdp1
  * lpop * nfire * pi * Lb_lf + baf_crop + baf_peatf)` with `g0 = 0.05`.

**4. Tropical-forest / deforestation fire.** When the column is dominated by
broadleaf tropical evergreen or deciduous trees
(`trotr1_col + trotr2_col > 0.6`) and `transient_landcover` is active, the
deforestation-fire pathway (`FireMod.F90:602-624`) replaces the main model
with a moisture-and-clearing-rate expression parameterized by
`cli_scale = 0.035 /day`, precipitation over 60-day and 10-day windows, and
the change in tropical-forest fraction `dtrotr_col`.

### `FireFluxes` — C, N, and P effects

After `farea_burned` is known for each column, `FireFluxes`
(`FireMod.F90:648`) distributes the burned area over vegetation and litter
pools and accumulates emissions. Per-PFT combustion completeness `cc_*` and
per-pool mortality-by-fire fractions `fm_*` come from `pftvarcon`:
`cc_leaf`, `cc_lstem`, `cc_dstem`, `cc_other`, `fm_leaf`, `fm_lstem`,
`fm_other`, `fm_root`, `fm_lroot`, `fm_droot` (`FireMod.F90:663`). For each
vegetation C pool, the fire sends a portion to the atmosphere (combusted)
and a portion to litter (killed but not combusted), using the patch's
combustion completeness and mortality-by-fire fractions. The same pattern
applies to N and P with pool-specific completeness rules.

The routine also sinks litter and CWD directly via `farea_burned` (non-crop
component) scaled by `decomp_cpools_vr` profiles, handles accelerated-spinup
fuel adjustments, and, for transient land-cover runs, updates `lfc` (the
"still-burnable tropical forest fraction") and `lfc2` (the fraction
consumed this time step by the deforestation pathway).

Outputs per column: `farea_burned` (/sec), `baf_crop`, `baf_peatf`,
`fbac` (out-of-conversion BA), `fbac1` (LU-only out-of-conversion BA),
`nfire`, `fsr_col` (fire spread rate weighted average), `fd_col` (fire
duration), and per-pool fire emission fluxes into `col_cf` / `col_nf` /
`col_pf`.

### Control flag

`use_nofire` (`main/elm_varctl.F90:348`) turns CN-fire off entirely; it is
checked at the top of `FireArea` (`FireMod.F90:127-128` via the
`use_nofire` use-statement) and short-circuits the entire burned-area
calculation.

## FATES fire factory

When `use_fates = .true.`, FATES-internal SPITFIRE owns the fire process.
However, SPITFIRE can run in several modes that differ by what external
data they read. ELM provides the data-ingestion layer via a small
polymorphism hierarchy.

### Class hierarchy

```
fire_method_type                         (FireMethodType.F90:16)
  abstract base
  defers: FireInit(this, bounds, NLFilename)
          FireInterp(this, bounds)
      │
      ▼
fire_base_type                           (FireDataBaseType.F90:30)
  abstract extends fire_method_type
  owns:  forc_lnfm, forc_hdm, gdp_lf_col, sdat_hdm, sdat_lnfm
  impl:  FireInit  => BaseFireInit         (FireDataBaseType.F90:84)
  impl:  FireInterp
  defers: need_lightning_and_popdens()
      │
      ▼
fates_fire_base_type                     (FATESFireBase.F90:19)
  abstract extends fire_base_type
  defers: GetLight24(this), GetGDP(this)
          InitAccBuffer, InitAccVars, UpdateAccVars
          need_lightning_and_popdens
      │
      ├────────────▶ fates_fire_data_type       (FATESFireDataMod.F90:23)
      │              - has lnfm24(:) daily lightning data
      │              - need_lightning_and_popdens = .true.
      │
      └────────────▶ fates_fire_no_data_type    (FATESFireNoDataMod.F90:23)
                     - has only a sentinel lnfm24_nodata(:) = spval
                     - need_lightning_and_popdens = .false.
                     - GetLight24 / GetGDP call endrun (must not be used)
```

Both terminal types inherit the shared lightning/population/GDP fields and
the default `FireInit` / `FireInterp` from `fire_base_type`, so the
distinction is only in whether the SPITFIRE module will ask for
`GetLight24` and `GetGDP` at run time. This is the Bill-Sacks-style
polymorphism pattern used elsewhere in ELM for soil-water retention curves:
deferred methods with constant-in-time inputs passed in through the
constructor, so the top-level interface stays the same for every variant
(`FireMethodType.F90:29-41`).

### Factory

`create_fates_fire_data_method`
(`biogeochem/FATESFireFactoryMod.F90:38`) allocates the right concrete type
based on the namelist variable `fates_spitfire_mode`
(`main/elm_varctl.F90:223`). The integer constants defined as public
parameters inside the factory module are
(`FATESFireFactoryMod.F90:25-30`):

| Value | Symbol | Meaning |
|---|---|---|
| 0 | `no_fire` | No fire. |
| 1 | `scalar_lightning` | Fixed scalar lightning (no stream read). |
| 2 | `lightning_from_data` | Lightning read from stream. |
| 3 | `successful_ignitions` | As above, filtered by successful ignitions. |
| 4 | `anthro_ignitions` | As above, plus anthropogenic ignition data. |
| 5 | `anthro_suppression` | As above, plus anthropogenic suppression. |

The factory maps these to concrete types with a range select
(`FATESFireFactoryMod.F90:60-72`):

```
case (no_fire : scalar_lightning)          ! 0, 1
   allocate(fates_fire_no_data_type :: fates_fire_data_method)
case (lightning_from_data : anthro_suppression)  ! 2, 3, 4, 5
   allocate(fates_fire_data_type   :: fates_fire_data_method)
case default
   endrun with "unknown method"
```

This means modes 0 and 1 use the no-data wrapper — SPITFIRE will compute
fire without any stream I/O — while modes 2 through 5 wire in the
`shr_strdata` lightning and population density streams inherited from
`fire_base_type`.

### How it plugs in

The abstract and concrete modules do not call FATES directly. Instead, the
ELM driver allocates a `class(fates_fire_base_type)` pointer, invokes
`create_fates_fire_data_method` to populate it, and then passes the object
into FATES where SPITFIRE's routines call `need_lightning_and_popdens()`,
`GetLight24()`, and `GetGDP()` as deferred virtual methods. The
`need_lightning_and_popdens` flag is what SPITFIRE uses to decide whether
to even try reading lightning and GDP; the `no_data` variant returns
`.false.` and calls `endrun` from the unused getters
(`FATESFireNoDataMod.F90:45-88`) to catch any code path that tries to use
them by mistake.

### `FireDataBaseType.BaseFireInit` and interp

`BaseFireInit` (`FireDataBaseType.F90:84`) allocates `gdp_lf_col` and sets
up the lightning and human-population streams via `lnfm_init` and
`hdm_init` (the method implementations are private to the module). It is
the default `FireInit` for both `fates_fire_data_type` and
`fates_fire_no_data_type`, though for the no-data variant the
infrastructure allocates but the deferred `GetLight24` / `GetGDP` will
never be called in practice.

## Which path runs?

The dispatch is decided at the top-level BGC driver by the combination of
`use_fates`, `use_cn`, and `use_nofire`:

| `use_cn` | `use_fates` | `use_nofire` | `fates_spitfire_mode` | Path |
|---|---|---|---|---|
| T | F | F | — | `FireMod.F90` CN-fire |
| T | F | T | — | No fire (CN-fire skipped) |
| F | T | — | 0 | FATES SPITFIRE, `fates_fire_no_data_type`, no fire |
| F | T | — | 1 | FATES SPITFIRE, `fates_fire_no_data_type`, scalar lightning |
| F | T | — | 2–5 | FATES SPITFIRE, `fates_fire_data_type`, with streams |
| F | F | — | — | No vegetation dynamics, no fire |

FATES and CN-fire are mutually exclusive: when `use_fates = .true.`, the
ELM-native CN ecosystem dynamics driver (which owns `FireArea`/`FireFluxes`)
is not invoked, and all vegetation-mass loss from fire happens inside FATES
via SPITFIRE.

## What is and is not in ELM's tree

- Owned by ELM (this directory):
  CN-fire physics (`FireMod.F90`), the lightning/human-density/GDP data
  streams, the abstract interface, and the factory that decides which
  FATES fire wrapper to allocate.
- Owned by FATES (not in scope):
  SPITFIRE physics, the definition of what "lightning from data" actually
  does to per-cohort mortality, crown-fire promotion, and fire intensity
  calculation. Those live under `external_models/fates/` and are documented
  in the FATES codebase wiki.
