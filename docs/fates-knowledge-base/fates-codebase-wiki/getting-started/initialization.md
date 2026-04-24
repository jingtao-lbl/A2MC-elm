---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Initialization Modes

## Purpose and Scope

FATES supports three initialization modes that determine the initial state of vegetation, patches, and cohorts at the beginning of a model run. This document describes all three and how FATES selects between them. Initialization is separate from the daily dynamics loop (see [Daily Dynamics Loop](../core-dynamics/daily_loop.md)) and the parameter loading system (see [Parameter System](parameter_system.md)).

## Overview of Initialization Modes

The mode is controlled by two flags set by the host land model:

| Mode | Control | Description | Use Case |
|------|---------|-------------|----------|
| Near-Bare-Ground (NBG) | `hlm_use_inventory_init == ifalse` and `hlm_is_restart == ifalse` | Starts with minimal or no vegetation | Long spin-up runs, theoretical studies |
| Inventory | `hlm_use_inventory_init == itrue` | Initializes from forest-inventory data (PSS/CSS files) | Site-level studies with observed data |
| Restart | `hlm_is_restart == itrue` | Continues from a previous simulation checkpoint | Production runs, sensitivity experiments |

Both flags are declared in `main/FatesInterfaceTypesMod.F90` (lines 37, 175). Mode selection occurs during cold-start, before the daily dynamics loop begins; the HLM signals which mode to use via these flags.

## Initialization Mode Selection Flow

The top-level entry for NBG vs inventory is `init_patches()` `(main/EDInitMod.F90:534)`:

```fortran
if ( hlm_use_inventory_init .eq. itrue ) then
   call initialize_sites_by_inventory(nsites,sites,bc_in)   ! main/FatesInventoryInitMod.F90:113
else
   ! Near-Bare-Ground: create default patches and init_cohorts
   ...
end if
```

Restart mode takes a different entry into FATES from the HLM's restart read path (see `main/FatesRestartInterfaceMod.F90`); it bypasses `init_patches` entirely.

## Near-Bare-Ground Initialization

NBG initialization creates a minimal vegetation state, suitable for long spin-up runs or when no inventory data is available.

### Process Overview

1. `init_patches()` `(main/EDInitMod.F90:534)` is called by the HLM.
2. For each site it sets `spread = init_spread_near_bare_ground`, zeroes `sp_tlai/tsai/htop`, and determines whether to create one patch or one patch per PFT (nocomp mode) `(main/EDInitMod.F90:609-655)`.
3. A set of default patches is created, and for each patch `init_cohorts()` `(main/EDInitMod.F90:807)` is called to create small seedling cohorts using PFT parameter defaults.

### Cohort Initialization Parameters

`init_cohorts()` sets each cohort's initial state from PFT parameters and allometry functions:

| Parameter | Source | Description |
|-----------|--------|-------------|
| `dbh` | PFT parameter | Initial diameter at breast height (cm) |
| `n` | Computed | Number of individuals per patch |
| `height` | `h_allom()` | Calculated from DBH |
| `c_area` | `carea_allom()` | Crown area |
| `leaf_status` | Phenology | Initial leaf on/off state |
| `prt` | PARTEH | Biomass pools initialized via `InitPRTObject` |

Source: `main/EDInitMod.F90:807-1037`.

## Inventory Initialization

Inventory initialization lets FATES start from observed forest structure data, typically for site-level simulations where measurements are available. The entry point is `initialize_sites_by_inventory()` `(main/FatesInventoryInitMod.F90:113)`.

### File Structure

Inventory initialization uses:

- A control file listing sites, their lat/lon, and paths to PSS/CSS files
- One PSS file per site (patch structure)
- One CSS file per site (cohort structure)

### Inventory Control File Format

Parsed in `assess_inventory_sites()` `(main/FatesInventoryInitMod.F90:597)`:

| Field | Type | Description |
|-------|------|-------------|
| format | integer | Format version (1 = legacy ED format) |
| latitude | float | Geographic latitude of site |
| longitude | float | Geographic longitude of site |
| pss_path | string | Full path to patch file |
| css_path | string | Full path to cohort file |

### PSS File Format (Patch Structure, Type 1)

| Field | Units | Description |
|-------|-------|-------------|
| time | year | Year of measurement |
| patch | string | Unique patch identifier |
| trk | integer | Land use type (0=non-forest, 1=secondary, 2=primary) |
| age | years | Time since disturbance |
| area | fraction | Fraction of site occupied by patch |
| fsc | kg/m² | Fast soil carbon |
| stsc | kg/m² | Structural soil carbon |
| stsl | kg/m² | Structural soil lignin |
| ssc | kg/m² | Slow soil carbon |
| msn | kg/m² | Mineralized soil nitrogen |
| fsn | kg/m² | Fast soil nitrogen |

