# Model Extensibility

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

<details>
<summary>Relevant source files</summary>

- `main/EDPftvarcon.F90` (`TransferParamsPFT` reads PFT parameters via `pstruct%GetParamFromName`; `FatesCheckParams` validates them)
- `main/EDParamsMod.F90` (global / scalar parameter handling)
- `main/JSONParameterUtilsMod.F90` (`JSONRead` parses the JSON parameter file into a `params_type` structure)
- `main/FatesParametersInterface.F90` (parameter pass-through utilities)
- `main/FatesInterfaceMod.F90` (`FatesTransferParameters` dispatcher; PARTEH-mode `select case` blocks)
- `parteh/PRTGenericMod.F90` (PARTEH base class, organ and element constants, hypothesis IDs)
- `parteh/PRTAllometricCarbonMod.F90` (carbon-only allocation hypothesis, 6 state variables)
- `parteh/PRTAllometricCNPMod.F90` (CNP flexible allocation hypothesis, 18 state variables)
- `parteh/PRTLossFluxesMod.F90` (shared PARTEH loss fluxes)
- `parteh/PRTParamsFATESMod.F90` (`TransferParamsPRT` reads PARTEH parameters by name)
- `biogeochem/EDMortalityFunctionsMod.F90` (mortality dispatcher and per-mechanism rate computation)
- `biogeochem/FatesSoilBGCFluxMod.F90` (nutrient boundary conditions)
- `biogeophys/FatesPlantRespPhotosynthMod.F90` (biophysics module pattern)
- `parameter_files/fates_params_default.json` (ground-truth parameter list, JSON format at api 43)

</details>

## Purpose and Scope

This page explains how to extend FATES with new scientific hypotheses and parameterizations. It covers the main extensibility points: adding new PFTs and PFT parameters, adding new PARTEH allocation hypotheses, and adding new process models such as mortality mechanisms. For configuring existing model options, see `simulation_modes.md` and `nutrient_competition.md`. For the PARTEH allocation framework design, see `../plant-physiology/parteh/index.md`.

> **api 43 file format and loader changes (foundational read).** At api 43 the FATES parameter file moved from CDL (NetCDF Common Data Language) to JSON. The on-disk file is `parameter_files/fates_params_default.json`, parsed by `JSONRead` in `main/JSONParameterUtilsMod.F90:189`. The two-phase Register/Receive loader pattern (`Register_PFT`/`Receive_PFT` in `EDPftvarcon.F90`, and `PrtRegisterParams`/`PrtReceiveParams` in `PRTParamsFATESMod.F90`) is **gone**. Parameters are now copied directly from the parsed `pstruct` (a `params_type` from `JSONParameterUtilsMod`) into module storage by single subroutines: `TransferParamsPFT(pstruct)` at `EDPftvarcon.F90:306-...` for non-PARTEH PFT parameters, `TransferParamsPRT(pstruct)` at `PRTParamsFATESMod.F90:62-380` for PARTEH parameters, plus `TransferParamsGeneric`, `TransferParamsSpitFire`, `TransferParamsLeafBiophys`. The dispatcher is `FatesTransferParameters` at `FatesInterfaceMod.F90:2675-2694`, called once at init. Each parameter access uses `pstruct%GetParamFromName('<param_name>')`. CDL line citations from earlier wiki versions are no longer meaningful; reference parameters by name only.

## Extensibility Architecture Overview

FATES exposes three primary extension points:

| Extension point | Mechanism | Primary files |
|---|---|---|
| PFT parameters | JSON parameter file + `pstruct%GetParamFromName(...)` lookup pattern | `parameter_files/fates_params_default.json`, `main/EDPftvarcon.F90`, `parteh/PRTParamsFATESMod.F90` |
| Allocation hypotheses | Object-oriented PARTEH framework | `parteh/PRTGenericMod.F90`, `parteh/PRTAllometric*.F90` |
| Process models | Modular subroutines with standardized interfaces | `biogeochem/`, `biogeophys/`, `fire/` modules |

Sources: `main/EDPftvarcon.F90:306-...`, `parteh/PRTGenericMod.F90:1-100`, `main/JSONParameterUtilsMod.F90:1-251`.

## Adding New Plant Functional Types

### Parameter File Structure

