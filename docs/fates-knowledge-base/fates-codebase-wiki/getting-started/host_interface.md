---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Host Model Interface

## Purpose and Scope

The Host Model Interface (HMI) defines the coupling layer between FATES and host land models (HLMs) such as CLM, ALM, and ELM. This interface establishes the API through which the HLM controls FATES execution, passes environmental drivers and boundary conditions, and receives vegetation state and flux information. The HMI is intentionally generic: the same FATES internal implementation can couple to multiple host models without modification.

This page covers the boundary condition structures, interface data types, and coupling mechanisms. For initialization modes (near-bare-ground, inventory, restart), see [Initialization Modes](initialization.md). For parameter file handling, see [Parameter System](parameter_system.md).

## Interface Architecture Overview

The host model interface is implemented primarily through three modules:

- `main/FatesInterfaceMod.F90` — runtime interface, boundary-condition allocation and zeroing, parameter read driver
- `main/FatesInterfaceTypesMod.F90` — global flag and boundary-condition type declarations
- `main/FatesRestartInterfaceMod.F90` — restart I/O (covered in [Restart System](../output/restart.md))

## The `fates_interface_type` Structure

`fates_interface_type` `(main/FatesInterfaceMod.F90:125)` is the root container for all FATES state and boundary conditions. Each HLM thread or domain instantiates one or more of these objects.

```fortran
type, public :: fates_interface_type
   integer                      :: nsites
   type(ed_site_type),  pointer :: sites(:)
   type(bc_in_type),    allocatable :: bc_in(:)
   type(bc_out_type),   allocatable :: bc_out(:)
   type(bc_pconst_type)         :: bc_pconst
end type fates_interface_type
```

| Component | Purpose | Allocation |
|-----------|---------|------------|
| `sites(:)` | FATES site structures containing patches and cohorts | Per site |
| `bc_in(:)` | Input boundary conditions from HLM (meteorology, soil state, etc.) | Per site |
| `bc_out(:)` | Output boundary conditions to HLM (fluxes, canopy properties) | Per site |
| `bc_pconst` | Parameter constants (nutrient uptake kinetics) | Once per interface |

Source: `main/FatesInterfaceMod.F90:125-159`.

## Boundary Condition System

### Input Boundaries (`bc_in_type`)

`bc_in_type` holds all environmental drivers and soil-state information that FATES requires from the HLM. These are updated each model timestep or sub-timestep.

Key input groups:

| Category | Key Variables | Units | Dimension |
|----------|---------------|-------|-----------|
| Radiation | `solad_parb`, `solai_parb` | W/m² | patch × band |
| Soil hydrology | `smp_sl`, `h2o_liqvol_sl`, `watsat_sl` | mm, m³/m³ | soil layer |
| Soil temperature | `tempk_sl`, `t_soisno_sl` | K | soil layer |
| Atmosphere | `cair_pa`, `oair_pa`, `eair_pa` | Pa | patch |
| Fire weather | `lightning24`, `precip24_pa`, `wind24_pa`, `relhumid24_pa` | various | patch |
| Nutrient fluxes | `plant_nh4_uptake_flux`, `plant_no3_uptake_flux`, `plant_p_uptake_flux` | kg/m²/day | competitor × layer |
| Land use | `hlm_harvest_rates`, `hlm_harvest_catnames` | — | harvest category |

Sources: `main/FatesInterfaceTypesMod.F90:348-562`, `main/FatesInterfaceMod.F90:412-564` (`allocate_bcin`).

### Output Boundaries (`bc_out_type`)

`bc_out_type` holds vegetation state, canopy structure, and biogeochemical fluxes that FATES returns to the HLM for surface energy balance, hydrology, and soil BGC.

| Category | Key Variables | Units | Dimension |
|----------|---------------|-------|-----------|
| Canopy structure | `elai_pa`, `esai_pa`, `htop_pa` | m²/m², m | patch |
| Radiation | `albd_parb`, `albi_parb`, `fabd_parb`, `fabi_parb` | fraction | patch × band |
| Hydrology | `rootr_pasl`, `btran_pa` | fraction | patch (× layer) |
| Stomatal conductance | `rssun_pa`, `rssha_pa` | s/m | patch |
| Litter fluxes | `litt_flux_cel_c_si`, `litt_flux_lig_c_si`, `litt_flux_lab_c_si` | g/m³/s | decomp layer |
| Nutrient competition | `veg_rootc`, `ft_index`, `cn_scalar`, `cp_scalar` | gC/m³, index, — | competitor (× layer) |