Source: `main/FatesInventoryInitMod.F90:732-841` (PSS reader).

### CSS File Format (Cohort Structure, Type 1)

One line per cohort:

| Field | Units | Description |
|-------|-------|-------------|
| time | year | Year of measurement |
| patch | string | Patch identifier (links to PSS) |
| cohort | integer | Cohort number within patch |
| dbh | cm | Diameter at breast height |
| height | m | Tree height |
| pft | integer | Plant functional type |
| n | plants/patch | Number of individuals |
| bdead | kgC/plant | Structural biomass per plant |
| balive | kgC/plant | Live biomass per plant |

`set_inventory_edcohort_type1()` `(main/FatesInventoryInitMod.F90:846)` reads CSS records and creates cohorts with initialized PARTEH objects.

### Site Matching Algorithm

FATES matches each model grid cell to the nearest inventory site using Euclidean distance in latitude-longitude space. The tolerance is `max_site_adjacency_deg = 0.05` degrees `(main/FatesInventoryInitMod.F90:99)`. If the distance exceeds this tolerance, the initialization aborts with a "separation must be less than 0.05 degrees" error `(main/FatesInventoryInitMod.F90:238-242)`.

## Restart Initialization

Restart initialization continues a simulation from a previously saved state, preserving all patch, cohort, and site-level variables. Restart I/O is implemented in `main/FatesRestartInterfaceMod.F90`.

### Restart System Architecture

The restart interface first calls the internal register / define routines to declare hundreds of restart variables, then the read path populates the site/patch/cohort hierarchy from the restart file. Entry points are around `main/FatesRestartInterfaceMod.F90:631-2918`.

### Key Restart Variable Categories

| Category | Example Variables |
|----------|-------------------|
| Site | `fates_PatchesPerSite`, `fates_gdd_site`, `fates_acc_nesterov_id` |
| Patch | `fates_CohortsPerPatch`, `fates_age_pa`, `fates_area_pa` |
| Cohort | `fates_dbh`, `fates_height`, `fates_nplant`, `fates_pft` |
| Phenology | `fates_cold_dec_status`, `fates_cold_leafondate` |
| Mortality | `fates_bmort`, `fates_cmort`, `fates_hmort` |
| PRT pools | Declared via `DefinePRTRestartVars` |
| Litter | `fates_leaf_litt`, `fates_agcwd_litt`, `fates_bgcwd_litt` |

See `main/FatesRestartInterfaceMod.F90` for the full registration and read/write routines.

## Configuration and Control

### Relevant Flags

Initialization behavior is controlled by several flags in `main/FatesInterfaceTypesMod.F90`:

| Flag | Values | Effect on Initialization |
|------|--------|--------------------------|
| `hlm_is_restart` | `itrue` / `ifalse` | If true, use restart mode |
| `hlm_use_inventory_init` | `itrue` / `ifalse` | If true, use inventory files |
| `hlm_inventory_ctrl_file` | file path | Location of inventory control file |
| `hlm_use_nocomp` | `itrue` / `ifalse` | Create separate patches per PFT (with `hlm_use_fixed_biogeog`, fixes PFT areas) |
| `hlm_use_sp` | `itrue` / `ifalse` | Satellite phenology mode — drives the one-patch-per-PFT layout |
| `hlm_use_fixed_biogeog` | `itrue` / `ifalse` | Use surface dataset PFT area fractions |

Flag sources: `main/FatesInterfaceTypesMod.F90:37-196`.

## Common Post-Initialization Steps

Regardless of initialization mode, several common steps occur after the initial state is established:

- `set_site_properties()` `(main/EDInitMod.F90:354)` sets initial phenology state, fire variables, and biogeography flags.
- Total carbon stocks are recorded as the baseline for mass balance via `SiteMassStock()`.
- Boundary conditions are zeroed and filled before the first daily dynamics call.

## Summary Table: Mode Comparison

| Aspect | Near-Bare-Ground | Inventory | Restart |
|--------|------------------|-----------|---------|
| Entry point | `init_patches` (`main/EDInitMod.F90:534`) | `initialize_sites_by_inventory` (`main/FatesInventoryInitMod.F90:113`) | Restart read (`main/FatesRestartInterfaceMod.F90`) |
| Patch count | 1 or `numpft` | From PSS file | From restart file |
| Cohort size | Small seedlings (from allometry) | From CSS file | From restart file |
| Litter pools | Zero | Zero (soil C from PSS columns) | From restart file |
| Phenology state | Default values | Default values | Restored from file |
| Fire variables | Zero | Zero | Restored from file |
| Typical use | Spin-up | Site studies | Continue runs |
| Typical runtime | Years to equilibrium | Months to years | Immediate |
