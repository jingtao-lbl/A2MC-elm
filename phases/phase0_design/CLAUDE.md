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

**End-to-end roadmap:** for the full 4-stage path from a user-supplied parameter
list to a launched-and-monitored ensemble (sample → NetCDF → build-once/reuse →
launch+monitor), see `docs/a2mc_reference/phase0_ensemble_generation_roadmap.md`.

## Scripts in This Folder

| Script | Purpose |
|--------|---------|
| `create_parameter_sample.py` | **Stage 1.** Generate the parameter sample matrix from $A2MC_PARAM_LIST_FILE. `--method {morris,sobol,lhs}` — all three implemented. Sobol/LHS accept `--screened-params FILE` to vary only a subset (non-screened parameters take their `Default_Value` column or the midpoint of (lower, upper)). Sample count is determined by the method's own knob: `--trajectories` for Morris (default 30), `--n-samples` for Sobol/LHS (default 1024 = 2^10; Sobol prefers N=2^k for low-discrepancy convergence — a non-power-of-2 N still runs but emits a warning). |
| `create_morris_ensemble.py` | **Stage 2 (fresh-sample path).** Materialize per-case FATES parameter NetCDF files from the sample matrix. NetCDF-only on this branch (FATES api-31-0); contains Kougarok-specific column-to-parameter mapping. Cross-site + JSON-format rewrite is the documented handoff to main — see `memory/dev_logs/20260511h_Create_Morris_Ensemble_Refactor_Recommendation.md`. |
| `apply_param_override.py` | **Stage 2 (override path).** Alternative to `create_morris_ensemble.py` for rounds that REUSE an existing per-case NC dir and apply a global override. CLI: `--source-dir`, `--dest-dir`, `--pattern`, `--range`, `--override KEY=VALUE` (repeatable). Multiprocessing.Pool copy+modify; `--verify-only` inspection mode; JSON manifest. Used by R5 to apply `fates_cnp_prescribed_puptake=1.0` to R3's 4890 NCs in ~2s. |
| `create_subset_replay.py` | **Stage 2 (subset path).** Replay top-N cases from previous round with parameter overrides (controlled experiments). Reads `ranked_cases` from `$A2MC_REPLAY_SOURCE_STATE` workflow_state JSON, selects top-N by ranking metric, copies + applies override. Used for old R4 (superseded). |
| `submit_phase0.py` | **Stage 3.** Orchestrate ensemble submission: generate per-case scripts via `tools/create_case.sh --write-script`, run the build case fresh (synchronously), run remaining cases in parallel batches reusing the build case's `bld/`. Replaces `tools/submit_ensemble.sh` (deprecated) and the casetemplate bundle script. Key flags: `--start/--end` or `--cases-file`, `--build-case N` (default smallest in range), `--batch-size N` (default 20), `--skip-build-case` (skip Stage 3c.1 when the build case has already been completed by a separate invocation — useful for batched bulk submissions after a pilot). Auto-invokes `tools/validate_submission_plan.py`; writes `$A2MC_ENSEMBLE_OUTPUT/submission_manifest.json`. |
| `tools/ensemble_auto_monitor.sh` | **Stage 4 (post-submission monitoring).** Canonical live monitor for an in-flight ensemble (matches root `CLAUDE.md` Key Files). Config-driven — no per-round editing; round wrappers (e.g. R5's `r5_auto_monitor.sh`) just exec it after sourcing the site config. Per poll it watches the SLURM queue, auto-triggers extraction on TRANS completion, regenerates the milestone plot, and exits on terminal-idle. Derives its case-number regex + TRANS glob from `$A2MC_CASE_NAME_PATTERN`. Emits stdout events (`QUEUE_DEPTH`, `QUEUE_BELOW_THRESHOLD`, `TRANS_DONE`, `STARTING_EXTRACTION`, `EXTRACTION_TARGET_REACHED`, `*_TERMINAL`) that a Claude Monitor subscription arms against. Copy-and-edit alternative: `tools/ensemble_progress_monitor.sh.template` (lighter; customize its `ROUND CUSTOMIZATION` block, `cp` to `tmp/<round>_progress_monitor.sh`, launch via `nohup`). Full workflow + design rationale: `memory/dev_logs/20260514c_Monitoring_Workflow_Pattern_For_HPC_Ensembles.md`. |

**Stage 2 path choice:** the three Stage-2 scripts above are mutually
exclusive per round. Pick based on the round design:

| Round style | Stage 2 script | Example |
|---|---|---|
| Fresh Morris/Sobol/LHS sampling | `create_morris_ensemble.py` | R2, R3, R4 |
| Existing NC dir + global override on every case | `apply_param_override.py` | R5 (`prescribed_puptake=1.0` over R3's 4890 NCs) |
| Existing NC dir + override + top-N ranked subset | `create_subset_replay.py` | old R4 (subset_replay_PrescP, superseded) |

**Sampling → Materialization flow:** `create_parameter_sample.py` writes the X matrix to
`$A2MC_ENSEMBLE_MATRIX_FILE`; `create_morris_ensemble.py` reads that file
and writes one `.nc` per row. `create_parameter_sample.py` replaces the historical
`generate_morris_ensemble.py` (deleted in P1 of the refactor — see
`memory/dev_logs/20260511c_Phase0_P1_Sampling_Tool.md`).

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
source use_cases/Kougarok/config/kougarok_config_r4.sh
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

This guidance applies to **both** modes — the autonomous orchestrator traversing Phase 0, and the interactive (offline) agent navigating here. Offline skills for this phase: `arm-hpc-monitoring`, `restart-failed-jobs` (see `docs/a2mc_reference/skills_catalog.md`).

**Focus on:**
- Correct parameter sampling coverage
- Proper handling of PFT-specific parameters
- Ensuring parameter file integrity

**Do NOT:**
- Modify shared tools unless necessary
- Skip parameter validation
- Create files outside this phase's outputs
