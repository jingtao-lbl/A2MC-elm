#!/usr/bin/env python3
"""Scaffold a calibration_rounds.yaml round entry FROM the sourced A2MC configs.

`calibration_rounds.yaml` records, per calibration round, the parameter count,
ensemble size, artifact paths, targets, protocol, and model milestone. Every one
of those is already defined in `a2mc_config.sh` + the site config — so hand-typing
the YAML invites drift (a wrong param count or a stale path silently mis-routes a
phase). This tool DERIVES the round block from the live config environment instead,
leaving only the narrative fields (rationale, changes_from_previous, outcome) as
TODO for the human.

Usage (source BOTH configs first — the standard A2MC invocation):
    source a2mc_config.sh
    source use_cases/<site>/config/<site>_config.sh
    python tools/generate_calibration_rounds.py --round 1            # print to stdout
    python tools/generate_calibration_rounds.py --round 1 --write    # merge into the yaml

Pairs with tools/check_calibration_rounds.py (validates an existing YAML vs the
live config). Author: Jing Tao with Claude.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _env(name: str, required: bool = True, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if required and (v is None or v == ""):
        sys.exit(f"ERROR: {name} is unset. Source a2mc_config.sh + the site config first.")
    return v or ""


def _repo_root() -> Path:
    # A2MC_USE_CASE_DIR = <root>/use_cases/<site>; root is two levels up.
    ucd = _env("A2MC_USE_CASE_DIR")
    return Path(ucd).resolve().parent.parent


def _rel(path: str, root: Path) -> str:
    """Repo-relative path for in-repo files; unchanged (or ${VAR}-templated) otherwise."""
    if not path:
        return path
    try:
        return str(Path(path).resolve().relative_to(root))
    except ValueError:
        return path  # outside the repo (e.g. an $A2MC_OUTPUT_ROOT path)


def _templated_output(path: str, out_root: str) -> str:
    """Re-template an absolute output path back to ${A2MC_OUTPUT_ROOT}/... form."""
    if path and out_root and path.startswith(out_root):
        return "${A2MC_OUTPUT_ROOT}" + path[len(out_root):]
    return path


def _templated_scripts(path: str) -> str:
    """Re-template the scripts dir against ${A2MC_SCRIPTS_DIR}, mirroring _templated_output."""
    root = os.environ.get("A2MC_SCRIPTS_DIR", "")
    if root and path.startswith(root):
        return "${A2MC_SCRIPTS_DIR}" + path[len(root):]
    return path


# ── The derivable / authored split ────────────────────────────────────────────────────
# Everything this generator emits is DERIVED from the sourced config, so re-running it must
# be idempotent. But a round record also accumulates fields no config can produce: the
# rationale a human wrote, and — after the round runs — the `outcome` the agent writes at the
# Phase-6 gate. Before 2026-08-02 `--write` did `doc["rounds"][n] = rnd`, a wholesale replace,
# so re-running it on a completed round silently destroyed all of that (measured on a copy of
# the live R1 record: 3 paths dropped, both model commits and the #17 `patches` note reset to
# TODO, plus rationale and changes_from_previous). These are never overwritten on an EXISTING
# round; on a NEW round the generator's TODO placeholders are useful scaffolding.
AUTHORED_KEYS = {
    "outcome", "outcome_leafroot_basis",     # agent-written at the Phase-6 gate
    "status", "completed_date",              # round lifecycle
    "rationale", "changes_from_previous", "notes",
    "key_cases", "verification_note", "provenance", "total_cases",
    "pi_decision_required", "reopened",      # PI gate / re-entry markers
    "source_round", "source_top_n", "source_ranking_metric",   # subset-replay rounds
}
# Sub-keys inside a generated block that are still authored. `patches` is the sharp one: it
# records the model-build dependency a round needs (e.g. the #17 per-PFT phen split for para169)
# and no config exports it.
AUTHORED_SUBKEYS = {
    # `binary` = {archive_label, sha256_prefix}: which archived executable this round is bound to.
    # AUTHORED, because it is written after the build is archived (model-evolution step 4.5) and
    # nothing about the checkout tells the generator which archive label was chosen. Cross-checked
    # by `tools/binary_archive_manifest.py --verify` (M7).
    "fates_source": {"patches", "branch", "base_commit", "patched_commit", "binary"},
    "ecosim_source": {"patches", "branch", "fork", "binary"},
    "overrides": None,                       # None = preserve the whole block if present
}


def _is_placeholder(v) -> bool:
    """A generated value carrying no information — must never overwrite a real one.

    `_detect_milestone_commits` degrades to 'TODO' when the model checkout is unreachable
    (routinely, on a laptop with the checkout on HPC), and unset env vars derive to ''. Without
    this guard a `--write` from the wrong machine would quietly reset a round's recorded
    milestone and commits to TODO.
    """
    return v is None or v == "" or v == [] or (isinstance(v, str) and v.strip().startswith("TODO"))


def merge_round(existing: dict, generated: dict, changes: list | None = None) -> dict:
    """Overwrite only the DERIVED fields of `existing`; preserve everything authored.

    Idempotent by construction: re-running against an unchanged config is a no-op, and against
    a changed config updates exactly the fields the config owns. Every overwrite of a differing
    value is appended to `changes` so the caller can SHOW the drift instead of applying it
    silently — the config is the authority, but a surprising overwrite should still be visible.
    """
    if not existing:
        return generated
    out = dict(existing)

    def _set(container, key, new, path):
        old = container.get(key)
        if _is_placeholder(new) and not _is_placeholder(old):
            return                                       # never downgrade to a placeholder
        if old != new and changes is not None:
            changes.append((path, old, new))
        container[key] = new

    for k, v in generated.items():
        if k in AUTHORED_KEYS and k in existing:
            continue                                     # never clobber an authored field
        if isinstance(v, dict) and isinstance(existing.get(k), dict):
            keep = AUTHORED_SUBKEYS.get(k, set())
            if keep is None:                             # preserve the whole block
                continue
            merged = dict(existing[k])
            for sk, sv in v.items():
                if sk not in keep:
                    _set(merged, sk, sv, f"{k}.{sk}")
            out[k] = merged
        else:
            _set(out, k, v, k)
    return out


def _derive_targets(targets_file: str) -> list[str]:
    """Group targets.yaml PFT keys into 'PFT<id>_a, PFT<id>_b' lines (best-effort)."""
    try:
        import yaml
        with open(targets_file) as f:
            doc = yaml.safe_load(f) or {}
        keys = list((doc.get("targets") or doc).keys())
        by_pft: dict[str, list[str]] = {}
        for k in keys:
            if isinstance(k, str) and k.startswith("PFT") and "_" in k:
                pft, _, var = k.partition("_")
                by_pft.setdefault(pft, []).append(k)
        if by_pft:
            return [", ".join(v) for v in by_pft.values()]
    except Exception:
        pass
    return ["TODO: list this round's targets (see validation_targets_file)"]


def _detect_milestone_commits(model_path: str) -> tuple[str, str, str]:
    """(milestone, fates_commit, elm_commit) — best-effort; 'TODO' on any failure."""
    milestone = os.environ.get("A2MC_RAG_ACTIVE", "") or "TODO"
    fates_c = elm_c = "TODO"
    try:
        sys.path.insert(0, str(_repo_root()))
        from tools.model_version import detect_model_version  # type: ignore
        mv = detect_model_version(Path(model_path))
        fates_c = mv.fates.commit_short or "TODO"
        elm_c = mv.elm.commit_short or "TODO"
    except Exception:
        pass
    return milestone, fates_c, elm_c


def build_round(round_num: int, milestone_override: str | None) -> dict:
    root = _repo_root()
    n_params = int(_env("A2MC_N_PARAMS"))
    scheme = _env("A2MC_SAMPLING_SCHEME")
    traj = int(_env("A2MC_N_TRAJECTORIES", required=False, default="30"))
    total = os.environ.get("A2MC_TOTAL_ENSEMBLE", "")
    ensembles = int(total) if total.isdigit() else traj * (n_params + 1)
    out_root = _env("A2MC_OUTPUT_ROOT")
    name = _env("A2MC_ENSEMBLE_NAME")
    targets_file = _env("A2MC_VALIDATION_TARGETS")
    milestone, fates_c, elm_c = _detect_milestone_commits(_env("A2MC_MODEL_PATH"))
    if milestone_override:
        milestone = milestone_override

    def sup(phase: str, nutrient: str) -> str:
        return _env(f"A2MC_{phase}_{nutrient}", required=False, default="NONE")

    return {
        "parameters": n_params,
        "ensembles": ensembles,
        "trajectories": traj,
        "sampling_scheme": scheme,
        "config_file": _rel(_env("A2MC_SITE_CONFIG", required=False,
                                 default=str(Path(_env("A2MC_USE_CASE_DIR")) / "config")), root),
        "paths": {
            "ensemble_name": name,
            "ensemble_output": _templated_output(_env("A2MC_ENSEMBLE_OUTPUT", required=False,
                                                       default=f"{out_root}/{name}"), out_root),
            "extracted_data": _templated_output(_env("A2MC_EXTRACTED_DATA", required=False,
                                                      default=f"{out_root}/{name}_Extract"), out_root),
            "param_list": _rel(_env("A2MC_PARAM_LIST_FILE"), root),
            "salib_problem": _rel(_env("A2MC_SALIB_PROBLEM_FILE"), root),
            "param_dir": _templated_output(_env("A2MC_PARAM_DIR", required=False, default=""), out_root),
            "param_pattern": _env("A2MC_PARAM_PATTERN", required=False, default=""),
            "case_name_pattern": _env("A2MC_CASE_NAME_PATTERN"),
            "case_scripts": _templated_scripts(_env("A2MC_CASE_SCRIPTS", required=False, default="")),
        },
        "targets": _derive_targets(targets_file),
        "validation_targets_file": _rel(targets_file, root),
        "protocol": {
            "suplphos": {"ADSP": sup("ADSP", "SUPLPHOS"), "RGSP": sup("RGSP", "SUPLPHOS"),
                         "TRANS": sup("TRANS", "SUPLPHOS")},
            "suplnitro": {"ADSP": sup("ADSP", "SUPLNITRO"), "RGSP": sup("RGSP", "SUPLNITRO"),
                          "TRANS": sup("TRANS", "SUPLNITRO")},
        },
        "elm_options": _env("A2MC_ELM_OPTIONS", required=False, default=""),
        "overrides": {},
        "fates_source": {
            "milestone": milestone,
            "fates_commit": fates_c,
            "elm_commit": elm_c,
            "checkout": _env("A2MC_MODEL_PATH"),
            "patches": [],  # TODO: confirm whether the checkout carries custom patches
        },
        "changes_from_previous": [f"TODO: what changed vs round {round_num - 1}" if round_num > 1
                                  else "First round on this lineage."],
        "rationale": "TODO: why this round is designed as it is.",
        "outcome": None,
        "status": "planned",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--round", type=int, default=1, help="calibration round number")
    ap.add_argument("--milestone", default=None, help="override milestone (else A2MC_RAG_ACTIVE / autodetect)")
    ap.add_argument("--write", action="store_true",
                    help="merge into ${A2MC_USE_CASE_DIR}/config/calibration_rounds.yaml (else print)")
    args = ap.parse_args()

    import yaml
    rnd = build_round(args.round, args.milestone)

    if not args.write:
        print(yaml.safe_dump({"rounds": {args.round: rnd}}, sort_keys=False, default_flow_style=False))
        print("# (derivable fields from config; TODO fields need human input. "
              "Re-run with --write to merge into calibration_rounds.yaml.)", file=sys.stderr)
        return

    yaml_path = Path(_env("A2MC_USE_CASE_DIR")) / "config" / "calibration_rounds.yaml"
    doc = {}
    header = ""
    if yaml_path.exists():
        text = yaml_path.read_text()
        # Preserve the leading comment block. yaml.safe_dump cannot round-trip comments, so
        # without this every --write silently strips the file's "what this file is" header.
        # (Inline per-key comments are still lost — that needs ruamel.yaml, which is not a
        # dependency here. Keep durable explanation in the header block, not inline.)
        lead = []
        for line in text.splitlines(True):
            if line.strip() == "" or line.lstrip().startswith("#"):
                lead.append(line)
            else:
                break
        header = "".join(lead)
        doc = yaml.safe_load(text) or {}
    doc.setdefault("rounds", {})
    existing = doc["rounds"].get(args.round)
    if existing:
        kept = sorted(k for k in existing if k in AUTHORED_KEYS)
        print(f"NOTE: round {args.round} already exists in {yaml_path.name} — refreshing only the "
              f"DERIVED fields. Preserved: {', '.join(kept) or '(none)'}"
              f"{' + <model>_source.patches' if 'patches' in str(existing) else ''}"
              # name `binary` too, or a round-trip looks like it dropped the round's build claim
              f"{' + <model>_source.binary' if 'binary' in str(existing) else ''}", file=sys.stderr)
    changes: list = []
    doc["rounds"][args.round] = merge_round(existing, rnd, changes)
    if changes:
        print(f"\n  {len(changes)} derived field(s) refreshed from the live config:", file=sys.stderr)
        for path, old, new in changes:
            print(f"    {path}\n       was: {str(old)[:88]}\n       now: {str(new)[:88]}", file=sys.stderr)
        print("  Review these: the config is the runtime authority, so a surprise here means the "
              "config drifted, not the record.\n", file=sys.stderr)
    with open(yaml_path, "w") as f:
        if header:
            f.write(header)
        yaml.safe_dump(doc, f, sort_keys=False, default_flow_style=False)
    print(f"Wrote round {args.round} to {yaml_path}")
    if not existing:
        print("Fill the TODO fields (rationale, changes_from_previous, patches) by hand, then run "
              "tools/check_calibration_rounds.py to confirm it matches the config.")
    else:
        print("Authored fields (rationale, outcome, status, patches, …) were preserved. "
              "Run tools/check_calibration_rounds.py to confirm it matches the config.")


if __name__ == "__main__":
    main()
