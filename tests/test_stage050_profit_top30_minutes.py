from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import subprocess
import re
import tempfile
from unittest.mock import patch
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'research/lines/futures_trend_winner_trade_forensics/tools'


class ProfitMinuteTest(unittest.TestCase):
    def target(self):
        path = TOOLS / 'stage050_enrich_profit_top30_minutes.py'
        self.assertTrue(path.exists(), 'Missing profit-top30 minute enrichment entrypoint')
        if str(TOOLS) not in sys.path:
            sys.path.insert(0, str(TOOLS))
        import stage050_enrich_profit_top30_minutes
        return stage050_enrich_profit_top30_minutes

    def test_period_hint_discloses_partial_top30_data_instead_of_tail_only(self):
        module = self.target()
        page = module.atlas._html([], {'intraday_top_selection': {'count':60}})
        function = re.search(r'function updatePeriodNote\(meta\)\{.*?(?=\nfunction)', page).group(0)
        code = """
        const summary={intraday_top_selection:{count:60}};
        const selectedPeriods=new Set(['intraday']);
        const note={innerHTML:''};
        const document={querySelector:()=>({classList:{toggle(){}}}), getElementById:()=>note};
        """ + function + """
        updatePeriodNote({draw_intraday:1,intraday_selection:'空头盈利涨跌幅Top30 · 第2名',missing_15m_dates:['2020-01-02']});
        console.log(note.innerHTML);
        updatePeriodNote({draw_intraday:0,missing_15m_dates:[]});console.log(note.innerHTML);
        """
        result = subprocess.run(['node','-e',code],capture_output=True,text=True,check=True)
        self.assertIn('第2名',result.stdout)
        self.assertIn('缺',result.stdout)
        self.assertNotIn('切回尾部',result.stdout)

    def test_selects_each_direction_by_price_not_money_or_input_order(self):
        module = self.target()
        rows = [
            {'open_trade_id': 'L1', 'result_type': 'profit', 'direction': 'long', 'price_change_pct': 20, 'realized_pnl': 1, 'entry_date': '2021-01-01'},
            {'open_trade_id': 'L2', 'result_type': 'profit', 'direction': 'long', 'price_change_pct': 2, 'realized_pnl': 9999, 'entry_date': '2021-01-01'},
            {'open_trade_id': 'S1', 'result_type': 'profit', 'direction': 'short', 'price_change_pct': -25, 'realized_pnl': 1, 'entry_date': '2021-01-01'},
            {'open_trade_id': 'S2', 'result_type': 'profit', 'direction': 'short', 'price_change_pct': -3, 'realized_pnl': 9999, 'entry_date': '2021-01-01'},
            {'open_trade_id': 'loss', 'result_type': 'loss', 'direction': 'long', 'price_change_pct': -40, 'realized_pnl': -999, 'entry_date': '2021-01-01'},
        ]
        records = [{'meta': row} for row in rows]
        before = copy.deepcopy(records)
        selection = module.select_profit_top(records, count=1)
        self.assertEqual(set(selection), {'L1', 'S1'})
        self.assertEqual(selection['S1']['gain_pct'], 25)
        self.assertEqual(module.select_profit_top(list(reversed(records)), count=1), selection)
        self.assertEqual(records, before)

    def test_top_count_is_not_percent_and_ties_are_deterministic(self):
        module = self.target()
        records = [{'meta': {'open_trade_id': f'{d}{i:02}', 'result_type': 'profit', 'direction': d,
                            'price_change_pct': 5 if d == 'long' else -5, 'entry_date': '2021-01-01'}}
                   for d in ['long', 'short'] for i in range(35)]
        picked = module.select_profit_top(list(reversed(records)))
        self.assertEqual(len(picked), 60)
        self.assertEqual(picked['long00']['rank'], 1)
        self.assertEqual(picked['short29']['rank'], 30)
        self.assertNotIn('long30', picked)

    def test_minute_aggregation_rejects_incomplete_buckets(self):
        module = self.target()
        times = list(pd.date_range('2021-01-04 09:00', periods=30, freq='min'))
        frame = pd.DataFrame({'bar_datetime': times, 'open': range(1, 31), 'high': range(2, 32),
                              'low': range(30), 'close': range(1, 31), 'volume': 1})
        frame = frame.drop(index=20)
        result = module.aggregate_local_minutes(frame, 'rb2105.SHFE')
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0][['open','high','low','close','volume']].tolist(), [1, 16, 0, 15, 15])

    def test_reader_preserves_all_completed_rows_when_replay_clock_jumps(self):
        module = self.target()
        self.assertTrue(hasattr(module, 'completed_serial_rows'), 'Replay reader must collect every completed row')
        serial = pd.DataFrame({'id':[40,41,42,43,44], 'datetime':[1,2,3,4,5], 'open':[10]*5})
        seen = {40}
        result = module.completed_serial_rows(serial, seen)
        self.assertEqual(result['id'].tolist(), [41,42,43])
        self.assertNotIn(44, seen)
        self.assertTrue(module.completed_serial_rows(serial, seen).empty)

    def test_expired_contract_final_candle_is_read_only_after_replay_passes_close(self):
        module = self.target()
        self.assertTrue(hasattr(module,'terminal_completed_row'), 'Last delivery-day bar has no successor')
        stamp=pd.Timestamp('2025-08-29 14:45',tz='Asia/Shanghai').value
        serial=pd.DataFrame({'id':[1,2], 'datetime':[stamp-900_000_000_000,stamp], 'open':[10,11]})
        self.assertTrue(module.terminal_completed_row(serial,{1},pd.Timestamp('2025-08-29 14:59')).empty)
        final=module.terminal_completed_row(serial,{1},pd.Timestamp('2025-08-29 15:00'))
        self.assertEqual(final['id'].tolist(),[2])

    def test_present_night_session_must_start_at_2100(self):
        module=self.target()
        times=pd.to_datetime(['2021-01-04 '+t for t in sorted(module.DAY_SLOTS)]+['2021-01-03 22:30','2021-01-03 22:45'])
        frame=pd.DataFrame({'bar_datetime':times,'open':10,'high':11,'low':9,'close':10,'volume':1})
        self.assertIn('night_session_start_missing',module.day_issues(frame))

    def test_historical_sessions_reject_missing_night_but_respect_known_exceptions(self):
        module=self.target()
        self.assertTrue(hasattr(module,'expected_night_slots'), 'Night completeness needs historical calendar')
        calendar=list(pd.bdate_range('2019-12-01','2020-05-08'))
        self.assertEqual(module.expected_night_slots('MA005.CZCE',pd.Timestamp('2019-12-26'),calendar),{'22:30','22:45'})
        self.assertEqual(len(module.expected_night_slots('MA005.CZCE',pd.Timestamp('2019-12-10'),calendar)),10)
        self.assertEqual(len(module.expected_night_slots('MA005.CZCE',pd.Timestamp('2019-12-12'),calendar)),8)
        self.assertEqual(module.expected_night_slots('sp2009.SHFE',pd.Timestamp('2020-04-01'),calendar),set())
        self.assertEqual(module.expected_night_slots('AP101.CZCE',pd.Timestamp('2020-05-08'),calendar),set())
        holiday_cal=list(pd.to_datetime(['2021-04-02','2021-04-06','2021-04-07']))
        self.assertEqual(module.expected_night_slots('rb2110.SHFE',pd.Timestamp('2021-04-06'),holiday_cal),set())
        self.assertEqual(len(module.expected_night_slots('rb2110.SHFE',pd.Timestamp('2021-04-07'),holiday_cal)),8)
        times=pd.to_datetime(['2021-04-07 '+t for t in sorted(module.DAY_SLOTS)])
        frame=pd.DataFrame({'bar_datetime':times,'open':10,'high':11,'low':9,'close':10,'volume':1})
        self.assertIn('night_session_slots_missing', module.day_issues(frame,expected_night={'21:00','21:15'}))

    def test_modified_cached_base_is_rejected(self):
        module=self.target()
        self.assertTrue(hasattr(module,'validate_base'), 'Must check actual base bytes not self-reported identity')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'base.json'
            path.write_text('{"records":[],"summary":{}}')
            valid=module.atlas._sha256(path)
            with patch.object(module,'BASE_JSON_SHA',valid):
                self.assertEqual(module.validate_base(path)['records'],[])
                path.write_text('{"records":[1],"summary":{}}')
                with self.assertRaisesRegex(RuntimeError,'fingerprint'):
                    module.validate_base(path)

    def test_download_padding_cannot_replace_complete_cache_with_partial_day(self):
        module = self.target()
        self.assertTrue(hasattr(module,'merge_completed_days'), 'Preserve complete cached days at replay boundaries')
        clock=sorted(module.DAY_SLOTS)
        full=pd.DataFrame({'bar_datetime':pd.to_datetime(['2021-01-04 '+t for t in clock]),'trading_day':pd.Timestamp('2021-01-04'),
                           'vt_symbol':'rb2105.SHFE','open':10,'high':11,'low':9,'close':10,'volume':1})
        partial=full.iloc[:-1].assign(close=11)
        result=module.merge_completed_days(full,partial)
        self.assertEqual(len(result),15)
        self.assertTrue(result.close.eq(10).all())
        replaced=module.merge_completed_days(partial,full)
        self.assertEqual(len(replaced),15)
        self.assertTrue(replaced.close.eq(10).all())

    def test_daily_session_gaps_cannot_be_called_complete(self):
        module = self.target()
        clock = ['09:00','09:15','09:30','09:45','10:00','10:30','10:45','11:00','11:15','13:30','13:45','14:00','14:15','14:30','14:45']
        full = pd.DataFrame({'bar_datetime': pd.to_datetime(['2021-01-04 '+t for t in clock]), 'open': 10, 'high': 11, 'low': 9, 'close': 10, 'volume': 1})
        self.assertEqual(module.day_issues(full), [])
        self.assertIn('day_session_slots_missing', module.day_issues(full.drop(index=4)))
        self.assertIn('invalid_ohlcv', module.day_issues(full.assign(high=8)))

    def test_night_session_gap_is_detected_without_inventing_holiday_night(self):
        module = self.target()
        clock = ['09:00','09:15','09:30','09:45','10:00','10:30','10:45','11:00','11:15','13:30','13:45','14:00','14:15','14:30','14:45']
        times = pd.to_datetime(['2021-01-04 '+t for t in clock] + ['2021-01-01 '+t for t in ['21:00','21:15','21:45','22:00','22:15','22:30','22:45']])
        frame = pd.DataFrame({'bar_datetime': times, 'open':10,'high':11,'low':9,'close':10,'volume':1})
        self.assertIn('night_session_internal_gap', module.day_issues(frame))

    def test_enrichment_keeps_daily_and_trade_data_and_hides_ma_warmup(self):
        module = self.target()
        clock = ['09:00','09:15','09:30','09:45','10:00','10:30','10:45','11:00','11:15','13:30','13:45','14:00','14:15','14:30','14:45']
        dates = pd.bdate_range('2021-01-04', periods=5)
        times = pd.to_datetime([d.strftime('%Y-%m-%d')+' '+t for d in dates for t in clock])
        bars = pd.DataFrame({'bar_datetime': times, 'trading_day': [d for d in dates for t in clock], 'vt_symbol':'AP105.CZCE', 'open':10,'high':11,'low':9,'close':10,'volume':1})
        record = {'meta': {'open_trade_id':'L1', 'intraday_start':'2021-01-07','intraday_end':'2021-01-08','draw_intraday':0,'entry_price':10,'weighted_exit_price':12,'price_change_pct':20,'missing_15m_dates':[]},
                  'daily': {'date':['2021-01-07','2021-01-08'],'x':[100.5,101.5],'source':['AP105.CZCE']*2,'close':[999,888]},
                  'weekly':{'close':[999]},'intraday':{}}
        original=copy.deepcopy(record)
        result, audit = module.enrich_record(record, bars, {'rank':1,'direction':'long','gain_pct':20})
        self.assertEqual(record, original)
        self.assertEqual(result['daily'], original['daily'])
        self.assertEqual(result['weekly'], original['weekly'])
        self.assertEqual(result['meta']['price_change_pct'], 20)
        self.assertEqual(len(result['intraday']['x']), 30)
        self.assertEqual(result['intraday']['ma40'][0], 10)
        self.assertEqual(result['intraday']['trading_day'][0], '2021-01-07')
        self.assertTrue(all(100 < x < 102 for x in result['intraday']['x']))
        self.assertTrue(all(row['status'] == 'covered' for row in audit))

    def test_missing_visible_day_is_audited_not_filled(self):
        module = self.target()
        record = {'meta': {'open_trade_id':'L1','intraday_start':'2021-01-04','intraday_end':'2021-01-04','draw_intraday':0},
                  'daily':{'date':['2021-01-04'],'x':[0.5],'source':['rb2105.SHFE']}, 'intraday':{}}
        bars=pd.DataFrame(columns=['bar_datetime','trading_day','vt_symbol','open','high','low','close','volume'])
        result,audit=module.enrich_record(record,bars,{'rank':1,'direction':'long','gain_pct':20})
        self.assertEqual(result['meta']['missing_15m_dates'], ['2021-01-04'])
        self.assertEqual(result['intraday']['x'], [])
        self.assertEqual(audit[0]['status'], 'missing')


if __name__ == '__main__':
    unittest.main()
