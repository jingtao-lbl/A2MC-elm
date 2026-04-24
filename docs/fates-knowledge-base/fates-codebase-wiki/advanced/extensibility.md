# Model Extensibility

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

<details>
<summary>Relevant source files</summary>

- `main/EDPftvarcon.F90` (parameter registration and receiving)
- `main/EDParamsMod.F90` (global parameter handling)
- `parteh/PRTGenericMod.F90` (PARTEH base class, organ and element constants, hypothesis IDs)
- `parteh/PRTAllometricCarbonMod.F90` (carbon-only allocation hypothesis)
- `parteh/PRTAllometricCNPMod.F90` (CNP flexible allocation hypothesis)
- `parteh/PRTLossFluxesMod.F90` (shared PARTEH loss fluxes)
- `biogeochem/FatesSoilBGCFluxMod.F90` (nutrient boundary conditions)
- `biogeophys/FatesPlantRespPhotosynthMod.F90` (biophysics module pattern)
- `parameter_files/fates_params_default.cdl` (ground-truth parameter list)

</details>

## Purpose and Scope

This page explains how to extend FATES with new scientific hypotheses and parameterizations. It covers the main extensibility points: adding new PFTs and PFT parameters, adding new PARTEH allocation hypotheses, and adding new process models such as mortality mechanisms. For configuring existing model options, see `simulation_modes.md` and `nutrient_competition.md`. For the PARTEH allocation framework design, see `../plant-physiology/parteh/index.md`.

## Extensibility Architecture Overview

FATES exposes three primary extension points:

| Extension point | Mechanism | Primary files |
|---|---|---|
| PFT parameters | NetCDF parameter files with register and receive pattern | `parameter_files/fates_params_default.cdl`, `main/EDPftvarcon.F90` |
| Allocation hypotheses | Object-oriented PARTEH framework | `parteh/PRTGenericMod.F90`, `parteh/PRTAllometric*.F90` |
| Process models | Modular subroutines with standardized interfaces | `biogeochem/`, `biogeophys/` modules |

Sources: `main/EDPftvarcon.F90:1-700`, `parteh/PRTGenericMod.F90:1-100`, `main/EDParamsMod.F90:1-100`.

## Adding New Plant Functional Types

### Parameter File Structure

PFTs are defined in NetCDF parameter files following the CDL (Common Data Language) specification. The file declares dimensions, variables, and default values.

Key dimensions:

- `fates_pft` number of PFTs (default 12)
- `fates_plant_organs` number of organ types (6: leaf, fine root, sapwood, storage, reproductive, structural, per `PRTGenericMod.F90:80-85`)
- `fates_hydr_organs` number of hydraulic compartments
- `fates_leafage_class` number of leaf age classes
- `fates_litterclass`, `fates_fuel`, `fates_hlm_pftno`, and others

Parameter categories (approximate locations in `parameter_files/fates_params_default.cdl` at commit `e85d997`):

| Category | Example parameters | Approximate lines |
|---|---|---|
| Allometry | `fates_allom_d2h1`, `fates_allom_d2bl1`, `fates_allom_l2fr` | 34-140 |
| CNP | `fates_cnp_vmax_nh4`, `fates_cnp_eca_km_nh4`, `fates_cnp_prescribed_nuptake` | 170-235 |
| Phenology | `fates_phen_evergreen`, `fates_phen_stress_decid`, `fates_phen_season_decid` | 440-475 |
| Leaf physiology | `fates_leaf_vcmax25top`, `fates_leaf_slatop` | 350-400 |
| Mortality | `fates_mort_bmort`, `fates_mort_scalar_cstarvation`, `fates_mort_scalar_hydrfailure`, `fates_mort_scalar_coldstress`, `fates_mort_ip_size_senescence`, `fates_mort_ip_age_senescence` | 395-433 |
| Hydraulics | `fates_hydro_p50_node`, `fates_hydro_kmax_node` | 287-331 |
| Nutrient stoichiometry | `fates_stoich_nitr`, `fates_stoich_phos` (both 2-D, organ by PFT) | 545-550 |

Sources: `parameter_files/fates_params_default.cdl`, `parteh/PRTGenericMod.F90:80-85`.

### Parameter Registration and Receiving Pattern

FATES uses a two-phase pattern to load parameters: **Register** declares which parameters are needed, **Receive** populates the values into `EDPftvarcon_inst` fields.

In `main/EDPftvarcon.F90`:

- `Register_PFT` (approximately `EDPftvarcon.F90:315-346`) declares each needed PFT parameter through calls that add the parameter name to the read list.
- `Receive_PFT` (approximately `EDPftvarcon.F90:349-700`) reads each parameter from the netCDF file and copies it into the `EDPftvarcon_inst%<field>` array.

