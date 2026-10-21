"""One u20 daily3 batch and unfunded composition; root authorization required.

No data/network on import. No model fitting, account creation, price replay,
metadata query, T0 creation or production interface. Original sources unchanged.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import redirect_stdout,redirect_stderr
from copy import deepcopy
from datetime import datetime,timezone
from functools import lru_cache
import csv,gzip,hashlib,importlib.metadata,importlib.util,io,json,logging,math,re
from pathlib import Path
import time
from types import SimpleNamespace

TOOLS=Path(__file__).resolve().parent;ROOT=TOOLS.parents[3]
U='2026-10-20';PREVIOUS='2026-10-19';D='2026-10-21'
NOT_BEFORE='2026-10-20T15:15:00+08:00';NOT_AFTER='2026-10-20T21:00:00+08:00'
FIELDS=('open','high','low','close','volume','close_oi')
LIMITS=dict(global_timeout_seconds=600.,connect_timeout_seconds=45.,ready_timeout_seconds=40.,
    close_timeout_seconds=8.,batch_size=80,max_consecutive_connection_errors=3,max_consecutive_unready_batches=3)
CLOCK_CONTRACT=json.loads('{"D_execution_domain": {"aggregate": "minimum first execution open from complete bounded operational session candidates; required unknown/conflict keeps domain unknown", "auction": "separate evidence; do not move original execution open to collection/auction time", "eligible_rule": "use original stage320 qualification before score/K ranking/family winner; recompute each new u", "empty_existing_state": "current observe run explicitly has no financial states; never infer future flatness from omitted state", "known_false_examples": [{"evidence": "original same-epoch history/run/indicator qualification is known insufficient", "reason": "insufficient_or_gap_history20"}, {"evidence": "frozen target/listed date and confirmed D establish original known ineligibility", "reason": "known_entry_ineligible_lifecycle"}, {"evidence": "qualified economics and positive integral round_lot plus accepted volume establish original known capacity below one lot", "reason": "capacity_below_one_roundtrip"}, {"evidence": "explicit invalid native input state; never promote to accepted current quote", "reason": "invalid_u_native_bar"}], "members": "new-u original pre-score eligible=True OR qualification unresolved, UNION explicit existing open-position/pending execution dependencies", "unresolved_examples": ["economics_unresolved", "execution_capacity_unknown", "unrepresentable_u_cost_quote", "no_accepted_u_anchor", "unrecognized_or_unproven_false_reason"], "unresolved_treatment": "retain as clock dependency only; does not upgrade trading eligibility, fill, selected status or missing inputs"}, "activation": "no T0 creation, no funded state initialization, no orders/scheduler/production authority", "freeze_boundary": "pre-T0 conservative clarification of Stage352; can change operational admission. Does not assert equality to prior historical cash execution path", "frozen_at": null, "line_id": "futures_full_market_long_signal_ai", "prohibited_domain_filters": ["final winners", "positive score", "score rank", "K pass/fail", "cached u19 eligible count427", "cached final2 selections"], "research_reference": "PURE52_MAIN2023_VOLUNTARY_RESELECT_NARROW", "root_freeze_rule": "only real stage321 research_reference_freeze receipt.recorded_at supplies T0; completed<=T0 remains historical even received later", "schema": "stage356_causal_clock_domain_policy_v1", "session_evidence": "actual received metadata subset + confirmed source calendar + stage353 bounded operational_regular_schedule expansion; last-day exception unknown without explicit override", "source_completion_domain": {"aggregate": "maximum confirmed operational session_end; any required missing/unknown clock keeps domain unknown", "completion_observed_at": "actual freshready observation time, separate from source_completed_at", "members": "all causal current-u price/feature/peer/reference inputs actually required for complete observations, plus existing-state required prices", "received_at": "actual stage321 UTC immutable receipt", "source_completed_at": "confirmed u operational session_end aggregate, never received_at", "vendor_finality": "unknown"}, "status": "pre_T0_contract_no_freeze_event_created", "strict_full_input_diagnostic": "preserve Stage354 full726 diagnostic and its unknowns unchanged; two-domain result is separately named", "version": "pure52_input_vs_execution_v1"}')
KNOWN_INELIGIBLE={'invalid_u_native_bar','insufficient_or_gap_history20',
    'known_entry_ineligible_lifecycle','capacity_below_one_roundtrip'}


@lru_cache(maxsize=1)
def components():
    result={}
    for key,name in [('transport','stage336_recent_daily_receiver'),('dates','stage342_offline_date_adapter'),
                     ('adapter','stage339_incremental_snapshot'),('caller','stage325_forward_caller')]:
        spec=importlib.util.spec_from_file_location('stage357_'+key,TOOLS/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);result[key]=module
    return SimpleNamespace(**result)


def _time(value):return components().transport._utc(value)
def _finite(v):return isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)
def _valid(v):
    return (all(_finite(v.get(k)) and v[k]>0 for k in FIELDS[:5])
        and v['low']<=min(v['open'],v['close'])<=max(v['open'],v['close'])<=v['high']
        and (v.get('close_oi') is None or _finite(v['close_oi']) and v['close_oi']>=0))


def check_collection_window(now):
    if not _time(NOT_BEFORE)<=_time(now)<_time(NOT_AFTER):
        raise ValueError('u20 acquisition permitted only after15:15 and before frozen21:00 deadline')


def compose_snapshot(raw_items,*,warmup_states,epoch_inventory,dates,calendar,identity_map,products,
        economics,prior_overlay,sessions,clock_contract,source_receipt,core,execution_dependencies=()):
    """Pure342 decode -> finite continuity predicate ->339 -> pre-score domains.

    factor1 is conditional on an exact u19 witness within the same observed
    product in this new SDK batch. A prior accepted symbol's missing/conflicting
    overlap quarantines that symbol. No new product/unit/economics proxy exists.
    """
    if clock_contract!=CLOCK_CONTRACT:raise ValueError('pre-frozen dual-domain policy required')
    c=components();prior={};prior_products=set()
    for row in prior_overlay:
        symbol=row['native_values']['symbol'];epoch=row['contract_epoch_id']
        if symbol in prior or row['trade_date']!=PREVIOUS:raise ValueError('prior overlay duplicate/date')
        prior[symbol]=row;prior_products.add(epoch.rsplit('.',1)[0])
    decoded=[];by_symbol={};conflicts=set();matches=set();rejections=[]
    for symbol,item in sorted(raw_items.items()):
        rows=[]
        for raw in item.get('rows',[]):
            mapped=c.dates.recover_timestamp(raw,source_dtype=item.get('dtypes',{}).get('datetime'),calendar=calendar)
            row=dict(mapped,symbol=symbol,contract_epoch_id=identity_map.get(symbol),native_values=deepcopy(raw.get('values',{})),
                received_at=item.get('receipt',{}).get('recorded_at'),source_receipt=dict(raw=item.get('raw'),
                receiver321=item.get('receipt'),source_version=item.get('source_version')),fresh_ready=item.get('fresh_ready') is True,
                raw_datetime_literal=raw.get('raw_datetime_literal'),raw_row_index=raw.get('row_index'))
            rows.append(row);decoded.append(row)
        by_symbol[symbol]=rows
        if symbol in prior:
            overlaps=[r for r in rows if r['trade_date']==PREVIOUS]
            if (len(overlaps)!=1 or not item.get('fresh_ready') or identity_map.get(symbol)!=prior[symbol]['contract_epoch_id']
                    or any(overlaps[0]['native_values'].get(k)!=prior[symbol]['canonical_values'].get(k) for k in FIELDS)):
                conflicts.add(symbol)
            else:matches.add(symbol)
    witnesses={identity_map[s].rsplit('.',1)[0] for s in matches}
    canonical=[];seen=set()
    for row in decoded:
        symbol=row['symbol'];epoch=row['contract_epoch_id'];day=row['trade_date'];reason=None
        if day!=U:reason='future_forming_not_consumed' if day and day>U else 'overlap_or_other_date_not_replayed' if day else 'date_unknown'
        elif not row['fresh_ready']:reason='serial_not_ready'
        elif not epoch:reason='identity_unknown'
        elif symbol in conflicts:reason='u19_overlap_conflict_or_missing'
        elif not _valid(row['native_values']):reason='invalid_or_zero_volume'
        elif epoch.rsplit('.',1)[0] not in prior_products or epoch.rsplit('.',1)[0] not in witnesses:
            reason='units_unconfirmed_product'
        if reason:
            rejections.append(dict(symbol=symbol,contract_epoch_id=epoch,trade_date=day,reason=reason,
                native_values=deepcopy(row['native_values']),source_receipt=row['source_receipt']));continue
        if epoch in seen:
            raise ValueError('duplicate new-u epoch;no silent selection or last-write-wins')
        seen.add(epoch)
        canonical.append(dict(row,canonical_values={k:row['native_values'].get(k) for k in FIELDS},
            identity_state='known_explicit',date_mapping_state='operational_midnight_label',
            units_status='canonical_normalized',canonical_quality_status='accepted',model_input_eligible=True,
            unit_overlay=dict(volume_factor=1,oi_factor=1,scope='newbatch_same_observed_product_with_exact_u19_witness'),
            source_completed_at=None,completion_observed_at=None,vendor_finality='unknown',source_first_published_at=None))
    u=list(dates).index(U);dc=dict(confirmed=calendar.get(D) is True,D_index=u+1,D_date=D,
        proof='bound_calendar_next_source_date')
    if not dc['confirmed']:dc.update(D_index=None,D_date=None)
    normalization=dict(status='completed',canonical_rows_accepted=True,policy='finite_same_source_u19_overlap_factor1',
        matched_symbols=sorted(matches),quarantined_symbols=sorted(conflicts),witness_products=sorted(witnesses),
        inherited_product_scope=sorted(prior_products),no_new_unit_or_economic_proxy=True)
    snapshot=c.adapter.build_incremental_snapshot(warmup_states,epoch_inventory,canonical,dates=dates,
        previous_u_date=PREVIOUS,u_date=U,products=products,economics=economics,
        calendar_confirmation=dict(confirmed=calendar.get(U) is True,u_date=U,u_index=u,proof=source_receipt),
        normalization_receipt=normalization,source_receipt=source_receipt,D_context=dc,core=core)
    # These observations contain original eligibility, no scores or selection.
    prescore=core.build_u_observations(snapshot['series_by_epoch'],u,dates,economics,products,D_context=dc)
    by_epoch={r['contract_epoch_id']:r for r in canonical};session={}
    for r in sessions:
        key=(r['symbol'],r['trade_date'])
        if key in session:raise ValueError('duplicate session candidate')
        session[key]=r
    inverse={e:s for s,e in identity_map.items()}
    execution=[];eligibility_unknown=[];excluded=[]
    for row in prescore['candidates']:
        epoch=row['reference_epoch'];flag=row.get('u_action_eligible');reason=row.get('u_ineligibility_reason')
        if flag==1:execution.append(epoch)
        elif flag==0 and reason in KNOWN_INELIGIBLE:excluded.append(dict(epoch=epoch,reason=reason))
        else:execution.append(epoch);eligibility_unknown.append(epoch)
    dependencies=[]
    for value in execution_dependencies:
        epoch=value if isinstance(value,str) else value['epoch']
        execution.append(epoch);dependencies.append(deepcopy(value))
    execution=sorted(set(execution))
    dependency_epochs={v if isinstance(v,str) else v['epoch'] for v in execution_dependencies}
    input_epochs=sorted(set(by_epoch)|dependency_epochs);ends=[];opens=[];u_unknown=[];D_unknown=[]
    for epoch in input_epochs:
        if epoch not in by_epoch:u_unknown.append(epoch);continue
        row=by_epoch[epoch];s=session.get((row['symbol'],U),{})
        end=s.get('session_end') if s.get('state')=='operational_regular_schedule' else None
        if not end or not row.get('received_at') or _time(row['received_at'])<_time(end):u_unknown.append(epoch)
        else:ends.append(end);row.update(source_completed_at=end,completion_observed_at=row['received_at'])
    for epoch in execution:
        s=session.get((inverse.get(epoch),D),{})
        opened=s.get('first_open') if s.get('state')=='operational_regular_schedule' else None
        if not opened:D_unknown.append(epoch)
        else:opens.append(opened)
    complete=max(ends,key=_time) if ends and not u_unknown else None
    opened=min(opens,key=_time) if opens and not D_unknown else None
    domains=dict(schema='stage357_dual_clock_domains_v1',policy=deepcopy(clock_contract),u_date=U,D_date=D,
        input_completion=dict(epochs=input_epochs,unknown_epochs=u_unknown,source_completed_at=complete),
        execution_deadline=dict(epochs=execution,eligibility_unknown_epochs=sorted(eligibility_unknown),
            excluded_original_ineligible=excluded,explicit_dependencies=dependencies,unknown_epochs=D_unknown,D_open_at=opened),
        before_score=True,score_or_winner_used=False,prior354_strict_result_unchanged=True)
    snapshot['clock']=dict(source_completed_at=complete,D_open_at=opened,domain_policy=clock_contract['version'])
    audit=dict(overlap_matches=sorted(matches),overlap_conflicts=sorted(conflicts),witness_products=sorted(witnesses),
        input_raw_rows=len(decoded),accepted_current_rows=len(canonical),rejections=rejections,
        reason_counts=dict(Counter(r['reason'] for r in rejections)),factor1_conditional=True)
    return dict(snapshot=snapshot,canonical_rows=canonical,normalization_audit=audit,prescore_observations=prescore,
                clock_domains=domains,normalization_receipt=normalization)


def observe_composed(composed,*,model,scaler,journal,policy_identity,caller):
    """Full immutable unfunded research decision before its real seal clock."""
    result=caller.process_snapshot(composed['snapshot'],model=model,scaler=scaler,journal=journal,
        policy_identity=policy_identity,mode='observe_only',states=None)
    payload=caller._clean(dict(schema='stage357_unfunded_research_decision_v1',active=False,states=None,
        observations=result['observations'],scores=result['scores'],selection=result['selection'],
        instrument_evidence=result['instrument_evidence'],cost_scenarios=result['cost_scenarios'],
        input_receipt=result['input_receipt'],observation_receipt=result['observation_receipt'],
        clock_domains=composed['clock_domains'],policy_identity=policy_identity,
        boundary='Complete unfunded research object;not an executable or funded account decision.'))
    seal=journal.append('unfunded_research_decision',payload,key='u20/research/'+result['observation_receipt']['entry_hash'])
    clock=caller._components().journal.evaluate_clock(frozen_at=policy_identity['frozen_at'],
        source_completed_at=composed['snapshot']['clock']['source_completed_at'],
        received_at=result['input_receipt']['recorded_at'],decision_sealed_at=seal['recorded_at'],
        D_open_at=composed['snapshot']['clock']['D_open_at'])
    return dict(result=result,research_seal=seal,research_clock=clock,active=False,states=None,
        new_fit=0,new_cash=0,paper_state_calls=0,T0_created=False)


def collect_from_api(api,symbols,*,output,journal,source_version,secrets=()):
    """Same bounded336 transport pattern, fixed3 rows, no catalog/metadata API."""
    b=components().transport;out=Path(output);(out/'raw').mkdir()
    report=dict(schema='stage357_daily3_capture_v1',status='running',items={s:dict(status='not_attempted') for s in symbols},
        requests=dict(single_symbol_serial=0,catalog=0,calendar=0,quote_list=0),source_version=source_version,
        duration_seconds=86400,data_length=3,retries=0,T0_created=False)
    raw_items={};circuit=False;connection_errors=0;unready=0
    stop=time.monotonic()+min(LIMITS['global_timeout_seconds'],max(0.,(_time(NOT_AFTER)-datetime.now(timezone.utc)).total_seconds()))
    try:
        for offset in range(0,len(symbols),LIMITS['batch_size']):
            if circuit or time.monotonic()>=stop:break
            batch=symbols[offset:offset+LIMITS['batch_size']];frames={};errors={}
            async def subscribe():
                nonlocal connection_errors,circuit
                for symbol in batch:
                    if circuit or time.monotonic()>=stop:break
                    try:
                        check_collection_window(datetime.now(timezone.utc));report['requests']['single_symbol_serial']+=1
                        report['items'][symbol]=dict(status='request_started')
                        frames[symbol]=api.get_kline_serial(symbol,86400,data_length=3);connection_errors=0
                    except Exception as error:
                        errors[symbol]=b._error(error,secrets)
                        if isinstance(error,(ConnectionError,OSError)) or type(error).__name__ in ('TqTimeoutError','ConnectionClosed'):
                            connection_errors+=1
                            if connection_errors>=LIMITS['max_consecutive_connection_errors']:circuit=True
            task=api.create_task(subscribe());until=min(stop,time.monotonic()+LIMITS['ready_timeout_seconds'])
            while time.monotonic()<until and not circuit:
                if task.done() and task.exception():raise task.exception()
                if task.done() and all(s in errors or s in frames and api.is_serial_ready(frames[s]) for s in batch):break
                api.wait_update(deadline=time.time()+min(3.,max(0.,until-time.monotonic())))
            if not task.done():task.cancel()
            ready_count=0
            for symbol in batch:
                if symbol not in frames:
                    report['items'][symbol]=dict(status='error' if symbol in errors else 'missing_timeout',**errors.get(symbol,{}));continue
                frame=frames[symbol].copy(deep=True);ready=bool(api.is_serial_ready(frames[symbol]));ready_count+=ready
                rows=b.raw_records(frame)
                raw=b._write(out/'raw'/(symbol.replace('.','_')+'.json'),dict(schema='stage357_raw_daily3_v1',symbol=symbol,
                    source_version=source_version,duration_seconds=86400,data_length=3,rows=rows,
                    dtypes={str(k):str(frame[k].dtype) for k in frame.columns},fresh_ready=ready,scaling_applied='none'))
                item=report['items'][symbol]=dict(status='raw_archived_pending_receipt',raw=raw,fresh_ready=ready)
                receipt=journal.append('daily3_raw_symbol',dict(symbol=symbol,raw=raw,source_version=source_version),
                    key=out.name+':'+symbol+':'+raw['sha256'])
                item.update(status='success' if ready else 'missing_timeout',receipt=receipt)
                raw_items[symbol]=dict(symbol=symbol,rows=rows,dtypes={str(k):str(frame[k].dtype) for k in frame.columns},
                    fresh_ready=ready,raw=raw,receipt=receipt,source_version=source_version)
            unready=unready+1 if frames and not ready_count else 0
            if unready>=LIMITS['max_consecutive_unready_batches']:circuit=True
        report['status']='completed' if all(v['status']=='success' for v in report['items'].values()) else 'partial'
    except Exception as error:
        report.update(status='partial',**b._error(error,secrets))
    report['circuit_open']=circuit
    for symbol,item in report['items'].items():
        if item['status'] in ('not_attempted','request_started'):
            item['status']='not_attempted_circuit' if circuit else 'not_persisted_before_deadline'
    return report,raw_items


def _bound(b):return components().transport._bound(b)
def _json(b):return json.loads(_bound(b))
def _lines(b):return [json.loads(v) for v in gzip.decompress(_bound(b)).decode().splitlines() if v]


def _freeze(auth):
    event=auth.get('freeze_event')
    if event is None:return None
    envelope=_json(event);receipt=envelope.get('receipt',{})
    if (envelope.get('schema')!='stage359_research_reference_freeze_v1'
            or receipt.get('kind')!='research_reference_freeze'
            or not re.fullmatch(r'[a-f0-9]{64}',receipt.get('entry_hash','')) or receipt.get('entry_hash')=='0'*64
            or not re.fullmatch(r'[a-f0-9]{64}',receipt.get('payload_sha256',''))
            or not receipt.get('recorded_at') or envelope.get('closure_manifest')!=auth.get('closure_manifest')
            or envelope.get('clock_contract')!=auth['inputs']['clock_contract']):
        raise ValueError('real321 reference freeze envelope and exact closure/clock bindings required')
    _bound(envelope['closure_manifest']);_time(receipt['recorded_at'])
    return receipt['recorded_at']


def run_batch(authorization,output):
    """Root freshout/exactauth, one reception -> normalization -> observation."""
    c=components();b=c.transport
    auth=b.read_json(authorization) if isinstance(authorization,(str,Path)) else deepcopy(authorization)
    if (auth.get('schema')!='stage357_daily_collect_compose_authorization_v1' or auth.get('authorized') is not True
            or auth.get('authorized_by')!='root' or auth.get('mode')!='observe_only' or auth.get('limits')!=LIMITS):
        raise ValueError('root exact u20 observe-only authorization required')
    out=Path(output).resolve()
    if out.exists():raise FileExistsError('fresh root output required')
    bundle=_json(auth['source_bundle'])
    for binding in bundle['sources']:_bound(binding)
    inp=auth['inputs'];scope=_json(inp['scope352']);contract=_json(inp['clock_contract'])
    if scope.get('schema')!='stage352_reference_freeze_and_thin_daily_scope_v1' or contract!=CLOCK_CONTRACT:
        raise ValueError('frozen352 scope/dual-domain contract required')
    freeze=_freeze(auth)
    if importlib.metadata.version('tqsdk')!=auth['tqsdk_version']:raise ValueError('SDK version mismatch')
    catalog=_json(inp['catalog338']);identities=_json(inp['identity354'])['identity_map'];symbols=catalog['symbols']
    if len(symbols)!=874 or len(identities)!=874 or set(symbols)!=set(identities):raise ValueError('accepted874 identities/catalog required')
    states={r['epoch']:r['final_state'] for r in _lines(inp['warmup344'])};inventory=_lines(inp['inventory344'])
    overlay=_lines(inp['overlay344']);economics=_json(inp['economics331'])
    for epoch,value in _json(inp['economics344']).items():
        if epoch in economics and economics[epoch]!=value:raise ValueError('compact economics conflict,no overwrite')
        economics[epoch]=value
    if len(states)!=757 or len(inventory)!=9520 or len(overlay)!=726:raise ValueError('accepted344 compact lineage/count mismatch')
    products=[r['product_id'] for r in csv.DictReader(io.StringIO(_bound(inp['roster']).decode('utf-8-sig')))]
    import numpy as np
    a=np.load(io.BytesIO(_bound(inp['source_calendar'])),allow_pickle=False)
    dates=([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in a]
           if a.dtype.kind in 'iu' else a.astype('datetime64[D]').astype(str).tolist())
    calendar=_json(inp['calendar338'])['days'];sessions=_lines(inp['sessions354'])
    model=_json(inp['model']);scaler=_json(inp['scaler'])
    check_collection_window(datetime.now(timezone.utc));out.mkdir(parents=True)
    collector_journal=b.load_journal().ForwardJournal(out/'source_journal',dict(purpose='u20_daily3_raw_receipts',T0=None))
    api=None;secrets=[];report=None;raw_items={};old_logging=logging.root.manager.disable;attempts=0
    try:
        cfg=b.read_json(auth['credential_path']);username,password=b._pure(b.CREDENTIAL_SOURCE,b.CREDENTIAL_SHA,'require_credentials',{'SETTINGS':cfg})();del cfg
        secrets=[username,password];logging.disable(logging.CRITICAL)
        remaining=min(LIMITS['global_timeout_seconds'],(_time(NOT_AFTER)-datetime.now(timezone.utc)).total_seconds())
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),b._alarm(remaining):
            from tqsdk import TqApi,TqAuth,TqSim
            check_collection_window(datetime.now(timezone.utc))
            with b._alarm(LIMITS['connect_timeout_seconds']):
                attempts+=1;api=TqApi(TqSim(),auth=TqAuth(username,password),debug=False,disable_print=True,web_gui=False)
            report,raw_items=collect_from_api(api,symbols,output=out,journal=collector_journal,
                source_version='tqsdk/'+auth['tqsdk_version'],secrets=secrets)
    except Exception as error:
        report=report or dict(status='partial',items={s:dict(status='not_attempted_connection_error') for s in symbols})
        report.update(**b._error(error,secrets))
    finally:
        if api is not None:
            try:
                with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),b._alarm(LIMITS['close_timeout_seconds']):api.close()
            except Exception as error:
                report=report or dict(status='partial');report.update(close_error=b._error(error,secrets))
        logging.disable(old_logging)
    report.update(api_instances_attempted=attempts,retries=0)
    capture=b._write(out/'capture_manifest.json',report)
    composed=compose_snapshot(raw_items,warmup_states=states,epoch_inventory=inventory,dates=dates,calendar=calendar,
        identity_map=identities,products=products,economics=economics,prior_overlay=overlay,sessions=sessions,
        clock_contract=contract,source_receipt=dict(inputs=inp,capture=capture),core=c.caller._components().core,
        execution_dependencies=())
    identity=c.caller.make_policy_identity(model,scaler,frozen_at=freeze)
    journal=c.caller._components().journal.ForwardJournal(out/'model_journal',identity)
    observed=observe_composed(composed,model=model,scaler=scaler,journal=journal,policy_identity=identity,caller=c.caller)
    # All numeric evidence is new/compact. No second read of captured raw.
    writer=components().transport._write;artifacts=dict(capture=capture)
    for name,value in [('result',observed),('clock_domains',composed['clock_domains']),
                       ('normalization_audit',composed['normalization_audit']),('canonical_overlay',composed['canonical_rows']),
                       ('warmup_state',composed['snapshot']['warmup_state']),('epoch_inventory',composed['snapshot']['_inventory']),
                       ('continuation_evidence',composed['snapshot']['_continuation_evidence'])]:
        artifacts[name]=writer(out/(name+'.json'),c.caller._clean(value))
    current={r['contract_epoch_id']:economics.get(r['contract_epoch_id'],{}) for r in composed['canonical_rows']}
    artifacts['current_economics']=writer(out/'current_economics.json',c.caller._clean(current))
    manifest=dict(schema='stage357_daily_collect_compose_manifest_v1',status='completed_observation' if raw_items else 'no_raw_observation',
        source_bundle=auth['source_bundle'],inputs=inp,artifacts=artifacts,target_u=U,mode='observe_only',
        T0=freeze,T0_created=False,freeze_event=auth.get('freeze_event'),research_clock=observed['research_clock'],
        counts=observed['result']['counts'],canonical_rows=len(composed['canonical_rows']),
        active=False,states=None,new_fit=0,new_cash=0,financial_D=0,SQL=0,old_native_cache=0,original_economics_projection_loads=0,
        metadata_queries=0,retries=0,api_instances_attempted=attempts,finished_at=datetime.now(timezone.utc).isoformat())
    writer(out/'manifest.json',manifest);writer(out/'terminal.json',manifest)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--authorization',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if not a.execute:raise SystemExit('explicit --execute required')
    result=run_batch(a.authorization,a.output);print(json.dumps(dict(status=result['status'],active=False,new_fit=0,new_cash=0)))
    return 0 if result['canonical_rows'] else 1


if __name__=='__main__':raise SystemExit(main())
