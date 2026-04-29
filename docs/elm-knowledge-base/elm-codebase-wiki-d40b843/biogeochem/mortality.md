---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Mortality, Root Dynamics, and Wood Products

This document describes three tightly related biogeochemistry modules that
together handle the "turn vegetation into litter and product pools" side of
ELM's CN cycle when `use_cn = .true.` and `use_fates = .false.`:

| File | Role |
|---|---|
| `biogeochem/GapMortalityMod.F90` | Gap-phase background mortality of living plants. |
| `biogeochem/RootDynamicsMod.F90` | Per-time-step update of vertical fine-root and coarse-root distribution. |
| `biogeochem/WoodProductsMod.F90` | 10-year and 100-year wood product pools that receive harvested dead-stem C/N/P. |

FATES handles its own cohort-level gap, crown, carbon-starvation, and hydraulic
mortalities internally. The ELM-native routines described here are bypassed
when FATES is active.

## `GapMortality` — background turnover of live vegetation

Entry point: `GapMortality(num_soilc, filter_soilc, num_soilp, filter_soilp,
cnstate_vars, crop_vars)` (`biogeochem/GapMortalityMod.F90:81`), called by the
CN ecosystem dynamics driver once per time step after allocation
(`EcosystemDynNoLeaching2:721` in the `.not. use_fates` block).

### Parameter source and constants

Module parameters live in `CNGapMortParamsType`
(`biogeochem/GapMortalityMod.F90:34`) and are read from the ELM parameter file
by `readGapMortParams` (`:47-78`):

- `r_mort` (annual mortality, 1/yr) — stored as `CNGapMortParamsInst%am`.
- `k_mort` — coefficient of growth efficiency in the mortality equation
  (loaded but not used in the current main loop).

The routine converts the annual rate to per-second:

```
m = am / (dayspyr * secspday)
```

### RD-mode override (soilorder mortality)

When `nu_com == 'RD'`, the routine calls `mortality_rate_soilorder`
(`biogeochem/GapMortalityMod.F90:557-601`) first. **At d40b8431** this routine
identifies the relevant tropical PFTs by trait flags rather than named
constants:

```fortran
use pftvarcon, only: woody, needleleaf, climatezone
...
if( woody(veg_pp%itype(p)) == 1.0_r8 .and. &
    needleleaf(veg_pp%itype(p)) == 0 .and. &
    climatezone(veg_pp%itype(p)) == 1 )then
   am = r_mort_soilorder(isoilorder(c))   ! tropical broadleaf woody (covers BET and BDT trees)
else
   am = 0.02_r8                            ! everything else
end if
```

The named constants `nbrdlf_evr_trp_tree`, `nbrdlf_dcd_trp_tree` are no longer
used in `GapMortalityMod`. The new test selects "tropical (`climatezone == 1`)
broadleaf (`needleleaf == 0`) tree (`woody == 1.0_r8`)" — note that
`woody == 2.0_r8` (shrubs) are explicitly excluded by the equality test. The
per-patch rate is then pulled back into `am` inside the main loop.

### Patch loop: all C, N, and P pools

For each patch, `GapMortality` computes mortality fluxes for every displayed,
storage, and transfer pool. Using shorthand, for each live pool `X`:

```
m_X_to_litter(p) = X(p) * m       ! displayed
m_X_storage_to_litter(p)  = X_storage(p)  * m
m_X_xfer_to_litter(p)     = X_xfer(p)     * m
```

Pools touched (`:143-265`):

- Displayed C: `leafc`, `livestemc`, `deadstemc`, `frootc`, `livecrootc`,
  `deadcrootc`. For crops (`iscft(ivt(p))` test, replacing
  `ivt >= npcropmin`), `m_leafc_to_litter` and `m_livestemc_to_litter` are
  zeroed unless the crop is live (`croplive(p)`).
- Storage C: `leafc_storage`, `frootc_storage`, `livestemc_storage`,
  `deadstemc_storage`, `livecrootc_storage`, `deadcrootc_storage`,
  `gresp_storage`, `cpool`.
- Transfer C: the `*_xfer` analogs plus `gresp_xfer`.
- N and P mirror the full C list, plus `retransn(p) * m` / `retransp(p) * m`
  applied only to non-crop patches, and `npool(p) * m`, `ppool(p) * m`.

### Spinup mortality factor

When `spinup_state >= 1` (accelerated spinup), `m_deadstemc_to_litter`,
`m_deadcrootc_to_litter` and their N / P counterparts are multiplied by
`spinup_mortality_factor`. The same factor is used in `VegStructUpdateMod` to
scale `deadstemc` when diagnosing canopy height during spinup.

### Column aggregation (`CNGapPftToColumn`, `:278-555`)

After the patch loop, `GapMortality` calls `CNGapPftToColumn` to aggregate the
patch-level fluxes to the column and distribute them into the vertical
decomposition layers. The routine multiplies by `wtcol` and the PFT-specific
profiles (`leaf_prof`, `froot_prof`, `croot_prof`, `stem_prof` from
`cnstate_vars`).