PFTs are defined in the JSON parameter file `parameter_files/fates_params_default.json`. The file declares dimensions in a top-level `dimensions` block, then each parameter as a JSON object with `dtype`, `dims`, `long_name`, `units`, and `data` fields.

Key dimensions at e027a40 (`fates_params_info_e027a40.json:11-16`):

- `fates_pft = 14` (was 12 at e85d997; new arctic shrubs at PFT 10-11, plus split of grass into arctic/cool/C4 at PFT 12-14)
- `fates_plant_organs = 4` (was 6 at e85d997; the parameter-file organ axis was reduced to 4 slots; see `fates_alloc_organ_id = [1, 2, 3, 6]` and `fates_alloc_organ_name = ["leaf", "fine root", "sapwood", "structure"]`. Storage and reproductive organs are still tracked at runtime in `PRTGenericMod.F90:80-85` but no longer have per-PFT stoichiometry slots in the parameter file.)
- `fates_landuseclass = 5` (**new at api 43**; classes are `["primaryland", "secondaryland", "rangeland", "pastureland", "cropland"]`)
- `fates_hydr_organs = 4` (`["leaf", "stem", "transporting root", "absorbing root"]`)
- `fates_leafage_class`, `fates_litterclass`, `fates_fuel`, `fates_hlm_pftno`, `fates_history_*_bins`, `scalar`, and others.

Parameter categories in `parameter_files/fates_params_default.json` at e027a40 (reference by name; line numbers are not stable for JSON):

| Category | Example parameters |
|---|---|
| Allometry | `fates_allom_d2h1`, `fates_allom_d2bl1`, `fates_allom_l2fr` |
| CNP — uptake & demand | `fates_cnp_vmax_nh4`, `fates_cnp_vmax_no3`, `fates_cnp_vmax_p`, `fates_cnp_prescribed_nuptake`, `fates_cnp_prescribed_puptake` |
| CNP — ECA family | `fates_cnp_eca_decompmicc`, `fates_cnp_eca_km_nh4`, `fates_cnp_eca_km_no3`, `fates_cnp_eca_km_p`, `fates_cnp_eca_km_ptase`, `fates_cnp_eca_alpha_ptase`, `fates_cnp_eca_lambda_ptase`, `fates_cnp_eca_vmax_ptase`, `fates_cnp_eca_plant_escalar` |
| CNP — storage & PID | `fates_cnp_nitr_store_ratio`, `fates_cnp_phos_store_ratio`, `fates_cnp_store_ovrflw_frac`, `fates_cnp_pid_kp`, `fates_cnp_pid_ki`, `fates_cnp_pid_kd` |
| CNP — fixation & retranslocation | `fates_cnp_nfix1`, `fates_cnp_turnover_nitr_retrans`, `fates_cnp_turnover_phos_retrans` |
| Phenology | `fates_phen_evergreen`, `fates_phen_stress_decid`, `fates_phen_season_decid` |
| Leaf physiology | `fates_leaf_vcmax25top`, `fates_leaf_slatop` |
| Mortality | `fates_mort_bmort`, `fates_mort_scalar_cstarvation`, `fates_mort_scalar_hydrfailure`, `fates_mort_scalar_coldstress`, `fates_mort_ip_size_senescence`, `fates_mort_ip_age_senescence`, `fates_mort_freezetol` |
| Hydraulics | `fates_hydro_p50_node`, `fates_hydro_kmax_node` |
| Nutrient stoichiometry | `fates_stoich_nitr`, `fates_stoich_phos` (both 2-D, organ × PFT, with the new 4-slot organ axis) |
| **Land use (new at api 43)** | `fates_landuse_grazing_palatability`, `fates_landuse_grazing_rate`, `fates_landuse_grazing_carbon_use_eff`, `fates_landuse_grazing_nitrogen_use_eff`, `fates_landuse_grazing_phosphorus_use_eff`, `fates_landuse_grazing_maxheight`, `fates_landuse_harvest_pprod10`, `fates_landuse_luc_frac_burned`, `fates_landuse_luc_frac_exported`, `fates_landuse_luc_pprod10`, `fates_landuse_logging_*` (10 parameters), `fates_landuse_crop_lu_pft_vector` |

Sources: `parameter_files/fates_params_default.json`, `parteh/PRTGenericMod.F90:80-85`.

### Parameter Loading Pattern (api 43)

