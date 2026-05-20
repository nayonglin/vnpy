from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

import pandas as pd


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from run_qmt_no_lower_shadow_swing_backtest import (  # noqa: E402
    BacktestConfig,
    MarketBar,
    NoLowerShadowSwingBacktester,
    calculate_position_size,
    first_day_half_exit_volume,
    is_no_lower_shadow_rising,
    is_strict_no_lower_shadow_rising,
    update_trailing_stop_long,
)
from run_qmt_no_lower_shadow_swing_entry_timing_counterfactual import (  # noqa: E402
    EntryTimingCounterfactualBacktester,
    ceil_price_to_tick,
    entry_trigger_price,
)
from run_qmt_no_upper_shadow_short_swing_backtest import (  # noqa: E402
    NoUpperShadowShortSwingBacktester,
    calculate_short_position_size,
    is_strict_no_upper_shadow_falling,
    update_trailing_stop_short,
)
from run_qmt_no_lower_shadow_swing_top_down_weekly_stage008 import (  # noqa: E402
    _build_adjusted_index_for_product,
    last_completed_weekly_state,
)
from run_qmt_no_lower_shadow_swing_top_down_pullback_stage009 import (  # noqa: E402
    _daily_pullback_table,
    _pullback_stop_price,
    _recent_strict_ignition_exists,
)


def _date(text: str) -> pd.Timestamp:
    return pd.Timestamp(text).normalize()


def _bar(date: str, vt_symbol: str, open_: float, high: float, low: float, close: float) -> MarketBar:
    return MarketBar(
        date=_date(date),
        vt_symbol=vt_symbol,
        open=open_,
        high=high,
        low=low,
        close=close,
    )


def _mapping(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": _date(date),
                "continuous_symbol_vt": product,
                "main_contract_vt": contract,
            }
            for date, product, contract in rows
        ]
    )


def _metadata(contracts: list[str]) -> dict[str, object]:
    return {
        "product_symbols": ["rb.SHFE"],
        "sizes": {contract: 10 for contract in contracts},
        "priceticks": {contract: 1.0 for contract in contracts},
        "margin_ratios": {contract: 0.10 for contract in contracts},
        "rates": {contract: 0.0 for contract in contracts},
        "slippages": {contract: 1.0 for contract in contracts},
    }


def _run_fake(
    mapping: pd.DataFrame,
    bars: dict[str, dict[pd.Timestamp, MarketBar]],
    *,
    start: str,
    end: str,
    capital: float = 500_000.0,
    risk_ratio: float = 0.005,
    signal_variant: str = "strict",
) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    contracts = sorted(bars)
    config = BacktestConfig(
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
        capital=capital,
        risk_ratio=risk_ratio,
        signal_variant=signal_variant,
        save_outputs=False,
    )
    tester = NoLowerShadowSwingBacktester(config, mapping, _metadata(contracts), bars)
    stats = tester.run()
    return stats, tester.output_frames()


def _run_fake_entry_timing(
    mapping: pd.DataFrame,
    bars: dict[str, dict[pd.Timestamp, MarketBar]],
    *,
    start: str,
    end: str,
    entry_timing_variant: str,
    stop_mode: str,
    capital: float = 500_000.0,
    risk_ratio: float = 0.005,
) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    contracts = sorted(bars)
    config = BacktestConfig(
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
        capital=capital,
        risk_ratio=risk_ratio,
        signal_variant="strict",
        save_outputs=False,
    )
    tester = EntryTimingCounterfactualBacktester(
        config,
        mapping,
        _metadata(contracts),
        bars,
        entry_timing_variant=entry_timing_variant,
        stop_mode=stop_mode,
    )
    stats = tester.run()
    return stats, tester.output_frames()


def _run_fake_short(
    mapping: pd.DataFrame,
    bars: dict[str, dict[pd.Timestamp, MarketBar]],
    *,
    start: str,
    end: str,
    stop_mode: str,
    capital: float = 500_000.0,
    risk_ratio: float = 0.005,
) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    contracts = sorted(bars)
    config = BacktestConfig(
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
        capital=capital,
        risk_ratio=risk_ratio,
        save_outputs=False,
    )
    tester = NoUpperShadowShortSwingBacktester(
        config,
        mapping,
        _metadata(contracts),
        bars,
        stop_mode=stop_mode,
    )
    stats = tester.run()
    return stats, tester.output_frames()


