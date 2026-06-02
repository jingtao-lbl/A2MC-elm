# Phase 0: Design, Submit, and Monitor

This phase handles the full lifecycle of ensemble simulations: parameter sampling, case creation, HPC submission, status monitoring, and restarting failed cases.

---

## Pipeline overview

Reflects the actual tooling on this branch (`kougarok_fates_demo`,
anchored at FATES api-31-0).

```
   parameter list + bounds  (use_cases/{site}/parameters/*.txt)
            |
            |   Stage 1: SAMPLE
            |   phases/phase0_design/create_parameter_sample.py
            |   (Morris / Sobol / LHS via --method)
            v
   ensemble matrix X  (N_cases x M_params)
   ($A2MC_ENSEMBLE_MATRIX_FILE, e.g. FATES_..._Nsets.txt)
            |
            |   Stage 2: MATERIALIZE
            |   phases/phase0_design/create_morris_ensemble.py
            |   (Morris-from-sample path; calls tools/modify_fates_parameters.py)
            |
            |   --- OR for override-based rounds (e.g. R5) ---
            |   phases/phase0_design/apply_param_override.py
            |   (copies an existing per-case NC dir + applies global override
            |    like fates_cnp_prescribed_puptake=1.0)
            |
            |   (NetCDF format only on this branch — FATES api-31-0;
            |    JSON support is FATES api-43+, lives on main)
            v
   N FATES parameter NetCDF files
   ($A2MC_PARAM_DIR/fates_params_*_En{N}.nc)
            |
            |   Stage 3: SUBMIT
            |   phases/phase0_design/submit_phase0.py
            |   (generates per-case En{N}.sh via tools/create_case.sh --write-script,
            |    auto-invokes tools/validate_submission_plan.py,
            |    writes $A2MC_ENSEMBLE_OUTPUT/submission_manifest.json)
            |
            |   coordinated submit:
            |     Stage 3c.1: build case (case 1) fresh, synchronous
            |                 (skippable via --skip-build-case when build already done)
            |     Stage 3c.2: cases 2..N in parallel batches (--batch-size, default 20)
            |                 — each uses --reuse-build 1 (EXEROOT = case 1's bld)
            |
            |   each En{N}.sh queues ADSP -> RGSP -> TRANS chained via
            |     sbatch --dependency=afterok:<prev_jobid>
            v
   N SLURM jobs running on Perlmutter  (3 jobs per case;
                                        watch out for the ~5000-job ceiling
                                        — submit in batches of <=1500 cases)
```

Notes on the current implementation:

- **Stage 2 has Kougarok-specific column mapping** in `create_morris_ensemble.py`.
  The script hardcodes the 162-param column-to-FATES-parameter map for this
  site. Rewriting it as a generic format-aware
  `generate_parameter_files.py` (with `.json`/api-43+ support) is documented
  in `memory/dev_logs/20260511h_Create_Morris_Ensemble_Refactor_Recommendation.md`
  as a handoff to `main`.
- **`tools/submit_ensemble.sh`** is the deprecated legacy submitter
  (header points at `submit_phase0.py`). Kept for compat; new rounds
  should use `submit_phase0.py`.
- **Restart-side validation** is independent of submission: when a case
  needs restart, `tools/diagnose_ensemble_status.py` auto-invokes
  `tools/validate_restart_script.py` after writing the
  `restart_incomplete_<TS>.sh` script.

---

## Quick Reference

```bash
# Always source configs first — the machine-level config (a2mc_config.sh)
# AND your round-specific site config in that order. The round config
# overrides any machine-level defaults that need to differ per round
# (ensemble name, case-name pattern, per-phase protocol values, etc.).
source a2mc_config.sh
source use_cases/<site>/config/<round>_config.sh
# e.g., source use_cases/Kougarok/config/kougarok_config_r4.sh
```

### 1. Generate Parameter Ensemble

Two stages: sample the parameter space → materialize per-case FATES NCs.

