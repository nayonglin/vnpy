"""One root-authorized expansion of accepted quote metadata; no SDK or finance."""
from collections import Counter
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import time


def bound(b):
    raw=Path(b['path']).read_bytes()
    if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:
        raise ValueError('bound input changed: '+b['path'])
    return raw


def module(name,b):
    bound(b)
    spec=importlib.util.spec_from_file_location(name,b['path'])
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj


def write(path,value):
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb') as f:f.write(raw)
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def run(auth_path):
    a=json.loads(Path(auth_path).read_text())
    if (a.get('schema')!='stage354_offline_session_authorization_v1'
            or a.get('authorized') is not True or a.get('T0') is not None
            or a.get('scope')!='874_metadata_three_dates_unfunded'):
        raise ValueError('root exact offline authorization required')
    bound(a['sources']['runner'])
    pure=module('stage354_pure',a['sources']['sessions'])
    transport=module('stage354_identity_parts',a['sources']['identity_parts'])
    inp=a['inputs'];review=json.loads(bound(inp['review']))
    if (review.get('decision')!='GO_METADATA_SESSION_SUBSET' or review.get('status')!='completed'
            or review.get('core_blockers')!=0 or review['coverage']['delivery_nominal_mismatch']!=0):
        raise ValueError('accepted session subset required')
    out=Path(a['output']);out.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();terminal=dict(status='started',T0=None,new_fit=0,new_cash=0,
        API=0,SQL=0,old_cache=0,economics=0,forward_observations=0)
    try:
        metadata=json.loads(bound(inp['metadata']))
        calendar=json.loads(bound(inp['calendar']))['days']
        prior=json.loads(bound(inp['identity']))['identity_map']
        regular=json.loads(bound(inp['regular_evidence']))
        overlay=[json.loads(v) for v in gzip.decompress(bound(inp['dependencies'])).decode().splitlines() if v]
        dependencies={r['native_values']['symbol']:r['contract_epoch_id'] for r in overlay}
        if len(overlay)!=len(dependencies) or len(dependencies)!=726 or len(metadata['items'])!=874:
            raise ValueError('fixed874 metadata /726 full pre-selection dependency domain required')
        evidence=dict(policy='operational_regular_schedule',source_receipt=dict(
            regular=inp['regular_evidence'],metadata_acceptance=inp['review']))
        sessions=[];by_key={};identities={};identity_errors=[];template_shapes=Counter()
        for symbol,row in sorted(metadata['items'].items()):
            f=row['fields'];parts=transport.symbol_parts(symbol)
            identity_received=(row.get('response_matches_requested_symbol') is True
                and f['instrument_id']['value']==symbol and f['exchange_id']['value']==parts['exchange'])
            received=(identity_received and all(f[k]['state']=='known' for k in
                ('instrument_id','exchange_id','ins_class','trading_time.day','trading_time.night','expire_datetime')))
            meta=dict(symbol=symbol,metadata_received=received,day=f['trading_time.day']['value'],
                night=f['trading_time.night']['value'],expire_datetime=f['expire_datetime']['value'],
                source_receipt=dict(metadata=inp['metadata'],receiver321=metadata['receipt']))
            template_shapes[(str(f['trading_time.day']['value']),str(f['trading_time.night']['value']))]+=1
            for day in regular['dates']:
                result=pure.expand_sessions(meta,day,calendar=calendar,
                    night_anchors=regular['night_anchor'],evidence=evidence)
                sessions.append(result);by_key[(symbol,day)]=result
            dy,dm=f['delivery_year']['value'],f['delivery_month']['value']
            code=parts['delivery_code_raw'];expected=f'{dy%100:02d}{dm:02d}' if len(code)==4 else f'{dy%10}{dm:02d}'
            epoch=f"{parts['exchange']}.{parts['product_hint']}.{dy:04d}{dm:02d}"
            conflicts=[]
            if not identity_received:conflicts.append('response_identity')
            if any(f[k]['state']!='known' for k in ('delivery_year','delivery_month')):conflicts.append('delivery_unknown')
            if code!=expected:conflicts.append('literal_code_delivery_conflict')
            if symbol in prior and prior[symbol]!=epoch:conflicts.append('prior_explicit_identity_conflict')
            if conflicts:identity_errors.append(dict(symbol=symbol,reasons=conflicts))
            identities[symbol]=dict(epoch=epoch if not conflicts else None,
                state='explicit_quote_nominal_delivery' if not conflicts else 'unknown',
                previous_epoch=prior.get(symbol),newly_observed=symbol not in prior,
                delivery_year=dy,delivery_month=dm,source_receipt=metadata['receipt'],
                observed_at=metadata['receipt']['recorded_at'],model_input_eligible=False)
        if any(dependencies[s]!=prior.get(s) for s in dependencies):
            raise ValueError('pre-selection dependencies do not match accepted explicit identity map')
        counts={day:dict(Counter(v['state'] for v in sessions if v['trade_date']==day)) for day in regular['dates']}
        unknowns=[dict(symbol=v['symbol'],date=v['trade_date'],reasons=v['reasons'])
            for v in sessions if v['state']=='unknown']
        windows=[]
        for u,D in [('2026-10-19','2026-10-20'),('2026-10-20','2026-10-21')]:
            urows=[by_key[(s,u)] for s in dependencies];drows=[by_key[(s,D)] for s in dependencies]
            u_unknown=[v['symbol'] for v in urows if v['state']!='operational_regular_schedule']
            d_unknown=[v['symbol'] for v in drows if v['state']!='operational_regular_schedule']
            ends=[v['session_end'] for v in urows if v['session_end']]
            opens=[v['first_open'] for v in drows if v['first_open']]
            windows.append(dict(u_date=u,D_date=D,domain='all726 observed inputs before selection;not2winners',
                dependencies=len(dependencies),u_unconfirmed=u_unknown,D_unconfirmed=d_unknown,
                latest_known_session_end=max(ends) if ends else None,
                earliest_known_D_open=min(opens) if opens else None,
                all_dependency_schedules_known=not u_unknown and not d_unknown,
                assurance='bounded operational regular-day candidates;new completed price snapshot still required'))
        samples=[]
        for prefix in ('CFFEX.T.','CFFEX.IF.','SHFE.AU.','SHFE.FU.'):
            choices=sorted(s for s,e in dependencies.items() if e.startswith(prefix))
            if choices:
                s=choices[0];samples.append(dict(symbol=s,epoch=dependencies[s],
                    day=metadata['items'][s]['fields']['trading_time.day']['value'],
                    night=metadata['items'][s]['fields']['trading_time.night']['value']))
        raw=("\n".join(json.dumps(r,ensure_ascii=False,sort_keys=True,allow_nan=False) for r in sessions)+'\n').encode()
        compressed=gzip.compress(raw,compresslevel=1,mtime=0)
        with (out/'sessions.jsonl.gz').open('xb') as f:f.write(compressed)
        artifacts=dict(sessions=dict(path=str(out/'sessions.jsonl.gz'),bytes=len(compressed),sha256=hashlib.sha256(compressed).hexdigest()))
        artifacts['identities']=write(out/'identity_observations.json',dict(
            schema='stage354_nominal_delivery_identity_observations_v1',source=inp['metadata'],
            identity_map={s:v['epoch'] for s,v in identities.items() if v['epoch']},
            items=identities,conflicts=identity_errors,model_input_eligible=False,
            boundary='Known now from observed nominal delivery metadata;does not rewrite past known status or qualify price/units/history/economics.'))
        summary=dict(schema='stage354_offline_session_observation_summary_v1',status='completed',
            inputs=inp,metadata_source_status='partial',subset='accepted9fields;multiplier remains unknown',
            symbols=len(metadata['items']),session_rows=len(sessions),date_states=counts,
            unknown_sessions=unknowns,template_shapes=len(template_shapes),windows=windows,
            prior_explicit_identities=len(prior),new_identity_observations=sum(v['newly_observed'] and v['epoch'] is not None for v in identities.values()),
            identity_count=sum(v['epoch'] is not None for v in identities.values()),identity_conflicts=identity_errors,
            contract_examples=samples,dependency_symbols=sorted(dependencies),
            no_source_completed_or_D_open_assigned=True,price_snapshots_received=0,
            artifacts=artifacts,API=0,SQL=0,old_cache=0,economics=0,new_fit=0,new_cash=0,
            T0=None,forward_observations=0,active=False,
            boundary='Operational schedule candidates only;no claim of exhaustive exception search,firstpublication,finality or strategy alpha.')
        artifacts['summary']=write(out/'summary.json',summary)
        terminal.update(status='completed',exit_code=0,artifacts=artifacts,
            session_rows=len(sessions),identity_count=summary['identity_count'],windows=windows)
    except Exception as error:
        terminal.update(status='failed_no_retry',exit_code=1,error_type=type(error).__name__,error=str(error))
        raise
    finally:
        terminal.update(elapsed_seconds=time.perf_counter()-start,finished_at=datetime.now(timezone.utc).isoformat())
        write(out/'terminal.json',terminal)
        print(json.dumps({k:v for k,v in terminal.items() if k!='artifacts'},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--authorization',required=True)
    run(p.parse_args().authorization)

