# RAG Comparison: api-31-0 vs api-43-1

**Generated:** 2026-04-27T21:43:13

**Profile A:** api-31-0
- Graph: `Offline/rag_scratch/api-31-0/graph.json`
- Wiki: `docs/fates-knowledge-base/fates-codebase-wiki-e85d997`
- Parameter file: `docs/fates-knowledge-base/fates_params_info.cdl`

**Profile B:** api-43-1
- Graph: `rag/fates_knowledge_graph.json`
- Wiki: `docs/fates-knowledge-base/fates-codebase-wiki-e027a40`
- Parameter file: `docs/fates-knowledge-base/fates_params_info_e027a40.json`

---

## Sanity assessment

Per `docs/18_ELM_FATES_Version_Association_Plan.md` §4.9 thresholds:

- **Green**: 10-50 params added, 0-5 params removed, 0-5 renamed, wiki avg Jaccard > 0.5 -> proceed
- **Yellow**: 50+ added OR 5+ removed OR many low-similarity rewrites -> review
- **Red**: >100 added/removed OR >50% files near zero similarity -> wiki regen broke

This diff: **Green**

- Params added: 34
- Params removed: 18
- Params renamed: 5
- Wiki avg Jaccard: 0.654

- Profile names indicate 12-major API distance; thresholds scaled (Yellow at >65 removed, >65 renamed).
- All thresholds within Green band; safe to proceed.

## 1. Parameter Inventory

- Profile A (api-31-0): 290 parameters
- Profile B (api-43-1): 306 parameters

### Added in B (only in B): 34 params

| Parameter | Category | Units |
| --- | --- | --- |
| fates_allom_h2cd1 | allom | variable |
| fates_allom_h2cd2 | allom | variable |
| fates_landuse_crop_lu_pft_vector | landuse | NA |
| fates_landuse_grazing_carbon_use_eff | landuse | unitless |
| fates_landuse_grazing_maxheight | landuse | m |
| fates_landuse_grazing_nitrogen_use_eff | landuse | unitless |
| fates_landuse_grazing_palatability | landuse | unitless 0-1 |
| fates_landuse_grazing_phosphorus_use_eff | landuse | unitless |
| fates_landuse_grazing_rate | landuse | 1/day |
| fates_landuse_harvest_pprod10 | landuse | fraction |
| fates_landuse_luc_frac_burned | landuse | fraction |
| fates_landuse_luc_frac_exported | landuse | fraction |
| fates_landuse_luc_pprod10 | landuse | fraction |
| fates_leaf_agross_btran_model | leaf | index |
| fates_leaf_fnps | leaf | fraction |
| fates_leafn_vert_scaler_coeff1 | leafn | unitless |
| fates_leafn_vert_scaler_coeff2 | leafn | unitless |
| fates_maintresp_leaf_vert_scaler_coeff2 | maintresp | unitless |
| fates_max_nocomp_pfts_by_landuse | max | count |
| fates_maxpatches_by_landuse | maxpatches | count |
| fates_phen_leaf_habit | phen | flag |
| fates_recruit_init_seed | recruit | kg/m2 |
| fates_rxfire_AB | rxfire | fraction/day |
| fates_rxfire_fuel_min | rxfire | kgC/m2 |
| fates_rxfire_max_threshold | rxfire | kJ/m/s or kW/m |
| fates_rxfire_min_frac | rxfire | fraction |
| fates_rxfire_min_threshold | rxfire | kJ/m/s or kW/m |
| fates_rxfire_rh_lwthreshold | rxfire | % |
| fates_rxfire_rh_upthreshold | rxfire | % |
| fates_rxfire_temp_lwthreshold | rxfire | degree C |
| fates_rxfire_temp_upthreshold | rxfire | degree C |
| fates_rxfire_wind_lwthreshold | rxfire | % |
| fates_rxfire_wind_upthreshold | rxfire | % |
| fates_turnover_leaf_ustory | turnover | yr |

### Removed in B (only in A): 18 params

