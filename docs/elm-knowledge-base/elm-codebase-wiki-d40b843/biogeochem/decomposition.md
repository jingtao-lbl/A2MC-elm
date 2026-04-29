---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Decomposition Cascade and Vertical Soil BGC

ELM represents soil organic matter (SOM) turnover as a cascade of donor ->
receiver transitions among a small number of pools, with vertical resolution
over `nlevdecomp` layers and a tridiagonal solver for vertical mixing (bio-
and cryo-turbation). This page covers the cascade definition
(`biogeochem/CNDecompCascadeConType.F90`), the two alternative
parameterizations (CENTURY/BGC and CN), the main decomposition driver
(`biogeochem/SoilLittDecompMod.F90`), and the vertical transport
(`biogeochem/SoilLittVertTranspMod.F90`).

## Cascade Topology

The cascade topology is stored in the module-global type `decomp_cascade_con`
declared in `biogeochem/CNDecompCascadeConType.F90:20`. Its fields describe
per-transition and per-pool properties:

```fortran
type :: decomp_cascade_type
   ! per-transition:
   character(len=8),  pointer :: cascade_step_name(:)
   integer,           pointer :: cascade_donor_pool(:)
   integer,           pointer :: cascade_receiver_pool(:)
   ! per-pool:
   logical,           pointer :: floating_cn_ratio_decomp_pools(:)
   logical,           pointer :: floating_cp_ratio_decomp_pools(:)
   character(len=8),  pointer :: decomp_pool_name_restart(:)
   character(len=8),  pointer :: decomp_pool_name_history(:)
   character(len=20), pointer :: decomp_pool_name_long(:)
   character(len=8),  pointer :: decomp_pool_name_short(:)
   logical,           pointer :: is_litter(:)
   logical,           pointer :: is_soil(:)
   logical,           pointer :: is_cwd(:)
   real(r8),          pointer :: initial_cn_ratio(:)
   real(r8),          pointer :: initial_cp_ratio(:)
   real(r8),          pointer :: initial_stock(:)
   logical,           pointer :: is_metabolic(:)
   logical,           pointer :: is_cellulose(:)
   logical,           pointer :: is_lignin(:)
   real(r8),          pointer :: spinup_factor(:)
   real(r8),          pointer :: decomp_k_pools(:)
end type
```

`init_decomp_cascade_constants` (`CNDecompCascadeConType.F90:52`) allocates
these arrays over `0:ndecomp_pools` and `1:ndecomp_cascade_transitions`. The
content is filled by either `DecompCascadeBGCMod%init_decompcascade_bgc`
(`DecompCascadeBGCMod.F90:276`) or `DecompCascadeCNMod%init_decompcascade_cn`
(`DecompCascadeCNMod.F90:294`), selected by the `use_century_decomp` flag in
`elm_varctl`.

## BGC / CENTURY Parameterization (default)

`biogeochem/DecompCascadeBGCMod.F90` implements the CENTURY/BGC parameterization
with 3 SOM pools, 3 litter pools, and 1 CWD pool (total `ndecomp_pools = 7`),
and 10 transitions. The parameters are stored in `DecompBGCParamsInst` (type
`DecompBGCParamsType`, declared near line 47), read from the NetCDF parameter
file by `readDecompBGCParams` (`:98`).

| Parameter group | Fields |
|---|---|
| C:N of SOM | `cn_s1_bgc`, `cn_s2_bgc`, `cn_s3_bgc` |
| N:P of SOM (new) | `np_s1_new_bgc`, `np_s2_new_bgc`, `np_s3_new_bgc` |
| C:P of SOM (new) | `cp_s1_new_bgc`, `cp_s2_new_bgc`, `cp_s3_new_bgc` |
| Respiration fractions | `rf_l1s1_bgc`, `rf_l2s1_bgc`, `rf_l3s2_bgc`, `rf_s2s1_bgc`, `rf_s2s3_bgc`, `rf_s3s1_bgc`, `rf_cwdl2_bgc`, `rf_cwdl3_bgc` |
| Turnover times (years) | `tau_l1_bgc`, `tau_l2_l3_bgc`, `tau_s1_bgc`, `tau_s2_bgc`, `tau_s3_bgc`, `tau_cwd_bgc` |
| CWD fractions | `cwd_fcel_bgc`, `cwd_flig_bgc` |
| Water potential | `minpsi_bgc` (loaded from netCDF; the in-source override is `-10.0_r8` at `:867`) |
| Fragmentation | `k_frag_bgc` (CWD fragmentation rate) |
| AD spinup | `nsompools = 3`, `spinup_vector` |

