# Advanced Topics

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

<details>
<summary>Relevant source files</summary>

- `biogeophys/FatesPlantRespPhotosynthMod.F90`
- `biogeochem/FatesSoilBGCFluxMod.F90`
- `main/EDParamsMod.F90`
- `main/EDPftvarcon.F90`
- `main/FatesInterfaceMod.F90`
- `main/FatesInterfaceTypesMod.F90`
- `main/FatesConstantsMod.F90`
- `parameter_files/fates_params_default.cdl`

</details>

## Purpose and Scope

This page covers advanced model configurations, specialized simulation modes, and extensibility features in FATES. It documents the main simulation mode flags, the nutrient competition alternatives, and the extensibility framework used to add new hypotheses. For the standard daily dynamics loop, see `../core-dynamics/daily_loop.md`. For the default PARTEH allocation system, see `../plant-physiology/parteh/index.md`. For initialization procedures, see `../getting-started/initialization.md`.

## 10.1 Simulation Modes

FATES exposes several alternative simulation modes that modify the standard ecosystem dynamics. They are controlled by host-land-model flags declared in `FatesInterfaceTypesMod.F90` and set during FATES initialization.

### Mode Configuration Flags

| Mode | Flag variable | Declared at | Purpose | Mutual exclusivity |
|---|---|---|---|---|
| Satellite phenology (SP) | `hlm_use_sp` | `FatesInterfaceTypesMod.F90:194` | Drive FATES with prescribed LAI/SAI/height | Implies no competition and no growth dynamics |
| No competition | `hlm_use_nocomp` | `FatesInterfaceTypesMod.F90:191` | Separate each PFT into its own patch (no inter-PFT competition) | Incompatible with standard multi-PFT-per-patch mode |
| Fixed biogeography | `hlm_use_fixed_biogeog` | `FatesInterfaceTypesMod.F90:188` | Prescribe PFT area fractions from the surface dataset | Usually combined with nocomp |
| Prescribed physiology | `hlm_use_ed_prescribed_phys` | `FatesInterfaceTypesMod.F90:165-173` | Replace photosynthesis / respiration with a prescribed NPP per area | Cannot combine with ST3 |
| Static stand structure (ST3) | `hlm_use_ed_st3` | `FatesInterfaceTypesMod.F90:155-162` | Freeze demography (no growth / mortality / recruitment) | Cannot combine with prescribed physiology |

Sources: `main/FatesInterfaceTypesMod.F90:155-195`.

For the full mode walk-through, see `simulation_modes.md`.

### Key Correction: `hlm_use_nocomp` Semantics

Setting `hlm_use_nocomp = 1` does not "fix PFT areas". The flag:

1. Puts each PFT into its own patch, so different PFTs cannot share light, water, or nutrients within a patch.
2. Leaves the FATES demographic equations (growth, recruitment, mortality) operating inside each patch.

Fixing PFT area fractions is a separate flag: `hlm_use_fixed_biogeog`. In practice `nocomp` is almost always combined with `fixed_biogeog` to get a stable, PFT-isolated experiment, but they are independent switches.

## 10.2 Nutrient Competition Modes

FATES supports two HLM-side competition algorithms (ECA and RD), two scaling schemes (coupled and trivial), and two uptake modes (prescribed and coupled). See `nutrient_competition.md` for full details.

### Selecting the HLM Competition Algorithm

Set via the character string `hlm_nu_com` (`main/FatesInterfaceTypesMod.F90:54`). Valid values:

- `'ECA'` Ecosystem Chemistry Approximation (Michaelis-Menten competition)
- `'RD'` Relative Demand

### Competitor Scaling Modes

`fates_np_comp_scaling` is an **internal FATES integer** (module variable, declared as `integer, public :: fates_np_comp_scaling` in `FatesConstantsMod.F90:124`) whose value is set automatically at initialization (`FatesInterfaceMod.F90:875-900`). The enum constants, also in `FatesConstantsMod.F90`, are:

| Constant | Integer value | Declared at |
|---|---|---|
| `coupled_np_comp_scaling` | **1** | `FatesConstantsMod.F90:96` |
| `trivial_np_comp_scaling` | **2** | `FatesConstantsMod.F90:115` |

The initialization rule is: if `hlm_parteh_mode == prt_cnp_flex_allom_hyp` and **either** N or P uptake is coupled, use `coupled_np_comp_scaling = 1`. Otherwise use `trivial_np_comp_scaling = 2` (`FatesInterfaceMod.F90:887-900`). This means the scaling mode is derived from the uptake mode, not an independent namelist switch.

**Correction over earlier documentation:** previous versions of this wiki stated that `trivial_np_comp_scaling = 0`. The correct value is `2`. Anyone pattern-matching the integer value by hand would silently misconfigure FATES.

### Boundary Condition Scalars `cn_scalar` and `cp_scalar`

When ECA is active, the boundary condition arrays `bc_out%cn_scalar` and `bc_out%cp_scalar` are used to send plant-side C:N and C:P stress information to the HLM's BGC competition routine. In the FATES source at commit `e85d997`, the only place these arrays are assigned is `PrepNutrientAquisitionBCs` at `FatesSoilBGCFluxMod.F90:436-437`:

