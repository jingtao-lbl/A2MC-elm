---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `drivers/boxsbgc/` + `drivers/boxshared/ChemIDMod.F90`
**Last verified:** 2026-04-24
---

# Soil BGC Batch Driver (`boxsbgc.x`)

`boxsbgc.x` is a single-layer "box" driver for EcoSIM's soil
biogeochemistry module (`MicBGCMod`, plus the surface / dissolution
/ volatilization fluxes and the nosalt chemistry equilibria). It is the
second of the three batch harnesses in the tree (the other two being
`aquachem.x` for pure aqueous chemistry and `mock.x` as a scaffolding
template), and it is the one used for testing the microbial BGC stack in
isolation from soil-water / transport / plant physics.

## Purpose

The microbial BGC code in `f90src/Microbial_bgc/` is one of the most
numerically intensive parts of EcoSIM. When a microbial-guild parameter
or a new organic-matter pool is added, running the full column model at
a multi-day timestep to see whether things still work is expensive.
`boxsbgc.x` exists as the fast unit-test loop for that code: one
spatial "layer" (no vertical structure), one column, driven by a
NetCDF climate / soil-state forcing file. Researchers use it for:

- Diagnosing why a particular microbial flux goes to zero or blows up.
- Parameter-sweep experiments on turnover rates, temperature responses,
  or nutrient stoichiometry ceilings.
- Regression-testing the BGC pipeline against a reference history file.
- Comparing fixed-climate vs transient-climate behavior at a single
  profile without having to run the full coupled model.

## Source Files

| File | Lines | Role |
|---|---|---|
| `drivers/boxsbgc/batchsbgc.F90` | 240 | `program main` + `RunModel` — command-line, namelist, main time loop |
| `drivers/boxsbgc/batchmod.F90` | 1765 | `module batchmod` — initializer, per-step configurator, and BGC runner (by far the biggest file) |
| `drivers/boxsbgc/ChemMod.F90` | 272 | `RunModel_nosalt` + `RetrieveYstatef` for chemistry equilibrium on the single box |
| `drivers/boxsbgc/ForcTypeMod.F90` | 502 | `forc_type` — the ~200-field forcing / state container for the box. Also defines `ReadFORC` and `UpdateFORC` |
| `drivers/boxsbgc/MicIDMod.F90` | 109 | Microbial-layer `cid_*` / `fid_*` index declarations (dissolution/volatilization fluxes, ecosystem demand/uptake fluxes, gas exchange) |
| `drivers/boxshared/ChemIDMod.F90` | 392 | Chemistry state IDs shared with `aquachem.x` |

Build target: `boxsbgc.x` (`drivers/boxsbgc/CMakeLists.txt:1-8`, built
from `file(GLOB BOXSBGC_DRIVER_SOURCES "*.F90")`). Target
include-directories include both the chemistry and microbial-bgc
box-library paths (`Geochem/Box_chem`, `Microbial_bgc/Box_Micmodel`), plus
`drivers/boxshared`.

## Run Flow (`batchsbgc.F90`)

### Command-line contract

Exactly one argument, the namelist file.

```
./boxsbgc.x my_case.nml
```

Argument handling at `drivers/boxsbgc/batchsbgc.F90:17-22`. Usage string
(lines 42-43) advertises `boxsbgc.x` as a "standalone driver for ecosim
1-layer soilbgc library".

### `program main` (lines 1-33)

Standard pattern: argument check → `namelist_to_buffer` → `RunModel`.
Identical in shape to the aquachem and mockbatch drivers.

### `subroutine RunModel(namelist_buffer)` (lines 47-240)

Driver namelist at `drivers/boxsbgc/batchsbgc.F90:107-108`:

```fortran
namelist /driver_nml/ model_name, case_id, hist_freq, salton, forc_file, &
  CO2E, OXYE, Z2OE, Z2GE, ZNH3E, CH4E, H2GE, forctype, disvolonly
```

