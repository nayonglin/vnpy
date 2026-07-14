from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

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
MODULE_NAME = "stage135_no_jd_stage208_true_carry_degraded"
MODULE_PATH = TOOLS_DIR / f"{MODULE_NAME}.py"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _module():
    if not MODULE_PATH.exists():
        raise AssertionError(f"production module missing: {MODULE_PATH}")
    return importlib.import_module(MODULE_NAME)


class Stage135FrozenInputTest(unittest.TestCase):
    def test_drop_jd_without_replacement_preserves_remaining_order(self) -> None:
        s135 = _module()
        signals = pd.DataFrame(
            {
                "date": ["2022-01-04", "2022-01-05"],
                "long_products": ["rb.SHFE,jd.DCE,au.SHFE", "jd.DCE"],
                "short_products": ["MA.CZCE,SM.CZCE", "cu.SHFE,jd.DCE"],
            }
        )

        clean, audit = s135.drop_jd_without_replacement(signals)

        self.assertEqual(clean.loc[0, "long_products"], "rb.SHFE,au.SHFE")
        self.assertEqual(clean.loc[1, "long_products"], "")
        self.assertEqual(clean.loc[1, "short_products"], "cu.SHFE")
        self.assertEqual(audit["removed_jd_leg_count"], 3)
        self.assertEqual(audit["replacement_leg_count"], 0)

    def test_price_frame_fails_closed_on_missing_non_jd_spec(self) -> None:
        s135 = _module()
        product_returns = pd.DataFrame(
            {
                "date": ["2022-01-04"],
                "product_vt_symbol": ["rb.SHFE"],
                "main_contract_vt": ["rb2205.SHFE"],
                "main_close": [4500.0],
                "product_return": [0.01],
            }
        )

        with self.assertRaisesRegex(ValueError, "missing_exact_spec:rb.SHFE"):
            s135.build_price_frame(
                product_returns,
                sizes={},
                margin_ratios={"rb.SHFE": 0.10},
                slippages={"rb.SHFE": 1.0},
            )

    def test_frozen_one_lot_roll_day_has_no_cross_contract_price_jump(self) -> None:
        s135 = _module()
        product_returns = pd.DataFrame(
            {
                "date": ["2022-01-04", "2022-01-05"],
                "product_vt_symbol": ["rb.SHFE", "rb.SHFE"],
                "main_contract_vt": ["rb2205.SHFE", "rb2210.SHFE"],
                "main_close": [4500.0, 5000.0],
                "product_return": [0.0, 0.0],
            }
        )
        price = s135.build_price_frame(
            product_returns,
            sizes={"rb.SHFE": 10},
            margin_ratios={"rb.SHFE": 0.10},
            slippages={"rb.SHFE": 1.0},
        )
        signals = pd.DataFrame(
            {
                "date": pd.to_datetime(["2022-01-04", "2022-01-05"]),
                "long_products": ["rb.SHFE", "rb.SHFE"],
                "short_products": ["", ""],
            }
        )

        daily = s135.build_frozen_one_lot_daily(price, signals)

        self.assertEqual(daily["gross_pnl"].tolist(), [0.0, 0.0])
        self.assertEqual(daily["turnover_contracts"].tolist(), [1, 2])
        self.assertEqual(daily["slippage_cost"].tolist(), [10.0, 20.0])
        self.assertEqual(daily["daily_pnl"].tolist(), [-10.0, -20.0])

    def test_prelisting_signal_leg_is_skipped_without_replacement(self) -> None:
        s135 = _module()
        product_returns = pd.DataFrame(
            {
                "date": ["2023-06-01"],
                "product_vt_symbol": ["rb.SHFE"],
                "main_contract_vt": ["rb2310.SHFE"],
                "main_close": [3500.0],
                "product_return": [0.0],
            }
        )
        price = s135.build_price_frame(
            product_returns,
            sizes={"rb.SHFE": 10},
            margin_ratios={"rb.SHFE": 0.10},
            slippages={"rb.SHFE": 1.0},
        )
        signals = pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-06-01"]),
                "long_products": ["lc.GFEX,rb.SHFE"],
                "short_products": [""],
            }
        )

        daily = s135.build_frozen_one_lot_daily(price, signals)

        self.assertEqual(daily.loc[0, "desired_leg_count"], 2)
        self.assertEqual(daily.loc[0, "executable_leg_count"], 1)
        self.assertEqual(daily.loc[0, "unavailable_signal_leg_count"], 1)


