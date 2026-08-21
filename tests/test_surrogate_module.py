"""Tests for ``models.surrogate`` — the S0/S1 emulator foundation.

Synthetic data with known structure throughout; no dependency on a real physics-model
ensemble (that is step A4). Each test encodes WHY the behaviour matters, not
merely that the code runs, because most of these guards exist to stop a specific
recorded failure from recurring.
"""
import json

import numpy as np
import pytest

from models.surrogate import (
    CLASSIFIERS,
    HullGate,
    KnowledgeGuidedLoss,
    LEARNERS,
    Provenance,
    RFLearner,
    S0Surrogate,
    S1Surrogate,
    SurrogateSpec,
    TargetSpec,
    apply_transform,
    hash_param_list,
    explain_recommendation,
    invert_transform,
    load,
    make_classifier,
    make_learner,
    recommend,
    recommend_goals,
)
from models.surrogate.validate import (
    RANK_KEYS,
    bakeoff_summary,
    compare_learners,
    rank_results,
    interval_coverage,
    manifold_respect,
    ranking_fidelity,
    record_confirmation,
    run_acceptance,
)


# =============================================================================
# Fixtures — a smooth 2-input, 2-target problem with a viability boundary
# =============================================================================

def _spec(tier="S1", transforms=("identity", "identity")):
    return SurrogateSpec(
        name="test", use_mode="offline_search", tier=tier,
        input_names=("a", "b"), input_lower=(0.0, 0.0), input_upper=(1.0, 1.0),
        targets=(TargetSpec("plant_C", observed=1.0, lower=0.8, transform=transforms[0]),
                 TargetSpec("NPP", observed=2.0, upper=2.5, transform=transforms[1])),
        provenance=Provenance(model="fates", model_commit="deadbeef",
                              param_list_hash="0123456789abcdef",
                              base_param_file_hash="fedcba9876543210",
                              scoring_convention="targets-yaml-v1",
                              training_ensemble_id="test-ensemble",
                              a2mc_version="v2.218", created="2026-07-31"))


def _data(n=300, seed=0, with_failures=True):
    """Y is a smooth function of X; rows with a < 0.15 are 'dead' (NaN targets).

    The dead region mimics the knife-edge structure the real model has (the
    VCMX4 collapse): a sharp cliff rather than a gradient.
    """
    rng = np.random.default_rng(seed)
    X = rng.uniform(0, 1, size=(n, 2))
    y0 = 1.0 + 0.8 * X[:, 0] - 0.3 * X[:, 1]
    y1 = 2.0 + 0.5 * X[:, 0] * X[:, 1]
    Y = np.column_stack([y0, y1]) + rng.normal(0, 0.01, size=(n, 2))
    viable = np.ones(n, dtype=bool)
    if with_failures:
        viable = X[:, 0] >= 0.15
        Y[~viable] = np.nan
    return X, Y, viable


# =============================================================================
# Spec: the seam must refuse a design it cannot represent
# =============================================================================

def test_spec_rejects_length_mismatch():
    """A silent names/bounds mismatch permutes the design matrix invisibly."""
    with pytest.raises(ValueError, match="length mismatch"):
        SurrogateSpec(name="x", use_mode="offline_search", tier="S0",
                      input_names=("a", "b"), input_lower=(0.0,), input_upper=(1.0, 1.0))


def test_spec_rejects_inverted_bounds_and_bad_transform():
    with pytest.raises(ValueError, match="lower .* > upper"):
        SurrogateSpec(name="x", use_mode="offline_search", tier="S0",
                      input_names=("a",), input_lower=(1.0,), input_upper=(0.0,))
    with pytest.raises(ValueError, match="transform"):
        TargetSpec("t", transform="sqrt")


def test_spec_rejects_unknown_use_mode_and_tier():
    """use_mode selects the acceptance battery, so a typo must not fall through."""
    with pytest.raises(ValueError, match="use_mode"):
        SurrogateSpec(name="x", use_mode="online", tier="S0")
    with pytest.raises(ValueError, match="tier"):
        SurrogateSpec(name="x", use_mode="offline_search", tier="S9")


def test_spec_roundtrip(tmp_path):
    s = _spec()
    p = tmp_path / "spec.json"
    s.write(p)
    back = SurrogateSpec.read(p)
    assert back == s
    assert back.target("NPP").upper == 2.5


def test_param_list_hash_includes_bounds():
    """Same names over different bounds is a DIFFERENT design (R1's void bounds)."""
    a = hash_param_list(["p"], [0.0], [1.0])
    b = hash_param_list(["p"], [0.0], [2.0])
    assert a != b


def test_provenance_mismatch_ignores_unstamped_but_reports_them():
    a = Provenance(model="fates", scoring_convention="targets-yaml-v1")
    b = Provenance(model="fates", scoring_convention="targets-yaml-v2")
    assert a.mismatches(b) == ["scoring_convention"]
    # An unrecorded field is unknown, not a mismatch, but must be visible.
    c = Provenance(model="fates")
    assert c.mismatches(a) == []
    assert "scoring_convention" in c.unstamped_fields()


# =============================================================================
# Transforms
# =============================================================================

def test_transforms_roundtrip():
    y = np.array([0.2, 0.5, 0.9])
    for kind in ("identity", "log", "logit"):
        assert np.allclose(invert_transform(apply_transform(y, kind), kind), y)


