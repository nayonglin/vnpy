"""One independent new156 selection/new157 cash audit; no author imports/replay.

Only root launches actual review after binding this source and the six fixtures.
Old accepted132 pure accounting and bar checks are reused without calling any
model, label, SQL, dataset-review or strategy-replay entry point.
"""
from __future__ import annotations
import argparse
from bisect import bisect_left
from collections import Counter
from contextlib import contextmanager
import csv
from datetime import date, timedelta, datetime, timezone
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

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL_SHA = '7ec4f92b31b46b04e0a17812878acb7f6305c9c476f9350d84bb7d873fe11e47'
CLARIFIER_SHA = 'cffb443b6368439251012db1c9c01def169d8105c5769ee81e7a9252c5f63eac'
HELPERS = {'stage132_contract_choice_review.py':'7d8b5fd1c1a2d80d2df32632c8b097e9ca15eced9e65de745af40f1e32a3a181',
    'stage102_cash_adapter.py':'702ad195d988eec4d847289ad9961525a35e65d4146de796073b1ca3c0df9044',
    'stage102_cash_core.py':'4310bdd81375e17406b1773658c582ccb570a25d09b8fa53d15461c76cbb3eaa',
    'stage102_cash_diagnostics.py':'0075f91ba110ea902ee374a917f20433ace66afde9bde755088f2573d09d11cc'}
ARM = 'VOLUNTARY_RESELECT'
POLICY = 'stage155_voluntary_reselect_lead_months_1_v1_not_certified'
WINDOWS, COSTS = ('primary_2020','cold_2023'), ('base','stress')
IDENTITY = ['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
SCORES = ['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible','score','scope','cutoff']
LEDGERS = ('daily','fills','positions','reservations','rejections','closed','open','capacity_audit','entry_execution_unknown')
VERIFIED, ERRORS = set(), {}


def binding(path):
    p=Path(path).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())


def same(a,b):
    assert all(a.get(k)==b.get(k) for k in ('path','bytes','sha256')),('binding differs',a,b)


def verify(b):
    key=tuple(b[k] for k in ('path','bytes','sha256'))
    if key not in VERIFIED:same(binding(b['path']),b);VERIFIED.add(key)
    return Path(b['path'])


def read_json(b):return json.loads(verify(b).read_text())


def table(b,usecols=None):
    return pd.read_csv(verify(b),dtype=str,keep_default_na=False,usecols=usecols,float_precision='round_trip')


def numeric(frame,columns):
    for k in columns:
        if k in frame:frame[k]=pd.to_numeric(frame[k].replace('',np.nan),errors='raise')
    return frame


def integer(x):
    v=float(x);assert math.isfinite(v) and v.is_integer() and not isinstance(x,bool),('integer',x)
    return int(v)


def flag(x):
    assert str(x).lower() in ('true','false','1','0'),('boolean',x)
    return str(x).lower() in ('true','1')


def finite(x):
    try:return not isinstance(x,(bool,np.bool_)) and math.isfinite(float(x))
    except(TypeError,ValueError):return False


def compare(a,b,label,atol=2e-7,rtol=2e-10):
    x,y=np.asarray(a,float),np.asarray(b,float)
    assert x.shape==y.shape and np.array_equal(np.isnan(x),np.isnan(y)),(label,'shape/null')
    assert np.array_equal(np.isfinite(x),np.isfinite(y)),(label,'finite')
    z=np.isfinite(x)&np.isfinite(y);err=np.abs(x[z]-y[z]);m=float(err.max()) if err.size else 0.
    ERRORS[label]=max(ERRORS.get(label,0.),m)
    assert np.all(err<=atol+rtol*np.abs(y[z])),(label,m)


def scalar_compare(got,want,label,atol=1e-8,rtol=2e-9):
    a=float(got) if got!='' else math.nan;b=float(want)
    assert math.isnan(a)==math.isnan(b),(label,'null')
    assert math.isfinite(a)==math.isfinite(b),(label,'finite')
    if math.isfinite(a):
        err=abs(a-b);ERRORS[label]=max(ERRORS.get(label,0.),err)
        assert err<=atol+rtol*abs(b),(label,err,a,b)


def fields(got,want,label):
    for k,v in want.items():
        assert k in got,(label,'missing',k)
        a=got[k]
        if isinstance(v,(bool,np.bool_)):assert flag(a)==v,(label,k,a,v)
        elif v is None:assert a is None or a=='' or (isinstance(a,float) and math.isnan(a)),(label,k,a)
        elif isinstance(v,(int,float,np.number)):scalar_compare(a,v,label+'.'+k)
        else:assert a==v,(label,k,a,v)


def nested(got,want,label):
    if isinstance(want,dict):
        assert isinstance(got,dict) and set(got)==set(want),(label,'keys',set(got)^set(want))
        for k,v in want.items():nested(got[k],v,label+'.'+k)
    elif isinstance(want,list):
        assert isinstance(got,list) and len(got)==len(want),(label,'length')
        for i,(a,b) in enumerate(zip(got,want)):nested(a,b,label+'.'+str(i))
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


def progress(out,name,x):
    write(out/(name+'.json'),x);print(json.dumps(dict(phase=name,completed=True)),flush=True)


def bundle():
    return sorted([binding(TOOLS/n) for n in ('stage158_voluntary_review.py','test_stage158_voluntary_review.py',*HELPERS)],key=lambda b:b['path'])


def deadline(epoch,calendar,sample_end):
    month=epoch.rsplit('.',1)[-1]
    assert len(month)==6 and month.isdigit(),('complete nominal month',epoch)
    first=date(int(month[:4]),int(month[4:]),1)
    previous=(first-timedelta(days=1)).replace(day=1).isoformat()
    i=bisect_left(calendar,previous)
    if previous<calendar[0]:state,k,day='before_calendar_blocked',None,None
    elif i==len(calendar):state,k,day='after_calendar_pending',None,None
    else:state,k,day='in_calendar',i,calendar[i]
    return dict(K_target_date=previous,K_index=k,K_date=day,K_state=state,K_after_sample_end=(day or previous)>sample_end)


