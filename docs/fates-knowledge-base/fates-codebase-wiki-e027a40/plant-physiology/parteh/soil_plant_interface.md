# Soil-Plant Nutrient Interface

---
**Source pin:** FATES commit e027a40 (sci.1.91.1_api.43.1.0)
**HLM pairing:** ELM at E3SM commit d40b8431
**Last verified:** 2026-04-25
---

**Relevant source files:**
- `biogeochem/FatesSoilBGCFluxMod.F90`
- `biogeochem/FatesCohortMod.F90`
- `main/EDMainMod.F90`
- `main/FatesConstantsMod.F90`
- `main/FatesInterfaceTypesMod.F90`
- `main/EDPftvarcon.F90`
- `biogeophys/FatesPlantRespPhotosynthMod.F90`
- `biogeophys/EDAccumulateFluxesMod.F90`
- `parteh/PRTAllometricCNPMod.F90`
- `parameter_files/fates_params_default.json`

## Purpose and Scope

This document describes how FATES plants exchange nitrogen and phosphorus with the host land model's soil biogeochemistry. The interface is active only under the CNP allocation hypothesis (`prt_cnp_flex_allom_hyp`). Under the carbon-only hypothesis, `UnPackNutrientAquisitionBCs` exits immediately after zeroing the host's plant-uptake flux arrays.

The interface covers:

- Computing per-cohort nutrient demand (from fine-root biomass and PFT `vmax_*` parameters)
- Choosing competition/uptake mode (prescribed vs coupled)
- Packing vegetation state into boundary conditions for the host BGC (`PrepNutrientAquisitionBCs`)
- Unpacking actual uptake fluxes back into cohort state (`UnPackNutrientAquisitionBCs`) **and the new HLM supplementation flags that gate the L2FR PID controller**
- Returning plant efflux/exudation into the litter pool (`EffluxIntoLitterPools`)

For the downstream allocation consumer see [CNP Allocation and Nutrient Dynamics](./cnp_allocation.md). For framework-level context see [PARTEH: Plant Allocation System](./index.md).

## Daily Pipeline

Within the daily loop, the soil-plant exchange runs in this order:

```
1. PrepNutrientAquisitionBCs(csite, bc_in, bc_out)            [FatesSoilBGCFluxMod.F90:423-540]
     |-- writes vegetation state (veg_rootc, decompmicc, num_plant_comps, ft_index) to bc_out
2. Host BGC runs (e.g. CLM5/ELM CN) — reads bc_out, solves nutrient competition,
   fills bc_in%plant_nh4_uptake_flux, bc_in%plant_no3_uptake_flux, bc_in%plant_p_uptake_flux
3. UnPackNutrientAquisitionBCs(sites, bc_in, nitr_suppl, phos_suppl)   [FatesSoilBGCFluxMod.F90:105-255]
     |-- writes the global hlm_nitrogen_suppl / hlm_phosphorus_suppl flags from inputs (lines 140-150)
     |-- reads bc_in, fills ccohort%daily_nh4_uptake, daily_no3_uptake, daily_p_gain
     |-- zeros the bc_in uptake arrays (lines 249-251)
4. currentCohort%daily_n_gain = daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily   [EDMainMod.F90:583-584]
5. DailyPRT(phase=1) — CNP allocation reads daily_n_gain via bc_inout index 4 (netdn)
   The L2FR PID controller is invoked only if (coupled_p AND not phos_suppl) OR (coupled_n AND not nitr_suppl).
```

The N fixation term `sym_nfix_daily` is populated earlier by `FatesPlantRespPhotosynthMod::RootLayerNFixation` (called at `FatesPlantRespPhotosynthMod.F90:1010`). Per-timestep contributions are summed each day in `EDAccumulateFluxesMod.F90:85`. So by step 4 it has already accumulated from the photosynthesis/respiration timestep.

