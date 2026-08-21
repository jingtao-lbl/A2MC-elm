#!/usr/bin/env python3
"""Print the number of sampled parameters (Morris/Sobol columns) in a parameter list.

The **authoritative** source for `A2MC_N_PARAMS` — derive it from the list, never hardcode it, so it
stays in sync as the list changes (and the ensemble *size* is then computed by scheme in
`calculate_ensemble_size()`, which is what varies for Morris trajectories vs Sobol vs LHS).

Handles both the docs/37 explicit-column CSV (via `load_param_spec`) and the legacy shorthand `.txt`.

    python tools/count_param_list.py <param_list_file>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _is_new_format(path):
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Accept either name column: `param_name` (canonical — this branch calibrates ELM
            # with OR without FATES) or the legacy `fates_name`. Sniffing only `fates_name`
            # made an ELM-only list fall through to the legacy .txt counter and report 0.
            return "," in line and line.split(",")[0].strip() in ("param_name", "fates_name")
    return False


def count_params(path):
    if _is_new_format(path):
        from tools.param_spec import load_param_spec
        return len(load_param_spec(path))
    # legacy .txt: count numbered data rows (No<TAB>fates_name<TAB>shorthand<TAB>...)
    n = 0
    for line in open(path):
        line = line.strip()
        if not line or line.startswith(("#", "=")):
            continue
        first = line.split("\t")[0] if "\t" in line else line.split()[0] if line.split() else ""
        try:
            int(first)
            n += 1
        except ValueError:
            pass
    return n


# Suffixes marking a param list kept for provenance but no longer in use. A retired list must
# never be picked as "the active one" — on 2026-07-28 two lists were renamed to `_NotUsed` /
# `_Old`, and a `sorted(glob(...))[0]` in two test modules silently began resolving to the
# RETIRED para168 file. The tests kept passing their structural checks against the wrong list
# and only their hardcoded count gave it away.
# NOTE: `resolve_param_list` + `_RETIRED_MARKERS` lived here until 2026-08-19.
# They guessed the active list ("newest paraNNN minus a blocklist") for two test
# fixtures; production always had the answer in the site config's
# A2MC_PARAM_LIST_FILE. The guess picked a RETIRED list once and an in-progress
# `_candidate` list once (killing collection for all 370 tests for ten days), and a
# blocklist can only enumerate names already retired. Tests now read the same
# authority production reads — see tests/helpers.py::active_param_list.

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: count_param_list.py <param_list_file>")
    print(count_params(sys.argv[1]))
