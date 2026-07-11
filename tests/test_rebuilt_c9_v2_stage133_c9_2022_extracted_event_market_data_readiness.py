from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "tools"
)
MODULE_NAME = "stage133_c9_2022_extracted_event_market_data_readiness"
MODULE_PATH = TOOLS_DIR / f"{MODULE_NAME}.py"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


EXPECTED_EVENT_IDS = [
    "2424ec63fd31887211f99761200188b2ad2a0afb482997c9d8ad65a4081f3d39",
    "9df8755883c082095fd03b87ab99734546df9b375453c82e1f2088871f20db98",
    "d90db2cbffbbe58a48be41bdeb736aa0056f404709d2bb47230eab9a25805cb8",
    "bb6d3275a518d933758ae3dfec300685616b6f48ae86c11e5d61e41c7e40c9c3",
]
EXPECTED_OPTION_SYMBOLS = [
    "CZCE.MA209C2700",
    "SHFE.au2206P400",
    "CZCE.MA209C2700",
    "CZCE.MA209P2900",
]


def _module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"production module missing: {MODULE_PATH}")
    return importlib.import_module(MODULE_NAME)


def _metadata() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "option_symbol": [
                "CZCE.MA209C2650",
                "CZCE.MA209C2700",
                "CZCE.MA209C2750",
                "CZCE.MA209P2700",
            ],
            "underlying_symbol": ["CZCE.MA209"] * 4,
            "option_class": ["CALL", "CALL", "CALL", "PUT"],
            "expire_datetime": ["2022-08-03 15:00:00"] * 4,
            "last_exercise_datetime": ["2022-08-03 15:00:00"] * 4,
            "strike_price": [2650.0, 2700.0, 2750.0, 2700.0],
            "expired": [False] * 4,
            "volume_multiple": [10] * 4,
            "price_tick": [0.5] * 4,
        }
    )


SESSION_START = pd.Timestamp("2022-04-25 20:00:00", tz="Asia/Shanghai")
SESSION_END = pd.Timestamp("2022-04-26 16:00:00", tz="Asia/Shanghai")


def _ns(value: str) -> int:
    return int(pd.Timestamp(value, tz="Asia/Shanghai").tz_convert("UTC").value)


def _minute_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2],
            "datetime": [
                _ns("2022-04-25 21:01:00"),
                _ns("2022-04-26 09:01:00"),
            ],
            "open": [10.0, 11.0],
            "high": [11.0, 12.0],
            "low": [9.0, 10.0],
            "close": [10.5, 11.5],
            "volume": [3.0, 4.0],
            "open_oi": [100.0, 101.0],
            "close_oi": [101.0, 102.0],
        }
    )


def _tick_frame(*, two_sided: bool = True) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [1, 2],
            "datetime": [
                _ns("2022-04-25 21:01:01"),
                _ns("2022-04-26 09:01:01"),
            ],
            "last_price": [10.5, 11.5],
            "average": [10.4, 11.0],
            "highest": [10.5, 11.5],
            "lowest": [10.5, 10.5],
            "ask_price1": [10.6, 11.6] if two_sided else [float("nan")] * 2,
            "ask_volume1": [2.0, 3.0] if two_sided else [float("nan")] * 2,
            "bid_price1": [10.4, 11.4],
            "bid_volume1": [3.0, 4.0],
            "volume": [10.0, 13.0],
            "amount": [105.0, 139.5],
            "open_interest": [101.0, 102.0],
        }
    )


def _event_row() -> dict[str, object]:
    return _module().load_frozen_probe_plan().iloc[0].to_dict()


def _lineage() -> dict[str, str]:
    return {
        "tool_sha256": "1" * 64,
        "test_sha256": "2" * 64,
        "predecl_sha256": "3" * 64,
        "plan_sha256": "4" * 64,
    }


