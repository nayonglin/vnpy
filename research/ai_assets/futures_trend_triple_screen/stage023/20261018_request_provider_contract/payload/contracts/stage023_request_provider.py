"""One bounded provider packet for an actual Stage021 request; never signs review."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout,redirect_stderr
from datetime import datetime
from importlib import metadata
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import numpy as np
import pandas as pd

import stage002_local_minute_overlay as old
import stage007_tqsdk_stream_probe as safety
import stage011_needed_local_completed as prior
import stage012_provider_batch as core
import stage015_daily_recovered_minute_delta as daily013
import stage018_provider_wait_budget as budget
import stage021_blocking_data_gate as gate

LINE,ROOT=old.LINE,old.ROOT
OUTPUT=LINE/'outputs/stage023_request_provider'
REQUEST_ROOT=LINE/'outputs/stage001_first_screen/C0_attempt3/data_wait'
PROTOCOL=LINE/'stages/20261018_0134_stage023_request_provider_protocol.md'
R013=LINE/'outputs/stage013_independent_review/review_receipt.json'
R013_SHA='194e48847c9e0927772c482cd5bacc3529a625ac76aeec2a157089924177c795'
OLD_MANIFEST_SHA='376cefaf2a56f75e97adf31e431dac508189695c4bb4691294ab5f950aeada03'
P018=budget.OUTPUT/'preflight.json'
P018_SHA='c178b128b39f0a85999a2992f1730d9737d51cd5b5a0b170c649cc97caa738e9'
SOFT,HARD=570,600


def read_request(path,file_sha,*,fixture_root=None):
    path=Path(path).resolve();root=Path(fixture_root).resolve()if fixture_root is not None else REQUEST_ROOT.resolve()
    if path.name!='request.json'or path.parent.parent!=root:raise ValueError('request_outside_exact_wait_root')
    if old.sha256(path)!=file_sha:raise ValueError('request_file_sha_mismatch')
    request=json.loads(path.read_text());digest=request.get('request_sha256')
    if request.get('schema')!=gate.REQUEST_SCHEMA or gate.request_sha256(request)!=digest:
        raise ValueError('request_canonical_sha_or_schema_mismatch')
    if path.parent.name!='request_'+str(digest):raise ValueError('request_folder_digest_mismatch')
    fingerprint=path.parent/'request_fingerprint.json';saved=json.loads(fingerprint.read_text())
    if saved!=dict(request_sha256=digest,request_file_sha256=file_sha,request_path=str(path)):
        raise ValueError('saved_request_fingerprint_mismatch')
    return request,{str(path):file_sha,str(fingerprint):old.sha256(fingerprint)}


def packet_targets(request,calendar,packet_index):
    if gate.request_sha256(request)!=request.get('request_sha256'):raise ValueError('request_canonical_sha_mismatch')
    calendar=pd.DatetimeIndex(calendar);date=str(request['execution_trade_date'])
    if not('2020-01-01'<=date<='2026-10-14'):raise ValueError('request_outside_frozen_period')
    orders={}
    for order in request['active_orders']:
        symbol=str(order['vt_symbol']);kind=order['requirement_kind']
        if kind not in {'full_session','anchor'}:raise ValueError('unknown_request_order_kind')
        if symbol not in orders or kind=='full_session':orders[symbol]=kind
    seen=set();targets=[]
    for item in request['requirements']:
        symbol=str(item['vt_symbol']);kind=item['requirement_kind']
        if symbol in seen or item['execution_trade_date']!=date or orders.get(symbol)!=kind:
            raise ValueError('request_kind_date_or_order_scope_invalid')
        seen.add(symbol);grid=old.session_grid(symbol,date,calendar)
        required=grid if kind=='full_session'else grid[:1]
        stamps=[stamp.isoformat()for stamp in required]
        if item['required_timestamps']!=stamps:raise ValueError('request_canonical_grid_mismatch')
        missing=item['missing_or_unqualified_timestamps']
        if not missing or len(missing)!=len(set(missing))or not set(missing).issubset(stamps):raise ValueError('request_missing_scope_invalid')
        if not set(item['existing_source_timestamps']).issubset(stamps):raise ValueError('request_existing_scope_invalid')
        targets.append(dict(item))
    symbols=sorted(seen);count=(len(symbols)+7)//8
    if not symbols or packet_index<0 or packet_index>=count:raise ValueError('packet_index_out_of_range')
    chosen=set(symbols[8*packet_index:8*(packet_index+1)])
    later=calendar[calendar>pd.Timestamp(date)]
    if len(later)==0:raise ValueError('next_mapping_trade_date_missing')
    clock=later[0]+pd.Timedelta(hours=9,minutes=1)
    selected=sorted([target for target in targets if target['vt_symbol']in chosen],key=lambda x:x['vt_symbol'])
    return selected,dict(packet_index=packet_index,packet_count=count,packet_contracts=sorted(chosen),
        total_request_contracts=len(symbols),covers_whole_request=count==1,
        request_required_minutes=sum(len(row['required_timestamps'])for row in targets),
        packet_required_minutes=sum(len(row['required_timestamps'])for row in selected),
        provider_start=clock.isoformat(),provider_end=(clock+pd.Timedelta(minutes=4)).isoformat())


def choose_daily_reference(symbol,day,kind,original,recovered,rejected):
    key=(symbol,day)
    if key in rejected:raise ValueError('explicitly_rejected_daily_target')
    required=old.VALUES if kind=='full_session'else ['open']
    if original is not None:
        dates=pd.to_datetime(original.trade_date).dt.strftime('%Y-%m-%d');hit=original.loc[dates.eq(day)]
        if len(hit)==1 and dates.gt(day).any()and all(name in hit and np.isfinite(float(hit.iloc[0][name]))for name in required):
            return {name:float(hit.iloc[0][name])for name in old.VALUES if name in hit and np.isfinite(float(hit.iloc[0][name]))},'original_daily_csv'
    if key in recovered:
        row=recovered[key]
        if all(np.isfinite(float(row.get(name,np.nan)))for name in required):
            return {name:float(row[name])for name in old.VALUES if np.isfinite(float(row.get(name,np.nan)))},'reviewed_stage013_daily'
    if original is not None:raise ValueError('daily_not_completed_or_invalid')
    raise ValueError('qualified_daily_reference_missing')


def qualify_target(raw,proofs,target):
    symbol=target['vt_symbol'];grid=pd.DatetimeIndex(target['required_timestamps'])
    selected=old.normal_times(raw.loc[raw.vt_symbol.eq(symbol)].copy())
    selected=selected.loc[selected.bar_datetime.isin(grid)].sort_values('bar_datetime')
    complete={(symbol,stamp)for stamp in grid}.issubset(proofs)
    if target['requirement_kind']=='full_session':
        _,check=old.validate_session(selected,grid,target['daily_reference'],selected.iloc[:0])
        return dict(vt_symbol=symbol,execution_trade_date=target['execution_trade_date'],requirement_kind='full_session',
            accepted=bool(check['status']=='accepted'and complete),completion_evidence_complete=complete,
            qualification_kind='completed_full_session_daily7',**check)
    check=dict(vt_symbol=symbol,execution_trade_date=target['execution_trade_date'],requirement_kind='anchor',
        accepted=False,completion_evidence_complete=complete,qualification_kind='anchor_only_not_full_session',
        status='quarantined',reason='anchor_grid_or_completion_missing',expected_minutes=1,actual_rows=len(selected),daily_mismatch_fields=[])
    if len(selected)!=1 or selected.bar_datetime.duplicated().any()or not complete:return check
    values=selected[old.VALUES].to_numpy(dtype=float);row=selected.iloc[0]
    if not np.isfinite(values).all()or min(row.open,row.high,row.low,row.close)<=0 or min(row.volume,row.open_oi,row.close_oi)<0 or(
        row.low>min(row.open,row.close))or(row.high<max(row.open,row.close)):
        check['reason']='invalid_anchor_ohlcvoi';return check
    reference=target['daily_reference'];fields=['open']
    if np.isfinite(float(reference.get('open_oi',np.nan))):fields.append('open_oi')
    mismatch=[name for name in fields if not np.isclose(float(row[name]),float(reference[name]),rtol=1e-12,atol=1e-8)]
    check.update(daily_mismatch_fields=mismatch,daily_openOI_check='checked'if'open_oi'in fields else'unknown')
    if mismatch:check['reason']='raw_anchor_daily_open_mismatch';return check
    check.update(accepted=True,status='accepted',reason='real_completed_anchor_open_matched_not_daily_price_fallback')
    return check


def prepare(request_path,request_file_sha,packet_index,*,fixture_root=None):
    request,inputs=read_request(request_path,request_file_sha,fixture_root=fixture_root)
    folder=OUTPUT/('request_'+request['request_sha256'])/f'packet_{packet_index:03d}'
    if folder.exists():raise FileExistsError('existing_request_packet_refusing_repeat')
    original=prior.bound_json(old.OLD/'input_manifest.json',OLD_MANIFEST_SHA,inputs)
    calendar_df=prior.read_bound_csv(old.MAPPING,original[str(old.MAPPING.relative_to(ROOT))],inputs,usecols=['date'])
    calendar=pd.DatetimeIndex(pd.to_datetime(sorted(calendar_df.date.unique())))
    targets,info=packet_targets(request,calendar,packet_index)
    review=prior.bound_json(R013,R013_SHA,inputs)
    for key in ['qualified_daily_path','target_qualification_path']:
        path=Path(review[key]);inputs[str(path)]=review['source_fingerprints'][str(path)]
    qualified=prior.read_bound_csv(review['qualified_daily_path'],inputs[review['qualified_daily_path']],inputs)
    audits=prior.read_bound_csv(review['target_qualification_path'],inputs[review['target_qualification_path']],inputs)
    references=daily013.approved_references(qualified,audits,review)
    rejected={(str(item['vt_symbol']),str(item['trade_date']))for item in review['rejected_targets']}
    for target in targets:
        symbol=target['vt_symbol'];day=target['execution_trade_date'];native,exchange=symbol.rsplit('.',1)
        path=old.PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04'/exchange/(native+'.csv')
        daily=None
        if path.is_file():daily=prior.read_bound_csv(path,original.get(str(path.relative_to(ROOT))),inputs)
        reference,source=choose_daily_reference(symbol,day,target['requirement_kind'],daily,references,rejected)
        target.update(daily_reference=reference,daily_reference_source=source,
            daily_reference_path=str(path)if source=='original_daily_csv'else review['qualified_daily_path'])
    manifest=dict(schema='stage023_provider_packet_v1',request_path=str(Path(request_path).resolve()),
        request_file_sha256=request_file_sha,request_sha256=request['request_sha256'],targets=targets,**info,
        input_sha256=inputs,fixture_scope=fixture_root is not None,fixture_root=str(Path(fixture_root).resolve())if fixture_root else None,
        financial_replays=0,orders=0,independent_review_signed=False,response_written=False)
    folder.mkdir(parents=True,exist_ok=False);old.write_json(folder/'packet_manifest.json',manifest)
    result=preflight(folder);old.write_json(folder/'preflight.json',result)
    print(json.dumps(dict(packet_dir=str(folder),**{k:info[k]for k in ['packet_index','packet_count','covers_whole_request','packet_required_minutes']})))


def read_packet(folder):
    folder=Path(folder).resolve()
    if not folder.is_relative_to(OUTPUT.resolve()):raise ValueError('packet_outside_stage023_output')
    manifest=json.loads((folder/'packet_manifest.json').read_text())
    if folder!=OUTPUT.resolve()/('request_'+manifest['request_sha256'])/f"packet_{manifest['packet_index']:03d}":
        raise ValueError('packet_path_identity_mismatch')
    return manifest


def preflight(folder):
    folder=Path(folder).resolve();manifest=read_packet(folder)
    request,_=read_request(manifest['request_path'],manifest['request_file_sha256'],fixture_root=manifest['fixture_root'])
    if request['request_sha256']!=manifest['request_sha256']:raise ValueError('packet_request_binding_changed')
    inputs=dict(manifest['input_sha256'])
    for path,digest in inputs.items():
        if old.sha256(path)!=digest:raise ValueError('packet_reference_source_changed')
    if metadata.version('tqsdk')!='3.10.2'or any(os.environ.get(key)for key in safety.ENDPOINT_ENV):raise ValueError('sdk_or_endpoint_changed')
    safety.load_credentials()
    if old.sha256(P018)!=P018_SHA:raise ValueError('frozen_budget_preflight_changed')
    verified=json.loads(P018.read_text())['source_fingerprints']
    sdk=Path(metadata.distribution('tqsdk').locate_file('tqsdk'))
    frozen=[Path(core.__file__),Path(budget.__file__),*[sdk/name for name in ['api.py','auth.py','tradeable/sim/tqsim.py','backtest/backtest.py','tools/downloader.py']]]
    for path in frozen:
        if old.sha256(path)!=verified[str(path)]:raise ValueError('verified_collector_budget_or_sdk_changed')
    paths=[Path(__file__),PROTOCOL,Path(gate.__file__),Path(old.__file__),Path(prior.__file__),Path(daily013.__file__),Path(safety.__file__),P018,
        folder/'packet_manifest.json',*frozen]
    inputs.update({str(path):old.sha256(path)for path in paths})
    return dict(status='passed_offline_preflight_no_connection',request_sha256=manifest['request_sha256'],
        packet_index=manifest['packet_index'],packet_count=manifest['packet_count'],covers_whole_request=manifest['covers_whole_request'],
        target_minutes=manifest['packet_required_minutes'],contracts=len(manifest['packet_contracts']),
        provider_start=manifest['provider_start'],provider_end=manifest['provider_end'],fixture_scope=manifest['fixture_scope'],
        soft_seconds=SOFT,hard_seconds=HARD,provider_attempts_max=1,credentials_present=True,credential_values_saved=False,
        auth_checks_unmodified=True,source_fingerprints=inputs,financial_replays=0,orders=0,independent_review_signed=False,response_written=False)


def save(folder,collector,diagnostic):
    raw,evidence=collector.frames()
    for name,frame in [('raw_completed_minutes.csv',raw),('completion_evidence.csv',evidence)]:
        temporary=folder/(name+'.tmp');frame.to_csv(temporary,index=False);os.replace(temporary,folder/name)
    old.write_json(folder/'progress.json',dict(completed_minutes=len(raw),target_minutes=collector.target_count,diagnostic=dict(diagnostic)))


def worker(folder,parent_pid):
    folder=Path(folder).resolve();manifest=read_packet(folder);attempt=folder/'network_attempt1'
    if os.getppid()!=parent_pid or not(attempt/'attempt_started.json').is_file()or manifest['fixture_scope']:return 2
    expected={row['vt_symbol']:row['required_timestamps']for row in manifest['targets']};collector=core.BatchCollector(expected)
    api=None;provider=False;sim_created=False;status='initializing';finished=();began=time.monotonic();diagnostic={'phase':'initializing'}
    with open(os.devnull,'w')as discard,redirect_stdout(discard),redirect_stderr(discard):
        logging.disable(logging.CRITICAL)
        try:
            from tqsdk import TqApi,TqAuth,TqSim,TqBacktest,BacktestFinished
            finished=(BacktestFinished,);username,password=safety.load_credentials();sim=TqSim();sim_created=True;provider=True
            diagnostic['phase']='api_initializing'
            api=TqApi(account=sim,auth=TqAuth(username,password),backtest=TqBacktest(
                start_dt=datetime.fromisoformat(manifest['provider_start']),end_dt=datetime.fromisoformat(manifest['provider_end'])),debug=False,web_gui=False)
            username=password=None;serials={}
            async def subscribe():
                for symbol in sorted(expected):
                    native,exchange=symbol.rsplit('.',1);serials[symbol]=api.get_kline_serial(f'{exchange}.{native}',60,data_length=10000)
            api.create_task(subscribe())
            status=budget.collect_with_budget(api,collector,serials,began,diagnostic,lambda:save(attempt,collector,diagnostic))
        except finished:status='provider_finished';diagnostic['phase']='provider_finished'
        except BaseException as error:
            status='provider_or_local_failed';old.write_json(attempt/'safe_error.json',{**safety.safe_error(error),'phase':diagnostic['phase']})
        finally:
            save(attempt,collector,diagnostic)
            if api is not None:
                try:api.close()
                except BaseException as error:
                    status='close_failed';old.write_json(attempt/'safe_close_error.json',safety.safe_error(error))
    raw,evidence=collector.frames();raw=old.normal_times(raw)
    proofs={(row.vt_symbol,pd.Timestamp(row.bar_datetime))for row in evidence.itertuples(index=False)
        if row.completed and pd.Timestamp(row.successor_time)>=pd.Timestamp(row.bar_datetime)+pd.Timedelta(minutes=1)}
    checks=[qualify_target(raw,proofs,target)for target in manifest['targets']]
    accepted=all(check['accepted']for check in checks)
    quality=dict(request_sha256=manifest['request_sha256'],packet_index=manifest['packet_index'],packet_count=manifest['packet_count'],
        covers_whole_request=manifest['covers_whole_request'],packet_all_targets_accepted=accepted,
        request_fully_qualified_by_this_packet=accepted and manifest['covers_whole_request'],sessions=checks,raw_rows=len(raw),
        accepted_requirements=sum(check['accepted']for check in checks),independent_review_signed=False,response_written=False)
    old.write_json(attempt/'quality.json',quality)
    old.write_json(attempt/'worker_receipt.json',dict(status=status,provider_attempts=int(provider),local_TqSim_created=sim_created,
        request_sha256=manifest['request_sha256'],completed_minutes=len(raw),target_minutes=collector.target_count,diagnostic=diagnostic,
        financial_replays=0,orders=0,cancels=0,broker_or_ctp_connections=0,model_fits=0,raw_sdk_output_saved=False,
        credential_values_saved=False,cache_or_overlay_written=False,independent_review_signed=False,response_written=False,production_qualified=False))
    return 0 if accepted and status=='all_target_minutes_completed'else 1


def run_once(folder):
    folder=Path(folder).resolve();manifest=read_packet(folder);attempt=folder/'network_attempt1'
    if manifest['fixture_scope']:raise ValueError('test_fixture_forbidden_from_provider_run')
    if attempt.exists():raise FileExistsError('existing_packet_attempt_refusing_retry')
    frozen=json.loads((folder/'preflight.json').read_text())
    if preflight(folder)!=frozen:raise ValueError('packet_preflight_drift')
    attempt.mkdir(exist_ok=False);old.write_json(attempt/'attempt_started.json',dict(request_sha256=manifest['request_sha256'],
        packet_index=manifest['packet_index'],provider_attempts_max=1,soft_seconds=SOFT,hard_seconds=HARD,automatic_retry=False))
    began=time.monotonic();process=None;killed=False
    try:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',str(os.getpid()),'--packet-dir',str(folder)],
            cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:code=process.wait(timeout=HARD)
        except subprocess.TimeoutExpired:killed=True;os.killpg(process.pid,signal.SIGKILL);process.wait();code=-9
        unchanged=all(old.sha256(path)==digest for path,digest in frozen['source_fingerprints'].items())
        result=dict(status='hard_timeout'if killed else'worker_terminal',exit_code=code,hard_kill=killed,elapsed_seconds=time.monotonic()-began,
            all_inputs_unchanged=unchanged,request_sha256=manifest['request_sha256'],packet_index=manifest['packet_index'],
            packet_count=manifest['packet_count'],covers_whole_request=manifest['covers_whole_request'],provider_attempts_max=1,automatic_retry=False,
            financial_replays=0,orders=0,cancels=0,broker_or_ctp_connections=0,raw_sdk_output_saved=False,credential_values_saved=False,
            cache_or_overlay_written=False,independent_review_signed=False,response_written=False,production_qualified=False)
        result['artifact_sha256']={path.name:old.sha256(path)for path in attempt.iterdir()if path.is_file()}
        old.write_json(attempt/'parent_receipt.json',result);print(json.dumps({k:result[k]for k in ['status','exit_code','elapsed_seconds','all_inputs_unchanged']}))
        return 0 if code==0 and unchanged else 1
    finally:
        if process is not None and process.poll()is None:os.killpg(process.pid,signal.SIGKILL);process.wait()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',action='store_true');mode.add_argument('--run',action='store_true');mode.add_argument('--worker',type=int)
    parser.add_argument('--request');parser.add_argument('--request-file-sha256');parser.add_argument('--packet-index',type=int,default=0)
    parser.add_argument('--packet-dir');parser.add_argument('--fixture-root');args=parser.parse_args()
    try:
        if args.prepare:
            if not args.request or not args.request_file_sha256:parser.error('request path and actual file SHA are required')
            prepare(args.request,args.request_file_sha256,args.packet_index,fixture_root=args.fixture_root)
        elif args.worker is not None:raise SystemExit(worker(args.packet_dir,args.worker))
        else:raise SystemExit(run_once(args.packet_dir))
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        print(json.dumps(safety.safe_error(error)));raise SystemExit(1)