```bash
# Stage 1: Generate the sample matrix from $A2MC_PARAM_LIST_FILE.
#   Writes $A2MC_ENSEMBLE_MATRIX_FILE + $A2MC_SALIB_PROBLEM_FILE.
python phases/phase0_design/create_parameter_sample.py

# Stage 2: Materialize per-case FATES parameter NetCDF files.
#   Reads $A2MC_ENSEMBLE_MATRIX_FILE, writes one .nc per row to $A2MC_PARAM_DIR.
python phases/phase0_design/create_morris_ensemble.py
```

`create_parameter_sample.py` supports three sampling methods via
`--method`. Pick by round goal:

| Method | When to use | Sample count | Default knob |
|---|---|---|---|
| `morris` (default) | First exploration of a new parameter space; rank parameter importance via μ*/σ | `T × (P+1)` | `--trajectories 30 --num-levels 8` |
| `sobol` | Variance decomposition (S_i, S_Ti, S_ij) after Morris narrows P down | `N × (2P+2)` (or `N × (P+2)` with `--no-second-order`) | `--n-samples 1024` (= 2^10) |
| `lhs` | General-purpose uniform coverage; no sensitivity decomposition | `N` | `--n-samples 1024` |

`P` is the number of parameters being sampled — the full list, or the
active subset when `--screened-params FILE` is used (Sobol/LHS only; non-
listed parameters take their `Default_Value` column or the bound midpoint).

```bash
# Morris (default) — 30 trajectories × (162+1) = 4890 cases for the Kougarok config
python phases/phase0_design/create_parameter_sample.py

# Sobol — N=1024 must be 2^k for low-discrepancy convergence.
# Full 162-param Sobol is huge (1024*(2*162+2) = 333,824); pair with
# --screened-params to keep tractable.
python phases/phase0_design/create_parameter_sample.py --method sobol \
    --screened-params top20_morris_mustar.txt

# LHS — N samples, no power-of-2 requirement
python phases/phase0_design/create_parameter_sample.py --method lhs --n-samples 1024
```

The parameter list file format is auto-detected: the existing A2MC files
(with a multi-line preamble and a `Symbol/Short and PFT#` column) work,
and a minimal 3-column `name<TAB>lower<TAB>upper` file also works for
sites starting from scratch. Full per-method documentation in
`python create_parameter_sample.py --help`.

#### Option B — Subset replay (controlled experiment from previous round)

For mechanistic hypothesis tests at the ensemble scale (e.g., "does removing
P limitation rescue PFT10?"). Replays the top-N cases from a previous round
with a global parameter override applied.

```bash
# Source the round-specific config (sets all REPLAY_* env vars)
source use_cases/Kougarok/config/kougarok_config_r4.sh

# Generate parameter files (copies top-N source NC files + applies overrides in place)
python phases/phase0_design/create_subset_replay.py

# Output:
#   - N NC files in $A2MC_PARAM_DIR (case numbers match SOURCE round, NOT renumbered 1..N)
#   - subset_replay_manifest.json in $A2MC_ENSEMBLE_OUTPUT
#   - subset_replay_case_list.txt in $A2MC_ENSEMBLE_OUTPUT (case numbers, one per line)
```

**Important:** Subset replay preserves the source round's case numbers for traceability.
For example, R4 case 86 corresponds to R3 case 86 with the override applied — same
parameter values, same filename, just in a different directory.

The script only PREPARES the parameter files. Submission is then handled
by `submit_phase0.py` in `--cases-file` mode — the non-sequential case
numbers in `subset_replay_case_list.txt` are passed through directly,
and the same build-coordination logic applies (one build case fresh,
rest reuse its bld):

```bash
python phases/phase0_design/submit_phase0.py \
    --cases-file $A2MC_ENSEMBLE_OUTPUT/subset_replay_case_list.txt \
    --build-case <FIRST_CASE_NUMBER> \
    --submit
```

`<FIRST_CASE_NUMBER>` should be the first case in `subset_replay_case_list.txt`
(or any case from the source round whose bld you want to reuse). Without
`--build-case`, `submit_phase0.py` defaults to the smallest case number in
the file.

**Case-number traceability:** `subset_replay_case_list.txt` preserves
the source round's case numbers (e.g., 2939, 86, 82, ... for R4 from
R3). The output NCs in `$A2MC_PARAM_DIR` keep those numbers; downstream
analysis joins back to the source round by case number.