class Stage135TimingAndFillTest(unittest.TestCase):
    def test_stage101_scale_is_shifted_one_day(self) -> None:
        s135 = _module()
        dates = pd.bdate_range("2022-01-03", periods=66)
        pnl = np.array([100.0 + (index % 7) * 10.0 for index in range(66)])
        base = pd.DataFrame({"date": dates, "daily_pnl": pnl})
        changed = base.copy()
        changed.loc[63, "daily_pnl"] = 1_000_000.0

        scale_a = s135.build_stage101_scale(base, capital=150_000.0)
        scale_b = s135.build_stage101_scale(changed, capital=150_000.0)

        self.assertEqual(float(scale_a.iloc[62]), 0.0)
        self.assertGreater(float(scale_a.iloc[63]), 0.0)
        self.assertAlmostEqual(float(scale_a.iloc[63]), float(scale_b.iloc[63]), places=12)
        self.assertNotAlmostEqual(float(scale_a.iloc[64]), float(scale_b.iloc[64]), places=6)

    def test_fill_prefers_prior_night_then_day_and_never_falls_back(self) -> None:
        s135 = _module()
        bars = pd.DataFrame(
            {
                "bar_datetime": pd.to_datetime(
                    [
                        "2022-01-04 21:00:00",
                        "2022-01-04 21:01:00",
                        "2022-01-05 09:00:00",
                    ]
                ),
                "open": [101.0, 102.0, 103.0],
                "source_file": ["night.csv", "night.csv", "day.csv"],
            }
        )
        loader = lambda _contract: bars

        night = s135.resolve_fill_price(
            "rb2205.SHFE", pd.Timestamp("2022-01-04"), pd.Timestamp("2022-01-05"), loader
        )
        day = s135.resolve_fill_price(
            "rb2205.SHFE",
            pd.Timestamp("2022-01-03"),
            pd.Timestamp("2022-01-05"),
            loader,
        )

        self.assertEqual(night["fill_price"], 101.0)
        self.assertEqual(night["price_source"], "raw_prev_signal_night_2100_2105_first_open")
        self.assertEqual(day["fill_price"], 103.0)
        self.assertEqual(day["price_source"], "raw_fill_day_0900_0905_first_open")
        with self.assertRaisesRegex(RuntimeError, "missing_real_fill"):
            s135.resolve_fill_price(
                "rb2205.SHFE",
                pd.Timestamp("2022-01-02"),
                pd.Timestamp("2022-01-03"),
                loader,
            )

    def test_reversal_pnl_is_split_at_real_fill_and_slippage_uses_delta(self) -> None:
        s135 = _module()
        bars = pd.DataFrame(
            {
                "bar_datetime": pd.to_datetime(["2022-01-04 21:00:00"]),
                "open": [105.0],
                "source_file": ["rb.csv"],
            }
        )
        old_positions = {
            "rb2205.SHFE": {
                "lots": 1,
                "product": "rb.SHFE",
                "size": 10.0,
                "slippage": 1.0,
                "last_mark": 100.0,
            }
        }
        target_meta = {
            "rb2205.SHFE": {
                "product": "rb.SHFE",
                "size": 10.0,
                "slippage": 1.0,
                "main_close": 100.0,
                "margin_per_contract": 100.0,
            }
        }

        new_positions, daily, orders = s135.replay_target_transition(
            old_positions=old_positions,
            targets={"rb2205.SHFE": -1},
            target_meta=target_meta,
            date=pd.Timestamp("2022-01-05"),
            signal_date=pd.Timestamp("2022-01-04"),
            minute_loader=lambda _contract: bars,
            slippage_multiplier=1.0,
        )

        self.assertEqual(new_positions["rb2205.SHFE"]["lots"], -1)
        self.assertEqual(daily["gross_pnl"], 100.0)
        self.assertEqual(daily["turnover_contracts"], 2)
        self.assertEqual(daily["slippage_cost"], 20.0)
        self.assertEqual(daily["net_pnl"], 80.0)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["delta_lots"], -2)


