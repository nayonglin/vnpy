"""Two causal input contracts; no account, provider or market-data build."""
import unittest

from stage027_build_ordered_features import Eligibility, load_native_identities


class InputContracts(unittest.TestCase):
    def test_native_identity_is_independent_of_economic_columns(self):
        row = dict(signal_date='2020-01-08', product_vt_symbol='rb.SHFE',
                   vt_symbol='rb2005.SHFE', signal='long_case3',
                   execution_trade_date='2020-01-09', net_pnl='untrusted_outcome')
        first = load_native_identities([row])
        row['net_pnl'] = 'totally_different'
        self.assertEqual(first, load_native_identities([row]))
        self.assertEqual(set(next(iter(first.values()))),
                         {'signal_date', 'product_vt_symbol', 'vt_symbol',
                          'signal', 'execution_trade_date'})
        with self.assertRaises(ValueError):
            load_native_identities([row, row])

    def test_ai_snapshot_uses_strict_prior_eval_date_and_has_no_fu_override(self):
        rows = [dict(strategy='fixed', eval_date='2020-01-31',
                     product_vt_symbol='rb.SHFE', score_rank='1', top_n='1'),
                dict(strategy='fixed', eval_date='2020-02-28',
                     product_vt_symbol='cu.SHFE', score_rank='1', top_n='1')]
        pool = Eligibility(rows, 'fixed')
        self.assertTrue(pool.allowed('anything.EX', '2020-01-30'))
        self.assertTrue(pool.allowed('anything.EX', '2020-01-31'))
        self.assertTrue(pool.allowed('rb.SHFE', '2020-02-28'))
        self.assertFalse(pool.allowed('cu.SHFE', '2020-02-28'))
        self.assertTrue(pool.allowed('cu.SHFE', '2020-03-02'))
        self.assertFalse(pool.allowed('fu.SHFE', '2020-03-02'))


if __name__ == '__main__':
    unittest.main()
