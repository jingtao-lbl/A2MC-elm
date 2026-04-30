#!/usr/bin/env python3
"""
extract_elm_outputs.py - Build elm_output_info_<commit>.cdl from ELM source.

Walks components/elm/src/**/*.F90 looking for `call hist_addfld1d(...)` and
`call hist_addfld2d(...)` registrations, extracts each variable's name,
units, long_name, and 2d type, and emits a CDL file documenting the full
ELM history-variable surface.

Why exists
----------
A2MC's GraphRAG previously used a CASE-SPECIFIC ncdump snapshot for ELM
outputs (elm_fates_output_info.cdl from a Kougarok PtCNPEn845 case).
Phase 4 wiki regen replaced that with a SOURCE-GROUNDED FATES-only
registry (elm_fates_output_info_e027a40.cdl). Result: ELM-side outputs
(TOTSOMC, TOTLITC, NFIX_TO_SMINN, etc.) lost their CDL representation,
producing a Yellow on Validator #2.

This script gives ELM the same source-grounded treatment FATES got.
The output CDL pins to ELM commit d40b843 (api-43-1 milestone).

Usage
-----
    python scripts/extract_elm_outputs.py \\
        --elm-src /path/to/E3SM/components/elm/src \\
        --output docs/fates-knowledge-base/elm_output_info_d40b843.cdl

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# Match `call hist_addfld<X>d(<args>)` with the args spanning continuation lines
# (we collapse continuations before matching so this can be greedy on a logical line).
_CALL_RE = re.compile(
    r"\bcall\s+hist_addfld(\d)d\s*\(\s*(.*?)\s*\)",
    re.IGNORECASE | re.DOTALL,
)

# Match a single `key='value'` or `key="value"` argument
_KW_RE = re.compile(
    r"(\w+)\s*=\s*(?:'([^']*)'|\"([^\"]*)\"|([^,)]+))"
)

# Common ELM dimensions and their canonical sizes. Used for the CDL
# `dimensions:` block. Sizes are typical values; the CDL is descriptive,
# not authoritative for any single run.
ELM_DIMENSIONS: Dict[str, int] = {
    "lndgrid": 1,
    "levgrnd": 15,        # soil layers (vegetated)
    "levsoi": 10,         # FATES soil layers
    "levdcmp": 15,        # decomposition layers
    "levsno": 5,          # snow layers
    "levurb": 5,          # urban roof/wall/floor layers
    "ltype": 9,           # landunit types
    "natpft": 17,         # natural PFTs (CN/BGC, not FATES)
    "cft": 64,            # crop functional types
    "numrad": 2,          # radiation bands
    "nlevsoifl": 10,      # FATES soil layers (alt name)
    "topounit": 1,        # topographic unit
    "column": 16,         # column subgrid
    "pft": 30,            # ELM-side PFT (CN/BGC; NOT FATES PFT)
}

# Map ELM `type2d` values (the 2nd-dimension category) to a (cdl_dim, py_dim_size).
# Where the type2d argument is missing or unrecognized, fall back to the
# raw token value.
_TYPE2D_TO_DIM = {
    "levgrnd": "levgrnd",
    "levsoi": "levsoi",
    "levdcmp": "levdcmp",
    "levsno": "levsno",
    "levurb": "levurb",
    "lev_lake": "lev_lake",
    "lev_ozone": "lev_ozone",
    "ltype": "ltype",
    "natpft": "natpft",
    "cft": "cft",
    "numrad": "numrad",
}


def strip_full_line_comments(text: str) -> str:
    """Drop lines that are pure Fortran comments (`!...`)."""
    out = []
    for line in text.split("\n"):
        s = line.lstrip()
        if s.startswith("!"):
            continue
        out.append(line)
    return "\n".join(out)


def collapse_continuations(text: str) -> str:
    """Replace `&\\n<whitespace>` with a single space for multi-line statements."""
    return re.sub(r"&\s*\n\s*", " ", text)


def parse_kwargs(arg_str: str) -> Dict[str, str]:
    """Parse `key='value', key2='value2', ...` from a Fortran call's args.

    Non-string args (e.g., ``ptr_col=this%foo``) are captured as the
    raw token; only string args (single- or double-quoted) get unquoted.
    """
    args: Dict[str, str] = {}
    for m in _KW_RE.finditer(arg_str):
        key = m.group(1).lower()
        val = m.group(2) if m.group(2) is not None else (
            m.group(3) if m.group(3) is not None else
            (m.group(4) or "").strip()
        )
        args[key] = val
    return args


def extract_from_file(fpath: Path) -> List[Dict]:
    """Extract all hist_addfld*d calls from a single F90 file."""
    try:
        text = fpath.read_text(errors="ignore")
    except Exception:
        return []
    text = strip_full_line_comments(text)
    text = collapse_continuations(text)
    fields = []
    for m in _CALL_RE.finditer(text):
        ndim = int(m.group(1))
        args = parse_kwargs(m.group(2))
        if "fname" not in args:
            continue
        # Skip aliases (Fortran variables, not literals): heuristic — fname
        # should look like a CF variable name (uppercase letters, digits, _)
        fname = args["fname"]
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", fname):
            continue
        fields.append({
            "name": fname,
            "ndim": ndim,
            "units": args.get("units", ""),
            "long_name": args.get("long_name", ""),
            "type2d": args.get("type2d", ""),
            "avgflag": args.get("avgflag", ""),
            "standard_name": args.get("standard_name", ""),
            "src_file": str(fpath),
        })
    return fields


def extract_all(elm_src: Path) -> List[Dict]:
    """Walk the ELM source tree and collect all history-field registrations."""
    if not elm_src.exists():
        raise FileNotFoundError(f"ELM source root not found: {elm_src}")
    all_fields: List[Dict] = []
    seen_names = set()
    n_files = 0
    for fpath in sorted(elm_src.rglob("*.F90")):
        # Skip external_models (FATES, EMI, etc.) — we only want core ELM
        rel = fpath.relative_to(elm_src)
        if "external_models" in rel.parts:
            continue
        n_files += 1
        for f in extract_from_file(fpath):
            if f["name"] in seen_names:
                continue
            f["src_file"] = str(rel)
            all_fields.append(f)
            seen_names.add(f["name"])
    print(f"  Scanned {n_files} F90 files; found {len(all_fields)} unique fields")
    return all_fields


def variable_dims(field: Dict) -> List[str]:
    """Return the CDL dimension list for a field.

    Dim order convention (matches ELM history files):
        1d: (time, lndgrid)
        2d: (time, <type2d>, lndgrid)

    `time` is unlimited and shown as `time = UNLIMITED`. Validator
    treats it as the leading dim of every variable.
    """
    if field["ndim"] == 1:
        return ["time", "lndgrid"]
    type2d = field.get("type2d", "")
    inner = _TYPE2D_TO_DIM.get(type2d, type2d or "unknown_dim")
    return ["time", inner, "lndgrid"]


def emit_cdl(fields: List[Dict], out_path: Path, elm_commit: str) -> None:
    """Generate a CDL file matching the ELM core output registry."""
    short = elm_commit[:7] if len(elm_commit) >= 7 else elm_commit
    today = datetime.now().strftime("%Y-%m-%d")

    # Collect all dimensions actually used by extracted fields
    used_dims = {"lndgrid", "time"}
    for f in fields:
        used_dims.update(variable_dims(f))

    lines = [
        "// ELM core output-variable registry (ELM-only, no FATES variables)",
        f"// Source pin: ELM commit {short} (api-43-1 milestone, ELM coupled to FATES e027a40)",
        f"//             extracted from components/elm/src/**/*.F90 hist_addfld* calls",
        f"// Generated: {today}",
        f"// Companion to elm_fates_output_info_{short}.cdl (FATES-only registry).",
        "//",
        "// Each variable's CDL attributes preserve what `hist_addfld1d`/`hist_addfld2d`",
        "// registered in source: long_name, units, plus optional standard_name.",
        "// Dimensions are per-file-typical sizes (time × spatial dim × lndgrid).",
        "",
        f"netcdf elm_output_{short} {{",
        "  dimensions:",
        "    time = UNLIMITED ;",
    ]
    for dim in sorted(used_dims - {"time", "unknown_dim"}):
        size = ELM_DIMENSIONS.get(dim)
        if size is None:
            # Unknown 2d type — declare as size 1 so CDL parses
            lines.append(f"    {dim} = 1 ;   // size unknown (dim not in ELM_DIMENSIONS)")
        else:
            lines.append(f"    {dim} = {size} ;")
    lines.append("  variables:")
    for f in sorted(fields, key=lambda x: x["name"]):
        dims = ", ".join(variable_dims(f))
        lines.append(f"    float {f['name']}({dims}) ;")
        # Attributes
        if f.get("long_name"):
            ln = f["long_name"].replace('"', '\\"')
            lines.append(f"        {f['name']}:long_name = \"{ln}\" ;")
        if f.get("units"):
            u = f["units"].replace('"', '\\"')
            lines.append(f"        {f['name']}:units = \"{u}\" ;")
        if f.get("standard_name"):
            sn = f["standard_name"].replace('"', '\\"')
            lines.append(f"        {f['name']}:standard_name = \"{sn}\" ;")
        if f.get("avgflag"):
            lines.append(f"        {f['name']}:cell_methods = \"time: {f['avgflag']}\" ;")
        lines.append(f"        {f['name']}:src_file = \"{f['src_file']}\" ;")
    lines.append("}")
    out_path.write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Extract ELM history-output registry")
    ap.add_argument(
        "--elm-src", type=Path,
        default=Path("/Users/jingtao/Desktop/Work/SourceCode/ELM_FATES/E3SM_FATES_api43-1/components/elm/src"),
        help="Path to components/elm/src in your E3SM checkout",
    )
    ap.add_argument(
        "--output", type=Path,
        default=Path("docs/fates-knowledge-base/elm_output_info_d40b843.cdl"),
        help="Output CDL path",
    )
    ap.add_argument(
        "--elm-commit", default="d40b8431",
        help="ELM commit hash for source-pin (default: d40b8431, api-43-1 milestone)",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    print(f"Extracting ELM output registry from {args.elm_src}")
    fields = extract_all(args.elm_src)
    print(f"  Total unique fields: {len(fields)}")
    by_dim = defaultdict(int)
    for f in fields:
        by_dim[f["ndim"]] += 1
    for ndim, n in sorted(by_dim.items()):
        print(f"    {ndim}D fields: {n}")
    print(f"\nWriting {args.output}")
    emit_cdl(fields, args.output, args.elm_commit)
    print(f"Done. {len(fields)} variables written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
