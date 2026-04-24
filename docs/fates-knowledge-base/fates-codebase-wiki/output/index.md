# Model Output and Diagnostics

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `main/FatesHistoryInterfaceMod.F90`
- `main/FatesHistoryVariableType.F90`
- `main/FatesRestartInterfaceMod.F90`
- `main/FatesRestartVariableType.F90`
- `main/FatesIODimensionsMod.F90`
- `main/FatesIOVariableKindMod.F90`
- `main/EDMainMod.F90`
- `main/ChecksBalancesMod.F90`

## Purpose and Scope

This page surveys the two output paths FATES maintains (history and restart) and the conservation-checking layer that runs alongside them. History output is the time-series diagnostic pipeline that writes `FATES_*` variables to the host land model's history files. Restart output serializes the site/patch/cohort state needed for exact continuation. Mass balance is a separate verification layer, driven from `TotalBalanceCheck` in `EDMainMod`, that calls into `ChecksBalancesMod` to sum stocks at multiple points in the daily loop.

Related topics:

- [History Output System](history/index.md) — variable registration and dimension system
- [History Update Pipeline](history/pipeline.md) — update-routine flow and accumulation patterns
- [History Variables and Dimensions](history/variables.md) — dimension kinds and multiplexing
- [Restart System](restart.md) — state serialization and HLM coupling
- [Mass Balance Checking](mass_balance.md) — `TotalBalanceCheck` and call-index semantics

## System Architecture

History and restart are two independent pipelines that share a common dimension and variable-kind infrastructure (in `FatesIODimensionsMod.F90` and `FatesIOVariableKindMod.F90`). Both systems register variables during initialization, maintain per-thread bounds, and exchange flat arrays with the host land model.

The history interface is the `fates_history_interface_type` (in `main/FatesHistoryInterfaceMod.F90`, with a global instance `fates_hist`). It manages `fates_history_num_dimensions = 50` static dimension slots and `fates_history_num_dim_kinds = 50` dimension-kind slots.

The restart interface is the `fates_restart_interface_type` (in `main/FatesRestartInterfaceMod.F90`). It uses a much smaller dimension space, with `fates_restart_num_dimensions = 2` (cohort, column) and `fates_restart_num_dim_kinds = 4` (cohort_int, cohort_r8, site_int, site_r8).

Sources: `(main/FatesHistoryInterfaceMod.F90:743-854)`, `(main/FatesRestartInterfaceMod.F90:297-376)`

## History Output Pipeline Overview

History output operates in three phases within each simulation:

1. **Initialization.** `define_history_vars` (invoked at interface init) calls `set_history_var` hundreds of times to register each `FATES_*` variable with a name, long name, units, averaging flag, `vtype` (dimension kind), flush value, and update frequency (`upfreq`). Each call increments a global `ivar` counter and stores the resulting index into module-level integers named `ih_*`.
2. **Accumulation.** Four update routines are called at different points in the time loop (see [History Update Pipeline](history/pipeline.md)). Each routine iterates over sites, patches, and cohorts, computing indexed sums and writing them into the variable's data buffer.
3. **Flush and zero.** At the end of each host-model output interval, `flush_hvars` transfers buffers to the host I/O and `zero_site_hvars` resets the accumulators.

Sources: `(main/FatesHistoryInterfaceMod.F90:777-854)`, `(main/FatesHistoryInterfaceMod.F90:1144-1260)`

## Update Routines and Frequencies

Four update routines cover all FATES history output. The line ranges below are verified against `e85d997`.

| Routine | Lines | Called from | Purpose |
|---|---|---|---|
| `update_history_dyn` | 2108–4387 | After `ed_ecosystem_dynamics` | Demographic state, biomass pools, mortality rates, disturbance rates, daily fluxes |
| `update_history_hifrq` | 4389–4857 | Each photosynthesis timestep | GPP, autotrophic respiration, radiation, canopy temperature |
| `update_history_hydraulics` | 4861–5207 | Each hydraulics timestep when `hlm_use_planthydro == itrue` | Tissue water potential, sapflow, conductance, stomatal diagnostics |
| `update_history_nutrflux` | 1917–2104 | Daily, when `hlm_parteh_mode == prt_cnp_flex_allom_hyp` | NH4/NO3/P uptake, nutrient demand, N fixation, efflux |

Sources: `(main/FatesHistoryInterfaceMod.F90:1917-5207)`

## Dimension System

