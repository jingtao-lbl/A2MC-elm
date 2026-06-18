# Phase 0: Design, Submit, and Monitor

This phase handles the full lifecycle of ensemble simulations: parameter sampling, parameter-file materialization, pre-flight validation, HPC submission with build reuse, status monitoring, and restarting failed cases.

---

## Three stages of Phase 0 (v2.100+)

```
parameter list + bounds (use_cases/{site}/parameters/*.txt)
       |
       |  Stage 1: SAMPLE
       |  phases/phase0_design/create_parameter_sample.py
       |  (Morris / Sobol / LHS)
       v
ensemble matrix X (N_cases x M_params)
(e.g. FATES_..._Nsets.txt)
       |
       |  Stage 2: MATERIALIZE
       |  phases/phase0_design/generate_parameter_files.py
       |  (calls tools/modify_fates_parameters.py with format dispatch:
       |   detect_format(BASE) -> .nc or .json path)
       v
N FATES parameter files
($A2MC_PARAM_DIR/fates_params_*_En{N}.{nc|json})
       |
       |  Stage 3: SUBMIT
       |  phases/phase0_design/submit_phase0.py
       |  (invokes tools/create_case.sh)
       |  (gated by tools/validate_submission_plan.py)
       |  ADSP -> RGSP -> TRANS chained via sbatch --dependency=afterok:<prev_jobid>
       |  (per-case scripts launched in parallel; default --batch-size 20)
       v
N SLURM jobs running on Perlmutter
```

The materializer auto-detects the base parameter file's format from `$A2MC_BASE_PARAM_FILE` and emits matching `.nc` (api-31 and earlier) or `.json` (api-43+) outputs.

---

## Quick Reference

```bash
# Always source configs first
source a2mc_config.sh
source use_cases/Kougarok/config/kougarok_config.sh
```

### Stage 1 — Generate the ensemble matrix (SAMPLE)

```bash
# Morris OAT (default; for sensitivity analysis)
python phases/phase0_design/create_parameter_sample.py \
    --method morris --trajectories 30 \
    --param-list-file <use_cases/{site}/parameters/...txt> \
    --output-matrix <ensemble_dir>/matrix.txt

# Sobol quasi-random
python phases/phase0_design/create_parameter_sample.py --method sobol --N 1024 ...

# Latin Hypercube
python phases/phase0_design/create_parameter_sample.py --method lhs --N 500 ...
```

Default Sobol N is 1024 (warns on non-power-of-2). Methods are dispatched by `--method`; the same script handles all three.

### Stage 2 — Materialize per-case FATES parameter files (MATERIALIZE)

```bash
# Reads ensemble matrix + base parameter file from env;
# emits one parameter file per case into $A2MC_PARAM_DIR.
python phases/phase0_design/generate_parameter_files.py
```

The output extension follows the base file's format:
- `$A2MC_BASE_PARAM_FILE` ends in `.nc` -> writes `fates_params_*_En{N}.nc`
- `$A2MC_BASE_PARAM_FILE` ends in `.json` (api-43+) -> writes `fates_params_*_En{N}.json`

Cross-parameter post-modifications (e.g., `slamax` floor relative to `slatop`, prescribed C/N/P uptake reset) are applied through a format-aware dispatcher.

### Stage 3 — Submit to HPC (SUBMIT)

```bash
# Dry-run preview (writes manifest, no submission)
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --dry-run

# Full submit (4890 cases, build case 1, parallel batches of 20)
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --submit

# Submit a subset via explicit case list (subset replay etc.)
python phases/phase0_design/submit_phase0.py --cases-file <list>.txt --submit

# Use a different build case (default = first case in the list)
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --build-case 1 --submit

# Tune submission parallelism
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --submit --batch-size 40
```

What `submit_phase0.py` does, end-to-end:

1. **Stage 3a — write per-case scripts.** Calls `tools/create_case.sh --write-script` once per case to produce `$A2MC_CASE_SCRIPTS_DIR/En{N}.sh`. Build case writes a fresh-build script; remaining cases get `--reuse-build <build_case>` so they `xmlchange EXEROOT` to the build case's `bld/`.
2. **Stage 3b — pre-flight + manifest.** `tools/validate_submission_plan.py` checks env vars, parameter files, base file/restart paths, queue, project, etc. (8 categories); writes a JSON manifest of cases + build_case + submit flag.
3. **Stage 3c.1 — build case (synchronous).** Runs the build-case script; Python blocks until FATES compiles (~30 min) and the build case's ADSP -> RGSP -> TRANS chain is queued. Aborts on any non-zero exit.
4. **Stage 3c.2 — remaining cases (parallel batches).** Launches `--batch-size` per-case scripts in parallel via `subprocess.Popen`; waits for each batch before the next. Each script calls `case.submit`, which queues that case's ADSP -> RGSP -> TRANS chain. Default batch size is **20**.

