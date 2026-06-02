#!/usr/bin/env python3
"""
Diagnose and restart incomplete ELM-FATES ensemble simulations.

This script scans the ensemble output directory to identify:
1. Which cases have completed all phases (all 3 phases have final restart files)
2. Which cases are stuck in which phase
3. The last restart file year for each incomplete case
4. Generates restart scripts for incomplete cases

FIXED VERSION: Corrects restart logic based on MATLAB templates:
- Uses RUN_STARTDATE + finidat approach (not CONTINUE_RUN)
- Correctly calculates STOP_N = end_year - restart_year + 1
- Handles finidat in user_nl_elm (ADSP strips 2 lines and conditionally
  re-adds `nyears_ad_carbon_only = K` if restart_year <= K, where K is read
  from $A2MC_ADSP_NYEARS_AD_CARBON_ONLY in a2mc_config.sh; RGSP/TRANS strips 1)
- Handles fresh starts by pointing to previous phase's restart file

- It creates restart_incomplete_{timestamp}.sh
  - The script contains ./case.submit commands for each incomplete case
  - IMPORTANT: When restarting ADSP, it also submits RGSP and TRANS with SLURM dependencies
  - Uses job ID capture to chain phases: ADSP → RGSP (afterok) → TRANS (afterok)
  - If RGSP/TRANS cases not created yet, runs existing case script to create them first
  - You need to manually run the generated script on HPC

Output files generated:
  1. ensemble_status_report_{timestamp}.txt - CSV status of all cases (includes error info)
  2. completed_cases_{timestamp}.txt - List of completed case numbers
  3. incomplete_cases_{timestamp}.txt - List of incomplete cases with details
  4. error_cases_{timestamp}.txt - List of cases with errors needing manual fix
  5. recreate_cases_{timestamp}.txt - List of cases needing recreation (case creation failed)
  6. recreate_cases_{timestamp}.sh - Script to recreate failed cases
  7. restart_incomplete_{timestamp}.sh - Executable restart script

Validation checks:
  - Verifies restart files have non-zero size (0-byte files are placeholders from failed runs)
  - Verifies case was created correctly (case.submit, user_nl_elm, .case.run exist)
  - Verifies previous phase completed with valid restart file (ADSP→RGSP, RGSP→TRANS)
  - Scans case creation log files for errors (disk quota, permission, etc.)
  - Cases needing recreation are separated from those that can be restarted

Usage:
    python diagnose_ensemble_status.py                    # Diagnose only
    python diagnose_ensemble_status.py --restart          # Generate restart script
    python diagnose_ensemble_status.py --cases 2-100      # Check specific range
    python diagnose_ensemble_status.py --cases 1,5,10     # Check individual cases
    python diagnose_ensemble_status.py --cases 1-50,100,200-300  # Mixed ranges and individuals
    python diagnose_ensemble_status.py --parallel 8       # Use 8 parallel workers
"""

import os
import re
import glob
import argparse
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# Configuration - loaded from a2mc_config.sh via environment variables
# Source a2mc_config.sh and site config before running:
#   source a2mc_config.sh
#   source use_cases/{site}/config/{site}_config.sh
try:
    from config import config
    OUTPUT_ROOT = config.ENSEMBLE_OUTPUT
    SCRIPT_DIR = f"{config.E3SM_ROOT}/cime/scripts"
    CASE_PREFIX = config.CASE_PREFIX
    LOG_DIR = config.LOG_DIR
    CASE_SCRIPTS_DIR = config.CASE_SCRIPTS
    TOTAL_ENSEMBLE = config.TOTAL_ENSEMBLE
except ImportError:
    # Fallback: read from environment variables (no hardcoded defaults)
    OUTPUT_ROOT = os.environ.get('A2MC_ENSEMBLE_OUTPUT', '')
    SCRIPT_DIR = os.environ.get('A2MC_E3SM_ROOT', '') + "/cime/scripts"
    CASE_PREFIX = os.environ.get('A2MC_ENSEMBLE_PREFIX', '')
    LOG_DIR = os.environ.get('A2MC_LOG_DIR', '')
    CASE_SCRIPTS_DIR = os.environ.get('A2MC_CASE_SCRIPTS', '')
    TOTAL_ENSEMBLE = int(os.environ.get('A2MC_TOTAL_ENSEMBLE', '0'))

# Case name pattern: how to construct case directory names from case number and phase
# Uses {N} for case number and {PHASE} for phase name (ADSP, RGSP, TRANS)
# Example: "Kougarok_ELM-FATES_PtCNPEn{N}_{PHASE}"
# Fallback: "{CASE_PREFIX}{N}_{PHASE}" (legacy behavior)
CASE_NAME_PATTERN = os.environ.get(
    'A2MC_CASE_NAME_PATTERN',
    f"{CASE_PREFIX}{{N}}_{{PHASE}}"
)

def make_case_name(case_num, phase):
    """Build case directory name from case number and phase."""
    return CASE_NAME_PATTERN.format(N=case_num, PHASE=phase)

# Validate configuration
if not OUTPUT_ROOT:
    print("ERROR: A2MC_ENSEMBLE_OUTPUT not set. Source a2mc_config.sh and site config first.")
    print("  source a2mc_config.sh")
    print("  source use_cases/{site}/config/{site}_config.sh")

# Case script pattern (used to recreate failed cases) - loaded from config
CASE_SCRIPT_PATTERN = os.environ.get('A2MC_CASE_SCRIPT_PATTERN', '{CASE_PREFIX}_En{N}.sh')

