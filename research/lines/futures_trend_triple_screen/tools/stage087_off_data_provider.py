"""Owner-scoped ordinary daily / completed-minute provider, never a reviewer.

Only stdlib imports at bootstrap. One normal API per prepared packet, one worker
attempt, original collector and 570/600 limits. No engine, broker or model path.
"""
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

import stage087_off_data_scope as scope

SOFT,HARD=570,600


def sdk_preflight(bindings):
    d=scope.deps();m=d.minute
    if metadata.version('tqsdk')!='3.10.2'or any(os.environ.get(k)for k in m.safety.ENDPOINT_ENV):raise ValueError('sdk_or_endpoint_changed')
    username,password=m.safety.load_credentials();username=password=None
    verified=bindings.json(m.P018,m.P018_SHA)['source_fingerprints']
    sdk=Path(metadata.distribution('tqsdk').locate_file('tqsdk'))
    for path in [Path(m.core.__file__),Path(m.budget.__file__),*[sdk/name for name in
            ('api.py','auth.py','tradeable/sim/tqsim.py','backtest/backtest.py','tools/downloader.py')]]:
        bindings.bind(path,verified[str(path)])
    return dict(sdk_version='3.10.2',auth_checks_unmodified=True,soft_seconds=SOFT,hard_seconds=HARD,
        automatic_retry=False,provider_connections_max=1)


def prepare_packet(owner,current,*,family,packet_index=0,daily_references_path=None,daily_references_sha256=None,symbols=None):
    if family not in{'daily','minute'}or packet_index!=0:raise ValueError('one_packet_daily_or_minute_only')
    scope.read_actual_request(owner,current['path'],current['file_sha']);d=scope.deps();b=scope.Bindings()
    scope.owner_bindings(owner,current,b)
    packet=scope.request_directory(owner,current)/(family+'_packet')
    if packet.exists():raise FileExistsError('existing_packet_refusing_repeat')
    manifest=dict(schema='stage087_provider_packet_v1',family=family,packet_index=0,packet_count=1,
        owner_path=str(owner.path),owner_sha256=owner.sha256,request_path=str(current['path']),
        request_file_sha256=current['file_sha'],request_sha256=current['digest'],fixture_only=owner.fixture_allowed,
        independent_review_signed=False,response_written=False,financial_replays=0,orders=0)
    if family=='daily':
        contexts,missing,_,info=scope._daily_contexts(owner,current,b)
        if not symbols or not set(symbols).issubset(missing)or len(set(symbols))!=len(symbols):raise ValueError('daily_only_actual_missing_reference_subset')
        old_manifest=b.json(d.old.OLD/'input_manifest.json',d.frozen.OLD_MANIFEST_SHA)
        mapping=b.csv(d.old.MAPPING,old_manifest[str(d.old.MAPPING.relative_to(scope.ROOT))])
        calendar=d.pd.DatetimeIndex(d.pd.to_datetime(sorted(mapping.date.unique())))
        selected=d.daily.select_requirements(current['request'],symbols,calendar)
        targets=d.daily.database_targets(selected)
        manifest.update(daily_targets=targets.to_dict('records'),selected_symbols=sorted(symbols))
        # Inherited frozen DB identity; only actual selected target days are qualified.
        b.bind(d.daily.DATABASE,d.daily.DB_SHA)
        b.bind(d.daily.FROZEN_013,d.daily.FROZEN_013_SHA)
    else:
        path=Path(daily_references_path).absolute()
        if path!=scope.request_directory(owner,current)/'daily_references.json':raise ValueError('references_not_owned')
        refs=b.json(path,daily_references_sha256)
        if refs['owner_sha256']!=owner.sha256 or refs['request_sha256']!=current['digest']:raise ValueError('references_owner_or_request_changed')
        for source,digest in refs['source_fingerprints'].items():b.bind(source,digest)
        old_manifest=b.json(d.old.OLD/'input_manifest.json',d.frozen.OLD_MANIFEST_SHA)
        mapping=b.csv(d.old.MAPPING,old_manifest[str(d.old.MAPPING.relative_to(scope.ROOT))])
        calendar=d.pd.DatetimeIndex(d.pd.to_datetime(sorted(mapping.date.unique())))
        targets,info=d.minute.packet_targets(current['request'],calendar,0)
        refmap={(x['target']['vt_symbol'],x['target']['execution_trade_date'],x['target']['requirement_kind']):x for x in refs['contexts']}
        for target in targets:
            context=refmap[tuple(target[k]for k in ('vt_symbol','execution_trade_date','requirement_kind'))]
            if context['target']!=target:raise ValueError('packet_reference_actual_target_mismatch')
            target['daily_reference']=context['daily']
        manifest.update(targets=targets,**info,daily_references_path=str(path),daily_references_sha256=daily_references_sha256)
    sdk=sdk_preflight(b)if not owner.fixture_allowed else dict(fixture_only=True,no_credentials_or_SDK_preflight=True)
    manifest['input_sha256']=b.inputs
    packet.mkdir(parents=True,exist_ok=False)
    scope.atomic(packet/'packet_manifest.json',d.runtime.json_safe(manifest))
    b.bind(packet/'packet_manifest.json')
    scope.atomic(packet/'preflight.json',dict(schema='stage087_provider_preflight_v1',owner_sha256=owner.sha256,
        request_sha256=current['digest'],family=family,source_fingerprints=b.inputs,**sdk))
    return dict(status='prepared_no_network',packet_dir=str(packet),preflight_sha256=scope.sha(packet/'preflight.json'),family=family)


