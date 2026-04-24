# Restart System

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `main/FatesRestartInterfaceMod.F90`
- `main/FatesRestartVariableType.F90`
- `main/FatesIODimensionsMod.F90`
- `main/FatesIOVariableKindMod.F90`
- `parteh/PRTGenericMod.F90`
- `parteh/PRTAllometricCNPMod.F90`

## Purpose and Scope

The FATES restart system handles bidirectional serialization of model state between the linked-list structure used at runtime (sites → patches → cohorts) and the flat arrays used by the host land model for restart I/O. It is responsible for defining all restart variables, packing state into HLM arrays on write, and reconstructing the hierarchy and populating state on read.

For time-series diagnostic output see [History Output System](history/index.md). For the conservation layer that runs alongside the dynamics loop see [Mass Balance Checking](mass_balance.md).

## Architecture

The primary object is `fates_restart_interface_type` in `main/FatesRestartInterfaceMod.F90`. It manages:

- A fixed set of dimensions and dimension kinds.
- A hundreds-long set of restart variables, registered via `set_restart_var` with auto-incrementing `ivar` counters.
- A per-thread `dim_bounds` array that maps each dimension to the calling thread's lower/upper indices.
- A `restart_map_type` object that maps FATES site indices and cohort offsets to HLM I/O array positions.

The restart dimension space is intentionally small:

```
fates_restart_num_dimensions = 2   ! (cohort, column)
fates_restart_num_dim_kinds  = 4   ! (cohort_int, cohort_r8, site_int, site_r8)
```

Variables are flat 1-D arrays keyed by either cohort index or site/column index.

Sources: `(main/FatesRestartInterfaceMod.F90:297-376)`

## Dimension Kinds and Data Types

| Kind | Base dimension | Fortran type | Example use |
|---|---|---|---|
| `cohort_r8` | cohort | `real(r8)` | DBH, height, per-cohort PARTEH state |
| `cohort_int` | cohort | `integer` | PFT index, canopy layer, damage class, status |
| `site_r8` | column | `real(r8)` | Site-level litter pools, running means, age-since-disturbance |
| `site_int` | column | `integer` | Number of patches, phenology status, counters |

### Flush Values

When restart arrays are allocated they are initialized to sentinel values so that downstream code can detect "variable was never set":

| Constant | Value | Use |
|---|---|---|
| `flushinvalid` | `-9999.0` | Variables that must be explicitly populated (error if still at flush) |
| `flushzero` | `0.0` | Variables that default to zero |
| `flushone` | `1.0` | Variables that default to one |

Sources: `(main/FatesRestartInterfaceMod.F90:297-306)`

## Write and Read Workflow

### Writing (`set_restart_vectors`)

`set_restart_vectors` traverses the entire site/patch/cohort hierarchy, unpacks state, and writes it into the host's flat restart arrays. Because patches hold variable numbers of cohorts and sites hold variable numbers of patches, cohort-scale variables are packed sequentially into one long array per variable. The `restart_map%cohort1_index(s)` field stores the starting position of site `s`'s cohorts; the packing loop maintains a running `io_idx_co` index that increments with each cohort visited.

### Reading (`get_restart_vectors`)

`get_restart_vectors` performs two stages:

1. **Structure reconstruction.** `create_patchcohort_structure` walks the restart arrays and creates site, patch, and cohort objects in the correct order. Patches are linked youngest-to-oldest (age order); cohorts are linked tallest-to-shortest (height order). Since cohort height must be derived from `dbh` via allometry, the code reads `dbh` first, computes `height`, and then inserts the cohort into the list.
2. **State population.** Scalar and array state is copied from the flat restart arrays into the reconstructed objects.

The two stages cannot be swapped — state population assumes the linked lists already exist.

Sources: `(main/FatesRestartInterfaceMod.F90:1697-3555)`

## PARTEH State Serialization

PARTEH plant carbon, nitrogen, and phosphorus state is serialized by a dedicated routine, `DefinePRTRestartVars` (in `main/FatesRestartInterfaceMod.F90:1636-1762`). Rather than hand-listing one restart variable per organ-element combination, the routine loops over `prt_global%num_vars` (the number of PARTEH state variables active for the current allocation hypothesis) and, for each variable and each position (`i_pos` from 1 to `num_pos`), registers four restart records: one for the instantaneous state (`val`), one for the turnover flux (`turn`), one for the net allocation flux (`net`), and one for the fire burn flux (`burned`).

