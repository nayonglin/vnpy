"""Root-only one-pass u19 observer; no API/SQL/native cache or paper state.

No data is read on import. --execute needs an exact authorization.337's bounded
factor1 acceptance, not raw receiver success, permits the canonical overlay.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import time
import traceback
import numpy as np

U='2026-10-19';PREVIOUS='2026-10-16';D='2026-10-20'
FIELDS=('open','high','low','close','volume','close_oi')
BUDGET=dict(date_rows_passes=1,raw_index_passes=1,warmup_passes=1,inventory_passes=1,
    calendar_loads=1,roster_passes=1,economics_loads=1,model_loads=1,scaler_loads=1,
    API=0,SQL=0,native_cache=0,fit=0,cash=0,financial_state_calls=0)


def _finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)


def prepare_overlay(rows,raw_index,*,date_rows_binding,acceptance_binding):
    """Only the fixed337 u19 predicate. rows yields(dict,exact343lineSHA)."""
    accepted=[];rejected=[];counts=Counter();seen=set();products=set()
    for row,line_sha in rows:
        counts['input_rows']+=1;day=row.get('trade_date')
        if day!=U:
            counts['u20_excluded' if day==D else 'other_dates_excluded' if day else 'unknown_dates_excluded']+=1
            continue
        counts['u19_rows']+=1;symbol=row['symbol'];item=raw_index.get(symbol)
        if (not item or row.get('raw_sha256')!=item['raw']['sha256']
                or row.get('received_at')!=item['receipt']['recorded_at']):
            raise ValueError('343 row/raw321 receipt lineage mismatch')
        v=row.get('native_values',{});reason=None
        if (not all(_finite(v.get(k)) and v[k]>0 for k in FIELDS[:5])
                or v['low']>min(v['open'],v['close']) or v['high']<max(v['open'],v['close'])
                or v['high']<v['low'] or (v.get('close_oi') is not None
                and (not _finite(v['close_oi']) or v['close_oi']<0))):
            reason='invalid_or_zero_volume';counts['invalid_or_zero_volume_rows']+=1
        elif row.get('identity_state')!='known_explicit' or not row.get('contract_epoch_id'):
            reason='identity_unknown';counts['identity_unknown_geometry_rows']+=1
        elif row.get('date_mapping_state')!='operational_midnight_label' or row.get('fresh_ready') is not True:
            reason='date_or_ready_unknown';counts['date_or_ready_unknown_rows']+=1
        if reason:
            rejected.append(dict(symbol=symbol,trade_date=day,contract_epoch_id=row.get('contract_epoch_id'),
                reason=reason,native_values=deepcopy(v),native_missing_fields=deepcopy(row.get('native_missing_fields',[])),
                raw_sha256=row['raw_sha256'],raw_row_index=row['raw_row_index'],date343_line_sha256=line_sha))
            continue
        epoch=row['contract_epoch_id'];key=(epoch,day)
        if key in seen:raise ValueError('duplicate accepted epoch/date')
        seen.add(key);products.add(epoch.rsplit('.',1)[0])
        provenance=dict(date343_artifact=deepcopy(date_rows_binding),date343_line_sha256=line_sha,
            raw_artifact=deepcopy(item['raw']),raw_row_index=row['raw_row_index'],
            receiver321_receipt=deepcopy(item['receipt']),accepted337=deepcopy(acceptance_binding))
        accepted.append(dict(contract_epoch_id=epoch,trade_date=day,canonical_values={k:v.get(k) for k in FIELDS},
            native_values=deepcopy(v),native_missing_fields=deepcopy(row.get('native_missing_fields',[])),
            unit_overlay=dict(volume_factor=1,oi_factor=1,scope='accepted337_same_batch_u19_only'),
            raw_datetime_literal=row.get('raw_datetime_literal'),raw_ns_original=row.get('raw_ns_original'),
            recovered_ns=row.get('recovered_ns'),timestamp_recovery_state=row.get('timestamp_recovery_state'),
            raw_local_iso_recovered=row.get('raw_local_iso_recovered'),
            identity_state='known_explicit',date_mapping_state='operational_midnight_label',
            date_mapping_rule=row.get('date_mapping_rule'),units_status='canonical_normalized',
            canonical_quality_status='accepted',model_input_eligible=True,source_receipt=provenance,
            received_at=row['received_at'],source_completed_at=None,completion_observed_at=None,
            D_open_at=None,vendor_finality='unknown',source_first_published_at=None))
    counts.update(accepted_rows=len(accepted),accepted_products=len(products))
    return accepted,rejected,dict(counts)


def _read(binding):
    raw=Path(binding['path']).read_bytes()
    if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:
        raise ValueError('exact binding changed: '+binding['path'])
    return raw


def _json(binding):return json.loads(_read(binding))


def _lines(raw):
    with gzip.GzipFile(fileobj=io.BytesIO(raw),mode='rb') as stream:
        for line in stream:
            if line.strip():yield json.loads(line),hashlib.sha256(line.rstrip(b'\n')).hexdigest()


def _module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


def _write(path,value):
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with Path(path).open('xb') as stream:stream.write(raw)
    return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _jsonl(path,rows):
    buffer=io.BytesIO()
    with gzip.GzipFile(fileobj=buffer,mode='wb',compresslevel=1,mtime=0) as stream:
        for row in rows:stream.write((json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())
    raw=buffer.getvalue()
    with Path(path).open('xb') as stream:stream.write(raw)
    return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _stat(binding):
    st=Path(binding['path']).stat();actual=dict(st_size=st.st_size,st_ino=st.st_ino,st_mtime_ns=st.st_mtime_ns)
    if binding.get('stat_expectation') and actual!=binding['stat_expectation']:
        raise ValueError('source stat changed: '+binding['path'])
    if st.st_size!=binding['bytes']:raise ValueError('source size changed')
    return actual


def run_once(authorization):
    auth=json.loads(Path(authorization).read_text()) if isinstance(authorization,(str,Path)) else deepcopy(authorization)
    if (auth.get('schema')!='stage346_incremental_observation_authorization_v1' or auth.get('authorized') is not True
            or auth.get('authorized_by')!='root' or auth.get('T0') is not None or auth.get('mode')!='observe_only'
            or auth.get('read_budget')!=BUDGET):raise ValueError('exact root one-shot observation authorization required')
    for b in auth['sources'].values():_read(b)
    if Path(auth['sources']['runner']['path']).resolve()!=Path(__file__).resolve():raise ValueError('wrong runner source')
    inputs=auth['inputs'];review=_json(inputs['source_acceptance']);prior_review=_json(inputs['prior_review'])
    prior=_json(inputs['prior_source_receipt']);offline=_json(inputs['date_manifest'])
    scope=review.get('accepted_overlay_scope',{})
    if (review.get('schema')!='stage337_recent_daily_receiver_actual_review_v1' or review.get('status')!='completed'
            or review.get('core_blockers')!=0 or review.get('canonical_rows_accepted') is not True
            or review['inputs']['date_rows']!=inputs['date_rows'] or scope.get('u_date')!=U
            or scope.get('factor')!=1 or scope.get('rows')!=726 or scope.get('product_count')!=85
            or scope.get('mode')!='observe_only' or scope.get('T0') is not None):raise ValueError('limited337 acceptance mismatch')
    if (prior_review.get('status')!='completed' or prior_review.get('core_blockers')!=0
            or prior_review['bindings']['source_receipt']!=inputs['prior_source_receipt']
            or prior.get('status')!='completed' or prior.get('snapshot_date')!=PREVIOUS
            or prior['artifacts']['warmup_evidence']!=inputs['warmup']
            or prior['artifacts']['epoch_inventory']!=inputs['inventory']):raise ValueError('accepted331 checkpoint lineage mismatch')
    if (offline.get('status')!='completed' or offline['artifacts']['date_rows']!=inputs['date_rows']
            or offline['artifacts']['raw_artifact_index']!=inputs['raw_index']):raise ValueError('343 artifact lineage mismatch')
    before={k:_stat(v) for k,v in inputs.items()}
    out=Path(auth['output']).resolve();out.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter();counts={k:0 for k in BUDGET};artifacts={}
    terminal=dict(schema='stage346_incremental_observation_terminal_v1',status='started',T0=None,
        started_at=datetime.now(timezone.utc).isoformat(),u_date=U,new_fit=0,new_cash=0,financial_D=0,
        forward_observations=0,read_counts=counts)
    try:
        counts['raw_index_passes']+=1;index={}
        for r,_ in _lines(_read(inputs['raw_index'])):
            if r['symbol'] in index:raise ValueError('raw index symbol duplicate')
            index[r['symbol']]=r
        counts['date_rows_passes']+=1
        overlay,rejections,coverage=prepare_overlay(_lines(_read(inputs['date_rows'])),index,
            date_rows_binding=inputs['date_rows'],acceptance_binding=inputs['source_acceptance'])
        expected=dict(input_rows=30590,u19_rows=865,accepted_rows=726,accepted_products=85,
            identity_unknown_geometry_rows=13,invalid_or_zero_volume_rows=126)
        if any(coverage.get(k)!=v for k,v in expected.items()):raise ValueError('accepted u19 overlay coverage changed')
        artifacts['canonical_overlay']=_jsonl(out/'canonical_overlay.jsonl.gz',overlay)
        artifacts['rejections']=_jsonl(out/'u19_rejections.jsonl.gz',rejections)
        normalization=dict(status='completed',canonical_rows_accepted=True,accepted337=inputs['source_acceptance'],
            overlay=artifacts['canonical_overlay'],date_rows=inputs['date_rows'],coverage=coverage,
            factor=1,scope='same338batch/343/u19only;not universal future units',T0=None,source_completed_at=None)
        artifacts['canonical_receipt']=_write(out/'canonical_receipt.json',normalization)
        counts['warmup_passes']+=1;states={}
        for row,_ in _lines(_read(inputs['warmup'])):
            if row['epoch'] in states:raise ValueError('warmup epoch duplicate')
            states[row['epoch']]=row['final_state']
        counts['inventory_passes']+=1;inventory=[r for r,_ in _lines(_read(inputs['inventory']))]
        if len(states)!=744 or len(inventory)!=9520:raise ValueError('fixed331 compact coverage mismatch')
        counts['calendar_loads']+=1;a=np.load(io.BytesIO(_read(inputs['calendar'])),allow_pickle=False)
        dates=([str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in a]
               if a.dtype.kind in 'iu' else a.astype('datetime64[D]').astype(str).tolist())
        if len(dates)!=5587 or dates[5288:5291]!=[PREVIOUS,U,D]:raise ValueError('source date/index mismatch')
        counts['roster_passes']+=1;roster=list(csv.DictReader(io.StringIO(_read(inputs['roster']).decode('utf-8-sig'))))
        products=[r['product_id'] for r in roster]
        counts['economics_loads']+=1
        with Path(inputs['economics']['path']).open() as stream:economics=json.load(stream)['instruments']
        counts['model_loads']+=1;model=_json(inputs['model'])
        counts['scaler_loads']+=1;scaler=_json(inputs['scaler'])
        caller=_module('stage346_caller',auth['sources']['caller']['path'])
        adapter=_module('stage346_adapter',auth['sources']['adapter']['path'])
        snapshot=adapter.build_incremental_snapshot(states,inventory,overlay,dates=dates,previous_u_date=PREVIOUS,
            u_date=U,products=products,economics=economics,
            calendar_confirmation=dict(confirmed=True,u_date=U,u_index=5289,proof=dict(source_calendar=inputs['calendar'],accepted343=inputs['source_acceptance'])),
            normalization_receipt=normalization,source_receipt=dict(inputs=inputs,source338_status='partial'),
            D_context=dict(confirmed=True,D_index=5290,D_date=D,proof='bound_source_calendar'),
            clock=dict(source_completed_at=None,D_open_at=None),core=caller._components().core)
        modes=snapshot['incremental_audit']['continuation_modes']
        if modes!=dict(continued_exact_prior_u=713,known_epoch_prior_gap=13):raise ValueError('expected713 continuation/13 known gaps mismatch')
        artifacts['continuation_evidence']=_jsonl(out/'continuation_evidence.jsonl.gz',snapshot['_continuation_evidence'])
        artifacts['inventory']=_jsonl(out/'epoch_inventory.jsonl.gz',snapshot['_inventory'])
        artifacts['warmup']=_jsonl(out/'warmup_state.jsonl.gz',
            (dict(epoch=e,final_state=s) for e,s in sorted(snapshot['warmup_state'].items())))
        artifacts['current_economics']=_write(out/'current_economics.json',caller._clean(
            {r['contract_epoch_id']:economics.get(r['contract_epoch_id'],{}) for r in overlay}))
        identity=caller.make_policy_identity(model,scaler,frozen_at=None)
        journal=caller._components().journal.ForwardJournal(out/'model_journal',identity)
        result=caller.process_snapshot(snapshot,model=model,scaler=scaler,journal=journal,
            policy_identity=identity,mode='observe_only',states=None)
        if (result['active'] or result['states'] is not None or result['clock']['status']!='not_frozen'
                or any(result['counts'][k] for k in ('new_state_calls','advance_D_calls','seal_u_calls','new_fit','SQL'))):
            raise ValueError('observer created forbidden forward/financial state')
        artifacts['result']=_write(out/'result.json',result)
        after={k:_stat(v) for k,v in inputs.items()}
        if before!=after or counts!=BUDGET:raise ValueError('source changed or read budget not exact')
        receipt=dict(schema='stage346_incremental_observation_source_receipt_v1',status='completed',inputs=inputs,
            source_before=before,source_after=after,read_counts=counts,economics_hash='inherited_not_rehashed',
            authorization=auth,source338_status_preserved='partial',canonical_coverage=coverage,
            incremental_audit=snapshot['incremental_audit'],artifacts=artifacts,T0=None,
            boundary='One historical u19 operational factor1 observation;no publication/finality/forward/financial qualification.')
        artifacts['source_receipt']=_write(out/'source_receipt.json',receipt)
        terminal.update(status='completed_historical_observation_only',exit_code=0,coverage=coverage,
            counts=result['counts'],incremental_audit=snapshot['incremental_audit'],artifacts=artifacts)
        return terminal
    except Exception as exc:
        terminal.update(status='failed_no_retry',exit_code=1,error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
        raise
    finally:
        terminal.update(elapsed_seconds=time.perf_counter()-start,finished_at=datetime.now(timezone.utc).isoformat())
        _write(out/'terminal.json',terminal)
        print(json.dumps(terminal,ensure_ascii=False,allow_nan=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true')
    p.add_argument('--authorization',required=True);args=p.parse_args()
    if not args.execute:raise SystemExit('explicit --execute required')
    run_once(args.authorization);return 0

if __name__=='__main__':raise SystemExit(main())
