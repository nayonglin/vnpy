"""Finalization consumes verified chart cache, never recalculates the strategy."""
import importlib.util
import json
from pathlib import Path
import unittest

import pandas as pd

HERE = Path(__file__).resolve().parent
FINALIZER = HERE / 'stage020_review_finalizer.py'


class FinalizerTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(FINALIZER.exists(), 'generic review finalizer is not implemented')
        fixture_spec = importlib.util.spec_from_file_location('recap_fixtures', HERE / 'test_stage001_frozen_recap.py')
        fixture_module = importlib.util.module_from_spec(fixture_spec)
        fixture_spec.loader.exec_module(fixture_module)
        self.fixture = fixture_module.FrozenRecapTest(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.source = self.fixture.source
        self.root = self.fixture.root
        self.parent = self.root / 'parent_recap'
        self.out = self.root / 'reviewed_recap'
        meta = pd.read_csv(self.source / 'contract_metadata.csv')
        meta['product'] = 'rb'
        meta['exchange'] = 'SHFE'
        meta = pd.concat([meta, pd.DataFrame([{'vt_symbol':'cu2201.SHFE','size':5,'product':'cu','exchange':'SHFE'}, {'vt_symbol':'sc2201.INE','size':1000,'product':'sc','exchange':'INE'}])], ignore_index=True)
        meta.to_csv(self.source / 'contract_metadata.csv', index=False)
        metrics_path = self.source / 'summary.json'
        metrics = json.loads(metrics_path.read_text())
        metrics.update(max_actual_products=1, last_fill_date='2019-01-03', mode='daily-proxy', position_count_limit_removed=True)
        metrics_path.write_text(json.dumps(metrics))
        self.fixture.freeze()
        self.parent_summary = self.fixture.module.render_bundle(self.source, self.parent)
        self.review = self.root / 'stage099_independent_review.md'
        self.review.write_text('# 仅fixture独立审查\n未执行金融回测。\n')
        self.review_json = self.review.with_suffix('.json')
        self.review_json.write_text(json.dumps({'source_manifest_sha256':self.fixture.module.sha256(self.source / 'manifest.json'), 'verdict':'fixture_only_no_strategy_promotion'}))
        spec = importlib.util.spec_from_file_location('review_finalizer', FINALIZER)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.visible_parser = fixture_module.VisibleText

    def test_annotates_dynamic_facts_and_reuses_identical_chart_cache(self):
        result = self.module.finalize(self.parent, self.review, self.out)
        self.assertEqual((self.out / 'records.json').read_bytes(), (self.parent / 'records.json').read_bytes())
        self.assertEqual(result['backtest_metrics'], self.parent_summary['backtest_metrics'])
        self.assertEqual(result['artifact_sha256']['records.json'], self.fixture.module.sha256(self.out / 'records.json'))
        facts = result['review_display_facts']
        self.assertEqual(facts['input_product_count'], 3)
        self.assertEqual(facts['input_exchanges'], ['INE','SHFE'])
        self.assertEqual(facts['traded_product_count'], 1)
        self.assertEqual(facts['traded_exchanges'], ['SHFE'])
        self.assertEqual(facts['residual_quote_dates'], [{'vt_symbol':'rb1901.SHFE','direction':'short','volume':1.0,'last_quote_date':'2020-12-31'}])
        self.assertEqual(facts['max_actual_products'], 1)
        self.assertEqual(facts['last_fill_date'], '2019-01-03')
        self.assertEqual(result['independent_review']['sha256'], self.fixture.module.sha256(self.review))
        parser = self.visible_parser()
        parser.feed((self.out / 'index.html').read_text())
        visible = ''.join(parser.text)
        for expected in ('输入3品种/2所', '实际成交1品种/1所', '最后报价2020-12-31', '最大同时持仓品种1', '末次成交2019-01-03', 'stage099_independent_review.md'):
            self.assertIn(expected, visible)
        self.assertNotIn('四残仓', visible)
        self.assertNotIn('实际67品种', visible)
        self.assertEqual((self.out / 'independent_review.md').read_bytes(), self.review.read_bytes())

    def test_mutated_chart_cache_fails_before_output_creation(self):
        (self.parent / 'records.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'parent_artifact'):
            self.module.finalize(self.parent, self.review, self.out)
        self.assertFalse(self.out.exists())

    def test_mutated_source_quote_file_fails_before_output_creation(self):
        with (self.source / 'market_daily.csv').open('a') as handle:
            handle.write('\n')
        with self.assertRaisesRegex(ValueError, 'source_hash'):
            self.module.finalize(self.parent, self.review, self.out)
        self.assertFalse(self.out.exists())

    def test_review_bound_to_another_source_is_rejected(self):
        self.review_json.write_text(json.dumps({'source_manifest_sha256':'wrong-source'}))
        with self.assertRaisesRegex(ValueError, 'review_source'):
            self.module.finalize(self.parent, self.review, self.out)
        self.assertFalse(self.out.exists())

    def test_review_annotations_are_plain_text_and_empty_residual_is_dynamic(self):
        # Create another valid frozen fixture with the residual short closed later.
        path = self.source / 'trades.csv'
        trades = pd.read_csv(path)
        trades = pd.concat([trades, pd.DataFrame([{'trade_id':'c2','datetime':'2019-02-04 09:00:00','date':'2019-02-04','vt_symbol':'rb1901.SHFE','direction':'long','offset':'close','volume':1,'price':115}])], ignore_index=True)
        trades.to_csv(path, index=False)
        metrics_path = self.source / 'summary.json'
        metrics = json.loads(metrics_path.read_text())
        metrics.update(total_trade_count=4, last_fill_date='2019-02-04')
        metrics_path.write_text(json.dumps(metrics))
        self.fixture.freeze()
        self.parent = self.root / 'flat_parent'
        self.parent_summary = self.fixture.module.render_bundle(self.source, self.parent)
        payload = '</script><img src=x onerror="alert(1)">审查结果仅作研究。'
        self.review_json.write_text(json.dumps({'source_manifest_sha256':self.fixture.module.sha256(self.source / 'manifest.json'), 'verdict':payload}))
        result = self.module.finalize(self.parent, self.review, self.out)
        self.assertEqual(result['review_display_facts']['residual_quote_dates'], [])
        parser = self.visible_parser()
        parser.feed((self.out / 'index.html').read_text())
        self.assertIn('期末无残余仓位', ''.join(parser.text))
        self.assertIn(payload, ''.join(parser.text))
        self.assertNotIn('img', parser.tags)

    def test_output_is_new_and_isolated(self):
        with self.assertRaises(ValueError):
            self.module.finalize(self.parent, self.review, self.parent / 'nested')
        self.out.mkdir()
        with self.assertRaises(FileExistsError):
            self.module.finalize(self.parent, self.review, self.out)


if __name__ == '__main__':
    unittest.main()
