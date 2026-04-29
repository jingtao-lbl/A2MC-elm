---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Model Output and Diagnostics

**Relevant source files:**
- `main/FatesHistoryInterfaceMod.F90` (9944 lines)
- `main/FatesHistoryVariableType.F90`
- `main/FatesRestartInterfaceMod.F90` (4259 lines)
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
- [History Variables and Dimensions](history/variables.md) — dimension kinds and the canonical e027a40 inventory
- [Restart System](restart.md) — state serialization and HLM coupling
- [Mass Balance Checking](mass_balance.md) — `TotalBalanceCheck` and call-index semantics

## What Changed at e027a40

This document and its companions are pinned to FATES commit `e027a40` (release tag `sci.1.91.1_api.43.1.0`, paired with ELM at E3SM commit `d40b8431`). Compared to the e85d997 baseline, the output subsystem has substantially churned. Roughly 30% of `FATES_*` history variable names are renamed, added, or removed. Highlights:

- A new **Land Use (LU)** family was added (suffix `_LU`, `_LUPF`, `_LULU`, dim `fates_levlanduse=5`). This generalizes the older `*_SECONDARY` and `*_SE_PF`/`*_SE_SZ` family, which has been removed (only `FATES_MORTALITY_CANOPY_SE_SZ` remains).
- The `_Z` infix in `FATES_PARSUN_Z_*` and `FATES_LAISUN_Z_*` was dropped: e027a40 names are `FATES_PARSUN_CLLL`, `FATES_LAISUN_CLLL`, `FATES_PARSUN_CL`, etc.
- `FATES_AR`, `FATES_AR_CANOPY`, `FATES_AR_UNDERSTORY` were renamed to `FATES_AUTORESP`, `FATES_AUTORESP_CANOPY`, `FATES_AUTORESP_USTORY`.
- The fire family was split into a `FATES_WILDFIRE_*` set and a `FATES_RXFIRE_*` (prescribed-fire) set, and the mortality variables now have parallel `WILDFIRE` / `RXFIRE` partitions (e.g., `FATES_MORTALITY_WILDFIRE_SZPF`, `FATES_MORTALITY_RXFIRE_SZPF`, `FATES_MORTALITY_WILDFIRE_CAMBIAL_SZPF`). The old `FATES_MORTALITY_FIRE_SZPF`, `_CAMBIALBURN_SZPF`, `_CROWNSCORCH_SZPF` are gone.
- `FATES_HARVEST_CARBON_FLUX` and `FATES_WOOD_PRODUCT` were replaced by `FATES_HARVEST_WOODPROD_C_FLUX` and the new `FATES_LUCHANGE_WOODPROD_C_FLUX`.
- The 12 `FATES_FABD_*` and `FATES_FABI_*` absorbed-radiation variables were removed.
- New `FATES_GRAZING` site flux, error fields `FATES_VIS_RAD_ERROR`, `FATES_NIR_RAD_ERROR`, `FATES_INTERR_LIVEVEG_EL`, `FATES_INTERR_LITTER_EL`, and a continuous-cstarv decomposition `FATES_MORT_CSTARV_CONT_CFLUX_PF`.

The CDL `docs/fates-knowledge-base/elm_fates_output_info_e027a40.cdl` is the canonical, machine-checkable inventory (493 unique vars). The Fortran source registers 494 (`FATES_L2FR_CLSZPF` is conditional on a build flag and absent from the standard CDL).

## System Architecture

History and restart are two independent pipelines that share a common dimension and variable-kind infrastructure (in `FatesIODimensionsMod.F90` and `FatesIOVariableKindMod.F90`). Both systems register variables during initialization, maintain per-thread bounds, and exchange flat arrays with the host land model.

The history interface is the `fates_history_interface_type` (in `main/FatesHistoryInterfaceMod.F90`, with a global instance `fates_hist`). It manages `fates_history_num_dimensions = 50` static dimension slots and `fates_history_num_dim_kinds = 50` dimension-kind slots.

