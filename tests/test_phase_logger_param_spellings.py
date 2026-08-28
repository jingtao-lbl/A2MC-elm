"""log_hypothesis must not lose a parameter's name or values to a key-spelling mismatch.

Adopted from adapter-kit `49f195e2` (re-authored). DEFENSIVE on main: 0 affected logs here,
against 20 on the source branch that had lost the NAME and BOTH VALUES of every parameter they
proposed, latent for five weeks.

The failure is silent and unrecoverable: the renderer substitutes "Unknown / N/A / N/A", and once
the source dict is gone the log is the only record. That is the same defect shape
`check_log_placeholders` blocks on — this stops it being produced in the first place.
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from phase_logger import PhaseLogger  # noqa: E402


@pytest.fixture()
def logger(tmp_path):
    site = tmp_path / "use_cases" / "S"
    (site / "memory" / "logs").mkdir(parents=True)
    (site / "memory" / "phase_results").mkdir(parents=True)
    return PhaseLogger(site_dir=str(site), calibration_round=1, experiment_count=1)


CANONICAL = {"name": "fates_leaf_vcmax", "current": 40, "proposed": 55, "rationale": "r"}
ALIASES = [
    {"parameter": "fates_leaf_vcmax", "current_value": 40, "proposed_value": 55},
    {"param": "fates_leaf_vcmax", "from": 40, "to": 55},
    {"name": "fates_leaf_vcmax", "base": 40, "new": 55},
]


def _render(logger, params):
    p = logger.log_hypothesis(
        title="spelling probe", hypothesis_name="H", mechanism="m",
        parameters_to_modify=params)
    return Path(p).read_text(encoding="utf-8")


def test_canonical_spelling_renders(logger):
    t = _render(logger, [CANONICAL])
    assert "fates_leaf_vcmax" in t
    assert "40" in t and "55" in t
    # Scoped to the PARAMETER heading, not the whole file: the log header legitimately renders
    # "Site: Unknown" when A2MC_SITE_NAME is unset, as it is in this fixture. A bare
    # `"Unknown" not in t` fails on that and would have been a false alarm about the renderer.
    assert "### Unknown" not in t


@pytest.mark.parametrize("param", ALIASES)
def test_alias_spellings_do_not_lose_the_parameter(logger, param):
    """Each alias must still produce the name and BOTH values, never Unknown/N/A."""
    t = _render(logger, [param])
    assert "fates_leaf_vcmax" in t, f"name lost for {param}"
    assert "40" in t and "55" in t, f"values lost for {param}"
    assert "### Unknown" not in t, f"rendered Unknown for {param}"


def test_a_genuinely_empty_param_still_degrades_visibly(logger):
    """The fallback must not invent data: an empty dict still renders the honest stub.

    Without this, a broadened matcher could paper over a caller that supplied nothing, which is
    the opposite of the intent — the stub is what check_log_placeholders is meant to catch.
    """
    t = _render(logger, [{"rationale": "no values supplied"}])
    assert "Unknown" in t and "N/A" in t
