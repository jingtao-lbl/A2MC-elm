---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# FATES Land-Use Change (LUH2) and IAC/EHC Coupling

This page documents two integration paths into `dyn_subgrid/` that did not exist
in the older `60d9aad` ELM tree:

1. **FATES LUH2 land-use change** via the new module `dynFATESLandUseChangeMod.F90`,
   gated by the `use_fates_luh` namelist flag and the `fates_harvest_mode` enum.
2. **IAC / EHC (Integrated Assessment Component / E3SM Human Coupling) coupling**
   via two new private routines `dyn_iac_init` and `set_iac_veg_weights` in
   `dynSubgridDriverMod.F90`, gated by `iac_present`.

Neither path is mutually exclusive with the existing file-based transient
mechanisms in the abstract, but `dynSubgridControlMod::read_namelist` enforces
that `iac_present` excludes all of `do_harvest`, `do_transient_pfts`,
`do_transient_crops`, and a non-empty `flanduse_timeseries`
(`dyn_subgrid/dynSubgridControlMod.F90:161-169`).

## 1. `dynFATESLandUseChangeMod` — LUH2 dataset reader

Source: `dyn_subgrid/dynFATESLandUseChangeMod.F90` (268 lines).

### 1.1 Purpose

Owns three module-public arrays consumed downstream by FATES boundary-condition
code (`dyn_subgrid/dynFATESLandUseChangeMod.F90:24-30`):

```fortran
real(r8), allocatable, public :: landuse_states(:,:)       ! (12, begg:endg)
real(r8), allocatable, public :: landuse_transitions(:,:)  ! (108, begg:endg)
real(r8), allocatable, public :: landuse_harvest(:,:)      ! (5, begg:endg)
```

with the corresponding count parameters (`:28-30`):

```fortran
integer, public, parameter :: num_landuse_transition_vars = 108
integer, public, parameter :: num_landuse_state_vars      = 12
integer, public, parameter :: num_landuse_harvest_vars    = 5
```

These are populated each time step by reading the LUH2 (Land Use Harmonization v2)
dataset addressed by the namelist file name passed into `dynFatesLandUseInit`.

### 1.2 Namelist gates

Two namelist flags (defined in `main/elm_varctl.F90`) control this path:

| Flag | Default | Source |
|---|---|---|
| `use_fates_luh` | `.false.` | `main/elm_varctl.F90:249` |
| `use_fates_potentialveg` | `.false.` | `main/elm_varctl.F90:251` |
| `fates_harvest_mode` | `''` | `main/elm_varctl.F90:230` |

The code allocates and initializes the three arrays unconditionally when
`dynFatesLandUseInit` is called (`:136-152`), but only opens the LUH2 file and
constructs `dyn_var_time_uninterp_type` readers when `use_fates_luh = .true.`
**and** `use_fates_potentialveg = .false.` (`:155-201`). The latter flag is the
"potential vegetation" mode, in which FATES is run without anthropogenic land
use.

### 1.3 `fates_harvest_mode` enum (5 values)

Five public string parameters (`dyn_subgrid/dynFATESLandUseChangeMod.F90:33-37`):

```fortran
character(len=18), public, parameter :: fates_harvest_no_logging   = 'no_harvest'
character(len=18), public, parameter :: fates_harvest_logging_only = 'event_code'
character(len=18), public, parameter :: fates_harvest_hlmlanduse   = 'landuse_timeseries'
character(len=18), public, parameter :: fates_harvest_luh_area     = 'luhdata_area'
character(len=18), public, parameter :: fates_harvest_luh_mass     = 'luhdata_mass'
```

These are namelist-string sentinel values that select which harvest pathway
runs:

