---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Gas and Particle Emissions, Dry Deposition, and Erosion

This document covers five biogeochemistry modules that handle mass exchange
with the atmosphere (outside the standard CO2/H2O coupling) and one module
that moves C, N, and P laterally through soil erosion:

| File | What it does | Always on? |
|---|---|---|
| `biogeochem/DUSTMod.F90` | Wind-driven dust mobilization and turbulent dry deposition for dust. | On whenever `ndst > 0` at build time. |
| `biogeochem/VOCEmissionMod.F90` | BVOC emissions via MEGAN 2.1 (isoprene + 19 other compound classes). | Only when `shr_megan_mechcomps_n >= 1`. |
| `biogeochem/DryDepVelocity.F90` | Wesely-scheme dry-deposition velocity for a configurable list of chemical species. | Only when `n_drydep > 0`. |
| `biogeochem/MEGANFactorsMod.F90` | Read and hash-lookup MEGAN emission factors per compound and per PFT. | Called from `VOCEmission`. |
| `biogeochem/ErosionMod.F90` | Erosion-induced C, N, and P fluxes (vertically resolved). | Only when `ero_ccycle = .true.`. |

None of these modules depend on `use_fates` or `use_cn`; they all run on the
patch or column level and read inputs from canopy, atmosphere forcing, and
(for erosion) sediment flux from the hydrology subsystem.

## Where they are called

At d40b8431, the four atmospheric-exchange routines are dispatched from
`main/elm_driver.F90` (not from `EcosystemDynMod.F90`):

```
elm_driver.F90:833    call DustEmission(...)
elm_driver.F90:839    call DustDryDep(...)
elm_driver.F90:844    call VOCEmission(...)               ! if shr_megan_mechcomps_n >= 1
elm_driver.F90:1179   call depvel_compute(...)            ! drydep, gated by n_drydep
elm_driver.F90:1223   call depvel_compute(...)            ! second-pass for FATES-SP
```

Erosion is dispatched from the BGC driver:

```
EcosystemDynMod.F90:820-822
   if ( ero_ccycle ) then
      call t_startf('ErosionFluxes')
      call ErosionFluxes(bounds, num_soilc, filter_soilc, soilstate_vars, sedflux_vars )
      call t_stopf('ErosionFluxes')
   end if
```

`WoodProducts` (`EcosystemDynMod.F90:796/813`) and
`CropHarvestPools` (`:798/815`) live in `mortality.md` and `crops.md`
respectively.

---

## `DUSTMod.F90` -- dust emission and dry deposition

### Reference

The core emission scheme is Zender's DEAD model (Zender et al. 2003) with the
Kok et al. (2014) physically based parameterization layered on top. Both are
present and selected at run time via `dust_emis_scheme` (held in
`shr_dust_mod`):

- `dust_emis_scheme = 1` -- original Zender DEAD with `flx_mss_fdg_fct = 5.0e-4`
  tuning factor.
- `dust_emis_scheme = 2` -- Kok et al. 2014 with `Cd0 = 4.4e-5`, `Ca = 2.7`,
  `Ce = 2.0`, `C_tune = 0.05`.

### `dust_type`

Container at `biogeochem/DUSTMod.F90:63` holding per-patch arrays:

- `flx_mss_vrt_dst_patch(p, 1:ndst)` -- vertical dust emission by size bin
  (kg/m^2/s), public.
- `flx_mss_vrt_dst_tot_patch(p)` -- total dust flux.
- `vlc_trb_patch(p, 1:ndst)` and `vlc_trb_[1-4]_patch(p)` -- turbulent
  dry-deposition velocities per bin (m/s).
- `mbl_bsn_fct_col(c)` -- basin factor.
- `lnd_frc_mbl_patch(p)` (`:72`, private) -- land fraction for dust
  mobilization. **At d40b8431, this gained an explicit history field
  `LND_FRC_DUST_MBL`** (registered at `DUSTMod.F90:173`); it is otherwise
  unchanged in semantics.

### `DustEmission` (`biogeochem/DUSTMod.F90:203`)

For every non-lake patch, compute surface dust emission flux from local wind
friction velocity `fv`, 10 m wind `u10`, soil texture (`mss_frc_cly_vld_col`),
soil moisture (`h2osoi_vol`), snow cover (`frac_sno`), and LAI+SAI (canopy
quenching test, `vai_mbl_thr = 0.3`):

1. Sum LAI+SAI across the patch's landunit to get `tlai_lu`.
2. Compute gravimetric soil moisture at the surface (`gwc_sfc`) from
   `h2osoi_liq + h2osoi_ice` and compare to clay-dependent threshold
   `gwc_thr` -> wet-soil factor `frc_thr_wet_fct`.
3. Compute surface-roughness factor `frc_thr_rgh_fct`.
4. Compute threshold friction velocity `wnd_frc_thr_slt` and horizontal mass
   flux. In Kok 2014 mode, threshold is first standardized to reference air
   density (`forc_rho_std = 1.225 kg/m^3`).
