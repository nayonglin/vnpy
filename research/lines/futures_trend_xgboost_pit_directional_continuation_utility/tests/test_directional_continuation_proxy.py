from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


LINE_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = LINE_DIR.parents[2]
TOOLS_DIR = LINE_DIR / "tools"
EXAMPLES_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (TOOLS_DIR, EXAMPLES_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import directional_continuation_proxy as proxy_module  # noqa: E402
from directional_continuation_proxy import (  # noqa: E402
    DirectionProxyError,
    DirectionSettings,
    _formal_direction,
    build_cost_metadata,
    evaluate_direction_proxy,
    prepare_contract_bars,
    select_am_history,
)


def _bars(close: np.ndarray, *, start: str = "2024-01-02", wick_rows: int = 0) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=len(close))
    open_ = close - 0.1
    high = np.maximum(open_, close) + 0.02
    low = np.minimum(open_, close) - 0.02
    if wick_rows:
        high[-wick_rows:] = np.maximum(open_[-wick_rows:], close[-wick_rows:]) + 5.0
        low[-wick_rows:] = np.minimum(open_[-wick_rows:], close[-wick_rows:]) - 5.0
    return pd.DataFrame(
        {
            "trade_date": dates,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": 100,
            "open_oi": 100,
            "close_oi": 100,
        }
    )


def test_am41_uses_only_observed_bars_at_or_before_query_date() -> None:
    raw = _bars(np.linspace(100.0, 150.0, 50))
    prepared = prepare_contract_bars(raw, "rb2405.SHFE")
    query_date = pd.Timestamp(raw.loc[44, "trade_date"])

    selected = select_am_history(prepared, query_date, size=41)

    assert selected.observable is True
    assert len(selected.history) == 41
    assert selected.history["trade_date"].max() == query_date
    assert (selected.history["trade_date"] > query_date).sum() == 0
    assert selected.post_query_bar_usage_count == 0
    assert selected.flat_fill_bar_usage_count == 0
    assert selected.available_bar_count == 45


def test_unobservable_history_is_not_coerced_to_neutral() -> None:
    raw = _bars(np.linspace(100.0, 120.0, 40))
    prepared = prepare_contract_bars(raw, "rb2405.SHFE")

    result = evaluate_direction_proxy(prepared, raw["trade_date"].iloc[-1])

    assert result["proxy_observable"] is False
    assert result["proxy_unobservable_reason"] == "insufficient_observed_bars"
    assert result["direction_proxy"] is None
    assert result["long_allowed"] is None
    assert result["short_allowed"] is None


def test_missing_query_bar_is_unobservable_even_with_41_prior_bars() -> None:
    raw = _bars(np.linspace(100.0, 150.0, 45))
    prepared = prepare_contract_bars(raw, "rb2405.SHFE")
    query_date = pd.Timestamp(raw["trade_date"].iloc[-1]) + pd.offsets.BDay(1)

    result = evaluate_direction_proxy(prepared, query_date)

    assert result["proxy_observable"] is False
    assert result["proxy_unobservable_reason"] == "query_date_real_bar_missing"
    assert result["direction_proxy"] is None


def test_duplicate_dates_and_invalid_used_ohlc_fail_closed() -> None:
    raw = _bars(np.linspace(100.0, 150.0, 45))
    duplicate = pd.concat([raw, raw.tail(1)], ignore_index=True)
    with pytest.raises(DirectionProxyError, match="raw_bar_date_duplicate"):
        prepare_contract_bars(duplicate, "rb2405.SHFE")

    invalid = raw.copy()
    invalid.loc[invalid.index[-1], "high"] = invalid.loc[invalid.index[-1], "low"] - 1.0
    prepared = prepare_contract_bars(invalid, "rb2405.SHFE")
    with pytest.raises(DirectionProxyError, match="used_ohlc_invalid"):
        evaluate_direction_proxy(prepared, invalid["trade_date"].iloc[-1])


