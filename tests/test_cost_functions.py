"""Tests for tools/cost_functions.py — metric correctness, aggregation, the
targets-satisfied logic, and a regression guarding the skill-score cost direction
(the `to_cost` inversion bug on main; see memory/TODO.md)."""
import math

import numpy as np
import pytest

from tools.cost_functions import (
    CostFunction, ObservationType, aggregate_costs, compute_snapshot_cost,
    within_tolerance, count_targets_satisfied,
)


def snap(method):
    return CostFunction(method=method, obs_type=ObservationType.SNAPSHOT)


def series(method):
    return CostFunction(method=method, obs_type=ObservationType.TIME_SERIES)


# --------------------------- per-metric correctness ---------------------------

def test_relative_error_perfect_is_zero():
    assert snap("relative_error").compute(10.0, 10.0).value == pytest.approx(0.0)


def test_relative_error_known_value():
    # |12 - 10| / 10 == 0.2
    assert snap("relative_error").compute(12.0, 10.0).value == pytest.approx(0.2)


def test_rmse_known_value():
    sim = np.array([1.0, 2.0, 3.0])
    obs = np.array([1.0, 2.0, 5.0])           # residuals 0,0,-2 -> rmse sqrt(4/3)
    assert series("rmse").compute(sim, obs).value == pytest.approx(math.sqrt(4.0 / 3.0))


def test_nse_is_skill_score_higher_is_better():
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    good = np.array([1.1, 2.0, 2.9, 4.1, 5.0])   # close fit
    poor = np.array([3.0, 3.0, 3.0, 3.0, 3.0])   # mean predictor -> nse ~ 0
    assert series("nse").compute(good, obs).value > series("nse").compute(poor, obs).value
    assert series("nse").compute(poor, obs).value == pytest.approx(0.0, abs=1e-9)


def test_correlation_perfect_positive():
    obs = np.array([1.0, 2.0, 3.0, 4.0])
    sim = 2.0 * obs + 5.0                         # perfectly correlated
    assert series("correlation").compute(sim, obs).value == pytest.approx(1.0)


# ------------------------------- aggregation ----------------------------------

def test_aggregate_rmsre():
    assert aggregate_costs([0.1, 0.2, 0.3], method="rmsre") == pytest.approx(
        math.sqrt((0.01 + 0.04 + 0.09) / 3.0))


def test_aggregate_mean_and_max():
    assert aggregate_costs([1.0, 2.0, 3.0], method="mean") == pytest.approx(2.0)
    assert aggregate_costs([1.0, 2.0, 3.0], method="max") == pytest.approx(3.0)


def test_snapshot_cost_better_fit_is_lower():
    obs = {"a": 10.0, "b": 20.0}
    good = {"a": 10.5, "b": 19.0}
    bad = {"a": 15.0, "b": 30.0}
    cost_good, _ = compute_snapshot_cost(good, obs)
    cost_bad, _ = compute_snapshot_cost(bad, obs)
    assert cost_good < cost_bad


# --------------------------- targets-satisfied logic --------------------------

def test_within_tolerance_relative():
    assert within_tolerance(11.0, 10.0, tolerance=0.2) is True     # 10% <= 20%
    assert within_tolerance(13.0, 10.0, tolerance=0.2) is False    # 30% > 20%


def test_count_targets_satisfied():
    obs = {"a": 10.0, "b": 20.0, "c": 30.0}
    sim = {"a": 11.0, "b": 30.0}                  # a within, b out, c missing
    n_ok, n_total, satisfied = count_targets_satisfied(sim, obs, tolerance=0.2)
    assert (n_ok, n_total) == (1, 3)
    assert satisfied == {"a": True, "b": False, "c": False}


# ----------------- regression: skill-score cost direction ---------------------

def test_to_cost_inverts_skill_scores():
    """A correct framework must convert skill scores (nse/kge/correlation; higher=better)
    into costs (lower=better) before the optimizer minimizes — otherwise a better fit
    ranks WORSE. `cost_functions.to_cost()` (v2.102) does this; this is the live regression
    that guards against re-introducing the inversion. Signature is to_cost(value, method)."""
    from tools.cost_functions import to_cost
    # better fit (higher nse) must map to a LOWER cost
    assert to_cost(0.99, "nse") < to_cost(0.0, "nse")
    # proper costs (lower=better) must pass through unchanged
    assert to_cost(0.2, "relative_error") == pytest.approx(0.2)
