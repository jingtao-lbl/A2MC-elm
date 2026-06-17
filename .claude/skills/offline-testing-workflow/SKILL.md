---
name: offline-testing-workflow
description: Design + launch + analyze an A2MC offline HPC experiment (parameter sweep on top of a Morris base case). Use when the user wants to test a hypothesis with N variant runs (e.g., clumping_index sweep, vmax_p sensitivity, hydraulic-vulnerability probe). Codifies the conventions distributed across phases/phase5_testing/, tools/create_case.sh --case-suffix, and prior per-experiment plans in memory/dev_logs/.
---

# Offline Testing Workflow

A reproducible pipeline for running an A2MC HPC experiment (typically 6-10 variants on a Morris base case) and feeding the result into the AI knowledge base. Distilled from `memory/dev_logs/20260519e_Phase4_Clumping_Index_Verification_Experiment_Plan.md` + the H1 misadventure documented in `memory/dev_logs/20260528b,c_*.md`.

## When to invoke

- The user asks for an "experiment", "test", "verify the X hypothesis", "Phase 4/5 run", or "parameter sweep" on a small set (≤ ~10) of variants
- Diagnosis (manual or AI-driven) has surfaced a candidate parameter to test
- An ana_log identifies a mechanistic hypothesis that needs experimental confirmation before updating the knowledge base

