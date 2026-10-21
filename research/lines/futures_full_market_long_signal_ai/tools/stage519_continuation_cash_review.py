"""Independent saved-ledger review for the four Stage517 continuation books.

Import performs no data I/O. Actual mode is once-only and requires an exact
root authorization. No fits, cash replay, SQL, original labels or COMMON reads.
"""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
import hashlib
import importlib.util
import inspect
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
PROTOCOL_SHA = 'd90a160e62ae460a16dabb867e2a7495aceda59ebbd6b5e7487d5ee1084bb32a'
ARM = 'C_CONTINUATION_EXIT'
WINDOWS = ('primary_2020', 'cold_2023')
COSTS = ('base', 'stress')


def load(name):
    s = importlib.util.spec_from_file_location('review519_'+name[:-3], TOOLS/name)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


base = load('stage500_member_identity_cash_review.py')
binding, same, safe, write = base.binding, base.same, base.safe, base.write
compare, number = base.compare, base.number


class Reader(base.Reader):
    def table(self,b):
        path=str(Path(b['path']).resolve())
        if path not in self.tables:
            try:
                self.tables[path]=pd.read_csv(io.BytesIO(self.read(b)),compression='gzip' if path.endswith('.gz') else None,dtype=str,keep_default_na=False,float_precision='round_trip')
            except pd.errors.EmptyDataError:
                self.tables[path]=pd.DataFrame()
        return self.tables[path].copy()


def source_bundle():
    return sorted([binding(TOOLS/n) for n in [Path(__file__).name,
        'test_stage519_continuation_cash_review.py', 'stage500_member_identity_cash_review.py',
        'stage132_contract_choice_review.py', 'stage102_cash_adapter.py',
        'stage102_cash_core.py', 'stage102_cash_diagnostics.py']], key=lambda b:b['path'])


def missing(v):
    return v is None or str(v) == '' or isinstance(v, (float,np.floating)) and not np.isfinite(v)


def num(v):
    return float('nan') if missing(v) else float(v)


def truth(v):
    assert str(v).lower() in ('true','false','0','1'), ('invalid boolean',v)
    return str(v).lower() in ('true','1')


def schema(frame, required):
    """Add empty-table columns only; never silently invent nonempty fields."""
    absent=set(required)-set(frame)
    assert not absent or frame.empty, ('required nonempty columns absent', sorted(absent))
    for c in absent: frame[c]=pd.Series(dtype=str)
    return frame


def ledger_table(reader,path):
    frame=reader.path_table(path)
    required={
        'fills.csv.gz':['root_id','event_id','family_id','product_id','epoch','date','side','qty','reference_price','fill_price','entry_fill','multiplier','fee','slippage','realized_gross','margin_rate','risk_per_lot','budget_id','reason'],
        'positions.csv.gz':['root_id','event_id','product_id','date','family_id','epoch','qty','entry_fill','entry_reference','mark','multiplier','margin_rate','risk_per_lot','SL0','boundary_next','unrealized','notional','stale_days','mark_state','force_next','reduce_to_next','voluntary_requested_next','voluntary_request_date'],
        'closed.csv.gz':['root_id','net_pnl','exit_date','entry_date'],
        'open.csv.gz':['root_id','qty','state'],
        'entry_execution_unknown.csv.gz':['budget_id','event_id','date']}
    return schema(frame,required.get(Path(path).name,[]))


def signal_execution_dates(signals, calendar):
    """Accepted signal schema stores D_index, not a redundant date string."""
    frame=signals.copy()
    planned=[calendar[int(k)+1] for k in frame.u_index]
    if 'planned_execution_date' in frame:
        assert frame.planned_execution_date.tolist()==planned
    if 'D_index' in frame:
        assert pd.to_numeric(frame.D_index).tolist()==[int(k)+1 for k in frame.u_index]
    frame['planned_execution_date']=planned
    return frame


def compare_fields(actual, expected, label):
    for field,val in expected.items():
        assert field in actual,(label,field,'absent')
        if missing(val): assert missing(actual[field]),(label,field,'missing')
        elif isinstance(val,(str,bool,np.bool_)):
            assert str(actual[field]).lower()==str(val).lower(),(label,field,actual[field],val)
        else: compare(num(actual[field]),val,label+'.'+field)


def raw_features(state):
    """Independent six causal scalars; future targets must be actual dates."""
    mark,sl,boundary,close,previous,n,risk,age=(num(state.get(k)) for k in
        ('mark','SL0','boundary_next','close','previous_close','N_t','R0','age_source_days'))
    x=np.full(6,np.nan)
    if np.isfinite(risk) and risk>0:
        x[:4]=((mark-sl)/risk,(mark-boundary)/risk,(close-previous)/risk,n/risk)
    x[4]=age
    dates=[state.get(k) for k in ('source_lifecycle_target_date','K_target_date','t_date')]
    try:
        if all(dates):x[5]=(min(date.fromisoformat(str(dates[0])[:10]),date.fromisoformat(str(dates[1])[:10]))-date.fromisoformat(str(dates[2])[:10])).days
    except (ValueError,TypeError): pass
    x[~np.isfinite(x)]=np.nan
    return x


