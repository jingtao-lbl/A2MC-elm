# Codebase Wiki Generation Roadmap

**Audience:** users adapting A2MC to a new model (the "adapter kit" workflow), or A2MC maintainers refreshing an existing model wiki at a new commit.

**Status:** workflow proven on existing models so far (ELM, FATES, EcoSIM, BeTR, ReSOM, etc.) and extended to the FATES e85d997 → e027a40 + ELM 60d9aad → d40b8431 paired regens.

**Companion doc:** `rag_build_roadmap.md` — what to do AFTER the wiki exists. This roadmap covers **Step 1**: producing the source-grounded codebase wiki itself.

---

## Why a wiki at all

A2MC's reasoning agents ground every claim against a knowledge graph + vector index built from the wiki. If the wiki contains fabricated parameter names, wrong defaults, or stale line numbers, the AI confidently retrieves and propagates those errors into calibration recommendations. The four-version FATES + ELM + EcoSIM regen series happened because three independently-generated wikis (Feb 2026 FATES, original ELM-codebase-wiki, deepwiki EcoSIM) each contained the same class of errors: fabricated routine names, wrong line ranges, references to source files that don't exist.

**For an adapter-kit user, the wiki IS the model knowledge.** Skipping this step or shortcutting it produces a calibration framework that confidently calibrates the wrong model. There is no useful A2MC instance without a defensible wiki.

A defensible wiki at a pinned commit:

1. Documents the actual source code that the user will run.
2. Carries `(path/Module.F90:NNN)` citations on every substantive claim.
3. Is regenerable when the model bumps (Workflow B below).

Anything less and the version-association infrastructure (`docs/18_ELM_FATES_Version_Association_Plan.md`) has nothing to anchor to.

---

## Two workflows

### Workflow A — Greenfield (no prior wiki, or prior wiki is being abandoned)

Use this when:
- The model has no source-grounded wiki at all (e.g., you just downloaded a fresh model).
- An existing auto-generated wiki (deepwiki, cursor-generated, etc.) is structurally broken — fabricated routines or paths, wrong scope.
- You're starting an adapter-kit run for a model A2MC has never targeted.

**Examples in this repo:**
- `memory/dev_logs/20260410e_ELM_Wiki_vs_60d9aad_Rewrite.md` — original ELM wiki, 41 files at commit 60d9aad
- `memory/dev_logs/20260424g_EcoSIM_Codebase_Wiki_Rewrite.md` — EcoSIM wiki, 41 files at commit 2dea74d9

### Workflow B — Audit + rewrite (existing source-grounded wiki at one commit, regen at a newer commit)

Use this when:
- You already have a defensible wiki at commit X.
- The model has bumped to commit Y and you want a wiki at Y.
- You want to know what drifted between X and Y.

**Examples in this repo:**
- `memory/dev_logs/20260410d_FATES_Wiki_vs_e85d997_Audit.md` — FATES original → e85d997
- `memory/dev_logs_fatesversionassociation/fates_wiki_audit_e027a40/` — FATES e85d997 → e027a40 (api-31-0 → api-43-1)
- `memory/dev_logs_fatesversionassociation/elm_wiki_audit_d40b843/` — ELM 60d9aad → d40b8431

---

## Cross-cutting prerequisites

Both workflows need these before dispatching any subagents.

### 1. Define model boundary

Decide what counts as "the model" for wiki purposes. Get this wrong and the wiki documents the wrong scope.

| Boundary question | Example answers |
|---|---|
| Is this a standalone model or coupled to a host? | FATES is coupled (under ELM); ELM is host but separately wikified; EcoSIM is largely standalone |
| Where does the source live in the file tree? | FATES: `components/elm/src/external_models/fates/`; ELM: `components/elm/src/`; EcoSIM: `f90src/` + `drivers/` |
| What's excluded? | Submodules of submodules; build helpers (`*.F90.in`, `*.pl`, `Makefile`); auto-generated code; obsolete branches |

Record the decision explicitly in the wiki's root `index.md` "Scope" section so a future reader knows why a particular module isn't documented.

### 2. Pin the source commit

Always work against an exact commit. Tags are convenient but read the actual `git rev-parse HEAD` and use it. Reasons:

- Line numbers in citations only resolve at one commit; tag drift can break them retroactively.
- The version-association layer keys milestones on commit hashes, not tags.
- Workflow B requires comparing two commits — both need precise SHAs.

