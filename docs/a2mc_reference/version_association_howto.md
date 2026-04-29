# Version Association: How to Use

**Audience:** new A2MC users running their first calibration. You have an E3SM/ELM-FATES checkout; you want A2MC to use the right RAG/GraphRAG content for *your* version, automatically.

**Reading time:** ~5 minutes. For the comprehensive reference see `version_association_workflow.md`.

---

## What this gives you

A2MC's RAG/GraphRAG holds wiki text, parameter metadata, and curated knowledge for a specific FATES + ELM commit. If A2MC reads from the wrong version, the AI calibration agent silently retrieves mismatched information and produces wrong recommendations.

**With version association, A2MC handles this automatically:**

1. You point A2MC at your E3SM checkout (`A2MC_MODEL_PATH`).
2. A2MC reads your FATES + ELM commits.
3. A2MC matches them to a registered "milestone" RAG profile.
4. The orchestrator loads the right profile silently. No symlink switching, no per-run config tweaking.

If your checkout doesn't match any registered milestone, A2MC tells you exactly what to do.

---

## Setup (one-time per machine)

### Step 1: get an E3SM/ELM-FATES checkout

You probably already have one. Confirm it has the FATES submodule initialized:

```bash
cd /path/to/your/E3SM
ls components/elm/src/external_models/fates/   # should be non-empty
# If empty:
git submodule update --init components/elm/src/external_models/fates
```

### Step 2: tell A2MC where it is

In your site config (e.g., `use_cases/Kougarok/config/kougarok_config.sh`), set:

```bash
export A2MC_MODEL_PATH="/path/to/your/E3SM"
```

That's it. The default `A2MC_RAG_DIR=$A2MC_ROOT/rag` and other env vars are correct out of the box.

### Step 3: confirm A2MC sees your checkout

```bash
source a2mc_config.sh
source use_cases/Kougarok/config/kougarok_config.sh

python scripts/rag_match.py
```

Expected output (for a user at the canonical FATES `e027a40`):

```
User checkout:      /path/to/your/E3SM
  FATES:            e027a40  (sci.1.91.1_api.43.1.0-0-ge027a403)
  ELM:              d40b843
  api epoch:        43.1

Selection:          api-43-1
  mode:             exact_epoch
  bump tier:        T1

--- Recommendation ---
T1 (metadata refresh only). Use milestone 'api-43-1' as-is.
```

If you see this, **you're done**. A2MC will pick up `api-43-1` automatically every time you run `orchestrator.py`.

---

## Auto-detection flow (what's happening under the hood)

```
                  Your run starts
                        │
                        ▼
              orchestrator.py __init__
                        │
                        ▼
            _check_rag_alignment()
                        │
              ┌─────────┴──────────┐
              │                    │
              ▼                    ▼
     A2MC_MODEL_PATH set?     If no → ERROR + abort
              │
              │ yes
              ▼
     detect_model_version()
     (reads ELM + FATES commits via git)
              │
              ▼
      load rag/milestones.json
              │
              ▼
     select_rag(version, manifest)
              │
       ┌──────┴───────────────────┐
       ▼                          ▼
  exact_epoch / close_enough    rebuild_needed / no_match
       │                          │
       ▼                          ▼
  set A2MC_RAG_ACTIVE         WARN + tell user to run
  to matched profile          scripts/rag_bump.py
       │
       ▼
  HybridRetriever auto-loads
  rag/chroma_db/<profile>/
  rag/graphs/<profile>.json
       │
       ▼
  AI calibration agent uses
  the right RAG silently
```

The key auto-detection step is in `_check_rag_alignment()` in `orchestrator.py`. It runs at every orchestrator start.

---

## What A2MC does when it can't auto-match

If your FATES checkout doesn't fit any registered milestone, the selector reports `mode: rebuild_needed` and `rag_match.py` recommends a concrete next step. Three scenarios:

### Scenario T1: You're at the exact milestone commit

`rag_match.py` says `T1 (metadata refresh only). Use milestone X as-is.` Nothing else to do; A2MC will pick it up automatically. Optional: `python scripts/build_rag_index.py --record-metadata-only --profile <name>` to refresh the build timestamp.

### Scenario T2: Same api epoch, different commit

You've moved a few commits past (or behind) the milestone but stayed within the same `api.X.Y` epoch (e.g., milestone built at `sci.1.91.1`, you're at `sci.1.91.4`). The wiki and parameter file structure are still valid; just the commit-level details may differ.

```bash
python scripts/rag_bump.py --target-milestone <existing-milestone-name> --mode prompt-pack
```

For T2, `--mode prompt-pack` runs `build_rag_index.py --rebuild --graph-only` directly. No AI calls needed.

### Scenario T3: Different api epoch entirely

You're on `api.45.0` but only `api-43-1` and `api-31-0` are registered. The wiki must be regenerated against your new source. Pick an execution mode based on what you have:

| Mode | Requires | Cost | Speed |
|---|---|---|---|
| `--mode prompt-pack` | Any AI assistant (Claude Code, Claude.ai, ChatGPT, etc.) — you drive each prompt yourself | Free | Slowest |
| `--mode api` | Anthropic / OpenAI / CBorg API key (see `A2MC_AI_PROVIDER` config) | ~$5–15 | Medium |
| `--mode auto` | Same as `api` plus willingness to auto-deploy drafts | Same | Fastest |

