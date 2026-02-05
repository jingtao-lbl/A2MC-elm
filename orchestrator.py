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
    iteration: int = 1  # Start at iteration 1 (not 0)
    current_phase: str = Phase.DESIGN.value
    converged: bool = False
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
                    iteration=self.state.iteration
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
            from integration import HPCExecutor
            self._hpc = HPCExecutor(self.config)
        return self._hpc

    @property
    def data(self):
        """Lazy-load data pipeline."""
        if self._data is None:
            from integration import DataPipeline
            self._data = DataPipeline(self.config)
        return self._data

    @property
    def params(self):
        """Lazy-load parameter manager."""
        if self._params is None:
            from integration import ParameterManager
            self._params = ParameterManager(self.config)
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
            from integration import HPCExecutor
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

        while not self.state.converged and self.state.iteration <= self.config.max_iterations:
            phase = Phase(self.state.current_phase)
            phase_num = list(Phase).index(phase)

            # Update environment variable for PhaseLogger to pick up
            os.environ['A2MC_ITERATION'] = str(self.state.iteration)

            logger.info(f"\n{'='*60}")
            logger.info(f"PHASE: {phase.value.upper()}")
            logger.info(f"Iteration: {self.state.iteration}")
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
            logger.warning(f"Max iterations ({self.config.max_iterations}) reached without convergence")
            logger.info(f"Final iteration: {self.state.iteration}")
            # Mark workflow as paused (not failed, just stopped)
            if self._workflow_status:
                self._workflow_status.pause_workflow(
                    reason=f"Max iterations ({self.config.max_iterations}) reached at iteration {self.state.iteration}"
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
                self._phase_logger.set_iteration(self.state.iteration)
                exploration_data = self.state.exploration_data

                # Build sensitivity analysis summary for log
                ai_reasoning = self._build_sensitivity_summary(exploration_data)

                log_path = self._phase_logger.log_exploration(
                    title=f"Iteration_{self.state.iteration}_Exploration",
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
                    logger.warning(f"No extracted files found in: {extracted_dir}")
                    logger.info("Run: python tools/extract_monthly_variables_FATES.py --case-file completed_cases.txt")
            else:
                logger.warning(f"Extracted data directory does not exist: {extracted_dir}")

            # Check for Morris sensitivity results (Y matrices)
            # Look in multiple locations
            # Pattern: Morris{Varname}_{N}cases_{start}_{end}.txt
            # e.g., MorrisLeafbiomass_4889cases_2010_2019.txt
            phase1_output_dir = Path(a2mc_config.USE_CASE_DIR) / "memory" / "phase_logs" / "phase1_exploration"
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
                logger.info("No Morris Y matrices found and extraction incomplete")
                logger.info("Run: python phases/phase1_exploration/extract_sensitivity_outputs.py --output-var leaf_biomass")

        except ImportError:
            logger.debug("tools.config not available, skipping results loading")

        return results

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
            output_dir = Path(a2mc_config.USE_CASE_DIR) / "memory" / "phase_logs" / "phase1_exploration"

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
            output_dir = Path(a2mc_config.USE_CASE_DIR) / "memory" / "phase_logs" / "phase1_exploration"
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
                    self._phase_logger.set_iteration(self.state.iteration)
                    log_path = self._phase_logger.log_screening(
                        title=f"Iteration_{self.state.iteration}_Screening",
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
            "target_performance": {}
        }

        # Parse results file
        try:
            with open(results_file, 'r') as f:
                lines = f.readlines()

            # Extract best case (assuming sorted by composite NRMSE)
            # Format: Case_ID, Type, Composite_NRMSE, ...
            for line in lines[1:11]:  # Top 10 cases
                parts = line.strip().split(',')
                if len(parts) >= 3:
                    screening_data["best_cases"].append({
                        "case_id": parts[0],
                        "type": parts[1],
                        "composite_nrmse": float(parts[2]) if parts[2] else None
                    })

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
            screening_data = {
                "n_cases_evaluated": result.n_valid_cases,
                "n_available_cases": result.n_available_cases,
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

            # Prepare data for Claude reasoning
            diagnosis_input = {
                "screening_results": screening_data,
                "sensitivity_rankings": exploration_data.get("sensitivity_rankings", {}),
                "targets": asdict(self.config.targets),
                "iteration": self.state.iteration
            }

            # Use Claude API for diagnosis (if available)
            if self.reasoning:
                logger.info("Using Claude API for diagnosis...")
                diagnosis = self._diagnose_with_claude(diagnosis_input)
            else:
                logger.info("Claude API not available, using rule-based diagnosis...")
                diagnosis = self._diagnose_rule_based(diagnosis_input)

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
                    self._phase_logger.set_iteration(self.state.iteration)
                    log_path = self._phase_logger.log_diagnosis(
                        title=f"Iteration_{self.state.iteration}_Diagnosis",
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
        if self.config.human_review:
            self._human_review_checkpoint(
                phase="DIAGNOSIS",
                summary=f"""
Diagnosis Summary:
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

        # Transition to HYPOTHESIS
        self.state.record_phase_transition(
            Phase.DIAGNOSIS.value, Phase.HYPOTHESIS.value,
            f"Identified {len(diagnosis.get('likely_causes', []))} likely causes"
        )
        self.state.current_phase = Phase.HYPOTHESIS.value
        logger.info("Diagnosis complete. Advancing to HYPOTHESIS.")

    def _diagnose_with_claude(self, diagnosis_input: Dict) -> Dict:
        """Use Claude API for diagnosis."""
        try:
            diagnosis = self.reasoning.diagnose(
                results=diagnosis_input["screening_results"],
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

    # =========================================================================
    # PHASE 4: HYPOTHESIS - Experimental Design
    # =========================================================================
    def _run_hypothesis(self):
        """
        Phase 4: Generate testable hypotheses with experimental designs.

        This phase:
        1. Uses diagnosis to identify mechanistic hypotheses
        2. Designs experiments (cumulative or factorial)
        3. Specifies parameter modifications
        4. Predicts expected outcomes

        Design Strategies:
        - CUMULATIVE: Sequential parameter addition (A → A+B → A+B+C)
          Use when mechanisms are sequential (survival → storage → recruitment)
        - FACTORIAL: All parameter combinations (A, B, AB, ABC)
          Use when parameters may interact (P × N synergy)

        Outputs:
        - Hypothesis objects with parameter modifications
        - Experimental design specifications
        """
        # Check if hypothesis already exists for this iteration (e.g., resuming after checkpoint)
        existing_hypothesis = None
        if self.state.hypotheses:
            last_hyp = self.state.hypotheses[-1]
            # Check if last hypothesis was generated in this iteration
            if last_hyp.get('iteration', None) == self.state.iteration or (
                self.state.diagnoses and len(self.state.hypotheses) >= len(self.state.diagnoses)
            ):
                existing_hypothesis = last_hyp
                logger.info("Hypothesis already generated for this iteration (resuming from checkpoint)")

        if existing_hypothesis:
            hypothesis = existing_hypothesis
        else:
            logger.info("Generating hypotheses...")

            latest_diagnosis = self.state.diagnoses[-1] if self.state.diagnoses else {}

            # Use Claude API for hypothesis generation (if available)
            if self.reasoning:
                logger.info("Using Claude API for hypothesis generation...")
                hypothesis = self._generate_hypothesis_with_claude(latest_diagnosis)
            else:
                logger.info("Using rule-based hypothesis generation...")
                hypothesis = self._generate_hypothesis_rule_based(latest_diagnosis)

            self.state.hypotheses.append(hypothesis)

        # Log hypothesis
        logger.info(f"Hypothesis generated:")
        logger.info(f"  Name: {hypothesis.get('name', 'N/A')}")
        logger.info(f"  Design: {hypothesis.get('experimental_design', 'N/A')}")
        logger.info(f"  Parameters: {len(hypothesis.get('parameters_to_test', []))}")

        # Log to phase logger
        log_path = None
        if self._phase_logger:
            try:
                self._phase_logger.set_iteration(self.state.iteration)
                # Handle both Claude-generated (parameters) and rule-based (parameters_to_test) field names
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
                # AI reasoning is in 'mechanism' field (Claude) or 'reasoning' field (fallback)
                ai_reasoning = hypothesis.get('mechanism', '') or hypothesis.get('reasoning', '')
                log_path = self._phase_logger.log_hypothesis(
                    title=f"Iteration_{self.state.iteration}_{hypothesis.get('name', 'Hypothesis')}",
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

    def _generate_hypothesis_with_claude(self, diagnosis: Dict) -> Dict:
        """Use Claude API to generate hypothesis."""
        try:
            # reasoning.generate_hypothesis() expects a Diagnosis object with attributes
            # (e.g., .parameter_recommendations, .likely_causes, .to_json()),
            # but state stores diagnosis as a plain dict. Reconstruct the object.
            from reasoning import Diagnosis
            diagnosis_obj = Diagnosis(**diagnosis)

            hypothesis = self.reasoning.generate_hypothesis(
                diagnosis=diagnosis_obj,
                sensitivity_data=self.state.exploration_data,
                previous_experiments=self.state.experiments
            )
            return asdict(hypothesis) if hasattr(hypothesis, '__dict__') else hypothesis
        except Exception as e:
            logger.error(f"Claude hypothesis generation failed: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return self._generate_hypothesis_rule_based(diagnosis)

    def _generate_hypothesis_rule_based(self, diagnosis: Dict) -> Dict:
        """Rule-based hypothesis when Claude API unavailable."""
        iteration = self.state.iteration

        if iteration == 0:
            # First iteration: Address root distribution and turnover
            return {
                "name": "Root Distribution Correction",
                "mechanism": "Current FATES defaults make graminoids SHALLOWEST rooted when they should be DEEPEST. Correcting root distribution improves ECA capacitance and P access.",
                "parameters_to_test": [
                    {"name": "fates_allom_fnrt_prof_a_10", "current": 11.0, "proposed": 7.0,
                     "rationale": "Match shrub parameters; deeper roots for graminoids"},
                    {"name": "fates_allom_fnrt_prof_b_10", "current": 2.0, "proposed": 1.5,
                     "rationale": "Match shrub parameters; deeper roots for graminoids"},
                    {"name": "fates_turnover_fnrt_10", "current": 1.0, "proposed": 5.0,
                     "rationale": "Arctic roots live >5 years (Blume-Werry et al. 2019)"}
                ],
                "experimental_design": "cumulative",
                "expected_outcome": "PFT#10 fineroot +100-200% from improved ECA capacitance",
                "confidence": 0.75
            }
        else:
            # Subsequent iterations: Build on previous results
            return {
                "name": f"Iteration {iteration} Refinement",
                "mechanism": "Fine-tuning based on previous experiment results",
                "parameters_to_test": [],
                "experimental_design": "factorial",
                "expected_outcome": "Further improvement toward all targets",
                "confidence": 0.60
            }

    # =========================================================================
    # PHASE 5: TESTING - Execute Experiments on HPC
    # =========================================================================
    def _run_testing(self):
        """
        Phase 5: Execute experiments on HPC.

        This phase:
        1. Creates modified parameter files
        2. Submits simulations to HPC
        3. Monitors job completion
        4. Extracts and validates results

        Experiment Execution:
        - Base case: Best case from screening (e.g., #2678)
        - Modifications: As specified in hypothesis
        - Duration: 20-year spinup + 20-year analysis
        """
        logger.info("Executing experiments on HPC...")

        hypothesis = self.state.hypotheses[-1] if self.state.hypotheses else {}

        # Create experiment specifications
        experiments = self._design_experiment_sequence(hypothesis)

        for i, exp in enumerate(experiments):
            logger.info(f"\nExperiment {i+1}/{len(experiments)}: {exp['name']}")
            logger.info(f"  Base case: {exp['base_case']}")
            logger.info(f"  Modifications: {len(exp['modifications'])}")

            # TODO: Implement HPC execution
            # 1. Create modified parameter file
            # param_file = self.params.create_modified_file(exp)

            # 2. Submit to HPC
            # job_id = self.hpc.submit_experiment(param_file, exp)

            # 3. Wait for completion
            # self.hpc.wait_for_job(job_id)

            # 4. Extract results
            # results = self.data.extract_experiment_results(exp)

            # Placeholder results
            exp["status"] = "placeholder"
            exp["results"] = {
                "froot_pft10": 150.0,  # Placeholder
                "targets_met": 4
            }

            self.state.experiments.append(exp)

            # Record experiment to adaptive memory
            if self._memory and self.config.auto_learn:
                try:
                    self._memory.record_experiment(
                        experiment_id=exp.get("name", f"exp_{i}"),
                        base_case=exp.get("base_case", "unknown"),
                        modifications=exp.get("modifications", []),
                        results=exp.get("results", {}),
                        outcome="placeholder"  # Will be updated in refinement
                    )
                    logger.debug(f"Recorded experiment {exp['name']} to memory")
                except Exception as e:
                    logger.warning(f"Could not record experiment to memory: {e}")

        # Transition to REFINEMENT
        self.state.record_phase_transition(
            Phase.TESTING.value, Phase.REFINEMENT.value,
            f"Executed {len(experiments)} experiments"
        )
        self.state.current_phase = Phase.REFINEMENT.value
        logger.info("Testing complete. Advancing to REFINEMENT.")

    def _design_experiment_sequence(self, hypothesis: Dict) -> List[Dict]:
        """Design experiment sequence from hypothesis."""
        design_type = hypothesis.get("experimental_design", "cumulative")
        params = hypothesis.get("parameters_to_test", [])
        base_case = self.state.screening_data.get("best_case", {}).get("case_id", "2678")

        experiments = []

        if design_type == "cumulative":
            # Cumulative: Exp1 = A, Exp2 = A+B, Exp3 = A+B+C
            cumulative_mods = []
            for i, param in enumerate(params):
                cumulative_mods.append({
                    "parameter": param["name"],
                    "old_value": param["current"],
                    "new_value": param["proposed"]
                })
                experiments.append({
                    "name": f"Exp{i+1}_{hypothesis.get('name', 'test')}",
                    "base_case": base_case,
                    "modifications": cumulative_mods.copy(),
                    "expected_outcome": hypothesis.get("expected_outcome", "")
                })

        elif design_type == "factorial":
            # Factorial: All combinations
            import itertools
            for r in range(1, len(params) + 1):
                for combo in itertools.combinations(range(len(params)), r):
                    mods = [
                        {
                            "parameter": params[i]["name"],
                            "old_value": params[i]["current"],
                            "new_value": params[i]["proposed"]
                        }
                        for i in combo
                    ]
                    name_suffix = "+".join([params[i]["name"].split("_")[-1] for i in combo])
                    experiments.append({
                        "name": f"F{len(experiments)+1}_{name_suffix}",
                        "base_case": base_case,
                        "modifications": mods,
                        "expected_outcome": hypothesis.get("expected_outcome", "")
                    })

        return experiments

    # =========================================================================
    # PHASE 6: REFINEMENT - Evaluate and Iterate/Converge
    # =========================================================================
    def _run_refinement(self):
        """
        Phase 6: Evaluate experiment results and decide next action.

        Decision Logic:
        1. If ALL targets met → CONVERGE
        2. If significant progress → UPDATE best, ITERATE
        3. If no progress → Try different hypothesis
        4. If max iterations → STOP with best result

        Outputs:
        - Convergence decision
        - Best experiment selection
        - Next iteration parameters (if continuing)
        """
        logger.info("Evaluating experiment results...")

        # Get latest experiments
        latest_experiments = [e for e in self.state.experiments
                            if e.get("status") != "skipped"]

        if not latest_experiments:
            logger.warning("No experiments to evaluate!")
            self.state.iteration += 1
            self.state.current_phase = Phase.DIAGNOSIS.value
            return

        # Evaluate each experiment and extract lessons
        best_exp = None
        best_targets_met = 0
        total_targets = 8

        for exp in latest_experiments:
            results = exp.get("results", {})
            targets_met = results.get("targets_met", 0)

            logger.info(f"  {exp['name']}: {targets_met}/{total_targets} targets met")

            # Determine outcome for memory
            if targets_met >= total_targets:
                outcome = "SUCCESS"
            elif targets_met >= 6:
                outcome = "PARTIAL_SUCCESS"
            elif targets_met <= 2:
                outcome = "FAILED"
            else:
                outcome = "MARGINAL"

            # Extract lesson via reasoning module (if available)
            if self.reasoning and self.config.auto_learn:
                try:
                    lesson = self.reasoning.extract_lesson(
                        experiment=exp,
                        results=results,
                        outcome=outcome
                    )
                    if lesson:
                        logger.info(f"    Lesson extracted: {lesson.get('lesson', 'N/A')[:50]}...")
                except Exception as e:
                    logger.debug(f"Could not extract lesson: {e}")

            # Update experiment outcome in memory
            if self._memory and self.config.auto_learn:
                try:
                    # Update the experiment record with final outcome
                    self._memory.record_experiment(
                        experiment_id=exp.get("name", "unknown"),
                        base_case=exp.get("base_case", "unknown"),
                        modifications=exp.get("modifications", []),
                        results=results,
                        outcome=outcome
                    )
                except Exception as e:
                    logger.debug(f"Could not update experiment in memory: {e}")

            if targets_met > best_targets_met:
                best_targets_met = targets_met
                best_exp = exp

        # Log refinement to phase logger
        if self._phase_logger:
            try:
                self._phase_logger.set_iteration(self.state.iteration)

                # Determine targets improved/degraded
                prev_best_targets = (self.state.best_experiment or {}).get("results", {}).get("targets_met", 0)
                targets_improved = []
                targets_degraded = []
                if best_targets_met > prev_best_targets:
                    targets_improved = [f"{best_targets_met - prev_best_targets} additional targets"]
                elif best_targets_met < prev_best_targets:
                    targets_degraded = [f"{prev_best_targets - best_targets_met} targets degraded"]

                # Determine next action
                if best_targets_met >= total_targets:
                    next_action = "converge"
                    hypothesis_status = "CONFIRMED"
                elif best_targets_met > prev_best_targets:
                    next_action = "iterate"
                    hypothesis_status = "PARTIAL_SUCCESS"
                else:
                    next_action = "revise_hypothesis"
                    hypothesis_status = "FAILED"

                log_path = self._phase_logger.log_refinement(
                    title=f"Iteration_{self.state.iteration}_Refinement",
                    hypothesis_status=hypothesis_status,
                    targets_improved=targets_improved,
                    targets_degraded=targets_degraded,
                    ai_reasoning="",  # Will be filled by lesson extraction
                    lessons_learned=[],  # Populated by reasoning.extract_lesson()
                    next_action=next_action,
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
            next_action_desc = (
                "CONVERGE (all targets met!)" if best_targets_met >= total_targets
                else f"ITERATE (progress: {best_targets_met}/{total_targets})"
                if best_targets_met > (self.state.best_experiment or {}).get("results", {}).get("targets_met", 0)
                else f"REVISE HYPOTHESIS (no improvement: {best_targets_met}/{total_targets})"
            )
            self._human_review_checkpoint(
                phase="REFINEMENT",
                summary=f"""
Refinement Summary:
  - Best experiment: {best_exp.get('name', 'N/A') if best_exp else 'N/A'}
  - Targets met: {best_targets_met}/{total_targets}
  - Recommended action: {next_action_desc}
""",
                next_phase="NEXT ITERATION" if best_targets_met < total_targets else "CONVERGED",
                options={
                    'c': f'Continue ({next_action_desc})',
                    'q': 'Quit workflow (state saved)',
                }
            )

        # Decision logic
        if best_targets_met >= total_targets:
            # ALL targets met - CONVERGE!
            self.state.converged = True
            self.state.best_experiment = best_exp
            self.state.current_phase = Phase.CONVERGED.value
            logger.info(f"\nALL {total_targets} TARGETS MET! Workflow CONVERGED.")

        elif best_targets_met > (self.state.best_experiment or {}).get("results", {}).get("targets_met", 0):
            # Progress made - update best and continue
            self.state.best_experiment = best_exp
            self.state.iteration += 1
            self.state.current_phase = Phase.DIAGNOSIS.value
            logger.info(f"\nProgress made ({best_targets_met}/{total_targets}). Iterating...")

            self.state.record_phase_transition(
                Phase.REFINEMENT.value, Phase.DIAGNOSIS.value,
                f"Progress: {best_targets_met}/{total_targets} targets"
            )

        else:
            # No progress - try different hypothesis
            self.state.iteration += 1
            self.state.current_phase = Phase.DIAGNOSIS.value
            logger.info(f"\nNo improvement. Trying different approach...")

            self.state.record_phase_transition(
                Phase.REFINEMENT.value, Phase.DIAGNOSIS.value,
                "No improvement, trying new hypothesis"
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

  # Start from specific phase (accepts number, 'phaseN', or name)
  python orchestrator.py --run --start-phase 1 --start-iteration 2
  python orchestrator.py --run --start-phase phase1 --start-iteration 2
  python orchestrator.py --run --start-phase exploration --start-iteration 2

  # Start from diagnosis phase at iteration 3
  python orchestrator.py --init --start-phase 3 --start-iteration 3

  # Resume at different iteration
  python orchestrator.py --resume --start-iteration 5

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
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--no-review", action="store_true", help="Skip human review points")
    parser.add_argument("--no-reasoning", action="store_true", help="Disable Claude API")
    parser.add_argument("--start-phase", type=parse_phase,
                       help="Start from phase (0-7, phase0-phase7, or name like 'exploration')")
    parser.add_argument("--start-iteration", type=int, default=None,
                       help="Start from specific iteration number (use with --init or --resume)")

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
        human_review=not args.no_review,
        use_reasoning=not args.no_reasoning,
        sampling_scheme=args.sampling_scheme or "",
        n_trajectories=args.n_trajectories or 0,
        n_samples=args.n_samples or 0,
        n_levels=args.n_levels,
        n_parameters=args.n_parameters or 0
    )

    # Create output directory
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    # Initialize orchestrator
    orchestrator = CalibrationOrchestrator(config)

    # Handle start phase and iteration overrides
    if args.start_phase:
        orchestrator.state.current_phase = args.start_phase
        logger.info(f"Starting from phase: {args.start_phase}")

    if args.start_iteration is not None:
        orchestrator.state.iteration = args.start_iteration
        logger.info(f"Starting from iteration: {args.start_iteration}")
        # Also set environment variable for PhaseLogger
        os.environ['A2MC_ITERATION'] = str(args.start_iteration)

    # Initialize sampling_design for iteration 2+ (simulations already complete)
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
                logger.info(f"Initialized sampling_design for iteration {args.start_iteration}:")
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


if __name__ == "__main__":
    import sys
    sys.exit(main() or 0)
