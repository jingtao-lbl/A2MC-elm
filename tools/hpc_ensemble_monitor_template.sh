#!/bin/bash
# hpc_ensemble_monitor_template.sh — A2MC HPC ensemble auto-monitor (TEMPLATE)
#
# =============================================================================
# WHAT THIS IS
# =============================================================================
# Generic implementation of the autonomous monitoring workflow documented in
# memory/dev_logs/20260514c_Monitoring_Workflow_Pattern_For_HPC_Ensembles.md.
# This template is the round-agnostic version of the canonical instance that
# lives at use_cases/Kougarok/analysis/r5_auto_monitor.sh — the live R5 Morris
# ensemble instance (May 2026), moved from tmp/ on 2026-05-18 to be git-tracked.
# Every R5-specific value (launch timestamp, case-count target, A2MC_ROOT,
# extracted-NC filename pattern, etc.) is now resolved at startup by sourcing
# the two A2MC config files — there is no need to edit this template for a
# new round; just expose the right env vars in your site config.
#
# Side-effects per 30-min poll:
#   1. Emit SLURM queue-depth + threshold-crossing events on stdout
#   2. Detect new TRANS-phase completions on disk + auto-trigger extraction
#   3. Invoke the per-site milestone-plot regen helper (idempotent)
#   4. Track consecutive-idle polls and exit on terminal-idle (NOT count-based)
#
# =============================================================================
# REFERENCE INSTANCE
# =============================================================================
# use_cases/Kougarok/analysis/r5_auto_monitor.sh — the live R5 instance, patched twice on 2026-05-18:
#   v1 (pre_terminal_idle):  count-based stop → 2-tick terminal-idle stop;
#                            one-shot QUEUE_BELOW_500 latch → re-armable
#                            crossing-based events.
#   v2 (pre_regen_hook):     added the milestone-plot regen call.
# Sequence of dev_logs that describe the patch history:
#   memory/dev_logs/20260513a_Session_Log_R5_Batch1_Launch_and_Monitoring.md
#   memory/dev_logs/20260514c_Monitoring_Workflow_Pattern_For_HPC_Ensembles.md
#   memory/dev_logs/20260518b_R5_Mid_Ensemble_Audit_And_Automation_Hardening.md
#
# When in doubt about why a particular design choice was made, the R5 instance
# at tmp/r5_auto_monitor.sh.bak_20260518_pre_terminal_idle (and its newer
# revisions) is the historical record of what we tried and what we changed.
#
# =============================================================================
# USAGE
# =============================================================================
# 1. Copy this template to the per-round operational location, e.g.:
#       cp tools/hpc_ensemble_monitor_template.sh \
#          use_cases/Kougarok/analysis/r6_auto_monitor.sh
#    (You CAN run the template directly without copying, but having a named
#    per-round instance under `use_cases/<site>/analysis/` makes the live
#    process easy to identify in `ps -ef | grep r6_auto_monitor` AND keeps it
#    git-tracked alongside its companion `regen_milestone_plot.sh` helper.)
#
# 2. Source the machine + site config files FIRST so the env vars are populated
#    in the bash session that will run the monitor. For Kougarok R5 the source
#    chain was:
#       source ${A2MC_ROOT}/a2mc_config.sh
#       source ${A2MC_ROOT}/use_cases/Kougarok/config/kougarok_config_r5.sh
#    For R6 you'd swap in kougarok_config_r6.sh (or whatever you name it).
#    The site config MUST export the round-specific env vars listed below.
#
# 3. Launch via:
#       nohup bash <your-copy>.sh >> <log-file> 2>&1 &
#    The log file path is what your Claude `Monitor` tool tails. In R5 we
#    appended to the same log across script restarts so the event history
#    persisted (see 20260514c §"Part 3 — The re-arm cycle").
#
# =============================================================================
# REQUIRED ENV VARS (must be exported by a2mc_config.sh + site config)
# =============================================================================
# Round-agnostic (already in a2mc_config.sh / standard site configs):
#   A2MC_ROOT             — machine root, e.g. /global/u1/j/jingtao/A2MC
#   A2MC_EXTRACTED_DATA   — where extracted monthly NCs land
#   A2MC_ENSEMBLE_OUTPUT  — where per-case run dirs live
#   A2MC_USE_CASE_DIR     — root of the active site, used to find the regen helper
#
# Round-specific (MUST be added to your site config for the new round):
#   A2MC_LAUNCH_TIME      — wall-clock timestamp the round was launched, in the
#                           login node's local TZ, format "YYYY-MM-DD HH:MM:SS".
#                           Used as the mtime cutoff for "fresh NC" filtering
#                           (excludes stale leftovers from prior rounds that
#                           share the filename pattern).
#                           R5 value: "2026-05-12 18:00:00"
#   A2MC_TARGET_TOTAL     — full ensemble case count. Informational ONLY —
#                           the loop's stop condition is terminal-idle, not a
#                           count check (see DESIGN NOTES). R5 value: 4890
#
# =============================================================================
# OPTIONAL ENV VARS (with R5-matching defaults; override in site config if your
#                    case-naming or restart-file conventions differ)
# =============================================================================
#   A2MC_TRANS_RESTART_PATH  — find -path argument used to count completed
#       TRANS-phase runs. Default matches FATES adapter convention:
#         "*_TRANS/run/*.elm.r.2020-01-01-00000.nc"
#       Override if your round uses a different TRANS phase tag, or a different
#       final-restart year (e.g. for a 2010-stop run set the 2020 → 2010).
#       R5 used the default unmodified.
#
#   A2MC_EXTRACTED_NC_GLOB   — find -name argument for the extracted monthly
#       NC files. Default:
#         "*_TRANS_all_variables_monthly_*.nc"
#       Override if extract_monthly_variables_FATES.py is producing a
#       different filename convention. R5 used the default unmodified.
#
#   A2MC_CASE_NUM_REGEX      — regex to extract the case number from a filename
#       or job name. Default matches the Kougarok PrescP convention:
#         "PtCNPEn([0-9]+)PrescP"
#       For ADSPSupNP rounds, set in site config to something like:
#         "PtCNPEn([0-9]+)ADSPSupNP"
#
#   A2MC_QUEUE_JOB_REGEX     — regex to identify *this round's* jobs in the
#       SLURM queue (separate from any orchestrator-spawned jobs from other
#       sessions that might be in the same queue). Default matches R5:
#         "PtCNPEn[0-9]+PrescP_(ADSP|RGSP|TRANS)"
#
#   A2MC_REGEN_HELPER        — path to per-site milestone-plot regen helper.
#       Default:
#         "${A2MC_USE_CASE_DIR}/analysis/regen_milestone_plot.sh"
#       The helper itself is round-aware (it reads $A2MC_LAUNCH_TIME for the
#       mtime cutoff and builds output filenames with the round prefix); see
#       use_cases/Kougarok/analysis/regen_milestone_plot.sh for the R5 example.
#
#   A2MC_NEEDS_LIST_FILE     — temp file the extraction-trigger writes the list
#       of completed-but-not-extracted case numbers into.
#       Default: "${A2MC_ROOT}/tmp/auto_monitor_needs.txt"
#
#   A2MC_AUTOMON_LOG_DIR     — where this script writes extractor launch logs.
#       Default: "${A2MC_ROOT}/tmp"
#
#   A2MC_POLL_INTERVAL_SECONDS — poll cadence. Default: 1800 (30 min).
#       Don't go lower than 600 — squeue and find -newermt on CFS aren't cheap.
#
# =============================================================================
# EVENTS EMITTED ON STDOUT (each line is one event for Claude `Monitor` filter)
# =============================================================================
#   QUEUE_DEPTH: queue=<N> running=<R> pending=<P>
#   QUEUE_BELOW_1000: queue=<N>      (downward crossing — safe for ~1100-case launch)
#   QUEUE_BELOW_500: queue=<N>       (downward crossing — safe for ~1500-case launch)
#   QUEUE_ABOVE_500: queue=<N>       (upward crossing — a batch was just launched)
#   TRANS_DONE: completed=<C> extracted=<E> pending=<C-E>
#   STARTING_EXTRACTION: cases=<N>
#   IDLE_TICK: <n>/2 (queue=0 extractor=0 needs=0 extracted=<E>/<T>)
#   ROUND_TERMINAL: extracted=<E>/<T>   (final exit, ensemble done)
#   REGEN_LAUNCHED / REGEN_SKIP / REGEN_DEFER   (forwarded from regen helper)
#
# Note that ROUND_TERMINAL here replaces the round-specific R5_TERMINAL name
# used in the R5 instance. If your Claude `Monitor` filter grep was previously
# anchored on R5_TERMINAL, change it to ROUND_TERMINAL.
#
# =============================================================================
# DESIGN NOTES (also covered in 20260514c §Design Decisions and 20260518b §3)
# =============================================================================
# Stop condition is "queue empty AND no extractor AND needs=0 for 2 consecutive
# polls" — NOT a count-based check on A2MC_TARGET_TOTAL. R5's batch 1 false-
# trigger (BATCH1_EXTRACTION_DONE at 1512/1500 when batch 1 only really had
# 1248 cases) was caused by a count-based stop that didn't filter by batch
# range, and even with that filter fixed, terminal failures cap the achievable
# count below the target so count-based stops would never fire correctly.
# See 20260518b §"1. Correction to the audit's extraction count" for the
# bug history.
#
# Queue thresholds use crossing detection (prev_queue vs current) so each
# downcross emits exactly one signal. The initial prev_queue sentinel value
# of 99999 will spuriously fire QUEUE_BELOW_* on the first poll if the live
# queue is already below threshold — this is informational noise documented
# in 20260518b §"5. Monitor relaunched + Batch 3A submitted".
#
# 2-tick idle window (1 hour) before exit ensures a TRANS that finishes
# between polls gets one more extraction chance before the monitor exits.
# See 20260518b §"Why 2-tick terminal-idle instead of immediate?".
# =============================================================================