5. Apply mobilization thresholds: emission zero if friction velocity below
   threshold, if `lnd_frc_mbl` is zero, or if snow covers the surface.
6. Distribute total vertical flux into `ndst` size bins using
   `ovr_src_snk_mss`.

### `DustDryDep` (`:539`)

Computes turbulent dry-deposition velocity for each dust size bin through the
lowest atmospheric layer. Molecular diffusivity, gravity settling, Stokes
correction (`stk_crc`, `dns_aer`); gravity settling through the rest of the
column is the atmosphere's responsibility. Output `vlc_trb_patch(p, 1:ndst)`
passed up via `lnd2atm_vars`.

### History fields at d40b8431

`InitHistory` (`:131-177`) registers the public dust history variables:

- `DSTFLXT` (`:148`)
- `DPVLTRB1`, `DPVLTRB2`, `DPVLTRB3`, `DPVLTRB4` (`:153-168`)
- `LND_FRC_DUST_MBL` (`:173`) — NEW at d40b8431

### Always-on behavior

There is no namelist flag that turns DUSTMod off inside ELM. If `ndst = 0` in
the build, the routines effectively do nothing because all per-bin arrays are
zero-sized.

---

## `VOCEmissionMod.F90` -- BVOC emissions (MEGAN)

### Reference and compound set

Implementation follows Guenther et al. 2006 (isoprene) and its MEGAN 2.1
generalization to 20 compound classes. Canonical equation:

```
E = epsilon * gamma * rho
```

`epsilon` is a PFT-and-compound-specific emission factor (ug/m^2/hr), `gamma`
is the activity factor (light, temperature, LAI, leaf-age, soil-moisture
factors), `rho = 1`.

### `vocemis_type` state

(`biogeochem/VOCEmissionMod.F90:48-74`) Holds diagnostic coefficients
(`Eopt_out`, `topt_out`, `alpha_out`, `cp_out`), PPFD history arrays
(`paru_out`, `par24u_out`, `par240u_out`, shaded analogs), gamma factors
(`gamma_out`, `gammaL_out`, `gammaT_out`, `gammaP_out`, `gammaA_out`,
`gammaS_out`, `gammaC_out`), and outputs:

- `vocflx_patch(p, num_mech_comps)` -- per-mechanism-component flux in
  moles/m^2/s (public).
- `vocflx_tot_patch(p)` -- total VOC flux.
- `efisop_grc(g, ...)` -- gridcell isoprene emission factors.

### `VOCEmission` (`:371`)

Loops over soil patches:

1. Returns immediately if `shr_megan_mechcomps_n < 1`.
2. Requires `nlevcan == 1` (multi-level canopy not supported).
3. For each mechanism component mapping to a MEGAN compound, reads the
   per-PFT emission factor `epsilon`. For isoprene only, if
   `shr_megan_mapped_emisfctrs = .true.`, uses the gridcell-mapped
   `efisop_grc` instead of the PFT-constant table.
4. Computes the five activity factors (`gamma_p`, `gamma_l`, `gamma_t`,
   `gamma_a`, `gamma_sm`, `gamma_c`).
5. Multiplies to form total `gamma`, then `epsilon * gamma`, converts to
   moles/m^2/s via `megemis_units_factor = 1/3600/1e6` and the molecular
   weight.
6. Accumulates into `vocflx_patch(p, imech)` and `vocflx_tot_patch(p)`.

### `MEGANFactorsMod.F90`

Lookup table consumed by `VOCEmission`:

- `megan_factors_init(filename)` (`:84-201`) reads the MEGAN emission factors
  file, populates a hash table indexed by compound name, fills per-PFT arrays
  `Agro`, `Amat`, `Anew`, `Aold`, `betaT`, `ct1`, `ct2`, `LDF`, `Ceo`.
- `megan_factors_get(comp_name, factors, class_n, molecwght)` (`:52-81`)
  returns per-PFT emission-factor vector, MEGAN class number, molecular
  weight. Uses `gen_hashkey` into `hash_table_indices(1:2**16)`.

### Gating

`VOCEmission` is called unconditionally from the driver, but short-circuits
when `shr_megan_mechcomps_n < 1`. The mechanism components and MEGAN mapping
come from the atmosphere component's MEGAN namelist.

---

## `DryDepVelocity.F90` -- Wesely dry-deposition velocities

Based on Wesely 1989 with modifications from Vitt 2007:

```
|vd| = (ra + rb + rc)^-1
```

`ra` (aerodynamic) and `rb` (quasilaminar sublayer) come from earlier ELM
parts; `rc` (bulk surface) is the main output here.

### `drydepvel_type` state

- `velocity_patch(p, n_drydep)` -- dry-deposition velocity per species (m/s),
  public.

