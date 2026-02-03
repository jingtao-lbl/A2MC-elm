# BeTR-ReSOM Knowledge Base

**Biogeochemical Transport and Reaction Framework with ReSOM Soil BGC Model**

A comprehensive technical documentation for BeTR and the ReSOM (Reactive Soil Organic Matter) model, covering architecture, transport, BGC models, and land model coupling.

---

## Quick Navigation

### Core Documentation

| Section | Description |
|---------|-------------|
| [BeTR Overview](1__BeTR_Overview.md) | Introduction, architecture, execution modes |
| [System Architecture](1.1__System_Architecture.md) | Design patterns, module organization |
| [Directory Structure](1.2__Directory_Structure.md) | Source code organization |

### Getting Started

| Section | Description |
|---------|-------------|
| [Getting Started](2__Getting_Started.md) | Build, run, configure overview |
| [Building BeTR](2.1__Building_BeTR.md) | Compilation and dependencies |
| [Running Simulations](2.2__Running_Simulations.md) | Execution modes and commands |
| [Configuration Files](2.3__Configuration_Files.md) | Namelist and input configuration |

### Simulation Execution

| Section | Description |
|---------|-------------|
| [Simulation Execution](3__Simulation_Execution.md) | Main execution flow |
| [Simulation Modes](3.1__Simulation_Modes.md) | Standalone, CLM-coupled, jarmodel |
| [Initialization Process](3.2__Initialization_Process.md) | Startup sequence |
| [Time-Stepping Loop](3.3__Time-Stepping_Loop.md) | Main integration loop |
| [Data Flow and Coupling](3.4__Data_Flow_and_Coupling.md) | Data exchange patterns |

---

## Core Systems

### BeTR Engine

| Section | Description |
|---------|-------------|
| [Core BeTR Engine](4__Core_BeTR_Engine.md) | Central engine overview |
| [betr_type Architecture](4.1__betr_type_Architecture.md) | Main data structure |
| [BGC Reaction Interface](4.2__BGC_Reaction_Interface.md) | Reaction abstraction layer |

### Tracer Transport

| Section | Description |
|---------|-------------|
| [Tracer Transport System](5__Tracer_Transport_System.md) | Multi-phase transport overview |
| [Tracer Configuration](5.1__Tracer_Configuration.md) | Tracer definitions and setup |
| [Tracer State Management](5.2__Tracer_State_Management.md) | State variables and updates |
| [Phase Equilibration](5.3__Phase_Equilibration.md) | Gas-aqueous-solid equilibrium |
| [Transport Mechanisms](5.4__Transport_Mechanisms.md) | Advection, diffusion, dispersion |
| [Adaptive Time-Stepping](5.5__Adaptive_Time-Stepping.md) | Numerical stability |
| [Boundary Conditions](5.6__Boundary_Conditions.md) | Surface and bottom boundaries |
| [Mass Balance and Diagnostics](5.7__Mass_Balance_and_Diagnostics.md) | Conservation checks |

### Numerical Methods

| Section | Description |
|---------|-------------|
| [Numerical Methods](6__Numerical_Methods.md) | Numerical algorithms overview |
| [ODE Integrators](6.1__ODE_Integrators.md) | Time integration schemes |
| [Interpolation Methods](6.2__Interpolation_Methods.md) | Spatial interpolation |
| [Root Finding and Linear Algebra](6.3__Root_Finding_and_Linear_Algebra.md) | Solvers |

---

## BGC Models

### Model Framework

| Section | Description |
|---------|-------------|
| [BGC Models](7__BGC_Models.md) | Plugin architecture overview |
| [BGC Model Plugin System](7.1__BGC_Model_Plugin_System.md) | Factory pattern, extensibility |
| [Parameter Management](7.2__Parameter_Management.md) | Parameter loading and access |

### Available Models

| Section | Description |
|---------|-------------|
| [ECACNP Model](7.3__ECACNP_Model.md) | ECA-based C-N-P model |
| [SIMIC Model](7.4__SIMIC_Model.md) | Microbial implicit model |
| [V1ECA Model](7.5__V1ECA_Model.md) | V1 ECA implementation |
| [Other BGC Models](7.6__Other_BGC_Models.md) | DIOC, H2O isotope, Mock |
| [Creating Custom BGC Models](7.7__Creating_Custom_BGC_Models.md) | Extension tutorial |
| [ReSOM Model](7.8__ReSOM_Model.md) | Reactive SOM model |