def read_packet(owner,packet):
    packet=Path(packet).absolute();b=scope.Bindings();manifest=b.json(packet/'packet_manifest.json')
    current=scope.read_actual_request(owner,manifest['request_path'],manifest['request_file_sha256'])
    if packet!=scope.request_directory(owner,current)/(manifest['family']+'_packet')or manifest['owner_sha256']!=owner.sha256:
        raise ValueError('provider_packet_scope_mismatch')
    preflight=b.json(packet/'preflight.json')
    if preflight.get('owner_sha256')!=owner.sha256 or preflight.get('request_sha256')!=current['digest']:raise ValueError('provider_preflight_owner_mismatch')
    for path,digest in preflight['source_fingerprints'].items():b.bind(path,digest)
    return manifest,current,preflight,b


def run_once(owner,packet):
    if owner.fixture_allowed or owner.document.get('fixture_only'):raise ValueError('fixture_owner_provider_forbidden')
    owner.verify()
    manifest,current,preflight,b=read_packet(owner,packet);packet=Path(packet);attempt=packet/'network_attempt1'
    if attempt.exists():raise FileExistsError('existing_provider_attempt_no_retry')
    scope.read_actual_request(owner,current['path'],current['file_sha'])
    if scope.remaining_engine_seconds(owner,current)<840:raise ValueError('public_provider_launch_reserve_budget_unavailable')
    probe=scope.Bindings();sdk_preflight(probe)
    for path,digest in probe.inputs.items():
        if preflight['source_fingerprints'].get(path)!=digest:raise ValueError('provider_sdk_preflight_drift')
    scope.read_actual_request(owner,current['path'],current['file_sha'])
    if scope.remaining_engine_seconds(owner,current)<840:raise ValueError('public_provider_launch_reserve_budget_unavailable')
    attempt.mkdir();scope.atomic(attempt/'attempt_started.json',dict(owner_sha256=owner.sha256,
        request_sha256=current['digest'],provider_attempts_max=1,soft_seconds=SOFT,hard_seconds=HARD,automatic_retry=False))
    began=time.monotonic();process=None;killed=False
    try:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--role','worker','--owner',str(owner.path),
            '--owner-sha256',owner.sha256,'--packet-dir',str(packet),'--parent-pid',str(os.getpid())],
            cwd=scope.ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:code=process.wait(timeout=HARD)
        except subprocess.TimeoutExpired:
            killed=True;os.killpg(process.pid,signal.SIGKILL);process.wait();code=-9
        unchanged=all(scope.sha(p)==h for p,h in preflight['source_fingerprints'].items())
        result=dict(status='hard_timeout'if killed else'worker_terminal',exit_code=code,hard_kill=killed,
            all_inputs_unchanged=unchanged,elapsed_seconds=time.monotonic()-began,request_sha256=current['digest'],
            owner_sha256=owner.sha256,preflight_sha256=scope.sha(packet/'preflight.json'),provider_attempts_max=1,
            automatic_retry=False,financial_replays=0,orders=0,cancels=0,broker_or_ctp_connections=0,
            credential_values_saved=False,old_CSV_or_DB_written=False,independent_review_signed=False,response_written=False,
            artifact_sha256={str(p.relative_to(attempt)):scope.sha(p)for p in attempt.rglob('*')if p.is_file()})
        scope.atomic(attempt/'parent_receipt.json',result)
        if code!=0 or not unchanged:raise ValueError('provider_worker_failed')
        return dict(status=result['status'],exit_code=code,all_inputs_unchanged=unchanged)
    finally:
        if process is not None and process.poll()is None:os.killpg(process.pid,signal.SIGKILL);process.wait()


