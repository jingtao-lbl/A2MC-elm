#!/Library/Frameworks/Python.framework/Versions/3.10/bin/python3
"""
rag_bump.py - Orchestrate a RAG profile bump (T1 / T2 / T3).

Decides which bump tier applies to a user's checkout (vs a target milestone)
and runs the appropriate workflow:

    T1: same epoch, sha matches      -> metadata refresh only.
    T2: same epoch, sha differs      -> partial rebuild (graph + vector).
    T3: different epoch              -> full new-epoch wiki regen + rebuild.

Three execution modes (--mode flag):

    prompt-pack   Plan + a structured set of markdown files in
                  Offline/bump_pack_<target>/ that the user runs through
                  Claude Code, Claude.ai, or any AI of their choice. No AI
                  credentials or network access needed. Default mode.

    api           Same plan + script calls Anthropic / OpenAI / CBorg API
                  directly to execute Phase 2 wiki regen in parallel.
                  Reuses A2MC's reasoning/base.py AI provider abstraction.
                  Requires the matching API key env var.

    auto          Mode `api` + auto-runs Phase 1 prep (E3SM clone + FATES
                  submodule init) + Phase 3 build + Phase 3.5 validators
                  in a loop until Green. Most automation; highest cost.

This is the ELM-FATES-specific orchestrator. Adapter-kit (separate branch)
will generalize the model assumptions baked in here:

    - E3SM submodule layout (`components/elm/src/external_models/fates/`)
    - FATES api.X.Y_sci.Z.Z.Z tagging methodology
    - JSON param file at `parameter_files/fates_params_default.json` (api.43+),
      CDL extracted from `.nc` (api.31)
    - Wiki structure: 10 FATES topics + 6 ELM topics
    - ELM coupling required (FATES wiki cross-references ELM source)

Usage examples:
    # Plan only — see what would happen for a hypothetical api-45-0 bump
    python scripts/rag_bump.py --target-milestone api-45-0 --mode prompt-pack --dry-run

    # T1 metadata refresh against current api-43-1 milestone
    python scripts/rag_bump.py --target-milestone api-43-1 --mode prompt-pack

    # T2 partial rebuild (after a parameter file change in same epoch)
    python scripts/rag_bump.py --target-milestone api-43-1 --mode auto

    # T3 full bump to a new epoch (writes the prompt pack)
    python scripts/rag_bump.py --target-milestone api-44-0 --mode prompt-pack \\
        --basis api-43-1

Author: Jing Tao with Claude
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "tools"))

from model_version import detect_model_version, ModelPathError, ELMFATESVersion  # noqa: E402
from rag_manifest import load_manifest, Milestone  # noqa: E402
from rag_metadata import compute_file_sha  # noqa: E402
from rag_selector import (  # noqa: E402
    select_rag, classify_bump_tier, get_milestone_param_sha,
)


# =============================================================================
# Bump plan dataclass
# =============================================================================

@dataclass
class BumpPlan:
    """Concrete dispatch plan for a bump. Drives all three modes."""
    target_milestone: str          # name of milestone to produce
    basis_milestone: Optional[str] # nearest existing milestone to clone from
    tier: str                      # 'T1' | 'T2' | 'T3'
    user_version: ELMFATESVersion
    target_api_epoch: str
    target_fates_commit: str
    target_elm_commit: str

    fates_topics: List[str] = field(default_factory=list)  # 10 FATES wiki topics
    elm_topics: List[str] = field(default_factory=list)    # 6 ELM wiki topics

    # Files that will be created
    output_chroma_dir: str = ""
    output_graph_path: str = ""
    output_metadata_path: str = ""
    output_fates_wiki_subdir: str = ""
    output_elm_wiki_subdir: str = ""
    frozen_curated_yaml: str = ""

    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target_milestone": self.target_milestone,
            "basis_milestone": self.basis_milestone,
            "tier": self.tier,
            "user_version": self.user_version.to_dict(),
            "target_api_epoch": self.target_api_epoch,
            "target_fates_commit": self.target_fates_commit,
            "target_elm_commit": self.target_elm_commit,
            "fates_topics": list(self.fates_topics),
            "elm_topics": list(self.elm_topics),
            "output_chroma_dir": self.output_chroma_dir,
            "output_graph_path": self.output_graph_path,
            "output_metadata_path": self.output_metadata_path,
            "output_fates_wiki_subdir": self.output_fates_wiki_subdir,
            "output_elm_wiki_subdir": self.output_elm_wiki_subdir,
            "frozen_curated_yaml": self.frozen_curated_yaml,
            "notes": list(self.notes),
        }


# =============================================================================
# Topic taxonomy (mirrors Phase 2 dispatch on this branch)
# =============================================================================

FATES_WIKI_TOPICS = [
    "Overview + Getting Started",
    "Architecture",
    "Core Dynamics",
    "Canopy Structure",
    "Plant Physiology",
    "PARTEH",
    "Biophysics",
    "Fire",
    "Logging + Output",
    "Advanced",
]

ELM_WIKI_TOPICS = [
    "Overview + Source Tree",
    "Core + Driver",
    "Biogeochemistry",
    "Biogeophysics",
    "Hydrology",
    "Land Use + Dynamic Subgrid",
]


# =============================================================================
# Plan construction
# =============================================================================

def build_plan(
    user_version: ELMFATESVersion,
    target_milestone: str,
    basis_milestone: Optional[str],
    tier: str,
    rag_dir: Path,
) -> BumpPlan:
    """Construct a BumpPlan from detected user state + target/basis names."""
    target_epoch = user_version.fates_api_epoch or "?"

    plan = BumpPlan(
        target_milestone=target_milestone,
        basis_milestone=basis_milestone,
        tier=tier,
        user_version=user_version,
        target_api_epoch=target_epoch,
        target_fates_commit=user_version.fates.commit_sha,
        target_elm_commit=user_version.elm.commit_sha,
        fates_topics=list(FATES_WIKI_TOPICS),
        elm_topics=list(ELM_WIKI_TOPICS),
        output_chroma_dir=str(rag_dir / "chroma_db" / target_milestone),
        output_graph_path=str(rag_dir / "graphs" / f"{target_milestone}.json"),
        output_metadata_path=str(rag_dir / "metadata" / f"{target_milestone}.json"),
        output_fates_wiki_subdir=f"fates-codebase-wiki-{user_version.fates.commit_short}",
        output_elm_wiki_subdir=f"elm-codebase-wiki-{user_version.elm.commit_short}",
        frozen_curated_yaml=f"rag/data/curated_relationships_{target_milestone}.yaml",
    )

    if tier == "T1":
        plan.notes.append(
            "T1 bump: same epoch, parameter file unchanged. "
            "Only refresh metadata for the existing milestone artifacts."
        )
    elif tier == "T2":
        plan.notes.append(
            "T2 bump: same epoch, parameter file changed within epoch. "
            "Re-run graph build (parameters changed) and re-add CDL definitions "
            "to ChromaDB. Wiki content remains valid."
        )
    elif tier == "T3":
        plan.notes.append(
            "T3 bump: new api epoch. Wiki regen required: 10 FATES + 6 ELM "
            "topics must be rewritten against the new source. After wiki regen, "
            "rebuild graph + ChromaDB + write metadata + freeze curated YAML "
            "snapshot. v2.96+ note: also re-extract the ELM output CDL via "
            "`python scripts/extract_elm_outputs.py --elm-src <path>/components/elm/src "
            "--elm-commit <new-elm-commit-short>` and re-extract the FATES output "
            "registry CDL (matching the FATES wiki regen workflow). Register both "
            "in milestones.json under the new milestone's `fates_output_cdl` and "
            "`elm_output_cdl` fields."
        )

    return plan


# =============================================================================
# Mode A: prompt-pack
# =============================================================================

PROMPT_HEADER_TEMPLATE = """# RAG Bump: {target} ({tier})