def admission(u,original,score,b,calendar,sample_end):
    positive=integer(original)==1 and finite(score) and float(score)>0
    D=u+1 if u+1<len(calendar) else None;day=calendar[D] if D is not None else None
    if b['K_state']=='before_calendar_blocked':gate,state=False,'K_before_calendar_blocked'
    elif D is None:gate,state=None,'next_source_session_unknown'
    elif b['K_index'] is None:gate,state=day<b['K_target_date'],'K_after_calendar_D_before_target'
    else:gate=D<b['K_index'];state='D_before_K' if gate else 'D_on_or_after_K'
    return dict(D_index=D,D_date=day,D_state='unknown' if day is None else 'after_sample_end' if day>sample_end else 'in_sample_calendar',
        original_positive_eligible=int(positive),new_eligible=None if positive and gate is None else int(positive and gate is True),
        eligibility_state=state if positive else 'original_ineligible_or_nonpositive_score')


def action_order(a):return (-float(a['score']),a['reference_epoch'],a['action_id'])


def family_choices(proposals):
    groups={}
    for a in proposals:
        group=(a['family_id'],integer(a['u_index']))
        rank=(a['product_id'].endswith('_F'),a['product_id'],a['reference_epoch'],a['action_id'])
        if group not in groups or rank<groups[group][0]:groups[group]=(rank,a)
    return {integer(a['mother_sequence_index']):a for _,a in groups.values()}


def effective_boundary(source,b,D):
    k=b['K_index']
    if k is None:
        assert b['K_state']=='after_calendar_pending'
        return source,'source_lifecycle'
    assert D<k,('entry on or after voluntary K',D,k)
    return min(source,k),'same_source_and_voluntary' if source==k else 'source_lifecycle' if source<k else 'voluntary_calendar'


def check_root_boundary(root,signals):
    signal=signals[root['event_id']]
    assert integer(root['expiry'])==integer(signal['lifecycle_index']),('root effective expiry',root['event_id'])


def paired(active,control,indices):
    if active is None or control is None:
        return dict(status='survival_failure_no_log_repair',mean_daily_log_difference=None,cumulative_log_difference=None,ci95_low=None,ci95_high=None),np.full(len(indices),np.nan)
    delta=np.asarray(active,float)-np.asarray(control,float)
    assert len(delta)==indices.shape[1] and indices.dtype.kind in 'iu' and indices.min()>=0 and indices.max()<len(delta)
    dist=np.mean(delta[indices],axis=1)
    return dict(status='valid',mean_daily_log_difference=float(np.mean(delta)),cumulative_log_difference=float(np.sum(delta)),ci95_low=float(np.quantile(dist,.025)),ci95_high=float(np.quantile(dist,.975))),dist


def rows(b):
    with gzip.open(verify(b),'rt',newline='') as f:yield from csv.DictReader(f)


def artifact(m,name):
    found=[b for b in m['artifacts'] if b.get('logical_name')==name or Path(b['path']).name==name]
    assert len(found)==1,('artifact',name,len(found))
    return found[0]


def helpers():
    for n,h in HELPERS.items():assert binding(TOOLS/n)['sha256']==h,('accepted helper changed',n)
    if str(TOOLS) not in sys.path:sys.path.insert(0,str(TOOLS))
    spec=importlib.util.spec_from_file_location('review158_accepted132_math',TOOLS/'stage132_contract_choice_review.py')
    r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    cash,diag=r.independent_helpers();return r,cash,diag


@contextmanager
def cash_context(r,cash,positions):
    old=(r.CASH_HELPER,r.ACTIVE_POSITIONS,cash.review_budgets)
    r.CASH_HELPER,r.ACTIVE_POSITIONS,cash.review_budgets=cash,positions,r.review_capped_budgets
    try:yield
    finally:r.CASH_HELPER,r.ACTIVE_POSITIONS,cash.review_budgets=old


