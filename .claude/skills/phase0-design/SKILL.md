---
name: phase0-design
description: Run Phase 0 (DESIGN) of the A2MC calibration workflow as the offline agent — the human-in-the-loop analog of the orchestrator's `_run_design()`. Sample the parameter space (Morris/Sobol/LHS), materialize one FATES parameter file per case, generate + build + submit the ensemble, and arm monitoring. Use when the user says "design a new round", "set up the ensemble", "sample the parameters", "submit the Morris ensemble", "start a calibration round", "expand the parameter space (redesign)".
---

# Phase 0: Design & Submit (offline agent)

The offline analog of the orchestrator's `_run_design()`. Online this is deterministic sampling +
submission; offline **you own the design decisions** the online loop takes from config — scheme,
trajectory count, which parameters vary, bounds, and whether this is a fresh round or a
redesign/replay. The underlying scripts are the same the online agent drives.

> **Floor, not ceiling.** This skill is the minimum to stand up a round the way the online agent
> would. As the offline agent you can do more: reconsider the parameter list itself, add or widen
> bounds a redesign implies, sanity-check the sampling against prior-round μ* before spending
> compute, or design a targeted sub-ensemble the fixed loop would never propose. Match the
> discipline (verify param existence, don't clobber the committed matrix, validate before submit),
> then exercise judgment about *what* to sample.

**Deliverable:** simulation jobs queued (ADSP→RGSP→TRANS dependency chains), `submission_manifest.json`
written, monitoring armed.

## Step 1 — sample the parameter space (parameter-file prep — no simulations)

`phases/phase0_design/create_parameter_sample.py --method {morris|sobol|lhs}` reads
`$A2MC_PARAM_LIST_FILE` (name + bounds) and writes the ensemble matrix (`$A2MC_ENSEMBLE_MATRIX_FILE`)
and SALib problem (`$A2MC_SALIB_PROBLEM_FILE`). Morris: `--trajectories T` (N = T×(P+1)).

> **Footgun — matrix overwrite.** `$A2MC_ENSEMBLE_MATRIX_FILE` for Kougarok points at the
> **committed, byte-stable 4890-set matrix the manuscript depends on**. To regenerate without
> clobbering it, write to a scratch path (`--output-matrix`) or repoint the env var to a fresh
> round file first.

**Redesign / replay** (reuse a prior round's NC dir instead of fresh sampling):
`apply_param_override.py` (global override, e.g. R5's `prescribed_puptake=1.0` onto R3's NCs) or
`create_subset_replay.py` (top-N replay preserving source case numbers).

## Step 2 — materialize per-case parameter files (parameter-file prep — no simulations)

`phases/phase0_design/create_morris_ensemble.py` reads the X matrix + `$A2MC_BASE_PARAM_FILE` and
writes one NetCDF per row into `$A2MC_PARAM_DIR` (pattern `$A2MC_PARAM_PATTERN`, `{N}` placeholder).
Verify file count = N_sets.

> **Footgun — site-specific column order.** `build_modifications_list()` in
> `create_morris_ensemble.py` hardcodes Kougarok's exact 162-column mapping (PFT#7→#9→#10, 2-organ
> retrans params, `nfix1` PFT#9-only). Porting to a new site requires rewriting it. Never assume a
> column's meaning.

## Step 3 — generate scripts, build, submit the simulations

`phases/phase0_design/submit_phase0.py --start 1 --end N --dry-run` first (preview), then `--submit`.
It (3a) writes per-case scripts via `tools/create_case.sh --write-script`, (3b) auto-validates via
`tools/validate_submission_plan.py`, (3c.1) builds ONE case fresh (~30 min), (3c.2) runs the rest in
`--batch-size` parallel batches reusing the build's `bld/`. Non-sequential rounds: `--cases-file`.

> **Footgun — build-case reuse.** All cases share the build case's `bld/`. If the build case fails,
> every dependent case is orphaned — confirm it completed before the batch. Restart it separately,
> then `--skip-build-case --build-case N`.

## Step 4 — arm monitoring, don't idle-wait

Launch `tools/ensemble_auto_monitor.sh` (queue polling + auto extraction kick + milestone plots),
then hand monitoring setup to `arm-hpc-monitoring` (CLAUDE.md Rule #6). Point-in-time completion:
`tools/diagnose_ensemble_status.py --cases 1-N` (writes completed/incomplete lists + a validated
restart script). Infrastructure failures → `restart-failed-jobs`; model failures need a fix first.

## Step 5 — log it and hand off

Log via `calibration-log` (phase log → `PhaseLogger.log_design`): scheme, N cases, param dir,
manifest hash, any redesign rationale. **Hand off** to `phase1-exploration` once TRANS is >95%
complete. (Arrived here from Phase 6 with all candidates pinned at bounds? That's the 6→0 redesign —
widen bounds / add parameters and start a new `calibration_round`.)

## Related skills / next phase

- **Monitoring the in-flight ensemble** → `arm-hpc-monitoring`. **Failed jobs** → `restart-failed-jobs`.
- **Rebuilding a new site/model's knowledge base first** → `build-rag-from-scratch`.
- **Next:** `phase1-exploration` (extract Y matrix + Morris sensitivity).

## Changelog

- 2026-07-02: Created — offline Phase 0 routine mirroring `_run_design()`; drives create_parameter_sample → create_morris_ensemble → submit_phase0, delegates monitoring/restart, hands off to `phase1-exploration`.
