#!/bin/bash
# ensemble_auto_monitor.sh — A2MC generic HPC ensemble auto-monitor.
#
# =============================================================================
# WHAT THIS IS
# =============================================================================
# Config-driven autonomous monitor for an A2MC FATES ensemble on SLURM. It is
# the generalized version of use_cases/Kougarok/analysis/r5_auto_monitor.sh and
# is intended to serve BOTH reuse paths:
#
#   * ONLINE  Phase 0 — orchestrator-driven Morris ensembles. The orchestrator
#     submits the ADSP/RGSP/TRANS phases; this monitor watches the queue, kicks
#     extraction on TRANS completion, and regenerates the milestone plots.
#   * OFFLINE Phase-0-mimic — a hand-submitted whole-ensemble run (e.g. a Morris
#     re-run on a new FATES branch). Same lifecycle, no orchestrator.
#
# Everything that used to be an R5 literal is now a CLI flag or an env var with
# an R5-matching default. Per-round instances (r5_auto_monitor.sh, future
# r6_auto_monitor.sh, ...) are thin wrappers that set the round-specific values
# and exec this script, so muscle-memory invocations and live `ps`/Monitor
# wiring keep working.
#
# NOTE: This complements tools/hpc_ensemble_monitor_template.sh, which is the
# copy-and-edit template form. This file is the flag/env-driven form that the
# round wrappers exec directly (no copy needed).
#
# Side-effects per poll:
#   1. Emit SLURM queue-depth + threshold-crossing events on stdout
#   2. Detect new TRANS-phase completions on disk + auto-trigger extraction
#   3. Invoke the milestone-plot regen helper (idempotent)
#   4. Track consecutive-idle polls and exit on terminal-idle (NOT count-based)
#
# =============================================================================
# USAGE
# =============================================================================
#   source a2mc_config.sh
#   source use_cases/<site>/config/<site>_config_rN.sh
#   nohup bash tools/ensemble_auto_monitor.sh [flags] >> <log> 2>&1 &
#
# Flags (each also has an env-var equivalent; the flag wins):
#   --launch "YYYY-MM-DD HH:MM:SS"  mtime cutoff for "fresh" files   [A2MC_LAUNCH_TIME]
#   --target-total N                informational ensemble size      [A2MC_TARGET_TOTAL]
#   --label STR                     prefix for the *_TERMINAL event  [A2MC_ENSEMBLE_LABEL, default ENSEMBLE]
#   --poll-interval SECONDS         poll cadence                     [A2MC_POLL_INTERVAL_SECONDS, default 1800]
#   --max-case-num N                ignore case numbers > N (e.g. exclude out-of-Morris
#                                   experiment cases 5001+)          [A2MC_MAX_CASE_NUM, default unbounded]
#   --regen-helper PATH             milestone-plot regen helper      [A2MC_REGEN_HELPER]
#   --milestone-step N              passed through to the regen helper[A2MC_MILESTONE_STEP, default 250]
#
# Derived automatically from $A2MC_CASE_NAME_PATTERN (no hardcoded PrescP):
#   * the TRANS extracted-NC glob   = pattern{N=*,PHASE=TRANS}_all_variables_monthly_*.nc
#   * the case-number regex         = pattern with {N}->(\d+), {PHASE}->TRANS
#   * the in-queue job regex        = pattern{N=[0-9]+,PHASE=(ADSP|RGSP|TRANS)}
# (the same substitution plot_all_extracted.py's _build_case_regex performs).
#
# =============================================================================
# EVENTS EMITTED ON STDOUT (kept identical to the R5 vocabulary so existing
# Monitor-arming filters and the arm-hpc-monitoring skill still match)
# =============================================================================
#   QUEUE_DEPTH: queue=<N> running=<R> pending=<P>
#   QUEUE_BELOW_1000: queue=<N>   (downward crossing)
#   QUEUE_BELOW_500: queue=<N>    (downward crossing)
#   QUEUE_ABOVE_500: queue=<N>    (upward crossing — a batch was just launched)
#   TRANS_DONE: completed=<C> extracted=<E> pending=<C-E>
#   STARTING_EXTRACTION: cases=<N>
#   IDLE_TICK: <n>/2 (queue=0 extractor=0 needs=0 extracted=<E>/<T>)
#   <LABEL>_TERMINAL: extracted=<E>/<T>   (final exit, ensemble done)
#   REGEN_LAUNCHED / REGEN_SKIP / REGEN_DEFER   (forwarded from the regen helper)
#
# The *_TERMINAL event is prefixed by --label (default ENSEMBLE), so the R5
# wrapper passes --label R5 to keep emitting the historical "R5_TERMINAL".
#
# =============================================================================
# DESIGN NOTES (full history in 20260514c + 20260518b dev_logs)
# =============================================================================
# * Stop on terminal-idle (queue empty AND no extractor AND needs=0 for 2 polls),
#   NOT on a count check against --target-total: ADSP/RGSP/TRANS failures cap the
#   achievable maximum below the nominal total, so a count-based stop never fires.
# * Queue thresholds use crossing detection (prev_queue vs current) so each
#   downcross emits exactly one signal; re-armable across multiple batch launches.
# * 2-tick idle window before exit lets a TRANS that finishes between polls get
#   one more extraction chance.
# * NERSC rule: this script writes only under $A2MC_ROOT/tmp — never /tmp,
#   /scratch, $TMPDIR, /dev/shm, or /global/cfs.
# =============================================================================

