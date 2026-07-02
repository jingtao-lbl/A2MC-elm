# CLAUDE.md - Context for Claude AI Assistants

**Project:** A2MC (Agentic Adaptive Multi-target Calibration)
**Purpose:** Autonomous + interactive multi-target calibration of ELM-FATES using Claude API + HPC + Adaptive Memory (two agent modes — see root `AGENTS.md` and README §"Two Ways to Run A2MC")
**Status:** Implementation Complete (v3.00)
**Last Updated:** July 2, 2026
---


---

## What is A2MC?

A2MC is an AI-driven calibration framework for ELM-FATES (E3SM Land Model - Functionally Assembled Terrestrial Ecosystem Simulator). It combines:

1. **Morris/Sobol sensitivity analysis** - Parameter space exploration
2. **Claude API reasoning** - Intelligent diagnosis and hypothesis generation
3. **HPC execution** - Runs on NERSC Perlmutter supercomputer
4. **Adaptive Memory** - Learns from experiments, avoids repeating failures
5. **Multi-objective optimization** - Calibrates multiple PFTs simultaneously

---

---

## Calibration Rules - for calibrating ELM-FATES with A2MC

Rules that govern **calibration work**. They apply to **both agent modes** — the autonomous `orchestrator.py --run` loop and the interactive coding agent. The harness-neutral statement of the same discipline is `AGENTS.md` §"Core operating rules"; keep the two in sync.

1. **NEVER ASSUME — ALWAYS VERIFY** - Do NOT make assumptions about project structure, parameters, or FATES behavior. Read the source of truth (configs, scripts, the FATES knowledge base) before stating what is or isn't included/allowed.
2. **VERIFY FATES BEHAVIOR FIRST** - Never infer a parameter, flag, or mechanism's effect from its name. Query the RAG/GraphRAG knowledge base and `docs/fates-knowledge-base/` before writing comments, docs, or code that assert how FATES works.
3. **READ THE PHASE CONTEXT DOC** - When working in a phase folder, read its `CLAUDE.md` (overview in `phases/CLAUDE.md`) before editing or running there.
4. **KEEP CODE AND DOCS GENERIC** - A2MC is meant to be reused across sites. Code must be site-agnostic; site-specific content belongs in `use_cases/{site}/`.
5. **NO HARDCODED PATHS** - Machine settings live in `a2mc_config.sh`, site settings in `use_cases/{site}/config/{site}_config.sh`; access them in Python via `tools/config.py`. Source both before running anything.
6. **CHECK EXISTING STRUCTURE** - Verify actual folder/file names by reading existing code or listing directories before writing paths. Never assume folder names (e.g., `data` vs `gained_knowledge`, `logs` vs `phase_results`).

---

## 7-Phase Workflow

```
   ┌─────────┐   ┌─────────────┐   ┌───────────┐   ┌───────────┐
┌─►│ Phase 0 │──►│   Phase 1   │──►│  Phase 2  │──►│  Phase 3  │◄─┐
│  │ DESIGN  │   │ EXPLORATION │   │ SCREENING │   │ DIAGNOSIS │  │
│  └─────────┘   └─────────────┘   └───────────┘   └─────▲─────┘  │
│                                            skip-test   │        │
│                                            (innermost: │        │
│                                             Phase 3↔4) │        │
│  ┌─────────┐   ┌─────────────┐   ┌───────────┐   ┌─────▼─────┐  │   
│  │ Phase 7 │◄Y─│   Phase 6   │◄──│  Phase 5  │◄──│  Phase 4  │  │
│  │CONVERGED│   │ REFINEMENT  │   │  TESTING  │   │HYPOTHESIS │  │
│  └─────────┘   └──┬───────┬──┘   └───────────┘   └───────────┘  │
│                   │       └────── rethink (middle: Phase 6↔3) ──┘
└───────(N)─────────┘
   Redesign (outermost: Phase 6→0): expand parameter space when experiment cycles reach max without meeting all targets

Phase 6, after evaluating experiment results:
   all targets met                        → Phase 7 CONVERGED (terminal)        [Y]
   not met, experiment cycles < max       → Phase 3 (rethink, middle loop)
   not met, experiment cycles reached max → Phase 0 (redesign, outermost loop)  [N]
Inner loop: Phase 3 ↔ Phase 4 (skip-test with existing data, no HPC)
```

| Phase | Name | Purpose | AI in online mode|
|-------|------|---------|-----|
| 0 | DESIGN | Morris/Sobol sampling, create cases, submit to HPC | Yes |
| 1 | EXPLORATION | Extract Y matrix, run sensitivity analysis | Yes |
| 2 | SCREENING | Rank ensemble by validation targets | Yes |
| 3 | DIAGNOSIS | Root cause analysis, edge case detection | Yes |
| 4 | HYPOTHESIS | Generate testable hypotheses OR test with existing data | Yes |
| 5 | TESTING | Run designed experiments on HPC | No |
| 6 | REFINEMENT | Evaluate results, extract lessons, check equifinality | Yes |
| 7 | CONVERGED | Final optimal configuration | No |

**Key design principle:** No idle waiting within any phase. Each phase completes with a deliverable.

**Iteration paths:**
- **Phase 4 ↔ Phase 3:** Skip testing experiments when existing ensemble simulation results can test hypothesis (e.g., P mass balance analysis)
- **Phase 6 ↔ Phase 3:** Rethink/adjust hypothesis and run another experiment cycle when targets are not met **and** experiment cycles are still below the max (middle loop)
- **Phase 6 → Phase 0:** Redesign (expand the parameter space) when experiment cycles **reach the max** without meeting all targets (outermost loop). Phase 7 (CONVERGED) is reserved for true convergence — a terminal state, not on the redesign loop.

**Memory learning (mode-dependent — "online proposes, offline disposes"):** Phase 6 extracts lessons in **both** agent modes, but the two modes have different write authority over curated Adaptive Memory. The **autonomous (online) agent** runs `MemoryManager` in `propose` mode: its extracted discoveries/experiments are staged to `auto_discovered_pending.json` (gitignored run-state) for review — it **cannot** write knowledge directly. Only the **interactive (offline) agent** promotes vetted, human-in-the-loop-curated proposals into the curated Adaptive Memory (`tools/review_pending_knowledge.py` / the `curate-knowledge` skill), and injects human-originated discoveries (`inject-knowledge`). This write gate is what keeps unattended runs from contaminating the knowledge base.

**Diagnostic-tool promotion (Phase 3, same propose/dispose split):** the same "online proposes, offline disposes" pattern governs the diagnosis tool library. When no existing tool can test a hypothesis, the agent writes a custom `test_hypothesis()` script into `phases/phase3_diagnosis/generated/` (staging; auto-discovered for the current run only). A vetted, reusable one is then **promoted by the interactive (offline) agent** into the permanent library with `tools/promote_diagnostic_script.py` (`--list` → `--script <name> --dry-run` → promote), which copies it to `phases/phase3_diagnosis/` and registers it in `DIAGNOSTIC_TOOLS_INVENTORY` so future runs auto-discover it. Human-gated — review before committing. Full contract: `phases/phase3_diagnosis/generated/README.md`.

