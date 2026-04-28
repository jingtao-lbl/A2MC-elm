---
**Source pin:** EcoSIM commit `2dea74d9` (jinyun1tang/EcoSIM, 2026-04-23)
**Scope:** core orchestration: `f90src/{Main, Ecosim_mods, Modelconfig, Modelpars, Mesh, Utils, Minimath, DebugTools}/`
**Last verified:** 2026-04-24
---

# Model Configuration and Parameters

This doc describes two directories:

- `f90src/Modelconfig/` — run-mode flags, simulation type, solver sub-cycle counts, chemical-element IDs, tracer IDs.
- `f90src/Modelpars/` — scientific parameter tables and physical-property constants.

The split is important. `Modelconfig` is what an operator twiddles (namelist, command line, build flags). `Modelpars` is where scientific values live (Michaelis-Menten constants, equilibrium constants, diffusivities, solubilities, parameter objects `micpar` and `pltpar`).

## Modelconfig

### `Modelconfig/EcoSIMConfig.F90` (98 lines)

Module-level flags, compile-time counts, restart-type logic.

Compile-time parameters (f90src/Modelconfig/EcoSIMConfig.F90:18-23):

| Parameter | Value | Meaning |
|---|---|---|
| `NumDeadMicrbCompts` | 2 | number of microbial residue components |
| `NumLiveMicrbCompts` | 3 | number of living biomass components |
| `jskenc` | 4 | number of kinetic components of substrates |
| `jcplxc` | 5 | number of microbe-substrate complexes |
| `jcplxcm1` | `jcplxc-1 = 4` | commonly aliased as `jcplx1` |
| `NumMicbFunGrupsPerCmplx` | 7 | number of microbial functional groups per complex |

Runtime flags (f90src/Modelconfig/EcoSIMConfig.F90:7-16): `is_first_year`, `transport_on`, `column_mode`, `do_instequil`, `brnch_retain_casename`, `iFlagRaiseZ0GbyVeg`. Of these, `column_mode` is consulted by `Mesh/GridMod.F90:103` when sizing `JX`/`JY`, and `iFlagRaiseZ0GbyVeg` controls whether surface-roughness grows with vegetation.

Restart support (f90src/Modelconfig/EcoSIMConfig.F90:38-45): integer parameters `nsrStartup=0`, `nsrContinue=1`, `nsrBranch=2`, stored in `nsrest`. Helper functions `is_restart()` (:48), `is_branch()` (:61), and `cold_run()` (:92) are thin wrappers over `nsrest`. `set_sim_type()` at :75-89 decides the restart mode based on `continue_run` (from `EcoSIMCtrlMod`) and whether `finidat` is empty.

Metadata strings: `ref_date`, `start_date`, `case_name`, `finidat`, `ctitle`, `restartFileFullPath`, `hostname`, `username`, `source="ECOSIM"`, `version`, and restart I/O paths `rpntdir='.'`, `rpntfil='rpointer.esim'`, `inst_suffix=''`.

### `Modelconfig/EcoSIMCtrlMod.F90` (132 lines)

The big dashboard. Flags consumed by virtually every subsystem (f90src/Modelconfig/EcoSIMCtrlMod.F90:11-77):

Core mode toggles:
- `salt_model=.false.` — enable salt/PO4 mineral tracer set (changes `idsalt_*` range in `TracerIDMod`)
- `erosion_model=.false.`, `iErosionMode=-1`
- `plant_model=.true.`, `microbial_model=.true.`, `soichem_model=.true.`
- `snowRedist_model=.true.`
- `ATS_cpl_mode=.false.` — coupled to Amanzi-ATS hydrology engine
- `plantOM4Heat=.false.`, `fixWaterLevel=.false.`, `lsoilCompaction=.false.`
- `ldo_sp_mode=.false.` (satellite phenology), `mod_snow_albedo=.false.`
- `ldo_radiation_test=.false.`, `ldo_transpt_bubbling=.true.` (ebullition during transport)
- `first_topou=.false.`, `first_pft=.false.` (restrict simulation to first topo-unit / first PFT)
- `Lirri_auto=.false.`, `fixClime=.false.`
- `disp_planttrait=.true.`, `disp_modelconfig=.true.`
- `grid_mode = 3` (vertical only)