```bash
git -C /path/to/model rev-parse HEAD          # short-SHA goes in filenames + headers
git -C /path/to/model describe --tags --long  # human-readable provenance
```

### 3. Topic decomposition

Split the model into 5–10 audit/rewrite topics. Each topic becomes one parallel subagent. Heuristics:

- **Source-tree subdirectories** are the natural starting point (e.g., FATES has `biogeochem/`, `biogeophys/`, `parteh/`, `fire/`, `main/`, `radiation/`).
- **Scientific domain boundaries** are second-best (e.g., FATES topic 06 "PARTEH" maps to a subfolder of `plant-physiology/`).
- **Try to make topics independently auditable**: a subagent reading topic N's source should not need to grep topic M's source to verify topic N's claims. If two topics share a critical dependency, document that explicitly in both topics' prompts.
- **Calibration-critical content gets its own topic** (e.g., FATES 10 "advanced/cnp_calibration_guide"). Smaller scope = better focus.

| Model | Topics | Total .md files |
|---|---|---|
| FATES at e027a40 | 10 (overview, architecture, core dynamics, canopy, plant physiology, parteh, biophysics, fire, output, advanced) | 55 + index |
| ELM at d40b8431 | 6 (biogeochem, biogeophys, core, dyn_subgrid, overview, reference) | 41 + index |
| EcoSIM at 2dea74d9 | ~10 (drivers, core, hydrotherm, microbial_bgc, plant_bgc, geochem, transport, etc.) | 41 |

If you don't have a strong prior, **start with subdirectory-aligned topics**. Topics can be split or merged after the audit (Workflow B) reveals where drift is concentrated.

### 4. Stage parameter / config files

If the model has a parameter file, extract a structured representation (CDL for NetCDF/CDL formats; raw JSON for JSON formats; YAML/INI for text-based formats) and stage it under `docs/<model>-knowledge-base/`:

```
docs/<model>-knowledge-base/<model>_params_info_<commit>.{cdl|json|yaml}
docs/<model>-knowledge-base/<model>_output_info_<commit>.cdl    # if applicable
```

The parameter file is the canonical truth-source for parameter names and defaults; subagents will cross-check against it. If your model doesn't have a parameter file, skip this step.

**FATES example:** `docs/fates-knowledge-base/fates_params_info_e027a40.json` (98 KB, 14 PFTs, structured `{attributes, dimensions, parameters}`).

---

## Universal subagent context

Both workflows dispatch subagents whose output quality depends heavily on a "universal context" block injected at the top of every prompt. This block lists model-wide facts that every topic's rewrite must respect. Without it, subagents independently hallucinate or carry forward wrong content.

### What goes in the universal context block

- **Pinned commit + tag/describe string** — every subagent embeds this in source-pin headers
- **High-level scope statement** — what's in/out of the wiki
- **Known global drifts** (Workflow B only) — for example, "PFT count went from 12 to 14, including two new Arctic shrubs"
- **Known structural changes** — file format changes (CDL → JSON), API/coupling boundary changes, removed/renamed top-level modules
- **Citation conventions** — `(path/from/model/root.F90:NNN)` format
- **Output path conventions**

### Worked example (FATES e85d997 → e027a40)

The universal context block injected into every FATES rewrite subagent for the api-31 → api-43 jump:

```text
- 14 PFTs (was 12). New Arctic shrubs at positions 10-11; arctic_c3_grass shifted to position 12.
- JSON parameter format (was CDL). Loader: JSONRead + FatesTransferParameters.
- Default fates_cnp_prescribed_n/puptake = 0.0 (was 1.0; default is now coupled).
- nclmax = 3 (was 2).
- PID gate moved to (coupled_*_uptake .and. .not. hlm_*_suppl).
- Phenology two-flag system collapsed into integer fates_phen_leaf_habit (1-4).
- ...
```

These bullets distilled from the audit phase, prevent every rewrite subagent from independently rediscovering them.

---

## Workflow A: Greenfield generation

Use when there's no defensible prior wiki to compare against.

### Steps

#### A.1 — Stage source

```bash
# Clone (or symlink to existing checkout)
git clone <model-repo> /path/to/<model>_source
cd /path/to/<model>_source
git checkout <target_commit>
git rev-parse HEAD               # save short-SHA as <model>_<sha>
git describe --tags --long       # save as fallback metadata
```

