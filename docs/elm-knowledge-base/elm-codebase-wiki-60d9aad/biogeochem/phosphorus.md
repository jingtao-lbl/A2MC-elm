---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Phosphorus Dynamics

Phosphorus is an ELM-specific extension (Yang et al. 2014 / 2016) over the CESM/CLM ancestor. The N-P coupled path runs when ELM is compiled with the CNP option enabled. At the vegetation level, P flows through the same three-state tissue structure as N (display + storage + xfer pools), and the plant P balance is closed by the three staged updaters `biogeochem/PhosphorusStateUpdate1Mod.F90`, `PhosphorusStateUpdate2Mod.F90`, `PhosphorusStateUpdate3Mod.F90`. At the soil level, P has a four-reservoir inorganic cascade (solution / labile / secondary mineral / occluded) plus a primary-mineral weathering source, implemented in `biogeochem/PhosphorusDynamicsMod.F90`. This page documents the ELM-specific soil P cascade and the staged P state updates. The derived types `phosphorusstate_type` and `phosphorusflux_type` are described in `cnp_state_and_fluxes.md`.

## Conceptual Overview of the Inorganic P Cascade

The soil P cycle has a structure fundamentally different from soil N:

- P has no atmospheric redox transformations analogous to nitrification/denitrification. There is no gaseous loss pathway for P.
- P availability is instead controlled by sorption/desorption equilibria between soil solution P (`solutionp`), exchangeable adsorbed "labile" P (`labilep`), strongly adsorbed/precipitated "secondary mineral" P (`secondp`), and chemically "occluded" P (`occlp`) that is essentially unavailable.
- Fresh P enters the system from weathering of primary minerals (`primp`, the parent-material P such as apatite or feldspar) and atmospheric deposition (dust). Phosphatase-mediated biochemical mineralization of organic P is an additional source path that plants and microbes can upregulate under P limitation.
- P is lost from the active pool via leaching (solution P moving with drainage), soil erosion, fire, and occlusion.

ELM implements this as a vertically resolved column-level cascade:

```
     deposition              weathering
         |                        |
         v                        v
    +----------+            +-----------+
    | solution |<---------->|  primary  |
    |    P     |            |  mineral  |
    +----+-----+            +-----------+
         |  ^
 leaching|  | desorption
         |  |
         v  |
    +----+-----+  occlusion +----------+
    | labile P | ---------->| occluded |
    +----+-----+            +----------+
         |  ^
adsorption|  |
         v  |
    +----+-----+
    | secondary|
    |  mineral |
    +----------+
         |
 occlusion v
    +----------+
    | occluded |
    +----------+
```

ELM stores each pool per decomposition layer (`nlevdecomp_full`) in the `phosphorusstate_type`:

| Pool | Vertically resolved field | Col total |
|---|---|---|
| Solution P | `solutionp_vr_col` | `solutionp_col` |
| Labile P | `labilep_vr_col` | `labilep_col` |
| Secondary mineral P | `secondp_vr_col` | `secondp_col` |
| Occluded P | `occlp_vr_col` | `occlp_col` |
| Primary mineral P | `primp_vr_col` | - |

A summary "total mineral P" field `sminp_vr_col`, `sminp_col` is also computed (sum of active forms). The truncation sink is `ptrunc_vr_col`, `ptrunc_col`.

## PhosphorusDynamicsMod

`biogeochem/PhosphorusDynamicsMod.F90` (846 lines) implements the inorganic cycle. Public entries:

- `PhosphorusDeposition` (`:52`): copy gridcell `forc_pdep_grc` into `col_pf%pdep_to_sminp`.
- `PhosphorusWeathering` (`:87`): release P from `primp_vr` to `labilep_vr` at a soil-order-dependent rate `r_weather(isoilorder)`. The rate is stored as a monthly fraction and converted to the decomposition time step via `dtd = dt / (30 * secspday)` with the log-transformation `r = 1 - exp(-rr*dtd)` where `rr = -log(1 - r_monthly)`.
- `PhosphorusAdsportion` (`:143`): move labile P to secondary mineral P at rate `r_adsorp(isoilorder)`.
- `PhosphorusDesoprtion` (`:207`): move secondary mineral P back to labile P at rate `r_desorp(isoilorder)`.
- `PhosphorusOcclusion` (`:271`): move secondary mineral P to occluded P at rate `r_occlude(isoilorder)`.
- `PhosphorusLeaching` (`:336`): compute loss of solution P to drainage (same water-based approach as N leaching).
- `PhosphorusBiochemMin` (`:450`): phosphatase-mediated biochemical mineralization of organic P, releasing P from decomposing organic pools into the mineral N (`sminp`) pool.
- `PhosphorusBiochemMin_balance`: alternative "balance" version used when `nu_com_phosphatase = .true.`, which computes phosphatase activity from an explicit cost-benefit analysis.
- `PhosphorusFert`: crop P fertilization (adds to `sminp`).