def portable_prediction(models, day, state):
    cutoff=None if day<'2020-01-01' else '2020-01-01' if day<'2023-01-01' else '2023-01-01'
    if cutoff is None:return None,None,'before_first_cutoff_hold'
    m=models.get('main|'+cutoff)
    if m is None:return None,cutoff,'missing_head_hold'
    raw=raw_features(state);missing_x=~np.isfinite(raw)
    means,scales,coef=np.asarray(m['mean']),np.asarray(m['scale']),np.asarray(m['coef'])
    assert means.shape==scales.shape==(6,) and coef.shape==(13,)
    assert np.isfinite(means).all() and np.isfinite(scales).all() and (scales>0).all() and np.isfinite(coef).all()
    z=(raw-means)/scales;z[missing_x]=0.
    y=float(np.dot(np.r_[1.,z,missing_x.astype(float)],coef))
    return (y,cutoff,'predicted') if np.isfinite(y) else (None,cutoff,'nonfinite_prediction_hold')


def free_close(stale, force, latched, target, qty):
    return not (stale or force or latched or not missing(target) and float(target)<float(qty))


def next_exit_reason(force, actual_reduction, voluntary, op, low, boundary):
    if force:return force
    if actual_reduction:return 'risk_margin_joint_reduction'
    if voluntary:return 'ai_continuation_next_open_exit'
    if op<=boundary:return 'gap_stop'
    if low<=boundary:return 'stop_boundary'
    return None


def restore_native(r,c,calendar,old):
    deps=c['input_bindings'];meta=r.doc(deps['native_cache_manifest'])
    assert same(meta['file'],deps['native_cache'])
    store=old.NativeBars(calendar)
    with np.load(io.BytesIO(r.read(deps['native_cache'])),allow_pickle=False) as z:
        epochs=z['epochs'].tolist();offsets=z['offsets']
        arrays={k:z[k] for k in ('days','values','accepted','valid','N','low20','run')}
        assert len(epochs)==9520 and int(offsets[-1])==1552456 and int(offsets[0])==0
        for i,e in enumerate(epochs):
            a,b=map(int,offsets[i:i+2]);store.series[e]={k:v[a:b] for k,v in arrays.items()}
    return store


def frozen_entry_choices(r,binding0,signals):
    cols=['selected','event_id','chosen_action_id','chosen_epoch','u_date','u_index',
        'product_id','family_id','reference_epoch','anchor_epoch','chosen_action_sequence_index',
        'sequence_index','score','arm','policy','scope']
    source=pd.read_csv(io.BytesIO(r.read(binding0)),compression='gzip',usecols=cols,
        dtype=str,keep_default_na=False,float_precision='round_trip')
    assert len(source)==161014 and source.event_id.is_unique
    assert set(source.arm)=={'VOLUNTARY_RESELECT'} and set(source.scope)=={'main'} and set(source.policy)=={'NARROW'}
    number(source,['selected','u_index','chosen_action_sequence_index','sequence_index','score'])
    assert source.selected.isin([0,1]).all()
    selected=source.loc[source.selected.eq(1)].set_index('chosen_action_id',verify_integrity=True)
    assert set(selected.index)==set(signals.index) and len(selected)==len(signals)
    for action,s in signals.iterrows():
        old=selected.loc[action]
        for sf,of in [('mother_event_id','event_id'),('reference_epoch','chosen_epoch'),('anchor_epoch','anchor_epoch'),
                ('product_id','product_id'),('family_id','family_id'),('u_date','u_date')]:
            assert s[sf]==old[of],('frozen entry identity',action,sf)
        for sf,of in [('u_index','u_index'),('action_sequence_index','chosen_action_sequence_index'),('score','score')]:
            compare(num(s[sf]),old[of],'frozen entry '+sf,1e-12,1e-12)
        assert old.score>0 and old.reference_epoch==old.anchor_epoch
    return dict(original_main_choice_reads=1,choice_rows=len(source),selected_actions=len(selected),
        source_fields=cols,choices_changed=0,source_old_full_score_reads=0)