def test_strict_no_lower_shadow_requires_tick_rounded_open_equals_low_and_rising_close() -> None:
    assert is_strict_no_lower_shadow_rising(_bar("2026-01-01", "rb2605.SHFE", 100, 103, 100, 102), 1.0)
    assert not is_strict_no_lower_shadow_rising(_bar("2026-01-01", "rb2605.SHFE", 101, 103, 100, 102), 1.0)
    assert not is_strict_no_lower_shadow_rising(_bar("2026-01-01", "rb2605.SHFE", 100, 103, 100, 100), 1.0)


def test_strict_no_upper_shadow_requires_tick_rounded_open_equals_high_and_falling_close() -> None:
    assert is_strict_no_upper_shadow_falling(_bar("2026-01-01", "rb2605.SHFE", 103, 103, 100, 101), 1.0)
    assert not is_strict_no_upper_shadow_falling(_bar("2026-01-01", "rb2605.SHFE", 102, 103, 100, 101), 1.0)
    assert not is_strict_no_upper_shadow_falling(_bar("2026-01-01", "rb2605.SHFE", 103, 103, 100, 103), 1.0)


def test_relaxed_no_lower_shadow_variants_are_predeclared_and_conservative() -> None:
    one_tick_shadow = _bar("2026-01-01", "rb2605.SHFE", 101, 105, 100, 104)
    two_tick_shadow_large_body = _bar("2026-01-01", "rb2605.SHFE", 102, 125, 100, 122)
    two_tick_shadow_small_body = _bar("2026-01-01", "rb2605.SHFE", 102, 108, 100, 106)

    assert not is_no_lower_shadow_rising(one_tick_shadow, 1.0, "strict")
    assert is_no_lower_shadow_rising(one_tick_shadow, 1.0, "lower_shadow_1tick")
    assert is_no_lower_shadow_rising(two_tick_shadow_large_body, 1.0, "lower_shadow_2tick_body10")
    assert not is_no_lower_shadow_rising(two_tick_shadow_small_body, 1.0, "lower_shadow_2tick_body10")


def test_pullback_mid_trigger_rounds_up_to_tick_for_long_entry() -> None:
    signal_bar = _bar("2026-01-02", "rb2605.SHFE", 101, 106, 101, 104)

    assert ceil_price_to_tick(102.5, 1.0) == 103.0
    assert entry_trigger_price(signal_bar, 1.0, "pullback_signal2_mid") == 103.0
    assert entry_trigger_price(signal_bar, 1.0, "pullback_signal2_close") == 104.0


def test_weekly_state_uses_only_previous_completed_week() -> None:
    weekly = pd.DataFrame(
        {
            "adjusted_close": [100.0, 110.0],
            "weekly_ma20": [95.0, 100.0],
            "weekly_ma20_prev": [94.0, 95.0],
            "weekly_ma20_slope": [1.0, 5.0],
            "weekly_trend_up": [True, True],
            "weekly_warmup_ready": [True, True],
        },
        index=pd.to_datetime(["2026-01-02", "2026-01-09"]),
    )

    friday_state = last_completed_weekly_state(weekly, product="rb.SHFE", date=_date("2026-01-09"))
    monday_state = last_completed_weekly_state(weekly, product="rb.SHFE", date=_date("2026-01-12"))

    assert friday_state.weekly_state_date == _date("2026-01-02")
    assert monday_state.weekly_state_date == _date("2026-01-09")
    assert friday_state.weekly_trend_up


def test_adjusted_index_neutralizes_roll_day_spread_jump() -> None:
    product = "rb.SHFE"
    dates = [_date("2026-01-01"), _date("2026-01-02"), _date("2026-01-03")]
    contracts = {
        (product, dates[0]): "rb2605.SHFE",
        (product, dates[1]): "rb2610.SHFE",
        (product, dates[2]): "rb2610.SHFE",
    }
    bars = {
        "rb2605.SHFE": {
            dates[0]: _bar("2026-01-01", "rb2605.SHFE", 100, 101, 99, 100),
        },
        "rb2610.SHFE": {
            dates[1]: _bar("2026-01-02", "rb2610.SHFE", 200, 201, 199, 200),
            dates[2]: _bar("2026-01-03", "rb2610.SHFE", 220, 221, 219, 220),
        },
    }

    adjusted = _build_adjusted_index_for_product(
        product=product,
        product_dates=dates,
        contract_by_product_date=contracts,
        bar_cache=bars,
    )

    assert adjusted["adjusted_close"].round(6).tolist() == [100.0, 100.0, 110.0]


