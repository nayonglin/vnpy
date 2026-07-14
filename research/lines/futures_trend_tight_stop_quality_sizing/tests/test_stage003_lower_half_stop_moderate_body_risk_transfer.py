from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import talib


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage003_lower_half_stop_moderate_body_risk_transfer as s003


def _history(rows: int = 80) -> pd.DataFrame:
    x = np.arange(rows, dtype=float)
    close = 100.0 + x * 0.3 + np.sin(x / 3.0)
    open_ = close - 0.4
    high = np.maximum(open_, close) + 0.6
    low = np.minimum(open_, close) - 0.6
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def test_latest_history_row_is_t1_and_is_used() -> None:
    original = _history()
    mutated = original.copy()
    mutated.loc[mutated.index[-1], ["open", "high", "low", "close"]] = [1.0, 10_000.0, 0.1, 9_000.0]
    left = s003.t1_quality_snapshot(original, stop_distance=1.0, feature_date="2026-01-05")
    right = s003.t1_quality_snapshot(mutated, stop_distance=1.0, feature_date="2026-01-05")
    assert left["atr14"] != pytest.approx(right["atr14"], abs=1e-12)
    assert left["body_ratio"] != pytest.approx(right["body_ratio"], abs=1e-12)
    assert left["stop_atr14"] != pytest.approx(right["stop_atr14"], abs=1e-12)
    assert left["feature_date"] == "2026-01-05"


def test_snapshot_atr_is_talib_t1() -> None:
    history = _history()
    snapshot = s003.t1_quality_snapshot(history, stop_distance=1.0)
    expected = talib.ATR(
        history.high.to_numpy(dtype=float),
        history.low.to_numpy(dtype=float),
        history.close.to_numpy(dtype=float),
        timeperiod=14,
    )[-1]
    assert snapshot["atr14"] == pytest.approx(expected, abs=1e-12)


def test_stop_preview_matches_frozen_long_and_short_logic() -> None:
    class Bar:
        close_price = 100.0
        low_price = 98.0
        high_price = 103.0

    assert s003.preview_entry_stop_price("long", Bar(), 0.03) == pytest.approx(98.0)
    assert s003.preview_entry_stop_price("short", Bar(), 0.03) == pytest.approx(103.0)


@pytest.mark.parametrize(
    ("snapshot", "enabled", "context", "exempt", "weight", "reason"),
    [
        ({"feature_available": 1, "quality_hit": 1}, True, "flat_entry", False, 1.25, "quality_risk_increase"),
        ({"feature_available": 1, "quality_hit": 0}, True, "flat_entry", False, 0.75, "other_risk_decrease"),
        ({"feature_available": 1, "quality_hit": 1}, True, "flat_entry", True, 1.0, "recovery_sleeve_exempt"),
        ({"feature_available": 0, "quality_hit": 0}, True, "flat_entry", False, 1.0, "feature_unavailable_fail_unchanged"),
        ({"feature_available": 1, "quality_hit": 1}, True, "rollover_reopen", False, 1.0, "non_flat_entry"),
    ],
)
def test_budget_weight_branches(snapshot, enabled, context, exempt, weight, reason) -> None:
    actual = s003.choose_budget_weight(snapshot, enabled=enabled, entry_context=context, recovery_exempt=exempt)
    assert actual == (weight, reason)


def test_budget_weight_uses_runtime_parameters() -> None:
    actual = s003.choose_budget_weight(
        {"feature_available": 1, "quality_hit": 1},
        enabled=True,
        entry_context="flat_entry",
        recovery_exempt=False,
        quality_weight=1.1,
        other_weight=0.9,
    )
    assert actual == (1.1, "quality_risk_increase")


def test_config_diff_is_only_stage003() -> None:
    metadata = s003.s901.s513._metadata()
    audit = s003.config_audit(metadata)
    changed = audit[audit.changed.eq(1)]
    assert not changed.empty
    assert changed.allowed.eq(1).all()
    assert set(changed.key).issubset(
        {
            "enable_stage003_risk_transfer",
            "stage003_stop_atr_max",
            "stage003_body_min_exclusive",
            "stage003_body_max_inclusive",
            "stage003_quality_weight",
            "stage003_other_weight",
        }
    )


def test_stage003_audit_fields_do_not_add_ai_features() -> None:
    source = Path(s003.__file__).read_text(encoding="utf-8")
    field_literals = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith('"stage003_') and '":' in stripped:
            field_literals.append(stripped.split('"', 2)[1])
    assert field_literals
    assert all(not s003.is_ai_derived_field(field) for field in field_literals)
    assert s003.is_ai_derived_field("stage003_ai_score")
    assert not s003.is_ai_derived_field("stage003_feature_available")
    payload = s003._stage003_audit_payload({key: index for index, key in enumerate(s003.STAGE003_AUDIT_FIELDS)})
    assert set(payload) == set(s003.STAGE003_AUDIT_FIELDS)


