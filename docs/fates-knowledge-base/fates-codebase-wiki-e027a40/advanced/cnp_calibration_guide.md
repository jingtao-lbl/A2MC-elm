# FATES-CNP Calibration Guide

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

<details>
<summary>Relevant source files</summary>

- `parteh/PRTAllometricCNPMod.F90` (CNP allocation, PID fine-root controller, storage overflow, efflux)
- `parteh/PRTParamsFATESMod.F90` (`TransferParamsPRT` reads CNP PARTEH parameters via `pstruct%GetParamFromName`)
- `biogeochem/FatesSoilBGCFluxMod.F90` (N/P demand computation, prescribed vs coupled uptake, boundary conditions to the HLM)
- `main/EDPftvarcon.F90` (`TransferParamsPFT` reads PFT parameters such as `fates_cnp_vmax_nh4`, `fates_cnp_vmax_no3`, `fates_cnp_vmax_p`, `fates_cnp_prescribed_nuptake`, `fates_cnp_prescribed_puptake`, `fates_cnp_eca_km_*`)
- `main/FatesConstantsMod.F90` (enum constants: `prescribed_n_uptake = 1`, `coupled_n_uptake = 2`, `coupled_np_comp_scaling = 1`, `trivial_np_comp_scaling = 2`)
- `main/FatesInterfaceMod.F90` (initialization of `n_uptake_mode`, `p_uptake_mode`, `fates_np_comp_scaling`)
- `main/FatesInterfaceTypesMod.F90` (`hlm_nu_com`, `hlm_parteh_mode`, `hlm_nitrogen_suppl`, `hlm_phosphorus_suppl`)
- `main/JSONParameterUtilsMod.F90` (`JSONRead` parameter loader, replaces the api 25 NetCDF/CDL read path)
- `parameter_files/fates_params_default.json` (ground-truth defaults for every `fates_cnp_*` parameter)

</details>

**Author:** Jing Tao with Claude. Adapted from the FATES CNP Guidebook by Ryan Knox, with all parameter names, defaults, and line citations re-verified against FATES commit `e027a40` (sci.1.91.1_api.43.1.0).

This guide gives practical guidance for calibrating FATES with coupled carbon, nitrogen, and phosphorus (CNP) dynamics. It covers core concepts, common pitfalls, diagnostic strategies, and a step-by-step site setup procedure. **Every FATES parameter name mentioned in this guide has been verified to exist in `parameter_files/fates_params_default.json` at commit `e027a40`.** All listed defaults are the 14-PFT defaults shipped in that file.

> **api 43 file format change.** The CDL parameter file (`fates_params_default.cdl`) used in earlier FATES releases was retired at api 43. The canonical parameter file is now `parameter_files/fates_params_default.json`. The legacy CDL files are archived under `parameter_files/archive/` only. The JSON file is read by `JSONRead` in `main/JSONParameterUtilsMod.F90` and dispatched to FATES module storage by `FatesTransferParameters` (no two-phase Register / Receive split). Parameter line numbers are no longer meaningful; reference parameters by name.

---

## Core Concepts

### Nutrient Cycling Modes

ELM and CLM always cycle nutrients internally when FATES is on. FATES itself selects between carbon-only allocation and full CNP allocation via the `parteh_mode` namelist value, which populates the module-level flag `hlm_parteh_mode` (`FatesInterfaceTypesMod.F90:85`). The two mode constants are defined in `PRTGenericMod.F90:69-70`:

- `prt_carbon_allom_hyp = 1` (carbon-only allocation, `PRTAllometricCarbonMod.F90`)
- `prt_cnp_flex_allom_hyp = 2` (CNP flexible allocation, `PRTAllometricCNPMod.F90`)

