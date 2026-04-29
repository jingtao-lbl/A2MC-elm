---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

# Host Model Interface

## Purpose and Scope

The Host Model Interface (HMI) defines the coupling layer between FATES and host land models (HLMs) such as CLM, ALM, and ELM. This interface establishes the API through which the HLM controls FATES execution, passes environmental drivers and boundary conditions, and receives vegetation state and flux information. The HMI is intentionally generic, the same FATES internal implementation can couple to multiple host models without modification.

This page covers the boundary condition structures, interface data types, and coupling mechanisms. For initialization modes (near-bare-ground, inventory, restart), see [Initialization Modes](initialization.md). For parameter file handling, see [Parameter System](parameter_system.md).

## Interface Architecture Overview

The host model interface is implemented primarily through three modules:

- `main/FatesInterfaceMod.F90` — runtime interface, boundary-condition allocation and zeroing, JSON parameter loading, `FatesTransferParameters` driver
- `main/FatesInterfaceTypesMod.F90` — global flag and boundary-condition type declarations
- `main/FatesRestartInterfaceMod.F90` — restart I/O (covered in [Restart System](../output/restart.md))

A new module `main/JSONParameterUtilsMod.F90` (1272 lines) provides the JSON parsing engine; `main/FatesParametersInterface.F90` (76 lines) holds the module-level `pstruct` instance and two transpose helpers (`Transp2dInt`, `Transp2dReal`).

## The `fates_interface_type` Structure

`fates_interface_type` `(main/FatesInterfaceMod.F90:138)` is the root container for all FATES state and boundary conditions. Each HLM thread or domain instantiates one or more of these objects.

```fortran
type, public :: fates_interface_type
   integer                          :: nsites
   type(ed_site_type),  pointer     :: sites(:)
   type(bc_in_type),    allocatable :: bc_in(:)
   type(bc_out_type),   allocatable :: bc_out(:)
   type(bc_pconst_type)             :: bc_pconst
end type fates_interface_type
```

| Component | Purpose | Allocation |
|-----------|---------|------------|
| `sites(:)` | FATES site structures containing patches and cohorts | Per site |
| `bc_in(:)` | Input boundary conditions from HLM (meteorology, soil state, etc.) | Per site |
| `bc_out(:)` | Output boundary conditions to HLM (fluxes, canopy properties) | Per site |
| `bc_pconst` | Parameter constants (nutrient uptake kinetics) | Once per interface |

Source: `main/FatesInterfaceMod.F90:138-172`.

## Boundary Condition System

### Input Boundaries (`bc_in_type`)

`bc_in_type` `(main/FatesInterfaceTypesMod.F90:383-606)` holds all environmental drivers and soil-state information that FATES requires from the HLM. These are updated each model timestep or sub-timestep.

Key input groups:

| Category | Key Variables | Units | Dimension |
|----------|---------------|-------|-----------|
| Radiation | `solad_parb`, `solai_parb` | W/m² | patch × band |
| Soil hydrology | `smp_sl`, `h2o_liqvol_sl`, `watsat_sl`, `eff_porosity_sl` | mm, m³/m³ | soil layer |
| Soil temperature | `tempk_sl`, `t_soisno_sl` | K | soil layer |
| Decomposition controls | `w_scalar_sisl`, `t_scalar_sisl` | fraction | soil layer |
| Atmosphere | `cair_pa`, `oair_pa`, `eair_pa` | Pa | patch |
| Snow | `snow_depth_si`, `frac_sno_eff_si`, `fcansno_pa` | m, fraction | site / patch |
| BGC accounting | `tot_het_resp`, `tot_somc`, `tot_litc` | gC/m²/s, gC/m² | site |
| Fire weather | `lightning24`, `pop_density`, `precip24_pa`, `wind24_pa`, `relhumid24_pa` | various | patch |
| Nutrient fluxes | `plant_nh4_uptake_flux`, `plant_no3_uptake_flux`, `plant_p_uptake_flux` | gN(P)/m²/day | competitor × layer |
| Land use | `hlm_harvest_rates`, `hlm_harvest_catnames`, `hlm_luh_states`, `hlm_luh_transitions` | — | category / state / transition |
| SP mode | `hlm_sp_tlai`, `hlm_sp_tsai`, `hlm_sp_htop` | m²/m², m | surface PFT |
| Fixed biogeo | `pft_areafrac`, `pft_areafrac_lu` | fraction | PFT (× land use) |

