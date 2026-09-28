import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools/stage006_monthly_models.py"
SPEC = json.loads((ROOT / "stages/stage004_model_spec.json").read_text())


def module():
    assert PATH.exists(), "monthly model implementation missing"
    spec = importlib.util.spec_from_file_location("monthly_models_test", PATH)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sample(count=70):
    values = np.arange(count, dtype=float)
    data = pd.DataFrame({"event_id": [f"synthetic-{i}" for i in range(count)],
                         "decision_date": "2020-01-02", "label_end_date": "2020-01-03",
                         "label_status": "verified", "lifecycle_status": "mature",
                         "product_vt_symbol": "rb.SHFE", "return_marginal": values / 1000 - 0.04,
                         "drawdown_marginal": -values / 2000 + 0.01})
    for index, feature in enumerate(SPEC["features"]):
        data[feature] = np.sin(values + index) + values / 10
    return data


class RecordingRegressor:
    def __init__(self, **parameters):
        self.parameters = parameters

    def fit(self, features, target):
        self.features = features.copy()
        self.target = np.array(target, copy=True)
        return self

    def predict(self, features):
        return np.zeros(len(features))


def test_training_cutoff_excludes_same_day_and_future_endpoints():
    data = sample()
    data.loc[0, "label_end_date"] = "2020-02-01"
    data.loc[1, "label_end_date"] = "2020-02-02"
    data.loc[2, ["decision_date", "label_end_date"]] = ["2020-02-01", "2020-02-01"]
    train = module().training_rows(data, "2020-02-01", SPEC)
    assert len(train) == 67
    assert not set(data.iloc[:3].event_id).intersection(train.event_id)


def test_censored_rows_never_train_or_receive_zero_targets():
    data = sample()
    data.loc[0, ["label_status", "lifecycle_status"]] = ["censored", "right_censored_open"]
    data.loc[0, ["label_end_date", *SPEC["targets"]]] = [None, np.nan, np.nan]
    train = module().training_rows(data, "2020-02-01", SPEC)
    assert len(train) == 69 and data.loc[0, SPEC["targets"]].isna().all()


@pytest.mark.parametrize("change", [{"label_status": "pending"}, {"event_id": "synthetic-1"},
                                     {"product_vt_symbol": "fu.SHFE"}, {"directional_rsi": np.nan},
                                     {"return_marginal": np.inf}, {"label_end_date": "2020-01-01"}])
def test_invalid_training_inventory_is_rejected(change):
    data = sample()
    for key, value in change.items():
        data.loc[0, key] = value
    with pytest.raises(RuntimeError):
        module().training_rows(data, "2020-02-01", SPEC)


def test_cutoff_must_be_calendar_month_start():
    with pytest.raises(RuntimeError, match="cutoff_not_month_start"):
        module().training_rows(sample(), "2020-02-02", SPEC)


def test_subminimum_month_does_not_construct_regressor():
    def forbidden(**kwargs):
        raise AssertionError("must not fit")
    bundle = module().fit_month(sample(59), "2020-02-01", SPEC, forbidden)
    assert bundle["status"] == "untrained" and bundle["fit_count"] == 0


def test_standardization_uses_only_training_labels_and_fixed_features():
    data = sample()
    data.loc[69, "label_end_date"] = "2020-02-01"
    data.loc[69, SPEC["targets"]] = [1e9, -1e9]
    bundle = module().fit_month(data, "2020-02-01", SPEC, RecordingRegressor)
    assert bundle["fit_count"] == 2 and len(bundle["train_event_ids"]) == 69
    for target, head in bundle["heads"].items():
        expected = data.iloc[:69][target].to_numpy()
        assert head["mean"] == expected.mean()
        assert head["std"] == expected.std(ddof=0)
        estimator = head["estimator"]
        assert estimator.parameters == SPEC["estimator"]
        assert estimator.features.columns.tolist() == SPEC["features"]
        np.testing.assert_array_equal(estimator.target, (expected - expected.mean()) / expected.std(ddof=0))
        predicted = module().predict_bundle(bundle, data.iloc[[0]], SPEC)
        assert predicted[target][0] == head["mean"]


def test_constant_target_uses_training_mean_without_xgboost():
    data = sample()
    data[SPEC["targets"]] = [-0.125, -0.25]
    def forbidden(**kwargs):
        raise AssertionError("constant target must not fit")
    m = module()
    bundle = m.fit_month(data, "2020-02-01", SPEC, forbidden)
    assert bundle["fit_count"] == 0 and bundle["status"] == "trained"
    predictions = m.predict_bundle(bundle, data.iloc[:2], SPEC)
    assert predictions["return_marginal"].tolist() == [-0.125, -0.125]


@pytest.mark.parametrize("ret,dd,product,expected", [(-0.01, -0.02, "rb.SHFE", True),
    (0.0, -0.02, "rb.SHFE", False), (-0.01, 0.0, "rb.SHFE", False),
    (0.01, -0.02, "rb.SHFE", False), (-0.01, 0.02, "rb.SHFE", False),
    (-0.01, -0.02, "fu.SHFE", False), (None, None, "rb.SHFE", False)])
