"""Offline joint resolver for one actual request of up to eight requirements.

Reuse pinned Stage045 data checks. No provider execution, engine, network,
financial replay, model, or response writer. Actual Stage021 protects old values.
"""
from pathlib import Path
from datetime import datetime
import argparse
import json

import numpy as np
import pandas as pd
import stage045_exact_request_resolver as frozen

LINE,ROOT=frozen.LINE,frozen.ROOT
old,local,gate=frozen.old,frozen.local,frozen.gate
OUTPUT=LINE/'outputs/stage047_multi_exact_request_resolver'
PROTOCOL=LINE/'stages/20261018_0427_stage047_multi_actual_request_resolver_contract.md'
FROZEN_SOURCE=LINE/'tools/stage045_exact_request_resolver.py'
FROZEN_SHA='597551c51a021f763318086e4e3084bd5a54aa03abb8d4b038f63d131f8d02df'
REVIEWER='ordered_execution_review_joint_actual_resolver'
READERS={branch:(LINE/'tools/stage048_general_provider_delivery.py',
    '3b220aadeb1e8091a35d84624b643c3a0b276c6e3f4be9874293a9abaecd785a')for branch in ['037','041']}


def request_key_scope(request):
    required=set();existing=set()
    for target in request['requirements']:
        symbol=str(target['vt_symbol'])
        stamps=[pd.Timestamp(s)for s in target['required_timestamps']]
        prior=[pd.Timestamp(s)for s in target['existing_source_timestamps']]
        missing=[pd.Timestamp(s)for s in target['missing_or_unqualified_timestamps']]
        r,e,m=set(stamps),set(prior),set(missing)
        if(len(r)!=len(stamps)or len(e)!=len(prior)or len(m)!=len(missing)or not m or
            not e.issubset(r)or not m.issubset(r)or not(r-e).issubset(m)):
            raise ValueError('joint_required_existing_missing_scope_invalid')
        required.update((symbol,s)for s in r);existing.update((symbol,s)for s in e)
    return existing,required-existing


