"""Frozen304 lag1 observed-traded-month OI share source only.

Actual requires exact root authorization, one native ten-column SELECT and one
three-column action stream. Persist all selected OI evidence for zero-SQL review.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sqlite3
import time
import zipfile
import numpy as np
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage304_month_pool_oi_share_protocol/protocol.json'
PROTOCOL_SHA='729aa21945cc9dc0f446485dd2671a970cec443f1c32783a083b99ce10ffe6a4'
OUTPUT=LINE/'outputs/stage305_month_pool_oi_source/actual_run1'
BUNDLE=LINE/'outputs/stage305_month_pool_oi_source/implementation/source_bundle.json'
ROWS=1552456
FIELDS=['sequence_index','reference_epoch','u_index']
NATIVE_FIELDS=['contract_epoch_id','exchange','trade_date','close_oi','volume','source_id',
               'volume_factor','oi_factor','quality_status','source_family']
SQL='''SELECT b.contract_epoch_id,b.exchange,b.trade_date,b.close_oi,b.volume,b.source_id,
       b.volume_factor,b.oi_factor,b.quality_status,s.family
       FROM daily_bars b LEFT JOIN sources s ON b.source_id=s.source_id
       WHERE b.trade_date>=? AND b.trade_date<=? ORDER BY b.contract_epoch_id,b.trade_date'''
STATES={0:'missing_exact_lag_bar',1:'available',2:'query_lag_not_in_traded_pool',
        3:'pool_unknown_oi_or_unit',4:'pool_nonpositive_or_nonfinite_total'}
_unit_path=Path(__file__).with_name('stage085_oi_projection.py')
_spec=importlib.util.spec_from_file_location('stage305_accepted085_units',_unit_path)
_units=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_units)
unit_state=_units.unit_state
NATIVE_QUERIES=0


def binding(path,raw=None):
    path=Path(path).resolve();raw=path.read_bytes() if raw is None else raw
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def bound_bytes(ref):
    raw=Path(ref['path']).read_bytes()
    if len(raw)!=ref['bytes'] or hashlib.sha256(raw).hexdigest()!=ref['sha256']:
        raise ValueError('small_binding_changed '+ref['path'])
    return raw


def read_json(path):
    raw=Path(path).read_bytes();return json.loads(raw),binding(path,raw)


def save_json(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def stat_lock(ref,database=False):
    p=Path(ref['path']);s=p.stat()
    state=dict(path=str(p),bytes=s.st_size,inode=s.st_ino,mtime_ns=s.st_mtime_ns)
    if state['bytes']!=ref['bytes']:raise ValueError('accepted_source_size_changed '+str(p))
    if database:
        state.update(wal_present=Path(str(p)+'-wal').exists(),shm_present=Path(str(p)+'-shm').exists())
        if any(state[k]!=ref[k] for k in ('bytes','inode','mtime_ns','wal_present','shm_present')):
            raise ValueError('accepted_database_stat_changed')
    return state


def compile_native(records,dates,contract,expected_rows):
    """Encode every ten-column row; no OI-invalid member is discarded."""
    if not dates or list(dates)!=sorted(set(dates)):raise ValueError('frozen_calendar_order')
    n=int(expected_rows)
    if n<=0:raise ValueError('expected_native_rows')
    calendar={day:k for k,day in enumerate(dates)}
    numeric={k:np.full(n,np.nan,dtype=np.float64) for k in ('close_oi','volume','volume_factor','oi_factor')}
    arrays=dict(day_index=np.empty(n,dtype=np.int32),source_code=np.empty(n,dtype=np.int32),
        quality_code=np.empty(n,dtype=np.uint16),unit_code=np.empty(n,dtype=np.uint16),**numeric)
    epochs=[];offsets=[];sources=[];source_index={};quality=[];quality_index={};units=[];unit_index={}
    last=None;done=0
    for values in records:
        if done>=n:raise ValueError('native_row_count_exceeded')
        if len(values)!=len(NATIVE_FIELDS):raise ValueError('native_ten_column_shape')
        row=dict(zip(NATIVE_FIELDS,values));epoch=row['contract_epoch_id'];day=row['trade_date']
        parts=epoch.split('.') if isinstance(epoch,str) else []
        if (len(parts)!=3 or not all(parts[:2]) or len(parts[2])!=6 or not parts[2].isdigit()
                or not 1<=int(parts[2][4:])<=12 or parts[0]!=row['exchange'] or day not in calendar):
            raise ValueError('native_epoch_or_source_calendar_identity')
        key=(epoch,calendar[day])
        if last is not None and key<=last:raise ValueError('native_duplicate_or_order')
        if last is None or epoch!=last[0]:epochs.append(epoch);offsets.append(done)
        last=key;arrays['day_index'][done]=key[1]
        for name in numeric:
            value=row[name];arrays[name][done]=float(value) if value is not None else np.nan
        sid=row['source_id'] or '';family=row['source_family'] or ''
        if sid not in source_index:
            source_index[sid]=len(sources);sources.append(dict(source_id=sid,source_family=family))
        code=source_index[sid]
        if sources[code]['source_family']!=family:raise ValueError('source_id_family_inconsistent')
        arrays['source_code'][done]=code
        status=row['quality_status'] or ''
        if status not in quality_index:quality_index[status]=len(quality);quality.append(status)
        if quality_index[status]>=65536:raise ValueError('quality_code_overflow')
        arrays['quality_code'][done]=quality_index[status]
        state,rule=unit_state(row,contract);unit=(state,rule)
        if unit not in unit_index:
            unit_index[unit]=len(units);units.append(dict(state=state,rule=rule))
        if unit_index[unit]>=65536:raise ValueError('unit_code_overflow')
        arrays['unit_code'][done]=unit_index[unit];done+=1
    if done!=n:raise ValueError('complete_native_row_count')
    offsets.append(done);arrays.update(epochs=np.asarray(epochs,dtype=str),offsets=np.asarray(offsets,dtype=np.int64))
    codes=dict(sources=sources,quality_states=quality,unit_results=units)
    return arrays,codes


def pool_quantities(native,codes,calendar_size):
    """Only quality/positiveV defines P; unknownOI/units invalidates whole P."""
    n=len(native['day_index']);lengths=np.diff(native['offsets']);epochs=native['epochs'].tolist()
    if lengths.shape!=(len(epochs),) or np.any(lengths<=0) or int(lengths.sum())!=n:
        raise ValueError('native_epoch_offsets')
    product_index={};ep=[]
    for epoch in epochs:
        product=epoch.rsplit('.',1)[0]
        if product not in product_index:product_index[product]=len(product_index)
        ep.append(product_index[product])
    product=np.repeat(np.asarray(ep,dtype=np.int32),lengths)
    quality=codes['quality_states'];accepted=quality.index('accepted') if 'accepted' in quality else -1
    member=(native['quality_code']==accepted)&np.isfinite(native['volume'])&(native['volume']>0)
    positions=np.flatnonzero(member);q=np.full(n,np.nan,dtype=np.float64);state=np.full(n,2,dtype=np.uint8)
    if not len(positions):
        return q,state,dict(pool_member_rows=0,pools=0,invalid_oi_or_unit_pools=0,nonpositive_or_nonfinite_pools=0)
    approved=[i for i,v in enumerate(codes['unit_results']) if v['state']=='accepted_canonical_inherited_stage266']
    oi=native['close_oi'][positions]
    bad=~np.isfinite(oi)|(oi<0)|~np.isin(native['unit_code'][positions],approved)
    keys=product[positions].astype(np.int64)*int(calendar_size)+native['day_index'][positions]
    _,inverse=np.unique(keys,return_inverse=True)
    total=np.bincount(inverse,weights=oi);invalid=np.bincount(inverse,weights=bad.astype(np.int64))>0
    good=(~invalid)&np.isfinite(total)&(total>0)
    row_good=good[inverse];state[positions]=4;state[positions[invalid[inverse]]]=3
    q[positions[row_good]]=oi[row_good]/total[inverse[row_good]];state[positions[row_good]]=1
    if not np.array_equal(np.isfinite(q),state==1) or np.any(q[np.isfinite(q)]<0) or np.any(q[np.isfinite(q)]>1):
        raise ValueError('share_bounds_or_state')
    summary=dict(pool_member_rows=int(len(positions)),pools=int(len(total)),
        invalid_oi_or_unit_pools=int(invalid.sum()),nonpositive_or_nonfinite_pools=int(((~invalid)&~good).sum()),
        observed_product_codes=len(product_index),nonmember_native_rows=int(n-len(positions)))
    return q,state,summary


def align_block(sequence_index,reference_epoch,u_index,native,native_q,native_state,start,calendar_size):
    """Exact epoch/u identity; lag is u_index-1, never previous existing bar."""
    seq=np.asarray(sequence_index);refs=np.asarray(reference_epoch,dtype=object);u=np.asarray(u_index,dtype=np.int64);n=len(seq)
    if not np.array_equal(seq,np.arange(start,start+n,dtype=np.int64)) or refs.shape!=(n,) or u.shape!=(n,):
        raise ValueError('original_action_sequence_alignment')
    if np.any(u<0) or np.any(u>=calendar_size):raise ValueError('action_source_calendar_index')
    lookup={str(epoch):i for i,epoch in enumerate(native['epochs'])}
    q=np.full(n,np.nan,dtype=np.float64);state=np.zeros(n,dtype=np.uint8);lagrow=np.full(n,-1,dtype=np.int64)
    for epoch,positions in pd.DataFrame({'epoch':refs}).groupby('epoch',sort=False).indices.items():
        if epoch not in lookup:raise ValueError('action_epoch_missing_from_native')
        code=lookup[epoch];lo,hi=map(int,native['offsets'][code:code+2]);days=native['day_index'][lo:hi]
        current=u[positions];where=np.searchsorted(days,current)
        if np.any(where>=len(days)) or not np.array_equal(days[where],current):
            raise ValueError('action_u_missing_from_native')
        wanted=current-1;j=np.searchsorted(days,wanted);inside=j<len(days)
        exact=inside.copy();exact[inside]=days[j[inside]]==wanted[inside]
        selected=positions[exact];indices=lo+j[exact]
        lagrow[selected]=indices;q[selected]=native_q[indices];state[selected]=native_state[indices]
    return q,state,lagrow


def expected_inputs(protocol):
    ref=protocol['identity_inputs']['original130_manifest'];old=json.loads(bound_bytes(ref))
    if old.get('schema')!='stage130_contract_choice_fit_v1' or old.get('status')!='completed':
        raise ValueError('accepted130_manifest_schema_status')
    inputs={k:old['input_bindings'][k] for k in ('actions','mothers','common')}
    if inputs['common']!=protocol['identity_inputs']['original_common']:raise ValueError('original_common_binding')
    inputs.update(original130_manifest=ref,**{k:v for k,v in protocol['source']['source_inputs'].items()
        if k in ('database','unit_contract','calendar')})
    return inputs


def write_npz(path,arrays):
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for key,value in arrays.items():
            with archive.open(key+'.npy','w') as member:np.lib.format.write_array(member,value,allow_pickle=False)


def run_actual(auth_path,output):
    protocol,pb=read_json(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA or protocol.get('schema')!='stage304_month_pool_oi_share_protocol_v1':
        raise ValueError('frozen304_protocol_changed')
    inputs=expected_inputs(protocol);bundle,sb=read_json(BUNDLE);auth,ab=read_json(auth_path);out=Path(output).resolve()
    wanted=dict(schema='stage305_root_source_authorization_v1',authorized=True,stage=305,protocol_sha256=PROTOCOL_SHA,
        source_bundle_sha256=sb['sha256'],input_bindings=inputs,output=str(out))
    if auth!=wanted:raise ValueError('root_exact_source_authorization_mismatch')
    if bundle.get('protocol_sha256')!=PROTOCOL_SHA:raise ValueError('source_bundle_protocol')
    for ref in bundle['source_bindings'].values():bound_bytes(ref)
    if bundle['source_bindings']['inherited_unit_implementation']!=protocol['source']['source_inputs']['inherited_unit_implementation']:
        raise ValueError('accepted085_unit_implementation_binding')
    bound_bytes(protocol['source']['nonredundancy_proof'])
    out.mkdir(parents=True,exist_ok=False);began=time.monotonic();status='failed';failure=None;done=0;identity_streams=0
    before={};after={};pool_summary={};counts={};native_reads=0;digest=hashlib.sha256();samples=[]
    save_json(out/'started.json',dict(schema='stage305_source_started_v1',protocol=pb,authorization=ab,source_bundle=sb,inputs=inputs))
    try:
        contract=json.loads(bound_bytes(inputs['unit_contract']))
        raw_dates=np.load(io.BytesIO(bound_bytes(inputs['calendar'])),allow_pickle=False)
        if raw_dates.ndim!=1 or raw_dates.dtype.kind not in ('i','u'):raise ValueError('frozen_calendar_dtype')
        dates=[str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in raw_dates]
        if len(dates)!=5587 or dates!=sorted(set(dates)):raise ValueError('frozen_source_calendar')
        before=dict(database=stat_lock(inputs['database'],True),actions=stat_lock(inputs['actions']))
        global NATIVE_QUERIES
        if NATIVE_QUERIES:raise ValueError('one_native_SELECT_only_no_retry')
        uri=Path(inputs['database']['path']).resolve().as_uri()+'?mode=ro&immutable=1'
        with sqlite3.connect(uri,uri=True) as db:
            NATIVE_QUERIES+=1;native_reads+=1
            cursor=db.execute(SQL,('2010-01-01','2026-10-16'))
            native,codes=compile_native(cursor,dates,contract,ROWS)
        if len(native['epochs'])!=protocol['source']['source_native_epochs']:raise ValueError('accepted9520_native_epochs')
        native_q,native_state,pool_summary=pool_quantities(native,codes,len(dates))
        # Complete source evidence is saved before identity alignment, including failure recovery.
        write_npz(out/'native_oi_evidence.npz',native)
        save_json(out/'native_oi_codes.json',dict(schema='stage305_native_oi_evidence_codes_v1',**codes,
            calendar=inputs['calendar'],source_fields=NATIVE_FIELDS,
            native_row_identity='epochs[offsets] repeated to next offset + exact source calendar day_index',
            exchange='epoch first component; checked equal to selected SQL exchange',
            product='epoch first two components; ordinary/_F separate',
            unit_state_implementation=protocol['source']['source_inputs']['inherited_unit_implementation'],
            source_input_units=inputs['unit_contract'],all_selected_native_rows=ROWS,SQL=SQL,
            query_parameters=['2010-01-01','2026-10-16'],pool_summary=pool_summary))
        q=np.full(ROWS,np.nan,dtype=np.float64);state=np.zeros(ROWS,dtype=np.uint8);identity_streams+=1
        stream=pd.read_csv(inputs['actions']['path'],compression='gzip',usecols=FIELDS,
            dtype={'sequence_index':'int64','reference_epoch':str,'u_index':'int64'},keep_default_na=False,chunksize=100000)
        for frame in stream:
            n=len(frame)
            if done+n>ROWS:raise ValueError('original_action_rows_exceeded')
            seq=frame.sequence_index.to_numpy();refs=frame.reference_epoch.to_numpy();u=frame.u_index.to_numpy()
            values,states,lag=align_block(seq,refs,u,native,native_q,native_state,done,len(dates))
            q[done:done+n]=values;state[done:done+n]=states
            digest.update(frame[FIELDS].to_csv(index=False,header=False,lineterminator='\n').encode())
            for at in sorted({0,n-1}):
                samples.append(dict(sequence_index=int(seq[at]),reference_epoch=str(refs[at]),u_index=int(u[at]),
                    v_index=int(u[at])-1,lag_native_row=int(lag[at]),state_code=int(states[at]),
                    q=float(values[at]) if np.isfinite(values[at]) else None))
            done+=n
        if done!=ROWS:raise ValueError('complete1552456_action_rows')
        available=np.isfinite(q).astype(np.uint8)
        if not np.array_equal(available,state==1):raise ValueError('available_finiteq_state_mismatch')
        after=dict(database=stat_lock(inputs['database'],True),actions=stat_lock(inputs['actions']))
        if before!=after:raise ValueError('input_stat_changed_during_source')
        write_npz(out/'source_vector.npz',dict(sequence_index=np.arange(ROWS,dtype=np.int64),q=q,available=available,state_code=state))
        counts=dict(action_rows=done,available=int(available.sum()),unavailable=int((available==0).sum()),
            legal_zero=int(((q==0)&(available==1)).sum()),legal_one=int(((q==1)&(available==1)).sum()),
            state_counts={STATES[k]:int((state==k).sum()) for k in STATES},native_rows=ROWS,
            native_epochs=len(native['epochs']),inherited_product_domain=98,inherited_mother_rows=399252,pools=pool_summary)
        save_json(out/'source_evidence.json',dict(schema='stage305_source_alignment_evidence_v1',identity_columns=FIELDS,
            identity_csv_rows_sha256=digest.hexdigest(),digest_encoding='UTF8 noheader CSV sequence_index,reference_epoch,u_index newline',
            sequence_index='exact int64 arange1552456',state_codes=STATES,samples=samples,
            mapping='same epoch exact v=u_index-1; never last existing row, carry or future/calendar natural day'))
        save_json(out/'summary.json',dict(schema='stage305_month_pool_oi_source_summary_v1',counts=counts,new_fit=0,new_cash=0))
        status='completed'
    except Exception as exc:failure=dict(type=type(exc).__name__,message=str(exc))
    receipt=dict(schema='stage305_month_pool_oi_source_receipt_v1',status=status,protocol=pb,authorization=ab,source_bundle=sb,
        inputs=inputs,source_stat_before=before,source_stat_after=after,counts=counts,action_rows=done,
        native_source_queries=native_reads,native_source_columns=NATIVE_FIELDS,action_identity_streams=identity_streams,
        action_identity_fields=FIELDS,source_calendar_loads=1,big_input_hashes_recomputed=0,
        mother_reads=0,common_reads=0,OHLC_reads=0,label_reads=0,old_model_reads=0,old_cash_reads=0,
        new_fit=0,new_cash=0,downloads=0,network=0,automatic_retry=False,failure=failure,
        quantity_semantics='canonical single-sided unchanged; no factor reapplied',
        pool='accepted finitepositiveV observed traded months only; not all listed months or net long capital flow',
        strict_first_publication_PIT_established=False,production_qualified=False,
        elapsed_seconds=time.monotonic()-began,completed_at=datetime.now(timezone.utc).isoformat())
    save_json(out/'receipt.json',receipt)
    save_json(out/'terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,
        native_source_queries=native_reads,new_fit=0,new_cash=0,elapsed_seconds=receipt['elapsed_seconds']))
    roles=dict(source_vector='source_vector.npz',native_oi_evidence='native_oi_evidence.npz',native_oi_codes='native_oi_codes.json',
        source_evidence='source_evidence.json',summary='summary.json',receipt='receipt.json',terminal='terminal.json')
    save_json(out/'manifest.json',dict(schema='stage305_month_pool_oi_source_manifest_v1',status=status,
        candidate='LAGGED_MONTH_POOL_OI_SHARE_OFFSET',protocol_sha256=PROTOCOL_SHA,protocol=pb,source_bundle=sb,inputs=inputs,
        arrays=dict(sequence_index='int64 arange1552456',q='float64 unknown NaN',available='uint8 0/1 == finiteq',state_code='uint8 diagnostic'),
        artifacts={role:binding(out/name) for role,name in roles.items() if (out/name).is_file()},new_fit=0,new_cash=0))
    if failure:raise RuntimeError(failure['type']+': '+failure['message'])
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true',required=True)
    parser.add_argument('--authorization',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv);result=run_actual(args.authorization,args.output)
    print(json.dumps(dict(status=result['status'],counts=result['counts']),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
