---
**Source pin:** ELM source at commit `60d9aad` (E3SM_FATES working tree, 2026-04-10)
**Scope:** `components/elm/src/` excluding `external_models/` (FATES) and `.ipynb_checkpoints/`
**Last verified:** 2026-04-10
---

# Mortality, root dynamics, and wood products

This document describes three tightly related biogeochemistry modules that
together handle the "turn vegetation into litter and product pools" side of
ELM's CN cycle when `use_cn = .true.` and `use_fates = .false.`:

| File | Role |
|---|---|
| `biogeochem/GapMortalityMod.F90` | Gap-phase (background) mortality of living plants, converting displayed/storage/transfer pools into column-level litter. |
| `biogeochem/RootDynamicsMod.F90` | Per-time-step update of the vertical fine-root and coarse-root distribution. |
| `biogeochem/WoodProductsMod.F90` | 10-year and 100-year wood product pools that receive harvested dead-stem C/N/P. |

FATES handles its own cohort-level gap, crown, carbon starvation, and
hydraulic mortalities internally. The ELM-native routines described here are
bypassed when FATES is active.

## `GapMortality` — background turnover of live vegetation

Entry point: `GapMortality` (`biogeochem/GapMortalityMod.F90:81`), called by
the CN ecosystem dynamics driver once per time step after allocation and
before litterfall aggregation.

### Parameter source and constants

Module parameters live in `CNGapMortParamsType`
(`biogeochem/GapMortalityMod.F90:34`) and are read from the ELM parameter
file by `readGapMortParams` (`biogeochem/GapMortalityMod.F90:47`):

- `r_mort` (annual mortality, 1/yr) — stored as `CNGapMortParamsInst%am`.
- `k_mort` — coefficient of growth efficiency in the mortality equation
  (not used in this routine except as a scalar load; retained for future
  growth-efficiency variants).

The routine converts the annual rate to a per-second rate
(`biogeochem/GapMortalityMod.F90:137`):

```
m = am / (dayspyr * secspday)
```

### RD-mode override (soilorder mortality)

When `nu_com == 'RD'` (relaxation-decomposition soilorder mode), the
subroutine calls `mortality_rate_soilorder`
(`biogeochem/GapMortalityMod.F90:558`) first. That routine overrides `am`
per-patch with `r_mort_soilorder(isoilorder(c))` for tropical broadleaf
evergreen and broadleaf deciduous PFTs (`nbrdlf_evr_trp_tree`,
`nbrdlf_dcd_trp_tree`) and sets 0.02/yr for everything else
(`biogeochem/GapMortalityMod.F90:589-594`). The per-patch rate is then
pulled back into `am` inside the main loop
(`biogeochem/GapMortalityMod.F90:132-134`).

### Patch loop: all C, N, and P pools

For each patch, `GapMortality` computes mortality fluxes for every
displayed, storage, and transfer pool in the CNP state. Using shorthand,
for each live pool `X`:

```
m_X_to_litter(p) = X(p) * m       ! displayed
m_X_storage_to_litter(p)  = X_storage(p)  * m
m_X_xfer_to_litter(p)     = X_xfer(p)     * m
```

The set of pools touched (`biogeochem/GapMortalityMod.F90:143-265`):

- Displayed C: `leafc`, `livestemc`, `deadstemc`, `frootc`, `livecrootc`,
  `deadcrootc`. For crops (`ivt >= npcropmin`), `m_leafc_to_litter` and
  `m_livestemc_to_litter` are zeroed unless the crop is live
  (`croplive(p)`) — a live crop can still experience background mortality,
  but a harvested stubble cannot
  (`biogeochem/GapMortalityMod.F90:144-148, 183-188, 226-232`).
- Storage C: `leafc_storage`, `frootc_storage`, `livestemc_storage`,
  `deadstemc_storage`, `livecrootc_storage`, `deadcrootc_storage`,
  `gresp_storage`, `cpool`.
- Transfer C: the `*_xfer` analogs plus `gresp_xfer`.
- N and P mirror the full C list, plus a retranslocated pool
  `retransn(p) * m` / `retransp(p) * m` that is applied only to non-crop
  patches (`biogeochem/GapMortalityMod.F90:193-197, 238-241`), and
  `npool(p) * m`, `ppool(p) * m` (the plant N/P storage pools used by PARTEH).

### Spinup mortality factor

When `spinup_state >= 1` (accelerated spinup), `m_deadstemc_to_litter`,
`m_deadcrootc_to_litter` and their N / P counterparts are additionally
multiplied by `spinup_mortality_factor`
(`biogeochem/GapMortalityMod.F90:154-157, 199-204, 244-249`). This compresses
the slow wood-turnover time scale so equilibrium soil carbon can be reached
in far fewer simulated years. The same factor is used in
`VegStructUpdateMod` to scale `deadstemc` when diagnosing canopy height
during spinup.

### Column aggregation (`CNGapPftToColumn`)

