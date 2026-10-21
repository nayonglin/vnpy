"""Frozen249 raw archive: one bounded batch, no retries, parsing or finance.

Request-start is durable before HTTP. Any previous attempt, including an
interrupted one, is never fetched again. Tests inject transport and time only.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import threading
import time
import urllib.error
import urllib.request

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage249_full_raw_spot_archive_protocol/protocol.json'
PROTOCOL_SHA='59a7622677e2d75ad989ff16db573a2d773d0c28616bf914c0cf7186514f8fea'


def utcnow():return datetime.now(timezone.utc).isoformat()


def binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def atomic_create(path,raw):
    """fsync then atomic, exclusive hard-link publication in the same directory."""
    path=Path(path);tmp=path.with_name('.'+path.name+'.'+str(os.getpid())+'.'+str(threading.get_ident())+'.tmp')
    try:
        with tmp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.link(tmp,path)  # Raises if an immutable final/start row already exists.
        fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if tmp.exists():tmp.unlink()


def save_json(path,value):
    atomic_create(path,(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())


@contextmanager
def archive_lock(root):
    """Kernel lock is released after crashes; no stale-lock deletion/retry logic."""
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/'.archive.lock').open('a+b') as f:
        try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc:raise RuntimeError('archive_already_running') from exc
        try:yield
        finally:fcntl.flock(f.fileno(),fcntl.LOCK_UN)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,new_url):return None


def http_once(url,settings,stop_event,*,opener=None):
    """One HTTP transaction, including error bodies; never follow 3xx or retry."""
    result=dict(http_status=None,final_url=url,headers={},body=None,bytes_received=None,truncated=None,
                redirect_location=None,redirect_followed=False,transport_error=None)
    client=opener if opener is not None else urllib.request.build_opener(NoRedirect())
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'text/html'})
    response=None
    try:
        try:response=client.open(request,timeout=settings['timeout_seconds'])
        except urllib.error.HTTPError as exc:
            response=exc;result['transport_error']=dict(type=type(exc).__name__,message=str(exc))
        status=int(response.status if hasattr(response,'status') else response.code)
        result['http_status']=status
        if status in settings['stop_new_submissions_on_HTTP']:stop_event.set()
        result['final_url']=response.geturl()
        headers={k:response.headers.get(k) for k in ('Content-Type','Content-Length','Date','Last-Modified','ETag','Location')}
        result['headers']=headers;result['redirect_location']=headers.get('Location') if 300<=status<400 else None
        cap=settings['max_body_bytes']
        try:
            raw=response.read(cap+1)  # One sentinel byte detects overflow; saved body never exceeds cap.
            result.update(body=raw[:cap],bytes_received=len(raw),truncated=len(raw)>cap)
        except Exception as exc:
            partial=getattr(exc,'partial',None)
            if isinstance(partial,bytes):result.update(body=partial[:cap],bytes_received=len(partial),truncated=len(partial)>cap)
            result['transport_error']=dict(type=type(exc).__name__,message=str(exc),phase='read_body')
    except Exception as exc:
        result['transport_error']=dict(type=type(exc).__name__,message=str(exc),phase='open_or_headers')
    finally:
        if response is not None:response.close()
    return result


class StartGate:
    def __init__(self,interval,stop_event,sleep,monotonic,prior_attempt):
        self.interval=float(interval);self.stop=stop_event;self.sleep=sleep;self.now=monotonic
        self.last=self.now() if prior_attempt else None;self.lock=threading.Lock()

    def start(self,write_start):
        with self.lock:
            if self.stop.is_set():return False
            if self.last is not None:
                wait=self.interval-(self.now()-self.last)
                if wait>0:self.sleep(wait)
            if self.stop.is_set():return False
            stamp=self.now();write_start(stamp)
            # Slow fsync must not consume the interval before HTTP dispatch.
            self.last=self.now()
            return True


def restore_rows(protocol,rows_dir,raw_dir):
    """Read metadata only; inherit nine accepted bindings without reading raw."""
    state={};recovered=0;reused=0
    for day in protocol['dates']:
        final=rows_dir/(day+'.json');started=rows_dir/(day+'.started.json');raw=raw_dir/(day+'.response')
        if final.exists():
            row=json.loads(final.read_text())
            if row.get('date')!=day:raise ValueError('existing_row_date_mismatch '+day)
            state[day]=row;continue
        if started.exists() or raw.exists():
            prior=json.loads(started.read_text()) if started.exists() else dict(date=day)
            row=dict(prior,state='attempted_unknown',attempts=1,reused=False,http_success=False,
                completed_at=utcnow(),error=dict(type='InterruptedAttempt',message='Durable request-start or orphan body without final row; never automatically fetch again'),
                quote_validity='not_assessed',body_unverified_path=str(raw) if raw.exists() else None)
            save_json(final,row);state[day]=row;recovered+=1;continue
        if day in protocol['reused']:
            ref=protocol['reused'][day]
            row=dict(date=day,url=protocol['url_template'].format(date=day),state='reused_binding',attempts=0,reused=True,
                body=ref['body'],source_receipt=ref['source_receipt'],http_status=ref['http_status'],
                http_status_inherited=True,http_success=True,quote_validity='not_assessed',completed_at=utcnow())
            save_json(final,row);state[day]=row;reused+=1
    return state,recovered,reused


def run_batch(protocol,batch_id,limit,*,transport=http_once,sleep=time.sleep,monotonic=time.monotonic,protocol_binding=None):
    """One fresh batch only. Completion queue defines consecutive-failure order."""
    if not re.fullmatch(r'batch\d{3,}',batch_id):raise ValueError('batch_id_must_be_batchNNN')
    h=protocol['HTTP'];dates=protocol['dates'];contract=protocol['output_contract'];root=Path(contract['path']).resolve()
    if (not isinstance(limit,int) or not 1<=limit<=h['max_new_requests_per_invocation'] or not 1<=h['max_parallel']<=2
            or len(dates)!=len(set(dates)) or len(dates)!=protocol['date_count']
            or h['attempts_per_date']!=1 or not h['no_retry'] or not h['no_latest_fallback']):
        raise ValueError('frozen_batch_budget_or_dates')
    with archive_lock(root):
        raw_dir=root/contract['body_subdir'];rows_dir=root/contract['metadata_subdir'];batches=root/contract['batch_subdir']
        for folder in (raw_dir,rows_dir,batches):folder.mkdir(parents=True,exist_ok=True)
        batch=batches/batch_id;batch.mkdir(exist_ok=False)
        began=monotonic();source=binding(Path(__file__).resolve())
        save_json(batch/'started.json',dict(schema='stage250_raw_batch_started_v1',batch_id=batch_id,limit=limit,
            protocol=protocol_binding,source=source,started_at=utcnow(),automatic_retry=False))
        state={};new_rows=[];cancelled=[];recovered=0;reused=0;stop_reason=None;failure=None;status='failed'
        stop_event=threading.Event();done=queue.Queue();attempt_count=0;attempt_guard=threading.Lock()
        completion_guard=threading.Lock();failed_run=0
        attempted_dates=[]
        try:
            state,recovered,reused=restore_rows(protocol,rows_dir,raw_dir)
            available=[d for d in dates if d not in state];selected=available[:limit]
            gate=StartGate(h['global_min_start_interval_seconds'],stop_event,sleep,monotonic,
                           any(int(r.get('attempts',0))>0 for r in state.values()))
            def worker(day):
                nonlocal attempt_count,failed_run,stop_reason
                url=protocol['url_template'].format(date=day);start_row={}
                def request_start(stamp):
                    nonlocal attempt_count
                    start_row.update(date=day,url=url,batch_id=batch_id,attempts=1,reused=False,
                        request_started_at=utcnow(),request_start_monotonic=stamp,protocol=protocol_binding)
                    save_json(rows_dir/(day+'.started.json'),start_row)
                    with attempt_guard:attempt_count+=1;attempted_dates.append(day)
                if not gate.start(request_start):return dict(date=day,state='cancelled_before_HTTP',attempts=0)
                result=transport(url,h,stop_event)
                # Custom/simulated transports receive the same stop semantics.
                if result.get('http_status') in h['stop_new_submissions_on_HTTP']:stop_event.set()
                body=result.pop('body',None)
                row=dict(start_row,**result,completed_at=utcnow(),quote_validity='not_assessed')
                if body is not None:
                    if not isinstance(body,bytes) or len(body)>h['max_body_bytes']:raise ValueError('transport_body_exceeds_frozen_cap')
                    path=raw_dir/(day+'.response');atomic_create(path,body)
                    row['body']=dict(path=str(path),bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
                else:row['body']=None
                row['http_success']=bool(row.get('http_status')==200 and row.get('truncated') is False and row.get('transport_error') is None)
                row['state']='http_complete' if row['http_success'] else 'http_failed'
                save_json(rows_dir/(day+'.json'),row)
                with completion_guard:
                    failed_run=0 if row['http_success'] else failed_run+1
                    if row.get('http_status') in h['stop_new_submissions_on_HTTP']:
                        stop_event.set();stop_reason=stop_reason or 'HTTP_'+str(row['http_status'])
                    if failed_run>=h['stop_new_submissions_after_consecutive_failed_completions']:
                        stop_event.set();stop_reason=stop_reason or 'consecutive_failed_completions'
                return row
            next_index=0;pending=set()
            with ThreadPoolExecutor(max_workers=h['max_parallel']) as pool:
                def submit():
                    nonlocal next_index
                    while not stop_event.is_set() and len(pending)<h['max_parallel'] and next_index<len(selected):
                        future=pool.submit(worker,selected[next_index]);next_index+=1;pending.add(future);future.add_done_callback(done.put)
                submit()
                while pending:
                    completed=[done.get()]
                    while True:
                        try:completed.append(done.get_nowait())
                        except queue.Empty:break
                    for future in completed:
                        pending.remove(future)
                        try:row=future.result()
                        except Exception:
                            stop_event.set();raise
                        if not row['attempts']:cancelled.append(row['date']);continue
                        new_rows.append(row);state[row['date']]=row
                        if row.get('http_status') in h['stop_new_submissions_on_HTTP']:
                            stop_event.set();stop_reason=stop_reason or 'HTTP_'+str(row['http_status'])
                    submit()
            status='completed'
        except Exception as exc:
            stop_event.set();failure=dict(type=type(exc).__name__,message=str(exc))
        # If a metadata/write error interrupted main, all inflight workers have
        # drained by pool.__exit__; unfinished starts remain durable unknown.
        remaining=sum(not (rows_dir/(d+'.json')).exists() and not (rows_dir/(d+'.started.json')).exists()
                      and not (raw_dir/(d+'.response')).exists() for d in dates)
        receipt=dict(schema='stage250_raw_spot_batch_receipt_v1',status=status,batch_id=batch_id,protocol=protocol_binding,source=source,
            limit=limit,network_attempts=attempt_count,attempted_dates=attempted_dates,rows=new_rows,
            cancelled_before_HTTP=cancelled,reused_bindings_added=reused,interrupted_attempts_resolved_unknown=recovered,
            archive_recorded_dates=len(state),remaining_unattempted=remaining,stopped_early=stop_event.is_set(),stop_reason=stop_reason,
            consecutive_failed_completions_at_end=failed_run,failure=failure,
            automatic_retry=False,automatic_next_batch=False,quote_validity='not_assessed',new_fit=0,new_cash=0,SQL=0,
            cumulative_fit=protocol.get('cumulative_fit'),cumulative_cash=protocol.get('cumulative_cash'),
            elapsed_seconds=monotonic()-began,completed_at=utcnow())
        save_json(batch/'receipt.json',receipt)
        save_json(batch/'terminal.json',dict(schema='stage250_raw_spot_batch_terminal_v1',status=status,exit_code=0 if status=='completed' else 1,
            batch_id=batch_id,network_attempts=attempt_count,remaining_unattempted=remaining,stop_reason=stop_reason,
            automatic_retry=False,automatic_next_batch=False,new_fit=0,new_cash=0,elapsed_seconds=receipt['elapsed_seconds']))
        save_json(batch/'manifest.json',dict(schema='stage250_raw_spot_batch_manifest_v1',status=status,protocol=protocol_binding,source=source,
            artifacts={p.name:binding(p) for p in sorted(batch.iterdir()) if p.is_file()},
            new_date_metadata=[dict(date=r['date'],row_path=str(rows_dir/(r['date']+'.json')),body=r.get('body')) for r in new_rows],
            reused_raw_rehashed=False,old_source_body_reads=0,new_fit=0,new_cash=0))
        if failure:raise RuntimeError(failure['type']+': '+failure['message'])
        return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--batch-id',required=True)
    parser.add_argument('--limit',type=int,default=250);args=parser.parse_args(argv)
    pb=binding(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen249_protocol_changed')
    protocol=json.loads(PROTOCOL.read_text())
    if protocol['schema']!='stage249_raw_spot_archive_protocol_v1':raise ValueError('frozen249_schema')
    result=run_batch(protocol,args.batch_id,args.limit,protocol_binding=pb)
    print(json.dumps({k:result[k] for k in ('status','batch_id','network_attempts','remaining_unattempted','stop_reason')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
