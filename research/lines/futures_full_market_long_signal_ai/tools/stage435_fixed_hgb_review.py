"""Bounded independent review of fixed432 new HGB selection and four cash books.

No training, financial replay, SQL, raw-price qualification or old large rehash.
Root binds this source before the one actual review; original controls are reused.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import time
import traceback
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

TOOLS=Path(__file__).resolve().parent;LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage432_fixed_learner_protocol/protocol.json'
PROTOCOL_SHA='45c93399f2d6552a77805c9ca5bce9568b8e32522a5b6cdf5c289de11dbe847d'
ARM='COMMON52_FIXED_SHALLOW_HGB';END='2026-10-16'
WINDOWS=('primary_2020','cold_2023');COSTS=('base','stress')
IDENTITY=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
SCORE_FIELDS=['sequence_index','action_id','mother_sequence_index','mother_event_id','product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible','score','scope','cutoff','old_score']
HELPERS=('stage158_voluntary_review.py','stage132_contract_choice_review.py','stage102_cash_adapter.py','stage102_cash_core.py','stage102_cash_diagnostics.py')


def binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def doc(b):
    assert binding(b['path'])=={k:b[k] for k in ('path','bytes','sha256')},('small/new binding',b['path'])
    return json.loads(Path(b['path']).read_text())


def stat(b):
    p=Path(b['path']);s=p.stat();assert s.st_size==b['bytes'],('inherited size',p)
    return dict(path=str(p.resolve()),bytes=s.st_size,inode=s.st_ino,mtime_ns=s.st_mtime_ns,inherited_sha256=b['sha256'],rehashed=False)


def write(path,obj):
    def safe(x):
        if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [safe(v) for v in x]
        if isinstance(x,np.ndarray):return safe(x.tolist())
        if isinstance(x,(np.integer,np.bool_)):return x.item()
        if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
        return x
    with Path(path).open('x') as f:json.dump(safe(obj),f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False);f.write('\n')


def load(name):
    spec=importlib.util.spec_from_file_location('review435_'+name.removesuffix('.py'),TOOLS/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def source_bundle():return [binding(Path(__file__)),*[binding(TOOLS/n) for n in HELPERS]]


def table(b,new=True,**kwargs):
    if new:assert binding(b['path'])=={k:b[k] for k in ('path','bytes','sha256')}
    else:stat(b)
    return pd.read_csv(b['path'],dtype=str,keep_default_na=False,float_precision='round_trip',**kwargs)


def group(f):return int(hashlib.sha256(str(f).encode()).hexdigest(),16)%2


def native_summary_alias(summary):
    """Reviewer-only old132 vocabulary view; original summary is never changed."""
    view=dict(summary)
    if 'unknown_capacity_fills' not in view:
        assert 'capacity_unknown_fills' in view
        view['unknown_capacity_fills']=view['capacity_unknown_fills']
    elif 'capacity_unknown_fills' in view:
        assert view['unknown_capacity_fills']==view['capacity_unknown_fills']
    return view


def cutoff(day):return '2020-01-01' if day<'2023-01-01' else '2023-01-01'


def portable_scores(p,x):
    """Independent scalar traversal; standardized design is finite, no NaN branch."""
    assert x.ndim==2 and x.shape[1]==52 and np.isfinite(x).all() and p['n_features']==52
    values=[]
    for row in x:
        value=float(p['baseline'])
        for tree in p['trees']:
            i=0
            while not tree[i]['is_leaf']:
                node=tree[i];i=node['left'] if row[node['feature_idx']]<=node['num_threshold'] else node['right']
            value+=tree[i]['value']
        values.append(value)
    return np.asarray(values)


def independent_gate(points,annual,held):
    finite=lambda x:x is not None and math.isfinite(float(x))
    checks={}
    for p in points:
        key=(p['window'],p['cost']);checks['_'.join(key)]=dict(
            equity_strictly_higher=finite(p['ending_equity_difference']) and p['ending_equity_difference']>0,
            drawdown_nonharm=finite(p['drawdown_percentage_point_difference']) and p['drawdown_percentage_point_difference']>=0,
            sharpe_nonharm=finite(p['sharpe_difference']) and p['sharpe_difference']>=0,
            positive_return=finite(p['active_total_return_pct']) and p['active_total_return_pct']>0,
            paired_growth=(finite(p['ci95_low']) and p['ci95_low']>0) if key[0]=='primary_2020' else finite(p['cumulative_log_difference']) and p['cumulative_log_difference']>0)
    assert len(checks)==4
    family={k:finite(v['known_u_equal_mean_increment_R']) and v['known_u_equal_mean_increment_R']>=0 for k,v in held['groups'].items()}
    years=[r for r in annual if r['window']=='primary_2020' and r['cost']=='stress' and str(r['year']) in set(map(str,range(2020,2026)))]
    assert len(years)==6 and {str(r['year']) for r in years}==set(map(str,range(2020,2026)))
    nonnegative=sum(finite(r['candidate_growth_amount']) and r['candidate_growth_amount']>=0 for r in years)
    increments=sum(finite(r['growth_amount_difference']) and r['growth_amount_difference']>0 for r in years)
    return dict(nominal_all_fixed_gates_pass=bool(all(all(v.values()) for v in checks.values()) and all(family.values()) and nonnegative>=4 and increments>=4),
        predicates=checks,held_known_mean_nonnegative=family,complete_stress_years_nonnegative=nonnegative,
        complete_stress_years_positive_paired_growth=increments,weak_year_gate=nonnegative>=4 and increments>=4)


def review_models(protocol,manifest,h,r,out):
    assert manifest['schema']=='stage433_fixed_hgb_fit_select_manifest_v1' and manifest['status']=='completed'
    assert manifest['protocol_sha256']==PROTOCOL_SHA and manifest['candidate']==ARM
    for b in manifest['source_bundle']:assert binding(b['path'])==b
    counters=manifest['counters'];assert counters['fit_attempted']==counters['fit_completed']==6
    assert counters['common_reads']==counters['score_csv_reads']==1 and counters['training_csv_reads']==6
    assert counters['cash']==counters['SQL']==counters['old52_refit']==counters['new_labels']==0
    terminal=doc(manifest['artifacts']['terminal']);assert terminal['status']=='completed' and terminal['exit_code']==0
    inputs=protocol['inputs'];assert manifest['inputs']==inputs
    inherited={k:inputs[k] for k in ('mothers','actions','control_choices_main','control_held_choices')}
    inherited['common']=protocol['identity_inputs']['original_common']
    before={k:stat(b) for k,b in inherited.items()}
    cal=np.load(inputs['calendar']['path'],allow_pickle=False)
    dates=[str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in cal] if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist()
    assert len(dates)==5587 and dates==sorted(set(dates))
    mothers=table(inputs['mothers'],False,usecols=IDENTITY)
    h.numeric(mothers,['sequence_index','u_index'])
    assert len(mothers)==399252 and mothers.sequence_index.tolist()==list(range(399252)) and mothers.event_id.is_unique
    assert mothers.product_id.nunique()==98 and mothers.family_id.nunique()==95
    forward=mothers.loc[mothers.u_date.between('2020-01-01',END)].copy();assert len(forward)==161014
    parents=mothers.set_index('sequence_index',drop=False)
    family_groups={f:group(f) for f in mothers.family_id.unique()}
    originals={(f['scope'],f['cutoff']):f for f in protocol['identity_inputs']['original130_folds']}
    records={(f['scope'],f['cutoff']):f for f in manifest['folds']};assert set(records)==set(originals)
    for key,f in records.items():
        original=originals[key];assert f['parameters']==protocol['parameters'] and f['dimension']==52 and f['n_iter']==100
        for field in ('training_rows','training_dates','training_families','training_groups','prediction_children','prediction_mothers','max_u_date','max_label_known_date','training_identity_weights','scaler'):assert f[field]==original[field],(key,field)
        assert f['training_weights_renormalized'] is False and f['portable_anchor_count']==64 and f['portable_max_abs_error']<=1e-12
        # A deterministic prefix tests mature identities and w/Y values; full train validation is inherited and source-inspected.
        a=table(f['training_identity_weights'],False,nrows=16)
        assert (a.u_date<key[1]).all() and (a.label_known_date!='').all() and (a.label_known_date<key[1]).all()
        assert a.label_state.eq('closed_complete_bar_model').all() and a.u_action_eligible.astype(int).eq(1).all()
        assert np.isfinite(a.net_R_stress.astype(float)).all() and np.isfinite(a.sample_weight.astype(float)).all() and a.sample_weight.astype(float).gt(0).all()
        if key[0]!='main':assert not a.family_id.map(family_groups).eq(int(key[0][-1])).any()
    observed={s:set() for s in ('main','holdout_0','holdout_1')};positive={s:{} for s in observed};proposed={s:{} for s in observed}
    boundaries={};seen=set();counts=Counter();anchors={k:[] for k in records}
    score_binding=manifest['artifacts']['child_scores'];stat(score_binding)
    for chunk in pd.read_csv(score_binding['path'],usecols=SCORE_FIELDS,dtype=str,keep_default_na=False,chunksize=100000,float_precision='round_trip'):
        h.numeric(chunk,['sequence_index','mother_sequence_index','u_index','u_action_eligible','score','old_score'])
        assert np.isfinite(chunk.score).all() and np.isfinite(chunk.old_score).all() and chunk.u_action_eligible.isin([0,1]).all()
        pp=parents.loc[chunk.mother_sequence_index].reset_index(drop=True)
        assert chunk.mother_event_id.tolist()==pp.event_id.tolist() and chunk.anchor_epoch.tolist()==pp.reference_epoch.tolist()
        for field in ('product_id','family_id','u_date','u_index'):assert chunk[field].tolist()==pp[field].tolist(),field
        assert chunk.cutoff.tolist()==chunk.u_date.map(cutoff).tolist() and chunk.u_date.between('2020-01-01',END).all()
        for key,part in chunk.groupby(['scope','cutoff'],sort=False):
            assert key in records;counts[key]+=len(part)
            if key[0]!='main':assert part.family_id.map(family_groups).eq(int(key[0][-1])).all()
            anchors[key].extend(part.head(max(0,16-len(anchors[key]))).to_dict('records'))
        for row in chunk.to_dict('records'):
            scope=row['scope'];seq=int(row['sequence_index']);mother=int(row['mother_sequence_index']);key=(scope,seq)
            assert key not in seen;seen.add(key);observed[scope].add(mother)
            assert row['reference_epoch'].rsplit('.',1)[0]==row['product_id']
            epoch=row['reference_epoch']
            if epoch not in boundaries:boundaries[epoch]=h.deadline(epoch,dates,END)
            if row['u_action_eligible']!=1 or row['score']<=0:continue
            rank=(-float(row['score']),epoch,row['action_id'])
            if mother not in positive[scope] or rank<positive[scope][mother][0]:positive[scope][mother]=(rank,row)
            eligibility=h.admission(int(row['u_index']),1,row['score'],boundaries[epoch],dates,END)
            if eligibility['new_eligible']==1 and (mother not in proposed[scope] or rank<proposed[scope][mother][0]):proposed[scope][mother]=(rank,row)
    assert sum(counts.values())==1933480
    for key,f in records.items():assert counts[key]==f['prediction_children']
    choices={}
    for role in ('choices_main','choices_holdout'):
        frame=table(manifest['artifacts'][role]);h.numeric(frame,['sequence_index','u_index','selected','chosen_action_sequence_index','score','proposed_score'])
        assert len(frame)==161014 and frame.event_id.tolist()==forward.event_id.tolist()
        choices[role]=frame
    for scope in observed:
        ps={k:v[1] for k,v in proposed[scope].items()};old={k:v[1] for k,v in positive[scope].items()}
        winners=h.family_choices(ps.values());oldwinners=h.family_choices(old.values())
        frame=choices['choices_main'] if scope=='main' else choices['choices_holdout'].loc[choices['choices_holdout'].scope.eq(scope)]
        expected_parents=forward if scope=='main' else forward.loc[forward.family_id.map(family_groups).eq(int(scope[-1]))]
        assert frame.sequence_index.tolist()==expected_parents.sequence_index.tolist()
        for row in frame.to_dict('records'):
            mother=int(row['sequence_index']);p=ps.get(mother);w=winners.get(mother);ow=oldwinners.get(mother)
            state='selected' if w else 'family_priority_suppressed' if p else 'no_observed_children' if mother not in observed[scope] else 'no_calendar_eligible_positive_action' if mother in old else 'no_original_eligible_positive_action'
            want=dict(scope=scope,selected=int(w is not None),chosen_action_id=w['action_id'] if w else '',chosen_epoch=w['reference_epoch'] if w else '',chosen_action_sequence_index=int(w['sequence_index']) if w else -1,score=float(w['score']) if w else None,
                proposed_action_id=p['action_id'] if p else '',proposed_epoch=p['reference_epoch'] if p else '',proposed_score=float(p['score']) if p else None,selection_state=state,old_chosen_action_id=ow['action_id'] if ow else '',old_chosen_epoch=ow['reference_epoch'] if ow else '')
            h.fields(row,want,'complete K and family choice')
    savedbound=doc(manifest['artifacts']['boundaries']);h.nested(savedbound['epochs'],boundaries,'all new K boundaries')
    with np.load(inherited['common']['path'],allow_pickle=False) as z:common=z['common'];names=z['columns'].tolist()
    assert common.shape==(1552456,26)
    anchor_results=[]
    for key,f in records.items():
        portable=doc(f['portable_model']);scaler=doc(f['scaler']);assert portable['parameters']==protocol['parameters']
        assert portable['scaler']==f['scaler'] and portable['training_identity_weights']==f['training_identity_weights']
        assert scaler['common']['columns']==names and len(scaler['feature_names'])==52 and portable['feature_names']==scaler['feature_names']
        aa=anchors[key];assert len(aa)==16;raw=common[[int(a['sequence_index']) for a in aa]];finite=np.isfinite(raw)
        x=np.column_stack([np.where(finite,(raw-np.asarray(scaler['common']['mean']))/np.asarray(scaler['common']['scale']),0.),(~finite).astype(float)])
        assert binding(f['model']['path'])==f['model'];model=joblib.load(f['model']['path'])
        for k,v in protocol['parameters'].items():assert model.get_params()[k]==v
        with threadpool_limits(limits=1):direct=model.predict(x)
        independent=portable_scores(portable,x);saved=np.asarray([a['score'] for a in aa],float)
        h.compare(direct,independent,'independent portable forward anchors',atol=1e-12,rtol=1e-12)
        h.compare(saved,direct,'saved new score forward anchors',atol=1e-12,rtol=1e-12)
        anchor_results.append(dict(scope=key[0],cutoff=key[1],anchors=16,max_portable_error=float(np.max(np.abs(direct-independent))),max_saved_error=float(np.max(np.abs(saved-direct)))))
    del common
    control=table(inputs['control_choices_main'],False);heldcontrol=table(inputs['control_held_choices'],False)
    for frame in (control,heldcontrol):assert frame.event_id.tolist()==forward.event_id.tolist();h.numeric(frame,['selected','sequence_index','u_index'])
    changed=int(np.count_nonzero(control.chosen_action_id.to_numpy()!=choices['choices_main'].chosen_action_id.to_numpy()))
    assert changed==manifest['changed_main_parent_choices'] and manifest['cash_eligible']==bool(changed)
    # Independently retain unknown held outcomes; no cash veto is imposed here.
    ids=set(heldcontrol.loc[heldcontrol.selected.eq(1),'chosen_action_id'])|set(choices['choices_holdout'].loc[choices['choices_holdout'].selected.eq(1),'chosen_action_id'])
    labels={};labelrows=0
    for chunk in pd.read_csv(inputs['actions']['path'],usecols=['action_id','label_state','participation_state','net_R_stress','label_known_date'],dtype=str,keep_default_na=False,chunksize=100000):
        labelrows+=len(chunk)
        for row in chunk.loc[chunk.action_id.isin(ids)].to_dict('records'):assert row['action_id'] not in labels;labels[row['action_id']]=row
    assert labelrows==1552456 and set(labels)==ids
    def outcome(row):
        if int(row['selected'])==0:return 0.
        a=labels[row['chosen_action_id']]
        if a['participation_state']=='known_nonparticipation':return 0.
        if a['label_state']=='closed_complete_bar_model' and a['label_known_date'] and a['label_known_date']<=END and a['net_R_stress'] and math.isfinite(float(a['net_R_stress'])):return float(a['net_R_stress'])
        return math.nan
    held=doc(manifest['artifacts']['held_diagnostic']);held_results={}
    for scope in ('holdout_0','holdout_1'):
        aa=heldcontrol.loc[heldcontrol.scope.eq(scope)].sort_values('selected',ascending=False,kind='stable').drop_duplicates(['family_id','u_index']).set_index(['family_id','u_index']).sort_index()
        bb=choices['choices_holdout'].loc[choices['choices_holdout'].scope.eq(scope)].sort_values('selected',ascending=False,kind='stable').drop_duplicates(['family_id','u_index']).set_index(['family_id','u_index']).sort_index()
        assert aa.index.tolist()==bb.index.tolist() and aa.u_date.tolist()==bb.u_date.tolist()
        same=aa.chosen_action_id.to_numpy()==bb.chosen_action_id.to_numpy();a=np.asarray([outcome(v) for v in aa.to_dict('records')]);b=np.asarray([outcome(v) for v in bb.to_dict('records')]);known=np.isfinite(a)&np.isfinite(b)
        delta=np.where(same,0.,np.where(known,b-a,np.nan));unknown=~same&~known
        daily=pd.DataFrame(dict(u_date=aa.u_date.to_numpy(),delta=delta,unknown=unknown)).groupby('u_date',sort=True).agg(delta=('delta','mean'),unknown=('unknown','sum')).reset_index()
        mean=float(daily.delta.mean()) if daily.delta.notna().any() else None
        want=dict(known_u_equal_mean_increment_R=mean,unknown_differential_selected_events=int(unknown.sum()),common_unresolved_same_action=int((same&(aa.chosen_action_id.to_numpy()!='')&~known).sum()),full_family_u=len(aa),known_increment_family_u=int(np.isfinite(delta).sum()),known_source_days=int(daily.delta.notna().sum()),selected_by_arm={'A':int(heldcontrol.loc[heldcontrol.scope.eq(scope),'selected'].sum()),'B':int(choices['choices_holdout'].loc[choices['choices_holdout'].scope.eq(scope),'selected'].sum())})
        h.fields(held['groups'][scope],{k:v for k,v in want.items() if k!='selected_by_arm'},'independent held outcome')
        assert held['groups'][scope]['selected_by_arm']==want['selected_by_arm'];held_results[scope]=want
    assert {k:stat(b) for k,b in inherited.items()}==before
    receipt=dict(status='completed',folds=6,prediction_rows=sum(counts.values()),all_new_K_choices_checked=322028,forward_anchor_results=anchor_results,changed_main_parent_choices=changed,held=held_results,
        full_old_training_rows_reaudited=False,training_prefix_anchors_per_fold=16,full_forward_prediction_rerun=False,model_refits=0,old_action_label_streams=1,large_old_rehashes=0)
    write(out/'model_selection_review.json',receipt);print(json.dumps(dict(phase='model_selection_review_completed',changed=changed)),flush=True)
    return receipt,mothers,dates,choices,held


def review_cash(protocol,fit,manifest,h,r,cash,diag,mothers,dates,choices,held,out):
    assert manifest['schema']=='stage434_fixed_hgb_cash_manifest_v1' and manifest['status']=='completed' and manifest['candidate']==ARM
    assert manifest['new_cash_accounts']==manifest['cash_accounts_started']==4 and manifest['new_fit']==manifest['old_control_replays']==0
    for b in manifest['source_bundle']:assert binding(b['path'])==b
    terminal=doc(manifest['terminal']);assert terminal['status']=='completed' and terminal['cash_accounts_started']==terminal['cash_accounts_completed']==4
    refs=doc(protocol['cash']['reference']);execution=doc(protocol['inputs']['execution_protocol']);market=doc(protocol['inputs']['market_protocol'])
    accepted=doc(refs['small_identity_bindings']['accepted_158']);assert accepted['completed'] and accepted['research_arithmetic_accepted']
    accepted_sources={b['path']:b for b in accepted['source_bundle']}
    for name in HELPERS:assert binding(TOOLS/name)==accepted_sources[str(TOOLS/name)]
    dep=refs['market_dependencies'];cb=refs['input_bindings_inherited_from_accepted157']['native_cache'];before=stat(cb)
    store=r.NativeBars(dates)
    with np.load(cb['path'],allow_pickle=False) as z:
        epochs=z['epochs'].tolist();offsets=z['offsets'];arrays={k:z[k] for k in ('days','values','accepted','valid','N','low20','run')}
        assert len(epochs)==9520 and offsets[-1]==1552456
        for i,e in enumerate(epochs):store.series[e]={k:v[int(offsets[i]):int(offsets[i+1])] for k,v in arrays.items()}
    eb=dep['economic_projection'];stat(eb);economics=json.loads(Path(eb['path']).read_text())['instruments'];assert set(economics)==set(store.series)
    artifacts={Path(b['path']).name:b for b in manifest['artifacts']}
    signals=table(artifacts['signals_candidate.csv.gz']);h.numeric(signals,['action_sequence_index','u_index','D_index','label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index','entry_capacity_qty','u_gross_capacity_qty','potential','score','source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index'])
    picked=choices['choices_main'].loc[choices['choices_main'].selected.eq(1)];assert signals.event_id.tolist()==picked.chosen_action_id.tolist() and not signals.duplicated(['family_id','u_date']).any()
    bounds=doc(fit['artifacts']['boundaries'])['epochs'];signals=signals.set_index('event_id',drop=False)
    for c in picked.itertuples(index=False):
        epoch=c.chosen_epoch;u=int(c.u_index);j=store.locate(epoch,u);native=store.series[epoch];assert j is not None and native['valid'][j] and native['run'][j]>=20
        gross,entry=r.capacity(native['values'][j,4],economics[epoch]['round_lot']);source=r.lifecycle(epoch,economics[epoch],dates);effective,origin=h.effective_boundary(source,bounds[epoch],u+1)
        want=dict(mother_event_id=c.event_id,action_sequence_index=int(c.chosen_action_sequence_index),product_id=c.product_id,family_id=c.family_id,u_date=c.u_date,u_index=u,D_index=u+1,reference_epoch=epoch,anchor_epoch=c.anchor_epoch,N_u=float(native['N'][j]),low20_u=float(native['low20'][j]),u_close=float(native['values'][j,3]),lifecycle_index=effective,entry_capacity_qty=entry,u_gross_capacity_qty=gross,score=float(c.score),source_lifecycle_index=source,voluntary_boundary_index=bounds[epoch]['K_index'],effective_lifecycle_index=effective,effective_boundary_origin=origin)
        h.fields(signals.loc[c.chosen_action_id].to_dict(),want,'cash selected causal signal')
    signals['planned_execution_date']=[dates[int(u)+1] for u in signals.u_index]
    family=diag._read(Path(artifacts['family_year_including_zero.csv.gz']['path']).parent,'family_year_including_zero');families=sorted(mothers.family_id.unique())
    accounts={(a['window'],a['cost']):a for a in manifest['accounts']};assert set(accounts)=={(w,c) for w in WINDOWS for c in COSTS}
    controls={(a['window'],a['cost']):a for a in refs['control_accounts']}
    baseline=doc(refs['small_identity_bindings']['157']);baseline_reports=doc(baseline['diagnostics'])
    metrics={};daily={};reviews=[];annual=[];points=[];dists=table(artifacts['bootstrap_distributions.csv.gz']);savedcomp=table(artifacts['comparisons.csv.gz'])
    savedannual=table(artifacts['paired_annual.csv.gz']);savedmetrics=table(artifacts['account_summaries.csv.gz'])
    for w in WINDOWS:
        ib=dep['bootstrap_indices_optional_if_paired_CI_retained'][w];assert ib==execution['bootstrap_indices'][w];stat(ib);indices=np.load(ib['path'],allow_pickle=False)
        for cost in COSTS:
            a=accounts[(w,cost)];name=f'NARROW_{ARM}_{w}_{cost}';assert a['account_id']==name and a['candidate']==ARM
            folder=Path(a['directory']);summary=doc(a['summary']);assert set(a['ledgers'])==set(h.LEDGERS)
            for b in a['ledgers'].values():h.verify(b)
            with h.cash_context(r,cash,cash.csv(folder/'positions.csv.gz')):
                arithmetic=cash.review_account(folder,cost,dict(id=w,start=execution['cash']['windows'][w][0],end=execution['cash']['windows'][w][1]),execution,signals,economics,dates,.25)
                native=r.account_native_and_capacity(folder,signals,mothers,store,economics,native_summary_alias(summary),cost)
            report=json.loads((folder/'diagnostics.json').read_text());sf=family.loc[family.arm.eq(ARM)&family.window.eq(w)&family.cost.eq(cost)]
            d,log,numbers,fy=diag._account(folder,summary,report,sf,families);diag._daily_summary(d,summary,1000000.)
            roots=pd.concat([cash.csv(folder/'closed.csv.gz'),cash.csv(folder/'open.csv.gz')],ignore_index=True)
            for root in roots.to_dict('records'):h.check_root_boundary(root,signals.to_dict('index'))
            row=savedmetrics.loc[savedmetrics.account_id.eq(name)];assert len(row)==1;h.fields(row.iloc[0].to_dict(),{k:v for k,v in summary.items() if not isinstance(v,(dict,list))},'candidate metrics')
            # Slippage is embedded in fills, never subtracted again from equity.
            fills=cash.csv(folder/'fills.csv.gz');cash.numeric(fills,['fill_price','reference_price','qty']);known=0.;unknown=0
            for f in fills.to_dict('records'):
                tick=economics[f['epoch']].get('tick_size')
                if r.positive(tick):known+=abs(f['fill_price']-f['reference_price'])/float(tick)*f['qty']
                else:unknown+=1
            h.scalar_compare(summary['slippage_tick_lots_known'],known,'ticklots');assert summary['unknown_tick_fills']==unknown
            metrics[(w,cost)]=summary;daily[(w,cost)]=d
            old=controls[(w,cost)];control=doc(old['summary']);db=old['daily'] if 'daily' in old else dict(old['ledgers_relative_to_directory']['daily'],path=str(Path(old['directory'])/'daily.csv.gz'))
            if 'file' in db:db={k:db[k] for k in ('path','bytes','sha256')}
            cd=pd.read_csv(db['path'],float_precision='round_trip');assert d.date.tolist()==cd.date.tolist();diag._daily_summary(cd,control,1000000.)
            ca=np.asarray(d.equity,float);co=np.asarray(cd.equity,float);assert np.isfinite(ca).all() and np.isfinite(co).all() and (ca>0).all() and (co>0).all()
            delta=np.diff(np.log(np.r_[1000000.,ca]))-np.diff(np.log(np.r_[1000000.,co]));assert indices.shape==(2000,len(delta)) and indices.dtype.kind in 'iu'
            distribution=delta[indices].mean(axis=1);lo,hi=np.quantile(distribution,[.025,.975])
            p=dict(window=w,cost=cost,ending_equity_difference=summary['ending_equity']-control['ending_equity'],sharpe_difference=None if summary['sharpe'] is None or control['sharpe'] is None else summary['sharpe']-control['sharpe'],active_total_return_pct=summary['total_return_pct'],return_percentage_point_difference=summary['total_return_pct']-control['total_return_pct'],drawdown_percentage_point_difference=summary['max_drawdown_pct']-control['max_drawdown_pct'],mean_daily_log_difference=float(delta.mean()),cumulative_log_difference=float(delta.sum()),ci95_low=float(lo),ci95_high=float(hi))
            row=savedcomp.loc[savedcomp.window.eq(w)&savedcomp.cost.eq(cost)];assert len(row)==1;h.fields(row.iloc[0].to_dict(),p,'independent paired CI/metrics');h.compare(dists[w+'_'+cost].astype(float),distribution,'paired bootstrap distribution',atol=1e-12,rtol=1e-12)
            aa={a['year']:a for a in report['annual_slices']};bb={a['year']:a for a in baseline_reports[old['account_id']]['annual_slices']};assert set(aa)==set(bb)
            for year in sorted(aa):
                x,y=aa[year],bb[year];yr=dict(window=w,cost=cost,year=year,candidate_growth_amount=x['cash_growth'],control_growth_amount=y['cash_growth'],growth_amount_difference=x['cash_growth']-y['cash_growth'],candidate_return_pct=x['return_pct'],control_return_pct=y['return_pct'],drawdown_percentage_point_difference=x['max_drawdown_pct']-y['max_drawdown_pct'])
                row=savedannual.loc[savedannual.window.eq(w)&savedannual.cost.eq(cost)&savedannual.year.eq(year)];assert len(row)==1;h.fields(row.iloc[0].to_dict(),yr,'paired annual');annual.append(yr)
            points.append(p);review=dict(account_id=name,ledger=arithmetic,native=native,diagnostics=numbers,roots=len(roots));reviews.append(review);write(out/(name+'.json'),review)
            print(json.dumps(dict(phase='new_book_reviewed',account=name)),flush=True)
    gate=independent_gate(points,annual,held);savedgate=doc(artifacts['decision.json']);h.fields(savedgate,{k:v for k,v in gate.items() if not isinstance(v,dict)},'fixed432 gate')
    h.nested(savedgate['predicates'],gate['predicates'],'fixed four account gates');assert savedgate['held_known_mean_nonnegative']==gate['held_known_mean_nonnegative']
    assert stat(cb)==before
    return dict(status='completed',new_books_verified=4,accounts=reviews,points=points,gate=gate,native_cache_reads=1,old_control_replays=0,old_control_fill_reaudits=0,SQL=0)


def actual(auth,out):
    out.mkdir(parents=True,exist_ok=False);began=time.monotonic()
    try:
        protocol=doc(binding(PROTOCOL));fit=doc(auth['fit_manifest']);h=load('stage158_voluntary_review.py');r,cash,diag=h.helpers()
        if auth.get('cash_only_continuation'):
            # The previous process completed model/score/held review before its
            # old132 vocabulary KeyError. Reuse that persisted phase, never run
            # the 1.9m stream or the model anchors again for a cash schema fix.
            model=doc(auth['model_phase_receipt'])
            assert model['status']=='completed' and model['folds']==6 and model['prediction_rows']==1933480
            assert model['all_new_K_choices_checked']==322028 and model['changed_main_parent_choices']==fit['changed_main_parent_choices']
            assert model['model_refits']==0 and auth['cash_manifest']
            for b in fit['source_bundle']:assert binding(b['path'])==b
            cal=np.load(protocol['inputs']['calendar']['path'],allow_pickle=False)
            dates=[str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in cal] if cal.dtype.kind in 'iu' else cal.astype('datetime64[D]').astype(str).tolist()
            mothers=table(protocol['inputs']['mothers'],False,usecols=IDENTITY);h.numeric(mothers,['sequence_index','u_index'])
            assert len(mothers)==399252 and mothers.event_id.is_unique and mothers.family_id.nunique()==95
            choice=table(fit['artifacts']['choices_main']);h.numeric(choice,['sequence_index','u_index','selected','chosen_action_sequence_index','score'])
            choices={'choices_main':choice};held=doc(fit['artifacts']['held_diagnostic'])
            write(out/'reused_model_phase.json',dict(receipt=auth['model_phase_receipt'],original_phase_retained=True,model_score_or_held_rerun=False))
        else:model,mothers,dates,choices,held=review_models(protocol,fit,h,r,out)
        cash_receipt=None
        if auth.get('cash_manifest'):cash_receipt=review_cash(protocol,fit,doc(auth['cash_manifest']),h,r,cash,diag,mothers,dates,choices,held,out)
        receipt=dict(schema='stage435_fixed_hgb_independent_review_v1',status='completed',core_blockers=0,protocol_sha256=PROTOCOL_SHA,fit_manifest=auth['fit_manifest'],cash_manifest=auth.get('cash_manifest'),source_bundle=source_bundle(),model=model,cash=cash_receipt,
            model_phase_receipt_reused=auth.get('model_phase_receipt'),cash_only_continuation=bool(auth.get('cash_only_continuation')),new_fit=0,new_cash=0,SQL=0,API=0,large_old_rehashes=0,elapsed_seconds=time.monotonic()-began,numerical_errors=h.ERRORS,accepted132_errors=r.ERRORS,
            limits=['Bounded training prefix anchors plus source-inspected original mature row/Y/w use, not full old label/weight regeneration.','Portable and sklearn compared on 64 author training anchors and 16 independent new forward anchors per fold, not a second full prediction pass.','Repeated historical hypothesis/learner selection and missing untouched new OOS remain; arithmetic acceptance is not alpha, production or increased-betting qualification.','Held original first-exitR and K cash are distinct estimands; differential unknowns remain unknown.'],remaining_core_problems=[],production_qualified=False,increased_betting_qualified=False,goal_complete=False)
        write(out/'review_receipt.json',receipt);write(out/'terminal.json',dict(status='completed',exit_code=0,elapsed_seconds=time.monotonic()-began));print(json.dumps(dict(status='completed',core_blockers=0,new_books_verified=0 if cash_receipt is None else 4)),flush=True)
    except BaseException as exc:
        write(out/'failure.json',dict(status='failed',error=str(exc),traceback=traceback.format_exc(),auto_retry=False));raise


def main():
    p=argparse.ArgumentParser();p.add_argument('--authorization',required=True);p.add_argument('--authorization-sha256',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    ab=binding(a.authorization);assert ab['sha256']==a.authorization_sha256;auth=doc(ab);out=Path(a.output).resolve()
    assert binding(PROTOCOL)['sha256']==PROTOCOL_SHA and not out.exists() and LINE/'outputs/stage435_fixed_hgb_review' in out.parents
    assert auth['schema']=='stage435_exact_root_review_authorization_v1' and auth['authorized_by']=='root' and auth['protocol_sha256']==PROTOCOL_SHA and auth['source_bundle']==source_bundle() and auth['output']==str(out)
    actual(auth,out)


if __name__=='__main__':main()
