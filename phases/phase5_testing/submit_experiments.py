#!/usr/bin/env python3
"""
Phase 5: Submit Experiments - Create Cases and Submit to HPC

Submits experiment cases to HPC via tools/submit_experiment.sh.
Each experiment must have a parameter file (from design_experiments.py).

Uses shared tools:
    - tools/submit_experiment.sh → case creation and job submission

Usage:
    # From Python
    from phases.phase5_testing import submit_experiments
    updated = submit_experiments(experiments, submit=True)

    # From CLI
    python phases/phase5_testing/submit_experiments.py \\
        --experiments experiments_with_params.json \\
        --phases TRANS --submit
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)

# Path to submit_experiment.sh
SUBMIT_SCRIPT = _project_root / "tools" / "submit_experiment.sh"


def _is_hpc() -> bool:
    """Check if running on an HPC system with SLURM."""
    try:
        result = subprocess.run(["which", "sbatch"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def _extract_job_id(output: str) -> Optional[str]:
    """Extract SLURM job ID from submission output."""
    # Patterns: "Submitted batch job 12345678" or "with id 12345678"
    match = re.search(r"(?:Submitted batch job|with id)\s+(\d+)", output)
    if match:
        return match.group(1)
    return None


def submit_experiments(
    experiments: List[Dict],
    output_root: Optional[str] = None,
    phases: str = "TRANS",
    submit: bool = True,
    dry_run: bool = False
) -> List[Dict]:
    """
    Submit experiment cases to HPC.

    For each experiment:
    1. Call tools/submit_experiment.sh with --name, --param-file, --base-case
    2. Capture job_id from submission output
    3. Tag experiment with submission status

    When SLURM is not available (local machine), runs in simulated mode:
    logs [SIMULATED] and returns fake job IDs.

    Args:
        experiments: List of experiment dicts. Each must have:
            - 'name': str - Experiment name
            - 'param_file': str - Path to modified parameter file
            - 'base_case': str (optional) - Base case for restart files
        output_root: HPC output directory (default from config/env)
        phases: HPC phases to run (default "TRANS" for quick experiments)
        submit: Actually submit (vs just build cases)
        dry_run: Preview what would be done

    Returns:
        Updated experiment dicts with added fields:
            - 'job_id': str or None - SLURM job ID
            - 'submission_status': str - 'submitted', 'simulated', 'failed', etc.
            - 'case_name': str - Full case name on HPC
    """
    is_hpc = _is_hpc()

    if not is_hpc:
        logger.warning("SLURM not available - running in SIMULATED mode")

    if not SUBMIT_SCRIPT.exists():
        logger.error(f"Submit script not found: {SUBMIT_SCRIPT}")
        # Still allow simulated mode
        if is_hpc:
            raise FileNotFoundError(f"Submit script not found: {SUBMIT_SCRIPT}")

    # Resolve output_root from environment if not provided
    if output_root is None:
        output_root = os.environ.get("A2MC_OUTPUT_ROOT", "")

    updated_experiments = []

    for exp in experiments:
        exp = dict(exp)  # Don't modify the original

        name = exp.get("name", "unnamed")
        param_file = exp.get("param_file")
        base_case = exp.get("base_case", "")

        # Skip experiments without parameter files
        if not param_file or exp.get("param_status") == "creation_failed":
            logger.warning(f"Skipping '{name}': no valid parameter file")
            exp["submission_status"] = "skipped_no_param_file"
            updated_experiments.append(exp)
            continue

        if dry_run:
            logger.info(f"[DRY RUN] Would submit: {name} (param_file={param_file}, "
                        f"base_case={base_case}, phases={phases})")
            exp["submission_status"] = "dry_run"
            updated_experiments.append(exp)
            continue

        if not is_hpc:
            # Simulated mode
            fake_job_id = f"SIM_{abs(hash(name)) % 100000:06d}"
            logger.info(f"[SIMULATED] Experiment '{name}': job_id={fake_job_id}")
            exp["job_id"] = fake_job_id
            exp["submission_status"] = "simulated"
            exp["case_name"] = f"simulated_{name}"
            updated_experiments.append(exp)
            continue

        # Build command for submit_experiment.sh
        cmd = [str(SUBMIT_SCRIPT), "--name", name, "--param-file", param_file]

        if base_case:
            # Format base case: ensure it has the expected prefix
            # submit_experiment.sh expects just the case identifier (e.g., "En2678")
            base_case_str = str(base_case)
            if base_case_str.isdigit():
                base_case_str = f"En{base_case_str}"
            cmd.extend(["--base-case", base_case_str])

        if output_root:
            cmd.extend(["--output-root", output_root])

        cmd.extend(["--phases", phases])

        if submit:
            cmd.append("--submit")

        try:
            logger.info(f"Submitting experiment '{name}': {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes for case creation + submission
            )

            if result.returncode == 0:
                job_id = _extract_job_id(result.stdout)
                exp["job_id"] = job_id
                exp["submission_status"] = "submitted" if submit else "built"
                exp["submission_output"] = result.stdout[-500:]  # Last 500 chars
                logger.info(f"Submitted '{name}': job_id={job_id}")
            else:
                logger.error(f"Submission failed for '{name}': {result.stderr}")
                exp["job_id"] = None
                exp["submission_status"] = "submission_failed"
                exp["error"] = result.stderr[-500:]

        except subprocess.TimeoutExpired:
            logger.error(f"Submission timed out for '{name}'")
            exp["job_id"] = None
            exp["submission_status"] = "submission_timeout"
        except Exception as e:
            logger.error(f"Submission error for '{name}': {e}")
            exp["job_id"] = None
            exp["submission_status"] = "submission_failed"
            exp["error"] = str(e)

        updated_experiments.append(exp)

    # Summary
    submitted = sum(1 for e in updated_experiments if e.get("submission_status") == "submitted")
    simulated = sum(1 for e in updated_experiments if e.get("submission_status") == "simulated")
    failed = sum(1 for e in updated_experiments if "failed" in e.get("submission_status", ""))
    logger.info(f"\nSubmission summary: {submitted} submitted, {simulated} simulated, "
                f"{failed} failed, {len(updated_experiments)} total")

    return updated_experiments


def main():
    parser = argparse.ArgumentParser(
        description="Submit A2MC experiments to HPC"
    )
    parser.add_argument("--experiments", required=True,
                        help="JSON file with experiment specifications")
    parser.add_argument("--output-root", default=None,
                        help="HPC output directory")
    parser.add_argument("--phases", default="TRANS",
                        help="HPC phases to run (default: TRANS)")
    parser.add_argument("--submit", action="store_true",
                        help="Submit jobs after building")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without executing")

    args = parser.parse_args()

    # Load experiments
    with open(args.experiments) as f:
        experiments = json.load(f)

    if not isinstance(experiments, list):
        experiments = [experiments]

    # Submit
    updated = submit_experiments(
        experiments=experiments,
        output_root=args.output_root,
        phases=args.phases,
        submit=args.submit,
        dry_run=args.dry_run
    )

    # Write updated experiments
    output_file = Path(args.experiments).parent / "experiments_submitted.json"
    with open(output_file, "w") as f:
        json.dump(updated, f, indent=2)
    print(f"\nUpdated experiments written to: {output_file}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
