#!/usr/bin/env python3
"""
A2MC Integration Module for ELM-FATES

This module provides HPC-native interfaces for:
1. Parameter Management - Creating modified FATES parameter files
2. HPC Execution - Submitting and monitoring jobs via sbatch/squeue
3. Data Pipeline - Extracting and processing simulation results

IMPORTANT: This module is designed to run DIRECTLY on HPC (NERSC Perlmutter).
No SSH tunneling - all commands execute locally on the HPC system.

Integration with Existing Tools:
- modify_fates_parameters.py - Parameter file modification
- extract_monthly_variables_FATES.py - Data extraction from NetCDF
- submit4890jobs.sh - Job submission template

Author: Jing Tao
Created: January 2026
"""

import os
import sys
import json
import time
import shutil
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Get the path to the tools directory (bundled with A2MC)
TOOLS_DIR = Path(__file__).parent / "tools"


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
    extract_data_script: str = ""

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
        except ImportError:
            pass
        import os
        self.project = self.project or os.environ.get('A2MC_PROJECT', 'm2467')
        self.scratch_root = self.scratch_root or os.environ.get('A2MC_SCRATCH_ROOT', '')
        self.output_root = self.output_root or os.environ.get('A2MC_OUTPUT_ROOT', '')
        self.scripts_dir = self.scripts_dir or os.environ.get('A2MC_SCRIPTS_DIR', '')
        self.case_root = self.case_root or os.environ.get('A2MC_ENSEMBLE_OUTPUT', '')
        self.param_dir = self.param_dir or os.environ.get('A2MC_PARAM_DIR', '')
        self.extracted_data = self.extracted_data or os.environ.get('A2MC_EXTRACTED_DATA', '')
        user = os.environ.get('USER', 'jingtao')
        self.modify_params_script = self.modify_params_script or f'/global/homes/j/{user}/Program/PythonScripts/modify_fates_parameters.py'
        self.extract_data_script = self.extract_data_script or f'/global/homes/j/{user}/Program/PythonScripts/extract_monthly_variables_FATES.py'


# ============================================================================
# PARAMETER MANAGER
# ============================================================================

