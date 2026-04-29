---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Phosphorus Dynamics

Phosphorus is an ELM-specific extension (Yang et al. 2014/2016) over the
CESM/CLM ancestor. The N-P coupled path runs when ELM is compiled with the CNP
option enabled. At the vegetation level, P flows through the same three-state
tissue structure as N (display + storage + xfer pools), and the plant P balance
is closed by the three staged updaters
`biogeochem/PhosphorusStateUpdate1Mod.F90`,
`PhosphorusStateUpdate2Mod.F90`, `PhosphorusStateUpdate3Mod.F90`. At the soil
level, P has a four-reservoir inorganic cascade (solution / labile / secondary
mineral / occluded) plus a primary-mineral weathering source, implemented in
`biogeochem/PhosphorusDynamicsMod.F90`. The derived types `phosphorusstate_type`
and `phosphorusflux_type` are described in `cnp_state_and_fluxes.md`.

## Conceptual Overview of the Inorganic P Cascade

The soil P cycle has a structure fundamentally different from soil N:

- P has no atmospheric redox transformations; no gaseous loss pathway.
- P availability is controlled by sorption/desorption equilibria between
  soil solution P (`solutionp`), exchangeable adsorbed "labile" P (`labilep`),
  strongly adsorbed/precipitated "secondary mineral" P (`secondp`), and
  chemically "occluded" P (`occlp`).
- Fresh P enters from weathering of primary minerals (`primp`) and atmospheric
  deposition (dust). Phosphatase-mediated biochemical mineralization is an
  additional source path that plants and microbes upregulate under P
  limitation.
- P is lost via leaching (solution P moving with drainage), soil erosion, fire,
  and occlusion.

ELM stores each pool per decomposition layer (`nlevdecomp_full`) in
`phosphorusstate_type`. Pools are summarized in `cnp_state_and_fluxes.md`.

## PhosphorusDynamicsMod (signatures rewritten at d40b8431)

`biogeochem/PhosphorusDynamicsMod.F90` (757 lines). Public entries (with the
exact arg lists at d40b8431):

| Subroutine | Line | Signature |
|---|---|---|
| `PhosphorusDeposition` | `:51` | `(bounds, atm2lnd_vars)` — 2 args. |
| `PhosphorusWeathering` | `:88` | `(num_soilc, filter_soilc, cnstate_vars, dt)`. |
| `PhosphorusAdsportion` | `:136` | `(num_soilc, filter_soilc, cnstate_vars, dt)`. |
| `PhosphorusDesoprtion` | `:190` | `(num_soilc, filter_soilc, cnstate_vars, dt)`. |
| `PhosphorusOcclusion` | `:243` | `(num_soilc, filter_soilc, cnstate_vars, dt)`. |
| `PhosphorusLeaching` | `:297` | `(num_soilc, filter_soilc, dt)` — **`bounds` removed**. |
| `PhosphorusBiochemMin` | `:389` | `(num_soilc, filter_soilc, cnstate_vars, dt)` — **`bounds` removed**. |
| `PhosphorusBiochemMin_balance` | `:477` | `(bounds, num_soilc, filter_soilc, cnstate_vars, dt)`. |
| `PhosphorusFert` | `:729` | `(bounds, num_soilc, filter_soilc)`. |

Note that the ECA "balance" path (`PhosphorusBiochemMin_balance`) still takes
`bounds`; only the default `PhosphorusBiochemMin` lost it.

### Soil-order parameters

The per-soil-order rates `r_weather`, `r_adsorp`, `r_desorp`, `r_occlude` are
defined in `main/soilorder_varcon.F90` and indexed by a per-column soil order
integer `cnstate_vars%isoilorder`. The rates have units of monthly fraction and
are converted to per-time-step fluxes using a log transformation:

```fortran
r_weather_c = r_weather(isoilorder(c))       ! monthly fraction
rr = -log(1 - r_weather_c)                   ! continuous rate
r_weather_c = 1 - exp(-rr * dtd)             ! per-timestep fraction
```