### N and P retranslocation on death

Because `retransn` and `retransp` are mixed labile pools held at the patch
level, only non-crop PFTs drop them to litter. For crops the retranslocated
N / P is used by grain fill in `CropPhenology` and ends up in the harvest
pool instead.

## `RootDynamics` — per-step vertical root distribution (NEW SIGNATURE)

Entry point at d40b8431:

```fortran
subroutine RootDynamics(bounds, num_soilc, filter_soilc, num_soilp, filter_soilp, &
     canopystate_vars, cnstate_vars, crop_vars, energyflux_vars, &
     soilstate_vars, dt)
   real(r8), intent(in) :: dt    ! radiation time step delta t (seconds)
```

(`biogeochem/RootDynamicsMod.F90:40-65`). **The `dt` argument is now passed in
explicitly**; in 60d9aad it was computed via `get_step_size()` inside the
routine. Any external script that copy-pasted the old call signature will not
compile against d40b8431.

The orchestrating call in `EcosystemDynMod.F90:627-629` was updated to pass
`dt`:

```fortran
call RootDynamics(bounds, num_soilc, filter_soilc, num_soilp, filter_soilp, &
      canopystate_vars,   &
      cnstate_vars, crop_vars, energyflux_vars, soilstate_vars, dt)
```

The routine produces `rootfr(p, 1:nlevgrnd)`, the fraction of root mass in
each soil layer, used by transpiration stress, nutrient uptake, mortality, and
the methane model.

### Dynamic root depth

For each live patch (`:135-149`):

- Crops: replaces the legacy `ivt >= npcropmin` test with `iscft(ivt(p))`:
  ```fortran
  if (iscft(ivt(p))) then
     if (huigrain(p) > 0._r8) then
        root_depth(p) = max(zi(c,2), min(hui(p)/huigrain(p) * root_dmx(ivt(p)), &
                                         root_dmx(ivt(p))))
     end if
  ```
  where `hui` is `gddplant_patch` and `huigrain` is the HUI required to reach
  vegetative maturity.
- Natural PFTs: bounded by the smaller of last year's max active-layer depth
  (`altmax_lastyear`), the bedrock interface `zi(c, nlevbed(c))`, and the
  PFT-max `root_dmx`.

### Water- and nitrogen-weighted growth allocation

Module-level constants (`:82-84`):

```fortran
real(r8), parameter :: minpsi = -1.5_r8                  ! permanent wilting point (MPa)
real(r8), parameter :: soil_water_factor_min = 0.9_r8
real(r8), parameter :: exp_decay_factor = 3._r8
```

Between `root_depth` and bedrock, the routine builds two normalized scalar
fields per layer:

- `rswa(p,j)` = water availability, from `rresis(p,j)` weighted by layer
  thickness. Normalizer: `sumrswa(p)`.
- `rsmn(p,j)` = nitrogen availability. When `use_vertsoilc = .true.` it uses
  `sminn_vr(c,j) * dz(c,j)`; otherwise a fixed exponential
  `dz * exp(-exp_decay_factor * zi)` profile. Normalizer: `sumrsmn(p)`.

The relative weighting of water vs nitrogen is controlled by `w_limit(p)`,
capped at `soil_water_factor_min = 0.9`.

### Updating the root-mass profile

A separate `rootfr_coarse` profile is produced by `init_vegrootfr`
(`RootBiophysMod`) for coarse roots. New fine-root growth comes from
`cpool_to_frootc + frootc_xfer_to_frootc` (plus `cpool_to_frootc_storage` for
non-evergreen PFTs). New coarse-root growth is the sum of live and dead
coarse-root allocation and transfer fluxes. Then:

```
frootc_dz(p,lev) = (livecrootc + deadcrootc + frootc) * rootfr(p,lev)       ! existing
                 + new_croot_growth * rootfr_coarse(p,lev)                  ! new coarse
                 + new_growth * ((1 - w_limit) * rswa/sumrswa                ! hydric
                                + w_limit * rsmn/sumrsmn)                   ! nutrient
```

Finally `rootfr(p, lev) = frootc_dz(p, lev) / sumfrootc(p)` normalizes.

New growth is skipped while `onset_flag == 1`.

### Dispatch

`RootDynamics` is called only when `use_dynroot` is true and only inside the
`.not. use_fates` block (`EcosystemDynMod.F90:624-631`).

### What RootDynamics does not do

- Does not move root mass between layers for its own sake.
- Does not apply mortality to roots (handled in `GapMortality`).
- Does not compute the root biophysics profile used for hydraulic
  redistribution (`RootBiophysMod`).

## `WoodProducts` — 10-year and 100-year product pools

Entry point: `WoodProducts(num_soilc, filter_soilc)`
(`biogeochem/WoodProductsMod.F90:30-134`), called once per time step from the
CN driver — and ALSO when FATES is active (see below).