set -u

# -----------------------------------------------------------------------------
# CLI parsing (flags override env vars).
# -----------------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --launch)         A2MC_LAUNCH_TIME="$2";          shift 2 ;;
        --target-total)   A2MC_TARGET_TOTAL="$2";         shift 2 ;;
        --label)          A2MC_ENSEMBLE_LABEL="$2";       shift 2 ;;
        --poll-interval)  A2MC_POLL_INTERVAL_SECONDS="$2"; shift 2 ;;
        --max-case-num)   A2MC_MAX_CASE_NUM="$2";         shift 2 ;;
        --regen-helper)   A2MC_REGEN_HELPER="$2";         shift 2 ;;
        --milestone-step) A2MC_MILESTONE_STEP="$2";       shift 2 ;;
        -h|--help)        sed -n '2,75p' "$0"; exit 0 ;;
        *) echo "ERROR: unknown flag: $1" >&2; exit 2 ;;
    esac
done

# -----------------------------------------------------------------------------
# Config validation — fail fast on missing required values.
# -----------------------------------------------------------------------------
required=(A2MC_ROOT A2MC_EXTRACTED_DATA A2MC_ENSEMBLE_OUTPUT
          A2MC_CASE_NAME_PATTERN A2MC_LAUNCH_TIME A2MC_TARGET_TOTAL)
missing=0
for v in "${required[@]}"; do
    if [ -z "${!v:-}" ]; then
        echo "ERROR: required value \$$v is not set. Source a2mc_config.sh + the round config, or pass the matching flag." >&2
        missing=1
    fi
done
[ "$missing" -eq 1 ] && exit 2

# -----------------------------------------------------------------------------
# Resolve config with R5-matching defaults.
# -----------------------------------------------------------------------------
LAUNCH="$A2MC_LAUNCH_TIME"
TARGET_TOTAL="$A2MC_TARGET_TOTAL"
LABEL="${A2MC_ENSEMBLE_LABEL:-ENSEMBLE}"
POLL_INTERVAL="${A2MC_POLL_INTERVAL_SECONDS:-1800}"
MAX_CASE_NUM="${A2MC_MAX_CASE_NUM:-}"          # empty = no upper bound
MILESTONE_STEP="${A2MC_MILESTONE_STEP:-250}"
NEEDS_LIST_FILE="${A2MC_NEEDS_LIST_FILE:-${A2MC_ROOT}/tmp/ensemble_auto_needs.txt}"
LOG_DIR="${A2MC_AUTOMON_LOG_DIR:-${A2MC_ROOT}/tmp}"
REGEN_HELPER="${A2MC_REGEN_HELPER:-${A2MC_ROOT}/tools/regen_ensemble_milestone_plot.sh}"
TRANS_RESTART_PATH="${A2MC_TRANS_RESTART_PATH:-*_TRANS/run/*.elm.r.2020-01-01-00000.nc}"
CASE_PATTERN="$A2MC_CASE_NAME_PATTERN"

