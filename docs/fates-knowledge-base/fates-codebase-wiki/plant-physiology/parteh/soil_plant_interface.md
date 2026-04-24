# Soil-Plant Nutrient Interface

---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

**Relevant source files:**
- `biogeochem/FatesSoilBGCFluxMod.F90`
- `biogeochem/FatesCohortMod.F90`
- `main/EDMainMod.F90`
- `main/FatesConstantsMod.F90`
- `main/EDPftvarcon.F90`
- `biogeophys/FatesPlantRespPhotosynthMod.F90`
- `parteh/PRTAllometricCNPMod.F90`

## Purpose and Scope

This document describes how FATES plants exchange nitrogen and phosphorus with the host land model's soil biogeochemistry. The interface is active only under the CNP allocation hypothesis (`prt_cnp_flex_allom_hyp`). Under the carbon-only hypothesis, `UnPackNutrientAquisitionBCs` exits immediately after zeroing the host's plant-uptake flux arrays.

The interface covers:

- Computing per-cohort nutrient demand (from fine-root biomass and PFT `vmax_*` parameters)
- Choosing competition/uptake mode (prescribed vs. coupled)
- Packing vegetation state into boundary conditions for the host BGC (`PrepNutrientAquisitionBCs`)
- Unpacking actual uptake fluxes back into cohort state (`UnPackNutrientAquisitionBCs`)
- Returning plant efflux/exudation into the litter pool (`EffluxIntoLitterPools`)

For the downstream allocation consumer see [CNP Allocation and Nutrient Dynamics](./cnp_allocation.md). For framework-level context see [PARTEH: Plant Allocation System](./index.md).

## Daily Pipeline

Within the daily loop, the soil-plant exchange runs in this order:

```
1. PrepNutrientAquisitionBCs(csite, bc_in, bc_out)      [FatesSoilBGCFluxMod.F90:401-518]
     └── writes vegetation state (veg_rootc, decompmicc, num_plant_comps, ft_index) to bc_out
2. Host BGC runs (e.g. CLM5/ELM CN) — reads bc_out, solves nutrient competition,
   fills bc_in%plant_nh4_uptake_flux, bc_in%plant_no3_uptake_flux, bc_in%plant_p_uptake_flux
3. UnPackNutrientAquisitionBCs(sites, bc_in)            [FatesSoilBGCFluxMod.F90:102-235]
     └── reads bc_in, fills ccohort%daily_nh4_uptake, daily_no3_uptake, daily_p_gain
     └── zeros the bc_in uptake arrays
4. currentCohort%daily_n_gain = daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily   [EDMainMod.F90:550-551]
5. DailyPRT(phase=1) — CNP allocation reads daily_n_gain via bc_inout index 4 (netdn)
```

The N fixation term `sym_nfix_daily` is populated earlier by `FatesPlantRespPhotosynthMod::RootLayerNFixation`, so by step 4 it has already accumulated from the photosynthesis/respiration timestep.

Sources: `(main/EDMainMod.F90:530-615)`, `(biogeochem/FatesSoilBGCFluxMod.F90:102-518)`, `(biogeophys/FatesPlantRespPhotosynthMod.F90:800,965-1017)`

## Demand Calculation

Every cohort's nutrient demand is proportional to its fine-root carbon biomass:

```fortran
! FatesSoilBGCFluxMod.F90:162-164, 182-184, 201
fnrt_c = ccohort%prt%GetState(fnrt_organ, carbon12_element)
daily_n_demand = fnrt_c * (vmax_nh4(pft) + vmax_no3(pft)) * sec_per_day       ! kgN/plant/day
daily_p_demand = fnrt_c * vmax_p(pft) * sec_per_day                           ! kgP/plant/day
```

`vmax_*` parameters have units of kg-nutrient / kg-fineroot-C / second. Computed demand represents the theoretical maximum uptake if the soil supply is unlimited. It is not directly used by the allocation routine; instead, it controls the cohort's share under prescribed mode and informs the ECA competition solver.

## Uptake Modes (Prescribed vs Coupled)

Two orthogonal flags live in `EDParamsMod`:

- `n_uptake_mode ∈ {prescribed_n_uptake, coupled_n_uptake}`
- `p_uptake_mode ∈ {prescribed_p_uptake, coupled_p_uptake}`

The values are the integer constants from `FatesConstantsMod.F90:94-95`.

### Prescribed Uptake

Under prescribed mode, plants receive a fixed fraction of their demand independent of the host's soil BGC. FATES computes uptake itself inside `UnPackNutrientAquisitionBCs`:

```fortran
! FatesSoilBGCFluxMod.F90:165-166 (N branch)
daily_nh4_uptake = fnrt_c * vmax_nh4(pft) * prescribed_nuptake(pft) * sec_per_day
daily_no3_uptake = fnrt_c * vmax_no3(pft) * prescribed_nuptake(pft) * sec_per_day

! FatesSoilBGCFluxMod.F90:201-202 (P branch)
daily_p_demand = fnrt_c * vmax_p(pft) * sec_per_day
daily_p_gain   = fnrt_c * vmax_p(pft) * sec_per_day * prescribed_nuptake(pft)
```

Note the **source-level oddity**: the P prescribed-uptake branch multiplies by `EDPftvarcon_inst%prescribed_nuptake(pft)`, not `prescribed_puptake(pft)`. `prescribed_puptake` is declared in `EDPftvarcon` but is **not consumed** anywhere in `UnPackNutrientAquisitionBCs`. A calibrator adjusting P uptake under prescribed mode must touch `prescribed_nuptake` or modify source. This is likely an oversight in the source and not a documentation issue.

Under prescribed mode, `DailyPRTAllometricCNP` also overrides `n_gain` and `p_gain` to 1e3 kg inside the routine (`PRTAllometricCNPMod.F90:470-475`), effectively treating nutrients as unlimited, then reports back "how much was used" by the difference `n_gain0 - n_gain` at `PRTAllometricCNPMod.F90:688-697`. This is the prescribed-mode accounting loop.

### Coupled Uptake

Under coupled mode, the host soil BGC explicitly solves for nutrient uptake based on soil availability, root distribution, and competition with microbes. FATES hands over `bc_out%veg_rootc(icomp, layer)`, `bc_out%decompmicc(layer)` (ECA only), `bc_out%cn_scalar`, `bc_out%cp_scalar`, and `bc_out%num_plant_comps`, then reads back `bc_in%plant_nh4_uptake_flux`, `bc_in%plant_no3_uptake_flux`, `bc_in%plant_p_uptake_flux` (all in g/m²/day), and distributes them to cohorts:

```fortran
! FatesSoilBGCFluxMod.F90:182-186 (N branch)
ccohort%daily_nh4_uptake = bc_in%plant_nh4_uptake_flux(icomp, 1) * kg_per_g * AREA / ccohort%n
ccohort%daily_no3_uptake = bc_in%plant_no3_uptake_flux(icomp, 1) * kg_per_g * AREA / ccohort%n
```

where `AREA = 10000 m²` is the FATES site area constant and `ccohort%n` is the cohort density (plants). The unit conversion `g/m²/day * kg/g * m²/plant → kg/plant/day` turns the host's areal flux into a per-plant daily mass.

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:102-235)`

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
! FatesSoilBGCFluxMod.F90:482-492
decompmicc_layer = EDPftvarcon_inst%decompmicc(pft) &
                   * exp(-decompmicc_lambda * abs(z_soil(j) - decompmicc_zmax))

bc_out%decompmicc(id) = bc_out%decompmicc(id) + decompmicc_layer * veg_rootc
! After the cohort loop:
bc_out%decompmicc(id) = bc_out%decompmicc(id) / max(nearzero, sum(veg_rootc(:, id)))
```

with `decompmicc_lambda = 2.5` and `decompmicc_zmax = 0.07 m`. The final per-layer value is the root-biomass-weighted average of the PFT-specific `decompmicc(pft)` parameter.

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:434-509)`

### Axis 2: Competitor Count (`fates_np_comp_scaling`)

An integer flag defined in `FatesConstantsMod.F90:94-125`:

```fortran
integer, public, parameter :: coupled_np_comp_scaling = 1   ! one competitor per cohort
integer, public, parameter :: trivial_np_comp_scaling = 2   ! one competitor total
integer, public          :: fates_np_comp_scaling = fates_unset_int
```

This decides **how many rows FATES writes into `bc_out%veg_rootc`**, i.e. how many "plants" the host sees.

| Value | What FATES writes |
|---|---|
| `trivial_np_comp_scaling` | `num_plant_comps = 1`, all cohorts pooled. Under RD this triggers a fast-path return at line 440-446 after just setting `num_plant_comps = 1` and `ft_index(1) = 1`. Under ECA, FATES still runs the full loop to build `veg_rootc` and `decompmicc` arrays because ECA needs them. |
| `coupled_np_comp_scaling` | `num_plant_comps = cohort_count`, `icomp` is incremented per cohort. Host sees every cohort as a separate competitor. |

`hlm_nu_com` (Axis 1) and `fates_np_comp_scaling` (Axis 2) are **independent**. All four combinations are valid. The old wiki labeled RD as always being "1 competitor" and ECA as always being "1 per cohort"; this is incorrect.

```fortran
! FatesSoilBGCFluxMod.F90:440-446 (the RD+trivial shortcut)
if (fates_np_comp_scaling == trivial_np_comp_scaling) then
   if (trim(hlm_nu_com) == 'RD') then
      bc_out%num_plant_comps = 1
      bc_out%ft_index(1)     = 1
      return
   end if
