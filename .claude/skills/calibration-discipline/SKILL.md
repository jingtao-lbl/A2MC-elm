---
name: calibration-discipline
visibility: public
category: calibration
description: The per-cycle and per-round DISCIPLINE checklist that keeps a long offline calibration campaign stable — the "definition of done" for each experiment cycle and each round. Use at the start of a multi-cycle offline calibration, and re-check every cycle, to guarantee the stable behaviors happen every cycle, e.g. log each phase with the right skill into log/{stem}.md + a self-documenting phase_results/{stem}/, arm monitors right after every testing-simulation launch (arm-hpc-monitoring for scheduler runs; watch the process + log for local runs), keep the figure script canonical in phase_results (never dev-in-scratch-and-copy), update + validate workflow_state after every phase, write a synthesis report at each cycle end, drive the loop to its limit pausing only at the human gates, and at round end write a round summary that INCLUDES the next-round work plan (param add/remove, bounds, base update). DISTINCT from calibration-goal (the driver LOOP mechanics) and from a single phaseN skill (one phase) — this is the HABITS layer the driver must honor so performance does not drift across cycles.
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [calibration]
  summary: "Per-cycle/per-round discipline checklist (definition-of-done) that keeps a long offline campaign stable. Model-agnostic; pairs with calibration-goal."
---

<!-- ─────────────────────────── At a glance ─────────────────────────── -->
```text
calibration-goal DRIVES the loop; calibration-discipline is the DEFINITION OF DONE it honors.
the loop = 7 phases (0 DESIGN→1 EXPLORATION→2 SCREENING→3 DIAGNOSIS→4 HYPOTHESIS→5 TESTING→6 REFINEMENT→7 CONVERGED),
nested in 3 iteration levels: ROUND (outer, Phase 0→7; redesign 6→0), experiment CYCLE (middle, 3→6, max 10),
skip-testing (inner, 3↔4 on existing data). This checklist runs per CYCLE and per ROUND (below).

per experiment cycle (Phase 3→4→5→6):
  □ each phase logged with its phaseN skill + calibration-log → log/{stem}.md + phase_results/{stem}/
  □ every figure self-documenting IN phase_results/{stem}/ (figure + caption.md + its .py + data)
  □ …and READABLE — `plotting` rule 8: open the rendered PNG and look at it. This checklist
    governs WHERE a figure lives; it is not a judgement that the figure can be read.
  □ analysis is FIRST-HAND this cycle (check_offline_log_evidence.py exit 0 for phase 3/4/6)
  □ after ANY Phase-5 testing-simulation launch → arm monitoring on YOUR launches, react with proposals
     (scheduler/HPC run → arm-hpc-monitoring; local/foreground run → watch the process + its log)
  □ workflow_state_offline_r{RR}.json updated + validated after EVERY phase (check_..._offline.py exit 0)
     ↳ that validator now also WARNs when the state's current phase has no matching offline log
       (stem `_phase{N}_{name}_r{RR}`), so the 'each phase logged' box above is observable rather
       than remembered. WARN not ERROR on purpose: it fires legitimately mid-phase (the state is
       written when a phase STARTS, the log when it ends), and erroring would gate the loop on a
       bookkeeping artifact — which is how gates get bypassed.
  □ cycle end → a synthesis report (write-report): empty-alt figs, no em dash, one canonical script/fig
  □ no KB write / model-source edit before a verified test + human gate

per round (loop limit reached OR converged):
  □ ROUND SUMMARY report — and it MUST propose the next-round work plan
    (param list add/remove, bounds recenter, base update, residual→model-dev/extraction split)
  □ curate the round's VERIFIED knowledge into the KB (human-gated): inject-knowledge (findings you
    originated) + curate-knowledge (the online agent's staged proposals) → gained_knowledge/*.json
  □ promote REUSABLE scripts to the shared library (promote_diagnostic_script.py): online generated/ via
    --script; offline phase_results/{stem}/ via --source <path> --dest tools|phase3_diagnosis
    → then GENERALIZE the promoted copy (strip hardcoded paths/stems/case IDs, parameterize — CLAUDE.md 5+8)
  □ round_summary + the Phase-6 gate recorded in state; PAUSE for the PI at the gate
```