Diagnostics: `idebug_day=-1`, `idebug_year=-1`, `iselect_plantZ=-1`, `iVerbLevel=0`, `do_budgets=.false.`, `diag_opt='nsteps'`, `diag_frq=-999999999`, `lverb`, `do_rgres`.

Atmospheric GHG mixing ratios (f90src/Modelconfig/EcoSIMCtrlMod.F90:34-44) — defaults approximate 1800-era atmospheric composition:
`aco2_ppm=280`, `ach4_ppm=1.144`, `an2o_ppm=0.270`, `ao2_ppm=0.209e6`, `arg_ppm=0.00934e6`, `an2_ppm=0.78e6`, `anh3_ppm=5.e-3`, `ah2_ppm=0.55`. Override sentinels: `atm_co2_fix=-100`, `atm_ch4_fix=-100`, `atm_n2o_fix=-100`.

File paths (:46-54): `pft_file_in`, `pft_mgmt_in`, `grid_file_in`, `clm_hour_file_in`, `clm_day_file_in`, `soil_mgmt_in`, `clm_factor_in`, `atm_ghg_in`, `micpar_file_in`.

Solver sub-cycle counts (:71-73):
- `NPXS(5)`, `NPYS(5)` — arrays of sub-cycle counts per forcing period
- `NCYC_LITR` — number of subcycles for litter
- `NCYC_SNOW` — number of subcycles for snow

Clock and forcing: `yearf1`, `yearf2`, `nyeardal1`, `continue_run`, `restart_out`, `visual_out`, `hist_yrclose`, `hist_config(10)`, `sim_yyyymmdd`, `forc_periods(15)`.

Two non-trivial objects:
- `type(file_desc_t) :: pft_nfid` (:57) — the netCDF file handle for the PFT trait file, opened in `PlantInfoMod`.
- `type(ecosim_time_type) :: etimer` (:58) — the simulation clock; see `utilities.md`.

Nested record type (:80-93): `forc_data_rec_type` with fields `pft_rec`, `yearclm`, `yearacc`, `yearcur`, `yearpre`, `yearrst`, `lskip_loop`, `ymdhs0` (the starting YYYYMMDDHHMMSS stamp), bound method `Init`. Singleton `frectyp`.

Utility: `get_sim_len(forc_periods, nperiods)` (:112-129) reads `forc_periods` in triplets of (year_start, year_end, count) and sums `(abs(end-start)+1)*count` across all triplets; aborts via `endrun` if the result is negative.

### `Modelconfig/EcoSIMSolverPar.F90` (26 lines)

Global solver time-step bookkeeping (f90src/Modelconfig/EcoSIMSolverPar.F90:10-24). Set by `StartsMod.set_ecosim_solver` once per forcing period.

Real time steps in hours:
- `dts_wat` — water transport
- `dts_sno` — snow processes
- `dt_watvap` — water vapor fluxes
- `dts_HeatWatTP` — heat/water/solute transport
- `dt_GasCyc`, `dts_gas` — gas cycle iteration / gas flux update
- Unused auxiliaries: `XNPB`, `XNPD`, `XNPR`, `XNPS`

Integer cycle counts per hour (one forcing hour is partitioned into these sub-cycles):
- `NPH` — heat and water flux cycles per hour
- `NPT` — gas flux cycles within each `NPH`
- `NPG` — gas flux cycles per hour
- `NPR` — surface-litter heat/water cycles per time step
- `NPS` — snowpack heat/water cycles

Plus `oscal_test` (debug scalar).

### `Modelconfig/ElmIDMod.F90` (213 lines)

Pure-integer-parameter module; no allocatable state. Defines enumerations consumed by many modules.

Chemical elements (f90src/Modelconfig/ElmIDMod.F90:8-11):
- `ielmc=1` (carbon), `ielmn=2` (nitrogen), `ielmp=3` (phosphorus), `NumPlantChemElms=3`

Microbial biomass components (:13-15): `ibiom_kinetic=1`, `ibiom_struct=2`, `ibiom_reserve=3`.