Sources: `(main/EDMainMod.F90:560-634)`, `(biogeochem/FatesSoilBGCFluxMod.F90:105-540)`, `(biogeophys/FatesPlantRespPhotosynthMod.F90:1010,1154-1206)`, `(biogeophys/EDAccumulateFluxesMod.F90:85)`

## Demand Calculation

Every cohort's nutrient demand is proportional to its fine-root carbon biomass:

```fortran
! FatesSoilBGCFluxMod.F90:182-184, 201-202, 220
fnrt_c = ccohort%prt%GetState(fnrt_organ, carbon12_element)
daily_n_demand = fnrt_c * (vmax_nh4(pft) + vmax_no3(pft)) * sec_per_day       ! kgN/plant/day
daily_p_demand = fnrt_c * vmax_p(pft) * sec_per_day                           ! kgP/plant/day
```

`vmax_*` parameters have units of kg-nutrient / kg-fineroot-C / second. Computed demand represents the theoretical maximum uptake if the soil supply is unlimited. It is not directly used by the allocation routine. Instead, it controls the cohort's share under prescribed mode and informs the ECA competition solver.

## `UnPackNutrientAquisitionBCs` — Updated Signature at e027a40

The unpack routine signature changed from 2 args to 4 args. The two new arguments carry HLM nutrient supplementation flags that control the new L2FR PID gate (see [CNP Allocation](./cnp_allocation.md)):

```fortran
! FatesSoilBGCFluxMod.F90:105
subroutine UnPackNutrientAquisitionBCs(sites, bc_in, nitr_suppl, phos_suppl)
   type(ed_site_type), intent(inout) :: sites(:)
   type(bc_in_type),   intent(in)    :: bc_in(:)
   logical,            intent(in)    :: nitr_suppl   ! Is the HLM supplementing nitrogen?
   logical,            intent(in)    :: phos_suppl   ! Is the HLM supplementing phosphorus?
```

Inside the routine, the two logical inputs are written to module-level flags imported from `FatesInterfaceTypesMod`:

```fortran
! FatesSoilBGCFluxMod.F90:140-150
if(nitr_suppl) then
   hlm_nitrogen_suppl = itrue
else
   hlm_nitrogen_suppl = ifalse
end if

if(phos_suppl) then
   hlm_phosphorus_suppl = itrue
else
   hlm_phosphorus_suppl = ifalse
end if
```

`hlm_nitrogen_suppl` and `hlm_phosphorus_suppl` then feed the L2FR PID gate at `PRTAllometricCNPMod.F90:1909-1915` (intent shown below; see source-level note):

```fortran
limiting_p = ((p_uptake_mode .eq. coupled_p_uptake) .and. (hlm_phosphorus_suppl .eq. ifalse))
limiting_n = ((n_uptake_mode .eq. coupled_n_uptake) .and. (hlm_nitrogen_suppl .eq. ifalse))

if (limiting_p .or. limiting_n) then
   call this%CNPAdjustFRootTargets(target_c,target_dcdd)
end if
```

When the host model supplements either nutrient (e.g. supplemental-N spinup, or `add_temperature` style supplementation), the corresponding `hlm_*_suppl` flag is set true on the calling side. The PID controller is then disabled for that nutrient. If both are supplemented or both are in prescribed mode, the PID is disabled entirely and `l2fr` is frozen at its current value.

**Source-level note** (functionally inert today, fragile): the actual source at `PRTAllometricCNPMod.F90:1911` reads `limiting_n = ((n_uptake_mode .eq. coupled_p_uptake) .and. ...)`, comparing `n_uptake_mode` against `coupled_p_uptake` instead of `coupled_n_uptake`. Both constants are defined as integer `2` in `FatesConstantsMod.F90:114, 119`, so the gate evaluates correctly today, but the intent is `coupled_n_uptake`. The block above shows the corrected intent for clarity.

After setting the suppl flags, the routine performs three more things for each cohort:

1. **Early return if carbon-only.** `select case (hlm_parteh_mode); case (prt_carbon_allom_hyp) ... return; end select` at lines 154-164. Zeros the host uptake arrays first.
2. **Compute per-cohort demand and uptake** under the N uptake mode. Dispatches on `n_uptake_mode` at lines 174-211 (prescribed branch vs coupled branch). Repeats for P under `p_uptake_mode` at lines 213-246.
3. **Zero the host-side flux arrays** at lines 249-251. The host integrates uptake over many short timesteps then daily arrays are zeroed here to start the next daily accumulation.

```fortran
! after step 3, the ed_integrate_state_variables loop will do:
currentCohort%daily_n_gain = currentCohort%daily_nh4_uptake + &
                             currentCohort%daily_no3_uptake + &
                             currentCohort%sym_nfix_daily
```

at `EDMainMod.F90:583-584`. Note that `daily_n_gain` is a **sum** that explicitly includes symbiotic N fixation alongside NH4 and NO3 uptake. This is the value that arrives at the CNP allocation routine via `bc_inout(acnp_bc_inout_id_netdn)`.

For P, `ccohort%daily_p_gain` is registered directly to `bc_inout(acnp_bc_inout_id_netdp)` in `FatesCohortMod.F90:914`; there is no extra summation step (no analogous P-fixation term).

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:105-255)`, `(main/EDMainMod.F90:583-584)`, `(biogeochem/FatesCohortMod.F90:913-914)`

## Uptake Modes (Prescribed vs Coupled)

Two orthogonal flags live in `EDParamsMod`:

- `n_uptake_mode in {prescribed_n_uptake, coupled_n_uptake}` (constants 1 and 2)
- `p_uptake_mode in {prescribed_p_uptake, coupled_p_uptake}` (constants 1 and 2)

The integer constants are defined in `FatesConstantsMod.F90:113-119`.

**Default at e027a40 is COUPLED.** The JSON parameter file ships with `fates_cnp_prescribed_nuptake = fates_cnp_prescribed_puptake = 0.0` (default for all 14 PFTs). Their `long_name` annotations explicitly read "0fully coupled simulation, >0prescribed (experimental)". This **inverts** the e85d997-era guidance: at e85d997 the default was `1.0` (prescribed) and coupled was the deliberate opt-in; at e027a40 the default is `0.0` (coupled) and prescribed is the experimental opt-in.

### Prescribed Uptake (experimental opt-in)

Under prescribed mode, plants receive a fixed fraction of their demand independent of the host's soil BGC. FATES computes uptake itself inside `UnPackNutrientAquisitionBCs`:

```fortran
! FatesSoilBGCFluxMod.F90:184-185 (N branch)
daily_nh4_uptake = fnrt_c * vmax_nh4(pft) * prescribed_nuptake(pft) * sec_per_day
daily_no3_uptake = fnrt_c * vmax_no3(pft) * prescribed_nuptake(pft) * sec_per_day

! FatesSoilBGCFluxMod.F90:220-221 (P branch)
daily_p_demand = fnrt_c * vmax_p(pft) * sec_per_day
daily_p_gain   = fnrt_c * vmax_p(pft) * sec_per_day * prescribed_nuptake(pft)
```

Note the **persistent source-level oddity**: the P prescribed-uptake branch multiplies by `EDPftvarcon_inst%prescribed_nuptake(pft)`, not `prescribed_puptake(pft)`. `prescribed_puptake` is declared in `EDPftvarcon` but is **not consumed** anywhere in `UnPackNutrientAquisitionBCs`. A calibrator adjusting P uptake under prescribed mode must touch `prescribed_nuptake` or modify source. This is likely a long-standing oversight, not a documentation issue.

Under prescribed mode, `DailyPRTAllometricCNP` also overrides `n_gain` and `p_gain` to `1.e3 kg` inside the routine (`PRTAllometricCNPMod.F90:471-479`), effectively treating nutrients as unlimited, then reports back "how much was used" by the difference `n_gain0 - n_gain` at `PRTAllometricCNPMod.F90:692-701`. This is the prescribed-mode accounting loop.

### Coupled Uptake (default at e027a40)

Under coupled mode, the host soil BGC explicitly solves for nutrient uptake based on soil availability, root distribution, and competition with microbes. FATES hands over `bc_out%veg_rootc(icomp, layer)`, `bc_out%decompmicc(layer)` (ECA only), `bc_out%cn_scalar`, `bc_out%cp_scalar`, and `bc_out%num_plant_comps`, then reads back `bc_in%plant_nh4_uptake_flux`, `bc_in%plant_no3_uptake_flux`, `bc_in%plant_p_uptake_flux` (all in g/m^2/day), and distributes them to cohorts:

```fortran
! FatesSoilBGCFluxMod.F90:204-205 (N branch)
ccohort%daily_nh4_uptake = bc_in(s)%plant_nh4_uptake_flux(icomp,1) * kg_per_g * AREA / ccohort%n
ccohort%daily_no3_uptake = bc_in(s)%plant_no3_uptake_flux(icomp,1) * kg_per_g * AREA / ccohort%n

