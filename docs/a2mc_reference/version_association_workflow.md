# Version Association Workflow

**Audience:** users running A2MC against any ELM-FATES checkout, A2MC maintainers shipping new milestones, and adapter-kit users who need to understand the model-to-RAG matching design.

**Status:** Implemented in Phase 4 of `docs/18_ELM_FATES_Version_Association_Plan.md` on the `elm-fates_version_association` branch. Two milestones currently registered: `api-43-1` (canonical) and `api-31-0` (legacy, Kougarok manuscript reproducibility).

**Companion docs (the adapter-kit five-step series):**

- `codebase_wiki_generation_roadmap.md` — Step 1: produce a source-grounded wiki
- `rag_build_roadmap.md` — Step 2: wire wiki + parsers into the vector RAG
- `graphrag_curated_yaml_roadmap.md` — Step 3: overlay calibration intelligence via curated YAML
- `rag_validation_workflow.md` — Step 4: validate the chain before shipping
- **This doc — Step 5: associate users' checkouts with the right RAG profile**

---

## Why version association exists

The wiki, parameter file, and curated YAML in a single A2MC RAG are pinned to a specific FATES + ELM commit. If a user runs A2MC against a DIFFERENT checkout, the AI calibration agents quietly read mismatched information — wrong parameter defaults, references to renamed routines, wiki text that documents removed mechanisms. The errors propagate from retrieval to recommendation to HPC submission to results, with no obvious failure mode.

Before Phase 4, A2MC had one RAG. The user manually pointed it at the right wiki via symlinks (`docs/fates-knowledge-base/fates-codebase-wiki -> fates-codebase-wiki-e027a40`). This was fragile (silent on the wrong link), single-user (one symlink target on disk at a time), and offered no rebuild path when a user's checkout drifted.

