#!/usr/bin/env python3
"""
Diagnose which (case, phase) submissions failed when an auto-generated
restart_incomplete_{session}.sh hit QOSMaxSubmitJobPerUserLimit (or any
other sbatch error) partway through.

Why this is not just diagnose_ensemble_status.py:
  diagnose_ensemble_status.py looks at *run output* (restart files on
  disk) to decide what's incomplete. After a partial restart_*.sh run,
  the case folders are already in the correct post-edit state (xmlchange
  done, user_nl_elm sed'd, finidat appended, case.setup done) but the
  case.submit call did not reach SLURM. Re-running the original restart
  script would `sed -i '$ d'` AGAIN, removing two more real lines from
  user_nl_elm and corrupting it.

  This tool diffs the restart script (what it intended to submit)
  against `sacct` (what actually made it into SLURM), then emits a
  recovery script that does ONLY `cd <case_dir>; ./case.submit ...` —
  no xmlchange, no sed, no echo, no case.setup. The prep has already
  run; we only need to re-issue the submit.

Output files (written to <dir-of-restart-script>/tmp/ by default;
override with --output-dir). The tmp/ subdir is auto-created if
missing and is intended to be gitignored — these outputs regenerate
on every run.
  - restart_qos_diagnosis_{session}.csv    : per-case summary
  - restart_qos_resubmit_{session}.sh      : recovery script
  - restart_phases_submitted_{session}.txt : raw sacct dump (audit)

Usage:
  python tools/diagnose_qos_failures.py \\
      --restart-script restart_incomplete_20260501_214604.sh

  # If sacct's default lookback misses the start of your run:
  python tools/diagnose_qos_failures.py \\
      --restart-script restart_incomplete_20260501_214604.sh \\
      --start-time 2026-05-01T21:46:00

Author: Jing Tao with Claude
"""

from __future__ import print_function

import argparse
import os
import re
import subprocess
import sys
from collections import OrderedDict
from datetime import datetime

PHASE_ORDER = ('ADSP', 'RGSP', 'TRANS')
PHASE_RANK = {p: i for i, p in enumerate(PHASE_ORDER)}

# SLURM job states (sacct State column; may have suffixes like "CANCELLED by 12345")
DEP_DONE_STATES   = {'COMPLETED'}
DEP_ACTIVE_STATES = {'PENDING', 'RUNNING', 'REQUEUED', 'CONFIGURING', 'RESIZING', 'SUSPENDED'}
DEP_BAD_STATES    = {'FAILED', 'CANCELLED', 'TIMEOUT', 'NODE_FAIL',
                     'OUT_OF_MEMORY', 'BOOT_FAIL', 'DEADLINE'}


def parse_restart_script(path):
    """Parse a restart_incomplete_*.sh file.

    Returns:
        session_id (str | None)   - parsed from filename if matchable
        generated  (str | None)   - "Generated:" timestamp in header
        cases      (list[dict])   - each {'case_id': int, 'blocks': OrderedDict}
                                    where blocks maps phase -> dict with
                                    'case_dir', 'job_name', 'batch_args'.
    """
    with open(path) as f:
        text = f.read()

    m = re.search(r'^# Generated: (\S+\s+\S+)', text, re.MULTILINE)
    generated = m.group(1).split('.')[0] if m else None  # drop microseconds

    m = re.search(r'restart_incomplete_(\d{8}_\d{6})\.sh$', os.path.basename(path))
    session = m.group(1) if m else None

    # Each per-case block:
    #   # ============================
    #   # Case N: ...
    #   # Phases to submit: ...
    #   # ============================
    #   <body>
    case_re = re.compile(
        r'^# =+\s*\n'
        r'^# Case (\d+):.*?\n'
        r'^# .*?\n'           # "# Phases to submit: ..."
        r'^# =+\s*\n'
        r'(.*?)(?=^# =+\s*\n|\Z)',
        re.MULTILINE | re.DOTALL,
    )

    phase_re = re.compile(
        r'^# --- (ADSP|RGSP|TRANS) Phase ---\s*\n(.*?)(?=^# --- |\Z)',
        re.MULTILINE | re.DOTALL,
    )

    finidat_re = re.compile(r'echo "finidat = \'([^\']+)\'"\s*>>\s*user_nl_elm')

    cases = []
    for cm in case_re.finditer(text):
        case_id = int(cm.group(1))
        body = cm.group(2)
        blocks = OrderedDict()
        for pm in phase_re.finditer(body):
            phase = pm.group(1)
            block = pm.group(2)
            cd_m = re.search(r'^cd (\S+)', block, re.MULTILINE)
            case_dir = cd_m.group(1) if cd_m else None
            job_name = os.path.basename(case_dir) if case_dir else None
            ba_m = re.search(r'case\.submit --batch-args="([^"]+)"', block)
            batch_args = ba_m.group(1) if ba_m else ''
            # Strip any --dependency= from the captured batch_args; the
            # resubmit script will re-add deps based on current sacct state.
            batch_args_no_dep = re.sub(r'\s*--dependency=\S+', '', batch_args).strip()
            fi_m = finidat_re.search(block)
            expected_finidat = fi_m.group(1) if fi_m else None
            blocks[phase] = {
                'case_dir':         case_dir,
                'job_name':         job_name,
                'batch_args':       batch_args_no_dep,
                'expected_finidat': expected_finidat,
                'raw_block':        block.rstrip() + '\n',  # for verbatim re-emission
            }
        cases.append({'case_id': case_id, 'blocks': blocks})

    return session, generated, cases


