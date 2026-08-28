"""PhaseLogger.topic_stem() must survive a process boundary.

Adopted from adapter-kit v2.274 (re-authored, per adopt-from-adapter-kit).

The defect: `_offline_stems` is a per-PROCESS dict and `_offline_letter()` returns the next FREE
same-day letter. In the ordinary two-process shape -- one run writes figures into
`phase_results/`, a later run writes the log -- the second process sees the first's folder
occupying `c`, allocates `d`, and the log silently stops matching its own artifact folder.

Preventive on main: a scan on 2026-08-22 found 0 existing mismatched pairs here. These tests keep
it that way.

The reuse must match on the FULL suffix. Matching on the date alone would be a WORSE bug --
two topics on the same day collapsing onto one letter and overwriting each other -- so the
different-topic test below is as load-bearing as the reuse test.
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from phase_logger import PhaseLogger  # noqa: E402


@pytest.fixture()
def site(tmp_path):
    d = tmp_path / "use_cases" / "S"
    (d / "memory" / "logs").mkdir(parents=True)
    (d / "memory" / "phase_results").mkdir(parents=True)
    return d


def _logger(site):
    """A fresh PhaseLogger == a fresh process, as far as the in-memory stem cache is concerned."""
    return PhaseLogger(site_dir=str(site), calibration_round=1, experiment_count=1)


def test_same_process_is_stable(site):
    lg = _logger(site)
    assert lg.topic_stem(5, "my topic") == lg.topic_stem(5, "my topic")


def test_stem_survives_a_new_process_via_the_artifact_dir(site):
    """Process 1 creates the artifact folder; process 2 must reuse its letter, not advance."""
    lg1 = _logger(site)
    stem1 = lg1.topic_stem(5, "my topic")
    (site / "memory" / "phase_results" / stem1).mkdir()

    lg2 = _logger(site)                      # new process: empty cache
    assert lg2.topic_stem(5, "my topic") == stem1


def test_stem_survives_a_new_process_via_the_log(site):
    """The mirror case: the log exists first, the artifacts come later."""
    lg1 = _logger(site)
    stem1 = lg1.topic_stem(5, "my topic")
    (site / "memory" / "logs" / f"{stem1}.md").write_text("x")

    lg2 = _logger(site)
    assert lg2.topic_stem(5, "my topic") == stem1


def _letter(stem):
    """The same-day sequence letter: the run of [a-z] between the date and the first '_'."""
    return stem[8:stem.index("_")]


def test_a_different_topic_same_day_does_not_collide(site):
    """The guard on the fix. Reusing too eagerly collapses two topics onto one letter.

    Asserting only `stem_b != stem_a` is NOT enough -- the differing descriptor satisfies that
    even when both topics take letter 'a', which is precisely the collision. Mutation-checked:
    breaking both halves of the matcher leaves the weaker assertion green and this one red.
    """
    lg1 = _logger(site)
    stem_a = lg1.topic_stem(5, "topic alpha")
    (site / "memory" / "phase_results" / stem_a).mkdir()

    lg2 = _logger(site)
    stem_b = lg2.topic_stem(5, "topic beta")
    assert stem_b.endswith("_topic_beta")
    assert _letter(stem_b) != _letter(stem_a), (
        f"two same-day topics collapsed onto letter {_letter(stem_a)!r}: "
        f"{stem_a} vs {stem_b} — the sequence letter must stay one-per-topic")


def test_a_different_phase_same_descriptor_does_not_collide(site):
    lg1 = _logger(site)
    stem5 = lg1.topic_stem(5, "same words")
    (site / "memory" / "phase_results" / stem5).mkdir()

    lg2 = _logger(site)
    stem3 = lg2.topic_stem(3, "same words")
    assert stem3 != stem5


def test_a_different_round_does_not_collide(site):
    lg1 = PhaseLogger(site_dir=str(site), calibration_round=1, experiment_count=1)
    stem_r1 = lg1.topic_stem(5, "same words")
    (site / "memory" / "phase_results" / stem_r1).mkdir()

    lg2 = PhaseLogger(site_dir=str(site), calibration_round=2, experiment_count=1)
    assert lg2.topic_stem(5, "same words") != stem_r1


def test_artifact_dir_and_log_stem_agree_across_processes(site):
    """The pairing this exists to protect, end to end."""
    lg1 = _logger(site)
    d = lg1.topic_artifact_dir(5, "my topic")
    lg2 = _logger(site)
    assert lg2.topic_stem(5, "my topic") == d.name


# --------------------------------------------------- the 60-char cut (adapter-kit f9f4828f)

def test_stem_never_ends_in_a_separator():
    """`_clean_descriptor` truncates at 60; the cut can land on the '_' between two words.

    A stem ending in a separator makes logs/{stem}.md and phase_results/{stem}/ differ from a
    stem derived any other way — reintroducing, one layer down, exactly the pairing failure
    `_existing_offline_letter` exists to prevent.
    """
    from phase_logger import PhaseLogger as P
    raw = "_".join(["aaaa"] * 20)          # separators every 5 chars; s[:60] ends on one
    assert raw[:60].endswith("_"), "fixture invalid: the cut must land on a separator"
    out = P._clean_descriptor(" ".join(["aaaa"] * 20))
    assert not out.endswith("_"), out
    assert out                              # and it is not emptied


def test_clean_descriptor_still_falls_back_when_emptied():
    """Stripping must not turn a punctuation-only descriptor into an empty stem."""
    from phase_logger import PhaseLogger as P
    assert P._clean_descriptor("///") == "topic"
