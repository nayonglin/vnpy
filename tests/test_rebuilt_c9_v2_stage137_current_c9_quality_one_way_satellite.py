from __future__ import annotations

import importlib
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "tools"
)
MODULE_NAME = "stage137_current_c9_quality_one_way_satellite"
MODULE_PATH = TOOLS_DIR / f"{MODULE_NAME}.py"
OPEN_GROUP_COLUMNS = [
    "requested_start_month",
    "open_trade_id",
    "vt_symbol",
    "direction",
    "entry_date",
    "entry_price",
    "base_open_volume",
    "close_trade_ids",
    "close_matched_volumes",
    "satellite_open_volume",
]
ORDER_COLUMNS = [
    "requested_start_month",
    "open_trade_id",
    "base_open_trade_id",
    "base_close_trade_id",
    "base_trade_id",
    "vt_symbol",
    "direction",
    "trade_datetime",
    "trade_price",
    "satellite_delta",
    "base_matched_volume",
    "base_remaining_volume",
    "satellite_target_volume",
]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"production module missing: {MODULE_PATH}")
    return importlib.import_module(MODULE_NAME)


def _identity_input_fields(start: str) -> dict[str, object]:
    return {
        "current_ai_snapshot_pass": 1,
        "current_ai_golden_membership_pass": 1,
        "current_ai_golden_curve_applicable": int(start == "2020-01"),
        "current_ai_golden_curve_pass": 1,
        "current_c9_repeat_identity_pass": 1,
        "repeat_source_manifest_pass": 1,
        "repeat_worker_environment_pass": 1,
    }


def _identity_output_frames() -> dict[str, pd.DataFrame]:
    module = _module()
    current_path = str(module.CURRENT_AI_PATH.resolve())
    current_snapshot = module._file_snapshot(module.CURRENT_AI_PATH)
    current_ai = pd.DataFrame(
        [
            {
                "requested_start_month": start,
                "current_ai_snapshot_pass": 1,
                "current_ai_snapshot_sha256": module.CURRENT_AI_EXPECTED_SHA256,
                "current_ai_snapshot_row_count": module.CURRENT_AI_EXPECTED_ROWS,
                "current_ai_snapshot_eval_date_count": len(
                    module.CURRENT_AI_EXPECTED_EVAL_DATES
                ),
                "current_ai_golden_membership_pass": 1,
                "current_ai_golden_curve_applicable": int(start == "2020-01"),
                "current_ai_golden_curve_pass": 1,
                "repeat_worker_environment_pass": 1,
                "repeat_worker_environment_sha256": "e" * 64,
            }
            for start in module.CANARY_STARTS
        ]
    )
    repeat_identity = pd.DataFrame(
        [
            {
                "requested_start_month": start,
                "frame_name": frame_name,
                "first_row_count": 1,
                "second_row_count": 1,
                "first_column_count": 1,
                "second_column_count": 1,
                "first_schema_sha256": "a" * 64,
                "second_schema_sha256": "a" * 64,
                "first_content_sha256": "b" * 64,
                "second_content_sha256": "b" * 64,
                "identity_match": 1,
            }
            for start in module.CANARY_STARTS
            for frame_name in module._REPEAT_ARTIFACT_KEYS
        ]
    )
    repeat_source = pd.DataFrame(
        [
            {
                "requested_start_month": start,
                "path": current_path,
                "size": current_snapshot["size"],
                "sha256": module.CURRENT_AI_EXPECTED_SHA256,
                "content_identity_match": 1,
            }
            for start in module.CANARY_STARTS
        ]
    )
    source_manifest = pd.DataFrame(
        [
            {
                "path": current_path,
                "size": current_snapshot["size"],
                "mtime_ns": current_snapshot["mtime_ns"],
                "sha256": module.CURRENT_AI_EXPECTED_SHA256,
            }
        ]
    )
    return {
        "current_ai_audit": current_ai,
        "repeat_identity_audit": repeat_identity,
        "repeat_source_manifest": repeat_source,
        "source_manifest": source_manifest,
    }


def _complete_identity_output_bundle(bundle: dict[str, object]) -> None:
    module = _module()
    input_audit = bundle["input_audit"]
    if not isinstance(input_audit, pd.DataFrame) or input_audit.empty:
        raise AssertionError("identity fixture requires a non-empty input audit")
    template = input_audit.iloc[0].to_dict()
    bundle["input_audit"] = pd.DataFrame(
        [
            {
                **template,
                "requested_start_month": start,
                **_identity_input_fields(start),
            }
            for start in module.CANARY_STARTS
        ]
    )
    bundle.update(_identity_output_frames())


class Stage137QualitySatelliteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.closed_lots = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-01",
                    "open_trade_id": "OPEN.1",
                    "close_trade_id": "CLOSE.1",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "entry_date": "2022-01-03",
                    "entry_price": 4500.0,
                    "exit_date": "2022-01-05",
                    "exit_price": 4550.0,
                    "entry_context": "flat_entry",
                    "layer_kind": "base",
                    "ai_product_pool_allowed": 1.0,
                    "ai_product_pool_rank": 3.0,
                    "selected_volume": 11.0,
                    "volume": 4.0,
                },
                {
                    "requested_start_month": "2022-01",
                    "open_trade_id": "OPEN.1",
                    "close_trade_id": "CLOSE.2",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "entry_date": "2022-01-03",
                    "entry_price": 4500.0,
                    "exit_date": "2022-01-06",
                    "exit_price": 4600.0,
                    "entry_context": "flat_entry",
                    "layer_kind": "base",
                    "ai_product_pool_allowed": 1.0,
                    "ai_product_pool_rank": 3.0,
                    "selected_volume": 11.0,
                    "volume": 7.0,
                },
                {
                    "requested_start_month": "2022-01",
                    "open_trade_id": "OPEN.2",
                    "close_trade_id": "CLOSE.3",
                    "vt_symbol": "cu2205.SHFE",
                    "direction": "long",
                    "entry_date": "2022-01-03",
                    "entry_price": 70000.0,
                    "exit_date": "2022-01-05",
                    "exit_price": 70100.0,
                    "entry_context": "regular_add",
                    "layer_kind": "base",
                    "ai_product_pool_allowed": np.nan,
                    "ai_product_pool_rank": np.nan,
                    "selected_volume": np.nan,
                    "volume": 3.0,
                },
            ]
        )

    def test_quality_selector_groups_split_closes_by_original_open_trade(self) -> None:
        selected = _module().select_quality_open_groups(self.closed_lots)

        self.assertEqual(selected["open_trade_id"].tolist(), ["OPEN.1"])
        self.assertEqual(selected.loc[0, "base_open_volume"], 11)
        self.assertEqual(selected.loc[0, "satellite_open_volume"], 2)
        self.assertEqual(selected.loc[0, "close_trade_ids"], ["CLOSE.1", "CLOSE.2"])
        self.assertEqual(selected.loc[0, "close_matched_volumes"], [4.0, 7.0])

    def test_quality_selector_ignores_missing_rank_on_non_structural_rows(self) -> None:
        selected = _module().select_quality_open_groups(self.closed_lots)

        self.assertEqual(selected["open_trade_id"].tolist(), ["OPEN.1"])

    def test_quality_selector_fails_closed_on_missing_rank_in_structural_rows(self) -> None:
        lots = self.closed_lots.copy()
        lots.loc[lots["open_trade_id"].eq("OPEN.1"), "ai_product_pool_rank"] = np.nan

        with self.assertRaisesRegex(ValueError, "ai_product_pool_rank"):
            _module().select_quality_open_groups(lots)

    def test_quality_selector_fails_closed_on_inconsistent_open_group_identity(self) -> None:
        lots = self.closed_lots.copy()
        lots.loc[lots["close_trade_id"].eq("CLOSE.2"), "entry_price"] = 4501.0

        with self.assertRaisesRegex(ValueError, "inconsistent open group identity"):
            _module().select_quality_open_groups(lots)

    def test_quality_selector_validates_full_lifecycle_before_group_level_selection(self) -> None:
        lots = self.closed_lots.copy()
        lots.loc[lots["close_trade_id"].eq("CLOSE.2"), "ai_product_pool_rank"] = 9.0

        with self.assertRaisesRegex(ValueError, "inconsistent open group identity: ai_product_pool_rank"):
            _module().select_quality_open_groups(lots)

    def test_quality_selector_requires_lifecycle_volume_to_equal_selected_volume(self) -> None:
        lots = self.closed_lots.copy()
        lots.loc[lots["close_trade_id"].eq("CLOSE.2"), "volume"] = 6.0

        with self.assertRaisesRegex(ValueError, "sum\(volume\).+selected_volume"):
            _module().select_quality_open_groups(lots)

    def test_quality_selector_rejects_invalid_requested_start_month_before_grouping(self) -> None:
        for invalid_month in (np.nan, "", "2022-1", "2022-13"):
            with self.subTest(invalid_month=invalid_month):
                lots = self.closed_lots.copy()
                lots.loc[lots["open_trade_id"].eq("OPEN.1"), "requested_start_month"] = invalid_month

                with self.assertRaisesRegex(ValueError, "requested_start_month"):
                    _module().select_quality_open_groups(lots)

    def test_quality_selector_returns_fixed_schema_when_no_group_is_selected(self) -> None:
        lots = self.closed_lots.copy()
        lots.loc[lots["open_trade_id"].eq("OPEN.1"), "ai_product_pool_rank"] = 9.0

        selected = _module().select_quality_open_groups(lots)

        self.assertEqual(selected.columns.tolist(), OPEN_GROUP_COLUMNS)
        self.assertTrue(selected.empty)

    def test_quality_selector_accepts_zero_column_empty_input_but_rejects_nonempty_missing_columns(self) -> None:
        try:
            selected = _module().select_quality_open_groups(pd.DataFrame())
        except ValueError as exc:
            self.fail(f"zero-column empty selector input must be accepted: {exc}")

        self.assertEqual(selected.columns.tolist(), OPEN_GROUP_COLUMNS)
        self.assertTrue(selected.empty)
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            _module().select_quality_open_groups(pd.DataFrame([{}]))

    def test_quality_selector_is_fully_deterministic_under_closed_lot_shuffle(self) -> None:
        lots = self.closed_lots.copy()
        second_group = lots["open_trade_id"].eq("OPEN.2")
        lots.loc[second_group, "entry_context"] = "flat_entry"
        lots.loc[second_group, "ai_product_pool_allowed"] = 1.0
        lots.loc[second_group, "ai_product_pool_rank"] = 2.0
        lots.loc[second_group, "selected_volume"] = 4.0
        lots.loc[second_group, "volume"] = 4.0

        expected = _module().select_quality_open_groups(lots)
        shuffled = _module().select_quality_open_groups(lots.sample(frac=1.0, random_state=7))

        pd.testing.assert_frame_equal(shuffled, expected)

    def test_quality_selector_requires_positive_integer_selected_volume(self) -> None:
        lots = self.closed_lots.copy()
        selected = lots["open_trade_id"].eq("OPEN.1")
        lots.loc[selected, "selected_volume"] = 11.5
        lots.loc[lots["close_trade_id"].eq("CLOSE.2"), "volume"] = 7.5

        with self.assertRaisesRegex(ValueError, "positive integer selected_volume"):
            _module().select_quality_open_groups(lots)

    def test_quality_selector_requires_positive_integer_closed_lot_volume(self) -> None:
        for volumes in ((4.5, 6.5), (0.0, 11.0)):
            with self.subTest(volumes=volumes):
                lots = self.closed_lots.copy()
                selected = lots["open_trade_id"].eq("OPEN.1")
                lots.loc[selected, "volume"] = volumes

                with self.assertRaisesRegex(ValueError, "positive integer closed-lot volume"):
                    _module().select_quality_open_groups(lots)


class Stage137FloorMirrorAllocationTest(unittest.TestCase):
    def setUp(self) -> None:
        lots = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-01",
                    "open_trade_id": "OPEN.1",
                    "close_trade_id": "CLOSE.1",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "entry_date": "2022-01-03",
                    "entry_price": 4500.0,
                    "exit_date": "2022-01-05",
                    "exit_price": 4550.0,
                    "entry_context": "flat_entry",
                    "layer_kind": "base",
                    "ai_product_pool_allowed": 1.0,
                    "ai_product_pool_rank": 3.0,
                    "selected_volume": 11.0,
                    "volume": 4.0,
                },
                {
                    "requested_start_month": "2022-01",
                    "open_trade_id": "OPEN.1",
                    "close_trade_id": "CLOSE.2",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "entry_date": "2022-01-03",
                    "entry_price": 4500.0,
                    "exit_date": "2022-01-06",
                    "exit_price": 4600.0,
                    "entry_context": "flat_entry",
                    "layer_kind": "base",
                    "ai_product_pool_allowed": 1.0,
                    "ai_product_pool_rank": 3.0,
                    "selected_volume": 11.0,
                    "volume": 7.0,
                },
            ]
        )
        self.open_groups = _module().select_quality_open_groups(lots)
        self.trades = pd.DataFrame(
            [
                {
                    "trade_id": "OPEN.1",
                    "datetime": "2022-01-03 09:01:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "offset": "Open",
                    "price": 4500.0,
                    "volume": 11.0,
                },
                {
                    "trade_id": "CLOSE.1",
                    "datetime": "2022-01-05 09:02:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "short",
                    "offset": "Close",
                    "price": 4550.0,
                    "volume": 4.0,
                },
                {
                    "trade_id": "CLOSE.2",
                    "datetime": "2022-01-06 09:03:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "short",
                    "offset": "Close",
                    "price": 4600.0,
                    "volume": 7.0,
                },
            ]
        )

    def test_partial_close_allocation_tracks_floor_of_remaining_base_volume(self) -> None:
        orders, audit = _module().allocate_floor_mirror_orders(self.open_groups, self.trades)

        self.assertEqual(orders["satellite_delta"].tolist(), [2, -1, -1])
        self.assertEqual(orders["base_trade_id"].tolist(), ["OPEN.1", "CLOSE.1", "CLOSE.2"])
        self.assertEqual(orders["trade_price"].tolist(), [4500.0, 4550.0, 4600.0])
        self.assertEqual(orders["trade_datetime"].tolist(), list(pd.to_datetime(self.trades["datetime"])))
        self.assertEqual(audit["overclose_count"], 0)
        self.assertEqual(audit["nonflat_final_open_group_count"], 0)

    def test_allocation_fails_closed_on_duplicate_trade_id(self) -> None:
        trades = pd.concat([self.trades, self.trades.iloc[[0]]], ignore_index=True)

        with self.assertRaisesRegex(ValueError, "trade_id is not unique"):
            _module().allocate_floor_mirror_orders(self.open_groups, trades)

    def test_allocation_requires_long_open_and_short_close_trade_directions(self) -> None:
        trades = self.trades.copy()
        trades.loc[trades["trade_id"].eq("CLOSE.1"), "direction"] = "long"

        with self.assertRaisesRegex(ValueError, "trade direction mismatch"):
            _module().allocate_floor_mirror_orders(self.open_groups, trades)

    def test_allocation_rejects_unknown_trade_offset(self) -> None:
        trades = self.trades.copy()
        trades.loc[trades["trade_id"].eq("CLOSE.1"), "offset"] = "CloseToday"

        with self.assertRaisesRegex(ValueError, "invalid trade offset"):
            _module().allocate_floor_mirror_orders(self.open_groups, trades)

    def test_allocation_requires_positive_integer_trade_volume(self) -> None:
        trades = self.trades.copy()
        trades.loc[trades["trade_id"].eq("CLOSE.1"), "volume"] = 4.5

        with self.assertRaisesRegex(ValueError, "positive integer trade volume"):
            _module().allocate_floor_mirror_orders(self.open_groups, trades)

    def test_allocation_conserves_shared_close_volume_across_open_groups(self) -> None:
        groups = self.open_groups.copy()
        groups.at[0, "close_trade_ids"] = ["CLOSE.SHARED", "CLOSE.2"]
        groups.at[0, "close_matched_volumes"] = [4.0, 7.0]
        second = groups.copy()
        second.at[0, "open_trade_id"] = "OPEN.2"
        second.at[0, "close_trade_ids"] = ["CLOSE.SHARED", "CLOSE.2"]
        groups = pd.concat([groups, second], ignore_index=True)
        trades = pd.concat(
            [
                self.trades,
                pd.DataFrame(
                    [
                        {
                            "trade_id": "OPEN.2",
                            "datetime": "2022-01-03 09:02:00+08:00",
                            "vt_symbol": "rb2205.SHFE",
                            "direction": "long",
                            "offset": "Open",
                            "price": 4501.0,
                            "volume": 11.0,
                        },
                        {
                            "trade_id": "CLOSE.SHARED",
                            "datetime": "2022-01-04 09:01:00+08:00",
                            "vt_symbol": "rb2205.SHFE",
                            "direction": "short",
                            "offset": "Close",
                            "price": 4510.0,
                            "volume": 4.0,
                        },
                    ]
                ),
            ],
            ignore_index=True,
        )

        with self.assertRaisesRegex(ValueError, "shared close matched volume"):
            _module().allocate_floor_mirror_orders(groups, trades)

    def test_allocation_rejects_duplicate_open_group_identity(self) -> None:
        groups = pd.concat([self.open_groups, self.open_groups], ignore_index=True)

        with self.assertRaisesRegex(ValueError, "duplicate open group identity"):
            _module().allocate_floor_mirror_orders(groups, self.trades)

    def test_allocation_rejects_invalid_requested_start_month_before_keying(self) -> None:
        groups = self.open_groups.copy()
        groups.loc[0, "requested_start_month"] = "2022-1"

        with self.assertRaisesRegex(ValueError, "requested_start_month"):
            _module().allocate_floor_mirror_orders(groups, self.trades)

    def test_allocation_rejects_naive_trade_datetime(self) -> None:
        trades = self.trades.copy()
        trades.loc[trades["trade_id"].eq("OPEN.1"), "datetime"] = "2022-01-03 09:01:00"

        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            _module().allocate_floor_mirror_orders(self.open_groups, trades)

    def test_allocation_rejects_close_before_its_open(self) -> None:
        trades = self.trades.copy()
        trades.loc[trades["trade_id"].eq("CLOSE.1"), "datetime"] = "2022-01-02 09:02:00+08:00"

        with self.assertRaisesRegex(ValueError, "close before open"):
            _module().allocate_floor_mirror_orders(self.open_groups, trades)

    def test_allocation_uses_requested_start_open_id_and_event_type_as_stable_tie_breakers(self) -> None:
        first = self.open_groups.copy()
        first.loc[0, "open_trade_id"] = "OPEN.Z"
        first.loc[0, "close_trade_ids"] = ["CLOSE.Z"]
        first.loc[0, "close_matched_volumes"] = [11.0]
        second = first.copy()
        second.loc[0, "requested_start_month"] = "2022-07"
        second.loc[0, "open_trade_id"] = "OPEN.A"
        second.loc[0, "close_trade_ids"] = ["CLOSE.A"]
        groups = pd.concat([first, second], ignore_index=True)
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "CLOSE.A",
                    "datetime": "2022-01-03 09:01:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "short",
                    "offset": "Close",
                    "price": 4501.0,
                    "volume": 11.0,
                },
                {
                    "trade_id": "OPEN.Z",
                    "datetime": "2022-01-03 09:01:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "offset": "Open",
                    "price": 4500.0,
                    "volume": 11.0,
                },
                {
                    "trade_id": "CLOSE.Z",
                    "datetime": "2022-01-03 09:01:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "short",
                    "offset": "Close",
                    "price": 4501.0,
                    "volume": 11.0,
                },
                {
                    "trade_id": "OPEN.A",
                    "datetime": "2022-01-03 09:01:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "offset": "Open",
                    "price": 4500.0,
                    "volume": 11.0,
                },
            ]
        ).sample(frac=1.0, random_state=7)

        orders, _audit = _module().allocate_floor_mirror_orders(groups, trades)

        self.assertEqual(orders["requested_start_month"].tolist(), ["2022-01", "2022-01", "2022-07", "2022-07"])
        self.assertEqual(orders["base_trade_id"].tolist(), ["OPEN.Z", "CLOSE.Z", "OPEN.A", "CLOSE.A"])

    def test_allocation_returns_fixed_schema_for_empty_open_groups(self) -> None:
        orders, audit = _module().allocate_floor_mirror_orders(self.open_groups.iloc[0:0], self.trades)

        self.assertEqual(orders.columns.tolist(), ORDER_COLUMNS)
        self.assertTrue(orders.empty)
        self.assertEqual(audit["selected_open_group_count"], 0)

    def test_allocation_accepts_zero_column_empty_groups_without_parsing_trades(self) -> None:
        try:
            orders, audit = _module().allocate_floor_mirror_orders(
                pd.DataFrame(),
                pd.DataFrame([{"not_a_trade": 1}]),
            )
        except ValueError as exc:
            self.fail(f"zero-column empty open groups must bypass trade parsing: {exc}")

        self.assertEqual(orders.columns.tolist(), ORDER_COLUMNS)
        self.assertTrue(orders.empty)
        self.assertEqual(
            audit,
            {
                "selected_open_group_count": 0,
                "satellite_order_count": 0,
                "overclose_count": 0,
                "nonflat_final_open_group_count": 0,
                "expected_terminal_position_count": 0,
                "unexpected_terminal_position_count": 0,
                "max_terminal_position_reconciliation_error": 0.0,
                "expected_terminal_positions": {},
            },
        )
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            _module().allocate_floor_mirror_orders(pd.DataFrame([{}]), pd.DataFrame())

    def test_allocation_requires_integer_base_satellite_and_matched_volumes(self) -> None:
        invalid_cases = (
            ("base_open_volume", 11.5, "positive integer base_open_volume"),
            ("satellite_open_volume", 2.5, "non-negative integer satellite_open_volume"),
            ("close_matched_volumes", [4.5, 6.5], "positive integer close_matched_volume"),
        )
        for column, value, message in invalid_cases:
            with self.subTest(column=column):
                groups = self.open_groups.copy()
                if column in {"base_open_volume", "satellite_open_volume"}:
                    groups[column] = groups[column].astype(float)
                groups.at[0, column] = value

                with self.assertRaisesRegex(ValueError, message):
                    _module().allocate_floor_mirror_orders(groups, self.trades)

        zero_satellite = self.open_groups.copy()
        zero_satellite.at[0, "open_trade_id"] = "OPEN.ZERO"
        zero_satellite.at[0, "base_open_volume"] = 3.0
        zero_satellite.at[0, "satellite_open_volume"] = 0.0
        zero_satellite.at[0, "close_trade_ids"] = ["CLOSE.ZERO"]
        zero_satellite.at[0, "close_matched_volumes"] = [3.0]
        zero_trades = pd.DataFrame(
            [
                {
                    "trade_id": "OPEN.ZERO",
                    "datetime": "2022-01-03 09:01:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "offset": "Open",
                    "price": 4500.0,
                    "volume": 3.0,
                },
                {
                    "trade_id": "CLOSE.ZERO",
                    "datetime": "2022-01-05 09:02:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "short",
                    "offset": "Close",
                    "price": 4550.0,
                    "volume": 3.0,
                },
            ]
        )

        orders, audit = _module().allocate_floor_mirror_orders(zero_satellite, zero_trades)
        self.assertEqual(orders.columns.tolist(), ORDER_COLUMNS)
        self.assertTrue(orders.empty)
        self.assertEqual(audit["selected_open_group_count"], 1)
        self.assertEqual(audit["satellite_order_count"], 0)

    def test_allocation_fails_closed_when_matched_closes_do_not_equal_selected_open_volume(self) -> None:
        groups = self.open_groups.copy()
        groups.at[0, "close_matched_volumes"] = [4.0, 6.0]

        with self.assertRaisesRegex(ValueError, "matched close volume"):
            _module().allocate_floor_mirror_orders(groups, self.trades)

    def test_allocation_fails_closed_on_overclose(self) -> None:
        groups = self.open_groups.copy()
        groups.at[0, "close_matched_volumes"] = [4.0, 8.0]

        with self.assertRaisesRegex(ValueError, "overclose"):
            _module().allocate_floor_mirror_orders(groups, self.trades)

    def test_allocation_fails_closed_on_nonflat_final_open_group(self) -> None:
        groups = self.open_groups.copy()
        groups.at[0, "close_trade_ids"] = ["CLOSE.1"]
        groups.at[0, "close_matched_volumes"] = [4.0]

        with self.assertRaisesRegex(ValueError, "nonflat final open group"):
            _module().allocate_floor_mirror_orders(groups, self.trades)


