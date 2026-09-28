from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import roll_aware_label_plan as plan


def _candidate() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "query_date": ["2024-01-01"],
            "product_vt_symbol": ["p.EX"],
            "main_contract_vt": ["P01.EX"],
            "entry_date": ["2024-01-02"],
            "label_end": ["2024-01-04"],
            "source_partition": ["fixed_label_accepted"],
        }
    )


def _mapping() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "continuous_symbol_vt": ["p.EX"] * 4,
            "main_contract_vt": ["P01.EX", "P02.EX", "P03.EX", "P03.EX"],
            "mapping_resolution": ["resolved"] * 4,
        }
    )


def _presence() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03", "2024-01-03", "2024-01-04"],
            "contract_vt_symbol": ["P01.EX", "P01.EX", "P03.EX", "P03.EX"],
        }
    )


def test_first_leg_uses_query_contract_and_later_leg_uses_previous_date_mapping() -> None:
    summary, legs, failures = plan.build_roll_aware_paths(
        _candidate(),
        _mapping(),
        _presence(),
        pd.date_range("2024-01-01", periods=4, freq="D"),
        holding_period=2,
    )

    assert failures.empty
    assert summary.loc[0, ["leg_count", "roll_count", "path_valid"]].to_dict() == {
        "leg_count": 2,
        "roll_count": 1,
        "path_valid": True,
    }
    assert legs[
        [
            "leg_index",
            "previous_date",
            "return_date",
            "mapping_date",
            "selected_contract_vt",
            "roll_event",
        ]
    ].to_dict("records") == [
        {
            "leg_index": 1,
            "previous_date": pd.Timestamp("2024-01-02"),
            "return_date": pd.Timestamp("2024-01-03"),
            "mapping_date": pd.Timestamp("2024-01-01"),
            "selected_contract_vt": "P01.EX",
            "roll_event": False,
        },
        {
            "leg_index": 2,
            "previous_date": pd.Timestamp("2024-01-03"),
            "return_date": pd.Timestamp("2024-01-04"),
            "mapping_date": pd.Timestamp("2024-01-03"),
            "selected_contract_vt": "P03.EX",
            "roll_event": True,
        },
    ]


def test_roll_boundary_requires_new_contract_bar_on_boundary_date() -> None:
    missing_new_start = _presence().query(
        "not (date == '2024-01-03' and contract_vt_symbol == 'P03.EX')"
    )

    summary, legs, failures = plan.build_roll_aware_paths(
        _candidate(),
        _mapping(),
        missing_new_start,
        pd.date_range("2024-01-01", periods=4, freq="D"),
        holding_period=2,
    )

    assert summary.loc[0, "path_valid"] == False  # noqa: E712
    assert legs.loc[legs["leg_index"].eq(2), "failure_reason"].item() == (
        "previous_bar_missing"
    )
    assert failures[["leg_index", "failure_reason"]].to_dict("records") == [
        {"leg_index": 2, "failure_reason": "previous_bar_missing"}
    ]


def test_missing_mapped_contract_fails_without_fallback() -> None:
    mapping = _mapping()
    mapping.loc[mapping["date"].eq("2024-01-03"), "main_contract_vt"] = None

    summary, legs, failures = plan.build_roll_aware_paths(
        _candidate(),
        mapping,
        _presence(),
        pd.date_range("2024-01-01", periods=4, freq="D"),
        holding_period=2,
    )

    assert summary.loc[0, "path_valid"] == False  # noqa: E712
    failed_leg = legs.loc[legs["leg_index"].eq(2)].iloc[0]
    assert pd.isna(failed_leg["selected_contract_vt"])
    assert failed_leg["failure_reason"] == "mapping_missing"
    assert failures["failure_reason"].tolist() == ["mapping_missing"]


def test_query_mapping_must_match_frozen_entry_contract() -> None:
    mapping = _mapping()
    mapping.loc[mapping["date"].eq("2024-01-01"), "main_contract_vt"] = "OTHER.EX"

    summary, legs, failures = plan.build_roll_aware_paths(
        _candidate(),
        mapping,
        _presence(),
        pd.date_range("2024-01-01", periods=4, freq="D"),
        holding_period=2,
    )

    assert summary.loc[0, "path_valid"] == False  # noqa: E712
    assert legs.loc[legs["leg_index"].eq(1), "selected_contract_vt"].item() == (
        "P01.EX"
    )
    assert failures["failure_reason"].tolist() == ["query_mapping_mismatch"]


def test_partition_windows_covers_base_once_and_keeps_cutoff_separate() -> None:
    base = pd.DataFrame(
        {
            "query_date": ["2024-01-01", "2024-01-01", "2024-01-02"],
            "product_vt_symbol": ["a.EX", "b.EX", "a.EX"],
            "main_contract_vt": ["A01.EX", "B01.EX", "A01.EX"],
        }
    )
    accepted = pd.DataFrame(
        {
            "query_date": ["2024-01-01"],
            "product_vt_symbol": ["a.EX"],
            "main_contract_vt": ["A01.EX"],
            "entry_date": ["2024-01-02"],
            "label_end": ["2024-01-31"],
        }
    )
    rejected = pd.DataFrame(
        {
            "query_date": ["2024-01-01", "2024-01-02"],
            "product_vt_symbol": ["b.EX", "a.EX"],
            "main_contract_vt": ["B01.EX", "A01.EX"],
            "entry_date": ["2024-01-02", "2024-01-03"],
            "label_end": ["2024-01-31", None],
            "rejection_reason": ["exit_bar_missing", "exit_date_outside_cutoff"],
        }
    )

    candidates, cutoff, diagnostics = plan.partition_windows(base, accepted, rejected)

    assert candidates["source_partition"].tolist() == [
        "fixed_label_accepted",
        "fixed_exit_bar_missing",
    ]
    assert cutoff[["query_date", "product_vt_symbol"]].to_dict("records") == [
        {"query_date": pd.Timestamp("2024-01-02"), "product_vt_symbol": "a.EX"}
    ]
    assert diagnostics == {
        "base_rows": 3,
        "base_qids": 2,
        "fixed_label_accepted_rows": 1,
        "fixed_exit_bar_missing_rows": 1,
        "exit_date_outside_cutoff_rows": 1,
        "candidate_rows": 2,
        "cutoff_rows": 1,
    }


def test_partition_windows_rejects_duplicate_or_uncovered_base_key() -> None:
    base = pd.DataFrame(
        {
            "query_date": ["2024-01-01"],
            "product_vt_symbol": ["a.EX"],
            "main_contract_vt": ["A01.EX"],
        }
    )
    accepted = pd.DataFrame(
        {
            "query_date": ["2024-01-01", "2024-01-01"],
            "product_vt_symbol": ["a.EX", "a.EX"],
            "main_contract_vt": ["A01.EX", "A01.EX"],
            "entry_date": ["2024-01-02", "2024-01-02"],
            "label_end": ["2024-01-31", "2024-01-31"],
        }
    )
    rejected = pd.DataFrame(
        columns=[
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
            "rejection_reason",
        ]
    )

    with pytest.raises(plan.PlanError, match="duplicate_partition_key"):
        plan.partition_windows(base, accepted, rejected)

    with pytest.raises(plan.PlanError, match="partition_key_mismatch"):
        plan.partition_windows(base, accepted.iloc[:0], rejected)
