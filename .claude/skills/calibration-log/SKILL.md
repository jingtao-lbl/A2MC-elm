---
name: calibration-log
visibility: public
category: calibration
description: Log interactive calibration work for a site under use_cases/{site}/memory/logs/. Two log types — a PHASE log (a diagnosis, screening, experiment design/result, refinement — recorded the same way the autonomous agent does, via PhaseLogger, so both modes' logs synthesize together) or a free-form SESSION log (exploratory work that does not map to a specific phase). Use when the user wants to record calibration or exploration work — "log this", "log this phase / diagnosis / experiment", "log this calibration session", "write a session log", "record what I explored".
modes:
  requires_fates: false      # logging convention; model-agnostic (PhaseLogger)
  nutrient_pathway: any
  scope: [logging]
  summary: "Site calibration/exploration logging via PhaseLogger; applies in every mode."
---

# Log Calibration Work (phase log or free-form session log)

Records the interactive agent's calibration/exploration work for a site under
`use_cases/{site}/memory/logs/`, so it lives alongside the autonomous agent's logs and
`tools/session_report.py` / synthesis reporting can process everything for a session together.

**Mechanical conformance check.** After writing (or before committing), run
`python3 tools/check_calibration_log_conformance.py <log.md>` — it checks the structural contract
below (filename, header, required sections; for a phase log, that phase's own section list read
directly from `PhaseLogger._EXPECTED_SECTIONS`). **This is a different tool from `log`'s
`check_log_conformance.py`, which governs dev/ana logs only and has a completely different
contract** (`Version`/`Branch` header, Summary/Problem/Solution/Files Changed/Verification — none
of which a calibration log has). Each tool refuses the other's stream with a `wrong tool:` error;
using the wrong one on a calibration log produces several false "missing section" errors, not just
noise. Orthogonal to `tools/check_offline_log_evidence.py` (that one checks *substance* — does an
analysis-phase log rest on a first-hand artifact — not structure; run both). Wired into
`.githooks/pre-commit`, staged-only.

## Step 1 — pick the log type

| Type | When | How it is written |
|------|------|-------------------|
| **phase log** | The work maps to a Phase 0–7 activity (diagnosis, screening, experiment design/result, refinement, …) | `PhaseLogger` — identical format/naming to the autonomous agent |
| **session log** | Free-form / exploratory work that does **not** follow the phases exactly (an ad-hoc analysis, a data check, an idea) — which is fine | a plain dated note using the `YYYYMMDDx_Topic.md` convention |

Both land under the same session directory `use_cases/{site}/memory/logs/{stamp}/`, so synthesis
sees one session in one place. `{stamp}` = the orchestrator `session_id` (`YYYYMMDD_HHMMSS`) when a
run is active, otherwise a date stamp for the interactive session.

## Type A — phase log (via PhaseLogger)

Don't hand-roll the format; call `tools/phase_logger.py` so the output matches the autonomous
agent byte-for-byte.

```python
# source a2mc_config.sh + use_cases/{site}/config/{site}_config.sh first. As the INTERACTIVE agent set:
#   export A2MC_AGENT_MODE=offline   → the flat memory/logs/{stem}.md layout (see "Offline layout" below)
from tools.phase_logger import create_logger

logger = create_logger()                 # resolves site dir from A2MC_USE_CASE_DIR
logger.set_iteration_context(            # the three-level counters (see CLAUDE.md)
    iteration=<skip+1, or 0>,            # REQUIRED positional arg; use 0 for Phase 0-2 (no inner loop)
    calibration_round=<round>,           # RR — outermost loop
    experiment_count=<exp_cycle>,        # EE — middle loop (Phase 3-6)
    skip_testing_count=<skip>,           # inner loop (Phase 3/4 only)
)
logger.log_diagnosis(title="PFT10 Fineroot Root-Cause", content=<markdown>, ...)
```

Per-phase methods: `log_design` (0), `log_exploration` (1), `log_screening` (2),
`log_diagnosis` (3), `log_hypothesis` (4) / `log_experiment_design`, `log_testing` (5),
`log_refinement` (6). Each applies the right section template from `templates/logging/`.

Lands at (**ONLINE / orchestrator run only** — a `session_id` is present):
```
use_cases/{site}/memory/logs/{stamp}/phase{N}_{name}/
    Phase 0–2 : r{RR}_{stamp}_Title.md
    Phase 3–6 : r{RR}_c{EE}_iter{II}_{stamp}_Title.md
```
`RR` = `calibration_round`, `EE` = `experiment_count`, `II` = `skip_testing_count + 1` (Phase 3/4).
Full convention: `CLAUDE.md` §"Session Logging Convention" and the `tools/phase_logger.py` header.

**Offline (interactive-agent) layout — THE DEFAULT FOR YOU, the interactive agent (docs/31).** You have
no orchestrator run / `session_id`, so this is your convention (the nested `{session_id}/phase{N}_{name}/`
form above is the online/orchestrator layout ONLY). Set `A2MC_AGENT_MODE=offline` (or `create_logger(...)`
with `agent_mode='offline'`). `PhaseLogger` then writes a **date-led flat topic-stem** — `logs/{stem}.md` with
`stem = YYYYMMDDx_phase{N}_{name}_r{RR}[_c{EE}[_iter{II}]]_{descriptor}` — and `topic_artifact_dir()`
gives the paired `phase_results/{stem}/` for figures/data. Track progress in the per-round
`workflow_state_offline_r{RR}.json` (`tools/workflow_state_offline.py`). The **online path is
unchanged**; this only switches on for the interactive agent. `session_report.collect_session_artifacts(include_offline=True)`
folds these flat logs into synthesis alongside session-scoped ones.

**The `log/{stem}.md` and `phase_results/{stem}/` have DIFFERENT jobs — do both fully.**
- **`log/{stem}.md` carries the ANALYSIS this session** — the reasoning, findings, discussion, the numbers
  with their interpretation, the conclusion, and the next action. Not a caption dump; the argument a cold
  reader reconstructs. (Analysis-phase logs also perform *first-hand* analysis, not a restatement of a prior
  log, `feedback_offline_logs_need_first_hand_analysis`.)
- **`phase_results/{stem}/` is a SELF-DOCUMENTING artifact folder** (mirror the `write-report` self-contained
  folder, `feedback_figures_over_tables_over_words`): for EACH figure ship **(1) the figure**, **(2) a
  caption/NOTES `.md`** (what it shows + how-to-read + provenance: which script produced it, from what data),
  **(3) the generating `.py` script SAVED into the folder** (not run as an inline bash heredoc that vanishes),
  and **(4) the underlying data file**. A future reader (or you next month) must be able to regenerate and
  interpret the figure without you. A lone figure with no caption / script / data is under-documented.

**Pass the TITLE as the descriptor to `topic_artifact_dir()`.** The artifact folder is keyed on a
descriptor you choose; the log is keyed on the `title=` you pass to `log_<phase>()`. They pair only if
both derive from the same string:

```python
TITLE = "R1 Screening Of The Alive Sub-Ensemble: One Target Fails, Not All Three"
d = logger.topic_artifact_dir(2, TITLE)     # <- the TITLE, not a separate phrase
...                                          # write figures + NOTES.md into d
logger.log_screening(title=TITLE, ...)       # same string -> same stem
```

Give them different strings and you get two stems and a log that does not match its own folder.
`topic_stem()` reuses an existing stem found on disk, which fixes the **process-boundary** case — one
run creates the folder, a later one writes the log — but it cannot rescue two genuinely different
descriptors, because the suffixes legitimately differ.

**The log must SHOW its figures, not just name their folder** (effective 2026-08-22). The log and
`phase_results/{stem}/` are meant to be read as ONE document: a reader opens `logs/{stem}.md` and
expects the evidence to be there. `` `phase_results/{stem}/plot.png` `` in prose renders as a text
path, so a log that discusses "Figure 1" while displaying nothing sends the reader hunting. **Embed
every figure the paired folder holds:**

```markdown
![](../phase_results/{stem}/r01_leafroot_biomass_vs_obs_4variants.png)

**Figure 1. State the finding, not the axes.** What it shows, how to read it, and its provenance
(which script, from what data).
```

Empty alt text, bold `**Figure N.**` caption beneath — `feedback_report_figure_empty_alt_text`. The path
is relative from `logs/` (`../phase_results/{stem}/…`), so it resolves in-repo. Close the log with an
**Artifacts** table indexing every file in the folder and how to regenerate it.

The rule is **dated**: logs stamped before `EMBED_RULE_EFFECTIVE` (`20260822`) are grandfathered — they
could not follow a rule that did not exist, and a checker that is always red is a checker nobody reads.
The exempted count is **printed**, so the backlog stays a visible decision rather than a silent one.

**Update the STATE before you write the log — the order is load-bearing.** `PhaseLogger` **bakes the
`## Reasoning chain` block into the file at write time**, rebuilding it from
`workflow_state_offline_r{RR}.json`. Nothing rewrites a log afterwards, so:

```
1. st.add_decision(...) / add_evidence(...) / save()     <- state correct FIRST
2. logger.log_<phase>(...)                               <- chain baked in correct
```

Do it the other way and every stale pointer is frozen in the log permanently.

**Evidence gate (docs/33).** After writing an offline phase log run `python tools/check_offline_log_evidence.py
<log.md>` — it must **exit 0**. What it checks, and at which severity:

| | severity | applies to |
|---|---|---|
| a cited `phase_results/<stem>/` that does not exist | **ERROR** (blocks) | **every** offline phase log, at any age |
| no resolvable first-hand artifact (a restatement) | **ERROR** | analysis phases (3/4/6) |
| a figure the paired folder holds and the log never embeds | WARN | every log, **dated** (see above) |
| a figure missing its caption `.md` / generating `.py` / data file | WARN | every log |

Clear the warnings too (the self-documenting-folder discipline above); don't just pass on exit 0. The
first two rows run for **every** phase, not only analysis phases — a phase-0/1/2/5/7 log used to be
returned clean by code that had inspected nothing.

## Type B — session log (free-form)

For exploratory work that doesn't fit a phase. Write a plain dated markdown note at the **session
root** (no `phase{N}` subdir):
```
use_cases/{site}/memory/logs/{stamp}/YYYYMMDDx_Topic.md
```
- `YYYYMMDDx` = date + a sequential letter (`a`, `b`, `c`, … for same-day notes — check existing
  files so you don't reuse a letter), `Topic` = Title_Case with underscores. Past `z` (27th+
  same-day), append a second letter keeping the `z` prefix: `za, zb, …, zz` (sort-stable — the
  offline stem does this automatically in `tools/phase_logger.py`; never `aa`, it sorts before `b`).
- Keep it light: a short header (**Date**, **Author**, **Type:** exploration/analysis) followed by
  free-form reasoning — what you looked at, what you found, evidence (cite specific cases/values),
  and any open question. No fixed section list; it is a working note, not a phase deliverable.
- **Author field** = `{A2MC_USER_NAME} with {coding-agent name}` — e.g. *"Jing Tao with Claude Code"*.
  `A2MC_USER_NAME` is captured at first run by `a2mc-init` (the greeting) and stored in `a2mc_config.sh`;
  the coding-agent name is whatever harness you're running in. Fall back to the user's stated name, or
  `A2MC user with {coding-agent name}` if none was given. This is the **calibration-user** convention and
  it governs every log under `use_cases/{site}/memory/logs/`. A2MC *framework-development* logs follow a
  different rule (author by environment), set by the `log` skill — a maintainer-side development skill not
  included in this release (see `.claude/skills/README.md`); that rule does not apply to site logs either way.

## The phase handshake — what you inherited, what you hand on

**A calibration log is not a dev log.** A dev log records a change. A phase log is a link in the
3→4→5→6→3 chain, and it carries the *reasoning* forward.

The autonomous agent hands the next phase a typed object (`reasoning/schemas.py`) — `Diagnosis` →
`Hypothesis` → `Experiment` — living in memory inside one run, so its chain cannot break. **You have
no such object.** Your phases are separated by days, sessions and compactions, so **the log is the
only channel.** If it does not carry the handshake, the next phase re-derives what this one already
concluded, which is the re-derivation the loop exists to avoid.

So an offline phase log must carry **more** than the online one: the field set *and* the narration.

`PhaseLogger` emits the frame for you in offline mode. Set it before the `log_*` call, the same way
you set the iteration counters:

```python
logger.set_phase_handshake(
    inherited_from="20260716b_phase2_screening_r01 — ranked ensemble; best_case=En2939, 2/3 targets",
    handed_to="parameter_recommendations + base_case_id (mirror the schema field names)",
    next_action="Phase 4: skip-test the P-retranslocation ceiling on existing Morris data",
)
logger.log_diagnosis(title=..., failing_targets=[...], ...)
```

### The chain accumulates — it is not just the previous phase

`PhaseLogger` also emits **`## Reasoning chain — round RR, through cycle EE`**, rebuilt from
`workflow_state_offline_r{RR}.json` on every log: the round's explorations, diagnoses, hypotheses,
experiments and standing decisions, **each naming the log stem that produced it**.

This is the point of the loop. Calibration **accumulates** — each phase builds on the one before,
each experiment cycle on the cycles before it — so a log showing only its immediate predecessor
cannot be checked for logical consistency; a reader would have to open ten files to see whether the
reasoning follows. With the chain, every phase log states what it stands on and is traceable end to
end without leaving the file.

**Your job is to keep it true.** The chain is only as good as what the phases recorded into the
state, so update `workflow_state_offline` after every phase (`calibration-discipline` already
requires it) with the finding, not a label. Its canonical summary field is `one_line`. An entry
reading "ran the sweep" contributes nothing to a chain; "v4 retrans+nfix survives coupled-N to
RGSP-yr400 while all four demand-cut variants collapse" does.

Note the per-log handshake fields are consumed after each write. That is not to prevent carry-over —
carry-over is what the chain is for — but because those three fields describe *this* phase's
position: reusing them would state, falsely, that the next phase inherited what this one inherited.

Name the **predecessor log stem**, not just the phase — a stem resolves, "the last diagnosis" does not.
On a **6→3 re-entry** also say which hypothesis was disproven and what changed, or the new cycle reads
as a fresh start.

## Enrichment contract — the template is a floor, not a form

**A Phase-6 log that routes 6→3 must carry the RETHINK, not just the decision.** `phase6-refinement`
owns the protocol; the log is where its output has to land, **because the next cycle reads the log,
not the state enum**. Record all six answers — this cycle's synthesis (Phases 3–6, separating what it
ESTABLISHED from what it merely tried), Phases 1 and 2 re-read against that synthesis, whether the
BASE is still right for the question now being asked, whether the BINDING TARGET has moved, which
lever CLASS the round has exhausted, and for each refuted lever the (parameter, direction, base-miss-
sign) triple. Then record the **NEW PATHWAYS**, each with its class and falsifier, and name them in
`set_phase_handshake(handed_to=...)` so Phase 3 starts from them.