def native_review(r,folder,signals,refs,store,economics,summary,cost,models,old,cash):
    fills=cash.csv(folder/'fills.csv.gz');positions=cash.csv(folder/'positions.csv.gz')
    closed=cash.csv(folder/'closed.csv.gz');opened=cash.csv(folder/'open.csv.gz')
    roots=pd.concat([closed,opened],ignore_index=True).set_index('root_id',verify_integrity=True)
    audit=r.path_table(folder/'continuation_audit.csv.gz')
    schema(audit,['root_id','date','discretionary','requested','latched_prior'])
    assert not audit.duplicated(['root_id','date']).any()
    assert len(audit)==len(positions)
    assert set(zip(audit.root_id,audit.date))==set(zip(positions.root_id,positions.date))
    number(fills,['qty','reference_price']);number(positions,['qty','mark','SL0','boundary_next','stale_days'])
    pos=positions.set_index(['root_id','date'],verify_integrity=True)
    ai=audit.set_index(['root_id','date'],verify_integrity=True)
    index=store.index;forced=free=requests=0
    for root_id,root in roots.to_dict('index').items():
        sig=signals.loc[root['event_id']]
        assert root['epoch']==sig.reference_epoch and root['anchor_epoch']==sig.anchor_epoch
        compare(num(root['SL0']),num(root['entry_reference'])-.25*sig.N_u,'root fixed SL0',1e-10,1e-11)
        compare(num(root['R0']),.25*sig.N_u,'root fixed R0')
        assert root['source_lifecycle_target_date']==sig.source_lifecycle_target_date and root['K_target_date']==sig.K_target_date
        expiry=min(int(np.searchsorted(store.calendar,sig.source_lifecycle_target_date)),int(np.searchsorted(store.calendar,sig.K_target_date)))
        assert int(float(root['expiry']))==expiry and index[root['entry_date']]<expiry
    for row in positions.to_dict('records'):
        root=roots.loc[row['root_id']];sig=signals.loc[row['event_id']];k=index[row['date']]
        bar=store.get((row['epoch'],row['date']));valid=old.legal_bar(bar)
        prior_day=store.calendar[k-1] if k else ''
        previous=pos.loc[(row['root_id'],prior_day)] if (row['root_id'],prior_day) in pos.index else None
        record=ai.loc[(row['root_id'],row['date'])]
        old_latch=truth(previous.voluntary_requested_next) if previous is not None else False
        if row['mark_state']=='stale':
            assert not valid and row['force_next']=='research_deferred_liquidation'
            assert previous is not None
            compare(row['mark'],num(previous.mark),'stale mark retention',0,0)
            compare(row['boundary_next'],num(previous.boundary_next),'stale boundary retention',0,0)
        else:
            assert valid
            compare(row['mark'],bar[3],'native mark',0,0)
            s=store.series[row['epoch']];j=store.locate(row['epoch'],k)
            compare(row['boundary_next'],max(num(root.SL0),float(s['low20'][j])),'native next boundary',1e-10,1e-11)
            prior_boundary=num(previous.boundary_next) if previous is not None else max(num(root.SL0),sig.low20_u)
            assert previous is None or not previous.force_next
            assert not old_latch,('latched valid next-open exit omitted',row['root_id'],row['date'])
            assert bar[0]>prior_boundary and bar[2]>prior_boundary,('stop omitted',row['root_id'],row['date'])
            expected=old.map_request(old.request(None,sig.anchor_epoch,refs.get((row['product_id'],k),''),k+1,int(float(root.expiry))))
            assert (row['force_next'] or None)==expected
        target=row.get('reduce_to_next','');stale=row['mark_state']=='stale'
        expected_free=free_close(stale,row['force_next'],old_latch,target,row['qty'])
        assert int(record.discretionary)==int(expected_free)
        assert int(record.latched_prior)==int(old_latch)
        for f in ('event_id','epoch','family_id'):assert record[f]==row[f]
        compare_fields(record,dict(t_index=k,qty=row['qty'],stale=int(stale),force_next=row['force_next'],reduce_to_next=target),'audit eligibility')
        expected_D=store.calendar[k+1] if k+1<len(store.calendar) else None
        compare_fields(record,dict(planned_execution_date=expected_D),'audit planned D')
        requested=False
        if expected_free:
            free+=1;s=store.series[row['epoch']];j=store.locate(row['epoch'],k)
            previous_native=store.get((row['epoch'],prior_day)) if k else None
            state=dict(mark=row['mark'],SL0=row['SL0'],boundary_next=row['boundary_next'],close=bar[3],
                previous_close=previous_native[3] if old.legal_bar(previous_native) else None,N_t=float(s['N'][j]),
                R0=num(root.R0),age_source_days=k-index[root.entry_date]+1,
                source_lifecycle_target_date=sig.source_lifecycle_target_date,K_target_date=sig.K_target_date,t_date=row['date'])
            compare_fields(record,state,'audit causal state')
            pred,cutoff,status=portable_prediction(models,row['date'],state)
            compare_fields(record,dict(prediction=pred,cutoff=cutoff,status=status),'audit portable prediction')
            requested=pred is not None and np.isfinite(pred) and pred<0
            compare(raw_features(record),raw_features(state),'audit six causal features')
        else:
            forced+=1
            compare_fields(record,dict(prediction=None,cutoff=None,status='not_discretionary'),'nonfree hold')
        assert int(record.requested)==int(requested)
        assert truth(row['voluntary_requested_next'])==(old_latch or requested)
        if old_latch or requested:
            reqdate=previous.voluntary_request_date if old_latch else row['date']
            assert row['voluntary_request_date']==reqdate
        else:assert missing(row.get('voluntary_request_date'))
        requests+=requested
    for row in fills.to_dict('records'):
        k=index[row['date']];bar=store.get((row['epoch'],row['date']));assert old.legal_bar(bar)
        sig=signals.loc[row['event_id']];root=roots.loc[row['root_id']]
        if row['side']=='BUY':
            assert row['date']==sig.planned_execution_date
            compare(row['reference_price'],bar[0],'native BUY',0,0)
            assert 2*row['qty']<=old.capacity(store.get((row['epoch'],sig.u_date))[4],economics[row['epoch']]['round_lot'])[0]
            continue
        prior_day=store.calendar[k-1] if k else ''
        prior=pos.loc[(row['root_id'],prior_day)] if (row['root_id'],prior_day) in pos.index else None
        force=(prior.force_next or None) if prior is not None else None
        voluntary=truth(prior.voluntary_requested_next) if prior is not None else False
        boundary=num(prior.boundary_next) if prior is not None else max(num(root.SL0),sig.low20_u)
        reduction=row['reason']=='risk_margin_joint_reduction'
        expected=next_exit_reason(force,reduction,voluntary,bar[0],bar[2],boundary)
        assert row['reason']==expected,('exit priority',row['root_id'],row['date'],row['reason'],expected)
        reference=boundary if expected=='stop_boundary' else bar[0]
        compare(row['reference_price'],reference,'native SELL',1e-10,1e-11)
        if expected=='ai_continuation_next_open_exit':
            assert prior is not None and prior.voluntary_request_date<row['date']
    expected_capacity=old.audit_capacity_rows(fills,store,store.calendar,economics)
    saved=cash.csv(folder/'capacity_audit.csv.gz');assert len(saved)==len(expected_capacity)
    unknown_roots=set()
    for observed,expected in zip(saved.to_dict('records'),expected_capacity):
        f=fills.iloc[expected['fill_sequence_index']]
        for a,b in [('root_id','root_id'),('account_id','account_id'),('epoch','epoch'),('side','side'),('reason','reason')]:assert observed[a]==f[b]
        assert int(observed['fill_sequence'])==expected['fill_sequence_index'] and observed['fill_date']==expected['date'] and observed['capacity_reference_date']==expected['previous_date']
        for a,b in [('capacity_reference_volume','reference_volume'),('capacity_cap_qty','gross_cap'),('prior_same_epoch_day_gross_qty','prior_gross_qty'),('fill_qty','qty'),('cumulative_same_epoch_day_gross_qty','cumulative_gross_qty')]:compare(num(observed[a]),np.nan if expected[b] is None else expected[b],'native gross capacity '+a,0,0)
        assert (observed['capacity_state']=='execution_capacity_unknown')==expected['execution_capacity_unknown']
        if expected['execution_capacity_unknown']:unknown_roots.add(observed['root_id'])
    budgets=cash.csv(folder/'reservations.csv.gz');number(budgets,['qty_cap','D_qty','allocated_risk','allocated_buffered_margin','allocated_fee','existing_qty','target_existing_qty'])
    schema(budgets,['budget_kind','budget_id','D_state','D_qty'])
    for b in budgets.loc[budgets.budget_kind.eq('new_entry')].to_dict('records'):
        sig=signals.loc[b['event_id']];bar=store.get((sig.reference_epoch,b['execution_date']));qty=0;state=b['budget_state']
        if b['qty_cap']>0:
            if not old.legal_bar(bar):state='entry_execution_unknown'
            elif bar[0]<=sig.low20_u:state='stale_breakout_cancel_at_open'
            elif bar[0]-.25*sig.N_u<=0:state='invalid_initial_risk_cancel'
            else:
                e=economics[sig.reference_epoch];R,_,_,buy=cash.estimate(bar[0],sig.N_u,e,cost,.25)
                unit=buy[0]*e['contract_multiplier']*cash.econ_rate(e,cost)+buy[1];L=int(e['round_lot'])
                qty=min(b['qty_cap'],cash.floorlot(b['allocated_risk']/R,L),cash.floorlot((b['allocated_buffered_margin']+b['allocated_fee'])/unit,L))
                state='own_open_allocation_insufficient' if qty==0 else 'entered' if qty==b['qty_cap'] else 'entered_reduced_own_allocation'
        assert b['D_qty']==qty and b['D_state']==state,('entry decision',b['budget_id'],b['D_state'],state)
        actual=fills.loc[fills.side.eq('BUY')&fills.budget_id.eq(b['budget_id'])]
        assert len(actual)==int(qty>0)
        if qty:compare(num(actual.iloc[0].qty),qty,'entry actual qty',0,0)
    for b in budgets.loc[budgets.budget_kind.eq('existing_position_reduction')].to_dict('records'):
        bar=store.get((b['reference_epoch'],b['execution_date']));k=index[b['execution_date']]
        prior=pos.loc[(b['root_id'],store.calendar[k-1])];desired=b['existing_qty']-b['target_existing_qty']
        if not old.legal_bar(bar):assert b['D_state']=='missing_quote_deferred_exit' and b['D_qty']==0
        elif prior.force_next:assert b['D_state']=='forced_full_exit_priority' and b['D_qty']==b['existing_qty']
        elif desired>0:
            assert b['D_state']=='executed_reduction' and b['D_qty']==desired
            actual=fills.loc[fills.side.eq('SELL')&fills.budget_id.eq(b['budget_id'])&fills.reason.eq('risk_margin_joint_reduction')]
            assert len(actual)==1 and num(actual.iloc[0].qty)==desired
        else:assert b['D_state']=='scheduled_reduction' and b['D_qty']==0
    unknown_entry=cash.csv(folder/'entry_execution_unknown.csv.gz')
    schema(unknown_entry,['budget_id','event_id','date'])
    assert set(unknown_entry.budget_id)==set(budgets.loc[budgets.D_state.eq('entry_execution_unknown'),'budget_id'])
    for row in unknown_entry.to_dict('records'):
        sig=signals.loc[row['event_id']]
        assert not old.legal_bar(store.get((sig.reference_epoch,row['date']))) and row['date']==sig.planned_execution_date
        assert not fills.budget_id.eq(row['budget_id']).any()
    for root_id,root in roots.to_dict('index').items():assert truth(root['execution_capacity_unknown'])==(root_id in unknown_roots)
    compare_fields(summary,dict(execution_unknown=bool(unknown_roots or len(unknown_entry)),capacity_unknown_roots=len(unknown_roots),
        entry_execution_unknown=len(unknown_entry),unknown_capacity_fills=sum(x['execution_capacity_unknown'] for x in expected_capacity),
        continuation_close_decisions=free,continuation_exit_requests=requests,
        continuation_actual_exit_fills=int(fills.reason.eq('ai_continuation_next_open_exit').sum())),'native summary')
    warnings=old.rejection_equivalence(budgets,cash.csv(folder/'rejections.csv.gz'))
    return dict(native_fill_references=len(fills),native_position_states=len(positions),
        continuation_audit_rows=len(audit),free_decisions=free,not_discretionary=forced,requests=requests,
        ai_exit_fills=int(fills.reason.eq('ai_continuation_next_open_exit').sum()),capacity_rows=len(saved),
        capacity_unknown_roots=len(unknown_roots),entry_unknown=len(unknown_entry),presentation_warnings=warnings)


