#!/usr/bin/env python3
"""
Morris Sensitivity Analysis for FATES Parameters

Phase 1: EXPLORATION - Analyze Morris ensemble output to rank parameter sensitivities.

This script:
1. Loads Morris ensemble parameter samples (X matrix)
2. Loads model outputs (Y matrix) for specified variables
3. Runs SALib Morris analysis for each PFT
4. Generates visualization with parameter type color-coding
5. Exports results to CSV for use in Phase 2 (Screening) and Phase 3 (Diagnosis)

Usage:
    # Analyze leaf biomass sensitivity
    python morris_sensitivity_analysis.py --output-var leaf_biomass

    # Analyze fineroot biomass sensitivity
    python morris_sensitivity_analysis.py --output-var fineroot_biomass

    # Analyze fineroot:leaf ratio (log-transformed)
    python morris_sensitivity_analysis.py --output-var fineroot_leaf_ratio

    # Custom output file
    python morris_sensitivity_analysis.py --output-var leaf_biomass --y-matrix /path/to/output.txt

Author: Jing Tao, 2026-01-19
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import warnings

# HPC-compatible matplotlib backend (must be before importing pyplot)
import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import Patch

# SALib imports
from SALib.analyze import morris

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from tools.config import config
except ImportError:
    config = None
    print("Warning: A2MC config not available, using command-line arguments only")


# =============================================================================
# PARAMETER TYPE CLASSIFICATION
# =============================================================================

# Color mapping for parameter types
PARAM_TYPE_COLORS = {
    'N': '#1f77b4',       # Blue - Nitrogen uptake
    'P': '#ff7f0e',       # Orange - Phosphorus uptake
    'Allocation': '#9467bd',  # Purple - Allocation
    'Microbial': '#d62728',   # Red - Microbial
    'Phenology': '#e377c2',   # Pink - Phenology
    'Allometry': '#8c564b',   # Brown - Allometry
    'Mortality': '#7f7f7f',   # Gray - Mortality
    'Turnover': '#17becf',    # Cyan - Turnover
    'Other': '#2ca02c'        # Green - Other traits
}

# Keywords for parameter classification
PARAM_TYPE_KEYWORDS = {
    'N': ['nh4', 'no3', 'nfix', 'nitr_retrans', 'nitr_store', 'stoich_nitr'],
    'P': ['_p_', 'ptase', 'phos_retrans', 'phos_store', 'stoich_phos'],
    'Allocation': ['pid_k', 'l2fr_ini', 'alloc_'],
    'Microbial': ['microb_bio'],
    'Phenology': ['phen_'],
    'Allometry': ['allom_', 'recruit_height_min', 'leaf_slatop', 'leaf_vcmax'],
    'Mortality': ['mort_'],
    'Turnover': ['turnover_', 'frag_seed_decay', 'fnrt_prof'],
}


def classify_parameter(param_name: str) -> str:
    """Classify a parameter by its type based on naming conventions."""
    param_lower = param_name.lower()
    for param_type, keywords in PARAM_TYPE_KEYWORDS.items():
        if any(kw in param_lower for kw in keywords):
            return param_type
    return 'Other'


def get_param_colors(param_names: List[str]) -> List[str]:
    """Get colors for a list of parameter names based on their types."""
    return [PARAM_TYPE_COLORS[classify_parameter(p)] for p in param_names]


# =============================================================================
# SALib PROBLEM LOADING
# =============================================================================

def load_salib_problem_from_file(filepath: str) -> Dict:
    """
    Load SALib problem definition from a text file.

    The file format (salib_problem_162params.txt) has:
    - num_vars: N
    - Parameter names section
    - Bounds section with [lower, upper] ranges

    Returns:
        dict: SALib problem definition with keys: num_vars, names, bounds
    """
    names = []
    bounds = []

    with open(filepath, 'r') as f:
        content = f.read()

    # Parse num_vars
    for line in content.split('\n'):
        if line.startswith('num_vars:'):
            num_vars = int(line.split(':')[1].strip())
            break

    # Parse bounds section (more reliable format)
    in_bounds = False
    for line in content.split('\n'):
        if line.strip() == 'Bounds:':
            in_bounds = True
            continue
        if in_bounds and line.strip():
            # Format: "  123. param_name                   [lower, upper]"
            parts = line.strip().split('[')
            if len(parts) == 2:
                # Extract parameter name (between number and '[')
                name_part = parts[0].strip()
                # Remove leading number and period
                if '.' in name_part:
                    name = name_part.split('.', 1)[1].strip()
                else:
                    name = name_part

                # Extract bounds
                bounds_str = parts[1].rstrip(']').strip()
                lower, upper = bounds_str.split(',')
                names.append(name)
                bounds.append([float(lower.strip()), float(upper.strip())])

    if len(names) != num_vars:
        print(f"Warning: Expected {num_vars} parameters, found {len(names)}")

    return {
        'num_vars': len(names),
        'names': names,
        'bounds': bounds
    }


def load_salib_problem_from_json(filepath: str) -> Dict:
    """Load SALib problem definition from JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data


