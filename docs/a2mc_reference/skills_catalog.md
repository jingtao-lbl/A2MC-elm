# A2MC Skills — Capability Catalog

The **capability catalog** of the A2MC interactive (offline) agent. Each skill is a
folder under [`.claude/skills/`](../../.claude/skills/) containing a `SKILL.md` with
YAML frontmatter (`name`, `description`, `modes`) and an action-oriented body. A
coding-agent harness auto-discovers them and matches a user request against the
`description` trigger to decide which skill to invoke.

This catalog is the human- and agent-readable index: what each skill does, when to
invoke it, **which run configurations it applies to**, and the repo tools it drives.
See [`AGENTS.md`](../../AGENTS.md) for the operating contract these skills run under.

> **Mode-aware:** A2MC runs many configurations (ELM with or without FATES, different
> FATES API milestones, ECA vs RD nutrient schemes). Each skill declares a `modes:`
> block; before mode-specific steps, resolve the active configuration with
> `python tools/describe_mode.py` and honor the skill's applicability — skip or branch
> when the case's mode does not satisfy it.

> **When to invoke a skill:** when a request matches a skill's trigger **and** the active
> mode satisfies its `modes:` block, invoke the skill **before** improvising. Each one
> encodes conventions (case-naming, dedicated experiment directories, reproducibility
> gates, contamination guards) that are easy to get wrong from first principles.

---

## Skills (mode-agnostic — available now)



### `calibration-log`
- **Purpose:** Log interactive calibration/exploration work for a site under
  `use_cases/{site}/memory/logs/` — a PHASE log via `tools/phase_logger.py` (identical to the
  autonomous agent) or a free-form SESSION log, so both modes' logs synthesize together.
- **Invoke when:** "log this / this phase / this diagnosis / this experiment", "log this calibration session", "write a session log", "record what I explored".
- **Modes:** `any` — model-agnostic (PhaseLogger).

### `restart-failed-jobs`
- **Purpose:** Restart SLURM jobs that failed in an ensemble/experiment. Diagnoses failure
  mode first (infrastructure → restart-eligible vs model failure → archive), handles
  two-wave zombie cleanup, generates an audit TSV + flat case-list, and submits the
  restart via `phases/phase0_design/submit_phase0.py --cases-file`.
- **Invoke when:** failures appear mid-run (NODE_FAIL, PartitionDown, SIGKILL clusters) or
  at end-of-run; "restart the failed jobs", "which failures are restart-eligible".
- **Modes:** `any` (HPC) — the SLURM restart workflow is model-agnostic. The model-failure
  fingerprints in Step 2 are FATES examples; a different model has different abort signatures.
- **Backing tools:** `tools/diagnose_ensemble_status.py`, `tools/validate_restart_script.py`,
  `phases/phase0_design/submit_phase0.py`.

### `arm-hpc-monitoring`
- **Purpose:** At session start (or after compaction), detect live long-running login-node
  processes and arm Claude `Monitor` tasks on each long-running log with the right event +
  error filters (silence ≠ success), reacting with proposals rather than just relaying.
- **Invoke when:** a session begins/resumes while an ensemble round is in flight, or right
  after launching a new submitter/restart job.
- **Modes:** `any` (HPC) — monitors any in-flight A2MC ensemble/experiment; model-agnostic.

### `a2mc-init`
- **Purpose:** First-run setup for the offline agent — the official "getting started" flow the
  first time A2MC is used in a repo/site. Interviews the user (checkout path, FATES on/off,
  carbon-only vs nutrient-enabled PARTEH, ECA/RD, site + PFTs + targets), verifies the checkout
  against the RAG milestone registry (`rag_match.py`), creates + populates the use case (site
  config + `targets.yaml` + parameter list), validates (`describe_mode.py`,
  `validate_targets_config.py`), and hands off to `phase0-design`.
- **Invoke when:** "set up A2MC", "first time using A2MC", "help me get started / onboard me to
  A2MC", "initialize a new site / use case", "configure A2MC for my site", "calibrate a new site".
- **Modes:** `any` — model-agnostic; resolves FATES/nutrient mode from the interview. **Distinct
  from `onboard-session`**, which resumes an already-configured setup.

### `onboard-session`
- **Purpose:** Cold-start runbook — orient at the start of a session or after a context
  reset/compaction (read the latest handoff, re-read CLAUDE.md, check live HPC processes +
  run state, check pending knowledge), delegating to `arm-hpc-monitoring` / `curate-knowledge`.
