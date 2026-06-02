#!/usr/bin/env python3
"""Pre-flight validation for a Phase 0 ensemble submission.

Mirrors `tools/validate_restart_script.py` but for the submission side.
Catches obvious foot-guns before SLURM accepts 4890 jobs:

  - Required env vars set, $A2MC_SITE_CONFIG points to a real file
  - $A2MC_PARAM_LIST_FILE and $A2MC_ENSEMBLE_MATRIX_FILE exist
  - Every case in the range has a parameter .nc file in $A2MC_PARAM_DIR
  - Per-case scripts exist in $A2MC_CASE_SCRIPTS (when --scripts-required)
    and contain no unresolved {...} tokens
  - No conflicting jobs already queued in squeue for the same case names
  - The build case can plausibly do a fresh build (its case dir doesn't
    exist, or `--allow-existing-case-dirs` is passed)

Auto-invoked from `phases/phase0_design/submit_phase0.py` between Stage 3a
(generate per-case scripts) and Stage 3c (coordinated submit). Can also
run standalone before invoking the orchestrator.

Usage:
    source a2mc_config.sh
    source use_cases/<site>/config/<round>_config.sh

    # Standalone (no per-case scripts yet)
    python tools/validate_submission_plan.py --start 1 --end 4890

    # After submit_phase0.py --dry-run (per-case scripts exist)
    python tools/validate_submission_plan.py --start 1 --end 4890 --scripts-required

Exit 0 = all checks pass, 1 = any check fails, 2 = setup error.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CASE_TOKEN_RE = re.compile(r'\{[A-Za-z_]+\}')


def env_path(var: str) -> Optional[Path]:
    v = os.environ.get(var)
    return Path(v) if v else None


def resolve_case_name(pattern: str, case_num: int, phase: Optional[str]) -> Tuple[str, List[str]]:
    """Apply the same substitution rules as create_case.sh::resolve_case_name.

    Returns (resolved_name, unresolved_tokens). The caller checks
    `unresolved_tokens` for emptiness.
    """
    resolved = pattern.replace('{N}', str(case_num))
    if phase is not None:
        resolved = resolved.replace('{PHASE}', phase)
    else:
        resolved = re.sub(r'_\{PHASE\}$', '', resolved)
    unresolved = CASE_TOKEN_RE.findall(resolved)
    return resolved, unresolved


def find_param_file(param_dir: Path, pattern: str, case_num: int) -> Optional[Path]:
    expected = param_dir / pattern.replace('{N}', str(case_num))
    if expected.is_file():
        return expected
    fallback = list(param_dir.glob(f'*En{case_num}*.nc'))
    return fallback[0] if fallback else None


def parse_case_list(args: argparse.Namespace) -> List[int]:
    if args.cases_file:
        if not args.cases_file.is_file():
            raise SystemExit(f"ERROR: cases-file not found: {args.cases_file}")
        cases = []
        for line in args.cases_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                cases.append(int(line.split(',')[0]))
            except ValueError:
                pass
        if not cases:
            raise SystemExit(f"ERROR: no case numbers in {args.cases_file}")
        return cases
    if args.start is None or args.end is None:
        raise SystemExit("ERROR: must provide --start AND --end, OR --cases-file")
    return list(range(args.start, args.end + 1))


def squeue_user_jobs() -> List[str]:
    """Return the list of currently-queued job names for the calling user.

    Empty list on failure (squeue unavailable, e.g., outside a SLURM environment).
    """
    try:
        out = subprocess.check_output(
            ['squeue', '-u', os.environ.get('USER', ''), '-h', '-o', '%j'],
            stderr=subprocess.DEVNULL, text=True, timeout=30,
        )
        return [n.strip() for n in out.splitlines() if n.strip()]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Check runner
# ---------------------------------------------------------------------------

class CheckRunner:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def check(self, passed: bool, msg: str, level: str = 'error') -> None:
        if passed:
            print(f"  PASS  {msg}")
        else:
            marker = 'FAIL' if level == 'error' else 'WARN'
            print(f"  {marker}  {msg}")
            (self.errors if level == 'error' else self.warnings).append(msg)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_environment(r: CheckRunner) -> dict:
    """Verify required env vars and return them in a dict."""
    required = [
        'A2MC_SITE_CONFIG', 'A2MC_PARAM_DIR', 'A2MC_PARAM_PATTERN',
        'A2MC_CASE_NAME_PATTERN', 'A2MC_ENSEMBLE_OUTPUT', 'A2MC_CASE_SCRIPTS',
    ]
    print("\n=== Environment ===")
    env = {}
    for v in required:
        val = os.environ.get(v, '')
        ok = bool(val)
        r.check(ok, f"${v} is set ({'<empty>' if not val else val})")
        env[v] = val
    # Site config file existence
    site_cfg = env.get('A2MC_SITE_CONFIG', '')
    if site_cfg:
        r.check(Path(site_cfg).is_file(), f"$A2MC_SITE_CONFIG file exists: {site_cfg}")
    # Param list / matrix files
    plf = os.environ.get('A2MC_PARAM_LIST_FILE', '')
    if plf:
        r.check(Path(plf).is_file(), f"$A2MC_PARAM_LIST_FILE exists: {plf}", level='warning')
    emf = os.environ.get('A2MC_ENSEMBLE_MATRIX_FILE', '')
    if emf:
        r.check(Path(emf).is_file(),
                f"$A2MC_ENSEMBLE_MATRIX_FILE exists: {emf} (run create_parameter_sample.py if missing)",
                level='warning')
    return env


def validate_per_case(
    r: CheckRunner,
    cases: List[int],
    env: dict,
    scripts_required: bool,
    allow_existing_case_dirs: bool,
) -> None:
    """Per-case parameter-file, script, and case-dir existence checks."""
    param_dir = Path(env['A2MC_PARAM_DIR'])
    param_pattern = env['A2MC_PARAM_PATTERN']
    case_pattern = env['A2MC_CASE_NAME_PATTERN']
    case_scripts = Path(env['A2MC_CASE_SCRIPTS'])
    e3sm_scripts = Path(os.environ.get('A2MC_E3SM_ROOT', '')) / 'cime' / 'scripts'

    print("\n=== Per-case files ===")
    missing_params = []
    missing_scripts = []
    unresolved_cases = []
    existing_case_dirs = []

    for n in cases:
        # Parameter file
        pf = find_param_file(param_dir, param_pattern, n)
        if pf is None:
            missing_params.append(n)
        # Case name resolution
        base_name, leftover = resolve_case_name(case_pattern, n, None)
        if leftover:
            unresolved_cases.append((n, leftover))
        # Per-case script
        script = case_scripts / f'En{n}.sh'
        if scripts_required and not script.is_file():
            missing_scripts.append(n)
        # CIME case dir collision
        if e3sm_scripts.is_dir():
            for phase in ('ADSP', 'RGSP', 'TRANS'):
                full_name, _ = resolve_case_name(case_pattern, n, phase)
                cdir = e3sm_scripts / full_name
                if cdir.is_dir():
                    existing_case_dirs.append((n, phase, str(cdir)))

    r.check(not missing_params,
            f"all {len(cases)} cases have a parameter .nc in {param_dir}"
            f" ({len(missing_params)} missing: {missing_params[:5]}{'...' if len(missing_params) > 5 else ''})")

    r.check(not unresolved_cases,
            f"all case names resolve cleanly ({len(unresolved_cases)} with unresolved tokens: "
            f"{unresolved_cases[:3]})")

    if scripts_required:
        r.check(not missing_scripts,
                f"all per-case scripts exist in {case_scripts}"
                f" ({len(missing_scripts)} missing: {missing_scripts[:5]}{'...' if len(missing_scripts) > 5 else ''})")

    if not allow_existing_case_dirs:
        r.check(not existing_case_dirs,
                f"no CIME case dirs already exist that would be overwritten "
                f"({len(existing_case_dirs)} found; use --allow-existing-case-dirs to skip this check)",
                level='warning')


def validate_per_case_scripts_content(r: CheckRunner, cases: List[int], env: dict) -> None:
    """Verify each per-case script has no unresolved {...} tokens in its body."""
    case_scripts = Path(env['A2MC_CASE_SCRIPTS'])
    print("\n=== Per-case script content ===")
    bad_scripts = []
    for n in cases:
        script = case_scripts / f'En{n}.sh'
        if not script.is_file():
            continue
        body = script.read_text()
        # Scan for {N}, {PHASE} that the heredoc substitution might have missed.
        # The generated scripts SHOULD have no `{N}` or `{PHASE}` outside of
        # quoted strings that document the original pattern.
        for line_no, line in enumerate(body.splitlines(), 1):
            # Skip the literal pattern declaration line
            if line.strip().startswith('CASE_NAME_PATTERN='):
                continue
            # Skip comments
            if line.lstrip().startswith('#'):
                continue
            for token in ('{N}', '{PHASE}'):
                # but allow inside bash parameter expansion like ${...//{N}/...}
                # — those are intentional. Look for tokens NOT preceded by a $.
                idx = line.find(token)
                while idx >= 0:
                    if idx == 0 or line[idx - 1] != '$' and line[idx - 1] != '/':
                        # Likely unresolved
                        bad_scripts.append((n, line_no, line.strip()[:80]))
                        break
                    idx = line.find(token, idx + 1)
                if bad_scripts and bad_scripts[-1][0] == n:
                    break
    r.check(not bad_scripts,
            f"no per-case script has unresolved {{N}}/{{PHASE}} tokens outside parameter-expansion syntax "
            f"({len(bad_scripts)} suspect; first: {bad_scripts[0] if bad_scripts else None})",
            level='warning')


def validate_no_queue_collisions(r: CheckRunner, cases: List[int], env: dict) -> None:
    """Check that none of the planned case names already have queued SLURM jobs."""
    print("\n=== SLURM queue collisions ===")
    queued = squeue_user_jobs()
    if not queued:
        r.check(True, "no queued jobs for $USER (squeue returned empty or unavailable)", level='warning')
        return
    queued_set = set(queued)
    case_pattern = env['A2MC_CASE_NAME_PATTERN']
    collisions = []
    for n in cases:
        for phase in ('ADSP', 'RGSP', 'TRANS'):
            full_name, _ = resolve_case_name(case_pattern, n, phase)
            # SLURM job names from case.submit often have a 'run.' prefix
            candidates = {full_name, f'run.{full_name}'}
            if candidates & queued_set:
                collisions.append((n, phase, full_name))
    r.check(not collisions,
            f"no planned case has a colliding queued job "
            f"({len(collisions)} collisions; first: {collisions[0] if collisions else None})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-flight validation for Phase 0 submission.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--start', type=int, default=None, help="Range start")
    parser.add_argument('--end', type=int, default=None, help="Range end")
    parser.add_argument('--cases-file', type=Path, default=None,
                        help="Alternative to --start/--end: file with one case per line")
    parser.add_argument('--scripts-required', action='store_true',
                        help="Require per-case scripts to exist in $A2MC_CASE_SCRIPTS (post-Stage 3a)")
    parser.add_argument('--allow-existing-case-dirs', action='store_true',
                        help="Suppress the warning about CIME case dirs that already exist")
    args = parser.parse_args()

    runner = CheckRunner()

    # 1. Environment
    env = validate_environment(runner)
    if runner.errors:
        # Critical setup error — bail before trying per-case checks
        _print_result(runner)
        return 2

    cases = parse_case_list(args)
    print(f"\nValidating {len(cases)} cases (range {min(cases)}..{max(cases)})")

    # 2. Per-case files
    validate_per_case(runner, cases, env, args.scripts_required, args.allow_existing_case_dirs)

    # 3. Per-case script content (only if scripts are required)
    if args.scripts_required:
        validate_per_case_scripts_content(runner, cases, env)

    # 4. SLURM queue collisions
    validate_no_queue_collisions(runner, cases, env)

    _print_result(runner)
    return 0 if not runner.errors else 1


def _print_result(runner: CheckRunner) -> None:
    print("\n" + "=" * 60)
    print(f"Validation result: {len(runner.errors)} error(s), {len(runner.warnings)} warning(s)")
    print("=" * 60)
    if runner.errors:
        print("\nERRORS:")
        for e in runner.errors:
            print(f"  - {e}")
    if runner.warnings:
        print("\nWARNINGS:")
        for w in runner.warnings:
            print(f"  - {w}")


if __name__ == '__main__':
    sys.exit(main())
