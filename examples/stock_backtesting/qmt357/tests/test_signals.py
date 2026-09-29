"""QMT 357 migration contract: pure signals, no account or futures imports."""

import importlib.util

import numpy as np
import pandas as pd
import pytest


def api():
    """Make the initial RED a missing-feature assertion, not collection failure."""
    try:
        spec = importlib.util.find_spec("examples.stock_backtesting.qmt357.signals")
    except ModuleNotFoundError:
        spec = None
    assert spec is not None, "the independent qmt357 signal module is not implemented"
    from examples.stock_backtesting.qmt357.signals import (
        SignalSettings,
        evaluate_signal,
        market_allows_entry,
    )

    return SignalSettings, evaluate_signal, market_allows_entry


def prices_frame(closes):
    values = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": values, "high": values + 1, "low": values - 1, "close": values})


def rebound_frame():
    frame = prices_frame([100.0, 101.0] * 28 + [101.0, 101.0, 96.0, 103.0])
    frame.loc[58, "open"] = 102.0
    return frame


def test_market_gate_requires_nonnegative_day_and_strict_bullish_averages():
    _, _, gate = api()
    assert gate(list(range(100, 120)))
    assert gate(list(range(100, 119)) + [118])  # A flat day still qualifies.
    assert not gate(list(range(100, 119)) + [117])
    assert not gate([100.0] * 20)
    assert not gate(list(range(100, 119)))
    assert not gate([np.nan] + list(range(101, 120)))


def test_rebound_preserves_source_rsi_macd_bollinger_and_score():
    _, evaluate, _ = api()
    result = evaluate(rebound_frame())
    assert result is not None
    assert (result["eligible"], result["bollinger"], result["rsi"], result["macd"]) == (True, True, True, True)
    assert result["condition_count"] == 3
    # Independent golden numbers from AST-extracted pure source indicators;
    # only compute_rsi/compute_macd were executed, never the QMT account code.
    assert result["rsi_value"] == pytest.approx(54.54545454545455)
    assert result["rsi_change"] == pytest.approx(17.045454545454547)
    assert result["macd_hist"] == pytest.approx(0.13324384283393098)
    assert result["middle_band"] == pytest.approx(100.45)
    assert result["lower_band"] == pytest.approx(97.89739555087667)
    assert result["close"] == 103.0
    assert result["score"] == pytest.approx(0.4851617526892306)


def test_flexible_accepts_two_conditions_and_strict_requires_three():
    settings, evaluate, _ = api()
    frame = rebound_frame()
    frame.loc[58, "open"] = 95.0  # Remove the yesterday-open Bollinger leg.
    result = evaluate(frame)
    assert result is not None and result["eligible"]
    assert (result["bollinger"], result["rsi"], result["macd"]) == (False, True, True)
    assert result["condition_count"] == 2
    assert result["score"] == pytest.approx(0.4366455774203075)
    strict = evaluate(frame, settings(selection_mode="strict"))
    assert strict is not None and not strict["eligible"]


def test_effective_lookback_is_the_last_sixty_rows():
    _, evaluate, _ = api()
    tail = rebound_frame()
    full = pd.concat([prices_frame([np.nan, 9000.0, 1.0] * 30), tail], ignore_index=True)
    assert evaluate(full) == evaluate(tail)


@pytest.mark.parametrize("closes", [[100.0] * 60, list(range(100, 160))])
def test_source_rsi_without_recent_losses_is_invalid_instead_of_one_hundred(closes):
    _, evaluate, _ = api()
    assert evaluate(prices_frame(closes)) is None


def test_valid_but_ineligible_is_distinct_from_invalid_data():
    _, evaluate, _ = api()
    result = evaluate(prices_frame([100.0, 101.0] * 30))
    assert result is not None
    assert not result["eligible"]
    assert result["condition_count"] == 1
    assert result["macd"]
    assert not result["bollinger"] and not result["rsi"]
    assert evaluate(rebound_frame().iloc[-39:]) is None
    bad = rebound_frame()
    bad.loc[30, "close"] = np.nan
    assert evaluate(bad) is None
    assert evaluate(rebound_frame().drop(columns="open")) is None


def test_non_downtrend_prefilter_keeps_either_independent_or_branch():
    _, evaluate, _ = api()
    downtrend = list(range(140, 80, -1))
    assert evaluate(prices_frame(downtrend)) is None
    # Latest close recovers to MA20 tolerance, even though MA20 remains below MA40.
    assert evaluate(prices_frame(downtrend[:-1] + [90])) is not None
    # MA20 remains near MA40, even though the latest close fails its own tolerance.
    assert evaluate(prices_frame([100.0, 101.0] * 29 + [101.0, 90.0])) is not None
