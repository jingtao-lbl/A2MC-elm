# A2MC Phase Overview

**Purpose:** Overview of all calibration phases and their relationships
**Last Updated:** July 2, 2026

---

## The shared calibration roadmap (both agent modes)

The Phase 0→7 workflow below is the **single methodology both A2MC agent modes follow** — the
calibration roadmap, not an implementation detail of the orchestrator:

- The **autonomous (online) agent** (`orchestrator.py --run`) *traverses* the phases mechanically
  as a fixed state machine, tracking the nested loops with explicit counters.
- The **interactive (offline) agent** (a coding-agent harness driven by conversation) *navigates*
  the same phases with judgment — it enters at the right phase for the task (see **Entry Points**
  below) and uses the same nested loops (see **Three-Level Iteration Structure** below). It is
  phase-aware and iterative, not rigidly sequential.

The roadmap is **not** a single linear 0→7 pass — it is a nested loop structure (see
**Three-Level Iteration Structure** and **Iteration Paths** below).

**Which phases queue new simulations.** Only **Phase 0** (build + submit the ensemble) and
**Phase 5** (submit experiments) queue new ELM-FATES simulation jobs. Every other phase reads and
analyzes existing ensemble outputs.

**Per-phase offline skills.** The offline agent has a skill for each phase (`phase0-design` …
`phase6-refinement`), the human-in-the-loop analog of the online agent's `_run_<phase>()` method — it
drives the same scripts and reproduces the reasoning `reasoning.py` does online. These are the
primary entry point per phase; the other skills below support them.

| Phase | Primary phase skill | Supporting skills |
|-------|---------------------|-------------------|
| 0 Design | `phase0-design` | `arm-hpc-monitoring`, `restart-failed-jobs` |
| 1 Exploration | `phase1-exploration` | `summarize-calibration-round`, `compare-calibration-rounds` |
| 2 Screening | `phase2-screening` | `summarize-calibration-round`, `compare-calibration-rounds` |
| 3 Diagnosis | `phase3-diagnosis` | `diagnose-forensics`, `scientific-analysis` |
| 4 Hypothesis | `phase4-hypothesis` | `offline-testing-workflow`, `scientific-analysis` |
| 5 Testing | `phase5-testing` → `offline-testing-workflow` | `arm-hpc-monitoring`, `restart-failed-jobs` |
| 6 Refinement | `phase6-refinement` | `curate-knowledge`, `inject-knowledge`, `summarize-calibration-round` |

> **The phase skills are a floor, not a ceiling.** Each captures what the online agent does so you
> never do *less*; the offline agent's value is doing *more* — pull extra data, run analyses no phase
> tool exists for, cross into an adjacent phase when the evidence leads there.

---

## Phase Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         A2MC CALIBRATION WORKFLOW                               │
│                                                                                 │
│    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐ │
│    │  Phase 0    │     │  Phase 1    │     │  Phase 2    │     │  Phase 3    │ │
│    │   DESIGN    │────▶│ EXPLORATION │────▶│  SCREENING  │────▶│  DIAGNOSIS  │ │
│    │             │     │             │     │             │     │             │ │
│    │ Morris/Sobol│     │ Sensitivity │     │ Multi-Obj   │     │ Root Cause  │ │
│    │  Sampling   │     │  Analysis   │     │ Validation  │     │  Analysis   │ │
│    └──────▲──────┘     └─────────────┘     └─────────────┘     └──────┬──────┘ │
│           │                                                           │        │
│           │ Redesign:                              ┌──────────────────┤        │
│           │ Expand parameter                       │                  │        │
│           │ space if needed                        │                  ▼        │
│           │                                        │           ┌─────────────┐ │
│    ┌──────┴──────┐     ┌─────────────┐     ┌──────┴──────┐     │  Phase 4    │ │
│    │  Phase 7    │     │  Phase 5    │     │  Phase 6    │     │ HYPOTHESIS  │ │
│    │  CONVERGED  │◀────│   TESTING   │◀────│ REFINEMENT  │◀────│             │ │
│    │             │     │             │     │             │     │ Experiment  │ │
│    │  Optimal    │     │ Simulation  │     │  Evaluate   │     │   Design    │ │
│    │   Config    │     │  Execution  │     │   Results   │     └──────┬──────┘ │
│    └─────────────┘     └─────────────┘     └──────┬──────┘            │        │
│                                                   │                   │        │
│                                                   │    Rethink:       │        │
│                                                   │    Adjust         │        │
│                                                   │    hypothesis     │        │
│                                                   │         │         │        │
│                                                   └─────────┼─────────┘        │
│                                                             │                  │
│                                                             ▼                  │
│                                                      Back to Phase 3           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

Iteration Paths:
  ─────▶  Normal flow (forward)
  ──────▶ Phase 4 → Phase 3: Skip testing if existing data can test hypothesis
  ──────▶ Phase 6 → Phase 3: Rethink if hypothesis proven wrong
  ──────▶ Phase 6 → Phase 0: Redesign if parameter space needs expansion