---

## Three-Level Iteration Structure

A2MC uses a three-level iteration structure:

### Calibration Round (Outermost: Phase 0 → 7; redesign loops Phase 6 → 0)

A full calibration cycle from parameter design through convergence:

- **Round 1:** e.g., 138 parameters, 4170 simulations
- **Round 2:** e.g., 162 parameters, 4890 simulations (expanded parameter space)
- Set via `--calibration-round N` CLI argument
- Incremented when redesigning the parameter space (Phase 6 → Phase 0)

### Middle Experiment-cycle Loop: (Diagnosis/Hypothesis/Testing/Refinement cycles within a round, Phase 3 → 4 → 5 → 6 → 3)

Each diagnosis → hypothesis → testing → refinement cycle within a round from phase 3 to 6 and back to 3.
Run HPC experiments to test hypotheses that can't be validated with existing data:

- **Max cycles:** 10 (configurable via `--max-experiments`)
- **Exit conditions:**
  1. All targets met (CONVERGED)
  2. Experiment cycle limit reached
  3. Max iterations limit reached (backward compatibility)

- **Counter:** `experiment_count`, incremented once per experiment cycle
- Tracks progress within the current calibration round

### Inner Loop: Skip Testing (Phase 3 ↔ 4)

Test hypotheses using existing ensemble data without running new HPC simulations:

- **Max cycles:** 10 (configurable via `--max-skip-testing`)
- **Exit conditions:**
  1. Hypothesis confidence ≥ 0.95 (configurable via `--confidence-threshold`)
  2. Skip testing cycle limit reached
  3. Hypothesis requires new experiments (`test_with_existing=false`)

- **Counter:** `skip_testing_count`, incremented once per skip-testing cycle; resets to 0 when a new experiment cycle begins (Phase 5 entry)
- Tracks progress within the current experiment cycle of the current calibration round

### State Tracking

| Field | Description | When Updated |
|-------|-------------|--------------|
| `calibration_round` | Outermost loop (Phase 0→7) | Set via CLI `--start-round` |
| `experiment_count`  | Middle loop counter | Incremented in Phase 6 when returning to Phase 3 |
| `skip_testing_count` | Inner loop counter | Incremented in Phase 4 skip testing, reset when entering Phase 5 |

### Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│              THREE-LEVEL ITERATION STRUCTURE                                 │
│                                                                              │
│  CALIBRATION ROUND (outermost): Phase 0 → 7 cycle                            │
│  e.g., Round 1 = 138 params, Round 2 = 162 params, Round 3 = ...             │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐      │
│  │  MIDDLE LOOP: Experiment Cycle (max 10 cycles)                     │      │
│  │                                                                    │      │
│  │  ┌──────────────────────────────────────────────────────────┐      │      │
│  │  │  INNER LOOP: Skip Testing (max 10 cycles)                │      │      │
│  │  │                                                          │      │      │
│  │  │  Phase 3 (Diagnosis) ◄───────────────────┐               │      │      │
│  │  │    │                                     │               │      │      │
│  │  │    ▼                                     │               │      │      │
│  │  │  Phase 4 (Hypothesis)                    │               │      │      │
│  │  │    │                                     │               │      │      │
│  │  │    ├── test_with_existing=true ──────────┘               │      │      │
│  │  │    │   skip_testing_count++                              │      │      │
│  │  │    │                                                     │      │      │
│  │  │    │   EXIT: confidence >= 0.95, or                      │      │      │
│  │  │    │         skip_testing_count >= 10, or                │      │      │
│  │  │    │         test_with_existing=false                    │      │      │
│  │  │    ▼                                                     │      │      │
│  │  └──────────────────────────────────────────────────────────┘      │      │
│  │    │                                                               │      │
│  │    ▼                                                               │      │
│  │  Phase 5 (HPC Testing)                                             │      │
│  │    │   skip_testing_count = 0  (RESET)                             │      │
│  │    ▼                                                               │      │
│  │  Phase 6 (Refinement)                                              │      │
│  │    │                                                               │      │
│  │    ├── targets MET ──────────────────────► Phase 7 (CONVERGED)     │      │
│  │    │                                                               │      │
│  │    ├── not met, experiment_count < max ──► Phase 3 (next cycle)    │      │
│  │    │   experiment_count++                                          │      │
│  │    │                                                               │      │
│  │    └── not met, experiment_count = max ──► Phase 0 (redesign)      │      │
│  └────────────────────────────────────────────────────────────────────┘      │
│                                                                              │
│  When Phase 6 → Phase 0 (redesign): calibration_round++                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

### CLI Arguments to run online agent

```bash
# Start from screening phase in calibration round 2 (e.g., 162 params)
python orchestrator.py --run --start-phase 2 --start-round 2

# Three-level iteration control
python orchestrator.py --run \
    --start-round 2 \        # Calibration round (outermost loop)
    --max-skip-testing 5 \       # Limit skip testing to 5 cycles
    --max-experiments 3 \        # Limit to 3 full experiment cycles
    --confidence-threshold 0.90  # Exit skip testing at 90% confidence

# Backward compatible (still works)
python orchestrator.py --run --max-iterations 10
```

---

## Key Files

