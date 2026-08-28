"""The staleness guard in restart_experiment_case.py.

These tests exist because the guard's first "verification" ran it against a live case whose
stale restart was a 0-byte placeholder -- already excluded by get_restart_files' size filter.
The guard never executed, and the sane-looking output read as a pass. Each test below asserts
BOTH polarities so a silently-inert guard cannot look healthy.

Run with a repo-internal basetemp (NERSC: no writes outside $HOME):
    python -m pytest tests/test_restart_staleness_guard.py --basetemp=./tmp/pytest -q
"""
import os
import sys
import time
import pytest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "tools"))
# The import chain (restart_experiment_case -> diagnose_ensemble_status -> tools.config)
# resolves several required env vars at MODULE level. The guard under test touches none of
# them, so stub them to repo-internal dummies rather than requiring a sourced site config --
# that keeps this test runnable in a bare checkout / CI.
for _k, _v in {
    "A2MC_OUTPUT_ROOT": str(_REPO / "tmp" / "unused_output_root"),
    "A2MC_ENSEMBLE_NAME": "unused",
    "A2MC_E3SM_ROOT": str(_REPO / "tmp" / "unused_e3sm_root"),
    "A2MC_MODEL_PATH": str(_REPO / "tmp" / "unused_e3sm_root"),
}.items():
    os.environ.setdefault(_k, _v)

from restart_experiment_case import _check_restart_staleness  # noqa: E402

CASE = "TestCase_RGSP"


def _mk(run_root, year, mtime):
    d = Path(run_root) / "run"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{CASE}.elm.r.{year:04d}-01-01-00000.nc"
    f.write_bytes(b"\0" * 4096)
    os.utime(f, (mtime, mtime))
    return f


def test_coherent_segment_is_allowed(tmp_path):
    """Year order == mtime order: the normal case must NOT raise."""
    t = time.time()
    for i, y in enumerate((211, 221, 231)):
        _mk(tmp_path, y, t + i * 3600)
    _check_restart_staleness(str(tmp_path), CASE, [211, 221, 231])  # must not raise


def test_stale_high_year_is_refused(tmp_path):
    """A valid-sized high-year restart written EARLIER than lower years must raise.

    This is the case get_restart_files' size filter cannot see, and the only reason the
    guard exists.
    """
    t = time.time()
    _mk(tmp_path, 401, t - 7 * 86400)          # superseded segment, written a week ago
    for i, y in enumerate((211, 221, 251)):
        _mk(tmp_path, y, t + i * 3600)
    with pytest.raises(RuntimeError) as e:
        _check_restart_staleness(str(tmp_path), CASE, [211, 221, 251, 401])
    msg = str(e.value)
    assert "0401" in msg and "0251" in msg, msg
    assert "--restart-year 251" in msg, "must name the exact remedy, not just complain"


def test_single_file_is_allowed(tmp_path):
    """One restart file cannot be inconsistent with itself."""
    _mk(tmp_path, 211, time.time())
    _check_restart_staleness(str(tmp_path), CASE, [211])


def test_missing_files_are_skipped_not_crashed(tmp_path):
    """Years with no file on disk must be ignored, not raise KeyError/OSError."""
    t = time.time()
    _mk(tmp_path, 211, t)
    _mk(tmp_path, 221, t + 3600)
    _check_restart_staleness(str(tmp_path), CASE, [211, 221, 999])