| Mode string | Meaning | Effect on `dyn_subgrid/` |
|---|---|---|
| `'no_harvest'` | FATES runs with no logging | None of the harvest paths run |
| `'event_code'` | FATES uses internal event-code logging | None of the `dyn_subgrid/` harvest paths run |
| `'landuse_timeseries'` | Harvest read from the legacy `flanduse_timeseries` HARVEST_VH/SH streams | `dynHarvest_init` and `dynHarvest_interp_harvest_types` are called from the driver via the `fates_harvest_mode == fates_harvest_hlmlanduse` branch (`dyn_subgrid/dynSubgridDriverMod.F90:120, 272`) |
| `'luhdata_area'` | Harvest read as area fraction from LUH2 (`primf_harv`, `primn_harv`, `secmf_harv`, `secyf_harv`, `secnf_harv`) (`:47-48`) | `landuse_harvest_vars(:)` populated; `landuse_harvest_units = 1` (`:185`) |
| `'luhdata_mass'` | Harvest read as biomass carbon from LUH2 (`primf_bioh`, `primn_bioh`, `secmf_bioh`, `secyf_bioh`, `secnf_bioh`) (`:51-52`) | `landuse_harvest_vars(:)` populated; `landuse_harvest_units = 2` (`:188`) |

The `landuse_harvest_units` switch (1 = area fraction, 2 = mass / carbon) is
declared at `:40-42` and set inside `dynFatesLandUseInit` once the mode is
parsed.

### 1.4 LUH2 state variable names (12)

`landuse_state_varnames` (`:57-69`) holds the 12 named LUH2 state classes:

| # | Code | Description |
|---|---|---|
| 1 | `primf` | forested primary land |
| 2 | `primn` | non-forested primary land |
| 3 | `secdf` | potentially forested secondary land |
| 4 | `secdn` | potentially non-forested secondary land |
| 5 | `pastr` | managed pasture |
| 6 | `range` | rangeland |
| 7 | `urban` | urban land |
| 8 | `c3ann` | C3 annual crops |
| 9 | `c4ann` | C4 annual crops |
| 10 | `c3per` | C3 perennial crops |
| 11 | `c4per` | C4 perennial crops |
| 12 | `c3nfx` | C3 nitrogen-fixing crops |

### 1.5 LUH2 transition variable names (108)

`landuse_transition_varnames` (`:71-95`) holds 108 named transitions of the form
`{src}_to_{dst}`. Every ordered pair from the 12-class set is enumerated except
`primf_to_primn` and `primn_to_primf` (primary land cannot regenerate),
`primf_to_secdf` and `primn_to_secdn` (primary becomes the matching secondary
class implicitly via harvest), and same-class transitions (`X_to_X`). The full
list groups by source class:

- 9 `primf_to_*` (`secdn`, `pastr`, `range`, `urban`, `c3ann`, `c4ann`, `c3per`, `c4per`, `c3nfx`)
- 9 `primn_to_*`
- 9 `secdf_to_*`
- 9 `secdn_to_*`
- 9 `pastr_to_*`
- 9 `range_to_*`
- 9 `urban_to_*`
- 9 each for `c3ann_to_*`, `c4ann_to_*`, `c3per_to_*`, `c4per_to_*`, `c3nfx_to_*`

Total = 12 sources, 9 destinations each = 108.

### 1.6 `dynFatesLandUseInit(bounds, landuse_filename)` — `:107-209`

- `SHR_ASSERT_ALL` requires processor-level bounds (`:133`).
- Allocates the three module-public arrays at `(num_*_vars, bounds%begg:bounds%endg)`
  with explicit error checks (`:136-147`).
- Initializes them all to `0._r8` (`:150-152`).
- If `.not. use_fates_potentialveg`:
  - If `use_fates_luh`: opens `landuse_filename` as a `dyn_file_type` with
    `YEAR_POSITION_END_OF_TIMESTEP` (`:160`) and constructs one
    `dyn_var_time_uninterp_type` per state variable and per transition variable,
    all with `do_check_sums_equal_1=.false.` and `data_shape=[num_points]` where
    `num_points = bounds%endg - bounds%begg + 1` (`:163-176`).
  - If `fates_harvest_mode` is one of `fates_harvest_luh_area` or
    `fates_harvest_luh_mass`, points `landuse_harvest_varnames` at the
    corresponding 5-element string array, sets `landuse_harvest_units` to 1 or
    2, and constructs the 5 harvest readers (`:179-199`). Any unrecognized
    harvest mode (other than the two LUH modes) inside this branch triggers
    `endrun` (`:189-190`).
  - Calls `dynFatesLandUseInterp(bounds, init_state=.true.)` so FATES has
    state data available at initialization (`:205`).

The `dynFatesLandUse_file` object is module-private (`:44`), so this opening
happens once per process.

### 1.7 `dynFatesLandUseInterp(bounds, init_state)` — `:213-265`

