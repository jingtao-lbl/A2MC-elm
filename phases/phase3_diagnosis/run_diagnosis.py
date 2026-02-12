#!/usr/bin/env python3
"""
Run Diagnosis - A2MC Phase 3 Diagnosis Module

Orchestrates diagnostic scripts to analyze model-data mismatch.
Provides structured diagnostic data for AI reasoning.

Integrates with:
  - read_case_parameters.py for parameter reading
  - check_edge_parameters.py for edge detection
  - compare_case_parameters.py for case comparison
  - diagnose_pft_limitations.py for PFT-specific diagnosis
  - compare_targets.py for target comparison
  - analyze_nutrient_balance.py for N/P mass balance analysis
  - reasoning.py for AI analysis

Usage:
    # As module (from orchestrator)
    from phases.phase3_diagnosis.run_diagnosis import run_diagnosis, DiagnosisConfig
    result = run_diagnosis(screening_data, config)

    # Standalone
    python run_diagnosis.py --screening-result screening.json --morris-file params.txt

Created: February 2026
Author: Jing Tao with Claude
"""

import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logger = logging.getLogger(__name__)

# Import diagnostic modules
try:
    from phases.phase3_diagnosis.read_case_parameters import (
        read_case_parameters,
        get_parameters_with_bounds,
        load_param_names,
        load_param_bounds
    )
    from phases.phase3_diagnosis.check_edge_parameters import (
        check_parameters_at_edge,
        categorize_edge_parameters,
        get_edge_summary_for_ai,
        identify_redesign_candidates
    )
    from phases.phase3_diagnosis.compare_case_parameters import (
        compare_cases,
        get_largest_differences,
        get_comparison_summary_for_ai,
        compare_multiple_cases
    )
    from phases.phase3_diagnosis.compare_targets import (
        compare_biomass_targets,
        get_target_summary_for_ai
    )
    from phases.phase3_diagnosis.diagnose_pft_limitations import (
        run_pft_diagnosis,
        get_diagnosis_summary_for_ai
    )
    from phases.phase3_diagnosis.analyze_nutrient_balance import (
        extract_nutrient_budget,
        calculate_budget_closure,
        analyze_pft_competition,
        identify_nutrient_sinks,
        get_balance_summary_for_ai,
        results_to_dict as nutrient_balance_results_to_dict
    )
    HAS_DIAGNOSIS_TOOLS = True
except ImportError as e:
    logger.warning(f"Could not import diagnosis tools: {e}")
    HAS_DIAGNOSIS_TOOLS = False

try:
    from tools.fates_output_variables import resolve_target_name
except ImportError:
    # Fallback if registry not available
    def resolve_target_name(name):
        return {'fineroot': 'froot'}.get(name, name)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class DiagnosisConfig:
    """Configuration for Phase 3 diagnosis."""
    # Morris ensemble files
    morris_file: Optional[str] = None
    param_names_file: Optional[str] = None
    param_bounds_file: Optional[str] = None

    # Case settings
    best_case_id: Optional[int] = None
    comparison_case_ids: List[int] = field(default_factory=list)

    # PFT settings
    pft_ids: List[int] = field(default_factory=lambda: [7, 9, 10])

    # Targets (can be dict or path to file)
    targets: Optional[Dict] = None
    targets_file: Optional[str] = None

    # NC file for simulation output (optional - for PFT diagnosis)
    nc_file: Optional[str] = None

    # Edge detection threshold
    edge_threshold_pct: float = 1.0

    # Number of top differences to report
    top_n_differences: int = 20

    # Nutrient for mass balance analysis ('P' or 'N')
    nutrient: str = 'P'


@dataclass
class DiagnosisResult:
    """Structured results from Phase 3 diagnosis."""
    # Case being diagnosed
    case_id: int

    # Parameter values for best case
    parameters: Dict[str, float] = field(default_factory=dict)

    # Edge analysis
    edge_analysis: Dict = field(default_factory=dict)
    edge_summary: str = ""
    redesign_candidates: List[Dict] = field(default_factory=list)

    # Case comparison (if comparison cases provided)
    case_comparisons: Dict[int, Dict] = field(default_factory=dict)
    comparison_summary: str = ""

    # Target comparison (if NC file provided)
    target_comparison: Dict = field(default_factory=dict)
    target_summary: str = ""

    # PFT diagnosis (if NC file provided)
    pft_diagnoses: Dict[int, Dict] = field(default_factory=dict)
    pft_summary: str = ""

    # Nutrient mass balance (if NC file provided)
    nutrient_balance: Dict = field(default_factory=dict)
    nutrient_balance_summary: str = ""

    # Combined summary for AI
    combined_summary: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def get_ai_context(self) -> str:
        """Get combined context for AI reasoning."""
        sections = []

        if self.edge_summary:
            sections.append(self.edge_summary)

        if self.comparison_summary:
            sections.append(self.comparison_summary)

        if self.target_summary:
            sections.append(self.target_summary)

        if self.pft_summary:
            sections.append(self.pft_summary)

        if self.nutrient_balance_summary:
            sections.append(self.nutrient_balance_summary)

        return "\n\n".join(sections) if sections else self.combined_summary


