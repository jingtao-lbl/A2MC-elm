"""`generate_calibration_rounds.merge_round` — the derived/authored contract.

Before 2026-08-02 `--write` replaced the round block wholesale, so re-running it on a completed
round destroyed the agent-written `outcome`, the human `rationale`, and the `<model>_source.patches`
note recording a round's model-build dependency. These lock the merge contract:

  * DERIVED fields (config-owned) are refreshed
  * AUTHORED fields (human/agent-owned) are never touched on an existing round
  * a placeholder ('TODO', '', None, []) never overwrites a real value
  * re-running against an unchanged config is a no-op
"""
from tools.generate_calibration_rounds import merge_round


def _existing():
    """A completed round, as it looks after the agent has written its Phase-6 outcome."""
    return {
        "parameters": 169,
        "ensembles": 5100,
        "paths": {"param_list": "…/para169.csv", "param_dir": "${A2MC_OUTPUT_ROOT}/para169_Morris"},
        "fates_source": {"milestone": "api-43-1", "fates_commit": "57016c44",
                         "patches": ["A2MCapi43port17 (#17): per-PFT gddthresh_c"]},
        "overrides": {"fates_cnp_prescribed_puptake": 0.0},
        "rationale": "First api-43-1 round for this site.",
        "changes_from_previous": ["New api-43-1 lineage."],
        "outcome": "R1 completed 5100/5100; PFT12 fineroot under-predicted.",
        "status": "completed",
        "completed_date": "2026-08-02",
        "key_cases": {"best": "En2939"},
        "provenance": {"key_logs": ["20260719a"]},
    }


def _generated(**over):
    """What the generator emits from a live config (TODOs where detection failed)."""
    g = {
        "parameters": 169,
        "ensembles": 5100,
        "paths": {"param_list": "…/para169.csv", "param_dir": "${A2MC_OUTPUT_ROOT}/para169_Morris"},
        "fates_source": {"milestone": "TODO", "fates_commit": "TODO", "patches": []},
        "overrides": {},
        "rationale": "TODO: why this round is designed as it is.",
        "changes_from_previous": ["TODO: what changed vs round 0"],
        "outcome": None,
        "status": "planned",
    }
    g.update(over)
    return g


def test_agent_written_outcome_survives():
    """The regression that motivated this: `outcome` is written by the agent at the Phase-6
    gate and no config can reproduce it."""
    m = merge_round(_existing(), _generated())
    assert m["outcome"] == "R1 completed 5100/5100; PFT12 fineroot under-predicted."
    assert m["status"] == "completed"
    assert m["completed_date"] == "2026-08-02"


def test_human_narrative_and_patches_survive():
    m = merge_round(_existing(), _generated())
    assert m["rationale"] == "First api-43-1 round for this site."
    assert m["changes_from_previous"] == ["New api-43-1 lineage."]
    # the model-build dependency a round needs — no config exports it
    assert m["fates_source"]["patches"] == ["A2MCapi43port17 (#17): per-PFT gddthresh_c"]
    assert m["key_cases"] == {"best": "En2939"}
    assert m["provenance"] == {"key_logs": ["20260719a"]}
    assert m["overrides"] == {"fates_cnp_prescribed_puptake": 0.0}


def test_placeholder_never_downgrades_a_real_value():
    """Running --write from a machine where the model checkout is unreachable must not reset
    the recorded milestone/commits to TODO."""
    m = merge_round(_existing(), _generated())
    assert m["fates_source"]["milestone"] == "api-43-1"
    assert m["fates_source"]["fates_commit"] == "57016c44"


def test_derived_fields_are_refreshed_and_reported():
    """A genuine config change DOES win — the config is the runtime authority — and the
    overwrite is reported so drift is visible rather than silent."""
    gen = _generated(parameters=170,
                     paths={"param_list": "…/para170.csv", "param_dir": "${A2MC_OUTPUT_ROOT}/x"})
    changes = []
    m = merge_round(_existing(), gen, changes)
    assert m["parameters"] == 170
    assert m["paths"]["param_list"] == "…/para170.csv"
    reported = {c[0] for c in changes}
    assert "parameters" in reported and "paths.param_list" in reported
    assert m["outcome"] == "R1 completed 5100/5100; PFT12 fineroot under-predicted."  # still safe


def test_unchanged_config_is_a_noop():
    existing = _existing()
    changes = []
    m = merge_round(existing, _generated(), changes)
    assert m == existing, "re-running against an unchanged config must not modify the record"
    assert changes == []


def test_new_round_takes_the_generated_scaffold():
    """With no existing record the generator's TODO scaffolding is what you want."""
    m = merge_round(None, _generated())
    assert m["status"] == "planned"
    assert m["rationale"].startswith("TODO")
