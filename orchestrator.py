#!/usr/bin/env python3
"""
Agentic Adaptive Multi-target Calibration (A2MC) Orchestrator for ELM-FATES

This is the main controller that orchestrates the autonomous calibration workflow.
It maintains state, coordinates modules, and decides when to advance or iterate.

Key Features:
- 7-Phase workflow: DESIGN → EXPLORATION → SCREENING → DIAGNOSIS → HYPOTHESIS → TESTING → REFINEMENT
- HPC-native execution (direct sbatch/squeue, no SSH)
- Claude API integration for autonomous reasoning
- Adaptive Memory System for learning from experiments
- Multi-objective optimization (configurable targets)

Configuration is read from:
- a2mc_config.sh (environment variables)
- use_cases/{site}/config/{site}_config.sh (site-specific)
- tools/config.py (Python interface)

Usage:
    # First, source the config files
    source a2mc_config.sh
    source use_cases/Kougarok/config/kougarok_config.sh

    # Run workflow (output-dir and state-file auto-detected from config)
    python orchestrator.py --run

    # Resume from checkpoint (state-file auto-detected)
    python orchestrator.py --resume

    # Start from specific phase
    python orchestrator.py --run --start-phase exploration

Author: Jing Tao
Created: January 2026
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import workflow status tracker
try:
    from tools.workflow_status import WorkflowStatus
except ImportError:
    WorkflowStatus = None

# Import phase logger
try:
    from tools.phase_logger import PhaseLogger
except ImportError:
    PhaseLogger = None

# Import Phase 3 diagnosis tools
try:
    from phases.phase3_diagnosis import (
        run_diagnosis_for_orchestrator,
        DiagnosisConfig,
        DiagnosisResult
    )
    HAS_DIAGNOSIS_TOOLS = True
except ImportError:
    HAS_DIAGNOSIS_TOOLS = False
    DiagnosisConfig = None
    DiagnosisResult = None


class Phase(Enum):
    """Workflow phases following A2MC methodology."""
    DESIGN = "design"           # Phase 0: Sensitivity sampling design
    EXPLORATION = "exploration"  # Phase 1: Run sensitivity analysis ensemble
    SCREENING = "screening"      # Phase 2: Screen cases against targets
    DIAGNOSIS = "diagnosis"      # Phase 3: Diagnose why targets fail
    HYPOTHESIS = "hypothesis"    # Phase 4: Generate testable hypotheses
    TESTING = "testing"          # Phase 5: Execute experiments on HPC
    REFINEMENT = "refinement"    # Phase 6: Evaluate and iterate/converge
    CONVERGED = "converged"      # Final: Calibration complete


@dataclass
class ValidationTargets:
    """
    Multi-objective validation targets.

    Targets are loaded from use_cases/{site}/validation/targets.txt
    or specified in the site config. This class provides defaults
    that can be overridden.
    """
    # Biomass targets (g C/m2) with uncertainty - loaded from config
    biomass: Dict = field(default_factory=dict)
    # Ecosystem function targets - loaded from config
    ecosystem: Dict = field(default_factory=dict)

    @classmethod
    def from_config(cls, config_path: str = None) -> 'ValidationTargets':
        """Load targets from configuration file."""
        # Try to load from environment or config
        try:
            from tools.config import config
            validation_file = config.VALIDATION_FILE
            if validation_file and Path(validation_file).exists():
                # Parse validation file (implement based on file format)
                pass
        except ImportError:
            pass
        return cls()


@dataclass
class SamplingDesign:
    """
    Sensitivity analysis sampling design parameters.

    Supports multiple sampling schemes:
    - morris: trajectories × (params + 1) simulations
    - lhs: n_samples simulations
    - sobol: samples × (2 × params + 2) simulations
    - custom: user-specified ensemble
    """
    scheme: str = "morris"          # Sampling scheme (from A2MC_SAMPLING_SCHEME)
    n_parameters: int = 0           # Number of parameters (from A2MC_N_PARAMS)
    n_trajectories: int = 30        # For morris scheme (from A2MC_N_TRAJECTORIES)
    n_samples: int = 1000           # For lhs/sobol schemes (from A2MC_N_SAMPLES)
    n_levels: int = 8               # Grid levels for parameter space
    n_simulations: int = 0          # Total simulations (auto-calculated)
    parameter_file: str = ""        # Path to parameter bounds file
    sampling_file: str = ""         # Ensemble matrix file
    complete: bool = False

    def __post_init__(self):
        """Calculate n_simulations based on scheme."""
        if self.n_simulations == 0:
            if self.scheme == "morris":
                self.n_simulations = self.n_trajectories * (self.n_parameters + 1)
            elif self.scheme == "lhs":
                self.n_simulations = self.n_samples
            elif self.scheme == "sobol":
                self.n_simulations = self.n_samples * (2 * self.n_parameters + 2)
            # custom: leave as 0 or set from config


@dataclass
class WorkflowState:
    """Persistent state of the A2MC calibration workflow."""
    # Core state
    calibration_round: int = 1     # Outermost loop: Phase 0→7 cycle (e.g., round 1=138 params, round 2=162 params)
    iteration: int = 1             # Display counter: cycles within a round (resets on new round)
    current_phase: str = Phase.DESIGN.value
    converged: bool = False

    # Two-level iteration tracking (within a calibration round)
    skip_testing_count: int = 0    # Inner loop: Phase 3↔4 cycles (resets after HPC)
    experiment_count: int = 0       # Outer loop: Full experiment cycles (3→4→5→6)

    started_at: str = ""
    updated_at: str = ""

    # Phase 0: Design (generic sampling design)
    sampling_design: Dict = field(default_factory=dict)

    # Phase 1: Exploration (sensitivity analysis results)
    exploration_data: Dict = field(default_factory=dict)

    # Phase 2: Screening (best cases, target performance)
    screening_data: Dict = field(default_factory=dict)

    # Phase 3-4: Diagnosis and Hypotheses
    diagnoses: List = field(default_factory=list)
    hypotheses: List = field(default_factory=list)

    # Phase 5-6: Testing and Refinement
    experiments: List = field(default_factory=list)
    best_experiment: Dict = field(default_factory=dict)

    # Skip Testing: Results from testing hypotheses with existing data
    hypothesis_tests: List = field(default_factory=list)

    # Cumulative insights: Key findings accumulated across skip-testing cycles
    # Each entry: {cycle, hypothesis, supported, confidence, key_insights, evidence}
    # Passed to next diagnosis so AI can build on previous findings
    cumulative_insights: List = field(default_factory=list)

    # History tracking
    phase_history: List = field(default_factory=list)

    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.now().isoformat()

    def save(self, path: str):
        """Save state to JSON file."""
        self.updated_at = datetime.now().isoformat()
        with open(path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
        logger.info(f"State saved to {path}")

    @classmethod
    def load(cls, path: str) -> 'WorkflowState':
        """Load state from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(**data)

    def record_phase_transition(self, from_phase: str, to_phase: str, reason: str):
        """Record phase transition in history."""
        self.phase_history.append({
            "timestamp": datetime.now().isoformat(),
            "iteration": self.iteration,
            "from": from_phase,
            "to": to_phase,
            "reason": reason
        })


@dataclass
class Config:
    """
    Configuration for the A2MC orchestrator.

    Values are loaded from environment variables (set by sourcing a2mc_config.sh
    and the site-specific config) with sensible defaults.
    """
    # Paths
    state_file: str = ""   # Auto-detected from A2MC_USE_CASE_DIR config
    output_dir: str = ""   # Auto-detected from A2MC_USE_CASE_DIR config
    param_bounds_file: str = ""      # Parameter bounds definition
    base_param_file: str = ""        # Base FATES parameter file
    memory_dir: str = ""             # Adaptive memory data directory (default: output_dir/memory/data)

    # HPC settings (from A2MC_* environment variables)
    hpc_project: str = ""
    hpc_scratch: str = ""
    hpc_output_root: str = ""
    hpc_queue: str = "shared"
    hpc_time_limit: str = "12:00:00"
    hpc_nodes: int = 1

    # Sampling design settings (from A2MC_* environment variables)
    sampling_scheme: str = ""        # morris, lhs, sobol, custom
    n_trajectories: int = 0          # For morris
    n_samples: int = 0               # For lhs/sobol
    n_levels: int = 8
    n_parameters: int = 0
    total_ensemble: int = 0          # Total simulations (auto-calculated if 0)

    # Claude API settings (from A2MC_AI_MODEL or default)
    claude_model: str = ""
    max_tokens: int = 4096
    use_reasoning: bool = True       # Enable Claude API reasoning

    # Memory settings
    use_memory: bool = True          # Enable adaptive memory system
    auto_learn: bool = True          # Auto-extract lessons from experiments

    # Workflow settings
    max_iterations: int = 10
    poll_interval: int = 300         # seconds
    human_review: bool = True        # Pause for human review at key points

    # Two-level iteration limits
    max_skip_testing: int = 10       # Max Phase 3↔4 skip testing cycles before forcing HPC
    max_experiments: int = 10        # Max Phase 3→4→5→6 full experiment cycles
    hypothesis_confidence_threshold: float = 0.95  # Exit skip testing when confidence >= this
    auto_skip_testing: bool = True   # Auto-continue Phase 3↔4 cycles (no checkpoint during skip testing)

    # Validation targets (loaded from site config)
    targets: ValidationTargets = field(default_factory=ValidationTargets)

    def __post_init__(self):
        """Load values from environment/config if not explicitly set."""
        try:
            from tools.config import config as a2mc_config
            # HPC settings
            if not self.hpc_project:
                self.hpc_project = a2mc_config.PROJECT
            if not self.hpc_output_root:
                self.hpc_output_root = a2mc_config.OUTPUT_ROOT
            if not self.hpc_scratch:
                self.hpc_scratch = a2mc_config.SCRIPTS_DIR
            # Sampling settings
            if not self.sampling_scheme:
                self.sampling_scheme = a2mc_config.SAMPLING_SCHEME
            if not self.n_parameters:
                self.n_parameters = a2mc_config.N_PARAMS
            if not self.n_trajectories:
                self.n_trajectories = a2mc_config.N_TRAJECTORIES
            if not self.total_ensemble:
                self.total_ensemble = a2mc_config.TOTAL_ENSEMBLE
            # Parameter files
            if not self.base_param_file:
                self.base_param_file = a2mc_config.BASE_PARAM_FILE
            if not self.param_bounds_file:
                self.param_bounds_file = a2mc_config.PARAM_LIST_FILE
            # AI model (default if not set)
            if not self.claude_model:
                self.claude_model = os.environ.get('A2MC_AI_MODEL', 'claude-sonnet-4-20250514')
        except ImportError:
            # tools.config not available, use defaults
            if not self.sampling_scheme:
                self.sampling_scheme = os.environ.get('A2MC_SAMPLING_SCHEME', 'morris')
            if not self.n_parameters:
                self.n_parameters = int(os.environ.get('A2MC_N_PARAMS', '100'))
            if not self.n_trajectories:
                self.n_trajectories = int(os.environ.get('A2MC_N_TRAJECTORIES', '30'))
            if not self.claude_model:
                self.claude_model = os.environ.get('A2MC_AI_MODEL', 'claude-sonnet-4-20250514')