Called every time step from Pass B of the driver (see Section 3 below). Its
behavior:

1. Calls `dynFatesLandUse_file%time_info%set_current_year_get_year()` (`:237`)
   to advance the LUH2 file's time-info to the current model year.
2. **Before the start of the time series** (and `init_state` not set): zeros all
   three arrays for safety (`:239-243`).
3. **Otherwise**: allocates a `(begg:endg)` scratch buffer, reads each
   transition variable into it via `landuse_transition_vars(varnum)%get_current_data`,
   and copies into `landuse_transitions(varnum, begg:endg)`. Same loop for the
   12 state variables. For LUH harvest modes, same loop for the 5 harvest
   variables. Deallocates the buffer (`:244-263`).

Note the comment at `:245`: "Right now we don't account for the topounits". The
LUH2 reader operates on `(begg:endg)` only, with no topounit dimension.

### 1.8 Limitations

- All three arrays are sized `(begg:endg)`, not `(begg:endg, max_topounits)` —
  the LUH2 path is gridcell-resolution only.
- The `dyn_var_time_uninterp_type` readers use `dim1name=grlnd` (`:168, 174,
  196`), so values jump on January 1 of each model year (no within-year linear
  interpolation, unlike `dyn_var_time_interp_type`).
- The state and transition arrays are **published**; this module does not modify
  any `veg_pp` / `col_pp` / `lun_pp` weight. Consumption happens on the FATES
  side via boundary-condition code that reads `landuse_states`,
  `landuse_transitions`, and `landuse_harvest` once per FATES time step.

## 2. IAC / EHC coupling — private routines in the driver

`dynSubgridDriverMod.F90` adds two private routines for the IAC / EHC pathway,
both gated by `iac_present` (defined in `main/elm_varctl.F90`):

| Routine | Lines | Caller |
|---|---|---|
| `dyn_iac_init(bounds)` | `:409-462` | `dynSubgrid_init` at `:131` (under `if (iac_present)`) |
| `set_iac_veg_weights(bounds)` | `:465-553` | `dynSubgrid_wrapup_weight_changes` at `:396` (under `if (iac_present)`) |

### 2.1 `dyn_iac_init(bounds)` — `:409-462`

- `SHR_ASSERT_ALL` requires processor-level bounds (`:431`).
- If `.not. get_do_harvest()`, allocates `harvest_rates(num_harvest_vars,
  bounds%begg:bounds%endg)` and zeros it (`:436-444`). This ensures harvest_rates
  exists for the IAC path even when the standard CN harvest namelist is off,
  because IAC will publish harvest data into it.
- Asserts `maxpatch_pft == numpft + 1` (`:446-451`), the same constraint
  enforced by `dynpft_init`.
- Sets the module-public `do_cn_harvest = .true.` (`:454`). This is a public
  module variable on `dynHarvestMod` (see the `do_cn_harvest` rename in
  `dyn_subgrid/transient_landuse.md`).
- Initializes `veg_pp%wtgcell_iac(p) = veg_pp%wtgcell(p)` for every patch in
  bounds (`:458-460`), so that `dynSubgrid_wrapup_weight_changes` sees a
  consistent IAC weight at startup.

### 2.2 `set_iac_veg_weights(bounds)` — `:465-553`

Called inside `dynSubgrid_wrapup_weight_changes` at `:396` after a first
`reweight_wrapup` has run (so the active flags are up to date), but before the
final `reweight_wrapup` at `:403`.

- Allocates per-column / per-landunit / per-topounit / per-gridcell sum scratch
  arrays (`:488-495`).
- For each patch (`:500-519`):
  - If the column's `wtgcell` is zero, assigns `wtcol = 1` to bare-soil PFT
    (`itype == 0`) and `wtcol = 0` to all other PFTs in that column.
  - Otherwise, assigns `wtcol = wtgcell_iac(p) / col_pp%wtgcell(c)`.
  - Recomputes `wtlunit`, `wttopounit`, `wtgcell` from `wtcol` times the
    corresponding column-level weight.
  - Accumulates `sumwtcol(c)`.
