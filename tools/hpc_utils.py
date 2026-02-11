#!/usr/bin/env python3
"""
HPC Utilities for A2MC

Provides site-agnostic HPC integration:
- HPCConfig: NERSC Perlmutter configuration (auto-loads from env/config)
- HPCExecutor: SLURM job submission and monitoring
- ParameterManager: FATES parameter file modification wrapper

Author: Jing Tao with Claude
"""

import os
import time
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Get the path to the tools directory (bundled with A2MC)
TOOLS_DIR = Path(__file__).parent


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class HPCConfig:
    """
    NERSC Perlmutter HPC configuration.
    Paths loaded from environment (source a2mc_config.sh).
    """
    project: str = ""
    scratch_root: str = ""
    output_root: str = ""
    scripts_dir: str = ""
    queue: str = "regular"
    time_limit: str = "12:00:00"
    nodes: int = 1
    constraint: str = "cpu"
    case_root: str = ""
    param_dir: str = ""
    extracted_data: str = ""
    modify_params_script: str = ""

    def __post_init__(self):
        """Load from environment or tools.config."""
        try:
            from tools.config import config as a2mc_config
            self.project = self.project or a2mc_config.PROJECT
            self.output_root = self.output_root or a2mc_config.OUTPUT_ROOT
            self.scripts_dir = self.scripts_dir or a2mc_config.SCRIPTS_DIR
            self.case_root = self.case_root or a2mc_config.ENSEMBLE_OUTPUT
            self.param_dir = self.param_dir or a2mc_config.PARAM_DIR
            self.extracted_data = self.extracted_data or a2mc_config.EXTRACTED_DATA
        except (ImportError, AttributeError):
            pass
        self.project = self.project or os.environ.get('A2MC_PROJECT', 'm2467')
        self.scratch_root = self.scratch_root or os.environ.get('A2MC_SCRATCH_ROOT', '')
        self.output_root = self.output_root or os.environ.get('A2MC_OUTPUT_ROOT', '')
        self.scripts_dir = self.scripts_dir or os.environ.get('A2MC_SCRIPTS_DIR', '')
        self.case_root = self.case_root or os.environ.get('A2MC_ENSEMBLE_OUTPUT', '')
        self.param_dir = self.param_dir or os.environ.get('A2MC_PARAM_DIR', '')
        self.extracted_data = self.extracted_data or os.environ.get('A2MC_EXTRACTED_DATA', '')


# ============================================================================
# HPC EXECUTOR
# ============================================================================

