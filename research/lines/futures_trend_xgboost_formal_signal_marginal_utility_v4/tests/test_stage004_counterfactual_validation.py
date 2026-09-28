import copy
import importlib.util
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def module():
    spec = importlib.util.spec_from_file_location("stage004_test", ROOT / "tools/stage004_counterfactual_validation.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def target():
    return {"event_id": "fixed", "candidate_index": 1, "decision_date": "2022-02-08",
            "decision_datetime": "2022-02-08T00:00:00+08:00", "product_vt_symbol": "sp.SHFE",
            "contract_vt_symbol": "sp2205.SHFE", "direction": "long", "signal": "long_case2"}


def strategy_fixture(target):
    class Base:
        def __init__(self):
            self.estimated_equity = 100.0
            self.entry_candidate_snapshots = []

        def _plan_flat_entry_candidates(self, contexts):
            return contexts

        def _record_entry_candidate_snapshot(self, **row):
            self.entry_candidate_snapshots.append({"candidate_index": len(self.entry_candidate_snapshots) + 1, **row})

    class Strategy(Base):
        pass

    plan = {"product_vt_symbol": target["product_vt_symbol"], "target_contract": target["contract_vt_symbol"],
            "direction": "long", "signal": "long_case2", "candidate_status": "opened", "skip_reason": "",
            "volume": 2, "target_bar": SimpleNamespace(datetime=datetime.fromisoformat(target["decision_datetime"]))}
    return Strategy, plan


def test_noop_keeps_allocations_and_restores_inherited_methods(module, target):
    strategy, plan = strategy_fixture(target)
    original = strategy._plan_flat_entry_candidates
    with module.intervention(strategy, None) as audit:
        plans = {target["product_vt_symbol"]: plan}
        assert strategy()._plan_flat_entry_candidates(plans) is plans
        assert plan["candidate_status"] == "opened"
        assert audit["skip_count"] == 0
    assert strategy._plan_flat_entry_candidates is original
    assert "_plan_flat_entry_candidates" not in strategy.__dict__
    assert "_record_entry_candidate_snapshot" not in strategy.__dict__


def test_skip_changes_only_selected_plan_and_verifies_root_index(module, target):
    strategy, plan = strategy_fixture(target)
    other = copy.deepcopy(plan)
    other["product_vt_symbol"] = "rb.SHFE"
    with module.intervention(strategy, target) as audit:
        obj = strategy()
        plans = obj._plan_flat_entry_candidates({target["product_vt_symbol"]: plan, "rb.SHFE": other})
        assert plans[target["product_vt_symbol"]]["candidate_status"] == "skipped"
        assert other["candidate_status"] == "opened"
        assert other["volume"] == 2
        obj._record_entry_candidate_snapshot(product_vt_symbol=target["product_vt_symbol"],
            bar=plan["target_bar"], candidate_status=plan["candidate_status"],
            skip_reason=plan["skip_reason"], entry_context="flat_entry")
        assert audit["skip_count"] == audit["verified_snapshot_count"] == 1
        assert audit["pre_event_equity"] == 100.0
        with pytest.raises(RuntimeError, match="identity_mismatch"):
            obj._plan_flat_entry_candidates({target["product_vt_symbol"]: plan})


@pytest.mark.parametrize("field,value", [("target_contract", "sp2209.SHFE"), ("direction", "short"), ("signal", "long_case3")])
def test_wrong_plan_identity_fails_and_restores(module, target, field, value):
    strategy, plan = strategy_fixture(target)
    original = strategy._plan_flat_entry_candidates
    plan[field] = value
    with pytest.raises(RuntimeError, match="identity_mismatch"):
        with module.intervention(strategy, target):
            strategy()._plan_flat_entry_candidates({target["product_vt_symbol"]: plan})
    assert strategy._plan_flat_entry_candidates is original


def test_wrong_snapshot_index_fails(module, target):
    strategy, plan = strategy_fixture(target)
    with module.intervention(strategy, target):
        obj = strategy()
        obj.entry_candidate_snapshots.append({})
        obj._plan_flat_entry_candidates({target["product_vt_symbol"]: plan})
        with pytest.raises(RuntimeError, match="snapshot_identity_mismatch"):
            obj._record_entry_candidate_snapshot(product_vt_symbol=target["product_vt_symbol"],
                bar=plan["target_bar"], candidate_status="skipped", skip_reason=plan["skip_reason"], entry_context="flat_entry")


def daily(values, dates=None):
    return pd.DataFrame({"date": dates or ["2022-02-08", "2022-02-09", "2022-02-10"][:len(values)],
        "account_equity": values, "total_net_pnl": [values[0] - 100] + [b-a for a, b in zip(values, values[1:])],
        "total_slippage": [1.0] * len(values), "commission": [0.5] * len(values)})


def test_metrics_include_initial_equity_and_explicit_daily_win_rate(module):
    result = module.equity_metrics(daily([80, 90, 110]), pd.DataFrame({"id": [1, 2]}), initial=100)
    assert result["max_drawdown_pct"] == pytest.approx(-20)
    assert result["total_return_pct"] == pytest.approx(10)
    assert result["trade_count"] == 2
    assert result["total_slippage"] == 3
    assert result["nonzero_daily_win_rate_pct"] == pytest.approx(200 / 3)


def test_marginal_signs_follow_accept_minus_skip(module):
    result = module.account_marginal(daily([80, 90, 110]), daily([100, 100, 105]), "2022-02-08", "2022-02-10", 100)
    assert result["return_marginal"] == pytest.approx(.05)
    assert result["drawdown_marginal"] == pytest.approx(-.20)


@pytest.mark.parametrize("dates", [["2022-02-09", "2022-02-10"], ["2022-02-08", "2022-02-08", "2022-02-10"]])
def test_marginal_rejects_missing_start_and_duplicate_days(module, dates):
    with pytest.raises(RuntimeError, match="dates"):
        module.account_marginal(daily([100] * len(dates), dates), daily([100] * len(dates), dates), "2022-02-08", "2022-02-10", 100)


def endpoint_frames(target, end_positions):
    candidates = pd.DataFrame([{**target, "date": target["decision_date"], "entry_context": "flat_entry", "candidate_status": "opened"}])
    trades = pd.DataFrame([
        {"date": "2022-02-08", "vt_symbol": "sp2205.SHFE", "direction": "Long", "offset": "Open"},
        {"date": "2022-02-08", "vt_symbol": "sp2205.SHFE", "direction": "Short", "offset": "Close"},
        {"date": "2022-02-08", "vt_symbol": "sp2205.SHFE", "direction": "Long", "offset": "Open"},
        {"date": "2022-02-09", "vt_symbol": "sp2205.SHFE", "direction": "Short", "offset": "Close"},
        {"date": "2022-02-09", "vt_symbol": "sp2209.SHFE", "direction": "Long", "offset": "Open"},
    ])
    positions = pd.DataFrame(end_positions, columns=["date", "vt_symbol", "end_pos"])
    return {"entry_candidates": candidates, "trades": trades, "positions": positions}


MAPPING = {"sp2205.SHFE": "sp.SHFE", "sp2209.SHFE": "sp.SHFE"}


def test_endpoint_ignores_intraday_retry_and_rollover_close(module, target):
    frames = endpoint_frames(target, [("2022-02-08", "sp2205.SHFE", 2), ("2022-02-09", "sp2205.SHFE", 0),
        ("2022-02-09", "sp2209.SHFE", 2), ("2022-02-10", "sp2209.SHFE", 0)])
    result = module.event_endpoint(frames, target, MAPPING)
    assert result["status"] == "mature"
    assert result["end_date"] == "2022-02-10"


def test_open_position_at_end_is_censored_not_zero_label(module, target):
    frames = endpoint_frames(target, [("2022-02-08", "sp2205.SHFE", 2), ("2022-02-09", "sp2209.SHFE", 2)])
    result = module.event_endpoint(frames, target, MAPPING)
    assert result["status"] == "right_censored"
    assert "end_date" not in result


def test_planned_open_without_fill_is_unresolved(module, target):
    frames = endpoint_frames(target, [("2022-02-08", "sp2205.SHFE", 0)])
    frames["trades"] = frames["trades"].iloc[:0]
    assert module.event_endpoint(frames, target, MAPPING)["status"] == "unresolved_no_root_fill"


def test_same_day_new_root_is_not_silently_merged(module, target):
    frames = endpoint_frames(target, [("2022-02-08", "sp2205.SHFE", 2), ("2022-02-09", "sp2209.SHFE", 0)])
    row = frames["entry_candidates"].iloc[0].to_dict()
    row.update(candidate_index=2, date="2022-02-09")
    frames["entry_candidates"] = pd.concat([frames["entry_candidates"], pd.DataFrame([row])], ignore_index=True)
    assert module.event_endpoint(frames, target, MAPPING)["status"] == "unresolved_same_day_root_overlap"


def test_empty_optional_frames_round_trip(module, tmp_path):
    for name in module.FRAME_NAMES:
        pd.DataFrame().to_csv(tmp_path / f"{name}.csv", index=False)
    result = module.read_frames(tmp_path)
    assert all(frame.empty for frame in result.values())


def test_failed_upstream_parity_cannot_report_validation_success(module, target, monkeypatch):
    frames = {name: pd.DataFrame() for name in module.FRAME_NAMES}
    monkeypatch.setattr(module, "support", lambda: SimpleNamespace(evaluate_stage002_features=lambda a, b: {"passed": False}))
    with pytest.raises(RuntimeError, match="baseline_event_parity_failed"):
        module.validate_results([{"frames": frames}] * 3, target)
