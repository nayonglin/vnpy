import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest


PATH = Path(__file__).resolve().parents[1] / "tools/stage003_cancelled_lifecycle.py"


def module():
    assert PATH.exists(), "cancelled lifecycle implementation missing"
    spec = importlib.util.spec_from_file_location("cancelled_lifecycle", PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TARGET = {"event_id": "event", "decision_date": "2020-05-11", "contract_vt_symbol": "CF009.CZCE", "direction": "long"}


def trace():
    order = {"vt_orderid": "BACKTESTING.25", "datetime": "2020-05-11 00:00:00+08:00",
             "direction": "Direction.LONG", "offset": "Offset.OPEN", "price": "11625", "volume": "6",
             "traded": "0", "status": "Status.SUBMITTING"}
    common = {"date": "2020-05-11", "phase": "after", "position": 0, "trade_events": []}
    return [{**common, "method": "rebalance_portfolio", "target": 6, "layers": [{"volume": "6"}],
             "orders": [order], "active_order_ids": ["BACKTESTING.25"]},
            {**common, "method": "_process_forced_margin_deleverage", "target": 0, "layers": [],
             "orders": [order], "active_order_ids": ["BACKTESTING.25"],
             "trade_events": [{"reason": "forced_margin_deleverage", "vt_symbol": "CF009.CZCE", "volume": "6"}]},
            {**common, "method": "on_bars", "target": 0, "layers": [],
             "orders": [{**order, "status": "Status.CANCELLED"}], "active_order_ids": []}]


def test_terminal_cancel_keeps_event_and_does_not_create_zero_labels():
    result = module().adjudicate(TARGET, trace())
    assert result["status"] == "mature_cancelled_unfilled"
    assert result["end_date"] == TARGET["decision_date"]
    assert result["terminal_order_id"] == "BACKTESTING.25"
    assert "return_marginal" not in result


@pytest.mark.parametrize("field,value", [("traded", "1"), ("status", "Status.SUBMITTING"),
                                         ("direction", "Direction.SHORT"), ("datetime", "2020-05-12")])
def test_ambiguous_or_partially_filled_order_not_treated_as_cancelled(field, value):
    rows = deepcopy(trace())
    rows[-1]["orders"][0][field] = value
    with pytest.raises(RuntimeError):
        module().adjudicate(TARGET, rows)


def test_remaining_target_or_missing_force_evidence_rejected():
    for key, value in (("target", 1), ("layers", [{"volume": "1"}])):
        rows = trace()
        rows[-1][key] = value
        with pytest.raises(RuntimeError):
            module().adjudicate(TARGET, rows)
    rows = trace()
    rows[1]["trade_events"] = []
    with pytest.raises(RuntimeError):
        module().adjudicate(TARGET, rows)
