---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `drivers/aquachem/` (+ shared ID tables in `drivers/boxshared/ChemIDMod.F90`)
**Last verified:** 2026-04-24
---

# Aquachem Batch Driver

`aquachem.x` is the standalone batch driver for EcoSIM's aqueous-phase
chemical-equilibria solver. It exercises the solute chemistry code
(`ChemEquilibriaMod::NoSaltChemEquilibria`,
`SaltChemEquilibriaMod::SaltChemEquilibria`) on a single virtual soil
layer without running any of the flow, transport, or plant / microbial
models.

## Purpose — Why This Driver Exists

The chemistry solver in `f90src/Geochem/Box_chem/` is large (several
hundred species / reactions), numerically stiff, and sits on the hot path
of every soil-chemistry step. When the chemistry code is modified — for
example adding a new sorbed species, fixing a reaction rate, or debugging
a pH drift — rebuilding the entire coupled model and running a multi-year
site simulation to see whether the change broke something is expensive
and slow. `aquachem.x` is the fast-feedback unit harness for that
workflow.

In concrete terms, it is used to:

- Verify that the no-salt chemistry equilibrium iterates to a sensible
  steady state from a canonical initial condition.
- Verify that the salt chemistry variant (`salton=.true.`) converges when
  the large extra set of Na, K, Ca, Mg, Cl, SO4 species is enabled.
- Regenerate the chemistry regression history file that the regression
  tests under `regression-tests/` compare against.

## Source Files

| File | Lines | Role |
|---|---|---|
| `drivers/aquachem/aquachem.F90` | 173 | `program main`, command-line + namelist dispatch, history loop |
| `drivers/aquachem/AquachemMod.F90` | 443 | Front-door module — `getvarllen`, `getvarlist`, `initmodel`, `Runchem`; branches to nosalt or salt backends |
| `drivers/aquachem/AquaSaltChemMod.F90` | 1003 | Salt-chemistry variant — extended state IDs, initializer, and runner |
| `drivers/boxshared/ChemIDMod.F90` | 392 | Shared chemical-state ID table (`cid_*` and `fid_*`) used by both the nosalt and salt paths |

Build target: `aquachem.x` (`drivers/aquachem/CMakeLists.txt:1-15`, built
from `file(GLOB AQUACHEM_DRIVER_SOURCES "*.F90")`).

## Run Flow (`aquachem.F90`)

### Command-line contract

Exactly one argument: the namelist file path.

```
./aquachem.x my_case.nml
```

Arg count validation at `drivers/aquachem/aquachem.F90:13-18`; the
`usage()` subroutine at lines 34-41 prints:

```
aquachem.x - standalone driver for aquachem
usage: aquachem.x namelist_filename
```

### `program main` (lines 1-29)

1. `command_argument_count()` check.
2. `get_command_argument(1, namelist_filename)`.
3. `namelist_to_buffer(namelist_filename, namelist_buffer)` — read the
   file into an in-memory buffer (same helper used by the full driver).
4. `call RunModel(namelist_buffer)`.

### `subroutine RunModel(namelist_buffer)` (lines 46-173)

The driver-namelist group is `driver_nml` with fields:

```fortran
namelist /driver_nml/ model_name, case_id, hist_freq, salton
```

declared at line 81. Defaults (lines 84-87):

| Field | Default | Meaning |
|---|---|---|
| `model_name` | `'mock'` | Used only as a label in the history filename |
| `case_id` | `'exp0'` | Used only as a label in the history filename |
| `hist_freq` | `'day'` | History output frequency |
| `salton` | `.false.` | If `.true.`, activate the salt-chemistry variant |

After reading the namelist, the driver proceeds:

1. **Build the variable list (lines 104-110).**
   `nvars = getvarllen(salton)`. Then allocate `varl`, `varlnml`, `unitl`,
   `freql`, `vartypes` of that length and call `getvarlist(..., salton)`.
2. **Allocate state vectors (lines 115-117).**
   `ystatesf(ncols, nvars)` — the per-step history snapshot (`ncols=1`).
   `ystates0l(nvars)` — current state. `ystatesfl(nvars)` — next state.
3. **Initial condition (line 120).**
   `call initmodel(nvars, ystates0l, salton, err_status)`.
4. **Timer (line 128).** `timer%Init(namelist_buffer=namelist_buffer)`.
   `dtime = timer%get_step_size()`.