### Naming Convention

Each restart variable name is built from the PARTEH state symbol concatenated with a flux tag and a three-digit position index:

```
<symbol_base>_val_<NNN>      ! instantaneous state
<symbol_base>_turn_<NNN>     ! turnover flux
<symbol_base>_net_<NNN>      ! net allocation / reactive-transport flux
<symbol_base>_burned_<NNN>   ! mass lost to fire burn
```

where `<symbol_base>` is `prt_global%state_descriptor(i_var)%symbol` and `<NNN>` is the zero-padded position index (e.g., `001`). There is **no** `fates_` prefix prepended to the name, and there is **no** combined `<organ>_<element>` variable — each PARTEH state has four distinct records.

For the CNP flexible allometry hypothesis (`PRTAllometricCNPMod.F90:332-351`), the symbols are:

| Organ | Carbon | Nitrogen | Phosphorus |
|---|---|---|---|
| Leaf | `leaf_c` | `leaf_n` | `leaf_p` |
| Fine root | `fnrt_c` | `fnrt_n` | `fnrt_p` |
| Sapwood | `sapw_c` | `sapw_n` | `sapw_p` |
| Structural | `struct_c` | `struct_n` | `struct_p` |
| Storage | `store_c` | `store_n` | `store_p` |
| Reproductive | `repro_c` | `repro_n` | `repro_p` |

Concrete examples of actual restart variable names that appear in a CNP restart file:

```
leaf_c_val_001    leaf_c_turn_001    leaf_c_net_001    leaf_c_burned_001
leaf_c_val_002    leaf_c_turn_002    leaf_c_net_002    leaf_c_burned_002
...
fnrt_c_val_001    fnrt_c_turn_001    fnrt_c_net_001    fnrt_c_burned_001
sapw_n_val_001    sapw_n_turn_001    sapw_n_net_001    sapw_n_burned_001
store_p_val_001   store_p_turn_001   store_p_net_001   store_p_burned_001
```

Leaf pools can have multiple positions because `nleafage > 1` is supported for aging leaf cohorts; other organs typically have `num_pos = 1`. A user grepping a restart file for `fates_leaf_c` will find **nothing** — the correct search strings are `leaf_c_val_`, `leaf_c_turn_`, `leaf_c_net_`, or `leaf_c_burned_`.

### Long-Name Convention

Each restart record also carries a long name for self-documentation:

```
<name_base>, state var, position:<NNN>
<name_base>, turnover, position:<NNN>
<name_base>, net allocation/transp, position:<NNN>
<name_base>, burned mass:<NNN>
```

where `<name_base>` is `prt_global%state_descriptor(i_var)%longname` (e.g., `"Leaf Carbon"`, `"Fine Root Nitrogen"`).

Sources: `(main/FatesRestartInterfaceMod.F90:1636-1762)`, `(parteh/PRTAllometricCNPMod.F90:332-351)`, `(parteh/PRTGenericMod.F90:42, 466)`

## Variable Categories

Beyond PARTEH, the restart system serializes state organized into broad categories:

| Category | Examples (internal `ir_*` index names) |
|---|---|
| Site metadata | `ir_npatch_si`, `ir_cd_status_si`, `ir_acc_ni_si` |
| Patch metadata | `ir_ncohort_pa`, `ir_age_pa`, `ir_area_pa`, `ir_anthro_disturbance_label_pa` |
| Cohort structure | `ir_dbh_co`, `ir_height_co`, `ir_pft_co`, `ir_nplant_co` |
| Cohort physiology | `ir_canopy_layer_co`, `ir_status_co`, `ir_efleaf_co` |
| Litter pools | `ir_agcwd_litt`, `ir_leaf_litt`, `ir_seed_litt` (per element) |
| PARTEH state | `<symbol>_val_<NNN>`, `_turn_`, `_net_`, `_burned_` (see above) |
| Running-mean state (EMAs) | `rmean_type::rvars` payloads for environmental signals |

These `ir_*` names are internal Fortran identifiers assigned during registration — they are distinct from the user-facing variable names in the restart NetCDF file, which are the `vname=` strings passed to `set_restart_var`.

