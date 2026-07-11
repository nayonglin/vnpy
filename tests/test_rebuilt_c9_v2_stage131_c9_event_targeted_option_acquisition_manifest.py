from __future__ import annotations

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
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage131_c9_event_targeted_option_acquisition_manifest as s131


def _sample_lots() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "lot_id": ["L1", "L2", "L3", "L4"],
            "open_trade_id": ["T1", "T2", "T3", "T4"],
            "vt_symbol": ["m2209.DCE", "m2209.DCE", "m2209.DCE", "au2212.SHFE"],
            "direction": ["long", "long", "short", "long"],
            "entry_date": ["2022-03-09", "2022-03-09", "2022-03-09", "2022-03-10"],
            "exit_date": ["2022-03-20", "2022-03-25", "2022-03-15", "2022-04-01"],
            "entry_price": [3000.0, 3010.0, 3020.0, 400.0],
            "volume": [1.0, 2.0, 3.0, 1.0],
            "size": [10.0, 10.0, 10.0, 1000.0],
            "risk_amount": [100.0, 200.0, 300.0, 400.0],
            "risk_multiplier": [1.0, 1.0, 2.0, 1.0],
            "stop_distance": [50.0, 60.0, 70.0, 8.0],
            "selected_volume": [1.0, 2.0, 3.0, 1.0],
            "original_stop_price": [2950.0, 2950.0, 3090.0, 392.0],
            "risk_link_method": ["direct"] * 4,
        }
    )