5. **History-file name (lines 132-142).**
   If `salton`, prefix is `aquachem.salt`; otherwise `aquachem.nosalt`.
   Full name: `<prefix>.<case_id>.<model_name>`.
6. **Main loop (lines 144-168).**
   ```
   do
     call timer%update_time_stamp()
     call Runchem(nvars, ystates0l, ystatesfl, err_status, salton)
     if(err_status%check_status()) call endrun(...)
     do jj = 1, nvars
       ystatesf(1,jj) = ystatesfl(jj)
       ystates0l(jj)  = ystatesfl(jj)    ! persist state into next step
     enddo
     call hist%hist_wrap(ystatesf, timer)
     if(timer%its_a_new_year()) write(iulog,*) 'year ', timer%get_curr_year()
     if(timer%its_time_to_exit()) exit
   enddo
   ```
7. **Restart write (line 171).**
   `hist%histrst('aquachem.x', 'write', yymmddhhss)`.

## `AquachemMod` — The Front Door

`drivers/aquachem/AquachemMod.F90`. Declares the public API that the
program calls:

```fortran
public :: getvarllen   ! function (line 19)
public :: getvarlist   ! subroutine (line 104)
public :: initmodel    ! subroutine (line 125)
public :: runchem      ! subroutine (line 193)
```

### `getvarllen(salton) → nvars` (lines 19-29)

Dispatch function. If `salton`, calls `Init_geochem_salt(nvars)` (defined
in `AquaSaltChemMod`). Otherwise calls `Init_geochem_nosalt(nvars)`
(lines 34-103 of this file). In both cases the callee populates the
global `cid_*` / `fid_*` indices defined in `ChemIDMod` (the shared
table) and returns the total count as `nvars`.

### `Init_geochem_nosalt(nvars)` (lines 34-102)

Calls `addone(itemp)` for each of ~45 state variables (NH4, NH3, H1PO4,
H2PO4, exchangeable XNH4, exchangeable XROH{1,2} / XH2PO4 / XHPO4 non-band
and band forms, the AlPO4, CaHPO4, Ca5P3O12O3H3, CaH4P2O8, FePO4
precipitates — all in non-band and band variants) and then ~20 flux IDs
(`fid_TRChem_NH4_soil`, `fid_TRChem_NH3_soil`, etc.) and finally writes
the count into `nvars`. The `addone` helper (from `MiniMathMod`) simply
increments `itemp` and returns the pre-increment value, so the `cid_` /
`fid_` indices are assigned in declaration order.

### `initmodel(nvars, ystatesfl, salton, err_status)` (lines 125-140)

Dispatches to `initmodel_salt` or `initmodel_nosalt`. The nosalt initial
condition is hard-coded (lines 145-190) — fixed concentrations for
H1PO4, H2PO4, NH3, NH4, plus initial precipitate masses. These values
are fixed initial conditions for the harness; real runs would load them
from a site file.

### `Runchem(nvars, ystates0l, ystatesfl, err_status, salton)` (lines 193-211)

Dispatches to `RunModel_salt` or `RunModel_nosalt`. Both follow the same
three-step pattern:

1. `SetChemVar(nvars, ystates0l, chemvar)` — pack the flat `ystates0l`
   into a `chem_var_type` derived type.
2. `NoSaltChemEquilibria(0,0,0,0,0, chemvar, solflx)` **or**
   `SaltChemEquilibria(chemvar, solflx)` — the actual equilibria solver
   from `f90src/Geochem/Box_chem/`.
3. `RetrieveYstatef(nvars, ystates0l, ystatesfl, chemvar, solflx)` —
   unpack back into the flat state vector and add the computed fluxes.

The nosalt path calls `NoSaltChemEquilibria` with five zero position
arguments (line 233). This is deliberate — the equilibria solver is
written to be callable from any location in the 4-D grid; here we
simulate the `(0,0,0,0,0)` pseudo-cell.

## Salt Chemistry (`AquaSaltChemMod`)

`drivers/aquachem/AquaSaltChemMod.F90`. 1003 lines, most of it ID
registration and the list of history variables exposed in salt mode.
Four public symbols:

```fortran
public :: Init_geochem_salt     ! line 57, registers extra cid_*/fid_*
public :: getvarlist_salt       ! line 263, populates varl / varlnml / etc.
public :: initmodel_salt        ! line 47, mostly a no-op (line 54)
public :: RunModel_salt         ! line 19, chemvar → SaltChemEquilibria → ystatesfl
```

