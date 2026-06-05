# Phase 0 Ensemble Generation Roadmap

**Scope:** From a user-supplied parameter list to a launched-and-monitored HPC
ensemble, in four stages. This is the end-to-end map of A2MC Phase 0 (DESIGN &
SUBMIT) on the `kougarok_fates_demo` branch (FATES api-31-0, NetCDF parameter
files).

**Author:** Jing Tao with Claude
**Branch:** `kougarok_fates_demo`
**Last Updated:** June 04, 2026

> History: the single old `generate_morris_ensemble.py` was split in the Phase 0
> refactor into **Stage 1** (`create_parameter_sample.py`, sampling) and
> **Stage 2** (`create_morris_ensemble.py`, NetCDF materialization). See
> `memory/dev_logs/20260511c_Phase0_P1_Sampling_Tool.md`. This doc is the
> reading map a new user (or future Claude session) follows when they hand A2MC
> a parameter list and want simulations running.

---

## The four stages at a glance

```
 user parameter list (names + bounds, e.g.
 use_cases/Kougarok/parameters/FATES_Parameter_List_Full_162_Finalized.txt)
        │
        ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ STAGE 1  Sample the parameter space                                    │
 │   phases/phase0_design/create_parameter_sample.py                      │
 │   Morris | Sobol | LHS  →  X matrix + SALib problem file               │
 │   out: $A2MC_ENSEMBLE_MATRIX_FILE  (N_cases x P floats)                │
 │        $A2MC_SALIB_PROBLEM_FILE    (human-readable bounds)             │
 └──────────────────────────────────────────────────────────────────────┘
        │  one row = one ensemble member
        ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ STAGE 2  Materialize per-case FATES parameter NetCDF files            │
 │   phases/phase0_design/create_morris_ensemble.py                      │
 │   reads X matrix, writes one .nc per row from $A2MC_BASE_PARAM_FILE    │
 │   out: $A2MC_PARAM_DIR/<A2MC_PARAM_PATTERN with {N}>  (N_cases .nc)    │
 └──────────────────────────────────────────────────────────────────────┘
        │  one .nc = one ensemble member's FATES parameter file
        ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ STAGE 3  Build the first case, generate + reuse-build the rest        │
 │   phases/phase0_design/submit_phase0.py                              │
 │   create_case.sh --write-script per case; build case 1 fresh;         │
 │   remaining cases --reuse-build <build_case> (share compiled bld/)     │
 │   out: $A2MC_CASE_SCRIPTS/En{N}.sh  +  submission_manifest.json        │
 └──────────────────────────────────────────────────────────────────────┘
        │  each script submits an ADSP → RGSP → TRANS SLURM chain
        ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ STAGE 4  Launch + monitor                                              │
 │   submit_phase0.py --submit  (queues SLURM chains)                     │
 │   tools/ensemble_auto_monitor.sh  (queue polling + extraction kick)    │
 │   tools/diagnose_ensemble_status.py  (completion accounting)           │
 └──────────────────────────────────────────────────────────────────────┘
        │  >95% TRANS complete
        ▼
                          Phase 1 (EXPLORATION)
```

**Prerequisite for every stage:** source the two config layers first. All
scripts read their paths and knobs from `$A2MC_*` env vars.

```bash
source a2mc_config.sh                               # machine layer
source use_cases/Kougarok/config/kougarok_config.sh  # site/round layer
```

---

## Inputs the user provides

### 1. Parameter list file

The single required input. `create_parameter_sample.py` auto-detects the header
row (first line containing both a lower- and upper-bound column), the delimiter
(tab > comma > whitespace), and the name/bound/default columns. Two formats work:

**A2MC full format** (what Kougarok uses — multi-line preamble, then a tab-
separated table). Header row in
`use_cases/Kougarok/parameters/FATES_Parameter_List_Full_162_Finalized.txt`:

```
No  ELM-FATES CNP Parameters  Symbol/Short and PFT#  Lower_Bound  Upper_Bound  Default_Value  Description
1   fates_cnp_eca_alpha_ptase alpha_ptase_7          0.25         0.95         0.5            Phosphatase ... PFT#7
```

- **Name column** detected from: `name`, `parameter`, `Symbol/Short and PFT#`,
  or any column starting `symbol`/`name`/`parameter`. (Kougarok's name column is
  the shorthand `Symbol/Short and PFT#`, e.g. `alpha_ptase_7`.)