Erosion modes (:18-22): `ieros_noaction=-1`, `ieros_frzthawelv=0`, `ieros_frzthaweros=1`, `ieros_frzthawsom=2`, `ieros_frzthawsomeros=3`.

Irrigation trigger types (:24-25): `iIrrig_swc=0`, `iIrrig_cwp=1`.

Flux directions (:27-31): `iWestEastDirection=1`, `iNorthSouthDirection=2`, `iVerticalDirection=3`, `iFront=1`, `iBehind=2`.

Soil property slot IDs (:33-38): `isoi_fc=1`, `isoi_wp=2`, `isoi_scnv=3`, `isoi_scnh=4`, `isoi_set=0`, `isoi_unset=1`.

Plant harvest fractions (:40-43) and harvest-operation codes `iharvtyp_*` (:108-114), with helper functions `StriHarvtype(iharvtyp)` (:191-212) and `StrjHarvtype(jhavtype)` (:176-189) that map codes to strings (used in log output).

Photosynthesis pathway (:45-46): `ic4_photo=4`, `ic3_photo=3`.

Fertilizer and amendment types (:48-73), manure categories (:75-77), plant-residue types (:79-86): these are string-free integer codes used by reader modules to route inputs.

Root-order, root-profile, mycorrhizae, plant-root-vs-mycorrhizal (:88-97). Phenology (:150-153): `iphenotyp_evgreen=0`, `iphenotyp_coldecid=1`, `iphenotyp_drouhtdecidu=2`, `iphenotyp_coldroutdecid=3`.

N-fixation types (:155-161), thermo-zones (:163-167), tillage (:169-170), plant calendar stages `ipltcal_*` (:128-138, a 10-stage pheno sequence from Planting to EndSeedFill), photoperiod types (:140-142), embryo types (:144-148).

### `Modelconfig/TracerIDMod.F90` (410 lines)

Defines and populates the integer indices that all transport, chemistry, and I/O code uses to find individual tracers inside packed arrays.

**Gas tracer IDs** are compile-time constants (f90src/Modelconfig/TracerIDMod.F90:13-20):

| Constant | Value | Species |
|---|---|---|
| `idg_CO2` | 1 | CO2 |
| `idg_CH4` | 2 | CH4 |
| `idg_O2` | 3 | O2 |
| `idg_N2` | 4 | N2 |
| `idg_N2O` | 5 | N2O |
| `idg_H2` | 6 | H2 |
| `idg_AR` | 7 | Ar |
| `idg_NH3` | 8 | NH3 |

`idg_beg=idg_CO2=1`. The "banded NH3" pseudo-gas `idg_NH3B` and the end-index `idg_end` are set at runtime inside `InitTracerIDs` (:183-184).

**Dynamic tracer IDs** are assigned by `InitTracerIDs(lsalt_model)` (:170-402) at model init. `InitAllocMod` invokes it via `call InitTracerIDs(salt_model)` (f90src/Ecosim_mods/InitAllocMod.F90:76). The helper `addone(idx)` from `MiniMathMod` returns `idx+1` and also mutates its argument in place, giving tightly packed sequential IDs.

Solute tracers (non-band then band) populated at :186-201: after `idg_NH3B`, add `ids_NH4B`, `ids_NO3B`, `ids_NO2B`, `ids_H1PO4B`, `ids_H2PO4B` (band group), then `ids_NH4`, `ids_NO3`, `ids_NO2`, `ids_H1PO4`, `ids_H2PO4` (non-band). `ids_beg=idg_beg`; `ids_end` tracks the running end.

Solubility caps `tracerSolc_max(ids_beg:ids_end)` are allocated at :206 with default 1.e3 g/m^3 and adjusted for NH3, NH4, and NO3 at :208-214 based on 25 °C solubility (NH3 at 320 g/L, NH4Cl at 370 g/L, NaNO3 at 912 g/L).

Human-readable names go into `trcs_names(ids_beg:ids_end)` at :216-226.

DOM tracers (:229-233): `idom_DOC=1`, `idom_DON=2`, `idom_DOP=3`, `idom_acetate=4`. `trc_confs%NDOMS = idom_end-idom_beg+1 = 4`.

