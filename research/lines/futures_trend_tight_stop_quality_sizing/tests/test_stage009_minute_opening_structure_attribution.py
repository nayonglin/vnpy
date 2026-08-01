from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage009_minute_opening_structure_attribution as s009


def _session(
    *,
    direction: str = "long",
    minute6_open: float | None = None,
    same_bar_both: bool = False,
) -> pd.DataFrame:
    times = pd.date_range("2022-01-03 21:00:00", periods=12, freq="min")
    if direction == "long":
        opens = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111]
        closes = [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112]
        highs = [102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113]
        lows = [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
    else:
        opens = [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89]
        closes = [99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88]
        highs = [101, 100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90]
        lows = [98, 97, 96, 95, 94, 93, 92, 91, 90, 89, 88, 87]
    if minute6_open is not None:
        opens[5] = minute6_open
    if same_bar_both:
        if direction == "long":
            lows[5] = 97
            highs[5] = 114
        else:
            highs[5] = 103
            lows[5] = 86
    return pd.DataFrame(
        {
            "vt_symbol": "rb2205.SHFE",
            "bar_date": pd.Timestamp("2022-01-04"),
            "bar_datetime": times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": 100.0,
        }
    )


def _event(direction: str = "long") -> dict[str, object]:
    return {
        "open_trade_id": "T1",
        "vt_symbol": "rb2205.SHFE",
        "product": "rb.SHFE",
        "direction": direction,
        "entry_date": pd.Timestamp("2022-01-04"),
        "planned_entry_price": 100.0,
        "actual_entry_price": 100.0,
        "planned_stop_distance": 20.0,
        "baseline_realized_pnl": 1_000.0,
        "baseline_r_multiple": 1.5,
        "sample_segment": "discovery",
    }


def test_long_features_use_first_five_completed_bars_and_minute6_open() -> None:
    result = s009.compute_minute_opening_event(
        _event("long"),
        _session(direction="long", minute6_open=107.0),
        pricetick=1.0,
    )

    assert result["feature_bar_count"] == 5
    assert pd.Timestamp(result["feature_last_bar_time"]) == pd.Timestamp("2022-01-03 21:04:00")
    assert pd.Timestamp(result["decision_time"]) == pd.Timestamp("2022-01-03 21:05:00")
    assert pd.Timestamp(result["counterfactual_entry_time"]) == pd.Timestamp("2022-01-03 21:05:00")
    assert result["counterfactual_entry_price"] == pytest.approx(107.0)
    assert result["structural_stop_price"] == pytest.approx(98.0)
    assert result["micro_stop_distance"] == pytest.approx(9.0)
    assert result["micro_stop_original_stop_ratio"] == pytest.approx(0.45)
    assert result["or5_close_location"] == pytest.approx(6.0 / 7.0)
    assert result["minute6_open_beyond_planned_entry"] == 1
    assert result["or5_all_closes_directional_side"] == 1


def test_short_features_are_direction_symmetric() -> None:
    result = s009.compute_minute_opening_event(
        _event("short"),
        _session(direction="short", minute6_open=93.0),
        pricetick=1.0,
    )

    assert result["counterfactual_entry_price"] == pytest.approx(93.0)
    assert result["structural_stop_price"] == pytest.approx(102.0)
    assert result["micro_stop_distance"] == pytest.approx(9.0)
    assert result["micro_stop_original_stop_ratio"] == pytest.approx(0.45)
    assert result["or5_close_location"] == pytest.approx(6.0 / 7.0)
    assert result["minute6_open_beyond_planned_entry"] == 1
    assert result["or5_all_closes_directional_side"] == 1


@pytest.mark.parametrize("direction", ["long", "short"])
def test_same_bar_stop_and_target_is_conservatively_stop_first(direction: str) -> None:
    result = s009.compute_minute_opening_event(
        _event(direction),
        _session(direction=direction, same_bar_both=True),
        pricetick=1.0,
    )

    assert result["micro_first_touch_1r"] == "stop_first"
    assert result["micro_first_touch_1r_bar_index"] == 0


def test_missing_bar_inside_first_six_minutes_fails_closed() -> None:
    session = _session().drop(index=2).reset_index(drop=True)

    with pytest.raises(ValueError, match="first six minute bars are not contiguous"):
        s009.compute_minute_opening_event(_event(), session, pricetick=1.0)


def test_future_feature_seal_ignores_all_outcome_columns() -> None:
    frame = pd.DataFrame(
        {
            "open_trade_id": ["D", "V"],
            "vt_symbol": ["rb2205.SHFE", "MA605.CZCE"],
            "direction": ["long", "short"],
            "entry_date": pd.to_datetime(["2022-01-04", "2023-01-04"]),
            "sample_segment": ["discovery", "validation"],
            "or5_close_location": [0.8, 0.9],
            "micro_stop_original_stop_ratio": [0.4, 0.5],
            "baseline_realized_pnl": [10.0, 20.0],
            "baseline_r_multiple": [1.0, 2.0],
            "micro_first_touch_1r": ["target_first", "stop_first"],
            "return_60m_micro_r": [1.2, -0.7],
        }
    )
    _, seal = s009.partition_minute_outputs(frame)
    mutated = frame.copy()
    mutated.loc[1, "baseline_realized_pnl"] = -1e9
    mutated.loc[1, "baseline_r_multiple"] = -1e6
    mutated.loc[1, "micro_first_touch_1r"] = "target_first"
    mutated.loc[1, "return_60m_micro_r"] = 1e6
    _, mutated_seal = s009.partition_minute_outputs(mutated)

    assert seal["feature_only_sha256"] == mutated_seal["feature_only_sha256"]
    assert seal["true_oos_claim"] is False
    assert seal["future_row_data_exported"] is False


def test_wilson_interval_is_bounded_and_handles_empty_sample() -> None:
    low, high = s009.wilson_interval(7, 10)
    assert 0.0 <= low < 0.7 < high <= 1.0
    empty_low, empty_high = s009.wilson_interval(0, 0)
    assert np.isnan(empty_low)
    assert np.isnan(empty_high)


def test_effective_pricetick_uses_historical_lc_rule_at_trade_date_boundary() -> None:
    assert s009.effective_pricetick("lc2401.GFEX", "2024-12-17", 20.0) == (50.0, "gfex_lc_pre_2024_12_18")
    assert s009.effective_pricetick("lc2501.GFEX", "2024-12-18", 20.0) == (20.0, "current_metadata")
    assert s009.effective_pricetick("rb2501.SHFE", "2024-12-17", 1.0) == (1.0, "current_metadata")


def test_compute_all_events_applies_historical_lc_tick_to_structural_stop() -> None:
    event = _event("long")
    event["vt_symbol"] = "lc2401.GFEX"
    event["product"] = "lc.GFEX"
    event["entry_date"] = pd.Timestamp("2023-08-01")
    session = _session(direction="long")
    session["vt_symbol"] = "lc2401.GFEX"
    session["bar_date"] = pd.Timestamp("2023-08-01")

    computed, coverage = s009._compute_all_events(
        pd.DataFrame([event]),
        session,
        {"lc2401.GFEX": 20.0},
    )

    assert computed.iloc[0]["effective_pricetick"] == pytest.approx(50.0)
    assert computed.iloc[0]["pricetick_rule"] == "gfex_lc_pre_2024_12_18"
    assert computed.iloc[0]["structural_stop_price"] == pytest.approx(49.0)
    assert coverage.iloc[0]["effective_pricetick"] == pytest.approx(50.0)


def _summary_events() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    outcomes = [
        ("target_first", "target_first"),
        ("target_first", "stop_first"),
        ("stop_first", "stop_first"),
        ("no_touch", "no_touch"),
    ]
    for year in (2020, 2021, 2022):
        for index, (touch1, touch2) in enumerate(outcomes):
            row: dict[str, object] = {
                "open_trade_id": f"{year}-{index}",
                "product": "rb.SHFE" if index % 2 == 0 else "MA.CZCE",
                "direction": "long" if index % 2 == 0 else "short",
                "entry_date": pd.Timestamp(f"{year}-06-01"),
                "sample_segment": "discovery",
                "micro_first_touch_1r": touch1,
                "micro_first_touch_2r": touch2,
                "baseline_realized_pnl": float(index),
                "baseline_r_multiple": float(index) / 10.0,
                "return_5m_micro_r": 0.1,
                "return_15m_micro_r": 0.2,
                "return_60m_micro_r": 0.3,
                "minute6_open_beyond_planned_entry": 1,
                "micro_stop_original_stop_ratio": 0.5 + 0.1 * index,
            }
            for feature_index, feature in enumerate(s009.CONTINUOUS_FEATURES):
                row[feature] = float(index) * 10.0 + (year - 2020) + feature_index / 100.0
            row["micro_stop_original_stop_ratio"] = 0.5 + 0.05 * index + 0.01 * (year - 2020)
            rows.append(row)
    return pd.DataFrame(rows)


def test_group_summary_reports_conservative_2r_outcomes_and_wilson_interval() -> None:
    summary = s009._group_summary(_summary_events())

    assert summary["resolved_2r_count"] == 9
    assert summary["target_first_2r_count"] == 3
    assert summary["stop_first_2r_count"] == 6
    assert summary["no_touch_2r_count"] == 3
    assert summary["target_first_2r_rate"] == pytest.approx(1.0 / 3.0)
    assert summary["target_first_2r_wilson_low"] < 1.0 / 3.0 < summary["target_first_2r_wilson_high"]


def test_discovery_yearly_covers_all_fixed_structure_and_every_feature_bin() -> None:
    events = _summary_events()
    bins = s009.discovery_feature_bins(events)
    yearly = s009.discovery_yearly(events)

    assert set(yearly["scope_type"]) == {"all_discovery", "fixed_structure", "feature_bin"}
    assert set(yearly.loc[yearly["scope_type"].eq("all_discovery"), "entry_year"]) == {2020, 2021, 2022}
    assert set(yearly.loc[yearly["scope_type"].eq("fixed_structure"), "entry_year"]) == {2020, 2021, 2022}
    expected_bins = set(zip(bins["feature"], bins["feature_bin"], strict=False))
    yearly_bins = set(
        zip(
            yearly.loc[yearly["scope_type"].eq("feature_bin"), "feature"],
            yearly.loc[yearly["scope_type"].eq("feature_bin"), "feature_bin"],
            strict=False,
        )
    )
    assert yearly_bins == expected_bins
    assert yearly.loc[yearly["scope_type"].eq("feature_bin")].groupby(["feature", "feature_bin"])[
        "entry_year"
    ].nunique().eq(3).all()
