from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import expiry_safe_roll_mapping as core


def test_keeps_original_contract_when_expiry_covers_return_date() -> None:
    legs = pd.DataFrame(
        {
            "query_date": ["2025-01-02"],
            "product_vt_symbol": ["p.EX"],
            "leg_index": [1],
            "mapping_date": ["2025-01-02"],
            "previous_date": ["2025-01-03"],
            "return_date": ["2025-01-06"],
            "selected_contract_vt": ["P2501.EX"],
        }
    )
    catalog = pd.DataFrame(
        {
            "vt_symbol": ["P2501.EX", "P2505.EX"],
            "product_vt_symbol": ["p.EX", "p.EX"],
            "expire_date": ["2025-01-06", "2025-05-16"],
        }
    )
    liquidity = pd.DataFrame(
        {
            "date": ["2025-01-02", "2025-01-02"],
            "contract_vt_symbol": ["P2501.EX", "P2505.EX"],
            "volume": [10.0, 1000.0],
            "open_interest": [20.0, 2000.0],
        }
    )

    result = core.select_expiry_safe_contracts(legs, catalog, liquidity)

    row = result.iloc[0]
    assert row["original_contract_vt"] == "P2501.EX"
    assert row["selected_contract_vt"] == "P2501.EX"
    assert row["selection_reason"] == "original_expiry_valid"
    assert not bool(row["expiry_fallback"])
    assert bool(row["selection_valid"])


def test_expired_original_uses_mapping_date_liquidity_ranking() -> None:
    legs = pd.DataFrame(
        {
            "query_date": ["2025-01-02"],
            "product_vt_symbol": ["p.EX"],
            "leg_index": [2],
            "mapping_date": ["2025-01-03"],
            "previous_date": ["2025-01-03"],
            "return_date": ["2025-01-06"],
            "selected_contract_vt": ["P2501.EX"],
        }
    )
    catalog = pd.DataFrame(
        {
            "vt_symbol": [
                "P2501.EX",
                "P2503.EX",
                "P2505.EX",
                "P2507.EX",
            ],
            "product_vt_symbol": ["p.EX"] * 4,
            "expire_date": [
                "2025-01-03",
                "2025-03-14",
                "2025-05-16",
                "2025-07-18",
            ],
        }
    )
    liquidity = pd.DataFrame(
        {
            "date": ["2025-01-03"] * 4,
            "contract_vt_symbol": [
                "P2501.EX",
                "P2503.EX",
                "P2505.EX",
                "P2507.EX",
            ],
            "volume": [1000.0, 500.0, 600.0, 2000.0],
            "open_interest": [2000.0, 100.0, 100.0, 90.0],
        }
    )

    result = core.select_expiry_safe_contracts(legs, catalog, liquidity)

    row = result.iloc[0]
    assert row["selected_contract_vt"] == "P2505.EX"
    assert row["selected_expire_date"] == pd.Timestamp("2025-05-16")
    assert row["selection_reason"] == "expiry_fallback_liquidity"
    assert bool(row["expiry_fallback"])
    assert row["fallback_rank"] == 1
    assert row["fallback_open_interest"] == 100.0
    assert row["fallback_volume"] == 600.0
    assert bool(row["selection_valid"])


def test_fallback_ignores_return_date_liquidity() -> None:
    legs = pd.DataFrame(
        {
            "query_date": ["2025-01-02"],
            "product_vt_symbol": ["p.EX"],
            "leg_index": [2],
            "mapping_date": ["2025-01-03"],
            "previous_date": ["2025-01-03"],
            "return_date": ["2025-01-06"],
            "selected_contract_vt": ["P2501.EX"],
        }
    )
    catalog = pd.DataFrame(
        {
            "vt_symbol": ["P2501.EX", "P2503.EX", "P2505.EX"],
            "product_vt_symbol": ["p.EX"] * 3,
            "expire_date": ["2025-01-03", "2025-03-14", "2025-05-16"],
        }
    )
    liquidity = pd.DataFrame(
        {
            "date": ["2025-01-03", "2025-01-06"],
            "contract_vt_symbol": ["P2503.EX", "P2505.EX"],
            "volume": [10.0, 10000.0],
            "open_interest": [20.0, 20000.0],
        }
    )

    result = core.select_expiry_safe_contracts(legs, catalog, liquidity)

    row = result.iloc[0]
    assert row["selected_contract_vt"] == "P2503.EX"
    assert row["selection_source_date"] == pd.Timestamp("2025-01-03")
    assert row["future_selection_rows_used"] == 0


