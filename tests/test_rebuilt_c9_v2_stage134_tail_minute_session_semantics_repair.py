from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "tools"
)
MODULE_NAME = "stage134_tail_minute_session_semantics_repair"
MODULE_PATH = TOOLS_DIR / f"{MODULE_NAME}.py"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


EXPECTED_CONTRACTS = [
    "cu2607.SHFE",
    "au2608.SHFE",
    "lh2609.DCE",
    "SM609.CZCE",
    "SH609.CZCE",
    "cu2608.SHFE",
]


def _module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"production module missing: {MODULE_PATH}")
    return importlib.import_module(MODULE_NAME)


def _bars(contract: str = "cu2607.SHFE") -> pd.DataFrame:
    timestamps = [
        "2026-05-22 21:00:00",
        "2026-05-22 21:01:00",
        "2026-05-23 00:00:00",
        "2026-05-25 09:00:00",
        "2026-05-25 09:01:00",
        "2026-05-25 21:00:00",
        "2026-05-25 21:01:00",
        "2026-05-26 09:00:00",
        "2026-05-26 09:01:00",
    ]
    rows = []
    for idx, value in enumerate(timestamps):
        price = 100.0 + idx
        rows.append(
            {
                "vt_symbol": contract,
                "tq_symbol": "SHFE.cu2607",
                "bar_datetime": value,
                "bar_id": idx,
                "open": price,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price + 0.5,
                "volume": 1.0,
                "open_oi": 1000.0,
                "close_oi": 1001.0,
            }
        )
    return pd.DataFrame(rows)


def _audit_row(temp_path: Path, final_path: Path | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        contract_vt="cu2607.SHFE",
        product_vt_symbol="cu.SHFE",
        tq_symbol="SHFE.cu2607",
        download_start_datetime="2026-05-22 20:55:00",
        download_end_datetime="2026-05-26 15:15:00",
        output_path=str(temp_path),
        final_output_path=str(final_path or temp_path.with_name("final.csv")),
    )


def _expected_dates() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(["2026-05-25", "2026-05-26"])


def _global_dates() -> pd.DatetimeIndex:
    return pd.DatetimeIndex(["2026-05-22", "2026-05-25", "2026-05-26"])


class Stage134PlanTest(unittest.TestCase):
    def test_build_session_plan_freezes_contracts_and_previous_trading_day(self) -> None:
        s134 = _module()
        before = pd.DataFrame(
            {
                "contract_vt": EXPECTED_CONTRACTS,
                "product_vt_symbol": [
                    "cu.SHFE",
                    "au.SHFE",
                    "lh.DCE",
                    "SM.CZCE",
                    "SH.CZCE",
                    "cu.SHFE",
                ],
                "priority": ["P1_tail_contract_gap"] * 6,
            }
        )
        expected = {
            contract: pd.DatetimeIndex(["2026-05-25", "2026-05-26"])
            for contract in EXPECTED_CONTRACTS
        }

        plan = s134.build_session_plan(before, expected, _global_dates())

        self.assertEqual(plan["contract_vt"].tolist(), EXPECTED_CONTRACTS)
        self.assertEqual(
            plan.loc[0, "download_start_datetime"], "2026-05-22 20:55:00"
        )
        self.assertEqual(
            plan.loc[0, "download_end_datetime"], "2026-05-26 15:15:00"
        )
        self.assertEqual(int(plan.loc[0, "expected_trade_date_count"]), 2)