def test_pullback_table_requires_ma20_reclaim_after_recent_ma20_pullback() -> None:
    dates = pd.date_range("2026-01-01", periods=25, freq="D")
    closes = [100 + i * 0.5 for i in range(20)] + [108.0, 106.0, 104.0, 105.0, 111.0]
    adjusted = pd.DataFrame({"date": dates, "adjusted_close": closes})

    table = _daily_pullback_table(adjusted)
    signal = table.iloc[-1]

    assert bool(signal["pullback_near_ma20"])
    assert bool(signal["close_above_ma20"])
    assert bool(signal["close_above_previous"])
    assert bool(signal["setup_passed"])


def test_recent_strict_ignition_blocks_repeated_pullback_trigger() -> None:
    product = "rb.SHFE"
    dates = [_date("2026-01-01"), _date("2026-01-02"), _date("2026-01-03"), _date("2026-01-04")]
    contracts = {(product, date): "rb2605.SHFE" for date in dates}
    bars = {
        "rb2605.SHFE": {
            dates[0]: _bar("2026-01-01", "rb2605.SHFE", 100, 104, 100, 103),
            dates[1]: _bar("2026-01-02", "rb2605.SHFE", 102, 103, 101, 101),
            dates[2]: _bar("2026-01-03", "rb2605.SHFE", 103, 106, 103, 105),
            dates[3]: _bar("2026-01-04", "rb2605.SHFE", 105, 107, 105, 106),
        }
    }

    assert _recent_strict_ignition_exists(
        product=product,
        signal_index=3,
        product_dates=dates,
        contract_by_product_date=contracts,
        bar_cache=bars,
        pricetick=1.0,
    )


def test_pullback_stop_uses_lowest_same_contract_low_in_window() -> None:
    product = "rb.SHFE"
    dates = [_date("2026-01-01"), _date("2026-01-02"), _date("2026-01-03"), _date("2026-01-04")]
    contracts = {(product, date): "rb2605.SHFE" for date in dates}
    bars = {
        "rb2605.SHFE": {
            dates[0]: _bar("2026-01-01", "rb2605.SHFE", 100, 105, 99, 104),
            dates[1]: _bar("2026-01-02", "rb2605.SHFE", 104, 106, 101, 103),
            dates[2]: _bar("2026-01-03", "rb2605.SHFE", 103, 105, 97, 104),
            dates[3]: _bar("2026-01-04", "rb2605.SHFE", 104, 108, 104, 107),
        }
    }

    stop, count = _pullback_stop_price(
        product=product,
        signal_index=3,
        product_dates=dates,
        contract="rb2605.SHFE",
        contract_by_product_date=contracts,
        bar_cache=bars,
    )

    assert stop == 97
    assert count == 4


def test_calculate_position_size_uses_half_percent_risk_budget() -> None:
    sizing = calculate_position_size(
        equity=500_000,
        risk_ratio=0.005,
        entry_price=105,
        stop_price=100,
        size=10,
        pricetick=1,
        margin_ratio=0.1,
        active_margin=0,
    )
    assert sizing["risk_amount"] == 2_500
    assert sizing["risk_per_contract"] == 50
    assert sizing["contracts_by_risk"] == 50
    assert sizing["selected_volume"] == 50


def test_calculate_short_position_size_uses_half_percent_risk_budget() -> None:
    sizing = calculate_short_position_size(
        equity=500_000,
        risk_ratio=0.005,
        entry_price=100,
        stop_price=105,
        size=10,
        pricetick=1,
        margin_ratio=0.1,
        active_margin=0,
    )
    assert sizing["risk_amount"] == 2_500
    assert sizing["risk_per_contract"] == 50
    assert sizing["contracts_by_risk"] == 50
    assert sizing["selected_volume"] == 50


