"""Synthetic scope/accounting tests; manufactured dates are not exchange evidence."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/stage011-plots-mpl')
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

try:
    import stage011_plots as plots
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
VARIANTS = ('A_old', 'A_new', 'C_old', 'C_new')


def _sharpe(values, initial):
    previous = np.r_[initial, values[:-1]]
    returns = np.diff(np.r_[initial, values]) / previous
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(252))


def synthetic_bundle(new_profit_delta=-5000.):
    summaries, curves, pairs = [], [], []
    for i, (start, actual, count) in enumerate(zip(STARTS, ACTUALS, COUNTS)):
        available = pd.bdate_range(actual, '2026-10-29')
        dates = available[np.linspace(0, len(available) - 1, count).astype(int)]
        progress = np.linspace(0, 1, count)
        for variant in VARIANTS:
            new = variant.endswith('_new')
            profit = (-22000 - i * 1000 if i % 5 == 0 else 10000 + i * 3000)
            profit += (4000 if variant[0] == 'C' else 0) + (new_profit_delta if new else 0)
            raw = 150000 + profit * progress + 1800 * np.sin(progress * 15)
            pnl = np.diff(np.r_[150000., raw])
            amount = np.zeros(count)
            consumed = (150000 if i % 4 == 0 else 120000) if not new else 80000
            amount[[count // 3, 2 * count // 3]] = consumed / 2
            deposits = amount.cumsum()
            equity = raw + deposits
            reserve = 150000 - deposits
            wealth = equity + reserve
            dd = (equity / np.maximum.accumulate(np.r_[150000., equity])[1:] - 1) * 100
            wdd = (wealth / np.maximum.accumulate(np.r_[300000., wealth])[1:] - 1) * 100
            margin = np.full(count, 10000.)
            exhausted = reserve[-1] == 0
            exhaustion = dates[np.flatnonzero(reserve == 0)[0]].strftime('%Y-%m-%d') if exhausted else ''
            curves.append(pd.DataFrame(dict(
                start=start, variant=variant, date=dates.strftime('%Y-%m-%d'),
                raw_account_equity=raw, net_pnl=pnl, trading_account_equity=equity,
                reserve_balance=reserve, cumulative_transfer=deposits,
                transfer_amount=amount, account_nav=equity / 150000,
                balance_drawdown_pct=dd, total_account_equity=wealth,
                wealth_nav=wealth / 300000, wealth_drawdown_pct=wdd,
                slippage=np.full(count, 2.), commission=np.zeros(count),
                trade_count=np.ones(count, dtype=int), total_margin_exact=margin)))
            summaries.append(dict(
                start=start, variant=variant, arm=variant[0], funding_mode='external_topup',
                version='uniform_risk' if new else 'prior_risk',
                actual_start=actual, actual_end='2026-10-29', trading_days=count,
                observation_only=start == '2026-01-01', initial_trading_capital=150000.,
                account_end_equity=equity[-1], account_growth_pct=(equity[-1] / 150000 - 1) * 100,
                balance_max_dd_pct=dd.min(), balance_sharpe=_sharpe(equity, 150000.),
                balance_returns_defined=True, wealth_returns_defined=True, nonpositive_total_equity_days=0, real_trading_net_pnl=pnl.sum(),
                total_transferred=deposits[-1], off_account_reserve_end=reserve[-1],
                total_slippage=count * 2., total_commission=0., modeled_fill_count=count,
                transfer_event_days=2, transfer_event_count=3,
                nonpositive_trading_equity_days=0, wealth_end_equity=wealth[-1],
                wealth_return_pct=(wealth[-1] / 300000 - 1) * 100,
                wealth_max_dd_pct=wdd.min(), wealth_sharpe=_sharpe(wealth, 300000.),
                reserve_exhausted=exhausted, exhaustion_date=exhaustion,
                trading_margin_peak_pct=float((margin * 1.65 / equity * 100).max()),
                trading_margin_over100_days=0))
        for arm in ('A', 'C'):
            old = next(r for r in summaries if r['start'] == start and r['variant'] == arm + '_old')
            new = next(r for r in summaries if r['start'] == start and r['variant'] == arm + '_new')
            row = dict(start=start, arm=arm, cohort='January' if start[5:7] == '01' else 'June',
                       observation_only=start == '2026-01-01')
            for target, field in (
                ('delta_account_growth_pp', 'account_growth_pct'),
                ('delta_balance_max_dd_pp', 'balance_max_dd_pct'),
                ('delta_balance_sharpe', 'balance_sharpe'),
                ('delta_real_trading_net_pnl', 'real_trading_net_pnl'),
                ('delta_account_end_equity', 'account_end_equity'),
                ('delta_deposits', 'total_transferred'),
                ('delta_wealth_return_pp', 'wealth_return_pct'),
                ('delta_wealth_max_dd_pp', 'wealth_max_dd_pct'),
                ('delta_wealth_sharpe', 'wealth_sharpe')):
                row[target] = new[field] - old[field]
            row.update(real_pnl_gate=row['delta_real_trading_net_pnl'] > 0,
                       wealth_dd_gate=row['delta_wealth_max_dd_pp'] >= 0,
                       wealth_sharpe_gate=row['delta_wealth_sharpe'] >= 0)
            row['three_gate_pass'] = all(row[field] for field in ('real_pnl_gate', 'wealth_dd_gate', 'wealth_sharpe_gate'))
            pairs.append(row)
    return pd.DataFrame(summaries), pd.DataFrame(pairs), pd.concat(curves, ignore_index=True)


class UniformRiskPlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = synthetic_bundle()

    def setUp(self):
        self.assertIsNotNone(plots, 'Stage011 renderer is missing')

    def test_both_versions_include_deposits_and_keep_wealth_separate(self):
        s, p, d = self.bundle
        si, pi, curves = plots.validate_inputs(s, p, d)
        self.assertEqual((len(si), len(pi), len(d)), (92, 46, 141996))
        for variant in VARIANTS:
            frame = curves[('2015-01-01', variant)]
            self.assertEqual(frame.account_nav.iloc[0], 1.)
            self.assertGreater(frame.cumulative_transfer.iloc[-1], 0)
            np.testing.assert_allclose(frame.trading_account_equity, 150000 + frame.net_pnl.cumsum() + frame.cumulative_transfer)
            np.testing.assert_allclose(frame.total_account_equity, 300000 + frame.net_pnl.cumsum())

    def test_rejects_stage010_idle_identity_or_forces_old_deposits_to_zero(self):
        s, p, d = self.bundle
        for field, value in (('funding_mode', 'original'), ('version', 'uniform_risk'), ('variant', 'A_idle')):
            bad = s.copy()
            bad.loc[0, field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(bad, p, d)

    def test_cashflow_cannot_be_pnl_or_part_of_untransferred_nav(self):
        s, p, d = self.bundle
        for field, values in (
            ('net_pnl', d.net_pnl + d.transfer_amount),
            ('account_nav', d.total_account_equity / 150000),
            ('account_nav', d.trading_account_equity / 300000),
            ('account_nav', d.raw_account_equity / 150000),
            ('wealth_nav', d.trading_account_equity / 300000)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(s, p, d.assign(**{field: values}))

    def test_rejects_missing_or_fabricated_scope_before_any_figure(self):
        s, p, d = self.bundle
        with patch.object(plots, '_figure', side_effect=AssertionError('figure allocated before validation')):
            for frames in ((s.iloc[:-1], p, d), (s, p.iloc[:-1], d), (s, p, d.iloc[:-1]),
                           (s, p, pd.concat([d.iloc[:-1], d.iloc[[0]]]))):
                with self.assertRaises(ValueError):
                    plots.render_five(*frames)
        bad = s.copy()
        bad.loc[0, 'trading_days'] -= 1
        with self.assertRaises(ValueError):
            plots.validate_inputs(bad, p, d)
        bad = d.copy()
        bad.loc[100, 'date'] = '2015-01-06'
        with self.assertRaises(ValueError):
            plots.validate_inputs(s, p, bad)

    def test_every_pair_delta_and_gate_reconciles_to_its_own_arm(self):
        s, p, d = self.bundle
        fields = [field for field in p if field.startswith('delta_')]
        for field in fields:
            bad = p.copy()
            bad.loc[0, field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(s, bad, d)
        for field in ('real_pnl_gate', 'wealth_dd_gate', 'wealth_sharpe_gate', 'three_gate_pass', 'observation_only'):
            bad = p.copy()
            bad.loc[0, field] = not bool(bad.loc[0, field])
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(s, bad, d)

    def test_research_gates_treat_source_tolerance_as_a_tie_not_an_improvement(self):
        s, p, d = synthetic_bundle(new_profit_delta=1e-8)
        p = p.assign(real_pnl_gate=False, wealth_dd_gate=True,
                     wealth_sharpe_gate=True, three_gate_pass=False)
        si, pi, curves = plots.validate_inputs(s, p, d)
        self.assertEqual(int(pi.real_pnl_gate.sum()), 0)
        self.assertEqual(int(pi.wealth_dd_gate.sum()), 46)

    def test_summary_wealth_exhaustion_and_margin_metrics_are_checked(self):
        s, p, d = self.bundle
        for field in ('real_trading_net_pnl', 'wealth_return_pct', 'wealth_end_equity',
                      'wealth_max_dd_pct', 'wealth_sharpe', 'trading_margin_peak_pct',
                      'trading_margin_over100_days', 'account_growth_pct', 'total_transferred',
                      'transfer_event_days', 'balance_sharpe', 'total_slippage'):
            bad = s.copy()
            bad.loc[0, field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(bad, p, d)
        for field, value in (('reserve_exhausted', False), ('exhaustion_date', '2015-01-06'),
                             ('transfer_event_count', 1), ('observation_only', True)):
            bad = s.copy()
            bad.loc[0, field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(bad, p, d)

    def test_invalid_daily_costs_margin_and_cash_bridges_are_rejected(self):
        s, p, d = self.bundle
        for field in ('transfer_amount', 'slippage', 'commission', 'trade_count',
                      'raw_account_equity', 'reserve_balance', 'total_account_equity',
                      'balance_drawdown_pct', 'wealth_drawdown_pct'):
            bad = d.copy()
            bad.loc[100, field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                plots.validate_inputs(s, p, bad)
        with self.assertRaises(ValueError):
            plots.validate_inputs(s, p, d.assign(total_margin_exact=-1))

    def test_account_and_wealth_sharpe_keep_distinct_nonpositive_denominator_rules(self):
        self.assertEqual(plots.balance_sharpe([150000., -1000., 2000.]), (0., False))
        value, defined = plots.wealth_sharpe([300000., -1000., 2000.])
        self.assertTrue(defined)
        self.assertTrue(np.isfinite(value))
        self.assertEqual(plots.wealth_sharpe([300000., 0., 2000.]), (0., False))
        self.assertEqual(plots.balance_sharpe([150000., 150000.]), (0., True))

    def test_all_figures_keep_old_uniform_labels_and_review_is_status_only(self):
        s, p, d = self.bundle
        pending = plots.render_five(s, p, d)
        reviewed = plots.render_five(s, p, d, reviewed=True)
        self.assertEqual(tuple(pending), plots.FIGURE_NAMES)
        self.assertEqual(len(pending), 5)
        for variant, line in zip(VARIANTS, pending[plots.FIGURE_NAMES[0]].axes[0].lines[:4]):
            np.testing.assert_array_equal(line.get_ydata(), d.loc[(d.start == '2015-01-01') & (d.variant == variant), 'account_nav'])
            self.assertEqual(line.get_color(), plots.COLORS[variant])
        january = [ax for ax in pending[plots.FIGURE_NAMES[1]].axes if ax.get_visible()]
        june = [ax for ax in pending[plots.FIGURE_NAMES[2]].axes if ax.get_visible()]
        self.assertEqual((len(january), len(june)), (12, 11))
        self.assertIn('OBS', january[-1].get_title())
        legend = ' '.join(t.get_text() for t in pending[plots.FIGURE_NAMES[0]].axes[0].get_legend().texts)
        self.assertIn('prior', legend.lower())
        self.assertIn('uniform', legend.lower())
        for name, fig in pending.items():
            other = reviewed[name]
            text = '\n'.join(t.get_text() for t in fig.texts)
            self.assertIn('PENDING', text)
            self.assertIn('REVIEWED', other._suptitle.get_text())
            self.assertIn('NO_PROMOTION', text)
            self.assertIn('deposits INCLUDED', text)
            self.assertIn('W = E + R', text)
            self.assertIn('1.8%', text)
            self.assertNotIn('3x risk', text.lower())
            self.assertNotIn('triple risk', text.lower())
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

    def test_heatmap_uses_real_pnl_and_same_budget_wealth_metrics(self):
        s, p, d = self.bundle
        figures = plots.render_five(s, p, d)
        heat_axes = [ax for ax in figures[plots.FIGURE_NAMES[3]].axes if ax.images]
        fields = ('delta_real_trading_net_pnl', 'delta_wealth_max_dd_pp', 'delta_wealth_sharpe')
        for row, arm in enumerate(('A', 'C')):
            for col, field in enumerate(fields):
                expected = p.loc[p.arm.eq(arm)].set_index('start').loc[list(STARTS), field].to_numpy()
                np.testing.assert_array_equal(heat_axes[row * 3 + col].images[0].get_array().ravel(), expected)
        for fig in figures.values():
            fig.clear()

    def test_loss_and_exhaustion_counts_use_real_pnl_and_retain_all_mature_windows(self):
        s, p, d = self.bundle
        figures = plots.render_five(s, p, d)
        axes = figures[plots.FIGURE_NAMES[4]].axes
        for axis, field, check in ((axes[0], 'real_trading_net_pnl', lambda x: x < 0),
                                    (axes[1], 'reserve_exhausted', lambda x: x)):
            expected = [int((s.variant.eq(variant) & ~s.observation_only &
                             s.start.str[5:7].eq(month) & check(s[field])).sum())
                        for variant in VARIANTS for month in ('01', '06')]
            self.assertEqual([int(bar.get_height()) for bar in axis.patches], expected)
        for fig in figures.values():
            fig.clear()


if __name__ == '__main__':
    unittest.main()
