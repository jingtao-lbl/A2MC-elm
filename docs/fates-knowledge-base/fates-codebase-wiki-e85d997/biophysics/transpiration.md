---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# Transpiration and Soil Moisture Stress (BTRAN)

## Purpose and Scope

This page documents how FATES calculates the soil moisture stress factor `BTRAN` and distributes root water uptake across soil layers when plant hydraulics is disabled. When plant hydraulics is enabled (`hlm_use_planthydro == itrue`), the mechanistic soil-plant-atmosphere water transport model in `FatesPlantHydraulicsMod` replaces the empirical `BTRAN` approach, though a diagnostic `btran_pa` is still produced for the host land model.

For the mechanistic pathway see [Plant Hydraulics](hydraulics/index.md). For how `btran_eff` multiplies into the stomatal conductance solve, see [Photosynthesis and Respiration](photosynthesis.md).

Primary source file: `biogeophys/EDBtranMod.F90`.

## CRITICAL: Parameter Units and Semantics

The two PFT parameters that control the BTRAN stress curve, `smpsc` and `smpso`, are a well-known documentation hazard.

- **Both parameters are in millimetres (mm) of water potential, NOT MPa.** `parameter_files/fates_params_default.cdl:437-442` declares `fates_nonhydro_smpsc:units = "mm"` and `fates_nonhydro_smpso:units = "mm"`.
- **Default values** in `parameter_files/fates_params_default.cdl:1348,1351` are `fates_nonhydro_smpsc = -255000` mm and `fates_nonhydro_smpso = -66000` mm for every PFT. Converted to MPa these are roughly -2.50 MPa and -0.65 MPa, but the parameter file stores and the code consumes them in **mm**.
- **`smpsc` is the water potential at FULL stomatal closure**, and **`smpso` is the water potential at FULL stomatal opening**. The letter suffix matches: `o`=open, `c`=close. `main/EDPftvarcon.F90:75-77` declares them as "Soil water potential at full stomatal opening" and "Soil water potential at full stomatal closure", which `parameter_files/fates_params_default.cdl:439,442` repeats verbatim.
- Because both are negative and `smpsc` is more negative than `smpso`, the inequality `smpsc < smpso < 0` holds. The wet end (rresis→1) is bounded above by `smpso`; the dry end (rresis→0) is bounded below by `smpsc`.

Setting these parameters off by a factor of ~1000, or swapping their roles, silently shifts the entire BTRAN response and is a leading source of spurious calibration results. Always verify units against `fates_params_default.cdl` before assigning new values.

## Implementation Module

`biogeophys/EDBtranMod.F90` exports three public procedures:

| Procedure | Purpose | Output |
| --- | --- | --- |
| `btran_ed` | Main driver for the BTRAN calculation | Updates `bc_out%btran_pa`, `bc_out%rootr_pasl` |
| `get_active_suction_layers` | Marks layers where soil water can be extracted | Sets `bc_out%active_suction_sl` |
| `check_layer_water` | Tests whether a single layer has liquid water above freezing | Returns a logical |

`check_layer_water` (lines 41-56) returns `.true.` only when `h2o_liq_vol > 0` and `tempk > tfrz - 2 K`, so frozen and fully dry layers are excluded from uptake.

## The BTRAN Algorithm

`btran_ed` (lines 88-262) walks the site-patch-PFT hierarchy and, for each `(ft, j)` pair, computes a layer root resistance `rresis`:

```fortran
smp_node = max(smpsc(ft), bc_in(s)%smp_sl(j))
rresis   = min( (bc_in(s)%eff_porosity_sl(j) / bc_in(s)%watsat_sl(j)) *            &
                 (smp_node - smpsc(ft)) / (smpso(ft) - smpsc(ft)), 1._r8 )
```
(`biogeophys/EDBtranMod.F90:160-163`).

Reading the code carefully:

1. `smp_node` is the layer soil matric potential clipped to be no lower (no more negative) than `smpsc`. The host-model `smp_sl(j)` is in **mm**, matching the parameter units.
2. `rresis` is the linear ramp `(smp_node - smpsc) / (smpso - smpsc)`, multiplied by an ice fraction `(eff_porosity / watsat)`, and capped at `1.0`.
3. At the driest end, `smp_node = smpsc` gives `rresis = 0` → complete stomatal closure.
4. At `smp_node = smpso` (and `eff_porosity = watsat`), the numerator equals the denominator and the min clamps to `rresis = 1.0` → no water stress.
5. For any `smp_sl > smpso`, the unclamped value exceeds 1 and the `min(..., 1._r8)` keeps the result at unity.

The `(eff_porosity / watsat)` factor further suppresses uptake in partially frozen layers, because only unfrozen porosity is considered effective.

### Piecewise-linear BTRAN shape

Combining the clamp and the linear ramp gives the conventional piecewise description:

| Layer state | Condition | `rresis` |
| --- | --- | --- |
| Wet (no stress) | `smp_sl >= smpso` | `1.0` |
| Transitional | `smpsc < smp_sl < smpso` | `(smp_sl - smpsc) / (smpso - smpsc)`, scaled by `eff_porosity/watsat` |
| Dry (full stress) | `smp_sl <= smpsc` | `0.0` |

The **width of the transition** is `|smpso - smpsc|` ≈ 189000 mm (~1.85 MPa) with defaults. Narrowing this width makes the PFT behave more like an on-off switch; widening it makes the stress response gentler.

## Layer Weighting and Root Uptake Distribution

The per-PFT wetness factor `cpatch%btran_ft(ft)` is accumulated across layers weighted by root fraction:

```fortran
root_resis(ft,j)     = rootfrac_scr(j) * rresis
cpatch%btran_ft(ft) = sum_j root_resis(ft,j)
```
(`biogeophys/EDBtranMod.F90:165-170`).