After the patch loop, `GapMortality` calls `CNGapPftToColumn`
(`biogeochem/GapMortalityMod.F90:279`) to aggregate the patch-level fluxes
to the column and distribute them into the vertical decomposition layers.
The routine multiplies by `wtcol` and the PFT-specific profiles
(`leaf_prof`, `froot_prof`, `croot_prof`, `stem_prof` — all from
`cnstate_vars`; `biogeochem/GapMortalityMod.F90:310-314`). The resulting
column-level mortality fluxes feed the litter C, N, and P pools consumed by
`SoilLittDecompMod`.

### N and P retranslocation on death

Because `retransn` and `retransp` are mixed labile pools held at the patch
level, only non-crop PFTs drop them to litter. For crops the retranslocated
N / P is used by grain fill in `CropPhenology` and ends up in the harvest
pool instead.

## `RootDynamics` — per-step vertical root distribution

Entry point: `RootDynamics`
(`biogeochem/RootDynamicsMod.F90:40`). Called after photosynthesis in the CN
ecosystem dynamics sequence. It produces `rootfr(p, 1:nlevgrnd)`, the
fraction of root mass in each soil layer, which is used by transpiration
stress, nutrient uptake, mortality, and the methane model.

### Dynamic root depth

First, `RootDynamics` updates `root_depth(p)` for each live patch
(`biogeochem/RootDynamicsMod.F90:135-149`):

- Crops (`ivt >= npcropmin`): scale max depth by developmental progress:

  ```
  root_depth(p) = max(zi(c,2), min(hui/huigrain * root_dmx(ivt), root_dmx(ivt)))
  ```

  where `hui` is `gddplant_patch` (GDD since planting) and `huigrain` is the
  HUI required to reach vegetative maturity. Crops can therefore grow roots
  deeper as they develop, bounded by the second soil-layer interface and
  the PFT-max `root_dmx`.

- Natural PFTs: bounded by the smaller of last year's max active-layer depth
  (`altmax_lastyear` from `canopystate_vars`), the bedrock interface
  `zi(c, nlevbed(c))`, and the PFT-max `root_dmx`. The use of
  `altmax_lastyear` is the Arctic / boreal permafrost constraint — frozen
  soil below the active layer is off-limits for roots.

### Water- and nitrogen-weighted growth allocation

Between the current `root_depth` and the bedrock, the routine builds two
normalized scalar fields for every soil layer (`biogeochem/RootDynamicsMod.F90:158-193`):

- `rswa(p,j)` = water availability, from `rresis(p,j)` (root-zone hydraulic
  resistance) weighted by layer thickness. A layer-integrated scalar
  `sumrswa(p)` serves as the normalizer.
- `rsmn(p,j)` = nitrogen availability. When `use_vertsoilc = .true.` it
  uses `sminn_vr(c,j) * dz(c,j)`; otherwise a fixed exponential
  `dz * exp(-3 * zi)` profile. `sumrsmn(p)` is the normalizer.

The relative weighting of water vs nitrogen is controlled by `w_limit(p)`,
an integrated measure of how many layers in the root zone are water-stressed,
capped at `soil_water_factor_min = 0.9`
(`biogeochem/RootDynamicsMod.F90:82-83, 165-171`).

### Updating the root-mass profile

A separate `rootfr_coarse` profile is produced by
`init_vegrootfr` (`RootBiophysMod`) for coarse roots
(`biogeochem/RootDynamicsMod.F90:199-201`). New fine-root growth over the
time step comes from `cpool_to_frootc + frootc_xfer_to_frootc` (plus
`cpool_to_frootc_storage` only for non-evergreen PFTs because evergreens
retain storage year-round). New coarse-root growth is the sum of live and
dead coarse-root allocation and transfer fluxes. Then
(`biogeochem/RootDynamicsMod.F90:208-236`):

```
frootc_dz(p,lev) = (livecrootc + deadcrootc + frootc) * rootfr(p,lev)       ! existing
                 + new_croot_growth * rootfr_coarse(p,lev)                  ! new coarse
                 + new_growth * ((1 - w_limit) * rswa/sumrswa                ! hydric
                                + w_limit * rsmn/sumrsmn)                   ! nutrient
```

New fine-root growth is split between "where the water is" and "where the
nitrogen is" by `1 - w_limit` and `w_limit`. Drier root zones therefore shift
growth toward the nitrogen profile, while moist root zones follow water
availability. Finally, `rootfr(p, lev) = frootc_dz(p, lev) / sumfrootc(p)`
normalizes to a unit-sum profile (`biogeochem/RootDynamicsMod.F90:244-252`).

New growth is skipped entirely while `onset_flag == 1`, so that allocation
during the onset pulse doesn't artificially shift the profile during rapid
storage flushing (`biogeochem/RootDynamicsMod.F90:213-217`).

### What RootDynamics does not do

`RootDynamics` updates `rootfr` but does not move root mass between layers
for its own sake, does not apply mortality to roots (that happens in
`GapMortality`), and does not compute the root biophysics profile used for
hydraulic redistribution (`RootBiophysMod`). It is strictly a diagnostic
spatial-redistribution update driven by this time step's root-growth flux.

