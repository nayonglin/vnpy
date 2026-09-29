"""Read-only BB overlays must preserve the frozen entry signal's price basis."""
from copy import deepcopy
import importlib.util
from math import sqrt
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


MODULE = Path(__file__).resolve().parents[1] / "tools/stage015_stock_bollinger.py"
SETTINGS = dict(bb_period=20, bb_std=2, lookback=60, rsi_period=14,
                rsi_oversold=40, macd_fast=5, macd_slow=20, macd_signal=9,
                selection_mode="flexible", min_conditions=2)


@pytest.fixture
def enrich():
    def call(*args, **kwargs):
        assert MODULE.exists(), "BB record enrichment has not been implemented"
        spec = importlib.util.spec_from_file_location("stock_bb", MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.enrich_records(*args, **kwargs)
    return call


def sample(*, bollinger=True, corporate_action=False):
    """Last signal window is 17 tens + 11, 9, 11: mean=10.05, SSE=2.95."""
    dates = pd.bdate_range("2020-01-01", periods=44)
    close = np.array([10.] * 39 + [11., 9., 11., 13., 15.])
    opens = close.copy()
    opens[40] = 11.
    if not bollinger:
        opens[39] = 9.  # Violates the first day's open >= its middle band.
    factors = np.ones(44)
    if corporate_action:
        close[:40] *= 2
        opens[:40] *= 2
        factors[40:] = 2
    panel = pd.DataFrame(dict(date=dates, vt_symbol="600000.SSE", open=opens,
                              high=np.maximum(opens, close) + 1,
                              low=np.minimum(opens, close) - 1, close=close,
                              volume=10000., adj_factor=factors))
    daily = {field: panel[field].tolist() for field in ("open", "high", "low", "close")}
    daily.update(date=dates.strftime("%Y-%m-%d").tolist(),
                 x=(np.arange(44) + .5).tolist())
    records = [dict(meta=dict(vt_symbol="600000.SSE", open_trade_id="stock-0001",
                              entry_signal_date=str(dates[41].date()),
                              entry_date=str(dates[42].date()), price_basis="unadjusted"),
                    daily=daily, weekly=dict(x=[.5], close=[10.]))]
    signals = pd.DataFrame([dict(date=dates[41].isoformat(), vt_symbol="600000.SSE",
                                 raw_close=11., close=11., middle_band=10.05,
                                 lower_band=10.05 - 2 * sqrt(2.95 / 19),
                                 bollinger=bollinger, rsi=True, macd=not bollinger,
                                 condition_count=2, eligible=True)])
    return records, panel, signals


def test_bb20_uses_sample_std_and_leaves_nineteen_unavailable_bands_null(enrich):
    records, panel, signals = sample()
    result, audit = enrich(records, panel, signals, SETTINGS)
    daily = result[0]["daily"]
    assert daily["bb_middle"][:19] == [None] * 19
    assert daily["bb_upper"][19] == 10.
    assert daily["bb_lower"][19] == 10.
    assert daily["bb_middle"][41] == pytest.approx(10.05)
    assert daily["bb_upper"][41] == pytest.approx(10.838068924565556)
    assert daily["bb_lower"][41] == pytest.approx(9.261931075434445)
    assert audit["entries_checked"] == audit["bollinger_true"] == 1
    assert audit["bollinger_false"] == 0


def test_overlay_and_three_day_condition_use_each_day_adjustment_basis(enrich):
    records, panel, signals = sample(corporate_action=True)
    result, _ = enrich(records, panel, signals, SETTINGS)
    daily, signal = result[0]["daily"], result[0]["meta"]["entry_signal"]
    assert daily["bb_middle"][39] == pytest.approx(20.1)
    assert daily["bb_middle"][40] == pytest.approx(10.)
    assert daily["bb_middle"][41] == pytest.approx(10.05)
    assert daily["bb_lower"][41] == pytest.approx(9.261931075434445)
    assert signal["bollinger"] is True


def test_scaling_all_factors_does_not_change_visible_prices_or_bands(enrich):
    records, panel, signals = sample(corporate_action=True)
    original, _ = enrich(records, panel, signals, SETTINGS)
    panel["adj_factor"] *= 731.25
    scaled, _ = enrich(records, panel, signals, SETTINGS)
    for field in ("bb_middle", "bb_upper", "bb_lower"):
        assert scaled[0]["daily"][field][19:] == pytest.approx(original[0]["daily"][field][19:])
    assert scaled[0]["daily"]["close"] == original[0]["daily"]["close"]


def test_future_price_and_factor_changes_cannot_change_past_bands_or_signal(enrich):
    records, panel, signals = sample()
    original, _ = enrich(records, panel, signals, SETTINGS)
    panel.loc[42:, ["open", "high", "low", "close"]] *= 1000
    panel.loc[42:, "adj_factor"] *= 4
    for field in ("open", "high", "low", "close"):
        records[0]["daily"][field] = panel[field].tolist()
    changed, _ = enrich(records, panel, signals, SETTINGS)
    for field in ("bb_middle", "bb_upper", "bb_lower"):
        assert changed[0]["daily"][field][:42] == original[0]["daily"][field][:42]
    assert changed[0]["meta"]["entry_signal"] == original[0]["meta"]["entry_signal"]


def test_warmup_uses_full_panel_before_the_visible_window(enrich):
    records, panel, signals = sample()
    records[0]["daily"] = {key: values[30:] for key, values in records[0]["daily"].items()}
    result, _ = enrich(records, panel, signals, SETTINGS)
    assert result[0]["daily"]["bb_middle"][0] == 10.
    assert result[0]["meta"]["entry_signal"]["x"] == 41.5


def test_signal_marker_uses_signal_close_and_preserves_false_log_flags(enrich):
    records, panel, signals = sample(bollinger=False)
    signals[["bollinger", "rsi", "macd"]] = ["False", "True", "True"]
    result, audit = enrich(records, panel, signals, SETTINGS)
    signal = result[0]["meta"]["entry_signal"]
    assert signal["date"] == "2020-02-27"
    assert result[0]["meta"]["entry_date"] == "2020-02-28"
    assert signal["x"] == 41.5
    assert signal["raw_close"] == 11.
    assert signal["bollinger"] is False
    assert signal["rsi"] is signal["macd"] is True
    assert signal["condition_count"] == 2
    assert audit["bollinger_false"] == 1
    assert audit["condition_combinations"] == {"bollinger=0,rsi=1,macd=1": 1}


def test_enrichment_deepcopies_inputs_and_does_not_load_trading_modules(enrich):
    records, panel, signals = sample()
    original = deepcopy(records)
    original_panel, original_signals = panel.copy(deep=True), signals.copy(deep=True)
    modules, cwd = set(sys.modules), Path.cwd()
    result, _ = enrich(records, panel, signals, SETTINGS)
    result[0]["weekly"]["close"][0] = 999.
    assert records == original
    pd.testing.assert_frame_equal(panel, original_panel)
    pd.testing.assert_frame_equal(signals, original_signals)
    assert Path.cwd() == cwd
    assert not any(name.startswith(("vnpy", "tqsdk", "qmt357"))
                   for name in set(sys.modules) - modules)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "wrong_bollinger", "wrong_count",
                                 "wrong_raw_close", "wrong_close", "wrong_middle", "wrong_lower",
                                 "unknown_boolean", "null_boolean", "ineligible"])
