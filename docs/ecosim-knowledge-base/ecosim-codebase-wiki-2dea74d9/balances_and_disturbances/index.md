---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** `f90src/Balances/` and `f90src/Disturbances/`
**Last verified:** 2026-04-24
---

# Balances and disturbances overview

Two adjacent subsystems in the EcoSIM source tree cover "book-keeping" operations that run after physical/biological transport:

1. **Balances** (`f90src/Balances/`) -- mass-conservation diagnostics, end-of-step state redistribution, surface runoff accounting, lateral inter-grid transport glue, sedimentation, and soil-layer-geometry updates. These are not "physics" in the sense of computing new rates; they consume the fluxes computed by `HydroTherm`, `Transport`, `Microbial_bgc`, `Plant_bgc` and `Disturbances`, write updated state into the canonical arrays (`trcs_solml_vr`, `trcg_gasml_vr`, `VLWatMicP_vr`, `TKS_vr`, `SOM*`, etc.), and verify that the accounting closes.
2. **Disturbances** (`f90src/Disturbances/`) -- discrete or continuous management/perturbation events: soil warming (cable, IR, open-top chamber), erosion, fertilizer and manure application, fire, grazing and herbivory preparation, and tillage-based SOM removal. These modify state variables or force inputs; the actual bookkeeping of their mass-balance consequences is done through the Balances path after transport.

## Why these subsystems exist

The separation is functional, not arbitrary:

- **Balances** modules are diagnostic-first. Each is called after the core physics step and reconciles what *should* have happened (sum of fluxes computed upstream) against what the state arrays now contain. Conservation failures exceeding thresholds trigger `endrun` (see `f90src/ModelDiags/BalancesMod.F90:170-424` for the global end-of-step check, and the per-call checks inside `TranspNoSaltMod.F90:186-287`). This catches coding errors in any upstream physics module.
- **Disturbances** modules represent ecosystem events that are not continuous biogeochemistry. They are triggered on explicit conditions (solar-noon time of day for fertilizer and tillage, configured management-file entries for fire, event-specific date windows for soil warming, runoff and freeze-thaw thresholds for erosion) and modify multiple state variables atomically.

Neither subsystem exists only to produce outputs; both are structural. Removing balance checks would hide bugs. Removing disturbance hooks would deny the model the ability to simulate agriculture, fire-prone ecosystems, or manipulation experiments.

## Navigation

- [`mass_balance.md`](mass_balance.md) -- Documents `f90src/Balances/`: the seven modules that redistribute mass, close conservation checks, handle surface runoff and erosion bookkeeping, and perform tillage mixing.
- [`disturbances.md`](disturbances.md) -- Documents `f90src/Disturbances/`: the six modules that implement fertilizer/manure, fire, soil warming, erosion, plant grazing, and SOM removal by tillage or litter removal.

## External couplings at a glance

| Subsystem | Consumes | Produces | Called from |
|-----------|----------|----------|-------------|
| Balances/RedistMod | All fluxes from Transport, Microbial_bgc, Plant_bgc, Disturbances; water fluxes from HydroTherm | Updated `trcs_solml_vr`, `trcg_gasml_vr`, `CanopyFluxes`, column summaries | `drivers/ecosim/EcoSIMAPI.F90:113` (once per hour) |
| Balances/TillageMixMod | Management stream (`iSoilDisturbType_col`), soil state | Mixed SOM, nutrient, water, heat profiles | `RedistMod.F90:251` via `UpdateOutputVars` |
| Disturbances/FertilizerMod | Fertilizer input file `FERT`, management flags | Updated `trcs_solml_vr(ids_NH4,...)`, `trc_soHml_vr`, `CSoilOrgM_vr` (manure) | `f90src/Modelforc/Hour1Mod.F90:247` (once per hour, applied at solar noon) |
| Disturbances/EcosysWarmingMod | Warming-experiment config string, reference soil T | Modified `TKS_vr` (cable, IR) or canopy energy balance (OTC) | `f90src/Modelforc/WthrMod.F90:105-106`, `HydroTherm/SoilPhys/WatsubMod.F90:117` |
| Disturbances/ErosionMod | Runoff, freeze-thaw state, soil detachability | Lateral sediment flux, updated `SED_col` | `drivers/ecosim/EcoSIMAPI.F90:106` |
| Disturbances/FireMod | Management file `soil_mgmt_in`, year | `iSoilDisturbType_col = itill_fire` | `f90src/IOutils/readsmod.F90:235-239` (annual check) |
| Disturbances/SoilDisturbMod | `iSoilDisturbType_col` set by management or FireMod | Removed/combusted SOM, updated CNP and litter | `f90src/APIs/MicBGCAPI.F90:128` |
| Disturbances/PlantDisturbMod | `iHarvstType_pft` per-PFT harvest codes | Landscape-average grazable biomass per PFT (staging for plant model) | `f90src/APIs/PlantMod.F90:47` |

Together these subsystems account for roughly 3500 lines of source in Balances/ and 3000 lines in Disturbances/.