A log that records `rethink_6to3` and nothing else has documented a counter increment — which is
exactly what the route was before the protocol existed.

`PhaseLogger` writes the skeleton; **you fill it.** In offline mode it also appends a
`## Sections not provided` list naming every expected section left empty, because each section is
emitted behind an `if <arg>:` guard — an unfilled one otherwise leaves no trace it was skipped, and a
thin call produces a short, well-formed, entirely plausible log.

- **A phase log is a LIVING record, not an end-of-phase write-up.** Start it when the phase
  starts and enrich it as you go. This matters most for the phases that are not "analysis":
  **Phases 0 and 5 both put simulations on a scheduler**, so both carry the run-and-watch spine —
  Submission (job/array IDs) · Simulation Status · Monitoring Armed · Failures and Restarts —
  each paired with its artifact in `phase_results/{stem}/`. They differ in what surrounds it:
  **Phase 0** materializes an ensemble, so it adds Sampling Design · Cases Materialized ·
  Verification Plots. **Phase 5** runs a handful of VARIANTS designed from the hypothesis the
  inner 3↔4 loop produced, so it adds Experiments Designed · **V0 Reproducibility Gate** ·
  Results Preview (does each new test look sane?) · Results Summary. "Cases Materialized" is
  phase-0 vocabulary and is deliberately not asked of phase 5. Deferred to the end, that
  operational detail is simply gone: nobody reconstructs a failed-case list or a restart
  command from memory a week later.