def test_action_requires_two_strictly_negative_heads(ret, dd, product, expected):
    assert module().should_skip(ret, dd, product) is expected


def test_nonfinite_prediction_is_a_model_failure():
    with pytest.raises(RuntimeError, match="nonfinite_prediction"):
        module().should_skip(np.nan, -0.01, "rb.SHFE")


def test_synthetic_xgboost_save_load_predict_is_exact(tmp_path):
    m = module()
    data = sample()
    bundle = m.fit_month(data, "2020-02-01", SPEC)
    before = m.predict_bundle(bundle, data.iloc[:5], SPEC)
    target = tmp_path / "2020-02-01"
    identity = m.save_bundle(bundle, target, SPEC)
    loaded = m.load_bundle(target, identity, SPEC)
    after = m.predict_bundle(loaded, data.iloc[:5], SPEC)
    for name in SPEC["targets"]:
        np.testing.assert_array_equal(before[name], after[name])
    with pytest.raises(FileExistsError):
        m.save_bundle(bundle, target, SPEC)
    (target / "return_marginal.ubj").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="model_file_changed"):
        m.load_bundle(target, identity, SPEC)


def test_training_summary_blocks_partial_snapshot_before_fitting():
    with pytest.raises(RuntimeError, match="training_inventory_incomplete"):
        module().require_complete_summary({"status": "passed", "completed": 29, "planned": 274,
                                          "censored": 2, "pending": 245, "training_ready": False,
                                          "unfinished_job_ids": []})


def test_month_schedule_includes_full_frozen_period():
    months = module().month_schedule(SPEC)
    assert months[0] == "2020-01-01" and months[-1] == "2026-08-01" and len(months) == 80


def test_decision_uses_current_account_features_without_baseline_event_id():
    class FeatureRegressor(RecordingRegressor):
        def predict(self, features):
            self.last_features = features.copy()
            return features["portfolio_drawdown_pct"].to_numpy()
    m = module()
    bundle = m.fit_month(sample(), "2020-02-01", SPEC, FeatureRegressor)
    current = {name: 0.0 for name in SPEC["features"]}
    current["portfolio_drawdown_pct"] = -0.4
    result = m.predict_decision(bundle, "2020-02-03", "rb.SHFE", current, SPEC)
    assert result["status"] == "predicted" and result["cutoff"] == "2020-02-01"
    for target in SPEC["targets"]:
        head = bundle["heads"][target]
        assert head["estimator"].last_features.iloc[0].to_dict() == current
        assert result[target] == -0.4 * head["std"] + head["mean"]


def test_future_or_stale_month_model_cannot_be_used():
    m = module()
    bundle = m.fit_month(sample(59), "2020-02-01", SPEC, RecordingRegressor)
    for day in ("2020-01-31", "2020-03-02"):
        with pytest.raises(RuntimeError, match="decision_model_month_mismatch"):
            m.predict_decision(bundle, day, "rb.SHFE", {}, SPEC)


def test_untrained_month_and_fixed_fu_leave_decision_unchanged():
    m = module()
    result = m.predict_decision(None, "2020-02-03", "rb.SHFE", {}, SPEC)
    assert result["skip"] is False and result["status"] == "untrained"
    bundle = m.fit_month(sample(59), "2020-02-01", SPEC, RecordingRegressor)
    result = m.predict_decision(bundle, "2020-02-03", "rb.SHFE", {}, SPEC)
    assert result["skip"] is False and result["return_marginal"] is None
    result = m.predict_decision(bundle, "2020-02-03", "fu.SHFE", {}, SPEC)
    assert result["skip"] is False and result["status"] == "fixed_fu"


def test_training_summary_with_failure_or_bad_counts_is_rejected():
    valid = {"status": "passed", "completed": 274, "planned": 274, "censored": 2,
             "pending": 0, "training_ready": True, "unfinished_job_ids": []}
    m = module()
    m.require_complete_summary(valid)
    for patch in ({"status": "failed"}, {"completed": 273}, {"censored": 0}, {"unfinished_job_ids": ["x"]}):
        with pytest.raises(RuntimeError, match="training_inventory_incomplete"):
            m.require_complete_summary({**valid, **patch})


def test_constant_and_untrained_bundles_survive_storage(tmp_path):
    m = module()
    data = sample()
    data[SPEC["targets"]] = [-0.1, -0.2]
    for name, count in (("constant", 70), ("untrained", 59)):
        bundle = m.fit_month(data.iloc[:count], "2020-02-01", SPEC, RecordingRegressor)
        identity = m.save_bundle(bundle, tmp_path / name, SPEC)
        loaded = m.load_bundle(tmp_path / name, identity, SPEC)
        result = m.predict_bundle(loaded, data.iloc[:2], SPEC)
        if count < 60:
            assert result is None
        else:
            assert result["return_marginal"].tolist() == [-0.1, -0.1]