## `WoodProducts` — 10-year and 100-year product pools

Entry point: `WoodProducts` (`biogeochem/WoodProductsMod.F90:30`), called
once per time step from the CN driver.

The routine maintains column-level `prod10c`, `prod100c` (and their N/P
analogs and C13/C14 tracers when `use_c13`/`use_c14` is set) that receive
harvested dead-stem wood from `CNHarvestPoolsMod` (not shown here) via
`hrv_deadstemc_to_prod10c` and `hrv_deadstemc_to_prod100c`.

Two hard-coded first-order decay constants
(`biogeochem/WoodProductsMod.F90:53-56`):

```
kprod10  = 7.2e-9   ! ~90% lost over 10 years
kprod100 = 7.2e-10  ! ~90% lost over 100 years
```

Each step:

1. Compute loss fluxes `prod10*_loss = prod10* * kprod10`,
   `prod100*_loss = prod100* * kprod100`
   (`biogeochem/WoodProductsMod.F90:62-79`).
2. Update state:

   ```
   prod10c  += (hrv_deadstemc_to_prod10c  - prod10c_loss)  * dt
   prod100c += (hrv_deadstemc_to_prod100c - prod100c_loss) * dt
   ```

   (`biogeochem/WoodProductsMod.F90:85-130`) — same update applied for N
   and P, and for C13 / C14 when their flags are on.

The loss terms are not sent back to the atmosphere inside this module; the
column CNP budget closure code accumulates them into the "column fire +
product loss" sink term.

### Companion: `CropHarvestPoolsMod`

A near-identical pattern in `biogeochem/CropHarvestPoolsMod.F90` maintains a
single `prod1c`, `prod1n`, `prod1p` pool with `kprod1 = 7.2e-9` (~1-year
turnover), fed by `hrv_cropc_to_prod1c` and friends
(`biogeochem/CropHarvestPoolsMod.F90:50-100`). That pool is the 1-year
"crop food product" short-term sink used by the prognostic crop pathway
(see `biogeochem/crops.md`).

## Sequencing and data dependencies

Each of the three routines runs independently on its own phase of the CN
cycle, but they are linked via shared state on the patch and column data
objects:

- `RootDynamics` needs `rresis` from the energy flux module and
  `cpool_to_frootc` / `cpool_to_livecrootc` from allocation. Its output
  `rootfr` is consumed later by transpiration stress and by
  `GapMortality` (indirectly via `froot_prof`).
- `GapMortality` reads C, N, P pools from `veg_cs`, `veg_ns`, `veg_ps`
  and writes per-patch fluxes into `veg_cf`, `veg_nf`, `veg_pf`. Its
  column aggregation is then consumed by `SoilLittDecompMod`.
- `WoodProducts` only touches column-level product pools, isolated from
  the patch pipeline. It depends on the previous time step's harvest
  fluxes computed elsewhere; the harvest driver writes into
  `hrv_deadstemc_to_prod{10,100}c` before this routine runs.

## Parameter summary

| Parameter | Source | Used in |
|---|---|---|
| `r_mort` (named `am` in code) | ELM parameter file → `CNGapMortParamsInst%am` | `GapMortality` annual background mortality rate |
| `k_mort` | ELM parameter file → `CNGapMortParamsInst%k_mort` | Loaded but not used in the current main loop (placeholder for growth-efficiency mortality) |
| `r_mort_soilorder(isoilorder)` | `soilorder_varcon` table | `mortality_rate_soilorder`, tropical BET / BDT under RD mode |
| `spinup_mortality_factor` | `elm_varctl`, namelist-driven | Scales dead-stem mortality in `GapMortality` and dead-stem C in `VegStructUpdateMod` |
| `root_dmx(ivt)` | `pftvarcon` | Max rooting depth per PFT in `RootDynamics` |
| `roota_par`, `rootb_par` | `pftvarcon` | Fixed exponential root distribution; used by `init_vegrootfr` called in `RootDynamics` |
| `kprod10`, `kprod100` | Hard-wired in `WoodProductsMod.F90` | Product-pool decay constants |
| `kprod1` | Hard-wired in `CropHarvestPoolsMod.F90` | 1-year crop product-pool decay constant |

## What's not in this subsystem

- Fire mortality is handled in `FireMod.F90` (`FireFluxes`) —
  see `biogeochem/fire.md`.
- Transient landcover mortality (deforestation, crop expansion, harvest as
  a disturbance) is processed by the dynamic-subgrid bookkeeping code in
  `dyn_subgrid/` and flows into these pools via separate harvest flux
  fields, not via `GapMortality`.
- Nutrient-stress mortality, carbon-starvation mortality, and hydraulic
  mortality are FATES-only concepts and are not implemented in the
  ELM-native path. `GapMortality` is a pure background exponential decay
  with no feedbacks from current plant state.
