from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))
STAGE028_TOOLS_DIR = (
    ROOT / "research" / "lines" / "futures_trend_rollover_shape_same_volume" / "tools"
)
if str(STAGE028_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(STAGE028_TOOLS_DIR))

import qmt_roll_candidate_stage027_target_contract_history_config as stage027_cfg
import qmt_roll_candidate_stage028_delayed_rollover_config as stage028_cfg
import stage028_q_delayed_rollover_abc as stage028_tool
from qmt_roll_portfolio_strategy import ProductState, QmtRollPortfolioStrategy
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData


class Stage028DelayedRolloverTest(unittest.TestCase):
    def strategy(self, delay: int = 5) -> QmtRollPortfolioStrategy:
        strategy = QmtRollPortfolioStrategy.__new__(QmtRollPortfolioStrategy)
        strategy.rollover_delay_trading_days = delay
        strategy.rollover_delay_diagnostics = []
        strategy.strategy_engine = SimpleNamespace(bars={})
        return strategy

    @staticmethod
    def bar(symbol: str, date_text: str) -> BarData:
        return BarData(
            gateway_name="test",
            symbol=symbol,
            exchange=Exchange.DCE,
            datetime=datetime.fromisoformat(date_text),
            interval=Interval.DAILY,
            open_price=100,
            high_price=101,
            low_price=99,
            close_price=100,
        )

    def test_candidate_only_adds_fixed_five_session_delay(self) -> None:
        stage027 = stage027_cfg.build_candidate_overrides()
        stage028 = stage028_cfg.build_candidate_overrides()
        keys = set(stage027) | set(stage028)
        diff = {
            key: (stage027.get(key), stage028.get(key))
            for key in sorted(keys)
            if stage027.get(key) != stage028.get(key)
        }
        self.assertEqual({"rollover_delay_trading_days": (None, 5)}, diff)
        self.assertEqual("target_contract_only", stage028["rollover_shape_history_mode"])

    def test_rollover_becomes_due_on_fifth_later_trading_session(self) -> None:
        strategy = self.strategy()
        state = ProductState(product_vt_symbol="jm.DCE", contract_vt_symbol="jm2701.DCE")
        dates = [
            "2026-08-19",
            "2026-08-20",
            "2026-08-21",
            "2026-08-24",
            "2026-08-25",
            "2026-08-26",
        ]

        results = [
            strategy._rollover_delay_due(
                state=state,
                target_contract="jm2705.DCE",
                current_date=date,
            )
            for date in dates
        ]

        self.assertEqual([False, False, False, False, False, True], results)
        self.assertEqual("2026-08-19", state.rollover_pending_signal_date)
        self.assertEqual(5, state.rollover_pending_elapsed_trading_days)
        self.assertEqual(["scheduled", "waiting", "waiting", "waiting", "waiting", "due"], [
            row["status"] for row in strategy.rollover_delay_diagnostics
        ])

    def test_same_session_is_not_counted_twice(self) -> None:
        strategy = self.strategy()
        state = ProductState(product_vt_symbol="fu.SHFE", contract_vt_symbol="fu2609.SHFE")
        for _ in range(2):
            self.assertFalse(
                strategy._rollover_delay_due(
                    state=state,
                    target_contract="fu2611.SHFE",
                    current_date="2026-08-21",
                )
            )
        self.assertEqual(0, state.rollover_pending_elapsed_trading_days)

    def test_new_target_restarts_delay_clock(self) -> None:
        strategy = self.strategy()
        state = ProductState(product_vt_symbol="fu.SHFE", contract_vt_symbol="fu2609.SHFE")
        strategy._rollover_delay_due(
            state=state,
            target_contract="fu2610.SHFE",
            current_date="2026-08-20",
        )
        strategy._rollover_delay_due(
            state=state,
            target_contract="fu2610.SHFE",
            current_date="2026-08-21",
        )

        due = strategy._rollover_delay_due(
            state=state,
            target_contract="fu2611.SHFE",
            current_date="2026-08-24",
        )

        self.assertFalse(due)
        self.assertEqual("fu2611.SHFE", state.rollover_pending_target_contract)
        self.assertEqual("2026-08-24", state.rollover_pending_signal_date)
        self.assertEqual(0, state.rollover_pending_elapsed_trading_days)
        self.assertEqual(
            ["scheduled", "waiting", "target_changed_reset", "scheduled"],
            [row["status"] for row in strategy.rollover_delay_diagnostics],
        )

    def test_zero_delay_preserves_immediate_rollover_and_clears_pending(self) -> None:
        strategy = self.strategy(delay=0)
        state = ProductState(
            product_vt_symbol="SM.CZCE",
            contract_vt_symbol="SM809.CZCE",
            rollover_pending_target_contract="SM901.CZCE",
            rollover_pending_signal_date="2018-08-16",
            rollover_pending_last_counted_date="2018-08-16",
            rollover_pending_elapsed_trading_days=3,
        )

        self.assertTrue(
            strategy._rollover_delay_due(
                state=state,
                target_contract="SM901.CZCE",
                current_date="2018-08-17",
            )
        )
        self.assertEqual("", state.rollover_pending_target_contract)
        self.assertEqual(0, state.rollover_pending_elapsed_trading_days)

    def test_position_reset_cancels_pending_rollover(self) -> None:
        state = ProductState(
            product_vt_symbol="AP.CZCE",
            contract_vt_symbol="AP905.CZCE",
            rollover_pending_target_contract="AP910.CZCE",
            rollover_pending_signal_date="2019-04-12",
            rollover_pending_last_counted_date="2019-04-15",
            rollover_pending_elapsed_trading_days=1,
        )
        state.reset()
        self.assertEqual("", state.rollover_pending_target_contract)
        self.assertEqual(0, state.rollover_pending_elapsed_trading_days)

    def test_delay_applies_only_to_open_old_contract_position(self) -> None:
        strategy = self.strategy()
        state = ProductState(product_vt_symbol="jm.DCE", contract_vt_symbol="jm2701.DCE")

        self.assertTrue(strategy._rollover_delay_applies(state, "jm2705.DCE", 2))
        self.assertFalse(strategy._rollover_delay_applies(state, "jm2701.DCE", 2))
        self.assertFalse(strategy._rollover_delay_applies(state, "jm2705.DCE", 0))
        strategy.rollover_delay_trading_days = 0
        self.assertFalse(strategy._rollover_delay_applies(state, "jm2705.DCE", 2))

    def test_same_day_bar_rejects_stale_engine_fallback(self) -> None:
        strategy = self.strategy()
        stale = self.bar("jm2701", "2026-08-25")
        strategy.strategy_engine.bars = {stale.vt_symbol: stale}

        self.assertIsNone(strategy._same_day_bar(stale.vt_symbol, {}, "2026-08-26"))

        current = self.bar("jm2701", "2026-08-26")
        self.assertIs(
            current,
            strategy._same_day_bar(current.vt_symbol, {current.vt_symbol: current}, "2026-08-26"),
        )

    def test_missing_d5_bar_can_retry_as_overdue_without_repeating_due(self) -> None:
        strategy = self.strategy()
        state = ProductState(product_vt_symbol="jm.DCE", contract_vt_symbol="jm2701.DCE")
        dates = [
            "2026-08-19",
            "2026-08-20",
            "2026-08-21",
            "2026-08-24",
            "2026-08-25",
            "2026-08-26",
            "2026-08-27",
        ]

        results = [
            strategy._rollover_delay_due(
                state=state,
                target_contract="jm2705.DCE",
                current_date=date,
            )
            for date in dates
        ]

        self.assertEqual([False, False, False, False, False, True, True], results)
        self.assertEqual("due", strategy.rollover_delay_diagnostics[-2]["status"])
        self.assertEqual("overdue", strategy.rollover_delay_diagnostics[-1]["status"])

    def test_delay_contract_treats_blocked_due_as_attempt_not_execution(self) -> None:
        common = {
            "experiment_arm": "C",
            "product_vt_symbol": "jm.DCE",
            "old_contract_vt_symbol": "jm2701.DCE",
            "target_contract_vt_symbol": "jm2705.DCE",
            "signal_date": "2026-08-19",
            "required_trading_days": 5,
        }
        delay = pd.DataFrame(
            [
                {**common, "date": "2026-08-19", "elapsed_trading_days": 0, "status": "scheduled"},
                {**common, "date": "2026-08-26", "elapsed_trading_days": 5, "status": "due"},
                {
                    **common,
                    "date": "2026-08-26",
                    "elapsed_trading_days": 5,
                    "status": "due_old_bar_missing",
                },
                {**common, "date": "2026-08-27", "elapsed_trading_days": 6, "status": "overdue"},
            ]
        )
        rollover = pd.DataFrame(
            [
                {
                    "experiment_arm": "C",
                    "date": "2026-08-27",
                    "product_vt_symbol": "jm.DCE",
                    "target_contract_vt_symbol": "jm2705.DCE",
                }
            ]
        )
        trade_events = pd.DataFrame(
            columns=["experiment_arm", "offset", "product_vt_symbol", "vt_symbol", "date"]
        )

        result = stage028_tool._delay_contract(delay, rollover, trade_events)

        self.assertTrue(result["all_pass"])
        self.assertEqual(1, result["due_count"])
        self.assertEqual(1, result["overdue_count"])

    def test_full_period_gate_rejects_truncated_database_result(self) -> None:
        complete = pd.DataFrame(
            {
                "experiment_arm": ["A", "B", "C"],
                "analysis_end": ["2026-08-25", "2026-08-25", "2026-08-25"],
            }
        )
        stage028_tool._assert_full_period_coverage(complete)

        truncated = complete.copy()
        truncated.loc[truncated["experiment_arm"].eq("B"), "analysis_end"] = "2026-07-22"
        with self.assertRaisesRegex(RuntimeError, "stage028_full_period_coverage_failed"):
            stage028_tool._assert_full_period_coverage(truncated)


if __name__ == "__main__":
    unittest.main()
