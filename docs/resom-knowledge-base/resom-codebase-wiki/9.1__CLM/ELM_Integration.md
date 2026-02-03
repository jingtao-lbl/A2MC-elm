# CLM/ELM Integration

<details>
<summary>Relevant source files</summary>


- [example_input/ecacnp-reaction.namelist](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/example_input/ecacnp-reaction.namelist)
- [src/Applications/soil-farm/bgcfarm_util/GeoChemAlgorithmMod.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/Applications/soil-farm/bgcfarm_util/GeoChemAlgorithmMod.F90)
- [src/betr/betr_dtype/BeTR_biogeophysInputType.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/betr/betr_dtype/BeTR_biogeophysInputType.F90)
- [src/driver/clm/BeTRSimulationCLM.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90)
- [src/driver/main/BeTRSimulationFactory.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/BeTRSimulationFactory.F90)
- [src/driver/main/sbetrDriverMod.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90)
- [src/driver/shared/BeTRSimulation.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90)
- [src/driver/shared/bncdio_pio.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/bncdio_pio.F90)
- [src/driver/standalone/BeTRSimulationStandalone.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/BeTRSimulationStandalone.F90)
- [src/driver/standalone/ForcingDataType.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/ForcingDataType.F90)
- [src/driver/standalone/GridMod.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/GridMod.F90)
- [src/stub_clm/WaterFluxType.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/stub_clm/WaterFluxType.F90)


</details>

## Purpose and Scope

This document describes how BeTR integrates with the Community Land Model (CLM) and Energy Exascale Earth System Model Land (ELM) surface models. The integration enables BeTR's reactive transport and biogeochemistry models to run as coupled components within these land surface models.