### Soil-order parameters

The per-soil-order rates `r_weather`, `r_adsorp`, `r_desorp`, `r_occlude` are defined in `main/soilorder_varcon.F90` and indexed by a per-column soil order integer `cnstate_vars%isoilorder`. These rates have units of monthly fraction and are converted to per-time-step fluxes using the log transformation inside each routine. The soil order map comes from the surface dataset, typically with values 1 through 12 for the USDA soil orders (Entisol, Inceptisol, Andisol, Mollisol, Alfisol, Ultisol, Oxisol, Vertisol, Histosol, Aridisol, Spodosol, Gelisol).

Additional soil-order parameters for biochemical mineralization are in `soilorder_varcon`: `k_s1_biochem`, `k_s2_biochem`, `k_s3_biochem`, `k_s4_biochem` (monthly phosphatase rate constants for SOM pools 1-4), and `smax`, `ks_sorption` (maximum adsorption capacity and half-saturation constant for the Langmuir isotherm, used by `PhosphorusStateType%InitCold` to compute initial labilep in equilibrium with solution P).

### PhosphorusWeathering (`:87-137`)

For each soil level, every decomposition time step:

```fortran
r_weather_c = r_weather(isoilorder(c))       ! monthly fraction
rr = -log(1 - r_weather_c)                    ! continuous rate
r_weather_c = 1 - exp(-rr * dtd)              ! per-timestep fraction
primp_to_labilep(c,j) = primp(c,j) * r_weather_c / dt
```

This moves P from `primp_vr` to `labilep_vr` at a first-order rate. The soil-order weathering rate is what determines the long-term P budget of a column: highly weathered soils (Oxisol, Ultisol) have very low `r_weather` and accumulate occluded P.

### PhosphorusAdsportion / Desoprtion / Occlusion

All three routines follow the same pattern: first-order transfer between adjacent pools of the cascade, with the rate parameterized per soil order. Desorption and adsorption run as separate routines rather than a combined equilibrium because the implementation wants to compute each flux as a diagnostic output (`secondp_to_labilep_vr`, `labilep_to_secondp_vr`). The occlusion flux is `secondp * r_occlude / dt`.

For Occlusion: `secondp_to_occlp(c,j) = secondp(c,j) * r_occlude_c / dt` guarded by `if (secondp(c,j) > 0)`.

### PhosphorusLeaching (`:336-441`)

Structure parallels `NitrogenLeaching` but applies to solution P:

1. Compute `tot_water(c) = sum_j h2osoi_liq(c,j)` over the active soil column.
2. For each level: `disp_conc = solutionp_vr(c,j) * dz(c,j) / h2osoi_liq(c,j)` (gP/kg water).
3. `sminp_leached_vr(c,j) = disp_conc * drain_tot(c) * h2osoi_liq(c,j) / (tot_water(c) * dz(c,j))`.
4. Cap at `solutionp_vr(c,j) / dt` and clip to non-negative.
5. Use `depth_runoff_Ploss = 0.05 m` (hardcoded at `:360`) for surface runoff loss, in contrast to N leaching's `depth_runoff_Nloss`.

Note that unlike N leaching (which uses `sf_no3 < 1` to model non-soluble NO3), P leaching assumes all solution P is soluble (no `sf` factor).

### PhosphorusBiochemMin (`:450-550`)

Implements phosphatase-mediated mineralization of organic P from the decomposing pools. For each SOM pool `l` (1..4), each level `j`:

```fortran
k_s1_biochem_c = k_s1_biochem(isoilorder(c))          ! monthly rate
rr = -log(1 - k_s1_biochem_c)
k_s1_biochem_c = 1 - exp(-rr * dtd)                    ! per-timestep fraction

if decomp_ppools_vr_col(c,j,l) > 0:
    biochem_pmin_ppools_vr_col(c,j,l) = decomp_ppools_vr_col(c,j,l) * k_s1_biochem_c
                                        * fpi_vr_col(c,j) * (1 - exp(r_bc * (1 - fpi_p_vr_col(c,j)))) / dt
```

with `r_bc = -5.0` (hardcoded at `:498`). The factor `(1 - exp(r_bc * (1 - fpi_p_vr_col)))` scales phosphatase activity with P limitation: when P is not limiting (`fpi_p_vr_col` close to 1), the phosphatase activity is near zero; under strong P limitation (`fpi_p_vr_col` close to 0), `1 - exp(-5) ~ 0.99`, the full phosphatase rate is applied. The `fpi_vr_col` factor further scales by N availability (microbes need N to produce phosphatase enzymes). The total mineralization is summed across pools to `biochem_pmin_vr_col` (`:540-549`).

### PhosphorusBiochemMin_balance

Alternative "balance" version used when `nu_com_phosphatase = .true.` (cost-benefit phosphatase). This computes the optimal phosphatase activity by balancing the N cost of producing the enzyme against the P return, using partial-derivative fields in `nitrogenstate_type` (`benefit_pgpp_pleafn_patch`, `cost_plmr_pleafn_patch`, etc.). Active only under the ECA nutrient competition path.

## PhosphorusStateUpdate1Mod (stage 1: post-allocation)

`biogeochem/PhosphorusStateUpdate1Mod.F90` (377 lines). Two public routines:

### PhosphorusStateUpdateDynPatch (`:44`)

Called once per time step from the dynamic subgrid driver, parallel to `NitrogenStateUpdateDynPatch`. When `.not. use_fates`:

- `grc_ps%seedp(g) -= (dwt_seedp_to_leaf + dwt_seedp_to_deadstem + dwt_seedp_to_ppool) * dt`
- `col_ps%prod10p`, `prod100p`, `prod1p` += the respective `dwt_*_gain` fluxes.
- Column decomposing P pools gain fine root and coarse root transfers from landcover change in the same manner as N.

### PhosphorusStateUpdate1

Called from `EcosystemDynNoLeaching2` after allocation. Updates:

- Patch-level living pools: `veg_ps%leafp`, `leafp_storage`, `leafp_xfer`, `frootp`, `livestemp`, `deadstemp`, `livecrootp`, `deadcrootp`, `grainp`. For each, the stage-1 fluxes (allocation, phenology transfer, retranslocation) are applied: `veg_ps%leafp += leafp_xfer_to_leafp - leafp_to_litter - leafp_to_retransp`, etc.
- `veg_ps%ppool += sminp_to_ppool + retransp_to_ppool` minus all `ppool_to_*` allocation outflows.
- `veg_ps%retransp += leafp_to_retransp + frootp_to_retransp + livestemp_to_retransp + livecrootp_to_retransp`.
- Column decomposing P pools: `col_ps%decomp_ppools_vr(c,j,l) += decomp_cascade_ptransfer_vr(c,j,k) * dt` along each cascade transition.
- Column-level inorganic pools get updated by the cascade fluxes (one direction per flux), plus deposition and weathering inputs:
  - `col_ps%primp_vr(c,j) -= primp_to_labilep_vr * dt` (weathering loss)
  - `col_ps%labilep_vr(c,j) += (primp_to_labilep_vr - labilep_to_secondp_vr + secondp_to_labilep_vr) * dt`
  - `col_ps%secondp_vr(c,j) += (labilep_to_secondp_vr - secondp_to_labilep_vr - secondp_to_occlp_vr) * dt`
  - `col_ps%occlp_vr(c,j) += secondp_to_occlp_vr * dt`
  - `col_ps%solutionp_vr(c,j) += (pdep_to_sminp * pdep_prof_col(c,j) + biochem_pmin_vr - sminp_to_plant_vr - actual_immob_p_vr - ...) * dt`

NOTE: the exact coupling between solutionp and labilep is handled via a Langmuir equilibrium in the initial step and via the adsorption/desorption fluxes during the time loop; the exact details of the split depend on whether we're using the ECA path or the RD path. Under RD (`nu_com = 'RD'`), the full "sminp" is stored in `labilep_vr` and plant uptake comes directly from `labilep`. Under ECA (`nu_com /= 'RD'`), `solutionp_vr` is the kinetically active pool and `labilep_vr` is in sorption equilibrium with it.