| Field | Default | Meaning |
|---|---|---|
| `model_name` | `'boxsbgc'` | Label for history file |
| `case_id` | `'exp0'` | Label for history file |
| `hist_freq` | `'day'` | History frequency |
| `salton` | `.false.` | Reserved — salt-chemistry variant is not currently used by this driver |
| `forc_file` | `'bbforc.nc'` | Path to NetCDF forcing file |
| `CO2E`, `OXYE`, `Z2OE`, `Z2GE`, `ZNH3E`, `CH4E`, `H2GE` | see lines 120-126 | Atmospheric boundary concentrations, ppmv |
| `forctype` | `0` | Mode flag: 0 = transient, 1 = T const, 2 = water const, 3 = T and water const (comment at line 105) |
| `disvolonly` | `.false.` | If `.true.`, restrict gas coupling to dissolution / volatilization (skip other gas pathways) |

Defaults are set at `batchsbgc.F90:113-127`.

After reading `driver_nml`:

1. **Solver subcycling (line 147).**
   ```
   NPH=1; NPT=15; NPG=NPT*NPH; dts_gas=1/NPG; dts_HeatWatTP=1/NPH; dt_GasCyc=1/NPT
   ```
   These are the same `EcoSIMSolverPar` globals used by the full driver
   but with a stripped-down configuration appropriate for a single box.

2. **Variable list (lines 152-155).** `nvars = getvarllen()` (no `salton`
   argument — this driver's `getvarllen` is distinct from the aquachem
   one), then allocate the list arrays and call `getvarlist(...)`.

3. **State allocation (lines 159-161).**
   `ystatesf(1,nvars)`, `ystates0l(nvars)`, `ystatesfl(nvars)`.

4. **Forcing initialization (lines 164-173).** Populate `forc%OXYE`,
   `forc%Z2GE`, etc. from the namelist values, `forc%disvolonly`, and
   then call `ReadFORC(forc, forc_file)` to load all the soil-state /
   site-attribute fields from the NetCDF file.

5. **Type-bound init (lines 175-177).**
   `call micfor%Init()`, `call micstt%Init()`, `call micflx%Init()`.
   These allocate the three microbial-side derived types
   (`micforctype`, `micsttype`, `micfluxtype`) that hold forcing, state,
   and fluxes for the microbial module.

6. **Initial condition (line 180).**
   `call initmodel(nvars, ystates0l, forc, err_status)` — populates the
   `ystates0l` vector from the forcing and the `forc_type`.

7. **Timer (line 188).** `call timer%Init(namelist_buffer=namelist_buffer)`.

8. **History init (lines 192-198).**
   Prefix `boxsbgc.<case_id>.<model_name>`, then
   `hist%init(ncols, varl, varlnml, unitl, vartypes, freql, gname, dtime)`.

9. **Main loop (lines 201-232).** Per step:
   ```
   do
     call timer%update_time_stamp()
     call UpdateFORC(forc, forctype)
     call BatchModelConfig(nvars, ystates0l, forc, micfor, micstt, micflx, err_status)
     if(err_status%check_status()) call endrun(...)
     call RunMicBGC(nvars, ystates0l, ystatesfl, forc, micfor, micstt, micflx, err_status)
     call timer%update_time_stamp()
     do jj = 1, nvars
       ystatesf(1,jj) = ystatesfl(jj)
       ystates0l(jj)  = ystatesfl(jj)
       forc%ORGC      = micfor%ORGC
     enddo
     call hist%hist_wrap(ystatesf, timer)
     if(timer%its_a_new_year()) write(iulog,*) 'year ', timer%get_curr_year()
     if(timer%its_time_to_exit()) exit
   enddo
   ```

   Note the `timer%update_time_stamp()` is called **twice** in the body
   (lines 203, 217). This is intentional: the first advances the clock
   into the current step for the forcing update; the second advances it
   again after the BGC run so that history timestamps mark the end of
   the step. The full-column driver handles this differently via the
   hour loop inside `AdvanceModelOneYear`.

10. **Shutdown (lines 233-239).** Write the restart file, call
    `micfor%destroy()`, `micflx%destroy()`, `micstt%destroy()`.

## The Engine (`batchmod`)

`drivers/boxsbgc/batchmod.F90:1-1765`. Module `batchmod`. Five public
symbols (lines 26-28):