# calibration-discipline — keep a long offline campaign stable

**The failure mode this prevents is DRIFT.** A single offline calibration round is 10 experiment
cycles; a campaign is several rounds. The individual steps are all covered by other skills, but over a
long run it is easy to *skip one some cycle* — forget to arm a monitor after a launch, edit the scratch
copy of a plot script instead of the canonical one, not update the state file, or (the classic) write a
round summary with no next-round plan. Each omission is individually small and individually invisible;
together they make performance uneven. This skill is the **invariant checklist** that makes every cycle
look like every other good cycle. It is the *definition of done*, not a new procedure.

## The loop limits are CONFIG, not literals in this file

**Read them from the machine config before running any check below.** All three live there and
nowhere else — a site or round config does not set them:

```bash
source a2mc_config.sh            # CIME model (ELM, ELM-FATES) — this branch
```

| variable | default | governs |
|---|---|---|
| `A2MC_MAX_EXPERIMENTS` | 10 | the middle loop — how many Phase 3→6 experiment cycles before redesign |
| `A2MC_MAX_SKIP_TESTING` | 10 | the inner loop — Phase 3↔4 iterations on existing data |
| `A2MC_CONFIDENCE_THRESHOLD` | 0.95 | the skip-testing early exit |

Any "max 10" written in prose here (including the summary above) is a **restatement of the default,
not the authority**. Change the config and this file does not follow; quote the config when the
number matters to a decision.

## ARM THE REVIEW AT SESSION START — it is a mechanism or it is nothing

**This checklist only works if it actually fires.** If it fires because the PI types the next step,
that is not a mechanism — it is the PI doing the agent's bookkeeping. Running the checks *from
recollection of this skill* instead of invoking it is the same failure one level up, and is exactly
what `check_skill_claims.py` (pre-commit check 12) now catches.

**When a campaign is live, arm the recurring self-review before doing anything else:**

```
CronCreate(cron="23 * * * *", recurring=true, prompt=<the self-review prompt>)
```

Pick an off-:00/:30 minute. The prompt must (a) say **INVOKE the skill**, not "check against it",
(b) carry the per-cycle checks, and (c) end with **DRIVE THE LOOP THROUGH** — a review that stops at
reporting leaves the loop parked, which is the drift this skill exists to prevent.

**Two limits, worth stating rather than discovering.** A cron job is **session-only** and dies with
the session, so re-arming belongs to session start, not one-time setup; and it fires only while the
REPL is idle, so it will not interrupt long work. Neither makes it worthless — an armed cron that
survives an hour of quiet beats a checklist nobody runs. See
[[feedback_schedule_periodic_reviews_with_a_real_mechanism]].

**Nothing in the loop is the PI's decision except the Phase-6 converge / redesign / stop fork.**
`rethink_6to3` is auto-taken — meaning it needs **no PI approval, NOT that it needs no work**.
Auto-taken is about the *gate*, not the *effort*: the routing is automatic and the rethink protocol
behind it (below) is mandatory. A model-evolution item queued in `TODO.md` (a parameter bound, a
source defect) is **not** a loop gate. Ending a turn by surfacing one as though it blocks is a
premature stop wearing politeness instead of a verdict.

**On a 6→3 routing, ANSWER the rethink protocol in the Phase-6 log.** The route is the default and
was, until the protocol existed, only a counter increment — nothing said what a rethink should DO,
so a cycle could re-enter Phase 3 carrying the previous cycle's base, binding target and lever class
forward unexamined. The protocol is in `phase6-refinement`, and its questions are all settled by
existing data at **zero compute**. The deliverable is **NEW PATHWAYS, plural**, each with its class
and falsifier, named in `set_phase_handshake(handed_to=...)` so Phase 3 starts from them.
**Where it must be written:** the Phase-6 log — the next cycle reads the log, not the state enum
(`calibration-log`, Enrichment contract). **Carried onward:** the class verdict and pathways go into
the cycle report too (`write-report`), drawn from this synthesis rather than derived again.