| Mode | Namelist value | Nutrient transfer | Litter nutrients | HLM supplementation |
|---|---|---|---|---|
| FATES-CNP | `parteh_mode = 2` | Mineralized pools to FATES plant storage via boundary conditions | C, N, P in fragmented litter returned to ELM/CLM | `suplnitro = NONE` and `suplphos = NONE` (target end state) |
| FATES carbon-only | `parteh_mode = 1` | No nutrients reach the plant | No nutrient mass in litter | `suplnitro = ALL` and `suplphos = ALL` |

The HLM N and P supplementation status is stored inside FATES as `hlm_nitrogen_suppl` and `hlm_phosphorus_suppl` (`FatesInterfaceTypesMod.F90:61-62`); both take the integer values `itrue` (supplementing) or `ifalse` (not supplementing). These two flags now drive the dynamic L2FR gating (see "PID Controller Gating" below).

Sources: `parteh/PRTAllometricCNPMod.F90`, `parteh/PRTAllometricCarbonMod.F90`, `parteh/PRTGenericMod.F90:69-70`, `main/FatesInterfaceTypesMod.F90:61-62, 85`.

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

The transition between supplemented and limited mode is now governed by the HLM-side N and P supplementation flags (`suplnitro`, `suplphos` namelist), not by an AD-spinup year counter inside FATES. See "PID Controller Gating" below.

---

## Critical Gotchas

### 1. AD Simulation Must Start at Year 0001

Carbon AD mode requires `RUN_STARTDATE = '0001-01-01'`:

```bash
./xmlchange --append ELM_BLDNML_OPTS="-bgc_spinup on"
./xmlchange RUN_STARTDATE='0001-01-01'
```

### 2. The Default Is Now Coupled Uptake (Not Prescribed)

FATES decides between prescribed and coupled uptake automatically at initialization, based on the sign of the PFT-level parameters `fates_cnp_prescribed_nuptake` and `fates_cnp_prescribed_puptake` (`FatesInterfaceMod.F90:962-972`):

```fortran
if (any(abs(EDPftvarcon_inst%prescribed_nuptake(:)) > nearzero)) then
   n_uptake_mode = prescribed_n_uptake   ! integer 1
else
   n_uptake_mode = coupled_n_uptake      ! integer 2
end if

if (any(abs(EDPftvarcon_inst%prescribed_puptake(:)) > nearzero)) then
   p_uptake_mode = prescribed_p_uptake
else
   p_uptake_mode = coupled_p_uptake
end if
```

**If any PFT has a non-zero `fates_cnp_prescribed_nuptake`, every PFT at the site is driven in prescribed-N mode.** The same rule holds for P. The integer constants are defined in `FatesConstantsMod.F90:113-119`.

> **Drift from earlier FATES releases.** Up through e85d997 the default `fates_params_default.cdl` set both `fates_cnp_prescribed_nuptake` and `fates_cnp_prescribed_puptake` to 1.0 for every PFT, which silently put new sites into prescribed-uptake mode. **At e027a40 both defaults are 0.0** for all 14 PFTs in `parameter_files/fates_params_default.json`, so out-of-the-box FATES is in coupled CNP mode. Calibration recipes carried over from earlier wikis that say "you must set both to 0 for coupled mode" are inverted; under e027a40 that condition is the default. The flip-side warning is now active: starting from a legacy site config that retains `prescribed_*uptake = 1` will silently switch the entire site into prescribed mode.

In prescribed-N mode, the daily N uptake is computed locally inside `FatesSoilBGCFluxMod.F90:174-189`:

```fortran
ccohort%daily_nh4_uptake = fnrt_c * vmax_nh4(pft) * prescribed_nuptake(pft) * sec_per_day
ccohort%daily_no3_uptake = fnrt_c * vmax_no3(pft) * prescribed_nuptake(pft) * sec_per_day
```

No mass is removed from the soil BGC pools. The daily demand formula is identical in prescribed and coupled modes (see "RD vs ECA vmax" below). In downstream CNP allocation, prescribed mode also disables the efflux path (`PRTAllometricCNPMod.F90:1993-2005`) and forces `n_efflux = 0` and `p_efflux = 0`, so leftover gain is preserved as demand for the next step rather than being dumped.

