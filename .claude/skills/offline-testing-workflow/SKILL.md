---
name: offline-testing-workflow
visibility: public
category: calibration
description: Design + launch + analyze an A2MC offline HPC experiment (parameter sweep on top of a Morris base case). Use when the user wants to test a hypothesis with N variant runs (e.g., clumping_index sweep, vmax_p sensitivity, hydraulic-vulnerability probe). Codifies the conventions distributed across phases/phase5_testing/, tools/create_case.sh --case-suffix, and prior per-experiment plans in memory/dev_logs/.
modes:
  requires_fates: true
  nutrient_pathway: any
  scope: [analysis]
  summary: "Design+launch+analyze a FATES parameter-sweep experiment on a Morris base case (HPC); requires FATES. Paths come from a2mc_config.sh config vars."
---

# Offline Testing Workflow

A reproducible pipeline for running an A2MC HPC experiment (typically 6-10 variants on a Morris base case) and feeding the result into the AI knowledge base. Distilled from the originating dev/ana log + the H1 misadventure documented in `the originating dev/ana log,c_*.md`.

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

For ELM-FATES specifically, the site coordinates come from `use_cases/ELM-FATES_Kougarok/config/kougarok_config*.sh` (`A2MC_SITE_LAT`, `A2MC_SITE_LON`).

If the data file is paywalled or requires login, set up `.netrc` once with the user's credentials (chmod 600). Pattern documented in the originating dev/ana log §4.

Document the extracted values in the same ana_log as Step 2.

## Step 4 — Variant design with falsifiability + pre-committed thresholds

Three properties every variant matrix must have:

1. **Control variant (V0/clump00 in the H1 example)** — pure copy of the base case's parameter file. Provides the V0 reproducibility check (does the experiment infrastructure reproduce the R5 baseline NRMSE within machine noise?). If V0 doesn't match, there's a build/env/seed drift — stop and investigate before trusting the variants.

2. **Falsifiability variant** — at least one variant that should produce the OPPOSITE result if the mechanism is wrong. For radiation/clumping mechanisms: PFT9 → 1.0 (anti-correlation) should make PFT10 *worse*. For carbon mechanisms: scale the wrong direction. Without falsifiability, "all variants show the predicted effect" could be coincidence with confounded mechanism.

3. **Pre-committed quantitative thresholds** — write down the ratio / delta / count BEFORE running. The post-result interpretation has no wiggle room. Format example (from `20260519e`):
   - H1 confirmed: target_metric_ratio ≥ 5.0 in any of {variant_A, variant_B, variant_C}
   - H2 (asymmetry) confirmed: target_metric_ratio < 1.5 in {variant_D}
   - H3 (no-harm) confirmed: secondary_metric_ratio > 0.7 in {variant_A..C}