def test_log_transform_refuses_nonpositive():
    """Structural admissibility must fail loudly, not silently emit NaN."""
    with pytest.raises(ValueError, match="strictly positive"):
        apply_transform(np.array([1.0, -1.0]), "log")


# =============================================================================
# S0
# =============================================================================

def test_s0_predicts_and_ranks():
    X, Y, viable = _data()
    m = S0Surrogate(_spec(tier="S0")).fit(X, Y, viable)
    Xt, Yt, vt = _data(n=120, seed=1)
    pred = m.predict_batch(Xt[vt])
    r = ranking_fidelity(Yt[vt][:, 0], pred.values[:, 0])
    assert r["spearman"] > 0.9


def test_s0_produces_no_intervals_and_acceptance_refuses_ruling_out():
    """S0 may not be used to rule anything out; that refusal must be explicit."""
    X, Y, viable = _data()
    m = S0Surrogate(_spec(tier="S0")).fit(X, Y, viable)
    Xt, Yt, vt = _data(n=100, seed=2)
    rep = run_acceptance(m, Xt[vt], Yt[vt], Y_train=Y[viable])
    assert "interval_coverage" not in rep.verdicts
    assert any("rule anything out" in n for n in rep.notes)


def test_s0_rejects_wrong_tier_spec():
    with pytest.raises(ValueError, match="requires tier 'S0'"):
        S0Surrogate(_spec(tier="S1"))


# =============================================================================
# S1 — the two-stage structure is the point
# =============================================================================

def test_s1_classifier_learns_the_viability_cliff():
    """Failed runs are training signal. Dropping them loses the boundary entirely."""
    X, Y, viable = _data(n=400)
    m = S1Surrogate(_spec()).fit(X, Y, viable)
    dead = np.array([[0.02, 0.5]])
    alive = np.array([[0.9, 0.5]])
    assert m.predict_batch(dead).viability[0] < 0.5
    assert m.predict_batch(alive).viability[0] > 0.5


def test_s1_regresses_only_on_viable_rows():
    """NaN targets on dead rows must be tolerated, not poison the regression."""
    X, Y, viable = _data(n=400)
    m = S1Surrogate(_spec()).fit(X, Y, viable)
    pred = m.predict_batch(np.array([[0.9, 0.1]]))
    assert np.all(np.isfinite(pred.values))
    assert abs(pred.values[0, 0] - (1.0 + 0.8 * 0.9 - 0.3 * 0.1)) < 0.15


def test_s1_conformal_intervals_achieve_nominal_coverage():
    """Coverage, not R2, is what licenses any exclusion claim."""
    X, Y, viable = _data(n=600, seed=3)
    m = S1Surrogate(_spec(), alpha=0.1, random_state=1).fit(X, Y, viable)
    Xt, Yt, vt = _data(n=400, seed=99)
    pred = m.predict_batch(Xt[vt])
    for j in range(2):
        cov = interval_coverage(Yt[vt][:, j], pred.lower[:, j], pred.upper[:, j], 0.9)
        # Split conformal guarantees >= 1-alpha marginally; allow finite-sample slack.
        assert cov["coverage"] >= 0.82, f"target {j} under-covered: {cov}"
        assert np.isfinite(cov["mean_width"])


def test_s1_needs_enough_viable_rows_to_split():
    """Refuse rather than silently produce an uncalibrated interval."""
    X, Y, viable = _data(n=10, with_failures=False)
    viable[:] = False
    viable[:3] = True
    with pytest.raises(ValueError, match="viable rows"):
        S1Surrogate(_spec()).fit(X, Y, viable)


def test_s1_conformal_quantile_is_reported_per_target():
    X, Y, viable = _data(n=300)
    m = S1Surrogate(_spec()).fit(X, Y, viable)
    q = m.conformal_quantile
    assert set(q) == {"plant_C", "NPP"}
    assert all(v >= 0 for v in q.values())


# =============================================================================
# The extrapolation gate
# =============================================================================

def test_hull_gate_refuses_points_far_from_training_data():
    """Calibration drives to the edges; the gate must refuse, not guess."""
    rng = np.random.default_rng(0)
    X = rng.uniform(0, 1, size=(200, 2))
    g = HullGate(k=5, quantile=0.99).fit(X)
    assert g.inside(np.array([[0.5, 0.5]]))[0]
    assert not g.inside(np.array([[9.0, 9.0]]))[0]


def test_hull_gate_catches_an_empty_diagonal_corner():
    """A per-dimension box test would PASS this point. That is the failure mode."""
    rng = np.random.default_rng(1)
    # Data on an anti-diagonal band: each coordinate spans [0,1], but the
    # (1,1) corner is empty.
    a = rng.uniform(0, 1, size=400)
    X = np.column_stack([a, 1.0 - a]) + rng.normal(0, 0.02, size=(400, 2))
    g = HullGate(k=5, quantile=0.99).fit(X)
    assert not g.inside(np.array([[1.0, 1.0]]))[0]


def test_hull_gate_survives_a_constant_column():
    """A zero-variance input must not explode every distance to infinity."""
    X = np.column_stack([np.linspace(0, 1, 50), np.full(50, 0.3)])
    g = HullGate().fit(X)
    assert np.isfinite(g.distance(np.array([[0.5, 0.3]]))[0])


def test_s1_flags_out_of_hull_queries():
    X, Y, viable = _data(n=300)
    m = S1Surrogate(_spec()).fit(X, Y, viable)
    pred = m.predict_batch(np.array([[0.5, 0.5], [50.0, 50.0]]))
    assert pred.in_hull[0]
    assert not pred.in_hull[1]