- **A placeholder is a finding, not a state.** `_(not provided — fill, or state why it does not
  apply)_` means either fill it or replace it with the reason it does not apply (a carbon-only run
  has no P-limitation causes; a single-PFT site has no Cross-PFT Conflicts). Both are acceptable;
  leaving it is not.
- **Cite evidence for every substantive claim** — the result file, the figure, the curated-knowledge
  entry, or **source `file:line`**. `FatesAllometryMod.F90:1086` is a different quality of claim from
  "the ceiling appears to bind", and mechanism-level reasoning in Phase 3 is where that difference
  decides whether the next phase tests the right thing ([[feedback_param_description_can_lie_verify_in_source]]).
- **Depth is not gated, and that is deliberate.** A gate demanding non-empty sections manufactures
  filler, and a hollow section that reads like analysis is indistinguishable from real analysis — which
  a visible placeholder never is. What IS checked is structural: `check_offline_log_evidence.py`
  (a first-hand artifact exists) and the log naming its predecessor and a next action.

**For a Type A phase log, put it in the `content=` markdown you pass to `PhaseLogger`** — do not
edit the generated file afterwards. The per-phase methods own the header, filename and section
template; `content` is free markdown, so the block travels inside it and the output still matches
the autonomous agent's format. For a Type B session log, just append it before you finish.

