"""Hand-calculated gates for the independent Stage257 reviewer; no engine run."""
import importlib.util
from pathlib import Path
import unittest

import pandas as pd

SCRIPT = Path(__file__).with_name('stage257_review_accounts.py')


class ReviewTests(unittest.TestCase):
    def module(self):
        self.assertTrue(SCRIPT.exists(), 'Stage257 independent reviewer not implemented')
        spec = importlib.util.spec_from_file_location('review257_test', SCRIPT)
        result = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(result)
        return result

    def ledger_fixture(self):
        t = pd.DataFrame([
            dict(trade_id='B.1', order_id='B.1', vt_symbol='x.X', direction='多', offset='开', volume=2., price=100., date='2020-01-02', datetime='2020-01-01 21:00:00+08:00'),
            dict(trade_id='B.2', order_id='B.2', vt_symbol='x.X', direction='空', offset='平', volume=1., price=110., date='2020-01-03', datetime='2020-01-02 21:00:00+08:00'),
        ])
        d = pd.DataFrame(dict(date=['2020-01-02', '2020-01-03'], account_equity=[150080., 150150.], net_pnl=[80., 70.], commission=[0., 0.], slippage=[20., 10.], trade_count=[1, 1]))
        p = pd.DataFrame(dict(date=d.date, vt_symbol=['x.X'] * 2, close_price=[105., 108.], pos_change=[2., -1.], end_pos=[2., 1.]))
        params = {'contract_sizes': {'x.X': 10}, 'rates': {'x.X': 0}, 'slippages': {'x.X': 1}}
        return t, d, p, params

    def test_open_partial_cycle_keeps_mtm_separate_from_closed_win_rate(self):
        got = self.module().audit_ledger(*self.ledger_fixture(), 150000.)
        self.assertEqual(got['errors'], [])
        self.assertEqual(got['closed_cycles'], 0)
        self.assertEqual(got['end_open_episode_net_mtm'], 150.)
        self.assertEqual(got['end_positions'], {'x.X': 1.})
        self.assertIsNone(got['cycle_win_rate_pct'])

    def test_ledger_rejects_one_unit_equity_drift(self):
        t, d, p, params = self.ledger_fixture()
        d.loc[1, 'account_equity'] += 1
        self.assertIn('cash_mtm_mismatch', self.module().audit_ledger(t, d, p, params, 150000.)['errors'])

    def test_weekend_end_uses_frozen_calendar_and_physical_previous_night(self):
        t, d, p, _ = self.ledger_fixture()
        got = self.module().audit_window(t, d, p, '2020-01-01', '2020-01-05', ['2019-12-31', '2020-01-02', '2020-01-03', '2020-01-06'])
        self.assertEqual(got['errors'], [])
        self.assertEqual(got['last_trading_date'], '2020-01-03')

    def test_missing_middle_trading_day_is_not_a_complete_window(self):
        t, d, p, _ = self.ledger_fixture()
        got = self.module().audit_window(t.iloc[:1], d.iloc[:1], p.iloc[:1], '2020-01-01', '2020-01-05', ['2020-01-02', '2020-01-03'])
        self.assertIn('daily_calendar_mismatch', got['errors'])

    def test_cold_start_rejects_carried_position(self):
        t, d, p, _ = self.ledger_fixture()
        p.loc[0, 'end_pos'] = 3
        got = self.module().audit_window(t, d, p, '2020-01-01', '2020-01-05', d.date.tolist())
        self.assertIn('nonflat_initial_position', got['errors'])

    def settings(self):
        a = dict(trade_start_date='2020-01-01', ai_product_pool_eligibility_path='/old.csv', ai_product_pool_strategy='old', enable_stage847_half_r_stop_retry=False, enable_stage827_intraday_c2_stop=True, enable_ai_product_pool_filter=True, enable_selection_pairwise_v2=True, risk=0.02)
        ref = {'setting': dict(a), 'actual': dict(a), 'engine_capital': 150000, 'non_strategy_fields': {'account_capital': 150000, 'c3_capital': 150000}, 'supply_demand_signal_rows': 0}
        got = {**ref, 'setting': dict(a), 'actual': dict(a)}
        for scope in ['setting', 'actual']:
            got[scope].update(trade_start_date='2022-02-07', ai_product_pool_eligibility_path='/new.csv', ai_product_pool_strategy='new')
        spec = {'start': '2022-02-07', 'pool_file': '/new.csv', 'policy_id': 'new'}
        return ref, got, spec

    def test_settings_allow_only_window_and_pool_changes(self):
        ref, got, spec = self.settings()
        self.assertEqual(self.module().audit_settings([got], ref, spec, 150000)['errors'], [])
        got['actual']['risk'] = .03
        self.assertIn('actual_unexpected_parameter_delta', self.module().audit_settings([got], ref, spec, 150000)['errors'])

    def test_private_universe_path_is_an_explicit_declared_identity_delta(self):
        ref, got, spec = self.settings()
        for scope in ['setting', 'actual']:
            ref[scope]['product_universe_csv_path'] = '/old_universe.csv'
            got[scope]['product_universe_csv_path'] = '/private/universe.csv'
        spec['_private_universe_path'] = '/private/universe.csv'
        self.assertEqual(self.module().audit_settings([got], ref, spec, 150000)['errors'], [])

    def test_fresh_state_rejects_missing_product_or_nonzero_initial_position(self):
        m = self.module()
        self.assertTrue(hasattr(m, 'audit_fresh_state'), 'fresh-state receipt gate not implemented')
        receipt = dict(fresh_engine=True, fresh_engine_and_account=True, actual_supported_symbols=['x.X', 'fu.SHFE'], actual_product_state_keys=['x.X', 'fu.SHFE'], initial_positions={}, initial_capital=150000)
        self.assertEqual(m.audit_fresh_state(receipt, {'x.X', 'fu.SHFE'}, 150000), [])
        receipt['initial_positions'] = {'x2401.X': 1}
        self.assertIn('initial_positions_not_flat', m.audit_fresh_state(receipt, {'x.X', 'fu.SHFE'}, 150000))
        receipt['actual_supported_symbols'] = ['fu.SHFE']
        self.assertIn('actual_loaded_universe_not_19', m.audit_fresh_state(receipt, {'x.X', 'fu.SHFE'}, 150000))

    def test_disabled_c2_or_boolean_like_zero_does_not_pass(self):
        ref, got, spec = self.settings()
        got['actual']['enable_stage827_intraday_c2_stop'] = False
        self.assertIn('wrong_flag:enable_stage827_intraday_c2_stop', self.module().audit_settings([got], ref, spec, 150000)['errors'])
        got['actual']['enable_stage827_intraday_c2_stop'] = True
        got['actual']['enable_stage847_half_r_stop_retry'] = 0
        self.assertIn('wrong_flag:enable_stage847_half_r_stop_retry', self.module().audit_settings([got], ref, spec, 150000)['errors'])

    def test_rank_and_eval_day_membership_are_checked_against_the_actual_pool(self):
        pool = pd.DataFrame([dict(eval_date='2019-12-31', product_vt_symbol='fu.SHFE', score_rank=19, score=0.), dict(eval_date='2022-01-28', product_vt_symbol='x.X', score_rank=1, score=.7)])
        c = pd.DataFrame([dict(date='2022-01-28', product_vt_symbol='fu.SHFE', ai_product_pool_allowed=1, ai_product_pool_signal_date='2019-12-31', ai_product_pool_rank=19, ai_product_pool_score=0., ai_product_pool_use_next_trade_date_for_entry=0)])
        self.assertEqual(self.module().audit_membership(c, pool)['mismatches'], [])
        c.loc[0, 'ai_product_pool_signal_date'] = '2022-01-28'
        self.assertEqual(len(self.module().audit_membership(c, pool)['mismatches']), 1)

    def test_date_keyed_iid_does_not_depend_on_an_earlier_call(self):
        m = self.module()
        u = list('abcdefghijklmno')
        a = m.replay_iid(u, 8, 3, '2023-06-30')
        m.replay_iid(u, 8, 3, '2022-01-28')
        self.assertEqual(a, m.replay_iid(u[::-1], 8, 3, '2023-06-30'))
        self.assertEqual(len(a), 8)

    def test_turnover_width_change_preserves_exact_retention(self):
        m = self.module()
        old = set('abcdefgh')
        new = m.replay_turnover(list('abcdefghijklmno'), 9, old, 5, 1, '2023-02-28')
        self.assertEqual(len(new), 9)
        self.assertEqual(len(new & old), 5)
        with self.assertRaisesRegex(ValueError, 'infeasible'):
            m.replay_turnover(list('abcdefghij'), 8, old, 1, 1, '2023-02-28')

    def test_alias_cannot_reuse_a_different_start_or_a_real_ai_window(self):
        m = self.module()
        self.assertTrue(hasattr(m, 'audit_aliases'), 'alias validation not implemented')
        windows = [{'window_id': 'w1', 'start': '2020-01-01', 'end': '2020-12-31', 'policy_phase': 'common_pre_ai_only'}, {'window_id': 'w2', 'start': '2021-01-01', 'end': '2021-12-31', 'policy_phase': 'common_pre_ai_only'}]
        accounts = {'w1__COMMON_PRE_AI': {'window_id': 'w1', 'kind': 'common_pre_ai', 'start': '2020-01-01', 'end': '2020-12-31'}}
        self.assertEqual(m.audit_aliases(accounts, {'w1__AI_FAIR': 'w1__COMMON_PRE_AI'}, windows), [])
        self.assertTrue(m.audit_aliases(accounts, {'w2__AI_FAIR': 'w1__COMMON_PRE_AI'}, windows))

    def test_missing_pool_member_is_rejected_even_with_correct_declared_width(self):
        m = self.module()
        self.assertTrue(hasattr(m, 'audit_pool_frame'), 'pool row validation not implemented')
        frame = pd.DataFrame([dict(strategy='p', eval_date='2022-01-28', product_vt_symbol='x.X', score_rank=1, top_n=2), dict(strategy='p', eval_date='2022-01-28', product_vt_symbol='fu.SHFE', score_rank=2, top_n=2)])
        expected = {'2022-01-28': {'x.X', 'fu.SHFE'}}
        self.assertEqual(m.audit_pool_frame(frame, expected, 'p'), [])
        self.assertTrue(m.audit_pool_frame(frame.iloc[:1], expected, 'p'))


if __name__ == '__main__':
    unittest.main()