Phase 4 replaced that with a **milestone registry** plus an **auto-detection layer**. A2MC now reads `A2MC_MODEL_PATH` (the user's E3SM checkout root), detects the ELM + FATES commits, and selects a matching registered milestone profile automatically. If no milestone matches, it tells the user how to rebuild.

---

## Architecture

### Per-profile layout

Every registered RAG profile has exactly four on-disk artifacts at canonical paths:

```
rag/
├── chroma_db/<profile>/                       ChromaDB persist dir
├── graphs/<profile>.json                      NetworkX node-link graph (with embedded _metadata)
├── metadata/<profile>.json                    Profile metadata JSON
└── data/curated_relationships_<profile>.yaml  Frozen per-milestone curated YAML snapshot
```

The `<profile>` name is the milestone identifier. Format: `api-<major>-<minor>` from the FATES api.X.Y tagging methodology — e.g., `api-31-0`, `api-43-1`, `api-44-0`.

### Milestone registry (`rag/milestones.json`)

Single JSON file maps profile name to a milestone description. Per entry:

```json
"api-43-1": {
  "fates_api_epoch": "43.1",
  "fates_tag_built": "sci.1.91.1_api.43.1.0",
  "fates_commit_built": "e027a4030d2a0f09039fb337ad67ced7461dd4f0",
  "fates_param_file_format": "json",
  "elm_commit_built": "d40b84318cd4e309ca66f014a7b6e9e5f43a3adc",
  "elm_wiki_subdir": "elm-codebase-wiki-d40b843",
  "fates_wiki_subdir": "fates-codebase-wiki-e027a40",
  "covers_sci_tags": ["sci.1.90.0_api.43.1.0", ...],
  "canonical": true,
  "available_locally": true,
  "curated_yaml_path": "rag/data/curated_relationships_api-43-1.yaml"
}
```

`covers_sci_tags` is auto-populated by `tools/rag_manifest.list_sci_tags_for_epoch()` querying the local FATES git repo. `canonical: true` marks the default profile; `legacy: true` marks profiles preserved for reproducibility (e.g., paper-target builds).

### Required environment variables

| Variable | Required? | Purpose |
|---|---|---|
| `A2MC_MODEL_PATH` | **Yes** | Absolute path to user's E3SM/ELM-FATES checkout root |
| `A2MC_RAG_DIR` | No (default `<repo>/rag`) | RAG storage tree root |
| `A2MC_RAG_ACTIVE` | Auto-set by orchestrator | Active milestone profile name |
| `A2MC_RAG_AUTO_REBUILD` | No (default `false`) | If `true`, orchestrator auto-rebuilds on T2 / T3-near drift |
| `A2MC_RAG_T3_AUTO_DISTANCE` | No (default `100`) | T3 epoch-distance ceiling above which the orchestrator always emits a prompt-pack instead of auto-rebuilding |

Hard error on missing `A2MC_MODEL_PATH` — version association is mandatory.

### Orchestrator alignment hook

`orchestrator.py:_check_rag_alignment()` runs at startup:

1. Reads `A2MC_MODEL_PATH`.
2. Calls `tools.model_version.detect_model_version()` → `ELMFATESVersion`.
3. Loads `rag/milestones.json`.
4. Calls `tools.rag_selector.select_rag()` → `RAGSelection`.
5. Sets `A2MC_RAG_ACTIVE` to the matched profile.
6. If drift detected, dispatches via `tools.auto_rebuild.handle_drift()` (v2.98, docs/22).

### Auto-rebuild tier policy (v2.98)

`handle_drift()` classifies the bump (`tools.rag_selector.classify_bump_tier()`) and dispatches per docs/22 §3.1:

| Tier / condition | Action | Flag-gated? |
|---|---|---|
| **T1** (no drift, sha matches) | Not entered — `rebuild_required` is false here. | n/a |
| **T2** (same epoch, sha differs) | If flag set: subprocess `rag_bump.py --mode auto` + in-process validator gate; on Red verdict, rollback from `<profile>.previous/` snapshot. If flag unset: warn + continue. | Yes |
| **T3-near** (`epoch_distance ≤ A2MC_RAG_T3_AUTO_DISTANCE`) | Same as T2. | Yes |
| **T3-distant** (`epoch_distance > A2MC_RAG_T3_AUTO_DISTANCE`) | Always emit prompt-pack via `rag_bump.py --mode prompt-pack`, abort startup. Distant epoch jumps need human-supervised wiki regen. | No (always manual) |
| **`no_match`** | Log error, abort startup — no basis to rebuild from. | n/a |

Default `A2MC_RAG_T3_AUTO_DISTANCE = 100` (one major epoch step). The api-43-1 → api-44-0 case has distance 100 (still auto-eligible). The api-31-0 → api-43-1 case has distance 1201 (always manual).

Concurrency: a file lock at `<rag_dir>/.bump.lock` prevents two startups from racing on a rebuild.

Mode-aware safety: T1 only writes metadata (chunks / graph nodes / curated YAML untouched). T2 / T3-near rebuilds run against the source-pinned wikis + per-milestone curated YAML (which carry `applies_in:` blocks); the validator gate (Tier 4 + snapshot + completeness + cross-milestone) catches any mode-tagging regression.

---

## Relation to mode-aware retrieval (Phase B / v2.92)

Version association and mode-aware retrieval are **orthogonal**:

- **Milestone selection** (this doc) decides WHICH RAG profile loads — what's in the chunk corpus.
- **Mode-aware filtering** (`mode_aware_workflow.md`) decides WHICH chunks within that profile pass at retrieval time, based on the active `ConfigMode` (env vars + `A2MC_ELM_OPTIONS`).

Adopters configure both:

```bash
# Site config
export A2MC_MODEL_PATH="/path/to/E3SM-checkout"           # version association
export A2MC_ELM_OPTIONS="-bgc fates -nutrient cnp -nutrient_comp_pathway eca"  # mode
export A2MC_FATES_PARTEH_MODE=2                            # mode
```

Each milestone profile has its own per-milestone YAML (`rag/data/curated_relationships_<profile>.yaml`) carrying its own `applies_in:` tags. Mode filters apply per-profile after the milestone is selected.

---

## End-user workflows

### Workflow 1: First-time setup

```bash
# In your site config (use_cases/<site>/config/<site>_config.sh):
export A2MC_MODEL_PATH="/path/to/your/E3SM_FATES"

# Then run A2MC normally:
source a2mc_config.sh
source use_cases/Kougarok/config/kougarok_config.sh
python orchestrator.py --run
```

The startup alignment hook auto-detects your FATES + ELM commits and matches them to a registered milestone. No manual symlink switching.

### Workflow 2: Diagnose what milestone matches your checkout

```bash
python scripts/rag_match.py
```

Output (example, user at api-43-1 commit):

```
User checkout:      /Users/.../E3SM_FATES_api43-1
  FATES:            e027a40  (sci.1.91.1_api.43.1.0-0-ge027a403)
  ELM:              d40b843
  api epoch:        43.1

Selection:          api-43-1
  mode:             exact_epoch
  bump tier:        T1

--- Recommendation ---
T1 (metadata refresh only). Use milestone 'api-43-1' as-is.
```

Output (example, user a few commits ahead of the milestone within api.43.1):

```
Selection:          api-43-1
  mode:             close_enough
  drift:            forward, 7 commits past milestone
  bump tier:        T2

FATES commits user has past milestone (forward, 7 shown):
  abc1234  Update some module
  def5678  Fix some bug
  ...
FATES .F90 files changed: 3
  biogeochem/SomeMod.F90
  ...

--- Recommendation ---
T2 (param-only delta). Same epoch as milestone, but the FATES parameter file
sha differs. Recommend partial rebuild:
  python scripts/rag_bump.py --target-milestone api-43-1 --mode prompt-pack
```

### Workflow 3: List registered milestones

```bash
python scripts/rag_list.py
```

```
RAG milestones registry: rag/milestones.json
Active profile:          api-43-1

  profile         fates tag                 epoch   flags
  --------------  ------------------------  ------  ---------------------------
  api-43-1        sci.1.91.1_api.43.1.0     43.1    canonical, local, ACTIVE
  api-31-0        sci.1.68.2_api.31.0.0     31.0    legacy, local
```

### Workflow 4: Bump to a new milestone

When a new FATES api epoch ships (e.g., user moves to `api.45.0`), no registered milestone covers it. `rag_bump.py` orchestrates the rebuild.

Three execution modes — pick based on what you have:

| Mode | When to use | Cost | Speed |
|---|---|---|---|
| `--mode prompt-pack` (default) | You have any AI assistant (Claude Code, Claude.ai, ChatGPT, etc.) and want to drive each prompt manually | $0 in tooling cost | Slowest (manual) |
| `--mode api` | You have an Anthropic / OpenAI / CBorg API key and want sequential AI calls | ~$5–15 per bump (Opus pricing ceiling) | Medium (~30 min) |
| `--mode auto` | You want full automation through the build + validation loop | Same as api + rebuild compute | Fastest |

```bash
# T3 bump (new epoch) with prompt-pack
python scripts/rag_bump.py --target-milestone api-45-0 --mode prompt-pack
# -> Writes Offline/bump_pack_api-45-0/ with PLAN.md + 16 topic prompts.
#    User runs them through Claude Code / their AI of choice.

# T3 bump with API-driven execution (cost-guarded)
python scripts/rag_bump.py --target-milestone api-45-0 --mode api --confirm-spend
# -> Sequentially calls AI API for each topic, drafts go to drafts/ for review.

# T3 bump fully automated
python scripts/rag_bump.py --target-milestone api-45-0 --mode auto --confirm-spend
# -> Mode B + auto-deploy + validators + build + register milestone.
```

T1 and T2 bumps don't use AI:
- T1: `build_rag_index.py --record-metadata-only` (just refresh metadata)
- T2: `build_rag_index.py --rebuild --graph-only` (rebuild graph only; wiki content stays valid)

### Workflow 5: Manually switch profile (advanced)

```bash
# Override the auto-selected profile (e.g., for ad-hoc experimentation)
export A2MC_RAG_ACTIVE=api-31-0
python orchestrator.py --run
```

The orchestrator's alignment hook will warn if your checkout doesn't match the forced profile. With `A2MC_RAG_AUTO_REBUILD=true` it will auto-rebuild for T2 / T3-near drift; T3-distant drift always emits a prompt-pack and aborts (see "Auto-rebuild tier policy" above).

---

## Maintainer workflows

### Building a new milestone from scratch

```bash
# 1. Set A2MC_MODEL_PATH to a checkout at the target commit
export A2MC_MODEL_PATH=/path/to/E3SM/at/target/commit

# 2. Run the build (auto-detects everything from the checkout)
python scripts/build_rag_index.py --rebuild --profile api-NN-M

# 3. Freeze a per-milestone YAML snapshot
cp rag/data/curated_relationships.yaml rag/data/curated_relationships_api-NN-M.yaml
# (Edit if api-NN-M needs different param/mechanism names than the canonical YAML)

# 4. Register in milestones.json (manually edit OR use rag_bump.py --mode auto's
#    registration step)
```

### Per-milestone YAML reproducibility principle

This is the load-bearing rule for milestone designs. Each milestone owns its own curated YAML at `rag/data/curated_relationships_<profile>.yaml`. The canonical `rag/data/curated_relationships.yaml` is treated as an active-development copy, NOT shared across milestones.

**Why:** If a milestone is rebuilt against an evolved canonical YAML, its graph gains nodes and edges that didn't exist in the original (e.g., the post-Phase-3.5 YAML refers to `fates_cnp_eca_km_nh4`, which doesn't exist at api.31). The rebuild silently corrupts the milestone's reproducibility.

