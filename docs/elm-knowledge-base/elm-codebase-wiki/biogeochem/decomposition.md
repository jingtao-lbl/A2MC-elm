---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Decomposition Cascade and Vertical Soil BGC

ELM represents soil organic matter (SOM) turnover as a cascade of donor -> receiver transitions among a small number of pools, with vertical resolution over `nlevdecomp` layers and a tridiagonal solver for vertical mixing (bio- and cryo-turbation). This page covers the cascade definition (`biogeochem/CNDecompCascadeConType.F90`), the two alternative parameterizations (CENTURY/BGC and CN), the main decomposition driver (`biogeochem/SoilLittDecompMod.F90`), and the vertical transport (`biogeochem/SoilLittVertTranspMod.F90`).

## Cascade Topology

The cascade topology is stored in the module-global type `decomp_cascade_con` declared in `biogeochem/CNDecompCascadeConType.F90:20`. Its fields describe per-transition and per-pool properties:

```fortran
type :: decomp_cascade_type
   ! per-transition:
   character(len=8),  pointer :: cascade_step_name(:)      ! 'L1S1', 'L2S1', ...
   integer,           pointer :: cascade_donor_pool(:)     ! pool index
   integer,           pointer :: cascade_receiver_pool(:)
   ! per-pool:
   logical,           pointer :: floating_cn_ratio_decomp_pools(:)  ! TRUE => pool has "floating" (receiver-inherited) C:N
   logical,           pointer :: floating_cp_ratio_decomp_pools(:)
   character(len=8),  pointer :: decomp_pool_name_restart(:)
   character(len=8),  pointer :: decomp_pool_name_history(:)
   character(len=20), pointer :: decomp_pool_name_long(:)
   character(len=8),  pointer :: decomp_pool_name_short(:)
   logical,           pointer :: is_litter(:)              ! TRUE => litter pool
   logical,           pointer :: is_soil(:)                ! TRUE => SOM pool
   logical,           pointer :: is_cwd(:)                 ! TRUE => CWD pool
   real(r8),          pointer :: initial_cn_ratio(:)
   real(r8),          pointer :: initial_cp_ratio(:)
   real(r8),          pointer :: initial_stock(:)
   logical,           pointer :: is_metabolic(:)
   logical,           pointer :: is_cellulose(:)
   logical,           pointer :: is_lignin(:)
   real(r8),          pointer :: spinup_factor(:)          ! AD spinup acceleration per pool
   real(r8),          pointer :: decomp_k_pools(:)         ! 1/s per pool
end type
```

`init_decomp_cascade_constants` (`CNDecompCascadeConType.F90:52`) allocates these arrays over `0:ndecomp_pools` (the 0 index is "atmosphere" for respiration sinks in the pflotran coupling) and `1:ndecomp_cascade_transitions`. The actual content is filled in by either `DecompCascadeBGCMod%init_decompcascade_bgc` or `DecompCascadeCNMod%init_decompcascade_cn`, selected by the `use_century_decomp` flag in `elm_varctl`.

## BGC / CENTURY Parameterization (default)

`biogeochem/DecompCascadeBGCMod.F90` implements the CENTURY/BGC parameterization with 3 SOM pools, 3 litter pools, and 1 CWD pool (total `ndecomp_pools = 7`), and 10 transitions. The parameters are stored in `DecompBGCParamsInst` (type `DecompBGCParamsType`, `:47`), read from the NetCDF parameter file by `readDecompBGCParams` (`:98`):

| Parameter group | Fields |
|---|---|
| C:N of SOM | `cn_s1_bgc`, `cn_s2_bgc`, `cn_s3_bgc` |
| N:P of SOM (new) | `np_s1_new_bgc`, `np_s2_new_bgc`, `np_s3_new_bgc` |
| C:P of SOM (new) | `cp_s1_new_bgc`, `cp_s2_new_bgc`, `cp_s3_new_bgc` |
| Respiration fractions | `rf_l1s1_bgc` (litter1 -> SOM1), `rf_l2s1_bgc` (litter2 -> SOM1), `rf_l3s2_bgc` (litter3 -> SOM2), `rf_s2s1_bgc`, `rf_s2s3_bgc`, `rf_s3s1_bgc`, `rf_cwdl2_bgc`, `rf_cwdl3_bgc` |
| Turnover times (years) | `tau_l1_bgc` (litter 1), `tau_l2_l3_bgc` (litter 2 and 3), `tau_s1_bgc`, `tau_s2_bgc`, `tau_s3_bgc`, `tau_cwd_bgc` |
| CWD fractions | `cwd_fcel_bgc` (cellulose), `cwd_flig_bgc` (lignin) |
| Water potential | `minpsi_bgc` (minimum soil water potential for HR) |
| Fragmentation | `k_frag_bgc` (CWD fragmentation rate) |
| AD spinup | `nsompools = 3`, `spinup_vector = (/ 1.0, 15.0, 675.0 /)` (hardcoded at `:147`) |