### CRITICAL: minpsi reverted to -10.0_r8 at d40b8431

`init_decompcascade_bgc` (`:276-628`) populates `decomp_cascade_con` and sets
the in-source moisture-limit floor at `:867`:

```fortran
minpsi = -10.0_r8;
```

In 60d9aad this was `minpsi = -1000.0_r8 !TJ` (a debug override). The d40b8431
revert restores the upstream default. The corresponding line in
`DecompCascadeCNMod.F90:964` is also `-10.0_r8`. **This changes the moisture
scalar `w_scalar(c,j)` for soil heterotrophic respiration in every BGC and CN
simulation.** Models calibrated against a 60d9aad code base that left this
override in place will see substantially stronger moisture limitation under
d40b8431.

### Pool Indices and Attributes

`init_decompcascade_bgc` populates the `decomp_cascade_con` arrays. The pool
indices (set in `:413-538`):

| idx | Name | Short | Long name | Kind | `is_cellulose` | `is_lignin` | `is_metabolic` | Floating C:N | Initial C:N | Initial stock |
|---|---|---|---|---|---|---|---|---|---|---|
| `i_litr1 = i_met_lit` | litr1 | L1 | litter 1 | litter | F | F | **T** | T | 90 | 0 |
| `i_litr2 = i_cel_lit` | litr2 | L2 | litter 2 | litter | **T** | F | F | T | 90 | 0 |
| `i_litr3 = i_lig_lit` | litr3 | L3 | litter 3 | litter | F | **T** | F | T | 90 | 0 |
| `i_cwd = 4`   | cwd   | CWD | coarse woody debris | CWD | F | F | F | T | 90 | 0 |
| `i_soil1 = 5` | soil1 | S1  | soil 1 | SOM | F | F | F | F | `cn_s1` | 20 |
| `i_soil2 = 6` | soil2 | S2  | soil 2 | SOM | F | F | F | F | `cn_s2` | 20 |
| `i_soil3 = 7` | soil3 | S3  | soil 3 | SOM | F | F | F | F | `cn_s3` | 20 |

A note in `DecompCascadeBGCMod.F90` explains that when FATES is active, the CWD
pool stays at zero because FATES does its own CWD bookkeeping and only delivers
already-fragmented litter to ELM (via `alm_fates%UpdateLitterFluxes` —
see `cnp_state_and_fluxes.md`).

### Cascade Transitions (BGC/CENTURY)

Each transition has a respiration fraction `rf` (fraction of donor C released
as CO2 during the transition) and a path fraction `pathfrac` (fraction of
outgoing C that flows through this transition):

| `i_*` | Step | Donor | Receiver | `rf` | `pathfrac` |
|---|---|---|---|---|---|
| 1 | L1S1 | litr1 | soil1 | `rf_l1s1` | 1.0 |
| 2 | L2S1 | litr2 | soil1 | `rf_l2s1` | 1.0 |
| 3 | L3S2 | litr3 | soil2 | `rf_l3s2` | 1.0 |
| 4 | S1S2 | soil1 | soil2 | `rf_s1s2(c,j)` (depth dependent on sand) | `f_s1s2 = 1 - .004/(1-t)` |
| 5 | S1S3 | soil1 | soil3 | `rf_s1s3(c,j)` | `f_s1s3 = .004/(1-t)` |
| 6 | S2S1 | soil2 | soil1 | `rf_s2s1` | `f_s2s1 = 0.42/0.45` |
| 7 | S2S3 | soil2 | soil3 | `rf_s2s3` | `f_s2s3 = 0.03/0.45` |
| 8 | S3S1 | soil3 | soil1 | `rf_s3s1` | 1.0 |
| 9 | CWDL2 | cwd  | litr2 | `rf_cwdl2` | `cwd_fcel` |
| 10 | CWDL3 | cwd | litr3 | `rf_cwdl3` | `cwd_flig` |

where `t = 0.85 - 0.68 * 0.01 * (100 - cellsand(c,j))` scales the SOM1
respiration fraction and the S1S2/S1S3 split with soil texture.

### Rate Constants (BGC/CENTURY)

`decomp_rate_constants_bgc` (`:631-1111`) computes `decomp_k(c,j,l)` (1/s) per
level from:

- Base turnover times (hardcoded for bit-for-bit reproducibility):
  ```
  tau_l1    = 1./18.5       (yr)
  tau_l2_l3 = 1./4.9        (yr)
  tau_s1    = 1./7.3        (yr)
  tau_s2    = 1./0.2        (yr)
  tau_s3    = 1./.0045      (yr)
  tau_cwd   = 1./0.3        (yr)
  ```
- Temperature scalar `t_scalar(c,j)`: Q10 from `ParamsShareInst%Q10_hr`,
  reference `T0 = 15 C`, frozen Q10 `froz_q10`. Optional CENTURY temperature
  function `catanf(t1) = 11.75 + (29.7/pi) * atan(pi * 0.031 * (t1 - 15.4))`
  if `use_century_tfunc = .true.`.
- **Moisture scalar** `w_scalar(c,j)`: `log(minpsi/soilpsi)/log(minpsi/maxpsi)`
  clipped to `[0, 1]`. **At d40b8431 the in-source `minpsi = -10.0_r8`** (see
  warning above).
- Oxygen scalar `o_scalar(c,j)`: anoxia limitation from CH4 module
  (`ch4_vars%o2stress_sat`, `o2stress_unsat`, `finundated`), floored at
  `ParamsShareInst%mino2lim` when `anoxia = .true.` and `use_lch4 = .true.`.
- Depth scalar `depth_scalar(c,j) = exp(-zsoi(j)/decomp_depth_efolding)`.
- AD spinup factor per SOM pool: `spinup_factor(i_soil{1,2,3})` from
  `DecompBGCParamsInst%spinup_vector`.

The final rate is `decomp_k(c,j,l) = base_k * t_scalar * w_scalar * o_scalar
* depth_scalar * spinup_factor(l)`.

## CN Parameterization (alternative)

`biogeochem/DecompCascadeCNMod.F90` implements the original CLMCN 4.0 cascade
with 4 SOM pools (S1..S4), 3 litter pools, and 1 CWD pool (total
`ndecomp_pools = 8`). Parameters in `DecompCNParamsInst` (type
`DecompCNParamsType`):

- C:N for SOM1..SOM4, N:P and C:P for SOM1..SOM4 (new).
- Respiration fractions: `rf_l1s1_cn`, `rf_l2s2_cn`, `rf_l3s3_cn`, `rf_s1s2_cn`,
  `rf_s2s3_cn`, `rf_s3s4_cn`.
- Decomposition rate constants: `k_l1_cn`, `k_l2_cn`, `k_l3_cn`, `k_s1_cn`,
  `k_s2_cn`, `k_s3_cn`, `k_s4_cn`, `k_frag_cn`.
- CWD fractions `cwd_fcel_cn`, `cwd_flig_cn`, `minpsi_cn`.
- Pool counts: `nsompools = 4`, `nlitpools = 3`, `ncwdpools = 1`.
- AD spinup multipliers: `spinup_vector(4)`.

`decomp_rate_constants_cn` is at `:626-1077`. The `minpsi` in-source override
at `:964` is also `-10.0_r8` at d40b8431 (same revert as BGC). Select this
path by setting `use_century_decomp = .false.`.

## SoilLittDecompMod (Main Decomposition Driver)

`biogeochem/SoilLittDecompMod.F90` is the primary driver for soil BGC. Two
public routines form the decomposition call sequence:

- `SoilLittDecompAlloc` (`:92-562`): potential decomposition fluxes and N/P
  competition resolution.
- `SoilLittDecompAlloc2` (`:566-809`): final CNP allocation and vertical
  integration of mineralization fluxes.

### SoilLittDecompAlloc (phase-1)

Computes, for each transition `k`:

1. `p_decomp_cpool_loss(c,j,k) = decomp_cpools_vr(c,j,donor) *
   decomp_k(c,j,donor) * pathfrac_decomp_cascade(c,j,k)` (potential C loss).
2. Partition the C flux into:
   - Respiration: `rf_decomp_cascade(c,j,k) * p_decomp_cpool_loss(c,j,k)`
     (released as CO2, `phr_vr_col`).
   - Transfer to receiver: `(1 - rf_decomp_cascade) * p_decomp_cpool_loss`.
3. N and P demand of each transition: `pmnf_decomp_cascade(c,j,k) =
   C_transfer * (1/cn_receiver - (1-rf)/cn_donor)`. Positive => immobilization,
   negative => gross mineralization.
4. Sum positive pmnf across transitions to `potential_immob_vr_col`; sum
   negative to `gross_nmin_vr_col`. Same for P via `pmpf_decomp_cascade`,
   `potential_immob_p_vr_col`, `gross_pmin_vr_col`.
