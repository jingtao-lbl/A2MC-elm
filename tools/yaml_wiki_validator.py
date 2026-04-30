#!/usr/bin/env python3
"""
yaml_wiki_validator.py - Validate curated_relationships.yaml against the codebase wiki.

Confirms that every parameter, mechanism, and output mentioned in the YAML
actually appears in the wiki text and supporting artifacts. Catches gaps
before AI calibration agents retrieve fabricated content.

Five validation dimensions:
    A. Parameter coverage in wiki (literal name match)
    B. Mechanism coverage in wiki (flexible name + code reference)
    C. Output reference validity (CDL existence + wiki mention)
    D. Code-reference resolution (file + routine match in wiki)
    E. Calibration-notes citation freshness (sample of 10)

Read-only on inputs; only writes the output Markdown report.

Usage
-----
    python tools/yaml_wiki_validator.py \\
        --yaml rag/data/curated_relationships.yaml \\
        --wiki docs/fates-knowledge-base/fates-codebase-wiki-e027a40 \\
        --param-file docs/fates-knowledge-base/fates_params_info_e027a40.json \\
        --output-cdl docs/fates-knowledge-base/elm_fates_output_info_e027a40.cdl \\
        --output docs/a2mc_reference/yaml_wiki_validation_e027a40.md

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

# Import A2MC parsers without triggering rag/__init__.py (which needs networkx)
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import importlib.util


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_pp = _load_module("_pp_mod", REPO_ROOT / "rag" / "parameter_parser.py")
_op = _load_module("_op_mod", REPO_ROOT / "rag" / "output_parser.py")
FATESParameterParser = _pp.FATESParameterParser
FATESOutputParser = _op.FATESOutputParser


# =============================================================================
# Data classes
# =============================================================================

@dataclass
class WikiCorpus:
    """In-memory wiki corpus: per-file content plus a concatenated blob."""
    files: Dict[str, str] = field(default_factory=dict)  # path_str -> content
    blob: str = ""
    blob_lower: str = ""  # lazy lowercased blob for case-insensitive lookups

    def files_containing(self, needle: str) -> List[str]:
        return [p for p, c in self.files.items() if needle in c]

    def contains(self, needle: str, case_insensitive: bool = False) -> bool:
        if case_insensitive:
            if not self.blob_lower:
                self.blob_lower = self.blob.lower()
            return needle.lower() in self.blob_lower
        return needle in self.blob

    def contains_file(self, path_or_name: str) -> bool:
        """Match either the full path-as-given OR its basename."""
        if path_or_name in self.blob:
            return True
        base = path_or_name.rsplit("/", 1)[-1]
        return base != path_or_name and base in self.blob


@dataclass
class DimensionResult:
    pass_count: int = 0
    total: int = 0
    rows: List[Tuple] = field(default_factory=list)
    extra_notes: List[str] = field(default_factory=list)

    @property
    def fraction(self) -> float:
        return (self.pass_count / self.total) if self.total else 1.0

    @property
    def status(self) -> str:
        f = self.fraction
        if f >= 0.90:
            return "Green"
        if f >= 0.70:
            return "Yellow"
        return "Red"


# =============================================================================
# Loading
# =============================================================================

def load_wiki(wiki_root: Path) -> WikiCorpus:
    """Load all .md files under wiki_root recursively."""
    corpus = WikiCorpus()
    chunks: List[str] = []
    for md_path in sorted(wiki_root.rglob("*.md")):
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(md_path.relative_to(wiki_root))
        corpus.files[rel] = text
        chunks.append(text)
    corpus.blob = "\n".join(chunks)
    return corpus


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# =============================================================================
# Helpers
# =============================================================================

def _host_model_skip_set(curated: dict) -> Set[str]:
    """Return set of output names whose `outputs[name].host_model` is not 'fates'.

    Outputs marked as ELM-side (or any non-FATES host) are cross-references
    used by A2MC for diagnosis but legitimately absent from the FATES output
    CDL. They are excluded from Dim C's coverage check.
    """
    skip: Set[str] = set()
    for name, body in (curated.get("outputs") or {}).items():
        host = (body or {}).get("host_model")
        if host and host != "fates":
            skip.add(name)
    return skip


def collect_yaml_outputs(curated: dict, exclude_external: bool = False) -> Set[str]:
    """Collect all output variable names referenced anywhere in the YAML.

    If `exclude_external=True`, drop outputs whose `host_model` field is not
    'fates' (used by Dim C, which validates against the FATES output CDL).
    """
    outs: Set[str] = set()
    for cat in (curated.get("categories") or {}).values():
        for o in (cat.get("key_outputs") or []):
            outs.add(o)
    for mech in (curated.get("mechanisms") or {}).values():
        for o in (mech.get("affects") or []):
            outs.add(o)
    for o in (curated.get("outputs") or {}).keys():
        outs.add(o)
    for p in (curated.get("parameters") or {}).values():
        for o in (p.get("affects") or []):
            outs.add(o)
    if exclude_external:
        outs -= _host_model_skip_set(curated)
    return outs


def normalize_mechanism_name(name: str) -> List[str]:
    """Return candidate search forms for a mechanism name.

    For 'PID_Controller' -> ['PID_Controller', 'PID controller', 'pid controller'].
    """
    forms = [name]
    spaced = name.replace("_", " ")
    forms.append(spaced)
    forms.append(spaced.lower())
    # Title-case form already covered if name is title; add lower of original
    forms.append(name.lower())
    # Dedup preserving order
    seen = set()
    out = []
    for f in forms:
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def parse_code_reference(ref: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse 'File.F90::routine' -> ('File.F90', 'routine')."""
    if not ref:
        return None, None
    if "::" in ref:
        f, r = ref.split("::", 1)
        return f.strip(), r.strip()
    return ref.strip(), None


