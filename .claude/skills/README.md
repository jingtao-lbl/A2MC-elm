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

## Changelog
- YYYY-MM-DD: Initial version — distilled from <source>.
```

When Claude Code starts in this repo, the skills are auto-discovered. The `description` field is what Claude uses to decide whether to invoke the skill for a given user request — write it as a triggering description, not a summary.

Every `SKILL.md` ends with a **`## Changelog`** — dated one-liners of what changed and why. Git holds the diff; the Changelog is the human-readable evolution trail, so a future reader (or a refinement pass) can see how the skill grew without `git blame`. (Convention adopted 2026-06-17, ported from the E2SA skill-evolution design.)

## Current skills

| Skill | Triggers when |
|---|---|
| [offline-testing-workflow](offline-testing-workflow/SKILL.md) | Designing + launching + analyzing an offline HPC experiment (parameter sweep on a Morris base case): N variants, V0 reproducibility gate, decision tree → KB injection. Invoke BEFORE writing any "test the X hypothesis" / "parameter sweep" plan. Steps 10–11 are backed by `tools/extract_and_plot_selected_cases.py`. |
| [restart-failed-jobs](restart-failed-jobs/SKILL.md) | Jobs failed in an A2MC ensemble or experiment and need to be restarted (or archived if model failure). Distinguishes infrastructure (NODE_FAIL, SIGKILL) from model failures (runaway recruitment, PARTEH abort). |
| [arm-hpc-monitoring](arm-hpc-monitoring/SKILL.md) | Session starts (or resumes after compaction) while an HPC ensemble is in flight on Perlmutter. Per CLAUDE.md Rule #6. |
| [compare-calibration-rounds](compare-calibration-rounds/SKILL.md) | Compare rounds R1…RN against each other + targets: top-N biomass overlay, per-target Morris μ* overlay, P-pool/cross-regime. Refresh any `multiround_*` figure. |
| [summarize-calibration-round](summarize-calibration-round/SKILL.md) | One-round summary: combined+TRANS ensemble graphs + evaluation (best case, targets met) + Morris μ* sensitivity → markdown/PDF report. |
| [calibration-log](calibration-log/SKILL.md) | Log interactive calibration work for a site under `use_cases/{site}/memory/logs/` — a **phase log** (via `PhaseLogger`, same format as the autonomous agent) or a free-form **session log** (`YYYYMMDDx_Topic.md`). Invoke on "log this phase / diagnosis / experiment", "log this calibration session", "record what I explored". |
| [curate-knowledge](curate-knowledge/SKILL.md) | Human-in-the-loop review + promotion of staged Tier-3 proposals (`auto_discovered_pending.json` → curated KB). The other half of the v2.90 write gate; invoke on "review/promote pending knowledge" or at session start when proposals exist. |
| [onboard-session](onboard-session/SKILL.md) | Cold-start runbook at session start / after compaction: re-read CLAUDE.md, read latest handoff, check live HPC processes + run state, delegate to arm-hpc-monitoring / curate-knowledge. Pairs with the G2 SessionStart hook. |
| [diagnose-forensics](diagnose-forensics/SKILL.md) | Investigate an ensemble anomaly/outlier/failure-cluster: artifact triage (contamination, infra-timing, mislabeled index, NaN) FIRST, then root-cause via the phase3 diagnosis tools. |