- **Invoke when:** a session begins/resumes/compacts; "catch up", "where did we leave off", "onboard".
- **Modes:** `any` — model-agnostic. Pairs with the `SessionStart` hook. For a **first-run** (no
  config yet), use `a2mc-init` instead.

### `curate-knowledge`
- **Purpose:** Review + promote staged Tier-3 knowledge proposals — the human-in-the-loop half
  of the memory write gate. Lists `auto_discovered_pending.json`, evaluates each against
  evidence, promotes vetted ones / discards misunderstandings (`tools/review_pending_knowledge.py`).
- **Invoke when:** "review/curate pending knowledge", "promote proposals", or at session start when staged proposals exist.
- **Modes:** `any` — model-agnostic. The interactive agent's job by design (curated writes are interactive-only).

### `diagnose-forensics`
- **Purpose:** Investigate an anomaly (outlier, too-good "best" case, failure cluster, stuck
  target) — determine FIRST whether it is real or an artifact (contamination, infra-timing,
  mislabeled index, NaN), then root-cause it with the phase-3 diagnosis tools.
- **Invoke when:** "why is case X an outlier", "is this real or contamination", "investigate this anomaly".
- **Modes:** `any` — workflow is model-agnostic; the worked examples are FATES/Morris.

### `scientific-analysis`
- **Purpose:** A manuscript-supporting investigation that ends in a figure + an ana_log:
  pose a question → pull run data → compute the statistic/mechanism → make a figure → cite
  evidence → write an ana_log.
- **Invoke when:** "investigate whether X", "is X correlated with Y", "analyze the mechanism", "make a manuscript figure for X".
- **Modes:** `any` — model-agnostic; examples are FATES/Kougarok.

### `markdown-to-pdf`
- **Purpose:** Convert a markdown document (an ana_log, report, or note) to a shareable PDF
  or Word `.docx` via pandoc (+ a LaTeX engine for PDF; python-docx for round-trip-safe docx).
  Prose only — slide decks go through Marp. Self-contained repo copy (no user-level dependency).
- **Invoke when:** "convert/render markdown to PDF/Word/docx", "render this ana_log/report to PDF", "make a PDF of this", "turn this .md into a docx".
- **Modes:** `any` — model-agnostic.

### `build-rag-from-scratch`
- **Purpose:** Construct the RAG/GraphRAG knowledge layer from scratch (new model or fresh build).
- **Invoke when:** "build the RAG from scratch", "stand up RAG for <model>".
- **Modes:** `any` — model-agnostic. See `docs/a2mc_reference/rag_build_roadmap.md`.

### `rebuild-rag`
- **Purpose:** Rebuild/refresh the RAG/GraphRAG index (wiki bump, or a `--graph-only` refresh after a curated-YAML injection).
- **Invoke when:** "rebuild/refresh the RAG", "the index is stale".
- **Modes:** `any` — model-agnostic.

### `generate-codebase-wiki`
- **Purpose:** Generate a source-grounded codebase wiki for a model (the substrate the RAG indexes).
- **Invoke when:** "generate the codebase wiki", "make a wiki for <model>".
- **Modes:** `any` — model-agnostic. See `docs/a2mc_reference/codebase_wiki_generation_roadmap.md`.

### `validate-rag-chain`
- **Purpose:** Validate the RAG chain with the three validators, in order, before shipping.
- **Invoke when:** "validate the RAG", "is the RAG chain sound".
- **Modes:** `any` — model-agnostic. See `docs/a2mc_reference/rag_validation_workflow.md`.

### `inject-knowledge`
- **Purpose:** Inject curated domain knowledge into the KB via the curated-YAML overlay (additive, evidence-backed).
- **Invoke when:** "inject this knowledge", "add a curated relationship".
- **Modes:** `any` — model-agnostic. See `docs/a2mc_reference/graphrag_curated_yaml_roadmap.md`.

### `add-skill`
- **Purpose:** Scaffold + register a new skill (correct frontmatter + `## Changelog`, both
  registries, the drift check), stopping for human review before commit.
- **Invoke when:** "add a skill", "scaffold a skill", "make this reusable as a skill".
- **Modes:** `any` — meta machinery, model-agnostic.

