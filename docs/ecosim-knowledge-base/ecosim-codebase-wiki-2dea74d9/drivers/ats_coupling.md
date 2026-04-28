---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `drivers/ATSEcoSIM/` + `f90src/ATSUtils/`
**Last verified:** 2026-04-24
---

# ATS-EcoSIM Coupling Layer

ATS (the [Advanced Terrestrial Simulator](https://amanzi.github.io/ats/))
owns the surface and subsurface flow solver in this coupling. EcoSIM is run
as a per-column biogeochemistry / surface-energy engine *driven* by ATS.
The coupling pattern is the classic operator-split one.

```
ATS owns the time loop
  for each ATS time step:
     ATS fills BGCState / BGCProperties  (water content, temperature,
                                          porosity, precipitation, ...)
     ATS calls EcoSIM_Advance(dt, props, state, sizes, ...)
        ATS2EcoSIMData(state, props, sizes)      ! pull into a_* arrays
        Run_EcoSIM_one_step(sizes)               ! run surface-balance
          SurfaceEBalance(sizes)
            RunEcoSIMSurfaceBalance(num_cols)    ! the real work
        EcoSIM2ATSData(state, sizes)             ! push back to ATS
     ATS advances flow using updated sources / sinks
```

This document covers only the *EcoSIM side* of that bridge. It is split
across two directories in the EcoSIM tree:

| Directory | Contents | Role |
|---|---|---|
| `f90src/ATSUtils/` | 8 F90 files, compiled into the `ATSUtils_mods` library | Bridge code linked into both the in-process test driver and the external ATS executable |
| `drivers/ATSEcoSIM/` | `ATSEcoSIM_test.F90` (181 lines), `CMakeLists.txt` | Standalone test harness (`ATSEcoSIM_test.x`) that fakes ATS inputs and drives the bridge in-process |

ATS internals (mesh, flow solver, state handling) are documented in the ATS
project and are out of scope here.

## The `ATS_ECOSIM` Build Flag

Defined in `CMakeLists.txt:172-229`. When set (`cmake -DATS_ECOSIM=ON ...`),
the build:

- Adds `-fPIC` to `CMAKE_CXX_FLAGS`, `CMAKE_C_FLAGS`, and
  `CMAKE_Fortran_FLAGS`, plus `-g -O0 -fbacktrace -fbounds-check` to the
  Fortran flags (`CMakeLists.txt:193-195`).
- Wires in the NetCDF, HDF5, zlib, libzip, libxml2, and libcurl paths from
  `${TPL_INSTALL_PREFIX}`, which points at the Amanzi-TPLs install that ATS
  is built against (`CMakeLists.txt:183-229`).
- Sets `ECOSIM_HAVE_NETCDF=TRUE` (`CMakeLists.txt:188`).

When `ATS_ECOSIM` is *not* set, the `ATSUtils_mods` library is still built
(it is always listed under `add_subdirectory(f90src)` in the top-level
CMake, and `f90src/ATSUtils/CMakeLists.txt:1-12` unconditionally adds the
library). The flag controls linkability into the ATS executable, not the
presence of the code.

The standalone test `ATSEcoSIM_test.x` (in `drivers/ATSEcoSIM/`) is always
built; see `drivers/ATSEcoSIM/CMakeLists.txt:7`.

## `f90src/ATSUtils/` File Map

| File | Lines | Role |
|---|---|---|
| `BGC_containers.F90` | 225 | `bind(c)` Fortran counterparts of the ATS-side `BGCState`, `BGCProperties`, `BGCSizes` structs — the wire format |
| `SharedDataMod.F90` | 209 | Module-scope `a_*` arrays that hold ATS inputs / outputs inside EcoSIM; `InitSharedData` / `DestroySharedData` |
| `c_f_interface_module.F90` | 187 | String conversion helpers between C and Fortran (adapted from Alquimia) |
| `ATSUtilsMod.F90` | 47 | Date arithmetic — `ComputeDatefromATS` (day-of-year to month / dom) |
| `ATSEcoSIMInitMod.F90` | 158 | `Init_EcoSIM_Soil` — first-time soil initialization under ATS control |
| `ATSEcoSIMAdvanceMod.F90` | 382 | `RunEcoSIMSurfaceBalance` — the per-step orchestrator |
| `ATSCPLMod.F90` | 375 | Public coupler surface: `ATS2EcoSIMData`, `EcoSIM2ATSData`, `Run_EcoSIM_one_step`, `Init_EcoSIM`, `SurfaceEBalance`, `SetBGCSizes` |
| `ecosim_wrappers.F90` | 126 | `bind(c)` wrappers `EcoSIM_Setup`, `EcoSIM_Advance`, `EcoSIM_Shutdown`, `EcoSIM_DataTest` — the actual C entry points that ATS calls |

## The C Entry Surface (`ecosim_wrappers.F90`)

All three C-callable entry points are free-standing subroutines with
`bind(C)` — they deliberately live outside any Fortran module to avoid
name-mangling conflicts between gfortran (`__modulename_MOD_procedurename`)
and intel (`_modulename_mp_procedurename_`). This is noted in the file
header (`ecosim_wrappers.F90:5-22`).

### `EcoSIM_Setup(properties, state, sizes, num_iterations, num_columns, ncells_per_col_)`

`f90src/ATSUtils/ecosim_wrappers.F90:44-70`. Called once by ATS at startup.
It does:

```
call ATS2EcoSIMData(num_columns, state, properties, sizes)   ! line 64
call Init_EcoSIM(sizes)                                      ! line 66
call EcoSIM2ATSData(num_columns, state, sizes)               ! line 68
```

That is, it pulls ATS's state and properties into the `a_*` arrays, runs
EcoSIM's first-time soil initialization, and pushes any fields back out to
ATS that EcoSIM may have changed.

### `EcoSIM_Advance(delta_t, properties, state, sizes, num_iterations, num_columns)`

`f90src/ATSUtils/ecosim_wrappers.F90:97-126`. Called once per ATS time step:

```
call ATS2EcoSIMData(num_columns, state, properties, sizes)   ! line 120
call Run_EcoSIM_one_step(sizes)                              ! line 122
call EcoSIM2ATSData(num_columns, state, sizes)               ! line 124
```

`delta_t` is declared `value, intent(in)` but is **not currently used** by
the Fortran side — the surface-balance loop inside
`RunEcoSIMSurfaceBalance` drives its own internal subcycling.

### `EcoSIM_Shutdown()`

`f90src/ATSUtils/ecosim_wrappers.F90:74-93`. Currently a no-op (the inline
comment `!For now this does nothing, but it should clear all the data
structures` tracks the intent). The active `DestroySharedData` routine
exists at `SharedDataMod.F90:174-207` but is not yet wired into this wrapper.

### `EcoSIM_DataTest()`

`f90src/ATSUtils/ecosim_wrappers.F90:33-40`. Trivial sanity-test entry that
just prints `"in the data test"`. Used to verify the C linkage during ATS
build-out.

## The Coupler Module (`ATSCPLMod`)

Defined at `f90src/ATSUtils/ATSCPLMod.F90:1-375`. Four public subroutines.

### `ATS2EcoSIMData(ncol, state, props, sizes)`

`ATSCPLMod.F90:29-240`. Converts the C-side `BGCState` / `BGCProperties`
structures (whose fields are `type(c_ptr)`) into EcoSIM's Fortran `a_*`
arrays via `c_f_pointer`. The pattern, repeated for each field, is:

```fortran
data_ptr = state%temperature%data
call c_f_pointer(data_ptr, data2D, [size_col, num_cols])
a_TEMP = data2D(:,:)
```

Field coverage (all within `ATSCPLMod.F90:61-239`):

- **2-D fields:** temperature, water_content, bulk_density,
  liquid/rock/gas densities, matric_pressure, porosity,
  hydraulic_conductivity, subsurface_water_source,
  subsurface_energy_source, depth, dz, volume, liquid_saturation,
  rooting_depth_fraction. `a_AREA3` is assigned from `props%volume`
  (line 79); `a_AreaZ(i,1) = a_Volume/a_dz` is computed in-line.
- **Per-column 1-D fields:** shortwave_radiation, longwave_radiation,
  air_temperature, vapor_pressure_air, wind_speed, aspect, LAI, SAI,
  vegetation_type, snow_albedo, column_area.
- **Atmospheric / physical scalars:** `atm_n2`, `atm_o2`, `atm_co2`,
  `atm_ch4`, `atm_n2o`, `atm_h2`, `atm_nh3`, `heat_capacity`,
  `field_capacity`, `wilting_point`, `current_day`, `current_year`, plus
  booleans `p_bool`, `a_bool`, `pheno_bool`.
- **Precipitation (branch at lines 208-217).** When `p_bool=.true.` ATS
  passes a single combined `p_total` flux and EcoSIM decides rain vs
  snow; when `p_bool=.false.` ATS supplies separate `p_rain` and
  `p_snow`. Either side can own the partitioning.
- **Surface fluxes:** surface_water_source, surface_energy_source,
  snow_depth.
- **Canopy state (pulled for restart continuity):**
  canopy_longwave_radiation, boundary_latent_heat_flux,
  boundary_sensible_heat_flux, canopy_surface_water.

### `EcoSIM2ATSData(ncol, state, sizes)`

`ATSCPLMod.F90:243-308`. The reverse direction. Writes EcoSIM-computed
quantities back into the C-side `BGCState` matrices/vectors:

- `subsurface_water_source <- a_SSWS`
- `subsurface_energy_source <- a_SSES`
- `canopy_longwave_radiation <- a_LWCan`
- `boundary_latent_heat_flux <- a_CLHF`
- `boundary_sensible_heat_flux <- a_CSHF`
- `canopy_surface_water <- a_CanopyWat`
- `transpiration <- a_Transpiration`
- `evaporation_canopy <- a_EvapCan`
- `evaporation_bare_ground <- a_EvapGrnd`
- `evaporation_litter <- a_EvapLitr`
- `evaporation_snow <- a_EvapSnow`
- `sublimation_snow <- a_Sublim`
- `surface_water_source <- surf_w_source`
- `surface_energy_source <- surf_e_source`
- `snow_depth <- surf_snow_depth`

`snow_temperature` is prepared but commented out (`ATSCPLMod.F90:264-265`).

### `Run_EcoSIM_one_step(sizes)` (ATS variant)

`ATSCPLMod.F90:312-323`. This is **not** the full-physics orchestrator from
`EcoSIMAPI.F90`. It is a thin wrapper that calls `SurfaceEBalance(sizes)`
(which calls `RunEcoSIMSurfaceBalance(num_cols)`). In the ATS coupling,
only surface energy / water is run under ATS control per step — the full
plant / microbial / chemistry stack is not invoked here. That is
consistent with the flag settings applied in `Init_EcoSIM_Soil`:
`microbial_model=.false.`, `soichem_model=.false.`, `snowRedist_model=.false.`
(`ATSEcoSIMInitMod.F90:57-60`).

### `Init_EcoSIM(sizes)` and `SurfaceEBalance(sizes)`

`ATSCPLMod.F90:326-355`. `Init_EcoSIM` calls `InitSharedData(size_col,num_cols)`
to allocate the `a_*` arrays, then `Init_EcoSIM_Soil(num_cols)` to populate
EcoSIM's soil state from the ATS-filled inputs. `SurfaceEBalance` is a
three-line trampoline to `RunEcoSIMSurfaceBalance(num_cols)`.

### `SetBGCSizes(sizes)`

`ATSCPLMod.F90:359-372`. Debug / default fill: sets
`ncells_per_col_=100`, `num_columns=1`, `num_components=1`. Used by the
standalone test harness when ATS is not present.

## Shared Data (`SharedDataMod`)

Defined at `f90src/ATSUtils/SharedDataMod.F90:1-209`. This module is the
"dock" where ATS-side inputs sit while EcoSIM is running. It is a simple
flat collection of `allocatable` arrays with `a_` prefix plus a handful of
scalars.

### Layout categories

- **Soil / column 2-D fields** `(cell, column)`
  (`SharedDataMod.F90:17-53`) — sand/silt fractions, bulk/liquid/rock
  densities, geometry (depth/volume/dz/area), FC/WP, macropore/rock
  fractions, CORGC/CORGN/CORGP, porosity, matric pressure, water
  content, saturation/permeability/hydraulic-conductivity, temperature,
  subsurface energy/water sources, snow temperature.
- **Per-column 1-D fields** (`SharedDataMod.F90:36-77`) — aspect,
  altitude, LAI/SAI, vegetation type, snow albedo, mean annual-temp
  accumulator, canopy state (LWCan, CLHF, CSHF, CanopyWat), ET and its
  components (Transpiration, EvapCan, EvapGrnd, EvapLitr, EvapSnow,
  Sublim), atmospheric driving (tairc, uwind, vpair, swrad, sunrad),
  precipitation (p_rain/p_snow/p_total), column_area, and surface
  sources (surf_e_source, surf_w_source, surf_snow_depth).
- **Column indexing** (`SharedDataMod.F90:79-83`) — `a_NU`, `a_NL`,
  `a_NJ`, `a_MaxNumRootLays_col`, `NYS`, `I`.
- **Atmospheric scalars** (`SharedDataMod.F90:15-16`) —
  `atm_{n2,o2,co2,ch4,N2o,H2,NH3}`, `heat_capacity`,
  `pressure_at_field_capacity`, `pressure_at_wilting_point`.
- **Mode flags** (`SharedDataMod.F90:85`) — `p_bool` (precipitation
  partitioning mode), `a_bool` (whether EcoSIM computes snow albedo),
  `pheno_bool` (plant / prescribed-phenology model active).

### Lifecycle routines

- `InitSharedData(ncells_per_col_, ncol)` at
  `SharedDataMod.F90:88-170`. Sets `JX=1; JY=ncol; JZ=ncells_per_col_`
  to reconfigure EcoSIM's mesh constants for the ATS column layout.
  Allocates a subset of the `a_*` arrays — note that several allocations
  are intentionally commented out because those arrays are bound in-place
  to ATS memory by `c_f_pointer` from inside `ATS2EcoSIMData` rather than
  being independently allocated here.
- `DestroySharedData()` at `SharedDataMod.F90:174-207`. Symmetric cleanup
  (calls `destroy` on each allocatable). As noted above, this is not
  currently invoked from `EcoSIM_Shutdown`.

## Soil Initialization (`ATSEcoSIMInitMod`)

`f90src/ATSUtils/ATSEcoSIMInitMod.F90:1-158`. Exports two things:

- `THETRX(:)` — a small public array with three ceiling values
  `(4.0e-6, 8.0e-6, 8.0e-6)` for the litter complexes
  (`ATSEcoSIMInitMod.F90:26-27,72-73`).
- `Init_EcoSIM_Soil(NYS)` — the first-time initialization routine.

### `Init_EcoSIM_Soil` flow (lines 31-155)

1. **Mode overrides (lines 52-63).** Force ATS-appropriate flag values:
   `ATS_cpl_mode=.true.`, `column_mode=.true.`,
   `plant_model=pheno_bool`, `ldo_sp_mode=pheno_bool`,
   `microbial_model=.false.`, `soichem_model=.false.`,
   `snowRedist_model=.false.`, `disp_planttrait=.false.`,
   `disp_modelconfig=.false.`, `mod_snow_albedo=a_bool`.
   **This is the authoritative list of what ATS coupling turns off.**

2. **Mesh and solver (lines 66-67).**
   `SetMeshATS(1,1,1,NYS)`, `set_ecosim_solver(30, 10, 20, 20)`.

3. **Allocation (lines 70-73).** Calls `InitAlloc()`, `InitUptake`, and
   allocates `THETRX`.

4. **Debug file (lines 76-78).** Opens `snow_debug.txt` for diagnostic
   writes during the snow-pack update.

5. **Topology constants (lines 80-82).** `FlowDirIndicator_col = 3`
   (no lateral flow), `MaxNumRootLays_col = 1`.

6. **Per-column copy (lines 89-142).** For each of `NY = 1..NYS` copies
   the relevant `a_*` values into EcoSIM's canonical per-column arrays
   (`NU_col`, `NL_col`, `ASP_col`, `TairK_col`, `VPK_col`, `VPA_col`,
   `WindSpeedAtm_col`, `POROS0_col`, `VGeomLayer_vr`, plus per-layer
   `TKSoil1_vr`, `CumDepz2LayBottom_vr`, `POROS_vr`, `AREA_3D(3,...)`,
   `SoiBulkDensityt0_vr`, `SoilBulkDensity_vr`, `SoilFracAsMicP_vr`,
   `CSoilOrgM_vr(ielmc/ielmn/ielmp, ...)`, `DH_col`, `DV_col`). Note
   the unit conversions: vapor pressure is divided by `1.0e3` to get
   kPa; bulk density is divided by `1.0e3` to convert kg/m^3 → Mg/m^3.

7. **Field-capacity / wilt-point (lines 144-145).**
   `PSIAtFldCapacity_col = pressure_at_field_capacity`,
   `PSIAtWiltPoint_col = pressure_at_wilting_point`.

8. **`startsim` call (line 147).** Hands off to EcoSIM's standard
   `starts` / `startq` machinery.

9. **Area patch-up (lines 149-153).** Overwrites `AREA_3D(3,L,NY,NX)` with
   `a_AREA3(L,NY)` after `startsim`, since `startsim` rewrites the area
   field internally.

## Per-Step Orchestrator (`ATSEcoSIMAdvanceMod`)

`f90src/ATSUtils/ATSEcoSIMAdvanceMod.F90:1-382`. Exports one public
subroutine, `RunEcoSIMSurfaceBalance(NYS)` (lines 45-380). This is the
per-step workhorse called on every ATS advance.

Flow:

1. **Date arithmetic (line 102).** `ComputeDatefromATS(current_day,
   current_year, current_month, day_of_month, total_days_in_month)`. Uses
   `current_day` and `current_year` scalars that `ATS2EcoSIMData` pulled
   from `props%current_day` / `props%current_year`.
2. **Build `yearIJ` (lines 107-109).** `yearIJ%year=current_year`,
   `yearIJ%J=12` (fixed noon), `yearIJ%I=current_day+1`.
3. **Mesh / column setup (line 111).** `SetMeshATS(NHW,NVN,NHE,NVS)`.
4. **Per-column clear (lines 116-124).** Zero transient accumulators and
   set `Myco_pft(1,NY,NX)=1`, `NP0_col=1`.
5. **Hourly weather prep (line 127).** `PrepHourlyWeather(I,J,NHW,NHE,NVN,NVS)`.
6. **Main per-column loop (lines 128-284).** For each column: copy
   surface forcing into canonical arrays with unit conversions
   (`uwind*3600` m/s → m/hr, `swrad*0.0036` W/m^2 → MJ/m^2/hr,
   `vpair/1e3` Pa → kPa; lines 141-155), compute sky long-wave with
   `EMM=0.684` and the Stefan-Boltzmann constant (lines 158-161), and
   then per soil layer derive auxiliary quantities — water volume from
   mol to m^3 (`VLWatMicP1_vr = a_WC/(a_LDENS*AREA_3D)`, line 174),
   matric pressure Pa → MPa (`PSISM1_vr = a_MATP/1e6`, line 181). A
   hard-coded `HYCDMicP4RootUptake_vr = 0.000571` sits at line 195 as a
   temporary placeholder pending a proper exchange with the ATS
   water-retention model. Precipitation partitioning (lines 250-261)
   branches on `p_bool` identically to the forward translator. Phenology
   setup at lines 272-282 sets `CanopyHeight_col=17.0`, `LAI_col=a_LAI`,
   `irootType_col=a_VEG`, and fills `NP0_col` according to
   `irootType_col`.
7. **Prescribed phenology (lines 286, 294-298).** When `ldo_sp_mode` is
   on, calls `PrescribePhenologyInterp(I,NHW,NHE,NVN,NVS)` then
   `PlantCanopyRadsModel` per column.
8. **Field-capacity / wilt-point (lines 300-301).** Refresh each step
   (ATS could update these).
9. **Surface-physics stage (line 303).**
   `StageSurfacePhysModel(I,J,NHW,NHE,NVN,NVS,ResistanceLitRLay)`.
10. **Subcycled surface-physics loop (lines 317-338).** `DO M=1,NPH`:
    - `RunSurfacePhysModelM(I,J,M,...)` — the inner surface energy /
      water kernel.
    - Accumulate `HeatFlx2Grnd_col += HeatInfl2Soil` and
      `Qinflx2Soil_col += Qinfl2MicP_col`.
    - `UpdateSurfaceAtM(I,J,M,...)`.
11. **Snow update (lines 339-341).** `SnowMassUpdate(I,J,NY,NX,...)` per
    column.
12. **Plant model (line 343).** When `ldo_sp_mode` is on,
    `PlantModel(yearIJ, NHW,NHE,NVN,NVS)` is called. This is the *full*
    `PlantModel` from `f90src/Plant_bgc/`, not a stub.
13. **Push results back to `a_*` arrays (lines 345-376).** Per column,
    convert accumulated fluxes back to ATS units by dividing by
    `dts_HeatWatTP` (subcycle length), and populate `surf_e_source`,
    `surf_w_source`, `surf_snow_depth`, `a_LWCan`, `a_CLHF`, `a_CSHF`,
    `a_CanopyWat`, `a_ET`, `a_Transpiration`, `a_EvapCan`, `a_EvapGrnd`,
    `a_EvapLitr`, `a_EvapSnow`, `a_Sublim`. Per-layer root water
    uptake is pushed into `a_SSWS` at line 374.

## Date Arithmetic (`ATSUtilsMod`)

`f90src/ATSUtils/ATSUtilsMod.F90:1-47`. One public routine,
`ComputeDatefromATS(current_day, current_year, current_month, day_of_month,
total_days_in_month)` (lines 17-46).

Given a zero-based day-of-year (0..364) and a year, returns the calendar
month, day-of-month, and total days in that month using a fixed
`days_in_month(12) = [31,28,31,30,31,30,31,31,30,31,30,31]` table. Note
that the leap-year check is **commented out** (`ATSUtilsMod.F90:29`),
so `is_leap` is always its uninitialized default. In practice this
matches EcoSIM's own no-leap-year convention used elsewhere in the code.

## C Containers (`BGC_containers.F90`)

`f90src/ATSUtils/BGC_containers.F90:1-225`. Defines the wire format as a
set of `bind(c)` Fortran derived types that mirror C structs. Adapted from
Alquimia (credits at lines 1-29).

Container primitives at lines 77-137: `BGCVectorDouble` / `BGCVectorInt` /
`BGCVectorString` (1-D), `BGCMatrixDouble` / `BGCMatrixInt` /
`BGCMatrixString` (2-D), and `BGCTensorDouble` / `BGCTensorInt` (3-D, with
a `procs` axis). Every primitive carries explicit `size` / `capacity` /
`cap_*` ints plus a single `type(c_ptr) :: data` payload.

Three payload types built from those primitives:

- `BGCSizes` (line 139) — `ncells_per_col_`, `num_components`, `num_columns`.
- `BGCState` (line 145) — the per-step *dynamic* data ATS owns. 14
  `BGCMatrixDouble` fields (liquid / gas / ice / rock density, porosity,
  water_content, matric_pressure, temperature, hydraulic_conductivity,
  bulk_density, subsurface_water_source, subsurface_energy_source,
  snow_temperature), one `BGCTensorDouble` (total_component_concentration),
  and a dozen `BGCVectorDouble` surface-flux fields (surface_*_source,
  snow_depth, canopy_longwave_radiation, boundary_latent_heat_flux,
  boundary_sensible_heat_flux, canopy_surface_water, transpiration, four
  evaporation_* fields, sublimation_snow). This list must stay in sync
  with the fields consumed by `ATS2EcoSIMData` and produced by
  `EcoSIM2ATSData` (see tables above).
- `BGCProperties` (line 176) — mostly *static* site data. Matrix fields
  (liquid_saturation, gas_saturation, ice_saturation,
  relative_permeability, thermal_conductivity, volume, depth, depth_c,
  dz, plant_wilting_factor, rooting_depth_fraction), vector fields
  (column_area, shortwave_radiation, longwave_radiation, air_temperature,
  vapor_pressure_air, wind_speed, precipitation, precipitation_snow,
  elevation, aspect, slope, LAI, SAI, vegetation_type, snow_albedo), plus
  scalar atmospheric composition (`atm_n2` ... `atm_nh3`),
  `heat_capacity`, `field_capacity`, `wilting_point`, `current_day`,
  `current_year`, and the three `logical(c_bool)` flags `p_bool`,
  `a_bool`, `pheno_bool`.
- `BGCAuxiliaryData` (line 220) — generic `aux_ints` / `aux_doubles`
  reserved for future use.

**API stability warning (file header, lines 37-50):** the field order of
these types is part of the API. Changing the order, renaming fields, or
inserting fields breaks the C side. Add new fields only at the end, and
mirror every change on the C side of the bridge.

## C-Fortran String Helpers (`c_f_interface_module.F90`)

`f90src/ATSUtils/c_f_interface_module.F90:1-187`. Adapted from Alquimia.
Four public routines: `c_f_string_ptr` (lines 49-72), `c_f_string_chars`
(lines 74-91), `f_c_string_ptr` (lines 93-117), `f_c_string_chars` (lines
119-139), plus a convenience `CaseInsensitiveStrcmp` (lines 142-173) that
uses the private `To_lower` (lines 176-185).

These exist because the ATS side passes strings (constraint names,
component names) as null-terminated `char*` and Fortran wants fixed-length
character arrays. Not heavily exercised in the current wrapper set — only
a small number of constraint-name constants are defined in
`BGC_containers.F90:68-75`
(`kBGCStringTotalAqueous`, `kBGCStringTotalSorbed`, etc.) — but kept as
groundwork for future constraint-driven coupling.

## The Standalone Test Driver (`drivers/ATSEcoSIM/`)

`drivers/ATSEcoSIM/ATSEcoSIM_test.F90` (181 lines) is a *Fortran*
program that fakes ATS by manually allocating the `a_*` arrays and
stuffing them with synthetic values.

### `program EcoATSTest` (lines 1-47)

1. Declare local `BGCState`, `BGCProperties`, `BGCSizes` (unused except
   for `sizes`).
2. Set `NX=1; NYS=1; ncells_per_col_=100; ncol=1`
   (lines 21-24).
3. Set `sizes%num_components=1; sizes%ncells_per_col_=100;
   sizes%num_columns=1` (lines 27-29).
4. Set `a_bool=.false.; pheno_bool=.true.` (lines 30-31).
5. `call Init_ATSEcoSIM_driver()` (line 32) — local subroutine that fakes
   the `a_*` fields.
6. `call Init_EcoSIM(sizes)` (line 34) — calls into
   `ATSCPLMod::Init_EcoSIM`, which calls `InitSharedData` and then
   `Init_EcoSIM_Soil(1)`.
7. Six-step rain experiment: loops over a fixed
   `rain_array = (/1.0e-3, ..., 1.0e-3/)`, setting
   `p_rain(NY)=rain_array(ii)` each step and calling
   `Run_EcoSIM_one_step(sizes)` (lines 36-45).

### `subroutine Init_ATSEcoSIM_driver` (lines 51-181)

Allocates all of the `a_*` arrays that would normally be bound by
`c_f_pointer` from the ATS side (lines 104-139), then populates them
with representative values (lines 141-179) — a bulk density of 1100 kg/m^3,
a matric pressure of -6.9, porosity 0.5, `a_TEMP=242.00` K (very cold),
LAI=0.2, SAI=0.05, and so on.

> The fake values set here should not be treated as defaults. They exist
> only to let the Fortran test harness run without ATS. Real couplings
> always receive these values from ATS via `ATS2EcoSIMData`.

### `drivers/ATSEcoSIM/CMakeLists.txt`

Produces the `ATSEcoSIM_test.x` executable by linking against
`ATSUtils_mods` and `Ecosim_datatype` (lines 9-12).

## Confusable Names — Reference

Because `Run_EcoSIM_one_step` is reused as a subroutine name in two
different modules, it is worth laying out the distinction:

| Name | Module | File:line | What it does |
|---|---|---|---|
| `Run_EcoSIM_one_step` | `EcoSIMAPI` (module-private) | `drivers/ecosim/EcoSIMAPI.F90:35` | Full hourly physics sequence (HOUR1, WATSUB, MicrobeModel, PlantModel, soluteModel, TranspNoSalt, TranspSalt, EROSION, REDIST, balances) |
| `Run_EcoSIM_one_step` | `ATSCPLMod` (public) | `f90src/ATSUtils/ATSCPLMod.F90:312` | Surface-balance-only wrapper; delegates to `SurfaceEBalance` → `RunEcoSIMSurfaceBalance` |

Similarly there are two `SetChemVar`-style routines — one in
`AquachemMod`, one in `AquaSaltChemMod` — but those are in the aquachem
driver and are not part of this coupling.

## Cross-References

- ATS project documentation (outside this tree) for `BGCState` /
  `BGCProperties` semantics as owned by ATS.
- EcoSIM full-driver API: [`ecosim_main.md`](ecosim_main.md).
- Physics routines called from the ATS path (`StageSurfacePhysModel`,
  `RunSurfacePhysModelM`, `UpdateSurfaceAtM`, `SnowMassUpdate`,
  `PrescribePhenologyInterp`, `PlantCanopyRadsModel`, `PlantModel`) are
  documented under `hydrotherm/surf_phys/`, `hydrotherm/snow_phys/`,
  `plant_bgc/`, and `plant_bgc/prescribed_pheno/` in this wiki.