- **Bound columns** detected from `Lower_Bound`/`Upper_Bound` (or `lower`/`upper`,
  `min`/`max`).
- **`Default_Value`** is optional. It is used only by Sobol/LHS `--screened-params`
  (non-screened parameters are held at their default; midpoint if no default
  column). Morris ignores it.
- Rows with non-numeric bounds are dropped automatically (so the preamble and any
  separator lines are harmless). Lower must be `<` upper or the parser raises.

**Minimal 3-column format** (a first-time user on a new site can write this):

```
name        lower   upper
param1      0.1     1.0
param2      0.5     2.0
```

### 2. Config knobs (env vars)

Set in the site/round config (`use_cases/<site>/config/<round>_config.sh`):

| Var | Role | Kougarok value |
|-----|------|----------------|
| `A2MC_PARAM_LIST_FILE` | Stage 1 input | `.../parameters/FATES_Parameter_List_Full_162_Finalized.txt` |
| `A2MC_ENSEMBLE_MATRIX_FILE` | Stage 1 output / Stage 2 input | `.../parameters/FATES_CNPnPlantTraits_162param_Morris_4890sets.txt` |
| `A2MC_SALIB_PROBLEM_FILE` | Stage 1 output (Phase 1 reads it) | `.../parameters/salib_problem_162params.txt` |
| `A2MC_SAMPLING_SCHEME` | default `--method` | `morris` |
| `A2MC_N_TRAJECTORIES` | Morris trajectories | `30` |
| `A2MC_BASE_PARAM_FILE` | Stage 2 template `.nc` | `fates_params_api25.5.0_12pft_c230710.nc` |
| `A2MC_PARAM_DIR` | Stage 2 output dir | `.../fates_params_NonPrescribed_..._Morris` |
| `A2MC_PARAM_PATTERN` | per-case `.nc` filename, `{N}` placeholder | `fates_params_..._PtCNP162_En{N}.nc` |
| `A2MC_N_PARAMS`, `A2MC_TOTAL_ENSEMBLE` | Stage 2 sanity checks | `162`, `4890` |
| `A2MC_CASE_NAME_PATTERN` | case name, `{N}`/`{PHASE}` placeholders | `..._PtCNPEn{N}_{PHASE}` |
| `A2MC_CASE_SCRIPTS` | Stage 3 per-case script dir | `.../ReCalibration_PtCNP162_AllPhase_*` |
| `A2MC_ENSEMBLE_OUTPUT` | Stage 3 manifest dir | `$A2MC_OUTPUT_ROOT/$A2MC_ENSEMBLE_NAME` |
| `A2MC_{ADSP,RGSP,TRANS}_*` | spinup/transient protocol (years, suppl N/P, finidat) | per round |

---

## Stage 1 — Sample the parameter space

**Script:** `phases/phase0_design/create_parameter_sample.py`
**Reads:** `$A2MC_PARAM_LIST_FILE`
**Writes:** `$A2MC_ENSEMBLE_MATRIX_FILE` (N_cases × P whitespace floats),
`$A2MC_SALIB_PROBLEM_FILE` (bounds, consumed by
`phases/phase1_exploration/morris_sensitivity_analysis.py`).

Three methods, each with its own count knob. `P` = number of active parameters.

| Method | `--method` | Count knob | N_cases | When |
|--------|-----------|-----------|---------|------|
| Morris (OAT screening) | `morris` (default) | `--trajectories T` (def 30), `--num-levels K` (def 8) | `T·(P+1)` | rank importance (μ*, σ) cheaply at high P |
| Sobol (Saltelli) | `sobol` | `--n-samples N` (def 1024=2^10), `--no-second-order` | `N·(2P+2)` or `N·(P+2)` | interaction structure (S_i, S_Ti, S_ij); expensive |
| LHS | `lhs` | `--n-samples N` | `N` | general-purpose uniform coverage |

For 162 params × 30 trajectories → **30·163 = 4890** cases (the committed
Kougarok matrix).

**Screening for Sobol/LHS at high P:** `--screened-params FILE` (one parameter
name per line) varies only the listed subset; the rest are held at
`Default_Value` (or bound midpoint). The output matrix still has all P columns
(non-screened columns constant) so Stage 2 needs no changes. Not valid for
Morris (which already sweeps every parameter). Typical use: feed the top-K from a
prior Morris μ* ranking into a focused Sobol round.

