# FATES Knowledge Base

**Functionally Assembled Terrestrial Ecosystem Simulator**

A comprehensive technical documentation for FATES, covering model architecture, processes, and parameters.

---

## Quick Navigation

### Core Documentation

| Section | Description |
|---------|-------------|
| [Model Overview](overview/model_overview.md) | Architecture, design principles, execution flow |
| [Getting Started](getting-started/index.md) | Host interface, initialization, parameters |
| [Core Dynamics](core-dynamics/index.md) | Daily loop, patch/cohort dynamics |

### Plant Processes

| Section | Description |
|---------|-------------|
| [Plant Physiology](plant-physiology/index.md) | Growth, phenology, allocation, mortality |
| [PARTEH Allocation](plant-physiology/parteh/index.md) | Carbon and CNP allocation systems |
| [Canopy Structure](canopy-structure/index.md) | PPA, LAI/SAI profiles |

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

### Parameter System
- [Parameter System Overview](getting-started/parameter_system.md) - How parameters are loaded and organized
- [Parameter Management Tools](getting-started/parameter_tools.md) - Python tools for parameter modification

### Nutrient Dynamics (CNP)
- [CNP Allocation](plant-physiology/parteh/cnp_allocation.md) - PID controller, stoichiometry, three-phase allocation
- [Nutrient Competition](advanced/nutrient_competition.md) - ECA vs RD competition modes
- [Soil-Plant Interface](plant-physiology/parteh/soil_plant_interface.md) - Nutrient uptake mechanics

### Plant Growth
- [Phenology](plant-physiology/phenology.md) - GDD-based leaf dynamics, state machines
- [Allometry](plant-physiology/allometry.md) - DBH-biomass relationships
- [Mortality](plant-physiology/mortality.md) - Stress-induced mortality mechanisms

---

## Source Code References

All documentation includes links to the FATES source code on GitHub:
- Repository: [FATES on GitHub](https://github.com/NGEET/fates)
- Source files are referenced with specific line numbers

---

## About This Knowledge Base

This knowledge base was generated from the FATES DeepWiki documentation and organized for:
- **A2MC Integration**: Supports AI-assisted calibration workflows
- **RAG/GraphRAG**: Structured for semantic search and retrieval
- **Community Use**: Generic documentation for any FATES application

**Last Updated:** January 2026