def _minute_worker(manifest,attempt):
    d=scope.deps();m=d.minute
    expected={row['vt_symbol']:row['required_timestamps']for row in manifest['targets']}
    collector=m.core.BatchCollector(expected);api=None;sim_created=False;started=False;status='initializing';finished=()
    diagnostic=dict(phase='initializing');began=time.monotonic()
    with open(os.devnull,'w')as discard,redirect_stdout(discard),redirect_stderr(discard):
        logging.disable(logging.CRITICAL)
        try:
            from tqsdk import TqApi,TqAuth,TqSim,TqBacktest,BacktestFinished
            finished=(BacktestFinished,);username,password=m.safety.load_credentials()
            sim=TqSim();sim_created=True;started=True
            api=TqApi(account=sim,auth=TqAuth(username,password),backtest=TqBacktest(
                start_dt=datetime.fromisoformat(manifest['provider_start']),end_dt=datetime.fromisoformat(manifest['provider_end'])),
                debug=False,web_gui=False);username=password=None;serials={}
            async def subscribe():
                for symbol in sorted(expected):
                    native,exchange=symbol.split('.');serials[symbol]=api.get_kline_serial(exchange+'.'+native,60,data_length=10000)
            api.create_task(subscribe())
            status=m.budget.collect_with_budget(api,collector,serials,began,diagnostic,lambda:m.save(attempt,collector,diagnostic))
        except finished:status='provider_finished'
        except BaseException as error:
            status='provider_or_local_failed';scope.atomic(attempt/'safe_error.json',m.safety.safe_error(error))
        finally:
            m.save(attempt,collector,diagnostic)
            if api is not None:
                try:api.close()
                except BaseException:status='close_failed'
    raw,evidence=collector.frames();raw=d.old.normal_times(raw)
    proof=scope._proofs(raw,d.old.normal_times(evidence),network=True)
    checks=[m.qualify_target(raw,proof,target)for target in manifest['targets']]
    accepted=all(row['accepted']for row in checks)
    scope.atomic(attempt/'quality.json',d.runtime.json_safe(dict(accepted=accepted,targets=checks)))
    return dict(status=status,accepted=accepted,provider_connections_attempted=int(started),TqSim_created=sim_created,
        completed_minutes=len(raw),target_minutes=collector.target_count)