## SEARCH BEFORE YOU RECORD — the case has usually been here already

**Before recording a finding as NEW, a premise as UNVERIFIED, or a question as OPEN, search the
case's own logs.**

**A plain `git grep` is not enough, and that is the interesting part.** A grep shows you the log you
found, not the log that *supersedes* it — and this project's convention puts the correction banner
at the top of the superseded log precisely so a reader can follow the chain. A keyword search does
not surface them, so a settled-then-corrected question reads as still open.

```bash
python3 tools/prior_art.py <keyword> [...] --site <Site> [--all-streams]
```

It searches the case's logs **and reports each hit's correction status**, so a withdrawn finding
announces itself instead of being re-derived. Verified on this branch: searching `l2fr` returns four
logs, one of them carrying a `withdrawn` banner that a grep would have shown as a plain hit.

## When to use (vs. calibration-goal vs. a phase skill)

```
DRIVE the loop (what's next → dispatch → advance)      → calibration-goal (the driver)
Do exactly ONE phase                                   → phase{0..6}-*
Is THIS cycle / round actually complete + clean?       → calibration-discipline (this — the checklist)
```

`calibration-goal` decides *what* runs next and advances the state; `calibration-discipline` is *how each
step must be done* so the campaign stays stable. Run this checklist mentally at every phase transition,
and explicitly at each cycle end and round end. The two are complementary: the driver without the
discipline drifts; the discipline without the driver does not move.

## The per-cycle checklist (Phase 3 → 4 → 5 → 6)

1. **Log every phase with its own skill, into the offline layout.** Execute a phase via its `phaseN`
   skill; record it with `calibration-log` (PhaseLogger, `A2MC_AGENT_MODE=offline`) so it lands as
   `logs/{stem}.md` with the paired `phase_results/{stem}/`. `stem =
   YYYYMMDDx_phase{N}_{name}_r{RR}[_c{EE}[_iter{II}]]_{descriptor}`. Do not hand-roll the format.
2. **Make every `phase_results/{stem}/` folder self-documenting.** Per figure: the figure PNG, a caption
   or `NOTES.md`, the exact producing `.py`, and its data. The figure `.py` is **canonical here** — edit
   and regenerate it *in place*; never develop it in a scratch/CFS dir and copy the PNG back (that is how
   the script and the figure silently diverge). Memory: `feedback_plot_scripts_canonical_in_phase_results`.
3. **Analysis is first-hand this cycle.** A diagnosis / hypothesis / refinement (phase 3/4/6) log must do
   *this* cycle's analysis and cite a first-hand artifact produced this session, not restate a prior log.
   In **Phase 3**, that first-hand artifact should include a **sim-vs-obs TIME-SERIES comparison** for the
   diagnosed cases (the trajectory shape is often the diagnosis) — don't defer it to the report; and every
   mechanism claim is verified in the checked-out model **source** (`file:line`), not RAG/long_names
   ([[feedback_timeseries_plots_during_diagnosis]]).
   Gate: `python tools/check_offline_log_evidence.py <log.md>` must exit 0.
   Memory: `feedback_offline_logs_need_first_hand_analysis`.