Sources: `main/FatesInterfaceTypesMod.F90:383-606`, `main/FatesInterfaceMod.F90:443-619` (`allocate_bcin`).

### Output Boundaries (`bc_out_type`)

`bc_out_type` `(main/FatesInterfaceTypesMod.F90:609-807)` holds vegetation state, canopy structure, and biogeochemical fluxes that FATES returns to the HLM for surface energy balance, hydrology, and soil BGC.

| Category | Key Variables | Units | Dimension |
|----------|---------------|-------|-----------|
| Canopy structure | `elai_pa`, `esai_pa`, `tlai_pa`, `tsai_pa`, `htop_pa`, `hbot_pa` | m²/m², m | patch |
| Radiation | `albd_parb`, `albi_parb`, `fabd_parb`, `fabi_parb`, `ftdd_parb`, `ftid_parb`, `ftii_parb` | fraction | patch × band |
| Hydrology | `rootr_pasl`, `btran_pa`, `active_suction_sl` | fraction | patch (× layer) |
| Stomatal conductance | `rssun_pa`, `rssha_pa` | s/m | patch |
| Litter fluxes | `litt_flux_cel_c_si`, `litt_flux_lig_c_si`, `litt_flux_lab_c_si` (and N, P analogues) | g/m³/s | decomp layer |
| Nutrient competition | `veg_rootc`, `decompmicc`, `ft_index`, `cn_scalar`, `cp_scalar` | gC/m³, index, — | competitor (× layer) |
| BGC source terms | `source_nh4`, `source_p` | gN(P)/m³ | decomp layer |
| Site carbon stocks | `veg_c_si`, `litter_cwd_c_si`, `seed_c_si` | gC/m² | site |
| LULCC | `hrv_deadstemc_to_prod10c`, `hrv_deadstemc_to_prod100c` | gC/m²/s | site |
| CH4 inputs | `annavg_agnpp_pa`, `annavg_bgnpp_pa`, `frootc_pa`, `rootfr_pa` | various | patch (× layer) |

Sources: `main/FatesInterfaceTypesMod.F90:609-807`, `main/FatesInterfaceMod.F90:623-759` (`allocate_bcout`).

### Parameter Constants (`bc_pconst_type`)

`bc_pconst_type` `(main/FatesInterfaceTypesMod.F90:815-842)` holds parameters set once during initialization and read-only afterwards. These are primarily used for nutrient uptake kinetics in ECA (Equilibrium Chemistry Approximation) mode. Allocated in `allocate_bcpconst()` `(main/FatesInterfaceMod.F90:236-254)` and populated in `set_bcpconst()` `(main/FatesInterfaceMod.F90:258-278)`:

```
vmax_nh4, vmax_no3, vmax_p            ! uptake rate constants (per PFT)
eca_km_nh4, eca_km_no3, eca_km_p      ! half-saturation constants (per PFT)
eca_km_ptase, eca_vmax_ptase
eca_alpha_ptase, eca_lambda_ptase
j_uptake                               ! per soil decomp layer
eca_plant_escalar                      ! scalar (set in set_bcpconst at :275)
```

`set_bcpconst()` copies these from `EDPftvarcon_inst`, so any calibration that changes `fates_cnp_vmax_*` or `fates_cnp_eca_km_*` parameters flows through automatically.

## Host Model Configuration Parameters

FATES behavior is controlled by global flags set by the HLM during initialization. They are declared in `main/FatesInterfaceTypesMod.F90` and remain constant for the run.

### Critical Configuration Flags

