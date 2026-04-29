# Wiki-Source Validation: fates-codebase-wiki-e027a40 vs fates

**Generated:** 2026-04-28T04:42:22Z

**Wiki:** `docs/fates-knowledge-base/fates-codebase-wiki-e027a40`
**Source:** `/Users/jingtao/Desktop/Work/SourceCode/ELM_FATES/E3SM_FATES_api43-1/components/elm/src/external_models/fates`
**Parameter file:** `docs/fates-knowledge-base/fates_params_info_e027a40.json`

---

## Sanity assessment

- Total wiki .md files: 56
- Total source .F90 files: 89
- Total wiki citations extracted: 974
- Total parameter mentions: 449 (140 unique)
- Total module-file mentions: 64 unique

| Dimension | Status | Pass / Total |
|---|---|---|
| 1. File-citation existence | green | 974/974 |
| 2. Line-bound validity | green | 974/974 |
| 3. Routine declaration presence | green | 49/50 |
| 4. Parameter-name validity | green | 136/140 |
| 5. Module-file presence | green | 61/64 |

**Overall verdict:** Green

(Green = all dimensions >= 90% pass; Yellow = any dimension 70-90%; Red = any dimension < 70%)

---

## 1. File-citation existence

- Total citations: 974
- File EXISTS:    974
- File ABSENT:    0

All citations resolve to existing files.

## 2. Line-bound validity

- Citations checked: 974 (only those that passed Dim 1)
- Within bounds:     974
- OVER file length:  0

All cited line numbers are within file bounds.

## 3. Routine declaration presence

- Routine candidates checked: 50 (top backtick identifiers with routine-hint context)
- Found in source:           49
- NOT FOUND:                 1

### Candidate routine names not found in source

| Identifier | Mentions | First wiki file |
|---|---|---|
| `float` | 2 | `getting-started/parameter_tools.md` |

## 4. Parameter-name validity

- Unique fates_* mentions: 140
- Match parameter file:    136
- NOT IN PARAMETER FILE:   4

### Wiki-only parameter names (not in param file)

| Parameter | Mentions | First wiki file |
|---|---|---|
| `fates_pft` | 19 | `advanced/cnp_calibration_guide.md` |
| `fates_cnp_decompmicc` | 5 | `plant-physiology/parteh/cnp_allocation.md` |
| `fates_turnover_leaf` | 3 | `plant-physiology/index.md` |
| `fates_cnp_nfix` | 1 | `advanced/cnp_calibration_guide.md` |

## 5. Module-file presence

- Unique module files mentioned: 64
- Found in source tree:          61
- NOT FOUND:                     3

### Module files mentioned in wiki but missing from source

| Module file | First wiki file |
|---|---|
| `CanopyFluxesMod.F90` | `biophysics/hydraulics/index.md` |
| `EDSurfaceAlbedoMod.F90` | `biophysics/index.md` |
| `SurfaceAlbedoMod.F90` | `biophysics/index.md` |

---

## Summary recommendations

- Validation passed; no action needed.
