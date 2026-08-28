#!/usr/bin/env python3
"""Evidence gate for offline (interactive-agent) phase logs — docs/33 §3a (meta-validation
Phase 1). Targets failure mode FM-1 (verification laxity / over-claiming): a `phase3_diagnosis`
that RESTATES a prior log with no first-hand analysis this session, yet stamps high confidence.

For an offline topic-stem log (`logs/{stem}.md`, stem = YYYYMMDDx_phase{N}_{name}_r{RR}[...]) of
an ANALYSIS phase (3 diagnosis / 4 hypothesis / 6 refinement), this checks:

ERRORS (exit 1) — the restatement-blocker:
  - no resolvable FIRST-HAND ARTIFACT: the log must cite (or have produced) at least one non-`.md`
    artifact — a script (.py), figure (.png/.pdf), or data file (.csv/.txt/.nc/.json) — that EXISTS
    in the log's paired `phase_results/{stem}/`, a `phases/*/generated/` dir, or a relative path
    that resolves. A log that cites only prior `.md` logs is a restatement.

WARNINGS (exit 0) — softer nudges (kept out of ERROR to avoid false positives):
  - phase 3/4 log with Confidence >= 0.95 and no Phase-5 / experiment reference (a diagnosis /
    hypothesis is a hypothesis until a test confirms it — see feedback_no_kb_injection_before_verified_test).
  - an orphan number in a Recommendation / Conclusion / Decision sentence whose value does not appear
    in any cited artifact name or the evidence text.

Non-analysis phases (0/1/2/5/7) and non-offline files are skipped. Dependency-free (stdlib only).

Usage:
    python3 tools/check_offline_log_evidence.py <log.md | logs_dir | --site use_cases/<site>>
"""
import os
import re
import sys
from pathlib import Path

# Offline topic-stem: YYYYMMDDx_phase{N}_{name}_r{RR}[...]_{descriptor}.md
STEM_RE = re.compile(r"^(\d{8}[a-z])_phase(\d+)_[a-z]+_r(\d+)")
ANALYSIS_PHASES = {3, 4, 6}

# A cited artifact FOLDER: phase_results/<full stem>. The `_phase\d+` is load-bearing -- logs
# routinely write `phase_results/20260820a_...` as prose shorthand for "the paired folder", and a
# looser pattern turns every one of those into a blocking dead-pointer ERROR. Measured on main's
# 17 offline logs: this pattern -> 0 matches on such prose; dropping `_phase\d+` -> 5.
ARTIFACT_DIR_RE = re.compile(r"phase_results/(\d{8}[a-z]+_phase\d+_[A-Za-z0-9_]+)")
# A markdown image embed: ![alt](path)
EMBED_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

# The "embed your figures" rule was adopted on main 2026-08-22 (from adapter-kit v2.273, where it
# was ruled the same day). Logs written BEFORE it are grandfathered for the figure WARN only --
# they could not have followed a rule that did not exist. Compared `stem[:8] < EFFECTIVE` so the
# rule fires ON its own effective date; `<=` would silently exempt day zero.
# A dead pointer is NOT dated: it stays an ERROR at any age, and grandfathered logs are still
# checked for it.
EMBED_RULE_EFFECTIVE = "20260822"

# First-hand artifact extensions (NOT .md — logs/notes are not first-hand computation).
ARTIFACT_EXT = {".py", ".png", ".pdf", ".csv", ".txt", ".nc", ".json", ".npy", ".npz"}
# Evidence-section headers we recognize (from templates/logging/ + the offline convention).
EVIDENCE_HEADERS = re.compile(
    r"^#{2,4}\s*(evidence|scripts?\s+(created|run|developed)|"
    r"diagnostic\s+script\s+development|output\s+figures?|"
    r"results?\s+produced|quantitative\s+evidence)\b", re.I | re.M)