### Stage 3 internals — job dependency model

| Boundary | Mechanism |
|---|---|
| Build case finishes before remaining cases launch | Python `subprocess.run` blocking wait (build-artifact gate, not SLURM) |
| Cases within one batch | Independent SLURM submits (no dep) |
| ADSP -> RGSP -> TRANS within one case | `sbatch --dependency=afterok:<prev_jobid>` set in `tools/create_case.sh:submit_phase_case()` |

Only the intra-case ADSP -> RGSP -> TRANS chain uses SLURM `afterok:` dependencies. Across cases, Perlmutter's scheduler runs as many jobs concurrently as the queue allows.

### Subset replay (alternative Stage 1, for hypothesis-test rounds)

For mechanistic hypothesis tests at the ensemble scale (e.g., "does removing P limitation rescue PFT10?"), replay the top-N cases from a previous round with a global parameter override applied:

```bash
# Source the round-specific config (sets all REPLAY_* env vars)
source use_cases/Kougarok/config/kougarok_config_r4.sh

# Generate parameter files (copies top-N source files + applies overrides in place)
python phases/phase0_design/create_subset_replay.py
```

Outputs (written to `$A2MC_ENSEMBLE_OUTPUT/`):
- `subset_replay_manifest.json` — full mapping with source rank, cost, n_satisfied, overrides applied
- `subset_replay_case_list.txt` — plain list of case numbers, one per line, for `submit_phase0.py --cases-file`

**Important:** subset replay preserves the source round's case numbers for traceability. R4 case 86 corresponds to R3 case 86 with the override applied — same filename, just in a different directory. Phase 1 sensitivity analysis is automatically skipped for `subset_replay` rounds (no Morris design to analyze).

Submit using:

```bash
python phases/phase0_design/submit_phase0.py \
    --cases-file $A2MC_ENSEMBLE_OUTPUT/subset_replay_case_list.txt \
    --submit
```

### Check simulation status

```bash
# Diagnose all cases — shows completed, incomplete, and errored
python tools/diagnose_ensemble_status.py

# Check specific range
python tools/diagnose_ensemble_status.py --cases 1-500

# Speed up with parallel workers
python tools/diagnose_ensemble_status.py --parallel 8
```

**Output files** (timestamped, written to current directory):

| File | Description |
|------|-------------|
| `ensemble_status_report_{ts}.txt` | CSV status of all cases (phase, last restart year, errors) |
| `completed_cases_{ts}.txt` | Case numbers that finished all 3 phases |
| `incomplete_cases_{ts}.txt` | Case numbers still running or stuck, with details |
| `error_cases_{ts}.txt` | Cases with errors needing manual investigation |

### Restart failed/incomplete cases

```bash
# Generate restart script for all incomplete cases (auto-validates by default)
python tools/diagnose_ensemble_status.py --restart

# Skip auto-validation if you want to inspect the script first
python tools/diagnose_ensemble_status.py --restart --no-validate

# Then run the generated script on HPC
chmod +x restart_incomplete_{ts}.sh
./restart_incomplete_{ts}.sh
```

The restart workflow:
- **Correct restart logic**: uses `RUN_STARTDATE` + `finidat` (not `CONTINUE_RUN`)
- **Phase chaining**: ADSP -> RGSP -> TRANS via SLURM `--dependency=afterok:<prev_jobid>`
- **Partial restarts**: picks up from the last valid restart file
- **Case recreation**: generates a separate `recreate_cases_{ts}.sh` for cases that need to be rebuilt from scratch
- **Auto-validation**: `tools/validate_restart_script.py` checks the generated script before execution (suppress with `--no-validate`)

### Create a single case (for experiments or testing)

```bash
# Create and submit one case with a specific parameter file
./tools/create_case.sh --case-num 1 --param-file /path/to/fates_params.nc --submit

# Generate a reviewable script instead of executing
./tools/create_case.sh --case-num 1 --param-file /path/to/params.nc --write-script review.sh

# Run only specific phases
./tools/create_case.sh --case-num 1 --param-file /path/to/params.nc --phases "RGSP TRANS" --submit
```