The update is guarded against the BeTR path (`is_active_betr_bgc`) and against the PFLOTRAN path (`use_pflotran .and. pf_cmode`), both of which would handle the soil P updates through their own tracer transport.

Semantic meaning: **stage 1 = post-photosynthesis, post-allocation, post-decomposition cascade, post-phosphorus inorganic cascade, post-phosphorus deposition and weathering**.

## PhosphorusStateUpdate2Mod (stage 2: post-gap-mortality)

`biogeochem/PhosphorusStateUpdate2Mod.F90` (213 lines). Public routines `PhosphorusStateUpdate2` and `PhosphorusStateUpdate2h`.

### PhosphorusStateUpdate2

Applies gap-phase mortality fluxes to patch-level P pools and the column-level decomposing P pools:

```fortran
col_ps%decomp_ppools_vr(c,j,i_met_lit) += gap_mortality_p_to_litr_met_p(c,j) * dt
col_ps%decomp_ppools_vr(c,j,i_cel_lit) += gap_mortality_p_to_litr_cel_p(c,j) * dt
col_ps%decomp_ppools_vr(c,j,i_lig_lit) += gap_mortality_p_to_litr_lig_p(c,j) * dt
col_ps%decomp_ppools_vr(c,j,i_cwd)     += gap_mortality_p_to_cwdp(c,j)       * dt

veg_ps%leafp -= m_leafp_to_litter_patch * dt
veg_ps%frootp -= m_frootp_to_litter_patch * dt
! ... for every tissue and storage/xfer pool
veg_ps%retransp -= m_retransp_to_litter_patch * dt
veg_ps%ppool -= m_ppool_to_litter_patch * dt
```

### PhosphorusStateUpdate2h

Harvest variant. Applies `hrv_*_to_litter_patch` and sends deadstem harvest to `prod10p_col`, `prod100p_col`, crop harvest to `prod1p_col`. Subtracts the harvested tissue from patch pools.

Semantic meaning: **stage 2 = post-gap-mortality, post-harvest**.

## PhosphorusStateUpdate3Mod (stage 3: post-leaching and post-fire)

`biogeochem/PhosphorusStateUpdate3Mod.F90` (394 lines). Public routine `PhosphorusStateUpdate3`.

Called from `EcosystemDynLeaching` after `PhosphorusLeaching`. Applies leaching, fire, and (optionally) erosion losses:

```fortran
col_ps%solutionp_vr(c,j) = max( col_ps%solutionp_vr(c,j) - sminp_leached_vr(c,j) * dt, 0 )

! fire losses to decomposing pools
do l = 1, ndecomp_pools:
    col_ps%decomp_ppools_vr(c,j,l) -= m_decomp_ppools_to_fire_vr(c,j,l) * dt

! uncombusted wood and storage
col_ps%decomp_ppools_vr(c,j,i_cwd)     += fire_mortality_p_to_cwdp(c,j) * dt
col_ps%decomp_ppools_vr(c,j,i_met_lit) += m_p_to_litr_met_fire(c,j) * dt
col_ps%decomp_ppools_vr(c,j,i_cel_lit) += m_p_to_litr_cel_fire(c,j) * dt
col_ps%decomp_ppools_vr(c,j,i_lig_lit) += m_p_to_litr_lig_fire(c,j) * dt

! patch-level fire losses
veg_ps%leafp -= m_leafp_to_fire_patch * dt
! ... for every tissue
veg_ps%retransp -= m_retransp_to_fire_patch * dt
veg_ps%ppool    -= m_ppool_to_fire_patch * dt
```

If `ero_ccycle = .true.`, SOM P is also depleted by erosion through analogous flux terms (`som_p_leached_col` or `labilep_yield_col`, `secondp_yield_col` for the labile and secondary mineral fractions).

Semantic meaning: **stage 3 = post-leaching, post-fire, post-erosion**.

## Initial P Pools (InitCold)

The `InitCold` routine in `PhosphorusStateType.F90` seeds the initial P pools from PFT leaf/root C, from the decomposing C cascade, and from soil-order parameters `smax` and `ks_sorption`. The seed initialization uses:

- Initial leaf P = leaf C / C:P ratio from `veg_vp%leafcp(ivt)`.
- Initial fine root P = fine root C / C:P ratio from `veg_vp%frootcp(ivt)`.
- Initial dead stem P = dead stem C / C:P ratio from `veg_vp%deadcrootcp(ivt)`.
- Initial storage, xfer, ppool, retransp set to small constants scaled by `ppool_seed_param = 0.01` (module-level parameter at `PhosphorusStateType.F90:35`).
- Initial soil labile / solution / secondary / primary / occluded P computed from the Langmuir sorption isotherm equilibrium using soil-order `smax`, `ks_sorption`, `VMAX_MINSURF_P_vr`, and `KM_MINSURF_P_vr` from `pftvarcon`.

## Related Flags

- `nu_com = 'RD'` (default, relative demand) or `'ECA'`: selects the nutrient competition mode. RD uses the legacy CN logic adapted for P (proportional sharing). ECA uses enzyme-competition with Michaelis-Menten kinetics on solution P.
- `nu_com_phosphatase = .false.` (default): if true, phosphatase activity is computed from the cost-benefit balance rather than the fixed `PhosphorusBiochemMin` formula.
- `NFIX_PTASE_plant`: when true, plants can invest C in N fixation and phosphatase production; this activates `dynamic_plant_alloc` in `AllocationMod`.
- `use_fates = .true.`: FATES handles the vegetation P pools (via its own cohort-level state); ELM still runs the soil P cascade, mineralization, deposition, weathering, leaching, and erosion as described above. FATES communicates plant P demand to ELM through `main/ELMFatesInterfaceMod.F90` (the same interface used for N demand).
- `use_pflotran .and. pf_cmode`: bypasses ELM's P state updates for soil pools and relies on PFLOTRAN tracer transport instead.
- `ECA_Pconst_RGspin`: keep solution P constant during recovery/growth phase of spinup (namelist flag, checked in `EcosystemBalanceCheckMod.F90:19`).

## Summary Flow

A single radiation time step for the ELM P cycle (non-FATES, non-PFLOTRAN, non-BeTR):

1. `PhosphorusDeposition` (from `EcosystemDynNoLeaching1`): set `pdep_to_sminp` from forcing.
2. `PhosphorusWeathering`, `PhosphorusBiochemMin` (or `_balance`): called twice, once in `EcosystemDynNoLeaching1` and once in `EcosystemDynLeaching`. In the first pass, labile P and solution P are augmented with weathered and biochemically mineralized P before plant and decomposer competition sees them. In the second pass, the updated state is propagated to leaching.
3. `PhosphorusBiochemMin` contributes to `biochem_pmin_vr_col`, which feeds into `sminp_to_plant_vr_col` / `actual_immob_p_vr_col` resolution.
4. Decomposition cascade (in `SoilLittDecompAlloc`): gross P mineralization and immobilization computed per cascade transition based on decomposer C:P stoichiometry.
5. `Allocation2_ResolveNPLimit`: split P between plants and decomposers, produce `fpg_p_col`, `fpi_p_vr_col`, `sminp_to_plant_vr_col`.
6. `Allocation3_PlantCNPAlloc`: apply the resolved fractions, emit `ppool_to_leafp_patch`, etc.
7. `PhosphorusStateUpdate1` (stage 1).
8. `GapMortality` + `PhosphorusStateUpdate2` + `PhosphorusStateUpdate2h` (stage 2).
9. `FireFluxes` contribute fire P fluxes.
10. `EcosystemDynLeaching`: `PhosphorusWeathering`, `PhosphorusAdsportion`, `PhosphorusDesoprtion`, `PhosphorusOcclusion` (updated inorganic cascade), `PhosphorusLeaching`, `PhosphorusStateUpdate3` (stage 3).
11. `PrecisionControl` moves any round-off negatives into `ptrunc_vr_col` / `ptrunc_col`.
12. Summary routines aggregate to patch, column, grid.

Under FATES the vegetation portions of steps 4-9 are bypassed (FATES runs its own plant P dynamics), but the entire soil inorganic cascade (steps 1-3, 10) and mineralization (step 4) still runs, because FATES cohorts consume P from the ELM mineral P pool via the `sminp_to_plant_vr_col` uptake channel.