| Parameter | Type | Purpose | Source |
|-----------|------|---------|--------|
| `hlm_name` | `character(16)` | Identifies the host model for I/O filtering | `main/FatesInterfaceTypesMod.F90:41` |
| `hlm_is_restart` | integer | Signals restart vs cold-start initialization | `main/FatesInterfaceTypesMod.F90:37` |
| `hlm_parteh_mode` | integer | Plant allocation hypothesis (1=C-only, 2=CNP) | `main/FatesInterfaceTypesMod.F90:85` |
| `hlm_use_planthydro` | integer | Enable plant hydraulics | `main/FatesInterfaceTypesMod.F90:142` |
| `hlm_use_nocomp` | integer | No-competition mode | `main/FatesInterfaceTypesMod.F90:213` |
| `hlm_use_sp` | integer | Satellite phenology (prescribed LAI) | `main/FatesInterfaceTypesMod.F90:216` |
| `hlm_use_fixed_biogeog` | integer | Fixed biogeography (PFT areas from surface dataset) | `main/FatesInterfaceTypesMod.F90:210` |
| `hlm_use_inventory_init` | integer | Initialize from inventory files (PSS/CSS) | `main/FatesInterfaceTypesMod.F90:197` |
| `hlm_use_lu_harvest` | integer | Use land-use harvest from HLM | `main/FatesInterfaceTypesMod.F90:107` |
| `hlm_use_luh` | integer | Use LUH2 land-use drivers | `main/FatesInterfaceTypesMod.F90:119` |
| `hlm_spitfire_mode` | integer | Fire model configuration | `main/FatesInterfaceTypesMod.F90:101` |
| `hlm_use_tree_damage` | integer | Enable tree damage module | `main/FatesInterfaceTypesMod.F90:151` |
| `hlm_numSWb` | integer | Number of shortwave radiation bands (typically 2) | `main/FatesInterfaceTypesMod.F90:24` |
| `hlm_maxlevsoil` | integer | Maximum number of soil layers | `main/FatesInterfaceTypesMod.F90:34` |
| `hlm_stepsize` | `real(r8)` | HLM timestep (s), shortest timestep at which FATES is called | `main/FatesInterfaceTypesMod.F90:64` |
| `hlm_seeddisp_cadence` | integer | Seed dispersal cadence (0=none, 1=daily, 2=monthly, 3=yearly) | `main/FatesInterfaceTypesMod.F90:88` |
| `hlm_radiation_model` | integer | Radiation model (1=Norman, 2=Two-stream) | `main/FatesInterfaceTypesMod.F90:169` |
| `hlm_maintresp_leaf_model` | integer | Leaf maintenance respiration model (1=Ryan 1991, 2=Atkin 2017) | `main/FatesInterfaceTypesMod.F90:162` |
| `hlm_mort_cstarvation_model` | integer | C-starvation mortality (1=Linear, 2=Exponential) | `main/FatesInterfaceTypesMod.F90:165` |
| `hlm_regeneration_model` | integer | Regeneration model (1=default, 2=TRS, 3=TRS-no-seedlings) | `main/FatesInterfaceTypesMod.F90:172` |

Binary flags use `0=off (ifalse) / 1=on (itrue)`. Mode-selector integers use a small enumerated set per flag.

### Fire Mode Configurations

| Mode Constant | Description |
|---------------|-------------|
| `hlm_sf_nofire_def` | Fire module disabled |
| `hlm_sf_scalar_lightning_def` | Constant lightning ignition rate |
| `hlm_sf_successful_ignitions_def` | Lightning ignitions from dataset |
| `hlm_sf_anthro_ignitions_def` | Anthropogenic ignition from dataset |

Source: `main/FatesInterfaceTypesMod.F90:126-129`.

## Initialization Sequence

The host model interface initialization follows a strict sequence to ensure all components are properly configured before the first timestep.

| Function | Module | Source | Purpose |
|----------|--------|--------|---------|
| `FatesInterfaceInit` | `FatesInterfaceMod` | `main/FatesInterfaceMod.F90:199` | Initialize global FATES logging state |
| `SetFatesGlobalElements1` | `FatesInterfaceMod` | `main/FatesInterfaceMod.F90:792` | `JSONRead`, `FatesTransferParameters`, determine `numpft`, compute `maxpatches_by_landuse` |
| `SetFatesGlobalElements2` | `FatesInterfaceMod` | `main/FatesInterfaceMod.F90:897` | Finalize dimensions, set `n_uptake_mode`, `p_uptake_mode`, `nleafage`, init PARTEH globals |
| `allocate_bcin`, `allocate_bcout` | `FatesInterfaceMod` | `main/FatesInterfaceMod.F90:443`, `:623` | Allocate boundary-condition arrays |
| `init_site_vars` | `EDInitMod` | `main/EDInitMod.F90:131` | Allocate site-level arrays |
| `zero_site` | `EDInitMod` | `main/EDInitMod.F90:278` | Initialize site variables to defaults |
| `init_patches` | `EDInitMod` | `main/EDInitMod.F90:690` | Create initial patch/cohort structure |
| `set_site_properties` | `EDInitMod` | `main/EDInitMod.F90:439` | Set initial phenology, fire, and biogeography state |