def review_selection(protocol,choice,calendar,out):
    src=protocol['source_bindings'];full=numeric(table(src['mothers'],IDENTITY),['sequence_index','u_index'])
    assert len(full)==399252 and full.sequence_index.tolist()==list(range(399252)) and full.event_id.is_unique
    assert full.product_id.nunique()==98 and full.family_id.nunique()==95
    forward=full.loc[full.u_date.between('2020-01-01','2026-10-16')]
    assert len(forward)==161014
    parents=forward.set_index('sequence_index',drop=False).to_dict('index')
    counts,folds=Counter(),Counter();old,new,bounds,observed={},{},{},set();ids,seqs=set(),set()
    audit=iter(rows(choice['artifacts']['action_eligibility']))
    for raw in rows(src['child_scores']):
        if raw['scope']!='main':counts['non_main_rows_not_selected']+=1;continue
        seq=integer(raw['sequence_index']);pseq=integer(raw['mother_sequence_index']);u=integer(raw['u_index']);p=parents[pseq]
        assert seq not in seqs and raw['action_id'] not in ids
        seqs.add(seq);ids.add(raw['action_id']);observed.add(pseq)
        assert integer(raw['u_action_eligible']) in (0,1) and calendar[u]==raw['u_date']
        fields(raw,{k:p[k] for k in ('product_id','family_id','u_date','u_index')},'child complete identity')
        fields(raw,dict(mother_event_id=p['event_id'],anchor_epoch=p['reference_epoch'],cutoff='2020-01-01' if raw['u_date']<'2023-01-01' else '2023-01-01'),'child original anchor/fold')
        epoch=raw['reference_epoch'];assert epoch.rsplit('.',1)[0]==raw['product_id']
        if epoch not in bounds:bounds[epoch]=deadline(epoch,calendar,'2026-10-16')
        b=bounds[epoch];a=admission(u,raw['u_action_eligible'],raw['score'],b,calendar,'2026-10-16')
        saved=next(audit);fields(saved,{k:raw[k] for k in SCORES},'every original main score field')
        fields(saved,dict(action_sequence_index=seq,**b,**a),'every prospective main eligibility')
        counts['main_actions']+=1;folds[raw['cutoff']]+=1
        counts['original_positive_eligible_actions']+=a['original_positive_eligible']
        counts['new_eligible_actions']+=a['new_eligible']==1;counts['unknown_eligible_actions']+=a['new_eligible'] is None
        counts['reason:'+a['eligibility_state']]+=1
        if a['original_positive_eligible'] and (pseq not in old or action_order(raw)<action_order(old[pseq])):old[pseq]=raw
        if a['new_eligible']==1 and (pseq not in new or action_order(raw)<action_order(new[pseq])):new[pseq]=raw
    assert next(audit,None) is None,'no extra eligibility rows'
    assert counts['main_actions']==counts['non_main_rows_not_selected']==966740
    oldwin,newwin=family_choices(old.values()),family_choices(new.values())
    saved=table(choice['artifacts']['choices_main']);assert len(saved)==161014 and saved.event_id.is_unique
    differences,parentstates,parentfold,selectedfold,oldfold=Counter(),Counter(),Counter(),Counter(),Counter()
    for got,(seq,p) in zip(saved.to_dict('records'),sorted(parents.items())):
        proposal,winner,previous=new.get(seq),newwin.get(seq),oldwin.get(seq)
        state='selected' if winner else 'family_priority_suppressed' if proposal else 'no_observed_children' if seq not in observed else 'no_calendar_eligible_positive_action' if seq in old else 'no_original_eligible_positive_action'
        cutoff='2020-01-01' if p['u_date']<'2023-01-01' else '2023-01-01'
        want=dict(p,proposed_action_id=proposal['action_id'] if proposal else '',proposed_epoch=proposal['reference_epoch'] if proposal else '',proposed_score=float(proposal['score']) if proposal else None,
            chosen_action_id=winner['action_id'] if winner else '',chosen_action_sequence_index=integer(winner['sequence_index']) if winner else -1,chosen_epoch=winner['reference_epoch'] if winner else '',anchor_epoch=p['reference_epoch'],score=float(winner['score']) if winner else None,
            selected=int(winner is not None),selection_state=state,scope='main',cutoff=cutoff,arm=ARM,policy='NARROW',old_chosen_action_id=previous['action_id'] if previous else '',old_chosen_epoch=previous['reference_epoch'] if previous else '',voluntary_policy_version=POLICY,account_deadline_certified=False)
        fields(got,want,'every complete parent choice')
        oldid,newid=want['old_chosen_action_id'],want['chosen_action_id']
        change='unchanged' if oldid==newid else 'newly_selected' if not oldid else 'removed' if not newid else 'different_action'
        differences[(cutoff,change)]+=1;parentstates[state]+=1;parentfold[cutoff]+=1
        if winner:selectedfold[cutoff]+=1
        if previous:oldfold[cutoff]+=1
    assert dict(parentfold)=={'2020-01-01':71344,'2023-01-01':89670}
    doc=read_json(choice['artifacts']['boundaries']);nested(doc['epochs'],bounds,'all full-calendar boundaries')
    assert doc['account_deadline_certified'] is False and doc['sample_end']=='2026-10-16'
    counts.update(parent_rows=len(saved),selected_parent_rows=len(newwin),old_selected_parent_rows_reconstructed_from_same_scores=len(oldwin),changed_parent_choices=sum(n for (c,state),n in differences.items() if state!='unchanged'))
    summary=read_json(choice['artifacts']['summary'])
    nested(summary['counts'],dict(counts),'all choice counters');nested(summary['main_actions_per_cutoff'],dict(folds),'all choice fold counters')
    for key,value in [('parent_states',parentstates),('parents_per_cutoff',parentfold),('selected_per_cutoff',selectedfold),('old_selected_per_cutoff',oldfold)]:nested(summary[key],dict(value),'choice summary '+key)
    nested(summary['selection_differences'],[dict(cutoff=k[0],state=k[1],parents=v) for k,v in sorted(differences.items())],'all choice differences')
    report=dict(full_original_mothers=399252,full_forward_parents=161014,full_main_children=966740,non_main_rows_not_selected=966740,full_calendar_days=len(calendar),calendar_first=calendar[0],calendar_last=calendar[-1],boundaries=len(bounds),counts=dict(counts),parent_states=dict(parentstates),selection_differences=summary['selection_differences'],all_parent_rows_retained=True,full_pool_filter_before_argmax=True,author_selection_imported=False,old_fit_reaudited=False,new_fit=0)
    progress(out,'selection_review',report)
    return full,numeric(saved,['sequence_index','u_index','selected','chosen_action_sequence_index','score']),bounds,report


def cached_store(protocol,execution,clarifier,r):
    # The accepted NPZ has no calendar. Never stat/hash/open the native DB.
    bridge,calendar=r.calendar_from_protocol(execution)
    same(bridge['calendar'],clarifier['calendar_binding'])
    src=protocol['source_bindings'];meta=read_json(src['native_cache_json'])
    same(meta['file'],src['native_cache_file'])
    assert meta['schema']=='stage132_native_store_recovery_cache_v1' and meta['native_rows']==1552456 and meta['native_epochs']==9520
    store=r.NativeBars(calendar)
    with np.load(verify(src['native_cache_file']),allow_pickle=False) as z:
        assert 'calendar' not in z.files
        epochs=z['epochs'].tolist();offsets=z['offsets'];arrays={k:z[k] for k in ('days','values','accepted','valid','N','low20','run')}
        assert len(epochs)==9520 and offsets[0]==0 and offsets[-1]==1552456
        for i,e in enumerate(epochs):store.series[e]={k:v[int(offsets[i]):int(offsets[i+1])] for k,v in arrays.items()}
    economics=read_json(bridge['economic_projection'])['instruments'];assert set(economics)==set(store.series)
    return store,economics


