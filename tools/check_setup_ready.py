#!/usr/bin/env python3
"""Goal-conditional 'is this site ready for Phase 0?' preflight for A2MC setup.

Runs the full preparation checklist AFTER the user has sourced a2mc_config.sh + the
site config. It is deliberately GOAL-AWARE, not a rigid list: checks that don't apply
to the user's goal report N/A instead of failing.

  - PFT inventory is required ONLY for PFT-level targets (a MODIS/tower GPP goal that
    calibrates ecosystem fluxes needs no per-PFT breakdown -> N/A).
  - The simulation protocol (ADSP/RGSP/TRANS spin-up) is READ from config and reported,
    not required -- a user who doesn't care about BGC may run no spin-up.
  - FATES base param file / RAG milestone apply only when FATES is enabled.

Universal checks (always required): model path + milestone, site config overrides the
machine config, targets.yaml valid AND its targets mapped to model output variables
with a cost function established, parameter list present, calibration_rounds.yaml
present + consistent with the config (via tools/check_calibration_rounds.py).

Exit 0 = no failures (N/A and INFO don't fail); exit 1 = at least one FAIL.

Usage:
    source a2mc_config.sh
    source use_cases/<site>/config/<site>_config.sh
    python tools/check_setup_ready.py

Companion doc for the milestone step: docs/a2mc_reference/version_association_howto.md.
Author: Jing Tao with Claude.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PASS, FAIL, NA, INFO = "PASS", "FAIL", "NA", "INFO"
_MARK = {PASS: "✓", FAIL: "✗", NA: "–", INFO: "ℹ"}


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


def _root() -> Path:
    """Repo root. Falls back to this file's location when no config is sourced.

    The env route stays first so a sourced config still decides. The fallback is
    what lets STAGE 1 run at all — requiring A2MC_USE_CASE_DIR here is precisely
    why a pre-case clone had no runnable gate.
    """
    ucd = env("A2MC_USE_CASE_DIR")
    if ucd:
        return Path(ucd).resolve().parent.parent
    return Path(__file__).resolve().parent.parent


def _run(argv: list[str]) -> tuple[int, str]:
    try:
        out = subprocess.run(argv, capture_output=True, text=True, cwd=str(_root()))
        return out.returncode, (out.stdout or "") + (out.stderr or "")
    except Exception as e:  # pragma: no cover
        return 1, str(e)


def _load_targets() -> dict:
    tf = env("A2MC_VALIDATION_TARGETS")
    if not tf or not Path(tf).exists():
        return {}
    try:
        import yaml
        with open(tf) as f:
            doc = yaml.safe_load(f) or {}
        return doc.get("targets", {}) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Stage routing (added 2026-08-19)
#
# The per-CASE checks below need a sourced site config, so they cannot run
# before a case exists — which left Stage 1 (`a2mc-init`, the per-CLONE half)
# with no executable gate at all. Everything in _stage1() therefore reads the
# DISK, never the environment.
#
# The Stage-2 contract is unchanged: with a site config sourced, this behaves
# exactly as before and still exits 1 on any FAIL. Skills cite that.
# ---------------------------------------------------------------------------

_NOT_A_CASE = {"TEMPLATE", "__pycache__"}


def _real_cases(root: Path) -> list[str]:
    """Cases that are actual work — excludes TEMPLATE and any *_template seed."""
    d = root / "use_cases"
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir()
                  if p.is_dir() and p.name not in _NOT_A_CASE
                  and not p.name.endswith("_template"))


def _detect_stage(root: Path) -> int:
    """1 = per-clone setup unfinished; 2 = clone configured, audit the case.

    Checked on disk so this works with nothing sourced. A sourced site config
    is decisive for stage 2 — it means someone got that far.
    """
    if env("A2MC_USE_CASE_DIR") and env("A2MC_SITE_CONFIG"):
        return 2
    if not (root / "a2mc_config.sh").is_file():
        return 1
    # A2MC_MODEL_PATH may simply be UNSOURCED rather than unconfigured — a hook or a
    # bare shell has no config loaded, and treating that as stage 1 would report an
    # already-configured clone as unconfigured every time. Fall back to the DISK
    # signal: does a2mc_config.sh declare it? (Found 2026-08-19 when the SessionStart
    # port fired on a configured clone.)
    if not env("A2MC_MODEL_PATH"):
        cfg = root / "a2mc_config.sh"
        try:
            declared = "A2MC_MODEL_PATH=" in cfg.read_text()
        except OSError:
            declared = False
        if not declared:
            return 1
    return 2 if _real_cases(root) else 1


def _stage1(root: Path, py: str) -> int:
    """Per-CLONE readiness. Returns the FAIL count."""
    results: list[tuple[str, str, str]] = []

    mp = env("A2MC_MODEL_PATH")
    results.append((PASS if mp and Path(mp).exists() else FAIL,
                    "A2MC_MODEL_PATH set and exists",
                    mp or "<unset> — the orchestrator hard-fails without it"))

    cfg = root / "a2mc_config.sh"
    results.append((PASS if cfg.is_file() else FAIL, "a2mc_config.sh present",
                    str(cfg) if cfg.is_file() else "run a2mc-init Step 3"))

    if mp and Path(mp).exists():
        rc, out = _run([py, "scripts/rag_match.py"])
        sel = next((ln.strip() for ln in out.splitlines() if "Selection:" in ln), "")
        matched = rc == 0 and "no_match" not in out.lower()
        results.append((PASS if matched else FAIL,
                        "checkout matches a registered RAG milestone",
                        sel or "python scripts/rag_match.py"))
        # Fork-safety: pushing to upstream is the failure this prevents.
        rc_r, remotes = _run(["git", "-C", mp, "remote", "-v"])
        has_fork = "fork" in remotes
        origin_push_off = "DISABLED" in remotes or "no_push" in remotes
        results.append((PASS if (has_fork and origin_push_off) else FAIL,
                        "fork-safe remotes on the model checkout",
                        "fork set + origin push disabled" if (has_fork and origin_push_off)
                        else "a2mc-init Step 2b — verify BOTH directions, not just that a fork remote exists"))
    else:
        results.append((NA, "RAG milestone match", "needs A2MC_MODEL_PATH"))
        results.append((NA, "fork-safe remotes", "needs A2MC_MODEL_PATH"))

    # The write paths. tools/config.py raises when any of these is unset (v2.261 —
    # they used to fall back to the maintainer's own absolute paths), but "set" is
    # not "usable": an output root that does not exist, or exists and is read-only,
    # or is full, fails only when an ensemble is hours in and has already burned the
    # allocation. Checking existence AND writability here is what makes this gate
    # mean "ready to run" rather than "the variables are populated".
    for var, what, hint in (
        ("A2MC_E3SM_ROOT", "E3SM source root (CIME builds from it)",
         "a2mc-init Step 3 — usually the same path as A2MC_MODEL_PATH"),
        ("A2MC_OUTPUT_ROOT", "simulation output root",
         "a2mc-init Step 3 — a project/scratch allocation, not the home filesystem"),
        ("A2MC_SCRIPTS_DIR", "generated case scripts dir",
         "a2mc-init Step 3 — one script per ensemble member lands here"),
    ):
        val = env(var)
        if not val:
            results.append((FAIL, f"{var} set", f"<unset> — {hint}"))
            continue
        p = Path(val)
        if not p.is_dir():
            results.append((FAIL, f"{var} exists", f"{val} — no such directory"))
        elif not os.access(val, os.W_OK):
            # Read-only is the quiet one: the path resolves, so every "does it exist"
            # check passes and the failure lands at the first write instead.
            results.append((FAIL, f"{var} writable", f"{val} — exists but is NOT writable"))
        else:
            results.append((PASS, f"{var} exists and is writable", val))

    # Free space on the output root, reported not enforced: only the user knows how
    # big their ensemble is, and a shared filesystem's free space is not their quota.
    out = env("A2MC_OUTPUT_ROOT")
    if out and Path(out).is_dir():
        try:
            st = os.statvfs(out)
            free_gb = (st.f_bavail * st.f_frsize) / (1024 ** 3)
            results.append((INFO, "output root free space",
                            f"{free_gb:,.0f} GiB available at {out} — size this against your "
                            f"ensemble (see the site's quota command for your real limit)"))
        except OSError:
            pass

    cases = _real_cases(root)
    results.append((PASS if cases else INFO,
                    "a real case exists",
                    ", ".join(cases) if cases else "only TEMPLATE/ — next stage is onboard-case"))

    print("A2MC setup readiness — STAGE 1 (per-clone: a2mc-init)\n")
    for status, label, detail in results:
        line = f"    [{_MARK[status]}] {label}"
        if detail:
            line += f"   {detail}"
        print(line)
    n_fail = sum(1 for s, _, _ in results if s == FAIL)
    print()
    if n_fail:
        print(f"✗ {n_fail} check(s) FAILED — the clone is not configured. Resolve the ✗ items, "
              f"then re-run. Stage-2 (per-case) checks cannot run until this passes.")
    elif cases:
        print("✓ clone configured. Re-run with a site config sourced to audit the case (stage 2).")
    else:
        print("✓ clone configured. No case yet — next is `onboard-case`.")
    return n_fail


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Is this setup stage finished? (see the setup-discipline skill)")
    ap.add_argument("--stage", type=int, choices=(1, 2), default=None,
                    help="force a stage; default auto-detects from disk + env")
    args = ap.parse_args()

    root = _root()
    py = sys.executable

    stage = args.stage or _detect_stage(root)
    if stage == 1:
        sys.exit(1 if _stage1(root, py) else 0)

    if not env("A2MC_USE_CASE_DIR"):
        sys.exit("ERROR: stage-2 (per-case) checks need a sourced config — "
                 "source a2mc_config.sh + the site config first, "
                 "or run with --stage 1 for the per-clone checks.")

    fates_on = "fates" in env("A2MC_ELM_OPTIONS").lower() or bool(env("A2MC_FATES_PARTEH_MODE"))
    targets = _load_targets()
    pft_targets = {k: v for k, v in targets.items()
                   if isinstance(k, str) and k[:3] == "PFT" and "_" in k and k[3].isdigit()}
    pft_level = bool(pft_targets)

    results: list[tuple[str, str, str, str]] = []  # (group, status, label, detail)

    def add(group: str, status: str, label: str, detail: str = ""):
        results.append((group, status, label, detail))

    # ---- Universal ----
    mp = env("A2MC_MODEL_PATH")
    add("Model + milestone", PASS if mp and Path(mp).exists() else FAIL,
        "A2MC_MODEL_PATH set and exists", mp or "<unset>")

    if fates_on:
        rc, out = _run([py, "scripts/rag_match.py"])
        sel = next((ln.strip() for ln in out.splitlines() if "Selection:" in ln), "")
        matched = rc == 0 and "no_match" not in out.lower()
        add("Model + milestone", PASS if matched else FAIL,
            "checkout matches a registered RAG milestone",
            sel or "see: python scripts/rag_match.py (docs/a2mc_reference/version_association_howto.md)")
    else:
        add("Model + milestone", NA, "RAG milestone match", "FATES off — RAG milestone N/A")

    # site config overrides machine config
    sc = env("A2MC_SITE_CONFIG")
    site_ok = bool(sc) and Path(sc).exists() and bool(env("A2MC_ENSEMBLE_NAME")) and bool(env("A2MC_USE_CASE_DIR"))
    add("Config layering", PASS if site_ok else FAIL,
        "site config sourced + overrides a2mc_config.sh",
        f"A2MC_SITE_CONFIG={Path(sc).name if sc else '<unset>'}, ENSEMBLE_NAME={env('A2MC_ENSEMBLE_NAME') or '<unset>'}")

    # targets.yaml valid
    rc, out = _run([py, "tools/validate_targets_config.py"])
    add("Targets + cost fn", PASS if rc == 0 else FAIL, "validate_targets_config.py",
        "" if rc == 0 else "run it directly for details")

    # targets mapped to model output variables + cost function established
    if not targets:
        add("Targets + cost fn", FAIL, "targets present + mapped to output variables",
            "no targets found in targets.yaml")
    else:
        missing_var = [k for k, v in targets.items()
                       if not (isinstance(v, dict) and str(v.get("variable", "")).strip()
                               and "TODO" not in str(v.get("variable", "")))]
        def _has_obs(v):
            # valid if a scalar snapshot `observed`, OR a non-empty time-series `observations:` list
            if isinstance(v.get("observed"), (int, float)):
                return True
            obs = v.get("observations")
            return isinstance(obs, list) and len(obs) > 0
        missing_obs = [k for k, v in targets.items() if not (isinstance(v, dict) and _has_obs(v))]
        add("Targets + cost fn", PASS if not missing_var else FAIL,
            "every target mapped to a model output variable",
            "" if not missing_var else f"missing/placeholder `variable`: {missing_var}")
        add("Targets + cost fn", PASS if not missing_obs else FAIL,
            "every target has an observed value + uncertainty",
            "" if not missing_obs else f"missing numeric `observed`: {missing_obs}")
        # cost function established
        try:
            import yaml
            cc = (yaml.safe_load(open(env("A2MC_VALIDATION_TARGETS"))) or {}).get("cost_config", {}) or {}
        except Exception:
            cc = {}
        cost_ok = bool(cc.get("error_method")) and bool(cc.get("aggregation_method"))
        add("Targets + cost fn", PASS if cost_ok else FAIL, "cost function established (cost_config)",
            f"error_method={cc.get('error_method')}, aggregation={cc.get('aggregation_method')}"
            if cost_ok else "cost_config missing error_method/aggregation_method (confirm with user)")

    # parameter list + salib
    pl = env("A2MC_PARAM_LIST_FILE")
    add("Parameters", PASS if pl and Path(pl).exists() else FAIL,
        "parameter list file exists", Path(pl).name if pl else "<unset>")
    sp = env("A2MC_SALIB_PROBLEM_FILE")
    add("Parameters", PASS if sp and Path(sp).exists() else NA,
        "SALib problem file", (Path(sp).name if sp and Path(sp).exists()
                               else "not yet generated — Phase 0 create_parameter_sample.py writes it"))

    # calibration_rounds.yaml present + consistent
    cr = root / "use_cases" / Path(env("A2MC_USE_CASE_DIR")).name / "config" / "calibration_rounds.yaml"
    if not cr.exists():
        add("Round record", FAIL, "calibration_rounds.yaml exists",
            f"missing — generate: python tools/generate_calibration_rounds.py --round 1 --write")
    else:
        rc, out = _run([py, "tools/check_calibration_rounds.py"])
        add("Round record", PASS if rc == 0 else FAIL,
            "calibration_rounds.yaml consistent with config (check_calibration_rounds.py)",
            "" if rc == 0 else "mismatch — run check_calibration_rounds.py for the diff")

    # ---- Conditional ----
    if pft_level:
        pfts = env("A2MC_PFTS")
        base = env("A2MC_BASE_PARAM_FILE")
        valid_ids: set[int] = set()
        try:
            sys.path.insert(0, str(root))
            from tools.fates_utils import get_pft_names_from_file  # type: ignore
            valid_ids = set(get_pft_names_from_file(base).keys()) if base and Path(base).exists() else set()
        except Exception:
            pass
        want = {int(x) for x in pfts.split(",") if x.strip().isdigit()} if pfts else set()
        tgt_pfts = {int(v.get("pft")) for v in pft_targets.values() if isinstance(v, dict) and v.get("pft")}
        problems = []
        if not want:
            problems.append("A2MC_PFTS unset")
        if valid_ids and not want <= valid_ids:
            problems.append(f"A2MC_PFTS {sorted(want - valid_ids)} not in base file PFTs {sorted(valid_ids)}")
        if valid_ids and not tgt_pfts <= valid_ids:
            problems.append(f"target PFTs {sorted(tgt_pfts - valid_ids)} not in base file")
        add("PFT inventory (PFT-level goal)", PASS if not problems else FAIL,
            "A2MC_PFTS set + PFT ids valid in the base param file",
            f"A2MC_PFTS={pfts}" if not problems else "; ".join(problems))
    else:
        add("PFT inventory", NA, "PFT inventory / A2MC_PFTS",
            "ecosystem-level goal (no PFT-level targets) — PFT inventory not required")

    if fates_on:
        base = env("A2MC_BASE_PARAM_FILE")
        add("FATES base file", PASS if base and Path(base).exists() else FAIL,
            "FATES base parameter file exists", base or "<unset>")
    else:
        add("FATES base file", NA, "FATES base parameter file", "FATES off — N/A")

    # protocol is INFORMATIONAL (read from config, not required)
    def yr(p):
        return env(f"A2MC_{p}_YEARS", "0")
    proto = "; ".join(
        f"{p}: {yr(p)}yr suplP={env(f'A2MC_{p}_SUPLPHOS','NONE')}/suplN={env(f'A2MC_{p}_SUPLNITRO','NONE')}"
        for p in ("ADSP", "RGSP", "TRANS"))
    add("Simulation protocol", INFO, "configured protocol (confirm it matches the goal)", proto)

    # ---- report ----
    order = ["Model + milestone", "Config layering", "Targets + cost fn", "Parameters",
             "Round record", "PFT inventory (PFT-level goal)", "PFT inventory", "FATES base file",
             "Simulation protocol"]
    seen_groups = [g for g in order if any(r[0] == g for r in results)]
    print(f"A2MC setup readiness — site '{Path(env('A2MC_USE_CASE_DIR')).name}' "
          f"({'FATES' if fates_on else 'ELM-only'}, "
          f"{'PFT-level' if pft_level else 'ecosystem-level'} targets)\n")
    for g in seen_groups:
        print(f"  {g}:")
        for grp, status, label, detail in results:
            if grp != g:
                continue
            line = f"    [{_MARK[status]}] {label}"
            if detail:
                line += f"   {detail}"
            print(line)
    n_fail = sum(1 for _, s, _, _ in results if s == FAIL)
    print()
    if n_fail:
        print(f"✗ {n_fail} check(s) FAILED — not ready for Phase 0. Resolve the ✗ items above.")
        sys.exit(1)
    print("✓ setup is ready for Phase 0 (all applicable checks pass; N/A items don't apply to this goal).")


if __name__ == "__main__":
    main()
