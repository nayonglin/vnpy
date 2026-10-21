"""Four simulated transport behaviors. No HTTP, market data, fits or old suite."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error

p=Path(__file__).with_name('stage250_raw_spot_archive.py');s=importlib.util.spec_from_file_location('tiny250',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


class Clock:
    def __init__(self):self.t=0.;self.lock=threading.Lock()
    def now(self):
        with self.lock:return self.t
    def sleep(self,delay):
        with self.lock:self.t+=delay


def protocol(root,n=6):
    dates=[f'2020-01-{i+1:02d}' for i in range(n)]
    return dict(schema='stage249_raw_spot_archive_protocol_v1',dates=dates,date_count=n,reused={},
        url_template='https://www.100ppi.com/sf/day-{date}.html',
        HTTP=dict(max_parallel=2,global_min_start_interval_seconds=.75,timeout_seconds=15,max_body_bytes=131072,
            attempts_per_date=1,max_new_requests_per_invocation=250,stop_new_submissions_on_HTTP=[403,429],
            stop_new_submissions_after_consecutive_failed_completions=3,no_retry=True,no_latest_fallback=True),
        output_contract=dict(path=str(root),body_subdir='raw',metadata_subdir='rows',batch_subdir='batches'),
        new_fit=0,new_cash=0,cumulative_fit=439,cumulative_cash=234)


def response(url,status=200,body=b'raw'):
    return dict(http_status=status,final_url=url,body=body,bytes_received=len(body),truncated=False,
                redirect_location=None,redirect_followed=False,transport_error=None)


class TestStage250(unittest.TestCase):
    def function(self,name):
        self.assertTrue(callable(getattr(m,name,None)),'new bounded archive behavior is not implemented')
        return getattr(m,name)

    def test_reuse_pending_never_refetched_and_exclusive_lock(self):
        run=self.function('run_batch')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=protocol(root,4);days=p['dates'];rows=root/'rows';rows.mkdir()
            p['reused'][days[0]]=dict(body=dict(path='/never/open/raw',bytes=3,sha256='accepted'),source_receipt='accepted.json',http_status=200)
            (rows/(days[1]+'.started.json')).write_text(json.dumps(dict(date=days[1],url='old',batch_id='old',attempts=1)))
            calls=[];clock=Clock()
            result=run(p,'batch001',250,transport=lambda u,h,e:(calls.append(u) or response(u)),sleep=clock.sleep,monotonic=clock.now)
            self.assertEqual(result['network_attempts'],2);self.assertEqual(len(calls),2)
            self.assertEqual(json.loads((rows/(days[0]+'.json')).read_text())['attempts'],0)
            self.assertEqual(json.loads((rows/(days[1]+'.json')).read_text())['state'],'attempted_unknown')
            again=run(p,'batch002',250,transport=lambda *a:self.fail('prior attempt fetched again'),sleep=clock.sleep,monotonic=clock.now)
            self.assertEqual(again['network_attempts'],0)
            with self.assertRaises(FileExistsError):run(p,'batch002',250,transport=lambda *a:self.fail('freshdir guard failed'))
            with m.archive_lock(root):
                with self.assertRaises(RuntimeError):
                    with m.archive_lock(root):pass

    def test_start_spacing_and_two_inflight_with_start_record(self):
        run=self.function('run_batch')
        # A slow durable start must not consume spacing between dispatches.
        clock=Clock();gate=m.StartGate(.75,threading.Event(),clock.sleep,clock.now,False);dispatch_times=[]
        def slow_durable_start(stamp):
            if not dispatch_times:clock.sleep(.9)
        for _ in range(2):
            self.assertTrue(gate.start(slow_durable_start))
            dispatch_times.append(clock.now())  # Simulated transport entry.
        self.assertGreaterEqual(dispatch_times[1],dispatch_times[0]+.75)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=protocol(root,8);clock=Clock();active=0;peak=0;times=[];guard=threading.Lock()
            def fetch(url,settings,event):
                nonlocal active,peak
                day=url.rsplit('day-',1)[1][:-5]
                self.assertTrue((root/'rows'/(day+'.started.json')).is_file())
                with guard:
                    active+=1;peak=max(peak,active)
                    times.append(json.loads((root/'rows'/(day+'.started.json')).read_text())['request_start_monotonic'])
                time.sleep(.01)
                with guard:active-=1
                return response(url)
            result=run(p,'batch001',5,transport=fetch,sleep=clock.sleep,monotonic=clock.now)
            self.assertEqual(result['network_attempts'],5);self.assertLessEqual(peak,2)
            self.assertTrue(all(b-a>=.75 for a,b in zip(sorted(times),sorted(times)[1:])))
            self.assertEqual(result['remaining_unattempted'],3)

    def test_http_hard_stop_and_three_completed_failures(self):
        run=self.function('run_batch')
        for status in [403,429,500]:
            with self.subTest(status=status),tempfile.TemporaryDirectory() as folder:
                p=protocol(Path(folder),12);clock=Clock();calls=[]
                def fetch(url,settings,event):
                    calls.append(url)
                    return response(url,status,b'error body')
                result=run(p,'batch001',250,transport=fetch,sleep=clock.sleep,monotonic=clock.now)
                self.assertTrue(result['stopped_early'])
                if status in [403,429]:self.assertLessEqual(len(calls),2);self.assertIn(str(status),result['stop_reason'])
                else:self.assertLessEqual(len(calls),4);self.assertIn('consecutive',result['stop_reason'])
                self.assertEqual(len(calls),result['network_attempts'])
                self.assertEqual(result['new_cash'],0)

    def test_error_body_truncation_and_redirect_are_preserved(self):
        fetch=self.function('http_once');settings=protocol(Path('/not_used'))['HTTP'];settings['max_body_bytes']=4
        class R(io.BytesIO):
            status=200;headers={'Content-Type':'text/html'}
            def geturl(self):return 'https://www.100ppi.com/sf/day-2020-01-01.html'
        class Opener:
            def __init__(self,status):self.status=status;self.calls=0
            def open(self,request,timeout):
                self.calls+=1
                if self.status!=200:raise urllib.error.HTTPError(request.full_url,self.status,'test',{'Location':'https://other.invalid/'},io.BytesIO(b'error'))
                return R(b'abcdef')
        for status in [200,302,429]:
            with self.subTest(status=status):
                event=threading.Event();opener=Opener(status);r=fetch('https://www.100ppi.com/sf/day-2020-01-01.html',settings,event,opener=opener)
                self.assertEqual(opener.calls,1);self.assertEqual(r['body'],b'abcd' if status==200 else b'erro')
                self.assertTrue(r['truncated']);self.assertFalse(r['redirect_followed'])
                self.assertEqual(r['http_status'],status);self.assertEqual(event.is_set(),status==429)
        self.assertIsNone(m.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://other.invalid/'))


if __name__=='__main__':unittest.main()