class Stage135AccountingAndGateTest(unittest.TestCase):
    def test_aggregate_margin_gate_flattens_satellite_when_previous_equity_is_insufficient(self) -> None:
        s135 = _module()
        targets = {"rb2205.SHFE": 1}
        meta = {"rb2205.SHFE": {"margin_per_contract": 20_000.0}}

        kept, kept_meta, audit = s135.apply_aggregate_margin_gate(
            targets,
            meta,
            c9_margin_exact=75_000.0,
            previous_combined_equity=100_000.0,
        )

        self.assertEqual(kept, {})
        self.assertEqual(kept_meta, {})
        self.assertEqual(audit["margin_gate_skipped"], 1)
        self.assertAlmostEqual(audit["proposed_broker10_margin_to_equity_pct"], 104.5)

    def test_combo_reconciliation_requires_both_equity_identities(self) -> None:
        s135 = _module()
        daily = pd.DataFrame(
            {
                "c9_net_pnl": [0.0, 10.0, -5.0],
                "satellite_net_pnl": [0.0, 2.0, 3.0],
                "c9_account_equity": [150_000.0, 150_010.0, 150_005.0],
                "combined_equity": [150_000.0, 150_012.0, 150_010.0],
            }
        )

        audit = s135.reconcile_combo_daily(daily, capital=150_000.0)

        self.assertLessEqual(audit["max_abs_error_from_daily_pnl"], 1e-9)
        self.assertLessEqual(audit["max_abs_error_from_c9_plus_satellite"], 1e-9)
        self.assertTrue(audit["reconciliation_pass"])

    def test_longest_underwater_uses_consecutive_trading_rows(self) -> None:
        s135 = _module()

        result = s135.longest_underwater_days(pd.Series([100.0, 90.0, 80.0, 110.0, 100.0, 120.0]))

        self.assertEqual(result, 2)

    def test_canary_gate_is_conjunctive(self) -> None:
        s135 = _module()
        evidence = {
            "fallback_order_count": 0,
            "max_reconciliation_error": 0.0,
            "max_aggregate_broker10_margin_to_equity_pct": 99.0,
            "return_retention_pct": 75.0,
            "a_max_drawdown_pct": -50.0,
            "c_max_drawdown_pct": -40.0,
            "a_longest_underwater_days": 300,
            "c_longest_underwater_days": 200,
            "b_min_equity": 100_000.0,
            "c_min_equity": 90_000.0,
        }

        passed = s135.evaluate_canary(evidence)
        failed = s135.evaluate_canary({**evidence, "return_retention_pct": 69.999})

        self.assertTrue(passed["canary_pass"])
        self.assertFalse(failed["canary_pass"])
        self.assertIn("return_retention_below_70pct", failed["failed_checks"])

    def test_window_simulation_starts_flat_then_carries_real_filled_position(self) -> None:
        s135 = _module()
        dates = pd.to_datetime(["2022-01-03", "2022-01-04", "2022-01-05"])
        c9 = pd.DataFrame(
            {
                "date": dates,
                "net_pnl": [0.0, 0.0, 0.0],
                "total_slippage": [0.0, 0.0, 0.0],
                "trade_count": [0, 0, 0],
                "account_equity": [150_000.0, 150_000.0, 150_000.0],
                "total_margin_exact": [0.0, 0.0, 0.0],
            }
        )
        price = pd.DataFrame(
            {
                "date": dates,
                "product_vt_symbol": ["rb.SHFE"] * 3,
                "main_contract_vt": ["rb2205.SHFE"] * 3,
                "main_close": [100.0, 102.0, 104.0],
                "product_return": [0.0, 0.02, 2.0 / 102.0],
                "prev_main_close": [100.0, 100.0, 102.0],
                "size": [1.0, 1.0, 1.0],
                "margin_ratio": [0.10, 0.10, 0.10],
                "slippage": [0.0, 0.0, 0.0],
                "margin_per_contract": [10.0, 10.2, 10.4],
            }
        )
        signals = pd.DataFrame(
            {
                "date": dates,
                "long_products": ["rb.SHFE"] * 3,
                "short_products": [""] * 3,
            }
        )
        scale = pd.Series([1.0, 1.0, 1.0], index=dates)
        bars = pd.DataFrame(
            {
                "bar_datetime": pd.to_datetime(["2022-01-03 21:00:00"]),
                "open": [101.0],
                "source_file": ["rb.csv"],
            }
        )

        daily, targets, orders = s135.simulate_window(
            c9,
            price,
            signals,
            scale,
            requested_start_month="2022-01",
            minute_loader=lambda _contract: bars,
            slippage_multiplier=1.0,
        )

        self.assertEqual(targets.loc[0, "start_day_forced_flat"], 1)
        self.assertEqual(targets.loc[0, "held_contract_count"], 0)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders.loc[0, "date"], pd.Timestamp("2022-01-04"))
        self.assertEqual(daily["satellite_net_pnl"].tolist(), [0.0, 1.0, 2.0])
        self.assertEqual(daily["combined_equity"].tolist(), [150_000.0, 150_001.0, 150_003.0])
        self.assertTrue(s135.reconcile_combo_daily(daily)["reconciliation_pass"])

    def test_margin_gate_uses_previous_close_state_not_current_close_margin(self) -> None:
        s135 = _module()
        dates = pd.to_datetime(["2022-01-03", "2022-01-04", "2022-01-05"])
        c9 = pd.DataFrame(
            {
                "date": dates,
                "net_pnl": [0.0, 0.0, 0.0],
                "total_slippage": [0.0, 0.0, 0.0],
                "trade_count": [0, 0, 0],
                "account_equity": [150_000.0, 150_000.0, 150_000.0],
                "total_margin_exact": [0.0, 140_000.0, 0.0],
            }
        )
        price = pd.DataFrame(
            {
                "date": dates,
                "product_vt_symbol": ["rb.SHFE"] * 3,
                "main_contract_vt": ["rb2205.SHFE"] * 3,
                "main_close": [100.0, 102.0, 104.0],
                "product_return": [0.0, 0.02, 2.0 / 102.0],
                "prev_main_close": [100.0, 100.0, 102.0],
                "size": [1.0, 1.0, 1.0],
                "margin_ratio": [0.10, 0.10, 0.10],
                "slippage": [0.0, 0.0, 0.0],
                "margin_per_contract": [10.0, 10.2, 10.4],
            }
        )
        signals = pd.DataFrame(
            {
                "date": dates,
                "long_products": ["rb.SHFE"] * 3,
                "short_products": [""] * 3,
            }
        )
        scale = pd.Series([1.0, 1.0, 1.0], index=dates)
        bars = pd.DataFrame(
            {
                "bar_datetime": pd.to_datetime(
                    ["2022-01-03 21:00:00", "2022-01-04 21:00:00"]
                ),
                "open": [101.0, 103.0],
                "source_file": ["rb.csv", "rb.csv"],
            }
        )

        _daily, targets, orders = s135.simulate_window(
            c9,
            price,
            signals,
            scale,
            requested_start_month="2022-01",
            minute_loader=lambda _contract: bars,
            slippage_multiplier=1.0,
        )

        self.assertEqual(targets["held_contract_count"].tolist(), [0, 1, 0])
        self.assertEqual(targets["margin_gate_skipped"].tolist(), [0, 0, 1])
        self.assertEqual(orders["date"].tolist(), [pd.Timestamp("2022-01-04"), pd.Timestamp("2022-01-05")])
        self.assertEqual(targets.loc[1, "c9_margin_exact_known_pretrade"], 0.0)
        self.assertEqual(targets.loc[2, "c9_margin_exact_known_pretrade"], 140_000.0)

    def test_arm_summary_computes_return_retention_from_absolute_equity(self) -> None:
        s135 = _module()
        daily = pd.DataFrame(
            {
                "date": pd.to_datetime(["2022-01-03", "2022-01-04", "2022-01-05"]),
                "requested_start_month": ["2022-01"] * 3,
                "slippage_multiplier": [1.0] * 3,
                "c9_account_equity": [150_000.0, 175_000.0, 200_000.0],
                "carried_leg_equity": [150_000.0, 145_000.0, 135_000.0],
                "combined_equity": [150_000.0, 170_000.0, 185_000.0],
                "c9_net_pnl": [0.0, 25_000.0, 25_000.0],
                "satellite_net_pnl": [0.0, -5_000.0, -10_000.0],
                "c9_slippage_cost": [0.0, 100.0, 100.0],
                "satellite_slippage_cost": [0.0, 10.0, 10.0],
                "c9_trade_count": [0, 1, 1],
                "satellite_turnover_contracts": [0, 1, 1],
                "aggregate_broker10_margin_to_previous_equity_pct": [0.0, 50.0, 40.0],
                "margin_gate_skipped": [0, 0, 0],
            }
        )

        summary = s135.summarize_arms(daily)
        evidence = s135.build_canary_evidence(
            summary,
            reconciliation={
                "max_abs_error_from_daily_pnl": 0.0,
                "max_abs_error_from_c9_plus_satellite": 0.0,
                "max_abs_c9_source_equity_error": 0.0,
            },
            daily=daily,
            orders=pd.DataFrame(),
        )

        c = summary[summary["arm"].eq("C_c9_plus_no_jd_true_carried")].iloc[0]
        self.assertAlmostEqual(c["total_return_pct"], 35_000.0 / 150_000.0 * 100.0)
        self.assertAlmostEqual(evidence["return_retention_pct"], 70.0)
        self.assertEqual(evidence["fallback_order_count"], 0)


if __name__ == "__main__":
    unittest.main()