def query_sacct(user, start_time):
    """Query sacct for all top-level jobs since start_time. Returns list of
    {'jobid', 'jobname', 'state'}. The most recent record per jobname wins
    (sacct returns chronological order)."""
    cmd = ['sacct', '-u', user, '-X',
           '--starttime', start_time,
           '--format=JobID,JobName%150,State',
           '-n', '-P']
    out = subprocess.check_output(cmd, universal_newlines=True)
    jobs = []
    for line in out.splitlines():
        parts = line.split('|')
        if len(parts) >= 3:
            jobs.append({
                'jobid':   parts[0].strip(),
                'jobname': parts[1].strip(),
                'state':   parts[2].strip().split()[0],  # "CANCELLED by 123" -> "CANCELLED"
            })
    return jobs


def match_jobs_to_cases(cases, jobs):
    """Build (case_id, phase) -> {'jobid', 'state'} from the cases' job_name
    expectations and the sacct dump. Latest record per name wins."""
    name_to_key = {}
    for c in cases:
        for phase, b in c['blocks'].items():
            if b['job_name']:
                name_to_key[b['job_name']] = (c['case_id'], phase)

    submitted = {}
    for j in jobs:
        jn = j['jobname']
        if jn.startswith('run.'):
            jn = jn[4:]
        key = name_to_key.get(jn)
        if key is not None:
            submitted[key] = {'jobid': j['jobid'], 'state': j['state']}
    return submitted


def diagnose(cases, submitted):
    """For each case, compute (expected_phases, submitted_phases, missing_phases).
    Returns list of dicts in script order. Sets prep_status='UNVERIFIED' by
    default; verify_prep() can fill it in afterwards."""
    rows = []
    for c in cases:
        cid = c['case_id']
        expected = list(c['blocks'].keys())
        submitted_phases = [p for p in expected if (cid, p) in submitted]
        missing_phases = [p for p in expected if (cid, p) not in submitted]
        if missing_phases:
            if set(missing_phases) == set(expected):
                status = 'NEED_FULL'
            else:
                status = 'NEED_PARTIAL'
        else:
            status = 'FULLY_SUBMITTED'
        rows.append({
            'case_id': cid,
            'expected': expected,
            'submitted': submitted_phases,
            'missing': missing_phases,
            'status': status,
            'prep_status': 'UNVERIFIED',
            'prep_per_phase': {},  # phase -> 'DONE' / 'PENDING' / 'NO_DIR' / 'NO_FILE'
        })
    return rows


def _phase_prep_state(case_dir, expected_finidat):
    """Inspect <case_dir>/user_nl_elm to decide whether the restart script's
    prep block already ran for this phase.

    Returns one of:
        'NO_PREP'  - the restart block has no prep (fresh-start phase: just
                     bare `./case.submit`); recovery is identical to DONE
        'DONE'     - expected finidat line is present in user_nl_elm
        'PENDING'  - user_nl_elm exists but does not contain the expected line
        'NO_DIR'   - case directory missing
        'NO_FILE'  - case dir exists but user_nl_elm missing
    """
    # No echo-finidat line in the original block means no prep is performed
    # (e.g., "Restart from {phase} (fresh)" first-phase blocks just submit).
    if not expected_finidat:
        return 'NO_PREP'
    if not case_dir or not os.path.isdir(case_dir):
        return 'NO_DIR'
    nl = os.path.join(case_dir, 'user_nl_elm')
    if not os.path.isfile(nl):
        return 'NO_FILE'
    needle = "finidat = '{}'".format(expected_finidat)
    try:
        with open(nl) as f:
            txt = f.read()
    except (IOError, OSError):
        return 'NO_FILE'
    return 'DONE' if needle in txt else 'PENDING'


