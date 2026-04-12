# FATES-CNP Calibration Guide

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

<details>
<summary>Relevant source files</summary>

- `parteh/PRTAllometricCNPMod.F90` (CNP allocation, PID fine-root controller, storage overflow, efflux)
- `parteh/PRTParamsFATESMod.F90` (Register / Receive for `fates_cnp_*` PARTEH parameters including storage ratios and PID gains)
- `biogeochem/FatesSoilBGCFluxMod.F90` (N/P demand computation, prescribed vs coupled uptake, boundary conditions to the HLM)
- `main/EDPftvarcon.F90` (non-PARTEH PFT parameters such as `vmax_nh4`, `vmax_no3`, `vmax_p`, `prescribed_nuptake`, `prescribed_puptake`, `eca_km_*`)
- `main/FatesConstantsMod.F90` (enum constants: `prescribed_n_uptake = 1`, `coupled_n_uptake = 2`, `coupled_np_comp_scaling = 1`, `trivial_np_comp_scaling = 2`)
- `main/FatesInterfaceMod.F90` (initialization of `n_uptake_mode`, `p_uptake_mode`, `fates_np_comp_scaling`)
- `main/FatesInterfaceTypesMod.F90` (`hlm_nu_com`, `hlm_parteh_mode`)
- `parameter_files/fates_params_default.cdl` (ground-truth defaults for every `fates_cnp_*` parameter)

</details>

**Author:** Jing Tao with Claude. Adapted from the FATES CNP Guidebook by Ryan Knox, with all parameter names, defaults, and line citations re-verified against FATES commit `e85d997`.

This guide gives practical guidance for calibrating FATES with coupled carbon, nitrogen, and phosphorus (CNP) dynamics. It covers core concepts, common pitfalls, diagnostic strategies, and a step-by-step site setup procedure. **Every FATES parameter name mentioned in this guide has been verified to exist in `parameter_files/fates_params_default.cdl` at commit `e85d997`.**

---

## Core Concepts

### Nutrient Cycling Modes

ELM and CLM always cycle nutrients internally when FATES is on. FATES itself selects between carbon-only allocation and full CNP allocation via the `parteh_mode` namelist value, which populates the module-level flag `hlm_parteh_mode` (`FatesInterfaceTypesMod.F90:94`). The two mode constants are defined in `PRTGenericMod.F90:69-70`:

- `prt_carbon_allom_hyp = 1` (carbon-only allocation, `PRTAllometricCarbonMod.F90`)
- `prt_cnp_flex_allom_hyp = 2` (CNP flexible allocation, `PRTAllometricCNPMod.F90`)

| Mode | Namelist value | Nutrient transfer | Litter nutrients | HLM supplementation |
|---|---|---|---|---|
| FATES-CNP | `parteh_mode = 2` | Mineralized pools to FATES plant storage via boundary conditions | C, N, P in fragmented litter returned to ELM/CLM | `suplnitro = NONE` and `suplphos = NONE` (target end state) |
| FATES carbon-only | `parteh_mode = 1` | No nutrients reach the plant | No nutrient mass in litter | `suplnitro = ALL` and `suplphos = ALL` |

Sources: `parteh/PRTAllometricCNPMod.F90`, `parteh/PRTAllometricCarbonMod.F90`, `parteh/PRTGenericMod.F90:69-70`.

### Multi-Phase Spin-Up

CNP simulations require a multi-phase spin-up:

```
Phase 1: AD spin-up (~500+ years typical for forests)
  Initial period: N AND P supplementation (multi-year)
  Remainder:      N limitation on, P still supplemented
  Target:         multi-year smoothed FATES_NEP near zero

Phase 2: Post-AD (~100-500 years)
  N-limited, P-supplemented
  Target: NEP equilibrium

Phase 3: Target / transient
  N-limited, P-limited (if desired)
  P initialized from data
```

---

## Critical Gotchas

### 1. AD Simulation Must Start at Year 0001

Carbon AD mode requires `RUN_STARTDATE = '0001-01-01'`:

```bash
./xmlchange --append ELM_BLDNML_OPTS="-bgc_spinup on"
./xmlchange RUN_STARTDATE='0001-01-01'
```