with `dtd = dt / (30 * secspday)`. Soil order map comes from the surface
dataset, typically values 1 through 12 for the USDA orders (Entisol, Inceptisol,
Andisol, Mollisol, Alfisol, Ultisol, Oxisol, Vertisol, Histosol, Aridisol,
Spodosol, Gelisol).

Additional soil-order parameters for biochemical mineralization in
`soilorder_varcon`: `k_s1_biochem`, `k_s2_biochem`, `k_s3_biochem`,
`k_s4_biochem` (monthly phosphatase rate constants for SOM pools 1-4), `smax`,
`ks_sorption` (Langmuir adsorption parameters used by
`PhosphorusStateType%InitCold`).

### PhosphorusWeathering (`:88`)

For each soil level, every decomposition time step:

```fortran
primp_to_labilep(c,j) = primp(c,j) * r_weather_c / dt
```

### PhosphorusAdsportion / Desoprtion / Occlusion

All three follow the same pattern: first-order transfer between adjacent pools
of the cascade, with the rate parameterized per soil order.
`secondp_to_occlp(c,j) = secondp(c,j) * r_occlude_c / dt`.

### PhosphorusLeaching (`:297`)

Structure parallels `NitrogenLeaching` but applies to solution P:

1. `tot_water(c) = sum_j h2osoi_liq(c,j)` over the active soil column.
2. For each level: `disp_conc = solutionp_vr(c,j) * dz(c,j) / h2osoi_liq(c,j)`.
3. `sminp_leached_vr(c,j) = disp_conc * drain_tot(c) * h2osoi_liq(c,j) /
   (tot_water(c) * dz(c,j))`.
4. Cap at `solutionp_vr(c,j) / dt`, clip to non-negative.
5. `depth_runoff_Ploss = 0.05 m` (hardcoded inside the routine) for surface
   runoff loss.

Unlike N leaching, P leaching assumes all solution P is soluble (no `sf`
factor).

### PhosphorusBiochemMin (`:389`)

Implements phosphatase-mediated mineralization of organic P from the
decomposing pools. For each SOM pool `l` (1..4), each level `j`:

```fortran
biochem_pmin_ppools_vr_col(c,j,l) = decomp_ppools_vr_col(c,j,l) * k_biochem_c
                                   * fpi_vr_col(c,j) &
                                   * (1 - exp(r_bc * (1 - fpi_p_vr_col(c,j)))) / dt
```

with `r_bc = -5.0` (hardcoded). The factor `(1 - exp(r_bc * (1 -
fpi_p_vr_col)))` scales phosphatase activity with P limitation: when P is not
limiting (`fpi_p_vr_col` close to 1), the phosphatase activity is near zero;
under strong P limitation (`fpi_p_vr_col` close to 0), `1 - exp(-5) ~ 0.99`,
the full phosphatase rate is applied. The `fpi_vr_col` factor scales by N
availability (microbes need N to produce phosphatase enzymes). Total
mineralization is summed across pools to `biochem_pmin_vr_col`.

### PhosphorusBiochemMin_balance (`:477`)

Alternative version used when `nu_com_phosphatase = .true.`. Computes optimal
phosphatase activity by balancing the N cost of producing the enzyme against
the P return, using partial-derivative fields in `nitrogenstate_type`
(`benefit_pgpp_pleafn_patch`, `cost_plmr_pleafn_patch`, etc.). Active only
under the ECA path. **Retains `bounds` argument** unlike `PhosphorusBiochemMin`.

## PhosphorusStateUpdate1Mod (stage 1: post-allocation)

`biogeochem/PhosphorusStateUpdate1Mod.F90`. Two public routines:

### PhosphorusStateUpdateDynPatch (`:44`)

Called once per time step from the dynamic subgrid driver. When `.not.
use_fates`:

- `grc_ps%seedp(g) -= (dwt_seedp_to_leaf + dwt_seedp_to_deadstem +
  dwt_seedp_to_ppool) * dt`
- `col_ps%prod10p`, `prod100p`, `prod1p` += the respective `dwt_*_gain` fluxes.
- Column decomposing P pools gain fine root and coarse root transfers from
  landcover change.

