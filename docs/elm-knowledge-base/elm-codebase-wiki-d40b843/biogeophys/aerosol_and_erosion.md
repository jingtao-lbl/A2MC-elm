---
**Source pin:** ELM at E3SM commit d40b8431
**FATES pairing:** FATES at commit e027a40 (sci.1.91.1_api.43.1.0)
**Last verified:** 2026-04-26
---

# Aerosol Deposition, Snow-on Aerosols, and Soil Erosion

This document covers two loosely coupled but physically distinct processes:

- **Aerosol deposition onto snow**: black carbon (BC), organic carbon (OC), and four dust species deposit onto the snowpack, are aged through layers, and darken the snow (SNICAR).
- **Soil erosion**: rainfall-driven and runoff-driven detachment of soil material from hillslopes, with transport-capacity-limited yield to inland waters (Tan et al. 2022).

Both paths operate on the snow/soil column but write to independent state (`aerosol_type` and `sedflux_type`).

At `d40b8431`, the changes here are localized: (a) the snow-capping aerosol-mass scaling in `AerosolMod` is now gated on `use_firn_percolation_and_compaction` (instead of `use_extrasnowlayers`), (b) `SedYieldMod` uses the generic `crop()` and `iscft()` PFT accessors, and (c) the `is_soil`/`is_crop` accessors are used. Algorithmic physics is unchanged.

## Scope

- `biogeophys/AerosolMod.F90` — `AerosolMasses` (column-integrated masses and per-layer concentrations) and `AerosolFluxes` (deposition from atmosphere). Snow-cap aerosol scaling now gated on the firn flag (line 110).
- `biogeophys/AerosolType.F90` — `aerosol_type` holding per-layer snow aerosol mass and concentration plus landed deposition fluxes. Unchanged.
- `biogeophys/SedYieldMod.F90` — `SoilErosion` subroutine implementing a BQART-inspired rainfall and runoff erosion model. Two `crop()`/`iscft()` substitutions at lines 221 and 269.
- `biogeophys/SedFluxType.F90` — `sedflux_type` holding per-column sediment detachment and yield. Unchanged.

## Aerosol on snow

### Aerosol species

ELM tracks seven aerosol species (eight pointers, including hydrophilic vs hydrophobic carbons) in each snow layer (`aerosol_type`, `biogeophys/AerosolType.F90:21-71`):

| Category | Species | Pointer |
|---|---|---|
| Black carbon | hydrophobic BC | `mss_bcpho_col(:,:)` |
| Black carbon | hydrophilic BC | `mss_bcphi_col(:,:)` |
| Organic carbon | hydrophobic OC | `mss_ocpho_col(:,:)` |
| Organic carbon | hydrophilic OC | `mss_ocphi_col(:,:)` |
| Dust | species 1 | `mss_dst1_col(:,:)` |
| Dust | species 2 | `mss_dst2_col(:,:)` |
| Dust | species 3 | `mss_dst3_col(:,:)` |
| Dust | species 4 | `mss_dst4_col(:,:)` |

Four dust size bins cover the standard SNICAR dust optical ranges. Mass-concentration counterparts (`mss_cnc_*_col`) are `kg/kg` quantities passed directly to `SnowSnicarMod` (see [radiation.md](radiation.md)). The `flx_*_dep_*_col` arrays hold dry, wet, hydrophobic, and hydrophilic deposition fluxes per column `[kg/s]`.

### `AerosolMasses`

`biogeophys/AerosolMod.F90:33-225` defines `AerosolMasses`. At the top of hydrology Phase 2 (after `BuildSnowFilter` has rebuilt the layer structure), the routine:

1. **Zeros the column-integrated totals** (`mss_bc_col`, `mss_oc_col`, `mss_dst_col`) at lines 100-103.
2. **Snow capping correction** — when `do_capsnow(c)` is true and the top layer mass has been reduced by `qflx_snwcp_ice*dtime`, all aerosol masses in the top layer are scaled by `snowmass / (snowmass + qflx_snwcp_ice*dtime)` to preserve concentration (not mass). At `d40b8431`, this branch is gated on `.not. use_firn_percolation_and_compaction` (line 110):

   ```fortran
   do j = -nlevsno+1, 0
      snowmass = h2osoi_ice(c,j) + h2osoi_liq(c,j)
      if (.not. use_firn_percolation_and_compaction) then
         if (j == snl(c)+1) then
            if (do_capsnow(c)) then
               snowcap_scl_fct = snowmass / (snowmass + qflx_snwcp_ice(c)*dtime)
               mss_bcpho(c,j) = mss_bcpho(c,j) * snowcap_scl_fct
               ... ! mss_bcphi, mss_ocpho, mss_ocphi, mss_dst1..4
            endif
         endif
      endif
      ...
   end do
   ```

   When firn mode is on, this scaling is skipped — the firn percolation/compaction physics handles top-layer aerosol mass differently.

3. **Mass concentration computation** — for each snow layer, `mss_cnc_bcphi = mss_bcphi(c,j) / snowmass`, etc.
4. **Column and top-layer aggregation** — `mss_bc_col`, `mss_oc_col`, `mss_dst_col` get column sums; `mss_bc_top`, `mss_oc_top`, `mss_dst_top` get top-layer masses; `h2osno_top` tracks top-layer SWE for diagnostics.

### `AerosolFluxes`

`biogeophys/AerosolMod.F90:228-379` reads `atm2lnd_vars%forc_aer_grc(:,:)` — a 14-component array holding deposition fluxes from the atmosphere model (or prescribed file) and maps it into the `flx_*_dep_*_col` arrays. Two branches exist:

- **Bulk deposition** (default, not `MODAL_AER`): the first three indices are BC (hydrophilic dry, hydrophobic dry, wet), the next three are OC, and `forc_aer(g,7:14)` are the eight dust fluxes (wet/dry x 4 species).
- **Modal deposition** (`#ifdef MODAL_AER`): "phi" BC/OC flavors represent within-hydrometeor (cloud-borne) aerosol and "pho" flavors are interstitial, consistent with the MAM modal aerosol scheme in EAM.

After building the column deposition fluxes, the routine deposits into the top snow layer:
```
mss_bcphi(c, snl(c)+1) += flx_bc_dep_phi(c) * dtime
mss_bcpho(c, snl(c)+1) += flx_bc_dep_pho(c) * dtime
mss_ocphi(c, snl(c)+1) += flx_oc_dep_phi(c) * dtime
mss_ocpho(c, snl(c)+1) += flx_oc_dep_pho(c) * dtime
mss_dst{1..4}(c, snl(c)+1) += (dry + wet)*dtime
```

The deposition step comes *after* the per-layer aerosol advection in `SnowHydrologyMod` so that newly deposited aerosols appear in the top layer before the next radiative call.

### Aging and advection

Aerosol masses are advected between snow layers by `SnowHydrologyMod::SnowWater` as part of the liquid water fluxes, with species-specific effective solubilities. Hydrophilic flavors are largely washed out with percolating water; hydrophobic flavors age to hydrophilic over a prescribed timescale. ELM inherits the CLM4/SNICAR aging formulation documented in Flanner et al. 2007.

### Coupling to SNICAR and snow albedo

`SnowSnicarMod` reads `mss_cnc_*` arrays each timestep to compute snow-layer-resolved specific absorption that darkens the visible albedo. The resulting `albgrd`, `albgri` are used by `SurfaceAlbedoMod` and `UrbanAlbedoMod`. Dust optics uses the four prescribed size bins consistent with the Fialho et al. 2006 / Balkanski et al. 2007 optical properties.

`snw_rds_min = 54.526_r8` (`biogeophys/AerosolMod.F90:27`) is the minimum allowed snow effective radius (also the "fresh snow" value) used by the grain-growth solver in `SnowSnicarMod`.

### `snw_rds_refrz` is a variable, not a parameter

`snw_rds_refrz` (the effective radius assigned to refrozen snow) lives in `SnowSnicarMod`, not `AerosolMod` — but it is calibration-relevant here because it controls how aerosol absorption scales when liquid water in the top snow layer refreezes. At `d40b8431`, `snw_rds_refrz` is declared as a **module variable** (no longer a parameter) at `SnowSnicarMod.F90:83`:

```fortran
real(r8) :: snw_rds_refrz = 1000._r8
```

and reset at every call inside `SnowAge_grain` based on the firn flag (`SnowSnicarMod.F90:1444-1447`):

```fortran
if (use_firn_percolation_and_compaction) then
   snw_rds_refrz = 1500._r8
else
   snw_rds_refrz = 1000._r8
endif
```

The wiki at `60d9aad` described this as a "fixed constant" — not accurate at `d40b8431`. See [radiation.md](radiation.md) for the full snow grain aging discussion.

## Soil erosion: `SedYieldMod`

`biogeophys/SedYieldMod.F90:53-303` implements the Tan et al. 2022 erosion model. The single public routine is `SoilErosion`:

```
subroutine SoilErosion(bounds, num_soilc, filter_soilc,
     canopystate_vars, cnstate_vars, soilstate_vars, sedflux_vars)
```

The routine signature, structure, and Tan et al. 2022 algorithm are unchanged at `d40b8431`. The only diff is the use of `crop()`/`iscft()` accessors at lines 221 and 269 (in place of `> nc4_grass` index comparisons), and `col_pp%is_soil(c)` / `is_crop` at line 160.

### Inputs

From `soilstate_vars` (tuning and soil properties):
- `bd_col` — bulk density (kg/m^3)
- `cellsand_col`, `cellclay_col`, `cellgrvl_col` — soil texture and gravel percentage (by mass)
- `tillage_col` — conserved tillage fraction
- `litho_col` — lithology erodibility index

From `col_pp`:
- `hslp_p10(c,:)` — hillslope gradient percentiles (`nlevslp` bins)

From the topounit / gridcell atmospheric state (`top_as`, `top_af`):
- `forc_rain(t)` — rain rate (mm/s)
- `forc_t(t)` — atmospheric temperature (K), used to gate rainfall erosion (must be > 273.15 K)

From water fluxes (`col_wf`, `veg_wf`):
- `qflx_surf(c)` — surface runoff (mm/s)
- `qflx_qrgwl(c)` — glacier runoff (mm/s)
- `qflx_dirct_rain(p)`, `qflx_leafdrip(p)`, `qflx_real_irrig_patch(p)` — throughfall, leaf drip, irrigation

From canopy state (`canopystate_vars`):
- `tlai_patch`, `htop_patch`, `hbot_patch`

From the soil BGC cascade (`decomp_cpools_vr`):
- Litter C in the top soil layer, used to compute residue cover (`Brsd`).

### Mechanics

Two independent components:

1. **Rainfall-driven detachment** (`Es_P`):
   - Throughfall kinetic energy: `KE_DT = Ptot * fungrvl * max(8.95 + 8.44*log10(Ie), 0)`, with `Ie = 3.6e3 * (rain + irrigation)` and `fungrvl = 1 - 0.01*fgrvl`.
   - Leaf-drip kinetic energy: `KE_LD = max(15.8*sqrt(cheight) - 5.87, 0) * fungrvl * Dl`.
   - Ground cover attenuation: `fgndcov = exp(-gcbc_p(pft) * PCT_gnd - gcbr_p(pft) * Broot)`, where `PCT_gnd = 100 * max(residue_cover, 1 - exp(-LAI))`.
   - Assembly: `Es_P += pfactor(c) * ftillage * flitho * fgndcov * wtcol(p) * K * (KE_DT + KE_LD)`.
   - Snow cover scales the final result by `(1 - frac_sno(c))`.

2. **Runoff-driven detachment** (`Es_Q`):
   - Runoff power: `Qss = (1 - 0.7846 * frac_sno) * Qs`, `Qs = 8.64e4 * qflx_surf` (mm/day).
   - Slope factor: average `sin(atan(hslp_p10))` over hillslope percentile bins.
   - Cohesion via `COH = SoilCohesion(stxt)`.
   - Manning roughness: `nh = 0.03 + 0.05 * max(Crsd, Clai)`, and `fsr = wtcol * (0.03/nh)^0.6`.
   - At `d40b8431`, the crop discriminator at `SedYieldMod.F90:221, 269` is `crop(veg_pp%itype(p)) >= 1 .or. iscft(veg_pp%itype(p))` (replacing the old `> nc4_grass` check). The non-crop branch uses a glacier factor; the crop branch uses the standard runoff-detachment factor.
   - Assembly: `Es_Q += 19.1 * qfactor(c) * 2/COH * flitho * fslp * ftillage * fgndcov * Qss^1.5 * wtcol(p)`.

