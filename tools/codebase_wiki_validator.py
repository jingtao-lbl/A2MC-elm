#!/usr/bin/env python3
"""
codebase_wiki_validator.py - Validate a codebase wiki against the source tree.

Catches wiki-side hallucinations (fabricated routine names, dead file:line
citations, wrong parameter names, missing module files) that would otherwise
propagate through curated YAML and into RAG retrieval.

Sister tool to:
    - tools/yaml_wiki_validator.py  (YAML  vs wiki + param + CDL)
    - tools/rag_diff.py             (compare two RAG profiles)

Five validation dimensions:
    1. File-citation existence       (does <subdir>/<File>.F90 exist?)
    2. Line-bound validity           (does file have at least <line> lines?)
    3. Routine declaration presence  (top-N backtick-quoted identifiers)
    4. Parameter-name validity       (fates_* names match param file)
    5. Module-file presence          (*Mod.F90 mentions exist somewhere)

Read-only on inputs; only writes the output Markdown report.

Usage
-----
    python tools/codebase_wiki_validator.py \\
        --wiki docs/fates-knowledge-base/fates-codebase-wiki-e027a40 \\
        --source /path/to/components/elm/src/external_models/fates \\
        --param-file docs/fates-knowledge-base/fates_params_info_e027a40.json \\
        --output docs/a2mc_reference/wiki_source_validation_fates_e027a40.md

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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


# =============================================================================
# Data classes
# =============================================================================

@dataclass
class WikiCorpus:
    """In-memory wiki corpus: per-file content plus a concatenated blob."""
    files: Dict[str, str] = field(default_factory=dict)  # rel_path -> content
    blob: str = ""

    def files_containing(self, needle: str) -> List[str]:
        return [p for p, c in self.files.items() if needle in c]


@dataclass
class SourceIndex:
    """In-memory source index for fast lookups.

    Attributes
    ----------
    rel_paths : Set[str]
        All .F90 files keyed by path relative to source root, forward slashes.
    by_basename : Dict[str, List[str]]
        basename (e.g., 'EDMainMod.F90') -> list of relative paths.
    line_counts : Dict[str, int]
        rel_path -> line count of that file (lazy populated).
    contents : Dict[str, str]
        rel_path -> full file text (lazy populated, used to grep routines).
    """
    rel_paths: Set[str] = field(default_factory=set)
    by_basename: Dict[str, List[str]] = field(default_factory=dict)
    line_counts: Dict[str, int] = field(default_factory=dict)
    contents: Dict[str, str] = field(default_factory=dict)

    def has_path(self, rel: str) -> bool:
        return rel in self.rel_paths

    def has_basename(self, basename: str) -> bool:
        return basename in self.by_basename

    def line_count(self, rel: str, source_root: Path) -> int:
        if rel not in self.line_counts:
            try:
                # Read just to count lines without keeping content
                full = (source_root / rel).read_text(
                    encoding="utf-8", errors="replace"
                )
                self.line_counts[rel] = full.count("\n") + (
                    0 if full.endswith("\n") else 1
                )
            except Exception:
                self.line_counts[rel] = 0
        return self.line_counts[rel]


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


def load_source_index(source_root: Path) -> SourceIndex:
    """Walk source_root and collect all .F90 files."""
    idx = SourceIndex()
    for p in source_root.rglob("*.F90"):
        # Skip .F90.in templates if any (rglob('*.F90') already excludes .in)
        try:
            rel = str(p.relative_to(source_root)).replace("\\", "/")
        except ValueError:
            continue
        idx.rel_paths.add(rel)
        idx.by_basename.setdefault(p.name, []).append(rel)
    return idx


# =============================================================================
# Regex patterns
# =============================================================================

# Citation patterns: try parenthesized first, then bare path:line.
# Match common subdir prefixes (letters, digits, underscores, slashes).
CITE_PAREN_RE = re.compile(r"\(([A-Za-z0-9_/\-]+\.F90):(\d+)")
CITE_BARE_RE = re.compile(r"(?<![\w/])([A-Za-z0-9_][A-Za-z0-9_/\-]*\.F90):(\d+)")

# Module file references: e.g., EDMainMod.F90, FatesAllometryMod.F90
MODULE_FILE_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*Mod\.F90)\b")

# Backtick-delimited identifiers (candidates for routine names).
BACKTICK_ID_RE = re.compile(r"`([A-Za-z][A-Za-z0-9_]*)`")

# Parameter-style identifiers in wiki. We restrict to fates_* style which is
# the canonical FATES parameter prefix; reduces false positives drastically.
PARAM_NAME_RE = re.compile(r"\b(fates_[a-z0-9_]+)\b")

# Known false-positive classes for `fates_*` parameter-name detection. The wiki
# uses the same prefix for derived-type names, namelist flags, dimension tokens,
# filenames, and wildcard prefix strings — none of which appear in the parameter
# JSON. These regexes pre-filter each PARAM_NAME_RE hit so that Dim 4 measures
# only true candidate parameter names. Hand-derived from the api-43-1 audit.
PARAM_NAME_FP_PATTERNS = [
    re.compile(r"^fates_.*_type$"),                      # derived-type names
    re.compile(r"^fates_lev[a-z]+$"),                    # dimension tokens
    re.compile(r"^fates_params_(default|new|info|opt|"
               r"arctic|swapped|3pft)[a-z0-9_]*$"),      # parameter filenames
    re.compile(r"^fates_(log|tiny|r8|unset_int|"
               r"string_length|errfates|cnplimiter|"
               r"hist|hlm_pftno|cx_int|emadcxdt|"
               r"oldstock|swapped|cnp_)$"),              # constants/handles
    re.compile(r"^fates_history_[a-z]+$"),               # history-system internals
    re.compile(r"^fates_(restart|hydro|landuse|"
               r"history|leafage|litterclass|fuel|"
               r"hdim|io_dimension|woodprod|np_comp_"
               r"scaling|hydr_organs|plant_organs|"
               r"phen_(season_decid|stress_decid|"
               r"evergreen|doff_time|doff_temp)|"
               r"check_param_set|"
               r"daily_(n|p|nh4|no3)_(demand|uptake)|"
               r"acc_nesterov_id|"
               r"(agcwd|bgcwd|leaf|cwd)_litt|"
               r"(termnindiv|imortrate)_[a-z]+|"
               r"(my_new_param|patch_type|cohort_type|"
               r"interface_type|3pft|arctic|swapped|"
               r"radiation_model|stomatal_model|"
               r"insufficient_for_harvest_debt|"
               r"bypass_harvest_debt|no_harvest_debt|"
               r"mortality_disturbance_fraction|"
               r"frzleaftol|cold_(dec_status|leafondate)|"
               r"area_pa|age_pa|nplant|dbh|height|"
               r"(h|c|b)mort|gdd_site|leaf_(c|n|p|"
               r"photo_tempsens_model|stomatal_model)|"
               r"maintresp_leaf_model|"
               r"rad_clumping|numpft|"
               r"allom_zroot_|cnp_(km|prescribed|vmax|"
               r"nfix|eca_km)_))[a-z0-9_]*$"),
    re.compile(r"^fates_[a-z0-9_]*_$"),                  # wildcard prefix forms
]

# Subroutine / function declarations in Fortran source.
# Handles plain `subroutine foo`, `function foo`, AND typed function returns
# like `integer function foo`, `real(r8) function foo`, `logical function foo`,
# `character(len=*) function foo`, etc. Also handles attribute prefixes
# (recursive, pure, elemental, module).
SUB_DECL_RE = re.compile(
    r"^\s*"
    r"(?:(?:recursive|pure|elemental|module)\s+)*"
    r"(?:(?:integer|real|logical|character|double\s+precision|complex)"
    r"\s*(?:\([^)]*\))?\s+)?"
    r"(?:(?:recursive|pure|elemental|module)\s+)*"
    r"(?:subroutine|function)\s+([A-Za-z][A-Za-z0-9_]*)",
    re.IGNORECASE | re.MULTILINE,
)

# Words that hint a backticked identifier is referring to a routine.
ROUTINE_HINT_RE = re.compile(
    r"\b(subroutine|routine|function|called from|calls?\s+to|"
    r"call\s+`?[A-Za-z]|invoked\s+by)\b",
    re.IGNORECASE,
)

# Words that are obviously NOT routine names (Fortran keywords + common words).
ROUTINE_BLACKLIST = {
    # Fortran keywords / intrinsics
    "if", "then", "else", "endif", "do", "enddo", "end", "case", "select",
    "type", "kind", "real", "integer", "logical", "character", "module",
    "use", "implicit", "none", "private", "public", "subroutine", "function",
    "return", "stop", "call", "where", "elsewhere", "while", "forall",
    "associate", "block", "exit", "cycle", "continue", "go", "goto",
    "true", "false", "pure", "elemental", "recursive", "result",
    "in", "out", "inout", "intent", "optional", "target", "pointer",
    "allocatable", "save", "parameter", "data", "dimension", "common",
    "namelist", "external", "intrinsic", "interface", "contains",
    "abstract", "extends", "class", "deferred", "procedure", "generic",
    "import", "bind", "size", "len", "trim", "adjustl", "adjustr",
    "present", "any", "all", "minval", "maxval", "sum", "abs", "min", "max",
    "sqrt", "exp", "log", "sin", "cos", "tan", "huge", "tiny", "epsilon",
    # Common English / Markdown noise
    "the", "and", "for", "with", "from", "this", "that", "these", "those",
    "are", "was", "were", "has", "have", "had", "but", "not", "can",
    "will", "should", "would", "could", "may", "might", "must",
    "yes", "no", "true", "false", "none", "null", "nan",
    "src", "dst", "tmp", "var", "val", "key", "row", "col", "idx",
    # More Fortran intrinsics
    "associated", "allocated", "shape", "lbound", "ubound", "transfer",
    "cshift", "merge", "pack", "unpack", "spread", "reshape",
    # Domain predicates / type tags often appearing in backticks (not routines)
    "crop", "iscft", "nfixer", "woody", "evergreen", "deciduous",
    "perennial", "annual", "shrub", "grass", "tree", "needleleaf",
    "broadleaf", "c3", "c4", "boreal", "temperate", "tropical",
}


# =============================================================================
# Helpers
# =============================================================================

def find_citations(blob: str) -> List[Tuple[str, int]]:
    """Extract unique (file_path, line) tuples from wiki text.

    Tries parenthesized form first (recommended in wiki style guide), then
    falls back to bare 'path/File.F90:NNN' form. Deduplicates.
    """
    seen: Set[Tuple[str, int]] = set()
    out: List[Tuple[str, int]] = []

    for m in CITE_PAREN_RE.finditer(blob):
        path, line = m.group(1), int(m.group(2))
        key = (path, line)
        if key not in seen:
            seen.add(key)
            out.append(key)

    for m in CITE_BARE_RE.finditer(blob):
        path, line = m.group(1), int(m.group(2))
        key = (path, line)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def find_citation_origin(corpus: WikiCorpus, path: str, line: int) -> str:
    """Return the first wiki .md file mentioning this (path:line) citation."""
    needle_paren = f"({path}:{line}"
    needle_bare = f"{path}:{line}"
    for rel, text in corpus.files.items():
        if needle_paren in text or needle_bare in text:
            return rel
    return "(unknown)"


def find_module_mentions(blob: str) -> Set[str]:
    """Extract unique *Mod.F90 basenames mentioned anywhere."""
    return set(MODULE_FILE_RE.findall(blob))


def find_first_origin(corpus: WikiCorpus, needle: str) -> str:
    """Return the first wiki .md file containing the literal needle."""
    for rel, text in corpus.files.items():
        if needle in text:
            return rel
    return "(unknown)"


def find_parameter_mentions(blob: str) -> Counter:
    """Count fates_* parameter mentions in wiki body text.

    Filters out hits matching `PARAM_NAME_FP_PATTERNS` (derived-type names,
    dimension tokens, file aliases, namelist flags, wildcard prefixes) so that
    Dim 4 measures only true candidate parameter names.
    """
    counter: Counter = Counter()
    for name in PARAM_NAME_RE.findall(blob):
        if any(p.match(name) for p in PARAM_NAME_FP_PATTERNS):
            continue
        counter[name] += 1
    return counter


def collect_routine_candidates(corpus: WikiCorpus,
                               top_n: int = 50) -> List[Tuple[str, int]]:
    """Pick top-N identifiers used as routines in wiki text.

    To minimise false positives (struct fields, parameter names, type
    components also appear in backticks), we only accept identifiers that
    appear in one of these high-precision routine patterns:

      1. ``ident()``  -- function-call form with parentheses
      2. ``ident``    -- but immediately preceded by 'call ' / 'subroutine ' /
                         'function ' / 'routine ' / 'invokes ' / 'calls '
      3. ``Mod.F90::ident`` -- explicit code-reference form (rare in wiki)

    Returns list of (name, mention_count) sorted by count desc.
    """
    counter: Counter = Counter()

    # Pattern 1: `ident()` -- backticked identifier followed by ()
    pat_call = re.compile(r"`([A-Za-z][A-Za-z0-9_]*)\s*\(\s*\)`?")
    # Also accept `ident` followed immediately by `()` outside the backtick
    pat_call2 = re.compile(r"`([A-Za-z][A-Za-z0-9_]*)`\s*\(\s*\)")
    # Pattern 2: routine-keyword right before backticked identifier
    pat_kw = re.compile(
        r"\b(?:call|calls?\s+to|invokes?|invoked\s+by|"
        r"subroutine|function|routine|called\s+(?:from|by))\s+"
        r"`([A-Za-z][A-Za-z0-9_]*)`",
        re.IGNORECASE,
    )
    # Pattern 3: File.F90::ident or Mod::ident
    pat_ref = re.compile(
        r"`?[A-Za-z][A-Za-z0-9_]*(?:\.F90)?::([A-Za-z][A-Za-z0-9_]*)`?"
    )

    for text in corpus.files.values():
        for pat in (pat_call, pat_call2, pat_kw, pat_ref):
            for m in pat.finditer(text):
                ident = m.group(1)
                low = ident.lower()
                if len(ident) < 4 or low in ROUTINE_BLACKLIST:
                    continue
                counter[ident] += 1
    return counter.most_common(top_n)


# =============================================================================
# Dimension validators
# =============================================================================

def _resolve_citation(path: str, source: SourceIndex) -> Optional[str]:
    """Resolve a cited path to an actual source rel-path.

    The wiki uses two citation styles:
      - Subdir-qualified: 'biogeochem/EDMainMod.F90'
      - Basename-only:    'EDMainMod.F90'

    We accept either: if the exact rel-path exists, use it; else if the
    basename matches a unique file under source, use that. If multiple
    files share the basename and no subdir prefix is given, we still
    accept (any one is sufficient evidence the file exists).
    """
    if source.has_path(path):
        return path
    base = path.rsplit("/", 1)[-1]
    if source.has_basename(base):
        return source.by_basename[base][0]
    return None


def validate_file_citations(citations: List[Tuple[str, int]],
                            source: SourceIndex,
                            corpus: WikiCorpus) -> DimensionResult:
    """Dimension 1: each (file, line) cited path exists in source.

    Accepts both subdir-qualified and basename-only citation styles.
    """
    result = DimensionResult()
    for path, line in citations:
        result.total += 1
        if _resolve_citation(path, source) is not None:
            result.pass_count += 1
        else:
            origin = find_citation_origin(corpus, path, line)
            result.rows.append((f"{path}:{line}", origin))
    return result


def validate_line_bounds(citations: List[Tuple[str, int]],
                         source: SourceIndex, source_root: Path,
                         corpus: WikiCorpus) -> DimensionResult:
    """Dimension 2: cited line number does not exceed file length.

    Only counts citations that PASSED Dimension 1 (file exists, possibly
    via basename-only resolution).
    """
    result = DimensionResult()
    for path, line in citations:
        resolved = _resolve_citation(path, source)
        if resolved is None:
            continue
        result.total += 1
        n_lines = source.line_count(resolved, source_root)
        if line <= n_lines:
            result.pass_count += 1
        else:
            origin = find_citation_origin(corpus, path, line)
            result.rows.append(
                (f"{path}:{line}", n_lines, line - n_lines, origin)
            )
    return result


def validate_routines(candidates: List[Tuple[str, int]],
                      source: SourceIndex, source_root: Path,
                      corpus: WikiCorpus) -> DimensionResult:
    """Dimension 3: routine candidates appear as subroutine/function decls
    somewhere in the source tree.

    Accepts subroutine, function (typed or plain), and `interface NAME`
    blocks (Fortran generic interfaces — the wiki often references the
    public interface name, not its underlying specific procedures).
    """
    result = DimensionResult()
    iface_re = re.compile(
        r"^\s*(?:abstract\s+)?interface\s+([A-Za-z][A-Za-z0-9_]*)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    # Build (lazy) global declared-routine set by scanning every .F90 once.
    declared: Set[str] = set()
    for rel in source.rel_paths:
        try:
            text = (source_root / rel).read_text(
                encoding="utf-8", errors="replace"
            )
        except Exception:
            continue
        for m in SUB_DECL_RE.finditer(text):
            declared.add(m.group(1).lower())
        for m in iface_re.finditer(text):
            declared.add(m.group(1).lower())

    for name, count in candidates:
        result.total += 1
        if name.lower() in declared:
            result.pass_count += 1
        else:
            origin = find_first_origin(corpus, f"`{name}`")
            result.rows.append((name, count, origin))
    return result


def validate_parameters(mentions: Counter, param_file: Optional[Path],
                        corpus: WikiCorpus) -> DimensionResult:
    """Dimension 4: fates_* mentions exist in the parameter file."""
    result = DimensionResult()
    if param_file is None:
        result.extra_notes.append(
            "No --param-file supplied; skipping parameter-name validation."
        )
        return result

    pp_mod = _load_module("_pp_mod_cwv", REPO_ROOT / "rag" / "parameter_parser.py")
    parser = pp_mod.FATESParameterParser(str(param_file))
    valid_names: Set[str] = set(parser.parse().keys())

    for name, count in sorted(mentions.items(),
                              key=lambda kv: (-kv[1], kv[0])):
        result.total += 1
        if name in valid_names:
            result.pass_count += 1
        else:
            origin = find_first_origin(corpus, name)
            result.rows.append((name, count, origin))
    return result


def validate_module_files(modules: Set[str], source: SourceIndex,
                          corpus: WikiCorpus) -> DimensionResult:
    """Dimension 5: every *Mod.F90 mention exists somewhere in source."""
    result = DimensionResult()
    for mod in sorted(modules):
        result.total += 1
        if source.has_basename(mod):
            result.pass_count += 1
        else:
            origin = find_first_origin(corpus, mod)
            result.rows.append((mod, origin))
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


def _build_recommendations(verdict: str, dim1, dim2, dim3, dim4,
                           dim5) -> List[str]:
    if verdict == "Green":
        return ["Validation passed; no action needed."]
    recs: List[str] = []
    if dim1.status != "Green" and dim1.total > 0:
        n_bad = len(dim1.rows)
        recs.append(
            f"Dimension 1 at {int(dim1.fraction * 100)}%: {n_bad} citations "
            "point to nonexistent source files. Wiki may be pinned to a "
            "different commit than the source tree, or files were renamed."
        )
    if dim2.status != "Green" and dim2.total > 0:
        n_bad = len(dim2.rows)
        recs.append(
            f"Dimension 2 at {int(dim2.fraction * 100)}%: {n_bad} citations "
            "exceed file line count. Stale line numbers from a pre-refactor "
            "version of the file."
        )
    if dim3.status != "Green" and dim3.total > 0:
        n_bad = len(dim3.rows)
        recs.append(
            f"Dimension 3 at {int(dim3.fraction * 100)}%: {n_bad} of the "
            "top routine candidates have no matching subroutine/function "
            "declaration in source. Likely fabricated or renamed."
        )
    if dim4.status != "Green" and dim4.total > 0:
        n_bad = len(dim4.rows)
        recs.append(
            f"Dimension 4 at {int(dim4.fraction * 100)}%: {n_bad} fates_* "
            "parameter names not found in the parameter file. Either "
            "fabricated or renamed in this commit."
        )
    if dim5.status != "Green" and dim5.total > 0:
        n_bad = len(dim5.rows)
        recs.append(
            f"Dimension 5 at {int(dim5.fraction * 100)}%: {n_bad} *Mod.F90 "
            "files mentioned in wiki do not exist in source. Module renamed "
            "or removed."
        )
    return recs


def write_report(out_path: Path,
                 wiki_root: Path, source_root: Path,
                 param_file: Optional[Path],
                 corpus: WikiCorpus, source: SourceIndex,
                 citations: List[Tuple[str, int]],
                 modules: Set[str],
                 param_mentions: Counter,
                 dim1: DimensionResult, dim2: DimensionResult,
                 dim3: DimensionResult, dim4: DimensionResult,
                 dim5: DimensionResult) -> None:
    n_wiki = len(corpus.files)
    n_src = len(source.rel_paths)
    n_cites = len(citations)
    n_params = sum(param_mentions.values())
    verdict = overall_verdict([dim1, dim2, dim3, dim4, dim5])

    out: List[str] = [
        f"# Wiki-Source Validation: {wiki_root.name} vs {source_root.name}",
        "",
        f"**Generated:** {datetime.utcnow().isoformat(timespec='seconds')}Z",
        "",
        f"**Wiki:** `{wiki_root}`",
        f"**Source:** `{source_root}`",
        f"**Parameter file:** "
        f"{'`' + str(param_file) + '`' if param_file else 'none'}",
        "",
        "---",
        "",
        "## Sanity assessment",
        "",
        f"- Total wiki .md files: {n_wiki}",
        f"- Total source .F90 files: {n_src}",
        f"- Total wiki citations extracted: {n_cites}",
        f"- Total parameter mentions: {n_params} "
        f"({len(param_mentions)} unique)",
        f"- Total module-file mentions: {len(modules)} unique",
        "",
    ]
    out += _table(
        ["Dimension", "Status", "Pass / Total"],
        [
            ("1. File-citation existence", color_for(dim1.status),
             f"{dim1.pass_count}/{dim1.total}"),
            ("2. Line-bound validity", color_for(dim2.status),
             f"{dim2.pass_count}/{dim2.total}"),
            ("3. Routine declaration presence", color_for(dim3.status),
             f"{dim3.pass_count}/{dim3.total}"),
            ("4. Parameter-name validity", color_for(dim4.status),
             f"{dim4.pass_count}/{dim4.total}"),
            ("5. Module-file presence", color_for(dim5.status),
             f"{dim5.pass_count}/{dim5.total}"),
        ],
    )
    out += [
        "",
        f"**Overall verdict:** {verdict}",
        "",
        "(Green = all dimensions >= 90% pass; Yellow = any dimension 70-90%; "
        "Red = any dimension < 70%)",
        "",
        "---",
        "",
    ]

    # ----- Dimension 1
    out += [
        "## 1. File-citation existence",
        "",
        f"- Total citations: {dim1.total}",
        f"- File EXISTS:    {dim1.pass_count}",
        f"- File ABSENT:    {len(dim1.rows)}",
        "",
    ]
    if dim1.rows:
        out += ["### Citations to nonexistent files", ""]
        out += _table(
            ["Citation (file:line)", "Wiki file containing it"],
            [(f"`{c}`", f"`{o}`") for c, o in dim1.rows[:50]],
        )
        if len(dim1.rows) > 50:
            out.append("")
            out.append(f"...({len(dim1.rows) - 50} more rows omitted)")
        out.append("")
    else:
        out += ["All citations resolve to existing files.", ""]

    # ----- Dimension 2
    out += [
        "## 2. Line-bound validity",
        "",
        f"- Citations checked: {dim2.total} (only those that passed Dim 1)",
        f"- Within bounds:     {dim2.pass_count}",
        f"- OVER file length:  {len(dim2.rows)}",
        "",
    ]
    if dim2.rows:
        out += ["### Citations whose line exceeds file length", ""]
        out += _table(
            ["Citation (file:line)", "File lines", "Overshoot",
             "Wiki file containing it"],
            [(f"`{c}`", n, over, f"`{o}`")
             for c, n, over, o in dim2.rows[:50]],
        )
        if len(dim2.rows) > 50:
            out.append("")
            out.append(f"...({len(dim2.rows) - 50} more rows omitted)")
        out.append("")
    else:
        out += ["All cited line numbers are within file bounds.", ""]

    # ----- Dimension 3
    out += [
        "## 3. Routine declaration presence",
        "",
        f"- Routine candidates checked: {dim3.total} (top backtick "
        "identifiers with routine-hint context)",
        f"- Found in source:           {dim3.pass_count}",
        f"- NOT FOUND:                 {len(dim3.rows)}",
        "",
    ]
    if dim3.rows:
        out += ["### Candidate routine names not found in source", ""]
        out += _table(
            ["Identifier", "Mentions", "First wiki file"],
            [(f"`{n}`", c, f"`{o}`") for n, c, o in dim3.rows],
        )
        out.append("")
    else:
        out += ["All sampled routine candidates resolve in source.", ""]

    # ----- Dimension 4
    out += ["## 4. Parameter-name validity", ""]
    if dim4.total == 0:
        for n in dim4.extra_notes:
            out.append(f"- {n}")
        out.append("")
    else:
        out += [
            f"- Unique fates_* mentions: {dim4.total}",
            f"- Match parameter file:    {dim4.pass_count}",
            f"- NOT IN PARAMETER FILE:   {len(dim4.rows)}",
            "",
        ]
        if dim4.rows:
            out += ["### Wiki-only parameter names (not in param file)", ""]
            out += _table(
                ["Parameter", "Mentions", "First wiki file"],
                [(f"`{n}`", c, f"`{o}`") for n, c, o in dim4.rows],
            )
            out.append("")
        else:
            out += ["All wiki parameter mentions resolve in the param file.",
                    ""]

    # ----- Dimension 5
    out += ["## 5. Module-file presence", ""]
    out += [
        f"- Unique module files mentioned: {dim5.total}",
        f"- Found in source tree:          {dim5.pass_count}",
        f"- NOT FOUND:                     {len(dim5.rows)}",
        "",
    ]
    if dim5.rows:
        out += ["### Module files mentioned in wiki but missing from source",
                ""]
        out += _table(
            ["Module file", "First wiki file"],
            [(f"`{m}`", f"`{o}`") for m, o in dim5.rows],
        )
        out.append("")
    else:
        out += ["All mentioned module files exist in source.", ""]

    # ----- Recommendations
    out += ["---", "", "## Summary recommendations", ""]
    for r in _build_recommendations(verdict, dim1, dim2, dim3, dim4, dim5):
        out.append(f"- {r}")
    out.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out), encoding="utf-8")


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Validate a codebase wiki against the source tree."
    )
    ap.add_argument("--wiki", required=True, type=Path,
                    help="Wiki root directory (recursive .md scan)")
    ap.add_argument("--source", required=True, type=Path,
                    help="Source tree root (recursive .F90 scan)")
    ap.add_argument("--param-file", required=False, type=Path, default=None,
                    help="Optional parameter file (.cdl/.json/.nc) for "
                         "Dimension 4 cross-checking")
    ap.add_argument("--output", required=True, type=Path,
                    help="Path to write Markdown report")
    ap.add_argument("--top-n-routines", type=int, default=50,
                    help="Number of top routine candidates to validate "
                         "(Dimension 3). Default: 50")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    for p, label, required in (
        (args.wiki, "wiki", True),
        (args.source, "source", True),
        (args.param_file, "param-file", False),
    ):
        if required and not p.exists():
            print(f"ERROR: --{label} path not found: {p}", file=sys.stderr)
            return 1
        if (not required) and (p is not None) and (not p.exists()):
            print(f"ERROR: --{label} path not found: {p}", file=sys.stderr)
            return 1

    print(f"Loading wiki:   {args.wiki}")
    corpus = load_wiki(args.wiki)
    print(f"  wiki files: {len(corpus.files)}")

    print(f"Indexing source: {args.source}")
    source = load_source_index(args.source)
    print(f"  .F90 files: {len(source.rel_paths)}")

    print("Extracting citations, modules, parameters, routines...")
    citations = find_citations(corpus.blob)
    modules = find_module_mentions(corpus.blob)
    param_mentions = find_parameter_mentions(corpus.blob)
    routine_candidates = collect_routine_candidates(
        corpus, top_n=args.top_n_routines
    )
    print(f"  citations: {len(citations)}, modules: {len(modules)}, "
          f"param mentions: {len(param_mentions)} unique, "
          f"routine candidates: {len(routine_candidates)}")

    print("Dimension 1: file-citation existence...")
    dim1 = validate_file_citations(citations, source, corpus)
    print(f"  {dim1.pass_count}/{dim1.total}  ({dim1.status})")

    print("Dimension 2: line-bound validity...")
    dim2 = validate_line_bounds(citations, source, args.source, corpus)
    print(f"  {dim2.pass_count}/{dim2.total}  ({dim2.status})")

    print("Dimension 3: routine declaration presence...")
    dim3 = validate_routines(routine_candidates, source, args.source, corpus)
    print(f"  {dim3.pass_count}/{dim3.total}  ({dim3.status})")

    print("Dimension 4: parameter-name validity...")
    dim4 = validate_parameters(param_mentions, args.param_file, corpus)
    if dim4.total > 0:
        print(f"  {dim4.pass_count}/{dim4.total}  ({dim4.status})")
    else:
        print("  (skipped, no --param-file)")

    print("Dimension 5: module-file presence...")
    dim5 = validate_module_files(modules, source, corpus)
    print(f"  {dim5.pass_count}/{dim5.total}  ({dim5.status})")

    print(f"Writing report: {args.output}")
    write_report(args.output, args.wiki, args.source, args.param_file,
                 corpus, source, citations, modules, param_mentions,
                 dim1, dim2, dim3, dim4, dim5)
    verdict = overall_verdict([dim1, dim2, dim3, dim4, dim5])
    print(f"Done. Overall verdict: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
