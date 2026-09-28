import importlib.util
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def module():
    path = Path(__file__).resolve().parents[1] / "tools/stage005_event_lifecycle_audit.py"
    spec = importlib.util.spec_from_file_location("stage005_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(next_date="2022-03-04"):
    target = {"event_id": "root", "candidate_index": 1, "decision_date": "2022-03-02",
              "product_vt_symbol": "SM.CZCE", "contract_vt_symbol": "SM205.CZCE", "direction": "long"}
    candidates = pd.DataFrame([{"candidate_index": 2, "date": next_date, "product_vt_symbol": "SM.CZCE",
                               "entry_context": "flat_entry", "candidate_status": "opened"}])
    trades = pd.DataFrame([
        {"trade_id": "1", "date": "2022-03-03", "vt_symbol": "SM205.CZCE", "direction": "Long", "offset": "Open", "volume": 2, "signed_volume": 2},
        {"trade_id": "2", "date": "2022-03-04", "vt_symbol": "SM205.CZCE", "direction": "Short", "offset": "Close", "volume": 2, "signed_volume": -2},
        {"trade_id": "3", "date": "2022-03-07", "vt_symbol": "SM205.CZCE", "direction": "Long", "offset": "Open", "volume": 1, "signed_volume": 1},
    ])
    exposure = pd.Series([2.0, 0.0, 1.0], index=["2022-03-03", "2022-03-04", "2022-03-07"])
    calendar = ["2022-03-02", "2022-03-03", "2022-03-04", "2022-03-07"]
    return target, candidates, trades, exposure, calendar


def test_close_before_same_day_new_decision_is_mature(module):
    result = module.event_lifecycle(*fixture())
    assert result["status"] == "mature"
    assert result["first_fill_date"] == "2022-03-03"
    assert result["end_date"] == "2022-03-04"
    assert result["root_trade_id"] == "1"


def test_fill_on_next_decision_day_belongs_to_previous_root(module):
    target, candidates, trades, exposure, calendar = fixture("2022-03-03")
    exposure.loc["2022-03-03"] = 0.0
    result = module.event_lifecycle(target, candidates, trades, exposure, calendar)
    assert result["status"] == "mature"
    assert result["end_date"] == "2022-03-03"


def test_pending_entry_at_last_bar_is_censored(module):
    target, candidates, trades, exposure, calendar = fixture()
    target["decision_date"] = calendar[-1]
    result = module.event_lifecycle(target, candidates.iloc[:0], trades.iloc[:0], exposure, calendar)
    assert result["status"] == "right_censored_pending_entry"
    assert not result.get("end_date")


def test_no_fill_before_end_is_unresolved_not_censored(module):
    target, candidates, trades, exposure, calendar = fixture()
    result = module.event_lifecycle(target, candidates, trades.iloc[:0], exposure, calendar)
    assert result["status"] == "unresolved_no_root_fill"


def test_open_position_is_censored_without_zero_label(module):
    target, candidates, trades, exposure, calendar = fixture()
    exposure[:] = 2
    result = module.event_lifecycle(target, candidates.iloc[:0], trades, exposure, calendar)
    assert result["status"] == "right_censored_open"
    assert not result.get("end_date")


def test_missing_position_date_is_not_filled_as_flat(module):
    target, candidates, trades, exposure, calendar = fixture()
    result = module.event_lifecycle(target, candidates, trades, exposure.drop("2022-03-04"), calendar)
    assert result["status"] == "unresolved_position_coverage"


def test_truly_overlapping_root_is_unresolved(module):
    target, candidates, trades, exposure, calendar = fixture("2022-03-03")
    result = module.event_lifecycle(target, candidates, trades, exposure, calendar)
    assert result["status"] == "unresolved_root_overlap"


def test_signed_fills_reconcile_with_actual_positions(module):
    _, _, trades, _, _ = fixture()
    positions = pd.DataFrame([
        {"date": "2022-03-03", "vt_symbol": "SM205.CZCE", "start_pos": 0, "end_pos": 2},
        {"date": "2022-03-04", "vt_symbol": "SM205.CZCE", "start_pos": 2, "end_pos": 0},
        {"date": "2022-03-07", "vt_symbol": "SM205.CZCE", "start_pos": 0, "end_pos": 1},
    ])
    assert module.reconcile_positions(trades, positions)["max_abs_position_error"] == 0
    positions.loc[1, "end_pos"] = 1
    with pytest.raises(RuntimeError, match="position_reconciliation"):
        module.reconcile_positions(trades, positions)


def test_duplicate_trade_id_is_rejected(module):
    _, _, trades, _, _ = fixture()
    with pytest.raises(RuntimeError, match="trade_identity"):
        module.reconcile_positions(pd.concat([trades, trades.iloc[:1]]), pd.DataFrame())
