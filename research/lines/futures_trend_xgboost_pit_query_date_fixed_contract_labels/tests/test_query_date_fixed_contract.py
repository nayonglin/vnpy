from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import query_date_fixed_contract as core


def _dates() -> pd.DatetimeIndex:
    return pd.bdate_range("2025-01-01", periods=41)


def _window(product: str = "p.EX") -> pd.DataFrame:
    dates = _dates()
    return pd.DataFrame(
        {
            "query_date": [dates[19]],
            "product_vt_symbol": [product],
            "main_contract_vt": ["P2502.EX"],
            "entry_date": [dates[20]],
            "label_end": [dates[40]],
            "source_partition": ["fixed_label_accepted"],
        }
    )


def _catalog(rows: list[tuple[str, str, pd.Timestamp]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=["vt_symbol", "product_vt_symbol", "expire_date"],
    )


def _liquidity_rows(
    contract: str,
    *,
    volume: float,
    open_interest: float,
    low_indices: tuple[int, ...] = (),
    missing_indices: tuple[int, ...] = (),
) -> list[dict[str, object]]:
    dates = _dates()
    rows: list[dict[str, object]] = []
    for index in range(20):
        if index in missing_indices:
            continue
        rows.append(
            {
                "date": dates[index],
                "contract_vt_symbol": contract,
                "volume": 99.0 if index in low_indices else volume,
                "open_interest": 99.0 if index in low_indices else open_interest,
            }
        )
    return rows


def test_selector_excludes_high_oi_contract_that_expires_before_label_end() -> None:
    dates = _dates()
    catalog = _catalog(
        [
            ("P2502.EX", "p.EX", dates[30]),
            ("P2505.EX", "p.EX", dates[40]),
        ]
    )
    liquidity = pd.DataFrame(
        [
            *_liquidity_rows(
                "P2502.EX", volume=10_000.0, open_interest=20_000.0
            ),
            *_liquidity_rows(
                "P2505.EX", volume=500.0, open_interest=600.0
            ),
        ]
    )

    selected, candidates, rejected = core.select_query_date_contracts(
        _window(), catalog, liquidity, dates
    )

    assert selected["selected_contract_vt"].tolist() == ["P2505.EX"]
    assert selected["capacity_days_20"].tolist() == [20]
    assert rejected.loc[
        rejected["contract_vt_symbol"].eq("P2502.EX"),
        "selection_failure_reason",
    ].tolist() == ["expires_before_label_end"]
    assert candidates["future_selection_rows_used"].eq(0).all()


def test_selector_requires_at_least_eighteen_capacity_days() -> None:
    dates = _dates()
    catalog = _catalog(
        [
            ("P2505.EX", "p.EX", dates[40]),
            ("P2506.EX", "p.EX", dates[40]),
        ]
    )
    liquidity = pd.DataFrame(
        [
            *_liquidity_rows(
                "P2505.EX",
                volume=2_000.0,
                open_interest=3_000.0,
                low_indices=(0, 1, 2),
            ),
            *_liquidity_rows(
                "P2506.EX",
                volume=1_000.0,
                open_interest=1_500.0,
                low_indices=(0, 1),
            ),
        ]
    )

    selected, _, rejected = core.select_query_date_contracts(
        _window(), catalog, liquidity, dates
    )

    assert selected["selected_contract_vt"].tolist() == ["P2506.EX"]
    failed = rejected[rejected["contract_vt_symbol"].eq("P2505.EX")].iloc[0]
    assert failed["capacity_days_20"] == 17
    assert failed["selection_failure_reason"] == "history_capacity_days_below_18"


def test_selector_ignores_future_liquidity_and_uses_stable_tie_breaks() -> None:
    dates = _dates()
    catalog = _catalog(
        [
            ("P2505.EX", "p.EX", dates[40]),
            ("P2506.EX", "p.EX", dates[40] + pd.Timedelta(days=30)),
            ("P2507.EX", "p.EX", dates[40]),
        ]
    )
    liquidity = pd.DataFrame(
        [
            *_liquidity_rows(
                "P2505.EX", volume=300.0, open_interest=300.0
            ),
            *_liquidity_rows(
                "P2506.EX", volume=300.0, open_interest=300.0
            ),
            *_liquidity_rows(
                "P2507.EX", volume=200.0, open_interest=200.0
            ),
            {
                "date": dates[20],
                "contract_vt_symbol": "P2507.EX",
                "volume": 9_000_000.0,
                "open_interest": 9_000_000.0,
            },
        ]
    )

    selected, candidates, _ = core.select_query_date_contracts(
        _window(), catalog, liquidity, dates
    )

    assert selected["selected_contract_vt"].tolist() == ["P2505.EX"]
    assert selected["selection_source_date"].tolist() == [dates[19]]
    assert candidates["future_selection_rows_used"].eq(0).all()


def test_missing_history_sessions_count_against_the_eighteen_day_gate() -> None:
    dates = _dates()
    catalog = _catalog(
        [
            ("P2505.EX", "p.EX", dates[40]),
            ("P2506.EX", "p.EX", dates[40]),
        ]
    )
    liquidity = pd.DataFrame(
        [
            *_liquidity_rows(
                "P2505.EX",
                volume=500.0,
                open_interest=600.0,
                missing_indices=(0, 1, 2),
            ),
            *_liquidity_rows(
                "P2506.EX",
                volume=400.0,
                open_interest=500.0,
                missing_indices=(0, 1),
            ),
        ]
    )

    selected, _, rejected = core.select_query_date_contracts(
        _window(), catalog, liquidity, dates
    )

    assert selected["selected_contract_vt"].tolist() == ["P2506.EX"]
    assert selected["history_observation_days"].tolist() == [18]
    assert selected["history_missing_days"].tolist() == [2]
    failed = rejected[rejected["contract_vt_symbol"].eq("P2505.EX")].iloc[0]
    assert failed["capacity_days_20"] == 17


def test_fixed_contract_legs_hold_one_contract_for_exactly_twenty_returns() -> None:
    dates = _dates()
    selected = pd.DataFrame(
        {
            "query_date": [dates[19]],
            "product_vt_symbol": ["p.EX"],
            "main_contract_vt": ["P2502.EX"],
            "entry_date": [dates[20]],
            "label_end": [dates[40]],
            "source_partition": ["fixed_label_accepted"],
            "selected_contract_vt": ["P2505.EX"],
            "selected_expire_date": [dates[40]],
        }
    )

    legs = core.build_fixed_contract_legs(selected, dates, holding_period=20)

    assert len(legs) == 20
    assert legs["selected_contract_vt"].unique().tolist() == ["P2505.EX"]
    assert legs["leg_index"].tolist() == list(range(1, 21))
    assert legs.iloc[0]["previous_date"] == dates[20]
    assert legs.iloc[0]["return_date"] == dates[21]
    assert legs.iloc[-1]["previous_date"] == dates[39]
    assert legs.iloc[-1]["return_date"] == dates[40]
    assert legs["roll_event"].eq(False).all()