class Stage131EventTargetedOptionAcquisitionManifestTest(unittest.TestCase):
    def test_source_usecols_exclude_outcome_and_equity_labels(self) -> None:
        forbidden = {
            "realized_pnl",
            "r_multiple",
            "winner",
            "account_equity",
            "net_pnl",
            "drawdown_pct",
            "entry_period_2022",
        }
        parsed_columns = {
            column
            for columns in s131.SOURCE_USECOLS.values()
            for column in columns
        }

        self.assertFalse(forbidden & parsed_columns)
        self.assertEqual(s131.SOURCE_USECOLS["trading_calendar"], ["date"])

    def test_tqsdk_underlying_conversion_is_mechanical(self) -> None:
        self.assertEqual(s131.to_tqsdk_underlying("m2209.DCE"), "DCE.m2209")
        self.assertEqual(s131.to_tqsdk_underlying("SA209.CZCE"), "CZCE.SA209")
        with self.assertRaises(ValueError):
            s131.to_tqsdk_underlying("missing_exchange")
        with self.assertRaises(ValueError):
            s131.to_tqsdk_underlying("m2209.UNKNOWN")

    def test_source_audit_rejects_bad_dates_values_and_direction(self) -> None:
        clean = _sample_lots()
        self.assertTrue(s131.audit_source_lots(clean)["source_audit_pass"])

        bad = clean.copy()
        bad.loc[0, "direction"] = "flat"
        bad.loc[1, "volume"] = 0.0
        bad.loc[2, "entry_price"] = -1.0
        bad.loc[3, "exit_date"] = "2022-03-01"
        audit = s131.audit_source_lots(bad)

        self.assertFalse(audit["source_audit_pass"])
        self.assertEqual(audit["invalid_direction_count"], 1)
        self.assertEqual(audit["nonpositive_volume_count"], 1)
        self.assertEqual(audit["nonpositive_entry_price_count"], 1)
        self.assertEqual(audit["exit_before_entry_count"], 1)

    def test_entry_risk_linking_covers_next_day_retry_and_volume_mismatch(self) -> None:
        trades = pd.DataFrame(
            {
                "trade_id": ["T1", "C1", "T2", "T3", "T4"],
                "datetime": [
                    "2022-03-09 00:00:00+08:00",
                    "2022-03-09 09:00:00+08:00",
                    "2022-03-09 10:00:00+08:00",
                    "2022-02-07 00:00:00+08:00",
                    "2022-03-30 00:00:00+08:00",
                ],
                "date": ["2022-03-09", "2022-03-09", "2022-03-09", "2022-02-07", "2022-03-30"],
                "vt_symbol": ["m2209.DCE", "m2209.DCE", "m2209.DCE", "AP205.CZCE", "fu2205.SHFE"],
                "direction": ["Long", "Short", "Long", "Long", "Long"],
                "offset": ["Open", "Close", "Open", "Open", "Open"],
                "price": [3000.0, 2945.0, 3001.0, 8888.0, 3750.0],
                "volume": [1.0, 1.0, 1.0, 2.0, 3.0],
            }
        )
        entry_risk = pd.DataFrame(
            {
                "entry_index": [1, 2, 3],
                "datetime": [
                    "2022-03-08 00:00:00+08:00",
                    "2022-01-28 00:00:00+08:00",
                    "2022-03-29 00:00:00+08:00",
                ],
                "date": ["2022-03-08", "2022-01-28", "2022-03-29"],
                "contract_vt_symbol": ["m2209.DCE", "AP205.CZCE", "fu2205.SHFE"],
                "direction": ["long", "long", "long"],
                "volume": [1.0, 2.0, 5.0],
                "stop_price": [2950.0, 8800.0, 3987.0],
                "stop_distance": [50.0, 88.0, 43.0],
                "risk_per_contract": [500.0, 880.0, 430.0],
                "actual_risk_amount": [500.0, 1760.0, 2150.0],
                "target_risk_amount": [500.0, 1760.0, 2150.0],
                "risk_multiplier": [1.0, 1.0, 2.0],
                "selected_volume": [1.0, 2.0, 5.0],
                "size": [10.0, 10.0, 10.0],
            }
        )

        trading_dates = pd.Series(
            pd.to_datetime(["2022-01-28", "2022-02-07", "2022-03-08", "2022-03-09", "2022-03-29", "2022-03-30"])
        )
        links, audit = s131.build_entry_risk_links(trades, entry_risk, trading_dates)

        self.assertTrue(audit["entry_risk_link_audit_pass"])
        self.assertEqual(audit["open_trade_count"], 4)
        self.assertEqual(audit["linked_open_trade_count"], 4)
        self.assertEqual(
            links.set_index("open_trade_id")["risk_link_method"].to_dict(),
            {
                "T1": "direct_exact_volume_next_trade_date",
                "T2": "intraday_retry_inherit",
                "T3": "direct_exact_volume_next_trade_date",
                "T4": "fallback_next_trade_date_volume_mismatch",
            },
        )
        self.assertEqual(links.set_index("open_trade_id").loc["T2", "original_stop_price"], 2950.0)
        self.assertEqual(links.set_index("open_trade_id").loc["T4", "original_stop_price"], 3987.0)

    def test_enriched_risk_uses_risk_per_contract_not_fill_to_stop_distance(self) -> None:
        lots = _sample_lots().iloc[[0]].drop(columns=["original_stop_price", "risk_link_method"]).copy()
        trades = pd.DataFrame(
            {
                "trade_id": ["T1"],
                "datetime": ["2022-03-09 00:00:00+08:00"],
                "date": ["2022-03-09"],
                "vt_symbol": ["m2209.DCE"],
                "direction": ["Long"],
                "offset": ["Open"],
                "price": [3000.0],
                "volume": [1.0],
            }
        )
        entry_risk = pd.DataFrame(
            {
                "entry_index": [1],
                "datetime": ["2022-03-08 00:00:00+08:00"],
                "date": ["2022-03-08"],
                "contract_vt_symbol": ["m2209.DCE"],
                "direction": ["long"],
                "volume": [1.0],
                "stop_price": [2950.0],
                "stop_distance": [50.0],
                "risk_per_contract": [600.0],
                "actual_risk_amount": [600.0],
                "target_risk_amount": [600.0],
            }
        )
        links, _ = s131.build_entry_risk_links(
            trades,
            entry_risk,
            pd.Series(pd.to_datetime(["2022-03-08", "2022-03-09"])),
        )

        enriched = s131.enrich_lots_with_entry_risk(lots, links)

        self.assertEqual(enriched.iloc[0]["recovered_original_risk_amount"], 600.0)
        self.assertEqual(enriched.iloc[0]["fill_to_original_stop_cash_distance"], 500.0)

    def test_same_day_open_without_intervening_close_is_not_retry(self) -> None:
        trades = pd.DataFrame(
            {
                "trade_id": ["T1", "T2"],
                "datetime": ["2022-03-09 00:00:00+08:00", "2022-03-09 10:00:00+08:00"],
                "date": ["2022-03-09", "2022-03-09"],
                "vt_symbol": ["m2209.DCE", "m2209.DCE"],
                "direction": ["Long", "Long"],
                "offset": ["Open", "Open"],
                "price": [3000.0, 3001.0],
                "volume": [1.0, 1.0],
            }
        )
        entry_risk = pd.DataFrame(
            {
                "entry_index": [1],
                "datetime": ["2022-03-08 00:00:00+08:00"],
                "date": ["2022-03-08"],
                "contract_vt_symbol": ["m2209.DCE"],
                "direction": ["long"],
                "volume": [1.0],
                "stop_price": [2950.0],
                "stop_distance": [50.0],
                "risk_per_contract": [500.0],
                "actual_risk_amount": [500.0],
                "target_risk_amount": [500.0],
            }
        )

        links, audit = s131.build_entry_risk_links(
            trades,
            entry_risk,
            pd.Series(pd.to_datetime(["2022-03-08", "2022-03-09"])),
        )

        self.assertEqual(set(links["open_trade_id"]), {"T1"})
        self.assertEqual(audit["intraday_retry_inherit_count"], 0)
        self.assertEqual(audit["unmatched_open_trade_count"], 1)
        self.assertFalse(audit["entry_risk_link_audit_pass"])

    def test_entry_risk_linking_fails_closed_on_direct_ambiguity(self) -> None:
        trades = pd.DataFrame(
            {
                "trade_id": ["T1"],
                "datetime": ["2022-03-09 00:00:00+08:00"],
                "date": ["2022-03-09"],
                "vt_symbol": ["m2209.DCE"],
                "direction": ["Long"],
                "offset": ["Open"],
                "price": [3000.0],
                "volume": [1.0],
            }
        )
        entry_risk = pd.DataFrame(
            {
                "entry_index": [1, 2],
                "datetime": ["2022-03-08 00:00:00+08:00"] * 2,
                "date": ["2022-03-08"] * 2,
                "contract_vt_symbol": ["m2209.DCE"] * 2,
                "direction": ["long"] * 2,
                "volume": [1.0, 1.0],
                "stop_price": [2950.0, 2940.0],
                "stop_distance": [50.0, 60.0],
                "risk_per_contract": [500.0, 600.0],
                "actual_risk_amount": [500.0, 600.0],
                "target_risk_amount": [500.0, 600.0],
            }
        )

        links, audit = s131.build_entry_risk_links(
            trades,
            entry_risk,
            pd.Series(pd.to_datetime(["2022-03-08", "2022-03-09"])),
        )

        self.assertTrue(links.empty)
        self.assertEqual(audit["ambiguous_direct_count"], 1)
        self.assertFalse(audit["entry_risk_link_audit_pass"])

    def test_entry_risk_not_from_previous_trading_date_is_rejected(self) -> None:
        trades = pd.DataFrame(
            {
                "trade_id": ["T1"],
                "datetime": ["2022-03-09 00:00:00+08:00"],
                "date": ["2022-03-09"],
                "vt_symbol": ["m2209.DCE"],
                "direction": ["Long"],
                "offset": ["Open"],
                "price": [3000.0],
                "volume": [1.0],
            }
        )
        entry_risk = pd.DataFrame(
            {
                "entry_index": [1],
                "datetime": ["2022-03-07 00:00:00+08:00"],
                "date": ["2022-03-07"],
                "contract_vt_symbol": ["m2209.DCE"],
                "direction": ["long"],
                "volume": [1.0],
                "stop_price": [2950.0],
                "stop_distance": [50.0],
                "risk_per_contract": [500.0],
                "actual_risk_amount": [500.0],
                "target_risk_amount": [500.0],
            }
        )
        trading_dates = pd.Series(pd.to_datetime(["2022-03-07", "2022-03-08", "2022-03-09"]))

        links, audit = s131.build_entry_risk_links(trades, entry_risk, trading_dates)

        self.assertTrue(links.empty)
        self.assertEqual(audit["non_next_trading_date_candidate_count"], 1)
        self.assertFalse(audit["entry_risk_link_audit_pass"])

    def test_query_events_merge_same_contract_day_without_losing_exposure(self) -> None:
        lots = _sample_lots()
        events = s131.build_query_events(lots)

        self.assertEqual(len(events), 2)
        m_event = events[events["vt_symbol"].eq("m2209.DCE")].iloc[0]
        self.assertEqual(m_event["tqsdk_underlying"], "DCE.m2209")
        self.assertEqual(m_event["lot_count"], 3)
        self.assertEqual(m_event["lot_ids"], "L1|L2|L3")
        self.assertEqual(m_event["total_volume"], 6.0)
        self.assertEqual(m_event["total_original_risk_amount"], 600.0)
        self.assertEqual(m_event["metadata_query_method"], "TqApi.query_options")
        self.assertEqual(m_event["historical_context"], "TqBacktest(entry_date)")
        self.assertEqual(
            m_event["event_id"],
            s131.event_id_for("m2209.DCE", pd.Timestamp("2022-03-09")),
        )

    def test_requirements_preserve_lots_direction_and_original_stop_anchor(self) -> None:
        lots = _sample_lots()
        events = s131.build_query_events(lots)
        requirements = s131.build_acquisition_requirements(lots, events)

        self.assertEqual(len(requirements), len(lots))
        by_lot = requirements.set_index("lot_id")
        self.assertEqual(by_lot.loc["L1", "protection_option_class"], "PUT")
        self.assertEqual(by_lot.loc["L1", "stop_price_anchor"], 2950.0)
        self.assertEqual(by_lot.loc["L3", "protection_option_class"], "CALL")
        self.assertEqual(by_lot.loc["L3", "stop_price_anchor"], 3090.0)
        self.assertEqual(by_lot.loc["L4", "stop_price_anchor"], 392.0)
        self.assertTrue(by_lot["metadata_query_expired_as_of_entry"].eq(False).all())

    def test_sanitized_enriched_lots_do_not_persist_outcome_labels(self) -> None:
        lots = _sample_lots().assign(
            realized_pnl=[1.0, -2.0, 3.0, -4.0],
            r_multiple=[0.1, -0.2, 0.3, -0.4],
            winner=[True, False, True, False],
            entry_period_2022=[True] * 4,
        )

        sanitized = s131.sanitize_enriched_lots(lots)

        forbidden = {"realized_pnl", "r_multiple", "winner", "entry_period_2022"}
        self.assertFalse(forbidden & set(sanitized.columns))
        self.assertEqual(len(sanitized), len(lots))
        self.assertIn("original_stop_price", sanitized.columns)
        self.assertIn("risk_link_method", sanitized.columns)

    def test_manifest_audit_fails_on_dropped_or_duplicate_lot_mapping(self) -> None:
        lots = _sample_lots()
        events = s131.build_query_events(lots)
        requirements = s131.build_acquisition_requirements(lots, events)

        clean = s131.audit_manifest(lots, events, requirements)
        self.assertTrue(clean["manifest_audit_pass"])
        self.assertEqual(clean["mapped_lot_count"], 4)
        self.assertEqual(clean["event_id_mismatch_count"], 0)
        self.assertEqual(clean["stop_anchor_error_count"], 0)

        dirty = pd.concat([requirements.iloc[:-1], requirements.iloc[[0]]], ignore_index=True)
        failed = s131.audit_manifest(lots, events, dirty)
        self.assertFalse(failed["manifest_audit_pass"])
        self.assertEqual(failed["missing_lot_mapping_count"], 1)
        self.assertEqual(failed["duplicate_lot_mapping_count"], 2)

    def test_manifest_has_detached_checksum_without_self_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            payload_path = output_dir / "payload.csv"
            manifest_path = output_dir / "manifest.csv"
            checksum_path = output_dir / "manifest.sha256"
            payload_path.write_bytes(b"value\n1\n")

            manifest = s131.build_output_manifest(
                output_dir,
                excluded_paths={manifest_path, checksum_path},
            )
            s131._write_csv(manifest, manifest_path)
            checksum_path.write_text(
                s131.detached_checksum_line(manifest_path),
                encoding="ascii",
            )

            self.assertEqual(manifest["file"].tolist(), [payload_path.name])
            self.assertNotIn(manifest_path.name, manifest["file"].tolist())
            self.assertNotIn(checksum_path.name, manifest["file"].tolist())
            self.assertEqual(
                checksum_path.read_text(encoding="ascii"),
                f"{s131.file_sha256(manifest_path)}  {manifest_path.name}\n",
            )


if __name__ == "__main__":
    unittest.main()