Sources: `biogeochem/FatesSoilBGCFluxMod.F90:174-225`, `parteh/PRTAllometricCNPMod.F90:1993-2005`, `main/FatesInterfaceMod.F90:962-972`, `parameter_files/fates_params_default.json` (`fates_cnp_prescribed_nuptake`, `fates_cnp_prescribed_puptake`).

**Known source-code quirk (e027a40, unchanged from e85d997):** at `FatesSoilBGCFluxMod.F90:221` the P gain in prescribed mode is scaled by `prescribed_nuptake(pft)` instead of `prescribed_puptake(pft)`:

```fortran
ccohort%daily_p_gain = fnrt_c * EDPftvarcon_inst%vmax_p(pft) * sec_per_day * EDPftvarcon_inst%prescribed_nuptake(pft)
```

Users running in full prescribed-N and prescribed-P mode should be aware that the P side of the gain currently follows the N fraction. This is a FATES bug, not a calibration choice.

### 3. ECA vs RD Vmax Magnitudes

The two soil BGC competition modes, ECA and RD, have very different typical `vmax_*` magnitudes because of how the HLM's competition routine filters demand:

| HLM competition | Typical `vmax_nh4`, `vmax_no3`, `vmax_p` | Notes |
|---|---|---|
| ECA (`hlm_nu_com = 'ECA'`) | approximately 1e-7 gN or gP per gC per s | Stronger source limitation imposed in HLM; FATES needs a larger `vmax` to push demand through |
| RD (`hlm_nu_com = 'RD'`) | approximately 1e-9 | Weaker limitation from HLM |

JSON defaults at e027a40 (`parameter_files/fates_params_default.json`):

- `fates_cnp_vmax_nh4 = 2.5e-9` gN/gC/s (uniform across all 14 PFTs)
- `fates_cnp_vmax_no3 = 2.5e-9` gN/gC/s (uniform across all 14 PFTs)
- `fates_cnp_vmax_p = 5e-10` gP/gC/s (uniform across all 14 PFTs)

These are calibrated for RD mode. If you switch to ECA you usually need to raise them.

Sources: parameter file by name (`fates_cnp_vmax_nh4`, `fates_cnp_vmax_no3`, `fates_cnp_vmax_p`), `main/FatesInterfaceTypesMod.F90:54`.

### 4. Daily N Demand Uses the Sum of `vmax_nh4 + vmax_no3`

Inside FATES, the daily N demand is computed identically in prescribed and coupled modes:

```fortran
ccohort%daily_n_demand = fnrt_c * (vmax_nh4(pft) + vmax_no3(pft)) * sec_per_day
```

(`FatesSoilBGCFluxMod.F90:182-183` and `201-202`.) The individual `vmax_nh4` and `vmax_no3` values only matter to FATES through their sum. The split between NH4 and NO3 matters later in the HLM's ECA or RD competition routine, not in FATES. Sources: `biogeochem/FatesSoilBGCFluxMod.F90:174-211`.

### 5. ECA Half-Saturation Parameters

**The ECA half-saturation constants are `fates_cnp_eca_km_*`, not `fates_cnp_km_*`.** Users who try the latter will get silent parameter-file write failures.

| JSON parameter | Units | Default (uniform across 14 PFTs) | Role |
|---|---|---|---|
| `fates_cnp_eca_km_nh4` | gN/m3 | 0.14 | Plant half-saturation for NH4 uptake under ECA |
| `fates_cnp_eca_km_no3` | gN/m3 | 0.27 | Plant half-saturation for NO3 uptake under ECA |
| `fates_cnp_eca_km_p`   | gP/m3 | 0.10 | Plant half-saturation for P uptake under ECA |
| `fates_cnp_eca_km_ptase` | gP/m3 | 1.00 | Half-saturation for biochemical P mineralization via phosphatase |