FATES uses a **single-phase, name-keyed** load pattern at api 43. The flow is:

1. `JSONRead(filename, pstruct)` (`JSONParameterUtilsMod.F90:189-251`) parses the JSON into a `params_type` structure with `parameters(:)` and `dimensions(:)` arrays.
2. `FatesTransferParameters()` (`FatesInterfaceMod.F90:2675-2694`) dispatches to per-domain transfer subroutines:
   - `TransferParamsGeneric(pstruct)`
   - `TransferParamsSpitFire(pstruct)`
   - `TransferParamsPRT(pstruct)` (PARTEH parameters)
   - `TransferParamsLeafBiophys(pstruct)`
   - `TransferParamsPFT(pstruct)` (non-PARTEH PFT parameters)
3. Each transfer subroutine pulls each parameter by name with `pstruct%GetParamFromName('<name>')`, allocates the destination array, and copies the data.

Example from `EDPftvarcon.F90:637-643`:

```fortran
param_p => pstruct%GetParamFromName('fates_cnp_prescribed_nuptake')
allocate(EDPftvarcon_inst%prescribed_nuptake(numpft))
EDPftvarcon_inst%prescribed_nuptake(:) = param_p%r_data_1d(:)

param_p => pstruct%GetParamFromName('fates_cnp_prescribed_puptake')
allocate(EDPftvarcon_inst%prescribed_puptake(numpft))
EDPftvarcon_inst%prescribed_puptake(:) = param_p%r_data_1d(:)
```

There is no separate `Register_PFT` step that has to be kept in sync with the `Receive_PFT` step. There is no `nbuffer` variable to count beforehand. There is no two-phase round-trip through the netCDF reader.

### Adding a New PFT Parameter (rewritten for api 43)

Step-by-step at e027a40:

1. **Add the parameter declaration** to `parameter_files/fates_params_default.json` as a new top-level object, with the appropriate `dims` (e.g. `["fates_pft"]` for a 1-D PFT array, `["fates_plant_organs", "fates_pft"]` for a 2-D organ × PFT array, or `["scalar"]` for a single-value parameter), `dtype` (`"float"`, `"integer"`, `"string"`), `long_name`, `units`, and `data` (a JSON array sized to match `dims`, in row-major order). Example:
   ```json
   "fates_my_new_param": {
     "dtype": "float",
     "dims": ["fates_pft"],
     "long_name": "description of my new parameter",
     "units": "kgC/m2/yr",
     "data": [0.0, 0.0, ..., 0.0]   // 14 entries at e027a40
   }
   ```
2. **Add a field** to the appropriate derived type:
   - For non-PARTEH PFT parameters, add `real(r8), allocatable :: my_new_param(:)` (or appropriate type/rank) to `EDPftvarcon_type` in `main/EDPftvarcon.F90` (declarations near line 186 onward).
   - For PARTEH parameters, add the field to `prt_parameter_type` in `parteh/PRTParamsFATESMod.F90`.
3. **Add a load block** to the corresponding `Transfer*` subroutine. For non-PARTEH PFT parameters, add to `TransferParamsPFT` in `main/EDPftvarcon.F90:306-...`. For PARTEH, add to `TransferParamsPRT` in `parteh/PRTParamsFATESMod.F90:62-380`. Use the standard three-line pattern:
   ```fortran
   param_p => pstruct%GetParamFromName('fates_my_new_param')
   allocate(EDPftvarcon_inst%my_new_param(numpft))
   EDPftvarcon_inst%my_new_param(:) = param_p%r_data_1d(:)
   ```
   For 2-D parameters use `param_p%r_data_2d(:,:)`; for integers use `param_p%i_data_1d(:)`; for strings use `param_p%c_data_1d(:)`.
4. **(Optional) Add validation** in `FatesCheckParams` (`main/EDPftvarcon.F90:934-1440`) if the parameter has constraints (e.g. must be non-negative, all-or-none across PFTs, etc.). The all-or-none check on `fates_cnp_prescribed_nuptake` at lines 1013-1031 is a representative pattern.
5. **Use the parameter** via `EDPftvarcon_inst%my_new_param(pft)` or `prt_params%my_new_param(pft)` from any module that imports the parent type.

