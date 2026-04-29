# Nutrient Competition Modes

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

<details>
<summary>Relevant source files</summary>

- `biogeochem/FatesSoilBGCFluxMod.F90` (uptake modes, BC preparation, BC unpacking)
- `main/FatesInterfaceMod.F90` (initialization of `n_uptake_mode`, `p_uptake_mode`, `fates_np_comp_scaling`)
- `main/FatesInterfaceTypesMod.F90` (`hlm_nu_com` declaration, supplementation flags)
- `main/FatesConstantsMod.F90` (enum constants for uptake modes and scaling modes)
- `main/EDParamsMod.F90` (module storage)
- `parteh/PRTAllometricCNPMod.F90` (CNP allocation entry point)
- `parameter_files/fates_params_default.json` (PFT parameters such as `fates_cnp_prescribed_nuptake`, `fates_cnp_prescribed_puptake`, `fates_cnp_vmax_*`, `fates_cnp_eca_km_*`, `fates_cnp_eca_decompmicc`)

</details>

## Purpose and Scope

This document describes the nutrient competition modes in FATES, which control how plants acquire nitrogen and phosphorus from the soil. The competition system has three orthogonal axes:

1. **Uptake mode** prescribed versus coupled
2. **Competition method** ECA or RD (selected inside the HLM, signalled to FATES through `hlm_nu_com`)
3. **Competitor scaling approach** coupled versus trivial

For how plants allocate acquired nutrients, see `../plant-physiology/parteh/cnp_allocation.md`. For the soil-plant interface mechanics, see `../plant-physiology/parteh/soil_plant_interface.md`.

> **api 43 file format note.** The CDL parameter file referenced in earlier wiki versions (`fates_params_default.cdl`) was retired at api 43. The canonical parameter file is now `parameter_files/fates_params_default.json`, read by `JSONRead` (`main/JSONParameterUtilsMod.F90`). Parameters are referenced by name rather than CDL line number throughout this document.

## Nutrient Uptake Modes

FATES supports two uptake modes, **set automatically per-site at initialization** based on the sign of `fates_cnp_prescribed_nuptake` and `fates_cnp_prescribed_puptake` (`main/FatesInterfaceMod.F90:962-972`):

```fortran
if (any(abs(EDPftvarcon_inst%prescribed_nuptake(:)) > nearzero)) then
   n_uptake_mode = prescribed_n_uptake     ! integer 1
else
   n_uptake_mode = coupled_n_uptake        ! integer 2
end if
```

The four enum constants are declared in `main/FatesConstantsMod.F90:113-119`:

| Constant | Value | Description |
|---|---|---|
| `prescribed_n_uptake` | 1 | Plants receive a prescribed fraction of their N demand locally (no mass removed from HLM pools) |
| `coupled_n_uptake` | 2 | Plants compete with the HLM soil BGC for N |
| `prescribed_p_uptake` | 1 | Plants receive a prescribed fraction of their P demand locally |
| `coupled_p_uptake` | 2 | Plants compete with the HLM soil BGC for P |

**If any PFT in the parameter file has a non-zero `fates_cnp_prescribed_nuptake`, the entire site runs in prescribed-N mode.** Same rule for P.

> **Default flip at api 43.** In `parameter_files/fates_params_default.json` at e027a40, both `fates_cnp_prescribed_nuptake` and `fates_cnp_prescribed_puptake` default to **0.0** for all 14 PFTs. The corresponding default behavior is therefore **coupled mode**. Earlier versions of this wiki documented the e85d997 default of 1.0, which silently put new sites into prescribed mode; users carrying calibration recipes from that era should re-read the "Verify You Are Not in Prescribed-Uptake Mode" gotcha as "Verify your site config has not overridden the new coupled-mode default to 1.0".

Sources: `main/FatesInterfaceMod.F90:962-987`, `main/FatesConstantsMod.F90:113-119`, parameter file by name (`fates_cnp_prescribed_nuptake`, `fates_cnp_prescribed_puptake`).

### Prescribed Uptake Implementation

In prescribed mode the daily NH4 and NO3 uptakes are computed locally inside `UnPackNutrientAquisitionBCs` at `biogeochem/FatesSoilBGCFluxMod.F90:174-189`:

```fortran
ccohort%daily_n_demand = fnrt_c * (vmax_nh4(pft) + vmax_no3(pft)) * sec_per_day
ccohort%daily_nh4_uptake = fnrt_c * vmax_nh4(pft) * prescribed_nuptake(pft) * sec_per_day
ccohort%daily_no3_uptake = fnrt_c * vmax_no3(pft) * prescribed_nuptake(pft) * sec_per_day
```