Good starting points are close to the decomposer KM values, or slightly larger than them. Making plant KM larger than the decomposer KM biases uptake toward the decomposer and increases mineralization flux.

Other ECA-family parameters that did not appear in the e85d997 calibration guide but are present at e027a40 and should be inspected before tuning: `fates_cnp_eca_decompmicc` (default 280 gC/m3, controls the decomposer biomass profile passed to the HLM, see `FatesSoilBGCFluxMod.F90:510-511`), `fates_cnp_eca_alpha_ptase` and `fates_cnp_eca_lambda_ptase` (both default 0; "INACTIVE, KEEP AT 0" per the parameter long-name), `fates_cnp_eca_vmax_ptase` (5e-9 gP/m2/s), and `fates_cnp_eca_plant_escalar` (advanced ECA tuning knob).

Sources: parameter file by name (`fates_cnp_eca_km_nh4`, `fates_cnp_eca_km_no3`, `fates_cnp_eca_km_p`, `fates_cnp_eca_km_ptase`, `fates_cnp_eca_decompmicc`).

### 6. Storage Parameters for Stability

Increasing the target plant storage for C, N, and P improves spin-up stability and resilience. The four parameters that control storage-side behavior are:

| JSON parameter | Units | Default | Semantics |
|---|---|---|---|
| `fates_cnp_nitr_store_ratio` | gN/gN | 1.5 (uniform) | Target labile N storage as a ratio of the N bound in structural tissues. Read in `PRTParamsFATESMod.F90:343-345`. |
| `fates_cnp_phos_store_ratio` | gP/gP | 1.5 (uniform) | Target labile P storage as a ratio of structural P. Read in `PRTParamsFATESMod.F90:347-349`. |
| `fates_cnp_store_ovrflw_frac` | fraction | 1.0 (uniform) | Size of the overflow storage as a fraction of the storage target. Used as `target = target * (1 + store_ovrflw_frac)` in `PRTAllometricCNPMod.F90:1883-1884, 1938, 1955, 2138`. A value of 1.0 means the storage pool can grow to **twice** the nominal target before overflow. This inflates the allowed pool, it does not "dump" excess. Read in `PRTParamsFATESMod.F90:247-249`. |
| `fates_alloc_storage_cushion` | fraction | 1.2 most PFTs; 2.4 for PFTs 5 and 8 (broadleaf hydrodecid tropical tree, broadleaf hydrodecid extratropical shrub); 1.5 for PFT 10 (broadleaf evergreen arctic shrub); 1.4 for PFT 11 (broadleaf colddecid arctic shrub) | Maximum storage C pool size relative to the maximum leaf C pool |

To make the plant more resilient to nutrient shortfalls, typical moves are to increase `store_ovrflw_frac` (larger effective storage cap), increase `nitr_store_ratio` / `phos_store_ratio` (larger target storage), and/or raise `alloc_storage_cushion` (larger leaf-proportional C storage cap).

**Important correction for users of the Knox 2026 guidebook:** earlier versions of this wiki described `fates_cnp_store_ovrflw_frac` as "fraction of excess nutrients to overflow". That is backwards. In the code the parameter **inflates the storage target**, it does not drain excess.

Sources: `parteh/PRTParamsFATESMod.F90:247-249, 343-349`, `parteh/PRTAllometricCNPMod.F90:1883-1884, 1938, 1955, 2138`, parameter file by name.

### 7. Retranslocation Parameters Are 2-D (organ, pft) — Now With a 4-Slot Organ Axis

The retranslocation parameters are declared on two dimensions, `fates_plant_organs` and `fates_pft`. **At api 43 the parameter-file `fates_plant_organs` axis was collapsed from 6 to 4** (`fates_params_info_e027a40.json:16`). The 4 parameter-file slots map to PRTGeneric organ ids through `fates_alloc_organ_id = [1, 2, 3, 6]` (`fates_params_info_e027a40.json:54-60`):

