---
name: model-evolution
visibility: public
category: model-dev
description: The general workflow for evolving the ELM/FATES model SOURCE — an algorithm/mechanism fix, a structural refactor, debug instrumentation, or a new parameter. Use when changing model code, not calibration params — "update the model code", "change/modify the FATES/ELM source", "add a mechanism/fix to FATES", "make a structural model change", "refactor the phenology/allocation code", "instrument the model". Umbrella that `add-fates-parameter` (the add-a-tunable-knob sub-recipe) routes up to. NOT for parameter-file tuning (that's calibration).
allowed-tools: [Read, Glob, Grep, Write, Edit, Bash]
modes:
  requires_fates: false      # covers ELM and/or FATES source; model-dev, not a calibration phase
  nutrient_pathway: any
  scope: [model-dev]
  summary: "The disciplined workflow for changing ELM/FATES source — branch, default-off, paired verify, log both streams, fork-only push."
---

# model-evolution — evolving the ELM/FATES source under the reproducibility discipline

A2MC's model runs against a versioned ELM-FATES checkout (main's anchor: api-43-1, E3SM `d40b843` / FATES
`e027a40`). *Changing model code* is not like editing a parameter file — it's a disciplined workflow so the
change is isolated, switch-gated, verified equal-to-baseline when off, logged where the public can see it,
and pushed only to the personal fork. This skill is that workflow; `add-fates-parameter` is the specialized
sub-recipe for the "add a tunable knob" case. Read the model-tree contract first: the model checkout's
`CLAUDE.md` §1 (its path is recorded in [[feedback_model_source_push_fork_only]]).