Root fractions come from `set_root_fraction` in `biogeochem/FatesAllometryMod.F90`, which uses the two-parameter Zeng (2001) exponential model controlled by PFT parameters `roota` and `rootb` plus a maximum-rooting-depth bound.

Root uptake is then renormalized so the per-layer fractions sum to one across layers that had water (lines 179-185), guaranteeing that the total transpiration flux handed back to the host model is distributed among layers in proportion to both root density and layer water availability.

## Patch-Level Output to the Host Land Model

After the PFT loop, `btran_ed` produces two patch-level outputs via the `bc_out` structure:

- `bc_out(s)%btran_pa(ifp)` — PFT-weighted wetness factor for diagnostic output. The PFT weights are the cohort LAI-weighted stomatal conductances `cpatch%pftgs(ft) = Σ cohort%g_sb_laweight` summed over cohorts (lines 193-198). When `hlm_use_planthydro == itrue`, this branch is skipped and a companion routine `BTranForHLMDiagnosticsFromCohortHydr` in `FatesPlantHydraulicsMod` fills `btran_pa` from the hydraulic `co_hydr%btran` instead (lines 224-235).
- `bc_out(s)%rootr_pasl(ifp,j)` — layer fractions of transpired water. Computed by averaging `root_resis(ft,j)` across PFTs using the same conductance weights (lines 206-218), then rescaled so the layer sum is exactly one within `1e-10` tolerance (lines 237-246).

## Connection to Photosynthesis

Inside `FatesPlantRespPhotosynthMod`, each PFT's `btran_ft` is used as the stomatal multiplier `btran_eff` (line 475). `btran_eff` scales the stomatal conductance intercept and, through the Ball-Berry / Medlyn solve, suppresses net assimilation under dry conditions. See [Photosynthesis and Respiration](photosynthesis.md).

### Salinity stress overlay

When the optional salinity module is active (`do_fates_salinity == .true.`), an additional multiplicative factor `bstress_sal_ft(ft)` is applied after `btran_eff` is assigned:

```fortran
btran_eff = btran_eff * currentPatch%bstress_sal_ft(ft)
```
(`biogeophys/FatesPlantRespPhotosynthMod.F90:488-490`).

`bstress_sal_ft` is computed by `FatesBstressMod.F90` and is independent of the soil moisture pathway. The BTRAN diagnostics reported back to the host do NOT include this salinity factor. This means that under salt stress the effective gs multiplier seen by photosynthesis is `btran_eff × bstress_sal_ft`, while the patch-level `btran_pa` output still reports only the moisture component.

## Key Parameters

| Parameter | Description | Units | Default (all PFTs) | Source |
| --- | --- | --- | --- | --- |
| `fates_nonhydro_smpsc` | Soil water potential at full stomatal closure | mm | -255000 | `fates_params_default.cdl:437-439, 1348` |
| `fates_nonhydro_smpso` | Soil water potential at full stomatal opening | mm | -66000 | `fates_params_default.cdl:440-442, 1351` |
| `fates_allom_zroot_*` / `roota` / `rootb` | Root vertical distribution controls | varies | PFT-specific | `main/EDPftvarcon.F90` |

`smpsc` and `smpso` are stored in `EDPftvarcon_inst%smpsc(:)` and `EDPftvarcon_inst%smpso(:)`. They are PFT-indexed and must satisfy `smpsc < smpso < 0` in mm. If the user writes positive values or supplies MPa-scale numbers (e.g. `-2.0`), the code will still run but the stress curve will be crushed against the wet end and `BTRAN` will effectively be identically one at all soil moisture states.

## Integration with Plant Hydraulics

The BTRAN computation above is executed only when `hlm_use_planthydro == ifalse` (integer flag, not logical). When hydraulics is active (`hlm_use_planthydro == itrue`), FATES bypasses the empirical ramp and relies on the mechanistic leaf water potential passed back from `wkf_plant(stomata_p_media,ft)%p%ftc_from_psi(psi_ag(1))`, as shown in `FatesPlantHydraulicsMod.F90:2651`. The routine `BTranForHLMDiagnosticsFromCohortHydr` then populates `bc_out%btran_pa` from the cohort-level hydraulic `btran`, so the host model always receives a scalar stress diagnostic regardless of which pathway is active.

## Diagnostic Output

Through the `bc_out` interface the host land model receives:

- `bc_out(s)%btran_pa(ifp)` — patch-level moisture wetness factor, `[0, 1]`.
- `bc_out(s)%rootr_pasl(ifp,j)` — fraction of transpiration drawn from each soil layer, summing to `1.0`.
- `bc_out(s)%active_suction_sl(j)` — boolean indicating which layers can currently supply water (frozen/dry layers are `.false.`).

These arrays are consumed by CLM/ELM to compute the soil moisture sink, to report the transpiration wetness diagnostic, and to short-circuit root uptake in frozen soil layers.

## Source References

- `biogeophys/EDBtranMod.F90:88-262` — `btran_ed` implementation
- `biogeophys/EDBtranMod.F90:160-163` — root resistance formula
- `biogeophys/EDBtranMod.F90:206-246` — layer renormalization and patch output
- `main/EDPftvarcon.F90:75-77, 444-448` — `smpsc` / `smpso` declarations and registration
- `parameter_files/fates_params_default.cdl:437-442, 1348-1353` — units and default values
- `biogeophys/FatesPlantRespPhotosynthMod.F90:475, 488-490` — assignment of `btran_eff` and salinity overlay
- `biogeophys/FatesPlantHydraulicsMod.F90:2651` — hydraulic `btran` diagnostic path