def _payload(message: str = ""):
    s133 = _module()
    underlying = _minute_frame()
    option = _minute_frame()
    ticks = _tick_frame()
    audit = s133.audit_event_market_data(
        underlying, option, ticks, SESSION_START, SESSION_END
    )
    return s133.FetchPayload(
        terminal_status="extracted",
        underlying_minute=underlying,
        option_minute=option,
        option_tick=ticks,
        audit=audit,
        message=message,
        elapsed_seconds=1.25,
        network_called=True,
    )


class Stage133FrozenProbePlanTest(unittest.TestCase):
    def test_load_frozen_probe_plan_has_exact_events_and_symbols(self) -> None:
        s133 = _module()

        plan = s133.load_frozen_probe_plan()
        audit = s133.audit_probe_plan(plan)

        self.assertEqual(plan["event_id"].tolist(), EXPECTED_EVENT_IDS)
        self.assertEqual(plan["option_symbol"].tolist(), EXPECTED_OPTION_SYMBOLS)
        self.assertTrue(audit["probe_plan_audit_pass"])
        self.assertEqual(audit["event_count"], 4)
        self.assertEqual(audit["lot_count"], 6)

    def test_source_hash_drift_fails_before_network(self) -> None:
        s133 = _module()

        with self.assertRaises(s133.IntegrityError):
            s133.load_frozen_probe_plan(expected_terminal_sha256="0" * 64)

    def test_select_probe_option_uses_first_expiry_then_nearest_strike(self) -> None:
        s133 = _module()

        selected = s133.select_probe_option(
            _metadata(),
            option_class="CALL",
            entry_price=2698.0,
            entry_date=pd.Timestamp("2022-04-26"),
        )

        self.assertEqual(selected["option_symbol"], "CZCE.MA209C2700")
        self.assertEqual(float(selected["strike_price"]), 2700.0)

    def test_select_probe_option_fails_closed_without_unexpired_class(self) -> None:
        s133 = _module()
        expired = _metadata().assign(expire_datetime="2022-04-25 15:00:00")

        with self.assertRaises(s133.IntegrityError):
            s133.select_probe_option(
                expired,
                option_class="CALL",
                entry_price=2698.0,
                entry_date=pd.Timestamp("2022-04-26"),
            )