---

## Specialized Modes

### Jarmodel (Single-Layer)

| Section | Description |
|---------|-------------|
| [Jarmodel Single-Layer Mode](8__Jarmodel_Single-Layer_Mode.md) | Incubation simulation mode |
| [Jarmodel Architecture](8.1__Jarmodel_Architecture.md) | Single-layer design |
| [Forcing Data for Jarmodel](8.2__Forcing_Data_for_Jarmodel.md) | Input data requirements |
| [Jarmodel Configuration and Output](8.3__Jarmodel_Configuration_and_Output.md) | Setup and results |

### Land Model Coupling

| Section | Description |
|---------|-------------|
| [Land Model Coupling](9__Land_Model_Coupling.md) | CLM/ELM integration overview |
| [CLM/ELM Integration](9.1__CLM/ELM_Integration.md) | Coupling implementation |
| [Data Exchange Protocol](9.2__Data_Exchange_Protocol.md) | Interface variables |
| [Stub CLM Types](9.3__Stub_CLM_Types.md) | Standalone type definitions |

---

## Development & Testing

### Testing

| Section | Description |
|---------|-------------|
| [Testing and Validation](10__Testing_and_Validation.md) | Testing overview |
| [Unit Testing](10.1__Unit_Testing.md) | pFUnit-based tests |
| [Regression Testing Framework](10.2__Regression_Testing_Framework.md) | Automated regression |
| [Test Suite Organization](10.3__Test_Suite_Organization.md) | Test structure |
| [Creating New Tests](10.4__Creating_New_Tests.md) | Adding tests |

### Advanced Topics

| Section | Description |
|---------|-------------|
| [Advanced Topics](11__Advanced_Topics.md) | Advanced usage overview |
| [Spinup Strategies](11.1__Spinup_Strategies.md) | Equilibration approaches |
| [Performance Optimization](11.2__Performance_Optimization.md) | Optimization techniques |
| [Debugging Simulations](11.3__Debugging_Simulations.md) | Troubleshooting |
| [Input/Output System](11.4__Input/Output_System.md) | I/O implementation |

### Developer Guide

| Section | Description |
|---------|-------------|
| [Developer Guide](12__Developer_Guide.md) | Contributing overview |
| [Code Organization Principles](12.1__Code_Organization_Principles.md) | Design guidelines |
| [Contributing Code](12.2__Contributing_Code.md) | Contribution workflow |

---

## Key Topics for Calibration

### BGC Model Selection
- [BGC Models](7__BGC_Models.md) - Available models and their characteristics
- [ReSOM Model](7.8__ReSOM_Model.md) - Reactive SOM with explicit microbial dynamics
- [ECACNP Model](7.3__ECACNP_Model.md) - ECA-based nutrient competition

### Parameter System
- [Parameter Management](7.2__Parameter_Management.md) - How parameters are loaded and organized
- [Configuration Files](2.3__Configuration_Files.md) - Namelist configuration

### Transport and Reactions
- [Tracer Transport System](5__Tracer_Transport_System.md) - Multi-phase transport
- [Phase Equilibration](5.3__Phase_Equilibration.md) - Gas-aqueous-solid partitioning
- [BGC Reaction Interface](4.2__BGC_Reaction_Interface.md) - Reaction calculations

### Land Model Integration
- [CLM/ELM Integration](9.1__CLM/ELM_Integration.md) - Coupling with ELM
- [Data Exchange Protocol](9.2__Data_Exchange_Protocol.md) - Interface variables

---

## Source Code References

All documentation includes links to the BeTR-ReSOM source code on GitHub:
- Repository: [sbetr-resomv1 on GitHub](https://github.com/jingtao-lbl/sbetr-resomv1)
- Source files are referenced with specific line numbers

---

## About This Knowledge Base

This knowledge base was generated from the BeTR-ReSOM DeepWiki documentation and organized for:
- **A2MC Integration**: Supports AI-assisted calibration of soil BGC
- **RAG/GraphRAG**: Structured for semantic search and retrieval
- **Community Use**: Generic documentation for BeTR applications

**Last Updated:** January 2026
