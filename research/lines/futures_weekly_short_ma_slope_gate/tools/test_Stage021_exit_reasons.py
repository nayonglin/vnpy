"""Frozen-ledger behavior checks for the display-only exit explanation."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('exit_recap', HERE / 'Stage021_exit_reasons.py')
recap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recap)


class ExitReasons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = json.loads((recap.SOURCE / 'records.json').read_text())
        cls.tables = recap.read_evidence()

    def test_all_18_reasons_have_unique_frozen_evidence(self):
        records = recap.enrich(self.records, self.tables)
        self.assertEqual(len(records), 18)
        for old, new in zip(self.records, records):
            unchanged = copy.deepcopy(new)
            reason = unchanged['meta'].pop('exit_explanation')
            self.assertEqual(old, unchanged, 'financials, bars and all old metadata must stay identical')
            self.assertEqual(reason['raw_code'], old['meta']['exit_reason'])
            self.assertEqual(reason['fill_id'], old['meta']['close_trade_id'])
            self.assertEqual(reason['execution_datetime'], old['meta']['exit_execution_datetime'])
            self.assertLess(reason['signal_date'], reason['trading_date'])
            self.assertTrue(reason['label'] and reason['description'] and reason['evidence'])

    def test_two_previous_bars_are_completed_weeks_not_days(self):
        records = recap.enrich(self.records, self.tables)
        items = [r['meta']['exit_explanation'] for r in records if 'prev2day' in r['meta']['exit_reason']]
        self.assertEqual(len(items), 4)
        for item in items:
            self.assertIn('两周', item['label'])
            self.assertIn('周收盘', item['evidence'])
            self.assertLessEqual(item['trigger_close'], item['stop_price'])
        self.assertEqual(items[0]['stop_price'], 16460)
        self.assertEqual(items[0]['trigger_close'], 16000)

    def test_every_technical_exit_has_real_trigger_comparison(self):
        records = recap.enrich(self.records, self.tables)
        technical = [r for r in records if r['meta']['exit_explanation']['kind'] == 'technical_stop']
        self.assertEqual(len(technical), 9)
        for r in technical:
            x = r['meta']['exit_explanation']
            self.assertTrue(x['trigger_close'] <= x['stop_price'] if r['meta']['direction'] == 'long'
                            else x['trigger_close'] >= x['stop_price'])

    def test_risk_and_rollover_are_not_reported_as_stop_losses(self):
        records = recap.enrich(self.records, self.tables)
        reasons = [r['meta']['exit_explanation'] for r in records]
        self.assertEqual(sum(x['kind'] == 'risk_cluster' for x in reasons), 7)
        self.assertEqual(sum(x['kind'] == 'forced_margin' for x in reasons), 1)
        roll = next(x for x in reasons if x['kind'] == 'rollover')
        self.assertIn('MA611.CZCE', roll['evidence'])
        self.assertIn('未开仓', roll['evidence'])
        for x in reasons:
            if x['kind'] != 'technical_stop':
                self.assertIsNone(x['stop_price'])

    def test_unknown_reason_is_rejected(self):
        records = copy.deepcopy(self.records)
        records[0]['meta']['exit_reason'] = 'unrecognized_exit'
        with self.assertRaises(ValueError):
            recap.enrich(records, self.tables)

    def test_ambiguous_execution_anchor_is_rejected(self):
        tables = copy.deepcopy(self.tables)
        tables['anchors'] = recap.pd.concat([tables['anchors'], tables['anchors']], ignore_index=True)
        with self.assertRaisesRegex(ValueError, 'unique.*anchor'):
            recap.enrich(self.records, tables)

    def test_wrong_trigger_line_is_rejected(self):
        tables = copy.deepcopy(self.tables)
        mask = tables['weekly'].vt_symbol.eq('ru2605.SHFE') & tables['weekly'].date.eq('2026-03-20')
        tables['weekly'].loc[mask, 'stop_price'] = 1
        with self.assertRaisesRegex(ValueError, 'trigger'):
            recap.enrich(self.records, tables)

    def test_changed_fill_price_is_rejected(self):
        tables = copy.deepcopy(self.tables)
        tables['fills'].loc[tables['fills'].trade_id.eq('BACKTESTING.8'), 'price'] += 1
        with self.assertRaisesRegex(ValueError, 'fill price'):
            recap.enrich(self.records, tables)

    def test_closed_output_path_cannot_overwrite_prior_recap(self):
        with self.assertRaises(ValueError):
            recap.require_output(recap.SOURCE)
        with self.assertRaises(ValueError):
            recap.require_output(recap.OUTPUT.parent / 'other_line')


if __name__ == '__main__':
    unittest.main()