# =============================================================================
# Manifold respect
# =============================================================================

def test_manifold_respect_flags_unreachable_target_combinations():
    """Independent regressors emit pairs the model cannot produce (the R2 finding)."""
    t = np.linspace(0, 1, 300)
    Y_train = np.column_stack([t, 2 * t])          # a 1-D manifold in 2-D output
    on = np.column_stack([t[:50], 2 * t[:50]])
    off = np.column_stack([t[:50], 2 * t[:50] + 5.0])
    assert manifold_respect(Y_train, on)["on_manifold"] > 0.9
    assert manifold_respect(Y_train, off)["on_manifold"] < 0.1


# =============================================================================
# The `simulated` seam — the whole architectural point
# =============================================================================

def test_simulated_feeds_the_existing_cost_layer_unchanged():
    """Surrogate and physics must be scored by literally the same function."""
    from tools.cost_functions import compute_snapshot_cost

    X, Y, viable = _data(n=300)
    m = S1Surrogate(_spec()).fit(X, Y, viable)
    sim = m.simulated([0.8, 0.2])
    assert set(sim) == {"plant_C", "NPP"}
    assert all(isinstance(v, float) for v in sim.values())
    cost, errors = compute_snapshot_cost(sim, {"plant_C": 1.0, "NPP": 2.0})
    assert np.isfinite(cost)
    assert set(errors) == {"plant_C", "NPP"}


def test_band_reachable_is_more_permissive_than_in_band():
    """Ruling out must use the interval, not the point estimate (docs/41 2.1)."""
    X, Y, viable = _data(n=300)
    m = S1Surrogate(_spec(), alpha=0.05).fit(X, Y, viable)
    pred = m.predict_batch(np.array([[0.5, 0.5], [0.9, 0.1], [0.2, 0.9]]))
    assert np.all(pred.band_reachable() | ~pred.in_band())


# =============================================================================
# Persistence
# =============================================================================

def test_save_load_roundtrip_preserves_predictions(tmp_path):
    X, Y, viable = _data(n=300)
    m = S1Surrogate(_spec()).fit(X, Y, viable)
    d = m.save(tmp_path / "art")
    back = load(d)
    q = np.array([[0.4, 0.6]])
    assert np.allclose(m.predict_batch(q).values, back.predict_batch(q).values)
    assert back.spec.provenance.scoring_convention == "targets-yaml-v1"


def test_load_refuses_a_provenance_mismatch(tmp_path):
    """The scoring convention is the field that has already bitten this project:
    the leap-calendar fix changed how targets are reduced, so an artifact
    trained before it is scored against a DIFFERENT objective. Nothing about it
    looks wrong on load, which is why this has to be a gate."""
    X, Y, viable = _data(n=220, seed=40)
    d = S1Surrogate(_spec()).fit(X, Y, viable).save(tmp_path / "art")

    stale = Provenance(model="fates", scoring_convention="targets-yaml-v2")
    with pytest.raises(ValueError, match="provenance mismatch"):
        load(d, expect=stale)

    # non-strict downgrades to a warning rather than silence
    with pytest.warns(RuntimeWarning, match="provenance mismatch"):
        load(d, expect=stale, strict=False)

    # the matching convention loads clean
    ok = Provenance(model="fates", scoring_convention="targets-yaml-v1")
    assert load(d, expect=ok) is not None


def test_load_warns_when_provenance_is_unstamped(tmp_path):
    """An unstamped field is UNPROTECTED, not verified — say so rather than
    letting an empty stamp read as a clean check."""
    spec = SurrogateSpec(
        name="bare", use_mode="offline_search", tier="S1",
        input_names=("a", "b"), input_lower=(0.0, 0.0), input_upper=(1.0, 1.0),
        targets=(TargetSpec("plant_C"), TargetSpec("NPP")),
        provenance=Provenance(model="fates"))          # nothing else stamped
    X, Y, viable = _data(n=220, seed=41)
    d = S1Surrogate(spec).fit(X, Y, viable).save(tmp_path / "bare")
    with pytest.warns(RuntimeWarning, match="unstamped provenance"):
        load(d)


def test_load_without_expect_skips_the_comparison(tmp_path):
    """Correct for inspection; NOT correct before acting on the artifact."""
    X, Y, viable = _data(n=220, seed=42)
    d = S1Surrogate(_spec()).fit(X, Y, viable).save(tmp_path / "art")
    # The fixture spec is fully stamped, so this path is silent. A partially
    # stamped artifact still warns — see the test above.
    assert load(d) is not None


def test_load_refuses_artifact_spec_mismatch(tmp_path):
    """A spec edited after training must not silently mis-map columns."""
    X, Y, viable = _data(n=300)
    m = S1Surrogate(_spec()).fit(X, Y, viable)
    d = m.save(tmp_path / "art")
    bad = _spec()
    tampered = bad.to_dict()
    tampered["targets"] = tampered["targets"][:1]  # drop a target
    (d / "spec.json").write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="regressors, spec declares"):
        load(d)


# =============================================================================
# Acceptance battery + confirmation rate
# =============================================================================