## Both types — record what you CONSULTED, not just what you did

Add a short **`## Skills and memory invoked`** block near the end of the log (just before any
cross-references). It applies to phase logs and session logs alike.

```markdown
## Skills and memory invoked

- **Skills:** `phase3-diagnosis`, `plotting`
- **Memory:** `feedback_timeseries_plots_during_diagnosis`, `reference_l2fr_is_fineroot_per_leaf`
- **Knowledge consulted:** RAG `api-43-1` (2 queries on ECA uptake); curated discovery
  `pid_controller_paradox`
- **Gaps / misfires:** nothing in curated knowledge covered the P-retranslocation ceiling,
  hence the candidate below.
```

Rules:

- **Name things exactly** — the skill directory name, the memory's `name:` slug, the RAG profile,
  the curated-knowledge key — so the entries are greppable rather than prose.
- **List what you actually followed.** A skill you opened and abandoned belongs under
  *Gaps / misfires* with the reason, not under *Skills*.
- **"None" is a legitimate and informative answer.** Write it rather than dropping the section: a
  substantial diagnosis that consulted no knowledge source is itself a finding, and usually a
  prompt to go check the knowledge base before trusting the conclusion.
- **The Gaps line is the load-bearing one.** A skill that misled feeds `refine-skill`; a lesson
  with no knowledge entry yet is a **candidate** for `inject-knowledge` / `curate-knowledge` —
  a candidate, never a write. Curated knowledge stays human-gated, and a diagnosis is not
  curated knowledge until an experiment verifies it
  ([[feedback_no_kb_injection_before_verified_test]]).