set -u

# -----------------------------------------------------------------------------
# Config validation — fail fast on missing required env vars.
# -----------------------------------------------------------------------------
required=(A2MC_ROOT A2MC_EXTRACTED_DATA A2MC_ENSEMBLE_OUTPUT
          A2MC_LAUNCH_TIME A2MC_TARGET_TOTAL)
missing=0
for v in "${required[@]}"; do
    if [ -z "${!v:-}" ]; then
        echo "ERROR: required env var \$$v is not set. Source a2mc_config.sh + the site config before launching this monitor." >&2
        missing=1
    fi
done
[ "$missing" -eq 1 ] && exit 2

# -----------------------------------------------------------------------------
# Defaults for optional config (matches R5 / Kougarok PrescP conventions).
# -----------------------------------------------------------------------------
LAUNCH="$A2MC_LAUNCH_TIME"
TARGET_TOTAL="$A2MC_TARGET_TOTAL"
TRANS_RESTART_PATH="${A2MC_TRANS_RESTART_PATH:-*_TRANS/run/*.elm.r.2020-01-01-00000.nc}"
EXTRACTED_NC_GLOB="${A2MC_EXTRACTED_NC_GLOB:-*_TRANS_all_variables_monthly_*.nc}"
CASE_NUM_REGEX="${A2MC_CASE_NUM_REGEX:-PtCNPEn([0-9]+)PrescP}"
QUEUE_JOB_REGEX="${A2MC_QUEUE_JOB_REGEX:-PtCNPEn[0-9]+PrescP_(ADSP|RGSP|TRANS)}"
REGEN_HELPER="${A2MC_REGEN_HELPER:-${A2MC_USE_CASE_DIR:-$A2MC_ROOT/use_cases/Kougarok}/analysis/regen_milestone_plot.sh}"
NEEDS_LIST_FILE="${A2MC_NEEDS_LIST_FILE:-${A2MC_ROOT}/tmp/auto_monitor_needs.txt}"
LOG_DIR="${A2MC_AUTOMON_LOG_DIR:-${A2MC_ROOT}/tmp}"
POLL_INTERVAL="${A2MC_POLL_INTERVAL_SECONDS:-1800}"