### PhosphorusStateUpdate1 (`:99`)

Called from `EcosystemDynNoLeaching2:709`. Updates:

- Patch-level living pools: `veg_ps%leafp`, `leafp_storage`, `leafp_xfer`,
  `frootp`, `livestemp`, `deadstemp`, `livecrootp`, `deadcrootp`, `grainp`.
  For each, the stage-1 fluxes (allocation, phenology transfer, retranslocation)
  are applied.
- `veg_ps%ppool += sminp_to_ppool + retransp_to_ppool` minus all `ppool_to_*`
  allocation outflows.
- `veg_ps%retransp += leafp_to_retransp + frootp_to_retransp + livestemp_to_retransp + livecrootp_to_retransp`.
- Column decomposing P pools: `col_ps%decomp_ppools_vr(c,j,l) +=
  decomp_cascade_ptransfer_vr(c,j,k) * dt` along each cascade transition.
- Column-level inorganic pools updated by cascade fluxes plus deposition and
  weathering inputs:
  - `col_ps%primp_vr(c,j) -= primp_to_labilep_vr * dt` (weathering loss)
  - `col_ps%labilep_vr(c,j) += (primp_to_labilep_vr - labilep_to_secondp_vr +
    secondp_to_labilep_vr) * dt`
  - `col_ps%secondp_vr(c,j) += (labilep_to_secondp_vr - secondp_to_labilep_vr -
    secondp_to_occlp_vr) * dt`
  - `col_ps%occlp_vr(c,j) += secondp_to_occlp_vr * dt`
  - `col_ps%solutionp_vr(c,j) += (pdep_to_sminp * pdep_prof_col(c,j) +
    biochem_pmin_vr - sminp_to_plant_vr - actual_immob_p_vr - ...) * dt`

Under RD (`nu_com == 'RD'`), the full `sminp` is stored in `labilep_vr` and
plant uptake comes directly from `labilep`. Under ECA (`nu_com /= 'RD'`),
`solutionp_vr` is the kinetically active pool and `labilep_vr` is in sorption
equilibrium with it.

The update is guarded against the BeTR path (`is_active_betr_bgc`) and against
the PFLOTRAN path (`use_pflotran .and. pf_cmode`).

Semantic meaning: **stage 1 = post-photosynthesis, post-allocation,
post-decomposition cascade, post-phosphorus inorganic cascade, post-phosphorus
deposition and weathering**.

## PhosphorusStateUpdate2Mod (stage 2: post-gap-mortality)

`biogeochem/PhosphorusStateUpdate2Mod.F90`. Public routines
`PhosphorusStateUpdate2(num_soilc, filter_soilc, num_soilp, filter_soilp, dt)`
(`:34`) and `PhosphorusStateUpdate2h` (`:117`).

### PhosphorusStateUpdate2

Applies gap-phase mortality fluxes to patch-level P pools and column-level
decomposing P pools:

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

Harvest variant. Applies `hrv_*_to_litter_patch` and sends deadstem harvest to
`prod10p_col`, `prod100p_col`, crop harvest to `prod1p_col`.

Semantic meaning: **stage 2 = post-gap-mortality, post-harvest**.

## PhosphorusStateUpdate3Mod (stage 3: post-leaching and post-fire)

`biogeochem/PhosphorusStateUpdate3Mod.F90`. Public routine
`PhosphorusStateUpdate3(bounds, num_soilc, filter_soilc, num_soilp,
filter_soilp, ...)` (`:40`). Note this updater retains `bounds`.

Called from `EcosystemDynLeaching` after `PhosphorusLeaching`. Applies
leaching, fire, and (optionally) erosion losses:

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

If `ero_ccycle = .true.`, SOM P is also depleted by erosion.

Semantic meaning: **stage 3 = post-leaching, post-fire, post-erosion**.

## Initial P Pools (InitCold)

`InitCold` in `PhosphorusStateType.F90` seeds initial P pools from PFT
leaf/root C, the decomposing C cascade, and soil-order parameters `smax` and
`ks_sorption`:

- Initial leaf P = leaf C / C:P ratio from `veg_vp%leafcp(ivt)`.
- Initial fine root P = fine root C / C:P ratio from `veg_vp%frootcp(ivt)`.
- Initial dead stem P = dead stem C / C:P ratio from `veg_vp%deadcrootcp(ivt)`.
- Initial storage, xfer, ppool, retransp scaled by `ppool_seed_param = 0.01`
  (module-level parameter).
- Initial soil labile/solution/secondary/primary/occluded P from Langmuir
  sorption isotherm equilibrium using `smax`, `ks_sorption`, `VMAX_MINSURF_P_vr`,
  `KM_MINSURF_P_vr` from `pftvarcon`.

## Related Flags

- `nu_com = 'RD'` (default) or `'ECA'`: nutrient competition mode.
- `nu_com_phosphatase = .false.` (default): if true, phosphatase activity
  computed from cost-benefit balance (`PhosphorusBiochemMin_balance`).
- `NFIX_PTASE_plant`: when true, plants invest C in N fixation and phosphatase
  production; activates `dynamic_plant_alloc` in `AllocationMod`.
- `use_fates = .true.` (`elm_varctl.F90:227`): FATES handles the vegetation P
  pools. ELM still runs the soil P cascade, mineralization, deposition,
  weathering, leaching, and erosion. FATES communicates plant P demand to ELM
  through `main/elmfates_interfaceMod.F90` (lowercase filename — note that
  some older docs used a CamelCase form of this filename, which never matched
  the on-disk lowercase path).
- `use_pflotran .and. pf_cmode`: bypasses ELM's P state updates for soil pools.
- `ECA_Pconst_RGspin`: keep solution P constant during recovery/growth phase
  of spinup.

## Summary Flow

A single radiation time step for the ELM P cycle (non-FATES, non-PFLOTRAN,
non-BeTR):

1. `PhosphorusDeposition(bounds, atm2lnd_vars)` (`:51`, from
   `EcosystemDynNoLeaching1:437`).
2. (If `nu_com /= 'RD'`) `PhosphorusWeathering` and either
   `PhosphorusBiochemMin` or `PhosphorusBiochemMin_balance`
   (`EcosystemDynNoLeaching1:411-430`). Augments labile P and solution P
   before plant and decomposer competition sees them.
3. `PhosphorusBiochemMin` contributes to `biochem_pmin_vr_col`.
4. Decomposition cascade in `SoilLittDecompAlloc`: gross P mineralization and
   immobilization computed per cascade transition based on decomposer C:P
   stoichiometry.
5. `Allocation2_ResolveNPLimit`: split P between plants and decomposers,
   produce `fpg_p_col`, `fpi_p_vr_col`, `sminp_to_plant_vr_col`.
6. (Dispatched by `nu_com`) `PlantCNPAlloc_RD` or `PlantCNPAlloc_ECAMIC`:
   apply resolved fractions, emit `ppool_to_leafp_patch`, etc.
7. `PhosphorusStateUpdate1` (stage 1).
8. `GapMortality` (only when `.not. use_fates`) + `PhosphorusStateUpdate2` +
   `PhosphorusStateUpdate2h` (stage 2).
9. `FireFluxes` contributes fire P fluxes.
10. `EcosystemDynLeaching`: `PhosphorusWeathering`, `PhosphorusAdsportion`,
    `PhosphorusDesoprtion`, `PhosphorusOcclusion` (updated inorganic cascade),
    `PhosphorusLeaching(num_soilc, filter_soilc, dt)`,
    `PhosphorusStateUpdate3(bounds, ...)` (stage 3).
11. `PrecisionControl` moves any round-off negatives into `ptrunc_vr_col` /
    `ptrunc_col`.
12. Summary routines aggregate to patch, column, grid.

Under FATES, the vegetation portions of steps 4-9 are bypassed (FATES runs its
own plant P dynamics), but the entire soil inorganic cascade (steps 1-3, 10)
and mineralization (step 4) still runs because FATES cohorts consume P from
the ELM mineral P pool via the `sminp_to_plant_vr_col` uptake channel.
