# Input/Output System

<details>
<summary>Relevant source files</summary>


- [example_input/ecacnp-reaction.namelist](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/example_input/ecacnp-reaction.namelist)
- [src/Applications/soil-farm/bgcfarm_util/GeoChemAlgorithmMod.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/Applications/soil-farm/bgcfarm_util/GeoChemAlgorithmMod.F90)
- [src/betr/betr_dtype/BeTR_biogeophysInputType.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/betr/betr_dtype/BeTR_biogeophysInputType.F90)
- [src/betr/betr_math/LinearAlgebraMod.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/betr/betr_math/LinearAlgebraMod.F90)
- [src/driver/clm/BeTRSimulationCLM.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/clm/BeTRSimulationCLM.F90)
- [src/driver/main/BeTRSimulationFactory.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/BeTRSimulationFactory.F90)
- [src/driver/main/sbetrDriverMod.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90)
- [src/driver/shared/BeTRSimulation.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90)
- [src/driver/shared/bncdio_pio.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/bncdio_pio.F90)
- [src/driver/standalone/BeTRSimulationStandalone.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/BeTRSimulationStandalone.F90)
- [src/driver/standalone/ForcingDataType.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/ForcingDataType.F90)
- [src/driver/standalone/GridMod.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/GridMod.F90)
- [src/io_util/histMod.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/histMod.F90)
- [src/io_util/ncdio_pio.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/ncdio_pio.F90)
- [src/jarmodel/driver/jarmodel.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/jarmodel/driver/jarmodel.F90)
- [src/jarmodel/forcing/CMakeLists.txt](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/jarmodel/forcing/CMakeLists.txt)
- [src/jarmodel/forcing/SetJarForcMod.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/jarmodel/forcing/SetJarForcMod.F90)
- [src/stub_clm/WaterFluxType.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/stub_clm/WaterFluxType.F90)
- [templates/reaction.1d.sbetr.nl](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/templates/reaction.1d.sbetr.nl)
- [templates/reaction.jar.sbetr.nl](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/templates/reaction.jar.sbetr.nl)


</details>

## Purpose and Scope

This document describes BeTR's Input/Output (I/O) system, which handles all file-based data operations including reading forcing data and grid configurations, writing time-series output (history files), and saving/restoring simulation state (restart files). The I/O system is built on NetCDF and supports both standalone and coupled execution modes.

