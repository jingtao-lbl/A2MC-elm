#!/usr/bin/env python3
"""
audit_param_list_against_api.py - One-off utility to find renamed/removed
FATES parameters when migrating a Phase 0 parameter list between api epochs.

Use case (the one that motivated this in v2.100):
    Kougarok's FATES_Parameter_List_Full_162_Finalized.txt contains
    parameter names from the api-25 / api-31 era. Some are renamed or
    removed in api-43-1 (e.g., fates_turnover_leaf was split into
    fates_turnover_leaf_canopy + fates_turnover_leaf_ustory). A user
    running Phase 0 against api-43-1 with the old list gets per-case
    "Parameter X not found" errors at materialization time. This script
    catches all the missing names up front in one pass.

What it does:
    1. Parse the parameter list via tools.modify_fates_parameters.build_param_lookup
    2. Load the target api JSON parameter file (e.g., api-43-1's fates_params_default.json)
    3. For each unique param name in the list, check if it exists in the JSON
    4. For each missing name, fuzzy-suggest matching api names (longest common prefix)
    5. Emit a Markdown audit report

Output:
    A Markdown report listing:
      - PRESENT params (count)
      - MISSING params with suggested replacements (count)
      - SUMMARY line for quick-scan triage

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import json
import sys
from difflib import get_close_matches
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.modify_fates_parameters import build_param_lookup


def load_api_params(json_path: Path) -> dict:
    """Load the parameter dict from a FATES api JSON file."""
    with open(json_path) as f:
        doc = json.load(f)
    return doc.get("parameters", doc)  # graceful for older shapes


def suggest_replacements(missing_name: str, available_names: list[str],
                          n: int = 5, cutoff: float = 0.6) -> list[str]:
    """Return up to n api param names most similar to missing_name."""
    # difflib's get_close_matches is OK for typo-style matches. For
    # api renames like `fates_turnover_leaf` -> `fates_turnover_leaf_canopy`,
    # the longest-common-prefix matches well.
    return get_close_matches(missing_name, available_names, n=n, cutoff=cutoff)


def audit(param_list_file: Path, api_json_file: Path) -> dict:
    """Run the audit. Returns a result dict suitable for rendering."""
    lookup = build_param_lookup(param_list_file)
    # build_param_lookup keys by shorthand; values have 'fates_name' field
    unique_names = sorted({v["fates_name"] for v in lookup.values()})

    api_params = load_api_params(api_json_file)
    available = sorted(api_params.keys())
    available_set = set(available)

    present = [n for n in unique_names if n in available_set]
    missing = [n for n in unique_names if n not in available_set]

    suggestions = {
        m: suggest_replacements(m, available) for m in missing
    }

    return {
        "param_list_file": str(param_list_file),
        "api_json_file": str(api_json_file),
        "total_unique_params": len(unique_names),
        "total_in_list_file": len(lookup),
        "present": present,
        "missing": missing,
        "suggestions": suggestions,
        "api_param_count": len(available),
    }


def render_report(result: dict) -> str:
    """Render the audit result as Markdown."""
    n_total = result["total_unique_params"]
    n_present = len(result["present"])
    n_missing = len(result["missing"])

    lines = []
    lines.append("# FATES Parameter List API-Migration Audit")
    lines.append("")
    lines.append(f"- **Parameter list:** `{result['param_list_file']}`")
    lines.append(f"- **Target api JSON:** `{result['api_json_file']}`")
    lines.append(f"- **Param list entries:** {result['total_in_list_file']}"
                 f" (across all PFTs)")
    lines.append(f"- **Unique parameter names in list:** {n_total}")
    lines.append(f"- **Parameters available in api JSON:** {result['api_param_count']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- ✅ Present in api: **{n_present} / {n_total}**")
    lines.append(f"- ❌ Missing from api: **{n_missing} / {n_total}**")
    lines.append("")
    if n_missing == 0:
        lines.append("**No migration needed — every parameter in the list "
                     "is present in the target api.**")
        return "\n".join(lines) + "\n"

    lines.append("---")
    lines.append("")
    lines.append("## Missing parameters with suggested replacements")
    lines.append("")
    lines.append("Each row shows a parameter that's in your list but NOT in "
                 "the target api JSON. The \"Suggestions\" column shows up to "
                 "5 api param names with similar spelling — review each, since "
                 "some renames split one old param into multiple new ones (e.g., "
                 "canopy/understory variants).")
    lines.append("")
    lines.append("| # | Missing param | Suggested replacement(s) |")
    lines.append("|---|---|---|")
    for i, name in enumerate(result["missing"], 1):
        sugg = result["suggestions"].get(name) or []
        cell = "<br>".join(f"`{s}`" for s in sugg) if sugg \
            else "_(none; check FATES wiki for rename history)_"
        lines.append(f"| {i} | `{name}` | {cell} |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Migration approach")
    lines.append("")
    lines.append("1. For each missing param, decide:")
    lines.append("   - **Same semantic intent kept**: replace the name in the list")
    lines.append("     (e.g., `fates_turnover_leaf` → `fates_turnover_leaf_canopy`).")
    lines.append("   - **Split into multiple**: add one entry per replacement")
    lines.append("     (e.g., separate `_canopy` and `_ustory` variants if the")
    lines.append("     old semantics need both).")
    lines.append("   - **Removed without replacement**: drop the entry; document")
    lines.append("     the decision in the param-list file's preamble.")
    lines.append("")
    lines.append("2. Re-run this audit; expect zero missing.")
    lines.append("3. Run the v2.100 Phase 0 pipeline:")
    lines.append("   ```bash")
    lines.append("   python phases/phase0_design/create_parameter_sample.py "
                 "--method morris --trajectories 30 \\")
    lines.append("       --param-list-file <updated-list> \\")
    lines.append("       --output-matrix samples.txt")
    lines.append("   python phases/phase0_design/generate_parameter_files.py "
                 "# materializer auto-detects JSON")
    lines.append("   ```")
    lines.append("")

    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Audit a FATES Phase 0 parameter list against a target "
                    "api JSON file. Lists missing params + suggests renames."
    )
    p.add_argument("--param-list", type=Path, required=True,
                   help="Path to the parameter list file (e.g., "
                        "use_cases/<site>/parameters/FATES_Parameter_List_*.txt)")
    p.add_argument("--api-json", type=Path, required=True,
                   help="Path to the target api JSON file (e.g., "
                        "fates_params_default.json from an api-43-1 checkout)")
    p.add_argument("--output", type=Path, default=None,
                   help="Output Markdown report path (default: stdout)")
    args = p.parse_args(argv)

    for label, path in [("param-list", args.param_list),
                        ("api-json", args.api_json)]:
        if not path.is_file():
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            return 2

    result = audit(args.param_list, args.api_json)
    report = render_report(result)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Audit report written to: {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(report)

    # Exit code reflects audit verdict
    return 0 if not result["missing"] else 1


if __name__ == "__main__":
    sys.exit(main())