class ParameterManager:
    """
    Manages FATES parameter file modifications.

    Wraps the existing modify_fates_parameters.py script for batch operations.
    Handles both PFT-specific and global parameters.
    """

    def __init__(self, config: HPCConfig = None):
        self.config = config or HPCConfig()
        self.logger = logging.getLogger(f"{__name__}.ParameterManager")
        self._modifier = None

    def _get_modifier(self):
        """Lazy-load the parameter modification module."""
        if self._modifier is not None:
            return self._modifier

        # Priority order: bundled tools first, then HPC path
        paths_to_try = [
            TOOLS_DIR / "modify_fates_parameters.py",  # Bundled tool (highest priority)
            Path(self.config.modify_params_script),     # HPC fallback
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

        raise ImportError("Cannot find modify_fates_parameters.py in tools/ or fallback paths")

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

        # Use the existing function
        results = modifier.create_modified_parameter_file(
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

        # Generate output filename
        exp_name = experiment.get("name", "exp").replace(" ", "_")
        output_file = output_dir / f"fates_params_{exp_name}.nc"

        # Convert experiment modifications to the format expected by modify_fates_parameters
        modifications = []
        for mod in experiment.get("modifications", []):
            param_name = mod.get("parameter", "")
            new_value = mod.get("new_value")

            # Parse PFT from parameter name (e.g., fates_turnover_fnrt_10 → PFT 10)
            pft = 0  # Default: global
            parts = param_name.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                pft = int(parts[1])
                # Reconstruct the actual FATES parameter name
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
            self.logger.warning("Run this on NERSC Perlmutter for actual execution")

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
            # Simulate submission
            fake_id = f"SIM_{int(time.time())}"
            self.logger.info(f"[SIMULATED] Would submit: {job_script} -> {fake_id}")
            return fake_id

        cmd = ["sbatch"]

        # Add dependencies if specified
        if dependencies:
            dep_str = ":".join(dependencies)
            cmd.extend(["--dependency", f"afterok:{dep_str}"])

        cmd.extend(["--job-name", job_name])
        cmd.append(job_script)

        self.logger.info(f"Submitting job: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"sbatch failed: {result.stderr}")

        # Parse job ID from output (format: "Submitted batch job 12345678")
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
            # Job not in queue - check sacct for completed jobs
            return self._check_completed_job(job_id)

        # Parse squeue output
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

        # Parse first line (main job, not steps)
        lines = result.stdout.strip().split("\n")
        for line in lines:
            parts = line.split("|")
            if len(parts) >= 4 and "." not in parts[0]:  # Main job, not step
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

        # Handle timeout
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
            base_case: Base case name to use for restart file (e.g., "En2678")
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

        # Build command
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
        self.logger.info(f"Command: {' '.join(cmd)}")

        if not self._is_hpc:
            # Simulate on non-HPC
            self.logger.info(f"[SIMULATED] Would run: {' '.join(cmd)}")
            return {
                "success": True,
                "simulated": True,
                "experiment": exp_name,
                "command": cmd
            }

        # Execute submission script
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

        if result.returncode != 0:
            self.logger.error(f"Submission failed: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr,
                "stdout": result.stdout
            }

        # Parse job ID from output
        job_id = None
        for line in result.stdout.split("\n"):
            if "Job ID" in line:
                parts = line.split()
                for part in parts:
                    if part.isdigit():
                        job_id = part
                        break

        return {
            "success": True,
            "experiment": exp_name,
            "job_id": job_id,
            "stdout": result.stdout
        }

    def create_experiment_job_script(
        self,
        experiment: Dict,
        param_file: str,
        output_dir: str
    ) -> str:
        """
        Create a wrapper script that calls submit_experiment.sh.

        Args:
            experiment: Experiment specification
            param_file: Path to parameter file
            output_dir: Output directory for results

        Returns:
            Path to created wrapper script
        """
        exp_name = experiment.get("name", "exp").replace(" ", "_")
        base_case = experiment.get("base_case", "")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        script_path = output_dir / f"run_{exp_name}.sh"

        # Use bundled submit_experiment.sh
        submit_script = TOOLS_DIR / "submit_experiment.sh"

        script_content = f"""#!/bin/bash
# A2MC Experiment Wrapper: {exp_name}
# Generated: {datetime.now().isoformat()}
# Uses bundled submit_experiment.sh for case creation and submission

set -e

echo "========================================"
echo "A2MC Experiment: {exp_name}"
echo "========================================"

# Call the bundled experiment submission script
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

    def submit_ensemble(
        self,
        sampling_design: Dict,
        param_dir: str,
        batch_size: int = 10,
        start_case: int = 1,
        end_case: int = None
    ) -> Dict:
        """
        Submit ensemble using the bundled submit_ensemble.sh script.

        Args:
            sampling_design: Sampling design specification with 'n_simulations'
            param_dir: Directory containing parameter files
            batch_size: Number of cases to submit in parallel
            start_case: Starting case number (default: 1)
            end_case: Ending case number (default: from sampling_design)

        Returns:
            Dict with submission results
        """
        n_sims = sampling_design.get("n_simulations", 0)
        if end_case is None:
            end_case = n_sims

        submit_script = TOOLS_DIR / "submit_ensemble.sh"

        if not submit_script.exists():
            self.logger.error(f"Submit script not found: {submit_script}")
            return {"success": False, "error": "submit_ensemble.sh not found"}

        self.logger.info(f"Submitting ensemble:")
        self.logger.info(f"  Cases: {start_case} to {end_case}")
        self.logger.info(f"  Total: {end_case - start_case + 1} simulations")
        self.logger.info(f"  Batch size: {batch_size}")
        self.logger.info(f"  Parameter directory: {param_dir}")

        # Build command
        cmd = [
            "bash", str(submit_script),
            "--start", str(start_case),
            "--end", str(end_case),
            "--param-dir", param_dir,
            "--output-root", self.config.output_root,
            "--batch-size", str(batch_size),
            "--submit"
        ]

        self.logger.info(f"Command: {' '.join(cmd)}")

        if not self._is_hpc:
            # Simulate on non-HPC
            self.logger.info(f"[SIMULATED] Would run: {' '.join(cmd)}")
            return {
                "success": True,
                "simulated": True,
                "n_cases": end_case - start_case + 1,
                "command": cmd
            }

        # Execute submission script
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=86400)

        if result.returncode != 0:
            self.logger.error(f"Ensemble submission failed: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr,
                "stdout": result.stdout
            }

        return {
            "success": True,
            "n_cases": end_case - start_case + 1,
            "stdout": result.stdout
        }

    def submit_single_case(
        self,
        case_num: int,
        param_file: str,
        phases: str = "ADSP RGSP TRANS",
        case_suffix: str = ""
    ) -> Dict:
        """
        Submit a single ensemble case using the bundled create_case.sh script.

        Args:
            case_num: Case number
            param_file: Path to FATES parameter file
            phases: Which phases to run
            case_suffix: Optional suffix for case name

        Returns:
            Dict with submission results
        """
        create_script = TOOLS_DIR / "create_case.sh"

        if not create_script.exists():
            self.logger.error(f"Create script not found: {create_script}")
            return {"success": False, "error": "create_case.sh not found"}

        # Build command
        cmd = [
            "bash", str(create_script),
            "--case-num", str(case_num),
            "--param-file", param_file,
            "--output-root", self.config.output_root,
            "--phases", phases,
            "--submit"
        ]

        if case_suffix:
            cmd.extend(["--case-suffix", case_suffix])

        self.logger.info(f"Submitting case {case_num}")
        self.logger.info(f"Command: {' '.join(cmd)}")

        if not self._is_hpc:
            # Simulate on non-HPC
            self.logger.info(f"[SIMULATED] Would run: {' '.join(cmd)}")
            return {
                "success": True,
                "simulated": True,
                "case_num": case_num,
                "command": cmd
            }

        # Execute creation script
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

        if result.returncode != 0:
            self.logger.error(f"Case submission failed: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr,
                "stdout": result.stdout
            }

        return {
            "success": True,
            "case_num": case_num,
            "stdout": result.stdout
        }


# ============================================================================
# DATA PIPELINE
# ============================================================================

class DataPipeline:
    """
    Data extraction and processing pipeline.

    Wraps the existing extract_monthly_variables_FATES.py script.
    Handles NetCDF extraction, CSV conversion, and validation against targets.
    """

    def __init__(self, config: HPCConfig = None):
        self.config = config or HPCConfig()
        self.logger = logging.getLogger(f"{__name__}.DataPipeline")

        # Validation targets (g C/m2 with ±20% uncertainty)
        self.targets = {
            "leaf_pft7": {"mean": 24.6, "uncertainty": 0.20},
            "leaf_pft9": {"mean": 124.7, "uncertainty": 0.20},
            "leaf_pft10": {"mean": 82.7, "uncertainty": 0.20},
            "froot_pft7": {"mean": 174.2, "uncertainty": 0.20},
            "froot_pft9": {"mean": 187.3, "uncertainty": 0.20},
            "froot_pft10": {"mean": 382.1, "uncertainty": 0.20},
        }

    def extract_case_data(
        self,
        case_id: str,
        start_year: int = 2000,
        end_year: int = 2019
    ) -> Dict:
        """
        Extract monthly data for a single case.

        Args:
            case_id: Case identifier (e.g., "2678" or "2678_exp1")
            start_year: Start year for extraction
            end_year: End year for extraction

        Returns:
            Dict with extraction results
        """
        # Priority order: bundled tool first, then HPC fallback
        extract_script = None
        paths_to_try = [
            TOOLS_DIR / "extract_monthly_variables_FATES.py",  # Bundled
            Path(self.config.extract_data_script),              # HPC fallback
        ]

        for path in paths_to_try:
            if path.exists():
                extract_script = str(path)
                break

        if extract_script is None:
            self.logger.warning("Extract script not found in tools/ or fallback paths")
            return {"success": False, "error": "Script not found"}

        self.logger.info(f"Extracting data for case {case_id}")

        cmd = ["python", extract_script, "--cases", str(case_id)]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

        if result.returncode != 0:
            self.logger.error(f"Extraction failed: {result.stderr}")
            return {"success": False, "error": result.stderr}

        return {
            "success": True,
            "case_id": case_id,
            "output": result.stdout
        }

    def extract_batch(
        self,
        case_ids: List[str],
        parallel: int = 4
    ) -> List[Dict]:
        """
        Extract data for multiple cases.

        Args:
            case_ids: List of case identifiers
            parallel: Number of parallel extractions

        Returns:
            List of extraction results
        """
        results = []

        # For small batches, run directly
        for case_id in case_ids:
            result = self.extract_case_data(case_id)
            results.append(result)

        return results

    def load_extracted_data(
        self,
        case_id: str,
        data_type: str = "csv"
    ) -> Any:
        """
        Load previously extracted data.

        Args:
            case_id: Case identifier
            data_type: "netcdf" or "csv"

        Returns:
            pandas.DataFrame (csv) or xarray.Dataset (netcdf)
        """
        # Search for extracted files in configured paths
        output_dirs = []
        if self.config.extracted_data:
            output_dirs.append(Path(self.config.extracted_data))
        if self.config.case_root:
            output_dirs.append(Path(self.config.case_root) / "extracted_monthly_data")

        for output_dir in output_dirs:
            if not output_dir.exists():
                continue

            if data_type == "netcdf":
                pattern = f"*{case_id}*_all_variables_monthly_*.nc"
                files = list(output_dir.glob(pattern))
                if files:
                    try:
                        import xarray as xr
                        return xr.open_dataset(files[0])
                    except ImportError:
                        self.logger.warning("xarray not available")

            elif data_type == "csv":
                pattern = f"*{case_id}*_site_pft_monthly_*.csv"
                files = list(output_dir.glob(pattern))
                if files:
                    try:
                        import pandas as pd
                        return pd.read_csv(files[0])
                    except ImportError:
                        self.logger.warning("pandas not available")

        self.logger.warning(f"No data found for case {case_id}")
        return None

    def evaluate_against_targets(
        self,
        case_data: Any,
        analysis_start_year: int = 2010,
        analysis_end_year: int = 2019
    ) -> Dict:
        """
        Evaluate case data against validation targets.

        Args:
            case_data: Extracted case data (pandas DataFrame or xarray Dataset)
            analysis_start_year: Start year for analysis period
            analysis_end_year: End year for analysis period

        Returns:
            Dict with evaluation metrics
        """
        results = {
            "targets_met": 0,
            "total_targets": len(self.targets),
            "metrics": {}
        }

        # Convert to DataFrame if needed
        if hasattr(case_data, 'to_dataframe'):
            df = case_data.to_dataframe()
        else:
            df = case_data

        # Filter to analysis period
        if 'year' in df.columns:
            df = df[(df['year'] >= analysis_start_year) & (df['year'] <= analysis_end_year)]

        # Column mapping for biomass variables
        biomass_cols = {
            "leaf_pft7": "FATES_LEAFC_PF_PFT7",
            "leaf_pft9": "FATES_LEAFC_PF_PFT9",
            "leaf_pft10": "FATES_LEAFC_PF_PFT10",
            "froot_pft7": "FATES_FROOTC_PF_PFT7",
            "froot_pft9": "FATES_FROOTC_PF_PFT9",
            "froot_pft10": "FATES_FROOTC_PF_PFT10",
        }

        for target_name, col_name in biomass_cols.items():
            target_info = self.targets.get(target_name, {})
            target_value = target_info.get("mean", 0)
            uncertainty = target_info.get("uncertainty", 0.20)

            if col_name in df.columns:
                # Average over analysis period (convert kg to g)
                simulated = df[col_name].mean() * 1000

                # Calculate relative error
                if target_value > 0:
                    rel_error = abs(simulated - target_value) / target_value
                    within_target = rel_error <= uncertainty

                    results["metrics"][target_name] = {
                        "simulated": simulated,
                        "target": target_value,
                        "relative_error": rel_error,
                        "within_target": within_target
                    }

                    if within_target:
                        results["targets_met"] += 1

        return results


# ============================================================================
# EXPERIMENT RUNNER
# ============================================================================

class ExperimentRunner:
    """
    High-level experiment execution coordinator.

    Combines ParameterManager, HPCExecutor, and DataPipeline to run
    complete A2MC experiments from hypothesis to evaluation.
    """

    def __init__(self, config: HPCConfig = None):
        self.config = config or HPCConfig()
        self.params = ParameterManager(config)
        self.hpc = HPCExecutor(config)
        self.data = DataPipeline(config)
        self.logger = logging.getLogger(f"{__name__}.ExperimentRunner")

    def run_experiment(
        self,
        experiment: Dict,
        base_param_file: str,
        output_dir: str,
        wait: bool = True
    ) -> Dict:
        """
        Run a complete experiment.

        Args:
            experiment: Experiment specification
            base_param_file: Path to base parameter file
            output_dir: Output directory
            wait: Whether to wait for completion

        Returns:
            Dict with experiment results
        """
        exp_name = experiment.get("name", "exp")
        self.logger.info(f"Running experiment: {exp_name}")

        result = {
            "experiment": experiment,
            "status": "started",
            "steps": {}
        }

        try:
            # 1. Create modified parameter file
            self.logger.info("Step 1: Creating modified parameter file...")
            param_file = self.params.create_experiment_files(
                experiment=experiment,
                base_case_param_file=base_param_file,
                output_dir=output_dir
            )
            result["param_file"] = param_file
            result["steps"]["create_params"] = {"status": "success"}

            # 2. Create job script
            self.logger.info("Step 2: Creating job script...")
            job_script = self.hpc.create_experiment_job_script(
                experiment=experiment,
                param_file=param_file,
                output_dir=output_dir
            )
            result["job_script"] = job_script
            result["steps"]["create_job"] = {"status": "success"}

            # 3. Submit job
            self.logger.info("Step 3: Submitting job...")
            job_id = self.hpc.submit_job(
                job_script=job_script,
                job_name=exp_name
            )
            result["job_id"] = job_id
            result["steps"]["submit"] = {"status": "success", "job_id": job_id}

            # 4. Wait for completion if requested
            if wait:
                self.logger.info("Step 4: Waiting for job completion...")
                job_status = self.hpc.wait_for_jobs([job_id])
                result["job_status"] = job_status.get(job_id, {})
                result["steps"]["wait"] = {"status": "success"}

                # 5. Extract and evaluate results
                if result["job_status"].get("status") == "COMPLETED":
                    self.logger.info("Step 5: Extracting results...")
                    case_id = f"{experiment.get('base_case', '')}_{exp_name}"
                    self.data.extract_case_data(case_id)

                    case_data = self.data.load_extracted_data(case_id)
                    if case_data is not None:
                        evaluation = self.data.evaluate_against_targets(case_data)
                        result["evaluation"] = evaluation
                        result["steps"]["evaluate"] = {"status": "success"}

            result["status"] = "completed"

        except Exception as e:
            self.logger.error(f"Experiment failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    def run_experiment_sequence(
        self,
        experiments: List[Dict],
        base_param_file: str,
        output_dir: str
    ) -> List[Dict]:
        """
        Run a sequence of experiments.

        Args:
            experiments: List of experiment specifications
            base_param_file: Path to base parameter file
            output_dir: Output directory

        Returns:
            List of experiment results
        """
        results = []

        for i, exp in enumerate(experiments):
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"Experiment {i+1}/{len(experiments)}: {exp.get('name')}")
            self.logger.info(f"{'='*50}")

            result = self.run_experiment(
                experiment=exp,
                base_param_file=base_param_file,
                output_dir=output_dir,
                wait=True
            )
            results.append(result)

            # Log summary
            status = result.get("status", "UNKNOWN")
            targets_met = result.get("evaluation", {}).get("targets_met", 0)
            self.logger.info(f"Status: {status}, Targets met: {targets_met}/6")

        return results


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    """Command-line interface for integration module."""
    import argparse

    parser = argparse.ArgumentParser(
        description="A2MC Integration Module for ELM-FATES",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Modify parameter file
  python integration.py modify-params --input base.nc --output mod.nc --param fates_turnover_fnrt --pft 10 --value 5.0

  # Submit job to HPC
  python integration.py submit --script run_exp.sh --name my_experiment

  # Check job status
  python integration.py status --job-id 12345678

  # Extract case data
  python integration.py extract --cases 2678 2679 2680
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Parameter modification command
    param_parser = subparsers.add_parser("modify-params", help="Modify parameter file")
    param_parser.add_argument("--input", required=True, help="Input parameter file")
    param_parser.add_argument("--output", required=True, help="Output parameter file")
    param_parser.add_argument("--param", required=True, help="Parameter name")
    param_parser.add_argument("--pft", type=int, required=True, help="PFT index (1-12, or 0 for global)")
    param_parser.add_argument("--value", type=float, help="New absolute value")
    param_parser.add_argument("--percent", type=float, help="Percent change")

    # Job submission command
    submit_parser = subparsers.add_parser("submit", help="Submit job to HPC")
    submit_parser.add_argument("--script", required=True, help="Job script path")
    submit_parser.add_argument("--name", default="a2mc_job", help="Job name")

    # Job status command
    status_parser = subparsers.add_parser("status", help="Check job status")
    status_parser.add_argument("--job-id", required=True, help="SLURM job ID")

    # Data extraction command
    extract_parser = subparsers.add_parser("extract", help="Extract case data")
    extract_parser.add_argument("--cases", nargs="+", required=True, help="Case IDs")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run integration tests")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    config = HPCConfig()

    if args.command == "modify-params":
        manager = ParameterManager(config)
        modifications = [{"param": args.param, "pft": args.pft}]
        if args.value is not None:
            modifications[0]["value"] = args.value
        elif args.percent is not None:
            modifications[0]["percent"] = args.percent
        manager.create_modified_file(args.input, args.output, modifications)

    elif args.command == "submit":
        executor = HPCExecutor(config)
        job_id = executor.submit_job(args.script, args.name)
        print(f"Submitted job: {job_id}")

    elif args.command == "status":
        executor = HPCExecutor(config)
        status = executor.check_job_status(args.job_id)
        print(json.dumps(status, indent=2))

    elif args.command == "extract":
        pipeline = DataPipeline(config)
        results = pipeline.extract_batch(args.cases)
        print(json.dumps(results, indent=2, default=str))

    elif args.command == "test":
        # Run integration tests
        print("=" * 60)
        print("A2MC Integration Module Tests")
        print("=" * 60)

        print("\n1. Testing ParameterManager...")
        try:
            param_mgr = ParameterManager(config)
            print("   ✓ ParameterManager initialized")
        except Exception as e:
            print(f"   ✗ ParameterManager failed: {e}")

        print("\n2. Testing HPCExecutor...")
        hpc_exec = HPCExecutor(config)
        print(f"   On HPC: {hpc_exec._is_hpc}")

        print("\n3. Testing DataPipeline...")
        data_pipe = DataPipeline(config)
        print(f"   Validation targets: {len(data_pipe.targets)}")

        # Test evaluation with dummy data
        print("\n4. Testing evaluation with dummy data...")
        try:
            import pandas as pd
            dummy_df = pd.DataFrame({
                'year': [2015] * 12,
                'FATES_LEAFC_PF_PFT7': [0.025] * 12,  # kg -> ~25 g
                'FATES_LEAFC_PF_PFT9': [0.120] * 12,  # kg -> ~120 g
                'FATES_LEAFC_PF_PFT10': [0.080] * 12,  # kg -> ~80 g
                'FATES_FROOTC_PF_PFT7': [0.170] * 12,
                'FATES_FROOTC_PF_PFT9': [0.180] * 12,
                'FATES_FROOTC_PF_PFT10': [0.300] * 12,  # Underestimate
            })
            evaluation = data_pipe.evaluate_against_targets(dummy_df)
            print(f"   Targets met: {evaluation['targets_met']}/{evaluation['total_targets']}")
        except Exception as e:
            print(f"   Evaluation test skipped: {e}")

        print("\n" + "=" * 60)
        print("Integration module ready for use")
        print("=" * 60)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