| [phase0-design](phase0-design/SKILL.md) | **Phase workflow (offline analog of the online agent's Phase 0):** Run Phase 0 (DESIGN) — sample the parameter space (Morris/Sobol/LHS), materialize per-case FATES param files, generate+build+submit the HPC ensemble, arm monitoring. Invoke on "design a new round", "submit the ensemble", "expand the parameter space (redesign)". |
| [phase1-exploration](phase1-exploration/SKILL.md) | **Phase workflow:** Run Phase 1 (EXPLORATION) — extract the Y matrix, run Morris sensitivity, interpret μ* (what to tune, generic vs PFT-specific, edge effects). Invoke on "run the sensitivity analysis", "which parameters matter", "run Phase 1". |
| [phase2-screening](phase2-screening/SKILL.md) | **Phase workflow:** Run Phase 2 (SCREENING) — rank the ensemble vs targets (RMSRE, targets-met), find best/lowest-cost/most-targets cases, read bias patterns, route to Phase 3. Includes the `--max-case-num` contamination guard. Invoke on "screen the ensemble", "which case is best", "run Phase 2". |
| [phase3-diagnosis](phase3-diagnosis/SKILL.md) | **Phase workflow:** Run Phase 3 (DIAGNOSIS) — HITL analog of `reasoning.diagnose()`: systematically root-cause why the round misses its targets (phase3 tools + RAG + Memory → ranked root causes, parameter recs, base cases, hypotheses), hand off to Phase 4. Invoke on "diagnose the failing targets", "run Phase 3". (Systematic per-round; for one suspicious case use `diagnose-forensics`.) |
| [phase4-hypothesis](phase4-hypothesis/SKILL.md) | **Phase workflow:** Run Phase 4 (HYPOTHESIS) — turn a diagnosis into testable hypotheses (parameter moves + expected outcomes), skip-test against existing Morris data first (3↔4, no HPC), else route to Phase 5. Invoke on "generate a hypothesis", "what should we test next", "can we test this with existing data". |
| [phase5-testing](phase5-testing/SKILL.md) | **Phase workflow:** Run Phase 5 (TESTING) — thin router to `offline-testing-workflow` for HPC experiment execution (param files, case-suffix cases, V0 gate, extract). Invoke on "run the experiment", "submit the test cases", "run Phase 5". |
| [phase6-refinement](phase6-refinement/SKILL.md) | **Phase workflow:** Run Phase 6 (REFINEMENT) — evaluate results vs baseline/expected (honestly), extract lessons, write curated Memory directly + promote staged proposals (offline "disposer"), decide converge / rethink (6→3) / redesign (6→0). Invoke on "evaluate the results", "what did we learn", "should we converge or iterate". |

| [scientific-analysis](scientific-analysis/SKILL.md) | Manuscript-supporting investigation → figure → ana_log: pose a question, pull data, compute the statistic/mechanism, cite evidence, write the ana_log. |
| [build-rag-from-scratch](build-rag-from-scratch/SKILL.md) | Knowledge-base build **orchestrator**: construct the whole RAG/GraphRAG layer when the index and/or its inputs don't exist — reconstruct an existing model's layer (api-31-0 reproducibility, Path R) or bootstrap a new model (EcoSim/ReSOM, Recipe 2 Path N). Sequences the four step-skills + owns loader registration, per-model parsers, separate persist dirs. Includes the "prove the graph built, not just the vector index" gate. (For reindexing existing inputs, use `rebuild-rag`.) |
| [generate-codebase-wiki](generate-codebase-wiki/SKILL.md) | Knowledge-base build (step 1): produce a source-grounded codebase wiki by fanning out parallel subagents that cite `(file:line)`. Workflow A (greenfield) vs B (audit+rewrite); fabrication/citation gates; commit-pinned output. |
| [rebuild-rag](rebuild-rag/SKILL.md) | Knowledge-base build (step 2): rebuild/repair the RAG/GraphRAG index (`scripts/build_rag_index.py`). Encodes the loader pattern-probe symlink footgun, `--rebuild` vs `--graph-only`, Python 3.10, verify gates. Invoke on "rebuild the RAG", "bump the wiki", "I edited the curated YAML", "the index stopped working". |
| [inject-knowledge](inject-knowledge/SKILL.md) | Knowledge-base build (step 3): inject a human-originated fact (discovery / parameter insight / mechanism) across the up-to-3 curated channels (discoveries.json, parameters.json, curated YAML), validate + graph-rebuild. Judgment-scaffolding — you own the truth call. Human-originated counterpart to curate-knowledge. Invoke on "add this finding to A2MC's AI", "make the agent aware of X". |
| [validate-rag-chain](validate-rag-chain/SKILL.md) | Knowledge-base build (step 4): validate source→wiki→YAML→RAG with the 3 validators in dependency order (`codebase_wiki_validator` → `yaml_wiki_validator` → `rag_diff`), Green/Yellow/Red banding + fabrication-vs-false-positive triage. |
| [add-skill](add-skill/SKILL.md) | Meta (skill management): scaffold a new skill + register it in all THREE registries (this table + `skills_catalog.md` + `AGENTS.md`) + seed a `## Changelog` + run the drift check; human-gated. Invoke on "add/scaffold a skill", "distill X into a skill". |
| [refine-skill](refine-skill/SKILL.md) | Meta (skill management): improve an existing skill from accumulated signal (dev_logs/ana_logs/verify findings) — propose a concrete `SKILL.md` diff, **never self-apply**, human gate, then edit + Changelog line. Invoke on "refine/improve the X skill", "review the skills". |
| [markdown-to-pdf](markdown-to-pdf/SKILL.md) | Utility: convert a Markdown doc to PDF or Word (`.docx`) via pandoc (+ a LaTeX engine for PDF; python-docx for round-trip-safe `.docx` edits). Prose/reports/notes, not slides. Self-contained repo copy of a general user-level converter. Invoke on "convert/render markdown to PDF/docx". |

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
3. Body: decision tree → recipes (numbered, with ready-to-run bash) → anti-patterns → cross-references, ending with a **`## Changelog`** (seed an "Initial version" line citing the source).
4. Register in **both** human-facing registries: the `Current skills` table above **and** `docs/a2mc_reference/skills_catalog.md`. (The `add-skill` skill does this for you.)
5. Run `python3 tools/check_skill_registry.py` — it must exit 0 (verifies disk ↔ README table ↔ catalog parity, `name:`↔dir, `## Changelog`, **and that every repo path / sibling-skill the SKILL.md cites actually exists** — the Tier-1 contract check that catches skill rot). This is enforced by the **`.githooks/pre-commit`** hook whenever skill-system files are staged. Activate it once per clone (git doesn't auto-run hooks from clones): `git config core.hooksPath .githooks` (bypass in an emergency with `git commit --no-verify`).
6. Commit on the appropriate branch (per CLAUDE.md Rule #11 — verify branch first).
7. Write a brief dev_log noting why the skill was extracted and from which source logs.

## Refining a skill (refine on signal, not noise)

Skills should get better as they're used — absorbing the traps and better practices we discover — without silently rewriting themselves and drifting. The discipline (ported 2026-06-17 from the E2SA skill-evolution design):

- **Refine on a repeated signal**, not a one-off: the same trap hit ≥ ~2–3 times, an explicit human correction, or a clear failure pattern. A single surprise is usually not enough to change the contract.
- **Surgical edits only** — add or fix a step / gotcha / trigger phrase; don't bloat or rewrite wholesale. A skill that keeps growing is a smell — consider splitting or pruning instead.
- **`description` (trigger) edits are the highest risk** — they change *when* the skill fires, so a careless edit silently mis-fires or hides the skill. Treat trigger changes with extra care and call them out in the dev_log.
- **Cite the evidence** — every change names the dev_log / ana_log / verify-pass / correction that justifies it. No speculative edits.
- **Append a `## Changelog` line** stating what changed and which signal drove it, in the same commit (Rule #11 wants the dev_log too if substantive).
- Curated knowledge writes stay human-gated (see `curate-knowledge` / `inject-knowledge`); editing a skill is a contract change, so it is likewise a human-reviewed step, never an autonomous self-rewrite.

A2MC has no `refine-skill` *meta-skill* yet (E2SA does); this is the convention a human-driven refinement follows. If refinements become frequent, distilling that into a meta-skill is the natural next step.

## Skills are branch-scoped

This `.claude/` directory is tracked in git, so each branch has its own skill set. On `kougarok_fates_demo`, skills should reflect the operational reality of that branch (FATES api-31-0, Kougarok manuscript flow, R5 ensemble structure). On `main`, skills may differ (version-association infrastructure, adapter-kit work). Don't blindly copy skills across branches — re-evaluate the recipes against the branch's actual tooling and conventions.

## Anti-patterns

- **Do NOT** write a skill that just paraphrases existing CLAUDE.md content. Skills should add value beyond the master context file — typically by capturing operational recipes that don't belong in the always-loaded CLAUDE.md.
- **Do NOT** add a skill for a one-off recipe used in a single session. Wait until the pattern repeats; otherwise the skill rots.
- **Do NOT** put binary blobs (scripts, configs) in `SKILL.md` itself. If a skill needs an accompanying script, add it as a sibling file in the same folder and reference it.
- **Do NOT** make skills depend on session-local Claude state (e.g., specific task IDs, specific Monitor task names). Skills must be reproducible from a cold session.
