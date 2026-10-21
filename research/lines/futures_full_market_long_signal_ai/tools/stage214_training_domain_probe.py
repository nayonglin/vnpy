"""Frozen213 read-only training-domain probe: identities/old weights, no Y/X.

Only root's exact source/input authorization permits six cache reads. No model,
labels, cash, original actions, COMMON or native-price arrays are imported/read.
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
import time
import traceback

import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent; LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage213_training_domain_probe_protocol/protocol.json'
PROTOCOL_SHA='17805a9fa6dd2df655ea9f4bebb84993f9c6beb6733d0772ea2c5812abee1033'
OUTPUT=LINE/'outputs/stage214_training_domain_probe/actual_run1'
READ_COLUMNS=['sequence_index','action_id','product_id','family_id','u_date','u_index',
              'reference_epoch','u_action_eligible','label_known_date','sample_weight']
PARTITIONS=('admissible','inadmissible','unknown')
SCOPES=('main','holdout_0','holdout_1'); CUTOFFS=('2020-01-01','2023-01-01')
SAMPLE_END='2026-10-16'; _GATE=None


def binding(path):
    p=Path(path).resolve(); raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read_bound(bound):
    raw=Path(bound['path']).read_bytes()
    if len(raw)!=bound['bytes'] or hashlib.sha256(raw).hexdigest()!=bound['sha256']:
        raise ValueError('small_binding_changed '+bound['path'])
    return raw


def write_json(path,value):
    with Path(path).open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)
        stream.write('\n');stream.flush()


def source_bundle():
    return sorted([binding(TOOLS/n) for n in ('stage214_training_domain_probe.py',
        'test_stage214_training_domain_probe.py','stage156_voluntary_choices.py')],key=lambda b:b['path'])


def source_stat(bound):
    p=Path(bound['path']); s=p.stat()
    if not p.is_file() or s.st_size!=bound['bytes']:raise ValueError('accepted_cache_size_changed '+str(p))
    return dict(path=str(p.resolve()),bytes=s.st_size,device=s.st_dev,inode=s.st_ino,
                mtime_ns=s.st_mtime_ns,inherited_sha256=bound['sha256'],rehashed=False)


def gate_helper():
    global _GATE
    if _GATE is None:
        spec=importlib.util.spec_from_file_location('stage214_accepted156',TOOLS/'stage156_voluntary_choices.py')
        _GATE=importlib.util.module_from_spec(spec);spec.loader.exec_module(_GATE)
    return _GATE


def action_gate(u,epoch,calendar,boundary=None):
    """213's score-free copy of156 gate order, calling its unchanged K helper."""
    if isinstance(u,bool) or int(u)!=u or not 0<=int(u)<len(calendar):raise ValueError('invalid_source_u_index')
    u=int(u); b=gate_helper().calendar_boundary(epoch,calendar,SAMPLE_END) if boundary is None else boundary
    D=u+1 if u+1<len(calendar) else None; date=calendar[D] if D is not None else None
    if b['K_state']=='before_calendar_blocked': state,reason='inadmissible','K_before_calendar_blocked'
    elif D is None: state,reason='unknown','next_source_session_unknown'
    elif b['K_index'] is None:
        state='admissible' if date<b['K_target_date'] else 'inadmissible'
        reason='K_after_calendar_D_before_target' if state=='admissible' else 'K_after_calendar_D_on_or_after_target'
    else:
        state='admissible' if D<b['K_index'] else 'inadmissible'
        reason='D_before_K' if state=='admissible' else 'D_on_or_after_K'
    return dict(D_index=D,D_date=date,partition=state,gate_reason=reason,**b)


