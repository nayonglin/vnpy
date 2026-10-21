"""Frozen092 pure-X event_id alignment. No tensor or DAY target is consumed.

Actual preparation requires exact root source/protocol/input/fresh-output binding.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage092_crossday_order_bag_protocol/protocol.json'
PROTOCOL_SHA='580c59d77964b27372570b2d48e197ce7a75f5edd77dac0a9aa5e42548d3a736'
STAGE_ROOT=LINE/'outputs/stage093_sequence_alignment'
_spec=importlib.util.spec_from_file_location('stage093_accepted071',TOOLS/'stage071_settlement_narrow_fit.py')
legacy=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(legacy)
IDENTITY=legacy.IDENTITY
file_binding=legacy.file_binding
read_bound=legacy.read_bound
same_binding=legacy.same_binding
write_json=legacy.write_json
write_csv=legacy.write_csv


def source_bundle():
    names=('stage093_sequence_alignment.py','test_stage093_sequence_alignment.py','stage071_settlement_narrow_fit.py')
    return sorted([file_binding(TOOLS/n) for n in names],key=lambda b:b['path'])


def _integers(frame,columns):
    frame=frame.copy()
    for col in columns:
        values=pd.to_numeric(frame[col],errors='raise').to_numpy(float)
        if not np.isfinite(values).all() or not np.equal(values,np.floor(values)).all():raise ValueError('noninteger '+col)
        frame[col]=values.astype(np.int64)
    return frame


def validate_alignment(mother,alignment,tensor_rows):
    legacy._identity(mother,alignment)
    if mother.event_id.duplicated().any() or mother.duplicated(['product_id','u_date']).any():raise ValueError('duplicate mother')
    if not np.array_equal(mother.sequence_index,np.arange(len(mother))):raise ValueError('full mother sequence differs')
    a=_integers(alignment,['sequence_index','u_index','legacy_tensor_index','sequence_missing'])
    idx=a.legacy_tensor_index.to_numpy(int);missing=a.sequence_missing.to_numpy(int)
    if (not np.isin(missing,[0,1]).all() or not np.array_equal(missing,idx<0)
            or (idx < -1).any() or (idx>=tensor_rows).any()):raise ValueError('alignment index/missing differs')
    if not np.array_equal(np.sort(idx[idx>=0]),np.arange(tensor_rows)):
        raise ValueError('legacy tensor rows not one-to-one covered')
    return a


def align_by_event_id(mother,legacy_event_ids):
    f=_integers(mother[IDENTITY],['sequence_index','u_index'])
    ids=list(legacy_event_ids)
    if any(not isinstance(v,str) or not v for v in ids) or len(set(ids))!=len(ids):raise ValueError('duplicate/invalid legacy event_id')
    if not set(ids).issubset(set(f.event_id)):raise ValueError('legacy event outside current mother')
    lookup={event:i for i,event in enumerate(ids)}
    f['legacy_tensor_index']=f.event_id.map(lookup).fillna(-1).astype(np.int64)
    f['sequence_missing']=f.legacy_tensor_index.lt(0).astype(np.int8)
    return validate_alignment(mother,f,len(ids))


def authorize(args):
    out=Path(args.output).resolve()
    if STAGE_ROOT.resolve() not in out.parents:raise ValueError('output outside Stage093 root')
    if out.exists():raise FileExistsError('fresh output required; no automatic retry')
    if args.protocol_sha256!=PROTOCOL_SHA or file_binding(PROTOCOL)['sha256']!=PROTOCOL_SHA:
        raise ValueError('exact frozen092 protocol required')
    protocol=json.loads(PROTOCOL.read_bytes());binding=file_binding(args.authorization)
    if binding['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=json.loads(read_bound(binding))
    required=dict(schema='stage092_exact_root_authorization_v1',authorized_by='root',stage='prepare',
        exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if any(auth.get(k)!=v for k,v in required.items()):raise ValueError('exact root prepare authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():raise ValueError('exact prepare source binding differs')
    inputs=auth.get('input_bindings',{})
    if set(inputs)!={'narrow_labels','old_event_ids'}:raise ValueError('prepare input roles differ')
    if not same_binding(inputs['narrow_labels'],protocol['input_roles']['narrow_labels']) or not same_binding(inputs['old_event_ids'],protocol['old_event_ids']):
        raise ValueError('frozen pure-ID inputs differ')
    return out,protocol,auth,binding


def run_actual(out,protocol,auth,authorization_binding):
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();bundle=source_bundle()
    counts=dict(native_source_queries=0,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,downloads=0,whole_database_hashes=0)
    write_json(out/'actual_started.json',dict(status='started',stage='prepare',started_at=datetime.now(timezone.utc).isoformat(),
        source_bundle=bundle,protocol=file_binding(PROTOCOL),authorization=authorization_binding,**counts))
    try:
        inputs=auth['input_bindings']
        mother=pd.read_csv(io.BytesIO(read_bound(inputs['narrow_labels'])),compression='gzip',usecols=IDENTITY,dtype=str,keep_default_na=False)
        mother=_integers(mother,['sequence_index','u_index'])
        # Deliberately ignore old subset sequence_index and all old DAY fields.
        ids=pd.read_csv(io.BytesIO(read_bound(inputs['old_event_ids'])),compression='gzip',usecols=['event_id'],dtype=str,keep_default_na=False)
        if len(mother)!=399252 or len(ids)!=194709:raise ValueError('fixed mother/legacy ID row count differs')
        alignment=align_by_event_id(mother,ids.event_id.tolist())
        alignment_binding=write_csv(out/'sequence_alignment.csv.gz',alignment)
        order_sha=hashlib.sha256(('\n'.join(mother.event_id)+'\n').encode()).hexdigest()
        summary=dict(schema='stage093_sequence_alignment_summary_v1',mother_rows=len(mother),legacy_tensor_rows=len(ids),
            sequence_observed=int(alignment.sequence_missing.eq(0).sum()),sequence_missing=int(alignment.sequence_missing.sum()),
            full_mother_order_sha256=order_sha,no_old_DAY_fields_read=True,tensor_read=False,**counts)
        write_json(out/'summary.json',summary)
        if source_bundle()!=bundle:raise ValueError('source changed during preparation')
        write_json(out/'actual_terminal.json',dict(status='completed',completed=True,exit_code=0,completed_projection_rows=len(alignment),
            elapsed_seconds=time.monotonic()-started,**counts))
        artifacts=[dict(file_binding(out/name),role=role,reproducibility_required=True,raw_ohlc=False)
            for name,role in [('sequence_alignment.csv.gz','pure_X_event_identity_alignment'),('summary.json','alignment_summary'),
                              ('actual_started.json','actual_start_audit'),('actual_terminal.json','actual_terminal')]]
        manifest=dict(schema='stage093_sequence_alignment_v1',status='completed',mode='actual',protocol=file_binding(PROTOCOL),
            authorization=authorization_binding,source_bundle=bundle,input_bindings=inputs,alignment=alignment_binding,
            terminal=file_binding(out/'actual_terminal.json'),mother_rows=len(mother),legacy_tensor_rows=len(ids),
            full_mother_order_sha256=order_sha,artifacts=artifacts,**counts)
        write_json(out/'manifest.json',manifest);return manifest
    except BaseException as error:
        if not (out/'actual_terminal.json').exists():
            write_json(out/'actual_terminal.json',dict(status='failed',completed=False,exit_code=1,error_type=type(error).__name__,
                error=str(error),automatic_retry=False,elapsed_seconds=time.monotonic()-started,**counts))
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('output','protocol-sha256','authorization','authorization-sha256'):p.add_argument('--'+name,required=True)
    out,protocol,auth,binding=authorize(p.parse_args(argv));m=run_actual(out,protocol,auth,binding)
    print(json.dumps(dict(status=m['status'],output=str(out),mother_rows=m['mother_rows'],native_source_queries=0,actual_model_fit_calls=0)),flush=True)


if __name__=='__main__':main()
