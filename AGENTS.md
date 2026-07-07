# AGENTS.md — A2MC Interactive Agent Operating Contract

**Audience:** Any coding-agent harness (Claude Code or other AGENTS.md-aware agents) operating interactively inside a clone of this repository.
**Scope:** Public-safe, harness-neutral. This is the portable distillation of the operating rules an interactive agent needs.

---

## What you are

A2MC ("Agentic Adaptive Multi-target Calibration") is an AI-driven calibration framework for **ELM — with or without FATES**. It runs as **one agent, two ways** — read [`README.md` §"Two Ways to Run A2MC"](README.md):

- **Autonomous (online) agent** — `python orchestrator.py --run`, a fixed Phase 0→7 state machine that calls the model in a loop. Unattended, at scale.
- **Interactive (offline) agent** — *you*, a coding-agent harness operating in the repo, driven by conversation. For open-ended, exploratory, judgment-heavy, one-off work the fixed loop cannot do (forensics, synthesis, triage, figures, experiment design, auditing). You are also the **only writer of curated knowledge**: the autonomous agent runs its memory in "propose" mode (stages proposals); *you* review and promote them (see §"Memory & knowledge conventions").

Both agents share the same brain and hands — operating rules (this file), the skills catalog (`.claude/skills/`), persistent memory, episodic logs (`use_cases/<site>/memory/logs/` — phase + session logs), RAG/GraphRAG knowledge, and the shared tools in `tools/`. Findings flow between the two agents through that shared substrate (see §"The knowledge loop").

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
10. **Drive the workflow; pause only at forks + hard stops.** Given a goal, advance it — you are the superset of the autonomous loop, which drives itself with no per-phase prompt. Execute the resume brain's next action (extract, monitor, run a planned experiment, advance a phase); surface results + proposals, not "shall I…?" for mechanical steps. **Pause** for: a Phase-6 converge/redesign/stop decision, a curated-KB write, an expensive/irreversible action, or a standing hard stop (rule 9). See the `onboard-session` skill's drive-vs-pause list.

## Offline-Agent Operating Discipline

The interactive (offline) agent has **four recurring failure modes** — judgment lapses at unguarded
checkpoints. Each has one **checkable habit** and a **gate** that enforces it. This is the canonical
stance; the individual `feedback_*` memories carry the detail. *A new correction updates this section
(or a linked memory) — it does not spawn a free-floating memory.*

| Failure mode | The habit | Enforced by |
|---|---|---|
| **Verify before claiming.** A restated log / an unverified "load-bearing" number / a KB write on a mechanism-story. | Every load-bearing number cites a script + output produced **this session**; confidence ≤ what was tested; no curated-KB write without a verification link. | `tools/check_offline_log_evidence.py` (analysis-log gate) + `add_discovery(verified_by=…)` / `promote --verified-by` gate + `check_rag_coverage.py`. |
| **Track the objective.** Crash-debugging displacing the fit; escalating to "stop → model" too early. | Before converge / redesign / **stop**, state the binding target + the next targeted experiment; "stop → model-dev" must be *earned*. | `WorkflowStateOffline.validate_phase6_decision()` (blocks a premature escalation). |
| **Drive, don't wait.** Asking permission for mechanical steps. | Execute the resume brain's next action; pause only at forks + hard stops. | Core rule 10 + the SessionStart `► NEXT:` line + `onboard-session` drive-vs-pause list. |
| **Trust the skill.** A memory that drifts from / shadows a SKILL; acting on a truncated skill. | A SKILL is authoritative over a memory; read the full SKILL before acting; never encode a memory that contradicts one. | Review discipline + `check_memory_bucket.py` dead-link backstop. |


## Capability catalog (skills)

Your reusable capabilities live in `.claude/skills/`, each a folder with a `SKILL.md`. The harness auto-discovers them; the `description` frontmatter is the trigger the agent matches against a request, and the `modes:` frontmatter declares which run configurations the skill applies to. The full human- and agent-readable index — purpose, when to invoke, mode applicability, backing tools — is:

➡️ **[`docs/a2mc_reference/skills_catalog.md`](docs/a2mc_reference/skills_catalog.md)**

At a glance (most skills are mode-agnostic; the FATES Morris-ensemble analysis skills are `requires_fates: true`). Full index + per-skill detail: the catalog above.

