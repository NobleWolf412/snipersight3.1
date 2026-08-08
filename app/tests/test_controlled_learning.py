import sqlite3

import pytest

from engine import learning


REPORT = {"windows": [{"train": [1, 10], "forward": [11, 20]}],
          "by_regime": {"TREND": {"n": 20}},
          "by_horizon": {"intraday": {"n": 20}},
          "forward_metrics": {"mean_r": 0.1}}


def test_learning_refuses_non_point_in_time_data_and_random_splits():
    con = sqlite3.connect(":memory:")
    with pytest.raises(learning.LearningRejected, match="point-in-time"):
        learning.register_challenger(
            con, model_id="m1", strategy="PULLBACK", horizon="intraday",
            algorithm_version="algo-v2", dataset_version="data-v1",
            point_in_time=False)
    learning.register_challenger(
        con, model_id="m1", strategy="PULLBACK", horizon="intraday",
        algorithm_version="algo-v2", dataset_version="data-v1",
        point_in_time=True)
    with pytest.raises(learning.LearningRejected, match="chronological"):
        learning.record_walk_forward(con, "m1", REPORT, split_method="RANDOM")


def test_promotion_needs_evidence_human_and_exact_new_algorithm_version():
    con = sqlite3.connect(":memory:")
    learning.register_challenger(
        con, model_id="m1", strategy="PULLBACK", horizon="intraday",
        algorithm_version="algo-v2", dataset_version="data-v1",
        point_in_time=True)
    with pytest.raises(learning.LearningRejected, match="evidence"):
        learning.propose(con, proposal_id="p1", model_id="m1",
                         target_stage="SHADOW", expected_algorithm_version="algo-v2")
    learning.record_walk_forward(con, "m1", REPORT)
    learning.propose(con, proposal_id="p1", model_id="m1",
                     target_stage="SHADOW", expected_algorithm_version="algo-v2")
    with pytest.raises(learning.LearningRejected, match="human"):
        learning.approve(con, "p1", human_approver="", new_algorithm_version="algo-v2")
    with pytest.raises(learning.LearningRejected, match="version"):
        learning.approve(con, "p1", human_approver="operator",
                         new_algorithm_version="algo-v3")
    result = learning.approve(con, "p1", human_approver="operator",
                              new_algorithm_version="algo-v2")
    assert result["stage"] == "SHADOW"
    assert result["does_not_enable_live"] is True
