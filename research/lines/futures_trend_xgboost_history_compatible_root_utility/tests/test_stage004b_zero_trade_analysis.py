import importlib.util
from pathlib import Path

import pandas as pd
import pytest


PATH = Path(__file__).resolve().parents[1] / "tools/stage004b_zero_trade_analysis.py"


def module():
    assert PATH.exists(), "zero trade normalizer missing"
    spec = importlib.util.spec_from_file_location("zero_trade_analysis", PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def fixture():
    dates = ["2020-01-02", "2020-01-03"]
    raw = pd.DataFrame([dict(date=dates[-1], account_equity=150000, net_pnl=0, total_net_pnl=0,
                             total_slippage=0, commission=0, trade_count=0)])
    positions = pd.DataFrame([{**{key: 0 for key in ["start_pos", "end_pos", "trade_count", "commission", "slippage",
                                                    "holding_pnl", "trading_pnl", "total_pnl", "net_pnl"]},
                               "date": date, "vt_symbol": "rb2005.SHFE"} for date in dates])
    columns = [*raw.columns, "holding_pnl", "trading_pnl", "total_pnl"]
    return raw, positions, pd.DataFrame(), dates, columns


def test_zero_trade_curve_uses_complete_s_ledger_not_a_equity():
    result = module().normalize_zero_trade(*fixture())
    assert result.date.tolist() == ["2020-01-02", "2020-01-03"]
    assert result.account_equity.tolist() == [150000, 150000]
    assert result.total_pnl.tolist() == [0, 0]


@pytest.mark.parametrize("kind", ["missing_day", "position", "cost", "trade", "equity", "unknown_column"])
def test_nonzero_or_incomplete_evidence_is_rejected(kind):
    raw, positions, trades, dates, columns = fixture()
    if kind == "missing_day":
        positions = positions.iloc[:1]
    elif kind == "position":
        positions.loc[0, "end_pos"] = 1
    elif kind == "cost":
        positions.loc[0, "commission"] = 1
    elif kind == "trade":
        trades = pd.DataFrame([{"volume": 1}])
    elif kind == "equity":
        raw.loc[0, "account_equity"] = 150001
    else:
        columns.append("unknown_state")
    with pytest.raises(RuntimeError):
        module().normalize_zero_trade(raw, positions, trades, dates, columns)


def test_uncomputed_pre_close_uses_only_previous_s_calendar_day():
    m = module()
    raw, positions, *_ = fixture()
    positions["close_price"] = [100.0, 102.0]
    positions["pre_close"] = 0
    assert hasattr(m, "normalize_zero_positions"), "zero position normalizer missing"
    normalized = m.normalize_zero_positions(positions)
    assert normalized.pre_close.tolist() == [0, 100]
    assert positions.pre_close.tolist() == [0, 0]
