#!/usr/bin/env python3
"""
Phase 1 Ensemble Analysis — Analyze existing sensitivity ensemble results

Extracted from orchestrator.py: _analyze_existing_ensemble, _run_monthly_extraction,
_run_y_matrix_extraction, _run_morris_sensitivity_analysis, _build_sensitivity_summary.

Author: Jing Tao with Claude
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def analyze_existing_ensemble(
    total_ensemble: int,
    data_pipeline=None,
) -> Dict:
    """
    Analyze existing sensitivity ensemble results.

    Checks for extracted data, counts available cases, and runs
    Morris sensitivity analysis if extraction is complete.

    Args:
        total_ensemble: Total number of ensemble members expected.
        data_pipeline: Optional DataPipeline instance for fallback extraction.

    Returns:
        Dict with extraction status and sensitivity rankings.
    """
    n_sims = total_ensemble

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
                extraction_result = run_monthly_extraction(data_pipeline=data_pipeline, total_ensemble=n_sims)
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
            extraction_result = run_monthly_extraction(data_pipeline=data_pipeline, total_ensemble=n_sims)
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
            results = run_morris_sensitivity_analysis(results, morris_files)

        elif results.get("extraction_complete", False):
            # Extraction complete but no Y matrices - need to extract from NetCDF
            logger.info("Extraction complete but no Y matrices found. Running Y matrix extraction...")
            results = run_y_matrix_extraction(results)

            # Check again for Y matrices after extraction
            morris_files = list(phase1_output_dir.glob("Morris*biomass*.txt")) if phase1_output_dir.exists() else []
            if morris_files:
                logger.info(f"Found {len(morris_files)} Morris Y matrix files after extraction")
                results["morris_y_matrices"] = [str(f) for f in morris_files]
                results = run_morris_sensitivity_analysis(results, morris_files)
        else:
            # No Y matrices and extraction not marked complete — try extraction anyway
            logger.info("No Morris Y matrices found. Attempting Y matrix extraction...")
            results = run_y_matrix_extraction(results)

            # Check again for Y matrices after extraction
            morris_files = list(phase1_output_dir.glob("Morris*biomass*.txt")) if phase1_output_dir.exists() else []
            if not morris_files:
                morris_files = list(Path('.').glob("Morris*biomass*.txt"))
            if morris_files:
                logger.info(f"Found {len(morris_files)} Morris Y matrix files after extraction")
                results["morris_y_matrices"] = [str(f) for f in morris_files]
                results = run_morris_sensitivity_analysis(results, morris_files)
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


def run_monthly_extraction(
    data_pipeline=None,
    total_ensemble: int = 0,
) -> Dict:
    """
    Extract comprehensive monthly variables from simulation output.

    Calls tools/extract_monthly_variables_FATES.run_monthly_extraction() to
    produce per-case NetCDF files with all variables (biomass, nutrients,
    fluxes, etc.) that Phase 3 diagnostic scripts need.

    Falls back to DataPipeline if direct import fails.

    Args:
        data_pipeline: Optional DataPipeline instance for fallback extraction.
        total_ensemble: Total ensemble size (needed for fallback path).

    Returns:
        Dict with 'status', 'successful_cases', 'failed_cases', 'output_dir'
    """
    # Primary: direct in-process call (efficient, skips already-extracted)
    try:
        from tools.extract_monthly_variables_FATES import run_monthly_extraction as _run_extraction
        logger.info("Starting monthly variable extraction from simulation output...")
        result = _run_extraction()
        if result.get('status') in ['completed', 'partial']:
            logger.info(f"Monthly extraction {result['status']}: "
                        f"{result.get('total_extracted', len(result.get('successful_cases', [])))} cases")
        else:
            logger.warning(f"Monthly extraction failed: {result.get('error', 'unknown')}")
        return result
    except ImportError as e:
        logger.warning(f"Could not import monthly extraction directly: {e}")

    # Fallback: use DataPipeline (subprocess-based, slower but always available)
    if data_pipeline is None:
        return {'status': 'failed', 'error': 'No DataPipeline and direct import unavailable'}

    try:
        logger.info("Falling back to DataPipeline for extraction...")
        # Test first case before attempting all ~4890 cases
        test_result = data_pipeline.extract_case_data("1")
        if not test_result.get('success'):
            error_msg = test_result.get('error', 'extraction failed')
            logger.error(f"Test extraction of case 1 failed: {error_msg}")
            if 'xarray' in str(error_msg) or 'ModuleNotFoundError' in str(error_msg):
                logger.error("Missing Python packages. On Perlmutter, run:")
                logger.error("  module load python")
                logger.error("  # OR: conda activate <your_env>")
            return {'status': 'failed', 'error': error_msg}

        n_sims = total_ensemble
        case_ids = [str(i) for i in range(1, n_sims + 1)]
        results = data_pipeline.extract_batch(case_ids)
        n_success = sum(1 for r in results if r.get('success'))
        status = 'completed' if n_success >= len(case_ids) * 0.9 else 'partial'
        return {'status': status, 'total_extracted': n_success}
    except Exception as e:
        logger.error(f"Error during monthly extraction: {e}")
        return {'status': 'failed', 'error': str(e)}


def run_y_matrix_extraction(results: Dict) -> Dict:
    """
    Extract Y matrices from simulation outputs for Morris analysis.

    Args:
        results: Current results dict to update.

    Returns:
        Updated results dict with extraction info.
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


def run_morris_sensitivity_analysis(results: Dict, morris_files: List[Path]) -> Dict:
    """
    Run Morris sensitivity analysis on extracted Y matrices.

    Args:
        results: Current results dict to update.
        morris_files: List of Morris Y matrix files.

    Returns:
        Updated results dict with sensitivity rankings.
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


def build_sensitivity_summary(exploration_data: Dict) -> str:
    """
    Build a human-readable summary of sensitivity analysis results.

    Args:
        exploration_data: Dict containing sensitivity rankings.

    Returns:
        Markdown-formatted summary string.
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
