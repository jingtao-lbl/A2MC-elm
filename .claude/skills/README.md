# A2MC Project Skills

This directory holds **reusable workflow skills** for the A2MC project — operational patterns distilled from prior session experience so future Claude Code sessions can invoke them by natural-language match rather than reassembling from scattered dev_logs.

## What is a skill?

A skill is a folder under `.claude/skills/` containing a `SKILL.md` with YAML frontmatter:

```yaml
---
name: <skill-name>
description: <when to use this skill — Claude reads this to decide if it's relevant>
modes:                       # which run configurations this skill applies to
  requires_fates: false      # true => only meaningful when use_fates
  nutrient_pathway: any      # any | eca | rd
  scope: [hpc]               # tags: hpc | analysis | logging | experiment
  summary: "<one-line applicability note>"
---

# Skill body — action-oriented instructions
```

A2MC is **mode-aware** (ELM with/without FATES, different FATES API milestones, ECA vs RD).
Before mode-specific steps a skill should resolve the active mode (`python tools/describe_mode.py`)
and honor its own `modes:` block — skip or branch when the case's mode doesn't satisfy it.

When Claude Code starts in this repo, the skills are auto-discovered. The `description` field is what Claude uses to decide whether to invoke the skill for a given user request — write it as a triggering description, not a summary.

## Current skills

Each skill declares a `modes:` block (see below) so the agent can check it against the active
run configuration (`python tools/describe_mode.py`). Most skills are mode-agnostic (`any`); the
FATES Morris-ensemble analysis skills (`summarize-`/`compare-calibration-rounds`,
`offline-testing-workflow`) are `requires_fates: true` — the gate keeps them out of ELM-only mode.

| Skill | Modes | Triggers when |
|---|---|---|
| [log](log/SKILL.md) | any | Write a dev_log / ana_log / session log / Handoff_To_Main in the two-stream logging system. Invoke on "/log", "write a log", "log this session". |
| [onboard-session](onboard-session/SKILL.md) | any | Cold-start runbook — orient at session start or after a compaction/reset ("catch up", "where did we leave off"). |
| [curate-knowledge](curate-knowledge/SKILL.md) | any | Review + promote staged Tier-3 knowledge proposals (the human-in-the-loop half of the memory write gate). |
| [arm-hpc-monitoring](arm-hpc-monitoring/SKILL.md) | any (HPC) | Session starts (or resumes after compaction) while an HPC ensemble is in flight. |
| [restart-failed-jobs](restart-failed-jobs/SKILL.md) | any (HPC) | Jobs failed in an ensemble/experiment and need restart (or archive if model failure). |
| [diagnose-forensics](diagnose-forensics/SKILL.md) | any | Investigate an anomaly/outlier/too-good "best" case — real or artifact? — then root-cause it. |
| [scientific-analysis](scientific-analysis/SKILL.md) | any | Manuscript-supporting investigation → figure → ana_log (question → data → statistic → figure → evidence). |
| [build-rag-from-scratch](build-rag-from-scratch/SKILL.md) | any | Construct the RAG/GraphRAG knowledge layer from scratch (for a new model or a fresh build). |
| [rebuild-rag](rebuild-rag/SKILL.md) | any | Rebuild/refresh the RAG/GraphRAG index (wiki bump, curated-YAML graph-only refresh). |
| [generate-codebase-wiki](generate-codebase-wiki/SKILL.md) | any | Generate a source-grounded codebase wiki for a model. |
| [validate-rag-chain](validate-rag-chain/SKILL.md) | any | Validate the RAG chain with the three validators, in order. |
| [inject-knowledge](inject-knowledge/SKILL.md) | any | Inject curated domain knowledge into the KB via the curated-YAML overlay. |
| [add-skill](add-skill/SKILL.md) | any | Scaffold + register a new skill (frontmatter + ## Changelog + both registries + drift check). |
| [refine-skill](refine-skill/SKILL.md) | any | Refine an existing skill from accumulated evidence, human-gated (propose → approve → apply). |
| [summarize-calibration-round](summarize-calibration-round/SKILL.md) | FATES | One-round summary: ensemble figures + evaluation + Morris μ* sensitivity → markdown/PDF. |
| [compare-calibration-rounds](compare-calibration-rounds/SKILL.md) | FATES | Compare rounds R1…RN + targets (top-N biomass + per-target Morris μ* overlays). |
| [offline-testing-workflow](offline-testing-workflow/SKILL.md) | FATES | Design + launch + analyze an offline HPC parameter-sweep experiment on a Morris base case. |

## Skills vs dev_logs

| | Skill (`.claude/skills/`) | Dev log (`memory/dev_logs/`) |
|---|---|---|
| Purpose | Reusable WORKFLOW (HOW to do something) | Forensic RECORD (WHY/WHAT happened in one session) |
| Audience | Future Claude sessions (auto-discovered) | Human + future Claude reading session history |
| Tone | Action-oriented; bash blocks ready to paste | Narrative; chronological |
| Lifetime | Long-lived; updated as the workflow evolves | Immutable; written once per session |
| Cross-reference | Skill cites the originating dev_logs for forensic context | Dev_log cites the skill when the workflow was first formalized |

When the same workflow is invoked multiple times across sessions, both records grow:
- The skill accumulates refinements (better filters, anti-patterns learned from new bugs).
- New dev_logs accumulate each session's specific events (which cases failed, which cohort, what was the operator decision).

If a skill's behavior changes substantively (anti-pattern discovered, new step added), record the change in the next session's dev_log AND update the SKILL.md in the same commit.

## Adding a new skill

1. Look for a pattern across ≥ 2 dev_logs that would benefit from consolidation (mention by previous Claude session, repeated bash recipes, scattered decision criteria).
2. Create `<.claude/skills/<kebab-name>/SKILL.md` with YAML frontmatter (`name`, `description`).
3. Body: decision tree → recipes (numbered, with ready-to-run bash) → anti-patterns → cross-references.
4. Add an entry to the `Current skills` table above.
5. Commit on the appropriate branch (per CLAUDE.md Rule #11 — verify branch first).
6. Write a brief dev_log noting why the skill was extracted and from which source logs.

## Skills are branch- and mode-scoped

This `.claude/` directory is tracked in git, so each branch carries its own skill set, and skills must be **mode-aware** rather than assume one model configuration. A manuscript working branch may pin a specific stack (e.g. FATES at one API with one nutrient scheme); `main` is generic and runs many configurations. Don't blindly copy a skill across branches or assume a stack — declare the skill's `modes:` applicability and re-evaluate its recipes against the active tooling and the resolved run configuration (`tools/describe_mode.py`).

## Anti-patterns

- **Do NOT** write a skill that just paraphrases existing CLAUDE.md content. Skills should add value beyond the master context file — typically by capturing operational recipes that don't belong in the always-loaded CLAUDE.md.
- **Do NOT** add a skill for a one-off recipe used in a single session. Wait until the pattern repeats; otherwise the skill rots.
- **Do NOT** put binary blobs (scripts, configs) in `SKILL.md` itself. If a skill needs an accompanying script, add it as a sibling file in the same folder and reference it.
- **Do NOT** make skills depend on session-local Claude state (e.g., specific task IDs, specific Monitor task names). Skills must be reproducible from a cold session.