The `Init` method aborts if FATES is active outside of FATES-SP mode -- Wesely
deposition needs surface-aggregated canopy state not exposed through FATES.

### `depvel_compute` (`biogeochem/DryDepVelocity.F90:134-616`)

For each species in `drydep_list` (built-in indices: O3, SO2, H2, CO, CH4,
PAN, X-PAN), looks up Wesely parameters by species and current land-use
category and computes `rc` combining surface water resistance, mesophyllic
resistance (Henry's-law and reactivity), cuticle resistance, ground-to-canopy
resistance, and canopy-adjusted stomatal resistance via `rs` from
`photosyns_type`.

Recognized named indices from `seq_drydep_mod`: `index_o3`, `index_o3a`,
`index_so2`, `index_h2`, `index_co`, `index_ch4`, `index_pan`, `index_xpan`.

### Gating

The driver call is wrapped in `n_drydep > 0` and `drydep_method == DD_XLND`.
`n_drydep` is populated from the atmosphere coupler.

---

## `ErosionMod.F90` -- erosion-driven C / N / P fluxes

### Scope

`ErosionFluxes(bounds, num_soilc, filter_soilc, soilstate_vars, sedflux_vars)`
(`biogeochem/ErosionMod.F90:31-497`) translates sediment detachment and yield
rates (`sed_ero_col`, `sed_yld_col` from `SedFluxType`) into corresponding
C, N, and P fluxes from every decomposition pool in every soil layer, plus
the four mineral-P pools (`labilep_vr`, `secondp_vr`, `occlp_vr`, `primp_vr`).
Supports both detachment (`*_erode`, vertically integrated) and redeposition
on the hillslope (`*_deposit`).

### Per-pool outputs

For each decomposition pool index `k` and soil layer `j`:

- `cpools_erode(c, k)` -- gC/m^2/s detachment.
- `cpools_deposit(c, k)` -- gC/m^2/s redeposition.
- `cpools_yield_vr(c, j, k)` -- gC/m^3/s loss from layer `j`.

Same for `npools_*` and `ppools_*`. For the four mineral-P pools, outputs
are `labilep_erode`, `labilep_deposit`, `labilep_yield_vr`, etc.

### Algorithm

For each column with `flx_sed_ero > 0`:

1. Convert total detachment rate to a surface-layer depth removed `dh` using
   bulk density.
2. Walk top-down through soil layers, cutting pool mass proportional to
   removed depth versus layer thickness, until full `dh` is accounted for.
3. Total detached mass split into eroded portion (`*_erode`, off-column) and
   redeposited (`*_deposit`, on-column down-slope) per the sediment delivery
   ratio from `SedFluxType`.
4. New pool values written back into `decomp_cpools_vr`, `decomp_npools_vr`,
   `decomp_ppools_vr`, and the four mineral-P `*_vr` arrays.

The routine does not apply erosion to live-vegetation pools, only to
decomposition and mineral-P pools.

### Gating

`ErosionFluxes` is invoked only when `ero_ccycle = .true.`. `ero_ccycle` is
itself only valid when `use_erosion = .true.`. Both default to `.false.`.

---

## Summary of always-on vs gated

| Module | Default | Gate |
|---|---|---|
| DustEmission | on (if `ndst > 0` in build) | `dust_emis_scheme` selects Zender vs Kok; no namelist off-switch. |
| DustDryDep | on | same. |
| VOCEmission | on | Self-gated on `shr_megan_mechcomps_n >= 1`. |
| depvel_compute | off by default | Requires `n_drydep > 0` and `drydep_method == DD_XLND`. |
| ErosionFluxes | off by default | Requires `ero_ccycle = .true.` (and `use_erosion = .true.`). |

## Data flow to and from the atmosphere

- Dust: `flx_mss_vrt_dst_patch` -> `lnd2atm_vars%flxdst`; dry deposition
  velocities -> `lnd2atm_vars%ddvel` per bin.
- BVOCs: `vocflx_patch(:, :)` -> `lnd2atm_vars`; picked up by atmospheric
  chemistry in EAM via the MEGAN mechanism mapping.
- Dry deposition velocities: `velocity_patch(:, :)` -> `lnd2atm_vars%ddvel`.
- Erosion: fluxes written into `col_cf`/`col_nf`/`col_pf`; remain within ELM
  C, N, and P budgets (not sent to the atmosphere).

## What's missing from this subsystem

- Biomass-burning emissions are handled by `FireMod.F90` (CN-fire) or FATES
  SPITFIRE -- see `fire.md`.
- Sea-salt, black carbon, and organic carbon aerosol fluxes are not computed
  by ELM.
- Ammonia emissions from agriculture (FAN) are handled in `FanMod.F90` /
  `FanUpdateMod.F90` (see `nitrogen.md`) and routed through the nitrogen
  cycle, not through `DryDepVelocity`.