```fortran
public :: getvarllen, getvarlist, initmodel
public :: BatchModelConfig
public :: RunMicBGC
```

### `getvarllen()` (lines 31-41)

Two side effects before counting variables:
`call micpar%Init()`, `call micpar%SetPars()` — seed the microbial
parameter object (`EcoSiMParDataMod::micpar`). Then call `Initboxbgc(nvars)`
to assign the full `cid_*` / `fid_*` set.

### `Initboxbgc(nvars)` (lines 310-505)

Registers every state and flux index the driver needs — gas-phase tracers
(`cidg_CO2`, `cidg_CH4`, `cid_OXYG`, `cid_Z2GG`, `cid_Z2OG`,
`cid_ZN3G`, `cid_H2GG`), aqueous forms (`cid_Z2GS`, `cid_ZNH3S`, `cid_ZNH3B`,
`cid_ZNH4S`, `cid_ZNH4B`, `cid_H1PO4`, `cid_H1POB`, `cid_H2PO4`, `cid_H2POB`,
`cid_ZNO2S`, `cid_ZNO2B`, `cid_CCO2S`, `cid_CNO2S`, `cid_CZ2OS`, `cid_Z2OS`,
`cid_COXYS`, `cid_OXYS`, `cid_COXYG`, etc.), dissolved / adsorbed / humus
/ microbial-residue organic pools (the `oqc_{b,e}`, `oqn_{b,e}`, `oqp_{b,e}`,
`oqa_{b,e}`, `ohc_*`, `ohn_*`, `ohp_*`, `oha_*`, `osc_*`, `osa_*`, `osn_*`,
`osp_*`, `orc_*`, `orn_*`, `orp_*` bands), and the heterotroph /
autotroph biomass bands (`mBiomeHeter_{b,e}`, `mBiomeAutor_{b,e}`).

The `_b` / `_e` suffixes denote inclusive begin / end indices for
multi-species ranges — i.e., `cid_oqc_b:cid_oqc_e` is a contiguous slice
of the `ystates0l` vector containing all dissolved-organic-C pools.

### `initmodel(nvars, ystates0l, forc, err_status)` (lines 43-94)

`use MicBGCMod, only : initNitro1Layer`. Calls into the microbial
BGC library's single-layer initializer after packing the forcing into the
canonical one-layer EcoSIM state arrays. This is the same routine the
full driver uses at `STARTS`-time for the first soil layer.

### `BatchModelConfig(nvars, ystates0l, forc, micfor, micstt, micflx, err_status)` (lines 95-309)

Per-step pre-processing. Unpacks `ystates0l` plus `forc` into
`micfor` / `micstt` / `micflx` (the derived types the microbial BGC
library expects) and primes the chemistry variables used by the
subsequent equilibria call. This is where the mapping between the flat
state vector and the rich `micforctype` / `micsttype` structure lives —
when a new BGC variable is added to the microbial library, this routine
is typically the one that needs updating.

### `UpdateStateVars(micfor, micstt, micflx, nvars, ystates0l, ystatesfl)` (lines 507-658, private)

Reverse direction. After `RunMicBGC` has updated the three microbial
type-bound objects, this helper pushes the results back into the flat
`ystatesfl` state vector so the history-file writer can pick them up.

### `getvarlist(nvars, varl, varlnml, unitl, vartypes)` (lines 659-1241)

~580 lines of `varl(i) = 'name'; varlnml(i) = 'long name'; unitl(i) = 'unit';
vartypes(i) = var_flux_type | var_state_type` assignments. Each entry
corresponds to one slot in `ystates0l` / `ystatesfl` and is the complete
list of what `boxsbgc.x` writes to its history file.

### `RunMicBGC(nvars, ystates0l, ystatesfl, forc, micfor, micstt, micflx, err_status)` (lines 1242-1280)

The one-step orchestrator. Call sequence:

1. `err_status%reset()`.
2. Per-step run of the microbial BGC library (microbial decomposition,
   growth, mortality, nitrification, denitrification).