The source must NOT be modified during wiki generation. If you need to apply patches, do so before the wiki regen and document the patches in scope.

#### A.2 — Topic decomposition (with rationale)

Inspect the source tree:

```bash
find /path/to/<model>_source -type d -maxdepth 2
find /path/to/<model>_source -name "*.F90" -o -name "*.f90" -o -name "*.py" | wc -l
```

Decide on N topics (typically 5-10 for models with 50-300 source files). Document the topic split as a table in the wiki's eventual `index.md`. Examples:

- ~50 source files → 5–6 topics (ELM, EcoSIM)
- ~150-300 source files → 8–10 topics (FATES has 200+, split into 10)
- 500+ source files → consider splitting into multiple wikis (e.g., FATES is one wiki, ELM is another, even though they live under the same E3SM tree)

#### A.3 — Stage parameter files (if applicable)

See cross-cutting step 4.

#### A.4 — Dispatch N rewrite subagents in parallel

No audit phase needed (no prior wiki to audit against). Each subagent receives:

- Universal context block
- Its topic's source paths (the subset of files it owns)
- Output path: `docs/<model>-knowledge-base/<model>-codebase-wiki-<sha>/<topic>/`
- Required source-pin header to embed in every output file

**Subagent prompt template (greenfield rewrite):**

```text
Generate the {topic_name} section of the {model} codebase wiki at commit {sha}.

## Universal context

{universal_context_block}

## Inputs (read-only)

- {Model} source: {source_root}/{topic_subdirs}
- Parameter file (if any): {param_file_path}
- Other ground-truth files: {list}

## Output

Mirror sensible filenames into:
{output_root}/{model}-codebase-wiki-{sha}/{topic}/

Each file starts with:
---
**Source pin:** {Model} commit {sha} ({describe})
**Last verified:** {date}
---

Cite (path/Module.{ext}:NNN) for every substantive claim. Grep the source
before citing. Do NOT invent module names, parameter names, or line numbers.

If a routine or parameter you expected to exist is not in the source,
document the absence rather than fabricating.

## Constraints

- Read-only on source.
- Length: roughly proportional to the number of files in the topic.
- Be honest about uncertainty.

## Final report

Return: files written + line counts; spot-check (3 random claims with
file:line); any source surprises beyond the universal context.
```

Dispatch all N subagents in parallel. Wall-clock typically 10–30 minutes.

#### A.5 — Top-level `index.md`

Write a navigation index linking the topic indexes. Should include:

- Source pin + scope statement
- Topic table with brief descriptions and file counts
- Entry-point cheat-sheet (most-bookmarked file:line citations)
- "How to use this wiki" notes for new readers

#### A.6 — Sanity check

- File count matches your topic plan
- Every file has the source-pin header
- Sample 5 random `(file:line)` citations and verify each opens to relevant code
- Search for fabricated patterns: parameter names that don't appear in the parameter file, routine names that don't appear in any source `.F90`

```bash
# Spot-check fabrications by sampling random parameter mentions
grep -hoE '`[a-z_]+_[a-z_]+`' docs/<model>-knowledge-base/<model>-codebase-wiki-<sha>/**/*.md | sort -u | head -30
# Then verify a sample exists in the parameter file or source
```

#### A.7 — Commit

```bash
git add docs/<model>-knowledge-base/<model>-codebase-wiki-<sha>/
git commit -m "Add {model} codebase wiki at commit {sha}"
```

---

## Workflow B: Audit + rewrite

Use when you already have a defensible wiki at commit X and want a fresh one at commit Y.

### Steps

#### B.1 — Pre-audit setup

Same as Workflow A.1–A.4, plus: keep the prior wiki at commit X intact so subagents can read it for section structure.

#### B.2 — Dispatch N audit subagents in parallel

Each audit subagent's job: identify drift between the X-grounded wiki and the Y source. Output: a structured findings report with severity classifications.

**Audit subagent prompt template:**