| Skill | Modes | Invoke when the user wants to… |
|---|---|---|
| `calibration-log` | any | Log interactive calibration/exploration work for a site (PhaseLogger + session logs) |
| `a2mc-init` | any | First-run setup — interview + create/populate a use case, then hand off to phase0-design (distinct from onboard-session) |
| `onboard-session` | any | Cold-start: orient at session start or after a compaction/reset |
| `curate-knowledge` | any | Review + promote staged Tier-3 knowledge proposals (the write-gate loop) |
| `arm-hpc-monitoring` | any (HPC) | Set up real-time monitoring of an in-flight ensemble at session start |
| `restart-failed-jobs` | any (HPC) | Restart SLURM jobs that failed in an ensemble/experiment |
| `diagnose-forensics` | any | Investigate an anomaly — real or artifact? — then root-cause it |
| `scientific-analysis` | any | Run an investigation → figure → ana_log |
| `markdown-to-pdf` | any | Convert a markdown ana_log/report/note to a shareable PDF or Word doc |
| `build-rag-from-scratch` | any | Build the RAG/GraphRAG knowledge layer from scratch (new model or full reconstruction) |
| `rebuild-rag` | any | Rebuild/repair the RAG index — reindex, bump wiki commit, refresh the graph |
| `generate-codebase-wiki` | any | Produce a source-grounded codebase wiki for a model |
| `validate-rag-chain` | any | Validate the source → wiki → curated-YAML → RAG chain before shipping |
| `inject-knowledge` | any | Inject a human-originated discovery / parameter / relationship into curated knowledge |
| `add-skill` | any | Scaffold + register a new skill (4-way registry parity) |
| `refine-skill` | any | Refine an existing skill from accumulated evidence (human-gated) |
| `summarize-calibration-round` | **FATES** | Summarize one calibration round (whole-ensemble biomass + evaluation report) |
| `compare-calibration-rounds` | **FATES** | Compare calibration rounds (top-N, μ* sensitivity, cross-round overlays) |
| `offline-testing-workflow` | **FATES** | Design + launch + analyze a parameter-sweep HPC experiment |
| `phase0-design` | any | Offline Phase 0 — design/sample/submit the ensemble |
| `phase1-exploration` | any | Offline Phase 1 — extract Y matrix + Morris sensitivity |
| `phase2-screening` | any | Offline Phase 2 — rank ensemble vs validation targets |
| `phase3-diagnosis` | any | Offline Phase 3 — root-cause the failing targets |
| `phase4-hypothesis` | any | Offline Phase 4 — hypotheses + skip-test on existing data |
| `phase5-testing` | any | Offline Phase 5 — run HPC experiments (routes to offline-testing-workflow) |
| `phase6-refinement` | any | Offline Phase 6 — evaluate, learn, converge/iterate |

When a request matches a skill's trigger **and** the active mode satisfies its `modes:` block, invoke that skill **before** improvising — it encodes conventions (case-naming, dedicated experiment dirs, reproducibility gates) that are easy to get wrong from first principles.

## Memory & knowledge conventions

| Where | What it holds | You should… |
|---|---|---|
| `memory/gained_knowledge/` | Generic model discoveries, parameters, failed approaches (JSON) | read for context; **promote** vetted proposals here (you are the curator) |
| `use_cases/<site>/memory/gained_knowledge/` | Site-specific knowledge | read for the site you're working on |
| `use_cases/<site>/memory/logs/` | Calibration/exploration logs for a site — phase logs (via PhaseLogger) + free-form session notes | read a session's prior logs for context; **write** here via the `calibration-log` skill |
| `rag/` + `docs/fates-knowledge-base/` | Model knowledge (RAG + static docs), per milestone | query (active milestone) before asserting model behavior |
| `tools/` | Shared utilities (extraction, plotting, HPC, cost functions) | reuse rather than re-implement |

**Curated-knowledge gate:** the autonomous agent runs its `MemoryManager` in `propose` mode — its auto-learned discoveries are staged to `auto_discovered_pending.json`, not written to the curated JSONs. You (the interactive agent) review and promote vetted entries via `tools/review_pending_knowledge.py`. This keeps the knowledge that shapes every future diagnosis human-vetted.

**Before starting a task:** read the site's prior session logs under `use_cases/<site>/memory/logs/` for work on the same site/round. Repeating a superseded approach is the most common avoidable mistake.

**When you finish substantive work:** write a log via the `calibration-log` skill — a phase log or a free-form session note under `use_cases/<site>/memory/logs/` — so the next session can build on it.

## The knowledge loop

The two agents are two writers on **one knowledge substrate**:

```
  Interactive agent  ──writes/promotes──►  calibration logs / curated knowledge / tools
        ▲                                          │
        │ reasons over                             │ absorbed by
        │ phase logs + run state                   ▼
  Autonomous agent  ◄──reads / PROPOSES──  MemoryManager (propose mode) + RAG + phase logs
```

The interactive agent writes calibration/analysis logs, curates knowledge (promoting the autonomous agent's proposals), and builds tools; the autonomous agent's `MemoryManager` and RAG absorb that vetted knowledge and apply it in the calibration loop, while emitting phase logs, run state, and *proposed* lessons that the interactive agent then reasons over and promotes. Neither agent forks the knowledge base — improvements compound across both.

---

*This is the public, harness-neutral operating contract. When a project-specific `CLAUDE.md` is present, Claude Code reads it for any additional detail that file provides.*