3. `call CalcSurflux(forc, micfor, nvars, ystates0l, ystatesfl, err_status)`
   (defined at line 1281) — dissolution / volatilization fluxes at the
   soil-air interface plus gas exchange.
4. Chemistry equilibrium via `ChemMod::RunModel_nosalt(forc, micfor,
   nvars, ystates0l, ystatesfl, err_status)` (see below).
5. `call UpdateSOMORGM(micfor, micstt)` (line 1673) — roll microbial
   biomass updates into the humus / SOM bookkeeping.
6. `call UpdateStateVars(...)` — repack into `ystatesfl`.

### `CalcSurflux(forc, micfor, nvars, ystates0l, ystatesfl, err_status)` (lines 1281-1672)

By far the longest routine in the file. Computes all surface-to-soil
gas fluxes (CO2, CH4, O2, N2, N2O, NH3, H2), applies the
`disvolonly` restriction when set, and updates all the `fid_X*` gas
flux variables.

## Chemistry on the Box (`ChemMod`)

`drivers/boxsbgc/ChemMod.F90`. One public symbol: `RunModel_nosalt`
(lines 13-40).

The routine is a thin shim that:

1. Calls `SetChemVar(forc, micfor, nvars, ystates0l, chemvar)` — a
   private helper in this file (different from the aquachem driver's
   `SetChemVar`) that packs both the box forcing and the microbial
   forcing into the shared `chem_var_type`.
2. `call NoSaltChemEquilibria(0,0,0,0,0, chemvar, solflx)` — identical
   call pattern to `aquachem`: the zero arguments are the 4-D grid
   coordinates, which the equilibria solver ignores when the fifth
   argument (`L`) is zero (the "pseudo-cell" mode).
3. `call RetrieveYstatef(nvars, ystates0l, ystatesfl, chemvar, solflx)`
   — lines 45-272 of the same file. Adds `solflx%TRChem_*` fluxes to
   the state variables and updates the aqueous concentrations. This is
   where the chemistry-produced fluxes get commingled with the BGC
   state for the next time step.

## The Box Forcing Container (`ForcTypeMod`)

`drivers/boxsbgc/ForcTypeMod.F90`. Defines `forc_type` at line 16 — the
monolithic container holding everything a single-box simulation needs
that isn't already in the microbial types.

A selective inventory of its fields (`ForcTypeMod.F90:19-215`):

- **Geometry / physical.** `DLYR3` (layer thickness), `AREA3`, `BKDS`
  (bulk density), `POROS` (porosity), `SoilMicPMassLayer`, `VLSoilMicP`,
  `VLSoilPoreMicP`.
- **Hydrology.** `FieldCapacity`, `WiltPoint`, `SRP`, `LOGPSIMX`,
  `LOGPSIMND`, `LOGPSIAtSat`, `PSISD`, `PSISE`.
- **Site chemistry.** `CEC`, `XCEC`, `AEC`, `XAEC`, `CFE`, `CCA`, `CMG`,
  `CNA`, `CKA`, `CSO4`, `CCL`, `CAL`, `ZMG`, `ZNA`, `ZKA`, `pH`,
  `ATCS` (annual mean temperature), `EHUM` (humus partitioning coeff),
  `CALPO`, `CFEPO`, `CCAPD`, `CCAPH`, `CALOH`, `CFEOH`, `CCACO`,
  `CCASO`.
- **Initial / boundary state.** `ORGC` (total soil organic C), `ZNH4S`,
  `ZNO3S`, `ZNO2S`, `H2PO4`, `H1PO4`.
- **Allocatable element pools.** `ElmAllocmatMicrblitr2POM(:)`,
  `CNOSC(:,:)`, `CPOSC(:,:)`, `SolidOM(:,:,:)`, `SolidOMAct(:,:)`,
  `OMBioResdu(:,:,:)`, `SorbedOM(:,:)`, `DOM(:,:)`, `mBiomeHeter(:,:,:)`,
  `mBiomeAutor(:,:)`.

Two public routines:

- `ReadFORC(forc, fname)` (line 216) — reads all of the above from the
  `forc_file` NetCDF (default `'bbforc.nc'`). This is where the single
  layer's initial condition comes from.