```bash
# Morris (default; reads all knobs from env)
python phases/phase0_design/create_parameter_sample.py

# explicit Morris
python phases/phase0_design/create_parameter_sample.py --method morris --trajectories 30 --num-levels 8

# Sobol on a screened subset
python phases/phase0_design/create_parameter_sample.py --method sobol --n-samples 1024 \
    --screened-params top20_from_morris.txt

# preview only, no files written
python phases/phase0_design/create_parameter_sample.py --dry-run
```

**Reproducibility:** `--seed` (default 123) fixes the design. The script prints
the sha256 of the matrix it writes — record it in the round log.

> ⚠ **Caution:** running Stage 1 overwrites `$A2MC_ENSEMBLE_MATRIX_FILE`. For
> Kougarok that env var points at the *committed* 4890-set matrix that the
> manuscript runs depend on. To regenerate without clobbering it, pass
> `--output-matrix <scratch path>` (and `--output-problem`), or point the env
> var at a fresh round file before sampling. The api-31-0 reproducibility
> contract means the committed matrix must stay byte-stable.

> 🐞 **Known doc bug:** the script's closing print says
> `Next step: ... create_parameter_files.py`. That filename does not exist; the
> real Stage 2 script is `create_morris_ensemble.py` (below). Fix the print when
> next touching the file.

---

## Stage 2 — Materialize per-case FATES parameter NetCDF files

**Script:** `phases/phase0_design/create_morris_ensemble.py`
**Reads:** `$A2MC_ENSEMBLE_MATRIX_FILE`, `$A2MC_BASE_PARAM_FILE`
**Writes:** one `.nc` per matrix row into `$A2MC_PARAM_DIR`, named by
`$A2MC_PARAM_PATTERN` (`{N}` = 1-based case id).
**Engine:** `tools/modify_fates_parameters.py::create_modified_parameter_file`.

For each row it builds a modifications list (`build_modifications_list`),
clones the base `.nc`, applies the edits, then runs `apply_post_modifications`.

This is the **one site-specific link in the chain.** `build_modifications_list`
hardcodes the column → (FATES name, PFT, organ) mapping for Kougarok's exact 162
columns. The mapping encodes Kougarok modelling rules that any new site must
revisit:

- Columns are grouped PFT#7 → PFT#9 → PFT#10 (CNP block, then plant-trait block),
  then shared/scalar params (cols 134–138), then the 24 "new" params (139–162).
- **`fates_cnp_nfix1` is PFT#9 only** (N-fixer); not sampled for PFT#7/#10.
- **2-organ params** (`fates_cnp_turnover_nitr_retrans`,
  `..._phos_retrans`) take one sampled value applied to **both** organ=1 (leaf)
  and organ=2 (fineroot).
- **`fates_stoich_nitr`/`fates_stoich_phos`** take *separate* leaf and fineroot
  columns.
- `fates_maintresp_nonleaf_baserate` is broadcast to all 12 PFTs; the four
  `fates_phen_*` scalars are written at pft index 0.
- **Post-processing (`apply_post_modifications`):** enforce
  `fates_leaf_slamax ≥ fates_leaf_slatop` per PFT, and set
  `fates_cnp_prescribed_puptake = fates_cnp_prescribed_nuptake = 0` (coupled ECA
  uptake, not prescribed).

It verifies the file count equals N_sets and spot-checks the first and last `.nc`
against the matrix.

**Porting to a new site / parameter list:** rewrite `build_modifications_list`
so its column order matches the new parameter list, and review the special-case
rules above for the new PFT set. The cross-site + JSON-format (api-43+)
generalization is the documented handoff to `main`:
`memory/dev_logs/20260511h_Create_Morris_Ensemble_Refactor_Recommendation.md`.
On this branch it stays NetCDF-only and Kougarok-shaped.

```bash
python phases/phase0_design/create_morris_ensemble.py
```

### Stage 2 alternatives (mutually exclusive per round)

| Round style | Script | Example |
|---|---|---|
| Fresh Morris/Sobol/LHS sampling | `create_morris_ensemble.py` | R2, R3, R4 |
| Reuse an existing NC dir + apply a global override to every case | `apply_param_override.py` (`--source-dir/--dest-dir/--override KEY=VALUE`) | R5 (`prescribed_puptake=1.0` over R3's 4890 NCs) |
| Reuse NC dir + override + top-N ranked subset | `create_subset_replay.py` (reads `ranked_cases` from a prior workflow_state) | old R4 (superseded) |

The override/subset paths skip Stage 1 entirely — they start from a previous
round's `.nc` files and mutate them, preserving source case numbers (use
`submit_phase0.py --cases-file` for the non-sequential numbering).

