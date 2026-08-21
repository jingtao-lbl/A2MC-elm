#!/usr/bin/env python3
"""agent_state.py — the offline agent's clone-level master state.

WHY THIS EXISTS, AND WHY IT IS SHAPED THIS WAY
----------------------------------------------
`use_cases/<case>/memory/workflow_state_offline_r{RR}.json` is per-round and
calibration-only, and it rots. Measured 2026-08-21 on this clone: it read
`current_phase: design, experiment_count: 0, updated_at: 2026-08-11` while the
newest phase log was `20260820a_phase5_testing_r01_c01_…` — ten days and five
phases adrift, with a `next_action` naming jobs that had finished a fortnight
earlier. The SessionStart hook surfaces that field as the `► NEXT:` line, so a
stale value is handed to the agent at every session start.

It rots because it STORES DERIVED FACTS. `current_phase`, `calibration_round`
and `experiment_count` are all already encoded in the log stem
`20260820a_phase5_testing_r01_c01_…`; copying them into JSON by hand creates a
second source that drifts silently (`feedback_bind_derived_facts_to_their_source`).
Enforcement cannot fix that — a hook only notices afterwards, and only if read.

So this file splits by DERIVABILITY, not by topic:

  DERIVED, never stored  — setup stage, case list, per-case phase/round/cycle,
                           rounds on disk. Recomputed on every read, so it is
                           structurally incapable of going stale.
  STORED                 — only what no artifact can prove: the approved plan's
                           tasks, decisions and their rationale, open threads
                           not yet written into a log, campaign goals/gates.

Detection DELEGATES to tools/check_setup_ready.py (`_detect_stage`,
`_real_cases`) rather than restating it, following the precedent set by
`.claude/hooks/session-start.py::setup_stage`: "a second copy of 'which stage am
I in' drifts from the first."

Stdlib only, and must work with NOTHING sourced — hooks call it from a bare
shell.

Author: Jing Tao with Claude
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

SCHEMA = "a2mc.agent_state.v1"
_REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_REL = "memory/agent_state.json"
TEMPLATE_REL = "memory/agent_state.template.json"

STATUSES = ("todo", "doing", "done", "dropped")

# Offline log stem: YYYYMMDDx_phase{N}_{name}_r{RR}[_c{EE}][_iter{II}]_{descriptor}
# (docs/31; the same convention tools/phase_logger.py::topic_stem writes).
_STEM = re.compile(
    r"^(?P<date>\d{8})(?P<letter>[a-z]+)_phase(?P<phase>\d)_(?P<name>[a-z0-9]+)"
    r"_r(?P<round>\d+)(?:_c(?P<cycle>\d+))?(?:_iter(?P<iter>\d+))?"
)


# ---------------------------------------------------------------------------
# DERIVED — computed on every read, never written down
# ---------------------------------------------------------------------------

def _setup_gate(root):
    """Import check_setup_ready as a module. None if unavailable."""
    gate = root / "tools" / "check_setup_ready.py"
    if not gate.is_file():
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_a2mc_setup_gate", gate)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)      # the gate guards its own main()
        return mod
    except Exception:
        return None


def derive_case(root, case):
    """Per-case position, read off the artifacts that prove it.

    The newest offline log stem carries phase, round and cycle in its NAME, so
    this never consults a stored copy of them.
    """
    logs = sorted(glob.glob(str(root / "use_cases" / case / "memory" / "logs" / "*.md")),
                  key=os.path.basename)
    newest, pos = None, {}
    for p in reversed(logs):                       # newest stem first
        m = _STEM.match(os.path.basename(p))
        if m:
            newest = os.path.basename(p)
            pos = {
                "phase": int(m.group("phase")),
                "phase_name": m.group("name"),
                "round": int(m.group("round")),
                "cycle": int(m.group("cycle")) if m.group("cycle") else None,
                "iter": int(m.group("iter")) if m.group("iter") else None,
                "as_of": m.group("date"),
            }
            break

    rounds = sorted(
        int(m.group(1))
        for m in (re.search(r"_r(\d+)\.json$", p) for p in
                  glob.glob(str(root / "use_cases" / case / "memory" /
                                "workflow_state_offline_r*.json")))
        if m
    )
    return {
        "case": case,
        "position": pos,                 # {} when the case has no phase log yet
        "newest_log": newest,
        "rounds_on_disk": rounds,
        "n_logs": len(logs),
    }


def derive(root):
    """Everything the filesystem can prove. No stored input is consulted."""
    gate = _setup_gate(root)
    if gate is not None:
        stage = gate._detect_stage(root)
        cases = gate._real_cases(root)
    else:                                # degrade honestly rather than guess
        stage, cases = None, sorted(
            p.name for p in (root / "use_cases").iterdir()
            if p.is_dir() and p.name != "TEMPLATE" and not p.name.endswith("_template")
        ) if (root / "use_cases").is_dir() else []
    return {
        "setup_stage": stage,
        "cases": [derive_case(root, c) for c in cases],
    }


# ---------------------------------------------------------------------------
# STORED — only what no artifact can prove
# ---------------------------------------------------------------------------

def _blank(note_extra=""):
    return {
        "schema": SCHEMA,
        "note": (
            "Offline agent's clone-level master state. STORES ONLY what no artifact can "
            "prove: approved-plan tasks, decisions, open threads, campaign goals. Phase, "
            "round, cycle, case list and setup stage are DERIVED on read "
            "(tools/agent_state.py --derive) and deliberately absent here — storing them "
            "is what made workflow_state_offline drift." + note_extra
        ),
        "updated_at": date.today().isoformat(),
        "cases": {},          # case -> {plan, tasks, goal, gates}
        "decisions": [],      # {date, what, why}
        "open_threads": [],   # {id, summary, next_action}
    }


def load(path):
    if not path.is_file():
        return _blank()
    with open(path) as f:
        return json.load(f)


def save(path, state):
    state["updated_at"] = date.today().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    tmp.replace(path)                     # atomic: a crashed write never truncates


def _case_block(state, case):
    return state.setdefault("cases", {}).setdefault(
        case, {"plan": {}, "tasks": [], "goal": "", "gates": []})


def _next_task_id(block):
    n = 0
    for t in block["tasks"]:
        m = re.match(r"t(\d+)$", str(t.get("id", "")))
        if m:
            n = max(n, int(m.group(1)))
    return f"t{n + 1}"


def add_task(state, case, text, phase=None, status="todo"):
    block = _case_block(state, case)
    task = {"id": _next_task_id(block), "text": text, "status": status}
    if phase is not None:
        task["phase"] = int(phase)        # OPTIONAL — free-form tasks need no phase
    block["tasks"].append(task)
    return task


# Plan lines worth importing: markdown checkboxes and numbered steps. Free-form
# by design — the tasks a user approved are whatever their plan says, not a
# normalization of it. `--phase` stays optional and hand-set.
_PLAN_TASK = re.compile(r"^\s*(?:[-*]\s*\[( |x|X)\]\s*|\d+[.)]\s+)(?P<text>\S.*?)\s*$")


def import_plan(state, root, case, plan_path):
    if not plan_path.is_file():
        raise FileNotFoundError(f"no research plan at {plan_path}")
    block = _case_block(state, case)
    existing = {t["text"] for t in block["tasks"]}
    added = []
    for line in plan_path.read_text().splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = _PLAN_TASK.match(line)
        if not m:
            continue
        text = m.group("text")
        if len(text) < 8 or text in existing:   # skip fragments and re-imports
            continue
        checked = m.group(1) in ("x", "X")
        added.append(add_task(state, case, text, status="done" if checked else "todo"))
        existing.add(text)
    # Store repo-relative when the plan is inside the repo (the normal case), and
    # the path as given otherwise — a plan outside the tree is legitimate (a
    # --plan-file under review), and relative_to() raises rather than degrading.
    try:
        stored_path = str(plan_path.resolve().relative_to(root))
    except ValueError:
        stored_path = str(plan_path)
    block["plan"] = {"path": stored_path, "imported_on": date.today().isoformat()}
    return added


# ---------------------------------------------------------------------------
# CHECK — invariants on the STORED half only (the derived half cannot be wrong)
# ---------------------------------------------------------------------------

def check(root, state):   # -> (errors, warnings)
    errs, warns = [], []
    if state.get("schema") != SCHEMA:
        errs.append(f"schema is {state.get('schema')!r}, expected {SCHEMA!r}")

    for banned in ("current_phase", "experiment_count", "calibration_round", "setup_stage"):
        if banned in state:
            errs.append(f"{banned!r} is DERIVED — remove it; storing it is the drift this file exists to prevent")

    derived_cases = {c["case"] for c in derive(root)["cases"]}
    for case, block in (state.get("cases") or {}).items():
        if case not in derived_cases:
            warns.append(f"case {case!r} is in the state but not on disk (renamed or removed?)")
        ids = [t.get("id") for t in block.get("tasks", [])]
        if len(ids) != len(set(ids)):
            errs.append(f"{case}: duplicate task ids")
        for t in block.get("tasks", []):
            if t.get("status") not in STATUSES:
                errs.append(f"{case}/{t.get('id')}: status {t.get('status')!r} not in {STATUSES}")
            if not str(t.get("text", "")).strip():
                errs.append(f"{case}/{t.get('id')}: empty text")
        plan = block.get("plan") or {}
        if plan.get("path") and not (root / plan["path"]).is_file():
            warns.append(f"{case}: plan {plan['path']} no longer exists")

    for i, t in enumerate(state.get("open_threads") or []):
        if not t.get("id"):
            errs.append(f"open_threads[{i}]: missing id")
    return errs, warns


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def report(root, state):
    d = derive(root)
    out = []
    stage = d["setup_stage"]
    out.append(f"Setup stage: {stage if stage is not None else '?'}"
               + ("  (stage 1 — run the `a2mc-init` skill)" if stage == 1 else ""))
    if not d["cases"]:
        out.append("Cases: none yet")
    for c in d["cases"]:
        pos, block = c["position"], (state.get("cases") or {}).get(c["case"], {})
        tasks = block.get("tasks", [])
        done = sum(1 for t in tasks if t.get("status") == "done")
        where = (f"phase {pos['phase']} ({pos['phase_name']}) R{pos['round']}"
                 + (f" c{pos['cycle']}" if pos.get("cycle") is not None else "")
                 + f", as of {pos['as_of']}") if pos else "no phase log yet"
        line = f"  {c['case']}: {where}"
        if tasks:
            line += f" | plan tasks {done}/{len(tasks)} done"
            nxt = next((t for t in tasks if t.get("status") in ("doing", "todo")), None)
            if nxt:
                line += f" | next: [{nxt['id']}] {nxt['text'][:70]}"
        out.append(line)
    if state.get("open_threads"):
        out.append(f"Open threads: {len(state['open_threads'])}")
        for t in state["open_threads"][:2]:
            out.append(f"  - {t.get('id')}: {t.get('next_action', t.get('summary', ''))[:90]}")
    return out


def main():
    ap = argparse.ArgumentParser(description="Offline agent's clone-level master state.")
    ap.add_argument("--repo-root", default=str(_REPO_ROOT))
    ap.add_argument("--derive", action="store_true", help="print only the derived half")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--check", action="store_true", help="validate the stored half (exit 1 on error)")
    ap.add_argument("--init", action="store_true", help="create the state file if absent")
    ap.add_argument("--import-plan", metavar="CASE", help="import tasks from a case's research_plan.md")
    ap.add_argument("--plan-file", help="override the plan path for --import-plan")
    ap.add_argument("--add-task", nargs=2, metavar=("CASE", "TEXT"))
    ap.add_argument("--phase", type=int, help="optional phase for --add-task")
    ap.add_argument("--set-status", nargs=3, metavar=("CASE", "TASK_ID", "STATUS"))
    args = ap.parse_args()

    root = Path(args.repo_root).resolve()
    path = root / STATE_REL

    if args.derive:
        d = derive(root)
        print(json.dumps(d, indent=2) if args.json else
              "\n".join(report(root, _blank())))
        return 0

    state = load(path)

    if args.init:
        if path.is_file():
            print(f"already exists: {path.relative_to(root)}")
        else:
            save(path, state)
            print(f"created {path.relative_to(root)}")
        return 0

    if args.import_plan:
        case = args.import_plan
        plan = Path(args.plan_file) if args.plan_file else (
            root / "use_cases" / case / "research_plan.md")
        try:
            added = import_plan(state, root, case, plan)
        except FileNotFoundError as e:
            print(f"✘ {e}", file=sys.stderr)
            return 1
        save(path, state)
        print(f"imported {len(added)} task(s) for {case} from {plan.name}")
        for t in added:
            print(f"  [{t['id']}] {t['status']:6} {t['text'][:80]}")
        if not added:
            print("  (no `- [ ]` or numbered items found — add them with --add-task)")
        return 0

    if args.add_task:
        case, text = args.add_task
        t = add_task(state, case, text, phase=args.phase)
        save(path, state)
        print(f"added [{t['id']}] to {case}: {t['text']}")
        return 0

    if args.set_status:
        case, tid, status = args.set_status
        if status not in STATUSES:
            print(f"✘ status must be one of {STATUSES}", file=sys.stderr)
            return 1
        block = _case_block(state, case)
        for t in block["tasks"]:
            if str(t.get("id")) == tid:
                t["status"] = status
                save(path, state)
                print(f"{case}/{tid} -> {status}")
                return 0
        print(f"✘ no task {tid} in {case}", file=sys.stderr)
        return 1

    if args.check:
        errs, warns = check(root, state)
        for w in warns:
            print(f"  [warn] {w}")
        if errs:
            print(f"✘ agent_state: {len(errs)} problem(s):")
            for e in errs:
                print(f"    {e}")
            return 1
        print("✔ agent_state: stored half valid "
              f"({len(state.get('cases') or {})} case(s), "
              f"{sum(len(b.get('tasks', [])) for b in (state.get('cases') or {}).values())} task(s))")
        return 0

    if args.json:
        print(json.dumps({"derived": derive(root), "stored": state}, indent=2))
    else:
        print("\n".join(report(root, state)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
