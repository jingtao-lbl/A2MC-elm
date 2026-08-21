# YAML-Wiki Validation: curated_relationships.yaml vs fates-codebase-wiki-e027a40

**Generated:** 2026-07-19T14:15:51Z

**YAML:** `rag/data/curated_relationships_api-43-1.yaml`
**Wiki:** `docs/fates-knowledge-base/fates-codebase-wiki-e027a40`
**Parameter file:** `docs/fates-knowledge-base/fates_params_info_e027a40.json`
**Output CDL:** `docs/fates-knowledge-base/elm_fates_output_info_e027a40.cdl`

---

## Sanity assessment

- Total YAML parameters: 31
- Total YAML mechanisms: 8
- Total YAML output references: 90 (deduplicated)
- Total wiki .md files: 56

| Dimension | Status | Pass / Total |
|---|---|---|
| A. Parameter coverage in wiki | green | 31/31 |
| B. Mechanism coverage in wiki | yellow | 7/8 |
| C. Output reference validity | green | 79/79 |
| D. Code-reference resolution | green | 8/8 |
| E. Citation freshness sample | green | 2/2 |
| F. applies_in: schema (Phase B) | green | 21/21 |

**Overall verdict:** Yellow

(Green = all dimensions >= 90% pass; Yellow = any dimension 70-90%; Red = any dimension < 70%)

---

## A. Parameter coverage in wiki

- Documented in wiki: 31 / 31
- ABSENT from wiki: 0 (listed below)

All YAML parameters appear in the wiki.

## B. Mechanism coverage in wiki

| Mechanism | Status | Name match form | Ref file | Ref routine | Ref status |
|---|---|---|---|---|---|
| `Biochemical_Phosphatase` | PARTIAL | - | main/EDPftvarcon.F90 | FatesCheckParams | BOTH |
| `Carbon_Starvation` | DOCUMENTED | Carbon Starvation | biogeochem/EDMortalityFunctionsMod.F90 | mortality_rates | BOTH |
| `Cold_Deciduous` | DOCUMENTED | Cold Deciduous | biogeochem/EDPhysiologyMod.F90 | phenology_leafonoff | BOTH |
| `ECA_Competition` | DOCUMENTED | ECA Competition | biogeochem/FatesSoilBGCFluxMod.F90 | - | FILE_ONLY |
| `PID_Controller` | DOCUMENTED | PID Controller | parteh/PRTAllometricCNPMod.F90 | CNPAdjustFRootTargets | BOTH |
| `RD_Competition` | DOCUMENTED | RD Competition | biogeochem/FatesSoilBGCFluxMod.F90 | - | FILE_ONLY |
| `Root_Distribution` | DOCUMENTED | Root Distribution | biogeochem/FatesAllometryMod.F90 | exponential_2p_root_profile | BOTH |
| `Storage_Allocation` | DOCUMENTED | Storage Allocation | parteh/PRTAllometricCNPMod.F90 | CNPAllocateRemainder | BOTH |

## C. Output reference validity

- CDL-missing: 0; wiki-missing: 0; both-pass: 79

All YAML output references resolve in both CDL and wiki.

## D. Code-reference resolution

| Mechanism | Ref file | Ref routine | Classification |
|---|---|---|---|
| `Biochemical_Phosphatase` | `main/EDPftvarcon.F90` | `FatesCheckParams` | BOTH_FOUND |
| `Carbon_Starvation` | `biogeochem/EDMortalityFunctionsMod.F90` | `mortality_rates` | BOTH_FOUND |
| `Cold_Deciduous` | `biogeochem/EDPhysiologyMod.F90` | `phenology_leafonoff` | BOTH_FOUND |
| `ECA_Competition` | `biogeochem/FatesSoilBGCFluxMod.F90` | `-` | FILE_ONLY_BY_DESIGN |
| `PID_Controller` | `parteh/PRTAllometricCNPMod.F90` | `CNPAdjustFRootTargets` | BOTH_FOUND |
| `RD_Competition` | `biogeochem/FatesSoilBGCFluxMod.F90` | `-` | FILE_ONLY_BY_DESIGN |
| `Root_Distribution` | `biogeochem/FatesAllometryMod.F90` | `exponential_2p_root_profile` | BOTH_FOUND |
| `Storage_Allocation` | `parteh/PRTAllometricCNPMod.F90` | `CNPAllocateRemainder` | BOTH_FOUND |

## E. Citation freshness (sample)


| Parameter | Cited file | Status |
|---|---|---|
| `fates_cnp_eca_alpha_ptase` | `EDPftvarcon.F90` | OK |
| `fates_cnp_eca_lambda_ptase` | `EDPftvarcon.F90` | OK |

## F. applies_in: schema (Phase B)


| Entry | Severity | Axis | Value | Message |
|---|---|---|---|---|
| `parameters.fates_cnp_pid_kp` | OK | — | — | all axes valid |
| `parameters.fates_cnp_pid_ki` | OK | — | — | all axes valid |
| `parameters.fates_cnp_pid_kd` | OK | — | — | all axes valid |
| `parameters.fates_cnp_vmax_p` | OK | — | — | all axes valid |
| `parameters.fates_cnp_eca_vmax_ptase` | OK | — | — | all axes valid |
| `parameters.fates_cnp_eca_km_ptase` | OK | — | — | all axes valid |
| `parameters.fates_cnp_eca_decompmicc` | OK | — | — | all axes valid |
| `parameters.fates_cnp_eca_plant_escalar` | OK | — | — | all axes valid |
| `parameters.fates_cnp_nitr_store_ratio` | OK | — | — | all axes valid |
| `parameters.fates_cnp_phos_store_ratio` | OK | — | — | all axes valid |
| `parameters.fates_cnp_store_ovrflw_frac` | OK | — | — | all axes valid |
| `parameters.fates_cnp_turnover_nitr_retrans` | OK | — | — | all axes valid |
| `parameters.fates_cnp_turnover_phos_retrans` | OK | — | — | all axes valid |
| `parameters.fates_cnp_nfix1` | OK | — | — | all axes valid |
| `parameters.fates_cnp_eca_km_nh4` | OK | — | — | all axes valid |
| `parameters.fates_cnp_eca_km_no3` | OK | — | — | all axes valid |
| `parameters.fates_cnp_eca_km_p` | OK | — | — | all axes valid |
| `mechanisms.PID_Controller` | OK | — | — | all axes valid |
| `mechanisms.ECA_Competition` | OK | — | — | all axes valid |
| `mechanisms.RD_Competition` | OK | — | — | all axes valid |
| `mechanisms.Biochemical_Phosphatase` | OK | — | — | all axes valid |

---

## Summary recommendations

- Dimension B at 87%: 1 mechanisms not fully documented (`Biochemical_Phosphatase`). Update mechanism names to match wiki vocabulary or extend wiki coverage.
