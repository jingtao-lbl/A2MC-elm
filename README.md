# A2MC: Agentic Adaptive Multi-target Calibration

[![CAF Agent of the Week](https://img.shields.io/badge/CAF-Agent%20of%20the%20Week-blue)](https://github.com/AI-ModCon/BaseCAF_agent_of_the_week/blob/main/AotW-05-A2MC.md)

**Status:** Implementation Complete <br>
**Version:** 2.127 <br>
**Purpose:** Fully autonomous multi-target calibration of ELM (with or without FATES) using AI API + HPC + RAG/GraphRAG + Adaptive Memory

> **New here?** This README is the front door. For the full operational detail — configuration reference, per-phase behavior, module APIs, knowledge-system internals, state persistence, cost, and reporting — see the [**A2MC User Guide**](docs/a2mc_reference/user_guide.md).

---

## Motivation

Earth system models like ELM-FATES contain hundreds of parameters that must be calibrated against observations at each study site. Traditional calibration is a months-long manual process of running ensembles on HPC, inspecting sensitivity analyses, and making expert decisions about which parameters to adjust. Black-box optimizers (genetic algorithms, gradient descent) work well when the parameter space already contains viable solutions, but for novel model configurations where no prior successful calibration exists (e.g., ELM-FATES CNP at Arctic sites), the initial ensemble may entirely miss observational ranges. In these cases, numerical optimization alone cannot identify the mechanistic barriers preventing calibration. A2MC addresses this by combining optimization with interpretable, hypothesis-driven reasoning that diagnoses *why* the model fails and proposes targeted fixes.

A2MC replaces the manual process with an autonomous, interpretable workflow that:

- **Leverages a model-specific knowledge base** through hybrid RAG/GraphRAG retrieval over documentation, codebase wikis, and curated parameter-mechanism-output relationships
- **Diagnoses root causes** of calibration failures using LLM reasoning augmented with retrieved knowledge
- **Generates and tests hypotheses** with specific parameter modifications and predicted outcomes
- **Satisfies multiple targets simultaneously** (biomass, fluxes, phenology across PFTs), reducing equifinality through mechanistically defensible solutions
- **Learns across sessions** via persistent adaptive memory, avoiding repeated failures across sites and campaigns
- **Minimizes HPC cost** by selecting among flexible iteration paths (re-diagnose, skip testing, redesign, converge)

<p align="center">
  <img src="https://raw.githubusercontent.com/jingtao-lbl/A2MC-elm/main/plot/A2MC_Workflow_Horizontal_Finalized_A2MC-ELM.png" width="100%" alt="A2MC 7-phase calibration workflow">
</p>

---

## Two Ways to Run A2MC

A2MC is **one agent you run two ways**. The intelligence lives in the repo's shared assets — operating rules, a skills catalog, persistent memory, episodic logs, RAG knowledge, and tools — and two different runtimes consume those same assets:

| | **Autonomous agent** (online) | **Interactive agent** (offline) |
|---|---|---|
| Runtime | `python orchestrator.py --run` — AI API inside a Python state machine | A coding-agent harness (e.g. Claude Code) operating directly in the repo |
| Driver | Fixed Phase 0→7 state machine | Human conversation, turn-by-turn |
| Cadence | Unattended, at scale (`--run` checkpoints by default; `--no-review` = fully autonomous) | Human-in-the-loop |
| Best for | The repetitive, well-defined calibration loop | Open-ended, exploratory, one-off, judgment-heavy tasks |
| Curated memory | **Proposes** (auto-learned lessons staged for review) | **Promotes** (the sole writer of curated knowledge) |

A2MC is **mode-aware**: the same repo runs ELM with or without FATES, different FATES API milestones, and different nutrient schemes (ECA vs RD). Both runtimes resolve the active configuration (`python tools/describe_mode.py`) and adapt, and both read and write the **same knowledge substrate**, so discoveries made by one agent compound in the other.

- **Online agent:** the Quick Start below. `python orchestrator.py --run` drives the full Phase 0→7 loop.
- **Offline agent:** any coding-agent harness opened in a clone of this repo. Its operating contract is [`AGENTS.md`](AGENTS.md) (harness-neutral); on startup the harness auto-loads the operating rules plus the capability catalog of skills in `.claude/skills/` (indexed in [`docs/a2mc_reference/skills_catalog.md`](docs/a2mc_reference/skills_catalog.md)), then you drive it by conversation. It is the tool for work the fixed loop cannot do (forensics, synthesis, triage, one-off analysis) and, because of the curated-memory gate, the **only** writer of vetted knowledge.

**The knowledge loop** — the two agents are two writers on one knowledge substrate, so improvements compound across both:

```
  Interactive agent  ──writes/promotes──►  calibration logs / curated knowledge / tools
        ▲                                          │
        │ reasons over                             │ absorbed by
        │ phase logs + run state                   ▼
  Autonomous agent  ◄──reads / PROPOSES──  MemoryManager (propose mode) + RAG + phase logs
```

A discovery vetted by either agent is available to the other on the next run.

---

## Architecture

<p align="center">
  <img src="https://raw.githubusercontent.com/jingtao-lbl/A2MC-elm/main/plot/A2MC_Architecture.png" width="100%" alt="A2MC architecture: orchestrator state machine over reasoning, phase scripts, and shared tools">
</p>

## The 7-phase workflow

| Phase | Name | Purpose | AI-Driven? |
|-------|------|---------|------------|
| 0 | DESIGN | Morris/Sobol sampling, create cases, submit to HPC | Yes |
| 1 | EXPLORATION | Extract Y matrix, run sensitivity analysis | Yes |
| 2 | SCREENING | Rank ensemble by validation targets | Yes |
| 3 | DIAGNOSIS | Root cause analysis, edge case detection | Yes |
| 4 | HYPOTHESIS | Generate experiments OR test with existing data | Yes |
| 5 | TESTING | Run designed experiments on HPC | No |
| 6 | REFINEMENT | Evaluate results, extract lessons, check equifinality | Yes |
| 7 | CONVERGED | Final optimal configuration | - |

Non-linear iteration paths avoid unnecessary HPC computation: **Phase 4 → Phase 3** (skip testing when existing data can test the hypothesis), **Phase 6 → Phase 3** (rethink when results disprove the hypothesis), **Phase 6 → Phase 0** (redesign when the parameter space needs expansion). These are organized as three nested loops — calibration round (Phase 0→7), experiment cycle (Phase 3→4→5→6→3), and skip-testing (Phase 3↔4).

Full per-phase behavior, diagnostic-tool inventory, and the three-level iteration counters are in the [User Guide → 7-phase workflow](docs/a2mc_reference/user_guide.md#5-the-7-phase-workflow-in-detail).

---

## Quick Start (online agent)

```bash
# 1. Create a use case (copy the Kougarok example or the minimal template)
cp -r use_cases/ELM-FATES_Kougarok use_cases/YourSite      # or use_cases/TEMPLATE

# 2. Configure site + machine settings
vim use_cases/YourSite/config/yoursite_config.sh # PFTs, parameters, validation, HPC paths
vim a2mc_config.sh                               # HPC project, A2MC_MODEL_PATH, AI provider

# 3. Set the API key for your provider (one-time)
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc && source ~/.bashrc

# 4. Source both configs and run
source a2mc_config.sh
source use_cases/YourSite/config/yoursite_config.sh
python orchestrator.py --run                     # add --no-review for fully autonomous
```

`A2MC_MODEL_PATH` (your E3SM/ELM-FATES checkout root) is **required** — A2MC reads the FATES + ELM commits and selects the matching RAG profile. AI reasoning (phases 2, 3, 4, 6) needs the API key for your chosen provider (`anthropic`, `openai`, or `cborg`).

Full setup — every config field, provider/model table, installation on NERSC Perlmutter, and all run/resume options — is in the [User Guide → Installation](docs/a2mc_reference/user_guide.md#1-installation-and-setup-nersc-perlmutter), [Configuration](docs/a2mc_reference/user_guide.md#2-configuration-reference), and [Running the workflow](docs/a2mc_reference/user_guide.md#4-using-the-online-autonomous-agent).

---

## Quick Start (offline agent)

The offline agent is any coding-agent harness (e.g. Claude Code) opened in a clone of this repo. There is nothing to launch — you open the repo and talk to it.

```bash
# 1. Clone and open the repo in a coding agent that reads AGENTS.md
git clone https://github.com/jingtao-lbl/A2MC-elm.git && cd A2MC-elm

# 2. (For calibration work) point at your checkout so mode-aware skills resolve
export A2MC_MODEL_PATH="/path/to/your/E3SM_FATES_checkout"
```

**First time?** Just tell the agent **"set up A2MC"** (or "help me get started"). That runs the [`a2mc-init`](.claude/skills/a2mc-init/SKILL.md) skill, which interviews you (checkout location, FATES on/off, carbon-only vs nutrient-enabled, site, PFTs, calibration targets), verifies your checkout against the RAG milestone, creates and populates your use case, and hands off to Phase 0.

On startup the harness auto-loads the operating contract ([`AGENTS.md`](AGENTS.md)) and the capability catalog of skills in `.claude/skills/`. Then drive it by conversation — the agent resolves the active mode (`python tools/describe_mode.py`), matches your request to an applicable skill, or reasons from the shared tools, memory, and RAG knowledge:

```text
"Set up A2MC" (first-time setup)                -> a2mc-init
"Catch up — where did we leave off?"           -> onboard-session
"Screen the ensemble and diagnose the misses"  -> phase2-screening / phase3-diagnosis
"Run a parameter-sweep experiment for X"        -> offline-testing-workflow
"Review and promote the pending proposals"     -> curate-knowledge
"Restart the jobs that failed in this ensemble" -> restart-failed-jobs
```

No API key or `orchestrator.py` run is needed — the reasoning happens in your coding agent. Full skills index: [`docs/a2mc_reference/skills_catalog.md`](docs/a2mc_reference/skills_catalog.md); operating rules: [`AGENTS.md`](AGENTS.md).

---

## Knowledge system

A2MC encodes the same FATES/ELM knowledge in three tiers so the AI can reach it via multiple paths:

| Tier | Location | Purpose |
|------|----------|---------|
| **Static Documentation** | `docs/fates-knowledge-base/` | Human reference, RAG indexing |
| **RAG/GraphRAG** | `rag/{chroma_db,graphs,metadata}/<profile>/` | AI semantic search + graph traversal — **version-aware** and **configuration-aware** |
| **Adaptive Memory** | `memory/gained_knowledge/` | AI reasoning context, learned discoveries |

The RAG/GraphRAG tier auto-detects the user's E3SM/ELM-FATES checkout (via `A2MC_MODEL_PATH`) and loads the matching knowledge profile (**version-aware**, v2.90+), filters every chunk to the active simulation mode — FATES on/off, PARTEH carbon-only vs CNP, ECA vs RD, fire/hydraulics/logging on/off (**configuration-aware**, v2.91/v2.92), and can auto-rebuild the profile when the checkout drifts (**drift-aware**, v2.98). Two milestones ship: `api-43-1` (canonical) and `api-31-0` (legacy / Kougarok manuscript reproducibility).

The **Adaptive Memory** system learns across sessions: generic FATES insights in `memory/gained_knowledge/` and site-specific discoveries under `use_cases/{site}/memory/`, with generalizable lessons promoted from site to generic. At diagnosis/hypothesis time, RAG knowledge, adaptive memory, and current task data are combined into the reasoning prompt (failed approaches marked "DO NOT REPEAT").

Details: [User Guide → Knowledge system](docs/a2mc_reference/user_guide.md#7-knowledge-system) and [Adaptive Memory](docs/a2mc_reference/user_guide.md#8-adaptive-memory-system).

---

## Documentation

- [**A2MC User Guide**](docs/a2mc_reference/user_guide.md) — full operational reference (config, phases, modules, knowledge system, state, cost, reporting)
- [`AGENTS.md`](AGENTS.md) — operating contract for the offline interactive agent
- [`docs/a2mc_reference/skills_catalog.md`](docs/a2mc_reference/skills_catalog.md) — offline-agent skills catalog
- `docs/a2mc_reference/` — mode-aware workflow, version association, validation playbook, RAG build roadmap, FATES data reference
- `docs/fates-knowledge-base/` — FATES documentation (official docs + codebase wiki)
- `use_cases/ELM-FATES_Kougarok/README.md` — a complete worked example (Arctic tundra, NGEE-Arctic)

---

## Citation

If you use A2MC in your work, please cite the software release:

> Tao, J. (2026). *A2MC: Agentic Adaptive Multi-Target Calibration.* Zenodo software release. Autonomous 7-phase calibration framework for the E3SM Land Model (ELM) combining LLM reasoning, a curated knowledge base, hybrid RAG/GraphRAG retrieval, and persistent adaptive memory. https://doi.org/10.5281/zenodo.19194999

```bibtex
@software{tao_a2mc_2026,
  author    = {Tao, Jing},
  title     = {{A2MC}: Agentic Adaptive Multi-Target Calibration},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.19194999},
  url       = {https://github.com/jingtao-lbl/A2MC-elm},
  note      = {Autonomous 7-phase calibration framework for the E3SM Land Model (ELM)
               combining LLM reasoning, a curated knowledge base, hybrid RAG/GraphRAG
               retrieval, and persistent adaptive memory}
}
```

A dedicated methods paper on A2MC is in preparation; this section will be updated with the article citation once it is available.

---

## References

- [Anthropic Claude API](https://docs.anthropic.com/)
- [NERSC SLURM Documentation](https://docs.nersc.gov/jobs/)
- [ELM-FATES Technical Reference](https://fates-users-guide.readthedocs.io/)
- [SALib Morris Sensitivity](https://salib.readthedocs.io/)
- [CAF Agent of the Week #7 — A2MC](https://github.com/AI-ModCon/BaseCAF_agent_of_the_week/blob/main/AotW-05-A2MC.md)


---

## Contact

**Author:** Jing Tao <br>
**Email:** jingtao@lbl.gov <br>
**Project:** NGEE-Arctic Phase 4, CC4, ELM-FATES calibration <br>
**GitHub:** https://github.com/jingtao-lbl/A2MC-elm