The routine maintains column-level `prod10c`, `prod100c` (and N/P analogs and
C13/C14 tracers when `use_c13`/`use_c14` is set) that receive harvested
dead-stem wood from `CNHarvestPoolsMod` via `hrv_deadstemc_to_prod10c` and
`hrv_deadstemc_to_prod100c`.

Two hard-coded first-order decay constants:

```fortran
kprod10  = 7.2e-9   ! ~90% lost over 10 years
kprod100 = 7.2e-10  ! ~90% lost over 100 years
```

Each step:

1. Compute loss fluxes `prod10*_loss = prod10* * kprod10`,
   `prod100*_loss = prod100* * kprod100`.
2. Update state:

   ```
   prod10c  += (hrv_deadstemc_to_prod10c  - prod10c_loss)  * dt
   prod100c += (hrv_deadstemc_to_prod100c - prod100c_loss) * dt
   ```

   (`biogeochem/WoodProductsMod.F90:85-130`) — same update applied for N and P,
   and for C13 / C14 when their flags are on.

### FATES wood-products coupling (NEW at d40b8431)

When `use_fates = .true.`, `EcosystemDynNoLeaching2:811` calls
`alm_fates%wrap_WoodProducts(bounds, num_soilc, filter_soilc)` first
(`elmfates_interfaceMod.F90:2735-2767`), which copies harvested wood from FATES
cohorts into ELM's `hrv_deadstemc_to_prod10c` / `hrv_deadstemc_to_prod100c`
column flux fields. THEN `WoodProducts` runs unconditionally
(`EcosystemDynNoLeaching2:813`). So the 10-year and 100-year pool decay is
managed centrally on the ELM side regardless of mode.

### Companion: `CropHarvestPoolsMod`

A near-identical pattern in `biogeochem/CropHarvestPoolsMod.F90` maintains a
single `prod1c`, `prod1n`, `prod1p` pool with `kprod1 = 7.2e-9` (~1-year
turnover). `CropHarvestPools` runs unconditionally
(`EcosystemDynNoLeaching2:798, 815`).

## Sequencing and data dependencies

Each routine runs independently on its own phase of the CN cycle, but they are
linked via shared state:

- `RootDynamics` needs `rresis` from the energy flux module and
  `cpool_to_frootc` / `cpool_to_livecrootc` from allocation. Output `rootfr`
  is consumed later by transpiration stress and (indirectly via `froot_prof`)
  by `GapMortality`.
- `GapMortality` reads C, N, P pools from `veg_cs`, `veg_ns`, `veg_ps` and
  writes per-patch fluxes into `veg_cf`, `veg_nf`, `veg_pf`. Column
  aggregation is consumed by `SoilLittDecompMod`.
- `WoodProducts` only touches column-level product pools, isolated from the
  patch pipeline. It depends on the previous time step's harvest fluxes
  (CN-side `CNHarvest` or FATES-side `wrap_WoodProducts`).

## Parameter summary

| Parameter | Source | Used in |
|---|---|---|
| `r_mort` (named `am` in code) | ELM parameter file -> `CNGapMortParamsInst%am` | `GapMortality` annual background mortality rate |
| `k_mort` | ELM parameter file -> `CNGapMortParamsInst%k_mort` | Loaded but not used in the current main loop |
| `r_mort_soilorder(isoilorder)` | `soilorder_varcon` table | `mortality_rate_soilorder`, applied to tropical broadleaf woody PFTs (`woody == 1.0_r8 .and. needleleaf == 0 .and. climatezone == 1`) under RD mode |
| `spinup_mortality_factor` | `elm_varctl`, namelist-driven | Scales dead-stem mortality in `GapMortality` and dead-stem C in `VegStructUpdateMod` |
| `root_dmx(ivt)` | `pftvarcon` | Max rooting depth per PFT in `RootDynamics` |
| `roota_par`, `rootb_par` | `pftvarcon` | Fixed exponential root distribution; used by `init_vegrootfr` called in `RootDynamics` |
| `kprod10`, `kprod100` | Hard-wired in `WoodProductsMod.F90` | Product-pool decay constants |
| `kprod1` | Hard-wired in `CropHarvestPoolsMod.F90` | 1-year crop product-pool decay constant |
| `minpsi = -1.5_r8` | `RootDynamicsMod.F90:82` (module parameter) | Permanent wilting point in root-availability calculation |
| `soil_water_factor_min = 0.9_r8` | `RootDynamicsMod.F90:83` | Cap on `w_limit` |

## What's not in this subsystem

- Fire mortality is in `FireMod.F90` (`FireFluxes`). See `fire.md`.
- Transient landcover mortality (deforestation, crop expansion, harvest as a
  disturbance) is processed by `dyn_subgrid/`.
- Nutrient-stress, carbon-starvation, and hydraulic mortalities are FATES-only
  concepts and are not implemented in the ELM-native path. `GapMortality` is a
  pure background exponential decay with no feedbacks from current plant state.