def _daily_worker(manifest,attempt):
    d=scope.deps();prior=d.daily;api=None;started=False;sim_created=False;began=time.monotonic()
    targets=d.pd.DataFrame(manifest['daily_targets']);receipts=[];qualified=[];audits=[];status='initializing'
    def save():
        q=d.pd.concat(qualified,ignore_index=True)if qualified else d.pd.DataFrame(columns=prior.DAILY)
        a=d.pd.concat(audits,ignore_index=True)if audits else d.pd.DataFrame(columns=['vt_symbol','trade_date','accepted','reason'])
        prior.atomic_csv(attempt/'qualified_daily.csv',q);prior.atomic_csv(attempt/'target_qualification.csv',a)
        (attempt/'symbol_receipts.json').write_bytes(scope.json_bytes(receipts))
    with open(os.devnull,'w')as discard,redirect_stdout(discard),redirect_stderr(discard):
        logging.disable(logging.CRITICAL)
        try:
            from tqsdk import TqApi,TqAuth,TqSim
            username,password=prior.safety.load_credentials();prior.budget_guard(began)
            sim=TqSim();sim_created=True;started=True
            api=TqApi(account=sim,auth=TqAuth(username,password),debug=False,web_gui=False);username=password=None
            for symbol,group in targets.groupby('vt_symbol',sort=True):
                prior.budget_guard(began);native,exchange=symbol.split('.');holder={}
                async def subscribe():holder['serial']=api.get_kline_serial(exchange+'.'+native,86400,data_length=10000)
                api.create_task(subscribe());symbol_began=time.monotonic()
                while 'serial'not in holder or not api.is_serial_ready(holder['serial']):
                    prior.budget_guard(began)
                    if time.monotonic()-symbol_began>85:raise TimeoutError('symbol_initialization_timeout')
                    api.wait_update(deadline=time.time()+max(.01,min(10.,SOFT-(time.monotonic()-began))))
                snapshot=holder['serial'].reindex(columns=prior.RAW).copy();path=attempt/'raw'/exchange/(native+'.csv')
                prior.atomic_csv(path,snapshot);q,a=prior.qualify_daily_snapshot(symbol,snapshot,group)
                qualified.append(q);audits.append(a)
                receipts.append(dict(vt_symbol=symbol,tq_symbol=exchange+'.'+native,raw_path=str(path),raw_sha256=scope.sha(path),
                    raw_rows=len(snapshot),target_days=len(group),accepted_days=len(q),rejected_days=len(a)-len(q),database_closeOI='N/A_not_independently_available'))
                save()
            status='completed_all_targets_qualified'if sum(map(len,qualified))==len(targets)else'completed_with_rejections'
        except BaseException as error:
            status='provider_or_local_failed';scope.atomic(attempt/'safe_error.json',prior.safety.safe_error(error))
        finally:
            save()
            if api is not None:
                try:api.close()
                except BaseException:status='close_failed'
    return dict(status=status,accepted=status=='completed_all_targets_qualified',provider_connections_attempted=int(started),
        TqSim_created=sim_created,target_days=len(targets),accepted_days=sum(map(len,qualified)),peak_memory_bytes=prior.peak_memory())


def worker(owner,packet,parent_pid):
    if owner.fixture_allowed or owner.document.get('fixture_only'):raise ValueError('fixture_owner_provider_forbidden')
    manifest,current,preflight,b=read_packet(owner,packet);attempt=Path(packet)/'network_attempt1'
    if os.getppid()!=parent_pid or not(attempt/'attempt_started.json').is_file():raise ValueError('true_provider_parent_required')
    result=_daily_worker(manifest,attempt)if manifest['family']=='daily'else _minute_worker(manifest,attempt)
    result.update(owner_sha256=owner.sha256,request_sha256=current['digest'],automatic_retry=False,financial_replays=0,
        orders=0,cancels=0,broker_or_ctp_connections=0,model_fits=0,credential_values_saved=False,old_CSV_or_DB_written=False,
        independent_review_signed=False,response_written=False,production_qualified=False)
    scope.atomic(attempt/'worker_receipt.json',scope.deps().runtime.json_safe(result))
    if not result['accepted']:raise ValueError('target_qualification_failed')
    return dict(status=result['status'],accepted=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--role',choices=['prepare','run','worker'],required=True)
    p.add_argument('--owner',type=Path,required=True);p.add_argument('--owner-sha256',required=True)
    p.add_argument('--request',type=Path);p.add_argument('--request-file-sha256');p.add_argument('--family',choices=['daily','minute'])
    p.add_argument('--symbols',nargs='+');p.add_argument('--daily-references',type=Path);p.add_argument('--daily-references-sha256')
    p.add_argument('--packet-dir',type=Path);p.add_argument('--parent-pid',type=int);args=p.parse_args()
    owner=scope.load_owner(args.owner,args.owner_sha256)
    if args.role=='prepare':
        current=scope.read_actual_request(owner,args.request,args.request_file_sha256)
        result=prepare_packet(owner,current,family=args.family,symbols=args.symbols,
            daily_references_path=args.daily_references,daily_references_sha256=args.daily_references_sha256)
    elif args.role=='run':result=run_once(owner,args.packet_dir)
    else:result=worker(owner,args.packet_dir,args.parent_pid)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='blocked',error_type=type(error).__name__,error=str(error),response_written=False),ensure_ascii=False));raise SystemExit(1)
