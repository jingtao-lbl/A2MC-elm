---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# History Output System

**Relevant source files:**
- `main/FatesHistoryInterfaceMod.F90` (9944 lines)
- `main/FatesHistoryVariableType.F90`
- `main/FatesIODimensionsMod.F90`
- `main/FatesIOVariableKindMod.F90`
- `main/FatesInterfaceMod.F90`
- `main/FatesInterfaceTypesMod.F90`

## Purpose and Scope

The History Output System manages the definition, registration, accumulation, and flushing of FATES diagnostic variables. Because FATES organizes vegetation hierarchically (sites → patches → cohorts) and its patches and cohorts are born and die continuously, the output system has to bin continuous cohort attributes (DBH, age) into discrete classes and aggregate per-plant quantities into per-site arrays that can be written into a rectangular NetCDF file.

Related topics:

- [History Update Pipeline](pipeline.md) — where and how each update routine is called
- [History Variables and Dimensions](variables.md) — dimension kinds and the canonical e027a40 inventory
- [Restart System](../restart.md) — the separate pipeline for state serialization
- [Mass Balance Checking](../mass_balance.md) — conservation enforcement

## Architecture

The system lives in `main/FatesHistoryInterfaceMod.F90` and centers on the type `fates_history_interface_type`, with a global instance `fates_hist`. It manages:

- An `hvars(:)` array of history variable objects of type `fates_history_variable_type` (defined in `main/FatesHistoryVariableType.F90`), each carrying `vname`, `long_name`, `units`, `avgflag`, `vtype`, `flushval`, `upfreq`, and one or more data buffers.
- A `dim_kinds(:)` registry of dimension-kind objects (sized to `fates_history_num_dim_kinds = 50`).
- A `dim_bounds(:)` registry of per-thread dimension bounds (sized to `fates_history_num_dimensions = 50`).
- A set of integer indices into `dim_bounds`, one per dimension (e.g., `column_index_`, `levscpf_index_`, `levpft_index_`, `levlanduse_index_`).

Sources: `(main/FatesHistoryInterfaceMod.F90:825-862)`

## Initialization, Runtime, Flushing

The system moves through three phases:

1. **Initialization.** `define_history_vars` (called from `initialize_history_vars`) invokes `set_history_var` once per `FATES_*` variable, to register the variable's metadata, look up its dimension kind via `iotype_index`, allocate its data buffer, and stamp its integer index (e.g., `ih_leafc_pf`) into a module-level variable. There are **494 such registrations in e027a40** (493 unique vars in the standard CDL plus the conditional `FATES_L2FR_CLSZPF`).
2. **Runtime.** Four user-visible update routines (`update_history_dyn`, `update_history_hifrq`, `update_history_hydraulics`, `update_history_nutrflux`) walk the site/patch/cohort hierarchy and accumulate data into the registered variables. At e027a40 the first two are dispatchers that call a stack of sub-routines (sitelevel + subsite + subsite_ageclass; `_hifrq` additionally calls `update_history_hifrq_landuse` when `hlm_use_luh .eq. itrue`). See [History Update Pipeline](pipeline.md) for details.
3. **Flushing.** At the end of each host-model history interval, `flush_hvars` copies the accumulated buffers into the host's I/O arrays and `zero_site_hvars` resets the buffers using each variable's `flushval`.

Sources: `(main/FatesHistoryInterfaceMod.F90:825-862, 2355, 5152)`

## Dimension Registry

FATES tracks output across multiple axes. Each base dimension and each multiplexed dimension is registered once into the `dim_bounds` array during initialization, and a dedicated getter method returns its index:

| Dimension | Getter | Axis |
|---|---|---|
| `column` | `column_index()` | Site / gridcell |
| `levsoil` | `levsoil_index()` | Soil layer |
| `levpft` | `levpft_index()` | Plant functional type (14 PFTs at e027a40) |
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
| `levlanduse` | — | Land-use category (5 values: primary, secondary, pasture, rangeland, crop) |
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
| `levelage` | — | Element × patch age |
| `levlupft` | — | Land-use × PFT (multiplexed; 60 = 5 × 12 in CDL) |
| `levlulu` | — | Land-use × land-use (transition matrix; 25 = 5 × 5) |

