"""Source-only daily continuation of frozen357; no inference or account API.

Import/compose/restore are offline. Only run_daily_source with a fresh explicit
root authorization, inside its completed-source window, can create one TqApi.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,importlib.metadata,importlib.util,io,json,logging
from contextlib import redirect_stdout,redirect_stderr
from copy import deepcopy
from datetime import datetime,timezone
from functools import lru_cache
from pathlib import Path
from types import FunctionType,SimpleNamespace
import numpy as np

LINE=Path(__file__).resolve().parents[1]
FROZEN=LINE/'outputs/stage359_local_reference_actual/actual_run1/payload/research/lines/futures_full_market_long_signal_ai/tools/stage357_daily_collect_compose.py'
FROZEN_SHA='65d18a5c39e8df5442eafc2f5e2fd782f9bb492743339dc6cb5b013c91877e87'


def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if hasattr(v,'tolist'):return clean(v.tolist())
    if isinstance(v,float) and not np.isfinite(v):return None
    return v


def canonical(v,newline=False):
    return (json.dumps(clean(v),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+('\n' if newline else '')).encode()


def digest(v):return hashlib.sha256(canonical(v)).hexdigest()


def binding(path,raw=None):
    p=Path(path).resolve();raw=p.read_bytes() if raw is None else raw
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def bound(b):
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('bound artifact changed: '+Path(b['path']).name)
    return raw


def read(b):return json.loads(bound(b))


def write(path,value):
    raw=(json.dumps(clean(value),ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as f:f.write(raw)
    return binding(path,raw)


def calendar_dates(b):
    a=np.load(io.BytesIO(bound(b)),allow_pickle=False)
    return ([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in a]
            if a.dtype.kind in 'iu' else a.astype('datetime64[D]').astype(str).tolist())


@lru_cache(maxsize=1)
def legacy():
    if binding(FROZEN)['sha256']!=FROZEN_SHA:raise ValueError('frozen357 changed')
    spec=importlib.util.spec_from_file_location('source419_frozen357',FROZEN)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def day_view(scope_binding):
    scope=read(scope_binding);day=scope['day'];m=legacy()
    if scope['schema']!='stage418_bounded_next_daily_scope_v1' or scope['limits']!=m.LIMITS:raise ValueError('explicit418 scope and unchanged limits required')
    g=dict(m.__dict__,U=day['u_date'],PREVIOUS=day['previous_u'],D=day['D_date'],
           NOT_BEFORE=day['hard_not_before'],NOT_AFTER=day['hard_not_after'])
    def clone(f):
        result=FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)
        result.__kwdefaults__=deepcopy(f.__kwdefaults__);return result
    original_check=clone(m.check_collection_window)
    def check(now):
        try:original_check(now)
        except ValueError as e:raise ValueError('outside completed-source window for '+day['u_date']) from e
    g['check_collection_window']=check
    c=m.components()
    return SimpleNamespace(scope=scope,original=m,check_collection_window=check,
        collect_from_api=clone(m.collect_from_api),compose_snapshot=clone(m.compose_snapshot),
        core=c.caller._components().core,adapter=c.adapter,transport=c.transport,
        journal=c.transport.load_journal())


def load_checkpoint(pointer_binding):
    p=read(pointer_binding);b=p['source_checkpoint_inputs']
    states,inventory,overlay=(read(b[k]) for k in ('warmup_state','epoch_inventory','canonical_overlay'))
    if not isinstance(states,dict) or len({v['epoch'] for v in inventory})!=len(inventory):raise ValueError('JSON checkpoint identity mismatch')
    if any(v['trade_date']!=p['last_u'] for v in overlay):raise ValueError('previous-day overlay mismatch')
    return dict(warmup_states=states,epoch_inventory=inventory,prior_overlay=overlay,
        previous_u=p['last_u'],previous_u_index=p['last_u_index'],pointer_binding=pointer_binding)


def compose_day(raw_items,*,scope,checkpoint,operational_binding,execution_dependencies,core):
    # The explicit globals view leaves the original module's u20 bindings intact.
    sb=scope['_binding'] if '_binding' in scope else binding(LINE/'outputs/stage418_next_daily_scope/scope.json')
    view=day_view(sb);day=scope['day'];document=read(operational_binding);op=document.get('bindings',document)
    if checkpoint['previous_u']!=day['previous_u']:raise ValueError('wrong source checkpoint day')
    dates=calendar_dates(scope['canonical_calendar'])
    if dates[day['u_index']]!=day['u_date'] or dates[day['D_index']]!=day['D_date'] or day['D_index']!=day['u_index']+1:raise ValueError('source-calendar day/index mismatch')
    calendar=read(op['calendar'])['days'];identity=read(op['identity'])['identity_map']
    sessions=[json.loads(v) for v in gzip.decompress(bound(op['sessions'])).splitlines() if v]
    products=[v['product_id'] for v in csv.DictReader(io.StringIO(bound(scope['full_inputs_unchanged']['roster']).decode('utf-8-sig')))]
    if 'economics' in op:economics=read(op['economics'])
    else:
        economics=read(scope['full_inputs_unchanged']['economics331'])
        for e,v in read(scope['full_inputs_unchanged']['economics344']).items():
            if e in economics and economics[e]!=v:raise ValueError('economics conflict')
            economics[e]=v
    deps=execution_dependencies
    if deps.get('schema')!='stage421_execution_dependencies_v1':raise ValueError('explicit421 dependency union required')
    owners=[dict(epoch=e,roles=[v for v in deps['roles'] if v['epoch']==e]) for e in deps['epochs']]
    context=dict(previous_u=day['previous_u'],u_date=day['u_date'],D_date=day['D_date'],
        overlap_previous_trade_date=day['previous_u'],legacy_algorithm='stage357',
        legacy_u19_labels_are_previous_day_aliases=True)
    composed=view.compose_snapshot(raw_items,warmup_states=checkpoint['warmup_states'],epoch_inventory=checkpoint['epoch_inventory'],
        dates=dates,calendar=calendar,identity_map=identity,products=products,economics=economics,
        prior_overlay=checkpoint['prior_overlay'],sessions=sessions,clock_contract=read(scope['full_inputs_unchanged']['clock_contract']),
        source_receipt=dict(schema='stage419_day_source_input_v1',day_context=context,checkpoint=checkpoint['pointer_binding'],
            capture=checkpoint.get('capture'),operational=operational_binding),core=core,execution_dependencies=owners)
    composed['day_context']=context;composed['execution_dependencies']=deepcopy(deps)
    composed['clock_domains']['day_context']=context
    for row in composed['canonical_rows']:row['unit_overlay']['overlap_previous_trade_date']=day['previous_u']
    # A missing owner's identity cannot disappear merely because no epoch can be named.
    if deps.get('unresolved') or deps.get('complete') is not True:
        for name,key in (('input_completion','source_completed_at'),('execution_deadline','D_open_at')):
            composed['clock_domains'][name]['unresolved_owner_dependencies']=deepcopy(deps.get('unresolved',[]))
            composed['clock_domains'][name][key]=None;composed['snapshot']['clock'][key]=None
    return composed


def persist_day(composed,*,scope_binding,output,source_metadata,source_journal=None):
    out=Path(output).resolve();view=day_view(scope_binding)
    if source_journal is None:
        out.mkdir(parents=True,exist_ok=False)
        source_journal=view.journal.ForwardJournal(out/'source_journal',dict(schema='stage419_source_identity_v1',scope=scope_binding,day=composed['day_context']))
    elif not out.is_dir() or (out/'manifest.json').exists():raise ValueError('fresh in-progress source directory required')
    snap=composed['snapshot'];art={}
    metadata={k:snap[k] for k in ('schema','development_only','u_date','u_index','dates','economics','products','D_context','clock','source','version','source_receipt','incremental_audit')}
    values=dict(snapshot_metadata=metadata,warmup_state=snap['warmup_state'],epoch_inventory=snap['_inventory'],
        continuation_evidence=snap['_continuation_evidence'],canonical_overlay=composed['canonical_rows'],
        normalization_audit=composed['normalization_audit'],normalization_receipt=composed['normalization_receipt'],
        observations=composed['prescore_observations'],clock_domains=composed['clock_domains'],execution_dependencies=composed['execution_dependencies'])
    for name,value in values.items():art[name]=write(out/(name+'.json'),value)
    payload=dict(schema='stage419_composed_source_receipt_v1',day_context=composed['day_context'],scope=scope_binding,
        artifacts=art,source_metadata=source_metadata,observations_sha256=digest(composed['prescore_observations']),
        clock_domains_sha256=digest(composed['clock_domains']),active=False,model_inference=0)
    receipt=source_journal.append('day_source_composed',payload,key=snap['u_date']+'/source_composed')
    status='completed_source' if source_metadata.get('capture_status')=='completed' else 'partial_source'
    manifest=dict(schema='stage419_day_source_v1',status=status,scope=scope_binding,day_context=composed['day_context'],
        artifacts=art,source_metadata=source_metadata,source_receipt=receipt,source_journal=str(source_journal.path),
        observations_sha256=payload['observations_sha256'],clock_domains_sha256=payload['clock_domains_sha256'],
        active=False,states=None,model_inference=0,new_fit=0,new_cash=0,financial_D=0,SQL=0,retries=0,
        legacy_helper=dict(path=str(FROZEN),sha256=FROZEN_SHA),finished_at=datetime.now(timezone.utc).isoformat())
    result=write(out/'manifest.json',manifest);write(out/'terminal.json',manifest);return result


def restore_day(manifest_binding):
    m=read(manifest_binding)
    if m['schema']!='stage419_day_source_v1' or m['status'] not in ('completed_source','partial_source'):raise ValueError('persisted day-source object required')
    art={k:read(v) for k,v in m['artifacts'].items()};meta=art['snapshot_metadata'];view=day_view(m['scope']);core=view.core
    path=Path(m['source_journal']);policy=path/'policy_identity.json';index=path/'journal.jsonl'
    if not policy.is_file() or not index.is_file():raise ValueError('existing source journal required; no repair')
    pm=json.loads(policy.read_bytes());ph=hashlib.sha256(canonical(pm['policy_identity'],True)).hexdigest();previous='0'*64;found=False
    for i,line in enumerate(index.read_bytes().splitlines(keepends=True)):
        e=json.loads(line);content={k:v for k,v in e.items() if k!='entry_hash'}
        if not line.endswith(b'\n') or e['sequence']!=i or e['previous_entry_hash']!=previous or e['policy_sha256']!=ph or hashlib.sha256(canonical(content,True)).hexdigest()!=e['entry_hash']:raise ValueError('source journal chain mismatch')
        previous=e['entry_hash'];found=found or e==m['source_receipt']
    receipt=m['source_receipt'];raw=(path/'objects'/(receipt['payload_sha256']+'.json')).read_bytes()
    if not found or hashlib.sha256(raw).hexdigest()!=receipt['payload_sha256']:raise ValueError('source receipt object mismatch')
    payload=json.loads(raw)
    if payload['artifacts']!=m['artifacts'] or payload['scope']!=m['scope']:raise ValueError('source receipt binding mismatch')
    inventory=art['epoch_inventory'];warmup=art['warmup_state'];u=meta['u_index'];states={e:core.WilderState.from_dict(v) for e,v in warmup.items()}
    arrays={v['epoch']:states[v['epoch']].to_series() if v['epoch'] in states else core.WilderState().to_series() for v in inventory}
    series={e:states[e] if e in states and states[e].last_seen==u else a for e,a in arrays.items()}
    snap=dict(meta,warmup_state=warmup,series_by_epoch=series,market=view.adapter.SnapshotMarket(arrays,meta['dates']),
        _inventory=inventory,_continuation_evidence=art['continuation_evidence'])
    if meta['development_only'] is not True:raise ValueError('source remains development-only')
    obs=core.build_u_observations(series,u,meta['dates'],meta['economics'],meta['products'],D_context=meta['D_context'])
    if digest(obs)!=m['observations_sha256'] or digest(art['observations'])!=m['observations_sha256'] or digest(art['clock_domains'])!=m['clock_domains_sha256']:raise ValueError('restored observations/raw26 or domains differ')
    return dict(snapshot=snap,canonical_rows=art['canonical_overlay'],normalization_audit=art['normalization_audit'],
        normalization_receipt=art['normalization_receipt'],prescore_observations=clean(obs),clock_domains=art['clock_domains'],
        day_context=m['day_context'],execution_dependencies=art['execution_dependencies'],
        restoration=dict(schema='stage419_final_checkpoint_restore_v1',manifest=manifest_binding,
            observations_sha256=digest(obs),source_receipt=receipt,unpersisted_diagnostics_omitted=['_row_dispositions','unsupported_catalog','product_states']))


def run_daily_source(authorization_binding,output):
    auth=read(authorization_binding);view=day_view(auth['scope']);scope=view.scope;day=scope['day']
    view.check_collection_window(datetime.now(timezone.utc))  # Before credentials, SDK or API.
    out=Path(output).resolve()
    if (auth.get('schema')!='stage419_daily_source_authorization_v1' or auth.get('authorized') is not True
            or auth.get('authorized_by')!='root' or auth.get('market_execution_authorized') is not True
            or auth.get('execution_environment')!='approved_outside_sandbox' or auth.get('max_API_instances')!=1
            or auth.get('retries')!=0 or str(out)!=scope['source419']['targets']['source']):raise ValueError('fresh explicit root one-API authorization required')
    if out.exists():raise FileExistsError('fresh source directory required')
    if importlib.metadata.version('tqsdk')!=scope['tqsdk_version']:raise ValueError('SDK version mismatch')
    ck=load_checkpoint(scope['previous']['pointers']);document=read(auth['operational']);op=document.get('bindings',document);deps=read(auth['execution_dependencies'])
    symbols=read(scope['catalog'])['symbols'];ids=read(op['identity'])['identity_map']
    if len(symbols)!=874 or set(symbols)!=set(ids):raise ValueError('complete874 catalog/identity required')
    b=view.transport;out.mkdir(parents=True);journal=view.journal.ForwardJournal(out/'source_journal',dict(schema='stage419_source_identity_v1',scope=auth['scope'],day=day))
    api=None;secrets=[];attempts=0;items={};report=None;old_logging=logging.root.manager.disable
    try:
        cfg=b.read_json(scope['credential_path']);username,password=b._pure(b.CREDENTIAL_SOURCE,b.CREDENTIAL_SHA,'require_credentials',{'SETTINGS':cfg})();del cfg
        secrets=[username,password];logging.disable(logging.CRITICAL)
        remaining=min(scope['limits']['global_timeout_seconds'],(b._utc(day['hard_not_after'])-datetime.now(timezone.utc)).total_seconds())
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),b._alarm(remaining):
            from tqsdk import TqApi,TqAuth,TqSim
            view.check_collection_window(datetime.now(timezone.utc))
            with b._alarm(scope['limits']['connect_timeout_seconds']):
                attempts+=1;api=TqApi(TqSim(),auth=TqAuth(username,password),debug=False,disable_print=True,web_gui=False)
            report,items=view.collect_from_api(api,symbols,output=out,journal=journal,source_version='tqsdk/'+scope['tqsdk_version'],secrets=secrets)
    except Exception as e:
        report=report or dict(status='partial',items={s:dict(status='not_attempted_connection_error') for s in symbols})
        report.update(**b._error(e,secrets))
    finally:
        if api is not None:
            try:
                with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()),b._alarm(scope['limits']['close_timeout_seconds']):api.close()
            except Exception as e:report.update(close_error=b._error(e,secrets))
        logging.disable(old_logging)
    report.update(api_instances_attempted=attempts,retries=0,day_context=day)
    capture=write(out/'capture_manifest.json',report)
    if not items:
        terminal=dict(schema='stage419_day_source_v1',status='no_raw_observation',scope=auth['scope'],day_context=day,
            capture=capture,API_instances=attempts,retries=0,model_inference=0,new_fit=0,new_cash=0,financial_D=0,active=False,states=None)
        result=write(out/'manifest.json',terminal);write(out/'terminal.json',terminal);return result
    ck['capture']=capture;scope=dict(scope,_binding=auth['scope'])
    composed=compose_day(items,scope=scope,checkpoint=ck,operational_binding=auth['operational'],execution_dependencies=deps,core=view.core)
    return persist_day(composed,scope_binding=auth['scope'],output=out,source_journal=journal,
        source_metadata=dict(capture=capture,capture_status=report['status'],raw_items_count=len(items),
            authorization=authorization_binding,operational=auth['operational'],execution_dependencies=auth['execution_dependencies'],API_instances=attempts))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--authorization',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if not a.execute:raise SystemExit('explicit future root --execute required')
    print(json.dumps(run_daily_source(binding(a.authorization),a.output)))
