# A2MC Skills — Capability Catalog

The **capability catalog** of the A2MC interactive (offline) agent. Each skill is a
folder under [`.claude/skills/`](../../.claude/skills/) containing a `SKILL.md` with
YAML frontmatter (`name`, `description`) and an action-oriented body. A coding-agent
harness auto-discovers them and matches a user request against the `description`
trigger to decide which skill to invoke.

This catalog is the human- and agent-readable index: what each skill does, when to
invoke it, and the repo tools it drives. See [`AGENTS.md`](../../AGENTS.md) for the
operating contract these skills run under.

> **When to invoke a skill:** when a request matches a skill's trigger, invoke the
> skill **before** improvising. Each one encodes conventions (case-naming, dedicated
> experiment directories, reproducibility gates, contamination guards) that are easy
> to get wrong from first principles.

---

## Skills

### `summarize-calibration-round`
- **Purpose:** Produce a one-round calibration summary — whole-ensemble biomass
  graphs (combined long-axis + TRANS), an evaluation report (best case, # targets
  met, per-target biomass vs tolerance bands), and a Morris μ* sensitivity report —
  ending in a markdown + PDF report.
- **Invoke when:** "summarize round N", "make a report for R<N>", "round N
  summary/report", "how did R<N> do", or any request for the combined+TRANS ensemble
  figures plus evaluation+sensitivity for a **single** round.
- **Backing tools:** `tools/plot_ensemble_cases.py`, the slim spinup extractor, the
  Morris μ* sensitivity pipeline; markdown→PDF rendering.
- **Note:** per-round figures stay uncapped (re-running your own round is fine);
  screening evaluation caps foreign experiment cases.

### `compare-calibration-rounds`
- **Purpose:** Compare calibration rounds (R1, R2, …) against each other and the
  validation targets — top-N best-achievable biomass per round, per-target Morris
  μ* sensitivity overlays, P-pool / cross-regime overlays.
- **Invoke when:** "compare rounds", "update the multi-round figure", "refresh the
  R1–RN comparison", "which round is best", "top sensitive parameters per round", or
  to regenerate any `multiround_*` / cross-round figure after new cases complete.
- **Backing tools:** the multi-round comparison bundle over `tools/plot_ensemble_cases.py`
  and the sensitivity pipeline.
- **Note:** codifies the footguns — screening contamination guard (use the cap for
  cross-round screening), case-name patterns, μ* ranking, param-set mismatch,
  partial-ensemble caveats.

### `offline-testing-workflow`
- **Purpose:** Design + launch + analyze an offline HPC experiment — a parameter
  sweep of N variants on top of a Morris base case — with a V0 reproducibility gate
  and a decision tree feeding results back into the knowledge base.
- **Invoke when:** the user wants to "test the X hypothesis", "parameter sweep",
  "verify the X mechanism", or run a "Phase 4/5" experiment (e.g. clumping_index
  sweep, vmax_p sensitivity, hydraulic-vulnerability probe). **Invoke before writing
  any such plan.**
- **Backing tools:** `tools/create_case.sh --case-suffix`,
  `tools/modify_fates_parameters.py` (verify-modifications gate),
  `tools/validate_submission_plan.py`, `tools/extract_and_plot_selected_cases.py`
  (extract / v0check / plot).
- **Critical preconditions:** grep `memory/dev_logs/` **and** `memory/ana_logs/` for
  prior plans/analysis on the same topic first; follow the case-suffix naming
  convention (never invent out-of-range
  case numbers); use dedicated param/case/output/extract dirs; verify param-file
  modifications before submitting; V0 reproducibility check before trusting V1+.

### `restart-failed-jobs`
- **Purpose:** Restart SLURM jobs that failed in an ensemble or experiment,
  distinguishing **infrastructure** failures (restart-eligible) from **model**
  failures (not restart-eligible without a parameter/model fix).
- **Invoke when:** failures appear mid-run (NODE_FAIL, PartitionDown, SIGKILL
  clusters) or at end-of-run (runaway recruitment, FATES mass-balance, PARTEH abort).
- **Backing tools:** `tools/diagnose_ensemble_status.py` (quiescent ensemble) or the
  `sacct`-based TSV pathway (in-flight ensemble); restart submission via the Phase 0
  submitter with a cases-file.
- **Note:** generates an audit TSV + flat case-list and handles zombie cleanup.

### `arm-hpc-monitoring`
- **Purpose:** Set up real-time monitoring of an active ensemble/experiment at
  session start — detect live long-running processes, arm monitors on each
  long-running log with the right event + error filters (silence ≠ success), and
  react to events with proposals, not just relays.
- **Invoke when:** a session begins (or resumes after a context reset) while an
  ensemble round is in flight, or immediately after launching a new submitter/restart
  job.