DECISION_HDR = re.compile(r"^#{2,4}\s*(.*\b(recommendation|conclusion|decision)s?\b.*)$", re.I | re.M)
# A cited artifact: `name.ext` in backticks, or a bare path token ending in a known ext.
CITED_RE = re.compile(r"`([^`]+?\.(?:py|png|pdf|csv|txt|nc|json|npy|npz))`|"
                      r"(?<![\w`])([\w./\-]+\.(?:py|png|pdf|csv|txt|nc|json|npy|npz))")


def cited_artifacts(text):
    out = set()
    for m in CITED_RE.finditer(text):
        out.add((m.group(1) or m.group(2)).strip())
    return out


def resolve(name, site_dir, stem, repo_root):
    """True if a cited artifact name/path resolves to an existing file produced by this work."""
    cands = []
    p = Path(name)
    # absolute or repo-relative path as written
    cands.append((repo_root / name).resolve() if not p.is_absolute() else p)
    base = p.name
    # paired topic-artifact folder
    cands.append(site_dir / "memory" / "phase_results" / stem / base)
    # generated diagnostic scripts (any phase)
    for g in (repo_root / "phases").glob("*/generated"):
        cands.append(g / base)
    for c in cands:
        try:
            if Path(c).is_file():
                return True
        except OSError:
            continue
    # last resort: basename match anywhere under the topic folder
    topic = site_dir / "memory" / "phase_results" / stem
    if topic.is_dir():
        for f in topic.rglob(base):
            if f.is_file():
                return True
    return False


def parse_confidence(text):
    m = re.search(r"confidence[:*\s]+\**\s*([0-9]*\.?[0-9]+)\s*(%?)", text, re.I)
    if not m:
        return None
    val = float(m.group(1))
    if m.group(2) == "%" or val > 1.5:  # a percentage
        val /= 100.0
    return val


SKILLS_HDR = re.compile(r"^#{2,4}\s*Skills and memory invoked\s*$", re.I | re.M)
# A skill claim is checkable only if it names WHERE in the skill it followed, or says it deviated.
SKILL_TICK = re.compile(r"`([a-z0-9][a-z0-9-]{2,})`")
STEP_REF = re.compile(r"(?:§|\bsteps?\s*|\bsec(?:tion)?\.?\s*)([0-9]+[a-z]?)", re.I)
DEVIATED = re.compile(r"\bdeviat|\bnot followed\b|\bskipped\b|\bmisfire", re.I)


def _skill_dir(repo_root):
    return repo_root / ".claude" / "skills"