> **Decision — is this even a model-code change?** Tuning a value in a parameter file = **calibration**
> (Phase 0/5, not this skill). Changing *what the code does* (a mechanism, a loop, a cap, a new
> parameter's wiring) = **model evolution** = this skill. If the change is purely "add a new tunable/
> switchable knob," this skill's step 3 routes you into **`add-fates-parameter`** for the plumbing.

## The workflow (each step is a gate the next depends on)

**0. Branch by intent (not dogma).** A **small change you intend to keep** in the working model can go on
the working branch (`fork/master` for E3SM, `fork/main` for FATES). Use a **dedicated experiment branch**
cut from the anchor for **exploratory / A-B / reproducibility-sensitive** work — there, keep the pinned
baseline rebuildable and never edit the anchor in place. (Contract: `E3SM_FATES_api43/CLAUDE.md` §1a. This
is main's working-model policy; the frozen manuscript branch (demo/api-31) is stricter — always an
experiment branch.)

**1. Mechanism-first — GATE the build on evidence, don't assume.** *Wiring is easy; the control point is
where it fails.* Before paying for a structural change, verify **on existing data (cheap, no HPC)** that
the mechanism can actually move the target.
- Positive precedent (demo #17 `phen_gddthresh_c`): a partial-dependence analysis showed PFT9-leaf and
  PFT10-fineroot want *different* values of the shared parameter → decoupling it per-PFT is justified. The
  gate PASSED *before* any code was written.
- Negative precedent (demo #16 `max_plant_density`): Options A (per-event cap) and B (crown-area) were
  wired perfectly and **still failed** — wrong quantity controlled; only C (count-based) worked, found by
  **instrumentation** (debug dumps). When the right control point is unclear, **instrument first**
  (temporary debug output), analyze, *then* implement.
- Do not escalate to model-dev on an unverified assumption ([[feedback_performance_experiment_is_the_objective]]
  — earn model-dev only after the calibration loop is provably exhausted).

**2. Scope from source, THEN implement (comment `!Jing Tao:`).** *The real scope is routinely bigger than
the sketch — read before you write.* (demo #17: the "redimension a scalar + a phenology tweak" sketch was,
in the source, a ~6-file refactor + a restart-format change.)
- **Grep EVERY consumer** of the symbol/state you're touching first. Removing or redimensioning a variable
  breaks every reader you miss — a compile error at best, a silent wrong-answer at worst. (demo #17:
  `ED_val_phen_c` had one consumer; the *state* it feeds, `%cstatus`, had 15.) **Pick the tool from the
  filesystem the checkout is on:**
  ```bash
  # Personal workstation (local clone) — a filesystem walk is fine, and it sees submodules:
  grep -rn '<symbol>' --include='*.F90' "$A2MC_MODEL_PATH"

  # Shared HPC filesystem (NERSC /global, /pscratch, any site scratch) — recursive traversal is
  # PROHIBITED there ([[feedback_nersc_no_recursive_traversal]]); use the index instead:
  git -C "$A2MC_MODEL_PATH" grep --recurse-submodules -n '<symbol>' -- '*.F90'
  ```
  **If you take the `git grep` branch, `--recurse-submodules` is mandatory.** FATES is a git *submodule* of
  E3SM (`components/elm/src/external_models/fates`), and `git grep` stops at the submodule boundary:
  verified 2026-08-14 (twice, independently), `EDPftvarcon` returns **0** files from the E3SM root without
  the flag and **31** with it. `grep -r` never had this problem, because a filesystem walk descends into the
  submodule directory regardless — so the HPC-safe tool is the one needing extra care, not the reverse. A
  silent zero reads as "no consumers" and is exactly the miss this step exists to prevent
  ([[feedback_dont_assert_absence_from_one_grep]]). Note also that `git grep` searches only **tracked**
  files, so an untracked scratch `.F90` in the checkout is invisible to it.
  **This covers the harness's own search tool, not just the shell.** A coding agent's `Grep`/`Glob` tool is
  ripgrep doing a recursive walk, so aiming it at a checkout under `/global`/`/pscratch` is the same
  prohibited operation as typing `grep -r` — reach for `git grep` via Bash there instead. (On a personal
  workstation the tool is fine and is the better ergonomic choice.)
- **Verify the framework mechanism EXISTS — don't assume.** #17's sketch assumed `EDParamsMod` could hold a
  PFT-dimensioned param; the source showed it has no clean array-retrieve, so the param moved to the
  idiomatic per-PFT container `EDPftvarcon`. Read the actual register/retrieve path before choosing where a
  thing lives.
- **MIN vs FULL — a local change can be a bug if the quantity is coupled to global state.** A "minimal"
  local edit that leaves coupled downstream state inconsistent is not a shortcut. (#17: a per-cohort
  leaf-out gate was *not* viable — site-level status drives cohorts through two coupled channels, flush
  trigger + biomass target — so it had to become a full per-PFT state promotion.)
- **Find an existing working TEMPLATE in the same codebase and MIRROR it — don't invent.** #17's per-PFT
  cold-status refactor mirrors the already-working drought-deciduous `dstatus(maxpft)` design. Mirroring a
  proven pattern is far lower-risk than a fresh structural change; grep for an analogous feature first.
- For a genuinely large map, **fan out a read-only subagent** to enumerate consumers + the state coupling +
  the template — and if the checkout is on shared HPC scratch, state the constraint IN its prompt
  (`git grep --recurse-submodules` only, no `grep -r`/`find`). A subagent runs its own tool loop and does
  not inherit this rule from the parent session.

Then implement; every edited/added line gets a detailed `!Jing Tao:` comment — mechanism, units, value
choice, follow-ups ([[feedback_model_code_comment_jing_tao]]). This is the in-source audit trail.

**3. Switch-gate — DEFAULT-OFF = bit-for-bit baseline.** For a **reproducibility-sensitive or exploratory**
change, make it **default-off**: a no-op value or a switch such that a switch-off build reproduces the
baseline **bit-for-bit** (the *V0-at-equality* gate). If the change is a tunable/switchable knob, **promote
it to a FATES parameter → follow `add-fates-parameter`** for the declare/register/retrieve + every-param-
file wiring — a **scalar/global** knob goes in `EDParamsMod`, a **per-PFT** knob in `EDPftvarcon`
(`EDParamsMod` has no clean array-retrieve). (A small keep-it change on the working branch need not be
switch-gated — but you then can't V0-at-equality it against the anchor; build from the anchor for a clean
baseline.)

**4. Build.** Fresh build of the changed source (the code changed, so the executable must recompile). For a
subsequent multi-variant experiment on that build, reuse it per `offline-testing-workflow` Step 5 (one
build serves all param-file variants; `e3sm.exe` is phase-agnostic).

**5. Paired verification — ON vs OFF, before trusting anything.** For a switch-gated change, run it **ON**
(does the intended thing) *and* **OFF** (reproduces baseline) — do not interpret any result until the OFF
run confirms V0-at-equality (build/env/seed drift otherwise masquerades as signal).
- **If the change alters the restart or history I/O layout** (e.g. promoting a scalar to per-PFT changes
  the restart variable's *shape*), the V0-at-equality check **must be a fresh COLD-START chain** (a spin-up
  *is* a cold start), NOT a warm restart across the format boundary — and an old-format restart cannot be
  read across the change. Check whether your edit touches `FatesRestartInterfaceMod` /
  `FatesHistoryInterfaceMod` before planning the verification run.
- **Same-env PAIRED build — never diff against an *old* build.** A recompile can perturb FP
  (`E3SM_FATES_api43/CLAUDE.md` §1), so V0 is only meaningful between the change branch and its **parent
  built in the SAME env/session**. Clean control: `git diff <parent> <change-branch>` = **exactly the
  changed files**, so any output diff is attributable solely to the change. Diff the paired runs' science
  outputs for **exact** equality (`max|A−B| = 0`), excluding variables the change intentionally reshaped.
- **Build the same-env baseline with `tools/model_evolution/`** — CIME compiles FATES from the one fixed
  in-tree path (no per-case source override), so the baseline build needs a guarded in-place branch-switch
  on the checkout itself, not a `git worktree` or a hand-reconstructed `create_newcase` case:
  - `lib_guarded_switch.sh` — sourceable library, `guarded_switch_and_run()`: clean-tree hard-gate →
    `git checkout <target_ref>` in place → run your build command → `trap`-guaranteed restore to
    `<restore_ref>` on exit → optional "confirm-on-target" sanity grep. Works on the E3SM root or a
    submodule path (e.g. FATES) — pass whichever tree the change lives in.
  - `build_v0_case_via_create_case.sh` — wraps the guard around a **fresh cold-start chain** via the
    canonical `tools/create_case.sh`, so compset/res/domain/DATM_MODE/`ELM_USRDAT_NAME`/`ELM_BLDNML_OPTS`
    all come from the site config. Use for a V0-off vs. baseline chain.
  - `build_v0_case_via_clone.sh` — wraps the guard around `create_clone` **from an existing reference
    case**, which inherits that case's entire configuration in one step. Use when the V0 check should
    CONTINUE an existing case's restart (a short `CONTINUE_RUN` segment) rather than cold-start.
- **A scalar→per-PFT V0-off param broadcasts the baseline CASE's own value, not the code default.** If the
  promoted parameter is Morris-varied, the test case carries its *own* value — set **all PFTs to that
  scalar** so off = bit-baseline; the code default makes a *different* run, not a V0.
- **The V0 param file must carry EVERY registered param the build's lineage added — derive it from a
  *post-change* file, not the pristine ensemble/default file.** When experiment branches **stack**, the
  executable needs the *union* of all registered params added anywhere in the lineage. A V0 file built from
  the pristine Morris/default file silently drops them and the run **aborts at param read**
  (`check_var: <name> is not on dataset` → `ENDRUN` — a runtime abort, NOT a build error, so it slips past
  the compile gate). Build the V0/test file from the immediately-prior experiment's param file. This bites
  BOTH the OFF and the baseline file. (Driving failure: #17 phen-split V0 aborting on #16's missing
  `fates_max_plant_density`, demo `model_logs/20260709b`, `20260710a`.)
- **Compare with `tools/model_evolution/compare_v0.py`** — auto-detects netCDF vs. log-diff mode: if both
  run dirs have `*.elm.h0.*.nc` monthly history (a chain long enough to cross a write boundary), it diffs
  key science variables for exact equality (`max|A−B| = 0`) plus a broad sweep over all shared non-`_PF`
  variables; otherwise (e.g. a short `CONTINUE_RUN` segment with no history/restart output yet) it falls
  back to a gzip-aware, non-deterministic-line-stripped diff of `lnd.log`'s per-timestep prints — the only
  science-output stream a short run produces. For an HPC-run pair, `wait_and_compare_v0.sh` polls `squeue`
  for both case names (crash-detecting via `DependencyNeverSatisfied`) and invokes `compare_v0.py`
  automatically once both finish.

**6. Log it — in BOTH streams, because model_logs is not public.** The code reasoning + mechanism goes in
`memory/model_logs/` (see its `CLAUDE.md`) with the `!Jing Tao:` source comment. **AND restate the approach
in the public-eligible `use_cases/<site>/memory/logs/` calibration log** — `memory/model_logs/` is
**excluded from the public sync**, so the public record must be self-contained (define terms, restate the
approach, don't just point at model_logs).

**7. Push — fork only, NEVER upstream.** Push to your **own fork** of the model repo (your fork of
`NGEET/fates` for FATES, of `E3SM-Project/E3SM` for ELM), **never** the upstream repos themselves. On the
model clone the fork is the `fork` remote and `origin`'s push URL is a `DISABLE`d sentinel — so
`git push fork <branch>`; verify with `git -C <tree> remote -v` (origin push must be the DISABLE sentinel).
Full setup: the model checkout's `CLAUDE.md` §1a; [[feedback_model_source_push_fork_only]]. Contributing
upstream is a separate, deliberate PR.

## Footguns

- **Editing the anchor in place for a repro-sensitive change** — breaks the reproducibility baseline. Use an
  experiment branch for those; keep the anchor rebuildable.
- **Skipping default-off on a switch-gated change** — a change that alters baseline even when "off" makes the
  reference drift; the OFF run must be baseline-identical.
- **Trusting a run before V0-at-equality** — an "on" result is meaningless until the paired "off" run proves
  the harness reproduces baseline.
- **Assuming the mechanism moves the target** — build the gate (step 1) first; #16's A/B are the cautionary tale.
- **Assuming the scope is small / the framework mechanism exists** — the sketch under-counts. Grep every
  consumer and read the register/retrieve + state-coupling from source *before* editing; a structural change
  routinely spans several files + a restart-format change. Mirror an existing template, don't invent.
- **Pushing upstream** — a stray `git push origin`/`upstream` targets the community repo; the `DISABLE` guard
  blocks it, but keep the discipline.
- **Leaving the approach only in `model_logs/`** — it won't ship publicly; restate it in the calibration log.

## Cross-references

- **Sub-recipe:** `add-fates-parameter` (the "add a tunable/switchable knob" case — `EDParamsMod` scalar or
  `EDPftvarcon` per-PFT plumbing).
- Build reuse + paired-run pilots: `offline-testing-workflow` (Step 5 build reuse; the pilot pattern).
- Contract + memories: `E3SM_FATES_api43/CLAUDE.md` §1; [[feedback_model_code_comment_jing_tao]],
  [[feedback_model_source_push_fork_only]], [[feedback_performance_experiment_is_the_objective]].
- Model-dev-track adoption on main: `memory/dev_logs/20260709i_Model_Development_Track_Adoption.md`.
- **V0-at-equality tooling (main, generic):** `tools/model_evolution/` — `lib_guarded_switch.sh`,
  `build_v0_case_via_create_case.sh`, `build_v0_case_via_clone.sh`, `compare_v0.py`,
  `wait_and_compare_v0.sh`. Promoted 2026-08-18 from the phen_split #17 V0-check scripts
  (`use_cases/ELM-FATES_Kougarok/memory/phase_results/20260712_phen_split_v0_api43/`) plus the
  `PhosphorusBiochemMin_balance` perf-fix V0 check (`memory/model_logs/20260818a_*.md`); reflection log
  `memory/dev_logs/20260818a_Model_Evolution_V0_Tooling_Promoted_And_Skill_Updated.md`.
- Worked examples live on the **demo branch** (api-31): #16 `fates_max_plant_density`, #17 `phen_gddthresh_c`
  PFT-split — their logs live on the demo branch (under its `use_cases/{site}/memory/logs/`), not on main.

## Notes

- **Branch fit:** the *workflow* (branch-by-intent, default-off, paired verify, log-both-streams, fork-only
  push) is generic model-dev. The specific forks/paths are Jing's; the frozen-manuscript branch (demo) is
  stricter on step 0 (always an experiment branch).

## Changelog

- 2026-08-18: **Step 5's guarded-branch-switch V0 recipe is now backed by promoted, generic tooling**
  (`tools/model_evolution/`) instead of prose-only instructions + demo-branch worked scripts. Also named
  `compare_v0.py`'s new log-diff fallback mode for V0 checks too short to produce history/restart output.
  See `memory/dev_logs/20260818a_Model_Evolution_V0_Tooling_Promoted_And_Skill_Updated.md`.
- 2026-08-14: **Step 2's consumer-census command is now chosen by FILESYSTEM, and the `git grep` form
  carries a mandatory `--recurse-submodules`.** Signal: NERSC issued a formal "Improper Use of AI Agents on
  Shared Systems" warning (account suspension on repeat) against this account after this branch's own
  session ran unbounded `grep -r`/`find` calls against the E3SM/FATES checkout on shared NERSC scratch
  (`memory/dev_logs/20260814a_NERSC_Warning_Recursive_Grep_Find_On_Shared_Filesystem.md`) — and this exact
  step was *instructing* that call (`grep -rn '<symbol>' --include=*.F90`,
  [[feedback_nersc_no_recursive_traversal]]). The initial NERSC-response commit (`47f31206`) fixed the
  memory but missed this skill. The fix is **not** a blanket ban: on a personal workstation `grep -r` is
  unrestricted and remains correct, so the step now branches on the path root rather than the command
  name. The subtlety that makes this more than a search-and-replace: **FATES is a git submodule of E3SM**,
  so the HPC-safe substitute silently regresses — `git grep` for `EDPftvarcon` from the E3SM root returns
  **0** files without `--recurse-submodules` and **31** with it (verified twice, independently, 2026-08-14),
  whereas `grep -r` never had the problem because a filesystem walk descends into the submodule directory
  regardless. A naive substitution would have turned a compliance fix into the exact silent-zero miss this
  step exists to prevent. Also extends the constraint to the **subagent** bullet (a subagent runs its own
  tool loop and does not inherit the rule) and to the **harness `Grep`/`Glob` tools** (ripgrep is a
  recursive walk too). Re-authored from `adapter-kit`'s parallel fix (its own dev log:
  `memory/dev_logs_adapterkit/20260814a_NERSC_Traversal_Rule_Adopted_And_Scoped_By_Filesystem.md`) via
  `adopt-from-adapter-kit` — took only this hunk; adapter-kit's much larger same-day multi-model
  generalization of this skill (EcoSIM/PFLOTRAN/ATS support, Step 3.5 build-artifact preservation, V0
  self-validation) is out of scope for `main`, which has no non-FATES model checkouts.
- 2026-07-10: Ported demo `47ae78f`+`5d587ce` — Step 5 gained the **same-env PAIRED-build V0 methodology**
  ((a) V0 is only meaningful vs the parent built in the same env — a recompile perturbs FP — with
  `git diff <parent> <change>` = exactly the changed files as the clean control, then an exact-equality
  science-output diff; (b) build the same-env baseline via a **guarded in-place branch-switch** because a
  submodule worktree does not compose with CIME's fixed in-tree FATES path; (c) a scalar→per-PFT V0-off param
  broadcasts the case's own Morris value, not the code default) and the **V0-param-lineage rule** (a
  V0/test param file must carry the *union* of every stacked branch's registered params; build it from a
  post-change file, else the run aborts at param read — `check_var … not on dataset` → `ENDRUN`, past the
  compile gate). Concrete recipes/failures remain demo-branch worked examples.
- 2026-07-09: Ported to `main` from demo `27719c1`+`7c08096` (v3.13), adapted to api-43: step 0 uses main's
  **branch-by-intent** policy (small keep-it changes → working branch; experiment branch for exploratory/
  repro-sensitive) rather than demo's always-experiment-branch; step 7 uses main's `fork`-remote /
  `origin`-DISABLEd push convention; paths → `E3SM_FATES_api43`; memory refs → main's names
  (`feedback_model_source_push_fork_only`); #16/#17 kept as **demo-branch** worked examples (their logs are
  not on main). Umbrella for `add-fates-parameter`.