# Derive the case-name stem (everything except the {N}/{PHASE} placeholders is
# literal), exactly the way plot_all_extracted.py builds its regex. This is what
# keeps the glob/regex free of any hardcoded "PrescP".
#   * EXTRACTED_NC_GLOB : pattern with N=* PHASE=TRANS, + monthly suffix
#   * CASE_NUM_REGEX    : pattern with N=(digits) PHASE=TRANS, anchored on suffix
#   * QUEUE_JOB_REGEX   : pattern with N=(digits) PHASE=(ADSP|RGSP|TRANS)
EXTRACTED_NC_GLOB="${A2MC_EXTRACTED_NC_GLOB:-}"
if [ -z "$EXTRACTED_NC_GLOB" ]; then
    glob_stem="${CASE_PATTERN//\{N\}/*}"
    glob_stem="${glob_stem//\{PHASE\}/TRANS}"
    EXTRACTED_NC_GLOB="${glob_stem}_all_variables_monthly_*.nc"
fi

# State variables.
prev_queue=99999              # sentinel: forces first-poll downcross detection
idle_consecutive=0
last_completed_announced=0

echo "ENSEMBLE_MONITOR_START: label=$LABEL launch='$LAUNCH' target=$TARGET_TOTAL pattern='$CASE_PATTERN' max_case_num='${MAX_CASE_NUM:-none}' glob='$EXTRACTED_NC_GLOB'"

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
    # Completed = final-year restart >1KB AND mtime > launch.
    completed=$(find "$A2MC_ENSEMBLE_OUTPUT" \
                     -path "$TRANS_RESTART_PATH" \
                     -size +1k -newermt "$LAUNCH" 2>/dev/null | wc -l)
    # Extracted = monthly-extract NC exists AND mtime > LAUNCH (mtime filter
    # excludes stale leftover NCs from prior rounds that share the pattern).
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
            # Compute completed-but-not-extracted case numbers. Python helper
            # builds the case-number regex from the case-name PATTERN (matching
            # plot_all_extracted.py's _build_case_regex), applies the optional
            # --max-case-num cap, and writes the needs list. NERSC-safe: the
            # needs file lives under $A2MC_ROOT/tmp.
            A2MC_ENSEMBLE_OUTPUT="$A2MC_ENSEMBLE_OUTPUT" \
            A2MC_EXTRACTED_DATA="$A2MC_EXTRACTED_DATA" \
            A2MC_LAUNCH_TIME="$LAUNCH" \
            A2MC_TRANS_RESTART_PATH="$TRANS_RESTART_PATH" \
            A2MC_EXTRACTED_NC_GLOB="$EXTRACTED_NC_GLOB" \
            A2MC_CASE_NAME_PATTERN="$CASE_PATTERN" \
            A2MC_MAX_CASE_NUM="$MAX_CASE_NUM" \
            NEEDS_LIST_FILE="$NEEDS_LIST_FILE" \
            python3 - <<'PYEOF'
import os, glob, re, subprocess

ens   = os.environ['A2MC_ENSEMBLE_OUTPUT']
ext   = os.environ['A2MC_EXTRACTED_DATA']
launch = os.environ['A2MC_LAUNCH_TIME']
trans_path = os.environ['A2MC_TRANS_RESTART_PATH']
extracted_glob = os.environ['A2MC_EXTRACTED_NC_GLOB']
pattern = os.environ['A2MC_CASE_NAME_PATTERN']
max_case_num = os.environ.get('A2MC_MAX_CASE_NUM', '').strip()
max_case_num = int(max_case_num) if max_case_num else None
needs_file = os.environ['NEEDS_LIST_FILE']