Salt tracers (:235-302): enumerated in a single contiguous block `idsalt_Al`, `idsalt_Fe`, `idsalt_Ca`, `idsalt_Mg`, `idsalt_Na`, `idsalt_K`, `idsalt_SO4`, `idsalt_Cl`. These 8 are always present (required for irrigation chemistry). If `lsalt_model` is true, a long list follows: `idsalt_Hp`, `idsalt_OH`, `idsalt_CO3`, `idsalt_HCO3`, 5 Al–OH/SO4 species, 5 Fe–OH/SO4 species, 4 Ca–O/CO3/SO4 species, 3 Mg–O/CO3 species, 2 Na species, 1 K species, and 8 soil phosphate species (:274-281), then 8 matching band-phosphate species (:290-298).

Precipitate tracers `idsp_*` (:304-327): `AlOH3`, `FeOH3`, `CaCO3`, `CaSO4` are always defined; then phosphate precipitates `Apatite`, `AlPO4`, `FePO4`, `CaHPO4`, `CaH4P2O8` for soil, with matching `*B` versions for the band (:313-325).

Exchangeable tracers `idx_*` (:329-364): cations first (CEC + NH4, H, Al, Fe, Ca, Mg, Na, K, COOH, AlOH2, FeOH2, NH4B), then AEC + anions (OHe, OH, OHp, HPO4, H2PO4, and their band versions).

Summary counts stored in `trc_confs` at :366-374:

| Field | Formula |
|---|---|
| `NGasTracers` | `idg_end - idg_beg` |
| `NSolutTracers` | `idg_end - ids_beg + 1` |
| `NSaltTracers` | `idsaltb_end - idsalt_beg + 1` (only if `lsalt_model`) |
| `NPrecipTracers` | `idsp_end - idsp_beg + 1` |
| `nxtracers` | `idx_end - idx_beg + 1` |
| `NnutrientTracers` | `ids_nuts_end - ids_nut_beg + 1` |
| `NFertNitro` | `ifertn_end - ifertn_beg + 1` |
| `NFertNitrob` | `ifertnb_end - ifertnb_beg + 1` |
| `NDOMS` | `idom_end - idom_beg + 1` |

`CleanUpTracerIDs()` at :404-408 destroys `trcs_names` and is invoked from `EcoSIMDesctruct` (:135).

## Modelpars

### `Modelpars/EcoSiMParDataMod.F90` (9 lines — the whole thing)

The single module-level aggregator. Declares two public globals (f90src/Modelpars/EcoSiMParDataMod.F90:7-8):

- `type(plant_bgc_par_type), target :: pltpar` — populated by `PlantBGCPars.InitVegPars` inside `InitAllocMod → InitPlantTraitTable`.
- `type(MicParType), target :: micpar` — populated by `MicBGCPars.Init` + `SetPars`, driven through `InitAllocMod → InitSOMBGC`.

Every subsystem that needs plant or microbial parameters does `use EcoSiMParDataMod, only: micpar, pltpar`. There is no plain-array alternative.

### `Modelpars/MicBGCPars.F90` (537 lines) — `MicParType` and `micpar`

Module-level globals outside the type hold per-functional-group guild counts (f90src/Modelpars/MicBGCPars.F90:14-26): `NumGuild_Heter_Aerob_Bact`, `NumGuild_Heter_Aerob_Fung`, `NumGuild_Heter_Facul_Dent`, `NumGuild_Heter_Aerob_N2Fixer`, `NumGuild_Heter_Anaer_N2Fixer`, `NumGuild_Heter_Anaer_Fermentor`, `NumGuild_Heter_AcetoMethanogen`, `NumGuild_Autor_H2genMethanogen`, `NumGuild_Autor_AmoniaOxidBact`, `NumGuild_Autor_NitritOxidBact`, `NumGuild_Autor_AerobMethOxid`, `NumGuild_Autor_ANMO_ANME2d`, `NumGuild_Autor_ANMO_ANMENC10`. All default to 1; they are overridden via the `&Microbes` namelist (see `MicrobeConfigMod` below).