def verify_prep(rows, cases):
    """For each row that needs recovery (NEED_PARTIAL / NEED_FULL), check
    user_nl_elm for the expected finidat line of every missing phase.
    Sets row['prep_status'] to one of:
        'PREP_DONE'    - all missing phases ready (DONE or NO_PREP)
        'PREP_PENDING' - all missing phases lack the expected finidat
        'PREP_MIXED'   - some missing phases prepped, others not (rare;
                         indicates the original script was killed mid-case)
        'PREP_ERROR'   - case dir or user_nl_elm missing on disk
    Also stores per-phase state in row['prep_per_phase']."""
    case_by_id = {c['case_id']: c for c in cases}
    for r in rows:
        if r['status'] == 'FULLY_SUBMITTED':
            r['prep_status'] = 'N/A'
            continue
        per_phase = {}
        c = case_by_id[r['case_id']]
        for phase in r['missing']:
            block = c['blocks'][phase]
            per_phase[phase] = _phase_prep_state(block['case_dir'],
                                                  block['expected_finidat'])
        r['prep_per_phase'] = per_phase
        states = set(per_phase.values())
        ok_states = {'DONE', 'NO_PREP'}
        error_states = {'NO_DIR', 'NO_FILE'}

        # Walk missing phases in script order to find the first PENDING one.
        # The script preps phases sequentially within a case, so if phase i
        # is PENDING (didn't run), phase i+1 also didn't run in this round
        # regardless of what its user_nl_elm shows (could be stale match
        # from an earlier restart iteration).
        first_pending_idx = None
        for i, phase in enumerate(r['missing']):
            if per_phase[phase] == 'PENDING':
                first_pending_idx = i
                break

        if error_states & states:
            r['prep_status'] = 'PREP_ERROR'
        elif first_pending_idx is None:
            # No PENDING anywhere -> all phases are DONE or NO_PREP
            r['prep_status'] = 'PREP_DONE'
        elif first_pending_idx == 0:
            # First missing phase wasn't prepped -> script never reached this
            # case in the current round; later DONE flags are stale.
            r['prep_status'] = 'PREP_PENDING'
        else:
            # Script ran prep on early missing phases then stopped before
            # the rest. Rare; flag for manual review (early phases need
            # bare submit, later need full prep — partial-splice required).
            r['prep_status'] = 'PREP_MIXED'
    return rows


def write_csv(out_path, rows):
    with open(out_path, 'w') as f:
        f.write('case_id,expected,submitted,missing,status,prep_status,prep_per_phase\n')
        for r in rows:
            ppp = ';'.join('{}={}'.format(p, s) for p, s in r['prep_per_phase'].items())
            f.write('{},{},{},{},{},{},{}\n'.format(
                r['case_id'],
                '+'.join(r['expected']),
                '+'.join(r['submitted']) or '-',
                '+'.join(r['missing']) or '-',
                r['status'],
                r['prep_status'],
                ppp or '-',
            ))


def write_sacct_dump(out_path, jobs):
    with open(out_path, 'w') as f:
        f.write('jobid|jobname|state\n')
        for j in jobs:
            f.write('{jobid}|{jobname}|{state}\n'.format(**j))


