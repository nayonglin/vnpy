"""Display-only adapter behavior: no strategy replay or market I/O."""
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

import pandas as pd

HERE = Path(__file__).resolve().parent
ADAPTER = HERE / 'stage031_canonical_recap.py'


def load_adapter():
    if not ADAPTER.exists():
        raise AssertionError('Stage031 frozen-source recap adapter is missing')
    spec = importlib.util.spec_from_file_location('stage031_canonical_recap', ADAPTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture():
    rounds = pd.DataFrame([dict(role='weekly', vt_symbol='CF505.CZCE', direction='short',
        entry_trade_id='BACKTESTING.1', exit_trade_id='BACKTESTING.3',
        entry_execution_datetime='2015-01-05 09:00:00+08:00',
        exit_execution_datetime='2015-01-07 09:00:00+08:00',
        entry_trading_date='2015-01-05', exit_trading_date='2015-01-07',
        opened_volume=2., fill_count=3, net_pnl=40.)])
    terminal = pd.DataFrame([dict(role='weekly', vt_symbol='rb2701.SHFE', direction='short',
        entry_trade_id='BACKTESTING.4', entry_execution_datetime='2026-10-19 09:00:00+08:00',
        entry_trading_date='2026-10-19', opened_volume=1., fill_count=1, end_pos=-1.,
        terminal_mark=3037., partial_closed_net_pnl=0., remaining_open_net_mtm=30., net_mtm=30.)])
    fills = pd.DataFrame([
        dict(trade_id='BACKTESTING.1', vt_symbol='CF505.CZCE', direction='空', offset='开',
             price=100., volume=2., trading_date='2015-01-05', datetime='2015-01-05 09:00:00+08:00', exit_reason=''),
        dict(trade_id='BACKTESTING.2', vt_symbol='CF505.CZCE', direction='多', offset='平',
             price=90., volume=1., trading_date='2015-01-06', datetime='2015-01-06 09:00:00+08:00', exit_reason='short_profit5_half'),
        dict(trade_id='BACKTESTING.3', vt_symbol='CF505.CZCE', direction='多', offset='平',
             price=95., volume=1., trading_date='2015-01-07', datetime='2015-01-07 09:00:00+08:00', exit_reason='short_ma20_stop'),
        dict(trade_id='BACKTESTING.4', vt_symbol='rb2701.SHFE', direction='空', offset='开',
             price=3040., volume=1., trading_date='2026-10-19', datetime='2026-10-19 09:00:00+08:00', exit_reason='')])
    return rounds, terminal, fills


class FrozenRecapTests(unittest.TestCase):
    def test_canonical_loader_avoids_strategy_and_tqsdk_imports(self):
        m = load_adapter()
        before = set(sys.modules)
        renderer = m.load_canonical_renderer(m.RENDERER)
        added = set(sys.modules) - before
        self.assertTrue(callable(renderer._records))
        self.assertTrue(callable(renderer._html))
        self.assertFalse(any(x.startswith(('tqsdk', 'qmt_roll', 'analyze_qmt')) for x in added))

    def test_partial_closes_use_weighted_price_and_frozen_pnl_without_direction_adjustment(self):
        m = load_adapter()
        rounds, terminal, fills = fixture()
        episodes, remainder = m.episodes_from_frozen(rounds, terminal, fills, 'weekly')
        row = episodes.iloc[0]
        self.assertEqual(row.weighted_exit_price, 92.5)
        self.assertEqual(row.exit_price, 95.)
        self.assertAlmostEqual(row.price_change_pct, -7.5)
        self.assertEqual(row.realized_pnl, 40.)
        self.assertTrue(pd.isna(row.r_multiple))
        self.assertEqual(row.partial_markers[0]['trade_id'], 'BACKTESTING.2')
        self.assertEqual(row.partial_markers[0]['volume'], 1.)
        self.assertEqual(len(remainder), 1)

    def test_terminal_is_separate_and_never_gets_a_final_exit(self):
        m = load_adapter()
        episodes, terminal = m.episodes_from_frozen(*fixture(), 'weekly')
        self.assertEqual(len(episodes), 1)
        self.assertEqual(terminal.iloc[0].entry_trade_id, 'BACKTESTING.4')
        self.assertNotIn('exit_date', terminal.columns)
        self.assertNotIn('exit_price', terminal.columns)

    def test_missing_fill_evidence_fails_closed(self):
        m = load_adapter()
        r, t, f = fixture()
        with self.assertRaisesRegex(ValueError, 'fill count'):
            m.episodes_from_frozen(r, t, f.drop(index=1), 'weekly')

    def test_unbalanced_closed_volume_fails_closed(self):
        m = load_adapter()
        r, t, f = fixture()
        f.loc[2, 'volume'] = .5
        with self.assertRaisesRegex(ValueError, 'closed volume'):
            m.episodes_from_frozen(r, t, f, 'weekly')

    def test_existing_or_source_output_is_rejected(self):
        m = load_adapter()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'source'
            source.mkdir()
            with self.assertRaises(ValueError):
                m.create_new_output(source / 'nested', [source])
            dest = root / 'new'
            m.create_new_output(dest, [source])
            with self.assertRaises(FileExistsError):
                m.create_new_output(dest, [source])

    def test_physical_epoch_prevents_decade_alias_mixing_and_preserves_gap(self):
        m = load_adapter()
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'daily.sqlite'
            conn = sqlite3.connect(db)
            conn.execute('CREATE TABLE dbbardata(symbol,exchange,interval,datetime,open_price,high_price,low_price,close_price,volume,open_interest)')
            data = [('CF505','CZCE','d','2015-01-05 00:00:00',100.,101.,99.,100.,10.,20.),
                    ('CF505','CZCE','d','2015-01-07 00:00:00',95.,96.,94.,95.,10.,20.),
                    ('CF505','CZCE','d','2025-01-06 00:00:00',900.,901.,899.,900.,10.,20.)]
            conn.executemany('INSERT INTO dbbardata VALUES (?,?,?,?,?,?,?,?,?,?)', data)
            conn.commit(); conn.close()
            epoch = pd.DataFrame([dict(vt_symbol='CF505.CZCE', date='2015-01-05', contract_epoch_id='CZCE.CF.201505',open=100.,high=101.,low=99.,close=100.,volume=10.),
                                  dict(vt_symbol='CF505.CZCE', date='2015-01-07', contract_epoch_id='CZCE.CF.201505',open=95.,high=96.,low=94.,close=95.,volume=10.),
                                  dict(vt_symbol='CF505.CZCE', date='2025-01-06', contract_epoch_id='CZCE.CF.202505',open=900.,high=901.,low=899.,close=900.,volume=10.)])
            bars, epoch_id = m.exact_epoch_bars(db, epoch, 'CF505.CZCE', '2015-01-05', '2015-01-07')
            self.assertEqual(epoch_id, 'CZCE.CF.201505')
            self.assertEqual(bars['close'].tolist(), [100.,95.])
            self.assertEqual(len(bars), 2)

    def test_epoch_must_contain_both_closed_endpoints(self):
        m = load_adapter()
        epoch = pd.DataFrame([dict(vt_symbol='CF505.CZCE',date='2015-01-05',contract_epoch_id='e1')])
        with self.assertRaisesRegex(ValueError, 'exit'):
            m.exact_epoch_bars(Path('/not/used'), epoch, 'CF505.CZCE', '2015-01-05', '2015-01-07')

    def test_record_partial_markers_keep_canonical_coordinates_and_unknown_R_is_null(self):
        m = load_adapter()
        renderer = m.load_canonical_renderer(m.RENDERER)
        episodes, terminal = m.episodes_from_frozen(*fixture(), 'weekly')
        dates = pd.date_range('2014-11-01', '2015-03-01', freq='B')
        daily = pd.DataFrame(dict(date=dates,open=100.,high=101.,low=90.,close=95.,volume=10.,
            source_vt_symbol='CF505.CZCE',context_fallback=0,display=1,weekly_display=1,
            monthly_display=1,trading_day_index=range(len(dates))))
        row = episodes.iloc[0]
        records, manifest = m.make_records(renderer, episodes, {row.open_trade_id:daily},
            {row.open_trade_id:list(dates)})
        meta = records[0]['meta']
        self.assertIsNone(meta['r_multiple'])
        self.assertEqual(meta['partial_markers'][0]['price'], 90.)
        i = records[0]['daily']['date'].index('2015-01-06')
        self.assertEqual(meta['partial_markers'][0]['x'], records[0]['daily']['x'][i])
        self.assertEqual(manifest.iloc[0].partial_marker_count, 1)
        self.assertEqual(manifest.iloc[0].context_fallback_days, 0)
        self.assertEqual(manifest.iloc[0].intraday_missing_days, len(dates))
        self.assertEqual(len(meta['missing_15m_dates']), len(dates))


    def test_canonical_html_inserts_partial_extension_without_replacing_plot_code(self):
        m = load_adapter()
        renderer = m.load_canonical_renderer(m.RENDERER)
        page = m.canonical_html(renderer, [], {'episode_scope':'all', 'page_title':'frozen recap'})
        self.assertLess(page.index('const original=Plotly.react'), page.index('const records='))
        self.assertIn('data-period="day30" checked', page)
        self.assertIn('data-period="daily" checked', page)

    def test_held_period_exact_bar_gap_blocks_chart_instead_of_using_proxy(self):
        m = load_adapter()
        renderer = m.load_canonical_renderer(m.RENDERER)
        episodes, _ = m.episodes_from_frozen(*fixture(), 'weekly')
        row = next(episodes.itertuples(index=False))
        calendar = pd.DataFrame(dict(date=pd.date_range('2015-01-05','2015-01-07',freq='B'),
            product='CF',exchange='CZCE',main_contract_vt='some_proxy.CZCE'))
        exact = pd.DataFrame(dict(date=pd.to_datetime(['2015-01-05','2015-01-07']),
            open=100.,high=101.,low=90.,close=95.,volume=10.))
        with self.assertRaisesRegex(ValueError, 'held-period exact-contract gap'):
            m.make_context(renderer,row,calendar,exact)


    def test_terminal_fill_export_retains_actual_entry_and_never_synthesizes_close(self):
        m = load_adapter()
        _, terminal, fills = fixture()
        table = m.terminal_fill_table(fills,terminal)
        self.assertEqual(table.trade_id.tolist(), ['BACKTESTING.4'])
        self.assertEqual(table.price.tolist(), [3040.])
        self.assertEqual(table.offset.tolist(), ['开'])
        self.assertTrue(table.terminal_observation_no_final_exit.all())

    def test_terminal_missing_fill_evidence_fails_closed(self):
        m = load_adapter()
        _, terminal, fills = fixture()
        with self.assertRaisesRegex(ValueError,'terminal fill count'):
            m.terminal_fill_table(fills.iloc[:3],terminal)


if __name__ == '__main__':
    unittest.main()