`type MicParType` (f90src/Modelpars/MicBGCPars.F90:28-115) packages:

- Pointer allocatable arrays — stoichiometry (`rNCOMC`, `rPCOMC`, `rNCOMCAutor`, `rPCOMCAutor`, `rNCOMC_ave`, `rPCOMC_ave`), colonization (`DOSA`), specific decomposition rates (`SPOSC`), C:N:P fractions for kinetic components (`ORCI`, `FL`, `CNOFC`, `CPOFC`, `CNRH`, `CPRH`), initial biomass fractions (`OMCF`, `OMCA`, `OMCI`, `OHCK`, `OMCK`, `ORCK`, `OQCK`).
- Scalar indices — `jcplx`, `jsken`, `NumMicbFunGrupsPerCmplx`; litter complex IDs `k_woody_comp`, `k_fine_comp`, `k_manure`, `k_POM`, `k_humus`; functional-group IDs `mid_Auto*`, `mid_Heter*`, `mid_fermentor`, `mid_AutoAMO*`; kinetic-component IDs `iprotein`, `icarbhyro`, `icellulos`, `ilignin`.
- Counts — `NumMicrobAutoTrophCmplx`, `NumHetetr1MicCmplx`, `NumOfLitrCmplxs`, `NumOfPlantLitrCmplxs` (woody + fine), `NumLiveHeterBioms`, `NumLiveAutoBioms`, `ndbiomcp` (residue components), `nlbiomcp` (living components).
- Logical flags per guild — `is_activeMicrbFungrpAutor`, `is_activeMicrbFungrpHeter`, `is_aerobic_hetr`, `is_anaerobic_hetr`, `is_aerobic_autor`, `is_CO2_autotroph`, `is_litter`, `is_finelitter`.
- Name arrays — `kiname(jskenc)`, `cplxname(1:jcplxc)`, `hmicname`, `amicname`, `micresb`, `micbiom`.

Methods (f90src/Modelpars/MicBGCPars.F90:109-114): `Init`, `SetPars`, `get_micb_id(M,NGL)` (:499-511 — returns the linear biomass index given component `M` and guild `NGL`), `is_group_defined(igroup, isauto)` (:515-536), `destroy` (bound to `DestructMicBGCPar` at :466-496).

### `Modelpars/MicrobeConfigMod.F90` (48 lines)

Single public entry `ReadMicrobeNamelist(nml_buffer)` (f90src/Modelpars/MicrobeConfigMod.F90:9, :12-47) that parses a `&Microbes` namelist in `nml_buffer` and overrides the `NumGuild_*` globals in `MicBGCPars`. All guild counts default to 1; the namelist can raise them.

### `Modelpars/NitroPars.F90` (322 lines)

Large module-level parameter block for microbial/nitrification/denitrification kinetics. Over 70 scalar parameters organized by process (f90src/Modelpars/NitroPars.F90:19-80+): microbial morphology (`ORAD`, `BIOS`, `BIOA`), decomposition (`DCKI`, `DCKM0`, `DCKML`, `FPRIM`, `OMGR`, `COMKI`, `COMKM`), C recycling (`RCCX`, `RCCQ`, `RCCZ`, `RCCY`, `CKC`), specific oxidation rates (`VMXO` bacteria, `VMXF` fungi, `VMXCH4gAcet`, `VMXNH3Oxi`, `VMXNO2Oxi`, `VMXCH4OxiAero`, `VMXCH4gH2`), uptake kinetics (`OQKM`, `OQKA`, `OQKAM` for DOC/acetate; `Z4MX`, `Z4KU`, `Z4MN` for NH4; `ZOMX`, `ZOKU`, `ZOMN` for NO3; `HPMX`, `HPKU`, `HPMN` for H2PO4; `ZFKM` for N2; `H2KM` for H2), efficiencies (`EAMO10`, `EAMO2D`, `ECNH`, `ECNO`, `ECHO`), and inhibition (`RNFNI`, `ZHKI`, `VMKI`, `VHKI`).

Two public routines at :121 and :232: `initNitroPars` (sets defaults), `ReadPars()` (reads from the netCDF file identified by `micpar_file_in` via `ncdio_pio`).

