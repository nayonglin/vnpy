"""One ordinary latest-kline batch. Offline preparation never connects."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout,redirect_stderr
from datetime import datetime
from importlib import metadata
import json
import logging
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import time
import numpy as np
import pandas as pd

import stage002_local_minute_overlay as validation
import stage007_tqsdk_stream_probe as safety
import stage012_provider_batch as core

ROOT,LINE,PROJECT=validation.ROOT,validation.LINE,validation.PROJECT
OUTPUT=LINE/'outputs/stage019_normal_latest_batch'
ATTEMPT=OUTPUT/'network_attempt1'
PROTOCOL=LINE/'stages/20261018_0110_stage019_normal_latest10000_protocol.md'
S015=LINE/'outputs/stage015_daily_recovered_minute_delta'
R015=LINE/'outputs/stage015_independent_review/review_receipt.json'
R013=LINE/'outputs/stage013_independent_review/review_receipt.json'
R015_SHA='3512261d2191384f1099e7fbb77eda9622c9610ca855ad1d4607ad33e76552c9'
R013_SHA='194e48847c9e0927772c482cd5bacc3529a625ac76aeec2a157089924177c795'
SOFT,HARD,MEMORY=570,600,1_500_000_000


def capacity_bound(symbol,day,calendar,planning_date):
    """Conditional conservative bar upper bound, never a coverage certificate."""
    day=pd.Timestamp(day).normalize();now=pd.Timestamp(planning_date).normalize()
    next_work=(now+pd.offsets.BDay(1)).normalize()
    native=symbol.split('.')[0]
    match=re.fullmatch(r'([A-Za-z]+)(\d{3,4})',native)
    if not match:raise ValueError('unsupported_contract_code')
    product,digits=match.groups();month=int(digits[-2:])
    if len(digits)==4:year=2000+int(digits[:2])
    else:
        year=(day.year//10)*10+int(digits[0])
        if year<day.year-1:year+=10
    delivery_end=pd.Timestamp(year=year,month=month,day=1)+pd.offsets.MonthEnd(0)
    end=min(next_work,delivery_end)
    dates=pd.DatetimeIndex(calendar).normalize().drop_duplicates().sort_values()
    if end>dates[-1]:dates=dates.union(pd.bdate_range(dates[-1]+pd.Timedelta(days=1),end))
    count=int(((dates>=day)&(dates<=end)).sum())
    maximum=225 if product in {'AP','SM','lh','lc','si'}else 465 if product=='cu'else 555 if product=='au'else 345
    return dict(planning_endpoint=end.strftime('%Y-%m-%d'),session_count_upper=count,
        maximum_session_minutes=maximum,bars_upper=count*maximum+2,
        estimated_within_latest10000=bool(count>0 and day<=end and count*maximum+2<=10000))


def select_contracts(candidates,limit=8):
    counts={}
    for item in candidates:
        row=counts.setdefault(item['vt_symbol'],dict(vt_symbol=item['vt_symbol'],full=0,anchor=0))
        row['full'if item['original_requirement_kind']=='full_session'else'anchor']+=1
    ranking=sorted(counts.values(),key=lambda x:(-x['full'],-x['anchor'],x['vt_symbol']))
    return [r['vt_symbol']for r in ranking[:limit]],ranking


class LatestCollector:
    def __init__(self,expected):
        if not expected or len(expected)>8:raise ValueError('global_contract_limit')
        self.collectors={};self.target_count=0
        for symbol,times in expected.items():
            times=list(times);keys=[core.ns_value(t)for t in times]
            if len(keys)!=len(set(keys)):raise ValueError('duplicate_target_key')
            if len(keys)>10000:raise ValueError('per_symbol_target_limit')
            self.collectors[symbol]=core.BatchCollector({symbol:times})
            self.target_count+=len(keys)
        if self.target_count>80000:raise ValueError('global_minute_budget')

    def observe(self,symbol,serial):self.collectors[symbol].observe(symbol,serial,initial=True)

    def frames(self):
        frames=[c.frames()for c in self.collectors.values()]
        raw=pd.concat([f[0]for f in frames],ignore_index=True)
        evidence=pd.concat([f[1]for f in frames],ignore_index=True)
        if raw.duplicated(['vt_symbol','bar_datetime']).any()or evidence.duplicated(['vt_symbol','bar_datetime']).any():
            raise ValueError('duplicate_aggregate_key')
        return raw.sort_values(['vt_symbol','bar_datetime']),evidence.sort_values(['vt_symbol','bar_datetime'])


def prepare():
    if OUTPUT.exists():raise FileExistsError('existing_stage019_refusing_reselection')
    if validation.sha256(R015)!=R015_SHA or validation.sha256(R013)!=R013_SHA:
        raise ValueError('independent_review_changed')
    review15=json.loads(R015.read_text());review13=json.loads(R013.read_text())
    if not review15['qualified_research_overlay']or not review13['qualified_research_daily']:
        raise ValueError('prior_review_not_qualified')
    hashes={}
    def bind(path,expected=None):
        path=Path(path);digest=validation.sha256(path)
        if expected is not None and digest!=expected:raise ValueError('frozen_input_changed')
        hashes[str(path)]=digest;return path
    for path in [R015,R013]:bind(path)
    summary_path=bind(S015/'summary.json',review15['source_summary_sha256'])
    summary=json.loads(summary_path.read_text())
    remaining=bind(S015/'remaining_demand.csv',summary['artifact_sha256']['remaining_demand.csv'])
    old_path=bind(validation.OLD/'input_manifest.json');old=json.loads(old_path.read_text())
    bind(validation.MAPPING,old[str(validation.MAPPING.relative_to(ROOT))])
    calendar=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(validation.MAPPING,usecols=['date']).date).drop_duplicates().sort_values())
    original_calendar_end=calendar[-1].strftime('%Y-%m-%d')
    qualified_path=Path(review13['qualified_daily_path'])
    bind(qualified_path,review13['source_fingerprints'][str(qualified_path)])
    audit_path=Path(review13['target_qualification_path'])
    bind(audit_path,review13['source_fingerprints'][str(audit_path)])
    recovered=pd.read_csv(qualified_path).set_index(['vt_symbol','trade_date'],verify_integrity=True)
    quarantine=LINE/'outputs/stage011_needed_local_completed/quarantine.csv'
    bind(quarantine,review13['source_fingerprints'][str(quarantine)])
    q=pd.read_csv(quarantine);conflicts=set(zip(q.loc[q.reason.eq('base_overlap_conflict')].vt_symbol,
        q.loc[q.reason.eq('base_overlap_conflict')].execution_trade_date))
    frame=pd.read_csv(remaining);planning_date=datetime.now().astimezone().strftime('%Y-%m-%d')
    candidates=[];daily_cache={};skipped={};eligible_kinds={}
    def skip(reason):skipped[reason]=skipped.get(reason,0)+1
    for row in frame.itertuples():
        symbol,day=str(row.vt_symbol),str(row.execution_trade_date);key=(symbol,day)
        if str(row.real_daily_present).lower()!='true':skip('no_real_daily_carry');continue
        if key in conflicts:skip('known_base_overlap_conflict');continue
        bound=capacity_bound(symbol,day,calendar,planning_date)
        if not bound['estimated_within_latest10000']:skip('outside_conservative_latest_capacity');continue
        native,exchange=symbol.rsplit('.',1)
        path=PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04'/exchange/f'{native}.csv'
        if symbol not in daily_cache:
            if path.is_file():
                bind(path,old.get(str(path.relative_to(ROOT)),'not_in_original_manifest'))
                daily=pd.read_csv(path);daily['trade_date']=pd.to_datetime(daily.trade_date).dt.strftime('%Y-%m-%d')
                daily_cache[symbol]=daily
            else:daily_cache[symbol]=None
        daily=daily_cache[symbol];reference=None;reference_source=None
        if daily is not None:
            hit=daily.loc[daily.trade_date.eq(day)]
            if len(hit)==1 and all(k in hit and np.isfinite(float(hit.iloc[0][k]))for k in validation.VALUES)and daily.trade_date.gt(day).any():
                reference={k:float(hit.iloc[0][k])for k in validation.VALUES};reference_source=str(path)
        if reference is None and key in recovered.index:
            hit=recovered.loc[key]
            reference={k:float(hit[k])for k in validation.VALUES};reference_source=str(qualified_path)
        if reference is None:skip('missing_qualified_seven_field_completed_daily');continue
        grid=validation.session_grid(symbol,day,calendar)
        candidates.append(dict(vt_symbol=symbol,execution_trade_date=day,original_requirement_kind=str(row.requirement_kind),
            daily_reference=reference,daily_reference_path=reference_source,capacity_estimate=bound,
            expected_minutes=len(grid),expected_timestamps=[t.isoformat()for t in grid],
            session_start=grid[0].isoformat(),session_end_exclusive=(grid[-1]+pd.Timedelta(minutes=1)).isoformat()))
        eligible_kinds[str(row.requirement_kind)]=eligible_kinds.get(str(row.requirement_kind),0)+1
    symbols,ranking=select_contracts(candidates)
    targets=sorted([t for t in candidates if t['vt_symbol']in symbols],key=lambda x:(x['vt_symbol'],x['execution_trade_date']))
    expected={s:[stamp for t in targets if t['vt_symbol']==s for stamp in t['expected_timestamps']]for s in symbols}
    collector=LatestCollector(expected)
    manifest=dict(status='frozen_before_connection',planning_date=planning_date,planning_next_workday=str((pd.Timestamp(planning_date)+pd.offsets.BDay(1)).date()),
        mapping_actual_last_date=original_calendar_end,selection='full_desc_anchor_desc_code_asc_first8_conservative_latest10000',
        eligible_sessions=len(candidates),eligible_requirement_counts=eligible_kinds,skipped=skipped,ranking=ranking,
        contracts=symbols,targets=targets,target_sessions=len(targets),target_minutes=collector.target_count,
        selected_full_sessions=sum(t['original_requirement_kind']=='full_session'for t in targets),
        selected_anchor_sessions=sum(t['original_requirement_kind']=='anchor'for t in targets),
        per_symbol_target_minutes={s:len(v)for s,v in expected.items()},serial_data_length=10000,
        total_target_budget=80000,capacity_estimate_is_coverage_proof=False,collector='unchanged_stage012_per_symbol_observe_frames',
        input_sha256=hashes,protocol_sha256=validation.sha256(PROTOCOL),financial_replays=0,orders=0,PnL_accessed=False)
    OUTPUT.mkdir(exist_ok=False);validation.write_json(OUTPUT/'batch_manifest.json',manifest)
    return manifest


def read_manifest():
    manifest=json.loads((OUTPUT/'batch_manifest.json').read_text());expected={}
    for item in manifest['targets']:
        grid=pd.DatetimeIndex(item['expected_timestamps'])
        if len(grid)!=item['expected_minutes']or grid.has_duplicates:raise ValueError('target_grid_invalid')
        expected.setdefault(item['vt_symbol'],[]).extend(grid)
    collector=LatestCollector(expected)
    if collector.target_count!=manifest['target_minutes']:raise ValueError('target_budget_changed')
    return manifest,expected


def preflight():
    manifest,expected=read_manifest()
    if datetime.now().astimezone().strftime('%Y-%m-%d')!=manifest['planning_date']:raise ValueError('planning_date_expired')
    if metadata.version('tqsdk')!='3.10.2':raise ValueError('sdk_version_changed')
    if any(os.environ.get(k)for k in safety.ENDPOINT_ENV):raise ValueError('provider_endpoint_override')
    safety.load_credentials()
    prior=json.loads((core.OUTPUT/'preflight.json').read_text())['source_fingerprints']
    paths=[Path(__file__),PROTOCOL,OUTPUT/'batch_manifest.json',Path(core.__file__),Path(validation.__file__),Path(safety.__file__),core.OUTPUT/'preflight.json']
    if validation.sha256(Path(core.__file__))!=prior[str(Path(core.__file__))]:raise ValueError('frozen_collector_changed')
    sdk=Path(metadata.distribution('tqsdk').locate_file('tqsdk'))
    for name in ['api.py','auth.py','tradeable/sim/tqsim.py','tools/downloader.py']:
        path=sdk/name
        if validation.sha256(path)!=prior[str(path)]:raise ValueError('verified_sdk_changed')
        paths.append(path)
    for path,digest in manifest['input_sha256'].items():
        if validation.sha256(path)!=digest:raise ValueError('batch_input_changed')
        paths.append(Path(path))
    if validation.sha256(PROTOCOL)!=manifest['protocol_sha256']:raise ValueError('protocol_drift')
    return dict(status='passed_offline_preflight_no_connection',provider_connections=0,TqBacktest_instances=0,
        planned_TqApi_max=1,planned_TqSim_max=1,contracts=len(expected),target_sessions=len(manifest['targets']),
        target_minutes=manifest['target_minutes'],selected_full_sessions=manifest['selected_full_sessions'],
        selected_anchor_sessions=manifest['selected_anchor_sessions'],planning_date=manifest['planning_date'],
        planning_next_workday=manifest['planning_next_workday'],capacity_estimate_is_coverage_proof=False,
        soft_seconds=SOFT,hard_seconds=HARD,memory_budget_bytes=MEMORY,provider_attempts_max=1,
        normal_auth_checks_unmodified=True,credentials_present=True,credential_values_saved=False,
        initial_ready_all_symbols_is_terminal=True,false_wait_is_terminal=False,independent_string_series_only=True,
        source_fingerprints={str(p):validation.sha256(p)for p in paths},financial_replays=0,orders=0,PnL_accessed=False)


def peak_memory():
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform=='darwin'else value*1024)


def save(collector):
    raw,evidence=collector.frames()
    for name,frame in [('raw_completed_minutes.csv',raw),('completion_evidence.csv',evidence)]:
        temporary=ATTEMPT/(name+'.tmp');frame.to_csv(temporary,index=False);os.replace(temporary,ATTEMPT/name)
    validation.write_json(ATTEMPT/'progress.json',dict(completed_target_minutes=len(raw),target_minutes=collector.target_count,
        updated_at=datetime.now().astimezone().isoformat(),provider_attempts=1,financial_replays=0))


def collect_initial_snapshots(api,serials,collector,began,clock=time.monotonic,on_progress=None):
    observed=set();false_waits=0
    while True:
        if clock()-began>=SOFT:return dict(status='soft_time_budget_reached',observed=sorted(observed),false_waits=false_waits)
        if peak_memory()>MEMORY:raise MemoryError('memory_budget_reached')
        for symbol,serial in list(serials.items()):
            if symbol not in observed and api.is_serial_ready(serial):
                collector.observe(symbol,serial);observed.add(symbol)
                if on_progress:on_progress()
        if len(observed)==len(collector.collectors):
            return dict(status='all_initial_snapshots_observed',observed=sorted(observed),false_waits=false_waits)
        updated=api.wait_update(deadline=time.time()+min(30,max(.01,SOFT-(clock()-began))))
        if not updated:false_waits+=1


def qualify(collector,manifest):
    raw,evidence=collector.frames();raw=validation.normal_times(raw);empty=raw.iloc[:0].copy()
    proofs={(r.vt_symbol,pd.Timestamp(r.bar_datetime))for r in evidence.itertuples()
        if r.completed and pd.Timestamp(r.successor_time)>=pd.Timestamp(r.bar_datetime)+pd.Timedelta(minutes=1)}
    checks=[]
    for target in manifest['targets']:
        grid=pd.DatetimeIndex(target['expected_timestamps'])
        _,check=validation.validate_session(raw.loc[raw.vt_symbol.eq(target['vt_symbol'])],grid,target['daily_reference'],empty)
        proof=all((target['vt_symbol'],stamp)in proofs for stamp in grid)
        checks.append(dict(vt_symbol=target['vt_symbol'],execution_trade_date=target['execution_trade_date'],
            original_requirement_kind=target['original_requirement_kind'],accepted=bool(check['status']=='accepted'and proof),
            completion_evidence_complete=proof,**check))
    result=dict(sessions=checks,accepted_sessions=sum(c['accepted']for c in checks),target_sessions=len(checks),
        all_sessions_accepted=all(c['accepted']for c in checks),raw_rows=len(raw),
        qualification_scope='provider_subset_full_grid_seven_fields_no_existing_overlap_qualification_yet',
        cache_or_overlay_written=False,financial_replays=0,orders=0)
    validation.write_json(ATTEMPT/'quality.json',result);return result


def worker(parent_pid):
    if os.getppid()!=parent_pid or not(ATTEMPT/'attempt_started.json').is_file():return 2
    manifest,expected=read_manifest();collector=LatestCollector(expected)
    api=None;created=False;provider=False;status='initializing';result={};began=time.monotonic()
    with open(os.devnull,'w')as discard,redirect_stdout(discard),redirect_stderr(discard):
        logging.disable(logging.CRITICAL)
        try:
            from tqsdk import TqApi,TqAuth,TqSim
            username,password=safety.load_credentials();sim=TqSim();created=True;provider=True
            api=TqApi(account=sim,auth=TqAuth(username,password),debug=False,web_gui=False)
            username=password=None;serials={}
            async def subscribe():
                for symbol in manifest['contracts']:
                    native,exchange=symbol.rsplit('.',1)
                    serials[symbol]=api.get_kline_serial(f'{exchange}.{native}',60,data_length=10000)
            api.create_task(subscribe())
            result=collect_initial_snapshots(api,serials,collector,began,on_progress=lambda:save(collector))
            status=result['status']
        except BaseException as error:
            status='provider_or_local_failed';validation.write_json(ATTEMPT/'safe_error.json',safety.safe_error(error))
        finally:
            save(collector)
            if api is not None:
                try:api.close()
                except BaseException as error:
                    status='close_failed';validation.write_json(ATTEMPT/'safe_error.json',safety.safe_error(error))
    quality=qualify(collector,manifest)
    validation.write_json(ATTEMPT/'worker_receipt.json',dict(status=status,provider_attempts=int(provider),
        local_TqSim_created=created,TqBacktest_instances=0,observed_symbols=result.get('observed',[]),false_waits=result.get('false_waits',0),
        completed_target_minutes=quality['raw_rows'],target_minutes=collector.target_count,
        accepted_sessions=quality['accepted_sessions'],target_sessions=quality['target_sessions'],
        elapsed_seconds=time.monotonic()-began,peak_memory_bytes=peak_memory(),
        raw_sdk_output_saved=False,credential_values_saved=False,automatic_retry=False,
        financial_replays=0,orders=0,cancels=0,broker_or_ctp_connections=0,model_fits=0,
        old_source_writes=0,cache_or_overlay_written=False,production_qualified=False))
    return 0 if status=='all_initial_snapshots_observed'and quality['all_sessions_accepted']else 1


def run_once():
    if ATTEMPT.exists():raise FileExistsError('existing_stage019_attempt_refuse_retry')
    frozen=json.loads((OUTPUT/'preflight.json').read_text())
    if preflight()!=frozen:raise ValueError('preflight_drift')
    ATTEMPT.mkdir(exist_ok=False)
    validation.write_json(ATTEMPT/'attempt_started.json',dict(started_at=datetime.now().astimezone().isoformat(),
        provider_attempts_max=1,soft_seconds=SOFT,hard_seconds=HARD,automatic_retry=False,financial_replays=0,orders=0))
    began=time.monotonic();killed=False
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',str(os.getpid())],
        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:code=process.wait(timeout=HARD)
    except subprocess.TimeoutExpired:
        killed=True;os.killpg(process.pid,signal.SIGKILL);process.wait();code=-9
    changed=[path for path,digest in frozen['source_fingerprints'].items()if validation.sha256(path)!=digest]
    validation.write_json(ATTEMPT/'parent_receipt.json',dict(status='worker_terminal',exit_code=code,hard_kill=killed,
        elapsed_seconds=time.monotonic()-began,all_inputs_unchanged=not changed,changed_input_paths=changed,
        provider_attempts_max=1,automatic_retry=False,financial_replays=0,orders=0,TqBacktest_instances=0,
        raw_sdk_output_saved=False,credential_values_saved=False,cache_or_overlay_written=False,production_qualified=False))
    print(json.dumps(dict(exit_code=code,hard_kill=killed,all_inputs_unchanged=not changed)))
    return code


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--preflight',action='store_true');parser.add_argument('--run',action='store_true');parser.add_argument('--worker',type=int)
    args=parser.parse_args()
    if args.worker is not None:raise SystemExit(worker(args.worker))
    if args.prepare:result=prepare()
    elif args.preflight:
        if(OUTPUT/'preflight.json').exists():raise FileExistsError('preflight_already_exists')
        result=preflight();validation.write_json(OUTPUT/'preflight.json',result)
    elif args.run:raise SystemExit(run_once())
    else:parser.error('choose --prepare, --preflight or --run')
    print(json.dumps({k:result[k]for k in ['status','contracts','target_sessions','target_minutes','selected_full_sessions','selected_anchor_sessions']}))
