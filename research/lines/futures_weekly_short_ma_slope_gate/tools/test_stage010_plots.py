"""Synthetic-only tests for Stage010's cashflow-inclusive account display.

The manufactured calendars retain the frozen start/count/end contract but are
not exchange calendars or evidence about strategy performance.
"""
import os
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/stage010-plots-mpl')
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

try:
    import stage010_plots as plots
except ImportError:
    plots = None

STARTS = tuple(f'{year}-{month:02d}-01' for year in range(2015, 2027)
               for month in (1, 6) if (year, month) <= (2026, 1))
COUNTS = (2871, 2773, 2627, 2527, 2383, 2286, 2139, 2040, 1896,
          1797, 1652, 1555, 1409, 1312, 1166, 1070, 924, 826, 682,
          584, 440, 343, 197)
ACTUALS = ('2015-01-05', '2015-06-01', '2016-01-04', '2016-06-01',
           '2017-01-03', '2017-06-01', '2018-01-02', '2018-06-01',
           '2019-01-02', '2019-06-03', '2020-01-02', '2020-06-01',
           '2021-01-04', '2021-06-01', '2022-01-04', '2022-06-01',
           '2023-01-03', '2023-06-01', '2024-01-02', '2024-06-03',
           '2025-01-02', '2025-06-03', '2026-01-05')
VARIANTS = ('A_R', 'A_idle', 'C_R', 'C_idle')


