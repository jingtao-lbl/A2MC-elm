---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Transient Land-use File Reading

This document covers the modules that consume the transient land-use NetCDF
file (`flanduse_timeseries`) and push its contents into the subgrid weight
arrays. For the state-update and conservation machinery that runs after these
weights change, see `dyn_subgrid/weight_updates_and_conservation.md`. For the
separate FATES LUH2 dataset reader (`dynFATESLandUseChangeMod`) and the
IAC / EHC coupling, see `dyn_subgrid/fates_land_use_change.md`.

## 1. Module stack

```
dynSubgridControlMod   (namelist flags, file name)
       |
       v
dynFileMod             (dyn_file_type = file_desc_t + time_info_type)
       |
       v
dynTimeInfoMod         (time_info_type, YEAR_POSITION_{START,END}_OF_TIMESTEP)
       |
       v
dynVarTimeInterpMod       dynVarTimeUninterpMod
(do_genf90 templates)     (do_genf90 templates)
       |                         |
       v                         v
dynpftFileMod    dyncropFileMod   dynHarvestMod
(PCT_NAT_PFT)    (PCT_CROP, PCT_CFT, (HARVEST_VH1..SH3)
                  FERTNITRO_CFT,
                  FERTPHOSP_CFT)
       |                         |
       v                         v
veg_pp%wtcol              lun_pp%wttopounit, col_pp%wtlunit,     harvest_rates(:,:),
                          veg_pp%wtcol, crop_vars%fert*          + CNHarvest state
```

The three reader modules each own a singleton `dyn_file_type` object that wraps
the PIO file descriptor and a `time_info_type`. They are never instantiated
directly; `dynSubgrid_init` (`dyn_subgrid/dynSubgridDriverMod.F90:74-154`)
invokes each of their `_init` routines at startup and their `_interp` routines
every time step.

## 2. `dynSubgridControlMod` — namelist and flag gating

Source: `dyn_subgrid/dynSubgridControlMod.F90`.

The derived type `dyn_subgrid_control_type`
(`dyn_subgrid/dynSubgridControlMod.F90:37-60`) stores:

| Field | Default | Purpose |
|---|---|---|
| `flanduse_timeseries` | `' '` | Path to the shared transient land-use file |
| `do_transient_pfts` | `.false.` | Read `PCT_NAT_PFT` every year |
| `do_transient_crops` | `.false.` | Read `PCT_CROP`, `PCT_CFT`, `FERTNITRO_CFT`, `FERTPHOSP_CFT` |
| `do_harvest` | `.false.` | Read the five `HARVEST_*` streams |
| `for_testing_allow_non_annual_changes` | `.false.` | Bypass the "year-boundary only" check; **testing only** |
| `for_testing_zero_dynbal_fluxes` | `.false.` | Zero water/energy correction fluxes; **breaks conservation** |
| `initialized` | `.false.` | Set to `.true.` after `dynSubgridControl_init` |

`dynSubgridControl_init(NLFilename)`
(`dyn_subgrid/dynSubgridControlMod.F90:70-93`) reads the `/dynamic_subgrid/`
namelist on the master proc, broadcasts it via MPI, and then calls
`check_namelist_consistency` (`:196-253`), which enforces rules such as:

- `do_transient_pfts` requires `flanduse_timeseries` to be set.
- `do_transient_pfts` is incompatible with `use_fates`.
- `do_transient_crops` requires `flanduse_timeseries` and is incompatible with
  `use_fates`.
- `do_harvest` requires either `use_cn` or `use_fates`.
- The `for_testing_*` flags must not be used outside test infrastructure.

A separate IAC mutual-exclusion check inside `read_namelist`
(`dyn_subgrid/dynSubgridControlMod.F90:158-169`, gated by `iac_present` from
`elm_varctl`) aborts the run if EHC is active together with any of
`do_harvest`, `do_transient_pfts`, `do_transient_crops`, or a non-empty
`flanduse_timeseries`. See `dyn_subgrid/fates_land_use_change.md` Section 2.4.