The restart interface is the `fates_restart_interface_type` (in `main/FatesRestartInterfaceMod.F90`). It uses a much smaller dimension space, with `fates_restart_num_dimensions = 2` (cohort, column) and `fates_restart_num_dim_kinds = 4` (cohort_int, cohort_r8, site_int, site_r8).

Sources: `(main/FatesHistoryInterfaceMod.F90:825-842)`, `(main/FatesRestartInterfaceMod.F90:350-394)`

## History Output Pipeline Overview

History output operates in three phases within each simulation:

1. **Initialization.** `define_history_vars` (invoked at interface init) calls `set_history_var` 494 times to register each `FATES_*` variable with a name, long name, units, averaging flag, `vtype` (dimension kind), flush value, and update frequency (`upfreq`). Each call increments a global `ivar` counter and stores the resulting index into module-level integers named `ih_*`.
2. **Accumulation.** Update routines are called at different points in the time loop (see [History Update Pipeline](history/pipeline.md)). The user-facing entry points are `update_history_dyn`, `update_history_hifrq`, `update_history_hydraulics`, and `update_history_nutrflux`. At e027a40 the first two are thin wrappers that dispatch to a sitelevel/subsite/subsite_ageclass stack, and `update_history_hifrq` additionally dispatches to a new `update_history_hifrq_landuse` when `hlm_use_luh .eq. itrue`.
3. **Flush and zero.** At the end of each host-model output interval, `flush_hvars` transfers buffers to the host I/O and `zero_site_hvars` resets the accumulators.

## Update Routines and Frequencies

The visible call surface from outside `FatesHistoryInterfaceMod` is still four routines, but `_dyn` and `_hifrq` are now dispatchers:

| User-facing routine | e027a40 lines | Called from | Notes |
|---|---|---|---|
| `update_history_dyn` | 2355-2392 | After `ed_ecosystem_dynamics` | Dispatcher: calls `_sitelevel`, `_subsite`, `_subsite_ageclass`, plus `reset_history_dyn_subsite` |
| `update_history_hifrq` | 5152-5183 | Each photosynthesis timestep | Dispatcher: calls `_sitelevel`, `_subsite`, `_subsite_ageclass`, plus `_landuse` when `hlm_use_luh .eq. itrue` |
| `update_history_hydraulics` | 6042-6422 | Each hydraulics timestep when `hlm_use_planthydro == itrue` | Single routine |
| `update_history_nutrflux` | 2132-2351 | Daily, when `hlm_parteh_mode == prt_cnp_flex_allom_hyp` | Single routine |

See [History Update Pipeline](history/pipeline.md) for the sub-routine breakdown.

Sources: `(main/FatesHistoryInterfaceMod.F90:2132, 2355, 5152, 6042)`

## Dimension System

FATES variables are dimensioned across base dimensions (site, soil level, PFT, size class, age class, canopy layer, leaf layer, damage class, element, land use, etc.) and multiplexed dimensions that combine several base dimensions into a single flat index. Multiplexing is needed because history files impose low dimensionality per variable.

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
| `site_landuse_r8` | (LU) | Site × land-use category (NEW at e027a40) |
| `site_landuse_pft_r8` | (LUPF) | Site × (land-use × PFT) |
| `site_landuse_landuse_r8` | (LULU) | Site × (land-use × land-use) (transition matrix) |

The `site_landuse_*` kinds support the new `_LU`, `_LUPF`, `_LULU` family. The CDL exposes these via `fates_levlanduse=5`, `fates_levlupft=60`, `fates_levlulu=25`.

### Multiplexed dimension suffixes in output names

Output variable names encode their dimensionality using short suffixes. **These are the actual NetCDF variable names produced by FATES, not the internal `ih_*` index names.**