def _emit_prep_done_block(L, r, c, submitted, user):
    """Append lines for a prep-already-done recovery: bare ./case.submit
    chained via existing jobids (or freshly captured ones for NEED_FULL).
    Returns True on success, False if skipped."""
    cid = r['case_id']
    missing = r['missing']
    first_missing = missing[0]

    expected_in_order = list(c['blocks'].keys())
    first_pos = expected_in_order.index(first_missing)
    prereq_var = None
    if first_pos == 0:
        L.append('# (first phase in chain — no prereq dependency)')
    else:
        prereq_phase = expected_in_order[first_pos - 1]
        existing = submitted.get((cid, prereq_phase))
        if not existing:
            L.append('# WARNING: prereq phase {} missing from sacct — skipping case {}'.format(
                prereq_phase, cid))
            L.append('')
            return False
        state, jobid = existing['state'], existing['jobid']
        if state in DEP_DONE_STATES:
            L.append('# Prereq {} jobid={} state={} -> no afterok needed'.format(
                prereq_phase, jobid, state))
        elif state in DEP_ACTIVE_STATES:
            L.append('# Prereq {} jobid={} state={} -> chain via afterok'.format(
                prereq_phase, jobid, state))
            L.append('PREREQ_{}={}'.format(cid, jobid))
            prereq_var = 'PREREQ_{}'.format(cid)
        elif state in DEP_BAD_STATES:
            L.append('# WARNING: prereq {} jobid={} state={} — afterok will never satisfy.'
                     .format(prereq_phase, jobid, state))
            L.append('# Inspect manually before uncommenting the lines below.')
            L.append('# (skipped)')
            L.append('')
            return False
        else:
            L.append('# Prereq {} jobid={} state={} (unknown) -> defaulting to afterok'.format(
                prereq_phase, jobid, state))
            L.append('PREREQ_{}={}'.format(cid, jobid))
            prereq_var = 'PREREQ_{}'.format(cid)

    for i, phase in enumerate(missing):
        block = c['blocks'][phase]
        L.append('cd {}'.format(block['case_dir']))
        dep = ' --dependency=afterok:${{{}}}'.format(prereq_var) if prereq_var else ''
        base_args = block['batch_args']
        is_last = (i == len(missing) - 1)
        if is_last:
            L.append('./case.submit --batch-args="{}{}"'.format(base_args, dep))
        else:
            L.append('SUBMIT_OUTPUT=$(./case.submit --batch-args="{}{}" 2>&1)'.format(
                base_args, dep))
            L.append('echo "$SUBMIT_OUTPUT"')
            L.append('JOBID_{}_{}=$(echo "$SUBMIT_OUTPUT" | grep -oP '
                     '"(?:Submitted job id is |with id )\\K[0-9]+" | head -1)'.format(phase, cid))
            L.append('if [ -z "$JOBID_{p}_{c}" ]; then sleep 2; '
                     'JOBID_{p}_{c}=$(squeue -u {u} -n {jn} -h -o "%i" | head -1); fi'.format(
                p=phase, c=cid, u=user, jn=block['job_name']))
            prereq_var = 'JOBID_{}_{}'.format(phase, cid)
    L.append('echo "Case {} resubmitted (prep_done): {}"'.format(cid, ' -> '.join(missing)))
    L.append('')
    return True


def _emit_prep_pending_full_block(L, r, c):
    """Append the original (verbatim) restart blocks for a NEED_FULL case
    whose prep was never run. The original blocks are self-contained:
    they include xmlchange + sed + echo finidat + case.setup + case.submit
    with internal $JOBID_{phase}_{cid} dependency chaining."""
    cid = r['case_id']
    L.append('# (prep not yet run — emitting original block with full prep + submit chain)')
    for phase in r['missing']:
        block = c['blocks'][phase]
        L.append('# --- {} Phase ---'.format(phase))
        L.append(block['raw_block'].rstrip())
        L.append('')
    L.append('echo "Case {} resubmitted (prep_pending → full block): {}"'.format(
        cid, ' -> '.join(r['missing'])))
    L.append('')
    return True


