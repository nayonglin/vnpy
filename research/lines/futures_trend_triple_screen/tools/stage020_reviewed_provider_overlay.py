"""One offline append-only integration of explicitly reviewed provider sessions."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime
import json
from pathlib import Path
import time
import pandas as pd

import stage002_local_minute_overlay as old
import stage011_needed_local_completed as prior
import stage015_daily_recovered_minute_delta as delta015
import stage016_source859_qualification as delta016

LINE=old.LINE
OUTPUT=LINE/'outputs/stage020_reviewed_provider_overlay'
PROTOCOL=LINE/'stages/20261018_0114_stage020_reviewed_provider_overlay_protocol.md'
S016=delta016.OUTPUT
R016=LINE/'outputs/stage016_independent_review/review_receipt.json'
PROVIDERS={
    'stage018':(LINE/'outputs/stage018_provider_wait_budget',LINE/'outputs/stage018_independent_review/review_receipt.json'),
    'stage019':(LINE/'outputs/stage019_normal_latest_batch',LINE/'outputs/stage019_independent_review/review_receipt.json')}
R018_SHA='b7820471cc7d84963251182b8d10cf26e82cfc009a45e70ac9a7184ab39cd0cf'
FIELDS=prior.COLUMNS


def keys(frame):
    return {(str(r.vt_symbol),pd.Timestamp(r.bar_datetime))for r in frame[['vt_symbol','bar_datetime']].itertuples(index=False)}


def select_reviewed_targets(manifest,review,quality,excluded_sessions):
    if not review.get('qualified_research_data')or review.get('p0_findings',0)or review.get('p1_findings',0):
        raise ValueError('provider_independent_data_qualification_missing')
    bykey={};checked={}
    for row in manifest['targets']:
        key=(str(row['vt_symbol']),str(row['execution_trade_date']))
        if key in bykey:raise ValueError('duplicate_provider_target')
        bykey[key]=row
    for row in quality['sessions']:
        key=(str(row['vt_symbol']),str(row['execution_trade_date']))
        if key in checked:raise ValueError('duplicate_quality_target')
        checked[key]=row
    selected=[];excluded=[];seen=set()
    for row in review['accepted_sessions']:
        key=(str(row['vt_symbol']),str(row['execution_trade_date']))
        if key in seen or key not in bykey:raise ValueError('review_scope_not_unique_subset_of_manifest')
        seen.add(key);check=checked.get(key,{})
        if row.get('accepted')is not True or not check.get('accepted')or not check.get('completion_evidence_complete'):
            raise ValueError('review_scope_not_accepted_by_quality')
        (excluded if key in excluded_sessions else selected).append(bykey[key])
    if not seen:raise ValueError('review_has_no_accepted_sessions')
    return selected,excluded


def qualify_append_session(sources,grid,daily,existing,stage016_keys):
    scoped={(str(r.vt_symbol),pd.Timestamp(r.bar_datetime))for frame in sources.values()
        for r in frame.loc[frame.bar_datetime.isin(grid),['vt_symbol','bar_datetime']].itertuples(index=False)}
    if scoped&stage016_keys:raise ValueError('candidate_intersects_stage016_owned_grid')
    return prior.qualify_needed_session(sources,grid,daily,existing,'full_session')


def assert_new_keys(overlay,existing,allowed,stage016_keys,a0_keys):
    if old.minute_keys(overlay).has_duplicates:raise ValueError('duplicate_overlay_key')
    actual=keys(overlay)
    if not actual.issubset(allowed):raise ValueError('overlay_outside_reviewed_scope')
    if actual&keys(existing):raise ValueError('append_overlay_intersects_existing')
    if actual&stage016_keys:raise ValueError('append_overlay_intersects_stage016_scope')
    if actual&a0_keys:raise ValueError('append_overlay_intersects_A0_reads')


def read_provider(label,review_sha,excluded_sessions,inputs):
    root,review_path=PROVIDERS[label];folder=root/'network_attempt1'
    review=prior.bound_json(review_path,review_sha,inputs)
    hashes=review.get('source_fingerprints',{})
    required=[root/'batch_manifest.json',root/'preflight.json',*[folder/name for name in
        ['raw_completed_minutes.csv','completion_evidence.csv','quality.json','parent_receipt.json','worker_receipt.json']]]
    if any(str(path)not in hashes for path in required):raise ValueError('review_required_provider_asset_not_bound')
    delta015.bind_review_sources(review,inputs)
    manifest=json.loads((root/'batch_manifest.json').read_text())
    quality=json.loads((folder/'quality.json').read_text())
    parent=json.loads((folder/'parent_receipt.json').read_text());worker=json.loads((folder/'worker_receipt.json').read_text())
    if parent.get('status')!='worker_terminal'or parent.get('hard_kill')is not False or not parent.get('all_inputs_unchanged'):
        raise ValueError('provider_terminal_unchanged_inputs_required')
    if worker.get('provider_attempts')!=1 or worker.get('status')not in {
        'all_target_minutes_completed','all_initial_snapshots_observed','soft_time_budget_reached','provider_finished'}:
        raise ValueError('provider_partial_exception_or_unfinished_write_not_accepted')
    selected,excluded=select_reviewed_targets(manifest,review,quality,excluded_sessions)
    raw=old.normal_times(pd.read_csv(folder/'raw_completed_minutes.csv'))
    evidence=pd.read_csv(folder/'completion_evidence.csv')
    proofs={(str(row.vt_symbol),pd.Timestamp(row.bar_datetime))for row in evidence.itertuples(index=False)
        if str(row.completed).lower()=='true'and row.method=='observed_later_serial_kline'
        and pd.Timestamp(row.successor_time)>=pd.Timestamp(row.bar_datetime)+pd.Timedelta(minutes=1)}
    frames={};targets=[]
    preflight=json.loads((root/'preflight.json').read_text())
    source_hashes={**preflight.get('source_fingerprints',{}),**hashes}
    for target in selected:
        symbol=str(target['vt_symbol']);day=str(target['execution_trade_date']);grid=pd.DatetimeIndex(target['expected_timestamps'])
        if grid.has_duplicates or len(grid)!=target['expected_minutes']:raise ValueError('reviewed_grid_invalid')
        if not{(symbol,stamp)for stamp in grid}.issubset(proofs):raise ValueError('reviewed_completion_proof_missing')
        frame=raw.loc[raw.vt_symbol.eq(symbol)&raw.bar_datetime.isin(grid),FIELDS].copy()
        if len(frame)!=len(grid)or old.minute_keys(frame).has_duplicates:raise ValueError('reviewed_raw_grid_not_unique_complete')
        daily_path=Path(target.get('daily_csv_path')or target['daily_reference_path'])
        daily=prior.read_bound_csv(daily_path,source_hashes.get(str(daily_path)),inputs)
        daily=daily.loc[pd.to_datetime(daily.trade_date).dt.strftime('%Y-%m-%d').eq(day)]
        if 'vt_symbol'in daily:daily=daily.loc[daily.vt_symbol.eq(symbol)]
        if len(daily)!=1:raise ValueError('reviewed_daily_identity_not_unique')
        reference=daily.iloc[0].to_dict()
        if not delta016.same_values([reference[name]for name in old.VALUES],
                                   [target['daily_reference'][name]for name in old.VALUES]):
            raise ValueError('manifest_daily_reference_changed')
        source_id=label+'_independently_reviewed'
        frames[(symbol,day)]={source_id:frame}
        targets.append(dict(target,reference=reference,provider_label=label))
    return targets,frames,[dict(item,exclusion_reason='stage016_owned_full_session',provider_label=label)for item in excluded],dict(
        provider_label=label,review_path=str(review_path),review_sha256=review_sha,parent_exit_code=parent['exit_code'],
        parent_status=parent['status'],worker_status=worker['status'],review_accepted_sessions=len(review['accepted_sessions']),
        selected_sessions=len(selected),stage016_excluded_sessions=len(excluded))


def build(stage016_review_sha,stage019_review_sha):
    if OUTPUT.exists():raise FileExistsError('existing_stage020_refusing_repeat')
    inputs={};review016=prior.bound_json(R016,stage016_review_sha,inputs)
    summary_sha=review016['source_summary_sha256']
    # The existing consumer performs the independent qualification, full-source
    # hash and correction-scope gates without instantiating an engine.
    qualified=delta016.read_qualified_delta(S016/'summary.json',summary_sha,R016,stage016_review_sha)
    summary016=prior.bound_json(S016/'summary.json',summary_sha,inputs)
    input016=prior.bound_json(S016/'input_manifest.json',summary016['artifact_sha256']['input_manifest.json'],inputs)
    inputs.update(input016)
    for name in ['corrections.csv','append_only.csv']:
        inputs[str(S016/name)]=summary016['artifact_sha256'][name]
    readiness=prior.read_bound_csv(S016/'demand_readiness.csv',summary016['artifact_sha256']['demand_readiness.csv'],inputs)
    bykey={(str(r.vt_symbol),str(r.execution_trade_date)):r._asdict()for r in readiness.itertuples(index=False)}
    if len(bykey)!=len(readiness):raise ValueError('inherited_readiness_not_unique')
    owned=set(qualified.allowed_keys)
    if len(owned)!=1500:raise ValueError('stage016_full_scope_identity_changed')
    targets={};sources=defaultdict(dict);excluded=[];provider_audits=[]
    for label,digest in [('stage018',R018_SHA),('stage019',stage019_review_sha)]:
        rows,frames,ignored,audit=read_provider(label,digest,set(delta016.TARGETS),inputs)
        excluded.extend(ignored);provider_audits.append(audit)
        for row in rows:
            key=(str(row['vt_symbol']),str(row['execution_trade_date']))
            if key not in bykey:raise ValueError('provider_scope_outside_fixed_demand')
            if key in targets and(targets[key]['expected_timestamps']!=row['expected_timestamps']or
                not delta016.same_values([targets[key]['reference'][n]for n in old.VALUES],[row['reference'][n]for n in old.VALUES])):
                raise ValueError('provider_target_grid_or_daily_conflict')
            targets[key]=row;sources[key].update(frames[key])
    calendar_frame=prior.read_bound_csv(old.MAPPING,input016[str(old.MAPPING)],inputs,usecols=['date'])
    calendar=pd.DatetimeIndex(pd.to_datetime(sorted(calendar_frame.date.unique())))
    grids={key:old.session_grid(*key,calendar)for key in targets}
    requests=defaultdict(list)
    for key,grid in grids.items():
        if list(grid)!=list(pd.DatetimeIndex(targets[key]['expected_timestamps'])):raise ValueError('provider_grid_not_canonical_session')
        if {(key[0],stamp)for stamp in grid}&owned:raise ValueError('selected_grid_intersects_stage016_scope')
        requests[key[0]].extend(grid)
    requests={symbol:pd.DatetimeIndex(sorted(set(stamps)))for symbol,stamps in requests.items()}
    existing_paths={Path(item['path']):item['sha256']for item in summary016['existing_sources']}
    inputs.update({str(path):digest for path,digest in existing_paths.items()})
    for path in [Path(__file__),PROTOCOL,Path(old.__file__),Path(prior.__file__),Path(delta015.__file__),Path(delta016.__file__)]:
        inputs[str(path)]=old.sha256(path)
    OUTPUT.mkdir(parents=True,exist_ok=False);began=time.monotonic()
    old.write_json(OUTPUT/'attempt_started.json',dict(started_at=datetime.now().astimezone(),financial_replays=0,downloads=0))
    try:
        existing,existing_audits=delta015.stream_relevant_existing(existing_paths,requests)
        output=[];audits=[];updates={};empty=existing.iloc[:0].copy()
        for key in sorted(targets):
            symbol,day=key;grid=grids[key];target=targets[key]
            before=existing.loc[existing.vt_symbol.eq(symbol)&existing.bar_datetime.isin(grid)].copy()
            added,audit=qualify_append_session(sources[key],grid,target['reference'],before,owned)
            audit.update(vt_symbol=symbol,execution_trade_date=day,requirement_kind=bykey[key]['requirement_kind'])
            audits.append(audit)
            if audit['status']!='accepted':continue
            if len(added):
                added=added.copy();added['trading_date']=day;output.append(added)
            after=pd.concat([before,added],ignore_index=True,sort=False)
            updates[key]=dict(ready_after=prior.requirement_satisfied(after,grid,bykey[key]['requirement_kind']),
                session_missing_after=len(grid)-len(after),anchor_present_after=bool(grid[0]in set(after.bar_datetime)),
                stage020_added_minutes=len(added),stage020_price_qualification='reviewed_completed_session')
        overlay=pd.concat(output,ignore_index=True,sort=False)if output else empty.copy()
        anchors=prior.read_bound_csv(old.A0/'execution_anchor_requests.csv',input016[str(old.A0/'execution_anchor_requests.csv')],inputs)
        scans=prior.read_bound_csv(old.A0/'minute_scan_requests.csv',input016[str(old.A0/'minute_scan_requests.csv')],inputs)
        proof=old.prove_read_disjointness(overlay,anchors,scans,calendar)
        if(proof['anchor_request_rows'],proof['scan_request_rows'],proof['distinct_actual_read_keys'])!=(535,501,106731):
            raise ValueError('A0_read_identity_changed')
        allowed={(symbol,stamp)for(symbol,_),grid in grids.items()for stamp in grid}
        assert_new_keys(overlay,existing,allowed,owned,set())
        if proof['intersection_count']:raise ValueError('append_overlay_intersects_A0_reads')
        proof['stage016_all_scope_keys']=len(owned);proof['stage016_scope_intersection_count']=len(keys(overlay)&owned)
        merged=[]
        for row in readiness.to_dict('records'):
            key=(str(row['vt_symbol']),str(row['execution_trade_date']))
            row['stage020_checked']=key in targets
            row['stage020_price_qualification']='inherited_outside_this_review_scope'
            if key in updates:row.update(updates[key])
            merged.append(row)
        final=pd.DataFrame(merged);missing=final.loc[~final.ready_after.astype(str).str.lower().eq('true')]
        overlay=overlay.reindex(columns=[*FIELDS,'source_ids','trading_date']).sort_values(['vt_symbol','bar_datetime'])
        overlay.to_csv(OUTPUT/'overlay.csv',index=False)
        sessions=pd.DataFrame(audits)
        for name in ['source_ids','aggregate','daily_mismatch_fields']:
            if name in sessions:sessions[name]=sessions[name].map(lambda value:json.dumps(old.safe(value),ensure_ascii=False,sort_keys=True))
        sessions.to_csv(OUTPUT/'session_manifest.csv',index=False)
        sessions.loc[sessions.status.ne('accepted')].to_csv(OUTPUT/'quarantine.csv',index=False)
        old.write_json(OUTPUT/'excluded_stage016_sessions.json',excluded)
        final.to_csv(OUTPUT/'demand_readiness.csv',index=False);missing.to_csv(OUTPUT/'remaining_demand.csv',index=False)
        old.write_json(OUTPUT/'source_manifest.json',dict(providers=provider_audits,existing_scoped_read=existing_audits))
        old.write_json(OUTPUT/'a0_path_equivalence.json',proof)
        if any(old.sha256(path)!=digest for path,digest in inputs.items()):raise ValueError('source_changed_during_append_build')
        old.write_json(OUTPUT/'input_manifest.json',inputs)
        result=dict(status='built_reviewed_provider_overlay_pending_independent_review',elapsed_seconds=time.monotonic()-began,
            candidate_sessions=len(targets),accepted_sessions=int(sessions.status.eq('accepted').sum()),
            quarantine_reasons=dict(Counter(sessions.loc[sessions.status.ne('accepted'),'reason'])),
            excluded_stage016_sessions=len(excluded),added_minutes=len(overlay),existing_rows_changed=0,deleted_keys=0,
            stage016_scope_intersection_count=0,new_key_intersection_with_existing=0,a0_path_equivalence=proof,
            ready_before=int(readiness.ready_after.astype(str).str.lower().eq('true').sum()),ready_after=len(final)-len(missing),
            remaining_requirements=len(missing),inherited_ready_not_global_price_qualification=True,
            provider_terminal_receipts_preserved=provider_audits,all_inputs_unchanged=True,
            financial_replays=0,downloads=0,account_engines=0,orders=0,cancels=0,model_fits=0,PnL_accessed=False,
            original_source_writes=0,financial_metrics='N/A',production_qualified=False,
            limitations=['Only explicitly independently accepted provider session grids are integrated.',
                'Stage016 four full sessions are excluded; its correction loader stays outermost.',
                'Partial provider qualification does not change provider batch terminal status.',
                'Existing data and inherited unrelated readiness are retained; no C0 replay is authorized.'])
        result['artifact_sha256']={path.name:old.sha256(path)for path in OUTPUT.iterdir()if path.is_file()}
        old.write_json(OUTPUT/'summary.json',result)
        print(json.dumps({k:result[k]for k in ['status','candidate_sessions','accepted_sessions','added_minutes','ready_after']}))
    except BaseException as error:
        old.write_json(OUTPUT/'build_failure.json',dict(error_type=type(error).__name__,error=str(error),financial_replays=0,downloads=0))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true',required=True)
    parser.add_argument('--stage016-review-sha256',required=True);parser.add_argument('--stage019-review-sha256',required=True)
    args=parser.parse_args();build(args.stage016_review_sha256,args.stage019_review_sha256)