! FatesSoilBGCFluxMod.F90:239 (P branch)
ccohort%daily_p_gain = bc_in(s)%plant_p_uptake_flux(icomp,1) * kg_per_g * AREA / ccohort%n
```

where `AREA = 10000 m^2` is the FATES site area constant and `ccohort%n` is the cohort density (plants). The unit conversion `g/m^2/day * kg/g * m^2/plant -> kg/plant/day` turns the host's areal flux into a per-plant daily mass.

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:105-255)`

## Competition Mechanism: Two Independent Axes

Two orthogonal axes control how FATES cooperates with the host soil BGC. Conflating them is a common source of confusion.

### Axis 1: Decomposer Math (`hlm_nu_com`)

A string flag set by the host model to `"RD"` (Relative Demand) or `"ECA"` (Equilibrium Chemistry Approximation). This decides what **host-side math** consumes FATES' boundary condition output.

| Method | How it partitions nutrients | Required extra FATES BCs |
|---|---|---|
| `RD` | Nutrients divided among plants proportionally to demand | None beyond `veg_rootc`, `num_plant_comps`, `ft_index` |
| `ECA` | Root-microbe equilibrium with explicit decomposer biomass | Also requires `decompmicc`, `cn_scalar`, `cp_scalar` (initialized to 1.0) |

Under ECA, FATES estimates decomposer biomass per soil layer using a depth-attenuation function:

```fortran
! FatesSoilBGCFluxMod.F90:504-515
decompmicc_layer = EDPftvarcon_inst%decompmicc(pft) &
                   * exp(-decompmicc_lambda * abs(z_soil(j) - decompmicc_zmax))

bc_out%decompmicc(id) = bc_out%decompmicc(id) + decompmicc_layer * veg_rootc
! After the cohort loop:
bc_out%decompmicc(id) = bc_out%decompmicc(id) / max(nearzero, sum(veg_rootc(:, id)))
```

with `decompmicc_lambda = 2.5` and `decompmicc_zmax = 0.07 m` (parameters at lines 448-449). The final per-layer value is the root-biomass-weighted average of the PFT-specific `decompmicc(pft)` parameter.

