"""Behavior gates: evidence identity, residual disclosure, isolated canonical charts."""
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

HERE = Path(__file__).resolve().parent
ADAPTER = HERE / 'stage001_frozen_recap.py'


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.hidden = 0
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag in ('script', 'style'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)


class FrozenRecapTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ADAPTER.exists(), 'frozen recap adapter is not implemented')
        spec = importlib.util.spec_from_file_location('frozen_recap', ADAPTER)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'run'
        self.source.mkdir()
        dates = pd.bdate_range('2010-01-01', '2020-12-31')
        pd.DataFrame([['o1', '2018-01-03 09:00:00', '2018-01-03', 'rb1901.SHFE', 'long', 'open', 1, 100], ['c1', '2018-02-05 09:00:00', '2018-02-05', 'rb1901.SHFE', 'short', 'close', 1, 110], ['o2', '2019-01-03 09:00:00', '2019-01-03', 'rb1901.SHFE', 'short', 'open', 1, 120]], columns=['trade_id','datetime','date','vt_symbol','direction','offset','volume','price']).to_csv(self.source / 'trades.csv', index=False)
        pd.DataFrame({'date': dates, 'balance': 1000000}).to_csv(self.source / 'daily.csv', index=False)
        pd.DataFrame({'vt_symbol': ['rb1901.SHFE'], 'size': [10]}).to_csv(self.source / 'contract_metadata.csv', index=False)
        pd.DataFrame({'date': dates, 'product': 'rb', 'exchange': 'SHFE', 'main_contract_vt': 'rb1901.SHFE'}).to_csv(self.source / 'mapping.csv', index=False)
        pd.DataFrame({'date': dates, 'vt_symbol': 'rb1901.SHFE', 'open': 100, 'high': 120, 'low': 90, 'close': 110, 'volume': 1000}).to_csv(self.source / 'market_daily.csv', index=False)
        (self.source / 'summary.json').write_text(json.dumps({'end_balance':1000100, 'total_return':0.01, 'total_trade_count':3, 'sharpe_ratio':0.2}))
        self.freeze()

    def freeze(self):
        (self.source / 'manifest.json').write_text(json.dumps({'run_id':'fixture-one', 'source_commit':'fixture-commit', 'parameters':{'capital':1000000}, 'start':'2015-01-01', 'end':'2020-12-31', 'hashes':{p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir() if p.name != 'manifest.json'}}))

    def test_missing_or_mutated_evidence_is_rejected_before_output(self):
        (self.source / 'daily.csv').write_text('date,balance\n2018-01-03,999\n')
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.module.render_bundle(self.source, self.root / 'recap')
        self.assertFalse((self.root / 'recap').exists())

    def test_complete_episode_residual_and_metrics_are_preserved(self):
        out = self.root / 'recap'
        result = self.module.render_bundle(self.source, out)
        self.assertEqual(result['chart_episodes'], 1)
        self.assertEqual(result['residual_open_positions'], [{'vt_symbol':'rb1901.SHFE', 'direction':'short', 'volume':1.0}])
        self.assertEqual(result['backtest_metrics']['end_balance'],1000100)
        manifest = pd.read_csv(out / 'chart_manifest.csv')
        self.assertEqual(manifest.iloc[0]['entry_date'], '2018-01-03')
        self.assertEqual(manifest.iloc[0]['exit_date'], '2018-02-05')
        self.assertEqual(manifest.iloc[0]['realized_pnl'], 100)
        self.assertEqual(manifest.iloc[0]['price_change_pct'], 10)
        self.assertTrue((out / 'index.html').exists())
        self.assertTrue((out / 'summary.json').exists())
        self.assertGreater(manifest.iloc[0]['day30_bars'], 0)
        self.assertEqual(manifest.iloc[0]['draw_intraday'], 0, 'empty minute window is unavailable')
        self.assertEqual(result['market_download_performed'], False)

    def test_partially_closed_entry_is_not_a_complete_episode(self):
        trades = pd.read_csv(self.source / 'trades.csv')
        trades.loc[trades['trade_id'].eq('o1'), 'volume'] = 2
        trades.to_csv(self.source / 'trades.csv', index=False)
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'no completed episodes'):
            self.module.render_bundle(self.source, self.root / 'recap')

    def test_missing_identity_member_fails_closed(self):
        manifest = json.loads((self.source / 'manifest.json').read_text())
        del manifest['hashes']['summary.json']
        (self.source / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.module.render_bundle(self.source, self.root / 'recap')

    def test_frozen_metrics_trade_count_must_match_ledger(self):
        path = self.source / 'summary.json'
        metrics = json.loads(path.read_text())
        metrics['total_trade_count'] = 99
        path.write_text(json.dumps(metrics))
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'trade count'):
            self.module.render_bundle(self.source, self.root / 'recap')

    def test_daily_proxy_is_visible_and_all_boundaries_are_plain_text(self):
        path = self.source / 'summary.json'
        metrics = json.loads(path.read_text())
        boundaries = ['关闭C2日内止损和C9的0.5R止损/重试。', '静态费用快照，非PIT。', '</script><img src=x onerror="alert(1)">供需缺CSV。']
        metrics.update(mode='daily-proxy', boundaries=boundaries)
        path.write_text(json.dumps(metrics))
        self.freeze()
        out = self.root / 'recap'
        result = self.module.render_bundle(self.source, out)
        self.assertIn('日线近似', result['page_title'])
        self.assertIn('日线近似', result['source_label'])
        self.assertIn('日线近似', result['source_warning'])
        parser = VisibleText()
        parser.feed((out / 'index.html').read_text())
        visible = ''.join(parser.text)
        self.assertIn('日线近似', visible)
        for boundary in boundaries:
            self.assertIn(boundary, visible)
        self.assertNotIn('img', parser.tags)
        self.assertIn('合约价差毛收益', visible)
        self.assertIn('残余未平仓', visible)

    def test_strict_source_is_not_labeled_as_daily_proxy(self):
        path = self.source / 'summary.json'
        metrics = json.loads(path.read_text())
        metrics.update(mode='strict', boundaries=['严格缺分钟即停止。'])
        path.write_text(json.dumps(metrics))
        self.freeze()
        out = self.root / 'recap'
        result = self.module.render_bundle(self.source, out)
        self.assertNotIn('日线近似', result['page_title'])
        self.assertNotIn('日线近似', result['source_label'])
        parser = VisibleText()
        parser.feed((out / 'index.html').read_text())
        self.assertIn('严格缺分钟即停止。', ''.join(parser.text))

    def test_entry_signal_is_preserved_from_frozen_open_trade(self):
        path = self.source / 'trades.csv'
        trades = pd.read_csv(path)
        trades['signal'] = ['long_case2', 'close_exit', 'short_case3']
        trades.to_csv(path, index=False)
        self.freeze()
        out = self.root / 'recap'
        self.module.render_bundle(self.source, out)
        self.assertEqual(pd.read_csv(out / 'closed_lots.csv').iloc[0]['signal'], 'long_case2')
        self.assertEqual(pd.read_csv(out / 'all_trade_episodes.csv').iloc[0]['signal'], 'long_case2')
        self.assertEqual(pd.read_csv(out / 'chart_manifest.csv').iloc[0]['signal'], 'long_case2')
        page = (out / 'index.html').read_text()
        payload = page.split('const records=', 1)[1].split('; const summary=', 1)[0]
        self.assertEqual(json.loads(payload)[0]['meta']['signal'], 'long_case2')

    def test_uncertifiable_book_result_is_prominent_in_title(self):
        path = self.source / 'summary.json'
        metrics = json.loads(path.read_text())
        boundaries = ['4项到期残仓占满并发；2023年后未再交易；仅诊断账面结果。']
        metrics.update(mode='daily-proxy', performance_certifiable=False,
                       validity_status='diagnostic_book_result_expired_residual_deadlock',
                       boundaries=boundaries)
        path.write_text(json.dumps(metrics))
        self.freeze()
        out = self.root / 'recap'
        result = self.module.render_bundle(self.source, out)
        self.assertIn('执行与残仓受限', result['page_title'])
        self.assertIn('日线近似', result['page_title'])
        parser = VisibleText()
        parser.feed((out / 'index.html').read_text())
        self.assertIn('执行与残仓受限', ''.join(parser.text))
        self.assertIn(boundaries[0], ''.join(parser.text))
        self.assertIs(result['backtest_metrics']['performance_certifiable'], False)

    def test_frozen_aggregate_book_statistics_are_visible_from_source(self):
        path = self.source / 'summary.json'
        metrics = json.loads(path.read_text())
        metrics.update(performance_certifiable=False, end_balance=1175305.835252929,
                       total_return=17.530583525292908, max_ddpercent=-9.771712930111658,
                       sharpe_ratio=0.25366697953826445, completed_episodes=1,
                       win_rate_pct=34.776119402985074,
                       total_commission=9734.16474707106, total_slippage=30725.0)
        path.write_text(json.dumps(metrics))
        self.freeze()
        out = self.root / 'recap'
        result = self.module.render_bundle(self.source, out)
        parser = VisibleText()
        parser.feed((out / 'index.html').read_text())
        visible = ''.join(parser.text)
        for expected in ['冻结账面统计（不可认证业绩）', '期末权益1,175,305.84', '总收益17.5306%', '最大回撤-9.7717%', 'Sharpe0.2537', '3成交/1完整交易', '净胜率34.7761%', '手续费9,734.16', '滑点30,725.00']:
            self.assertIn(expected, result['source_warning'])
            self.assertIn(expected, visible)
        self.assertEqual(result['backtest_metrics']['end_balance'], 1175305.835252929)

    def test_unlimited_product_count_and_net_ratios_are_visible(self):
        path = self.source / 'summary.json'
        metrics = json.loads(path.read_text())
        metrics.update(position_count_limit_removed=True, payoff_ratio=2.345678,
                       profit_factor=1.234567, mode='daily-proxy')
        path.write_text(json.dumps(metrics))
        self.freeze()
        out = self.root / 'recap'
        result = self.module.render_bundle(self.source, out)
        self.assertIn('无品种数上限，每品种1手', result['page_title'])
        self.assertIn('无品种数上限，每品种1手', result['source_warning'])
        parser = VisibleText()
        parser.feed((out / 'index.html').read_text())
        for expected in ('日线近似', '净盈亏比2.3457', '盈利因子1.2346'):
            self.assertIn(expected, ''.join(parser.text))

    def test_chart_cache_is_hash_bound_and_matches_html(self):
        out = self.root / 'recap'
        result = self.module.render_bundle(self.source, out)
        self.assertTrue((out / 'records.json').is_file())
        self.assertEqual(result['artifact_sha256']['records.json'], self.module.sha256(out / 'records.json'))
        page = (out / 'index.html').read_text()
        payload = page.split('const records=', 1)[1].split('; const summary=', 1)[0]
        self.assertEqual(json.loads((out / 'records.json').read_text()), json.loads(payload))

    def test_uncertifiable_source_does_not_invent_old_contract_failures(self):
        path = self.source / 'summary.json'
        metrics = json.loads(path.read_text())
        metrics.update(performance_certifiable=False, boundaries=['本fixture不包含股指到期证据。'])
        path.write_text(json.dumps(metrics))
        self.freeze()
        result = self.module.render_bundle(self.source, self.root / 'recap')
        self.assertNotIn('IH201812', result['source_warning'])
        self.assertNotIn('IC202112', result['source_warning'])
        self.assertIn(metrics['boundaries'][0], result['source_warning'])

    def test_product_mapping_partition_preserves_canonical_context_exactly(self):
        self.assertTrue(hasattr(self.module, 'context_mapping_groups'), 'product mapping partition is not implemented')
        identity, frames, _ = self.module.read_bundle(self.source)
        renderer = self.module.load_display_functions({'rb1901.SHFE':'rb'})
        closed = renderer._closed_lots_from_trade_ledger(frames['trades.csv'], sizes={'rb1901.SHFE':10}, allow_residual_open=True)
        row = next(renderer._all_trade_episodes(closed).itertuples(index=False))
        mapping = frames['mapping.csv']
        other = mapping.assign(product='cu', main_contract_vt='cu1901.SHFE')
        unrelated_exchange = mapping.assign(exchange='DCE', main_contract_vt='rb1901.DCE')
        full = pd.concat([mapping, other, unrelated_exchange], ignore_index=True)
        market = frames['market_daily.csv'].drop(columns='vt_symbol')
        groups = self.module.context_mapping_groups(full)
        self.assertEqual(set(groups), {('rb','SHFE'), ('cu','SHFE'), ('rb','DCE')})
        self.assertEqual(len(groups[('rb','SHFE')]), len(mapping))
        original, original_dates = renderer._context_daily(row, full, {'rb1901.SHFE':market}, allow_daily_download=False, allow_noncritical_daily_gaps=True, data_end=pd.Timestamp(identity['end']))
        partition, partition_dates = renderer._context_daily(row, groups[('rb','SHFE')], {'rb1901.SHFE':market}, allow_daily_download=False, allow_noncritical_daily_gaps=True, data_end=pd.Timestamp(identity['end']))
        pd.testing.assert_frame_equal(original, partition)
        self.assertEqual(original.attrs, partition.attrs)
        self.assertEqual(original_dates, partition_dates)

    def test_output_cannot_overwrite_source_or_existing_recap(self):
        with self.assertRaises(ValueError):
            self.module.render_bundle(self.source, self.source)
        out = self.root / 'recap'
        out.mkdir()
        (out / 'index.html').write_text('keep')
        with self.assertRaises(FileExistsError):
            self.module.render_bundle(self.source, out)
        self.assertEqual((out / 'index.html').read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
