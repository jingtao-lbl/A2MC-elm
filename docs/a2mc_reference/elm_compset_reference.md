# ELM Compset Reference (A2MC-focused)

**Status:** Reference for A2MC users. Sourced from `components/elm/cime_config/config_component.xml` and `components/elm/bld/ELMBuildNamelist.pm` in the api-43-1 E3SM tree.

A2MC's mode-aware retrieval (Doc 20 / Doc 21) needs to know which CIME compset flags map to which simulation modes. The ELM codebase wiki (`docs/elm-knowledge-base/elm-codebase-wiki-d40b843/`) only covers `components/elm/src/` and excludes the `cime_config/` + `bld/` directories where the compset flag definitions live. This doc fills that gap for A2MC's purposes.

## Compset flag taxonomy

ELM compsets are colon-delimited descriptors like `CNPECACTCBC` or `BGC-CROP`. The CIME framework expands these into `ELM_BLDNML_OPTS` strings such as:

```
-bgc bgc -nutrient cnp -nutrient_comp_pathway eca -soil_decomp ctc -methane
```

That string flows into `ELMBuildNamelist.pm`, which interprets each flag and generates the runtime `lnd_in` namelist. A2MC's `ConfigMode.from_env()` parses the `A2MC_ELM_OPTIONS` env var (typically set from this string) into the 20 mode dimensions.

## Tier 1 flags (primary, paired with values)

### `-bgc <mode>`

Selects the biogeochemistry mode. Required for CN/BGC/FATES; not present for SP.