def test_comparison_gate_math() -> None:
    rows = [
        {"variant": "A_official", "requested_start_month": "2022-01", "total_return_pct": 100.0, "max_dd_pct": -50.0, "sharpe": 1.0, "total_slippage": 10.0, "total_trade_count": 20.0},
        {"variant": "C_stage003", "requested_start_month": "2022-01", "total_return_pct": 75.0, "max_dd_pct": -44.0, "sharpe": 1.1, "total_slippage": 9.0, "total_trade_count": 18.0},
    ]
    result = s003._comparison(pd.DataFrame(rows)).iloc[0]
    assert result.return_retention_ratio == pytest.approx(0.75)
    assert result.dd_improvement_pp == pytest.approx(6.0)
    assert result.retention_70_pass == 1
    assert result.dd_improve_3pp_pass == 1


def test_repaired_minute_audit_is_complete_and_profile_uses_fail_close_strategy() -> None:
    audit = pd.read_csv(s003.REPAIRED_MINUTE_AUDIT_PATH)
    decision = json.loads(Path(s003.s000.DECISION_PATH).read_text(encoding="utf-8"))
    assert len(audit) == decision["required_symbol_dates"]
    assert len(audit) >= 306
    assert audit.daily_ohlc_exact.eq(1).all()
    profile = s003._official_profile(s003.s901.s513._metadata())
    assert profile["strategy_cls"] is s003.QmtRollPortfolioStrategyStage000RepairedStopRetry


def test_repaired_entry_session_fails_closed(monkeypatch) -> None:
    trade_date = pd.Timestamp("2026-06-24")
    bars = pd.DataFrame(
        {
            "bar_date": [trade_date, trade_date],
            "bar_datetime": [trade_date + pd.Timedelta(hours=9), trade_date + pd.Timedelta(hours=9, minutes=1)],
            "open": [100.0, 101.0],
            "high": [101.0, 103.0],
            "low": [99.0, 100.0],
        }
    )
    monkeypatch.setattr(s003, "_REPAIRED_SESSION_KEYS", {("rb2610.SHFE", trade_date)})
    session = s003.validate_repaired_entry_session(
        vt_symbol="rb2610.SHFE",
        trade_date=trade_date,
        entry_price=100.0,
        price_tick=1.0,
        bars=bars,
    )
    assert len(session) == 2
    with pytest.raises(RuntimeError, match="outside repaired session range"):
        s003.validate_repaired_entry_session(
            vt_symbol="rb2610.SHFE",
            trade_date=trade_date,
            entry_price=200.0,
            price_tick=1.0,
            bars=bars,
        )
    with pytest.raises(RuntimeError, match="missing repaired"):
        s003.validate_repaired_entry_session(
            vt_symbol="FG609.CZCE",
            trade_date=trade_date,
            entry_price=100.0,
            price_tick=1.0,
            bars=bars,
        )


def test_strict_engine_open_uses_session_first_bar(monkeypatch) -> None:
    trade_date = pd.Timestamp("2026-06-24")
    monkeypatch.setattr(
        s003,
        "_REPAIRED_FIRST_OPEN",
        {
            ("rb2610.SHFE", trade_date): {
                "price": 3001.0,
                "bar_datetime": trade_date - pd.Timedelta(hours=3),
                "minute_source": "strict.csv",
            }
        },
    )
    engine = object.__new__(s003.Stage000StrictOpenStopRetryEngine)
    engine.datetime = trade_date.to_pydatetime()
    order = SimpleNamespace(vt_symbol="rb2610.SHFE", offset=SimpleNamespace(value="Open"))
    price, source, proxy = engine._resolve_trade_price(order, SimpleNamespace())
    assert price == 3001.0
    assert source == "stage000_strict_entry_session_first_open"
    assert proxy["proxy_first_time"] == trade_date - pd.Timedelta(hours=3)


def test_engine_account_equity_matches_mark_to_market_formula() -> None:
    strategy = object.__new__(s003.QmtRollPortfolioStrategyStage000RepairedStopRetry)
    trade = SimpleNamespace(
        vt_symbol="rb2610.SHFE",
        direction=SimpleNamespace(value="Long"),
        volume=2,
        price=100.0,
    )
    strategy.strategy_engine = SimpleNamespace(
        capital=150_000.0,
        trades={"1": trade},
        bars={"rb2610.SHFE": SimpleNamespace(close_price=110.0)},
        sizes={"rb2610.SHFE": 10.0},
        rates={"rb2610.SHFE": 0.001},
        slippages={"rb2610.SHFE": 1.0},
    )
    expected = 150_000.0 + 2 * (110.0 - 100.0) * 10.0 - 2 * 10.0 * 100.0 * 0.001 - 2 * 10.0
    assert strategy._engine_account_equity() == pytest.approx(expected, abs=1e-12)


def test_account_equity_evidence_reconciles_to_curve() -> None:
    candidates = pd.DataFrame(
        {
            "requested_start_month": ["2024-01"],
            "variant": ["C_stage003"],
            "date": ["2024-01-02"],
            "stage000_account_equity": [151_000.0],
            "stage000_account_high_water": [151_000.0],
            "stage000_account_drawdown_pct": [0.0],
            "stage000_account_equity_source": ["engine_trades_marked_to_signal_close"],
        }
    )
    curves = pd.DataFrame(
        {
            "requested_start_month": ["2024-01"],
            "variant": ["C_stage003"],
            "date": ["2024-01-02"],
            "account_equity": [151_000.0],
        }
    )
    result = s003.validate_account_equity_evidence(candidates, curves)
    assert result["candidate_count"] == 1
    assert result["max_equity_error"] == 0.0