## Data Exchange During Timesteps

Each model timestep involves a sequence of data transfers through the interface:

1. HLM populates `bc_in` for each site
2. HLM calls FATES sub-daily routines (photosynthesis, radiation)
3. Once per day HLM calls `ed_ecosystem_dynamics()` `(main/EDMainMod.F90:148)`
4. FATES updates `bc_out` for each site
5. HLM uses `bc_out` for its surface energy balance, hydrology, soil BGC

The boundary conditions are zeroed at the start of each dynamics step via `zero_bcs()` `(main/FatesInterfaceMod.F90:282-439)`.

## Zero and Set Functions

### `zero_bcs`

Resets all boundary-condition arrays to zero at the beginning of each timestep, ensuring no stale data persists between timesteps. Source: `main/FatesInterfaceMod.F90:282-439`. The routine zeros radiation, hydrology, soil temperature/moisture, snow, BGC accounting, and (when active) plant-hydro and salinity fields.

### `set_bcs`

Sets boundary conditions that are determined by FATES parameters rather than HLM state (e.g., soil salinity from parameter file). Source: `main/FatesInterfaceMod.F90:763-788`.

## Thread Safety and Multi-Site Execution

The interface supports multi-threaded execution where each thread manages a subset of sites:

- Each site has its own `bc_in` and `bc_out` instance.
- `bc_pconst` is shared across all sites (read-only after initialization).
- No inter-site communication during dynamics, sites are independent.
- Seed dispersal across sites occurs at end of day/month/year depending on `hlm_seeddisp_cadence` `(main/FatesInterfaceTypesMod.F90:88)`.

## Special Modes

### Satellite Phenology (SP) Mode

When `hlm_use_sp == itrue`, FATES reads prescribed LAI from the HLM rather than simulating leaf dynamics. The relevant `bc_in` fields are `hlm_sp_tlai`, `hlm_sp_tsai`, and `hlm_sp_htop`. FATES propagates these values to cohorts via `satellite_phenology()` in `EDPhysiologyMod`, called from `ed_ecosystem_dynamics()` at `main/EDMainMod.F90:210`.

In SP mode, `SetFatesGlobalElements1` sets `maxpatches_by_landuse(primaryland) = fates_numpft`, `maxpatches_by_landuse(secondaryland:n_landuse_cats) = 0`, and `maxpatch_total = fates_numpft` `(main/FatesInterfaceMod.F90:851-862)`, so each PFT gets its own primary patch. The earlier scalars `maxpatch_primary` and `maxpatch_secondary` no longer exist; they have been replaced by the array `maxpatches_by_landuse(n_landuse_cats)` declared at `main/EDParamsMod.F90:152` (`n_landuse_cats = 5`).

### No-Competition Mode

When `hlm_use_nocomp == itrue`, each patch represents a single PFT and there is no inter-PFT competition. Patch areas are driven by `bc_in%pft_areafrac(:)` when `hlm_use_fixed_biogeog == itrue`; otherwise area is determined by dynamics. No patch fusion or disturbance-driven patch creation is performed in this mode.

Note: despite the name, `hlm_use_nocomp` does *not* freeze PFT areas by itself, it separates PFTs into distinct patches so they do not compete within a patch. Area fixing requires `hlm_use_fixed_biogeog` as well. Source: `main/FatesInterfaceTypesMod.F90:213`, `main/EDInitMod.F90:786-790`.

## Summary

The Host Model Interface provides a clean separation between FATES ecosystem dynamics and host land model infrastructure:

- **Generic API** — the same interface works with CLM, ALM, ELM, and future HLMs.
- **Explicit boundaries** — all data exchange flows through `bc_in`, `bc_out`, and `bc_pconst` structures.
- **Flexible configuration** — a small set of `hlm_*` flags controls which modules and modes are active.
- **One-shot JSON parameter loading** — the parameter file is read and distributed in a single `SetFatesGlobalElements1` call (no longer two-phase Register/Receive).
- **Dimension independence** — FATES manages its own patch/cohort structure, the HLM only sees fluxes and aggregate properties.
- **Restart support** — see [Restart System](../output/restart.md).
