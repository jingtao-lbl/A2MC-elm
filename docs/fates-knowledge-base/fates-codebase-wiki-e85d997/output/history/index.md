# History Output System

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `main/FatesHistoryInterfaceMod.F90`
- `main/FatesHistoryVariableType.F90`
- `main/FatesIODimensionsMod.F90`
- `main/FatesIOVariableKindMod.F90`
- `main/FatesInterfaceMod.F90`
- `main/FatesInterfaceTypesMod.F90`

## Purpose and Scope

The History Output System manages the definition, registration, accumulation, and flushing of FATES diagnostic variables. Because FATES organizes vegetation hierarchically (sites → patches → cohorts) and its patches and cohorts are born and die continuously, the output system has to bin continuous cohort attributes (DBH, age) into discrete classes and aggregate per-plant quantities into per-site arrays that can be written into a rectangular NetCDF file.

Related topics:

- [History Update Pipeline](pipeline.md) — where and how each update routine is called
- [History Variables and Dimensions](variables.md) — dimension kinds and multiplexed dimensions
- [Restart System](../restart.md) — the separate pipeline for state serialization
- [Mass Balance Checking](../mass_balance.md) — conservation enforcement

## Architecture

The system lives in `main/FatesHistoryInterfaceMod.F90` and centers on the type `fates_history_interface_type`, with a global instance `fates_hist`. It manages:

- An `hvars(:)` array of history variable objects of type `fates_history_variable_type` (defined in `main/FatesHistoryVariableType.F90`), each carrying `vname`, `long_name`, `units`, `avgflag`, `vtype`, `flushval`, `upfreq`, and one or more data buffers.
- A `dim_kinds(:)` registry of dimension-kind objects (sized to `fates_history_num_dim_kinds = 50`).
- A `dim_bounds(:)` registry of per-thread dimension bounds (sized to `fates_history_num_dimensions = 50`).
- A set of integer indices into `dim_bounds`, one per dimension (e.g., `column_index_`, `levscpf_index_`, `levpft_index_`).

Sources: `(main/FatesHistoryInterfaceMod.F90:743-862)`

## Initialization, Runtime, Flushing

The system moves through three phases:

1. **Initialization.** `define_history_vars` (called from `initialize_history_vars`) invokes `set_history_var` hundreds of times, once per `FATES_*` variable, to register the variable's metadata, look up its dimension kind via `iotype_index`, allocate its data buffer, and stamp its integer index (e.g., `ih_leafc_pf`) into a module-level variable. There are 479 such registrations in `e85d997`.
2. **Runtime.** Four update routines (`update_history_dyn`, `update_history_hifrq`, `update_history_hydraulics`, `update_history_nutrflux`) walk the site/patch/cohort hierarchy and accumulate data into the registered variables. See [History Update Pipeline](pipeline.md) for details on when each is called.
3. **Flushing.** At the end of each host-model history interval, `flush_hvars` copies the accumulated buffers into the host's I/O arrays and `zero_site_hvars` resets the buffers using each variable's `flushval`.

Sources: `(main/FatesHistoryInterfaceMod.F90:777-862, 1144-1260)`

## Dimension Registry

FATES tracks output across multiple axes. Each base dimension and each multiplexed dimension is registered once into the `dim_bounds` array during initialization, and a dedicated getter method returns its index:

| Dimension | Getter | Axis |
|---|---|---|
| `column` | `column_index()` | Site / gridcell |
| `levsoil` | `levsoil_index()` | Soil layer |
| `levpft` | `levpft_index()` | Plant functional type |
| `levscls` | `levscls_index()` | Cohort size class |
| `levage` | `levage_index()` | Patch age class |
| `levcoage` | — | Cohort age class |
| `levcan` | — | Canopy layer (`nclmax`, typically 2) |
| `levleaf` | — | Leaf layer |
| `levcwdsc` | — | CWD size class |
| `levfuel` | — | Fuel size class |
| `levheight` | — | Height bin |
| `levelem` | — | Chemical element (C, N, P) |
| `levdamage` | — | Crown damage class |
| `levscpf` | `levscpf_index()` | Size × PFT (multiplexed) |
| `levscag` | `levscag_index()` | Size × patch age (multiplexed) |
| `levscagpft` | `levscagpft_index()` | Size × age × PFT (multiplexed) |
| `levagepft` | — | Age × PFT (multiplexed) |
| `levagefuel` | — | Age × fuel size (multiplexed) |
| `levcnlf` | — | Canopy layer × leaf layer |
| `levcnlfpft` | — | Canopy × leaf × PFT |
| `levcdpf` | — | Size × damage × PFT (3D, not 2D) |
| `levelcwd` | — | Element × CWD |
| `levelpft` | — | Element × PFT |

