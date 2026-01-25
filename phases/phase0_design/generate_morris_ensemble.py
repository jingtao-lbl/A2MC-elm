#!/usr/bin/env python3
"""
Generate Morris ensemble for 162 parameters (138 original + 24 new)

This script reads the parameter list v2 file and generates Morris samples
using SALib for sensitivity analysis.

Input:
    - FATES_Parameter_List_Full_162_Finalized.txt (parameter list with bounds)

Output:
    - FATES_CNPnPlantTraits_162param_Morris_4890sets.txt (parameter samples)
    - morris_problem_162params.txt (SALib problem definition)

Usage:
    python generate_morris_ensemble.py

Author: Created 2025-12-29
"""

import pandas as pd
import numpy as np
from SALib.sample.morris import sample as morris_sample
from pathlib import Path

# Directories
kb_dir = Path('/Users/jingtao/Desktop/Work/SourceCode/ELM_FATES/fates_knowledge_base')
salib_dir = Path('/Users/jingtao/Desktop/Work/NGEE-Arctic/Kougarok/SALib_FATES')
output_dir = salib_dir

print("="*80)
print("GENERATE MORRIS ENSEMBLE - 162 PARAMETERS")
print("="*80)

# Read parameter list
param_file = kb_dir / 'docs/parameters/FATES_Parameter_List_Full_162_Finalized.txt'
print(f"\nReading parameter list: {param_file}")

# Read file, skip header lines (first 14 lines are header, line 15 has column names)
df = pd.read_csv(param_file, sep='\t', skiprows=14)

# Filter to only keep valid parameter rows (No column should be numeric)
df = df[pd.to_numeric(df['No'], errors='coerce').notna()].copy()

print(f"✓ Loaded {len(df)} parameters")

# Extract parameter information
param_names = df['Symbol/Short and PFT#'].values
lower_bounds = df['Lower_Bound'].values
upper_bounds = df['Upper_Bound'].values

# Convert scientific notation strings to floats
lower_bounds = [float(x) for x in lower_bounds]
upper_bounds = [float(x) for x in upper_bounds]

# Create bounds list for SALib
bounds = [[lower_bounds[i], upper_bounds[i]] for i in range(len(param_names))]

# Verify counts
print(f"\nParameter verification:")
print(f"  Number of parameters: {len(param_names)}")
print(f"  Number of bounds: {len(bounds)}")
assert len(param_names) == 162, "Expected 162 parameters!"
assert len(bounds) == 162, "Expected 162 bound pairs!"

# Show summary of new parameters (139-162)
print(f"\n" + "-"*80)
print("NEW PARAMETERS (139-162):")
print("-"*80)
for i in range(138, 162):
    print(f"  {i+1:3d}. {param_names[i]:30s}  [{lower_bounds[i]:.6g}, {upper_bounds[i]:.6g}]")

# Create SALib problem dictionary
problem = {
    'num_vars': 162,
    'names': list(param_names),
    'bounds': bounds
}

# Save problem definition
problem_file = output_dir / 'morris_problem_162params.txt'
with open(problem_file, 'w') as f:
    f.write("SALib Morris Problem Definition - 162 Parameters\n")
    f.write("="*80 + "\n\n")
    f.write(f"num_vars: {problem['num_vars']}\n\n")
    f.write("Parameter names:\n")
    for i, name in enumerate(problem['names'], 1):
        f.write(f"  {i:3d}. {name}\n")
    f.write("\nBounds:\n")
    for i, (name, bound) in enumerate(zip(problem['names'], problem['bounds']), 1):
        f.write(f"  {i:3d}. {name:30s}  [{bound[0]:.6g}, {bound[1]:.6g}]\n")

print(f"✓ Saved problem definition: {problem_file}")

# Generate Morris samples
print(f"\n" + "="*80)
print("GENERATING MORRIS SAMPLES")
print("="*80)

print(f"\nMorris sampling parameters:")
print(f"  Number of trajectories (N): 30")
print(f"  Number of parameters (P): 162")
print(f"  Total samples: N × (P+1) = 30 × 163 = 4,890")
print(f"  Grid levels: 8")
print(f"  Random seed: 123")

X = morris_sample(
    problem,
    N=30,              # number of trajectories
    num_levels=8,      # number of grid levels
    optimal_trajectories=None,  # No optimization for computational efficiency
    local_optimization=False,
    seed=123
)

print(f"\n✓ Generated {X.shape[0]} parameter sets ({X.shape[1]} parameters)")

# Verify dimensions
assert X.shape[0] == 30 * (162 + 1), f"Expected 4890 samples, got {X.shape[0]}"
assert X.shape[1] == 162, f"Expected 162 parameters, got {X.shape[1]}"

# Save parameter sets
output_file = salib_dir / 'FATES_CNPnPlantTraits_162param_Morris_4890sets.txt'
np.savetxt(output_file, X)
print(f"✓ Saved parameter sets: {output_file}")

# Generate statistics
print(f"\n" + "-"*80)
print("PARAMETER SAMPLING STATISTICS")
print("-"*80)

# Check coverage for new parameters
print("\nNew parameter sampling coverage (parameters 139-162):")
for i in range(138, 162):
    param_values = X[:, i]
    coverage = (param_values.max() - param_values.min()) / (upper_bounds[i] - lower_bounds[i])
    print(f"  {i+1:3d}. {param_names[i]:30s}  Coverage: {coverage:6.1%}  "
          f"Range: [{param_values.min():.4g}, {param_values.max():.4g}]")

# Summary statistics
print(f"\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"\n✓ Generated Morris ensemble with 162 parameters")
print(f"✓ Total parameter sets: 4,890 (increase of 720 from original 4,170)")
print(f"✓ New critical parameters: 24")
print(f"  - Tier 1 (turnover, root distribution): 12 parameters")
print(f"  - Tier 2 (PID gains): 6 parameters")
print(f"  - Tier 3 (storage ratios): 6 parameters")

print(f"\n" + "-"*80)
print("OUTPUT FILES")
print("-"*80)
print(f"1. Parameter samples:     {output_file}")
print(f"2. Problem definition:    {problem_file}")
print(f"3. Parameter list (v2):   {param_file}")

print(f"\n" + "="*80)
print("NEXT STEPS")
print("="*80)
print("""
1. Review parameter sampling coverage above
2. Update simulation workflow to use 162-parameter ensemble:
   - Modify parameter modification scripts to handle new parameters
   - Update Morris analysis scripts to analyze 162 parameters
3. Run ELM-FATES simulations for all 4,890 parameter sets
4. Perform Morris sensitivity analysis:
   - Calculate μ* (importance ranking)
   - Calculate μ (directional effect)
   - Calculate σ (nonlinearity indicator)
5. Compare sensitivity patterns between 138-param and 162-param ensembles

CRITICAL NEW PARAMETERS TO MONITOR:
- fates_turnover_fnrt: Controls fine root steady-state biomass
- fates_allom_fnrt_prof_a/b: Controls root distribution and nutrient access
- fates_cnp_pid_ki: Integral gain for persistent nutrient limitation
""")