4. **Arm monitors the moment you launch a testing simulation.** Right after a Phase-5 launch, arm
   monitoring on the run's live log(s) with the event + error filters — and **only on runs THIS session
   launched** (`feedback_monitor_only_own_session_launches`; never adopt another effort's jobs). The
   mechanism depends on the run style: a **scheduler / HPC** run (SLURM on Perlmutter) → `arm-hpc-monitoring`
   (it detects the submitter/extractor via `ps`, tails the logs, watches `squeue`); a **local / foreground**
   run (a model without a scheduler) → watch the process and its stdout/log directly (there is no `squeue`,
   so gate on the process exiting + error lines in the log). Either way, **silence on a crash looks
   identical to silence on still-running**, so cover error signatures, not just happy-path events, and
   react to what you see with **proposals** (headroom math, next batch, next-phase extraction), not bare relay.
5. **Update and validate the state after every phase.** Write the phase transition into
   `workflow_state_offline_r{RR}.json` (`tools/workflow_state_offline.py`), then
   `python tools/check_workflow_state_offline.py` must exit 0. A corrupt/stale state misdrives the whole
   loop; validating after *every* write is the lesson from the mid-campaign state-format crash.
5b. **COMMIT AND PUSH at the same boundary.** The phase is not done when the state validates; it is
   done when the work has **left the machine**. An unpushed commit exists on **exactly one node** —
   on an HPC login node a session can lose it with no offsite copy — **and it is invisible to the PI
   until it lands**, which removes their ability to redirect the work while redirecting is still
   cheap. Both costs grow with the size of the pile.

   Push after each completed phase, each finished skill edit, each fix with its test; if several
   commits land on one thread, push once as that thread closes. The gap should be minutes and a
   handful of commits, never hours and dozens.

   > **Measured on this branch, 2026-08-23:** pushes happened only when the PI typed "push it",
   > in batches of up to **14** commits. That is the same shape as the source branch's 30-commit
   > pile — the PI doing the agent's bookkeeping, which is what the review-arming section above is
   > about, one level down. Push at the boundary, unprompted.

6. **Track the objective, not the loudest crash — and NEVER self-declare exhaustion below the loop limit.**
   The goal is the fit to the validation targets. When a crash and a calibration signal compete for
   attention, the targeted performance experiment is the objective
   (`feedback_performance_experiment_is_the_objective`); exhaust the input/param explanation before
   concluding a model-source change is needed. **Read the RAW counter, not your conclusion:** if
   `experiment_count < max_experiments` and not `converged`, the only valid states are "running a cycle"
   or "launching the next" — never "paused/complete/exhausted." Your "the rest is futile" conviction is
   the *hypothesis the remaining cycles test*, not a licence to skip them; the moment you feel most certain
   the space is exhausted is the moment to keep driving. (Worked failure, on the adapter-kit branch: a round
   declared "exhausted" at cycle 0/10 while a source-verified lever remained untested, found in the very
   next cycle.) See `feedback_never_self_declare_exhaustion`.
7. **Synthesize a report at each cycle end.** Use `write-report`: zero-context reader, empty-alt figures
   (`![](fig.png)` + a bold `**Figure N.**` caption), **no em dash**, one canonical script per figure,
   folder `reports/{YYYYMMDDx}_{topic}/` (same-day letter required). Cross-reference the logs; do not
   duplicate them.
8. **No premature writes.** No curated-KB injection and no model-source edit until a Phase-5 test verifies
   the hypothesis AND the human gate clears (`feedback_no_kb_injection_before_verified_test`).

## The per-round checklist (loop limit reached, or converged)

> **A round is done ONLY at `experiment_count == max_experiments` OR `converged` — not on your judgment
> that the space is exhausted.** In particular `stop_model_dev` below the loop limit is NOT a legitimate
> gate arrival: it needs the loop limit reached, `converged`, or an explicit `human_confirmed_exhaustion`
> (enforced by `validate_phase6_decision`). A self-authored `next_targeted_experiment=NONE` plus an
> exhaustion_justification is not sufficient. If you are below the limit and not converged, you are not at
> the per-round checklist yet — go back to item 6 and run the next cycle.

9. **Write the round summary — and it MUST propose the next-round work plan.** A round summary that only
   narrates what happened is **incomplete**. Whether the round converged or hit the cycle limit, the
   summary must end with a concrete **next-round plan** the PI can act on:
   - **Parameter list — add / remove.** Which dominant levers to *add* to the calibration list (e.g. ones
     that were fixed inputs but proved decisive), which insensitive ones to *drop* (justified by the
     sensitivity screen).
   - **Bounds — recenter / widen.** Which priors/bounds to move and why (developer correction, or the
     round's evidence that a value sits at a bound).
   - **Base update.** Which verified fixes to bake into the next round's base configuration so it starts
     from the best-known state (a fresh sensitivity screen on a *stale/dead* base is void — re-anchor).
   - **Residual split.** Route each unmet target to its track: a model-development item (source change on
     the fork, its own discipline) vs. an extraction/spin-up/data item (not a parameter problem).
   - **Mechanics.** The redesign is Phase 6 → Phase 0 with `calibration_round++`; list the sequence.
10. **Record the gate and PAUSE.** Write `round_summary` + the Phase-6 decision context into the state,
    leave `phase6_decision` for the human at a genuine fork (converge / redesign / stop→model-dev), and
    surface the decision. This is one of the four human gates — do not decide it unilaterally. *Once the PI
    records `redesign_6to0`*, opening round N+1 (per-round config wrapper → R{N} param list → add the round
    to `calibration_rounds.yaml` → fresh `workflow_state_offline_r{RR}.json` → sample on the corrected base)
    is the **`phase0-design`** skill's "Opening a NEW round" section — do not stand up a round before the gate.

Once the PI clears the gate, do the two round-close housekeeping steps (both human-gated Tier-3 writes,
so they happen **at / after** the gate, not before — item 8):

11. **Curate the round's verified knowledge into the KB.** Only findings a Phase-5 test actually verified
    this round (never a mechanism-story, `feedback_no_kb_injection_before_verified_test`). Two inputs, one
    destination `use_cases/{site}/memory/gained_knowledge/{discoveries,experiments,parameters,failed_approaches}.json`:
    a finding **you** originated → `inject-knowledge`; the online agent's **staged** proposals in
    `auto_discovered_pending.json` → review + promote/discard via `curate-knowledge`
    (`tools/review_pending_knowledge.py`). "Online proposes, offline disposes" — you are the sole curated
    writer. (The dir is created on first write; it may not exist yet for a new site.)
12. **Promote reusable scripts into the shared library.** A diagnostic/analysis script that proved
    reusable graduates out of its scratch home so future rounds/sites auto-discover it:
    - **online** agent's `phases/phase3_diagnosis/generated/*.py` → `phases/phase3_diagnosis/` via
      `tools/promote_diagnostic_script.py` (`--list` → `--script <n> --dry-run` → promote; it registers the
      tool in `DIAGNOSTIC_TOOLS_INVENTORY`).
    - **offline** (interactive) scripts you wrote into `use_cases/{site}/memory/phase_results/{stem}/` →
      `tools/` (a generic analysis utility) or `phases/phase3_diagnosis/` (a reusable `test_hypothesis`),
      via `promote_diagnostic_script.py --source <path> --dest tools|phase3_diagnosis` (`--dry-run` first;
      `--dest tools` just copies, `--dest phase3_diagnosis` also registers it in `DIAGNOSTIC_TOOLS_INVENTORY`).
      **Promotion is copy-then-generalize, not copy-and-done:** a `phase_results/{stem}/` script hardcodes
      its output path, stem, and case IDs, so after promoting you **must edit the copy** to remove hardcoded
      paths/stems/case/site names and parameterize inputs (argparse or `tools/config.py`) — CLAUDE.md rules
      5 + 8 (keep generic, no hardcoded paths). Promote **only genuinely reusable** scripts; one-off figure
      scripts stay in `phase_results/{stem}/` as the log's evidence.

## Footguns (the exact drifts this catches)

- **A round summary with no next-round plan** — narrates the round but leaves the PI nothing to act on.
  Item 9 is the fix; it is the most common omission.
- **Dev-in-scratch-and-copy plot scripts** — the report/`phase_results` folder ends up with a new figure
  but a stale script. Edit the canonical script in `phase_results/{stem}/` and regenerate in place (item 2).
- **A launch with no monitor** — silence on a crash looks identical to silence on still-running; arm
  immediately (item 4), and only on your own jobs.
- **Skipping the state update/validate** — the next session's resume brain (and `calibration-goal`) then
  misdrives. Update + `check_workflow_state_offline.py` after every phase (item 5).
- **Stopping early on a self-declared gate** — the loop runs to `experiment_count == max_experiments` or
  `converged`. The tempting loophole is to declare you have "reached a gate" (`stop_model_dev`) at a low
  cycle count and pause — but a `stop_model_dev` you authored below the loop limit is NOT a legitimate gate
  arrival; it is the premature-stop failure. A GENUINE gate is: the loop limit reached, `converged`, or a
  fork with `human_confirmed_exhaustion`. Don't halt with cycles remaining on your own "it's futile" call
  (`feedback_never_self_declare_exhaustion`, `feedback_offline_agent_drives_the_workflow`). The worked
  failure passed the old checks because the wrong decision was written INTO the state the checks read —
  a consistency check cannot catch a premise you corrupted; read the raw counter.
- **Promoting a script verbatim** — a `phase_results/{stem}/` script hardcodes paths, its stem, and case
  IDs; copied to `tools/` unchanged it breaks on the next run/site. Promotion is copy-**then-generalize**
  (item 12): edit the copy to be site/run-agnostic before committing.

## Cross-references

- Driver + orient: `calibration-goal` (the loop this discipline is the definition-of-done for),
  `onboard-session` (cold-start; its Step 4 DRIVE-vs-PAUSE list is the same gate set).
- Pieces: `calibration-log`, the `phase0-design`…`phase6-refinement` skills, `arm-hpc-monitoring`,
  `write-report`, `summarize-calibration-round` (FATES standardized round summary), `curate-knowledge`
  (the KB write gate), `model-evolution` (the residual model-dev track).
- Memories: `feedback_never_self_declare_exhaustion` (the premature-stop failure this skill now guards),
  `feedback_offline_agent_drives_the_workflow`, `feedback_offline_agent_operating_discipline`,
  `feedback_offline_logs_need_first_hand_analysis`, `feedback_plot_scripts_canonical_in_phase_results`,
  `feedback_monitor_only_own_session_launches`, `feedback_no_kb_injection_before_verified_test`,
  `feedback_performance_experiment_is_the_objective`.

## Notes

- **Branch fit:** generic offline-calibration discipline — model-agnostic, applies on any branch. Distilled
  on `adapter-kit` from the EcoSIM BioCON R1 ten-cycle onboarding; ported to `main` (adapter-kit never pushes
  back, `docs/38`).

## Changelog

- 2026-08-23 — New per-cycle item **5b: COMMIT AND PUSH at the same boundary**. Adopted from `adapter-kit` (`17664824`). A phase is done when the work has LEFT THE MACHINE: an unpushed commit lives on one login node and is invisible to the PI, removing their ability to redirect while redirecting is cheap. Numbered 5b rather than 6 following this file's inserted-item convention (cf. 2b, 3b) and because the per-round list continues the same sequence. Measured here: pushes happened only on a typed "push it", in batches of up to 14 — the same shape as the source branch's 30-commit pile.
- 2026-08-23 — **On a 6→3 routing, ANSWER the rethink protocol in the Phase-6 log**, and a correction to the line ported this morning: `rethink_6to3` being *auto-taken* is about the GATE, not the EFFORT — no PI approval needed, protocol still mandatory. As written it read as "automatic, nothing to do" and contradicted the protocol once one existed. Adopted from `adapter-kit` (`73007487`).

- 2026-08-23 — Adopted three sections from `adapter-kit` (`08b2675c`, `6f6af175`), re-authored: **the loop limits are CONFIG** (main's `a2mc_config.sh` already sets `A2MC_MAX_EXPERIMENTS`, `A2MC_MAX_SKIP_TESTING`, `A2MC_CONFIDENCE_THRESHOLD`, while this file stated a bare 'max 10' — the prose is now marked a restatement, not the authority); **ARM THE REVIEW AT SESSION START**, because a checklist that fires only when the PI types the next step is the PI doing the agent's bookkeeping; and **SEARCH BEFORE YOU RECORD** via the newly ported `tools/prior_art.py`, which reports each hit's correction status — a plain grep shows the log you found, not the one that supersedes it.

- 2026-08-01: **Closed the premature-stop loophole** (adapter-kit lineage: `stop_model_dev` declared at
  `experiment_count 0/10` while a source-verified lever remained; the periodic check rubber-stamped it because
  the wrong decision had been written into the state it reads). Hardened item 6 (read the RAW counter; never
  self-declare exhaustion below the loop limit; your "futile" conviction is the hypothesis the cycles test),
  added a per-round-checklist banner (a round is done ONLY at loop limit / converged / `human_confirmed_exhaustion`),
  rewrote the "Stopping early" footgun to kill the "reached a gate" escape hatch, and cross-referenced
  `feedback_never_self_declare_exhaustion`. Also: the per-cycle state box now points at the new
  `check_workflow_state_offline.py` phase-logged WARN, and item 3 requires a Phase-3 sim-vs-obs time-series
  plus source-verified mechanism claims. Paired code guardrail (same adoption): `validate_phase6_decision`
  now errors on `stop_model_dev` below the loop limit without `human_confirmed_exhaustion`.
- 2026-07-18: Ported to `main` from adapter-kit `6aff7cd` (skill created there `c240593`; items 11–12 +
  copy-then-generalize promotion `0eacaea`/`92e5c0e`/`9ac4d44`). Model-agnostic; the offline `--source/--dest`
  promote path (item 12) rides with the `promote_diagnostic_script.py` port. Registered 4-way.
- 2026-07-18: Item 12 + a footgun: promotion is copy-**then-generalize** — a phase_results/{stem}/ script
  hardcodes paths/stems/case IDs, so the promoted copy must be edited site/run-agnostic (CLAUDE.md 5+8).
- 2026-07-18: Item 12's offline promotion is no longer manual — `promote_diagnostic_script.py` now takes
  `--source <path> --dest tools|phase3_diagnosis`, so a `phase_results/{stem}/` script promotes with one command.
- 2026-07-18: Added the two round-close housekeeping steps to the per-round checklist (items 11–12):
  **curate the round's verified knowledge** into `gained_knowledge/*.json` (inject-knowledge / curate-knowledge,
  human-gated) and **promote reusable scripts** (online `generated/` → `phase3_diagnosis` via
  `promote_diagnostic_script.py`; offline `phase_results/{stem}/` → `tools/` or `phase3_diagnosis`).
  Both were implicit / lived only in `phase6-refinement`. Paired: `phase6-refinement` Step 3b.
- 2026-07-18: Added a one-line workflow orientation to the At-a-glance (the 7 phases + the 3 nested
  iteration levels: round / experiment cycle / skip-testing) so the checklist's per-cycle/per-round
  scope is legible without opening `calibration-goal`.
- 2026-07-18: Reworded item 4 to be run-style-agnostic — "testing-simulation launch" (not "HPC launch"),
  and split the monitoring mechanism: scheduler/HPC run → `arm-hpc-monitoring`; local/foreground run →
  watch the process + its log directly (no `squeue`). `arm-hpc-monitoring` is scheduler-specific; a
  dedicated non-HPC monitoring skill is a TODO for when the first local-run adapter model appears.
- 2026-07-18: Initial version — distilled from the EcoSIM_BioCON R1 offline onboarding (10 experiment cycles),
  where the stable behaviors (self-documenting `phase_results/{stem}/`, per-cycle reports, arm-after-launch,
  state-validate-after-write, canonical figure scripts, drive-to-limit) were all performed but scattered
  across many skills/memories with no single definition-of-done. Item 9 (round summary MUST propose the
  next-round plan) added after the R1 summary initially shipped without one.