3. **Transport capacity**: `Tc = 19.1 * tfactor(c) * fslp_tc * fsr * ftillage_tc * flitho * fglacier * Qs^2`. The yield to inland waters is capped by transport capacity:

   ```
   flx_sed_yld(c) = min(Es_P + Es_Q, Tc)
   ```

### Glacier scaling

If there is an active `istice` landunit in the same topounit and its meltwater runoff is finite, `fglacier = 1 + 9 * lun_pp%wttopounit(lt)`, implementing a runoff-power amplification for glacier-fed streams.

### Output: `sedflux_type`

Defined in `biogeophys/SedFluxType.F90:21-43` (unchanged):

| Member | Meaning |
|---|---|
| `pfactor_col` | Rainfall-driven erosion scaling factor (tunable, column-constant) |
| `qfactor_col` | Runoff-driven erosion scaling factor |
| `tfactor_col` | Transport capacity scaling factor |
| `sed_p_ero_col` | Sediment detachment driven by rainfall (kg/m2/s) |
| `sed_q_ero_col` | Sediment detachment driven by runoff (kg/m2/s) |
| `sed_ero_col` | Total detachment (kg/m2/s) |
| `sed_crop_ero_col` | Cropland-only detachment (kg/m2/s) |
| `sed_yld_col` | Sediment yield to inland waters (kg/m2/s), capped by `Tc` |

The first three scaling factors are read at initialization (via `InitCold`) from the surface dataset or a runtime parameter file and held fixed thereafter.

## Interfaces with other subsystems

- **SNICAR (snow albedo)** — `mss_cnc_*_col` arrays are the primary coupling point; SNICAR reads them and produces a multi-layer snow albedo that enters `SurfaceAlbedoType` and thus `CanopyFluxesMod` and `BareGroundFluxesMod`. See [canopy_fluxes.md](canopy_fluxes.md) for how the surface albedo feeds back into vegetation energy balance.
- **Snow hydrology** — `SnowWater`, `SnowCompaction`, `CombineSnowLayers`, and `DivideSnowLayers` advect aerosol mass alongside layer water. `AerosolMasses` must run after these layer-manipulation routines. Firn-mode (`use_firn_percolation_and_compaction = .true.`) skips the snow-cap mass scaling in `AerosolMasses` and uses larger `snw_rds_refrz` in `SnowSnicarMod`.
- **Soil biogeochemistry** — `SedYieldMod` uses `decomp_cpools_vr` (litter C in the top soil layer) to compute residue cover, and the sediment yield is consumed by the river routing subsystem (MOSART) and the land-ocean sediment-POC/PON/POP flux accounting.
- **Atmospheric coupling** — `atm2lnd_vars%forc_aer_grc` delivers the 14 aerosol fluxes (or MAM modal fluxes under `#ifdef MODAL_AER`).
- **FAN ammonia volatilization** — `SnowHydrologyMod` also moves FAN chemicals; the aerosol path is independent but shares the layer-advection infrastructure.

## Notes

- `forc_aer_grc(g,1:14)` is the contract between ELM and the atmospheric model/forcing files; its index layout depends on `MODAL_AER`. Users switching between bulk and modal forcing must verify the forcing dataset matches the compiled mode.
- `snw_rds_min = 54.526` microns is the SNICAR "fresh snow" effective radius; it is also used as a clipping value in the snow grain growth solver.
- The erosion model assumes `forc_t(t) > T0 = SHR_CONST_TKFRZ` before any rainfall detachment — i.e., rainfall detachment is suppressed when the surface is frozen.
- `SoilDetachability` and `SoilCohesion` are texture-based lookup functions (sand/silt/clay/gravel proportions) defined further down in `SedYieldMod.F90` — they are private helpers.
- The sediment model treats glacier columns only via the topounit scaling `fglacier`; glaciers themselves are not eroded.