| Output-name suffix | Dimensionality | Meaning |
|---|---|---|
| `_PF` | site × PFT | Per PFT (35 vars in CDL) |
| `_AP` | site × patch age | Per patch age class (22 vars) |
| `_APPF` | site × age × PFT | Per age × PFT |
| `_APFC` | site × age × fuel | Per age × fuel class |
| `_SZ` | site × size class | Per size class (74 vars) |
| `_SZPF` | site × size × PFT | Per size × PFT (most common; 115 vars) |
| `_SZAP` | site × size × age | Per size × age |
| `_SZAPPF` | site × size × age × PFT | Per size × age × PFT |
| `_AC` | site × cohort-age | Per cohort-age bin |
| `_ACPF` | site × cohort-age × PFT | Per cohort age × PFT |
| `_CD` | site × damage class | Per crown-damage class |
| `_CDPF` | site × size × damage × PFT | Per size × damage × PFT |
| `_CL` | site × canopy layer | Per canopy layer |
| `_CLLL` | site × canopy × leaf | Canopy × leaf layer (radiation/PAR profile) |
| `_CLLLPF` | site × canopy × leaf × PFT | Canopy × leaf × PFT |
| `_CLSZPF` | canopy × size × PFT | Canopy-layer × size × PFT (conditional, build-flag gated) |
| `_SL` | site × soil level | Per soil layer |
| `_HT` | site × height bin | Per height bin |
| `_EL` | site × element | Per element (C/N/P) |
| `_ELDC` | site × element × CWD | Per element × CWD |
| `_FC` | site × fuel class | Per fuel size class |
| `_DC` | site × CWD class | Per CWD size class |
| `_LU` | site × land-use | Per land-use category (NEW) |
| `_LUPF` | site × land-use × PFT | Per (land-use × PFT) (NEW) |
| `_LULU` | site × land-use × land-use | Land-use transition matrix (NEW) |
| `_SE_SZ` | site × size, secondary subset | Only `FATES_MORTALITY_CANOPY_SE_SZ` remains at e027a40 |

Note that the `*_SECONDARY` and `*_SE_PF` suffix families are gone. The `_SE_SZ` family has shrunk to a single survivor.

Sources: variable definitions span `(main/FatesHistoryInterfaceMod.F90: ~5300-9700)`; canonical inventory in `docs/fates-knowledge-base/elm_fates_output_info_e027a40.cdl`.

## Common History Variables

The following variables are registered via `set_history_var` with `vname=` exactly as shown. All carry `avgflag='A'` (time-mean over the output interval; see [History Update Pipeline](history/pipeline.md)). Units are quoted from the source / CDL (no unit conversion).