### Pool Indices and Attributes

`init_decompcascade_bgc` (`:350`) populates the decomp_cascade_con arrays. The pool indices are (`:413-538`):

| idx | Name | Short | Long name | Kind | `is_cellulose` | `is_lignin` | `is_metabolic` | Floating C:N | Initial C:N | Initial stock |
|---|---|---|---|---|---|---|---|---|---|---|
| `i_litr1 = i_met_lit` | litr1 | L1 | litter 1 | litter | F | F | **T** | T | 90 | 0 |
| `i_litr2 = i_cel_lit` | litr2 | L2 | litter 2 | litter | **T** | F | F | T | 90 | 0 |
| `i_litr3 = i_lig_lit` | litr3 | L3 | litter 3 | litter | F | **T** | F | T | 90 | 0 |
| `i_cwd = 4`   | cwd   | CWD | coarse woody debris | CWD | F | F | F | T | 90 | 0 |
| `i_soil1 = 5` | soil1 | S1  | soil 1 | SOM | F | F | F | F | `cn_s1` | 20 |
| `i_soil2 = 6` | soil2 | S2  | soil 2 | SOM | F | F | F | F | `cn_s2` | 20 |
| `i_soil3 = 7` | soil3 | S3  | soil 3 | SOM | F | F | F | F | `cn_s3` | 20 |

A note at `DecompCascadeBGCMod.F90:464` explains that when FATES is active, the CWD pool is left in place but always stays at zero because FATES does its own CWD bookkeeping and only delivers already-fragmented litter to ELM.

### Cascade Transitions (BGC/CENTURY)

Defined at `:551-619`. Each transition has a `rf` (respiration fraction, fraction of donor C released as CO2 during the transition) and a `pathfrac` (fraction of outgoing C that flows through this specific transition, the remainder going through alternative transitions from the same donor):

| `i_*` | Step | Donor | Receiver | `rf` | `pathfrac` |
|---|---|---|---|---|---|
| 1 | L1S1 | litr1 | soil1 | `rf_l1s1` | 1.0 |
| 2 | L2S1 | litr2 | soil1 | `rf_l2s1` | 1.0 |
| 3 | L3S2 | litr3 | soil2 | `rf_l3s2` | 1.0 |
| 4 | S1S2 | soil1 | soil2 | `rf_s1s2(c,j)` (depth dependent on sand fraction) | `f_s1s2 = 1 - .004/(1-t)` |
| 5 | S1S3 | soil1 | soil3 | `rf_s1s3(c,j)` (same) | `f_s1s3 = .004/(1-t)` |
| 6 | S2S1 | soil2 | soil1 | `rf_s2s1` | `f_s2s1 = 0.42/0.45` |
| 7 | S2S3 | soil2 | soil3 | `rf_s2s3` | `f_s2s3 = 0.03/0.45` |
| 8 | S3S1 | soil3 | soil1 | `rf_s3s1` | 1.0 |
| 9 | CWDL2 | cwd   | litr2 | `rf_cwdl2` | `cwd_fcel` |
| 10 | CWDL3 | cwd  | litr3 | `rf_cwdl3` | `cwd_flig` |

where `t = 0.85 - 0.68 * 0.01 * (100 - cellsand(c,j))` (`:404`) scales the SOM1 respiration fraction and the S1S2/S1S3 split with soil texture (more sand -> smaller `t` -> more S1->S2 flow, less respiration). This matches the CENTURY texture dependence.

### Rate Constants (BGC/CENTURY)

`decomp_rate_constants_bgc` (`:631`) computes the rate constants `decomp_k(c,j,l)` (1/s) at each level from:

- Base turnover times (hardcoded at `:730-737` to preserve bit-for-bit reproducibility):
  ```
  tau_l1    = 1./18.5       (yr)
  tau_l2_l3 = 1./4.9        (yr)
  tau_s1    = 1./7.3        (yr)
  tau_s2    = 1./0.2        (yr)
  tau_s3    = 1./.0045      (yr)
  tau_cwd   = 1./0.3        (yr)
  ```
  A comment notes these could be read from the parameters file but the explicit divide gives different rounding behavior from reading the already-divided value.
- Temperature scalar `t_scalar(c,j)`: Q10 from `ParamsShareInst%Q10_hr`, reference `T0 = 15 C`, frozen Q10 `froz_q10`. Optionally the CENTURY temperature function `catanf(t1) = 11.75 + (29.7/pi) * atan(pi * 0.031 * (t1 - 15.4))` is used if `use_century_tfunc = .true.`. Normalization (`normalize_q10_to_century_tfunc = .true.` default) rescales the CENTURY rates to match CLM Q10 at the reference temperature.
- Moisture scalar `w_scalar(c,j)`: `log(minpsi/soilpsi)/log(minpsi/maxpsi)` clipped to `[0, 1]`, where `minpsi` comes from `ParamsShareInst%minpsi`.
- Oxygen scalar `o_scalar(c,j)`: anoxia limitation from CH4 module (`ch4_vars%o2stress_sat`, `ch4_vars%o2stress_unsat`, finundated), floored at `ParamsShareInst%mino2lim` when `anoxia = .true.` and `use_lch4 = .true.`.
- Depth scalar `depth_scalar(c,j) = exp(-zsoi(j)/decomp_depth_efolding)` (default `decomp_depth_efolding = 0.5 m` from `ParamsShareInst`).
- AD spinup factor per SOM pool: `spinup_factor(i_soil{1,2,3})` from `DecompBGCParamsInst%spinup_vector`, applied to accelerate the decay of slow pools during accelerated-decomposition spinup.

The final rate is `decomp_k(c,j,l) = base_k * t_scalar * w_scalar * o_scalar * depth_scalar * spinup_factor(l)`.

## CN Parameterization (alternative)

`biogeochem/DecompCascadeCNMod.F90` implements the original CLMCN 4.0 cascade with 4 SOM pools (S1..S4), 3 litter pools, and 1 CWD pool (total `ndecomp_pools = 8`). Parameters in `DecompCNParamsInst` (`:38`):

- C:N for SOM1..SOM4, N:P and C:P for SOM1..SOM4 (new).
- Respiration fractions: `rf_l1s1_cn` (litter1 -> SOM1, unlike BGC where it goes L1->S1), `rf_l2s2_cn`, `rf_l3s3_cn`, `rf_s1s2_cn`, `rf_s2s3_cn`, `rf_s3s4_cn`.
- Decomposition rate constants: `k_l1_cn`, `k_l2_cn`, `k_l3_cn`, `k_s1_cn`, `k_s2_cn`, `k_s3_cn`, `k_s4_cn`, `k_frag_cn`.
- CWD fractions `cwd_fcel_cn`, `cwd_flig_cn`, minimum water potential `minpsi_cn`.
- Pool counts: `nsompools = 4`, `nlitpools = 3`, `ncwdpools = 1`.
- AD spinup multipliers: `spinup_vector(4)`.

The CN cascade has a simpler topology with strictly sequential L1 -> S1 -> S2 -> S3 -> S4 flow plus CWD fragmentation. Select this path by setting `use_century_decomp = .false.` in the namelist (it is `.true.` by default).

## SoilLittDecompMod (Main Decomposition Driver)

`biogeochem/SoilLittDecompMod.F90` is the primary driver for soil BGC. Two public routines form the decomposition call sequence:

- `SoilLittDecompAlloc` (`:93`) computes the potential decomposition fluxes and resolves N/P competition between plants and decomposers.
- `SoilLittDecompAlloc2` (not shown in read snippet but mentioned in comments) performs the final CNP allocation and vertically integrates mineralization fluxes.

### SoilLittDecompAlloc (phase-1)

Computes, for each transition `k`:

1. `p_decomp_cpool_loss(c,j,k) = decomp_cpools_vr(c,j, donor) * decomp_k(c,j,donor) * pathfrac_decomp_cascade(c,j,k)` (potential C loss from donor pool).
2. For each donor level and transition, partition the C flux into:
   - Respiration: `rf_decomp_cascade(c,j,k) * p_decomp_cpool_loss(c,j,k)` (released as CO2, `phr_vr_col`).
   - Transfer to receiver: `(1 - rf_decomp_cascade) * p_decomp_cpool_loss`.
3. Compute N and P demand of each transition: `pmnf_decomp_cascade(c,j,k) = C_transfer * (1/cn_receiver - (1-rf)/cn_donor)` where positive means immobilization, negative means gross mineralization.
4. Sum positive pmnf across transitions to `potential_immob_vr_col`; sum negative (i.e. mineralization releases) to `gross_nmin_vr_col`.
5. Same for P via `pmpf_decomp_cascade`, `potential_immob_p_vr_col`, `gross_pmin_vr_col`.
6. Call `Allocation2_ResolveNPLimit` which combines `potential_immob_*`, `gross_*_min_vr_col`, plant demand, and nutrient availability to compute `fpi_vr_col`, `fpi_col`, `fpg_col`, `fpi_p_vr_col`, `fpg_p_col`, `actual_immob_vr_col`, `sminn_to_plant_vr_col`.
7. Also call `nitrif_denitrif` which computes `f_nit_vr_col`, `f_denit_vr_col` that remove NH4/NO3 from the mineral N pool.

### SoilLittDecompAlloc2 (phase-2)

Takes the resolved `fpi_vr_col` and `fpi_p_vr_col`, scales each cascade transition's C flux by these factors (so that when plant demand exceeds supply, the decomposition cascade is effectively slowed by the fraction actually allowed), and writes the final `decomp_cascade_hr_vr_col`, `decomp_cascade_ctransfer_vr_col`, `decomp_cascade_ntransfer_vr_col`, `decomp_cascade_ptransfer_vr_col`, `soil_n_immob_flux`, `soil_p_immob_flux`, and the vertically integrated `gross_nmin`, `net_nmin`, `gross_pmin`, `net_pmin` in `col_nf` and `col_pf`. Also calls `Allocation3_PlantCNPAlloc` to emit the final plant allocation fluxes.

### readSoilLittDecompParams

Reads `CNDecompParamsInst%dnp` (denitrification proportion), used for the non-nitrif_denitrif code path.

## VerticalProfileMod

`biogeochem/VerticalProfileMod.F90` computes the vertical distributions that are used to convert surface fluxes (leaf litter, stem litter, N deposition, N fixation, P deposition) into vertically resolved column fluxes. Single public routine `decomp_vertprofiles` (`:36`). Two mode switches:

- `exponential_rooting_profile = .true.` (default): use exponential `exp(-rootprof_exp * zsoi(j))` for root inputs (default `rootprof_exp = 3`/m). `surfprof_exp = 10`/m for surface components (leaves, stems, N/P deposition).
- `pftspecific_rootingprofile = .true.` (default): use PFT-specific Jackson beta distribution: `rootprof_beta(ivt)^(zisoi(j-1)*100) - rootprof_beta(ivt)^(zisoi(j)*100)`, clipped to the active layer above bedrock.

Computed profiles per patch (`leaf_prof_patch`, `froot_prof_patch`, `stem_prof_patch`, `croot_prof_patch`) and per column (`nfixation_prof_col`, `ndep_prof_col`, `pdep_prof_col`) each integrate to unity over the active layer. The active layer depth comes from `altmax_lastyear_indx_col` (permafrost-aware): in permafrost regions the integration is cut off at the previous year's active-layer thickness so that surface inputs stay in the thawed zone. At permafrost-dominated columns (rootfr_tot = 0), all inputs are placed in layer 1.

For FATES columns, the N fixation, N deposition, and P deposition profiles use the surface profile only (no root profile) since FATES handles rooting internally: `nfixation_prof(c,j) = surface_prof(j) / surface_prof_tot` (`:255`).

When `use_vertsoilc = .false.` (single-layer decomposition mode), all profiles are set to unity so that surface fluxes are all deposited into layer 1.

## SoilLittVertTranspMod