CITATION_RE = re.compile(r"\(([A-Za-z0-9_./\-]+\.(?:F90|py|md)):(\d+)\)")
FILE_RE = re.compile(r"([A-Za-z0-9_./\-]+\.(?:F90|py|md))")


def find_citations(notes_text: str) -> List[Tuple[str, str]]:
    """Find (file, line) citation tuples in calibration_notes text.

    Tries explicit '(file:line)' style first; if none, falls back to any
    .F90/.py/.md file mention in the text.
    """
    matches = CITATION_RE.findall(notes_text)
    if matches:
        return [(f, ln) for f, ln in matches]
    # Fallback: just file names (no line number)
    files = FILE_RE.findall(notes_text)
    return [(f, "") for f in files]


# =============================================================================
# Dimension validators
# =============================================================================

def validate_parameters(curated: dict, wiki: WikiCorpus,
                        param_file: Path) -> DimensionResult:
    """Dimension A: every YAML parameter appears literally in the wiki."""
    result = DimensionResult()
    yaml_params = curated.get("parameters") or {}

    parser = FATESParameterParser(str(param_file))
    file_params = parser.parse()
    file_param_names = set(file_params.keys())

    for pname in sorted(yaml_params.keys()):
        result.total += 1
        wiki_files = wiki.files_containing(pname)
        in_wiki = len(wiki_files) > 0
        in_file = pname in file_param_names
        if in_wiki:
            result.pass_count += 1
        result.rows.append((pname, in_wiki, in_file, len(wiki_files)))
    return result


def validate_mechanisms(curated: dict, wiki: WikiCorpus) -> DimensionResult:
    """Dimension B: each mechanism name AND its code reference present in wiki."""
    result = DimensionResult()
    mechs = curated.get("mechanisms") or {}

    for mname in sorted(mechs.keys()):
        result.total += 1
        m = mechs[mname]
        # Name match (flexible + case-insensitive)
        name_forms = normalize_mechanism_name(mname)
        name_matched_form = None
        for f in name_forms:
            if wiki.contains(f, case_insensitive=True):
                name_matched_form = f
                break
        # Code reference match (file: try basename fallback; routine: case-insensitive)
        code_ref = m.get("code_reference") or ""
        ref_file, ref_routine = parse_code_reference(code_ref)
        file_match = bool(ref_file and wiki.contains_file(ref_file))
        routine_match = bool(ref_routine and wiki.contains(ref_routine, case_insensitive=True))
        ref_status = "n/a" if not code_ref else (
            "BOTH" if file_match and routine_match
            else "FILE_ONLY" if file_match
            else "ROUTINE_ONLY" if routine_match
            else "NEITHER"
        )
        # Status: DOCUMENTED if name found AND (code_ref absent OR at least one of
        # file/routine matched). PARTIAL if only name OR only code_ref. ABSENT otherwise.
        name_ok = name_matched_form is not None
        ref_ok = (not code_ref) or file_match or routine_match
        if name_ok and ref_ok:
            status = "DOCUMENTED"
            result.pass_count += 1
        elif name_ok or ref_ok:
            status = "PARTIAL"
        else:
            status = "ABSENT"
        result.rows.append(
            (mname, status, name_matched_form or "-", ref_file or "-",
             ref_routine or "-", ref_status)
        )
    return result