| Parameter | Category | Units |
| --- | --- | --- |
| fates_allom_crown_depth_frac | allom | fraction |
| fates_cnp_km_nh4 | cnp | None |
| fates_cnp_km_no3 | cnp | None |
| fates_cnp_km_p | cnp | None |
| fates_cnp_vmax_ptase | cnp | None |
| fates_fire_fdi_b | fire | NA |
| fates_hydro_solver | hydro | unitless |
| fates_landuse_pprodharv10_forest_mean | landuse | fraction |
| fates_leaf_photo_tempsens_model | leaf | unitless |
| fates_leaf_stomatal_assim_model | leaf | unitless |
| fates_leaf_theta_cj_c3 | leaf | unitless |
| fates_leaf_theta_cj_c4 | leaf | unitless |
| fates_maxpatch_primary | maxpatch | count |
| fates_maxpatch_secondary | maxpatch | count |
| fates_phen_evergreen | phen | logical flag |
| fates_phen_season_decid | phen | logical flag |
| fates_phen_stress_decid | phen | logical flag |
| fates_regeneration_model | regeneration | - |

### Renamed (fuzzy match, similarity >= 0.7): 5

| Old (A) | New (B) | Similarity |
| --- | --- | --- |
| fates_leaf_stomatal_model | fates_leaf_stomatal_btran_model | 0.89 |
| fates_turnover_leaf | fates_turnover_leaf_canopy | 0.84 |
| fates_fire_fdi_a | fates_rxfire_fuel_max | 0.76 |
| fates_rad_model | fates_allom_dmode | 0.75 |
| fates_maintresp_leaf_model | fates_maintresp_leaf_vert_scaler_coeff1 | 0.71 |

### Common (in both): 267 parameters

## 2. Graph Structure

### Node counts

| Node type | A | B | Δ |
| --- | --- | --- | --- |
| Category | 39 | 41 | +2 |
| Dimension | 58 | 38 | -20 |
| Mechanism | 7 | 7 | +0 |
| Module | 4 | 5 | +1 |
| Output | 291 | 505 | +214 |
| PFT | 3 | 3 | +0 |
| Parameter | 893 | 939 | +46 |
| **Total** | 1295 | 1538 | +243 |

### Edge counts

| Edge type | A | B | Δ |
| --- | --- | --- | --- |
| affects | 169 | 214 | +45 |
| belongs_to | 603 | 633 | +30 |
| competes_with | 3 | 3 | +0 |
| contains | 893 | 939 | +46 |
| controls | 77 | 93 | +16 |
| has_dimension | 360 | 598 | +238 |
| implemented_in | 7 | 7 | +0 |
| related_to | 85 | 133 | +48 |
| **Total** | 2197 | 2620 | +423 |

### Per-type node adds/removes

| Node type | Added in B | Removed in B |
| --- | --- | --- |
| Category | 4 | 2 |
| Dimension | 4 | 24 |
| Module | 5 | 4 |
| Output | 273 | 59 |
| Parameter | 96 | 50 |

### Per-type edge adds/removes

| Edge type | Added in B | Removed in B |
| --- | --- | --- |
| affects | 49 | 4 |
| belongs_to | 57 | 27 |
| contains | 96 | 50 |
| controls | 16 | 0 |
| has_dimension | 261 | 23 |
| implemented_in | 7 | 7 |
| related_to | 56 | 8 |

## 3. Wiki Content

- Profile A wiki: 55 files at `docs/fates-knowledge-base/fates-codebase-wiki-e85d997`
- Profile B wiki: 56 files at `docs/fates-knowledge-base/fates-codebase-wiki-e027a40`
- Average Jaccard for files in both: **0.654**

### Files added in B: 1

| Path | Lines |
| --- | --- |
| fire/managed_fire.md | 215 |

### Files removed in B: 0

_(none)_

### Likely wiki renames (path similarity >= 0.6): 0

_(none)_

### Files in both: 55

Top 20 most-changed (least similar first):

| Path | Lines A->B | Jaccard | Verdict |
| --- | --- | --- | --- |
| index.md | 88->115 | 0.391 | Major rewrite |
| getting-started/parameter_tools.md | 317->381 | 0.396 | Major rewrite |
| fire/index.md | 206->262 | 0.445 | Major rewrite |
| biophysics/radiation.md | 162->228 | 0.469 | Major rewrite |
| fire/spread.md | 375->442 | 0.475 | Major rewrite |
| canopy-structure/index.md | 186->270 | 0.480 | Major rewrite |
| fire/ignition.md | 184->228 | 0.488 | Major rewrite |
| getting-started/parameter_system.md | 306->383 | 0.503 | Minor edit |
| plant-physiology/mortality.md | 171->236 | 0.508 | Minor edit |
| biophysics/photosynthesis.md | 185->237 | 0.537 | Minor edit |
| canopy-structure/lai_sai.md | 154->254 | 0.540 | Minor edit |
| canopy-structure/ppa.md | 294->424 | 0.546 | Minor edit |
| fire/effects.md | 166->199 | 0.565 | Minor edit |
| plant-physiology/allometry.md | 236->371 | 0.566 | Minor edit |
| advanced/extensibility.md | 241->295 | 0.575 | Minor edit |
| plant-physiology/index.md | 131->180 | 0.578 | Minor edit |
| core-dynamics/daily_loop.md | 182->218 | 0.585 | Minor edit |
| biophysics/index.md | 179->205 | 0.590 | Minor edit |
| output/history/pipeline.md | 162->196 | 0.598 | Minor edit |
| getting-started/index.md | 177->212 | 0.609 | Minor edit |