**The api-31-0 case** is concrete: it's the RAG profile used for the Kougarok manuscript. Its frozen YAML uses `fates_cnp_km_nh4`, `FATES_NUPTAKE_SZPF`, `FATESPartehMod.F90::CNPAllocate` — names that DO exist at api.31 source. The post-3.6 canonical YAML would reference api-43 names that don't exist at api.31, breaking the manuscript-time graph.

**Test for any change to the canonical YAML:** would rebuilding any registered milestone from its frozen YAML produce different bytes than the registered artifacts? If yes, the change is fine for the canonical (active development) but must NOT touch the frozen snapshots.

### Promoting a milestone to canonical

In `rag/milestones.json`, set `canonical: true` on one milestone (and `false` on the previous canonical). The selector prefers canonical at the same epoch distance.

### Verification

`scripts/verify_phase4.py` runs content-correctness gates and end-to-end smoke tests. Output: `docs/a2mc_reference/phase4_verification.md`. Run after any milestone registration / migration to confirm the system is healthy:

```bash
python scripts/verify_phase4.py
```

---

## How a bump actually works (validator iteration flowchart)

A T3 bump (new api epoch) runs through three sequential validator gates. Each gate must land Green before advancing — the lower layer's correctness is a prerequisite for the upper layer's verdict to be meaningful (a YAML check against a fabricated wiki is meaningless; a RAG diff against a broken graph is meaningless).

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    USER STARTS A T3 BUMP                                 │
│   `python scripts/rag_bump.py --target-milestone api-NN-M --mode <X>`    │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │  Phase 1: Source prep        │
                │  - Clone E3SM at target SHA  │
                │  - Init FATES submodule      │
                │  - Stage param file (JSON or │
                │    CDL extracted from .nc)   │
                │  - Synthesize output CDL     │
                │    from FatesHistoryInter-   │
                │    faceMod.F90               │
                └──────────────┬───────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │  Phase 2: Wiki regeneration  │
                │  - 10 FATES topic prompts    │
                │  - 6 ELM topic prompts       │
                │  - Mode A: user runs prompts │
                │  - Mode B: API parallel calls│
                │  - Mode C: API + auto-deploy │
                └──────────────┬───────────────┘
                               │
                               ▼
       ┌───────────────────────────────────────────────────────┐
       │  GATE 1 — codebase_wiki_validator                     │
       │  (Wiki ↔ source code, 5 dimensions)                   │
       │                                                       │
       │   1. (file:line) citations resolve                    │
       │   2. Line numbers in-range                            │
       │   3. Routine declarations exist in source             │
       │   4. fates_*/elm_* parameter names valid              │
       │   5. *Mod.F90 references exist                        │
       └─────────────────────┬─────────────────────────────────┘
                             │
                             ▼
                       ┌─────────────┐
                       │   Verdict?  │
                       └──┬────────┬─┘
                          │        │
                  Red/Yellow      Green
                          │        │
                          ▼        │
       ┌──────────────────────────┐│
       │  Patch wiki:             ││
       │  - Fix dead citations    ││
       │  - Replace fabricated    ││
       │    routine/module names  ││
       │  - Add missing param     ││
       │    coverage              ││
       │  - Update validator FP   ││
       │    blacklists if regex   ││
       │    needs tuning          ││
       └──────────┬───────────────┘│
                  │                 │
                  └────loop─────────┤
                                    │
                                    ▼
                ┌──────────────────────────────┐
                │  Phase 3: Build RAG          │
                │  - chroma_db (vector index)  │
                │  - graph (NetworkX)          │
                │  - metadata JSON             │
                └──────────────┬───────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │  Phase 3.5: Curated YAML     │
                │  - Freeze per-milestone copy │
                │  - Update for renamed params │
                │    (`fates_cnp_km_*` →       │
                │    `fates_cnp_eca_km_*` etc.)│
                │  - Add new mechanisms        │
                └──────────────┬───────────────┘
                               │
                               ▼
       ┌───────────────────────────────────────────────────────┐
       │  GATE 2 — yaml_wiki_validator                         │
       │  (Curated YAML ↔ wiki + param + output, 5 dimensions) │
       │                                                       │
       │   A. Param coverage in wiki                           │
       │   B. Mechanism coverage in wiki (case-insensitive)    │
       │   C. Output references valid (in CDL/JSON)            │
       │   D. Code-reference resolution (file::routine)        │
       │   E. Citation freshness sample                        │
       └─────────────────────┬─────────────────────────────────┘
                             │
                             ▼
                       ┌─────────────┐
                       │   Verdict?  │
                       └──┬────────┬─┘
                          │        │
                  Red/Yellow      Green
                          │        │
                          ▼        │
       ┌──────────────────────────┐│
       │  Patch YAML or wiki:     ││
       │  - Rename phantom params ││
       │  - Update code_reference ││
       │    strings to real       ││
       │    file::routine         ││
       │  - Tag ELM-side outputs  ││
       │    with host_model: elm  ││
       │  - Add wiki coverage for ││
       │    missing entries       ││
       └──────────┬───────────────┘│
                  │                 │
                  └────loop─────────┤
                                    │
                                    ▼
       ┌───────────────────────────────────────────────────────┐
       │  GATE 3 (optional) — rag_diff                         │
       │  (Built RAG ↔ reference milestone, 4 dimensions)      │
       │                                                       │
       │   1. Parameter inventory delta                        │
       │   2. Graph structure (nodes/edges by type)            │
       │   3. Wiki content (Jaccard similarity)                │
       │   4. Parameter file structure                         │
       │                                                       │
       │  Thresholds version-bump-aware: cross-major-version   │
       │  diffs scale `removed_y` / `renamed_y` bands.         │
       └─────────────────────┬─────────────────────────────────┘
                             │
                             ▼
                       ┌─────────────┐
                       │   Verdict?  │
                       └──┬────────┬─┘
                          │        │
                       Red/      Green or
                       Unexp.   Yellow-by-
                       Yellow    design
                          │        │
                          ▼        │
       ┌──────────────────────────┐│
       │  Investigate:            ││
       │  - Unexpected node       ││
       │    drops?                ││
       │  - Wiki similarity too   ││
       │    low?                  ││
       │  - Re-check Gates 1-2    ││
       └──────────┬───────────────┘│
                  │                 │
                  └────loop─────────┤
                                    │
                                    ▼
                ┌──────────────────────────────┐
                │  Register milestone in       │
                │  rag/milestones.json         │
                │  - Mark canonical / legacy   │
                │  - Auto-populate covers_     │
                │    sci_tags from FATES git   │
                └──────────────┬───────────────┘
                               │
                               ▼
                ┌──────────────────────────────┐
                │  GATE 4 — verify_phase4.py   │
                │  Content gates + smoke tests │
                │                              │
                │  ALL GREEN → done            │
                └──────────────────────────────┘
