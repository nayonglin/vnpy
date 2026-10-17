"""Offline independent resolver for one actual B request with no physical old keys.

No network, engine, model, provider execution, or response writer. The caller
must use the returned pinned provider/reader only within its own allowlist.
"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import argparse
import csv
import io
import json
import math
import sqlite3
import sys

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
import numpy as np
import pandas as pd
import stage002_local_minute_overlay as old
import stage011_needed_local_completed as local
import stage015_daily_recovered_minute_delta as daily013
import stage021_blocking_data_gate as gate
import stage037_b_ts_request_provider as original_provider

OUTPUT=LINE/'outputs/stage045_exact_request_resolver'
PROTOCOL=LINE/'stages/20261018_0415_stage045_exact_request_resolver_contract.md'
R013=LINE/'outputs/stage013_independent_review/review_receipt.json'
R013_SHA='194e48847c9e0927772c482cd5bacc3529a625ac76aeec2a157089924177c795'
OLD_MANIFEST_SHA='376cefaf2a56f75e97adf31e431dac508189695c4bb4691294ab5f950aeada03'
HELPERS={
    'stage002_local_minute_overlay.py':'33a30bc1e8f4f970532382da46c2bda790dfb6baac8beeca65abd759a6af50a3',
    'stage011_needed_local_completed.py':'e65f3696505f31490913af16909cc9d1f5fd74308b05a7a1e3dd242e37ee3488',
    'stage015_daily_recovered_minute_delta.py':'4f31ccb1ecf26ea83a21c073abff3e50afbea168d4af694451068122471a0bc4',
    'stage021_blocking_data_gate.py':'150dd70a264f360046f6d633829a4dff9a81c371c34bad6288e41a081bbb498b'}
SOURCE_MANIFESTS={
    LINE/'outputs/stage002_local_minute_overlay/attempt2/source_manifest.json':'318da737a0a9e041919fbe6687669de3bf3aadacdbf191232b11ec43c6feb1ed',
    LINE/'outputs/stage011_needed_local_completed/source_manifest.json':'51b5c86680b2de3a8f4d1abee58da667f6f395fe99e65a632da03d285bad5849'}
PROVIDERS={
    '037':(LINE/'tools/stage037_b_ts_request_provider.py','19c9a83e83f2d69b70446cd49a8c84201c44e65a4f20380b0aaa8698ca2786d1'),
    '041':(LINE/'tools/stage041_exact_daily_request_provider.py','e4320208cc70d25959db7f66b80518ac0f6ceaaf3e6a61a97bdfc23f008bfa0d')}
READERS={
    '037':(LINE/'tools/stage046_original_provider_delivery.py','d0c1fb55b681ad3113a215cba1964e84eaff7c617875ef71ec27f9db018fe65b'),
    '041':(LINE/'outputs/stage043_exact_request_delivery/review_provider_delivery.py','373493d9eb50647063044e53c2c669584f237345cf2a8edf8f5d0d282c1b1d54')}
TERMINAL040=LINE/'outputs/stage040_exact_request_daily_recovery/terminal_observed.json'
TERMINAL040_SHA='e13d4b523b507bc7267bbcac0d2cd7ccf7e08798c961c90405e372d1efbd55e0'
REVIEWER='ordered_execution_review_frozen_exact_resolver'


class NeedRaw(Exception):pass


def read_json(path):return json.loads(Path(path).read_text())
def write(path,value):
    with Path(path).open('x')as f:f.write(json.dumps(old.safe(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def integer(value):
    number=Decimal(str(value))
    if not number.is_finite()or number!=number.to_integral_value():raise ValueError('noninteger_source_identity')
    return int(number)
def local_ns(value):
    seconds,nano=divmod(value,1_000_000_000)
    return(datetime.fromtimestamp(seconds,timezone.utc)+timedelta(microseconds=nano//1000)).astimezone(timezone(timedelta(hours=8)))
def legal(row):
    try:
        n={k:float(row[k])for k in old.VALUES}
        return all(math.isfinite(v)for v in n.values())and min(n[k]for k in ['open','high','low','close'])>0 and min(n[k]for k in ['volume','open_oi','close_oi'])>=0 and n['low']<=min(n['open'],n['close'])<=max(n['open'],n['close'])<=n['high']
    except(ValueError,TypeError,KeyError):return False


class Review:
    def __init__(self):self.inputs={}
    def bind(self,path,expected=None):
        path=Path(path).resolve();digest=old.sha256(path)
        if expected is not None and digest!=expected:raise ValueError('bound_input_changed:'+str(path))
        if str(path)in self.inputs and self.inputs[str(path)]!=digest:raise ValueError('bound_input_conflict')
        self.inputs[str(path)]=digest
        return digest
    def csv(self,path,expected):
        path=Path(path).resolve();payload=path.read_bytes();digest=__import__('hashlib').sha256(payload).hexdigest()
        if not expected or digest!=expected:raise ValueError('bound_csv_changed:'+str(path))
        self.inputs[str(path)]=digest
        return pd.read_csv(io.BytesIO(payload))
    def unchanged(self):
        if not all(old.sha256(path)==digest for path,digest in self.inputs.items()):raise ValueError('used_input_changed_during_review')


def qualify_local(sources,grid,daily,kind):
    """Check exactly the requested minute scope and actual source successors.

    A full session requires its complete grid and seven-field daily aggregate.
    An anchor requires only its first minute, daily open/available openOI and a
    real forward source row; it grants no full-session qualification.
    """
    if kind not in{'full_session','anchor'}:raise ValueError('unknown_requirement_kind')
    required=grid if kind=='full_session'else grid[:1]
    parts=[];proofs={};source_audits=[]
    for source_id,frame in sources.items():
        selected=frame.loc[frame.bar_datetime.isin(required)].copy()
        source_audits.append(dict(source_id=source_id,source_rows=len(frame),target_rows=len(selected)))
        if selected.empty:continue
        if selected.bar_datetime.duplicated().any()or not all(legal(row)for row in selected.to_dict('records')):
            raise ValueError('local_duplicate_or_invalid_requested_minute')
        parts.append(selected[gate.FIELDS])
        if not{'bar_id','tq_symbol','source_row_number'}.issubset(frame.columns):
            raise ValueError('local_completed_source_missing_actual_identity')
        symbol=str(selected.vt_symbol.iloc[0]);native,exchange=symbol.rsplit('.',1)
        for row in selected.itertuples(index=False):
            position=integer(row.source_row_number)-2
            if position+1>=len(frame):continue
            nxt=frame.iloc[position+1]
            if(str(nxt.vt_symbol)!=symbol or str(row.tq_symbol)!=str(nxt.tq_symbol)or str(row.tq_symbol)!=exchange+'.'+native):
                raise ValueError('local_successor_symbol_conflict')
            ident,next_id=integer(row.bar_id),integer(nxt.bar_id)
            stamp,next_stamp=pd.Timestamp(row.bar_datetime),pd.Timestamp(nxt.bar_datetime)
            if ident<0 or next_id<=ident or next_stamp<stamp+pd.Timedelta(minutes=1)or not legal(nxt):continue
            if(frame.bar_id.eq(row.bar_id).sum()!=1 or frame.bar_id.eq(nxt.bar_id).sum()!=1 or
                frame.bar_datetime.eq(stamp).sum()!=1 or frame.bar_datetime.eq(next_stamp).sum()!=1):
                raise ValueError('local_source_identity_conflict')
            proofs.setdefault(stamp,dict(vt_symbol=symbol,bar_datetime=stamp.isoformat(),source_id=source_id,
                source_row_number=position+2,source_bar_id=ident,successor_row_number=position+3,
                successor_id=next_id,successor_time=next_stamp.isoformat()))
    if parts:
        merged=pd.concat(parts,ignore_index=True)
        dup=merged.loc[merged.bar_datetime.duplicated(keep=False)]
        if len(dup):
            groups=dup.groupby('bar_datetime')[old.VALUES]
            if not np.isclose(groups.min().to_numpy(),groups.max().to_numpy(),rtol=1e-12,atol=1e-8).all():
                raise ValueError('completed_source_conflict')
        merged=merged.drop_duplicates('bar_datetime').sort_values('bar_datetime')
    else:merged=pd.DataFrame(columns=gate.FIELDS);merged['bar_datetime']=pd.Series(dtype='datetime64[ns]')
    missing=list(required.difference(merged.bar_datetime));uncompleted=[s for s in required if s not in proofs]
    audit=dict(source_audits=source_audits,local_present_minutes=len(merged),missing_minutes=len(missing),
        missing_timestamps=[s.isoformat()for s in missing],uncompleted_minutes=len(uncompleted),
        uncompleted_timestamps=[s.isoformat()for s in uncompleted],full_session_grid_minutes=len(grid),
        required_minutes=len(required),full_session_qualified=False)
    if missing or uncompleted:return None,audit,[]
    if kind=='anchor':
        if not np.isfinite(float(daily.get('open',np.nan))):
            audit['local_rejection_reason']='daily_anchor_open_unavailable'
            return None,audit,[]
        fields=['open']+(['open_oi']if np.isfinite(float(daily.get('open_oi',np.nan)))else[])
        row=merged.iloc[0]
        if not all(np.isclose(float(row[name]),float(daily[name]),rtol=1e-12,atol=1e-8)for name in fields):
            raise ValueError('local_anchor_daily_open_conflict')
        audit['session_qualification']=dict(status='accepted',reason='anchor_only_completed_daily_open_matched',
            expected_minutes=1,actual_rows=1,full_session_qualified=False,
            aggregate={name:float(row[name])for name in fields},daily_open_oi_check='checked'if'open_oi'in fields else'unknown')
        return merged[gate.FIELDS].copy(),audit,[proofs[required[0]]]
    if any(not np.isfinite(float(daily.get(name,np.nan)))for name in old.VALUES):
        audit['local_rejection_reason']='full_seven_field_daily_reference_unavailable'
        return None,audit,[]
    _,check=old.validate_session(merged,grid,daily,merged.iloc[:0])
    if check['status']!='accepted':raise ValueError('local_full_session_qualification_failed:'+check['reason'])
    audit['session_qualification']=check
    audit['full_session_qualified']=True
    delivered=merged.loc[merged.bar_datetime.isin(required),gate.FIELDS].copy()
    return delivered,audit,[proofs[s]for s in grid]


def recover_daily(review,symbol,day,old_review):
    native,exchange=symbol.rsplit('.',1)
    provider=LINE/'outputs/stage013_missing_daily_recovery'
    symbols_path=provider/'network_attempt1/symbol_receipts.json';symbols=read_json(symbols_path)
    found=[row for row in symbols if row['vt_symbol']==symbol]
    terminal=None
    if not found:
        provider=LINE/'outputs/stage040_exact_request_daily_recovery'
        review.bind(TERMINAL040,TERMINAL040_SHA);terminal=read_json(TERMINAL040)
        if not terminal['terminal_observed']or terminal['exit_code']!=0:raise ValueError('040_actual_terminal_not_accepted')
        symbols_path=provider/'network_attempt1/symbol_receipts.json'
        found=[row for row in read_json(symbols_path)if row['vt_symbol']==symbol]
    if not found:raise NeedRaw('no_bound_daily_raw_for_actual_symbol')
    if len(found)!=1:raise ValueError('duplicate_bound_daily_raw_symbol')
    attempt=provider/'network_attempt1';parent_path=attempt/'parent_receipt.json'
    parent_sha=old_review['source_fingerprints'][str(parent_path)]if terminal is None else terminal['parent_receipt_sha256']
    review.bind(parent_path,parent_sha);parent=read_json(parent_path)
    if not parent['all_inputs_unchanged']or parent['hard_kill']or parent['status']!='worker_terminal':raise ValueError('bound_daily_provider_terminal_not_accepted')
    if parent['exit_code']!=(1 if terminal is None else 0):raise ValueError('bound_daily_provider_original_terminal_changed')
    review.bind(symbols_path,parent['artifact_sha256']['symbol_receipts.json'])
    preflight_path=provider/'preflight.json';review.bind(preflight_path,parent['preflight_sha256']);preflight=read_json(preflight_path)
    raw_path=Path(found[0]['raw_path'])
    if raw_path!=attempt/'raw'/exchange/(native+'.csv'):raise ValueError('daily_raw_path_identity_mismatch')
    digest=found[0]['raw_sha256']
    if digest!=parent['artifact_sha256'][str(raw_path.relative_to(attempt))]:raise ValueError('daily_raw_parent_hash_mismatch')
    review.bind(raw_path,digest)
    with raw_path.open(encoding='utf-8-sig',newline='')as f:raw=list(csv.DictReader(f))
    if len(raw)!=found[0]['raw_rows']:raise ValueError('daily_raw_row_count_mismatch')
    valid=[]
    for index,row in enumerate(raw):
        if not legal(row):continue
        ident,ns=integer(row['id']),integer(row['datetime'])
        if ident>=0 and ns>0:valid.append((index,ident,ns,row))
    hit=[row for row in valid if local_ns(row[2]).date().isoformat()==day]
    if not hit:raise NeedRaw('bound_daily_raw_has_no_actual_target_day')
    if len(hit)!=1:raise ValueError('duplicate_daily_raw_target')
    source_index,source_id,source_ns,row=hit[0]
    successors=[r for r in valid if r[1]>source_id and r[2]>source_ns]
    if not successors:raise NeedRaw('actual_daily_target_has_no_forward_successor')
    next_index,next_id,next_ns,next_row=min(successors,key=lambda r:(r[1],r[2]))
    dbpath=ROOT/'.vntrader/database.db'
    with sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro',uri=True)as db:
        db.execute('PRAGMA query_only=ON')
        rows=db.execute('SELECT open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata WHERE symbol=? AND exchange=? AND interval=? AND substr(datetime,1,10)=?',(native,exchange,'d',day)).fetchall()
    if not rows:raise NeedRaw('exact_contract_DB_daily_missing')
    if len(rows)!=1:raise ValueError('duplicate_exact_contract_DB_daily')
    six=['open','high','low','close','volume','open_oi'];db_six=dict(zip(six,rows[0]));daily={name:float(row[name])for name in old.VALUES}
    if not all(np.isclose(daily[name],float(db_six[name]),rtol=1e-12,atol=1e-8)for name in six):raise ValueError('daily_raw_exact_DB_six_field_conflict')
    proof=dict(source_bar_id=source_id,source_datetime_ns=source_ns,successor_id=next_id,successor_datetime_ns=next_ns)
    checks=dict(vt_symbol=symbol,trade_date=day,daily=daily,exact_DB_six=db_six,six_fields_checked=True,
        six_fields_max_abs_difference={name:abs(daily[name]-float(db_six[name]))for name in six},
        DB_open_interest_maps_to='provider.open_oi',database_closeOI='N/A_not_independently_available',
        actual_raw_forward_successor_checked=True,source_csv_row=source_index+2,successor_csv_row=next_index+2,**proof,
        source_local_time=local_ns(source_ns).isoformat(),successor_local_time=local_ns(next_ns).isoformat(),
        successor_values={name:float(next_row[name])for name in old.VALUES},raw_snapshot_path=str(raw_path),raw_snapshot_sha256=digest,
        raw_non_target_daily_rows_qualified=False,full_DB_rehashed_by_reviewer=False,exact_DB_queries=1,
        inherited_DB_sha256=preflight['source_fingerprints'][str(dbpath)],provider_original_exit_code=parent['exit_code'],
        provider_original_rejections_preserved=True)
    qualified=dict(vt_symbol=symbol,tq_symbol=exchange+'.'+native,trade_date=day,datetime=local_ns(source_ns).isoformat(),
        **daily,**proof,successor_time=local_ns(next_ns).isoformat())
    audit=dict(vt_symbol=symbol,trade_date=day,accepted=True,reason='completed_and_six_fields_matched',mismatch_fields='',
        database_closeOI='N/A_not_independently_available',**proof)
    return daily,qualified,audit,checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',required=True,type=Path);parser.add_argument('--request-file-sha256',required=True)
    for kind in ['037','041']:
        parser.add_argument('--reviewer'+kind+'-path',type=Path)
        parser.add_argument('--reviewer'+kind+'-sha256')
    args=parser.parse_args();review=Review()
    for name,digest in HELPERS.items():review.bind(LINE/'tools'/name,digest)
    for kind,(path,digest)in PROVIDERS.items():review.bind(path,digest)
    reviewers=dict(READERS)
    for kind in ['037','041']:
        path=getattr(args,'reviewer'+kind+'_path');digest=getattr(args,'reviewer'+kind+'_sha256')
        if bool(path)!=bool(digest):raise ValueError('reader_path_sha_pair_required')
        if path is not None:
            if not path.is_absolute():raise ValueError('reader_absolute_path_required')
            reviewers[kind]=(path.resolve(),digest)
        review.bind(*reviewers[kind])
    review.bind(Path(__file__));review.bind(PROTOCOL)
    request,request_inputs=original_provider.read_request(args.request,args.request_file_sha256)
    for path,digest in request_inputs.items():review.bind(path,digest)
    digest=request['request_sha256']
    if len(request['requirements'])!=1:raise ValueError('resolver_v1_single_actual_requirement_only')
    target=request['requirements'][0];symbol,day,kind=(target[k]for k in ['vt_symbol','execution_trade_date','requirement_kind'])
    if target['existing_source_timestamps']:raise ValueError('resolver_v1_nonempty_physical_old_keys_requires_exact_old_value_review')
    if target['missing_or_unqualified_timestamps']!=target['required_timestamps']:raise ValueError('resolver_v1_partial_missing_scope_not_supported')
    dest=OUTPUT/('request_'+digest)
    if dest.exists():
        saved=read_json(dest/'decision.json');audit=read_json(dest/'resolver_audit.json')
        if saved['request_sha256']!=digest or audit['request_file_sha256']!=args.request_file_sha256:raise ValueError('existing_resolver_decision_identity_mismatch')
        for path,value in audit['source_fingerprints'].items():review.bind(path,value)
        if saved['status']=='accepted':gate._read_delivery(request,gate.QualifiedDelivery(Path(saved['receipt_path']),saved['receipt_sha256']))
        print(json.dumps(saved,ensure_ascii=False));return
    manifest_path=old.OLD/'input_manifest.json';review.bind(manifest_path,OLD_MANIFEST_SHA);original=read_json(manifest_path)
    mapping=review.csv(old.MAPPING,original[str(old.MAPPING.relative_to(ROOT))])
    calendar=pd.DatetimeIndex(pd.to_datetime(sorted(mapping.date.unique())))
    original_provider.packet_targets(request,calendar,0)
    grid=old.session_grid(symbol,day,calendar)
    review.bind(R013,R013_SHA);old_review=read_json(R013)
    qpath=old_review['qualified_daily_path'];apath=old_review['target_qualification_path']
    q=review.csv(qpath,old_review['source_fingerprints'][qpath]);a=review.csv(apath,old_review['source_fingerprints'][apath])
    recovered=daily013.approved_references(q,a,old_review)
    rejected={(r['vt_symbol'],r['trade_date'])for r in old_review['rejected_targets']}
    native,exchange=symbol.rsplit('.',1)
    daily_path=old.PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04'/exchange/(native+'.csv')
    original_daily=review.csv(daily_path,original.get(str(daily_path.relative_to(ROOT))))if daily_path.is_file()else None
    new_daily=None;daily_source=None
    try:daily,daily_source=original_provider.choose_daily_reference(symbol,day,kind,original_daily,recovered,rejected)
    except ValueError as error:
        if str(error)!='qualified_daily_reference_missing':raise
        try:
            daily,qualified,daily_audit,daily_checks=recover_daily(review,symbol,day,old_review)
            new_daily=(qualified,daily_audit,daily_checks);daily_source='new_independent_actual_request_daily'
        except NeedRaw as missing:
            dest.mkdir(parents=True,exist_ok=False)
            output=dict(status='needs_daily_raw',request_sha256=digest,reason=str(missing),vt_symbol=symbol,execution_trade_date=day,
                financial_replays=0,network_connections=0,response_written=False)
            write(dest/'resolver_audit.json',dict(request_file_sha256=args.request_file_sha256,source_fingerprints=review.inputs))
            write(dest/'decision.json',output);print(json.dumps(output,ensure_ascii=False));return
    dest.mkdir(parents=True,exist_ok=False)
    daily_receipt_path=None;daily_receipt_sha=None
    if new_daily is not None:
        qualified,daily_audit,daily_checks=new_daily;daily_checks['request_sha256']=digest
        daily_path=dest/'qualified_daily.csv';audit_path=dest/'target_qualification.csv';checks_path=dest/'daily_checks.json'
        pd.DataFrame([qualified]).to_csv(daily_path,index=False);review.bind(daily_path)
        pd.DataFrame([daily_audit]).to_csv(audit_path,index=False);review.bind(audit_path)
        write(checks_path,daily_checks);review.bind(checks_path)
        daily_receipt_path=dest/'daily_review_receipt.json'
        daily_receipt=dict(schema='stage045_independent_exact_daily_v1',reviewed_at=datetime.now().astimezone().isoformat(),independent_review=True,
            reviewer=REVIEWER,qualified_research_daily=True,p0_findings=0,p1_findings=0,p2_findings=0,request_sha256=digest,
            accepted_target_keys=[[symbol,day]],qualified_rows=1,target_rows=1,qualified_daily_path=str(daily_path),
            target_qualification_path=str(audit_path),daily_checks_path=str(checks_path),six_fields_checked=True,
            actual_raw_forward_successor_checked=True,database_closeOI='N/A_not_independently_available',
            source_fingerprints=dict(review.inputs),network_connections_in_review=0,financial_replays=0,orders=0,response_written=False,production_qualified=False)
        write(daily_receipt_path,daily_receipt);daily_receipt_sha=review.bind(daily_receipt_path)
    inventories=[]
    for path,expected in SOURCE_MANIFESTS.items():
        review.bind(path,expected)
        inventories.extend(row for row in read_json(path)['sources']if row['path'].endswith('/'+native+'_completed_minute_backtest.csv')and Path(row['path']).parent.name==exchange)
    sources={};seen_paths=set();source_checks=[]
    for info in inventories:
        path=Path(info['path'])
        if path in seen_paths:continue
        seen_paths.add(path)
        if info.get('status')not in {None,'accepted_source_bytes'}:raise ValueError('local_source_not_previously_accepted')
        frame,check=local.read_bound_minute_source(path,info['sha256'],symbol)
        if frame is None:raise ValueError('local_bound_source_unusable:'+check['reason'])
        review.inputs[str(path)]=info['sha256'];sources[info['source_id']]=frame;source_checks.append(check)
    delivered,local_check,completion=qualify_local(sources,grid,daily,kind)
    write(dest/'local_checks.json',dict(vt_symbol=symbol,execution_trade_date=day,requirement_kind=kind,
        source_checks=source_checks,**local_check));review.bind(dest/'local_checks.json')
    if delivered is None:
        branch='041'if new_daily is not None else'037';provider_path,provider_sha=PROVIDERS[branch];reader_path,reader_sha=reviewers[branch]
        output=dict(status='needs_provider',request_sha256=digest,packet_count=1,provider_path=str(provider_path),provider_sha256=provider_sha,
            reviewer_path=str(reader_path),reviewer_sha256=reader_sha,daily_reference_source=daily_source,
            missing_minutes=local_check['missing_minutes'],uncompleted_minutes=local_check['uncompleted_minutes'])
        if new_daily is not None:output.update(daily_review_path=str(daily_receipt_path),daily_review_sha256=daily_receipt_sha)
    else:
        anchors=old.A0/'execution_anchor_requests.csv';scans=old.A0/'minute_scan_requests.csv'
        review.bind(anchors,'72b61783602257c16b1b8c0307b0da4221430204808fdc29f21124f7556fbb20')
        review.bind(scans,'cedf3627a530985083839af071f997482dd417e3f2721ca21208b50b086a03ab')
        disjoint=old.prove_read_disjointness(delivered,pd.read_csv(anchors),pd.read_csv(scans),calendar)
        if not disjoint['path_equivalent']or disjoint['intersection_count']:raise ValueError('new_local_delivery_intersects_A0_actual_read_keys')
        data_path=dest/'delivery_minutes.csv';delivered.to_csv(data_path,index=False);data_sha=review.bind(data_path)
        pd.DataFrame(completion).to_csv(dest/'completion_evidence.csv',index=False);review.bind(dest/'completion_evidence.csv')
        write(dest/'key_checks.json',dict(A0_actual_read_disjointness=disjoint,request_scope_existing_physical_keys=0,
            new_request_scope_physical_keys=len(delivered),global_existing_keys_claimed_empty=False,
            old_key_protection='Real Stage021 compares overlap seven-values exactly before append-only atomic commit.',
            full_session_qualified=kind=='full_session',qualified_full_local_session_for_anchor=False,
            delivered_right=kind));review.bind(dest/'key_checks.json')
        receipt_path=dest/'delivery_receipt.json'
        receipt=dict(schema=gate.RECEIPT_SCHEMA,reviewed_at=datetime.now().astimezone().isoformat(),independent_review=True,reviewer=REVIEWER,
            qualified_research_data=True,p0_findings=0,p1_findings=0,p2_findings=0,request_sha256=digest,
            accepted_requirements=[dict(vt_symbol=symbol,execution_trade_date=day,requirement_kind=kind,accepted=True,
                completed_bars_and_daily_qualified=True,accepted_timestamps=target['required_timestamps'])],
            data_path=str(data_path),data_sha256=data_sha,source_fingerprints=dict(review.inputs),
            confidence='exact_requested_data_only; no profitability or global minute quality claim',
            network_connections_in_review=0,financial_replays=0,model_fits=0,orders=0,response_written=False,production_qualified=False)
        review.unchanged();write(receipt_path,receipt);receipt_sha=old.sha256(receipt_path)
        parsed,full,anchor,info=gate._read_delivery(request,gate.QualifiedDelivery(receipt_path,receipt_sha))
        if len(parsed)!=len(target['required_timestamps'])or len(full)+len(anchor)!=len(parsed):raise ValueError('local_delivery_parser_scope_mismatch')
        output=dict(status='accepted',request_sha256=digest,receipt_path=str(receipt_path),receipt_sha256=receipt_sha,
            rows=len(parsed),full_keys=len(full),anchor_keys=len(anchor),actual_stage021_parser_passed=True,response_written=False)
        write(dest/'parse_result.json',output)
    review.unchanged()
    write(dest/'resolver_audit.json',dict(request_file_sha256=args.request_file_sha256,request_sha256=digest,
        daily_reference_source=daily_source,source_fingerprints=review.inputs,financial_replays=0,network_connections=0,response_written=False))
    write(dest/'decision.json',output);print(json.dumps(output,ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='blocked',error_type=type(error).__name__,error=str(error),response_written=False),ensure_ascii=False))
        raise SystemExit(1)