class Stage137OpenMarginGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.order = pd.DataFrame(
            [
                {
                    "requested_satellite_delta": 3.0,
                    "c9_projected_total_margin_after": 90_000.0,
                    "satellite_margin_after_proposed": 1_000.0,
                    "is_open_event": 1,
                }
            ]
        )

    def test_open_gate_uses_c9_projected_margin_after_and_previous_combined_equity(self) -> None:
        gated = _module().apply_open_margin_gate(self.order, prior_combined_equity=100_000.0)

        self.assertEqual(gated.loc[0, "executed_satellite_delta"], 0)
        self.assertEqual(gated.loc[0, "margin_gate_blocked"], 1)
        self.assertAlmostEqual(gated.loc[0, "proposed_broker10_pct"], 100.1)

    def test_open_gate_allows_the_whole_order_at_exactly_one_hundred_percent(self) -> None:
        order = self.order.copy()
        order.loc[0, "c9_projected_total_margin_after"] = 89_000.0

        gated = _module().apply_open_margin_gate(order, prior_combined_equity=99_000.0)

        self.assertEqual(gated.loc[0, "executed_satellite_delta"], 3)
        self.assertEqual(gated.loc[0, "margin_gate_blocked"], 0)
        self.assertAlmostEqual(gated.loc[0, "proposed_broker10_pct"], 100.0)

    def test_open_gate_rejects_batch_or_non_open_usage(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one open event"):
            _module().apply_open_margin_gate(pd.concat([self.order, self.order]), 100_000.0)

        close = self.order.copy()
        close.loc[0, "is_open_event"] = 0
        with self.assertRaisesRegex(ValueError, "exactly one open event"):
            _module().apply_open_margin_gate(close, 100_000.0)

    def test_open_gate_fails_closed_on_missing_or_invalid_pit_values(self) -> None:
        invalid_cases = (
            ("prior_combined_equity", np.nan),
            ("prior_combined_equity", 0.0),
            ("broker_multiplier", np.inf),
            ("broker_multiplier", 0.0),
            ("requested_satellite_delta", 1.5),
            ("c9_projected_total_margin_after", np.nan),
            ("c9_projected_total_margin_after", -1.0),
            ("satellite_margin_after_proposed", np.inf),
            ("satellite_margin_after_proposed", -1.0),
        )
        for field, value in invalid_cases:
            with self.subTest(field=field, value=value):
                order = self.order.copy()
                kwargs = {
                    "prior_combined_equity": 100_000.0,
                    "broker_multiplier": 1.10,
                }
                if field in kwargs:
                    kwargs[field] = value
                else:
                    order.loc[0, field] = value
                with self.assertRaisesRegex(ValueError, "PIT margin input|integer requested_satellite_delta"):
                    _module().apply_open_margin_gate(order, **kwargs)

        with self.assertRaisesRegex(ValueError, "missing required columns"):
            _module().apply_open_margin_gate(
                self.order.drop(columns="satellite_margin_after_proposed"),
                prior_combined_equity=100_000.0,
            )


class Stage137SatelliteLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.base_daily = pd.DataFrame(
            {
                "date": pd.to_datetime(["2022-01-03", "2022-01-04"]),
                "account_equity": [150_000.0, 151_000.0],
                "total_margin_exact": [10_000.0, 12_000.0],
            }
        )
        self.price_table = pd.DataFrame(
            [
                {"date": "2022-01-03", "vt_symbol": "rb2205.SHFE", "pre_close": 100.0, "close_price": 108.0},
                {"date": "2022-01-03", "vt_symbol": "cu2205.SHFE", "pre_close": 200.0, "close_price": 190.0},
                {"date": "2022-01-04", "vt_symbol": "rb2205.SHFE", "pre_close": 108.0, "close_price": 111.0},
                {"date": "2022-01-04", "vt_symbol": "cu2205.SHFE", "pre_close": 190.0, "close_price": 195.0},
            ]
        )
        self.specs = {
            "rb2205.SHFE": {"size": 10.0, "margin_ratio": 0.10, "slippage": 1.0, "rate": 0.0001},
            "cu2205.SHFE": {"size": 5.0, "margin_ratio": 0.20, "slippage": 2.0, "rate": 0.0002},
        }
        self.candidate_orders = pd.DataFrame(
            [
                self._order("RB.OPEN", "RB.1", "rb2205.SHFE", "long", "2022-01-03 09:00:00+08:00", 102.0, 2, 10_000.0, 150_000.0),
                self._order("CU.OPEN", "CU.1", "cu2205.SHFE", "short", "2022-01-03 10:00:00+08:00", 198.0, -1, 20_000.0, 150_100.0),
                self._order("RB.PART", "RB.1", "rb2205.SHFE", "long", "2022-01-03 11:00:00+08:00", 106.0, -1),
                self._order("RB.CLOSE", "RB.1", "rb2205.SHFE", "long", "2022-01-04 09:00:00+08:00", 109.0, -1),
                self._order("CU.CLOSE", "CU.1", "cu2205.SHFE", "short", "2022-01-04 09:30:00+08:00", 192.0, 1),
            ]
        )
        self.expected_day1_gross = 2 * (106.0 - 102.0) * 10.0 + (108.0 - 106.0) * 10.0 + (-1) * (190.0 - 198.0) * 5.0
        self.expected_day1_slippage = 2 * 1.0 * 10.0 + 1 * 2.0 * 5.0 + 1 * 1.0 * 10.0
        self.expected_day1_commission = 2 * 102.0 * 10.0 * 0.0001 + 198.0 * 5.0 * 0.0002 + 106.0 * 10.0 * 0.0001
        self.expected_day2_gross = (109.0 - 108.0) * 10.0 + (-1) * (192.0 - 190.0) * 5.0
        self.expected_day2_slippage = 1 * 1.0 * 10.0 + 1 * 2.0 * 5.0
        self.expected_day2_commission = 109.0 * 10.0 * 0.0001 + 192.0 * 5.0 * 0.0002

    @staticmethod
    def _order(
        base_trade_id: str,
        open_trade_id: str,
        vt_symbol: str,
        direction: str,
        trade_datetime: str,
        trade_price: float,
        satellite_delta: int,
        c9_margin: float = np.nan,
        estimated_equity: float = np.nan,
        requested_start_month: str = "2022-01",
    ) -> dict[str, object]:
        return {
            "requested_start_month": requested_start_month,
            "base_trade_id": base_trade_id,
            "open_trade_id": open_trade_id,
            "vt_symbol": vt_symbol,
            "direction": direction,
            "trade_datetime": trade_datetime,
            "trade_price": trade_price,
            "satellite_delta": satellite_delta,
            "c9_projected_total_margin_after": c9_margin,
            "estimated_equity": estimated_equity,
        }

    def test_replay_marks_pre_close_to_each_trade_to_close_and_charges_each_order(self) -> None:
        daily, orders, audit = _module().replay_satellite_ledger(
            self.base_daily, self.price_table, self.candidate_orders, self.specs, 1.0
        )

        expected_gross = [self.expected_day1_gross, self.expected_day2_gross]
        expected_slippage = [self.expected_day1_slippage, self.expected_day2_slippage]
        expected_commission = [self.expected_day1_commission, self.expected_day2_commission]
        expected_net = [
            expected_gross[index] - expected_slippage[index] - expected_commission[index]
            for index in range(2)
        ]
        np.testing.assert_allclose(daily["satellite_gross_pnl"], expected_gross, atol=1e-12)
        np.testing.assert_allclose(daily["satellite_slippage"], expected_slippage, atol=1e-12)
        np.testing.assert_allclose(daily["satellite_commission"], expected_commission, atol=1e-12)
        np.testing.assert_allclose(daily["satellite_net_pnl"], expected_net, atol=1e-12)
        self.assertEqual(orders["executed_satellite_delta"].tolist(), [2, -1, -1, -1, 1])
        self.assertEqual(orders["slippage"].gt(0).tolist(), [True] * 5)
        self.assertEqual(orders["commission"].gt(0).tolist(), [True] * 5)
        self.assertEqual(audit["missing_price_count"], 0)
        self.assertLessEqual(audit["max_reconciliation_error"], 1e-9)

    def test_cost_multiplier_scales_slippage_only_not_commission_or_gross(self) -> None:
        one, _, _ = _module().replay_satellite_ledger(
            self.base_daily, self.price_table, self.candidate_orders, self.specs, 1.0
        )
        two, _, _ = _module().replay_satellite_ledger(
            self.base_daily, self.price_table, self.candidate_orders, self.specs, 2.0
        )

        pd.testing.assert_series_equal(one["satellite_gross_pnl"], two["satellite_gross_pnl"])
        pd.testing.assert_series_equal(one["satellite_commission"], two["satellite_commission"])
        self.assertAlmostEqual(two["satellite_slippage"].sum(), one["satellite_slippage"].sum() * 2.0)

    def test_replay_requires_positive_cost_multiplier_and_positive_risk_specs(self) -> None:
        for invalid_multiplier in (0.0, -1.0):
            with self.subTest(cost_multiplier=invalid_multiplier):
                with self.assertRaisesRegex(ValueError, "positive cost_multiplier"):
                    _module().replay_satellite_ledger(
                        self.base_daily,
                        self.price_table,
                        self.candidate_orders,
                        self.specs,
                        invalid_multiplier,
                    )

        for field in ("size", "slippage", "margin_ratio"):
            for invalid_value in (0.0, -0.01):
                with self.subTest(field=field, value=invalid_value):
                    specs = {symbol: dict(spec) for symbol, spec in self.specs.items()}
                    specs["rb2205.SHFE"][field] = invalid_value
                    with self.assertRaisesRegex(ValueError, f"positive spec value: {field}"):
                        _module().replay_satellite_ledger(
                            self.base_daily,
                            self.price_table,
                            self.candidate_orders,
                            specs,
                            1.0,
                        )

    def test_replay_accepts_explicit_zero_rate_and_charges_zero_commission(self) -> None:
        specs = {symbol: {**spec, "rate": 0.0} for symbol, spec in self.specs.items()}

        daily, orders, _ = _module().replay_satellite_ledger(
            self.base_daily, self.price_table, self.candidate_orders, specs, 1.0
        )

        self.assertTrue(daily["satellite_commission"].eq(0.0).all())
        self.assertTrue(orders["commission"].eq(0.0).all())

    def test_open_margin_uses_all_contracts_at_their_current_marks(self) -> None:
        _, orders, _ = _module().replay_satellite_ledger(
            self.base_daily, self.price_table, self.candidate_orders, self.specs, 1.0
        )

        cu_open = orders.loc[orders["base_trade_id"].eq("CU.OPEN")].iloc[0]
        expected_rb_margin = 2 * 102.0 * 10.0 * 0.10
        expected_cu_margin = 1 * 198.0 * 5.0 * 0.20
        self.assertAlmostEqual(cu_open["satellite_margin_after_proposed"], expected_rb_margin + expected_cu_margin)

    def test_same_day_later_open_uses_previous_day_c_equity_not_intraday_profit(self) -> None:
        orders = pd.DataFrame(
            [
                self._order("RB.OPEN", "RB.1", "rb2205.SHFE", "long", "2022-01-03 09:00:00+08:00", 102.0, 1, 1_000.0, 150_000.0),
                self._order("RB.WIN", "RB.1", "rb2205.SHFE", "long", "2022-01-03 10:00:00+08:00", 10_000.0, -1),
                self._order("CU.OPEN", "CU.1", "cu2205.SHFE", "short", "2022-01-03 11:00:00+08:00", 198.0, -1, 136_200.0, 300_000.0),
                self._order("CU.CLOSE", "CU.1", "cu2205.SHFE", "short", "2022-01-04 09:30:00+08:00", 192.0, 1),
            ]
        )

        _, replayed, audit = _module().replay_satellite_ledger(
            self.base_daily, self.price_table, orders, self.specs, 1.0
        )

        cu_lifecycle = replayed.loc[replayed["open_trade_id"].eq("CU.1")]
        self.assertTrue(cu_lifecycle["executed_satellite_delta"].eq(0).all())
        self.assertEqual(audit["blocked_open_trade_id_count"], 1)

    def test_blocked_close_cannot_reduce_another_lifecycle_on_same_contract(self) -> None:
        orders = pd.DataFrame(
            [
                self._order("KEEP.OPEN", "KEEP.1", "rb2205.SHFE", "long", "2022-01-03 09:00:00+08:00", 101.0, 1, 10_000.0, 150_000.0),
                self._order("BLOCK.OPEN", "BLOCK.1", "rb2205.SHFE", "long", "2022-01-03 09:01:00+08:00", 102.0, 2, 136_300.0, 150_000.0),
                self._order("BLOCK.CLOSE", "BLOCK.1", "rb2205.SHFE", "long", "2022-01-04 09:00:00+08:00", 109.0, -2),
                self._order("KEEP.CLOSE", "KEEP.1", "rb2205.SHFE", "long", "2022-01-04 09:01:00+08:00", 110.0, -1),
            ]
        )

        _, replayed, audit = _module().replay_satellite_ledger(
            self.base_daily, self.price_table, orders, self.specs, 1.0
        )

        blocked = replayed.loc[replayed["open_trade_id"].eq("BLOCK.1")]
        kept = replayed.loc[replayed["open_trade_id"].eq("KEEP.1")]
        self.assertTrue(blocked["executed_satellite_delta"].eq(0).all())
        self.assertEqual(kept["executed_satellite_delta"].tolist(), [1, -1])
        self.assertEqual(audit["blocked_open_trade_id_count"], 1)
        self.assertEqual(audit["overclose_count"], 0)

    def test_daily_b_c_net_identities_and_broker10_denominators(self) -> None:
        daily, _, audit = _module().replay_satellite_ledger(
            self.base_daily, self.price_table, self.candidate_orders, self.specs, 1.0
        )

        cumulative = daily["satellite_net_pnl"].cumsum()
        np.testing.assert_allclose(daily["satellite_cumulative_net_pnl"], cumulative, atol=1e-12)
        np.testing.assert_allclose(daily["satellite_equity"], 150_000.0 + cumulative, atol=1e-12)
        np.testing.assert_allclose(daily["combined_equity"], self.base_daily["account_equity"] + cumulative, atol=1e-12)
        self.assertAlmostEqual(daily.loc[0, "prior_combined_equity"], 150_000.0)
        self.assertAlmostEqual(daily.loc[1, "prior_combined_equity"], daily.loc[0, "combined_equity"])
        for row in daily.itertuples(index=False):
            expected_prior_pct = row.aggregate_broker10_margin / row.prior_combined_equity * 100.0
            expected_current_pct = row.aggregate_broker10_margin / row.combined_equity * 100.0
            self.assertAlmostEqual(row.aggregate_broker10_to_prior_combined_equity_pct, expected_prior_pct)
            self.assertAlmostEqual(row.aggregate_broker10_to_current_combined_equity_pct, expected_current_pct)
        self.assertLessEqual(audit["max_net_identity_error"], 1e-9)
        self.assertLessEqual(audit["max_b_equity_error"], 1e-9)
        self.assertLessEqual(audit["max_c_equity_error"], 1e-9)

    def test_replay_fails_closed_when_b_or_c_equity_is_zero_or_negative(self) -> None:
        prices = pd.DataFrame(
            [
                {
                    "date": "2022-01-03",
                    "vt_symbol": "rb2205.SHFE",
                    "pre_close": 100.0,
                    "close_price": 100.0,
                }
            ]
        )
        orders = pd.DataFrame(
            [
                self._order(
                    "OPEN.SURVIVAL",
                    "SURVIVAL.1",
                    "rb2205.SHFE",
                    "long",
                    "2022-01-03 09:00:00+08:00",
                    100.0,
                    1,
                    1_000.0,
                    150_000.0,
                ),
                self._order(
                    "CLOSE.SURVIVAL",
                    "SURVIVAL.1",
                    "rb2205.SHFE",
                    "long",
                    "2022-01-03 10:00:00+08:00",
                    100.0,
                    -1,
                ),
            ]
        )

        for target_b, slippage in ((0.0, 75_000.0), (-1.0, 75_000.5)):
            with self.subTest(ledger="B", target=target_b):
                base = pd.DataFrame(
                    [{"date": "2022-01-03", "account_equity": 300_000.0, "total_margin_exact": 1_000.0}]
                )
                specs = {
                    "rb2205.SHFE": {
                        "size": 1.0,
                        "margin_ratio": 0.10,
                        "slippage": slippage,
                        "rate": 0.0,
                    }
                }
                with self.assertRaisesRegex(ValueError, "non-positive satellite equity"):
                    _module().replay_satellite_ledger(base, prices, orders, specs, 1.0)

        for target_c, slippage in ((0.0, 50.0), (-1.0, 50.5)):
            with self.subTest(ledger="C", target=target_c):
                base = pd.DataFrame(
                    [{"date": "2022-01-03", "account_equity": 100.0, "total_margin_exact": 10.0}]
                )
                specs = {
                    "rb2205.SHFE": {
                        "size": 1.0,
                        "margin_ratio": 0.10,
                        "slippage": slippage,
                        "rate": 0.0,
                    }
                }
                with self.assertRaisesRegex(ValueError, "non-positive combined equity"):
                    _module().replay_satellite_ledger(base, prices, orders, specs, 1.0)

    def test_replay_fails_closed_on_missing_price_spec_or_duplicate_keys(self) -> None:
        cases = (
            (self.base_daily, self.price_table.loc[~((self.price_table["date"] == "2022-01-04") & (self.price_table["vt_symbol"] == "rb2205.SHFE"))], self.candidate_orders, self.specs, "missing price"),
            (self.base_daily, self.price_table, self.candidate_orders, {"rb2205.SHFE": self.specs["rb2205.SHFE"]}, "missing spec"),
            (pd.concat([self.base_daily, self.base_daily.iloc[[0]]], ignore_index=True), self.price_table, self.candidate_orders, self.specs, "duplicate base date"),
            (self.base_daily, pd.concat([self.price_table, self.price_table.iloc[[0]]], ignore_index=True), self.candidate_orders, self.specs, "duplicate price key"),
            (self.base_daily, self.price_table, pd.concat([self.candidate_orders, self.candidate_orders.iloc[[0]]], ignore_index=True), self.specs, "duplicate order key"),
        )
        for base, prices, orders, specs, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    _module().replay_satellite_ledger(base, prices, orders, specs, 1.0)

    def test_allocation_shared_close_replays_with_composite_order_identity(self) -> None:
        open_groups = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-01",
                    "open_trade_id": "OPEN.A",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "base_open_volume": 4,
                    "satellite_open_volume": 1,
                    "close_trade_ids": ["CLOSE.SHARED"],
                    "close_matched_volumes": [4],
                },
                {
                    "requested_start_month": "2022-01",
                    "open_trade_id": "OPEN.B",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "base_open_volume": 4,
                    "satellite_open_volume": 1,
                    "close_trade_ids": ["CLOSE.SHARED"],
                    "close_matched_volumes": [4],
                },
            ]
        )
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "OPEN.A",
                    "datetime": "2022-01-03 09:00:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "offset": "Open",
                    "price": 101.0,
                    "volume": 4,
                },
                {
                    "trade_id": "OPEN.B",
                    "datetime": "2022-01-03 09:01:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "offset": "Open",
                    "price": 102.0,
                    "volume": 4,
                },
                {
                    "trade_id": "CLOSE.SHARED",
                    "datetime": "2022-01-04 09:00:00+08:00",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "short",
                    "offset": "Close",
                    "price": 109.0,
                    "volume": 8,
                },
            ]
        )
        candidate_orders, allocation_audit = _module().allocate_floor_mirror_orders(open_groups, trades)
        is_open = candidate_orders["base_close_trade_id"].isna()
        candidate_orders["c9_projected_total_margin_after"] = np.where(is_open, 10_000.0, np.nan)
        candidate_orders["estimated_equity"] = np.where(is_open, 150_000.0, np.nan)

        _, replayed, replay_audit = _module().replay_satellite_ledger(
            self.base_daily,
            self.price_table.loc[self.price_table["vt_symbol"].eq("rb2205.SHFE")],
            candidate_orders,
            {"rb2205.SHFE": self.specs["rb2205.SHFE"]},
            1.0,
        )

        self.assertEqual(allocation_audit["overclose_count"], 0)
        self.assertEqual(replayed["base_trade_id"].tolist().count("CLOSE.SHARED"), 2)
        self.assertEqual(replayed["executed_satellite_delta"].tolist(), [1, 1, -1, -1])
        self.assertEqual(replay_audit["overclose_count"], 0)

    def test_nonempty_replay_requires_requested_start_month_and_full_composite_key_uniqueness(self) -> None:
        with self.assertRaisesRegex(ValueError, "requested_start_month|missing required columns"):
            _module().replay_satellite_ledger(
                self.base_daily,
                self.price_table,
                self.candidate_orders.drop(columns="requested_start_month"),
                self.specs,
                1.0,
            )

        duplicate = pd.concat([self.candidate_orders, self.candidate_orders.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate order key"):
            _module().replay_satellite_ledger(
                self.base_daily, self.price_table, duplicate, self.specs, 1.0
            )

    def test_replay_fails_closed_on_order_outside_base_dates_or_invalid_local_date(self) -> None:
        outside = self.candidate_orders.copy()
        outside.loc[outside["base_trade_id"].eq("RB.OPEN"), "trade_datetime"] = "2022-01-05 09:00:00+08:00"
        with self.assertRaisesRegex(ValueError, "outside base dates"):
            _module().replay_satellite_ledger(self.base_daily, self.price_table, outside, self.specs, 1.0)

        naive = self.candidate_orders.copy()
        naive.loc[naive["base_trade_id"].eq("RB.OPEN"), "trade_datetime"] = "2022-01-03 09:00:00"
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            _module().replay_satellite_ledger(self.base_daily, self.price_table, naive, self.specs, 1.0)

    def test_replay_fails_closed_on_non_finite_inputs_without_defaults(self) -> None:
        invalid_inputs = []
        base = self.base_daily.copy()
        base.loc[0, "account_equity"] = np.nan
        invalid_inputs.append((base, self.price_table, self.candidate_orders, self.specs, 1.0))
        prices = self.price_table.copy()
        prices.loc[0, "close_price"] = np.nan
        invalid_inputs.append((self.base_daily, prices, self.candidate_orders, self.specs, 1.0))
        orders = self.candidate_orders.copy()
        orders.loc[orders["base_trade_id"].eq("RB.OPEN"), "estimated_equity"] = np.nan
        invalid_inputs.append((self.base_daily, self.price_table, orders, self.specs, 1.0))
        specs = {symbol: dict(spec) for symbol, spec in self.specs.items()}
        specs["rb2205.SHFE"]["rate"] = np.nan
        invalid_inputs.append((self.base_daily, self.price_table, self.candidate_orders, specs, 1.0))
        invalid_inputs.append((self.base_daily, self.price_table, self.candidate_orders, self.specs, np.inf))

        for args in invalid_inputs:
            with self.subTest(args=args):
                with self.assertRaisesRegex(ValueError, "non-finite"):
                    _module().replay_satellite_ledger(*args)

        missing_key_specs = {symbol: dict(spec) for symbol, spec in self.specs.items()}
        del missing_key_specs["rb2205.SHFE"]["slippage"]
        with self.assertRaisesRegex(ValueError, "missing spec field: slippage"):
            _module().replay_satellite_ledger(
                self.base_daily, self.price_table, self.candidate_orders, missing_key_specs, 1.0
            )

    def test_replay_fails_closed_on_overclose_or_nonflat_final_holdings(self) -> None:
        overclose = self.candidate_orders.copy()
        overclose.loc[overclose["base_trade_id"].eq("RB.CLOSE"), "satellite_delta"] = -2
        with self.assertRaisesRegex(ValueError, "overclose"):
            _module().replay_satellite_ledger(self.base_daily, self.price_table, overclose, self.specs, 1.0)

        nonflat = self.candidate_orders.loc[~self.candidate_orders["base_trade_id"].eq("RB.CLOSE")]
        with self.assertRaisesRegex(ValueError, "nonflat final"):
            _module().replay_satellite_ledger(self.base_daily, self.price_table, nonflat, self.specs, 1.0)

    def test_replay_supports_an_empty_candidate_ledger_without_defaults(self) -> None:
        empty_orders = self.candidate_orders.iloc[0:0]

        daily, orders, audit = _module().replay_satellite_ledger(
            self.base_daily, self.price_table.iloc[0:0], empty_orders, {}, 1.0
        )

        self.assertTrue(orders.empty)
        self.assertEqual(daily["satellite_net_pnl"].tolist(), [0.0, 0.0])
        self.assertEqual(daily["satellite_equity"].tolist(), [150_000.0, 150_000.0])
        self.assertEqual(daily["combined_equity"].tolist(), self.base_daily["account_equity"].tolist())
        self.assertEqual(audit["blocked_open_trade_id_count"], 0)
        self.assertEqual(audit["max_reconciliation_error"], 0.0)

    def test_task1_real_empty_order_schema_replays_but_nonempty_orders_require_pit_columns(self) -> None:
        task1_empty, _ = _module().allocate_floor_mirror_orders(
            pd.DataFrame(), pd.DataFrame([{"not_a_trade": 1}])
        )
        self.assertEqual(task1_empty.columns.tolist(), ORDER_COLUMNS)

        daily, replayed, audit = _module().replay_satellite_ledger(
            self.base_daily,
            self.price_table.iloc[0:0],
            task1_empty,
            {},
            1.0,
        )

        self.assertTrue(replayed.empty)
        self.assertTrue(daily["satellite_net_pnl"].eq(0.0).all())
        self.assertEqual(audit["max_reconciliation_error"], 0.0)

        for missing_pit_column in ("c9_projected_total_margin_after", "estimated_equity"):
            with self.subTest(missing_pit_column=missing_pit_column):
                with self.assertRaisesRegex(ValueError, "missing required columns"):
                    _module().replay_satellite_ledger(
                        self.base_daily,
                        self.price_table,
                        self.candidate_orders.drop(columns=missing_pit_column),
                        self.specs,
                        1.0,
                    )

    def test_replay_rejects_empty_base_daily_explicitly(self) -> None:
        with self.assertRaisesRegex(ValueError, "^empty base_daily$"):
            _module().replay_satellite_ledger(
                self.base_daily.iloc[0:0],
                self.price_table.iloc[0:0],
                self.candidate_orders.iloc[0:0],
                {},
                1.0,
            )

    def test_blocked_lifecycle_still_fails_closed_on_requested_overclose(self) -> None:
        orders = pd.DataFrame(
            [
                self._order("BLOCK.OPEN", "BLOCK.1", "rb2205.SHFE", "long", "2022-01-03 09:01:00+08:00", 102.0, 2, 136_300.0, 150_000.0),
                self._order("BLOCK.CLOSE", "BLOCK.1", "rb2205.SHFE", "long", "2022-01-04 09:00:00+08:00", 109.0, -3),
            ]
        )

        with self.assertRaisesRegex(ValueError, "overclose"):
            _module().replay_satellite_ledger(
                self.base_daily, self.price_table, orders, self.specs, 1.0
            )

    def test_terminal_open_is_marked_to_end_without_synthetic_close_or_cost(self) -> None:
        orders = pd.DataFrame(
            [self._order("TERM.OPEN", "TERM.1", "rb2205.SHFE", "long", "2022-01-03 09:00:00+08:00", 102.0, 1, 10_000.0, 150_000.0)]
        )

        daily, replayed, audit = _module().replay_satellite_ledger(
            self.base_daily,
            self.price_table.loc[self.price_table["vt_symbol"].eq("rb2205.SHFE")],
            orders,
            {"rb2205.SHFE": self.specs["rb2205.SHFE"]},
            1.0,
            expected_terminal_positions={"TERM.1": 1},
        )

        np.testing.assert_allclose(daily["satellite_gross_pnl"], [(108.0 - 102.0) * 10.0, (111.0 - 108.0) * 10.0])
        self.assertEqual(replayed["base_trade_id"].tolist(), ["TERM.OPEN"])
        self.assertAlmostEqual(replayed["slippage"].sum(), 10.0)
        self.assertAlmostEqual(replayed["commission"].sum(), 102.0 * 10.0 * 0.0001)
        self.assertEqual(audit["expected_terminal_position_count"], 1)
        self.assertEqual(audit["unexpected_terminal_position_count"], 0)
        self.assertEqual(audit["max_terminal_position_reconciliation_error"], 0.0)
        self.assertEqual(audit["max_terminal_margin_reconciliation_error"], 0.0)
        self.assertEqual(audit["max_terminal_pnl_reconciliation_error"], 0.0)

    def test_terminal_position_mismatch_fails_but_default_contract_remains_flat(self) -> None:
        orders = pd.DataFrame(
            [self._order("TERM.OPEN", "TERM.1", "rb2205.SHFE", "long", "2022-01-03 09:00:00+08:00", 102.0, 1, 10_000.0, 150_000.0)]
        )
        args = (
            self.base_daily,
            self.price_table.loc[self.price_table["vt_symbol"].eq("rb2205.SHFE")],
            orders,
            {"rb2205.SHFE": self.specs["rb2205.SHFE"]},
            1.0,
        )
        with self.assertRaisesRegex(ValueError, "terminal position reconciliation"):
            _module().replay_satellite_ledger(*args, expected_terminal_positions={"TERM.1": 2})
        with self.assertRaisesRegex(ValueError, "nonflat final holdings"):
            _module().replay_satellite_ledger(*args)

    def test_terminal_price_audit_extends_from_open_through_base_end(self) -> None:
        orders = pd.DataFrame(
            [self._order("TERM.OPEN", "TERM.1", "rb2205.SHFE", "long", "2022-01-03 09:00:00+08:00", 102.0, 1, 10_000.0, 150_000.0)]
        )
        prices = _module()._minimal_price_audit(
            self.price_table,
            orders,
            base_dates=self.base_daily["date"],
            expected_terminal_positions={"TERM.1": 1},
        )

        self.assertEqual(prices["date"].dt.strftime("%Y-%m-%d").tolist(), ["2022-01-03", "2022-01-04"])
        self.assertEqual(prices["requested_start_month"].unique().tolist(), ["2022-01"])

        mixed = pd.concat(
            [orders, orders.assign(requested_start_month="2022-07")],
            ignore_index=True,
        )
        with self.assertRaisesRegex(ValueError, "one requested start"):
            _module()._minimal_price_audit(
                self.price_table,
                mixed,
                base_dates=self.base_daily["date"],
                expected_terminal_positions={"TERM.1": 1},
            )

    def test_minimal_price_audit_rejects_missing_middle_or_terminal_required_key(self) -> None:
        orders = pd.DataFrame(
            [self._order("TERM.OPEN", "TERM.1", "rb2205.SHFE", "long", "2022-01-03 09:00:00+08:00", 102.0, 1, 10_000.0, 150_000.0)]
        )
        base_dates = pd.Series(pd.to_datetime(["2022-01-03", "2022-01-04", "2022-01-05"]))
        complete = pd.DataFrame(
            [
                {"date": date, "vt_symbol": "rb2205.SHFE", "pre_close": 100.0 + index, "close_price": 101.0 + index}
                for index, date in enumerate(base_dates)
            ]
        )
        for missing_date in (pd.Timestamp("2022-01-04"), pd.Timestamp("2022-01-05")):
            with self.subTest(missing_date=missing_date), self.assertRaisesRegex(
                ValueError, "missing required price keys"
            ):
                _module()._minimal_price_audit(
                    complete.loc[~complete["date"].eq(missing_date)],
                    orders,
                    base_dates=base_dates,
                    expected_terminal_positions={"TERM.1": 1},
                )

    def test_minimal_price_audit_requires_positive_finite_marks(self) -> None:
        orders = pd.DataFrame(
            [self._order("TERM.OPEN", "TERM.1", "rb2205.SHFE", "long", "2022-01-03 09:00:00+08:00", 102.0, 1, 10_000.0, 150_000.0)]
        )
        prices = self.price_table.loc[self.price_table["vt_symbol"].eq("rb2205.SHFE")].copy()
        for column, value in (("pre_close", 0.0), ("pre_close", np.inf), ("close_price", -1.0), ("close_price", np.nan)):
            broken = prices.copy()
            broken.loc[broken.index[0], column] = value
            with self.subTest(column=column, value=value), self.assertRaisesRegex(
                ValueError, "positive finite price"
            ):
                _module()._minimal_price_audit(
                    broken,
                    orders,
                    base_dates=self.base_daily["date"],
                    expected_terminal_positions={"TERM.1": 1},
                )

    def test_independent_cashflow_reconciles_all_sleeve_orders_and_terminal_value(self) -> None:
        replayed = pd.DataFrame(
            [
                {"vt_symbol": "rb.SHFE", "executed_satellite_delta": 2, "trade_price": 100.0, "slippage": 10.0, "commission": 1.0},
                {"vt_symbol": "rb.SHFE", "executed_satellite_delta": -1, "trade_price": 105.0, "slippage": 10.0, "commission": 1.0},
                {"vt_symbol": "cu.SHFE", "executed_satellite_delta": -1, "trade_price": 200.0, "slippage": 5.0, "commission": 1.0},
            ]
        )
        specs = {"rb.SHFE": {"size": 10.0}, "cu.SHFE": {"size": 5.0}}
        terminal_positions = {"rb.SHFE": 1, "cu.SHFE": -1}
        final_marks = {"rb.SHFE": 110.0, "cu.SHFE": 190.0}
        expected = (
            1 * 110.0 * 10.0
            + (-1) * 190.0 * 5.0
            - (2 * 100.0 * 10.0 + (-1) * 105.0 * 10.0 + (-1) * 200.0 * 5.0)
            - 28.0
        )

        audit = _module().reconcile_sleeve_cashflow(
            replayed,
            terminal_positions,
            final_marks,
            specs,
            daily_cumulative_net_pnl=expected,
        )
        tampered = _module().reconcile_sleeve_cashflow(
            replayed,
            terminal_positions,
            final_marks,
            specs,
            daily_cumulative_net_pnl=expected + 7.0,
        )

        self.assertAlmostEqual(audit["cashflow_net_pnl"], expected)
        self.assertEqual(audit["max_terminal_pnl_reconciliation_error"], 0.0)
        self.assertEqual(tampered["max_terminal_pnl_reconciliation_error"], 7.0)


class Stage137IdentityAndRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.golden = pd.DataFrame(
            {
                "requested_start_month": ["2022-01", "2022-01"],
                "date": ["2022-01-03", "2022-01-04"],
                "account_equity": [150_010.0, 150_025.0],
                "net_pnl": [10.0, 15.0],
                "total_margin_exact": [1_000.0, 1_100.0],
            }
        )
        self.base_daily = self.golden.copy()

    def test_current_ai_golden_curve_compares_all_three_daily_fields(self) -> None:
        audit = _module().assert_current_ai_golden_curve(
            self.base_daily, self.golden, requested_start_month="2022-01"
        )
        self.assertTrue(audit["current_ai_golden_curve_pass"])
        self.assertEqual(audit["current_ai_golden_curve_date_drift_count"], 0)
        for field in ("account_equity", "net_pnl", "total_margin_exact"):
            self.assertEqual(audit[f"current_ai_golden_curve_max_{field}_error"], 0.0)

        for field in ("account_equity", "net_pnl", "total_margin_exact"):
            drifted = self.base_daily.copy()
            drifted.loc[0, field] += 1.1e-6
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "current-AI golden curve"
            ):
                _module().assert_current_ai_golden_curve(
                    drifted, self.golden, requested_start_month="2022-01"
                )

    def test_current_ai_golden_curve_rejects_exact_date_coverage_drift(self) -> None:
        with self.assertRaisesRegex(ValueError, "current-AI golden curve date coverage"):
            _module().assert_current_ai_golden_curve(
                self.base_daily.iloc[1:], self.golden, requested_start_month="2022-01"
            )

    def test_current_ai_snapshot_freezes_hash_rows_and_complete_eval_dates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "current_ai.csv"
            path.write_text(
                "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
                "current,score,2026-05-29,rb.SHFE,0.8,1,8\n"
                "current,score,2026-06-30,cu.SHFE,0.7,2,8\n",
                encoding="utf-8",
            )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            frame, audit = _module().audit_current_ai_snapshot(
                path,
                expected_sha256=digest,
                expected_rows=2,
                expected_eval_dates=("2026-05-29", "2026-06-30"),
            )
            self.assertEqual(len(frame.index), 2)
            self.assertEqual(audit["current_ai_snapshot_pass"], 1)
            self.assertEqual(audit["current_ai_snapshot_eval_date_count"], 2)

            path.write_text(
                path.read_text(encoding="utf-8").replace("0.8", "0.9"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "current AI snapshot SHA256"):
                _module().audit_current_ai_snapshot(
                    path,
                    expected_sha256=digest,
                    expected_rows=2,
                    expected_eval_dates=("2026-05-29", "2026-06-30"),
                )

    def test_current_ai_golden_membership_ignores_only_labels(self) -> None:
        current = pd.DataFrame(
            [
                {
                    "strategy": "current",
                    "score_type": "current-score",
                    "eval_date": "2026-06-30",
                    "product_vt_symbol": "rb.SHFE",
                    "score": 0.8,
                    "score_rank": 1,
                    "top_n": 8,
                }
            ]
        )
        golden = current.assign(strategy="golden", score_type="golden-score")
        audit = _module().assert_current_ai_golden_membership(current, golden)
        self.assertEqual(audit["current_ai_golden_membership_pass"], 1)
        self.assertEqual(audit["current_ai_golden_ignored_label_difference_count"], 1)

        drifted = golden.assign(score_rank=2)
        with self.assertRaisesRegex(ValueError, "current-AI golden membership"):
            _module().assert_current_ai_golden_membership(current, drifted)

        nan_key = golden.copy()
        nan_key.loc[0, "product_vt_symbol"] = np.nan
        with self.assertRaisesRegex(ValueError, "current-AI golden membership missing"):
            _module().assert_current_ai_golden_membership(current, nan_key)

    def test_canonical_frame_identity_is_key_sorted_and_type_sensitive(self) -> None:
        first = pd.DataFrame(
            {
                "trade_id": ["T2", "T1"],
                "datetime": [
                    pd.Timestamp("2022-01-04 09:00", tz="Asia/Shanghai"),
                    pd.Timestamp("2022-01-03 09:00", tz="Asia/Shanghai"),
                ],
                "volume": pd.Series([2, 1], dtype="int64"),
                "note": [pd.NA, "x"],
            }
        )
        reordered = first.iloc[::-1].reset_index(drop=True)
        identity = _module().canonical_frame_identity(
            first, "trades", key_columns=("trade_id",)
        )
        same = _module().canonical_frame_identity(
            reordered, "trades", key_columns=("trade_id",)
        )
        self.assertEqual(identity["content_sha256"], same["content_sha256"])

        changed = first.copy()
        changed.loc[0, "volume"] = 3
        different = _module().canonical_frame_identity(
            changed, "trades", key_columns=("trade_id",)
        )
        self.assertNotEqual(identity["content_sha256"], different["content_sha256"])

        dtype_changed = first.copy()
        dtype_changed["volume"] = dtype_changed["volume"].astype("float64")
        typed = _module().canonical_frame_identity(
            dtype_changed, "trades", key_columns=("trade_id",)
        )
        self.assertNotEqual(identity["content_sha256"], typed["content_sha256"])

        blank = first.copy()
        blank.loc[0, "trade_id"] = "  "
        with self.assertRaisesRegex(ValueError, "canonical identity blank key"):
            _module().canonical_frame_identity(
                blank, "trades", key_columns=("trade_id",)
            )

    def test_canonical_dict_keys_preserve_key_type(self) -> None:
        integer_key = pd.DataFrame([{"id": "A", "payload": {1: "x"}}])
        string_key = pd.DataFrame([{"id": "A", "payload": {"1": "x"}}])
        first = _module().canonical_frame_identity(
            integer_key, "dict-frame", key_columns=("id",)
        )
        second = _module().canonical_frame_identity(
            string_key, "dict-frame", key_columns=("id",)
        )
        self.assertNotEqual(first["content_sha256"], second["content_sha256"])

    def test_repeat_artifact_identity_covers_raw_and_derived_frames(self) -> None:
        artifacts = {
            "base_daily": pd.DataFrame([{"date": "2022-01-03", "account_equity": 150000.0}]),
            "positions": pd.DataFrame([{"date": "2022-01-03", "vt_symbol": "rb.SHFE", "close_price": 100.0}]),
            "trades": pd.DataFrame([{"trade_id": "T1", "datetime": "2022-01-03T09:00:00+08:00"}]),
            "entry_risk": pd.DataFrame([{"entry_index": 1, "risk": 1.0}]),
            "entry_candidates": pd.DataFrame([{"candidate_index": 1, "candidate_status": "opened"}]),
            "closed_lots": pd.DataFrame([{"open_trade_id": "T1", "close_trade_id": "T2"}]),
            "pit_source_ledger": pd.DataFrame([{"raw_risk_row_index": 0, "source_id": "R1"}]),
            "pit_candidate_audit": pd.DataFrame([{"raw_candidate_row_index": 0, "mapping_status": "opened"}]),
            "actual_open_audit": pd.DataFrame([{"raw_trade_row_index": 0, "trade_id": "T1"}]),
            "pit_binding_audit": pd.DataFrame([{"open_trade_id": "T1", "source_id": "R1"}]),
            "selected_lifecycle": pd.DataFrame([{"open_trade_id": "T1", "satellite_open_volume": 1}]),
            "candidate_orders": pd.DataFrame([{"requested_start_month": "2022-01", "open_trade_id": "T1", "base_trade_id": "T1"}]),
            "price_audit": pd.DataFrame([{"requested_start_month": "2022-01", "date": "2022-01-03", "vt_symbol": "rb.SHFE", "close_price": 100.0}]),
            "contract_specs": pd.DataFrame([{"vt_symbol": "rb.SHFE", "size": 10.0}]),
        }
        audit, ledger = _module().compare_repeat_artifacts(
            artifacts, {key: value.copy() for key, value in artifacts.items()}, "2022-01"
        )
        self.assertEqual(audit["current_c9_repeat_identity_pass"], 1)
        self.assertEqual(audit["current_c9_repeat_compared_frame_count"], len(artifacts))
        self.assertTrue(ledger["identity_match"].eq(1).all())

        drifted = {key: value.copy() for key, value in artifacts.items()}
        drifted["pit_binding_audit"].loc[0, "source_id"] = "R2"
        with self.assertRaisesRegex(ValueError, "repeat artifact identity drift"):
            _module().compare_repeat_artifacts(artifacts, drifted, "2022-01")

    def test_repeat_source_manifest_allows_mtime_only_and_rejects_sha_drift(self) -> None:
        first = pd.DataFrame(
            [{"path": "/tmp/a", "size": 10, "mtime_ns": 1, "sha256": "a" * 64}]
        )
        second = first.assign(mtime_ns=2)
        audit, ledger = _module().compare_repeat_source_manifests(
            first, second, "2022-01"
        )
        self.assertEqual(audit["repeat_source_manifest_pass"], 1)
        self.assertEqual(ledger.loc[0, "mtime_only_rewrite"], 1)

        with self.assertRaisesRegex(ValueError, "repeat source manifest drift"):
            _module().compare_repeat_source_manifests(
                first, second.assign(sha256="b" * 64), "2022-01"
            )

    def test_identity_worker_writes_isolated_payload_manifest_and_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "worker"
            metadata_path = root / "metadata.csv"
            metadata_path.write_text("symbol,size\nrb,10\n", encoding="utf-8")
            current_ai_path = root / "current_ai.csv"
            golden_ai_path = root / "golden_ai.csv"
            ai_text = (
                "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
                "current,score,2026-06-30,rb.SHFE,0.8,1,8\n"
            )
            current_ai_path.write_text(ai_text, encoding="utf-8")
            golden_ai_path.write_text(
                ai_text.replace("current,score", "golden,golden-score"),
                encoding="utf-8",
            )
            source_path = root / "source.py"
            source_path.write_text("VALUE = 1\n", encoding="utf-8")
            combined = pd.DataFrame(
                [{
                    "date": "2022-01-03",
                    "account_equity": 150_000.0,
                    "net_pnl": 0.0,
                    "total_margin_exact": 0.0,
                }]
            )
            raw_frames = {
                "positions": pd.DataFrame(),
                "trades": pd.DataFrame(),
                "entry_risk": pd.DataFrame(),
                "entry_candidates": pd.DataFrame(),
            }

            def load_metadata():
                pd.read_csv(metadata_path)
                return {"vt_symbols": []}

            runtime = SimpleNamespace(
                load_metadata=load_metadata,
                run_live_c9=lambda _metadata, _start, _end: (
                    combined,
                    raw_frames,
                    object(),
                ),
                build_closed_lots=lambda *_args: pd.DataFrame(),
                source_paths=[source_path, metadata_path, current_ai_path, golden_ai_path],
                current_ai_path=current_ai_path,
            )
            digest = hashlib.sha256(current_ai_path.read_bytes()).hexdigest()
            safe_environment = _module().effective_identity_worker_environment()
            with mock.patch.dict(
                os.environ, safe_environment, clear=True
            ), mock.patch.object(
                _module(), "_load_runtime_bridge", return_value=runtime
            ), mock.patch.object(
                _module(), "CURRENT_AI_PATH", current_ai_path
            ), mock.patch.object(
                _module(), "CURRENT_AI_GOLDEN_ELIGIBILITY_PATH", golden_ai_path
            ), mock.patch.object(
                _module(), "CURRENT_AI_EXPECTED_SHA256", digest
            ), mock.patch.object(
                _module(), "CURRENT_AI_EXPECTED_ROWS", 1
            ), mock.patch.object(
                _module(), "CURRENT_AI_EXPECTED_EVAL_DATES", ("2026-06-30",)
            ):
                _module().write_identity_worker_snapshot("2022-01", output_dir)

            self.assertTrue((output_dir / "payload.pkl").is_file())
            self.assertTrue((output_dir / "source_manifest.csv").is_file())
            self.assertTrue((output_dir / "worker.json").is_file())
            payload = pd.read_pickle(output_dir / "payload.pkl")
            self.assertEqual(payload["requested_start_month"], "2022-01")
            self.assertEqual(payload["ai_audit"]["current_ai_snapshot_pass"], 1)
            self.assertEqual(
                payload["membership_audit"]["current_ai_golden_membership_pass"], 1
            )
            self.assertIn("base_daily", payload["frames"])
            worker = json.loads((output_dir / "worker.json").read_text(encoding="utf-8"))
            self.assertEqual(worker["environment"], _module().worker_environment_contract())

    def test_identity_worker_launcher_uses_current_python_and_hidden_worker_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(
            os.environ, {"STAGE137_SECRET_FIXTURE": "must-not-leak"}
        ), mock.patch.object(_module().subprocess, "run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout="ok", stderr="")
            output_dir = Path(temp_dir) / "worker-a"
            _module().launch_identity_worker("2022-01", output_dir)

        command = run.call_args.args[0]
        self.assertEqual(command[0], sys.executable)
        self.assertIn("identity-worker", command)
        self.assertIn("--start-month", command)
        self.assertIn("2022-01", command)
        self.assertIn(str(output_dir.resolve()), command)
        self.assertTrue(run.call_args.kwargs["check"])
        child_env = run.call_args.kwargs["env"]
        self.assertNotIn("STAGE137_SECRET_FIXTURE", child_env)
        self.assertEqual(child_env["PYTHONHASHSEED"], "0")

    def test_worker_environment_contract_never_serializes_unknown_secret(self) -> None:
        with mock.patch.dict(
            os.environ, {"STAGE137_SECRET_FIXTURE": "must-not-serialize"}
        ):
            contract = _module().worker_environment_contract()
        self.assertNotIn("STAGE137_SECRET_FIXTURE", contract["process_environment_json"])
        self.assertEqual(
            hashlib.sha256(contract["process_environment_json"].encode("utf-8")).hexdigest(),
            contract["process_environment_sha256"],
        )

    def test_worker_environment_remains_exact_after_python_startup(self) -> None:
        environment = _module().identity_worker_subprocess_environment()
        completed = _module().subprocess.run(
            [
                sys.executable,
                "-c",
                "import json,os; print(json.dumps(dict(sorted(os.environ.items())), sort_keys=True))",
            ],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            json.loads(completed.stdout),
            _module().effective_identity_worker_environment(),
        )

    def test_identity_worker_timeout_is_converted_to_fail_close(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            _module().subprocess,
            "run",
            side_effect=_module().subprocess.TimeoutExpired("worker", 1800),
        ):
            with self.assertRaisesRegex(RuntimeError, "identity worker timed out"):
                _module().launch_identity_worker(
                    "2022-01", Path(temp_dir) / "worker"
                )

    def test_repeat_worker_pair_requires_distinct_process_outputs_and_same_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            launched: list[Path] = []

            def launcher(start_month: str, output_dir: Path) -> None:
                launched.append(Path(output_dir))
                output_dir.mkdir(parents=True)
                ordinal = len(launched)
                payload = {
                    "requested_start_month": start_month,
                    "analysis_end": "2026-06-30",
                    "metadata": {"vt_symbols": []},
                    "frames": {"base_daily": pd.DataFrame([{"date": "2022-01-03"}])},
                    "ai_audit": {"current_ai_snapshot_pass": 1},
                    "membership_audit": {"current_ai_golden_membership_pass": 1},
                    "environment": _module().worker_environment_contract(),
                }
                pd.to_pickle(payload, output_dir / "payload.pkl")
                pd.DataFrame(
                    [{
                        "path": "/tmp/input",
                        "size": 10,
                        "mtime_ns": ordinal,
                        "sha256": "a" * 64,
                    }]
                ).to_csv(output_dir / "source_manifest.csv", index=False)
                (output_dir / "worker.json").write_text(
                    json.dumps(
                        {
                            "requested_start_month": start_month,
                            "analysis_end": "2026-06-30",
                            "environment": payload["environment"],
                            "ai_audit": payload["ai_audit"],
                            "membership_audit": payload["membership_audit"],
                            "performance_metrics_run": False,
                        }
                    ),
                    encoding="utf-8",
                )

            pair = _module().load_repeat_worker_pair(
                "2022-01", root, launcher=launcher
            )

            self.assertEqual(len(launched), 2)
            self.assertNotEqual(launched[0], launched[1])
            self.assertEqual(pair["manifest_audit"]["repeat_source_manifest_pass"], 1)
            self.assertEqual(pair["manifest_ledger"].loc[0, "mtime_only_rewrite"], 1)
            self.assertEqual(pair["first"]["requested_start_month"], "2022-01")

    def test_repeat_worker_pair_rejects_environment_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ordinal = 0

            def launcher(start_month: str, output_dir: Path) -> None:
                nonlocal ordinal
                ordinal += 1
                output_dir.mkdir(parents=True)
                environment = _module().worker_environment_contract()
                environment["python_version"] = f"fixture-{ordinal}"
                payload = {
                    "requested_start_month": start_month,
                    "analysis_end": "2026-06-30",
                    "metadata": {},
                    "frames": {},
                    "ai_audit": {"current_ai_snapshot_pass": 1},
                    "membership_audit": {"current_ai_golden_membership_pass": 1},
                    "environment": environment,
                }
                pd.to_pickle(payload, output_dir / "payload.pkl")
                pd.DataFrame(
                    [{"path": "/tmp/input", "size": 1, "mtime_ns": 1, "sha256": "a" * 64}]
                ).to_csv(output_dir / "source_manifest.csv", index=False)
                (output_dir / "worker.json").write_text(
                    json.dumps(
                        {
                            "requested_start_month": start_month,
                            "analysis_end": "2026-06-30",
                            "environment": environment,
                            "ai_audit": payload["ai_audit"],
                            "membership_audit": payload["membership_audit"],
                            "performance_metrics_run": False,
                        }
                    ),
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(ValueError, "worker environment contract"):
                _module().load_repeat_worker_pair(
                    "2022-01", root, launcher=launcher
                )

    def test_repeat_worker_pair_resolves_default_launcher_at_call_time(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            _module(), "launch_identity_worker", side_effect=ValueError("patched launcher")
        ) as launcher:
            with self.assertRaisesRegex(ValueError, "patched launcher"):
                _module().load_repeat_worker_pair("2022-01", Path(temp_dir))
        launcher.assert_called_once()

    def test_repeat_worker_pair_rejects_incomplete_environment_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def launcher(start_month: str, output_dir: Path) -> None:
                output_dir.mkdir(parents=True)
                payload = {
                    "requested_start_month": start_month,
                    "analysis_end": "2026-06-30",
                    "metadata": {},
                    "frames": {},
                    "ai_audit": {"current_ai_snapshot_pass": 1},
                    "membership_audit": {"current_ai_golden_membership_pass": 1},
                    "environment": {"python": "fixture-only"},
                }
                pd.to_pickle(payload, output_dir / "payload.pkl")
                pd.DataFrame(
                    [{"path": "/tmp/input", "size": 1, "mtime_ns": 1, "sha256": "a" * 64}]
                ).to_csv(output_dir / "source_manifest.csv", index=False)
                (output_dir / "worker.json").write_text(
                    json.dumps(
                        {
                            "requested_start_month": start_month,
                            "analysis_end": "2026-06-30",
                            "environment": payload["environment"],
                            "ai_audit": payload["ai_audit"],
                            "membership_audit": payload["membership_audit"],
                            "performance_metrics_run": False,
                        }
                    ),
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(ValueError, "worker environment contract"):
                _module().load_repeat_worker_pair(
                    "2022-01", root, launcher=launcher
                )

    def test_final_worker_manifest_rehashes_cross_anchor_union_without_forcing_same_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            common = root / "common.csv"
            early = root / "early.csv"
            late = root / "late.csv"
            common.write_text("value\n1\n", encoding="utf-8")
            early.write_text("value\n2\n", encoding="utf-8")
            late.write_text("value\n3\n", encoding="utf-8")
            early_first = _module().build_source_manifest([common, early])
            first_mtime = common.stat().st_mtime_ns
            common.write_text("value\n1\n", encoding="utf-8")
            os.utime(
                common,
                ns=(common.stat().st_atime_ns, first_mtime + 1_000_000_000),
            )
            early_second = _module().build_source_manifest([common, early])
            late_first = _module().build_source_manifest([common, late])
            late_second = _module().build_source_manifest([common, late])

            final = _module().finalize_worker_source_manifest(
                {
                    "2020-01": [early_first, early_second],
                    "2022-01": [late_first, late_second],
                    "2022-07": [late_first, late_second],
                    "2026-01": [late_first, late_second],
                }
            )
            by_path = final.set_index("path")
            self.assertEqual(
                set(by_path.index),
                {str(common.resolve()), str(early.resolve()), str(late.resolve())},
            )
            self.assertEqual(by_path.loc[str(common.resolve()), "worker_snapshot_count"], 8)
            self.assertEqual(by_path.loc[str(early.resolve()), "worker_snapshot_count"], 2)
            self.assertEqual(by_path.loc[str(late.resolve()), "worker_snapshot_count"], 6)
            self.assertEqual(by_path.loc[str(common.resolve()), "worker_anchor_count"], 4)
            self.assertEqual(by_path.loc[str(early.resolve()), "worker_anchor_count"], 1)
            self.assertEqual(by_path.loc[str(common.resolve()), "worker_distinct_mtime_count"], 2)

            missing_from_pair = early_second.loc[
                early_second["path"].astype(str).ne(str(early.resolve()))
            ]
            with self.assertRaisesRegex(ValueError, "repeat source manifest drift"):
                _module().finalize_worker_source_manifest(
                    {
                        "2020-01": [early_first, missing_from_pair],
                        "2022-01": [late_first, late_second],
                        "2022-07": [late_first, late_second],
                        "2026-01": [late_first, late_second],
                    }
                )

            forged_late = late_first.copy()
            forged_late.loc[
                forged_late["path"].astype(str).eq(str(common.resolve())), "sha256"
            ] = "f" * 64
            with self.assertRaisesRegex(ValueError, "cross-anchor source manifest drift"):
                _module().finalize_worker_source_manifest(
                    {
                        "2020-01": [early_first, early_second],
                        "2022-01": [late_first, late_second],
                        "2022-07": [late_first, late_second],
                        "2026-01": [forged_late, forged_late.copy()],
                    }
                )

            with self.assertRaisesRegex(ValueError, "four-anchor coverage"):
                _module().finalize_worker_source_manifest(
                    {
                        "2020-01": [early_first, early_second],
                        "2026-01": [late_first, late_second],
                    }
                )

    def test_final_source_byte_validation_records_mtime_only_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.csv"
            source.write_text("value\n1\n", encoding="utf-8")
            manifest = _module().build_source_manifest([source])
            original_mtime = int(manifest.loc[0, "mtime_ns"])
            os.utime(
                source,
                ns=(source.stat().st_atime_ns, original_mtime + 1_000_000_000),
            )

            _module().assert_source_manifest_matches_bytes(manifest)

            self.assertEqual(manifest.loc[0, "post_finalization_mtime_only_rewrite"], 1)
            self.assertEqual(
                manifest.loc[0, "last_validated_mtime_ns"],
                source.stat().st_mtime_ns,
            )

            source.write_text("value\n2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "final source manifest byte drift"):
                _module().assert_source_manifest_matches_bytes(manifest)

    def test_source_manifest_csv_preserves_nanosecond_integer_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observed = root / "observed.csv"
            static = root / "static.py"
            observed.write_text("value\n1\n", encoding="utf-8")
            static.write_text("VALUE = 1\n", encoding="utf-8")
            observed_ns = 1_700_000_000_000_000_123
            static_ns = 1_700_000_000_000_000_231
            os.utime(observed, ns=(observed_ns, observed_ns))
            os.utime(static, ns=(static_ns, static_ns))
            observed_snapshot = _module()._file_snapshot(observed)
            manifest = _module().build_source_manifest(
                [observed, static],
                observed_snapshots={observed.resolve(): observed_snapshot},
            )
            for column in (
                "size",
                "mtime_ns",
                "observed_read",
                "first_read_mtime_ns",
                "last_read_mtime_ns",
                "same_content_rewrite_count",
                "post_read_same_content_rewrite",
            ):
                self.assertFalse(manifest[column].isna().any(), column)
                self.assertTrue(pd.api.types.is_integer_dtype(manifest[column]), column)

            path = root / "source_manifest.csv"
            manifest.to_csv(path, index=False, encoding="utf-8-sig")
            restored = _module().read_source_manifest_csv(path)
            by_path = restored.set_index("path")
            self.assertEqual(
                int(by_path.loc[str(observed.resolve()), "first_read_mtime_ns"]),
                observed_ns,
            )
            self.assertEqual(
                int(by_path.loc[str(static.resolve()), "last_read_mtime_ns"]),
                static_ns,
            )
            self.assertEqual(int(by_path.loc[str(static.resolve()), "observed_read"]), 0)

            final = _module().finalize_worker_source_manifest(
                {
                    start: [restored.copy(), restored.copy()]
                    for start in _module().CANARY_STARTS
                }
            )
            self.assertEqual(
                int(final["post_read_same_content_rewrite"].sum()),
                0,
            )
            final_by_path = final.set_index("path")
            self.assertEqual(
                int(final_by_path.loc[str(observed.resolve()), "last_read_mtime_ns"]),
                observed_ns,
            )

    def test_failure_diagnostic_is_structured_and_never_claims_performance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            failure_dir = Path(temp_dir) / "failures"
            path = _module().write_failure_diagnostic(
                "audit",
                ValueError("fixture fail-close"),
                failure_dir=failure_dir,
                requested_start_month="2022-01",
                phase="repeat_identity",
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["mode"], "audit")
        self.assertEqual(payload["requested_start_month"], "2022-01")
        self.assertEqual(payload["phase"], "repeat_identity")
        self.assertEqual(payload["error_type"], "ValueError")
        self.assertFalse(payload["performance_metrics_run"])
        self.assertFalse(payload["stage137_output_written"])

    def test_run_base_start_filters_daily_and_positions_without_real_engine(self) -> None:
        combined = pd.DataFrame(
            {
                "date": ["2021-12-31", "2022-01-03", "2022-01-04", "2026-07-01"],
                "account_equity": [1.0, 2.0, 3.0, 4.0],
                "net_pnl": [0.0, 1.0, 1.0, 1.0],
                "total_margin_exact": [0.0, 1.0, 1.0, 1.0],
            }
        )
        frames = {
            "positions": pd.DataFrame(
                {
                    "date": ["2021-12-31", "2022-01-03", "2022-01-05"],
                    "vt_symbol": ["rb.SHFE", "rb.SHFE", "rb.SHFE"],
                    "pre_close": [99.0, 100.0, 101.0],
                    "close_price": [100.0, 101.0, 102.0],
                }
            ),
            "trades": pd.DataFrame(),
            "entry_risk": pd.DataFrame(),
            "entry_candidates": pd.DataFrame(),
        }
        runtime = mock.Mock()
        runtime.load_metadata.return_value = {"vt_symbols": []}
        runtime.run_live_c9.return_value = (combined, frames, object())

        result = _module().run_base_start(
            pd.Timestamp("2022-01-01"), pd.Timestamp("2026-06-30"), runtime=runtime
        )

        self.assertEqual(result["base_daily"]["date"].dt.strftime("%Y-%m-%d").tolist(), ["2022-01-03", "2022-01-04"])
        self.assertEqual(result["positions"]["date"].dt.strftime("%Y-%m-%d").tolist(), ["2022-01-03"])
        self.assertTrue(result["base_daily"]["requested_start_month"].eq("2022-01").all())
        runtime.run_live_c9.assert_called_once()

    def test_run_base_captures_observed_stage149_and_fallback_csv_paths_and_restores_reader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stage149_detail = root / "stage149_contract_detail.csv"
            fallback_raw = root / "stage506_stage452_raw_minute.csv"
            stage149_detail.write_text("value\n1\n", encoding="utf-8")
            fallback_raw.write_text("value\n2\n", encoding="utf-8")
            original_read_csv = pd.read_csv
            observed: dict[Path, dict[str, object]] = {}

            def run_live_c9(_metadata, _start, _end):
                pd.read_csv(stage149_detail)
                pd.read_csv(fallback_raw)
                combined = pd.DataFrame(
                    {
                        "date": ["2022-01-03"],
                        "account_equity": [150_000.0],
                        "net_pnl": [0.0],
                        "total_margin_exact": [0.0],
                    }
                )
                return combined, {
                    "positions": pd.DataFrame(),
                    "trades": pd.DataFrame(),
                    "entry_risk": pd.DataFrame(),
                    "entry_candidates": pd.DataFrame(),
                }, object()

            runtime = SimpleNamespace(
                load_metadata=lambda: {"vt_symbols": []},
                run_live_c9=run_live_c9,
            )
            _module().run_base_start(
                pd.Timestamp("2022-01-01"),
                pd.Timestamp("2022-01-31"),
                runtime=runtime,
                observed_source_paths=observed,
            )

            self.assertEqual(set(observed), {stage149_detail.resolve(), fallback_raw.resolve()})
            for path, snapshot in observed.items():
                self.assertEqual(snapshot["path"], str(path))
                self.assertGreater(snapshot["size"], 0)
                self.assertGreater(snapshot["mtime_ns"], 0)
                self.assertEqual(len(snapshot["sha256"]), 64)
            self.assertIs(pd.read_csv, original_read_csv)

            def failing_run_live_c9(_metadata, _start, _end):
                pd.read_csv(stage149_detail)
                raise RuntimeError("fixture failure")

            runtime.run_live_c9 = failing_run_live_c9
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                _module().run_base_start(
                    pd.Timestamp("2022-01-01"),
                    pd.Timestamp("2022-01-31"),
                    runtime=runtime,
                    observed_source_paths=observed,
                )
            self.assertIs(pd.read_csv, original_read_csv)

            fallback_raw.write_text("value\nchanged\n", encoding="utf-8")
            runtime.run_live_c9 = lambda _metadata, _start, _end: pd.read_csv(fallback_raw)
            with self.assertRaisesRegex(ValueError, "observed source snapshot changed"):
                _module().run_base_start(
                    pd.Timestamp("2022-01-01"),
                    pd.Timestamp("2022-01-31"),
                    runtime=runtime,
                    observed_source_paths=observed,
                )
            self.assertIs(pd.read_csv, original_read_csv)

            stage149_detail.write_text("value\nchanged-after-read\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "observed source changed after read"):
                _module().build_source_manifest(
                    [stage149_detail, fallback_raw], observed_snapshots=observed
                )

    def test_csv_capture_rejects_same_size_same_mtime_content_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.csv"
            source.write_text("value\n1\n", encoding="utf-8")
            original_mtime = source.stat().st_mtime_ns
            real_read_csv = pd.read_csv

            def adversarial_read_csv(buffer, *args, **kwargs):
                frame = real_read_csv(buffer, *args, **kwargs)
                source.write_text("value\n2\n", encoding="utf-8")
                os.utime(
                    source,
                    ns=(source.stat().st_atime_ns, original_mtime),
                )
                return frame

            observed: dict[Path, dict[str, object]] = {}
            with mock.patch.object(
                _module().pd, "read_csv", side_effect=adversarial_read_csv
            ):
                with self.assertRaisesRegex(ValueError, "observed source changed during read"):
                    with _module().capture_pandas_read_csv_paths(observed):
                        pd.read_csv(source)
            self.assertEqual(observed, {})

    def test_source_snapshot_rejects_symlink_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "target.csv"
            link = root / "link.csv"
            target.write_text("value\n1\n", encoding="utf-8")
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, "symlink is forbidden"):
                _module()._file_snapshot(link)

    def test_metadata_and_current_ai_reads_are_snapshotted_at_read_time(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            metadata_path = root / "contract_metadata.csv"
            metadata_path.write_text("symbol,size\nrb,10\n", encoding="utf-8")
            current_ai_path = root / "current_ai.csv"
            current_ai_path.write_text(
                "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
                "current,score,2026-06-30,rb.SHFE,0.8,1,8\n",
                encoding="utf-8",
            )
            current_ai_sha = hashlib.sha256(current_ai_path.read_bytes()).hexdigest()
            observed: dict[Path, dict[str, object]] = {}
            runtime = SimpleNamespace(
                load_metadata=lambda: (
                    pd.read_csv(metadata_path),
                    {"vt_symbols": []},
                )[1]
            )

            metadata = _module().load_runtime_metadata(runtime, observed)
            current_ai, _audit = _module().audit_current_ai_snapshot(
                current_ai_path,
                expected_sha256=current_ai_sha,
                expected_rows=1,
                expected_eval_dates=("2026-06-30",),
                observed_source_paths=observed,
            )

            self.assertEqual(metadata, {"vt_symbols": []})
            self.assertEqual(len(current_ai.index), 1)
            self.assertEqual(
                set(observed), {metadata_path.resolve(), current_ai_path.resolve()}
            )

            current_ai_path.write_text(
                current_ai_path.read_text(encoding="utf-8").replace("0.8", "0.9"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "observed source changed after read"):
                _module().build_source_manifest(
                    [metadata_path, current_ai_path], observed_snapshots=observed
                )

    def test_same_content_rewrite_updates_mtime_audit_without_changing_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "generated_universe.csv"
            source.write_text("product\nrb\n", encoding="utf-8")
            observed: dict[Path, dict[str, object]] = {}

            with _module().capture_pandas_read_csv_paths(observed):
                pd.read_csv(source)
            first_mtime = source.stat().st_mtime_ns
            source.write_text("product\nrb\n", encoding="utf-8")
            os.utime(source, ns=(source.stat().st_atime_ns, first_mtime + 1_000_000_000))
            with _module().capture_pandas_read_csv_paths(observed):
                pd.read_csv(source)

            snapshot = observed[source.resolve()]
            self.assertEqual(snapshot["same_content_rewrite_count"], 1)
            self.assertNotEqual(
                snapshot["first_read_mtime_ns"], snapshot["last_read_mtime_ns"]
            )
            manifest = _module().build_source_manifest(
                [source], observed_snapshots=observed
            )
            self.assertEqual(manifest.loc[0, "observed_read"], 1)
            self.assertEqual(manifest.loc[0, "same_content_rewrite_count"], 1)
            self.assertEqual(manifest.loc[0, "post_read_same_content_rewrite"], 0)

    def test_normal_import_is_lazy_for_heavy_stage_modules(self) -> None:
        heavy = {
            "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow",
            "analyze_qmt_roll_stage719_official_winner_trade_forensics",
            "analyze_qmt_roll_stage513_stage208_exact_position_margin_audit",
        }
        self.assertTrue(heavy.isdisjoint(sys.modules))


class Stage137PitAndMetadataAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.selected = pd.DataFrame(
            [{
                "requested_start_month": "2022-01",
                "open_trade_id": "OPEN.1",
                "vt_symbol": "rb2205.SHFE",
                "direction": "long",
                "base_open_volume": 4,
                "satellite_open_volume": 1,
                "entry_date": pd.Timestamp("2022-01-03"),
                "entry_price": 100.0,
                "close_trade_ids": ["CLOSE.1"],
                "close_matched_volumes": [4],
            }]
        )
        self.closed = pd.DataFrame(
            [{
                "requested_start_month": "2022-01",
                "open_trade_id": "OPEN.1",
                "entry_context": "flat_entry",
                "layer_kind": "base",
                "ai_product_pool_allowed": 1,
                "ai_product_pool_rank": 3,
                "selected_volume": 4,
            }]
        )
        self.trades = pd.DataFrame(
            [{
                "trade_id": "OPEN.1",
                "datetime": "2022-01-03 09:01:00+08:00",
                "vt_symbol": "rb2205.SHFE",
                "direction": "Long",
                "offset": "Open",
                "volume": 4,
            }]
        )
        common = {
            "datetime": "2022-01-03 09:00:00+08:00",
            "contract_vt_symbol": "rb2205.SHFE",
            "direction": "Long",
            "entry_context": "flat_entry",
            "layer_kind": "base",
            "ai_product_pool_allowed": 1,
            "ai_product_pool_rank": 3,
            "selected_volume": 4,
            "projected_total_margin_after": 10_000.0,
            "estimated_equity": 150_000.0,
        }
        self.risks = pd.DataFrame([{**common, "entry_index": 7, "volume": 4}])
        self.candidates = pd.DataFrame([{**common, "candidate_index": 11, "candidate_status": "opened"}])

    def test_pit_binding_is_one_to_one_nonfuture_and_attaches_margin_fields(self) -> None:
        audit, bindings = _module().build_pit_binding_audit(
            self.selected, self.closed, self.trades, self.risks, self.candidates
        )
        self.assertEqual(audit.loc[0, "risk_match_count"], 1)
        self.assertEqual(audit.loc[0, "candidate_match_count"], 1)
        self.assertEqual(audit.loc[0, "future_match_count"], 0)
        self.assertEqual(bindings["OPEN.1"]["entry_index"], 7)
        orders = pd.DataFrame([{"open_trade_id": "OPEN.1", "base_trade_id": "OPEN.1", "satellite_delta": 1}])
        attached = _module().attach_pit_margin_to_orders(orders, bindings)
        self.assertEqual(attached.loc[0, "c9_projected_total_margin_after"], 10_000.0)
        self.assertEqual(attached.loc[0, "estimated_equity"], 150_000.0)

    def test_pit_binding_rejects_ambiguous_reused_future_and_selector_mismatch(self) -> None:
        duplicate = pd.concat([self.risks, self.risks.assign(entry_index=8)], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "PIT binding.*risk_match_count"):
            _module().build_pit_binding_audit(
                self.selected, self.closed, self.trades, duplicate, self.candidates
            )

        future = self.risks.assign(datetime="2022-01-03 09:02:00+08:00")
        with self.assertRaisesRegex(ValueError, "PIT binding.*future"):
            _module().build_pit_binding_audit(
                self.selected, self.closed, self.trades, future, self.candidates
            )

        mismatch = self.candidates.assign(ai_product_pool_rank=4)
        with self.assertRaisesRegex(ValueError, "PIT binding.*ai_product_pool_rank"):
            _module().build_pit_binding_audit(
                self.selected, self.closed, self.trades, self.risks, mismatch
            )

        reused_selected = pd.concat(
            [self.selected, self.selected.assign(open_trade_id="OPEN.2")], ignore_index=True
        )
        reused_trades = pd.concat(
            [self.trades, self.trades.assign(trade_id="OPEN.2")], ignore_index=True
        )
        reused_closed = pd.concat(
            [self.closed, self.closed.assign(open_trade_id="OPEN.2")], ignore_index=True
        )
        with self.assertRaisesRegex(ValueError, "PIT binding risk_match_count=0"):
            _module().build_pit_binding_audit(
                reused_selected, reused_closed, reused_trades, self.risks, self.candidates
            )

    def test_pit_binding_ignores_same_identity_future_rows_outside_five_days(self) -> None:
        later_risk = self.risks.assign(datetime="2022-01-20 09:00:00+08:00", entry_index=99)
        later_candidate = self.candidates.assign(datetime="2022-01-20 09:00:00+08:00", candidate_index=99)

        audit, bindings = _module().build_pit_binding_audit(
            self.selected,
            self.closed,
            self.trades,
            pd.concat([self.risks, later_risk], ignore_index=True),
            pd.concat([self.candidates, later_candidate], ignore_index=True),
        )

        self.assertEqual(audit.loc[0, "future_match_count"], 0)
        self.assertEqual(bindings["OPEN.1"]["entry_index"], 7)

    def test_pit_binding_uses_risk_first_candidate_fallback_and_typed_comparison(self) -> None:
        risks = self.risks.assign(
            entry_context=" Flat_Entry ",
            layer_kind=" BASE ",
            ai_product_pool_allowed=1,
            ai_product_pool_rank=np.nan,
            projected_total_margin_after=np.nan,
        )
        candidates = self.candidates.assign(
            entry_context="flat_entry",
            layer_kind="base",
            ai_product_pool_allowed=1.0,
            ai_product_pool_rank=3.0,
            projected_total_margin_after=10_000.0,
        )

        _, bindings = _module().build_pit_binding_audit(
            self.selected, self.closed, self.trades, risks, candidates
        )

        self.assertEqual(bindings["OPEN.1"]["c9_projected_total_margin_after"], 10_000.0)
        self.assertEqual(bindings["OPEN.1"]["ai_product_pool_rank"], 3.0)

        conflict = candidates.assign(ai_product_pool_allowed=0.0)
        with self.assertRaisesRegex(ValueError, "PIT binding.*conflict.*ai_product_pool_allowed"):
            _module().build_pit_binding_audit(
                self.selected, self.closed, self.trades, risks.assign(ai_product_pool_allowed=1), conflict
            )

    def test_legacy_binding_excludes_consumed_sources_and_ignores_future_when_prior_exists(self) -> None:
        selected = pd.concat(
            [self.selected, self.selected.assign(open_trade_id="OPEN.2")], ignore_index=True
        )
        closed = pd.concat(
            [self.closed, self.closed.assign(open_trade_id="OPEN.2")], ignore_index=True
        )
        trades = pd.concat(
            [
                self.trades,
                self.trades.assign(trade_id="OPEN.2", datetime="2022-01-03 09:03:00+08:00"),
            ],
            ignore_index=True,
        )
        risks = pd.concat(
            [
                self.risks,
                self.risks.assign(entry_index=8, datetime="2022-01-03 09:02:00+08:00"),
            ],
            ignore_index=True,
        )
        candidates = pd.concat(
            [
                self.candidates,
                self.candidates.assign(candidate_index=12, datetime="2022-01-03 09:02:00+08:00"),
            ],
            ignore_index=True,
        )

        _, bindings = _module().build_pit_binding_audit(
            selected, closed, trades, risks, candidates
        )

        self.assertEqual(bindings["OPEN.1"]["entry_index"], 7)
        self.assertEqual(bindings["OPEN.2"]["entry_index"], 8)

    def test_metadata_audit_records_explicit_zero_rates_and_rejects_zero_risk_specs(self) -> None:
        metadata = {
            "vt_symbols": ["rb2205.SHFE", "cu2205.SHFE"],
            "sizes": {"rb2205.SHFE": 10, "cu2205.SHFE": 5},
            "margin_ratios": {"rb2205.SHFE": 0.12, "cu2205.SHFE": 0.10},
            "slippages": {"rb2205.SHFE": 1.0, "cu2205.SHFE": 2.0},
            "rates": {"rb2205.SHFE": 0.0, "cu2205.SHFE": 0.0},
        }
        specs, audit = _module().build_contract_specs(metadata, {"rb2205.SHFE"})
        self.assertEqual(specs["rb2205.SHFE"]["rate"], 0.0)
        self.assertEqual(audit["metadata_universe_contract_count"], 2)
        self.assertEqual(audit["zero_rate_count"], 2)
        self.assertEqual(audit["zero_slippage_count"], 0)
        self.assertEqual(audit["zero_margin_ratio_count"], 0)

        for key in ("slippages", "margin_ratios"):
            broken = {
                name: dict(values) if isinstance(values, dict) else list(values)
                for name, values in metadata.items()
            }
            broken[key]["rb2205.SHFE"] = 0.0
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "metadata audit"):
                _module().build_contract_specs(broken, {"rb2205.SHFE"})


class Stage137EntryTimeCoverageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.end = pd.Timestamp("2026-06-30")
        self.base_dates = pd.Series(pd.date_range("2026-06-19", "2026-06-30", freq="D"))
        self.trades = pd.DataFrame(
            [
                self._trade("OPEN.CLOSED", "2026-06-20 00:00:00+08:00", "cu2608.SHFE", "Long", "Open", 70000.0, 8),
                self._trade("CLOSE.CLOSED", "2026-06-25 09:00:00+08:00", "cu2608.SHFE", "Short", "Close", 71000.0, 8),
                self._trade("OPEN.TERMINAL", "2026-06-23 00:00:00+08:00", "rb2610.SHFE", "Short", "Open", 3127.0, 11),
                self._trade("OPEN.PARTIAL", "2026-06-24 00:00:00+08:00", "FG609.CZCE", "Short", "Open", 967.0, 15),
                self._trade("CLOSE.PARTIAL", "2026-06-29 09:00:00+08:00", "FG609.CZCE", "Long", "Close", 978.0, 4),
                self._trade("CLOSE.JULY", "2026-07-06 09:00:00+08:00", "FG609.CZCE", "Long", "Close", 977.0, 11),
            ]
        )
        self.risks = pd.DataFrame(
            [self._pit(index, trade, candidate=False) for index, trade in enumerate(self.trades.iloc[[0, 2, 3]].to_dict("records"), 1)]
        )
        self.candidates = pd.DataFrame(
            [self._pit(index + 10, trade, candidate=True) for index, trade in enumerate(self.trades.iloc[[0, 2, 3]].to_dict("records"), 1)]
        )
        self.closed_lots = pd.DataFrame(
            [
                self._closed("OPEN.CLOSED", "CLOSE.CLOSED", "cu2608.SHFE", "long", "2026-06-25", 8),
                self._closed("OPEN.PARTIAL", "CLOSE.PARTIAL", "FG609.CZCE", "short", "2026-06-29", 4),
                self._closed("OPEN.PARTIAL", "CLOSE.JULY", "FG609.CZCE", "short", "2026-07-06", 11),
            ]
        )

    @staticmethod
    def _trade(trade_id: str, dt: str, symbol: str, direction: str, offset: str, price: float, volume: int) -> dict[str, object]:
        return {
            "trade_id": trade_id,
            "datetime": dt,
            "date": pd.Timestamp(dt).tz_convert("Asia/Shanghai").tz_localize(None).normalize(),
            "vt_symbol": symbol,
            "direction": direction,
            "offset": offset,
            "price": price,
            "volume": volume,
        }

    @staticmethod
    def _pit(index: int, trade: dict[str, object], *, candidate: bool) -> dict[str, object]:
        row = {
            "datetime": pd.Timestamp(trade["datetime"]) - pd.Timedelta(days=1),
            "contract_vt_symbol": trade["vt_symbol"],
            "direction": trade["direction"],
            "entry_context": "flat_entry",
            "layer_kind": "base",
            "ai_product_pool_allowed": 1,
            "ai_product_pool_rank": 3,
            "selected_volume": trade["volume"],
            "projected_total_margin_after": 20_000.0,
            "estimated_equity": 150_000.0,
        }
        if candidate:
            row.update({"candidate_index": index, "candidate_status": "opened"})
        else:
            row.update({"entry_index": index, "volume": trade["volume"]})
        return row

    @staticmethod
    def _closed(open_id: str, close_id: str, symbol: str, direction: str, exit_date: str, volume: int) -> dict[str, object]:
        return {
            "requested_start_month": "2026-01",
            "open_trade_id": open_id,
            "close_trade_id": close_id,
            "vt_symbol": symbol,
            "direction": direction,
            "exit_date": pd.Timestamp(exit_date),
            "volume": volume,
        }

    def test_entry_time_universe_includes_closed_partial_and_terminal_opens(self) -> None:
        groups, binding_audit, _, _, _, coverage = _module().build_entry_time_open_groups(
            self.trades,
            self.risks,
            self.candidates,
            self.closed_lots,
            base_dates=self.base_dates,
            requested_start_month="2026-01",
            analysis_end=self.end,
        )

        self.assertEqual(groups["open_trade_id"].tolist(), ["OPEN.CLOSED", "OPEN.PARTIAL", "OPEN.TERMINAL"])
        terminal = groups.set_index("open_trade_id").loc["OPEN.TERMINAL"]
        self.assertEqual(terminal["close_trade_ids"], [])
        self.assertEqual(terminal["base_remaining_volume"], 11)
        self.assertEqual(terminal["expected_terminal_satellite_position"], -2)
        partial = groups.set_index("open_trade_id").loc["OPEN.PARTIAL"]
        self.assertEqual(partial["close_trade_ids"], ["CLOSE.PARTIAL"])
        self.assertEqual(partial["base_remaining_volume"], 11)
        self.assertNotIn("CLOSE.JULY", sum(groups["close_trade_ids"].tolist(), []))
        self.assertEqual(len(binding_audit), 3)
        self.assertEqual(
            {key: coverage[key] for key in (
                "eligible_open_count",
                "selected_open_count",
                "missing_selected_open_count",
                "open_at_end_count",
                "expected_terminal_position_count",
            )},
            {
                "eligible_open_count": 3,
                "selected_open_count": 3,
                "missing_selected_open_count": 0,
                "open_at_end_count": 2,
                "expected_terminal_position_count": 2,
            },
        )
        self.assertNotIn("unexpected_terminal_position_count", coverage)

    def test_terminal_and_partial_lifecycles_emit_only_observed_orders(self) -> None:
        groups, _, _, _, _, _ = _module().build_entry_time_open_groups(
            self.trades,
            self.risks,
            self.candidates,
            self.closed_lots,
            base_dates=self.base_dates,
            requested_start_month="2026-01",
            analysis_end=self.end,
        )
        orders, audit = _module().allocate_floor_mirror_orders(groups, self.trades)

        terminal_orders = orders.loc[orders["open_trade_id"].eq("OPEN.TERMINAL")]
        self.assertEqual(terminal_orders["base_trade_id"].tolist(), ["OPEN.TERMINAL"])
        partial_orders = orders.loc[orders["open_trade_id"].eq("OPEN.PARTIAL")]
        self.assertEqual(partial_orders["base_trade_id"].tolist(), ["OPEN.PARTIAL", "CLOSE.PARTIAL"])
        self.assertEqual(partial_orders["satellite_delta"].tolist(), [-3, 1])
        self.assertNotIn("CLOSE.JULY", orders["base_trade_id"].tolist())
        self.assertEqual(audit["expected_terminal_positions"], {"OPEN.PARTIAL": -2, "OPEN.TERMINAL": -2})
        self.assertEqual(audit["unexpected_terminal_position_count"], 0)

    def test_pit_frames_are_not_trimmed_by_actual_open_windows(self) -> None:
        old_risk = self.risks.iloc[[0]].assign(datetime="2026-05-01 09:00:00+08:00", entry_index=99)
        far_candidate = self.candidates.iloc[[0]].assign(datetime="2026-07-20 09:00:00+08:00", candidate_index=99)
        risks, candidates, audit = _module().trim_pit_frames_to_open_windows(
            self.trades.loc[pd.to_datetime(self.trades["date"]).le(self.end)],
            pd.concat([self.risks, old_risk], ignore_index=True),
            pd.concat([self.candidates, far_candidate], ignore_index=True),
        )

        self.assertEqual(len(risks), 4)
        self.assertEqual(len(candidates), 4)
        self.assertEqual(audit["entry_risk_excluded_row_count"], 0)
        self.assertEqual(audit["entry_candidate_excluded_row_count"], 0)

    def test_future_rows_only_fail_for_entry_time_selected_bindings(self) -> None:
        trade = self.trades.iloc[[0]].copy()
        risk = self.risks.iloc[[0]].assign(ai_product_pool_rank=9)
        candidate = self.candidates.iloc[[0]].assign(ai_product_pool_rank=9)
        future_risk = risk.assign(datetime="2026-06-21 09:00:00+08:00", entry_index=99)
        future_candidate = candidate.assign(datetime="2026-06-21 09:00:00+08:00", candidate_index=99)

        groups, audit, source, _, _, coverage = _module().build_entry_time_open_groups(
            trade,
            pd.concat([risk, future_risk], ignore_index=True),
            pd.concat([candidate, future_candidate], ignore_index=True),
            pd.DataFrame(),
            base_dates=self.base_dates,
            requested_start_month="2026-01",
            analysis_end=self.end,
        )

        self.assertTrue(groups.empty)
        self.assertTrue(audit.empty)
        self.assertEqual(source["mapping_status"].tolist(), ["mapped", "source_without_actual"])
        self.assertEqual(coverage["eligible_open_count"], 0)

    def test_independent_source_ledger_excludes_rollover_add_and_unbacked_retry_before_mapping(self) -> None:
        flat = self._trade("OPEN.FLAT", "2026-06-20 00:00:00+08:00", "cu2608.SHFE", "Long", "Open", 70000.0, 8)
        flat["order_id"] = "ORDER.FLAT"
        rollover = self._trade("OPEN.ROLLOVER", "2026-06-21 00:00:00+08:00", "rb2610.SHFE", "Short", "Open", 3127.0, 11)
        rollover["order_id"] = "ORDER.ROLLOVER"
        regular_add = self._trade("OPEN.ADD", "2026-06-22 00:00:00+08:00", "FG609.CZCE", "Short", "Open", 967.0, 4)
        regular_add["order_id"] = "ORDER.ADD"
        retry = self._trade("OPEN.RETRY", "2026-06-20 10:00:00+08:00", "cu2608.SHFE", "Long", "Open", 70000.0, 8)
        retry["order_id"] = "ORDER.FLAT.stage847_c9.2"
        risks = pd.DataFrame(
            [
                self._pit(1, flat, candidate=False),
                {**self._pit(2, rollover, candidate=False), "entry_context": "rollover_reopen"},
                {**self._pit(3, regular_add, candidate=False), "entry_context": "regular_add"},
            ]
        )
        candidates = pd.DataFrame([self._pit(11, flat, candidate=True)])

        source, _, source_audit = _module().build_pit_risk_source_ledger(
            risks,
            candidates,
            base_dates=self.base_dates,
            requested_start_month="2026-01",
        )
        mapped, actual_audit, mapping_audit = _module().map_pit_risk_sources_to_actual_opens(
            source, pd.DataFrame([flat, retry, rollover, regular_add]), requested_start_month="2026-01"
        )

        self.assertEqual(source["entry_index"].tolist(), [1, 2, 3])
        self.assertEqual(source_audit["non_flat_base_source_count"], 2)
        self.assertEqual(mapped["mapping_status"].tolist(), ["mapped", "mapped", "mapped"])
        self.assertEqual(actual_audit["classification"].eq("synthetic_retry").sum(), 1)
        self.assertEqual(mapping_audit["retry_open_count"], 1)

        groups, _, _, _, _, coverage = _module().build_entry_time_open_groups(
            pd.DataFrame([flat, retry, rollover, regular_add]),
            risks,
            candidates,
            pd.DataFrame(),
            base_dates=self.base_dates,
            requested_start_month="2026-01",
            analysis_end=self.end,
        )
        self.assertEqual(groups["open_trade_id"].tolist(), ["OPEN.FLAT"])
        self.assertEqual(coverage["eligible_open_count"], 1)

    def test_coverage_anti_join_is_independent_from_selected_lifecycle(self) -> None:
        groups, binding_audit, _, _, _, _ = _module().build_entry_time_open_groups(
            self.trades,
            self.risks,
            self.candidates,
            self.closed_lots,
            base_dates=self.base_dates,
            requested_start_month="2026-01",
            analysis_end=self.end,
        )
        mapped_source = binding_audit.rename(columns={"open_trade_id": "open_trade_id"})
        selected_without_terminal = groups.loc[~groups["open_trade_id"].eq("OPEN.TERMINAL")]

        coverage = _module().audit_entry_time_coverage(mapped_source, selected_without_terminal)

        self.assertEqual(coverage["eligible_open_count"], 3)
        self.assertEqual(coverage["selected_open_count"], 2)
        self.assertEqual(coverage["missing_selected_open_count"], 1)
        self.assertEqual(coverage["missing_selected_open_ids"], ["OPEN.TERMINAL"])

    def test_consecutive_same_identity_opens_consume_prior_sources_before_counting(self) -> None:
        first = self._trade("OPEN.SAME.1", "2026-06-20 00:00:00+08:00", "cu2608.SHFE", "Long", "Open", 70000.0, 8)
        first["order_id"] = "ORDER.SAME.1"
        second = self._trade("OPEN.SAME.2", "2026-06-20 00:00:00+08:00", "cu2608.SHFE", "Long", "Open", 70010.0, 9)
        second["order_id"] = "ORDER.SAME.2"
        first_risk = self._pit(1, first, candidate=False)
        first_candidate = self._pit(11, first, candidate=True)
        second_risk = self._pit(2, second, candidate=False)
        second_candidate = self._pit(12, second, candidate=True)

        groups, mapped, _, _, _, coverage = _module().build_entry_time_open_groups(
            pd.DataFrame([first, second]),
            pd.DataFrame([first_risk, second_risk]),
            pd.DataFrame([first_candidate, second_candidate]),
            pd.DataFrame(),
            base_dates=self.base_dates,
            requested_start_month="2026-01",
            analysis_end=self.end,
        )

        self.assertEqual(groups["open_trade_id"].tolist(), ["OPEN.SAME.1", "OPEN.SAME.2"])
        self.assertEqual(mapped["entry_index"].tolist(), [1, 2])
        self.assertEqual(mapped["candidate_index"].tolist(), [11, 12])
        self.assertEqual(coverage["missing_selected_open_count"], 0)

    def test_source_mapping_ignores_future_after_valid_prior_but_future_only_fails(self) -> None:
        actual = self._trade("OPEN.ACTUAL", "2026-06-20 00:00:00+08:00", "cu2608.SHFE", "Long", "Open", 70000.0, 8)
        actual["order_id"] = "ORDER.ACTUAL"
        prior_risk = self._pit(1, actual, candidate=False)
        prior_candidate = self._pit(11, actual, candidate=True)
        future_risk = {**self._pit(2, actual, candidate=False), "datetime": "2026-06-20 09:02:00+08:00"}
        future_candidate = {**self._pit(12, actual, candidate=True), "datetime": "2026-06-20 09:02:00+08:00"}
        source, _, _ = _module().build_pit_risk_source_ledger(
            pd.DataFrame([prior_risk, future_risk]),
            pd.DataFrame([prior_candidate, future_candidate]),
            base_dates=self.base_dates,
            requested_start_month="2026-01",
        )

        mapped, _, audit = _module().map_pit_risk_sources_to_actual_opens(
            source, pd.DataFrame([actual]), requested_start_month="2026-01"
        )
        self.assertEqual(mapped.loc[mapped["mapping_status"].eq("mapped"), "entry_index"].tolist(), [1])
        self.assertEqual(audit["source_without_actual_open_count"], 1)

        with self.assertRaisesRegex(ValueError, "future"):
            _module().map_pit_risk_sources_to_actual_opens(
                source.loc[source["entry_index"].eq(2)],
                pd.DataFrame([actual]),
                requested_start_month="2026-01",
            )

    def test_flat_source_requires_opened_candidate_but_nonflat_sources_do_not(self) -> None:
        flat_trade = self._trade("OPEN.FLAT", "2026-06-20 00:00:00+08:00", "cu2608.SHFE", "Long", "Open", 70000.0, 8)
        flat_risk = pd.DataFrame([self._pit(1, flat_trade, candidate=False)])
        with self.assertRaisesRegex(ValueError, "candidate_match_count=0"):
            _module().build_pit_risk_source_ledger(
                flat_risk,
                pd.DataFrame(),
                base_dates=self.base_dates,
                requested_start_month="2026-01",
            )

        rollover_risk = flat_risk.assign(entry_context="rollover_reopen")
        source, _, audit = _module().build_pit_risk_source_ledger(
            rollover_risk,
            pd.DataFrame(),
            base_dates=self.base_dates,
            requested_start_month="2026-01",
        )
        self.assertEqual(source["source_classification"].tolist(), ["non_flat_base"])
        self.assertEqual(audit["non_flat_base_source_count"], 1)

    def test_unknown_actual_open_without_risk_is_not_treated_as_retry(self) -> None:
        unknown = self._trade("OPEN.UNKNOWN", "2026-06-20 00:00:00+08:00", "cu2608.SHFE", "Long", "Open", 70000.0, 8)
        unknown["order_id"] = "ORDER.UNKNOWN"

        with self.assertRaisesRegex(ValueError, "unmapped nonretry actual Open"):
            _module().build_entry_time_open_groups(
                pd.DataFrame([unknown]),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
                base_dates=self.base_dates,
                requested_start_month="2026-01",
                analysis_end=self.end,
            )


class Stage137Review3RiskSourceMappingTest(unittest.TestCase):
    base_dates = pd.Series(pd.to_datetime(["2026-01-05", "2026-01-06"]))

    @staticmethod
    def _risk(
        index: int,
        symbol: str,
        volume: int,
        *,
        context: str = "flat_entry",
        dt: str = "2026-01-05 15:00:00+08:00",
    ) -> dict[str, object]:
        return {
            "entry_index": index,
            "datetime": dt,
            "contract_vt_symbol": symbol,
            "direction": "Long",
            "volume": volume,
            "entry_context": context,
            "layer_kind": "base",
            "ai_product_pool_allowed": 1,
            "ai_product_pool_rank": 3,
            "selected_volume": volume,
            "projected_total_margin_after": 20_000.0,
            "estimated_equity": 150_000.0,
        }

    @staticmethod
    def _candidate(index: int, risk: dict[str, object]) -> dict[str, object]:
        return {
            "candidate_index": index,
            "datetime": risk["datetime"],
            "contract_vt_symbol": risk["contract_vt_symbol"],
            "direction": risk["direction"],
            "candidate_status": "opened",
            "selected_volume": risk["volume"],
            "entry_context": risk["entry_context"],
            "layer_kind": risk["layer_kind"],
            "ai_product_pool_allowed": risk["ai_product_pool_allowed"],
            "ai_product_pool_rank": risk["ai_product_pool_rank"],
            "projected_total_margin_after": risk["projected_total_margin_after"],
            "estimated_equity": risk["estimated_equity"],
        }

    @staticmethod
    def _open(
        trade_id: str,
        symbol: str,
        volume: int,
        *,
        dt: str = "2026-01-06 00:00:00+08:00",
        order_id: str | None = None,
    ) -> dict[str, object]:
        return {
            "trade_id": trade_id,
            "order_id": order_id or f"ORDER.{trade_id}",
            "datetime": dt,
            "date": pd.Timestamp(dt).tz_convert("Asia/Shanghai").tz_localize(None).normalize(),
            "vt_symbol": symbol,
            "direction": "Long",
            "offset": "Open",
            "price": 100.0,
            "volume": volume,
        }

    def _build_source(
        self,
        risks: list[dict[str, object]],
        candidates: list[dict[str, object]],
        *,
        base_dates: pd.Series | None = None,
    ) -> tuple[pd.DataFrame, dict[str, object]]:
        source, _candidate_audit, audit = _module().build_pit_risk_source_ledger(
            pd.DataFrame(risks),
            pd.DataFrame(candidates),
            base_dates=self.base_dates if base_dates is None else base_dates,
            requested_start_month="2026-01",
        )
        return source, audit

    def test_retry_and_rollover_before_eligible_cannot_be_consumed_by_eligible_source(self) -> None:
        rollover = self._risk(1, "rb2605.SHFE", 4, context="rollover_reopen")
        eligible = self._risk(2, "rb2605.SHFE", 8)
        source, _ = self._build_source([rollover, eligible], [self._candidate(12, eligible)])
        retry = self._open(
            "OPEN.RETRY",
            "rb2605.SHFE",
            8,
            dt="2026-01-06 08:59:00+08:00",
            order_id="ORDER.BASE.stage847_c9.2",
        )
        rollover_open = self._open(
            "OPEN.ROLLOVER", "rb2605.SHFE", 4, dt="2026-01-06 00:00:00+08:00"
        )
        eligible_open = self._open(
            "OPEN.ELIGIBLE", "rb2605.SHFE", 8, dt="2026-01-06 00:00:00+08:00"
        )

        ledger, actual, audit = _module().map_pit_risk_sources_to_actual_opens(
            source,
            pd.DataFrame([retry, rollover_open, eligible_open]),
            requested_start_month="2026-01",
        )

        by_entry = ledger.set_index("entry_index")
        self.assertEqual(by_entry.loc[1, "actual_open_trade_id"], "OPEN.ROLLOVER")
        self.assertEqual(by_entry.loc[2, "actual_open_trade_id"], "OPEN.ELIGIBLE")
        self.assertEqual(actual.set_index("trade_id").loc["OPEN.RETRY", "classification"], "synthetic_retry")
        self.assertEqual(actual.set_index("trade_id").loc["OPEN.ROLLOVER", "classification"], "mapped_non_flat_base")
        self.assertEqual(audit["retry_open_count"], 1)
        self.assertEqual(audit["mapped_rollover_open_count"], 1)

    def test_holiday_next_base_date_and_unique_volume_drift_are_explicit(self) -> None:
        base_dates = pd.Series(pd.to_datetime(["2026-02-13", "2026-02-24"]))
        risk = self._risk(
            1,
            "ag2606.SHFE",
            35,
            dt="2026-02-13 15:00:00+08:00",
        )
        source, _ = self._build_source(
            [risk], [self._candidate(11, risk)], base_dates=base_dates
        )
        actual_open = self._open(
            "OPEN.DRIFT",
            "ag2606.SHFE",
            21,
            dt="2026-02-24 00:00:00+08:00",
        )

        ledger, actual, audit = _module().map_pit_risk_sources_to_actual_opens(
            source, pd.DataFrame([actual_open]), requested_start_month="2026-01"
        )

        self.assertEqual(pd.Timestamp(source.loc[0, "expected_execution_date"]), pd.Timestamp("2026-02-24"))
        self.assertEqual(ledger.loc[0, "mapping_status"], "mapped")
        self.assertEqual(ledger.loc[0, "risk_volume"], 35)
        self.assertEqual(ledger.loc[0, "actual_open_volume"], 21)
        self.assertEqual(ledger.loc[0, "volume_drift"], -14)
        self.assertEqual(actual.loc[0, "volume_drift"], -14)
        self.assertEqual(audit["volume_drift_count"], 1)

    def test_crossed_volumes_follow_producer_sequence_instead_of_volume_identity(self) -> None:
        rollover = self._risk(1, "rb2605.SHFE", 8, context="rollover_reopen")
        eligible = self._risk(
            2,
            "rb2605.SHFE",
            4,
            dt="2026-01-05 15:01:00+08:00",
        )
        source, _ = self._build_source(
            [rollover, eligible], [self._candidate(12, eligible)]
        )
        first_actual = self._open(
            "OPEN.FIRST", "rb2605.SHFE", 4, dt="2026-01-06 00:00:00+08:00"
        )
        second_actual = self._open(
            "OPEN.SECOND", "rb2605.SHFE", 3, dt="2026-01-06 00:00:00+08:00"
        )

        ledger, actual, audit = _module().map_pit_risk_sources_to_actual_opens(
            source,
            pd.DataFrame([first_actual, second_actual]),
            requested_start_month="2026-01",
        )

        by_entry = ledger.set_index("entry_index")
        self.assertEqual(by_entry.loc[1, "actual_open_trade_id"], "OPEN.FIRST")
        self.assertEqual(by_entry.loc[2, "actual_open_trade_id"], "OPEN.SECOND")
        self.assertEqual(by_entry["source_sequence"].tolist(), [1, 2])
        self.assertEqual(by_entry["actual_sequence"].tolist(), [1, 2])
        self.assertTrue(by_entry["source_order_match"].eq(1).all())
        self.assertEqual(
            actual.set_index("trade_id").loc["OPEN.FIRST", "entry_context"],
            "rollover_reopen",
        )
        self.assertEqual(audit["source_order_mismatch_count"], 0)
        self.assertEqual(audit["positive_volume_drift_count"], 0)

    def test_positive_volume_drift_and_partial_key_counts_fail_closed(self) -> None:
        risk = self._risk(1, "cu2605.SHFE", 4)
        source, _ = self._build_source([risk], [self._candidate(11, risk)])
        with self.assertRaisesRegex(ValueError, "positive volume drift"):
            _module().map_pit_risk_sources_to_actual_opens(
                source,
                pd.DataFrame([self._open("OPEN.POSITIVE", "cu2605.SHFE", 5)]),
                requested_start_month="2026-01",
            )

        second = self._risk(
            2,
            "cu2605.SHFE",
            9,
            dt="2026-01-05 15:01:00+08:00",
        )
        two_sources, _ = self._build_source(
            [risk, second],
            [self._candidate(11, risk), self._candidate(12, second)],
        )
        with self.assertRaisesRegex(ValueError, "source/actual count mismatch"):
            _module().map_pit_risk_sources_to_actual_opens(
                two_sources,
                pd.DataFrame([self._open("OPEN.ONE", "cu2605.SHFE", 4)]),
                requested_start_month="2026-01",
            )

    def test_duplicate_source_sequence_fails_closed(self) -> None:
        first = self._risk(1, "cu2605.SHFE", 8)
        second = self._risk(
            2,
            "cu2605.SHFE",
            9,
            dt="2026-01-05 15:01:00+08:00",
        )
        source, _ = self._build_source(
            [first, second],
            [self._candidate(11, first), self._candidate(12, second)],
        )
        source["source_sequence"] = 1
        actual = pd.DataFrame(
            [
                self._open("OPEN.ONE", "cu2605.SHFE", 7, dt="2026-01-06 00:00:00+08:00"),
                self._open("OPEN.TWO", "cu2605.SHFE", 6, dt="2026-01-06 00:00:00+08:00"),
            ]
        )

        with self.assertRaisesRegex(ValueError, "source_sequence"):
            _module().map_pit_risk_sources_to_actual_opens(
                source, actual, requested_start_month="2026-01"
            )

    def test_source_without_actual_is_retained_and_unmapped_nonretry_fails(self) -> None:
        mapped_risk = self._risk(1, "cu2605.SHFE", 8)
        no_actual_risk = self._risk(2, "zn2605.SHFE", 6)
        source, _ = self._build_source(
            [mapped_risk, no_actual_risk],
            [self._candidate(11, mapped_risk), self._candidate(12, no_actual_risk)],
        )
        ledger, _, audit = _module().map_pit_risk_sources_to_actual_opens(
            source,
            pd.DataFrame([self._open("OPEN.MAPPED", "cu2605.SHFE", 8)]),
            requested_start_month="2026-01",
        )

        self.assertEqual(
            ledger.set_index("entry_index").loc[2, "mapping_status"],
            "source_without_actual",
        )
        self.assertEqual(audit["source_without_actual_open_count"], 1)
        self.assertEqual(audit["quality_source_without_actual_open_count"], 1)

        unknown = self._open("OPEN.UNKNOWN", "au2606.SHFE", 3)
        with self.assertRaisesRegex(ValueError, "unmapped nonretry actual Open"):
            _module().map_pit_risk_sources_to_actual_opens(
                source, pd.DataFrame([unknown]), requested_start_month="2026-01"
            )

    def test_candidate_audit_projects_matched_skipped_and_orphan_opened_rows(self) -> None:
        risk = self._risk(1, "cu2605.SHFE", 8)
        matched = self._candidate(11, risk)
        skipped = {
            **self._candidate(12, risk),
            "candidate_index": 12,
            "candidate_status": "skipped",
        }
        orphan = self._candidate(13, self._risk(99, "zn2605.SHFE", 6))

        source, candidate_audit, audit = _module().build_pit_risk_source_ledger(
            pd.DataFrame([risk]),
            pd.DataFrame([matched, skipped, orphan]),
            base_dates=self.base_dates,
            requested_start_month="2026-01",
        )

        self.assertEqual(len(source), 1)
        self.assertEqual(len(candidate_audit), 3)
        by_index = candidate_audit.set_index("candidate_index")
        self.assertEqual(by_index.loc[11, "mapping_status"], "matched_risk_source")
        self.assertEqual(
            by_index.loc[11, "matched_risk_source_id"], source.loc[0, "source_id"]
        )
        self.assertEqual(by_index.loc[12, "mapping_status"], "skipped_candidate")
        self.assertEqual(
            by_index.loc[13, "mapping_status"], "opened_candidate_without_risk"
        )
        for column in (
            "raw_candidate_row_index",
            "candidate_datetime",
            "contract_vt_symbol",
            "direction",
            "candidate_status",
            "selected_volume",
            "ai_product_pool_allowed",
            "ai_product_pool_rank",
            "projected_total_margin_after",
            "estimated_equity",
        ):
            self.assertIn(column, candidate_audit)
        self.assertEqual(audit["risk_input_count"], 1)
        self.assertEqual(audit["pit_source_ledger_row_count"], 1)
        self.assertEqual(audit["candidate_input_count"], 3)
        self.assertEqual(audit["pit_candidate_audit_row_count"], 3)
        self.assertEqual(audit["opened_candidate_count"], 2)
        self.assertEqual(audit["skipped_candidate_count"], 1)
        self.assertEqual(audit["opened_candidate_without_risk_count"], 1)

    def test_candidate_status_and_raw_identifiers_are_strict(self) -> None:
        risk = self._risk(1, "cu2605.SHFE", 8)
        for status in ("", np.nan, "open", "blocked"):
            candidate = {**self._candidate(11, risk), "candidate_status": status}
            with self.subTest(status=status), self.assertRaisesRegex(
                ValueError, "candidate_status"
            ):
                _module().build_pit_risk_source_ledger(
                    pd.DataFrame([risk]),
                    pd.DataFrame([candidate]),
                    base_dates=self.base_dates,
                    requested_start_month="2026-01",
                )

        for field, bad_value in (("entry_index", ""), ("entry_index", np.nan)):
            bad_risk = {**risk, field: bad_value}
            with self.subTest(field=field, bad_value=bad_value), self.assertRaisesRegex(
                ValueError, field
            ):
                _module().build_pit_risk_source_ledger(
                    pd.DataFrame([bad_risk]),
                    pd.DataFrame([self._candidate(11, bad_risk)]),
                    base_dates=self.base_dates,
                    requested_start_month="2026-01",
                )

        duplicate_risk = {**self._risk(1, "zn2605.SHFE", 6)}
        with self.assertRaisesRegex(ValueError, "duplicate entry_index"):
            _module().build_pit_risk_source_ledger(
                pd.DataFrame([risk, duplicate_risk]),
                pd.DataFrame(
                    [self._candidate(11, risk), self._candidate(12, duplicate_risk)]
                ),
                base_dates=self.base_dates,
                requested_start_month="2026-01",
            )

        for candidate_index in ("", np.nan):
            bad_candidate = {
                **self._candidate(11, risk),
                "candidate_index": candidate_index,
            }
            with self.subTest(candidate_index=candidate_index), self.assertRaisesRegex(
                ValueError, "candidate_index"
            ):
                _module().build_pit_risk_source_ledger(
                    pd.DataFrame([risk]),
                    pd.DataFrame([bad_candidate]),
                    base_dates=self.base_dates,
                    requested_start_month="2026-01",
                )

        duplicate_candidates = pd.DataFrame(
            [self._candidate(11, risk), self._candidate(11, risk)]
        )
        with self.assertRaisesRegex(ValueError, "duplicate candidate_index"):
            _module().build_pit_risk_source_ledger(
                pd.DataFrame([risk]),
                duplicate_candidates,
                base_dates=self.base_dates,
                requested_start_month="2026-01",
            )

    def test_all_raw_trade_prices_must_be_positive_finite(self) -> None:
        for price in (0.0, -1.0, np.nan, np.inf):
            trade = self._open("CLOSE.BAD", "cu2605.SHFE", 1)
            trade.update({"offset": "Close", "price": price})
            with self.subTest(price=price), self.assertRaisesRegex(
                ValueError, "positive finite raw trade price"
            ):
                _module().build_entry_time_open_groups(
                    pd.DataFrame([trade]),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    base_dates=self.base_dates,
                    requested_start_month="2026-01",
                    analysis_end=pd.Timestamp("2026-06-30"),
                )

    def test_retry_marker_and_local_midnight_must_agree_before_sequence_mapping(self) -> None:
        risk = self._risk(1, "cu2605.SHFE", 8)
        source, _ = self._build_source([risk], [self._candidate(11, risk)])
        renamed_intraday = self._open(
            "OPEN.RENAMED",
            "cu2605.SHFE",
            8,
            dt="2026-01-06 09:00:00+08:00",
            order_id="ORDER.RENAMED",
        )
        with self.assertRaisesRegex(ValueError, "non-midnight Open missing retry marker"):
            _module().map_pit_risk_sources_to_actual_opens(
                source,
                pd.DataFrame([renamed_intraday]),
                requested_start_month="2026-01",
            )

        midnight_marker = self._open(
            "OPEN.BAD.MARKER",
            "cu2605.SHFE",
            8,
            dt="2026-01-06 00:00:00+08:00",
            order_id="ORDER.BASE.stage847_c9.2",
        )
        with self.assertRaisesRegex(ValueError, "retry marker at local midnight"):
            _module().map_pit_risk_sources_to_actual_opens(
                source,
                pd.DataFrame([midnight_marker]),
                requested_start_month="2026-01",
            )

    def test_future_and_ambiguous_mapping_fail_closed(self) -> None:
        risk = self._risk(1, "cu2605.SHFE", 8)
        source, _ = self._build_source([risk], [self._candidate(11, risk)])
        early = self._open(
            "OPEN.EARLY", "cu2605.SHFE", 8, dt="2026-01-05 00:00:00+08:00"
        )
        with self.assertRaisesRegex(ValueError, "future"):
            _module().map_pit_risk_sources_to_actual_opens(
                source, pd.DataFrame([early]), requested_start_month="2026-01"
            )

        second_risk = self._risk(2, "cu2605.SHFE", 9)
        ambiguous_source, _ = self._build_source(
            [risk, second_risk],
            [self._candidate(11, risk), self._candidate(12, second_risk)],
        )
        drift = self._open("OPEN.AMBIGUOUS", "cu2605.SHFE", 7)
        with self.assertRaisesRegex(ValueError, "source/actual count mismatch"):
            _module().map_pit_risk_sources_to_actual_opens(
                ambiguous_source,
                pd.DataFrame([drift]),
                requested_start_month="2026-01",
            )

    def test_stage847_structural_counts_map_365_nonretry_and_preserve_two_sources(self) -> None:
        drift_pairs = [(35, 21), (13, 5), (298, 164), (500, 259), (494, 281)]
        risks: list[dict[str, object]] = []
        candidates: list[dict[str, object]] = []
        actual_opens: list[dict[str, object]] = []
        for index in range(367):
            symbol = f"S{index:03d}.SHFE"
            risk_volume = drift_pairs[index - 20][0] if 20 <= index < 25 else index + 2
            context = "rollover_reopen" if index < 12 else "flat_entry"
            risk = self._risk(index, symbol, risk_volume, context=context)
            risks.append(risk)
            if context == "flat_entry":
                candidates.append(self._candidate(index + 1000, risk))
            if index < 365:
                actual_volume = drift_pairs[index - 20][1] if 20 <= index < 25 else risk_volume
                actual_opens.append(self._open(f"OPEN.{index:03d}", symbol, actual_volume))
        for index in range(23):
            actual_opens.append(
                self._open(
                    f"RETRY.{index:03d}",
                    f"S{index + 30:03d}.SHFE",
                    index + 32,
                    dt=f"2026-01-06 08:{index:02d}:00+08:00",
                    order_id=f"ORDER.{index}.stage847_c9.2",
                )
            )

        source, source_audit = self._build_source(risks, candidates)
        ledger, actual, audit = _module().map_pit_risk_sources_to_actual_opens(
            source, pd.DataFrame(actual_opens), requested_start_month="2026-01"
        )

        self.assertEqual(source_audit["pit_risk_source_count"], 367)
        self.assertEqual(audit["mapped_nonretry_open_count"], 365)
        self.assertEqual(audit["retry_open_count"], 23)
        self.assertEqual(audit["source_without_actual_open_count"], 2)
        self.assertEqual(audit["quality_source_without_actual_open_count"], 2)
        self.assertEqual(audit["mapped_rollover_open_count"], 12)
        self.assertEqual(audit["volume_drift_count"], 5)
        self.assertEqual(audit["positive_volume_drift_count"], 0)
        self.assertEqual(audit["source_order_mismatch_count"], 0)
        drifts = ledger.loc[ledger["volume_drift"].ne(0), ["risk_volume", "actual_open_volume"]]
        self.assertEqual([tuple(row) for row in drifts.to_numpy().tolist()], drift_pairs)
        self.assertTrue(ledger.loc[ledger["mapping_status"].eq("mapped"), "source_order_match"].eq(1).all())
        self.assertEqual(actual["classification"].eq("synthetic_retry").sum(), 23)

    def test_entry_time_coverage_counts_only_mapped_quality_sources(self) -> None:
        eligible = self._risk(1, "cu2605.SHFE", 8)
        no_actual = self._risk(2, "zn2605.SHFE", 6)
        rollover = self._risk(3, "rb2605.SHFE", 4, context="rollover_reopen")
        trades = pd.DataFrame(
            [
                self._open("OPEN.ELIGIBLE", "cu2605.SHFE", 8),
                self._open("OPEN.ROLLOVER", "rb2605.SHFE", 4),
                self._open(
                    "OPEN.RETRY",
                    "cu2605.SHFE",
                    8,
                    dt="2026-01-06 08:59:00+08:00",
                    order_id="ORDER.BASE.stage847_c9.2",
                ),
            ]
        )
        groups, bindings, source, candidate_audit, actual, coverage = _module().build_entry_time_open_groups(
            trades,
            pd.DataFrame([eligible, no_actual, rollover]),
            pd.DataFrame(
                [self._candidate(11, eligible), self._candidate(12, no_actual)]
            ),
            pd.DataFrame(),
            base_dates=self.base_dates,
            requested_start_month="2026-01",
            analysis_end=pd.Timestamp("2026-06-30"),
        )

        self.assertEqual(groups["open_trade_id"].tolist(), ["OPEN.ELIGIBLE"])
        self.assertEqual(bindings["open_trade_id"].tolist(), ["OPEN.ELIGIBLE"])
        self.assertEqual(len(source), 3)
        self.assertEqual(len(candidate_audit), 2)
        self.assertEqual(len(actual), 3)
        self.assertEqual(coverage["eligible_open_count"], 1)
        self.assertEqual(coverage["mapped_eligible_open_count"], 1)
        self.assertEqual(coverage["selected_open_count"], 1)
        self.assertEqual(coverage["mapped_nonretry_open_count"], 2)
        self.assertEqual(coverage["quality_source_without_actual_open_count"], 1)
        self.assertEqual(coverage["retry_open_count"], 1)
        self.assertEqual(coverage["unmapped_actual_open_count"], 0)
        self.assertEqual(coverage["future_match_count"], 0)


class Stage137CanaryAndCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.summary = pd.DataFrame(
            [
                self._summary("2020-01", -40.0, -35.0, 500, 450, 10.0),
                self._summary("2022-01", -45.0, -40.0, 400, 350, 5.0),
                self._summary("2022-07", -30.0, -25.0, 300, 300, 3.0),
                self._summary("2026-01", -8.0, -8.5, 50, 55, -1.0),
            ]
        )
        self.audits = pd.DataFrame([self._audit(start) for start in ("2020-01", "2022-01", "2022-07", "2026-01")])

    @staticmethod
    def _summary(start: str, a_dd: float, c_dd: float, a_uw: int, c_uw: int, b_pnl: float) -> dict[str, object]:
        row: dict[str, object] = {
            "requested_start_month": start,
            "cost_multiplier": 1.0,
            "a_total_return_pct": 100.0,
            "c_total_return_pct": 80.0,
            "return_retention_pct": 80.0,
            "a_max_drawdown_pct": a_dd,
            "c_max_drawdown_pct": c_dd,
            "a_longest_underwater_days": a_uw,
            "c_longest_underwater_days": c_uw,
            "b_cumulative_net_pnl": b_pnl,
            "b_bankrupt": 0,
            "c_bankrupt": 0,
        }
        for prefix in ("a", "b", "c"):
            row.update({
                f"{prefix}_final_equity": 200_000.0,
                f"{prefix}_sharpe": 1.0,
                f"{prefix}_total_slippage": 10.0,
                f"{prefix}_total_commission": 0.0,
                f"{prefix}_total_trade_count": 10,
                f"{prefix}_nonzero_daily_win_rate_pct": 50.0,
            })
        row.update({
            "b_total_return_pct": 10.0,
            "b_max_drawdown_pct": -5.0,
            "b_longest_underwater_days": 20,
        })
        return row

    @staticmethod
    def _audit(start: str) -> dict[str, object]:
        return {
            "requested_start_month": start,
            "cost_multiplier": 1.0,
            "current_ai_snapshot_pass": 1,
            "current_ai_golden_membership_pass": 1,
            "current_ai_golden_curve_applicable": int(start == "2020-01"),
            "current_ai_golden_curve_pass": 1,
            "current_c9_repeat_identity_pass": 1,
            "repeat_source_manifest_pass": 1,
            "repeat_worker_environment_pass": 1,
            "pit_binding_fail_count": 0,
            "future_match_count": 0,
            "actual_open_count": 1,
            "actual_open_input_count": 1,
            "actual_open_audit_row_count": 1,
            "mapped_nonretry_open_count": 1,
            "unmapped_actual_open_count": 0,
            "retry_open_count": 0,
            "pit_risk_source_count": 1,
            "risk_input_count": 1,
            "pit_source_ledger_row_count": 1,
            "source_without_actual_open_count": 0,
            "candidate_input_count": 1,
            "pit_candidate_audit_row_count": 1,
            "opened_candidate_count": 1,
            "skipped_candidate_count": 0,
            "opened_candidate_without_risk_count": 0,
            "source_order_mismatch_count": 0,
            "positive_volume_drift_count": 0,
            "duplicate_satellite_open_count": 0,
            "overclose_count": 0,
            "nonflat_final_open_group_count": 0,
            "missing_price_count": 0,
            "fallback_count": 0,
            "silent_default_count": 0,
            "max_reconciliation_error": 0.0,
            "max_proposed_broker10_pct": 90.0,
            "max_eod_broker10_prior_pct": 90.0,
            "max_eod_broker10_current_pct": 90.0,
            "replay_bankrupt_count": 0,
            "input_audit_pass": 1,
            "eligible_open_count": 1,
            "mapped_eligible_open_count": 1,
            "selected_open_count": 1,
            "missing_selected_open_count": 0,
            "unexpected_selected_open_count": 0,
            "quality_source_without_actual_open_count": 0,
            "open_at_end_count": 0,
            "expected_terminal_position_count": 0,
            "unexpected_terminal_position_count": 0,
            "max_terminal_position_reconciliation_error": 0.0,
            "max_terminal_margin_reconciliation_error": 0.0,
            "max_terminal_pnl_reconciliation_error": 0.0,
        }

    def test_canary_implements_every_conjunctive_gate(self) -> None:
        decision = _module().evaluate_canary(self.summary, self.audits)
        self.assertTrue(decision["canary_pass"])
        self.assertEqual(decision["failed_checks"], [])

        mutations = {
            "current_ai_snapshot_failed": ("audit", "current_ai_snapshot_pass", 0),
            "current_ai_golden_membership_failed": ("audit", "current_ai_golden_membership_pass", 0),
            "current_ai_golden_curve_failed": ("audit", "current_ai_golden_curve_pass", 0),
            "current_c9_repeat_identity_failed": ("audit", "current_c9_repeat_identity_pass", 0),
            "repeat_source_manifest_failed": ("audit", "repeat_source_manifest_pass", 0),
            "repeat_worker_environment_failed": ("audit", "repeat_worker_environment_pass", 0),
            "pit_binding_failed": ("audit", "pit_binding_fail_count", 1),
            "future_pit_match": ("audit", "future_match_count", 1),
            "order_lifecycle_failed": ("audit", "overclose_count", 1),
            "missing_or_defaulted_input": ("audit", "missing_price_count", 1),
            "reconciliation_failed": ("audit", "max_reconciliation_error", 1e-4),
            "broker10_exceeded": ("audit", "max_eod_broker10_current_pct", 100.1),
            "bankrupt": ("audit", "replay_bankrupt_count", 1),
            "return_retention_below_70": ("summary", "return_retention_pct", 69.9),
            "input_audit_failed": ("audit", "input_audit_pass", 0),
            "coverage_failed": ("audit", "missing_selected_open_count", 1),
            "coverage_failed_mapped_count": ("audit", "mapped_eligible_open_count", 0),
            "actual_open_mapping_failed": ("audit", "unmapped_actual_open_count", 1),
            "actual_open_audit_incomplete": ("audit", "actual_open_audit_row_count", 0),
            "actual_open_classification_incomplete": ("audit", "retry_open_count", 1),
            "source_ledger_incomplete": ("audit", "pit_risk_source_count", 2),
            "risk_ledger_incomplete": ("audit", "pit_source_ledger_row_count", 0),
            "candidate_audit_incomplete": ("audit", "pit_candidate_audit_row_count", 0),
            "source_order_mismatch": ("audit", "source_order_mismatch_count", 1),
            "positive_volume_drift": ("audit", "positive_volume_drift_count", 1),
            "opened_candidate_without_risk": ("audit", "opened_candidate_without_risk_count", 1),
            "terminal_reconciliation_failed": ("audit", "unexpected_terminal_position_count", 1),
            "terminal_margin_reconciliation_failed": ("audit", "max_terminal_margin_reconciliation_error", 1e-4),
            "terminal_pnl_reconciliation_failed": ("audit", "max_terminal_pnl_reconciliation_error", 1e-4),
        }
        for expected, (kind, column, value) in mutations.items():
            summary = self.summary.copy()
            audits = self.audits.copy()
            target = summary if kind == "summary" else audits
            target.loc[0, column] = value
            with self.subTest(expected=expected):
                failed = _module().evaluate_canary(summary, audits)
                self.assertIn(
                    "coverage_failed" if expected == "coverage_failed_mapped_count" else expected,
                    failed["failed_checks"],
                )

    def test_static_audit_gate_requires_complete_mapping_and_coverage(self) -> None:
        decision = _module().evaluate_static_audit(self.audits)
        self.assertTrue(decision["audit_pass"])
        self.assertEqual(decision["failed_checks"], ["canary_not_run"])

        mutations = {
            "future_pit_match": ("future_match_count", 1),
            "actual_open_mapping_failed": ("unmapped_actual_open_count", 1),
            "actual_open_audit_incomplete": ("actual_open_audit_row_count", 0),
            "actual_open_classification_incomplete": ("retry_open_count", 1),
            "source_ledger_incomplete": ("pit_risk_source_count", 2),
            "risk_ledger_incomplete": ("pit_source_ledger_row_count", 0),
            "candidate_audit_incomplete": ("pit_candidate_audit_row_count", 0),
            "source_order_mismatch": ("source_order_mismatch_count", 1),
            "positive_volume_drift": ("positive_volume_drift_count", 1),
            "opened_candidate_without_risk": ("opened_candidate_without_risk_count", 1),
            "coverage_failed": ("mapped_eligible_open_count", 0),
            "coverage_failed_unexpected": ("unexpected_selected_open_count", 1),
        }
        for expected, (column, value) in mutations.items():
            audits = self.audits.copy()
            audits.loc[0, column] = value
            with self.subTest(expected=expected):
                failed = _module().evaluate_static_audit(audits)
                self.assertFalse(failed["audit_pass"])
                self.assertIn(
                    "coverage_failed" if expected == "coverage_failed_unexpected" else expected,
                    failed["failed_checks"],
                )

    def test_canary_requires_all_historical_drawdowns_and_2022_underwater_gates(self) -> None:
        summary = self.summary.copy()
        summary.loc[summary["requested_start_month"].eq("2022-07"), "c_max_drawdown_pct"] = -30.0
        decision = _module().evaluate_canary(summary, self.audits)
        self.assertIn("historical_drawdown_not_strictly_better", decision["failed_checks"])
        self.assertIn("2022_drawdown_not_strictly_better", decision["failed_checks"])

        summary = self.summary.copy()
        summary.loc[summary["requested_start_month"].eq("2022-01"), "c_longest_underwater_days"] = 401
        decision = _module().evaluate_canary(summary, self.audits)
        self.assertIn("2022_underwater_worse", decision["failed_checks"])

    def test_canary_requires_latest_drawdown_and_positive_b_across_anchors(self) -> None:
        summary = self.summary.copy()
        summary.loc[summary["requested_start_month"].eq("2026-01"), "c_max_drawdown_pct"] = -9.1
        self.assertIn("latest_drawdown_worse_over_1pp", _module().evaluate_canary(summary, self.audits)["failed_checks"])

        summary = self.summary.copy()
        summary.loc[summary["requested_start_month"].isin(["2020-01", "2022-01"]), "b_cumulative_net_pnl"] = -1.0
        failed = _module().evaluate_canary(summary, self.audits)["failed_checks"]
        self.assertIn("b_positive_below_3_of_4", failed)
        self.assertIn("b_2022_not_both_positive", failed)

    def test_bankrupt_replay_exception_is_converted_to_failed_decision(self) -> None:
        audit = _module().bankrupt_failure_audit("2022-01", 1.0, ValueError("non-positive combined equity"))
        audits = self.audits.copy()
        audits.loc[audits["requested_start_month"].eq("2022-01"), list(audit)] = list(audit.values())
        summary = self.summary.copy()
        summary.loc[summary["requested_start_month"].eq("2022-01"), ["b_bankrupt", "c_bankrupt"]] = [0, 1]
        decision = _module().evaluate_canary(summary, audits)
        self.assertFalse(decision["canary_pass"])
        self.assertIn("bankrupt", decision["failed_checks"])
        self.assertIn("non-positive combined equity", decision["bankrupt_reasons"])

    def test_cli_modes_do_not_mix_and_full_is_gate_closed(self) -> None:
        with mock.patch.object(_module(), "run_stage") as run_stage:
            _module().main("audit")
            run_stage.assert_called_once_with("audit")
        with mock.patch.object(_module(), "run_stage") as run_stage:
            _module().main("canary")
            run_stage.assert_called_once_with("canary")
        with self.assertRaisesRegex(ValueError, "full.*gate"):
            _module().main("full")

    def test_run_stage_rethrows_ordinary_value_error_without_writing(self) -> None:
        with mock.patch.object(
            _module(),
            "load_repeat_worker_pair",
            side_effect=ValueError("ordinary input failure"),
        ), mock.patch.object(_module(), "write_stage_outputs") as writer:
            with self.assertRaisesRegex(ValueError, "ordinary input failure"):
                _module().run_stage("audit")
        writer.assert_not_called()


class Stage137MetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.daily = pd.DataFrame(
            {
                "date": pd.to_datetime(["2022-01-03", "2022-01-04"]),
                "account_equity": [140_000.0, 145_000.0],
                "satellite_equity": [145_000.0, 150_000.0],
                "combined_equity": [135_000.0, 145_000.0],
                "satellite_cumulative_net_pnl": [-5_000.0, 0.0],
                "slippage": [100.0, 200.0],
                "commission": [10.0, 20.0],
                "trade_count": [2, 3],
                "satellite_slippage": [5.0, 7.0],
                "satellite_commission": [1.0, 2.0],
                "satellite_executed_order_count": [1, 2],
            }
        )

    def test_drawdown_and_underwater_use_initial_capital_as_time_zero(self) -> None:
        drawdown = _module()._drawdown_pct(self.daily["account_equity"])
        self.assertAlmostEqual(drawdown.iloc[0], -10000.0 / 150000.0 * 100.0)
        self.assertAlmostEqual(drawdown.min(), -10000.0 / 150000.0 * 100.0)
        self.assertEqual(
            _module()._longest_underwater_days(self.daily["date"], self.daily["account_equity"]),
            1,
        )

    def test_summary_contains_complete_a_b_c_metrics(self) -> None:
        summary = _module().summarize_start(self.daily, "2022-01", 1.0)

        expected_columns = {
            f"{prefix}_{metric}"
            for prefix in ("a", "b", "c")
            for metric in (
                "final_equity",
                "total_return_pct",
                "max_drawdown_pct",
                "sharpe",
                "total_slippage",
                "total_commission",
                "total_trade_count",
                "nonzero_daily_win_rate_pct",
                "longest_underwater_days",
            )
        }
        self.assertTrue(expected_columns.issubset(summary))
        self.assertEqual((summary["a_final_equity"], summary["b_final_equity"], summary["c_final_equity"]), (145_000.0, 150_000.0, 145_000.0))
        self.assertAlmostEqual(summary["a_max_drawdown_pct"], -10_000.0 / 150_000.0 * 100.0)
        self.assertAlmostEqual(summary["b_max_drawdown_pct"], -5_000.0 / 150_000.0 * 100.0)
        self.assertAlmostEqual(summary["c_max_drawdown_pct"], -15_000.0 / 150_000.0 * 100.0)
        self.assertEqual((summary["a_total_slippage"], summary["b_total_slippage"], summary["c_total_slippage"]), (300.0, 12.0, 312.0))
        self.assertEqual((summary["a_total_commission"], summary["b_total_commission"], summary["c_total_commission"]), (30.0, 3.0, 33.0))
        self.assertEqual((summary["a_total_trade_count"], summary["b_total_trade_count"], summary["c_total_trade_count"]), (5, 3, 8))
        self.assertEqual((summary["a_nonzero_daily_win_rate_pct"], summary["b_nonzero_daily_win_rate_pct"], summary["c_nonzero_daily_win_rate_pct"]), (50.0, 50.0, 50.0))
        self.assertTrue(np.isfinite([summary["a_sharpe"], summary["b_sharpe"], summary["c_sharpe"]]).all())

    def test_report_contains_complete_summary_and_zero_rate_limitation(self) -> None:
        summary = pd.DataFrame([_module().summarize_start(self.daily, "2022-01", 1.0)])
        report = _module()._report_text(
            {
                "summary": summary,
                "input_audit": pd.DataFrame([{"zero_rate_count": 783}]),
                "decision": {"mode": "canary", "canary_pass": False, "failed_checks": ["fixture"]},
            }
        )

        for token in ("a_final_equity", "b_sharpe", "c_total_trade_count", "a_longest_underwater_days"):
            self.assertIn(token, report)
        self.assertIn("不声称覆盖了非零手续费", report)


class Stage137OutputContractTest(unittest.TestCase):
    def test_static_audit_empty_performance_frames_have_machine_readable_schemas(self) -> None:
        frames = {
            "base_daily": pd.DataFrame(
                columns=["requested_start_month", "date", "account_equity"]
            ),
            "candidate_orders": pd.DataFrame(columns=ORDER_COLUMNS),
            "satellite_daily": pd.DataFrame(),
            "replayed_orders": pd.DataFrame(),
        }
        _module().attach_static_audit_empty_performance_schemas(frames)
        self.assertTrue(frames["satellite_daily"].empty)
        self.assertTrue(frames["replayed_orders"].empty)
        self.assertIn("satellite_cumulative_net_pnl", frames["satellite_daily"].columns)
        self.assertIn("executed_satellite_delta", frames["replayed_orders"].columns)
        with tempfile.TemporaryDirectory() as temp_dir:
            for name in ("satellite_daily", "replayed_orders"):
                path = Path(temp_dir) / f"{name}.csv"
                frames[name].to_csv(path, index=False, encoding="utf-8-sig")
                restored = pd.read_csv(path, encoding="utf-8-sig")
                self.assertEqual(restored.columns.tolist(), frames[name].columns.tolist())
                self.assertTrue(restored.empty)

    def test_source_manifest_hashes_references_without_copying_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "input.csv"
            source.write_text("a,b\n1,2\n", encoding="utf-8")
            manifest = _module().build_source_manifest([source])
        self.assertEqual(manifest.loc[0, "path"], str(source.resolve()))
        self.assertEqual(manifest.loc[0, "size"], 8)
        self.assertEqual(len(manifest.loc[0, "sha256"]), 64)

    def test_runtime_manifest_paths_include_database_and_settings_under_current_trader_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            trader_dir = Path(temp_dir)
            runtime_dir = trader_dir / ".vntrader"
            runtime_dir.mkdir()
            database = runtime_dir / "database.db"
            settings = runtime_dir / "vt_setting.json"
            database.write_bytes(b"sqlite fixture")
            settings.write_text("{}", encoding="utf-8")

            paths = _module().trader_state_source_paths(trader_dir)
            manifest = _module().build_source_manifest(paths)

        self.assertEqual(set(manifest["path"]), {str(database.resolve()), str(settings.resolve())})

    def test_manifest_includes_required_producers_and_loaded_transitive_local_modules(self) -> None:
        required = {
            "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
            "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py",
            "analyze_qmt_roll_stage513_stage208_exact_position_margin_audit.py",
            "analyze_qmt_roll_stage719_official_winner_trade_forensics.py",
            "analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap.py",
            "qmt_roll_portfolio_strategy.py",
        }
        self.assertTrue(required.issubset({path.name for path in _module()._STATIC_SOURCE_PATHS}))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            examples = root / "examples" / "portfolio_backtesting"
            package = root / "vnpy" / "app"
            outside = root / "outside"
            examples.mkdir(parents=True)
            package.mkdir(parents=True)
            outside.mkdir()
            producer = examples / "producer.py"
            strategy = package / "strategy.py"
            ignored = outside / "ignored.py"
            for path in (producer, strategy, ignored):
                path.write_text("VALUE = 1\n", encoding="utf-8")
            modules = [
                SimpleNamespace(__file__=str(producer)),
                SimpleNamespace(__file__=str(strategy)),
                SimpleNamespace(__file__=str(ignored)),
                SimpleNamespace(),
            ]

            paths = _module().collect_loaded_local_source_paths(
                modules=modules, repo_root=root
            )

        self.assertEqual(set(paths), {producer.resolve(), strategy.resolve()})

    def test_audit_writer_persists_static_ledgers_without_terminal_replay_columns(self) -> None:
        bundle = {
            key: pd.DataFrame()
            for key in _module()._PERSISTED_FRAME_FILES
        }
        bundle.update(
            {
                "base_daily": pd.DataFrame(
                    [{"requested_start_month": "2026-01", "date": "2026-01-05"}]
                ),
                "pit_source_ledger": pd.DataFrame(
                    [
                        {
                            "requested_start_month": "2026-01",
                            "source_id": "risk:1",
                            "mapping_status": "source_without_actual",
                        }
                    ]
                ),
                "pit_candidate_audit": pd.DataFrame(
                    columns=["requested_start_month", "candidate_index", "mapping_status"]
                ),
                "actual_open_audit": pd.DataFrame(
                    columns=["requested_start_month", "trade_id", "classification"]
                ),
                "summary": pd.DataFrame(columns=["requested_start_month"]),
                "reconciliation": pd.DataFrame(
                    columns=["requested_start_month", "cost_multiplier"]
                ),
                "input_audit": pd.DataFrame(
                    [
                        {
                            "requested_start_month": "2026-01",
                            "cost_multiplier": 1.0,
                            "input_audit_pass": 1,
                            "eligible_open_count": 0,
                            "mapped_eligible_open_count": 0,
                            "selected_open_count": 0,
                            "missing_selected_open_count": 0,
                            "unexpected_selected_open_count": 0,
                            "unmapped_actual_open_count": 0,
                            "future_match_count": 0,
                            "source_order_mismatch_count": 0,
                            "positive_volume_drift_count": 0,
                            "opened_candidate_without_risk_count": 0,
                            "risk_input_count": 1,
                            "pit_source_ledger_row_count": 1,
                            "candidate_input_count": 0,
                            "pit_candidate_audit_row_count": 0,
                            "opened_candidate_count": 0,
                            "skipped_candidate_count": 0,
                            "actual_open_input_count": 0,
                            "actual_open_audit_row_count": 0,
                            "open_at_end_count": 0,
                            "expected_terminal_position_count": 0,
                        }
                    ]
                ),
                "decision": {
                    "mode": "audit",
                    "audit_pass": True,
                    "canary_pass": False,
                    "failed_checks": ["canary_not_run"],
                    "full_allowed": False,
                },
            }
        )
        _complete_identity_output_bundle(bundle)

        replay_terminal_columns = {
            "unexpected_terminal_position_count",
            "max_terminal_position_reconciliation_error",
            "max_terminal_margin_reconciliation_error",
            "max_terminal_pnl_reconciliation_error",
        }
        self.assertTrue(replay_terminal_columns.isdisjoint(bundle["input_audit"].columns))
        self.assertTrue(replay_terminal_columns.isdisjoint(bundle["fifo_audit"].columns))

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "audit-output"
            _module().write_stage_outputs(bundle, output_dir)

            self.assertTrue((output_dir / "pit_source_ledger.csv").is_file())
            self.assertTrue((output_dir / "pit_candidate_audit.csv").is_file())
            self.assertTrue((output_dir / "actual_open_audit.csv").is_file())
            self.assertEqual(pd.read_csv(output_dir / "summary.csv").empty, True)
            self.assertEqual(pd.read_csv(output_dir / "reconciliation.csv").empty, True)
            for chart in ("equity.png", "drawdown.png", "focus_2022.png"):
                self.assertGreater((output_dir / chart).stat().st_size, 0)
            self.assertIn(
                "canary metrics not run",
                (output_dir / "report.md").read_text(encoding="utf-8"),
            )

    def test_failed_output_swap_restores_previous_complete_directory(self) -> None:
        bundle = {
            "base_daily": pd.DataFrame([{"requested_start_month": "2022-01", "date": "2022-01-03"}]),
            "selected_lifecycle": pd.DataFrame(),
            "pit_source_ledger": pd.DataFrame(),
            "pit_candidate_audit": pd.DataFrame(),
            "actual_open_audit": pd.DataFrame(),
            "pit_binding_audit": pd.DataFrame(),
            "candidate_orders": pd.DataFrame(),
            "replayed_orders": pd.DataFrame(),
            "satellite_daily": pd.DataFrame(),
            "price_audit": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "input_audit": pd.DataFrame([{
                "input_audit_pass": 1,
                "zero_rate_count": 783,
                "eligible_open_count": 0,
                "mapped_eligible_open_count": 0,
                "selected_open_count": 0,
                "missing_selected_open_count": 0,
                "unexpected_selected_open_count": 0,
                "unmapped_actual_open_count": 0,
                "future_match_count": 0,
                "source_order_mismatch_count": 0,
                "positive_volume_drift_count": 0,
                "opened_candidate_without_risk_count": 0,
                "risk_input_count": 0,
                "pit_source_ledger_row_count": 0,
                "candidate_input_count": 0,
                "pit_candidate_audit_row_count": 0,
                "opened_candidate_count": 0,
                "skipped_candidate_count": 0,
                "actual_open_input_count": 0,
                "actual_open_audit_row_count": 0,
                "open_at_end_count": 0,
                "expected_terminal_position_count": 0,
                "unexpected_terminal_position_count": 0,
                "max_terminal_position_reconciliation_error": 0.0,
            }]),
            "reconciliation": pd.DataFrame(),
            "fifo_audit": pd.DataFrame(),
            "margin_audit": pd.DataFrame(),
            "current_ai_audit": pd.DataFrame(),
            "repeat_identity_audit": pd.DataFrame(),
            "repeat_source_manifest": pd.DataFrame(),
            "source_manifest": pd.DataFrame(),
            "decision": {"mode": "audit", "canary_pass": False, "failed_checks": ["canary_not_run"]},
        }
        _complete_identity_output_bundle(bundle)
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            output_dir.mkdir()
            (output_dir / "previous-complete.txt").write_text("keep", encoding="utf-8")
            real_replace = _module().os.replace
            failed = False

            def flaky_replace(source, destination):
                nonlocal failed
                source_path = Path(source)
                destination_path = Path(destination)
                if destination_path == output_dir and ".backup" not in source_path.name and not failed:
                    failed = True
                    raise OSError("swap failed")
                return real_replace(source, destination)

            with mock.patch.object(_module(), "_write_charts"), mock.patch.object(
                _module().os, "replace", side_effect=flaky_replace
            ):
                with self.assertRaisesRegex(OSError, "swap failed"):
                    _module().write_stage_outputs(bundle, output_dir)

            self.assertEqual((output_dir / "previous-complete.txt").read_text(encoding="utf-8"), "keep")
            self.assertFalse(any("backup" in path.name for path in Path(temp_dir).iterdir()))

    def test_output_writer_rejects_empty_identity_evidence(self) -> None:
        bundle = {
            key: pd.DataFrame() for key in _module()._PERSISTED_FRAME_FILES
        }
        bundle["base_daily"] = pd.DataFrame(
            columns=["requested_start_month", "date", "account_equity"]
        )
        bundle["candidate_orders"] = pd.DataFrame(columns=ORDER_COLUMNS)
        coverage = {
            "cost_multiplier": 1.0,
            "input_audit_pass": 1,
            "eligible_open_count": 0,
            "mapped_eligible_open_count": 0,
            "selected_open_count": 0,
            "missing_selected_open_count": 0,
            "unexpected_selected_open_count": 0,
            "unmapped_actual_open_count": 0,
            "future_match_count": 0,
            "source_order_mismatch_count": 0,
            "positive_volume_drift_count": 0,
            "opened_candidate_without_risk_count": 0,
            "risk_input_count": 0,
            "pit_source_ledger_row_count": 0,
            "candidate_input_count": 0,
            "pit_candidate_audit_row_count": 0,
            "opened_candidate_count": 0,
            "skipped_candidate_count": 0,
            "actual_open_input_count": 0,
            "actual_open_audit_row_count": 0,
            "open_at_end_count": 0,
            "expected_terminal_position_count": 0,
        }
        bundle["input_audit"] = pd.DataFrame(
            [
                {
                    **coverage,
                    "requested_start_month": start,
                    **_identity_input_fields(start),
                }
                for start in _module().CANARY_STARTS
            ]
        )
        bundle["decision"] = {
            "mode": "audit",
            "audit_pass": True,
            "canary_pass": False,
            "failed_checks": ["canary_not_run"],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            with self.assertRaisesRegex(ValueError, "current AI audit"):
                _module().write_stage_outputs(bundle, output_dir)
            self.assertFalse(output_dir.exists())

    def test_identity_writer_rejects_nan_manifest_and_unrelated_repeat_paths(self) -> None:
        bundle: dict[str, object] = {
            "input_audit": pd.DataFrame(
                [
                    {
                        "requested_start_month": start,
                        **_identity_input_fields(start),
                    }
                    for start in _module().CANARY_STARTS
                ]
            ),
            **_identity_output_frames(),
        }
        _module().validate_identity_output_evidence(bundle)

        nan_manifest = dict(bundle)
        nan_manifest["source_manifest"] = bundle["source_manifest"].assign(size=np.nan)
        with self.assertRaisesRegex(ValueError, "source manifest invalid numeric"):
            _module().validate_identity_output_evidence(nan_manifest)

        unrelated = dict(bundle)
        unrelated["repeat_source_manifest"] = bundle["repeat_source_manifest"].assign(
            path="/tmp/unrelated"
        )
        with self.assertRaisesRegex(ValueError, "repeat source manifest path coverage"):
            _module().validate_identity_output_evidence(unrelated)

        missing_hash = dict(bundle)
        missing_hash["repeat_identity_audit"] = bundle["repeat_identity_audit"].drop(
            columns=["first_content_sha256"]
        )
        with self.assertRaisesRegex(ValueError, "repeat identity audit incomplete"):
            _module().validate_identity_output_evidence(missing_hash)

        forged_identity = dict(bundle)
        forged_identity["repeat_identity_audit"] = bundle[
            "repeat_identity_audit"
        ].assign(second_content_sha256="c" * 64)
        with self.assertRaisesRegex(ValueError, "repeat identity audit hash mismatch"):
            _module().validate_identity_output_evidence(forged_identity)

        environment_drift = dict(bundle)
        environment_rows = bundle["current_ai_audit"].copy()
        environment_rows.loc[
            environment_rows["requested_start_month"].astype(str).eq("2026-01"),
            "repeat_worker_environment_sha256",
        ] = "f" * 64
        environment_drift["current_ai_audit"] = environment_rows
        with self.assertRaisesRegex(ValueError, "worker environment SHA256 drift"):
            _module().validate_identity_output_evidence(environment_drift)

        with tempfile.TemporaryDirectory() as temp_dir:
            forged_path = Path(temp_dir) / "forged-source.csv"
            forged_path.write_text("value\n1\n", encoding="utf-8")
            snapshot = _module()._file_snapshot(forged_path)
            forged_source = dict(bundle)
            forged_source["source_manifest"] = pd.concat(
                [
                    bundle["source_manifest"],
                    pd.DataFrame(
                        [{
                            "path": str(forged_path.resolve()),
                            "size": snapshot["size"],
                            "mtime_ns": snapshot["mtime_ns"],
                            "sha256": "f" * 64,
                        }]
                    ),
                ],
                ignore_index=True,
            )
            forged_source["repeat_source_manifest"] = pd.concat(
                [
                    bundle["repeat_source_manifest"],
                    pd.DataFrame(
                        [
                            {
                                "requested_start_month": start,
                                "path": str(forged_path.resolve()),
                                "size": snapshot["size"],
                                "sha256": "f" * 64,
                                "content_identity_match": 1,
                            }
                            for start in _module().CANARY_STARTS
                        ]
                    ),
                ],
                ignore_index=True,
            )
            with self.assertRaisesRegex(ValueError, "final source manifest byte drift"):
                _module().validate_identity_output_evidence(forged_source)

    def test_identity_writer_accepts_anchor_specific_source_subsets_and_rejects_overlap_drift(self) -> None:
        bundle: dict[str, object] = {
            "input_audit": pd.DataFrame(
                [
                    {
                        "requested_start_month": start,
                        **_identity_input_fields(start),
                    }
                    for start in _module().CANARY_STARTS
                ]
            ),
            **_identity_output_frames(),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            early = root / "early-only.csv"
            late = root / "late-only.csv"
            shared = root / "shared.csv"
            early.write_text("value\n1\n", encoding="utf-8")
            late.write_text("value\n2\n", encoding="utf-8")
            shared.write_text("value\n3\n", encoding="utf-8")
            snapshots = {
                path.name: _module()._file_snapshot(path)
                for path in (early, late, shared)
            }
            source_manifest = pd.concat(
                [
                    bundle["source_manifest"],
                    pd.DataFrame(list(snapshots.values())),
                ],
                ignore_index=True,
            )
            repeat_rows = [
                {
                    "requested_start_month": start,
                    "path": snapshot["path"],
                    "size": snapshot["size"],
                    "sha256": snapshot["sha256"],
                    "content_identity_match": 1,
                }
                for start, names in {
                    "2020-01": ("early-only.csv", "shared.csv"),
                    "2022-01": ("shared.csv",),
                    "2022-07": ("shared.csv",),
                    "2026-01": ("late-only.csv", "shared.csv"),
                }.items()
                for snapshot in (snapshots[name] for name in names)
            ]
            subset_bundle = dict(bundle)
            subset_bundle["source_manifest"] = source_manifest
            subset_bundle["repeat_source_manifest"] = pd.concat(
                [bundle["repeat_source_manifest"], pd.DataFrame(repeat_rows)],
                ignore_index=True,
            )
            _module().validate_identity_output_evidence(subset_bundle)

            final_missing = dict(subset_bundle)
            final_missing["source_manifest"] = source_manifest.loc[
                source_manifest["path"].astype(str).ne(str(early.resolve()))
            ].copy()
            with self.assertRaisesRegex(ValueError, "path coverage"):
                _module().validate_identity_output_evidence(final_missing)

            extra = root / "final-only.csv"
            extra.write_text("value\n4\n", encoding="utf-8")
            final_extra = dict(subset_bundle)
            final_extra["source_manifest"] = pd.concat(
                [source_manifest, pd.DataFrame([_module()._file_snapshot(extra)])],
                ignore_index=True,
            )
            with self.assertRaisesRegex(ValueError, "path coverage"):
                _module().validate_identity_output_evidence(final_extra)

            drifted = dict(subset_bundle)
            drifted_repeat = subset_bundle["repeat_source_manifest"].copy()
            shared_rows = drifted_repeat["path"].astype(str).eq(str(shared.resolve()))
            drift_index = drifted_repeat.loc[
                shared_rows
                & drifted_repeat["requested_start_month"].astype(str).eq("2026-01")
            ].index[0]
            drifted_repeat.loc[drift_index, "sha256"] = "d" * 64
            drifted["repeat_source_manifest"] = drifted_repeat
            with self.assertRaisesRegex(ValueError, "cross-anchor source manifest drift"):
                _module().validate_identity_output_evidence(drifted)

            early.write_text("value\nchanged\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "final source manifest byte drift"):
                _module().validate_identity_output_evidence(subset_bundle)

    def test_atomic_writer_revalidates_full_path_closure_after_chart_generation(self) -> None:
        bundle = {
            key: pd.DataFrame() for key in _module()._PERSISTED_FRAME_FILES
        }
        bundle["base_daily"] = pd.DataFrame(
            columns=["requested_start_month", "date", "account_equity"]
        )
        bundle["candidate_orders"] = pd.DataFrame(columns=ORDER_COLUMNS)
        coverage = {
            "cost_multiplier": 1.0,
            "input_audit_pass": 1,
            "eligible_open_count": 0,
            "mapped_eligible_open_count": 0,
            "selected_open_count": 0,
            "missing_selected_open_count": 0,
            "unexpected_selected_open_count": 0,
            "unmapped_actual_open_count": 0,
            "future_match_count": 0,
            "source_order_mismatch_count": 0,
            "positive_volume_drift_count": 0,
            "opened_candidate_without_risk_count": 0,
            "risk_input_count": 0,
            "pit_source_ledger_row_count": 0,
            "candidate_input_count": 0,
            "pit_candidate_audit_row_count": 0,
            "opened_candidate_count": 0,
            "skipped_candidate_count": 0,
            "actual_open_input_count": 0,
            "actual_open_audit_row_count": 0,
            "open_at_end_count": 0,
            "expected_terminal_position_count": 0,
        }
        bundle["input_audit"] = pd.DataFrame(
            [
                {
                    **coverage,
                    "requested_start_month": start,
                    **_identity_input_fields(start),
                }
                for start in _module().CANARY_STARTS
            ]
        )
        bundle.update(_identity_output_frames())
        bundle["decision"] = {
            "mode": "audit",
            "audit_pass": True,
            "canary_pass": False,
            "failed_checks": ["canary_not_run"],
        }
        pristine_bundle = {
            key: value.copy(deep=True) if isinstance(value, pd.DataFrame) else dict(value)
            for key, value in bundle.items()
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            extra = root / "late-source.csv"
            extra.write_text("value\n1\n", encoding="utf-8")
            snapshot = _module()._file_snapshot(extra)

            def mutate_manifest(target_bundle, _output_dir):
                target_bundle["source_manifest"] = pd.concat(
                    [target_bundle["source_manifest"], pd.DataFrame([snapshot])],
                    ignore_index=True,
                )

            output_dir = root / "out"
            with mock.patch.object(
                _module(), "_write_charts", side_effect=mutate_manifest
            ):
                with self.assertRaisesRegex(
                    ValueError, "staged output evidence drift"
                ):
                    _module().write_stage_outputs(bundle, output_dir)
            self.assertFalse(output_dir.exists())

            input_bundle = {
                key: value.copy(deep=True) if isinstance(value, pd.DataFrame) else dict(value)
                for key, value in pristine_bundle.items()
            }

            def mutate_input_audit(target_bundle, _output_dir):
                target_bundle["input_audit"].loc[
                    target_bundle["input_audit"].index[0], "input_audit_pass"
                ] = 0

            prior_output = root / "prior-out"
            prior_output.mkdir()
            (prior_output / "sentinel.txt").write_text("keep", encoding="utf-8")
            with mock.patch.object(
                _module(), "_write_charts", side_effect=mutate_input_audit
            ):
                with self.assertRaisesRegex(
                    ValueError, "staged output evidence drift"
                ):
                    _module().write_stage_outputs(input_bundle, prior_output)
            self.assertEqual(
                (prior_output / "sentinel.txt").read_text(encoding="utf-8"),
                "keep",
            )

            mtime_source = root / "mtime-only-source.csv"
            mtime_source.write_text("value\n1\n", encoding="utf-8")
            mtime_snapshot = _module()._file_snapshot(mtime_source)
            mtime_bundle = {
                key: value.copy(deep=True) if isinstance(value, pd.DataFrame) else dict(value)
                for key, value in pristine_bundle.items()
            }
            mtime_bundle["source_manifest"] = pd.concat(
                [
                    mtime_bundle["source_manifest"],
                    pd.DataFrame([mtime_snapshot]),
                ],
                ignore_index=True,
            )
            mtime_bundle["repeat_source_manifest"] = pd.concat(
                [
                    mtime_bundle["repeat_source_manifest"],
                    pd.DataFrame(
                        [
                            {
                                "requested_start_month": start,
                                "path": mtime_snapshot["path"],
                                "size": mtime_snapshot["size"],
                                "sha256": mtime_snapshot["sha256"],
                                "content_identity_match": 1,
                            }
                            for start in _module().CANARY_STARTS
                        ]
                    ),
                ],
                ignore_index=True,
            )

            def rewrite_mtime_only(_target_bundle, _output_dir):
                os.utime(
                    mtime_source,
                    ns=(
                        mtime_source.stat().st_atime_ns,
                        int(mtime_snapshot["mtime_ns"]) + 1_000_000_000,
                    ),
                )

            mtime_output = root / "mtime-out"
            with mock.patch.object(
                _module(), "_write_charts", side_effect=rewrite_mtime_only
            ):
                _module().write_stage_outputs(mtime_bundle, mtime_output)
            written_manifest = pd.read_csv(
                mtime_output / _module()._PERSISTED_FRAME_FILES["source_manifest"],
                encoding="utf-8-sig",
            )
            written_row = written_manifest.loc[
                written_manifest["path"].astype(str).eq(str(mtime_source.resolve()))
            ].iloc[0]
            self.assertEqual(written_row["post_finalization_mtime_only_rewrite"], 1)
            self.assertEqual(
                int(written_row["last_validated_mtime_ns"]),
                mtime_source.stat().st_mtime_ns,
            )

            disk_bundle = {
                key: value.copy(deep=True) if isinstance(value, pd.DataFrame) else dict(value)
                for key, value in pristine_bundle.items()
            }

            def mutate_staged_csv(_target_bundle, staged_dir):
                (Path(staged_dir) / _module()._PERSISTED_FRAME_FILES["satellite_daily"]).write_text(
                    "unexpected\n1\n",
                    encoding="utf-8-sig",
                )

            disk_output = root / "disk-tamper-out"
            disk_output.mkdir()
            (disk_output / "sentinel.txt").write_text("keep", encoding="utf-8")
            with mock.patch.object(
                _module(), "_write_charts", side_effect=mutate_staged_csv
            ):
                with self.assertRaisesRegex(ValueError, "staged output evidence drift"):
                    _module().write_stage_outputs(disk_bundle, disk_output)
            self.assertEqual(
                (disk_output / "sentinel.txt").read_text(encoding="utf-8"),
                "keep",
            )

            schema_bundle = {
                key: value.copy(deep=True) if isinstance(value, pd.DataFrame) else dict(value)
                for key, value in pristine_bundle.items()
            }

            def drop_static_base_column(target_bundle, _staged_dir):
                target_bundle["satellite_daily"] = target_bundle["satellite_daily"].drop(
                    columns=["requested_start_month"]
                )

            schema_output = root / "schema-tamper-out"
            with mock.patch.object(
                _module(), "_write_charts", side_effect=drop_static_base_column
            ):
                with self.assertRaisesRegex(ValueError, "staged output evidence drift"):
                    _module().write_stage_outputs(schema_bundle, schema_output)
            self.assertFalse(schema_output.exists())

    def test_output_writer_rejects_missing_coverage_audit_columns(self) -> None:
        bundle = {
            key: pd.DataFrame()
            for key in (
                "base_daily",
                "selected_lifecycle",
                "pit_source_ledger",
                "pit_candidate_audit",
                "actual_open_audit",
                "pit_binding_audit",
                "candidate_orders",
                "replayed_orders",
                "satellite_daily",
                "price_audit",
                "summary",
                "reconciliation",
                "fifo_audit",
                "margin_audit",
                "current_ai_audit",
                "repeat_identity_audit",
                "repeat_source_manifest",
                "source_manifest",
            )
        }
        bundle.update({
            "input_audit": pd.DataFrame([{"input_audit_pass": 1}]),
            "decision": {"mode": "audit", "canary_pass": False, "failed_checks": []},
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            with self.assertRaisesRegex(ValueError, "coverage audit"):
                _module().write_stage_outputs(bundle, output_dir)
            self.assertFalse(output_dir.exists())

    def test_2022_chart_contract_is_full_anchor_path_not_calendar_slice(self) -> None:
        contract = _module().chart_contract()["focus_2022.png"]
        self.assertEqual(contract["requested_start_months"], ("2022-01", "2022-07"))
        self.assertEqual(contract["calendar_date_filter"], None)
        self.assertIn("full paths through 2026-06-30", contract["title"])

    def test_reconciliation_row_contains_all_terminal_errors(self) -> None:
        row = _module().build_reconciliation_row(
            "2022-01",
            1.0,
            {
                "max_reconciliation_error": 1e-9,
                "max_terminal_position_reconciliation_error": 2e-9,
                "max_terminal_margin_reconciliation_error": 3e-9,
                "max_terminal_pnl_reconciliation_error": 4e-9,
            },
        )

        self.assertEqual(
            row,
            {
                "requested_start_month": "2022-01",
                "cost_multiplier": 1.0,
                "max_reconciliation_error": 1e-9,
                "max_terminal_position_reconciliation_error": 2e-9,
                "max_terminal_margin_reconciliation_error": 3e-9,
                "max_terminal_pnl_reconciliation_error": 4e-9,
            },
        )

    def test_outputs_are_all_or_nothing_and_exclude_full_positions_and_minute_data(self) -> None:
        bundle = {
            "base_daily": pd.DataFrame([{"requested_start_month": "2022-01", "date": "2022-01-03"}]),
            "selected_lifecycle": pd.DataFrame([{"requested_start_month": "2022-01", "open_trade_id": "O1"}]),
            "pit_source_ledger": pd.DataFrame([{"requested_start_month": "2022-01", "source_id": "risk:1", "mapping_status": "mapped"}]),
            "pit_candidate_audit": pd.DataFrame([{"requested_start_month": "2022-01", "candidate_index": 1, "mapping_status": "matched_risk_source"}]),
            "actual_open_audit": pd.DataFrame([{"requested_start_month": "2022-01", "trade_id": "O1", "classification": "mapped_quality_eligible"}]),
            "pit_binding_audit": pd.DataFrame([{"requested_start_month": "2022-01", "open_trade_id": "O1"}]),
            "candidate_orders": pd.DataFrame([{"requested_start_month": "2022-01", "open_trade_id": "O1"}]),
            "replayed_orders": pd.DataFrame([{"requested_start_month": "2022-01", "open_trade_id": "O1"}]),
            "satellite_daily": pd.DataFrame([{"requested_start_month": "2022-01", "date": "2022-01-03", "account_equity": 1.0, "satellite_equity": 1.0, "combined_equity": 1.0}]),
            "price_audit": pd.DataFrame([{"date": "2022-01-03", "vt_symbol": "rb.SHFE", "pre_close": 1.0, "close_price": 1.0}]),
            "summary": pd.DataFrame([{"requested_start_month": "2022-01"}]),
            "input_audit": pd.DataFrame([{
                "requested_start_month": "2022-01",
                "input_audit_pass": 1,
                "eligible_open_count": 1,
                "mapped_eligible_open_count": 1,
                "selected_open_count": 1,
                "missing_selected_open_count": 0,
                "unexpected_selected_open_count": 0,
                "unmapped_actual_open_count": 0,
                "future_match_count": 0,
                "source_order_mismatch_count": 0,
                "positive_volume_drift_count": 0,
                "opened_candidate_without_risk_count": 0,
                "risk_input_count": 1,
                "pit_source_ledger_row_count": 1,
                "candidate_input_count": 1,
                "pit_candidate_audit_row_count": 1,
                "opened_candidate_count": 1,
                "skipped_candidate_count": 0,
                "actual_open_input_count": 1,
                "actual_open_audit_row_count": 1,
                "open_at_end_count": 0,
                "expected_terminal_position_count": 0,
                "unexpected_terminal_position_count": 0,
                "max_terminal_position_reconciliation_error": 0.0,
                "max_terminal_margin_reconciliation_error": 0.0,
                "max_terminal_pnl_reconciliation_error": 0.0,
            }]),
            "reconciliation": pd.DataFrame([{"requested_start_month": "2022-01", "max_reconciliation_error": 0.0}]),
            "fifo_audit": pd.DataFrame([{"requested_start_month": "2022-01", "overclose_count": 0}]),
            "margin_audit": pd.DataFrame([{"requested_start_month": "2022-01", "max_proposed_broker10_pct": 0.0}]),
            "current_ai_audit": pd.DataFrame([{"requested_start_month": "2022-01", "current_ai_snapshot_pass": 1}]),
            "repeat_identity_audit": pd.DataFrame([{"requested_start_month": "2022-01", "frame_name": "base_daily", "identity_match": 1}]),
            "repeat_source_manifest": pd.DataFrame([{"requested_start_month": "2022-01", "path": "/tmp/source", "content_identity_match": 1}]),
            "source_manifest": pd.DataFrame([{"path": "/tmp/source", "size": 1, "mtime_ns": 1, "sha256": "0" * 64}]),
            "decision": {"mode": "canary", "canary_pass": False, "failed_checks": ["fixture"]},
        }
        _complete_identity_output_bundle(bundle)
        forbidden = {"positions", "minute_bars", "entry_risk", "entry_candidates"}
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            _module().write_stage_outputs(bundle, output_dir)
            names = {path.name for path in output_dir.iterdir()}
            self.assertTrue({"base_daily.csv", "selected_lifecycle.csv", "price_audit.csv", "fifo_audit.csv", "margin_audit.csv", "decision.json", "report.md", "equity.png", "drawdown.png", "focus_2022.png"}.issubset(names))
            self.assertTrue(all(not any(token in name for token in forbidden) for name in names))
            decision = json.loads((output_dir / "decision.json").read_text(encoding="utf-8"))
            self.assertFalse(decision["canary_pass"])

        broken = dict(bundle)
        broken["input_audit"] = bundle["input_audit"].assign(input_audit_pass=0)
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            with self.assertRaisesRegex(ValueError, "input audit"):
                _module().write_stage_outputs(broken, output_dir)
            self.assertFalse(output_dir.exists())
