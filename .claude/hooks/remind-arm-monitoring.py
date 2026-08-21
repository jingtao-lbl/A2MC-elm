#!/usr/bin/env python3
"""PostToolUse hook: fire when a Bash command has just SUBMITTED HPC jobs.

Why this exists
---------------
`onboard-session` says to invoke `arm-hpc-monitoring` *when an ensemble is in
flight*. That is a CONDITIONAL instruction, and on 2026-08-08 it was evaluated
once, correctly, at session start (nothing was running) and never re-evaluated
when three jobs were later submitted. The agent then hand-rolled a watcher that
(a) was session-local, contradicting `arm-hpc-monitoring` #5, (b) carried no
PROGRESS signal, so a 48 h run emitted nothing between its two SLURM state
transitions, and (c) treated "not RUNNING" as terminal, so a `slurmdbd` outage
made three live jobs read as finished. That improvisation was then written into
`offline-testing-workflow` Step 9d as guidance, contradicting the skill that owns
the operation.

The root cause was not comprehension. It was that the moment the invocation
condition became true went unobserved. This hook observes it.

Contract
--------
Reads the PostToolUse payload on stdin. If the Bash command looks like a job
submission AND the tool succeeded, emits a `systemMessage` naming the skill and
its three load-bearing requirements. It never blocks: a submission is a normal,
desirable action, and a hook that denied it would be wrong.

Deliberately NOT matched: `squeue`, `sacct`, `scontrol`, `--dry-run`,
`--write-script`, and this file itself, so status checks and previews stay quiet.

Author: Jing Tao with Claude
"""
import json
import re
import sys

# A submission actually reached the scheduler.
# NOTE: plain \b boundaries, deliberately. An earlier version required whitespace or
# line-start before the command, which missed BOTH real-world forms: `./case.submit`
# and `python3 phases/phase0_design/submit_phase0.py` (a `/` precedes the name).
SUBMIT_RE = re.compile(
    r"\b(?:"
    r"sbatch"                         # direct
    r"|case\.submit"                  # CIME
    r"|submit_phase0\.py"             # A2MC ensemble
    r"|submit_experiments\.py"        # A2MC phase-5
    r"|submit_ensemble\.sh"
    r")\b",
    re.I,
)
# Previews and read-only queries must not trigger it.
QUIET_RE = re.compile(r"--dry-run\b|--write-script\b|\bsqueue\b|\bsacct\b|\bscontrol\b"
                      r"|remind-arm-monitoring", re.I)

MESSAGE = (
    "HPC JOBS SUBMITTED -> `arm-hpc-monitoring` now applies (it may have been correctly "
    "skipped at session start, when nothing was running; that answer is now stale).\n"
    "Its three load-bearing requirements, each of which a hand-rolled watcher has already "
    "missed once:\n"
    "  1. TWO LAYERS: nohup the watcher script, then arm `Monitor` on its LOG. A poll loop "
    "run directly as the Monitor command is session-local (anti-pattern #5).\n"
    "  2. A PROGRESS SIGNAL in the event filter, not only state transitions. A multi-day "
    "chain has two SLURM transitions, so a transitions-only filter is silent for days.\n"
    "  3. TERMINAL IS AN ALLOW-LIST, cross-checked against filesystem liveness. 'Not "
    "RUNNING' is not 'finished' -- a scheduler-database outage reads identically.\n"
    "Open the skill and follow it; do not re-derive a watcher shape."
)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)                                   # unparseable -> stay silent

    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (payload.get("tool_input") or {}).get("command", "") or ""
    if not cmd or QUIET_RE.search(cmd) or not SUBMIT_RE.search(cmd):
        sys.exit(0)

    # Only fire when the submission actually succeeded.
    resp = payload.get("tool_response") or {}
    if isinstance(resp, dict):
        if resp.get("success") is False:
            sys.exit(0)
        out = "{}{}".format(resp.get("stdout", ""), resp.get("stderr", ""))
        if re.search(r"\berror\b|\bfailed\b|command not found", out, re.I) and \
           not re.search(r"submitted (?:batch )?job", out, re.I):
            sys.exit(0)

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": MESSAGE}}))
    sys.exit(0)


if __name__ == "__main__":
    main()
