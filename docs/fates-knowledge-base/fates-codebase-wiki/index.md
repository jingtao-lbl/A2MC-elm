---
**Source pin:** FATES commit `e85d997` (2026-01-01)
**Last verified:** 2026-04-10
---

# FATES Knowledge Base

**Functionally Assembled Terrestrial Ecosystem Simulator**

Technical documentation for FATES, pinned to a specific source commit so every line reference resolves to real code.

---

## Quick Navigation

### Core Documentation

| Section | Description |
|---------|-------------|
| [Model Overview](overview/model_overview.md) | Architecture, data structures, daily execution flow |
| [Getting Started](getting-started/index.md) | Host interface, initialization, parameters |
| [Core Dynamics](core-dynamics/index.md) | Daily loop, patch/cohort dynamics |

### Plant Processes

| Section | Description |
|---------|-------------|
| [Plant Physiology](plant-physiology/index.md) | Growth, phenology, allocation, mortality |
| [PARTEH Allocation](plant-physiology/parteh/index.md) | Carbon and CNP allocation systems |
| [Canopy Structure](canopy-structure/index.md) | Perfect Plasticity Approximation, LAI/SAI profiles |

### Biophysical Processes

| Section | Description |
|---------|-------------|
| [Biophysics](biophysics/index.md) | Radiation, photosynthesis, hydraulics |
| [Fire Dynamics](fire/index.md) | SPITFIRE fire model |
| [Logging](logging/index.md) | Harvest and land use |

### Technical Reference

| Section | Description |
|---------|-------------|
| [Output & Diagnostics](output/index.md) | History, restart, mass balance |
| [Advanced Topics](advanced/index.md) | Simulation modes, nutrient competition |
| [Code Architecture](architecture/index.md) | Module organization, design patterns |

---

## Key Topics for Calibration

### CNP Calibration
- [CNP Calibration Guide](advanced/cnp_calibration_guide.md) — spin-up phases, vmax tuning, diagnostics, troubleshooting

### Parameter System
- [Parameter System](getting-started/parameter_system.md) — how parameters are loaded and organized
- [Parameter Management Tools](getting-started/parameter_tools.md) — Python tools for parameter modification

### Nutrient Dynamics (CNP)
- [CNP Allocation](plant-physiology/parteh/cnp_allocation.md) — PID controller, stoichiometry, three-phase allocation
- [Nutrient Competition](advanced/nutrient_competition.md) — ECA vs RD competition modes
- [Soil-Plant Interface](plant-physiology/parteh/soil_plant_interface.md) — nutrient uptake mechanics

### Plant Growth
- [Phenology](plant-physiology/phenology.md) — GDD-based leaf dynamics, state machines
- [Allometry](plant-physiology/allometry.md) — DBH-biomass relationships
- [Mortality](plant-physiology/mortality.md) — stress-induced mortality mechanisms

---

## Source Code References

All documentation in this knowledge base cites FATES source as `(path/from/fates/root.F90:NNN)` at commit `e85d997`. Line numbers have been verified against the source tree; if the upstream code changes, regenerate this wiki rather than mutate it in place.

- FATES repository: https://github.com/NGEET/fates
- This knowledge base is pinned to commit `e85d997`

---

## About This Knowledge Base

This knowledge base was regenerated from FATES source at commit `e85d997` and organized for:

- **A2MC integration**: supports AI-assisted calibration workflows
- **RAG/GraphRAG**: structured for semantic search and retrieval
- **Community use**: generic documentation for any FATES application

**Last verified:** 2026-04-10
