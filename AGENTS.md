# AGENTS.md — A2MC Interactive Agent Operating Contract

**Audience:** Any coding-agent harness (Claude Code or other AGENTS.md-aware agents) operating interactively inside a clone of this repository.
**Scope:** Public-safe, harness-neutral. This is the portable distillation of the operating rules an interactive agent needs.

---

## What you are

A2MC ("Agentic Adaptive Multi-target Calibration") is an AI-driven calibration framework for **ELM — with or without FATES**. It runs as **one agent in two modes** — read [`README.md` §"Two Ways to Run A2MC"](README.md):

- **Autonomous (online) agent** — `python orchestrator.py --run`, a fixed Phase 0→7 state machine that calls the model in a loop. Unattended, at scale.
- **Interactive (offline) agent** — *you*, a coding-agent harness operating in the repo, driven by conversation. For open-ended, exploratory, judgment-heavy, one-off work the fixed loop cannot do (forensics, synthesis, triage, figures, experiment design, auditing). You are also the **only writer of curated knowledge**: the autonomous agent runs its memory in "propose" mode (stages proposals); *you* review and promote them (see §"Memory & knowledge conventions").

Both modes share the same brain and hands — operating rules (this file), the skills catalog (`.claude/skills/`), persistent memory, episodic logs (`memory/dev_logs/` for engineering, `memory/ana_logs/` for scientific analysis), RAG/GraphRAG knowledge, and the shared tools in `tools/`. Findings flow between the two modes through that shared substrate (see §"The knowledge loop").

## Resolve your mode first

A2MC is **mode-aware**: the same repo runs different model configurations — ELM with or without FATES, different FATES API versions/milestones (which even change the parameter-file format), and different nutrient schemes (ECA vs RD), among others. Guidance, parameters, and mechanisms that are true in one mode are false in another.

**Before any mode-specific work** (diagnosing parameters, editing param files, plotting PFT outputs, designing experiments), determine the active configuration:

```bash
python tools/describe_mode.py          # human-readable Active Run Configuration
python tools/describe_mode.py --json   # structured fields for branching
```

This resolves the case's `ConfigMode` (`tools/config.py`): `bgc_mode`, `use_fates` (+ feature flags), `parteh_mode`, `nutrient`, `nutrient_comp_pathway` (`rd`/`eca`), plus the active RAG milestone (model API). Each skill declares its applicability in a `modes:` frontmatter block — honor it: if a skill `requires_fates: true` and FATES is off, it does not apply; if its logic is pathway-specific, branch on `nutrient_comp_pathway`. Do not carry one mode's assumptions into another.

## Core operating rules

These are the site- and framework-agnostic rules. Follow them on every task.

1. **Verify, don't assume.** Never state what a parameter, flag, file, or mechanism does based on its name. Read the source of truth first — the relevant config, script, doc, or the model knowledge base. When uncertain, check before claiming.
2. **Query the knowledge base before describing model behavior.** A2MC ships a three-tier knowledge system (static docs in `docs/fates-knowledge-base/`, RAG/GraphRAG in `rag/`, Adaptive Memory in `memory/gained_knowledge/`). Consult it — **for the active milestone's profile** (`$A2MC_RAG_ACTIVE`) — before writing comments, docs, or code that assert how the model (FATES/ELM) works.
3. **Keep code and docs generic.** A2MC is meant to be reused for many sites and model configurations. Code must be site- and mode-agnostic; site-specific content belongs in `use_cases/<site>/`. Don't hardcode site paths, parameters, or values — use the config files.
4. **No hardcoded paths.** Machine settings live in `a2mc_config.sh`; site settings in `use_cases/<site>/config/<site>_config.sh`. Access them in Python via `tools/config.py`. Source both config files before running anything.
5. **Read the phase folder's context doc when working in a phase folder.** Each `phases/phaseN_*/` carries its own README (and a `CLAUDE.md` in the dev repo); read it before editing there.
6. **Keep `orchestrator.py` lean.** It owns state transitions and human-review checkpoints only. Add new logic to `phases/` or `tools/` and call it from the orchestrator via thin wrappers — never grow the state machine with new logic.
7. **No AI attribution in commits.** Never add `Co-Authored-By` or any AI-attribution trailer to git commit messages. Use the project's author convention for authored files.
8. **Check structure before writing paths.** Verify actual folder/file names by listing or reading existing code; never guess directory names.
9. **Confirm before destructive or hard-to-reverse actions.**

## Capability catalog (skills)

Your reusable capabilities live in `.claude/skills/`, each a folder with a `SKILL.md`. The harness auto-discovers them; the `description` frontmatter is the trigger the agent matches against a request, and the `modes:` frontmatter declares which run configurations the skill applies to. The full human- and agent-readable index — purpose, when to invoke, mode applicability, backing tools — is:

➡️ **[`docs/a2mc_reference/skills_catalog.md`](docs/a2mc_reference/skills_catalog.md)**

At a glance (most skills are mode-agnostic; the FATES Morris-ensemble analysis skills are `requires_fates: true`). Full index + per-skill detail: the catalog above.

| Skill | Modes | Invoke when the user wants to… |
|---|---|---|
| `log` | any | Write a dev/analysis/session/handoff log in the two-stream logging system |
| `onboard-session` | any | Cold-start: orient at session start or after a compaction/reset |
| `curate-knowledge` | any | Review + promote staged Tier-3 knowledge proposals (the write-gate loop) |
| `arm-hpc-monitoring` | any (HPC) | Set up real-time monitoring of an in-flight ensemble at session start |
| `restart-failed-jobs` | any (HPC) | Restart SLURM jobs that failed in an ensemble/experiment |
| `diagnose-forensics` | any | Investigate an anomaly — real or artifact? — then root-cause it |
| `scientific-analysis` | any | Run an investigation → figure → ana_log |
| `build-rag-from-scratch` · `rebuild-rag` · `generate-codebase-wiki` · `validate-rag-chain` · `inject-knowledge` | any | Construct / refresh / validate the RAG/GraphRAG knowledge layer |
| `add-skill` · `refine-skill` | any | Scaffold/register a new skill, or refine an existing one (human-gated) |
| `summarize-calibration-round` · `compare-calibration-rounds` · `offline-testing-workflow` | **FATES** | Summarize/compare calibration rounds, or run a parameter-sweep experiment (FATES Morris ensembles) |

When a request matches a skill's trigger **and** the active mode satisfies its `modes:` block, invoke that skill **before** improvising — it encodes conventions (case-naming, dedicated experiment dirs, reproducibility gates) that are easy to get wrong from first principles.

## Memory & knowledge conventions

| Where | What it holds | You should… |
|---|---|---|
| `memory/gained_knowledge/` | Generic model discoveries, parameters, failed approaches (JSON) | read for context; **promote** vetted proposals here (you are the curator) |
| `use_cases/<site>/memory/gained_knowledge/` | Site-specific knowledge | read for the site you're working on |
| `memory/dev_logs/` | Engineering changelog — code/infra changes (Markdown, dated) | **read before** starting related work; **write** a dated log for substantive changes |
| `memory/ana_logs/` | Scientific analysis / working notes — results interpretation, manuscript-supporting reasoning (Markdown, dated) | read for prior analysis on the topic; write a dated note when you interpret results or reason scientifically |
| `rag/` + `docs/fates-knowledge-base/` | Model knowledge (RAG + static docs), per milestone | query (active milestone) before asserting model behavior |
| `tools/` | Shared utilities (extraction, plotting, HPC, cost functions) | reuse rather than re-implement |

**Curated-knowledge gate:** the autonomous agent runs its `MemoryManager` in `propose` mode — its auto-learned discoveries are staged to `auto_discovered_pending.json`, not written to the curated JSONs. You (the interactive agent) review and promote vetted entries via `tools/review_pending_knowledge.py`. This keeps the knowledge that shapes every future diagnosis human-vetted.

**Before starting a task:** grep both `memory/dev_logs/` and `memory/ana_logs/` for prior work on the same topic. Much of the framework's hard-won knowledge is recorded there, and repeating a superseded approach is the most common avoidable mistake.

**When you finish substantive work:** write a dated log so the next session can build on it — a **dev log** (`memory/dev_logs/`) for engineering/code changes, an **analysis note** (`memory/ana_logs/`) for results interpretation and scientific reasoning.

## The knowledge loop

The two modes are two writers on **one knowledge substrate**:

```
  Interactive agent  ──writes/promotes──►  dev_logs / ana_logs / curated knowledge / tools
        ▲                                          │
        │ reasons over                             │ absorbed by
        │ phase logs + run state                   ▼
  Autonomous agent  ◄──reads / PROPOSES──  MemoryManager (propose mode) + RAG + phase logs
```

The interactive agent writes engineering + analysis logs, curates knowledge (promoting the autonomous agent's proposals), and builds tools; the autonomous agent's `MemoryManager` and RAG absorb that vetted knowledge and apply it in the calibration loop, while emitting phase logs, run state, and *proposed* lessons that the interactive agent then reasons over and promotes. Neither mode forks the knowledge base — improvements compound across both.

---

*This is the public, harness-neutral operating contract. For the development-repo superset (clone topology, sync workflow, host-specific run paths), Claude Code reads the private `CLAUDE.md` when present — that content is intentionally not part of this shareable file.*
