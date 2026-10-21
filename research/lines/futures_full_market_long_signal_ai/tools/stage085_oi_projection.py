"""Frozen084 same-real-epoch lagged canonical close-OI projection only.

Pure fixture builder; actual entry is separately exact-root authorized, one
readonly SELECT, fresh output, no automatic retry. Never reads open_oi, prices,
labels/outcomes, H5 or network; never modifies source data or canonical units.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import sys
import time
import numpy as np
import pandas as pd


TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='82059f728efb70fedd54e2254f822898b6bbcf1b2ac3395cbd1c11470167cba5'
CLARIFICATIONS=LINE/'outputs/stage084_oi_information_protocol/implementation_clarifications.json'
CLARIFICATIONS_SHA='b72cfec8e934a9e347359f1a6f3bbb1384de2a6303c0b6b0bf5089bdab23b776'
NATIVE_QUERIES=0
IDENTITY=['sequence_index','event_id','product_id','family_id','exchange','u_date','u_index','reference_epoch']
NATIVE_FIELDS=['contract_epoch_id','exchange','trade_date','close_oi','volume','source_id','volume_factor','oi_factor',
               'quality_status','native_volume','native_close_oi','source_locator','source_family']
SQL='''SELECT b.contract_epoch_id,b.exchange,b.trade_date,b.close_oi,b.volume,b.source_id,b.volume_factor,b.oi_factor,
       b.quality_status,b.native_volume,b.native_close_oi,b.source_locator,s.family
       FROM daily_bars b LEFT JOIN sources s ON b.source_id=s.source_id
       WHERE b.trade_date>=? AND b.trade_date<=? ORDER BY b.contract_epoch_id,b.trade_date'''


def finite(value):
    return isinstance(value,(int,float,np.number)) and math.isfinite(float(value))


def unit_state(row,contract):
    """Consume accepted canonical values; factor checks never transform them."""
    source=row.get('source_id') or '';family=row.get('source_family') or ''
    vf,of=row.get('volume_factor'),row.get('oi_factor')
    if (contract.get('canonical_quantity_unit')!='single_sided_contracts' or not contract.get('cleaner_rule_approved')
        or not finite(vf) or not finite(of)):
        return 'unknown_or_inconsistent_unit','unit_contract_or_factor_unknown'
    expected=None;rule_id='source_family_or_identity_unknown'
    if family=='rqalpha' and source=='rqalpha':
        rules=[rule for rule in contract['rqalpha']['rules'] if row.get('exchange') in rule['exchanges']
               and rule['start']<=row['trade_date']<=rule['end']]
        if len(rules)==1:
            rule=rules[0];expected=(rule['volume_factor'],rule['close_oi_factor'])
            rule_id=f"rqalpha_{rule['start']}_{rule['end']}_{row['exchange']}"
    elif family in ('old_tq','recent_tq') and source.startswith(family+':'):
        rule=contract[family];expected=(rule['volume_factor'],rule['close_oi_factor'])
        rule_id=family+'_inherited_pinned_stage266'
    elif family=='official' and source.startswith('official:'):
        # Accepted Stage266 rows already passed its official-regime proof.
        # There is no raw unit_regime column here; never invent one or infer it
        # from year. Preserve the accepted factor, without applying it again.
        allowed=set(contract['official']['accepted_regime_factors'].values())
        if vf==of and vf in allowed:
            expected=(vf,of);rule_id='official_inherited_stage266_accepted_factor'
    if expected is None or (vf,of)!=expected:
        return 'unknown_or_inconsistent_unit',rule_id
    return 'accepted_canonical_inherited_stage266',rule_id


def build_projection(panel,records,dates,contract):
    """Full mother, exact v=u-1/w=u-2 in current epoch; missing is never zero."""
    if list(dates)!=sorted(set(dates)):raise ValueError('source calendar must be unique ordered')
    if panel.event_id.duplicated().any() or panel.duplicated(['product_id','u_date']).any():
        raise ValueError('duplicate mother identity')
    calendar={day:k for k,day in enumerate(dates)}
    u=panel.u_date.map(calendar)
    if u.isna().any() or not np.array_equal(u.to_numpy(),panel.u_index.to_numpy()):
        raise ValueError('mother u_index differs from frozen source calendar')
    if isinstance(records,dict):lookup=records
    else:
        lookup={}
        for row in records:
            key=(row['contract_epoch_id'],row['trade_date'])
            if key in lookup:raise ValueError('duplicate native epoch/day')
            lookup[key]=row
    units={key:unit_state(row,contract) for key,row in lookup.items()}
    n=len(panel)
    numeric=['v_index','w_index','v_close_oi','w_close_oi','v_volume','w_volume','v_volume_factor','w_volume_factor',
             'v_oi_factor','w_oi_factor','v_native_volume','w_native_volume','v_native_close_oi','w_native_close_oi','oi_scalar_raw']
    objects=['v_date','w_date','v_source_id','w_source_id','v_source_family','w_source_family','v_unit_state','w_unit_state',
             'v_unit_rule_id','w_unit_rule_id','v_quality_status','w_quality_status','v_source_locator','w_source_locator',
             'projection_state','missing_reason']
    a={name:np.full(n,np.nan,dtype=float) for name in numeric}
    a.update({name:np.full(n,'',dtype=object) for name in objects})
    a.update(oi_observed=np.zeros(n,dtype=np.int8),oi_missing=np.ones(n,dtype=np.int8))
    for i,row in enumerate(panel.itertuples(index=False)):
        epoch=row.reference_epoch if isinstance(row.reference_epoch,str) else ''
        k=int(row.u_index);reasons=[];lags={}
        if not epoch:reasons.append('no_reference_epoch')
        if k<2:reasons.append('missing_lag_source_day')
        for lag,index in [('v',k-1),('w',k-2)]:
            a[lag+'_index'][i]=index
            if index<0:continue
            day=dates[index];a[lag+'_date'][i]=day
            raw=lookup.get((epoch,day)) if epoch else None
            if raw is None:
                reasons.append('missing_'+lag+'_bar');continue
            lags[lag]=raw
            for field in ('close_oi','volume','volume_factor','oi_factor','native_volume','native_close_oi'):
                value=raw.get(field)
                a[lag+'_'+field][i]=float(value) if finite(value) else np.nan
            for field in ('source_id','source_family','quality_status','source_locator'):
                a[lag+'_'+field][i]=raw.get(field) or ''
            state,rule=units[(epoch,day)]
            a[lag+'_unit_state'][i]=state;a[lag+'_unit_rule_id'][i]=rule
            if raw.get('quality_status')!='accepted':reasons.append('unaccepted_'+lag+'_bar')
            if state!='accepted_canonical_inherited_stage266':reasons.append('unaccepted_'+lag+'_unit')
            if not finite(raw.get('close_oi')) or raw['close_oi']<0:reasons.append('invalid_'+lag+'_close_oi')
            if lag=='v' and (not finite(raw.get('volume')) or raw['volume']<=0):reasons.append('invalid_v_volume')
        if len(lags)==2 and lags['v'].get('source_id')!=lags['w'].get('source_id'):
            reasons.append('different_source_id')
        if not reasons:
            scalar=(lags['v']['close_oi']-lags['w']['close_oi'])/lags['v']['volume']
            if finite(scalar):
                a['oi_scalar_raw'][i]=scalar;a['oi_observed'][i]=1;a['oi_missing'][i]=0
            else:reasons.append('nonfinite_ratio')
        a['missing_reason'][i]='|'.join(dict.fromkeys(reasons))
        a['projection_state'][i]='observed_same_epoch_same_source_canonical' if not reasons else 'missing'
    result=pd.concat([panel[IDENTITY].reset_index(drop=True),pd.DataFrame(a)],axis=1)
    result['v_index']=result.v_index.astype(np.int64);result['w_index']=result.w_index.astype(np.int64)
    if result.event_id.tolist()!=panel.event_id.tolist():raise AssertionError('mother rows/order changed')
    if not np.array_equal(result.oi_observed.to_numpy(),1-result.oi_missing.to_numpy()):raise AssertionError('mask disagrees')
    return result


def file_binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read_bound(binding):
    raw=Path(binding['path']).read_bytes()
    if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:
        raise ValueError('bound source file changed '+binding['path'])
    return raw


def safe(value):
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    if isinstance(value,np.integer):return int(value)
    if isinstance(value,np.bool_):return bool(value)
    if isinstance(value,(float,np.floating)):return float(value) if math.isfinite(value) else None
    return value


def write_json(path,value):
    with Path(path).open('x') as stream:json.dump(safe(value),stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')


def db_state(path):
    p=Path(path).resolve();s=p.stat()
    return dict(path=str(p),bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino,
                wal_present=Path(str(p)+'-wal').exists(),shm_present=Path(str(p)+'-shm').exists())


def assert_database(binding):
    actual=db_state(binding['path'])
    if any(actual[k]!=binding[k] for k in ('path','bytes','mtime_ns','inode','wal_present','shm_present')):
        raise ValueError('accepted database stat binding changed')
    return actual


def source_bundle():
    return [file_binding(TOOLS/name) for name in ('stage085_oi_projection.py','test_stage085_oi_projection.py')]


def authorize(args):
    output=Path(args.output).resolve()
    if output.exists():raise FileExistsError('fresh output required; no overwrite or automatic retry')
    protocol_binding=file_binding(args.protocol)
    if protocol_binding['sha256']!=PROTOCOL_SHA or args.protocol_sha256!=PROTOCOL_SHA:raise ValueError('exact084 protocol SHA required')
    protocol=json.loads(read_bound(protocol_binding))
    if protocol.get('schema')!='stage084_oi_information_protocol_v1':raise ValueError('wrong084 protocol')
    clarification_binding=file_binding(CLARIFICATIONS)
    if clarification_binding['sha256']!=CLARIFICATIONS_SHA:raise ValueError('084 clarification changed')
    auth=json.loads(Path(args.authorization).read_bytes())
    required=dict(schema='stage084_exact_root_authorization_v1',authorized_by='root',stage='source',exact_source_authorized=True,
                  protocol_sha256=PROTOCOL_SHA,clarifications_sha256=CLARIFICATIONS_SHA,output=str(output))
    if any(auth.get(k)!=v for k,v in required.items()):raise ValueError('exact root source/protocol/clarifications/output authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=sorted(source_bundle(),key=lambda b:b['path']):
        raise ValueError('root exact source/test binding changed')
    read_bound(protocol['plan'])
    return protocol,protocol_binding,clarification_binding,file_binding(args.authorization)


def load_native_once(database,dates,panel,begin,end):
    global NATIVE_QUERIES
    if NATIVE_QUERIES:raise ValueError('one native SELECT only; no retry')
    before=assert_database(database);needed=set();lookup={day:k for k,day in enumerate(dates)}
    for row in panel.itertuples(index=False):
        if not isinstance(row.reference_epoch,str) or not row.reference_epoch:continue
        u=lookup[row.u_date]
        needed.update((row.reference_epoch,dates[k]) for k in (u-1,u-2) if k>=0)
    records={};scanned=0
    uri=Path(database['path']).resolve().as_uri()+'?mode=ro&immutable=1'
    with sqlite3.connect(uri,uri=True) as db:
        NATIVE_QUERIES+=1
        for values in db.execute(SQL,(begin,end)):
            scanned+=1;key=(values[0],values[2])
            if key not in needed:continue
            if key in records:raise ValueError('duplicate requested native epoch/day')
            records[key]=dict(zip(NATIVE_FIELDS,values))
    after=assert_database(database)
    receipt=dict(native_source_queries=1,native_rows_scanned=scanned,requested_same_epoch_lag_keys=len(needed),
                 retained_native_rows=len(records),missing_requested_keys=len(needed)-len(records),query=SQL,query_parameters=[begin,end],
                 database_before=before,database_after=after,database_sha256_inherited=database['sha256'],database_rehashed=False,
                 open_oi_read=False,prices_read=False,whole_source_copy=False,canonical_values_reconverted=False)
    return records,receipt


def execute(args):
    protocol,protocol_binding,clarification_binding,auth_binding=authorize(args)
    market=json.loads(read_bound(protocol['market_protocol']))
    if any(market['database'][k]!=protocol['database'][k] for k in ('path','bytes','sha256','mtime_ns','inode')):
        raise ValueError('084/052 database identities differ')
    raw_dates=np.load(io.BytesIO(read_bound(market['calendar'])),allow_pickle=False)
    dates=[str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in raw_dates]
    if len(dates)!=5587 or dates!=sorted(set(dates)):raise ValueError('frozen source calendar differs')
    narrow=json.loads(read_bound(protocol['input_roles']['narrow_manifest']))
    labels_binding=protocol['input_roles']['narrow_labels']
    if narrow.get('status')!='completed' or narrow.get('mother_rows')!=399252 or narrow.get('labels_narrow')!=labels_binding:
        raise ValueError('accepted full-mother070 binding differs')
    panel=pd.read_csv(io.BytesIO(read_bound(labels_binding)),compression='gzip',usecols=IDENTITY,keep_default_na=False)
    if (len(panel)!=399252 or panel.product_id.nunique()!=98 or panel.exchange.nunique()!=6
        or not np.array_equal(panel.sequence_index.to_numpy(),np.arange(399252))):raise ValueError('complete399252 mother required')
    contract=json.loads(read_bound(protocol['unit_contract']))
    if NATIVE_QUERIES:raise ValueError('process already consumed native source')
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    started=datetime.now(timezone.utc).isoformat();clock=time.monotonic();sources=source_bundle()
    status,error,rows='failed',None,0
    write_json(out/'actual_started.json',dict(status='started',started_at=started,protocol=protocol_binding,
               implementation_clarifications=clarification_binding,authorization=auth_binding,source_bundle=sources,fixture=False))
    try:
        records,receipt=load_native_once(protocol['database'],dates,panel,market['scope']['start'],market['scope']['end'])
        write_json(out/'source_read_receipt.json',receipt)
        projection=build_projection(panel,records,dates,contract)
        projection.to_csv(out/'oi_projection.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        coverage=projection.assign(year=projection.u_date.str[:4]).groupby(['exchange','year','projection_state','missing_reason'],dropna=False).size().rename('rows').reset_index()
        coverage.to_csv(out/'coverage.csv.gz',index=False,compression={'method':'gzip','mtime':0})
        cases=[]
        selectors=[('observed',projection.oi_observed.eq(1)),('valid_zero',projection.oi_observed.eq(1)&projection.oi_scalar_raw.eq(0)),
                   ('canonical_factor_transition',projection.oi_observed.eq(1)&projection.v_oi_factor.ne(projection.w_oi_factor))]
        selectors.extend((reason,projection.missing_reason.str.contains(reason,regex=False)) for reason in
                         ('no_reference_epoch','missing_v_bar','missing_w_bar','different_source_id','unaccepted_v_unit','unaccepted_w_unit','invalid_v_volume'))
        for kind,mask in selectors:
            matches=projection.loc[mask]
            if len(matches):
                row=matches.iloc[0]
                lags=[records.get((row.reference_epoch,row[lag+'_date'])) for lag in ('w','v')]
                cases.append(dict(kind=kind,projection=row.to_dict(),lag_native_rows=lags))
        write_json(out/'finite_source_cases.json',dict(schema='stage085_finite_first_oi_source_cases_v1',cases=cases,
                   selection='first per predeclared source state; no outcome/PnL access',additional_native_queries=0))
        write_json(out/'projection_summary.json',dict(mother_rows=len(projection),observed=int(projection.oi_observed.sum()),
                   missing=int(projection.oi_missing.sum()),valid_zero=int((projection.oi_observed.eq(1)&projection.oi_scalar_raw.eq(0)).sum()),
                   missing_reasons=dict(Counter(projection.loc[projection.oi_missing.eq(1),'missing_reason'])),
                   formula=protocol['source']['formula'],canonical_units_inherited_not_reconverted=True,
                   missing_not_trade_gate=True,strict_first_release_PIT=False,goal_complete=False))
        assert_database(protocol['database'])
        if source_bundle()!=sources:raise ValueError('source changed during projection')
        rows=len(projection);status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        write_json(out/'actual_terminal.json',dict(status=status,started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),
                   elapsed_seconds=time.monotonic()-clock,exit_code=0 if status=='completed' else 1,error=error,fixture=False,python=sys.executable,
                   completed_projection_rows=rows,native_source_queries=NATIVE_QUERIES,actual_model_fit_calls=0,new_cash_accounts=0,
                   new_labels=0,downloads=0,whole_database_hashes=0))
    projection_binding=file_binding(out/'oi_projection.csv.gz')
    write_json(out/'manifest.json',dict(schema='stage085_oi_projection_v1',status=status,mode='actual',protocol=protocol_binding,
               implementation_clarifications=clarification_binding,authorization=auth_binding,source_bundle=sources,
               input_bindings=dict(narrow_labels=labels_binding,narrow_manifest=protocol['input_roles']['narrow_manifest'],
                                   market_protocol=protocol['market_protocol'],calendar=market['calendar'],unit_contract=protocol['unit_contract'],
                                   database_stat_with_inherited_SHA=protocol['database']),
               projection=projection_binding,terminal=file_binding(out/'actual_terminal.json'),source_read_receipt=file_binding(out/'source_read_receipt.json'),
               artifacts={p.name:file_binding(p) for p in sorted(out.iterdir()) if p.is_file()},mother_rows=rows,native_source_queries=NATIVE_QUERIES,
               actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,goal_complete=False,production_qualified=False))
    return dict(status=status,output=str(out),mother_rows=rows,native_source_queries=NATIVE_QUERIES)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','output'):parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