Sources: `(main/FatesRestartInterfaceMod.F90:85-295, 631-1484)`

## Conditional Registration

Variables for optional features are only registered when their enabling flag is active. A user restarting a run must match configuration flags between write and read, or the number of expected variables will differ.

### Plant Hydraulics (`hlm_use_planthydro == itrue`)

| Variable | Description | Units |
|---|---|---|
| `fates_hydro_th_ag_covec` | Above-ground tissue water content vector | `m3 m-3` |
| `fates_hydro_th_troot` | Transporting-root water content | `m3 m-3` |
| `fates_hydro_th_aroot_covec` | Absorbing-root water content vector | `m3 m-3` |
| `fates_hydro_liqvol_shell_si` | Rhizosphere shell liquid water volume | `m3` |
| `fates_hydro_recruit_si` | Recruitment water pool | `kg H2O m-2` |
| `fates_hydro_dead_si` | Mortality water pool | `kg H2O m-2` |

### CNP Dynamics (`hlm_parteh_mode == prt_cnp_flex_allom_hyp`)

| Variable | Role |
|---|---|
| `fates_daily_nh4_uptake` | Daily NH4 uptake accumulator (cohort) |
| `fates_daily_no3_uptake` | Daily NO3 uptake accumulator (cohort) |
| `fates_daily_p_uptake` | Daily P uptake accumulator (cohort) |
| `fates_daily_n_demand` | Daily N demand (cohort) |
| `fates_daily_p_demand` | Daily P demand (cohort) |
| `fates_cx_int` | Integrated C concentration (PID controller state) |
| `fates_emadcxdt` | EMA of dC/dt (PID controller state) |
| `fates_cnplimiter` | Limiter flag indicating binding nutrient |

### Tree Damage (`hlm_use_tree_damage == itrue`)

Additional size × damage-class arrays such as `fates_imortrate_cdpf`, `fates_termnindiv_cano_cdpf`, etc., are registered to persist per-damage-class mortality and termination bookkeeping.

Sources: `(main/FatesRestartInterfaceMod.F90:1283-1410, 767-815)`

## Restart Map

```fortran
type :: restart_map_type
   integer, allocatable :: site_index(:)    ! FATES site index -> HLM I/O site position
   integer, allocatable :: cohort1_index(:) ! FATES site index -> first cohort position in HIO arrays
end type
```

`site_index` maps each FATES site to its position in the host's flat per-site arrays. `cohort1_index` stores the starting index of each site's cohorts in the flat cohort arrays. Because the HLM stores data in long contiguous arrays across all threads, this mapping is how a FATES per-thread per-site view recovers which rows of those arrays belong to it.

Sources: `(main/FatesRestartInterfaceMod.F90:319-322)`

## Edge Cases

### Near-Bare-Ground Restarts

When a site starts from (or returns to) a near-bare-ground state, several precautions ensure valid initialization:

- Flush values prevent uninitialized reads from being interpreted as real data.
- PARTEH objects are always allocated and initialized via `InitPRTObject`, even when cohort biomass is zero — so the `val`/`turn`/`net`/`burned` variables always have a valid storage even in the absence of plants.
- Litter pools may legitimately be zero, which is not treated as an error.

### Cohort Status

The `status_co` variable distinguishes new from old cohorts and is preserved across restarts so that freshly recruited cohorts are still identifiable on the first step after restart.

### Multiple Elements

When multiple elements are active (C, CN, or CNP), `DefinePRTRestartVars` iterates over `prt_global%num_vars` and handles all active element-organ combinations without hand-coding each one. Restarts produced with CNP contain C, N, and P records; restarts produced with C-only contain only C records. A C-only-to-CNP upgrade across restart is therefore not supported without intervention.

Sources: `(main/FatesRestartInterfaceMod.F90:1489-1587, 3355-3414)`

## Summary

The FATES restart system provides: a bidirectional mapping between the FATES hierarchy and HLM flat arrays; flexible variable registration keyed on feature flags; automatic patch/cohort linked-list reconstruction on read; element-aware PARTEH serialization through a symbol-based loop; and thread-safe indexing via `restart_map` and per-thread `dim_bounds`. New state can be added by extending `define_restart_vars` (or `DefinePRTRestartVars`) and adding matching pack/unpack logic in `set_restart_vectors` / `get_restart_vectors`.
