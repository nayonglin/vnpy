from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

import numpy as np
import pandas as pd
import talib


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "stage001_baseline_technical_attribution.py"


def load_module():
    spec = importlib.util.spec_from_file_location("tight_stop_stage001", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot create module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_bars(rows: int = 90) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=rows)
    close = pd.Series(np.linspace(100.0, 145.0, rows))
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.arange(rows) + 100,
            "close_oi": np.arange(rows) + 1_000,
        }
    )


class Stage001AttributionTests(unittest.TestCase):
    def test_source_match_prefers_exact_volume_over_stale_earlier_source(self) -> None:
        module = load_module()
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "BACKTESTING.75",
                    "order_id": "BACKTESTING.61",
                    "datetime": "2020-07-24 00:00:00+08:00",
                    "vt_symbol": "ru2009.SHFE",
                    "direction": "Long",
                    "offset": "Open",
                    "volume": 3,
                }
            ]
        )
        sources = pd.DataFrame(
            [
                {"entry_index": 32, "datetime": "2020-07-09 00:00:00+08:00", "contract_vt_symbol": "ru2009.SHFE", "direction": "long", "volume": 5},
                {"entry_index": 35, "datetime": "2020-07-23 00:00:00+08:00", "contract_vt_symbol": "ru2009.SHFE", "direction": "long", "volume": 3},
            ]
        )

        matched, audit = module._match_source_rows_to_open_trades(
            trades,
            sources,
            source_kind="entry_risk",
            volume_column="volume",
            source_id_column="entry_index",
        )

        self.assertEqual(int(matched["BACKTESTING.75"]["entry_index"]), 35)
        self.assertEqual(audit["unmatched_source_ids"], ["32"])
        self.assertEqual(audit["volume_mismatch_match_count"], 0)

    def test_source_match_prefers_latest_causal_source_when_volume_ties(self) -> None:
        module = load_module()
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "BACKTESTING.75",
                    "order_id": "BACKTESTING.61",
                    "datetime": "2020-07-24 00:00:00+08:00",
                    "vt_symbol": "ru2009.SHFE",
                    "direction": "Long",
                    "offset": "Open",
                    "volume": 3,
                }
            ]
        )
        sources = pd.DataFrame(
            [
                {"candidate_index": 56, "datetime": "2020-07-09 00:00:00+08:00", "contract_vt_symbol": "ru2009.SHFE", "direction": "long", "selected_volume": 3},
                {"candidate_index": 61, "datetime": "2020-07-23 00:00:00+08:00", "contract_vt_symbol": "ru2009.SHFE", "direction": "long", "selected_volume": 3},
            ]
        )

        matched, audit = module._match_source_rows_to_open_trades(
            trades,
            sources,
            source_kind="entry_candidate",
            volume_column="selected_volume",
            source_id_column="candidate_index",
        )

        self.assertEqual(int(matched["BACKTESTING.75"]["candidate_index"]), 61)
        self.assertEqual(audit["unmatched_source_ids"], ["56"])
        self.assertEqual(audit["max_match_lag_days"], 1.0)

    def test_source_match_prefers_latest_causal_source_over_stale_exact_volume(self) -> None:
        module = load_module()
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "BACKTESTING.139",
                    "order_id": "BACKTESTING.111",
                    "datetime": "2020-11-26 00:00:00+08:00",
                    "vt_symbol": "SM101.CZCE",
                    "direction": "Long",
                    "offset": "Open",
                    "volume": 4,
                }
            ]
        )
        sources = pd.DataFrame(
            [
                {
                    "entry_index": 58,
                    "datetime": "2020-11-20 00:00:00+08:00",
                    "contract_vt_symbol": "SM101.CZCE",
                    "direction": "long",
                    "volume": 4,
                },
                {
                    "entry_index": 59,
                    "datetime": "2020-11-25 00:00:00+08:00",
                    "contract_vt_symbol": "SM101.CZCE",
                    "direction": "long",
                    "volume": 23,
                },
            ]
        )

        matched, audit = module._match_source_rows_to_open_trades(
            trades,
            sources,
            source_kind="entry_risk",
            volume_column="volume",
            source_id_column="entry_index",
        )

        self.assertEqual(int(matched["BACKTESTING.139"]["entry_index"]), 59)
        self.assertEqual(audit["unmatched_source_ids"], ["58"])
        self.assertEqual(audit["volume_mismatch_match_count"], 1)
        self.assertEqual(audit["max_volume_mismatch"], 19.0)

    def test_source_match_allows_unique_causal_partial_fill(self) -> None:
        module = load_module()
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "BACKTESTING.139",
                    "order_id": "BACKTESTING.120",
                    "datetime": "2020-11-26 00:00:00+08:00",
                    "vt_symbol": "SM101.CZCE",
                    "direction": "Long",
                    "offset": "Open",
                    "volume": 4,
                }
            ]
        )
        sources = pd.DataFrame(
            [
                {
                    "entry_index": 59,
                    "datetime": "2020-11-25 00:00:00+08:00",
                    "contract_vt_symbol": "SM101.CZCE",
                    "direction": "long",
                    "volume": 23,
                }
            ]
        )

        matched, audit = module._match_source_rows_to_open_trades(
            trades,
            sources,
            source_kind="entry_risk",
            volume_column="volume",
            source_id_column="entry_index",
        )

        self.assertEqual(int(matched["BACKTESTING.139"]["entry_index"]), 59)
        self.assertEqual(audit["unmatched_root_open_count"], 0)
        self.assertEqual(audit["volume_mismatch_match_count"], 1)
        self.assertEqual(audit["max_volume_mismatch"], 19.0)

    def test_lineage_overwrites_all_source_fields_from_causal_match(self) -> None:
        module = load_module()
        trades = pd.DataFrame(
            [
                {"trade_id": "BACKTESTING.75", "order_id": "BACKTESTING.61", "datetime": "2020-07-24 00:00:00+08:00", "vt_symbol": "ru2009.SHFE", "direction": "Long", "offset": "Open", "price": 10610.0, "volume": 3},
                {"trade_id": "BACKTESTING.81", "order_id": "BACKTESTING.67", "datetime": "2020-08-06 00:00:00+08:00", "vt_symbol": "ru2009.SHFE", "direction": "Short", "offset": "Close", "volume": 3, "exit_reason": "forced_margin_deleverage"},
            ]
        )
        risks = pd.DataFrame(
            [
                {"entry_index": 32, "datetime": "2020-07-09 00:00:00+08:00", "contract_vt_symbol": "ru2009.SHFE", "product_vt_symbol": "ru.SHFE", "direction": "long", "volume": 5, "entry_context": "flat_entry", "signal": "old", "risk_mode": "old", "layer_kind": "old", "size": 10, "stop_price": 10640.0, "stop_distance": 50.0, "risk_per_contract": 500.0, "risk_multiplier": 2.0, "target_risk_amount": 5000.0, "selected_volume": 5, "contracts_by_risk": 10, "contracts_by_margin": 11},
                {"entry_index": 35, "datetime": "2020-07-23 00:00:00+08:00", "contract_vt_symbol": "ru2009.SHFE", "product_vt_symbol": "ru.SHFE", "direction": "long", "volume": 3, "entry_context": "flat_entry", "signal": "long_case1a", "risk_mode": "regular", "layer_kind": "base", "size": 10, "stop_price": 10530.0, "stop_distance": 85.0, "risk_per_contract": 850.0, "risk_multiplier": 1.0, "target_risk_amount": 2871.8, "selected_volume": 3, "contracts_by_risk": 3, "contracts_by_margin": 12},
            ]
        )
        closed = pd.DataFrame(
            [
                {"open_trade_id": "BACKTESTING.75", "close_trade_id": "BACKTESTING.81", "vt_symbol": "ru2009.SHFE", "product": "ru", "direction": "long", "entry_date": "2020-07-24", "exit_date": "2020-08-06", "entry_price": 10610.0, "volume": 3.0, "size": 10, "realized_pnl": 9300.0, "risk_amount": 1500.0, "risk_per_contract": 500.0, "r_multiple": 6.2, "exit_reason": "forced_margin_deleverage", "signal": "old", "risk_mode": "old", "entry_context": "flat_entry", "layer_kind": "old", "risk_multiplier": 2.0, "target_risk_amount": 5000.0, "selected_volume": 5, "contracts_by_risk": 10, "contracts_by_margin": 11, "stop_distance": 50.0, "entry_risk_distance_pct": 50.0 / 10610.0},
            ]
        )

        enriched, lineage, audit = module.build_complete_closed_lot_lineage(closed, trades, risks, pd.DataFrame())
        row = enriched.iloc[0]

        self.assertEqual(row["product"], "ru.SHFE")
        self.assertEqual(row["signal"], "long_case1a")
        self.assertEqual(row["risk_mode"], "regular")
        self.assertEqual(row["layer_kind"], "base")
        self.assertEqual(float(row["selected_volume"]), 3.0)
        self.assertEqual(float(row["stop_distance"]), 85.0)
        self.assertEqual(float(row["planned_stop_distance"]), 85.0)
        self.assertEqual(float(row["actual_stop_distance"]), 80.0)
        self.assertEqual(float(row["risk_amount"]), 2400.0)
        self.assertAlmostEqual(float(row["r_multiple"]), 9300.0 / 2400.0)
        self.assertEqual(int(row["actual_risk_recomputed"]), 1)
        self.assertEqual(audit["risk_source_audit"]["unmatched_source_ids"], ["32"])

    def test_actual_fill_risk_does_not_replace_signal_time_planned_stop_feature(self) -> None:
        module = load_module()
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "T1",
                    "order_id": "O1",
                    "datetime": "2025-01-03 00:00:00+08:00",
                    "vt_symbol": "rb2505.SHFE",
                    "direction": "Long",
                    "offset": "Open",
                    "price": 100.0,
                    "volume": 2,
                },
                {
                    "trade_id": "C1",
                    "order_id": "C-O1",
                    "datetime": "2025-01-10 00:00:00+08:00",
                    "vt_symbol": "rb2505.SHFE",
                    "direction": "Short",
                    "offset": "Close",
                    "price": 110.0,
                    "volume": 2,
                },
            ]
        )
        risks = pd.DataFrame(
            [
                {
                    "entry_index": 1,
                    "datetime": "2025-01-02 00:00:00+08:00",
                    "contract_vt_symbol": "rb2505.SHFE",
                    "product_vt_symbol": "rb.SHFE",
                    "direction": "long",
                    "volume": 2,
                    "selected_volume": 2,
                    "entry_context": "flat_entry",
                    "planned_entry_price": 105.0,
                    "stop_price": 90.0,
                    "stop_distance": 15.0,
                    "size": 10,
                    "risk_per_contract": 150.0,
                }
            ]
        )
        lots = pd.DataFrame(
            [
                {
                    "open_trade_id": "T1",
                    "close_trade_id": "C1",
                    "vt_symbol": "rb2505.SHFE",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "entry_date": "2025-01-03",
                    "exit_date": "2025-01-10",
                    "entry_price": 100.0,
                    "volume": 2.0,
                    "size": 10,
                    "realized_pnl": 200.0,
                    "risk_amount": 300.0,
                    "risk_per_contract": 150.0,
                    "r_multiple": 2.0 / 3.0,
                    "stop_distance": 15.0,
                    "entry_context": "flat_entry",
                }
            ]
        )

        enriched, lineage, audit = module.build_complete_closed_lot_lineage(
            lots,
            trades,
            risks,
            pd.DataFrame(),
            priceticks={"rb2505.SHFE": 1.0},
        )
        row = enriched.iloc[0]
        lineage_row = lineage.iloc[0]

        self.assertEqual(float(row["planned_stop_distance"]), 15.0)
        self.assertEqual(float(row["stop_distance"]), 15.0)
        self.assertEqual(float(row["actual_stop_distance"]), 10.0)
        self.assertEqual(float(row["risk_per_contract"]), 100.0)
        self.assertEqual(float(row["risk_amount"]), 200.0)
        self.assertEqual(float(row["r_multiple"]), 1.0)
        self.assertEqual(float(lineage_row["actual_entry_price"]), 100.0)
        self.assertEqual(int(lineage_row["actual_risk_recomputed"]), 1)
        self.assertEqual(audit["actual_risk_recomputed_open_count"], 1)

    def test_feature_cutoff_is_strictly_before_entry(self) -> None:
        module = load_module()
        bars = sample_bars()
        entry_date = bars.loc[70, "date"]
        features = module.technical_features_before_entry(bars, entry_date, "long")
        self.assertEqual(features["feature_date"], bars.loc[69, "date"])
        self.assertLess(features["feature_date"], entry_date)

    def test_future_mutation_does_not_change_features(self) -> None:
        module = load_module()
        bars = sample_bars()
        entry_date = bars.loc[70, "date"]
        before = module.technical_features_before_entry(bars, entry_date, "long")
        changed = bars.copy()
        changed.loc[changed["date"] >= entry_date, ["open", "high", "low", "close"]] = 999_999.0
        after = module.technical_features_before_entry(changed, entry_date, "long")
        for key in module.TECHNICAL_FEATURE_COLUMNS:
            left = before[key]
            right = after[key]
            if pd.isna(left) and pd.isna(right):
                continue
            self.assertAlmostEqual(float(left), float(right), places=12, msg=key)

    def test_directional_features_flip_for_long_and_short(self) -> None:
        module = load_module()
        bars = sample_bars()
        entry_date = bars.loc[80, "date"]
        long = module.technical_features_before_entry(bars, entry_date, "long")
        short = module.technical_features_before_entry(bars, entry_date, "short")
        for key in ["directional_return20", "directional_return60", "efficiency20", "efficiency60", "di_spread14"]:
            self.assertAlmostEqual(float(long[key]), -float(short[key]), places=12, msg=key)
        self.assertAlmostEqual(float(long["directional_range_position20"]), 1.0 - float(short["directional_range_position20"]), places=12)

    def test_partial_closes_are_one_entry_event(self) -> None:
        module = load_module()
        lots = pd.DataFrame(
            [
                {
                    "open_trade_id": "OPEN.1",
                    "vt_symbol": "rb2501.SHFE",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "entry_date": "2025-01-02",
                    "exit_date": "2025-02-01",
                    "entry_price": 3_500.0,
                    "volume": 2.0,
                    "risk_amount": 1_000.0,
                    "realized_pnl": 2_000.0,
                    "stop_distance": 50.0,
                    "entry_context": "flat_entry",
                },
                {
                    "open_trade_id": "OPEN.1",
                    "vt_symbol": "rb2501.SHFE",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "entry_date": "2025-01-02",
                    "exit_date": "2025-03-01",
                    "entry_price": 3_500.0,
                    "volume": 3.0,
                    "risk_amount": 1_500.0,
                    "realized_pnl": -500.0,
                    "stop_distance": 50.0,
                    "entry_context": "flat_entry",
                },
            ]
        )
        events, audit = module.aggregate_entry_events(lots)
        self.assertEqual(len(events), 1)
        self.assertEqual(int(events.iloc[0]["closed_lot_count"]), 2)
        self.assertAlmostEqual(float(events.iloc[0]["risk_amount"]), 2_500.0)
        self.assertAlmostEqual(float(events.iloc[0]["realized_pnl"]), 1_500.0)
        self.assertAlmostEqual(float(events.iloc[0]["r_multiple"]), 0.6)
        self.assertEqual(int(audit["inconsistent_group_count"]), 0)

    def test_atr_and_adx_match_talib_wilder_definition(self) -> None:
        module = load_module()
        bars = sample_bars(120)
        panel = module.indicator_panel(bars)
        expected_atr = talib.ATR(
            bars["high"].to_numpy(dtype=float),
            bars["low"].to_numpy(dtype=float),
            bars["close"].to_numpy(dtype=float),
            timeperiod=14,
        )
        expected_adx = talib.ADX(
            bars["high"].to_numpy(dtype=float),
            bars["low"].to_numpy(dtype=float),
            bars["close"].to_numpy(dtype=float),
            timeperiod=14,
        )
        np.testing.assert_allclose(panel["atr14"].to_numpy(), expected_atr, rtol=1e-12, atol=1e-12, equal_nan=True)
        np.testing.assert_allclose(panel["adx14"].to_numpy(), expected_adx, rtol=1e-10, atol=1e-10, equal_nan=True)

    def test_database_loader_is_exact_and_read_only(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.db"
            with sqlite3.connect(path) as connection:
                connection.execute(
                    "CREATE TABLE dbbardata (symbol TEXT, exchange TEXT, datetime TEXT, interval TEXT, "
                    "volume REAL, open_interest REAL, open_price REAL, high_price REAL, low_price REAL, close_price REAL)"
                )
                connection.executemany(
                    "INSERT INTO dbbardata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        ("rb2501", "SHFE", "2025-01-02 00:00:00", "d", 10, 20, 100, 103, 99, 102),
                        ("rb2501", "SHFE", "2025-01-03 00:00:00", "d", 11, 21, 102, 104, 101, 103),
                        ("rb2501", "SHFE", "2025-01-03 09:01:00", "1m", 99, 99, 1, 1, 1, 1),
                        ("rb2501", "DCE", "2025-01-03 00:00:00", "d", 99, 99, 1, 1, 1, 1),
                    ],
                )
            before = path.read_bytes()
            bars = module.load_contract_bars_from_database("rb2501.SHFE", path)
            self.assertEqual(len(bars), 2)
            self.assertEqual(list(bars["close"]), [102.0, 103.0])
            self.assertEqual(path.read_bytes(), before)

    def test_retry_and_rollover_pnl_reconcile_to_flat_parent(self) -> None:
        module = load_module()
        trades = pd.DataFrame(
            [
                {"trade_id": "T1", "order_id": "O1", "datetime": "2025-01-02 00:00:00+08:00", "vt_symbol": "rb2501.SHFE", "direction": "Long", "offset": "Open", "volume": 2},
                {"trade_id": "C1", "order_id": "C-O1", "datetime": "2025-01-03 00:00:00+08:00", "vt_symbol": "rb2501.SHFE", "direction": "Short", "offset": "Close", "volume": 2, "exit_reason": "rollover_close"},
                {"trade_id": "T2", "order_id": "O2", "datetime": "2025-01-03 00:00:00+08:00", "vt_symbol": "rb2505.SHFE", "direction": "Long", "offset": "Open", "volume": 2},
                {"trade_id": "C2", "order_id": "O2.stage847_c9.1", "datetime": "2025-01-04 09:01:00+08:00", "vt_symbol": "rb2505.SHFE", "direction": "Short", "offset": "Close", "volume": 2},
                {"trade_id": "T3", "order_id": "O2.stage847_c9.2", "datetime": "2025-01-04 09:20:00+08:00", "vt_symbol": "rb2505.SHFE", "direction": "Long", "offset": "Open", "volume": 2},
                {"trade_id": "C3", "order_id": "O2.stage847_c9.3", "datetime": "2025-01-05 00:00:00+08:00", "vt_symbol": "rb2505.SHFE", "direction": "Short", "offset": "Close", "volume": 2},
            ]
        )
        risks = pd.DataFrame(
            [
                {"entry_index": 1, "datetime": "2025-01-01 00:00:00+08:00", "contract_vt_symbol": "rb2501.SHFE", "direction": "long", "volume": 2, "entry_context": "flat_entry", "stop_distance": 10, "size": 10, "risk_per_contract": 100},
                {"entry_index": 2, "datetime": "2025-01-03 00:00:00+08:00", "contract_vt_symbol": "rb2505.SHFE", "direction": "long", "volume": 2, "entry_context": "rollover_reopen", "stop_distance": 12, "size": 10, "risk_per_contract": 120},
            ]
        )
        lots = pd.DataFrame(
            [
                {"open_trade_id": "T1", "close_trade_id": "C1", "vt_symbol": "rb2501.SHFE", "product": "rb.SHFE", "direction": "long", "entry_date": "2025-01-02", "exit_date": "2025-01-03", "entry_price": 100, "volume": 2, "size": 10, "risk_amount": 200, "realized_pnl": 100, "stop_distance": 10, "entry_context": "flat_entry"},
                {"open_trade_id": "T2", "close_trade_id": "C2", "vt_symbol": "rb2505.SHFE", "product": "rb.SHFE", "direction": "long", "entry_date": "2025-01-03", "exit_date": "2025-01-04", "entry_price": 101, "volume": 2, "size": 10, "risk_amount": 240, "realized_pnl": -50, "stop_distance": 12, "entry_context": "rollover_reopen"},
                {"open_trade_id": "T3", "close_trade_id": "C3", "vt_symbol": "rb2505.SHFE", "product": "rb.SHFE", "direction": "long", "entry_date": "2025-01-04", "exit_date": "2025-01-05", "entry_price": 101, "volume": 2, "size": 10, "risk_amount": np.nan, "realized_pnl": 200, "stop_distance": np.nan, "entry_context": np.nan},
            ]
        )
        enriched, lineage, audit = module.build_complete_closed_lot_lineage(lots, trades, risks, pd.DataFrame())
        self.assertEqual(set(lineage["parent_event_id"]), {"T1"})
        self.assertEqual(audit["orphan_open_count"], 0)
        events, aggregate_audit = module.aggregate_entry_events(enriched)
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(float(events.iloc[0]["realized_pnl"]), 250.0)
        self.assertAlmostEqual(float(events.iloc[0]["risk_amount"]), 440.0)
        self.assertAlmostEqual(float(events.iloc[0]["r_multiple"]), 250.0 / 440.0)
        self.assertAlmostEqual(float(aggregate_audit["closed_lot_pnl"]), 250.0)

    def test_discovery_thresholds_ignore_later_segments(self) -> None:
        module = load_module()
        frame = pd.DataFrame(
            {
                "sample_segment": ["discovery"] * 4 + ["validation", "holdout"],
                "stop_atr14": [1.0, 2.0, 3.0, 4.0, 100.0, 200.0],
                "directional_range_position20": [0.1, 0.2, 0.3, 0.4, 99.0, 199.0],
                "adx14": [10.0, 20.0, 30.0, 40.0, 999.0, 1999.0],
                "directional_clv": [0.2, 0.4, 0.6, 0.8, 10.0, 20.0],
                "body_ratio": [0.1, 0.3, 0.5, 0.7, 10.0, 20.0],
            }
        )
        first = module.discovery_thresholds(frame)
        changed = frame.copy()
        changed.loc[changed["sample_segment"] != "discovery", module.THRESHOLD_COLUMNS] = -999_999.0
        second = module.discovery_thresholds(changed)
        self.assertEqual(first, second)

    def test_feature_output_rejects_ai_columns(self) -> None:
        module = load_module()
        clean = pd.DataFrame({"stop_atr14": [1.0], "directional_clv": [0.8]})
        module.assert_no_ai_features(clean)
        with self.assertRaises(ValueError):
            module.assert_no_ai_features(clean.assign(ai_product_pool_rank=1))

    def test_baseline_summary_matches_equity_math(self) -> None:
        module = load_module()
        daily = pd.DataFrame(
            {
                "date": pd.bdate_range("2020-01-01", periods=4),
                "account_equity": [150_000.0, 180_000.0, 135_000.0, 210_000.0],
                "slippage": [0.0, 1.0, 2.0, 3.0],
                "trade_count": [0, 1, 2, 1],
                "broker10_margin_to_equity_pct": [0.0, 20.0, 40.0, 10.0],
            }
        )
        row = module.summarize_baseline(daily, 150_000.0)
        self.assertAlmostEqual(row["end_equity"], 210_000.0)
        self.assertAlmostEqual(row["total_return_pct"], 40.0)
        self.assertAlmostEqual(row["max_dd_pct"], -25.0)
        self.assertAlmostEqual(row["total_slippage"], 6.0)
        self.assertAlmostEqual(row["total_trade_count"], 4.0)
        self.assertAlmostEqual(row["max_broker10_margin_to_equity_pct"], 40.0)

    def test_technical_plot_accepts_composite_table_with_existing_r_sum(self) -> None:
        module = load_module()
        events = pd.DataFrame(
            {
                "stop_atr14": [0.5, 1.0],
                "r_multiple": [1.0, -0.5],
                "sample_segment": ["discovery", "validation"],
            }
        )
        bins = pd.DataFrame(
            {
                "feature": ["stop_atr14", "directional_clv"],
                "sample_segment": ["discovery", "discovery"],
                "feature_bin": ["Q1", "Q4"],
                "r_mean": [0.2, 0.4],
            }
        )
        composites = pd.DataFrame(
            {
                "rule": ["tight_directional_efficiency"],
                "r_sum": [6.0],
                "discovery_r_sum": [3.0],
                "validation_r_sum": [2.0],
                "holdout_r_sum": [1.0],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "technical.png"
            module.TECHNICAL_CHART_PATH = output
            module._plot_technical(events, bins, composites)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