class CalibrationOrchestrator:
    """
    Main controller for the Agentic Adaptive Multi-target Calibration (A2MC) workflow.

    This orchestrator implements the 7-phase A2MC methodology:
    1. DESIGN: Create sensitivity sampling design (configurable scheme)
    2. EXPLORATION: Run sensitivity analysis ensemble on HPC
    3. SCREENING: Screen cases against multi-objective targets
    4. DIAGNOSIS: Diagnose why calibration targets fail
    5. HYPOTHESIS: Generate mechanistic hypotheses
    6. TESTING: Execute targeted experiments
    7. REFINEMENT: Evaluate results, iterate or converge

    Key Features:
    - State persistence for resumability
    - HPC-native execution (sbatch/squeue)
    - Claude API integration for autonomous reasoning
    - Multi-objective optimization (configurable targets)
    - Dynamic configuration from a2mc_config.sh
    """

    def __init__(self, config: Config):
        self.config = config
        self.state_path = Path(config.state_file)
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize or load state
        if self.state_path.exists():
            logger.info(f"Loading existing state from {self.state_path}")
            self.state = WorkflowState.load(str(self.state_path))
        else:
            logger.info("Initializing new workflow state")
            self.state = WorkflowState()

        # Initialize memory system
        self._memory = None
        if config.use_memory:
            # output_dir is already the memory directory (e.g., use_cases/Kougarok/memory)
            # gained_knowledge/ contains JSON files for discoveries, experiments, etc.
            memory_dir = config.memory_dir or str(self.output_dir / "gained_knowledge")
            try:
                from memory import MemoryManager
                self._memory = MemoryManager(memory_dir)
                stats = self._memory.stats()
                logger.info(f"Memory system initialized: {stats['discoveries']['total']} discoveries, "
                           f"{stats['experiments']['total']} experiments")
            except ImportError as e:
                logger.warning(f"Memory module not available: {e}")
            except Exception as e:
                logger.warning(f"Could not initialize memory system: {e}")

        # Initialize workflow status tracker
        self._workflow_status = None
        if WorkflowStatus is not None:
            try:
                # output_dir is already the memory directory (e.g., use_cases/Kougarok/memory)
                # Don't append another /memory
                status_dir = str(self.output_dir) if self.output_dir else "memory"
                self._workflow_status = WorkflowStatus(log_dir=status_dir)
                logger.info(f"Workflow status tracker initialized: {self._workflow_status.log_file}")
            except Exception as e:
                logger.warning(f"Could not initialize workflow status: {e}")

        # Initialize phase logger
        self._phase_logger = None
        if PhaseLogger is not None:
            try:
                # Get site directory from config
                site_dir = None
                site_name = "Unknown"
                try:
                    from tools.config import config as a2mc_config
                    site_dir = a2mc_config.USE_CASE_DIR
                    site_name = a2mc_config.SITE_NAME
                except (ImportError, AttributeError):
                    site_dir = os.environ.get('A2MC_USE_CASE_DIR', str(self.output_dir))
                    site_name = os.environ.get('A2MC_SITE_NAME', 'Unknown')

                self._phase_logger = PhaseLogger(
                    site_dir=site_dir,
                    site_name=site_name,
                    iteration=self.state.iteration,
                    experiment_count=self.state.experiment_count,
                    skip_testing_count=self.state.skip_testing_count
                )
                logger.info(f"Phase logger initialized: {self._phase_logger.log_dir}")
            except Exception as e:
                logger.warning(f"Could not initialize phase logger: {e}")

        # Initialize modules (lazy loading)
        self._reasoning = None
        self._hpc = None
        self._data = None
        self._params = None

    @property
    def reasoning(self):
        """Lazy-load reasoning module with memory integration."""
        if self._reasoning is None and self.config.use_reasoning:
            from reasoning import ReasoningModule
            self._reasoning = ReasoningModule(
                model=self.config.claude_model,
                memory=self._memory
            )
        return self._reasoning

    @property
    def hpc(self):
        """Lazy-load HPC executor."""
        if self._hpc is None:
            from tools.hpc_utils import HPCExecutor
            self._hpc = HPCExecutor()  # HPCConfig auto-loads from env
        return self._hpc

    @property
    def data(self):
        """Lazy-load data pipeline."""
        if self._data is None:
            from integration import DataPipeline
            self._data = DataPipeline()  # Legacy: will be replaced by tools/extract_monthly_variables_FATES.py
        return self._data

    @property
    def params(self):
        """Lazy-load parameter manager."""
        if self._params is None:
            from tools.hpc_utils import ParameterManager
            self._params = ParameterManager()  # HPCConfig auto-loads from env
        return self._params

    def bootstrap(self) -> Dict[str, Any]:
        """
        Bootstrap the orchestrator: validate configuration, check dependencies,
        and prepare for execution.

        This method should be called before run() to ensure the system is ready.

        Returns:
            Dict with bootstrap status and any issues found
        """
        issues = []
        warnings = []
        info = []

        logger.info("=" * 60)
        logger.info("A2MC BOOTSTRAP: Validating configuration and dependencies")
        logger.info("=" * 60)

        # 1. Configuration validation
        logger.info("\n[1/5] Validating configuration...")
        config_issues = self._validate_config()
        issues.extend(config_issues)

        # 2. Check required files
        logger.info("\n[2/5] Checking required files...")
        file_issues = self._check_required_files()
        issues.extend([f for f in file_issues if f.startswith("ERROR")])
        warnings.extend([f for f in file_issues if f.startswith("WARNING")])
        info.extend([f for f in file_issues if f.startswith("INFO")])

        # 3. Validate existing state (if resuming)
        logger.info("\n[3/5] Validating workflow state...")
        state_issues = self._validate_state()
        issues.extend([s for s in state_issues if s.startswith("ERROR")])
        warnings.extend([s for s in state_issues if s.startswith("WARNING")])
        info.extend([s for s in state_issues if s.startswith("INFO")])

        # 4. Check module availability
        logger.info("\n[4/5] Checking module availability...")
        module_status = self._check_modules()
        for module, status in module_status.items():
            if status == "unavailable" and module in ["reasoning", "memory"]:
                warnings.append(f"WARNING: {module} module not available")
            elif status == "available":
                info.append(f"INFO: {module} module ready")

        # 5. Generate status report
        logger.info("\n[5/5] Generating status report...")

        status_report = {
            "ready": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "info": info,
            "state_summary": {
                "current_phase": self.state.current_phase,
                "iteration": self.state.iteration,
                "converged": self.state.converged,
                "experiments_count": len(self.state.experiments),
                "diagnoses_count": len(self.state.diagnoses),
                "hypotheses_count": len(self.state.hypotheses)
            },
            "config_summary": {
                "sampling_scheme": self.config.sampling_scheme,
                "n_parameters": self.config.n_parameters,
                "total_ensemble": self.config.total_ensemble,
                "max_iterations": self.config.max_iterations,
                "use_reasoning": self.config.use_reasoning,
                "use_memory": self.config.use_memory
            },
            "modules": module_status
        }

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("BOOTSTRAP SUMMARY")
        logger.info("=" * 60)

        if issues:
            logger.error(f"\n{len(issues)} CRITICAL ISSUES (must fix before running):")
            for issue in issues:
                logger.error(f"  - {issue}")

        if warnings:
            logger.warning(f"\n{len(warnings)} WARNINGS (workflow may be affected):")
            for warning in warnings:
                logger.warning(f"  - {warning}")

        logger.info(f"\nWorkflow State:")
        logger.info(f"  Phase: {self.state.current_phase}")
        logger.info(f"  Iteration: {self.state.iteration}")
        logger.info(f"  Converged: {self.state.converged}")

        logger.info(f"\nConfiguration:")
        logger.info(f"  Sampling: {self.config.sampling_scheme} ({self.config.total_ensemble} simulations)")
        logger.info(f"  Parameters: {self.config.n_parameters}")
        logger.info(f"  Max iterations: {self.config.max_iterations}")

        if status_report["ready"]:
            logger.info("\n[OK] System ready to run")
        else:
            logger.error("\n[FAIL] System NOT ready - fix issues before running")

        logger.info("=" * 60)

        return status_report

    def _human_review_checkpoint(self, phase: str, summary: str, next_phase: str,
                                  options: Dict[str, str] = None):
        """
        Interactive human review checkpoint.

        Stops workflow execution and waits for user decision before proceeding.

        Args:
            phase: Current phase name
            summary: Summary of what was accomplished
            next_phase: Name of the next phase
            options: Dict of key -> description for user choices
        """
        if options is None:
            options = {
                'c': f'Continue to {next_phase}',
                'q': 'Quit workflow (state saved)',
            }

        print("\n" + "=" * 70)
        print(f"  HUMAN REVIEW CHECKPOINT - {phase} COMPLETE")
        print("=" * 70)
        print(summary)
        print("\n" + "-" * 70)
        print("OPTIONS:")
        for key, desc in options.items():
            print(f"  [{key}] {desc}")
        print("-" * 70)

        # Save state before waiting (in case user quits)
        self.state.save(str(self.state_path))
        logger.info(f"State saved to {self.state_path}")

        while True:
            try:
                choice = input("\nEnter choice: ").strip().lower()

                if choice == 'c':
                    print(f"\n→ Continuing to {next_phase}...\n")
                    return

                elif choice == 'q':
                    print("\n→ Workflow paused. State has been saved.")
                    print(f"   Resume with: python orchestrator.py --resume --state-file {self.state_path}")
                    raise SystemExit(0)

                elif choice == 'r' and 'r' in options:
                    print("\n→ Re-run requested. This feature is not yet implemented.")
                    print("   Please quit and manually adjust settings.")
                    continue

                else:
                    print(f"Invalid choice '{choice}'. Please enter one of: {', '.join(options.keys())}")

            except EOFError:
                # Non-interactive mode (e.g., running in background)
                print("\n[Non-interactive mode detected - auto-continuing]")
                return

            except KeyboardInterrupt:
                print("\n\n→ Interrupted. State has been saved.")
                print(f"   Resume with: python orchestrator.py --resume --state-file {self.state_path}")
                raise SystemExit(0)

    def _validate_config(self) -> List[str]:
        """Validate configuration completeness and consistency."""
        issues = []

        # Check sampling scheme
        if not self.config.sampling_scheme:
            issues.append("ERROR: sampling_scheme not set")

        # Check parameters
        if self.config.n_parameters <= 0:
            issues.append("ERROR: n_parameters must be > 0")

        # Check total ensemble for morris scheme
        if self.config.sampling_scheme == "morris":
            if self.config.n_trajectories <= 0:
                issues.append("ERROR: n_trajectories must be > 0 for morris scheme")
            expected = self.config.n_trajectories * (self.config.n_parameters + 1)
            if self.config.total_ensemble > 0 and self.config.total_ensemble != expected:
                logger.warning(f"total_ensemble ({self.config.total_ensemble}) != "
                             f"expected ({expected}) for morris scheme")

        # Check output directory is writable
        try:
            test_file = self.output_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            issues.append(f"ERROR: Cannot write to output directory: {e}")

        return issues

    def _check_required_files(self) -> List[str]:
        """Check for required files based on current phase."""
        issues = []
        phase = Phase(self.state.current_phase)

        # Base parameter file
        if self.config.base_param_file:
            if Path(self.config.base_param_file).exists():
                issues.append(f"INFO: Base param file found: {self.config.base_param_file}")
            else:
                issues.append(f"WARNING: Base param file not found: {self.config.base_param_file}")

        # Parameter bounds file
        if self.config.param_bounds_file:
            if Path(self.config.param_bounds_file).exists():
                issues.append(f"INFO: Param bounds file found: {self.config.param_bounds_file}")
            else:
                issues.append(f"WARNING: Param bounds file not found: {self.config.param_bounds_file}")

        # Check for ensemble matrix file (needed for Phase 1+)
        try:
            from tools.config import config as a2mc_config
            ensemble_file = getattr(a2mc_config, 'ENSEMBLE_MATRIX_FILE', None)
            if ensemble_file and Path(ensemble_file).exists():
                issues.append(f"INFO: Ensemble matrix found: {ensemble_file}")
            elif phase.value in ['exploration', 'screening', 'diagnosis']:
                issues.append(f"WARNING: Ensemble matrix not found (needed for {phase.value})")
        except ImportError:
            pass

        return issues

    def _validate_state(self) -> List[str]:
        """Validate current workflow state for consistency."""
        issues = []
        phase = Phase(self.state.current_phase)

        # Check state consistency
        if phase == Phase.SCREENING and not self.state.sampling_design:
            issues.append("WARNING: In SCREENING phase but no sampling_design data")

        if phase == Phase.DIAGNOSIS and not self.state.screening_data:
            issues.append("WARNING: In DIAGNOSIS phase but no screening_data")

        if phase == Phase.HYPOTHESIS and not self.state.diagnoses:
            issues.append("WARNING: In HYPOTHESIS phase but no diagnoses recorded")

        if phase == Phase.TESTING and not self.state.hypotheses:
            issues.append("WARNING: In TESTING phase but no hypotheses generated")

        if phase == Phase.REFINEMENT and not self.state.experiments:
            issues.append("WARNING: In REFINEMENT phase but no experiments recorded")

        # Check for stale state
        if self.state.updated_at:
            try:
                last_update = datetime.fromisoformat(self.state.updated_at)
                age_hours = (datetime.now() - last_update).total_seconds() / 3600
                if age_hours > 24:
                    issues.append(f"INFO: State last updated {age_hours:.1f} hours ago")
            except Exception:
                pass

        # Report state summary
        issues.append(f"INFO: {len(self.state.phase_history)} phase transitions recorded")
        issues.append(f"INFO: {len(self.state.experiments)} experiments recorded")
        issues.append(f"INFO: {len(self.state.diagnoses)} diagnoses recorded")

        return issues

    def _check_modules(self) -> Dict[str, str]:
        """Check availability of optional modules."""
        modules = {}

        # Check reasoning module
        if self.config.use_reasoning:
            try:
                from reasoning import ReasoningModule
                modules["reasoning"] = "available"
            except ImportError:
                modules["reasoning"] = "unavailable"
        else:
            modules["reasoning"] = "disabled"

        # Check memory module
        if self.config.use_memory:
            if self._memory is not None:
                modules["memory"] = "available"
            else:
                modules["memory"] = "unavailable"
        else:
            modules["memory"] = "disabled"

        # Check HPC integration
        try:
            from tools.hpc_utils import HPCExecutor
            modules["hpc"] = "available"
        except ImportError:
            modules["hpc"] = "unavailable"

        # Check workflow status
        if self._workflow_status is not None:
            modules["workflow_status"] = "available"
        else:
            modules["workflow_status"] = "unavailable"

        # Check phase logger
        if self._phase_logger is not None:
            modules["phase_logger"] = "available"
        else:
            modules["phase_logger"] = "unavailable"

        # Check RAG system
        try:
            from rag import HybridRetriever
            modules["rag"] = "available"
        except ImportError:
            modules["rag"] = "unavailable"

        return modules

    def run(self):
        """
        Main execution loop.

        Runs through phases until convergence or max iterations reached.
        Each phase advances automatically or iterates based on results.
        """
        logger.info("=" * 70)
        logger.info("AGENTIC ADAPTIVE MULTI-TARGET CALIBRATION (A2MC) STARTING")
        logger.info(f"Current phase: {self.state.current_phase}")
        logger.info(f"Iteration: {self.state.iteration}")
        logger.info("=" * 70)

        # Start workflow status tracking
        if self._workflow_status:
            self._workflow_status.start_workflow(
                use_case=self.config.targets.__class__.__name__,
                workflow_id=f"a2mc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            self._workflow_status.set_iteration(self.state.iteration)

        while (not self.state.converged and
               self.state.iteration <= self.config.max_iterations and
               self.state.experiment_count < self.config.max_experiments):
            phase = Phase(self.state.current_phase)
            phase_num = list(Phase).index(phase)

            # Update environment variable for PhaseLogger to pick up
            os.environ['A2MC_ITERATION'] = str(self.state.iteration)

            logger.info(f"\n{'='*60}")
            logger.info(f"PHASE: {phase.value.upper()}")
            # Phases 0-2 run once per round; iteration only meaningful for 3-6
            iterative_phases = ('diagnosis', 'hypothesis', 'testing', 'refinement')
            if phase.value in iterative_phases:
                banner = f"Round {self.state.calibration_round}, Iteration {self.state.iteration}"
                if phase.value in ('diagnosis', 'hypothesis') and (
                        self.state.skip_testing_count > 0 or self.state.experiment_count > 0):
                    banner += (f" (skip-test: {self.state.skip_testing_count}, "
                               f"experiment: {self.state.experiment_count})")
            else:
                banner = f"Round {self.state.calibration_round}"
            logger.info(banner)
            logger.info(f"{'='*60}\n")

            # Track phase start in workflow status
            if self._workflow_status:
                self._workflow_status.start_phase(
                    phase=phase_num,
                    phase_name=phase.value,
                    iteration=self.state.iteration
                )

            try:
                # Execute current phase
                if phase == Phase.DESIGN:
                    self._run_design()
                elif phase == Phase.EXPLORATION:
                    self._run_exploration()
                elif phase == Phase.SCREENING:
                    self._run_screening()
                elif phase == Phase.DIAGNOSIS:
                    self._run_diagnosis()
                elif phase == Phase.HYPOTHESIS:
                    self._run_hypothesis()
                elif phase == Phase.TESTING:
                    self._run_testing()
                elif phase == Phase.REFINEMENT:
                    self._run_refinement()
                elif phase == Phase.CONVERGED:
                    self._handle_convergence()
                    break

                # Track phase completion in workflow status
                if self._workflow_status:
                    self._workflow_status.complete_phase(
                        phase=phase_num,
                        phase_name=phase.value
                    )

                # Save state after each phase
                self.state.save(str(self.state_path))

            except Exception as e:
                logger.error(f"Error in phase {phase.value}: {e}")
                # Track phase failure in workflow status
                if self._workflow_status:
                    self._workflow_status.fail_phase(
                        phase=phase_num,
                        error=str(e),
                        phase_name=phase.value
                    )
                    self._workflow_status.fail_workflow(
                        error=str(e),
                        phase=phase_num
                    )
                self.state.save(str(self.state_path))
                raise

        # Final status
        if self.state.converged:
            logger.info("\n" + "=" * 70)
            logger.info("CALIBRATION CONVERGED!")
            logger.info("=" * 70)
            # Mark workflow as complete
            if self._workflow_status:
                self._workflow_status.complete_workflow()
        else:
            # Determine which limit was hit
            if self.state.experiment_count >= self.config.max_experiments:
                logger.warning(f"Max experiments ({self.config.max_experiments}) reached without convergence")
            else:
                logger.warning(f"Max iterations ({self.config.max_iterations}) reached without convergence")
            logger.info(f"Final iteration: {self.state.iteration}")
            logger.info(f"Skip testing cycles: {self.state.skip_testing_count}")
            logger.info(f"Experiment cycles: {self.state.experiment_count}")
            # Mark workflow as paused (not failed, just stopped)
            if self._workflow_status:
                self._workflow_status.pause_workflow(
                    reason=f"Limits reached at iteration {self.state.iteration} "
                           f"(experiments: {self.state.experiment_count}/{self.config.max_experiments})"
                )

        # Show final workflow status
        if self._workflow_status:
            logger.info("\nWorkflow Status Summary:")
            self._workflow_status.show()

    # =========================================================================
    # PHASE 0: DESIGN - Sensitivity Sampling
    # =========================================================================
    def _run_design(self):
        """
        Phase 0: Create sensitivity analysis sampling design.

        This phase generates the parameter sampling matrix using the configured
        sampling scheme (from A2MC_SAMPLING_SCHEME):
        - morris: trajectories × (params + 1) simulations
        - lhs: n_samples simulations
        - sobol: samples × (2 × params + 2) simulations
        - custom: user-specified ensemble

        Outputs:
        - Sampling matrix (parameter sets)
        - Parameter bounds file
        """
        scheme = self.config.sampling_scheme
        n_params = self.config.n_parameters
        n_traj = self.config.n_trajectories
        n_sims = self.config.total_ensemble

        logger.info(f"Creating {scheme.upper()} sensitivity analysis design...")
        logger.info(f"Sampling design parameters:")
        logger.info(f"  Scheme: {scheme}")
        logger.info(f"  Parameters: {n_params}")
        if scheme == "morris":
            logger.info(f"  Trajectories: {n_traj}")
        logger.info(f"  Grid levels: {self.config.n_levels}")
        logger.info(f"  Total simulations: {n_sims}")

        # Create design using SALib or load existing
        design_data = self._create_sampling_design()

        if design_data is None:
            logger.warning("Sampling design creation skipped - using existing ensemble")
            # Load from config
            try:
                from tools.config import config as a2mc_config
                sampling_file = a2mc_config.ENSEMBLE_MATRIX_FILE
                param_file = a2mc_config.PARAM_LIST_FILE
            except ImportError:
                sampling_file = os.environ.get('A2MC_ENSEMBLE_MATRIX_FILE', '')
                param_file = os.environ.get('A2MC_PARAM_LIST_FILE', '')

            self.state.sampling_design = {
                "scheme": scheme,
                "n_parameters": n_params,
                "n_trajectories": n_traj if scheme == "morris" else 0,
                "n_levels": self.config.n_levels,
                "n_simulations": n_sims,
                "sampling_file": sampling_file,
                "parameter_bounds_file": param_file,
                "complete": True,
                "note": f"Using existing {scheme.upper()} ensemble ({n_sims} simulations)"
            }
        else:
            self.state.sampling_design = design_data

        # Transition to EXPLORATION
        self.state.record_phase_transition(
            Phase.DESIGN.value, Phase.EXPLORATION.value,
            f"Sampling design complete: {self.state.sampling_design.get('n_simulations', 0)} simulations"
        )
        self.state.current_phase = Phase.EXPLORATION.value
        logger.info("Design complete. Advancing to EXPLORATION.")

    def _create_sampling_design(self) -> Optional[Dict]:
        """
        Create sampling design using SALib.

        Returns None if using existing design.
        """
        scheme = self.config.sampling_scheme

        try:
            if scheme == "morris":
                from SALib.sample import morris as sampler
            elif scheme == "sobol":
                from SALib.sample import sobol as sampler
            elif scheme == "lhs":
                from SALib.sample import latin as sampler
            else:
                logger.info(f"Custom scheme '{scheme}' - using existing ensemble")
                return None

            # TODO: Implement dynamic parameter bounds loading and sampling
            logger.info(f"Using existing {scheme.upper()} ensemble (dynamic design not yet implemented)")
            return None

        except ImportError:
            logger.warning(f"SALib not installed. Using existing {scheme.upper()} ensemble.")
            return None

    # =========================================================================
    # PHASE 1: EXPLORATION - Run Sensitivity Ensemble
    # =========================================================================
    def _run_exploration(self):
        """
        Phase 1: Run sensitivity ensemble on HPC.

        This phase:
        1. Submits all ensemble simulations to HPC
        2. Monitors job completion
        3. Extracts results for sensitivity analysis
        4. Calculates sensitivity metrics (scheme-dependent)

        Inputs:
        - Sampling matrix (from DESIGN phase)
        - Base parameter file

        Outputs:
        - Simulation results (biomass, LAI, GPP)
        - Sensitivity rankings per target × output
        """
        sampling_design = self.state.sampling_design
        scheme = sampling_design.get("scheme", self.config.sampling_scheme)
        n_sims = sampling_design.get("n_simulations", 0)

        logger.info(f"Running {scheme.upper()} sensitivity ensemble on HPC...")

        # Check if ensemble already exists
        if sampling_design.get("complete", False):
            logger.info(f"Ensemble already complete ({n_sims} simulations)")
            logger.info("Analyzing existing results...")

            # Load existing sensitivity results
            self.state.exploration_data = self._analyze_existing_ensemble()

            # If extraction was attempted but no data produced, block
            if self.state.exploration_data.get("data_missing", False):
                logger.error("=" * 60)
                logger.error("WORKFLOW BLOCKED: No Y matrix data available")
                logger.error("=" * 60)
                logger.error("Auto-extraction was attempted but did not produce Y matrices.")
                logger.error("This typically means simulation output is not accessible.")
                logger.error("Run extraction on HPC, then resume:")
                logger.error(f"  python orchestrator.py --resume")
                self.state.save(str(self.state_path))
                raise SystemExit(1)

        else:
            # Submit ensemble to HPC
            logger.info(f"Submitting {n_sims} simulations to HPC...")

            # TODO: Implement HPC submission
            # job_ids = self.hpc.submit_ensemble(sampling_design)
            # self.hpc.wait_for_completion(job_ids)

            # For now, mark as complete with placeholder
            self.state.exploration_data = {
                "n_simulations": n_sims,
                "status": "placeholder",
                "note": "HPC submission not yet implemented"
            }

        # Log exploration to phase logger
        if self._phase_logger:
            try:
                self._phase_logger.set_iteration_context(
                        calibration_round=self.state.calibration_round,
                        iteration=self.state.iteration,
                        experiment_count=self.state.experiment_count,
                        skip_testing_count=self.state.skip_testing_count
                    )
                exploration_data = self.state.exploration_data

                # Build sensitivity analysis summary for log
                ai_reasoning = self._build_sensitivity_summary(exploration_data)

                log_path = self._phase_logger.log_exploration(
                    title="Exploration",
                    total_cases=n_sims,
                    completed_cases=exploration_data.get('extracted_cases', 0),
                    failed_cases=n_sims - exploration_data.get('extracted_cases', 0),
                    ai_reasoning=ai_reasoning,
                    issues_encountered=[],
                    metadata={
                        'iteration': self.state.iteration,
                        'scheme': scheme,
                        'analysis_complete': exploration_data.get('analysis_complete', False),
                        'sensitivity_rankings': exploration_data.get('sensitivity_rankings', {}),
                        'analysis_results': exploration_data.get('analysis_results', [])
                    }
                )
                logger.info(f"  Phase log written: {log_path}")
            except Exception as e:
                logger.warning(f"Could not write exploration log: {e}")

        # Transition to SCREENING
        self.state.record_phase_transition(
            Phase.EXPLORATION.value, Phase.SCREENING.value,
            f"Exploration complete: {n_sims} simulations analyzed"
        )
        self.state.current_phase = Phase.SCREENING.value
        logger.info("Exploration complete. Advancing to SCREENING.")

    def _analyze_existing_ensemble(self) -> Dict:
        """
        Analyze existing sensitivity ensemble results.

        Checks for extracted data, counts available cases, and runs
        Morris sensitivity analysis if extraction is complete.

        Returns info about extraction status and sensitivity rankings.
        """
        n_sims = self.config.total_ensemble

        results = {
            "n_simulations": n_sims,
            "analysis_complete": False,
            "sensitivity_rankings": {},
            "extracted_cases": 0,
            "extraction_complete": False
        }

        # Try to load results from configured location
        try:
            from tools.config import config as a2mc_config
            ensemble_dir = Path(a2mc_config.ENSEMBLE_OUTPUT)
            extracted_dir = Path(a2mc_config.EXTRACTED_DATA)

            results["ensemble_output_dir"] = str(ensemble_dir)
            results["extracted_data_dir"] = str(extracted_dir)

            # Count extracted NetCDF files
            if extracted_dir.exists():
                # Pattern: *_PtCNPEn{N}_TRANS_all_variables_monthly_*.nc
                nc_files = list(extracted_dir.glob("*_all_variables_monthly_*.nc"))
                results["extracted_cases"] = len(nc_files)

                if len(nc_files) > 0:
                    logger.info(f"Found {len(nc_files)} extracted NetCDF files in: {extracted_dir}")

                    # Check if extraction is reasonably complete (>90%)
                    if len(nc_files) >= n_sims * 0.9:
                        results["extraction_complete"] = True
                        logger.info(f"Extraction appears complete ({len(nc_files)}/{n_sims} = {100*len(nc_files)/n_sims:.1f}%)")
                    else:
                        logger.warning(f"Extraction incomplete: {len(nc_files)}/{n_sims} ({100*len(nc_files)/n_sims:.1f}%)")
                        logger.info("Run: python phases/phase1_exploration/extract_sensitivity_outputs.py")
                else:
                    logger.info(f"No extracted files found in: {extracted_dir}")
                    logger.info("Running monthly variable extraction from simulation output...")
                    extraction_result = self._run_monthly_extraction()
                    if extraction_result.get('status') in ['completed', 'partial']:
                        nc_files = list(extracted_dir.glob("*_all_variables_monthly_*.nc"))
                        results["extracted_cases"] = len(nc_files)
                        if len(nc_files) >= n_sims * 0.9:
                            results["extraction_complete"] = True
                        logger.info(f"Monthly extraction done: {len(nc_files)} cases extracted")
                    else:
                        logger.warning(f"Monthly extraction failed: {extraction_result.get('error', 'unknown')}")
            else:
                logger.warning(f"Extracted data directory does not exist: {extracted_dir}")
                logger.info("Running monthly variable extraction from simulation output...")
                extraction_result = self._run_monthly_extraction()
                if extraction_result.get('status') in ['completed', 'partial']:
                    extracted_dir.mkdir(parents=True, exist_ok=True)
                    nc_files = list(extracted_dir.glob("*_all_variables_monthly_*.nc"))
                    results["extracted_cases"] = len(nc_files)
                    if len(nc_files) >= n_sims * 0.9:
                        results["extraction_complete"] = True
                    logger.info(f"Monthly extraction done: {len(nc_files)} cases extracted")
                else:
                    logger.warning(f"Monthly extraction failed: {extraction_result.get('error', 'unknown')}")

            # Check for Morris sensitivity results (Y matrices)
            # Look in multiple locations
            # Pattern: Morris{Varname}_{N}cases_{start}_{end}.txt
            # e.g., MorrisLeafbiomass_4889cases_2010_2019.txt
            phase1_output_dir = Path(a2mc_config.USE_CASE_DIR) / "memory" / "phase_results" / "phase1_exploration"
            morris_files = list(phase1_output_dir.glob("Morris*biomass*.txt")) if phase1_output_dir.exists() else []

            # Also check current directory and ensemble output
            if not morris_files:
                morris_files = list(Path('.').glob("Morris*biomass*.txt"))
            if not morris_files and ensemble_dir.exists():
                morris_files = list(ensemble_dir.glob("Morris*biomass*.txt"))

            if morris_files:
                logger.info(f"Found {len(morris_files)} Morris Y matrix files")
                results["morris_y_matrices"] = [str(f) for f in morris_files]

                # Run Morris sensitivity analysis
                results = self._run_morris_sensitivity_analysis(results, morris_files)

            elif results.get("extraction_complete", False):
                # Extraction complete but no Y matrices - need to extract from NetCDF
                logger.info("Extraction complete but no Y matrices found. Running Y matrix extraction...")
                results = self._run_y_matrix_extraction(results)

                # Check again for Y matrices after extraction
                morris_files = list(phase1_output_dir.glob("Morris*biomass*.txt")) if phase1_output_dir.exists() else []
                if morris_files:
                    logger.info(f"Found {len(morris_files)} Morris Y matrix files after extraction")
                    results["morris_y_matrices"] = [str(f) for f in morris_files]
                    results = self._run_morris_sensitivity_analysis(results, morris_files)
            else:
                # No Y matrices and extraction not marked complete — try extraction anyway
                logger.info("No Morris Y matrices found. Attempting Y matrix extraction...")
                results = self._run_y_matrix_extraction(results)

                # Check again for Y matrices after extraction
                morris_files = list(phase1_output_dir.glob("Morris*biomass*.txt")) if phase1_output_dir.exists() else []
                if not morris_files:
                    morris_files = list(Path('.').glob("Morris*biomass*.txt"))
                if morris_files:
                    logger.info(f"Found {len(morris_files)} Morris Y matrix files after extraction")
                    results["morris_y_matrices"] = [str(f) for f in morris_files]
                    results = self._run_morris_sensitivity_analysis(results, morris_files)
                else:
                    logger.warning("Y matrix extraction did not produce output files.")
                    logger.warning("This may mean simulation output is not accessible from this machine.")
                    logger.info("If running remotely, extract on HPC first:")
                    logger.info("  python tools/extract_monthly_variables_FATES.py --case-file completed_cases.txt")
                    logger.info("  python phases/phase1_exploration/extract_sensitivity_outputs.py")
                    results["data_missing"] = True

        except ImportError:
            logger.debug("tools.config not available, skipping results loading")

        return results

    def _run_monthly_extraction(self) -> Dict:
        """
        Extract comprehensive monthly variables from simulation output.

        Calls tools/extract_monthly_variables_FATES.run_monthly_extraction() to
        produce per-case NetCDF files with all variables (biomass, nutrients,
        fluxes, etc.) that Phase 3 diagnostic scripts need.

        Falls back to integration.DataPipeline if direct import fails.

        Returns:
            Dict with 'status', 'successful_cases', 'failed_cases', 'output_dir'
        """
        # Primary: direct in-process call (efficient, skips already-extracted)
        try:
            from tools.extract_monthly_variables_FATES import run_monthly_extraction
            logger.info("Starting monthly variable extraction from simulation output...")
            result = run_monthly_extraction()
            if result.get('status') in ['completed', 'partial']:
                logger.info(f"Monthly extraction {result['status']}: "
                            f"{result.get('total_extracted', len(result.get('successful_cases', [])))} cases")
            else:
                logger.warning(f"Monthly extraction failed: {result.get('error', 'unknown')}")
            return result
        except ImportError as e:
            logger.warning(f"Could not import monthly extraction directly: {e}")

        # Fallback: use DataPipeline (subprocess-based, slower but always available)
        try:
            logger.info("Falling back to DataPipeline for extraction...")
            # Test first case before attempting all ~4890 cases
            test_result = self.data.extract_case_data("1")
            if not test_result.get('success'):
                error_msg = test_result.get('error', 'extraction failed')
                logger.error(f"Test extraction of case 1 failed: {error_msg}")
                if 'xarray' in str(error_msg) or 'ModuleNotFoundError' in str(error_msg):
                    logger.error("Missing Python packages. On Perlmutter, run:")
                    logger.error("  module load python")
                    logger.error("  # OR: conda activate <your_env>")
                return {'status': 'failed', 'error': error_msg}

            n_sims = self.config.total_ensemble
            case_ids = [str(i) for i in range(1, n_sims + 1)]
            results = self.data.extract_batch(case_ids)
            n_success = sum(1 for r in results if r.get('success'))
            status = 'completed' if n_success >= len(case_ids) * 0.9 else 'partial'
            return {'status': status, 'total_extracted': n_success}
        except Exception as e:
            logger.error(f"Error during monthly extraction: {e}")
            return {'status': 'failed', 'error': str(e)}

    def _run_y_matrix_extraction(self, results: Dict) -> Dict:
        """
        Extract Y matrices from simulation outputs for Morris analysis.

        Args:
            results: Current results dict to update

        Returns:
            Updated results dict with extraction info
        """
        try:
            from phases.phase1_exploration.extract_sensitivity_outputs import run_extraction
            from tools.config import config as a2mc_config

            # Output directory for Y matrices
            output_dir = Path(a2mc_config.USE_CASE_DIR) / "memory" / "phase_results" / "phase1_exploration"

            logger.info("Extracting Y matrices from simulation outputs...")

            extraction_result = run_extraction(
                output_vars=['leaf_biomass', 'fineroot_biomass', 'abg_biomass'],
                output_dir=str(output_dir),
                resume=True
            )

            if extraction_result.get('status') in ['completed', 'partial']:
                results["y_matrix_files"] = extraction_result.get('y_matrix_files', {})
                results["extraction_statistics"] = extraction_result.get('statistics', {})
                logger.info(f"Y matrix extraction complete: {len(results['y_matrix_files'])} variables")
            else:
                logger.warning("Y matrix extraction failed")

        except ImportError as e:
            logger.warning(f"Could not import extraction module: {e}")
        except Exception as e:
            logger.error(f"Error during Y matrix extraction: {e}")

        return results

    def _run_morris_sensitivity_analysis(self, results: Dict, morris_files: List[Path]) -> Dict:
        """
        Run Morris sensitivity analysis on extracted Y matrices.

        Args:
            results: Current results dict to update
            morris_files: List of Morris Y matrix files

        Returns:
            Updated results dict with sensitivity rankings
        """
        try:
            from phases.phase1_exploration.morris_sensitivity_analysis import run_sensitivity_analysis
            from tools.config import config as a2mc_config

            # Determine output directory for sensitivity results
            output_dir = Path(a2mc_config.USE_CASE_DIR) / "memory" / "phase_results" / "phase1_exploration"
            output_dir.mkdir(parents=True, exist_ok=True)

            # Map Y matrix files to output variables
            var_mapping = {
                'leaf': 'leaf_biomass',
                'fineroot': 'fineroot_biomass',
                'abg': 'abg_biomass',
                'agb': 'abg_biomass',  # Alternative naming
            }

            all_rankings = {}
            analysis_results = []

            for y_file in morris_files:
                # Detect output variable from filename
                y_filename = y_file.name.lower()
                output_var = None

                for key, var in var_mapping.items():
                    if key in y_filename:
                        output_var = var
                        break

                if not output_var:
                    logger.warning(f"Could not determine output variable for: {y_file}")
                    continue

                logger.info(f"Running Morris analysis for {output_var}...")
                logger.info(f"  Y matrix: {y_file}")

                try:
                    # Run sensitivity analysis
                    sa_result = run_sensitivity_analysis(
                        output_var=output_var,
                        y_matrix_path=str(y_file),
                        output_dir=str(output_dir)
                    )

                    if sa_result.get('status') == 'completed':
                        all_rankings[output_var] = sa_result.get('rankings', {})
                        analysis_results.append({
                            'output_var': output_var,
                            'n_trajectories': sa_result.get('n_complete_trajectories', 0),
                            'plot_file': sa_result.get('plot_file'),
                            'csv_file': sa_result.get('csv_file')
                        })
                        logger.info(f"  Completed: {sa_result.get('n_complete_trajectories')} trajectories")
                    else:
                        logger.warning(f"  Analysis failed: {sa_result.get('error', 'Unknown error')}")

                except Exception as e:
                    logger.error(f"  Error running analysis for {output_var}: {e}")
                    continue

            if all_rankings:
                results["sensitivity_rankings"] = all_rankings
                results["analysis_results"] = analysis_results
                results["analysis_complete"] = True
                logger.info(f"Morris analysis complete for {len(all_rankings)} variables")
            else:
                logger.warning("No sensitivity rankings computed")

        except ImportError as e:
            logger.warning(f"Could not import Morris analysis module: {e}")
            logger.info("Install SALib: pip install SALib")

        return results

    def _build_sensitivity_summary(self, exploration_data: Dict) -> str:
        """
        Build a human-readable summary of sensitivity analysis results.

        Args:
            exploration_data: Dict containing sensitivity rankings

        Returns:
            Markdown-formatted summary string
        """
        if not exploration_data.get('analysis_complete', False):
            return "Sensitivity analysis not yet complete."

        rankings = exploration_data.get('sensitivity_rankings', {})
        if not rankings:
            return "No sensitivity rankings available."

        lines = ["## Morris Sensitivity Analysis Summary\n"]

        for output_var, pft_rankings in rankings.items():
            lines.append(f"### {output_var.replace('_', ' ').title()}\n")

            for pft_name, params in pft_rankings.items():
                if not params:
                    continue

                lines.append(f"**{pft_name}** - Top 5 most sensitive parameters:\n")
                for i, p in enumerate(params[:5]):
                    mu_star = p.get('mu_star', 0)
                    sigma = p.get('sigma', 0)
                    lines.append(f"  {i+1}. `{p['parameter']}`: μ*={mu_star:.3f}, σ={sigma:.3f}")
                lines.append("")

        # Add analysis results info
        analysis_results = exploration_data.get('analysis_results', [])
        if analysis_results:
            lines.append("### Output Files\n")
            for ar in analysis_results:
                lines.append(f"- **{ar['output_var']}**: {ar.get('n_trajectories', 0)} trajectories")
                if ar.get('plot_file'):
                    lines.append(f"  - Plot: `{ar['plot_file']}`")
                if ar.get('csv_file'):
                    lines.append(f"  - CSV: `{ar['csv_file']}`")

        return "\n".join(lines)

    # =========================================================================
    # PHASE 2: SCREENING - Multi-Objective Filtering
    # =========================================================================
    def _run_screening(self):
        """
        Phase 2: Screen ensemble cases against validation targets.

        This phase:
        1. Evaluates each case against configured targets
        2. Identifies best-performing cases (top N)
        3. Determines which targets are met/failed
        4. Analyzes cross-target performance patterns

        Outputs:
        - Best cases ranked by composite cost
        - Target success/failure matrix
        - Conflict analysis (if multi-objective)
        """
        # Check if screening already completed (e.g., resuming after checkpoint)
        screening_data = self.state.screening_data
        if screening_data and screening_data.get("n_cases_evaluated", 0) > 0:
            logger.info("Screening already completed (resuming from checkpoint)")
        else:
            n_sims = self.config.total_ensemble
            logger.info(f"Screening {n_sims} cases against validation targets...")

            targets = self.config.targets

            # Try to load screening results from configured location
            try:
                from tools.config import config as a2mc_config
                results_dir = Path(a2mc_config.ENSEMBLE_OUTPUT)
                results_file = results_dir / "screening_results.txt"
            except ImportError:
                results_file = Path("")

            if results_file.exists():
                logger.info(f"Loading existing screening results: {results_file}")
                screening_data = self._load_screening_results(results_file)
            else:
                # Run screening analysis
                logger.info("Running new screening analysis...")
                screening_data = self._perform_screening(targets)

            self.state.screening_data = screening_data

            # Log key findings
            n_cases = screening_data.get("n_cases_evaluated", 0)
            best_case = screening_data.get("best_case", {})
            targets_met = best_case.get("targets_met", 0)

            logger.info(f"Screening complete:")
            logger.info(f"  Cases evaluated: {n_cases}")
            logger.info(f"  Best case: #{best_case.get('case_id', 'N/A')}")
            logger.info(f"  Targets met: {targets_met}/8")

            # Critical finding
            if targets_met < 8:
                logger.info(f"  CRITICAL: 0/{n_cases} cases achieve all targets")
                logger.info(f"  → Proceeding to DIAGNOSIS phase")

            # Generate AI reasoning for screening results
            ai_reasoning = ""
            if self.config.use_reasoning and self.reasoning:
                try:
                    logger.info("Generating AI analysis of screening results...")
                    ai_reasoning = self._generate_screening_analysis(screening_data)
                    logger.info("  AI analysis complete")
                except Exception as e:
                    logger.warning(f"Could not generate AI screening analysis: {e}")
                    ai_reasoning = f"*AI analysis failed: {e}*"

            # Log to phase logger
            if self._phase_logger:
                try:
                    self._phase_logger.set_iteration_context(
                        calibration_round=self.state.calibration_round,
                        iteration=self.state.iteration,
                        experiment_count=self.state.experiment_count,
                        skip_testing_count=self.state.skip_testing_count
                    )
                    log_path = self._phase_logger.log_screening(
                        title="Screening",
                        n_sets_evaluated=n_cases,
                        best_cost=best_case.get('composite_rmsre', float('inf')),
                        top_sets=[c.get('case_num', 0) for c in screening_data.get('best_cases', [])[:10]],
                        ai_reasoning=ai_reasoning,
                        target_performance=screening_data.get('target_performance', {}),
                        key_findings=[
                            f"Best case: #{best_case.get('case_id', 'N/A')}",
                            f"Targets met: {targets_met}/8",
                            f"Cases evaluated: {n_cases}"
                        ],
                        metadata={
                            'iteration': self.state.iteration,
                            'n_simulations': self.config.total_ensemble
                        }
                    )
                    logger.info(f"  Phase log written: {log_path}")
                except Exception as e:
                    logger.warning(f"Could not write screening log: {e}")

        # Extract summary for checkpoint display
        n_cases = screening_data.get("n_cases_evaluated", 0)
        best_case = screening_data.get("best_case", {})
        targets_met = best_case.get("targets_met", 0)

        # Human review checkpoint after screening
        if self.config.human_review:
            top_cases_str = ", ".join([f"#{c.get('case_num', '?')}" for c in screening_data.get('best_cases', [])[:5]])
            self._human_review_checkpoint(
                phase="SCREENING",
                summary=f"""
Screening Summary:
  - Cases evaluated: {n_cases}
  - Best case: #{best_case.get('case_id', 'N/A')}
  - Best composite RMSRE: {best_case.get('composite_rmsre', 'N/A'):.3f}
  - Targets met: {targets_met}/8
  - Top 5 cases: {top_cases_str}

{'ALL TARGETS MET - Ready for convergence!' if targets_met >= 8 else 'Not all targets met - proceeding to diagnosis.'}

Review the screening log at:
  use_cases/{{site}}/memory/logs/phase2_screening/
""",
                next_phase="DIAGNOSIS",
                options={
                    'c': 'Continue to diagnosis phase',
                    'q': 'Quit workflow (state saved)',
                }
            )

        # Transition to DIAGNOSIS
        self.state.record_phase_transition(
            Phase.SCREENING.value, Phase.DIAGNOSIS.value,
            f"Best case meets {targets_met}/8 targets"
        )
        self.state.current_phase = Phase.DIAGNOSIS.value
        logger.info("Screening complete. Advancing to DIAGNOSIS.")

    def _load_screening_results(self, results_file: Path) -> Dict:
        """Load pre-computed screening results."""
        screening_data = {
            "n_cases_evaluated": 4329,
            "results_file": str(results_file),
            "best_cases": [],
            "target_performance": {},
            "case_numbers": [],  # actual case IDs from the CSV
        }

        # Parse results file
        try:
            with open(results_file, 'r') as f:
                lines = f.readlines()

            # Extract all case IDs and top 10 cases
            # Format: Case_ID, Type, Composite_NRMSE, ...
            all_case_ids = []
            for i, line in enumerate(lines[1:]):  # skip header
                parts = line.strip().split(',')
                if len(parts) >= 3 and parts[0].strip():
                    try:
                        case_id = int(parts[0].strip())
                        all_case_ids.append(case_id)
                    except ValueError:
                        all_case_ids.append(parts[0].strip())

                    if i < 10:  # Top 10 cases
                        screening_data["best_cases"].append({
                            "case_id": parts[0].strip(),
                            "type": parts[1].strip() if len(parts) > 1 else "",
                            "composite_nrmse": float(parts[2]) if parts[2] else None
                        })

            # Store all case numbers (maps array index → actual case number)
            screening_data["case_numbers"] = all_case_ids
            screening_data["n_cases_evaluated"] = len(all_case_ids)

            # Set best case
            if screening_data["best_cases"]:
                screening_data["best_case"] = {
                    "case_id": screening_data["best_cases"][0]["case_id"],
                    "composite_nrmse": screening_data["best_cases"][0]["composite_nrmse"],
                    "targets_met": 2  # Known from previous analysis
                }

        except Exception as e:
            logger.warning(f"Error loading screening results: {e}")

        return screening_data

    def _perform_screening(self, targets: ValidationTargets) -> Dict:
        """
        Perform new screening analysis against targets.

        Calls phases/phase2_screening/screen_ensemble.py to:
        1. Load simulation outputs from EXTRACTED_DATA
        2. Rank against validation targets
        3. Return structured results
        """
        try:
            from phases.phase2_screening.screen_ensemble import (
                screen_ensemble, load_kougarok_targets, ScreeningConfig
            )
            from tools.config import config as a2mc_config

            # Get data directory from config
            data_dir = Path(a2mc_config.EXTRACTED_DATA)
            if not data_dir.exists():
                logger.error(f"Extracted data directory not found: {data_dir}")
                return {"n_cases_evaluated": 0, "error": "Data directory not found"}

            logger.info(f"Loading data from: {data_dir}")

            # Load targets (use site-specific targets)
            screening_targets = load_kougarok_targets()

            # Configure screening
            config = ScreeningConfig(
                data_dir=data_dir,
                year_start=1901,
                year_end=2019,
                obs_year=2016,
                obs_month=7  # July
            )

            # Run screening
            result = screen_ensemble(data_dir, screening_targets, config=config, top_n=100)

            # Get top 10 cases by cost (RMSRE)
            top_cases = result.get_top_cases(10)

            # Find best case: most targets satisfied within top 10 by cost
            # This balances low error with high target satisfaction
            best_case_in_top10 = max(top_cases, key=lambda c: (c['n_satisfied'], -c['cost']))

            # Convert to dict format expected by orchestrator
            # case_numbers: maps array index → actual case number (not all 4890
            # cases may exist; missing cases are skipped during loading).
            # Downstream phases (diagnosis, hypothesis) use this to reference
            # the correct case in the Morris parameter matrix.
            screening_data = {
                "n_cases_evaluated": result.n_valid_cases,
                "n_available_cases": result.n_available_cases,
                "case_numbers": result.case_numbers,  # [int] actual case IDs
                "best_case": {
                    "case_id": best_case_in_top10['case_num'],
                    "composite_rmsre": best_case_in_top10['cost'],
                    "targets_met": best_case_in_top10['n_satisfied']
                },
                "lowest_cost_case": {
                    "case_id": result.best_case_num,
                    "composite_rmsre": result.best_cost,
                    "targets_met": int(top_cases[0]['n_satisfied']) if top_cases else 0
                },
                "best_cases": top_cases,
                "target_performance": result.to_dict().get('targets_satisfied_distribution', {}),
                "max_targets_satisfied": result.max_satisfied_count,
                "status": "completed"
            }

            # Generate ensemble biomass figure
            try:
                from phases.phase2_screening.plot_screening import (
                    plot_ensemble_biomass, rank_cases_by_nrmse
                )
                # Build simple target dict from screening targets
                simple_targets = {
                    name: {'observed': t.observed, 'uncertainty': t.uncertainty}
                    for name, t in screening_targets.items()
                }
                # Build ranked_cases list from optimization result
                ranked_cases = []
                for idx in result.optimization_result.ranked_indices:
                    ranked_cases.append({
                        'case_num': result.case_numbers[idx],
                        'composite_nrmse': float(result.optimization_result.composite_cost[idx]),
                        'n_satisfied': int(result.optimization_result.n_satisfied[idx]),
                        'n_total': len(screening_targets),
                    })
                # Determine output path in phase_results directory
                # (consistent with Phase 1 and Phase 3 which use phase_results/)
                fig_dir = None
                if a2mc_config.USE_CASE_DIR:
                    fig_dir = Path(a2mc_config.USE_CASE_DIR) / "memory" / "phase_results" / "phase2_screening"
                    fig_dir.mkdir(parents=True, exist_ok=True)
                if not fig_dir:
                    fig_dir = data_dir
                fig_path = plot_ensemble_biomass(
                    data_dir=str(data_dir),
                    ranked_cases=ranked_cases,
                    targets=simple_targets,
                    pft_ids=config.pfts,
                    output_path=str(Path(fig_dir) / 'ensemble_biomass_top_cases.png'),
                    top_n=100,
                )
                if fig_path:
                    screening_data['figure_paths'] = [fig_path]
                    logger.info(f"  Ensemble biomass figure: {fig_path}")
            except Exception as e:
                logger.warning(f"Could not generate ensemble biomass figure: {e}")

            return screening_data

        except ImportError as e:
            logger.warning(f"Could not import screening module: {e}")
            return {"n_cases_evaluated": 0, "error": str(e)}
        except Exception as e:
            logger.error(f"Screening failed: {e}")
            import traceback
            traceback.print_exc()
            return {"n_cases_evaluated": 0, "error": str(e)}

    def _generate_screening_analysis(self, screening_data: Dict) -> str:
        """
        Generate AI analysis of screening results.

        Args:
            screening_data: Results from _perform_screening()

        Returns:
            Markdown-formatted AI analysis string
        """
        # Extract key metrics
        n_cases = screening_data.get("n_cases_evaluated", 0)
        best_case = screening_data.get("best_case", {})
        best_cases = screening_data.get("best_cases", [])[:10]
        target_perf = screening_data.get("target_performance", {})
        max_satisfied = screening_data.get("max_targets_satisfied", 0)

        # Build summary for AI
        summary = f"""## Screening Results Summary

**Ensemble Size:** {n_cases} cases evaluated
**Best Case:** #{best_case.get('case_id', 'N/A')}
- Composite RMSRE: {best_case.get('composite_rmsre', 'N/A'):.4f}
- Targets Met: {best_case.get('targets_met', 0)}/8

**Target Satisfaction Distribution:**
"""
        for n_targets, count in sorted(target_perf.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0, reverse=True):
            pct = count / n_cases * 100 if n_cases > 0 else 0
            summary += f"- {n_targets} targets: {count} cases ({pct:.1f}%)\n"

        summary += f"""
**Top 10 Cases:**
| Rank | Case | RMSRE | Targets Met |
|------|------|-------|-------------|
"""
        for i, case in enumerate(best_cases):
            summary += f"| {i+1} | #{case.get('case_num', '?')} | {case.get('cost', 0):.4f} | {case.get('n_satisfied', 0)}/8 |\n"

        # Get sensitivity rankings from exploration phase if available
        sensitivity_info = ""
        if hasattr(self.state, 'exploration_data') and self.state.exploration_data:
            rankings = self.state.exploration_data.get('sensitivity_rankings', {})
            if rankings:
                sensitivity_info = "\n**Top Sensitive Parameters (from Phase 1):**\n"
                for var, pft_rankings in list(rankings.items())[:1]:  # Just first variable
                    for pft, params in list(pft_rankings.items())[:3]:  # Top 3 PFTs
                        if params:
                            top3 = [p['parameter'] for p in params[:3]]
                            sensitivity_info += f"- {pft}: {', '.join(top3)}\n"

        # Call AI for analysis
        prompt = f"""Analyze these ELM-FATES calibration screening results and provide insights:

{summary}
{sensitivity_info}

Please provide:
1. **Key Observations:** What patterns do you see in the results?
2. **Calibration Challenges:** Why might no cases achieve all 8 targets?
3. **Promising Directions:** Based on the top cases, what parameter adjustments might help?
4. **Recommendations:** What should the diagnosis phase focus on?

Keep your analysis concise (3-4 sentences per section)."""

        try:
            response = self.reasoning.query(prompt, max_tokens=1500)
            return response
        except Exception as e:
            # Fallback to rule-based summary
            return f"""## Automated Analysis

**Key Observations:**
- Best case achieves {best_case.get('targets_met', 0)}/8 targets with RMSRE {best_case.get('composite_rmsre', 'N/A'):.4f}
- {target_perf.get('0', 0)} cases ({target_perf.get('0', 0)/n_cases*100:.1f}%) meet zero targets
- Maximum targets satisfied by any case: {max_satisfied}

**Calibration Challenge:**
Multi-objective optimization with 8 biomass targets across 3 PFTs creates trade-offs where improving one PFT often degrades another.

**Recommendation:**
Focus diagnosis on identifying which PFT combinations conflict and whether parameter bounds need expansion.

*Note: AI analysis unavailable ({e})*"""

    # =========================================================================
    # PHASE 3: DIAGNOSIS - Root Cause Analysis
    # =========================================================================
    def _run_diagnosis(self):
        """
        Phase 3: Diagnose why calibration targets fail.

        This phase uses Claude API to analyze:
        1. Edge Analysis - Are optimal parameters at sampling bounds?
        2. Cross-Case Comparison - Why do different cases succeed for different targets?
        3. Mechanistic Analysis - What model processes limit performance?

        Outputs:
        - Structured Diagnosis object
        - Mechanistic hypotheses for testing
        """
        # Check if diagnosis already exists for this iteration (e.g., resuming after checkpoint)
        existing_diagnosis = None
        if self.state.diagnoses:
            last_diag = self.state.diagnoses[-1]
            if last_diag.get('iteration') == self.state.iteration:
                existing_diagnosis = last_diag
                logger.info("Diagnosis already completed for this iteration (resuming from checkpoint)")

        if existing_diagnosis:
            diagnosis = existing_diagnosis
        else:
            logger.info("Diagnosing calibration failures...")

            screening_data = self.state.screening_data
            exploration_data = self.state.exploration_data

            # Run diagnostic scripts to get actual parameter values and edge analysis
            diagnostic_data = None
            if HAS_DIAGNOSIS_TOOLS:
                try:
                    diagnostic_data = self._run_diagnostic_scripts(screening_data)
                    if diagnostic_data:
                        logger.info(f"Diagnostic analysis complete:")
                        logger.info(f"  Parameters read: {len(diagnostic_data.parameters)}")
                        logger.info(f"  Edge parameters: {len(diagnostic_data.edge_analysis.get('parameters_at_lower_bound', [])) + len(diagnostic_data.edge_analysis.get('parameters_at_upper_bound', []))}")
                        logger.info(f"  Redesign candidates: {len(diagnostic_data.redesign_candidates)}")
                except Exception as e:
                    logger.warning(f"Diagnostic scripts failed: {e}")
                    diagnostic_data = None

            # Prepare data for Claude reasoning
            diagnosis_input = {
                "screening_results": screening_data,
                "sensitivity_rankings": exploration_data.get("sensitivity_rankings", {}),
                "targets": asdict(self.config.targets),
                "iteration": self.state.iteration,
                "diagnostic_data": diagnostic_data,  # Pass diagnostic results to Claude
                "hypothesis_tests": self.state.hypothesis_tests,  # Results from Skip Testing path
                "previous_hypotheses": self.state.hypotheses,  # Previous hypotheses for context
                "cumulative_insights": self.state.cumulative_insights,  # Cross-cycle synthesis
            }

            # Use Claude API for diagnosis (if available)
            if self.reasoning:
                logger.info("Using Claude API for diagnosis...")
                diagnosis = self._diagnose_with_claude(diagnosis_input)
            else:
                logger.info("Claude API not available, using rule-based diagnosis...")
                diagnosis = self._diagnose_rule_based(diagnosis_input)

            # Handle requested diagnostics (if AI requested additional analyses)
            requested_diagnostics = diagnosis.get('requested_diagnostics', [])
            if requested_diagnostics and HAS_DIAGNOSIS_TOOLS:
                logger.info(f"AI requested {len(requested_diagnostics)} additional diagnostics")
                additional_context = self._execute_requested_diagnostics(
                    requested_diagnostics, screening_data
                )
                if additional_context:
                    # Re-run diagnosis with enhanced context
                    logger.info("Re-running diagnosis with enhanced context...")
                    diagnosis_input['diagnostic_context'] = additional_context
                    diagnosis = self._diagnose_with_claude(diagnosis_input)

            self.state.diagnoses.append(diagnosis)

            # Log diagnosis
            logger.info(f"Diagnosis complete:")
            logger.info(f"  Failing targets: {diagnosis.get('failing_targets', [])}")
            logger.info(f"  Likely causes: {len(diagnosis.get('likely_causes', []))}")
            logger.info(f"  Confidence: {diagnosis.get('confidence', 0):.2f}")

            # Log to phase logger
            log_path = None
            if self._phase_logger:
                try:
                    self._phase_logger.set_iteration_context(
                        calibration_round=self.state.calibration_round,
                        iteration=self.state.iteration,
                        experiment_count=self.state.experiment_count,
                        skip_testing_count=self.state.skip_testing_count
                    )
                    # Collect figure paths from diagnostic data
                    fig_paths = []
                    if diagnostic_data and hasattr(diagnostic_data, 'figure_paths'):
                        fig_paths = diagnostic_data.figure_paths

                    log_path = self._phase_logger.log_diagnosis(
                        title="Diagnosis",
                        failing_targets=diagnosis.get('failing_targets', []),
                        likely_causes=diagnosis.get('likely_causes', []),
                        ai_reasoning=diagnosis.get('reasoning', ''),
                        parameter_recommendations=diagnosis.get('parameter_recommendations', []),
                        cross_pft_conflicts=diagnosis.get('cross_pft_conflicts', []),
                        confidence=diagnosis.get('confidence', 0),
                        context_used={
                            'memory': self._memory is not None,
                            'rag': self.reasoning.rag_retriever is not None if self.reasoning else False,
                            'experiments': len(self.state.experiments) > 0
                        },
                        figure_paths=fig_paths if fig_paths else None,
                        metadata={
                            'iteration': self.state.iteration,
                            'screening_data_summary': {
                                'best_case': self.state.screening_data.get('best_case', {}),
                                'n_cases': self.state.screening_data.get('n_cases_evaluated', 0)
                            }
                        }
                    )
                    logger.info(f"  Phase log written: {log_path}")
                except Exception as e:
                    logger.warning(f"Could not write diagnosis log: {e}")

        # Human review checkpoint
        # During skip-testing, auto-continue by default (no interactive prompt)
        in_skip_testing = self.state.skip_testing_count > 0
        auto_continue = in_skip_testing and self.config.auto_skip_testing

        if self.config.human_review and not auto_continue:
            # Build skip-testing context header if in skip-testing loop
            skip_header = ""
            if in_skip_testing:
                last_test = self.state.hypothesis_tests[-1] if self.state.hypothesis_tests else {}
                last_confidence = last_test.get('confidence', 0)
                last_supported = last_test.get('hypothesis_supported', None)
                skip_header = (
                    f"\n  [Skip Testing Cycle {self.state.skip_testing_count}/{self.config.max_skip_testing}]"
                    f"\n  Last hypothesis: {'SUPPORTED' if last_supported else 'NOT SUPPORTED'}"
                    f" (confidence: {last_confidence:.2f}, threshold: {self.config.hypothesis_confidence_threshold})"
                    f"\n  Cumulative insights: {len(self.state.cumulative_insights)} findings accumulated"
                    f"\n"
                )

            self._human_review_checkpoint(
                phase="DIAGNOSIS",
                summary=f"""
Diagnosis Summary:{skip_header}
  - Iteration: {self.state.iteration} (experiment: {self.state.experiment_count}, skip-test: {self.state.skip_testing_count})
  - Failing targets: {diagnosis.get('failing_targets', ['unknown'])}
  - Likely causes: {len(diagnosis.get('likely_causes', []))}
  - Confidence: {diagnosis.get('confidence', 0):.2f}
  - Parameter recommendations: {len(diagnosis.get('parameter_recommendations', []))}
""",
                next_phase="HYPOTHESIS",
                options={
                    'c': 'Continue to hypothesis generation',
                    'r': 'Re-run diagnosis with different settings',
                    'q': 'Quit workflow (state saved)',
                }
            )
        elif auto_continue:
            # Log summary without blocking
            last_test = self.state.hypothesis_tests[-1] if self.state.hypothesis_tests else {}
            logger.info(f"[Auto Skip Testing {self.state.skip_testing_count}/{self.config.max_skip_testing}] "
                       f"Diagnosis complete → auto-continuing to hypothesis")
            logger.info(f"  Failing: {diagnosis.get('failing_targets', ['unknown'])}")
            logger.info(f"  Causes: {len(diagnosis.get('likely_causes', []))}, "
                       f"Confidence: {diagnosis.get('confidence', 0):.2f}")

        # Transition to HYPOTHESIS
        self.state.record_phase_transition(
            Phase.DIAGNOSIS.value, Phase.HYPOTHESIS.value,
            f"Identified {len(diagnosis.get('likely_causes', []))} likely causes"
        )
        self.state.current_phase = Phase.HYPOTHESIS.value
        logger.info("Diagnosis complete. Advancing to HYPOTHESIS.")

    def _diagnose_with_claude(self, diagnosis_input: Dict) -> Dict:
        """Use Claude API for diagnosis with diagnostic script context."""
        try:
            # Enrich results with diagnostic data if available
            results = diagnosis_input["screening_results"].copy()
            diagnostic_data = diagnosis_input.get("diagnostic_data")

            if diagnostic_data:
                # Add diagnostic context to results for AI reasoning
                results["diagnostic_context"] = {
                    "parameters": diagnostic_data.parameters if hasattr(diagnostic_data, 'parameters') else {},
                    "edge_summary": diagnostic_data.edge_summary if hasattr(diagnostic_data, 'edge_summary') else "",
                    "redesign_candidates": diagnostic_data.redesign_candidates if hasattr(diagnostic_data, 'redesign_candidates') else [],
                    "target_summary": diagnostic_data.target_summary if hasattr(diagnostic_data, 'target_summary') else "",
                    "pft_summary": diagnostic_data.pft_summary if hasattr(diagnostic_data, 'pft_summary') else "",
                    "combined_summary": diagnostic_data.get_ai_context() if hasattr(diagnostic_data, 'get_ai_context') else ""
                }
                logger.info("Added diagnostic context to Claude reasoning")

            # Check for additional diagnostic context from requested diagnostics
            additional_context = diagnosis_input.get("diagnostic_context")
            if additional_context:
                # Merge with existing diagnostic context
                if "diagnostic_context" not in results:
                    results["diagnostic_context"] = {}
                results["diagnostic_context"]["requested_diagnostics_results"] = additional_context
                if additional_context.get('_combined_summary'):
                    results["diagnostic_context"]["additional_analysis"] = additional_context['_combined_summary']
                logger.info("Added requested diagnostics context to Claude reasoning")

            # Add hypothesis test results from Skip Testing path
            hypothesis_tests = diagnosis_input.get("hypothesis_tests", [])
            if hypothesis_tests:
                results["hypothesis_test_results"] = hypothesis_tests
                logger.info(f"Added {len(hypothesis_tests)} hypothesis test results to Claude reasoning")

            # Add previous hypotheses for context
            previous_hypotheses = diagnosis_input.get("previous_hypotheses", [])
            if previous_hypotheses:
                results["previous_hypotheses"] = previous_hypotheses
                logger.info(f"Added {len(previous_hypotheses)} previous hypotheses to Claude reasoning")

            # Add cumulative insights from skip-testing cycles for cross-cycle synthesis
            cumulative_insights = diagnosis_input.get("cumulative_insights", [])
            if cumulative_insights:
                # Build a structured summary for AI consumption
                insights_summary = []
                for ins in cumulative_insights:
                    insights_summary.append({
                        'cycle': ins.get('cycle'),
                        'hypothesis': ins.get('hypothesis_name'),
                        'supported': ins.get('hypothesis_supported'),
                        'confidence': ins.get('confidence'),
                        'parameters_tested': ins.get('parameters_tested', []),
                        'key_insights': ins.get('key_insights', ''),
                    })
                results["cumulative_skip_testing_insights"] = {
                    'total_cycles': len(cumulative_insights),
                    'insights': insights_summary,
                    'instruction': (
                        "IMPORTANT: These are accumulated findings from previous skip-testing cycles. "
                        "Build on these insights rather than repeating the same analyses. "
                        "Identify patterns across cycles, refine hypotheses based on what was "
                        "supported/rejected, and propose NEW directions not yet explored."
                    )
                }
                logger.info(f"Added {len(cumulative_insights)} cumulative insights to Claude reasoning")

            diagnosis = self.reasoning.diagnose(
                results=results,
                targets=diagnosis_input["targets"],
                sensitivity_rankings=diagnosis_input["sensitivity_rankings"],
                iteration=diagnosis_input["iteration"]
            )
            return asdict(diagnosis) if hasattr(diagnosis, '__dict__') else diagnosis
        except Exception as e:
            logger.error(f"Claude diagnosis failed: {e}")
            return self._diagnose_rule_based(diagnosis_input)

    def _diagnose_rule_based(self, diagnosis_input: Dict) -> Dict:
        """Rule-based diagnosis when Claude API unavailable."""
        # Based on known findings from December 2025 analysis
        return {
            "iteration": diagnosis_input["iteration"],
            "failing_targets": ["froot_pft10", "leaf_pft10"],
            "likely_causes": [
                "P STARVATION: PFT#10 P uptake/demand ≈ 0.000005 (essentially zero)",
                "Light competition: PFT#9 GPP is 5-10× higher than PFT#10",
                "Excessive turnover: Default 1.0 yr vs 5.0 yr realistic for Arctic",
                "Root distribution: Parameters BACKWARDS (graminoids should be deepest)"
            ],
            "parameter_recommendations": [
                {"parameter": "fates_turnover_fnrt_10", "direction": "increase", "priority": 1},
                {"parameter": "fates_allom_fnrt_prof_a_10", "direction": "decrease", "priority": 2},
                {"parameter": "fates_allom_fnrt_prof_b_10", "direction": "decrease", "priority": 3}
            ],
            "cross_pft_conflicts": [
                "ECA competition: PFT#9 outcompetes PFT#10 for soil P",
                "Shared phenology parameters affect all PFTs differently"
            ],
            "confidence": 0.85,
            "reasoning": "Based on comprehensive Dec 2025 diagnostic analysis identifying triple bottleneck"
        }

    def _run_diagnostic_scripts(self, screening_data: Dict) -> Optional['DiagnosisResult']:
        """
        Run Phase 3 diagnostic scripts to gather actual data.

        This method calls the diagnosis scripts to:
        1. Read actual parameter values for the best case
        2. Check which parameters are at sampling bounds
        3. Compare best case with other top cases
        4. Run PFT-specific diagnostics (if NC file available)

        Args:
            screening_data: Screening results from Phase 2

        Returns:
            DiagnosisResult with parameter values, edge analysis, etc.
            Returns None if diagnostic tools unavailable or fail.
        """
        if not HAS_DIAGNOSIS_TOOLS:
            logger.warning("Diagnosis tools not available")
            return None

        try:
            from tools.config import config as a2mc_config

            # Get paths from config
            morris_file = a2mc_config.ENSEMBLE_MATRIX_FILE
            param_names_file = a2mc_config.PARAM_LIST_FILE
            param_bounds_file = a2mc_config.SALIB_PROBLEM_FILE

            # Validate paths exist
            if not morris_file or not Path(morris_file).exists():
                logger.warning(f"Morris file not found: {morris_file}")
                return None
            if not param_names_file or not Path(param_names_file).exists():
                logger.warning(f"Param names file not found: {param_names_file}")
                return None

            # Get PFT IDs from config or use defaults
            pft_ids = []
            pft_str = os.environ.get('A2MC_PFTS', '7,9,10')
            if pft_str:
                pft_ids = [int(p.strip()) for p in pft_str.split(',')]

            # Get targets from config, falling back to screening targets
            targets = None
            if hasattr(self.config.targets, 'biomass'):
                targets = asdict(self.config.targets).get('biomass', {})
            if not targets:
                # Build targets dict from screening module's target definitions
                try:
                    from phases.phase2_screening.screen_ensemble import load_kougarok_targets
                    screening_targets = load_kougarok_targets()
                    # Convert {PFT7_leaf: Target(...)} -> {PFT7: {leaf: obs_val}}
                    targets = {}
                    for tname, tobj in screening_targets.items():
                        parts = tname.split('_', 1)  # e.g. 'PFT7_leaf' -> ['PFT7', 'leaf']
                        if len(parts) == 2:
                            pft_key, var_name = parts
                            if pft_key not in targets:
                                targets[pft_key] = {}
                            targets[pft_key][var_name] = tobj.observed
                    if targets:
                        logger.info(f"Loaded {sum(len(v) for v in targets.values())} targets from screening module")
                except Exception as e:
                    logger.warning(f"Could not load screening targets: {e}")

            # Get NC file path for best case (if available)
            nc_file = None
            best_case = screening_data.get('best_case', {})
            if best_case:
                # Try to construct NC file path
                case_id = best_case.get('case_id', best_case.get('case_num'))
                if case_id:
                    extracted_dir = a2mc_config.EXTRACTED_DATA
                    if extracted_dir and Path(extracted_dir).exists():
                        # Look for extracted NC file
                        pattern = f"*En{case_id}_*all_variables*.nc"
                        nc_files = list(Path(extracted_dir).glob(pattern))
                        if nc_files:
                            nc_file = str(nc_files[0])
                            logger.info(f"Found NC file for case {case_id}: {nc_file}")

            # Compute plot output directory (phase_results, not logs)
            plot_output_dir = None
            plot_filename_prefix = ""
            if a2mc_config.USE_CASE_DIR:
                plot_output_dir = str(
                    Path(a2mc_config.USE_CASE_DIR) / "memory" / "phase_results" / "phase3_diagnosis"
                )
                # Build filename prefix from iteration context
                rr = self.state.calibration_round if hasattr(self.state, 'calibration_round') else 1
                ee = self.state.experiment_count if hasattr(self.state, 'experiment_count') else 0
                sc = self.state.skip_testing_count if hasattr(self.state, 'skip_testing_count') else 0
                ii = sc + 1  # 1-based inner loop counter
                plot_filename_prefix = f"r{rr:02d}_exp{ee:02d}_iter{ii:02d}_"

            # Run diagnosis
            result = run_diagnosis_for_orchestrator(
                screening_data=screening_data,
                morris_file=morris_file,
                param_names_file=param_names_file,
                param_bounds_file=param_bounds_file if param_bounds_file and Path(param_bounds_file).exists() else None,
                nc_file=nc_file,
                targets=targets,
                pft_ids=pft_ids,
                top_cases_for_comparison=5,
                plot_output_dir=plot_output_dir,
                plot_filename_prefix=plot_filename_prefix,
                verbose=True
            )

            return result

        except Exception as e:
            logger.error(f"Error running diagnostic scripts: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _execute_requested_diagnostics(
        self,
        requested_diagnostics: List[Dict],
        screening_data: Dict
    ) -> Optional[Dict]:
        """
        Execute diagnostic analyses requested by Claude AI.

        This enables a two-phase diagnosis where Claude first analyzes
        available data, then requests specific diagnostics for deeper insight.

        Args:
            requested_diagnostics: List of diagnostic requests from Claude
                [{"tool": "check_edge_parameters", "reason": "...", "priority": "high", "args": {...}}]
            screening_data: Screening results from Phase 2

        Returns:
            Dict with combined diagnostic results, or None if all fail
        """
        if not HAS_DIAGNOSIS_TOOLS:
            logger.warning("Diagnostic tools not available for requested analyses")
            return None

        # Import all diagnostic tools
        try:
            from phases.phase3_diagnosis import (
                # Parameter analysis
                check_parameters_at_edge,
                compare_cases,
                read_case_parameters,
                get_edge_summary_for_ai,
                get_comparison_summary_for_ai,
                # PFT limitation
                run_pft_diagnosis,
                analyze_allocation_dynamics,
                analyze_nutrient_limitation,
                analyze_light_competition,
                get_diagnosis_summary_for_ai,
                # Mortality & collapse
                diagnose_mortality_causes,
                detect_vegetation_collapse,
                extract_vegc_timeseries,
                detect_perfect_storm_pattern,
                get_mortality_summary_for_ai,
                get_collapse_summary_for_ai,
                # Nutrient pools
                analyze_nutrient_depletion,
                compare_uptake_vs_demand,
                extract_p_pools,
                extract_n_pools,
                get_nutrient_summary_for_ai,
                # Nutrient mass balance
                extract_nutrient_budget,
                calculate_budget_closure,
                analyze_pft_competition,
                identify_nutrient_sinks,
                get_balance_summary_for_ai,
                # Target comparison
                compare_biomass_targets,
                calculate_target_metrics,
                get_target_summary_for_ai,
                # Carbon balance
                analyze_carbon_balance,
                detect_carbon_bottleneck,
                get_carbon_summary_for_ai,
                # Hypothesis testing
                test_hypotheses,
                test_single_hypothesis,
                get_hypothesis_summary_for_ai,
            )
            from tools.config import config as a2mc_config
        except ImportError as e:
            logger.error(f"Could not import diagnostic tools: {e}")
            return None

        results = {}
        summaries = []

        # Resolve NC file for best case (needed by many tools)
        nc_file = None
        best_case = screening_data.get('best_case', {})
        case_id = None
        if best_case:
            case_id = best_case.get('case_id', best_case.get('case_num'))
            if case_id:
                extracted_dir = a2mc_config.EXTRACTED_DATA
                if extracted_dir and Path(extracted_dir).exists():
                    pattern = f"*En{case_id}_*all_variables*.nc"
                    nc_files_found = list(Path(extracted_dir).glob(pattern))
                    if nc_files_found:
                        nc_file = str(nc_files_found[0])

        # Get PFT IDs from config
        pft_str = os.environ.get('A2MC_PFTS', '7,9,10')
        pft_ids = [int(p.strip()) for p in pft_str.split(',')]

        # Sort by priority (high first)
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        sorted_requests = sorted(
            requested_diagnostics,
            key=lambda x: priority_order.get(x.get('priority', 'medium'), 1)
        )

        for request in sorted_requests:
            tool = request.get('tool', '')
            reason = request.get('reason', '')
            tool_args = request.get('args', {})
            priority = request.get('priority', 'medium')

            logger.info(f"Running requested diagnostic: {tool} (priority: {priority})")
            logger.info(f"  Reason: {reason}")

            try:
                # ===== Parameter Analysis =====
                if tool == 'check_edge_parameters':
                    target_case = int(tool_args.get('case_id', case_id or 2678))
                    edge_result = check_parameters_at_edge(
                        case_id=target_case,
                        morris_file=a2mc_config.ENSEMBLE_MATRIX_FILE,
                        param_names=a2mc_config.PARAM_LIST_FILE,
                        param_bounds=a2mc_config.SALIB_PROBLEM_FILE,
                        threshold_pct=tool_args.get('threshold_pct', 1.0)
                    )
                    results['edge_parameters'] = edge_result
                    summaries.append(f"## Edge Parameters Analysis\n{get_edge_summary_for_ai(edge_result)}")

                elif tool == 'compare_case_parameters':
                    case1_id = int(tool_args.get('case1_id', case_id or 2678))
                    case2_id = tool_args.get('case2_id', None)
                    if not case2_id:
                        best_cases = screening_data.get('best_cases', [])
                        if len(best_cases) > 1:
                            case2_id = int(best_cases[-1].get('case_id', best_cases[-1].get('case_num', 1)))
                    if case2_id:
                        comparison = compare_cases(
                            case1_id=case1_id,
                            case2_id=int(case2_id),
                            morris_file=a2mc_config.ENSEMBLE_MATRIX_FILE,
                            param_names=a2mc_config.PARAM_LIST_FILE,
                            param_bounds=a2mc_config.SALIB_PROBLEM_FILE,
                            top_n=tool_args.get('top_n', 20)
                        )
                        results['case_comparison'] = comparison
                        summaries.append(f"## Case Comparison\n{get_comparison_summary_for_ai(comparison)}")

                elif tool == 'read_case_parameters':
                    target_case = int(tool_args.get('case_id', case_id or 2678))
                    params = read_case_parameters(
                        case_id=target_case,
                        morris_file=a2mc_config.ENSEMBLE_MATRIX_FILE,
                        param_names=a2mc_config.PARAM_LIST_FILE or None,
                        param_bounds=a2mc_config.SALIB_PROBLEM_FILE or None
                    )
                    results['case_parameters'] = params
                    summaries.append(f"## Case {target_case} Parameters\nRead {len(params)} parameters")

                # ===== PFT Limitation Analysis (require NC file) =====
                elif tool in ('diagnose_pft_limitations', 'analyze_allocation_dynamics',
                              'analyze_nutrient_limitation', 'analyze_light_competition'):
                    if not nc_file:
                        logger.warning(f"  {tool} requires NC file - not available")
                        results[f'{tool}_skipped'] = {'status': 'nc_file_not_available'}
                    else:
                        pft_id = tool_args.get('pft_id', pft_ids[0] if pft_ids else 10)
                        # run_pft_diagnosis covers all sub-analyses for a single PFT
                        if tool == 'diagnose_pft_limitations':
                            req_pft_ids = tool_args.get('pft_ids', pft_ids)
                            combined_summaries = {}
                            for pid in req_pft_ids:
                                pft_result = run_pft_diagnosis(
                                    nc_file=nc_file, pft_id=pid, targets=tool_args.get('targets', {})
                                )
                                combined_summaries[f'pft{pid}'] = get_diagnosis_summary_for_ai(pft_result)
                            results['pft_diagnosis'] = combined_summaries
                            summaries.append(f"## PFT Limitation Diagnosis\n" +
                                           "\n".join(f"PFT#{p}: {s}" for p, s in combined_summaries.items()))
                        else:
                            pft_result = run_pft_diagnosis(
                                nc_file=nc_file, pft_id=pft_id, targets=tool_args.get('targets', {})
                            )
                            label = {'analyze_allocation_dynamics': 'Allocation Dynamics',
                                     'analyze_nutrient_limitation': 'Nutrient Limitation',
                                     'analyze_light_competition': 'Light Competition'}[tool]
                            pft_summary = get_diagnosis_summary_for_ai(pft_result)
                            results[tool] = pft_summary
                            summaries.append(f"## {label} (PFT#{pft_id})\n{pft_summary}")

                # ===== Mortality & Collapse (require NC file) =====
                elif tool in ('analyze_mortality', 'detect_collapse', 'detect_perfect_storm_pattern'):
                    if not nc_file:
                        logger.warning(f"  {tool} requires NC file - not available")
                        results[f'{tool}_skipped'] = {'status': 'nc_file_not_available'}
                    else:
                        from phases.phase3_diagnosis import extract_mortality_timeseries
                        data_files = {'trans': nc_file}

                        if tool == 'analyze_mortality':
                            mort_pft_ids = tool_args.get('pft_ids', pft_ids)
                            mort_data = extract_mortality_timeseries(
                                data_files=data_files, pft_ids=mort_pft_ids
                            )
                            # Diagnose each PFT
                            mort_results = {}
                            for pid in mort_pft_ids:
                                mort_results[f'pft{pid}'] = diagnose_mortality_causes(
                                    mortality_data=mort_data, pft_id=pid
                                )
                            results['mortality'] = mort_results
                            summaries.append(f"## Mortality Analysis\n{get_mortality_summary_for_ai(mort_results, mort_pft_ids)}")
                        elif tool == 'detect_collapse':
                            vegc_data = extract_vegc_timeseries(
                                data_files=data_files, pft_ids=tool_args.get('pft_ids', pft_ids)
                            )
                            # detect_vegetation_collapse needs vegc array and time array
                            # Use vegc_data dict which contains per-PFT time series
                            collapse_summary = f"Extracted vegc timeseries for {len(vegc_data.get('phases', {}))} phases, {len(vegc_data.get('pft_data', {}))} PFTs"
                            results['collapse'] = collapse_summary
                            summaries.append(f"## Collapse Detection\n{collapse_summary}")
                        elif tool == 'detect_perfect_storm_pattern':
                            vegc_data = extract_vegc_timeseries(
                                data_files=data_files, pft_ids=tool_args.get('pft_ids', pft_ids)
                            )
                            storm_result = detect_perfect_storm_pattern(
                                vegc_data=vegc_data,
                                pft_id=tool_args.get('pft_id', pft_ids[0] if pft_ids else 10)
                            )
                            storm_summary = str(storm_result)[:500]
                            results['perfect_storm'] = storm_summary
                            summaries.append(f"## Perfect Storm Pattern\n{storm_summary}")

                # ===== Nutrient Pool Analysis (require NC file) =====
                elif tool in ('analyze_nutrient_pools', 'compare_uptake_vs_demand',
                              'extract_p_pools', 'extract_n_pools'):
                    if not nc_file:
                        logger.warning(f"  {tool} requires NC file - not available")
                        results[f'{tool}_skipped'] = {'status': 'nc_file_not_available'}
                    else:
                        data_files = {'trans': nc_file}
                        if tool == 'analyze_nutrient_pools':
                            # Extract pools first, then analyze depletion
                            p_pools = extract_p_pools(data_files=data_files)
                            depletion = analyze_nutrient_depletion(pool_data=p_pools)
                            nutrient_summary = get_nutrient_summary_for_ai(p_pools, depletion, {})
                            results['nutrient_pools'] = nutrient_summary
                            summaries.append(f"## Nutrient Pool Analysis\n{nutrient_summary}")
                        elif tool == 'compare_uptake_vs_demand':
                            pft_id = tool_args.get('pft_id', pft_ids[0] if pft_ids else 10)
                            nutrient = tool_args.get('nutrient', 'P')
                            uptake_result = compare_uptake_vs_demand(
                                nc_file=nc_file, pft_id=pft_id, nutrient=nutrient
                            )
                            uptake_summary = str(uptake_result)[:500]
                            results['uptake_vs_demand'] = uptake_summary
                            summaries.append(f"## Uptake vs Demand (PFT#{pft_id}, {nutrient})\n{uptake_summary}")
                        elif tool == 'extract_p_pools':
                            p_result = extract_p_pools(data_files=data_files)
                            results['p_pools'] = f"Extracted {len(p_result.get('pools', {}))} P pool variables"
                            summaries.append(f"## P Pool Data\nExtracted {len(p_result.get('pools', {}))} P pool variables")
                        elif tool == 'extract_n_pools':
                            n_result = extract_n_pools(data_files=data_files)
                            results['n_pools'] = f"Extracted {len(n_result.get('pools', {}))} N pool variables"
                            summaries.append(f"## N Pool Data\nExtracted {len(n_result.get('pools', {}))} N pool variables")

                # ===== Nutrient Mass Balance (require NC file) =====
                elif tool in ('extract_nutrient_budget', 'calculate_budget_closure',
                              'analyze_pft_competition', 'identify_nutrient_sinks'):
                    if not nc_file:
                        logger.warning(f"  {tool} requires NC file - not available")
                        results[f'{tool}_skipped'] = {'status': 'nc_file_not_available'}
                    else:
                        nutrient = tool_args.get('nutrient', 'P')
                        if tool == 'extract_nutrient_budget':
                            budget = extract_nutrient_budget(
                                nc_file=nc_file, nutrient=nutrient,
                                pft_ids=tool_args.get('pft_ids', pft_ids)
                            )
                            budget_summary = get_balance_summary_for_ai(budget)
                            results['nutrient_budget'] = budget_summary
                            summaries.append(f"## {nutrient} Budget\n{budget_summary}")
                        elif tool == 'calculate_budget_closure':
                            budget = extract_nutrient_budget(
                                nc_file=nc_file, nutrient=nutrient,
                                pft_ids=tool_args.get('pft_ids', pft_ids)
                            )
                            closure = calculate_budget_closure(budget)
                            closure_summary = str(closure)[:500]
                            results['budget_closure'] = closure_summary
                            summaries.append(f"## {nutrient} Budget Closure\n{closure_summary}")
                        elif tool == 'analyze_pft_competition':
                            competition = analyze_pft_competition(
                                nc_file=nc_file, pft_ids=pft_ids, nutrient=nutrient
                            )
                            competition_summary = str(competition)[:500]
                            results['pft_competition'] = competition_summary
                            summaries.append(f"## PFT {nutrient} Competition\n{competition_summary}")
                        elif tool == 'identify_nutrient_sinks':
                            budget = extract_nutrient_budget(
                                nc_file=nc_file, nutrient=nutrient,
                                pft_ids=tool_args.get('pft_ids', pft_ids)
                            )
                            sinks = identify_nutrient_sinks(budget)
                            sinks_summary = str(sinks)[:500]
                            results['nutrient_sinks'] = sinks_summary
                            summaries.append(f"## {nutrient} Sinks\n{sinks_summary}")

                # ===== Target Comparison (require NC file) =====
                elif tool in ('compare_biomass_targets', 'calculate_target_metrics'):
                    if not nc_file:
                        logger.warning(f"  {tool} requires NC file - not available")
                        results[f'{tool}_skipped'] = {'status': 'nc_file_not_available'}
                    else:
                        if tool == 'compare_biomass_targets':
                            targets_dict = tool_args.get('targets', {})
                            target_result = compare_biomass_targets(
                                nc_file=nc_file, targets=targets_dict,
                                pft_ids=tool_args.get('pft_ids', pft_ids)
                            )
                            target_summary = get_target_summary_for_ai(target_result)
                            results['target_comparison'] = target_summary
                            summaries.append(f"## Target Comparison\n{target_summary}")
                        elif tool == 'calculate_target_metrics':
                            # Needs extracted data dict - use compare_biomass_targets first
                            target_result = compare_biomass_targets(
                                nc_file=nc_file, targets=tool_args.get('targets', {}),
                                pft_ids=tool_args.get('pft_ids', pft_ids)
                            )
                            metrics_summary = get_target_summary_for_ai(target_result)
                            results['target_metrics'] = metrics_summary
                            summaries.append(f"## Target Metrics\n{metrics_summary}")

                # ===== Carbon Balance (require NC file) =====
                elif tool in ('analyze_carbon_balance', 'detect_carbon_bottleneck'):
                    if not nc_file:
                        logger.warning(f"  {tool} requires NC file - not available")
                        results[f'{tool}_skipped'] = {'status': 'nc_file_not_available'}
                    else:
                        try:
                            import pandas as pd
                            import netCDF4 as nc4
                            # Load data into DataFrame for carbon balance tools
                            ds = nc4.Dataset(nc_file)
                            data_dict = {}
                            for var in ['FATES_GPP', 'FATES_AUTORESP', 'FATES_MAINT_RESP',
                                       'FATES_GROWTH_RESP', 'FATES_NPP']:
                                if var in ds.variables:
                                    data_dict[var] = ds.variables[var][:].flatten()
                            n_timesteps = len(data_dict.get('FATES_GPP', []))
                            ds.close()

                            # Derive year and doy from monthly time index
                            # Extracted NC files have 12 months/year starting from START_YEAR
                            start_year = int(os.environ.get('A2MC_TRANS_START_YEAR', '1901'))
                            mid_month_doy = [16, 46, 75, 106, 136, 167, 197, 228, 259, 289, 320, 350]
                            years = []
                            doys = []
                            for t in range(n_timesteps):
                                years.append(start_year + t // 12)
                                doys.append(mid_month_doy[t % 12])
                            data_dict['year'] = years
                            data_dict['doy'] = doys
                            df = pd.DataFrame(data_dict)

                            if tool == 'analyze_carbon_balance':
                                carbon_result = analyze_carbon_balance(data=df)
                                carbon_summary = get_carbon_summary_for_ai(carbon_result)
                                results['carbon_balance'] = carbon_summary
                                summaries.append(f"## Carbon Balance\n{carbon_summary}")
                            elif tool == 'detect_carbon_bottleneck':
                                bottleneck = detect_carbon_bottleneck(data=df)
                                bottleneck_summary = str(bottleneck)[:500]
                                results['carbon_bottleneck'] = bottleneck_summary
                                summaries.append(f"## Carbon Bottleneck\n{bottleneck_summary}")
                        except Exception as e:
                            logger.warning(f"  Carbon balance analysis failed: {e}")
                            results[f'{tool}_error'] = {'error': str(e)}

                # ===== Hypothesis Testing (require NC file) =====
                elif tool in ('test_hypotheses', 'test_single_hypothesis'):
                    if not nc_file:
                        logger.warning(f"  {tool} requires NC file - not available")
                        results[f'{tool}_skipped'] = {'status': 'nc_file_not_available'}
                    else:
                        try:
                            import pandas as pd
                            import netCDF4 as nc4
                            ds = nc4.Dataset(nc_file)
                            data_dict = {}
                            n_szpf_size_classes = 13
                            for var in ds.variables:
                                try:
                                    v = ds.variables[var]
                                    dims = v.dimensions
                                    if v.ndim == 1 and 'time' in str(dims):
                                        # 1D site-level: include directly
                                        data_dict[var] = v[:]
                                    elif v.ndim == 2 and 'time' in str(dims):
                                        arr = v[:]
                                        second_dim_size = arr.shape[1]
                                        if second_dim_size == 12:
                                            # PFT-level (time, fates_levpft): extract per PFT
                                            for pid in pft_ids:
                                                idx = pid - 1  # 0-based
                                                data_dict[f"{var}_PFT{pid}"] = arr[:, idx]
                                        elif second_dim_size == 156:
                                            # SZPF-level (time, fates_levscpf): sum by PFT
                                            for pid in pft_ids:
                                                start = (pid - 1) * n_szpf_size_classes
                                                end = start + n_szpf_size_classes
                                                data_dict[f"{var}_PFT{pid}"] = np.nansum(arr[:, start:end], axis=1)
                                except Exception:
                                    pass
                            # Add day-of-year column from time variable
                            if 'time' in ds.variables:
                                try:
                                    import cftime
                                    times = nc4.num2date(ds.variables['time'][:],
                                                         ds.variables['time'].units,
                                                         ds.variables['time'].calendar)
                                    data_dict['doy'] = np.array([t.timetuple().tm_yday for t in times])
                                except Exception:
                                    n_time = len(ds.variables['time'][:])
                                    # Fallback: assume monthly data, assign mid-month DOY
                                    monthly_doy = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349]
                                    data_dict['doy'] = np.array([monthly_doy[i % 12] for i in range(n_time)])
                            ds.close()
                            df = pd.DataFrame(data_dict)

                            hyp_result = test_hypotheses(
                                data=df,
                                pft_id=tool_args.get('pft_id', pft_ids[0] if pft_ids else 10)
                            )
                            hyp_summary = get_hypothesis_summary_for_ai(hyp_result)
                            results['hypothesis_tests'] = hyp_summary
                            summaries.append(f"## Hypothesis Tests\n{hyp_summary}")
                        except Exception as e:
                            logger.warning(f"  Hypothesis testing failed: {e}")
                            results[f'{tool}_error'] = {'error': str(e)}

                # ===== Ensemble Visualization =====
                elif tool == 'plot_ensemble_biomass':
                    try:
                        from phases.phase2_screening.plot_screening import (
                            plot_ensemble_biomass_from_dir
                        )
                        extracted_dir = a2mc_config.EXTRACTED_DATA
                        if extracted_dir and Path(extracted_dir).exists():
                            # Build simple targets dict
                            simple_targets = {}
                            for tc in screening_data.get('best_cases', []):
                                pass  # targets come from config
                            # Load targets from screening module
                            try:
                                from phases.phase2_screening.screen_ensemble import load_kougarok_targets
                                raw_targets = load_kougarok_targets()
                                simple_targets = {
                                    name: {'observed': t.observed, 'uncertainty': t.uncertainty}
                                    for name, t in raw_targets.items()
                                }
                            except Exception:
                                simple_targets = tool_args.get('targets', {})
                            # Determine output path
                            fig_dir = None
                            if self._phase_logger:
                                fig_dir = self._phase_logger._get_phase_dir(3)
                            if not fig_dir:
                                fig_dir = Path(extracted_dir)
                            fig_path = plot_ensemble_biomass_from_dir(
                                data_dir=extracted_dir,
                                targets=simple_targets,
                                pft_ids=pft_ids,
                                output_path=str(Path(fig_dir) / 'ensemble_biomass_top_cases.png'),
                                top_n=tool_args.get('top_n', 100),
                            )
                            if fig_path:
                                results['ensemble_biomass_figure'] = fig_path
                                summaries.append(f"## Ensemble Biomass Figure\nSaved: {fig_path}")
                        else:
                            logger.warning("  plot_ensemble_biomass: extracted data dir not available")
                    except Exception as e:
                        logger.warning(f"  plot_ensemble_biomass failed: {e}")
                        results[f'{tool}_error'] = {'error': str(e)}

                # ---- Ensemble-level hypothesis tests ----
                elif tool in ('test_p_limitation_cascade', 'test_root_turnover_impact'):
                    try:
                        from phases.phase3_diagnosis import (
                            test_p_limitation_cascade,
                            test_root_turnover_impact,
                        )
                        from phases.phase4_hypothesis.test_with_existing_data import (
                            load_morris_ensemble_data,
                            get_morris_param_names,
                        )
                        test_fn = {
                            'test_p_limitation_cascade': test_p_limitation_cascade,
                            'test_root_turnover_impact': test_root_turnover_impact,
                        }[tool]
                        param_matrix, y_outputs = load_morris_ensemble_data(self.config)
                        param_names = get_morris_param_names(self.config)
                        test_config = {
                            'param_names': param_names,
                            'pft_ids': pft_ids,
                            'use_case_dir': str(a2mc_config.USE_CASE_DIR),
                        }
                        result = test_fn(param_matrix, y_outputs, screening_data, test_config)
                        # Format as text summary
                        lines = [f"Supported: {result.get('supported', False)}",
                                 f"Confidence: {result.get('confidence', 0.0):.2f}"]
                        for insight in result.get('insights', []):
                            lines.append(f"  - {insight}")
                        summary_text = "\n".join(lines)
                        results[tool] = summary_text
                        summaries.append(f"## {tool}\n{summary_text}")
                    except Exception as e:
                        logger.warning(f"  {tool} failed: {e}")
                        results[f'{tool}_error'] = {'error': str(e)}

                else:
                    logger.warning(f"  Unknown diagnostic tool: {tool}")
                    results[f'{tool}_unknown'] = {'status': 'unknown_tool'}

            except Exception as e:
                logger.error(f"  Diagnostic {tool} failed: {e}")
                import traceback
                traceback.print_exc()
                results[f'{tool}_error'] = {'error': str(e)}

        # Combine summaries for AI context
        if summaries:
            results['_combined_summary'] = "\n\n".join(summaries)
            logger.info(f"Completed {len(summaries)} diagnostic analyses with summaries")
            return results

        if results:
            logger.info(f"Completed {len(results)} diagnostics (no AI summaries generated)")
            return results

        return None

    # =========================================================================
    # PHASE 4: HYPOTHESIS - Experimental Design
    # =========================================================================
    def _run_hypothesis(self):
        """
        Phase 4: Generate testable hypotheses with experimental designs.

        This method keeps loop control logic (skip testing inner loop,
        phase transitions) while delegating analysis to phase scripts:
        - phases/phase4_hypothesis/generate_hypothesis.py
        - phases/phase4_hypothesis/test_with_existing_data.py
        """
        from phases.phase4_hypothesis import (
            run_hypothesis_generation,
            test_hypothesis_with_existing_data,
        )

        latest_diagnosis = self.state.diagnoses[-1] if self.state.diagnoses else {}

        # Generate hypothesis (delegates to phase script)
        hypothesis = run_hypothesis_generation(
            diagnosis=latest_diagnosis,
            reasoning_module=self.reasoning,
            exploration_data=self.state.exploration_data,
            previous_experiments=self.state.experiments,
            iteration=self.state.iteration,
            existing_hypotheses=self.state.hypotheses,
            existing_diagnoses=self.state.diagnoses
        )

        # Only append if this is a new hypothesis (not resumed)
        if not self.state.hypotheses or self.state.hypotheses[-1] is not hypothesis:
            self.state.hypotheses.append(hypothesis)

        # Log hypothesis
        logger.info(f"Hypothesis generated:")
        logger.info(f"  Name: {hypothesis.get('name', 'N/A')}")
        logger.info(f"  Design: {hypothesis.get('experimental_design', 'N/A')}")
        logger.info(f"  Parameters: {len(hypothesis.get('parameters_to_test', []))}")

        # Log to phase logger
        if self._phase_logger:
            try:
                self._phase_logger.set_iteration_context(
                        calibration_round=self.state.calibration_round,
                        iteration=self.state.iteration,
                        experiment_count=self.state.experiment_count,
                        skip_testing_count=self.state.skip_testing_count
                    )
                raw_params = hypothesis.get('parameters', hypothesis.get('parameters_to_test', []))
                params_to_modify = [
                    {
                        'name': p.get('name', ''),
                        'current': p.get('current', ''),
                        'proposed': p.get('proposed', ''),
                        'rationale': p.get('rationale', '')
                    }
                    for p in raw_params
                ]
                ai_reasoning = hypothesis.get('mechanism', '') or hypothesis.get('reasoning', '')
                log_path = self._phase_logger.log_hypothesis(
                    title=hypothesis.get('name', "Hypothesis"),
                    hypothesis_name=hypothesis.get('name', 'Unknown'),
                    mechanism=hypothesis.get('mechanism', ''),
                    parameters_to_modify=params_to_modify,
                    ai_reasoning=ai_reasoning,
                    design_type=hypothesis.get('design_type', hypothesis.get('experimental_design', 'cumulative')),
                    expected_outcomes=hypothesis.get('expected_outcomes', {'expectation': hypothesis.get('expected_outcome', '')}),
                    confidence=hypothesis.get('confidence', 0),
                    metadata={
                        'iteration': self.state.iteration,
                        'diagnosis_count': len(self.state.diagnoses)
                    }
                )
                logger.info(f"  Phase log written: {log_path}")
            except Exception as e:
                logger.warning(f"Could not write hypothesis log: {e}")

        # =====================================================================
        # Skip Testing Path: Test hypothesis with existing ensemble data
        # (Inner Loop of Two-Level Iteration Structure)
        # =====================================================================
        if hypothesis.get('test_with_existing', False):
            logger.info("=" * 60)
            logger.info("SKIP TESTING: Hypothesis can be tested with existing data")
            logger.info("=" * 60)

            # Delegate testing to phase script
            test_result = test_hypothesis_with_existing_data(
                hypothesis=hypothesis,
                config=self.config,
                screening_data=self.state.screening_data,
                diagnostic_runner=self._run_diagnostic_scripts if HAS_DIAGNOSIS_TOOLS else None
            )
            test_result['iteration'] = self.state.iteration

            logger.info(f"  Test method: {test_result.get('test_method', 'unknown')}")
            logger.info(f"  Result: {'SUPPORTED' if test_result.get('hypothesis_supported') else 'NOT SUPPORTED'}")
            logger.info(f"  Confidence: {test_result.get('confidence', 0):.2f}")

            # Record test result
            self.state.hypothesis_tests.append(test_result)

            # Accumulate insights for cross-cycle synthesis
            insight_entry = {
                'cycle': self.state.skip_testing_count + 1,
                'iteration': self.state.iteration,
                'hypothesis_name': hypothesis.get('name', 'Unknown'),
                'hypothesis_supported': test_result.get('hypothesis_supported', None),
                'confidence': test_result.get('confidence', 0),
                'test_method': test_result.get('test_method', 'unknown'),
                'key_insights': test_result.get('insights', test_result.get('evidence', '')),
                'evidence_summary': test_result.get('evidence', ''),
                'parameters_tested': [
                    p.get('name', '') for p in hypothesis.get('parameters',
                        hypothesis.get('parameters_to_test', []))
                ],
            }
            self.state.cumulative_insights.append(insight_entry)
            logger.info(f"  Accumulated insight #{len(self.state.cumulative_insights)}: "
                       f"{hypothesis.get('name', '?')} → "
                       f"{'supported' if test_result.get('hypothesis_supported') else 'not supported'}")

            # Increment skip testing counter (inner loop)
            self.state.skip_testing_count += 1
            self.state.iteration += 1

            # Check if should exit skip testing and proceed to HPC
            confidence = test_result.get('confidence', 0)
            if (confidence >= self.config.hypothesis_confidence_threshold or
                self.state.skip_testing_count >= self.config.max_skip_testing):

                logger.info(f"Exiting Skip Testing after {self.state.skip_testing_count} cycles")
                logger.info(f"  Confidence: {confidence:.2f} (threshold: {self.config.hypothesis_confidence_threshold})")
                logger.info(f"  Skip testing cycles: {self.state.skip_testing_count}/{self.config.max_skip_testing}")

                # Synthesize cumulative insights into multiple experiment designs
                if self.reasoning and self.state.cumulative_insights:
                    logger.info("Synthesizing cumulative insights into experiment designs...")
                    try:
                        synthesized_list = self.reasoning.synthesize_experiment_design(
                            cumulative_insights=self.state.cumulative_insights,
                            hypotheses=self.state.hypotheses,
                            diagnosis=self.state.diagnoses[-1] if self.state.diagnoses else {},
                            sensitivity_data=self.state.exploration_data.get('sensitivity_rankings', {}),
                            previous_experiments=self.state.experiments,
                        )
                        if synthesized_list:
                            for synth in synthesized_list:
                                if synth and synth.get('parameters'):
                                    self.state.hypotheses.append(synth)

                            n_synth = sum(1 for s in synthesized_list if s and s.get('parameters'))
                            logger.info(f"  Synthesized {n_synth} experiment designs for HPC testing")

                            # Log each synthesized experiment
                            if self._phase_logger:
                                for synth in synthesized_list:
                                    if not synth or not synth.get('parameters'):
                                        continue
                                    try:
                                        self._phase_logger.log_hypothesis(
                                            title=f"Synthesized: {synth.get('name', 'Experiment')}",
                                            hypothesis_name=synth.get('name', 'Synthesized'),
                                            mechanism=synth.get('mechanism', ''),
                                            parameters_to_modify=synth.get('parameters', []),
                                            ai_reasoning=synth.get('synthesis_summary', ''),
                                            design_type=synth.get('design_type', 'cumulative'),
                                            expected_outcomes=synth.get('expected_outcomes', {}),
                                            confidence=synth.get('confidence', 0),
                                            metadata={
                                                'synthesis': True,
                                                'n_cycles': len(self.state.cumulative_insights),
                                                'iteration': self.state.iteration,
                                                'source_hypothesis': synth.get('source_hypothesis', ''),
                                            }
                                        )
                                    except Exception as e:
                                        logger.warning(f"Could not write synthesis log: {e}")
                        else:
                            logger.warning("Synthesis returned no experiment designs, using last hypothesis")
                    except Exception as e:
                        logger.warning(f"Synthesis failed, using last hypothesis: {e}")

                self.state.current_phase = Phase.TESTING.value
                self.state.record_phase_transition(
                    Phase.HYPOTHESIS.value, Phase.TESTING.value,
                    f"Skip Testing complete after {self.state.skip_testing_count} cycles, "
                    f"confidence={confidence:.2f}, proceeding to HPC"
                )
                logger.info("Advancing to TESTING phase (HPC experiments).")
                return

            # Otherwise continue skip testing loop (back to DIAGNOSIS)
            self.state.record_phase_transition(
                Phase.HYPOTHESIS.value, Phase.DIAGNOSIS.value,
                f"Skip Testing cycle {self.state.skip_testing_count}: "
                f"{'supported' if test_result.get('hypothesis_supported') else 'not supported'}, "
                f"confidence={confidence:.2f}"
            )
            self.state.current_phase = Phase.DIAGNOSIS.value
            logger.info(f"Skip Testing cycle {self.state.skip_testing_count}/{self.config.max_skip_testing}")
            logger.info(f"Returning to DIAGNOSIS (iteration {self.state.iteration}) with test results.")
            return

        # Human review checkpoint - key handoff before HPC testing
        if self.config.human_review:
            raw_params = hypothesis.get('parameters', hypothesis.get('parameters_to_test', []))
            param_summary = "\n".join([
                f"    {p.get('name', '?')}: {p.get('current', '?')} → {p.get('proposed', '?')}"
                for p in raw_params
            ]) or "    (none specified)"
            self._human_review_checkpoint(
                phase="HYPOTHESIS",
                summary=f"""
Hypothesis: {hypothesis.get('name', 'Unknown')}
  Design: {hypothesis.get('design_type', hypothesis.get('experimental_design', 'N/A'))}
  Confidence: {hypothesis.get('confidence', 0):.2f}

  Parameter modifications:
{param_summary}

  Expected outcome: {hypothesis.get('expected_outcomes', hypothesis.get('expected_outcome', 'N/A'))}
""",
                next_phase="TESTING",
                options={
                    'c': 'Continue to testing phase',
                    'q': 'Quit workflow (state saved - review hypothesis log and run HPC experiments manually)',
                }
            )

        # Transition to TESTING
        self.state.record_phase_transition(
            Phase.HYPOTHESIS.value, Phase.TESTING.value,
            f"Hypothesis: {hypothesis.get('name', 'Unknown')}"
        )
        self.state.current_phase = Phase.TESTING.value
        logger.info("Hypothesis generated. Advancing to TESTING.")

    # =========================================================================
    # PHASE 5: TESTING - Execute Experiments on HPC
    # =========================================================================
    def _run_testing(self):
        """
        Phase 5: Execute experiments on HPC.

        This phase:
        1. Creates modified parameter files (tools/modify_fates_parameters.py)
        2. Submits simulations to HPC (tools/submit_experiment.sh)
        3. Waits for job completion (squeue/sacct polling)
        4. Extracts and evaluates results (tools/extract_*, tools/cost_functions.py)

        Uses phase scripts from phases/phase5_testing/ which directly
        call shared tools in tools/.

        Experiment Execution:
        - Base case: Best case from screening (e.g., #2678)
        - Modifications: As specified in hypothesis
        - Default phase: TRANS only (uses existing spinup restart files)
        """
        from phases.phase5_testing import (
            create_experiment_param_files,
            submit_experiments,
            wait_for_experiments,
            extract_experiment_results
        )

        logger.info("=" * 60)
        logger.info("PHASE 5: TESTING - Execute Experiments on HPC")
        logger.info("=" * 60)

        # Reset skip testing counter when entering HPC testing (outer loop)
        if self.state.skip_testing_count > 0:
            logger.info(f"Completed {self.state.skip_testing_count} skip testing cycles, now running HPC experiments")
            self.state.skip_testing_count = 0

        # --- 1. Resume-skip check ---
        current_iter = self.state.iteration
        existing_exps = [
            e for e in self.state.experiments
            if e.get("iteration") == current_iter
            and e.get("status") not in (None, "placeholder")
        ]
        if existing_exps:
            logger.info(f"Found {len(existing_exps)} experiments from iteration "
                        f"{current_iter} with non-placeholder status. Skipping to transition.")
            self.state.record_phase_transition(
                Phase.TESTING.value, Phase.REFINEMENT.value,
                f"Resumed: {len(existing_exps)} experiments already exist for iteration {current_iter}"
            )
            self.state.current_phase = Phase.REFINEMENT.value
            return

        # --- 2. Design experiments from hypotheses ---
        # Collect all synthesized hypotheses; fall back to the last hypothesis
        synthesized = [h for h in self.state.hypotheses if isinstance(h, dict) and h.get('synthesized')]
        if not synthesized:
            last = self.state.hypotheses[-1] if self.state.hypotheses else {}
            synthesized = [last] if last else []

        if not synthesized:
            logger.warning("No hypothesis available. Cannot design experiments.")
            self.state.record_phase_transition(
                Phase.TESTING.value, Phase.REFINEMENT.value,
                "No hypothesis to test"
            )
            self.state.current_phase = Phase.REFINEMENT.value
            return

        # Design experiments for each hypothesis independently
        experiments = []
        for hyp in synthesized:
            hyp_experiments = self._design_experiment_sequence(hyp)
            experiments.extend(hyp_experiments)

        if not experiments:
            logger.warning("No experiments designed from hypotheses.")
            self.state.record_phase_transition(
                Phase.TESTING.value, Phase.REFINEMENT.value,
                "No experiments could be designed"
            )
            self.state.current_phase = Phase.REFINEMENT.value
            return

        logger.info(f"Designed experiments from {len(synthesized)} hypotheses")

        # Tag each experiment with iteration
        for exp in experiments:
            exp["iteration"] = current_iter

        logger.info(f"Designed {len(experiments)} experiments for iteration {current_iter}")

        # --- 3. Create modified parameter files ---
        # Each experiment uses its base_case's parameter file (not the default template)
        param_dir = os.environ.get('A2MC_PARAM_DIR', '')
        param_pattern = os.environ.get('A2MC_PARAM_PATTERN', '')

        if not param_dir or not param_pattern:
            try:
                from tools.config import config as a2mc_config
                if not param_dir:
                    param_dir = a2mc_config.PARAM_DIR
                if not param_pattern:
                    param_pattern = a2mc_config.PARAM_PATTERN
            except (ImportError, AttributeError):
                pass

        if not param_dir or not param_pattern:
            logger.error("A2MC_PARAM_DIR and A2MC_PARAM_PATTERN must be configured. "
                         "Experiments require case-specific parameter files.")
            for exp in experiments:
                exp["status"] = "no_param_config"
                exp["iteration"] = current_iter
                self.state.experiments.append(exp)
            self.state.current_phase = Phase.REFINEMENT.value
            return

        logger.info(f"Case parameter files: {param_dir}/{param_pattern}")

        output_dir = os.path.join(self.config.output_dir, "logs",
                                  "phase5_testing", f"iter_{current_iter}")
        try:
            experiments = create_experiment_param_files(
                experiments=experiments,
                output_dir=output_dir,
                verify=True,
                param_dir=param_dir,
                param_pattern=param_pattern,
            )
            created = sum(1 for e in experiments if e.get("param_status") == "created")
            logger.info(f"Created {created}/{len(experiments)} parameter files")
        except Exception as e:
            logger.error(f"Parameter file creation failed: {e}")
            for exp in experiments:
                exp["status"] = "param_creation_failed"
                exp["error"] = str(e)
                self.state.experiments.append(exp)
            self.state.current_phase = Phase.REFINEMENT.value
            return

        # --- 4. Submit experiments to HPC ---
        try:
            experiments = submit_experiments(
                experiments=experiments,
                output_root=self.config.hpc_output_root,
                phases="ADSP RGSP TRANS",  # Full spinup required for modified params
                submit=True
            )
            submitted = sum(1 for e in experiments
                           if e.get("submission_status") in ("submitted", "simulated"))
            logger.info(f"Submitted {submitted}/{len(experiments)} experiments")
        except Exception as e:
            logger.error(f"Experiment submission failed: {e}")
            for exp in experiments:
                if not exp.get("submission_status"):
                    exp["submission_status"] = "submission_failed"
                    exp["status"] = "submission_failed"
                    exp["error"] = str(e)

        # --- 5. Wait for all jobs to complete ---
        try:
            experiments = wait_for_experiments(
                experiments=experiments,
                poll_interval=self.config.poll_interval,
                timeout=86400  # 24 hours
            )
        except Exception as e:
            logger.error(f"Job monitoring failed: {e}")

        # --- 6. Extract and evaluate results ---
        # Pass screening targets so evaluation can compute metrics
        screening_targets = None
        try:
            from phases.phase2_screening.screen_ensemble import load_kougarok_targets
            screening_targets = load_kougarok_targets()
        except Exception:
            pass

        try:
            experiments = extract_experiment_results(
                experiments=experiments,
                output_root=self.config.hpc_output_root,
                targets=screening_targets
            )
        except Exception as e:
            logger.error(f"Result extraction failed: {e}")
            for exp in experiments:
                if not exp.get("extraction_status"):
                    exp["extraction_status"] = "extraction_failed"
                    exp["error"] = str(e)

        # --- 7. Set final status and record to state ---
        for exp in experiments:
            # Determine overall status
            if exp.get("extraction_status") in ("extracted", "simulated_no_output"):
                exp["status"] = "completed"
            elif exp.get("submission_status") == "simulated":
                exp["status"] = "simulated"
            elif "failed" in str(exp.get("submission_status", "")):
                exp["status"] = "submission_failed"
            elif "failed" in str(exp.get("extraction_status", "")):
                exp["status"] = "extraction_failed"
            else:
                exp["status"] = exp.get("job_status", "unknown")

            self.state.experiments.append(exp)

        # --- 8. Record to adaptive memory ---
        if self._memory and self.config.auto_learn:
            for exp in experiments:
                try:
                    outcome = "completed" if exp.get("status") == "completed" else exp.get("status", "unknown")
                    self._memory.record_experiment(
                        experiment_id=exp.get("name", "unnamed"),
                        base_case=exp.get("base_case", "unknown"),
                        modifications=exp.get("modifications", []),
                        results=exp.get("results", {}),
                        outcome=outcome
                    )
                    logger.debug(f"Recorded experiment '{exp.get('name')}' to memory")
                except Exception as e:
                    logger.warning(f"Could not record experiment to memory: {e}")

        # --- 9. Phase logger ---
        try:
            exp_names = []
            results_summary = {}
            for exp in experiments:
                name = exp.get("name", "unnamed")
                exp_names.append(name)
                met = exp.get("results", {}).get("targets_met", "?")
                total = exp.get("results", {}).get("total_targets", "?")
                results_summary[name] = {
                    "status": exp.get("status", "unknown"),
                    "targets_met": met,
                    "total_targets": total,
                }
            self._phase_logger.log_testing(
                title=f"Iteration_{current_iter}_Testing",
                experiments_run=exp_names,
                results_summary=results_summary,
                ai_reasoning=f"Hypothesis: {hypothesis.get('name', 'unknown')}\n"
                             f"Mechanism: {hypothesis.get('mechanism', 'unknown')}"
            )
        except Exception as e:
            logger.warning(f"Phase logging failed: {e}")

        # --- 10. Human review checkpoint ---
        if self.config.human_review:
            completed = sum(1 for e in experiments if e.get("status") == "completed")
            failed = sum(1 for e in experiments if "failed" in str(e.get("status", "")))
            simulated = sum(1 for e in experiments if e.get("status") == "simulated")

            summary = f"""
  Iteration: {current_iter}
  Hypothesis: {hypothesis.get('name', 'unknown')}
  Experiments: {len(experiments)} total
    Completed: {completed}
    Simulated: {simulated}
    Failed: {failed}

  Results Summary:"""
            for exp in experiments:
                met = exp.get("results", {}).get("targets_met", "?")
                total = exp.get("results", {}).get("total_targets", "?")
                summary += f"\n    {exp.get('name', '?')}: {exp.get('status', '?')} (targets: {met}/{total})"

            self._human_review_checkpoint(
                phase="TESTING",
                summary=summary,
                next_phase="REFINEMENT"
            )

        # --- 11. Phase transition → REFINEMENT ---
        completed_count = sum(1 for e in experiments if e.get("status") in ("completed", "simulated"))
        self.state.record_phase_transition(
            Phase.TESTING.value, Phase.REFINEMENT.value,
            f"Executed {len(experiments)} experiments ({completed_count} completed)"
        )
        self.state.current_phase = Phase.REFINEMENT.value
        logger.info(f"Testing complete. {completed_count}/{len(experiments)} experiments done. "
                     f"Advancing to REFINEMENT.")

    def _design_experiment_sequence(self, hypothesis: Dict) -> List[Dict]:
        """Design experiment sequence from hypothesis."""
        design_type = hypothesis.get("design_type", hypothesis.get("experimental_design", "cumulative"))
        params = hypothesis.get("parameters", hypothesis.get("parameters_to_test", []))
        base_case = self.state.screening_data.get("best_case", {}).get("case_id", "2678")

        experiments = []

        if design_type == "cumulative":
            # Cumulative: Exp1 = A, Exp2 = A+B, Exp3 = A+B+C
            cumulative_mods = []
            for i, param in enumerate(params):
                mod = {
                    "parameter": param["name"],
                    "old_value": param.get("current"),
                    "new_value": param.get("proposed"),
                }
                if "pft" in param:
                    mod["pft"] = param["pft"]
                if "organ" in param:
                    mod["organ"] = param["organ"]
                cumulative_mods.append(mod)
                experiments.append({
                    "name": f"Exp{i+1}_{hypothesis.get('name', 'test')}",
                    "base_case": base_case,
                    "modifications": cumulative_mods.copy(),
                    "expected_outcome": hypothesis.get("expected_outcome",
                                                       hypothesis.get("expected_outcomes", ""))
                })

        elif design_type == "factorial":
            # Factorial: All combinations
            import itertools
            for r in range(1, len(params) + 1):
                for combo in itertools.combinations(range(len(params)), r):
                    mods = []
                    for i in combo:
                        mod = {
                            "parameter": params[i]["name"],
                            "old_value": params[i].get("current"),
                            "new_value": params[i].get("proposed"),
                        }
                        if "pft" in params[i]:
                            mod["pft"] = params[i]["pft"]
                        if "organ" in params[i]:
                            mod["organ"] = params[i]["organ"]
                        mods.append(mod)
                    name_suffix = "+".join([params[i]["name"].split("_")[-1] for i in combo])
                    experiments.append({
                        "name": f"F{len(experiments)+1}_{name_suffix}",
                        "base_case": base_case,
                        "modifications": mods,
                        "expected_outcome": hypothesis.get("expected_outcome",
                                                           hypothesis.get("expected_outcomes", ""))
                    })

        return experiments

    # =========================================================================
    # PHASE 6: REFINEMENT - Evaluate and Iterate/Converge
    # =========================================================================
    def _run_refinement(self):
        """
        Phase 6: Evaluate experiment results and decide next action.

        Delegates evaluation to phases/phase6_refinement/evaluate_results.py.
        Keeps loop control (phase transitions, counter updates) here.
        """
        from phases.phase6_refinement import evaluate_experiments, determine_refinement_action

        logger.info("Evaluating experiment results...")

        # Delegate evaluation to phase script
        eval_result = evaluate_experiments(
            experiments=self.state.experiments,
            total_targets=8,
            reasoning_module=self.reasoning if self.config.auto_learn else None,
            memory_manager=self._memory if self.config.auto_learn else None,
            auto_learn=self.config.auto_learn
        )

        if eval_result.get('no_experiments'):
            self.state.iteration += 1
            self.state.current_phase = Phase.DIAGNOSIS.value
            return

        best_exp = eval_result['best_experiment']
        best_targets_met = eval_result['best_targets_met']
        total_targets = eval_result['total_targets']
        prev_best_targets = (self.state.best_experiment or {}).get("results", {}).get("targets_met", 0)

        # Determine action
        action_result = determine_refinement_action(best_targets_met, total_targets, prev_best_targets)

        # Log refinement to phase logger
        if self._phase_logger:
            try:
                self._phase_logger.set_iteration_context(
                        calibration_round=self.state.calibration_round,
                        iteration=self.state.iteration,
                        experiment_count=self.state.experiment_count,
                        skip_testing_count=self.state.skip_testing_count
                    )

                targets_improved = []
                targets_degraded = []
                if best_targets_met > prev_best_targets:
                    targets_improved = [f"{best_targets_met - prev_best_targets} additional targets"]
                elif best_targets_met < prev_best_targets:
                    targets_degraded = [f"{prev_best_targets - best_targets_met} targets degraded"]

                log_path = self._phase_logger.log_refinement(
                    title="Refinement",
                    hypothesis_status=action_result['hypothesis_status'],
                    targets_improved=targets_improved,
                    targets_degraded=targets_degraded,
                    ai_reasoning="",
                    lessons_learned=[],
                    next_action=action_result['action'],
                    metadata={
                        'iteration': self.state.iteration,
                        'best_experiment': best_exp.get('name', '') if best_exp else '',
                        'best_targets_met': best_targets_met,
                        'total_targets': total_targets
                    }
                )
                logger.info(f"  Phase log written: {log_path}")
            except Exception as e:
                logger.warning(f"Could not write refinement log: {e}")

        # Human review checkpoint before iteration decision
        if self.config.human_review:
            self._human_review_checkpoint(
                phase="REFINEMENT",
                summary=f"""
Refinement Summary:
  - Best experiment: {best_exp.get('name', 'N/A') if best_exp else 'N/A'}
  - Targets met: {best_targets_met}/{total_targets}
  - Recommended action: {action_result['description']}
""",
                next_phase="NEXT ITERATION" if best_targets_met < total_targets else "CONVERGED",
                options={
                    'c': f"Continue ({action_result['description']})",
                    'q': 'Quit workflow (state saved)',
                }
            )

        # Decision logic (Outer Loop of Two-Level Iteration Structure)
        if best_targets_met >= total_targets:
            # ALL targets met - CONVERGE!
            self.state.converged = True
            self.state.best_experiment = best_exp
            self.state.current_phase = Phase.CONVERGED.value
            logger.info(f"\nALL {total_targets} TARGETS MET! Workflow CONVERGED.")

        elif best_targets_met > prev_best_targets:
            # Progress made - update best and continue
            self.state.best_experiment = best_exp
            self.state.experiment_count += 1
            self.state.iteration += 1

            if self.state.experiment_count >= self.config.max_experiments:
                logger.warning(f"Max experiments ({self.config.max_experiments}) reached")
                logger.info(f"Best result: {best_targets_met}/{total_targets} targets met")
                self.state.current_phase = Phase.CONVERGED.value
                self.state.record_phase_transition(
                    Phase.REFINEMENT.value, Phase.CONVERGED.value,
                    f"Max experiments reached with {best_targets_met}/{total_targets} targets"
                )
            else:
                self.state.current_phase = Phase.DIAGNOSIS.value
                logger.info(f"\nProgress made ({best_targets_met}/{total_targets}). Iterating...")
                logger.info(f"Experiment cycle {self.state.experiment_count}/{self.config.max_experiments}")
                self.state.record_phase_transition(
                    Phase.REFINEMENT.value, Phase.DIAGNOSIS.value,
                    f"Progress: {best_targets_met}/{total_targets} targets, "
                    f"experiment cycle {self.state.experiment_count}"
                )

        else:
            # No progress - try different hypothesis
            self.state.experiment_count += 1
            self.state.iteration += 1

            if self.state.experiment_count >= self.config.max_experiments:
                logger.warning(f"Max experiments ({self.config.max_experiments}) reached without improvement")
                logger.info(f"Best result: {best_targets_met}/{total_targets} targets met")
                self.state.current_phase = Phase.CONVERGED.value
                self.state.record_phase_transition(
                    Phase.REFINEMENT.value, Phase.CONVERGED.value,
                    f"Max experiments reached without improvement, {best_targets_met}/{total_targets} targets"
                )
            else:
                self.state.current_phase = Phase.DIAGNOSIS.value
                logger.info(f"\nNo improvement. Trying different approach...")
                logger.info(f"Experiment cycle {self.state.experiment_count}/{self.config.max_experiments}")
                self.state.record_phase_transition(
                    Phase.REFINEMENT.value, Phase.DIAGNOSIS.value,
                    f"No improvement, trying new hypothesis, "
                    f"experiment cycle {self.state.experiment_count}"
                )

    # =========================================================================
    # CONVERGENCE - Final Report
    # =========================================================================
    def _handle_convergence(self):
        """Handle successful convergence and generate final report."""
        logger.info("\n" + "=" * 70)
        logger.info("CALIBRATION COMPLETE")
        logger.info("=" * 70)

        best = self.state.best_experiment

        if best:
            logger.info(f"Best experiment: {best.get('name', 'N/A')}")
            logger.info(f"Targets met: {best.get('results', {}).get('targets_met', 0)}/8")
            logger.info(f"\nParameter modifications:")
            for mod in best.get("modifications", []):
                logger.info(f"  - {mod['parameter']}: {mod['old_value']} → {mod['new_value']}")

        # Generate final report
        final_report = {
            "converged": self.state.converged,
            "iterations": self.state.iteration,
            "best_experiment": best,
            "all_experiments": self.state.experiments,
            "diagnoses": self.state.diagnoses,
            "hypotheses": self.state.hypotheses,
            "phase_history": self.state.phase_history,
            "completed_at": datetime.now().isoformat()
        }

        report_path = self.output_dir / "final_report.json"
        with open(report_path, 'w') as f:
            json.dump(final_report, f, indent=2)

        logger.info(f"\nFinal report saved to: {report_path}")


def parse_phase(value: str) -> str:
    """
    Parse phase argument - accepts number (0-7), name, or 'phaseN' format.

    Examples: '1', 'phase1', 'exploration' all map to 'exploration'
    """
    # Phase number to name mapping
    phase_number_map = {
        '0': 'design',
        '1': 'exploration',
        '2': 'screening',
        '3': 'diagnosis',
        '4': 'hypothesis',
        '5': 'testing',
        '6': 'refinement',
        '7': 'converged',
    }

    # Normalize input
    value = value.lower().strip()

    # Try direct number
    if value in phase_number_map:
        return phase_number_map[value]

    # Try 'phaseN' format
    if value.startswith('phase') and value[5:] in phase_number_map:
        return phase_number_map[value[5:]]

    # Try direct phase name
    valid_names = [p.value for p in Phase]
    if value in valid_names:
        return value

    # Not found
    raise argparse.ArgumentTypeError(
        f"Invalid phase: '{value}'. Use 0-7, phase0-phase7, or: {', '.join(valid_names)}"
    )


def main():
    """Entry point for the A2MC orchestrator."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Agentic Adaptive Multi-target Calibration (A2MC) for ELM-FATES",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Bootstrap: validate configuration and dependencies
  python orchestrator.py --bootstrap

  # Run workflow (source configs first, output-dir auto-detected)
  python orchestrator.py --run

  # Resume from checkpoint (state file is in site memory folder)
  python orchestrator.py --resume --state-file ./use_cases/Kougarok/memory/workflow_state.json

  # Start from specific phase in calibration round 2 (e.g., 162 params)
  python orchestrator.py --run --start-phase 2 --start-iteration 2
  python orchestrator.py --run --start-phase screening --start-iteration 2

  # Start from diagnosis in round 2
  python orchestrator.py --run --start-phase diagnosis --start-iteration 2

  # Skip bootstrap check before running
  python orchestrator.py --run --skip-bootstrap

Phase numbers:
  0 = design       (Phase 0: Sensitivity sampling design)
  1 = exploration  (Phase 1: Run sensitivity analysis)
  2 = screening    (Phase 2: Screen cases against targets)
  3 = diagnosis    (Phase 3: Diagnose failures)
  4 = hypothesis   (Phase 4: Generate hypotheses)
  5 = testing      (Phase 5: Run experiments)
  6 = refinement   (Phase 6: Evaluate and iterate)
  7 = converged    (Final: Calibration complete)
        """
    )

    parser.add_argument("--bootstrap", action="store_true",
                       help="Validate configuration and dependencies without running")
    parser.add_argument("--init", action="store_true", help="Initialize new workflow")
    parser.add_argument("--run", action="store_true", help="Run workflow")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--skip-bootstrap", action="store_true",
                       help="Skip bootstrap validation before running")
    parser.add_argument("--state-file", type=str, default=None,
                       help="State file path (default: auto-detected from A2MC_USE_CASE_DIR)")
    parser.add_argument("--output-dir", type=str, default=None,
                       help="Output directory (default: auto-detected from A2MC_USE_CASE_DIR)")
    parser.add_argument("--max-iterations", type=int, default=10,
                       help="Max total iterations (backward compatibility)")
    parser.add_argument("--max-skip-testing", type=int, default=10,
                       help="Max Phase 3↔4 skip testing cycles (default: 10)")
    parser.add_argument("--max-experiments", type=int, default=10,
                       help="Max full experiment cycles 3→4→5→6 (default: 10)")
    parser.add_argument("--confidence-threshold", type=float, default=0.95,
                       help="Hypothesis confidence threshold to exit skip testing (default: 0.95)")
    parser.add_argument("--no-review", action="store_true", help="Skip human review points")
    parser.add_argument("--manual-skip-testing", action="store_true",
                       help="Require manual review at each skip-testing cycle (default: auto-continue)")
    parser.add_argument("--no-reasoning", action="store_true", help="Disable Claude API")
    parser.add_argument("--start-phase", type=parse_phase,
                       help="Start from phase (0-7, phase0-phase7, or name like 'exploration')")
    parser.add_argument("--start-iteration", type=int, default=None,
                       help="Calibration round (outermost loop: 1=first ensemble, 2=redesigned, ...)")

    # Sampling design options (override config defaults)
    parser.add_argument("--sampling-scheme", type=str,
                       help="Sampling scheme (morris, lhs, sobol, custom)")
    parser.add_argument("--n-trajectories", type=int,
                       help="Number of trajectories (for morris scheme)")
    parser.add_argument("--n-samples", type=int,
                       help="Number of samples (for lhs/sobol schemes)")
    parser.add_argument("--n-levels", type=int, default=8,
                       help="Grid levels for parameter space")
    parser.add_argument("--n-parameters", type=int,
                       help="Number of parameters (override config)")

    args = parser.parse_args()

    # Determine output directory and state file (use site memory if available)
    output_dir = args.output_dir
    state_file = args.state_file

    if output_dir is None or state_file is None:
        # Try to use site-specific memory directory
        try:
            from tools.config import config as a2mc_config
            if a2mc_config.USE_CASE_DIR:
                site_memory_dir = os.path.join(a2mc_config.USE_CASE_DIR, "memory")
                if output_dir is None:
                    output_dir = site_memory_dir
                    logger.info(f"Using site memory directory: {output_dir}")
                if state_file is None:
                    state_file = os.path.join(site_memory_dir, "workflow_state.json")
                    logger.info(f"Using site state file: {state_file}")
            else:
                logger.error("A2MC_USE_CASE_DIR not set. Please source the config files first:")
                logger.error("  source a2mc_config.sh")
                logger.error("  source use_cases/{site}/config/{site}_config.sh")
                sys.exit(1)
        except ImportError:
            use_case_dir = os.environ.get('A2MC_USE_CASE_DIR')
            if use_case_dir:
                site_memory_dir = os.path.join(use_case_dir, "memory")
                if output_dir is None:
                    output_dir = site_memory_dir
                if state_file is None:
                    state_file = os.path.join(site_memory_dir, "workflow_state.json")
            else:
                logger.error("A2MC_USE_CASE_DIR not set. Please source the config files first:")
                logger.error("  source a2mc_config.sh")
                logger.error("  source use_cases/{site}/config/{site}_config.sh")
                sys.exit(1)

    # Create config (values from args override environment/config defaults)
    config = Config(
        state_file=state_file,
        output_dir=output_dir,
        max_iterations=args.max_iterations,
        max_skip_testing=args.max_skip_testing,
        max_experiments=args.max_experiments,
        hypothesis_confidence_threshold=args.confidence_threshold,
        human_review=not args.no_review,
        auto_skip_testing=not args.manual_skip_testing,
        use_reasoning=not args.no_reasoning,
        sampling_scheme=args.sampling_scheme or "",
        n_trajectories=args.n_trajectories or 0,
        n_samples=args.n_samples or 0,
        n_levels=args.n_levels,
        n_parameters=args.n_parameters or 0
    )

    # Create output directory
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    # Set up log file to capture all screen output (print + logging)
    # Log goes to use_cases/{site}/ (site root directory)
    try:
        from tools.config import config as a2mc_config
        log_parent = Path(a2mc_config.USE_CASE_DIR)
    except (ImportError, AttributeError):
        log_parent = Path(os.environ.get('A2MC_USE_CASE_DIR', config.output_dir))
    log_filename = f"a2mc_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_filepath = log_parent / log_filename

    # Tee class: writes to both original stream and log file
    class TeeStream:
        """Duplicate output to both console and log file."""
        def __init__(self, original, log_file):
            self.original = original
            self.log_file = log_file
        def write(self, text):
            self.original.write(text)
            self.log_file.write(text)
            self.log_file.flush()
        def flush(self):
            self.original.flush()
            self.log_file.flush()
        def fileno(self):
            return self.original.fileno()
        def isatty(self):
            return self.original.isatty()

    log_file_handle = open(log_filepath, 'w')
    sys.stdout = TeeStream(sys.__stdout__, log_file_handle)
    sys.stderr = TeeStream(sys.__stderr__, log_file_handle)

    # Also add file handler to root logger for logging module output
    file_handler = logging.FileHandler(log_filepath)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)

    logger.info(f"Log file: {log_filepath}")

    try:
        # Initialize orchestrator
        orchestrator = CalibrationOrchestrator(config)

        # Handle start phase and iteration overrides
        if args.start_phase:
            orchestrator.state.current_phase = args.start_phase
            logger.info(f"Starting from phase: {args.start_phase}")

            # Clear cached results for this phase so it actually re-runs
            # (otherwise the phase sees existing results and skips execution)
            iteration = orchestrator.state.iteration

            # Screening: clear screening_data dict
            if args.start_phase == 'screening':
                if orchestrator.state.screening_data:
                    orchestrator.state.screening_data = {}
                    logger.info("Cleared cached screening results (will re-run)")

            # Diagnosis/Hypothesis: clear from result lists
            phase_result_lists = {
                'diagnosis': 'diagnoses',
                'hypothesis': 'hypotheses',
            }
            result_key = phase_result_lists.get(args.start_phase)
            if result_key:
                result_list = getattr(orchestrator.state, result_key, [])
                if result_list and result_list[-1].get('iteration') == iteration:
                    removed = result_list.pop()
                    logger.info(f"Cleared cached {args.start_phase} result for iteration {iteration} "
                               f"(will re-run)")
                    # Also clear downstream results for the same iteration
                    if args.start_phase == 'diagnosis':
                        hyp_list = orchestrator.state.hypotheses
                        if hyp_list and hyp_list[-1].get('iteration') == iteration:
                            hyp_list.pop()
                            logger.info(f"  Also cleared cached hypothesis for iteration {iteration}")

        if args.start_iteration is not None:
            orchestrator.state.calibration_round = args.start_iteration
            logger.info(f"Calibration round: {args.start_iteration}")
            os.environ['A2MC_CALIBRATION_ROUND'] = str(args.start_iteration)

        # Initialize sampling_design for round 2+ (simulations already complete)
        if args.start_iteration is not None and args.start_iteration >= 2:
            if not orchestrator.state.sampling_design.get('complete', False):
                try:
                    from tools.config import config as a2mc_config
                    orchestrator.state.sampling_design = {
                        'scheme': a2mc_config.SAMPLING_SCHEME,
                        'n_parameters': a2mc_config.N_PARAMS,
                        'n_trajectories': a2mc_config.N_TRAJECTORIES,
                        'n_simulations': a2mc_config.TOTAL_ENSEMBLE,
                        'complete': True,  # Simulations already exist
                        'extracted_data_dir': a2mc_config.EXTRACTED_DATA,
                        'ensemble_output_dir': a2mc_config.ENSEMBLE_OUTPUT,
                        'ensemble_matrix_file': a2mc_config.ENSEMBLE_MATRIX_FILE,
                    }
                    logger.info(f"Initialized sampling_design for round {args.start_iteration}:")
                    logger.info(f"  - {a2mc_config.TOTAL_ENSEMBLE} simulations (marked complete)")
                    logger.info(f"  - Extracted data: {a2mc_config.EXTRACTED_DATA}")
                except ImportError:
                    logger.warning("Could not load tools.config - sampling_design not initialized")

        # Execute
        if args.bootstrap:
            # Bootstrap only: validate and exit
            status = orchestrator.bootstrap()
            if not status["ready"]:
                logger.error("Bootstrap failed. Fix issues before running.")
                return 1
            return 0

        if args.init:
            orchestrator.state.save(str(orchestrator.state_path))
            logger.info("Workflow initialized. Use --run to start.")
            return 0

        if args.run or args.resume:
            # Run bootstrap check unless skipped
            if not args.skip_bootstrap:
                status = orchestrator.bootstrap()
                if not status["ready"]:
                    logger.error("Bootstrap failed. Fix issues or use --skip-bootstrap to override.")
                    return 1
                logger.info("\n")  # Space before run output

            orchestrator.run()
            return 0

        parser.print_help()
        return 0

    finally:
        # Restore stdout/stderr and close log file
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        logging.getLogger().removeHandler(file_handler)
        file_handler.close()
        log_file_handle.close()


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