# Forcing data cycle length (ADSP/RGSP recycle forcing over this many years)
# Default: 1920 - 1901 + 1 = 20 years
_spinup_start = int(os.environ.get('A2MC_SPINUP_START_YEAR', '1901'))
_spinup_end = int(os.environ.get('A2MC_SPINUP_END_YEAR', '1920'))
FORCING_CYCLE_LENGTH = _spinup_end - _spinup_start + 1

# AD-carbon-only window — number of (calendar) years from RUN_STARTDATE during
# which the ELM/FATES gate `yr .le. nyears_ad_carbon_only` runs the model in
# AD-carbon-only mode. Set in a2mc_config.sh as A2MC_ADSP_NYEARS_AD_CARBON_ONLY.
# Used by the ADSP-continue prep block to decide whether to re-append
# `nyears_ad_carbon_only = K` after stripping (only if restart_year <= K).
NYEARS_AD_CARBON_ONLY = int(os.environ.get('A2MC_ADSP_NYEARS_AD_CARBON_ONLY', '30'))

# Phase definitions
# - duration: how many years to simulate
# - start_year: first year of simulation
# - end_year: last year of simulation (for STOP_N calculation)
# - final_year: year of final restart file (end_year + 1)
# - restart_interval: how often restart files are written
PHASES = {
    'ADSP': {
        'duration': 200,
        'start_year': 1,
        'end_year': 200,
        'final_year': 201,
        'restart_interval': 10,
        'prev_phase': None
    },
    'RGSP': {
        'duration': 200,
        'start_year': 201,
        'end_year': 400,
        'final_year': 401,
        'restart_interval': 10,
        'prev_phase': 'ADSP'
    },
    'TRANS': {
        'duration': 119,
        'start_year': 1901,
        'end_year': 2019,  # Last simulated year; restart at 2020-01-01
        'final_year': 2020,
        'restart_interval': 1,
        'prev_phase': 'RGSP'
    }
}


def get_restart_files(case_dir, min_size_bytes=1000):
    """Find all valid restart files (*.elm.r.*.nc) and return sorted list of years.

    Note: We use restart files, NOT history output files (*.elm.h0.*.nc).
    The last restart year may differ from last output year due to REST_N setting.

    Args:
        case_dir: Path to case output directory
        min_size_bytes: Minimum file size to consider valid (default 1KB).
                        Files with 0 bytes are placeholders from failed runs.

    Returns:
        List of years with valid restart files (sorted)
    """
    run_dir = os.path.join(case_dir, "run")
    if not os.path.isdir(run_dir):
        return []

    restart_pattern = os.path.join(run_dir, "*.elm.r.*.nc")
    restart_files = glob.glob(restart_pattern)

    years = []
    for f in restart_files:
        # Check file size - skip 0-byte placeholders
        try:
            file_size = os.path.getsize(f)
            if file_size < min_size_bytes:
                continue  # Skip invalid/placeholder files
        except OSError:
            continue

        # Extract year from: CASENAME.elm.r.YYYY-MM-DD-SSSSS.nc
        match = re.search(r'\.elm\.r\.(\d{4})-\d{2}-\d{2}', f)
        if match:
            years.append(int(match.group(1)))

    return sorted(years)


def check_case_creation(case_num, phase):
    """Check if a case was created correctly (script directory exists with key files).

    Returns:
        dict with 'valid' (bool) and 'error' (str) keys
    """
    case_name = make_case_name(case_num, phase)
    script_path = os.path.join(SCRIPT_DIR, case_name)

    errors = []

    # Check if case directory exists in SCRIPT_DIR
    if not os.path.isdir(script_path):
        return {'valid': False, 'error': 'case_dir_missing', 'script_path': script_path}

    # Check for key files that indicate successful case creation
    key_files = ['case.submit', 'user_nl_elm', '.case.run']
    for f in key_files:
        if not os.path.exists(os.path.join(script_path, f)):
            errors.append(f'{f}_missing')

    if errors:
        return {'valid': False, 'error': ','.join(errors), 'script_path': script_path}

    return {'valid': True, 'error': None, 'script_path': script_path}


def check_prev_phase_restart(case_num, phase, min_size_bytes=1000):
    """Check if previous phase has a valid final restart file.

    Args:
        case_num: Case number
        phase: Current phase (RGSP or TRANS)
        min_size_bytes: Minimum file size to consider valid

    Returns:
        dict with 'exists' (bool), 'path' (str), 'error' (str), and 'size' (int) keys
    """
    phase_info = PHASES[phase]
    prev_phase = phase_info.get('prev_phase')

    if not prev_phase:
        return {'exists': True, 'path': None, 'error': None, 'size': None}  # ADSP has no prev phase

    prev_final_year = PHASES[prev_phase]['final_year']
    prev_case_name = make_case_name(case_num, prev_phase)
    prev_restart_file = f"{OUTPUT_ROOT}/{prev_case_name}/run/{prev_case_name}.elm.r.{prev_final_year:04d}-01-01-00000.nc"

    if os.path.exists(prev_restart_file):
        try:
            file_size = os.path.getsize(prev_restart_file)
            if file_size < min_size_bytes:
                return {'exists': False, 'path': prev_restart_file,
                        'error': f'prev_restart_invalid:{prev_phase}:size={file_size}', 'size': file_size}
            return {'exists': True, 'path': prev_restart_file, 'error': None, 'size': file_size}
        except OSError as e:
            return {'exists': False, 'path': prev_restart_file,
                    'error': f'prev_restart_error:{prev_phase}:{e}', 'size': 0}
    else:
        return {'exists': False, 'path': prev_restart_file,
                'error': f'prev_restart_missing:{prev_phase}', 'size': 0}