A2MC tooling implication: the Morris shorthand expander in `tools/modify_fates_parameters.py` does not need to change, since the JSON file is read and rewritten by name. But any 2-D PFT × organ parameter has a new shape `(4, 14)` (was `(6, 12)` at e85d997); see Critical Gotcha 7 in `cnp_calibration_guide.md`.

## Adding New Allocation Hypotheses (PARTEH)

### PARTEH Base Class Structure

PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses) uses Fortran derived types with type-bound procedures to support multiple allocation schemes. Each hypothesis extends a base class defined in `parteh/PRTGenericMod.F90`.

### Organ and Element Constants

Declared in `parteh/PRTGenericMod.F90:80-85`:

```fortran
integer, parameter, public :: leaf_organ    = 1
integer, parameter, public :: fnrt_organ    = 2
integer, parameter, public :: sapw_organ    = 3
integer, parameter, public :: store_organ   = 4
integer, parameter, public :: repro_organ   = 5
integer, parameter, public :: struct_organ  = 6
```

These six runtime organ ids are unchanged from earlier FATES releases. **What did change at api 43:** the parameter file now carries data for only four of them (leaf, fine root, sapwood, structure) via `fates_alloc_organ_id = [1, 2, 3, 6]`. Storage and reproductive organs are still allocated and tracked in PARTEH state but their PFT-specific parameters (stoichiometry, retranslocation) are no longer in the parameter file.

Element IDs (`carbon12_element`, `nitrogen_element`, `phosphorus_element`) are also declared in `PRTGenericMod.F90`.

### Hypothesis IDs

The two current hypothesis constants are declared at `parteh/PRTGenericMod.F90:69-70`:

```fortran
integer, parameter, public :: prt_carbon_allom_hyp   = 1
integer, parameter, public :: prt_cnp_flex_allom_hyp = 2
```

The active hypothesis is selected through the module variable `hlm_parteh_mode` (`main/FatesInterfaceTypesMod.F90:85`), set from the namelist value `parteh_mode` at initialization time.

### State Variables

- Carbon-only hypothesis state variables are declared in `parteh/PRTAllometricCarbonMod.F90:76-81`: six variables corresponding to carbon pools for the six organs (`leaf_c_id=1, fnrt_c_id=2, sapw_c_id=3, store_c_id=4, repro_c_id=5, struct_c_id=6`).
- CNP hypothesis state variables are declared in `parteh/PRTAllometricCNPMod.F90:90-112`: 18 variables (`num_vars = 18`), three elements (C, N, P) per organ, with carbon ids 1-6, nitrogen ids 7-12, phosphorus ids 13-18.

### Required Methods for a New Hypothesis

A new allocation hypothesis must implement at least:

| Method | Purpose | Inherited or must implement |
|---|---|---|
| `InitPRTVartype` | Initialize organ pools and state variables | implement |
| `DailyPRT` | Main daily allocation routine | implement |
| `CheckMassConservation` | Verify mass balance at end of each call | implement |
| `DailyPRTAllometry` | Apply allometric constraints (hypothesis-specific) | implement if needed |
| `GetState`, `SetState` | Retrieve and set pool values | inherited |

Registration:

1. Add a new integer ID constant to `parteh/PRTGenericMod.F90` near lines 69-70.
2. Add an initialization branch in `FatesInterfaceMod.F90` inside each `select case(hlm_parteh_mode)` block. At e027a40 there are three such dispatch sites: lines 350-351, 704-705, and 1170-1171. All three must be updated for a new hypothesis.
3. Document the new mode ID in the parameter file and in the namelist validation block in `FatesCheckParams` at `EDPftvarcon.F90:980-1052` (the `select case (hlm_parteh_mode)` validator that aborts on unknown modes at line 1056-1062).

### Carbon-Only vs CNP: Key Differences

| Feature | Carbon-only (`prt_carbon_allom_hyp = 1`) | CNP flexible (`prt_cnp_flex_allom_hyp = 2`) |
|---|---|---|
| State variables | 6 (C per organ) | 18 (C, N, P per organ); `num_vars = 18` at `PRTAllometricCNPMod.F90:112` |
| Growth limitation | Carbon availability | min(C, N, P) with stoichiometric constraints |
| Fine-root allocation | Fixed L2FR parameter | Dynamic L2FR through PID controller in `CNPAdjustFRootTargets` (`PRTAllometricCNPMod.F90:733-874`); gating rewritten at api 43 (see `cnp_calibration_guide.md` Critical Gotcha "PID Controller Gating") |
| Excess handling | Excess C eventually exuded or burned | Excess nutrients tracked separately (`n_efflux`, `p_efflux`, `PRTAllometricCNPMod.F90:1993-2005`) |
| Complexity | Simple allometry | Three-phase allocation with nutrient demand, uptake, and overflow |