end if

! FatesSoilBGCFluxMod.F90:459-463 (competitor increment)
if (fates_np_comp_scaling == coupled_np_comp_scaling) then
   icomp = icomp + 1
else
   icomp = 1
end if
```

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:440-515)`, `(main/FatesConstantsMod.F90:94-125)`

## Root Distribution and `veg_rootc`

Per-layer vegetation fine-root carbon, which both RD and ECA need:

```fortran
! FatesSoilBGCFluxMod.F90:468-480
call set_root_fraction(csite%rootfrac_scr, pft, csite%zi_soil, bc_in%max_rooting_depth_index_col)
fnrt_c = ccohort%prt%GetState(fnrt_organ, carbon12_element)

do j = 1, bc_in%nlevdecomp
   id = bc_in%decomp_id(j)  ! map soil layer -> decomp layer
   veg_rootc = fnrt_c * ccohort%n * rootfrac(j) * AREA_INV * g_per_kg / dz_soil(j)
   bc_out%veg_rootc(icomp, id) = bc_out%veg_rootc(icomp, id) + veg_rootc
end do
```

Units check: `fnrt_c [kgC/plant] * n [plants/ha] * rootfrac [-] * (1 ha / 10000 m²) * (1000 g/kg) / dz [m] = gC/m³`.

`set_root_fraction` (`FatesAllometryMod`) normalizes per-layer root fractions to the PFT's vertical rooting profile parameters and the host's max-rooting depth.

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:468-496)`

## Unpack: `UnPackNutrientAquisitionBCs`

Called once per day before `DailyPRT`. Walks sites → patches → cohorts and performs four things for each cohort:

1. **Early return if carbon-only.** `select case (hlm_parteh_mode); case (prt_carbon_allom_hyp) ... return; end select` at lines 136-145. Zeros the host uptake arrays first.
2. **Compute per-cohort demand and uptake** under the N uptake mode. Dispatches on `n_uptake_mode` at lines 155-192 (prescribed branch vs. coupled branch). Repeats for P under `p_uptake_mode` at lines 194-226.
3. **Zero the host-side flux arrays** at lines 229-231. The host integrates uptake over many short timesteps then daily arrays are zeroed here to start the next daily accumulation.

```fortran
! after step 3, the ed_integrate_state_variables loop will do:
currentCohort%daily_n_gain = currentCohort%daily_nh4_uptake + &
                             currentCohort%daily_no3_uptake + &
                             currentCohort%sym_nfix_daily
```

at `EDMainMod.F90:550-551` — note that `daily_n_gain` is a **sum** that explicitly includes symbiotic N fixation alongside NH4 and NO3 uptake. This is the value that arrives at the CNP allocation routine via `bc_inout(acnp_bc_inout_id_netdn)`.

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:102-235)`, `(main/EDMainMod.F90:550-551)`, `(biogeochem/FatesCohortMod.F90)` (BC registration)

## Cohort-Level Nutrient State Variables

| Field | Units | Populated by | Consumed by |
|---|---|---|---|
| `ccohort%daily_n_demand` | kgN/plant/day | `UnPackNutrientAquisitionBCs` | Diagnostic |
| `ccohort%daily_nh4_uptake` | kgN/plant/day | `UnPackNutrientAquisitionBCs` | `daily_n_gain` sum |
| `ccohort%daily_no3_uptake` | kgN/plant/day | `UnPackNutrientAquisitionBCs` | `daily_n_gain` sum |
| `ccohort%sym_nfix_daily` | kgN/plant/day | `FatesPlantRespPhotosynthMod::RootLayerNFixation` | `daily_n_gain` sum |
| `ccohort%daily_n_gain` | kgN/plant/day | `EDMainMod.F90:550-551` (sum of above three) | CNP `bc_inout(netdn)` |
| `ccohort%daily_p_demand` | kgP/plant/day | `UnPackNutrientAquisitionBCs` | Diagnostic |
| `ccohort%daily_p_gain` | kgP/plant/day | `UnPackNutrientAquisitionBCs` | CNP `bc_inout(netdp)` |

