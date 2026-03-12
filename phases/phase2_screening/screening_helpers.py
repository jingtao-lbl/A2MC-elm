#!/usr/bin/env python3
"""
Phase 2 Screening Helpers — Load, perform, and analyze screening results

Extracted from orchestrator.py: _load_screening_results, _perform_screening,
_generate_screening_analysis.

Author: Jing Tao with Claude
"""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def load_screening_results(results_file: Path) -> Dict:
    """Load pre-computed screening results from a CSV file.

    Args:
        results_file: Path to the screening results CSV.

    Returns:
        Dict with parsed screening data (best_cases, case_numbers, etc.).
    """
    screening_data = {
        "n_cases_evaluated": 4329,
        "results_file": str(results_file),
        "best_cases": [],
        "target_performance": {},
        "case_numbers": [],  # actual case IDs from the CSV
    }

    # Compute n_targets from site-specific target definitions
    try:
        from phases.phase2_screening.screen_ensemble import load_kougarok_targets
        screening_data["n_targets"] = len(load_kougarok_targets())
    except Exception:
        screening_data["n_targets"] = 6  # fallback

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


def perform_screening(targets, total_ensemble: int) -> Dict:
    """
    Perform new screening analysis against targets.

    Calls phases/phase2_screening/screen_ensemble.py to:
    1. Load simulation outputs from EXTRACTED_DATA
    2. Rank against validation targets
    3. Return structured results

    Args:
        targets: ValidationTargets dataclass (not used directly; targets loaded
                 from site-specific config internally).
        total_ensemble: Total number of ensemble members.

    Returns:
        Dict with screening results (best_cases, target_performance, etc.).
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
            "n_targets": len(screening_targets),
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
            # Build obs_uncertainty dict from Target.obs_std (if available)
            obs_uncertainty = {}
            for name, t in screening_targets.items():
                if hasattr(t, 'obs_std') and t.obs_std is not None:
                    obs_uncertainty[name] = t.obs_std
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
                fig_dir = a2mc_config.phase_results_dir("phase2_screening")
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
                obs_uncertainty=obs_uncertainty if obs_uncertainty else None,
            )
            if fig_path:
                screening_data['figure_paths'] = [fig_path]
                logger.info(f"  Ensemble biomass figure: {fig_path}")
            # Save top-ranked cases so Phase 3 can reuse without re-ranking
            # all 4890 cases from scratch.  Keep top 200 (covers any
            # reasonable top_n while keeping state file under 20KB).
            screening_data['ranked_cases'] = ranked_cases[:200]
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


def generate_screening_analysis(
    screening_data: Dict,
    reasoning_module,
    exploration_data: Optional[Dict] = None,
) -> str:
    """
    Generate AI analysis of screening results.

    Args:
        screening_data: Results from perform_screening().
        reasoning_module: ReasoningModule instance for Claude API calls.
        exploration_data: Optional exploration data with sensitivity rankings.

    Returns:
        Markdown-formatted AI analysis string.
    """
    # Extract key metrics
    n_cases = screening_data.get("n_cases_evaluated", 0)
    best_case = screening_data.get("best_case", {})
    best_cases = screening_data.get("best_cases", [])[:10]
    target_perf = screening_data.get("target_performance", {})
    max_satisfied = screening_data.get("max_targets_satisfied", 0)
    n_targets = screening_data.get("n_targets", best_case.get("targets_met", 0))

    # Build summary for AI
    summary = f"""## Screening Results Summary

**Ensemble Size:** {n_cases} cases evaluated
**Best Case:** #{best_case.get('case_id', 'N/A')}
- Composite RMSRE: {best_case.get('composite_rmsre', 'N/A'):.4f}
- Targets Met: {best_case.get('targets_met', 0)}/{n_targets}

**Target Satisfaction Distribution:**
"""
    for n_tgt, count in sorted(target_perf.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0, reverse=True):
        pct = count / n_cases * 100 if n_cases > 0 else 0
        summary += f"- {n_tgt} targets: {count} cases ({pct:.1f}%)\n"

    summary += f"""
**Top 10 Cases:**
| Rank | Case | RMSRE | Targets Met |
|------|------|-------|-------------|
"""
    for i, case in enumerate(best_cases):
        summary += f"| {i+1} | #{case.get('case_num', '?')} | {case.get('cost', 0):.4f} | {case.get('n_satisfied', 0)}/{n_targets} |\n"

    # Get sensitivity rankings from exploration phase if available
    sensitivity_info = ""
    if exploration_data:
        rankings = exploration_data.get('sensitivity_rankings', {})
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
2. **Calibration Challenges:** Why might no cases achieve all {n_targets} targets?
3. **Promising Directions:** Based on the top cases, what parameter adjustments might help?
4. **Recommendations:** What should the diagnosis phase focus on?

Keep your analysis concise (3-4 sentences per section)."""

    try:
        response = reasoning_module.query(prompt, max_tokens=1500)
        return response
    except Exception as e:
        # Fallback to rule-based summary
        return f"""## Automated Analysis

**Key Observations:**
- Best case achieves {best_case.get('targets_met', 0)}/{n_targets} targets with RMSRE {best_case.get('composite_rmsre', 'N/A'):.4f}
- {target_perf.get('0', 0)} cases ({target_perf.get('0', 0)/n_cases*100:.1f}%) meet zero targets
- Maximum targets satisfied by any case: {max_satisfied}

**Calibration Challenge:**
Multi-objective optimization with {n_targets} biomass targets across 3 PFTs creates trade-offs where improving one PFT often degrades another.

**Recommendation:**
Focus diagnosis on identifying which PFT combinations conflict and whether parameter bounds need expansion.

*Note: AI analysis unavailable ({e})*"""