```text
Audit topic NN ({topic_name}) of the {model} wiki against current source
at commit {Y_sha} ({describe_Y}).

## Background

A2MC has an existing wiki at {wiki_path_X}, generated against {model}
commit {X_sha} on {date_X}. We're now migrating to commit {Y_sha}.

## Inputs (read-only)

1. Existing wiki: {wiki_path_X}/{topic}/
2. NEW source at {Y_sha}: {source_path_Y}/{topic_subdirs}
3. OLD source at {X_sha} for diff reference: {source_path_X}/{topic_subdirs}

## What to look for

- Module renames / additions / removals
- Subroutine renames or signature changes
- Default parameter / constant value changes
- Refactored module paths
- New features missing from wiki
- Removed features still in wiki
- Stale file:line citations
- Coupling boundary changes (if model has a host)

For each finding, classify severity:
- CRITICAL: misleads into wrong action (inverted semantics, fabricated parameter, wrong default)
- MODERATE: missing important new content, incomplete description
- MINOR: stale lines, refactored paths, cosmetic differences

## Output

Write to {audit_path}/{NN}_{topic}.md with structure:

# Audit NN: {topic_name} — {X_sha} wiki vs {Y_sha} source

**Audit baseline:** wiki at {wiki_path_X}/{topic}/ (correct at {X_sha})
**Source pin:** {model} commit {Y_sha} ({describe_Y})
**Docs audited:** N (list)
**Source files checked:** (list with brief role)

---

## Findings

### CRITICAL

**C1. {doc}:{line} — {short_title}**

Wiki claims: "..."
Actual at {Y_sha} ({file:line}): ...
Drift: {what changed}.

(repeat per finding)

### MODERATE
### MINOR

---

## Summary

- Critical: N
- Moderate: N
- Minor: N

Brief verdict: how much rework does the {Y_sha} wiki rewrite need?
(short / medium / long / none-needed)

## Final report

Return: report path, C/M/m counts, top-3 most-impactful findings,
rewrite estimate.
```

#### B.3 — Quality gate (pilot pattern)

Dispatch 2 pilot audit subagents first (typically the highest-stakes topics — for FATES that was Plant Physiology + Advanced; for ELM it was core + biogeochem). Spot-check their reports against source for ONE concrete claim each. If the spot-checks pass, dispatch the remaining N-2.

Why pilot first: subagent quality varies session-to-session, and dispatching 10 in parallel that all produce garbage wastes 30+ minutes. Pilot first catches the failure mode early.

#### B.4 — Dispatch N rewrite subagents in parallel

