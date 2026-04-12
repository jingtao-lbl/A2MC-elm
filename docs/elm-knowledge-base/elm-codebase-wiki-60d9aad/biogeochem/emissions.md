---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Gas and particle emissions, dry deposition, and erosion

This document covers five biogeochemistry modules that handle mass exchange
with the atmosphere (outside the standard CO2/H2O coupling) and one module
that moves C, N, and P laterally through soil erosion:

| File | What it does | Always on? |
|---|---|---|
| `biogeochem/DUSTMod.F90` | Wind-driven dust mobilization and turbulent dry deposition for dust. | On whenever `ndst > 0` at build time (always called from the driver; does nothing when no dust bins are requested). |
| `biogeochem/VOCEmissionMod.F90` | BVOC emissions via MEGAN 2.1 (isoprene and 19 other compound classes). | Only when `shr_megan_mechcomps_n >= 1`; built from the atmosphere component's MEGAN namelist. |
| `biogeochem/DryDepVelocity.F90` | Wesely-scheme dry-deposition velocity for a configurable list of chemical species. | Only when `n_drydep > 0` (from `seq_drydep_mod`). |
| `biogeochem/MEGANFactorsMod.F90` | Read and hash-lookup MEGAN emission factors per compound and per PFT. | Called from `VOCEmission` only. |
| `biogeochem/ErosionMod.F90` | Erosion-induced C, N, and P fluxes (vertically resolved). | Only when `ero_ccycle = .true.` (requires `use_erosion = .true.`). |

None of these modules depend on `use_fates` or `use_cn`; they all run on the
patch or column level and read their inputs from the canopy, atmosphere
forcing, and (for erosion) the sediment flux driver in the hydrology
subsystem. They are effectively orthogonal to the vegetation-dynamics
backend.

## Where they are called

From `biogeochem/EcosystemDynMod.F90`:

```
call DustEmission(...)         (line 817)
call DustDryDep(...)           (line 823)
call VOCEmission(...)          (line 828)    ! if shr_megan_mechcomps_n >= 1
call WoodProducts(...)         (line 835)
call CropHarvestPools(...)     (line 837)
if (ero_ccycle) then
   call ErosionFluxes(...)     (line 844)
end if
call depvel_compute(...)       (line 1160 / 1204, from a later driver section)
```

So on every time step, `DustEmission`, `DustDryDep`, `VOCEmission`, and
`depvel_compute` are invoked unconditionally from the driver, and the
modules self-gate internally when their respective species lists are empty.
`ErosionFluxes` is the only one wrapped in a namelist flag.

---

## `DUSTMod.F90` — dust emission and dry deposition

### Reference