The public accessors `get_flanduse_timeseries`, `get_do_transient_pfts`,
`get_do_transient_crops`, `get_do_harvest`,
`get_for_testing_allow_non_annual_changes`, and
`get_for_testing_zero_dynbal_fluxes`
(`dyn_subgrid/dynSubgridControlMod.F90:23-30`) give the driver a read-only view
of the singleton. Note that calling `get_do_harvest()` alone is no longer
sufficient to determine whether `dynHarvest_interp_harvest_types` is invoked
in Pass B of the driver — the gate is now
`get_do_harvest() .or. fates_harvest_mode == fates_harvest_hlmlanduse`
(`dyn_subgrid/dynSubgridDriverMod.F90:120, 272`).

## 3. `dynFileMod` — a typed file handle

Source: `dyn_subgrid/dynFileMod.F90`.

```fortran
type, extends(file_desc_t) :: dyn_file_type
   type(time_info_type) :: time_info
end type dyn_file_type
```

`constructor(filename, year_position)`
(`dyn_subgrid/dynFileMod.F90:35-86`) opens the file, reads the `YEAR` variable
(which must be dimensioned by `time`), and uses it to build the `time_info`
field. `year_position` is `YEAR_POSITION_START_OF_TIMESTEP` or
`YEAR_POSITION_END_OF_TIMESTEP` and determines whether the time lookup uses
the year at the start or end of the current step.

## 4. `dynTimeInfoMod` — tracking the two-year interval

Source: `dyn_subgrid/dynTimeInfoMod.F90`.

The derived type (`dyn_subgrid/dynTimeInfoMod.F90:34-62`) holds:

```fortran
integer :: nyears
integer, allocatable :: years(:)
type(year_position_type) :: year_position    ! START or END of timestep
integer :: time_index_lower
integer :: time_index_upper
```

`set_current_year` (`dyn_subgrid/dynTimeInfoMod.F90:104-140`) uses
`get_prev_date` or `get_curr_date` from `elm_time_manager` depending on
`year_position%flag`, then calls `set_info_from_year` to position
`time_index_lower/upper` on the two-year interval that brackets the current
model year.

Edge-case logic (`dyn_subgrid/dynTimeInfoMod.F90:236-270`):

- **Before the file starts**: `time_index_lower = time_index_upper = 1` — the
  first year's weights are held constant.
- **At or after the last file year**: both indices set to `nyears` — the last
  year's weights are held constant.
- **Inside the file**: both indices set to the year-boundary pair, so
  `dyn_var_time_interp_type` can interpolate linearly.

This interval logic is what enables the "dynamic PFT period in the middle of a
simulation" pattern (`dyn_subgrid/dynTimeInfoMod.F90:227-229`): weights can be
constant before the file's first year, interpolated during it, and constant
again after the last year.

The other public methods are `set_current_year_get_year(offset)` (optional
lookahead for harvest; used at `dyn_subgrid/dynHarvestMod.F90:171`),
`set_current_year_from_year(cur_year)`, `get_time_index_lower`,
`get_time_index_upper`, `get_year(index)`, `is_within_bounds`,
`is_before_time_series`, and `is_after_time_series`. The same module is also
used by `dynFATESLandUseChangeMod` for its LUH2 file.

## 5. `dynVarTimeInterpMod` / `dynVarTimeUninterpMod`

These are `.F90.in` templates instantiated by `do_genf90` for different rank
combinations. They define:

- `dyn_var_time_interp_type` — constructs from a `dyn_file_type` + variable
  name, owns storage for "lower" and "upper" interval values, and exposes
  `get_current_data(out)` which linearly interpolates between them with respect
  to the current time.
- `dyn_var_time_uninterp_type` — same constructor but `get_current_data(out)`
  simply copies the "lower" value, so the variable jumps to its new value on
  January 1 of each year.

Both types optionally enforce that values sum to 1 per spatial point on read
(`do_check_sums_equal_1`) and apply a scalar `conversion_factor` (typically
`100.0` because the file stores percentages).

## 6. `dynpftFileMod` — natural-PFT area (`PCT_NAT_PFT`)

Source: `dyn_subgrid/dynpftFileMod.F90`.

### 6.1 `dynpft_init(bounds, dynpft_filename)` (lines 47-107)