---

## Stage 3 — Build the first case, generate + reuse-build the rest

**Script:** `phases/phase0_design/submit_phase0.py` (orchestrator)
**Per-case worker:** `tools/create_case.sh --write-script`
**Writes:** `$A2MC_CASE_SCRIPTS/En{N}.sh` (one self-contained script per case),
`$A2MC_ENSEMBLE_OUTPUT/submission_manifest.json`.

The core efficiency idea: **compile FATES once, reuse the binary for every other
case.** A FATES build is ~30 min; reusing it makes each subsequent case ~1–2 min.

What `submit_phase0.py` does:

1. **Stage 3a — generate per-case scripts.** For each case it calls
   `create_case.sh --case-num N --param-file <matching .nc> --config <site_config>
   --write-script $A2MC_CASE_SCRIPTS/En{N}.sh`. The build case is generated with a
   **fresh build**; every other case gets `--reuse-build <build_case>`, which sets
   `EXEROOT` to the build case's compiled `bld/` and marks `BUILD_COMPLETE=TRUE`.
   The matching `.nc` is found via `$A2MC_PARAM_PATTERN` (glob fallback on
   `*En{N}*.nc`).
2. **Manifest** — always written (even dry-run): case range, build case,
   matrix sha256, param dir/pattern, ADSP/RGSP/TRANS protocol, and the detected
   FATES + ELM commit hashes (for the reproducibility record).
3. **Stage 3b — pre-flight validation.** Auto-invokes
   `tools/validate_submission_plan.py` (param files exist, scripts written,
   STOP_N/finidat sanity). A failure aborts before any SLURM submission. Skip with
   `--no-validate`.
4. **Stage 3c.1 — run the build case synchronously.** Executes `En{build}.sh`,
   which builds FATES and submits its own ADSP→RGSP→TRANS chain. Must succeed
   before the rest launch. (`--skip-build-case` when a prior pilot already built
   it; then `build_case` is used only as the `--reuse-build` target.)
5. **Stage 3c.2 — run remaining cases in parallel batches** (`--batch-size`,
   default 20). Each `En{N}.sh` does create_case + `xmlchange EXEROOT` +
   `case.setup` + `case.submit`, queuing its own chain.

Each generated `En{N}.sh` is self-contained: it bakes in the resolved `$A2MC_*`
values at write time (compset, run years/restarts, suppl-N/P flags, finidat,
case-name pattern) and runs the three phases as a SLURM dependency chain
**ADSP (accelerated-decomposition spinup) → RGSP (regular spinup) → TRANS
(transient)**. The case name comes from `$A2MC_CASE_NAME_PATTERN` with `{N}` and
`{PHASE}` filled in.

```bash
# 1) Dry run — generate scripts + manifest + validate, no submission
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --dry-run

# 2) Inspect a couple of scripts
ls -1 $A2MC_CASE_SCRIPTS/En*.sh | head -5

# 3) Real submission (build case 1 fresh, 2..4890 reuse its bld/)
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --submit

# Non-sequential case numbers (override/subset rounds)
python phases/phase0_design/submit_phase0.py --cases-file <list>.txt --submit

# Bulk submission after a separate pilot already built+ran the build case
python phases/phase0_design/submit_phase0.py --start 2 --end 4890 \
    --build-case 1 --skip-build-case --submit
```

> `submit_phase0.py` replaces the deprecated `tools/submit_ensemble.sh` and the
> old casetemplate bundle script. Use it as the single Stage 3 entry point.

---

## Stage 4 — Launch + monitor

Launch is just Stage 3 with `--submit` (above). Once chains are queued, monitor
the ensemble through to >95% TRANS completion, then hand off to Phase 1.

**Live auto-monitor** — `tools/ensemble_auto_monitor.sh` (config-driven; derives
its case-number regex and TRANS-extract glob from `$A2MC_CASE_NAME_PATTERN`). Per
poll it: emits SLURM queue-depth + threshold-crossing events on stdout, detects
new TRANS completions on disk and kicks extraction, regenerates the milestone
ensemble plot (idempotent), and exits on terminal-idle.

