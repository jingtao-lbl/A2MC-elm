#!/usr/bin/env python3
"""ELM land-column (snow + soil) output-variable registry for SNOW_/SOIL_ targets.

The FATES registry (`tools/fates_output_variables`) covers FATES *vegetation* variables;
snow and soil-column variables are ELM-side and registered here. Each entry declares its
extraction SHAPE — `site` (a gridcell scalar, 1-D `(time,)`) or `profile` (depth/layer
resolved, 2-D `(time, vert)`) — which is what the dispatcher routes on (NOT the prefix).

Key grammar:
  SNOW_<var> / SOIL_<var>                 -> a site-level variable
  SOIL_<var>_<N>cm / SNOW_<var>_<N>cm     -> a profile variable at depth N cm (nearest node)
  SOIL_<var>_L<n> / SNOW_<var>_L<n>       -> a profile variable at layer index n (1-based)

Snow-LAYER (`levsno`) variables ARE registered below (the confirmed ELM `SNO_*` history
var names), and the extractor threads `LEVSNO_VARS`. But they are **not written to the
default ELM h0 history** — they must be added to the run's history fields (namelist) to
appear in output. Until then a `SNOW_sno_*_surface/bottom` target resolves but the
extractor finds the var absent and skips it (verified against real api-43 output,
2026-07-11: `SNO_T/SNO_Z/...` absent from the default h0; site scalars + soil profiles
present). See the dynamic-layer note on the `SNO_*` block and `read_profile_layer`.

Author: Jing Tao with Claude on Perlmutter.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

# shorthand -> (nc_var, level, vcoord, units, factor)
#   level  : 'site' | 'profile'
#   vcoord : None (site) | 'levgrnd' | 'levsno' | 'levsoi'
LAND_VARS: Dict[str, Tuple[str, str, Optional[str], str, float]] = {
    # --- snow, site-level scalars (confirmed in the extractor) ---
    "snowdp":        ("SNOWDP",  "site", None, "m",  1.0),
    "snow_depth":    ("SNOWDP",  "site", None, "m",  1.0),
    "h2osno":        ("H2OSNO",  "site", None, "mm", 1.0),
    "swe":           ("H2OSNO",  "site", None, "mm", 1.0),
    "fsno":          ("FSNO",    "site", None, "1",  1.0),
    "snow_cover":    ("FSNO",    "site", None, "1",  1.0),
    # --- soil, depth-resolved on levgrnd (confirmed in the extractor's LEVGRND_VARS) ---
    "tsoi":          ("TSOI",    "profile", "levgrnd", "K",        1.0),
    "soil_temp":     ("TSOI",    "profile", "levgrnd", "K",        1.0),
    "h2osoi":        ("H2OSOI",  "profile", "levgrnd", "mm3/mm3",  1.0),
    "soil_moisture": ("H2OSOI",  "profile", "levgrnd", "mm3/mm3",  1.0),
    "soilliq":       ("SOILLIQ", "profile", "levgrnd", "kg/m2",    1.0),
    "soilice":       ("SOILICE", "profile", "levgrnd", "kg/m2",    1.0),
    # --- snow, LAYER-resolved on levsno (confirmed ELM SNO_* history vars, ColumnDataType.F90)
    #     DYNAMIC layers: snl (negative) active layers fill the LAST output levels; absent
    #     layers are spval (no_snow_normal). So only 'surface'/'bottom' selectors are
    #     physically meaningful — NOT a fixed _L<n>/_<N>cm (see read_profile_layer + dev_log).
    "sno_t":         ("SNO_T",      "profile", "levsno", "K",       1.0),
    "sno_temp":      ("SNO_T",      "profile", "levsno", "K",       1.0),
    "sno_z":         ("SNO_Z",      "profile", "levsno", "m",       1.0),
    "sno_liq":       ("SNO_LIQH2O", "profile", "levsno", "kg/m2",   1.0),
    "sno_ice":       ("SNO_ICE",    "profile", "levsno", "kg/m2",   1.0),
    "sno_bw":        ("SNO_BW",     "profile", "levsno", "kg/m3",   1.0),
    "sno_density":   ("SNO_BW",     "profile", "levsno", "kg/m3",   1.0),
    "sno_gs":        ("SNO_GS",     "profile", "levsno", "Microns", 1.0),
    "sno_tk":        ("SNO_TK",     "profile", "levsno", "W/m-K",   1.0),
}

_LAND_KEY = re.compile(r"^(SNOW|SOIL)_(.+)$")
_DEPTH_SUFFIX = re.compile(r"^(.*)_(\d+(?:\.\d+)?)cm$", re.IGNORECASE)
_INDEX_SUFFIX = re.compile(r"^(.*)_L(\d+)$", re.IGNORECASE)
_SEMANTIC_SUFFIX = re.compile(r"^(.*)_(surface|top|bottom)$", re.IGNORECASE)


def parse_land_target_key(name: str):
    """Parse a SNOW_/SOIL_ target key -> (shorthand, selector) or None if not a land key.

    selector: None (site) | ('depth', cm) | ('index', n, 1-based) | ('surface',) | ('bottom',).
    `surface`/`bottom` are the physically-meaningful selectors for **dynamic snow layers**
    (a fixed index/depth does not map to a fixed snow layer — see read_profile_layer); for
    soil they mean the top / deepest layer. Suffix matched case-insensitively; shorthand
    lower-cased for the registry.
    """
    m = _LAND_KEY.match(name)
    if not m:
        return None
    body = m.group(2)
    ms = _SEMANTIC_SUFFIX.match(body)
    if ms:
        kind = ms.group(2).lower()
        return ms.group(1).lower(), ("surface" if kind in ("surface", "top") else "bottom",)
    md = _DEPTH_SUFFIX.match(body)
    if md:
        return md.group(1).lower(), ("depth", float(md.group(2)))
    mi = _INDEX_SUFFIX.match(body)
    if mi:
        return mi.group(1).lower(), ("index", int(mi.group(2)))
    return body.lower(), None


def resolve_land_var(shorthand: str):
    """shorthand -> (nc_var, level, vcoord, units, factor); raises KeyError if unknown."""
    key = shorthand.lower()
    if key not in LAND_VARS:
        raise KeyError(shorthand)
    return LAND_VARS[key]