**Why:** a calibration log records the evidence for its conclusion but not which knowledge the
conclusion was built on. That hides the two failure modes that matter most here — a hypothesis
formed without checking the knowledge base, and a conclusion inherited from a knowledge entry
that has since gone stale.

## Notes

- These are **run-state** logs (site-specific calibration data) — not synced to the public demo.
  The value is local synthesis across a session.
- Do **not** re-implement the phase naming/section logic here; it lives in `tools/phase_logger.py`
  and this skill follows it.

## Changelog

- 2026-08-23 — **A Phase-6 log routing 6→3 must carry the RETHINK, not just the decision** (Enrichment contract). Adopted from `adapter-kit` (`28076e11`). The log is where the protocol's output lands, because the next cycle reads the LOG, not the state enum. Enforced by `check_calibration_log_conformance.py` **C11** (renumbered from adapter's C9 — C9 and C10 are already taken on main).

- 2026-08-22: **Three rules adopted from `adapter-kit` (v2.272–v2.274), re-authored.** (a) *Embed your
  figures* — the log and its `phase_results/{stem}/` review as one document; naming the folder in prose
  is not showing the figure. Dated via `EMBED_RULE_EFFECTIVE=20260822`, with the grandfathered count
  printed rather than silent. (b) *State before log* — `PhaseLogger` bakes the reasoning chain in at
  write time, so repointing state afterwards freezes a superseded stem permanently. (c) *Pass the TITLE
  as the descriptor* to `topic_artifact_dir()`, since the folder is keyed on the descriptor and the log
  on the title. `check_offline_log_evidence.py` now runs its dead-pointer ERROR and figure WARN for
  **every** offline phase log, not only analysis phases; pre-commit check (9) gates staged ones.
