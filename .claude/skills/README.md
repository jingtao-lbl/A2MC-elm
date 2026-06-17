# A2MC Project Skills

This directory holds **reusable workflow skills** for the A2MC project — operational patterns distilled from prior session experience so future Claude Code sessions can invoke them by natural-language match rather than reassembling from scattered dev_logs.

## What is a skill?

A skill is a folder under `.claude/skills/` containing a `SKILL.md` with YAML frontmatter:

```yaml
---
name: <skill-name>
description: <when to use this skill — Claude reads this to decide if it's relevant>
---

# Skill body — action-oriented instructions
```

When Claude Code starts in this repo, the skills are auto-discovered. The `description` field is what Claude uses to decide whether to invoke the skill for a given user request — write it as a triggering description, not a summary.

## Current skills

| Skill | Triggers when |
|---|---|
| [offline-testing-workflow](offline-testing-workflow/SKILL.md) | Designing + launching + analyzing an offline HPC experiment (parameter sweep on a Morris base case): N variants, V0 reproducibility gate, decision tree → KB injection. Invoke BEFORE writing any "test the X hypothesis" / "parameter sweep" plan. Steps 10–11 are backed by `tools/extract_and_plot_selected_cases.py`. |
| [restart-failed-jobs](restart-failed-jobs/SKILL.md) | Jobs failed in an A2MC ensemble or experiment and need to be restarted (or archived if model failure). Distinguishes infrastructure (NODE_FAIL, SIGKILL) from model failures (runaway recruitment, PARTEH abort). |
| [arm-hpc-monitoring](arm-hpc-monitoring/SKILL.md) | Session starts (or resumes after compaction) while an HPC ensemble is in flight on Perlmutter. Per CLAUDE.md Rule #6. |
| [compare-calibration-rounds](compare-calibration-rounds/SKILL.md) | Compare rounds R1…RN against each other + targets: top-N biomass overlay, per-target Morris μ* overlay, P-pool/cross-regime. Refresh any `multiround_*` figure. |
| [summarize-calibration-round](summarize-calibration-round/SKILL.md) | One-round summary: combined+TRANS ensemble graphs + evaluation (best case, targets met) + Morris μ* sensitivity → markdown/PDF report. |
| [log](log/SKILL.md) | Write a dev_log / ana_log / session log / Handoff_To_Main in the two-stream logging system (naming, header, required sections, version-bump/supersede/handoff post-steps). Invoke on "/log", "write a log", "log this session". |
| [curate-knowledge](curate-knowledge/SKILL.md) | Human-in-the-loop review + promotion of staged Tier-3 proposals (`auto_discovered_pending.json` → curated KB). The other half of the v2.90 write gate; invoke on "review/promote pending knowledge" or at session start when proposals exist. |
| [onboard-session](onboard-session/SKILL.md) | Cold-start runbook at session start / after compaction: re-read CLAUDE.md, read latest handoff, check live HPC processes + run state, delegate to arm-hpc-monitoring / curate-knowledge. Pairs with the G2 SessionStart hook. |
| [diagnose-forensics](diagnose-forensics/SKILL.md) | Investigate an ensemble anomaly/outlier/failure-cluster: artifact triage (contamination, infra-timing, mislabeled index, NaN) FIRST, then root-cause via the phase3 diagnosis tools. |
| [scientific-analysis](scientific-analysis/SKILL.md) | Manuscript-supporting investigation → figure → ana_log: pose a question, pull data, compute the statistic/mechanism, cite evidence, write the ana_log. |
| [build-rag-from-scratch](build-rag-from-scratch/SKILL.md) | Knowledge-base build **orchestrator**: construct the whole RAG/GraphRAG layer when the index and/or its inputs don't exist — reconstruct an existing model's layer (api-31-0 reproducibility, Path R) or bootstrap a new model (EcoSim/ReSOM, Recipe 2 Path N). Sequences the four step-skills + owns loader registration, per-model parsers, separate persist dirs. Includes the "prove the graph built, not just the vector index" gate. (For reindexing existing inputs, use `rebuild-rag`.) |
| [generate-codebase-wiki](generate-codebase-wiki/SKILL.md) | Knowledge-base build (step 1): produce a source-grounded codebase wiki by fanning out parallel subagents that cite `(file:line)`. Workflow A (greenfield) vs B (audit+rewrite); fabrication/citation gates; commit-pinned output. |
| [rebuild-rag](rebuild-rag/SKILL.md) | Knowledge-base build (step 2): rebuild/repair the RAG/GraphRAG index (`scripts/build_rag_index.py`). Encodes the loader pattern-probe symlink footgun, `--rebuild` vs `--graph-only`, Python 3.10, verify gates. Invoke on "rebuild the RAG", "bump the wiki", "I edited the curated YAML", "the index stopped working". |
| [inject-knowledge](inject-knowledge/SKILL.md) | Knowledge-base build (step 3): inject a human-originated fact (discovery / parameter insight / mechanism) across the up-to-3 curated channels (discoveries.json, parameters.json, curated YAML), validate + graph-rebuild. Judgment-scaffolding — you own the truth call. Human-originated counterpart to curate-knowledge. Invoke on "add this finding to A2MC's AI", "make the agent aware of X". |
| [validate-rag-chain](validate-rag-chain/SKILL.md) | Knowledge-base build (step 4): validate source→wiki→YAML→RAG with the 3 validators in dependency order (`codebase_wiki_validator` → `yaml_wiki_validator` → `rag_diff`), Green/Yellow/Red banding + fabrication-vs-false-positive triage. |

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