def test_inconsistent_frozen_signal_logs_are_rejected(enrich, kind):
    records, panel, signals = sample()
    if kind == "missing":
        signals = signals.iloc[:0]
    elif kind == "duplicate":
        signals = pd.concat([signals, signals], ignore_index=True)
    elif kind == "wrong_bollinger":
        signals.loc[0, "bollinger"] = False
    elif kind == "wrong_count":
        signals.loc[0, "condition_count"] = 3
    elif kind in ("unknown_boolean", "null_boolean"):
        signals["rsi"] = "perhaps" if kind == "unknown_boolean" else None
    elif kind == "ineligible":
        signals.loc[0, "eligible"] = False
    else:
        field = {"wrong_middle": "middle_band", "wrong_lower": "lower_band"}.get(kind, kind[6:])
        signals.loc[0, field] += 1
    with pytest.raises(ValueError):
        enrich(records, panel, signals, SETTINGS)


@pytest.mark.parametrize("kind", ["missing_signal_day", "missing_entry_day", "missing_factor",
                                 "null_close", "zero_factor", "duplicate_day", "short_history",
                                 "wrong_daily_close", "wrong_basis", "signal_at_entry",
                                 "stale_signal", "duplicate_daily_day", "wrong_daily_length"])
def test_missing_or_ambiguous_price_history_is_rejected(enrich, kind):
    records, panel, signals = sample()
    if kind in ("missing_signal_day", "missing_entry_day"):
        panel = panel.drop(index=41 if kind == "missing_signal_day" else 42)
    elif kind == "missing_factor":
        panel = panel.drop(columns="adj_factor")
    elif kind == "null_close":
        panel.loc[25, "close"] = np.nan
    elif kind == "zero_factor":
        panel.loc[25, "adj_factor"] = 0
    elif kind == "duplicate_day":
        panel = pd.concat([panel, panel.iloc[[10]]], ignore_index=True)
    elif kind == "short_history":
        panel = panel.iloc[10:]
        records[0]["daily"] = {key: values[10:] for key, values in records[0]["daily"].items()}
    elif kind == "wrong_daily_close":
        records[0]["daily"]["close"][25] += 1
    elif kind == "wrong_basis":
        records[0]["meta"]["price_basis"] = "forward_adjusted"
    elif kind == "signal_at_entry":
        records[0]["meta"]["entry_signal_date"] = records[0]["meta"]["entry_date"]
    elif kind == "stale_signal":
        records[0]["meta"]["entry_signal_date"] = str(panel.date.iloc[40].date())
        signals.loc[0, "date"] = panel.date.iloc[40].isoformat()
    elif kind == "duplicate_daily_day":
        records[0]["daily"]["date"][10] = records[0]["daily"]["date"][9]
    else:
        records[0]["daily"]["x"].pop()
    with pytest.raises(ValueError):
        enrich(records, panel, signals, SETTINGS)