| Parameter-file slot (1..4) | PRTGeneric organ id | Organ name |
|---|---|---|
| 1 | 1 | leaf |
| 2 | 2 | fine root |
| 3 | 3 | sapwood |
| 4 | 6 | structure |

Storage (PRTGeneric `store_organ = 4`) and reproductive (PRTGeneric `repro_organ = 5`) tissues are still tracked internally in `PRTGenericMod.F90:80-85`, but they no longer have PFT-specific stoichiometry slots in the parameter file.

```
fates_cnp_turnover_nitr_retrans(fates_plant_organs, fates_pft)   ! shape (4, 14)
fates_cnp_turnover_phos_retrans(fates_plant_organs, fates_pft)   ! shape (4, 14)
```

Defaults at e027a40 are 0.25 in slots 1 (leaf) and 2 (fine root) for every PFT, and 0.0 in slots 3 (sapwood) and 4 (structure). When you increase retranslocation you must update **both** slot 1 (leaf) and slot 2 (fine root) for the same PFT, otherwise one pathway silently stays at the default.

A2MC Morris shorthand `retrans_nitr_{pft}` / `retrans_phos_{pft}` already expands to the paired (leaf, fine-root) update through `tools/modify_fates_parameters.py`. Because the leaf and fine-root indices are still 1 and 2 in both the parameter file (1..4 axis) and the PRTGeneric internal ids (1..6), the shorthand expansion remains correct, but the parameter-file array shape that downstream tooling allocates is now (4, 14), not (6, 12).

Sources: `parteh/PRTGenericMod.F90:80-85`, parameter file by name (`fates_alloc_organ_id`, `fates_alloc_organ_name`, `fates_cnp_turnover_nitr_retrans`, `fates_cnp_turnover_phos_retrans`).

### 8. Decomposition E-Folding Depth

Increasing the soil decomposition e-folding depth strengthens the decomposition cycle and generates more plant-available nutrients.

