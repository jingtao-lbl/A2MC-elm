#!/usr/bin/env python3
"""PostToolUse hook: fire when an action just CROSSED a setup-stage boundary.

`SessionStart` names the setup stage once. But setup is a SEQUENCE — `a2mc-init`
finishes, a case gets scaffolded, a parameter list lands — and the stage that was
true at session start is stale within the hour. Nothing observes the transition.

That is the same failure `remind-arm-monitoring.py` was written for, and its
docstring names it exactly: a conditional instruction, correctly evaluated once,
never re-evaluated. This hook observes the setup half.

Ported from `adapter-kit` (handoff 20260819f Part 2), re-authored for `main`:
5 triggers rather than 6 (`tools/create_use_case.py` does not exist here), and
no model-onboarding rows, since this branch has 2 stages, not 4.

DESIGN RULES, each from the working precedent rather than invented:
  * NEVER BLOCK. Every action it watches is normal and desirable.
  * EXCLUDE PREVIEWS (`--dry-run`, `--list`, `--write-script`) and this file,
    or it becomes noise and gets muted.
  * NAME THE SKILL AND THE SPECIFIC GAPS, not a generic nudge. A vague reminder
    is acknowledged and ignored.
  * FIRE ON THE TRANSITION, NOT THE STATE. Re-emitting on every write is the
    fastest way to train the reader to skip it. A gitignored stamp keyed on
    (stage, outstanding-count) keeps a run of writes inside one stage quiet
    while a genuine second transition still reports.
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

STAMP = ".claude/.setup_stage_stamp"

# Path writes that bring a setup artifact into EXISTENCE. Matched against the
# tool's target path. Deliberately anchored under use_cases/ so unrelated edits
# stay silent.
_PATH_TRIGGERS = (
    r"use_cases/[^/]+/config/[^/]+_config\.sh$",
    r"use_cases/[^/]+/config/calibration_rounds\.yaml$",
    r"use_cases/[^/]+/validation/targets\.yaml$",
    r"use_cases/[^/]+/parameters/",
)
# Commands that wire the clone. `create_use_case.py` is adapter-kit-only.
_CMD_TRIGGERS = (r"setup_clone\.sh",)
# Previews and status calls change nothing.
_PREVIEW = ("--dry-run", "--list", "--write-script", "--help", "remind-setup-stage")


def _root():
    return os.environ.get("CLAUDE_PROJECT_DIR") or str(Path(__file__).resolve().parents[2])


def _gate(root):
    """Load the stage gate. Delegating keeps one definition of 'which stage'."""
    p = Path(root) / "tools" / "check_setup_ready.py"
    if not p.is_file():
        return None
    spec = importlib.util.spec_from_file_location("_a2mc_gate", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)      # safe: the gate guards its own main()
    return m


def _outstanding(root, gate):
    """Setup artifacts still missing, as short human labels."""
    r = Path(root)
    cases = gate._real_cases(r)
    if not cases:
        return ["a real case under use_cases/ (only TEMPLATE/ so far)"]
    missing = []
    for c in cases:
        d = r / "use_cases" / c
        if not list((d / "config").glob("*_config.sh")):
            missing.append(f"{c}: site config (<case>_config.sh)")
        if not (d / "config" / "calibration_rounds.yaml").is_file():
            missing.append(f"{c}: calibration_rounds.yaml (generate, do not hand-author)")
        if not (d / "validation" / "targets.yaml").is_file():
            missing.append(f"{c}: validation/targets.yaml")
        params = d / "parameters"
        if not params.is_dir() or not any(params.glob("*.csv")):
            missing.append(f"{c}: parameter list (GATE 2)")
    return missing


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return                                  # unparseable payload: silent

    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input", {}) or {}

    if payload.get("tool_response", {}).get("success") is False:
        return                                  # the action failed; nothing changed

    blob = " ".join(str(v) for v in ti.values())
    if any(p in blob for p in _PREVIEW):
        return

    hit = False
    if tool == "Bash":
        cmd = ti.get("command", "")
        hit = any(re.search(p, cmd) for p in _CMD_TRIGGERS)
    elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = str(ti.get("file_path", ""))
        hit = any(re.search(p, path) for p in _PATH_TRIGGERS)
    if not hit:
        return

    root = _root()
    gate = _gate(root)
    if gate is None:
        return

    stage = gate._detect_stage(Path(root))
    missing = _outstanding(root, gate)
    if not missing:
        return                                  # nothing outstanding: say nothing

    # Transition, not state: same (stage, gap-count) => already reported.
    key = f"{stage}:{len(missing)}"
    stamp = Path(root) / STAMP
    try:
        if stamp.read_text().strip() == key:
            return
    except OSError:
        pass
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(key)
    except OSError:
        pass

    skill = "a2mc-init" if stage == 1 else "onboard-case"
    body = (f"SETUP STAGE {stage} ADVANCED — the definition of done is the "
            f"`setup-discipline` skill (stage skill: `{skill}`).\n"
            f"  Still outstanding:\n"
            + "\n".join(f"    - {m}" for m in missing[:6])
            + f"\n  Audit: python3 tools/check_setup_ready.py")

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "systemMessage": body}}))


if __name__ == "__main__":
    main()