| `vname` | Kind | Units | Description |
|---|---|---|---|
| `FATES_GPP` | `site_r8` | `kg m-2 s-1` | Gross primary productivity (site total) |
| `FATES_NPP` | `site_r8` | `kg m-2 s-1` | Net primary productivity (site total) |
| `FATES_AUTORESP` | `site_r8` | `kg m-2 s-1` | Autotrophic respiration (REPLACES `FATES_AR`) |
| `FATES_AUTORESP_CANOPY` | `site_r8` | `kg m-2 s-1` | Canopy autotrophic respiration (REPLACES `FATES_AR_CANOPY`) |
| `FATES_AUTORESP_USTORY` | `site_r8` | `kg m-2 s-1` | Understory autotrophic respiration (REPLACES `FATES_AR_UNDERSTORY`) |
| `FATES_HET_RESP` | `site_r8` | `kg m-2 s-1` | Heterotrophic respiration (handed from HLM) |
| `FATES_NEP` | `site_r8` | `kg m-2 s-1` | Net ecosystem production |
| `FATES_GRAZING` | `site_r8` | `kg m-2 s-1` | Grazing of leaves by herbivores (NEW) |
| `FATES_VEGC` | `site_r8` | `kg m-2` | Total live vegetation carbon |
| `FATES_VEGC_ABOVEGROUND` | `site_r8` | `kg m-2` | Above-ground live vegetation carbon |
| `FATES_LEAFC` | `site_r8` | `kg m-2` | Leaf carbon (all PFTs) |
| `FATES_FROOTC` | `site_r8` | `kg m-2` | Fine-root carbon |
| `FATES_STOREC` | `site_r8` | `kg m-2` | Storage carbon |
| `FATES_STRUCTC` | `site_r8` | `kg m-2` | Structural carbon |
| `FATES_SAPWOODC` | `site_r8` | `kg m-2` | Sapwood carbon |
| `FATES_LAI` | `site_r8` | `m2 m-2` | Total leaf area index |
| `FATES_ELAI` | `site_r8` | `m2 m-2` | Effective LAI (NEW) |
| `FATES_NCL` | `site_r8` | `count` | Number of canopy layers (NEW; site-level companion to `FATES_NCL_AP`) |
| `FATES_CANOPYAREA` | `site_r8` | `m2 m-2` | Canopy area (NEW) |
| `FATES_PATCHAREA` | `site_r8` | `m2 m-2` | Patch area (NEW; site-level companion to `FATES_PATCHAREA_AP`) |
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
| `FATES_MORTALITY_WILDFIRE_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Wildfire mortality (REPLACES `FATES_MORTALITY_FIRE_SZPF`) |
| `FATES_MORTALITY_WILDFIRE_CAMBIAL_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Wildfire cambial-burn mortality (REPLACES `_CAMBIALBURN_SZPF`) |
| `FATES_MORTALITY_WILDFIRE_CROWN_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Wildfire crown-scorch mortality (REPLACES `_CROWNSCORCH_SZPF`) |
| `FATES_MORTALITY_RXFIRE_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Prescribed-fire mortality (NEW) |
| `FATES_MORTALITY_RXCAMBIAL_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Prescribed-fire cambial mortality (NEW) |
| `FATES_MORTALITY_RXCROWN_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Prescribed-fire crown mortality (NEW) |
| `FATES_MORTALITY_LOGGING_SZPF` | `site_size_pft_r8` | `m-2 s-1` | Logging-induced mortality |
| `FATES_MORT_CSTARV_CONT_CFLUX_PF` | `site_pft_r8` | `kg m-2 s-1` | Continuous-cstarv mortality C flux per PFT (NEW) |
| `FATES_BURNFRAC` | `site_r8` | `s-1` | Total burned area fraction (sum of wildfire+rxfire) |
| `FATES_WILDFIRE_BURNFRAC` | `site_r8` | `s-1` | Wildfire-only burnt fraction (NEW) |
| `FATES_RXFIRE_BURNFRAC` | `site_r8` | `s-1` | Prescribed-fire burnt fraction (NEW) |
| `FATES_FIRE_INTENSITY` | `site_r8` | `J m-1 s-1` | Combined fire-line intensity |
| `FATES_WILDFIRE_INTENSITY` | `site_r8` | `J m-1 s-1` | Wildfire fireline intensity (NEW) |
| `FATES_RXFIRE_INTENSITY` | `site_r8` | `J m-1 s-1` | Prescribed-fire fireline intensity (NEW) |
| `FATES_FIRE_CLOSS_LIVEFUELS` | `site_r8` | `kg m-2 s-1` | Fire C loss from live fuels only (NEW) |
| `FATES_FIRE_CLOSS_LANDUSECHANGE` | `site_r8` | `kg m-2 s-1` | Fire C loss attributable to land-use change (NEW) |
| `FATES_DISTURBANCE_RATE_LOGGING` | `site_r8` | `m2 m-2 yr-1` | Logging disturbance rate |
| `FATES_DISTURBANCE_RATE_FIRE` | `site_r8` | `m2 m-2 yr-1` | Fire disturbance rate |
| `FATES_DISTURBANCE_RATE_TREEFALL` | `site_r8` | `m2 m-2 yr-1` | Treefall disturbance rate |
| `FATES_DISTURBANCE_RATE_MATRIX_LULU` | `site_landuse_landuse_r8` | `m2 m-2 yr-1` | Land-use × land-use disturbance transition matrix (NEW) |
| `FATES_TRANSITION_MATRIX_LULU` | `site_landuse_landuse_r8` | `m2 m-2 yr-1` | Land-use × land-use transition matrix (NEW) |
| `FATES_HARVEST_WOODPROD_C_FLUX` | `site_r8` | `kg m-2 yr-1` | Wood product flux from harvest (REPLACES `FATES_HARVEST_CARBON_FLUX` and `FATES_WOOD_PRODUCT`) |
| `FATES_LUCHANGE_WOODPROD_C_FLUX` | `site_r8` | `kg m-2 yr-1` | Wood product flux from land-use change (NEW) |
| `FATES_HARVEST_DEBT` | `site_r8` | `kg C` | Accumulated unmet harvest carbon |
| `FATES_HARVEST_DEBT_SEC` | `site_r8` | `kg C` | Accumulated unmet harvest C from secondary patches |
| `FATES_PARSUN_CLLL` | `site_cnlf_r8` | `W m-2` | Sunlit PAR by canopy × leaf layer (was `FATES_PARSUN_Z_CLLL` at e85d997) |
| `FATES_PARSHA_CLLL` | `site_cnlf_r8` | `W m-2` | Shaded PAR by canopy × leaf layer (was `FATES_PARSHA_Z_CLLL`) |
| `FATES_LAISUN_CLLLPF` | `site_cnlfpft_r8` | `m2 m-2` | Sunlit LAI by canopy × leaf × PFT (was `FATES_LAISUN_Z_CLLLPF`) |
| `FATES_GPP_LU` | `site_landuse_r8` | `kg m-2 s-1` | GPP per land-use type (NEW; replaces `_SECONDARY` family) |
| `FATES_NPP_LU` | `site_landuse_r8` | `kg m-2 s-1` | NPP per land-use type (NEW) |
| `FATES_VEGC_LU` | `site_landuse_r8` | `kg m-2` | Vegetation carbon per land-use type (NEW) |
| `FATES_NH4UPTAKE_SZPF` | `site_size_pft_r8` | `kg m-2 s-1` | NH4 uptake by size × PFT |
| `FATES_NO3UPTAKE_SZPF` | `site_size_pft_r8` | `kg m-2 s-1` | NO3 uptake by size × PFT |
| `FATES_PUPTAKE_SZPF` | `site_size_pft_r8` | `kg m-2 s-1` | P uptake by size × PFT |
| `FATES_CBALANCE_ERROR` | `site_r8` | `kg` | Reported carbon-balance error from `TotalBalanceCheck` |
| `FATES_VIS_RAD_ERROR` | `site_r8` | `W m-2` | Visible-radiation balance error (NEW) |
| `FATES_NIR_RAD_ERROR` | `site_r8` | `W m-2` | Near-infrared radiation balance error (NEW) |
| `FATES_INTERR_LIVEVEG_EL` | `site_elem_r8` | `kg m-2` | Live-veg integration error per element (NEW) |
| `FATES_INTERR_LITTER_EL` | `site_elem_r8` | `kg m-2` | Litter-pool integration error per element (NEW) |

