import importlib.util
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def module():
    path = Path(__file__).resolve().parents[1] / "tools/stage007_objective_headroom_audit.py"
    spec = importlib.util.spec_from_file_location("stage007_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def events(end="2022-02-01", status="mature"):
    return pd.DataFrame({"decision_date": ["2022-01-01"], "end_date": [end], "status": [status]})


def daily(values):
    return pd.DataFrame({"date": ["2022-01-03", "2022-02-01", "2022-03-01", "2022-04-01"], "account_equity": values})


def test_past_drawdown_cannot_be_erased_by_later_model(module):
    result = module.objective_headroom(daily([100, 60, 100, 200]), events(), 1, initial=100)
    assert result["first_eligible_training_month"] == "2022-03-01"
    assert result["full_max_drawdown_pct"] == pytest.approx(-40)
    assert not result["strict_full_drawdown_improvement_possible"]


def test_later_worst_drawdown_has_headroom_not_proven_success(module):
    result = module.objective_headroom(daily([100, 90, 100, 50]), events(), 1, initial=100)
    assert result["strict_full_drawdown_improvement_possible"]
    assert result["immutable_prefix_max_drawdown_pct"] == pytest.approx(-10)
    assert result["decision"] == "headroom_exists_not_model_evidence"


@pytest.mark.parametrize("event_frame", [events(status="right_censored_open"), events(end="2022-04-01")])
def test_unmatured_labels_cannot_enable_training_earlier(module, event_frame):
    result = module.objective_headroom(daily([100, 90, 100, 80]), event_frame, 1, initial=100)
    assert result["first_eligible_training_month"] is None
    assert not result["strict_full_drawdown_improvement_possible"]
