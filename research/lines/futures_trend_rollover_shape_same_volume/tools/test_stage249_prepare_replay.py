"""交易日所需分钟分段、离线补丁证据回归；不接网络或回测引擎。"""
from __future__ import annotations
from datetime import date, datetime
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

class Stage249Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module_path = Path(__file__).with_name('stage249_prepare_replay.py')

    def module(self):
        self.assertTrue(self.module_path.is_file(), 'Stage249 preparation module must exist')
        import stage249_prepare_replay
        return stage249_prepare_replay

    def test_monday_au_contains_friday_evening_saturday_early_and_monday_day(self):
        m = self.module()
        tasks = m.tasks_for_trade_day('au2012.SHFE', '2020-06-08', ['2020-06-05', '2020-06-08'])
        self.assertEqual([(x['natural_date'], x['start'], x['end_exclusive']) for x in tasks], [
            ('2020-06-05','21:00','24:00'), ('2020-06-06','00:00','02:30'),
            ('2020-06-08','09:00','10:15'), ('2020-06-08','10:30','11:30'), ('2020-06-08','13:30','15:00')])
        self.assertEqual(sum(len(m.task_moments(t)) for t in tasks), 555)

    def test_copper_midnight_ends_at_0059(self):
        m = self.module()
        tasks = m.tasks_for_trade_day('cu2012.SHFE','2020-06-09',['2020-06-08','2020-06-09'])
        early = tasks[1]
        self.assertEqual((early['natural_date'],early['start'],early['end_exclusive']),('2020-06-09','00:00','01:00'))
        self.assertEqual(max(m.task_moments(early)),datetime(2020,6,9,0,59))

    def test_holiday_first_session_has_no_preholiday_night(self):
        m = self.module()
        tasks = m.tasks_for_trade_day('au2612.SHFE','2026-10-09',['2026-09-30','2026-10-09'])
        self.assertEqual({t['natural_date'] for t in tasks},{'2026-10-09'})
        self.assertEqual(sum(len(m.task_moments(t)) for t in tasks),225)

    def test_2020_night_pause_and_resume(self):
        m = self.module()
        self.assertEqual(len(m.tasks_for_trade_day('fu2009.SHFE','2020-05-06',['2020-04-30','2020-05-06'])),3)
        self.assertEqual(len(m.tasks_for_trade_day('fu2009.SHFE','2020-05-07',['2020-05-06','2020-05-07'])),4)
        self.assertEqual(len(m.tasks_for_trade_day('fu2005.SHFE','2020-02-04',['2020-02-03','2020-02-04'])),3)

    def test_day_only_has_no_night_even_on_monday(self):
        m = self.module()
        self.assertEqual(len(m.tasks_for_trade_day('AP010.CZCE','2020-06-08',['2020-06-05','2020-06-08'])),3)

    def test_calendar_missing_target_or_predecessor_fails_closed(self):
        m = self.module()
        for calendar in [['2020-06-08'],['2020-06-05']]:
            with self.assertRaises(ValueError):
                m.tasks_for_trade_day('au2012.SHFE','2020-06-08',calendar)

    def task(self):
        return {'vt_symbol':'au2012.SHFE','trading_day':'2020-06-08','natural_date':'2020-06-06',
                'start':'00:00','end_exclusive':'00:03','session':'early'}

    def bars(self):
        return pd.DataFrame({'vt_symbol':['au2012.SHFE']*3,
            'bar_datetime':pd.date_range('2020-06-06 00:00',periods=3,freq='min'),
            'open':[100.,101.,102.], 'high':[101.,102.,103.], 'low':[99.,100.,101.],
            'close':[100.,101.,102.], 'volume':[1.,2.,3.], 'open_oi':[20.,21.,22.], 'close_oi':[21.,22.,23.]})

    def test_fragment_accepts_saturday_without_daytime(self):
        m = self.module()
        proof = m.validate_fragment(self.bars(), self.task())
        self.assertEqual(proof['rows'],3)
        self.assertEqual(proof['last_minute'],'2020-06-06 00:02:00')

    def test_missing_duplicate_wrong_day_and_nonminute_fail(self):
        m = self.module()
        variants = [self.bars().iloc[:2], pd.concat([self.bars(),self.bars().iloc[:1]])]
        wrong_day=self.bars(); wrong_day['bar_datetime']+=pd.Timedelta(days=1); variants.append(wrong_day)
        seconds=self.bars(); seconds['bar_datetime']+=pd.Timedelta(seconds=1); variants.append(seconds)
        for frame in variants:
            with self.assertRaises(ValueError): m.validate_fragment(frame,self.task())

    def test_invalid_ohlcv_symbol_and_timezone_fail(self):
        m = self.module()
        variants=[]
        for column,value in [('high',90.),('volume',-1.),('close',float('nan')),('vt_symbol','cu2012.SHFE')]:
            frame=self.bars(); frame.loc[0,column]=value; variants.append(frame)
        frame=self.bars();frame['bar_datetime']=frame.bar_datetime.dt.tz_localize('Asia/Shanghai');variants.append(frame)
        for frame in variants:
            with self.assertRaises(ValueError): m.validate_fragment(frame,self.task())

    def test_tasks_csv_json_normalize_and_overlap_fail(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); task=self.task()
            (root/'tasks.json').write_text(json.dumps([task]))
            pd.DataFrame([task]).to_csv(root/'tasks.csv',index=False)
            self.assertEqual(m.read_tasks(root/'tasks.json'),m.read_tasks(root/'tasks.csv'))
            (root/'tasks.json').write_text(json.dumps([task,task]))
            with self.assertRaisesRegex(ValueError,'duplicate|overlap'): m.read_tasks(root/'tasks.json')

    def test_snapshot_bounds_require_preceding_bar_and_completed_end(self):
        m=self.module();task=self.task()
        m.validate_serial_bounds(self.bars(),task,datetime(2020,6,7,8),earliest=datetime(2020,6,5,23,59),latest=datetime(2020,6,6,2,29))
        for first,last in [(datetime(2020,6,6),datetime(2020,6,6,2,29)),(datetime(2020,6,5,23,59),datetime(2020,6,8))]:
            with self.assertRaises(ValueError):m.validate_serial_bounds(self.bars(),task,datetime(2020,6,7,8),earliest=first,latest=last)

    def test_patch_roundtrip_and_tamper_rejected(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            patch=m.save_patch(Path(tmp),[self.task()],self.bars(),{'kind':'fixture','source_sha256':'abc'})
            proof=m.verify_patch(Path(patch['parquet']),Path(patch['proof']))
            self.assertEqual(proof['rows'],3)
            with Path(patch['parquet']).open('ab') as f:f.write(b'tamper')
            with self.assertRaisesRegex(ValueError,'sha256'):m.verify_patch(Path(patch['parquet']),Path(patch['proof']))

    def test_extract_filters_unrequested_future_and_assigns_trading_day(self):
        m=self.module(); future=self.bars().copy();future['bar_datetime']+=pd.Timedelta(days=1)
        rows=m.extract_fragments(pd.concat([self.bars(),future]),[self.task()])
        self.assertEqual(len(rows),3)
        self.assertEqual(set(rows.trading_day),{'2020-06-08'})
        self.assertEqual(set(rows.bar_date),{'2020-06-06'})

if __name__=='__main__':unittest.main()

class DownloadInterfaceTests(unittest.TestCase):
    def test_offline_source_cli_writes_only_requested_fragment_and_reuses_it(self):
        import subprocess
        path=Path(__file__).with_name('stage249_download_minutes.py')
        self.assertTrue(path.is_file(),'Stage249 downloader module must exist')
        fixture=Stage249Tests()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'tasks.json').write_text(json.dumps([fixture.task()]))
            fixture.bars().to_parquet(root/'source.parquet')
            command=[sys.executable,str(path),'--tasks',str(root/'tasks.json'),'--output-dir',str(root/'out'),
                     '--source-parquet',str(root/'source.parquet')]
            first=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(first.returncode,0,first.stderr)
            summary=json.loads((root/'out/progress.json').read_text())
            self.assertEqual(summary['status'],'complete');self.assertEqual(summary['segments'],1)
            proof=json.loads(Path(summary['patches'][0]['proof']).read_text())
            self.assertEqual(proof['rows'],3);self.assertEqual(proof['source']['kind'],'offline_parquet')
            second=subprocess.run(command,text=True,capture_output=True)
            self.assertEqual(second.returncode,0,second.stderr)

    def test_no_download_flag_does_not_attempt_credentials_or_network(self):
        import subprocess
        path=Path(__file__).with_name('stage249_download_minutes.py')
        self.assertTrue(path.is_file(),'Stage249 downloader module must exist')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'tasks.json').write_text(json.dumps([Stage249Tests().task()]))
            result=subprocess.run([sys.executable,str(path),'--tasks',str(root/'tasks.json'),
                '--output-dir',str(root/'out')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'plan_only')
            self.assertFalse((root/'out').exists())

class ProvenanceTests(unittest.TestCase):
    def test_calendar_contract_catches_helper_drift(self):
        import stage249_prepare_replay as m
        self.assertTrue(hasattr(m,'assert_session_contract'),'shared calendar cross-check required')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'helper.py'
            path.write_text('def session_minutes(*args):\n return []\n')
            tasks=m.tasks_for_trade_day('fu2009.SHFE','2020-06-08',['2020-06-05','2020-06-08'])
            with self.assertRaisesRegex(ValueError,'session_contract'):
                m.assert_session_contract(tasks,['2020-06-05','2020-06-08'],path)

    def test_cache_requires_matching_accepted_completed_source(self):
        import stage249_prepare_replay as m
        fixture=Stage249Tests();task=fixture.task()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'20200606.parquet';cache=root/'cache.csv'
            fixture.bars().to_parquet(source);fixture.bars().to_csv(cache,index=False)
            proof={'sha256':m.sha256(source),'all_cached_symbols':['au2012.SHFE'],
                   'snapshot_at':'2020-06-07T08:00:00','raw_serial_ranges':{'au2012.SHFE':{
                       'earliest':'2020-06-05 23:59:00','latest':'2020-06-06 02:29:00'}}}
            (root/'20200606_proof.json').write_text(json.dumps(proof))
            rows,missing=m.audit_cache(cache,[task],accepted_minute_dir=root)
            self.assertEqual(missing,[]);self.assertEqual(rows[0]['source_status'],'accepted_identical')
            changed=fixture.bars();changed.loc[0,'volume']=0;changed.to_csv(cache,index=False)
            rows,missing=m.audit_cache(cache,[task],accepted_minute_dir=root)
            self.assertEqual(len(missing),1);self.assertEqual(rows[0]['source_status'],'accepted_values_differ')

class DownloaderFailureTests(unittest.TestCase):
    def test_first_failed_snapshot_stops_worker_without_retry_storm(self):
        import subprocess
        fixture=Stage249Tests()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);first=fixture.task();second={**first,'natural_date':'2020-06-07'}
            (root/'tasks.json').write_text(json.dumps([first,second]))
            frame=fixture.bars();frame['bar_datetime']+=pd.Timedelta(days=3);frame.to_parquet(root/'source.parquet')
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('stage249_download_minutes.py')),
                '--tasks',str(root/'tasks.json'),'--output-dir',str(root/'out'),'--source-parquet',str(root/'source.parquet')],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            progress=json.loads((root/'out/progress.json').read_text())
            self.assertEqual(len(progress['failures']),1,'one failure must stop this worker')
