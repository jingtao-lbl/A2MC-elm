---
name: curate-knowledge
visibility: public
category: calibration
description: Review and promote staged Tier-3 knowledge proposals (the human-in-the-loop curation step that pairs with the memory write gate). Use when the user asks to "review/curate pending knowledge", "promote proposals", "what did the runs propose to learn", "check auto_discovered_pending", or at session start when staged proposals exist. The autonomous online agent stages auto_learn proposals to auto_discovered_pending.json instead of the curated KB; this skill evaluates each against evidence and promotes the vetted ones (or discards misunderstandings).
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [memory]
  summary: "Human-in-the-loop curation of staged Tier-3 proposals; model-agnostic."
---

# Curate Pending Knowledge (human-in-the-loop promotion)

The autonomous online agent (`orchestrator.py --run`) runs its `MemoryManager` in
**propose mode**: its `auto_learn` proposals are staged to
`auto_discovered_pending.json`, **never** written straight to the curated Tier-3 stores
(`discoveries.json` / `failed_approaches.json` / `experiments.json`). This skill is the
**other half of that gate** — the interactive (human-in-the-loop) agent reviews the
staging queue and promotes only vetted entries.

> **Why this matters.** The curated KB shapes the AI's diagnoses. A May-2026
> contamination incident produced 70 false `auto_discovered` entries
> — including `do_not_repeat` rules that **forbade the AI's own best fixes**. The write
> gate stops those reaching curated knowledge automatically; **but if no
> one runs this curation, the gate becomes a silent drop** and the KB stops learning
> from runs. Run it when proposals exist.

## Step 1 — list the queue

```bash
# --memory-dir defaults to $A2MC_USE_CASE_DIR/memory/gained_knowledge
python tools/review_pending_knowledge.py list          # open proposals
python tools/review_pending_knowledge.py list --all    # incl. already promoted/discarded
```

If the queue is empty, you're done. (A G2 `SessionStart` hook can surface the open count
so you know when to run this.)

## Step 2 — evaluate each proposal against evidence

For each open proposal, read its `kind` (discovery / failed_approach / experiment), its
`key`, and the staged `entry` (mechanism, `do_not_repeat`, the experiment results it
came from). Then **cross-check** — do not promote on the proposal's own say-so:

- **Is the result real and reproduced?** Did the experiment actually run with usable
  data? (The data-reliability gate should have caught phantoms, but verify the metrics
  exist and aren't garbage.) Check the run/extract dirs or the cited session.
- **Does the mechanism fit the data and FATES?** If the proposed mechanism is a guess,
  check the RAG / `docs/fates-knowledge-base/` before trusting it. A plausible-sounding
  but unverified story is the exact failure mode that contaminated the KB.
- **Duplicate or contradiction?** Compare to existing curated entries
  (`discoveries.json`, `failed_approaches.json`). Skip duplicates; never let a weaker
  proposal overwrite better-established curated knowledge.
- **Scrutinize every `do_not_repeat`.** This is the highest-risk field: an overbroad
  "never do X" can forbid the right direction. Promote a `do_not_repeat` only if X is a
  genuine, demonstrated dead end — not one failed attempt.

Decision per proposal:

| Verdict | When | Action |
|---|---|---|
| **Promote** | real, reproduced, mechanism fits, not a duplicate, any `do_not_repeat` is a true dead end | `promote --key …` (writes curated, `verified:true`) |
| **Discard** | phantom/no-data, misunderstanding, mechanism unsupported, duplicate, or an overbroad `do_not_repeat` | `discard --key …` |
| **Promote-then-fix / rewrite** | partially right | discard it, then author a corrected curated entry by hand (edit the JSON or use an `interactive`-mode `MemoryManager`) — don't promote a half-right lesson as-is |

## Step 3 — apply

```bash
python tools/review_pending_knowledge.py promote --key <discovery_name>   # vetted → curated
python tools/review_pending_knowledge.py discard --key <name>             # rejected
python tools/review_pending_knowledge.py promote --confidence 0.8 --key X # override confidence
# --index N or --all are also accepted; --all only after you've reviewed every item
```

Never `promote --all` blind — that defeats the gate. Use `--all` only when you have
genuinely reviewed every open item.

## Step 4 — record what you did

Note the curation outcome so it's traceable: which keys were promoted (and why), which
were discarded (and why). For a substantial curation pass, write a short dev log (the
`log` skill); for a quick one, a one-line note referencing the session is enough. The
curated JSONs are hand-vetted manuscript knowledge (CLAUDE.md Rule 3) — the audit trail
matters.

## Notes

- The staging file `auto_discovered_pending.json` is gitignored run-state; promoted
  entries land in the tracked curated JSONs, which the user hand-commits per the
  curation policy.
- Pairs with: the write gate (`tools/review_pending_knowledge.py`) and the memory
  write gate that stages proposals instead of writing curated knowledge.
- This is the **interactive agent's** job by design (Tier-3 curated writes are
  interactive-only). The online agent only proposes.

## Changelog

- 2026-06-17: `## Changelog` convention adopted (see .claude/skills/README.md). Earlier history: git log + memory/dev_logs/.