Sources: `parteh/PRTAllometricCarbonMod.F90:76-81`, `parteh/PRTAllometricCNPMod.F90:90-112, 733-874, 1993-2005`.

## Adding New Process Models

### Mortality Mechanisms

FATES mortality is modular. Each mechanism is computed separately inside `mortality_rates` (`biogeochem/EDMortalityFunctionsMod.F90:59-285`) and summed. Current mechanisms and the parameter names they expose:

| Mechanism | JSON parameter | Default | Units | Notes |
|---|---|---|---|---|
| Background | `fates_mort_bmort` | 0.014 baseline; **PFT 10 = 0.016, PFT 11 = 0.01** at e027a40 | 1/yr | Per-PFT defaults differ for the new arctic shrubs |
| Carbon starvation | `fates_mort_scalar_cstarvation` | 0.6 baseline; **PFT 11 = 0.57** | 1/yr (max rate) | Per-PFT |
| Hydraulic failure | `fates_mort_scalar_hydrfailure` | 0.6 baseline; **PFT 11 = 0.8** | 1/yr (max rate) | Per-PFT |
| Cold stress | `fates_mort_scalar_coldstress` | 3.0 baseline; **PFT 11 = 3.5, PFT 12 = 2.3** | 1/yr (max rate) | Per-PFT |
| Size senescence | `fates_mort_ip_size_senescence` | unset (off) | cm DBH (inflection point) | |
| Age senescence | `fates_mort_ip_age_senescence` | unset (off) | years (inflection point) | |
| Fire | various fire parameters | - | - | See `../fire/` |
| Logging | various `fates_landuse_logging_*` parameters | - | - | New land-use category at api 43 |
| Prescribed physiology canopy | `fates_mort_prescribed_canopy` | 0.0194 | 1/yr | Used only with `hlm_use_ed_prescribed_phys` |
| Prescribed physiology understory | `fates_mort_prescribed_understory` | 0.025 | 1/yr | Used only with `hlm_use_ed_prescribed_phys` |

Sources: parameter file by name; `biogeochem/EDMortalityFunctionsMod.F90:47-285`.

> **Default-value drift at sci.1.91.x.** Where the e85d997 wiki listed single uniform default values (e.g. `bmort = 0.014`, `cstarvation = 0.6`), the e027a40 parameter file has PFT-specific defaults for the new arctic shrub PFTs (10, 11) and arctic / cool grasses (12). The single-scalar table from earlier wikis is no longer accurate; the per-PFT values listed above are the e027a40 defaults verified against `parameter_files/fates_params_default.json`.

To add a new mortality mechanism:

1. Define one or more JSON parameters following the naming convention `fates_mort_*`.
2. Add the field to `EDPftvarcon_type` and wire the load block in `TransferParamsPFT` (`EDPftvarcon.F90:306-...`).
3. Add a new code block in `mortality_rates` (`EDMortalityFunctionsMod.F90:59-285`) that computes the mechanism-specific rate from the relevant state variables.
4. Sum the new rate into the total mortality rate at the aggregation site inside `mortality_rates` and (if it should affect the per-mechanism derivative) inside `Mortality_Derivative` (`EDMortalityFunctionsMod.F90:289-380`).

Mortality rate constraints:

- Rates must be non-negative.
- Rates are interpreted per-year (units `1/yr`).
- Combined rates should not exceed about 0.99 per year for numerical stability.

### Process Model Integration Pattern

New process models should follow the standard pattern:

1. Create a new module `Fates<Process>Mod.F90` under `biogeochem/`, `biogeophys/`, or `fire/` as appropriate.
2. Define a top-level subroutine with a clear interface that takes `bc_in`, `bc_out`, and site or patch pointers.
3. Declare any new parameters in the JSON parameter file and wire a load block (per "Adding a New PFT Parameter" above) in the appropriate `Transfer*` subroutine.
4. Add the call from the daily or sub-daily dynamics loop at the correct point in the call sequence.
5. Add diagnostic history variables in `main/FatesHistoryInterfaceMod.F90`.

