#!/usr/bin/env python3
"""SessionStart hook — surface a brief operating snapshot into context at session start
(also runs on resume / after compaction). Best-effort and read-only; never blocks.

Shows: current branch, uncommitted-file count, the latest Handoff/Session dev_log plus
the latest dev_log and ana_log of ANY type (both logging streams), the count of pending
knowledge proposals awaiting curation, and any live long-running A2MC processes. Helps the
cold-start runbook (CLAUDE.md Rule 6) fire reliably.
"""
import sys, os, re, json, glob, subprocess


def sh(args):
    try:
        return subprocess.check_output(args, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def ensure_memory_symlink(root, lines):
    """Self-heal the .claude_memory bucket wiring (docs/29 machinery).

    The harness reads memory from ~/.claude/projects/<cwd-key>/memory/, which must be
    a symlink to the tracked <repo>/.claude_memory/. NON-DESTRUCTIVE: auto-wire only a
    fresh clone (harness path absent or holding no real memories); if the harness store
    holds its OWN memories, WARN loudly and leave it, never clobber/merge automatically.
    Best-effort; never raises. The automatic fallback to scripts/setup_clone.sh.
    """
    try:
        bucket = os.path.join(root, ".claude_memory")
        if not os.path.isdir(bucket):
            return  # no tracked bucket on this branch (e.g. a public clone)
        harness = os.path.expanduser(
            "~/.claude/projects/%s/memory" % root.replace("/", "-"))
        if os.path.islink(harness):
            return  # already wired
        mems = [f for f in os.listdir(harness)
                if f.endswith(".md") and f != "MEMORY.md"] if os.path.isdir(harness) else []
        if not mems:
            # fresh clone (absent / empty): safe to auto-wire, back up any empty dir
            if os.path.isdir(harness):
                os.rename(harness, harness + ".pre-symlink-bak")
            os.makedirs(os.path.dirname(harness), exist_ok=True)
            os.symlink(bucket, harness)
            lines.append("✓ auto-wired Claude memory bucket (fresh clone) -> .claude_memory")
        else:
            stray = sorted(set(mems) - {f for f in os.listdir(bucket) if f.endswith(".md")})
            lines.append(
                "⚠ Claude memory bucket NOT wired: %d standalone file(s) in the harness "
                "store%s not under git. Reconcile into .claude_memory/, then run "
                "scripts/setup_clone.sh."
                % (len(mems), (" incl. %s" % ", ".join(stray[:3])) if stray else ""))
    except Exception:
        pass


def memory_checkup_due(root, lines):
    """Weekly memory/skills staleness checkup — a DURABLE trigger.

    CronCreate/Monitor timers are session-only and expire, so they cannot carry a weekly
    cadence across session boundaries (see memory
    `feedback_schedule_periodic_reviews_with_a_real_mechanism`). This is stateless instead: a
    timestamp file plus an age check, so it fires the next time a session starts after the
    interval elapses, which for a weekly audit is exactly when it is useful.

    The stamp lives at .claude_memory/.last_checkup and is gitignored (per-clone, not shared).
    """
    import datetime
    stamp = os.path.join(root, ".claude_memory", ".last_checkup")
    today = datetime.date.today()
    try:
        with open(stamp) as f:
            last = datetime.date.fromisoformat(f.read().strip())
        days = (today - last).days
    except Exception:
        days, last = None, None
    if days is None:
        lines.append("⏰ memory checkup: never run here — run the `memory-checkup` skill "
                     "(then: date -I > .claude_memory/.last_checkup)")
    elif days >= 7:
        lines.append("⏰ memory checkup DUE — %d days since %s. Run the `memory-checkup` "
                     "skill (then: date -I > .claude_memory/.last_checkup)" % (days, last))


def hpc_jobs_in_flight(root, lines):
    """Jobs already on the scheduler at session start => `arm-hpc-monitoring` applies NOW.

    THE BLIND SPOT THIS CLOSES. The sibling hook `remind-arm-monitoring.py` is PostToolUse
    on a SUBMISSION, so it can only fire in the session that submits. A session that
    INHERITS running jobs -- the normal case after a compaction, a resume, or simply the
    next day -- never triggers it. That is not a corner case: a multi-day ensemble is
    inherited by every session except the first.

    Why "jobs in flight" is sufficient evidence that nothing is watching them: a Claude
    `Monitor` is session-scoped and does not survive a session boundary, so a starting
    session has zero armed monitors BY CONSTRUCTION. No state file is needed to detect the
    gap -- queued/running jobs at session start always mean "unwatched, so far".

    Motivated by, but NOT demonstrated by, the 2026-08-09 miss: three restarted TRANS chains
    ran ~25 h with a correctly nohup'd watcher writing events no Monitor was reading. The
    submission-time hook did not catch that for the mundane reason that it did not yet exist
    (jobs submitted 08-08 07:36; hook written 08-09 08:11). The inherited-session gap above is
    a property of the TRIGGER, reasoned from where it fires, not an inference from that
    incident. Stated this way deliberately: the first draft of this docstring claimed the jobs
    were inherited from an earlier session, which two timestamps disprove. See
    memory/dev_logs/reflection/20260809a_Reflection_Why_Reading_The_Skill_Was_Not_Enough.md.

    `timeout` is not optional: a busy or degraded SLURM controller makes squeue HANG rather
    than fail, and a session-start hook must never wedge the session.
    """
    out = sh(["bash", "-lc",
              "timeout 15 squeue -u \"$USER\" -h -o '%T' 2>/dev/null "
              "| sort | uniq -c | sort -rn"])
    if not out:
        return                      # no jobs, squeue absent, or the query timed out
    counts, total = [], 0
    for ln in out.splitlines():
        parts = ln.split()
        if len(parts) == 2 and parts[0].isdigit():
            total += int(parts[0])
            counts.append("%s %s" % (parts[0], parts[1].lower()))
    if not total:
        return

    lines.append(
        "⚠ %d HPC job%s IN FLIGHT (%s) and NO monitor is armed — a Monitor is session-scoped, "
        "so this session starts with none. `arm-hpc-monitoring` applies now; the submission-time "
        "hook cannot have fired for jobs inherited from an earlier session."
        % (total, "" if total == 1 else "s", ", ".join(counts)))
    # Reuse the sibling hook's wording verbatim so the two can never drift apart.
    try:
        import importlib.util
        _sp = importlib.util.spec_from_file_location(
            "_ram", os.path.join(root, ".claude", "hooks", "remind-arm-monitoring.py"))
        _ram = importlib.util.module_from_spec(_sp)
        _sp.loader.exec_module(_ram)
        body = _ram.MESSAGE.split("\n", 1)[1]      # drop its submission-specific first line
        lines.append("  " + body.replace("\n", "\n  "))
    except Exception:
        lines.append("  Two layers (nohup the watcher, arm Monitor on its LOG); a PROGRESS "
                     "signal, not only state transitions; terminal is an ALLOW-LIST "
                     "cross-checked against filesystem liveness.")


def setup_stage(root, lines):
    """Name the setup stage when this clone is NOT yet configured.

    Silent once setup is done, which is the normal case — a session that pays
    nothing for this is a session that will not learn to skip the block.

    DELEGATES detection to tools/check_setup_ready.py::_detect_stage rather than
    restating the routing. A second copy of "which stage am I in" drifts from the
    first, and the gate is the thing the user is told to run, so the hook must
    agree with it by construction (adapter-kit handoff 20260819f, Part 1).
    """
    import importlib.util
    gate = os.path.join(root, "tools", "check_setup_ready.py")
    if not os.path.isfile(gate):
        return
    spec = importlib.util.spec_from_file_location("_a2mc_setup_gate", gate)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # safe: the gate guards its own main()

    from pathlib import Path
    stage = mod._detect_stage(Path(root))
    if stage != 1:
        return                            # configured — say nothing

    cases = mod._real_cases(Path(root))
    why = ("only TEMPLATE/ — no real case yet" if not cases
           else "a2mc_config.sh or A2MC_MODEL_PATH is not set up")
    lines.append(
        f"► SETUP STAGE 1 — start with the `a2mc-init` skill ({why}).\n"
        f"  Definition of done: the `setup-discipline` skill. "
        f"Audit it now: python3 tools/check_setup_ready.py")


def main():
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    lines = []
    ensure_memory_symlink(root, lines)

    branch = sh(["git", "-C", root, "branch", "--show-current"])
    if branch:
        lines.append("Branch: %s" % branch)

    dirty = sh(["git", "-C", root, "status", "--porcelain"])
    n_dirty = len([l for l in dirty.splitlines() if l.strip()])
    lines.append("Uncommitted files: %d" % n_dirty)

    def latest(pattern):
        # Newest by the YYYYMMDDx naming convention (basename lexical sort).
        hits = glob.glob(pattern)
        return os.path.basename(sorted(hits, key=os.path.basename)[-1]) if hits else ""

    # Narrow cold-start pointer: latest Handoff/Session log specifically.
    hs = (glob.glob(os.path.join(root, "memory", "dev_logs", "*Handoff*")) +
          glob.glob(os.path.join(root, "memory", "dev_logs", "*Session_Log*")))
    if hs:
        lines.append("Latest handoff/session log: %s"
                     % os.path.basename(sorted(hs, key=os.path.basename)[-1]))

    # Latest of ANY type in each stream, so no recent work is missed.
    dev = latest(os.path.join(root, "memory", "dev_logs", "20*.md"))
    if dev:
        lines.append("Latest dev_log (any type): %s" % dev)
    ana = latest(os.path.join(root, "memory", "ana_logs", "20*.md"))
    if ana:
        lines.append("Latest ana_log (any type): %s" % ana)

    # Offline-agent resume state (docs/31): the highest-round workflow_state_offline_r{RR}.json.
    best = None
    for p in glob.glob(os.path.join(root, "use_cases", "*", "memory",
                                    "workflow_state_offline_r*.json")):
        m = re.search(r"_r(\d+)\.json$", p)
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), p)
    if best:
        try:
            with open(best[1]) as f:
                st = json.load(f)
            nt = len(st.get("open_threads", []))
            lines.append("Offline state: R%s (%s) %s | cycle %s | %d open thread%s"
                         % (st.get("calibration_round"), st.get("site", "?"),
                            st.get("current_phase"), st.get("experiment_count"),
                            nt, "" if nt == 1 else "s"))
            # docs/35: the next action is the most salient cold-start line — DRIVE it, don't wait.
            if st.get("open_threads"):
                na = st["open_threads"][0].get("next_action", "")
                if na:
                    lines.append("  ► NEXT: %s  (execute it; pause only at a fork/hard stop)" % na)
            # Phase-6 objective gate (docs/34): surface the binding target + next experiment.
            pd = st.get("phase6_decision")
            if pd and (pd.get("binding_target") or pd.get("next_targeted_experiment")):
                lines.append("  objective: binding target '%s' | next experiment: %s"
                             % (pd.get("binding_target", "?"),
                                pd.get("next_targeted_experiment", "?")))
            # Invariant check — surface a corrupt/misdriving state loudly (non-blocking).
            try:
                import importlib.util
                _sp = importlib.util.spec_from_file_location(
                    "_cwso", os.path.join(root, "tools", "check_workflow_state_offline.py"))
                _cwso = importlib.util.module_from_spec(_sp)
                _sp.loader.exec_module(_cwso)
                _errs, _ = _cwso.check_one(best[1])
                if _errs:
                    lines.append("⚠ Offline state INVALID (%d error%s) — run "
                                 "tools/check_workflow_state_offline.py before driving: %s"
                                 % (len(_errs), "" if len(_errs) == 1 else "s", _errs[0]))
            except Exception:
                pass
        except Exception:
            pass

    open_props = 0
    for p in glob.glob(os.path.join(root, "use_cases", "*", "memory",
                                    "gained_knowledge", "auto_discovered_pending.json")):
        try:
            with open(p) as f:
                d = json.load(f)
            open_props += sum(1 for it in d.get("pending", [])
                              if not it.get("promoted") and not it.get("discarded"))
        except Exception:
            pass
    if open_props:
        lines.append("Pending knowledge proposals to curate: %d "
                     "(run the curate-knowledge skill)" % open_props)

    try:
        setup_stage(root, lines)
    except Exception:
        pass

    try:
        memory_checkup_due(root, lines)
    except Exception:
        pass

    ps = sh(["bash", "-lc",
             "ps -ef | grep \"$USER\" | grep -E 'monitor|submit|extract' "
             "| grep -v grep | head -5"])
    if ps:
        lines.append("Live A2MC processes:\n" + ps)

    # Ask the scheduler directly. The `ps` check above sees only THIS login node, so it
    # misses an ensemble whose driver has exited or was launched from another node --
    # while its jobs keep running. Last, so the reminder lands closest to the prompt.
    try:
        hpc_jobs_in_flight(root, lines)
    except Exception:
        pass

    ctx = "A2MC session snapshot —\n" + "\n".join(lines)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx}}))


if __name__ == "__main__":
    # Guard added 2026-08-19. Without it, `import session_start` RUNS main() and
    # emits a full session snapshot, so the module cannot be imported by a test.
    # remind-arm-monitoring.py:97 already had this; only this file lagged.
    main()