**Parameter rename at e027a40**: the JSON parameter name moved from `fates_cnp_decompmicc` (e85d997) to `fates_cnp_eca_decompmicc` (e027a40). The Fortran field `EDPftvarcon_inst%decompmicc(pft)` is unchanged. The reader at `EDPftvarcon.F90:649` looks up the new JSON key. Calibration tables that key on the old name will silently fail to find the parameter at e027a40.

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:456-540)`, `(main/EDPftvarcon.F90:649)`

### Axis 2: Competitor Count (`fates_np_comp_scaling`)

An integer flag defined in `FatesConstantsMod.F90:113-148`:

```fortran
integer, public, parameter :: coupled_np_comp_scaling = 1   ! one competitor per cohort
integer, public, parameter :: trivial_np_comp_scaling = 2   ! one competitor total
integer, public            :: fates_np_comp_scaling = fates_unset_int
```

This decides **how many rows FATES writes into `bc_out%veg_rootc`**, i.e. how many "plants" the host sees.

| Value | What FATES writes |
|---|---|
| `trivial_np_comp_scaling` | `num_plant_comps = 1`, all cohorts pooled. Under RD this triggers a fast-path return at lines 462-468 after just setting `num_plant_comps = 1` and `ft_index(1) = 1`. Under ECA, FATES still runs the full loop to build `veg_rootc` and `decompmicc` arrays because ECA needs them. |
| `coupled_np_comp_scaling` | `num_plant_comps = cohort_count`, `icomp` is incremented per cohort (lines 481-485). Host sees every cohort as a separate competitor. |

`hlm_nu_com` (Axis 1) and `fates_np_comp_scaling` (Axis 2) are **independent**. All four combinations are valid.

```fortran
! FatesSoilBGCFluxMod.F90:462-468 (the RD+trivial shortcut)
if (fates_np_comp_scaling == trivial_np_comp_scaling) then
   if (trim(hlm_nu_com) == 'RD') then
      bc_out%num_plant_comps = 1
      bc_out%ft_index(1)     = 1
      return
   end if
end if

! FatesSoilBGCFluxMod.F90:481-485 (competitor increment)
if (fates_np_comp_scaling .eq. coupled_np_comp_scaling) then
   icomp = icomp + 1
else
   icomp = 1
end if
```

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:462-540)`, `(main/FatesConstantsMod.F90:113-148)`

## Root Distribution and `veg_rootc`

Per-layer vegetation fine-root carbon, which both RD and ECA need:

```fortran
! FatesSoilBGCFluxMod.F90:490-502
call set_root_fraction(csite%rootfrac_scr, pft, csite%zi_soil, bc_in%max_rooting_depth_index_col)
fnrt_c = ccohort%prt%GetState(fnrt_organ, carbon12_element)

do j = 1, bc_in%nlevdecomp
   id = bc_in%decomp_id(j)  ! map soil layer -> decomp layer
   veg_rootc = fnrt_c * ccohort%n * rootfrac(j) * AREA_INV * g_per_kg / dz_soil(j)
   bc_out%veg_rootc(icomp, id) = bc_out%veg_rootc(icomp, id) + veg_rootc
end do
```

Units check: `fnrt_c [kgC/plant] * n [plants/ha] * rootfrac [-] * (1 ha / 10000 m^2) * (1000 g/kg) / dz [m] = gC/m^3`.