# -----------------------------------------------------------------------------
# State variables — initialized so first-poll behavior is well-defined.
# -----------------------------------------------------------------------------
prev_queue=99999              # sentinel: forces first-poll downcross detection
idle_consecutive=0            # consecutive idle polls (terminate at 2)
last_completed_announced=0    # for TRANS_DONE event deduplication

# =============================================================================
# Main poll loop
# =============================================================================
while true; do
    # ---- Queue depth ----
    q=$(squeue -u "$USER" -h 2>/dev/null | wc -l)
    r=$(squeue -u "$USER" -t RUNNING -h 2>/dev/null | wc -l)
    p=$(squeue -u "$USER" -t PENDING -h 2>/dev/null | wc -l)
    echo "QUEUE_DEPTH: queue=$q running=$r pending=$p"

    # Crossing-based queue events (re-armable across multiple batch launches).
    # See 20260514c §"Why one-shot QUEUE_BELOW_500" — short answer: we WERE
    # one-shot in the early R5 batches but that broke when multi-batch runs
    # needed multiple downcross signals.
    if [ "$q" -le 1000 ] && [ "$prev_queue" -gt 1000 ]; then
        echo "QUEUE_BELOW_1000: queue=$q -- safe to launch combined ~1100-case batch under 5000-job ceiling"
    fi
    if [ "$q" -le 500 ] && [ "$prev_queue" -gt 500 ]; then
        echo "QUEUE_BELOW_500: queue=$q -- safe to launch ~1500-case batch under 5000-job ceiling"
    fi
    if [ "$q" -gt 500 ] && [ "$prev_queue" -le 500 ] && [ "$prev_queue" -ne 99999 ]; then
        echo "QUEUE_ABOVE_500: queue=$q -- batch launched; QUEUE_BELOW_500 will re-fire on next downcross"
    fi
    prev_queue=$q

    # ---- TRANS completion + extraction state ----
    # Completed = year-2020 (or configured) restart >1KB AND mtime > launch
    completed=$(find "$A2MC_ENSEMBLE_OUTPUT" \
                     -path "$TRANS_RESTART_PATH" \
                     -size +1k -newermt "$LAUNCH" 2>/dev/null | wc -l)
    # Extracted = monthly-extract NC exists AND mtime > LAUNCH (mtime filter
    # excludes any stale leftover NCs from prior rounds that share the
    # filename pattern — for R5 this caught the 4/13 subset_replay+PrescP
    # variant's 183 NCs; see 20260518b Addendum 1).
    extracted=$(find "$A2MC_EXTRACTED_DATA" -maxdepth 1 \
                     -name "$EXTRACTED_NC_GLOB" \
                     -newermt "$LAUNCH" 2>/dev/null | wc -l)
    needs=$((completed - extracted))

    if [ "$completed" -ne "$last_completed_announced" ]; then
        echo "TRANS_DONE: completed=$completed extracted=$extracted pending=$needs"
        last_completed_announced=$completed
    fi

    # ---- Trigger extraction if there's new work AND no extractor running ----
    if [ "$needs" -gt 0 ]; then
        active=$(ps -ef | grep -E "extract_ADSP_RGSP_slim|extract_monthly_variables_FATES" \
                 | grep -v grep | wc -l)
        if [ "$active" -eq 0 ]; then
            # Compute the list of completed-but-not-extracted case numbers.
            # Python helper handles the set-difference + mtime check (faster
            # than nested bash + find for this scale).
            A2MC_ENSEMBLE_OUTPUT="$A2MC_ENSEMBLE_OUTPUT" \
            A2MC_EXTRACTED_DATA="$A2MC_EXTRACTED_DATA" \
            A2MC_LAUNCH_TIME="$LAUNCH" \
            A2MC_TRANS_RESTART_PATH="$TRANS_RESTART_PATH" \
            A2MC_EXTRACTED_NC_GLOB="$EXTRACTED_NC_GLOB" \
            A2MC_CASE_NUM_REGEX="$CASE_NUM_REGEX" \
            NEEDS_LIST_FILE="$NEEDS_LIST_FILE" \
            python3 - <<'PYEOF'
