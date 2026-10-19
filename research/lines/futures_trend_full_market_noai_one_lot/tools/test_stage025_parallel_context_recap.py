"""A parallel adapter must preserve canonical contexts and chart payloads exactly."""
import importlib.util
import json
from pathlib import Path
import unittest

import pandas as pd

HERE = Path(__file__).resolve().parent
ENTRY = HERE / 'stage025_parallel_context_recap.py'


class ParallelContextTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ENTRY.exists(), 'optional parallel context adapter is not implemented')
        spec = importlib.util.spec_from_file_location('parallel_fixture', HERE / 'test_stage001_frozen_recap.py')
        fixture_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture_module)
        self.fixture = fixture_module.FrozenRecapTest(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        import stage025_parallel_context_recap
        self.module = stage025_parallel_context_recap

    def test_parallel_contexts_and_final_records_match_serial(self):
        identity, frames, _ = self.fixture.module.read_bundle(self.fixture.source)
        renderer = self.fixture.module.load_display_functions({'rb1901.SHFE':'rb','cu1901.SHFE':'cu'})
        closed = renderer._closed_lots_from_trade_ledger(frames['trades.csv'], sizes={'rb1901.SHFE':10}, allow_residual_open=True)
        episodes = renderer._all_trade_episodes(closed)
        duplicate = episodes.copy()
        duplicate['open_trade_id'] = 'cu-long'
        duplicate['vt_symbol'] = 'cu1901.SHFE'
        duplicate['product'] = 'cu'
        duplicate['direction'] = 'short'
        episodes = pd.concat([episodes, duplicate], ignore_index=True)
        episodes['draw_intraday'] = 1
        mapping = frames['mapping.csv']
        mapping = pd.concat([mapping, mapping.assign(product='cu', main_contract_vt='cu1901.SHFE')], ignore_index=True)
        market = frames['market_daily.csv'].drop(columns='vt_symbol')
        cache = {'rb1901.SHFE':market.copy(), 'cu1901.SHFE':market.copy()}
        serial, serial_dates = {}, {}
        for row in episodes.itertuples(index=False):
            daily, dates = renderer._context_daily(row, mapping, cache, allow_daily_download=False, allow_noncritical_daily_gaps=True, data_end=pd.Timestamp(identity['end']))
            serial[str(row.open_trade_id)] = daily
            serial_dates[str(row.open_trade_id)] = dates
        parallel, parallel_dates = self.module.build_contexts(episodes, mapping, cache, pd.Timestamp(identity['end']), workers=2)
        for key in serial:
            pd.testing.assert_frame_equal(serial[key], parallel[key])
            self.assertEqual(serial[key].attrs, parallel[key].attrs)
            self.assertEqual(serial_dates[key], parallel_dates[key])
        empty_minute = pd.DataFrame(columns=['vt_symbol','bar_datetime','trading_day','open','high','low','close','volume'])
        serial_records, serial_manifest = renderer._records(episodes, serial, serial_dates, empty_minute)
        parallel_records, parallel_manifest = renderer._records(episodes, parallel, parallel_dates, empty_minute)
        self.assertEqual(renderer._json_safe(serial_records), renderer._json_safe(parallel_records))
        pd.testing.assert_frame_equal(serial_manifest, parallel_manifest)

    def test_worker_limit_is_explicit(self):
        with self.assertRaisesRegex(ValueError, 'workers'):
            self.module.build_contexts(pd.DataFrame(), pd.DataFrame(), {}, pd.Timestamp('2020-01-01'), workers=5)

    def test_optional_entry_writes_separate_equivalent_recap_with_provenance(self):
        serial_out = self.fixture.root / 'serial'
        parallel_out = self.fixture.root / 'parallel'
        serial_summary = self.fixture.module.render_bundle(self.fixture.source, serial_out)
        parallel_summary = self.module.render_parallel(self.fixture.source, parallel_out, workers=2)
        self.assertEqual(json.loads((serial_out / 'records.json').read_text()), json.loads((parallel_out / 'records.json').read_text()))
        self.assertEqual(serial_summary['backtest_metrics'], parallel_summary['backtest_metrics'])
        self.assertEqual(parallel_summary['context_generation']['workers'], 2)
        self.assertEqual(parallel_summary['context_generation']['entry_sha256'], self.fixture.module.sha256(ENTRY))
        self.assertEqual(parallel_summary['adapter_code_sha256'], self.fixture.module.sha256(HERE / 'stage001_frozen_recap.py'))


if __name__ == '__main__':
    unittest.main()