def check_skill_citations(text, name, repo_root):
    """WARN when the 'Skills and memory invoked' section records recollection, not a claim.

    Rationale (dev_logs/reflection/20260809a): this section is meant to be the checkpoint where a
    deviation is caught, but written from memory it cannot fail -- the recollection IS the
    deviation. Requiring a step reference (or an explicit 'deviated') per skill forces the
    skill file open, and the citation is verifiable: you cannot cite a step that does not
    exist. This does NOT verify the step was followed; it makes the claim falsifiable.

    Only skills that actually use numbered `## Step N` headings are held to this -- a skill
    organised by named sections (e.g. `plotting`) has no step to cite, and demanding one
    would manufacture a false citation, which is worse than none.
    """
    out = []
    m = SKILLS_HDR.search(text)
    if not m:
        return out
    seg = text[m.end(): m.end() + 2500]
    sm = re.search(r"^\s*[-*]\s*\*\*Skills:?\*\*(.+?)(?=^\s*[-*]\s*\*\*|\Z)",
                   seg, re.S | re.M)
    if not sm:
        return out
    claim = sm.group(1)
    skills_dir = repo_root / ".claude" / "skills"

    # Split the bullet into one clause per backticked item, so a neighbour's "Step 4"
    # cannot be read as this skill's citation.
    toks = [(mm.start(), mm.group(1)) for mm in SKILL_TICK.finditer(claim)]
    seen = set()
    for idx, (pos, cand) in enumerate(toks):
        sk = skills_dir / cand / "SKILL.md"
        if not sk.is_file():
            continue                                    # not a skill name
        if cand in seen:
            continue        # a skill named twice is still ONE claim; prose that mentions it
        seen.add(cand)      # again (e.g. explaining a deviation) must not re-trigger.
        stop = toks[idx + 1][0] if idx + 1 < len(toks) else len(claim)
        clause = claim[pos:stop]
        if DEVIATED.search(clause):
            continue                                    # an explicit deviation IS a claim
        body = sk.read_text(encoding="utf-8", errors="replace")
        # Three heading forms the skills use: "## Step 9 -- ..." / sub-step "### 9d -- ..." /
        # bold-numbered-list ("**0. Branch by intent...**", model-evolution + port-param-file).
        steps = set(re.findall(r"^#{2,4}\s*(?:Step\s*)?([0-9]+[a-z]?)\b", body, re.I | re.M))
        steps |= set(re.findall(r"^\*\*([0-9]+[a-z]?)\.\s", body, re.M))
        if not steps:
            continue                                    # skill has no steps to cite
        ref = STEP_REF.search(clause)
        if not ref:
            out.append(
                "%s: skill `%s` is listed with no step reference and no deviation note -- an "
                "unfalsifiable recollection. Cite the step you followed (e.g. `%s` Step 4) or "
                "state the deviation (dev_logs/reflection/20260809a)." % (name, cand, cand))
            continue
        step = ref.group(1).lower()
        if step not in {x.lower() for x in steps}:
            out.append(
                "%s: skill `%s` is cited at Step %s, which does NOT exist in "
                ".claude/skills/%s/SKILL.md (has: %s) -- the citation cannot be right." %
                (name, cand, step, cand, ", ".join(sorted(steps, key=str))))
    return out


def _dead_artifact_pointers(name, text, site_dir):
    """ERROR on a cited phase_results/<stem>/ directory that does not exist.

    A dead pointer is worse than a missing one: it reads as a citation, so a reader chases it
    instead of disbelieving it.

    The usual cause is an ordering bug, which is why the message says so: `PhaseLogger` bakes the
    reasoning-chain block into the log at write time from workflow_state_offline_r{RR}.json, and
    nothing rewrites a log afterwards. Writing the log and THEN repointing the state freezes the
    superseded stem permanently. State first, log second.
    """
    out, seen = [], set()
    pr = site_dir / "memory" / "phase_results"
    for stem in ARTIFACT_DIR_RE.findall(text):
        if stem in seen:
            continue
        seen.add(stem)
        if not (pr / stem).is_dir():
            out.append(
                f"{name}: cites `phase_results/{stem}/` which does not exist — a dead artifact "
                f"pointer. If the stem was renamed, the log must be REGENERATED after the state "
                f"is repointed: PhaseLogger bakes the reasoning chain in at write time, so state "
                f"first, log second.")
    return out


def _unembedded_figures(name, text, site_dir, stem):
    """WARN when the paired folder holds figures the log never shows.

    A phase log and its artifact folder are meant to review as ONE document. Naming a folder is not
    showing a figure: `phase_results/{stem}/foo.png` in prose renders as text and the reader has to
    go hunting. Embed as `![](../phase_results/{stem}/foo.png)`.

    Dated: see EMBED_RULE_EFFECTIVE. Returns [] for a grandfathered stem.
    """
    if stem[:8] < EMBED_RULE_EFFECTIVE:
        return []
    topic = site_dir / "memory" / "phase_results" / stem
    if not topic.is_dir():
        return []
    figs = sorted(f.name for f in topic.iterdir()
                  if f.is_file() and f.suffix.lower() in (".png", ".pdf"))
    if not figs:
        return []
    embedded = {Path(m).name for m in EMBED_RE.findall(text)}
    missing = [f for f in figs if f not in embedded]
    if not missing:
        return []
    return [f"{name}: {len(missing)} of {len(figs)} figure(s) in phase_results/{stem}/ are not "
            f"EMBEDDED in the log ({', '.join(missing[:3])}"
            f"{'…' if len(missing) > 3 else ''}) — embed each as "
            f"`![](../phase_results/{stem}/<file>.png)` with a bold **Figure N.** caption, so the "
            f"log and its evidence review as one document. Naming the folder in prose is not "
            f"showing the figure."]