def fixed_gate(points,stale,wealth,unknown):
    primary=next(x for x in points if (x['window'],x['cost'])==('primary_2020','stress'))
    own=all(x['active_total_return_pct']>0 for x in points)
    ret=all(x['return_percentage_point_difference']>0 if x is primary else x['return_percentage_point_difference']>=0 for x in points)
    known=all(x['drawdown_percentage_point_difference'] is not None and np.isfinite(x['drawdown_percentage_point_difference']) for x in points)
    dd=known and all(x['drawdown_percentage_point_difference']>0 if x is primary else x['drawdown_percentage_point_difference']>=0 for x in points)
    ci=primary['ci95_low'] is not None and np.isfinite(primary['ci95_low']) and primary['ci95_low']>0
    nominal=bool(own and ret and dd and ci and wealth);financial_unknown=bool(stale or unknown or not known)
    return dict(cash_nominal_pass=nominal,nominal_pass=bool(nominal and not financial_unknown),
        own_returns_positive_all_four=bool(own),return_gate=bool(ret),drawdown_gate=bool(dd),
        primary_daily_log_CI_lower_positive=bool(ci),actual_wealth_positive=bool(wealth),
        any_historical_stale=bool(stale),execution_unknown=bool(unknown),financial_unknown=financial_unknown)