def validate_outputs(curated: dict, wiki: WikiCorpus,
                     output_cdl: Path) -> DimensionResult:
    """Dimension C: each YAML output exists in CDL and is mentioned in wiki.

    Outputs marked `host_model: <non-fates>` in the YAML's `outputs:` block
    are skipped (they are cross-references to ELM-side variables that A2MC
    uses for diagnosis but legitimately do not appear in the FATES CDL).
    """
    result = DimensionResult()
    outs = collect_yaml_outputs(curated, exclude_external=True)

    op = FATESOutputParser(str(output_cdl))
    cdl_vars = set(op.parse().keys())

    pass_outs = []
    cdl_missing = []
    wiki_missing = []
    for o in sorted(outs):
        result.total += 1
        in_cdl = o in cdl_vars
        in_wiki = wiki.contains(o)
        if in_cdl and in_wiki:
            result.pass_count += 1
            pass_outs.append(o)
        else:
            if not in_cdl:
                cdl_missing.append(o)
            if not in_wiki:
                wiki_missing.append(o)
        result.rows.append((o, in_cdl, in_wiki))
    result.extra_notes.append(
        f"CDL-missing: {len(cdl_missing)}; wiki-missing: {len(wiki_missing)}; "
        f"both-pass: {len(pass_outs)}"
    )
    return result


def validate_code_refs(curated: dict, wiki: WikiCorpus) -> DimensionResult:
    """Dimension D: each mechanism code_reference resolves in the wiki."""
    result = DimensionResult()
    mechs = curated.get("mechanisms") or {}

    for mname in sorted(mechs.keys()):
        ref = (mechs[mname] or {}).get("code_reference") or ""
        if not ref:
            continue
        result.total += 1
        ref_file, ref_routine = parse_code_reference(ref)
        file_found = bool(ref_file and wiki.contains_file(ref_file))
        rout_found = bool(ref_routine and wiki.contains(ref_routine, case_insensitive=True))
        # FILE_ONLY_BY_DESIGN: curator deliberately provided just a file path
        # (no '::routine'), e.g. for mechanisms with no canonical entry point
        # like ECA/RD competition. Counts as PASS when the file resolves.
        no_routine_intended = (ref_routine is None)
        if file_found and rout_found:
            classification = "BOTH_FOUND"
            result.pass_count += 1
        elif file_found and no_routine_intended:
            classification = "FILE_ONLY_BY_DESIGN"
            result.pass_count += 1
        elif file_found:
            classification = "FILE_ONLY"
        elif rout_found:
            classification = "ROUTINE_ONLY"
        else:
            classification = "NEITHER_FOUND"
        result.rows.append((mname, ref_file or "-", ref_routine or "-",
                            classification))
    return result


def _load_axis_values():
    """Load ALL_AXIS_VALUES + FATES_SPECIFIC_AXES from tools/config.

    Loaded lazily to avoid import-time failure if tools/config has issues.
    """
    cfg_mod = _load_module("_cfg_mod", REPO_ROOT / "tools" / "config.py")
    return cfg_mod.ALL_AXIS_VALUES, cfg_mod.FATES_SPECIFIC_AXES