class Stage134SessionAuditTest(unittest.TestCase):
    def test_cross_midnight_natural_dates_do_not_fail_exact_trade_dates(self) -> None:
        s134 = _module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.csv"
            _bars().to_csv(path, index=False, encoding="utf-8-sig")

            audit = s134.audit_session_file(
                _audit_row(path), path, _expected_dates(), _global_dates()
            )

        self.assertTrue(audit["strict_ready"])
        self.assertEqual(audit["expected_trade_date_count"], 2)
        self.assertEqual(audit["day_session_trade_date_count"], 2)
        self.assertGreater(audit["natural_date_count"], 2)
        self.assertEqual(audit["night_window_ready_count"], 2)
        self.assertEqual(audit["fill_window_coverage_count"], 2)

    def test_missing_night_and_day_fill_windows_fails_closed(self) -> None:
        s134 = _module()
        data = _bars()
        dt = pd.to_datetime(data["bar_datetime"])
        keep = ~(
            ((dt >= pd.Timestamp("2026-05-22 21:00")) & (dt < pd.Timestamp("2026-05-22 21:05")))
            | ((dt >= pd.Timestamp("2026-05-25 09:00")) & (dt < pd.Timestamp("2026-05-25 09:05")))
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.csv"
            data.loc[keep].to_csv(path, index=False, encoding="utf-8-sig")

            audit = s134.audit_session_file(
                _audit_row(path), path, _expected_dates(), _global_dates()
            )

        self.assertFalse(audit["strict_ready"])
        self.assertEqual(audit["fill_window_coverage_count"], 1)
        self.assertIn("fill_window_coverage", audit["blocking_reason"])

    def test_extra_day_session_date_and_invalid_ohlc_fail_closed(self) -> None:
        s134 = _module()
        data = _bars()
        extra = data.iloc[[0]].copy()
        extra["bar_datetime"] = "2026-05-27 09:00:00"
        extra["high"] = extra["low"] - 1.0
        data = pd.concat([data, extra], ignore_index=True).sort_values("bar_datetime")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.csv"
            data.to_csv(path, index=False, encoding="utf-8-sig")

            audit = s134.audit_session_file(
                _audit_row(path), path, _expected_dates(), _global_dates()
            )

        self.assertFalse(audit["strict_ready"])
        self.assertFalse(audit["day_session_dates_exact"])
        self.assertEqual(audit["ohlc_relation_error_count"], 1)


class Stage134AtomicPublishTest(unittest.TestCase):
    def test_verified_candidate_backs_up_and_atomically_replaces_old_file(self) -> None:
        s134 = _module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            temp_path = root / "tmp" / "cu2607.csv"
            final_path = root / "final" / "cu2607.csv"
            temp_path.parent.mkdir(parents=True)
            final_path.parent.mkdir(parents=True)
            temp_path.write_bytes(b"new-data")
            final_path.write_bytes(b"old-data")
            audit = pd.DataFrame(
                [
                    {
                        "contract_vt": "cu2607.SHFE",
                        "strict_ready": True,
                        "temp_path": str(temp_path),
                        "final_output_path": str(final_path),
                        "sha256": s134.sha256_path(temp_path),
                        "blocking_reason": "",
                    }
                ]
            )

            result = s134.publish_verified(audit, root / "quarantine")

            self.assertEqual(result.loc[0, "action"], "replaced")
            self.assertEqual(final_path.read_bytes(), b"new-data")
            backup = Path(result.loc[0, "previous_backup_path"])
            self.assertEqual(backup.read_bytes(), b"old-data")

    def test_rejected_candidate_preserves_old_final(self) -> None:
        s134 = _module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            temp_path = root / "tmp" / "cu2607.csv"
            final_path = root / "final" / "cu2607.csv"
            temp_path.parent.mkdir(parents=True)
            final_path.parent.mkdir(parents=True)
            temp_path.write_bytes(b"bad-data")
            final_path.write_bytes(b"old-data")
            audit = pd.DataFrame(
                [
                    {
                        "contract_vt": "cu2607.SHFE",
                        "strict_ready": False,
                        "temp_path": str(temp_path),
                        "final_output_path": str(final_path),
                        "sha256": s134.sha256_path(temp_path),
                        "blocking_reason": "invalid",
                    }
                ]
            )

            result = s134.publish_verified(audit, root / "quarantine")

            self.assertEqual(result.loc[0, "action"], "quarantined")
            self.assertEqual(final_path.read_bytes(), b"old-data")
            self.assertFalse(temp_path.exists())


if __name__ == "__main__":
    unittest.main()