Each rewrite subagent receives:
- Its audit report (from B.2)
- The X-commit wiki for **section structure only** (NOT for content — it's the prior version)
- Y-commit source for **ground truth**
- Universal context block
- Output path

**Rewrite subagent prompt template (Workflow B):**

```text
Rewrite topic NN ({topic_name}) of the {model} wiki to be ground-truth-correct
against {model} source at commit {Y_sha} ({describe_Y}).

## Universal context

{universal_context_block}

## Inputs (read-only)

1. Audit (your guide for what to fix): {audit_path}/{NN}_{topic}.md
   Address every CRITICAL and MODERATE finding.

2. Existing wiki for SECTION STRUCTURE ONLY (NOT content):
   {wiki_path_X}/{topic}/

3. {Model} source (ground truth):
   {source_path_Y}/{topic_subdirs}

4. Parameter file (if applicable): {param_file_path_Y}

## Output

Mirror filenames from the existing wiki into:
{output_root}/{model}-codebase-wiki-{Y_sha}/{topic}/

Each file starts with:
---
**Source pin:** {model} commit {Y_sha} ({describe_Y})
{coupling_pairing_if_applicable}
**Last verified:** {date}
---

Cite (file:line) with {Y_sha} line numbers — NOT line numbers from the
old wiki. Grep before citing.

## Constraints

- Read-only on source. Write only to output folder.
- No invented paths/functions/parameters.
- If something was removed at {Y_sha}, document removal explicitly.
- Match e85d997 doc length per file roughly.

## Final report

Return: files + line counts; audit findings addressed (counts vs audit
totals); unresolved findings; discoveries beyond audit; self-rating
(high/medium/low with reason).
```

#### B.5 — Top-level `index.md`

Same as A.5, plus a "What changed at {Y_sha} (vs {X_sha})" section listing the most user-relevant drifts (drawn from the audit summaries). For api-43-1 vs api-31-0 this section was 12 rows, organized by impact-on-calibration.

#### B.6 — Verify regression-free

For Workflow B specifically: confirm that any e85d997-corrected content the audits classified as "still valid at Y" actually survived the rewrite. The most common failure mode is rewrite subagents quietly rolling back a prior fix while updating other content.

Sample verification: if the X-version audit found and fixed a "smpsc/smpso units = mm not MPa" error, grep the Y-version wiki for `MPa` and `mm` references in transpiration-related docs and confirm the corrected version is present.

#### B.7 — Commit

Two commits is cleaner than one:

```bash
# Commit 1: audit reports
git add memory/dev_logs/.../audit_{Y_sha}/
git commit -m "Phase 2.1: {model} wiki audit reports vs {Y_sha} source"

# Commit 2: rewrite output
git add docs/<model>-knowledge-base/<model>-codebase-wiki-<Y_sha>/
git commit -m "Phase 2.2: regenerate {model} wiki for {Y_sha}"
```

---

## Output conventions

### Filename + path structure

```
docs/<model>-knowledge-base/
├── <model>-codebase-wiki-<sha>/        # the wiki itself
│   ├── index.md                        # navigation root
│   ├── <topic1>/
│   │   ├── index.md                    # topic overview
│   │   ├── <subtopic1>.md
│   │   └── <subtopic2>.md
│   ├── <topic2>/
│   │   └── ...
│   └── reference/                      # optional: module inventory
├── <model>_params_info_<sha>.json      # parameter file ground truth
└── <model>_output_info_<sha>.cdl       # output variable inventory (if applicable)
```

The `<sha>` suffix is the short commit hash. When the model bumps, generate a parallel directory with the new hash; do not modify the existing one.

### Source-pin header (every output file)

```markdown
---
**Source pin:** {Model} commit `{sha}` ({describe})
**HLM pairing:** {host_model} at commit `{host_sha}`     # if applicable
**Last verified:** {date}
---
```

### Citation format

`(path/relative/to/source_root/Module.F90:NNN)` for line citations. `(path/Module.F90:NNN-MMM)` for ranges. Cite the new commit's line numbers, not the old commit's.

### Audit report format

Stored under `memory/dev_logs/.../audit_{sha}/` (Workflow B only). One report per topic, named `NN_topic_name.md`. Per-finding structure: severity heading, identifier (`C1`, `M3`, etc.), citation, drift description.

---

## Cost estimates

Based on three-model experience (FATES, ELM, EcoSIM):

| Stage | Per-topic time | Wall-clock if parallel |
|---|---|---|
| Audit subagent (Workflow B) | 5–15 min | ~10–15 min for 6–10 topics |
| Rewrite subagent | 10–30 min | ~20–40 min for 6–10 topics |
| Top-level index.md | 5–10 min | sequential |
| Spot-check sanity verification | 10–20 min | sequential |
| **Total Workflow A** | | ~30–60 min |
| **Total Workflow B** | | ~60–90 min |

Token cost per subagent: 100K–400K tokens depending on topic size. Cost dominates the API budget for the wiki generation step.

Disk usage: ~500 KB–15 MB per wiki, depending on model size. Source checkouts dominate (~hundreds of MB per checkout).

---

## Common pitfalls

| Pitfall | Mitigation |
|---|---|
| Hallucinated routine names or fabricated source files | Mandate `(file:line)` citations + grep verification before citing. Spot-check 3–5 random claims. |
| Stale line numbers (subagent extracts from prior wiki, not new source) | Universal context emphasizes "use {Y_sha} line numbers, NOT {X_sha}". Audit reports anchor everything to the new source. |
| Rewrite subagents quietly rolling back a prior fix | Workflow B step B.6: explicit regression check on previously-corrected items. |
| Topic boundaries cross-cut a module — both topics under-document | Topic split should align with module boundaries; cross-cutting modules go in the topic where they conceptually live (e.g., FATES `EDMainMod.F90` is "core dynamics", not "biogeochem"). |
| Subagent dispatched 10 in parallel and they all produce thin output | Pilot-2-first pattern (B.3). Quality gate before committing to the full dispatch. |
| Universal context block too long → subagents skim or ignore it | Keep it ≤15 bullets, ordered by impact. Use bold for critical items. |
| Source-pin header missing or inconsistent across files | Sanity check: `grep -L 'Source pin' docs/<model>.../*.md` should be empty. |
| Wrong filename casing in citations | Cite the actual filename verbatim from `ls`, not from prior docs. Common trap: `ELMFatesInterfaceMod.F90` vs `elmfates_interfaceMod.F90`. |
| Calibration-critical doc ends up in a low-priority topic | Promote it to its own topic. FATES "advanced/cnp_calibration_guide.md" is its own audit topic for this reason. |

---

## Recipes

### Recipe A1 — New model, no prior wiki, single component

Example: bringing in a small standalone vegetation model.

1. Decide scope: which directories and files count as the model.
2. Pick 5–8 topics aligned with subdirectories.
3. Stage source (clone + checkout commit).
4. Stage parameter file (if applicable).
5. Dispatch N rewrite subagents in parallel (Workflow A).
6. Write top-level index.md.
7. Sanity check + commit.

Estimated time: ~30–45 min.

### Recipe A2 — New model with broken auto-generated wiki

Example: deepwiki / cursor wiki has fabricated content.

1. Confirm the breakage with 2–3 spot-checks against actual source. If broken, abandon the auto-generated wiki entirely (don't try to "fix" it incrementally — fabrications hide fabrications).
2. Run Recipe A1 from scratch.
3. In the new wiki's root index.md, document explicitly that the prior auto-generated wiki was abandoned and why.

This was the EcoSIM case (deepwiki had fabricated routines, files, paths).

### Recipe B1 — Existing source-grounded wiki, new commit, single component

Example: FATES e85d997 → e027a40.

1. Confirm the prior wiki is source-grounded (sample-check it against the OLD commit). If not, this is Recipe A2 instead.
2. Pin the new commit and prepare universal context block (drifts you already know about).
3. Dispatch 2 pilot audit subagents on highest-stakes topics. Spot-check.
4. Dispatch remaining audit subagents in parallel.
5. Read all audit summaries; refine universal context block with newly-discovered drifts.
6. Dispatch N rewrite subagents in parallel.
7. Top-level index.md with "What changed" section.
8. Regression check on prior-corrected items.
9. Two commits (audit + rewrite).

Estimated time: ~60–90 min.

### Recipe B2 — Coupled model pair (e.g., ELM + FATES at api-43-1)

Both components bumped together. Examples: api-31-0 → api-43-1 in this branch.

1. Decide the pairing: what's the "matched commit" for the host? E3SM master pins FATES via submodule; that's the natural pairing.
2. Run Recipe B1 for each component.
3. The component documenting the **coupling boundary contract** (in this case ELM's `core/`) is the highest-stakes audit topic in the pair — pilot it.
4. Universal context blocks reference each other ("FATES at e027a40 paired with ELM at d40b8431").
5. Top-level index.md explicitly calls out coupling boundary changes (in this case: `alm_fates%init` 3-arg signature, new `wrap_*` callbacks, ~10 new namelist flags).

Estimated time: ~2–3 hours.

### Recipe B3 — Adapter-kit user adding a new model

Example: a researcher wants to use A2MC for a model never targeted before.

1. Run Recipe A1 for greenfield wiki generation.
2. Then: build the parameter file extraction tool if the model uses an exotic parameter format.
3. Then: build the output-variable extraction tool if the model has registered history variables (analogous to FATES's `set_history_var` extraction at e027a40).
4. Then: register the model in `rag/loader.py` per Recipe 2 in `rag_build_roadmap.md`.
5. Then: build the RAG index per `rag_build_roadmap.md`.
6. Finally: register a milestone in A2MC's milestones.json (per `docs/18_ELM_FATES_Version_Association_Plan.md`).

The wiki generation step (this doc) is **prerequisite to all subsequent A2MC work** for the new model. Get this right and the rest of the adapter-kit pipeline is mostly mechanical.

---

## Connection to RAG and version-association infrastructure

The wiki produced by this roadmap feeds into:

| Downstream artifact | Built from | Reference doc |
|---|---|---|
| ChromaDB vector index | All `.md` files in the wiki | `rag_build_roadmap.md` |
| NetworkX knowledge graph | Parameter file + curated YAML overlay + wiki structure | `rag_build_roadmap.md` |
| Milestone metadata | Source-pin headers + commit hashes | `docs/18_ELM_FATES_Version_Association_Plan.md` |
| Calibration agent prompts | RAG retrieval results | `reasoning/methods.py` |
| Mode-aware path-prefix tags | Wiki path layout + `rag/loader.py:_WIKI_PATH_PREFIX_TAGS` | `mode_aware_workflow.md`, Doc 21 §B.2.3 |

If any of those downstream artifacts produces wrong content, the most likely root cause is wiki errors. Treat wiki generation as the foundation; nothing built on top can be more correct than it.

### Path-prefix tagging conventions for new wiki trees (Phase B / v2.92)

When generating a wiki for a new model (Workflow A) or rewriting an existing wiki (Workflow B), identify which paths gate mode-restricted content and add them to `rag/loader.py:_WIKI_PATH_PREFIX_TAGS`. The canonical FATES table is the reference (Doc 21 §B.2.3 path-prefix mapping). Conventions:

- **Mode-specific subdirectories** (e.g., `fire/`, `logging/`, `biophysics/hydraulics/`): tag with the gating flag plus `use_fates: [True]`.
- **Inverse-tagged docs** (apply when feature is OFF): use the same flag but with `[False]`. Example: `biophysics/transpiration.md` is tagged `use_fates_planthydro: [False]` because BTRAN runs only when hydraulics is off.
- **Theory docs by hypothesis** (`parteh/cnp_*.md`, `parteh/carbon_only.md`): tag with `parteh_mode: [2]` or `[1]` plus `use_fates: [True]` and `nutrient: [...]`.
- **Filename-prefix substring** (`parteh/h2_`): used when multiple files share a prefix (CNP allocation hypothesis files under `fates-official-docs/docs/source/parteh/`).

After adding entries, rebuild the index and run Tier 4 (`tools/mode_metadata_validator.py`) to confirm the new tags propagate.

### Output-registry extraction (parallel to wiki regen, v2.96+)

The wiki captures human-readable knowledge; the **output registry** captures the structured list of every variable the model exposes through its history-file mechanism. Both are needed for the AI to ground retrieval correctly. The wiki tells it *what concepts exist*; the output CDL tells it *what variables it can reference by name*.

For each model, produce a CDL by extracting from source code (NOT from `ncdump -h` of a representative case — that approach is case-specific and was abandoned in Phase 4):

| Model | Source pattern | Extraction |
|---|---|---|
| **FATES** | `set_history_var(...)` calls in `FatesHistoryInterfaceMod.F90` | Phase 4 wiki regen (manual / agent task; no committed extractor) |
| **ELM core** | `hist_addfld1d(...)` and `hist_addfld2d(...)` calls across `components/elm/src/**/*.F90` | `python scripts/extract_elm_outputs.py` |
| **New model (adapter-kit)** | Whatever your model uses to register history variables (see your model's docs) | Adapt `extract_elm_outputs.py`'s parser pattern: strip Fortran comments + collapse `&` continuations + regex match `call <register-fn>(<args>)`, then `key='value'` arg parsing |

The output CDL gets one row in the milestone registry (`rag/milestones.json`) under `output_cdl` (single-model) or `fates_output_cdl` + `elm_output_cdl` (ELM-FATES two-model). The build script auto-detects from the milestone's commit short SHAs but explicit registration is preferred for self-describing milestones.

After each wiki regen, re-extract the corresponding output CDL — they're tied to the same commit pins.

---

## When to regenerate

| Trigger | Workflow |
|---|---|
| Adapter-kit user starts a new model | Workflow A |
| Existing-model commit bumps within an api epoch (e.g., api.43.1.0 → api.43.1.1) | Skip — milestone covers within-epoch sci drift via parameter-file sha check (per `docs/18`) |
| Existing-model commit bumps across api epochs (e.g., api-31-0 → api-43-1) | Workflow B |
| Audit reports flag drift even within an epoch (rare) | Workflow B for the affected topics only |
| The auto-generated deepwiki/cursor wiki is being refreshed | Skip — deepwiki output is not source-grounded; running it is wasted effort |

---

## Companion docs

- `rag_build_roadmap.md` — what to do AFTER the wiki exists. Recipe 1 (RAG rebuild after wiki bump) and Recipe 2 (RAG for a new model).
- `docs/18_ELM_FATES_Version_Association_Plan.md` — version association layer. Milestones, drift detection, alignment checks.
- `memory/dev_logs/20260410d_FATES_Wiki_vs_e85d997_Audit.md` — first proven Workflow B example.
- `memory/dev_logs/20260410e_ELM_Wiki_vs_60d9aad_Rewrite.md` — Workflow A example.
- `memory/dev_logs/20260424g_EcoSIM_Codebase_Wiki_Rewrite.md` — Workflow A example for adapter-kit-style new-model adoption.
- `memory/dev_logs_fatesversionassociation/20260424e_ELM_FATES_Version_Association_Execution_Roadmap.md` — most recent paired Workflow B (FATES e027a40 + ELM d40b8431).