def load_salib_problem(filepath: str) -> Dict:
    """Load SALib problem definition from file (auto-detect format)."""
    if filepath.endswith('.json'):
        return load_salib_problem_from_json(filepath)
    else:
        return load_salib_problem_from_file(filepath)


# =============================================================================
# MORRIS ANALYSIS
# =============================================================================

def filter_complete_trajectories(
    X: np.ndarray,
    Y: np.ndarray,
    trajectory_size: int
) -> Tuple[np.ndarray, np.ndarray, int, int]:
    """
    Filter X and Y to keep only complete trajectories (no NaNs).

    Morris analysis requires complete trajectories. This function identifies
    and removes any trajectories containing NaN values.

    Args:
        X: Parameter samples (n_samples x n_params)
        Y: Model outputs (n_samples x n_outputs)
        trajectory_size: Size of each trajectory (num_vars + 1)

    Returns:
        Filtered X, filtered Y, number of complete trajectories, total trajectories
    """
    num_trajectories = Y.shape[0] // trajectory_size

    complete_trajectories = []
    for traj_idx in range(num_trajectories):
        start_idx = traj_idx * trajectory_size
        end_idx = start_idx + trajectory_size

        # Check if this trajectory has any NaNs
        traj_Y = Y[start_idx:end_idx, :]
        if not np.any(np.isnan(traj_Y)):
            complete_trajectories.append(traj_idx)

    if len(complete_trajectories) == 0:
        raise ValueError("No complete trajectories found! All trajectories have NaNs.")

    # Filter X and Y
    indices_to_keep = []
    for traj_idx in complete_trajectories:
        start_idx = traj_idx * trajectory_size
        end_idx = start_idx + trajectory_size
        indices_to_keep.extend(range(start_idx, end_idx))

    X_filtered = X[indices_to_keep, :]
    Y_filtered = Y[indices_to_keep, :]

    return X_filtered, Y_filtered, len(complete_trajectories), num_trajectories


def run_morris_analysis(
    problem: Dict,
    X: np.ndarray,
    Y: np.ndarray,
    num_levels: int = 8,
    conf_level: float = 0.95
) -> Dict:
    """
    Run Morris sensitivity analysis.

    Args:
        problem: SALib problem definition
        X: Parameter samples
        Y: Model outputs (1D array for single output)
        num_levels: Number of levels in Morris sampling
        conf_level: Confidence level for intervals

    Returns:
        Morris analysis results dictionary
    """
    return morris.analyze(
        problem, X, Y,
        conf_level=conf_level,
        print_to_console=False,
        num_levels=num_levels
    )


