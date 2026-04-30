#!/usr/bin/env python3
"""
cross_milestone_validator.py - Compare applies_in: tagging across milestones.

As profiles proliferate (each milestone = a separate frozen YAML), drift
between them becomes a real risk. A user updates the canonical YAML and
forgets to copy applies_in: tags to a milestone YAML, OR the milestone
gets out-of-date relative to canonical curation work.

This validator compares the applies_in: blocks for every parameter and
mechanism that appears in TWO OR MORE milestone YAMLs and flags
disagreements. The underlying physics shouldn't change with API version,
so the same parameter should have the same applies_in: across milestones.

Three categories:

    (a) Parameter applies_in: drift — same parameter tagged differently
        across milestone YAMLs.
    (b) Mechanism applies_in: drift — same mechanism tagged differently.
    (c) Coverage drift — parameter present in one milestone YAML but
        completely missing from another (could be intentional API churn
        or a missed sync).

Usage
-----
    python tools/cross_milestone_validator.py \\
        --output docs/a2mc_reference/cross_milestone_validation.md

Compares all milestones registered in rag/milestones.json. The canonical
YAML at rag/data/curated_relationships.yaml is treated as a third
'profile' for comparison.

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class DriftRow:
    severity: str  # "OK" | "WARN" | "DRIFT"
    entity: str
    profiles: Dict[str, Dict]  # profile_name -> applies_in dict (or None)
    note: str = ""


@dataclass
class CrossMilestoneReport:
    profiles: List[str] = field(default_factory=list)
    parameter_rows: List[DriftRow] = field(default_factory=list)
    mechanism_rows: List[DriftRow] = field(default_factory=list)
    output_rows: List[DriftRow] = field(default_factory=list)

    @property
    def n_drift(self) -> int:
        return sum(1 for rows in (self.parameter_rows, self.mechanism_rows,
                                   self.output_rows)
                   for r in rows if r.severity == "DRIFT")

    @property
    def n_warn(self) -> int:
        return sum(1 for rows in (self.parameter_rows, self.mechanism_rows,
                                   self.output_rows)
                   for r in rows if r.severity == "WARN")

    @property
    def verdict(self) -> str:
        if self.n_drift > 0:
            return "Red"
        if self.n_warn > 0:
            return "Yellow"
        return "Green"


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _normalize_applies_in(d: Optional[Dict]) -> Optional[Dict]:
    """Normalize applies_in for comparison: sort lists, lowercase strings.

    Returns None if d is None. Two applies_in blocks compare equal if their
    normalized forms are equal.
    """
    if not d:
        return None
    out = {}
    for axis, values in d.items():
        if isinstance(values, list):
            # Normalize: sort + stringify
            out[axis] = sorted(str(v).lower() if isinstance(v, str) else v
                               for v in values)
        else:
            out[axis] = values
    return out


def _collect_yamls(include_legacy: bool = False) -> Dict[str, Path]:
    """Return {profile_name: yaml_path} for canonical + active milestones.

    Legacy milestones (info.legacy == True) are skipped by default. They're
    typically frozen pre-Phase-B snapshots (e.g., api-31-0 for Kougarok
    manuscript reproducibility) and their drift from canonical is by design.
    Use ``include_legacy=True`` to compare them anyway.
    """
    profiles = {"canonical": REPO_ROOT / "rag" / "data" / "curated_relationships.yaml"}
    milestones_path = REPO_ROOT / "rag" / "milestones.json"
    if milestones_path.exists():
        ms = json.loads(milestones_path.read_text())
        for name, info in ms.get("milestones", {}).items():
            if not include_legacy and info.get("legacy", False):
                continue
            yaml_path = REPO_ROOT / info.get("curated_yaml_path", "")
            if yaml_path.exists():
                profiles[name] = yaml_path
    return profiles


# =============================================================================
# Comparison logic
# =============================================================================

def compare_section(
    section: str, yamls: Dict[str, dict],
) -> List[DriftRow]:
    """Compare applies_in across milestones for a YAML section (parameters/mechanisms/outputs).

    For each entity name appearing in ANY profile:
        - If only in some profiles → coverage drift (WARN)
        - If in all profiles with same applies_in → OK (skip)
        - If in all profiles with different applies_in → DRIFT
    """
    # Collect all entity names across profiles
    all_entities: Set[str] = set()
    for prof_name, data in yamls.items():
        all_entities.update((data.get(section) or {}).keys())

    rows = []
    for entity in sorted(all_entities):
        # Per profile: entity_data dict, or None if absent
        per_profile = {}
        present_in = []
        for prof_name, data in yamls.items():
            ent = (data.get(section) or {}).get(entity)
            if ent is None:
                per_profile[prof_name] = None
            else:
                per_profile[prof_name] = ent.get("applies_in")
                present_in.append(prof_name)

        # All-absent skip (shouldn't happen since entity is in all_entities)
        if not present_in:
            continue

        # Coverage drift: entity in some profiles but not all
        if len(present_in) < len(yamls):
            missing = [p for p in yamls if p not in present_in]
            rows.append(DriftRow(
                severity="WARN",
                entity=entity,
                profiles=per_profile,
                note=f"Present in {present_in}; missing from {missing}",
            ))
            continue

        # Compare applies_in across all profiles
        normalized = {p: _normalize_applies_in(per_profile[p])
                      for p in present_in}
        # Use canonical as reference if present, else first profile
        ref = normalized.get("canonical") if "canonical" in normalized else normalized[present_in[0]]
        all_same = all(normalized[p] == ref for p in present_in)
        if all_same:
            rows.append(DriftRow(
                severity="OK", entity=entity, profiles=per_profile,
            ))
        else:
            # Find which profiles differ
            differ = [p for p in present_in if normalized[p] != ref]
            rows.append(DriftRow(
                severity="DRIFT", entity=entity, profiles=per_profile,
                note=f"applies_in differs between profiles: {differ} differ from canonical",
            ))

    return rows


def run_validation(include_legacy: bool = False) -> CrossMilestoneReport:
    yamls_paths = _collect_yamls(include_legacy=include_legacy)
    if len(yamls_paths) < 2:
        raise RuntimeError(
            f"Need at least 2 milestone YAMLs to compare; got {len(yamls_paths)}: "
            f"{list(yamls_paths.keys())}. "
            "(Legacy milestones excluded by default; pass --include-legacy to override.)"
        )

    legacy_note = " (excl. legacy)" if not include_legacy else " (incl. legacy)"
    print(f"Cross-milestone validator{legacy_note}")
    yamls = {}
    for name, path in yamls_paths.items():
        yamls[name] = _load_yaml(path)
        print(f"  {name}: {path.name}")

    report = CrossMilestoneReport(profiles=list(yamls_paths.keys()))

    print()
    print("Comparing parameters...")
    report.parameter_rows = compare_section("parameters", yamls)
    n_drift = sum(1 for r in report.parameter_rows if r.severity == "DRIFT")
    n_warn = sum(1 for r in report.parameter_rows if r.severity == "WARN")
    n_ok = sum(1 for r in report.parameter_rows if r.severity == "OK")
    print(f"  {n_ok} OK, {n_warn} WARN (coverage drift), {n_drift} DRIFT (applies_in mismatch)")

    print("Comparing mechanisms...")
    report.mechanism_rows = compare_section("mechanisms", yamls)
    n_drift = sum(1 for r in report.mechanism_rows if r.severity == "DRIFT")
    n_warn = sum(1 for r in report.mechanism_rows if r.severity == "WARN")
    n_ok = sum(1 for r in report.mechanism_rows if r.severity == "OK")
    print(f"  {n_ok} OK, {n_warn} WARN, {n_drift} DRIFT")

    print("Comparing outputs...")
    report.output_rows = compare_section("outputs", yamls)
    n_drift = sum(1 for r in report.output_rows if r.severity == "DRIFT")
    n_warn = sum(1 for r in report.output_rows if r.severity == "WARN")
    n_ok = sum(1 for r in report.output_rows if r.severity == "OK")
    print(f"  {n_ok} OK, {n_warn} WARN, {n_drift} DRIFT")

    print(f"\nVerdict: {report.verdict}  ({report.n_drift} drift, {report.n_warn} coverage warnings)")
    return report


def write_report(report: CrossMilestoneReport, out_path: Path) -> None:
    lines = [
        f"# Cross-Milestone Consistency Validation",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"**Profiles compared:** {', '.join(report.profiles)}",
        f"**Verdict:** {report.verdict}",
        f"  - DRIFT (applies_in mismatch): {report.n_drift}",
        f"  - WARN (coverage drift): {report.n_warn}",
        "",
    ]

    for section, rows in [
        ("Parameters", report.parameter_rows),
        ("Mechanisms", report.mechanism_rows),
        ("Outputs", report.output_rows),
    ]:
        n_drift = sum(1 for r in rows if r.severity == "DRIFT")
        n_warn = sum(1 for r in rows if r.severity == "WARN")
        n_ok = sum(1 for r in rows if r.severity == "OK")
        lines.append(f"## {section} ({n_ok} OK, {n_warn} WARN, {n_drift} DRIFT)")
        lines.append("")

        # DRIFT rows first, then WARN
        priority_rows = [r for r in rows if r.severity == "DRIFT"] + \
                        [r for r in rows if r.severity == "WARN"]
        if priority_rows:
            lines.append("| Entity | Severity | Detail |")
            lines.append("|---|---|---|")
            for r in priority_rows[:50]:
                detail = r.note
                if r.severity == "DRIFT":
                    # Show per-profile applies_in for clarity
                    detail += " — " + ", ".join(
                        f"{p}={r.profiles[p]}" for p in r.profiles
                        if r.profiles[p] is not None
                    )
                # Truncate long detail
                if len(detail) > 200:
                    detail = detail[:200] + "..."
                lines.append(f"| `{r.entity}` | {r.severity} | {detail} |")
            if len(priority_rows) > 50:
                lines.append(f"\n*({len(priority_rows) - 50} additional rows omitted)*")
        else:
            lines.append("All entries match across profiles.")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    print(f"Report: {out_path}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Cross-milestone consistency validator (Validator #3)")
    ap.add_argument("--output", type=Path)
    ap.add_argument("--include-legacy", action="store_true",
                    help="Compare legacy milestones too (frozen pre-Phase-B snapshots; "
                         "their drift is by design — useful for audit)")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_validation(include_legacy=args.include_legacy)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2
    if args.output:
        write_report(report, args.output)
    return 0 if report.verdict != "Red" else 1


if __name__ == "__main__":
    sys.exit(main())