class Stage133MarketDataAuditTest(unittest.TestCase):
    def test_normalize_accepts_nanoseconds_and_preserves_source_columns(self) -> None:
        s133 = _module()
        raw = _minute_frame()
        before = raw.copy(deep=True)

        normalized = s133.normalize_market_frame(raw, SESSION_START, SESSION_END)

        pd.testing.assert_frame_equal(raw, before)
        self.assertEqual(
            normalized.loc[0, "datetime_beijing"],
            pd.Timestamp("2022-04-25 21:01:00", tz="Asia/Shanghai"),
        )
        self.assertTrue(normalized["in_session_window"].all())
        self.assertEqual(
            normalized.columns.tolist(),
            raw.columns.tolist() + ["datetime_beijing", "in_session_window"],
        )

    def test_normalize_preserves_fractional_nanoseconds_exactly(self) -> None:
        s133 = _module()
        raw_ns = _ns("2022-04-26 14:59:59.000001")
        raw = _minute_frame().iloc[[0]].copy()
        raw.loc[raw.index[0], "datetime"] = raw_ns

        normalized = s133.normalize_market_frame(raw, SESSION_START, SESSION_END)
        normalized_ns = int(
            normalized.iloc[0]["datetime_beijing"].tz_convert("UTC").value
        )

        self.assertEqual(normalized_ns, raw_ns)

    def test_nan_padding_is_not_malformed_datetime(self) -> None:
        s133 = _module()
        padded = pd.concat(
            [
                pd.DataFrame([{column: float("nan") for column in _minute_frame().columns}]),
                _minute_frame(),
            ],
            ignore_index=True,
        )

        normalized = s133.normalize_market_frame(padded, SESSION_START, SESSION_END)

        self.assertEqual(int(normalized["datetime_beijing"].isna().sum()), 1)
        self.assertFalse(bool(normalized.loc[0, "in_session_window"]))

    def test_audit_counts_all_nan_padding_without_malformed_time(self) -> None:
        s133 = _module()
        minute = _minute_frame().astype(object)
        padding = pd.DataFrame(
            [{column: None for column in minute.columns}], columns=minute.columns
        )
        padded = pd.concat([padding, minute], ignore_index=True)

        audit = s133.audit_event_market_data(
            padded, padded, _tick_frame(), SESSION_START, SESSION_END
        )

        self.assertEqual(audit["underlying_minute_padding_row_count"], 1)
        self.assertEqual(audit["option_minute_padding_row_count"], 1)
        self.assertEqual(audit["underlying_minute_malformed_datetime_count"], 0)
        self.assertEqual(audit["option_minute_malformed_datetime_count"], 0)
        self.assertTrue(audit["market_data_integrity_pass"])

    def test_audit_separates_tick_price_from_two_sided_spread(self) -> None:
        s133 = _module()

        audit = s133.audit_event_market_data(
            _minute_frame(),
            _minute_frame(),
            _tick_frame(two_sided=False),
            SESSION_START,
            SESSION_END,
        )

        self.assertTrue(audit["premium_observed"])
        self.assertTrue(audit["tick_price_observed"])
        self.assertFalse(audit["two_sided_spread_observed"])
        self.assertTrue(audit["oi_observed"])
        self.assertFalse(audit["all_fields_observed"])

    def test_tick_cumulative_volume_is_change_not_sum(self) -> None:
        s133 = _module()

        audit = s133.audit_event_market_data(
            _minute_frame(),
            _minute_frame(),
            _tick_frame(),
            SESSION_START,
            SESSION_END,
        )

        self.assertEqual(audit["tick_volume_first"], 10.0)
        self.assertEqual(audit["tick_volume_last"], 13.0)
        self.assertEqual(audit["tick_volume_change"], 3.0)
        self.assertNotIn("tick_volume_sum", audit)
        self.assertTrue(audit["positive_trade_observed"])
        self.assertTrue(audit["all_fields_observed"])

    def test_tick_cumulative_volume_uses_time_order_not_input_index(self) -> None:
        s133 = _module()
        reversed_ticks = _tick_frame().iloc[::-1].reset_index(drop=True)

        audit = s133.audit_event_market_data(
            _minute_frame(),
            _minute_frame(),
            reversed_ticks,
            SESSION_START,
            SESSION_END,
        )

        self.assertEqual(audit["tick_volume_first"], 10.0)
        self.assertEqual(audit["tick_volume_last"], 13.0)
        self.assertEqual(audit["tick_volume_change"], 3.0)
        self.assertEqual(audit["tick_cumulative_volume_decrease_count"], 0)

    def test_tick_cumulative_volume_rollback_fails_integrity(self) -> None:
        s133 = _module()
        ticks = _tick_frame()
        ticks["volume"] = [10.0, 9.0]

        audit = s133.audit_event_market_data(
            _minute_frame(), _minute_frame(), ticks, SESSION_START, SESSION_END
        )

        self.assertEqual(audit["tick_cumulative_volume_decrease_count"], 1)
        self.assertFalse(audit["market_data_integrity_pass"])
        self.assertFalse(audit["all_fields_observed"])

    def test_audit_detects_duplicates_bad_ohlc_and_negative_values(self) -> None:
        s133 = _module()
        option = pd.concat([_minute_frame(), _minute_frame().iloc[[0]]], ignore_index=True)
        option.loc[0, "high"] = 8.0
        option.loc[1, "volume"] = -1.0
        option.loc[1, "close_oi"] = -2.0
        ticks = _tick_frame()
        ticks.loc[0, "ask_price1"] = 10.0
        ticks.loc[0, "bid_price1"] = 10.5
        ticks.loc[1, "bid_volume1"] = -1.0

        audit = s133.audit_event_market_data(
            _minute_frame(), option, ticks, SESSION_START, SESSION_END
        )

        self.assertGreater(audit["option_minute_duplicate_timestamp_count"], 0)
        self.assertEqual(audit["option_minute_ohlc_relation_error_count"], 1)
        self.assertEqual(audit["option_minute_negative_volume_count"], 1)
        self.assertEqual(audit["option_minute_negative_oi_count"], 1)
        self.assertEqual(audit["tick_crossed_spread_count"], 1)
        self.assertEqual(audit["tick_negative_quote_volume_count"], 1)
        self.assertFalse(audit["market_data_integrity_pass"])

    def test_audit_rejects_infinite_minute_values(self) -> None:
        s133 = _module()
        option = _minute_frame()
        option.loc[0, "close"] = float("inf")

        audit = s133.audit_event_market_data(
            _minute_frame(), option, _tick_frame(), SESSION_START, SESSION_END
        )

        self.assertEqual(audit["option_minute_infinite_numeric_count"], 1)
        self.assertFalse(audit["market_data_integrity_pass"])
        self.assertFalse(audit["all_fields_observed"])

    def test_audit_rejects_infinite_tick_values(self) -> None:
        s133 = _module()
        ticks = _tick_frame()
        ticks.loc[0, "ask_price1"] = float("inf")

        audit = s133.audit_event_market_data(
            _minute_frame(), _minute_frame(), ticks, SESSION_START, SESSION_END
        )

        self.assertEqual(audit["tick_infinite_numeric_count"], 1)
        self.assertFalse(audit["market_data_integrity_pass"])
        self.assertFalse(audit["all_fields_observed"])