def emit_resubmit_script(out_path, rows, cases, submitted, user, verified):
    """Generate the recovery script. Per-case dispatch:

        prep_status=PREP_DONE / N/A (unverified) → bare submit (prep-less)
        prep_status=PREP_PENDING + status=NEED_FULL → original block (full prep)
        prep_status=PREP_PENDING + status=NEED_PARTIAL → skip, manual review
            (would need to splice existing jobids into a re-prepped block)
        prep_status=PREP_MIXED / PREP_ERROR → skip, manual review
    """
    case_by_id = {c['case_id']: c for c in cases}
    needs_resubmit = [r for r in rows if r['status'] != 'FULLY_SUBMITTED']

    counts = {'prep_done': 0, 'prep_pending_full': 0, 'skipped': 0}
    skipped_reasons = {}

    L = []
    L.append('#!/bin/bash')
    L.append('# Auto-generated QOS-failure recovery script')
    L.append('# Generated: ' + datetime.now().isoformat(' ').split('.')[0])
    L.append('#')
    L.append('# RECOVERY CONTRACT')
    L.append('# -----------------')
    L.append('# Per-case dispatch based on whether the original restart')
    L.append('# script\'s prep block (xmlchange / sed / echo finidat /')
    L.append('# case.setup) already ran for the missing phases:')
    L.append('#')
    L.append('#   prep_status=PREP_DONE          -> bare ./case.submit (prep-less)')
    L.append('#   prep_status=PREP_PENDING(FULL) -> original block with full prep')
    L.append('#   prep_status=PREP_MIXED/ERROR   -> skipped, manual review')
    L.append('#   prep_status=N/A (unverified)   -> assumed PREP_DONE')
    L.append('#')
    if verified:
        L.append('# Prep verification: ENABLED (--verify-prep). Each missing phase\'s')
        L.append('# user_nl_elm was grepped for the expected `finidat = \'...\'` line.')
    else:
        L.append('# Prep verification: DISABLED. Re-run with --verify-prep if you')
        L.append('# may have killed the original restart script partway through.')
    L.append('#')
    L.append('# Before running: check `squeue -u $USER -h | wc -l` is well below')
    L.append('# the QOS MaxSubmitJobsPerUser limit (5000 on Perlmutter shared).')
    L.append('')
    L.append('set -o pipefail')
    L.append('')

    for r in needs_resubmit:
        cid = r['case_id']
        c = case_by_id[cid]
        L.append('# ============================================================')
        L.append('# Case {}: status={} prep={} expected={} missing={}'.format(
            cid, r['status'], r['prep_status'],
            '+'.join(r['expected']), '+'.join(r['missing'])))
        if r['prep_per_phase']:
            L.append('#   per-phase prep: {}'.format(
                ', '.join('{}={}'.format(p, s) for p, s in r['prep_per_phase'].items())))
        L.append('# ============================================================')

        # Dispatch
        if r['prep_status'] in ('PREP_DONE', 'N/A'):
            ok = _emit_prep_done_block(L, r, c, submitted, user)
            if ok:
                counts['prep_done'] += 1
            else:
                counts['skipped'] += 1
                skipped_reasons[cid] = 'prep_done_path_failed'
        elif r['prep_status'] == 'PREP_PENDING' and r['status'] == 'NEED_FULL':
            _emit_prep_pending_full_block(L, r, c)
            counts['prep_pending_full'] += 1
        else:
            reason = r['prep_status']
            if r['prep_status'] == 'PREP_PENDING' and r['status'] == 'NEED_PARTIAL':
                reason = 'PREP_PENDING_PARTIAL (would need splice; do it manually)'
            L.append('# WARNING: case {} skipped — {}'.format(cid, reason))
            L.append('# (Inspect case dir, decide between manual prep+submit or full re-run.)')
            L.append('')
            counts['skipped'] += 1
            skipped_reasons[cid] = reason

    with open(out_path, 'w') as f:
        f.write('\n'.join(L))
    os.chmod(out_path, 0o755)
    return counts, skipped_reasons