When `salton=.true.` the front door in `AquachemMod` routes all calls
through this module, which adds the full set of Na, K, Ca, Mg, Al, Fe,
Cl, SO4, HCO3, CO3, OH, H+ species on top of the nosalt base.

Note: `initmodel_salt` (lines 47-55) is currently a bare stub that
returns `err_status%reset()` and leaves `ystatesfl` untouched. This is
consistent with the fact that the shared initial condition is assumed to
be set elsewhere; users of `salton=.true.` need to be aware that the
harness does not seed the salt state for them.

## Shared Chemistry IDs (`drivers/boxshared/ChemIDMod.F90`)

`drivers/boxshared/ChemIDMod.F90`. 392 lines. Declares the entire
`cid_*` / `fid_*` integer lookup table used by `AquachemMod`,
`AquaSaltChemMod`, `boxsbgc/ChemMod.F90`, and the main chemistry
library. Examples from the head of the file (lines 9-50):

```fortran
integer :: cid_CO2S                         ! aqueous CO2 micropore [g d-2]
integer :: cid_H1PO4_2e_aque_mole_conc      ! HPO4^2- concentration [mol m-3]
integer :: cid_H2PO4_1e_aque_mole_conc      ! H2PO4- concentration [mol m-3]
integer :: cid_NH3_aque_mole_conc           ! NH3 concentration [mol m-3]
integer :: cid_NH4_1p_aque_mole_conc        ! NH4+ concentration [mol m-3]
integer :: cid_ZNO3S                        ! NO3 mass non-band micropore [g d-2]
...
```

These integers are **not set by the module itself** — they are `save`
variables that get populated at runtime by the various
`Init_geochem_*` / `Initboxbgc` routines, which call `addone(itemp)`
against a local counter. The contract is: the `cid_*` value is the index
into the flat `ystates0l(1:nvars)` vector where that species' state
lives.

Because this table is shared between `aquachem` and `boxsbgc`, both
drivers see the same name space for solute IDs, and the compiled library
`boxshared` (see `drivers/boxshared/CMakeLists.txt`) is linked into both
targets.

## How Aquachem Differs from the Full EcoSIM Driver

At the level of numerics:

- No flow, no transport, no heat, no plants, no microbes. Only the
  *chemistry equilibrium* is iterated. Species with transport-dependent
  dynamics (e.g., NO3 leaching) do not move in `aquachem`.
- The "column" is a single virtual box with no layer structure. State is
  a flat `ystatesfl(1:nvars)` vector; there is no `(L,NY,NX)` indexing.
- The rain / irrigation / fertilizer inputs that drive real soil
  chemistry are replaced by the hard-coded initial state in
  `initmodel_nosalt`. Time-evolution within a run is limited to the
  internal dynamics of the equilibria solver itself.

At the level of code structure:

- No `EcoSIMAPI`, no `AdvanceModelOneYear`, no hourly loop. Just a flat
  `do ... enddo` driven by `ecosim_time_type::its_time_to_exit`.
- No mesh (`SetMesh`), no site file, no climate forcing NetCDF. The only
  configuration is `driver_nml`.
- History is written through the same `histf_type` / `bhistMod` path as
  the main driver. This is deliberate — regression comparisons use the
  same history format across all drivers.

## Namelist Reference

The complete driver-side namelist for `aquachem.x`:

```fortran
namelist /driver_nml/ model_name, case_id, hist_freq, salton
```

Nothing else in the `aquachem.F90` top level reads from any other
namelist group. However, `timer%Init(namelist_buffer=namelist_buffer)`
(called at line 128) reads its own `ecosim_time_nml` group from the
buffer — see `f90src/Utils/ecosim_Time_Mod.F90` for its fields
(`ecosim_time_step`, `ecosim_nyears`, etc.).

## Cross-References

- Chemistry equilibria solvers: `f90src/Geochem/Box_chem/` —
  `ChemEquilibriaMod::NoSaltChemEquilibria`,
  `SaltChemEquilibriaMod::SaltChemEquilibria`. These are the same
  routines called from the full driver at
  `drivers/ecosim/EcoSIMAPI.F90:78` (inside `Run_EcoSIM_one_step`), via
  the `GeochemAPI::soluteModel` wrapper.
- Solute state / flux containers: `f90src/Geochem/.../SoluteChemDataType.F90`
  (defines `chem_var_type`, `solute_flx_type`).
- Timing: `f90src/Utils/ecosim_Time_Mod.F90`.
- History: `f90src/IOutils/bhistMod.F90`.