- For each column (`:522-540`): if `|sumwtcol(c) - 1| > 1.e-12` (the local
  `tolerance` parameter at `:485`), normalizes patch weights in that column. If
  `sumwtcol(c) == 0`, writes a diagnostic message to `iulog` and sets `wtcol =
  0` for all patches in the column. After re-normalization, recomputes the
  higher-order weights (`wtlunit`, `wttopounit`, `wtgcell`) again.
- Skeleton comments at `:542-546` ("Normalize the wtlunit / wttopounit /
  wtgcell if necessary") indicate further normalization layers were planned but
  are not yet implemented.

The IAC path therefore writes `veg_pp%wtgcell_iac` (which is owned by
`VegetationType`, populated by the IAC coupler via
`iac2lnd_vars%update_iac2lnd`) and uses it to overwrite all four weight levels
on `veg_pp`.

### 2.3 `iac2lnd_vars` argument and Pass B invocation

`dynSubgrid_driver` now takes `iac2lnd_vars` as an `inout` argument
(`dyn_subgrid/dynSubgridDriverMod.F90:225`). In Pass B (the I/O-bound,
processor-level region outside OMP), after the existing
`dynHarvest_interp_harvest_types` and the new `dynFatesLandUseInterp` calls,
the driver invokes (`:284-286`):

```fortran
if (iac_present) then
   call iac2lnd_vars%update_iac2lnd(bounds_proc)
end if
```

This is what populates `veg_pp%wtgcell_iac`. The accompanying comment at
`:280-282` notes that "pft and harvest come from iac when active" and that the
namelist values for `do_transient_pfts`, `do_transient_crops`, `do_harvest`
must be `.false.` — exactly the constraint enforced by the `read_namelist`
check.

### 2.4 Mutually-exclusive namelist check (`dynSubgridControlMod::read_namelist`)

`dyn_subgrid/dynSubgridControlMod.F90:161-169`:

```fortran
if (iac_present) then
   if (do_harvest .or. do_transient_crops .or. do_transient_pfts .or. &
       flanduse_timeseries /= '') then
      call endrun(msg='ERROR in dynamic_subgrid namelist: when EHC is active ' // &
                       'do_harvest, do_transient_pfts, do_transient_crops ' // &
                       'must be .false., and flanduse_timeseries must not ' // &
                       'be set (i.e., an empty string)' //errMsg(sourcefile, __LINE__))
   endif
endif
```

This is a hard error at namelist-read time, before
`check_namelist_consistency` runs, and lives in `read_namelist` (not in
`check_namelist_consistency`). The corresponding `use elm_varctl, only :
fname_len, iac_present` import was added at `:17`.

## 3. Pass-B placement in the driver

The new calls in Pass B of `dynSubgrid_driver` are (in order, `:264-286`):

```
if (get_do_transient_pfts())          call dynpft_interp(bounds_proc)
if (get_do_transient_crops())         call dyncrop_interp(bounds_proc, crop_vars)
if (get_do_harvest() .or. fates_harvest_mode == fates_harvest_hlmlanduse) then
                                      call dynHarvest_interp_harvest_types(bounds_proc)
if (use_fates_luh .and. .not. use_fates_potentialveg) then
                                      call dynFatesLandUseInterp(bounds_proc)
if (iac_present)                      call iac2lnd_vars%update_iac2lnd(bounds_proc)
```

All five blocks run at processor-level outside the OMP region, because they
either do PIO file reads (the first four) or invoke a coupler-side update (the
fifth).

The matching block in `dynSubgrid_init` (`:114-132`) calls `dynpft_init`,
`dynHarvest_init`, `dyncrop_init`, and `dyn_iac_init` under analogous gates;
note that `dynFatesLandUseInit` is called from elsewhere in ELM initialization
(driven by FATES startup), not from `dynSubgrid_init` itself.

## 4. Cross-references

- Driver structure and Pass A/B/C summary diagram: `dyn_subgrid/index.md`.
- File reader machinery for `flanduse_timeseries` (`dynFileMod`,
  `dynVarTimeUninterpMod`, `dynTimeInfoMod`): `dyn_subgrid/transient_landuse.md`.
- The `do_cn_harvest` rename and the `if (use_fates) do_cn_harvest = .false.`
  enforcement: `dyn_subgrid/transient_landuse.md` Section 8.
- The second `reweight_wrapup` call inside `dynSubgrid_wrapup_weight_changes`:
  `dyn_subgrid/weight_updates_and_conservation.md` Section 7.
