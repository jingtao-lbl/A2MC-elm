"""Unit tests for WorkflowStateOffline.resolve_next_action (docs/38 §4.3, T1).

Pure-state resolver: given a state, what is the next workflow action? Covers each runnable
phase, the converged short-circuit, and the four Phase-6 fork branches.
"""
from tools.workflow_state_offline import WorkflowStateOffline


def _st(**position):
    st = WorkflowStateOffline(calibration_round=1)  # blank in-memory state (no save)
    if position:
        st.set_position(**position)
    return st


def test_runnable_phases_return_run_phase():
    for ph in ("design", "exploration", "screening", "diagnosis", "hypothesis", "testing"):
        na = _st(current_phase=ph).resolve_next_action()
        assert na.kind == "run_phase" and na.phase == ph, (ph, na)


def test_converged_short_circuits_to_done():
    na = _st(current_phase="testing", converged=True).resolve_next_action()
    assert na.kind == "done" and na.phase == "converged", na


def test_phase6_without_decision_is_a_gate():
    na = _st(current_phase="refinement").resolve_next_action()
    assert na.kind == "gate" and na.phase == "refinement", na


def test_phase6_converge_is_done():
    st = _st(current_phase="refinement")
    st.set_phase6_decision("converge")
    na = st.resolve_next_action()
    assert na.kind == "done", na


def test_phase6_rethink_routes_to_diagnosis():
    st = _st(current_phase="refinement")
    st.set_phase6_decision("rethink_6to3", binding_target="PFT10_leaf",
                           next_targeted_experiment="vmax_p sweep")
    na = st.resolve_next_action()
    assert na.kind == "run_phase" and na.phase == "diagnosis", na


def test_phase6_redesign_routes_to_design():
    st = _st(current_phase="refinement")
    st.set_phase6_decision("redesign_6to0", binding_target="PFT10_leaf")
    na = st.resolve_next_action()
    assert na.kind == "run_phase" and na.phase == "design", na


def test_phase6_stop_model_dev_is_a_human_gate():
    st = _st(current_phase="refinement")
    st.set_phase6_decision("stop_model_dev", binding_target="PFT10_leaf",
                           next_targeted_experiment="NONE",
                           exhaustion_justification="all in-range experiments tried")
    na = st.resolve_next_action()
    assert na.kind == "gate" and na.phase == "refinement", na


def test_converged_beats_a_pending_phase6_gate():
    st = _st(current_phase="refinement", converged=True)
    na = st.resolve_next_action()
    assert na.kind == "done", na


def test_driver_walkthrough_phase0_to_converged():
    """Simulate the calibration-goal driver stepping resolve_next_action through a full loop:
    design→…→refinement (gate) → a rethink cycle back to diagnosis → converge (done)."""
    st = WorkflowStateOffline(calibration_round=1)
    # phases 0-5 each resolve to run themselves
    for ph in ("design", "exploration", "screening", "diagnosis", "hypothesis", "testing"):
        st.set_position(current_phase=ph)
        assert st.resolve_next_action() == ("run_phase", ph, st.resolve_next_action().detail)
    # phase 6 with no decision → gate (the driver pauses for the human)
    st.set_position(current_phase="refinement")
    assert st.resolve_next_action().kind == "gate"
    # decision = rethink → route back to diagnosis; the driver then advances + clears the decision
    st.set_phase6_decision("rethink_6to3", binding_target="PFT10_leaf",
                           next_targeted_experiment="vmax_p sweep")
    assert st.resolve_next_action().phase == "diagnosis"
    st.set_position(current_phase="diagnosis", experiment_count=1)
    st.data["phase6_decision"] = None
    assert st.resolve_next_action() == ("run_phase", "diagnosis", st.resolve_next_action().detail)
    # second refinement → converge → done
    st.set_position(current_phase="refinement")
    st.set_phase6_decision("converge")
    assert st.resolve_next_action().kind == "done"