`biogeochem/SoilLittVertTranspMod.F90` solves vertical mixing (advection + diffusion) of decomposing pools using a tridiagonal Patankar (1980) scheme. Main driver `SoilLittVertTransp` (`:96`).

### Parameters (read from parameters NetCDF via `readSoilLittVertTranspParams`)

- `som_diffus`: SOM diffusion (default hardcoded at `:75` to `1e-4 / (secspday * 365)`  m^2/s = 1 cm^2/yr; the value from the file is ignored for bit-for-bit reasons).
- `cryoturb_diffusion_k`: cryoturbation diffusion rate, similarly hardcoded to `5e-4 / (secspday * 365)` m^2/s = 5 cm^2/yr = 1 m^2 / 200 yr (`:85`). Enhanced mixing in the permafrost active layer.
- `max_altdepth_cryoturbation`: maximum active layer thickness for cryoturbation to occur (read from file).

Module-level constants:
- `som_adv_flux = 0` (no advection by default; the solver supports advection but it is disabled).
- `max_depth_cryoturb = 3 m` (maximum depth cryoturbation extends).

### Algorithm

At each time step, for each vertically resolved pool `l` in `ndecomp_pools`:

1. Compute effective diffusivity per layer interface: `diffus(c,j+1)`. In cryoturbation columns (active layer within `max_altdepth_cryoturbation` of surface), `diffus = cryoturb_diffusion_k`, linearly tapered down to `som_diffus` below the active layer and going to zero at `max_depth_cryoturb`. Otherwise pure `som_diffus`.
2. Compute advective flux `adv_flux` (zero by default).
3. Build the tridiagonal matrix `a_tri`, `b_tri`, `c_tri`, `r_tri` using the "A" function from Patankar (1980) that chooses the weighting between upwind and central differences based on the Peclet number `pe = adv_flux * dz / diffus`.
4. Call `Tridiagonal` from `TridiagonalMod` to solve for the updated concentration.
5. Store the tendency in `decomp_cpools_transport_tendency_col` for history output and for use by the next time step's source-sink term.

During AD spinup (`spinup_state /= 0`), the vertical transport rates are also accelerated by the `spinup_factor` of each pool to keep the system at near-steady-state faster.

The N, P, C13, and C14 decomposing pools are transported using the same coefficients. Loop over `i_type = 1..ntype` where ntype includes C (bulk), N, P, and isotopes as appropriate.

## Summary

The decomposition pipeline is:

1. **Cascade topology** (fixed at initialization): `init_decomp_cascade_constants` allocates, then either `init_decompcascade_bgc` or `init_decompcascade_cn` populates the pool/transition structure and initial C:N, C:P ratios.
2. **Rate constants** (every time step): `decomp_rate_constants_bgc` or `_cn` computes `decomp_k(c,j,l) = base_k(l) * t_scalar(c,j) * w_scalar(c,j) * o_scalar(c,j) * depth_scalar(j) * spinup_factor(l)`.
3. **Vertical profiles** (every time step, pre-decomposition): `decomp_vertprofiles` updates `leaf_prof`, `froot_prof`, `ndep_prof`, `pdep_prof`, `nfixation_prof`.
4. **Potential decomposition + competition** (`SoilLittDecompAlloc`): compute potential C loss, immobilization demand, gross mineralization, call `Allocation2_ResolveNPLimit`.
5. **Actual decomposition + plant allocation** (`SoilLittDecompAlloc2`): apply the resolved `fpi_*`, `fpg_*` factors, emit actual transfers along the cascade, call `Allocation3_PlantCNPAlloc`.
6. **Vertical mixing** (`SoilLittVertTransp`): advection-diffusion tridiagonal solver moves C, N, P, isotopes between decomposition layers.

When FATES is active, the decomposition and vertical transport still run as described above on the column-level soil BGC pools. FATES delivers fragmented litter (leaf, fine root, stem) via `main/ELMFatesInterfaceMod.F90`, and the CWD pool in the ELM cascade is kept at zero because FATES manages coarse woody debris internally (comment at `DecompCascadeBGCMod.F90:464`). PFLOTRAN coupling (`use_pflotran .and. pf_cmode`) bypasses this decomposition driver entirely for soil organic C/N transport and uses the `decomp_cpools_sourcesink_col` / `bgc_cpool_ext_inputs_vr_col` channels to communicate sources and sinks between ELM and PFLOTRAN.