def scan_case_creation_log(case_num):
    """Scan the case creation log file for errors.

    Returns:
        dict with 'has_error' (bool), 'error_type' (str), and 'log_path' (str) keys
    """
    # Use CASE_PREFIX for log file pattern (without trailing underscore for log name)
    log_prefix = CASE_PREFIX.rstrip('_') if CASE_PREFIX else f"case"
    log_file = os.path.join(LOG_DIR, f"{log_prefix}{case_num}.log")

    if not os.path.exists(log_file):
        return {'has_error': False, 'error_type': None, 'log_path': log_file, 'found': False}

    try:
        with open(log_file, 'r') as f:
            content = f.read()

        # Check for common error patterns
        error_patterns = [
            ('Disk quota exceeded', 'disk_quota_exceeded'),
            ('No space left on device', 'no_space'),
            ('Permission denied', 'permission_denied'),
            ("can't open", 'file_open_error'),
            ('ERROR:', 'general_error'),
            ('Traceback', 'python_error'),
        ]

        for pattern, error_type in error_patterns:
            if pattern in content:
                return {'has_error': True, 'error_type': error_type, 'log_path': log_file, 'found': True}

        return {'has_error': False, 'error_type': None, 'log_path': log_file, 'found': True}

    except Exception as e:
        return {'has_error': True, 'error_type': f'log_read_error:{e}', 'log_path': log_file, 'found': True}


def check_phase_status(case_num, phase):
    """Check the status of a specific phase for a case."""
    case_name = make_case_name(case_num, phase)
    case_dir = os.path.join(OUTPUT_ROOT, case_name)

    phase_info = PHASES[phase]

    # First check if case was created correctly
    case_creation = check_case_creation(case_num, phase)

    if not os.path.isdir(case_dir):
        # Output directory doesn't exist - check if case was created
        if not case_creation['valid']:
            return {'status': 'CASE_ERROR', 'last_year': 0, 'case_dir': case_dir,
                    'restart_years': [], 'error': case_creation['error'],
                    'script_path': case_creation['script_path']}
        return {'status': 'NOT_EXIST', 'last_year': 0, 'case_dir': case_dir, 'restart_years': [],
                'script_path': case_creation['script_path']}

    restart_years = get_restart_files(case_dir)

    if not restart_years:
        # No restart files - check if case was created correctly and prev phase completed
        if not case_creation['valid']:
            return {'status': 'CASE_ERROR', 'last_year': phase_info['start_year'] - 1,
                    'case_dir': case_dir, 'restart_years': [], 'error': case_creation['error'],
                    'script_path': case_creation['script_path']}

        # Check if previous phase completed (for RGSP/TRANS)
        prev_restart = check_prev_phase_restart(case_num, phase)
        if not prev_restart['exists']:
            return {'status': 'PREV_INCOMPLETE', 'last_year': phase_info['start_year'] - 1,
                    'case_dir': case_dir, 'restart_years': [], 'error': prev_restart['error'],
                    'script_path': case_creation['script_path']}

        return {'status': 'NO_RESTARTS', 'last_year': phase_info['start_year'] - 1,
                'case_dir': case_dir, 'restart_years': [],
                'script_path': case_creation['script_path']}

    last_year = max(restart_years)
    final_year = phase_info['final_year']

    if last_year >= final_year:
        return {'status': 'COMPLETE', 'last_year': last_year,
                'case_dir': case_dir, 'restart_years': restart_years}
    else:
        return {'status': 'INCOMPLETE', 'last_year': last_year,
                'case_dir': case_dir, 'restart_years': restart_years}


def diagnose_case(case_num):
    """Diagnose the full status of a single case (all phases)."""
    result = {
        'case_num': case_num,
        'overall_status': 'COMPLETE',
        'phases': {},
        'stuck_phase': None,
        'last_year': None,
        'needs_restart': False,
        'needs_recreate': False,  # Case needs to be recreated (case creation failed)
        'restart_type': None,  # 'fresh' or 'continue'
        'has_error': False,
        'error_msg': None,
        'log_error': None
    }

    # First check if there were errors during case creation
    log_result = scan_case_creation_log(case_num)
    if log_result['has_error']:
        result['log_error'] = log_result['error_type']

    phase_order = ['ADSP', 'RGSP', 'TRANS']

    for phase in phase_order:
        phase_status = check_phase_status(case_num, phase)
        result['phases'][phase] = phase_status

        if phase_status['status'] == 'CASE_ERROR':
            # Case creation failed - needs to be recreated
            result['overall_status'] = f'{phase}_CASE_ERROR'
            result['stuck_phase'] = phase
            result['last_year'] = phase_status['last_year']
            result['has_error'] = True
            result['error_msg'] = phase_status.get('error', 'unknown')
            result['needs_recreate'] = True  # Needs case recreation
            result['needs_restart'] = False
            break
        elif phase_status['status'] == 'PREV_INCOMPLETE':
            # Previous phase didn't complete or has invalid restart file
            result['overall_status'] = f'{phase}_BLOCKED'
            result['stuck_phase'] = phase
            result['last_year'] = phase_status['last_year']
            result['has_error'] = True
            result['error_msg'] = phase_status.get('error', 'prev_phase_incomplete')
            # Check if previous phase needs recreation
            prev_phase = PHASES[phase]['prev_phase']
            if prev_phase:
                prev_status = result['phases'].get(prev_phase, {}).get('status', '')
                if prev_status == 'CASE_ERROR' or 'invalid' in result['error_msg']:
                    result['needs_recreate'] = True
            result['needs_restart'] = False
            break
        elif phase_status['status'] in ['NOT_EXIST', 'NO_RESTARTS']:
            if phase == 'ADSP':
                result['overall_status'] = 'NOT_STARTED'
                # Check if ADSP case was created but failed
                if log_result['has_error']:
                    result['needs_recreate'] = True
                    result['has_error'] = True
                    result['error_msg'] = f'case_creation_failed:{log_result["error_type"]}'
                else:
                    result['needs_restart'] = True
                    result['restart_type'] = 'fresh'
            else:
                result['overall_status'] = f'WAITING_{phase}'
                # Check if previous phase completed
                prev_phase = PHASES[phase]['prev_phase']
                if prev_phase and result['phases'][prev_phase]['status'] == 'COMPLETE':
                    result['needs_restart'] = True
                    result['restart_type'] = 'fresh'
            result['stuck_phase'] = phase
            result['last_year'] = phase_status['last_year']
            break
        elif phase_status['status'] == 'INCOMPLETE':
            result['overall_status'] = f'{phase}_INCOMPLETE'
            result['stuck_phase'] = phase
            result['last_year'] = phase_status['last_year']
            result['needs_restart'] = True
            result['restart_type'] = 'continue'
            break

    return result


