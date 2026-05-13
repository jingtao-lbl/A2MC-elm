"""
A2MC Phase-Specific Scripts

This package contains scripts organized by workflow phase.
Each phase has its own subdirectory with phase-specific code.

Phase Overview:
    phase0_design/      - Sampling design (Morris, Sobol, LHS)
    phase1_exploration/ - Run sensitivity ensemble on HPC
    phase2_screening/   - Rank ensemble, identify top parameter sets
    phase3_diagnosis/   - Root cause analysis of model-data mismatch
    phase4_hypothesis/  - Generate testable hypotheses
    phase5_testing/     - Run designed experiments
    phase6_refinement/  - Evaluate results, extract lessons

Usage:
    from phases.phase0_design import generate_parameter_files
    from phases.phase2_screening import compare_biomass_topcases
"""