def check_log(path, repo_root):
    """Return (errors, warnings) for one offline log file."""
    errors, warnings = [], []
    name = path.name
    m = STEM_RE.match(name)
    if not m:
        return errors, warnings  # not an offline topic-stem log
    stem = name[:-3] if name.endswith(".md") else name
    phase = int(m.group(2))
    text0 = path.read_text(encoding="utf-8", errors="replace")
    skill_warns = check_skill_citations(text0, name, repo_root)
    # site dir = parent of the logs/ dir the file lives in
    logs_dir = path.parent
    site_dir = logs_dir.parent.parent  # .../{site}/memory/logs/file -> .../{site}

    # --- UNIVERSAL: run for EVERY offline phase log, above the analysis-phase early return. ---
    # The restatement checks below are rightly analysis-only, but "the log's pointers must not be
    # dead" and "the log must show its figures" are universal. This early return used to sit at the
    # top of the function, so a phase-0/1/2/5/7 log got a clean bill from code that had inspected
    # NOTHING -- and the summary line still counted it as checked.
    universal_errors = _dead_artifact_pointers(name, text0, site_dir)
    universal_warns = _unembedded_figures(name, text0, site_dir, stem)

    if phase not in ANALYSIS_PHASES:
        return universal_errors, skill_warns + universal_warns

    errors.extend(universal_errors)
    text = text0
    warnings.extend(skill_warns)
    warnings.extend(universal_warns)

    # --- ERROR: at least one resolvable first-hand artifact ---
    arts = cited_artifacts(text)
    resolved = [a for a in arts if resolve(a, site_dir, stem, repo_root)]
    if not resolved:
        # also accept a non-empty paired topic folder as produced evidence
        topic = site_dir / "memory" / "phase_results" / stem
        produced = topic.is_dir() and any(
            f.suffix in ARTIFACT_EXT for f in topic.rglob("*") if f.is_file())
        if not produced:
            errors.append(
                f"{name}: no resolvable first-hand artifact — a phase{phase} (analysis) log must "
                f"cite a script/figure/data file produced THIS session (in phase_results/{stem}/ or "
                f"a phases/*/generated/ dir). Citing only prior .md logs is a restatement "
                f"(feedback_offline_logs_need_first_hand_analysis).")

    # --- WARN: high confidence for a pre-test phase, no Phase-5/experiment link ---
    if phase in (3, 4):
        conf = parse_confidence(text)
        has_test_link = bool(re.search(r"phase[_ ]?5|_c\d+_|experiment[_ ]id|verified_by", text, re.I))
        if conf is not None and conf >= 0.95 and not has_test_link:
            warnings.append(
                f"{name}: Confidence {conf:.2f} on a phase{phase} log with no Phase-5/experiment "
                f"link — a diagnosis/hypothesis is a hypothesis until a test confirms it; do not "
                f"promote to the curated KB yet (feedback_no_kb_injection_before_verified_test).")

    # --- WARN: orphan number in a recommendation/conclusion/decision sentence ---
    art_blob = " ".join(arts) + " " + " ".join(
        # numbers appearing in evidence sections
        EVIDENCE_HEADERS.split(text)[-1:] if EVIDENCE_HEADERS.search(text) else [])
    for hm in DECISION_HDR.finditer(text):
        seg = text[hm.end(): hm.end() + 600]
        for num in re.findall(r"(?<![\w.])(\d{2,}(?:\.\d+)?)", seg):
            if num not in art_blob and num not in "".join(resolved):
                warnings.append(
                    f"{name}: load-bearing number `{num}` appears in a "
                    f"{hm.group(1).strip().lower()} but is not traceable to a cited artifact — "
                    f"verify it first-hand (feedback_performance_experiment_is_the_objective).")
                break  # one nudge per decision section is enough

    # --- WARN: the paired artifact folder should be SELF-DOCUMENTING (figure + caption + script + data) ---
    # A figure with no caption / no generating script / no data is under-documented: a future reader can't
    # tell what it shows, how it was made, or from what. Mirror the write-report self-contained folder.
    topic = site_dir / "memory" / "phase_results" / stem
    if topic.is_dir():
        exts = {f.suffix.lower() for f in topic.rglob("*") if f.is_file()}
        if exts & {".png", ".pdf"}:  # there is a figure to document
            missing = []
            if ".md" not in exts:
                missing.append("a caption/NOTES .md (what it shows + how-to-read + provenance)")
            if ".py" not in exts:
                missing.append("the generating .py script (saved, reproducible — not an inline heredoc)")
            if not (exts & {".csv", ".txt", ".nc", ".json", ".npz", ".npy"}):
                missing.append("the underlying data file")
            if missing:
                warnings.append(
                    f"{name}: phase_results/{stem}/ has a figure but is not self-documenting — add "
                    f"{'; '.join(missing)} (figures>tables>words + the write-report self-contained-folder "
                    f"discipline). The log/{{stem}}.md carries the analysis; the folder must let a future "
                    f"reader regenerate + interpret the figure without you.")
    return errors, warnings