# =============================================================================
# Main Diagnosis Functions
# =============================================================================

def run_diagnosis(
    screening_data: Dict,
    config: Optional[DiagnosisConfig] = None,
    verbose: bool = True
) -> DiagnosisResult:
    """
    Run Phase 3 diagnosis on screening results.

    This is the main entry point for Phase 3 diagnosis.

    Parameters
    ----------
    screening_data : Dict
        Screening results from Phase 2, containing:
        - best_case: {case_id, cost, simulated, ...}
        - top_cases: List of top case dicts
        - targets: Target definitions
        - n_cases_evaluated: Total cases
    config : DiagnosisConfig, optional
        Diagnosis configuration
    verbose : bool
        Print progress

    Returns
    -------
    DiagnosisResult
        Structured diagnosis results

    Example
    -------
    >>> from phases.phase3_diagnosis.run_diagnosis import run_diagnosis, DiagnosisConfig
    >>> config = DiagnosisConfig(
    ...     morris_file="/path/to/morris_params.txt",
    ...     param_names_file="/path/to/param_names.txt",
    ...     pft_ids=[7, 9, 10]
    ... )
    >>> result = run_diagnosis(screening_data, config)
    >>> print(result.edge_summary)
    """
    if not HAS_DIAGNOSIS_TOOLS:
        logger.warning("Diagnosis tools not available - returning minimal result")
        return DiagnosisResult(
            case_id=screening_data.get('best_case', {}).get('case_id', 0),
            combined_summary="Diagnosis tools not available"
        )

    # Setup config
    config = config or DiagnosisConfig()

    # Normalize target variable names (e.g., 'fineroot' → 'froot')
    if config.targets:
        normalized = {}
        for pft_key, var_dict in config.targets.items():
            normalized[pft_key] = {}
            for var_name, value in var_dict.items():
                normalized[pft_key][resolve_target_name(var_name)] = value
        config.targets = normalized

    # Extract best case from screening data
    best_case = screening_data.get('best_case', {})
    case_id = config.best_case_id or best_case.get('case_id', 0)

    if verbose:
        print("\n" + "=" * 60)
        print("A2MC PHASE 3: DIAGNOSIS")
        print("=" * 60)
        print(f"Best case from screening: #{case_id}")

    result = DiagnosisResult(case_id=case_id)

    # Step 1: Read parameters for best case
    if config.morris_file and config.param_names_file:
        if verbose:
            print("\nStep 1: Reading parameters for best case...")

        try:
            params = read_case_parameters(
                case_id=case_id,
                morris_file=config.morris_file,
                param_names=config.param_names_file
            )
            result.parameters = params

            if verbose:
                print(f"  Read {len(params)} parameters")
        except Exception as e:
            logger.warning(f"Could not read parameters: {e}")

    # Step 2: Check edge parameters
    if config.morris_file and config.param_names_file and config.param_bounds_file:
        if verbose:
            print("\nStep 2: Checking edge parameters...")

        try:
            edge_result = check_parameters_at_edge(
                case_id=case_id,
                morris_file=config.morris_file,
                param_names=config.param_names_file,
                param_bounds=config.param_bounds_file,
                threshold_pct=config.edge_threshold_pct
            )
            result.edge_analysis = edge_result
            result.edge_summary = get_edge_summary_for_ai(edge_result)
            result.redesign_candidates = identify_redesign_candidates(edge_result)

            n_at_lower = len(edge_result.get('parameters_at_lower_bound', []))
            n_at_upper = len(edge_result.get('parameters_at_upper_bound', []))

            if verbose:
                print(f"  Parameters at lower bound: {n_at_lower}")
                print(f"  Parameters at upper bound: {n_at_upper}")
                print(f"  Redesign candidates: {len(result.redesign_candidates)}")
        except Exception as e:
            logger.warning(f"Could not check edge parameters: {e}")

    # Step 3: Compare with other top cases
    if config.comparison_case_ids and config.morris_file and config.param_names_file:
        if verbose:
            print(f"\nStep 3: Comparing with {len(config.comparison_case_ids)} other cases...")

        try:
            if config.param_bounds_file:
                comparisons = compare_multiple_cases(
                    case_ids=config.comparison_case_ids,
                    reference_case=case_id,
                    morris_file=config.morris_file,
                    param_names=config.param_names_file,
                    param_bounds=config.param_bounds_file
                )
            else:
                comparisons = {}
                for comp_id in config.comparison_case_ids[:5]:  # Limit to 5
                    comp = compare_cases(
                        case1_id=case_id,
                        case2_id=comp_id,
                        morris_file=config.morris_file,
                        param_names=config.param_names_file
                    )
                    comparisons[comp_id] = comp

            result.case_comparisons = comparisons

            # Generate summary for first comparison
            if comparisons:
                first_key = list(comparisons.keys())[0]
                result.comparison_summary = get_comparison_summary_for_ai(comparisons[first_key])

            if verbose:
                print(f"  Compared {len(comparisons)} cases")
        except Exception as e:
            logger.warning(f"Could not compare cases: {e}")

    # Step 4: Compare targets (if NC file provided)
    if config.nc_file and config.targets:
        if verbose:
            print("\nStep 4: Comparing simulated vs observed targets...")

        try:
            target_result = compare_biomass_targets(
                nc_file=config.nc_file,
                targets=config.targets,
                pft_ids=config.pft_ids
            )
            result.target_comparison = target_result
            result.target_summary = get_target_summary_for_ai(target_result)

            if verbose:
                summary = target_result.get('summary', {})
                print(f"  Pass rate: {summary.get('pass_rate', 0):.1f}%")
                print(f"  Failing targets: {summary.get('failing', 0)}")
        except Exception as e:
            logger.warning(f"Could not compare targets: {e}")

    # Step 5: Run PFT-specific diagnosis (if NC file provided)
    if config.nc_file and config.targets:
        if verbose:
            print("\nStep 5: Running PFT-specific diagnosis...")

        pft_summaries = []
        for pft_id in config.pft_ids:
            pft_key = f'PFT{pft_id}'
            pft_targets = config.targets.get(pft_key, {})

            if not pft_targets:
                continue

            try:
                pft_diagnosis = run_pft_diagnosis(
                    nc_file=config.nc_file,
                    pft_id=pft_id,
                    targets=pft_targets
                )
                result.pft_diagnoses[pft_id] = pft_diagnosis
                pft_summaries.append(get_diagnosis_summary_for_ai(pft_diagnosis))

                if verbose:
                    print(f"  PFT#{pft_id} diagnosis complete")
            except Exception as e:
                logger.warning(f"Could not diagnose PFT#{pft_id}: {e}")

        if pft_summaries:
            result.pft_summary = "\n\n".join(pft_summaries)

    # Step 6: Nutrient mass balance (if NC file provided)
    if config.nc_file:
        if verbose:
            print(f"\nStep 6: Analyzing {config.nutrient} mass balance...")

        try:
            budget = extract_nutrient_budget(
                config.nc_file, config.nutrient, config.pft_ids
            )
            closure = calculate_budget_closure(budget)

            competition = None
            if config.pft_ids:
                competition = analyze_pft_competition(
                    config.nc_file, config.pft_ids, config.nutrient
                )

            sinks = identify_nutrient_sinks(budget)

            result.nutrient_balance = nutrient_balance_results_to_dict(
                budget, closure, competition, sinks
            )
            result.nutrient_balance_summary = get_balance_summary_for_ai(
                budget, closure, competition, sinks
            )

            if verbose:
                print(f"  Budget closure: {'OK' if closure.closure_acceptable else 'FAILED'}")
                print(f"  Residual: {closure.relative_residual:.1%} of total input")
                if sinks.leaching_exceeds_uptake:
                    print(f"  WARNING: Leaching exceeds plant uptake!")
        except Exception as e:
            logger.warning(f"Could not run nutrient balance: {e}")

    # Build combined summary
    result.combined_summary = result.get_ai_context()

    if verbose:
        print("\n" + "=" * 60)
        print("DIAGNOSIS COMPLETE")
        print("=" * 60)
        if result.redesign_candidates:
            print(f"\nRedesign candidates ({len(result.redesign_candidates)}):")
            for cand in result.redesign_candidates[:5]:
                print(f"  - {cand.get('name')}: {cand.get('suggestion')}")

    return result


