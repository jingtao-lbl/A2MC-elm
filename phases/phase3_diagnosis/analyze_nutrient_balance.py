#!/usr/bin/env python3
"""
Nutrient Mass Balance Analysis for A2MC Phase 3 Diagnosis

Performs full N/P budget accounting to detect:
- Budget closure failures (mass imbalance)
- Dominant nutrient loss pathways (leaching, occlusion, efflux)
- PFT-level competitive advantages in nutrient uptake
- Supply/demand ratios per PFT

Unlike analyze_nutrient_pools.py (pool depletion + uptake/demand ratios),
this tool calculates COMPLETE budget closure:
    dPool/dt = Inputs - Outputs
and reports residuals.

Usage (Python API):
    from phases.phase3_diagnosis import (
        extract_nutrient_budget,
        calculate_budget_closure,
        analyze_pft_competition,
        identify_nutrient_sinks,
        get_balance_summary_for_ai
    )

    budget = extract_nutrient_budget('output.nc', nutrient='P', pft_ids=[7, 9, 10])
    closure = calculate_budget_closure(budget)
    competition = analyze_pft_competition('output.nc', pft_ids=[7, 9, 10], nutrient='P')
    sinks = identify_nutrient_sinks(budget)
    summary = get_balance_summary_for_ai(budget, closure, competition, sinks)

Usage (CLI):
    python -m phases.phase3_diagnosis.analyze_nutrient_balance \\
        --nc-file /path/to/output.nc \\
        --nutrient P \\
        --pft-ids 7 9 10 \\
        --output balance_results.json

Author: Jing Tao with Claude
Created: February 2026
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from tools.fates_utils import get_szpf_range, aggregate_szpf_by_pft

logger = logging.getLogger(__name__)

# =============================================================================
# VARIABLE DEFINITIONS
# =============================================================================

# P budget variables: (variable_name, category, source, units_are_fates)
# source: 'ELM' means g/m2/s, 'FATES' means kg/m2/s
P_FLUX_INPUTS = [
    ('PRIMP_TO_LABILEP',     'Weathering',             'ELM'),
    ('PDEP_TO_SMINP',        'Deposition',             'ELM'),
    ('SECONDP_TO_LABILEP',   'Desorption',             'ELM'),
    ('BIOCHEM_PMIN',         'Biochem mineralization',  'ELM'),
    ('GROSS_PMIN',           'Gross mineralization',    'ELM'),
]

P_FLUX_OUTPUTS = [
    ('FATES_PUPTAKE',        'Plant uptake',           'FATES'),
    ('SMINP_LEACHED',        'Leaching',               'ELM'),
    ('FATES_PEFFLUX',        'Plant efflux',           'FATES'),
    ('LABILEP_TO_SECONDP',   'Sorption',               'ELM'),
    ('SECONDP_TO_OCCLP',     'Occlusion',              'ELM'),
]

P_POOLS = [
    ('SMINP',      'Soil mineral P',  'ELM'),
    ('LABILEP',    'Labile P',        'ELM'),
    ('SECONDP',    'Secondary P',     'ELM'),
    ('PRIMP',      'Primary P',       'ELM'),
    ('FATES_STOREP', 'Plant storage P', 'FATES'),
    ('FATES_VEGP',   'Vegetation P',    'FATES'),
]

P_SZPF_VARS = [
    ('FATES_PUPTAKE_SZPF',  'Plant uptake',   'FATES'),
    ('FATES_PEFFLUX_SZPF',  'Plant efflux',   'FATES'),
    ('FATES_PDEMAND_SZPF',  'Plant demand',   'FATES'),
]

# N budget variables
N_FLUX_INPUTS = [
    ('NDEP_TO_SMINN',       'Deposition',              'ELM'),
    ('NFIX_TO_SMINN',       'Free-living fixation',    'ELM'),
    ('FATES_NFIX_SYM',      'Symbiotic fixation',      'FATES'),
    ('GROSS_NMIN',           'Gross mineralization',    'ELM'),
]

N_FLUX_OUTPUTS = [
    ('FATES_NH4UPTAKE',     'NH4 uptake',              'FATES'),
    ('FATES_NO3UPTAKE',     'NO3 uptake',              'FATES'),
    ('SMIN_NO3_LEACHED',    'NO3 leaching',            'ELM'),
    ('SMIN_NO3_RUNOFF',     'NO3 runoff',              'ELM'),
    ('FATES_NEFFLUX',       'Plant N efflux',          'FATES'),
]

N_POOLS = [
    ('SMINN',        'Total mineral N',  'ELM'),
    ('SMIN_NH4',     'Ammonium',         'ELM'),
    ('SMIN_NO3',     'Nitrate',          'ELM'),
    ('FATES_STOREN', 'Plant storage N',  'FATES'),
    ('FATES_VEGN',   'Vegetation N',     'FATES'),
]

N_SZPF_VARS = [
    ('FATES_NH4UPTAKE_SZPF',  'NH4 uptake',   'FATES'),
    ('FATES_NO3UPTAKE_SZPF',  'NO3 uptake',   'FATES'),
    ('FATES_NEFFLUX_SZPF',    'N efflux',     'FATES'),
    ('FATES_NDEMAND_SZPF',    'N demand',     'FATES'),
]

# Unit conversions
G_PER_KG = 1000.0
SECONDS_PER_DAY = 86400.0
DAYS_PER_MONTH = 30.4375  # Average days per month (365.25/12)
SECONDS_PER_MONTH = SECONDS_PER_DAY * DAYS_PER_MONTH


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FluxTimeSeries:
    """A single flux variable with metadata."""
    variable: str
    label: str
    source: str           # 'ELM' or 'FATES'
    monthly: np.ndarray   # g/m2/month
    annual_mean: float    # g/m2/month (mean monthly rate)
    annual_total: float   # g/m2/yr


@dataclass
class PoolTimeSeries:
    """A single pool variable with metadata."""
    variable: str
    label: str
    source: str
    monthly: np.ndarray   # g/m2
    initial: float        # g/m2 (first year mean)
    final: float          # g/m2 (last year mean)
    change: float         # g/m2 (final - initial)


@dataclass
class NutrientBudget:
    """Complete nutrient budget for one nutrient type."""
    nutrient: str           # 'P' or 'N'
    n_months: int
    inputs: Dict[str, FluxTimeSeries]
    outputs: Dict[str, FluxTimeSeries]
    pools: Dict[str, PoolTimeSeries]
    total_input_annual: float    # g/m2/yr
    total_output_annual: float   # g/m2/yr
    missing_variables: List[str]


@dataclass
class BudgetClosure:
    """Budget closure analysis results."""
    nutrient: str
    soil_pool_var: str           # Primary soil pool used for closure
    calculated_dpool_dt: float   # g/m2/yr (inputs - outputs)
    actual_dpool_dt: float       # g/m2/yr (from pool time series)
    residual: float              # g/m2/yr (calculated - actual)
    relative_residual: float     # fraction of total input
    closure_acceptable: bool     # |relative_residual| < 0.1


@dataclass
class PFTCompetition:
    """PFT-level nutrient competition analysis."""
    nutrient: str
    pft_ids: List[int]
    uptake_by_pft: Dict[int, float]       # g/m2/yr per PFT
    demand_by_pft: Dict[int, float]       # g/m2/yr per PFT
    supply_demand_ratio: Dict[int, float] # uptake/demand per PFT
    uptake_share: Dict[int, float]        # fraction of total uptake
    total_uptake: float                   # g/m2/yr
    total_demand: float                   # g/m2/yr
    dominant_pft: Optional[int]           # PFT with highest uptake share
    most_limited_pft: Optional[int]       # PFT with lowest supply/demand


@dataclass
class NutrientSinks:
    """Ranking of nutrient output pathways."""
    nutrient: str
    ranked_sinks: List[Dict[str, Any]]  # [{name, flux, fraction}]
    leaching_exceeds_uptake: bool
    dominant_sink: str
    findings: List[str]


# =============================================================================
# EXTRACTION
# =============================================================================

def _read_site_variable(ds, var_name: str) -> Optional[np.ndarray]:
    """Read a site-level (1D time series) variable from NetCDF, handling dimensions."""
    if var_name not in ds.variables:
        return None

    arr = ds.variables[var_name][:]

    # Handle masked arrays
    if hasattr(arr, 'filled'):
        arr = arr.filled(0.0)

    # Collapse to 1D time series
    if arr.ndim == 1:
        return arr
    elif arr.ndim == 2:
        # (time, spatial) or (time, level) - take first spatial or sum levels
        dims = ds.variables[var_name].dimensions
        if len(dims) == 2 and dims[1] in ('levdcmp', 'levsoi', 'levgrnd'):
            return np.sum(arr, axis=1)
        return arr[:, 0]
    elif arr.ndim == 3:
        # (time, level, spatial)
        return np.sum(arr[:, :, 0], axis=1)

    return arr


def _convert_flux_to_g_per_month(data: np.ndarray, source: str) -> np.ndarray:
    """Convert flux from native units to g/m2/month.

    ELM variables: g/m2/s -> g/m2/month
    FATES variables: kg/m2/s -> g/m2/month
    """
    scale = SECONDS_PER_MONTH
    if source == 'FATES':
        scale *= G_PER_KG
    return data * scale


def _convert_pool_to_g(data: np.ndarray, source: str) -> np.ndarray:
    """Convert pool from native units to g/m2.

    ELM variables: already g/m2
    FATES variables: kg/m2 -> g/m2
    """
    if source == 'FATES':
        return data * G_PER_KG
    return data.copy()


def extract_nutrient_budget(
    nc_file: str,
    nutrient: str = 'P',
    pft_ids: Optional[List[int]] = None
) -> NutrientBudget:
    """
    Extract complete nutrient budget from a NetCDF file.

    Reads all input/output flux variables and pool variables for the specified
    nutrient (P or N). Handles missing variables gracefully (warns and sets to zero).
    Converts all units to g/m2/month for fluxes and g/m2 for pools.

    Parameters
    ----------
    nc_file : str
        Path to NetCDF output file
    nutrient : str
        'P' for phosphorus, 'N' for nitrogen
    pft_ids : list of int, optional
        PFT IDs for SZPF extraction (not used directly here, reserved)

    Returns
    -------
    NutrientBudget
        Complete budget with all fluxes and pools
    """
    try:
        import netCDF4 as nc
    except ImportError:
        raise ImportError("netCDF4 required for NetCDF reading")

    nutrient = nutrient.upper()
    if nutrient == 'P':
        flux_inputs_def = P_FLUX_INPUTS
        flux_outputs_def = P_FLUX_OUTPUTS
        pools_def = P_POOLS
    elif nutrient == 'N':
        flux_inputs_def = N_FLUX_INPUTS
        flux_outputs_def = N_FLUX_OUTPUTS
        pools_def = N_POOLS
    else:
        raise ValueError(f"nutrient must be 'P' or 'N', got '{nutrient}'")

    inputs = {}
    outputs = {}
    pools = {}
    missing = []

    with nc.Dataset(nc_file, 'r') as ds:
        n_time = ds.dimensions['time'].size

        # --- Extract input fluxes ---
        for var_name, label, source in flux_inputs_def:
            raw = _read_site_variable(ds, var_name)
            if raw is None:
                logger.warning(f"Variable {var_name} not found, setting to zero")
                missing.append(var_name)
                raw = np.zeros(n_time)
            monthly = _convert_flux_to_g_per_month(raw, source)
            annual_total = float(np.mean(monthly)) * 12.0  # g/m2/yr
            inputs[var_name] = FluxTimeSeries(
                variable=var_name, label=label, source=source,
                monthly=monthly,
                annual_mean=float(np.mean(monthly)),
                annual_total=annual_total,
            )

        # --- Extract output fluxes ---
        for var_name, label, source in flux_outputs_def:
            raw = _read_site_variable(ds, var_name)
            if raw is None:
                logger.warning(f"Variable {var_name} not found, setting to zero")
                missing.append(var_name)
                raw = np.zeros(n_time)
            monthly = _convert_flux_to_g_per_month(raw, source)
            annual_total = float(np.mean(monthly)) * 12.0
            outputs[var_name] = FluxTimeSeries(
                variable=var_name, label=label, source=source,
                monthly=monthly,
                annual_mean=float(np.mean(monthly)),
                annual_total=annual_total,
            )

        # --- Extract pools ---
        for var_name, label, source in pools_def:
            raw = _read_site_variable(ds, var_name)
            if raw is None:
                logger.warning(f"Pool {var_name} not found, setting to zero")
                missing.append(var_name)
                raw = np.zeros(n_time)
            monthly = _convert_pool_to_g(raw, source)
            n_avg = min(12, len(monthly))
            initial = float(np.mean(monthly[:n_avg]))
            final = float(np.mean(monthly[-n_avg:]))
            pools[var_name] = PoolTimeSeries(
                variable=var_name, label=label, source=source,
                monthly=monthly,
                initial=initial, final=final,
                change=final - initial,
            )

    total_input = sum(f.annual_total for f in inputs.values())
    total_output = sum(f.annual_total for f in outputs.values())

    return NutrientBudget(
        nutrient=nutrient,
        n_months=n_time,
        inputs=inputs,
        outputs=outputs,
        pools=pools,
        total_input_annual=total_input,
        total_output_annual=total_output,
        missing_variables=missing,
    )


# =============================================================================
# BUDGET CLOSURE
# =============================================================================

def calculate_budget_closure(budget: NutrientBudget) -> BudgetClosure:
    """
    Check budget closure: dPool/dt = Inputs - Outputs.

    Uses the primary soil mineral pool (SMINP for P, SMINN for N) for closure.
    Reports residual as absolute and relative to total input.

    Parameters
    ----------
    budget : NutrientBudget
        Output from extract_nutrient_budget()

    Returns
    -------
    BudgetClosure
        Closure check results
    """
    # Select primary soil pool
    if budget.nutrient == 'P':
        soil_pool_var = 'SMINP'
    else:
        soil_pool_var = 'SMINN'

    pool = budget.pools.get(soil_pool_var)

    # Calculated dPool/dt from budget
    calculated = budget.total_input_annual - budget.total_output_annual

    # Actual dPool/dt from pool time series
    if pool is not None and budget.n_months > 12:
        n_years = budget.n_months / 12.0
        actual = pool.change / n_years
    elif pool is not None:
        actual = pool.change
    else:
        actual = 0.0

    residual = calculated - actual

    if budget.total_input_annual > 0:
        relative = residual / budget.total_input_annual
    else:
        relative = 0.0 if abs(residual) < 1e-10 else float('inf')

    return BudgetClosure(
        nutrient=budget.nutrient,
        soil_pool_var=soil_pool_var,
        calculated_dpool_dt=calculated,
        actual_dpool_dt=actual,
        residual=residual,
        relative_residual=relative,
        closure_acceptable=abs(relative) < 0.1,
    )


# =============================================================================
# PFT COMPETITION
# =============================================================================

def analyze_pft_competition(
    nc_file: str,
    pft_ids: List[int],
    nutrient: str = 'P',
    fates_pft: int = 12
) -> PFTCompetition:
    """
    Analyze PFT-level nutrient competition using SZPF variables.

    Extracts uptake and demand per PFT, calculates supply/demand ratios
    and uptake shares to identify competitive advantages/disadvantages.

    Parameters
    ----------
    nc_file : str
        Path to NetCDF output file
    pft_ids : list of int
        PFT IDs to analyze (1-indexed)
    nutrient : str
        'P' or 'N'
    fates_pft : int
        Total number of PFTs in configuration (default: 12)

    Returns
    -------
    PFTCompetition
        Competition analysis results
    """
    try:
        import netCDF4 as nc
    except ImportError:
        raise ImportError("netCDF4 required")

    nutrient = nutrient.upper()

    # Select SZPF variable names
    if nutrient == 'P':
        uptake_vars = ['FATES_PUPTAKE_SZPF']
        demand_var = 'FATES_PDEMAND_SZPF'
    else:
        uptake_vars = ['FATES_NH4UPTAKE_SZPF', 'FATES_NO3UPTAKE_SZPF']
        demand_var = 'FATES_NDEMAND_SZPF'

    uptake_by_pft = {}
    demand_by_pft = {}

    with nc.Dataset(nc_file, 'r') as ds:
        for pft_id in pft_ids:
            start, end = get_szpf_range(pft_id, fates_pft)

            # Uptake: sum across uptake vars and size classes
            pft_uptake = 0.0
            for uvar in uptake_vars:
                if uvar in ds.variables:
                    raw = ds.variables[uvar][:]
                    if hasattr(raw, 'filled'):
                        raw = raw.filled(0.0)
                    # SZPF dim could be axis 1 or axis 0 depending on file
                    if raw.ndim == 2:
                        pft_data = np.sum(raw[:, start:end+1], axis=1)
                    elif raw.ndim == 3:
                        pft_data = np.sum(raw[:, start:end+1, 0], axis=1)
                    else:
                        pft_data = np.zeros(1)
                    # FATES: kg/m2/s -> g/m2/yr
                    annual = float(np.mean(pft_data)) * G_PER_KG * SECONDS_PER_DAY * 365.25
                    pft_uptake += annual

            uptake_by_pft[pft_id] = pft_uptake

            # Demand
            pft_demand = 0.0
            if demand_var in ds.variables:
                raw = ds.variables[demand_var][:]
                if hasattr(raw, 'filled'):
                    raw = raw.filled(0.0)
                if raw.ndim == 2:
                    pft_data = np.sum(raw[:, start:end+1], axis=1)
                elif raw.ndim == 3:
                    pft_data = np.sum(raw[:, start:end+1, 0], axis=1)
                else:
                    pft_data = np.zeros(1)
                pft_demand = float(np.mean(pft_data)) * G_PER_KG * SECONDS_PER_DAY * 365.25

            demand_by_pft[pft_id] = pft_demand

    total_uptake = sum(uptake_by_pft.values())
    total_demand = sum(demand_by_pft.values())

    # Uptake share (fraction of total)
    uptake_share = {}
    for pft_id in pft_ids:
        if total_uptake > 0:
            uptake_share[pft_id] = uptake_by_pft[pft_id] / total_uptake
        else:
            uptake_share[pft_id] = 0.0

    # Supply/demand ratio
    supply_demand = {}
    for pft_id in pft_ids:
        if demand_by_pft[pft_id] > 0:
            supply_demand[pft_id] = uptake_by_pft[pft_id] / demand_by_pft[pft_id]
        else:
            supply_demand[pft_id] = float('inf') if uptake_by_pft[pft_id] > 0 else 0.0

    # Identify dominant and most limited
    dominant = max(uptake_share, key=uptake_share.get) if uptake_share else None
    finite_ratios = {k: v for k, v in supply_demand.items() if v != float('inf')}
    most_limited = min(finite_ratios, key=finite_ratios.get) if finite_ratios else None

    return PFTCompetition(
        nutrient=nutrient,
        pft_ids=pft_ids,
        uptake_by_pft=uptake_by_pft,
        demand_by_pft=demand_by_pft,
        supply_demand_ratio=supply_demand,
        uptake_share=uptake_share,
        total_uptake=total_uptake,
        total_demand=total_demand,
        dominant_pft=dominant,
        most_limited_pft=most_limited,
    )


# =============================================================================
# SINK ANALYSIS
# =============================================================================

def identify_nutrient_sinks(budget: NutrientBudget) -> NutrientSinks:
    """
    Rank nutrient output pathways by magnitude.

    Identifies where nutrients go (plant uptake, leaching, sorption, etc.)
    and flags if leaching exceeds uptake.

    Parameters
    ----------
    budget : NutrientBudget
        Output from extract_nutrient_budget()

    Returns
    -------
    NutrientSinks
        Ranked sinks with findings
    """
    total_output = budget.total_output_annual
    sinks = []
    findings = []

    for var_name, flux_ts in budget.outputs.items():
        fraction = flux_ts.annual_total / total_output if total_output > 0 else 0.0
        sinks.append({
            'name': flux_ts.label,
            'variable': var_name,
            'flux_g_m2_yr': flux_ts.annual_total,
            'fraction': fraction,
        })

    # Sort by magnitude (descending)
    sinks.sort(key=lambda x: x['flux_g_m2_yr'], reverse=True)

    dominant_sink = sinks[0]['name'] if sinks else 'none'

    # Check leaching vs uptake
    leaching_total = 0.0
    uptake_total = 0.0
    for s in sinks:
        name_lower = s['name'].lower()
        if 'leach' in name_lower or 'runoff' in name_lower:
            leaching_total += s['flux_g_m2_yr']
        if 'uptake' in name_lower:
            uptake_total += s['flux_g_m2_yr']

    leaching_exceeds = leaching_total > uptake_total

    if leaching_exceeds:
        findings.append(
            f"CRITICAL: {budget.nutrient} leaching ({leaching_total:.4f} g/m2/yr) "
            f"exceeds plant uptake ({uptake_total:.4f} g/m2/yr) - nutrient loss problem"
        )

    # Flag if sorption/occlusion dominates
    for s in sinks:
        if s['fraction'] > 0.5:
            findings.append(
                f"{s['name']} accounts for {s['fraction']:.0%} of {budget.nutrient} outputs"
            )

    # Flag negligible uptake
    total_input = budget.total_input_annual
    if total_input > 0 and uptake_total / total_input < 0.1:
        findings.append(
            f"Plant uptake is only {uptake_total/total_input:.1%} of total {budget.nutrient} input"
        )

    return NutrientSinks(
        nutrient=budget.nutrient,
        ranked_sinks=sinks,
        leaching_exceeds_uptake=leaching_exceeds,
        dominant_sink=dominant_sink,
        findings=findings,
    )


# =============================================================================
# AI SUMMARY
# =============================================================================

def get_balance_summary_for_ai(
    budget: NutrientBudget,
    closure: BudgetClosure,
    competition: Optional[PFTCompetition] = None,
    sinks: Optional[NutrientSinks] = None
) -> str:
    """
    Generate a summary string suitable for AI reasoning context.

    Parameters
    ----------
    budget : NutrientBudget
        Complete budget from extract_nutrient_budget()
    closure : BudgetClosure
        Closure check from calculate_budget_closure()
    competition : PFTCompetition, optional
        PFT competition from analyze_pft_competition()
    sinks : NutrientSinks, optional
        Sink ranking from identify_nutrient_sinks()

    Returns
    -------
    str
        Formatted summary for inclusion in AI prompts
    """
    lines = [
        f"## {budget.nutrient} Mass Balance Analysis",
        f"",
        f"**Time span:** {budget.n_months} months ({budget.n_months/12:.1f} years)",
    ]
    if budget.missing_variables:
        lines.append(f"**Missing variables:** {', '.join(budget.missing_variables)}")
    lines.append("")

    # --- Input fluxes ---
    lines.append("### Input Fluxes (g/m2/yr)")
    for var, fts in budget.inputs.items():
        lines.append(f"- {fts.label} ({var}): {fts.annual_total:.4f}")
    lines.append(f"- **Total Input: {budget.total_input_annual:.4f}**")
    lines.append("")

    # --- Output fluxes ---
    lines.append("### Output Fluxes (g/m2/yr)")
    for var, fts in budget.outputs.items():
        lines.append(f"- {fts.label} ({var}): {fts.annual_total:.4f}")
    lines.append(f"- **Total Output: {budget.total_output_annual:.4f}**")
    lines.append("")

    # --- Pool changes ---
    lines.append("### Pool Changes (g/m2)")
    for var, pts in budget.pools.items():
        direction = "+" if pts.change > 0 else ""
        lines.append(f"- {pts.label} ({var}): {pts.initial:.4f} -> {pts.final:.4f} ({direction}{pts.change:.4f})")
    lines.append("")

    # --- Budget closure ---
    lines.append("### Budget Closure Check")
    lines.append(f"- Calculated dPool/dt (inputs - outputs): {closure.calculated_dpool_dt:.4f} g/m2/yr")
    lines.append(f"- Actual dPool/dt ({closure.soil_pool_var}): {closure.actual_dpool_dt:.4f} g/m2/yr")
    lines.append(f"- Residual: {closure.residual:.4f} g/m2/yr")
    lines.append(f"- Relative residual: {closure.relative_residual:.2%} of total input")
    lines.append(f"- **Closure: {'ACCEPTABLE' if closure.closure_acceptable else 'FAILED (>10% residual)'}**")
    lines.append("")

    # --- PFT competition ---
    if competition is not None:
        lines.append("### PFT Nutrient Competition")
        lines.append(f"Total {competition.nutrient} uptake: {competition.total_uptake:.4f} g/m2/yr")
        lines.append(f"Total {competition.nutrient} demand: {competition.total_demand:.4f} g/m2/yr")
        lines.append("")
        lines.append("| PFT | Uptake (g/m2/yr) | Demand (g/m2/yr) | Supply/Demand | Uptake Share |")
        lines.append("|-----|-----------------|-----------------|---------------|-------------|")
        for pft_id in competition.pft_ids:
            up = competition.uptake_by_pft[pft_id]
            dem = competition.demand_by_pft[pft_id]
            sd = competition.supply_demand_ratio[pft_id]
            share = competition.uptake_share[pft_id]
            sd_str = f"{sd:.3f}" if sd != float('inf') else "inf"
            lines.append(f"| PFT{pft_id} | {up:.4f} | {dem:.4f} | {sd_str} | {share:.1%} |")
        lines.append("")
        if competition.dominant_pft:
            lines.append(f"- Dominant uptake: PFT{competition.dominant_pft}")
        if competition.most_limited_pft:
            lines.append(f"- Most {competition.nutrient}-limited: PFT{competition.most_limited_pft}")
        lines.append("")

    # --- Nutrient sinks ---
    if sinks is not None:
        lines.append("### Nutrient Output Pathways (ranked)")
        for i, s in enumerate(sinks.ranked_sinks, 1):
            lines.append(f"{i}. {s['name']}: {s['flux_g_m2_yr']:.4f} g/m2/yr ({s['fraction']:.1%})")
        lines.append("")
        if sinks.leaching_exceeds_uptake:
            lines.append("**WARNING:** Leaching exceeds plant uptake!")
        if sinks.findings:
            lines.append("")
            lines.append("### Key Findings")
            for f in sinks.findings:
                lines.append(f"- {f}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# SERIALIZATION
# =============================================================================

def results_to_dict(
    budget: NutrientBudget,
    closure: BudgetClosure,
    competition: Optional[PFTCompetition] = None,
    sinks: Optional[NutrientSinks] = None
) -> dict:
    """Convert all results to a JSON-serializable dictionary."""
    result = {
        'nutrient': budget.nutrient,
        'n_months': budget.n_months,
        'missing_variables': budget.missing_variables,
        'total_input_annual': budget.total_input_annual,
        'total_output_annual': budget.total_output_annual,
        'inputs': {
            var: {'label': f.label, 'annual_total': f.annual_total}
            for var, f in budget.inputs.items()
        },
        'outputs': {
            var: {'label': f.label, 'annual_total': f.annual_total}
            for var, f in budget.outputs.items()
        },
        'pools': {
            var: {
                'label': p.label,
                'initial': p.initial,
                'final': p.final,
                'change': p.change,
            }
            for var, p in budget.pools.items()
        },
        'closure': {
            'soil_pool_var': closure.soil_pool_var,
            'calculated_dpool_dt': closure.calculated_dpool_dt,
            'actual_dpool_dt': closure.actual_dpool_dt,
            'residual': closure.residual,
            'relative_residual': closure.relative_residual,
            'closure_acceptable': closure.closure_acceptable,
        },
    }

    if competition is not None:
        result['competition'] = {
            'pft_ids': competition.pft_ids,
            'uptake_by_pft': {str(k): v for k, v in competition.uptake_by_pft.items()},
            'demand_by_pft': {str(k): v for k, v in competition.demand_by_pft.items()},
            'supply_demand_ratio': {
                str(k): v if v != float('inf') else 'inf'
                for k, v in competition.supply_demand_ratio.items()
            },
            'uptake_share': {str(k): v for k, v in competition.uptake_share.items()},
            'total_uptake': competition.total_uptake,
            'total_demand': competition.total_demand,
            'dominant_pft': competition.dominant_pft,
            'most_limited_pft': competition.most_limited_pft,
        }

    if sinks is not None:
        result['sinks'] = {
            'ranked_sinks': sinks.ranked_sinks,
            'leaching_exceeds_uptake': sinks.leaching_exceeds_uptake,
            'dominant_sink': sinks.dominant_sink,
            'findings': sinks.findings,
        }

    return result


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Nutrient (N/P) mass balance analysis for A2MC diagnosis"
    )
    parser.add_argument(
        "--nc-file", required=True,
        help="Path to NetCDF output file"
    )
    parser.add_argument(
        "--nutrient", choices=["P", "N"], default="P",
        help="Nutrient to analyze (default: P)"
    )
    parser.add_argument(
        "--pft-ids", type=int, nargs="+",
        help="PFT IDs for competition analysis (e.g., 7 9 10)"
    )
    parser.add_argument(
        "--fates-pft", type=int, default=12,
        help="Total number of PFTs in configuration (default: 12)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file for results"
    )
    parser.add_argument(
        "--text", action="store_true",
        help="Output text summary (for AI reasoning)"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s: %(message)s")

    # Extract budget
    print(f"Extracting {args.nutrient} budget from {args.nc_file}...")
    budget = extract_nutrient_budget(args.nc_file, args.nutrient, args.pft_ids)

    # Budget closure
    print("Checking budget closure...")
    closure = calculate_budget_closure(budget)

    # PFT competition (if PFT IDs given)
    competition = None
    if args.pft_ids:
        print(f"Analyzing PFT competition for PFTs {args.pft_ids}...")
        competition = analyze_pft_competition(
            args.nc_file, args.pft_ids, args.nutrient, args.fates_pft
        )

    # Sink analysis
    print("Identifying nutrient sinks...")
    sinks = identify_nutrient_sinks(budget)

    # Output
    if args.text:
        print("\n" + "=" * 80)
        print(get_balance_summary_for_ai(budget, closure, competition, sinks))
        print("=" * 80)
    elif args.output:
        result = results_to_dict(budget, closure, competition, sinks)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to {args.output}")
    else:
        result = results_to_dict(budget, closure, competition, sinks)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