- Asserts `maxpatch_pft == numpft + 1`; transient PFTs are not compatible with
  any other PFT layout.
- Constructs `dynpft_file` with `YEAR_POSITION_END_OF_TIMESTEP`.
- Uses `check_dim(dynpft_file, 'natpft', natpft_size)` to verify the file has
  the expected number of natural PFTs.
- Calls `dynpft_check_consistency` (`dyn_subgrid/dynpftFileMod.F90:109-182`),
  which reads the first time slice of `PCT_NAT_PFT` and compares it to the
  `wt_nat_patch` array loaded from the surface dataset. A mismatch is fatal
  unless the namelist `dynpft_consistency_checks` has
  `check_dynpft_consistency=.false.`. The error message enumerates the
  diagnostic output the user should inspect.
- Builds `wtpatch = dyn_var_time_interp_type(...)` with shape
  `[ngridcell_local, max_topounits, natpft_size]` (line 99) and
  `do_check_sums_equal_1=.true.` so that every gridcell/topounit column must
  sum to 100% natural PFT area at each input time.
- Calls `dynpft_interp(bounds)` so the initial state is correct.

### 6.2 `dynpft_interp(bounds)` (lines 241-297)

- Advances the file's `time_info` and fetches the current-time weights into
  `wtpatch_cur(:, :, natpft_lb:natpft_ub)`.
- Iterates over **every patch** in the processor bounds, filters with
  `veg_pp%is_on_soil_col(p)` (`:286`) — natural veg landunit only; crop area
  is handled by `dyncropFileMod`. The predicate replaces the older direct
  comparison `lun_pp%itype(l) == istsoil`.
- Writes `veg_pp%wtcol(p) = wtpatch_cur(g, ti, m)` where `m =
  veg_pp%itype(p)`. The topounit ordinal `ti = t - grc_pp%topi(g) + 1`
  translates the absolute topounit index into the per-gridcell index used in
  the file.

Note the comment at `dyn_subgrid/dynpftFileMod.F90:93-97`: changing the interp
type to `dyn_var_time_uninterp_type` makes PFT weights jump to their new
value on Jan 1 instead of interpolating during the year.

## 7. `dyncropFileMod` — crop area and fertilizer (`PCT_CROP`, `PCT_CFT`, `FERT*_CFT`)

Source: `dyn_subgrid/dyncropFileMod.F90`.

### 7.1 `dyncrop_init(bounds, dyncrop_filename)` (lines 50-116)

- Opens the file with `YEAR_POSITION_START_OF_TIMESTEP` — crop weights take
  effect starting on the year boundary. The comment at
  `dyn_subgrid/dyncropFileMod.F90:78-82` explains that this timing aligns with
  glacier updates and matches how prognostic crops would likely operate.
- `check_dim(dyncrop_file, 'cft', cft_size)` confirms the file's CFT axis.
- Constructs four `dyn_var_time_uninterp_type` objects:
  - `wtcrop` — `PCT_CROP`, shape `[ngridcell_local, max_topounits]`, does not
    enforce sum-to-1 because crop fraction is a standalone landunit weight.
  - `wtcft` — `PCT_CFT`, shape `[ngridcell_local, max_topounits, cft_size]`,
    enforces sum-to-1 across CFTs.
  - `nfertcft`, `pfertcft` — `FERTNITRO_CFT` and `FERTPHOSP_CFT`,
    `allow_nodata=.true.` so missing fertilizer data is tolerated.

### 7.2 `dyncrop_interp(bounds, crop_vars)` (lines 119-221)

1. Advances `dyncrop_file%time_info`.
2. Reads `wtcrop` and sets the crop landunit weight for every topounit of every
   gridcell with `set_landunit_weight(t, istcrop, wtcrop_cur(g, t2))`. Note
   that this writes the **landunit-level** weight, not a column weight.
3. Reads `wtcft`, `nfertcft`, `pfertcft`, then calls `collapse_crop_types` and
   `collapse_crop_var` from `surfrdUtilsMod` to fold pairs of managed/irrigated
   CFTs into the representation ELM uses internally.