def test_acceptance_battery_passes_on_a_learnable_problem():
    X, Y, viable = _data(n=600, seed=5)
    m = S1Surrogate(_spec(), alpha=0.1, random_state=2).fit(X, Y, viable)
    Xt, Yt, vt = _data(n=300, seed=6)
    rep = run_acceptance(m, Xt[vt], Yt[vt], Y_train=Y[viable], viable_test=vt[vt],
                         coverage_tolerance=0.08)
    assert rep.passed, rep.summary()
    assert "ranking_fidelity" in rep.verdicts
    assert "interval_coverage" in rep.verdicts
    assert "manifold_respect" in rep.verdicts


def test_acceptance_reports_out_of_hull_contamination():
    """Out-of-hull test rows are extrapolation; their errors are not in-hull evidence."""
    X, Y, viable = _data(n=300)
    m = S1Surrogate(_spec()).fit(X, Y, viable)
    Xt = np.vstack([np.array([[0.5, 0.5]]), np.array([[80.0, 80.0]])])
    Yt = np.array([[1.3, 2.1], [1.3, 2.1]])
    rep = run_acceptance(m, Xt, Yt, Y_train=Y[viable])
    assert rep.overall["in_hull_fraction"] < 1.0
    assert any("outside the training hull" in n for n in rep.notes)


def test_confirmation_rate_counts_only_interval_hits():
    X, Y, viable = _data(n=300)
    m = S1Surrogate(_spec()).fit(X, Y, viable)
    q = np.array([[0.7, 0.3], [0.4, 0.8]])
    pred = m.predict_batch(q)
    truth = [{"plant_C": float(pred.values[i, 0]), "NPP": float(pred.values[i, 1])}
             for i in range(2)]
    assert record_confirmation(pred, truth)["overall"] == 1.0
    way_off = [{"plant_C": 999.0, "NPP": -999.0} for _ in range(2)]
    assert record_confirmation(pred, way_off)["overall"] == 0.0


# =============================================================================
# Learner families — the model-class axis
# =============================================================================

# Keep the MLP small: this is a contract test, not a benchmark.
_MLP_KW = dict(hidden=(16, 16), n_models=2, epochs=80)


def _kw(name):
    return dict(_MLP_KW) if name == "mlp" else {}


# ---- ridge: the complexity baseline ----

def test_ridge_nails_a_linear_response():
    """On a genuinely linear problem the baseline should be excellent — that is
    what makes it a fair yardstick rather than a strawman."""
    X, Y, viable = _data(n=300, seed=31)          # y0 = 1 + 0.8a - 0.3b, linear
    m = S1Surrogate(_spec(), learner="ridge").fit(X, Y, viable)
    p = m.predict_batch(np.array([[0.9, 0.1]])).values[0, 0]
    assert abs(p - (1.0 + 0.8 * 0.9 - 0.3 * 0.1)) < 0.05


def test_ridge_loses_to_a_tree_on_a_cliff_which_is_the_point():
    """If the baseline could never lose it would prove nothing. On a step
    response the tree must beat it, which is how the bake-off shows complexity
    earning its place."""
    rng = np.random.default_rng(32)
    X = rng.uniform(0, 1, size=(400, 2))
    y = (X[:, 0] > 0.5).astype(float) * 2.0       # a pure step
    err = {}
    for name in ("ridge", "rf"):
        lr = make_learner(name).fit(X[:300], y[:300])
        err[name] = float(np.mean(np.abs(lr.predict(X[300:]) - y[300:])))
    assert err["rf"] < err["ridge"], err


def test_ridge_recovers_the_true_linear_sensitivity():
    """Coefficients on standardised inputs are directly comparable; y0's 'a'
    coefficient is ~2.7x 'b', so 'a' must dominate."""
    X, Y, viable = _data(n=300, seed=33)
    s = S0Surrogate(_spec(tier="S0"), learner="ridge").fit(X, Y, viable).sensitivity()
    assert s["plant_C"]["a"] > s["plant_C"]["b"]
    assert abs(sum(s["plant_C"].values()) - 1.0) < 1e-9        # normalised


def test_ridge_leverage_grows_away_from_the_data():
    """Native sigma is leverage — the textbook linear-model extrapolation
    diagnostic — so it must rise as a query leaves the training cloud."""
    rng = np.random.default_rng(34)
    X = rng.normal(0, 1, size=(200, 2))
    lr = make_learner("ridge").fit(X, X[:, 0] * 2.0)
    near = lr.predict_std(np.array([[0.0, 0.0]]))[0]
    far = lr.predict_std(np.array([[8.0, 8.0]]))[0]
    assert far > near


def test_ridge_survives_a_fit_split_too_small_to_cross_validate():
    """RidgeCV needs rows to cross-validate; the fallback must be the
    near-OLS alpha rather than an exception."""
    X = np.random.default_rng(35).uniform(0, 1, size=(4, 2))
    lr = make_learner("ridge").fit(X, np.array([1.0, 2.0, 3.0, 4.0]))
    assert np.all(np.isfinite(lr.predict(X)))


def test_recommend_always_names_the_complexity_baseline():
    """Without a linear baseline in the bake-off, a crowned `mlp` could be
    losing to a straight line at a thousandth of the cost."""
    for g in recommend_goals():
        assert any("ridge" in c for c in recommend(g)["caveats"]), g


@pytest.mark.parametrize("name", ["ridge", "rf", "gbm", "gp", "mlp"])
def test_every_learner_family_fits_and_predicts(name):
    """The tier must work with ANY family — that is the point of separating axes."""
    X, Y, viable = _data(n=200, seed=11)
    m = S1Surrogate(_spec(), learner=name, **_kw(name)).fit(X, Y, viable)
    pred = m.predict_batch(np.array([[0.8, 0.2]]))
    assert np.all(np.isfinite(pred.values))
    # all four should learn a smooth 2-input trend to within a loose tolerance
    assert abs(pred.values[0, 0] - (1.0 + 0.8 * 0.8 - 0.3 * 0.2)) < 0.3, name