import os, glob, re, subprocess
ens   = os.environ['A2MC_ENSEMBLE_OUTPUT']
ext   = os.environ['A2MC_EXTRACTED_DATA']
launch = os.environ['A2MC_LAUNCH_TIME']
trans_path = os.environ['A2MC_TRANS_RESTART_PATH']
extracted_glob = os.environ['A2MC_EXTRACTED_NC_GLOB']
case_num_re = re.compile(os.environ['A2MC_CASE_NUM_REGEX'])
needs_file = os.environ['NEEDS_LIST_FILE']

done = set()
res = subprocess.run(['find', ens, '-path', trans_path,
                      '-size', '+1k', '-newermt', launch],
                     capture_output=True, text=True)
for line in res.stdout.splitlines():
    m = case_num_re.search(line)
    if m: done.add(int(m.group(1)))

have = set()
launch_dt = subprocess.run(['date', '-d', launch, '+%s'],
                            capture_output=True, text=True)
launch_epoch = int(launch_dt.stdout.strip())
for f in glob.glob(f'{ext}/{extracted_glob}'):
    try:
        if os.path.getmtime(f) > launch_epoch:
            m = case_num_re.search(f)
            if m: have.add(int(m.group(1)))
    except OSError:
        pass

needs = sorted(done - have)
with open(needs_file, 'w') as f:
    for n in needs: f.write(f'{n}\n')