def review_signals(protocol,manifest,choices,boundaries,store,economics,r,out):
    picked=choices.loc[choices.selected.eq(1)];ids=set(picked.chosen_action_id)
    columns=['action_id','action_sequence_index','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close']
    chunks=[]
    for chunk in pd.read_csv(verify(protocol['source_bindings']['actions']),usecols=columns,dtype=str,keep_default_na=False,chunksize=100000,float_precision='round_trip'):
        part=chunk.loc[chunk.action_id.isin(ids)]
        if len(part):chunks.append(part)
    actions=pd.concat(chunks,ignore_index=True);assert actions.action_id.is_unique and set(actions.action_id)==ids
    numeric(actions,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close'])
    actions=actions.set_index('action_id')
    saved=numeric(table(manifest['signals']),['action_sequence_index','u_index','D_index','label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index','entry_capacity_qty','u_gross_capacity_qty','potential','score','source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index'])
    assert saved.event_id.is_unique and saved.event_id.tolist()==picked.chosen_action_id.tolist()
    assert not saved.duplicated(['family_id','u_date']).any()
    lookup=saved.set_index('event_id',drop=False)
    origins=Counter()
    for c in picked.itertuples(index=False):
        a=actions.loc[c.chosen_action_id];epoch=a.reference_epoch;u=integer(a.u_index);j=store.locate(epoch,u)
        assert j is not None and store.series[epoch]['valid'][j] and a.u_action_eligible==1
        native=store.series[epoch];gross,entry=r.capacity(native['values'][j,4],economics[epoch]['round_lot'])
        assert native['run'][j]>=20 and entry>=economics[epoch]['round_lot'] and c.score>0
        source=r.lifecycle(epoch,economics[epoch],store.calendar);b=boundaries[epoch];effective,origin=effective_boundary(source,b,u+1)
        want=dict(mother_event_id=c.event_id,action_sequence_index=integer(a.action_sequence_index),product_id=a.product_id,family_id=a.family_id,u_date=a.u_date,u_index=u,D_index=u+1,reference_epoch=epoch,anchor_epoch=a.anchor_epoch,
            label_history_ready20=1,N_u=float(native['N'][j]),low20_u=float(native['low20'][j]),u_close=float(native['values'][j,3]),history_run=integer(native['run'][j]),lifecycle_index=effective,
            entry_capacity_qty=integer(entry),u_gross_capacity_qty=integer(gross),potential=1,score=float(c.score),arm=ARM,control_id=ARM,policy='NARROW',cutoff=c.cutoff,
            source_lifecycle_index=source,voluntary_boundary_index=b['K_index'],effective_lifecycle_index=effective,effective_boundary_origin=origin,K_target_date=b['K_target_date'],K_date=b['K_date'],K_state=b['K_state'])
        fields(lookup.loc[c.chosen_action_id].to_dict(),want,'every independent selected signal')
        assert a.mother_event_id==c.event_id and a.anchor_epoch==c.anchor_epoch and epoch==c.chosen_epoch
        assert integer(a.action_sequence_index)==integer(c.chosen_action_sequence_index)
        compare([a.N_u,a.low20_u,a.u_close,a.entry_capacity_qty],[want['N_u'],want['low20_u'],want['u_close'],entry],'accepted selected action causal data',atol=1e-10,rtol=1e-12)
        origins[origin]+=1
    trace=table(manifest['boundary_lineage']);assert trace.event_id.tolist()==saved.event_id.tolist()
    for got,want in zip(trace.to_dict('records'),saved[trace.columns].to_dict('records')):fields(got,want,'every boundary sidecar row')
    lookup['planned_execution_date']=[store.calendar[integer(u)+1] if integer(u)+1<len(store.calendar) else '' for u in lookup.u_index]
    report=dict(selected_signals=len(saved),all_selected_original_actions_checked=len(actions),all_own_causal_features_checked=True,all_source_voluntary_effective_boundaries_checked=True,boundary_origins=dict(origins),entry_on_K_forbidden=True,sample_end_clamping=False,full_original_canonical_owner='399252 mothers')
    progress(out,'signal_boundary_review',report)
    return lookup,report


def extra_book_checks(folder,account,summary,group_table,tails,year_table,cash,daily):
    closed,opened,fills,positions=[cash.csv(folder/(n+'.csv.gz')) for n in ('closed','open','fills','positions')]
    cash.numeric(closed,['net_pnl']);cash.numeric(opened,['realized_gross','entry_fees','exit_fees','unrealized'])
    cash.numeric(fills,['fee','slippage','realized_gross','qty']);cash.numeric(positions,['unrealized'])
    roots=[]
    for frame,isclosed in ((closed,True),(opened,False)):
        for row in frame.to_dict('records'):
            value=float(row['net_pnl']) if isclosed else math.fsum([float(row['realized_gross']),-float(row['entry_fees']),-float(row['exit_fees']),float(row['unrealized'])])
            roots.append(dict(root_id=row['root_id'],product_id=row['product_id'],closed=isclosed,value=value))
    expected=[];expected_year=[];date_index=daily.date.tolist();years=sorted(daily.date.str[:4].unique())
    for dimension,names in [('market_sector',('financial','commodity')),('product_variant',('ordinary','F'))]:
        for name in names:
            def group(p):return ('financial' if p.startswith('CFFEX.') else 'commodity') if dimension=='market_sector' else ('F' if p.endswith('_F') else 'ordinary')
            part=[r for r in roots if group(r['product_id'])==name];ids={r['root_id'] for r in part};cl=[r for r in part if r['closed']];op=[r for r in part if not r['closed']]
            f=fills.loc[fills.root_id.isin(ids)];p=positions.loc[positions.root_id.isin(ids)]
            record=dict(dimension=dimension,group=name,episodes=len(part),closed_episodes=len(cl),open_episodes=len(op),closed_net_pnl=math.fsum(r['value'] for r in cl),open_marked_net_pnl=math.fsum(r['value'] for r in op),net_equity_contribution=math.fsum(r['value'] for r in part),fees=float(f.fee.sum()),slippage_attribution=float(f.slippage.sum()),slippage_already_in_fill_price=True)
            row=group_table.loc[group_table.account.eq(account)&group_table.dimension.eq(dimension)&group_table.group.eq(name)];assert len(row)==1;fields(row.iloc[0].to_dict(),record,'all sector variant rows');expected.append(record)
            dayflow=f.groupby('date')[['realized_gross','fee','slippage']].sum().reindex(date_index,fill_value=0.)
            un=p.groupby('date').unrealized.sum().reindex(date_index,fill_value=0.).to_numpy(float)
            contrib=dayflow.realized_gross.to_numpy(float)-dayflow.fee.to_numpy(float)+np.diff(np.r_[0.,un])
            for year in years:
                mask=daily.date.str.startswith(year).to_numpy();annual_f=f.loc[f.date.str.startswith(year)]
                record=dict(account=account,window=summary['window'],cost=summary['cost'],dimension=dimension,group=name,year=year,net_equity_contribution=float(contrib[mask].sum()),fee=float(dayflow.fee.to_numpy(float)[mask].sum()),slippage=float(dayflow.slippage.to_numpy(float)[mask].sum()),fill_count=len(annual_f),filled_qty=integer(annual_f.qty.sum()),slippage_already_in_fill_price=True)
                row=year_table.loc[year_table.account.eq(account)&year_table.dimension.eq(dimension)&year_table.group.eq(name)&year_table.year.eq(year)];assert len(row)==1;fields(row.iloc[0].to_dict(),record,'all sector variant year zero grid');expected_year.append(record)
        compare(math.fsum(r['net_equity_contribution'] for r in expected if r['dimension']==dimension),summary['ending_equity']-1000000.,'sector variant equity bridge',atol=1e-5)
    cols=[c for c in ('root_id','event_id','product_id','family_id','epoch','entry_date','exit_date','net_pnl') if c in closed]
    for key,part in [('largest_wins',closed.loc[closed.net_pnl.gt(0)].nlargest(5,'net_pnl')),('largest_losses',closed.loc[closed.net_pnl.lt(0)].nsmallest(5,'net_pnl'))]:nested(tails[key],part[cols].to_dict('records'),'all new '+key)
    return dict(sector_variant_rows=len(expected),sector_variant_year_rows=len(expected_year),largest_wins=len(tails['largest_wins']),largest_losses=len(tails['largest_losses']))


def frame_values(got,want,keys,measures,label):
    a,b=got.set_index(keys).sort_index(),want.set_index(keys).sort_index()
    assert a.index.is_unique and b.index.is_unique and a.index.tolist()==b.index.tolist(),(label,'complete keys')
    for m in measures:compare(pd.to_numeric(a[m]),pd.to_numeric(b[m]),label+'.'+m)


def review_books(protocol,manifest,signals,mothers,store,economics,execution,out,r,cash,diag):
    books={(a['window'],a['cost']):a for a in manifest['accounts']}
    assert len(books)==len(manifest['accounts'])==4 and set(books)=={(w,c) for w in WINDOWS for c in COSTS}
    reports=read_json(manifest['diagnostics']);family=diag._read(verify(manifest['family_year_including_zero']).parent,'family_year_including_zero')
    annual,summtab,capacity,groups,years=[table(manifest[n]) for n in ('annual_slices','account_summaries','capacity_summary','sector_variant_attribution','sector_variant_year_including_zero')]
    tails=read_json(manifest['largest_wins_losses']);families=sorted(mothers.family_id.unique());metrics,daily,logs={}, {}, {};reviewed=[];newfamily=[];yearrows=0
    sigdict=signals.to_dict('index')
    for key in [(w,c) for w in WINDOWS for c in COSTS]:
        w,c=key;a=books[key];name=f'NARROW_{ARM}_{w}_{c}';folder=Path(a['directory'])
        assert a['account_id']==name and a['arm']==ARM and folder==Path(manifest['terminal']['path']).parent/name
        assert set(a['ledgers'])==set(LEDGERS)
        for role,b in a['ledgers'].items():assert Path(b['path'])==folder/(role+'.csv.gz');verify(b)
        summary=read_json(a['summary']);assert Path(a['summary']['path'])==folder/'summary.json'
        bounds=protocol['cash']['windows'][w];assert bounds==execution['cash']['windows'][w]
        schedule=dict(id=w,start=bounds[0],end=bounds[1])
        with cash_context(r,cash,cash.csv(folder/'positions.csv.gz')):
            checked=cash.review_account(folder,c,schedule,execution,signals,economics,store.calendar,.25)
            native=r.account_native_and_capacity(folder,signals,mothers,store,economics,summary,c)
        for n in ('closed','open'):
            for root in cash.csv(folder/(n+'.csv.gz')).to_dict('records'):check_root_boundary(root,sigdict)
        saved_fy=family.loc[family.arm.eq(ARM)&family.window.eq(w)&family.cost.eq(c)]
        d,log,numbers,fy=diag._account(folder,summary,reports[name],saved_fy,families);diag._daily_summary(d,summary,1000000.)
        part=annual.loc[annual.account.eq(name)].sort_values('year');assert len(part)==len(reports[name]['annual_slices'])
        for got,want in zip(part.to_dict('records'),reports[name]['annual_slices']):fields(got,want,'new annual slices')
        row=summtab.loc[summtab.account.eq(name)];assert len(row)==1;fields(row.iloc[0].to_dict(),{k:v for k,v in summary.items() if not isinstance(v,(dict,list))},'all new metric rows')
        cap=capacity.loc[capacity.account.eq(name)];assert len(cap)==1;fields(cap.iloc[0].to_dict(),{k:summary[k] for k in ('execution_unknown','unknown_capacity_fills','capacity_unknown_roots','entry_execution_unknown')},'all new capacity rows')
        fills=cash.csv(folder/'fills.csv.gz');roots=pd.concat([cash.csv(folder/'closed.csv.gz'),cash.csv(folder/'open.csv.gz')],ignore_index=True).set_index('root_id');gap=[]
        for f in fills.loc[fills.side.eq('SELL')&fills.reason.eq('gap_stop')].to_dict('records'):
            root=roots.loc[f['root_id']];loss=(float(root.entry_reference)-float(f['reference_price']))/(.25*signals.loc[f['event_id'],'N_u'])
            gap.append(dict(event_id=f['event_id'],date=f['date'],gross_loss_R=loss,qty=integer(f['qty']),realized_gross=float(f['realized_gross']),exit_fee=float(f['fee'])))
        nested(reports[name]['gap_stop_fills'],gap,'all new gap fills');assert reports[name]['gap_stop_exceeds_1R']==sum(g['gross_loss_R']>1 for g in gap)
        assert summary['any_historical_stale']==bool(numbers['stale_days']>0)
        extra=extra_book_checks(folder,name,summary,groups,tails[name],years,cash,d);yearrows+=extra['sector_variant_year_rows']
        report=dict(account_id=name,ledger=checked,native=native,diagnostics=numbers,extra_reports=extra,root_effective_expiry_checked=len(roots))
        progress(out,'book_'+name,report);reviewed.append(report)
        metrics[key],daily[key],logs[key]=summary,d,log;newfamily.append(fy.assign(arm=ARM,window=w,cost=c))
    assert set(reports)==set(tails)=={a['account_id'] for a in reviewed}
    assert len(summtab)==8 and len(capacity)==4 and len(groups)==16 and len(years)==yearrows
    # Old accepted B family/year is an identity reference, never a fill re-audit.
    baseline=read_json(manifest['input_bindings']['accepted_cash_manifest']);oldbind=artifact(baseline,'family_year_including_zero.csv.gz')
    same(manifest['control_family_year_source'],oldbind)
    old=diag._read(verify(oldbind).parent,'family_year_including_zero');old=old.loc[old.arm.eq('B')].copy();old['arm']='CONTROL_REUSED'
    keycols=['arm','window','cost','family_id','year'];measures=['net_equity_contribution','fee','slippage','fill_count','filled_qty']
    expected=pd.concat([*newfamily,old],ignore_index=True)
    frame_values(family,expected,keycols,measures,'all8 family/year including zero')
    frame_values(table(manifest['family_total_including_zero']),expected.groupby(keycols[:-1])[measures].sum().reset_index(),keycols[:-1],measures,'all8 family totals including zero')
    return metrics,daily,logs,reviewed,dict(full_family_year_rows=len(expected),sector_variant_year_rows=yearrows)


def fixed_gate(points,stale,positive_wealth,execution_unknown):
    assert set(points)=={(w,c) for w in WINDOWS for c in COSTS}
    own=all(finite(p['active_total_return_pct']) and p['active_total_return_pct']>0 for p in points.values())
    def passed(field):
        return all(finite(p[field]) and (p[field]>0 if key==('primary_2020','stress') else p[field]>=0) for key,p in points.items())
    ret,dd=passed('return_percentage_point_difference'),passed('drawdown_percentage_point_difference')
    ci=finite(points[('primary_2020','stress')]['ci95_low']) and points[('primary_2020','stress')]['ci95_low']>0
    nominal=bool(own and ret and dd and ci and positive_wealth)
    unknown=bool(stale or execution_unknown or not all(finite(p['drawdown_percentage_point_difference']) for p in points.values()))
    return dict(status='unsupported' if not nominal else 'unknown_historical_stale' if stale else 'unknown_execution_capacity_or_entry' if execution_unknown else 'nominal_policy_pass_unqualified',
        cash_nominal_pass=nominal,nominal_pass=bool(nominal and not unknown),financial_unknown=unknown,own_returns_positive_all_four=bool(own),return_gate=bool(ret),drawdown_gate=bool(dd),primary_daily_log_CI_lower_positive=bool(ci),actual_wealth_positive=bool(positive_wealth),any_historical_stale=bool(stale),execution_unknown=bool(execution_unknown),held_recomputed=False,new_model_generalization_claim=False,legal_clearance_proved=False,independent_actual_review_required=True,no_automatic_promotion=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False)


def review_comparisons(protocol,manifest,metrics,daily,logs,reviewed,diag,execution,out):
    points={};controls={};control_logs={};old_reports={}
    comp,dist,summary_table,annual=[table(manifest[n]) for n in ('comparisons','bootstrap_distributions','account_summaries','annual_slices')]
    assert len(comp)==4 and not comp.duplicated(['window','cost']).any() and comp.contrast.eq(ARM+'_minus_CONTROL_REUSED').all()
    assert len(dist)==2000 and set(dist)=={w+'_'+c+'_'+ARM+'_minus_CONTROL_REUSED' for w in WINDOWS for c in COSTS}
    assert set(manifest['baseline_books'])=={w+'_'+c for w in WINDOWS for c in COSTS}
    for w in WINDOWS:
        indices=np.load(verify(protocol['statistics']['indices'][w]),allow_pickle=False)
        same(manifest['bootstrap_indices'][w],protocol['statistics']['indices'][w])
        for c in COSTS:
            key=(w,c);name=f'NARROW_B_{w}_{c}';b=protocol['cash']['read_only_control_books'][w+'_'+c]
            nested(manifest['baseline_books'][w+'_'+c],b,'exact unchanged control binding')
            control=read_json(b['summary']);cd=pd.read_csv(verify(b['daily']),dtype={'date':str},float_precision='round_trip')
            assert cd.date.tolist()==daily[key].date.tolist()
            assert indices.shape==(2000,len(cd)) and indices.dtype.kind in 'iu' and indices.min()>=0 and indices.max()<len(cd)
            cl=diag._log(cd,1000000.);p,distribution=paired(logs[key],cl,indices);active=metrics[key]
            p.update(active_total_return_pct=active['total_return_pct'],reference_total_return_pct=control['total_return_pct'],return_percentage_point_difference=active['total_return_pct']-control['total_return_pct'],drawdown_percentage_point_difference=None if control['fills']==0 else active['max_drawdown_pct']-control['max_drawdown_pct'],dd_comparison_state='NA_empty_reference' if control['fills']==0 else 'active_reference',identification='all_empty_unidentified' if active['fills']==control['fills']==0 else 'observed_cash_comparison',active_log_status='valid' if logs[key] is not None else 'survival_failure_no_log_repair',control_log_status='valid' if cl is not None else 'survival_failure_no_log_repair',bootstrap_repetitions=2000,block_length=252,indices_regenerated=False,epsilon_log_repair=False)
            row=comp.loc[comp.window.eq(w)&comp.cost.eq(c)];assert len(row)==1;fields(row.iloc[0].to_dict(),p,'all four paired new/control values')
            compare(pd.to_numeric(dist[w+'_'+c+'_'+ARM+'_minus_CONTROL_REUSED'].replace('',np.nan)),distribution,'all four original070 CI distributions',atol=1e-12)
            got=summary_table.loc[summary_table.account.eq(name)];assert len(got)==1
            fields(got.iloc[0].to_dict(),dict({k:v for k,v in control.items() if not isinstance(v,(dict,list))},arm='CONTROL_REUSED',window=w,cost=c,source_only=True,replayed=False),'four reused control metric identities')
            old_reports[key]=read_json(b['diagnostics'])[b['diagnostic_key']]
            ar=annual.loc[annual.account.eq(name)].sort_values('year');assert len(ar)==len(old_reports[key]['annual_slices'])
            for got,want in zip(ar.to_dict('records'),old_reports[key]['annual_slices']):fields(got,want,'reused old annual identity')
            points[key],controls[key],control_logs[key]=p,control,cl
    assert len(summary_table)==8 and set(summary_table.account)=={f'NARROW_{arm}_{w}_{c}' for arm in (ARM,'B') for w in WINDOWS for c in COSTS}
    expected_accounts={f'NARROW_{arm}_{w}_{c}' for arm in (ARM,'B') for w in WINDOWS for c in COSTS}
    assert set(annual.account)==expected_accounts and not annual.duplicated(['account','year']).any()
    stale=any(b['diagnostics']['stale_days']>0 for b in reviewed) or any(r['stale_days']>0 for r in old_reports.values())
    unknown=any(v['execution_unknown'] for v in list(metrics.values())+list(controls.values()))
    positive=all(log is not None for log in list(logs.values())+list(control_logs.values()))
    gate=fixed_gate(points,stale,positive,unknown);nested(read_json(manifest['continuation_gate']),gate,'entire fixed155 gate')
    fields(read_json(manifest['signal_identification']),dict(full_mother_rows=399252,full_main_parent_rows=161014,canonical_from_full_original_mothers=True,filter_full_domain_before_argmax=True,old_B_selection_used_as_admission_gate=False,future_label_state_used_as_admission_gate=False,local_B_schema_alias_only=True,old_global_ARMS_changed=False,held_recomputed=False,new_model_generalization_claim=False),'population and epistemic disclosure')
    disclosure=read_json(manifest['budget_and_tick_disclosure'])
    fields(disclosure,dict(policy='NARROW',bootstrap_indices_regenerated=False,fees_already_in_cash=True,slippage_in_fill_price_already=True,slippage_deducted_again=False,no_gap_loss_cap=True,no_actual_orderbook_execution_proof=True,legal_clearance_proved=False,source_archive_is_final_reconstruction=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False),'cash disclosure')
    nested(disclosure['budget'],protocol['cash'],'unchanged155 cash budget')
    nested(disclosure['capacity'],execution['cash']['capacity'],'unchanged128 capacity')
    nested(disclosure['anchor'],execution['anchor_and_execution'],'unchanged128 anchor execution')
    nested(disclosure['bootstrap_indices'],protocol['statistics']['indices'],'exact070 index disclosure')
    fields(read_json(manifest['source_read_receipt']),dict(native_source_queries=0,actual_model_fit_calls=0,new_labels=0,old_baseline_replays=0,full_forward_parent_rows=161014,full_mother_rows=399252,canonical_from_full_original_mothers=True,original_source_lifecycle_modified=False),'cache-only receipt')
    result=dict(comparisons_checked=4,bootstrap_repetitions=2000,block_length=252,indices_regenerated=False,paired_daily_log_conditional_not_unseen_OOS=True,points=[dict(window=w,cost=c,**p) for (w,c),p in points.items()],gate=gate,old_control_book_reaudits=0,old_control_replays=0,execution_unknown_in_either_arm_retained=unknown)
    progress(out,'confidence_and_gate_review',result);return result


def authorize(args):
    out=Path(args.output).resolve();assert not out.exists(),'fresh review output required'
    assert LINE/'outputs/stage158_voluntary_review' in out.parents,'review output outside assigned directory'
    inputs={k:binding(getattr(args,k)) for k in ('protocol','clarifier','choice_manifest','cash_manifest')}
    assert inputs['protocol']['sha256']==PROTOCOL_SHA and inputs['clarifier']['sha256']==CLARIFIER_SHA
    clarifier=read_json(inputs['clarifier']);inputs['accepted_cash_review']=clarifier['accepted_cash_review']
    ab=binding(args.authorization);assert ab['sha256']==args.authorization_sha256
    auth=read_json(ab);fields(auth,dict(schema='stage158_exact_root_review_authorization_v1',authorized_by='root',exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(out)),'root review authorization')
    nested(auth['input_bindings'],inputs,'exact review input roles')
    assert sorted(auth['source_bundle'],key=lambda b:b['path'])==bundle(),'exact reviewer and accepted helper bytes'
    return out,inputs,auth,ab,clarifier


def input_closure(inputs,clarifier):
    protocol=read_json(inputs['protocol']);assert protocol['schema']=='stage155_voluntary_calendar_full_domain_protocol_v1' and protocol['line_id']==LINE.name
    assert clarifier['protocol_sha256']==PROTOCOL_SHA and clarifier['scientific_policy_unchanged'] is True
    src=protocol['source_bindings'];execution=read_json(src['base_execution_protocol'])
    same(execution['inputs']['market_protocol'],clarifier['market_protocol'])
    bridge=read_json(clarifier['market_protocol']);same(bridge['calendar'],clarifier['calendar_binding'])
    assert bridge['calendar']['bytes']==44824 and bridge['calendar']['sha256']=='57dd7f539d1cdbefb528978a6c7bd79b118790f933ce63c37b10747b999f9585'
    accepted=read_json(inputs['accepted_cash_review'])
    assert accepted['completed'] is True and accepted['research_arithmetic_accepted'] is True and (accepted['C'],accepted['I'])==(0,0)
    choice,cash=read_json(inputs['choice_manifest']),read_json(inputs['cash_manifest'])
    fields(choice,dict(schema='stage156_voluntary_choices_manifest_v1',parent_rows=161014,main_action_rows=966740,new_fit=0,new_cash=0,new_SQL=0,new_labels=0,not_certified=True),'156 manifest')
    fields(read_json(choice['artifacts']['terminal']),dict(status='completed',exit_code=0,main_actions=966740,parents=161014,fit=0,SQL=0,labels=0,cash=0),'156 actual terminal')
    for role in ('protocol','fit_manifest','mothers','child_scores'):
        same(choice['inputs'][role],inputs['protocol'] if role=='protocol' else src[role])
    same(choice['inputs']['calendar_only'],clarifier['calendar_binding'])
    for b in choice['source_bundle']:verify(b)
    for b in choice['artifacts'].values():verify(b)
    fields(cash,dict(schema='stage157_voluntary_cash_v1',new_cash_accounts=4,native_source_queries=0,actual_model_fit_calls=0,new_labels=0,old_baseline_replays=0,old_control_cash_replays=0,production_qualified=False,increased_betting_qualified=False,goal_complete=False),'157 manifest')
    same(cash['protocol'],inputs['protocol']);same(cash['input_bindings']['choice_manifest'],inputs['choice_manifest'])
    for role,frozen in [('execution_protocol','base_execution_protocol'),('dataset_manifest','dataset_manifest'),('fit_manifest','fit_manifest'),('actions','actions'),('mothers','mothers'),('native_cache_manifest','native_cache_json'),('native_cache','native_cache_file')]:same(cash['input_bindings'][role],src[frozen])
    same(cash['input_bindings']['accepted_review_receipt'],inputs['accepted_cash_review'])
    same(cash['input_bindings']['market_protocol'],clarifier['market_protocol'])
    for role in ('choices_main','boundaries'):same(cash['input_bindings'][role],choice['artifacts'][role])
    for b in cash['source_bundle']:verify(b)
    for b in cash['input_bindings'].values():verify(b)
    for b in cash['artifacts']:verify(b)
    terminal=read_json(cash['terminal']);continuation={}
    if cash['status']=='completed':
        fields(terminal,dict(status='completed',exit_code=0,cash_accounts_started=4,new_cash_accounts=4,native_source_queries=0,actual_model_fit_calls=0,new_labels=0,downloads=0,whole_database_hashes=0,old_baseline_replays=0),'157 terminal')
    else:
        assert cash['status']=='completed_with_metadata_continuation'
        original=read_json(cash['original_actual_terminal']);same(cash['financial_actual_terminal'],cash['original_actual_terminal'])
        fields(original,dict(status='failed',exit_code=1,cash_accounts_started=4,new_cash_accounts=4,native_source_queries=0,actual_model_fit_calls=0,new_labels=0,downloads=0,whole_database_hashes=0,old_baseline_replays=0,error="KeyError: 'anchor_and_execution'"),'transparent original failed after4 cash')
        fields(terminal,dict(status='completed',exit_code=0,new_cash_accounts=0,reused_completed_cash_accounts=4,actual_model_fit_calls=0,native_source_queries=0,financial_recalculations=0,bootstrap_recalculations=0,original_financial_outputs_unchanged=True,original_failed_terminal_preserved=True),'metadata-only continuation terminal')
        same(terminal['original_actual_terminal'],cash['original_actual_terminal'])
        snapshot=read_json(cash['metadata_continuation_started'])
        fields(snapshot,dict(schema='stage157_metadata_continuation_started_v1',new_cash_accounts=0,actual_model_fit_calls=0,native_source_queries=0,financial_recalculations=0),'metadata continuation started')
        assert len(snapshot['all_original_artifact_bindings'])==terminal['original_artifact_count']==63
        same(snapshot['original_actual_terminal'],cash['original_actual_terminal'])
        nested(snapshot['source_bundle'],cash['metadata_continuation_source_bundle'],'exact metadata source bundle')
        preserved={b['path'] for b in snapshot['all_original_artifact_bindings']}
        financial={b['path'] for a in cash['accounts'] for b in [a['summary'],*a['ledgers'].values()]}
        assert financial.issubset(preserved),'all four financial books in immutable pre-continuation snapshot'
        assert cash['original_actual_terminal']['path'] in preserved
        for b in snapshot['all_original_artifact_bindings']:verify(b)
        for b in cash['metadata_continuation_source_bundle']:verify(b)
        original_start=read_json(snapshot['original_actual_started'])
        nested(original_start['source_bundle'],cash['source_bundle'],'unchanged original cash author bundle')
        same(original_start['protocol'],inputs['protocol']);same(original_start['authorization'],cash['authorization'])
        continuation=dict(original_actual_terminal=cash['original_actual_terminal'],metadata_terminal=cash['terminal'],original_financial_cash_completed=4,metadata_cash=0,original_artifacts_unchanged=len(preserved),all_four_books_in_snapshot=True)
    c=protocol['cash']
    assert (c['initial_capital'],c['initial_stop_N'],c['single_family_risk'],c['total_risk'],c['buffered_margin_cap'],c['margin_buffer'],c['participation_rate'])==(1000000,.25,.0025,.02,.25,1.1,.01)
    assert c['new_accounts_max']==4 and c['cache_only'] and c['native_SQL']==0 and c['roundtrip_entry_half_capacity']
    return protocol,execution,choice,cash,dict(exact_source_and_input_closed=True,accepted132_identity_only=True,source_calendar_days=5587,original_fit_receipt_reused=True,metadata_continuation=continuation)


def review(args):
    out,inputs,auth,ab,clarifier=authorize(args);out.mkdir(parents=True,exist_ok=False)
    began=time.monotonic();source_before=bundle();receipt=dict(schema='stage158_voluntary_independent_review_v1',completed=False,C=0,I=0,M=0,errors=[],inputs=inputs,authorization=ab,source_bundle=source_before,new_fit=0,new_cash=0,SQL=0,downloads=0,whole_database_hashes=0,strategy_replays=0,old_control_book_reaudits=0,old_control_replays=0,models_refit_or_repredicted=0,author156_or157_imported=False)
    write(out/'started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),schema=receipt['schema'],source_bundle=source_before,inputs=inputs))
    try:
        protocol,execution,choice,manifest,closure=input_closure(inputs,clarifier);receipt['closure']=closure;progress(out,'input_closure',closure)
        r,cash,diag=helpers();bridge,calendar=r.calendar_from_protocol(execution)
        assert calendar==sorted(set(calendar)) and len(calendar)==5587
        same(bridge['calendar'],clarifier['calendar_binding']);same(read_json(choice['artifacts']['boundaries'])['calendar'],bridge['calendar'])
        mothers,choices,bounds,selection=review_selection(protocol,choice,calendar,out);receipt['selection']=selection
        store,economics=cached_store(protocol,execution,clarifier,r)
        signals,signal_report=review_signals(protocol,manifest,choices,bounds,store,economics,r,out);receipt['signals']=signal_report
        metrics,daily,logs,books,grids=review_books(protocol,manifest,signals,mothers,store,economics,execution,out,r,cash,diag)
        receipt['books'],receipt['grids']=books,grids
        receipt['confidence']=review_comparisons(protocol,manifest,metrics,daily,logs,books,diag,execution,out)
        assert bundle()==source_before,'reviewer/helper changed during review'
        for b in inputs.values():same(binding(b['path']),b)
        # Accepted helper error maps quantify tolerances without another run.
        receipt['maximum_numeric_errors']=dict(ERRORS);receipt['accepted132_numeric_errors']=dict(r.ERRORS)
        receipt.update(completed=True,research_arithmetic_accepted=True,financial_review_new_books=4,financial_cash_accounts_added_by_this_review=0,cumulative_fit=397,cumulative_cash=210,conditional_reconstructed_evidence_only=True,legal_clearance_proved=False,production_qualified=False,increased_betting_qualified=False,goal_complete=False)
    except BaseException as exc:
        receipt['I']=1;receipt['errors'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()));raise
    finally:
        receipt['elapsed_seconds']=time.monotonic()-began;write(out/'receipt.json',receipt)
        print(json.dumps(dict(completed=receipt['completed'],C=receipt['C'],I=receipt['I'],M=receipt['M'],output=str(out))),flush=True)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ('protocol','clarifier','choice-manifest','cash-manifest','authorization','authorization-sha256','output'):parser.add_argument('--'+n,required=True)
    review(parser.parse_args())


if __name__=='__main__':main()
