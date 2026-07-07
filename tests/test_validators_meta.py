"""Meta-validation tests (docs/33 §3d) — run each new evidence gate against known-good and
known-bad inputs to confirm it actually fires. Guards the 1a phase-log gate + 1b KB-write gate
("who validates the validators"). tmp_path stays under the repo tmp/ via pytest.ini --basetemp.
"""
import json
from pathlib import Path

import pytest

from memory.manager import MemoryManager
from tools.check_offline_log_evidence import check_log


# ---------------------------------------------------------------------------
# 1a — phase-log evidence gate (check_offline_log_evidence.check_log)
# ---------------------------------------------------------------------------
def _write_log(site, stem, body):
    logs = site / "memory" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    p = logs / f"{stem}.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_evidence_gate_fails_restatement(tmp_path):
    """An analysis-phase log that cites only a prior .md log ERRORs (restatement)."""
    site = tmp_path / "site"
    stem = "20260706a_phase3_diagnosis_r05_c00_iter01_restate"
    p = _write_log(site, stem, "# d\n## Executive Summary\nSee `prior_log.md`.\n"
                               "## Parameter Recommendations\nCap it.\n**Confidence:** 0.90\n")
    errors, _ = check_log(p, tmp_path)
    assert errors, "restatement-only analysis log should ERROR (no first-hand artifact)"


def test_evidence_gate_passes_first_hand(tmp_path):
    """An analysis-phase log citing a produced script/figure passes."""
    site = tmp_path / "site"
    stem = "20260706b_phase3_diagnosis_r05_c00_iter01_good"
    art = site / "memory" / "phase_results" / stem
    art.mkdir(parents=True)
    (art / "analyze_l2fr.py").write_text("print('x')")
    (art / "dist.png").write_text("fig")
    p = _write_log(site, stem, "# d\n## Scripts Created\nRan `analyze_l2fr.py` this session.\n"
                               "## Output Figures\n`dist.png`\n**Confidence:** 0.7\n")
    errors, _ = check_log(p, tmp_path)
    assert not errors, f"first-hand log should pass; got {errors}"


def test_evidence_gate_skips_non_analysis_phase(tmp_path):
    """A non-analysis phase (e.g. phase 2 screening) is not gated."""
    site = tmp_path / "site"
    stem = "20260706c_phase2_screening_r05_screen"
    p = _write_log(site, stem, "# screening\nno artifacts here\n")
    errors, _ = check_log(p, tmp_path)
    assert not errors, "non-analysis phase should be skipped (no error)"


def test_evidence_gate_warns_high_confidence_no_test(tmp_path):
    """phase-3/4 log with Confidence>=0.95 and no Phase-5 link WARNs (not error)."""
    site = tmp_path / "site"
    stem = "20260706d_phase4_hypothesis_r05_c00_iter02_overclaim"
    art = site / "memory" / "phase_results" / stem
    art.mkdir(parents=True)
    (art / "skiptest.csv").write_text("a,b\n1,2\n")
    p = _write_log(site, stem, "# h\n## Evidence\n`skiptest.csv`\n"
                               "## Conclusion\nConfirmed. **Confidence:** 0.97\n")
    errors, warnings = check_log(p, tmp_path)
    assert not errors
    assert any("Confidence" in w for w in warnings), "high confidence w/o test link should WARN"


# ---------------------------------------------------------------------------
# 1b — curated-KB write verified_by gate (memory.manager.add_discovery)
# ---------------------------------------------------------------------------
def test_verified_by_gate_raises_without_link(tmp_path):
    m = MemoryManager(str(tmp_path), write_mode="interactive")
    with pytest.raises(ValueError):
        m.add_discovery("x", "d", "mech", ["leaf_pft7"], source="curated", verified=True)


def test_verified_by_gate_ok_with_link(tmp_path):
    m = MemoryManager(str(tmp_path), write_mode="interactive")
    m.add_discovery("x", "d", "mech", ["leaf_pft7"], source="curated",
                    verified=True, verified_by="r05_c01_joint_corner_test")
    disc = json.loads((tmp_path / "discoveries.json").read_text())
    assert disc["x"]["verified"] is True
    assert disc["x"]["verified_by"] == "r05_c01_joint_corner_test"


def test_verified_by_grandfathers_legacy(tmp_path):
    """A legacy caller (source='curated', no verified) is not broken by the gate."""
    m = MemoryManager(str(tmp_path), write_mode="interactive")
    m.add_discovery("x", "d", "mech", ["leaf_pft7"], source="curated")
    disc = json.loads((tmp_path / "discoveries.json").read_text())
    assert disc["x"]["verified"] is True  # grandfathered


def test_verified_by_explicit_false_is_unverified(tmp_path):
    m = MemoryManager(str(tmp_path), write_mode="interactive")
    m.add_discovery("x", "d", "mech", ["leaf_pft7"], source="curated", verified=False)
    disc = json.loads((tmp_path / "discoveries.json").read_text())
    assert disc["x"]["verified"] is False