```

**Why three gates, not one combined check?**

Each gate has a different question and a different fix path:

| Gate | Question | Fix happens in |
|---|---|---|
| 1. codebase_wiki | "Does the wiki cite real source code?" | Wiki `.md` files |
| 2. yaml_wiki | "Does curated YAML match the wiki?" | `rag/data/curated_relationships*.yaml` |
| 3. rag_diff | "Does the built RAG resemble the reference?" | Either gate above OR threshold tuning |

If you collapsed them into one validator, a Red verdict couldn't tell you what to fix. The three-gate stack makes drift attributable to a specific layer.

**Why does the iteration loop exist (rather than a one-shot validator)?**

Wiki regeneration uses an LLM (subagent dispatch in Mode A/C, API call in Mode B). LLMs hallucinate. The Phase 2 → Gate 1 loop is the gauntlet that catches:

- Fabricated module names (e.g., `PRTMyHypothesisMod.F90` from a tutorial template)
- Dead `(file:line)` citations from outdated source pinning
- Cross-component citations bleeding into the wrong wiki (FATES wiki citing ELM-side files)

We saw all three classes of error during the api-31-0 → api-43-1 bump on this branch. The validator-iterate-fix loop turned the wiki from Red to Green over ~6 patch passes. See `memory/dev_logs_fatesversionassociation/20260427b/c/d_*.md` for the worked record.

**Validator improvements during iteration**

Sometimes Red is the validator's fault (false positives) rather than the wiki's fault. Examples we hit:

- `codebase_wiki_validator` Dim 4 was matching `fates_*` against derived-type names (`fates_patch_type`), namelist flags (`fates_log`), and filenames (`fates_params_default`). Fix: hand-derived FP-pattern blacklist (~8 regex).
- `yaml_wiki_validator` Dim B mechanism name match was case-sensitive; "ECA Competition" vs "ECA competition" was flagged. Fix: `wiki.contains(needle, case_insensitive=True)`.

These improvements get committed to the validator scripts themselves. Future bumps benefit. The loop is therefore:

```
fix wiki → re-run validator → if still Red but signal looks like FP →
fix validator → re-run → if real Red → fix wiki → re-run → ... → Green
```

**T1 and T2 short-circuit the flowchart**

- T1 (same epoch, same commit, sha matches): no Phase 2, no validator iteration. Just `build_rag_index.py --record-metadata-only`. Done.
- T2 (same epoch, param file changed): skip Phase 2 (wiki content valid). Run Phase 3 graph rebuild only. Re-run Gate 2 (yaml_wiki) since the parameter list moved. Skip Gate 3 (rag_diff) unless you want a sanity report.

T3 is the only path that exercises every gate.

---

## Common recipes

Patterns that recur in version-association work.

### Recipe A1 — User reports "RAG seems wrong"

Workflow:

1. Run `scripts/rag_match.py`. Confirm which milestone the selector picked.
2. Compare to `A2MC_RAG_ACTIVE` in the failing run's environment. Mismatch?
3. Check `rag/metadata/<profile>.json` to see when the profile was built.
4. If user's checkout doesn't match any milestone, run `rag_bump.py --target-milestone <derived-name>`.

### Recipe A2 — Adding a new model checkout

User has a FATES checkout at a commit no registered milestone covers. The selector returns `mode: rebuild_needed`. Workflow:

1. Decide milestone name: `api-<major>-<minor>` from the user's FATES describe output.
2. Run `rag_bump.py --target-milestone <name> --mode <prompt-pack|api|auto>`.
3. Review validator reports (Step 4 of the adapter kit) before declaring the milestone built.
4. Commit the resulting `rag/chroma_db/<name>/`, `rag/graphs/<name>.json`, `rag/metadata/<name>.json`, `rag/data/curated_relationships_<name>.yaml`, and the manifest update.

### Recipe A3 — Same epoch, parameter-only change

User edited a parameter default in their checkout (custom calibration setup) but is at the same FATES commit as a registered milestone. The selector reports `T1` (commit equality is the drift signal); the user's custom param values are runtime data, not RAG content. No rebuild needed; the milestone's wiki + graph still describe the parameter correctly.

If the user wants their custom values reflected in the graph (rare), they manually run `build_rag_index.py --rebuild --graph-only --param-cdl /path/to/custom.cdl`.

### Recipe A4 — Cross-major-version diff

Comparing api-31-0 vs api-43-1 with `tools/rag_diff.py` — multi-major-version distances tripped the original "removed > 5" Yellow threshold. The validator now scales thresholds by the api-major distance (added in v2.88, see `rag_diff.py:scale_thresholds`).

Practical: when comparing milestones more than 1 api-major apart, expect Yellow on `removed_params` purely from the time gap. Inspect the report's "scaled thresholds" note to confirm.

### Recipe A5 — Forking a milestone for an experimental branch

User wants to keep the canonical milestone untouched but iterate on a custom curated YAML for an experimental calibration. Workflow:

1. Copy: `cp rag/data/curated_relationships_<canonical>.yaml rag/data/curated_relationships_<canonical>-experimental.yaml`
2. Build: `build_rag_index.py --rebuild --profile <canonical>-experimental --curated-yaml rag/data/curated_relationships_<canonical>-experimental.yaml --model-path $A2MC_MODEL_PATH`
3. The new profile lives at `rag/{chroma_db,graphs,metadata}/<canonical>-experimental/`.
4. To switch into it: `export A2MC_RAG_ACTIVE=<canonical>-experimental`.
5. Don't register it in the canonical manifest unless you want it permanent.

---

## Pitfalls and known limitations

### Param-file sha drift signal uses commit equality

The metadata records the docs-staged param file's sha (used by the graph builder). The user's source-tree file lives at a different path. Comparing the two shas is meaningless — they're different artifacts even with identical content. The selector / orchestrator alignment hook instead use FATES commit-SHA equality as the drift signal: same commit ⇒ same source content by definition.

Future enhancement: also record the source-tree sha at index time for finer-grained drift detection (e.g., user edits parameter file without changing FATES commit).

### Mode B/C of `rag_bump.py` work from prompt content + general FATES knowledge

A standalone Python script can't dispatch Claude Code subagents (which have file-system access). Modes B and C therefore work from what's in the prompt + the AI's training data. Quality is lower than Phase 2's Claude-Code-driven dispatch. Adapter-kit branch will likely abstract this with a `ModelDescriptor` interface that drives subagent dispatch when running inside Claude Code.

### api-31-0 staged CDL is header-only

`docs/fates-knowledge-base/fates_params_info.cdl` was extracted from a Kougarok-specific NetCDF without the data block. Parameter defaults are not parseable from this artifact. The api-31-0 graph nodes have `default_values: None`. To recover defaults for api-31, parse the actual `.nc` file at `<E3SM>/components/elm/src/external_models/fates/parameter_files/`.

This is a staging-time decision (header-only is enough for parameter-name and dimension extraction). Future enhancement: include data block at staging time.

### Symlinks are gone — explicit `wiki_subdir` is mandatory

`docs/fates-knowledge-base/fates-codebase-wiki` and `docs/elm-knowledge-base/elm-codebase-wiki` were removed in Phase 4 Step 4.15. Any code that hardcoded these paths will silently load nothing. The loader's first-match-wins probe still works for back-compat, but emits a warning. Always pass `wiki_subdir` explicitly when calling `rag.loader.load_knowledge_base()` from new code.

### ELM-FATES-specific assumptions in `rag_bump.py`

- E3SM submodule layout (`components/elm/src/external_models/fates/`)
- FATES api.X.Y_sci.Z.Z.Z tagging methodology
- JSON param file (api.43+) / CDL (api.31)
- 10 FATES + 6 ELM wiki topic taxonomy
- Required ELM coupling for FATES wiki cross-references

These assumptions are documented at the top of `scripts/rag_bump.py`. Adapter-kit users targeting a non-ELM-FATES model (BeTR, EcoSIM, ReSOM, etc.) will need to abstract these into a `ModelDescriptor` interface.

---

## File-level reference

| File | Purpose |
|---|---|
| `tools/model_version.py` | `detect_model_version()`, ComponentVersion / ELMFATESVersion dataclasses |
| `tools/rag_metadata.py` | metadata schema, sha computation, ChromaDB metadata flattening |
| `tools/rag_manifest.py` | `Manifest` / `Milestone` dataclasses, CRUD, `list_sci_tags_for_epoch()` |
| `tools/rag_selector.py` | bidirectional milestone matching; `select_rag()`, `classify_bump_tier()` |
| `scripts/build_rag_index.py` | profile-aware build with auto-detection |
| `scripts/rag_list.py` | tabular milestone listing |
| `scripts/rag_match.py` | diagnostic CLI; runs selector + git-history walk |
| `scripts/rag_bump.py` | T1/T2/T3 bump orchestrator, modes A/B/C |
| `scripts/verify_phase4.py` | content-gates + smoke tests verification harness |
| `orchestrator.py:_check_rag_alignment()` | startup alignment hook |
| `rag/loader.py:load_knowledge_base()` | accepts explicit `wiki_subdir` (no probe) |
| `rag/vector_store.py`, `rag/retriever.py`, `rag/hybrid_retriever.py` | env-var-driven path resolution |
| `rag/graph_builder.py:save_graph()` | accepts optional `metadata` dict, embeds `_metadata` |
| `tools/config.py` | `MODEL_PATH`, `RAG_DIR`, `RAG_ACTIVE`, `RAG_AUTO_REBUILD` properties |

For internal-implementation details see the dev log series at `memory/dev_logs_fatesversionassociation/20260428a-d_*.md`.