@pytest.mark.parametrize("key,value", [("bb_period", 19), ("bb_std", 2.1), ("lookback", 20)])
def test_changed_frozen_bollinger_contract_is_rejected(enrich, key, value):
    with pytest.raises(ValueError):
        enrich(*sample(), {**SETTINGS, key: value})


@pytest.mark.parametrize("case,bollinger,middle,squared_deviations", [
    ("first_close_below", False, 9.95, 2.95),
    ("second_open_below", False, 10.05, 2.95),
    ("second_close_equal", False, 10.05, .95),
    ("last_close_equal", False, 10., 2.),
    ("first_open_close_equal", True, 10., 2.),
    ("second_open_equal", True, 10.05, 2.95),
])
def test_original_three_day_strict_and_inclusive_boundaries(
        enrich, case, bollinger, middle, squared_deviations):
    records, panel, signals = sample()
    if case == "first_close_below":
        panel.loc[39, "close"] = 9.
    elif case == "second_open_below":
        panel.loc[40, "open"] = 9.
    elif case == "second_close_equal":
        panel.loc[[39, 40], "close"] = 10.
    elif case == "last_close_equal":
        panel.loc[41, "close"] = 10.
    elif case == "first_open_close_equal":
        panel.loc[39, ["open", "close"]] = 10.
    else:
        panel.loc[40, "open"] = 10.
    for field in ("open", "close"):
        records[0]["daily"][field] = panel[field].tolist()
    signals.loc[0, ["bollinger", "macd"]] = [bollinger, not bollinger]
    signals.loc[0, ["raw_close", "close"]] = 10. if case == "last_close_equal" else 11.
    signals.loc[0, "middle_band"] = middle
    signals.loc[0, "lower_band"] = middle - 2 * sqrt(squared_deviations / 19)
    result, _ = enrich(records, panel, signals, SETTINGS)
    assert result[0]["meta"]["entry_signal"]["bollinger"] is bollinger


def test_duplicate_entry_records_cannot_double_count_a_frozen_signal(enrich):
    records, panel, signals = sample()
    records.append(deepcopy(records[0]))
    with pytest.raises(ValueError):
        enrich(records, panel, signals, SETTINGS)


def test_entry_flags_must_satisfy_the_frozen_selection_contract(enrich):
    records, panel, signals = sample(bollinger=False)
    signals.loc[0, "macd"] = False
    signals.loc[0, "condition_count"] = 1
    with pytest.raises(ValueError):
        enrich(records, panel, signals, SETTINGS)
