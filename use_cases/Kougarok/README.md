# Kougarok, Alaska - A2MC Use Case

**Location:** Kougarok, Seward Peninsula, Alaska, USA
**Coordinates:** 65.35°N, 164.75°W
**Ecosystem:** Arctic tundra (shrub-graminoid mosaic)
**Project:** NGEE-Arctic
**Status:** Active Development

---

## Overview

Kougarok is a representative Arctic tundra site with three dominant plant functional types competing for limited nutrients (especially phosphorus) in permafrost-affected soils. The calibration challenge involves simultaneously optimizing leaf and fine root biomass across all three PFTs while accounting for nutrient competition dynamics.

---

## Target PFTs

| PFT Index | Name | Description |
|-----------|------|-------------|
| PFT#7 | Evergreen shrub | Low-growing evergreen shrubs|
| PFT#9 | Deciduous shrub | Deciduous shrubs|
| PFT#10 | Arctic graminoid | Sedges and grasses |

---

## Validation Targets

### Biomass Targets

| Variable | PFT | Observed (g C/m²) | Uncertainty | Source |
|----------|-----|-------------------|-------------|--------|
| Leaf | PFT#7 | 24.6 | ±20% | NGEE-Arctic field measurements |
| Leaf | PFT#9 | 124.7 | ±20% | NGEE-Arctic field measurements |
| Leaf | PFT#10 | 82.7 | ±20% | NGEE-Arctic field measurements |
| Fine Root | PFT#7 | 174.2 | ±20% | NGEE-Arctic field measurements |
| Fine Root | PFT#9 | 187.3 | ±20% | NGEE-Arctic field measurements |
| Fine Root | PFT#10 | 382.1 | ±20% | NGEE-Arctic field measurements |