def _validate_one_applies_in(name: str, applies_in: dict, axis_values: Dict,
                              fates_axes: frozenset) -> List[Tuple]:
    """Validate one applies_in: block. Returns rows for the report.

    Each row is (entry_name, severity, axis, value, message).
    severity: 'OK' (passed), 'WARN' (advisory), 'ERROR' (schema violation).
    """
    rows = []
    if not isinstance(applies_in, dict):
        rows.append((name, "ERROR", "—", "—",
                     f"applies_in: must be a mapping, got {type(applies_in).__name__}"))
        return rows

    has_use_fates_true = (
        "use_fates" in applies_in
        and isinstance(applies_in["use_fates"], list)
        and True in applies_in["use_fates"]
    )

    for axis, values in applies_in.items():
        # (a) axis name must be in ALL_AXIS_VALUES
        if axis not in axis_values:
            rows.append((name, "ERROR", axis, "—",
                         f"unknown axis '{axis}' (valid axes: "
                         f"{', '.join(sorted(axis_values))})"))
            continue
        # (b) values must be a list
        if not isinstance(values, list):
            rows.append((name, "ERROR", axis, str(values),
                         f"axis '{axis}' value must be a list, got "
                         f"{type(values).__name__}"))
            continue
        if not values:
            rows.append((name, "ERROR", axis, "[]",
                         f"axis '{axis}' value list cannot be empty"))
            continue
        # (c) each value must be in the axis enum
        valid = axis_values[axis]
        for v in values:
            if v not in valid:
                rows.append((name, "ERROR", axis, repr(v),
                             f"value {v!r} not in {valid}"))

    # (d) Partial-tagging warning: FATES-specific axis tagged without use_fates: [true]
    fates_tagged = set(applies_in.keys()) & fates_axes
    if fates_tagged and not has_use_fates_true:
        rows.append((name, "WARN", ", ".join(sorted(fates_tagged)), "—",
                     "tags FATES-specific axis without use_fates: [true]; "
                     "consider adding for explicitness"))

    if not rows:
        rows.append((name, "OK", "—", "—", "all axes valid"))
    return rows


def validate_applies_in(curated: dict) -> DimensionResult:
    """Dimension F: validate `applies_in:` blocks across YAML.

    Parameters, mechanisms, and outputs may each carry an optional
    `applies_in:` block. This dimension confirms:

      - Every axis name appears in ALL_AXIS_VALUES.
      - Every value appears in ALL_AXIS_VALUES[axis].
      - FATES-specific axes are not tagged without use_fates: [true]
        (warning, not error — partial tagging works under default-permissive
        logic but is brittle).

    Untagged entries are NOT flagged; default-permissive design treats them
    as universal (applies in all modes).
    """
    result = DimensionResult()
    try:
        axis_values, fates_axes = _load_axis_values()
    except Exception as e:
        result.extra_notes.append(
            f"Could not load ALL_AXIS_VALUES from tools/config: {e}. Skipping Dim F."
        )
        return result

    sections = ("parameters", "mechanisms", "outputs")
    error_count = 0
    warn_count = 0
    ok_count = 0

    for section in sections:
        entries = curated.get(section) or {}
        for entry_name, entry_data in entries.items():
            if not isinstance(entry_data, dict):
                continue
            applies_in = entry_data.get("applies_in")
            if applies_in is None:
                # Universal entry — fine, no applies_in block needed
                continue
            rows = _validate_one_applies_in(
                f"{section}.{entry_name}", applies_in, axis_values, fates_axes,
            )
            for row in rows:
                _name, severity, _axis, _value, _msg = row
                if severity == "ERROR":
                    error_count += 1
                elif severity == "WARN":
                    warn_count += 1
                else:
                    ok_count += 1
                result.rows.append(row)

    result.total = ok_count + warn_count + error_count
    # Pass = OK + WARN (warnings don't fail the dimension). Errors fail.
    result.pass_count = ok_count + warn_count
    if result.total == 0:
        result.extra_notes.append(
            "No applies_in: blocks present in YAML. "
            "Phase B curation has not yet been applied; this is OK pre-Phase-B."
        )
    elif error_count > 0:
        result.extra_notes.append(
            f"{error_count} schema errors detected (axis or value typos). "
            "Fix these before rebuilding the index."
        )
    if warn_count:
        result.extra_notes.append(
            f"{warn_count} partial-tagging warnings "
            "(FATES-specific axis without use_fates: [true]). "
            "Advisory; works under default-permissive logic."
        )
    return result


