"""Independent Stage675 2015 extension audit; actual requires exact root authority.

Checks saved products, not strategy replay. No estimator fit, linear solve, SQL,
network, old-cash replay, or held model audit. Imports perform no data access.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import traceback
from datetime import datetime, timezone

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
CUTOFF = '2015-01-01'
END = '2026-10-16'
ARM = 'VOLUNTARY_RESELECT'
IDENTITY = ['sequence_index', 'event_id', 'product_id', 'family_id', 'u_date', 'u_index', 'reference_epoch']
SCORE_ID = ['sequence_index', 'action_id', 'mother_sequence_index', 'mother_event_id', 'product_id',
    'family_id', 'u_date', 'u_index', 'reference_epoch', 'anchor_epoch', 'u_action_eligible', 'scope', 'cutoff']
ACTION_ID = [x for x in SCORE_ID if x not in ('scope', 'cutoff')]
ACTION_EXTRA = ['entry_index', 'exit_index', 'label_state', 'label_known_date', 'net_R_stress',
    'action_sequence_index', 'entry_capacity_qty', 'N_u', 'low20_u', 'u_close', 'history_run']
NUMERIC = ['sequence_index', 'mother_sequence_index', 'u_index', 'u_action_eligible', 'entry_index',
    'exit_index', 'net_R_stress', 'action_sequence_index', 'entry_capacity_qty', 'N_u', 'low20_u', 'u_close', 'history_run', 'score']
_VERIFIED = {}
_HELPERS = None
_TABLES = {}
_BINDINGS = {}


def cutoff_for(day):
    assert day >= CUTOFF, 'pre-2015 prediction is outside the contract'
    return CUTOFF if day < '2020-01-01' else '2020-01-01' if day < '2023-01-01' else '2023-01-01'


def training_mask(frame):
    return (frame.u_action_eligible.eq(1) & frame.label_state.eq('closed_complete_bar_model')
        & frame.u_date.lt(CUTOFF) & frame.label_known_date.ne('')
        & frame.label_known_date.lt(CUTOFF) & np.isfinite(frame.net_R_stress))


def check_equations(lhs, rhs, beta):
    lhs, rhs, beta = (np.asarray(x, float) for x in (lhs, rhs, beta))
    assert lhs.shape == (len(beta), len(beta)) and rhs.shape == beta.shape
    assert np.isfinite(lhs).all() and np.isfinite(rhs).all() and np.isfinite(beta).all()
    assert np.allclose(lhs @ beta, rhs, rtol=1e-8, atol=1e-7), 'saved coefficient fails frozen Ridge normal equations'
    return float(np.max(np.abs(lhs @ beta-rhs)))


def binding(path):
    path = Path(path).resolve(); h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())


def verify(item):
    path = Path(item['path']).resolve()
    expected = {k:item[k] for k in ('path', 'bytes', 'sha256')}
    if str(path) not in _VERIFIED:
        _VERIFIED[str(path)] = binding(path)
    assert _VERIFIED[str(path)] == expected, ('binding differs', str(path))
    return path


def payload(item):
    """Read, hash and then parse the same payload; never a separate full scan."""
    path=Path(item['path']).resolve();data=path.read_bytes()
    actual=dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    assert actual=={k:item[k] for k in ('path','bytes','sha256')},('payload differs',str(path))
    _VERIFIED[str(path)]=actual;_BINDINGS[str(path)]=item
    return data


def document(item): return json.loads(payload(item))


def table(item, columns=None):
    path=str(Path(item['path']).resolve())
    if path not in _TABLES:
        _TABLES[path]=pd.read_csv(io.BytesIO(payload(item)),compression='gzip' if path.endswith('.gz') else None,
            dtype=str,keep_default_na=False,float_precision='round_trip')
    frame=_TABLES[path]
    return frame[columns].copy() if columns is not None else frame.copy()


def numeric(frame, columns=NUMERIC):
    for column in columns:
        if column in frame:
            frame[column] = np.asarray([float(x) if str(x) not in ('','None') else np.nan for x in frame[column]],float)
    return frame


def load(name):
    spec = importlib.util.spec_from_file_location('independent676_'+name[:-3], TOOLS/name)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def pure_helpers():
    global _HELPERS
    if _HELPERS is None:
        if str(TOOLS) not in sys.path:sys.path.insert(0,str(TOOLS))
        r, v = load('stage132_contract_choice_review.py'), load('stage158_voluntary_review.py')
        cash, diag = r.independent_helpers()
        _HELPERS = dict(r=r, v=v, cash=cash, diag=diag)
    return _HELPERS


def safe(value):
    if isinstance(value, dict): return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [safe(v) for v in value]
    if isinstance(value, np.generic): return safe(value.item())
    if isinstance(value, float) and not np.isfinite(value): return None
    return value


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(safe(value), stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False); stream.write('\n')


def sources():
    names = ['stage676_2015_independent_review.py', 'test_stage676_2015_independent_review.py',
        'stage132_contract_choice_review.py', 'stage158_voluntary_review.py',
        'stage102_cash_adapter.py', 'stage102_cash_core.py', 'stage102_cash_diagnostics.py']
    return [binding(TOOLS/n) for n in names]


def progress(output, phase, value):
    write(output/(phase+'.json'), value)
    print(json.dumps(dict(phase=phase, completed=True)), flush=True)


def install_ledger_cache(cash,diag):
    """Reuse independently parsed ledgers across the accepted audit functions."""
    empty_required={
        'fills.csv.gz':['root_id','event_id','family_id','product_id','epoch','date','side','qty','reference_price','fill_price','entry_fill','multiplier','fee','slippage','realized_gross','margin_rate','risk_per_lot','budget_id','reason'],
        'positions.csv.gz':['root_id','date','family_id','epoch','qty','entry_fill','entry_reference','mark','multiplier','margin_rate','risk_per_lot','SL0','boundary_next','unrealized','notional','stale_days','mark_state'],
        'closed.csv.gz':['root_id','net_pnl','exit_date','entry_date'],'open.csv.gz':['root_id','qty','state']}
    def cached(path):
        path=Path(path).resolve();assert str(path) in _BINDINGS,('unbound ledger read',str(path))
        frame=table(_BINDINGS[str(path)])
        if frame.empty:
            for c in empty_required.get(path.name,[]):
                if c not in frame:frame[c]=pd.Series(dtype=str)
        return frame
    def diagnostics(directory,name):
        frame=cached(Path(directory)/(name+'.csv.gz'))
        for column in frame:
            if column in ('date','year','family_id'):continue
            try:frame[column]=np.asarray([float(x) if str(x)!='' else np.nan for x in frame[column]],float)
            except (ValueError,TypeError):pass
        return frame
    cash.csv=cached;diag._read=diagnostics


def assert_ids(actual, expected, columns, label):
    assert len(actual) == len(expected), (label, 'row count')
    for column in columns:
        assert actual[column].tolist() == expected[column].tolist(), (label, column)


def source_actions(item, selected_ids):
    """One streamed CSV parse; retain only early train/pred and saved signal rows."""
    columns = list(dict.fromkeys(ACTION_ID+ACTION_EXTRA)); train, early, forward, selected = [], [], [], []
    count = 0
    for chunk in pd.read_csv(io.BytesIO(payload(item)),compression='gzip',usecols=columns,dtype=str,keep_default_na=False,
                            float_precision='round_trip', chunksize=100000):
        numeric(chunk); count += len(chunk)
        t = chunk.loc[training_mask(chunk)]
        if len(t): train.append(t.copy())
        p = chunk.loc[chunk.u_date.ge(CUTOFF)&chunk.u_date.lt('2020-01-01')]
        if len(p): early.append(p.copy())
        f = chunk.loc[chunk.u_date.ge(CUTOFF), ACTION_ID]
        if len(f): forward.append(f.copy())
        s = chunk.loc[chunk.action_id.isin(selected_ids)]
        if len(s): selected.append(s.copy())
    empty = pd.DataFrame(columns=columns)
    return tuple(pd.concat(x, ignore_index=True) if x else empty.copy() for x in (train, early, forward, selected))+(count,)


def review_new_model(manifest, train, early, output, r):
    fold = manifest['fold2015']; scaler = document(fold['scaler']); model = document(fold['portable_model'])
    saved = numeric(table(fold['training_identity_weights']))
    assert len(train) > 0 and len(early) > 0 and train.action_id.is_unique
    assert_ids(saved, train, ['action_id', 'u_date', 'label_known_date', 'family_id', 'product_id'], 'new training identity')
    for c in ('u_action_eligible', 'u_index', 'entry_index', 'exit_index', 'net_R_stress'):
        r.compare(saved[c], train[c], '2015_training_'+c, atol=1e-11)
    w = r.union_weights(train); weights = w['sample_weight']
    for c,k in [('group_id','group_id'), ('group_member_count','group_member_count'),
        ('group_union_length','union_length'), ('group_uniqueness','group_uniqueness'),
        ('base_weight','b_a'), ('day_weight_total','day_weight_total'), ('sample_weight','sample_weight')]:
        r.compare(pd.to_numeric(saved[c]), w[k], '2015_weight_'+c, atol=1e-10)
    groups = table(fold['weight_groups']); assert len(groups) == len(w['groups'])
    for a,b in zip(groups.to_dict('records'), w['groups']):
        assert int(a['group_id']) == b['group_id'] and a['family_id'] == b['family_id'] and a['u_date'] == b['u_date']
        assert json.loads(a['union_intervals']) == b['union_intervals'] and int(a['member_count']) == b['member_count']
        assert int(a['union_length']) == b['union_length']; r.compare(float(a['uniqueness']), b['uniqueness'], '2015_group_uniqueness', atol=1e-10)
    common_binding = manifest['input_bindings']['common']
    with np.load(io.BytesIO(payload(common_binding)), allow_pickle=False) as archive:
        columns = archive['columns'].tolist(); raw = archive['common']
        assert raw.ndim == 2 and raw.shape[1] == 26
        train_raw = raw[train.sequence_index.to_numpy(int)].copy(); early_raw = raw[early.sequence_index.to_numpy(int)].copy()
        del raw
    assert scaler['common']['columns'] == columns and scaler['feature_names'] == columns+[c+'_missing' for c in columns]
    assert scaler['scope'] == model['scope'] == 'main' and scaler['cutoff'] == model['cutoff'] == CUTOFF
    assert model['parameters'] == dict(alpha=1., fit_intercept=True, solver='cholesky') and model['feature_names'] == scaler['feature_names']
    stats = [r.weighted_stats(train_raw[:,j], weights) for j in range(26)]
    for key in ('mean','var','scale','finite_count'):
        r.compare(scaler['common'][key], [x[key] for x in stats], '2015_scaler_'+key, atol=1e-10)
    coef = np.asarray(model['coef'],float); beta = np.r_[coef,float(model['intercept'])]; assert len(coef) == 52
    import joblib
    estimator=joblib.load(io.BytesIO(payload(fold['model'])))
    r.compare(estimator.coef_,coef,'new serialized coefficient',atol=0,rtol=0)
    r.compare(estimator.intercept_,model['intercept'],'new serialized intercept',atol=0,rtol=0)
    assert estimator.alpha==1. and estimator.fit_intercept is True and estimator.solver=='cholesky'
    X = r.head52(train_raw, scaler); Z = np.column_stack([X,np.ones(len(X))])
    lhs = Z.T@(weights[:,None]*Z); lhs[np.arange(52),np.arange(52)] += 1.
    rhs = Z.T@(weights*train.net_R_stress.to_numpy(float)); residual = check_equations(lhs,rhs,beta)
    with np.load(io.BytesIO(payload(fold['normal_equations'])),allow_pickle=False) as ne:
        r.compare(ne['lhs'],lhs,'2015_normal_lhs',atol=2e-6); r.compare(ne['rhs'],rhs,'2015_normal_rhs',atol=2e-6)
        r.compare(ne['coefficient_with_intercept'],beta,'2015_beta',atol=1e-12);r.compare(ne['weight_sum'],weights.sum(),'2015_weight_sum',atol=1e-9)
    del X,Z,train_raw
    scores = numeric(table(fold['new_scores']))
    assert_ids(scores,early,ACTION_ID,'2015 all early prediction identities')
    assert set(scores.scope) == {'main'} and set(scores.cutoff) == {CUTOFF}
    expected = r.head52(early_raw,scaler)@coef+model['intercept']
    r.compare(scores.score,expected,'2015_all_forward_scores',atol=1e-10)
    record = dict(training_rows=len(train),training_dates=train.u_date.nunique(),training_families=train.family_id.nunique(),
        training_groups=len(groups),prediction_children=len(early),max_u_date=train.u_date.max(),
        max_label_known_date=train.label_known_date.max(),normal_equation_max_abs_residual=residual,
        coefficient_solved=False,fit_calls=0,feature_N='own11 rolling mean TR20; label/maturity Wilder20; frozen distinction retained',
        feature_units='COMMON original2N; target net_R_stress .25N; frozen distinction retained')
    for key in ('training_rows','training_dates','training_families','training_groups','prediction_children','max_u_date','max_label_known_date'):
        assert fold[key] == record[key], ('new fit record',key)
    progress(output,'new_model_review',record)
    return scores, record


def review_selection(manifest, mothers, forward, new_scores, output, v, r, choices):
    scores = numeric(table(manifest['combined_scores']))
    expected_parents = mothers.loc[mothers.u_date.ge(CUTOFF)].copy()
    assert scores.action_id.is_unique and choices.event_id.is_unique and set(scores.scope) == {'main'}
    assert_ids(scores,forward,ACTION_ID,'full forward action domain')
    assert_ids(choices,expected_parents,IDENTITY,'full forward parent domain')
    assert choices.selected.isin([0,1]).all() and set(choices.arm) == {ARM} and set(choices.scope) == {'main'}
    assert scores.cutoff.tolist() == [cutoff_for(x) for x in scores.u_date]
    assert choices.cutoff.tolist() == [cutoff_for(x) for x in choices.u_date]
    actual_early = scores.loc[scores.cutoff.eq(CUTOFF)]
    assert_ids(actual_early,new_scores,SCORE_ID,'combined new scores')
    r.compare(actual_early.score,new_scores.score,'combined new numeric scores',atol=0,rtol=0)
    old_binding = manifest['input_bindings'].get('child_scores',manifest['input_bindings'].get('accepted_scores'))
    assert old_binding is not None, 'accepted130 main scores binding required'
    old_parts=[]
    for chunk in pd.read_csv(io.BytesIO(payload(old_binding)),compression='gzip',usecols=SCORE_ID+['score'],dtype=str,keep_default_na=False,float_precision='round_trip',chunksize=100000):
        p=chunk.loc[chunk.scope.eq('main')]
        if len(p):old_parts.append(p.copy())
    old = numeric(pd.concat(old_parts,ignore_index=True)).sort_values('sequence_index',kind='stable')
    reused = scores.loc[scores.u_date.ge('2020-01-01')]
    assert_ids(reused,old,SCORE_ID,'2020/2023 old score reuse')
    r.compare(reused.score,old.score,'old scores byte roundtrip values',atol=0,rtol=0)
    accepted=numeric(table(manifest['input_bindings']['accepted_stage156_choices']),NUMERIC+['selected','chosen_action_sequence_index'])
    overlap=choices.loc[choices.u_date.ge('2020-01-01')]
    assert_ids(overlap,accepted,IDENTITY+['selected','chosen_action_id','chosen_action_sequence_index',
        'chosen_epoch','anchor_epoch','cutoff','selection_state'],'accepted156 forward choice overlap')
    r.compare(overlap.score,accepted.score,'accepted156 exact score overlap',atol=0,rtol=0)
    overlap_saved=document(manifest['overlap_receipt'])
    assert overlap_saved['status']=='identical' and overlap_saved['parent_rows']==len(accepted)
    assert overlap_saved['selected_rows']==int(overlap.selected.sum()) and overlap_saved['old_cash_replayed'] is False
    calendar = manifest['_calendar']; boundaries_document=document(manifest['boundaries'])
    boundaries = boundaries_document['epochs']; proposed={}; observed=set(); chosen_epochs=set(); early_unknown=0
    parent_lookup={int(row.sequence_index):(row.event_id,row.reference_epoch) for row in expected_parents.itertuples(index=False)}
    boundary_cache={}
    for a in scores.to_dict('records'):
        seq=int(a['mother_sequence_index']);parent_id,parent_epoch=parent_lookup[seq]
        assert a['mother_event_id']==parent_id and a['anchor_epoch']==parent_epoch
        assert calendar[int(a['u_index'])]==a['u_date']; observed.add(seq)
        epoch=a['reference_epoch']
        if epoch not in boundary_cache:
            b=v.deadline(epoch,calendar,END);assert epoch in boundaries
            v.nested(boundaries[epoch],b,'all K boundaries');boundary_cache[epoch]=b
        b=boundary_cache[epoch]
        eligible=v.admission(int(a['u_index']),a['u_action_eligible'],a['score'],b,calendar,END)
        early_unknown += eligible['new_eligible'] is None
        if eligible['new_eligible']==1 and (seq not in proposed or v.action_order(a)<v.action_order(proposed[seq])):
            proposed[seq]=a
    winners=v.family_choices(proposed.values())
    for c in choices.to_dict('records'):
        seq=int(c['sequence_index']); p=proposed.get(seq); winner=winners.get(seq)
        assert c['anchor_epoch']==c['reference_epoch'] and c['chosen_action_id']==(winner['action_id'] if winner else '')
        assert int(c['selected'])==int(winner is not None)
        assert c['proposed_action_id']==(p['action_id'] if p else '')
        if winner:
            assert c['chosen_epoch']==winner['reference_epoch'] and int(c['chosen_action_sequence_index'])==int(winner['sequence_index'])
            r.compare(c['score'],winner['score'],'all selected positive scores',atol=0,rtol=0);chosen_epochs.add(c['chosen_epoch'])
        elif int(c['chosen_action_sequence_index'])!=-1:raise AssertionError('unselected action sequence sentinel differs')
    assert len(winners)==int(choices.selected.sum()) and not choices.loc[choices.selected.eq(1)].duplicated(['family_id','u_index']).any()
    record=dict(full_parents=len(choices),full_actions=len(scores),selected=len(winners),unknown_eligibility=early_unknown,
        main_scores_per_cutoff=scores.groupby('cutoff').size().to_dict(),parents_per_cutoff=choices.groupby('cutoff').size().to_dict(),
        selected_per_cutoff=choices.loc[choices.selected.eq(1)].groupby('cutoff').size().to_dict(),
        K_exact_entry_forbidden=True,old_scores_refit=False,old_models_reaudited=False,held_models=0)
    progress(output,'selection_review',record)
    return choices,boundaries,record


def restore_store(manifest,r):
    inputs=manifest['input_bindings']; meta=document(inputs['native_cache_manifest'])
    native=inputs.get('native_cache',meta['file']); assert native==meta['file']
    calendar=manifest['_calendar']; store=r.NativeBars(calendar)
    with np.load(io.BytesIO(payload(native)),allow_pickle=False) as archive:
        epochs=archive['epochs'].tolist(); offsets=archive['offsets'];arrays={k:archive[k] for k in ('days','values','accepted','valid','N','low20','run')}
        assert len(epochs)==meta['native_epochs'] and offsets[-1]==meta['native_rows']
        for i,epoch in enumerate(epochs):store.series[epoch]={k:a[int(offsets[i]):int(offsets[i+1])] for k,a in arrays.items()}
    economics=document(manifest['_bridge']['economic_projection'])['instruments']
    assert set(economics)==set(store.series)
    return store,economics


def review_signals(manifest,choices,actions,boundaries,store,economics,r,v,output):
    saved=numeric(table(manifest['signals']),NUMERIC+['D_index','label_history_ready20','lifecycle_index','u_gross_capacity_qty','potential','source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index'])
    picked=choices.loc[choices.selected.eq(1)]; assert len(saved)==len(picked)
    assert saved.event_id.is_unique and set(saved.event_id)==set(picked.chosen_action_id)==set(actions.action_id)
    by_choice=picked.set_index('chosen_action_id'); by_action=actions.set_index('action_id'); dates=store.calendar
    for sig in saved.to_dict('records'):
        choice=by_choice.loc[sig['event_id']];action=by_action.loc[sig['event_id']];u=int(sig['u_index']);epoch=sig['reference_epoch'];s=store.series[epoch];j=store.locate(epoch,u)
        assert j is not None and s['valid'][j] and s['run'][j]>=20
        gross,entry=r.capacity(s['values'][j,4],economics[epoch]['round_lot'])
        assert entry>=economics[epoch]['round_lot'] and int(sig['entry_capacity_qty'])==entry and int(sig['u_gross_capacity_qty'])==gross
        r.compare([sig['N_u'],sig['low20_u'],sig['u_close']],[s['N'][j],s['low20'][j],s['values'][j,3]],'all signals causal values',atol=1e-10,rtol=1e-12)
        r.compare([action.N_u,action.low20_u,action.u_close],[sig['N_u'],sig['low20_u'],sig['u_close']],'selected original action values',atol=1e-10,rtol=1e-12)
        assert sig['mother_event_id']==choice.event_id and sig['anchor_epoch']==choice.anchor_epoch and sig['cutoff']==cutoff_for(sig['u_date'])
        assert int(sig['D_index'])==u+1 and sig['arm']==ARM and sig['policy']=='NARROW'
        source=r.lifecycle(epoch,economics[epoch],dates);effective,origin=v.effective_boundary(source,boundaries[epoch],u+1)
        assert int(sig['source_lifecycle_index'])==source and int(sig['effective_lifecycle_index'])==int(sig['lifecycle_index'])==effective and sig['effective_boundary_origin']==origin
    lineage=table(manifest['boundary_lineage']);assert lineage.event_id.tolist()==saved.event_id.tolist()
    for column in lineage:
        if column in saved:
            a=lineage[column].fillna('').astype(str).tolist();b=saved[column].fillna('').astype(str).tolist()
            if a!=b:
                if column.endswith('_index'):r.compare(pd.to_numeric(lineage[column],errors='coerce'),saved[column],'boundary_lineage_'+column,atol=0,rtol=0)
                else:assert a==b,('lineage',column)
    progress(output,'signals_review',dict(selected_signals=len(saved),early_signals=int(saved.u_date.lt('2020-01-01').sum()),
        independently_checked_native_eligibility=True,N_warmup_min=int(saved.history_run.min()),all_source_voluntary_effective_boundaries=True))
    saved['planned_execution_date']=[dates[int(u)+1] if int(u)+1<len(dates) else '' for u in saved.u_index]
    return saved.set_index('event_id',drop=False)


def review_books(manifest,signals,mothers,store,economics,protocol,output,r,v,cash,diag):
    accounts=manifest['accounts'];assert len(accounts)==2 and {a['cost'] for a in accounts}=={'base','stress'}
    reports=document(manifest['diagnostics']);family=table(manifest['family_year_including_zero'])
    numeric(family,['net_equity_contribution','fee','slippage','fill_count','filled_qty'])
    summaries=table(manifest['account_summaries']); annual=table(manifest['annual_slices']);curve=table(manifest['curve_data'])
    assert len(summaries)==2 and not annual.duplicated(['account','year']).any()
    families=sorted(mothers.family_id.unique()); results=[];daily_by_cost={}
    for a in accounts:
        name=a['account_id'];folder=Path(a['directory']);cost=a['cost'];summary=document(a['summary'])
        for role,item in a['ledgers'].items():
            assert Path(item['path'])==folder/(role+'.csv.gz');_BINDINGS[str(Path(item['path']).resolve())]=item
        assert set(a['ledgers'])==set(v.LEDGERS) and a['arm']==ARM and summary['cost']==cost
        start=next(day for day in store.calendar if day>=CUTOFF)
        schedule=dict(id=a['window'],start=start,end=END)
        assert schedule['start']>='2015-01-01' and schedule['start']<'2015-02-01' and schedule['end']==END
        with v.cash_context(r,cash,cash.csv(folder/'positions.csv.gz')):
            checked=cash.review_account(folder,cost,schedule,protocol,signals,economics,store.calendar,.25)
            native=r.account_native_and_capacity(folder,signals,mothers,store,economics,summary,cost)
        for role in ('closed','open'):
            for root in cash.csv(folder/(role+'.csv.gz')).to_dict('records'):v.check_root_boundary(root,signals.to_dict('index'))
        saved_family=family.loc[family.arm.eq(ARM)&family.window.eq(a['window'])&family.cost.eq(cost)]
        d,log,numbers,fy=diag._account(folder,summary,reports[name],saved_family,families);diag._daily_summary(d,summary,1000000.)
        rows=annual.loc[annual.account.eq(name)].sort_values('year');assert len(rows)==len(reports[name]['annual_slices'])
        for x,y in zip(rows.to_dict('records'),reports[name]['annual_slices']):v.fields(x,y,'2015 annual summary')
        row=summaries.loc[summaries.account.eq(name)];assert len(row)==1
        v.fields(row.iloc[0].to_dict(),{k:x for k,x in summary.items() if not isinstance(x,(dict,list))},'2015 account summary table')
        assert curve.date.tolist()==d.date.tolist()
        r.compare(curve[cost+'_equity'].map(float),d.equity,'2015 curve equity '+cost,atol=0,rtol=0)
        path=np.r_[1000000.,d.equity.to_numpy(float)]
        drawdown=(path[1:]/np.maximum.accumulate(path)[1:]-1)*100
        r.compare(curve[cost+'_drawdown_pct'].map(float),drawdown,'2015 curve drawdown '+cost,atol=1e-12)
        assert summary['any_historical_stale']==bool(numbers['stale_days']>0)
        result=dict(account_id=name,cost=cost,ledger=checked,native=native,diagnostics=numbers,curve_rows=len(curve))
        progress(output,'book_'+cost,result);results.append(result);daily_by_cost[cost]=d
    assert set(reports)=={a['account_id'] for a in accounts}
    assert all(len(d)==len(curve) for d in daily_by_cost.values())
    return results


def authorize(args):
    output=Path(args.output).resolve();assert not output.exists()
    assert LINE/'outputs/stage676_2015_extension_review' in output.parents
    item=binding(args.manifest);assert item['sha256']==args.manifest_sha256
    ab=binding(args.authorization);assert ab['sha256']==args.authorization_sha256
    auth=document(ab)
    required=dict(schema='stage676_exact_root_review_authorization_v1',authorized_by='root',exact_source_authorized=True,
        output=str(output),manifest=item,source_bundle=sources(),actual_review_max=1,new_fits=0,new_cash_runs=0,new_SQL=0)
    for key,value in required.items():assert auth.get(key)==value,('exact review authority',key)
    return output,item,ab


def actual(args):
    output,mb,ab=authorize(args);output.mkdir(parents=True,exist_ok=False);started=time.monotonic();complete=False
    write(output/'actual_started.json',dict(status='started',at=datetime.now(timezone.utc).isoformat(),manifest=mb,authorization=ab,source_bundle=sources(),new_fits=0,new_cash_runs=0,new_SQL=0))
    try:
        manifest=document(mb);terminal=document(manifest['terminal']);protocol=document(manifest['protocol'])
        assert manifest['protocol']['sha256']=='4d27ee6c708de39d029e6eee87f9b6d0db81aefa66ee271802f486e7fb97aa13'
        assert manifest['input_bindings']==protocol['inputs']
        assert manifest['status']=='completed' and terminal['status']=='completed' and terminal['exit_code']==0
        assert terminal['actual_fit_calls_attempted']==terminal['actual_fit_calls_completed']==1
        assert terminal['cash_accounts_started']==terminal['new_cash_accounts']==2
        assert terminal['native_source_queries']==0 and terminal['new_held_models']==0
        assert manifest['actual_fit_calls_completed']==1 and manifest['new_cash_accounts']==2 and manifest['old_refits']==manifest['old_cash_replays']==0
        assert document(manifest['fit_records'])==[manifest['fold2015']]
        source_receipt=document(manifest['source_read_receipt'])
        assert source_receipt['new_held_models']==source_receipt['old_refits']==source_receipt['old_cash_replays']==source_receipt['new_labels']==source_receipt['downloads']==0
        assert source_receipt['complete_original_mothers_for_canonical'] is True and source_receipt['old_main_scores_reused'] is True
        assert source_receipt['native']['native_source_queries']==0 and source_receipt['native']['database_before']==source_receipt['native']['database_after']
        assert all(item['passes']==1 for item in source_receipt['payloads'])
        for item in manifest['source_bundle']:verify(item)
        h=pure_helpers();r,v,cash,diag=(h[k] for k in ('r','v','cash','diag'))
        install_ledger_cache(cash,diag)
        inputs=manifest['input_bindings'];execution=document(inputs['execution_protocol'])
        bridge=document(inputs['market_protocol'])
        calendar_raw=np.load(io.BytesIO(payload(bridge['calendar'])),allow_pickle=False)
        calendar=([str(int(day))[:4]+'-'+str(int(day))[4:6]+'-'+str(int(day))[6:8] for day in calendar_raw]
            if calendar_raw.dtype.kind in 'iu' else calendar_raw.astype('datetime64[D]').astype(str).tolist())
        assert calendar==sorted(set(calendar))
        manifest['_calendar']=calendar;manifest['_bridge']=bridge
        cash_contract=protocol['cash']
        assert (cash_contract['original_equity'],cash_contract['initial_stop_N'],cash_contract['single_family_risk'],cash_contract['total_planned_risk'],cash_contract['buffered_margin_cap'],cash_contract['margin_buffer'],cash_contract['capacity_participation'])==(1000000,.25,.0025,.02,.25,1.1,.01)
        mothers=numeric(table(inputs['mothers']),['sequence_index','u_index'])
        assert len(mothers)==399252 and mothers.event_id.is_unique and mothers.product_id.nunique()==98 and mothers.family_id.nunique()==95
        choices=numeric(table(manifest['choices_main']),NUMERIC+['selected','chosen_action_sequence_index','proposed_score'])
        selected_ids=set(choices.loc[choices.selected.eq(1),'chosen_action_id'])
        train,early,forward,selected,total_actions=source_actions(inputs['actions'],selected_ids)
        assert set(selected.action_id)==selected_ids and selected.action_id.is_unique
        new_scores,model_review=review_new_model(manifest,train,early,output,r)
        choices,boundaries,selection=review_selection(manifest,mothers,forward,new_scores,output,v,r,choices)
        del train,early,forward,new_scores
        store,economics=restore_store(manifest,r)
        signals=review_signals(manifest,choices,selected,boundaries,store,economics,r,v,output)
        books=review_books(manifest,signals,mothers,store,economics,protocol,output,r,v,cash,diag)
        result=dict(schema='stage676_2015_extension_independent_review_v1',completed=True,C=0,I=0,M=0,
            research_arithmetic_accepted=True,model=model_review,selection=selection,cash_accounts=books,
            source_actions_scanned=total_actions,numeric_max_errors=dict(r.ERRORS,**{'cash_'+k:x for k,x in cash.ERRORS.items()}),
            execution=dict(review_startups=1,full_review_completions=1,new_fits=0,new_cash_runs=0,new_SQL=0,linear_solves=0,
                strategy_replays=0,old_cash_reaudits=0,old_model_reaudits=0,held_models=0,downloads=0),
            caveats=['2015-2019新增前向时段未成为真正未见OOS','2015前有效成熟closed训练是条件样本','早年品种与epoch自然覆盖不同，完整母域保留并非固定98品种同时可交易',
                'rolling TR20特征与Wilder20标签N保持原合同差异','日线成交、历史费用保证金快照和容量unknown仍非生产证明'],
            goal_complete=False,production_qualified=False,increased_betting_qualified=False)
        write(output/'review_receipt.json',result);complete=True
        return dict(completed=True,C=0,I=0,M=0,output=str(output),elapsed_seconds=time.monotonic()-started)
    finally:
        write(output/'actual_terminal.json',dict(status='completed' if complete else 'failed',exit_code=0 if complete else 1,
            elapsed_seconds=time.monotonic()-started,new_fits=0,new_cash_runs=0,new_SQL=0,linear_solves=0,strategy_replays=0,
            error=None if complete else traceback.format_exc()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ('manifest','manifest-sha256','authorization','authorization-sha256','output'):parser.add_argument('--'+option,required=True)
    args=parser.parse_args();print(json.dumps(actual(args),ensure_ascii=False))


if __name__=='__main__':main()