def test_first_day_half_exit_and_trailing_stop_are_conservative() -> None:
    assert first_day_half_exit_volume(1) == 0
    assert first_day_half_exit_volume(3) == 1
    assert update_trailing_stop_long(100, 99) == 100
    assert update_trailing_stop_long(100, 101) == 101
    assert update_trailing_stop_short(100, 101) == 100
    assert update_trailing_stop_short(100, 99) == 99


def test_signal_uses_previous_two_days_and_enters_at_third_day_open() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 100, 104, 100, 103),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 103, 106, 103, 105),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 108, 109, 106, 107),
        }
    }
    stats, frames = _run_fake(mapping, bars, start="2026-01-01", end="2026-01-03")
    trades = frames["trades"]
    candidates = frames["candidates"]

    assert stats["opened_candidate_count"] == 1
    assert candidates.iloc[0]["signal_date_1"] == "2026-01-01"
    assert candidates.iloc[0]["signal_date_2"] == "2026-01-02"
    assert trades.iloc[0]["offset"] == "Open"
    assert trades.iloc[0]["price"] == 108
    assert trades.iloc[1]["reason"] == "first_day_half_exit"


def test_short_signal_uses_previous_two_days_and_enters_short_at_third_day_open() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 105, 105, 101, 102),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 102, 102, 98, 99),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 97, 98, 95, 95),
        }
    }
    stats, frames = _run_fake_short(mapping, bars, start="2026-01-01", end="2026-01-03", stop_mode="signal2_high")
    trades = frames["trades"]
    candidates = frames["candidates"]

    assert stats["opened_candidate_count"] == 1
    assert candidates.iloc[0]["signal_date_1"] == "2026-01-01"
    assert candidates.iloc[0]["signal_date_2"] == "2026-01-02"
    assert trades.iloc[0]["direction"] == "Short"
    assert trades.iloc[0]["offset"] == "Open"
    assert trades.iloc[0]["price"] == 97
    assert trades.iloc[1]["reason"] == "first_day_half_exit"
    assert trades.iloc[1]["net_pnl"] > 0


def test_short_same_day_initial_stop_blocks_first_day_half_exit() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 105, 105, 101, 102),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 102, 102, 98, 99),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 97, 103, 95, 96),
        }
    }
    _, frames = _run_fake_short(mapping, bars, start="2026-01-01", end="2026-01-03", stop_mode="signal2_high")
    trades = frames["trades"]

    assert trades.iloc[1]["reason"] == "short_initial_stop"
    assert "first_day_half_exit" not in set(trades["reason"])


def test_short_two_signal_high_stop_mode_widens_stop_anchor() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 105, 105, 101, 102),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 102, 102, 98, 99),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 97, 98, 95, 95),
        }
    }
    _, frames = _run_fake_short(mapping, bars, start="2026-01-01", end="2026-01-03", stop_mode="two_signal_high")

    candidate = frames["candidates"].iloc[0]
    assert candidate["stop_price"] == 105
    assert candidate["stop_mode"] == "two_signal_high"


def test_pullback_entry_skips_when_signal2_close_is_not_touched() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 100, 104, 100, 103),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 103, 106, 103, 105),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 108, 109, 106, 107),
        }
    }
    stats, frames = _run_fake_entry_timing(
        mapping,
        bars,
        start="2026-01-01",
        end="2026-01-03",
        entry_timing_variant="pullback_signal2_close",
        stop_mode="signal2_low",
    )

    assert stats["opened_candidate_count"] == 0
    assert frames["candidates"].iloc[0]["skip_reason"] == "entry_pullback_not_touched"
    assert frames["trades"].empty


def test_pullback_entry_fills_at_signal2_close_and_uses_same_day_stop_conservatively() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 100, 104, 100, 103),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 103, 106, 103, 105),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 108, 109, 102, 107),
        }
    }
    stats, frames = _run_fake_entry_timing(
        mapping,
        bars,
        start="2026-01-01",
        end="2026-01-03",
        entry_timing_variant="pullback_signal2_close",
        stop_mode="signal2_low",
    )
    trades = frames["trades"]

    assert stats["opened_candidate_count"] == 1
    assert trades.iloc[0]["reason"] == "entry_pullback_signal2_close"
    assert trades.iloc[0]["price"] == 105
    assert trades.iloc[1]["reason"] == "long_initial_stop"


