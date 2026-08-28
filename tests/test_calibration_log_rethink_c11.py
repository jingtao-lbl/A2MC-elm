"""C11 — a Phase-6 log that routes 6->3 must carry the rethink, not just the routing decision.

Adopted from adapter-kit `77632483` (re-authored). **Renumbered C9 -> C11**: adapter-kit's C9 slot
was free there, but main already uses C9 (missing Cross-references) and C10. A silent code collision
would have made two different findings indistinguishable in output.

Preventive on main: no 6->3 rethink has run here yet (`experiment_count=1`,
`phase6_decision=None`), so the enforcement lands before the first one rather than after a round
spends several cycles on one base.
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CHECKER = REPO / "tools" / "check_calibration_log_conformance.py"

HEADER = (
    "# T\n\n"
    "**Site:** S\n**Phase:** 6 (Refinement)\n**Round:** 1\n**Date:** August 23, 2026\n"
    "**Author:** Jing Tao with Claude\n\n"
)
ITERATE = "## Next Action: iterate\n\n"


def _run(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(HEADER + body, encoding="utf-8")
    r = subprocess.run([sys.executable, str(CHECKER), str(p)],
                       capture_output=True, text=True, cwd=REPO)
    return r.stdout + r.stderr


def _c11(out):
    return [l for l in out.splitlines() if "C11" in l]


STEM = "20260823a_phase6_refinement_r01_c01_probe.md"


def test_routes_6to3_with_no_rethink_section_errors(tmp_path):
    out = _run(tmp_path, STEM, ITERATE + "We will iterate.\n")
    assert _c11(out), out
    assert "no Rethink section" in out


def test_rethink_section_present_and_substantive_is_clean(tmp_path):
    body = ITERATE + "## Rethink (6->3)\n\n" + ("word " * 80) + "\nPathway A: raise X.\n"
    assert not _c11(_run(tmp_path, STEM, body))


def test_thin_rethink_section_warns(tmp_path):
    body = ITERATE + "## Rethink\n\nWe thought about it. Pathway A.\n"
    hits = _c11(_run(tmp_path, STEM, body))
    assert hits and "thin" in hits[0], hits


def test_rethink_naming_no_pathway_warns(tmp_path):
    """Its deliverable is candidate PATHWAYS, not a narrative of the cycle."""
    body = ITERATE + "## Rethink\n\n" + ("narrative " * 80) + "\n"
    hits = _c11(_run(tmp_path, STEM, body))
    assert hits and "no PATHWAY" in hits[0], hits


def test_a_phase6_log_that_does_NOT_route_6to3_is_untouched(tmp_path):
    """Converge/redesign logs carry no rethink obligation — the trigger is the iterate routing."""
    body = "## Next Action: converge\n\nAll targets met.\n"
    assert not _c11(_run(tmp_path, STEM, body))


def test_non_phase6_log_is_untouched(tmp_path):
    body = ITERATE + "Nothing here.\n"
    out = _run(tmp_path, "20260823a_phase3_diagnosis_r01_c01_iter01_probe.md", body)
    assert not _c11(out)


def test_rule_is_not_retroactive(tmp_path):
    """A log predating the effective date must not be flagged."""
    out = _run(tmp_path, "20260801a_phase6_refinement_r01_c01_probe.md",
               ITERATE + "We will iterate.\n")
    assert not _c11(out)


def test_code_does_not_collide_with_mains_existing_codes():
    """C9 and C10 are already used on main; a collision makes two findings indistinguishable."""
    src = CHECKER.read_text(encoding="utf-8")
    import re
    codes = set(re.findall(r'"(C\d+)"', src))
    assert "C11" in codes
    # the rethink block must not reuse an existing code
    block = src[src.index("# C11: a Phase-6 log that ROUTES"):]
    block = block[:block.index("    return out")]
    assert '"C9"' not in block and '"C10"' not in block, block