def run_diagnosis_for_orchestrator(
    screening_data: Dict,
    morris_file: str,
    param_names_file: str,
    param_bounds_file: Optional[str] = None,
    nc_file: Optional[str] = None,
    targets: Optional[Dict] = None,
    pft_ids: List[int] = None,
    top_cases_for_comparison: int = 5,
    verbose: bool = True
) -> DiagnosisResult:
    """
    Convenience function for orchestrator integration.

    Extracts relevant info from screening data and runs diagnosis.

    Parameters
    ----------
    screening_data : Dict
        Screening results from Phase 2
    morris_file : str
        Path to Morris parameter file
    param_names_file : str
        Path to parameter names file
    param_bounds_file : str, optional
        Path to parameter bounds file
    nc_file : str, optional
        Path to simulation output for PFT diagnosis
    targets : Dict, optional
        Validation targets
    pft_ids : List[int], optional
        PFT IDs to diagnose (default: [7, 9, 10])
    top_cases_for_comparison : int
        Number of top cases to compare (default: 5)
    verbose : bool
        Print progress

    Returns
    -------
    DiagnosisResult
        Structured diagnosis results
    """
    if pft_ids is None:
        pft_ids = [7, 9, 10]

    # Extract comparison case IDs from top cases
    # Orchestrator uses 'best_cases', older code may use 'top_cases'
    top_cases = screening_data.get('best_cases', screening_data.get('top_cases', []))
    comparison_ids = [c.get('case_num', c.get('case_id'))
                      for c in top_cases[1:top_cases_for_comparison + 1]]
    comparison_ids = [c for c in comparison_ids if c]  # Filter None

    config = DiagnosisConfig(
        morris_file=morris_file,
        param_names_file=param_names_file,
        param_bounds_file=param_bounds_file,
        best_case_id=screening_data.get('best_case', {}).get('case_id'),
        comparison_case_ids=comparison_ids,
        pft_ids=pft_ids,
        targets=targets,
        nc_file=nc_file
    )

    return run_diagnosis(screening_data, config, verbose)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    """CLI interface for Phase 3 diagnosis."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Run A2MC Phase 3 diagnosis on screening results'
    )
    parser.add_argument('--screening-result', '-s', required=True,
                        help='JSON file with screening results')
    parser.add_argument('--morris-file', '-m', required=True,
                        help='Morris parameter file')
    parser.add_argument('--param-names', '-p', required=True,
                        help='Parameter names file')
    parser.add_argument('--param-bounds', '-b',
                        help='Parameter bounds file')
    parser.add_argument('--nc-file', '-n',
                        help='NetCDF simulation output file')
    parser.add_argument('--targets', '-t',
                        help='Targets JSON file')
    parser.add_argument('--pft-ids', type=int, nargs='+', default=[7, 9, 10],
                        help='PFT IDs to diagnose')
    parser.add_argument('--nutrient', choices=['P', 'N'], default='P',
                        help='Nutrient for mass balance analysis (default: P)')
    parser.add_argument('--output', '-o',
                        help='Output JSON file')
    parser.add_argument('--summary', action='store_true',
                        help='Print summary for AI')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Load screening results
    with open(args.screening_result) as f:
        screening_data = json.load(f)

    # Load targets if provided
    targets = None
    if args.targets:
        with open(args.targets) as f:
            targets = json.load(f)

    # Build config
    config = DiagnosisConfig(
        morris_file=args.morris_file,
        param_names_file=args.param_names,
        param_bounds_file=args.param_bounds,
        nc_file=args.nc_file,
        targets=targets,
        pft_ids=args.pft_ids,
        nutrient=args.nutrient
    )

    # Run diagnosis
    result = run_diagnosis(screening_data, config)

    # Output
    if args.summary:
        print("\n" + "=" * 60)
        print("AI CONTEXT SUMMARY")
        print("=" * 60)
        print(result.get_ai_context())
    elif args.output:
        with open(args.output, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"\nResults written to: {args.output}")
    else:
        print(json.dumps(result.to_dict(), indent=2))

    return result


if __name__ == '__main__':
    main()
