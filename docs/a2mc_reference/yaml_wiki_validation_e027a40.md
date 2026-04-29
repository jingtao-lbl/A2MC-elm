# YAML-Wiki Validation: curated_relationships.yaml vs fates-codebase-wiki-e027a40

**Generated:** 2026-04-28T04:42:34Z

**YAML:** `rag/data/curated_relationships.yaml`
**Wiki:** `docs/fates-knowledge-base/fates-codebase-wiki-e027a40`
**Parameter file:** `docs/fates-knowledge-base/fates_params_info_e027a40.json`
**Output CDL:** `docs/fates-knowledge-base/elm_fates_output_info_e027a40.cdl`

---

## Sanity assessment

- Total YAML parameters: 30
- Total YAML mechanisms: 7
- Total YAML output references: 90 (deduplicated)
- Total wiki .md files: 56

| Dimension | Status | Pass / Total |
|---|---|---|
| A. Parameter coverage in wiki | green | 30/30 |
| B. Mechanism coverage in wiki | green | 7/7 |
| C. Output reference validity | green | 79/79 |
| D. Code-reference resolution | green | 7/7 |
| E. Citation freshness sample | green | 0/0 |

**Overall verdict:** Green

(Green = all dimensions >= 90% pass; Yellow = any dimension 70-90%; Red = any dimension < 70%)

---

## A. Parameter coverage in wiki

- Documented in wiki: 30 / 30
- ABSENT from wiki: 0 (listed below)

All YAML parameters appear in the wiki.

## B. Mechanism coverage in wiki

| Mechanism | Status | Name match form | Ref file | Ref routine | Ref status |
|---|---|---|---|---|---|
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
| `Carbon_Starvation` | `biogeochem/EDMortalityFunctionsMod.F90` | `mortality_rates` | BOTH_FOUND |
| `Cold_Deciduous` | `biogeochem/EDPhysiologyMod.F90` | `phenology_leafonoff` | BOTH_FOUND |
| `ECA_Competition` | `biogeochem/FatesSoilBGCFluxMod.F90` | `-` | FILE_ONLY_BY_DESIGN |
| `PID_Controller` | `parteh/PRTAllometricCNPMod.F90` | `CNPAdjustFRootTargets` | BOTH_FOUND |
| `RD_Competition` | `biogeochem/FatesSoilBGCFluxMod.F90` | `-` | FILE_ONLY_BY_DESIGN |
| `Root_Distribution` | `biogeochem/FatesAllometryMod.F90` | `exponential_2p_root_profile` | BOTH_FOUND |
| `Storage_Allocation` | `parteh/PRTAllometricCNPMod.F90` | `CNPAllocateRemainder` | BOTH_FOUND |

## E. Citation freshness (sample)

- No file citations found in calibration_notes; nothing to validate.

---

## Summary recommendations

- Validation passed; no action needed.
