"""Regression checks: CZCE decade aliases must not lend warmup or balances."""
from datetime import datetime
from types import SimpleNamespace
import unittest

import pandas as pd

import stage263_build_expanded_source as source


class EpochTests(unittest.TestCase):
    def test_new_epoch_does_not_borrow_old_warmup(self):
        dates = pd.to_datetime(['2015-01-05', '2015-03-19', '2024-05-20', '2024-05-21'])
        self.assertEqual(str(source.epoch_start(dates, '2024-05-21').date()), '2024-05-20')
        self.assertEqual(str(source.epoch_start(dates, '2015-03-19').date()), '2015-01-05')

    def test_same_epoch_history_is_unchanged_and_future_removed(self):
        raw = pd.DataFrame({'date': pd.to_datetime(['2015-01-05', '2024-05-20', '2024-05-21', '2024-05-22']), 'close': [10, 20, 21, 22]})
        actual = source.filter_epoch_history(raw, '2024-05-21', '2024-05-20')
        self.assertEqual(actual.close.tolist(), [20, 21])

    def strategy(self):
        # Minimal engine boundary; numerical AM replacement uses its real constructor protocol.
        class AM:
            def __init__(self, size): self.size, self.count = size, 0
        engine = SimpleNamespace(active_limit_orders={}, bars={})
        obj = SimpleNamespace(ams={'CF505.CZCE': AM(140)}, pos_data={}, target_data={},
            equity_start_positions={'CF505.CZCE': 0}, last_close_prices={'CF505.CZCE': 10},
            pending_close_lots={}, pending_close_reasons={}, pending_entry_diagnostics={},
            execution_price_overrides={}, states={}, strategy_engine=engine)
        return obj

    def test_flat_epoch_reset_replaces_am_and_forgets_only_old_mark(self):
        s = self.strategy(); old = s.ams['CF505.CZCE']
        old.count = 139
        bar = SimpleNamespace(vt_symbol='CF505.CZCE', datetime=datetime(2024, 5, 20))
        source.reset_contract_epoch(s, 'CF505.CZCE', bar)
        self.assertIsNot(s.ams['CF505.CZCE'], old)
        self.assertEqual(s.ams['CF505.CZCE'].count, 0)
        self.assertEqual(s.ams['CF505.CZCE'].size, 140)
        self.assertNotIn('CF505.CZCE', s.last_close_prices)
        self.assertNotIn('CF505.CZCE', s.equity_start_positions)

    def test_live_old_position_or_order_stops_instead_of_erasing_balance(self):
        for field in ['pos_data', 'target_data', 'equity_start_positions']:
            s=self.strategy(); getattr(s, field)['CF505.CZCE']=1
            with self.assertRaisesRegex(RuntimeError, 'epoch_not_quiescent'):
                source.reset_contract_epoch(s,'CF505.CZCE',SimpleNamespace())
        s=self.strategy()
        s.strategy_engine.active_limit_orders={'x':SimpleNamespace(vt_symbol='CF505.CZCE')}
        with self.assertRaisesRegex(RuntimeError, 'epoch_not_quiescent'):
            source.reset_contract_epoch(s,'CF505.CZCE',SimpleNamespace())

    def test_pending_settlement_is_not_silently_erased(self):
        for field in ['pending_close_lots', 'pending_close_reasons']:
            s = self.strategy(); getattr(s, field)['CF505.CZCE'] = ['unsettled']
            with self.assertRaisesRegex(RuntimeError, 'epoch_not_quiescent'):
                source.reset_contract_epoch(s,'CF505.CZCE',SimpleNamespace())

    def test_epoch_boundary_is_five_years_and_ordinary_gaps_do_not_reset(self):
        self.assertEqual(str(source.epoch_start(pd.to_datetime(['2015-01-05','2020-01-04']), '2020-01-04').date()), '2015-01-05')
        self.assertEqual(str(source.epoch_start(pd.to_datetime(['2015-01-05','2020-01-05']), '2020-01-05').date()), '2020-01-05')


if __name__ == '__main__': unittest.main()