class HPCExecutor:
    """
    HPC-native job execution manager.

    Executes directly on NERSC Perlmutter via sbatch/squeue.
    No SSH tunneling - runs locally on the HPC system.
    """

    def __init__(self, config: HPCConfig = None):
        self.config = config or HPCConfig()
        self.logger = logging.getLogger(f"{__name__}.HPCExecutor")
        self._is_hpc = self._check_hpc_environment()

    def _check_hpc_environment(self) -> bool:
        """Check if we're running on HPC with SLURM available."""
        result = subprocess.run(["which", "sbatch"], capture_output=True, text=True)
        is_hpc = result.returncode == 0

        if not is_hpc:
            self.logger.warning("sbatch not found - HPC commands will be simulated")

        return is_hpc

    def submit_job(
        self,
        job_script: str,
        job_name: str = "a2mc_exp",
        dependencies: List[str] = None
    ) -> str:
        """
        Submit a job to SLURM queue.

        Args:
            job_script: Path to job script
            job_name: Name for the job
            dependencies: List of job IDs this job depends on

        Returns:
            Job ID from SLURM (or simulated ID if not on HPC)
        """
        if not self._is_hpc:
            fake_id = f"SIM_{int(time.time())}"
            self.logger.info(f"[SIMULATED] Would submit: {job_script} -> {fake_id}")
            return fake_id

        cmd = ["sbatch"]

        if dependencies:
            dep_str = ":".join(dependencies)
            cmd.extend(["--dependency", f"afterok:{dep_str}"])

        cmd.extend(["--job-name", job_name])
        cmd.append(job_script)

        self.logger.info(f"Submitting job: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"sbatch failed: {result.stderr}")

        job_id = result.stdout.strip().split()[-1]
        self.logger.info(f"Submitted job {job_id}: {job_name}")
        return job_id

    def check_job_status(self, job_id: str) -> Dict:
        """
        Check status of a SLURM job.

        Args:
            job_id: SLURM job ID

        Returns:
            Dict with job status information
        """
        if not self._is_hpc or job_id.startswith("SIM_"):
            return {"job_id": job_id, "status": "SIMULATED", "running": False}

        cmd = ["squeue", "-j", job_id, "--format", "%i|%j|%T|%M|%S", "--noheader"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0 or not result.stdout.strip():
            return self._check_completed_job(job_id)

        parts = result.stdout.strip().split("|")
        if len(parts) >= 4:
            return {
                "job_id": parts[0],
                "name": parts[1],
                "status": parts[2],
                "time": parts[3],
                "start_time": parts[4] if len(parts) > 4 else None,
                "running": parts[2] in ["RUNNING", "PENDING", "CONFIGURING"]
            }

        return {"job_id": job_id, "status": "UNKNOWN", "running": False}

    def _check_completed_job(self, job_id: str) -> Dict:
        """Check completed job via sacct."""
        cmd = ["sacct", "-j", job_id, "--format", "JobID,JobName,State,ExitCode",
               "--noheader", "--parsable2"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return {"job_id": job_id, "status": "UNKNOWN", "running": False}

        lines = result.stdout.strip().split("\n")
        for line in lines:
            parts = line.split("|")
            if len(parts) >= 4 and "." not in parts[0]:
                return {
                    "job_id": parts[0],
                    "name": parts[1],
                    "status": parts[2],
                    "exit_code": parts[3],
                    "running": False
                }

        return {"job_id": job_id, "status": "COMPLETED", "running": False}

    def wait_for_jobs(
        self,
        job_ids: List[str],
        poll_interval: int = 60,
        timeout: int = 86400
    ) -> Dict[str, Dict]:
        """
        Wait for multiple jobs to complete.

        Args:
            job_ids: List of job IDs to monitor
            poll_interval: Seconds between status checks
            timeout: Maximum wait time in seconds

        Returns:
            Dict mapping job_id to final status
        """
        start_time = time.time()
        remaining = set(job_ids)
        results = {}

        self.logger.info(f"Waiting for {len(job_ids)} jobs to complete...")

        while remaining and (time.time() - start_time) < timeout:
            for job_id in list(remaining):
                status = self.check_job_status(job_id)
                if not status.get("running", True):
                    results[job_id] = status
                    remaining.remove(job_id)
                    self.logger.info(f"Job {job_id} completed: {status.get('status')}")

            if remaining:
                self.logger.info(f"Still waiting for {len(remaining)} jobs...")
                time.sleep(poll_interval)

        for job_id in remaining:
            results[job_id] = {"job_id": job_id, "status": "TIMEOUT", "running": True}

        return results

    def submit_experiment(
        self,
        experiment: Dict,
        param_file: str,
        base_case: str = None,
        phases: str = "TRANS",
        wait: bool = False
    ) -> Dict:
        """
        Submit an A2MC experiment using the bundled submit_experiment.sh script.

        Args:
            experiment: Experiment specification with 'name' field
            param_file: Path to modified FATES parameter file
            base_case: Base case name to use for restart file
            phases: Which phases to run (default: "TRANS" for quick experiments)
            wait: Whether to wait for job completion

        Returns:
            Dict with submission results
        """
        exp_name = experiment.get("name", "exp").replace(" ", "_")
        submit_script = TOOLS_DIR / "submit_experiment.sh"

        if not submit_script.exists():
            self.logger.error(f"Submit script not found: {submit_script}")
            return {"success": False, "error": "submit_experiment.sh not found"}

        cmd = [
            "bash", str(submit_script),
            "--name", exp_name,
            "--param-file", param_file,
            "--output-root", self.config.output_root,
            "--phases", phases,
            "--submit"
        ]

        if base_case:
            cmd.extend(["--base-case", base_case])
        if wait:
            cmd.append("--wait")

        self.logger.info(f"Submitting experiment: {exp_name}")

        if not self._is_hpc:
            self.logger.info(f"[SIMULATED] Would run: {' '.join(cmd)}")
            return {"success": True, "simulated": True, "experiment": exp_name, "command": cmd}

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

        if result.returncode != 0:
            self.logger.error(f"Submission failed: {result.stderr}")
            return {"success": False, "error": result.stderr, "stdout": result.stdout}

        job_id = None
        for line in result.stdout.split("\n"):
            if "Job ID" in line:
                parts = line.split()
                for part in parts:
                    if part.isdigit():
                        job_id = part
                        break

        return {"success": True, "experiment": exp_name, "job_id": job_id, "stdout": result.stdout}

    def create_experiment_job_script(
        self,
        experiment: Dict,
        param_file: str,
        output_dir: str
    ) -> str:
        """Create a wrapper script that calls submit_experiment.sh."""
        exp_name = experiment.get("name", "exp").replace(" ", "_")
        base_case = experiment.get("base_case", "")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        script_path = output_dir / f"run_{exp_name}.sh"

        submit_script = TOOLS_DIR / "submit_experiment.sh"

        script_content = f"""#!/bin/bash
# A2MC Experiment Wrapper: {exp_name}
# Generated: {datetime.now().isoformat()}

set -e

echo "A2MC Experiment: {exp_name}"

bash {submit_script} \\
    --name {exp_name} \\
    --param-file {param_file} \\
    --output-root {self.config.output_root} \\
    {"--base-case " + base_case if base_case else ""} \\
    --submit

echo "Experiment {exp_name} submitted"
"""

        with open(script_path, "w") as f:
            f.write(script_content)

        script_path.chmod(0o755)
        self.logger.info(f"Created experiment wrapper script: {script_path}")
        return str(script_path)


# ============================================================================
# PARAMETER MANAGER
# ============================================================================

class ParameterManager:
    """
    Manages FATES parameter file modifications.

    Wraps the existing modify_fates_parameters.py script for batch operations.
    """

    def __init__(self, config: HPCConfig = None):
        self.config = config or HPCConfig()
        self.logger = logging.getLogger(f"{__name__}.ParameterManager")
        self._modifier = None

    def _get_modifier(self):
        """Lazy-load the parameter modification module."""
        if self._modifier is not None:
            return self._modifier

        paths_to_try = [
            TOOLS_DIR / "modify_fates_parameters.py",
        ]

        for script_path in paths_to_try:
            if script_path.exists():
                try:
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("modify_fates_parameters", str(script_path))
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    self._modifier = module
                    self.logger.info(f"Loaded parameter tool from: {script_path}")
                    return self._modifier
                except Exception as e:
                    self.logger.warning(f"Failed to load from {script_path}: {e}")

        raise ImportError("Cannot find modify_fates_parameters.py in tools/")

    def create_modified_file(
        self,
        base_file: str,
        output_file: str,
        modifications: List[Dict],
        verbose: bool = True
    ) -> str:
        """
        Create a modified FATES parameter file.

        Args:
            base_file: Path to base parameter file
            output_file: Path for modified output file
            modifications: List of modifications, each dict containing:
                - param: Parameter name
                - pft: PFT index (1-12, or 0 for global)
                - value: New absolute value (optional)
                - percent: Percentage change (optional)
                - organ: Organ index for 2D params (optional)
            verbose: Print progress

        Returns:
            Path to created file
        """
        modifier = self._get_modifier()

        if verbose:
            self.logger.info(f"Creating modified parameter file:")
            self.logger.info(f"  Base: {Path(base_file).name}")
            self.logger.info(f"  Output: {Path(output_file).name}")
            self.logger.info(f"  Modifications: {len(modifications)}")

        modifier.create_modified_parameter_file(
            input_file=base_file,
            output_file=output_file,
            modifications=modifications,
            verbose=verbose
        )
        return output_file

    def create_experiment_files(
        self,
        experiment: Dict,
        base_case_param_file: str,
        output_dir: str
    ) -> str:
        """
        Create parameter file for an experiment.

        Args:
            experiment: Experiment specification with modifications
            base_case_param_file: Path to base parameter file
            output_dir: Directory for output files

        Returns:
            Path to created parameter file
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exp_name = experiment.get("name", "exp").replace(" ", "_")
        output_file = output_dir / f"fates_params_{exp_name}.nc"

        modifications = []
        for mod in experiment.get("modifications", []):
            param_name = mod.get("parameter", "")
            new_value = mod.get("new_value")

            pft = 0
            parts = param_name.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                pft = int(parts[1])
                param_name = "_".join(parts[0].split("_")[:-1]) if "_" in parts[0] else parts[0]

            modifications.append({
                "param": param_name,
                "pft": pft,
                "value": new_value
            })

        return self.create_modified_file(
            base_file=base_case_param_file,
            output_file=str(output_file),
            modifications=modifications
        )
