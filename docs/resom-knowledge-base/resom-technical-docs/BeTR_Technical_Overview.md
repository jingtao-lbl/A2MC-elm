# BeTR (Biogeochemical Transport and Reaction) Model: Structure and Mechanisms

## 1. Introduction
The Biogeochemical Transport and Reaction (BeTR) model is a generic reactive transport module designed to simulate the vertical transport, interactions, and biotic/abiotic transformations of chemical tracers within terrestrial ecosystem models. Initially developed for the Community Land Model (CLM4) and updated to version 2 (BeTR-v2) for the Energy Exascale Earth System Model (E3SM) land model (ELM), BeTR serves as a platform to accelerate soil biogeochemical (BGC) model development and analyze structural uncertainty.

## 2. Governing Equations
BeTR solves a one-dimensional multiphase reactive-transport equation. It accounts for an arbitrary number of tracers across aqueous, gaseous, and solid phases.

The general governing equation is:

$$
\frac{\partial}{\partial t} (\theta_w C_w + \varepsilon_g C_g + (1 - \theta_w - \varepsilon_g) C_s) = 
\frac{\partial}{\partial z} \left( \theta_w \tau_w D_w \frac{\partial C_w}{\partial z} \right) + 
\frac{\partial}{\partial z} \left( \varepsilon_g \tau_g D_g \frac{\partial C_g}{\partial z} \right) + 
\frac{\partial}{\partial z} \left( (1 - \theta_w - \varepsilon_g) D_s \frac{\partial C_s}{\partial z} \right) - 
\frac{\partial}{\partial z} (q_w C_w) - E_{bub} - T_r + R_{bgc}
$$

**Where:**
*   $\theta_w$: Volumetric water content ($m^3 m^{-3}$)
*   $C_w, C_g, C_s$: Tracer concentrations in aqueous, gaseous, and adsorbed/solid phases ($mol m^{-3}$)
*   $\varepsilon_g$: Air-filled porosity ($m^3 m^{-3}$)
*   $\tau_w, \tau_g$: Tortuosity for aqueous and gaseous phases
*   $D_w, D_g, D_s$: Diffusivity for aqueous, gaseous, and solid phases ($m^2 s^{-1}$)
*   $q_w$: Aqueous advection velocity ($m s^{-1}$)
*   $E_{bub}$: Ebullition flux ($mol m^{-3} s^{-1}$)
*   $T_r$: Transpiration flux transport ($mol m^{-3} s^{-1}$)
*   $R_{bgc}$: Biogeochemical reaction rate ($mol m^{-3} s^{-1}$)

Solid-phase diffusivity ($D_s$) approximates mixing processes like bioturbation and cryoturbation.

## 3. Numerical Implementation
BeTR employs an operator splitting approach (Strang splitting) to solve the governing equation, allowing the use of specific numerical solvers for different physical processes.

### 3.1 solving Sequence (BeTR-v2)
In BeTR-v2, the sequence of operations within a time step is typically:
1.  Surface runoff (tracer loss).
2.  Biogeochemical reactions ($R_{bgc}$).
3.  Advection ($q_w$).
4.  Diffusion ($D_w, D_g, D_s$).
5.  Ebullition (using hydrostatic approximation).
6.  Subsurface drainage.

### 3.2 Transport Algorithms
*   **Advection:** BeTR-v2 utilizes a mass-conserving semi-Lagrangian approach for aqueous advection to reduce numerical dispersion, an improvement over the upstream scheme used in v1.
*   **Diffusion:** Aqueous and gaseous diffusion are solved together using a dual-phase algorithm with implicit time-stepping. This assumes equilibrium between gaseous and aqueous phases.
*   **Solid Phase:** Solid-phase diffusion is split from other processes due to its slower timescale and solved implicitly.

### 3.3 Coupling and Boundary Conditions
BeTR diagnoses tracer fluxes consistent with hydrological processes in the host land model (e.g., CLM or ELM).
*   **Top Boundary:** Determined by atmospheric precipitation, canopy dripping (dry/wet deposition), and diffusive surface fluxes.
*   **Surface Flux Calculation:** Modeled using a two-layer model (soil surface and vegetation) to diagnose tracer concentrations at the apparent sink level and compute diffusive flux to the atmosphere.
*   **Bottom Boundary:** Typically applies a radiation boundary condition (tracer advects only with water flow).

## 4. Code Structure (BeTR-v2)
BeTR-v2 is designed as a standalone capability for easier development.
*   **Core Code:** Located in `sbetr/src/betr`.
*   **Soil Farm:** Located in `sbetr/src/Applications/soil-farm/`. This directory contains customized BGC modules (e.g., `v1eca`, `ecacnp`).
*   **Drivers:** Supports both single-layer models (`sbetr/src/jarmodel/`) and 1-D vertically resolved column models (`sbetr/src/driver/`).

--------------------------------------------------------------------------------
## BeTR Soil Farm Modules
# BeTR Soil Farm: Modules and Kinetic Representations

