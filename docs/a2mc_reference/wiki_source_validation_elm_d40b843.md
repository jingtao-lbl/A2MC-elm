# Wiki-Source Validation: elm-codebase-wiki-d40b843 vs src

**Generated:** 2026-07-06T23:34:52Z

**Wiki:** `docs/elm-knowledge-base/elm-codebase-wiki-d40b843`
**Source:** `~/E3SM_FATES_api43/components/elm/src`
**Parameter file:** none

---

## Sanity assessment

- Total wiki .md files: 42
- Total source .F90 files: 777
- Total wiki citations extracted: 542
- Total parameter mentions: 194 (23 unique)
- Total module-file mentions: 106 unique

| Dimension | Status | Pass / Total |
|---|---|---|
| 1. File-citation existence | green | 542/542 |
| 2. Line-bound validity | green | 542/542 |
| 3. Routine declaration presence | green | 49/50 |
| 4. Parameter-name validity | green | 0/0 |
| 5. Module-file presence | green | 106/106 |

**Overall verdict:** Green

(Green = all dimensions >= 90% pass; Yellow = any dimension 70-90%; Red = any dimension < 70%)

---

## 1. File-citation existence

- Total citations: 542
- File EXISTS:    542
- File ABSENT:    0

All citations resolve to existing files.

## 2. Line-bound validity

- Citations checked: 542 (only those that passed Dim 1)
- Within bounds:     542
- OVER file length:  0

All cited line numbers are within file bounds.

## 3. Routine declaration presence

- Routine candidates checked: 50 (top backtick identifiers with routine-hint context)
- Found in source:           49
- NOT FOUND:                 1

### Candidate routine names not found in source

| Identifier | Mentions | First wiki file |
|---|---|---|
| `FatesReadPFTs` | 4 | `biogeochem/index.md` |

## 4. Parameter-name validity

- No --param-file supplied; skipping parameter-name validation.

## 5. Module-file presence

- Unique module files mentioned: 106
- Found in source tree:          106
- NOT FOUND:                     0

All mentioned module files exist in source.

---

## Summary recommendations

- Validation passed; no action needed.