| File | Purpose |
|------|---------|
| `orchestrator.py` | Main workflow controller, state machine |
| `reasoning/` | Claude API interface package (base, methods, schemas, prompts) |
| `tools/hpc_utils.py` | HPC utilities: HPCConfig, HPCExecutor, ParameterManager |
| `phases/phase1_exploration/extract_sensitivity_outputs.py` | Extract Y matrix from completed simulations |
| `phases/phase1_exploration/morris_sensitivity_analysis.py` | Run Morris sensitivity analysis with SALib |
| `tools/config.py` | Configuration management |
| `tools/cost_functions.py` | Generic error metrics library |
| `tools/evaluate_case.py` | Shared case evaluation against validation targets (screening + experiments) |
| `tools/optimize_function.py` | Ensemble ranking against targets |
| `tools/create_case.sh` | Create CIME case for ensemble member |
| `tools/submit_ensemble.sh` | Submit ensemble jobs to HPC |
| `tools/extract_monthly_variables_FATES.py` | Production TRANS/phase extractor (Phase 1/5/6). Case-name resolution is `_exp`-gated to the Phase 5/6 convention — **do not "generalize" it** (see `tools/extract_and_plot_selected_cases.py` for non-`_exp` experiment suffixes) |
| `tools/extract_and_plot_selected_cases.py` | Generic driver for a SMALL selected-case offline experiment: `extract` / `v0check` / `plot` subcommands. Reuses the production extractor's `process_case()` without touching its `_exp` pre-flight. Backs the offline-testing-workflow skill |
| `tools/extract_ADSP_RGSP_slim.py` | Fast 2-variable (leaf/fineroot) ADSP+RGSP spinup extractor for the combined-axis ensemble plot |
| `tools/plot_ensemble_cases.py` | Whole-ensemble biomass-vs-targets plot (`R{N}_{combined,TRANS}_{count}cases_ensemble.png`): purple cloud + best-NRMSE (red) + most-targets (blue). Generic CLI (`--combined`, `--pft-ids`, `--round-label`, `--output-dir`). Generalized from `use_cases/Kougarok/analysis/plot_all_extracted.py` (now a shim → this); driven by `regen_ensemble_milestone_plot.sh` / `ensemble_auto_monitor.sh` |
| `tools/ensemble_auto_monitor.sh` | Config-driven whole-ensemble monitor (queue polling + extraction kick + milestone-plot trigger). Generic; R5's `r5_auto_monitor.sh` is now a thin wrapper |
| `tools/regen_ensemble_milestone_plot.sh` | Config-driven milestone ensemble-plot regen. Generic; R5's `regen_milestone_plot.sh` is now a thin wrapper |
| `tools/diagnose_ensemble_status.py` | Check completion status of ensemble; auto-invokes validator after writing `restart_incomplete_<TS>.sh` |
| `tools/validate_restart_script.py` | Validates auto-generated restart scripts (filesystem state + STOP_N math + finidat consistency + chain wiring) |
| `tools/phase_logger.py` | Standardized Markdown logging to use_cases/{site}/memory/logs/ |
| `tools/workflow_status.py` | Master workflow status tracker |
| `tools/extract_knowledge.py` | AI-powered knowledge extraction from logs |
| `tools/session_report.py` | Collect session artifacts and generate AI-powered session report |
| `tools/reports/generate_presentation.py` | Full pipeline: session logs → AI slides → AI narration → PDF → video |
| `tools/reports/generate_video.py` | PDF + narration JSON → narrated MP4 video |
| `memory/manager.py` | MemoryManager class for persistent knowledge. `write_mode` gate (v2.90): online agent runs `propose` (stages to `auto_discovered_pending.json`); only the interactive agent writes curated Tier-3 |
| `memory/store.py` | JSON persistence utilities |
| `tools/review_pending_knowledge.py` | Interactive (human-in-the-loop) curation of staged `auto_discovered` proposals: `list`/`promote`/`discard`. Promotes vetted entries from `auto_discovered_pending.json` into the curated KB (v2.90 write gate) |
| `tools/promote_diagnostic_script.py` | Promote a vetted AI-generated diagnostic script from `phases/phase3_diagnosis/generated/` into the permanent tool library (`--list`/`--script <name>`/`--dry-run`): copies to `phases/phase3_diagnosis/` + registers it in `DIAGNOSTIC_TOOLS_INVENTORY`. Human-gated |

---

## A2MC Skills (`.claude/skills/`)

A2MC ships its own project-scoped skills, **tracked in this repo** under `.claude/skills/` (versioned). They are A2MC domain knowledge — HPC-run procedures specific to this framework — so they live with the code, not in the user-level `~/.claude/skills/` (which holds cross-project skills like `literature-review`). When invoked via the Skill tool, project skills override user skills of the same name.

These skills are the **interactive (offline) agent's capability catalog**. The interactive agent — a coding-agent harness operating in the repo, the co-equal counterpart to the autonomous `orchestrator.py --run` mode — runs under the public-safe, harness-neutral operating contract in root `AGENTS.md`, with the catalog indexed at `docs/a2mc_reference/skills_catalog.md`. 