---

## Simulation phases (ADSP -> RGSP -> TRANS)

Each ensemble case runs three sequential ELM phases chained via SLURM `afterok:` dependencies:

| Phase | Name | Duration | Description |
|-------|------|----------|-------------|
| ADSP | Accelerated Decomposition Spinup | 200 yr | Builds the system with accelerated decomposition |
| RGSP | Regular Spinup | 200 yr | Equilibrates with regular decomposition rates |
| TRANS | Transient | 119 yr (1901-2019) | Transient run with historical forcing |

The restart file from each phase initializes the next: ADSP -> RGSP -> TRANS.

---

## Tool reference

| Script | Location | Purpose |
|--------|----------|---------|
| `create_parameter_sample.py` | `phases/phase0_design/` | Stage 1 — Morris / Sobol / LHS sampling (NEW v2.100, replaces `create_morris_ensemble.py`) |
| `create_subset_replay.py` | `phases/phase0_design/` | Stage 1 alternative — replay top-N cases from a prior round with overrides |
| `apply_param_override.py` | `phases/phase0_design/` | Stage 1 alternative — copy ALL per-case files (NC or JSON) and apply a global override to each (v2.100 follow-up; full-ensemble equivalent of subset_replay) |
| `generate_parameter_files.py` | `phases/phase0_design/` | Stage 2 — materialize per-case FATES parameter files (NC or JSON, renamed from `create_morris_ensemble.py` in v2.100) |
| `submit_phase0.py` | `phases/phase0_design/` | Stage 3 — orchestrate write-scripts + pre-flight + build + parallel submit |
| `create_case.sh` | `tools/` | Build one per-case script (CIME create_newcase + xmlchange + case.submit with `afterok:` chain) |
| `modify_fates_parameters.py` | `tools/` | Format-dispatching parameter editor (NC or JSON, v2.100) |
| `validate_submission_plan.py` | `tools/` | Pre-flight gate before submission (8 categories of checks) |
| `validate_restart_script.py` | `tools/` | Validator for auto-generated restart scripts |
| `diagnose_ensemble_status.py` | `tools/` | Check completion status, generate restart scripts |
| `audit_param_list_against_api.py` | `scripts/` | Sidecar — diff a parameter list against a target api JSON, flag renames/removals |

`tools/submit_ensemble.sh` (pre-v2.100) is superseded by `submit_phase0.py` and retained only for backward compatibility.

---

## Common scenarios

### Node failure on Perlmutter

```bash
# 1. Check which cases failed
python tools/diagnose_ensemble_status.py --parallel 8

# 2. Generate restart script (auto-validates before writing)
python tools/diagnose_ensemble_status.py --restart --parallel 8

# 3. Review and run the restart script
less restart_incomplete_*.sh
./restart_incomplete_*.sh
```

### Expanding parameter space for a new round

1. Update parameter list in `use_cases/{site}/parameters/`
2. Update `A2MC_N_PARAMS` in site config
3. Regenerate matrix: `python phases/phase0_design/create_parameter_sample.py --method morris --trajectories 30 ...`
4. Materialize parameter files: `python phases/phase0_design/generate_parameter_files.py`
5. Submit: `python phases/phase0_design/submit_phase0.py --start 1 --end {new_size} --submit`
6. Document in `use_cases/{site}/config/calibration_rounds.yaml`

### Migrating a parameter list across api epochs (e.g., api-31 -> api-43)

Older parameter lists may reference names that were renamed or removed in newer FATES APIs (e.g., `fates_turnover_leaf` was split into `fates_turnover_leaf_canopy` + `fates_turnover_leaf_ustory` at api-43). Audit before running Stage 2:

```bash
python scripts/audit_param_list_against_api.py \
    --param-list use_cases/{site}/parameters/<list>.txt \
    --api-json <E3SM>/components/elm/src/external_models/fates/parameter_files/fates_params_default.json \
    --output use_cases/{site}/parameters/api_migration_audit.md
```

Exit 0 = clean, exit 1 = migration needed. The report lists missing params with `difflib`-based rename suggestions (up to 5 per missing name).

### Changing simulation protocol (e.g., suplphos)

1. Update protocol settings in `a2mc_config.sh` (e.g., `A2MC_RGSP_SUPLPHOS="ALL"`)
2. Cases must be recreated from scratch (protocol changes affect spinup)
3. Resubmit full ensemble via `submit_phase0.py`
4. Document in `calibration_rounds.yaml`