def get_top_n_parameters(
    morris_result: Dict,
    param_names: List[str],
    top_n: int = 10,
    use_signed: bool = True
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Get top N parameters sorted by sensitivity.

    Args:
        morris_result: Morris analysis result
        param_names: List of parameter names
        top_n: Number of top parameters to return
        use_signed: If True, sort by |μ| (signed); if False, sort by μ*

    Returns:
        Tuple of (parameter names, sensitivity values, confidence intervals)
    """
    if use_signed:
        # Sort by |μ| (absolute value of signed effects)
        mu = morris_result['mu']
        mu_conf = morris_result.get('mu_conf', morris_result.get('mu_star_conf', np.zeros_like(mu)))
        idx_sorted = np.argsort(np.abs(mu))[::-1][:top_n]
        return np.array(param_names)[idx_sorted], mu[idx_sorted], mu_conf[idx_sorted]
    else:
        # Sort by μ* (mean absolute elementary effect)
        mu_star = morris_result['mu_star']
        mu_star_conf = morris_result['mu_star_conf']
        idx_sorted = np.argsort(mu_star)[::-1][:top_n]
        return np.array(param_names)[idx_sorted], mu_star[idx_sorted], mu_star_conf[idx_sorted]


def normalize_signed_sensitivity(values: np.ndarray) -> np.ndarray:
    """Normalize signed sensitivity values to -1 to 1 range."""
    max_abs = np.max(np.abs(values))
    if max_abs == 0:
        return np.zeros_like(values)
    return values / max_abs


# =============================================================================
# VISUALIZATION
# =============================================================================

def plot_morris_results(
    results_by_pft: Dict[str, Dict],
    param_names: List[str],
    output_file: str,
    top_n: int = 10,
    title_suffix: str = ""
):
    """
    Create horizontal bar plot of Morris sensitivity for each PFT.

    Args:
        results_by_pft: Dictionary mapping PFT name to Morris results
        param_names: List of all parameter names
        output_file: Path to save figure
        top_n: Number of top parameters to show
        title_suffix: Additional text for figure title
    """
    plt.rcParams.update({
        'font.size': 16,
        'axes.titlesize': 18,
        'axes.labelsize': 16,
        'xtick.labelsize': 14,
        'ytick.labelsize': 14,
        'legend.fontsize': 14,
    })

    n_pfts = len(results_by_pft)
    fig = plt.figure(figsize=(12, 6 * n_pfts))
    gs = gridspec.GridSpec(n_pfts, 1, height_ratios=[1] * n_pfts)

    pft_titles = {
        'PFT7': 'PFT#7 Evergreen Shrub',
        'PFT9': 'PFT#9 Deciduous Shrub',
        'PFT10': 'PFT#10 Arctic Graminoid',
        'Evergreen': 'PFT#7 Evergreen Shrub',
        'Deciduous': 'PFT#9 Deciduous Shrub',
        'Graminoid': 'PFT#10 Arctic Graminoid',
    }

    for idx, (pft_name, morris_result) in enumerate(results_by_pft.items()):
        ax = fig.add_subplot(gs[idx])

        # Get top N parameters with signed values
        params, values, _ = get_top_n_parameters(
            morris_result, param_names, top_n=top_n, use_signed=True
        )

        # Normalize to -1 to 1 range
        values_norm = normalize_signed_sensitivity(values)

        # Get colors based on parameter types
        colors = get_param_colors(params)

        # Create horizontal bar plot
        bars = ax.barh(params, values_norm, color=colors, alpha=0.8)

        # Format
        title = pft_titles.get(pft_name, pft_name)
        ax.set_title(f"{title}{title_suffix}", fontweight='bold')
        ax.invert_yaxis()
        ax.set_xlabel("Normalized Morris μ (-1 to +1)")
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.set_xlim(-1, 1)
        ax.axvline(x=0, color='black', linestyle='-', linewidth=0.8)

        # Add sign labels
        for i, (val, param) in enumerate(zip(values_norm, params)):
            sign = "+" if val > 0 else "-" if val < 0 else "0"
            ax.text(0.02, i, sign, va='center', ha='left', fontsize=12, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved figure: {output_file}")


def create_legend_figure(output_file: str):
    """Create a standalone legend figure for parameter types."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis('off')

    legend_elements = [
        Patch(facecolor=PARAM_TYPE_COLORS['N'], label='Nitrogen uptake'),
        Patch(facecolor=PARAM_TYPE_COLORS['P'], label='Phosphorus uptake'),
        Patch(facecolor=PARAM_TYPE_COLORS['Allocation'], label='Allocation'),
        Patch(facecolor=PARAM_TYPE_COLORS['Microbial'], label='Microbial'),
        Patch(facecolor=PARAM_TYPE_COLORS['Phenology'], label='Phenology'),
        Patch(facecolor=PARAM_TYPE_COLORS['Allometry'], label='Allometry'),
        Patch(facecolor=PARAM_TYPE_COLORS['Mortality'], label='Mortality'),
        Patch(facecolor=PARAM_TYPE_COLORS['Turnover'], label='Turnover'),
        Patch(facecolor=PARAM_TYPE_COLORS['Other'], label='Other traits'),
    ]

    ax.legend(handles=legend_elements, loc='center', ncol=3, fontsize=14)
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved legend: {output_file}")


# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

def export_morris_results(
    morris_result: Dict,
    param_names: List[str],
    output_file: str,
    pft_name: str = ""
):
    """
    Export Morris results to CSV file.

    Args:
        morris_result: Morris analysis result dictionary
        param_names: List of parameter names
        output_file: Path to output CSV file
        pft_name: PFT name for metadata
    """
    df = pd.DataFrame({
        'parameter': param_names,
        'mu': morris_result['mu'],
        'mu_star': morris_result['mu_star'],
        'sigma': morris_result['sigma'],
        'mu_star_conf': morris_result['mu_star_conf'],
        'param_type': [classify_parameter(p) for p in param_names]
    })

    # Sort by absolute mu
    df['abs_mu'] = np.abs(df['mu'])
    df = df.sort_values('abs_mu', ascending=False)
    df['rank'] = range(1, len(df) + 1)

    # Reorder columns
    df = df[['rank', 'parameter', 'param_type', 'mu', 'mu_star', 'sigma', 'mu_star_conf', 'abs_mu']]

    df.to_csv(output_file, index=False)
    print(f"Saved {pft_name} results: {output_file}")

    return df


def export_combined_rankings(
    results_by_pft: Dict[str, Dict],
    param_names: List[str],
    output_file: str,
    method: str = 'avg_rank'
):
    """
    Export combined parameter rankings across PFTs.

    Args:
        results_by_pft: Dictionary mapping PFT name to Morris results
        param_names: List of parameter names
        output_file: Path to output CSV file
        method: Ranking method ('avg_rank' or 'max_mu_star')
    """
    # Create dataframe for each PFT
    pft_dfs = {}
    for pft_name, morris_result in results_by_pft.items():
        df = pd.DataFrame({
            'parameter': param_names,
            f'mu_{pft_name}': morris_result['mu'],
            f'mu_star_{pft_name}': morris_result['mu_star'],
            f'sigma_{pft_name}': morris_result['sigma'],
        })
        # Add rank for this PFT
        df[f'rank_{pft_name}'] = df[f'mu_star_{pft_name}'].rank(ascending=False)
        pft_dfs[pft_name] = df

    # Merge all PFT results
    combined = pft_dfs[list(pft_dfs.keys())[0]][['parameter']]
    for pft_name, df in pft_dfs.items():
        combined = combined.merge(df, on='parameter')

    # Calculate combined ranking
    rank_cols = [f'rank_{pft}' for pft in results_by_pft.keys()]
    mu_star_cols = [f'mu_star_{pft}' for pft in results_by_pft.keys()]

    if method == 'avg_rank':
        combined['combined_rank'] = combined[rank_cols].mean(axis=1)
    elif method == 'max_mu_star':
        combined['max_mu_star'] = combined[mu_star_cols].max(axis=1)
        combined['combined_rank'] = combined['max_mu_star'].rank(ascending=False)

    # Add parameter type
    combined['param_type'] = [classify_parameter(p) for p in combined['parameter']]

    # Sort by combined rank
    combined = combined.sort_values('combined_rank')
    combined['final_rank'] = range(1, len(combined) + 1)

    # Reorder columns
    cols = ['final_rank', 'parameter', 'param_type', 'combined_rank'] + rank_cols + mu_star_cols
    combined = combined[cols]

    combined.to_csv(output_file, index=False)
    print(f"Saved combined rankings: {output_file}")

    return combined


# =============================================================================
# OUTPUT VARIABLE LOADING
# =============================================================================

def load_output_variable(
    var_name: str,
    data_dir: str,
    n_pfts: int = 3
) -> Tuple[np.ndarray, str]:
    """
    Load model output for a specific variable.

    Supports:
    - leaf_biomass: Leaf biomass by PFT
    - fineroot_biomass: Fine root biomass by PFT
    - abg_biomass: Aboveground biomass by PFT
    - fineroot_leaf_ratio: Log(fineroot/leaf) ratio by PFT

    Args:
        var_name: Variable name
        data_dir: Directory containing output files
        n_pfts: Number of PFTs (columns in output)

    Returns:
        Tuple of (Y matrix, descriptive name for plots)
    """
    data_dir = Path(data_dir)

    if var_name == 'leaf_biomass':
        Y = np.loadtxt(data_dir / 'MorrisLeafBiomass_UpdatedModel_138param.txt')
        desc = 'Leaf Biomass'
    elif var_name == 'fineroot_biomass':
        Y = np.loadtxt(data_dir / 'MorrisFineRootBiomass_UpdatedModel_138param.txt')
        desc = 'Fine Root Biomass'
    elif var_name == 'abg_biomass':
        Y = np.loadtxt(data_dir / 'MorrisABGBiomass_UpdatedModel_138param.txt')
        desc = 'Aboveground Biomass'
    elif var_name == 'fineroot_leaf_ratio':
        Y_froot = np.loadtxt(data_dir / 'MorrisFineRootBiomass_UpdatedModel_138param.txt')
        Y_leaf = np.loadtxt(data_dir / 'MorrisLeafBiomass_UpdatedModel_138param.txt')
        epsilon = 1e-10
        Y = np.log((Y_froot + epsilon) / (Y_leaf + epsilon))
        desc = 'Fine Root:Leaf Ratio (log)'
    else:
        raise ValueError(f"Unknown variable: {var_name}")

    return Y, desc


# =============================================================================
# HIGH-LEVEL API (for orchestrator)
# =============================================================================

def run_sensitivity_analysis(
    output_var: str = 'leaf_biomass',
    x_matrix_path: str = None,
    y_matrix_path: str = None,
    problem_path: str = None,
    output_dir: str = '.',
    pft_names: List[str] = None,
    top_n: int = 10,
    num_levels: int = 8
) -> Dict:
    """
    Run complete Morris sensitivity analysis.

    This is the high-level API for calling from the orchestrator.

    Args:
        output_var: Variable to analyze ('leaf_biomass', 'fineroot_biomass', etc.)
        x_matrix_path: Path to Morris parameter samples (X matrix)
        y_matrix_path: Path to model outputs (Y matrix), optional
        problem_path: Path to SALib problem definition file
        output_dir: Directory to save results
        pft_names: List of PFT names (default: ['PFT7', 'PFT9', 'PFT10'])
        top_n: Number of top parameters to show
        num_levels: Number of levels in Morris sampling

    Returns:
        Dict with sensitivity rankings and metadata
    """
    if pft_names is None:
        pft_names = ['PFT7', 'PFT9', 'PFT10']

    # Resolve paths from config if not provided
    if config is not None and config.is_configured():
        x_matrix_path = x_matrix_path or config.ENSEMBLE_MATRIX_FILE
        problem_path = problem_path or config.SALIB_PROBLEM_FILE

    if not x_matrix_path or not problem_path:
        raise ValueError("Must provide x_matrix_path and problem_path, or source A2MC config")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(f"Morris Sensitivity Analysis: {output_var}")
    print("=" * 70)

    # Load SALib problem definition
    problem = load_salib_problem(problem_path)
    print(f"Parameters: {problem['num_vars']}")

    # Load X matrix (parameter samples)
    X = np.loadtxt(x_matrix_path)
    print(f"X matrix shape: {X.shape}")

    # Load Y matrix (model outputs)
    if y_matrix_path:
        Y = np.loadtxt(y_matrix_path)
        output_desc = output_var
    else:
        # Try to find Y matrix based on output_var
        data_dir = Path(config.get('ENSEMBLE_OUTPUT', '.')) if config else Path('.')
        Y, output_desc = load_output_variable(output_var, data_dir)
    print(f"Y matrix shape: {Y.shape}")

    # Filter for complete trajectories
    # Morris trajectory size = num_vars + 1 (each trajectory has num_vars+1 samples)
    trajectory_size = problem['num_vars'] + 1
    X_filtered, Y_filtered, num_complete, num_total = filter_complete_trajectories(
        X, Y, trajectory_size
    )
    print(f"Complete trajectories: {num_complete}/{num_total}")

    if num_complete == 0:
        return {
            'status': 'error',
            'error': 'No complete trajectories found',
            'output_var': output_var
        }

    # Run Morris analysis for each PFT
    results_by_pft = {}
    rankings = {}

    for pft_idx, pft_name in enumerate(pft_names):
        if pft_idx >= Y_filtered.shape[1]:
            print(f"  Skipping {pft_name}: not enough columns in Y matrix")
            continue

        Y_pft = Y_filtered[:, pft_idx]

        # Skip if all NaN
        if np.all(np.isnan(Y_pft)):
            print(f"  Skipping {pft_name}: all NaN values")
            continue

        print(f"\nAnalyzing {pft_name}...")
        result = run_morris_analysis(problem, X_filtered, Y_pft, num_levels=num_levels)
        results_by_pft[pft_name] = result

        # Get top parameters
        top_params, top_mu, top_conf = get_top_n_parameters(
            result, problem['names'], top_n=top_n, use_signed=True
        )

        rankings[pft_name] = [
            {
                'rank': i + 1,
                'parameter': str(top_params[i]),
                'mu': float(top_mu[i]),
                'mu_star': float(result['mu_star'][np.where(np.array(problem['names']) == top_params[i])[0][0]]),
                'sigma': float(result['sigma'][np.where(np.array(problem['names']) == top_params[i])[0][0]]),
                'type': classify_parameter(str(top_params[i]))
            }
            for i in range(len(top_params))
        ]

        print(f"  Top 3: {', '.join(top_params[:3])}")

    # Generate plots
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    plot_file = output_dir / f'morris_{output_var}_sensitivity_{timestamp}.png'
    plot_morris_results(results_by_pft, problem['names'], str(plot_file), top_n=top_n)
    print(f"\nPlot saved: {plot_file}")

    # Save CSV results
    csv_file = output_dir / f'morris_{output_var}_rankings_{timestamp}.csv'
    export_combined_rankings(results_by_pft, problem['names'], str(csv_file))
    print(f"CSV saved: {csv_file}")

    return {
        'status': 'completed',
        'output_var': output_var,
        'n_parameters': problem['num_vars'],
        'n_complete_trajectories': num_complete,
        'n_total_trajectories': num_total,
        'rankings': rankings,
        'plot_file': str(plot_file),
        'csv_file': str(csv_file)
    }


# =============================================================================
# MAIN (command-line interface)
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Morris Sensitivity Analysis for FATES Parameters',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic usage with default paths from A2MC config
    python morris_sensitivity_analysis.py --output-var leaf_biomass

    # Analyze multiple variables
    python morris_sensitivity_analysis.py --output-var fineroot_leaf_ratio

    # Custom file paths
    python morris_sensitivity_analysis.py \\
        --x-matrix /path/to/X.txt \\
        --y-matrix /path/to/Y.txt \\
        --problem /path/to/problem.txt \\
        --output-dir ./results
        """
    )

    parser.add_argument('--output-var', type=str, default='leaf_biomass',
                        choices=['leaf_biomass', 'fineroot_biomass', 'abg_biomass', 'fineroot_leaf_ratio'],
                        help='Output variable to analyze')
    parser.add_argument('--x-matrix', type=str, default=None,
                        help='Path to Morris parameter samples (X matrix)')
    parser.add_argument('--y-matrix', type=str, default=None,
                        help='Path to model outputs (Y matrix). If not provided, loads based on --output-var')
    parser.add_argument('--problem', type=str, default=None,
                        help='Path to SALib problem definition file')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='Directory containing output data files')
    parser.add_argument('--output-dir', type=str, default='.',
                        help='Directory to save results')
    parser.add_argument('--top-n', type=int, default=10,
                        help='Number of top parameters to show in plots')
    parser.add_argument('--num-levels', type=int, default=8,
                        help='Number of levels in Morris sampling')
    parser.add_argument('--pft-names', type=str, default='PFT7,PFT9,PFT10',
                        help='Comma-separated PFT names for columns in Y matrix')

    args = parser.parse_args()

    # Resolve paths from config or arguments
    if config is not None and config.is_configured():
        x_matrix_path = args.x_matrix or config.ENSEMBLE_MATRIX_FILE
        problem_path = args.problem or config.SALIB_PROBLEM_FILE
        data_dir = args.data_dir or '~/Desktop/Work/NGEE-Arctic/Kougarok/Program'
    else:
        x_matrix_path = args.x_matrix
        problem_path = args.problem
        data_dir = args.data_dir or '.'

    if not x_matrix_path or not problem_path:
        print("Error: Must provide --x-matrix and --problem paths")
        print("       Or source A2MC config: source use_cases/Kougarok/config/kougarok_config.sh")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Parse PFT names
    pft_names = args.pft_names.split(',')

    print("=" * 70)
    print("Morris Sensitivity Analysis")
    print("=" * 70)
    print(f"Output variable: {args.output_var}")
    print(f"X matrix: {x_matrix_path}")
    print(f"Problem file: {problem_path}")
    print(f"Data directory: {data_dir}")
    print(f"PFTs: {pft_names}")
    print("=" * 70)

    # Load SALib problem definition
    print("\nLoading SALib problem definition...")
    problem = load_salib_problem(problem_path)
    print(f"  Parameters: {problem['num_vars']}")

    # Load X matrix (parameter samples)
    print("\nLoading parameter samples (X matrix)...")
    X = np.loadtxt(x_matrix_path)
    print(f"  Shape: {X.shape}")

    # Load Y matrix (model outputs)
    print(f"\nLoading output variable: {args.output_var}...")
    if args.y_matrix:
        Y = np.loadtxt(args.y_matrix)
        output_desc = args.output_var
    else:
        Y, output_desc = load_output_variable(args.output_var, data_dir)
    print(f"  Shape: {Y.shape}")
    print(f"  Description: {output_desc}")

    # Check for NaNs
    total_nans = np.sum(np.isnan(Y))
    print(f"  NaN values: {total_nans} ({total_nans/Y.size*100:.1f}%)")

    # Filter complete trajectories
    trajectory_size = problem['num_vars'] + 1
    print(f"\nFiltering complete trajectories (trajectory size: {trajectory_size})...")
    X_filtered, Y_filtered, n_complete, n_total = filter_complete_trajectories(
        X, Y, trajectory_size
    )
    print(f"  Complete trajectories: {n_complete}/{n_total}")
    print(f"  Filtered data shape: X={X_filtered.shape}, Y={Y_filtered.shape}")

    # Run Morris analysis for each PFT
    print("\nRunning Morris analysis...")
    results_by_pft = {}
    for i, pft_name in enumerate(pft_names):
        if i >= Y_filtered.shape[1]:
            print(f"  Warning: Skipping {pft_name}, only {Y_filtered.shape[1]} columns in Y")
            continue

        print(f"  Analyzing {pft_name}...")
        result = run_morris_analysis(
            problem, X_filtered, Y_filtered[:, i],
            num_levels=args.num_levels
        )
        results_by_pft[pft_name] = result

        # Print top 5 for quick reference
        params, values, _ = get_top_n_parameters(result, problem['names'], top_n=5)
        print(f"    Top 5 by |μ|: {', '.join(params[:5])}")

    # Generate timestamp for output files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    var_name = args.output_var.replace('_', '')

    # Export results to CSV
    print("\nExporting results...")
    for pft_name, result in results_by_pft.items():
        csv_file = output_dir / f"morris_{var_name}_{pft_name}_{timestamp}.csv"
        export_morris_results(result, problem['names'], csv_file, pft_name)

        # Also save top 20 for quick reference
        top20_file = output_dir / f"morris_{var_name}_{pft_name}_top20_{timestamp}.csv"
        df = export_morris_results(result, problem['names'], top20_file, pft_name)

    # Export combined rankings
    combined_file = output_dir / f"morris_{var_name}_combined_rankings_{timestamp}.csv"
    export_combined_rankings(results_by_pft, problem['names'], combined_file)

    # Generate visualization
    print("\nGenerating plots...")
    fig_file = output_dir / f"morris_{var_name}_sensitivity_{timestamp}.png"
    plot_morris_results(
        results_by_pft, problem['names'],
        str(fig_file), top_n=args.top_n,
        title_suffix=f" - {output_desc}"
    )

    # Create legend figure
    legend_file = output_dir / f"morris_parameter_type_legend.png"
    create_legend_figure(str(legend_file))

    print("\n" + "=" * 70)
    print("Morris Sensitivity Analysis Complete")
    print("=" * 70)
    print(f"Results saved to: {output_dir}")
    print(f"  - Individual PFT results: morris_{var_name}_{{PFT}}_{timestamp}.csv")
    print(f"  - Combined rankings: {combined_file.name}")
    print(f"  - Sensitivity plot: {fig_file.name}")
    print("=" * 70)


if __name__ == '__main__':
    main()