## 1. The "Soil Farm" Concept
BeTR utilizes a "soil farm" structure (BeTR-S), which allows for the flexible integration and testing of different soil biogeochemistry (BGC) formulations within a single Earth System Model (ESM) framework. This architecture supports hierarchical modeling, enabling comparisons between simple and complex mechanistic representations.

## 2. Kinetic Formulations
A primary distinction between modules in the soil farm is the mathematical formulation of substrate uptake kinetics.

### 2.1 Equilibrium Chemistry Approximation (ECA)
The ECA kinetics treats substrate uptake in consumer-substrate networks as an equilibrium chemistry problem. It assumes that consumer-substrate complexes equilibrate much faster than other metabolic processes (Total Quasi-Steady-State Assumption or tQSSA).

**Equation:**
For a network with multiple substrates ($S$) and consumers ($E$), the ECA kinetics for the complex $C_{ij}$ is approximated as:

$$
C_{ij} = \frac{S_{i,T} E_{j,T}}{K_{S,ij}} \left( 1 + \sum_{k=1}^{I} \frac{S_{k,T}}{K_{S,kj}} + \sum_{k=1}^{J} \frac{E_{k,T}}{K_{S,ik}} \right)^{-1}
$$

*   **Advantages:** ECA explicitly accounts for competitive inhibition (multiple microbes competing for substrates) and adsorption shielding (mineral surfaces competing for substrates). It is more robust than Michaelis-Menten kinetics in complex networks involving multiple consumers and substrates.

### 2.2 Michaelis-Menten (MM)
The classical MM kinetics is valid when the substrate concentration is much higher than the enzyme concentration. BeTR studies have shown that MM kinetics fail to realistically reproduce reference solutions when multiple consumers (microbes and mineral surfaces) compete for multiple substrates.

### 2.3 Multicomponent Langmuir (ECA-ML)
A simplified version of ECA (Eq. 21 in Tang & Riley 2013) that resembles the multicomponent Langmuir isotherm. It assumes enzyme concentrations are much lower than substrate concentrations (standard QSSA).

## 3. Specific Module Implementations in BeTR-v2

### 3.1 ELMv1-ECA (Legacy Implementation)
*   **Description:** The default soil BGC from ELMv1-ECA re-implemented in BeTR.
*   **Numerical Method:** Uses an explicit Euler scheme where nutrient mineralization and uptake are solved asynchronously (newly mineralized nutrients are available only in the next time step).
*   **Characteristics:** Requires reordering of subroutines to separate vegetation and soil BGC, which can lead to sporadic negative variables.

### 3.2 ELMv1-BeTR-ECA0 (Robust Numerical Coupling)
*   **Description:** Implements the same mathematical BGC formulation as ELMv1-ECA but uses BeTR's advanced numerical solvers.
*   **Numerical Method:** Uses the **multiple-flux co-limiting solver**. This solves production and consumption fluxes concurrently within a time step.
*   **Impact:** This tighter coupling results in different model behaviors (e.g., less nitrogen limitation) compared to the default ELMv1-ECA, even with identical parameters.

### 3.3 ReSOM (ecacnp)
*   **Description:** A microbe- and mineral-surface-explicit model (See *ReSOM_Model_Details.md* for full description).
*   **Structure:** Implemented in two steps within the file structure:
    1.  Single-layer implementation (`ecacnp/ecacnp1layer/`).
    2.  Extension to 1-D soil column (`ecacnp/ecacnpNlayer/`).

## 4. Hierarchical Modeling Capabilities
BeTR-v2 supports running these modules in different modes:
*   **Single-Layer Mode:** Useful for comparing with incubation experiments. Solves a simplified equation ignoring vertical transport between layers.
*   **Vertically Resolved (1-D):** Full reactive transport with multiple layers (e.g., 10 layers), solving for advection, diffusion, and reaction across the soil profile.

--------------------------------------------------------------------------------
## ReSOM Model Details
# ReSOM: Reaction-network-based Model of Soil Organic Matter and Microbes

## 1. Overview
ReSOM is a microbe- and mineral-surface-explicit model designed to mechanistically represent soil organic matter (SOM) decomposition and stabilization. It is integrated into the E3SM Land Model (ELM) via the BeTR module.

## 2. Model Structure and Carbon Pools
ReSOM is based on **Dynamic Energy Budget (DEB)** theory, partitioning microbial biomass into reserve and structural compartments. It tracks five primary carbon pools:
1.  **Polymers ($S$):** Complex organic matter (e.g., cellulose, lignin).
2.  **Monomers ($D$):** Low molecular weight substrates (e.g., glucose).
3.  **Microbial Reserve Biomass ($X$):** Supports growth and maintenance.
4.  **Microbial Structural Biomass ($B$):** The physical microbial body.
5.  **Extracellular Enzymes ($E$):** Catalyze polymer degradation.

## 3. Key Biogeochemical Mechanisms