The P-side at lines 213-225 mirrors this for phosphorus. The daily demand formula is identical in prescribed and coupled modes; the only thing that differs is how the actual uptake is sourced.

Inside CNP allocation, prescribed mode additionally suppresses nutrient efflux: `n_efflux = 0` and `p_efflux = 0` in `PRTAllometricCNPMod.F90:1993-2005`, so leftover gain is preserved as demand for the next step rather than being dumped.

### Coupled Uptake Implementation

In coupled mode, the HLM BGC model returns the actual uptake via the boundary-condition arrays `bc_in%plant_nh4_uptake_flux`, `bc_in%plant_no3_uptake_flux`, and `bc_in%plant_p_uptake_flux` (`FatesSoilBGCFluxMod.F90:191-211, 227-244`). FATES unpacks these from units of `g/m2/day` to `kg/plant/day` and writes them into `ccohort%daily_nh4_uptake`, `daily_no3_uptake`, and `daily_p_gain`.

Coupled mode requires two boundary-condition exchanges per nutrient time step: FATES sends competitor information via `PrepNutrientAquisitionBCs` (see below), the HLM computes uptake, and FATES reads it back in `UnPackNutrientAquisitionBCs`.

Sources: `biogeochem/FatesSoilBGCFluxMod.F90:120-260, 423-540`.

## Competition Methods: `hlm_nu_com`

`hlm_nu_com` is a character string declared at `main/FatesInterfaceTypesMod.F90:54` that tells FATES which competition algorithm the HLM is running. Valid values:

- `'ECA'` Equilibrium Chemistry Approximation
- `'RD'`  Relative Demand
- `'NONE'` No soil BGC coupling (for prescribed uptake only)

The string is set by the HLM during initialization. It affects **what FATES sends to the HLM** through `PrepNutrientAquisitionBCs`: when `hlm_nu_com = 'ECA'`, FATES populates `bc_out%decompmicc`, `bc_out%cn_scalar`, and `bc_out%cp_scalar` in addition to `bc_out%veg_rootc`. When `hlm_nu_com = 'RD'`, only `veg_rootc` is populated.

### ECA (Equilibrium Chemistry Approximation)

ECA mode is a more mechanistic approach that explicitly accounts for decomposer microbial biomass and plant-soil enzyme kinetics when allocating nutrient supply. FATES provides these boundary conditions to the HLM:

- `bc_out%veg_rootc(icomp, nlevdecomp)` fine root biomass by competitor and soil layer in `gC/m3`
- `bc_out%decompmicc(nlevdecomp)` estimated decomposer microbial biomass per layer
- `bc_out%cn_scalar` and `bc_out%cp_scalar` plant-side stress scalars

The decomposer biomass is estimated using an exponential attenuation function weighted by root biomass (`FatesSoilBGCFluxMod.F90:510-514`):

```
decompmicc_layer = decompmicc(pft) * exp(-decompmicc_lambda * abs(z_soil - decompmicc_zmax))
```

where `decompmicc_lambda = 2.5` and `decompmicc_zmax = 7.0e-2` m are hard-coded constants (`FatesSoilBGCFluxMod.F90:448-449`), and `decompmicc(pft)` is read from the parameter `fates_cnp_eca_decompmicc` (units `gC/m3`, default 280 gC/m3 for all 14 PFTs at e027a40). After accumulation across cohorts, the per-layer decomposer biomass is normalized by total root biomass.

**Important:** in this version of FATES, `bc_out%cn_scalar(:)` and `bc_out%cp_scalar(:)` are only ever assigned `1.0` inside FATES (`FatesSoilBGCFluxMod.F90:458-459`). There is no branch that computes them from plant C:N or C:P ratios. They are initialized as a token boundary condition; any plant-side stress weighting of competitors has to be done inside the HLM's BGC model, not inside FATES.

### RD (Relative Demand)

RD mode uses a simpler demand-based nutrient acquisition scheme. FATES only needs to pass root biomass to the HLM, which then partitions available nutrients in proportion to plant demand (the specific implementation is in the HLM, not in FATES). When `hlm_nu_com = 'RD'` and the scaling mode is `trivial_np_comp_scaling`, FATES exits `PrepNutrientAquisitionBCs` early after writing `num_plant_comps = 1` and `ft_index(1) = 1` (`FatesSoilBGCFluxMod.F90:462-468`).