### `refine-skill`
- **Purpose:** Refine an existing skill from accumulated evidence, human-gated — gather signal,
  propose a SKILL.md diff with cited evidence, STOP for approval, then apply + append a `## Changelog` line.
- **Invoke when:** "refine the X skill", "the X skill should have caught Y", "review the skills".
- **Modes:** `any` — meta machinery, model-agnostic.

---

## FATES Morris-ensemble analysis (`requires_fates: true`)

These consume the mode-aware machinery (the case `targets.yaml`, api-aware parameter-file
handling, ECA/RD pathway) but assume a FATES Morris-ensemble calibration (PFT/SZPF outputs,
ADSP/RGSP/TRANS spinup, Morris μ*). The `modes:` gate keeps them out of ELM-only mode.

### `summarize-calibration-round`
- **Purpose:** One-round summary — whole-ensemble figures + an evaluation report (best case,
  targets met vs tolerance) + a Morris μ* sensitivity report → markdown/PDF. Targets from the
  case `targets.yaml`.
- **Invoke when:** "summarize round N", "report for R<N>", "how did R<N> do".
- **Modes:** `requires_fates: true` — FATES PFT/SZPF figures + a Morris ensemble.

### `compare-calibration-rounds`
- **Purpose:** Compare rounds R1…RN against each other + the validation targets — top-N biomass
  overlay, per-target Morris μ* overlay; refresh a multi-round figure.
- **Invoke when:** "compare rounds", "which round is best", "refresh the multi-round figure".
- **Modes:** `requires_fates: true`.

### `offline-testing-workflow`
- **Purpose:** Design + launch + analyze an offline HPC parameter-sweep experiment on a Morris
  base case — variant matrix, V0 reproducibility gate, dedicated output dirs (config-var paths),
  decision tree → KB injection.
- **Invoke when:** "test the X hypothesis", "parameter sweep", "<param> sensitivity experiment".
- **Modes:** `requires_fates: true` — FATES parameter files + HPC submission.

## Offline phase skills (per-phase, mirror online Phase 0–6)

### `phase0-design`
- **Purpose:** Offline analog of online Phase 0 — sample the parameter space, materialize per-case FATES param files, generate + build + submit the ensemble, arm monitoring.
- **Invoke when:** "design a new round", "submit the ensemble", "sample the parameters", "expand/redesign the parameter space".
- **Modes:** `any` — calibration-workflow phase skill (mode resolved at runtime).

### `phase1-exploration`
- **Purpose:** Offline analog of Phase 1 — extract the Y matrix, run Morris sensitivity, interpret μ*.
- **Invoke when:** "run the sensitivity analysis", "which parameters matter", "run Phase 1".
- **Modes:** `any`.

### `phase2-screening`
- **Purpose:** Offline analog of Phase 2 — rank the ensemble vs targets, find best/most-targets cases, read bias patterns, route to Phase 3.
- **Invoke when:** "screen the ensemble", "which case is best", "how many targets met", "run Phase 2".
- **Modes:** `any`.

### `phase3-diagnosis`
- **Purpose:** Offline analog of Phase 3 (`reasoning.diagnose`) — root-cause the failing targets via the phase3 tools + RAG + Adaptive Memory → structured diagnosis; hand off to Phase 4.
- **Invoke when:** "diagnose the failing targets", "why aren't the targets calibrating", "run Phase 3".
- **Modes:** `any`.

### `phase4-hypothesis`
- **Purpose:** Offline analog of Phase 4 — turn a diagnosis into testable hypotheses + skip-test against existing Morris data (3↔4, no HPC); route to Phase 5 if new sims needed.
- **Invoke when:** "generate a hypothesis", "what should we test next", "can we test with existing data", "run Phase 4".
- **Modes:** `any`.

### `phase5-testing`
- **Purpose:** Offline analog of Phase 5 — thin router to `offline-testing-workflow` for HPC experiment execution.
- **Invoke when:** "run the experiment", "submit the test cases", "run Phase 5".
- **Modes:** `any`.

### `phase6-refinement`
- **Purpose:** Offline analog of Phase 6 — evaluate results vs baseline/expected, extract lessons, update Adaptive Memory, decide converge / rethink (6→3) / redesign (6→0).
- **Invoke when:** "evaluate the results", "what did we learn", "converge or iterate", "run Phase 6".
- **Modes:** `any`.