print(len(needs))
PYEOF
            n_list=$(wc -l < "$NEEDS_LIST_FILE")
            if [ "$n_list" -gt 0 ]; then
                TS=$(date +%Y%m%d_%H%M%S)
                echo "STARTING_EXTRACTION: cases=$n_list"
                # Slim ADSP/RGSP/TRANS extractor (A2MC-generic tool since 2026-05-31).
                nohup python3 -u "${A2MC_ROOT}/tools/extract_ADSP_RGSP_slim.py" \
                      "$NEEDS_LIST_FILE" 16 \
                      > "${LOG_DIR}/auto_monitor_slim_${TS}.log" 2>&1 &
                # Full TRANS monthly-variable extractor (A2MC-generic tool).
                nohup python3 -u "${A2MC_ROOT}/tools/extract_monthly_variables_FATES.py" \
                      --case-file "$NEEDS_LIST_FILE" --parallel 16 \
                      > "${LOG_DIR}/auto_monitor_trans_${TS}.log" 2>&1 &
            fi
        fi
    fi

    # ---- Auto-regenerate milestone plot (idempotent: REGEN_SKIP unless we
    # ---- crossed a milestone and the file doesn't exist; REGEN_DEFER if
    # ---- another plot job is in flight). See 20260514c §"Part 5 — Auto-
    # ---- regenerated milestone plots" for the dual-variant pattern, and
    # ---- use_cases/Kougarok/analysis/regen_milestone_plot.sh for the R5
    # ---- example of what this helper looks like.
    if [ -x "$REGEN_HELPER" ]; then
        bash "$REGEN_HELPER" || true
    fi

    # ---- Terminal condition: queue empty, no extractor running, no pending
    # ---- extraction. TARGET_TOTAL is informational because ADSP/RGSP/TRANS
    # ---- failures cap the achievable maximum below the target. Two
    # ---- consecutive idle polls (1 hour) before exit so a freshly-finished
    # ---- TRANS gets one more extraction chance.
    in_queue=$(squeue -u "$USER" -h --format="%j" 2>/dev/null \
               | grep -cE "$QUEUE_JOB_REGEX")
    active_extractor=$(ps -ef | grep -E "extract_ADSP_RGSP_slim|extract_monthly_variables_FATES" \
                       | grep -v grep | wc -l)
    if [ "$in_queue" -eq 0 ] && [ "$active_extractor" -eq 0 ] && [ "$needs" -eq 0 ]; then
        idle_consecutive=$((idle_consecutive + 1))
        echo "IDLE_TICK: $idle_consecutive/2 (queue=0 extractor=0 needs=0 extracted=$extracted/$TARGET_TOTAL)"
        if [ "$idle_consecutive" -ge 2 ]; then
            echo "ROUND_TERMINAL: extracted=$extracted/$TARGET_TOTAL (queue empty 2 polls, ensemble done)"
            break
        fi
    else
        idle_consecutive=0
    fi

    sleep "$POLL_INTERVAL"
done
