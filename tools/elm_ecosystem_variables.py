#!/usr/bin/env python3
"""ELM ecosystem-level (site-scalar) output-variable registry for ECO_ targets.

The FATES family registry (`tools/fates_output_variables`) covers FATES *vegetation*
ecosystem variables (GPP, LAI, NPP, VEGC, ...). ELM-side ecosystem fluxes and states —
energy (latent/sensible heat), water (ET components), carbon (NEE/NEP/HR), and bulk
temperatures/states — are ELM history variables and are registered here.

The ecosystem extractor (`tools/extract_ecosystem_series.parse_ecosystem_specs`) resolves
an `ECO_<var>` key against the FATES family registry FIRST, then falls back to this ELM
registry, so `ECO_gpp` -> FATES_GPP (FATES) while `ECO_eflx_lh_tot` / `ECO_nee` -> the ELM
var here. All are read as 1-D `(time,)` site scalars (same `read_site_1d` path).

Every variable below was verified present in real api-43 ELM-FATES h0 output
(2026-07-11). Units are the native ELM history units; `factor` is 1.0 (any unit change is
a scoring-layer concern — a target carries its own units).

Author: Jing Tao with Claude on Perlmutter.
"""
from __future__ import annotations

from typing import Dict, Tuple

# shorthand -> (nc_var, units, factor)
ELM_ECO_VARS: Dict[str, Tuple[str, str, float]] = {
    # --- energy fluxes (W/m^2) ---
    "eflx_lh_tot":   ("EFLX_LH_TOT", "W/m^2", 1.0),
    "lh":            ("EFLX_LH_TOT", "W/m^2", 1.0),
    "le":            ("EFLX_LH_TOT", "W/m^2", 1.0),
    "latent_heat":   ("EFLX_LH_TOT", "W/m^2", 1.0),
    "fsh":           ("FSH", "W/m^2", 1.0),
    "sh":            ("FSH", "W/m^2", 1.0),
    "sensible_heat": ("FSH", "W/m^2", 1.0),
    "fctr":          ("FCTR", "W/m^2", 1.0),   # canopy transpiration (latent)
    "fcev":          ("FCEV", "W/m^2", 1.0),   # canopy evaporation (latent)
    "fgev":          ("FGEV", "W/m^2", 1.0),   # ground evaporation (latent)
    "fgr":           ("FGR", "W/m^2", 1.0),    # ground heat flux
    "ground_heat":   ("FGR", "W/m^2", 1.0),
    "fsa":           ("FSA", "W/m^2", 1.0),    # absorbed solar
    "fsr":           ("FSR", "W/m^2", 1.0),    # reflected solar
    "fsds":          ("FSDS", "W/m^2", 1.0),   # incident solar
    "fire":          ("FIRE", "W/m^2", 1.0),   # emitted longwave
    # --- water fluxes (mm/s) ---
    "qvegt":         ("QVEGT", "mm/s", 1.0),   # transpiration
    "transpiration": ("QVEGT", "mm/s", 1.0),
    "qvege":         ("QVEGE", "mm/s", 1.0),   # canopy evaporation
    "qsoil":         ("QSOIL", "mm/s", 1.0),   # ground evaporation
    # --- carbon fluxes (gC/m^2/s) ---
    "nee":           ("NEE", "gC/m^2/s", 1.0),
    "nep":           ("NEP", "gC/m^2/s", 1.0),
    "nbp":           ("NBP", "gC/m^2/s", 1.0),
    "hr":            ("HR",  "gC/m^2/s", 1.0),  # heterotrophic respiration
    # --- carbon states (gC/m^2) ---
    "totecosysc":    ("TOTECOSYSC", "gC/m^2", 1.0),
    "totsomc":       ("TOTSOMC", "gC/m^2", 1.0),
    # --- temperatures / states ---
    "tsa":           ("TSA", "K", 1.0),        # 2 m air temperature
    "t2m":           ("TSA", "K", 1.0),
    "tg":            ("TG", "K", 1.0),         # ground temperature
    "tground":       ("TG", "K", 1.0),
    "tv":            ("TV", "K", 1.0),         # vegetation temperature
    "tveg":          ("TV", "K", 1.0),
    "trefmnav":      ("TREFMNAV", "K", 1.0),   # daily-min 2 m air temp
    "trefmxav":      ("TREFMXAV", "K", 1.0),   # daily-max 2 m air temp
    "rh2m":          ("RH2M", "%", 1.0),       # 2 m relative humidity
}


def resolve_elm_eco_var(shorthand: str):
    """shorthand -> (nc_var, units, factor); raises KeyError if unknown."""
    key = shorthand.lower()
    if key not in ELM_ECO_VARS:
        raise KeyError(shorthand)
    return ELM_ECO_VARS[key]