### Notes
- AGB data excluded due to inconsistency (PFT#10 AGB < Leaf biomass, physically impossible)
- ±20% uncertainty is more restrictive than observed standard deviation

---

## Key Discoveries

### 1. Allocation Paradox

**Description:** Increasing P uptake rate (vmax_p) causes biomass COLLAPSE instead of increase.

**Mechanism:**
- Higher vmax_p → More P uptake per root → Higher storage P concentration
- → Lower C:P storage ratio → PID controller detects "excess nutrients"
- → PID DECREASES leaf-to-fineroot ratio → Less root allocation
- → Lower total uptake capacity → Biomass collapse

**Affected parameters:** `fates_cnp_vmax_p`, `fates_cnp_pid_kp`

### 2. Triple Bottleneck (PFT#10)

**Description:** Arctic graminoids face three simultaneous limitations.

**Components:**
1. **P starvation** - P uptake/demand ≈ 0.000005 (essentially zero)
2. **Light competition** - PFT#9 is 5-10× more productive (GPP ratio)
3. **Excessive turnover** - Default 1.0 yr vs realistic 5.0 yr

### 3. ECA Competition

**Description:** PFT#9 outcompetes PFT#10 for soil P under Equilibrium Chemistry Approximation.

**Mechanism:** Competition is simultaneous based on capacitance (fine-root biomass × vmax_p × root distribution). PFT#9 has higher capacitance → gets more P.

### 4. Soil P Chemistry Bottleneck

**Description:** 98.9% of soil P locked in mineral-adsorbed pool (SECONDP).

**Key insight:** P limitation is ELM soil chemistry parameters, NOT FATES plant parameters. Parameters `r_desorp`, `r_adsorp` were never varied in Morris ensemble.

### 5. Root Distribution Backwards

**Description:** Default FATES parameters make graminoids SHALLOWEST rooted, but field observations show they should be DEEPEST.

**Calibrated from:** NGA240 dataset (56 soil cores from Kougarok)

---

## Morris Ensemble

- **Iteration 1:** 138 parameters, 4170 simulations
- **Iteration 2:** 162 parameters, 4890 simulations (added turnover, root distribution, PID gains)

Key parameter expansions:
- Nutrient uptake: 10× upper bound
- Root distribution: ±50% around field-calibrated values
- Storage cushion: Upper bound → 5.0

---

## File Structure

```
use_cases/Kougarok/
├── README.md                       # This file
├── config/
│   └── kougarok_config.sh          # Site-specific configuration overrides
├── parameters/
│   ├── FATES_Parameter_List_Full_162_Finalized.txt  # 162 parameters with bounds
│   └── salib_problem_162params.txt                   # SALib problem definition
├── validation/
│   └── validation_targets_leafroot.txt              # Observed biomass targets
│
└── memory/                         # Site-specific A2MC memory (created at runtime)
    ├── workflow_log.json           # Master workflow status tracker
    │
    ├── logs/                       # Markdown documentation logs (AI reasoning)
    │   ├── phase1_exploration/     #   └── 20260123a_Iteration_2_Exploration.md
    │   ├── phase2_screening/       #   └── 20260123b_Iteration_2_Screening.md
    │   ├── phase3_diagnosis/
    │   ├── phase4_hypothesis/
    │   ├── phase5_testing/
    │   └── phase6_refinement/
    │
    ├── phase_logs/                 # Data files (Y matrices, plots, CSVs)
    │   └── phase1_exploration/     #   ├── MorrisLeafbiomass_4890cases_2010_2019.txt
    │                               #   ├── morris_leaf_biomass_sensitivity_*.png
    │                               #   └── morris_leaf_biomass_rankings_*.csv
    │
    └── gained_knowledge/           # Site-specific knowledge (JSON)
        ├── discoveries.json        # Mechanistic insights (e.g., "Allocation Paradox")
        ├── experiments.json        # Experiment records with outcomes
        └── failed_approaches.json  # Approaches to NOT repeat
```

**Memory folder distinction:**
- `logs/` = Human-readable Markdown documentation with AI reasoning
- `phase_logs/` = Data outputs (matrices, plots, CSVs) from each phase
- `gained_knowledge/` = Structured JSON knowledge for AI to reference

### Running the Workflow

Before running, modify the two configuration files for your setup:

1. **`A2MC/a2mc_config.sh`** — Machine-level settings (HPC project, E3SM path, output root, Python env)
2. **`A2MC/use_cases/Kougarok/config/kougarok_config.sh`** — Kougarok-specific settings (PFTs, parameters, validation targets, case naming)

```bash
# Source both configuration files (required before every run)
source a2mc_config.sh
source use_cases/Kougarok/config/kougarok_config.sh

# Start a new calibration run
python orchestrator.py --run

# Start from screening phase in calibration round 2 (162 params)
python orchestrator.py --run --start-phase 2 --start-iteration 2

# Resume from a saved checkpoint
python orchestrator.py --resume --state-file ./use_cases/Kougarok/memory/workflow_state.json

# Monitor progress (main log file saved to use_cases/Kougarok/)
tail -f use_cases/Kougarok/a2mc_run_*.log
```

All screen output is automatically saved to `use_cases/Kougarok/a2mc_run_{timestamp}.log`.

---

## HPC Data Locations (NERSC Perlmutter)

```
# FATES parameter files (4890 NetCDF files)
/dvs_ro/u1/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_NonPrescribed_EnPlantTraitsCNPparam162_Morris/

# Ensemble matrix (4890 x 162 parameter values)
/global/cfs/cdirs/m2467/jingtao/SALib_FATES/FATES_CNPnPlantTraits_162param_Morris_4890sets.txt

# Simulation outputs
/global/cfs/cdirs/m2467/jingtao/Kougarok_PlantTraitsCNPEnsemble162_Morris/

# Extracted monthly data
/global/cfs/cdirs/m2467/jingtao/Kougarok_PlantTraitsCNPEnsemble162_Morris/extracted_monthly_data/

# Case scripts
/pscratch/sd/j/jingtao/CaseScripts/Kougarok_FATES/ReCalibration_PtCNP162_AllPhase/
```

---

## Reference for Similar Sites

**If you are calibrating another Arctic/tundra site**, the Kougarok knowledge base may be relevant:

| Resource | Location | Contents |
|----------|----------|----------|
| **Discoveries** | `memory/gained_knowledge/discoveries.json` | Mechanistic insights (Allocation Paradox, Triple Bottleneck, etc.) |
| **Failed Approaches** | `memory/gained_knowledge/failed_approaches.json` | What NOT to try |
| **Key Findings** | This README (Key Discoveries section) | Summary of major lessons |
| **Phase Logs** | `memory/logs/` | Detailed AI reasoning from each calibration phase |

### Applicability to Other Sites

| Discovery | Likely Applicable To |
|-----------|---------------------|
| Allocation Paradox (PID feedback) | Any CNP simulation with nutrient limitation |
| ECA Competition dynamics | Multi-PFT sites with shared nutrient pools |
| Soil P Chemistry Bottleneck | P-limited systems (Arctic, tropical weathered soils) |
| Root Distribution calibration | Sites with field root distribution data |
| Triple Bottleneck (graminoids) | Arctic/alpine graminoid-shrub competition |

### How to Reference

```python
from memory import MemoryManager

# Load Kougarok knowledge for reference
kougarok_memory = MemoryManager("use_cases/Kougarok/memory/gained_knowledge")

# Check discoveries relevant to your calibration
discoveries = kougarok_memory.discoveries.get('discoveries', [])
for d in discoveries:
    print(f"- {d['name']}: {d['description'][:80]}...")
```

**Note:** Site-specific parameter VALUES (e.g., "vmax_p = 2.5e-10 worked for Kougarok") may not transfer directly. The MECHANISMS and LESSONS are more transferable than exact numbers.

---

## References

- NGEE-Arctic project data archive
- Knox et al. 2024 - ELM-FATES-CNP Technical Reference
- Blume-Werry et al. 2019 - Arctic root longevity