- **Host-model parameter (ELM/CLM):** `decomp_depth_efolding` (this is not a FATES parameter; set it in ELM/CLM's BGC namelist)
- **Trade-offs:** higher value gives more nutrient availability but reduces soil carbon and shifts the 14C depth profile.

---

## Monitoring FATES_L2FR

`FATES_L2FR` is the leaf-to-fine-root target biomass scaler. It is updated daily by the PID controller in `CNPAdjustFRootTargets` (`PRTAllometricCNPMod.F90:733-874`). During spin-up and calibration it is the most diagnostic variable for whether the CNP machinery is healthy.

### What to Watch For

| Behavior | Interpretation | Action |
|---|---|---|
| Rapid monotonic drift | PID is over-reacting or nutrient supply is too weak or too strong | Reduce `fates_cnp_pid_kp` by a factor of 10 |
| L2FR less than 0.1 or greater than 10 | Poor calibration or unstable dynamics | Investigate nutrient supply and storage parameters |
| Reaches a steady value | Good calibration | Proceed to the next phase |
| Canopy and understory differentiate | Normal | Expected |

### PID Controller Parameters

The PID controller drives `l2fr` based on the log ratio of relative C storage to the relative N or P storage of the plant (whichever is more limiting). The update equation is at `PRTAllometricCNPMod.F90:860-862`:

```fortran
l2fr_delta = prt_params%pid_kp(ipft)*cx_logratio + &
             prt_params%pid_ki(ipft)*cx_int      + &
             prt_params%pid_kd(ipft)*ema_dcxdt
```

| JSON parameter | Default (uniform across 14 PFTs) | Role |
|---|---|---|
| `fates_cnp_pid_kp` | 0.0005 | Proportional gain. Reduce by 10x if L2FR is unstable. |
| `fates_cnp_pid_ki` | 0.0    | Integral gain. Raise carefully if there is a persistent steady-state offset. |
| `fates_cnp_pid_kd` | 0.1    | Derivative gain applied to the 20-day EMA of `d(cx_logratio)/dt`. Raise if the controller is oscillating. |

### PID Controller Gating

**The gate that decides whether `CNPAdjustFRootTargets` is called each daily step was rewritten at api 43.** The old condition (`spinup_state == 1 .and. yr > nyears_ad_carbon_only`, with non-AD spin-up always firing) is gone. The current gate at `PRTAllometricCNPMod.F90:1909-1915` is:

```fortran
! turn on the dynamic L2FR if either nutrient is not being supplemented
limiting_p = ((p_uptake_mode .eq. coupled_p_uptake) .and. (hlm_phosphorus_suppl .eq. ifalse))
limiting_n = ((n_uptake_mode .eq. coupled_p_uptake) .and. (hlm_nitrogen_suppl .eq. ifalse))
if (limiting_p .or. limiting_n) then
  call this%CNPAdjustFRootTargets(target_c,target_dcdd)
end if
```

The PID is engaged only when (a) the relevant element is in coupled-uptake mode AND (b) the HLM is not supplementing that element (`hlm_nitrogen_suppl == ifalse`, or the analogous P flag). This decouples PID activation from the AD-spinup year counter and ties it directly to the two namelist switches that the operator already has to set (`suplnitro` for N, `suplphos` for P) and to the per-PFT `fates_cnp_prescribed_*uptake` values that determine `n_uptake_mode` and `p_uptake_mode` at site init.

> **Source-code typo note.** Line 1911 reads `n_uptake_mode .eq. coupled_p_uptake`, comparing the N-side mode variable against the P-uptake constant. Both `coupled_n_uptake` and `coupled_p_uptake` equal integer 2 in `FatesConstantsMod.F90:113-119`, so the comparison evaluates as intended. The behavior is correct; the symbol is misleading.
>
> **Drift note.** Earlier wiki versions cited `nyears_ad_carbon_only` (an ELM `elm_varctl` namelist variable) as the AD spinup year threshold inside the gate. That variable does not appear anywhere in `PRTAllometricCNPMod.F90` at e027a40. If you carry forward calibration recipes that mention it, replace the AD-year threshold step with an explicit `suplnitro` / `suplphos` namelist transition (see "Step 3" below).

Sources: `parteh/PRTAllometricCNPMod.F90:733-874, 1909-1915`, `main/FatesConstantsMod.F90:113-119`, `main/FatesInterfaceTypesMod.F90:61-62`, parameter file by name.

---

## Strategies for Insufficient Nutrient Availability

If the soil is not generating enough plant-available N or P for the vegetation:

### A. Free-living N fixation

Free-living fixation is handled on the ELM/CLM side. Increasing the hard-coded constant in ELM source (historically named `test_mult` in some branches) is not a supported FATES knob.

### B. Decomposition depth

ELM/CLM parameter `decomp_depth_efolding`. Deeper e-folding depth means more mineralization.

### C. Enable symbiotic fixation on a PFT

**Use `fates_cnp_nfix1`, not `fates_cnp_nfix`.** The parameter is declared in the JSON parameter file with:

```
"fates_cnp_nfix1": {
  "dtype": "float",
  "dims": ["fates_pft"],
  "long_name": "fractional surcharge added to maintenance respiration that drives symbiotic fixation",
  "units": "fraction",
  "data": [0.0, ...]   ! 14 zeros at e027a40
}
```

The default is 0 for every PFT. A non-zero value adds a **fractional surcharge to maintenance respiration** that drives symbiotic fixation. It is not a "fraction of N demand met by fixation". Treat it as a respiration-tax tuning knob and raise it gradually.

Source: parameter file by name (`fates_cnp_nfix1`).

### D. Reduce leaching

Target NO3 leaching in the HLM by reducing the relevant leaching scalar (check the `SMIN_NO3_LEACHED` history variable).

### E. Increase retranslocation

- `fates_cnp_turnover_nitr_retrans` (2-D, set parameter-file slot 1 (leaf) and slot 2 (fine root) together)
- `fates_cnp_turnover_phos_retrans` (2-D, same)

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

Switch to `parteh_mode = 2`. Run AD spin-up with both N and P supplemented the whole time (`suplnitro = ALL` and `suplphos = ALL`). Start at year 0001. Use default `vmax_*` as a starting point (defaults are RD-calibrated, so raise them by about 2 orders of magnitude if you are running ECA). Confirm that `fates_cnp_prescribed_nuptake` and `fates_cnp_prescribed_puptake` are 0.0 for every PFT in the parameter file (this is the default at e027a40, but legacy site configs may still carry the e85d997 default of 1.0 — see "The Default Is Now Coupled Uptake" above).

Evaluate at end of this phase:

- `TLAI` leaf area index
- `FATES_VEGC_ABOVEGROUND`
- `FATES_NPP`
- `FATES_NEFFLUX` and `FATES_PEFFLUX` (the amount of uptake that the plant had to dump because its storage targets were already full)

The efflux values are set in `PRTAllometricCNPMod.F90:1993-2005` inside subroutine `CNPAllocateRemainder`. They are set to zero in prescribed-uptake mode and to the leftover `n_gain` or `p_gain` in coupled mode.

Decision tree:

```
Low biomass + low NPP + near-zero efflux  -> vmax is too small, raise
High biomass + high NPP + large efflux    -> vmax is too large, lower
```

Binary search on `fates_cnp_vmax_nh4`, `fates_cnp_vmax_no3`, `fates_cnp_vmax_p` until the vegetation matches the carbon-only run and `FATES_NEFFLUX` is small.

### Step 3: Turn N Limitation On

Switch off N supplementation by setting the HLM namelist `suplnitro = NONE` (leave `suplphos = ALL` for now). Internally this clears `hlm_nitrogen_suppl` to `ifalse`. From that moment, for every PFT that is in coupled-N uptake mode, the new gate at `PRTAllometricCNPMod.F90:1909-1915` will fire and the PID controller will start updating L2FR daily.

There is **no FATES-side namelist year-counter** (`nyears_ad_carbon_only` is gone from `PRTAllometricCNPMod.F90` at e027a40). The transition is operator-controlled, by switching the supplementation namelist at the right point in the case workflow. Common patterns:

- AD spin-up split into two segments: an initial `suplnitro = ALL` segment of 10-25 years to let demographics stabilize, then a continuation case with `suplnitro = NONE` for the rest of AD spin-up. The shock magnitude depends on the first-segment length.
- AD spin-up with `suplnitro = NONE` from the start, accepting a larger initial transient.

Expected behavior at the transition:

- Plants start adjusting roots, visible in `FATES_L2FR`
- Transient shock in biomass
- Drop in NPP

Iterate by slowly increasing `vmax_*` until the canopy re-stabilizes after the shock. If the shock is too strong, run a longer fully-supplemented segment first so the demographic state is more mature before the gate flips.

Success indicators:

- `FATES_NPP` stabilizes
- `FATES_NEFFLUX / FATES_NUPTAKE` is small (strong demand, small waste)

### Step 4: Extended Spin-Up (500+ years)

Extend the run under stationary pre-industrial forcing. Target a multi-decade rolling average of `FATES_NEP` near zero. Optionally repeat the supplementation transition for P (`suplphos = NONE`) once the N-limited equilibrium is established.

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

| Parameter | Value to check | Notes |
|---|---|---|
| `parteh_mode` (namelist) | 2 | Turns on `PRTAllometricCNPMod` |
| `fates_cnp_prescribed_nuptake` (JSON) | 0 for every PFT (this is the e027a40 default) | Any non-zero value puts every PFT into prescribed-N uptake mode |
| `fates_cnp_prescribed_puptake` (JSON) | 0 for every PFT (this is the e027a40 default) | Any non-zero value puts every PFT into prescribed-P uptake mode |
| `RUN_STARTDATE` | `0001-01-01` | Required for AD spin-up |
| `hlm_nu_com` (set in the HLM) | `'ECA'` or `'RD'` | Controls which HLM competition routine runs |
| `suplnitro`, `suplphos` (HLM namelist) | `ALL` initially, transition to `NONE` per Step 3 | Drive `hlm_nitrogen_suppl` / `hlm_phosphorus_suppl` and the PID gate |

### Key Tuning Parameters

| JSON parameter | Default | Typical tuning range | Notes |
|---|---|---|---|
| `fates_cnp_vmax_nh4` | 2.5e-9 | about 1e-9 (RD) to 1e-7 (ECA) | Binary search to calibrate |
| `fates_cnp_vmax_no3` | 2.5e-9 | same | Binary search to calibrate |
| `fates_cnp_vmax_p`   | 5.0e-10 | about 1e-10 (RD) to 1e-8 (ECA) | Binary search to calibrate |
| `fates_cnp_eca_km_nh4` | 0.14 | plant KM close to or slightly above decomposer KM | ECA only |
| `fates_cnp_eca_km_no3` | 0.27 | same | ECA only |
| `fates_cnp_eca_km_p`   | 0.10 | same | ECA only |
| `fates_cnp_eca_decompmicc` | 280 gC/m3 | site-specific, used in decomposer profile | ECA only |
| `fates_cnp_nitr_store_ratio` | 1.5 | 1.0 to 3.0 | Raise for more storage buffer |
| `fates_cnp_phos_store_ratio` | 1.5 | 1.0 to 3.0 | Raise for more storage buffer |
| `fates_cnp_store_ovrflw_frac` | 1.0 | 0.5 to 2.0 | Inflates storage target; higher means larger storage cap |
| `fates_alloc_storage_cushion` | 1.2 most PFTs (PFTs 5, 8: 2.4; PFT 10: 1.5; PFT 11: 1.4) | 1.0 to 5.0 | Cap on storage C as a multiple of max leaf C |
| `fates_cnp_pid_kp` | 0.0005 | default / 10 | Reduce if L2FR is unstable |
| `fates_cnp_pid_ki` | 0.0 | 0.0 to 0.001 | Use only if a persistent offset remains |
| `fates_cnp_pid_kd` | 0.1 | 0.05 to 0.2 | Tune for oscillation damping |
| `fates_cnp_nfix1` | 0.0 | 0.0 to about 0.1 | Respiration-surcharge knob for symbiotic fixation, PFT-specific |
| `decomp_depth_efolding` | site-specific | raise for more nutrients | ELM/CLM parameter, not FATES |

> **PFT-count note.** The e027a40 default parameter file has **14 PFTs** (was 12 at e85d997). The new positions are `broadleaf_evergreen_arctic_shrub` (PFT 10), `broadleaf_colddecid_arctic_shrub` (PFT 11); the previous PFT 10 (`arctic_c3_grass`) is now PFT 12, and `cool_c3_grass` (PFT 13) and `c4_grass` (PFT 14) are appended. Site configs that hand-craft `(pft)` arrays must be sized for 14, and any prior site-specific calibrations that reference "PFT#10" by integer should be re-checked: at e027a40 PFT#10 is no longer the arctic graminoid.

---

## See Also

- `cnp_allocation.md` (in `plant-physiology/parteh/`) for the three-phase allocation and PID controller
- `nutrient_competition.md` for ECA versus RD, prescribed versus coupled, and scaling modes
- `../plant-physiology/parteh/soil_plant_interface.md` for the uptake mechanics at the soil-plant boundary

---

## References

- FATES CNP Guidebook (Ryan Knox, February 2, 2026)
- FATES technical documentation (FATES commit `e027a40`, sci.1.91.1_api.43.1.0)