**Generated:** {built_at}
**User checkout:** `{model_path}`
**FATES commit:** `{fates_short}` ({fates_describe})
**ELM commit:** `{elm_short}` ({elm_describe})
**Target api epoch:** `{api_epoch}`
**Basis milestone:** `{basis}`

---

## Pre-flight notes

{notes}

---

## Output paths

- ChromaDB:   `{chroma}`
- Graph JSON: `{graph}`
- Metadata:   `{metadata}`
- FATES wiki: `docs/fates-knowledge-base/{fates_subdir}/`
- ELM wiki:   `docs/elm-knowledge-base/{elm_subdir}/`
- Curated YAML snapshot: `{frozen_yaml}`
"""


def _make_topic_prompt(plan: BumpPlan, kb_label: str, topic: str,
                       basis_wiki_path: Optional[Path]) -> str:
    """One topic prompt for Mode A. User feeds it to Claude / their AI of choice."""
    short = (
        plan.user_version.fates.commit_short
        if kb_label == "FATES" else plan.user_version.elm.commit_short
    )
    repo_label = "FATES" if kb_label == "FATES" else "ELM"
    source_subdir = (
        "components/elm/src/external_models/fates/"
        if kb_label == "FATES" else "components/elm/src/"
    )
    return f"""# Wiki Regen Topic: {kb_label} -- {topic}

