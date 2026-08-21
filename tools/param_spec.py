#!/usr/bin/env python3
"""
Canonical FATES parameter-list loader (docs/37 — parameter-naming refactor).

THE single source of truth for reading a parameter list. Replaces the scattered
shorthand parsers (`build_param_lookup`, `resolve_parameter_name`, `parse_parameter_list`,
`load_parameter_bounds`, the `reasoning/` regex/token extractors, ...).

Param-list format (CSV, header row):
    param_name,pft,organ,lower,upper,default,description
  - param_name : the parameter name EXACTLY as it appears in the model's parameter file or
                 namelist. This branch calibrates ELM **with or without FATES**, so the column
                 is not FATES-specific: a FATES case writes `fates_stoich_nitr`, an ELM-only
                 case writes an ELM parameter/namelist name. **The legacy header `fates_name`
                 is still accepted** so existing lists load unchanged, and `ParamSpec.fates_name`
                 remains a read alias for `param_name`.
  - pft        : site PFT id (int); blank/`-`/`0` = a global/scalar param.
  - organ      : OPTIONAL, and a FATES/PARTEH concept — the organ slot(s) this row's single
                 sampled value is written into: blank (non-organ), a single id
                 (1=leaf,2=fineroot,3=sapwood,4=structure), or a `|`-list like `1|2` (one value
                 broadcast to several organs, e.g. retrans). Omit the column entirely for an
                 ELM-only list; absent => no row is organ-dimensioned.
  - lower,upper : floats.
  - default : the **operative** default (the value used when a param isn't otherwise set). The column may
                 be named `default_api43` (preferred — the api-43 base value) or plain `default`; the loader
                 reads whichever is present.
  - description: free text.

Optional extra columns are ignored by the loader. `default_api31` (if present) is a **reference-only**
column holding the legacy api-31 list default (PFT-remapped 7→10/9→11/10→12) for side-by-side drift
comparison — blank where there is no api-31 equivalent (migrated/split or new names). It is NOT read.

Invariant (docs/37 §3.1): **one row = one Morris matrix column = one independently-sampled
value.** The `organ` field never adds rows/columns — it only lists which organ slot(s) the
value is written to (usually one; retrans broadcasts to [1,2]).
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:  # normal package import
    from tools.param_transforms import (
        DERIVED_TRANSFORMS, group_for_coord, is_virtual_coord, native_targets,
    )
except ImportError:  # when run directly as `python tools/param_spec.py`
    from param_transforms import (
        DERIVED_TRANSFORMS, group_for_coord, is_virtual_coord, native_targets,
    )

# FATES fates_plant_organs id convention (1-based).
ORGAN_NAME_TO_INDEX = {"leaf": 1, "fineroot": 2, "sapwood": 3, "structure": 4}
ORGAN_INDEX_TO_NAME = {v: k for k, v in ORGAN_NAME_TO_INDEX.items()}

_PREFIXES = ("fates_cnp_eca_", "fates_cnp_", "fates_alloc_", "fates_leaf_", "fates_")


@dataclass
class ParamSpec:
    """One parameter-list row = one independently-sampled Morris dimension."""
    param_name: str          # the parameter name EXACTLY as it appears in the model's parameter
                             # file or namelist. Named `param_name`, not `fates_name`, because
                             # this branch calibrates ELM **with or without FATES**: an ELM-only
                             # case (BGC / soil / snow parameters) has no FATES parameters at
                             # all. `fates_name` remains as a read alias below so existing code
                             # and existing param-list CSVs keep working unchanged.
    pft: int                 # 0 = global/scalar
    organ: List[int]         # [] = non-organ; [1]=leaf; [1,2]=broadcast (retrans).
                             # A FATES/PARTEH concept — always [] for an ELM-only list.
    lower: float
    upper: float
    default: float
    description: str = ""
    row_index: int = -1      # 0-based order == Morris matrix column index
    is_virtual: bool = False           # a derived-param virtual sampling coordinate (tools/param_transforms)
    transform_group: Optional[str] = None  # the derived group this coord belongs to (if is_virtual)

    @property
    def fates_name(self) -> str:
        """Backward-compatible alias for `param_name`.

        ~18 modules and the existing Kougarok param lists read `fates_name`. Keeping it as a
        read alias means generalizing the column cost one file instead of a repo-wide rename
        (CLAUDE.md rule 3, surgical changes). Prefer `param_name` in new code.
        """
        return self.param_name

    @property
    def canonical_id(self) -> str:
        """Deterministic, unique string id (SALib var name / Morris column / μ* key / ledger).
        Never parsed back for meaning — look it up in the loaded spec list instead."""
        cid = self.fates_name
        if self.pft:
            cid += f"#p{self.pft}"
        if self.organ:
            cid += "#o" + "-".join(str(o) for o in self.organ)
        return cid

    @property
    def is_organ(self) -> bool:
        return bool(self.organ)

    @property
    def short_label(self) -> str:
        """Display-ONLY short label (e.g. for sensitivity-plot axes). NOT a key."""
        base = self.fates_name
        for pre in _PREFIXES:
            if base.startswith(pre):
                base = base[len(pre):]
                break
        lbl = base
        if self.organ:
            lbl += "_" + "_".join(ORGAN_INDEX_TO_NAME.get(o, str(o)) for o in self.organ)
        if self.pft:
            lbl += f"_{self.pft}"
        return lbl

    def organ_slots(self) -> List[Optional[int]]:
        """Organ slot(s) to write this value into ([None] for a non-organ param)."""
        return list(self.organ) if self.organ else [None]


def _parse_pft(s: str) -> int:
    s = (s or "").strip()
    if s in ("", "-", "none", "None"):
        return 0
    return int(s)


def _parse_organ(s: str) -> List[int]:
    s = (s or "").strip()
    if s in ("", "-", "0", "none", "None"):
        return []
    return [int(x) for x in s.replace(",", "|").split("|") if x.strip()]


def load_param_spec(param_list_file) -> List[ParamSpec]:
    """Load a param-list CSV into an ordered list of ParamSpec (order == Morris columns)."""
    p = Path(param_list_file)
    if not p.exists():
        raise FileNotFoundError(f"Parameter list file not found: {p}")

    specs: List[ParamSpec] = []
    with open(p, newline="") as f:
        # Skip a leading `#` comment block before the header row. count_param_list's format
        # sniffer already skips them, so without this a commented list COUNTS fine and then
        # fails to LOAD — the two tools disagreed about the same file. Row-level `#` lines are
        # skipped separately below.
        lines = [ln for ln in f]
        start = 0
        for i, ln in enumerate(lines):
            if ln.strip() and not ln.lstrip().startswith("#"):
                start = i
                break
        reader = csv.DictReader(lines[start:])
        cols = {(c or "").strip() for c in (reader.fieldnames or [])}
        required = {"pft", "lower", "upper"}
        # Name column: `param_name` (canonical — this branch calibrates ELM with OR without
        # FATES) or legacy `fates_name`. Same alias pattern as the default column below.
        name_col = next((c for c in ("param_name", "fates_name") if c in cols), None)
        # `organ` is a FATES/PARTEH concept. Optional, so an ELM-only list need not carry an
        # all-blank column; absent => no row is organ-dimensioned.
        organ_col = "organ" if "organ" in cols else None
        # operative default: `default_api43` (preferred, post-rename) or plain `default`.
        # `default_api31` is reference-only and never read.
        default_col = next((c for c in ("default_api43", "default") if c in cols), None)
        if not required.issubset(cols) or name_col is None or default_col is None:
            raise ValueError(
                f"CSV must have a 'param_name'/'fates_name' column, {sorted(required)}, and a "
                f"'default_api43'/'default' column; got {sorted(cols)}")
        for row in reader:
            fates = (row[name_col] or "").strip()
            if not fates or fates.startswith("#"):
                continue
            dval = (row.get(default_col) or "").strip()
            if dval == "":
                raise ValueError(
                    f"{p}: row '{fates}' pft={row.get('pft')} has an empty {default_col} — every "
                    f"parameter needs an operative default")
            bounds = {}
            for col in ("lower", "upper"):
                raw = (row.get(col) or "").strip()
                if raw == "":
                    raise ValueError(
                        f"{p}: row '{fates}' pft={row.get('pft')} has an empty {col} bound — "
                        f"every parameter needs a numeric {col}. A list still being assembled "
                        f"(bounds not yet justified) is not loadable; finish the bound, or keep "
                        f"the list out of the resolution path.")
                try:
                    bounds[col] = float(raw)
                except ValueError:
                    raise ValueError(
                        f"{p}: row '{fates}' pft={row.get('pft')} has a non-numeric {col} "
                        f"bound {raw!r}") from None
            spec = ParamSpec(
                param_name=fates,
                pft=_parse_pft(row["pft"]),
                organ=_parse_organ(row[organ_col]) if organ_col else [],
                lower=bounds["lower"],
                upper=bounds["upper"],
                default=float(dval),
                description=(row.get("description") or "").strip(),
                row_index=len(specs),
            )
            if is_virtual_coord(spec.fates_name):
                spec.is_virtual = True
                spec.transform_group = group_for_coord(spec.fates_name)
                if spec.organ:
                    raise ValueError(
                        f"virtual coord '{spec.fates_name}' (pft{spec.pft}) must have no organ; got {spec.organ}")
            specs.append(spec)

    ids = [s.canonical_id for s in specs]
    seen, dupes = set(), set()
    for i in ids:
        (dupes if i in seen else seen).add(i)
    if dupes:
        raise ValueError(f"Duplicate canonical ids in {p}: {sorted(dupes)}")

    _check_derived_groups(specs, p)
    return specs


def _check_derived_groups(specs: List[ParamSpec], p) -> None:
    """Derived-parameter invariants (only fire when virtual coords are actually present):
      - every group is complete per PFT (all its coords present) — all-or-nothing;
      - no native write-target of an active group also appears as its own direct row for that PFT
        (that would write the same param twice / ambiguously)."""
    present = defaultdict(set)         # (group, pft) -> {coord names present}
    native_by_pft = defaultdict(set)   # pft -> {direct (non-virtual) fates_names}
    for s in specs:
        if s.is_virtual:
            present[(s.transform_group, s.pft)].add(s.fates_name)
        else:
            native_by_pft[s.pft].add(s.fates_name)
    for (group, pft), names in present.items():
        t = DERIVED_TRANSFORMS[group]
        required = set(t.coords)
        if names != required:
            raise ValueError(
                f"{p}: derived group '{group}' incomplete for pft{pft}: "
                f"missing {sorted(required - names)} (have {sorted(names)}) — groups are all-or-nothing")
        conflict = native_by_pft.get(pft, set()) & set(t.native_names())
        if conflict:
            raise ValueError(
                f"{p}: derived group '{group}' pft{pft} writes {sorted(conflict)}, "
                f"but those also appear as direct param-list rows — remove the direct rows")


if __name__ == "__main__":
    import sys
    specs = load_param_spec(sys.argv[1])
    print(f"{len(specs)} params, {len({s.fates_name for s in specs})} unique fates_names")
    for s in specs[:8]:
        print(f"  {s.canonical_id:42s} organ={s.organ or '-'} label={s.short_label}")
