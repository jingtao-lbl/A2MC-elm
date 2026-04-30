#!/usr/bin/env python3
"""
case_parser.py - Parse CIME case directories into A2MC ConfigMode.

A CIME case directory carries the full simulation configuration across three
artifacts:

    env_run.xml         <- compset + xmlchange ELM_BLDNML_OPTS append
    user_nl_elm         <- explicit namelist overrides
    CaseDocs/lnd_in     <- post-build fully-resolved namelist
    (or Buildconf/elmconf/lnd_in)

CIME resolves these in order: ELM_BLDNML_OPTS feeds into ELMBuildNamelist.pm,
which combines with user_nl_elm and namelist defaults to produce lnd_in.
For A2MC, lnd_in is the most authoritative (post-build truth) but it does
NOT carry ``-nutrient`` directly (only ``suplnitro``/``suplphos`` indicators);
that field can ONLY be recovered from env_run.xml's ELM_BLDNML_OPTS.

So the resolution per ConfigMode field:

    bgc_mode                <- env_run.xml (-bgc)
    use_fates               <- derived from bgc_mode
    parteh_mode             <- lnd_in > user_nl_elm > default 1
    use_fates_nocomp        <- lnd_in > user_nl_elm > default false
    nutrient                <- env_run.xml (-nutrient) ONLY
    nutrient_comp_pathway   <- env_run.xml (-nutrient_comp_pathway) | lnd_in (nu_com)
    soil_decomp             <- env_run.xml (-soil_decomp) | lnd_in (use_century_decomp)
    Tier 2 (use_fates_*)    <- lnd_in > user_nl_elm > default false
    Tier 3 (crop, methane,
             hydrstress,
             topounit, irrig,
             solar_rad_scheme) <- env_run.xml ELM_BLDNML_OPTS bare flags

Author: Jing Tao with Claude
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional


# Lazy import to avoid circular dependency at module load time.
def _import_config():
    import tools.config as cfg_mod
    return cfg_mod


def parse_env_run_xml(env_run_path: Path) -> str:
    """Extract the ELM_BLDNML_OPTS value from a CIME env_run.xml file.

    Returns the raw flag string (e.g. "-bgc fates -nutrient cnp ..."), or
    empty string if not found.
    """
    if not env_run_path.exists():
        return ""
    try:
        tree = ET.parse(env_run_path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise ValueError(f"Failed to parse {env_run_path}: {e}")

    # Find <entry id="ELM_BLDNML_OPTS" value="..." />
    for entry in root.iter("entry"):
        if entry.get("id") == "ELM_BLDNML_OPTS":
            return entry.get("value", "") or ""
    return ""


def _normalize_namelist_value(raw: str) -> object:
    """Normalize a Fortran namelist value to a Python type.

    - ``.true.`` / ``.false.`` -> Python True / False
    - integer literals -> int
    - quoted strings 'foo' or "foo" -> 'foo' (lowercased for case-insensitive enums)
    - everything else -> stripped string
    """
    s = raw.strip().rstrip(",")
    if not s:
        return ""
    low = s.lower()
    if low in (".true.", "t"):
        return True
    if low in (".false.", "f"):
        return False
    # quoted string
    if (s.startswith("'") and s.endswith("'")) or \
       (s.startswith('"') and s.endswith('"')):
        return s[1:-1]
    # integer
    try:
        return int(s)
    except ValueError:
        pass
    # float
    try:
        return float(s)
    except ValueError:
        pass
    return s


# Match `key = value` lines in a Fortran namelist; tolerates
# leading whitespace, & group markers, comments (!).
_NL_LINE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*(?:!.*)?$"
)


def parse_namelist_file(path: Path) -> Dict[str, object]:
    """Parse a Fortran namelist file (user_nl_elm or lnd_in).

    Returns a dict mapping namelist variable names (lowercased) to
    Python-typed values. Handles single-line `key = value` entries; ignores
    multi-line list values (e.g. hist_fincl1=...long list...) by recording
    them as raw strings, which A2MC doesn't consume.
    """
    if not path.exists():
        return {}
    result: Dict[str, object] = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            # Skip comment lines and group markers
            stripped = line.strip()
            if not stripped or stripped.startswith("!") or \
               stripped.startswith("&") or stripped.startswith("/"):
                continue
            m = _NL_LINE_RE.match(line)
            if not m:
                continue
            key = m.group(1).lower()
            raw_val = m.group(2)
            result[key] = _normalize_namelist_value(raw_val)
    return result


def _resolve_lnd_in(case_dir: Path) -> Optional[Path]:
    """Return path to lnd_in (CaseDocs first, then Buildconf), or None."""
    candidates = [
        case_dir / "CaseDocs" / "lnd_in",
        case_dir / "Buildconf" / "elmconf" / "lnd_in",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def read_case_dir(case_dir: Path) -> Dict[str, object]:
    """Read all three CIME case artifacts and return a merged dict.

    Returns a dict with keys:
        elm_opts (str)        - raw ELM_BLDNML_OPTS from env_run.xml
        elm_flags (dict)      - parsed flag dict (-bgc fates etc.)
        user_nl (dict)        - user_nl_elm key=value pairs
        lnd_in (dict)         - post-build resolved namelist; empty if not built
        lnd_in_path (Path)    - which lnd_in was used (None if neither found)
    """
    case_dir = Path(case_dir)
    if not case_dir.exists():
        raise FileNotFoundError(f"Case directory not found: {case_dir}")

    config = _import_config()

    elm_opts = parse_env_run_xml(case_dir / "env_run.xml")
    elm_flags = config.parse_elm_options(elm_opts)
    user_nl = parse_namelist_file(case_dir / "user_nl_elm")

    lnd_in_path = _resolve_lnd_in(case_dir)
    lnd_in = parse_namelist_file(lnd_in_path) if lnd_in_path else {}

    return {
        "elm_opts": elm_opts,
        "elm_flags": elm_flags,
        "user_nl": user_nl,
        "lnd_in": lnd_in,
        "lnd_in_path": lnd_in_path,
    }


# =============================================================================
# Resolve ConfigMode from a parsed case
# =============================================================================

def case_to_config_mode(case_dir: Path):
    """Build a ConfigMode from a CIME case directory.

    Returns a fully-populated ConfigMode. Raises ValueError if essential
    fields can't be resolved (e.g. ELM_BLDNML_OPTS empty AND no lnd_in).
    """
    config = _import_config()
    ConfigMode = config.ConfigMode

    parsed = read_case_dir(case_dir)
    elm_flags = parsed["elm_flags"]
    user_nl = parsed["user_nl"]
    lnd_in = parsed["lnd_in"]

    # ----- Tier 1 -----
    # bgc_mode: must come from env_run.xml ELM_BLDNML_OPTS
    bgc_mode = str(elm_flags.get("bgc", ""))
    if not bgc_mode:
        # Fall back: derive from lnd_in's use_fates / use_cn flags
        if lnd_in.get("use_fates") is True:
            bgc_mode = "fates"
        elif lnd_in.get("use_cn") is True:
            # Could be cn or bgc; distinguish by use_lch4 (bgc has methane)
            bgc_mode = "bgc" if lnd_in.get("use_lch4") is True else "cn"
        else:
            bgc_mode = "sp"
    if bgc_mode not in ("sp", "cn", "bgc", "fates"):
        raise ValueError(
            f"case parse: bgc_mode={bgc_mode!r} from {case_dir} is not in "
            "{sp,cn,bgc,fates}. Check ELM_BLDNML_OPTS in env_run.xml."
        )

    use_fates = (bgc_mode == "fates")
    if "use_fates" in lnd_in and lnd_in["use_fates"] is not use_fates:
        raise ValueError(
            f"case parse: lnd_in use_fates={lnd_in['use_fates']} contradicts "
            f"bgc_mode={bgc_mode!r} (which derives use_fates={use_fates}). "
            "This indicates an inconsistent CIME state; rebuild the case."
        )

    # parteh_mode: lnd_in > user_nl > default 1 (from FATES namelist defaults)
    parteh_mode = lnd_in.get("fates_parteh_mode",
                             user_nl.get("fates_parteh_mode", 1))
    if not isinstance(parteh_mode, int) or parteh_mode not in (1, 2):
        raise ValueError(
            f"case parse: fates_parteh_mode={parteh_mode!r} invalid "
            "(expected 1 or 2)"
        )

    # use_fates_nocomp: lnd_in > user_nl > default false
    use_fates_nocomp = bool(lnd_in.get("use_fates_nocomp",
                                        user_nl.get("use_fates_nocomp", False)))

    # nutrient: env_run.xml ONLY (lnd_in doesn't carry it directly)
    nutrient = str(elm_flags.get("nutrient", ""))
    if nutrient and nutrient not in ("c", "cn", "cnp"):
        raise ValueError(
            f"case parse: nutrient={nutrient!r} invalid "
            "(expected '', 'c', 'cn', or 'cnp')"
        )

    # nutrient_comp_pathway: env_run.xml or lnd_in nu_com
    pathway = str(elm_flags.get("nutrient_comp_pathway", ""))
    if not pathway and "nu_com" in lnd_in:
        nu_com = str(lnd_in["nu_com"]).lower()
        if nu_com in ("eca", "rd"):
            pathway = nu_com
    if not pathway:
        # ELM default is RD per namelist_defaults.xml:67
        pathway = "rd"

    # soil_decomp: env_run.xml or lnd_in use_century_decomp
    soil_decomp = str(elm_flags.get("soil_decomp", ""))
    if not soil_decomp and "use_century_decomp" in lnd_in:
        soil_decomp = "century" if lnd_in["use_century_decomp"] else "ctc"

    # ----- Tier 2 (FATES feature flags) -----
    # All read from lnd_in (preferred) > user_nl > default
    def _flag(name: str, default=False) -> bool:
        if name in lnd_in:
            return bool(lnd_in[name])
        if name in user_nl:
            return bool(user_nl[name])
        return default

    fates_spitfire_mode = lnd_in.get("fates_spitfire_mode",
                                      user_nl.get("fates_spitfire_mode", 0))
    if not isinstance(fates_spitfire_mode, int) or fates_spitfire_mode not in (0, 1, 2):
        raise ValueError(f"fates_spitfire_mode={fates_spitfire_mode!r} invalid")

    use_fates_planthydro = _flag("use_fates_planthydro")
    use_fates_logging = _flag("use_fates_logging")
    use_fates_sp = _flag("use_fates_sp")
    use_fates_ed_prescribed_phys = _flag("use_fates_ed_prescribed_phys")
    use_fates_fixed_biogeog = _flag("use_fates_fixed_biogeog")

    # ----- Tier 3 (compset modifiers from env_run.xml ELM_BLDNML_OPTS) -----
    crop = bool(elm_flags.get("crop", False))
    dynamic_vegetation = bool(elm_flags.get("dynamic_vegetation", False))
    methane_explicit = bool(elm_flags.get("methane", False))
    methane = methane_explicit or (bgc_mode == "bgc")
    hydrstress = bool(elm_flags.get("hydrstress", False))
    topounit = bool(elm_flags.get("topounit", False))
    irrig_paired = elm_flags.get("irrig", False)
    irrig = (
        bool(elm_flags.get("tw_irr_on", False))
        or (isinstance(irrig_paired, str) and irrig_paired.lower() in ("true", ".true.", "1", "yes", "on"))
        or (isinstance(irrig_paired, bool) and irrig_paired)
    )
    solar_rad_scheme = str(elm_flags.get("solar_rad_scheme", ""))

    # Cross-axis constraints (mirror ConfigMode.from_env)
    if bgc_mode == "fates" and dynamic_vegetation:
        raise ValueError(
            "case parse: bgc_mode='fates' is incompatible with "
            "-dynamic_vegetation; FATES is its own DGVM."
        )
    if bgc_mode == "sp" and use_fates_sp:
        raise ValueError(
            "case parse: bgc_mode='sp' is incompatible with use_fates_sp=True"
        )

    return ConfigMode(
        bgc_mode=bgc_mode,
        use_fates=use_fates,
        parteh_mode=parteh_mode,
        use_fates_nocomp=use_fates_nocomp,
        nutrient=nutrient,
        nutrient_comp_pathway=pathway,
        soil_decomp=soil_decomp,
        fates_spitfire_mode=fates_spitfire_mode,
        use_fates_planthydro=use_fates_planthydro,
        use_fates_logging=use_fates_logging,
        use_fates_sp=use_fates_sp,
        use_fates_ed_prescribed_phys=use_fates_ed_prescribed_phys,
        use_fates_fixed_biogeog=use_fates_fixed_biogeog,
        crop=crop,
        dynamic_vegetation=dynamic_vegetation,
        methane=methane,
        hydrstress=hydrstress,
        topounit=topounit,
        irrig=irrig,
        solar_rad_scheme=solar_rad_scheme,
    )


def resolve_case_dir(explicit: Optional[str] = None) -> Optional[Path]:
    """Return the active CIME case directory, or None if not resolvable.

    Resolution order:
        1. explicit argument
        2. $A2MC_CASE_DIR
        3. ${A2MC_E3SM_ROOT}/cime/scripts/${A2MC_CASE_NAME}  if both set
    """
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None

    env = os.environ.get("A2MC_CASE_DIR")
    if env:
        p = Path(env)
        return p if p.exists() else None

    e3sm = os.environ.get("A2MC_E3SM_ROOT")
    case_name = os.environ.get("A2MC_CASE_NAME")
    if e3sm and case_name:
        p = Path(e3sm) / "cime" / "scripts" / case_name
        if p.exists():
            return p

    return None
