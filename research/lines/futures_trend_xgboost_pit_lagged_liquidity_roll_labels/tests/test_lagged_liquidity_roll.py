from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import lagged_liquidity_roll as core


def _catalog(rows: list[tuple[str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=["vt_symbol", "product_vt_symbol", "expire_date"],
    )


def _liquidity(
    rows: list[tuple[str, str, float, float]],
) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=["date", "contract_vt_symbol", "volume", "open_interest"],
    )


def test_mapping_uses_exact_previous_session_and_ignores_execution_day_spike() -> None:
    dates = pd.to_datetime(
        ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
    )
    catalog = _catalog(
        [
            ("P2505.EX", "p.EX", "2025-05-30"),
            ("P2509.EX", "p.EX", "2025-09-30"),
        ]
    )
    liquidity = _liquidity(
        [
            ("2025-01-03", "P2505.EX", 1_000, 2_000),
            ("2025-01-03", "P2509.EX", 500, 600),
            ("2025-01-06", "P2505.EX", 100, 100),
            ("2025-01-06", "P2509.EX", 9_000_000, 9_000_000),
        ]
    )

    mapping, candidates = core.build_lagged_contract_map(
        [dates[2]], ["p.EX"], catalog, liquidity, dates
    )

    assert mapping["selection_date"].tolist() == [dates[1]]
    assert mapping["return_date"].tolist() == [dates[3]]
    assert mapping["selected_contract_vt"].tolist() == ["P2505.EX"]
    assert mapping["mapping_valid"].tolist() == [True]
    assert candidates["selection_date"].eq(dates[1]).all()
    assert candidates["future_or_same_day_source"].eq(False).all()


def test_mapping_enforces_capacity_expiry_and_stable_tie_breaks() -> None:
    dates = pd.to_datetime(
        ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
    )
    catalog = _catalog(
        [
            ("P2501.EX", "p.EX", "2025-01-03"),
            ("P2505.EX", "p.EX", "2025-05-30"),
            ("P2506.EX", "p.EX", "2025-06-30"),
            ("P2507.EX", "p.EX", "2025-06-30"),
        ]
    )
    liquidity = _liquidity(
        [
            ("2025-01-03", "P2501.EX", 10_000, 20_000),
            ("2025-01-03", "P2505.EX", 99, 500),
            ("2025-01-03", "P2506.EX", 200, 300),
            ("2025-01-03", "P2507.EX", 200, 300),
        ]
    )

    mapping, candidates = core.build_lagged_contract_map(
        [dates[2]], ["p.EX"], catalog, liquidity, dates
    )

    assert mapping["selected_contract_vt"].tolist() == ["P2506.EX"]
    by_contract = candidates.set_index("contract_vt_symbol")
    assert not bool(by_contract.loc["P2501.EX", "expiry_valid"])
    assert not bool(by_contract.loc["P2505.EX", "capacity_valid"])
    assert int(by_contract.loc["P2506.EX", "raw_selection_rank"]) == 1
    assert int(by_contract.loc["P2507.EX", "raw_selection_rank"]) == 2


def test_mapping_never_rolls_back_to_an_earlier_expiry() -> None:
    dates = pd.to_datetime(
        [
            "2025-01-02",
            "2025-01-03",
            "2025-01-06",
            "2025-01-07",
            "2025-01-08",
        ]
    )
    catalog = _catalog(
        [
            ("P2505.EX", "p.EX", "2025-05-30"),
            ("P2509.EX", "p.EX", "2025-09-30"),
        ]
    )
    liquidity = _liquidity(
        [
            ("2025-01-03", "P2505.EX", 500, 600),
            ("2025-01-03", "P2509.EX", 1_000, 2_000),
            ("2025-01-06", "P2505.EX", 9_000, 10_000),
            ("2025-01-06", "P2509.EX", 200, 300),
        ]
    )

    mapping, candidates = core.build_lagged_contract_map(
        [dates[2], dates[3]], ["p.EX"], catalog, liquidity, dates
    )

    assert mapping["selected_contract_vt"].tolist() == [
        "P2509.EX",
        "P2509.EX",
    ]
    assert mapping["selected_expire_date"].is_monotonic_increasing
    second_day_near = candidates[
        candidates["execution_date"].eq(dates[3])
        & candidates["contract_vt_symbol"].eq("P2505.EX")
    ].iloc[0]
    assert bool(second_day_near["raw_selection_eligible"])
    assert not bool(second_day_near["monotone_selection_eligible"])
    assert second_day_near["selection_failure_reason"] == "earlier_than_prior_expiry"


def test_mapping_fails_explicitly_instead_of_rolling_back() -> None:
    dates = pd.to_datetime(
        [
            "2025-01-02",
            "2025-01-03",
            "2025-01-06",
            "2025-01-07",
            "2025-01-08",
        ]
    )
    catalog = _catalog(
        [
            ("P2505.EX", "p.EX", "2025-05-30"),
            ("P2509.EX", "p.EX", "2025-09-30"),
        ]
    )
    liquidity = _liquidity(
        [
            ("2025-01-03", "P2505.EX", 500, 600),
            ("2025-01-03", "P2509.EX", 1_000, 2_000),
            ("2025-01-06", "P2505.EX", 9_000, 10_000),
            ("2025-01-06", "P2509.EX", 99, 300),
        ]
    )

    mapping, _ = core.build_lagged_contract_map(
        [dates[2], dates[3]], ["p.EX"], catalog, liquidity, dates
    )

    failed = mapping.iloc[1]
    assert not bool(failed["mapping_valid"])
    assert pd.isna(failed["selected_contract_vt"])
    assert failed["mapping_failure_reason"] == "no_eligible_same_or_later_contract"
    assert failed["prior_selected_expire_date"] == pd.Timestamp("2025-09-30")


def test_dynamic_legs_join_daily_mapping_and_identify_rolls() -> None:
    dates = pd.to_datetime(
        [
            "2025-01-02",
            "2025-01-03",
            "2025-01-06",
            "2025-01-07",
            "2025-01-08",
        ]
    )
    windows = pd.DataFrame(
        {
            "query_date": [dates[0]],
            "product_vt_symbol": ["p.EX"],
            "main_contract_vt": ["P2501.EX"],
            "entry_date": [dates[1]],
            "label_end": [dates[3]],
            "source_partition": ["fixed_label_accepted"],
        }
    )
    mapping = pd.DataFrame(
        {
            "execution_date": [dates[1], dates[2]],
            "return_date": [dates[2], dates[3]],
            "selection_date": [dates[0], dates[1]],
            "product_vt_symbol": ["p.EX", "p.EX"],
            "selected_contract_vt": ["P2505.EX", "P2509.EX"],
            "selected_expire_date": ["2025-05-30", "2025-09-30"],
            "selection_volume": [500.0, 600.0],
            "selection_open_interest": [700.0, 800.0],
            "mapping_valid": [True, True],
            "mapping_failure_reason": ["", ""],
        }
    )

    legs = core.build_dynamic_legs(
        windows, mapping, dates, holding_period=2
    )

    assert legs["leg_index"].tolist() == [1, 2]
    assert legs["previous_date"].tolist() == [dates[1], dates[2]]
    assert legs["return_date"].tolist() == [dates[2], dates[3]]
    assert legs["selection_date"].tolist() == [dates[0], dates[1]]
    assert legs["selection_after_query"].tolist() == [False, True]
    assert legs["roll_event"].tolist() == [False, True]
    assert legs["leg_valid"].all()


def test_dynamic_legs_fail_when_mapping_is_not_strictly_lagged() -> None:
    dates = pd.to_datetime(
        ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
    )
    windows = pd.DataFrame(
        {
            "query_date": [dates[0]],
            "product_vt_symbol": ["p.EX"],
            "main_contract_vt": ["P2501.EX"],
            "entry_date": [dates[1]],
            "label_end": [dates[2]],
            "source_partition": ["fixed_label_accepted"],
        }
    )
    mapping = pd.DataFrame(
        {
            "execution_date": [dates[1]],
            "return_date": [dates[2]],
            "selection_date": [dates[1]],
            "product_vt_symbol": ["p.EX"],
            "selected_contract_vt": ["P2505.EX"],
            "selected_expire_date": ["2025-05-30"],
            "selection_volume": [500.0],
            "selection_open_interest": [700.0],
            "mapping_valid": [True],
            "mapping_failure_reason": [""],
        }
    )

    legs = core.build_dynamic_legs(
        windows, mapping, dates, holding_period=1
    )

    assert not bool(legs.iloc[0]["leg_valid"])
    assert bool(legs.iloc[0]["same_day_or_future_selection_violation"])
    assert legs.iloc[0]["leg_failure_reason"] == "selection_not_previous_session"