- `UpdateFORC(forc, forctype)` (line 337) — per-step update. Implements
  the four `forctype` modes (transient, fixed-T, fixed-water, fixed
  both). When a field is fixed, it overrides whatever `ReadFORC` read
  from the NetCDF forcing.

## Microbial-Side IDs (`MicIDMod`)

`drivers/boxsbgc/MicIDMod.F90`. 109 lines. Unlike
`drivers/boxshared/ChemIDMod.F90`, this module is scoped to the box-BGC
driver only — it holds the microbial-specific `cid_*` and `fid_*`
indices that are not needed by `aquachem`.

Highlights:

- **Gas-phase tracer IDs** (`cidg_CO2`, `cidg_CH4`, `cid_OXYG`,
  `cid_Z2GG`, `cid_Z2OG`, `cid_ZN3G`, `cid_H2GG`, `cid_ZNH3G`).
- **Aqueous micropore species** — NH3 / NH4 / NO2 / HPO4 / H2PO4 in both
  band (`_B` suffix) and non-band forms.
- **Gas concentrations and masses** at the soil level (`cid_CCO2S`,
  `cid_CH2GS`, etc.).
- **`_b` / `_e` range markers** for DOM / sorbed / humus / microbial
  pools (`cid_oqc_b` through `cid_mBiomeAutor_e`) — these are ranges
  because the microbial library keeps multiple complexes.
- **Dissolution / volatilization flux IDs** (`fid_XCODFS`, `fid_XCHDFS`,
  `fid_XOXDFS`, `fid_XNGDFS`, `fid_XN2DFS`, `fid_XN3DFS`, `fid_XNBDFS`,
  `fid_XHGDFS`; the `DFG` and `FLG` variants for in-soil dissolution
  and gas-exchange with atmosphere).
- **Previous-step ecosystem demand / uptake flux IDs** (`fid_RO2GasXchangePrev`,
  `fid_RO2EcoDmndPrev`, `fid_RNH4EcoDmndSoilPrev`, ..., and the
  heterotrophic demand ranges `fid_RNH4DmndSoilHeter_{b,e}` etc.) —
  these carry per-step persistent demand from the microbial library for
  use in the next chemistry equilibrium.

## Differences from `aquachem.x`

Both are "batch" drivers, but they exercise different code:

| Axis | `aquachem.x` | `boxsbgc.x` |
|---|---|---|
| What is iterated | Pure aqueous-phase chemistry equilibria | Microbial BGC + surface-gas fluxes + chemistry equilibria |
| Forcing source | Hard-coded initial concentrations in `initmodel_nosalt` | NetCDF file `forc_file` (default `bbforc.nc`) read by `ReadFORC` |
| Time evolution | Only the internal relaxation of the equilibria solver | Microbial decomposition / growth / nitrification / denitrification each step |
| Salt option | Yes — branched via `salton` | `salton` namelist field exists but is not routed to a salt backend in this driver |
| Per-step size | 3 calls (SetChemVar, equilibria, RetrieveYstatef) | 6 calls (BGC run, CalcSurflux, chemistry equilibria, UpdateSOMORGM, UpdateStateVars, plus forcing update) |

## Cross-References

- Microbial BGC library: `f90src/Microbial_bgc/` and
  `f90src/Microbial_bgc/Box_Micmodel/` (the "box" variants that
  `boxsbgc.x` links against).
- Chemistry equilibria: `f90src/Geochem/Box_chem/ChemEquilibriaMod.F90`
  (same `NoSaltChemEquilibria` routine the full driver calls via
  `GeochemAPI::soluteModel`).
- Shared chemistry IDs: [`aquachem.md`](aquachem.md) covers the
  `drivers/boxshared/ChemIDMod.F90` table in more detail.
- Microbial parameters: `f90src/Modelpars/EcoSiMParDataMod.F90`
  (`micpar%Init`, `micpar%SetPars`).
- Microbial state / forcing / flux types: `f90src/Microbial_bgc/`
  (`MicForcTypeMod`, `MicStateTraitTypeMod`, `MicFLuxTypeMod`).