5. Call `Allocation2_ResolveNPLimit` to compute `fpi_vr_col`, `fpi_col`,
   `fpg_col`, `fpi_p_vr_col`, `fpg_p_col`, `actual_immob_vr_col`,
   `sminn_to_plant_vr_col`.
6. Call `nitrif_denitrif`, which computes `f_nit_vr_col`, `f_denit_vr_col`
   that remove NH4/NO3 from the mineral N pool.

### SoilLittDecompAlloc2 (phase-2)

Takes `fpi_vr_col` and `fpi_p_vr_col`, scales each cascade transition's C flux
by these factors, and writes `decomp_cascade_hr_vr_col`,
`decomp_cascade_ctransfer_vr_col`, `decomp_cascade_ntransfer_vr_col`,
`decomp_cascade_ptransfer_vr_col`, `soil_n_immob_flux`, `soil_p_immob_flux`,
and the vertically integrated `gross_nmin`, `net_nmin`, `gross_pmin`,
`net_pmin` in `col_nf` and `col_pf`.

**Then dispatches the final allocation** at `:758-772` based on `nu_com`:

```fortran
if(.not.use_fates)then
  if(nu_com .eq. 'RD') then
     call PlantCNPAlloc_RD(...)
  else
     call PlantCNPAlloc_ECAMIC(...)
  endif
end if
```

This is the central refactor described in `allocation_and_respiration.md`.
The legacy `Allocation3_PlantCNPAlloc` no longer exists in the default path.

### readSoilLittDecompParams

Reads `CNDecompParamsInst%dnp` (denitrification proportion) for the
non-nitrif_denitrif legacy path.

## VerticalProfileMod

`biogeochem/VerticalProfileMod.F90` computes the vertical distributions used to
convert surface fluxes into vertically resolved column fluxes. Single public
routine `decomp_vertprofiles`. Two mode switches:

- `exponential_rooting_profile = .true.` (default): exponential
  `exp(-rootprof_exp * zsoi(j))` for root inputs.
- `pftspecific_rootingprofile = .true.` (default): PFT-specific Jackson beta
  distribution: `rootprof_beta(ivt)^(zisoi(j-1)*100) -
  rootprof_beta(ivt)^(zisoi(j)*100)`.

Computed profiles per patch (`leaf_prof_patch`, `froot_prof_patch`,
`stem_prof_patch`, `croot_prof_patch`) and per column (`nfixation_prof_col`,
`ndep_prof_col`, `pdep_prof_col`) integrate to unity over the active layer. The
active layer depth comes from `altmax_lastyear_indx_col` (permafrost-aware).

For FATES columns, N fixation, N deposition, and P deposition profiles use the
surface profile only (no root profile) since FATES handles rooting internally.

When `use_vertsoilc = .false.`, all profiles are unity (single-layer mode).

## SoilLittVertTranspMod

`biogeochem/SoilLittVertTranspMod.F90` solves vertical mixing of decomposing
pools using a Patankar (1980) tridiagonal scheme. **At d40b8431, this module
was promoted to expose more of its internals as `public`** so callers can
register new tracers in the transport list:

```fortran
public :: SoilLittVertTransp
public :: createLitterTransportList
public :: readSoilLittVertTranspParams

type, public :: SoilLittVertTranspParamsType   ! was private in 60d9aad
   ...
end type SoilLittVertTranspParamsType
type(SoilLittVertTranspParamsType), public :: SoilLittVertTranspParamsInst

type, public :: ConcTransportType              ! NEW at d40b8431
   real(r8), pointer :: conc_ptr(:,:,:)        => null()
   real(r8), pointer :: src_ptr(:,:,:)         => null()
   real(r8), pointer :: trcr_tend_ptr(:,:,:)   => null()
end type ConcTransportType
type(ConcTransportType), public, allocatable :: transport_ptr_list(:)
```

`createLitterTransportList()` (`:56-110`) builds the per-tracer pointer table
once at init, registering one entry per active tracer:

| Index | conc_ptr | src_ptr | trcr_tend_ptr |
|---|---|---|---|
| 1 | `col_cs%decomp_cpools_vr` | `col_cf%decomp_cpools_sourcesink` | `col_cf%decomp_cpools_transport_tendency` |
| 2 | `col_ns%decomp_npools_vr` | `col_nf%decomp_npools_sourcesink` | `col_nf%decomp_npools_transport_tendency` |
| 3 | `col_ps%decomp_ppools_vr` | `col_pf%decomp_ppools_sourcesink` | `col_pf%decomp_ppools_transport_tendency` |
| 4 (if `use_c13`) | `c13_col_cs%decomp_cpools_vr` | `c13_col_cf%decomp_cpools_sourcesink` | `c13_col_cf%decomp_cpools_transport_tendency` |
| 5 (if `use_c14`) | `c14_col_cs%decomp_cpools_vr` | `c14_col_cf%decomp_cpools_sourcesink` | `c14_col_cf%decomp_cpools_transport_tendency` |

The driver loop in `SoilLittVertTransp` dereferences via
`transport_ptr_list(i_type)%conc_ptr(c,j,s)` etc. (`:323, 345, 372, 407, 421,
462, 477, 490, 505, 506`). The previous hardcoded sequence of pool transports
is gone.

### Parameters

- `som_diffus`: SOM diffusion. Hardcoded module-level default
  `1e-4 / (secspday * 365)` m^2/s = 1 cm^2/yr.
- `cryoturb_diffusion_k`: cryoturbation diffusion. Hardcoded default
  `5e-4 / (secspday * 365)` m^2/s = 5 cm^2/yr = 1 m^2 / 200 yr.
- `max_altdepth_cryoturbation`: max active-layer thickness for cryoturbation.

Module-level constants:
- `som_adv_flux = 0._r8` (no advection; supported but disabled).
- `max_depth_cryoturb = 3._r8` m.

### Algorithm

For each time step, for each vertically resolved tracer index `i_type`:

1. Compute effective diffusivity per layer interface `diffus(c,j+1)`. In
   cryoturbation columns, `diffus = cryoturb_diffusion_k`, linearly tapered
   to `som_diffus` below the active layer and to zero at `max_depth_cryoturb`.
2. Compute advective flux `adv_flux` (zero by default).
3. Build tridiagonal matrix `a_tri`, `b_tri`, `c_tri`, `r_tri` using the "A"
   function from Patankar 1980.
4. Call `Tridiagonal` from `TridiagonalMod`.
5. Store the tendency in
   `transport_ptr_list(i_type)%trcr_tend_ptr(c,j,s)` for history output and for
   use by the next time step's source-sink term.

During AD spinup (`spinup_state /= 0`), vertical transport rates are
accelerated by `spinup_factor` of each pool.

## Summary

The decomposition pipeline:

1. **Cascade topology** (init): `init_decomp_cascade_constants` allocates,
   then `init_decompcascade_bgc` (`:276`) or `init_decompcascade_cn`
   (`:294`) populates the pool/transition structure and initial C:N, C:P ratios.
2. **Rate constants** (every step): `decomp_rate_constants_bgc` (`:631`) or
   `_cn` (`:626`) computes `decomp_k(c,j,l)`. **`minpsi = -10.0_r8`** at
   d40b8431.
3. **Vertical profiles** (every step, pre-decomposition): `decomp_vertprofiles`
   updates `leaf_prof`, `froot_prof`, `ndep_prof`, `pdep_prof`,
   `nfixation_prof`.
4. **Potential decomposition + competition** (`SoilLittDecompAlloc:92`):
   compute potential C loss, immobilization demand, gross mineralization,
   call `Allocation2_ResolveNPLimit`, call `nitrif_denitrif`.
5. **Actual decomposition + plant allocation** (`SoilLittDecompAlloc2:566`):
   apply resolved `fpi_*`, `fpg_*`, emit cascade transfers, dispatch on
   `nu_com` to call either `PlantCNPAlloc_RD` or `PlantCNPAlloc_ECAMIC`.
6. **Vertical mixing** (`SoilLittVertTransp`): tridiagonal solver iterates over
   the registered `transport_ptr_list` tracers (C, N, P, optionally C13/C14).

When FATES is active, the decomposition and vertical transport still run as
described above on the column-level soil BGC pools. FATES delivers fragmented
litter (leaf, fine root, stem) via `alm_fates%UpdateLitterFluxes`
(`elmfates_interfaceMod.F90:1423`), called from `EcosystemDynNoLeaching2:689`
inside the `if(use_fates)` block. The CWD pool in the ELM cascade stays at zero
because FATES manages CWD internally.

PFLOTRAN coupling (`use_pflotran .and. pf_cmode`) bypasses this decomposition
driver entirely for soil organic C/N transport.