`set_root_fraction` (`FatesAllometryMod`) normalizes per-layer root fractions to the PFT's vertical rooting profile parameters and the host's max-rooting depth. The dispatch behind `set_root_fraction` selects from three rooting-profile shapes via `fates_allom_fnrt_prof_mode`: `exponential_1p_root_profile` (`biogeochem/FatesAllometryMod.F90:2839`), `jackson_beta_root_profile`, and `exponential_2p_root_profile` (`biogeochem/FatesAllometryMod.F90:2860`). The two-parameter exponential form (mode 3) is typical for arctic PFTs where steepness and depth scale differ; see [Allometry](../allometry.md) for parameter details.

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:490-515)`, `(biogeochem/FatesAllometryMod.F90:2839-2860)`

## Cohort-Level Nutrient State Variables

| Field | Units | Populated by | Consumed by |
|---|---|---|---|
| `ccohort%daily_n_demand` | kgN/plant/day | `UnPackNutrientAquisitionBCs` | Diagnostic |
| `ccohort%daily_nh4_uptake` | kgN/plant/day | `UnPackNutrientAquisitionBCs` | `daily_n_gain` sum |
| `ccohort%daily_no3_uptake` | kgN/plant/day | `UnPackNutrientAquisitionBCs` | `daily_n_gain` sum |
| `ccohort%sym_nfix_daily` | kgN/plant/day | `EDAccumulateFluxesMod.F90:85` (sums per-tstep contributions from `RootLayerNFixation`) | `daily_n_gain` sum |
| `ccohort%daily_n_gain` | kgN/plant/day | `EDMainMod.F90:583-584` (sum of above three) | CNP `bc_inout(netdn)` |
| `ccohort%daily_p_demand` | kgP/plant/day | `UnPackNutrientAquisitionBCs` | Diagnostic |
| `ccohort%daily_p_gain` | kgP/plant/day | `UnPackNutrientAquisitionBCs` | CNP `bc_inout(netdp)` directly (no summing step) |

Note carefully: `daily_n_gain` includes fixation; `daily_p_gain` does not have an analogous P-fixation term. P bypasses the EDMainMod summing step because it has no fixation source — `daily_p_gain` is registered directly to the inout BC in `FatesCohortMod.F90:914`.

Sources: `(main/EDMainMod.F90:583-584)`, `(biogeochem/FatesCohortMod.F90:913-914)`, `(biogeophys/FatesPlantRespPhotosynthMod.F90:1154-1206)`, `(biogeophys/EDAccumulateFluxesMod.F90:85)`

## Efflux Back to Soil

Excess nutrient or carbon that PARTEH cannot allocate is sent back to the soil as exudation, via `EffluxIntoLitterPools` (`FatesSoilBGCFluxMod.F90:544+`). Per-cohort efflux pointers are:

```fortran
ccohort%daily_c_efflux  ! (element = carbon12)
ccohort%daily_n_efflux  ! (element = nitrogen)
ccohort%daily_p_efflux  ! (element = phosphorus)
```

The effluxed mass is added to the labile fraction of the patch's root-fine fragment pool, distributed vertically by `rootfrac_scr`:

```fortran
litt%root_fines_frag(ilabile, j) += efflux_ptr * ccohort%n * AREA_INV * rootfrac_scr(j)   ! kg/m^2/day
```

Under prescribed uptake mode, N and P efflux are forced to zero at the end of `CNPAllocateRemainder` (see `PRTAllometricCNPMod.F90:1993-2005`) because in that mode the "remaining gain" is reinterpreted as "amount actually used", not as excess.

The `store_c_overflow` compile-time flag in `PRTAllometricCNPMod` (hard-coded to `burn_c_store_overflow` at line 223) also determines whether excess carbon is sent to efflux (`exude_c_store_overflow`) or routed to respiration (`burn_c_store_overflow`, the default).

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:544+)`, `(parteh/PRTAllometricCNPMod.F90:1923-2008)`

## Key Parameters