4. Iterates over every patch, and for crop patches writes
   `col_pp%wtlunit(c) = wtcft_cur(g, ti, m)` (the per-column share of the crop
   landunit). When `use_crop=.true.`, it also fills
   `crop_vars%fertnitro_patch(p)` and `crop_vars%fertphosp_patch(p)`.
5. The `col_set` bitmask ensures that each crop column is written exactly
   once; writing twice would mean two CFTs share a column, which is
   unsupported.

## 8. `dynHarvestMod` — wood harvest streams

Source: `dyn_subgrid/dynHarvestMod.F90`.

Harvest does **not** change subgrid weights directly. Instead, it reads the
five fraction-of-vegetated-area streams `HARVEST_VH1`, `HARVEST_VH2`,
`HARVEST_SH1`, `HARVEST_SH2`, `HARVEST_SH3`
(`dyn_subgrid/dynHarvestMod.F90:71-75`) and uses them to shift mass between
live pools, product pools, and litter.

### 8.1 Module-level state

`dyn_subgrid/dynHarvestMod.F90:71-83`:

```fortran
integer, public, parameter      :: num_harvest_vars = 5
character(len=64), public, parameter :: harvest_varnames(num_harvest_vars) = &
     [character(len=64) :: 'HARVEST_VH1','HARVEST_VH2','HARVEST_SH1','HARVEST_SH2','HARVEST_SH3']
integer, public, parameter      :: wood_harvest_units = 2    ! 1 = area fraction, 2 = carbon
real(r8), allocatable, public   :: harvest_rates(:,:)        ! harvest rates
logical, public                 :: do_cn_harvest             ! whether harvest applies this period
```

Three notes:

- `do_cn_harvest` is the renamed `do_harvest` module variable (renamed and
  promoted from `private` to `public`). It is distinct from the namelist flag
  `do_harvest` accessed via `dynSubgridControlMod::get_do_harvest()`.
- `wood_harvest_units` is a `parameter` (compile-time constant), not a runtime
  toggle. It records the intended units of the carbon-vs-area-fraction harvest
  data and is set to `2` (carbon) at build time. It is **not** the runtime
  switch that selects FATES harvest behavior — that role belongs to
  `fates_harvest_mode` (see `dyn_subgrid/fates_land_use_change.md` Section
  1.3) and `landuse_harvest_units` in `dynFATESLandUseChangeMod`.
- `harvest_rates` is allocated by `dynHarvest_init` when `do_harvest` is true,
  and also by `dyn_iac_init` when `iac_present` is true and `do_harvest` is
  false (`dyn_subgrid/dynSubgridDriverMod.F90:436-444`).

### 8.2 `dynHarvest_init(bounds, harvest_filename)` (lines 89-137)

- Allocates `harvest_rates(num_harvest_vars, begg:endg)` and zeros it.
- Opens `dynHarvest_file` with `YEAR_POSITION_END_OF_TIMESTEP`.
- If `use_cn .or. use_fates`, constructs a `dyn_var_time_uninterp_type` for
  each of the five streams with `data_shape = [num_points]`.

### 8.3 `dynHarvest_interp_harvest_types(bounds)` (lines 140-195)

Runs once per year. The `set_current_year_get_year(1)` call looks one year
**forward** because input harvest data for current year are stored in year+1
on the file (`dyn_subgrid/dynHarvestMod.F90:170-171`).

Behaviour outside the time range
(`dyn_subgrid/dynHarvestMod.F90:175-194`):

- **Before the file**: `do_cn_harvest = .false.`, every rate is zero.
- **After the file**: `do_cn_harvest = .true.`, harvest rates stay at their
  last value.
- **`use_fates` override** (`dyn_subgrid/dynHarvestMod.F90:192-193`):
  ```fortran
  ! FATES does not make use of the get_do_cn_harvest mechanism.
  ! Make sure this is always false for fates runs.
  if (use_fates) do_cn_harvest = .false.
  ```
  This unconditionally disables CN-side harvest mortality whenever FATES is
  active, regardless of the namelist `do_harvest` flag and regardless of
  position in the time series. FATES instead consumes `harvest_rates(:,:)`
  through its own pathway.

