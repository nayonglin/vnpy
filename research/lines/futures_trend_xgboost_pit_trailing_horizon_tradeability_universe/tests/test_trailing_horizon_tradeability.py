from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import trailing_horizon_tradeability as core


def _window(dates: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "query_date": [dates[5]],
            "product_vt_symbol": ["p.EX"],
            "main_contract_vt": ["P2501.EX"],
            "entry_date": [dates[6]],
            "label_end": [dates[8]],
            "source_partition": ["fixed_label_accepted"],
            "path_valid": [True],
        }
    )


def _qualification_fixture(
    dates: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    windows = _window(dates)
    historical_legs = pd.DataFrame(
        {
            "query_date": [dates[5], dates[5]],
            "product_vt_symbol": ["p.EX", "p.EX"],
            "leg_index": [1, 2],
            "selection_date": [dates[2], dates[3]],
            "previous_date": [dates[3], dates[4]],
            "return_date": [dates[4], dates[5]],
            "selected_contract_vt": ["P2505.EX", "P2509.EX"],
            "roll_event": [False, True],
            "mapping_valid": [True, True],
            "expiry_valid": [True, True],
            "exact_previous_session": [True, True],
            "leg_valid": [True, True],
        }
    )
    historical_audit = historical_legs.assign(
        price_observation_valid=True,
        price_observation_failure_reason="",
    )
    historical_events = pd.DataFrame(
        {
            "query_date": [dates[5]] * 4,
            "product_vt_symbol": ["p.EX"] * 4,
            "event_role": ["entry", "roll_close", "roll_open", "exit"],
            "event_date": [dates[3], dates[4], dates[4], dates[5]],
            "capacity_valid": [True, True, True, True],
            "capacity_failure_reason": ["", "", "", ""],
        }
    )
    future_leg1_mapping = pd.DataFrame(
        {
            "execution_date": [dates[6]],
            "return_date": [dates[7]],
            "selection_date": [dates[5]],
            "product_vt_symbol": ["p.EX"],
            "selected_contract_vt": ["P2509.EX"],
            "selected_expire_date": [dates[-1] + pd.Timedelta(days=30)],
            "mapping_valid": [True],
            "mapping_failure_reason": [""],
        }
    )
    return (
        windows,
        historical_legs,
        historical_audit,
        historical_events,
        future_leg1_mapping,
    )


def test_trailing_window_has_exact_mirrored_horizon() -> None:
    dates = pd.bdate_range("2025-01-01", periods=10)

    trailing = core.build_trailing_windows(
        _window(dates), dates, lookback=2
    )

    assert trailing["entry_date"].tolist() == [dates[3]]
    assert trailing["label_end"].tolist() == [dates[5]]
    assert trailing["future_entry_date"].tolist() == [dates[6]]
    assert trailing["future_label_end"].tolist() == [dates[8]]
    assert trailing["history_return_leg_count"].tolist() == [2]


def test_trailing_window_rejects_calendar_without_prior_selection_session() -> None:
    dates = pd.bdate_range("2025-01-01", periods=6)
    windows = pd.DataFrame(
        {
            "query_date": [dates[2]],
            "product_vt_symbol": ["p.EX"],
            "main_contract_vt": ["P2501.EX"],
            "entry_date": [dates[3]],
            "label_end": [dates[5]],
            "source_partition": ["fixed_label_accepted"],
        }
    )

    with pytest.raises(core.TrailingUniverseError, match="history_calendar_insufficient"):
        core.build_trailing_windows(windows, dates, lookback=2)


def test_complete_historical_path_and_query_date_leg1_enter_universe() -> None:
    dates = pd.bdate_range("2025-01-01", periods=10)
    frames = _qualification_fixture(dates)

    qualification, selected = core.build_universe_qualification(
        *frames, lookback=2
    )

    row = qualification.iloc[0]
    assert bool(row["historical_tradeability_valid"])
    assert row["historical_observation_max_date"] == dates[5]
    assert bool(row["future_leg1_mapping_valid"])
    assert bool(row["universe_eligible"])
    assert row["universe_rejection_reason"] == ""
    assert len(selected) == 1


def test_historical_roll_close_capacity_failure_rejects_candidate() -> None:
    dates = pd.bdate_range("2025-01-01", periods=10)
    frames = list(_qualification_fixture(dates))
    events = frames[3].copy()
    roll_close = events["event_role"].eq("roll_close")
    events.loc[roll_close, "capacity_valid"] = False
    events.loc[roll_close, "capacity_failure_reason"] = (
        "volume_below_one_lot_capacity"
    )
    frames[3] = events

    qualification, selected = core.build_universe_qualification(
        *frames, lookback=2
    )

    assert not bool(qualification.iloc[0]["historical_tradeability_valid"])
    assert qualification.iloc[0]["universe_rejection_reason"] == (
        "historical_event_capacity_invalid"
    )
    assert selected.empty


def test_future_leg1_must_be_selected_on_query_date() -> None:
    dates = pd.bdate_range("2025-01-01", periods=10)
    frames = list(_qualification_fixture(dates))
    future = frames[4].copy()
    future["selection_date"] = future["execution_date"]
    frames[4] = future

    qualification, selected = core.build_universe_qualification(
        *frames, lookback=2
    )

    row = qualification.iloc[0]
    assert bool(row["future_leg1_same_day_or_future_violation"])
    assert not bool(row["future_leg1_mapping_valid"])
    assert row["universe_rejection_reason"] == "future_leg1_not_query_date_selected"
    assert selected.empty


def test_historical_observation_after_query_date_is_rejected() -> None:
    dates = pd.bdate_range("2025-01-01", periods=10)
    frames = list(_qualification_fixture(dates))
    events = frames[3].copy()
    events.loc[events["event_role"].eq("exit"), "event_date"] = dates[6]
    frames[3] = events

    qualification, selected = core.build_universe_qualification(
        *frames, lookback=2
    )

    row = qualification.iloc[0]
    assert bool(row["historical_future_observation_violation"])
    assert row["universe_rejection_reason"] == "historical_observation_after_query"
    assert selected.empty