Encode the variant matrix as a Python list of tuples (variant_id, list of parameter overrides), then map each tuple to a per-case FATES parameter file via `tools/modify_fates_parameters.py`. A worked example of this generator pattern: `tools/estab_exp_make_param_files.py` (the PFT10-establishment 6-variant generator) — note it is an **api-31 demo example** (12-PFT `.nc`, base case #488, `PFT10` = api-31 graminoid ≠ api-43's PFT10 evergreen shrub), so reuse the *pattern*, not its specific PFT ids / values / param format.

## Step 5 — Dedicated output directories (avoid contamination)

Per the originating dev/ana log §"HPC submission details", set up dedicated dirs to keep the experiment cleanly separated from the parent Morris ensemble:

| Purpose | Path pattern |
|---|---|
| Param files | `$A2MC_OUTPUT_ROOT/ParameterFiles/fates_params_<exp_name>_<YYYYMMDD>/` |
| Case scripts **+ run/submitter logs** | `use_cases/{site}/memory/phase_results/{stem}/` (repo-tracked, the same folder `calibration-log` creates for this experiment) — the `--write-script` launcher (e.g. `run_En<base>_<exp>.sh`) and the launcher/submitter running log (the `<submitter_log>` armed in Step 9c) live HERE, alongside the experiment's param-modification generator, param files (if small), figures, and captions. **Not** `$A2MC_SCRIPTS_DIR`/scratch, **not** `~`, **not** a system tmp — those durability requirements apply here too. |
| Ensemble output | `$A2MC_OUTPUT_ROOT/<ExpName>_<YYYYMMDD>/` |
| Extracted NCs | `$A2MC_OUTPUT_ROOT/<ExpName>_<YYYYMMDD>_Extract/` |

`$A2MC_SCRIPTS_DIR`/`A2MC_CASE_SCRIPTS` is Morris **ensemble-scale** infrastructure (`submit_phase0.py` writes thousands of auto-generated per-case scripts there; `validate_submission_plan.py`/`diagnose_ensemble_status.py` read it back) — high-volume and regenerable, so scratch is the right home for it. A small (≤~10-variant) offline experiment's case script(s) are hand-authored/reviewed, not auto-generated at that volume, and are exactly the kind of durable per-experiment record `phase_results/{stem}/` exists for (`calibration-discipline` item 2) — don't route them through the ensemble env var at all.

Set via env-var overrides BEFORE calling `create_case.sh` (only the ensemble-output and extract dirs — case scripts need no env var, they're just written to `phase_results/{stem}/` directly):

```bash
export A2MC_ENSEMBLE_OUTPUT="$A2MC_OUTPUT_ROOT/<ExpName>_<YYYYMMDD>"
export A2MC_EXTRACTED_DATA="$A2MC_OUTPUT_ROOT/<ExpName>_<YYYYMMDD>_Extract"
mkdir -p "$A2MC_ENSEMBLE_OUTPUT" "$A2MC_EXTRACTED_DATA"
```

To reuse the parent ensemble's FATES build (saves ~30 min compile × N variants), set the cross-ensemble bld template:

```bash
export A2MC_REUSE_BUILD_EXEROOT_TEMPLATE="<parent_ensemble_output>/<parent_case1_name_pattern_with_{PHASE}>/bld"
# For R5 PrescribedP example:
# "$A2MC_OUTPUT_ROOT/<parent_ensemble>/<case1_name>_{PHASE}/bld"
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
TARGET_PARAM_DIR = Path(os.environ["A2MC_OUTPUT_ROOT"]) / "ParameterFiles" / "fates_params_<exp>_<YYYYMMDD>"
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

Also write a flat manifest TSV (`use_cases/{site}/memory/phase_results/{stem}/<exp_name>_manifest_<YYYYMMDD>.tsv` — same durable, repo-tracked folder as Step 5's case scripts, NOT the repo's `tmp/` and NOT a system `/tmp`) so downstream analysis can map variant_id → overrides → nc_file deterministically. (The `phase_results/{stem}/` rule for case scripts/logs/manifest is scoped to **these small offline experiments** — an **ensemble-scale** run keeps its auto-monitor/submitter logs in the repo's `tmp/` per `arm-hpc-monitoring`; don't over-apply either convention to the other's scale.)

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

**Critical path knowledge — case dir and run dir are NOT co-located.** Source the machine + active-round site configs first, then read both roots off the environment (`${A2MC_E3SM_ROOT}`, `${A2MC_ENSEMBLE_OUTPUT}`); never take a path from a memory, which can go stale against a config change. The **layout** is a CIME structural fact, verifiable in `tools/create_case.sh:651`: CIME places the case dir under `${A2MC_E3SM_ROOT}/cime/scripts/<case_name>/` regardless of `--output-root`, while only the RUN dirs land under `${A2MC_ENSEMBLE_OUTPUT}/<case_name>/run/`. So the pre-flight check for case dirs must look under `cime/scripts/`, **not** under the ensemble output root. This distinction is the #1 path-knowledge gap when validating an experiment's submission state.

| Want to verify... | Look at |
|---|---|
| All 24 case dirs were created by create_case.sh | `${A2MC_E3SM_ROOT}/cime/scripts/Kougarok_ELM-FATES_PtCNPEn<base>PrescP_<variant>_<PHASE>/` |
| All jobs are queued | `squeue -u $USER -h --format=%j \| grep <variant_id>` |
| Param files exist for all variants | `ls ${TARGET_PARAM_DIR}/` — extension follows the API milestone: **`.json` on api-43+**, `.nc`/`.cdl` on api-31 and earlier. Match `${A2MC_PARAM_PATTERN}` from the site config rather than assuming either. |
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

Submit each variant via `tools/create_case.sh` (`--case-suffix`) — see `phases/phase5_testing/submit_experiments.py`. Each variant's invocation:

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

Arm a Monitor on the submitter log — `<submitter_log>` is the launcher/submitter running log, which lives **in `use_cases/{site}/memory/phase_results/{stem}/`** (per Step 5), not `$A2MC_SCRIPTS_DIR`/scratch and not `~` — with the standard filter from the `arm-hpc-monitoring` skill:

```text
tail -F -n 0 <submitter_log> | grep -E --line-buffered \
    "Submission complete|\[[0-9]+/N\]|ERROR|Traceback|FAILED|sbatch:|Job ID|Killed"
```

(Replace `N` with the number of variants.)

### 9d — Resume a chain that ran out of wall clock (TIMEOUT)

A TIMEOUT is **neither** of the two failure modes `restart-failed-jobs` triages. The model ran correctly
and the clock ran out, so this is a **continuation**, not a re-run, and the "is it infrastructure or is it
model" question does not apply. That skill is also built around the Morris ensemble (numbered cases,
`submit_phase0.py --cases-file`), so it cannot be *driven* on a suffixed experiment case: `make_case_name()`
formats `{N}`/`{PHASE}` only and cannot express `_<variant_id>`.

**Use `tools/restart_experiment_case.py` — the shortcut for this exact scenario.** It works identically
for **any of the three phases restarting itself** (ADSP, RGSP, or TRANS) — one function, same forcing-cycle
and carbon-only gates, self-contained (reads `CIME_OUTPUT_ROOT` and the forcing-cycle window from the
case's own `env_*.xml`, no ensemble config needed):

```bash
python tools/restart_experiment_case.py --case-dir <CASEROOT>              # dry run -- prints the plan
python tools/restart_experiment_case.py --case-dir <CASEROOT> --execute \
    --output-script use_cases/<site>/memory/phase_results/{stem}/restart_<case_name>_<YYYYMMDD>.sh
```

**`--output-script` is not optional in practice — point it at `phase_results/{stem}/`, never `tmp/`.**
Per Step 5's artifact-placement rule (below), the generated plan is the durable record of what was done
to a case; `--execute` without `--output-script` prints a warning and leaves nothing on disk once the
terminal scrolls. Repo-relative `tmp/` is the wrong destination too — that convention is
**ensemble-scale** (`arm-hpc-monitoring`'s auto-monitor/submitter logs), not this one's.

**It also cascade-repairs the downstream chain automatically (as of 2026-08-16).** If ADSP or RGSP
already has a downstream phase queued (RGSP/TRANS), restarting the upstream one leaves that queued job
chained to the now-superseded old job ID — `restart_experiment_case.py --execute` detects this, cancels
the stale downstream job, and resubmits it with `--dependency=afterok:<the new job ID>`, then repeats for
however many phases are queued below it (RGSP's own resubmit can itself invalidate an already-queued
TRANS, and the cascade catches that too). It never touches a downstream job that's already `RUNNING` —
only a genuinely stale `PENDING` one. Found live 2026-08-16: restarting `RGnone_RGSP` left the
already-queued `RGnone_TRANS` chained to the dead old RGSP job for ~30 hours, undetected, before a
routine status check surfaced it — see
`memory/dev_logs/reflection/20260816a_Reflection_Restart_Tool_Left_A_Zombie_Its_Own_Docstring_Warned_About.md`.
For a chain repair needed *outside* this tool (e.g. after a manual, un-tooled `case.submit` resubmit),
run the cascade standalone: `restart_experiment_case.py --rechain-downstream --case-dir <that phase>
--new-jobid <ITS_NEW_JOBID>`.

**Two edge cases the tool (and the authoritative generator it mirrors,
`tools/diagnose_ensemble_status.py::generate_phase_submit_command()`) handle automatically:**

1. **`nyears_ad_carbon_only` is dropped ONLY if the restart year has moved past the carbon-only window.**
   ADSP's carbon-only window (default 30 years) is a property of the *simulation stage*, not of whether
   this is a restart. If the (possibly cycle-snapped-back) restart year is still `<=` the case's own
   `nyears_ad_carbon_only` value, that namelist line is **kept** — the restart must stay in carbon-only
   mode too. Example: a checkpoint at year 31 snaps back to year 21 (20-year forcing cycle) — 21 is still
   inside a 30-year carbon-only window, so `nyears_ad_carbon_only = 30` survives the sed.
2. **A restart with no progress beyond the first forcing cycle is a bare resubmit, not a namelist edit.**
   If the last checkpoint's cycle-aligned year equals the phase's own start year (e.g. only a year-11
   checkpoint exists under a 20-year cycle — nothing to snap back to), the correct action is `cd <case>;
   ./case.submit ...` with **no** `xmlchange`/`sed`/`case.setup` at all: that machinery only adds risk for
   a case that is already, numerically, in its pristine as-created state.

**Why cycle-snap-back only matters for ADSP/RGSP, not TRANS:** ADSP and RGSP use `REST_N=10` (a restart
file written every 10 years, to keep multi-century spin-up runs fast), so a crash can leave the last
checkpoint off the 20-year forcing-cycle boundary and it must be snapped back. TRANS uses `REST_N=1`
(every year) — with a restart file for every year, the last checkpoint is always usable as-is, so no
snap-back is ever needed there. This is a property of this project's `REST_N` choice for speed, not an
inherent ADSP/RGSP-vs-TRANS asymmetry.

**Manually, this is what the tool does under the hood** (useful if you need to hand-verify or the tool
doesn't apply):

```bash
YEAR=<last restart year, possibly cycle-snapped>   # from rpointer.lnd / the case's restart files, NOT the log
STOP_N=$(( END_YEAR - YEAR + 1 ))                  # TRANS END_YEAR=2019 -> restart 1975 gives STOP_N=45
cd "$CASEROOT"
./xmlchange STOP_N=$STOP_N
./xmlchange RUN_STARTDATE=${YEAR}-01-01
sed -i '/^finidat/d' ./user_nl_elm                 # name-targeted, not positional (see trap #3)
# ADSP only, and only if YEAR is still inside the carbon-only window: also
# sed -i '/^nyears_ad_carbon_only/d' ./user_nl_elm  when YEAR has moved past it
echo "finidat = '<RUNDIR>/<case>.elm.r.${YEAR}-01-01-00000.nc'" >> user_nl_elm
./case.setup                                        # NOT --reset, see below
./case.submit --batch-args="-q shared --mem=16G"
```

**Four traps, all of which cost time on 2026-08-08 (trap #3 fixed 2026-08-14, see the tool above):**

1. **`./case.setup --reset` clears `BUILD_COMPLETE`**, and every submit then dies with
   `ERROR: Build complete is not True`. The recipe says plain `./case.setup` for a reason. If you have
   already done it, do **not** rebuild: these experiments share one `e3sm.exe` that `--reset` never
   touches, so verify the executable exists and is unchanged, then `./xmlchange BUILD_COMPLETE=TRUE`.
2. **Do not build `finidat` from `$A2MC_ENSEMBLE_OUTPUT`.** The live config points at the *current* round,
   while an older experiment's cases live in a previous round's tree. Take the literal paths from the
   case's own `run/CASEROOT` and `run/rpointer.lnd`.
3. **A positional `sed -i '$ d'` deletes the last line(s) blind**, which silently corrupts any case whose
   `user_nl_elm` has a manual append after the generic template's trailing lines (e.g. a one-off namelist
   flag with no `--write-script` CLI flag yet). `restart_experiment_case.py` and
   `diagnose_ensemble_status.py` both target lines **by name** (`/^finidat/d`, `/^nyears_ad_carbon_only/d`)
   instead — safe regardless of what else got appended. If hand-applying, target by name too, never by
   position.
4. **Check the wall-clock arithmetic before submitting.** `years_remaining x 17520 / (measured steps per
   hour)` against the QOS ceiling (48h at NERSC). If it does not fit, the run will time out again at a
   predictable year: say so up front rather than discovering it two days later. Do **not** reach for
   `RESUBMIT=1` to cover the gap: CIME re-runs `STOP_N` *more* years on the next segment, overshooting the
   forcing data. Submit sequential segments instead.

**Artifacts go with the experiment, not in `tmp/`.** The restart script, its watcher and their logs belong
in `use_cases/<site>/memory/phase_results/{stem}/` — they are the durable record of what was done to those
cases. Repo-relative `tmp/` is for **ensemble-scale** monitor/submitter logs (the `arm-hpc-monitoring`
convention); do not over-apply it to a handful of experiment cases. `restart_experiment_case.py`'s
`--output-script` (above) is how the restart script itself lands there — it does not write anywhere by
default, so pass it explicitly every time, the same way you'd never let a launcher/submitter log fall back
to `tmp/` for a small offline experiment (Step 5).

**Monitoring a restart: follow `arm-hpc-monitoring`, do not invent a shape.** Its structure is
**nohup the watcher script, then arm `Monitor` on the watcher's log** — two layers on purpose. The
nohup'd script survives the session; the `Monitor` tail process does not, and is re-armed at session
start (that skill's anti-pattern #5). Three requirements from it that a hand-rolled watcher tends to miss:

- **The event stream must carry a PROGRESS signal, not only state transitions.** A multi-day chain has
  exactly two SLURM transitions, so a transitions-only filter is silent for days and the run is
  effectively unmonitored. Emit on a model-year or milestone cadence (a few hours' worth) alongside the
  error and terminal signatures.
- **"Terminal" must be an allow-list**, and liveness cross-checked on the filesystem — see the header of
  `phase_results/…_trans_timeout_restart/watch_trans_timeout.sh` for why (a `slurmdbd` outage made
  `sacct` fail, three live jobs read as UNKNOWN, and a not-in-RUNNING test declared them all finished).
- **The job-name filter must match the ACTUAL SLURM job name, not the case name.** CIME prefixes every
  job `run.<case_name>`; a bare-name `squeue -n`/`sacct --name` filter silently matches nothing
  (`arm-hpc-monitoring` anti-pattern #12) — verify with a real `squeue -o "%j"` sample first.

Never stop a stray watcher with a loose `pkill -f <pattern>` — it matches your own shell's command line
and kills the session; stop it by verified PID, or let it self-exit.

> **Recorded because it is the more useful lesson:** the single-layer "poll loop *is* the `Monitor`
> command" shape was written into this step on 2026-08-08 after a hand-rolled watcher was redesigned
> mid-session. It contradicted `arm-hpc-monitoring` #5 and silently traded away session-survival. The
> failure was not the shape, it was **improvising a procedure a skill already owned, then codifying the
> improvisation here**. When two skills touch the same operation, the one that owns it is authoritative;
> extend it rather than restating it differently ([[feedback_skill_is_authoritative_over_memory]]).

## Step 10 — V0 reproducibility check FIRST (hard gate)

> **Concrete tool (use this):** `tools/extract_and_plot_selected_cases.py` implements Steps 10–11 as three subcommands — `extract`, `v0check`, `plot`. It is generic (base case + variant suffixes + dirs are all CLI args; nothing experiment-specific is hardcoded) and **reuses the production extractor's `process_case()` without touching its `_exp`-gated Phase-5/6 pre-flight** (see `<auto-memory>/feedback_do_not_change_extractor_case_naming.md` — do NOT "generalize" `tools/extract_monthly_variables_FATES.py` to accept non-`_exp` suffixes). First end-to-end exercise: the clumping experiment, the originating dev/ana log + the originating dev/ana log.
> Its `plot` overlay follows the **A2MC ensemble figure template** (`plotting` skill): same obs-diamond /
> ±20%-band / `g C m$^{-2}$` convention as the whole-ensemble plot, but solid opaque colored variant lines
> (not a purple cloud) with the control black-dashed via `--baseline`.
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
>     --baseline <ctrl_suffix> \   # optional: dash-highlight the control (black dashed, on top)
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

The KB injection plan should be a companion dev_log that documents WHAT to add to `memory/gained_knowledge/discoveries.json` and the matching site-specific `gained_knowledge/` files. Example pattern: the originating dev/ana log is the companion to `20260519e`.

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

1. **Don't invent case numbers above the Morris range.** This was the H1 bug — case numbers 5001-5018 share the Morris case-name pattern, contaminating the auto-monitor and Morris screening. Use `--case-suffix` instead. See the originating dev/ana log.

2. **Don't share extraction directories with the parent Morris ensemble.** The dedicated `$A2MC_EXTRACTED_DATA` override per Step 5 is non-negotiable. Skipping this requires post-hoc cleanup (move/delete contaminating NCs) which is expensive and error-prone.

3. **Don't skip Step 1 (search dev_logs).** This is the #1 lesson from the H1 misadventure. A prior plan for the SAME experiment likely exists.

4. **Don't skip falsifiability or pre-committed thresholds.** Both are easy to lose in a hurry. Without falsifiability, your "confirmation" might be coincidence. Without pre-commitment, the "interpretation" can drift to match whatever the experiment produces.

5. **Don't bypass the V0 reproducibility check.** Without V0, you cannot distinguish a real mechanism signal from infrastructure drift.

6. **Don't run >10 variants in one experiment.** If you have more than ~10 candidate variants, the design probably hasn't been narrowed down enough — consider splitting into sequential experiments, with each informing the next.

7. **Don't skip Step 7 (parameter file verification) before submitting.** The cost of finding a generator bug after 24+ hours of HPC compute is much higher than the cost of catching it in a 30-second ncdump check. A common failure mode: 0-based vs 1-based PFT index confusion silently modifies the wrong PFT.

8. **Don't pass a RELATIVE `--param-file` to `create_case.sh`.** The path is written *verbatim* into the case namelist and later read from the case *run* dir (a different CWD), so a relative path silently fails to resolve and the run dies partway. Always resolve to absolute first (`D="$(cd <topic_dir> && pwd)"`, pass `"$D/…"`) and verify with `grep '^PARAM_FILE=' <generated>.sh` → an absolute path that `[ -f ]` exists.

9. **Don't treat a TIMEOUT as a failure to diagnose, or restart it with CIME `CONTINUE_RUN`.** A TIMEOUT is a continuation: A2MC restarts branch-style via `RUN_STARTDATE` + `finidat` + `STOP_N` (Step 9d). Don't `./case.setup --reset` (it clears `BUILD_COMPLETE`), don't build `finidat` from the round env vars when the cases live in an older round's tree, and don't put the restart script or its log in `tmp/` — they belong in `phase_results/{stem}/`.

10. **Don't `module load python` before `submit_phase0.py` / `create_case.sh`.** It prepends NERSC's default Python (3.13) over `a2mc_config.sh`'s `~/a2mc_env` (CIME-compatible 3.11), and CIME's `create_newcase` then dies at case-creation for *every* case (`TypeError: expected an Element, not _Element`). Source `a2mc_config.sh` and run `python3 …` directly; assert `python3 --version` is 3.11 right before launch. **The dry-run does NOT catch this** — `create_newcase` runs only on the real `--submit`, so a clean `--write-script`/`--dry-run` can still fail every case. `module load python` is fine only for standalone analysis scripts (e.g. the Step 7c ncdump check) that never call CIME. Full detail: `<auto-memory>/feedback_no_module_load_python_for_cime`.

## Cross-references

### In-repo authoritative docs (READ FIRST when in doubt)
- `docs/a2mc_reference/tools_reference.md` — A2MC tools API (cost functions, phase logger, workflow status, two-level config, `tools/config.py` Python API, case-name pattern, diagnose_ensemble_status outputs, phase year ranges, AI provider switching)
- `docs/a2mc_reference/fates_data_reference.md` — FATES parameter file dimensions, PFT names with array-index mapping (PFT7=idx6, PFT9=idx8, PFT10=idx9), official parameter naming convention (no PFT suffix), output dimension levels, SZPF index formula `(pft-1)×13`, unit conventions, ELM no-leap-year calendar
- `docs/a2mc_reference/rag_reference.md` — RAG/GraphRAG for FATES knowledge queries during diagnosis/design

### Auto-memories

*(Repointed 2026-08-05: this block was carried over from another branch and cited three memories that do
not exist here. Replaced with this branch's own.)*

- **Paths: source the configs and read them off the environment — do not look them up in a memory.**
  `source a2mc_config.sh` then the ACTIVE round's site config, and every path you need is exported:
  case dir, run dir, `$A2MC_ENSEMBLE_OUTPUT`, `$A2MC_PARAM_DIR`, `$A2MC_CASE_SCRIPTS`. That is the source
  of truth ([[feedback_source_config_order_and_round_selection]]); `tools/config.py` is the Python reader.
  A memory can go stale against a config change, so it should never be the authority for a path.
  For the *machine-level* facts the config assumes: clone + sync topology
  [[reference_local_repos_and_sync]], scratch-vs-home [[reference_main_tmp_cfs_scratch_path]].
- **Case naming:** the `--case-suffix` convention in this skill's own experiment-design section.
- **Config sourcing:** [[feedback_source_config_order_and_round_selection]] — machine config first, then
  the ACTIVE round's site config named by `calibration_rounds.yaml`.

### Worked examples / prior plans
- Canonical worked example: the originating dev/ana log
- Reconciliation log when this skill was distilled: the originating dev/ana log

### Companion skills
- `.claude/skills/arm-hpc-monitoring/SKILL.md` — arms HPC monitoring during the experiment
- `.claude/skills/restart-failed-jobs/SKILL.md` — handles failures during the experiment

### Phase 5 source code
- `phases/phase5_testing/{design_experiments,submit_experiments}.py` — orchestrator-driven path
- `tools/create_case.sh` (--case-suffix flag is the load-bearing convention element)
- `tools/submit_experiment.sh` — single-experiment harness
- `tools/modify_fates_parameters.py` — `create_modified_parameter_file()` + `verify_modifications()`
- `tools/validate_submission_plan.py` — pre-flight validator (auto-invoked by submit_phase0.py, must be invoked manually for experiments)

## Changelog

- 2026-08-16: **Step 9d's "What it does NOT do" flipped — `restart_experiment_case.py` now
  cascade-repairs the downstream chain automatically**, replacing the old advisory-only
  reminder. Restarting `RGnone_RGSP` left the already-queued `RGnone_TRANS` chained to the dead
  old RGSP job for ~30 hours, undetected by any monitor, until a routine status check surfaced
  it — the tool's own docstring already documented the manual fix but nothing acted on it. The
  tool now walks the entire downstream chain after `--execute` (not just one hop), cancelling
  and resubmitting every stale-`PENDING` downstream job with the corrected dependency, and never
  touches an already-`RUNNING` one. Also exposed standalone (`--rechain-downstream --new-jobid`)
  for a chain repair needed outside this tool's own `--execute` path — e.g. after a manual,
  un-tooled resubmit, which the single-hop reminder this replaces could not have covered either.
  Signal: PI correction — after the single-hop advisory reminder shipped, the PI pointed out the
  real fix needed to redo the whole dependency chain automatically, not just print a note about
  one hop of it. Companion: `memory/dev_logs/20260816b_Restart_Tool_Automates_Downstream_Chain_Repair.md`.
- 2026-08-14 (b): **`restart_experiment_case.py` gained `--output-script`** and Step 9d's usage example now
  shows it. The tool as first built only printed the generated plan to stdout and, with `--execute`, ran it
  directly — nothing was ever persisted, silently contradicting this skill's own artifact-placement rule
  ("the restart script... belong in `phase_results/{stem}/`", stated a few paragraphs below Step 9d's usage
  block since 2026-08-08). `--output-script <path>` now writes the plan as a durable, executable script
  (`chmod 755`, proper shebang); `--execute` without it prints a stderr warning rather than silently leaving
  no record. The artifact-placement paragraph now names the flag explicitly rather than describing a
  destination with no documented way to reach it. Signal: PI correction — "using repo-relative `tmp/` is not
  correct, restarting scripts should be also written into `use_cases/ELM-FATES_Kougarok/memory/phase_results/{stem}/`"
  — the tool itself was the gap, not the skill text (which already said the right thing); fixed the tool and
  made the usage example demonstrate it instead of leaving the reader to infer it from a separate paragraph.
- 2026-08-14 (a): **Step 9d now leads with `tools/restart_experiment_case.py`**, the new standalone shortcut
  (mirrors `diagnose_ensemble_status.py::generate_phase_submit_command()`, same fixes applied to both) —
  no more hand-applying the recipe per case for the common path. Fixed a wording gap the PI caught directly:
  the step previously read as if RGSP restarts needed different handling than ADSP; in fact the same
  function/gates cover ADSP, RGSP, and TRANS restarting *themselves* identically — the real "does NOT do"
  boundary is same-phase restart (tool territory) vs. chain-resubmitting an untouched *downstream* phase
  after its upstream was restarted (no tool needed, just `case.submit --dependency=afterok:...`), which had
  been conflated with the RGSP case. Also documents two edge-case rules the PI specified and that the tool
  now implements: (1) `nyears_ad_carbon_only` is dropped only if the restart year has moved past the
  carbon-only window, not unconditionally on every ADSP restart — a restart still inside the window (e.g.
  snapped-back year 21 under a 30-year window) must keep it; (2) a restart with no progress beyond the first
  forcing cycle (aligned_year == start) is a bare resubmit with no namelist edits at all, not degenerate
  "restart from year 1" namelist surgery. Added the `REST_N=10` (ADSP/RGSP) vs `REST_N=1` (TRANS) rationale
  for why cycle-snap-back is ADSP/RGSP-only, per the PI's explanation. Trap #3 now points at the fixed tools
  instead of a manual "assert the last line" check. Signal: PI-driven — a live restart of `ADRGnone` ADSP
  surfaced the request for a shortcut tool, then two direct corrections
  ("why RGSP restrating can't follow this tool?"; "if the ADSP simulation has not gone beyond 40 years... we
  keep nyears_ad_carbon_only, right? and if... not gone beyond 20 years, then we should just resubmit it").
  Companion tool + fix: `tools/restart_experiment_case.py` (new) and
  `tools/diagnose_ensemble_status.py::generate_phase_submit_command()` (both fixes ported into the
  authoritative generator too, so the two stay consistent).
- 2026-08-12 (b): Added a third bullet to Step 9d's "requirements a hand-rolled watcher tends to miss"
  list: the `squeue -n`/`sacct --name` filter must match the ACTUAL SLURM job name (CIME prefixes every
  job `run.<case_name>`), not the bare case name — cross-referencing the new `arm-hpc-monitoring`
  anti-pattern #12. Signal: this same session's `watch_suplphos_dose_experiment.sh` (and the older
  `watch_p169v6rffix_chain.sh`) both filtered on the bare case name and both silently logged
  `NOT_IN_QUEUE` for jobs that were actually running. Full incident + the primary fix live in
  `arm-hpc-monitoring`'s changelog (2026-08-12 (b)) — this is the reciprocal cross-reference, per
  "when two skills touch one operation, the owner is authoritative."
- 2026-08-12 (a): **Reversed the Step 5/9c case-scripts location — `phase_results/{stem}/`, not `$A2MC_SCRIPTS_DIR` scratch.** The 2026-07-10 entry below sent a small experiment's launcher script + submitter running log to `$A2MC_SCRIPTS_DIR/<ExpName>_<date>/` (scratch, not git-tracked). Two worked examples never followed that: `20260715c_phase5_testing_r01_c01_p2939uni_efficacy/run_En2939_uni.sh` (+ its submit log) and a `run_En2939_p169v6rffix.sh` reconstructed the same way for the rootfinesfrag-fix experiment both went straight into `phase_results/{stem}/` instead. The skill also already contradicted itself: the 2026-08-08 entry below sends a *restart* script + its log to `phase_results/{stem}/` explicitly ("not repo `tmp/`, which is the ensemble-scale convention") while Step 5 still sent the *original* launch script for the same experiment to scratch — no coherent reason the restart continuation is more durable than the launch it continues. Step 5's table, its env-var block (`A2MC_CASE_SCRIPTS` export dropped — that env var is real ensemble-scale infrastructure `submit_phase0.py`/`validate_submission_plan.py`/`diagnose_ensemble_status.py` depend on, and a small experiment's hand-authored script(s) don't belong routed through it), Step 6's manifest-TSV location, and Step 9c's monitor-arming path all now point at `use_cases/{site}/memory/phase_results/{stem}/`. Companion fix in `arm-hpc-monitoring`'s Step 1 log-location note (same day). Signal: PI question ("shouldn't the skill say job scripts go in phase_results/{stem}/, right?") after noticing I'd placed a reconstructed launcher script there without checking the skill first.
- 2026-08-09: **Corrected the Step 9d monitoring guidance, which contradicted `arm-hpc-monitoring`.** The version added 2026-08-08 recommended making the poll loop itself the `Monitor` command, over the two-layer nohup-script + tail-the-log arrangement. That is the opposite of `arm-hpc-monitoring` anti-pattern #5, and it silently traded away session-survival: the single-layer watcher dies with the session. Step 9d now defers to that skill and adds the two requirements a hand-rolled watcher misses (a PROGRESS signal, since a multi-day chain has only two SLURM transitions and a transitions-only filter is silent for days; and an allow-list definition of terminal with a filesystem liveness cross-check). Signal: PI asked why the monitor was built differently when the skill existed. Root cause was not the shape but the process -- `arm-hpc-monitoring` was never invoked when the jobs were launched (it had correctly been skipped at session start, when nothing was running), fragments of it read for another purpose were mistaken for knowing it, and the resulting improvisation was then written here as a lesson. When two skills touch one operation, the owner is authoritative.
- 2026-08-08: Added **Step 9d — resume a chain that ran out of wall clock** + anti-pattern #9. A TIMEOUT is neither failure mode `restart-failed-jobs` triages: the model ran fine and the clock ran out, so it is a continuation. That skill also cannot be *driven* on suffixed experiment cases (`make_case_name()` formats `{N}`/`{PHASE}` only), but its recipe transfers: A2MC restarts branch-style via `RUN_STARTDATE` + `finidat` + `STOP_N` (authoritative in `diagnose_ensemble_status.py::generate_phase_submit_command(restart_type='continue')`), NOT CIME `CONTINUE_RUN`. Records four traps that cost time restarting `eca_c4`/`p169v6`/`h1suplN`: `case.setup --reset` clears `BUILD_COMPLETE` and blocks every submit (fix by restoring the flag, not rebuilding, since these cases share one `e3sm.exe`); `finidat` must come from the case's own CASEROOT/rpointer, not the round env vars, which point at a different round's tree; `sed -i '$ d'` deletes blind so assert the last line is the old `finidat`; and check the wall-clock arithmetic against the 48h QOS ceiling up front (`RESUBMIT=1` is not the fix — it runs `STOP_N` MORE years and overshoots the forcing data). Also fixes artifact placement (restart script + watcher + logs go in `phase_results/{stem}/`, not repo `tmp/`, which is the ensemble-scale convention) and monitoring shape (make the poll loop itself the `Monitor` command; never stop a watcher with a loose `pkill -f`, which matches and kills your own shell). Signal: PI corrections this session on all three points.
- 2026-08-05 (b): **Step 9a's path block** — caught by the `memory-checkup` run the same day, which found the
  2026-08-05 (a) fix below had repointed the Auto-memories block at the foot of the file but **missed this body
  citation**: it still sourced its path claim to `reference_a2mc_path_topology`, a memory that does not exist
  here. The claim itself is correct, so it is now sourced to what actually establishes it — source the configs
  and read `${A2MC_E3SM_ROOT}` / `${A2MC_ENSEMBLE_OUTPUT}` off the environment, with the case-vs-run layout
  attributed to the CIME structural fact at `tools/create_case.sh:651`. Also de-hardcoded the param-file
  extension in the verification table: `.nc` is api-31-era, while this branch is api-43/JSON — it now defers to
  `${A2MC_PARAM_PATTERN}`. **Lesson: when repointing citations, grep the whole file, not just the block you
  came for.**
- 2026-08-05 (a): **Repointed the Auto-memories block** — it was carried over from another branch and cited three
  memories that do not exist here, all dead. The Paths bullet now says the operative thing: **source the
  machine + active-round site configs and read the paths off the environment**; a memory can go stale against
  a config change, so it is never the authority for a path. Machine-level facts the config assumes still get
  memories. (A first pass also carried an inherited justification for not porting the frozen demo branch's
  originals — dropped, per the PI: the demo is frozen, so its memories are frozen with it and are not a live
  consideration here.)
- 2026-07-15: Step 10 plot example adds the `extract_and_plot_selected_cases.py --baseline` flag (dash-highlight the control; ported from demo `db488cd`). Step 6 names `tools/estab_exp_make_param_files.py` as a worked example of the generator pattern (ported from demo `84af889`; the tool was copied from demo and flagged as an api-31 demo example — reuse the pattern, not its PFT ids/values).
- 2026-07-10: Documented the **log-location convention** (Step 5 dirs table + Step 6 manifest note + Step 9c) — an experiment's launcher/submitter *running* log goes in the **job-scripts folder** (`$A2MC_SCRIPTS_DIR/<ExpName>_<date>/`) with the case scripts, and every `tmp/` path in this skill (and `arm-hpc-monitoring`) means the **repo-relative** `<repo>/tmp/` (e.g. `~/A2MC-main/tmp/`), not a system/random `/tmp`. Signal: PI correction this session — I wrote the launcher log to `~` (wrong); the location was previously unspecified so it drifted.
- 2026-07-10: **Scoped** the job-scripts-folder rule to *small offline experiments* — an **ensemble-scale** run keeps its auto-monitor/submitter logs in the repo-relative `tmp/` per `arm-hpc-monitoring` (which now carries the reciprocal note). Signal: PI clarification — `arm-hpc-monitoring` logs can go to `tmp/`, especially for ensemble simulations; don't over-apply the job-scripts convention to ensembles.
- 2026-07-09: Added anti-pattern #9 — **no `module load python` before a CIME step** (clobbers `a2mc_env`'s
  CIME-safe Python 3.11 with NERSC 3.13 → `create_newcase` dies for every case; the dry-run doesn't catch
  it). Concise pointer to `feedback_no_module_load_python_for_cime`. Ported the generic nugget from demo
  `a44717d` (v3.13); **deliberately did NOT port** demo's Step 5 per-phase-build rework, Step 9
  `--output-root` removal, or the anti-pattern #6 large-cohort carve-out — those ride on demo's divergent
  "follow-the-online-agent" path model (main keeps dedicated output/extract dirs per anti-pattern #2) and/or
  are Kougarok massbalance-recovery-specific.
- 2026-07-06: Added anti-pattern #8 — the `--param-file` **absolute-path footgun** (`create_case.sh` writes the path verbatim; a relative path silently fails from the run dir). Ported the generic HPC fix from demo, scrubbed of the Kougarok Fork-B worked example. (Build-reuse + monitoring are already covered by Step 5 / Step 9 on main.)
- 2026-06-17: `## Changelog` convention adopted (see .claude/skills/README.md). Earlier history: git log + memory/dev_logs/.