# Build case-number regex from the PATTERN the same way plot_all_extracted.py
# does: substitute {N}=marker, {PHASE}=TRANS, escape, swap marker for (\d+).
marker = '___CASENUM___'
template = pattern.format(N=marker, PHASE='TRANS')
case_num_re = re.compile(re.escape(template).replace(marker, r'(\d+)'))

def in_scope(n):
    return max_case_num is None or n <= max_case_num

done = set()
res = subprocess.run(['find', ens, '-path', trans_path,
                      '-size', '+1k', '-newermt', launch],
                     capture_output=True, text=True)
for line in res.stdout.splitlines():
    m = case_num_re.search(line)
    if m and in_scope(int(m.group(1))):
        done.add(int(m.group(1)))

have = set()
launch_dt = subprocess.run(['date', '-d', launch, '+%s'],
                            capture_output=True, text=True)
launch_epoch = int(launch_dt.stdout.strip())
for f in glob.glob(f'{ext}/{extracted_glob}'):
    try:
        if os.path.getmtime(f) > launch_epoch:
            m = case_num_re.search(f)
            if m and in_scope(int(m.group(1))):
                have.add(int(m.group(1)))
    except OSError:
        pass

needs = sorted(done - have)
with open(needs_file, 'w') as f:
    for n in needs:
        f.write(f'{n}\n')
print(len(needs))
PYEOF
            n_list=$(wc -l < "$NEEDS_LIST_FILE")
            if [ "$n_list" -gt 0 ]; then
                TS=$(date +%Y%m%d_%H%M%S)
                echo "STARTING_EXTRACTION: cases=$n_list"
                # Slim ADSP/RGSP/TRANS extractor (A2MC-generic tool).
                nohup python3 -u "${A2MC_ROOT}/tools/extract_ADSP_RGSP_slim.py" \
                      "$NEEDS_LIST_FILE" 16 \
                      > "${LOG_DIR}/ensemble_auto_slim_${TS}.log" 2>&1 &
                # Full TRANS monthly-variable extractor (A2MC-generic tool).
                nohup python3 -u "${A2MC_ROOT}/tools/extract_monthly_variables_FATES.py" \
                      --case-file "$NEEDS_LIST_FILE" --parallel 16 \
                      > "${LOG_DIR}/ensemble_auto_trans_${TS}.log" 2>&1 &
            fi
        fi
    fi

    # ---- Auto-regenerate milestone plots (idempotent). The regen helper is
    # ---- itself config-driven; we pass the milestone step through.
    if [ -f "$REGEN_HELPER" ]; then
        A2MC_MILESTONE_STEP="$MILESTONE_STEP" bash "$REGEN_HELPER" "$MILESTONE_STEP" || true
    fi

    # ---- Terminal condition: queue empty, no extractor, no pending extraction.
    # ---- Two consecutive idle polls before exit.
    # Build the in-queue regex from the pattern: N->[0-9]+, PHASE->(ADSP|RGSP|TRANS)
    qre="${CASE_PATTERN//\{N\}/[0-9]+}"
    qre="${qre//\{PHASE\}/(ADSP|RGSP|TRANS)}"
    in_queue=$(squeue -u "$USER" -h --format="%j" 2>/dev/null \
               | grep -cE "$qre")
    active_extractor=$(ps -ef | grep -E "extract_ADSP_RGSP_slim|extract_monthly_variables_FATES" \
                       | grep -v grep | wc -l)
    if [ "$in_queue" -eq 0 ] && [ "$active_extractor" -eq 0 ] && [ "$needs" -eq 0 ]; then
        idle_consecutive=$((idle_consecutive + 1))
        echo "IDLE_TICK: $idle_consecutive/2 (queue=0 extractor=0 needs=0 extracted=$extracted/$TARGET_TOTAL)"
        if [ "$idle_consecutive" -ge 2 ]; then
            echo "${LABEL}_TERMINAL: extracted=$extracted/$TARGET_TOTAL (queue empty 2 polls, ensemble done)"
            break
        fi
    else
        idle_consecutive=0
    fi

    sleep "$POLL_INTERVAL"
done
