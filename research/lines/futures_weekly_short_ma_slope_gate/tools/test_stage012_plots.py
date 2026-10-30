"""Synthetic tests for the C-only reserve-cap comparison; no financial replay."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/stage012-plots-mpl')
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

try:
    import stage012_plots as plots
except ImportError:
    plots = None

STARTS = tuple(f'{year}-{month:02d}-01' for year in range(2015, 2027)
               for month in (1, 6) if (year, month) <= (2026, 1))
COUNTS = (2871, 2773, 2627, 2527, 2383, 2286, 2139, 2040, 1896,
          1797, 1652, 1555, 1409, 1312, 1166, 1070, 924, 826, 682, 584, 440, 343, 197)
ACTUALS = ('2015-01-05', '2015-06-01', '2016-01-04', '2016-06-01',
           '2017-01-03', '2017-06-01', '2018-01-02', '2018-06-01',
           '2019-01-02', '2019-06-03', '2020-01-02', '2020-06-01',
           '2021-01-04', '2021-06-01', '2022-01-04', '2022-06-01',
           '2023-01-03', '2023-06-01', '2024-01-02', '2024-06-03',
           '2025-01-02', '2025-06-03', '2026-01-05')
FRESH = {'2016-06-01', '2017-01-01', '2017-06-01', '2018-01-01',
         '2018-06-01', '2019-01-01', '2019-06-01', '2020-01-01', '2021-06-01'}
VARIANTS = ('C_R150', 'C_R50')


def _sharpe(equity):
    previous = np.r_[150000., equity[:-1]]
    returns = np.diff(np.r_[150000., equity]) / previous
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(252))


def synthetic_bundle():
    summaries, curves, pairs = [], [], []
    for i, (start, actual, count) in enumerate(zip(STARTS, ACTUALS, COUNTS)):
        available = pd.bdate_range(actual, '2026-10-29')
        dates = available[np.linspace(0, len(available) - 1, count).astype(int)]
        progress = np.linspace(0, 1, count)
        for variant in VARIANTS:
            small = variant == 'C_R50'
            reserve_initial = 50000. if small else 150000.
            fresh = start in FRESH
            profit = (-22000. if i % 5 == 0 else 10000. + i * 3000)
            if fresh and small:
                profit -= 4000
            raw = 150000. + profit * progress + 1800 * np.sin(progress * 15)
            pnl = np.diff(np.r_[150000., raw])
            amount = np.zeros(count)
            consumed = (50000. if small else 150000.) if fresh else (43960. if i == 0 else 10000. + i * 1000)
            amount[[count // 3, 2 * count // 3]] = consumed / 2
            deposits = amount.cumsum()
            equity = raw + deposits
            reserve = reserve_initial - deposits
            dd = (equity / np.maximum.accumulate(np.r_[150000., equity])[1:] - 1) * 100
            margin = np.full(count, 10000.)
            exhausted = reserve[-1] == 0
            exhaustion = dates[np.flatnonzero(reserve == 0)[0]].strftime('%Y-%m-%d') if exhausted else ''
            method = ('fresh_engine' if fresh else 'proven_nonbinding_reuse') if small else 'frozen_baseline'
            curves.append(pd.DataFrame(dict(
                start=start, variant=variant, date=dates.strftime('%Y-%m-%d'),
                raw_account_equity=raw, net_pnl=pnl, trading_account_equity=equity,
                reserve_balance=reserve, cumulative_transfer=deposits,
                transfer_amount=amount, account_nav=equity / 150000,
                balance_drawdown_pct=dd, total_account_equity=equity + reserve,
                reserve_initial=reserve_initial, slippage=np.full(count, 2.),
                commission=np.zeros(count), trade_count=np.ones(count, dtype=int),
                total_margin_exact=margin)))
            summaries.append(dict(
                start=start, variant=variant, arm='C', funding_mode='external_topup', method=method,
                version='reserve50k' if small else 'reserve150k', reserve_initial=reserve_initial,
                actual_start=actual, actual_end='2026-10-29', trading_days=count,
                observation_only=start == '2026-01-01', initial_trading_capital=150000.,
                account_end_equity=equity[-1], account_growth_pct=(equity[-1] / 150000 - 1) * 100,
                balance_max_dd_pct=dd.min(), balance_sharpe=_sharpe(equity),
                balance_returns_defined=True, real_trading_net_pnl=pnl.sum(),
                total_transferred=deposits[-1], off_account_reserve_end=reserve[-1],
                total_slippage=count * 2., total_commission=0., modeled_fill_count=count,
                transfer_event_days=2, transfer_event_count=3, nonpositive_trading_equity_days=0,
                reserve_exhausted=exhausted, exhaustion_date=exhaustion,
                trading_margin_peak_pct=float((margin * 1.65 / equity * 100).max()),
                trading_margin_over100_days=0))
        old, new = summaries[-2:]
        row = dict(start=start, arm='C', cohort='January' if start[5:7] == '01' else 'June',
                   observation_only=start == '2026-01-01', method50=new['method'])
        for target, field in (
            ('delta_account_end_equity', 'account_end_equity'),
            ('delta_real_trading_net_pnl', 'real_trading_net_pnl'),
            ('delta_account_growth_pp', 'account_growth_pct'),
            ('delta_balance_max_dd_pp', 'balance_max_dd_pct'),
            ('delta_balance_sharpe', 'balance_sharpe'), ('delta_deposits', 'total_transferred')):
            row[target] = new[field] - old[field]
        row.update(real_pnl_comparison=-1 if fresh else 0,
                   dd_comparison=-1 if row['delta_balance_max_dd_pp'] < 0 else 1 if row['delta_balance_max_dd_pp'] > 0 else 0,
                   sharpe_comparison=-1 if row['delta_balance_sharpe'] < 0 else 1 if row['delta_balance_sharpe'] > 0 else 0)
        pairs.append(row)
    return pd.DataFrame(summaries), pd.DataFrame(pairs), pd.concat(curves, ignore_index=True)


class Reserve50kPlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = synthetic_bundle()

    def setUp(self):
        self.assertIsNotNone(plots, 'Stage012 renderer is missing')

    def test_complete_scope_allows_proven_equal_trading_paths_with_different_reserves(self):
        s, p, d = self.bundle
        si, pi, curves = plots.validate_inputs(s, p, d)
        self.assertEqual((len(si), len(pi), len(d), len(curves)), (46, 23, 70998, 46))
        old = curves[('2015-01-01', 'C_R150')]
        new = curves[('2015-01-01', 'C_R50')]
        np.testing.assert_array_equal(old.account_nav, new.account_nav)
        np.testing.assert_allclose(old.reserve_balance - new.reserve_balance, 100000.)
        self.assertEqual(float(new.cumulative_transfer.iloc[-1]), 43960.)
        self.assertEqual((old.account_nav.iloc[0], new.account_nav.iloc[0]), (1., 1.))
        self.assertEqual(int(s.method.eq('proven_nonbinding_reuse').sum()), 14)
        self.assertEqual(int(s.method.eq('fresh_engine').sum()), 9)

    def test_validation_rejects_incomplete_scope_before_figure_creation(self):
        s, p, d = self.bundle
        with patch.object(plots, '_figure', side_effect=AssertionError('allocated early')):
            for bundle in ((s.iloc[:-1], p, d), (s, p.iloc[:-1], d), (s, p, d.iloc[:-1]),
                           (s, p, pd.concat([d.iloc[:-1], d.iloc[[0]]]))):
                with self.assertRaises(ValueError):
                    plots.render_five(*bundle)
        bad = s.copy()
        bad.loc[0, 'actual_end'] = '2026-10-28'
        with self.assertRaises(ValueError):
            plots.validate_inputs(bad, p, d)

    def test_rejects_wrong_capital_version_method_and_original_funding_identity(self):
        s, p, d = self.bundle
        for field, value in (('initial_trading_capital', 200000), ('reserve_initial', 50000),
                             ('version', 'uniform_risk'), ('method', 'fresh_engine'),
                             ('funding_mode', 'original'), ('arm', 'A')):
            bad = s.copy()
            bad.loc[0, field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(bad, p, d)
        bad = s.copy()
        bad.loc[s.variant.eq('C_R50'), 'method'] = 'fresh_engine'
        with self.assertRaises(ValueError):
            plots.validate_inputs(bad, p, d)

    def test_cashflow_and_reserve_cannot_be_strategy_pnl_or_account_nav(self):
        s, p, d = self.bundle
        for field, values in (('net_pnl', d.net_pnl + d.transfer_amount),
                              ('account_nav', d.total_account_equity / 150000),
                              ('account_nav', d.raw_account_equity / 150000),
                              ('account_nav', d.trading_account_equity / 200000),
                              ('total_account_equity', d.trading_account_equity + 150000)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(s, p, d.assign(**{field: values}))
        with self.assertRaises(ValueError):
            plots.validate_inputs(s, p, d.assign(reserve_initial=150000))

    def test_summary_and_paired_metrics_must_reconcile_to_daily(self):
        s, p, d = self.bundle
        for field in ('account_end_equity', 'real_trading_net_pnl', 'account_growth_pct',
                      'balance_max_dd_pct', 'balance_sharpe', 'total_transferred',
                      'total_slippage', 'trading_margin_peak_pct', 'trading_margin_over100_days'):
            bad = s.copy()
            bad.loc[0, field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(bad, p, d)
        for field in [name for name in p if name.startswith('delta_')] + ['real_pnl_comparison', 'dd_comparison', 'sharpe_comparison']:
            bad = p.copy()
            bad.loc[0, field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(s, bad, d)
        bad = p.copy()
        bad.loc[0, 'method50'] = 'fresh_engine'
        with self.assertRaises(ValueError):
            plots.validate_inputs(s, bad, d)

    def test_reuse_identity_must_match_every_daily_trading_field_not_just_end_equity(self):
        s, p, d = self.bundle
        # Equal total cost but a different daily cost path cannot be a proven reuse.
        bad = d.copy()
        indices = bad.index[(bad.start == '2015-01-01') & (bad.variant == 'C_R50')][100:102]
        bad.loc[indices, 'slippage'] += [1., -1.]
        with self.assertRaisesRegex(ValueError, 'proven_reuse_daily'):
            plots.validate_inputs(s, p, bad)

    def test_balance_sharpe_requires_positive_previous_account_equity(self):
        self.assertEqual(plots.balance_sharpe([150000., -1000., 2000.]), (0., False))
        self.assertEqual(plots.balance_sharpe([150000., 150000.]), (0., True))

    def test_five_figures_preserve_all_starts_pending_scope_and_overlap_annotation(self):
        s, p, d = self.bundle
        figures = plots.render_five(s, p, d)
        reviewed = plots.render_five(s, p, d, reviewed=True)
        self.assertEqual(tuple(figures), plots.FIGURE_NAMES)
        full_ax = figures[plots.FIGURE_NAMES[0]].axes[0]
        for variant, line in zip(VARIANTS, full_ax.lines[:2]):
            expected = d.loc[(d.start == '2015-01-01') & (d.variant == variant), 'account_nav']
            np.testing.assert_array_equal(line.get_ydata(), expected)
        self.assertTrue(any('overlap' in text.get_text().lower() for text in full_ax.texts))
        self.assertEqual([len([a for a in figures[name].axes if a.get_visible()]) for name in plots.FIGURE_NAMES[1:3]], [12, 11])
        for name, fig in figures.items():
            other = reviewed[name]
            text = '\n'.join(t.get_text() for t in fig.texts)
            self.assertIn('PENDING', text)
            self.assertIn('NO_PROMOTION', text)
            self.assertIn('REVIEWED', other._suptitle.get_text())
            self.assertIn('deposits INCLUDED', text)
            self.assertIn('14 proven', text)
            self.assertIn('9 fresh', text)
            self.assertIn('1.8%', text)
            self.assertIn('6%', text)
            self.assertIn('2.5%', text)
            self.assertIn('bottom 20%', text)
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

    def test_heatmap_uses_r50_minus_r150_real_pnl_account_dd_and_deposits(self):
        s, p, d = self.bundle
        figures = plots.render_five(s, p, d)
        axes = [ax for ax in figures[plots.FIGURE_NAMES[3]].axes if ax.images]
        for ax, field in zip(axes, ('delta_real_trading_net_pnl', 'delta_balance_max_dd_pp', 'delta_deposits')):
            expected = p.set_index('start').loc[list(STARTS), field].to_numpy()
            np.testing.assert_array_equal(ax.images[0].get_array().ravel(), expected)
        for fig in figures.values():
            fig.clear()

    def test_risk_overview_counts_actual_losses_and_margin_stress_not_deposit_growth(self):
        s, p, d = self.bundle
        figures = plots.render_five(s, p, d)
        ax = figures[plots.FIGURE_NAMES[4]].axes[0]
        expected = []
        for variant in VARIANTS:
            q = s.loc[s.variant.eq(variant) & ~s.observation_only]
            expected += [int(q.real_trading_net_pnl.lt(0).sum()),
                         int(q.nonpositive_trading_equity_days.gt(0).sum()),
                         int(q.trading_margin_over100_days.gt(0).sum())]
        self.assertEqual([int(bar.get_height()) for bar in ax.patches], expected)
        for fig in figures.values():
            fig.clear()


if __name__ == '__main__':
    unittest.main()
