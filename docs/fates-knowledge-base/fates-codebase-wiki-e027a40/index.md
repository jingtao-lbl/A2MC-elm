---
**Source pin:** FATES commit `e027a40` (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit `d40b8431`
**Last verified:** 2026-04-25
---

# FATES Knowledge Base

**Functionally Assembled Terrestrial Ecosystem Simulator**

Technical documentation for FATES at api-43-1, pinned to a specific source commit so every line reference resolves to real code.

This is the canonical knowledge base for the A2MC `api-43-1` milestone (FATES `sci.1.91.1_api.43.1.0`, the version currently pinned by E3SM master). Built 2026-04-25 from a complete audit + rewrite of the prior `e85d997` (`api-31-0`) wiki against e027a40 source. The companion api-31-0 wiki at `fates-codebase-wiki-e85d997/` is retained for Kougarok manuscript reproducibility.

---

## Quick Navigation

### Core Documentation

| Section | Description |
|---------|-------------|
| [Model Overview](overview/model_overview.md) | Architecture, data structures, daily execution flow |
| [Getting Started](getting-started/index.md) | Host interface, JSON parameter loading, initialization |
| [Core Dynamics](core-dynamics/index.md) | 26-step daily loop, patch/cohort dynamics |

### Plant Processes

| Section | Description |
|---------|-------------|
| [Plant Physiology](plant-physiology/index.md) | Phenology (`fates_phen_leaf_habit`), allometry, mortality, autoresp |
| [PARTEH Allocation](plant-physiology/parteh/index.md) | Carbon and CNP allocation; PID controller (new gate) |
| [Canopy Structure](canopy-structure/index.md) | PPA, `nclmax = 3`, unified `PromoteOrDemote` |

### Biophysical Processes

| Section | Description |
|---------|-------------|
| [Biophysics](biophysics/index.md) | Radiation (new `radiation/` subdir + Two-Stream MLPE solver), photosynthesis (Newton-secant Ci solver in `LeafBiophysicsMod`), hydraulics |
| [Fire Dynamics](fire/index.md) | Refactored SPITFIRE pipeline + new managed/rx fire capability |
| [Logging](logging/index.md) | Harvest, land-use change, mortality |

### Technical Reference

| Section | Description |
|---------|-------------|
| [Output & Diagnostics](output/index.md) | 495-variable history inventory, mass balance, restart |
| [Advanced Topics](advanced/index.md) | Simulation modes, nutrient competition, CNP calibration guide |
| [Code Architecture](architecture/index.md) | Module organization, JSON loader, type-bound procedures |

---

## What's New at api-43-1 (vs. api-31-0)

The most calibration-relevant changes between e85d997 and e027a40:

| Change | Impact |
|---|---|
| **14 PFTs** (was 12) | New dedicated `broadleaf_evergreen_arctic_shrub` (10) and `broadleaf_colddecid_arctic_shrub` (11). `arctic_c3_grass` shifted from PFT#10 to PFT#12. New `cool_c3_grass` (13), `c4_grass` (14). |
| **JSON parameter file** | `parameter_files/fates_params_default.json` replaces the CDL/NetCDF format. Loader is `JSONRead + FatesTransferParameters()`; the two-phase `Register/Receive` API is gone. |
| **Default `fates_cnp_prescribed_n/puptake = 0.0`** | Defaults flipped from 1.0 (prescribed) to 0.0 (coupled). The "verify you're not in prescribed mode" calibration gotcha is now inverted. |
| **PID gate replaced** | `(spinup_state == 1 .and. yr > nyears_ad_carbon_only)` → `(coupled_*_uptake .and. .not. hlm_*_suppl)`. `nyears_ad_carbon_only` no longer exists. |
| **`nclmax` = 3** (was 2) | Max canopy layers increased; `Promote/Demote` merged into `PromoteOrDemote` dispatch. |
| **Phenology two-flag → integer** | `fates_phen_season_decid`/`stress_decid` collapsed into `fates_phen_leaf_habit` (integer 1-4). |
| **Photosynthesis Ci solver rewritten** | Old niter==5 / 2e-6 ppm tolerance loop in `FatesPlantRespPhotosynthMod` → Newton-secant + bisection in `LeafBiophysicsMod.F90:1325-1399`. |
| **Radiation refactored** | Legacy `EDSurfaceAlbedo` module removed; new `radiation/` subdir with Norman + alternative Two-Stream MLPE solver dispatched via HLM namelist `radiation_model`. |
| **SPITFIRE pipeline rewritten** | 10 old subroutines → 8 new in `fire/SFMainMod.F90` + `SFEquationsMod.F90`. New managed/rx fire capability via `FatesRxFireMod`. |
| **History variable churn (~30%)** | `*_SECONDARY` family removed (Land-Use replaces); `_Z` infix dropped; `FATES_AR*` → `FATES_AUTORESP*`; fire split into wildfire vs rx; 495 total variables now. |
| **Carbon-starvation 2-model selector** | `hlm_mort_cstarvation_model` chooses linear or exponential; new `fates_mort_upthresh_cstarvation` per-PFT param. |

---

## Key Topics for Calibration

### CNP Calibration
- [CNP Calibration Guide](advanced/cnp_calibration_guide.md) — rewritten for new defaults, PID gate, and 14-PFT layout.

### Parameter System
- [Parameter System](getting-started/parameter_system.md) — JSON loading + `FatesTransferParameters` flow (api.43+).
- [Parameter Management Tools](getting-started/parameter_tools.md) — refactored Python tools (`pft_index_swapper.py`, `sort_parameters.py`, `batch_patch_params.py`, `cdl_to_xml.py`).

### Nutrient Dynamics (CNP)
- [CNP Allocation](plant-physiology/parteh/cnp_allocation.md) — PID controller with new gate, ECA family expansion (8 new params).
- [Nutrient Competition](advanced/nutrient_competition.md) — ECA vs RD competition.
- [Soil-Plant Interface](plant-physiology/parteh/soil_plant_interface.md) — `UnPackNutrientAquisitionBCs` 4-arg signature.

### Plant Growth
- [Phenology](plant-physiology/phenology.md) — `fates_phen_leaf_habit` integer dispatch, drought phenology with new gates.
- [Allometry](plant-physiology/allometry.md) — power-law / Michaelis-Menten / Saldarriaga / Gao 2024 modes.
- [Mortality](plant-physiology/mortality.md) — selectable C-starvation model + frozen-soil hydraulic-failure gates.

### Fire (NEW)
- [Managed Fire](fire/managed_fire.md) — rx-fire capability added in api.41.

---

## Source Code References

All documentation in this knowledge base cites FATES source as `(path/from/fates/root.F90:NNN)` at commit `e027a40`. Line numbers have been verified against the source tree; if upstream code changes, regenerate this wiki rather than mutate it in place.

- FATES repository: https://github.com/NGEET/fates
- This knowledge base is pinned to commit `e027a40` (`sci.1.91.1_api.43.1.0`)
- HLM pairing: ELM at E3SM commit `d40b8431` (E3SM master, 2026-04-24)

---

## About This Knowledge Base

Generated 2026-04-25 from a 10-topic audit + rewrite workflow against FATES at e027a40 source. Replaces the earlier e85d997 wiki for the canonical A2MC `api-43-1` milestone. The companion `api-31-0` wiki at `fates-codebase-wiki-e85d997/` is retained for Kougarok manuscript reproducibility.

- **A2MC integration**: supports AI-assisted calibration workflows for `api-43-1` and forward.
- **RAG/GraphRAG**: structured for semantic search and retrieval.
- **Community use**: generic documentation for any FATES application at this version.

**Last verified:** 2026-04-25