FATES variables are dimensioned across base dimensions (site, soil level, PFT, size class, age class, canopy layer, leaf layer, damage class, element, etc.) and multiplexed dimensions that combine several base dimensions into a single flat index. Multiplexing is needed because history files impose low dimensionality per variable.

### Base dimension kinds

Defined in `FatesIOVariableKindMod.F90`:

| Kind (constant name) | `name` string | Role |
|---|---|---|
| `site_r8` | `SI_R8` | Site-level real |
| `site_int` | `SI_INT` | Site-level integer |
| `cohort_r8` | `CO_R8` | Cohort-level real |
| `cohort_int` | `CO_INT` | Cohort-level integer |
| `site_pft_r8` | `SI_PFT_R8` | Site × PFT |
| `site_age_r8` | `SI_AGE_R8` | Site × patch age |
| `site_size_r8` | `SI_SCLS_R8` | Site × size class |
| `site_size_pft_r8` | `SI_SCPF_R8` | Site × (size × PFT) |
| `site_coage_r8` | `SI_CACLS_R8` | Site × cohort-age class |
| `site_coage_pft_r8` | `SI_CAPF_R8` | Site × (cohort age × PFT) |
| `site_height_r8` | `SI_HEIGHT_R8` | Site × height bin |
| `site_fuel_r8` | `SI_FUEL_R8` | Site × fuel class |
| `site_cwdsc_r8` | `SI_CWDSC_R8` | Site × CWD size class |
| `site_can_r8` | `SI_CAN_R8` | Site × canopy layer |
| `site_cnlf_r8` | `SI_CNLF_R8` | Site × (canopy layer × leaf layer) |
| `site_cnlfpft_r8` | `SI_CNLFPFT_R8` | Site × (canopy × leaf × PFT) |
| `site_cdpf_r8` | `SI_CDPF_R8` | Site × (size × damage × PFT) |
| `site_cdsc_r8` | `SI_CDSC_R8` | Site × (damage × size) |
| `site_cdam_r8` | `SI_CDAM_R8` | Site × damage class |
| `site_scag_r8` | `SI_SCAG_R8` | Site × (size × age) |
| `site_scagpft_r8` | `SI_SCAGPFT_R8` | Site × (size × age × PFT) |
| `site_agepft_r8` | `SI_AGEPFT_R8` | Site × (age × PFT) |
| `site_agefuel_r8` | `SI_AGEFUEL_R8` | Site × (age × fuel) |
| `site_clscpf_r8` | `SI_CLSCPF_R8` | Site × (canopy layer × size × PFT) |
| `site_soil_r8` | `SI_SOIL_R8` | Site × soil level |
| `site_elem_r8` | `SI_ELEM_R8` | Site × element (C/N/P) |
| `site_elpft_r8` | `SI_ELEMPFT_R8` | Site × (element × PFT) |
| `site_elcwd_r8` | `SI_ELEMCWD_R8` | Site × (element × CWD) |
| `site_elage_r8` | `SI_ELEMAGE_R8` | Site × (element × patch age) |

Sources: `(main/FatesIOVariableKindMod.F90:19-49)`

### Multiplexed dimension suffixes in output names

Output variable names encode their dimensionality using short suffixes. **These are the actual NetCDF variable names produced by FATES, not the internal `ih_*` index names.** Do not confuse the internal-style suffixes `_scpf`, `_cnlf`, `_cnlfpft` (used in `ih_*_si_scpf` variable-index identifiers inside the source) with the user-facing suffixes used in the history file.

| Output-name suffix | Dimensionality | Meaning |
|---|---|---|
| `_PF` | site × PFT | Per PFT |
| `_AP` | site × patch age | Per patch age class |
| `_APPF` | site × age × PFT | Per age × PFT |
| `_SZ` | site × size class | Per size class |
| `_SZPF` | site × size × PFT | Per size × PFT (by far the most common multi-PFT dimension, 100+ variables) |
| `_SZAP` | site × size × age | Per size × age |
| `_SZAPPF` | site × size × age × PFT | Per size × age × PFT |
| `_AC` | site × patch age (cohort-age variant) | Per cohort-age bin |
| `_ACPF` | site × cohort-age × PFT | Per cohort age × PFT |
| `_CDPF` | site × size × damage × PFT | Per size × damage × PFT |
| `_CL` | site × canopy layer | Per canopy layer |
| `_CLLL` | site × canopy layer × leaf layer | Canopy × leaf layer (radiation/PAR profile) |
| `_CLLLPF` | site × canopy layer × leaf layer × PFT | Canopy × leaf × PFT |
| `_SL` | site × soil level | Per soil layer |
| `_EL` | site × element | Per element (C/N/P) |
| `_FC` | site × fuel class | Per fuel size class |
| `_DC` | site × CWD decomposition class | Per CWD size class |
| `_SE_SZ` | site × size, "secondary" subset | Secondary-forest-only variant |

