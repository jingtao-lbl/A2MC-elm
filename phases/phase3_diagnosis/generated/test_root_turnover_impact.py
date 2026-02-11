#!/usr/bin/env python3
"""
Consolidated custom hypothesis test: Root turnover impact on biomass.

Tests whether high fineroot turnover is a primary driver of PFT#10 fineroot
failure, including cross-PFT turnover analysis, root profile effects, and
the turnover–biomass relationship.

Consolidates 3 earlier auto-generated scripts:
  test_turnover_carbon_drain_20260211_105831.py
  test_root_turnover_impact_20260211_110128.py
  test_turnover_biomass_relationship_20260211_110401.py

Author: Jing Tao with Claude
"""

import numpy as np
try:
    from scipy import stats
except ImportError:
    stats = None

# PFT column mapping in Y matrix (PFT#7=col0, PFT#9=col1, PFT#10=col2)
PFT_COL = {7: 0, 9: 1, 10: 2}
PFTS = [7, 9, 10]


def _safe_index(param_names, name):
    """Return parameter index or None if not found."""
    try:
        return param_names.index(name)
    except (ValueError, AttributeError):
        return None


def test_hypothesis(param_matrix, y_outputs, screening_data, config):
    """
    Test root turnover hypothesis using Morris ensemble data.

    Analyses performed:
    1. Per-PFT correlation between turnover_fnrt and fineroot biomass
    2. Binned comparison: low vs high turnover cases
    3. Root profile parameters (fnrt_prof_a, fnrt_prof_b) effects on PFT#10
    4. Cross-PFT comparison: which PFT is most turnover-sensitive
    5. Low-turnover + best-biomass overlap analysis
    """
    param_names = config.get('param_names', [])
    pft_ids = config.get('pft_ids', PFTS)

    # --- Locate turnover parameters ---
    turnover_idx = {}
    for pft in pft_ids:
        idx = _safe_index(param_names, f'turnover_fnrt_{pft}')
        if idx is not None:
            turnover_idx[pft] = idx

    if not turnover_idx:
        return {
            'supported': False, 'confidence': 0.0,
            'evidence': {'error': 'No turnover_fnrt parameters found in param_names'},
            'insights': ['Cannot run analysis: turnover_fnrt_* not found']
        }

    # --- Locate root profile parameters (PFT#10 focus) ---
    prof_a_10 = _safe_index(param_names, 'fnrt_prof_a_10')
    prof_b_10 = _safe_index(param_names, 'fnrt_prof_b_10')

    # --- Load biomass Y matrices ---
    # Shape: (n_cases, 3) with columns [PFT#7, PFT#9, PFT#10]
    leaf = y_outputs.get('leaf_biomass', None)
    froot = y_outputs.get('froot_biomass', None)

    if froot is None:
        return {
            'supported': False, 'confidence': 0.0,
            'evidence': {'error': 'Missing froot_biomass in y_outputs'},
            'insights': ['Cannot run analysis: fineroot biomass data not found']
        }

    # Ensure 2D
    if froot.ndim == 1:
        froot = froot.reshape(-1, 1)
    if leaf is not None and leaf.ndim == 1:
        leaf = leaf.reshape(-1, 1)

    evidence = {}
    insights = []

    # ====================================================================
    # 1. Per-PFT correlation and binned comparison
    # ====================================================================
    for pft in pft_ids:
        col = PFT_COL.get(pft)
        tidx = turnover_idx.get(pft)
        if col is None or tidx is None or col >= froot.shape[1]:
            continue

        turnover_vals = param_matrix[:, tidx]
        froot_vals = froot[:, col]
        valid = ~(np.isnan(turnover_vals) | np.isnan(froot_vals))

        if np.sum(valid) < 20:
            continue

        # Spearman correlation (turnover vs froot biomass)
        if stats is not None:
            rho, p_val = stats.spearmanr(turnover_vals[valid], froot_vals[valid])
        else:
            rho = float(np.corrcoef(turnover_vals[valid], froot_vals[valid])[0, 1])
            p_val = 0.0  # Can't compute without scipy

        evidence[f'PFT{pft}_turnover_froot_rho'] = float(rho)
        evidence[f'PFT{pft}_turnover_froot_pval'] = float(p_val)

        # Quartile bins: Q1 (low turnover = long-lived roots) vs Q4 (high turnover)
        q25 = np.percentile(turnover_vals[valid], 25)
        q75 = np.percentile(turnover_vals[valid], 75)
        low_mask = (turnover_vals <= q25) & valid
        high_mask = (turnover_vals >= q75) & valid

        mean_low = np.mean(froot_vals[low_mask]) if np.any(low_mask) else 0.0
        mean_high = np.mean(froot_vals[high_mask]) if np.any(high_mask) else 0.0
        ratio = mean_low / (mean_high + 1e-10)

        evidence[f'PFT{pft}_froot_low_turnover_mean'] = float(mean_low)
        evidence[f'PFT{pft}_froot_high_turnover_mean'] = float(mean_high)
        evidence[f'PFT{pft}_low_vs_high_ratio'] = float(ratio)

        if ratio > 1.5 and p_val < 0.05:
            insights.append(
                f"PFT#{pft}: Low-turnover cases have {ratio:.1f}x higher "
                f"froot biomass (rho={rho:.3f}, p={p_val:.1e})"
            )
        elif abs(rho) < 0.1:
            insights.append(
                f"PFT#{pft}: Turnover has weak effect on froot (rho={rho:.3f})"
            )

    # ====================================================================
    # 2. PFT#10 focus: overlap of low-turnover and best-biomass cases
    # ====================================================================
    pft10_col = PFT_COL.get(10)
    tidx10 = turnover_idx.get(10)
    if pft10_col is not None and tidx10 is not None and pft10_col < froot.shape[1]:
        turnover_10 = param_matrix[:, tidx10]
        froot_10 = froot[:, pft10_col]

        lowest_10pct = np.percentile(turnover_10, 10)
        best_10pct = np.percentile(froot_10, 90)
        low_turnover_cases = turnover_10 <= lowest_10pct
        best_biomass_cases = froot_10 >= best_10pct

        overlap = int(np.sum(low_turnover_cases & best_biomass_cases))
        n_low = int(np.sum(low_turnover_cases))
        n_best = int(np.sum(best_biomass_cases))

        evidence['PFT10_low_turnover_best_biomass_overlap'] = overlap
        evidence['PFT10_n_lowest_10pct_turnover'] = n_low
        evidence['PFT10_n_best_10pct_biomass'] = n_best

        if n_low > 0:
            overlap_frac = overlap / n_low
            insights.append(
                f"PFT#10: {overlap}/{n_low} ({overlap_frac:.0%}) of lowest-turnover "
                f"cases are also in top 10% biomass"
            )

    # ====================================================================
    # 3. Root profile parameters effect on PFT#10
    # ====================================================================
    if pft10_col is not None and pft10_col < froot.shape[1] and stats is not None:
        froot_10 = froot[:, pft10_col]

        for name, label, pidx in [
            ('fnrt_prof_a_10', 'prof_a', prof_a_10),
            ('fnrt_prof_b_10', 'prof_b', prof_b_10),
        ]:
            if pidx is None:
                continue
            vals = param_matrix[:, pidx]
            valid = ~(np.isnan(vals) | np.isnan(froot_10))
            if np.sum(valid) < 20:
                continue

            rho, p_val = stats.spearmanr(vals[valid], froot_10[valid])
            evidence[f'PFT10_{label}_froot_rho'] = float(rho)
            evidence[f'PFT10_{label}_froot_pval'] = float(p_val)

            if abs(rho) > 0.2 and p_val < 0.05:
                direction = "deeper" if rho < 0 else "shallower"
                insights.append(
                    f"PFT#10: {direction} root profile ({label}) correlates "
                    f"with higher froot (rho={rho:.3f})"
                )

    # ====================================================================
    # 4. Cross-PFT sensitivity comparison
    # ====================================================================
    ratios = {
        pft: evidence.get(f'PFT{pft}_low_vs_high_ratio', 1.0)
        for pft in pft_ids
    }
    most_sensitive = max(ratios, key=ratios.get) if ratios else None
    if most_sensitive is not None:
        evidence['most_turnover_sensitive_pft'] = most_sensitive
        if ratios[most_sensitive] > 1.5:
            insights.append(
                f"PFT#{most_sensitive} is most sensitive to turnover "
                f"({ratios[most_sensitive]:.1f}x biomass ratio)"
            )

    # ====================================================================
    # Verdict — focused on PFT#10
    # ====================================================================
    pft10_ratio = evidence.get('PFT10_low_vs_high_ratio', 1.0)
    pft10_pval = evidence.get('PFT10_turnover_froot_pval', 1.0)

    supported = pft10_ratio > 1.5 and pft10_pval < 0.05
    confidence = min(0.95, max(0.1, (pft10_ratio - 1.0) * 0.3 + 0.2 * len(insights)))

    if not insights:
        insights.append("Insufficient evidence for root turnover as primary driver")

    return {
        'supported': supported,
        'confidence': float(confidence),
        'evidence': evidence,
        'insights': insights
    }