@pytest.mark.parametrize("name,expect", [("ridge", True), ("rf", True),
                                         ("gbm", False), ("gp", True), ("mlp", True)])
def test_native_sigma_support_is_declared_honestly(name, expect):
    """`supports_std` drives normalised conformal, so it must not lie."""
    lr = make_learner(name, **_kw(name))
    assert lr.supports_std is expect
    X, Y, _ = _data(n=120, seed=12, with_failures=False)
    lr.fit(X, Y[:, 0])
    s = lr.predict_std(X[:5])
    assert (s is not None and np.all(np.isfinite(s))) if expect else (s is None)


def test_normalized_conformal_gives_varying_width_constant_only_without_sigma():
    """The upgrade over a single constant half-width: intervals track uncertainty."""
    X, Y, viable = _data(n=400, seed=13)
    q = np.array([[0.3, 0.3], [0.6, 0.6], [0.9, 0.1]])

    gp = S1Surrogate(_spec(), learner="gp").fit(X, Y, viable)
    assert gp.normalized
    w_gp = (gp.predict_batch(q).upper - gp.predict_batch(q).lower)[:, 0]
    assert np.ptp(w_gp) > 0, "normalised conformal should vary with location"

    gbm = S1Surrogate(_spec(), learner="gbm").fit(X, Y, viable)
    assert not gbm.normalized
    w_gbm = (gbm.predict_batch(q).upper - gbm.predict_batch(q).lower)[:, 0]
    assert np.allclose(w_gbm, w_gbm[0]), "no sigma -> one constant width"


@pytest.mark.parametrize("name", ["ridge", "rf", "gp", "mlp"])
def test_coverage_holds_across_families(name):
    """Conformal is family-agnostic; honest intervals must not depend on the learner."""
    X, Y, viable = _data(n=500, seed=14)
    m = S1Surrogate(_spec(), learner=name, alpha=0.1, **_kw(name)).fit(X, Y, viable)
    Xt, Yt, vt = _data(n=300, seed=15)
    pred = m.predict_batch(Xt[vt])
    cov = interval_coverage(Yt[vt][:, 0], pred.lower[:, 0], pred.upper[:, 0], 0.9)
    assert cov["coverage"] >= 0.80, f"{name} under-covered: {cov}"


def test_gp_exposes_ard_sensitivity_and_rf_exposes_importance():
    """Two families give per-input sensitivity by different mechanisms."""
    X, Y, viable = _data(n=200, seed=16)
    for name in ("rf", "gp"):
        s = S0Surrogate(_spec(tier="S0"), learner=name).fit(X, Y, viable).sensitivity()
        assert set(s["plant_C"]) == {"a", "b"}
        # y0 = 1 + 0.8a - 0.3b, so 'a' should dominate for plant_C
        assert s["plant_C"]["a"] > s["plant_C"]["b"], name


def test_a_fresh_learner_is_built_per_target():
    """One shared instance would refit over itself, so target 0 would inherit
    target 1's fit. Assert BOTH that the objects are distinct and that each
    tracks its OWN function — the second is what actually matters."""
    X, Y, viable = _data(n=200, seed=17)
    m = S1Surrogate(_spec(), learner=RFLearner(n_estimators=50)).fit(X, Y, viable)
    assert m._models[0] is not m._models[1]
    a, b = 0.9, 0.1
    p = m.predict_batch(np.array([[a, b]])).values[0]
    true_plant_c = 1.0 + 0.8 * a - 0.3 * b        # 1.690
    true_npp = 2.0 + 0.5 * a * b                  # 2.045
    assert abs(p[0] - true_plant_c) < 0.15, f"plant_C {p[0]} vs {true_plant_c}"
    assert abs(p[1] - true_npp) < 0.15, f"NPP {p[1]} vs {true_npp}"


def test_make_learner_rejects_unknown_name():
    with pytest.raises(ValueError, match="unknown learner"):
        make_learner("randomforest")


# =============================================================================
# Knowledge-guided loss — the PGNN hook
# =============================================================================

def test_knowledge_guided_monotonicity_changes_the_fitted_response():
    """A monotone penalty must actually bend the model, not just be accepted.

    Fit deliberately noisy data whose true trend is DEcreasing in x0, then
    demand an INcreasing response. A model that ignored the penalty would keep
    the decreasing fit; a physics-guided one is pulled toward flat-or-rising.
    """
    rng = np.random.default_rng(3)
    X = rng.uniform(0, 1, size=(220, 2))
    y = -1.5 * X[:, 0] + 0.1 * X[:, 1] + rng.normal(0, 0.05, size=220)

    plain = make_learner("mlp", **_MLP_KW).fit(X, y)
    guided = make_learner(
        "mlp", kg_loss=KnowledgeGuidedLoss(monotone={0: +1}, weight=50.0),
        **_MLP_KW).fit(X, y)

    grid = np.column_stack([np.linspace(0.05, 0.95, 25), np.full(25, 0.5)])
    slope_plain = np.polyfit(grid[:, 0], plain.predict(grid), 1)[0]
    slope_guided = np.polyfit(grid[:, 0], guided.predict(grid), 1)[0]
    assert slope_plain < 0, "unguided fit should follow the decreasing data"
    assert slope_guided > slope_plain, "the monotone penalty should raise the slope"


