---
name: add-skill
description: Scaffold + register (or retire + de-register) an A2MC skill so the registry steps are never half-done. Use when the user or agent wants to create a new capability — "add a skill", "create/scaffold a skill", "make this reusable as a skill", "distill X into a skill" — OR to remove one — "remove/retire/delete the X skill". Writes (or deletes) the SKILL.md, and registers (or de-registers) it across all THREE human-facing registries (the README 'Current skills' table, docs/a2mc_reference/skills_catalog.md, AND the AGENTS.md 'At a glance' table), runs the mechanical drift check, and stops for human review before commit. Human-gated.
allowed-tools: [Read, Glob, Grep, Write, Edit, Bash]
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [meta]
  summary: "Scaffold + register a new skill; meta machinery, model-agnostic."
---

# add-skill — scaffold/retire + (de-)register an A2MC skill

A2MC has **three** human-facing registries that must stay in sync with the skills dir (the
README "Current skills" table, `docs/a2mc_reference/skills_catalog.md`, and the AGENTS.md
"At a glance" capability table), so the "create the SKILL.md and update the registries" step
is easy to half-do. `tools/check_skill_registry.py` enforces **4-way parity** (disk ↔ README
↔ catalog ↔ AGENTS.md). This skill does
all of it and verifies it mechanically. Conventions live in `.claude/skills/README.md`
("Adding a new skill", "Refining a skill", anti-patterns).

## When to fire

- The user asks to add/create/scaffold a skill, or to distill an existing procedure into one.
- The agent recognizes a **recurring** pattern (across ≥2 `memory/dev_logs/` or
  `memory/ana_logs/`) worth making reusable — propose it; don't self-create silently.

## Procedure

1. **Is it skill-worthy?** Per the README anti-patterns: not a one-off (wait for the pattern
   to repeat), not a paraphrase of `CLAUDE.md`. A skill encodes the easy-to-get-wrong
   conventions, not an essay.
2. **Name + scope.** Pick a kebab-case `<name>` (A2MC skills are **unprefixed** —
   `rebuild-rag`, not `a2mc-rebuild-rag`). The dir name becomes the `/<name>` invocation.
   **Branch-scoped:** skills are per-branch — a skill that only makes sense on a version-pinned
   manuscript branch doesn't belong on `main` (and vice-versa). Note the branch fit in
   the skill's Notes.
3. **Write `.claude/skills/<name>/SKILL.md`:**
   - `name:` matching the dir; `description:` = the trigger the harness matches (what it does
     + when to use + example phrasings — the highest-leverage line).
   - Body: short purpose → decision tree → numbered recipes (ready-to-run bash, use `$PY` for
     Python-3.10 RAG ops) → guardrails/footguns → cross-references.
   - End with a **`## Changelog`** seeded with a dated "Initial version — distilled from
     <source>." line.
   - **Public-sync aware:** skills ship to the public demo via `sync_to_public.sh`. No
     secrets; host-path tokens are advisory-OK on the demo leg (the leak scan), but prefer
     `$PY` / relative paths / `<placeholders>` over hardcoded personal paths.
4. **Register in all THREE registries (the manual step):**
   - add a row to the **"Current skills" table** in `.claude/skills/README.md`
     (`| [<name>](<name>/SKILL.md) | triggers when… |`);
   - add a **`### \`<name>\`` entry** to `docs/a2mc_reference/skills_catalog.md` (Purpose /
     Invoke when / Backing tools / Key discipline — match the existing entries; if it's part
     of a group like the KB-build pipeline, place it there);
   - add a **`| \`<name>\` | … |` row** to the **"At a glance" capability table** in
     `AGENTS.md` (the public, harness-neutral operating contract — an un-enforced skill here
     is exactly how AGENTS.md silently drifts from what ships).
5. **Verify mechanically:** run `python3 tools/check_skill_registry.py` — it must exit 0
   (confirms **4-way parity** disk ↔ README table ↔ catalog ↔ AGENTS.md, `name:`↔dir, and the
   `## Changelog`). A DRIFT failure means you missed a registry in step 4.
6. **Stop for human review.** Then, after verifying the branch (CLAUDE.md Rule #11), commit
   (`.claude/skills/<name>/` + README + catalog + AGENTS.md) with a plain no-attribution message, and
   write a brief dev_log (the `log` skill) on why it was extracted and from which logs. Do
   not commit unreviewed; do not public-sync (separate explicit action).

## Removing / retiring a skill

Symmetric to adding — de-register from the SAME registries, or the drift check fails. The
add-only asymmetry is exactly how a deleted skill leaves stale registry rows behind.

1. `git rm -r .claude/skills/<name>/`.
2. Remove its entry from all **THREE enforced registries**: the "Current skills" table row in
   `.claude/skills/README.md`, the `### \`<name>\`` entry in `docs/a2mc_reference/skills_catalog.md`,
   and the "At a glance" row in `AGENTS.md`. Also prune its row from the "A2MC Skills" table in
   `CLAUDE.md` (the private dev doc — NOT checker-enforced, so the easiest to forget).
3. **Prune cross-references:** `grep -rn "<name>" .claude/skills docs AGENTS.md CLAUDE.md` — any
   sibling skill that routes to or cites the removed one (a stale citation becomes a DEAD-REF).
4. **Verify mechanically:** `python3 tools/check_skill_registry.py` must exit 0 — a DRIFT means a
   registry still lists the removed skill; a DEAD-REF means a `SKILL.md` still cites it.
5. Human review, verify branch (CLAUDE.md Rule #11), commit, and dev_log why it was retired.

> The same symmetric-removal discipline applies to a **memory**: prune its `MEMORY.md` index line
> + any `[[link]]`. `tools/check_memory_bucket.py` now flags a dead `MEMORY.md` link as an error —
> the memory analog of the DRIFT check.

## Guardrails

- **Register in all THREE or it drifts** — never finish without the README-table row, the
  catalog entry, AND the AGENTS.md "At a glance" row. `tools/check_skill_registry.py` (step 5)
  is the enforceable 4-way-parity backstop; wire it into CI / pre-commit so the invariant holds
  even when this skill isn't used.
- **Minimal procedure** — if it's one obvious step, it may not need to be a skill.
- **Branch-scoped** — don't bake one branch's specifics (a pinned API, a manuscript flow)
  into a skill meant for another. Re-evaluate before copying across branches.
- **Human-gated** — propose + review before commit, consistent with the
  `curate-knowledge` / `inject-knowledge` write-gate stance (a skill is a contract).

## Changelog

- 2026-07-06: Added the **"Removing / retiring a skill"** section — symmetric de-registration from all
  three registries + the DRIFT/DEAD-REF verify, closing the add-only asymmetry that let a removed skill
  leave stale registry rows. `description:` now also fires on "remove/retire a skill". Paired change:
  `tools/check_memory_bucket.py` gained a dead-`MEMORY.md`-link check (the memory analog). Ported from demo `b28e1dc`.
- 2026-06-17: Initial version — A2MC counterpart to E2SA's `e2sa-add-skill`
  (`End2EndScienceAgent/docs/design/09_skill_evolution.md`), adapted for A2MC's registry
  setup and the `tools/check_skill_registry.py` drift gate.
- 2026-07-06: Prose corrected from "two/BOTH registries" to the **three** the checker actually
  enforces (README table + skills_catalog.md + AGENTS.md "At a glance" = 4-way parity with disk).
  The AGENTS.md leg was already enforced by `check_skill_registry.py`; only the doc lagged.
