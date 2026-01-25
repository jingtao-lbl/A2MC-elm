# FATES Knowledge Base

This folder contains comprehensive FATES documentation from two complementary sources.

---

## Documentation Sources

| Source | Folder | Best For |
|--------|--------|----------|
| **Official Tech Docs** | `fates-official-docs/` | Scientific equations, theory, methodology |
| **Codebase Wiki** | `fates-codebase-wiki/` | Code implementation, function locations, data flow |

---

## Official FATES Technical Documentation

**Source:** [NGEET/fates-docs](https://github.com/NGEET/fates-docs) (Sphinx/RST)
**Online:** [ReadTheDocs](https://fates-users-guide.readthedocs.io/projects/tech-doc/en/latest/)

Key files:
- `docs/source/fates_tech_note.rst` - Main technical document (4,768 lines)
- `docs/source/parteh/` - PARTEH allocation hypotheses
- `docs/source/images/` - Scientific figures

**Topics covered:**
- Ecosystem heterogeneity and cohort dynamics
- PARTEH allocation and stoichiometry
- Allometry and growth equations
- Canopy structure and radiation transfer
- Photosynthesis and respiration
- Phenology (cold/drought deciduous)
- Fire (SPITFIRE) and mortality
- Plant hydraulics

---

## FATES Codebase Wiki

**Source:** Devin DeepWiki export (AI-generated from source code)
**Format:** Markdown with SVG diagrams

Key sections:
- `plant-physiology/parteh/cnp_allocation.md` - PID controller, 3-phase allocation
- `advanced/nutrient_competition.md` - ECA vs RD competition modes
- `plant-physiology/phenology.md` - GDD state machines
- `getting-started/parameter_system.md` - Parameter loading

**Unique features:**
- 348 SVG algorithm flowcharts
- Direct GitHub source code links with line numbers
- Data structure visualizations

---

## When to Use Which

| Task | Use |
|------|-----|
| Understanding model equations | Official docs |
| Finding where code is implemented | Codebase wiki |
| Calibration parameter lookup | Both |
| Debugging model behavior | Codebase wiki |
| Writing methods section | Official docs |
| Understanding data flow | Codebase wiki |

---

## Quick Links for Calibration

### CNP Allocation & PID Controller
- Official: `fates-official-docs/docs/source/parteh/h2_callom_flexstoich.rst`
- Wiki: `fates-codebase-wiki/plant-physiology/parteh/cnp_allocation.md`

### Phenology
- Official: Search "Phenology" in `fates_tech_note.rst`
- Wiki: `fates-codebase-wiki/plant-physiology/phenology.md`

### Nutrient Competition (ECA)
- Wiki: `fates-codebase-wiki/advanced/nutrient_competition.md`

### Mortality
- Official: Search "Mortality" in `fates_tech_note.rst`
- Wiki: `fates-codebase-wiki/plant-physiology/mortality.md`