def check_phase_ready(case_num, phase):
    """Check if a phase case is ready to submit (case created correctly).

    Returns:
        dict with 'ready' (bool), 'reason' (str), and 'script_path' (str) keys
    """
    case_name = make_case_name(case_num, phase)
    script_path = os.path.join(SCRIPT_DIR, case_name)

    if not os.path.isdir(script_path):
        return {'ready': False, 'reason': 'case_dir_missing', 'script_path': script_path}

    key_files = ['case.submit', 'user_nl_elm', '.case.run']
    for f in key_files:
        if not os.path.exists(os.path.join(script_path, f)):
            return {'ready': False, 'reason': f'{f}_missing', 'script_path': script_path}

    return {'ready': True, 'reason': None, 'script_path': script_path}


def get_case_script_path(case_num):
    """Get the path to the case creation script for a case number."""
    script_name = CASE_SCRIPT_PATTERN.replace('{N}', str(case_num))
    return os.path.join(CASE_SCRIPTS_DIR, script_name)


def generate_phase_submit_command(case_num, phase, restart_type='fresh', last_year=None,
                                   prev_jobid_var=None, capture_jobid_var=None):
    """Generate shell commands to submit a single phase.

    Args:
        case_num: Case number
        phase: Phase name (ADSP, RGSP, TRANS)
        restart_type: 'fresh' or 'continue'
        last_year: Last completed year (for continue restarts)
        prev_jobid_var: Bash variable name containing previous phase's job ID (for dependency)
        capture_jobid_var: Bash variable name to store this phase's job ID

    Returns:
        List of shell command lines
    """
    phase_info = PHASES[phase]
    case_name = make_case_name(case_num, phase)
    case_path = os.path.join(SCRIPT_DIR, case_name)

    # Calculate restart year and STOP_N
    if restart_type == 'fresh':
        restart_year = phase_info['start_year']
    else:
        restart_year = last_year
        # For ADSP/RGSP: align restart year to forcing data cycle boundary.
        # Forcing recycles every FORCING_CYCLE_LENGTH years (e.g., 20).
        # If a crash leaves a restart at year 171 (not cycle-aligned),
        # snap back to 161 (= start + floor((171-1)/20)*20).
        if phase in ('ADSP', 'RGSP'):
            start = phase_info['start_year']
            elapsed = restart_year - start
            aligned_elapsed = (elapsed // FORCING_CYCLE_LENGTH) * FORCING_CYCLE_LENGTH
            aligned_year = start + aligned_elapsed
            if aligned_year != restart_year:
                restart_year = aligned_year

        # No phase ever wrote a checkpoint AT its own start_year — the model
        # begins from cold init (ADSP) or from the previous phase's final
        # restart (RGSP, TRANS) at that boundary. So if cycle alignment (or
        # the raw last_year, for TRANS) leaves restart_year at start_year,
        # the would-be `finidat = '<self>/run/<self>.elm.r.<start_year>-...nc'`
        # yields a GETFIL abort. Flip to fresh — the existing fresh code path
        # handles each phase correctly:
        #   ADSP fresh  -> just resubmit (no finidat, cold init)
        #   RGSP fresh  -> finidat = ADSP.elm.r.0201-01-01-00000.nc
        #   TRANS fresh -> finidat = RGSP.elm.r.0401-01-01-00000.nc
        if restart_type == 'continue' and restart_year == phase_info['start_year']:
            restart_type = 'fresh'

    stop_n = phase_info['end_year'] - restart_year + 1

    if stop_n <= 0:
        return []

    restart_yearstr = f"{restart_year:04d}"

    cmd_lines = [f"cd {case_path}"]

    # Build batch args with optional dependency
    queue = os.environ.get('A2MC_QUEUE', 'shared')
    memory = os.environ.get('A2MC_MEMORY', '16G')
    if prev_jobid_var:
        batch_args = f'-q {queue} --mem={memory} --dependency=afterok:${prev_jobid_var}'
    else:
        batch_args = f'-q {queue} --mem={memory}'

    if restart_type == 'fresh' and phase == 'ADSP':
        # ADSP fresh start - just resubmit
        cmd_lines.append(f"# Fresh start - just resubmit")
    elif restart_type == 'fresh':
        # RGSP or TRANS fresh start - finidat from previous phase
        prev_phase = phase_info['prev_phase']
        prev_final_year = PHASES[prev_phase]['final_year']
        prev_case_name = make_case_name(case_num, prev_phase)
        prev_restart_file = f"{OUTPUT_ROOT}/{prev_case_name}/run/{prev_case_name}.elm.r.{prev_final_year:04d}-01-01-00000.nc"

        cmd_lines.extend([
            f"# Fresh start from previous phase's restart file",
            f"./xmlchange STOP_N={stop_n}",
            f"./xmlchange RUN_STARTDATE={restart_yearstr}-01-01",
            f"sed -i '$ d' ./user_nl_elm",
            f"echo \"finidat = '{prev_restart_file}'\" >> user_nl_elm",
            f"./case.setup",
        ])
    else:
        # Continue from partial run
        restart_file = f"{OUTPUT_ROOT}/{case_name}/run/{case_name}.elm.r.{restart_yearstr}-01-01-00000.nc"

        if phase == 'ADSP':
            # ADSP user_nl_elm tail (per case template):
            #   ... finidat = ''
            #       nyears_ad_carbon_only = K
            # K is the project-level config (a2mc_config.sh:
            # A2MC_ADSP_NYEARS_AD_CARBON_ONLY, default 30). Strip both trailing
            # lines, append the new finidat, then iff restart_year <= K
            # re-append `nyears_ad_carbon_only = K`. The model's gate is
            # `yr .le. K` (yr is the calendar year from RUN_STARTDATE), so K
            # must remain in the namelist whenever there are still
            # AD-carbon-only years left to run. For restart_year > K the line
            # is functionally inert (gate fails for all yr >= 1) so we drop it.
            keep_ad_carbon_only = restart_year <= NYEARS_AD_CARBON_ONLY
            cmd_lines.extend([
                f"# Continue from year {restart_year} "
                    f"(K={NYEARS_AD_CARBON_ONLY}, "
                    f"keep nyears_ad_carbon_only: {keep_ad_carbon_only})",
                f"./xmlchange STOP_N={stop_n}",
                f"./xmlchange RUN_STARTDATE={restart_yearstr}-01-01",
                f"sed -i '$ d' ./user_nl_elm && sed -i '$ d' ./user_nl_elm",
                f"echo \"finidat = '{restart_file}'\" >> user_nl_elm",
            ])
            if keep_ad_carbon_only:
                cmd_lines.append(
                    f"echo 'nyears_ad_carbon_only = {NYEARS_AD_CARBON_ONLY}' "
                    f">> user_nl_elm"
                )
            cmd_lines.append(f"./case.setup")
        else:
            cmd_lines.extend([
                f"# Continue from year {restart_year}",
                f"./xmlchange STOP_N={stop_n}",
                f"./xmlchange RUN_STARTDATE={restart_yearstr}-01-01",
                f"sed -i '$ d' ./user_nl_elm",
                f"echo \"finidat = '{restart_file}'\" >> user_nl_elm",
                f"./case.setup",
            ])

    # Submit command with job ID capture
    if capture_jobid_var:
        cmd_lines.extend([
            f"SUBMIT_OUTPUT=$(./case.submit --batch-args=\"{batch_args}\" 2>&1)",
            f"echo \"$SUBMIT_OUTPUT\"",
            f"{capture_jobid_var}=$(echo \"$SUBMIT_OUTPUT\" | grep -oP '(?:Submitted job id is |with id )\\K[0-9]+' | head -1)",
            f"if [ -z \"${capture_jobid_var}\" ]; then",
            f"    sleep 2",
            f"    {capture_jobid_var}=$(squeue -u $USER -n {case_name} -h -o \"%i\" | head -1)",
            f"fi",
            f"echo \"  {phase} Job ID: ${capture_jobid_var}\"",
        ])
    else:
        cmd_lines.append(f"./case.submit --batch-args=\"{batch_args}\"")

    return cmd_lines


def generate_restart_command(case_result):
    """Generate shell commands to restart an incomplete case WITH full phase chain.

    When restarting ADSP, also submits RGSP and TRANS with SLURM dependencies.
    Uses job ID capture to chain phases: ADSP → RGSP → TRANS.

    Based on MATLAB template logic:
    - For fresh starts: just resubmit (ADSP) or set finidat to prev phase's restart
    - For continues: set RUN_STARTDATE, update finidat, calculate STOP_N
    - ADSP/RGSP continues: align restart year to forcing cycle boundary
      (e.g., last_year=171 snaps back to 161 for 20-year forcing cycle)
    - ADSP: strip 2 trailing lines (finidat='' and nyears_ad_carbon_only = K),
      append the new finidat, then re-append `nyears_ad_carbon_only = K` iff
      restart_year <= K (K read from $A2MC_ADSP_NYEARS_AD_CARBON_ONLY in
      a2mc_config.sh — single source of truth, project-level protocol setting)
    - RGSP/TRANS: remove 1 line from user_nl_elm (old finidat)
    """
    if not case_result['needs_restart']:
        return ""

    case_num = case_result['case_num']
    phase = case_result['stuck_phase']
    last_year = case_result['last_year']
    restart_type = case_result['restart_type']

    # Determine which phases need to be submitted
    phase_order = ['ADSP', 'RGSP', 'TRANS']
    stuck_idx = phase_order.index(phase)
    phases_to_submit = phase_order[stuck_idx:]  # Current phase and all subsequent

    cmd_lines = [
        f"",
        f"# {'='*60}",
        f"# Case {case_num}: Restart from {phase} ({restart_type})",
        f"# Phases to submit: {' → '.join(phases_to_submit)}",
        f"# {'='*60}",
    ]

    # Check if subsequent phases are ready
    phases_ready = {}
    phases_need_creation = []

    for p in phases_to_submit:
        if p == phase:
            # Stuck phase is assumed ready (we're restarting it)
            phases_ready[p] = True
        else:
            check = check_phase_ready(case_num, p)
            phases_ready[p] = check['ready']
            if not check['ready']:
                phases_need_creation.append(p)

    # If subsequent phases need creation, try to create them first
    if phases_need_creation:
        case_script = get_case_script_path(case_num)
        cmd_lines.extend([
            f"",
            f"# Phases {phases_need_creation} not created yet - creating them first",
            f"CASE_SCRIPT=\"{case_script}\"",
            f"if [ -f \"$CASE_SCRIPT\" ]; then",
            f"    echo \"Creating missing phases using: $CASE_SCRIPT\"",
            f"    bash \"$CASE_SCRIPT\"",
            f"else",
            f"    echo \"ERROR: Case script not found: $CASE_SCRIPT\"",
            f"    echo \"Cannot create phases {phases_need_creation}\"",
            f"    exit 1",
            f"fi",
            f"",
        ])

    # Define job ID variable names
    jobid_vars = {
        'ADSP': f'JOBID_ADSP_{case_num}',
        'RGSP': f'JOBID_RGSP_{case_num}',
        'TRANS': f'JOBID_TRANS_{case_num}',
    }

    # Submit each phase with dependency chain
    for i, p in enumerate(phases_to_submit):
        is_first = (i == 0)
        is_last = (i == len(phases_to_submit) - 1)

        # Determine restart type for this phase
        if is_first:
            p_restart_type = restart_type
            p_last_year = last_year
        else:
            p_restart_type = 'fresh'  # Subsequent phases are fresh starts
            p_last_year = None

        # Determine dependency
        prev_phase = phases_to_submit[i - 1] if i > 0 else None
        prev_jobid_var = jobid_vars[prev_phase] if prev_phase else None

        # Capture job ID unless it's the last phase
        capture_jobid_var = jobid_vars[p] if not is_last else None

        cmd_lines.append(f"")
        cmd_lines.append(f"# --- {p} Phase ---")

        phase_cmds = generate_phase_submit_command(
            case_num=case_num,
            phase=p,
            restart_type=p_restart_type,
            last_year=p_last_year,
            prev_jobid_var=prev_jobid_var,
            capture_jobid_var=capture_jobid_var,
        )
        cmd_lines.extend(phase_cmds)

    cmd_lines.append(f"echo \"Case {case_num} submitted: {' → '.join(phases_to_submit)}\"")
    cmd_lines.append(f"")

    return "\n".join(cmd_lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description='Diagnose ELM-FATES ensemble status')
    # Default case range uses TOTAL_ENSEMBLE from config (or fallback)
    default_range = f"1-{TOTAL_ENSEMBLE}" if TOTAL_ENSEMBLE > 0 else "1-100"
    parser.add_argument('--cases', type=str, default=default_range,
                        help=f'Case range or list, e.g., "1-100", "1,5,10", "1-50,100,200-300"')
    parser.add_argument('--restart', action='store_true',
                        help='Generate restart script')
    parser.add_argument('--parallel', type=int, default=16,
                        help='Number of parallel workers')
    parser.add_argument('--no-validate', action='store_true',
                       help='Skip auto-validation of the generated restart script')
    parser.add_argument('--output-dir', type=str, default='.',
                        help='Output directory for reports')
    args = parser.parse_args()

    # Parse case specification: supports ranges, lists, and combinations
    # Examples: "1-100", "1,5,10", "1-50,100,200-300"
    case_nums = []
    for part in args.cases.split(','):
        part = part.strip()
        if '-' in part:
            bounds = part.split('-')
            case_nums.extend(range(int(bounds[0]), int(bounds[1]) + 1))
        else:
            case_nums.append(int(part))
    case_nums = sorted(set(case_nums))  # deduplicate and sort

    print("=" * 60)
    print("ELM-FATES Ensemble Diagnostic Tool (FIXED VERSION)")
    print("=" * 60)
    print(f"Output root: {OUTPUT_ROOT}")
    if len(case_nums) <= 20:
        print(f"Cases: {args.cases} ({len(case_nums)} cases)")
    else:
        print(f"Cases: {case_nums[0]} to {case_nums[-1]} ({len(case_nums)} cases)")
    print(f"Parallel workers: {args.parallel}")
    print()

    # Scan all cases in parallel
    all_results = []

    print(f"Scanning {len(case_nums)} cases...")

    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {executor.submit(diagnose_case, n): n for n in case_nums}
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            all_results.append(result)
            completed += 1
            if completed % 500 == 0:
                print(f"  Processed {completed}/{len(case_nums)} cases...")

    # Sort by case number
    all_results.sort(key=lambda x: x['case_num'])

    # Generate statistics
    status_counts = defaultdict(int)
    incomplete_by_phase = defaultdict(list)
    error_cases = []
    recreate_cases = []

    for r in all_results:
        status_counts[r['overall_status']] += 1
        if r['needs_restart']:
            incomplete_by_phase[r['stuck_phase']].append(r)
        if r['has_error']:
            error_cases.append(r)
        if r['needs_recreate']:
            recreate_cases.append(r)

    # Print summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total_cases = len(all_results)
    complete = status_counts.get('COMPLETE', 0)

    print(f"Total cases scanned:    {total_cases}")
    print(f"Complete:               {complete} ({100*complete/total_cases:.1f}%)")
    print()
    print("Incomplete by phase (can be restarted):")
    for phase in ['ADSP', 'RGSP', 'TRANS']:
        count = len(incomplete_by_phase[phase])
        if count > 0:
            fresh_count = sum(1 for r in incomplete_by_phase[phase] if r['restart_type'] == 'fresh')
            continue_count = count - fresh_count
            print(f"  {phase}: {count} cases (fresh: {fresh_count}, continue: {continue_count})")
        else:
            print(f"  {phase}: 0 cases")
    print()
    print(f"Not started:            {status_counts.get('NOT_STARTED', 0)}")

    # Report cases needing recreation
    if recreate_cases:
        print()
        print(f"NEED RECREATION (case creation failed): {len(recreate_cases)}")
        recreate_by_error = defaultdict(list)
        for r in recreate_cases:
            error_key = r.get('log_error') or r.get('error_msg') or 'unknown'
            recreate_by_error[error_key].append(r['case_num'])
        for error_type, case_nums in recreate_by_error.items():
            if len(case_nums) <= 10:
                print(f"  {error_type}: cases {case_nums}")
            else:
                print(f"  {error_type}: {len(case_nums)} cases (first 10: {case_nums[:10]}...)")

    # Report other error cases
    other_errors = [r for r in error_cases if not r['needs_recreate']]
    if other_errors:
        print()
        print(f"OTHER ERRORS (need investigation): {len(other_errors)}")
        error_by_type = defaultdict(list)
        for r in other_errors:
            error_by_type[r['error_msg']].append(r['case_num'])
        for error_type, case_nums in error_by_type.items():
            if len(case_nums) <= 10:
                print(f"  {error_type}: cases {case_nums}")
            else:
                print(f"  {error_type}: {len(case_nums)} cases (first 10: {case_nums[:10]}...)")
    print()

    # Generate output files
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = Path(args.output_dir)

    # 1. Detailed report
    report_file = output_dir / f"ensemble_status_report_{timestamp}.txt"
    with open(report_file, 'w') as f:
        f.write("Case,Overall_Status,Stuck_Phase,Last_Year,ADSP_Status,RGSP_Status,TRANS_Status,Has_Error,Error_Msg\n")
        for r in all_results:
            adsp = r['phases'].get('ADSP', {}).get('status', 'N/A')
            rgsp = r['phases'].get('RGSP', {}).get('status', 'N/A')
            trans = r['phases'].get('TRANS', {}).get('status', 'N/A')
            has_error = 'Y' if r['has_error'] else 'N'
            error_msg = r.get('error_msg', '') or ''
            f.write(f"{r['case_num']},{r['overall_status']},{r['stuck_phase'] or 'N/A'},{r['last_year'] or 'N/A'},{adsp},{rgsp},{trans},{has_error},{error_msg}\n")
    print(f"Detailed report: {report_file}")

    # 2. Completed cases list
    completed_file = output_dir / f"completed_cases_{timestamp}.txt"
    with open(completed_file, 'w') as f:
        for r in all_results:
            if r['overall_status'] == 'COMPLETE':
                f.write(f"{r['case_num']}\n")
    print(f"Completed list: {completed_file}")

    # 3. Incomplete cases list (simple)
    incomplete_file = output_dir / f"incomplete_cases_{timestamp}.txt"
    with open(incomplete_file, 'w') as f:
        f.write("# Case numbers that need restart\n")
        f.write("# Format: case_num,phase,last_year,restart_type\n")
        for phase in ['ADSP', 'RGSP', 'TRANS']:
            for r in incomplete_by_phase[phase]:
                f.write(f"{r['case_num']},{phase},{r['last_year']},{r['restart_type']}\n")
    print(f"Incomplete list: {incomplete_file}")

    # 3b. Error cases list (need manual fix)
    if error_cases:
        error_file = output_dir / f"error_cases_{timestamp}.txt"
        with open(error_file, 'w') as f:
            f.write("# Cases with errors that need manual intervention\n")
            f.write("# These cases cannot be restarted automatically\n")
            f.write("# Format: case_num,phase,error_type\n")
            for r in error_cases:
                f.write(f"{r['case_num']},{r['stuck_phase']},{r['error_msg']}\n")
        print(f"Error cases list: {error_file}")

    # 3c. Recreation script for failed case creations
    if recreate_cases:
        recreate_file = output_dir / f"recreate_cases_{timestamp}.sh"
        recreate_list_file = output_dir / f"recreate_cases_{timestamp}.txt"

        # List file
        with open(recreate_list_file, 'w') as f:
            f.write("# Cases that need to be recreated (case creation failed)\n")
            f.write("# Format: case_num,phase,error_type\n")
            for r in recreate_cases:
                error_key = r.get('log_error') or r.get('error_msg') or 'unknown'
                f.write(f"{r['case_num']},{r['stuck_phase']},{error_key}\n")
        print(f"Recreate list: {recreate_list_file}")

        # Recreation script - simply re-run existing case scripts
        with open(recreate_file, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Auto-generated case recreation script\n")
            f.write(f"# Generated: {datetime.now()}\n")
            f.write(f"# Total cases to recreate: {len(recreate_cases)}\n")
            f.write(f"#\n")
            f.write(f"# These cases had errors during initial creation (e.g., disk quota exceeded)\n")
            f.write(f"# This script re-runs the existing case scripts created by submit_ensemble.sh\n")
            f.write(f"#\n")
            f.write(f"# BEFORE RUNNING: Make sure you have enough disk quota!\n")
            f.write(f"# Check with: lfs quota -h /global/cfs/cdirs/m2467/\n")
            f.write(f"#\n\n")

            f.write(f"# Directory containing pre-generated case scripts\n")
            f.write(f"CASE_SCRIPTS_DIR=\"{CASE_SCRIPTS_DIR}\"\n")
            f.write(f"CASE_SCRIPT_PATTERN=\"{CASE_SCRIPT_PATTERN}\"\n\n")

            f.write("# Cases to recreate:\n")
            case_nums_to_recreate = sorted([r['case_num'] for r in recreate_cases])
            f.write(f"CASES_TO_RECREATE=({' '.join(map(str, case_nums_to_recreate))})\n\n")

            f.write("echo \"Recreating ${#CASES_TO_RECREATE[@]} cases by re-running existing case scripts...\"\n")
            f.write("echo \"\"\n\n")

            f.write("for CASE_NUM in \"${CASES_TO_RECREATE[@]}\"; do\n")
            f.write("    # Build script path from pattern\n")
            f.write("    SCRIPT_NAME=\"${CASE_SCRIPT_PATTERN//\\{N\\}/$CASE_NUM}\"\n")
            f.write("    SCRIPT_PATH=\"$CASE_SCRIPTS_DIR/$SCRIPT_NAME\"\n")
            f.write("    \n")
            f.write("    echo \"======================================\"\n")
            f.write("    echo \"Recreating case $CASE_NUM\"\n")
            f.write("    echo \"Script: $SCRIPT_PATH\"\n")
            f.write("    echo \"======================================\"\n")
            f.write("    \n")
            f.write("    if [ -f \"$SCRIPT_PATH\" ]; then\n")
            f.write("        bash \"$SCRIPT_PATH\"\n")
            f.write("        echo \"Case $CASE_NUM recreation submitted.\"\n")
            f.write("    else\n")
            f.write("        echo \"ERROR: Script not found: $SCRIPT_PATH\"\n")
            f.write("        echo \"You may need to generate it first with submit_ensemble.sh\"\n")
            f.write("    fi\n")
            f.write("    echo \"\"\n")
            f.write("done\n\n")

            f.write("echo \"Done recreating cases.\"\n")
            f.write("echo \"After recreation completes, re-run diagnose_ensemble_status.py to check status.\"\n")

        os.chmod(recreate_file, 0o755)
        print(f"Recreate script: {recreate_file}")

    # 4. Restart script
    if args.restart or True:  # Always generate script
        restart_file = output_dir / f"restart_incomplete_{timestamp}.sh"
        with open(restart_file, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write(f"# Auto-generated restart script (FIXED VERSION with full phase chain)\n")
            f.write(f"# Generated: {datetime.now()}\n")
            f.write(f"# Total cases to restart: {sum(len(v) for v in incomplete_by_phase.values())}\n")
            f.write(f"#\n")
            f.write(f"# PHASE CHAIN FEATURE:\n")
            f.write(f"# - When restarting ADSP, also submits RGSP and TRANS with SLURM dependencies\n")
            f.write(f"# - Captures job IDs and chains: ADSP → RGSP (afterok:ADSP) → TRANS (afterok:RGSP)\n")
            f.write(f"# - If RGSP/TRANS cases not created, runs case script to create them first\n")
            f.write(f"#\n")
            f.write(f"# Key implementation details:\n")
            f.write(f"# - Uses RUN_STARTDATE + finidat approach (not CONTINUE_RUN)\n")
            f.write(f"# - STOP_N = end_year - restart_year + 1\n")
            f.write(f"# - ADSP continue: strips 2 lines (finidat, nyears_ad_carbon_only),\n")
            f.write(f"#   appends new finidat, re-appends nyears_ad_carbon_only=K iff\n")
            f.write(f"#   restart_year <= K (K from $A2MC_ADSP_NYEARS_AD_CARBON_ONLY,\n")
            f.write(f"#   currently {NYEARS_AD_CARBON_ONLY})\n")
            f.write(f"# - RGSP/TRANS: removes 1 line (old finidat)\n")
            f.write(f"# - Fresh starts use previous phase's restart file\n")

            # Group by phase for easier management
            for phase in ['ADSP', 'RGSP', 'TRANS']:
                if incomplete_by_phase[phase]:
                    f.write(f"\n# ===== {phase} Phase Restarts ({len(incomplete_by_phase[phase])} cases) =====\n")
                    for r in incomplete_by_phase[phase]:
                        f.write(generate_restart_command(r))

        os.chmod(restart_file, 0o755)
        print(f"Restart script: {restart_file}")

        # 4b. Auto-validate the generated restart script
        if not args.no_validate:
            print()
            print("=" * 60)
            print("RESTART SCRIPT VALIDATION")
            print("=" * 60)
            import sys as _sys
            import subprocess as _subprocess
            validator = Path(__file__).parent / 'validate_restart_script.py'
            if validator.is_file():
                cmd = [_sys.executable, str(validator), str(restart_file),
                       '--incomplete-cases', str(incomplete_file)]
                result = _subprocess.run(cmd)
                if result.returncode != 0:
                    print()
                    print("VALIDATION FAILED — review errors above before submitting")
                    print(f"(Re-run validator manually: python {validator} {restart_file})")
                else:
                    print()
                    print("Validation passed — restart script is ready to submit.")
            else:
                print(f"  (validator not found at {validator}; skipping)")

    # 5. Summary by last year for each phase (helpful for understanding where things failed)
    print()
    print("=" * 60)
    print("DETAILED BREAKDOWN BY LAST COMPLETED YEAR")
    print("=" * 60)

    for phase in ['ADSP', 'RGSP', 'TRANS']:
        if incomplete_by_phase[phase]:
            year_counts = defaultdict(int)
            type_counts = defaultdict(int)
            for r in incomplete_by_phase[phase]:
                year_counts[r['last_year']] += 1
                type_counts[r['restart_type']] += 1

            print(f"\n{phase} incomplete cases:")
            print(f"  By restart type: fresh={type_counts['fresh']}, continue={type_counts['continue']}")
            print(f"  By last year:")
            for year in sorted(year_counts.keys()):
                print(f"    Year {year}: {year_counts[year]} cases")

    print()
    print("=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("1. Review the incomplete cases list")
    print("2. Check SLURM logs for error messages:")
    print(f"   less {OUTPUT_ROOT}/<CASE_NAME>/run/<CASE_NAME>.log.*")
    print("3. Fix any issues (file quota, memory, etc.)")
    print("4. Run the restart script:")
    print(f"   ./{restart_file.name}")
    print()


if __name__ == '__main__':
    main()