def validate_citations(curated: dict, wiki: WikiCorpus,
                       sample_size: int = 10) -> DimensionResult:
    """Dimension E: sample calibration_notes citations and verify file existence."""
    result = DimensionResult()
    params = curated.get("parameters") or {}

    # Collect (param_name, file_ref) candidates
    candidates: List[Tuple[str, str]] = []
    for pname, pdata in params.items():
        notes = (pdata or {}).get("calibration_notes") or ""
        if not notes:
            continue
        cites = find_citations(notes)
        for fname, _line in cites:
            candidates.append((pname, fname))
        if len(candidates) >= sample_size:
            break

    sample = candidates[:sample_size]
    if not sample:
        result.extra_notes.append(
            "No file citations found in calibration_notes; nothing to validate."
        )
        result.total = 0
        return result

    for pname, fname in sample:
        result.total += 1
        in_wiki = wiki.contains(fname)
        if in_wiki:
            result.pass_count += 1
            status = "OK"
        else:
            status = "STALE_CITATION_RISK"
        result.rows.append((pname, fname, status))
    return result


# =============================================================================
# Report
# =============================================================================

def color_for(status: str) -> str:
    return {
        "Green": "green",
        "Yellow": "yellow",
        "Red": "red",
    }.get(status, status.lower())


def overall_verdict(dims: List[DimensionResult]) -> str:
    statuses = [d.status for d in dims if d.total > 0]
    if not statuses:
        return "Yellow"
    if all(s == "Green" for s in statuses):
        return "Green"
    if any(s == "Red" for s in statuses):
        return "Red"
    return "Yellow"


def _table(header: List[str], rows: List[Tuple]) -> List[str]:
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return out


def _build_recommendations(verdict: str, dim_a, dim_b, dim_c, dim_d,
                           dim_e) -> List[str]:
    if verdict == "Green":
        return ["Validation passed; no action needed."]
    recs: List[str] = []
    if dim_a.status != "Green":
        n_absent = len([r for r in dim_a.rows if not r[1]])
        recs.append(
            f"Dimension A at {int(dim_a.fraction * 100)}%: {n_absent} parameters "
            "absent from wiki. Either add wiki documentation or remove them from "
            "the curated YAML."
        )
    if dim_b.status != "Green":
        weak = [r[0] for r in dim_b.rows if r[1] in ("ABSENT", "PARTIAL")]
        sample = ", ".join("`" + m + "`" for m in weak[:5])
        more = "..." if len(weak) > 5 else ""
        recs.append(
            f"Dimension B at {int(dim_b.fraction * 100)}%: {len(weak)} mechanisms "
            f"not fully documented ({sample}{more}). Update mechanism names to "
            "match wiki vocabulary or extend wiki coverage."
        )
    if dim_c.status != "Green":
        recs.append(
            f"Dimension C at {int(dim_c.fraction * 100)}%: outputs missing from "
            "CDL or wiki. Check whether YAML references pin to a stale FATES version."
        )
    if dim_d.status != "Green":
        recs.append(
            f"Dimension D at {int(dim_d.fraction * 100)}%: code references do not "
            "resolve. Wiki may not include those source files; consider using "
            "filenames the wiki actually cites."
        )
    if dim_e.status != "Green" and dim_e.total > 0:
        recs.append(
            f"Dimension E at {int(dim_e.fraction * 100)}%: calibration_notes cite "
            "files not present in wiki. Likely stale citations from an older tree."
        )
    return recs