def gather(target):
    p = Path(target)
    if p.is_file():
        return [p]
    if p.is_dir():
        # a site dir or a logs dir
        logs = p / "memory" / "logs" if (p / "memory" / "logs").is_dir() else p
        return sorted(f for f in logs.glob("*.md") if STEM_RE.match(f.name))
    return []


def main(argv):
    if not argv:
        print("usage: check_offline_log_evidence.py <log.md | logs_dir | --site use_cases/<site>>")
        return 2
    if argv[0] == "--site":
        target = argv[1]
    else:
        target = argv[0]
    repo_root = Path(__file__).resolve().parent.parent
    files = gather(target)
    all_err, all_warn = [], []
    n_analysis, n_grandfathered = 0, 0
    for f in files:
        e, w = check_log(f, repo_root)
        all_err += e
        all_warn += w
        m = STEM_RE.match(f.name)
        if m:
            if int(m.group(2)) in ANALYSIS_PHASES:
                n_analysis += 1
            if m.group(1)[:8] < EMBED_RULE_EFFECTIVE:
                n_grandfathered += 1
    for w in all_warn:
        print(f"  [warn] {w}")
    if all_err:
        print(f"\n✘ {len(all_err)} evidence problem(s):")
        for e in all_err:
            print(f"  - {e}")
        return 1
    # SCANNED vs CHECKED, deliberately: the old line said "N analysis log(s) checked" for every
    # file it opened, including phases it returned from without inspecting. That green tick was
    # quoted as evidence of quality for logs nothing had examined. Say what was actually done.
    print(f"✔ offline log evidence gate: {len(files)} log(s) scanned "
          f"(all checked for dead pointers + unembedded figures; "
          f"{n_analysis} analysis log(s) additionally checked for restatement), "
          f"{len(all_warn)} warning(s), 0 errors")
    if n_grandfathered:
        # Counted and printed, never silent: a backlog that vanishes from the output stops being
        # a decision anybody makes.
        print(f"  ({n_grandfathered} log(s) predate {EMBED_RULE_EFFECTIVE} and are grandfathered "
              f"for the figure-embed warning only — dead pointers still error at any age)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