Sources: `biogeophys/FatesPlantRespPhotosynthMod.F90`, `biogeochem/FatesSoilBGCFluxMod.F90`.

## Best Practices and Guidelines

### Code Organization

| Aspect | Convention | Rationale |
|---|---|---|
| Module naming | `Fates<Process><Type>Mod` | Clear identification of functionality |
| File naming | Match module name exactly | Easy file location |
| Subroutine names | Descriptive, action-oriented (e.g. `PrepNutrientAquisitionBCs`, `TransferParamsPFT`) | Self-documenting |
| Variable naming | Lower case with underscores | Fortran standard |
| Constants | Lower case with `_` (e.g. `prt_cnp_flex_allom_hyp`) or upper-case acronyms | Distinguish scope by context |
| Parameter names | `fates_<category>_<name>` (e.g. `fates_cnp_vmax_nh4`, `fates_landuse_grazing_rate`) | Searchable by category |

### Parameter Management

- Prefer JSON parameters (`fates_params_default.json`) over hard-coded constants.
- Use descriptive `long_name` and `units` attributes so calibration users can identify parameters without reading the Fortran.
- Document the valid range and default values via the `long_name` when appropriate.
- When a new parameter interacts with an existing one (for example, a new mortality scalar that depends on an allometry parameter), cross-reference in the `long_name`.
- Prefer per-PFT (`["fates_pft"]`) parameters over scalars when ecological reasoning suggests PFT-specific values; the new arctic shrub PFTs at e027a40 illustrate this — many mortality and storage defaults are now per-PFT rather than uniform.
- For parameters that must satisfy a global constraint (e.g. all-or-none across PFTs), add a check to `FatesCheckParams` (`EDPftvarcon.F90:934-1440`).

### Testing and Validation

When adding new functionality:

- Run a short carbon-only simulation to check that the default allocation hypothesis still reproduces previous results.
- Run a short CNP simulation with **coupled** uptake (the e027a40 default — see `cnp_calibration_guide.md` Critical Gotcha 2) to check that the new code path does not break the CNP hypothesis.
- Verify mass conservation explicitly inside any new PARTEH method.
- Exercise the new parameter from an ensemble (for example A2MC Morris sampling) to check that it stays within plausible bounds.
- If the new parameter dimension involves the `fates_plant_organs` axis, remember that the parameter file axis is now 4-slot (leaf, fine root, sapwood, structure) and not 6-slot.

## Summary Table: Extensibility Points

| Extension type | Primary files | Key steps | Difficulty |
|---|---|---|---|
| Add a PFT | `parameter_files/fates_params_default.json` | Append to each `data` array; update `fates_pftname`; size `(pft)` arrays to the new count | low |
| Add a PFT parameter | `parameter_files/fates_params_default.json`, `main/EDPftvarcon.F90` (or `parteh/PRTParamsFATESMod.F90`) | Declare in JSON, add field, add `pstruct%GetParamFromName` load block, use | medium |
| New allocation hypothesis | new `parteh/PRTAllometric*.F90` | Extend base class, implement required methods, add hypothesis ID, wire dispatcher cases at three sites (`FatesInterfaceMod.F90:350, 704, 1170`) and validator | high |
| New mortality mechanism | `biogeochem/EDMortalityFunctionsMod.F90` | Add per-PFT parameter, load block, rate computation, sum into total | medium |
| New physiology process | new `biogeophys/Fates*Mod.F90` | Create module, integrate into main loop, add JSON parameters, history vars | high |
| New land-use category interaction | `main/FatesConstantsMod.F90` (`fates_landuseclass`), `parameter_files/fates_params_default.json` (`fates_landuse_*`) | Use the new `fates_landuse_*` parameter family and the 5-class enum (`primaryland`, `secondaryland`, `rangeland`, `pastureland`, `cropland`) added at api 43 | medium |

Sources: `parameter_files/fates_params_default.json`, `main/EDPftvarcon.F90`, `parteh/PRTGenericMod.F90`, `parteh/PRTAllometricCarbonMod.F90`, `parteh/PRTAllometricCNPMod.F90`, `main/FatesConstantsMod.F90:50-58, 64`.