def write_report(out_path: Path,
                 yaml_path: Path, wiki_root: Path,
                 param_file: Path, output_cdl: Path,
                 curated: dict, wiki: WikiCorpus,
                 dim_a: DimensionResult, dim_b: DimensionResult,
                 dim_c: DimensionResult, dim_d: DimensionResult,
                 dim_e: DimensionResult,
                 dim_f: Optional[DimensionResult] = None) -> None:
    n_params = len(curated.get("parameters") or {})
    n_mechs = len(curated.get("mechanisms") or {})
    n_outs = len(collect_yaml_outputs(curated))
    n_files = len(wiki.files)
    dims = [dim_a, dim_b, dim_c, dim_d, dim_e]
    if dim_f is not None:
        dims.append(dim_f)
    verdict = overall_verdict(dims)
    e_total = dim_e.total if dim_e.total else 0
    f_total = dim_f.total if (dim_f is not None and dim_f.total) else 0

    out: List[str] = [
        f"# YAML-Wiki Validation: curated_relationships.yaml vs {wiki_root.name}",
        "",
        f"**Generated:** {datetime.utcnow().isoformat(timespec='seconds')}Z",
        "",
        f"**YAML:** `{yaml_path}`",
        f"**Wiki:** `{wiki_root}`",
        f"**Parameter file:** `{param_file}`",
        f"**Output CDL:** `{output_cdl}`",
        "",
        "---",
        "",
        "## Sanity assessment",
        "",
        f"- Total YAML parameters: {n_params}",
        f"- Total YAML mechanisms: {n_mechs}",
        f"- Total YAML output references: {n_outs} (deduplicated)",
        f"- Total wiki .md files: {n_files}",
        "",
    ]
    summary_rows = [
        ("A. Parameter coverage in wiki", color_for(dim_a.status),
         f"{dim_a.pass_count}/{dim_a.total}"),
        ("B. Mechanism coverage in wiki", color_for(dim_b.status),
         f"{dim_b.pass_count}/{dim_b.total}"),
        ("C. Output reference validity", color_for(dim_c.status),
         f"{dim_c.pass_count}/{dim_c.total}"),
        ("D. Code-reference resolution", color_for(dim_d.status),
         f"{dim_d.pass_count}/{dim_d.total}"),
        ("E. Citation freshness sample", color_for(dim_e.status),
         f"{dim_e.pass_count}/{e_total}"),
    ]
    if dim_f is not None:
        summary_rows.append(
            ("F. applies_in: schema (Phase B)", color_for(dim_f.status),
             f"{dim_f.pass_count}/{f_total}"),
        )
    out += _table(["Dimension", "Status", "Pass / Total"], summary_rows)
    out += [
        "",
        f"**Overall verdict:** {verdict}",
        "",
        "(Green = all dimensions >= 90% pass; Yellow = any dimension 70-90%; "
        "Red = any dimension < 70%)",
        "",
        "---",
        "",
        "## A. Parameter coverage in wiki",
        "",
    ]
    absent = [r for r in dim_a.rows if not r[1]]
    out += [
        f"- Documented in wiki: {dim_a.pass_count} / {dim_a.total}",
        f"- ABSENT from wiki: {len(absent)} (listed below)",
        "",
    ]
    if absent:
        out.append("### Wiki-absent parameters")
        out.append("")
        rows_a = [
            (f"`{p}`", "yes" if in_file else "NO",
             "" if in_file else "MISSING from param file too")
            for p, _w, in_file, _n in absent
        ]
        out += _table(["Parameter", "In param file?", "Notes"], rows_a)
        out.append("")
    else:
        out += ["All YAML parameters appear in the wiki.", ""]

    out += ["## B. Mechanism coverage in wiki", ""]
    rows_b = [(f"`{n}`", s, fm, rf, rr, rs)
              for n, s, fm, rf, rr, rs in dim_b.rows]
    out += _table(
        ["Mechanism", "Status", "Name match form", "Ref file",
         "Ref routine", "Ref status"], rows_b)
    out.append("")

    out += ["## C. Output reference validity", ""]
    for n in dim_c.extra_notes:
        out.append(f"- {n}")
    out.append("")
    cdl_missing = [r for r in dim_c.rows if not r[1]]
    wiki_missing = [r for r in dim_c.rows if not r[2]]
    if cdl_missing:
        out += ["### Outputs absent from output CDL", ""]
        out += _table(["Output", "In wiki?"],
                      [(f"`{o}`", "yes" if w else "no")
                       for o, _c, w in cdl_missing])
        out.append("")
    if wiki_missing:
        out += ["### Outputs absent from wiki", ""]
        out += _table(["Output", "In CDL?"],
                      [(f"`{o}`", "yes" if c else "no")
                       for o, c, _w in wiki_missing])
        out.append("")
    if not cdl_missing and not wiki_missing:
        out += ["All YAML output references resolve in both CDL and wiki.", ""]

    out += ["## D. Code-reference resolution", ""]
    if dim_d.total == 0:
        out += ["No `code_reference` fields found in mechanisms.", ""]
    else:
        out += _table(
            ["Mechanism", "Ref file", "Ref routine", "Classification"],
            [(f"`{n}`", f"`{rf}`", f"`{rr}`", c)
             for n, rf, rr, c in dim_d.rows])
        out.append("")

    out += ["## E. Citation freshness (sample)", ""]
    for n in dim_e.extra_notes:
        out.append(f"- {n}")
    if dim_e.rows:
        out.append("")
        out += _table(["Parameter", "Cited file", "Status"],
                      [(f"`{p}`", f"`{f}`", s) for p, f, s in dim_e.rows])
    out.append("")

    if dim_f is not None:
        out += ["## F. applies_in: schema (Phase B)", ""]
        for n in dim_f.extra_notes:
            out.append(f"- {n}")
        if dim_f.rows:
            out.append("")
            # Show errors first, then warnings, then OK rows
            ordered_rows = sorted(
                dim_f.rows,
                key=lambda r: {"ERROR": 0, "WARN": 1, "OK": 2}.get(r[1], 3),
            )
            out += _table(
                ["Entry", "Severity", "Axis", "Value", "Message"],
                [(f"`{n}`", s, f"`{a}`" if a != "—" else a,
                  f"`{v}`" if v != "—" else v, m)
                 for n, s, a, v, m in ordered_rows[:50]],
            )
            if len(dim_f.rows) > 50:
                out.append(f"\n*({len(dim_f.rows) - 50} additional rows omitted)*")
        out.append("")

    out += ["---", "", "## Summary recommendations", ""]
    for r in _build_recommendations(verdict, dim_a, dim_b, dim_c, dim_d, dim_e):
        out.append(f"- {r}")
    out.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out), encoding="utf-8")


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Validate curated_relationships.yaml against codebase wiki."
    )
    ap.add_argument("--yaml", required=True, type=Path,
                    help="Path to curated_relationships.yaml")
    ap.add_argument("--wiki", required=True, type=Path,
                    help="Wiki root directory (contains .md files recursively)")
    ap.add_argument("--param-file", required=True, type=Path,
                    help="Parameter file (.cdl/.json/.nc) for cross-checking")
    ap.add_argument("--output-cdl", required=True, type=Path,
                    help="Output CDL file for cross-checking output variables")
    ap.add_argument("--output", required=True, type=Path,
                    help="Path to write Markdown report")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    for p, label in ((args.yaml, "yaml"), (args.wiki, "wiki"),
                     (args.param_file, "param-file"),
                     (args.output_cdl, "output-cdl")):
        if not p.exists():
            print(f"ERROR: --{label} path not found: {p}", file=sys.stderr)
            return 1

    print(f"Loading YAML: {args.yaml}")
    curated = load_yaml(args.yaml)
    print(f"Loading wiki: {args.wiki}")
    wiki = load_wiki(args.wiki)
    print(f"  wiki files: {len(wiki.files)}")

    print("Dimension A: parameter coverage...")
    dim_a = validate_parameters(curated, wiki, args.param_file)
    print(f"  {dim_a.pass_count}/{dim_a.total}  ({dim_a.status})")

    print("Dimension B: mechanism coverage...")
    dim_b = validate_mechanisms(curated, wiki)
    print(f"  {dim_b.pass_count}/{dim_b.total}  ({dim_b.status})")

    print("Dimension C: output reference validity...")
    dim_c = validate_outputs(curated, wiki, args.output_cdl)
    print(f"  {dim_c.pass_count}/{dim_c.total}  ({dim_c.status})")

    print("Dimension D: code-reference resolution...")
    dim_d = validate_code_refs(curated, wiki)
    print(f"  {dim_d.pass_count}/{dim_d.total}  ({dim_d.status})")

    print("Dimension E: citation freshness sample...")
    dim_e = validate_citations(curated, wiki)
    print(f"  {dim_e.pass_count}/{dim_e.total}  ({dim_e.status})")

    print("Dimension F: applies_in: schema (Phase B)...")
    dim_f = validate_applies_in(curated)
    print(f"  {dim_f.pass_count}/{dim_f.total}  ({dim_f.status})")

    print(f"Writing report: {args.output}")
    write_report(args.output, args.yaml, args.wiki, args.param_file,
                 args.output_cdl, curated, wiki,
                 dim_a, dim_b, dim_c, dim_d, dim_e, dim_f)
    verdict = overall_verdict([dim_a, dim_b, dim_c, dim_d, dim_e, dim_f])
    print(f"Done. Overall verdict: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