class Stage133AtomicAttemptTest(unittest.TestCase):
    def test_valid_attempt_round_trips_with_detached_manifest(self) -> None:
        s133 = _module()
        with tempfile.TemporaryDirectory() as tmp:
            path = s133.publish_attempt(
                _event_row(),
                _payload(),
                Path(tmp) / "attempts",
                _lineage(),
            )

            validation = s133.validate_attempt_dir(path, _event_row(), _lineage())

            self.assertTrue(validation["attempt_integrity_pass"])
            self.assertTrue(validation["cacheable"])
            manifest = pd.read_csv(path / s133.ATTEMPT_MANIFEST_NAME)
            self.assertNotIn(s133.ATTEMPT_MANIFEST_NAME, manifest["file"].tolist())
            self.assertNotIn(s133.ATTEMPT_CHECKSUM_NAME, manifest["file"].tolist())
            checksum = (path / s133.ATTEMPT_CHECKSUM_NAME).read_text(encoding="ascii")
            self.assertEqual(
                checksum,
                f"{s133.file_sha256(path / s133.ATTEMPT_MANIFEST_NAME)}  "
                f"{s133.ATTEMPT_MANIFEST_NAME}\n",
            )
            self.assertTrue((path / s133.SELECTION_CANDIDATES_NAME).is_file())
            self.assertTrue((path / s133.SELECTION_AUDIT_NAME).is_file())
            request = json.loads(
                (path / s133.ATTEMPT_REQUEST_NAME).read_text(encoding="utf-8")
            )
            self.assertEqual(
                request["terminal_status_source_sha256"],
                s133.TERMINAL_STATUS_SHA256,
            )
            self.assertEqual(
                request["acquisition_requirements_source_sha256"],
                s133.ACQUISITION_REQUIREMENTS_SHA256,
            )
            self.assertEqual(
                request["entry_risk_links_source_sha256"],
                s133.ENTRY_RISK_LINKS_SHA256,
            )
            self.assertEqual(request["metadata_sha256"], _event_row()["metadata_sha256"])
            self.assertEqual(request["option_expire_datetime"], _event_row()["option_expire_datetime"])
            candidates = pd.read_csv(path / s133.SELECTION_CANDIDATES_NAME)
            self.assertEqual(int(candidates.iloc[0]["rank"]), 1)
            self.assertTrue(bool(candidates.iloc[0]["selected"]))
            self.assertEqual(candidates.iloc[0]["option_symbol"], _event_row()["option_symbol"])

    def test_mutated_raw_file_is_not_cacheable(self) -> None:
        s133 = _module()
        with tempfile.TemporaryDirectory() as tmp:
            path = s133.publish_attempt(
                _event_row(), _payload(), Path(tmp) / "attempts", _lineage()
            )
            (path / s133.RAW_OPTION_TICK_NAME).write_text(
                "tampered\n", encoding="utf-8"
            )

            validation = s133.validate_attempt_dir(path, _event_row(), _lineage())

            self.assertFalse(validation["attempt_integrity_pass"])
            self.assertFalse(validation["cacheable"])

    def test_wrong_producer_lineage_is_not_cacheable(self) -> None:
        s133 = _module()
        with tempfile.TemporaryDirectory() as tmp:
            path = s133.publish_attempt(
                _event_row(), _payload(), Path(tmp) / "attempts", _lineage()
            )
            wrong = {**_lineage(), "tool_sha256": "f" * 64}

            validation = s133.validate_attempt_dir(path, _event_row(), wrong)

            self.assertFalse(validation["attempt_integrity_pass"])
            self.assertFalse(validation["cacheable"])
            self.assertIn("producer lineage mismatch", validation["blocking_reason"])

    def test_validator_binds_all_frozen_event_and_session_inputs(self) -> None:
        s133 = _module()
        with tempfile.TemporaryDirectory() as tmp:
            event = _event_row()
            path = s133.publish_attempt(
                event, _payload(), Path(tmp) / "attempts", _lineage()
            )
            mutations = {
                "direction": "long",
                "entry_price": float(event["entry_price"]) + 1.0,
                "option_strike": float(event["option_strike"]) + 50.0,
                "metadata_sha256": "f" * 64,
                "session_start": "2022-04-25 21:00:00",
            }

            for key, value in mutations.items():
                with self.subTest(key=key):
                    validation = s133.validate_attempt_dir(
                        path, {**event, key: value}, _lineage()
                    )
                    self.assertFalse(validation["attempt_integrity_pass"])
                    self.assertFalse(validation["cacheable"])
                    self.assertIn(key, validation["blocking_reason"])

    def test_failed_attempt_is_retained_without_raw_market_files(self) -> None:
        s133 = _module()
        failed = s133.FetchPayload(
            terminal_status="query_failed",
            underlying_minute=pd.DataFrame(),
            option_minute=pd.DataFrame(),
            option_tick=pd.DataFrame(),
            audit={},
            message="network failed",
            elapsed_seconds=0.5,
            network_called=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = s133.publish_attempt(
                _event_row(), failed, Path(tmp) / "attempts", _lineage()
            )

            validation = s133.validate_attempt_dir(path, _event_row(), _lineage())

            self.assertTrue(validation["attempt_integrity_pass"])
            self.assertFalse(validation["cacheable"])
            self.assertFalse((path / s133.RAW_OPTION_TICK_NAME).exists())
            self.assertTrue(path.is_dir())

    def test_attempt_redacts_forbidden_secrets(self) -> None:
        s133 = _module()
        secret = "credential-value-must-not-leak"
        with tempfile.TemporaryDirectory() as tmp:
            path = s133.publish_attempt(
                _event_row(),
                _payload(f"vendor error for {secret}"),
                Path(tmp) / "attempts",
                _lineage(),
                secrets=[secret],
            )

            for file_path in path.iterdir():
                if file_path.is_file():
                    self.assertNotIn(secret.encode(), file_path.read_bytes())
            status = json.loads(
                (path / s133.ATTEMPT_STATUS_NAME).read_text(encoding="utf-8")
            )
            self.assertIn("<redacted>", status["message"])

    def test_integrity_failed_attempt_preserves_raw_evidence_but_is_not_cacheable(self) -> None:
        s133 = _module()
        underlying = _minute_frame()
        option = _minute_frame().copy()
        option.loc[0, "high"] = 1.0
        ticks = _tick_frame()
        audit = s133.audit_event_market_data(
            underlying, option, ticks, SESSION_START, SESSION_END
        )
        failed = s133.FetchPayload(
            terminal_status="integrity_failed",
            underlying_minute=underlying,
            option_minute=option,
            option_tick=ticks,
            audit=audit,
            message="bad OHLC",
            elapsed_seconds=0.75,
            network_called=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = s133.publish_attempt(
                _event_row(), failed, Path(tmp) / "attempts", _lineage()
            )

            validation = s133.validate_attempt_dir(path, _event_row(), _lineage())

            self.assertTrue((path / s133.RAW_OPTION_MINUTE_NAME).is_file())
            self.assertTrue(validation["attempt_integrity_pass"])
            self.assertFalse(validation["cacheable"])
            self.assertEqual(validation["terminal_status"], "integrity_failed")


class Stage133RunnerTest(unittest.TestCase):
    def test_plan_mode_never_invokes_fetcher(self) -> None:
        s133 = _module()

        def forbidden_fetcher(*_args, **_kwargs):
            self.fail("plan mode called the network fetcher")

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "stage133"
            decision = s133.run(
                run_mode="plan",
                enable_network=False,
                fetcher=forbidden_fetcher,
                output_dir=output_dir,
            )
            report = s133._root_paths(output_dir)["report"].read_text(
                encoding="utf-8"
            )

        self.assertEqual(decision["network_fetch_count"], 0)
        self.assertFalse(decision["ready_for_option_strategy_ab"])
        self.assertEqual(decision["stage132_metadata_covered_event_count"], 123)
        self.assertEqual(decision["stage132_total_event_count"], 365)
        self.assertAlmostEqual(
            decision["stage132_metadata_coverage_ratio"], 123 / 365, places=12
        )
        self.assertTrue(decision["stage132_coverage_hard_fail"])
        self.assertIn("123/365=33.698630%", report)
        self.assertIn("4/4 只代表 vendor-extracted 子集", report)
        self.assertIn("fu/jm/FG/SM/hc", report)

    def test_canary_only_fetches_first_frozen_event(self) -> None:
        s133 = _module()
        seen: list[str] = []

        def fake_fetcher(event, _max_seconds):
            seen.append(str(event["event_id"]))
            return _payload()

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "stage133"
            decision = s133.run(
                run_mode="canary",
                enable_network=True,
                fetcher=fake_fetcher,
                output_dir=output_dir,
            )

            attempt = next(
                (output_dir / "event_attempts" / EXPECTED_EVENT_IDS[0]).glob(
                    "attempt_*"
                )
            )
            request = json.loads(
                (attempt / s133.ATTEMPT_REQUEST_NAME).read_text(encoding="utf-8")
            )
            status = json.loads(
                (attempt / s133.ATTEMPT_STATUS_NAME).read_text(encoding="utf-8")
            )
            event_dirs = sorted(
                path.name
                for path in (output_dir / "event_attempts").iterdir()
                if path.is_dir()
            )

        self.assertEqual(seen, [EXPECTED_EVENT_IDS[0]])
        self.assertEqual(decision["network_fetch_count"], 1)
        self.assertTrue(decision["canary_pass"])
        self.assertEqual(decision["cacheable_event_count"], 1)
        self.assertEqual(event_dirs, [EXPECTED_EVENT_IDS[0]])
        self.assertEqual(request["run_mode"], "canary")
        self.assertEqual(request["run_selection_event_ids"], [EXPECTED_EVENT_IDS[0]])
        self.assertEqual(request["run_fetch_ordinal"], 1)
        self.assertEqual(request["run_fetch_total"], 1)
        self.assertEqual(status["run_id"], request["run_id"])
        self.assertEqual(status["run_mode"], request["run_mode"])

    def test_remaining_refuses_without_valid_canary_cache(self) -> None:
        s133 = _module()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(s133.IntegrityError):
                s133.run(
                    run_mode="remaining",
                    enable_network=True,
                    fetcher=lambda *_: self.fail("remaining fetched before canary"),
                    output_dir=Path(tmp) / "stage133",
                )


if __name__ == "__main__":
    unittest.main()