def validate_frame(frame,scope,cutoff,expected_rows,calendar):
    if set(frame.columns)!=set(READ_COLUMNS):raise ValueError('exact_read_column_allowlist_required')
    f=frame.loc[:,READ_COLUMNS].copy()
    if len(f)!=expected_rows or not len(f):raise ValueError('accepted_training_row_count_differs')
    for field in ('sequence_index','u_index','u_action_eligible'):
        values=f[field].astype(float).to_numpy()
        if not np.isfinite(values).all() or not np.equal(values,np.floor(values)).all():
            raise ValueError('noninteger_identity '+field)
        if (values<0).any() or (values>np.iinfo(np.int64).max).any():raise ValueError('identity_outside_int64')
        f[field]=values.astype(np.int64)
    # Accepted130 numbers were already parsed and exported17g. Direct float
    # restoration preserves IEEE weights; never apply pd.to_numeric again.
    w=f.sample_weight.astype(float).to_numpy(); f['sample_weight']=w
    if not np.isfinite(w).all() or (w<=0).any():raise ValueError('old_weights_not_finite_positive')
    seq=f.sequence_index.to_numpy();u=f.u_index.to_numpy()
    if (np.diff(seq)<=0).any() or f.action_id.duplicated().any() or f.action_id.eq('').any():
        raise ValueError('nonmonotone_or_duplicate_training_identity')
    if (u>=len(calendar)).any() or not np.array_equal(f.u_date.to_numpy(),np.asarray(calendar)[u]):
        raise ValueError('source_u_calendar_identity_differs')
    if not f.u_action_eligible.eq(1).all():raise ValueError('accepted_training_u_eligibility_differs')
    if (not f.u_date.lt(cutoff).all() or f.label_known_date.eq('').any()
            or not f.label_known_date.lt(cutoff).all()):raise ValueError('old_mature_training_cutoff_differs')
    if (not f.reference_epoch.str.rsplit('.',n=1).str[0].eq(f.product_id).all()
            or not f.family_id.eq(f.product_id.str.removesuffix('_F')).all()):
        raise ValueError('exact_product_family_epoch_identity_differs')
    if scope not in SCOPES or cutoff not in CUTOFFS:raise ValueError('unknown_fixed_fold')
    if scope!='main':
        groups=f.family_id.map(lambda v:int(hashlib.sha256(str(v).encode()).hexdigest(),16)%2)
        if groups.eq(int(scope[-1])).any():raise ValueError('held_family_entered_training')
    return f


def partition_summary(frame):
    w=frame.sample_weight.to_numpy(float); total=math.fsum(w); n=len(frame)
    result=dict(rows=n,old_weight_mass=total)
    masses=[];counts=[]
    for state in PARTITIONS:
        part=w[frame.partition.eq(state).to_numpy()]; mass=math.fsum(part); count=len(part)
        result.update({state+'_rows':count,state+'_old_weight_mass':mass,
                       state+'_row_fraction':count/n,state+'_weight_fraction':mass/total})
        masses.append(mass);counts.append(count)
    residual=math.fsum(masses)-total; tolerance=8*math.ulp(total)
    if sum(counts)!=n or abs(residual)>tolerance:raise ValueError('three_partition_conservation_failed')
    result.update(weight_partition_residual=residual,weight_roundoff_tolerance=tolerance)
    return result


def aggregate(frame,scope,cutoff,column):
    rows=[]
    for key,part in frame.groupby(column,sort=True,observed=True):
        rows.append(dict(scope=scope,cutoff=cutoff,group=str(key),**partition_summary(part)))
    return rows


def conservation(overall,rows,dimension):
    fields=['old_weight_mass']+[s+'_old_weight_mass' for s in PARTITIONS]
    count_fields=['rows']+[s+'_rows' for s in PARTITIONS]
    if any(sum(r[k] for r in rows)!=overall[k] for k in count_fields):
        raise ValueError('group_count_conservation_failed '+dimension)
    residuals={k:math.fsum(r[k] for r in rows)-overall[k] for k in fields}
    tolerance=8*math.ulp(overall['old_weight_mass'])
    if any(abs(v)>tolerance for v in residuals.values()):raise ValueError('group_weight_conservation_failed '+dimension)
    return dict(dimension=dimension,groups=len(rows),count_fields_exact=True,
                weight_residuals=residuals,weight_roundoff_tolerance=tolerance)


def probe_frame(frame,scope,cutoff,expected_rows,calendar,anchor_positions=()):
    f=validate_frame(frame,scope,cutoff,expected_rows,calendar)
    epochs={e:gate_helper().calendar_boundary(e,calendar,SAMPLE_END) for e in sorted(f.reference_epoch.unique())}
    states=[];reasons=[];anchors=[];requested=set(int(i) for i in anchor_positions)
    if any(i<0 or i>=len(f) for i in requested):raise ValueError('anchor_position_outside_fold')
    for i,(u,epoch) in enumerate(zip(f.u_index,f.reference_epoch)):
        g=action_gate(int(u),epoch,calendar,epochs[epoch]);states.append(g['partition']);reasons.append(g['gate_reason'])
        if i in requested:
            row=f.iloc[i]
            anchors.append(dict(scope=scope,cutoff=cutoff,cached_row_position=i,
                **{k:(int(row[k]) if k in ('sequence_index','u_index') else float(row[k]) if k=='sample_weight' else row[k])
                   for k in ('sequence_index','action_id','product_id','family_id','u_date','u_index','reference_epoch','sample_weight')},
                **g))
    f['partition']=states;f['gate_reason']=reasons;f['year']=f.u_date.str[:4]
    summary=dict(scope=scope,cutoff=cutoff,**partition_summary(f))
    groups={dimension:aggregate(f,scope,cutoff,column) for dimension,column in
            (('year','year'),('family','family_id'),('product','product_id'))}
    checks=[conservation(summary,rows,dimension) for dimension,rows in groups.items()]
    reason_rows=aggregate(f,scope,cutoff,'gate_reason')
    checks.append(conservation(summary,reason_rows,'gate_reason'))
    support=dict(scope=scope,cutoff=cutoff,rows=len(f),sequence_min=int(f.sequence_index.min()),
        sequence_max=int(f.sequence_index.max()),action_id_unique=True,sequence_strictly_increasing=True,
        exact_product_and_family=True,source_calendar_aligned=True,old_u_eligible_all1=True,
        max_u_date=str(f.u_date.max()),max_old_label_known_date=str(f.label_known_date.max()),
        old_weight_min=float(f.sample_weight.min()),old_weight_max=float(f.sample_weight.max()),
        old_weights_renormalized=False,old_weights_recomputed=False,checks=checks,
        gate_reasons=reason_rows,anchor_positions=sorted(requested))
    return summary,groups,support,anchors