Sources: `main/FatesInterfaceTypesMod.F90:565-751`, `main/FatesInterfaceMod.F90:569-704` (`allocate_bcout`).

### Parameter Constants (`bc_pconst_type`)

`bc_pconst_type` holds parameters set once during initialization and read-only afterwards. These are primarily used for nutrient uptake kinetics in ECA (Equilibrium Chemistry Approximation) mode. Allocated in `allocate_bcpconst()` `(main/FatesInterfaceMod.F90:225-243)` and populated in `set_bcpconst()` `(main/FatesInterfaceMod.F90:247-267)`:

```
vmax_nh4, vmax_no3, vmax_p            ! uptake rate constants (per PFT)
eca_km_nh4, eca_km_no3, eca_km_p      ! half-saturation constants (per PFT)
eca_km_ptase, eca_vmax_ptase
eca_alpha_ptase, eca_lambda_ptase
j_uptake                               ! per soil decomp layer
eca_plant_escalar                      ! scalar
```

The `set_bcpconst()` copies these from `EDPftvarcon_inst`, so any calibration that changes `fates_cnp_vmax_*` or `fates_cnp_eca_km_*` parameters flows through automatically.

## Host Model Configuration Parameters

FATES behavior is controlled by global flags set by the HLM during initialization. They are declared in `main/FatesInterfaceTypesMod.F90` and remain constant for the run.

### Critical Configuration Flags

| Parameter | Type | Purpose | Source |
|-----------|------|---------|--------|
| `hlm_name` | `character(16)` | Identifies the host model for I/O filtering | `main/FatesInterfaceTypesMod.F90:41` |
| `hlm_is_restart` | integer | Signals restart vs cold-start initialization | `main/FatesInterfaceTypesMod.F90:37` |
| `hlm_parteh_mode` | integer | Plant allocation hypothesis (1=C-only, 2=CNP) | `main/FatesInterfaceTypesMod.F90:94` |
| `hlm_use_planthydro` | integer | Enable plant hydraulics | `main/FatesInterfaceTypesMod.F90:143` |
| `hlm_use_nocomp` | integer | No-competition mode | `main/FatesInterfaceTypesMod.F90:191` |
| `hlm_use_sp` | integer | Satellite phenology (prescribed LAI) | `main/FatesInterfaceTypesMod.F90:194` |
| `hlm_use_fixed_biogeog` | integer | Fixed biogeography (PFT areas from surface dataset) | `main/FatesInterfaceTypesMod.F90:188` |
| `hlm_use_inventory_init` | integer | Initialize from inventory files (PSS/CSS) | `main/FatesInterfaceTypesMod.F90:175` |
| `hlm_use_lu_harvest` | integer | Use land-use harvest from HLM | `main/FatesInterfaceTypesMod.F90:114` |
| `hlm_spitfire_mode` | integer | Fire model configuration | `main/FatesInterfaceTypesMod.F90:110` |
| `hlm_use_tree_damage` | integer | Enable tree damage module | `main/FatesInterfaceTypesMod.F90:152` |
| `hlm_numSWb` | integer | Number of shortwave radiation bands (typically 2) | `main/FatesInterfaceTypesMod.F90:24` |
| `hlm_maxlevsoil` | integer | Maximum number of soil layers | `main/FatesInterfaceTypesMod.F90:34` |
| `hlm_stepsize` | `real(r8)` | HLM timestep (s) — shortest timestep at which FATES is called | `main/FatesInterfaceTypesMod.F90:73` |

Binary flags use `0=off (ifalse) / 1=on (itrue)`; `hlm_spitfire_mode` selects a configuration.

### Fire Mode Configurations

| Mode Constant | Description |
|---------------|-------------|
| `hlm_sf_nofire_def` | Fire module disabled |
| `hlm_sf_scalar_lightning_def` | Constant lightning ignition rate |
| `hlm_sf_successful_ignitions_def` | Lightning ignitions from dataset |
| `hlm_sf_anthro_ignitions_def` | Anthropogenic ignition from dataset |

Source: `main/FatesInterfaceTypesMod.F90:127-130`.

## Initialization Sequence

The host model interface initialization follows a strict sequence to ensure all components are properly configured before the first timestep.

