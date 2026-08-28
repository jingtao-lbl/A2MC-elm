"""The two UNIVERSAL checks in tools/check_offline_log_evidence.py.

Adopted from adapter-kit v2.272 + v2.273 (re-authored, per adopt-from-adapter-kit).

The defect these close: the analysis-phase early return used to sit at the TOP of check_log(), so a
phase-0/1/2/5/7 log received a clean bill from code that had inspected nothing, and the summary
line still counted it as checked. So the load-bearing test here is
`test_non_analysis_phase_is_actually_inspected` — everything else guards its edges.
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import check_offline_log_evidence as ev  # noqa: E402

EFFECTIVE = ev.EMBED_RULE_EFFECTIVE          # "20260822"
BEFORE = "20260801"                          # grandfathered
ON = EFFECTIVE                               # the rule fires ON its effective date


def _site(tmp_path):
    d = tmp_path / "use_cases" / "S"
    (d / "memory" / "logs").mkdir(parents=True)
    (d / "memory" / "phase_results").mkdir(parents=True)
    return d


def _log(site, stem, body):
    p = site / "memory" / "logs" / f"{stem}.md"
    p.write_text(body, encoding="utf-8")
    return p


def _check(path):
    return ev.check_log(path, REPO)


# ------------------------------------------------------------------ the core fix


def test_non_analysis_phase_is_actually_inspected(tmp_path):
    """A phase-5 log (NOT in ANALYSIS_PHASES) must still get the universal checks.

    Before v2.272 this returned (errors=[], ...) from the top of the function without looking at
    anything. If this regresses, a whole class of logs silently stops being checked while the
    summary keeps calling them checked.
    """
    site = _site(tmp_path)
    stem = f"{ON}a_phase5_testing_r01_c01_thing"
    p = _log(site, stem, "see phase_results/20990101a_phase9_nope_r01_gone/ for details\n")
    errors, _ = _check(p)
    assert any("dead artifact pointer" in e for e in errors), errors


def test_analysis_phase_still_gets_universal_checks(tmp_path):
    site = _site(tmp_path)
    stem = f"{ON}a_phase3_diagnosis_r01_c01_iter01_thing"
    p = _log(site, stem, "see phase_results/20990101a_phase9_nope_r01_gone/\n")
    errors, _ = _check(p)
    assert any("dead artifact pointer" in e for e in errors)


# ------------------------------------------------------------------ dead pointers


def test_prose_ellipsis_is_not_a_dead_pointer(tmp_path):
    """`phase_results/20260820a_...` is prose shorthand, not a citation.

    Main's offline logs use this form routinely. A looser pattern (dropping the `_phase\\d+`)
    turns 5 of them into blocking ERRORs on ordinary prose. This is the guard on that.
    """
    site = _site(tmp_path)
    stem = f"{ON}a_phase5_testing_r01_c01_thing"
    p = _log(site, stem, "artifacts live in phase_results/20260820a_... alongside the log\n")
    errors, _ = _check(p)
    assert errors == [], errors


def test_existing_folder_is_not_a_dead_pointer(tmp_path):
    site = _site(tmp_path)
    target = f"{ON}b_phase5_testing_r01_c01_other"
    (site / "memory" / "phase_results" / target).mkdir()
    stem = f"{ON}a_phase5_testing_r01_c01_thing"
    p = _log(site, stem, f"see phase_results/{target}/\n")
    errors, _ = _check(p)
    assert errors == []


def test_dead_pointer_errors_even_on_a_grandfathered_log(tmp_path):
    """Only the FIGURE warning is dated. A dead pointer is an ERROR at any age."""
    site = _site(tmp_path)
    stem = f"{BEFORE}a_phase5_testing_r01_c01_thing"
    p = _log(site, stem, "see phase_results/20990101a_phase9_nope_r01_gone/\n")
    errors, _ = _check(p)
    assert any("dead artifact pointer" in e for e in errors)


# ------------------------------------------------------------------ figure embedding (dated)


def _with_figure(site, stem, body):
    d = site / "memory" / "phase_results" / stem
    d.mkdir(parents=True, exist_ok=True)
    (d / "fig.png").write_bytes(b"\x89PNG")
    return _log(site, stem, body)


def test_unembedded_figure_warns_on_the_effective_date(tmp_path):
    """`stem[:8] < EFFECTIVE` means the rule fires ON its own date; `<=` would exempt day zero."""
    site = _site(tmp_path)
    stem = f"{ON}a_phase5_testing_r01_c01_thing"
    p = _with_figure(site, stem, "no images here\n")
    _, warns = _check(p)
    assert any("not\nEMBEDDED" in w or "not EMBEDDED" in w for w in warns), warns


def test_embedded_figure_does_not_warn(tmp_path):
    site = _site(tmp_path)
    stem = f"{ON}a_phase5_testing_r01_c01_thing"
    p = _with_figure(site, stem, f"![](../phase_results/{stem}/fig.png)\n")
    _, warns = _check(p)
    assert not any("EMBEDDED" in w for w in warns), warns


def test_grandfathered_log_does_not_warn_about_figures(tmp_path):
    site = _site(tmp_path)
    stem = f"{BEFORE}a_phase5_testing_r01_c01_thing"
    p = _with_figure(site, stem, "no images here\n")
    _, warns = _check(p)
    assert not any("EMBEDDED" in w for w in warns), warns


# ------------------------------------------------------------------ the preserved hunk


def test_skill_citation_warnings_survive_on_a_non_analysis_phase(tmp_path):
    """main-specific: check_log returned `errors, skill_warns` on the early-return path.

    adapter-kit's version returns bare `warnings` there. Taking that function wholesale would have
    silently dropped main's skill-citation warnings for every non-analysis log -- the per-hunk
    hazard adopt-from-adapter-kit exists to prevent.
    """
    site = _site(tmp_path)
    stem = f"{ON}a_phase5_testing_r01_c01_thing"
    # The checker requires the canonical `- **Skills:**` bullet shape; a bare backticked name in
    # the section is not what it parses.
    p = _log(site, stem,
             "## Skills and memory invoked\n\n- **Skills:** `calibration-log`\n")
    _, warns = _check(p)
    assert any("calibration-log" in w for w in warns), (
        "skill-citation warnings must still be produced for a non-analysis phase")


@pytest.mark.parametrize("phase", [0, 1, 2, 5, 7])
def test_every_non_analysis_phase_is_covered(tmp_path, phase):
    site = _site(tmp_path)
    names = {0: "design", 1: "exploration", 2: "screening", 5: "testing", 7: "converged"}
    stem = f"{ON}a_phase{phase}_{names[phase]}_r01_thing"
    p = _log(site, stem, "see phase_results/20990101a_phase9_nope_r01_gone/\n")
    errors, _ = _check(p)
    assert any("dead artifact pointer" in e for e in errors), f"phase {phase} not inspected"
