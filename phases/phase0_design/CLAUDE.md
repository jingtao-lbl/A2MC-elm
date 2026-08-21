# Phase 0: Design & Submit

**Purpose:** Generate parameter ensemble and submit HPC simulations
**Status:** Entry point for new calibration iteration
**Inputs:** Parameter list with bounds, sampling configuration, case templates
**Outputs:** Parameter ensemble matrix, FATES parameter files, submitted HPC jobs

---

## What This Phase Does

1. Read parameter definitions (names, bounds, PFT assignments)
2. Generate sampling design (Morris, Sobol, or LHS)
3. Create parameter ensemble matrix (X matrix)
4. Generate FATES parameter NetCDF files for each ensemble member
5. **Create CIME cases** for each ensemble member
6. **Submit jobs** to HPC queue (ADSP → RGSP → TRANS chain)

**Phase completes when jobs are submitted.** Monitoring and analysis happen in Phase 1.

---

## Scripts in This Folder

| Script | Purpose |
|--------|---------|
| `create_parameter_sample.py` | Generate the parameter sample / X matrix (Morris, Sobol, or LHS) |
| `generate_parameter_files.py` | Generate FATES parameter files from the sample (method- and format-agnostic: JSON/NetCDF) |
| `create_subset_replay.py` | Replay top-N cases from previous round with parameter overrides (controlled experiments) |
| `apply_param_override.py` | Apply a global parameter override to every FATES parameter file in a directory |
| `submit_phase0.py` | Submit a Phase 0 ensemble to HPC |

## Sampling Schemes

`A2MC_SAMPLING_SCHEME` selects which sampling approach Phase 0 uses:

| Scheme | Purpose | Phase 1 (sensitivity) |
|--------|---------|----------------------|
| `morris` (default) | Morris OAT for sensitivity analysis | Run μ*, σ computation |
| `subset_replay` | Replay top-N source-round cases with global override | **Skipped** (no sensitivity structure) |
| `lhs` (future) | Latin Hypercube sampling | TBD |
| `sobol` (future) | Sobol quasi-random sampling | TBD |

### Subset Replay Workflow

For mechanistic hypothesis tests at the ensemble scale (e.g., "does removing
P limitation rescue PFT10?"), use `subset_replay` instead of running a full
Morris round. The script copies the top-N source-round NetCDF parameter files
and applies global overrides in place.

Required environment variables (set in a round-specific config file like
`use_cases/{site}/config/{site}_r4_subset_replay_config.sh`):

| Var | Description |
|-----|-------------|
| `A2MC_SAMPLING_SCHEME=subset_replay` | Selects this scheme |
| `A2MC_REPLAY_SOURCE_STATE` | Path to source workflow_state JSON (must contain `screening_data.ranked_cases`) |
| `A2MC_REPLAY_SOURCE_PARAM_DIR` | Directory with source NC param files |
| `A2MC_REPLAY_SOURCE_PARAM_PATTERN` | Source filename pattern with `{N}` placeholder |
| `A2MC_REPLAY_TOP_N` | How many top cases to replay (default 200) |
| `A2MC_REPLAY_OVERRIDES` | Comma-separated `param=value` list applied to all cases |
| `A2MC_REPLAY_RANKING_METRIC` | Ranking field (default `composite_nrmse`) |

**Case numbering:** Subset replay PRESERVES source case numbers for traceability.
R4 case 86 corresponds to R3 case 86 with the override applied — same filename,
just in a different directory. Since the case numbers are non-sequential, use
the `--cases-file` mode of `submit_ensemble.sh` (added alongside this scheme).

The script writes two outputs to `${A2MC_ENSEMBLE_OUTPUT}/`:
- `subset_replay_manifest.json` — full mapping with source rank, cost, n_satisfied, overrides applied
- `subset_replay_case_list.txt` — plain list of case numbers, one per line, for `submit_ensemble.sh --cases-file`

Example:
```bash
source a2mc_config.sh
source use_cases/ELM-FATES_Kougarok/config/kougarok_config_r4.sh
python phases/phase0_design/create_subset_replay.py
./tools/submit_ensemble.sh \
    --cases-file ${A2MC_ENSEMBLE_OUTPUT}/subset_replay_case_list.txt \
    --submit --reuse-build <FIRST_CASE_NUMBER>
```

## Shared Tools Used (in `tools/`)

| Tool | Purpose |
|------|---------|
| `tools/create_case.sh` | Create CIME case for each ensemble member |
| `tools/submit_ensemble.sh` | Submit jobs with SLURM dependencies |
| `tools/modify_fates_parameters.py` | Generate FATES parameter files |
| `tools/diagnose_ensemble_status.py` | Check completion after submission |

---

## Key Inputs

| Input | Location | Description |
|-------|----------|-------------|
| Parameter list | `use_cases/{site}/parameters/*.txt` | Parameter names, bounds, PFT indices |
| Base parameter file | `use_cases/{site}/config/` | Template FATES NetCDF file |
| Site config | `use_cases/{site}/config/{site}_config.sh` | N_PARAMS, N_TRAJECTORIES, etc. |

---

## Key Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Ensemble matrix | `{ENSEMBLE_OUTPUT}/morris_ensemble_matrix.txt` | N_ensemble × N_params values |
| Parameter files | `{ENSEMBLE_OUTPUT}/ParameterFiles/` | One NetCDF per ensemble member |
| SALib problem | `use_cases/{site}/parameters/salib_problem.txt` | SALib problem definition |

---

## Morris Sampling Details

**Formula:** `N_ensemble = N_trajectories × (N_params + 1)`

For 162 parameters with 30 trajectories: `30 × 163 = 4890` simulations

**Morris method:**
- One-at-a-time (OAT) perturbation
- Each trajectory perturbs each parameter once
- Computes elementary effects (μ*, σ)

---

## Success Criteria

- [ ] All parameter files created without errors
- [ ] Parameter values within specified bounds
- [ ] Ensemble matrix has correct dimensions
- [ ] SALib problem file matches parameter list
- [ ] All CIME cases created successfully
- [ ] Jobs submitted to HPC queue (check with `squeue`)

---

## Next Phase

After Phase 0 completes (jobs submitted) → **Wait for HPC simulations to complete**

Use `tools/diagnose_ensemble_status.py` to check completion:
```bash
python tools/diagnose_ensemble_status.py --cases 1-4890
```

When >95% cases complete → **Phase 1 (Exploration)**: Extract data, run sensitivity analysis

---

## Common Issues

1. **Parameter out of bounds:** Check parameter list formatting
2. **NetCDF write error:** Verify base parameter file is valid
3. **Wrong ensemble size:** Check N_TRAJECTORIES × (N_PARAMS + 1) formula

---

## When AI Works in This Phase

**Focus on:**
- Correct parameter sampling coverage
- Proper handling of PFT-specific parameters
- Ensuring parameter file integrity

**Do NOT:**
- Modify shared tools unless necessary
- Skip parameter validation
- Create files outside this phase's outputs