- 2026-08-14: **New mechanical conformance checker**, `tools/check_calibration_log_conformance.py`
  — both types (phase log's per-phase sections read via `ast` from `PhaseLogger._EXPECTED_SECTIONS`,
  never a second hardcoded copy; free-form's lighter header + Cross-references), wired into
  `.githooks/pre-commit` staged-only. Paired with a `wrong_stream()` guard against `log`'s
  `check_log_conformance.py`, and the sibling tool gained the mirror-image guard the same day —
  measured before wiring: pointing the dev checker at a real calibration log produced 9 false
  "missing section" errors; pointing this tool at a dev log, before its own guard existed, passed
  with a warning (a false clean, worse than a false failure). Full record:
  `memory/dev_logs/20260814f_Calibration_Log_Checker_And_Stream_Separation.md`; re-authored from
  `adapter-kit`'s same-day parallel work via `adopt-from-adapter-kit`.
- 2026-08-02: A phase log is a **living record** started at phase start, not an end-of-phase write-up.
  `PhaseLogger._EXPECTED_SECTIONS` now covers **every** phase (0-6), not only the analysis phases 3/4/6:
  phases 0 and 5 both put simulations on a scheduler and share a run-and-watch spine (Submission ·
  Simulation Status · Monitoring Armed · Failures and Restarts), with phase 0 adding Sampling Design ·
  Cases Materialized · Verification Plots and phase 5 adding Experiments Designed · V0 Reproducibility
  Gate · Results Preview · Results Summary. Rationale: that operational detail (array IDs, failed-case
  lists, restart commands) is unrecoverable if deferred to the end of the phase, and without the sections
  named a thin phase-0 log looked complete. Phase 4 gains **Success Criteria** — the falsification
  threshold, which `reasoning/schemas.py` has always carried but the logger silently dropped.
  The `check_workflow_state_offline.py` phase-logged WARN now says the same thing. Adopted from
  adapter-kit; examples kept in FATES/Kougarok vocabulary.
- 2026-08-01b: Added **§The phase handshake** (with §The chain accumulates) and **§Enrichment contract**.
  `PhaseLogger` now emits, offline only, a `## Phase Handshake` (inherited / handed on / next action, via
  the new `set_phase_handshake()`), the round's accumulated **`## Reasoning chain`** rebuilt from
  `workflow_state_offline_r{RR}.json` with every entry naming its source log stem, and a
  **`## Sections not provided`** list. Rationale: the online agent passes a typed object between phases so
  its chain cannot break, while offline phases are separated by days and compactions and the log is the
  only channel — and every section sits behind an `if <arg>:` guard, so an unfilled one left no trace and a
  thin call produced a plausible-looking log. Adopted from adapter-kit; the field lists were adapted to this
  repo's evidence schema (`one_line` leads; the `testing` bucket is read alongside `experiments`) and the
  examples retargeted from EcoSIM/PFLOTRAN to FATES/Kougarok.
- 2026-08-01: Added **"Skills and memory invoked"** (both log types): the skills followed, memories applied,
  knowledge consulted (RAG profile + curated keys), and a **Gaps / misfires** line feeding `refine-skill` and,
  as a *candidate* only, `inject-knowledge` / `curate-knowledge`. "None" is a legitimate answer. A calibration
  log recorded the evidence for its conclusion but never which knowledge it was built on, hiding a hypothesis
  formed without checking the KB and a conclusion inherited from a stale entry. Mirrors the same addition to
  the A2MC-development log convention. Adopted from adapter-kit; example retargeted to a real Kougarok
  curated key. *(The same edit also stripped the `log` skill's name from the author-field note, on the
  theory that a public skill must not cite a private one. **Reversed 2026-08-02 by the PI:** such a
  citation is fine and informative — the private skill is a maintainer-side development skill, and a
  reader who wants it can ask. Reference restored, with a pointer to the explanation in
  `.claude/skills/README.md`.)*
- 2026-07-18: Noted the **same-day letter overflow** rule (Type B naming): past `z`, keep the `z` prefix and
  append a second letter (`za, zb, …`), sort-stable; `tools/phase_logger.py::_offline_letter` auto-assigns it. Ported from adapter-kit `65a93ee`.
- 2026-07-17: Split the two artifact jobs explicitly — the `log/{stem}.md` carries the ANALYSIS, the `phase_results/{stem}/` is a SELF-DOCUMENTING folder (per figure: figure + caption/NOTES .md + saved generating .py + data), mirroring `write-report`. The evidence gate (`check_offline_log_evidence.py`) now WARNs on a figure missing its caption/script/data. Ported from adapter-kit `3d187c3`.
- 2026-07-15: Fixed two friction points (ported from adapter-kit `b53ce21`, generic — surfaced while
  exercising the kit on EcoSIM R1, but both apply verbatim to FATES/main): the code example was missing
  `set_iteration_context`'s **required `iteration` positional** (use 0 for Phase 0-2) and set no
  `A2MC_AGENT_MODE`; and the offline flat layout was framed as "optional" when it is **the** convention for
  the interactive agent (the nested `{session_id}/…` form is online/orchestrator-only). Reframed both.
- 2026-07-06: Added the offline (interactive-agent) topic-stem layout note now that `PhaseLogger`
  offline mode landed on main (v2.115, docs/31): `A2MC_AGENT_MODE=offline` → flat `logs/{stem}.md` +
  `phase_results/{stem}/` + per-round `workflow_state_offline`. Generic; online path unchanged.
- 2026-07-01: Created — public skill so the interactive agent logs calibration work the same way
  the autonomous agent does (phase logs) plus a free-form session-log option for exploratory work.