The full e027a40 inventory is in [History Variables and Dimensions](history/variables.md), regenerated from the canonical CDL.

**Naming-correction notes for users coming from e85d997:**

- The `_Z` infix has been dropped everywhere in radiation variables. Replace `FATES_PARSUN_Z_*` → `FATES_PARSUN_*`, `FATES_LAISUN_Z_*` → `FATES_LAISUN_*`, etc.
- `FATES_AR`, `FATES_AR_CANOPY`, `FATES_AR_UNDERSTORY` → `FATES_AUTORESP`, `FATES_AUTORESP_CANOPY`, `FATES_AUTORESP_USTORY`.
- `FATES_HARVEST_CARBON_FLUX` and `FATES_WOOD_PRODUCT` no longer exist; use `FATES_HARVEST_WOODPROD_C_FLUX` plus the new `FATES_LUCHANGE_WOODPROD_C_FLUX`. Note units are `kg m-2 yr-1`, NOT `kg m-2 s-1`.
- `FATES_FIRE_AREA` does not exist; fractional burned area is `FATES_BURNFRAC` (units `s-1`), and `FATES_NOCOMP_BURNEDAREA_PF` exists for nocomp PFT-specific burn area.
- `FATES_FABD_*` and `FATES_FABI_*` (12 variables) are gone with no direct replacement.
- Every `*_SECONDARY` and `*_SE_PF` variable is gone. Use the `_LU` family with `fates_levlanduse=5`.
- Every `MORTALITY_*_SE_SZ` variant is gone except `FATES_MORTALITY_CANOPY_SE_SZ`.
- Units for `FATES_GPP`/`FATES_NPP` are `kg m-2 s-1`, not `gC m-2 s-1` — differs by a factor of 1000.

