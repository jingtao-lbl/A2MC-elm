#!/usr/bin/env python3
"""Tier-2 deterministic smoke harness for the A2MC interactive-agent skill layer.

WHAT THIS IS (and is NOT). The offline (interactive) agent's *behavior* is the harness/
model's job — a human in the loop is the validator there. What A2MC *can* validate
mechanically is its own **skill contracts**:

  * Tier 1 (`tools/check_skill_registry.py`) — STATIC: registry parity + cited paths exist.
  * Tier 2 (THIS script) — RUNTIME: actually run the read-only backing commands the skills
    document and assert exit 0 + sane output. Catches runtime bugs a static check can't —
    e.g. the `inject-knowledge` memory smoke test that documented a `phase=` kwarg the real
    `get_relevant_context()` signature never had (TypeError on copy-paste; 20260617e).
  * Tier 3 (behavioral / trigger-correctness) — DEFERRED by design (needs an LLM judge).

It runs ONLY read-only commands — never the destructive `--rebuild` / wiki-gen / curated-write
paths. Each check is PASS / FAIL / SKIP. SKIP (not FAIL) when an optional dependency is absent
(no `~/a2mc_env`, no built RAG index) so this stays runnable in a bare checkout / CI; only a
genuinely broken documented command FAILs. Exit 0 iff no FAIL.

Run from the repo root (CI / periodic — NOT pre-commit; the RAG checks need Python 3.10 +
a built index):
    python3 tools/smoke_test_skills.py

Author: Jing Tao with Claude
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_SYS = sys.executable                                  # static checks (stdlib only)
PY_A2MC = str(Path.home() / "a2mc_env" / "bin" / "python")  # memory / RAG (Python 3.10 + deps)
# A real curated dir for read-only probes: the active use case if set, else the Kougarok
# reference use case (main's shipped example). Site-agnostic via $A2MC_USE_CASE_DIR.
_UC = os.environ.get("A2MC_USE_CASE_DIR", "").rstrip("/")
CURATED = f"{_UC}/memory/gained_knowledge" if _UC else "use_cases/ELM-FATES_Kougarok/memory/gained_knowledge"
SKIP_RC = 77                                             # an inline snippet signals SKIP with this

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

# ---- inline snippets (run under PY_A2MC). exit 0=ok, 77=skip(dep/index absent), other=fail ----

_MEMORY_SMOKE = f"""
import sys
try:
    from memory.manager import MemoryManager
except Exception as e:
    print("SKIP import:", e); sys.exit({SKIP_RC})
try:
    m = MemoryManager("{CURATED}")
    ctx = m.get_relevant_context(failing_targets=["PFT10_fineroot"])  # NO phase= kwarg (20260617e)
    assert isinstance(ctx, str), "context is not a str"
    print("OK len=%d" % len(ctx))
except TypeError as e:
    print("FAIL signature:", e); sys.exit(1)          # the exact class of bug this guards
except Exception as e:
    print("FAIL:", e); sys.exit(1)
"""

_RAG_SMOKE = f"""
import sys
try:
    from rag import HybridRetriever
except Exception as e:
    print("SKIP import (no rag deps):", e); sys.exit({SKIP_RC})
try:
    r = HybridRetriever(auto_build=False)             # load existing index; never build
except Exception as e:
    print("SKIP load (no built index / env):", e); sys.exit({SKIP_RC})
try:
    res = r.find_parameters_for_output("FATES_LEAFC")
    stats = r.get_stats()
    assert res is not None and len(res) >= 1, "no params returned for FATES_LEAFC"
    assert isinstance(stats, dict) and stats, "get_stats() empty/not a dict"
    print("OK params=%d stats_keys=%d" % (len(res), len(stats)))
except Exception as e:
    print("FAIL:", e); sys.exit(1)