def test_knowledge_guided_bounds_penalty_pulls_predictions_into_range():
    rng = np.random.default_rng(4)
    X = rng.uniform(0, 1, size=(200, 2))
    y = 5.0 + 2.0 * X[:, 0]                      # true range well above the cap
    guided = make_learner(
        "mlp", kg_loss=KnowledgeGuidedLoss(bounds=(None, 3.0), weight=50.0),
        **_MLP_KW).fit(X, y)
    plain = make_learner("mlp", **_MLP_KW).fit(X, y)
    assert guided.predict(X).mean() < plain.predict(X).mean()


def test_kg_loss_is_inactive_when_nothing_declared():
    assert not KnowledgeGuidedLoss().active
    assert KnowledgeGuidedLoss(monotone={0: 1}).active
    assert KnowledgeGuidedLoss(bounds=(0.0, None)).active


# =============================================================================
# Bake-off
# =============================================================================

# =============================================================================
# The classifier is the caller's choice too (the asymmetry, fixed)
# =============================================================================

@pytest.mark.parametrize("clf", ["rf", "gbm", "logistic", "gp"])
def test_viability_classifier_is_selectable(clf):
    """S1 has TWO halves. Hard-coding either makes a bake-off compare something
    other than what it appears to compare — and the alive/dead boundary is the
    cliff, the last place to bury an invisible choice."""
    X, Y, viable = _data(n=250, seed=21)
    m = S1Surrogate(_spec(), classifier=clf).fit(X, Y, viable)
    assert m.predict_batch(np.array([[0.02, 0.5]])).viability[0] < 0.5
    assert m.predict_batch(np.array([[0.9, 0.5]])).viability[0] > 0.5


def test_torch_classifier_honours_the_sklearn_surface():
    """It must drop into S1 with no special-casing, so the contract matters:
    classes_, an (n, 2) predict_proba whose rows sum to 1, and predict."""
    rng = np.random.default_rng(0)
    X = rng.uniform(0, 1, size=(250, 2))
    y = (X[:, 0] >= 0.35).astype(int)
    c = make_classifier("mlp", hidden=(24, 24), n_models=2, epochs=150).fit(X, y)
    p = c.predict_proba(np.array([[0.1, 0.5], [0.9, 0.5]]))
    assert list(c.classes_) == [0, 1]
    assert p.shape == (2, 2) and np.allclose(p.sum(axis=1), 1.0)
    assert p[0, 1] < 0.5 < p[1, 1]                       # learns the cliff
    assert list(c.predict(np.array([[0.1, 0.5], [0.9, 0.5]]))) == [0, 1]


def test_torch_classifier_survives_a_single_class_fit():
    """Degenerate but reachable; it must not train a net that cannot learn."""
    X = np.random.default_rng(1).uniform(0, 1, size=(30, 2))
    c = make_classifier("mlp", n_models=1, epochs=5).fit(X, np.ones(30, dtype=int))
    p = c.predict_proba(X[:3])
    assert p.shape == (3, 2) and np.allclose(p.sum(axis=1), 1.0)


def test_knowledge_guided_viability_bends_the_cliff():
    """The reason the torch classifier exists: domain knowledge applied to the
    alive/dead boundary itself, which is where this project's difficulty lives.

    Train on data whose survival DEcreases with x0, then assert survival must
    INcrease with x0. The guided model's boundary must move against the data."""
    rng = np.random.default_rng(7)
    X = rng.uniform(0, 1, size=(300, 2))
    y = (X[:, 0] <= 0.5).astype(int)              # survival falls with x0
    kw = dict(hidden=(24, 24), n_models=2, epochs=200)

    plain = make_classifier("mlp", **kw).fit(X, y)
    guided = make_classifier(
        "mlp", kg_loss=KnowledgeGuidedLoss(monotone={0: +1}, weight=20.0),
        **kw).fit(X, y)

    grid = np.column_stack([np.linspace(0.05, 0.95, 20), np.full(20, 0.5)])
    slope = lambda c: np.polyfit(grid[:, 0], c.predict_proba(grid)[:, 1], 1)[0]
    assert slope(plain) < 0, "unguided should follow the decreasing data"
    assert slope(guided) > slope(plain), "the monotone penalty should raise it"


def test_bounds_penalty_is_ignored_on_a_classifier_because_sigmoid_is_structural():
    """A probability is already in [0, 1] by construction, so a soft penalty for
    it would be strictly worse than free.

    Asserted the sharp way: a bounds-only kg_loss must leave the fit BITWISE
    unchanged versus no kg_loss at all, same seed. That proves it is genuinely
    ignored rather than merely having a small effect."""
    rng = np.random.default_rng(8)
    X = rng.uniform(0, 1, size=(150, 2))
    y = (X[:, 0] >= 0.5).astype(int)
    kw = dict(hidden=(16, 16), n_models=1, epochs=60, random_state=3)

    guided = make_classifier(
        "mlp", kg_loss=KnowledgeGuidedLoss(bounds=(0.2, 0.8), weight=10.0), **kw
    ).fit(X, y)
    plain = make_classifier("mlp", **kw).fit(X, y)

    pg, pp = guided.predict_proba(X)[:, 1], plain.predict_proba(X)[:, 1]
    assert np.allclose(pg, pp), "a bounds-only kg_loss must be a no-op here"
    assert np.all((pg >= 0.0) & (pg <= 1.0))