### 2. Verify You Are Not in Prescribed-Uptake Mode

FATES decides between prescribed and coupled uptake automatically at initialization, based on the sign of the PFT-level parameters `fates_cnp_prescribed_nuptake` and `fates_cnp_prescribed_puptake` (`FatesInterfaceMod.F90:875-885`):

```fortran
if (any(abs(EDPftvarcon_inst%prescribed_nuptake(:)) > nearzero)) then
   n_uptake_mode = prescribed_n_uptake   ! integer 1
else
   n_uptake_mode = coupled_n_uptake      ! integer 2
end if
```

**If any PFT has a non-zero `fates_cnp_prescribed_nuptake`, every PFT at the site is driven in prescribed-N mode.** The same rule holds for P.

In the default `fates_params_default.cdl` file at `e85d997`, `fates_cnp_prescribed_nuptake = 1` and `fates_cnp_prescribed_puptake = 1` for all 12 PFTs (lines 1085, 1087). **The defaults put FATES in prescribed-uptake mode.** For true coupled CNP dynamics you must set both to 0 for every PFT.

In prescribed-N mode, the daily N uptake is computed locally inside `FatesSoilBGCFluxMod.F90:155-170`:

```fortran
ccohort%daily_nh4_uptake = fnrt_c * vmax_nh4(pft) * prescribed_nuptake(pft) * sec_per_day
ccohort%daily_no3_uptake = fnrt_c * vmax_no3(pft) * prescribed_nuptake(pft) * sec_per_day
```

No mass is removed from the soil BGC pools. The daily demand formula is identical in prescribed and coupled modes (see "RD vs ECA vmax" below). In downstream CNP allocation, prescribed mode also disables the efflux path (`PRTAllometricCNPMod.F90:1990-2002`) and forces `n_efflux = 0`.

Sources: `biogeochem/FatesSoilBGCFluxMod.F90:155-206`, `parteh/PRTAllometricCNPMod.F90:1990-2002`, `main/FatesInterfaceMod.F90:875-885`, `parameter_files/fates_params_default.cdl:212-217, 1085-1087`.

**Known source-code quirk (e85d997):** At `FatesSoilBGCFluxMod.F90:202` the P gain in prescribed mode is scaled by `prescribed_nuptake(pft)` instead of `prescribed_puptake(pft)`. Users running in full prescribed-N and prescribed-P mode should be aware that the P side of the gain currently follows the N fraction. This is a FATES bug, not a calibration choice.

### 3. ECA vs RD Vmax Magnitudes

The two soil BGC competition modes, ECA and RD, have very different typical `vmax_*` magnitudes because of how the HLM's competition routine filters demand:

| HLM competition | Typical `vmax_nh4`, `vmax_no3`, `vmax_p` | Notes |
|---|---|---|
| ECA (`hlm_nu_com = 'ECA'`) | approximately 1e-7 gN or gP per gC per s | Stronger source limitation imposed in HLM; FATES needs a larger `vmax` to push demand through |
| RD (`hlm_nu_com = 'RD'`) | approximately 1e-9 | Weaker limitation from HLM |

Defaults in `fates_params_default.cdl` at `e85d997`:

- `fates_cnp_vmax_nh4 = 2.5e-9` (line 1103)
- `fates_cnp_vmax_no3 = 2.5e-9` (line 1106)
- `fates_cnp_vmax_p = 5e-10` (line 1109)

These are calibrated for RD mode. If you switch to ECA you usually need to raise them.

Sources: `parameter_files/fates_params_default.cdl:227-235, 1103-1109`, `main/FatesInterfaceTypesMod.F90:54`.

### 4. Daily N Demand Uses the Sum of `vmax_nh4 + vmax_no3`

Inside FATES, the daily N demand is computed identically in prescribed and coupled modes:

```fortran
ccohort%daily_n_demand = fnrt_c * (vmax_nh4(pft) + vmax_no3(pft)) * sec_per_day
```