Note carefully: `daily_n_gain` includes fixation; `daily_p_gain` does not have an analogous P-fixation term.

Sources: `(main/EDMainMod.F90:550-551,757)`, `(biogeochem/FatesCohortMod.F90)` (BC registration), `(biogeophys/FatesPlantRespPhotosynthMod.F90:965-1017)`

## Efflux Back to Soil

Excess nutrient or carbon that PARTEH cannot allocate is sent back to the soil as exudation, via `EffluxIntoLitterPools` (`FatesSoilBGCFluxMod.F90:522-582`). Per-cohort efflux pointers are:

```fortran
ccohort%daily_c_efflux  ! (element = carbon12)
ccohort%daily_n_efflux  ! (element = nitrogen)
ccohort%daily_p_efflux  ! (element = phosphorus)
```

The effluxed mass is added to the labile fraction of the patch's root-fine fragment pool, distributed vertically by `rootfrac_scr`:

```fortran
litt%root_fines_frag(ilabile, j) += efflux_ptr * ccohort%n * AREA_INV * rootfrac_scr(j)   ! kg/m²/day
```

Under prescribed uptake mode, N and P efflux are forced to zero at the end of `CNPAllocateRemainder` (see `PRTAllometricCNPMod.F90:1990-2005`) because in that mode the "remaining gain" is reinterpreted as "amount actually used", not as excess.

The `store_c_overflow` compile-time flag in `PRTAllometricCNPMod` (hard-coded to `burn_c_store_overflow`) also determines whether excess carbon is sent to efflux (`exude_c_store_overflow`) or routed to respiration (`burn_c_store_overflow`, the default).

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:522-582)`, `(parteh/PRTAllometricCNPMod.F90:1920-2005)`

## Key Parameters

| Parameter | Role | Fortran field |
|---|---|---|
| `fates_cnp_vmax_nh4` | Max NH4+ uptake per fine-root C [kgN/kgC/s] | `EDPftvarcon_inst%vmax_nh4(pft)` |
| `fates_cnp_vmax_no3` | Max NO3- uptake per fine-root C [kgN/kgC/s] | `EDPftvarcon_inst%vmax_no3(pft)` |
| `fates_cnp_vmax_p` | Max P uptake per fine-root C [kgP/kgC/s] | `EDPftvarcon_inst%vmax_p(pft)` |
| `fates_cnp_prescribed_nuptake` | Fraction of max uptake realized under prescribed mode (also used for P, see source oddity above) | `EDPftvarcon_inst%prescribed_nuptake(pft)` |
| `fates_cnp_prescribed_puptake` | **Declared but unused** in `UnPackNutrientAquisitionBCs` | `EDPftvarcon_inst%prescribed_puptake(pft)` |
| `fates_cnp_decompmicc` (ECA only) | PFT-specific maximum decomposer biomass, input to depth-attenuation estimator | `EDPftvarcon_inst%decompmicc(pft)` |
| `fates_cnp_nfix1` | Scale factor on fine-root maintenance respiration used to compute sym N fix | `prt_params%nfix_mresp_scfrac(ft)` |

Sources: `(main/EDPftvarcon.F90)`, `(biogeochem/FatesSoilBGCFluxMod.F90:155-225,482-492)`

## Summary

The soil-plant nutrient interface is driven by two files: `FatesSoilBGCFluxMod.F90` (host-side boundary condition packing/unpacking) and `PRTAllometricCNPMod.F90` (consumer). Two independent switches control how the interface operates: `hlm_nu_com` selects the host-side nutrient partitioning math (RD vs ECA), and `fates_np_comp_scaling` selects whether FATES reports one pooled competitor or one competitor per cohort. These are orthogonal. Uptake itself is further split by `n_uptake_mode` and `p_uptake_mode` between prescribed (FATES computes `fnrt_c * vmax * prescribed_nuptake`) and coupled (FATES reads the host's `plant_*_uptake_flux` arrays).

When `DailyPRTAllometricCNP` reads `bc_inout(acnp_bc_inout_id_netdn)`, it is reading `ccohort%daily_n_gain`, which is `daily_nh4_uptake + daily_no3_uptake + sym_nfix_daily` — symbiotic fixation is included in the same pool as soil uptake. The CNP routine does not distinguish the sources.

Sources: `(biogeochem/FatesSoilBGCFluxMod.F90:1-600)`, `(parteh/PRTAllometricCNPMod.F90:430-707)`, `(main/EDMainMod.F90:530-615)`