def test_torch_classifier_selectable_in_s1_and_survives_roundtrip(tmp_path):
    X, Y, viable = _data(n=220, seed=26)
    m = S1Surrogate(_spec(), classifier="mlp",
                    classifier_kw=dict(hidden=(16, 16), n_models=2, epochs=120)
                    ).fit(X, Y, viable)
    assert m.predict_batch(np.array([[0.02, 0.5]])).viability[0] < 0.5
    back = load(m.save(tmp_path / "art"))
    assert back.classifier == "mlp"
    q = np.array([[0.4, 0.6]])
    assert np.allclose(m.predict_batch(q).viability, back.predict_batch(q).viability)


def test_classifier_choice_actually_changes_the_boundary():
    """Different families must give genuinely different probabilities, or the
    knob is decorative."""
    X, Y, viable = _data(n=250, seed=22)
    q = np.array([[0.16, 0.5], [0.14, 0.5]])   # straddling the cliff at a=0.15
    p_rf = S1Surrogate(_spec(), classifier="rf").fit(X, Y, viable).predict_batch(q).viability
    p_lr = S1Surrogate(_spec(), classifier="logistic").fit(X, Y, viable).predict_batch(q).viability
    assert not np.allclose(p_rf, p_lr)


def test_classifier_accepts_a_ready_estimator_and_rejects_nonsense():
    from sklearn.tree import DecisionTreeClassifier
    X, Y, viable = _data(n=200, seed=23)
    m = S1Surrogate(_spec(), classifier=DecisionTreeClassifier(max_depth=4)
                    ).fit(X, Y, viable)
    assert np.isfinite(m.predict_batch(np.array([[0.5, 0.5]])).viability[0])
    with pytest.raises(ValueError, match="unknown classifier"):
        make_classifier("randomforest")
    with pytest.raises(TypeError, match="cannot resolve classifier"):
        make_classifier(42)


def test_classifier_choice_survives_save_load(tmp_path):
    X, Y, viable = _data(n=220, seed=24)
    m = S1Surrogate(_spec(), classifier="logistic").fit(X, Y, viable)
    back = load(m.save(tmp_path / "art"))
    assert back.classifier == "logistic"
    q = np.array([[0.3, 0.7]])
    assert np.allclose(m.predict_batch(q).viability, back.predict_batch(q).viability)


# =============================================================================
# Guidance — for a user who does not want to choose blind
# =============================================================================

def test_recommend_covers_every_goal_and_names_real_families():
    goals = recommend_goals()
    assert set(goals) >= {"screen", "sensitivity", "rule_out", "search",
                          "physics_constrained"}
    for g in goals:
        rec = recommend(g)
        assert rec["regressors"] and rec["classifiers"]
        for name, why in rec["regressors"]:
            assert name in LEARNERS and why
        for name, why in rec["classifiers"]:
            assert name in CLASSIFIERS and why
        # It must always say the priors are not the last word.
        assert "compare_learners" in rec["decide_empirically"]
        assert "goal:" in explain_recommendation(rec)


def test_rule_out_never_recommends_a_family_without_a_native_sigma():
    """Ruling out needs normalised intervals; gbm gives one constant width."""
    rec = recommend("rule_out")
    assert "gbm" not in [n for n, _ in rec["regressors"]]
    assert any("gbm" in c for c in rec["caveats"])


def test_physics_constrained_recommends_only_the_family_that_takes_a_loss():
    rec = recommend("physics_constrained")
    assert [n for n, _ in rec["regressors"]] == ["mlp"]
    assert any("not guarantees" in c or "structural" in c for c in rec["caveats"])


def test_recommend_adjusts_for_dataset_size():
    """A GP on 10k rows and an MLP on 80 rows are both bad ideas, for
    opposite reasons; the guidance should say so rather than stay generic."""
    big = recommend("rule_out", n_train=10_000)
    assert [n for n, _ in big["regressors"]][-1] == "gp"      # demoted to last
    assert any("subsample" in c for c in big["caveats"])
    small = recommend("search", n_train=80)
    assert any("thin for a neural ensemble" in w for _, w in small["regressors"])
    assert any("coverage will be coarse" in c for c in small["caveats"])


def test_structure_advice_can_introduce_a_family_not_merely_reorder():
    """`search` defaults to gp+mlp, both smooth. Saying "cliffs" must SURFACE a
    tree family, not silently change nothing — which would look considered and
    be useless."""
    base = [n for n, _ in recommend("search")["regressors"]]
    assert "rf" not in base                       # premise of the test
    cliff = recommend("search", structure="cliff")["regressors"]
    assert cliff[0][0] in ("rf", "gbm")
    assert any("ADDED for cliff" in why for _, why in cliff)
    smooth = [n for n, _ in recommend("search", structure="smooth")["regressors"]]
    assert smooth[0] in ("gp", "mlp")


def test_a_hard_goal_constraint_outranks_structure_advice():
    """No amount of "but it has cliffs" may put a tree where only a custom loss
    will do."""
    rec = recommend("physics_constrained", structure="cliff")
    assert [n for n, _ in rec["regressors"]] == ["mlp"]
    assert any("suppressed" in c for c in rec["caveats"])


def test_a_barred_family_is_not_reintroduced_by_structure_advice():
    """gbm suits a cliff but cannot rule anything out; the bar must hold, and
    the reason must be stated rather than the family silently vanishing."""
    rec = recommend("rule_out", structure="cliff")
    assert "gbm" not in [n for n, _ in rec["regressors"]]
    assert any("barred for this goal" in c for c in rec["caveats"])


