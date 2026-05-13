#!/usr/bin/env python3
"""Submit a Phase 0 ensemble to HPC.

Orchestrator for Stage 3 of Phase 0. Replaces `tools/submit_ensemble.sh`
and the casetemplate `submit_full_morris_ADSPSupNP.sh` bundle script with
a single config-driven Python entry point.

Workflow:
  1. Generate per-case scripts via `tools/create_case.sh --write-script`,
     resolving all $A2MC_* env vars at script-write time. Output goes to
     $A2MC_CASE_SCRIPTS (round-namespaced). Build case is created with
     a fresh build; remaining cases are created with --reuse-build BUILD_CASE.
  2. Run the build case synchronously (this builds FATES + submits the
     ADSP/RGSP/TRANS chain to SLURM).
  3. Run remaining cases in parallel batches (each reuses BUILD_CASE's
     compiled bld via EXEROOT and submits its own SLURM chain).
  4. Write submission_manifest.json to $A2MC_ENSEMBLE_OUTPUT for audit.

Usage:
  source a2mc_config.sh
  source use_cases/<site>/config/<round>_config.sh

  # Dry run: generate scripts + print plan, no submission
  python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --dry-run

  # Real submission
  python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --submit

  # Subset-replay mode (non-sequential case numbers)
  python phases/phase0_design/submit_phase0.py --cases-file <list>.txt --submit

  # Override build case (default: smallest in range / first in cases-file)
  python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --build-case 1 --submit
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """Phase 0 submission configuration, populated from $A2MC_* env vars."""

    site_config: Path                                  # $A2MC_SITE_CONFIG
    param_dir: Path                                    # $A2MC_PARAM_DIR
    param_pattern: str                                 # $A2MC_PARAM_PATTERN
    case_name_pattern: str                             # $A2MC_CASE_NAME_PATTERN
    ensemble_output: Path                              # $A2MC_ENSEMBLE_OUTPUT
    case_scripts: Path                                 # $A2MC_CASE_SCRIPTS
    a2mc_root: Path                                    # repo root
    create_case: Path                                  # tools/create_case.sh
    # Optional bookkeeping for the manifest
    ensemble_name: str = ""                            # $A2MC_ENSEMBLE_NAME
    ensemble_matrix_file: Optional[Path] = None        # $A2MC_ENSEMBLE_MATRIX_FILE
    sampling_scheme: str = ""                          # $A2MC_SAMPLING_SCHEME

    @classmethod
    def from_env(cls) -> "Config":
        """Build Config from the current environment. Raises if required vars are missing."""
        required = {
            'A2MC_SITE_CONFIG': 'sourced your site config?',
            'A2MC_PARAM_DIR': 'set via site config',
            'A2MC_PARAM_PATTERN': 'set via site config',
            'A2MC_CASE_NAME_PATTERN': 'set via site config',
            'A2MC_ENSEMBLE_OUTPUT': 'set via site config',
            'A2MC_CASE_SCRIPTS': 'set via site config',
        }
        missing = [v for v in required if not os.environ.get(v)]
        if missing:
            print("ERROR: missing required environment variable(s):", file=sys.stderr)
            for v in missing:
                print(f"  - ${v}  ({required[v]})", file=sys.stderr)
            print("\nFix:", file=sys.stderr)
            print("  source a2mc_config.sh", file=sys.stderr)
            print("  source use_cases/<site>/config/<round>_config.sh", file=sys.stderr)
            raise SystemExit(2)

        # Locate the A2MC repo root: parent of phases/phase0_design/
        a2mc_root = Path(__file__).resolve().parent.parent.parent
        create_case = a2mc_root / 'tools' / 'create_case.sh'
        if not create_case.is_file():
            raise SystemExit(f"ERROR: tools/create_case.sh not found at {create_case}")

        return cls(
            site_config=Path(os.environ['A2MC_SITE_CONFIG']),
            param_dir=Path(os.environ['A2MC_PARAM_DIR']),
            param_pattern=os.environ['A2MC_PARAM_PATTERN'],
            case_name_pattern=os.environ['A2MC_CASE_NAME_PATTERN'],
            ensemble_output=Path(os.environ['A2MC_ENSEMBLE_OUTPUT']),
            case_scripts=Path(os.environ['A2MC_CASE_SCRIPTS']),
            a2mc_root=a2mc_root,
            create_case=create_case,
            ensemble_name=os.environ.get('A2MC_ENSEMBLE_NAME', ''),
            ensemble_matrix_file=(
                Path(os.environ['A2MC_ENSEMBLE_MATRIX_FILE'])
                if os.environ.get('A2MC_ENSEMBLE_MATRIX_FILE') else None
            ),
            sampling_scheme=os.environ.get('A2MC_SAMPLING_SCHEME', ''),
        )


# ---------------------------------------------------------------------------
# Per-case helpers
# ---------------------------------------------------------------------------

def find_param_file(cfg: Config, case_num: int) -> Optional[Path]:
    """Return the parameter file for case_num, or None if missing.

    Primary lookup: substitute {N} into $A2MC_PARAM_PATTERN (extension-agnostic).
    Fallback: glob for `*En{case_num}*.{nc,json}` (v2.100+: api-43 uses JSON).
    """
    expected = cfg.param_dir / cfg.param_pattern.replace('{N}', str(case_num))
    if expected.is_file():
        return expected
    # Fall back to a glob in case the pattern doesn't match exactly
    for ext in ('nc', 'json'):
        matches = list(cfg.param_dir.glob(f'*En{case_num}*.{ext}'))
        if matches:
            return matches[0]
    return None


def per_case_script_path(cfg: Config, case_num: int) -> Path:
    """Return the path where the per-case script for case_num lives."""
    return cfg.case_scripts / f'En{case_num}.sh'


def parse_case_list(args: argparse.Namespace) -> List[int]:
    """Build the list of case numbers from --start/--end OR --cases-file."""
    if args.cases_file:
        cases = []
        for line in args.cases_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                cases.append(int(line.split(',')[0]))
            except ValueError:
                print(f"WARNING: ignoring unparseable line in {args.cases_file}: {line!r}",
                      file=sys.stderr)
        if not cases:
            raise SystemExit(f"ERROR: no case numbers in {args.cases_file}")
        return cases
    if args.start is None or args.end is None:
        raise SystemExit("ERROR: must provide --start AND --end, OR --cases-file")
    if args.start > args.end:
        raise SystemExit(f"ERROR: --start ({args.start}) > --end ({args.end})")
    return list(range(args.start, args.end + 1))


# ---------------------------------------------------------------------------
# Stage 3a: generate per-case scripts
# ---------------------------------------------------------------------------

def generate_one_script(
    cfg: Config,
    case_num: int,
    build_case: int,
    do_submit: bool,
) -> Path:
    """Invoke create_case.sh --write-script for one case. Returns the script path."""
    param_file = find_param_file(cfg, case_num)
    if param_file is None:
        raise FileNotFoundError(
            f"No parameter file for case {case_num} in {cfg.param_dir} "
            f"(pattern: {cfg.param_pattern})"
        )

    script_path = per_case_script_path(cfg, case_num)
    cmd = [
        'bash', str(cfg.create_case),
        '--case-num', str(case_num),
        '--param-file', str(param_file),
        '--config', str(cfg.site_config),
        '--write-script', str(script_path),
    ]
    if case_num != build_case:
        cmd += ['--reuse-build', str(build_case)]
    if do_submit:
        cmd += ['--submit']

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAILED to generate script for case {case_num}", file=sys.stderr)
        print(f"  stdout: {result.stdout[-400:]}", file=sys.stderr)
        print(f"  stderr: {result.stderr[-400:]}", file=sys.stderr)
        raise RuntimeError(f"create_case.sh --write-script failed for case {case_num}")
    if not script_path.is_file():
        raise RuntimeError(f"create_case.sh did not write {script_path}")
    return script_path


def generate_all_scripts(
    cfg: Config,
    cases: List[int],
    build_case: int,
    do_submit: bool,
) -> None:
    """Generate per-case scripts for every case. Writes to $A2MC_CASE_SCRIPTS."""
    cfg.case_scripts.mkdir(parents=True, exist_ok=True)
    print(f"Generating {len(cases)} per-case scripts in {cfg.case_scripts}")
    for i, n in enumerate(cases, 1):
        generate_one_script(cfg, n, build_case, do_submit)
        if i % 100 == 0 or i == len(cases):
            print(f"  generated {i}/{len(cases)}")


# ---------------------------------------------------------------------------
# Stage 3c: coordinated submit
# ---------------------------------------------------------------------------

def run_one_script(script: Path, log: Path) -> int:
    """Run a per-case script, redirecting stdout+stderr to a log file. Returns exit code."""
    with log.open('w') as logf:
        result = subprocess.run(['bash', str(script)], stdout=logf, stderr=subprocess.STDOUT)
    return result.returncode


def submit_build_case(cfg: Config, build_case: int) -> None:
    """Run the build case synchronously. Must succeed before remaining cases launch."""
    script = per_case_script_path(cfg, build_case)
    log = cfg.case_scripts / f'En{build_case}.log'
    print(f"\nStage 3c.1: running build case {build_case} (synchronous; build will take ~30 min)")
    print(f"  script: {script}")
    print(f"  log:    {log}")
    t0 = time.time()
    rc = run_one_script(script, log)
    elapsed = time.time() - t0
    if rc != 0:
        print(f"\nBUILD CASE FAILED (exit {rc}) after {elapsed:.0f}s", file=sys.stderr)
        print(f"Inspect log: {log}", file=sys.stderr)
        # Show the tail of the log for quick triage
        if log.is_file():
            tail = log.read_text().splitlines()[-30:]
            print("--- last 30 lines of log ---", file=sys.stderr)
            for line in tail:
                print(line, file=sys.stderr)
        raise SystemExit(3)
    print(f"  build case completed in {elapsed:.0f}s ({elapsed/60:.1f} min)")


def submit_remaining_cases(
    cfg: Config,
    remaining_cases: List[int],
    batch_size: int,
) -> None:
    """Run remaining per-case scripts in parallel batches.

    Each script does create_case + xmlchange EXEROOT + case.setup + case.submit
    (no build, since --reuse-build was set). Typical per-script wall time: ~1-2 min.
    """
    print(f"\nStage 3c.2: submitting {len(remaining_cases)} remaining cases "
          f"in batches of {batch_size}")
    n_batches = (len(remaining_cases) + batch_size - 1) // batch_size
    n_ok, n_fail = 0, 0
    for b in range(n_batches):
        batch = remaining_cases[b * batch_size:(b + 1) * batch_size]
        print(f"  batch {b+1}/{n_batches}: cases {batch[0]}..{batch[-1]} ({len(batch)} parallel)")
        # Launch each script in the background
        procs = []
        for n in batch:
            script = per_case_script_path(cfg, n)
            log = cfg.case_scripts / f'En{n}.log'
            logf = log.open('w')
            p = subprocess.Popen(['bash', str(script)], stdout=logf, stderr=subprocess.STDOUT)
            procs.append((n, p, logf))
        # Wait for all
        for n, p, logf in procs:
            rc = p.wait()
            logf.close()
            if rc == 0:
                n_ok += 1
            else:
                n_fail += 1
                print(f"    case {n}: FAILED (exit {rc}; see {cfg.case_scripts}/En{n}.log)",
                      file=sys.stderr)
    print(f"  submission summary: {n_ok} OK, {n_fail} FAILED")
    if n_fail:
        print(f"\n{n_fail} case(s) failed to submit. Inspect logs in {cfg.case_scripts}/")
        raise SystemExit(4)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _git_commit(repo: Path) -> Optional[str]:
    """Return the HEAD commit short hash of the git repo at `repo`, or None."""
    if not (repo / '.git').exists() and not (repo / '.git').is_file():
        return None
    try:
        out = subprocess.check_output(
            ['git', '-C', str(repo), 'rev-parse', '--short', 'HEAD'],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return out
    except Exception:
        return None


def write_manifest(cfg: Config, cases: List[int], build_case: int, do_submit: bool) -> Path:
    """Write $A2MC_ENSEMBLE_OUTPUT/submission_manifest.json for audit."""
    cfg.ensemble_output.mkdir(parents=True, exist_ok=True)
    manifest_path = cfg.ensemble_output / 'submission_manifest.json'

    # Try to identify the FATES + ELM commits
    e3sm_root = os.environ.get('A2MC_E3SM_ROOT', '') or os.environ.get('E3SM_ROOT', '')
    fates_commit, elm_commit = None, None
    if e3sm_root:
        fates_path = Path(e3sm_root) / 'components' / 'elm' / 'src' / 'external_models' / 'fates'
        elm_path = Path(e3sm_root) / 'components' / 'elm'
        fates_commit = _git_commit(fates_path)
        elm_commit = _git_commit(elm_path)

    manifest = {
        'timestamp': _dt.datetime.utcnow().isoformat() + 'Z',
        'site_config': str(cfg.site_config),
        'ensemble_name': cfg.ensemble_name,
        'sampling_scheme': cfg.sampling_scheme,
        'case_range': [min(cases), max(cases)] if cases else None,
        'n_cases': len(cases),
        'build_case': build_case,
        'submit_to_slurm': do_submit,
        'matrix_file': str(cfg.ensemble_matrix_file) if cfg.ensemble_matrix_file else None,
        'matrix_sha256': _sha256_file(cfg.ensemble_matrix_file) if cfg.ensemble_matrix_file else None,
        'param_dir': str(cfg.param_dir),
        'param_pattern': cfg.param_pattern,
        'case_name_pattern': cfg.case_name_pattern,
        'case_scripts': str(cfg.case_scripts),
        'ensemble_output': str(cfg.ensemble_output),
        'protocol': {
            k.lower(): os.environ.get(k, '') for k in [
                'A2MC_ADSP_SUPLPHOS', 'A2MC_ADSP_SUPLNITRO',
                'A2MC_RGSP_SUPLPHOS', 'A2MC_RGSP_SUPLNITRO',
                'A2MC_TRANS_SUPLPHOS', 'A2MC_TRANS_SUPLNITRO',
            ]
        },
        'fates_commit': fates_commit,
        'elm_commit': elm_commit,
        'e3sm_root': e3sm_root,
    }
    with manifest_path.open('w') as f:
        json.dump(manifest, f, indent=2)
    print(f"\nWrote submission manifest: {manifest_path}")
    return manifest_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submit a Phase 0 ensemble with build-coordination.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--start', type=int, default=None, help="Range start (inclusive)")
    parser.add_argument('--end', type=int, default=None, help="Range end (inclusive)")
    parser.add_argument('--cases-file', type=Path, default=None,
                        help="Alternative to --start/--end: file with one case number per line")
    parser.add_argument('--build-case', type=int, default=None,
                        help="Case number to build fresh (default: smallest in range / first in file)")
    parser.add_argument('--batch-size', type=int, default=20,
                        help="Number of cases to launch in parallel per batch (default: 20)")
    parser.add_argument('--dry-run', action='store_true',
                        help="Generate per-case scripts + print plan; don't run them")
    parser.add_argument('--submit', action='store_true',
                        help="Tell the per-case scripts to call case.submit (queue SLURM jobs)")
    parser.add_argument('--no-manifest', action='store_true',
                        help="Skip writing submission_manifest.json")
    parser.add_argument('--no-validate', action='store_true',
                        help="Skip auto-invoking tools/validate_submission_plan.py")
    parser.add_argument('--allow-existing-case-dirs', action='store_true',
                        help="Forwarded to the validator: suppress 'CIME case dir already exists' warning")
    parser.add_argument('--skip-build-case', action='store_true',
                        help="Skip Stage 3c.1 (running the build case synchronously). "
                             "Use when the build case has already been completed by a separate "
                             "submit_phase0.py call (e.g., a pilot run) and is currently running or "
                             "queued in SLURM. The build_case is then ONLY used as the --reuse-build "
                             "target for the En*.sh scripts of cases in --start/--end (its own "
                             "En*.sh is left alone). When set, --build-case is allowed to be "
                             "outside the case range.")
    args = parser.parse_args()

    cfg = Config.from_env()
    cases = parse_case_list(args)
    build_case = args.build_case if args.build_case is not None else cases[0]
    if build_case not in cases and not args.skip_build_case:
        raise SystemExit(f"ERROR: --build-case {build_case} not in case list "
                         f"(use --skip-build-case if the build case has already been "
                         f"completed/submitted by a separate orchestrator call)")
    if args.skip_build_case and build_case in cases:
        print(f"WARNING: --skip-build-case skips Stage 3c.1 entirely, but build_case "
              f"{build_case} IS in [{min(cases)}..{max(cases)}]. Its En{build_case}.sh "
              f"will be generated but never run, so case {build_case} will not be submitted "
              f"to SLURM by this invocation. Pass --build-case OUTSIDE the case range to "
              f"avoid generating its En*.sh.", file=sys.stderr)

    print("=" * 60)
    print("A2MC Phase 0 — Submit Ensemble")
    print("=" * 60)
    print(f"  site config:        {cfg.site_config}")
    print(f"  ensemble name:      {cfg.ensemble_name}")
    print(f"  case name pattern:  {cfg.case_name_pattern}")
    print(f"  param dir:          {cfg.param_dir}")
    print(f"  ensemble output:    {cfg.ensemble_output}")
    print(f"  case scripts:       {cfg.case_scripts}")
    print(f"  total cases:        {len(cases)}  (range {min(cases)}..{max(cases)})")
    if args.skip_build_case:
        print(f"  build case:         {build_case}  (--skip-build-case: assumed already done; only used as --reuse-build target)")
    else:
        print(f"  build case:         {build_case}  (fresh build; cases below reuse its bld/)")
    print(f"  batch size:         {args.batch_size}")
    print(f"  submit to SLURM:    {args.submit}")
    print(f"  dry-run:            {args.dry_run}")
    print(f"  skip build case:    {args.skip_build_case}")
    print()

    # Stage 3a: generate per-case scripts
    print("Stage 3a: generate per-case scripts")
    generate_all_scripts(cfg, cases, build_case, do_submit=args.submit)

    # Manifest (always write — useful even in dry-run)
    if not args.no_manifest:
        write_manifest(cfg, cases, build_case, do_submit=args.submit)

    # Stage 3b: pre-flight validation (auto-invoke validate_submission_plan.py)
    if not args.no_validate:
        print("\nStage 3b: pre-flight validation")
        validator = cfg.a2mc_root / 'tools' / 'validate_submission_plan.py'
        if validator.is_file():
            val_cmd = [sys.executable, str(validator), '--scripts-required']
            if args.cases_file:
                val_cmd += ['--cases-file', str(args.cases_file)]
            else:
                val_cmd += ['--start', str(args.start), '--end', str(args.end)]
            if args.allow_existing_case_dirs:
                val_cmd += ['--allow-existing-case-dirs']
            v_result = subprocess.run(val_cmd)
            if v_result.returncode != 0:
                print(f"\nPRE-FLIGHT VALIDATION FAILED (exit {v_result.returncode}); aborting.",
                      file=sys.stderr)
                print(f"(Re-run validator: {shlex.join(val_cmd)})", file=sys.stderr)
                raise SystemExit(2)
            print("Pre-flight validation passed.")
        else:
            print(f"  (validator not found at {validator}; skipping)")

    if args.dry_run:
        print("\n[DRY RUN] Per-case scripts generated. Review with:")
        print(f"  ls -1 {cfg.case_scripts}/En*.sh | head -5")
        print("Then re-run without --dry-run to execute.")
        return 0

    # Stage 3c: coordinated submit
    if args.skip_build_case:
        print(f"\nStage 3c.1: SKIPPED (--skip-build-case). "
              f"Assuming case {build_case} is already complete/running/queued "
              f"and its bld/ is available for --reuse-build {build_case}.")
    else:
        submit_build_case(cfg, build_case)
    remaining = [n for n in cases if n != build_case]
    if remaining:
        submit_remaining_cases(cfg, remaining, args.batch_size)

    print("\n" + "=" * 60)
    print("Phase 0 submission complete.")
    print("=" * 60)
    print(f"  monitor:  squeue -u $USER")
    print(f"  status:   python tools/diagnose_ensemble_status.py")
    return 0


if __name__ == '__main__':
    sys.exit(main())