Phase 1 sensitivity analysis is automatically skipped for subset_replay rounds since
there is no Morris design to analyze.

### 2. Create Cases and Submit to HPC

The recommended path is `submit_phase0.py` — a single command that:
1. Generates per-case scripts in `$A2MC_CASE_SCRIPTS` via
   `tools/create_case.sh --write-script`, resolving all `$A2MC_*` values
   at script-write time.
2. Runs the build case (default: smallest in range) synchronously so the
   FATES binary compiles once.
3. Runs the remaining cases in parallel batches; each reuses the build
   case's `bld/` via `EXEROOT` and submits its own ADSP→RGSP→TRANS
   SLURM chain.
4. Writes `submission_manifest.json` to `$A2MC_ENSEMBLE_OUTPUT` with the
   full provenance (matrix SHA256, FATES + ELM commit, protocol values).

```bash
# Dry run (generates per-case scripts + writes manifest, no execution)
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --dry-run

# Real submission
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --submit

# Subset-replay mode (non-sequential case numbers)
python phases/phase0_design/submit_phase0.py \
    --cases-file $A2MC_ENSEMBLE_OUTPUT/subset_replay_case_list.txt --submit

# Custom build case
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 \
    --build-case 1 --batch-size 30 --submit
```

Build-coordination is automatic: the build case is fresh-built (skipping
`--reuse-build` even if applied via the flag — see P4 of the refactor),
remaining cases all reuse its `bld/`. No manual two-step submission
needed.

#### Legacy: `tools/submit_ensemble.sh` (deprecated, kept for compatibility)

```bash
# Submit all ensemble cases (builds + submits ADSP → RGSP → TRANS chain)
./tools/submit_ensemble.sh --start 1 --end 4890 --submit

# Submit a subset
./tools/submit_ensemble.sh --start 1 --end 100 --submit

# Dry run (preview without submitting)
./tools/submit_ensemble.sh --start 1 --end 4890 --dry-run

# Reuse build from case 1 (much faster for large ensembles)
./tools/submit_ensemble.sh --start 2 --end 4890 --submit --reuse-build 1
```

### 3. Check Simulation Status

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

### 4. Restart Failed/Incomplete Cases

```bash
# Generate restart script for all incomplete cases
python tools/diagnose_ensemble_status.py --restart

# Then run the generated script on HPC
chmod +x restart_incomplete_{ts}.sh
./restart_incomplete_{ts}.sh
```

The restart script handles:
- **Correct restart logic**: uses `RUN_STARTDATE` + `finidat` (not `CONTINUE_RUN`)
- **Phase chaining**: ADSP → RGSP → TRANS via SLURM `--dependency=afterok`
- **Partial restarts**: picks up from the last valid restart file
- **Case recreation**: generates a separate `recreate_cases_{ts}.sh` for cases that need to be rebuilt from scratch

### 5. Create a Single Case (for experiments or testing)

```bash
# Create and submit one case with a specific parameter file
./tools/create_case.sh --case-num 1 --param-file /path/to/fates_params.nc --submit

# Generate a reviewable script instead of executing
./tools/create_case.sh --case-num 1 --param-file /path/to/params.nc --write-script review.sh

# Run only specific phases
./tools/create_case.sh --case-num 1 --param-file /path/to/params.nc --phases "RGSP TRANS" --submit
```

---

## Simulation Phases (ADSP → RGSP → TRANS)

Each ensemble case runs three sequential ELM phases chained via SLURM dependencies:

| Phase | Name | Duration | Description |
|-------|------|----------|-------------|
| ADSP | Accelerated Decomposition Spinup | 200 yr | Builds the system with accelerated decomposition |
| RGSP | Regular Spinup | 200 yr | Equilibrates with regular decomposition rates |
| TRANS | Transient | 119 yr (1901-2019) | Transient run with historical forcing |

The restart file from each phase initializes the next: ADSP → RGSP → TRANS.

---

## Tool Reference

| Script | Location | Purpose |
|--------|----------|---------|
| `create_parameter_sample.py` | `phases/phase0_design/` | Sample the parameter space (Morris/Sobol/LHS) from the parameter-list-with-bounds file; writes the X matrix |
| `create_morris_ensemble.py` | `phases/phase0_design/` | Materialize per-case FATES parameter NetCDF files from the X matrix |
| `create_subset_replay.py` | `phases/phase0_design/` | Replay top-N source-round cases with parameter overrides |
| `submit_phase0.py` | `phases/phase0_design/` | Orchestrate ensemble submission (generate per-case scripts → coordinated build → parallel submit + manifest) |
| `create_case.sh` | `tools/` | Create / write-script / submit a single CIME case (all 3 phases) |
| `validate_submission_plan.py` | `tools/` | Pre-flight validate a planned submission (auto-invoked by `submit_phase0.py`) |
| `validate_restart_script.py` | `tools/` | Pre-flight validate `restart_incomplete_*.sh` (auto-invoked by `diagnose_ensemble_status.py`) |
| `diagnose_ensemble_status.py` | `tools/` | Check completion status, generate restart scripts |
| `modify_fates_parameters.py` | `tools/` | Low-level helper used by `create_morris_ensemble.py` to write modifications into FATES parameter NetCDFs |
| `submit_ensemble.sh` | `tools/` | **Deprecated** — see `submit_phase0.py` |

---

## Common Scenarios

### Node failure on Perlmutter

```bash
# 1. Check which cases failed
python tools/diagnose_ensemble_status.py --parallel 8

# 2. Generate restart script
python tools/diagnose_ensemble_status.py --restart --parallel 8

# 3. Review and run the restart script
less restart_incomplete_*.sh
./restart_incomplete_*.sh
```

### Expanding parameter space for a new round

1. Update parameter list in `use_cases/{site}/parameters/`
2. Update `A2MC_N_PARAMS` in the round-specific config (e.g., `kougarok_config_r5.sh`)
3. Regenerate the sample matrix: `python phases/phase0_design/create_parameter_sample.py`
4. Materialize per-case NCs: `python phases/phase0_design/create_morris_ensemble.py`
5. Submit: `python phases/phase0_design/submit_phase0.py --start 1 --end {new_size} --submit`
6. Document in `use_cases/{site}/config/calibration_rounds.yaml`

### Changing simulation protocol (e.g., suplphos) for a new round

The protocol values (`A2MC_ADSP_SUPLPHOS`, `A2MC_RGSP_SUPLPHOS`, etc.)
are inherited from `a2mc_config.sh` and overridden in the round-specific
site config — never edit `a2mc_config.sh` for a round-level change.

1. Create a new round config: `cp use_cases/{site}/config/{site}_config_r4.sh use_cases/{site}/config/{site}_config_r5.sh`
2. Update the protocol exports in the new config (e.g., `export A2MC_RGSP_SUPLPHOS="ALL"`)
3. Set a unique `A2MC_ENSEMBLE_NAME` and `A2MC_CASE_NAME_PATTERN` suffix so the new round's case dirs don't collide with prior rounds
4. Source the new config: `source use_cases/{site}/config/{site}_config_r5.sh`
5. Resubmit: `python phases/phase0_design/submit_phase0.py --start 1 --end {N} --submit`
   `submit_phase0.py` reads the round's protocol values via `$A2MC_SITE_CONFIG` and writes them into each per-case `user_nl_elm` automatically — no hand-editing per case.
6. Document the round and its protocol overrides in `calibration_rounds.yaml`