def test_missing_expiry_fallback_returns_invalid_audit_row() -> None:
    legs = pd.DataFrame(
        {
            "query_date": ["2025-01-02"],
            "product_vt_symbol": ["p.EX"],
            "leg_index": [2],
            "mapping_date": ["2025-01-03"],
            "previous_date": ["2025-01-03"],
            "return_date": ["2025-01-06"],
            "selected_contract_vt": ["P2501.EX"],
        }
    )
    catalog = pd.DataFrame(
        {
            "vt_symbol": ["P2501.EX"],
            "product_vt_symbol": ["p.EX"],
            "expire_date": ["2025-01-03"],
        }
    )
    liquidity = pd.DataFrame(
        {
            "date": ["2025-01-03"],
            "contract_vt_symbol": ["P2501.EX"],
            "volume": [100.0],
            "open_interest": [200.0],
        }
    )

    result = core.select_expiry_safe_contracts(legs, catalog, liquidity)

    row = result.iloc[0]
    assert row["selection_reason"] == "expiry_fallback_failed"
    assert bool(row["expiry_fallback"])
    assert not bool(row["selection_valid"])
    assert row["selection_failure_reason"] == (
        "expiry_fallback_candidate_missing"
    )


def test_endpoint_validation_fails_without_reselecting_from_future_bar() -> None:
    legs = pd.DataFrame(
        {
            "query_date": ["2025-01-02"],
            "product_vt_symbol": ["p.EX"],
            "leg_index": [2],
            "mapping_date": ["2025-01-03"],
            "previous_date": ["2025-01-03"],
            "return_date": ["2025-01-06"],
            "selected_contract_vt": ["P2501.EX"],
        }
    )
    catalog = pd.DataFrame(
        {
            "vt_symbol": ["P2501.EX", "P2503.EX", "P2505.EX"],
            "product_vt_symbol": ["p.EX"] * 3,
            "expire_date": ["2025-01-03", "2025-03-14", "2025-05-16"],
        }
    )
    liquidity = pd.DataFrame(
        {
            "date": ["2025-01-03", "2025-01-03"],
            "contract_vt_symbol": ["P2503.EX", "P2505.EX"],
            "volume": [20.0, 10.0],
            "open_interest": [30.0, 20.0],
        }
    )
    presence = pd.DataFrame(
        {
            "date": ["2025-01-03", "2025-01-03", "2025-01-06"],
            "contract_vt_symbol": ["P2503.EX", "P2505.EX", "P2505.EX"],
        }
    )
    selected = core.select_expiry_safe_contracts(legs, catalog, liquidity)

    validated = core.validate_selected_endpoints(selected, presence)

    row = validated.iloc[0]
    assert row["selected_contract_vt"] == "P2503.EX"
    assert not bool(row["leg_valid"])
    assert row["failure_reason"] == "return_bar_missing_after_selection"


def test_duplicate_leg_identity_is_rejected() -> None:
    legs = pd.DataFrame(
        {
            "query_date": ["2025-01-02", "2025-01-02"],
            "product_vt_symbol": ["p.EX", "p.EX"],
            "leg_index": [1, 1],
            "mapping_date": ["2025-01-02", "2025-01-02"],
            "previous_date": ["2025-01-03", "2025-01-03"],
            "return_date": ["2025-01-06", "2025-01-06"],
            "selected_contract_vt": ["P2501.EX", "P2501.EX"],
        }
    )
    catalog = pd.DataFrame(
        {
            "vt_symbol": ["P2501.EX"],
            "product_vt_symbol": ["p.EX"],
            "expire_date": ["2025-01-06"],
        }
    )
    liquidity = pd.DataFrame(
        {
            "date": ["2025-01-02"],
            "contract_vt_symbol": ["P2501.EX"],
            "volume": [1.0],
            "open_interest": [1.0],
        }
    )

    with pytest.raises(core.SelectionError, match="duplicate_leg_identity"):
        core.select_expiry_safe_contracts(legs, catalog, liquidity)