## 4. Parameter File

- Profile A: `docs/fates-knowledge-base/fates_params_info.cdl` (cdl, 290 parameters)
- Profile B: `docs/fates-knowledge-base/fates_params_info_e027a40.json` (json, 311 parameters)

### Parameters added: 40

| Parameter | Default | Dims | Units |
| --- | --- | --- | --- |
| fates_allom_dmode | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] | fates_pft | index |
| fates_allom_h2cd1 | [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.95, 0.95, 0.95, 0.95, 0.... | fates_pft | variable |
| fates_allom_h2cd2 | [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1... | fates_pft | variable |
| fates_landuse_crop_lu_pft_vector | [-999, -999, -999, -999, 13] | fates_landuseclass | NA |
| fates_landuse_grazing_carbon_use_eff | [0.0] | (scalar) | unitless |
| fates_landuse_grazing_maxheight | [1.0] | (scalar) | m |
| fates_landuse_grazing_nitrogen_use_eff | [0.25] | (scalar) | unitless |
| fates_landuse_grazing_palatability | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1... | fates_pft | unitless 0-1 |
| fates_landuse_grazing_phosphorus_use_eff | [0.5] | (scalar) | unitless |
| fates_landuse_grazing_rate | [0.0, 0.0, 0.0, 0.0, 0.0] | fates_landuseclass | 1/day |
| fates_landuse_harvest_pprod10 | [1.0, 0.75, 0.75, 0.75, 1.0, 0.75, 1.0, 1.0, 1.0, 1.0, 1.... | fates_pft | fraction |
| fates_landuse_luc_frac_burned | [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0... | fates_pft | fraction |
| fates_landuse_luc_frac_exported | [0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.2, 0.2, 0.2, 0.2, 0.2, 0... | fates_pft | fraction |
| fates_landuse_luc_pprod10 | [1.0, 0.75, 0.75, 0.75, 1.0, 0.75, 1.0, 1.0, 1.0, 1.0, 1.... | fates_pft | fraction |
| fates_landuseclass_name | ['primaryland', 'secondaryland', 'rangeland', 'pasturelan... | fates_landuseclass | unitless - string |
| fates_leaf_agross_btran_model | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] | fates_pft | index |
| fates_leaf_fnps | [0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.... | fates_pft | fraction |
| fates_leaf_stomatal_btran_model | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] | fates_pft | index |
| fates_leafn_vert_scaler_coeff1 | [0.00963, 0.00963, 0.00963, 0.00963, 0.00963, 0.00963, 0.... | fates_pft | unitless |
| fates_leafn_vert_scaler_coeff2 | [2.43, 2.43, 2.43, 2.43, 2.43, 2.43, 2.43, 2.43, 2.43, 2.... | fates_pft | unitless |
| fates_maintresp_leaf_vert_scaler_coeff1 | [0.00963, 0.00963, 0.00963, 0.00963, 0.00963, 0.00963, 0.... | fates_pft | unitless |
| fates_maintresp_leaf_vert_scaler_coeff2 | [2.43, 2.43, 2.43, 2.43, 2.43, 2.43, 2.43, 2.43, 2.43, 2.... | fates_pft | unitless |
| fates_max_nocomp_pfts_by_landuse | [4, 4, 1, 1, 1] | fates_landuseclass | count |
| fates_maxpatches_by_landuse | [9, 4, 1, 1, 1] | fates_landuseclass | count |
| fates_phen_leaf_habit | [1, 1, 2, 1, 3, 2, 1, 3, 2, 1, 2, 2, 3, 3] | fates_pft | flag |
| fates_recruit_init_seed | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... | fates_pft | kg/m2 |
| fates_rxfire_AB | [0.01] | (scalar) | fraction/day |
| fates_rxfire_fuel_max | [1.5] | (scalar) | kgC/m2 |
| fates_rxfire_fuel_min | [0.5] | (scalar) | kgC/m2 |
| fates_rxfire_max_threshold | [500.0] | (scalar) | kJ/m/s or kW/m |
| fates_rxfire_min_frac | [0.1] | (scalar) | fraction |
| fates_rxfire_min_threshold | [50.0] | (scalar) | kJ/m/s or kW/m |
| fates_rxfire_rh_lwthreshold | [30.0] | (scalar) | % |
| fates_rxfire_rh_upthreshold | [55.0] | (scalar) | % |
| fates_rxfire_temp_lwthreshold | [5.0] | (scalar) | degree C |
| fates_rxfire_temp_upthreshold | [30.0] | (scalar) | degree C |
| fates_rxfire_wind_lwthreshold | [2.0] | (scalar) | % |
| fates_rxfire_wind_upthreshold | [10.0] | (scalar) | % |
| fates_turnover_leaf_canopy | [[1.5, 4.0, 1.0, 1.5, 1.0, 1.0, 1.5, 1.0, 1.0, 1.5, 1.0, ... | fates_leafage_class, fates_pft | yr |
| fates_turnover_leaf_ustory | [[1.5, 4.0, 1.0, 1.5, 1.0, 1.0, 1.5, 1.0, 1.0, 1.5, 1.0, ... | fates_leafage_class, fates_pft | yr |

### Parameters removed: 19

| Parameter | Last default (A) |
| --- | --- |
| fates_allom_crown_depth_frac |  |
| fates_fire_fdi_a |  |
| fates_fire_fdi_b |  |
| fates_hydro_solver |  |
| fates_landuse_pprodharv10_forest_mean |  |
| fates_leaf_photo_tempsens_model |  |
| fates_leaf_stomatal_assim_model |  |
| fates_leaf_stomatal_model |  |
| fates_leaf_theta_cj_c3 |  |
| fates_leaf_theta_cj_c4 |  |
| fates_maintresp_leaf_model |  |
| fates_maxpatch_primary |  |
| fates_maxpatch_secondary |  |
| fates_phen_evergreen |  |
| fates_phen_season_decid |  |
| fates_phen_stress_decid |  |
| fates_rad_model |  |
| fates_regeneration_model |  |
| fates_turnover_leaf |  |

### Parameters with changed defaults: 271

| Parameter | A default | B default |
| --- | --- | --- |
| fates_alloc_organ_id |  | [1, 2, 3, 6] |
| fates_alloc_organ_name |  | ['leaf', 'fine root', 'sapwood', 'structure'] |
| fates_alloc_organ_priority |  | [[1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [2, 2, 2, 2,... |
| fates_alloc_storage_cushion |  | [1.2, 1.2, 1.2, 1.2, 2.4, 1.2, 1.2, 2.4, 1.2, 1.5, 1.4, 1... |
| fates_alloc_store_priority_frac |  | [0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.7, 0.6, 0... |
| fates_allom_agb1 |  | [0.0673, 0.1364012, 0.0393057, 0.2653695, 0.0673, 0.07286... |
| fates_allom_agb2 |  | [0.976, 0.9449041, 1.087335, 0.8321321, 0.976, 1.0373211,... |
| fates_allom_agb3 |  | [1.94, 1.94, 1.94, 1.94, 1.94, 1.94, 1.94, 1.94, 1.94, 2.... |
| fates_allom_agb4 |  | [0.931, 0.931, 0.931, 0.931, 0.931, 0.931, 0.931, 0.931, ... |
| fates_allom_agb_frac |  | [0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 1... |
| fates_allom_amode |  | [3, 3, 3, 3, 3, 3, 1, 1, 1, 1, 1, 5, 5, 5] |
| fates_allom_blca_expnt_diff |  | [-0.12, -0.34, -0.32, -0.22, -0.12, -0.35, 0.0, 0.0, 0.0,... |
| fates_allom_cmode |  | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] |
| fates_allom_d2bl1 |  | [0.04, 0.07, 0.07, 0.01, 0.04, 0.07, 0.07, 0.07, 0.07, 0.... |
| fates_allom_d2bl2 |  | [1.6019679, 1.5234373, 1.3051237, 1.9621397, 1.6019679, 1... |
| fates_allom_d2bl3 |  | [0.55, 0.55, 0.55, 0.55, 0.55, 0.55, 0.55, 0.55, 0.55, 0.... |
| fates_allom_d2ca_coefficient_max |  | [0.2715891, 0.3693718, 1.0787259, 0.0579297, 0.2715891, 1... |
| fates_allom_d2ca_coefficient_min |  | [0.2715891, 0.3693718, 1.0787259, 0.0579297, 0.2715891, 1... |
| fates_allom_d2h1 |  | [78.4087704, 306.842667, 106.8745821, 104.3586841, 78.408... |
| fates_allom_d2h2 |  | [0.8124383, 0.752377, 0.9471302, 1.1146973, 0.8124383, 0.... |
| fates_allom_d2h3 |  | [47.6666164, 196.6865691, 93.9790461, 160.6835089, 47.666... |
| fates_allom_dbh_maxheight |  | [1000.0, 1000.0, 1000.0, 1000.0, 1000.0, 1000.0, 3.0, 3.0... |
| fates_allom_fmode |  | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] |
| fates_allom_fnrt_prof_a |  | [7.0, 7.0, 7.0, 7.0, 6.0, 6.0, 7.0, 7.0, 7.0, 7.0, 7.0, 1... |
| fates_allom_fnrt_prof_b |  | [1.0, 2.0, 2.0, 1.0, 2.0, 2.0, 1.5, 1.5, 1.5, 1.5, 1.5, 2... |
| fates_allom_fnrt_prof_mode |  | [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3] |
| fates_allom_frbstor_repro |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_allom_hmode |  | [5, 5, 5, 5, 5, 5, 1, 1, 1, 1, 1, 3, 3, 3] |
| fates_allom_l2fr |  | [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0... |
| fates_allom_la_per_sa_int |  | [0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0... |
| fates_allom_la_per_sa_slp |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_allom_lmode |  | [2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 5, 5, 5] |
| fates_allom_sai_scaler |  | [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0... |
| fates_allom_smode |  | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2] |
| fates_allom_stmode |  | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1] |
| fates_allom_zroot_k |  | [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10... |
| fates_allom_zroot_max_dbh |  | [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 2.0, 2.0, 2.0,... |
| fates_allom_zroot_max_z |  | [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, ... |
| fates_allom_zroot_min_dbh |  | [1.0, 1.0, 1.0, 2.5, 2.5, 2.5, 0.1, 0.1, 0.1, 0.1, 0.1, 0... |
| fates_allom_zroot_min_z |  | [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, ... |
| fates_c2b |  | [2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2... |
| fates_canopy_closure_thresh |  | [0.8] |
| fates_cnp_eca_alpha_ptase |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_cnp_eca_decompmicc |  | [280.0, 280.0, 280.0, 280.0, 280.0, 280.0, 280.0, 280.0, ... |
| fates_cnp_eca_km_nh4 |  | [0.14, 0.14, 0.14, 0.14, 0.14, 0.14, 0.14, 0.14, 0.14, 0.... |
| fates_cnp_eca_km_no3 |  | [0.27, 0.27, 0.27, 0.27, 0.27, 0.27, 0.27, 0.27, 0.27, 0.... |
| fates_cnp_eca_km_p |  | [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0... |
| fates_cnp_eca_km_ptase |  | [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1... |
| fates_cnp_eca_lambda_ptase |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_cnp_eca_plant_escalar |  | [1.25e-05] |
| fates_cnp_eca_vmax_ptase |  | [5e-09, 5e-09, 5e-09, 5e-09, 5e-09, 5e-09, 5e-09, 5e-09, ... |
| fates_cnp_nfix1 |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_cnp_nitr_store_ratio |  | [1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1... |
| fates_cnp_phos_store_ratio |  | [1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1... |
| fates_cnp_pid_kd |  | [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0... |
| fates_cnp_pid_ki |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_cnp_pid_kp |  | [0.0005, 0.0005, 0.0005, 0.0005, 0.0005, 0.0005, 0.0005, ... |
| fates_cnp_prescribed_nuptake |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_cnp_prescribed_puptake |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_cnp_store_ovrflw_frac |  | [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1... |
| fates_cnp_turnover_nitr_retrans |  | [[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0... |
| fates_cnp_turnover_phos_retrans |  | [[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0... |
| fates_cnp_vmax_nh4 |  | [2.5e-09, 2.5e-09, 2.5e-09, 2.5e-09, 2.5e-09, 2.5e-09, 2.... |
| fates_cnp_vmax_no3 |  | [2.5e-09, 2.5e-09, 2.5e-09, 2.5e-09, 2.5e-09, 2.5e-09, 2.... |
| fates_cnp_vmax_p |  | [5e-10, 5e-10, 5e-10, 5e-10, 5e-10, 5e-10, 5e-10, 5e-10, ... |
| fates_cohort_age_fusion_tol |  | [0.08] |
| fates_cohort_size_fusion_tol |  | [0.08] |
| fates_comp_excln |  | [-1.0] |
| fates_damage_canopy_layer_code |  | [1] |
| fates_damage_event_code |  | [1] |
| fates_damage_frac |  | [0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.... |
| fates_damage_mort_p1 |  | [9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9... |
| fates_damage_mort_p2 |  | [5.5, 5.5, 5.5, 5.5, 5.5, 5.5, 5.5, 5.5, 5.5, 5.5, 5.5, 5... |
| fates_damage_recovery_scalar |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_dev_arbitrary |  | [None] |
| fates_dev_arbitrary_pft |  | [None, None, None, None, None, None, None, None, None, No... |
| fates_fire_FBD |  | [15.4, 16.8, 19.6, 999.0, 4.0, 4.0] |
| fates_fire_SAV |  | [13.0, 3.58, 0.98, 0.2, 66.0, 66.0] |
| fates_fire_active_crown_fire |  | [0] |
| fates_fire_alpha_SH |  | [0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0... |
| fates_fire_bark_scaler |  | [0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.07, 0.... |
| fates_fire_cg_strikes |  | [0.2] |
| fates_fire_crown_kill |  | [0.775, 0.775, 0.775, 0.775, 0.775, 0.775, 0.775, 0.775, ... |
| fates_fire_drying_ratio |  | [66000.0] |
| fates_fire_durat_slope |  | [-11.06] |
| fates_fire_fdi_alpha |  | [0.00037] |
| fates_fire_fuel_energy |  | [18000.0] |
| fates_fire_low_moisture_Coeff |  | [1.12, 1.09, 0.98, 0.8, 1.15, 1.15] |
| fates_fire_low_moisture_Slope |  | [0.62, 0.72, 0.85, 0.8, 0.62, 0.62] |
| fates_fire_max_durat |  | [240.0] |
| fates_fire_mid_moisture |  | [0.72, 0.51, 0.38, 1.0, 0.8, 0.8] |
| fates_fire_mid_moisture_Coeff |  | [2.35, 1.47, 1.06, 0.8, 3.2, 3.2] |
| fates_fire_mid_moisture_Slope |  | [2.35, 1.47, 1.06, 0.8, 3.2, 3.2] |
| fates_fire_min_moisture |  | [0.18, 0.12, 0.0, 0.0, 0.24, 0.24] |
| fates_fire_miner_damp |  | [0.41739] |
| fates_fire_miner_total |  | [0.055] |
| fates_fire_nignitions |  | [15.0] |
| fates_fire_part_dens |  | [513.0] |
| fates_fire_threshold |  | [50.0] |
| fates_frag_cwd_fcel |  | [0.76] |
| fates_frag_cwd_flig |  | [0.24] |
| fates_frag_cwd_frac |  | [0.045, 0.075, 0.21, 0.67] |
| fates_frag_fnrt_fcel |  | [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0... |
| fates_frag_fnrt_flab |  | [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.... |
| fates_frag_fnrt_flig |  | [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.... |
| fates_frag_leaf_fcel |  | [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0... |
| fates_frag_leaf_flab |  | [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.... |
| fates_frag_leaf_flig |  | [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.... |
| fates_frag_maxdecomp |  | [0.52, 0.383, 0.383, 0.19, 1.0, 999.0] |
| fates_frag_seed_decay_rate |  | [0.51, 0.51, 0.51, 0.51, 0.51, 0.51, 0.51, 0.51, 0.51, 0.... |
| fates_grperc |  | [0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.11, 0.... |
| fates_history_ageclass_bin_edges |  | [0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0] |
| fates_history_coageclass_bin_edges |  | [0.0, 5.0] |
| fates_history_damage_bin_edges |  | [0.0, 80.0] |
| fates_history_height_bin_edges |  | [0.0, 0.1, 0.3, 1.0, 3.0, 10.0] |
| fates_history_sizeclass_bin_edges |  | [0.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0... |
| fates_hlm_pft_map |  | [[0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ... |
| fates_hydro_avuln_gs |  | [2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2... |
| fates_hydro_avuln_node |  | [[2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, ... |
| fates_hydro_epsil_node |  | [[12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 12.0, 1... |
| fates_hydro_fcap_node |  | [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ... |
| fates_hydro_htftype_node |  | [1, 1, 1, 1] |
| fates_hydro_k_lwp |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_hydro_kmax_node |  | [[-999.0, -999.0, -999.0, -999.0, -999.0, -999.0, -999.0,... |
| fates_hydro_kmax_rsurf1 |  | [20.0] |
| fates_hydro_kmax_rsurf2 |  | [0.0001] |
| fates_hydro_organ_name |  | ['leaf', 'stem', 'transporting root', 'absorbing root'] |
| fates_hydro_p50_gs |  | [-1.5, -1.5, -1.5, -1.5, -1.5, -1.5, -1.5, -1.5, -1.5, -1... |
| fates_hydro_p50_node |  | [[-2.25, -2.25, -2.25, -2.25, -2.25, -2.25, -2.25, -2.25,... |
| fates_hydro_p_taper |  | [0.333, 0.333, 0.333, 0.333, 0.333, 0.333, 0.333, 0.333, ... |
| fates_hydro_pinot_node |  | [[-1.465984, -1.465984, -1.465984, -1.465984, -1.465984, ... |
| fates_hydro_pitlp_node |  | [[-1.67, -1.67, -1.67, -1.67, -1.67, -1.67, -1.67, -1.67,... |
| fates_hydro_psi0 |  | [0.0] |
| fates_hydro_psicap |  | [-0.6] |
| fates_hydro_resid_node |  | [[0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0.16, 0... |
| fates_hydro_rfrac_stem |  | [0.625, 0.625, 0.625, 0.625, 0.625, 0.625, 0.625, 0.625, ... |
| fates_hydro_rs2 |  | [0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, 0.0001, ... |
| fates_hydro_srl |  | [25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25.0, 25... |
| fates_hydro_thetas_node |  | [[0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0... |
| fates_hydro_vg_alpha_node |  | [[0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0.12, 0... |
| fates_hydro_vg_m_node |  | [[0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, ... |
| fates_hydro_vg_n_node |  | [[2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0, ... |
| fates_landuse_logging_coll_under_frac |  | [0.0] |
| fates_landuse_logging_collateral_frac |  | [0.0] |
| fates_landuse_logging_dbhmax |  | [None] |
| fates_landuse_logging_dbhmax_infra |  | [0.0] |
| fates_landuse_logging_dbhmin |  | [0.0] |
| fates_landuse_logging_direct_frac |  | [1.0] |
| fates_landuse_logging_event_code |  | [-30] |
| fates_landuse_logging_export_frac |  | [0.8] |
| fates_landuse_logging_mechanical_frac |  | [0.0] |
| fates_leaf_c3psn |  | [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0] |
| fates_leaf_jmaxha |  | [43540.0, 43540.0, 43540.0, 43540.0, 43540.0, 43540.0, 43... |
| fates_leaf_jmaxhd |  | [152040.0, 152040.0, 152040.0, 152040.0, 152040.0, 152040... |
| fates_leaf_jmaxse |  | [495.0, 495.0, 495.0, 495.0, 495.0, 495.0, 495.0, 495.0, ... |
| fates_leaf_photo_temp_acclim_thome_time |  | [30.0] |
| fates_leaf_photo_temp_acclim_timescale |  | [30.0] |
| fates_leaf_slamax |  | [0.0954, 0.0954, 0.0954, 0.0954, 0.0954, 0.0954, 0.012, 0... |
| fates_leaf_slatop |  | [0.012, 0.005, 0.024, 0.009, 0.03, 0.03, 0.012, 0.03, 0.0... |
| fates_leaf_stomatal_intercept |  | [10000.0, 10000.0, 10000.0, 10000.0, 10000.0, 10000.0, 10... |
| fates_leaf_stomatal_slope_ballberry |  | [8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8... |
| fates_leaf_stomatal_slope_medlyn |  | [4.1, 2.3, 2.3, 4.1, 4.4, 4.4, 4.7, 4.7, 4.7, 4.7, 4.7, 2... |
| fates_leaf_vcmax25top |  | [[50.0, 62.0, 39.0, 61.0, 58.0, 58.0, 62.0, 54.0, 54.0, 3... |
| fates_leaf_vcmaxha |  | [65330.0, 65330.0, 65330.0, 65330.0, 65330.0, 65330.0, 65... |
| fates_leaf_vcmaxhd |  | [149250.0, 149250.0, 149250.0, 149250.0, 149250.0, 149250... |
| fates_leaf_vcmaxse |  | [485.0, 485.0, 485.0, 485.0, 485.0, 485.0, 485.0, 485.0, ... |
| fates_litterclass_name |  | ['twig', 'small branch', 'large branch', 'trunk', 'dead l... |
| fates_maintresp_leaf_atkin2017_baserate |  | [1.756, 1.4995, 1.4995, 1.756, 1.756, 1.756, 2.0749, 2.07... |
| fates_maintresp_leaf_ryan1991_baserate |  | [2.525e-06, 2.525e-06, 2.525e-06, 2.525e-06, 2.525e-06, 2... |
| fates_maintresp_nonleaf_baserate |  | [2.525e-06] |
| fates_maintresp_reduction_curvature |  | [0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.... |
| fates_maintresp_reduction_intercept |  | [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1... |
| fates_maintresp_reduction_upthresh |  | [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1... |
| fates_maxcohort |  | [100] |
| fates_mort_bmort |  | [0.014, 0.014, 0.014, 0.014, 0.014, 0.014, 0.014, 0.014, ... |
| fates_mort_disturb_frac |  | [1.0] |
| fates_mort_freezetol |  | [2.5, -55.0, -80.0, -30.0, 2.5, -80.0, -60.0, -10.0, -80.... |
| fates_mort_hf_flc_threshold |  | [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0... |
| fates_mort_hf_sm_threshold |  | [1e-06, 1e-06, 1e-06, 1e-06, 1e-06, 1e-06, 1e-06, 1e-06, ... |
| fates_mort_ip_age_senescence |  | [None, None, None, None, None, None, None, None, None, No... |
| fates_mort_ip_size_senescence |  | [None, None, None, None, None, None, None, None, None, No... |
| fates_mort_prescribed_canopy |  | [0.0194, 0.0194, 0.0194, 0.0194, 0.0194, 0.0194, 0.0194, ... |
| fates_mort_prescribed_understory |  | [0.025, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025, 0.025, ... |
| fates_mort_r_age_senescence |  | [None, None, None, None, None, None, None, None, None, No... |
| fates_mort_r_size_senescence |  | [None, None, None, None, None, None, None, None, None, No... |
| fates_mort_scalar_coldstress |  | [3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.5, 2... |
| fates_mort_scalar_cstarvation |  | [0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.57, ... |
| fates_mort_scalar_hydrfailure |  | [0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.8, 0... |
| fates_mort_understorey_death |  | [0.55983] |
| fates_mort_upthresh_cstarvation |  | [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1... |
| fates_nonhydro_smpsc |  | [-255000.0, -255000.0, -255000.0, -255000.0, -255000.0, -... |
| fates_nonhydro_smpso |  | [-66000.0, -66000.0, -66000.0, -66000.0, -66000.0, -66000... |
| fates_patch_fusion_tol |  | [0.05] |
| fates_pftname |  | ['broadleaf_evergreen_tropical_tree', 'needleleaf_evergre... |
| fates_phen_chilltemp |  | [5.0] |
| fates_phen_cold_size_threshold |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |
| fates_phen_coldtemp |  | [7.5] |
| fates_phen_drought_threshold |  | [-152957.4, -152957.4, -152957.4, -152957.4, -152957.4, -... |
| fates_phen_flush_fraction |  | [None, None, 0.5, None, 0.5, 0.5, None, 0.5, 0.5, None, 0... |
| fates_phen_fnrt_drop_fraction |  | [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0... |

_(truncated; showing first 200 of 271)_

### Parameters with changed dimensions: 0

_(none)_

---

## Interpretation

Overall verdict: **GREEN — proceed.** The diff is within the safe band (see Sanity assessment). Profile B (`api-43-1`) appears to be a clean evolution of Profile A (`api-31-0`): 34 parameters added, 18 removed, 5 renamed, with wiki content largely preserved (avg Jaccard 0.65).

**Where to look first:**

- Section 1 (parameter inventory) for additions/removals tied to the model version bump.
- Section 3 (wiki content) for the top-20 most-changed files; major rewrites may indicate restructured documentation or shifted file paths.
- Section 4 (parameter file) for default-value drifts, which directly affect calibration starting points.

**v0.1 scope note:** Retrieval semantics dimension (5) is not yet implemented — it requires running embedding queries against both ChromaDB stores and comparing top-k overlap. Add when ready to validate downstream RAG behavior.
