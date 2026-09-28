import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / "tools/stage009_path_validation.py"
    assert path.exists(), "full path validation implementation missing"
    spec = importlib.util.spec_from_file_location("full_path_validation_test", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize("a,c,want", [( (100,-40), (101,-39), True), ((100,-40),(99,-39),False),
                                     ((100,-40),(101,-41),False), ((100,-40),(100,-39),False)])
def test_primary_gate_requires_both_strict_improvements(a,c,want):
    m = module()
    result = m.primary_comparison({"total_return_pct":a[0], "max_drawdown_pct":a[1]},
                                  {"total_return_pct":c[0], "max_drawdown_pct":c[1]})
    assert result["primary_gate_passed"] is want
    assert result["valuable_candidate_verified"] is False
    assert result["reviewer_started"] is False


def test_decision_features_are_rebuilt_from_current_candidate_not_a_identity():
    m = module()
    batch = m.batch_module()
    h = batch.load_history()
    import json
    formal = json.loads((batch.REFERENCE / "receipt.json").read_text())["formal_identity"]
    raw = batch.read_frame(batch.REFERENCE / "entry_candidates.csv")
    candidates = raw.loc[raw.candidate_index.eq(241)].copy()
    candidates["estimated_equity"] = 500000
    candidates["total_margin_in_use_before"] = 100000
    rebuilt = h.build_features(candidates, formal)
    assert rebuilt.iloc[0].margin_to_equity_before == 0.2
    decisions = rebuilt.assign(cutoff="2022-02-01", status="predicted", skip=True,
                               return_marginal=-0.1, drawdown_marginal=-0.2)
    candidates["candidate_status"] = "skipped"
    candidates["skip_reason"] = "research_xgb_predicted_harm"
    candidates["is_opened"] = 0
    calls = []
    def predict(event):
        calls.append(event["margin_to_equity_before"])
        return {"cutoff":"2022-02-01", "status":"predicted", "skip":True,
                "return_marginal":-0.1, "drawdown_marginal":-0.2}
    assert m.validate_decisions(candidates, decisions, formal, predict)["skip_count"] == 1
    assert calls == [0.2]
    decisions["margin_to_equity_before"] = 0
    with pytest.raises(AssertionError):
        m.validate_decisions(candidates, decisions, formal, predict)


def test_decision_audit_rejects_missing_events_or_wrong_prediction():
    m = module()
    batch = m.batch_module()
    import json
    formal = json.loads((batch.REFERENCE / "receipt.json").read_text())["formal_identity"]
    raw = batch.read_frame(batch.REFERENCE / "entry_candidates.csv")
    candidates = raw.loc[raw.candidate_index.eq(241)].copy()
    decisions = batch.load_history().build_features(candidates, formal).assign(
        cutoff="2022-02-01", status="predicted", skip=False, return_marginal=0.1, drawdown_marginal=-0.2)
    with pytest.raises(RuntimeError, match="inventory"):
        m.validate_decisions(candidates, decisions.iloc[:0], formal, lambda _: {})
    with pytest.raises(RuntimeError, match="prediction"):
        m.validate_decisions(candidates, decisions, formal, lambda _: {
            "cutoff":"2022-02-01", "status":"predicted", "skip":False,
            "return_marginal":0.2, "drawdown_marginal":-0.2})


def test_prefix_changes_before_first_action_are_rejected():
    m = module()
    a = {"daily":pd.DataFrame({"date":["2020-01-01","2020-01-02"],"account_equity":[150000,151000]}),
         "trades":pd.DataFrame({"datetime":["2020-01-01"],"volume":[1]}),
         "positions":pd.DataFrame({"date":["2020-01-01"],"end_pos":[1]}),
         "entry_candidates":pd.DataFrame({"candidate_index":[0,1],"date":["2020-01-01","2020-01-02"]})}
    c = {key:value.copy() for key,value in a.items()}
    m.validate_prefix(a,c,"2020-01-02",1)
    c["positions"]["end_pos"] = 2
    with pytest.raises(AssertionError):
        m.validate_prefix(a,c,"2020-01-02",1)
