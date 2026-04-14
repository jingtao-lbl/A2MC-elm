#!/usr/bin/env python3
"""
Cross-Round Comparison Tool for Subset Replay

Compares simulation results between two calibration rounds case-by-case.
Designed for subset_replay rounds where the same parameter sets are run
under different conditions (e.g., R3 dynamic P vs R4 prescribed P).

Reads calibration_rounds.yaml for both rounds' paths, loads the subset
replay manifest to identify paired cases, then evaluates each pair
against validation targets.

Usage (CLI):
    python tools/compare_rounds.py \\
        --source-round 3 --target-round 4 \\
        --yaml use_cases/Kougarok/config/calibration_rounds.yaml \\
        --output-dir /tmp/cross_round/

Usage (Python API):
    from tools.compare_rounds import compare_rounds
    result = compare_rounds(source_round=3, target_round=4,
                            yaml_path='...', output_dir='...')

Author: Jing Tao with Claude
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CasePairResult:
    """Result for one paired source-vs-target round case."""
    case_num: int
    source_rank: int
    source_cost: float
    source_n_satisfied: int
    r_src_values: Dict[str, float]    # target_name -> simulated value
    r_tgt_values: Dict[str, float]
    r_src_eval: Dict                   # full evaluate_case result
    r_tgt_eval: Dict
    delta: Dict[str, float]            # target_name -> (tgt - src)
    rel_change: Dict[str, float]       # target_name -> (tgt - src) / |src|
    src_satisfied: Dict[str, bool]
    tgt_satisfied: Dict[str, bool]
    status: str = 'ok'                 # 'ok', 'src_missing', 'tgt_missing'


@dataclass
class CrossRoundResult:
    """Aggregate cross-round comparison result."""
    source_round: int
    target_round: int
    n_cases_total: int
    n_cases_paired: int
    n_cases_src_missing: int
    n_cases_tgt_missing: int

    case_results: List[CasePairResult]

    per_target_stats: Dict[str, Dict] = field(default_factory=dict)
    improved_count: Dict[str, int] = field(default_factory=dict)
    degraded_count: Dict[str, int] = field(default_factory=dict)
    satisfaction_changes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    rank_correlation: float = 0.0

    summary_dict: Dict = field(default_factory=dict)
    figure_paths: List[str] = field(default_factory=list)
    output_dir: str = ''


# ---------------------------------------------------------------------------
# YAML / config helpers
# ---------------------------------------------------------------------------

def _expand_vars(s: str) -> str:
    """Expand ${VAR} references in a string using os.environ."""
    return os.path.expandvars(s) if s else s


def _load_round_config(yaml_path: str, round_num: int) -> Dict:
    """Load and resolve paths for a given round from calibration_rounds.yaml."""
    import yaml
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    rounds = data.get('rounds', {})
    rnd = rounds.get(round_num)
    if rnd is None:
        raise ValueError(f"Round {round_num} not found in {yaml_path}")

    paths = rnd.get('paths', {})
    if not paths:
        raise ValueError(f"Round {round_num} has no 'paths' block in {yaml_path}")

    return {
        'round': round_num,
        'extracted_data': _expand_vars(paths.get('extracted_data', '')),
        'ensemble_output': _expand_vars(paths.get('ensemble_output', '')),
        'case_name_pattern': paths.get('case_name_pattern', ''),
        'param_dir': _expand_vars(paths.get('param_dir', '')),
        'param_pattern': paths.get('param_pattern', ''),
        'sampling_scheme': rnd.get('sampling_scheme', ''),
        'overrides': rnd.get('overrides', {}),
        'source_round': rnd.get('source_round'),
    }


def _load_manifest(ensemble_output: str) -> List[Dict]:
    """Load subset_replay_manifest.json from ensemble output dir.

    Returns list of case mapping entries sorted by source_rank.
    """
    manifest_path = Path(ensemble_output) / 'subset_replay_manifest.json'
    if not manifest_path.exists():
        logger.warning(f"Manifest not found: {manifest_path}")
        return []
    with open(manifest_path) as f:
        manifest = json.load(f)
    entries = manifest.get('case_mapping', [])
    entries.sort(key=lambda e: e.get('source_rank', 9999))
    return entries


def _load_case_list(ensemble_output: str) -> List[int]:
    """Load case numbers from subset_replay_case_list.txt (fallback)."""
    case_list_path = Path(ensemble_output) / 'subset_replay_case_list.txt'
    if not case_list_path.exists():
        return []
    cases = []
    with open(case_list_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                cases.append(int(line))
            except ValueError:
                continue
    return cases


def _build_case_name(pattern: str, case_num: int, phase: str = 'TRANS') -> str:
    """Resolve case_name_pattern with {N} and {PHASE} placeholders."""
    return pattern.replace('{N}', str(case_num)).replace('{PHASE}', phase)


# ---------------------------------------------------------------------------
# Per-case evaluation
# ---------------------------------------------------------------------------

def _evaluate_pair(
    case_num: int,
    src_config: Dict,
    tgt_config: Dict,
    targets: Dict,
    obs_idx: int,
    manifest_entry: Optional[Dict] = None,
) -> CasePairResult:
    """Evaluate one source/target pair."""
    from tools.evaluate_case import extract_case_values, evaluate_case, find_extracted_nc

    src_rank = manifest_entry.get('source_rank', 0) if manifest_entry else 0
    src_cost = manifest_entry.get('source_cost', 0.0) if manifest_entry else 0.0
    src_n_sat = manifest_entry.get('source_n_satisfied', 0) if manifest_entry else 0

    # Locate NC files
    src_case_name = _build_case_name(src_config['case_name_pattern'], case_num)
    tgt_case_name = _build_case_name(tgt_config['case_name_pattern'], case_num)

    src_nc = find_extracted_nc(src_case_name, [Path(src_config['extracted_data'])])
    tgt_nc = find_extracted_nc(tgt_case_name, [Path(tgt_config['extracted_data'])])

    empty_vals = {}
    empty_eval = {'targets_met': 0, 'total_targets': len(targets),
                  'composite_cost': float('inf'), 'satisfied': {}}

    if src_nc is None:
        return CasePairResult(
            case_num=case_num, source_rank=src_rank, source_cost=src_cost,
            source_n_satisfied=src_n_sat,
            r_src_values=empty_vals, r_tgt_values=empty_vals,
            r_src_eval=empty_eval, r_tgt_eval=empty_eval,
            delta={}, rel_change={},
            src_satisfied={}, tgt_satisfied={},
            status='src_missing')

    if tgt_nc is None:
        # Still extract source values for context
        src_vals = extract_case_values(src_nc, targets, obs_idx)
        src_eval = evaluate_case(src_nc, targets, obs_idx)
        return CasePairResult(
            case_num=case_num, source_rank=src_rank, source_cost=src_cost,
            source_n_satisfied=src_n_sat,
            r_src_values=src_vals, r_tgt_values=empty_vals,
            r_src_eval=src_eval, r_tgt_eval=empty_eval,
            delta={}, rel_change={},
            src_satisfied=src_eval.get('satisfied', {}), tgt_satisfied={},
            status='tgt_missing')

    # Both files found — full evaluation
    src_vals = extract_case_values(src_nc, targets, obs_idx)
    tgt_vals = extract_case_values(tgt_nc, targets, obs_idx)
    src_eval = evaluate_case(src_nc, targets, obs_idx)
    tgt_eval = evaluate_case(tgt_nc, targets, obs_idx)

    # Compute deltas
    delta = {}
    rel_change = {}
    for tname in src_vals:
        if tname in tgt_vals:
            d = tgt_vals[tname] - src_vals[tname]
            delta[tname] = d
            denom = abs(src_vals[tname])
            rel_change[tname] = d / denom if denom > 1e-10 else 0.0

    return CasePairResult(
        case_num=case_num, source_rank=src_rank, source_cost=src_cost,
        source_n_satisfied=src_n_sat,
        r_src_values=src_vals, r_tgt_values=tgt_vals,
        r_src_eval=src_eval, r_tgt_eval=tgt_eval,
        delta=delta, rel_change=rel_change,
        src_satisfied=src_eval.get('satisfied', {}),
        tgt_satisfied=tgt_eval.get('satisfied', {}),
        status='ok')


# ---------------------------------------------------------------------------
# Aggregate statistics
# ---------------------------------------------------------------------------

def _compute_aggregate_stats(
    case_results: List[CasePairResult],
    targets: Dict,
) -> Dict:
    """Compute per-target statistics from paired results."""
    paired = [c for c in case_results if c.status == 'ok']
    target_names = list(targets.keys())

    per_target_stats = {}
    improved_count = {}
    degraded_count = {}
    satisfaction_changes = {}

    for tname in target_names:
        deltas = [c.delta.get(tname, 0) for c in paired if tname in c.delta]
        rel_changes = [c.rel_change.get(tname, 0) for c in paired if tname in c.rel_change]

        if deltas:
            arr = np.array(deltas)
            rel_arr = np.array(rel_changes)
            per_target_stats[tname] = {
                'mean_delta': round(float(np.mean(arr)), 2),
                'median_delta': round(float(np.median(arr)), 2),
                'std_delta': round(float(np.std(arr)), 2),
                'min_delta': round(float(np.min(arr)), 2),
                'max_delta': round(float(np.max(arr)), 2),
                'mean_rel_change': round(float(np.mean(rel_arr)), 4),
                'median_rel_change': round(float(np.median(rel_arr)), 4),
                'n_cases': len(deltas),
            }
        else:
            per_target_stats[tname] = {'n_cases': 0}

        # Count improved vs degraded (closer to / farther from observed)
        t = targets[tname]
        obs_val = t.observed if hasattr(t, 'observed') else t.get('observed', 0)

        n_improved = 0
        n_degraded = 0
        for c in paired:
            if tname not in c.r_src_values or tname not in c.r_tgt_values:
                continue
            src_err = abs(c.r_src_values[tname] - obs_val)
            tgt_err = abs(c.r_tgt_values[tname] - obs_val)
            if tgt_err < src_err:
                n_improved += 1
            elif tgt_err > src_err:
                n_degraded += 1
        improved_count[tname] = n_improved
        degraded_count[tname] = n_degraded

        # Satisfaction changes
        gained = 0
        lost = 0
        unchanged = 0
        for c in paired:
            src_sat = c.src_satisfied.get(tname, False)
            tgt_sat = c.tgt_satisfied.get(tname, False)
            if not src_sat and tgt_sat:
                gained += 1
            elif src_sat and not tgt_sat:
                lost += 1
            else:
                unchanged += 1
        satisfaction_changes[tname] = {'gained': gained, 'lost': lost, 'unchanged': unchanged}

    # Rank correlation (Spearman) between source and target composite costs
    src_costs = []
    tgt_costs = []
    for c in paired:
        sc = c.r_src_eval.get('composite_cost', float('inf'))
        tc = c.r_tgt_eval.get('composite_cost', float('inf'))
        if np.isfinite(sc) and np.isfinite(tc):
            src_costs.append(sc)
            tgt_costs.append(tc)

    rank_corr = 0.0
    if len(src_costs) >= 3:
        try:
            from scipy.stats import spearmanr
            rank_corr, _ = spearmanr(src_costs, tgt_costs)
            rank_corr = round(float(rank_corr), 4)
        except ImportError:
            # Fallback: Pearson on ranks
            src_ranks = np.argsort(np.argsort(src_costs)).astype(float)
            tgt_ranks = np.argsort(np.argsort(tgt_costs)).astype(float)
            if np.std(src_ranks) > 0 and np.std(tgt_ranks) > 0:
                rank_corr = round(float(np.corrcoef(src_ranks, tgt_ranks)[0, 1]), 4)

    return {
        'per_target_stats': per_target_stats,
        'improved_count': improved_count,
        'degraded_count': degraded_count,
        'satisfaction_changes': satisfaction_changes,
        'rank_correlation': rank_corr,
    }


# ---------------------------------------------------------------------------
# AI summary builder
# ---------------------------------------------------------------------------

def _build_ai_summary(
    result: 'CrossRoundResult',
    targets: Dict,
    tgt_config: Dict,
) -> Dict:
    """Build structured summary dict for injection into the AI diagnosis prompt."""
    # Override description
    overrides = tgt_config.get('overrides', {})
    override_desc = ', '.join(f'{k}: {v}' for k, v in overrides.items()) if overrides else 'unknown'

    # Per-target summary table (markdown)
    lines = ['| Target | Mean Δ | Median Δ | Mean Rel Change | Improved | Degraded |',
             '|--------|--------|----------|-----------------|----------|----------|']
    for tname in targets:
        stats = result.per_target_stats.get(tname, {})
        if stats.get('n_cases', 0) == 0:
            lines.append(f'| {tname} | — | — | — | — | — |')
            continue
        lines.append(
            f"| {tname} | {stats['mean_delta']:+.1f} | {stats['median_delta']:+.1f} | "
            f"{stats['mean_rel_change']:+.1%} | {result.improved_count.get(tname, 0)} | "
            f"{result.degraded_count.get(tname, 0)} |"
        )
    per_target_summary = '\n'.join(lines)

    # Satisfaction summary
    sat_lines = []
    for tname in targets:
        sc = result.satisfaction_changes.get(tname, {})
        gained = sc.get('gained', 0)
        lost = sc.get('lost', 0)
        sat_lines.append(f"  {tname}: +{gained} gained, -{lost} lost")
    satisfaction_summary = '\n'.join(sat_lines)

    # Notable cases
    paired = [c for c in result.case_results if c.status == 'ok']
    crashed = [c.case_num for c in result.case_results if c.status == 'tgt_missing']

    # Top improved: sort by sum of relative improvements across targets
    def _total_improvement(c):
        return sum(c.rel_change.get(t, 0) for t in targets)

    top_improved = sorted(paired, key=_total_improvement, reverse=True)[:5]
    top_degraded = sorted(paired, key=_total_improvement)[:5]

    return {
        'source_round': result.source_round,
        'target_round': result.target_round,
        'override_description': override_desc,
        'n_cases_total': result.n_cases_total,
        'n_cases_paired': result.n_cases_paired,
        'n_cases_tgt_missing': result.n_cases_tgt_missing,
        'per_target_summary': per_target_summary,
        'per_target_stats': result.per_target_stats,
        'satisfaction_summary': satisfaction_summary,
        'satisfaction_changes': result.satisfaction_changes,
        'rank_correlation': result.rank_correlation,
        'notable_cases': {
            'top_improved': [
                {'case_num': c.case_num, 'source_rank': c.source_rank,
                 'delta': {k: round(v, 2) for k, v in c.delta.items()},
                 'rel_change': {k: round(v, 4) for k, v in c.rel_change.items()}}
                for c in top_improved
            ],
            'top_degraded': [
                {'case_num': c.case_num, 'source_rank': c.source_rank,
                 'delta': {k: round(v, 2) for k, v in c.delta.items()},
                 'rel_change': {k: round(v, 4) for k, v in c.rel_change.items()}}
                for c in top_degraded
            ],
            'crashed': crashed[:20],
        },
    }


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _generate_plots(
    result: 'CrossRoundResult',
    targets: Dict,
    output_dir: str,
) -> List[str]:
    """Generate comparison plots. Returns list of figure paths."""
    figure_paths = []
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available — skipping plots")
        return []

    paired = [c for c in result.case_results if c.status == 'ok']
    target_names = list(targets.keys())

    # 1. Delta boxplot
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        data_for_box = []
        labels = []
        for tname in target_names:
            deltas = [c.delta.get(tname, np.nan) for c in paired if tname in c.delta]
            if deltas:
                data_for_box.append(deltas)
                labels.append(tname.replace('_', '\n'))
        if data_for_box:
            bp = ax.boxplot(data_for_box, labels=labels, patch_artist=True)
            colors = ['#4CAF50', '#4CAF50', '#2196F3', '#2196F3', '#FF9800', '#FF9800']
            for patch, color in zip(bp['boxes'], colors[:len(bp['boxes'])]):
                patch.set_facecolor(color)
                patch.set_alpha(0.6)
            ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
            ax.set_ylabel('Δ Biomass (g C/m², R4 − R3)')
            ax.set_title(f'Round {result.target_round} − Round {result.source_round}: '
                         f'Biomass Change per Target (n={len(paired)} paired cases)')
            fig_path = str(out / 'delta_boxplot.png')
            fig.tight_layout()
            fig.savefig(fig_path, dpi=150)
            figure_paths.append(fig_path)
            logger.info(f"Saved: {fig_path}")
        plt.close(fig)
    except Exception as e:
        logger.warning(f"Delta boxplot failed: {e}")

    # 2. Cost scatter
    try:
        fig, ax = plt.subplots(figsize=(8, 8))
        src_costs = [c.r_src_eval.get('composite_cost', np.nan) for c in paired]
        tgt_costs = [c.r_tgt_eval.get('composite_cost', np.nan) for c in paired]
        mask = [np.isfinite(s) and np.isfinite(t) for s, t in zip(src_costs, tgt_costs)]
        sc = [s for s, m in zip(src_costs, mask) if m]
        tc = [t for t, m in zip(tgt_costs, mask) if m]
        if sc:
            ax.scatter(sc, tc, alpha=0.5, s=20, c='#2196F3')
            lim = max(max(sc), max(tc)) * 1.1
            ax.plot([0, lim], [0, lim], 'k--', alpha=0.3, label='no change')
            ax.set_xlabel(f'Round {result.source_round} Composite Cost (RMSRE)')
            ax.set_ylabel(f'Round {result.target_round} Composite Cost (RMSRE)')
            ax.set_title(f'Composite Cost: R{result.source_round} vs R{result.target_round} '
                         f'(ρ={result.rank_correlation:.3f})')
            ax.legend()
            fig_path = str(out / 'cost_scatter.png')
            fig.tight_layout()
            fig.savefig(fig_path, dpi=150)
            figure_paths.append(fig_path)
            logger.info(f"Saved: {fig_path}")
        plt.close(fig)
    except Exception as e:
        logger.warning(f"Cost scatter failed: {e}")

    # 3. Satisfaction bar chart
    try:
        fig, ax = plt.subplots(figsize=(10, 5))
        x = np.arange(len(target_names))
        width = 0.25
        gained = [result.satisfaction_changes.get(t, {}).get('gained', 0) for t in target_names]
        lost = [result.satisfaction_changes.get(t, {}).get('lost', 0) for t in target_names]
        ax.bar(x - width/2, gained, width, label='Gained (now satisfied)', color='#4CAF50')
        ax.bar(x + width/2, [-l for l in lost], width, label='Lost (no longer satisfied)', color='#F44336')
        ax.set_xticks(x)
        ax.set_xticklabels([t.replace('_', '\n') for t in target_names], fontsize=9)
        ax.set_ylabel('Number of Cases')
        ax.set_title(f'Target Satisfaction Changes: R{result.source_round} → R{result.target_round}')
        ax.axhline(y=0, color='gray', linewidth=0.5)
        ax.legend()
        fig_path = str(out / 'satisfaction_bar.png')
        fig.tight_layout()
        fig.savefig(fig_path, dpi=150)
        figure_paths.append(fig_path)
        logger.info(f"Saved: {fig_path}")
        plt.close(fig)
    except Exception as e:
        logger.warning(f"Satisfaction bar failed: {e}")

    return figure_paths


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def compare_rounds(
    source_round: int,
    target_round: int,
    yaml_path: str,
    output_dir: str,
    targets: Optional[Dict] = None,
    generate_plots: bool = True,
    top_k_timeseries: int = 5,
) -> CrossRoundResult:
    """
    Compare simulation results between two calibration rounds case-by-case.

    Reads calibration_rounds.yaml for both rounds' paths, loads the subset
    replay manifest to identify paired cases, then evaluates each pair
    against validation targets.

    Args:
        source_round: Round number providing the baseline (e.g., 3)
        target_round: Round number providing the experimental variant (e.g., 4)
        yaml_path:    Path to calibration_rounds.yaml
        output_dir:   Directory for CSV, JSON, and plot outputs
        targets:      Validation targets dict; if None, loads Kougarok defaults
        generate_plots: Whether to produce matplotlib figures
        top_k_timeseries: Number of best/worst cases for time series (reserved)

    Returns:
        CrossRoundResult with paired evaluations, aggregate stats, and figure paths
    """
    logger.info(f"Cross-round comparison: R{source_round} vs R{target_round}")

    # Load round configs from YAML
    src_config = _load_round_config(yaml_path, source_round)
    tgt_config = _load_round_config(yaml_path, target_round)

    logger.info(f"  Source (R{source_round}): {src_config['extracted_data']}")
    logger.info(f"  Target (R{target_round}): {tgt_config['extracted_data']}")

    # Load targets
    if targets is None:
        from phases.phase2_screening.screen_ensemble import load_kougarok_targets
        targets = load_kougarok_targets()

    # Observation index (July 2016, monthly from 1901)
    obs_idx = (2016 - 1901) * 12 + 7 - 1  # = 1386

    # Load case list from manifest (preferred) or case list file
    manifest_entries = _load_manifest(tgt_config['ensemble_output'])
    if manifest_entries:
        case_nums = [e['new_case_num'] for e in manifest_entries]
        manifest_by_case = {e['new_case_num']: e for e in manifest_entries}
        logger.info(f"  Loaded {len(case_nums)} cases from manifest")
    else:
        case_nums = _load_case_list(tgt_config['ensemble_output'])
        manifest_by_case = {}
        logger.info(f"  Loaded {len(case_nums)} cases from case list (no manifest)")

    if not case_nums:
        logger.error("No case numbers found — check manifest or case list file")
        return CrossRoundResult(
            source_round=source_round, target_round=target_round,
            n_cases_total=0, n_cases_paired=0,
            n_cases_src_missing=0, n_cases_tgt_missing=0,
            case_results=[], output_dir=output_dir)

    # Evaluate all pairs
    case_results = []
    n_src_missing = 0
    n_tgt_missing = 0
    n_paired = 0

    for i, cn in enumerate(case_nums):
        if (i + 1) % 50 == 0 or i == 0:
            logger.info(f"  Evaluating case {i+1}/{len(case_nums)} (case_num={cn})")

        pair = _evaluate_pair(
            case_num=cn,
            src_config=src_config,
            tgt_config=tgt_config,
            targets=targets,
            obs_idx=obs_idx,
            manifest_entry=manifest_by_case.get(cn),
        )
        case_results.append(pair)

        if pair.status == 'src_missing':
            n_src_missing += 1
        elif pair.status == 'tgt_missing':
            n_tgt_missing += 1
        else:
            n_paired += 1

    logger.info(f"  Results: {n_paired} paired, {n_tgt_missing} target missing, "
                f"{n_src_missing} source missing")

    # Aggregate statistics
    agg = _compute_aggregate_stats(case_results, targets)

    # Build result
    result = CrossRoundResult(
        source_round=source_round,
        target_round=target_round,
        n_cases_total=len(case_nums),
        n_cases_paired=n_paired,
        n_cases_src_missing=n_src_missing,
        n_cases_tgt_missing=n_tgt_missing,
        case_results=case_results,
        per_target_stats=agg['per_target_stats'],
        improved_count=agg['improved_count'],
        degraded_count=agg['degraded_count'],
        satisfaction_changes=agg['satisfaction_changes'],
        rank_correlation=agg['rank_correlation'],
        output_dir=output_dir,
    )

    # Build AI summary
    result.summary_dict = _build_ai_summary(result, targets, tgt_config)

    # Generate plots
    if generate_plots:
        result.figure_paths = _generate_plots(result, targets, output_dir)

    # Write output files
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Summary JSON
    summary_path = out / 'cross_round_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(result.summary_dict, f, indent=2, default=str)
    logger.info(f"  Summary: {summary_path}")

    # Per-case CSV
    csv_path = out / 'case_pair_results.csv'
    _write_csv(case_results, targets, csv_path)
    logger.info(f"  CSV: {csv_path}")

    return result


def _write_csv(case_results: List[CasePairResult], targets: Dict, csv_path: Path):
    """Write per-case results to CSV."""
    target_names = list(targets.keys())
    header = ['case_num', 'source_rank', 'source_cost', 'status',
              'r_src_cost', 'r_tgt_cost']
    for tname in target_names:
        header.extend([f'{tname}_src', f'{tname}_tgt', f'{tname}_delta', f'{tname}_rel_change'])

    with open(csv_path, 'w') as f:
        f.write(','.join(header) + '\n')
        for c in case_results:
            row = [
                str(c.case_num),
                str(c.source_rank),
                f'{c.source_cost:.4f}',
                c.status,
                f"{c.r_src_eval.get('composite_cost', '')}" if c.status != 'src_missing' else '',
                f"{c.r_tgt_eval.get('composite_cost', '')}" if c.status == 'ok' else '',
            ]
            for tname in target_names:
                row.append(f"{c.r_src_values.get(tname, '')}")
                row.append(f"{c.r_tgt_values.get(tname, '')}")
                row.append(f"{c.delta.get(tname, '')}")
                row.append(f"{c.rel_change.get(tname, '')}")
            f.write(','.join(row) + '\n')


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Cross-round comparison for subset replay experiments')
    parser.add_argument('--source-round', type=int, required=True,
                        help='Source round number (baseline)')
    parser.add_argument('--target-round', type=int, required=True,
                        help='Target round number (experimental)')
    parser.add_argument('--yaml', type=str, required=True,
                        help='Path to calibration_rounds.yaml')
    parser.add_argument('--output-dir', type=str, required=True,
                        help='Output directory for results and plots')
    parser.add_argument('--no-plots', action='store_true',
                        help='Skip plot generation')
    parser.add_argument('--top-k', type=int, default=5,
                        help='Number of cases for time series comparison')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    result = compare_rounds(
        source_round=args.source_round,
        target_round=args.target_round,
        yaml_path=args.yaml,
        output_dir=args.output_dir,
        generate_plots=not args.no_plots,
        top_k_timeseries=args.top_k,
    )

    print(f"\n{'='*60}")
    print(f"Cross-Round Comparison: R{result.source_round} vs R{result.target_round}")
    print(f"{'='*60}")
    print(f"Total cases:    {result.n_cases_total}")
    print(f"Paired:         {result.n_cases_paired}")
    print(f"Target missing: {result.n_cases_tgt_missing}")
    print(f"Source missing: {result.n_cases_src_missing}")
    print(f"Rank corr:      {result.rank_correlation}")
    print(f"\nPer-target stats:")
    for tname, stats in result.per_target_stats.items():
        if stats.get('n_cases', 0) > 0:
            print(f"  {tname}: mean Δ={stats['mean_delta']:+.1f}, "
                  f"median Δ={stats['median_delta']:+.1f}, "
                  f"rel={stats['mean_rel_change']:+.1%}")
    print(f"\nOutputs: {result.output_dir}")


if __name__ == '__main__':
    main()
