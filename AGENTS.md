# AGENTS.md — A2MC Interactive Agent Operating Contract

**Audience:** Any coding-agent harness (Claude Code or other AGENTS.md-aware agents) operating interactively inside a clone of this repository.
**Scope:** Public-safe, harness-neutral. This is the portable distillation of the operating rules an interactive agent needs.

---

## What you are

A2MC ("Agentic Adaptive Multi-target Calibration") is an AI-driven calibration framework for ELM-FATES. It runs as **one agent in two modes** — read [`README.md` §"Two Ways to Run A2MC"](README.md):

- **Autonomous (online) agent** — `python orchestrator.py --run`, a fixed Phase 0→7 state machine that calls the model in a loop. Unattended, at scale.
- **Interactive (offline) agent** — *you*, a coding-agent harness operating in the repo, driven by conversation. For open-ended, exploratory, judgment-heavy, one-off work the fixed loop cannot do (forensics, synthesis, triage, figures, experiment design, auditing).

Both modes share the same brain and hands — operating rules (this file), the skills catalog (`.claude/skills/`), persistent memory, episodic logs (calibration work → `use_cases/<site>/memory/logs/`, same format as the autonomous agent), RAG/GraphRAG knowledge, and the shared tools in `tools/`. Findings flow between the two modes through that shared substrate (see §"The knowledge loop").

**The Phase 0→7 workflow is the shared calibration roadmap — follow it.** It is documented in [`phases/CLAUDE.md`](phases/CLAUDE.md) (overview + per-phase docs), and it is the methodology *both* modes use, not an orchestrator implementation detail. The online agent *traverses* the phases as a fixed state machine; **you *navigate* the same phases** — enter at the right phase for the task (the Entry Points table in `phases/CLAUDE.md`), apply that phase's discipline and success criteria, and follow the **three-level iteration structure** documented in `phases/CLAUDE.md` rather than a single linear 0→7 pass. The roadmap is nested loops, not a line: an outermost **calibration round** (a full Phase 0→7 cycle; the 6→0 redesign expands the parameter space and starts a new round), within it **experiment cycles** (Phase 3→4→5→6, with the 6→3 rethink when a hypothesis is disproven), and within those a **skip-testing inner loop** (Phase 3↔4 testing hypotheses against existing ensemble data, no new HPC). Your calibration work is phase-aware and iterative, not rigidly sequential, and each phase's `CLAUDE.md` names the skills that serve it. Read the relevant phase doc before working a calibration task, the same way you read a phase folder before editing it (rule 5). Only **off-cycle framework/meta work** (KB build, skill management, auditing) sits outside the 0→7 loop — that is the part the fixed loop genuinely cannot do.

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

At a glance — the full set, grouped (one-liners here; the catalog has the detail). This table is kept complete and in sync with the skills dir by `tools/check_skill_registry.py`:

**Calibration & analysis (core)**

| Skill | Invoke when the user wants to… |
|---|---|
| `summarize-calibration-round` | Summarize one round: ensemble figures + evaluation + Morris μ* sensitivity report |
| `compare-calibration-rounds` | Compare rounds R1…RN, "which round is best", refresh a multi-round figure |
| `offline-testing-workflow` | Design + launch + analyze a parameter-sweep experiment on a Morris base case |
| `restart-failed-jobs` | Restart SLURM jobs that failed in an ensemble/experiment |
| `arm-hpc-monitoring` | Set up real-time monitoring of an in-flight ensemble at session start |
| `diagnose-forensics` | Investigate an ensemble anomaly — artifact triage first, then root-cause via the phase3 tools |
| `phase0-design` | Run Phase 0 (DESIGN) — sample the parameter space, materialize per-case param files, submit + monitor the HPC ensemble |
| `phase1-exploration` | Run Phase 1 (EXPLORATION) — extract the Y matrix, run Morris sensitivity, interpret μ* (what to tune) |
| `phase2-screening` | Run Phase 2 (SCREENING) — rank the ensemble vs targets, best/most-targets cases, bias patterns, route to Phase 3 |
| `phase3-diagnosis` | Run Phase 3 (DIAGNOSIS) — offline analog of `reasoning.diagnose()`: root-cause the round's failing targets via the phase3 tools + RAG + Memory, hand off to Phase 4 |
| `phase4-hypothesis` | Run Phase 4 (HYPOTHESIS) — testable hypotheses + skip-test against existing Morris data (no HPC), else route to Phase 5 |
| `phase5-testing` | Run Phase 5 (TESTING) — thin router to `offline-testing-workflow` for HPC experiment execution |
| `phase6-refinement` | Run Phase 6 (REFINEMENT) — evaluate results, extract lessons, write curated Memory (offline disposer), decide converge/rethink/redesign |
| `scientific-analysis` | Manuscript-supporting investigation → figure → ana_log (pose, analyze, cite, write) |
| `curate-knowledge` | Review + promote staged Tier-3 knowledge proposals into the curated KB (human-in-the-loop) |
| `onboard-session` | Cold-start runbook at session start / after compaction — restore context, check in-flight work, delegate |
| `calibration-log` | Log calibration work for a site (phase log via PhaseLogger, or free-form session log) under `use_cases/{site}/memory/logs/` |