| Value | Meaning | A2MC ConfigMode |
|---|---|---|
| `sp` | Satellite Phenology (no plant biogeochemistry; LAI prescribed from data) | `bgc_mode='sp'`, `use_fates=False` |
| `cn` | CN cycling (carbon + nitrogen, no phosphorus, no methane) | `bgc_mode='cn'`, `use_fates=False` |
| `bgc` | Full BGC cycling (CN + methane + vertical soil C) | `bgc_mode='bgc'`, `use_fates=False` |
| `fates` | FATES dynamic vegetation (replaces ELM's CN/BGC plant compartments) | `bgc_mode='fates'`, `use_fates=True` |

ELM default (`namelist_defaults.xml:32`): `<bgc_mode>sp</bgc_mode>`.

### `-nutrient <mode>`

Required when `-bgc bgc` or `-bgc fates`. Specifies which nutrient pools are tracked.

| Value | Meaning | A2MC ConfigMode |
|---|---|---|
| `c` | Carbon-only (no nutrient cycling) | `nutrient='c'` |
| `cn` | Carbon + Nitrogen | `nutrient='cn'` |
| `cnp` | Carbon + Nitrogen + Phosphorus | `nutrient='cnp'` |

No global default; `-nutrient` is required for non-SP runs and the absence raises `fatal_error("-nutrient nutrient_option can ONLY be used with elm with -bgc cn|bgc|fates")` when used inappropriately.

### `-nutrient_comp_pathway <pathway>`

Selects the plant-microbe nutrient competition algorithm.

| Value | Meaning | A2MC ConfigMode |
|---|---|---|
| `rd` | Relative Demand (legacy; sums per-PFT demands) | `nutrient_comp_pathway='rd'` |
| `eca` | Equilibrium Chemistry Approximation (per-PFT capacitance × vmax) | `nutrient_comp_pathway='eca'` |

ELM default (`namelist_defaults.xml:67`): `<nu_com>RD</nu_com>`. **NOTE:** Many users assume ECA is default; ELM ships with RD. Set explicitly when ECA is desired.

### `-soil_decomp <cascade>`

Selects the soil organic-matter decomposition cascade.

| Value | Meaning | A2MC ConfigMode | Source |
|---|---|---|---|
| `ctc` | Converging Trophic Cascade (4-pool, historical CLMCN model) | `soil_decomp='ctc'` | `ELMBuildNamelist.pm:1388-1430` (`use_century_decomp=.false.`) |
| `century` | CENTURY/BGC (3-pool) | `soil_decomp='century'` | `ELMBuildNamelist.pm:1388-1430` (`use_century_decomp=.true.`) |

No global default; activated only when the flag is passed. For `bgc_mode='fates'`, ELM auto-sets `use_century_decomp=.true.` via `namelist_defaults.xml:2285`.

## Tier 2 flags (FATES feature flags, namelist-only)

These are not CIME compset modifiers but rather FATES-side namelist options that toggle on/off independent of the compset string. Set via `user_nl_elm` or `xmlchange ELM_BLDNML_OPTS+="..."`.

| Flag | Default | A2MC env var | Wiki content gated |
|---|---|---|---|
| `fates_spitfire_mode` | 0 | `A2MC_FATES_SPITFIRE_MODE` | `fire/` (5 docs) |
| `use_fates_planthydro` | .false. | `A2MC_USE_FATES_PLANTHYDRO` | `biophysics/hydraulics/` |
| `use_fates_logging` | .false. | `A2MC_USE_FATES_LOGGING` | `logging/` |
| `use_fates_sp` | .false. | `A2MC_USE_FATES_SP` | All FATES dynamics |
| `use_fates_ed_prescribed_phys` | .false. | `A2MC_USE_FATES_ED_PRESCRIBED_PHYS` | `biophysics/photosynthesis.md` |
| `use_fates_fixed_biogeog` | .false. | `A2MC_USE_FATES_FIXED_BIOGEOG` | Competition + dyn biogeography |

All defaults from `namelist_defaults.xml:2246-2283`.

## Tier 3 flags (secondary compset modifiers)

These are bare boolean flags or paired flags that set additional simulation features. Some appear as compset suffixes (e.g., `CROP`, `PHS`).

| Flag | Compset suffix | Default | A2MC ConfigMode | Source |
|---|---|---|---|---|
| `-crop` (bare) | `CROP` | .false. | `crop=True/False` | `config_component.xml:143-144,157-158` |
| `-dynamic_vegetation` (bare) | `CNDV`, `BGCDV` | .false. | `dynamic_vegetation=True/False` | `config_component.xml:145-148`. Mutually exclusive with `bgc_mode='fates'`. |
| `-methane` (bare) | (auto-pair with BGC) | .false. (true iff `-bgc bgc`) | `methane=True/False` | Auto-set by ELM compset definitions when `-bgc bgc` |
| `-hydrstress` (bare) | `PHS` | .false. | `hydrstress=True/False` | `config_component.xml:153,156` |
| `-topounit` (bare) | `TGU` | .false. | `topounit=True/False` | `config_component.xml:154,156` |
| `-irrig .true. -tw_irr_on` (paired + bare) | `WFM` | .false. | `irrig=True/False` | `config_component.xml:155,156,158` |
| `-solar_rad_scheme top` (paired) | `TOP` | `''` | `solar_rad_scheme='top'` or `''` | `config_component.xml:161` |

## Compset-string compaction patterns

Common compset-suffix patterns A2MC users might see:

| Suffix | Expansion |
|---|---|
| `CRDCTCBC` | `-bgc bgc -nutrient c -nutrient_comp_pathway rd -soil_decomp ctc -methane` |
| `CNRDCTCBC` | `-bgc bgc -nutrient cn -nutrient_comp_pathway rd -soil_decomp ctc -methane` |
| `CNPRDCTCBC` | `-bgc bgc -nutrient cnp -nutrient_comp_pathway rd -soil_decomp ctc -methane` |
| `CNECACTCBC` | `-bgc bgc -nutrient cn -nutrient_comp_pathway eca -soil_decomp ctc -methane` |
| `CNPECACTCBC` | `-bgc bgc -nutrient cnp -nutrient_comp_pathway eca -soil_decomp ctc -methane` |
| `CNPECACNTBC` | `-bgc bgc -nutrient cnp -nutrient_comp_pathway eca -soil_decomp century -methane` |
| `CNPRDCTCBCPHS` | + `-hydrstress` |
| `CNPRDCTCBCTGU` | + `-topounit` |
| `CNPRDCTCBCWFM` | + `-irrig .true. -tw_irr_on` |
| `CNPRDCTCBCTOP` | + `-solar_rad_scheme top` |

Source: `config_component.xml:130-167`.

## Validation in ELMBuildNamelist.pm

The Perl namelist builder enforces the rules:

| Rule | Source line | Error |
|---|---|---|
| `-nutrient` requires non-SP bgc | `setup_cmdl_nutrient` | "-nutrient nutrient_option can ONLY be used with elm with -bgc cn\|bgc\|fates" |
| `-nutrient_comp_pathway` requires non-SP bgc | `setup_cmdl_nutrient_comp` | "-nutrient_comp_pathway option can ONLY be used with elm with -bgc cn\|bgc\|fates" |
| Pathway value must be in {rd, eca} | `setup_cmdl_nutrient_comp:1320` | "$var has a value ($val) that is not valid. Valid values are: [rd, eca]" |

A2MC's `ConfigMode.from_env()` mirrors these constraints (see `tools/config.py:from_env`).

## A2MC site config example (Kougarok)

`use_cases/Kougarok/config/kougarok_config.sh`:

```bash
# Compset string passed to E3SM as ELM_BLDNML_OPTS
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca"

# FATES-side namelist flags (Tier 2)
export A2MC_FATES_PARTEH_MODE=2
# All other Tier 2 flags default off (no fire, no hydraulics, no logging, etc.)
```

`ConfigMode.from_env()` parses this into:
- `bgc_mode='fates'` (from `-bgc fates`)
- `use_fates=True` (derived)
- `parteh_mode=2`
- `nutrient='cnp'`
- `nutrient_comp_pathway='eca'`
- All Tier 2/3 flags at default (off)

## Related references

- `docs/a2mc_reference/mode_aware_workflow.md` — full mode-aware retrieval guide
- `docs/a2mc_reference/mode_aware_howto.md` — quick how-to
- `docs/a2mc_reference/version_association_howto.md` — milestone selection (orthogonal)
- `components/elm/cime_config/config_component.xml` (in user's E3SM checkout) — source of truth for compset modifiers
- `components/elm/bld/ELMBuildNamelist.pm` — flag-to-namelist translation
