"""One independent new189 experiment audit; no refit/strategy replay/source q.

Accepted132/158 mathematics are reused only through arm-independent functions.
Root alone invokes actual after exact source/input authorization. Every finished
phase is durable; no automatic retry or completed financial-book regeneration.
Copies accepted169 independent review math, adapted only for frozen189 lineage,
original D/D-1/D-2 registration clock and hashed one-pass new CSV reads.
No author190/191 or old model/score/account result is imported or inspected.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import datetime,timezone
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
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='7d2209746ec71740d7869d8a993ed877d609a1bade71c748378d3519fa3a5451'
ARMS=('CONTROL54','REGISTRATION54')
SCOPES=('main','holdout_0','holdout_1')
CUTOFFS=('2020-01-01','2023-01-01')
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
IDENTITY=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
HELPERS={'stage158_voluntary_review.py':'fb39dc7e4eb7d108bb51de2f2a26a481c28377dd80e6581ecc8e241bce6cec37',
    'stage132_contract_choice_review.py':'7d8b5fd1c1a2d80d2df32632c8b097e9ca15eced9e65de745af40f1e32a3a181',
    'stage102_cash_adapter.py':'702ad195d988eec4d847289ad9961525a35e65d4146de796073b1ca3c0df9044',
    'stage102_cash_core.py':'4310bdd81375e17406b1773658c582ccb570a25d09b8fa53d15461c76cbb3eaa',
    'stage102_cash_diagnostics.py':'0075f91ba110ea902ee374a917f20433ace66afde9bde755088f2573d09d11cc'}
INHERITED=set()
NEW_CSV_BINDINGS={}
DISK_READS=Counter()
VERIFIED=set()
ERRORS={}
_REUSE=None


def binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for x in iter(lambda:f.read(1<<20),b''):h.update(x)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def same(a,b):assert all(a.get(k)==b.get(k) for k in ('path','bytes','sha256')),('binding',a,b)


def verify(b):
    p=Path(b['path'])
    if str(p) in INHERITED:assert p.stat().st_size==b['bytes'];return p
    key=tuple(b[k] for k in ('path','bytes','sha256'))
    if key not in VERIFIED:same(binding(p),b);VERIFIED.add(key)
    return p


def read_json(b):return json.loads(verify(b).read_text())


class HashingReader(io.RawIOBase):
    def __init__(self,stream):self.stream=stream;self.digest=hashlib.sha256();self.count=0
    def readable(self):return True
    def readinto(self,target):
        data=self.stream.read(len(target));target[:len(data)]=data;self.digest.update(data);self.count+=len(data);return len(data)


@contextmanager
def csv_stream(b):
    """Hash fresh CSV bytes while parsing, inherit accepted large-source SHA."""
    path=Path(b['path']);before=stat_identity(b);DISK_READS[str(path)]+=1
    if str(path) in INHERITED:
        with path.open('rb') as raw:
            stream=gzip.GzipFile(fileobj=raw) if str(path).endswith('.gz') else raw
            yield stream
    else:
        with path.open('rb') as raw:
            hashing=HashingReader(raw);buffer=io.BufferedReader(hashing)
            stream=gzip.GzipFile(fileobj=buffer) if str(path).endswith('.gz') else buffer
            yield stream
            while stream.read(1<<20):pass
            assert hashing.count==b['bytes'] and hashing.digest.hexdigest()==b['sha256'],('streamed new CSV binding',str(path))
            VERIFIED.add(tuple(b[k] for k in ('path','bytes','sha256')))
    assert before==stat_identity(b),('CSV changed while reading',str(path))


def table(b,usecols=None):
    with csv_stream(b) as stream:
        return pd.read_csv(stream,dtype=str,keep_default_na=False,float_precision='round_trip',usecols=usecols)


def numeric(f,cols):
    for c in cols:
        if c in f:f[c]=pd.to_numeric(f[c].replace('',np.nan),errors='raise')
    return f


def finite(x):
    try:return not isinstance(x,(bool,np.bool_)) and math.isfinite(float(x))
    except(TypeError,ValueError):return False


def flag(x):
    assert str(x).lower() in ('true','false','1','0')
    return str(x).lower() in ('true','1')


def compare(a,b,label,atol=2e-7,rtol=2e-10):
    x,y=np.asarray(a,float),np.asarray(b,float)
    assert x.shape==y.shape and np.array_equal(np.isnan(x),np.isnan(y)),(label,'shape/null')
    assert np.array_equal(np.isfinite(x),np.isfinite(y)),(label,'finite')
    z=np.isfinite(x)&np.isfinite(y);e=np.abs(x[z]-y[z]);m=float(e.max()) if e.size else 0.
    ERRORS[label]=max(ERRORS.get(label,0.),m)
    assert np.all(e<=atol+rtol*np.abs(y[z])),(label,m)


def fields(got,want,label):
    for k,v in want.items():
        assert k in got,(label,k)
        a=got[k]
        if isinstance(v,(bool,np.bool_)):assert flag(a)==v,(label,k,a,v)
        elif v is None:assert a is None or a=='' or isinstance(a,float) and math.isnan(a),(label,k,a)
        elif isinstance(v,(int,np.integer)):assert float(a).is_integer() and int(float(a))==int(v),(label,k,a,v)
        elif isinstance(v,(float,np.floating)):
            av=float(a) if a!='' else np.nan;key=label+'.'+k
            assert math.isnan(av)==math.isnan(float(v)) and math.isfinite(av)==math.isfinite(float(v)),(key,'finite/null')
            err=abs(av-float(v)) if math.isfinite(av) else 0.;ERRORS[key]=max(ERRORS.get(key,0.),err)
            assert err<=1e-8+2e-9*abs(float(v)),(key,av,v)
        elif isinstance(v,(dict,list)):nested(a,v,label+'.'+k)
        else:assert a==v,(label,k,a,v)


def nested(got,want,label):
    if isinstance(want,dict):
        assert set(got)==set(want),(label,'keys',set(got)^set(want))
        fields(got,want,label)
    elif isinstance(want,list):
        assert len(got)==len(want),(label,'length')
        for a,b in zip(got,want):nested(a,b,label)
    else:fields({'v':got},{'v':want},label)


def safe(x):
    if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [safe(v) for v in x]
    if isinstance(x,np.ndarray):return safe(x.tolist())
    if isinstance(x,(np.integer,np.bool_)):return x.item()
    if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
    return x


def write(path,x):
    with Path(path).open('x') as f:json.dump(safe(x),f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def interval_json(values):
    return json.dumps(safe(values),separators=(',',':'))


def progress(out,name,x):
    write(out/(name+'.json'),x);print(json.dumps(dict(phase=name,status='completed')),flush=True)


def artifact(m,role):
    if isinstance(m.get(role),dict) and 'path' in m[role]:return m[role]
    a=m.get('artifacts',[])
    if isinstance(a,dict):
        if role in a:return a[role]
        a=list(a.values())
    found=[v for v in a if v.get('role')==role or v.get('logical_name')==role or Path(v['path']).name==role]
    assert len(found)==1,('artifact',role,len(found));return found[0]


def reuse():
    global _REUSE
    if _REUSE is None:
        spec=importlib.util.spec_from_file_location('review192_accepted158',TOOLS/'stage158_voluntary_review.py')
        _REUSE=importlib.util.module_from_spec(spec);spec.loader.exec_module(_REUSE)
    return _REUSE


def bundle():return sorted([binding(TOOLS/n) for n in ('stage192_registration_review.py','test_stage192_registration_review.py',*HELPERS)],key=lambda b:b['path'])


def family_group(x):return int.from_bytes(hashlib.sha256(str(x).encode()).digest(),'big')%2


def q_statistics(q,w):
    q,w=np.asarray(q,float),np.asarray(w,float);ok=np.isfinite(q)
    assert q.shape==w.shape and np.isfinite(w).all() and (w>0).all()
    if not ok.any():return dict(ready=False,reason='no_finite_q',mean=None,var=None,scale=None,finite_count=0,finite_weight_sum=0.)
    mean=float(np.average(q[ok],weights=w[ok]));var=float(np.average((q[ok]-mean)**2,weights=w[ok]))
    ready=bool(math.isfinite(mean) and math.isfinite(var) and var>0)
    return dict(ready=ready,reason='' if ready else 'nonpositive_q_variance',mean=mean,var=var,scale=math.sqrt(var) if ready else None,finite_count=int(ok.sum()),finite_weight_sum=float(w[ok].sum()))


def design54(common,q,scaler,stats,arm):
    assert arm in ARMS
    x=np.asarray(common,float);q=np.asarray(q,float);m=np.asarray(scaler['common']['mean'],float);s=np.asarray(scaler['common']['scale'],float)
    assert x.shape==(len(q),26) and m.shape==s.shape==(26,) and np.isfinite(m).all() and np.isfinite(s).all() and (s>0).all()
    ok=np.isfinite(x);qok=np.isfinite(q)
    last=np.zeros(len(q)) if arm=='CONTROL54' else np.where(qok,(q-stats['mean'])/stats['scale'],0.)
    return np.column_stack([np.where(ok,(x-m)/s,0.),(~ok).astype(float),(~qok).astype(float),last])


def mature_mask(actions,scope,cutoff):
    mask=actions.u_action_eligible.eq(1)&actions.label_state.eq('closed_complete_bar_model')&actions.u_date.lt(cutoff)&actions.label_known_date.ne('')&actions.label_known_date.lt(cutoff)&np.isfinite(actions.net_R_stress)
    if scope!='main':mask &= actions.family_id.map(family_group).ne(int(scope[-1]))
    return mask


def normal_equations(X,y,w):
    Z=np.column_stack([X,np.ones(len(X))]);w=np.asarray(w,float);y=np.asarray(y,float)
    lhs=Z.T@(w[:,None]*Z);lhs[np.arange(X.shape[1]),np.arange(X.shape[1])]+=1.
    return lhs,Z.T@(w*y)


def align_q(actions,projection,calendar):
    identity=['action_id','event_id','action_sequence_index','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch']
    for c in identity:assert actions[c].astype(str).tolist()==projection[c].astype(str).tolist(),('accepted q identity',c)
    text=projection.scalar_missing.astype(str);assert text.isin(['0','1']).all()
    missing=text.eq('1').to_numpy();q=pd.to_numeric(projection.scalar_primary.replace('',np.nan),errors='raise').to_numpy(float)
    assert np.array_equal(missing,~np.isfinite(q)) and np.array_equal(projection.feature_state.eq('conditional_archive_scalar_known'),~missing)
    assert projection.loc[missing,'scalar_primary'].eq('').all() and (np.abs(q[~missing])<=1).all()
    u=actions.u_index.to_numpy(int);dates=np.asarray(calendar);assert (u>=0).all() and (u<len(dates)).all()
    assert np.array_equal(actions.u_date,dates[u])
    for ix,day,k,valid in [('decision_index','decision_date',u,np.ones(len(u),bool)),('prospective_entry_index','prospective_entry_date',u+1,u+1<len(dates)),('report_v_index','report_v',u-1,u>=2),('report_w_index','report_w',u-2,u>=2)]:
        got=pd.to_numeric(projection[ix].replace('',np.nan),errors='raise').to_numpy(float)
        assert np.array_equal(got[valid],k[valid]) and np.array_equal(projection.loc[valid,day],dates[k[valid]]),('exact original decision/report clock',ix)
        assert projection.loc[~valid,ix].eq('').all() and projection.loc[~valid,day].eq('').all(),('outside source clock remains missing',ix)
    return q


def full_choices(parents,children,calendar,scope,arm,cutoff):
    h=reuse();old={};new={};observed=set()
    for a in children:
        p=int(a['mother_sequence_index']);observed.add(p);positive=int(a['u_action_eligible'])==1 and finite(a['score']) and float(a['score'])>0
        b=h.deadline(a['reference_epoch'],calendar,'2026-10-16');legal=h.admission(int(a['u_index']),a['u_action_eligible'],a['score'],b,calendar,'2026-10-16')['new_eligible']==1
        if positive and (p not in old or h.action_order(a)<h.action_order(old[p])):old[p]=a
        if legal and (p not in new or h.action_order(a)<h.action_order(new[p])):new[p]=a
    winners=h.family_choices(new.values());oldwin=h.family_choices(old.values());result=[]
    for p in parents:
        seq=int(p['sequence_index']);proposal,winner,prior=new.get(seq),winners.get(seq),oldwin.get(seq)
        state='selected' if winner else 'family_priority_suppressed' if proposal else 'no_observed_children' if seq not in observed else 'no_calendar_eligible_positive_action' if seq in old else 'no_original_eligible_positive_action'
        result.append(dict(p,proposed_action_id=proposal['action_id'] if proposal else '',proposed_epoch=proposal['reference_epoch'] if proposal else '',proposed_score=float(proposal['score']) if proposal else None,chosen_action_id=winner['action_id'] if winner else '',chosen_action_sequence_index=int(winner['sequence_index']) if winner else -1,chosen_epoch=winner['reference_epoch'] if winner else '',anchor_epoch=p['reference_epoch'],score=float(winner['score']) if winner else None,selected=int(winner is not None),selection_state=state,scope=scope,cutoff=cutoff,arm=arm,policy='NARROW',old_chosen_action_id=prior['action_id'] if prior else '',old_chosen_epoch=prior['reference_epoch'] if prior else ''))
    return result


def outcome(action,labels,end):
    if not action:return 0.,False
    row=labels[action]
    if row['participation_state']=='known_nonparticipation':return 0.,False
    if row['label_state']=='closed_complete_bar_model' and row['label_known_date'] and row['label_known_date']<=end and finite(row['net_R_stress']):return float(row['net_R_stress']),False
    return None,True


def increment(control,active,labels,end):
    a,au=outcome(control,labels,end);b,bu=outcome(active,labels,end)
    if control==active:return 0.,False,bool(au or bu)
    if au or bu:return None,True,False
    return b-a,False,False


def frame_check(got,want,cols,label):
    assert len(got)==len(want),(label,'rows',len(got),len(want))
    for c in cols:
        a,b=got[c],want[c]
        if pd.api.types.is_numeric_dtype(b):compare(pd.to_numeric(a.replace('',np.nan)),b,label+'.'+c)
        else:assert a.astype(str).tolist()==b.astype(str).tolist(),(label,c)


def stat_identity(b):
    p=Path(b['path']);s=p.stat();assert s.st_size==b['bytes']
    return dict(path=str(p),bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino)


def financial_completion(terminal):
    fields(terminal,dict(status='completed',cash_accounts_started=8,new_cash_accounts=8,raw_ledgers_checkpointed=8,native_source_queries=0,new_labels=0,old_control_book_replays=0,no_automatic_resume=True),'financial completion before metadata')


def selection_disclosure(frame):
    assert frame.account_deadline_certified.map(flag).eq(False).all()
    assert frame.voluntary_policy_version.eq('stage155_voluntary_reselect_lead_months_1_v1_not_certified').all()


def input_closure(inputs,out):
    p=read_json(inputs['protocol']);fm=read_json(inputs['fit_manifest']);cm=read_json(inputs['cash_manifest'])
    assert inputs['protocol']['sha256']==PROTOCOL_SHA and p['schema']=='stage189_registration_information_financial_protocol_v1'
    assert fm['schema']=='stage190_registration_fit_v1' and cm['schema']=='stage191_registration_cash_v1'
    assert fm['status']==cm['status']=='completed' and fm['cash_eligible'] is True
    for role in ('actual_model_fit_calls','actual_fit_calls_attempted','actual_fit_calls_completed'):assert fm[role]==12
    assert cm['new_cash_accounts']==8 and cm['actual_model_fit_calls']==0 and cm['native_source_queries']==0
    newroles={'normalization_manifest','normalization_review','projection_manifest','projection_actions','projection_review','source_acceptance'}
    assert set(fm['input_bindings'])==set(p['source_bindings'])|newroles
    for role,b in p['source_bindings'].items():same(fm['input_bindings'][role],b)
    src=fm['input_bindings']
    for m in (fm,cm):
        same(m['protocol'],inputs['protocol']);assert m['protocol_sha256']==PROTOCOL_SHA
        for b in m['source_bundle']:verify(b)
        auth=read_json(m['authorization']);assert auth['authorized_by']=='root' and auth['exact_source_authorized'] is True
        assert auth['source_bundle']==m['source_bundle'];nested(auth['input_bindings'],m['input_bindings'],'upstream exact authorization inputs')
        t=read_json(m['terminal']);assert t['status']=='completed' and t['exit_code']==0
        artifacts=m['artifacts'];artifacts=list(artifacts.values()) if isinstance(artifacts,dict) else artifacts
        for b in artifacts:
            if b['path'].endswith('.csv.gz'):NEW_CSV_BINDINGS[b['path']]=b
            else:verify(b)
    for role,b in src.items():same(cm['input_bindings'][role],b)
    same(cm['input_bindings']['fit_manifest'],inputs['fit_manifest'])
    for role in ('choices_main','boundaries','held_diagnostic'):same(cm['input_bindings'][role],fm[role])
    same(cm['held_diagnostic'],fm['held_diagnostic'])
    dataset=read_json(src['dataset_manifest']);assert dataset['status']=='completed' and read_json(src['dataset_terminal'])['status']=='completed'
    for role in ('actions','common','mothers'):same(src[role],dataset[role])
    norm=read_json(src['normalization_manifest']);nr=read_json(src['normalization_review']);proj=read_json(src['projection_manifest']);pr=read_json(src['projection_review']);accept=read_json(src['source_acceptance'])
    assert norm['schema']=='stage186_warehouse_history_normalization_manifest_v1' and norm['status']=='completed'
    assert proj['schema']=='stage188_registration_projection_v1' and proj['status']=='completed'
    same(norm['calender'],src['calendar']);same(proj['actions_projection'],src['projection_actions'])
    for prefix,review in [('normalization',nr),('projection',pr)]:
        assert review['schema']=='stage187_registration_'+prefix+'_review_v1' and review['accepted'] is True and all(review[k]==0 for k in ('C','I','M'))
        same(review[prefix+'_manifest'],src[prefix+'_manifest'])
    for role in ('normalization_manifest','normalization_review'):same(pr[role],src[role])
    for role in ('normalization_manifest','normalization_review','dataset_manifest','actions','mothers','calendar'):same(proj['input_bindings'][role],src[role])
    same(proj['input_bindings']['feature_design'],p['design_basis']);same(proj['input_bindings']['scope_ruling'],p['legacy_representation_basis'])
    for manifest in (norm,proj):
        terminal=read_json(manifest['terminal']);assert terminal['status']=='completed' and terminal['exit_code']==0
    assert accept['schema']=='stage189_registration_source_acceptance_v1' and accept['source_measurement_arithmetic_accepted'] is True
    for role in ('normalization_manifest','normalization_review','projection_manifest','projection_review','projection_actions'):same(accept[role],src[role])
    for role in ('actions','common','mothers','projection_actions'):
        b=src[role];e=fm['input_evidence'][role];same(e['binding'],b)
        assert e['stat_before']==e['stat_after']==stat_identity(b),(role,'inherited stat');INHERITED.add(b['path'])
    native=read_json(cm['source_read_receipt']);same(native['cache_file'],src['native_cache']);assert native['cache_stat']==stat_identity(src['native_cache'])
    INHERITED.add(src['native_cache']['path'])
    ft=read_json(cm['financial_terminal']);financial_completion(ft);assert len(cm['accounts'])==8
    for a in cm['accounts']:
        check=read_json(a['checkpoint']);assert check['status']=='raw_book_complete' and check['no_book_replay_allowed'] is True
        for role,b in a['ledgers'].items():same(check['ledgers'][role],b);NEW_CSV_BINDINGS[b['path']]=b
    p['source_bindings']=src
    result=dict(protocol=inputs['protocol'],fit_manifest=inputs['fit_manifest'],cash_manifest=inputs['cash_manifest'],accepted_measurement_not_recomputed=True,large_input_sha_inherited_without_extra_hash=True,source_inputs_unchanged={r:stat_identity(src[r]) for r in ('actions','common','mothers','projection_actions','native_cache')},upstream_fit_calls=12,upstream_cash_books=8)
    progress(out,'input_closure',result);return p,fm,cm


def load_data(p,out):
    src=p['source_bindings'];num=['sequence_index','action_sequence_index','mother_sequence_index','u_index','entry_index','exit_index','net_R_stress','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close','label_history_ready20']
    cols=list(dict.fromkeys(IDENTITY+['action_sequence_index','action_id','actual_epoch','mother_sequence_index','mother_event_id','anchor_epoch','u_action_eligible','entry_index','exit_index','entry_date','exit_date','net_R_stress','label_state','label_known_date','participation_state','entry_capacity_qty','label_history_ready20','N_u','low20_u','u_close']))
    a=numeric(table(src['actions'],cols),num);m=numeric(table(src['mothers'],IDENTITY),['sequence_index','u_index'])
    assert len(a)==1552456 and len(m)==399252 and a.action_id.is_unique and m.event_id.is_unique
    assert np.array_equal(a.sequence_index,np.arange(len(a))) and np.array_equal(m.sequence_index,np.arange(len(m)))
    assert a.sequence_index.eq(a.action_sequence_index).all() and a.event_id.eq(a.action_id).all() and a.reference_epoch.eq(a.actual_epoch).all()
    assert m.product_id.nunique()==98 and m.family_id.nunique()==95 and m.product_id.str.split('.').str[0].nunique()==6
    pi=a.mother_sequence_index.to_numpy(int);assert (pi>=0).all() and (pi<len(m)).all()
    for l,r in [('mother_event_id','event_id'),('product_id','product_id'),('family_id','family_id'),('u_date','u_date'),('u_index','u_index'),('anchor_epoch','reference_epoch')]:assert np.array_equal(a[l],m[r].to_numpy()[pi]),('full original action-parent identity',l)
    raw=np.load(verify(src['calendar']),allow_pickle=False)
    calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in raw] if raw.dtype.kind in 'iu' else raw.astype('datetime64[D]').astype(str).tolist())
    assert len(calendar)==5587 and calendar==sorted(set(calendar)) and calendar[-1]=='2027-12-31'
    ids=['action_id','event_id','action_sequence_index','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch']
    clock=['decision_date','decision_index','prospective_entry_date','prospective_entry_index','report_v','report_v_index','report_w','report_w_index']
    qs=[];i=0;states=Counter();year_finite=Counter();year_rows=Counter()
    with csv_stream(src['projection_actions']) as stream:
        for chunk in pd.read_csv(stream,usecols=ids+clock+['scalar_missing','scalar_primary','feature_state'],dtype=str,keep_default_na=False,chunksize=100000,float_precision='round_trip'):
            part=a.iloc[i:i+len(chunk)];chunk=numeric(chunk,['action_sequence_index','mother_sequence_index','u_index']);v=align_q(part,chunk,calendar);qs.append(v);states.update(chunk.feature_state);year_rows.update(chunk.u_date.str[:4]);year_finite.update(chunk.loc[np.isfinite(v),'u_date'].str[:4]);i+=len(chunk)
    assert i==len(a);q=np.concatenate(qs)
    DISK_READS[src['common']['path']]+=1
    with np.load(verify(src['common']),allow_pickle=False) as z:common=z['common'].astype(float);columns=z['columns'].tolist()
    execution=read_json(src['execution_protocol']);assert common.shape==(len(a),26) and columns==execution['features']['common_columns']
    assert (a.u_date.ge(CUTOFFS[0])).sum()==966740 and (m.u_date.ge(CUTOFFS[0])).sum()==161014
    assert year_finite['2026']==0,'2026 original registration scalar support must remain missing'
    progress(out,'identity_and_accepted_q',dict(actions=len(a),mothers=len(m),common_shape=common.shape,q_finite=int(np.isfinite(q).sum()),q_projection_states=dict(states),q_rows_by_year=dict(year_rows),q_finite_by_year=dict(year_finite),all_2026_registration_q_missing=True,calendar_sessions=len(calendar),source_q_recalculations=0,child_parent_aliases_separate=True))
    return a,m,common,q,calendar,columns,execution


def fold_indices(a,m,scope,cutoff,nextcut):
    tr=mature_mask(a,scope,cutoff).to_numpy();pr=a.u_date.ge(cutoff).to_numpy();mr=m.u_date.ge(cutoff).to_numpy()
    if nextcut:pr&=a.u_date.lt(nextcut).to_numpy();mr&=m.u_date.lt(nextcut).to_numpy()
    if scope!='main':g=int(scope[-1]);pr&=a.family_id.map(family_group).eq(g).to_numpy();mr&=m.family_id.map(family_group).eq(g).to_numpy()
    return tuple(np.flatnonzero(v) for v in (tr,pr,mr))


def vector_choices(parents,child,bounds,calendar,scope,arm,cutoff):
    f=child.copy();positive=f.u_action_eligible.eq(1)&f.score.gt(0)&np.isfinite(f.score)
    gates=[]
    for epoch,u in zip(f.reference_epoch,f.u_index):
        b=bounds[epoch];D=int(u)+1
        gates.append(b['K_state']!='before_calendar_blocked' and D<len(calendar) and (D<b['K_index'] if b['K_index'] is not None else calendar[D]<b['K_target_date']))
    def proposals(mask):return f.loc[mask].sort_values(['mother_sequence_index','score','reference_epoch','action_id'],ascending=[True,False,True,True],kind='stable').drop_duplicates('mother_sequence_index')
    def winners(c):
        c=c.copy();c['isF']=c.product_id.str.endswith('_F').astype(int)
        return c.sort_values(['u_index','family_id','isF','product_id','reference_epoch','action_id'],kind='stable').drop_duplicates(['family_id','u_index']).set_index('mother_sequence_index')
    old=proposals(positive);new=proposals(positive&np.asarray(gates));win=winners(new);ow=winners(old);prop=new.set_index('mother_sequence_index')
    o=parents.copy();idx=o.sequence_index
    for col,source,key,fill in [('proposed_action_id',prop,'action_id',''),('proposed_epoch',prop,'reference_epoch',''),('proposed_score',prop,'score',np.nan),('chosen_action_id',win,'action_id',''),('chosen_action_sequence_index',win,'sequence_index',-1),('chosen_epoch',win,'reference_epoch',''),('score',win,'score',np.nan),('old_chosen_action_id',ow,'action_id',''),('old_chosen_epoch',ow,'reference_epoch','')]:o[col]=idx.map(source[key]).fillna(fill)
    o['chosen_action_sequence_index']=o.chosen_action_sequence_index.astype(int);o['anchor_epoch']=o.reference_epoch;o['selected']=o.chosen_action_id.ne('').astype(int)
    o['selection_state']=np.select([o.selected.eq(1),o.proposed_action_id.ne(''),~idx.isin(f.mother_sequence_index),idx.isin(old.mother_sequence_index)],['selected','family_priority_suppressed','no_observed_children','no_calendar_eligible_positive_action'],default='no_original_eligible_positive_action')
    o['scope']=scope;o['cutoff']=cutoff;o['arm']=arm;o['policy']='NARROW'
    return o


def held_values(choices,a):
    ids=set(choices.loc[choices.selected.eq(1),'chosen_action_id']);labels=a.loc[a.action_id.isin(ids)].set_index('action_id')[['participation_state','label_state','label_known_date','net_R_stress']].to_dict('index');groups={};daily=[]
    for scope in sorted(choices.scope.unique()):
        part=choices.loc[choices.scope.eq(scope)];f=part.sort_values('selected',ascending=False,kind='stable').drop_duplicates(['arm','family_id','u_index'])
        arms={arm:f.loc[f.arm.eq(arm)].set_index(['family_id','u_index']).sort_index() for arm in ARMS};c,b=arms[ARMS[0]],arms[ARMS[1]]
        assert c.index.tolist()==b.index.tolist() and c.u_date.tolist()==b.u_date.tolist()
        vals=[increment(x,y,labels,'2026-10-16') for x,y in zip(c.chosen_action_id,b.chosen_action_id)]
        frame=pd.DataFrame(dict(u_date=c.u_date.to_numpy(),delta_R=[v[0] for v in vals],known=[v[0] is not None for v in vals],unknown=[v[1] for v in vals]))
        day=frame.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_family_u=('known','sum'),unknown_family_u=('unknown','sum')).reset_index();day['scope']=scope;daily.append(day)
        mean=float(day.delta_R.mean()) if day.delta_R.notna().any() else None;nunknown=sum(v[1] for v in vals)
        groups[scope]=dict(nominal_pass=mean is not None and mean>=0,status='unsupported' if mean is not None and mean<0 else 'unknown' if mean is None or nunknown else 'supported',known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=nunknown,common_unresolved_same_action=sum(v[2] for v in vals),full_family_u=len(c),known_increment_family_u=sum(v[0] is not None for v in vals),known_source_days=int(day.delta_R.notna().sum()),selected_by_arm={arm:int(part.loc[part.arm.eq(arm),'selected'].sum()) for arm in ARMS},annual=[dict(year=y,mean_delta_R=float(v.delta_R.mean()) if v.delta_R.notna().any() else None,source_days=len(v),unknown_family_u=int(v.unknown_family_u.sum())) for y,v in day.groupby(day.u_date.str[:4])],unknown_R_bounds=None)
    return groups,pd.concat(daily,ignore_index=True)


def review_models(p,fm,a,m,common,q,calendar,columns,out,r):
    records=read_json(fm['fit_records']);assert len(records)==12
    keyed={(v['scope'],v['cutoff'],v['arm']):v for v in records};assert len(keyed)==12
    schedule=[dict(scope=s,cutoff=c,arm=arm,count=i+1) for i,(s,c,arm) in enumerate((s,c,arm) for s in SCOPES for c in CUTOFFS for arm in ARMS)]
    for name in ('fit_attempts.jsonl','fit_completed.jsonl'):
        rows=[json.loads(line) for line in verify(artifact(fm,name)).read_text().splitlines()]
        nested(rows,schedule,'all12 physical fit counters '+name)
    bounds=read_json(fm['boundaries']);same(bounds['calendar'],p['source_bindings']['calendar']);assert bounds['sample_end']=='2026-10-16' and bounds['not_certified'] is True and bounds['account_deadline_certified'] is False
    epochs=sorted(a.loc[a.u_date.ge(CUTOFFS[0]),'reference_epoch'].unique());assert set(bounds['epochs'])==set(epochs)
    independent_bounds={e:reuse().deadline(e,calendar,'2026-10-16') for e in epochs}
    nested(bounds['epochs'],independent_bounds,'all forward voluntary K boundaries')
    score_stream=csv_stream(fm['child_scores']);score_source=score_stream.__enter__();reader=pd.read_csv(score_source,dtype=str,keep_default_na=False,float_precision='round_trip',iterator=True)
    expected_choices=[];cellreports=[];scorecount=0;modelreports=[]
    for scope in SCOPES:
        for j,cutoff in enumerate(CUTOFFS):
            ti,pi,mi=fold_indices(a,m,scope,cutoff,CUTOFFS[j+1] if j+1<len(CUTOFFS) else None);train=a.iloc[ti].reset_index(drop=True);pred=a.iloc[pi];parent=m.iloc[mi]
            wdata=r.union_weights(train);w=wdata['sample_weight'];qs=q_statistics(q[ti],w)
            assert qs['ready'],'all six supports must preflight before first fit'
            stats=[r.weighted_stats(common[ti,k],w) for k in range(26)]
            scaler=dict(common=dict(columns=columns,**{key:[s[key] for s in stats] for key in ('mean','var','scale','finite_count')}),q=qs,feature_names=columns+[c+'_missing' for c in columns]+['registration_missing','registration_standardized'],scope=scope,cutoff=cutoff,control_final_design='exact_constant0',weighting='unchanged130 family_u_interval_union_then_divide_actions_then_equal_u')
            report=dict(scope=scope,cutoff=cutoff,training_rows=len(ti),training_dates=int(train.u_date.nunique()),training_families=int(train.family_id.nunique()),training_groups=len(wdata['groups']),prediction_children=len(pi),prediction_mothers=len(mi),q_statistics=qs,common_scaler_statistics=scaler['common'],max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()));cellreports.append(report)
            first=keyed[scope,cutoff,ARMS[0]];second=keyed[scope,cutoff,ARMS[1]]
            for role in ('training_identity_weights','weight_groups','scaler'):same(first[role],second[role])
            training_columns=[c for c in train if c not in ('N_u','low20_u','u_close')]
            got=table(first['training_identity_weights'],training_columns+['registration_q_raw','registration_q_missing','group_id','group_member_count','group_union_length','group_uniqueness','base_weight','day_weight_total','sample_weight'])
            frame_check(got,train,training_columns,'full original maturity identity and target')
            for col,key in [('group_id','group_id'),('group_member_count','group_member_count'),('group_union_length','union_length'),('group_uniqueness','group_uniqueness'),('base_weight','b_a'),('day_weight_total','day_weight_total'),('sample_weight','sample_weight')]:compare(pd.to_numeric(got[col]),wdata[key],'full family union weights '+col,atol=1e-9)
            compare(pd.to_numeric(got.registration_q_raw.replace('',np.nan)),q[ti],'training accepted q');compare(pd.to_numeric(got.registration_q_missing),(~np.isfinite(q[ti])).astype(int),'training same missing')
            gr=table(first['weight_groups']);expected=pd.DataFrame(wdata['groups']);expected['union_intervals']=expected.union_intervals.map(interval_json);frame_check(gr,expected,list(expected.columns),'full interval union groups')
            nested(read_json(first['scaler']),scaler,'shared fold scaler')
            del got,gr
            for arm in ARMS:
                rec=keyed[scope,cutoff,arm];fields(rec,dict(**report,arm=arm,dimension=54),'model record')
                portable=read_json(rec['portable_model']);fields(portable,dict(schema='stage190_portable_ridge54_v1',scope=scope,cutoff=cutoff,arm=arm),'portable model');nested(portable['parameters'],dict(alpha=1.,fit_intercept=True,solver='cholesky'),'fixed Ridge parameters');same(portable['scaler'],rec['scaler']);assert portable['feature_names']==scaler['feature_names']
                coef=np.asarray(portable['coef'],float);intercept=float(portable['intercept']);assert coef.shape==(54,) and np.isfinite(coef).all() and finite(intercept)
                if arm==ARMS[0]:assert coef[53]==0.,'CONTROL final coefficient must be exact zero'
                x=design54(common[ti],q[ti],scaler,qs,arm);lhs,rhs=normal_equations(x,train.net_R_stress.to_numpy(float),w);beta=np.r_[coef,intercept]
                with np.load(verify(rec['normal_equations']),allow_pickle=False) as z:
                    assert set(z.files)=={'lhs','rhs','coefficient_with_intercept','weight_sum'};compare(z['lhs'],lhs,'all12 independent lhs',atol=1e-7,rtol=1e-9);compare(z['rhs'],rhs,'all12 independent rhs',atol=1e-7,rtol=1e-9);compare(z['coefficient_with_intercept'],beta,'all12 portable beta',atol=1e-12);compare(z['weight_sum'],w.sum(),'all12 weight sum',atol=1e-8)
                residual=float(np.max(np.abs(lhs@beta-rhs)));compare(lhs@beta,rhs,'all12 Ridge normal equations without refit',atol=3e-7,rtol=1e-8);fields(rec,dict(normal_equation_max_abs_residual=residual),'record normal residual')
                del x,lhs,rhs
                xp=design54(common[pi],q[pi],scaler,qs,arm);scores=xp@coef+intercept;assert np.isfinite(scores).all()
                child=pred[['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible']].copy();child['score']=scores;child['scope']=scope;child['cutoff']=cutoff;child['arm']=arm;child['registration_q_raw']=q[pi];child['registration_q_missing']=xp[:,52].astype(int);child['registration_q_design']=xp[:,53]
                for start in range(0,len(child),100000):
                    part=child.iloc[start:start+100000];saved=reader.get_chunk(len(part));frame_check(saved,part,list(part.columns),'all forward scores and q design')
                scorecount+=len(child);expected_choices.append(vector_choices(parent,child,independent_bounds,calendar,scope,arm,cutoff));del xp,child
                rep=dict(scope=scope,cutoff=cutoff,arm=arm,training_rows=len(ti),predictions=len(pi),normal_equation_residual=residual,refits=0);modelreports.append(rep);progress(out,'model_'+scope+'_'+cutoff+'_'+arm,rep)
    try:extra=reader.get_chunk(1)
    except StopIteration:extra=pd.DataFrame()
    assert len(extra)==0 and scorecount==3866960
    score_stream.__exit__(None,None,None)
    preflight=read_json(fm['preflight']);nested(preflight['cells'],cellreports,'all6 original mature preflight supports');assert preflight['ready'] is True and preflight['failures']==[] and preflight['fit_calls_authorized']==12 and preflight['exact_six_unique_folds'] is True
    choices=pd.concat(expected_choices,ignore_index=True)
    main=numeric(table(fm['choices_main']),['sequence_index','u_index','chosen_action_sequence_index','proposed_score','score','selected']);held=numeric(table(fm['choices_holdout']),['sequence_index','u_index','chosen_action_sequence_index','proposed_score','score','selected'])
    for saved,is_main in ((main,True),(held,False)):
        expected=choices.loc[choices.scope.eq('main') if is_main else choices.scope.ne('main')].sort_values(['arm','sequence_index'],kind='stable');frame_check(saved,expected,list(expected.columns),'all full parent K selections')
        assert len(saved)==322028 and not saved.duplicated(['arm','event_id']).any()
        for arm in ARMS:
            part=saved.loc[saved.arm.eq(arm)];assert len(part)==161014 and part.sequence_index.tolist()==m.loc[m.u_date.ge(CUTOFFS[0]),'sequence_index'].tolist()
        selection_disclosure(saved)
    groups,days=held_values(choices,a);heldreport=read_json(fm['held_diagnostic']);nested(heldreport['groups'],groups,'all original target held diagnostic');fields(heldreport,dict(generalization_fully_qualified=False,full_policy_cash_qualified=False),'held limitations')
    saved_days=numeric(table(fm['held_daily']),['delta_R','known_family_u','unknown_family_u']);frame_check(saved_days,days,list(days.columns),'all held equal-u daily increments')
    result=dict(model_fits_reviewed=12,refits=0,all_forward_predictions_checked=scorecount,folds=cellreports,models=modelreports,main_parent_rows_per_arm=161014,held_union_parent_rows_per_arm=161014,held_groups=groups,all_full_parent_order_restored=True,filter_before_argmax=True,control_final_zero=True,accepted_q_measurement_inherited=True)
    progress(out,'models_and_choices_review',result);return main,heldreport,independent_bounds,result


def cached_store(p,calendar,r):
    src=p['source_bindings'];meta=read_json(src['native_cache_manifest']);same(meta['file'],src['native_cache'])
    assert meta['schema']=='stage132_native_store_recovery_cache_v1' and meta['native_rows']==1552456 and meta['native_epochs']==9520
    before=r.database_state(meta['database']['path']);assert all(meta['database'].get(k)==v for k,v in before.items())
    store=r.NativeBars(calendar);DISK_READS[src['native_cache']['path']]+=1
    with np.load(verify(src['native_cache']),allow_pickle=False) as z:
        assert 'calendar' not in z.files;epochs=z['epochs'].tolist();offsets=z['offsets'];arrays={k:z[k] for k in ('days','values','accepted','valid','N','low20','run')}
        assert len(epochs)==9520 and offsets[0]==0 and offsets[-1]==1552456
        for i,e in enumerate(epochs):store.series[e]={k:v[int(offsets[i]):int(offsets[i+1])] for k,v in arrays.items()}
    assert before==r.database_state(meta['database']['path'])
    market=read_json(src['market_protocol']);same(market['calendar'],src['calendar']);economics=read_json(market['economic_projection'])['instruments'];assert set(economics)==set(store.series)
    return store,economics,market['economic_projection']


def review_signals(p,cm,choices,a,bounds,store,economics,out,r):
    signals={};reports={};lineage=[];savedtrace=table(cm['boundary_lineage']);selected_ids=set()
    source=a.set_index('action_id',drop=False)
    for arm in ARMS:
        picked=choices.loc[choices.arm.eq(arm)&choices.selected.eq(1)];saved=numeric(table(cm['signals'][arm]),['action_sequence_index','u_index','D_index','label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index','entry_capacity_qty','u_gross_capacity_qty','potential','score','source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index'])
        assert saved.event_id.is_unique and saved.event_id.tolist()==picked.chosen_action_id.tolist() and not saved.duplicated(['family_id','u_date']).any()
        lookup=saved.set_index('event_id',drop=False);origins=Counter()
        for c in picked.itertuples(index=False):
            ac=source.loc[c.chosen_action_id];epoch=ac.reference_epoch;u=int(ac.u_index);j=store.locate(epoch,u);assert j is not None and store.series[epoch]['valid'][j] and ac.u_action_eligible==1
            native=store.series[epoch];gross,entry=r.capacity(native['values'][j,4],economics[epoch]['round_lot']);assert native['run'][j]>=20 and entry>=economics[epoch]['round_lot'] and c.score>0
            life=r.lifecycle(epoch,economics[epoch],store.calendar);b=bounds[epoch];effective,origin=reuse().effective_boundary(life,b,u+1)
            want=dict(mother_event_id=c.event_id,action_sequence_index=int(ac.action_sequence_index),product_id=ac.product_id,family_id=ac.family_id,u_date=ac.u_date,u_index=u,D_index=u+1,reference_epoch=epoch,anchor_epoch=ac.anchor_epoch,label_history_ready20=1,N_u=float(native['N'][j]),low20_u=float(native['low20'][j]),u_close=float(native['values'][j,3]),history_run=int(native['run'][j]),lifecycle_index=effective,entry_capacity_qty=int(entry),u_gross_capacity_qty=int(gross),potential=1,score=float(c.score),arm=arm,control_id=arm,policy='NARROW',cutoff=c.cutoff,source_lifecycle_index=life,voluntary_boundary_index=b['K_index'],effective_lifecycle_index=effective,effective_boundary_origin=origin,K_target_date=b['K_target_date'],K_date=b['K_date'],K_state=b['K_state'])
            fields(lookup.loc[c.chosen_action_id].to_dict(),want,'every independent selected signal')
            assert ac.mother_event_id==c.event_id and ac.anchor_epoch==c.anchor_epoch and epoch==c.chosen_epoch and int(ac.action_sequence_index)==int(c.chosen_action_sequence_index)
            compare([ac.N_u,ac.low20_u,ac.u_close,ac.entry_capacity_qty],[want['N_u'],want['low20_u'],want['u_close'],entry],'accepted selected causal features',atol=1e-10,rtol=1e-12);origins[origin]+=1
        trace=savedtrace.loc[savedtrace.arm.eq(arm)];frame_check(trace,saved,list(trace.columns),'all boundary sidecar rows')
        lookup['planned_execution_date']=[store.calendar[int(u)+1] if int(u)+1<len(store.calendar) else '' for u in lookup.u_index];signals[arm]=lookup;selected_ids.update(picked.chosen_action_id)
        reports[arm]=dict(selected_signals=len(saved),boundary_origins=dict(origins),all_source_min_K_checked=True,entry_on_K_forbidden=True,all_own_features_checked=True)
    assert len(savedtrace)==sum(len(v) for v in signals.values())
    src=read_json(cm['source_read_receipt']);fields(src,dict(native_source_queries=0,actual_model_fit_calls=0,new_labels=0,old_baseline_replays=0,selected_source_children=len(selected_ids),full_forward_parent_rows_per_arm=161014,full_mother_rows=399252,canonical_from_full_original_mothers=True,original_source_lifecycle_modified=False),'source read disclosure')
    progress(out,'signals_review',reports);return signals,reports


@contextmanager
def ledger_cache(spec,cash,diag):
    """Each raw new ledger is hashed/parsed once, independent math gets copies."""
    saved_csv,saved_read=cash.csv,diag._read;cache={}
    bindings={str(Path(v['path']).resolve()):v for v in spec['ledgers'].values()}
    required={'fills.csv.gz':['root_id','event_id','family_id','product_id','epoch','date','side','qty','reference_price','fill_price','entry_fill','multiplier','fee','slippage','realized_gross','margin_rate','risk_per_lot','budget_id','reason'],'positions.csv.gz':['root_id','date','family_id','epoch','qty','entry_fill','entry_reference','mark','multiplier','margin_rate','risk_per_lot','SL0','boundary_next','unrealized','notional','stale_days','mark_state'],'closed.csv.gz':['root_id','net_pnl','exit_date','entry_date'],'open.csv.gz':['root_id','qty','state']}
    def get(path):
        path=Path(path).resolve();key=str(path)
        if key not in cache:
            assert key in bindings,('unbound ledger read',key);frame=table(bindings[key])
            if frame.empty:
                for c in required.get(path.name,[]):
                    if c not in frame:frame[c]=pd.Series(dtype=str)
            cache[key]=frame
        return cache[key].copy(deep=True)
    def diag_read(folder,name):
        frame=pd.read_csv(io.StringIO(get(folder/(name+'.csv.gz')).to_csv(index=False)),dtype={'date':str,'year':str,'family_id':str},float_precision='round_trip')
        for col in ('qty','multiplier','fill_price','fee','slippage','realized_gross','net_pnl','unrealized','notional'):
            if col in frame:frame[col]=pd.to_numeric(frame[col],errors='raise')
        return frame
    cash.csv,diag._read=get,diag_read
    try:yield cache
    finally:cash.csv,diag._read=saved_csv,saved_read


def review_books(p,cm,signals,mothers,store,economics,execution,out,r,cash,diag):
    specs={(a['arm'],a['window'],a['cost']):a for a in cm['accounts']};assert len(specs)==8 and set(specs)=={(a,w,c) for a in ARMS for w in WINDOWS for c in COSTS}
    reports=read_json(cm['diagnostics']);family=table(cm['family_year_including_zero']);numeric(family,['net_equity_contribution','fee','slippage','fill_count','filled_qty'])
    annual,summtab,capacity,groups,years=[table(cm[n]) for n in ('annual_slices','account_summaries','capacity_summary','sector_variant_attribution','sector_variant_year_including_zero')]
    tails=read_json(cm['largest_wins_losses']);families=sorted(mothers.family_id.unique());assert len(families)==95
    metrics,daily,logs={}, {}, {};reviewed=[];newfamily=[];yearrows=0
    for key in [(a,w,c) for a in ARMS for w in WINDOWS for c in COSTS]:
        arm,w,c=key;spec=specs[key];name=f'NARROW_{arm}_{w}_{c}';folder=Path(spec['directory']);signal=signals[arm]
        assert spec['account_id']==name and folder==Path(cm['terminal']['path']).parent/name and set(spec['ledgers'])==set(reuse().LEDGERS)
        for role,b in spec['ledgers'].items():assert Path(b['path'])==folder/(role+'.csv.gz')
        with ledger_cache(spec,cash,diag):
            summary=read_json(spec['summary']);raw_checkpoint=read_json(spec['checkpoint']);raw_summary=read_json(raw_checkpoint['kernel_summary']);fields(summary,raw_summary,'raw book summary preserved in final report');assert Path(spec['summary']['path'])==folder/'summary.json';bounds=p['cash']['windows'][w];assert bounds==execution['cash']['windows'][w]
            with reuse().cash_context(r,cash,cash.csv(folder/'positions.csv.gz')):
                checked=cash.review_account(folder,c,dict(id=w,start=bounds[0],end=bounds[1]),execution,signal,economics,store.calendar,.25)
                native=r.account_native_and_capacity(folder,signal,mothers,store,economics,summary,c)
            roots=pd.concat([cash.csv(folder/'closed.csv.gz'),cash.csv(folder/'open.csv.gz')],ignore_index=True).set_index('root_id')
            sigmap=signal.to_dict('index')
            for root in roots.to_dict('index').values():reuse().check_root_boundary(root,sigmap)
            saved_fy=family.loc[family.arm.eq(arm)&family.window.eq(w)&family.cost.eq(c)]
            d,log,numbers,fy=diag._account(folder,summary,reports[name],saved_fy,families);diag._daily_summary(d,summary,1000000.)
            ar=annual.loc[annual.account.eq(name)].sort_values('year');assert len(ar)==len(reports[name]['annual_slices'])
            for got,want in zip(ar.to_dict('records'),reports[name]['annual_slices']):fields(got,want,'all8 annual slices')
            row=summtab.loc[summtab.account.eq(name)];assert len(row)==1;fields(row.iloc[0].to_dict(),{k:v for k,v in summary.items() if not isinstance(v,(dict,list))},'all8 metric table')
            cap=capacity.loc[capacity.account.eq(name)];assert len(cap)==1;fields(cap.iloc[0].to_dict(),{k:summary[k] for k in ('execution_unknown','unknown_capacity_fills','capacity_unknown_roots','entry_execution_unknown')},'all8 capacity rows')
            fills=cash.csv(folder/'fills.csv.gz');gap=[]
            for fill in fills.loc[fills.side.eq('SELL')&fills.reason.eq('gap_stop')].to_dict('records'):
                root=roots.loc[fill['root_id']];loss=(float(root.entry_reference)-float(fill['reference_price']))/(.25*signal.loc[fill['event_id'],'N_u']);gap.append(dict(event_id=fill['event_id'],date=fill['date'],gross_loss_R=loss,qty=int(float(fill['qty'])),realized_gross=float(fill['realized_gross']),exit_fee=float(fill['fee'])))
            nested(reports[name]['gap_stop_fills'],gap,'all8 uncapped gap fills');assert reports[name]['gap_stop_exceeds_1R']==sum(g['gross_loss_R']>1 for g in gap)
            assert summary['any_historical_stale']==bool(numbers['stale_days']>0)
            extra=reuse().extra_book_checks(folder,name,summary,groups,tails[name],years,cash,d);yearrows+=extra['sector_variant_year_rows']
            report=dict(account_id=name,ledger=checked,native=native,diagnostics=numbers,extra_reports=extra,root_effective_expiry_checked=len(roots),summary=summary)
            progress(out,'book_'+name,report);reviewed.append(report);metrics[key],daily[key],logs[key]=summary,d,log;newfamily.append(fy.assign(arm=arm,window=w,cost=c))
    names={a['account_id'] for a in reviewed};assert set(reports)==set(tails)==set(summtab.account)==set(capacity.account)==names
    assert len(summtab)==len(capacity)==8 and len(groups)==32 and len(years)==yearrows
    expected=pd.concat(newfamily,ignore_index=True);keys=['arm','window','cost','family_id','year'];measures=['net_equity_contribution','fee','slippage','fill_count','filled_qty']
    # Review158 frame comparison coerces numeric values; year type must agree.
    family['year']=family.year.astype(str);expected['year']=expected.year.astype(str)
    reuse().frame_values(family,expected,keys,measures,'all8 full family/year grid')
    reuse().frame_values(table(cm['family_total_including_zero']),expected.groupby(keys[:-1])[measures].sum().reset_index(),keys[:-1],measures,'all8 full family totals')
    result=dict(books_reviewed=8,family_year_rows=len(expected),sector_variant_rows=len(groups),sector_variant_year_rows=yearrows,all_full_canonical_anchors_checked=True,book_replays=0)
    progress(out,'books_review',result);return metrics,daily,logs,reviewed,result


def fixed_gate(points,held,stale,positive_wealth,execution_unknown):
    assert set(points)=={(w,c) for w in WINDOWS for c in COSTS}
    own=all(finite(p['active_total_return_pct']) and p['active_total_return_pct']>0 for p in points.values())
    def threshold(field):return all(finite(p[field]) and (p[field]>0 if k==('primary_2020','stress') else p[field]>=0) for k,p in points.items())
    ret=threshold('return_percentage_point_difference');ddknown=all(finite(p['drawdown_percentage_point_difference']) for p in points.values());dd=threshold('drawdown_percentage_point_difference');ci=finite(points['primary_2020','stress']['ci95_low']) and points['primary_2020','stress']['ci95_low']>0
    hg=[held['groups'][g] for g in ('holdout_0','holdout_1')];hn=all(finite(g['known_u_equal_mean_increment_R']) and g['known_u_equal_mean_increment_R']>=0 and g['nominal_pass'] is True for g in hg);hu=any(g['unknown_differential_selected_events']>0 or g['status']=='unknown' for g in hg)
    cash=bool(own and ret and ddknown and dd and ci and positive_wealth);unknown=bool(not ddknown or stale or execution_unknown)
    status='unknown_control_drawdown' if not ddknown else 'unsupported' if not(cash and hn) else 'unknown_historical_stale' if stale else 'unknown_execution_capacity_or_entry' if execution_unknown else 'unknown_differential_held_outcome' if hu else 'supported_limited_reconstruction_model_only'
    return dict(status=status,cash_nominal_pass=cash,held_known_nominal_pass=bool(hn),nominal_pass=bool(cash and hn and not hu and not unknown),own_returns_positive_all_four=bool(own),return_gate=bool(ret),drawdown_gate=bool(dd),primary_daily_log_CI_lower_positive=bool(ci),actual_wealth_positive=bool(positive_wealth),financial_unknown=unknown,held_signal_unknown=bool(hu),execution_unknown=bool(execution_unknown),any_historical_stale=bool(stale),held_diagnostic_is_K_cash_target=False,unchanged_training_target=True,fixed_algorithm_information_increment_under_shared_K_only=True,strict_first_release_PIT_established=False,independent_actual_review_required=True,no_automatic_promotion=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False)


def review_comparisons(p,cm,metrics,daily,logs,reviewed,held,execution,out):
    comp=table(cm['comparisons']);dist=table(cm['bootstrap_distributions']);assert len(comp)==4 and not comp.duplicated(['window','cost']).any() and comp.contrast.eq('REGISTRATION54_minus_CONTROL54').all()
    assert len(dist)==2000 and set(dist)=={w+'_'+c+'_REGISTRATION54_minus_CONTROL54' for w in WINDOWS for c in COSTS};points={}
    for w in WINDOWS:
        same(cm['bootstrap_indices'][w],p['statistics']['indices'][w]);indices=np.load(verify(p['statistics']['indices'][w]),allow_pickle=False)
        for c in COSTS:
            key=(w,c);ak,ck=(ARMS[1],w,c),(ARMS[0],w,c);active,control=metrics[ak],metrics[ck]
            assert daily[ak].date.tolist()==daily[ck].date.tolist() and indices.shape==(2000,len(daily[ak]))
            val,distribution=reuse().paired(logs[ak],logs[ck],indices);known=finite(active['max_drawdown_pct']) and finite(control['max_drawdown_pct'])
            val.update(active_arm=ARMS[1],reference_arm=ARMS[0],active_total_return_pct=active['total_return_pct'],reference_total_return_pct=control['total_return_pct'],return_percentage_point_difference=active['total_return_pct']-control['total_return_pct'],drawdown_percentage_point_difference=active['max_drawdown_pct']-control['max_drawdown_pct'] if known and control['fills'] else None,dd_comparison_state='unknown_drawdown' if not known else 'NA_empty_reference' if control['fills']==0 else 'active_reference',identification='all_empty_unidentified' if active['fills']==control['fills']==0 else 'observed_cash_comparison',active_log_status='valid' if logs[ak] is not None else 'survival_failure_no_log_repair',control_log_status='valid' if logs[ck] is not None else 'survival_failure_no_log_repair',bootstrap_repetitions=2000,block_length=252,indices_regenerated=False,epsilon_log_repair=False)
            row=comp.loc[comp.window.eq(w)&comp.cost.eq(c)];assert len(row)==1;fields(row.iloc[0].to_dict(),val,'all four new paired statistics')
            compare(pd.to_numeric(dist[w+'_'+c+'_REGISTRATION54_minus_CONTROL54'].replace('',np.nan)),distribution,'all four original070 distributions',atol=1e-12);points[key]=val
    stale=any(r['diagnostics']['stale_days']>0 for r in reviewed);unknown=any(v['execution_unknown'] for v in metrics.values());positive=all(v is not None for v in logs.values())
    gate=fixed_gate(points,held,stale,positive,unknown);nested(read_json(cm['continuation_gate']),gate,'entire fixed189 gate')
    fields(read_json(cm['signal_identification']),dict(full_mother_rows=399252,full_main_parent_rows_per_arm=161014,canonical_from_full_original_mothers=True,filter_full_domain_before_argmax=True,old_selection_used_as_admission_gate=False,future_label_state_used_as_admission_gate=False,local_B_schema_alias_only=True,old_global_ARMS_changed=False,held_diagnostic_is_K_cash_target=False),'full population disclosure')
    disclosure=read_json(cm['budget_and_tick_disclosure']);fields(disclosure,dict(policy='NARROW',bootstrap_indices_regenerated=False,fees_already_in_cash=True,slippage_in_fill_price_already=True,slippage_deducted_again=False,no_gap_loss_cap=True,no_actual_orderbook_execution_proof=True,legal_clearance_proved=False,source_archive_is_final_reconstruction=True,held_diagnostic_is_K_cash_target=False,old_cash_control_used=False,ordinary_F_and_financial_commodity_retained=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False),'cash limits')
    nested(disclosure['budget'],p['cash'],'fixed189 budget');nested(disclosure['capacity'],execution['cash']['capacity'],'fixed128 capacity');nested(disclosure['anchor'],execution['anchor_and_execution'],'fixed128 anchors');nested(disclosure['bootstrap_indices'],p['statistics']['indices'],'exact070 indices')
    result=dict(comparisons_checked=4,bootstrap_repetitions=2000,indices_regenerated=False,points=[dict(window=w,cost=c,**v) for (w,c),v in points.items()],gate=gate,all8_actual_wealth_positive=positive,conditional_CI_not_independent_OOS=True)
    progress(out,'confidence_and_gate_review',result);return result


def authorize(args):
    out=Path(args.output).resolve();assert not out.exists(),'fresh Stage192 review output required'
    assert LINE/'outputs/stage192_registration_review' in out.parents
    inputs={k:binding(getattr(args,k)) for k in ('protocol','fit_manifest','cash_manifest')};assert inputs['protocol']['sha256']==PROTOCOL_SHA
    ab=binding(args.authorization);assert ab['sha256']==args.authorization_sha256;auth=read_json(ab)
    fields(auth,dict(schema='stage192_exact_root_review_authorization_v1',authorized_by='root',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out)),'root review authorization')
    nested(auth['input_bindings'],inputs,'exact review inputs');assert sorted(auth['source_bundle'],key=lambda b:b['path'])==bundle()
    return out,inputs,ab


def review(args):
    out,inputs,ab=authorize(args);out.mkdir(parents=True,exist_ok=False);began=time.monotonic();before=bundle()
    receipt=dict(schema='stage192_registration_independent_review_v1',completed=False,C=0,I=0,M=0,errors=[],inputs=inputs,authorization=ab,source_bundle=before,new_fit=0,new_cash=0,SQL=0,downloads=0,whole_database_hashes=0,strategy_replays=0,source_q_recalculations=0,author190_or191_imported=False,automatic_retry=False,python=sys.executable,numpy_version=np.__version__,pandas_version=pd.__version__)
    write(out/'started.json',dict(status='started',started_at=datetime.now(timezone.utc).isoformat(),source_bundle=before,inputs=inputs,automatic_retry=False))
    try:
        p,fm,cm=input_closure(inputs,out);r,cash,diag=reuse().helpers()
        a,m,common,q,calendar,columns,execution=load_data(p,out)
        choices,held,bounds,models=review_models(p,fm,a,m,common,q,calendar,columns,out,r);receipt['models']=models
        del common,q
        store,economics,econ_binding=cached_store(p,calendar,r);same(cm['economic_projection'],econ_binding)
        signals,signal_report=review_signals(p,cm,choices,a,bounds,store,economics,out,r);receipt['signals']=signal_report;del a
        metrics,daily,logs,books,grids=review_books(p,cm,signals,m,store,economics,execution,out,r,cash,diag);receipt['books']=books;receipt['grids']=grids
        receipt['confidence']=review_comparisons(p,cm,metrics,daily,logs,books,held,execution,out)
        assert bundle()==before,'review source/helper changed'
        for b in inputs.values():same(binding(b['path']),b)
        for role in ('actions','common','mothers','projection_actions'):assert stat_identity(p['source_bindings'][role])==fm['input_evidence'][role]['stat_after']
        assert all(DISK_READS[b['path']]==1 for b in (p['source_bindings'][r] for r in ('actions','mothers','common','projection_actions','native_cache'))),('one disk read of accepted large inputs',dict(DISK_READS))
        assert all(tuple(b[k] for k in ('path','bytes','sha256')) in VERIFIED and DISK_READS[b['path']]==1 for b in NEW_CSV_BINDINGS.values()),('every new CSV hashed during exactly one data pass',dict(DISK_READS))
        receipt['disk_data_reads']=dict(DISK_READS)
        receipt['maximum_numeric_errors']=dict(ERRORS);receipt['accepted132_numeric_errors']=dict(r.ERRORS);receipt['accepted158_numeric_errors']=dict(reuse().ERRORS)
        receipt.update(completed=True,research_arithmetic_accepted=True,new_models_reviewed=12,new_financial_books_reviewed=8,cumulative_fit=421,cumulative_cash=226,conditional_reconstruction_only=True,strict_first_release_PIT_established=False,production_qualified=False,increased_betting_qualified=False,goal_complete=False)
    except BaseException as exc:
        receipt['I']=1;receipt['errors'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()));raise
    finally:
        receipt['elapsed_seconds']=time.monotonic()-began;write(out/'receipt.json',receipt)
        write(out/'terminal.json',dict(status='completed' if receipt['completed'] else 'failed',exit_code=0 if receipt['completed'] else 1,completed=receipt['completed'],elapsed_seconds=receipt['elapsed_seconds'],automatic_retry=False,new_fit=0,new_cash=0,SQL=0,completed_checkpoints_retained=True))
        print(json.dumps(dict(completed=receipt['completed'],C=receipt['C'],I=receipt['I'],M=receipt['M'],output=str(out))),flush=True)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','fit-manifest','cash-manifest','authorization','authorization-sha256','output'):parser.add_argument('--'+name,required=True)
    review(parser.parse_args())


if __name__=='__main__':main()