**Knowledge-base build pipeline**

| Skill | Invoke when the user wants to… |
|---|---|
| `build-rag-from-scratch` | Build the whole RAG/GraphRAG layer from scratch — new-model onboarding or disaster recovery |
| `generate-codebase-wiki` | Produce a source-grounded codebase wiki for a model (step 1 of the KB build) |
| `rebuild-rag` | Rebuild/repair the RAG index — reindex, bump the wiki commit, refresh after a curated-YAML edit |
| `inject-knowledge` | Inject a human-originated discovery / parameter / relationship into the curated KB |
| `validate-rag-chain` | Validate the source→wiki→curated-YAML→RAG chain before shipping |

**Skill management (meta)**

| Skill | Invoke when the user wants to… |
|---|---|
| `add-skill` | Scaffold + register a new skill (this procedure) — keeps the registries in sync |
| `refine-skill` | Improve an existing skill from accumulated evidence, human-gated |

**Utilities**

| Skill | Invoke when the user wants to… |
|---|---|
| `markdown-to-pdf` | Convert a Markdown doc (ana_log / report / note) to a shareable PDF or .docx |

When a request matches a skill's trigger, invoke that skill **before** improvising — it encodes conventions (case-naming, dedicated experiment dirs, reproducibility gates) that are easy to get wrong from first principles.

## Memory & knowledge conventions

| Where | What it holds | You should… |
|---|---|---|
| `memory/gained_knowledge/` | Generic FATES discoveries, parameters, failed approaches (JSON) | read for context; add vetted discoveries |
| `use_cases/<site>/memory/gained_knowledge/` | Site-specific knowledge | read for the site you're working on |
| `use_cases/<site>/memory/logs/` | Calibration session logs — phase logs (Phase 0–7) + free-form session notes, same format the autonomous agent produces | **write** here via the `calibration-log` skill when you do calibration/analysis work; read prior logs for the site |
| `rag/` + `docs/fates-knowledge-base/` | FATES knowledge (RAG + static docs) | query before asserting FATES behavior |
| `tools/` | Shared utilities (extraction, plotting, HPC, cost functions) | reuse rather than re-implement |

**Before starting a task:** grep prior logs for the same topic — calibration work lives in `use_cases/<site>/memory/logs/`. Repeating a superseded approach is the most common avoidable mistake.

**When you finish substantive work:** write a dated log so the next session (and the autonomous agent's knowledge absorption) can build on it. Calibration/analysis work → `use_cases/<site>/memory/logs/` via the `calibration-log` skill (same format as the autonomous agent, so synthesis sees both modes). You should log **more** than the autonomous agent, not less: the human's reasoning, the decisions made in conversation, and the alternatives considered and discarded are ephemeral, and capturing that decision record is exactly what the machine loop cannot do.

## The knowledge loop

The two modes are two writers on **one knowledge substrate**:

```
  Interactive agent  ──writes──►  logs / memories / gained_knowledge / tools
        ▲                                          │
        │ reasons over                             │ absorbed by
        │ phase logs + run state                   ▼
  Autonomous agent  ◄──reads/writes──  MemoryManager + RAG + phase execution logs
```

The interactive agent writes engineering + analysis logs, curates knowledge, and builds tools; the autonomous agent's `MemoryManager` and RAG absorb that knowledge and apply it in the calibration loop, while emitting phase logs and run state that the interactive agent then reasons over. Neither mode forks the knowledge base — improvements compound across both.

---

*This is the public, harness-neutral operating contract. For the development-repo superset (clone topology, sync workflow, host-specific run paths), Claude Code reads the private `CLAUDE.md` when present — that content is intentionally not part of this shareable file.*