def test_two_signal_low_stop_mode_widens_stop_anchor() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 100, 104, 100, 103),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 103, 106, 103, 105),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 108, 109, 106, 107),
        }
    }
    _, frames = _run_fake_entry_timing(
        mapping,
        bars,
        start="2026-01-01",
        end="2026-01-03",
        entry_timing_variant="open",
        stop_mode="two_signal_low",
    )

    candidate = frames["candidates"].iloc[0]
    assert candidate["stop_price"] == 100
    assert candidate["stop_mode"] == "two_signal_low"


def test_relaxed_signal_variant_opens_when_strict_signal_would_skip() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 101, 104, 100, 103),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 104, 107, 103, 106),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 108, 109, 106, 107),
        }
    }
    strict_stats, _ = _run_fake(mapping, bars, start="2026-01-01", end="2026-01-03")
    relaxed_stats, relaxed_frames = _run_fake(
        mapping,
        bars,
        start="2026-01-01",
        end="2026-01-03",
        signal_variant="lower_shadow_1tick",
    )

    assert strict_stats["candidate_count"] == 0
    assert relaxed_stats["opened_candidate_count"] == 1
    assert relaxed_frames["candidates"].iloc[0]["signal_variant"] == "lower_shadow_1tick"


def test_same_day_initial_stop_blocks_first_day_half_exit() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 100, 104, 100, 103),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 103, 106, 103, 105),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 108, 109, 102, 107),
        }
    }
    _, frames = _run_fake(mapping, bars, start="2026-01-01", end="2026-01-03")
    trades = frames["trades"]

    assert trades.iloc[1]["reason"] == "long_initial_stop"
    assert "first_day_half_exit" not in set(trades["reason"])


def test_existing_position_gap_stop_uses_open_price() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-04", "rb.SHFE", "rb2605.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 100, 104, 100, 103),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 103, 106, 103, 105),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 108, 110, 106, 109),
            _date("2026-01-04"): _bar("2026-01-04", "rb2605.SHFE", 105, 106, 104, 105),
        }
    }
    _, frames = _run_fake(mapping, bars, start="2026-01-01", end="2026-01-04")
    trades = frames["trades"]

    assert trades.iloc[-1]["reason"] == "long_gap_stop"
    assert trades.iloc[-1]["price"] == 105


def test_rollover_between_signal_and_entry_is_skipped() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2610.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 100, 104, 100, 103),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 103, 106, 103, 105),
        },
        "rb2610.SHFE": {
            _date("2026-01-03"): _bar("2026-01-03", "rb2610.SHFE", 108, 109, 106, 107),
        },
    }
    _, frames = _run_fake(mapping, bars, start="2026-01-01", end="2026-01-03")

    assert frames["candidates"].iloc[0]["candidate_status"] == "skipped"
    assert frames["candidates"].iloc[0]["skip_reason"] == "rollover_between_signal_and_entry"
    assert frames["trades"].empty


def test_rollover_during_holding_forces_exit_on_old_contract_close() -> None:
    mapping = _mapping(
        [
            ("2026-01-01", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-02", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-03", "rb.SHFE", "rb2605.SHFE"),
            ("2026-01-04", "rb.SHFE", "rb2610.SHFE"),
        ]
    )
    bars = {
        "rb2605.SHFE": {
            _date("2026-01-01"): _bar("2026-01-01", "rb2605.SHFE", 100, 104, 100, 103),
            _date("2026-01-02"): _bar("2026-01-02", "rb2605.SHFE", 103, 106, 103, 105),
            _date("2026-01-03"): _bar("2026-01-03", "rb2605.SHFE", 108, 110, 106, 109),
            _date("2026-01-04"): _bar("2026-01-04", "rb2605.SHFE", 109, 111, 108, 110),
        },
        "rb2610.SHFE": {
            _date("2026-01-04"): _bar("2026-01-04", "rb2610.SHFE", 112, 113, 111, 112),
        },
    }
    _, frames = _run_fake(mapping, bars, start="2026-01-01", end="2026-01-04")
    trades = frames["trades"]

    assert trades.iloc[-1]["reason"] == "rollover_forced_exit"
    assert trades.iloc[-1]["price"] == 110