The core emission scheme is Zender's DEAD model (Zender et al. 2003) with
the Kok et al. (2014, doi:10.5194/acp-14-13023-2014) physically based
parameterization layered on top. Both are present side-by-side in the code
and selected at run time via `dust_emis_scheme`
(`biogeochem/DUSTMod.F90:34, 98, 426-495`), which is held in
`shr_dust_mod` (a shared-code module outside ELM's tree). Two values are
coded:

- `dust_emis_scheme = 1` — original Zender DEAD formulation with the
  `flx_mss_fdg_fct = 5.0e-4` tuning factor (`biogeochem/DUSTMod.F90:254`).
- `dust_emis_scheme = 2` — Kok et al. 2014 with its own tuning constants
  `Cd0 = 4.4e-5`, `Ca = 2.7`, `Ce = 2.0`, `C_tune = 0.05`
  (`biogeochem/DUSTMod.F90:257-267`).

### `dust_type`

Container (`biogeochem/DUSTMod.F90:63`) holding per-patch arrays:

- `flx_mss_vrt_dst_patch(p, 1:ndst)` — vertical dust emission by size
  bin (kg/m²/s), public.
- `flx_mss_vrt_dst_tot_patch(p)` — total dust flux.
- `vlc_trb_patch(p, 1:ndst)` and `vlc_trb_[1-4]_patch(p)` — turbulent
  dry-deposition velocities per bin (m/s).
- `mbl_bsn_fct_col(c)` — basin factor, a multiplier for the global dust
  emission tuning.

### `DustEmission` (`biogeochem/DUSTMod.F90:196`)

For every non-lake patch, compute the surface dust emission flux given
the local wind friction velocity `fv`, 10 m wind `u10`, soil texture
(`mss_frc_cly_vld_col`), soil moisture (`h2osoi_vol`), snow cover
(`frac_sno`), and LAI+SAI (the canopy quenching test, `vai_mbl_thr = 0.3`,
`biogeochem/DUSTMod.F90:254-255`). The algorithm:

1. Sum LAI+SAI across the patch's landunit to get `tlai_lu` — dust is
   suppressed once vegetation cover is high.
2. Compute gravimetric soil moisture at the surface (`gwc_sfc`) from
   `h2osoi_liq + h2osoi_ice` and compare to the clay-dependent threshold
   `gwc_thr` to get the wet-soil factor `frc_thr_wet_fct`.
3. Compute surface-roughness factor `frc_thr_rgh_fct`.
4. Compute threshold friction velocity `wnd_frc_thr_slt` and horizontal
   mass flux. In Kok 2014 mode, the threshold is first standardized to a
   reference air density (`forc_rho_std = 1.225 kg/m³`) to yield
   `wnd_frc_thr_slt_std`, then the dust emission coefficient `Cd` is
   computed from that standardized threshold
   (`biogeochem/DUSTMod.F90:420-495`).
5. Apply mobilization thresholds: emission is zero if friction velocity
   is below threshold, if `lnd_frc_mbl` (mobilizable fraction) is zero,
   or if snow covers the surface.
6. Distribute the total vertical flux into the `ndst` size bins using
   `ovr_src_snk_mss` (the source-sink overlap matrix, initialized in
   `InitDustVars`).

### `DustDryDep` (`biogeochem/DUSTMod.F90:532`)

Computes the turbulent dry-deposition velocity for each dust size bin
through the lowest atmospheric layer. The molecular diffusivity, gravity
settling, and Stokes correction are handled here (`stk_crc`, `dns_aer`);
the gravity settling through the rest of the column is the atmosphere
model's responsibility. Output is `vlc_trb_patch(p, 1:ndst)`, which is
passed up via `lnd2atm_vars`.

### Always-on behavior

`Init` writes `dust_emis_scheme` to the log on `masterproc`
(`biogeochem/DUSTMod.F90:98`). There is no namelist flag that turns
DUSTMod off inside ELM; the driver always calls `DustEmission` and
`DustDryDep`. If the build has `ndst = 0`, the routines effectively do
nothing because all the per-bin arrays are zero-sized.

---

## `VOCEmissionMod.F90` — BVOC emissions (MEGAN)

### Reference and compound set

Implementation follows Guenther et al. 2006 (isoprene) and its MEGAN 2.1
generalization to 20 compound classes (Colette Heald et al.,
`biogeochem/VOCEmissionMod.F90:421-424`). The canonical equation is

```
E = epsilon * gamma * rho
```

where `epsilon` is a PFT-and-compound-specific emission factor (ug/m²/hr),
`gamma` is the activity factor (unitless, a product of light, temperature,
LAI, leaf-age, and soil-moisture factors), and `rho` is the escape
efficiency (assumed 1).

### `vocemis_type` state

(`biogeochem/VOCEmissionMod.F90:48-74`) Holds diagnostic coefficients
(`Eopt_out`, `topt_out`, `alpha_out`, `cp_out`), PPFD history arrays
(`paru_out`, `par24u_out`, `par240u_out`, and their shaded analogs),
gamma factor breakdown (`gamma_out`, `gammaL_out`, `gammaT_out`,
`gammaP_out`, `gammaA_out`, `gammaS_out`, `gammaC_out`), and the actual
flux outputs:

- `vocflx_patch(p, num_mech_comps)` — per-mechanism-component flux in
  moles/m²/s (public).
- `vocflx_tot_patch(p)` — total VOC flux into the atmosphere.
- `efisop_grc(g, ...)` — gridcell isoprene emission factors (mapped if
  available).

### `VOCEmission` (`biogeochem/VOCEmissionMod.F90:374`)

The main routine loops over soil patches. Per time step it:

1. Returns immediately if `shr_megan_mechcomps_n < 1` (no MEGAN
   compounds requested).
2. Requires `nlevcan == 1` (multi-level canopy not supported for MEGAN)
   and aborts otherwise (`:468-470`).
3. For each mechanism component that maps to a MEGAN compound name, reads
   the per-PFT emission factor `epsilon` from the MEGAN table. For
   isoprene only, if `shr_megan_mapped_emisfctrs = .true.`, uses the
   gridcell-mapped `efisop_grc` instead of the PFT-constant table.
4. Computes the five activity factors:
   - `gamma_p` (and combined `gamma_l` with LAI) — from PPFD, sun and
     shade averages, and 24 h / 240 h running means of PPFD.
   - `gamma_t` — temperature response using the `Agro`, `Amat`, `Anew`,
     `Aold`, `ct1`, `ct2`, `betaT`, `Ceo` arrays from `MEGANFactorsMod`.
   - `gamma_a` — leaf-age dependence from the fraction of new / mature /
     old / senescent leaves, estimated from LAI changes.
   - `gamma_sm` — soil moisture stress.
   - `gamma_c` — CO2 inhibition (isoprene only, Heald et al. 2009).
5. Multiplies to form the total activity factor `gamma`, multiplies by
   `epsilon` (ug m-2 h-1), and converts to moles/m²/s via
   `megemis_units_factor = 1/3600/1e6` and the compound's molecular weight.
6. Accumulates into `vocflx_patch(p, imech)` for the mechanism component,
   into `vocflx_tot_patch(p)`, and into the per-MEGAN-compound
   diagnostic `vocflx_meg`.

### `MEGANFactorsMod.F90`

Provides the lookup table consumed by `VOCEmission`
(`biogeochem/MEGANFactorsMod.F90`):

- `megan_factors_init` (declared public `:17`) reads the MEGAN emission
  factors file, populates a hash table indexed by compound name, and
  fills the per-PFT arrays `Agro`, `Amat`, `Anew`, `Aold`, `betaT`,
  `ct1`, `ct2`, `LDF`, `Ceo` (all shape `(npfts)`).
- `megan_factors_get(comp_name, factors, class_n, molecwght)` (`:52`)
  returns, for a named compound, the per-PFT emission-factor vector, the
  MEGAN class number, and the molecular weight. The lookup uses a
  `gen_hashkey` into `hash_table_indices(1:2**16)`
  (`:43`).

### Gating

`VOCEmission` is called unconditionally from the driver (line 828 of
`EcosystemDynMod.F90`), but short-circuits when `shr_megan_mechcomps_n < 1`.
The set of mechanism components and their mapping to MEGAN compounds
comes from the atmosphere component's MEGAN namelist; when the atmosphere
runs without MEGAN, ELM produces no BVOC flux.

---

## `DryDepVelocity.F90` — Wesely dry-deposition velocities

Based on Wesely 1989 (Atmos. Env. 23:1293-1304) with modifications
following Vitt 2007 (`biogeochem/DryDepVelocity.F90:11-46`). Computes

```
|vd| = (ra + rb + rc)^-1
```

where `ra` (aerodynamic) and `rb` (quasilaminar sublayer) come from
earlier parts of ELM, and `rc` (bulk surface) is the main output here.

### `drydepvel_type` state

(`biogeochem/DryDepVelocity.F90:76`)

- `velocity_patch(p, n_drydep)` — dry-deposition velocity per species
  (m/s), public.

The `Init` method aborts if FATES is active outside of FATES-SP mode
(`biogeochem/DryDepVelocity.F90:91-100`) — Wesely deposition needs
surface-aggregated canopy state that is not exposed through FATES.

### `depvel_compute` (`biogeochem/DryDepVelocity.F90:134`)

Entry point called from the driver. For each species in `drydep_list`
(indices include the built-in O3, SO2, H2, CO, CH4, PAN, and X-PAN),
looks up Wesely parameters by species and by the current land-use
category (which is patch-type-dependent) and computes `rc` combining:

- Surface water resistance,
- Mesophyllic resistance to the species (depends on Henry's-law constant
  and reactivity),
- Cuticle resistance,
- Ground-to-canopy resistance,
- Canopy-adjusted stomatal resistance via `rs` from `photosyns_type`.

The use-statements show which species are recognized via named indices
from `seq_drydep_mod`
(`biogeochem/DryDepVelocity.F90:54-56`):
`index_o3`, `index_o3a`, `index_so2`, `index_h2`, `index_co`, `index_ch4`,
`index_pan`, `index_xpan`. Any other species in `drydep_list` falls back
to the generic Wesely lookup.

### Gating

The driver call to `depvel_compute` is wrapped in a check that
`n_drydep > 0` and `drydep_method == DD_XLND` (the "dry deposition using
land-use categories" method) — otherwise nothing is called and
`velocity_patch` is left at its default. The `n_drydep` variable is
populated from the atmosphere coupler.

---

## `ErosionMod.F90` — erosion-driven C / N / P fluxes

### Scope

`ErosionFluxes` (`biogeochem/ErosionMod.F90:31`) translates sediment
detachment and yield rates (`sed_ero_col`, `sed_yld_col` from the
`SedFluxType`, itself updated by the hydrology-erosion driver) into
corresponding C, N, and P fluxes from every decomposition pool in every
soil layer, plus the four mineral-P pools (`labilep_vr`, `secondp_vr`,
`occlp_vr`, `primp_vr`). It supports both detachment (`*_erode`,
`*_erode`, vertically integrated) and redeposition on the hillslope
(`*_deposit`).

### Per-pool outputs

For each decomposition pool index `k` and soil layer `j`, the routine
computes three quantities (all on `col_cf`/`col_nf`/`col_pf`):

- `cpools_erode(c, k)` — gC/m²/s detachment.
- `cpools_deposit(c, k)` — gC/m²/s redeposition.
- `cpools_yield_vr(c, j, k)` — gC/m³/s loss from layer `j`.

and similarly for `npools_*` and `ppools_*`. For the four mineral-P
pools, the outputs are `labilep_erode`, `labilep_deposit`,
`labilep_yield_vr`, etc.
(`biogeochem/ErosionMod.F90:84-107`).

### Algorithm

For each column that has `flx_sed_ero > 0`:

1. Convert total detachment rate to a surface-layer depth removed,
   `dh`, using `bd` (bulk density) and the eroded soil mass per m².
2. Walk top-down through the soil layers, cutting the pool mass
   proportional to the depth removed versus the layer thickness, until
   the full `dh` is accounted for.
3. The total detached mass is split into the "eroded" portion
   (`*_erode`, moved off the column by the sediment flux) and the
   redeposited portion (`*_deposit`, stays on the column but is moved
   down-slope). The split is driven by the sediment delivery ratio
   supplied by `SedFluxType`.
4. New pool values are written back into `decomp_cpools_vr`,
   `decomp_npools_vr`, `decomp_ppools_vr`, and the four mineral-P
   `*_vr` arrays.

The routine does not apply erosion to live-vegetation pools, only to
decomposition and mineral-P pools, matching the Water-Erosion-Predicting
mass balance.

### Gating

`ErosionFluxes` is invoked only when `ero_ccycle = .true.`
(`main/elm_varctl.F90:444` and the driver check at
`biogeochem/EcosystemDynMod.F90:841`). `ero_ccycle` is itself only
valid when `use_erosion = .true.`
(`main/elm_varctl.F90:443`); setting `ero_ccycle` without the erosion
model will not produce fluxes because the `sedflux_vars` inputs will be
zero. The default for both flags is `.false.`.

---

## Summary of always-on vs gated

| Module | Default | Gate |
|---|---|---|
| DustEmission | on (if `ndst > 0` in build) | `dust_emis_scheme` selects Zender vs Kok; no namelist off-switch. |
| DustDryDep | on | same as above. |
| VOCEmission | on | Self-gated on `shr_megan_mechcomps_n >= 1`. |
| depvel_compute | off by default | Requires `n_drydep > 0` and `drydep_method == DD_XLND`, set by atmosphere coupler namelist. |
| ErosionFluxes | off by default | Requires `ero_ccycle = .true.` (and `use_erosion = .true.` to get meaningful sediment input). |

## Data flow to and from the atmosphere

- Dust: `flx_mss_vrt_dst_patch` goes to `lnd2atm_vars%flxdst`; dry
  deposition velocities go to `lnd2atm_vars%ddvel` per bin. The
  atmosphere model's gravity settling treats the rest of the column.
- BVOCs: `vocflx_patch(:, :)` goes to `lnd2atm_vars` and is picked up
  by the atmospheric chemistry in CAM / EAM via the MEGAN mechanism
  mapping. Conversion from mol/m²/s to whatever units the atmosphere
  wants is done downstream.
- Dry deposition velocities: `velocity_patch(:, :)` is written to the
  `lnd2atm_vars%ddvel` channel for the chemistry species list.
- Erosion: fluxes are written into `col_cf`/`col_nf`/`col_pf` and
  remain within the ELM C, N, and P budgets; they are not sent to the
  atmosphere.

## What's missing from this subsystem

- Biomass-burning emissions are handled by `FireMod.F90` (CN-fire) or
  FATES SPITFIRE, not here. See `biogeochem/fire.md`.
- Sea-salt, black carbon, and organic carbon aerosol fluxes are not
  computed by ELM — those are the atmosphere model's problem.
- Ammonia emissions from agriculture (FAN) are handled in `FanMod.F90` /
  `FanUpdateMod.F90` (not in this document's scope) and are routed
  through the nitrogen cycle, not through `DryDepVelocity`.