Do NOT invoke for:
- Full Morris ensemble runs (use `phases/phase0_design/submit_phase0.py` directly)
- Single-case re-runs (use `tools/submit_experiment.sh` directly with no variant matrix)
- AI-orchestrated Phase 4/5/6 inside a calibration cycle (the orchestrator already does this — don't bypass)

## Step 1 — Search dev_logs FIRST for prior plans on the same topic

This is the #1 lesson from the H1 misadventure. Before writing a new experiment plan, grep `memory/dev_logs/` and `memory/ana_logs/` for prior work:

```bash
# Replace <topic> with the parameter / mechanism you're about to test
grep -lriE "<topic>|<param_name>|experiment.*<topic>" memory/dev_logs/ memory/ana_logs/ 2>/dev/null
```

If a prior plan exists, **read it first** and decide: (a) execute it as-is, (b) augment it with new data, or (c) supersede it with explicit reasoning in a new dev_log. Do NOT silently write a parallel plan.

Concrete example from H1: `20260519e_Phase4_Clumping_Index_Verification_Experiment_Plan.md` existed for 9 days before I wrote `20260526a` — a parallel, inferior plan. The duplication cost ~30 hours of wasted compute and produced contamination in the Morris ensemble.

## Step 2 — Literature review for the candidate parameter

For any FATES (or other-model) parameter being swept, run a focused literature check to:
- Establish whether default values are placeholders vs literature-anchored
- Bracket the plausible numerical range from peer-reviewed measurements
- Surface prior community work that may already answer the question

Tools:
- **`paper-search-mcp`** MCP server (registered in `~/.claude.json`) — for peer-reviewed papers. Use `mcp__paper-search-mcp__search_*` for targeted queries.
- **GitHub queries** for the model repo (e.g., `NGEET/fates`) — community knowledge often surfaces in issues + PRs that don't make it to published literature. Use `curl https://api.github.com/search/issues?q=repo:NGEET/fates+<term>` since `gh` CLI may not be available on the HPC login node.
- **WebSearch** as fallback when MCP isn't loaded.

Capture findings in an ana_log (`memory/ana_logs/<date>_<param>_Literature_Search.md`) with these sections:
1. FATES (or model) community history — who set the default, when, with what justification
2. Peer-reviewed evidence — papers reporting the parameter value for the relevant ecosystem/species
3. Satellite/observational evidence (Step 3 below)
4. Implication for the variant matrix — anchor specific variants to specific evidence sources

The literature review strengthens manuscript framing even when the experimental result is already decided. Skip only if you're literally just re-running an existing plan with no new context.

## Step 3 — Satellite / observational data check for the relevant region

For parameters with measurable real-world analogues (radiation, soil moisture, LAI, biomass), extract a region-specific data value to anchor the variant matrix.

For Arctic / tundra ecosystems (Kougarok-class):
- **MODIS** — `paper-search-mcp` or direct download from ORNL DAAC. For ORNL DAAC files, NASA EarthData OAuth is required (see `memory/dev_logs/<date>_*Literature_Search.md` for the auth setup).
- **NSIDC** — Snow/ice products (some require EarthData, others public).
- **AMERIFLUX / Tower** — for GPP, NEE, energy fluxes at specific sites.
- **NGEE-Arctic data portal** — Kougarok-specific in-situ measurements.

For ELM-FATES specifically, the site coordinates come from `use_cases/Kougarok/config/kougarok_config*.sh` (`A2MC_SITE_LAT`, `A2MC_SITE_LON`).

If the data file is paywalled or requires login, set up `.netrc` once with the user's credentials (chmod 600). Pattern documented in `memory/ana_logs/20260526b_FATES_Clumping_Index_Literature_Search.md` §4.

Document the extracted values in the same ana_log as Step 2.

## Step 4 — Variant design with falsifiability + pre-committed thresholds

Three properties every variant matrix must have:

1. **Control variant (V0/clump00 in the H1 example)** — pure copy of the base case's parameter file. Provides the V0 reproducibility check (does the experiment infrastructure reproduce the R5 baseline NRMSE within machine noise?). If V0 doesn't match, there's a build/env/seed drift — stop and investigate before trusting the variants.

2. **Falsifiability variant** — at least one variant that should produce the OPPOSITE result if the mechanism is wrong. For radiation/clumping mechanisms: PFT9 → 1.0 (anti-correlation) should make PFT10 *worse*. For carbon mechanisms: scale the wrong direction. Without falsifiability, "all variants show the predicted effect" could be coincidence with confounded mechanism.

3. **Pre-committed quantitative thresholds** — write down the ratio / delta / count BEFORE running. The post-result interpretation has no wiggle room. Format example (from `20260519e`):
   - H1 confirmed: target_metric_ratio ≥ 5.0 in any of {variant_A, variant_B, variant_C}
   - H2 (asymmetry) confirmed: target_metric_ratio < 1.5 in {variant_D}
   - H3 (no-harm) confirmed: secondary_metric_ratio > 0.7 in {variant_A..C}

Encode the variant matrix as a Python list of tuples (variant_id, list of parameter overrides). Use the generator pattern from `tools/clumping_exp_make_param_files.py`.

## Step 5 — Dedicated output directories (avoid contamination)

Per `memory/dev_logs/20260519e` §"HPC submission details", set up FOUR dedicated dirs to keep the experiment cleanly separated from the parent Morris ensemble:

| Purpose | Path pattern |
|---|---|
| Param files | `/global/homes/j/jingtao/E3SM_Aid/FATES-ParameterFiles/fates_params_<exp_name>_<YYYYMMDD>/` |
| Case scripts | `/pscratch/sd/j/jingtao/CaseScripts/Kougarok_FATES/<ExpName>_<YYYYMMDD>/` |
| Ensemble output | `/global/cfs/cdirs/m2467/jingtao/Kougarok_<ExpName>_<YYYYMMDD>/` |
| Extracted NCs | `/global/cfs/cdirs/m2467/jingtao/Kougarok_<ExpName>_<YYYYMMDD>_Extract/` |

Set via env-var overrides BEFORE calling `create_case.sh`:

```bash
export A2MC_ENSEMBLE_OUTPUT="/global/cfs/cdirs/m2467/jingtao/Kougarok_<ExpName>_<YYYYMMDD>"
export A2MC_CASE_SCRIPTS="/pscratch/sd/j/jingtao/CaseScripts/Kougarok_FATES/<ExpName>_<YYYYMMDD>"
export A2MC_EXTRACTED_DATA="/global/cfs/cdirs/m2467/jingtao/Kougarok_<ExpName>_<YYYYMMDD>_Extract"
mkdir -p "$A2MC_ENSEMBLE_OUTPUT" "$A2MC_CASE_SCRIPTS" "$A2MC_EXTRACTED_DATA"
```

To reuse the parent ensemble's FATES build (saves ~30 min compile × N variants), set the cross-ensemble bld template:

```bash
export A2MC_REUSE_BUILD_EXEROOT_TEMPLATE="<parent_ensemble_output>/<parent_case1_name_pattern_with_{PHASE}>/bld"
# For R5 PrescribedP example:
# "/global/cfs/cdirs/m2467/jingtao/Kougarok_PlantTraitsCNPEnsemble162_PrescribedP/Kougarok_ELM-FATES_PtCNPEn1PrescP_{PHASE}/bld"
```

Verify the parent bld dirs exist before submitting (`ls -d <template>/{ADSP,RGSP,TRANS}/bld`).

## Step 6 — Generate parameter files (one per variant)

Write a small Python script (~80 lines) that loops over the variant matrix and produces one modified NC per variant. Use `tools/modify_fates_parameters.create_modified_parameter_file()` directly — it handles the copy + per-parameter override + verification within a single call.

```python
# tools/<exp_name>_make_param_files.py
from pathlib import Path
import shutil
from tools.modify_fates_parameters import create_modified_parameter_file

BASE_CASE = 1304
SOURCE_PARAM_DIR = Path(os.environ["A2MC_PARAM_DIR"])  # Morris param dir
TARGET_PARAM_DIR = Path("/global/.../fates_params_<exp>_<YYYYMMDD>/")
PARAM_PATTERN = "fates_params_api25.5.0_12pft_c230710__PtCNP162_En{N}.nc"

# Variant matrix: list of (variant_id, [(pft, value), ...])
VARIANTS = [
    ("clump00", []),                       # control: pure copy, no override
    ("clump01", [(9, 0.80)]),              # single-PFT override
    ("clump05", [(7, 0.60), (9, 0.60)]),   # multi-PFT override
    # ... etc
]

in_file = SOURCE_PARAM_DIR / PARAM_PATTERN.replace("{N}", str(BASE_CASE))
TARGET_PARAM_DIR.mkdir(parents=True, exist_ok=True)

for variant_id, overrides in VARIANTS:
    out_name = PARAM_PATTERN.replace("{N}", str(BASE_CASE)).replace(".nc", f"_{variant_id}.nc")
    out_file = TARGET_PARAM_DIR / out_name

    if not overrides:
        shutil.copy2(in_file, out_file)   # control: byte-for-byte copy
    else:
        mods = [{"param": "<param_name>", "pft": pft, "value": val}
                for pft, val in overrides]
        create_modified_parameter_file(in_file, out_file, mods, verbose=False)
```

Also write a flat manifest TSV (`tmp/<exp_name>_manifest_<YYYYMMDD>.tsv`) so downstream analysis can map variant_id → overrides → nc_file deterministically. Pattern documented in `tools/clumping_exp_make_param_files.py`.

## Step 7 — Verify parameter modifications (FAILED VERIFICATION = HALT, don't submit)

Before submitting 24+ HPC jobs, confirm the param files actually contain what the variant matrix says they contain. **Two complementary checks** — neither alone is sufficient.

### A2MC tools landscape — three validators, three jobs

| Tool | What it validates | Used here? |
|---|---|---|
| `tools/modify_fates_parameters.verify_modifications()` (function in the same module that does the modifications) | Each (param, pft, value) tuple in a variant NC matches the expected modification | **Yes — Step 7a** |
| `tools/verify_parameter_file.py` (standalone script) | A Morris-ensemble NC's values match its row in the Morris X matrix (column-by-column for all 162 params) | **No** — built for Morris cases, doesn't apply to modified variants |
| `tools/validate_submission_plan.py` (standalone script) | Pre-flight submission checks: env vars, all per-case param files exist, no unresolved `{N}`/`{PHASE}` tokens in case scripts, no queue collisions, build case plausible | **Yes — Step 9 (pre-submission)** |

### 7a — Programmatic verification per variant

`tools/modify_fates_parameters.py` exposes `verify_modifications(nc_file, expected_modifications)`. The wrapper script that generated the variants (Step 6) can call this directly after each `create_modified_parameter_file()` call:

```python
from tools.modify_fates_parameters import create_modified_parameter_file, verify_modifications

mods = [{"param": "<param_name>", "pft": pft, "value": val} for pft, val in overrides]
create_modified_parameter_file(in_file, out_file, mods, verbose=False)
verify_modifications(out_file, mods, verbose=True)   # halts on mismatch
```

Or run the standalone tool with `--verify` per file:
```bash
python tools/modify_fates_parameters.py --input <in> --output <out> --param <name> --pft <N> --value <V> --verify
```

### 7b — Sanity check: control variant inherits base case mtime

Caveat for the control variant: if Step 6 used `shutil.copy2(in_file, out_file)` to produce V0 (recommended pattern for byte-for-byte fidelity), the control's mtime is INHERITED from the source — NOT the moment of generation. So a fresh-looking variant matrix may appear to contain a "stale" control file. This is expected, not a bug. For freshness checks on V1+ (modified variants), `create_modified_parameter_file()` writes fresh, so their mtime IS the generation time.

### 7c — Direct ncdump sanity check on a sample

A 30-second visual check on at least the control (V0) + each variant family covers the case where the generator script silently mismatched the PFT index (e.g., 0-based vs 1-based off-by-one). Example for the clumping experiment:

```bash
module load python > /dev/null 2>&1
python3 -c "
import netCDF4 as nc
from pathlib import Path
pdir = Path('<target_param_dir>')
# Verify: V0 == base; V1-V5 differ in expected PFT slots; falsifier differs OPPOSITE
checks = [
    ('clump00', 'control — should match base'),
    ('clump01', 'PFT9=0.80'),
    ('clump05', 'PFT7+PFT9=0.60'),
    ('clump06', 'PFT10=0.50 (asymmetry)'),
    ('clump07', 'PFT9=1.00 (anti-correlation falsifier)'),
]
for variant_id, label in checks:
    f = pdir / f'fates_params_..._En<base>_{variant_id}.nc'
    with nc.Dataset(f) as ds:
        c = list(ds.variables['<param_name>'][:])
        print(f'{variant_id:<10} {label:<35} {[round(float(x), 2) for x in c]}')
"
```

Visually confirm:
- Control variant matches the base case (byte-for-byte)
- Each override changes ONLY the targeted PFT slot(s) (0-based: PFT7 → index 6, PFT9 → index 8, PFT10 → index 9)
- Untargeted slots are identical across variants

### What to do if verification fails

- Don't submit. The cost of finding the bug after 24 hours of HPC compute is far higher than the cost of fixing it now.
- Common causes: 0-based vs 1-based PFT index confusion, parameter name typo (FATES variable names are long and easy to mistype), wrong base case path, write/copy race condition between control and modified writes.
- Fix the generator, regenerate, re-verify. Iterate until all checks pass.

## Step 8 — Case-suffix naming convention (CRITICAL)

Use `create_case.sh --case-suffix` to name experiment cases. **NEVER invent out-of-Morris-range case numbers.**

```bash
./tools/create_case.sh \
    --case-num <base_case>          \  # preserves Morris lineage (e.g., 1304)
    --case-suffix <variant_id>      \  # differentiates from Morris case (e.g., clump02)
    --param-file <path/to/En<base>_<variant>.nc> \
    --phases "ADSP RGSP TRANS"      \
    --output-root <dedicated_ensemble_output> \
    --submit
```

Resulting case name: `<prefix>_PtCNPEn<base>PrescP_<variant>_<PHASE>` (e.g., `Kougarok_ELM-FATES_PtCNPEn1304PrescP_clump02_TRANS`).

**Why this matters:** Morris analysis tools (`r5_auto_monitor.sh`, `screen_ensemble.py`, etc.) use the filename pattern `*PrescP_TRANS_*.nc` to identify Morris cases. Experiment case names include the suffix between `PrescP` and `_TRANS_`, so the literal substring `PrescP_TRANS` does NOT appear in the experiment filename — naturally excluded from Morris analysis without any case-number filtering.

The param filename follows the same pattern: `fates_params_..._En<base>_<variant>.nc` (e.g., `fates_params_..._En1304_clump02.nc`).

**Verify before submitting**: `echo "<case_name>" | grep "PrescP_TRANS"` should return empty.

## Step 9 — Submit + arm Monitor (with pre-flight validation)

### 9a — Run pre-flight validation BEFORE the loop

`tools/validate_submission_plan.py` catches submission foot-guns (missing param files, unresolved tokens in case scripts, queue collisions, missing env vars). It's auto-invoked by `phases/phase0_design/submit_phase0.py` between Stages 3a and 3c — but the experiment workflow uses `create_case.sh` directly, bypassing that auto-call. **Run it manually**:

**Critical path knowledge** (`reference_a2mc_path_topology` auto-memory): the pre-flight check for case dirs must look at `${A2MC_E3SM_ROOT}/cime/scripts/<case_name>/`, NOT under `${A2MC_ENSEMBLE_OUTPUT}`. CIME hardcodes case dir location to `${E3SM_ROOT}/cime/scripts/` regardless of `--output-root`. Only the RUN dirs land under `${A2MC_ENSEMBLE_OUTPUT}/<case_name>/run/`. This distinction is the #1 path-knowledge gap when validating an experiment's submission state.

| Want to verify... | Look at |
|---|---|
| All 24 case dirs were created by create_case.sh | `${A2MC_E3SM_ROOT}/cime/scripts/Kougarok_ELM-FATES_PtCNPEn<base>PrescP_<variant>_<PHASE>/` |
| All jobs are queued | `squeue -u $USER -h --format=%j \| grep <variant_id>` |
| Param files exist for all variants | `ls ${TARGET_PARAM_DIR}/fates_params_..._En<base>_<variant>.nc` |
| Build path is valid (if reusing parent ensemble bld) | `ls -d ${A2MC_REUSE_BUILD_EXEROOT_TEMPLATE/{PHASE}/ADSP}` |
| RUN dirs exist (only AFTER first job starts) | `${A2MC_ENSEMBLE_OUTPUT}/<case_name>/run/` (empty until run begins) |

```bash
# For an experiment with cases 1304 only and case-suffix variants, the validator's
# --start/--end model doesn't directly apply (it iterates a range of case numbers).
# Adapt by either:
#   (a) writing a small wrapper that checks the 4 things the validator cares about
#       (param files, case scripts, env, queue) for each (base_case, variant) pair, OR
#   (b) running submit_phase0.py --dry-run with the expanded case list to trigger
#       Stage 3b's auto-validate, then read the validator's output.
# Cleanest: option (a). Pattern (~30 lines):
for variant in clump00 clump01 ... clump07; do
    p="$TARGET_PARAM_DIR/fates_params_..._En${BASE}_${variant}.nc"
    [ -f "$p" ] || { echo "MISSING: $p"; exit 1; }
done
# Plus check env vars + queue per the validator's logic.
```

If the validator fails, fix BEFORE submitting. Same rule as Step 7: cheap to fix now, expensive to fix after compute is wasted.

### 9b — Loop create_case.sh per variant in a small bash wrapper

Pattern documented in `tools/clumping_exp_submit.sh`. Each variant's invocation:

```bash
./tools/create_case.sh \
    --case-num <base>            \
    --case-suffix <variant_id>   \
    --param-file <variant_nc>    \
    --phases "ADSP RGSP TRANS"   \
    --output-root <dedicated>    \
    --submit
```

### 9c — Arm Claude Monitor

Arm a Monitor on the submitter log with the standard filter from the `arm-hpc-monitoring` skill:

```text
tail -F -n 0 <submitter_log> | grep -E --line-buffered \
    "Submission complete|\[[0-9]+/N\]|ERROR|Traceback|FAILED|sbatch:|Job ID|Killed"
```

(Replace `N` with the number of variants.)

## Step 10 — V0 reproducibility check FIRST (hard gate)

> **Concrete tool (use this):** `tools/extract_and_plot_selected_cases.py` implements Steps 10–11 as three subcommands — `extract`, `v0check`, `plot`. It is generic (base case + variant suffixes + dirs are all CLI args; nothing experiment-specific is hardcoded) and **reuses the production extractor's `process_case()` without touching its `_exp`-gated Phase-5/6 pre-flight** (see `<auto-memory>/feedback_do_not_change_extractor_case_naming.md` — do NOT "generalize" `tools/extract_monthly_variables_FATES.py` to accept non-`_exp` suffixes). First end-to-end exercise: the clumping experiment, `memory/dev_logs/20260531a` + `memory/ana_logs/20260531a`.
>
> ```bash
> # extract (output → dedicated dir, keeps the Morris extract dir clean)
> python tools/extract_and_plot_selected_cases.py extract \
>     --base <N> --suffixes <s0> <s1> ... \
>     --ensemble-output "$A2MC_ENSEMBLE_OUTPUT" \
>     --extract-dir <DEDICATED_EXTRACT_DIR> --parallel 8
> # V0 gate (exit 2 on FAIL)
> python tools/extract_and_plot_selected_cases.py v0check \
>     --control-case-id <N>_<control_suffix> \
>     --extract-dir <DEDICATED_EXTRACT_DIR> \
>     --ref-nc "$A2MC_EXTRACTED_DATA/<base_case>_TRANS_all_variables_monthly_1901_2019.nc"
> # overlay plot
> python tools/extract_and_plot_selected_cases.py plot \
>     --base <N> --suffixes <s0> <s1> ... \
>     --extract-dir <DEDICATED_EXTRACT_DIR> --output <PNG>
> ```

When the first variant's TRANS phase completes, run extraction + NRMSE comparison against the original Morris case's results. **Do not proceed with V1+ analysis until V0 matches within machine noise (ΔNRMSE ≤ 0.005).**

If V0 doesn't reproduce:
- Same FATES build? Same param file? Same forcing data?
- Build/env/seed drift between Morris run and experiment run
- Stop and investigate; the variants' results are not interpretable until V0 is validated

The V0 control is the load-bearing variant of the design — without it, you cannot distinguish a real mechanism signal from infrastructure drift.

## Step 11 — Analysis + decision tree → KB injection

Compute the pre-committed metrics from Step 4. Apply the decision tree from the experiment plan:

| Outcome | Action |
|---|---|
| **CONFIRMED** (all thresholds met) | Execute companion KB-injection plan with `verified: true`, `confidence: ≥0.85`. Write ana_log documenting experimental confirmation. Recommend next-round parameter-space expansion. |
| **PARTIAL** (some thresholds met, others borderline) | Execute KB-injection plan with `verified: true`, `confidence: 0.5-0.7`. Design follow-up experiment combining this parameter with adjacent candidates. |
| **REFUTED** (thresholds not met OR falsifiability variant shows wrong direction) | DO NOT execute KB-injection plan. Update the source ana_log with refutation note. Redirect investigation to alternative hypotheses. |

The KB injection plan should be a companion dev_log that documents WHAT to add to `memory/gained_knowledge/discoveries.json` and the matching site-specific `gained_knowledge/` files. Example pattern: `memory/dev_logs/20260519d_Inject_Clumping_Index_Knowledge_Into_A2MC_AI.md` is the companion to `20260519e`.

## Step 12 — Write the result ana_log + cross-link

Per A2MC convention, the experiment's scientific outcome lives in `memory/ana_logs/<date>_<exp_name>_Results_<Confirms|Refutes>_<Hypothesis>.md`. Include:
- Quantitative results table (one row per variant, all pre-committed metrics)
- Comparison plot (use `use_cases/<site>/analysis/<plot_script>.py`)
- Decision outcome + which KB injection (if any) was triggered
- Manuscript implications (how this changes the methods/discussion framing)

Cross-link from:
- The experiment plan dev_log (add a "Result" section pointing at the ana_log)
- The source ana_log (the one that proposed the hypothesis — add a Resolution note)
- `memory/gained_knowledge/discoveries.json` (if KB injection occurred)

## Anti-patterns (what to NOT do)

1. **Don't invent case numbers above the Morris range.** This was the H1 bug — case numbers 5001-5018 share the Morris case-name pattern, contaminating the auto-monitor and Morris screening. Use `--case-suffix` instead. See `memory/dev_logs/20260528b`.

2. **Don't share extraction directories with the parent Morris ensemble.** The dedicated `$A2MC_EXTRACTED_DATA` override per Step 5 is non-negotiable. Skipping this requires post-hoc cleanup (move/delete contaminating NCs) which is expensive and error-prone.

3. **Don't skip Step 1 (search dev_logs).** This is the #1 lesson from the H1 misadventure. A prior plan for the SAME experiment likely exists.

4. **Don't skip falsifiability or pre-committed thresholds.** Both are easy to lose in a hurry. Without falsifiability, your "confirmation" might be coincidence. Without pre-commitment, the "interpretation" can drift to match whatever the experiment produces.

5. **Don't bypass the V0 reproducibility check.** Without V0, you cannot distinguish a real mechanism signal from infrastructure drift.

6. **Don't run >10 variants in one experiment.** If you have more than ~10 candidate variants, the design probably hasn't been narrowed down enough — consider splitting into sequential experiments, with each informing the next.

7. **Don't skip Step 7 (parameter file verification) before submitting.** The cost of finding a generator bug after 24+ hours of HPC compute is much higher than the cost of catching it in a 30-second ncdump check. A common failure mode: 0-based vs 1-based PFT index confusion silently modifies the wrong PFT.

## Cross-references

### In-repo authoritative docs (READ FIRST when in doubt)
- `docs/a2mc_reference/tools_reference.md` — A2MC tools API (cost functions, phase logger, workflow status, two-level config, `tools/config.py` Python API, case-name pattern, diagnose_ensemble_status outputs, phase year ranges, AI provider switching)
- `docs/a2mc_reference/fates_data_reference.md` — FATES parameter file dimensions, PFT names with array-index mapping (PFT7=idx6, PFT9=idx8, PFT10=idx9), official parameter naming convention (no PFT suffix), output dimension levels, SZPF index formula `(pft-1)×13`, unit conventions, ELM no-leap-year calendar
- `docs/a2mc_reference/rag_reference.md` — RAG/GraphRAG for FATES knowledge queries during diagnosis/design

### Auto-memories
- **Path topology reference** (READ FIRST if unsure about any path): `<auto-memory>/reference_a2mc_path_topology.md`
- Phase 5 case-naming convention: `<auto-memory>/feedback_phase5_case_naming_convention.md`
- Round-specific config sourcing: `<auto-memory>/feedback_use_round_specific_kougarok_config.md`

### Worked examples / prior plans
- Canonical worked example: `memory/dev_logs/20260519e_Phase4_Clumping_Index_Verification_Experiment_Plan.md`
- Reconciliation log when this skill was distilled: `memory/dev_logs/20260528c_H1_Cancellation_Reconciliation_With_20260519e.md`

### Companion skills
- `.claude/skills/arm-hpc-monitoring/SKILL.md` — arms HPC monitoring during the experiment
- `.claude/skills/restart-failed-jobs/SKILL.md` — handles failures during the experiment

### Phase 5 source code
- `phases/phase5_testing/{design_experiments,submit_experiments}.py` — orchestrator-driven path
- `tools/create_case.sh` (--case-suffix flag is the load-bearing convention element)
- `tools/submit_experiment.sh` — single-experiment harness
- `tools/modify_fates_parameters.py` — `create_modified_parameter_file()` + `verify_modifications()`
- `tools/validate_submission_plan.py` — pre-flight validator (auto-invoked by submit_phase0.py, must be invoked manually for experiments)