(`FatesSoilBGCFluxMod.F90:163-164` and `182-183`.) The individual `vmax_nh4` and `vmax_no3` values only matter to FATES through their sum. The split between NH4 and NO3 matters later in the HLM's ECA or RD competition routine, not in FATES. Sources: `biogeochem/FatesSoilBGCFluxMod.F90:155-191`.

### 5. ECA Half-Saturation Parameters

**The ECA half-saturation constants are `fates_cnp_eca_km_*`, not `fates_cnp_km_*`.** Users who try the latter will get silent parameter-file write failures.

| CDL parameter | Units | Default | Role |
|---|---|---|---|
| `fates_cnp_eca_km_nh4` | gN/m3 | 0.14 | Plant half-saturation for NH4 uptake under ECA |
| `fates_cnp_eca_km_no3` | gN/m3 | 0.27 | Plant half-saturation for NO3 uptake under ECA |
| `fates_cnp_eca_km_p`   | gP/m3 | 0.10 | Plant half-saturation for P uptake under ECA |
| `fates_cnp_eca_km_ptase` | gP/m3 | 1.00 | Half-saturation for biochemical P mineralization via phosphatase |

Good starting points are close to the decomposer KM values, or slightly larger than them. Making plant KM larger than the decomposer KM biases uptake toward the decomposer and increases mineralization flux.

Sources: `parameter_files/fates_params_default.cdl:176-187, 1054-1063`.

### 6. Storage Parameters for Stability

Increasing the target plant storage for C, N, and P improves spin-up stability and resilience. The four parameters that control storage-side behavior are:

| CDL parameter | Units | Default | Semantics |
|---|---|---|---|
| `fates_cnp_nitr_store_ratio` | gN/gN | 1.5 | Target labile N storage as a ratio of the N bound in structural tissues (see `PRTParamsFATESMod.F90:414, 709`) |
| `fates_cnp_phos_store_ratio` | gP/gP | 1.5 | Target labile P storage as a ratio of structural P (`PRTParamsFATESMod.F90:418, 713`) |
| `fates_cnp_store_ovrflw_frac` | fraction | 1.0 | Size of the overflow storage as a fraction of the storage target. Used as `target = target * (1 + store_ovrflw_frac)` in `PRTAllometricCNPMod.F90:1880-1881, 1935, 1952, 2142`. A value of 1.0 means the storage pool can grow to **twice** the nominal target before overflow. This inflates the allowed pool, it does not "dump" excess. |
| `fates_alloc_storage_cushion` | fraction | 1.2 (most PFTs), 2.4 (PFTs 5 and 8) | Maximum storage C pool size relative to the maximum leaf C pool (`parameter_files/fates_params_default.cdl:53-55, 947-948`) |

To make the plant more resilient to nutrient shortfalls, typical moves are to increase `store_ovrflw_frac` (larger effective storage cap), increase `nitr_store_ratio` / `phos_store_ratio` (larger target storage), and/or raise `alloc_storage_cushion` (larger leaf-proportional C storage cap).

**Important correction for users of the Knox 2026 guidebook:** Earlier versions of this wiki described `fates_cnp_store_ovrflw_frac` as "fraction of excess nutrients to overflow". That is backwards. In the code the parameter **inflates the storage target**, it does not drain excess.

Sources: `parteh/PRTParamsFATESMod.F90:268-280, 414-418, 607-621, 709-715`, `parteh/PRTAllometricCNPMod.F90:1880-1881, 1935, 1952, 2142`, `parameter_files/fates_params_default.cdl:197-220, 1072-1089`.

### 7. Retranslocation Parameters Are 2-D (organ, pft)

The retranslocation parameters are declared on two dimensions, `fates_plant_organs` and `fates_pft` (`parameter_files/fates_params_default.cdl:221-226`):

```
double fates_cnp_turnover_nitr_retrans(fates_plant_organs, fates_pft)
double fates_cnp_turnover_phos_retrans(fates_plant_organs, fates_pft)
```

FATES uses them for the leaf and fine-root organs. In `PRTGenericMod.F90:80-85` the organ indices are `leaf_organ = 1`, `fnrt_organ = 2`, `sapw_organ = 3`, `store_organ = 4`, `repro_organ = 5`, `struct_organ = 6`. When you increase retranslocation you must update **both** organ 1 (leaf) and organ 2 (fine root) for the same PFT, otherwise one pathway silently stays at the default.