| Mode | Complexity | Key BC outputs | Use case |
|---|---|---|---|
| ECA | high | `veg_rootc`, `decompmicc`, `cn_scalar`, `cp_scalar` | Mechanistic nutrient cycling studies |
| RD  | low  | `veg_rootc` only | Simplified competition, faster runtime |

## Competitor Scaling Modes

### The Enum Constants

`fates_np_comp_scaling` is a module variable declared in `FatesConstantsMod.F90:148` with value `fates_unset_int` at module load, and assigned during initialization. The integer values are:

| Constant | Value | Declared at |
|---|---|---|
| `coupled_np_comp_scaling` | **1** | `main/FatesConstantsMod.F90:120` |
| `trivial_np_comp_scaling` | **2** | `main/FatesConstantsMod.F90:139` |

Earlier versions of this wiki used `0` for trivial scaling. The correct integer is `2`.

### When Each Mode is Used

The scaling mode is **not a user-settable namelist switch**. It is derived in `FatesInterfaceMod.F90:974-987`:

```fortran
if (hlm_parteh_mode .eq. prt_cnp_flex_allom_hyp) then
   if ((p_uptake_mode == coupled_p_uptake) .or. (n_uptake_mode == coupled_n_uptake)) then
      max_comp_per_site     = fates_maxElementsPerSite
      fates_np_comp_scaling = coupled_np_comp_scaling   ! = 1
   else
      max_comp_per_site     = 1
      fates_np_comp_scaling = trivial_np_comp_scaling   ! = 2
   end if
else
   max_comp_per_site     = 1
   fates_np_comp_scaling = trivial_np_comp_scaling      ! = 2
end if
```

So: CNP mode with at least one coupled element yields `coupled_np_comp_scaling = 1`. Any other configuration (carbon-only or fully prescribed uptake) yields `trivial_np_comp_scaling = 2`. **At api 43, with the new default of `fates_cnp_prescribed_*uptake = 0.0`, an out-of-the-box CNP run lands in coupled scaling without any namelist override.**

### Coupled Scaling Mode

In `coupled_np_comp_scaling = 1`, each cohort is treated as an independent competitor. Inside `PrepNutrientAquisitionBCs` the competitor index `icomp` is incremented for each cohort (`FatesSoilBGCFluxMod.F90:481-485`). This gives the HLM one row per cohort in `veg_rootc`, so memory scales with cohort count.

At end of the loop, `bc_out%num_plant_comps = icomp` (`FatesSoilBGCFluxMod.F90:533-534`).

### Trivial Scaling Mode

In `trivial_np_comp_scaling = 2`, all cohorts at a site are aggregated into a single competitor. The competitor index `icomp` is always 1, so root biomass accumulates into `bc_out%veg_rootc(1, :)` (`FatesSoilBGCFluxMod.F90:483-485`). At end of the loop, `bc_out%num_plant_comps = 1`. The HLM sees a single lumped plant community; FATES later distributes the returned uptake to individual cohorts in proportion to their root biomass.

| Scaling mode | Integer | Memory | Fidelity | Max competitors |
|---|---|---|---|---|
| Coupled | 1 | High (one row per cohort) | Cohort specific | ~hundreds per site |
| Trivial | 2 | Low (one row per site) | Site aggregated | 1 per site |

Sources: `biogeochem/FatesSoilBGCFluxMod.F90:423-540`, `main/FatesInterfaceMod.F90:962-987`.

## The `PrepNutrientAquisitionBCs` Subroutine

`PrepNutrientAquisitionBCs` (`biogeochem/FatesSoilBGCFluxMod.F90:423-540`) prepares the boundary conditions the HLM needs to compute nutrient uptake. Key operations:

1. **Zero the output arrays.** `bc_out%veg_rootc(:,:) = 0`, `bc_out%ft_index(:) = -1`. When `hlm_nu_com == 'ECA'`, also zero `bc_out%decompmicc(:)` and set `bc_out%cn_scalar(:) = 1`, `bc_out%cp_scalar(:) = 1`.
2. **Early exit for RD + trivial scaling.** Write `num_plant_comps = 1`, `ft_index(1) = 1`, and return.
3. **Loop over patches and cohorts.** For each cohort, set `icomp` (incrementing under coupled scaling, always 1 under trivial), look up the fine-root carbon `fnrt_c`, and distribute it by depth into `bc_out%veg_rootc(icomp, id)` in units of `gC/m3`.
4. **ECA only: accumulate decomposer biomass.** Compute the exponential profile, weight by root biomass, and accumulate into `bc_out%decompmicc(id)`.
5. **Normalize decomposer biomass** by the total root biomass at each layer (only under ECA).
6. **Set `num_plant_comps`** to `icomp` under coupled scaling or 1 under trivial scaling.