The same pattern applies to the parteh-side parameters in `parteh/PRTParamsFATESMod.F90`: `PrtRegisterParams` declares and `PrtReceiveParams` populates. For example `fates_cnp_store_ovrflw_frac` is declared at `PRTParamsFATESMod.F90:280` and received at line 619-621.

### Adding a New PFT Parameter

Step-by-step:

1. **Declare the variable** in `parameter_files/fates_params_default.cdl` with the appropriate dimension (1-D `fates_pft` or 2-D such as `(fates_plant_organs, fates_pft)`).
2. **Add a field** to the `EDPftvarcon_type` derived type in `main/EDPftvarcon.F90` (for non-parteh parameters) or to `prt_parameter_type` in `parteh/PRTParamsFATESMod.F90` (for parteh parameters).
3. **Add a `Register` call** in the corresponding `Register_*` subroutine to tell the parameter loader to read it.
4. **Add a `Receive` call** in the corresponding `Receive_*` subroutine to populate the array.
5. **Use the parameter** via `EDPftvarcon_inst%<field>(pft)` or `prt_params%<field>(pft)`.

Sources: `main/EDPftvarcon.F90:315-700`, `parteh/PRTParamsFATESMod.F90`.

## Adding New Allocation Hypotheses (PARTEH)

### PARTEH Base Class Structure

PARTEH (Plant Allocation and Reactive Transport Extensible Hypotheses) uses Fortran derived types with type-bound procedures to support multiple allocation schemes. Each hypothesis extends a base class defined in `parteh/PRTGenericMod.F90`.

### Organ and Element Constants

Declared in `parteh/PRTGenericMod.F90:80-85` and `parteh/PRTGenericMod.F90:233-277` (approximate):

```fortran
integer, parameter, public :: leaf_organ    = 1
integer, parameter, public :: fnrt_organ    = 2
integer, parameter, public :: sapw_organ    = 3
integer, parameter, public :: store_organ   = 4
integer, parameter, public :: repro_organ   = 5
integer, parameter, public :: struct_organ  = 6
```

Element IDs (carbon12_element, nitrogen_element, phosphorus_element) are also declared in `PRTGenericMod.F90`.

### Hypothesis IDs

The two current hypothesis constants are declared at `parteh/PRTGenericMod.F90:69-70`:

```fortran
integer, parameter, public :: prt_carbon_allom_hyp   = 1
integer, parameter, public :: prt_cnp_flex_allom_hyp = 2
```

The active hypothesis is selected through the module variable `hlm_parteh_mode` (`main/FatesInterfaceTypesMod.F90:94`), set from the namelist value `parteh_mode` at initialization time.

### State Variables

- Carbon-only hypothesis state variables are declared in `parteh/PRTAllometricCarbonMod.F90:76-90`: six variables corresponding to carbon pools for the six organs.
- CNP hypothesis state variables are declared in `parteh/PRTAllometricCNPMod.F90:86-108`: 18 variables, three elements (C, N, P) per organ.

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

1. Add a new integer ID constant to `parteh/PRTGenericMod.F90` in the block at lines 69-70.
2. Add an initialization branch in `FatesInterfaceMod.F90` inside the `select case(hlm_parteh_mode)` block near line 335 and its companion at 649.
3. Document the new mode ID in the parameter file and namelist validation at `EDPftvarcon.F90:1812-1882`.

### Carbon-Only vs CNP: Key Differences

| Feature | Carbon-only (`prt_carbon_allom_hyp = 1`) | CNP flexible (`prt_cnp_flex_allom_hyp = 2`) |
|---|---|---|
| State variables | 6 (C per organ) | 18 (C, N, P per organ) |
| Growth limitation | Carbon availability | min(C, N, P) with stoichiometric constraints |
| Fine-root allocation | Fixed L2FR parameter | Dynamic L2FR through PID controller in `CNPAdjustFRootTargets` (`PRTAllometricCNPMod.F90:729-870`) |
| Excess handling | Excess C eventually exuded or burned | Excess nutrients tracked separately (`n_efflux`, `p_efflux`, `PRTAllometricCNPMod.F90:1990-2002`) |
| Complexity | Simple allometry | Three-phase allocation with nutrient demand, uptake, and overflow |

Sources: `parteh/PRTAllometricCarbonMod.F90`, `parteh/PRTAllometricCNPMod.F90`.

## Adding New Process Models

### Mortality Mechanisms

FATES mortality is modular. Each mechanism is computed separately and summed. Current mechanisms and the CDL parameter names they expose:

| Mechanism | CDL parameter | Default | Units |
|---|---|---|---|
| Background | `fates_mort_bmort` | 0.014 | 1/yr |
| Carbon starvation | `fates_mort_scalar_cstarvation` | 0.6 | 1/yr (maximum rate) |
| Hydraulic failure | `fates_mort_scalar_hydrfailure` | 0.6 | 1/yr (maximum rate) |
| Cold stress | `fates_mort_scalar_coldstress` | 3.0 | 1/yr (maximum rate) |
| Size senescence | `fates_mort_ip_size_senescence` | unset (off) | cm DBH (inflection point) |
| Age senescence | `fates_mort_ip_age_senescence` | unset (off) | years (inflection point) |
| Fire | various fire parameters | - | - |
| Logging | various logging parameters | - | - |
| Prescribed physiology canopy | `fates_mort_prescribed_canopy` | 0.0194 | 1/yr |
| Prescribed physiology understory | `fates_mort_prescribed_understory` | 0.025 | 1/yr |

Sources: `parameter_files/fates_params_default.cdl:395-433, 1312-1343`.

To add a new mortality mechanism:

1. Define one or more CDL parameters following the naming convention `fates_mort_*`.
2. Add the field to `EDPftvarcon_type` and wire Register/Receive calls.
3. Add a new subroutine in the mortality module that computes the mechanism-specific rate from the relevant state variables.
4. Sum the new rate into the total mortality rate at the aggregation call site.

Mortality rate constraints:

- Rates must be non-negative.
- Rates are interpreted per-year (units `1/yr`).
- Combined rates should not exceed about 0.99 per year for numerical stability.

### Process Model Integration Pattern

New process models should follow the standard pattern:

1. Create a new module `Fates<Process>Mod.F90` under `biogeochem/`, `biogeophys/`, or `fire/` as appropriate.
2. Define a top-level subroutine with a clear interface that takes `bc_in`, `bc_out`, and site or patch pointers.
3. Declare any new parameters in the parameter file and wire Register/Receive calls.
4. Add the call from the daily or sub-daily dynamics loop at the correct point in the call sequence.
5. Add diagnostic history variables in `FatesHistoryInterfaceMod.F90`.

Sources: `biogeophys/FatesPlantRespPhotosynthMod.F90`, `biogeochem/FatesSoilBGCFluxMod.F90`.

## Best Practices and Guidelines

### Code Organization

| Aspect | Convention | Rationale |
|---|---|---|
| Module naming | `Fates<Process><Type>Mod` | Clear identification of functionality |
| File naming | Match module name exactly | Easy file location |
| Subroutine names | Descriptive, action-oriented (e.g. `PrepNutrientAquisitionBCs`) | Self-documenting |
| Variable naming | Lower case with underscores | Fortran standard |
| Constants | Lower case with `_` (e.g. `prt_cnp_flex_allom_hyp`) or upper-case acronyms | Distinguish scope by context |

### Parameter Management

- Prefer PFT parameters (`fates_params_default.cdl`) over hard-coded constants.
- Use descriptive CDL long-name and units attributes so calibration users can identify parameters without reading the Fortran.
- Document the valid range and default values in the parameter file metadata.
- When a new parameter interacts with an existing one (for example, a new mortality scalar that depends on an allometry parameter), cross-reference in the long-name.

### Testing and Validation

When adding new functionality:

- Run a short carbon-only simulation to check that the default allocation hypothesis still reproduces previous results.
- Run a short CNP simulation with prescribed uptake to check that the new code path does not break the CNP hypothesis.
- Verify mass conservation explicitly inside any new PARTEH method.
- Exercise the new parameter from an ensemble (for example A2MC Morris sampling) to check that it stays within plausible bounds.

## Summary Table: Extensibility Points

| Extension type | Primary files | Key steps | Difficulty |
|---|---|---|---|
| Add a PFT | `parameter_files/fates_params_*.cdl` | Add parameter values to the existing file | low |
| Add a PFT parameter | `fates_params_*.cdl`, `main/EDPftvarcon.F90` or `parteh/PRTParamsFATESMod.F90` | Declare, register, receive, use | medium |
| New allocation hypothesis | new `parteh/PRTAllometric*.F90` | Extend base class, implement required methods, add hypothesis ID | high |
| New mortality mechanism | `biogeochem/EDPhysiologyMod.F90` or a new module | Add calculation, parameters, history outputs | medium |
| New physiology process | new `biogeophys/Fates*Mod.F90` | Create module, integrate into main loop | high |

Sources: `parameter_files/fates_params_default.cdl`, `main/EDPftvarcon.F90`, `parteh/PRTGenericMod.F90`, `parteh/PRTAllometricCarbonMod.F90`, `parteh/PRTAllometricCNPMod.F90`.
