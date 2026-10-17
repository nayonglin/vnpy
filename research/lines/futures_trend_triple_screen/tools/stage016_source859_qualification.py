"""Scoped research correction of source859 full sessions; build only after AP review."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import io
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd

import stage002_local_minute_overlay as old
import stage011_needed_local_completed as prior
import stage015_daily_recovered_minute_delta as delta015

ROOT,LINE,PROJECT=old.ROOT,old.LINE,old.PROJECT
OUTPUT=LINE/'outputs/stage016_source859_qualification'
PROTOCOL=LINE/'stages/20261018_0044_stage016_source859_full_session_qualification_protocol.md'
S015=LINE/'outputs/stage015_daily_recovered_minute_delta'
R015=LINE/'outputs/stage015_independent_review/delta_checks.json'
S018=LINE/'outputs/stage018_provider_wait_budget'
R018=LINE/'outputs/stage018_independent_review/review_receipt.json'
S010=LINE/'outputs/stage010_reachable_demand'
EXPECTED_DEMAND='670766157d0ed3973080b793bedd88978dda0f8a44de07f243d773718f2dafba'
SOURCE859='stage859_tqsdk_backtest'
FIELDS=prior.COLUMNS
TARGETS={('cu2010.SHFE','2020-08-27'):(284,'local_0382'),
    ('fu2205.SHFE','2022-03-30'):(225,'local_0527'),
    ('AP210.CZCE','2022-04-06'):(225,'stage018_independently_reviewed'),
    ('cu2507.SHFE','2025-06-11'):(1,'local_0492')}


def keyset(frame):
    return {(str(row.vt_symbol),pd.Timestamp(row.bar_datetime))for row in frame[['vt_symbol','bar_datetime']].itertuples(index=False)}


def normal(frame):
    result=old.normal_times(frame)
    if old.minute_keys(result).has_duplicates:raise ValueError('duplicate_minute_key')
    return result


def same_values(left,right):return bool(np.array_equal(np.asarray(left,dtype=float),np.asarray(right,dtype=float)))


def prepare_delta(existing,reference,allowed_keys,source_id,source_sha):
    """Plan only exact old source859 changes; everything else must match."""
    existing=normal(existing);reference=normal(reference)
    allowed_keys=set(allowed_keys)
    if keyset(reference)!=allowed_keys:raise ValueError('full_completed_reference_scope_incomplete')
    if not keyset(existing).issubset(allowed_keys):raise ValueError('existing_scope_outside_allowed_full_grids')
    previous={(str(row.vt_symbol),pd.Timestamp(row.bar_datetime)):row._asdict()for row in existing.itertuples(index=False)}
    corrections=[];appended=[]
    for row in reference.to_dict('records'):
        key=(str(row['vt_symbol']),pd.Timestamp(row['bar_datetime']));before=previous.get(key)
        reference_id=str(row.get('reference_source_id',source_id));reference_sha=str(row.get('reference_source_sha256',source_sha))
        if before is None:
            appended.append({**{name:row[name]for name in FIELDS},'reference_source_id':reference_id,
                'reference_source_sha256':reference_sha,'minute_source':'stage016_reviewed_completed_append'})
            continue
        different=not same_values([before[name]for name in old.VALUES],[row[name]for name in old.VALUES])
        is859=(before.get('minute_source')==SOURCE859 and before.get('origin_kind','base')=='base')
        if not is859:
            if different:raise ValueError(f'non859_existing_conflict:{key}')
            continue
        if float(before['open'])!=float(row['open'])or float(before['open_oi'])!=float(row['open_oi']):
            raise ValueError(f'source859_open_or_openOI_changed:{key}')
        if different:
            record=dict(vt_symbol=key[0],bar_datetime=key[1],old_source=SOURCE859,
                reference_source_id=reference_id,reference_source_sha256=reference_sha)
            for name in old.VALUES:record['old_'+name]=float(before[name]);record['new_'+name]=float(row[name])
            corrections.append(record)
    columns=['vt_symbol','bar_datetime','old_source','reference_source_id','reference_source_sha256',
        *[prefix+name for name in old.VALUES for prefix in ['old_','new_']]]
    return pd.DataFrame(corrections,columns=columns),pd.DataFrame(appended,columns=[*FIELDS,'reference_source_id','reference_source_sha256','minute_source'])


def apply_delta(existing,corrections,appended,allowed_keys):
    """Fail on stale old values/source; append never replaces an existing key."""
    result=normal(existing).copy();corrections=normal(corrections);appended=normal(appended)
    allowed_keys=set(allowed_keys)
    if not(keyset(corrections)|keyset(appended)).issubset(allowed_keys):raise ValueError('delta_key_outside_qualified_scope')
    if keyset(corrections)&keyset(appended):raise ValueError('correction_append_overlap')
    index={(str(row.vt_symbol),pd.Timestamp(row.bar_datetime)):i for i,row in enumerate(result.itertuples(index=False))}
    result=result.reset_index(drop=True)
    for row in corrections.to_dict('records'):
        key=(str(row['vt_symbol']),pd.Timestamp(row['bar_datetime']));i=index.get(key)
        if i is None or 'minute_source'not in result or row['old_source']!=SOURCE859 or result.at[i,'minute_source']!=SOURCE859:
            raise ValueError('old_value_or_source_changed')
        if not same_values(result.loc[i,old.VALUES],[row['old_'+name]for name in old.VALUES]):
            raise ValueError('old_value_or_source_changed')
        if row['new_open']!=row['old_open']or row['new_open_oi']!=row['old_open_oi']:
            raise ValueError('open_or_openOI_correction_not_allowed')
        result.loc[i,old.VALUES]=[row['new_'+name]for name in old.VALUES]
        result.at[i,'minute_source']='stage016_reviewed_source859_correction'
    if keyset(appended)&set(index):raise ValueError('append_key_already_exists')
    appended=appended.copy();appended['bar_date']=appended.bar_datetime.dt.normalize()
    if 'bar_date'not in result:result['bar_date']=result.bar_datetime.dt.normalize()
    return pd.concat([result,appended],ignore_index=True,sort=False).sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)


def changed_key_intersection(corrections,appended,used_keys):
    keys=keyset(corrections)|keyset(appended);intersection=sorted(keys&set(used_keys))
    return dict(changed_keys=len(keys),replacement_keys=len(corrections),appended_keys=len(appended),deleted_keys=0,
        intersection_count=len(intersection),intersection_examples=[(symbol,stamp.isoformat())for symbol,stamp in intersection[:10]])


@dataclass
class QualifiedDelta:
    corrections: pd.DataFrame
    appended: pd.DataFrame
    allowed_keys: set
    review_accepted: bool=False
    all_four_sessions_qualified: bool=False


def read_qualified_delta(summary_path,summary_sha256,review_path,review_sha256):
    """Consumer must pin an independent qualification, not trust builder success."""
    inputs={};summary=prior.bound_json(Path(summary_path),summary_sha256,inputs)
    review=prior.bound_json(Path(review_path),review_sha256,inputs)
    if not review.get('qualified_research_source859_delta')or review.get('p0_findings',0)or review.get('p1_findings',0):
        raise ValueError('full_session_qualification_missing')
    if review.get('source_summary_sha256')!=summary_sha256 or summary.get('qualified_full_sessions')!=4:
        raise ValueError('full_session_qualification_missing')
    if not summary.get('all_inputs_unchanged')or not summary['a0_path_equivalence']['path_equivalent']:
        raise ValueError('delta_source_or_A0_guard_not_passed')
    folder=Path(summary_path).parent
    manifest=prior.bound_json(folder/'input_manifest.json',summary['artifact_sha256']['input_manifest.json'],inputs)
    for path,digest in manifest.items():
        if old.sha256(path)!=digest:raise ValueError('qualified_original_input_changed')
    frames={name:prior.read_bound_csv(folder/name,summary['artifact_sha256'][name],inputs)
        for name in ['corrections.csv','append_only.csv']}
    allowed=set();sessions=set()
    for item in summary['qualified_sessions']:
        sessions.add((item['vt_symbol'],item['trading_date']))
        allowed.update((item['vt_symbol'],pd.Timestamp(text))for text in item['expected_timestamps'])
    if sessions!=set(TARGETS):raise ValueError('full_session_qualification_missing')
    return QualifiedDelta(normal(frames['corrections.csv']),normal(frames['append_only.csv']),allowed,True,True)


@contextmanager
def temporary_qualified_minute_delta(s901,qualified):
    if not qualified.review_accepted or not qualified.all_four_sessions_qualified:
        raise ValueError('full_session_qualification_missing')
    original=s901._load_stage861_full_minute_bars
    names=('_FULL_MINUTE_BY_SYMBOL_CACHE','_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS','_LAST_MINUTE_AUDIT')
    saved={name:getattr(s901,name)for name in names}
    def load(symbols):
        frame=original(symbols)
        corrections=qualified.corrections.loc[qualified.corrections.vt_symbol.astype(str).isin(symbols)].copy()
        appended=qualified.appended.loc[qualified.appended.vt_symbol.astype(str).isin(symbols)].copy()
        return apply_delta(frame,corrections,appended,qualified.allowed_keys)
    s901._load_stage861_full_minute_bars=load
    s901._FULL_MINUTE_BY_SYMBOL_CACHE=None;s901._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS=set()
    try:yield
    finally:
        s901._load_stage861_full_minute_bars=original
        for name,value in saved.items():setattr(s901,name,value)


def stream_existing(paths,grids,inputs):
    wanted={symbol:set()for symbol,_ in grids}
    for(symbol,_),grid in grids.items():wanted[symbol].update(grid)
    pieces=[];audits=[]
    for path,digest in paths.items():
        path=Path(path);columns=[*FIELDS,'minute_source']if path==old.CACHE else FIELDS
        with path.open('rb')as handle:
            reader=delta015.HashingReader(handle)
            with io.BufferedReader(reader)as stream:
                for chunk in pd.read_csv(stream,usecols=columns,chunksize=200000):
                    selected=chunk.loc[chunk.vt_symbol.isin(wanted)].copy()
                    if selected.empty:continue
                    selected=normal(selected)
                    for symbol,group in selected.groupby('vt_symbol',sort=False):
                        hit=group.loc[group.bar_datetime.isin(wanted[str(symbol)])].copy()
                        if len(hit):
                            hit['origin_kind']='base'if path==old.CACHE else str(path)
                            if path!=old.CACHE:hit['minute_source']='previously_qualified_overlay'
                            pieces.append(hit)
            if reader.digest.hexdigest()!=digest:raise ValueError('original_minute_source_changed')
        inputs[str(path)]=digest;audits.append(dict(path=str(path),sha256=digest))
    result=normal(pd.concat(pieces,ignore_index=True))
    return result,audits


def reviewed_ap_reference(review_sha,grid,inputs):
    # No call to a provider, no fallback: these files must already exist and be
    # pinned by a separately supplied independent review receipt.
    review=prior.bound_json(R018,review_sha,inputs)
    if (review.get('p0_findings',0)or review.get('p1_findings',0)or review.get('qualified_precise_sessions',0)<1
        or not review.get('required_AP210_accepted')or not review.get('qualified_research_data')):
        raise ValueError('AP210_independent_full_session_qualification_missing')
    hashes=review.get('source_fingerprints',{})
    folder=S018/'network_attempt1'
    required=[folder/name for name in ['raw_completed_minutes.csv','completion_evidence.csv','quality.json','parent_receipt.json','worker_receipt.json']]
    if any(str(path)not in hashes for path in required):raise ValueError('AP210_review_required_asset_not_bound')
    for path,digest in hashes.items():
        if old.sha256(path)!=digest:raise ValueError('AP210_reviewed_source_changed')
        inputs[path]=digest
    parent=json.loads((folder/'parent_receipt.json').read_text());worker=json.loads((folder/'worker_receipt.json').read_text())
    if parent.get('exit_code')!=0 or not parent.get('all_inputs_unchanged')or worker.get('provider_attempts')!=1:
        raise ValueError('AP210_provider_receipt_not_accepted')
    quality=json.loads((folder/'quality.json').read_text())
    selected=[row for row in quality['sessions']if(row['vt_symbol'],row['execution_trade_date'])==('AP210.CZCE','2022-04-06')]
    if len(selected)!=1 or not selected[0]['accepted']or not selected[0]['completion_evidence_complete']:
        raise ValueError('AP210_independent_full_session_qualification_missing')
    raw=normal(pd.read_csv(folder/'raw_completed_minutes.csv'))
    raw=raw.loc[raw.vt_symbol.eq('AP210.CZCE')&raw.bar_datetime.isin(grid)].copy()
    evidence=pd.read_csv(folder/'completion_evidence.csv')
    proof={pd.Timestamp(row.bar_datetime)for row in evidence.itertuples()
        if row.vt_symbol=='AP210.CZCE'and str(row.completed).lower()=='true'
        and row.method=='observed_later_serial_kline'
        and pd.Timestamp(row.successor_time)>=pd.Timestamp(row.bar_datetime)+pd.Timedelta(minutes=1)}
    if len(raw)!=225 or not set(grid).issubset(proof):raise ValueError('AP210_completion_proof_missing')
    return raw,hashes[str(folder/'raw_completed_minutes.csv')]


def build(stage015_review_sha,stage018_review_sha):
    if OUTPUT.exists():raise FileExistsError('existing_source859_build_refusing_repeat')
    # AP independent qualification is required before even reserving a real build.
    if not R018.is_file():raise ValueError('AP210_independent_full_session_qualification_missing')
    inputs={};review015=prior.bound_json(R015,stage015_review_sha,inputs)
    if not review015.get('qualified_research_overlay')or review015.get('p0_findings',0)or review015.get('p1_findings',0):
        raise ValueError('stage015_inheritance_not_qualified')
    summary015=prior.bound_json(S015/'summary.json',review015['source_summary_sha256'],inputs)
    input015=prior.bound_json(S015/'input_manifest.json',summary015['artifact_sha256']['input_manifest.json'],inputs)
    def csv015(name):return prior.read_bound_csv(S015/name,summary015['artifact_sha256'][name],inputs)
    readiness=csv015('demand_readiness.csv')
    demand=prior.read_bound_csv(S010/'demand.csv',EXPECTED_DEMAND,inputs)
    for key in TARGETS:
        hit=demand.loc[demand.vt_symbol.eq(key[0])&demand.execution_trade_date.eq(key[1])]
        if len(hit)!=1 or hit.iloc[0].requirement_kind!='full_session':raise ValueError('fixed_source859_full_scope_changed')
    paths={old.CACHE:input015[str(old.CACHE)],prior.ACCEPTED/'overlay.csv':input015[str(prior.ACCEPTED/'overlay.csv')],
        prior.OUTPUT/'overlay.csv':input015[str(prior.OUTPUT/'overlay.csv')],S015/'overlay.csv':summary015['artifact_sha256']['overlay.csv']}
    source011=prior.bound_json(prior.OUTPUT/'source_manifest.json',input015[str(prior.OUTPUT/'source_manifest.json')],inputs)
    mapping=prior.read_bound_csv(old.MAPPING,input015[str(old.MAPPING)],inputs,usecols=['date'])
    calendar=pd.DatetimeIndex(pd.to_datetime(sorted(mapping.date.unique())))
    grids={key:old.session_grid(key[0],key[1],calendar)for key in TARGETS}
    ap,ap_sha=reviewed_ap_reference(stage018_review_sha,grids[('AP210.CZCE','2022-04-06')],inputs)
    old_manifest=prior.bound_json(old.OLD/'input_manifest.json',input015[str(old.OLD/'input_manifest.json')],inputs)
    references=[];session_rows=[]
    for key,(_,source_id)in TARGETS.items():
        symbol,day=key;grid=grids[key]
        if symbol=='AP210.CZCE':reference=ap.copy();reference_sha=ap_sha;source_path=str(S018/'network_attempt1/raw_completed_minutes.csv')
        else:
            matches=[row for row in source011['sources']if row['source_id']==source_id and row['status']=='accepted_source_bytes']
            if len(matches)!=1:raise ValueError('fixed_completed_reference_not_qualified')
            source=matches[0];source_path=source['path'];reference_sha=source['sha256']
            reference,audit=prior.read_bound_minute_source(Path(source_path),reference_sha,symbol)
            if reference is None:raise ValueError('completed_reference_bytes_changed')
            inputs[source_path]=reference_sha
            reference=reference.loc[reference.bar_datetime.isin(grid)].copy()
        native,exchange=symbol.rsplit('.',1)
        daily_path=PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04'/exchange/(native+'.csv')
        daily_sha=old_manifest.get(str(daily_path.relative_to(ROOT)))
        if not daily_sha:raise ValueError('original_daily_reference_not_bound')
        daily=prior.read_bound_csv(daily_path,daily_sha,inputs)
        daily=daily.loc[pd.to_datetime(daily.trade_date).dt.strftime('%Y-%m-%d').eq(day)]
        if len(daily)!=1:raise ValueError('original_daily_reference_not_unique')
        _,quality=old.validate_session(reference,grid,daily.iloc[0].to_dict(),pd.DataFrame(columns=FIELDS))
        if quality['status']!='accepted':raise ValueError(f'completed_session_not_qualified:{key}:{quality["reason"]}')
        reference=reference[FIELDS].copy();reference['reference_source_id']=source_id
        reference['reference_source_sha256']=reference_sha;references.append(reference)
        session_rows.append(dict(vt_symbol=symbol,trading_date=day,reference_source_id=source_id,
            reference_source_path=source_path,reference_source_sha256=reference_sha,daily_source_path=str(daily_path),
            daily_source_sha256=daily_sha,expected_minutes=len(grid),completed_price_qualified=True,
            source859_scope_keys=TARGETS[key][0],expected_timestamps=[stamp.isoformat()for stamp in grid]))
    for path in [Path(__file__),PROTOCOL,Path(old.__file__),Path(prior.__file__),Path(delta015.__file__),PROJECT/'qmt_roll_intraday_execution.py']:
        inputs[str(path)]=old.sha256(path)
    OUTPUT.mkdir(parents=True,exist_ok=False);began=time.monotonic()
    old.write_json(OUTPUT/'attempt_started.json',dict(started_at=datetime.now().astimezone(),financial_replays=0,downloads=0))
    try:
        existing,existing_audits=stream_existing(paths,grids,inputs)
        allowed={(symbol,stamp)for(symbol,_),grid in grids.items()for stamp in grid}
        reference=pd.concat(references,ignore_index=True)
        for key,(expected_count,_)in TARGETS.items():
            subset=existing.loc[existing.vt_symbol.eq(key[0])&existing.bar_datetime.isin(grids[key])]
            source_count=int((subset.minute_source.eq(SOURCE859)&subset.origin_kind.eq('base')).sum())
            if source_count!=expected_count:raise ValueError('fixed_source859_key_scope_changed')
        corrections,appended=prepare_delta(existing,reference,allowed,'per_row','per_row')
        corrected=apply_delta(existing,corrections,appended,allowed)
        if keyset(corrected)!=allowed:raise ValueError('corrected_full_sessions_incomplete')
        for key in TARGETS:
            hit=corrected.loc[corrected.vt_symbol.eq(key[0])&corrected.bar_datetime.isin(grids[key])].sort_values('bar_datetime')
            ref=reference.loc[reference.vt_symbol.eq(key[0])].sort_values('bar_datetime')
            if not same_values(hit[old.VALUES].to_numpy(),ref[old.VALUES].to_numpy()):raise ValueError('final_reference_equivalence_failed')
        anchors=prior.read_bound_csv(old.A0/'execution_anchor_requests.csv',input015[str(old.A0/'execution_anchor_requests.csv')],inputs)
        scans=prior.read_bound_csv(old.A0/'minute_scan_requests.csv',input015[str(old.A0/'minute_scan_requests.csv')],inputs)
        used={(str(row.vt_symbol),old.local_timestamp(row.expected_start))for row in anchors.itertuples()}
        for row in scans.itertuples():
            grid=old.session_grid(str(row.vt_symbol),row.trading_date,calendar)
            requested=grid[grid>=old.local_timestamp(row.requested_start)]
            if len(requested)!=int(row.expected_bar_count):raise ValueError('A0_scan_range_changed')
            used.update((str(row.vt_symbol),stamp)for stamp in requested)
        if(len(anchors),len(scans),len(used))!=(535,501,106731):raise ValueError('A0_actual_read_identity_changed')
        proof=changed_key_intersection(corrections,appended,used)
        proof.update(path_equivalent=proof['intersection_count']==0,distinct_actual_read_keys=len(used),
            anchor_request_rows=len(anchors),scan_request_rows=len(scans),
            reasoning='Every actual replacement and append key is disjoint from all recorded A0 anchor/scan reads; no deletion.')
        if not proof['path_equivalent']:raise ValueError('actual_changed_key_intersects_A0_reads')
        for row in session_rows:
            key=(row['vt_symbol'],row['trading_date']);grid=grids[key]
            row['actual_corrections']=int((corrections.vt_symbol.eq(key[0])&corrections.bar_datetime.isin(grid)).sum())
            row['append_only_minutes']=int((appended.vt_symbol.eq(key[0])&appended.bar_datetime.isin(grid)).sum())
        corrections.to_csv(OUTPUT/'corrections.csv',index=False);appended.to_csv(OUTPUT/'append_only.csv',index=False)
        old.write_json(OUTPUT/'session_qualification.json',session_rows);old.write_json(OUTPUT/'a0_path_equivalence.json',proof)
        before_ready=int(readiness.ready_after.sum())
        readiness['stage016_affected_full']=False
        readiness['stage016_price_qualification']='inherited_outside_this_review_scope'
        readiness['stage016_physical_missing_after']=pd.Series(pd.NA,index=readiness.index,dtype='Int64')
        readiness['stage016_anchor_present_after']=pd.Series(pd.NA,index=readiness.index,dtype='boolean')
        for symbol,day in TARGETS:
            mask=readiness.vt_symbol.eq(symbol)&readiness.execution_trade_date.eq(day)
            if int(mask.sum())!=1:raise ValueError('readiness_target_not_unique')
            readiness.loc[mask,'stage016_affected_full']=True
            readiness.loc[mask,'stage016_price_qualification']='completed_reference_qualified'
            readiness.loc[mask,'stage016_physical_missing_after']=0
            readiness.loc[mask,'stage016_anchor_present_after']=True
            readiness.loc[mask,'ready_after']=True
        readiness.to_csv(OUTPUT/'demand_readiness.csv',index=False)
        readiness.loc[~readiness.ready_after].to_csv(OUTPUT/'remaining_demand.csv',index=False)
        if not all(old.sha256(path)==digest for path,digest in inputs.items()):raise ValueError('input_changed_during_source859_build')
        old.write_json(OUTPUT/'input_manifest.json',inputs)
        summary=dict(status='built_source859_delta_pending_independent_review',elapsed_seconds=time.monotonic()-began,
            qualified_full_sessions=4,qualified_sessions=session_rows,source859_scope_keys=735,
            actual_replacement_keys=len(corrections),append_only_keys=len(appended),deleted_keys=0,
            non859_existing_keys_changed=0,open_or_openOI_changes=0,a0_path_equivalence=proof,
            ready_before_physical_coverage=before_ready,ready_after_physical_coverage=int(readiness.ready_after.sum()),
            inherited_ready_not_global_price_qualification=True,all_inputs_unchanged=True,
            original_base_sha256=paths[old.CACHE],existing_sources=existing_audits,
            stage018_independent_review_sha256=stage018_review_sha,stage015_independent_review_sha256=stage015_review_sha,
            financial_replays=0,downloads=0,account_engines=0,orders=0,cancels=0,model_fits=0,PnL_accessed=False,
            original_source_writes=0,production_qualified=False,
            consumer_independent_review_flag='qualified_research_source859_delta',
            limitations=['Only the four fixed source859 full sessions, not a global qualification of source859.',
                'Old base and all overlays remain immutable; FG209 anchor-only conflict remains isolated.',
                'Loader requires separate independent review and exact old-key value/source preconditions.',
                'No deployment, daily-open fallback or C0 attempt3 is authorized by this builder.'])
        summary['artifact_sha256']={path.name:old.sha256(path)for path in OUTPUT.iterdir()if path.is_file()}
        old.write_json(OUTPUT/'summary.json',summary)
        print(json.dumps({key:summary[key]for key in ['status','qualified_full_sessions','actual_replacement_keys','append_only_keys','ready_after_physical_coverage']}))
    except BaseException as error:
        old.write_json(OUTPUT/'build_failure.json',dict(error_type=type(error).__name__,error=str(error),financial_replays=0,downloads=0))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true',required=True)
    parser.add_argument('--stage015-review-sha256',required=True);parser.add_argument('--stage018-review-sha256',required=True)
    args=parser.parse_args();build(args.stage015_review_sha256,args.stage018_review_sha256)