def test_recommend_rejects_an_unknown_goal():
    with pytest.raises(ValueError, match="unknown goal"):
        recommend("make_it_good")


def test_bakeoff_can_cross_learners_with_classifiers():
    """The honest comparison varies BOTH halves."""
    X, Y, viable = _data(n=240, seed=25)
    cmp = compare_learners(_spec(), X, Y, viable, learners=("rf", "gbm"),
                           classifiers=("rf", "logistic"), coverage_tolerance=0.15)
    assert set(cmp["results"]) == {"rf/rf", "rf/logistic", "gbm/rf", "gbm/logistic"}
    for r in cmp["results"].values():
        assert r["learner"] in ("rf", "gbm") and r["classifier"] in ("rf", "logistic")
    assert "cliff" in bakeoff_summary(cmp)


def test_rank_key_depends_on_the_use_being_served():
    """A single key cannot serve every use. Screening wants the best ranker;
    ruling out wants the TIGHTEST honest interval, because a band wide enough to
    overlap everything excludes nothing."""
    results = {
        # a strong ranker with a very wide interval — great to screen with,
        # useless to rule out with
        "wide": dict(mean_top_k_recall=0.90, mean_spearman=0.99,
                     mean_coverage=0.99, mean_width=5.0,
                     normalized_intervals=True, passed=True),
        # a weaker ranker with a tight, still-honest interval
        "tight": dict(mean_top_k_recall=0.60, mean_spearman=0.95,
                      mean_coverage=0.96, mean_width=0.2,
                      normalized_intervals=True, passed=True),
    }
    assert rank_results(results, "screen", alpha=0.05)[0] == "wide"
    assert rank_results(results, "rule_out", alpha=0.05)[0] == "tight"


def test_rule_out_ranking_gates_on_coverage_before_anything_else():
    """Miss coverage and nothing may be excluded, however tight the band."""
    results = {
        "tight_but_dishonest": dict(mean_top_k_recall=0.9, mean_spearman=0.99,
                                    mean_coverage=0.60, mean_width=0.05,
                                    normalized_intervals=True, passed=False),
        "honest": dict(mean_top_k_recall=0.5, mean_spearman=0.9,
                       mean_coverage=0.96, mean_width=1.0,
                       normalized_intervals=True, passed=True),
    }
    assert rank_results(results, "rule_out", alpha=0.05)[0] == "honest"


def test_rule_out_demotes_a_constant_width_family():
    """One width everywhere cannot localise where the reachable set nears the
    target box, even if it is narrow on average."""
    results = {
        "constant": dict(mean_top_k_recall=0.7, mean_spearman=0.97,
                         mean_coverage=0.97, mean_width=0.3,
                         normalized_intervals=False, passed=True),
        "normalized": dict(mean_top_k_recall=0.7, mean_spearman=0.97,
                           mean_coverage=0.97, mean_width=0.4,
                           normalized_intervals=True, passed=True),
    }
    assert rank_results(results, "rule_out", alpha=0.05)[0] == "normalized"


def test_sensitivity_ranking_prefers_response_shape_over_the_top_k_head():
    results = {
        "shape": dict(mean_top_k_recall=0.4, mean_spearman=0.99,
                      mean_coverage=0.95, mean_width=1.0,
                      normalized_intervals=True, passed=True),
        "head": dict(mean_top_k_recall=0.9, mean_spearman=0.80,
                     mean_coverage=0.95, mean_width=1.0,
                     normalized_intervals=True, passed=True),
    }
    assert rank_results(results, "sensitivity", alpha=0.05)[0] == "shape"
    assert rank_results(results, "screen", alpha=0.05)[0] == "head"


def test_failed_fits_sort_last_under_every_scheme():
    results = {"good": dict(mean_top_k_recall=0.5, mean_spearman=0.9,
                            mean_coverage=0.95, mean_width=1.0,
                            normalized_intervals=True, passed=True),
               "broken": {"error": "ValueError: nope"}}
    for scheme in RANK_KEYS:
        assert rank_results(results, scheme, alpha=0.05)[-1] == "broken", scheme


def test_rank_results_rejects_an_unknown_scheme():
    with pytest.raises(ValueError, match="unknown rank_for"):
        rank_results({}, "whatever")


def test_compare_learners_honours_rank_for():
    X, Y, viable = _data(n=240, seed=27)
    cmp = compare_learners(_spec(), X, Y, viable, learners=("ridge", "rf"),
                           rank_for="rule_out", coverage_tolerance=0.15)
    assert cmp["rank_for"] == "rule_out"
    assert "ranked for: rule_out" in bakeoff_summary(cmp)


def test_compare_learners_ranks_families_and_records_failures():
    X, Y, viable = _data(n=260, seed=18)
    cmp = compare_learners(
        _spec(), X, Y, viable,
        learners=("rf", "gbm", "gp", "mlp", "nosuchlearner"),
        learner_kw={"mlp": _MLP_KW}, coverage_tolerance=0.1)
    assert cmp["best"] in {"rf", "gbm", "gp", "mlp"}
    # A failing family is RECORDED, not silently dropped — a missing row would
    # read as "not tried".
    assert "error" in cmp["results"]["nosuchlearner"]
    assert cmp["ranking"][-1] == "nosuchlearner"
    assert "learner" in bakeoff_summary(cmp)
