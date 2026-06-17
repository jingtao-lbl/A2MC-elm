# AGENTS.md — A2MC Interactive Agent Operating Contract

**Audience:** Any coding-agent harness (Claude Code or other AGENTS.md-aware agents) operating interactively inside a clone of this repository.
**Scope:** Public-safe, harness-neutral. This is the portable distillation of the operating rules an interactive agent needs.

---

## What you are

A2MC ("Agentic Adaptive Multi-target Calibration") is an AI-driven calibration framework for ELM-FATES. It runs as **one agent in two modes** — read [`README.md` §"Two Ways to Run A2MC"](README.md):

- **Autonomous (online) agent** — `python orchestrator.py --run`, a fixed Phase 0→7 state machine that calls the model in a loop. Unattended, at scale.
- **Interactive (offline) agent** — *you*, a coding-agent harness operating in the repo, driven by conversation. For open-ended, exploratory, judgment-heavy, one-off work the fixed loop cannot do (forensics, synthesis, triage, figures, experiment design, auditing).

Both modes share the same brain and hands — operating rules (this file), the skills catalog (`.claude/skills/`), persistent memory, episodic logs (`memory/dev_logs/` for engineering, `memory/ana_logs/` for scientific analysis), RAG/GraphRAG knowledge, and the shared tools in `tools/`. Findings flow between the two modes through that shared substrate (see §"The knowledge loop").

## Core operating rules

These are the site- and framework-agnostic rules. Follow them on every task.

1. **Verify, don't assume.** Never state what a parameter, flag, file, or mechanism does based on its name. Read the source of truth first — the relevant config, script, doc, or the FATES knowledge base. When uncertain, check before claiming.
2. **Query the knowledge base before describing FATES behavior.** A2MC ships a three-tier FATES knowledge system (static docs in `docs/fates-knowledge-base/`, RAG/GraphRAG in `rag/`, Adaptive Memory in `memory/gained_knowledge/`). Consult it before writing comments, docs, or code that assert how FATES works. Full detail (hybrid vector + two-layer knowledge graph, curated YAML overlay, Python-3.10 requirement) lives in `CLAUDE.md` §"RAG/GraphRAG System" and `docs/a2mc_reference/rag_reference.md` — read those rather than reconstructing the system from this one-line summary.
3. **Keep code and docs generic.** A2MC is meant to be reused for many sites. Code must be site-agnostic; site-specific content belongs in `use_cases/<site>/`. Don't hardcode site paths, parameters, or values — use the config files.
4. **No hardcoded paths.** Machine settings live in `a2mc_config.sh`; site settings in `use_cases/<site>/config/<site>_config.sh`. Access them in Python via `tools/config.py`. Source both config files before running anything.
5. **Read the phase folder's context doc when working in a phase folder.** Each `phases/phaseN_*/` carries its own README (and a `CLAUDE.md` in the dev repo); read it before editing there.
6. **Keep `orchestrator.py` lean.** It owns state transitions and human-review checkpoints only. Add new logic to `phases/` or `tools/` and call it from the orchestrator via thin wrappers — never grow the state machine with new logic.
7. **No AI attribution in commits.** Never add `Co-Authored-By` or any AI-attribution trailer to git commit messages. Use the project's author convention for authored files.
8. **Check structure before writing paths.** Verify actual folder/file names by listing or reading existing code; never guess directory names.
9. **Confirm before destructive or hard-to-reverse actions.**

## Capability catalog (skills)

Your reusable capabilities live in `.claude/skills/`, each a folder with a `SKILL.md`. The harness auto-discovers them; the `description` frontmatter is the trigger the agent matches against a request. The full human- and agent-readable index — purpose, when to invoke, backing tools — is:

➡️ **[`docs/a2mc_reference/skills_catalog.md`](docs/a2mc_reference/skills_catalog.md)**

At a glance:

| Skill | Invoke when the user wants to… |
|---|---|
| `summarize-calibration-round` | Summarize one round: ensemble figures + evaluation + Morris μ* sensitivity report |
| `compare-calibration-rounds` | Compare rounds R1…RN, "which round is best", refresh a multi-round figure |
| `offline-testing-workflow` | Design + launch + analyze a parameter-sweep experiment on a Morris base case |
| `restart-failed-jobs` | Restart SLURM jobs that failed in an ensemble/experiment |
| `arm-hpc-monitoring` | Set up real-time monitoring of an in-flight ensemble at session start |
| `log` | Write a dev/analysis/session/handoff log in the repo's two-stream logging system |
| `curate-knowledge` | Review + promote staged Tier-3 knowledge proposals into the curated KB (human-in-the-loop) |
| `onboard-session` | Cold-start runbook at session start / after compaction — restore context, check in-flight work, delegate |
| `diagnose-forensics` | Investigate an ensemble anomaly — artifact triage first, then root-cause via the phase3 tools |
| `scientific-analysis` | Manuscript-supporting investigation → figure → ana_log (pose, analyze, cite, write) |

When a request matches a skill's trigger, invoke that skill **before** improvising — it encodes conventions (case-naming, dedicated experiment dirs, reproducibility gates) that are easy to get wrong from first principles.

## Memory & knowledge conventions

| Where | What it holds | You should… |
|---|---|---|
| `memory/gained_knowledge/` | Generic FATES discoveries, parameters, failed approaches (JSON) | read for context; add vetted discoveries |
| `use_cases/<site>/memory/gained_knowledge/` | Site-specific knowledge | read for the site you're working on |
| `memory/dev_logs/` | Engineering changelog — code/infra changes (Markdown, dated) | **read before** starting related work; **write** a dated log for substantive changes |
| `memory/ana_logs/` | Scientific analysis / working notes — results interpretation, manuscript-supporting reasoning (Markdown, dated) | read for prior analysis on the topic; write a dated note when you interpret results or reason scientifically |
| `rag/` + `docs/fates-knowledge-base/` | FATES knowledge (RAG + static docs) | query before asserting FATES behavior |
| `tools/` | Shared utilities (extraction, plotting, HPC, cost functions) | reuse rather than re-implement |

**Before starting a task:** grep both `memory/dev_logs/` and `memory/ana_logs/` for prior work on the same topic. Much of the framework's hard-won knowledge is recorded there, and repeating a superseded approach is the most common avoidable mistake.

**When you finish substantive work:** write a dated log so the next session (and the autonomous agent's knowledge absorption) can build on it — a **dev log** (`memory/dev_logs/`) for engineering/code changes, an **analysis note** (`memory/ana_logs/`) for results interpretation and scientific reasoning.

## The knowledge loop

The two modes are two writers on **one knowledge substrate**:

```
  Interactive agent  ──writes──►  dev_logs / ana_logs / memories / gained_knowledge / tools
        ▲                                          │
        │ reasons over                             │ absorbed by
        │ phase logs + run state                   ▼
  Autonomous agent  ◄──reads/writes──  MemoryManager + RAG + phase execution logs
```

The interactive agent writes engineering + analysis logs, curates knowledge, and builds tools; the autonomous agent's `MemoryManager` and RAG absorb that knowledge and apply it in the calibration loop, while emitting phase logs and run state that the interactive agent then reasons over. Neither mode forks the knowledge base — improvements compound across both.

---

*This is the public, harness-neutral operating contract. For the development-repo superset (clone topology, sync workflow, host-specific run paths), Claude Code reads the private `CLAUDE.md` when present — that content is intentionally not part of this shareable file.*