A2MC Morris shorthand `retrans_nitr_{pft}` / `retrans_phos_{pft}` already expands to the paired (leaf, fine-root) update through `tools/modify_fates_parameters.py`, but hand-edited parameter files must set both organs explicitly.

Sources: `parameter_files/fates_params_default.cdl:221-226, 1091-1097`, `parteh/PRTGenericMod.F90:80-85`.

### 8. Decomposition E-Folding Depth

Increasing the soil decomposition e-folding depth strengthens the decomposition cycle and generates more plant-available nutrients.

- **Host-model parameter (ELM/CLM):** `decomp_depth_efolding` (this is not a FATES parameter; set it in ELM/CLM's BGC namelist)
- **Trade-offs:** higher value gives more nutrient availability but reduces soil carbon and shifts the 14C depth profile.

---

## Monitoring FATES_L2FR

`FATES_L2FR` is the leaf-to-fine-root target biomass scaler. It is updated daily by the PID controller in `CNPAdjustFRootTargets` (`PRTAllometricCNPMod.F90:729-870`). During spin-up and calibration it is the most diagnostic variable for whether the CNP machinery is healthy.

### What to Watch For

| Behavior | Interpretation | Action |
|---|---|---|
| Rapid monotonic drift | PID is over-reacting or nutrient supply is too weak or too strong | Reduce `fates_cnp_pid_kp` by a factor of 10 |
| L2FR less than 0.1 or greater than 10 | Poor calibration or unstable dynamics | Investigate nutrient supply and storage parameters |
| Reaches a steady value | Good calibration | Proceed to the next phase |
| Canopy and understory differentiate | Normal | Expected |

### PID Controller Parameters

The PID controller drives `l2fr` based on the log ratio of relative C storage to the relative N or P storage of the plant (whichever is more limiting). The update equation is at `PRTAllometricCNPMod.F90:856-858`:

```fortran
l2fr_delta = pid_kp(ipft) * cx_logratio &
           + pid_ki(ipft) * cx_int      &
           + pid_kd(ipft) * ema_dcxdt
```

| CDL parameter | Default | Role |
|---|---|---|
| `fates_cnp_pid_kp` | 0.0005 | Proportional gain. Reduce by 10x if L2FR is unstable. |
| `fates_cnp_pid_ki` | 0.0 | Integral gain. Raise carefully if there is a persistent steady-state offset. |
| `fates_cnp_pid_kd` | 0.1 | Derivative gain applied to the 20-day EMA of `d(cx_logratio)/dt`. Raise if the controller is oscillating. |

The controller is only called when `spinup_state == 1 .and. yr > nyears_ad_carbon_only`, or under any non-AD spin-up (`PRTAllometricCNPMod.F90:1907-1913`). `nyears_ad_carbon_only` is an ELM/CLM-side namelist variable (`elm_varctl`), not a FATES parameter.

Sources: `parteh/PRTAllometricCNPMod.F90:729-870, 1907-1913`, `parameter_files/fates_params_default.cdl:203-211, 1078-1082`.

---

## Strategies for Insufficient Nutrient Availability

If the soil is not generating enough plant-available N or P for the vegetation:

### A. Free-living N fixation

Free-living fixation is handled on the ELM/CLM side. Increasing the hard-coded constant in ELM source (historically named `test_mult` in some branches) is not a supported FATES knob.

### B. Decomposition depth

ELM/CLM parameter `decomp_depth_efolding`. Deeper e-folding depth means more mineralization.

### C. Enable symbiotic fixation on a PFT

**Use `fates_cnp_nfix1`, not `fates_cnp_nfix`.** The parameter is declared in `parameter_files/fates_params_default.cdl:194-196`:

```
double fates_cnp_nfix1(fates_pft) ;
  fates_cnp_nfix1:units = "fraction" ;
  fates_cnp_nfix1:long_name = "fractional surcharge added to maintenance respiration that drives symbiotic fixation" ;
```

The default is 0 for every PFT. A non-zero value adds a **fractional surcharge to maintenance respiration** that drives symbiotic fixation. It is not a "fraction of N demand met by fixation". Treat it as a respiration-tax tuning knob and raise it gradually.

Sources: `parameter_files/fates_params_default.cdl:194-196, 1070`.

### D. Reduce leaching

Target NO3 leaching in the HLM by reducing the relevant leaching scalar (check the `SMIN_NO3_LEACHED` history variable).

### E. Increase retranslocation

- `fates_cnp_turnover_nitr_retrans` (2-D, set organ 1 and organ 2 together)
- `fates_cnp_turnover_phos_retrans` (2-D, set organ 1 and organ 2 together)

### F. Monitor litter and SOM C:N, C:P

Track ratios to catch runaway immobilization:

| Diagnostic ratio | History variables |
|---|---|
| Litter C:N | `TOTLITC / TOTLITN` |
| Litter C:P | `TOTLITC / TOTLITP` |
| SOM C:N | `TOTSOMC / TOTSOMN` |
| SOM C:P | `TOTSOMC / TOTSOMP` |

If these ratios drift upward over decades the system is starving, usually meaning that heterotrophic respiration is too slow or mineralization is too weak.

---

## Site Setup: Step-by-Step

### Step 1: Carbon-Only Baseline (about 100 years)

Run a carbon-only simulation with `parteh_mode = 1` for roughly 100 years. Goal: establish a reasonable vegetation demographic state before enabling nutrient machinery. If carbon-only spin-up itself is unstable, CNP spin-up will not fix it.

### Step 2: Initial CNP with Full Supplementation

Switch to `parteh_mode = 2`. Run AD spin-up with both N and P supplemented the whole time. Start at year 0001. Use default `vmax_*` as a starting point (defaults are RD-calibrated, so raise them by about 2 orders of magnitude if you are running ECA).

Evaluate at end of this phase:

- `TLAI` leaf area index
- `FATES_VEGC_ABOVEGROUND`
- `FATES_NPP`
- `FATES_NEFFLUX` and `FATES_PEFFLUX` (the amount of uptake that the plant had to dump because its storage targets were already full)

The efflux values are set in `PRTAllometricCNPMod.F90:1990-2002` inside subroutine `CNPAllocateRemainder`. They are set to zero in prescribed-uptake mode and to the leftover `n_gain` or `p_gain` in coupled mode.

Decision tree:

```
Low biomass + low NPP + near-zero efflux  -> vmax is too small, raise
High biomass + high NPP + large efflux    -> vmax is too large, lower
```

Binary search on `fates_cnp_vmax_nh4`, `fates_cnp_vmax_no3`, `fates_cnp_vmax_p` until the vegetation matches the carbon-only run and `FATES_NEFFLUX` is small.

### Step 3: Turn N Limitation On

Switch off N supplementation (`suplnitro = NONE`) after a few tens of years inside AD spin-up, using ELM/CLM's `nyears_ad_carbon_only` namelist variable (for example 10, 20, or 25, depending on how hard the shock is to absorb). FATES will detect the transition through the `spinup_state == 1 .and. yr > nyears_ad_carbon_only` gate in `PRTAllometricCNPMod.F90:1907-1913` and let the PID controller start updating L2FR dynamically.

Expected behavior at the transition:

- Plants start adjusting roots, visible in `FATES_L2FR`
- Transient shock in biomass
- Drop in NPP

Iterate by slowly increasing `vmax_*` until the canopy re-stabilizes after the shock. If the shock is too strong, reduce `nyears_ad_carbon_only` so that the transition happens earlier in the spin-up.

Success indicators:

- `FATES_NPP` stabilizes
- `FATES_NEFFLUX / FATES_NUPTAKE` is small (strong demand, small waste)

### Step 4: Extended Spin-Up (500+ years)

Extend the run under stationary pre-industrial forcing. Target a multi-decade rolling average of `FATES_NEP` near zero.

---

## Key Output Variables

### Unit Conversion

- FATES flux variables are in kg per m2 per s
- To convert to kg per m2 per yr multiply by 31,536,000
- ELM/CLM non-FATES variables are in g per m2 per s

### Recommended History Variables

```
# Carbon and productivity
FATES_NPP, FATES_NEP, NEP, FATES_HET_RESP, FATES_VEGC_ABOVEGROUND

# Structure
TLAI, FATES_L2FR

# Nutrient dynamics
FATES_NDEMAND, FATES_PDEMAND
FATES_NH4UPTAKE, FATES_NO3UPTAKE, FATES_PUPTAKE
FATES_NEFFLUX, FATES_PEFFLUX
FATES_NFIX_SYM, NFIX_TO_SMINN

# Soil pools
TOTSOMC, TOTSOMN, TOTSOMP
TOTLITC, TOTLITN, TOTLITP

# Leaching
SMINP_LEACHED, SMIN_NO3_LEACHED, SOM_C_LEACHED
```

---

## Quick Reference: Parameter Checklist

### Must Check Before a CNP Run

| CDL parameter | Value to check | Notes |
|---|---|---|
| `parteh_mode` (namelist) | 2 | Turns on `PRTAllometricCNPMod` |
| `fates_cnp_prescribed_nuptake` | 0 for every PFT | Any non-zero value puts every PFT into prescribed-N uptake mode |
| `fates_cnp_prescribed_puptake` | 0 for every PFT | Any non-zero value puts every PFT into prescribed-P uptake mode |
| `RUN_STARTDATE` | `0001-01-01` | Required for AD spin-up |
| `hlm_nu_com` (set in the HLM) | `'ECA'` or `'RD'` | Controls which HLM competition routine runs |

### Key Tuning Parameters

| CDL parameter | Default | Typical tuning range | Notes |
|---|---|---|---|
| `fates_cnp_vmax_nh4` | 2.5e-9 | about 1e-9 (RD) to 1e-7 (ECA) | Binary search to calibrate |
| `fates_cnp_vmax_no3` | 2.5e-9 | same | Binary search to calibrate |
| `fates_cnp_vmax_p`   | 5.0e-10 | about 1e-10 (RD) to 1e-8 (ECA) | Binary search to calibrate |
| `fates_cnp_eca_km_nh4` | 0.14 | plant KM close to or slightly above decomposer KM | ECA only |
| `fates_cnp_eca_km_no3` | 0.27 | same | ECA only |
| `fates_cnp_eca_km_p`   | 0.10 | same | ECA only |
| `fates_cnp_nitr_store_ratio` | 1.5 | 1.0 to 3.0 | Raise for more storage buffer |
| `fates_cnp_phos_store_ratio` | 1.5 | 1.0 to 3.0 | Raise for more storage buffer |
| `fates_cnp_store_ovrflw_frac` | 1.0 | 0.5 to 2.0 | Inflates storage target; higher means larger storage cap |
| `fates_alloc_storage_cushion` | 1.2 (PFT 5 and 8: 2.4) | 1.0 to 5.0 | Cap on storage C as a multiple of max leaf C |
| `fates_cnp_pid_kp` | 0.0005 | default / 10 | Reduce if L2FR is unstable |
| `fates_cnp_pid_ki` | 0.0 | 0.0 to 0.001 | Use only if a persistent offset remains |
| `fates_cnp_pid_kd` | 0.1 | 0.05 to 0.2 | Tune for oscillation damping |
| `fates_cnp_nfix1` | 0.0 | 0.0 to about 0.1 | Respiration-surcharge knob for symbiotic fixation, PFT-specific |
| `decomp_depth_efolding` | site-specific | raise for more nutrients | ELM/CLM parameter, not FATES |

---

## See Also

- `cnp_allocation.md` (in `plant-physiology/parteh/`) for the three-phase allocation and PID controller
- `nutrient_competition.md` for ECA versus RD, prescribed versus coupled, and scaling modes
- `../plant-physiology/parteh/soil_plant_interface.md` for the uptake mechanics at the soil-plant boundary

---

## References

- FATES CNP Guidebook (Ryan Knox, February 2, 2026)
- FATES technical documentation (FATES commit `e85d997`)
