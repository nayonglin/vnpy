from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage005_current_snapshot_true_engine.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage005_current_snapshot_true_engine", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_payloads() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = pd.DataFrame(
        [
            {
                "end_equity": 100.0,
                "total_return_pct": 10.0,
                "max_dd_pct": -5.0,
                "sharpe": 1.0,
                "total_slippage": 20.0,
                "total_trade_count": 2.0,
                "nonzero_daily_win_rate_pct": 50.0,
                "max_broker10_margin_to_equity_pct": 90.0,
                "days_over_100pct": 0,
                "account_survival_pass": 1,
                "profile": "identity-a",
            }
        ]
    )
    curve = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "account_equity": 100.0,
                "nav": 1.0,
                "drawdown_pct": 0.0,
                "broker10_margin_to_equity_pct": 10.0,
                "net_pnl": 0.0,
                "trade_count": 0.0,
                "total_slippage": 0.0,
                "rebased_equity": 100.0,
                "rebased_nav": 1.0,
                "broker10_margin_to_rebased_equity_pct": 10.0,
                "profile": "identity-a",
            }
        ]
    )
    trades = pd.DataFrame(
        [
            {
                "trade_id": "t1",
                "order_id": "o1",
                "datetime": "2026-01-02 00:00:00+08:00",
                "date": "2026-01-02",
                "time": "00:00:00",
                "vt_symbol": "a.X",
                "symbol": "a",
                "exchange": "X",
                "direction": "Long",
                "offset": "Open",
                "price": 1.0,
                "volume": 1.0,
                "signed_volume": 1.0,
                "gateway_name": "BACKTESTING",
                "exit_reason": "",
                "profile": "identity-a",
            }
        ]
    )
    return summary, curve, trades


def test_baseline_repeat_ignores_only_identity_labels() -> None:
    module = load_module()
    summary, curve, trades = sample_payloads()
    repeated_summary = summary.assign(profile="identity-b")
    repeated_curve = curve.assign(profile="identity-b")
    repeated_trades = trades.assign(profile="identity-b")

    result = module.compare_baseline_repeat(
        summary,
        repeated_summary,
        curve,
        repeated_curve,
        trades,
        repeated_trades,
    )

    assert result["passed"] is True
    assert all(result["gates"].values())


def test_baseline_repeat_rejects_daily_equity_drift() -> None:
    module = load_module()
    summary, curve, trades = sample_payloads()
    repeated_curve = curve.copy()
    repeated_curve.loc[0, "account_equity"] += 0.01

    result = module.compare_baseline_repeat(
        summary,
        summary,
        curve,
        repeated_curve,
        trades,
        trades,
    )

    assert result["passed"] is False
    assert result["gates"]["curve_payload_exact"] is False


def test_baseline_repeat_rejects_trade_payload_drift() -> None:
    module = load_module()
    summary, curve, trades = sample_payloads()
    repeated_trades = trades.copy()
    repeated_trades.loc[0, "volume"] = 2.0

    result = module.compare_baseline_repeat(
        summary,
        summary,
        curve,
        curve,
        trades,
        repeated_trades,
    )

    assert result["passed"] is False
    assert result["gates"]["trade_payload_exact"] is False
