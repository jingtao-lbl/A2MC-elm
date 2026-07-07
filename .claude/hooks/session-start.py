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


def main():
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    lines = []

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

    ps = sh(["bash", "-lc",
             "ps -ef | grep \"$USER\" | grep -E 'monitor|submit|extract' "
             "| grep -v grep | head -5"])
    if ps:
        lines.append("Live A2MC processes:\n" + ps)

    ctx = "A2MC session snapshot —\n" + "\n".join(lines)
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx}}))


main()