def review(r,p,cm,mr,out):
    c=p['cash_contract'];root=Path(cm['terminal']['path']).parent
    old=load('stage132_contract_choice_review.py');sys.path.insert(0,str(TOOLS))
    cash,diag=old.independent_helpers();old.CASH_HELPER=cash;cash.review_budgets=old.review_capped_budgets
    cash.csv=lambda path:ledger_table(r,path)
    # The pinned helper's sole direct summary read is redirected into this same
    # immutable reader. Its arithmetic is unchanged; no second disk read occurs.
    source=inspect.getsource(cash.review_account);needle="summary=json.loads((directory/'summary.json').read_text())"
    assert source.count(needle)==1
    cash.REVIEW_SUMMARY=lambda path:r.path_doc(path)
    exec(source.replace(needle,"summary=REVIEW_SUMMARY(directory/'summary.json')"),cash.__dict__)
    diag._read=lambda folder,name:base.diagnostic_frame(r.read(r.path_binding(Path(folder)/(name+'.csv.gz'))))
    calendar0=np.load(io.BytesIO(r.read(c['input_bindings']['calendar'])),allow_pickle=False)
    calendar=[str(int(x))[:4]+'-'+str(int(x))[4:6]+'-'+str(int(x))[6:8] for x in calendar0]
    assert len(calendar)==5587 and calendar==sorted(set(calendar))
    store=restore_native(r,c,calendar,old);economics=r.doc(c['input_bindings']['economic_projection'])['instruments']
    models=r.doc(mr['portable_models_binding'])['models']
    signals=r.path_table(root/'signals_C_CONTINUATION_EXIT.csv.gz')
    number(signals,['u_index','N_u','low20_u','u_close','entry_capacity_qty','potential','lifecycle_index'])
    signals=signal_execution_dates(signals,calendar)
    assert signals.event_id.is_unique and not signals.duplicated(['family_id','u_date']).any()
    signals=signals.set_index('event_id',drop=False)
    frozen_entries=frozen_entry_choices(r,c['input_bindings']['A_choices'],signals)
    references=r.path_table(root/'canonical_references.csv.gz')
    assert len(references)==399252 and set(references.columns)=={'product_id','u_index','reference_epoch'}
    assert not references.duplicated(['product_id','u_index']).any() and references.product_id.nunique()==98
    # Canonical families are actual identities, never guessed from product text.
    fy=r.path_table(root/'family_year_including_zero.csv.gz');number(fy,['net_equity_contribution','fee','slippage','fill_count','filled_qty'])
    families=sorted(fy.family_id.unique());assert len(families)==95
    refs={(x.product_id,int(x.u_index)):x.reference_epoch for x in references.itertuples(index=False)}
    for s in signals.itertuples():
        k=int(s.u_index);series=store.series[s.reference_epoch];j=store.locate(s.reference_epoch,k)
        assert j is not None and bool(series['valid'][j]) and int(series['run'][j])>=20
        compare([s.N_u,s.low20_u,s.u_close],[series['N'][j],series['low20'][j],series['values'][j,3]],'selected causal source',1e-10,1e-11)
        assert s.planned_execution_date==calendar[k+1] and k+1<int(s.lifecycle_index)
    reports=r.path_doc(root/'diagnostics.json');summaries={};daily={};counts=[]
    for w in WINDOWS:
        for cost in COSTS:
            name='NARROW_'+ARM+'_'+w+'_'+cost;folder=root/name
            old.ACTIVE_POSITIONS=cash.csv(folder/'positions.csv.gz')
            bounds=dict(id=w,start='2020-01-01' if w=='primary_2020' else '2023-01-01',end='2026-10-16')
            account=cash.review_account(folder,cost,bounds,{},signals,economics,calendar,.25)
            write(out/(name+'_accounting_checkpoint.json'),account)
            native=native_review(r,folder,signals,refs,store,economics,account['summary'],cost,models,old,cash)
            family=fy.loc[fy.arm.eq(ARM)&fy.window.eq(w)&fy.cost.eq(cost)]
            d,_,dc,_=diag._account(folder,account['summary'],reports[name],family,families)
            diag._daily_summary(d,account['summary'],1000000.)
            s=account['summary'];key=ARM,w,cost;summaries[key]=s;daily[key]=d
            counts.append(dict(account_id=name,accounting=account,native=native,diagnostics=dc))
            write(out/(name+'_complete_checkpoint.json'),counts[-1])
            write(out/'core_progress.json',dict(accounts_completed=len(counts),core=counts))
    write(out/'all_four_core_checkpoint.json',dict(accounts=counts,all_four_core_complete=True,native_cache_reads=1))
    # Tail exports and frozen A157 OWN controls. A cash strategy is never rerun.
    for control in c['control_accounts_reused']:
        w,cost=control['window'],control['cost'];name=control['account_id']
        assert name=='NARROW_VOLUNTARY_RESELECT_'+w+'_'+cost and 'stage157_voluntary_cash' in control['directory']
        s=r.doc(control['summary']);b=control['ledgers_relative_to_directory']['daily']
        d=r.table(dict(path=str(Path(control['directory'])/b['file']),bytes=b['bytes'],sha256=b['sha256']))
        number(d,[x for x in d if x not in ('account_id','window_id','scenario','arm','date','ever_insolvent')])
        diag._daily_summary(d,s,1000000.);summaries['A',w,cost]=s;daily['A',w,cost]=d
    own_family=r.table(c['input_bindings']['A157_family_year']);own_family=own_family.loc[own_family.arm.eq('VOLUNTARY_RESELECT')].copy();own_family['arm']='A'
    cols=['net_equity_contribution','fee','slippage','fill_count','filled_qty'];number(own_family,cols)
    keys=['arm','window','cost','family_id','year']
    a=fy.loc[fy.arm.eq('A')].set_index(keys).sort_index();b=own_family.set_index(keys).sort_index()
    assert a.index.tolist()==b.index.tolist()
    for col in cols:compare(a[col],b[col],'A own family '+col)
    totals=r.path_table(root/'family_total_including_zero.csv.gz');number(totals,cols)
    a=fy.groupby(keys[:-1])[cols].sum().sort_index();b=totals.set_index(keys[:-1]).sort_index()
    assert a.index.tolist()==b.index.tolist() and len(b)==8*95
    for col in cols:compare(a[col],b[col],'all family total '+col)
    for key,s in summaries.items():
        part=fy.loc[fy.arm.eq(key[0])&fy.window.eq(key[1])&fy.cost.eq(key[2])]
        assert set(part.family_id)==set(families)
        compare(part.net_equity_contribution.sum(),s['ending_equity']-1000000.,'family cash total',1e-6,1e-11)
    exported=r.path_table(root/'account_summaries.csv.gz');assert len(exported)==8
    for key,s in summaries.items():
        row=exported.loc[exported.arm.eq(key[0])&exported.window.eq(key[1])&exported.cost.eq(key[2])]
        assert len(row)==1
        compare_fields(row.iloc[0],{k:s[k] for k in ['ending_equity','total_return_pct','max_drawdown_pct','sharpe','total_fees','total_slippage','fills','closed_trades','open_positions','closed_net_win_rate']},'summary export')
    annual=r.path_table(root/'annual_slices.csv.gz');control_reports=r.doc(c['input_bindings']['A157_diagnostics'])
    for control in c['control_accounts_reused']:reports[control['account_id']]=control_reports[control['account_id']]
    annual_n=0
    for key,s in summaries.items():
        name='NARROW_VOLUNTARY_RESELECT_'+key[1]+'_'+key[2] if key[0]=='A' else s['account_id']
        wanted=reports[name]['annual_slices'];seen=annual.loc[annual.account_id.eq(name)].sort_values('year');assert len(seen)==len(wanted);annual_n+=len(wanted)
        for observed,expected in zip(seen.to_dict('records'),wanted):compare_fields(observed,expected,'annual export')
    assert len(annual)==annual_n
    through=r.path_table(root/'same_book_through_2025.csv.gz');assert len(through)==8
    for row in through.to_dict('records'):
        d=daily[row['arm'],row['window'],row['cost']];path=np.r_[1000000.,d.loc[d.date.le('2025-12-31'),'equity'].to_numpy(float)]
        compare([num(row[x]) for x in ('ending_equity','total_return_pct','max_drawdown_pct')],
            [path[-1],(path[-1]/1000000.-1)*100,(path/np.maximum.accumulate(path)-1).min()*100],'same-book 2025')
        for field in ('new_account','capital_reset','year_end_liquidation'):assert not truth(row[field])
    indices={w:np.load(io.BytesIO(r.read(b)),allow_pickle=False) for w,b in c['CI_indices'].items()}
    comparisons=r.path_table(root/'comparisons.csv.gz');distribution=r.path_table(root/'bootstrap_distributions.csv.gz')
    paired_annual=r.path_table(root/'paired_annual.csv.gz');assert len(comparisons)==4 and len(distribution)==2000
    points=[]
    for w in WINDOWS:
        for cost in COSTS:
            a,b=summaries[ARM,w,cost],summaries['A',w,cost]
            stats,draw=base.paired(daily[ARM,w,cost],daily['A',w,cost],indices[w])
            q=dict(window=w,cost=cost,active_total_return_pct=a['total_return_pct'],reference_total_return_pct=b['total_return_pct'],
                ending_equity_difference=a['ending_equity']-b['ending_equity'],return_percentage_point_difference=a['total_return_pct']-b['total_return_pct'],
                drawdown_percentage_point_difference=None if b['fills']==0 else a['max_drawdown_pct']-b['max_drawdown_pct'],**(stats or dict(ci95_low=None,ci95_high=None,mean_daily_log_difference=None,cumulative_log_difference=None)))
            saved=comparisons.loc[comparisons.window.eq(w)&comparisons.cost.eq(cost)];assert len(saved)==1
            compare_fields(saved.iloc[0],q,'paired CI/points')
            compare(pd.to_numeric(distribution[w+'_'+cost].replace('',np.nan)),draw,'all bootstrap draws',1e-12,1e-10)
            points.append(q)
            aa={x['year']:x for x in reports[a['account_id']]['annual_slices']}
            bb={x['year']:x for x in reports['NARROW_VOLUNTARY_RESELECT_'+w+'_'+cost]['annual_slices']}
            py=paired_annual.loc[paired_annual.window.eq(w)&paired_annual.cost.eq(cost)];assert len(py)==len(aa)
            for row in py.to_dict('records'):
                for field,value in [('return_percentage_point_difference','return_pct'),('growth_amount_difference','cash_growth'),('drawdown_percentage_point_difference','max_drawdown_pct')]:compare(num(row[field]),aa[row['year']][value]-bb[row['year']][value],'paired annual '+field)
    stale=any(x['stale_days']>0 for x in reports.values());unknown=any(x['execution_unknown'] for x in summaries.values())
    wealth=all(diag._log(d,1000000.) is not None for d in daily.values());gate=fixed_gate(points,stale,wealth,unknown)
    decision=r.path_doc(root/'decision.json')
    for field,value in gate.items():assert decision[field]==value,('fixed gate',field,decision[field],value)
    for field in ('alpha_proved','causal_identification','goal_complete','production_qualified','increased_betting_qualified'):assert decision[field] is False
    tick_checks=[]
    for key,s in summaries.items():
        if key[0]=='A':continue
        fills=cash.csv(root/s['account_id']/'fills.csv.gz');tick_lots=0.;unknown_ticks=0
        for row in fills.to_dict('records'):
            tick=economics[row['epoch']].get('tick_size')
            if old.positive(tick):tick_lots+=abs(num(row['fill_price'])-num(row['reference_price']))/float(tick)*num(row['qty'])
            else:unknown_ticks+=1
        compare(s['slippage_tick_lots_known'],tick_lots,'ticklot slippage');assert s['unknown_tick_fills']==unknown_ticks and s['slippage_already_in_fill_price'] is True
        tick_checks.append(dict(account_id=s['account_id'],tick_lots=tick_lots,unknown_tick_fills=unknown_ticks))
    result=dict(schema='stage519_continuation_cash_review_v1',status='completed',completed=True,
        accounts_checked=4,A_own_daily_only=4,source_model_review_external=True,accounts=counts,
        comparisons=points,gate=gate,tick_slippage=tick_checks,frozen_entries=frozen_entries,bootstrap_cells=4,bootstrap_draws_per_cell=2000,
        full_policy_products=98,full_policy_families=95,observed_child_products=97,observed_child_families=94,
        material_disagreements=0,material_issues=[],native_cache_reads=1,new_fit=0,cash=0,
        native_SQL=0,old_A_replays=0,unknown_preserved=True,historical_adaptive_CI_not_blind=True,
        numeric_errors=dict(new519=base.ERRORS,independent132=old.ERRORS,independent102=cash.ERRORS),
        goal_complete=False,production_qualified=False,increased_betting_qualified=False)
    write(out/'cash_review_phase.json',result);return result


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','cash-manifest','model-review','authorization'):
        ap.add_argument('--'+name,required=True);ap.add_argument('--'+name+'-sha256',required=True)
    ap.add_argument('--output',required=True);args=ap.parse_args(argv)
    out=Path(args.output).resolve();assert LINE/'outputs/stage519_continuation_cash_review' in out.parents and not out.exists()
    r=Reader();docs={};bindings={}
    for k in ('protocol','cash_manifest','model_review','authorization'):
        b=binding(getattr(args,k));assert b['sha256']==getattr(args,k+'_sha256');bindings[k]=b;docs[k]=r.doc(b)
    p,cm,mr,auth=(docs[k] for k in ('protocol','cash_manifest','model_review','authorization'))
    assert bindings['protocol']['sha256']==PROTOCOL_SHA and p['schema']=='stage514_fixed_continuation_ridge_protocol_v1'
    expected=dict(schema='stage519_exact_root_review_authorization_v1',authorized_by='root',stage='cash_review',
        protocol_sha256=PROTOCOL_SHA,output=str(out),actual_run_limit=1,max_native_cache_reads=1,
        max_native_SQL=0,max_fit=0,max_strategy_cash_replays=0,A_choice_reads=1)
    assert all(auth.get(k)==v for k,v in expected.items()),'exact once-only root review authorization required'
    assert same(auth['cash_manifest_binding'],bindings['cash_manifest']) and same(auth['model_review_binding'],bindings['model_review'])
    assert sorted(auth['source_bundle'],key=lambda b:b['path'])==source_bundle()
    recovery=None
    if 'prior_failed_terminal_binding' in auth:
        prior=r.doc(auth['prior_failed_terminal_binding'])
        assert prior['status']=='failed' and prior['completed_core_checkpoints']==[]
        assert prior['error']['type']=='AttributeError' and prior['error']['message']=="'Pandas' object has no attribute 'planned_execution_date'"
        recovery=auth['recovery']
        assert recovery==dict(reason='derived planned execution date adapter only',prior_complete_core_accounts=0,
            current_native_cache_reads_max=1,cumulative_native_cache_reads_max=2,
            current_A_choice_reads_max=1,cumulative_A_choice_reads_max=2,
            new_cash_replays=0,new_fit=0,old_A_replays=0)
    assert cm['status']=='completed' and cm['new_cash_accounts']==4 and cm['new_fit']==0 and cm['old_A_replays']==0
    assert same(cm['metadata']['protocol'],bindings['protocol'])
    assert mr['status']=='completed' and mr['material_disagreements']==0 and mr['coefficient_reconstructions']==6
    assert same(mr['protocol_binding'],bindings['protocol'])
    for d in (p,cm,mr):r.register(d)
    out.mkdir(parents=True);started=time.monotonic();status='failed';error=None;result=None
    write(out/'actual_started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),bindings=bindings))
    try:
        result=review(r,p,cm,mr,out);status='completed'
        result.update(protocol_binding=bindings['protocol'],cash_manifest_binding=bindings['cash_manifest'],
            model_review_binding=bindings['model_review'],authorization_binding=bindings['authorization'],
            bounded_recovery=recovery,native_cache_reads_cumulative=2 if recovery else 1)
        write(out/'review_receipt.json',result)
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());raise
    finally:
        terminal=dict(status=status,elapsed_seconds=time.monotonic()-started,error=error,reads_by_path=r.reads,
            new_fit=0,cash=0,native_SQL=0,old_A_replays=0,automatic_retry=False,
            completed_core_checkpoints=[p.name for p in out.glob('*_complete_checkpoint.json')])
        write(out/'actual_terminal.json',terminal)
        write(out/'manifest.json',dict(schema='stage519_review_manifest_v1',status=status,
            metadata=bindings,source_bundle=source_bundle(),artifacts={p.name:binding(p) for p in out.iterdir() if p.is_file() and p.name!='manifest.json'}))


if __name__=='__main__':main()