def assemble_delivery(request,frames):
    """Build only the wanted identities; already-qualified active orders add none."""
    wanted={(r['vt_symbol'],r['execution_trade_date'],r['requirement_kind']):r for r in request['requirements']}
    if len(wanted)!=len(request['requirements'])or set(frames)!=set(wanted):raise ValueError('joint_delivery_requirement_identity_mismatch')
    parts=[];accepted=[]
    for identity,target in wanted.items():
        frame=frames[identity][gate.FIELDS].copy()
        expected={(identity[0],pd.Timestamp(s))for s in target['required_timestamps']}
        keys={(str(r.vt_symbol),pd.Timestamp(r.bar_datetime))for r in frame.itertuples(index=False)}
        if old.minute_keys(frame).has_duplicates or keys!=expected:raise ValueError('joint_delivery_exact_timestamp_scope_mismatch')
        parts.append(frame)
        accepted.append(dict(vt_symbol=identity[0],execution_trade_date=identity[1],requirement_kind=identity[2],accepted=True,
            completed_bars_and_daily_qualified=True,accepted_timestamps=target['required_timestamps']))
    data=pd.concat(parts,ignore_index=True).sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)
    if old.minute_keys(data).has_duplicates:raise ValueError('joint_delivery_duplicate_key')
    return data,accepted


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',required=True,type=Path);parser.add_argument('--request-file-sha256',required=True)
    for branch in ['037','041']:
        parser.add_argument('--reviewer'+branch+'-path',type=Path);parser.add_argument('--reviewer'+branch+'-sha256')
    args=parser.parse_args();review=frozen.Review()
    review.bind(FROZEN_SOURCE,FROZEN_SHA);review.bind(Path(__file__));review.bind(PROTOCOL)
    for name,digest in frozen.HELPERS.items():review.bind(LINE/'tools'/name,digest)
    for branch,(path,digest)in frozen.PROVIDERS.items():review.bind(path,digest)
    reviewers=dict(READERS)
    for branch in ['037','041']:
        path=getattr(args,'reviewer'+branch+'_path');digest=getattr(args,'reviewer'+branch+'_sha256')
        if bool(path)!=bool(digest):raise ValueError('reader_path_sha_pair_required')
        if path is not None:
            if not path.is_absolute():raise ValueError('reader_absolute_path_required')
            reviewers[branch]=(path.resolve(),digest)
        review.bind(*reviewers[branch])
    request,request_inputs=frozen.original_provider.read_request(args.request,args.request_file_sha256)
    for path,digest in request_inputs.items():review.bind(path,digest)
    digest=request['request_sha256'];targets=request['requirements']
    if not 1<=len(targets)<=8:raise ValueError('resolver047_requires_one_to_eight_actual_requirements')
    existing_keys,new_keys=request_key_scope(request)
    dest=OUTPUT/('request_'+digest)
    if dest.exists():
        saved=frozen.read_json(dest/'decision.json');audit=frozen.read_json(dest/'resolver_audit.json')
        if saved['request_sha256']!=digest or audit['request_file_sha256']!=args.request_file_sha256:raise ValueError('existing_joint_decision_identity_mismatch')
        for path,value in audit['source_fingerprints'].items():review.bind(path,value)
        if saved['status']=='accepted':gate._read_delivery(request,gate.QualifiedDelivery(Path(saved['receipt_path']),saved['receipt_sha256']))
        print(json.dumps(saved,ensure_ascii=False));return
    manifest_path=old.OLD/'input_manifest.json';review.bind(manifest_path,frozen.OLD_MANIFEST_SHA);original=frozen.read_json(manifest_path)
    mapping=review.csv(old.MAPPING,original[str(old.MAPPING.relative_to(ROOT))]);calendar=pd.DatetimeIndex(pd.to_datetime(sorted(mapping.date.unique())))
    canonical,info=frozen.original_provider.packet_targets(request,calendar,0)
    if info['packet_count']!=1 or len(canonical)!=len(targets):raise ValueError('resolver047_joint_request_exceeds_one_packet')
    review.bind(frozen.R013,frozen.R013_SHA);old_review=frozen.read_json(frozen.R013)
    qpath=old_review['qualified_daily_path'];apath=old_review['target_qualification_path']
    q=review.csv(qpath,old_review['source_fingerprints'][qpath]);a=review.csv(apath,old_review['source_fingerprints'][apath])
    recovered=frozen.daily013.approved_references(q,a,old_review)
    rejected={(r['vt_symbol'],r['trade_date'])for r in old_review['rejected_targets']}
    contexts=[];new_rows=[];new_audits=[];new_checks=[]
    for target in targets:
        symbol,day,kind=(target[name]for name in ['vt_symbol','execution_trade_date','requirement_kind'])
        native,exchange=symbol.rsplit('.',1)
        daily_path=old.PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04'/exchange/(native+'.csv')
        original_daily=review.csv(daily_path,original.get(str(daily_path.relative_to(ROOT))))if daily_path.is_file()else None
        is_new=False
        try:daily,daily_source=frozen.original_provider.choose_daily_reference(symbol,day,kind,original_daily,recovered,rejected)
        except ValueError as error:
            if str(error)!='qualified_daily_reference_missing':raise
            try:daily,qualified,audit,checks=frozen.recover_daily(review,symbol,day,old_review)
            except frozen.NeedRaw as missing:raise ValueError('needs_daily_raw:'+symbol+':'+day+':'+str(missing))from missing
            checks['request_sha256']=digest;new_rows.append(qualified);new_audits.append(audit);new_checks.append(checks)
            daily_source='new_independent_actual_request_daily';is_new=True
        contexts.append(dict(target=target,daily=daily,daily_source=daily_source,is_new_daily=is_new,
            grid=old.session_grid(symbol,day,calendar)))
    # No independent daily receipt is signed until every requested target's
    # reference has passed, and no non-requested active-order key is considered.
    dest.mkdir(parents=True,exist_ok=False);daily_receipt_path=None;daily_receipt_sha=None
    if new_rows:
        daily_path=dest/'qualified_daily.csv';audit_path=dest/'target_qualification.csv';checks_path=dest/'daily_checks.json'
        pd.DataFrame(new_rows).to_csv(daily_path,index=False);review.bind(daily_path)
        pd.DataFrame(new_audits).to_csv(audit_path,index=False);review.bind(audit_path)
        frozen.write(checks_path,dict(targets=new_checks));review.bind(checks_path)
        new_daily_keys=[[r['vt_symbol'],r['trade_date']]for r in new_rows]
        if len({tuple(k)for k in new_daily_keys})!=len(new_daily_keys):raise ValueError('joint_new_daily_duplicate_key')
        daily_receipt_path=dest/'daily_review_receipt.json'
        receipt=dict(schema='stage047_independent_exact_daily_subset_v1',reviewed_at=datetime.now().astimezone().isoformat(),
            independent_review=True,reviewer=REVIEWER,qualified_research_daily=True,p0_findings=0,p1_findings=0,p2_findings=0,
            request_sha256=digest,accepted_target_keys=new_daily_keys,qualified_rows=len(new_rows),target_rows=len(new_rows),
            qualified_daily_path=str(daily_path),target_qualification_path=str(audit_path),daily_checks_path=str(checks_path),
            six_fields_checked=True,actual_raw_forward_successor_checked=True,database_closeOI='N/A_not_independently_available',
            source_fingerprints=dict(review.inputs),network_connections_in_review=0,financial_replays=0,orders=0,response_written=False,production_qualified=False)
        frozen.write(daily_receipt_path,receipt);daily_receipt_sha=review.bind(daily_receipt_path)
    inventories=[]
    for path,expected in frozen.SOURCE_MANIFESTS.items():
        review.bind(path,expected);inventories.extend(frozen.read_json(path)['sources'])
    ready={};local_checks=[];proofs=[];source_cache={}
    for context in contexts:
        target=context['target'];symbol,day,kind=(target[name]for name in ['vt_symbol','execution_trade_date','requirement_kind'])
        native,exchange=symbol.rsplit('.',1);sources={};source_audits=[]
        for row in inventories:
            if not row['path'].endswith('/'+native+'_completed_minute_backtest.csv')or Path(row['path']).parent.name!=exchange:continue
            path=Path(row['path'])
            if row.get('status')not in{None,'accepted_source_bytes'}:raise ValueError('local_source_not_previously_accepted')
            if str(path)not in source_cache:
                frame,check=local.read_bound_minute_source(path,row['sha256'],symbol)
                if frame is None:raise ValueError('local_bound_source_unusable:'+check['reason'])
                review.inputs[str(path)]=row['sha256'];source_cache[str(path)]=(frame,check)
            frame,check=source_cache[str(path)];sources[row['source_id']]=frame;source_audits.append(check)
        delivered,check,completion=frozen.qualify_local(sources,context['grid'],context['daily'],kind)
        identity=(symbol,day,kind)
        if delivered is not None:ready[identity]=delivered;proofs.extend(completion)
        local_checks.append(dict(vt_symbol=symbol,execution_trade_date=day,requirement_kind=kind,
            daily_reference_source=context['daily_source'],is_new_daily=context['is_new_daily'],
            local_accepted=delivered is not None,source_checks=source_audits,**check))
    checks_path=dest/'local_checks.json';frozen.write(checks_path,dict(request_sha256=digest,targets=local_checks));review.bind(checks_path)
    if len(ready)!=len(targets):
        # A ready local subset is evidence only; never return a partial whole-
        # request receipt. The approved provider receives the original request.
        if ready:
            candidate=pd.concat(list(ready.values()),ignore_index=True)
            candidate.to_csv(dest/'local_candidate_minutes.csv',index=False);review.bind(dest/'local_candidate_minutes.csv')
        if proofs:pd.DataFrame(proofs).to_csv(dest/'local_completion_evidence.csv',index=False);review.bind(dest/'local_completion_evidence.csv')
        branch='041'if new_rows else'037';provider_path,provider_sha=frozen.PROVIDERS[branch];reader_path,reader_sha=reviewers[branch]
        output=dict(status='needs_provider',request_sha256=digest,packet_count=1,provider_path=str(provider_path),provider_sha256=provider_sha,
            reviewer_path=str(reader_path),reviewer_sha256=reader_sha,requirements=len(targets),local_ready_requirements=len(ready),
            provider_scope='entire_actual_request_not_only_the_local_missing_subset')
        if new_rows:output.update(daily_review_path=str(daily_receipt_path),daily_review_sha256=daily_receipt_sha)
    else:
        data,accepted=assemble_delivery(request,ready)
        anchors=old.A0/'execution_anchor_requests.csv';scans=old.A0/'minute_scan_requests.csv'
        review.bind(anchors,'72b61783602257c16b1b8c0307b0da4221430204808fdc29f21124f7556fbb20')
        review.bind(scans,'cedf3627a530985083839af071f997482dd417e3f2721ca21208b50b086a03ab')
        added=data.loc[[((str(row.vt_symbol),pd.Timestamp(row.bar_datetime))in new_keys)for row in data.itertuples(index=False)]].copy()
        if len(added)!=len(new_keys):raise ValueError('joint_newkey_filter_identity_mismatch')
        disjoint=old.prove_read_disjointness(added,pd.read_csv(anchors),pd.read_csv(scans),calendar)
        if not disjoint['path_equivalent']or disjoint['intersection_count']:raise ValueError('joint_new_delivery_intersects_A0_actual_read_keys')
        data_path=dest/'delivery_minutes.csv';data.to_csv(data_path,index=False);data_sha=review.bind(data_path)
        pd.DataFrame(proofs).to_csv(dest/'completion_evidence.csv',index=False);review.bind(dest/'completion_evidence.csv')
        key_checks=dict(request_sha256=digest,accepted_requirement_identities=[list(k)for k in ready],
            active_order_keys_not_requested_not_requalified=True,A0_actual_read_disjointness=disjoint,
            request_scope_existing_physical_keys=len(existing_keys),new_request_scope_physical_keys=len(new_keys),
            delivered_required_keys=len(data),global_existing_keys_claimed_empty=False,
            old_physical_values_independently_compared=False,
            old_value_comparison_delegated_to_actual_stage021=True,
            actual_stage021_sha256=frozen.HELPERS['stage021_blocking_data_gate.py'],
            full_session_qualified={symbol:kind=='full_session'for symbol,day,kind in ready},
            old_key_protection='Real Stage021 compares all overlap seven-values exactly before append-only atomic commit.')
        frozen.write(dest/'key_checks.json',key_checks);review.bind(dest/'key_checks.json')
        receipt_path=dest/'delivery_receipt.json'
        receipt=dict(schema=gate.RECEIPT_SCHEMA,reviewed_at=datetime.now().astimezone().isoformat(),independent_review=True,reviewer=REVIEWER,
            qualified_research_data=True,p0_findings=0,p1_findings=0,p2_findings=0,request_sha256=digest,
            accepted_requirements=accepted,data_path=str(data_path),data_sha256=data_sha,source_fingerprints=dict(review.inputs),
            confidence='exact_actual_requirements_only; no profitability or global minute quality claim',network_connections_in_review=0,
            financial_replays=0,model_fits=0,orders=0,response_written=False,production_qualified=False)
        review.unchanged();frozen.write(receipt_path,receipt);receipt_sha=old.sha256(receipt_path)
        parsed,full,anchor,info=gate._read_delivery(request,gate.QualifiedDelivery(receipt_path,receipt_sha))
        if len(parsed)!=sum(len(t['required_timestamps'])for t in targets)or len(full)+len(anchor)!=len(parsed):raise ValueError('joint_delivery_parser_scope_mismatch')
        output=dict(status='accepted',request_sha256=digest,receipt_path=str(receipt_path),receipt_sha256=receipt_sha,
            requirements=len(targets),rows=len(parsed),full_keys=len(full),anchor_keys=len(anchor),actual_stage021_parser_passed=True,response_written=False)
        frozen.write(dest/'parse_result.json',output)
    review.unchanged()
    frozen.write(dest/'resolver_audit.json',dict(request_file_sha256=args.request_file_sha256,request_sha256=digest,
        wanted_requirement_identities=[[t['vt_symbol'],t['execution_trade_date'],t['requirement_kind']]for t in targets],
        local_ready_requirements=len(ready),new_daily_keys=[[r['vt_symbol'],r['trade_date']]for r in new_rows],
        existing_physical_keys=len(existing_keys),new_physical_keys=len(new_keys),
        old_physical_values_independently_compared=False,old_value_comparison_delegated_to_actual_stage021=True,
        actual_stage021_sha256=frozen.HELPERS['stage021_blocking_data_gate.py'],
        source_fingerprints=review.inputs,financial_replays=0,network_connections=0,response_written=False))
    frozen.write(dest/'decision.json',output);print(json.dumps(output,ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='blocked',error_type=type(error).__name__,error=str(error),response_written=False),ensure_ascii=False))
        raise SystemExit(1)
