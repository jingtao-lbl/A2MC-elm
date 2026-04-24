# E3SM/ELM Knowledge Base

**Energy Exascale Earth System Model - Land Model (ELM)**

A comprehensive technical documentation for E3SM and its land component ELM, covering model architecture, configuration, components, and HPC execution.

---

## Quick Navigation

### Overview

| Section | Description |
|---------|-------------|
| [E3SM Overview](1__E3SM_Overview.md) | Introduction to E3SM |
| [Repository Structure](1.1__Repository_Structure.md) | Source code organization |
| [Key Concepts and Terminology](1.2__Key_Concepts_and_Terminology.md) | Essential definitions |

### Configuration System

| Section | Description |
|---------|-------------|
| [Configuration System](2__Configuration_System.md) | Configuration overview |
| [Machine Configuration](2.1__Machine_Configuration.md) | HPC machine setup |
| [Grid and Resolution Configuration](2.2__Grid_and_Resolution_Configuration.md) | Grid definitions |
| [Component Sets and PE Layouts](2.3__Component_Sets_and_PE_Layouts.md) | COMPSET configuration |
| [Build System](2.4__Build_System.md) | Compilation and build |
| [Namelist System](2.5__Namelist_System.md) | Runtime configuration |

---

## Model Components

### Component Overview

| Section | Description |
|---------|-------------|
| [Model Components](3__Model_Components.md) | All components overview |
| [Other Components](3.5__Other_Components.md) | River, wave, glacier |

### Atmosphere Model (EAM)

| Section | Description |
|---------|-------------|
| [Atmosphere Model (EAM)](3.1__Atmosphere_Model_(EAM).md) | EAM overview |
| [Dynamics Cores](3.1.1__Dynamics_Cores.md) | SE and HOMME dynamical cores |
| [Physics Parameterizations](3.1.2__Physics_Parameterizations.md) | Physical processes |
| [Chemistry and Aerosols](3.1.3__Chemistry_and_Aerosols.md) | MAM aerosol model |

### Ocean Model (MPAS-Ocean)

| Section | Description |
|---------|-------------|
| [Ocean Model (MPAS-Ocean)](3.2__Ocean_Model_(MPAS-Ocean).md) | MPAS-Ocean overview |
| [Time Integration Schemes](3.2.1__Time_Integration_Schemes.md) | Ocean time stepping |
| [Ocean Physics](3.2.2__Ocean_Physics.md) | Ocean physical processes |

### Sea Ice Model

| Section | Description |
|---------|-------------|
| [Sea Ice Model (MPAS-Seaice)](3.3__Sea_Ice_Model_(MPAS-Seaice).md) | Sea ice component |

### Land Model (ELM)

| Section | Description |
|---------|-------------|
| [Land Model (ELM)](3.4__Land_Model_(ELM).md) | **ELM component** - subgrid hierarchy, BGC modes, FATES coupling |

---

## Coupling Infrastructure

| Section | Description |
|---------|-------------|
| [Coupling Infrastructure](4__Coupling_Infrastructure.md) | Component coupling overview |
| [CIME Driver and MCT](4.1__CIME_Driver_and_MCT.md) | Driver and coupler |
| [MOAB Integration](4.2__MOAB_Integration.md) | MOAB mesh framework |
| [Mapping and Regridding](4.3__Mapping_and_Regridding.md) | Grid interpolation |
| [Flux Calculations and Fractional Coverage](4.4__Flux_Calculations_and_Fractional_Coverage.md) | Surface fluxes |

---

## Testing and Validation

| Section | Description |
|---------|-------------|
| [Testing and Validation](5__Testing_and_Validation.md) | Testing overview |
| [Test Infrastructure](5.1__Test_Infrastructure.md) | CIME test system |
| [Test Types and Use Cases](5.2__Test_Types_and_Use_Cases.md) | Test categories |

---

## HPC Execution and Performance

| Section | Description |
|---------|-------------|
| [HPC Execution and Performance](6__HPC_Execution_and_Performance.md) | HPC overview |
| [Supported Machines](6.1__Supported_Machines.md) | NERSC, OLCF, ALCF, etc. |
| [Parallel Execution Model](6.2__Parallel_Execution_Model.md) | MPI, OpenMP parallelism |
| [I/O System and PIO](6.3__I/O_System_and_PIO.md) | Parallel I/O |

---

## MPAS Framework Deep Dive

| Section | Description |
|---------|-------------|
| [MPAS Framework Deep Dive](7__MPAS_Framework_Deep_Dive.md) | MPAS overview |
| [Unstructured Meshes](7.1__Unstructured_Meshes.md) | Voronoi mesh structure |
| [Registry and Streams](7.2__Registry_and_Streams.md) | Variable management |
| [Domain Decomposition](7.3__Domain_Decomposition.md) | Parallel partitioning |

---

## Advanced Topics

| Section | Description |
|---------|-------------|
| [Advanced Topics](8__Advanced_Topics.md) | Advanced usage overview |
| [GPU Support and Performance Portability](8.1__GPU_Support_and_Performance_Portability.md) | GPU acceleration |
| [Energy and Water Conservation](8.2__Energy_and_Water_Conservation.md) | Conservation properties |
| [Provenance and Reproducibility](8.3__Provenance_and_Reproducibility.md) | Reproducible simulations |

---

## Key Topics for ELM-FATES Calibration

### Land Model Configuration
- [Land Model (ELM)](3.4__Land_Model_(ELM).md) - ELM architecture, BGC modes, FATES interface

### Configuration
- [Namelist System](2.5__Namelist_System.md) - Runtime parameter configuration
- [Component Sets and PE Layouts](2.3__Component_Sets_and_PE_Layouts.md) - COMPSET definitions

### HPC Execution
- [Supported Machines](6.1__Supported_Machines.md) - NERSC Perlmutter, etc.
- [Parallel Execution Model](6.2__Parallel_Execution_Model.md) - MPI/OpenMP configuration

### Testing
- [Test Infrastructure](5.1__Test_Infrastructure.md) - Running validation tests

---

## Source Code References

All documentation includes links to the E3SM source code on GitHub:
- Repository: [E3SM on GitHub](https://github.com/E3SM-Project/E3SM)
- Source files are referenced with specific line numbers

---

## About This Knowledge Base

This knowledge base was generated from the E3SM DeepWiki documentation and organized for:
- **A2MC Integration**: Supports AI-assisted calibration of ELM-FATES
- **RAG/GraphRAG**: Structured for semantic search and retrieval
- **Community Use**: Generic documentation for E3SM applications

**Note:** For detailed FATES documentation, see the [FATES Knowledge Base](../../fates-knowledge-base/fates-codebase-wiki/index.md).

**Last Updated:** January 2026
