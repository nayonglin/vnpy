"""Bounded append-only Tq recent daily reception; no freeze, model or cash.

run_batch requires an exact root authorization before private config/network.
capture_from_api is the transport seam for one offline tiny and that authorized
call only. It saves every returned raw row before any explicit date semantics.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager, redirect_stdout, redirect_stderr, suppress
from datetime import date, datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import logging
import math
from pathlib import Path
import re
import signal
import time
from zoneinfo import ZoneInfo

import numpy as np

TOOLS=Path(__file__).resolve().parent
ROOT=TOOLS.parents[3]
EXCHANGES=frozenset({'CFFEX','SHFE','INE','DCE','CZCE','GFEX'})
CUTOFF='2026-10-16'
CHINA=ZoneInfo('Asia/Shanghai')
JOURNAL_SHA='b687c3d6ae8f78dee30a05094c09fb0da3d5c9daa4e12d7132262c3ee052e003'
REDACT_SOURCE=ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools/stage264_diagnose_tqsdk.py'
CREDENTIAL_SOURCE=ROOT/'examples/portfolio_backtesting/download_tqsdk_all_futures_daily_csv.py'
REDACT_SHA='e9d3f0bccf20d21872605a671bd020beb81f084d460e25fe4d67d33ef555889d'
CREDENTIAL_SHA='51ecc292b6f8753c9822558282edb5e40eef38ebb93441ca81dd7e306150dca8'
DEFAULT_LIMITS=dict(batch_size=80,ready_timeout_seconds=40.,global_timeout_seconds=720.,
    connect_timeout_seconds=45.,catalog_timeout_seconds=45.,calendar_timeout_seconds=45.,
    close_timeout_seconds=8.,max_consecutive_connection_errors=3,max_consecutive_unready_batches=3)


def read_json(path):return json.loads(Path(path).read_text())


def _safe(value):
    if isinstance(value,dict):return {str(k):_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_safe(v) for v in value]
    if isinstance(value,np.generic):return _safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,(date,datetime)):return value.isoformat()
    return value


def _write(path,value):
    raw=(json.dumps(_safe(value),ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as f:f.write(raw)
    return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _bound(binding):
    p=Path(binding['path']);raw=p.read_bytes()
    if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:
        raise ValueError('frozen small source/input changed: '+p.name)
    return raw


def _pure(path,sha,name,namespace):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('accepted pure helper changed')
    node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name==name)
    env=dict(namespace);exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),env)
    return env[name]


def load_journal():
    p=TOOLS/'stage321_forward_journal.py'
    if hashlib.sha256(p.read_bytes()).hexdigest()!=JOURNAL_SHA:raise ValueError('accepted321 journal changed')
    spec=importlib.util.spec_from_file_location('stage336_accepted321',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def _redact(message,secrets):return _pure(REDACT_SOURCE,REDACT_SHA,'redact',{'re':re})(str(message),secrets)


def _error(error,secrets):return dict(error_type=type(error).__name__,error_redacted=_redact(error,secrets))


def _utc(value):
    d=value if isinstance(value,datetime) else datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if d.tzinfo is None or d.utcoffset() is None:raise ValueError('explicit timezone required')
    return d.astimezone(timezone.utc)


@contextmanager
def _alarm(seconds):
    """Main-thread hard limit, including SDK synchronous initialization waits."""
    def stop(signum,frame):raise TimeoutError('bounded_receiver_deadline')
    previous=signal.getsignal(signal.SIGALRM);old=signal.getitimer(signal.ITIMER_REAL)
    began=time.monotonic();signal.signal(signal.SIGALRM,stop)
    signal.setitimer(signal.ITIMER_REAL,min(seconds,old[0]) if old[0]>0 else seconds)
    try:yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        if old[0]>0:signal.setitimer(signal.ITIMER_REAL,max(.001,old[0]-(time.monotonic()-began)),old[1])


def symbol_parts(symbol):
    match=re.fullmatch(r'(CFFEX|SHFE|INE|DCE|CZCE|GFEX)\.([A-Za-z]+)(\d{3,4})(F?)',symbol)
    if not match:return None
    exchange,product,code,flex=match.groups()
    if not 1<=int(code[-2:])<=12 or (len(code)==3 and exchange!='CZCE'):return None
    if flex and (exchange!='DCE' or product.lower() not in ('l','pp','v')):return None
    return dict(exchange=exchange,product_hint=product.upper()+('_F' if flex else ''),
                delivery_code_raw=code,F_suffix=bool(flex),canonical_identity='unknown_until_explicit_binding')


def select_catalog(fresh,prior):
    fresh=list(fresh);prior=list(prior)
    accepted={s for s in fresh if isinstance(s,str) and symbol_parts(s)}
    old={s for s in prior if isinstance(s,str) and symbol_parts(s)}
    return dict(symbols=sorted(accepted|old),fresh_symbols=sorted(accepted),
        added_symbols=sorted(accepted-old),just_retired_symbols=sorted(old-accepted),
        rejected_fresh=[dict(symbol=s,reason='not_six_exchange_true_month') for s in fresh if s not in accepted],
        rejected_prior=[dict(symbol=s,reason='not_six_exchange_true_month') for s in prior if s not in old],
        fresh_exchanges_present=sorted({s.split('.')[0] for s in accepted}),
        queried_exchanges=sorted(EXCHANGES),ins_class='FUTURE',expired=False)


def raw_records(frame):
    """Column-wise scalar access preserves int64 ns; never iterrows/float cast."""
    rows=[]
    for i in range(len(frame)):
        original={str(c):frame[c].iloc[i] for c in frame.columns}
        value=original.get('datetime');valid=isinstance(value,(int,np.integer)) and not isinstance(value,(bool,np.bool_)) and int(value)>0
        ns=int(value) if valid else None;local=None;state='strict_integer_ns' if valid else 'raw_timestamp_unknown'
        if ns is not None:
            try:
                d=datetime.fromtimestamp(ns//10**9,timezone.utc).astimezone(CHINA)
                offset=d.strftime('%z');fraction='.'+f'{ns%10**9:09d}' if ns%10**9 else ''
                local=d.strftime('%Y-%m-%dT%H:%M:%S')+fraction+offset[:3]+':'+offset[3:]
            except (ValueError,OverflowError,OSError):state='raw_timestamp_out_of_range'
        rows.append(dict(row_index=i,raw_ns=ns,raw_local_iso=local,
            raw_datetime_literal=str(value),raw_datetime_type=type(value).__name__,timestamp_state=state,
            values=_safe(original),raw_missing_fields=[k for k,v in original.items()
                if v is None or isinstance(v,(float,np.floating)) and not math.isfinite(float(v))]))
    return rows


def normalize_record(raw,*,symbol,received_at,fresh_ready,contract,end_inclusive):
    """335 operational labels/clock only; provider units remain unqualified."""
    received=_utc(received_at);ns=raw['raw_ns'];calendar=contract.get('calendar',{})
    native={k:raw['values'].get(k) for k in ('open','high','low','close','volume','open_oi','close_oi')}
    numeric=all(isinstance(native[k],(int,float)) and math.isfinite(native[k]) and native[k]>0
                for k in ('open','high','low','close','volume'))
    shape=numeric and native['low']<=min(native['open'],native['close']) and native['high']>=max(native['open'],native['close'])
    result=dict(symbol=symbol,row_index=raw['row_index'],raw_ns=ns,raw_local_iso=raw['raw_local_iso'],
        trade_date=None,date_mapping_state='unknown',date_mapping_rule=None,session_evidence=None,
        session_end_at=None,source_completed_at=None,completion_state='completion_clock_unknown',
        completion_observed_at=None,received_at=received.isoformat(),D_date=None,D_open_at=None,
        D_open_state='unknown',vendor_finality='unknown',source_first_published_at=None,
        contract_epoch_id=None,identity_state='unknown',units_status='provider_raw_units_unverified',
        native_values=native,native_geometry_state='valid_native_shape' if shape else 'invalid_or_missing_native_shape',
        canonical_quality_status='unknown',
        model_input_eligible=False,active=False,T0=None,window_state='date_unknown')
    day=None
    if ns is not None and raw['timestamp_state']=='strict_integer_ns':
        local=datetime.fromtimestamp(ns//10**9,timezone.utc).astimezone(CHINA)
        if (contract.get('timestamp_semantics')=='tq_daily_midnight_label_calendar_v1'
                and local.hour==local.minute==local.second==0 and ns%10**9==0
                and calendar.get(local.date().isoformat()) is True):
            day=local.date().isoformat();result.update(date_mapping_state='operational_midnight_label',
                date_mapping_rule='tq_daily_midnight_label_calendar_v1')
        elif contract.get('timestamp_semantics')=='explicit_session_start_interval_v1':
            stamp=datetime.fromtimestamp(ns//10**9,timezone.utc)
            matches=[v for v in contract.get('session_start_intervals',{}).get(symbol,[])
                if v.get('confirmed') is True and _utc(v['start_at'])<=stamp<_utc(v['end_at'])
                and calendar.get(v['trade_date']) is True]
            if len(matches)==1:
                day=matches[0]['trade_date'];result.update(date_mapping_state='explicit_session_interval',
                    date_mapping_rule='explicit_session_start_interval_v1',session_evidence=matches[0])
    if day is None:return result
    result['trade_date']=day
    result['window_state']='before_or_at_cutoff' if day<=CUTOFF else 'in_window' if day<=end_inclusive else 'after_window'
    identity=contract.get('identity_map',{}).get(symbol)
    if isinstance(identity,str) and re.fullmatch(r'(CFFEX|SHFE|INE|DCE|CZCE|GFEX)\.[A-Z]+(?:_F)?\.\d{6}',identity):
        exchange,product,month=identity.split('.');parts=symbol_parts(symbol)
        date(int(month[:4]),int(month[4:]),1)
        if (parts is None or exchange!=parts['exchange'] or product!=parts['product_hint']
                or not month.endswith(parts['delivery_code_raw'])):
            raise ValueError('explicit identity differs from nominal symbol month/product; expiry is not nominal delivery')
        result.update(contract_epoch_id=identity,identity_state='explicit_bound_identity')
    proof=contract.get('session_evidence',{}).get(symbol,{}).get(day,{})
    if proof:result['session_evidence']=proof
    if proof.get('confirmed') is True and proof.get('session_end_at'):
        end=_utc(proof['session_end_at']);result['session_end_at']=end.isoformat()
        if fresh_ready and end<=received:
            result.update(source_completed_at=end.isoformat(),completion_observed_at=received.isoformat(),
                          completion_state='operational_closed_day_snapshot')
        elif received<end:result['completion_state']='current_session_not_closed'
    next_days=sorted(k for k,v in calendar.items() if v is True and k>day)
    if next_days:
        result['D_date']=next_days[0]
        if proof.get('confirmed') is True and proof.get('D_open_at') and proof.get('D_date',next_days[0])==next_days[0]:
            result.update(D_open_at=_utc(proof['D_open_at']).isoformat(),D_open_state='explicit_confirmed_session')
    return result


def _calendar_map(frame):
    result={}
    for i in range(len(frame)):
        day=str(frame['date'].iloc[i])[:10];value=frame['trading'].iloc[i]
        date.fromisoformat(day)
        if not isinstance(value,(bool,np.bool_)):raise ValueError('calendar trading boolean required')
        if day in result:raise ValueError('duplicate calendar date')
        result[day]=bool(value)
    return result


def capture_from_api(api,prior,*,output,journal,limits,source_version,calendar_start,calendar_end,
                     normalization_contract,secrets=(),clock=time):
    """One API instance; independent single-symbol series and complete outcomes."""
    out=Path(output).resolve()
    if out.exists():raise FileExistsError('fresh immutable batch output required')
    out.mkdir(parents=True);(out/'raw').mkdir();(out/'normalized').mkdir()
    started=clock.monotonic();stop=started+limits['global_timeout_seconds']
    report=dict(schema='stage336_recent_daily_receiver_manifest_v1',status='running',T0=None,
        forward_observations=0,active=False,units_status='provider_raw_units_unverified',
        source_version=source_version,items={},requests=dict(catalog=0,calendar=0,single_symbol_serial=0),
        duration_seconds=86400,data_length=35,broker_connections=0,order_api_calls=0,cancel_api_calls=0,
        limits=limits,started_at=datetime.now(timezone.utc).isoformat())
    _write(out/'started.json',report)
    targets=[];circuit=False;connection_errors=0;unready_batches=0
    try:
        report['requests']['catalog']+=1
        with _alarm(limits.get('catalog_timeout_seconds',45.)):
            fresh=list(api.query_quotes(ins_class='FUTURE',exchange_id=sorted(EXCHANGES),expired=False))
        catalog=select_catalog(fresh,prior);targets=catalog['symbols'];report['catalog']=catalog
        if not fresh:raise ValueError('fresh catalog empty; coverage unknown')
        catalog_artifact=_write(out/'catalog.json',dict(catalog,raw_fresh=fresh,
            queried_at=datetime.now(timezone.utc).isoformat(),source='TqSdk query_quotes'))
        report['catalog_receipt']=journal.append('receiver_catalog',catalog_artifact,key=out.name+':catalog:'+catalog_artifact['sha256'])
        context=dict(normalization_contract);context['calendar']=dict(context.get('calendar',{}))
        report['requests']['calendar']+=1
        try:
            with _alarm(limits.get('calendar_timeout_seconds',45.)):
                calendar_frame=api.get_trading_calendar(start_dt=date.fromisoformat(calendar_start),end_dt=date.fromisoformat(calendar_end)).copy(deep=True)
            context['calendar']=_calendar_map(calendar_frame)
            artifact=_write(out/'calendar.json',dict(source='TqSdk get_trading_calendar',
                start=calendar_start,end=calendar_end,days=context['calendar'],raw_rows=calendar_frame.to_dict('records')))
            report['calendar']=dict(status='received',artifact=artifact,
                receipt=journal.append('receiver_calendar',artifact,key=out.name+':calendar:'+artifact['sha256']))
        except Exception as exc:
            report['calendar']=dict(status='unknown',**_error(exc,secrets))
        size=int(limits['batch_size'])
        for offset in range(0,len(targets),size):
            if circuit or clock.monotonic()>=stop:break
            batch=targets[offset:offset+size];frames={};errors={}
            async def subscribe():
                nonlocal connection_errors,circuit
                for symbol in batch:
                    if circuit:break
                    try:
                        report['requests']['single_symbol_serial']+=1
                        report['items'][symbol]=dict(status='request_started')
                        frames[symbol]=api.get_kline_serial(symbol,86400,data_length=35)
                        connection_errors=0
                    except Exception as exc:
                        errors[symbol]=_error(exc,secrets)
                        if isinstance(exc,(ConnectionError,OSError)) or type(exc).__name__ in ('TqTimeoutError','ConnectionClosed'):
                            connection_errors+=1
                            if connection_errors>=limits['max_consecutive_connection_errors']:circuit=True
                        else:connection_errors=0
            task=api.create_task(subscribe());until=min(stop,clock.monotonic()+limits['ready_timeout_seconds'])
            wait_error=None
            while clock.monotonic()<until and not circuit:
                if task.done() and task.exception():wait_error=_error(task.exception(),secrets);break
                if task.done() and all(s in errors or s in frames and api.is_serial_ready(frames[s]) for s in batch):break
                try:api.wait_update(deadline=min(clock.time()+3.,clock.time()+max(0.,until-clock.monotonic())))
                except Exception as exc:wait_error=_error(exc,secrets);circuit=True;break
            if not task.done():task.cancel()
            ready_count=0
            for symbol in batch:
                if symbol in errors:
                    item=dict(status='error',**errors[symbol])
                elif symbol not in frames:
                    item=dict(status='not_attempted_circuit' if circuit else 'missing_timeout')
                else:
                    frame=frames[symbol].copy(deep=True);ready=bool(api.is_serial_ready(frames[symbol]));ready_count+=ready
                    rows=raw_records(frame)
                    raw=_write(out/'raw'/(symbol.replace('.','_')+'.json'),dict(schema='stage336_raw_daily_symbol_v1',
                        symbol=symbol,symbol_parts=symbol_parts(symbol),duration_seconds=86400,data_length_requested=35,
                        source='TqSdk get_kline_serial single symbol',source_version=source_version,
                        ready=ready,ready_observed_at=datetime.now(timezone.utc).isoformat(),
                        columns=list(frame.columns),dtypes={str(c):str(frame[c].dtype) for c in frame.columns},
                        rows=rows,units_status='provider_raw_units_unverified',scaling_applied='none; preserve native values'))
                    report['items'][symbol]=dict(status='raw_archived_pending_receipt',raw=raw)
                    receipt=journal.append('receiver_raw_symbol',dict(symbol=symbol,raw=raw,source_version=source_version),
                        key=out.name+':'+symbol+':'+raw['sha256'])
                    report['items'][symbol].update(status='raw_received_pending_normalization',receipt=receipt,
                                                   received_at=receipt['recorded_at'])
                    observations=[];normalization_errors=0
                    for r in rows:
                        try:
                            observations.append(normalize_record(r,symbol=symbol,received_at=receipt['recorded_at'],fresh_ready=ready,
                                contract=context,end_inclusive=normalization_contract.get('end_inclusive',calendar_end)))
                        except Exception as exc:
                            normalization_errors+=1
                            observations.append(dict(symbol=symbol,row_index=r['row_index'],raw_ns=r['raw_ns'],
                                trade_date=None,source_completed_at=None,completion_observed_at=None,window_state='date_unknown',
                                units_status='provider_raw_units_unverified',canonical_quality_status='unknown',
                                model_input_eligible=False,active=False,normalization_state='unknown_error',**_error(exc,secrets)))
                    normalized=_write(out/'normalized'/(symbol.replace('.','_')+'.json'),dict(symbol=symbol,raw=raw,
                        receipt=receipt,observations=[r for r in observations if r['window_state']=='in_window'],
                        unknown_rows=[r for r in observations if r['trade_date'] is None],canonical_model_rows=[],
                        historical_overlap_rows_kept_in_raw=sum(r['window_state']=='before_or_at_cutoff' for r in observations)))
                    item=dict(status='success' if ready and any(r['raw_ns'] for r in rows) else 'missing_timeout' if not ready else 'missing_data',
                        raw=raw,normalized=normalized,received_at=receipt['recorded_at'],receipt=receipt,
                        returned_rows=len(rows),fresh_ready=ready,normalization_errors=normalization_errors,
                        unknown_dates=sum(r['trade_date'] is None for r in observations))
                if wait_error:item['wait_error']=wait_error
                report['items'][symbol]=item
                if 'receipt' not in item:
                    item['receipt']=journal.append('receiver_symbol_status',dict(symbol=symbol,**item),key=out.name+':status:'+symbol)
            if ready_count==0 and frames:
                unready_batches+=1
                if unready_batches>=limits['max_consecutive_unready_batches']:circuit=True
            else:unready_batches=0
        reason='not_attempted_circuit' if circuit else 'not_attempted_deadline'
        for symbol in targets:
            if symbol not in report['items']:
                item=dict(status=reason)
                item['receipt']=journal.append('receiver_symbol_status',dict(symbol=symbol,**item),key=out.name+':status:'+symbol)
                report['items'][symbol]=item
        report['status']='completed' if all(v['status']=='success' for v in report['items'].values()) else 'partial'
    except Exception as exc:
        report.update(status='failed',**_error(exc,secrets))
        # Retain actual attempts and partial archives. A failed fresh catalog
        # cannot establish the missing current universe from the prior alone.
        for item in report['items'].values():
            if item['status']=='request_started':item['status']='attempted_no_persisted_snapshot'
        for symbol in targets or select_catalog([],prior)['symbols']:
            report['items'].setdefault(symbol,dict(status='not_attempted_after_capture_failure'))
    try:
        report.update(finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=clock.monotonic()-started,
                      circuit_open=circuit,target_symbols=len(targets),complete_target_statuses=len(report['items'])==len(targets),
                      new_fit=0,new_cash=0,old_cache_loads=0,SQL=0,source_completed_at_policy='confirmed session_end only, never receipt')
        _write(out/'manifest.json',report)
    except Exception as exc:
        exc.receiver_report=report
        raise
    return report


def run_batch(authorization,output):
    """Only root invokes the actual network path; adapter creates fresh output."""
    auth=read_json(authorization) if isinstance(authorization,(str,Path)) else dict(authorization)
    if (auth.get('schema')!='stage336_recent_daily_receiver_authorization_v1' or auth.get('authorized') is not True
            or auth.get('T0') is not None or auth.get('financial_D')!=0):raise ValueError('exact root reception authorization required')
    out=Path(output).resolve()
    if out.exists():raise FileExistsError('fresh receiver output required before config/network')
    bundle=json.loads(_bound(auth['source_bundle']))
    for b in bundle['sources']:_bound(b)
    prior=json.loads(_bound(auth['prior_catalog']))
    if prior.get('ins_class')!='FUTURE' or prior.get('expired') is not False or len(prior['symbols'])!=870:
        raise ValueError('frozen prior870 catalog required')
    _bound(auth['clock_design'])
    if auth.get('limits')!=DEFAULT_LIMITS:raise ValueError('pre-frozen bounded transport limits required')
    if auth.get('cutoff_exclusive')!=CUTOFF:raise ValueError('fixed historical gap boundary required')
    if importlib.metadata.version('tqsdk')!=auth.get('tqsdk_version'):raise ValueError('SDK version differs from root preflight')
    start=date.fromisoformat(auth['calendar_start']);end=date.fromisoformat(auth['calendar_end'])
    if start.isoformat()!=CUTOFF or not 1<=(end-start).days<=45:raise ValueError('bounded recent calendar window required')
    journal=load_journal().ForwardJournal(auth.get('journal_path',str(out.parent/'receiver_journal')),
        auth['journal_identity'])
    api=provider_auth=None;secrets=[];report=None;api_attempts=0;effective_manifest='manifest.json';old_logging=logging.root.manager.disable
    try:
        cfg=read_json(auth['credential_path'])
        username,password=_pure(CREDENTIAL_SOURCE,CREDENTIAL_SHA,'require_credentials',{'SETTINGS':cfg})()
        secrets=[username,password];del cfg
        logging.disable(logging.CRITICAL)
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),_alarm(DEFAULT_LIMITS['global_timeout_seconds']):
            from tqsdk import TqApi,TqAuth,TqSim
            with _alarm(DEFAULT_LIMITS['connect_timeout_seconds']):
                provider_auth=TqAuth(username,password)
                api_attempts+=1
                api=TqApi(TqSim(),auth=provider_auth,debug=False,disable_print=True,web_gui=False)
            secrets.extend(str(getattr(provider_auth,k,'') or '') for k in ('_access_token','_refresh_token','_auth_id'))
            report=capture_from_api(api,prior['symbols'],output=out,journal=journal,limits=DEFAULT_LIMITS,
                source_version='tqsdk/'+auth['tqsdk_version'],calendar_start=auth['calendar_start'],calendar_end=auth['calendar_end'],
                normalization_contract=auth['normalization_contract'],secrets=secrets)
    except Exception as exc:
        if provider_auth is not None:secrets.extend(str(getattr(provider_auth,k,'') or '') for k in ('_access_token','_refresh_token','_auth_id'))
        if not out.exists():out.mkdir(parents=True)
        preserved=getattr(exc,'receiver_report',None)
        if (out/'manifest.json').exists():
            preserved=read_json(out/'manifest.json');effective_manifest='post_capture_failure.json'
        if preserved is not None:
            report=dict(preserved,captured_status=preserved['status'],status='partial_capture_error',**_error(exc,secrets))
        else:
            report=dict(schema='stage336_recent_daily_receiver_manifest_v1',status='failed',T0=None,financial_D=0,
                        forward_observations=0,new_fit=0,new_cash=0,fresh_catalog_coverage='unknown',
                        items={s:dict(status='not_attempted_connection_failure') for s in select_catalog([],prior['symbols'])['symbols']},
                        **_error(exc,secrets))
        _write(out/effective_manifest,report)
    finally:
        if api is not None:
            with suppress(Exception),redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),_alarm(DEFAULT_LIMITS['close_timeout_seconds']):api.close()
        logging.disable(old_logging)
    terminal=dict(schema='stage336_recent_daily_receiver_terminal_v1',status=report['status'],T0=None,
        financial_D=0,new_fit=0,new_cash=0,forward_observations=0,api_instances_attempted=api_attempts,retries=0,
        manifest=dict(path=str(out/effective_manifest)),finished_at=datetime.now(timezone.utc).isoformat())
    _write(out/'terminal.json',terminal)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--authorization',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    if not args.execute:raise SystemExit('explicit --execute required')
    result=run_batch(args.authorization,args.output)
    print(json.dumps(dict(status=result['status'],new_fit=0,new_cash=0,T0=None),ensure_ascii=False))
    return 0 if result['status']=='completed' else 1


if __name__=='__main__':raise SystemExit(main())