The harvest rates are stored in the module-level `harvest_rates(:,:)` array.
CN code consumes them via `CNHarvest`
(`dyn_subgrid/dynHarvestMod.F90:199-497`), which:

- Selects woody PFTs using the `pftvarcon::woody(ivt(p)) == 1.0_r8` test
  (`dyn_subgrid/dynHarvestMod.F90:381`). The older test based on the
  `nbrdlf_evr_shrub` sentinel is gone; the new code imports
  `pftvarcon::woody` and treats any PFT with `woody == 1.0` as harvestable.
- Converts annual fractional rates into per-second mortality rates using
  `get_days_per_year()`.
- Moves harvested carbon, nitrogen, and phosphorus into `pprodharv10`-style
  product pools at 10-year and 100-year decay timescales (`:398-401, :430-433,
  :460-463`).
- `CNHarvestPftToColumn` (`:500-855`) aggregates the patch-level harvest
  fluxes up to the column level so biogeochemistry sees a coherent per-column
  loss term.

FATES consumes `harvest_rates` directly via its own pathway. The five
HARVEST_VH/SH categories map onto FATES's primary/secondary, forest/non-forest
land classes in the FATES boundary-condition layer.

## 9. Invocation order

`dynSubgrid_init(bounds_proc, glc2lnd_vars, crop_vars)`
(`dyn_subgrid/dynSubgridDriverMod.F90:74-154`) calls the `_init` routines
unconditionally when their flag is set, then runs one pass of `_interp` so the
cold start has a consistent set of weights:

```
if (get_do_transient_pfts())   call dynpft_init   (bounds, flanduse_timeseries)
if (get_do_harvest() .or. fates_harvest_mode == fates_harvest_hlmlanduse) &
                               call dynHarvest_init(bounds, flanduse_timeseries)
if (get_do_transient_crops())  call dyncrop_init  (bounds, flanduse_timeseries)
if (iac_present)               call dyn_iac_init  (bounds)

if (get_do_transient_pfts())   call dynpft_interp (bounds)
if (get_do_transient_crops())  call dyncrop_interp(bounds, crop_vars)

! per-clump wrap-up via dynSubgrid_wrapup_weight_changes
```

`dynSubgrid_driver` (`dyn_subgrid/dynSubgridDriverMod.F90:264-286`) runs the
`_interp` routines again at the start of each time step — outside any OMP
region because PIO reads are not thread-safe. The same Pass B block now also
calls `dynFatesLandUseInterp` (under `use_fates_luh`) and
`iac2lnd_vars%update_iac2lnd` (under `iac_present`); see
`dyn_subgrid/fates_land_use_change.md`.

The `for_testing_allow_non_annual_changes` flag is the only way to have these
routines update weights at any point other than the year boundary; they are
otherwise cheap no-ops during the other time steps of the year, because the
`time_info` object returns the same interval.

## 10. Conventions enforced by these readers

- **All `PCT_*` variables are stored as percentages** on disk; the readers
  divide by 100 via `conversion_factor`.
- **Topounit dimension ordering in the readers is
  `[gridcell, topounit, class]`.** Callers must translate the absolute
  topounit index `t` to the per-gridcell ordinal `ti = t - grc_pp%topi(g) + 1`
  before indexing into the read buffer (`dyn_subgrid/dynpftFileMod.F90:275-293`,
  `dyn_subgrid/dyncropFileMod.F90:189-214`).
- **Weights read from the file are always "relative to the parent"**:
  `PCT_NAT_PFT` is relative to the natural veg landunit, `PCT_CROP` is
  relative to the topounit, `PCT_CFT` is relative to the crop landunit. The
  primitive weights updated by the readers are therefore `veg_pp%wtcol` (for
  PFT), `lun_pp%wttopounit` (for crop landunit), and `col_pp%wtlunit` (for
  CFT).
- **Everything runs on processor-level bounds**
  (`bounds%level == BOUNDS_LEVEL_PROC` via `SHR_ASSERT`), because these files
  must be read once per MPI rank, not once per clump. The same constraint
  applies to `dynFatesLandUseInit` / `dynFatesLandUseInterp` (see
  `dyn_subgrid/fates_land_use_change.md`).