- **Backing tools:** the config-driven ensemble auto-monitor + milestone-plot
  regeneration; the harness's process listing and log-monitoring facilities.

### `log`
- **Purpose:** Write a log in the repo's **two-stream logging system** — engineering
  `memory/dev_logs/` vs scientific `memory/ana_logs/` — picking the right subtype
  (regular dev log, **session log**, or **Handoff_To_Main**), applying the naming +
  header + required-section conventions, and running the post-write checklist.
- **Invoke when:** "/log", "write a log", "log this session", "write a dev log / ana
  log", "session log", "handoff log", "document what we did", or to record a
  fix/feature/analysis.
- **Backing references:** `memory/dev_logs/CLAUDE.md` (authoritative style spec),
  `memory/a2mc_development_history.md` (changelog target for code-change version bumps).
- **Key steps:** classify stream+subtype → resolve header (date-letter,
  author-by-environment, type, version, branch) → draft with required sections + cite
  explicit evidence → post-write (version bump + changelog for code; Handoff_To_Main for
  generic; supersede-don't-edit for corrections).

### `curate-knowledge`
- **Purpose:** The human-in-the-loop half of the Tier-3 memory write gate. The
  autonomous online agent stages `auto_learn` proposals to
  `auto_discovered_pending.json`; this skill reviews each against evidence and promotes
  the vetted ones into the curated KB (or discards misunderstandings).
- **Invoke when:** "review/curate/promote pending knowledge", "what did the runs propose
  to learn", "check `auto_discovered_pending`", or at session start when staged
  proposals exist.
- **Backing tool:** `tools/review_pending_knowledge.py` (`list`/`promote`/`discard`).
- **Key discipline:** cross-check every proposal (real+reproduced? mechanism fits the
  data + FATES? duplicate? is each `do_not_repeat` a true dead end?); never
  `promote --all` blind; record what was promoted/discarded. Closes the loop the write
  gate (`20260612d`) opens; guards against the May contamination class (`20260519a`).

### `onboard-session`
- **Purpose:** The cold-start runbook for the interactive agent — orient at the start of
  a session, on resume, or after compaction. Restores context (re-read CLAUDE.md, read
  the latest handoff, verify branch), checks for in-flight HPC work (live processes, run
  state), and delegates to `arm-hpc-monitoring` / `curate-knowledge` as needed.
- **Invoke when:** a session begins/resumes/compacts (especially if the SessionStart
  snapshot shows in-flight work or pending proposals), or "catch up", "where did we leave
  off", "onboard", "what's the current state".
- **Pairs with:** the G2 `SessionStart` hook (`.claude/hooks/session-start.py`) — the hook
  surfaces the snapshot, this skill acts on it. References CLAUDE.md Rule 6 +
  `memory/dev_logs/20260514c_*` (monitoring reactions).
- **Key discipline:** summarize + **propose next actions**, don't just relay; re-derive
  run-state from live `squeue` + disk, not stale logs.

### `diagnose-forensics`
- **Purpose:** Investigate a suspicious ensemble result — outlier, too-good "best" case,
  failure cluster, a target that won't move — by triaging for **artifacts first**
  (contamination / experiment-leak, infra-timing failures, mislabeled partial-ensemble
  index, NaN, stale run-state), then root-causing with the `phases/phase3_diagnosis/`
  tools only if it survives triage.
- **Invoke when:** "is this real or contamination", "why is case X an outlier",
  "investigate this anomaly / failure cluster", "edge-case / collapse detection", "root
  cause of this PFT not calibrating".
- **Backing tools:** `phases/phase3_diagnosis/*` (read/compare params, edge params,
  targets, collapse, PFT limitations, C/mortality/nutrient mechanism).
- **Key discipline:** **triage → root-cause → write-up**, in that order — reading a
  pattern as science before triage is how the #100317 contamination episodes happened
  (`20260610g`). Fix-and-supersede if it's a tooling/data bug.

### `scientific-analysis`
- **Purpose:** A manuscript-supporting investigation that ends in a figure + an `ana_log`
  — pose a falsifiable question, scope + pull the data, compute the statistic/mechanism,
  make a figure (filename convention), cite evidence, write the ana_log, optionally land
  a vetted lesson.
- **Invoke when:** "investigate whether X", "is X correlated with Y", "analyze the
  mechanism of X", "make a manuscript figure", P-pool / cross-regime / attribution work.
  (For the canned single-round report use `summarize-calibration-round`; for cross-round
  figures use `compare-calibration-rounds`.)
- **Backing tools:** `use_cases/Kougarok/analysis/*`, `tools/plot_ensemble_cases.py`, the
  `/log` skill (ana_log + cite-evidence), `markdown-to-pdf`, `curate-knowledge`.
- **Key discipline:** every quantitative claim names its figure/statistic/data file
  inline; figure filenames embed round + axis-mode + count (gitignored → the name is the
  only pointer).

---

## Knowledge-base build pipeline

These skills mirror the documented adapter-kit pipeline (Steps 1→4 in
`docs/a2mc_reference/`): **`generate-codebase-wiki`** (step 1) → **`rebuild-rag`**
(step 2) → **`inject-knowledge`** (step 3, curated YAML + memory channels) →
**`validate-rag-chain`** (step 4). **`build-rag-from-scratch`** is the **orchestrator** over
the set — it constructs the whole layer from nothing (new model, or full reproducibility
reconstruction) by sequencing the four. They maintain the FATES knowledge layer the
calibration agent reasons over, as opposed to the runtime skills above which drive the
calibration loop itself.

### `build-rag-from-scratch`
- **Purpose:** Construct the entire RAG/GraphRAG knowledge layer when the index **and/or its
  inputs** don't exist yet — the **constructive orchestrator** counterpart to `rebuild-rag`
  (which reindexes existing inputs). Two paths: **R** = reconstruct an existing model's layer
  from source (api-31-0 reproducibility / disaster recovery); **N** = bootstrap a new model
  (EcoSim, ReSOM — Recipe 2 Path A, 12 steps).
- **Invoke when:** "build the RAG/GraphRAG from scratch", "set up RAG for a new model", "add
  EcoSim/ReSOM to A2MC", "reconstruct the whole knowledge layer", "bootstrap the knowledge
  base from nothing".
- **Sequences:** `generate-codebase-wiki` (wiki) → the `rebuild-rag` build mechanics
  (`build_rag_index.py`) → `inject-knowledge`/curated-YAML authoring → `validate-rag-chain`;
  owns the glue (loader registration, per-model parsers, separate persist dirs, milestone
  registration).
- **Key discipline:** the **Step V gate** proves the *graph* built, not just the vector index
  — `get_stats` (nonzero nodes/edges, typed `controls`/`affects`/`related_to` edges) **and**
  `find_parameters_for_output(...)` returns a non-empty list (vector docs > 0 is necessary but
  not sufficient; a YAML/CDL parse failure yields a vector-only half-build). New-model parsers
  + curated YAML are days of work, not a one-command build.

### `generate-codebase-wiki`
- **Purpose:** Produce a source-grounded codebase wiki for a model (FATES, ELM, EcoSim, …)
  by fanning out parallel subagents that read actual source and cite `(file:line)` — the
  foundation every downstream artifact (vector index, knowledge graph, calibration prompts)
  is built on.
- **Invoke when:** "generate/build a codebase wiki", "the deepwiki/cursor wiki is wrong —
  rewrite it", "audit the wiki against source", "bump the wiki to commit X", "add model Y
  to A2MC" (wiki is step 1).
- **Backing roadmap:** `codebase_wiki_generation_roadmap.md` (Workflow A greenfield /
  Workflow B audit+rewrite; Recipes A1/A2/B1/B2/B3).
- **Key discipline:** A-vs-B by semantic-vs-structural error; pilot 2 before full dispatch;
  mandatory `(file:line)` + grep verification, spot-check 3–5 claims; commit-pinned output
  dir + `Source pin` header; abandon (don't patch) a fabricated deepwiki.

### `rebuild-rag`
- **Purpose:** Rebuild or repair the RAG/GraphRAG index (ChromaDB vector store + NetworkX
  graph) that the `ReasoningModule` queries before every Claude API call.
- **Invoke when:** "rebuild the RAG / reindex", "bump the wiki to a new commit", "I edited
  the curated YAML — refresh the graph", "add a model to the RAG", "the index stopped
  working / returns stale content", or after any wiki / CDL / `curated_relationships.yaml`
  edit.
- **Backing tool + roadmap:** `scripts/build_rag_index.py`; `rag_build_roadmap.md`
  (Recipe 1 wiki bump, Recipe 2 new model, decision tree).
- **Key discipline:** the loader pattern-probe stops at first match → a wiki bump silently
  keeps the legacy tree unless you symlink (the #1 footgun); always `--rebuild` (dedup-by-id
  skips content changes), `--graph-only` for YAML-only edits; Python 3.10; verify stats
  (~2,700 docs / ~1,299 nodes) + spot-check 4 claims.

### `inject-knowledge`
- **Purpose:** Inject a **human-originated** domain fact (a discovery, a parameter insight, a
  mechanism/relationship) into the curated KB so the calibration agent surfaces it — placing
  it correctly across the up-to-three channels and rebuilding the graph. Judgment-scaffolding,
  **not** automation: the human owns the truth call; the skill enforces correct placement +
  gates. The human-originated counterpart to `curate-knowledge` (run-originated proposals).
- **Invoke when:** "add this finding/parameter knowledge to A2MC's AI", "inject the X
  discovery into the KB", "make the agent aware of X", "author a curated relationship for X",
  or to land a manuscript/literature insight in the reasoning pipeline.
- **Channels + triggers:** site `discoveries.json` (→ `MemoryManager.get_relevant_context`
  by `affects`/`failing_targets`); generic `parameters.json` (→ `ReasoningModule.query` when
  the param is in scope); `rag/data/curated_relationships.yaml` (→ ChromaDB + graph after a
  rebuild). Not every fact needs all three; an applicable channel missed = a trigger path
  that never surfaces it.
- **Key discipline:** clear the Step-0 truth call first (evidence-backed, not a guess; not a
  duplicate; scrutinize `do_not_repeat`; `verified:false` by default); `related_to` isn't
  auto-bidirectional; a YAML endpoint absent from the param/output file is a **silently
  dropped edge**; validate JSON/YAML + memory smoke test, then `--graph-only` rebuild
  (`rebuild-rag`) + `validate-rag-chain` Step 2. Worked example: `20260519d` (clumping_index).

### `validate-rag-chain`
- **Purpose:** Validate the `source → wiki → curated YAML → RAG` chain before shipping,
  with the three validators in dependency order.
- **Invoke when:** "validate the wiki/RAG", "check the wiki against source", "did the
  rebuild regress", "check for hallucinations before merging the wiki", or after generating
  a wiki / editing the YAML / rebuilding at a new commit.
- **Backing tools + roadmap:** `tools/codebase_wiki_validator.py` →
  `tools/yaml_wiki_validator.py` → `tools/rag_diff.py`; `rag_validation_workflow.md`.
- **Key discipline:** run in dependency order, fix any Red before the next tier (a Step-2
  "BOTH found" is meaningless on a hallucinated Step-1 claim); Green/Yellow/Red banding;
  triage real-fabrication vs validator-false-positive vs by-design vs renamed.

---

## Skill management (meta)

These two meta-skills are the skill-evolution machinery — they operate on the skill set
itself rather than on a calibration subsystem. Adapted from the E2SA skill-evolution design
(`End2EndScienceAgent/docs/design/09_skill_evolution.md`); backed by the mechanical drift
gate `tools/check_skill_registry.py` (disk ↔ README table ↔ this catalog parity).

### `add-skill`
- **Purpose:** Scaffold a new skill **and** register it so the steps are never half-done.
  Writes the `SKILL.md` (frontmatter + body + seeded `## Changelog`), registers it in **both**
  human-facing registries (the README "Current skills" table and this catalog), runs the
  drift check, and stops for human review before commit.
- **Invoke when:** "add a skill", "create/scaffold a skill", "make this reusable as a skill",
  "distill X into a skill".
- **Backing tool:** `tools/check_skill_registry.py` (the register-in-both invariant, enforced).
- **Key discipline:** register in BOTH registries or it drifts; minimal procedure (a one-off
  isn't a skill); branch-scoped (don't bake `main`/api-43-1 into a `kougarok_fates_demo`
  skill); public-sync aware (no secrets); human-gated.

### `refine-skill`
- **Purpose:** Improve an existing skill from accumulated signal — the distill → propose →
  gate → apply half of skill evolution. Gathers evidence (dev_logs, ana_logs, verify-pass
  findings, corrections), proposes a concrete `SKILL.md` diff, **stops at a human gate (never
  self-applies)**, then on approval edits + appends a `## Changelog` line + commits.
- **Invoke when:** "refine/improve the X skill", "the X skill should have caught Y", "review
  the skills".
- **Key discipline:** refine on a *repeated* signal (≥ ~2–3 / explicit correction / failure
  pattern), not one-offs; surgical edits only (a growing skill is a smell); **`description`
  /trigger edits are highest-risk**; evidence-cited; never self-apply (contract change, like
  `curate-knowledge` / `inject-knowledge`).

---

## Skills vs dev logs

| | Skill (`.claude/skills/`) | Dev log (`memory/dev_logs/`) |
|---|---|---|
| **Form** | Reusable procedure, invoked by trigger match | Dated record of one change/investigation |
| **Tense** | Imperative ("do X, then Y") | Past ("changed X because Y") |
| **Reused?** | Yes — every matching request | No — read once for context |

A skill captures *how to do a recurring task*; a dev log captures *what was done and
why* on a specific date. New skills are often distilled from repeated patterns first
recorded across several dev logs.