"""

# ---- check table: (name, group, interp, argv, want_substr) ----
# interp: "sys" = system python3 (stdlib-only checks); "a2mc" = ~/a2mc_env (memory/RAG).
CHECKS = [
    # Tier-1 gates, re-run here so one command covers both tiers
    ("check_skill_registry", "registry", "sys", ["tools/check_skill_registry.py"], "clean"),
    # offline-state invariant checker (the state analog of check_skill_registry) — exit 0 iff the
    # workflow_state_offline_r*.json the driver loads is valid (or none exists yet).
    ("check_workflow_state_offline", "registry", "sys", ["tools/check_workflow_state_offline.py"], None),
    # validator CLIs. codebase_wiki_validator is stdlib-only (runs anywhere); yaml_wiki_validator
    # needs PyYAML and rag_diff needs networkx, so those two run under ~/a2mc_env.
    ("codebase_wiki_validator --help", "validators", "sys", ["tools/codebase_wiki_validator.py", "--help"], "usage"),
    ("yaml_wiki_validator --help", "validators", "a2mc", ["tools/yaml_wiki_validator.py", "--help"], "usage"),
    ("rag_diff --help", "validators", "a2mc", ["tools/rag_diff.py", "--help"], "usage"),
    # curate-knowledge backing command (read-only list). --memory-dir is a GLOBAL arg → before subcommand.
    ("review_pending_knowledge list", "curate", "sys",
     ["tools/review_pending_knowledge.py", "--memory-dir", CURATED, "list"], None),
    # calibration-loop backing commands — argparse `--help` smoke. Can't run these for real (they need
    # HPC data / a live ensemble), but `--help` proves the module IMPORTS and its arg spec parses — it
    # catches the whole class of import/rename/dependency + unescaped-`%`-in-help breakage the static
    # check can't (found modify_fates_parameters' `40%`→`% f` argparse crash, 20260715). All need a2mc_env.
    ("extract_sensitivity_outputs --help", "calibration", "a2mc", ["phases/phase1_exploration/extract_sensitivity_outputs.py", "--help"], "usage"),
    ("morris_sensitivity_analysis --help", "calibration", "a2mc", ["phases/phase1_exploration/morris_sensitivity_analysis.py", "--help"], "usage"),
    ("screen_ensemble --help", "calibration", "a2mc", ["phases/phase2_screening/screen_ensemble.py", "--help"], "usage"),
    ("plot_ensemble_cases --help", "calibration", "a2mc", ["tools/plot_ensemble_cases.py", "--help"], "usage"),
    ("extract_and_plot_selected_cases --help", "calibration", "a2mc", ["tools/extract_and_plot_selected_cases.py", "--help"], "usage"),
    ("extract_monthly_variables_FATES --help", "calibration", "a2mc", ["tools/extract_monthly_variables_FATES.py", "--help"], "usage"),
    ("diagnose_ensemble_status --help", "calibration", "a2mc", ["tools/diagnose_ensemble_status.py", "--help"], "usage"),
    ("modify_fates_parameters --help", "calibration", "a2mc", ["tools/modify_fates_parameters.py", "--help"], "usage"),
    ("submit_phase0 --help", "calibration", "a2mc", ["phases/phase0_design/submit_phase0.py", "--help"], "usage"),
    ("validate_submission_plan --help", "calibration", "a2mc", ["tools/validate_submission_plan.py", "--help"], "usage"),
    # memory smoke — the get_relevant_context regression (inject-knowledge / curate-knowledge)
    ("memory get_relevant_context", "memory", "a2mc", ["-c", _MEMORY_SMOKE], "OK"),
    # RAG/GraphRAG — needs Python 3.10 + a built index; SKIPs cleanly otherwise
    ("build_rag_index --help", "rag", "a2mc", ["scripts/build_rag_index.py", "--help"], "usage"),
    ("rag find_parameters_for_output + get_stats", "rag", "a2mc", ["-c", _RAG_SMOKE], "OK"),
]


def interp_path(kind):
    if kind == "sys":
        return PY_SYS
    if kind == "a2mc":
        return PY_A2MC if Path(PY_A2MC).exists() else None
    raise ValueError(kind)


def run_check(name, group, interp, argv, want):
    py = interp_path(interp)
    if py is None:
        return SKIP, f"interpreter absent ({interp}: {PY_A2MC})"
    try:
        p = subprocess.run([py] + argv, cwd=ROOT, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return FAIL, "timeout (>180s)"
    out, err = p.stdout.strip(), p.stderr.strip()
    def last(s):
        return s.splitlines()[-1] if s else ""
    if p.returncode == SKIP_RC:                          # inline snippet asked to skip
        return SKIP, last(out) or last(err)
    if p.returncode != 0:                                # show stderr (where the error is)
        return FAIL, f"exit {p.returncode}: {last(err) or last(out) or '(no output)'}"
    if want and want.lower() not in out.lower():         # match on stdout only (stderr is warning noise)
        return FAIL, f"exit 0 but missing expected '{want}' in stdout: {last(out) or last(err)}"
    return PASS, last(out) or "(ok)"


def main():
    print(f"A2MC Tier-2 skill smoke harness — repo {ROOT.name}")
    print(f"  system py : {PY_SYS}")
    print(f"  a2mc   py : {PY_A2MC} {'(present)' if Path(PY_A2MC).exists() else '(ABSENT — RAG/memory SKIP)'}")
    print()
    results = []
    for name, group, interp, argv, want in CHECKS:
        status, detail = run_check(name, group, interp, argv, want)
        results.append((status, group, name, detail))
        mark = {PASS: "✔", FAIL: "✘", SKIP: "·"}[status]
        print(f"  {mark} [{status}] {name:<42s} {detail}")

    n_pass = sum(1 for r in results if r[0] == PASS)
    n_fail = sum(1 for r in results if r[0] == FAIL)
    n_skip = sum(1 for r in results if r[0] == SKIP)
    print()
    print(f"{n_pass} passed, {n_fail} failed, {n_skip} skipped (of {len(results)})")
    if n_fail:
        print("\n✘ smoke harness FAILED — a documented read-only skill command is broken:")
        for status, group, name, detail in results:
            if status == FAIL:
                print(f"  - [{group}] {name}: {detail}")
        return 1
    print("✔ smoke harness clean — every runnable documented command exits 0 with sane output")
    return 0


if __name__ == "__main__":
    sys.exit(main())
