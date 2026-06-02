#!/usr/bin/env python3
"""
Phase 5: Monitor Experiments - Track Jobs and Extract Results

Monitors SLURM job status and extracts results from completed experiments.
Uses squeue/sacct for job status and tools/ for data extraction and evaluation.

Uses shared tools:
    - tools/extract_monthly_variables_FATES.py (via subprocess)
    - tools/cost_functions.py → CostFunction, aggregate_costs
    - tools/optimize_function.py → Target comparison
    - tools/config.py → paths

Usage:
    # From Python
    from phases.phase5_testing import (
        check_experiment_status, wait_for_experiments, extract_experiment_results
    )
    experiments = check_experiment_status(experiments)
    experiments = wait_for_experiments(experiments, timeout=86400)
    experiments = extract_experiment_results(experiments)

    # From CLI
    python phases/phase5_testing/monitor_experiments.py --status experiments.json
    python phases/phase5_testing/monitor_experiments.py --wait --extract --experiments experiments.json
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)


def _is_hpc() -> bool:
    """Check if running on an HPC system with SLURM."""
    try:
        result = subprocess.run(["which", "squeue"], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def _get_job_status_squeue(job_ids: List[str]) -> Dict[str, str]:
    """
    Check job status via squeue (for queued/running jobs).

    Returns dict of {job_id: status} where status is one of:
    PENDING, RUNNING, COMPLETING, etc. Missing jobs are not in the dict.
    """
    if not job_ids:
        return {}

    try:
        result = subprocess.run(
            ["squeue", "-j", ",".join(job_ids), "-h", "-o", "%i %T"],
            capture_output=True, text=True, timeout=30
        )
        statuses = {}
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = line.strip().split()
                if len(parts) >= 2:
                    statuses[parts[0]] = parts[1]
        return statuses
    except Exception as e:
        logger.warning(f"squeue check failed: {e}")
        return {}


def _get_job_status_sacct(job_ids: List[str]) -> Dict[str, str]:
    """
    Check completed job status via sacct.

    Returns dict of {job_id: status} where status is one of:
    COMPLETED, FAILED, TIMEOUT, CANCELLED, etc.
    """
    if not job_ids:
        return {}

    try:
        result = subprocess.run(
            ["sacct", "-j", ",".join(job_ids), "--format=JobID,State", "-n", "-P"],
            capture_output=True, text=True, timeout=30
        )
        statuses = {}
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                parts = line.strip().split("|")
                if len(parts) >= 2:
                    job_id = parts[0].split(".")[0]  # Remove .batch suffix
                    status = parts[1]
                    # Only record the main job entry (not sub-steps)
                    if job_id in job_ids or any(job_id.startswith(jid) for jid in job_ids):
                        statuses[job_id] = status
        return statuses
    except Exception as e:
        logger.warning(f"sacct check failed: {e}")
        return {}


def check_experiment_status(experiments: List[Dict]) -> List[Dict]:
    """
    Check SLURM job status for submitted experiments.

    Updates each experiment's 'job_status' field with current SLURM status.

    Args:
        experiments: List of experiment dicts with 'job_id' field

    Returns:
        Updated experiment dicts with 'job_status' field
    """
    is_hpc = _is_hpc()

    # Collect all job IDs
    job_ids = [exp.get("job_id") for exp in experiments
               if exp.get("job_id") and not exp.get("job_id", "").startswith("SIM_")]

    if not is_hpc or not job_ids:
        # Simulated mode: mark all simulated jobs as "completed"
        for exp in experiments:
            if exp.get("submission_status") == "simulated":
                exp["job_status"] = "SIMULATED_COMPLETE"
            elif not exp.get("job_id"):
                exp["job_status"] = "NO_JOB"
        return experiments

    # Check squeue first (running/pending)
    squeue_statuses = _get_job_status_squeue(job_ids)

    # For jobs not in squeue, check sacct (completed/failed)
    missing_ids = [jid for jid in job_ids if jid not in squeue_statuses]
    sacct_statuses = _get_job_status_sacct(missing_ids)

    # Update experiments
    for exp in experiments:
        job_id = exp.get("job_id")
        if not job_id:
            exp["job_status"] = "NO_JOB"
        elif job_id.startswith("SIM_"):
            exp["job_status"] = "SIMULATED_COMPLETE"
        elif job_id in squeue_statuses:
            exp["job_status"] = squeue_statuses[job_id]
        elif job_id in sacct_statuses:
            exp["job_status"] = sacct_statuses[job_id]
        else:
            exp["job_status"] = "UNKNOWN"

    return experiments


def wait_for_experiments(
    experiments: List[Dict],
    poll_interval: int = 60,
    timeout: int = 86400
) -> List[Dict]:
    """
    Poll until all experiments complete or timeout.

    Args:
        experiments: List of experiment dicts with 'job_id' field
        poll_interval: Seconds between status checks (default 60)
        timeout: Max wait time in seconds (default 24h)

    Returns:
        Updated experiment dicts with final 'job_status'
    """
    is_hpc = _is_hpc()

    if not is_hpc:
        logger.info("[SIMULATED] All experiments instantly 'complete'")
        for exp in experiments:
            if exp.get("submission_status") == "simulated":
                exp["job_status"] = "SIMULATED_COMPLETE"
        return experiments

    # Only wait for real submitted jobs
    submitted = [exp for exp in experiments
                 if exp.get("job_id") and not exp.get("job_id", "").startswith("SIM_")]

    if not submitted:
        logger.info("No real HPC jobs to wait for")
        return experiments

    start_time = time.time()
    timeout_str = f"{timeout}s" if timeout > 0 else "unlimited"
    logger.info(f"Waiting for {len(submitted)} experiments (timeout={timeout_str}, "
                f"poll={poll_interval}s)...")

    while True:
        experiments = check_experiment_status(experiments)

        # Check if all done
        still_running = []
        for exp in submitted:
            status = exp.get("job_status", "UNKNOWN")
            if status in ("PENDING", "RUNNING", "COMPLETING", "CONFIGURING"):
                still_running.append(exp)

        if not still_running:
            logger.info("All experiments complete.")
            break

        elapsed = time.time() - start_time
        if timeout > 0 and elapsed > timeout:
            logger.warning(f"Timeout ({timeout}s) reached. "
                           f"{len(still_running)} experiments still running.")
            for exp in still_running:
                exp["job_status"] = "WAIT_TIMEOUT"
            break

        logger.info(f"  {len(still_running)}/{len(submitted)} still running "
                     f"({elapsed:.0f}s elapsed)")
        time.sleep(poll_interval)

    return experiments


def extract_experiment_results(
    experiments: List[Dict],
    variables: Optional[List[str]] = None,
    analysis_period: Tuple[int, int] = (2010, 2019),
    output_root: Optional[str] = None,
    targets: Optional[Dict] = None
) -> List[Dict]:
    """
    Extract results from completed experiments and evaluate against targets.

    For simulated experiments (no real output), sets status to 'extraction_failed'
    with a clear message.

    For real experiments:
    1. Calls tools/extract_monthly_variables_FATES.py to extract data
    2. Loads extracted data
    3. Evaluates against validation targets using cost_functions

    Args:
        experiments: List of experiment dicts with 'job_status' field
        variables: Variables to extract (default: standard biomass set)
        analysis_period: Year range for mean calculation (default 2010-2019)
        output_root: HPC output directory (default from config/env)
        targets: Validation targets dict {name: Target} from orchestrator.
            If None, attempts to load from config.

    Returns:
        Updated experiment dicts with 'results' field
    """
    if output_root is None:
        output_root = os.environ.get("A2MC_OUTPUT_ROOT", "")

    if variables is None:
        variables = [
            "FATES_LEAFC", "FATES_FROOTC", "FATES_VEGC_ABOVEGROUND",
            "FATES_LEAFC_PF", "FATES_FROOTC_PF",
        ]

    extract_script = _project_root / "tools" / "extract_monthly_variables_FATES.py"

    for exp in experiments:
        name = exp.get("name", "unnamed")
        job_status = exp.get("job_status", "UNKNOWN")

        # Skip experiments that were never submitted or failed to submit
        sub_status = exp.get("submission_status", "")
        if (job_status == "NO_JOB" or
                sub_status in ("skipped_no_param_file", "submission_failed",
                               "submission_timeout")):
            logger.warning(f"Skipping '{name}': never ran on HPC "
                          f"(submission_status={sub_status})")
            exp["extraction_status"] = "skipped_not_submitted"
            exp["results"] = {"error": f"Experiment never ran: {sub_status}"}
            continue

        # Skip definitively failed experiments
        if job_status in ("FAILED", "TIMEOUT", "CANCELLED"):
            exp["extraction_status"] = "skipped_job_failed"
            exp["results"] = {"error": f"Job {job_status}"}
            continue

        # Simulated mode: no real output to extract
        if job_status == "SIMULATED_COMPLETE":
            logger.info(f"[SIMULATED] '{name}': no real output to extract")
            exp["extraction_status"] = "simulated_no_output"
            exp["results"] = {
                "note": "Simulated mode - no real simulation output",
                "targets_met": 0,
                "total_targets": 0,
                "metrics": {}
            }
            continue

        # For non-COMPLETED jobs (UNKNOWN, NO_JOB, etc.), try extraction anyway —
        # the job may have completed while the orchestrator was offline
        if job_status not in ("COMPLETED",):
            logger.info(f"'{name}': job_status={job_status}, attempting extraction "
                       f"(job may have completed while offline)")

        # Real extraction
        case_name = exp.get("case_name", name)
        try:
            logger.info(f"Extracting results for '{name}'...")

            # Call extraction script
            cmd = [
                sys.executable, str(extract_script),
                "--cases", case_name
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )

            if result.returncode != 0:
                logger.error(f"Extraction failed for '{name}': {result.stderr}")
                exp["extraction_status"] = "extraction_failed"
                exp["results"] = {"error": result.stderr[-500:]}
                continue

            exp["extraction_status"] = "extracted"

            # The extraction script returns 0 even when its internal process_case()
            # fails to find h0 files (it prints a stdout warning, then continues).
            # Verify an NC actually landed so the status field doesn't lie to
            # downstream consumers (e.g. Phase 6 auto_learn). See dev_log
            # 20260519a for the contamination that this guards against.
            from tools.evaluate_case import find_extracted_nc
            search_dirs = []
            try:
                from tools.config import config as a2mc_config
                extracted_dir = Path(a2mc_config.EXTRACTED_DATA)
                if extracted_dir.exists():
                    search_dirs.append(extracted_dir)
            except (ImportError, AttributeError):
                pass
            if output_root:
                search_dirs.append(Path(output_root))
            if find_extracted_nc(case_name, search_dirs) is None:
                logger.error(
                    f"Extraction subprocess returned 0 but no NC file found "
                    f"for '{name}' (case_name='{case_name}'). "
                    f"Treating as extraction_failed."
                )
                exp["extraction_status"] = "extraction_failed"
                exp["results"] = {
                    "error": (
                        f"Extractor exited 0 but no NC found for {case_name}. "
                        f"Likely case-name interpolation mismatch or missing h0 files."
                    ),
                    "targets_met": 0,
                    "total_targets": len(targets) if targets else 0,
                    "metrics": {}
                }
                continue

            # Try to load and evaluate extracted data
            try:
                results = _evaluate_experiment(
                    case_name, output_root, analysis_period, targets=targets
                )
                exp["results"] = results
            except Exception as e:
                logger.warning(f"Evaluation failed for '{name}': {e}")
                exp["extraction_status"] = "evaluation_failed"
                exp["results"] = {"error": str(e), "extraction": "success"}

        except subprocess.TimeoutExpired:
            logger.error(f"Extraction timed out for '{name}'")
            exp["extraction_status"] = "extraction_timeout"
            exp["results"] = {"error": "Extraction timed out"}
        except Exception as e:
            logger.error(f"Extraction error for '{name}': {e}")
            exp["extraction_status"] = "extraction_failed"
            exp["results"] = {"error": str(e)}

    return experiments


def _evaluate_experiment(
    case_name: str,
    output_root: str,
    analysis_period: Tuple[int, int],
    targets: Optional[Dict] = None
) -> Dict:
    """
    Load extracted data and evaluate against validation targets.

    Delegates to the shared tools/evaluate_case.py which is the same
    evaluation logic used by Phase 2 screening.

    Args:
        case_name: Experiment case name
        output_root: HPC output directory
        analysis_period: Year range (year_start, year_end)
        targets: Validation targets {name: Target}. If None, loads from config.

    Returns:
        Dict with targets_met, total_targets, composite_cost, and per-target metrics
    """
    from tools.evaluate_case import evaluate_case, find_extracted_nc

    # --- 1. Load validation targets ---
    if targets is None:
        try:
            from phases.phase2_screening.screen_ensemble import load_kougarok_targets
            targets = load_kougarok_targets()
        except ImportError:
            pass

    if not targets:
        return {
            "error": "No validation targets available",
            "targets_met": 0,
            "total_targets": 0,
            "metrics": {}
        }

    # --- 2. Find the extracted NC file ---
    # Build search directories
    search_dirs = []
    try:
        from tools.config import config as a2mc_config
        extracted_dir = Path(a2mc_config.EXTRACTED_DATA)
        if extracted_dir.exists():
            search_dirs.append(extracted_dir)
    except (ImportError, AttributeError):
        pass
    if output_root:
        search_dirs.append(Path(output_root))

    nc_file = find_extracted_nc(case_name, search_dirs)
    if nc_file is None:
        return {
            "error": f"Extracted NC file not found for {case_name}",
            "targets_met": 0,
            "total_targets": len(targets),
            "metrics": {}
        }

    logger.info(f"  Loading extracted data from: {nc_file}")

    # --- 3. Compute observation timestep index ---
    year_start = analysis_period[0]
    obs_year = int(os.environ.get('A2MC_OBS_YEAR', '2016'))
    obs_month = int(os.environ.get('A2MC_OBS_MONTH', '7'))
    obs_idx = (obs_year - year_start) * 12 + obs_month - 1

    # --- 4. Evaluate using shared utility ---
    results = evaluate_case(nc_file, targets, obs_idx)

    # Add experiment-specific metadata
    results["analysis_period"] = list(analysis_period)
    results["obs_timestep"] = f"{obs_year}-{obs_month:02d}"
    results["nc_file"] = str(nc_file)

    # Log results
    n_met = results.get("targets_met", 0)
    n_total = results.get("total_targets", 0)
    cost = results.get("composite_cost", float("inf"))
    logger.info(f"  Evaluation: {n_met}/{n_total} targets met, composite RMSRE={cost:.4f}")
    for tname, m in results.get("per_target", {}).items():
        status = "OK" if m.get("within_20pct") else "FAIL"
        logger.info(f"    {tname}: sim={m['simulated']:.1f} obs={m['observed']:.1f} "
                     f"RE={m['relative_error']:.3f} [{status}]")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Monitor A2MC experiments and extract results"
    )
    parser.add_argument("--experiments", required=True,
                        help="JSON file with experiment specifications")
    parser.add_argument("--status", action="store_true",
                        help="Check and display job status")
    parser.add_argument("--wait", action="store_true",
                        help="Wait for all experiments to complete")
    parser.add_argument("--extract", action="store_true",
                        help="Extract results from completed experiments")
    parser.add_argument("--poll-interval", type=int, default=60,
                        help="Poll interval in seconds (default 60)")
    parser.add_argument("--timeout", type=int, default=86400,
                        help="Wait timeout in seconds (default 86400)")

    args = parser.parse_args()

    # Load experiments
    with open(args.experiments) as f:
        experiments = json.load(f)

    if not isinstance(experiments, list):
        experiments = [experiments]

    if args.status or args.wait:
        experiments = check_experiment_status(experiments)

        # Print status
        print("\n" + "=" * 60)
        print("Experiment Status")
        print("=" * 60)
        for exp in experiments:
            name = exp.get("name", "unnamed")
            job_id = exp.get("job_id", "N/A")
            status = exp.get("job_status", "UNKNOWN")
            print(f"  {name}: {status} (job_id={job_id})")
        print("=" * 60)

    if args.wait:
        experiments = wait_for_experiments(
            experiments,
            poll_interval=args.poll_interval,
            timeout=args.timeout
        )

    if args.extract:
        experiments = extract_experiment_results(experiments)

        # Print results summary
        print("\n" + "=" * 60)
        print("Experiment Results")
        print("=" * 60)
        for exp in experiments:
            name = exp.get("name", "unnamed")
            ext_status = exp.get("extraction_status", "not_extracted")
            results = exp.get("results", {})
            met = results.get("targets_met", "?")
            total = results.get("total_targets", "?")
            print(f"  {name}: {ext_status} (targets: {met}/{total})")
        print("=" * 60)

    # Write updated experiments
    output_file = Path(args.experiments).parent / "experiments_results.json"
    with open(output_file, "w") as f:
        json.dump(experiments, f, indent=2)
    print(f"\nUpdated experiments written to: {output_file}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