### 3.1 Enzymatic Depolymerization
Decomposition of polymers is driven by extracellular enzymes. ReSOM uses ECA kinetics to calculate the depolymerization flux ($F_S$), accounting for competition with mineral surface adsorption:

$$
F_S = \frac{V_{E,max} E S}{k_{ES} \left( 1 + \frac{S}{k_{ES}} + \frac{E}{k_{ES}} + \frac{M}{k_{ME}} \right)}
$$

*   $V_{E,max}$: Maximum enzymatic degradation rate.
*   $M$: Mineral surface sites (sorption capacity).
*   $k_{ME}$: Affinity parameter for mineral adsorption of enzymes.

### 3.2 Microbial Uptake and Assimilation
Monomer uptake ($F_D$) is calculated using ECA kinetics, considering transporter density ($z$) and competition with mineral adsorption ($M$):

$$
F_D = \frac{V_{B,max} z B D}{k_{BD} \left( 1 + \frac{D}{k_{BD}} + \frac{z B}{k_{BD}} + \frac{M}{k_{MD}} \right)}
$$

*   $V_{B,max}$: Maximum monomer assimilation rate.
*   $k_{MD}$: Affinity parameter for mineral adsorption of monomers.

### 3.3 Microbial Metabolism (DEB Theory)
Assimilated carbon enters the reserve pool ($X$). The net productive flux from the reserve pool $( \kappa - g )X$ supports metabolic processes in a specific priority order:
1.  **Maintenance:** Highest priority ($mB$).
2.  **Structural Growth:** ($gB$).
3.  **Enzyme Production:** ($p_E B$).

Growth ($g$) and enzyme production ($p_E$) rates are solved iteratively based on potential rates and available reserve energy.

### 3.4 Mineral Surface Interactions (Organo-Mineral)
ReSOM explicitly models the reversible adsorption and desorption of:
*   **Monomers:** Adsorption protects them from microbial uptake (forming MAOC).
*   **Enzymes:** Adsorption prevents them from catalyzing polymer degradation.
*   **Sorption Capacity ($Q_{max}$):** Estimated based on soil clay fraction and bulk density.

## 4. Environmental Sensitivities

### 4.1 Temperature Sensitivity
ReSOM distinguishes between three types of temperature-dependent processes:
1.  **Enzyme Activity:** Non-monotonic response due to reversible enzyme denaturation (folding/unfolding) based on Gibbs free energy.
2.  **Non-equilibrium Reactions:** (e.g., degradation, uptake). Follows Arrhenius kinetics modified by the active enzyme fraction.
3.  **Equilibrium Reactions:** (e.g., sorption). Governed by Gibbs free energy change ($\Delta G_{EQ}$).
    *   **Variants:** ReSOM allows testing different sorption hypotheses: Exothermic (sorption decreases with warming) vs. Endothermic (sorption increases with warming).

### 4.2 Moisture Sensitivity
ReSOM uses an **Effective Affinity Parameter** ($K_{s,w}$) to represent moisture limitations. This accounts for substrate diffusion through water films to microbial active sites. As moisture decreases, diffusion becomes less efficient, reducing the effective affinity between microbes and substrates.

## 5. Parameter Importance
Sensitivity analyses in ELM-ReSOM indicate:
*   **Microbial Traits:** Parameters like maximum mortality rate ($\gamma_{B0}$), transporter density scaling ($z$), and maximum assimilation rate ($V_{B,max}$) are the strongest controllers of heterotrophic respiration ($R_{CO2}$).
*   **Synergies:** Indirect effects of parameters (due to process interactions)

## Reference

Tang, J. Y., & Riley, W. J. (2013). A total quasi-steady-state formulation of substrate uptake kinetics in complex networks and an example application to microbial litter decomposition. Biogeosciences, 10, 8329–8351.
 Tang, J., Riley, W. J., & Zhu, Q. (2022). Supporting hierarchical soil biogeochemical modeling: version 2 of the Biogeochemical Transport and Reaction model (BeTR-v2). Geoscientific Model Development, 15, 1619–1632.
 Tao, J., Riley, W. J., Tang, J., Zhu, Q., Pegoraro, E. L., Castanha, C., Abramoff, R. Z., & Torn, M. S. (2025). Representing Soil Microbial Dynamics and Organo‐Mineral Interactions in the E3SM Land Model (ELM‐ReSOM). Journal of Advances in Modeling Earth Systems, 17, e2024MS004874.
 Abramoff, R. Z., Torn, M. S., Georgiou, K., Tang, J., & Riley, W. J. (2019). Soil Organic Matter Temperature Sensitivity Cannot be Directly Inferred From Spatial Gradients. Global Biogeochemical Cycles, 33, 761–776.
 Tang, J. Y., Riley, W. J., Koven, C. D., & Subin, Z. M. (2013). CLM4-BeTR, a generic biogeochemical transport and reaction module for CLM4: model development, evaluation, and application. Geoscientific Model Development, 6, 127–140.
 