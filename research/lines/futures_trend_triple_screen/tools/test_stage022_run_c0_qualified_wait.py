import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('stage022_run_c0_qualified_wait',Path(__file__).with_name('stage022_run_c0_qualified_wait.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Recorder:
    def __init__(self):self.extra=set();self.files={}
    def record(self,path):
        path=Path(path).resolve();self.files[str(path)]={'sha256':module.sha256(path)}


class WaitResolverTests(unittest.TestCase):
    def test_signed_response_is_hashed_and_recorded_before_delivery(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);request={'requirements':[]};request['request_sha256']=module.canonical_request_sha256(request)
            data=root/'data.csv';data.write_text('data')
            receipt=root/'review_receipt.json';module.write_json(receipt,dict(schema='stage021_independent_minute_delivery_v1',
                independent_review=True,reviewer='independent',qualified_research_data=True,p0_findings=0,p1_findings=0,
                request_sha256=request['request_sha256'],data_path=str(data),data_sha256=module.sha256(data),
                source_fingerprints={str(data):module.sha256(data)}))
            folder=root/'wait'/('request_'+request['request_sha256']);folder.mkdir(parents=True)
            module.write_json(folder/'response.json',dict(schema='stage022_delivery_pointer_v1',
                request_sha256=request['request_sha256'],receipt_path=str(receipt),receipt_sha256=module.sha256(receipt)))
            recorder=Recorder();audit=[]
            resolver=module.FileWaitResolver(root/'wait',recorder,audit,0,clock=lambda:0,
                delivery_factory=lambda p,h:(p,h))
            delivery=resolver(request)
            self.assertEqual(delivery,(receipt.resolve(),module.sha256(receipt)))
            self.assertIn(str(data.resolve()),recorder.files)
            self.assertEqual(audit[-1]['status'],'qualified_delivery_pointer_accepted')
            self.assertTrue((folder/'request.json').is_file())
            fingerprint=json.loads((folder/'request_fingerprint.json').read_text())
            self.assertEqual(fingerprint['request_file_sha256'],module.sha256(folder/'request.json'))

    def test_wrong_response_scope_fails_before_receipt_or_data_are_used(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);request={'requirements':[]};request['request_sha256']=module.canonical_request_sha256(request)
            folder=root/('request_'+request['request_sha256']);folder.mkdir()
            module.write_json(folder/'response.json',dict(schema='stage022_delivery_pointer_v1',request_sha256='b'*64,
                receipt_path='/missing/receipt.json',receipt_sha256='c'*64))
            resolver=module.FileWaitResolver(root,Recorder(),[],0,clock=lambda:0)
            with self.assertRaisesRegex(ValueError,'response_request_mismatch'):
                resolver(request)

    def test_wait_budget_stops_without_retry_and_preserves_request(self):
        with tempfile.TemporaryDirectory()as tmp:
            ticks=iter([0,1801]);root=Path(tmp);audit=[];request={'requirements':[]}
            request['request_sha256']=module.canonical_request_sha256(request)
            resolver=module.FileWaitResolver(root,Recorder(),audit,0,clock=lambda:next(ticks),sleep=lambda _:None)
            with self.assertRaisesRegex(TimeoutError,'wait_budget'):
                resolver(request)
            self.assertTrue((root/('request_'+request['request_sha256'])/'request.json').exists())
            self.assertEqual(audit[-1]['status'],'wait_budget_exceeded')

    def test_changed_payload_same_request_hash_refused(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);folder=root/('request_'+'a'*64);folder.mkdir()
            module.write_json(folder/'request.json',{'request_sha256':'a'*64,'requirements':['old']})
            resolver=module.FileWaitResolver(root,Recorder(),[],0,clock=lambda:0)
            with self.assertRaisesRegex(ValueError,'existing_request_payload_changed'):
                resolver({'request_sha256':'a'*64,'requirements':['new']})

    def test_anchor859_never_grants_full_and_absent016_key_never_admitted(self):
        import pandas as pd
        group=pd.DataFrame(dict(bar_datetime=pd.to_datetime(['2026-10-14 09:00']),
            minute_source=['stage859_tqsdk_backtest']))
        demand=pd.DataFrame([dict(vt_symbol='AP701.CZCE',execution_trade_date='2026-10-14',requirement_kind='anchor')])
        absent=pd.Timestamp('2026-10-14 09:01')
        full,anchor,audit=module.inherited_qualification_predicates({'AP701.CZCE':group},
            {('AP701.CZCE',absent)},demand,pd.to_datetime(['2026-10-13','2026-10-14']))
        self.assertFalse(full('AP701.CZCE',pd.Timestamp('2026-10-14 09:00')))
        self.assertTrue(anchor('AP701.CZCE',pd.Timestamp('2026-10-14 09:00')))
        self.assertFalse(full('AP701.CZCE',absent))
        self.assertEqual(audit['extra_anchor_only859_keys'],1)

    def test_original_candidate_and_model_helpers_remain_identical(self):
        import ast
        original=ast.parse(module.SOURCE001.read_text());current=ast.parse(Path(module.__file__).read_text())
        before={n.name:ast.dump(n)for n in original.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        after={n.name:ast.dump(n)for n in current.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for name in ['WeeklyLookup','build_research_strategy','capture_formal_profile','capture_actual_settings',
            'capture_engine','model_runtime_smoke','configure_runtime','InputRecorder']:
            self.assertEqual(before[name],after[name],name)
        self.assertEqual(module.sha256(module.SOURCE001),module.SOURCE001_SHA)

    def test_whole_run_deadline_escapes_exception_handlers_and_restores_timer(self):
        import signal,time
        previous=signal.getsignal(signal.SIGALRM)
        with self.assertRaises(module.WholeRunBudgetExceeded):
            with module.whole_run_budget(.01):
                try:time.sleep(.1)
                except Exception:self.fail('hard deadline was swallowed as ordinary Exception')
        self.assertEqual(signal.getsignal(signal.SIGALRM),previous)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.,0.))


if __name__=='__main__':unittest.main()