For information about standalone BeTR simulations that do not require an LSM, see [Simulation Modes](#3.1) . For details on the data exchange protocol between land models and BeTR, see [Data Exchange Protocol](#9.2) .

## Integration Architecture

BeTR uses an adapter pattern to integrate with different land surface models. Each LSM has a dedicated simulation class that extends the base `betr_simulation_type` and maps LSM-specific data structures to BeTR's internal data structures.

### Simulation Class Hierarchy

![SVG image](9.1__CLM/ELM_Integration__img-01.svg)

Sources:  [src/driver/shared/BeTRSimulation.F90 68-170](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L68-L170)  [src/driver/clm/BeTRSimulationCLM.F90 41-58](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90#L41-L58)

### Data Structure Mapping

BeTR maintains its own internal data structures and maps LSM variables to them through the `betr_biogeophys_input_type` . The mapping process isolates BeTR's core from LSM-specific implementations.

![SVG image](9.1__CLM/ELM_Integration__img-02.svg)

Sources:  [src/driver/shared/BeTRSimulation.F90 68-121](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L68-L121)  [src/betr/betr_dtype/BeTR_biogeophysInputType.F90 16-131](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/betr/betr_dtype/BeTR_biogeophysInputType.F90#L16-L131)

## Initialization Process

### CLM/ELM-Specific Initialization

The initialization process sets up the BeTR simulation environment within the CLM/ELM context. This includes configuring grid dimensions, allocating data structures, and establishing parameter mappings.

![SVG image](9.1__CLM/ELM_Integration__img-03.svg)

Sources:  [src/driver/clm/BeTRSimulationCLM.F90 81-132](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90#L81-L132)  [src/driver/shared/BeTRSimulation.F90 378-550](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L378-L550)

### Key Initialization Components

| Component | CLM/ELM Type | BeTR Type | Mapping Location | 
| --- | --- | --- | --- |
| Vertical levels | nlevsoi, nlevsno | betr_nlevsoi, betr_nlevsno | BeTRSimulationCLM.F90109-111 | 
| Plant functional types | nc3_arctic_grass, etc. | betr_pftvarcon%* | BeTRSimulationCLM.F90114-117 | 
| Landunit types | istsoil, istcrop | betr_landvarcon%* | BeTRSimulationCLM.F90119-121 | 
| Column filter | col%active(:) | active_col(:) | BeTRSimulation.F90451-455 | 


Sources:  [src/driver/clm/BeTRSimulationCLM.F90 81-132](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90#L81-L132)  [src/driver/shared/BeTRSimulation.F90 378-457](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L378-L457)

## Time-Stepping and Coupling

### Two-Phase Time-Stepping

BeTR uses Strang splitting to separate transport processes that occur with and without drainage. This improves numerical accuracy by treating different physical processes with appropriate time-stepping strategies.

![SVG image](9.1__CLM/ELM_Integration__img-04.svg)

Sources:  [src/driver/clm/BeTRSimulationCLM.F90 188-234](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90#L188-L234)  [src/driver/main/sbetrDriverMod.F90 272-346](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90#L272-L346)

### Data Transfer Methods

The `SetBiophysForcing` method is the primary interface for transferring environmental conditions from CLM/ELM to BeTR:

![SVG image](9.1__CLM/ELM_Integration__img-05.svg)

Sources:  [src/driver/clm/BeTRSimulationCLM.F90 236-389](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90#L236-L389)  [src/driver/shared/BeTRSimulation.F90 459-460](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L459-L460)

## LSM Data Structure Usage

### Required CLM/ELM Types

The following CLM/ELM data types are used in the integration:

| Type | Purpose | Key Fields Used | 
| --- | --- | --- |
| waterstate_type | Water content and phase | h2osoi_liq, h2osoi_ice, h2osoi_vol | 
| waterflux_type | Water fluxes | qflx_rootsoi, qflx_infl, qflx_drain_vr | 
| temperature_type | Soil and vegetation temperature | t_soisno, t_soi_10cm | 
| carbonflux_type | Carbon inputs to soil | cflx_input_litr_met_vr, rr_vr | 
| nitrogenflux_type | Nitrogen inputs and transformations | nflx_input_litr_*_vr, nflx_minn_input_* | 
| phosphorusflux_type | Phosphorus inputs | pflx_input_litr_*_vr | 
| soilhydrology_type | Hydraulic properties | fracice, qflx_bot | 
| atm2lnd_type | Atmospheric forcing | forc_pbot, forc_t | 


Sources:  [src/driver/clm/BeTRSimulationCLM.F90 236-278](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90#L236-L278)  [src/betr/betr_dtype/BeTR_biogeophysInputType.F90 16-131](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/betr/betr_dtype/BeTR_biogeophysInputType.F90#L16-L131)

### Conditional Compilation

BeTR uses preprocessor directives to handle differences between CLM and ELM:

![SVG image](9.1__CLM/ELM_Integration__img-06.svg)

Sources:  [src/driver/shared/BeTRSimulation.F90 18-42](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L18-L42)

## Plant-Soil BGC Coupling

### Send/Receive Pattern

For soil biogeochemistry simulations, BeTR uses a send/receive pattern to exchange carbon, nitrogen, and phosphorus fluxes:

![SVG image](9.1__CLM/ELM_Integration__img-07.svg)

Sources:  [src/driver/clm/BeTRSimulationCLM.F90 391-575](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90#L391-L575)  [src/driver/main/sbetrDriverMod.F90 286-332](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90#L286-L332)

## Stub CLM Types

For standalone BeTR simulations, the `src/stub_clm/` directory provides minimal implementations of CLM/ELM types. This allows BeTR to compile and run independently while maintaining the same interface.

### Stub Type Structure

![SVG image](9.1__CLM/ELM_Integration__img-08.svg)

Sources:  [src/stub_clm/WaterFluxType.F90 1-92](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/stub_clm/WaterFluxType.F90#L1-L92)  [src/driver/shared/BeTRSimulation.F90 18-42](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L18-L42)

## Configuration and Namelist

### CLM/ELM-Specific Parameters

When running in coupled mode, certain BeTR parameters must be consistent with CLM/ELM configuration:

| Parameter | CLM/ELM Source | BeTR Variable | Notes | 
| --- | --- | --- | --- |
| nlevsoi | elm_varpar | betr_nlevsoi | Number of soil layers | 
| nlevgrnd | elm_varpar | Grid specification | Total subsurface layers | 
| nlevtrc_soil | elm_varpar | betr_nlevtrc_soil | Layers for tracer transport | 
| dzsoi | Column properties | betr_col(c)%dz | Layer thickness | 
| zsoi | Column properties | betr_col(c)%z | Layer center depth | 


Sources:  [src/driver/clm/BeTRSimulationCLM.F90 109-112](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90#L109-L112)  [src/driver/shared/BeTRSimulation.F90 441-442](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L441-L442)

## Error Handling and Status Reporting

BeTR uses a status tracking system to propagate errors from individual columns up to the simulation level:

Sources:  [src/driver/clm/BeTRSimulationCLM.F90 225-232](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90#L225-L232)  [src/driver/shared/BeTRSimulation.F90 466-470](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L466-L470)