| Function | Module | Source | Purpose |
|----------|--------|--------|---------|
| `FatesInterfaceInit` | `FatesInterfaceMod` | `main/FatesInterfaceMod.F90:188` | Initialize global FATES logging state |
| `SetFatesGlobalElements1` | `FatesInterfaceMod` | `main/FatesInterfaceMod.F90:737` | Read parameters, determine PFT count, compute `maxpatch_*` |
| `SetFatesGlobalElements2` | `FatesInterfaceMod` | `main/FatesInterfaceMod.F90:808` | Finalize dimensions, set nutrient uptake modes |
| `allocate_bcin`, `allocate_bcout` | `FatesInterfaceMod` | `main/FatesInterfaceMod.F90:412`, `569` | Allocate boundary-condition arrays |
| `init_site_vars` | `EDInitMod` | `main/EDInitMod.F90:117` | Allocate site-level arrays |
| `zero_site` | `EDInitMod` | `main/EDInitMod.F90:222` | Initialize site variables to defaults |
| `init_patches` | `EDInitMod` | `main/EDInitMod.F90:534` | Create initial patch/cohort structure |
| `set_site_properties` | `EDInitMod` | `main/EDInitMod.F90:354` | Set initial phenology, fire, and biogeography state |

## Data Exchange During Timesteps

Each model timestep involves a sequence of data transfers through the interface:

1. HLM populates `bc_in` for each site
2. HLM calls FATES sub-daily routines (photosynthesis, radiation)
3. Once per day HLM calls `ed_ecosystem_dynamics()` `(main/EDMainMod.F90:141)`
4. FATES updates `bc_out` for each site
5. HLM uses `bc_out` for its surface energy balance, hydrology, soil BGC

The boundary conditions are zeroed at the start of each dynamics step via `zero_bcs()` `(main/FatesInterfaceMod.F90:271-408)`.

## Zero and Set Functions

### `zero_bcs`

Resets all boundary-condition arrays to zero at the beginning of each timestep, ensuring no stale data persists between timesteps. Source: `main/FatesInterfaceMod.F90:271-408`.

### `set_bcs`

Sets boundary conditions that are determined by FATES parameters rather than HLM state (e.g., soil salinity from parameter file). Source: `main/FatesInterfaceMod.F90:708-733`.

## Thread Safety and Multi-Site Execution

The interface supports multi-threaded execution where each thread manages a subset of sites:

- Each site has its own `bc_in` and `bc_out` instance.
- `bc_pconst` is shared across all sites (read-only after initialization).
- No inter-site communication during dynamics — sites are independent.
- Seed dispersal across sites occurs at end of day/month/year depending on `hlm_seeddisp_cadence` `(main/FatesInterfaceTypesMod.F90:97)`.

## Special Modes

### Satellite Phenology (SP) Mode

When `hlm_use_sp == itrue`, FATES reads prescribed LAI from the HLM rather than simulating leaf dynamics. The relevant `bc_in` fields are `hlm_sp_tlai`, `hlm_sp_tsai`, and `hlm_sp_htop`. FATES propagates these values to cohorts via `satellite_phenology()` in `EDPhysiologyMod`, called from `ed_ecosystem_dynamics()` at `main/EDMainMod.F90:205`.

In SP mode, `SetFatesGlobalElements1` sets `maxpatch_primary = fates_numpft`, `maxpatch_secondary = 0`, and `maxpatch_total = fates_numpft` `(main/FatesInterfaceMod.F90:768-770)`, so each PFT gets its own patch.

### No-Competition Mode

When `hlm_use_nocomp == itrue`, each patch represents a single PFT and there is no inter-PFT competition. Patch areas are driven by `bc_in%pft_areafrac(:)` when `hlm_use_fixed_biogeog == itrue`; otherwise area is determined by dynamics. No patch fusion or disturbance-driven patch creation is performed in this mode.

Note: despite the name, `hlm_use_nocomp` does *not* freeze PFT areas by itself; it separates PFTs into distinct patches so they do not compete within a patch. Area fixing requires `hlm_use_fixed_biogeog` as well. Source: `main/FatesInterfaceTypesMod.F90:191`, `main/EDInitMod.F90:619-655`.

## Summary

The Host Model Interface provides a clean separation between FATES ecosystem dynamics and host land model infrastructure:

- **Generic API** — the same interface works with CLM, ALM, ELM, and future HLMs.
- **Explicit boundaries** — all data exchange flows through `bc_in`, `bc_out`, and `bc_pconst` structures.
- **Flexible configuration** — a small set of `hlm_*` flags controls which modules and modes are active.
- **Dimension independence** — FATES manages its own patch/cohort structure; the HLM only sees fluxes and aggregate properties.
- **Restart support** — see [Restart System](../output/restart.md).
