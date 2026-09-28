import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage010_failure_diagnostics.py"
    assert path.exists(), "failure diagnostics implementation missing"
    spec = importlib.util.spec_from_file_location("failure_diagnostics_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def tables():
    events = pd.DataFrame({"event_id": ["a", "b", "c", "d"], "candidate_index": [1, 2, 3, 4],
        "decision_date": ["2021-06-02"] * 4, "product_vt_symbol": ["rb.SHFE"] * 4,
        "label_status": ["verified"] * 3 + ["censored"],
        "return_marginal": [-0.2, 0.3, -0.2, np.nan],
        "drawdown_marginal": [-0.1, 0.2, -0.1, np.nan]})
    pred = events.loc[:, ["event_id", "candidate_index", "decision_date", "product_vt_symbol"]].copy()
    pred = pred.assign(cutoff="2021-06-01", status="predicted", skip=[True, True, False, True],
                       return_marginal=[-0.1, -0.1, 0.1, -0.1], drawdown_marginal=-0.1)
    meta = {"2021-06-01": {"status": "trained", "heads": {
        "return_marginal": {"mean": 0.05, "std": 0.2},
        "drawdown_marginal": {"mean": -0.01, "std": 0.1}}}}
    return events, pred, meta


def test_skill_uses_supplied_past_baseline_not_evaluation_mean():
    result = module().regression_metrics([1, 3], [1, 1], [0, 2], [1, 1])
    assert result["model_mse"] == 2
    assert result["baseline_mse"] == 1
    assert result["mse_skill"] == -1
    assert result["standardized_mse_skill"] == -1


def test_zero_baseline_loss_or_constant_training_scale_is_undefined():
    result = module().regression_metrics([2, 2], [2, 2], [2, 2], [0, 0])
    assert result["mse_skill"] is None
    assert result["standardized_count"] == 0
    assert result["standardized_mse_skill"] is None
    assert result["pearson"] is None


@pytest.mark.parametrize("values", [[np.nan], [np.inf]])
def test_nonfinite_scoring_is_rejected(values):
    with pytest.raises(RuntimeError, match="scoring"):
        module().regression_metrics(values, [0], [0], [1])


def test_join_preserves_censored_and_uses_month_metadata_means():
    events, pred, meta = tables()
    joined = module().join_predictions(events, pred, meta)
    assert len(joined) == 4
    assert joined.evaluable.tolist() == [True, True, True, False]
    assert joined.baseline_return_marginal.tolist() == [0.05] * 4
    assert pd.isna(joined.loc[3, "return_marginal"])
    assert joined.pred_return_marginal.tolist() == [-0.1, -0.1, 0.1, -0.1]


def test_action_confusion_has_correct_sign_and_no_censored_zero_imputation():
    events, pred, meta = tables()
    m = module()
    row = m.action_metrics(m.join_predictions(events, pred, meta))
    assert row["evaluated_count"] == 3
    assert row["skip_count"] == 2
    assert (row["true_positive"], row["false_positive"], row["false_negative"], row["true_negative"]) == (1, 1, 1, 0)
    assert row["skip_precision"] == 0.5
    assert row["skipped_positive_return_count"] == 1


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "date", "cutoff", "action", "censored_value"])
def test_join_rejects_inconsistent_inventory_and_semantics(mutation):
    events, pred, meta = tables()
    if mutation == "missing":
        pred = pred.iloc[:-1]
    elif mutation == "duplicate":
        pred.loc[1, "event_id"] = "a"
    elif mutation == "date":
        pred.loc[1, "decision_date"] = "2021-05-02"
    elif mutation == "cutoff":
        pred.loc[1, "cutoff"] = "2021-05-01"
    elif mutation == "action":
        pred.loc[1, "skip"] = False
    else:
        events.loc[3, "return_marginal"] = 0
    with pytest.raises(RuntimeError):
        module().join_predictions(events, pred, meta)


def test_untrained_scores_stay_empty_and_excluded():
    events, pred, meta = tables()
    pred["status"] = "untrained"
    pred["skip"] = False
    pred[["return_marginal", "drawdown_marginal"]] = np.nan
    meta["2021-06-01"] = {"status": "untrained", "heads": {}}
    m = module()
    joined = m.join_predictions(events, pred, meta)
    assert not joined.evaluable.any()
    assert m.action_metrics(joined)["skip_precision"] is None


def test_path_matching_ignores_shifted_event_indices_without_attaching_a_labels():
    m = module()
    a = pd.DataFrame({key: ["x", "y"] for key in m.MATCH_KEYS})
    a = a.assign(event_id=["A1", "A2"], candidate_index=[1, 2], f=[1.0, 2.0], skip=[False, False])
    c = a.copy()
    c["event_id"] = ["C8", "C9"]
    c["candidate_index"] = [8, 9]
    c.loc[1, "f"] = 3
    c.loc[1, "skip"] = True
    pairs, summary = m.path_drift(a, c, ["f"])
    assert summary["common_count"] == 2
    assert summary["action_changed_count"] == 1
    assert summary["feature_changed_counts"] == {"f": 1}
    assert pairs.delta_f.tolist() == [0, 1]
    with pytest.raises(RuntimeError, match="duplicate"):
        m.path_drift(pd.concat([a, a.iloc[:1]]), c, ["f"])


def test_zero_common_path_inventory_is_not_a_matching_success():
    m = module()
    a = pd.DataFrame({key: ["x"] for key in m.MATCH_KEYS}).assign(f=1.0, skip=False, event_id="a", candidate_index=0)
    c = pd.DataFrame({key: ["y"] for key in m.MATCH_KEYS}).assign(f=1.0, skip=False, event_id="c", candidate_index=1)
    pairs, summary = m.path_drift(a, c, ["f"])
    assert pairs.empty
    assert (summary["a_only_count"], summary["c_only_count"], summary["common_count"]) == (1, 1, 0)
