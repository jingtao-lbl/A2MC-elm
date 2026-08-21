# A2MC Project Skills

This directory holds **reusable workflow skills** for the A2MC project — operational patterns distilled from prior session experience so future Claude Code sessions can invoke them by natural-language match rather than reassembling from scattered dev_logs.

## What is a skill?

A skill is a folder under `.claude/skills/` containing a `SKILL.md` with YAML frontmatter:

```yaml
---
name: <skill-name>
visibility: public | private
category: phase | calibration | model-dev | meta | kb-build | authoring
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

**Frontmatter schema (`name` + `visibility` + `category` required and enum-validated by `tools/check_skill_registry.py`; `description` + `modes` as above):**

| Field | Values | What it means / drives |
|---|---|---|
| `name` | = the skill dir name | the `/<name>` invocation; must match the directory |
| `visibility` | `public` \| `private` | **`private` = A2MC-dev-only, excluded from the public demo** — `sync_to_public.sh` derives its exclude list from this field (a new private skill needs no sync edit), and the skill's registry rows must be wrapped in a private-comment block (stripped from the shipped registries by `filter_private`). `public` ships to the demo. Today's private skills: `log`, `manage-auto-memory`, `manuscript-writing-style`, `memory-checkup`, `adopt-from-adapter-kit`. See the note below on citing them. |
| `category` | `phase` \| `calibration` \| `model-dev` \| `meta` \| `kb-build` \| `authoring` | machine-readable grouping (mirrors the `skills_catalog.md` groups): `phase` = the 7 offline phase skills; `calibration` = calibration-support utilities; `model-dev` = ELM/FATES source-change skills; `meta` = skill/session management (`add-skill`, `refine-skill`, `onboard-session`, `a2mc-init`); `kb-build` = the RAG/wiki construction pipeline; `authoring` = doc/report/log writing. |

(The schema mirrors the memory-bucket frontmatter idea — metadata worth adding because something reads it: `visibility` drives the sync, both are validated by the drift check.)

### A public skill may reference a private one — that is fine

Several shipped skills mention a private skill by name (`add-skill`, `curate-knowledge`,
`inject-knowledge` cite `log`; `literature-review` and `write-report` cite
`manuscript-writing-style`). The private skill is not in this release, so the reference does not
resolve here.

**That is intentional, not a broken link.** Those are the maintainer's own
A2MC-*development* skills — the two-stream dev/analysis logging system, the git-tracked
auto-memory bucket, the branch-transfer contract, the manuscript-writing workflow. They are
scoped to developing A2MC itself rather than to calibrating a site, so they are kept out of the
release rather than shipped half-usable.

The reference is left in place deliberately: it tells you the capability exists and what it
covers. **If one would be useful to you, contact Jing Tao (jingtao@lbl.gov)** — they can be
shared on request.

## Current skills

Each skill declares a `modes:` block (see below) so the agent can check it against the active
run configuration (`python tools/describe_mode.py`). Most skills are mode-agnostic (`any`); the
FATES Morris-ensemble analysis skills (`summarize-`/`compare-calibration-rounds`,
`offline-testing-workflow`) are `requires_fates: true` — the gate keeps them out of ELM-only mode.

| Skill | Modes | Triggers when |
|---|---|---|
| [calibration-log](calibration-log/SKILL.md) | any | Log interactive calibration/exploration work for a site (PhaseLogger phase logs + free-form session logs). |
| [a2mc-init](a2mc-init/SKILL.md) | any | First-run setup — interview + create/populate a use case the first time you use A2MC ("set up A2MC", "get started", "configure my site"), then hand off to phase0-design. Distinct from onboard-session (which resumes an existing setup). |
| [onboard-case](onboard-case/SKILL.md) | any | Add a NEW case/site to an already-configured clone — the repeatable half of getting started. Resolves case SCALE first (transect/regional are a HARD STOP: this branch is single-point) |
| [setup-discipline](setup-discipline/SKILL.md) | any | Definition-of-done for a setup stage — is `a2mc-init` / `onboard-case` actually finished, or does it only look finished? A checked box means the check was RUN |
| [onboard-session](onboard-session/SKILL.md) | any | Cold-start runbook — orient at session start or after a compaction/reset ("catch up", "where did we leave off"). |
| [calibration-goal](calibration-goal/SKILL.md) | any | The run-to-convergence DRIVER — conductor above the phase skills; advances the offline 7-phase loop to CONVERGED, pausing only at the human gates ("run the calibration", "drive to convergence"). Harness-neutral (docs/38). |
| [calibration-discipline](calibration-discipline/SKILL.md) | any | The per-cycle/per-round DISCIPLINE checklist (definition-of-done) that keeps a long offline campaign stable — log each phase + self-documenting phase_results, arm monitors after every launch, validate state, per-cycle report, round summary WITH next-round plan. HABITS layer the driver honors; distinct from calibration-goal (loop mechanics). |
| [curate-knowledge](curate-knowledge/SKILL.md) | any | Review + promote staged Tier-3 knowledge proposals (the human-in-the-loop half of the memory write gate). |
| [arm-hpc-monitoring](arm-hpc-monitoring/SKILL.md) | any (HPC) | Session starts (or resumes after compaction) while an HPC ensemble is in flight. |
| [restart-failed-jobs](restart-failed-jobs/SKILL.md) | any (HPC) | Jobs failed in an ensemble/experiment and need restart (or archive if model failure). |
| [diagnose-forensics](diagnose-forensics/SKILL.md) | any | Investigate an anomaly/outlier/too-good "best" case — real or artifact? — then root-cause it. |
| [scientific-analysis](scientific-analysis/SKILL.md) | any | Manuscript-supporting investigation → figure → ana_log (question → data → statistic → figure → evidence). |
| [markdown-to-pdf](markdown-to-pdf/SKILL.md) | any | Convert a markdown ana_log/report/note to a shareable PDF or Word `.docx` via pandoc. Prose, not slide decks (use Marp). |
| [literature-review](literature-review/SKILL.md) | any | Cited literature review via `paper-search-mcp` (search → triage → extract → synthesis). PARAMETER-BOUNDS mode (published value ranges → refine a FATES param list's `lower`/`upper`) or MANUSCRIPT topic review. Validated DOIs, no fabrication. NOT a single-citation lookup. |
| [plotting](plotting/SKILL.md) | any | Clean, readable, overlap-free matplotlib figures — verify by viewing the saved PNG. |
| [write-report](write-report/SKILL.md) | any | Integrated, self-contained report for a zero-context human reader (facts-first, embedded figures, provenance). |
| [build-rag-from-scratch](build-rag-from-scratch/SKILL.md) | any | Construct the RAG/GraphRAG knowledge layer from scratch (for a new model or a fresh build). |
| [rebuild-rag](rebuild-rag/SKILL.md) | any | Rebuild/refresh the RAG/GraphRAG index (wiki bump, curated-YAML graph-only refresh). |
| [generate-codebase-wiki](generate-codebase-wiki/SKILL.md) | any | Generate a source-grounded codebase wiki for a model. |
| [validate-rag-chain](validate-rag-chain/SKILL.md) | any | Validate the RAG chain with the three validators, in order. |
| [inject-knowledge](inject-knowledge/SKILL.md) | any | Inject curated domain knowledge into the KB via the curated-YAML overlay. |
| [port-param-file](port-param-file/SKILL.md) | any | Port a calibrated/tuned param file across model/API versions (e.g. api-31 `.nc` → api-43 `.json`) — remap PFT identity by functional type, transfer overlapping tuned values. Invoke on "port/migrate/convert params to api-XX". |
| [add-skill](add-skill/SKILL.md) | any | Scaffold + register a new skill (frontmatter + ## Changelog + both registries + drift check). |
| [refine-skill](refine-skill/SKILL.md) | any | Refine an existing skill from accumulated evidence, human-gated (propose → approve → apply). |
| [summarize-calibration-round](summarize-calibration-round/SKILL.md) | FATES | One-round summary: ensemble figures + evaluation + Morris μ* sensitivity → markdown/PDF. |
| [compare-calibration-rounds](compare-calibration-rounds/SKILL.md) | FATES | Compare rounds R1…RN + targets (top-N biomass + per-target Morris μ* overlays). |
| [offline-testing-workflow](offline-testing-workflow/SKILL.md) | FATES | Design + launch + analyze an offline HPC parameter-sweep experiment on a Morris base case. |
| [add-fates-parameter](add-fates-parameter/SKILL.md) | FATES | Model-dev: wire a new FATES parameter into EDParamsMod + the parameter file (experiment branch, default-off, V0-at-equality). |
| [model-evolution](model-evolution/SKILL.md) | any | Model-dev umbrella: the workflow for evolving ELM/FATES source (branch, default-off, paired verify, fork-only push). |
| [phase0-design](phase0-design/SKILL.md) | any | Offline Phase 0 — design/sample/submit the ensemble (analog of `_run_design`). |
| [phase1-exploration](phase1-exploration/SKILL.md) | any | Offline Phase 1 — extract Y matrix + Morris sensitivity. |
| [phase2-screening](phase2-screening/SKILL.md) | any | Offline Phase 2 — rank ensemble vs targets; best/most-targets cases. |
| [phase3-diagnosis](phase3-diagnosis/SKILL.md) | any | Offline Phase 3 — root-cause the failing targets (analog of `reasoning.diagnose`). |
| [phase4-hypothesis](phase4-hypothesis/SKILL.md) | any | Offline Phase 4 — hypotheses + skip-test on existing data. |
| [phase5-testing](phase5-testing/SKILL.md) | any | Offline Phase 5 — run HPC experiments (routes to offline-testing-workflow). |
| [phase6-refinement](phase6-refinement/SKILL.md) | any | Offline Phase 6 — evaluate, learn, converge/iterate. |

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