```bash
nohup bash tools/ensemble_auto_monitor.sh \
    --launch "2026-06-04 09:00:00" --target-total 4890 \
    >> $A2MC_CASE_SCRIPTS/auto_monitor.log 2>&1 &
```

The stdout event vocabulary (`QUEUE_DEPTH`, `QUEUE_BELOW_THRESHOLD`, `TRANS_DONE`,
`STARTING_EXTRACTION`, `EXTRACTION_TARGET_REACHED`, `*_TERMINAL`) is what a Claude
`Monitor` subscription arms against. See the **`arm-hpc-monitoring`** skill and
`memory/dev_logs/20260514c_Monitoring_Workflow_Pattern_For_HPC_Ensembles.md`
(required reading at session start when an ensemble is in flight, per CLAUDE.md
Rule #6).

**Point-in-time completion accounting** — `tools/diagnose_ensemble_status.py`:

```bash
python tools/diagnose_ensemble_status.py --cases 1-4890
```

It writes `completed_cases_<TS>.txt`, `incomplete_cases_<TS>.txt`, an
`ensemble_status_report_<TS>.txt`, and an auto-validated
`restart_incomplete_<TS>.sh` (these are gitignored transient outputs).

**Restarting failures** — use the **`restart-failed-jobs`** skill. It separates
infrastructure failures (NODE_FAIL, PartitionDown, SIGKILL clusters →
restart-eligible) from model failures (runaway recruitment, PARTEH abort,
mass-balance → NOT restart-eligible without a parameter/model fix), and submits
restarts via `submit_phase0.py --cases-file`.

**Exit criterion → Phase 1.** When >95% of cases have a completed TRANS phase,
proceed to `phases/phase1_exploration/` (extract the Y matrix, run Morris μ*/σ
against `$A2MC_SALIB_PROBLEM_FILE`).

---

## Generalizing for a brand-new site or parameter list

The pipeline is generic **except Stage 2's column mapping**. To stand up a new
site:

1. Write a `use_cases/<site>/parameters/<list>.txt` (full or minimal format).
2. Write a `use_cases/<site>/config/<site>_config.sh` setting the env vars in the
   inputs table (param list, matrix/problem outputs, base `.nc`, param dir +
   pattern, case-name pattern, case-scripts dir, spinup protocol, N_PARAMS).
3. **Stage 1 works unchanged** — auto-detects the header and samples.
4. **Stage 2 needs `build_modifications_list` rewritten** to match the new column
   order and PFT/organ rules (the one non-generic step; see the
   `20260511h` handoff for the cross-site refactor design).
5. **Stages 3–4 work unchanged** — they are fully config-driven.

---

## Quick command sequence (Kougarok, fresh Morris round)

```bash
source a2mc_config.sh
source use_cases/Kougarok/config/kougarok_config.sh

# Stage 1 — sample (use --output-matrix to avoid clobbering the committed matrix)
python phases/phase0_design/create_parameter_sample.py --method morris

# Stage 2 — per-case NetCDF files
python phases/phase0_design/create_morris_ensemble.py

# Stage 3 — generate + validate (dry run first)
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --dry-run

# Stage 3+4 — build case 1 fresh, submit all, then monitor
python phases/phase0_design/submit_phase0.py --start 1 --end 4890 --submit
nohup bash tools/ensemble_auto_monitor.sh --target-total 4890 \
    >> $A2MC_CASE_SCRIPTS/auto_monitor.log 2>&1 &
python tools/diagnose_ensemble_status.py --cases 1-4890   # spot-check anytime
```

---

## Related reading

- `phases/phase0_design/CLAUDE.md` — Phase 0 script-by-script reference
- `phases/phase0_design/README.md` — narrative walkthrough
- `memory/dev_logs/20260511c_Phase0_P1_Sampling_Tool.md` — Stage 1 split rationale
- `memory/dev_logs/20260511h_Create_Morris_Ensemble_Refactor_Recommendation.md` — Stage 2 generalization handoff
- `memory/dev_logs/20260514c_Monitoring_Workflow_Pattern_For_HPC_Ensembles.md` — Stage 4 monitoring pattern
- `.claude/skills/offline-testing-workflow/` — the small-experiment cousin of this full-ensemble flow
- `.claude/skills/arm-hpc-monitoring/`, `.claude/skills/restart-failed-jobs/` — Stage 4 skills
</content>
</invoke>
