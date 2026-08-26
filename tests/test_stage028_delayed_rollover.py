from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import qmt_roll_candidate_stage027_target_contract_history_config as stage027_cfg
import qmt_roll_candidate_stage028_delayed_rollover_config as stage028_cfg
from qmt_roll_portfolio_strategy import ProductState, QmtRollPortfolioStrategy


class Stage028DelayedRolloverTest(unittest.TestCase):
    def strategy(self, delay: int = 5) -> QmtRollPortfolioStrategy:
        strategy = QmtRollPortfolioStrategy.__new__(QmtRollPortfolioStrategy)
        strategy.rollover_delay_trading_days = delay
        strategy.rollover_delay_diagnostics = []
        return strategy

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


if __name__ == "__main__":
    unittest.main()
