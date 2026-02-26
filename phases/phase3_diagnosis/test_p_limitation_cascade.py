#!/usr/bin/env python3
"""
Consolidated custom hypothesis test: P limitation cascade.

Tests whether low vmax_p values are the primary bottleneck for PFT biomass,
including correlation analysis, threshold effects, PID cascade signature,
and microbial competition.

Consolidates 7 earlier auto-generated scripts:
  test_p_limitation_cascade_20260211_103039.py
  test_p_limitation_cascade_20260211_103424.py
  test_p_limitation_cascade_20260211_103818.py
  test_p_limitation_cascade_20260211_104208.py
  test_p_limitation_cascade_20260211_104752.py
  test_arctic_p_limitation_cascade_20260211_105422.py
  test_p_limitation_cascade_20260211_110743.py

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


def _find_param_indices(param_names, prefix, exclude=None):
    """Find all parameter indices matching prefix, optionally excluding a substring."""
    indices = {}
    for i, name in enumerate(param_names):
        if prefix in name:
            if exclude and exclude in name:
                continue
            # Extract PFT suffix (last token after '_')
            parts = name.rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                pft = int(parts[1])
                indices[pft] = i
    return indices


def test_hypothesis(param_matrix, y_outputs, screening_data, config):
    """
    Test P limitation cascade hypothesis using Morris ensemble data.

    Analyses performed:
    1. Correlation between vmax_p and biomass per PFT
    2. Threshold effect: compare bottom 10% vs top 10% vmax_p cases
    3. Failure rate analysis: cases with very low vmax_p
    4. PID cascade signature: low vmax_p → high froot:leaf ratio
    5. Microbial competition effect
    """
    param_names = config.get('param_names', [])
    pft_ids = config.get('pft_ids', PFTS)

    # --- Locate parameters ---
    vmax_p_idx = _find_param_indices(param_names, 'vmax_p_', exclude='vmax_ptase')
    microb_bio_idx = _find_param_indices(param_names, 'microb_bio_')
    pid_kp_idx = _find_param_indices(param_names, 'pid_kp_')

    if not vmax_p_idx:
        return {
            'supported': False, 'confidence': 0.0,
            'evidence': {'error': 'No vmax_p parameters found in param_names'},
            'insights': ['Cannot run analysis: vmax_p parameters not found']
        }

    # --- Load biomass Y matrices ---
    # Shape: (n_cases, 3) with columns [PFT#7, PFT#9, PFT#10]
    leaf = y_outputs.get('leaf_biomass', None)
    froot = y_outputs.get('froot_biomass', None)

    if leaf is None or froot is None:
        return {
            'supported': False, 'confidence': 0.0,
            'evidence': {'error': 'Missing leaf_biomass or froot_biomass in y_outputs'},
            'insights': ['Cannot run analysis: biomass data not found']
        }

    # Ensure 2D
    if leaf.ndim == 1:
        leaf = leaf.reshape(-1, 1)
    if froot.ndim == 1:
        froot = froot.reshape(-1, 1)

    n_cases = param_matrix.shape[0]
    evidence = {}
    insights = []

    # ====================================================================
    # 1. Per-PFT correlation between vmax_p and biomass
    # ====================================================================
    correlations = {}
    threshold_effects = {}

    for pft in pft_ids:
        col = PFT_COL.get(pft)
        vidx = vmax_p_idx.get(pft)
        if col is None or vidx is None or col >= leaf.shape[1]:
            continue

        vmax_vals = param_matrix[:, vidx]
        total_bio = leaf[:, col] + froot[:, col]
        valid = ~(np.isnan(vmax_vals) | np.isnan(total_bio))

        if np.sum(valid) < 20:
            continue

        # Pearson correlation
        corr = np.corrcoef(vmax_vals[valid], total_bio[valid])[0, 1]
        correlations[f'PFT{pft}'] = float(corr)

        # Threshold: bottom 10% vs top 10%
        n10 = max(1, int(np.sum(valid) * 0.1))
        sorted_idx = np.argsort(vmax_vals[valid])
        low_bio = np.mean(total_bio[valid][sorted_idx[:n10]])
        high_bio = np.mean(total_bio[valid][sorted_idx[-n10:]])
        ratio = high_bio / (low_bio + 1e-10)
        threshold_effects[f'PFT{pft}'] = float(ratio)

        if corr > 0.3:
            insights.append(
                f"PFT#{pft}: vmax_p–biomass r={corr:.3f}, "
                f"top 10% has {ratio:.1f}x more biomass than bottom 10%"
            )

    evidence['correlations'] = correlations
    evidence['threshold_effects_top10_vs_bottom10'] = threshold_effects

    # ====================================================================
    # 2. Failure rate: cases with any vmax_p < 1e-09
    # ====================================================================
    all_vmax_cols = [vmax_p_idx[p] for p in pft_ids if p in vmax_p_idx]
    if all_vmax_cols:
        low_vmax_mask = (param_matrix[:, all_vmax_cols] < 1e-09).any(axis=1)
        # "Failed" = bottom quartile of total ecosystem biomass
        total_eco = np.zeros(n_cases)
        for pft in pft_ids:
            col = PFT_COL.get(pft)
            if col is not None and col < leaf.shape[1]:
                total_eco += leaf[:, col] + froot[:, col]
        q25 = np.percentile(total_eco, 25)
        failed = total_eco < q25

        fail_low = np.mean(failed[low_vmax_mask]) if np.any(low_vmax_mask) else 0.0
        fail_normal = np.mean(failed[~low_vmax_mask]) if np.any(~low_vmax_mask) else 0.0

        evidence['failure_rate_low_vmax'] = float(fail_low)
        evidence['failure_rate_normal_vmax'] = float(fail_normal)
        evidence['n_low_vmax_cases'] = int(np.sum(low_vmax_mask))
        evidence['n_total_cases'] = int(n_cases)

        if fail_normal > 0 and fail_low > fail_normal * 1.5:
            insights.append(
                f"Cases with vmax_p<1e-09 fail {fail_low/fail_normal:.1f}x "
                f"more often ({evidence['n_low_vmax_cases']} cases)"
            )

    # ====================================================================
    # 3. PID cascade signature: low vmax_p → high froot:leaf ratio
    # ====================================================================
    cascade_found = False
    for pft in pft_ids:
        col = PFT_COL.get(pft)
        vidx = vmax_p_idx.get(pft)
        if col is None or vidx is None or col >= leaf.shape[1]:
            continue

        vmax_vals = param_matrix[:, vidx]
        leaf_vals = leaf[:, col]
        froot_vals = froot[:, col]

        # Avoid division by zero
        safe_leaf = np.where(leaf_vals > 0.01, leaf_vals, 0.01)
        ratio = froot_vals / safe_leaf

        valid = ~(np.isnan(vmax_vals) | np.isnan(ratio))
        if np.sum(valid) < 20 or stats is None:
            continue

        corr, p_val = stats.spearmanr(
            np.log10(vmax_vals[valid] + 1e-15),
            np.log10(ratio[valid] + 1e-10)
        )
        evidence[f'PFT{pft}_vmax_vs_froot_leaf_ratio_rho'] = float(corr)

        if corr < -0.3 and p_val < 0.05:
            cascade_found = True
            insights.append(
                f"PFT#{pft}: PID cascade detected — low vmax_p → "
                f"high froot:leaf (rho={corr:.3f}, p={p_val:.1e})"
            )

    evidence['cascade_detected'] = cascade_found

    # ====================================================================
    # 4. Microbial competition effect
    # ====================================================================
    if microb_bio_idx and stats is not None:
        # Use first PFT's microb_bio
        first_pft = min(microb_bio_idx.keys())
        midx = microb_bio_idx[first_pft]
        microb_vals = param_matrix[:, midx]
        total_eco = np.zeros(n_cases)
        for pft in pft_ids:
            col = PFT_COL.get(pft)
            if col is not None and col < leaf.shape[1]:
                total_eco += leaf[:, col] + froot[:, col]

        corr, p_val = stats.pearsonr(microb_vals, total_eco)
        evidence['microb_competition_r'] = float(corr)
        if corr < -0.2 and p_val < 0.05:
            insights.append(
                f"Microbial competition reduces plant biomass (r={corr:.3f})"
            )

    # ====================================================================
    # 5. Failed vs successful cases: vmax_p and pid_kp comparison
    # ====================================================================
    pft10_col = PFT_COL.get(10)
    vmax10_idx = vmax_p_idx.get(10)
    pidkp10_idx = pid_kp_idx.get(10)
    if pft10_col is not None and pft10_col < leaf.shape[1]:
        pft10_bio = leaf[:, pft10_col] + froot[:, pft10_col]
        # Guard: when many cases have zero biomass (PFT collapse), the 25th
        # percentile can be ~0, making (bio < 0) all-False → empty mask →
        # np.mean(empty) warning.  Use <= to include the zero cases, and
        # guard the downstream means with np.any() checks.
        pft10_fail = pft10_bio <= np.percentile(pft10_bio, 25)

        if np.any(pft10_fail) and np.any(~pft10_fail):
            if vmax10_idx is not None:
                failed_vmax = np.mean(param_matrix[pft10_fail, vmax10_idx])
                success_vmax = np.mean(param_matrix[~pft10_fail, vmax10_idx])
                evidence['PFT10_vmax_p_failed_mean'] = float(failed_vmax)
                evidence['PFT10_vmax_p_success_mean'] = float(success_vmax)

            if pidkp10_idx is not None:
                failed_kp = np.mean(param_matrix[pft10_fail, pidkp10_idx])
                success_kp = np.mean(param_matrix[~pft10_fail, pidkp10_idx])
                evidence['PFT10_pid_kp_failed_mean'] = float(failed_kp)
                evidence['PFT10_pid_kp_success_mean'] = float(success_kp)
                if success_kp > 0 and failed_kp > success_kp * 1.3:
                    insights.append(
                        f"PFT#10 failed cases have {failed_kp/success_kp:.1f}x "
                        f"higher pid_kp (PID overreaction)"
                    )

    # ====================================================================
    # Verdict
    # ====================================================================
    avg_corr = np.mean(list(correlations.values())) if correlations else 0.0
    avg_threshold = np.mean(list(threshold_effects.values())) if threshold_effects else 1.0

    supported = (avg_corr > 0.3 and avg_threshold > 5.0) or cascade_found
    confidence = min(0.95, max(0.1, avg_corr + 0.1 * len(insights)))

    if not insights:
        insights.append("Insufficient evidence for P limitation cascade")

    return {
        'supported': supported,
        'confidence': float(confidence),
        'evidence': evidence,
        'insights': insights
    }