def main():
    p = argparse.ArgumentParser(
        description='Diagnose QOS-limit submission failures from a restart script run.')
    p.add_argument('--restart-script', required=True,
                   help='Path to the restart_incomplete_*.sh that was run.')
    p.add_argument('--start-time',
                   help='sacct --starttime (ISO). Default: parsed from script header.')
    p.add_argument('--user', default=os.environ.get('USER'),
                   help='SLURM user (default: $USER).')
    p.add_argument('--output-dir',
                   help='Directory for output files. Default: <dir-of-restart-script>/tmp/ '
                        '(auto-created if missing). Outputs are transient; they are not meant '
                        'to be tracked in git.')
    p.add_argument('--no-resubmit-script', action='store_true',
                   help='Skip generating restart_qos_resubmit_*.sh (diagnosis only).')
    p.add_argument('--verify-prep', action='store_true',
                   help='For each case needing recovery, grep its user_nl_elm for the '
                        'expected finidat path to confirm the original restart script\'s '
                        'prep block ran. Without this flag, prep is assumed done '
                        '(safe only if the original restart script ran to completion).')
    args = p.parse_args()

    script_path = os.path.abspath(args.restart_script)
    if not os.path.isfile(script_path):
        sys.exit('ERROR: restart script not found: ' + script_path)

    if args.output_dir:
        out_dir = os.path.abspath(args.output_dir)
        if not os.path.isdir(out_dir):
            sys.exit('ERROR: --output-dir does not exist: ' + out_dir)
    else:
        # Default: <dir-of-restart-script>/tmp/  (auto-create if missing).
        # We write outputs into a tmp/ subdir so they're easy to gitignore
        # in bulk and don't clutter the project root.
        out_dir = os.path.join(os.path.dirname(script_path), 'tmp')
        if not os.path.isdir(out_dir):
            try:
                os.makedirs(out_dir)
                print('Created default output dir: ' + out_dir)
            except OSError as e:
                sys.exit('ERROR: cannot create default output dir {}: {}'.format(out_dir, e))

    print('Parsing {} ...'.format(script_path))
    session, generated, cases = parse_restart_script(script_path)
    if not cases:
        sys.exit('ERROR: no case blocks parsed from script — bad format?')
    print('  session_id : {}'.format(session))
    print('  generated  : {}'.format(generated))
    print('  cases      : {}'.format(len(cases)))

    if args.start_time:
        start_time = args.start_time
    elif generated:
        # "2026-05-01 21:46:04" -> "2026-05-01T21:46:04"
        start_time = generated.replace(' ', 'T')
    else:
        sys.exit('ERROR: cannot determine sacct --starttime; use --start-time.')
    print('  starttime  : {}'.format(start_time))
    if not session:
        # Fallback session id from start_time
        session = re.sub(r'[^0-9]', '', start_time)[:14]

    print('Querying sacct for user={} since {} ...'.format(args.user, start_time))
    jobs = query_sacct(args.user, start_time)
    print('  jobs returned: {}'.format(len(jobs)))

    submitted = match_jobs_to_cases(cases, jobs)
    print('  matched (case, phase) pairs: {}'.format(len(submitted)))

    rows = diagnose(cases, submitted)

    if args.verify_prep:
        n_to_check = sum(1 for r in rows if r['status'] != 'FULLY_SUBMITTED')
        print('Verifying prep state for {} cases needing recovery '
              '(reading user_nl_elm) ...'.format(n_to_check))
        verify_prep(rows, cases)

    # Summary
    by_status = {}
    for r in rows:
        by_status.setdefault(r['status'], 0)
        by_status[r['status']] += 1
    print()
    print('Summary:')
    for s in ('FULLY_SUBMITTED', 'NEED_PARTIAL', 'NEED_FULL'):
        print('  {:<16}: {}'.format(s, by_status.get(s, 0)))

    if args.verify_prep:
        # Per-status x prep_status breakdown
        prep_breakdown = {}
        for r in rows:
            if r['status'] == 'FULLY_SUBMITTED':
                continue
            key = (r['status'], r['prep_status'])
            prep_breakdown[key] = prep_breakdown.get(key, 0) + 1
        if prep_breakdown:
            print()
            print('Prep verification breakdown:')
            for (st, ps), n in sorted(prep_breakdown.items()):
                print('  {:<14} prep={:<14} count={}'.format(st, ps, n))

    # Per-missing-pattern breakdown for partial cases
    partial_breakdown = {}
    for r in rows:
        if r['status'] == 'NEED_PARTIAL':
            key = '+'.join(r['missing'])
            partial_breakdown[key] = partial_breakdown.get(key, 0) + 1
    if partial_breakdown:
        print()
        print('NEED_PARTIAL breakdown by missing phases:')
        for k in sorted(partial_breakdown):
            print('  missing={:<16} count={}'.format(k, partial_breakdown[k]))

    # Write outputs
    csv_path    = os.path.join(out_dir, 'restart_qos_diagnosis_{}.csv'.format(session))
    sacct_path  = os.path.join(out_dir, 'restart_phases_submitted_{}.txt'.format(session))
    write_csv(csv_path, rows)
    write_sacct_dump(sacct_path, jobs)

    print()
    print('Outputs:')
    print('  diagnosis  : {}'.format(csv_path))
    print('  sacct dump : {}'.format(sacct_path))

    if not args.no_resubmit_script:
        sh_path = os.path.join(out_dir, 'restart_qos_resubmit_{}.sh'.format(session))
        counts, _ = emit_resubmit_script(sh_path, rows, cases, submitted,
                                          args.user, args.verify_prep)
        print('  resubmit   : {}'.format(sh_path))
        print('  recovery counts: prep_done={} prep_pending_full={} skipped={}'.format(
            counts['prep_done'], counts['prep_pending_full'], counts['skipped']))
        print()
        if args.verify_prep:
            print('Inspect the resubmit script before running. PREP_DONE cases use bare')
            print('./case.submit; PREP_PENDING NEED_FULL cases re-emit the full original')
            print('block. Mixed/Unknown cases are flagged with WARNING comments.')
        else:
            print('Inspect the resubmit script before running. It assumes prep ran for')
            print('every case (safe only if the original restart script completed). If you')
            print('killed the original partway through, re-run this tool with --verify-prep.')


if __name__ == '__main__':
    main()
