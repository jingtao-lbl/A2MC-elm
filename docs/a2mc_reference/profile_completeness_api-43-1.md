# Profile Completeness Validation: api-43-1

**Generated:** 2026-04-30T18:56:27+00:00
**Verdict:** Yellow
**Chunks:** 6326  |  **Graph nodes:** 3178

## Summary

| Category | Severity | Summary |
|---|---|---|
| (a) Chunk-tagging distribution | OK | Within bounds |
| (b) Wiki-directory coverage | OK | All 12 path-prefix patterns matched expected chunks |
| (c) YAML-entity coverage | OK | All YAML entities have matching chunks |
| (d) Tier 2 axis distribution | OK | Tier 2 axes: 6 axes, distributions logged |
| (e) Golden chunk counts (per-mode) | WARN | default-elm-sp: expected 4055, got 5650 (delta=+1595); kougarok-parteh2-cnp-eca: expected 4333, got 5973 (delta=+1640); parteh1-carbon-only: expected 4145, got 5740 (delta=+1595) |

## (a) Chunk-tagging distribution

| Metric | col1 |
|---|---|
| Total chunks | 6326 |
| Universal | 5650 (89.3%) |
| YAML-entity tagged | 16 (0.3%) |
| Path-prefix tagged | 660 (10.4%) |
| Orphan (no metadata) | 0 |

**Status:** Within bounds

## (b) Wiki-directory coverage

| Metric | col1 | col2 | col3 |
|---|---|---|---|
| fire/ | 147 | 147 | OK |
| biophysics/hydraulics/ | 112 | 112 | OK |
| logging/ | 69 | 69 | OK |
| biophysics/transpiration.md | 19 | 19 | OK |
| biophysics/photosynthesis.md | 35 | 35 | OK |
| plant-physiology/parteh/cnp_allocation.md | 69 | 69 | OK |
| plant-physiology/parteh/soil_plant_interface.md | 46 | 46 | OK |
| plant-physiology/parteh/carbon_only.md | 25 | 25 | OK |
| advanced/cnp_calibration_guide.md | 54 | 54 | OK |
| advanced/nutrient_competition.md | 28 | 28 | OK |
| plant-physiology/crown_damage.md | 11 | 11 | OK |
| parteh/h2_ | 45 | 45 | OK |

**Status:** All 12 path-prefix patterns matched expected chunks

## (c) YAML-entity coverage

| Metric | col1 |
|---|---|
| YAML parameters | 30 |
| Param chunks present | 30 |
| YAML outputs | 86 |
| Output chunks present | 86 |

**Status:** All YAML entities have matching chunks

## (d) Tier 2 axis distribution

| Metric | col1 | col2 |
|---|---|---|
| fates_spitfire_mode | 676 | 147 |
| use_fates_planthydro | 676 | 131 |
| use_fates_logging | 676 | 69 |
| use_fates_sp | 676 | 0 |
| use_fates_ed_prescribed_phys | 676 | 35 |
| use_fates_fixed_biogeog | 676 | 0 |

**Status:** Tier 2 axes: 6 axes, distributions logged

## (e) Golden chunk counts (per-mode)

| Metric | col1 | col2 | col3 | col4 |
|---|---|---|---|---|
| default-elm-sp | 4055 | 5650 | 1595 | DRIFT |
| kougarok-parteh2-cnp-eca | 4333 | 5973 | 1640 | DRIFT |
| parteh1-carbon-only | 4145 | 5740 | 1595 | DRIFT |

**Status:** default-elm-sp: expected 4055, got 5650 (delta=+1595); kougarok-parteh2-cnp-eca: expected 4333, got 5973 (delta=+1640); parteh1-carbon-only: expected 4145, got 5740 (delta=+1595)