Sources: `(main/FatesHistoryInterfaceMod.F90:5326-7180)` (sample registration calls), `(main/FatesInterfaceTypesMod.F90:244-293)`

## Common History Variables

The following variables are registered via `set_history_var` with `vname=` exactly as shown. All carry `avgflag='A'` (time-mean over the output interval; see [History Update Pipeline](history/pipeline.md)). Units are quoted from the source (no unit conversion).

| `vname` | Kind | Units | Description |
|---|---|---|---|
| `FATES_GPP` | `site_r8` | `kg m-2 s-1` | Gross primary productivity (site total) |
| `FATES_NPP` | `site_r8` | `kg m-2 s-1` | Net primary productivity (site total) |
| `FATES_AR` | `site_r8` | `kg m-2 s-1` | Autotrophic respiration (site total) |
| `FATES_HET_RESP` | `site_r8` | `kg m-2 s-1` | Heterotrophic respiration (handed from HLM) |
| `FATES_NEP` | `site_r8` | `kg m-2 s-1` | Net ecosystem production |
| `FATES_VEGC` | `site_r8` | `kg m-2` | Total live vegetation carbon |
| `FATES_VEGC_ABOVEGROUND` | `site_r8` | `kg m-2` | Above-ground live vegetation carbon |
| `FATES_LEAFC` | `site_r8` | `kg m-2` | Leaf carbon (all PFTs) |
| `FATES_FROOTC` | `site_r8` | `kg m-2` | Fine-root carbon |
| `FATES_STOREC` | `site_r8` | `kg m-2` | Storage carbon |
| `FATES_STRUCTC` | `site_r8` | `kg m-2` | Structural carbon |
| `FATES_SAPWOODC` | `site_r8` | `kg m-2` | Sapwood carbon |
| `FATES_LAI` | `site_r8` | `m2 m-2` | Total leaf area index |
| `FATES_NPLANT_PF` | `site_pft_r8` | `m-2` | Plant density per PFT |
| `FATES_NPLANT_SZPF` | `site_size_pft_r8` | `m-2` | Plant density per size × PFT |
| `FATES_BASALAREA_SZPF` | `site_size_pft_r8` | `m2 m-2` | Basal area per size × PFT |
| `FATES_LEAFC_SZPF` | `site_size_pft_r8` | `kg m-2` | Leaf carbon per size × PFT |
| `FATES_GPP_SZPF` | `site_size_pft_r8` | `kg m-2 s-1` | GPP per size × PFT |
| `FATES_NPP_SZPF` | `site_size_pft_r8` | `kg m-2 s-1` | NPP per size × PFT |
| `FATES_DDBH_SZPF` | `site_size_pft_r8` | `m s-1` | Stem diameter increment per size × PFT |
| `FATES_MORTALITY_CANOPY_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Canopy mortality rate per size × PFT |
| `FATES_MORTALITY_USTORY_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Understory mortality rate per size × PFT |
| `FATES_MORTALITY_CSTARV_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Carbon-starvation mortality |
| `FATES_MORTALITY_HYDRAULIC_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Hydraulic failure mortality |
| `FATES_MORTALITY_FIRE_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Fire-induced mortality |
| `FATES_MORTALITY_LOGGING_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Logging-induced mortality |
| `FATES_BURNFRAC` | `site_r8` | `s-1` | Fractional area burned (per second) |
| `FATES_FIRE_INTENSITY` | `site_r8` | `J s-1 m-1` | Fire-line intensity |
| `FATES_DISTURBANCE_RATE_LOGGING` | `site_r8` | `m2 m-2 yr-1` | Logging disturbance rate |
| `FATES_DISTURBANCE_RATE_FIRE` | `site_r8` | `m2 m-2 yr-1` | Fire disturbance rate |
| `FATES_DISTURBANCE_RATE_TREEFALL` | `site_r8` | `m2 m-2 yr-1` | Treefall disturbance rate |
| `FATES_PARSUN_Z_CLLL` | `site_cnlf_r8` | `W m-2` | Sunlit PAR by canopy × leaf layer |
| `FATES_PARSHA_Z_CLLL` | `site_cnlf_r8` | `W m-2` | Shaded PAR by canopy × leaf layer |
| `FATES_LAISUN_Z_CLLLPF` | `site_cnlfpft_r8` | `m2 m-2` | Sunlit LAI by canopy × leaf × PFT |
| `FATES_NH4UPTAKE_SZPF` | `site_size_pft_r8` | `kg m-2 s-1` | NH4 uptake by size × PFT |
| `FATES_NO3UPTAKE_SZPF` | `site_size_pft_r8` | `kg m-2 s-1` | NO3 uptake by size × PFT |
| `FATES_PUPTAKE_SZPF` | `site_size_pft_r8` | `kg m-2 s-1` | P uptake by size × PFT |
| `FATES_CBALANCE_ERROR` | `site_r8` | `kg` | Reported carbon-balance error from `TotalBalanceCheck` |