```

---

## Phase Summary Table

| Phase | Name | Purpose | Key Scripts | AI-Driven? |
|-------|------|---------|-------------|------------|
| 0 | Design & Submit | Generate ensemble, submit to HPC | `create_parameter_sample.py`, `generate_parameter_files.py`, `submit_phase0.py` | No |
| - | [HPC Wait] | Monitor simulations | `tools/diagnose_ensemble_status.py` | No |
| 1 | Exploration | Extract Y matrix, Morris analysis, interpret results | `extract_sensitivity_outputs.py`, `morris_sensitivity_analysis.py` | **Yes** |
| 2 | Screening | Rank ensemble by targets | `screen_ensemble.py` | Yes |
| 3 | Diagnosis | Root cause analysis, edge case detection, results analysis | `run_diagnosis.py` (+ 11 diagnostic tools) | Yes |
| 4 | Hypothesis | Generate experiments OR test with existing data | `reasoning.py` | Yes |
| 5 | Testing | Run experiments on HPC | `tools/submit_experiment.sh` | No |
| 6 | Refinement | Evaluate results, extract lessons, check equifinality | `reasoning.py`, `memory/manager.py` | Yes |
| 7 | Converged | Final configuration | - | - |

**Phase 3 Diagnostic Tools:** `analyze_carbon_balance.py`, `analyze_mortality.py`, `analyze_nutrient_balance.py`, `analyze_nutrient_pools.py`, `check_edge_parameters.py`, `compare_case_parameters.py`, `compare_targets.py`, `detect_collapse.py`, `diagnose_pft_limitations.py`, `read_case_parameters.py`, `test_hypothesis_framework.py`

---

## Three-Level Iteration Structure

The phases run as **three nested loops**, not a single pass. Both agent modes use the same
structure (the autonomous agent tracks it with explicit counters; the interactive agent navigates
it by judgment):

```
CALIBRATION ROUND (outermost) — a full Phase 0→7 cycle
  e.g. R1 = 138 params, R2 = 162 params; 6→0 redesign starts a new round
  │
  └── EXPERIMENT CYCLE (outer loop) — Phase 3→4→5→6, runs HPC experiments
        6→3 rethink when a hypothesis is disproven; max ~10 cycles
        │
        └── SKIP-TESTING (inner loop) — Phase 3↔4, NO new simulations
              test hypotheses against existing ensemble data; max ~10;
              exit on confidence ≥ threshold or test_with_existing=false
```

| Level | Loop | Phases | Counter (autonomous) |
|-------|------|--------|----------------------|
| Outermost | Calibration round | 0→7 (redesign via 6→0) | `calibration_round` |
| Outer | Experiment cycle | 3→4→5→6 (rethink via 6→3) | `experiment_count` |
| Inner | Skip-testing | 3↔4 (existing data only) | `skip_testing_count` |

The transitions between these loops are the **Iteration Paths** below.

---

## Iteration Paths

A2MC supports multiple iteration paths to avoid unnecessary HPC computation:

### Normal Flow (First Pass)
```
Phase 0 → [HPC] → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → [HPC] → Phase 6
```

### Phase 4 → Phase 3 (Skip Testing)
**When:** Hypothesis can be tested with existing ensemble data (e.g., P mass balance analysis)
**Why:** Avoid HPC cost when diagnosis with current results is sufficient
```
Phase 3 → Phase 4 → (existing data sufficient) → Phase 3 (with new insights)
```

### Phase 6 → Phase 3 (Rethink Hypothesis)
**When:** Experiment results disprove the hypothesis
**Why:** Need to revise diagnosis and generate new hypothesis
```
Phase 6 → (hypothesis wrong) → Phase 3 → Phase 4 → ...
```

### Phase 6 → Phase 0 (Redesign)
**When:** Parameter space needs expansion (all candidates at bounds)
**Why:** Current sampling doesn't cover the optimal region
```
Phase 6 → (bounds too restrictive) → Phase 0 (expanded ranges) → ...
```

---

## Key Design Principle

**No idle waiting within any phase.**

Each phase completes with a concrete deliverable:
- Phase 0 → Jobs submitted to HPC queue
- Phase 1 → Morris sensitivity rankings (CSV + plots)
- Phase 2 → Ranked case list with RMSRE and targets satisfied
- Phase 3 → Diagnosis report with root causes
- Phase 4 → Experiment design OR hypothesis tested with existing data
- Phase 5 → Experiment results
- Phase 6 → Lessons extracted to memory, equifinality assessment
- Phase 7 → Final parameter file

---

## Shared Tools (in `tools/`)

All phases share utilities from the `tools/` directory:

| Tool | Used By | Purpose |
|------|---------|---------|
| `config.py` | All | Configuration management |
| `create_case.sh` | Phase 0 | Create CIME case |
| `submit_ensemble.sh` | Phase 0 | Submit ensemble jobs |
| `submit_experiment.sh` | Phase 5 | Submit experiment jobs |
| `diagnose_ensemble_status.py` | Between 0→1 | Check HPC completion |
| `cost_functions.py` | Phase 1, 2 | Error metrics |
| `optimize_function.py` | Phase 2 | Rank ensemble |
| `fates_utils.py` | Phase 1, 2 | FATES data handling |
| `modify_fates_parameters.py` | Phase 0, 5 | Edit parameter files |

---

## Phase Folder Structure

Each phase folder contains:
```
phase{N}_{name}/
├── CLAUDE.md           # Context for AI when working in this phase
├── __init__.py         # Python package marker
└── {phase_scripts}.py  # Phase-specific scripts
```

**Always read the phase's CLAUDE.md** before working in that phase.

---

## Entry Points

| Scenario | Start At |
|----------|----------|
| New calibration (no simulations) | Phase 0 |
| Simulations complete, need analysis | Phase 1 |
| Ensemble ranked, need diagnosis | Phase 3 |
| Hypothesis ready, need testing | Phase 5 |
| Resuming after experiment | Phase 6 |
| Hypothesis testable with existing data | Phase 3 (skip Phase 5) |