### `Modelpars/PlantBGCPars.F90` (319 lines) — `plant_bgc_par_type` and companion routines

Module-level scalars (f90src/Modelpars/PlantBGCPars.F90:15-140+) cover allocation (`FracHour4LeafoffRemob(0:5)`, `PART2LEAF_MIN`, `PART2PETOL_MIN`), respiration (`VMXC`, `RmSpecPlant`), phenology timing (`Hours4PhyslMature`, `Hours4FullSenes`, `Hours4ConiferSpringDeharden`, `Days2CallFalseBreak`), turnover (`XFRX`, `XFRY`, `FXFS`, `FMYC`, `RSpecLiterFall`), water relations (`TurgPSIMin4OrganExtens`, `RCMN`, `RTDPX`, `Root2ndTipLen4uptk`, `EMODR`), photosynthesis (`QNTM`, `CURV`, `CNKI_rubisco`, `CPKI_rubisco`, `RSMY_stomaCO2`, `C4KI_pepcarboxy`, `RCytoK(2)`, `kDCytof(2)`, `kDCytoC`, `ELEC3`, `ELEC4`, `CO2KI`, `FCMassCO2BundleSheath_node`, `FCMassHCO3BundleSheath_node`, `COMP4`, `FWCLeaf`, `FWCBundlSheath`, `FWCMesophyll`, `ZPLFM`, `ZPGRM`), wood/stalk structure (`FSTK`, `ZSTX`, `BlkDensFineRoots`, `BlkDActCoarseRoots`, `BlkDLigCoarseRoots`, `StalkMassDensity`, `SpecStalkVolume`, `FRTX`), seed set (`SETC`, `SETN`, `SETP`), morphology (`SLA2`, `SSL2`, `SNL2`), C:N:P ratios (`CNMX`, `CPMX`, `CNMN`, `CPMN`, `CNKI`, `CPKI`), N fixation (`EN2F`, `VMXO`, `SPNDLK`, `SPNDL`).

`type plant_bgc_par_type` wraps grid-derived counts that are copied in by `InitPlantMorphSize` (see `main_orchestration.md` §3) plus kinetic-component IDs and root counts (`iprotein`, `icarbhyro`, `icellulos`, `ilignin`, `k_woody_comp`, `k_fine_comp`, `jroots`, `NMaxRootSegs`, `jcplx`, `NumOfPlantLitrCmplxs`, `jsken`, `NumLitterGroups`, etc.).

Public routines: `InitPlantTraitTable(pltpar, NumGrowthStages, MaxNumRootAxes)` at :160-175 (calls `InitVegPars` then `AllocPlantTraitTable`), and `InitVegPars(pltpar, npft, nkopenclms, npfts_tab)` at :178-317 which reads the PFT trait netCDF file (path in `EcoSIMCtrlMod%pft_file_in`).

### `Modelpars/ChemTracerParsMod.F90` (56 lines)

Parameters only; no routines. All `real(r8), parameter`.

- **Molecular diffusivities** (f90src/Modelpars/ChemTracerParsMod.F90:10-44): gaseous and aqueous diffusivities in m^2/h for every gas and aqueous species. Names follow `<Species>SG` for gas and `<Species>SG`/`<Species>SL` conventions (e.g., `CGSG`, `CLSG` for CO2 gas/aqueous; `OGSG`, `OLSG` for O2; `ZGSG`, `ZLSG` for N2; `ZHSG`, `ZNSG` for NH3; `ZOSG` for NO3; `POSG` for PO4; `WGSG` for water vapor; plus Al/Fe/H/Ca/Mg/Na/K/OH/CO3/HCO3/SO4/Cl aqueous diffusivities at a uniform 5e-6 m^2/h).
- **Gas solubility coefficients at 25 °C** (:46-53): `SARX`, `SCO2X`, `SCH4X`, `SOXYX`, `SN2GX`, `SN2OX`, `SNH3X`, `SH2GX` in units of g solute per g gas.

### `Modelpars/SoluteParMod.F90` (155 lines)

