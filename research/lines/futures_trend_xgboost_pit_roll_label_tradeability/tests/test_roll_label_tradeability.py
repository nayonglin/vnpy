from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import roll_label_tradeability as core


def test_zero_return_volume_fails_price_observation_quality() -> None:
    legs = pd.DataFrame(
        {
            "query_date": ["2025-01-02"],
            "product_vt_symbol": ["p.EX"],
            "leg_index": [1],
            "previous_date": ["2025-01-03"],
            "return_date": ["2025-01-06"],
            "selected_contract_vt": ["P2505.EX"],
        }
    )
    liquidity = pd.DataFrame(
        {
            "date": ["2025-01-03", "2025-01-06"],
            "contract_vt_symbol": ["P2505.EX", "P2505.EX"],
            "volume": [10.0, 0.0],
            "open_interest": [20.0, 20.0],
        }
    )

    result = core.audit_leg_endpoints(legs, liquidity)

    row = result.iloc[0]
    assert bool(row["previous_price_quality"])
    assert not bool(row["return_price_quality"])
    assert not bool(row["price_observation_valid"])
    assert row["price_observation_failure_reason"] == (
        "return_volume_nonpositive"
    )


def test_single_contract_path_creates_only_entry_and_exit_events() -> None:
    legs = pd.DataFrame(
        {
            "query_date": ["2025-01-02"] * 3,
            "product_vt_symbol": ["p.EX"] * 3,
            "leg_index": [1, 2, 3],
            "previous_date": ["2025-01-03", "2025-01-06", "2025-01-07"],
            "return_date": ["2025-01-06", "2025-01-07", "2025-01-08"],
            "selected_contract_vt": ["P2505.EX"] * 3,
        }
    )
    liquidity = pd.DataFrame(
        {
            "date": ["2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08"],
            "contract_vt_symbol": ["P2505.EX"] * 4,
            "volume": [150.0] * 4,
            "open_interest": [200.0] * 4,
        }
    )
    audited = core.audit_leg_endpoints(legs, liquidity)

    events = core.build_execution_events(audited)

    assert events["event_role"].tolist() == ["entry", "exit"]
    assert events["event_date"].tolist() == [
        pd.Timestamp("2025-01-03"),
        pd.Timestamp("2025-01-08"),
    ]
    assert events["contract_vt_symbol"].tolist() == ["P2505.EX", "P2505.EX"]


def test_roll_boundary_creates_close_and_open_for_distinct_contracts() -> None:
    legs = pd.DataFrame(
        {
            "query_date": ["2025-01-02", "2025-01-02"],
            "product_vt_symbol": ["p.EX", "p.EX"],
            "leg_index": [1, 2],
            "previous_date": ["2025-01-03", "2025-01-06"],
            "return_date": ["2025-01-06", "2025-01-07"],
            "selected_contract_vt": ["P2501.EX", "P2505.EX"],
        }
    )
    liquidity = pd.DataFrame(
        {
            "date": [
                "2025-01-03",
                "2025-01-06",
                "2025-01-06",
                "2025-01-07",
            ],
            "contract_vt_symbol": [
                "P2501.EX",
                "P2501.EX",
                "P2505.EX",
                "P2505.EX",
            ],
            "volume": [200.0, 180.0, 160.0, 150.0],
            "open_interest": [300.0, 280.0, 260.0, 250.0],
        }
    )
    audited = core.audit_leg_endpoints(legs, liquidity)

    events = core.build_execution_events(audited)

    assert events["event_role"].tolist() == [
        "entry",
        "roll_close",
        "roll_open",
        "exit",
    ]
    assert events["contract_vt_symbol"].tolist() == [
        "P2501.EX",
        "P2501.EX",
        "P2505.EX",
        "P2505.EX",
    ]
    assert events["event_date"].tolist() == [
        pd.Timestamp("2025-01-03"),
        pd.Timestamp("2025-01-06"),
        pd.Timestamp("2025-01-06"),
        pd.Timestamp("2025-01-07"),
    ]
    assert events["volume"].tolist() == [200.0, 180.0, 160.0, 150.0]


def test_one_lot_capacity_passes_at_100_and_fails_at_99() -> None:
    events = pd.DataFrame(
        {
            "query_date": ["2025-01-02", "2025-01-02"],
            "product_vt_symbol": ["p.EX", "q.EX"],
            "event_role": ["entry", "entry"],
            "event_date": ["2025-01-03", "2025-01-03"],
            "contract_vt_symbol": ["P2505.EX", "Q2505.EX"],
            "volume": [100.0, 99.0],
            "open_interest": [100.0, 99.0],
        }
    )

    result = core.assess_event_capacity(events)

    assert result["order_volume_share_pct"].tolist() == [1.0, 100.0 / 99.0]
    assert result["position_oi_share_pct"].tolist() == [1.0, 100.0 / 99.0]
    assert result["capacity_valid"].tolist() == [True, False]
    assert result["capacity_failure_reason"].tolist() == [
        "",
        "volume_below_one_lot_capacity|open_interest_below_one_lot_capacity",
    ]


def test_open_interest_only_failure_reason_is_not_duplicated() -> None:
    events = pd.DataFrame(
        {
            "query_date": ["2025-01-02"],
            "product_vt_symbol": ["p.EX"],
            "event_role": ["entry"],
            "event_date": ["2025-01-03"],
            "contract_vt_symbol": ["P2505.EX"],
            "volume": [100.0],
            "open_interest": [99.0],
        }
    )

    result = core.assess_event_capacity(events)

    assert result["capacity_failure_reason"].tolist() == [
        "open_interest_below_one_lot_capacity"
    ]