You are rewriting a section of A2MC's {kb_label} codebase wiki against the
source pinned at commit `{short}`. Output goes to:

    docs/{kb_label.lower()}-knowledge-base/{plan.output_fates_wiki_subdir if kb_label == 'FATES' else plan.output_elm_wiki_subdir}/<topic-subdir>/*.md

## Source root

```
{plan.user_version.model_path}/{source_subdir}
```

## Workflow

1. Read the basis wiki for this topic (if available) at:
     {basis_wiki_path or '(no basis wiki available — greenfield)'}
2. Verify each claim against the actual {repo_label} source at
   the new commit.
3. Use the workflow described in
   `docs/a2mc_reference/codebase_wiki_generation_roadmap.md`:
     - Workflow A (greenfield) if no basis wiki exists
     - Workflow B (audit + rewrite) if basis wiki exists
4. Every substantive claim must carry a `(file:line)` citation that
   resolves at this commit.
5. Output one or more .md files under the topic subdir matching
   the basis wiki's structure.

## Validation

After all topics are rewritten, run:

```bash
python tools/codebase_wiki_validator.py \\
    --wiki docs/{kb_label.lower()}-knowledge-base/{plan.output_fates_wiki_subdir if kb_label == 'FATES' else plan.output_elm_wiki_subdir} \\
    --source {plan.user_version.model_path}/{source_subdir.rstrip('/')} \\
    --output docs/a2mc_reference/wiki_source_validation_{kb_label.lower()}_{short}.md
```

Aim for Green across all 5 dimensions.
"""


def write_prompt_pack(plan: BumpPlan, output_dir: Path) -> List[Path]:
    """Mode A: write the bump plan + per-topic prompt files. Returns paths written."""
    output_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []

    # Locate basis wiki paths
    basis_fates_wiki = None
    basis_elm_wiki = None
    if plan.basis_milestone:
        manifest = load_manifest(_REPO_ROOT / "rag" / "milestones.json")
        basis = manifest.get(plan.basis_milestone)
        if basis:
            if basis.fates_wiki_subdir:
                basis_fates_wiki = (
                    _REPO_ROOT / "docs" / "fates-knowledge-base" / basis.fates_wiki_subdir
                )
            if basis.elm_wiki_subdir:
                basis_elm_wiki = (
                    _REPO_ROOT / "docs" / "elm-knowledge-base" / basis.elm_wiki_subdir
                )

    # Master plan file
    plan_md = output_dir / "PLAN.md"
    notes_text = "\n".join(f"- {n}" for n in plan.notes)
    header = PROMPT_HEADER_TEMPLATE.format(
        target=plan.target_milestone,
        tier=plan.tier,
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        model_path=plan.user_version.model_path,
        fates_short=plan.user_version.fates.commit_short,
        fates_describe=plan.user_version.fates.describe or "(no describe)",
        elm_short=plan.user_version.elm.commit_short,
        elm_describe=plan.user_version.elm.describe or "(no describe)",
        api_epoch=plan.target_api_epoch,
        basis=plan.basis_milestone or "(none — greenfield)",
        notes=notes_text or "(none)",
        chroma=plan.output_chroma_dir,
        graph=plan.output_graph_path,
        metadata=plan.output_metadata_path,
        fates_subdir=plan.output_fates_wiki_subdir,
        elm_subdir=plan.output_elm_wiki_subdir,
        frozen_yaml=plan.frozen_curated_yaml,
    )
    if plan.tier == "T3":
        topics_listing = "\n".join(
            [f"### FATES topics ({len(plan.fates_topics)})"]
            + [f"- `fates_{i+1:02d}_{t.replace(' + ', '_').replace(' ', '_').lower()}.md`"
               for i, t in enumerate(plan.fates_topics)]
            + [f"\n### ELM topics ({len(plan.elm_topics)})"]
            + [f"- `elm_{i+1:02d}_{t.replace(' + ', '_').replace(' ', '_').lower()}.md`"
               for i, t in enumerate(plan.elm_topics)]
        )
    else:
        topics_listing = "(N/A: T1/T2 do not require wiki regen)"

    plan_md_content = (
        header
        + "\n## Per-topic prompts\n\n"
        + topics_listing
        + "\n\n## After all topics complete\n\n"
        + "1. Run `tools/codebase_wiki_validator.py` for both wikis (commands at "
          "the bottom of each topic prompt). Iterate until Green.\n"
        + "2. Freeze a curated YAML snapshot:\n"
          f"     `cp rag/data/curated_relationships.yaml {plan.frozen_curated_yaml}`\n"
        + "   Edit the snapshot to match the new api epoch's parameter / mechanism\n"
          "   names. Run `tools/yaml_wiki_validator.py` until Green.\n"
        + "3. Build the new RAG profile:\n"
          f"     `python scripts/build_rag_index.py --rebuild --profile {plan.target_milestone}`\n"
        + "4. Register as milestone (canonical or legacy as appropriate):\n"
          f"     Add an entry to `rag/milestones.json` for `{plan.target_milestone}`.\n"
        + "5. Run `tools/rag_diff.py` against the basis milestone to sanity-check\n"
          "   the bump.\n"
    )

    plan_md.write_text(plan_md_content, encoding="utf-8")
    written.append(plan_md)

    # Per-topic prompts (T3 only)
    if plan.tier == "T3":
        topics_dir = output_dir / "topics"
        topics_dir.mkdir(exist_ok=True)
        for i, topic in enumerate(plan.fates_topics, start=1):
            slug = topic.replace(" + ", "_").replace(" ", "_").lower()
            p = topics_dir / f"fates_{i:02d}_{slug}.md"
            p.write_text(
                _make_topic_prompt(plan, "FATES", topic, basis_fates_wiki),
                encoding="utf-8",
            )
            written.append(p)
        for i, topic in enumerate(plan.elm_topics, start=1):
            slug = topic.replace(" + ", "_").replace(" ", "_").lower()
            p = topics_dir / f"elm_{i:02d}_{slug}.md"
            p.write_text(
                _make_topic_prompt(plan, "ELM", topic, basis_elm_wiki),
                encoding="utf-8",
            )
            written.append(p)

    # plan.json — machine-readable for re-driving with --mode api / auto later
    plan_json = output_dir / "plan.json"
    plan_json.write_text(
        json.dumps(plan.to_dict(), indent=2, default=str), encoding="utf-8"
    )
    written.append(plan_json)

    return written


# =============================================================================
# Mode A T1/T2 helpers (no wiki regen needed; just metadata or partial rebuild)
# =============================================================================

def execute_t1_metadata_refresh(plan: BumpPlan) -> int:
    """T1: just call build_rag_index.py --record-metadata-only."""
    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "build_rag_index.py"),
        "--record-metadata-only",
        "--profile", plan.target_milestone,
        "--model-path", plan.user_version.model_path,
    ]
    print(f"\nRunning: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(_REPO_ROOT))
    return result.returncode


def execute_t2_partial_rebuild(plan: BumpPlan) -> int:
    """T2: call build_rag_index.py --rebuild --graph-only (param file changed,
    wiki content unchanged so vector index stays valid; graph/metadata refresh)."""
    cmd = [
        sys.executable,
        str(_REPO_ROOT / "scripts" / "build_rag_index.py"),
        "--rebuild",
        "--graph-only",
        "--profile", plan.target_milestone,
        "--model-path", plan.user_version.model_path,
    ]
    print(f"\nRunning: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(_REPO_ROOT))
    return result.returncode


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Orchestrate a RAG profile bump (T1/T2/T3)."
    )
    parser.add_argument(
        "--target-milestone", required=True,
        help="Milestone name to produce (e.g., 'api-45-0').",
    )
    parser.add_argument(
        "--basis", default=None,
        help="Existing milestone to use as basis for wiki content (T3). If "
             "omitted, the selector picks the nearest milestone.",
    )
    parser.add_argument(
        "--mode", choices=["prompt-pack", "api", "auto"],
        default="prompt-pack",
        help="Execution mode (default: prompt-pack).",
    )
    parser.add_argument(
        "--model-path", type=Path, default=None,
        help="E3SM checkout root. Defaults to $A2MC_MODEL_PATH.",
    )
    parser.add_argument(
        "--rag-dir", type=Path,
        default=os.environ.get("A2MC_RAG_DIR") or str(_REPO_ROOT / "rag"),
        help="RAG storage root.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Where to write the prompt pack (default: "
             "Offline/bump_pack_<target>/).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Plan only; do not execute or write files (still prints the plan).",
    )
    parser.add_argument(
        "--confirm-spend", action="store_true",
        help="Required when estimated API cost exceeds $5 (--mode api / auto only).",
    )
    args = parser.parse_args()

    # 1. Detect user version
    model_path = args.model_path
    if model_path is None:
        env = os.environ.get("A2MC_MODEL_PATH")
        if not env:
            print("ERROR: A2MC_MODEL_PATH not set and --model-path not given.",
                  file=sys.stderr)
            sys.exit(2)
        model_path = Path(env)
    model_path = model_path.resolve()
    try:
        version = detect_model_version(model_path)
    except ModelPathError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Load manifest, run selector, classify tier
    manifest = load_manifest(_REPO_ROOT / "rag" / "milestones.json")
    sel = select_rag(version, manifest)

    user_param_sha_matches = False
    if sel.milestone:
        ms_sha = get_milestone_param_sha(args.rag_dir, sel.profile_name)
        fates_root = (
            model_path / "components" / "elm" / "src" / "external_models" / "fates"
        )
        fmt = sel.milestone.fates_param_file_format
        user_param = fates_root / "parameter_files" / f"fates_params_default.{fmt}"
        if user_param.exists() and ms_sha:
            user_param_sha_matches = (compute_file_sha(user_param) == ms_sha)
    classification = classify_bump_tier(sel, user_param_sha_matches)
    tier = classification.tier

    # Resolve basis: either user-supplied or selector's nearest
    basis_milestone = args.basis or (sel.profile_name if sel.profile_name else None)

    # 3. Build plan
    plan = build_plan(
        version, args.target_milestone, basis_milestone, tier, args.rag_dir
    )

    # 4. Print plan summary
    print()
    print("=" * 60)
    print(f"  Bump plan: {plan.target_milestone} ({plan.tier})")
    print("=" * 60)
    print(f"  User FATES:    {version.fates.commit_short}  ({version.fates.describe})")
    print(f"  User ELM:      {version.elm.commit_short}  ({version.elm.describe or 'no describe'})")
    print(f"  Target epoch:  {plan.target_api_epoch}")
    print(f"  Basis:         {plan.basis_milestone or '(none)'}")
    print(f"  Mode:          {args.mode}")
    if args.dry_run:
        print(f"  Dry run:       YES (no execution)")
    print()
    for n in plan.notes:
        print(f"  - {n}")
    print()

    if args.dry_run:
        # Print machine-readable plan and exit
        print(json.dumps(plan.to_dict(), indent=2, default=str))
        return

    # 5. Mode dispatch
    if args.mode == "prompt-pack":
        if tier == "T1":
            print("T1 bump: prompt-pack mode runs metadata refresh directly "
                  "(no AI work needed).")
            sys.exit(execute_t1_metadata_refresh(plan))
        if tier == "T2":
            print("T2 bump: prompt-pack mode runs partial rebuild directly "
                  "(no AI work needed).")
            sys.exit(execute_t2_partial_rebuild(plan))
        # T3 — write prompt pack
        out_dir = args.output_dir or (_REPO_ROOT / "Offline" / f"bump_pack_{plan.target_milestone}")
        written = write_prompt_pack(plan, out_dir)
        print(f"\nPrompt pack written ({len(written)} files) under: {out_dir}/")
        for p in written[:5]:
            print(f"  {p.relative_to(_REPO_ROOT)}")
        if len(written) > 5:
            print(f"  ... and {len(written) - 5} more")
        print(
            f"\nNext steps: open `{out_dir / 'PLAN.md'}` and follow the workflow. "
            f"For each topic prompt, run it through Claude Code / Claude.ai / "
            f"any AI of choice and save the resulting wiki content under the "
            f"output paths."
        )
        return

    if args.mode == "api":
        if tier == "T1":
            print("T1 bump: api mode is no different from prompt-pack mode "
                  "(no AI call needed). Running metadata refresh.")
            sys.exit(execute_t1_metadata_refresh(plan))
        if tier == "T2":
            print("T2 bump: api mode is no different from prompt-pack mode "
                  "(no AI call needed). Running partial rebuild.")
            sys.exit(execute_t2_partial_rebuild(plan))
        # T3 — call API for each topic
        out_dir = args.output_dir or (_REPO_ROOT / "Offline" / f"bump_pack_{plan.target_milestone}")
        # First, write the prompt pack so prompts exist on disk
        write_prompt_pack(plan, out_dir)
        sys.exit(execute_t3_api_mode(plan, out_dir, args))

    if args.mode == "auto":
        if tier == "T1":
            print("T1 bump: auto mode is just metadata refresh. Running.")
            sys.exit(execute_t1_metadata_refresh(plan))
        if tier == "T2":
            print("T2 bump: auto mode is just partial rebuild. Running.")
            sys.exit(execute_t2_partial_rebuild(plan))
        # T3 — full automation
        out_dir = args.output_dir or (_REPO_ROOT / "Offline" / f"bump_pack_{plan.target_milestone}")
        write_prompt_pack(plan, out_dir)
        sys.exit(execute_t3_auto_mode(plan, out_dir, args))


# =============================================================================
# Mode B: API-driven (sequential)
# =============================================================================

def estimate_t3_api_cost(plan: BumpPlan) -> dict:
    """Rough cost estimate for a T3 bump in API mode.

    Assumes ~5k input tokens per topic prompt + ~5k output tokens per response.
    16 topics total. Uses Opus-tier pricing as the conservative ceiling
    ($15/M input, $75/M output). Real cost depends on the configured model
    and provider.
    """
    n_topics = len(plan.fates_topics) + len(plan.elm_topics)
    input_tokens = n_topics * 5000
    output_tokens = n_topics * 5000
    cost_opus_input = input_tokens / 1_000_000 * 15.0
    cost_opus_output = output_tokens / 1_000_000 * 75.0
    return {
        "n_topics": n_topics,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_opus_usd": round(cost_opus_input + cost_opus_output, 2),
    }


_WIKI_REGEN_SYSTEM_PROMPT = """You are an expert assistant rewriting an A2MC \
codebase wiki section against a pinned source-code commit.

Constraints:
- Output Markdown only. No conversational preamble.
- Every substantive claim must carry a `(file:line)` citation that resolves \
at the pinned commit. If you cannot verify a claim from your training data, \
either omit it or flag it as "needs verification".
- Match the basis wiki's section structure if one is available.
- Do NOT invent module names or routine names. If you don't know the real \
name, write a placeholder with TODO and a description of what should go there.
- Each topic should produce one or more .md files. If multiple, name them \
by sub-topic (e.g., `mortality.md`, `phenology.md`).
"""


def execute_t3_api_mode(plan: BumpPlan, prompt_pack_dir: Path, args) -> int:
    """T3 in API mode: sequentially call AI for each topic prompt and save
    responses as draft wiki content under Offline/bump_pack_<target>/drafts/.

    User reviews drafts, then deploys to docs/<kb>-knowledge-base/<subdir>/.
    """
    # Cost guardrail
    cost = estimate_t3_api_cost(plan)
    print()
    print(f"Estimated API cost (Opus pricing ceiling): ${cost['cost_opus_usd']}")
    print(f"  ({cost['n_topics']} topics x ~5k input + 5k output tokens each)")
    print(f"  Real cost depends on your A2MC_AI_PROVIDER + A2MC_AI_MODEL.")

    if cost["cost_opus_usd"] > 5.0 and not getattr(args, "confirm_spend", False):
        print(
            f"\nERROR: estimated cost ${cost['cost_opus_usd']} > $5 threshold. "
            f"Re-run with --confirm-spend to proceed.",
            file=sys.stderr,
        )
        return 4
    print()

    # Lazy import — avoid cost if user only wants prompt-pack
    try:
        from reasoning.base import ReasoningModule
    except ImportError as e:
        print(f"ERROR: cannot import reasoning.base: {e}", file=sys.stderr)
        return 5

    # Subclass with a wiki-regen-specific system prompt + RAG disabled
    class _WikiRegenClient(ReasoningModule):
        SYSTEM_PROMPT = _WIKI_REGEN_SYSTEM_PROMPT

    try:
        client = _WikiRegenClient(use_rag=False)
    except Exception as e:
        print(f"ERROR: could not initialize AI client: {e}", file=sys.stderr)
        return 5
    print(f"AI client ready: provider={client.provider}, model={client.model}")
    print()

    # Iterate through topic prompts
    topics_dir = prompt_pack_dir / "topics"
    drafts_dir = prompt_pack_dir / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    if not topics_dir.exists():
        print(f"ERROR: topic prompts not found at {topics_dir}", file=sys.stderr)
        return 6

    topic_files = sorted(topics_dir.glob("*.md"))
    if not topic_files:
        print(f"ERROR: no .md prompts found in {topics_dir}", file=sys.stderr)
        return 6

    print(f"Running {len(topic_files)} topic prompts sequentially...")
    print()

    failures = 0
    for i, topic_path in enumerate(topic_files, start=1):
        topic_name = topic_path.stem
        prompt = topic_path.read_text(encoding="utf-8")
        print(f"[{i}/{len(topic_files)}] {topic_name}", flush=True)
        try:
            response = client.query(prompt, max_tokens=8192)
        except Exception as e:
            print(f"   FAILED: {e}", flush=True)
            failures += 1
            continue
        draft_path = drafts_dir / f"{topic_name}_draft.md"
        draft_path.write_text(response, encoding="utf-8")
        print(f"   -> {draft_path.relative_to(_REPO_ROOT)}  ({len(response)} chars)",
              flush=True)

    print()
    print(f"Done. {len(topic_files) - failures}/{len(topic_files)} drafts written.")
    if failures > 0:
        print(f"WARNING: {failures} topics failed; re-run after fixing.")
        return 7

    print()
    print(f"Drafts written under: {drafts_dir}/")
    print(
        "Next steps:\n"
        "  1. Review each draft for correctness (especially file:line citations).\n"
        "  2. Move accepted drafts to "
        f"docs/fates-knowledge-base/{plan.output_fates_wiki_subdir}/ and "
        f"docs/elm-knowledge-base/{plan.output_elm_wiki_subdir}/.\n"
        "  3. Run tools/codebase_wiki_validator.py for both wikis until Green.\n"
        "  4. Continue to step 2 (curated YAML freeze) of the PLAN.md workflow."
    )
    return 0


# =============================================================================
# Mode C: full automation
# =============================================================================

def execute_t3_auto_mode(plan: BumpPlan, prompt_pack_dir: Path, args) -> int:
    """T3 in auto mode: run Mode B (API draft generation) + auto-deploy
    drafts to wiki paths + run codebase_wiki_validator + freeze curated
    YAML snapshot + build the new RAG profile + run yaml_wiki_validator
    + register in milestones.json.

    This is the highest-automation mode. User still reviews the final
    validator reports for unfixable hallucinations, but everything in
    between is automated.

    Skips Phase 1 prep (E3SM clone + FATES submodule init): assumes the
    user already has the source checkout at A2MC_MODEL_PATH. Cloning
    arbitrary E3SM checkouts is best done by the user manually because
    NERSC vs local paths, disk space, and submodule init flags vary.
    """
    print()
    print("=" * 60)
    print("  AUTO MODE: full T3 bump automation")
    print("=" * 60)
    print()
    print("Workflow:")
    print("  1. Run Mode B (API draft generation)")
    print("  2. Auto-deploy drafts to docs/<kb>-knowledge-base/<subdir>/")
    print("  3. Run codebase_wiki_validator (FATES + ELM)")
    print("  4. Freeze curated YAML snapshot")
    print("  5. Build the new RAG profile (build_rag_index.py --rebuild)")
    print("  6. Run yaml_wiki_validator")
    print("  7. Register milestone in rag/milestones.json")
    print()

    # Step 1: Mode B draft generation
    print("--- Step 1: AI draft generation (Mode B) ---")
    rc = execute_t3_api_mode(plan, prompt_pack_dir, args)
    if rc != 0:
        print(f"\nDraft generation failed (rc={rc}). Aborting auto mode.")
        return rc

    # Step 2: Deploy drafts
    print("\n--- Step 2: Deploy drafts to wiki paths ---")
    drafts_dir = prompt_pack_dir / "drafts"
    fates_wiki_root = (
        _REPO_ROOT / "docs" / "fates-knowledge-base" / plan.output_fates_wiki_subdir
    )
    elm_wiki_root = (
        _REPO_ROOT / "docs" / "elm-knowledge-base" / plan.output_elm_wiki_subdir
    )
    fates_wiki_root.mkdir(parents=True, exist_ok=True)
    elm_wiki_root.mkdir(parents=True, exist_ok=True)
    deployed = 0
    for draft in sorted(drafts_dir.glob("*_draft.md")):
        # fates_05_plant_physiology_draft.md  ->  fates-side, basename plant_physiology.md
        stem = draft.stem.replace("_draft", "")
        if stem.startswith("fates_"):
            # Strip leading 'fates_NN_' prefix
            parts = stem.split("_", 2)
            wiki_name = (parts[2] if len(parts) > 2 else stem) + ".md"
            target = fates_wiki_root / wiki_name
        elif stem.startswith("elm_"):
            parts = stem.split("_", 2)
            wiki_name = (parts[2] if len(parts) > 2 else stem) + ".md"
            target = elm_wiki_root / wiki_name
        else:
            continue
        shutil.copy2(draft, target)
        deployed += 1
        print(f"  {draft.name} -> {target.relative_to(_REPO_ROOT)}")
    print(f"  Deployed {deployed} drafts.")

    # Step 3: codebase_wiki_validator
    print("\n--- Step 3: codebase_wiki_validator ---")
    fates_source = (
        Path(plan.user_version.model_path) / "components" / "elm" / "src"
        / "external_models" / "fates"
    )
    elm_source = (
        Path(plan.user_version.model_path) / "components" / "elm" / "src"
    )
    fates_short = plan.user_version.fates.commit_short
    elm_short = plan.user_version.elm.commit_short

    fates_validator_report = (
        _REPO_ROOT / "docs" / "a2mc_reference"
        / f"wiki_source_validation_fates_{fates_short}.md"
    )
    elm_validator_report = (
        _REPO_ROOT / "docs" / "a2mc_reference"
        / f"wiki_source_validation_elm_{elm_short}.md"
    )
    # FATES wiki validation
    cmd = [
        sys.executable, str(_REPO_ROOT / "tools" / "codebase_wiki_validator.py"),
        "--wiki", str(fates_wiki_root),
        "--source", str(fates_source),
        "--output", str(fates_validator_report),
    ]
    # If a JSON param file is co-located with the FATES commit, pass it
    fates_param_json = (
        _REPO_ROOT / "docs" / "fates-knowledge-base"
        / f"fates_params_info_{fates_short}.json"
    )
    if fates_param_json.exists():
        cmd.extend(["--param-file", str(fates_param_json)])
    print(f"  Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(_REPO_ROOT), check=False)

    # ELM wiki validation
    cmd = [
        sys.executable, str(_REPO_ROOT / "tools" / "codebase_wiki_validator.py"),
        "--wiki", str(elm_wiki_root),
        "--source", str(elm_source),
        "--output", str(elm_validator_report),
    ]
    print(f"  Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(_REPO_ROOT), check=False)
    print(
        f"  Reports: {fates_validator_report.relative_to(_REPO_ROOT)}, "
        f"{elm_validator_report.relative_to(_REPO_ROOT)}"
    )
    print(
        "  Manual: review reports for any Red dimensions; iterate on prompts/"
        "drafts if needed before continuing."
    )

    # Step 4: Freeze curated YAML
    print("\n--- Step 4: Freeze curated YAML snapshot ---")
    canonical_yaml = _REPO_ROOT / "rag" / "data" / "curated_relationships.yaml"
    target_yaml = _REPO_ROOT / plan.frozen_curated_yaml
    if not target_yaml.exists():
        shutil.copy2(canonical_yaml, target_yaml)
        print(f"  {target_yaml.relative_to(_REPO_ROOT)} written from canonical.")
        print(
            "  Manual: edit this snapshot to reflect the new api epoch's "
            "param/mechanism naming. Then run "
            "`tools/yaml_wiki_validator.py` until Green."
        )
    else:
        print(f"  Already exists: {target_yaml.relative_to(_REPO_ROOT)} (skipping copy).")

    # Step 5: Build the new RAG profile
    print("\n--- Step 5: Build RAG profile ---")
    cmd = [
        sys.executable, str(_REPO_ROOT / "scripts" / "build_rag_index.py"),
        "--rebuild",
        "--profile", plan.target_milestone,
        "--model-path", plan.user_version.model_path,
    ]
    print(f"  Running: {' '.join(cmd)}")
    rc = subprocess.run(cmd, cwd=str(_REPO_ROOT)).returncode
    if rc != 0:
        print(f"  build_rag_index.py failed (rc={rc}). Aborting auto mode.")
        return rc

    # Step 6: yaml_wiki_validator
    print("\n--- Step 6: yaml_wiki_validator ---")
    yaml_report = (
        _REPO_ROOT / "docs" / "a2mc_reference"
        / f"yaml_wiki_validation_{plan.target_milestone}.md"
    )
    output_cdl = (
        _REPO_ROOT / "docs" / "fates-knowledge-base"
        / f"elm_fates_output_info_{fates_short}.cdl"
    )
    cmd = [
        sys.executable, str(_REPO_ROOT / "tools" / "yaml_wiki_validator.py"),
        "--yaml", str(target_yaml),
        "--wiki", str(fates_wiki_root),
        "--output", str(yaml_report),
    ]
    if fates_param_json.exists():
        cmd.extend(["--param-file", str(fates_param_json)])
    if output_cdl.exists():
        cmd.extend(["--output-cdl", str(output_cdl)])
    print(f"  Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(_REPO_ROOT), check=False)
    print(f"  Report: {yaml_report.relative_to(_REPO_ROOT)}")

    # Step 7: Register milestone (best-effort; user reviews entry)
    print("\n--- Step 7: Register milestone ---")
    try:
        from rag_manifest import (
            load_manifest, save_manifest, add_milestone, Milestone,
            list_sci_tags_for_epoch,
        )
        manifest = load_manifest(_REPO_ROOT / "rag" / "milestones.json")
        sci_tags = list_sci_tags_for_epoch(fates_source, plan.target_api_epoch)
        new_ms = Milestone(
            profile_name=plan.target_milestone,
            description=f"FATES api.{plan.target_api_epoch} epoch (auto-registered by rag_bump.py)",
            fates_api_epoch=plan.target_api_epoch,
            fates_tag_built=plan.user_version.fates.nearest_tag,
            fates_commit_built=plan.user_version.fates.commit_sha,
            fates_param_file_format=(
                "json" if fates_param_json.exists() else "cdl"
            ),
            elm_commit_built=plan.user_version.elm.commit_sha,
            elm_wiki_subdir=plan.output_elm_wiki_subdir,
            fates_wiki_subdir=plan.output_fates_wiki_subdir,
            covers_sci_tags=sci_tags,
            canonical=False,
            legacy=False,
            available_locally=True,
            published_at=datetime.now(timezone.utc).date().isoformat(),
            curated_yaml_path=plan.frozen_curated_yaml,
            notes="Auto-registered by scripts/rag_bump.py --mode auto. Set canonical=true manually if appropriate.",
        )
        add_milestone(manifest, new_ms, overwrite=True)
        save_manifest(manifest)
        print(f"  Milestone '{plan.target_milestone}' registered with {len(sci_tags)} sci tags.")
    except Exception as e:
        print(f"  Auto-registration failed: {e}")
        print("  Manual: edit rag/milestones.json directly.")

    print()
    print("=" * 60)
    print("  AUTO MODE COMPLETE")
    print("=" * 60)
    print(
        "Review the validator reports + the registered milestone entry "
        "before declaring victory. If any validator returned Red, iterate "
        "on the wiki content (manually or by re-running specific topics)."
    )
    return 0


if __name__ == "__main__":
    main()
