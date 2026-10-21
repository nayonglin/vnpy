"""Frozen294 source q only: vectorized same-epoch histories, no fit or cash.

Reuse the accepted132 valid flag and global-calendar day indices unchanged.
Read five native members once and one three-column129 identity stream only.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import time
import zipfile
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

LINE=Path(__file__).resolve().parents[1]
PROTOCOL=LINE/'outputs/stage294_reopening_contribution_protocol/protocol.json'
PROTOCOL_SHA='82a4e3f88c4c17c6319e298a2ad6c37ac1070f62fff6cd9eb5d25be857251016'
OUTPUT=LINE/'outputs/stage295_reopening_contribution_source/actual_run1'
BUNDLE=LINE/'outputs/stage295_reopening_contribution_source/implementation/source_bundle.json'
FIELDS=['sequence_index','reference_epoch','u_index']
MEMBERS=['epochs','offsets','days','values','valid']
ROWS=1552456
STATES={0:'insufficient_same_epoch_21',1:'available',2:'source_calendar_gap_rewarm',3:'invalid_inherited_valid_history',
    4:'zero_or_nonfinite_rolling_TR_ATR',5:'nonfinite_own11_or_q'}


def binding(path,raw=None):
    path=Path(path).resolve();raw=path.read_bytes() if raw is None else raw
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read_json(path):
    raw=Path(path).read_bytes();return json.loads(raw),binding(path,raw)


def bound_json(ref):
    value,got=read_json(ref['path'])
    if any(got[k]!=ref[k] for k in ('bytes','sha256')):raise ValueError('small_binding_changed '+ref['path'])
    return value,got


def save_json(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def stat_lock(ref):
    s=Path(ref['path']).stat()
    if s.st_size!=ref['bytes']:raise ValueError('accepted_source_size_changed '+ref['path'])
    return dict(path=ref['path'],bytes=s.st_size,inode=s.st_ino,mtime_ns=s.st_mtime_ns)


def epoch_quantity(days,values,valid):
    """Cumulative error is avoided: each rolling sum is a 20-wide local sum."""
    days=np.asarray(days);v=np.asarray(values,dtype=np.float64);valid=np.asarray(valid,dtype=bool);n=len(days)
    if v.shape!=(n,5) or valid.shape!=(n,) or np.any(np.diff(days)<=0):raise ValueError('accepted_epoch_array_shape_or_order')
    q=np.full(n,np.nan,dtype=np.float64);state=np.zeros(n,dtype=np.uint8)
    if n<21:return q,state
    with np.errstate(all='ignore'):
        tr=np.maximum.reduce([v[1:,1]-v[1:,2],np.abs(v[1:,1]-v[:-1,3]),np.abs(v[1:,2]-v[:-1,3])])
        tw=sliding_window_view(tr,20);atr=tw.sum(axis=1,dtype=np.float64)/20.
        gaps=v[1:,0]-v[:-1,3]
        amount=sliding_window_view(gaps,20).sum(axis=1,dtype=np.float64)
        candidate=amount/(math.sqrt(20)*atr)
        contiguous=days[20:]-days[:-20]==20
        history=sliding_window_view(valid,21).all(axis=1)
        base=contiguous&history;atr_ok=np.isfinite(atr)&(atr>0)
        # Match129 own11 readiness rather than replacing accepted132.valid.
        u=v[20:];previous=v[19:-1];width=u[:,1]-u[:,2]
        checks=[(u[:,3]-previous[:,3])/atr,(u[:,3]-v[15:-5,3])/(math.sqrt(5)*atr),
            (u[:,3]-v[:-20,3])/(math.sqrt(20)*atr),(u[:,3]-u[:,0])/atr,width/atr,
            np.where(width>0,(u[:,3]-u[:,2])/width,.5),(u[:,0]-previous[:,3])/atr,
            (tw[:,-5:].sum(axis=1,dtype=np.float64)/5.)/atr,
            np.log(u[:,4]/(sliding_window_view(v[:-1,4],20).sum(axis=1,dtype=np.float64)/20.)),
            (u[:,3]-sliding_window_view(v[:-1,1],20).max(axis=1))/atr,atr/u[:,3],candidate]
        finite=np.logical_and.reduce([np.isfinite(a) for a in checks]);good=base&atr_ok&finite
    tail=state[20:];tail[:]=2;tail[~history]=3;tail[base&~atr_ok]=4;tail[base&atr_ok&~finite]=5;tail[good]=1
    result=q[20:];result[good]=candidate[good]
    return q,state


def align_block(sequence_index,reference_epoch,u_index,cache_index,native_days,native_q,native_state,start):
    seq=np.asarray(sequence_index);refs=np.asarray(reference_epoch,dtype=object);u=np.asarray(u_index,dtype=np.int64);n=len(seq)
    if not np.array_equal(seq,np.arange(start,start+n,dtype=np.int64)):raise ValueError('original_sequence_alignment')
    native=np.empty(n,dtype=np.int64)
    for epoch,positions in pd.DataFrame({'epoch':refs}).groupby('epoch',sort=False).indices.items():
        if epoch not in cache_index:raise ValueError('action_epoch_missing_from_accepted_cache')
        lo,hi=cache_index[epoch];days=native_days[lo:hi];wanted=u[positions];j=np.searchsorted(days,wanted)
        if np.any(j>=len(days)) or not np.array_equal(days[j],wanted):raise ValueError('action_u_missing_from_accepted_cache')
        native[positions]=lo+j
    return native_q[native],native_state[native],native


def expected_inputs(protocol):
    refs,rb=bound_json(protocol['identity_inputs']['cash_refs']);old=refs['input_bindings_inherited_from_accepted157']
    inputs={k:old[k] for k in ('actions','mothers','native_cache','native_cache_manifest')}
    inputs['common']=protocol['identity_inputs']['original_common']
    return inputs,rb


def write_npz(path,arrays):
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
        for key,value in arrays.items():
            with archive.open(key+'.npy','w') as member:np.lib.format.write_array(member,value,allow_pickle=False)


def run_actual(auth_path):
    protocol,pb=read_json(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA or protocol['schema']!='stage294_frozen_common52_reopening_contribution_protocol_v1':raise ValueError('frozen294_changed')
    inputs,refs_binding=expected_inputs(protocol);bundle,sb=read_json(BUNDLE);auth,ab=read_json(auth_path)
    expected=dict(schema='stage295_root_source_authorization_v1',authorized=True,stage=295,protocol_sha256=PROTOCOL_SHA,
        source_bundle_sha256=sb['sha256'],input_bindings=inputs,output=str(OUTPUT))
    if auth!=expected:raise ValueError('root_exact_source_authorization_mismatch')
    for ref in bundle['source_bindings'].values():
        if binding(ref['path'])!=ref:raise ValueError('frozen_small_source_changed')
    OUTPUT.mkdir(parents=True,exist_ok=False);began=time.monotonic();status='failed';failure=None;done=0;opened=0;identity_streams=0
    before={};after={};cache_meta={};counts={};evidence=[];digest=hashlib.sha256();member_reads={k:0 for k in MEMBERS}
    save_json(OUTPUT/'started.json',dict(schema='stage295_source_started_v1',protocol=pb,authorization=ab,source_bundle=sb,inputs=inputs))
    try:
        cache_meta,_=bound_json(inputs['native_cache_manifest'])
        if (cache_meta['schema']!='stage132_native_store_recovery_cache_v1' or cache_meta['file']!=inputs['native_cache']
                or cache_meta['native_rows']!=ROWS or cache_meta['native_epochs']!=9520):raise ValueError('accepted132_cache_metadata_mismatch')
        before={k:stat_lock(inputs[k]) for k in ('actions','native_cache')}
        with np.load(inputs['native_cache']['path'],allow_pickle=False) as z:
            opened=1
            flat={}
            for key in MEMBERS:flat[key]=z[key];member_reads[key]+=1
        epochs=flat['epochs'].tolist();offsets=flat['offsets'];days=flat['days'];values=flat['values'];valid=flat['valid']
        if (len(epochs)!=9520 or len(set(epochs))!=len(epochs) or offsets.shape!=(len(epochs)+1,)
                or offsets[0]!=0 or offsets[-1]!=ROWS or values.shape!=(ROWS,5) or days.shape!=(ROWS,) or valid.shape!=(ROWS,)):
            raise ValueError('accepted132_native_member_shape')
        native_q=np.full(ROWS,np.nan);native_state=np.zeros(ROWS,dtype=np.uint8);index={}
        for i,epoch in enumerate(epochs):
            lo,hi=int(offsets[i]),int(offsets[i+1])
            if not 0<=lo<=hi<=ROWS:raise ValueError('accepted_epoch_offsets')
            index[epoch]=(lo,hi)
            native_q[lo:hi],native_state[lo:hi]=epoch_quantity(days[lo:hi],values[lo:hi],valid[lo:hi])
        q=np.full(ROWS,np.nan);state=np.zeros(ROWS,dtype=np.uint8)
        identity_streams+=1
        stream=pd.read_csv(inputs['actions']['path'],compression='gzip',usecols=FIELDS,
            dtype={'sequence_index':'int64','reference_epoch':str,'u_index':'int64'},keep_default_na=False,chunksize=100000)
        for frame in stream:
            seq=frame.sequence_index.to_numpy();refs=frame.reference_epoch.to_numpy();u=frame.u_index.to_numpy()
            got,states,native=align_block(seq,refs,u,index,days,native_q,native_state,done)
            n=len(frame)
            if done+n>ROWS:raise ValueError('original_action_count_exceeded')
            q[done:done+n]=got;state[done:done+n]=states
            digest.update(frame[FIELDS].to_csv(index=False,header=False,lineterminator='\n').encode())
            for at in sorted({0,n-1}):
                native_row=int(native[at]);lo,_=index[refs[at]];j=native_row-lo
                item=dict(sequence_index=int(seq[at]),reference_epoch=str(refs[at]),u_index=int(u[at]),native_row=native_row,
                    history_start_native_row=native_row-20 if j>=20 else None,state_code=int(states[at]),q=float(got[at]) if np.isfinite(got[at]) else None)
                if np.isfinite(got[at]):
                    w=values[native_row-20:native_row+1]
                    tr=[max(b[1]-b[2],abs(b[1]-a[3]),abs(b[2]-a[3])) for a,b in zip(w,w[1:])]
                    atr=math.fsum(tr)/20.;reference=math.fsum(b[0]-a[3] for a,b in zip(w,w[1:]))/(math.sqrt(20)*atr)
                    item.update(reference_q=reference,rolling20_TR_ATR=atr,abs_error=abs(reference-float(got[at])))
                    if not math.isclose(reference,float(got[at]),rel_tol=1e-10,abs_tol=1e-10):raise ValueError('vector_vs_fsum_tolerance')
                evidence.append(item)
            done+=n
        if done!=ROWS:raise ValueError('complete129_action_count')
        available=np.isfinite(q).astype(np.uint8)
        if not np.array_equal(available,state==1):raise ValueError('source_availability_state_mismatch')
        after={k:stat_lock(inputs[k]) for k in ('actions','native_cache')}
        if before!=after:raise ValueError('source_stat_lock_changed')
        write_npz(OUTPUT/'source_vector.npz',dict(sequence_index=np.arange(ROWS,dtype=np.int64),q=q,available=available,state_code=state))
        counts=dict(action_rows=done,available=int(available.sum()),unavailable=int((available==0).sum()),legal_zero=int(((q==0)&(available==1)).sum()),
            state_counts={STATES[k]:int((state==k).sum()) for k in STATES},native_epochs=len(epochs),native_rows=len(days),
            inherited_original_mother_rows=399252,inherited_product_domain=98)
        save_json(OUTPUT/'source_evidence.json',dict(identity_columns=FIELDS,identity_csv_rows_sha256=digest.hexdigest(),
            digest_encoding='UTF8 canonical CSV noheader sequence_index,reference_epoch,u_index each row newline',samples=evidence,
            sequence_index='exact int64 arange1552456',clock='complete source u close; never D',state_codes=STATES))
        save_json(OUTPUT/'summary.json',dict(schema='stage295_reopening_source_summary_v1',counts=counts,new_fit=0,new_cash=0))
        status='completed'
    except Exception as exc:failure=dict(type=type(exc).__name__,message=str(exc))
    receipt=dict(schema='stage295_reopening_contribution_source_receipt_v1',status=status,protocol=pb,authorization=ab,source_bundle=sb,
        inputs=inputs,interface_refs=refs_binding,cache_metadata=cache_meta,source_stat_before=before,source_stat_after=after,
        inherited132_valid='persisted valid member unchanged, includes accepted quality, finite positive OHLCV and OHLC consistency; not recomputed',
        days_semantics='accepted132 frozen global source calendar indices; searchsorted exact epoch/u;21-day endpoint difference20',
        source_cache_opens=opened,source_cache_member_reads=member_reads,action_identity_streams=identity_streams,action_identity_fields=FIELDS,
        action_rows=done,counts=counts,big_input_hashes_recomputed=0,mother_reads=0,common_reads=0,DB_stat_or_hash=0,
        SQL=0,native_source_queries=0,network=0,downloads=0,labels=0,old_model_reads=0,old_cash_reads=0,new_fit=0,new_cash=0,
        cumulative_fit=441,cumulative_cash=238,failure=failure,automatic_retry=False,clock='u daily source close only;not 9am/overnight/minute claim',
        elapsed_seconds=time.monotonic()-began,completed_at=datetime.now(timezone.utc).isoformat())
    save_json(OUTPUT/'receipt.json',receipt)
    save_json(OUTPUT/'terminal.json',dict(status=status,exit_code=0 if status=='completed' else 1,new_fit=0,new_cash=0,elapsed_seconds=receipt['elapsed_seconds']))
    roles={k:k+v for k,v in [('source_vector','.npz'),('source_evidence','.json'),('summary','.json'),('receipt','.json'),('terminal','.json')]}
    save_json(OUTPUT/'manifest.json',dict(schema='stage295_reopening_contribution_source_manifest_v1',status=status,
        candidate='REOPENING_GAP20_OFFSET',protocol_sha256=PROTOCOL_SHA,protocol=pb,source_bundle=sb,inputs=inputs,
        arrays=dict(sequence_index='int64 [1552456] exact arange',q='float64 [1552456] unknown NaN',available='uint8 [1552456] 0/1 == finiteq',state_code='uint8 [1552456] diagnostic'),
        artifacts={k:binding(OUTPUT/v) for k,v in roles.items() if (OUTPUT/v).is_file()},new_fit=0,new_cash=0))
    if failure:raise RuntimeError(failure['type']+': '+failure['message'])
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true',required=True)
    parser.add_argument('--authorization',required=True);args=parser.parse_args(argv)
    result=run_actual(args.authorization);print(json.dumps(dict(status=result['status'],counts=result['counts']),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
