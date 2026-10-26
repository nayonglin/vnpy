"""Behavior tests: exact trade day, closed-vs-open attribution, and fail-closed reporting."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
import pandas as pd

PATH = Path(__file__).with_name('stage029_build_artifacts.py')


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('stage029_report', PATH)
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def test_pnl_stats_names_flat_payoff_and_profit_factor(self):
        # Losing flat rows or using total PnL as the average would break this.
        got = self.m.pnl_stats(pd.DataFrame({'net_pnl': [20., -10., 0., 40.]}))
        self.assertEqual((got['count'], got['wins'], got['losses'], got['flat']), (4, 2, 1, 1))
        self.assertEqual(got['win_rate_pct'], 50.)
        self.assertEqual(got['average_win'], 30.)
        self.assertEqual(got['average_loss_abs'], 10.)
        self.assertEqual(got['payoff_ratio'], 3.)
        self.assertEqual(got['profit_factor'], 6.)
        self.assertEqual(got['closed_net_pnl'], 50.)

    def fixture(self):
        # The first fill is Friday night for Monday's trade day.
        rows = [
            ('1', '2020-01-03 21:00:00+08:00', '2020-01-06', '多', '开', 10., 2.),
            ('2', '2020-01-06 09:00:00+08:00', '2020-01-06', '空', '平', 12., 1.),
            ('3', '2020-01-07 09:00:00+08:00', '2020-01-07', '空', '平', 8., 1.),
            ('4', '2020-01-08 09:00:00+08:00', '2020-01-08', '多', '开', 10., 2.),
            ('5', '2020-01-09 09:00:00+08:00', '2020-01-09', '空', '平', 13., 1.),
        ]
        trades = pd.DataFrame(rows, columns=['trade_id', 'datetime', 'trading_date', 'direction', 'offset', 'price', 'volume'])
        trades['vt_symbol'] = 'au2006.SHFE'
        clock = trades.rename(columns={'datetime': 'execution_datetime'}).copy()
        effective = {'sizes': {'au2006.SHFE': 10}, 'slippages': {'au2006.SHFE': .1}, 'rates': {'au2006.SHFE': 0}}
        return trades, clock, effective

    def test_fifo_and_complete_contract_rounds_separate_open_round_realized_pnl(self):
        # A flat-to-flat round is one -4 round; partials of an open round stay separate.
        trades, clock, effective = self.fixture()
        fills = self.m.ordered_fills(trades, clock)
        segments, rounds, opened, stats = self.m.inventory_accounting(fills, effective, {'au2006.SHFE': 14.})
        self.assertEqual(segments.entry_trading_date.iloc[0], '2020-01-06')
        self.assertEqual(segments.net_pnl.tolist(), [18., -22., 28.])
        self.assertEqual(rounds.net_pnl.tolist(), [-4.])
        self.assertEqual(opened.iloc[0]['partial_closed_net_pnl'], 28.)
        self.assertEqual(opened.iloc[0]['remaining_open_net_mtm'], 39.)
        self.assertEqual(opened.iloc[0]['net_mtm'], 67.)
        self.assertEqual(stats['closed_fifo']['closed_net_pnl'], 24.)
        self.assertEqual(stats['open_remaining_net_mtm'], 39.)
        self.assertEqual(stats['ledger_net_pnl'], 63.)
        self.assertEqual(stats['total_slippage'], 7.)

    def test_trading_day_mismatch_is_rejected_even_when_execution_matches(self):
        trades, clock, _ = self.fixture()
        clock.loc[0, 'trading_date'] = '2020-01-03'
        with self.assertRaisesRegex(ValueError, 'trading_date'):
            self.m.ordered_fills(trades, clock)

    def test_unmatched_close_and_missing_terminal_mark_fail_closed(self):
        trades, clock, effective = self.fixture()
        fills = self.m.ordered_fills(trades, clock)
        with self.assertRaisesRegex(ValueError, 'terminal_mark'):
            self.m.inventory_accounting(fills, effective, {})
        with self.assertRaisesRegex(ValueError, 'unmatched_close'):
            self.m.inventory_accounting(fills.iloc[1:], effective, {})

    def test_curve_includes_initial_capital_drawdown_and_simple_return_sharpe(self):
        # Reporting must use all daily simple returns, including the initial day.
        d = pd.DataFrame({'date': pd.to_datetime(['2020-01-06', '2020-01-07']), 'account_equity': [90., 108.], 'net_pnl': [-10., 18.], 'slippage': [0., 0.], 'commission': [0., 0.], 'trade_count': [0., 0.]})
        got = self.m.curve_metrics(d, 100.)
        self.assertAlmostEqual(got['max_dd_pct'], -10.)
        self.assertAlmostEqual(got['total_return_pct'], 8.)
        self.assertAlmostEqual(got['sharpe'], 3.7416573867739413)

    def test_outputs_refuse_existing_or_source_descendant(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root);source = p/'N_attempt002';source.mkdir()
            with self.assertRaises(FileExistsError):
                self.m.validate_output_paths(source, p/'plot.png', [source])
            with self.assertRaisesRegex(ValueError, 'inside_input'):
                self.m.validate_output_paths(source/'new', p/'plot.png', [source])

    def write_empty_ledger(self, path, candidate, db):
        path.mkdir()
        flags = {key:False for key in self.m.FLAGS}
        actual = dict(flags, ma_short=5, ma_mid=10, ma_long=20, research_exact_array_manager_size=41,
            capital_base=150000., max_concurrent_positions=19, stage830_broker_margin_multiplier=1.65,
            forced_margin_deleverage_broker_multiplier=1.65, enable_rsi_partial_exit=not candidate)
        def write(name, value):
            (path/name).write_text(json.dumps(value))
        write('terminal.json', {'status':'completed_pending_independent_review', 'error':None})
        write('postflight.json', {'inputs_unchanged':True, 'mismatches':[]})
        write('actual_strategy_settings.json', [{'actual':actual, 'setting':actual, 'engine_capital':150000., 'strategy_class':'WeekCloseExitStrategy' if candidate else 'HistoricalSafetyStrategy'}])
        write('effective_parameters.json', {'spec':{'capital':{'account_capital':150000., 'c3_capital':150000.}}, 'sizes':{}, 'slippages':{}, 'rates':{}})
        write('metrics.json', {'end_equity':150000., 'total_return_pct':0., 'max_dd_pct':0., 'sharpe':None, 'total_trade_count':0})
        write('preflight.json', {'start':'2015-01-01', 'end':'2026-10-23', 'universe_products':sorted(self.m.POOL), 'ready_need':21, 'storage_capacity':41, 'execution_model':self.m.EXECUTION_MODEL, 'minute_quote_confirmed':False})
        proofs = {
            'bar_open_acceptance.json':{'accepted':True, 'verdict':'PASS_DECLARED_BAR_OPEN_MODEL', 'trade_count':0},
            'ai_selection_acceptance.json':{'accepted':True}, 'macd_acceptance.json':{'accepted':True},
            'short_case2_acceptance.json':{'accepted':True, 'short_case2_gate_allowed':not candidate, 'short_case2_opened':0},
            'no_position_cap_acceptance.json':{'accepted':True, 'MA40_decision_enabled':False, 'max_daily_product_positions':0},
            'historical_safety_acceptance.json':{'accepted':True, 'requested_start':'2015-01-01', 'requested_end':'2026-10-23', 'actual_calendar_matches':True, 'readiness_calendar_matches':True, 'epoch_failure_count':0, 'strict_next_trading_day_open':True}}
        if candidate:
            proofs['week_close_exit_acceptance.json'] = {'accepted':True, 'rsi_exit_enabled':False, 'short_case2_enabled':False, 'reconciliation_rebuilt_layer_count':0, 'weekly_stop_guard_failure_count':0}
        for name, value in proofs.items():
            write(name, value)
        write('data_quality.json', {'held_or_traded_daily_gaps':[], 'held_or_traded_zero_volume':[], 'captured_bar_failures':[]})
        write('data_read_counts.json', {'minute_reads':0, 'proxy_reads':0, 'ai_selection_model_load_attempts':0})
        write('actual_database_binding.json', {'expected':str(db), 'database_list':[[0,'main',str(db)]]})
        write('input_manifest.json', {str(db):self.m.sha(db)})
        dates = ['2015-01-05', '2019-12-31', '2020-12-31', '2026-10-23']
        pd.DataFrame({'date':dates, 'account_equity':[150000.]*4, 'net_pnl':[0.]*4, 'slippage':[0.]*4, 'commission':[0.]*4, 'trade_count':[0]*4, 'total_margin_exact':[0.]*4, 'broker10_total_margin_exact':[0.]*4}).to_csv(path/'daily.csv', index=False)
        pd.DataFrame(columns=['trade_id','vt_symbol','direction','offset','price','volume','trading_date','datetime']).to_csv(path/'trades.csv', index=False)
        pd.DataFrame(columns=['trade_id','vt_symbol','direction','offset','price','volume','trading_date','execution_datetime']).to_csv(path/'execution_clock.csv', index=False)
        pd.DataFrame(columns=['signal','candidate_status']).to_csv(path/'entry_candidates.csv', index=False)
        pd.DataFrame({'date':dates, 'vt_symbol':['au2006.SHFE']*4, 'end_pos':[0.]*4, 'close_price':[10.]*4, 'net_pnl':[0.]*4, 'slippage':[0.]*4, 'commission':[0.]*4, 'trade_count':[0]*4}).to_csv(path/'positions.csv', index=False)

    def test_empty_completed_ledgers_publish_hashed_outputs_and_nested_figure_once(self):
        # Catches I/O publication regressions and accidentally recomputing zero-fill data as missing.
        with tempfile.TemporaryDirectory() as root:
            root = Path(root);db = root/'daily.sqlite';db.write_bytes(b'synthetic immutable data identity')
            a, b, out = root/'baseline', root/'candidate', root/'stage029_report_fixture'
            self.write_empty_ledger(a, False, db);self.write_empty_ledger(b, True, db)
            proof_path = b/'week_close_exit_acceptance.json'
            proof = json.loads(proof_path.read_text());proof['weekly_stop_guard_failure_count'] = 1;proof_path.write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError, 'week_close_exit_guard_failure'):
                self.m.load_ledger(b, 'candidate')
            proof['weekly_stop_guard_failure_count'] = 0;proof_path.write_text(json.dumps(proof))
            before = {**self.m.snapshot_dir(a), **self.m.snapshot_dir(b)}
            result = self.m.build_artifacts(a, b, out, out/'equity.png')
            self.assertEqual(result['financial_replays'], 0)
            summary = json.loads((out/'comparison.json').read_text())
            self.assertEqual(summary['status'], 'DERIVED_PENDING_INDEPENDENT_REVIEW')
            self.assertIsNone(summary['independent_review_verdict'])
            self.assertEqual(summary['arms']['candidate']['metrics']['modeled_fill_count'], 0)
            self.assertEqual(len(pd.read_csv(out/'products.csv')), 38)
            self.assertEqual(len(pd.read_csv(out/'slices_2015_2019_2020.csv')), 4)
            self.assertTrue((out/'equity.png').stat().st_size > 1000)
            manifest = json.loads((out/'delivery_manifest.json').read_text())
            self.assertEqual(manifest['comparison_sha256'], self.m.sha(out/'comparison.json'))
            self.m.verify_sources(manifest['files_sha256'])
            self.assertEqual(before, {**self.m.snapshot_dir(a), **self.m.snapshot_dir(b)})
            with self.assertRaises(FileExistsError):
                self.m.build_artifacts(a, b, out, out/'equity.png')

    def test_terminal_and_acceptance_cannot_report_rejected_or_unfinished(self):
        with self.assertRaisesRegex(ValueError, 'completed'):
            self.m.validate_completion({'status': 'rejected_execution_bar_open', 'error': None}, {'inputs_unchanged': True}, {'bar_open_acceptance.json': {'accepted': True}})
        with self.assertRaisesRegex(ValueError, 'acceptance'):
            self.m.validate_completion({'status': 'completed_pending_independent_review', 'error': None}, {'inputs_unchanged': True}, {'bar_open_acceptance.json': {'accepted': False}})


if __name__ == '__main__':
    unittest.main()
