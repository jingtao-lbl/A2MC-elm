# Simulation Modes

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/EDCohortDynamicsMod.F90`
- `biogeochem/EDPhysiologyMod.F90`
- `biogeochem/FatesAllometryMod.F90` (`leafc_from_treelai`)
- `main/FatesInterfaceMod.F90`
- `main/FatesInterfaceTypesMod.F90`
- `main/FatesConstantsMod.F90`

</details>

## Overview

FATES supports several alternative simulation modes that modify its standard ecosystem dynamics. This page documents the three primary modes (satellite phenology, no-competition, fixed biogeography) plus the two experimental modes (prescribed physiology and static stand structure). All are controlled by integer flags declared in `FatesInterfaceTypesMod.F90:177-216`, set by the host land model (ELM or CLM) during initialization. For the daily dynamics loop that these modes modify, see `../core-dynamics/daily_loop.md`.

## Satellite Phenology (SP) Mode

### Purpose and Behaviour

SP mode drives FATES with prescribed leaf area index (LAI), stem area index (SAI), and canopy height instead of prognostic allocation and growth. It is useful for isolating biogeochemical processes from structural dynamics and for reproducing satellite-driven experiments.

**Control flag:** `hlm_use_sp` at `main/FatesInterfaceTypesMod.F90:216`.

When SP mode is on:

- LAI, SAI, and canopy height come from the host land model boundary conditions (`hlm_sp_tlai`, `hlm_sp_tsai`, `hlm_sp_htop`, declared in the boundary condition input type).
- Leaf carbon is reverse-engineered from the prescribed LAI by `leafc_from_treelai()` in `biogeochem/FatesAllometryMod.F90:890`.
- The normal `phenology()` call is replaced by `satellite_phenology()` (implementation in `biogeochem/EDPhysiologyMod.F90:1768`; the `public ::` declaration is at line 154).
- Each patch holds exactly one PFT.
- Growth, recruitment, and mortality are bypassed.
- Photosynthesis and respiration still run, driven by the prescribed canopy structure.

Sources: `main/FatesInterfaceTypesMod.F90:216`, `biogeochem/EDPhysiologyMod.F90` (declarations at 154-156, implementations at 1768, 1892, 1974).

### Boundary Conditions for SP Mode

Three arrays are passed from the host land model into FATES each time step:

| Variable | Type | Units | Description |
|---|---|---|---|
| `hlm_sp_tlai` | `real(r8)` | m2/m2 | Total leaf area index |
| `hlm_sp_tsai` | `real(r8)` | m2/m2 | Total stem area index |
| `hlm_sp_htop` | `real(r8)` | m | Canopy height |

They are stored per PFT in the `bc_in_type` structure inside `main/FatesInterfaceTypesMod.F90`.

### SP Key Subroutines

| Subroutine | Role | Implementation |
|---|---|---|
| `satellite_phenology()` | Replaces `phenology()` in the daily dynamics loop. Assigns prescribed LAI and SAI to cohorts. | `biogeochem/EDPhysiologyMod.F90` (public declaration at line 154, body at line 1768) |
| `assign_cohort_SP_properties()` | Maps patch-level boundary conditions to individual cohorts | public declaration at `EDPhysiologyMod.F90:155`, body at line 1974 |
| `calculate_SP_properties()` | Computes derived structural properties needed by biophysics | declaration at `EDPhysiologyMod.F90:156`, body at line 1892 |
| `leafc_from_treelai()` | Inverts the normal `tree_lai` calculation to obtain leaf carbon from prescribed LAI, accounting for SLA variation with canopy depth | `biogeochem/FatesAllometryMod.F90:890-977` |

### Patch Structure

In SP mode each PFT maps to one patch. The host-land-model side may allocate more patches than FATES to hold LAI data for additional crop functional types in the surface dataset. In ELM/CLM:

```
fates_maxPatchesPerSite = max(surf_numpft + surf_numcft, maxpatch_total + 1)
```

This ensures LAI slots exist for every PFT and CFT in the surface dataset even if FATES tracks fewer.

Sources: `main/FatesInterfaceMod.F90`.

## No-Competition Mode

### Purpose and Behaviour

No-competition mode runs FATES with prognostic dynamics (growth, mortality, recruitment), but eliminates **inter-PFT** competition by segregating each PFT into its own patch. Within a patch, cohorts of the same PFT still compete with each other for light according to the Perfect Plasticity Approximation canopy rules.

**Control flag:** `hlm_use_nocomp` at `main/FatesInterfaceTypesMod.F90:213`.

**Important semantic point:** `hlm_use_nocomp = 1` **does not fix PFT area fractions**. It only separates PFTs into their own patches so they cannot compete for light, water, or nutrients within a patch. The individual patches can still grow or shrink through disturbance, and their total areas evolve according to the standard FATES patch dynamics. To also fix PFT area fractions you must additionally set `hlm_use_fixed_biogeog = 1`.

When no-competition mode is enabled:

- Each PFT occupies a separate patch.
- Patches do not compete for light, water, or nutrients.
- Full dynamics (growth, recruitment, mortality, phenology) still operate inside each patch.
- Cohorts within a patch compete by size and canopy position as usual.
- The mode is usually combined with fixed biogeography (see below) for benchmarking.

Sources: `main/FatesInterfaceTypesMod.F90:213`, `biogeochem/EDPhysiologyMod.F90`.

### Patch Labelling

Each patch is labelled with its PFT identity through `nocomp_pft_label_pa(:)` in the boundary conditions (`main/FatesInterfaceTypesMod.F90:770`). The special integer `nocomp_bareground = 0` in `FatesConstantsMod.F90:64` identifies the bare-ground patch.

Sources: `main/FatesInterfaceTypesMod.F90:770`, `main/FatesConstantsMod.F90:64`.

### No-Competition vs Default

| Aspect | Default competition | No-competition |
|---|---|---|
| Patch structure | Multiple PFTs per patch | One PFT per patch |
| PFT interactions | Competition for light, water, nutrients | Isolated by patch |
| Within-PFT competition | Yes (by size and canopy position) | Yes (by size and canopy position) |
| Patch dynamics | Disturbance creates and merges patches | Same, operating within each PFT |
| Area allocation | Emergent from competition and disturbance | Emergent or prescribed (with `fixed_biogeog`) |
| Use case | Realistic ecosystem dynamics | PFT performance, benchmarking |

## Fixed Biogeography Mode

### Purpose and Behaviour

Fixed biogeography mode prescribes each PFT's fractional area from the surface dataset rather than letting it emerge from dynamics.

**Control flag:** `hlm_use_fixed_biogeog` at `main/FatesInterfaceTypesMod.F90:210`.

Area fractions are provided through two boundary-condition arrays in the `bc_in_type` (`main/FatesInterfaceTypesMod.F90:593-596`):

- `pft_areafrac(:)` Fractional area of the FATES column occupied by each PFT (1-D, indexed by PFT)
- `pft_areafrac_lu(:,:)` **New at api 43.** Fractional area occupied by each PFT on each land use type (2-D, indexed by PFT and by land-use class). Used when fixed-biogeography mode is combined with the new land-use infrastructure (`fates_landuseclass = 5` classes: `primaryland`, `secondaryland`, `rangeland`, `pastureland`, `cropland`; see `parameter_files/fates_params_default.json` parameter `fates_landuseclass_name`).

This mode is typically combined with no-competition for a stable, benchmark-style configuration. The 2-D `pft_areafrac_lu` array supports land-use-resolved benchmarking that did not exist at e85d997.

Sources: `main/FatesInterfaceTypesMod.F90:210, 593-596`.

## Prescribed Physiology Mode (Experimental)

### Purpose and Behaviour

Prescribed physiology mode disables photosynthesis and respiration and replaces them with prescribed net primary production. This is a placeholder / experimental mode used for benchmarking demographic processes.

**Control flag:** `hlm_use_ed_prescribed_phys` at `main/FatesInterfaceTypesMod.F90:187`.

### Key Parameters (JSON Names)

These are the FATES parameter-file names, not derived-type field names:

| JSON parameter | Units | Default (uniform across 14 PFTs) | Role |
|---|---|---|---|
| `fates_prescribed_npp_canopy` | kgC / m2 / yr | 0.4 | Canopy NPP |
| `fates_prescribed_npp_understory` | kgC / m2 / yr | 0.03125 | Understory NPP |
| `fates_mort_prescribed_canopy` | 1/yr | 0.0194 | Canopy mortality rate |
| `fates_mort_prescribed_understory` | 1/yr | 0.025 | Understory mortality rate |
| `fates_recruit_prescribed_rate` | n/yr | 0.02 | Recruitment rate |

Sources: parameter file by name (`fates_prescribed_npp_canopy`, `fates_prescribed_npp_understory`, `fates_mort_prescribed_canopy`, `fates_mort_prescribed_understory`, `fates_recruit_prescribed_rate`).

Constraints:

- Cannot combine with ST3 mode.
- Requires that every demographic rate be prescribed.

## Static Stand Structure Mode (ST3, Experimental)

ST3 mode freezes ecosystem structure by disabling all demographic processes, leaving only fast biophysics active.

**Control flag:** `hlm_use_ed_st3` at `main/FatesInterfaceTypesMod.F90:177`.

Disabled processes: growth, mortality (all types), recruitment, disturbance-driven patch creation, cohort fusion and termination.

Active processes: photosynthesis, respiration, phenology (leaf flush and abscission), plant hydraulics, radiation transfer, canopy layering adjustments from phenology.

Constraints:

- Cannot be combined with prescribed physiology mode.
- Initial stand structure must come from inventory or near-bare-ground initialization.
- Patch areas remain constant.

## Mode Interactions and Configuration

### Valid Mode Combinations

| SP | nocomp | fixed_biogeog | Dynamics | PFT competition | Area allocation |
|---|---|---|---|---|---|
| off | off | off | full | yes | emergent |
| off | on | on | full | none | prescribed |
| off | on | off | full | none (patches still evolve) | emergent |
| on | (not applicable) | (not applicable) | prescribed canopy | none | prescribed |

SP mode inherently implies no PFT competition and prescribed canopy structure, so the other flags are not meaningful when SP is on.

Sources: `main/FatesInterfaceMod.F90`.

### Runtime Flag Storage

All flags are stored as module-level integers in `FatesInterfaceTypesMod`:

- `hlm_use_sp` at `main/FatesInterfaceTypesMod.F90:216`
- `hlm_use_nocomp` at `main/FatesInterfaceTypesMod.F90:213`
- `hlm_use_fixed_biogeog` at `main/FatesInterfaceTypesMod.F90:210`
- `hlm_use_ed_prescribed_phys` at `main/FatesInterfaceTypesMod.F90:187` (experimental)
- `hlm_use_ed_st3` at `main/FatesInterfaceTypesMod.F90:177` (experimental)

They use the boolean integer constants `itrue = 1` and `ifalse = 0` from `FatesConstantsMod.F90:28, 31`.

## Implementation Notes

### Bare Ground Handling

All modes maintain a bare-ground patch in addition to the vegetated patches. The `maxpatch_total` variable does not include bare ground, but `fates_maxPatchesPerSite` adds 1 to account for it:

```
fates_maxPatchesPerSite = maxpatch_total + 1
```

In no-competition mode, the integer constant `nocomp_bareground = 0` (`FatesConstantsMod.F90:64`) identifies the bare-ground patch.

### Surface Dataset Compatibility

In SP mode, the host-land-model side must allocate enough patches to hold LAI data for every PFT and crop functional type in the surface dataset:

```
fates_maxPatchesPerSite = max(surf_numpft + surf_numcft, maxpatch_total + 1)
```

### Cohort Age Tracking

Cohort age tracking (`hlm_use_cohort_age_tracking`, declared in `FatesInterfaceTypesMod.F90`) is typically disabled in SP mode because cohort age loses meaning when growth is bypassed.
