"""
Phase 0: Design & Submit

Two-stage workflow:
    1. Sample the parameter space (Morris OAT / Sobol Saltelli / LHS).
    2. Materialize per-case FATES parameter files (.json for api-43+,
       .nc for legacy api-31 milestones).
    3. Orchestrate submission to HPC with build coordination.

Scripts:
    create_parameter_sample.py - Generate the sampling matrix (M/S/L)
    generate_parameter_files.py - Materialize per-case parameter files
    submit_phase0.py - Orchestrator with pre-flight validation
    create_subset_replay.py - Replay top-N cases from a previous round
"""