Equilibrium constants for every aqueous reaction considered by the geochemistry module. Pure parameter module, no routines.

- **Water and bulk dissociation** (f90src/Modelpars/SoluteParMod.F90:11-13): `DPH2O=6.5e-9` (water auto-ionization), `SPALO`, `SPFEO`, `SPCAC`, `SPCAS` (solubility products of hydroxide/carbonate/sulfate solids).
- **Phosphate precipitation/dissolution** (:15-20): `SPALP` (AlPO4), `SPFEP` (FePO4), `SPCAM` (`Ca(H2PO4)2`), `SPCAD` (CaHPO4), `SPCAH` (hydroxyapatite `Ca5(PO4)3OH`).
- **Surface complexation on X sites** (:21-24): `SXOH2`, `SXOH1`, `SXH2P`, `SXH1P`.
- **Carbonate system** (:25-26): `DPCO2`, `DPHCO`. Combined `DPCO3=DPCO2*DPHCO`.
- **Ammonium** (:27): `DPN4` (NH4+ ⇌ NH3 + H+).
- **Al-OH-SO4** and **Fe-OH-SO4** complexes (:28-37): `DPAL1..DPAL4`, `DPALS`, `DPFE1..DPFE4`, `DPFES`.
- **Ca/Mg/Na/K binary complexes** (:38-48): `DPCAO`, `DPCAC`, `DPCAH`, `DPCAS`, `DPMGO`, `DPMGC`, `DPMGH`, `DPMGS`, `DPNAC`, `DPNAS`, `DPKAS`.
- **Phosphate aqueous speciation** (:49-57): `DPH1P`, `DPH2P`, `DPH3P`, `DPF1P`, `DPF2P`, `DPC0P`, `DPC1P`, `DPC2P`, `DPM1P`.
- **X-COO complexes** (:58-60): `DPCOH`, `DPALO`, `DPFEO`.

Derived combined constants (:62-125) follow a consistent naming scheme where `SH…` means the reaction written with H+ on the reactant side and `SY…` means the reaction written with OH- on the reactant side. For example, `SHA0P1=SPALP/DPH1P` gives the effective K for `AlPO4(s)+H+ = Al(3+)+HPO4(2-)` (:83).

Miscellaneous kinetics at the bottom (:127-152): `DUKM`, `DUKI` (urea hydrolysis), `COOH`, `CCAMX`, `RFertNH4SpecReleaz`, `RFertNH3SpecReleaz`, `RFertUreaSpecHydrol`, `RFertNO3SpecReleaz`, `SPPO4`, plus `MRXN=1` (reaction-equilibrium cycles per step) and rate constants `TPD`, `TPDX`, `TADA`, `TADAX`, `TADC`, `TADCX`, `TADC0`, `TSL`, `TSLX`. These are consumed by the Geochem subsystem.

`RUreaInhibtorConst(0:2)` at :10 is a rank-1 parameter array of urea-hydrolysis-inhibitor rate constants (values `0.1`, `0.01`, `0.005` h^-1).

### `Modelpars/TracerPropMod.F90` (149 lines)

Public functions (f90src/Modelpars/TracerPropMod.F90:13-16): `gas_solubility(gid, tempC)`, `GramPerHr2umolPerSec(gid)`, `GasSechenovConst`, `MolecularWeight`.

- `gas_solubility(gid, tempC)` at :21-51: temperature-dependent gas solubility. Select-case on `gid` against `idg_CO2/CH4/O2/NH3/N2O/N2/H2/AR` (imported from `TracerIDMod`). Most use `coef = S*X * EXP(a - b*tempC)` with species-specific `a`, `b`; argon uses a Boltzmann form with reference 298.15 K. Aborts via `endrun` for unknown IDs.
- `GramPerHr2umolPerSec(gid)` at :55-78: converts g/h to μmol/s via `gH1hour2umol1sec = 1e6/3600` divided by species molar mass (12 for CO2/CH4, 32 for O2, 14 for NH3, 28 for N2O/N2, 2 for H2, 39.95 for Ar).
- `GasSechenovConst` and `MolecularWeight`: similar select-case helpers; consult the file for the species list.
