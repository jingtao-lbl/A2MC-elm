# Phase 0: Design, Submit, and Monitor

This phase handles the full lifecycle of ensemble simulations: parameter sampling, case creation, HPC submission, status monitoring, and restarting failed cases.

---

## Quick Reference

```bash
# Always source configs first
source a2mc_config.sh
source use_cases/Kougarok/config/kougarok_config.sh
```

### 1. Generate Parameter Ensemble

```bash
# Generate Morris sampling design (162 params, 30 trajectories = 4890 cases)
python phases/phase0_design/create_morris_ensemble.py
```

### 2. Create Cases and Submit to HPC

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
| `create_morris_ensemble.py` | `phases/phase0_design/` | Generate Morris OAT sampling design |
| `create_case.sh` | `tools/` | Create and optionally submit a single CIME case (all 3 phases) |
| `submit_ensemble.sh` | `tools/` | Submit multiple cases with batch control and build reuse |
| `diagnose_ensemble_status.py` | `tools/` | Check completion status, generate restart scripts |
| `modify_fates_parameters.py` | `tools/` | Generate FATES parameter NetCDF files from ensemble matrix |

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
2. Update `A2MC_N_PARAMS` in site config
3. Regenerate ensemble: `python phases/phase0_design/create_morris_ensemble.py`
4. Submit new ensemble: `./tools/submit_ensemble.sh --start 1 --end {new_size} --submit`
5. Document in `use_cases/{site}/config/calibration_rounds.yaml`

### Changing simulation protocol (e.g., suplphos)

1. Update protocol settings in `a2mc_config.sh` (e.g., `A2MC_RGSP_SUPLPHOS="ALL"`)
2. Cases must be recreated from scratch (protocol changes affect spinup)
3. Resubmit full ensemble
4. Document in `calibration_rounds.yaml`