Note: `levcdpf` is three-dimensional (`nlevsclass × nlevdamage × numpft`), not two-dimensional. See [History Variables and Dimensions](variables.md) for the full dimension-kind table, including the `dimsize` values used for allocation.

Sources: `(main/FatesHistoryInterfaceMod.F90:825-862)`, CDL `elm_fates_output_info_e027a40.cdl` for actual dimension sizes (`fates_levlanduse=5`, `fates_levlupft=60`, `fates_levlulu=25`).

## Variable Indexing (`ih_*`)

Each history variable receives a module-level integer index of the form `ih_<name>_<dim_suffix>` (e.g., `ih_nplant_si_scpf`, `ih_leafc_pf`). These indices are set during registration and are used at runtime to access variables without string lookups. They are **not** the user-facing output variable names.

User-facing output names are the `vname=` strings passed to `set_history_var` and follow a distinct convention using suffixes like `_SZPF`, `_PF`, `_CLLL`, `_CLLLPF`, `_LU`, `_LUPF`, `_LULU`. For example, the internal index `ih_nplant_si_scpf` is attached to the output variable whose `vname` is `FATES_NPLANT_SZPF`. A user grepping a NetCDF history file for `FATES_NPLANT_SCPF` will find nothing — the actual output name is `FATES_NPLANT_SZPF`.

Note also that the e85d997 `_Z`-infix radiation index identifiers (e.g., `ih_parsun_z_si_cnlf`) are gone at e027a40; the file vnames are now `FATES_PARSUN_CLLL`, `FATES_LAISUN_CLLL`, etc.

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
     upfreq=group_dyna_simple,                       &
     ivar=ivar, initialize=initialize_variables,     &
     index=ih_leafc_si_scpf)
```

Fields:

- `vname` — User-facing NetCDF variable name.
- `units` — Unit string (SI units; `kg m-2 s-1` for fluxes, `kg m-2` for stocks, `m-2` for densities, `s-1` for rates, `m2 m-2` for LAI, etc.). At e027a40 a few outliers use `kg m-2 yr-1` (e.g., the wood-product fluxes) and `kg C` (the harvest debt accumulators).
- `long` — Long name.
- `avgflag` — Time-aggregation flag; see below.
- `vtype` — Dimension kind (e.g., `site_r8`, `site_pft_r8`, `site_size_pft_r8`, `site_cnlf_r8`, `site_landuse_r8`). The `vtype` determines how the data buffer is sized and how the variable is indexed.
- `hlms` — Colon-separated list of compatible host land models (e.g., `'CLM:ALM'`).
- `upfreq` — Which update routine is responsible for this variable (now uses symbolic group constants, e.g., `group_dyna_simple`, `group_hifrq_simple`).
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

In e027a40, every FATES history variable is registered with `avgflag='A'` (a `grep -c "avgflag='A'"` against `FatesHistoryInterfaceMod.F90` yields 498 matches across 494 unique `vname='FATES_*'` registrations; the few extra hits are for `set_history_var` calls that share an `avgflag` literal with adjacent code). The output you read from a FATES history file is the **time-mean** of the variable over the host-model history interval, not an instantaneous snapshot.

Sources: `(main/FatesHistoryVariableType.F90)`, `(main/FatesHistoryInterfaceMod.F90)`

## Host Land Model Integration

The history interface is called from the host's main integration loop. The host is responsible for allocating the flat output arrays, invoking FATES' update and flush routines at the right times, and writing the arrays to NetCDF files. FATES is responsible for:

- Defining all diagnostic variables and their metadata during initialization.
- Accumulating into the per-variable buffers during each update routine call.
- Managing the dimension registry and multiplexed mappings.
- Ensuring unit consistency — all registered `units` strings are the units FATES writes; no conversion happens on the host side.

Each variable's `hlms` field marks it as compatible with specific host models. A sentinel value `hlm_hio_ignore_val` is used for variables that are not active in the current configuration. Boundary-condition types `bc_in_type` and `bc_out_type` (defined in `FatesInterfaceTypesMod.F90`) move other data between FATES and the host but are not directly involved in history output.