def authorize(args):
    out=Path(args.output).resolve()
    if out!=OUTPUT or out.exists():raise ValueError('fresh_exact_stage214_actual_run1_required')
    pb=binding(PROTOCOL)
    if pb['sha256']!=PROTOCOL_SHA:raise ValueError('frozen213_changed')
    protocol=json.loads(read_bound(pb));ab=binding(args.authorization)
    if ab['sha256']!=args.authorization_sha256:raise ValueError('root_authorization_sha_changed')
    auth=json.loads(read_bound(ab))
    required=dict(schema='stage213_exact_root_domain_authorization_v1',authorized_by='root',stage='domain_probe',
                  exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out))
    if (any(auth.get(k)!=v for k,v in required.items()) or auth.get('source_bundle')!=source_bundle()
            or auth.get('inputs')!=protocol['inputs'] or auth.get('folds')!=protocol['folds']):
        raise ValueError('exact_root_authorization_differs')
    if protocol.get('read_columns')!=READ_COLUMNS:raise ValueError('frozen_read_allowlist_differs')
    return out,protocol,auth,ab,pb


def run_actual(output,protocol,auth,authorization,protocol_binding):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    source=source_bundle();artifacts={};started_folds=completed_folds=0
    counters=dict(training_cache_reads_attempted=0,training_cache_reads_completed=0,calendar_reads=0,
        fit=0,cash=0,old_cash=0,SQL=0,new_labels=0,prediction=0,selection=0,price_data_reads=0,
        original_actions_reads=0,COMMON_reads=0,native_cache_reads=0,large_input_hashes=0)
    def save_json(name,obj):
        write_json(output/name,obj);b=binding(output/name);artifacts[name]=b;return b
    def save_csv(name,rows):
        pd.DataFrame(rows).to_csv(output/name,index=False,float_format='%.17g')
        b=binding(output/name);artifacts[name]=b;return b
    save_json('started.json',dict(status='started',started_at=datetime.now(timezone.utc).isoformat(),
        protocol=protocol_binding,authorization=authorization,source_bundle=source,automatic_retry=False))
    before={};after={}
    try:
        small={r:json.loads(read_bound(protocol['inputs'][r])) for r in
               ('control_fit_manifest','control_fit_records','prior_decision','alignment_proposal')}
        fit=small['control_fit_manifest'];records=small['control_fit_records']
        if fit.get('status')!='completed' or fit.get('actual_fit_calls_completed')!=6:
            raise ValueError('accepted130_fit_not_complete')
        if fit['fit_records']!=protocol['inputs']['control_fit_records']:raise ValueError('accepted_fit_records_changed')
        if binding(protocol['inputs']['calendar_gate_source']['path'])!=protocol['inputs']['calendar_gate_source']:
            raise ValueError('accepted156_gate_source_changed')
        expected={(s,c) for s in SCOPES for c in CUTOFFS}
        folds=protocol['folds'];rr={(r['scope'],r['cutoff']):r for r in records}
        if len(folds)!=6 or {(f['scope'],f['cutoff']) for f in folds}!=expected or set(rr)!=expected:
            raise ValueError('exact_six_unique_folds_required')
        for fold in folds:
            r=rr[(fold['scope'],fold['cutoff'])]
            if r['training_identity_weights']!=fold['training_cache'] or r['training_rows']!=fold['training_rows']:
                raise ValueError('accepted_training_cache_fold_changed')
        counters['calendar_reads']+=1
        arr=np.load(io.BytesIO(read_bound(protocol['inputs']['calendar'])),allow_pickle=False)
        calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in arr]
                  if arr.dtype.kind in 'iu' else arr.astype('datetime64[D]').astype(str).tolist())
        if len(calendar)!=5587 or calendar!=sorted(set(calendar)):raise ValueError('accepted_full_calendar_changed')
        totals=[];support=[];anchors=[];groups={k:[] for k in ('year','family','product')}
        total_rows=sum(f['training_rows'] for f in folds)
        global_positions=np.linspace(0,total_rows-1,min(16,total_rows),dtype=np.int64)
        offset=0
        for fold in folds:
            scope,cutoff=fold['scope'],fold['cutoff'];key=scope+'/'+cutoff;b=fold['training_cache']
            started_folds+=1;before[key]=source_stat(b)
            counters['training_cache_reads_attempted']+=1
            frame=pd.read_csv(b['path'],usecols=READ_COLUMNS,dtype=str,keep_default_na=False,float_precision='round_trip')
            counters['training_cache_reads_completed']+=1
            requested=global_positions[(global_positions>=offset)&(global_positions<offset+fold['training_rows'])]-offset
            summary,gg,proof,aa=probe_frame(frame,scope,cutoff,fold['training_rows'],calendar,requested)
            totals.append(summary);support.append(proof);anchors.extend(aa)
            for dim in groups:groups[dim].extend(gg[dim])
            offset+=len(frame);after[key]=source_stat(b)
            if before[key]!=after[key]:raise ValueError('accepted_cache_changed_during_read '+key)
            completed_folds+=1
            with (output/'fold_progress.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(scope=scope,cutoff=cutoff,completed=completed_folds,rows=len(frame)))+'\n');stream.flush()
            print(json.dumps(dict(phase='training_domain_fold_complete',scope=scope,cutoff=cutoff,
                                 completed=completed_folds)),flush=True)
        if completed_folds!=6 or counters['training_cache_reads_completed']!=6 or offset!=total_rows or len(anchors)>16:
            raise ValueError('six_fold_completion_or_anchor_budget_differs')
        if source!=source_bundle():raise ValueError('source_changed_during_actual')
        final_stat={f['scope']+'/'+f['cutoff']:source_stat(f['training_cache']) for f in folds}
        if final_stat!=after:raise ValueError('accepted_cache_changed_before_terminal')
        roles={'fold_summary':save_csv('fold_summary.csv',totals)}
        for dim,rows in groups.items():roles['by_'+dim]=save_csv('by_'+dim+'.csv',rows)
        roles['support']=save_json('support_and_conservation.json',support)
        roles['anchors']=save_json('anchors.json',dict(policy='16 equally spaced cached-row positions in frozen six-fold sequence order',
            global_positions=global_positions.tolist(),total_cached_rows=total_rows,anchors=anchors,not_outcome_selected=True))
        roles['source_receipt']=save_json('source_read_receipt.json',dict(before=before,after=final_stat,
            read_columns=READ_COLUMNS,counters=counters,old_weights_renormalized=False))
        summary=dict(schema='stage214_training_domain_summary_v1',status='completed',folds=totals,
            exact_six_folds=True,all_admissible=all(t['admissible_rows']==t['rows'] for t in totals),
            any_fold_no_admissible=any(t['admissible_rows']==0 for t in totals),
            any_gate_unknown=any(t['unknown_rows']>0 for t in totals),
            interpretation='training action-domain support only; no target effect, financial effect or model authorization',
            counters=counters,cumulative_fit=427,cumulative_cash=230,goal_complete=False)
        roles['summary']=save_json('summary.json',summary)
        terminal=save_json('terminal.json',dict(status='completed',exit_code=0,started_folds=started_folds,
            completed_folds=completed_folds,counters=counters,elapsed_seconds=time.monotonic()-start,automatic_retry=False))
        artifacts['fold_progress.jsonl']=binding(output/'fold_progress.jsonl')
        manifest=dict(schema='stage214_training_domain_probe_manifest_v1',status='completed',
            protocol=protocol_binding,protocol_sha256=PROTOCOL_SHA,authorization=authorization,source_bundle=source,
            inputs=protocol['inputs'],folds=folds,artifacts=artifacts,terminal=terminal,counters=counters,
            cumulative_fit=427,cumulative_cash=230,financial_authorization=False,goal_complete=False,**roles)
        write_json(output/'manifest.json',manifest);return manifest
    except BaseException as error:
        if not (output/'terminal.json').exists():
            write_json(output/'terminal.json',dict(status='failed',exit_code=1,started_folds=started_folds,
                completed_folds=completed_folds,counters=counters,before=before,after=after,
                error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),
                elapsed_seconds=time.monotonic()-start,automatic_retry=False))
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--actual',action='store_true',required=True)
    p.add_argument('--authorization',required=True);p.add_argument('--authorization-sha256',required=True)
    p.add_argument('--output',type=Path,default=OUTPUT);args=p.parse_args(argv)
    out,protocol,auth,ab,pb=authorize(args);result=run_actual(out,protocol,auth,ab,pb)
    print(json.dumps(dict(status=result['status'],counters=result['counters'],output=str(out))),flush=True)


if __name__=='__main__':main()
