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


def check_log(path, repo_root):
    """Return (errors, warnings) for one offline log file."""
    errors, warnings = [], []
    name = path.name
    m = STEM_RE.match(name)
    if not m:
        return errors, warnings  # not an offline topic-stem log
    stem = name[:-3] if name.endswith(".md") else name
    phase = int(m.group(2))
    if phase not in ANALYSIS_PHASES:
        return errors, warnings
    # site dir = parent of the logs/ dir the file lives in
    logs_dir = path.parent
    site_dir = logs_dir.parent.parent  # .../{site}/memory/logs/file -> .../{site}
    text = path.read_text(encoding="utf-8", errors="replace")

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
    for f in files:
        e, w = check_log(f, repo_root)
        all_err += e
        all_warn += w
    for w in all_warn:
        print(f"  [warn] {w}")
    if all_err:
        print(f"\n✘ {len(all_err)} evidence problem(s):")
        for e in all_err:
            print(f"  - {e}")
        return 1
    print(f"✔ offline log evidence gate: {len(files)} analysis log(s) checked, "
          f"{len(all_warn)} warning(s), 0 errors")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
