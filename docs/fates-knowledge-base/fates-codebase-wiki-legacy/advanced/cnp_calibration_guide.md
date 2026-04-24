# FATES-CNP Calibration Guide

<details>
<summary>Relevant source files</summary>

- [parteh/PRTAllometricCNPMod.F90](https://github.com/NGEET/fates/blob/main/parteh/PRTAllometricCNPMod.F90) - CNP allocation, PID controller, prescribed uptake
- [biogeochem/FatesSoilBGCFluxMod.F90](https://github.com/NGEET/fates/blob/main/biogeochem/FatesSoilBGCFluxMod.F90) - Nutrient uptake, ECA/RD competition
- [main/FatesInterfaceTypesMod.F90](https://github.com/NGEET/fates/blob/main/main/FatesInterfaceTypesMod.F90) - Mode constants (prescribed vs coupled)
- [main/EDPftvarcon.F90](https://github.com/NGEET/fates/blob/main/main/EDPftvarcon.F90) - PFT parameter definitions
- [main/EDParamsMod.F90](https://github.com/NGEET/fates/blob/main/main/EDParamsMod.F90) - Global parameter definitions
- [parameter_files/fates_params_default.cdl](https://github.com/NGEET/fates/blob/main/parameter_files/fates_params_default.cdl) - Default parameter values

</details>

**Author:** Ryan Knox (adapted for A2MC)
**Last Updated:** February 2026

This guide provides practical guidance for calibrating FATES with Carbon-Nitrogen-Phosphorus (CNP) dynamics. It covers core concepts, common pitfalls, diagnostic strategies, and step-by-step site setup procedures.

---

## Core Concepts

### Nutrient Cycling Modes

ELM and CLM **always** cycle nutrients internally when FATES is on. The key difference:

| Mode | Nutrient Transfer | Litter Nutrients | Supplementation |
|------|-------------------|------------------|-----------------|
| **FATES-CNP** (`parteh_mode=2`) | Mineralized pools → FATES plant storage | C, N, P in fragmented litter → ELM/CLM | `suplnitro`/`suplphos` = NONE (eventually) |
| **FATES Carbon-Only** (`parteh_mode=1`) | NO nutrients to plants | NO nutrients in litter flux | `suplnitro`/`suplphos` = ALL |

Sources: [parteh/PRTAllometricCNPMod.F90](https://github.com/NGEET/fates/blob/main/parteh/PRTAllometricCNPMod.F90) (CNP hypothesis), [parteh/PRTAllometricCarbonMod.F90](https://github.com/NGEET/fates/blob/main/parteh/PRTAllometricCarbonMod.F90) (Carbon-only hypothesis)

### Multi-Phase Simulation Process

CNP simulations require a multi-phase spinup approach:

```
Phase 1: AD Spinup (100-1000 years, ~500+ typical for forests)
├── Initial period: N AND P supplementation (multi-year)
├── Remainder: N-limited, P-supplemented
└── Target: Multi-year smoothed FATES_NEP ≈ 0

Phase 2: Post-AD (100-500 years)
├── N-limited, P-supplemented
└── Target: NEP equilibrium

Phase 3: Target/Transient
├── N-limited, P-limited (if desired)
└── P initialized from data
```

---

## Critical "Gotchas"

### 1. AD Simulation Start Year

**AD simulations MUST start at year 0001!** Carbon AD mode doesn't work otherwise.

```bash
./xmlchange --append ELM_BLDNML_OPTS="-bgc_spinup on"
./xmlchange RUN_STARTDATE='0001-01-01'
```

### 2. Prescribed Uptake Boundary Conditions

Ensure FATES is NOT using prescribed uptake:
```
fates_cnp_prescribed_nuptake = 0
fates_cnp_prescribed_puptake = 0
```

These are **PFT-specific fractions [0-1]** that determine what fraction of nutrient demand plants receive:
- **= 1**: Plants get 100% of their demand → **no real nutrient limitation**
- **= 0**: Plants must compete for nutrients via coupled uptake (ECA or RD mode)

For true CNP dynamics with nutrient limitation, both must be 0.

Sources: [biogeochem/FatesSoilBGCFluxMod.F90 155-170](https://github.com/NGEET/fates/blob/main/biogeochem/FatesSoilBGCFluxMod.F90#L155-L170) (prescribed N uptake), [biogeochem/FatesSoilBGCFluxMod.F90 194-206](https://github.com/NGEET/fates/blob/main/biogeochem/FatesSoilBGCFluxMod.F90#L194-L206) (prescribed P uptake), [parteh/PRTAllometricCNPMod.F90 470-475](https://github.com/NGEET/fates/blob/main/parteh/PRTAllometricCNPMod.F90#L470-L475) (sets large gain values to remove limitation)

### 3. ECA vs RD Mode: vmax Differences

The source limitation functions differ significantly between competition modes:

| Mode | vmax Typical Range | Notes |
|------|-------------------|-------|
| **ECA** | ~10⁻⁷ | Stronger source limitation, larger vmax needed |
| **RD** | ~10⁻⁹ | Weaker limitation, smaller vmax needed |

**Parameters affected:**
- `fates_cnp_vmax_nh4`
- `fates_cnp_vmax_no3`
- `fates_cnp_vmax_p`

### 4. RD Mode: NH4 and NO3 vmax Are Additive

With **RD** scheme, vmax_nh4 and vmax_no3 are added together to get total N demand. Individual values don't matter, only their sum.

With **ECA**, each vmax works independently on NH4 and NO3 uptake.

Sources: [biogeochem/FatesSoilBGCFluxMod.F90 162-166](https://github.com/NGEET/fates/blob/main/biogeochem/FatesSoilBGCFluxMod.F90#L162-L166) (N demand calculation), [main/FatesInterfaceTypesMod.F90 54-61](https://github.com/NGEET/fates/blob/main/main/FatesInterfaceTypesMod.F90#L54-L61) (ECA/RD mode constants)

### 5. ECA Mode: KM Value Guidance

Good starting points for plant KM values:
- Use same values as decomposer KM
- Or make plant KM **larger** than decomposer KM (prioritizes decomposer uptake → more mineralization → more available nutrients)

**Parameters:**
- `fates_cnp_km_nh4`
- `fates_cnp_km_no3`
- `fates_cnp_km_p`

### 6. Storage Parameters for Stability

Increasing plant storage of C, N, and P promotes stability, survivability, and adaptability:

| Parameter | Effect |
|-----------|--------|
| `fates_cnp_nitr_store_ratio` | Target N storage relative to structural N |
| `fates_cnp_phos_store_ratio` | Target P storage relative to structural P |
| `fates_cnp_store_ovrflw_frac` | Fraction of excess nutrients to overflow |
| `fates_alloc_storage_cushion` | Storage buffer multiplier |

Sources: [parteh/PRTAllometricCNPMod.F90 186-192](https://github.com/NGEET/fates/blob/main/parteh/PRTAllometricCNPMod.F90#L186-L192) (storage parameters), [parteh/PRTAllometricCNPMod.F90 216-219](https://github.com/NGEET/fates/blob/main/parteh/PRTAllometricCNPMod.F90#L216-L219) (overflow handling)

### 7. Decomposition E-Folding Depth

Increasing the e-folding depth strengthens the decomposition cycle and generates more nutrient availability:

**ELM/CLM parameter:** `decomp_depth_efolding`

**Trade-offs:**
- Higher value → More nutrient availability
- Higher value → Reduced soil carbon
- Higher value → Shifted ¹⁴C depth profile

---

## Monitoring FATES_L2FR

`FATES_L2FR` (Leaf-to-Fine-Root ratio) is a **critical diagnostic** during spinup and calibration.

### What to Watch For

| Behavior | Interpretation | Action |
|----------|----------------|--------|
| Rapid, monotonic changes | PID over-reacting or N/P availability issues | Reduce `fates_cnp_pid_kp` by 10× |
| Values < 0.1 or > 10 | Poor calibration or strange dynamics | Investigate nutrient supply |
| Reaches equilibrium | Good calibration | Proceed |
| Differentiated canopy/understory | Normal behavior | Expected |

### PID Controller Parameters

The PID controller adjusts L2FR based on nutrient stress:

| Parameter | Role | Recommendation |
|-----------|------|----------------|
| `fates_cnp_pid_kp` | Proportional gain | **Reduce by 10× if L2FR unstable** |
| `fates_cnp_pid_ki` | Integral gain | Adjust if persistent offset |
| `fates_cnp_pid_kd` | Derivative gain | Adjust if oscillations |

Sources: [parteh/PRTAllometricCNPMod.F90 1850-2100](https://github.com/NGEET/fates/blob/main/parteh/PRTAllometricCNPMod.F90#L1850-L2100) (PID controller implementation, `CNPAdjustFRootTargets`)

---

## Strategies for Insufficient Nutrient Availability

If the system struggles to generate enough available nutrients:

### A. Increase Free-Living N Fixation
Manually increase in ELM code using hard-coded constant: `test_mult`

### B. Increase Decomposition E-Folding Depth
ELM/CLM parameter: `decomp_depth_efolding`

### C. Make a PFT a N-Fixer
Set `fates_cnp_nfix > 0` for one PFT (e.g., start with 0.1 = 10%)

### D. Decrease Leaching
Target NO3 leaching (check history variable)

### E. Increase Retranslocation
- `fates_cnp_turnover_nitr_retrans` - N reabsorption from senescing tissues
- `fates_cnp_turnover_phos_retrans` - P reabsorption from senescing tissues

### F. Monitor Litter/SOM Quality
Track C:N and C:P ratios to ensure they're not spiraling:

| Diagnostic Ratio | Variables |
|------------------|-----------|
| Litter C:N | `TOTLITC / TOTLITN` |
| Litter C:P | `TOTLITC / TOTLITP` |
| SOM C:N | `TOTSOMC / TOTSOMN` |
| SOM C:P | `TOTSOMC / TOTSOMP` |

If ratios increase significantly → need more heterotrophic respiration.

---

## Site Setup: Step-by-Step

### Step 1: Carbon-Only Baseline (100 years)

Run a carbon-only simulation (`parteh_mode=1`) for 100 years.

**Goal:** Establish reasonable vegetation demographics before enabling nutrients.

**If successful → proceed to Step 2**

### Step 2: Initial CNP with Full Supplementation (50 years)

Switch to `parteh_mode=2` (CNP). Run AD spinup with:
- Phosphorus AND nitrogen supplementation the whole time
- **Start at year 0001!**

Initial vmax guess: Start LOW BUT REASONABLE (defaults are usually fine, but adjust for ECA vs RD).

**Evaluate:**
- `TLAI` - Leaf area
- `FATES_VEGC_ABOVEGROUND` - Biomass
- `FATES_NPP` - Productivity
- `FATES_NEFFLUX` - N "dumped" due to saturated stores (see [parteh/PRTAllometricCNPMod.F90 2600-2700](https://github.com/NGEET/fates/blob/main/parteh/PRTAllometricCNPMod.F90#L2600-L2700))

**Decision tree:**
```
Low biomass + Low NPP + No NEFFLUX → Increase vmax
High biomass + High NPP + High NEFFLUX → Decrease vmax
```

**Binary search** on vmax until:
- Vegetation similar to C-only simulation
- Very small FATES_NEFFLUX

### Step 3: Introduce N Limitation (50-100 years)

Run with N limitation after initial period:
```
suplnitro = NONE
nyears_ad_carbon_only = 25  # or 10, 20 depending on shock severity
```

**Expected behavior at year 25:**
- Plants start adjusting roots (watch `FATES_L2FR`)
- Shock in biomass
- NPP decline

**Iterate:** Slowly increase vmax until canopy reaches equilibrium after shock.

**Success indicators:**
- `FATES_NPP` stabilizes
- `FATES_NEFFLUX / FATES_NUPTAKE` is small after shock

**If shock too strong:** Decrease `nyears_ad_carbon_only` (try 10, 20).

### Step 4: Extended Spinup (500+ years)

Extend run length to ~500 years with stationary (pre-industrial) climate.

**Target:** `FATES_NEP` ≈ 0 when averaged over decade timescales.

If model behaves → you have a reasonable vmax calibration.

---

## Key Output Variables

### Unit Conversion
- All FATES variables: `kg m⁻² s⁻¹`
- To get `kg m⁻² yr⁻¹`: multiply by **31,536,000**
- ELM (non-FATES) variables: `g m⁻² s⁻¹`

### Recommended History Variables

```
# Carbon/Productivity
FATES_NPP, FATES_NEP, NEP, FATES_HET_RESP, FATES_VEGC_ABOVEGROUND

# Structure
TLAI, FATES_L2FR

# Nutrient Dynamics
FATES_NDEMAND, FATES_PDEMAND
FATES_NH4UPTAKE, FATES_NO3UPTAKE, FATES_PUPTAKE
FATES_NEFFLUX, FATES_PEFFLUX
FATES_NFIX_SYM, NFIX_TO_SMINN

# Soil Pools
TOTSOMC, TOTSOMN, TOTSOMP
TOTLITC, TOTLITN, TOTLITP

# Leaching
SMINP_LEACHED, SMIN_NO3_LEACHED, SOM_C_LEACHED
```

---

## Quick Reference: Parameter Checklist

### Must Check Before CNP Run

| Parameter | Check | Notes |
|-----------|-------|-------|
| `parteh_mode` | = 2 for CNP | |
| `fates_cnp_prescribed_nuptake` | = 0 | If = 1, no N limitation (100% of demand met) |
| `fates_cnp_prescribed_puptake` | = 0 | If = 1, no P limitation (100% of demand met) |
| `RUN_STARTDATE` | = '0001-01-01' | Required for AD spinup |

### Key Tuning Parameters

| Parameter | Typical Range | Notes |
|-----------|---------------|-------|
| `fates_cnp_vmax_nh4` | 10⁻⁹ (RD) to 10⁻⁷ (ECA) | Binary search to calibrate |
| `fates_cnp_vmax_no3` | 10⁻⁹ (RD) to 10⁻⁷ (ECA) | Binary search to calibrate |
| `fates_cnp_vmax_p` | 10⁻⁹ (RD) to 10⁻⁷ (ECA) | Binary search to calibrate |
| `fates_cnp_pid_kp` | Default / 10 | Reduce if L2FR unstable |
| `fates_alloc_storage_cushion` | 1.0 - 5.0 | Higher = more stability |
| `decomp_depth_efolding` | Site-specific | Higher = more nutrients |

---

## See Also

- [CNP Allocation and Nutrient Dynamics](cnp_allocation.md) - Three-phase allocation, PID controller
- [Nutrient Competition Modes](nutrient_competition.md) - ECA vs RD, prescribed vs coupled
- [Soil-Plant Nutrient Interface](../plant-physiology/parteh/soil_plant_interface.md) - Uptake mechanics

---

## References

- FATES CNP Guidebook by Ryan Knox (Feb 2, 2026)
- FATES Technical Documentation