| Skill | When to use |
|-------|-------------|
| `offline-testing-workflow` | Design + launch + analyze an offline HPC experiment (parameter sweep on a Morris base case): N variants, V0 reproducibility gate, decision tree → KB injection. Step 10–11 are backed by `tools/extract_and_plot_selected_cases.py`. Invoke BEFORE writing any "test the X hypothesis" plan |
| `arm-hpc-monitoring` | Set up real-time monitoring of an active ensemble/experiment at session start (CLAUDE.md Rule #6). Pairs with `tools/ensemble_auto_monitor.sh` |
| `restart-failed-jobs` | Restart SLURM jobs that failed mid-run or at end-of-run; distinguishes infrastructure (restart-eligible) from model failures (not, without a fix) |
| `compare-calibration-rounds` | Cross-round comparison (R1…RN): top-N biomass-vs-targets overlay, per-target Morris μ* overlay, P-pool/cross-regime. Codifies the multiround bundle + footguns (screening `--max-case-num` contamination guard, μ* ranking, param-set mismatch, partial-ensemble caveat). Use the **cap** for cross-round screening |
| `summarize-calibration-round` | Single-round summary: combined+TRANS ensemble graphs + evaluation (best case, targets met) + Morris μ* sensitivity → markdown/PDF report. Per-round graphs stay UNCAPPED (own reruns OK); screening evaluation caps foreign experiment cases |
| `calibration-log` | Log calibration/analysis work for a site under `use_cases/{site}/memory/logs/` — a **phase log** (via `PhaseLogger`, same format as the autonomous agent, so both modes synthesize together) or a free-form **session log** (`YYYYMMDDx_Topic.md`). Invoke on "log this phase / diagnosis / experiment", "log this calibration session", "record what I explored" |
| `curate-knowledge` | Human-in-the-loop review + promotion of staged Tier-3 proposals (`auto_discovered_pending.json` → curated KB). The other half of the v2.90 write gate. Invoke on "review/promote pending knowledge", or at session start when proposals exist |
| `onboard-session` | Cold-start runbook: re-read CLAUDE.md, read latest handoff, check live HPC processes + run state, delegate to arm-hpc-monitoring / curate-knowledge. Pairs with the G2 SessionStart hook. Invoke at session start / after compaction or "catch up / where did we leave off" |
| `diagnose-forensics` | Investigate an ensemble anomaly/outlier/failure-cluster: artifact triage (contamination, infra-timing, mislabeled index, NaN) FIRST, then root-cause via phase3 tools. Invoke on "is this real or contamination", "why is case X an outlier", "investigate this anomaly" |
| `phase0-design` | **Offline phase skill (mirrors online Phase 0):** sample the parameter space, materialize per-case param files, submit + monitor the HPC ensemble. Invoke on "design a new round", "submit the ensemble", "redesign / expand the parameter space" |
| `phase1-exploration` | **Offline phase skill (Phase 1):** extract the Y matrix, run Morris sensitivity, interpret μ*. Invoke on "run the sensitivity analysis", "which parameters matter", "run Phase 1" |
| `phase2-screening` | **Offline phase skill (Phase 2):** rank the ensemble vs targets, best/most-targets cases, bias patterns → route to Phase 3. Invoke on "screen the ensemble", "which case is best", "run Phase 2" |
| `phase3-diagnosis` | **Offline phase skill (Phase 3):** HITL analog of `reasoning.diagnose()` — root-cause the round's failing targets via the phase3 tools + RAG + Memory → ranked root causes, parameter recs, base cases, hypotheses; hand off to Phase 4. Invoke on "diagnose the failing targets", "run Phase 3" |
| `phase4-hypothesis` | **Offline phase skill (Phase 4):** turn a diagnosis into testable hypotheses + skip-test against existing Morris data (3↔4, no HPC), else route to Phase 5. Invoke on "generate a hypothesis", "what should we test next", "can we test with existing data" |
| `phase5-testing` | **Offline phase skill (Phase 5):** thin router to `offline-testing-workflow` for HPC experiment execution. Invoke on "run the experiment", "submit the test cases", "run Phase 5" |
| `phase6-refinement` | **Offline phase skill (Phase 6):** evaluate results, extract lessons, write curated Memory directly + promote staged proposals (offline "disposer"), decide converge / rethink (6→3) / redesign (6→0). Invoke on "evaluate the results", "what did we learn", "converge or iterate" |
| `scientific-analysis` | Manuscript-supporting investigation → figure → ana_log (pose question, pull data, compute stat, cite evidence). Invoke on "investigate whether X", "is X correlated with Y", "make a manuscript figure". (Standardized reports: summarize-/compare-calibration-rounds) |

**Why in-repo, not user-level:** these encode A2MC-specific conventions (case-naming, dedicated experiment dirs, the dont-touch-the-extractor rule, event-string vocabulary) that must travel with the framework and stay version-locked to it on this `api-31-0` branch. The user-level bucket is for skills that aren't tied to any one project.

---

## Project Structure

```
A2MC/
├── README.md              # Full user documentation
├── CLAUDE.md              # This file - AI assistant context
├── a2mc_config.sh         # Machine-level config (auto-activates ~/a2mc_env)
├── orchestrator.py        # Main workflow controller
├── reasoning/             # Claude API interface (package)
│   ├── __init__.py        # Backward-compatible re-exports, method attachment
│   ├── schemas.py         # Diagnosis, Hypothesis, Experiment dataclasses
│   ├── prompts.py         # DIAGNOSTIC_TOOLS_INVENTORY, CUSTOM_SCRIPT_TEMPLATE
│   ├── base.py            # ReasoningModule class core (init, query, RAG)
│   └── methods.py         # 8 phase methods (diagnose, hypothesis, etc.)
│
├── use_cases/             # Site-specific case studies
│   ├── README.md          # Overview and instructions
│   ├── TEMPLATE/          # Template for new sites
│   └── Kougarok/          # Kougarok, Alaska (NGEE-Arctic)
│       ├── README.md      # Site description and discoveries
│       ├── config/
│       │   └── kougarok_config.sh  # ALL site-specific settings
│       ├── parameters/
│       │   ├── FATES_Parameter_List_Full_162_Finalized.txt
│       │   └── salib_problem_162params.txt
│       ├── validation/
│       │   └── validation_targets_leafroot.txt
│       └── memory/        # SITE-SPECIFIC KNOWLEDGE
│           ├── logs/      # Phase execution logs (Markdown)
│           ├── extracted/ # Extracted lessons (YAML)
│           └── gained_knowledge/  # Site-specific knowledge (JSON)
│
├── phases/                # Phase-specific scripts
│   ├── CLAUDE.md          # Phase overview for AI assistants
│   ├── phase0_design/     # Morris sampling, case creation
│   ├── phase1_exploration/# Sensitivity analysis (wired to orchestrator)
│   │   ├── extract_sensitivity_outputs.py
│   │   └── morris_sensitivity_analysis.py
│   ├── phase2_screening/  # Ensemble ranking
│   ├── phase3_diagnosis/  # Root cause analysis
│   ├── phase4_hypothesis/ # Hypothesis generation
│   ├── phase5_testing/    # Run experiments
│   └── phase6_refinement/ # Learn from results
│
├── tools/                 # Shared utilities
│   ├── config.py          # Python config loader (reads a2mc_config.sh)
│   ├── phase_logger.py    # Site-specific Markdown logging
│   ├── workflow_status.py # Master workflow status
│   ├── cost_functions.py  # Error metrics (RE, RMSE, NSE, KGE)
│   ├── optimize_function.py  # Ensemble ranking
│   ├── fates_utils.py     # FATES data utilities
│   ├── hpc_utils.py       # HPCConfig, HPCExecutor, ParameterManager
│   ├── modify_fates_parameters.py
│   ├── diagnose_ensemble_status.py
│   └── extract_knowledge.py  # Knowledge extraction from logs
│
├── memory/                # GENERIC KNOWLEDGE (framework-level)
│   ├── __init__.py        # Package exports
│   ├── store.py           # JSON persistence utilities
│   ├── manager.py         # MemoryManager class
│   ├── gained_knowledge/  # Generic FATES knowledge (JSON)
│   │   ├── discoveries.json
│   │   ├── experiments.json
│   │   ├── parameters.json
│   │   └── failed_approaches.json
│   ├── dev_logs/          # A2MC DEVELOPMENT session logs (Markdown)
│   ├── extracted/         # Generic extracted lessons (YAML)
│   └── workflow_log.json  # Master workflow status
│
├── rag/                   # RAG/GraphRAG System
│   ├── loader.py, vector_store.py, knowledge_graph.py
│   ├── graph_builder.py, hybrid_retriever.py
│   ├── parameter_parser.py, output_parser.py
│   ├── data/
│   │   └── curated_relationships.yaml  # Curated mechanistic relationships
│   └── chroma_db/         # Vector index
│
├── templates/             # AI output & documentation templates
│   ├── reasoning/         # JSON schemas for AI output structure
│   └── logging/           # Markdown templates for reasoning documentation
│
├── docs/                  # Documentation
│   ├── A2MC_System_Master_Plan.md
│   ├── a2mc_reference/    # Detailed reference docs (extracted from CLAUDE.md)
│   │   ├── rag_reference.md         # RAG/GraphRAG system details
│   │   ├── fates_data_reference.md  # FATES dimensions, PFTs, SZPF, units
│   │   └── tools_reference.md       # Tool APIs: logger, status, config, ensemble
│   ├── 00-11_*.md         # Implementation plan docs
│   └── fates-knowledge-base/  # FATES documentation (official + wiki)
│
├── scripts/               # Utility scripts
│   ├── seed_memory_from_yaml.py
│   ├── build_rag_index.py
│   └── curated_knowledge_template.yaml
│
├── plot/                  # Visualization scripts
│   └── visualize_a2mc_horizontal.py
│
└── tools/reports/         # Offline presentation pipeline
    ├── WORKFLOW.md        # Full workflow documentation
    ├── generate_presentation.py  # Automated: logs → slides → narration → PDF → video
    ├── generate_video.py  # PDF + narration JSON → narrated MP4
    └── examples/          # Reference examples
```

**Each phase folder contains:**
- `CLAUDE.md` - Context for AI when working in that phase
- `__init__.py` - Python package marker
- Phase-specific scripts

---

## Adaptive Memory System

Two-tier knowledge architecture with JSON-based persistent memory:

### Generic Knowledge (Framework-level)

Located at `memory/gained_knowledge/` - applies to all sites:

| Store | Purpose |
|-------|---------|
| `discoveries.json` | General FATES mechanistic insights |
| `experiments.json` | Generic experiment patterns |
| `parameters.json` | Parameter knowledge (not site-specific) |
| `failed_approaches.json` | Generic approaches to NOT repeat |

### Site-Specific Knowledge

Located at `use_cases/{site}/memory/gained_knowledge/`:

| Store | Purpose |
|-------|---------|
| `discoveries.json` | Site-specific mechanistic insights (e.g., "Kougarok Allocation Paradox") |
| `experiments.json` | Site experiments with outcomes |
| `failed_approaches.json` | Site-specific approaches to NOT repeat |

### Other Memory Locations

| Location | Purpose |
|----------|---------|
| `memory/workflow_log.json` | Master workflow status (current phase, history) |
| `memory/dev_logs/` | A2MC **development** session logs (Markdown) |
| `memory/extracted/` | Generic extracted lessons (YAML) |
| `use_cases/{site}/memory/logs/{session_id}/` | Phase **execution** logs with AI reasoning (session-scoped, Markdown) |
| `use_cases/{site}/memory/extracted/` | Site-specific extracted lessons (YAML) |

### Knowledge Promotion

HITL interative agent evaluates site-specific discoveries and promotes generalizable ones to generic knowledge:

```
Site Discovery → Evaluation → If generalizable → Copy to memory/gained_knowledge/
```

### Session Logging Convention

**Phase Execution logs** (outputs from A2MC runs, session-scoped):
```
{session_id}/phase0_design/   r{RR}_{session_id}_Title.md
{session_id}/phase3_diagnosis/ r{RR}_c{EE}_iter{II}_{session_id}_Title.md
{session_id}/phase5_testing/   r{RR}_c{EE}_{session_id}_Title.md
```
- Logs are stored under `use_cases/{site}/memory/logs/{session_id}/phase{N}_{name}/`
- `RR` = calibration_round (outermost Phase 0→7 loop, e.g., round 1=138 params, round 2=162 params)
- `EE` = experiment_count (outer loop: full 3→4→5→6 experiment cycles)
- `II` = iteration (Phase 3&4 only: skip_testing_count+1, inner loop counter)
- `session_id` = `YYYYMMDD_HHMMSS` timestamp matching the run log (`a2mc_run_{session_id}.log`)
- Phases 0-2 omit cycle/iteration (always 1, not meaningful)
- Phases 5&6 omit iteration (only one Phase 5 and one Phase 6 per experiment cycle)
- Example: `20260210_143052/phase2_screening/r02_20260210_143052_Ensemble_Screening.md`
- Example: `20260210_143052/phase3_diagnosis/r02_c01_iter03_20260210_143052_PFT10_Analysis.md`
- Fallback (no session_id): logs go directly under `phase{N}_{name}/` without session subdirectory

**Key API:**
```python
from memory import MemoryManager

# Generic knowledge
memory = MemoryManager("memory/gained_knowledge")

# Site-specific knowledge
memory = MemoryManager("use_cases/Kougarok/memory/gained_knowledge")

memory.get_relevant_context(targets, parameters, phase)
memory.add_discovery(name, description, mechanism, affects, confidence)
memory.add_failed_approach(approach, experiment_id, why_failed, severity)
```

---

## Templates

Templates define structure for AI outputs and documentation:

```
templates/
├── reasoning/                 # AI output structure (JSON schemas + Markdown)
│   ├── README.md
│   ├── phase3_diagnosis_template.md    # Root cause analysis output
│   ├── phase4_hypothesis_template.md   # Hypothesis generation output
│   └── phase6_refinement_template.md   # Lesson extraction output
│
└── logging/                   # AI reasoning documentation (Markdown)
    ├── README.md
    ├── diagnostic_log_template.md      # Phase 3 deep dives
    ├── experiment_log_template.md      # Phase 4-5 experiments
    ├── discovery_log_template.md       # Key findings ("Perfect Storm", etc.)
    └── analysis_log_template.md        # General analysis
```

### Reasoning vs Logging Templates

| Aspect | Reasoning Templates | Logging Templates |
|--------|--------------------|--------------------|
| **Purpose** | Define AI output structure | Document reasoning process |
| **Format** | JSON schemas + sections | Markdown narratives |
| **Audience** | Programmatic parsing | Human readers + future AI |
| **Storage** | In-memory / API response | `use_cases/{site}/memory/logs/` |

**Reasoning templates** define WHAT to output (used by `reasoning/methods.py`).
**Logging templates** define HOW to document (for persistent memory).

### Key Patterns from Offline Iteration

Templates incorporate patterns from the first calibration iteration:

| Pattern | Description | Template |
|---------|-------------|----------|
| "Perfect Storm" | Multi-factor cascading failures | `discovery_log_template.md` |
| "Allocation Paradox" | Counter-intuitive allocation behavior | `experiment_log_template.md` |
| "Triple Bottleneck" | Multiple simultaneous constraints | `diagnostic_log_template.md` |
| Mortality Analysis | Hydraulic vs C starvation decomposition | All templates |
| Cross-PFT Comparison | Differential PFT responses | All templates |

### Phenology-Nutrient Uptake Interaction

Key mechanistic insight encoded in templates:
- **Evergreen PFTs (PFT7)**: Persistent but LOW nutrient uptake → vulnerable to chronic stress
- **Deciduous/Graminoid PFTs (PFT9/10)**: HIGH uptake during spring flushing → more resilient

---

## Three-Tier FATES Knowledge System

A2MC uses a three-tier architecture for FATES knowledge:

| Tier | Location | Format | Purpose |
|------|----------|--------|---------|
| **Static Documentation** | `docs/fates-knowledge-base/` | Markdown | Human reference, RAG indexing |
| **RAG/GraphRAG** | `rag/` | ChromaDB + JSON graph | AI semantic search, graph traversal |
| **Adaptive Memory** | `memory/gained_knowledge/` | JSON | AI reasoning context, learned discoveries |

**Key principle:** Same knowledge encoded in all three tiers ensures consistent AI access via multiple retrieval paths.

---

## RAG/GraphRAG System

Hybrid retrieval combining ChromaDB vector search (2,581 chunks) and NetworkX knowledge graph (1,295 nodes, 2,197 edges) for FATES documentation. The `ReasoningModule` automatically queries RAG before each Claude API call, combining RAG context + Adaptive Memory + task data. Current index built 2026-04-22 against `fates-codebase-wiki-e85d997/` and `elm-codebase-wiki-60d9aad/`; see `memory/dev_logs/20260422a_RAG_Rebuild_Against_New_Wikis_And_Curated_YAML_Fix.md`.

**Key concepts:** Two-layer graph (auto-extracted CDL + curated YAML overlay), Python 3.10 required for RAG ops, `HybridRetriever.get_targeted_context()` for efficient per-call context.

**`chroma_db/chroma.sqlite3` read-churn (per-clone gotcha).** The 16 MB vector store is git-tracked (so a clone ships a working index), but ChromaDB writes internal lock bookkeeping (`acquire_write` rows) on every open, so **merely querying the RAG dirties the file** — the embeddings are byte-identical, it is NOT a re-index. Don't commit that churn (binary bloat + cross-clone conflicts). Each clone (including Perlmutter) should run once: `git update-index --skip-worktree rag/chroma_db/chroma.sqlite3`. **Footgun:** before committing a *real* `scripts/build_rag_index.py` rebuild, run `git update-index --no-skip-worktree rag/chroma_db/chroma.sqlite3` first or the new index won't stage. Transient sidecars (`*.sqlite3-{wal,shm,journal}`) are gitignored. Verified 2026-06-30, `memory/dev_logs/20260630a_*`.

**Diagnostic tools:** Any `test_*.py` script with `test_hypothesis()` in `phases/phase3_diagnosis/` is auto-discovered. Claude can also generate custom scripts stored in `phases/phase3_diagnosis/generated/`.

**Promoting a generated script into the permanent tool library.** A vetted, reusable script in `generated/` is promoted into the formal diagnosis inventory with `tools/promote_diagnostic_script.py` (`--list` to see candidates → `--script <name> --dry-run` to preview → `--script <name>` to promote; optional `--tool-name/--category/--description/--use-when`). Promotion **copies** the script to `phases/phase3_diagnosis/`, **registers** it in `DIAGNOSTIC_TOOLS_INVENTORY` (so future runs auto-discover it), and **preserves** the original in `generated/`. This is a human-gated offline step — review before committing. Full contract: `phases/phase3_diagnosis/generated/README.md`.

**Full details:** `docs/a2mc_reference/rag_reference.md` (running-system overview)

**Rebuilding from scratch / new model adoption:** `docs/a2mc_reference/rag_build_roadmap.md` — self-contained reconstruction guide. Read this when bumping the wiki to a new commit-pinned tree (e.g., `fates-codebase-wiki-e85d997/`, `elm-codebase-wiki-60d9aad/`) or when starting an A2MC build for a different model (EcoSim, ReSOM, etc.). Includes Recipe 1 (wiki commit bump — note the loader path-pattern footgun) and Recipe 2 (adding a new model). See `memory/dev_logs/20260410f_RAG_Build_Roadmap_Doc.md` for design rationale.

**Version association (ACTIVE, branch `elm-fates_version_association`):** work in progress to replace the current symlink-based wiki selection with first-class version awareness. A2MC reads the user's `A2MC_MODEL_PATH` (E3SM/ELM-FATES checkout), detects ELM+FATES commits, and selects a matching milestone RAG. Canonical migration: `api-44-1` (FATES `sci.1.92.2_api.44.1.0`, commit `83863e9`) becomes the new default; `api-31-0` (FATES `sci.1.68.2_api.31.0.0+3`, commit `e85d997`) retained on main for Kougarok manuscript reproducibility. Full plan in `docs/18_ELM_FATES_Version_Association_Plan.md`. **When working on this branch, read that plan first.**

---

## Validation Targets & Case Studies

Validation targets and site-specific discoveries are documented in `use_cases/`:

| Use Case | Location | Description |
|----------|----------|-------------|
| `use_cases/Kougarok/` | Alaska, USA | Arctic tundra, 3 PFTs, NGEE-Arctic |
| `use_cases/TEMPLATE/` | - | Template for new sites |

**See `use_cases/{site}/README.md` for:**
- Site-specific validation targets (biomass, fluxes, etc.)
- Key discoveries and mechanistic insights
- Morris ensemble configuration
- Data locations

### Referencing Knowledge from Similar Sites

When calibrating a new site, you can reference knowledge from existing sites with similar characteristics:

| Your Site Type | Reference | Key Transferable Knowledge |
|----------------|-----------|---------------------------|
| Arctic/tundra | `use_cases/Kougarok/` | Allocation Paradox, P-limitation, graminoid-shrub competition |
| CNP-enabled | `use_cases/Kougarok/` | PID controller behavior, ECA competition, vmax calibration |

**What transfers:** Mechanistic insights, diagnostic patterns, failed approaches
**What doesn't transfer:** Exact parameter values (site-specific)

```python
# Reference another site's knowledge
from memory import MemoryManager
ref_memory = MemoryManager("use_cases/Kougarok/memory/gained_knowledge")
discoveries = ref_memory.get_relevant_context(targets=your_targets, phase="diagnosis")
```

---

## Important Patterns

### Parameter Naming Convention (Shorthand)

In A2MC scripts and Morris ensemble files, parameters may use shorthand with PFT suffix:
```
{param_name}_{pft}
Example: alloc_storage_cushion_10 (PFT#10 storage cushion)
```

**Note:** Official FATES parameter names do NOT include PFT suffixes. In Adaptive Memory (`parameters.json`, `discoveries.json`), PFT specificity is stored in separate fields (`parameter_pft`, `affects_pfts`), never embedded in key names. All A2MC naming conventions (targets, parameters, discovery `affects` fields, parameter knowledge keys) are documented in `docs/a2mc_reference/fates_data_reference.md`.

### PFT Indexing
- PFT#7 = Evergreen shrub (index 6 in 0-based arrays)
- PFT#9 = Deciduous shrub (index 8)
- PFT#10 = Arctic graminoid (index 9)

### Morris Ensemble
- 162 parameters, 4890 simulations (30 trajectories × 163)
- Column order matches `use_cases/Kougarok/parameters/FATES_Parameter_List_Full_162_Finalized.txt`
- Dynamic ensemble size calculation in `a2mc_config.sh`

---

## FATES Data Reference

FATES parameter dimensions (12 PFTs, 13 size bins), PFT names, SZPF index mapping, output variable levels (site/PFT/SZPF), data utilities (`tools/fates_utils.py`), unit conventions, and ELM no-leap-year calendar.

**Key quick reference:** SZPF index formula: `start = (pft_id - 1) × 13`, `end = start + 12`. ELM uses 365-day year (no leap). Official FATES parameter names do NOT include PFT suffixes.

**Full details:** `docs/a2mc_reference/fates_data_reference.md`

---

## Tools Reference

Detailed documentation for A2MC tools: cost functions, phase logger, workflow status, knowledge extraction, screening analysis, ensemble management, and AI configuration.

**Phase log filenames:** Stored under `logs/{session_id}/phase{N}_{name}/`. Phase 3&4: `r{RR}_c{EE}_iter{II}_{session_id}_Title.md`; Phase 5&6: `r{RR}_c{EE}_{session_id}_Title.md` — session_id = `YYYYMMDD_HHMMSS` matching the run log.

**Workflow status:** `python tools/workflow_status.py` for quick status check.

**Configuration:** Two-level — `a2mc_config.sh` (machine) + `use_cases/{site}/config/{site}_config.sh` (site). Case name pattern: `A2MC_CASE_NAME_PATTERN` with `{N}` and `{PHASE}` placeholders.

**AI config:** Set `A2MC_AI_PROVIDER` to `anthropic` (default), `openai`, or `cborg` (LBL proxy). Each provider auto-derives its API key env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CBORG_API_KEY`). Override with `A2MC_AI_API_KEY_ENV`. Model defaults to `claude-opus-4-20250514`. CBorg uses the OpenAI SDK and auto-sets base URL to `https://api.cborg.lbl.gov`. See `a2mc_config.sh` for all settings.

**Full details:** `docs/a2mc_reference/tools_reference.md`

---

## Running A2MC (the online agent)

### Command Line Usage

```bash
# IMPORTANT: Always source config files first!
source a2mc_config.sh
source use_cases/Kougarok/config/kougarok_config.sh

# Run workflow (output-dir and state-file auto-detected from config)
python orchestrator.py --run

# Resume from checkpoint (state-file auto-detected)
python orchestrator.py --resume

# Start from specific phase (flexible argument: number, "phaseN", or name)
python orchestrator.py --run --start-phase 1
python orchestrator.py --run --start-phase phase1
python orchestrator.py --run --start-phase exploration

# Start from specific phase in calibration round 2 (e.g., 162 params)
python orchestrator.py --run --start-phase diagnosis --start-round 2

# Run without human review checkpoints
python orchestrator.py --run --no-review

# Skip experiment script generation/review before HPC submission
python orchestrator.py --run --no-script-review

# Run without AI reasoning (rule-based fallback)
python orchestrator.py --run --no-reasoning
```

### Switching AI Providers

Set `A2MC_AI_PROVIDER` in `a2mc_config.sh`. Model and API key env var auto-derive from provider — only the provider needs to change:

```bash
# Option 1: Direct Anthropic (default — no changes needed)
export A2MC_AI_PROVIDER="anthropic"
# → model: claude-opus-4-20250514, key: ANTHROPIC_API_KEY

# Option 2: Direct OpenAI
export A2MC_AI_PROVIDER="openai"
# → model: gpt-4o, key: OPENAI_API_KEY

# Option 3: CBorg (Berkeley Lab proxy)
export A2MC_AI_PROVIDER="cborg"
# → model: anthropic/claude-sonnet, key: CBORG_API_KEY
```

| Provider | SDK | Default Model | Other Models | Base URL | API Key Env |
|----------|-----|---------------|--------------|----------|-------------|
| `anthropic` | `anthropic` | `claude-opus-4-20250514` | `claude-sonnet-4-20250514`, `claude-haiku-3-20240307` | `api.anthropic.com` | `ANTHROPIC_API_KEY` |
| `openai` | `openai` | `gpt-4o` | `gpt-4o-mini`, `o3-mini` | `api.openai.com` | `OPENAI_API_KEY` |
| `cborg` | `openai` | `anthropic/claude-sonnet` | `openai/gpt-4o`, `openai/gpt-4o-mini`, `lbl/llama` | `api.cborg.lbl.gov` | `CBORG_API_KEY` |

### Phase 1 High-Level APIs

```python
from phases.phase1_exploration import run_extraction, run_sensitivity_analysis

# Extract Y matrix from completed simulations
run_extraction(
    case_list="completed_cases.txt",
    output_dir="extracted_data/",
    variables=["FATES_LEAFC", "FATES_FROOTC", "FATES_VEGC_ABOVEGROUND"]
)

# Run Morris sensitivity analysis
run_sensitivity_analysis(
    y_matrix_file="MorrisLeafBiomass.txt",
    problem_file="salib_problem.txt",
    output_dir="sensitivity_results/"
)
```

### Python API

```python
# Note: Source configs first before running Python
# source a2mc_config.sh
# source use_cases/Kougarok/config/kougarok_config.sh

from orchestrator import CalibrationOrchestrator, Config

# Config auto-detects output_dir from A2MC_USE_CASE_DIR
config = Config(
    use_memory=True,
    use_reasoning=True,
    max_iterations=10
)
orch = CalibrationOrchestrator(config)
orch.run()
```

### Iteration Management

Iterations start at **1** (not 0). Environment variables used:

| Variable | Description |
|----------|-------------|
| `A2MC_ITERATION` | Current iteration number (set automatically by orchestrator) |

The orchestrator automatically updates `A2MC_ITERATION` before each phase, allowing PhaseLogger and other tools to pick up the current iteration.

---

## Documentation

### A2MC Framework

**IMPORTANT: Read `docs/A2MC_System_Master_Plan.md` for overall project status and progress tracking.**

- `docs/A2MC_System_Master_Plan.md` - **Master plan and progress tracker** (COMPLETE)
- `docs/00_FATES_Knowledge_Base_Plan.md` - Knowledge base structure
- `docs/01_RAG_Implementation_Guide.md` - RAG implementation guide (historical Phase 1)
- `docs/02_GraphRAG_Implementation_Plan.md` - GraphRAG design (✅ implemented)
- `docs/03_Adaptive_Memory_System_Implementation_Plan.md` - Adaptive Memory design (✅ implemented)
- `docs/a2mc_reference/rag_build_roadmap.md` - **RAG/GraphRAG from-scratch reconstruction guide** (read this for wiki commit bumps or new-model adoption)
- `docs/a2mc_reference/codebase_wiki_generation_roadmap.md` - Adapter-kit Step 1: produce a source-grounded codebase wiki (Workflow A greenfield + Workflow B audit-and-rewrite)
- `docs/a2mc_reference/graphrag_curated_yaml_roadmap.md` - Adapter-kit Step 3: overlay calibration intelligence via the curated YAML (5-phase methodology + AI-assisted bootstrap recipes G1–G4)
- `docs/a2mc_reference/rag_validation_workflow.md` - **Adapter-kit Step 4: validate the chain before shipping** (3-tier validation triangle + step-by-step playbook for `codebase_wiki_validator.py`, `yaml_wiki_validator.py`, `rag_diff.py`)
- `docs/18_ELM_FATES_Version_Association_Plan.md` - **Version-association design and 5-phase implementation plan** (active work on `elm-fates_version_association` branch; migrates canonical RAG to FATES api.44.1)
- `README.md` - Full user documentation and API reference

### FATES Knowledge Base
- `docs/fates-knowledge-base/` - Combined FATES documentation
  - `fates-official-docs/` - Official tech docs (RST, equations, theory)
  - `fates-codebase-wiki/` - Code-level wiki (Markdown, 348 diagrams)
- Key sections for calibration:
  - **`fates-codebase-wiki/advanced/cnp_calibration_guide.md`** - **START HERE** for CNP calibration (Knox 2026)
  - `fates-codebase-wiki/plant-physiology/parteh/cnp_allocation.md` - PID controller, three-phase allocation
  - `fates-codebase-wiki/advanced/nutrient_competition.md` - ECA vs RD modes, prescribed vs coupled uptake
  - `fates-codebase-wiki/plant-physiology/parteh/soil_plant_interface.md` - Nutrient uptake mechanics
  - `fates-official-docs/docs/source/parteh/` - PARTEH equations

### Adaptive Memory (`memory/gained_knowledge/`)
- `discoveries.json` - 11 actionable discoveries from Knox 2026 CNP Guidebook + A2MC experience
- `experiments.json` - Experiment records with outcomes
- `parameters.json` - Parameter knowledge (bounds, sensitivities)
- `failed_approaches.json` - Approaches to NOT repeat

---

## CRITICAL: Never Make Assumptions - Always Check RAG/GraphRAG and knowledge base First

**Before writing comments, documentation, or code that describes FATES behavior:**

1. **NEVER assume** what a parameter, flag, or mechanism does based on its name
2. **ALWAYS query the RAG knowledge base** to verify technical details
3. **Check the FATES documentation** in `docs/fates-knowledge-base/`

**How to query RAG:**
```bash
# Use Python 3.10 for RAG operations
/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -c "
from rag import HybridRetriever
retriever = HybridRetriever(auto_build=False)
# Use available methods: get_parameter_info, get_mechanism_info, get_context, etc.
"
```

**Or search the knowledge base directly:**
```bash
grep -r "use_fates_nocomp" docs/fates-knowledge-base/
```

**Example of what NOT to do:**
- ❌ Assumed `use_fates_nocomp` meant "fixed PFT areas" based on name
- ✅ Should have checked `docs/fates-knowledge-base/fates-codebase-wiki/advanced/simulation_modes.md`
- ✅ Correct: `use_fates_nocomp` means no competition and separates PFTs into patches (no inter-PFT competition), but does NOT fix areas

**Key documentation locations:**
- `docs/fates-knowledge-base/fates-codebase-wiki/` - Code-level wiki with detailed explanations
- `docs/fates-knowledge-base/fates-official-docs/` - Official FATES technical documentation
- `rag/data/curated_relationships.yaml` - Parameter-mechanism-output relationships

---

## When Working on This Codebase

1. **This is the development repo** - Code is developed and committed here (local machine), then pushed to GitHub. A2MC runs on NERSC Perlmutter, which pulls from this repo. When the user shows errors from Perlmutter, fix the issue here (commit + push) — do NOT run `git pull` locally.
2. **Keep orchestrator.py lean** - `orchestrator.py` (~2,800 lines) owns state transitions and human review checkpoints. **Do NOT add new logic directly to it.** Instead, add new functions to `phases/` or `tools/` and call them from orchestrator via thin wrappers (lazy import inside the method body, pass explicit args instead of `self`). See existing wrappers like `_run_diagnostic_scripts()` for the pattern.
3. **Memory integration** - `reasoning/` and `orchestrator.py` both use MemoryManager
4. **State persistence** - Workflow state saved to JSON for resumability
5. **HPC-native** - Designed to run on NERSC, uses direct sbatch/squeue
6. **No SSH tunneling** - API calls made directly from login node
7. **Visualization** - `plot/visualize_a2mc_horizontal.py` generates workflow diagram
8. **Verify before documenting** - Always check RAG/docs before writing technical comments
9. **Git commits** - **NEVER use Co-Authored-By or any AI attribution in commit messages**
10. **Sync to public repo** - After committing framework changes, sync to A2MC-elm (see below)
11. **Phase log cleanup is `--start-phase` ONLY** - The backup-and-clear logic at `orchestrator.py:3451-3499` (which clears downstream `phase_results/` and session `logs/`) ONLY runs when the user explicitly passes `--start-phase` AND `--session-id`. Natural Phase 6 → Phase 3 transitions (next experiment cycle within the same run) MUST NOT clear logs — `c00` logs from the previous cycle are preserved alongside new `c01` logs. Do NOT add log-clearing logic to `_run_refinement()` or anywhere in the natural phase transition path. See `memory/dev_logs/20260409a_Phase6_Refinement_Bug_Fixes.md` ("Behavior Verification: Log Cleanup Only on Explicit `--start-phase`").

---


---

## Important: Keep Code and Documentation Generic

**A2MC is designed to be reusable by the community for different study cases.**

When coding or writing documentation:

1. **Code should be site-agnostic** - Don't hardcode Kougarok-specific paths, parameters, or values
2. **Use configuration files** - Site-specific settings should be in config files, not in code
3. **Documentation should be generic** - Explain concepts and methods, not just Kougarok results
4. **Examples can be specific** - It's OK to use Kougarok as an example, but label it as such

**Memory files can contain case-specific lessons:**
- `discoveries.json` - OK to document Kougarok-specific findings (e.g., "Allocation Paradox")
- These lessons help the AI learn, and users can seed their own discoveries for their sites

**The goal:** Someone studying a different Arctic site (or any ELM-FATES application) should be able to:
1. Clone A2MC
2. Configure their site-specific settings
3. Seed their own initial knowledge
4. Run the calibration workflow

**Use the `use_cases/` folder for site-specific documentation:**
- `use_cases/TEMPLATE/` - Template for new case studies
- `use_cases/Kougarok/` - Kougarok, Alaska example (NGEE-Arctic)
- Create your own: `use_cases/YourSite/`

---

## Related Resources

- **Global CLAUDE.md:** `~/.claude/CLAUDE.md` - Cross-workspace rules, shared workflows (presentation/video, writing rules, tool dependencies)

- **Public Repository:** https://github.com/jingtao-lbl/A2MC-elm
- **Zenodo DOI:** Tao, J. (2026). A2MC: Agentic Adaptive Multi-Target Calibration. Zenodo software release. Autonomous 7-phase calibration framework for E3SM Land Model (ELM) combining LLM reasoning, curated knowledge base, hybrid RAG/GraphRAG retrieval, and persistent adaptive memory. Available from: https://github.com/jingtao-lbl/A2MC-elm. (https://doi.org/10.5281/zenodo.19194999)
- **FATES Knowledge Base:** `docs/fates-knowledge-base/` - Official docs + codebase wiki

### Upstream Model Repositories (always query these for commits, tags, or source — never guess)

| Repo | URL | Role |
|---|---|---|
| **E3SM** | https://github.com/E3SM-Project/E3SM | Host Earth system model. ELM lives at `components/elm/`. |
| **FATES standalone** | https://github.com/NGEET/fates/ | Authoritative FATES source and tag history. Read tags, release notes, source files here. |
| **FATES-users-guide** | https://github.com/NGEET/fates-users-guide | User/developer documentation. Holds the FATES-HLM compatibility table and the Tagging Methodology. |

**FATES inside E3SM:** `E3SM/components/elm/src/external_models/fates/` (FATES is an external model nested under ELM's source tree, NOT a top-level submodule at `components/fates/`). **The FATES commit pinned inside E3SM is often older than `NGEET/fates:main`** — always check the actual commit at `E3SM/components/elm/src/external_models/fates/.git/HEAD` or via `git submodule status`, don't assume E3SM is on the latest FATES.

**Parameter file format:** FATES switched from NetCDF/CDL to JSON at API 43 (`parameter_files/fates_params_default.json`). Older tags (api.31 and earlier) used `.cdl` / `.nc`. Any version-aware code must handle both formats.
---

## Version History

Full changelog: **`memory/a2mc_development_history.md`**

Current version: **v3.00** (2026-07-02)

### Git Tags (Stable Checkpoints)

| Tag | Commit | Description |
|-----|--------|-------------|
| `v2.62-stable-pre-prompt-trim` | `b5367ae` | Last version before AI prompt trimming (v2.63). Rollback: `git checkout v2.62-stable-pre-prompt-trim` |

---

## Contact

**Author:** Jing Tao (jingtao@lbl.gov)
**Project:** NGEE-Arctic Phase 4, CC4, ELM-FATES calibration
