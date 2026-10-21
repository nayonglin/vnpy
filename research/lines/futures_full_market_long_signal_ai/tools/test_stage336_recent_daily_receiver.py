"""One offline receiver group; fake transport, real journal/files/date code."""
import asyncio
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


class ReceiverTiny(unittest.TestCase):
    def test_true_month_raw_receipts_unknown_clock_timeout_and_immutability(self):
        # Catches aligned multi-symbol subscriptions, lost F/retired contracts,
        # ns converted through float, natural-date guessing, R-as-completion,
        # overwriting batches, or unbounded failure loops.
        path=Path(__file__).with_name('stage336_recent_daily_receiver.py')
        self.assertTrue(path.exists(),'bounded daily receiver is not implemented')
        spec=importlib.util.spec_from_file_location('stage336_tiny',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        ns=int(datetime(2026,10,19,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp())*10**9
        frame=pd.DataFrame(dict(id=np.array([1,2],np.int64),datetime=np.array([ns,ns+1],np.int64),
            open=[100.,100.],high=[101.,101.],low=[99.,99.],close=[100.,100.],
            volume=[1000.,1000.],open_oi=[10.,10.],close_oi=[11.,11.]))
        class Clock:
            now=0.
            def monotonic(self):return self.now
            def time(self):return 1000.+self.now
        class API:
            def __init__(self,clock,fail_all=False):
                self.clock=clock;self.fail_all=fail_all;self.calls=[];self.catalog_calls=0;self.calendar_calls=0
            def query_quotes(self,**kw):
                self.catalog_calls+=1;self.query=kw
                return ['CFFEX.IF2611','CZCE.SR701','DCE.l2611F','GFEX.si2611','INE.sc2611','SHFE.cu2611','KQ.m@DCE.m']
            def get_trading_calendar(self,**kw):
                self.calendar_calls+=1
                return pd.DataFrame(dict(date=['2026-10-19','2026-10-20'],trading=[True,True]))
            def get_kline_serial(self,symbol,duration_seconds,data_length):
                self.calls.append((symbol,duration_seconds,data_length))
                if self.fail_all or symbol=='GFEX.si2611':
                    raise ConnectionError('usersecret passsecret https://provider.invalid/private-token')
                f=frame.copy(deep=True);f.attrs['ready']=symbol!='CFFEX.IF2611';return f
            def create_task(self,coro):
                asyncio.run(coro)
                return SimpleNamespace(done=lambda:True,exception=lambda:None,cancel=lambda:None)
            def is_serial_ready(self,f):return f.attrs['ready']
            def wait_update(self,deadline):self.clock.now+=1;return False
        limits=dict(batch_size=80,ready_timeout_seconds=2.,global_timeout_seconds=30.,
            max_consecutive_connection_errors=3,max_consecutive_unready_batches=3)
        prior=['DCE.m2610','SHFE.cu2611']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);clock=Clock();api=API(clock)
            journal=m.load_journal().ForwardJournal(root/'journal',{'receiver':'tiny-no-T0'})
            result=m.capture_from_api(api,prior,output=root/'batch',journal=journal,
                limits=limits,source_version='tiny',calendar_start='2026-10-16',calendar_end='2026-10-27',
                normalization_contract={},secrets=['usersecret','passsecret'],clock=clock)
            self.assertEqual(api.catalog_calls,1)
            self.assertEqual(api.query,dict(ins_class='FUTURE',exchange_id=sorted(m.EXCHANGES),expired=False))
            self.assertEqual(api.calendar_calls,1)
            self.assertIn('DCE.l2611F',result['catalog']['symbols'])
            self.assertEqual(result['catalog']['just_retired_symbols'],['DCE.m2610'])
            self.assertEqual(len(result['items']),7)
            self.assertTrue(all(isinstance(s,str) and d==86400 and n==35 for s,d,n in api.calls))
            self.assertEqual(result['items']['CFFEX.IF2611']['status'],'missing_timeout')
            self.assertEqual(result['items']['GFEX.si2611']['status'],'error')
            saved=(root/'batch'/'manifest.json').read_text()
            self.assertNotIn('usersecret',saved);self.assertNotIn('passsecret',saved)
            raw=m.read_json(result['items']['SHFE.cu2611']['raw']['path'])
            self.assertEqual(raw['rows'][1]['raw_ns'],ns+1)
            self.assertEqual(raw['rows'][1]['raw_datetime_type'],'int64')
            self.assertEqual(raw['units_status'],'provider_raw_units_unverified')
            self.assertTrue(journal.entries())
            before=api.catalog_calls
            with self.assertRaises(FileExistsError):
                m.capture_from_api(api,prior,output=root/'batch',journal=journal,limits=limits,
                    source_version='tiny',calendar_start='2026-10-16',calendar_end='2026-10-27',
                    normalization_contract={},secrets=[],clock=clock)
            self.assertEqual(api.catalog_calls,before)
            c=Clock();broken=API(c,fail_all=True)
            stopped=m.capture_from_api(broken,prior,output=root/'broken',journal=journal,limits=limits,
                source_version='tiny',calendar_start='2026-10-16',calendar_end='2026-10-27',
                normalization_contract={},secrets=['usersecret','passsecret'],clock=c)
            self.assertEqual(len(broken.calls),3)
            self.assertEqual(len(stopped['items']),7)
            self.assertTrue(any(r['status']=='not_attempted_circuit' for r in stopped['items'].values()))
            class FaultJournal:
                count=0
                def append(self,*args,**kw):
                    self.count+=1
                    if self.count==5:raise OSError('offline injected receipt write fault')
                    return journal.append(*args,**kw)
            c=Clock();partial=m.capture_from_api(API(c),prior,output=root/'partial',journal=FaultJournal(),
                limits=limits,source_version='tiny',calendar_start='2026-10-16',calendar_end='2026-10-27',
                normalization_contract={},secrets=[],clock=c)
            self.assertEqual(partial['items']['CZCE.SR701']['status'],'success')
            self.assertEqual(len(partial['items']),7)
            self.assertNotEqual(partial['items']['DCE.l2611F']['status'],'not_attempted_catalog_or_connection_failure')
        rows=m.raw_records(frame)
        context=dict(timestamp_semantics='tq_daily_midnight_label_calendar_v1',
            calendar={'2026-10-19':True,'2026-10-20':True},identity_map={'SHFE.cu2611':'SHFE.CU.202611'},
            session_evidence={'SHFE.cu2611':{'2026-10-19':dict(confirmed=True,
                session_end_at='2026-10-19T15:00:00+08:00',D_open_at='2026-10-19T21:00:00+08:00')}})
        mapped=m.normalize_record(rows[0],symbol='SHFE.cu2611',received_at='2026-10-20T03:00:00+08:00',
            fresh_ready=True,contract=context,end_inclusive='2026-10-20')
        self.assertEqual(mapped['trade_date'],'2026-10-19')
        self.assertEqual(mapped['source_completed_at'],'2026-10-19T07:00:00+00:00')
        self.assertEqual(mapped['completion_observed_at'],'2026-10-19T19:00:00+00:00')
        self.assertFalse(mapped['active']);self.assertEqual(mapped['vendor_finality'],'unknown')
        self.assertEqual(mapped.get('canonical_quality_status'),'unknown')
        self.assertEqual(mapped['native_values']['close_oi'],11.)
        not_ready=m.normalize_record(rows[0],symbol='SHFE.cu2611',received_at='2026-10-20T03:00:00+08:00',
            fresh_ready=False,contract=context,end_inclusive='2026-10-20')
        self.assertIsNone(not_ready['source_completed_at'])
        wrong=dict(context,identity_map={'SHFE.fu2701':'SHFE.FU.202601'})
        with self.assertRaises(ValueError):
            m.normalize_record(rows[0],symbol='SHFE.fu2701',received_at='2026-10-20T03:00:00+08:00',
                fresh_ready=True,contract=wrong,end_inclusive='2026-10-20')
        unknown=m.normalize_record(rows[1],symbol='SHFE.cu2611',received_at='2026-10-20T03:00:00+08:00',
            fresh_ready=True,contract=context,end_inclusive='2026-10-20')
        self.assertIsNone(unknown['trade_date']);self.assertIsNone(unknown['source_completed_at'])
        f=frame.copy();f['datetime']=f.datetime.astype(float)
        self.assertIsNone(m.raw_records(f)[0]['raw_ns'])


if __name__=='__main__':unittest.main()