```bash
# T3 example — bumping to a hypothetical api-45-0
python scripts/rag_bump.py --target-milestone api-45-0 --mode prompt-pack

# Or if you want API-driven:
python scripts/rag_bump.py --target-milestone api-45-0 --mode api --confirm-spend

# Or fully automated:
python scripts/rag_bump.py --target-milestone api-45-0 --mode auto --confirm-spend
```

The cost guardrail blocks runs over $5 unless you pass `--confirm-spend`.

---

## Where the version-association data lives

```
rag/
├── chroma_db/<profile>/         ChromaDB vector store per profile
├── graphs/<profile>.json         Knowledge graph per profile
├── metadata/<profile>.json       Profile metadata (commit SHAs, file hashes, stats)
├── data/
│   ├── curated_relationships.yaml                canonical (active dev)
│   ├── curated_relationships_<profile>.yaml      frozen per-milestone snapshot
└── milestones.json                                registry of all profiles
```

Each milestone is **self-contained**: own ChromaDB, own graph, own metadata, own curated YAML. Rebuilding milestone X from its frozen YAML reproduces the same graph A2MC has been using — important for paper-target reproducibility (e.g., the api-31-0 Kougarok manuscript milestone).

---

## Listing what's registered

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

`canonical` = default for new builds. `legacy` = preserved for paper reproducibility (don't rebuild against modern YAML). `local` = the artifacts exist on disk. `ACTIVE` = the currently-loaded profile.

---

## Inspecting commit drift before deciding

`rag_match.py` walks `git log` between the milestone's pinned commit and your checkout's commit. Useful when you've moved a few commits and want to know what actually changed:

```bash
python scripts/rag_match.py
```

Sample output for a user a few commits past `api-43-1`:

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

This lets you make an informed call: "those 7 commits are unrelated to my calibration → ignore the T2 recommendation and proceed" or "one commit changed a parameter I'm calibrating → run the bump."

---

## Verifying everything is healthy

After any setup change or bump, run the full verification suite:

```bash
python scripts/verify_phase4.py
```

Healthy output:

```
api-31-0:  7/7 gates pass
api-43-1:  8/8 gates pass
smoke:     9/9 pass
```

A detailed report drops at `docs/a2mc_reference/phase4_verification.md`. Any Red row points at a specific failure to investigate.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `EnvironmentError: A2MC_MODEL_PATH is required` | Site config not sourced | `source use_cases/<site>/config/<site>_config.sh` |
| `A2MC_RAG_ACTIVE is required` from a RAG module | Calling RAG modules outside the orchestrator | `export A2MC_RAG_ACTIVE=<profile>` |
| Loader prints "WARNING: explicit wiki_subdir 'X' not found" | Wiki subdir name in metadata doesn't match disk | Check `rag/metadata/<profile>.json` against `ls docs/*-knowledge-base/` |
| `mode: no_match` | No milestone covers your checkout's epoch | Run `rag_bump.py --target-milestone api-<your-epoch>` |
| Cost guardrail blocks an API run | Estimated > $5 | Add `--confirm-spend` if you accept the cost, or use `--mode prompt-pack` instead |

---

## Quick reference: the four scripts

| Script | What it does | When to run |
|---|---|---|
| `scripts/rag_list.py` | Show all registered milestones + active profile | When you want to see what's available |
| `scripts/rag_match.py` | Diagnose your checkout vs milestones; show git-log drift | When `rag_list` says you're at an unfamiliar commit |
| `scripts/rag_bump.py` | Run a T1 / T2 / T3 bump; three execution modes | When `rag_match.py` says you need a rebuild |
| `scripts/verify_phase4.py` | Run all content-correctness gates + smoke tests | After any setup change or bump |

---

## Going deeper

- **`version_association_workflow.md`** — comprehensive reference. Covers maintainer workflows (registering a new milestone, freezing per-milestone YAMLs, promoting canonical), the per-milestone YAML reproducibility principle, recipe library (A1-A5), and known limitations.
- **`rag_build_roadmap.md`** — what `build_rag_index.py` does internally. Read this if a bump fails and you need to understand the build pipeline.
- **`codebase_wiki_generation_roadmap.md`** — Step 1 of the adapter kit; what a "wiki" must contain and how to regenerate one against a new commit.
- **`graphrag_curated_yaml_roadmap.md`** — Step 3 of the adapter kit; the curated YAML's role and how to evolve it.
- **`rag_validation_workflow.md`** — Step 4 of the adapter kit; the three-tier validation toolkit (codebase_wiki, yaml_wiki, rag_diff).

---

## Why we built this

A2MC originally relied on a single RAG/GraphRAG built against one FATES commit, with the wiki dir selected via a symlink. This was fragile:

- Silent failures: switch the symlink wrong and everything still "runs" but with the wrong content.
- Single-user: only one wiki target on disk at a time.
- No rebuild path: when FATES bumped, users had no automation to refresh the RAG.

Phase 4 of `docs/18_ELM_FATES_Version_Association_Plan.md` solved this by making versions first-class:

- A user's checkout is a query → which registered milestone fits? (rag_match.py)
- A milestone is a versioned, self-contained artifact set (chroma_db + graph + metadata + curated YAML).
- A bump is an orchestrated workflow with three execution modes (rag_bump.py).

End result: A2MC now correctly auto-detects "I need the api.31.0 RAG for this Kougarok run" or "I need the api.43.1 RAG for this E3SM-master run" without you having to think about it.