@pytest.mark.parametrize(
    ("close", "expected_direction"),
    [
        (np.linspace(100.0, 150.0, 41), 1),
        (np.linspace(150.0, 100.0, 41), -1),
        (np.repeat(100.0, 41), 0),
    ],
)
def test_direction_proxy_matches_frozen_strategy_methods(close: np.ndarray, expected_direction: int) -> None:
    raw = _bars(close)
    prepared = prepare_contract_bars(raw, "rb2405.SHFE")

    result = evaluate_direction_proxy(prepared, raw["trade_date"].iloc[-1])

    assert result["proxy_observable"] is True
    assert result["direction_proxy"] == expected_direction
    assert result["formula_mismatch"] is False
    assert result["formal_oracle_class"].endswith("QmtRollPortfolioStrategyStage847C9StopRetry")
    assert not (result["long_allowed"] and result["short_allowed"])


def test_formal_oracle_does_not_depend_on_manual_formula(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _bars(np.linspace(100.0, 150.0, 41))
    history = prepare_contract_bars(raw, "rb2405.SHFE")

    def fail_if_called(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("manual formula must not feed the formal oracle")

    monkeypatch.setattr(proxy_module, "_manual_direction", fail_if_called)

    formal_long, formal_short = _formal_direction(history, DirectionSettings())

    assert formal_long is True
    assert formal_short is False


def test_wick_filter_blocks_otherwise_bullish_continuation() -> None:
    raw = _bars(np.linspace(100.0, 150.0, 41), wick_rows=6)
    prepared = prepare_contract_bars(raw, "rb2405.SHFE")

    result = evaluate_direction_proxy(prepared, raw["trade_date"].iloc[-1])

    assert result["bullish_alignment"] is True
    assert result["long_wick_filter_pass"] is False
    assert result["long_allowed"] is False
    assert result["direction_proxy"] == 0


def test_frozen_settings_are_symmetric_and_exact_am41() -> None:
    settings = DirectionSettings()

    assert settings.ma_periods == (5, 10, 20, 40)
    assert settings.exact_am_size == 41
    assert settings.long_entry_enabled is True
    assert settings.short_entry_enabled is True
    assert settings.ma5_extreme_filter_enabled is True
    assert settings.ma5_extreme_compare_days == 3
    assert settings.ma5_angle_reversal_filter_enabled is False
    assert settings.short_ma5_slope_filter_enabled is True
    assert settings.wick_chop_filter_enabled is True
    assert settings.wick_chop_filter_lookback == 10
    assert settings.wick_chop_filter_max_days == 5


def test_cost_metadata_separates_explicit_and_research_fallback() -> None:
    product_metadata = pd.DataFrame(
        [
            {"vt_symbol": "jm.DCE", "symbol_kind": "product_cont", "price_tick": 0.5, "volume_multiple": 60},
            {"vt_symbol": "zn.SHFE", "symbol_kind": "product_cont", "price_tick": 5.0, "volume_multiple": 5},
        ]
    )
    costs = build_cost_metadata(
        ["jm.DCE", "zn.SHFE"],
        product_metadata,
        rates={"jm.DCE": 0.0},
        slippages={"jm.DCE": 1.0},
        sizes={"jm.DCE": 60},
        priceticks={"jm.DCE": 0.5},
    ).set_index("product_vt_symbol")

    assert costs.loc["jm.DCE", "cost_source"] == "formal_explicit_legacy_universe"
    assert costs.loc["jm.DCE", "slippage"] == pytest.approx(1.0)
    assert costs.loc["jm.DCE", "pricetick"] == pytest.approx(0.5)
    assert costs.loc["zn.SHFE", "cost_source"] == "research_metadata_fallback"
    assert costs.loc["zn.SHFE", "slippage"] == pytest.approx(5.0)
    assert costs.loc["zn.SHFE", "rate"] == pytest.approx(0.0)
    assert set(costs["cost_contract_name"]) == {"research_code_defined_cost_proxy"}


def test_cost_metadata_rejects_nonpositive_fallback_fields() -> None:
    product_metadata = pd.DataFrame(
        [{"vt_symbol": "zn.SHFE", "symbol_kind": "product_cont", "price_tick": 0.0, "volume_multiple": 5}]
    )

    with pytest.raises(DirectionProxyError, match="cost_metadata_invalid"):
        build_cost_metadata(
            ["zn.SHFE"],
            product_metadata,
            rates={},
            slippages={},
            sizes={},
            priceticks={},
        )