## Restart Output Overview

The restart pipeline serializes complete model state for exact continuation. State is packed into flat 1-D arrays by cohort and by site (via `set_restart_vectors`) and unpacked on restart read (`get_restart_vectors`). The linked-list structure (sites → patches → cohorts) is rebuilt from the flat arrays by `create_patchcohort_structure` before state is populated.

Optional subsystems (plant hydraulics, CNP nutrient dynamics, tree damage) are conditionally registered — their variables only exist in the restart file if the corresponding `hlm_use_*` / `hlm_parteh_mode` flag is active. PARTEH plant carbon/nitrogen/phosphorus pools are serialized through a dedicated loop (`DefinePRTRestartVars`) described in [Restart System](restart.md).

Sources: `(main/FatesRestartInterfaceMod.F90:350-394, 1883-2026)`

## Mass Balance Overview

Mass balance is enforced by `TotalBalanceCheck` in `main/EDMainMod.F90:928-1127`, which runs at eight distinct call indices through the daily dynamics loop. At e027a40 the routine takes an optional `is_restarting` argument so that on restart days the closure fluxes are zeroed and no spurious balance error is reported. At each call it invokes `SiteMassStock` from `ChecksBalancesMod.F90` to sum current stocks, compares the change-in-stock against the net flux-in minus flux-out, and aborts the run if the fractional error exceeds `10e-6`. See [Mass Balance Checking](mass_balance.md) for the call-index table, the new `flux_in`/`flux_out` formulae, and the per-PFT/per-disturbance-type field restructuring.

Sources: `(main/EDMainMod.F90:928-1127)`, `(main/ChecksBalancesMod.F90:45-128)`

## Flush and Thread Safety

Both history and restart systems initialize arrays to sentinel values so that uninitialized reads are detectable:

| Constant | Value | Use |
|---|---|---|
| `flushinvalid` | `-9999.0` | Variables that must be explicitly set (error if still at flush) |
| `flushzero` | `0.0` | Accumulators that naturally default to zero |
| `flushone` | `1.0` | Variables that default to one |

Thread safety is handled through `fates_io_dimension_type` objects that track per-thread lower/upper bounds. `SetThreadBoundsEach` is called during history/restart initialization, and subsequent variable accesses use those bounds to index into the shared HLM I/O arrays. A separate `restart_map_type` (fields `site_index` and `cohort1_index`) maps FATES site indices and cohort offsets to the host I/O positions.

Sources: `(main/FatesRestartInterfaceMod.F90:358-360, 470-571)`

## Host Land Model Integration

Each history variable carries an `hlms` metadata string (e.g., `hlms='CLM:ALM'`) that marks it as compatible with specific host models. A sentinel `hlm_hio_ignore_val` flags missing data. Boundary condition types `bc_in_type` and `bc_out_type` (defined in `FatesInterfaceTypesMod.F90`) move data between FATES and the host. At e027a40 the `bc_out` flow into ELM also carries the new `bc_out%grazing_closs_to_atm_si` (set from `site_mass%herbivory_flux_out`) alongside the renamed `bc_out%fire_closs_to_atm_si` (now summed across `n_dist_types`).

Sources: `(main/EDMainMod.F90:921-922)`