| JSON parameter | Role | Fortran field |
|---|---|---|
| `fates_cnp_vmax_nh4` | Max NH4+ uptake per fine-root C [kgN/kgC/s] | `EDPftvarcon_inst%vmax_nh4(pft)` |
| `fates_cnp_vmax_no3` | Max NO3- uptake per fine-root C [kgN/kgC/s] | `EDPftvarcon_inst%vmax_no3(pft)` |
| `fates_cnp_vmax_p` | Max P uptake per fine-root C [kgP/kgC/s] | `EDPftvarcon_inst%vmax_p(pft)` |
| `fates_cnp_prescribed_nuptake` | Fraction of max uptake realized under prescribed mode (also used for P, see source oddity above). **Default 0.0 at e027a40** = coupled mode. | `EDPftvarcon_inst%prescribed_nuptake(pft)` |
| `fates_cnp_prescribed_puptake` | **Declared but unused** in `UnPackNutrientAquisitionBCs`. Default 0.0. | `EDPftvarcon_inst%prescribed_puptake(pft)` |
| `fates_cnp_eca_decompmicc` (renamed from `fates_cnp_decompmicc` at e85d997, ECA only) | PFT-specific maximum decomposer biomass, input to depth-attenuation estimator. Default 280.0 gC/m^3. | `EDPftvarcon_inst%decompmicc(pft)` |
| `fates_cnp_eca_km_nh4` (NEW) | Half-saturation for plant NH4 uptake (ECA) [gN/m^3]. Default 0.14. | `EDPftvarcon_inst%eca_km_nh4(pft)` |
| `fates_cnp_eca_km_no3` (NEW) | Half-saturation for plant NO3 uptake (ECA) [gN/m^3]. Default 0.27. | `EDPftvarcon_inst%eca_km_no3(pft)` |
| `fates_cnp_eca_km_p` (NEW) | Half-saturation for plant P uptake (ECA) [gP/m^3]. Default 0.1. | `EDPftvarcon_inst%eca_km_p(pft)` |
| `fates_cnp_eca_km_ptase` (NEW) | Half-saturation for biochemical P (ECA) [gP/m^3]. Default 1.0. | `EDPftvarcon_inst%eca_km_ptase(pft)` |
| `fates_cnp_eca_vmax_ptase` (NEW) | Maximum production rate for biochemical P (ECA) [gP/m^2/s]. Default 5e-09. | `EDPftvarcon_inst%eca_vmax_ptase(pft)` |
| `fates_cnp_eca_alpha_ptase` (NEW, INACTIVE — KEEP AT 0) | (validation aborts if non-zero, `EDPftvarcon.F90:1044`) | `EDPftvarcon_inst%eca_alpha_ptase(pft)` |
| `fates_cnp_eca_lambda_ptase` (NEW, INACTIVE — KEEP AT 0) | (validation aborts if non-zero, `EDPftvarcon.F90:1038`) | `EDPftvarcon_inst%eca_lambda_ptase(pft)` |
| `fates_cnp_eca_plant_escalar` (NEW, scalar) | Plant fine-root biomass scaling for nutrient carrier enzymes (ECA). Default 1.25e-05. | (scalar in JSON, `fates_params_default.json:1685`) |
| `fates_cnp_nfix1` | Scale factor on fine-root maintenance respiration used to compute sym N fix | `prt_params%nfix_mresp_scfrac(ft)` |

Sources: `(main/EDPftvarcon.F90:649-691)`, `(biogeochem/FatesSoilBGCFluxMod.F90:174-246,490-515)`, `(parameter_files/fates_params_default.json:397-549,1685)`

## Summary

The soil-plant nutrient interface is driven by two files: `FatesSoilBGCFluxMod.F90` (host-side boundary condition packing/unpacking) and `PRTAllometricCNPMod.F90` (consumer). Two independent switches control how the interface operates: `hlm_nu_com` selects the host-side nutrient partitioning math (RD vs ECA), and `fates_np_comp_scaling` selects whether FATES reports one pooled competitor or one competitor per cohort. These are orthogonal. Uptake itself is further split by `n_uptake_mode` and `p_uptake_mode` between prescribed (FATES computes `fnrt_c * vmax * prescribed_nuptake`) and coupled (FATES reads the host's `plant_*_uptake_flux` arrays). At e027a40, **coupled is the default** because the JSON `fates_cnp_prescribed_nuptake/puptake` defaults are now `0.0`; prescribed mode is an experimental opt-in.

**The key new behavior at e027a40** is the unpack signature `UnPackNutrientAquisitionBCs(sites, bc_in, nitr_suppl, phos_suppl)`. Two new logical inputs from the host are written to the global flags `hlm_nitrogen_suppl` and `hlm_phosphorus_suppl`. These flags then gate the L2FR PID controller call site at `PRTAllometricCNPMod.F90:1909-1915`. Under HLM nutrient supplementation (e.g. supplemental-N spinup), the corresponding side of the PID is silently disabled and `l2fr` is frozen.

When `DailyPRTAllometricCNP` reads `bc_inout(acnp_bc_inout_id_netdn)`, it is reading `ccohort%daily_n_gain`, which is `daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily`. Symbiotic fixation is included in the same pool as soil uptake. The CNP routine does not distinguish the sources.

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:105-540)`, `(parteh/PRTAllometricCNPMod.F90:434-711,1909-1915)`, `(main/EDMainMod.F90:560-634)`
