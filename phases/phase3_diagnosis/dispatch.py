#!/usr/bin/env python3
"""
Phase 3 Diagnostic Dispatch — Execute AI-Requested Diagnostics

Extracted from orchestrator.py _execute_requested_diagnostics().
Dispatches 30+ diagnostic tools requested by the AI during diagnosis.

Author: Jing Tao with Claude
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def execute_requested_diagnostics(
    requested_diagnostics: List[Dict],
    screening_data: Dict,
    config=None,
    phase_logger=None,
) -> Optional[Dict]:
    """
    Execute diagnostic analyses requested by Claude AI.

    This enables a two-phase diagnosis where Claude first analyzes
    available data, then requests specific diagnostics for deeper insight.

    Args:
        requested_diagnostics: List of diagnostic requests from Claude
            [{"tool": "check_edge_parameters", "reason": "...", "priority": "high", "args": {...}}]
        screening_data: Screening results from Phase 2
        config: CalibrationOrchestrator.config (needs .targets attribute) — used for
            load_morris_ensemble_data / get_morris_param_names in the fallback branch.
        phase_logger: PhaseLogger instance (for figure output directory)

    Returns:
        Dict with combined diagnostic results, or None if all fail
    """
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
                # Build glob from the configured CASE_NAME_PATTERN so we
                # match whatever naming the current round uses (R3:
                # PtCNPEn{N}_TRANS, R4: PtCNPEn{N}PrescP_TRANS, etc.).
                # Substitute case number, leave PHASE as a wildcard so
                # any analysis phase suffix (TRANS/RGSP/...) is matched.
                case_name_glob = a2mc_config.CASE_NAME_PATTERN.format(
                    N=case_id, PHASE='*'
                )
                pattern = f"{case_name_glob}_all_variables*.nc"
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
                        closure = calculate_budget_closure(budget)
                        competition = analyze_pft_competition(
                            nc_file=nc_file, pft_ids=pft_ids, nutrient=nutrient
                        ) if pft_ids else None
                        sinks = identify_nutrient_sinks(budget)
                        budget_summary = get_balance_summary_for_ai(budget, closure, competition, sinks)
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
                        import numpy as np
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
                        import numpy as np
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
                                    data_dict[var] = v[:]
                                elif v.ndim == 2 and 'time' in str(dims):
                                    arr = v[:]
                                    second_dim_size = arr.shape[1]
                                    if second_dim_size == 12:
                                        for pid in pft_ids:
                                            idx = pid - 1
                                            data_dict[f"{var}_PFT{pid}"] = arr[:, idx]
                                    elif second_dim_size == 156:
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
                    extracted_dir = a2mc_config.EXTRACTED_DATA
                    if extracted_dir and Path(extracted_dir).exists():
                        simple_targets = {}
                        obs_uncert = {}
                        try:
                            from phases.phase2_screening.screen_ensemble import load_kougarok_targets
                            raw_targets = load_kougarok_targets()
                            simple_targets = {
                                name: {'observed': t.observed, 'uncertainty': t.uncertainty}
                                for name, t in raw_targets.items()
                            }
                            for name, t in raw_targets.items():
                                if hasattr(t, 'obs_std') and t.obs_std is not None:
                                    obs_uncert[name] = t.obs_std
                        except Exception:
                            simple_targets = tool_args.get('targets', {})
                        # Determine output path (phase_results, not logs)
                        fig_dir = None
                        if a2mc_config.USE_CASE_DIR:
                            fig_dir = a2mc_config.phase_results_dir("phase3_diagnosis")
                            fig_dir.mkdir(parents=True, exist_ok=True)
                        if not fig_dir:
                            fig_dir = Path(extracted_dir)
                        output_path = str(Path(fig_dir) / 'ensemble_biomass_top_cases.png')
                        top_n = max(tool_args.get('top_n', 100), 100)

                        # Reuse Phase 2 ranked_cases if available (avoids
                        # re-ranking all 4890 cases from scratch)
                        pre_ranked = screening_data.get('ranked_cases') if screening_data else None
                        if pre_ranked:
                            from phases.phase2_screening.plot_screening import (
                                plot_ensemble_biomass
                            )
                            logger.info(f"  Using pre-ranked cases from screening ({len(pre_ranked)} cases)")
                            fig_path = plot_ensemble_biomass(
                                data_dir=extracted_dir,
                                ranked_cases=pre_ranked,
                                targets=simple_targets,
                                pft_ids=pft_ids,
                                output_path=output_path,
                                top_n=top_n,
                                obs_uncertainty=obs_uncert if obs_uncert else None,
                            )
                        else:
                            from phases.phase2_screening.plot_screening import (
                                plot_ensemble_biomass_from_dir
                            )
                            logger.info("  No pre-ranked cases; ranking from scratch")
                            fig_path = plot_ensemble_biomass_from_dir(
                                data_dir=extracted_dir,
                                targets=simple_targets,
                                pft_ids=pft_ids,
                                output_path=output_path,
                                top_n=top_n,
                                obs_uncertainty=obs_uncert if obs_uncert else None,
                            )
                        if fig_path:
                            results['ensemble_biomass_figure'] = fig_path
                            summaries.append(f"## Ensemble Biomass Figure\nSaved: {fig_path}")
                    else:
                        logger.warning("  plot_ensemble_biomass: extracted data dir not available")
                except Exception as e:
                    logger.warning(f"  plot_ensemble_biomass failed: {e}")
                    results[f'{tool}_error'] = {'error': str(e)}

            # ---- Ensemble-level hypothesis tests (auto-discovered) ----
            else:
                from phases.phase3_diagnosis import load_ensemble_test
                test_fn = load_ensemble_test(tool)
                if test_fn is not None:
                    try:
                        from phases.phase4_hypothesis.test_with_existing_data import (
                            load_morris_ensemble_data,
                            get_morris_param_names,
                        )
                        param_matrix, y_outputs, _ensemble_ranges = load_morris_ensemble_data(config)
                        param_names = get_morris_param_names(config)
                        test_config = {
                            'param_names': param_names,
                            'pft_ids': pft_ids,
                            'use_case_dir': str(a2mc_config.USE_CASE_DIR),
                        }
                        result = test_fn(param_matrix, y_outputs, screening_data, test_config)
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