```fortran
bc_out%cn_scalar(:) = 1._r8
bc_out%cp_scalar(:) = 1._r8
```

There is no branch that computes these from plant C:N or C:P ratios inside FATES. They are **initialized to 1.0 by FATES and left for the HLM's BGC model to re-compute or consume as-is**. Any earlier description that said "computed from plant C:N and C:P ratios in coupled scaling mode" did not match this version of the source.

Sources: `biogeochem/FatesSoilBGCFluxMod.F90:400-518`.

### Prescribed vs Coupled Uptake

In prescribed mode, plants receive a PFT-specific fraction of their nutrient demand (parameter `fates_cnp_prescribed_nuptake(pft)` for N and `fates_cnp_prescribed_puptake(pft)` for P), with no mass removed from soil BGC pools. In coupled mode, the HLM returns the actual uptake through the boundary condition arrays `bc_in%plant_nh4_uptake_flux`, `bc_in%plant_no3_uptake_flux`, and `bc_in%plant_p_uptake_flux`.

The switch between prescribed and coupled is made per-site at initialization, based on whether **any** PFT has a non-zero `fates_cnp_prescribed_nuptake` or `fates_cnp_prescribed_puptake` (`FatesInterfaceMod.F90:875-885`). **If any PFT has a non-zero value, the entire site runs in prescribed mode for that element.**

### Prescribed Physiology Parameters (CDL names)

The five parameters actually used by `hlm_use_ed_prescribed_phys` are declared in the parameter file with `fates_` prefixes:

| CDL parameter | Units | Role |
|---|---|---|
| `fates_prescribed_npp_canopy` | kgC / m2 / yr | Canopy-tree NPP (`fates_params_default.cdl:473-475`) |
| `fates_prescribed_npp_understory` | kgC / m2 / yr | Understory-tree NPP (`fates_params_default.cdl:476-478`) |
| `fates_mort_prescribed_canopy` | 1/yr | Canopy mortality rate (`fates_params_default.cdl:413-415`) |
| `fates_mort_prescribed_understory` | 1/yr | Understory mortality rate (`fates_params_default.cdl:416-418`) |
| `fates_recruit_prescribed_rate` | n/yr | Prescribed recruitment rate (`fates_params_default.cdl:515-517`) |

**Correction over earlier documentation:** earlier versions of this wiki listed these as `prescribed_mortality_canopy`, `prescribed_mortality_understory`, and `prescribed_recruitment` using the module-internal derived-type field names from `EDPftvarcon.F90` rather than the CDL parameter names. The module-internal names are correct Fortran, but users editing parameter files must use the `fates_` prefixed CDL names. The recruitment rate is also declared in units of `n/yr`, not `1/yr`.

## 10.3 Model Extensibility

FATES is designed to be extended with new parameters, allocation hypotheses, mortality mechanisms, and history variables without modifying the core dispatch. See `extensibility.md` for the full guide. The key entry points are:

| Extension type | Primary files |
|---|---|
| PFT parameters | `parameter_files/fates_params_default.cdl`, `main/EDPftvarcon.F90` (`Register_PFT` and `Receive_PFT`) |
| Allocation hypotheses | `parteh/PRTGenericMod.F90` (base class), `parteh/PRTAllometricCarbonMod.F90` (`prt_carbon_allom_hyp = 1`), `parteh/PRTAllometricCNPMod.F90` (`prt_cnp_flex_allom_hyp = 2`) |
| Mortality mechanisms | `biogeochem/EDPhysiologyMod.F90` and parameter names of the form `fates_mort_*` |
| History variables | `main/FatesHistoryInterfaceMod.F90` |

The PARTEH dispatch is a `select case(hlm_parteh_mode)` in `FatesInterfaceMod.F90` that picks between the two allocation hypotheses. Adding a new hypothesis means defining a new integer constant in `PRTGenericMod.F90` and wiring it into the dispatcher.

Sources: `parteh/PRTGenericMod.F90:69-70`, `main/FatesInterfaceMod.F90:335-370`, `main/EDPftvarcon.F90:315-700`.

---

## Summary

Advanced FATES features provide three axes of flexibility:

- **Simulation modes** modify or freeze parts of the standard ecosystem dynamics (SP, no-comp, fixed biogeography, prescribed physiology, ST3).
- **Nutrient competition** modes control whether plants compete through the HLM's BGC model (ECA or RD), how FATES presents competitors to the HLM (coupled or trivial scaling, selected automatically), and whether uptake is coupled to the soil pool or prescribed as a fraction of demand.
- **Extensibility** hooks let researchers add parameters, PFTs, allocation hypotheses, mortality mechanisms, and history variables without touching core dispatch code.

All three axes are controlled by flags declared in `FatesInterfaceTypesMod.F90`, constants declared in `FatesConstantsMod.F90`, and PFT parameters declared in `fates_params_default.cdl`. Anyone configuring FATES for calibration should verify their settings against these three sources rather than against derived-type field names inside `EDPftvarcon.F90`.
