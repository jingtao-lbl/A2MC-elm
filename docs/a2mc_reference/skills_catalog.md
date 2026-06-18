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

### `log`
- **Purpose:** Write a development or analysis log in the repo's two-stream logging
  system — picks the stream (`memory/dev_logs/` for engineering vs `memory/ana_logs/`
  for scientific analysis) and subtype (regular / session / `Handoff_To_Main`), applies
  the naming + header + required-section conventions, and runs the post-write checklist
  (version bump, changelog, handoff, supersede protocol).
- **Invoke when:** "/log", "write a log", "log this session", "write a dev log / ana_log",
  "session log", "handoff log", "document what we did", or to record a fix/feature/analysis.
- **Modes:** `any` — logging convention; model-agnostic.

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

### `onboard-session`
- **Purpose:** Cold-start runbook — orient at the start of a session or after a context
  reset/compaction (read the latest handoff, re-read CLAUDE.md, check live HPC processes +
  run state, check pending knowledge), delegating to `arm-hpc-monitoring` / `curate-knowledge`.
- **Invoke when:** a session begins/resumes/compacts; "catch up", "where did we leave off", "onboard".
- **Modes:** `any` — model-agnostic. Pairs with the `SessionStart` hook.

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