Note: `levcdpf` is three-dimensional (`nlevsclass × nlevdamage × numpft`), not two-dimensional. See [History Variables and Dimensions](variables.md) for the full dimension-kind table, including the `dimsize` values used for allocation.

Sources: `(main/FatesHistoryInterfaceMod.F90:134-152, 869-1260)`, `(main/FatesInterfaceMod.F90:1168-1170)`

## Variable Indexing (`ih_*`)

Each history variable receives a module-level integer index of the form `ih_<name>_<dim_suffix>` (e.g., `ih_nplant_si_scpf`, `ih_leafc_pf`, `ih_parsun_z_si_cllllpft`). These indices are set during registration and are used at runtime to access variables without string lookups. They are **not** the user-facing output variable names.

User-facing output names are the `vname=` strings passed to `set_history_var` and follow a distinct convention using suffixes like `_SZPF`, `_PF`, `_CLLL`, `_CLLLPF`. For example, the internal index `ih_nplant_si_scpf` is attached to the output variable whose `vname` is `FATES_NPLANT_SZPF`. A user grepping a NetCDF history file for `FATES_NPLANT_SCPF` will find nothing — the actual output name is `FATES_NPLANT_SZPF`.

Sources: `(main/FatesHistoryInterfaceMod.F90:174-740, 7077)`

## Variable Registration Call Pattern

Every history variable is registered with a call structurally like:

```fortran
call this%set_history_var(                           &
     vname='FATES_LEAFC_SZPF',                       &
     units='kg m-2',                                 &
     long='leaf biomass by size class and PFT',      &
     use_default='active',                           &
     avgflag='A',                                    &
     vtype=site_size_pft_r8,                         &
     hlms='CLM:ALM',                                 &
     upfreq=1,                                       &
     ivar=ivar, initialize=initialize_variables,     &
     index=ih_leafc_si_scpf)
```

Fields:

- `vname` — User-facing NetCDF variable name.
- `units` — Unit string (SI units; `kg m-2 s-1` for fluxes, `kg m-2` for stocks, `m-2` for densities, `s-1` for rates, `m2 m-2` for LAI, etc.).
- `long` — Long name.
- `avgflag` — Time-aggregation flag; see below.
- `vtype` — Dimension kind (e.g., `site_r8`, `site_pft_r8`, `site_size_pft_r8`, `site_cnlf_r8`). The `vtype` determines how the data buffer is sized and how the variable is indexed.
- `hlms` — Colon-separated list of compatible host land models.
- `upfreq` — Which update routine is responsible for this variable.
- `ivar` — Global counter, incremented by `set_history_var`.
- `index` — Module-level integer (written only when `initialize=.true.`).

### Averaging Flag (`avgflag`)

FATES follows the same convention as the CLM/ALM `histFileMod` host:

| `avgflag` | Meaning |
|---|---|
| `'A'` | **Average** over the history interval (accumulator divided by sample count on flush) |
| `'I'` | **Instantaneous** (no averaging; last value wins) |
| `'M'` | Minimum |
| `'X'` | Maximum |

In `e85d997`, every FATES history variable is registered with `avgflag='A'` (479 of 479 registrations). The output you read from a FATES history file is the **time-mean** of the variable over the host-model history interval, not an instantaneous snapshot.

Sources: `(main/FatesHistoryVariableType.F90:42-90)`, `(main/FatesHistoryInterfaceMod.F90:5326-7180)`

## Host Land Model Integration

The history interface is called from the host's main integration loop. The host is responsible for allocating the flat output arrays, invoking FATES' update and flush routines at the right times, and writing the arrays to NetCDF files. FATES is responsible for:

- Defining all diagnostic variables and their metadata during initialization.
- Accumulating into the per-variable buffers during each update routine call.
- Managing the dimension registry and multiplexed mappings.
- Ensuring unit consistency — all registered `units` strings are the units FATES writes; no conversion happens on the host side.

Each variable's `hlms` field marks it as compatible with specific host models. A sentinel value `hlm_hio_ignore_val` is used for variables that are not active in the current configuration. Boundary-condition types `bc_in_type` and `bc_out_type` (defined in `FatesInterfaceTypesMod.F90`) move other data between FATES and the host but are not directly involved in history output.

Sources: `(main/FatesHistoryInterfaceMod.F90:38-56, 777-862)`, `(main/FatesInterfaceTypesMod.F90:244-293)`