Sources: `biogeochem/FatesSoilBGCFluxMod.F90:423-540`.

## The `UnPackNutrientAquisitionBCs` Subroutine

`UnPackNutrientAquisitionBCs` (`biogeochem/FatesSoilBGCFluxMod.F90:120-260`) reads the HLM's uptake result back into FATES. In prescribed mode, it computes the uptake locally from `vmax_*` and `prescribed_*uptake`. In coupled mode, it reads from `bc_in%plant_*_uptake_flux` arrays and unit-converts to `kg/plant/day`. The conversion is:

```
uptake_kg_per_plant = uptake_g_per_m2 * (kg/g) * AREA / cohort%n
```

**Known source-code quirk at `e027a40`:** at line 221 the P gain in prescribed mode is scaled by `prescribed_nuptake(pft)` instead of `prescribed_puptake(pft)`. This looks like an unintended copy-paste: P gain currently follows the N fraction in prescribed-P mode. Users running with different N and P fractions should be aware of this. (Same bug existed at e85d997.)

Sources: `biogeochem/FatesSoilBGCFluxMod.F90:120-260`.

## Configuration and Control Flags Summary

| Name | Type | Typical values | Set where | Purpose |
|---|---|---|---|---|
| `hlm_nu_com` | character(16) | `'ECA'`, `'RD'`, `'NONE'` | declared `FatesInterfaceTypesMod.F90:54`, set by HLM at init | Competition method used by HLM |
| `fates_np_comp_scaling` | integer | `coupled_np_comp_scaling = 1`, `trivial_np_comp_scaling = 2` | module var in `FatesConstantsMod.F90:148`, set by FATES at init (not user-facing) | Competitor scaling approach |
| `n_uptake_mode` | integer | `prescribed_n_uptake = 1`, `coupled_n_uptake = 2` | module var, set by FATES at init from `fates_cnp_prescribed_nuptake` | Nitrogen uptake mode |
| `p_uptake_mode` | integer | `prescribed_p_uptake = 1`, `coupled_p_uptake = 2` | module var, set by FATES at init from `fates_cnp_prescribed_puptake` | Phosphorus uptake mode |
| `hlm_parteh_mode` | integer | `prt_carbon_allom_hyp = 1`, `prt_cnp_flex_allom_hyp = 2` | `FatesInterfaceTypesMod.F90:85`, set from namelist `parteh_mode` | PARTEH allocation hypothesis |
| `hlm_nitrogen_suppl` | integer | `itrue` (1) or `ifalse` (0) | `FatesInterfaceTypesMod.F90:61`, set from HLM namelist `suplnitro` | True if HLM is supplementing N (gates the dynamic L2FR PID) |
| `hlm_phosphorus_suppl` | integer | `itrue` (1) or `ifalse` (0) | `FatesInterfaceTypesMod.F90:62`, set from HLM namelist `suplphos` | True if HLM is supplementing P (gates the dynamic L2FR PID) |
| `max_comp_per_site` | integer | computed | set by FATES at init | Maximum competitors per site |

### Compatible Mode Combinations

| `hlm_nu_com` | Scaling | n/p uptake | Valid | Notes |
|---|---|---|---|---|
| `'ECA'` | coupled | coupled | yes | Full mechanistic competition. **This is the e027a40 default** when `parteh_mode = 2` and the parameter file is unmodified. |
| `'ECA'` | trivial | coupled | yes | (not actually reachable: trivial implies prescribed) |
| `'ECA'` | trivial | prescribed | yes | ECA in HLM, plants get prescribed uptake |
| `'RD'`  | coupled | coupled | yes | Simple competition, per-cohort |
| `'RD'`  | trivial | prescribed | yes | Simple competition aggregated, plants get prescribed uptake |
| `'NONE'`| trivial | prescribed | yes | No soil BGC coupling at all |
| `'NONE'`| any      | coupled | no  | Invalid: no competition method |

Note: because `fates_np_comp_scaling` is derived from the uptake modes, the `coupled` scaling mode is only reached when at least one of `n_uptake_mode` or `p_uptake_mode` is coupled.

- **Highest fidelity:** ECA + coupled scaling + coupled uptake (now the stock CNP default at api 43)
- **Lowest cost:** any + trivial scaling + prescribed uptake
- **Balanced:** RD + coupled scaling + coupled uptake

Sources: `biogeochem/FatesSoilBGCFluxMod.F90:456-468`, `main/FatesInterfaceMod.F90:962-987`, `main/FatesInterfaceTypesMod.F90:54-85`.