For information about the simulation execution flow that uses these I/O capabilities, see [Simulation Execution](#3) . For details on tracer state management that is persisted through the I/O system, see [Tracer State Management](#5.2) .

## I/O Architecture Overview

BeTR's I/O system is organized in layers, with application code interfacing through high-level abstractions that wrap lower-level NetCDF operations:

![SVG image](11.4__Input/Output_System__img-01.svg)

Sources:  [src/driver/shared/BeTRSimulation.F90 1-172](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L1-L172)  [src/driver/main/sbetrDriverMod.F90 1-100](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90#L1-L100)  [src/io_util/histMod.F90 1-60](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/histMod.F90#L1-L60)

## NetCDF I/O Wrapper Modules

BeTR provides two NetCDF wrapper modules that simplify file operations and provide consistent error handling:

### bncdio_pio Module

Located in [src/driver/shared/bncdio_pio.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/bncdio_pio.F90) this module provides a PIO-compatible interface used primarily by the coupled simulation modes. Key data types and functions:

| Type/Function | Purpose | 
| --- | --- |
| file_desc_t | File descriptor containing file handle fh | 
| Var_desc_t | Variable descriptor with varID, rec, and type | 
| ncd_pio_openfile | Open existing file for reading | 
| ncd_pio_createfile | Create new NetCDF file | 
| ncd_pio_closefile | Close file and flush buffers | 
| ncd_defvar | Define variable with dimensions | 
| ncd_putvar | Write variable data (multiple overloaded versions) | 
| ncd_getvar | Read variable data (multiple overloaded versions) | 


Sources:  [src/driver/shared/bncdio_pio.F90 175-187](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/bncdio_pio.F90#L175-L187)

### ncdio_pio Module

Located in [src/io_util/ncdio_pio.F90](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/ncdio_pio.F90) this module provides similar functionality for standalone execution with extensive support for different data types and dimensionalities:

![SVG image](11.4__Input/Output_System__img-02.svg)

Both modules support polymorphic interfaces for reading and writing different data types (integer, real, character) and dimensionalities (0D scalar, 1D, 2D, 3D arrays).

Sources:  [src/io_util/ncdio_pio.F90 30-56](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/ncdio_pio.F90#L30-L56)  [src/io_util/ncdio_pio.F90 175-187](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/ncdio_pio.F90#L175-L187)

## History Output System

The history output system accumulates simulation state and flux variables over time and writes them to NetCDF files at specified frequencies.

### History File Type Structure

The `histf_type` class manages history output:

![SVG image](11.4__Input/Output_System__img-03.svg)

Key components:

| Component | Description | 
| --- | --- |
| varnames | Names of output variables | 
| hrfreq | Output frequency: 'hour', 'day', 'week', 'month', 'year' | 
| var_type | Variable type: var_flux_type or var_state_type | 
| counter | Accumulation counters for each frequency | 
| yvals | Buffer for accumulated values | 
| record | Current record number in each output file | 


Sources:  [src/io_util/histMod.F90 23-57](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/histMod.F90#L23-L57)

### History Output Workflow

![SVG image](11.4__Input/Output_System__img-04.svg)

The system supports multiple output frequencies simultaneously. For flux variables (e.g., respiration rates), values are accumulated as running sums and divided by the counter to compute averages. State variables (e.g., carbon pools) use the most recent value.

Sources:  [src/io_util/histMod.F90 113-158](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/histMod.F90#L113-L158)  [src/io_util/histMod.F90 160-212](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/histMod.F90#L160-L212)

### BeTR History Integration

BeTR simulation objects integrate with the history system through several methods in `BeTRSimulation` :

![SVG image](11.4__Input/Output_System__img-05.svg)

The `BeTRSimulation` type maintains separate arrays for different variable categories:

| Array | Description | Source | 
| --- | --- | --- |
| state_hist1d_var | 1D state variables (column-level) | Tracer pools, scalars | 
| state_hist2d_var | 2D state variables (column × layer) | Vertically-resolved pools | 
| flux_hist1d_var | 1D flux variables | Column-integrated fluxes | 
| flux_hist2d_var | 2D flux variables | Layer-specific fluxes | 


Sources:  [src/driver/shared/BeTRSimulation.F90 93-100](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L93-L100)  [src/driver/shared/BeTRSimulation.F90 512-538](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L512-L538)

### Offline History File Creation

For standalone simulations, history files are created with specific structure:

![SVG image](11.4__Input/Output_System__img-06.svg)

Example from [src/driver/shared/BeTRSimulation.F90 794-875](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L794-L875) :

Sources:  [src/driver/shared/BeTRSimulation.F90 794-875](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L794-L875)

## Restart System

The restart system enables simulation continuation by saving and restoring the complete state at specific points in time.

### Restart File Operations

The restart workflow involves three main operations:

![SVG image](11.4__Input/Output_System__img-07.svg)

Sources:  [src/driver/main/sbetrDriverMod.F90 369-389](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90#L369-L389)  [src/driver/main/sbetrDriverMod.F90 212-222](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90#L212-L222)

### Restart Variable Organization

Restart files contain two categories of variables:

![SVG image](11.4__Input/Output_System__img-08.svg)

The number of restart variables is determined by the BGC model during initialization via `get_restartvar_size` :

Sources:  [src/driver/shared/BeTRSimulation.F90 540-543](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L540-L543)  [src/driver/shared/BeTRSimulation.F90 552-567](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/BeTRSimulation.F90#L552-L567)

### Restart File Naming Convention

Restart files use a standardized naming pattern:

- `{base_filename}.{nstep}.rst.nc`Format:
- `sbetr.00001000.rst.nc`Example: (restart at step 1000)


A companion text file tracks the restart information:

Sources:  [src/driver/main/sbetrDriverMod.F90 371-374](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90#L371-L374)

### Implementation in Standalone Mode

The standalone driver demonstrates the complete restart workflow in [src/driver/main/sbetrDriverMod.F90 159-222](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90#L159-L222) :

Initialization from restart:

Writing restart during simulation:

Sources:  [src/driver/main/sbetrDriverMod.F90 159-222](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90#L159-L222)  [src/driver/main/sbetrDriverMod.F90 369-389](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90#L369-L389)

## Forcing Data Input

The forcing data input system reads time-series environmental and biogeochemical forcing from NetCDF files.

### Forcing Data Type Architecture

![SVG image](11.4__Input/Output_System__img-09.svg)

Sources:  [src/driver/standalone/ForcingDataType.F90 22-72](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/ForcingDataType.F90#L22-L72)

### Forcing Data Categories

Forcing data is organized into several categories:

| Category | Variables | Example NetCDF Variables | 
| --- | --- | --- |
| Soil State | t_soi, h2osoi_liqvol, h2osoi_icevol | TSOI, H2OSOI, SOILICE | 
| Water Fluxes | qflx_infl, qflx_rootsoi, qbot | QINFL, QFLX_ROOTSOI, QCHARGE | 
| Atmospheric | pbot, tbot, finundated | PBOT, TBOT | 
| C-N-P Inputs | cflx_met_vr, nflx_nh4_vr, pflx_po4_vr | CFLX_INPUT_LITR_MET_vr, NFLX_MINN_INPUT_NH4_vr | 


Sources:  [src/driver/standalone/ForcingDataType.F90 30-58](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/ForcingDataType.F90#L30-L58)

### Forcing Data Read Workflow

![SVG image](11.4__Input/Output_System__img-10.svg)

Sources:  [src/driver/standalone/ForcingDataType.F90 340-383](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/ForcingDataType.F90#L340-L383)  [src/driver/standalone/ForcingDataType.F90 191-338](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/ForcingDataType.F90#L191-L338)

### Transient vs. Steady State Forcing

The forcing system supports two modes:

![SVG image](11.4__Input/Output_System__img-11.svg)

In steady state mode, the same environmental conditions are applied at every time step, useful for equilibrium simulations.

Sources:  [src/driver/standalone/ForcingDataType.F90 76-101](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/ForcingDataType.F90#L76-L101)

### Grid Data Input

Grid configuration is read separately from forcing data:

![SVG image](11.4__Input/Output_System__img-12.svg)

Grid types supported:

- **CLM exponential**: Default vertical discretization matching CLM/ELM
- **Uniform**: Equal layer thicknesses
- **Dataset**: Read complete grid from file


Sources:  [src/driver/standalone/GridMod.F90 69-98](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/GridMod.F90#L69-L98)  [src/driver/standalone/GridMod.F90 224-320](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/GridMod.F90#L224-L320)

## Configuration File I/O

BeTR uses Fortran namelist files for configuration. Multiple namelists control different aspects:

### Namelist Organization

![SVG image](11.4__Input/Output_System__img-13.svg)

Example namelist structure from [example_input/ecacnp-reaction.namelist 1-40](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/example_input/ecacnp-reaction.namelist#L1-L40) :

Sources:  [example_input/ecacnp-reaction.namelist 1-40](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/example_input/ecacnp-reaction.namelist#L1-L40)  [templates/reaction.1d.sbetr.nl 1-39](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/templates/reaction.1d.sbetr.nl#L1-L39)

### Namelist Processing

Namelists are read into a character buffer and parsed:

![SVG image](11.4__Input/Output_System__img-14.svg)

This approach allows the same namelist buffer to be parsed multiple times by different modules without repeated file I/O.

Sources:  [src/jarmodel/driver/jarmodel.F90 22-31](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/jarmodel/driver/jarmodel.F90#L22-L31)  [src/driver/main/sbetrDriverMod.F90 408-535](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/main/sbetrDriverMod.F90#L408-L535)

## File Format Specifications

### History File Format

History files follow this structure:

### Restart File Format

Restart files have a simpler structure focused on state preservation:

### Forcing File Format

Forcing files must provide time-series data:

Sources:  [src/driver/standalone/ForcingDataType.F90 386-494](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/standalone/ForcingDataType.F90#L386-L494)

## Performance Considerations

### Buffered I/O

The history system uses buffered accumulation to minimize I/O operations:

![SVG image](11.4__Input/Output_System__img-15.svg)

This reduces file operations from O(N_timesteps) to O(N_timesteps / hist_freq).

### Memory vs. I/O Trade-offs

| Approach | Memory Usage | I/O Operations | Use Case | 
| --- | --- | --- | --- |
| Write every step | Low | High | High-frequency debugging | 
| Buffered (hourly) | Moderate | Moderate | Standard simulations | 
| Buffered (daily/monthly) | Higher | Low | Long-term simulations | 


The system allows multiple output frequencies simultaneously, with separate buffers for each frequency.

Sources:  [src/io_util/histMod.F90 160-212](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/histMod.F90#L160-L212)

### NetCDF Compression

While not explicitly configured in the current code, NetCDF-4 supports transparent compression that can significantly reduce file sizes for large simulations. This can be enabled by adding compression flags during variable definition.

## Error Handling

All NetCDF operations are wrapped with error checking:

The `check_ret` function (from both `bncdio_pio` and `ncdio_pio` modules) checks the return status and calls `endrun` with an informative message if an error occurred.

Sources:  [src/driver/shared/bncdio_pio.F90 217-260](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/driver/shared/bncdio_pio.F90#L217-L260)  [src/io_util/ncdio_pio.F90 217-260](https://github.com/jingtao-lbl/sbetr-resomv1/blob/72301c77/src/io_util/ncdio_pio.F90#L217-L260)