**Naming correction note.** Earlier versions of this wiki used internal-style suffixes like `FATES_NPLANT_SCPF`, `FATES_MORTALITY_SCPF`, `FATES_DDBH_SCPF`, `FATES_STOREC_SCPF`, and `FATES_PARSUN_Z_CNLF`. These strings are **not** registered anywhere in `set_history_var`. The actual output names use `_SZPF`, `_CLLL`, and related suffixes above. There is no `FATES_FIRE_AREA` variable; fractional burned area is `FATES_BURNFRAC` (units `s-1`), and `FATES_NOCOMP_BURNEDAREA_PF` exists for nocomp PFT-specific burn area. Units for `FATES_GPP`/`FATES_NPP` are `kg m-2 s-1`, not `gC m-2 s-1` — differs by a factor of 1000.

Sources: `(main/FatesHistoryInterfaceMod.F90:5326-8543)`

## Restart Output Overview

The restart pipeline serializes complete model state for exact continuation. State is packed into flat 1-D arrays by cohort and by site (via `set_restart_vectors`) and unpacked on restart read (`get_restart_vectors`). The linked-list structure (sites → patches → cohorts) is rebuilt from the flat arrays by `create_patchcohort_structure` before state is populated.

Optional subsystems (plant hydraulics, CNP nutrient dynamics, tree damage) are conditionally registered — their variables only exist in the restart file if the corresponding `hlm_use_*` / `hlm_parteh_mode` flag is active. PARTEH plant carbon/nitrogen/phosphorus pools are serialized through a dedicated loop (`DefinePRTRestartVars`) described in [Restart System](restart.md).

Sources: `(main/FatesRestartInterfaceMod.F90:297-376, 1636-1762)`

## Mass Balance Overview

Mass balance is enforced by `TotalBalanceCheck` in `main/EDMainMod.F90:847-1024`, which runs at eight distinct call indices through the daily dynamics loop. At each call it invokes `SiteMassStock` from `ChecksBalancesMod.F90` to sum current stocks, compares the change-in-stock against the net flux-in minus flux-out, and aborts the run if the fractional error exceeds `10e-6`. See [Mass Balance Checking](mass_balance.md) for the full call-index table and flux-field inventory.

Sources: `(main/EDMainMod.F90:847-1024)`, `(main/ChecksBalancesMod.F90:32-125)`

## Flush and Thread Safety

Both history and restart systems initialize arrays to sentinel values so that uninitialized reads are detectable:

| Constant | Value | Use |
|---|---|---|
| `flushinvalid` | `-9999.0` | Variables that must be explicitly set (error if still at flush) |
| `flushzero` | `0.0` | Accumulators that naturally default to zero |
| `flushone` | `1.0` | Variables that default to one |

Thread safety is handled through `fates_io_dimension_type` objects that track per-thread lower/upper bounds. `SetThreadBoundsEach` is called during history/restart initialization, and subsequent variable accesses use those bounds to index into the shared HLM I/O arrays. A separate `restart_map_type` (fields `site_index` and `cohort1_index`) maps FATES site indices and cohort offsets to the host I/O positions.

Sources: `(main/FatesHistoryInterfaceMod.F90:1024-1260)`, `(main/FatesRestartInterfaceMod.F90:297-437)`

## Host Land Model Integration

Each history variable carries an `hlms` metadata string (e.g., `hlms='CLM:ALM'`) that marks it as compatible with specific host models. A sentinel `hlm_hio_ignore_val` flags missing data. Boundary condition types `bc_in_type` and `bc_out_type` (defined in `FatesInterfaceTypesMod.F90`) move data between FATES and the host.

Sources: `(main/FatesHistoryInterfaceMod.F90:38-56)`, `(main/FatesRestartInterfaceMod.F90:20-28)`