def synthetic_bundle():
    summaries, curves, pairs = [], [], []
    for i, (start, actual, count) in enumerate(zip(STARTS, ACTUALS, COUNTS)):
        available = pd.bdate_range(actual, '2026-10-29')
        dates = available[np.linspace(0, len(available) - 1, count).astype(int)]
        progress = np.linspace(0, 1, count)
        for variant in VARIANTS:
            arm = variant[0]
            funded = variant.endswith('_R')
            profit = (-22000 - i * 1000 if i % 5 == 0 else 10000 + i * 3000)
            profit += (4000 if arm == 'C' else 0) + (3000 if funded else 0)
            raw = 150000 + profit * progress + 1800 * np.sin(progress * 15)
            pnl = np.diff(np.r_[150000., raw])
            amount = np.zeros(count)
            if funded:
                amount[[count // 3, 2 * count // 3]] = min(140000, 30000 + i * 5000) / 2
            deposits = np.cumsum(amount)
            equity = raw + deposits
            reserve = 150000 - deposits
            dd = (equity / np.maximum.accumulate(np.r_[150000., equity])[1:] - 1) * 100
            returns = np.diff(np.r_[150000., equity]) / np.r_[150000., equity[:-1]]
            sharpe = returns.mean() / returns.std(ddof=1) * np.sqrt(252)
            slippage = np.full(count, 2.)
            commission = np.zeros(count)
            trades = np.ones(count, dtype=int)
            curves.append(pd.DataFrame(dict(
                start=start, variant=variant, date=dates.strftime('%Y-%m-%d'),
                raw_account_equity=raw, net_pnl=pnl, trading_account_equity=equity,
                reserve_balance=reserve, cumulative_transfer=deposits,
                transfer_amount=amount, account_nav=equity / 150000,
                balance_drawdown_pct=dd, total_account_equity=equity + reserve,
                slippage=slippage, commission=commission, trade_count=trades)))
            summaries.append(dict(
                start=start, variant=variant, arm=arm,
                funding_mode='external_topup' if funded else 'original',
                actual_start=actual, actual_end='2026-10-29', trading_days=count,
                observation_only=start == '2026-01-01', initial_trading_capital=150000.,
                account_end_equity=equity[-1], account_growth_pct=(equity[-1] / 150000 - 1) * 100,
                balance_max_dd_pct=dd.min(), balance_sharpe=sharpe,
                balance_returns_defined=True, real_trading_net_pnl=pnl.sum(),
                total_transferred=deposits[-1], off_account_reserve_end=reserve[-1],
                total_slippage=slippage.sum(), total_commission=0.,
                modeled_fill_count=trades.sum(), transfer_event_days=int((amount > 0).sum()),
                nonpositive_trading_equity_days=0))
        for arm in ('A', 'C'):
            original = next(r for r in summaries if r['start'] == start and r['variant'] == arm + '_idle')
            funded = next(r for r in summaries if r['start'] == start and r['variant'] == arm + '_R')
            pairs.append(dict(
                start=start, arm=arm, cohort='January' if start[5:7] == '01' else 'June',
                observation_only=start == '2026-01-01',
                delta_account_growth_pp=funded['account_growth_pct'] - original['account_growth_pct'],
                delta_balance_max_dd_pp=funded['balance_max_dd_pct'] - original['balance_max_dd_pct'],
                delta_balance_sharpe=funded['balance_sharpe'] - original['balance_sharpe'],
                delta_real_trading_net_pnl=funded['real_trading_net_pnl'] - original['real_trading_net_pnl'],
                delta_account_end_equity=funded['account_end_equity'] - original['account_end_equity'],
                external_deposits=funded['total_transferred']))
    return pd.DataFrame(summaries), pd.DataFrame(pairs), pd.concat(curves, ignore_index=True)


class AccountPlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = synthetic_bundle()

    def setUp(self):
        self.assertIsNotNone(plots, 'Stage010 account renderer is missing')

    def test_valid_scope_and_account_cashflow_bridges(self):
        s, p, d = self.bundle
        si, pi, curves = plots.validate_inputs(s, p, d)
        self.assertEqual((len(si), len(pi), len(d)), (92, 46, 141996))
        original = curves[('2015-01-01', 'A_idle')]
        funded = curves[('2015-01-01', 'A_R')]
        np.testing.assert_allclose(original.account_nav, original.raw_account_equity / 150000)
        np.testing.assert_allclose(funded.account_nav, (150000 + funded.net_pnl.cumsum() + funded.cumulative_transfer) / 150000)
        self.assertTrue((funded.account_nav[funded.transfer_amount.gt(0)] > funded.raw_account_equity[funded.transfer_amount.gt(0)] / 150000).all())
        self.assertEqual(float(original.account_nav.iloc[0]), 1.)
        self.assertEqual(float(funded.account_nav.iloc[0]), 1.)

    def test_rejects_300k_or_off_account_reserve_in_nav(self):
        s, p, d = self.bundle
        for nav in (d.trading_account_equity / 300000, d.total_account_equity / 150000,
                    d.raw_account_equity / 150000):
            bad = d.assign(account_nav=nav)
            with self.assertRaisesRegex(ValueError, 'account_NAV150k'):
                plots.validate_inputs(s, p, bad)

    def test_rejects_deposit_removed_from_equity_or_counted_as_pnl(self):
        s, p, d = self.bundle
        bad = d.assign(trading_account_equity=d.raw_account_equity)
        with self.assertRaises(ValueError):
            plots.validate_inputs(s, p, bad)
        bad = d.assign(net_pnl=d.net_pnl + d.transfer_amount)
        with self.assertRaisesRegex(ValueError, 'raw_PnL_bridge'):
            plots.validate_inputs(s, p, bad)

    def test_rejects_false_daily_transfers_or_costs(self):
        s, p, d = self.bundle
        for field in ('transfer_amount', 'slippage', 'commission', 'trade_count'):
            bad = d.copy()
            bad.loc[100, field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(s, p, bad)

    def test_rejects_bad_summary_metric_and_legacy_pair_gates(self):
        s, p, d = self.bundle
        for field in ('initial_trading_capital', 'real_trading_net_pnl', 'account_growth_pct',
                      'balance_sharpe', 'account_end_equity', 'total_transferred'):
            bad = s.copy()
            bad.loc[0, field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(bad, p, d)
        with self.assertRaises(ValueError):
            plots.validate_inputs(s, p.assign(three_gate_pass=True), d)

    def test_paired_deltas_and_observation_flags_must_match(self):
        s, p, d = self.bundle
        for field in ('delta_account_growth_pp', 'delta_balance_max_dd_pp',
                      'delta_balance_sharpe', 'delta_real_trading_net_pnl',
                      'delta_account_end_equity', 'external_deposits'):
            bad = p.copy()
            bad.loc[0, field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(s, bad, d)
        for bad in (p.iloc[:-1], p.assign(observation_only=False), p.assign(cohort='June')):
            with self.assertRaises(ValueError):
                plots.validate_inputs(s, bad, d)

    def test_complete_start_end_counts_and_calendar_agreement_required(self):
        s, p, d = self.bundle
        for bad in (d.iloc[:-1], pd.concat([d.iloc[:-1], d.iloc[[0]]])):
            with self.assertRaises(ValueError):
                plots.validate_inputs(s, p, bad)
        for field, value in (('actual_start', '2015-01-06'), ('actual_end', '2026-10-28'),
                             ('trading_days', 2870), ('funding_mode', 'original')):
            bad = s.copy()
            bad.loc[0, field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(bad, p, d)
        bad = d.copy()
        bad.loc[100, 'date'] = '2015-01-06'
        with self.assertRaises(ValueError):
            plots.validate_inputs(s, p, bad)

    def test_invalid_inputs_are_rejected_before_figure_allocation(self):
        s, p, d = self.bundle
        with patch.object(plots, '_figure', side_effect=AssertionError('allocated too soon')):
            with self.assertRaises(ValueError):
                plots.render_five(s.iloc[:-1], p, d)

    def test_balance_sharpe_defensive_boundary(self):
        value, defined = plots.balance_sharpe(np.array([150000., -1000., 2000.]))
        self.assertEqual(value, 0.)
        self.assertFalse(defined)
        value, defined = plots.balance_sharpe(np.array([150000., 150000., 150000.]))
        self.assertEqual(value, 0.)
        self.assertTrue(defined)

    def test_five_figures_show_only_account_nav_and_review_changes_status_only(self):
        s, p, d = self.bundle
        pending = plots.render_five(s, p, d)
        reviewed = plots.render_five(s, p, d, reviewed=True)
        self.assertEqual(tuple(pending), plots.FIGURE_NAMES)
        self.assertEqual(len(pending), 5)
        nav_ax = pending[plots.FIGURE_NAMES[0]].axes[0]
        for variant, line in zip(VARIANTS, nav_ax.lines[:4]):
            expected = d.loc[(d.start == '2015-01-01') & (d.variant == variant), 'account_nav']
            np.testing.assert_array_equal(line.get_ydata(), expected)
        for name, fig in pending.items():
            other = reviewed[name]
            self.assertIn('PENDING', fig._suptitle.get_text())
            self.assertIn('REVIEWED', other._suptitle.get_text())
            self.assertIn('NO_PROMOTION', fig._suptitle.get_text())
            footer = '\n'.join(t.get_text() for t in fig.texts)
            self.assertIn('External reserve excluded; deposits INCLUDED in balance NAV', footer)
            self.assertIn('not flow-adjusted strategy performance', footer)
            self.assertEqual(len(fig.axes), len(other.axes))
            for a, b in zip(fig.axes, other.axes):
                self.assertEqual(a.get_xlim(), b.get_xlim())
                self.assertEqual(a.get_ylim(), b.get_ylim())
                for x, y in zip(a.lines, b.lines):
                    np.testing.assert_array_equal(x.get_ydata(), y.get_ydata())
                for x, y in zip(a.images, b.images):
                    np.testing.assert_array_equal(x.get_array(), y.get_array())
            fig.clear()
            other.clear()

    def test_overview_loss_counts_use_real_trading_pnl_not_account_growth(self):
        s, p, d = self.bundle
        figures = plots.render_five(s, p, d)
        ax = figures[plots.FIGURE_NAMES[4]].axes[0]
        expected = [int(((s.variant == variant) & ~s.observation_only &
                         (s.real_trading_net_pnl < 0) &
                         (s.start.str[5:7] == month)).sum())
                    for variant in VARIANTS for month in ('01', '06')]
        self.assertEqual([int(bar.get_height()) for bar in ax.patches], expected)
        for fig in figures.values():
            fig.clear()


if __name__ == '__main__':
    unittest.main()