### A note on `dev_logs/` / `ana_logs/` citations (public release)

Skill bodies cite dated logs under `memory/dev_logs/` and `memory/ana_logs/` for
provenance (the engineering/analysis history each recipe was distilled from). Those two
directories are **dev-repo-only and excluded from the public release** (`sync_to_public.sh`),
so in a public clone those `20260…` references won't resolve. They are pointers into the
private development history, **not required reading** to use a skill — every SKILL.md is
self-contained. Treat a missing-citation link in the public release as "see the private
dev history," not a broken instruction.

## Adding a new skill

1. Look for a pattern across ≥ 2 dev_logs that would benefit from consolidation (mention by previous Claude session, repeated bash recipes, scattered decision criteria).
2. Create `<.claude/skills/<kebab-name>/SKILL.md` with YAML frontmatter (`name`, `description`).
3. Body: decision tree → recipes (numbered, with ready-to-run bash) → anti-patterns → cross-references.
4. Add an entry to the `Current skills` table above.
5. Commit on the appropriate branch (per CLAUDE.md Rule #11 — verify branch first).
6. Write a brief dev_log noting why the skill was extracted and from which source logs.

## Skills are branch-scoped

This `.claude/` directory is tracked in git, so each branch has its own skill set. On `kougarok_fates_demo`, skills should reflect the operational reality of that branch (FATES api-31-0, Kougarok manuscript flow, R5 ensemble structure). On `main`, skills may differ (version-association infrastructure, adapter-kit work). Don't blindly copy skills across branches — re-evaluate the recipes against the branch's actual tooling and conventions.

## Anti-patterns

- **Do NOT** write a skill that just paraphrases existing CLAUDE.md content. Skills should add value beyond the master context file — typically by capturing operational recipes that don't belong in the always-loaded CLAUDE.md.
- **Do NOT** add a skill for a one-off recipe used in a single session. Wait until the pattern repeats; otherwise the skill rots.
- **Do NOT** put binary blobs (scripts, configs) in `SKILL.md` itself. If a skill needs an accompanying script, add it as a sibling file in the same folder and reference it.
- **Do NOT** make skills depend on session-local Claude state (e.g., specific task IDs, specific Monitor task names). Skills must be reproducible from a cold session.
