"""Bounded independent Stage497 saved-cash review; import has no data I/O.

One accepted native-cache read, eight saved books, four A157 own daily curves,
and original paired indices. Never calls a fit, strategy or cash kernel or SQL.
Source/model/argmax certification belongs to the separate Stage498 review.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import pickle
import sys
import time
import traceback
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='d3e3a5430b18ef71293cb950c06c5ef4e68f56d452edad3a8bf2bd343a653918'
ARMS=('B_MEMBER_AVAILABILITY','C_MEMBER_IDENTITY')
WINDOWS=('primary_2020','cold_2023')
COSTS=('base','stress')
CONTRASTS={'B_minus_A':(ARMS[0],'A'),'C_minus_A':(ARMS[1],'A'),'C_minus_B':(ARMS[1],ARMS[0])}
LEDGER_KEYS=dict(fills='fills',reservations='budgets',daily='daily',positions='position_days',
    closed='closed_episodes',open='open_episodes',capacity_audit='capacity_audit',entry_execution_unknown='entry_execution_unknown')
ERRORS={}


def load(name):
    spec=importlib.util.spec_from_file_location('review500_'+name[:-3],TOOLS/name)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def source_bundle():
    names=[Path(__file__).name,'test_stage500_member_identity_cash_review.py','stage490_fomc_economic_review.py',
        'stage132_contract_choice_review.py','stage102_cash_adapter.py','stage102_cash_core.py','stage102_cash_diagnostics.py']
    return sorted([binding(TOOLS/name) for name in names],key=lambda x:x['path'])


def same(a,b):return all(a.get(k)==b.get(k) for k in ('path','bytes','sha256'))


def safe(x):
    if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [safe(v) for v in x]
    if isinstance(x,np.ndarray):return safe(x.tolist())
    if isinstance(x,(np.integer,np.bool_)):return x.item()
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x


def write(path,value):
    Path(path).write_text(json.dumps(safe(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def compare(a,b,label,atol=1e-8,rtol=1e-11):
    x,y=np.asarray(a,float),np.asarray(b,float)
    assert x.shape==y.shape,(label,'shape')
    assert np.array_equal(np.isnan(x),np.isnan(y)),(label,'null')
    assert np.array_equal(np.isfinite(x),np.isfinite(y)),(label,'finite')
    good=np.isfinite(x);delta=np.abs(x[good]-y[good]);maximum=float(delta.max()) if delta.size else 0.
    ERRORS[label]=max(ERRORS.get(label,0.),maximum)
    assert np.all(delta<=atol+rtol*np.abs(y[good])),(label,maximum)


def number(frame,cols):
    for col in cols:
        if col in frame:frame[col]=frame[col].map(lambda x:float(x) if str(x)!='' else np.nan)
    return frame


def diagnostic_frame(raw,compression='gzip'):
    """Match accepted102 diagnostic CSV dtypes from cached bytes, not str table."""
    frame=pd.read_csv(io.BytesIO(raw),compression=compression,
        dtype={'date':str,'year':str,'family_id':str},float_precision='round_trip')
    for col in ('qty','multiplier','fill_price','fee','slippage','realized_gross','net_pnl','unrealized','notional'):
        if col in frame:frame[col]=pd.to_numeric(frame[col],errors='raise')
    return frame


def recovery_contract(authorization,prior,prior_binding,cache_path):
    expected=dict(schema='stage500_dtype_adapter_recovery_v1',prior_terminal_binding=prior_binding,
        current_native_cache_reads_max=1,cumulative_native_cache_reads_max=2,
        prior_complete_cash_review_accounts=0,prior_partial_first_account_recertified=False,
        source_model_held_argmax_reruns=0,fit=0,strategy_cash_replays=0,native_SQL=0)
    assert authorization.get('recovery')==expected,'exact bounded dtype recovery contract required'
    assert prior['status']=='failed' and prior['error']['type']=='TypeError'
    assert prior['error']['message']=="'>' not supported between instances of 'str' and 'int'"
    assert prior['reads_by_path'][cache_path]==1 and all(n==1 for n in prior['reads_by_path'].values())
    assert prior['predictive_fits']==prior['strategy_cash_replays']==prior['native_SQL']==0
    return dict(contract=expected,prior_read_files=prior['reads_by_path'],
        previous_cash_source_model_complete_claim=False,prior_partial_first_account_scope_inherited_as_complete=False,
        current_process_cache_restore_explicitly_additional=True,duplicate_derived_reads_explicit=True)


class Reader:
    def __init__(self):self.bindings={};self.raw={};self.tables={};self.reads=Counter()
    def register(self,value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=set(value):
                path=str(Path(value['path']).resolve())
                if path in self.bindings:assert same(self.bindings[path],value),('different binding',path)
                self.bindings[path]=value
            else:
                for x in value.values():self.register(x)
        elif isinstance(value,list):
            for x in value:self.register(x)
    def read(self,b):
        path=str(Path(b['path']).resolve())
        if path not in self.raw:
            raw=Path(path).read_bytes();assert len(raw)==b['bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256'],path
            self.raw[path]=raw;self.reads[path]+=1
        return self.raw[path]
    def doc(self,b):return json.loads(self.read(b))
    def path_binding(self,path):return self.bindings[str(Path(path).resolve())]
    def path_doc(self,path):return self.doc(self.path_binding(path))
    def table(self,b):
        path=str(Path(b['path']).resolve())
        if path not in self.tables:self.tables[path]=pd.read_csv(io.BytesIO(self.read(b)),compression='gzip' if path.endswith('.gz') else None,dtype=str,keep_default_na=False,float_precision='round_trip')
        return self.tables[path].copy()
    def path_table(self,path):return self.table(self.path_binding(path))


def semantic_raw_table(actual,rows,label):
    """All saved ledger cells must be the completed checkpoint's original cells."""
    expected=pd.DataFrame(rows);assert len(actual)==len(expected),(label,'row count')
    if expected.empty:return
    assert set(actual)==set(expected),(label,'columns',set(actual)^set(expected))
    for col in expected:
        for a,b in zip(actual[col],expected[col]):
            missing=b is None or (np.isscalar(b) and bool(pd.isna(b)))
            if missing:assert a=='',(label,col,'missing');continue
            if isinstance(b,(bool,np.bool_)):assert str(a).lower()==str(bool(b)).lower(),(label,col,'bool')
            elif isinstance(b,(int,float,np.integer,np.floating)):
                compare(float(a),b,label+'.'+col,atol=1e-8,rtol=1e-11)
            else:assert str(a)==str(b),(label,col,'identity')


def paired(daily_a,daily_b,index):
    assert daily_a.date.tolist()==daily_b.date.tolist(),'paired calendar'
    def log(d):
        p=np.r_[1000000.,pd.to_numeric(d.equity).to_numpy(float)]
        unknown=d.ever_insolvent.astype(str).str.lower().isin(['true','1']).any()
        return None if unknown or not np.isfinite(p).all() or (p<=0).any() else np.log(p[1:]/p[:-1])
    a,b=log(daily_a),log(daily_b)
    assert index.shape==(2000,len(daily_a)) and index.dtype.kind in 'iu'
    assert (index>=0).all() and (index<len(daily_a)).all()
    if a is None or b is None:return None,np.full(2000,np.nan)
    diff=a-b;draw=diff[index].mean(axis=1);lo,hi=np.quantile(draw,[.025,.975])
    return dict(ci95_low=float(lo),ci95_high=float(hi),mean_daily_log_difference=float(diff.mean()),cumulative_log_difference=float(diff.sum())),draw


def gate(points,held,*,wealth,stale,execution_unknown):
    passes=[];checks={}
    for q in points:
        strict=(q['window'],q['cost'])==('primary_2020','stress')
        ret=q['return_percentage_point_difference'];dd=q['drawdown_percentage_point_difference'];low=q['ci95_low']
        finite=lambda x:x is not None and np.isfinite(x)
        check=dict(own_positive=finite(q['active_total_return_pct']) and q['active_total_return_pct']>0,
            returns=finite(ret) and (ret>0 if strict else ret>=0),
            drawdown=finite(dd) and (dd>0 if strict else dd>=0),
            primary_CI=(not strict or finite(low) and low>0))
        checks[q['window']+'_'+q['cost']]=check;passes.append(all(check.values()))
    assert set(checks)=={w+'_'+c for w in WINDOWS for c in COSTS}
    assert set(held['groups'])=={'holdout_0','holdout_1'}
    held_known=all(x['known_u_equal_mean_increment_R'] is not None and np.isfinite(x['known_u_equal_mean_increment_R']) and x['known_u_equal_mean_increment_R']>=0 for x in held['groups'].values())
    unknown_counts={g:x['unknown_differential_selected_events'] for g,x in held['groups'].items()}
    assert all(isinstance(v,int) and not isinstance(v,bool) and v>=0 for v in unknown_counts.values())
    cash=bool(all(passes) and wealth);nominal=bool(cash and held_known and not any(unknown_counts.values()) and not stale and not execution_unknown)
    return dict(nominal_pass=nominal,cash_nominal_pass=cash,held_known_nominal_pass=bool(held_known),
        held_unknown=unknown_counts,any_stale=bool(stale),execution_unknown=bool(execution_unknown),checks=checks)


def read_native(r,p,calendar,old):
    deps=p['cash_contract_inherited_exact']['market_dependencies_inherited'];meta=r.doc(deps['native_cache_manifest'])
    assert (meta['native_rows'],meta['native_epochs'])==(1552456,9520)
    store=old.NativeBars(calendar)
    with np.load(io.BytesIO(r.read(deps['native_cache'])),allow_pickle=False) as z:
        epochs=z['epochs'].tolist();offsets=z['offsets'];arrays={k:z[k] for k in ['days','values','accepted','valid','N','low20','run']}
        assert len(epochs)==9520 and offsets[-1]==1552456
        for i,epoch in enumerate(epochs):store.series[epoch]={k:v[int(offsets[i]):int(offsets[i+1])] for k,v in arrays.items()}
    return store


def review(r,p,h,cm,out):
    old=load('stage132_contract_choice_review.py');sys.path.insert(0,str(TOOLS))
    cash,diag=old.independent_helpers();old.CASH_HELPER=cash;cash.review_budgets=old.review_capped_budgets
    # Cash helpers repeatedly request the same ledgers; return independent copies
    # from one hash-checked immutable read, preserving native float conversion.
    cash.csv=r.path_table
    def diagnostic_read(folder,name):
        return diagnostic_frame(r.read(r.path_binding(Path(folder)/(name+'.csv.gz'))))
    diag._read=diagnostic_read
    calendar0=np.load(io.BytesIO(r.read(h['calendar_binding'])),allow_pickle=False)
    calendar=[str(int(x))[:4]+'-'+str(int(x))[4:6]+'-'+str(int(x))[6:8] for x in calendar0]
    assert len(calendar)==5587 and calendar==sorted(set(calendar))
    store=read_native(r,p,calendar,old);economics=r.doc(p['input_bindings']['economic_projection'])['instruments']
    mothers=r.table(h['forward_mothers_projection_binding']);assert len(mothers)==161014 and mothers.event_id.is_unique
    assert mothers.product_id.nunique()==98 and mothers.family_id.nunique()==95 and mothers.product_id.str.split('.').str[0].nunique()==6
    families=sorted(mothers.family_id.unique());causal=r.table(h['causal_actions_projection_binding'])
    assert len(causal)==966740 and causal.action_id.is_unique and len(causal.columns)==16
    number(causal,['action_sequence_index','mother_sequence_index','u_index','u_action_eligible','entry_capacity_qty','N_u','low20_u','u_close'])
    causal=causal.set_index('action_id',drop=False)
    root=Path(cm['terminal']['path']).parent;fy=r.path_table(root/'family_year_including_zero.csv.gz')
    number(fy,['net_equity_contribution','fee','slippage','fill_count','filled_qty'])
    reports=r.path_doc(root/'diagnostics.json');bookmeta=r.path_doc(root/'book_checkpoints.json')
    books={x['spec']['account_id']:x for x in bookmeta['books']};assert len(books)==8
    all_summaries={};all_daily={};all_reports={};counts=[];expected_family=[]
    choices={a:r.table(h['arms'][a]['choices_main_binding']) for a in ARMS}
    for arm in ARMS:
        choice=choices[arm];assert len(choice)==len(mothers) and choice.event_id.tolist()==mothers.event_id.tolist()
        assert choice.candidate.eq(arm).all() and choice.scope.eq('main').all()
        pick=choice.loc[pd.to_numeric(choice.selected).eq(1)];signal=causal.loc[pick.chosen_action_id].copy()
        signal['potential']=1;signal['planned_execution_date']=[calendar[int(k)+1] for k in signal.u_index]
        signal=signal.set_index('event_id',drop=False);assert signal.index.is_unique and not signal.duplicated(['family_id','u_date']).any()
        for q in signal.itertuples():
            s=store.series[q.reference_epoch];j=store.locate(q.reference_epoch,int(q.u_index));assert j is not None and bool(s['valid'][j]) and int(s['run'][j])>=20
            compare([q.N_u,q.low20_u,q.u_close],[s['N'][j],s['low20'][j],s['values'][j,3]],'native causal selected',1e-10,1e-11)
            assert q.u_action_eligible==1
        for window in WINDOWS:
            for cost in COSTS:
                name=f'NARROW_{arm}_{window}_{cost}';folder=root/name
                book=pickle.loads(gzip.decompress(r.read(books[name]['book'])))
                for role,key in LEDGER_KEYS.items():semantic_raw_table(r.path_table(folder/(role+'.csv.gz')),book[key],name+'.'+role)
                semantic_raw_table(r.path_table(folder/'rejections.csv.gz'),[x for x in book['budgets'] if x.get('D_qty',0)==0],name+'.rejections')
                write(out/(name+'_raw_export_phase.json'),dict(account_id=name,raw_book_export_all_cells_checked=True))
                old.ACTIVE_POSITIONS=cash.csv(folder/'positions.csv.gz')
                bounds=p['cash']['windows'][window]
                account=cash.review_account(folder,cost,dict(id=window,start=bounds[0],end=bounds[1]),{},signal,economics,calendar,.25)
                write(out/(name+'_saved_account_phase.json'),account)
                extra=old.account_native_and_capacity(folder,signal,mothers,store,economics,account['summary'],cost)
                write(out/(name+'_native_capacity_phase.json'),extra)
                summary=account['summary'];family=fy.loc[fy.arm.eq(arm)&fy.window.eq(window)&fy.cost.eq(cost)]
                daily,logs,dc,ef=diag._account(folder,summary,reports[name],family,families);diag._daily_summary(daily,summary,1000000.)
                expected_family.append(ef.assign(arm=arm,window=window,cost=cost));key=arm,window,cost
                all_summaries[key]=summary;all_daily[key]=daily;all_reports[name]=reports[name]
                ticklots=0.;unknown_ticks=0
                for fill in book['fills']:
                    tick=economics[fill['epoch']].get('tick_size')
                    if tick is not None and np.isfinite(tick) and tick>0:ticklots+=abs(fill['fill_price']-fill['reference_price'])/tick*fill['qty']
                    else:unknown_ticks+=1
                compare(summary['slippage_tick_lots_known'],ticklots,'all ticklot slippage');assert summary['unknown_tick_fills']==unknown_ticks
                assert summary['slippage_already_in_fill_price'] is True
                count=dict(account_id=name,fills=account['fills_checked'],daily=account['daily_rows_checked'],positions=account['position_rows_checked'],
                    budgets=account['budgets_checked']['rows'],closed=account['closed_roots_checked'],open=account['open_roots_checked'],native_capacity=extra,diagnostics=dc,raw_book_export_all_cells_checked=True)
                counts.append(count);write(out/(name+'_audit.json'),count)
    # A is the four accepted157 own daily curves, not131B and never replayed.
    controls=p['cash_contract_inherited_exact']['control_accounts_reused'];control_reports=r.doc(p['input_bindings']['A157_diagnostics'])
    assert len(controls)==4
    for c in controls:
        name=c['account_id'];assert name=='NARROW_VOLUNTARY_RESELECT_'+c['window']+'_'+c['cost'] and 'stage157_voluntary_cash' in c['directory']
        summary=r.doc(c['summary']);b=c['ledgers_relative_to_directory']['daily'];daily=r.table(dict(path=str(Path(c['directory'])/b['file']),bytes=b['bytes'],sha256=b['sha256']))
        number(daily,[col for col in daily if col not in ['account_id','window_id','scenario','arm','date','ever_insolvent']])
        diag._daily_summary(daily,summary,1000000.);key='A',c['window'],c['cost'];all_summaries[key]=summary;all_daily[key]=daily;all_reports[name]=control_reports[name]
    own_family=r.table(p['input_bindings']['A157_family_year'])
    own_family=own_family.loc[own_family.arm.eq('VOLUNTARY_RESELECT')].copy();own_family['arm']='A'
    family_keys=['arm','window','cost','family_id','year'];family_measures=['net_equity_contribution','fee','slippage','fill_count','filled_qty']
    number(own_family,family_measures)
    expected_A=own_family.set_index(family_keys).sort_index();saved_A=fy.loc[fy.arm.eq('A')].set_index(family_keys).sort_index()
    assert saved_A.index.tolist()==expected_A.index.tolist(),'A157 own family attribution identity'
    for col in family_measures:compare(saved_A[col],expected_A[col],'A157 own family '+col)
    for key,s in all_summaries.items():
        own=fy.loc[fy.arm.eq(key[0])&fy.window.eq(key[1])&fy.cost.eq(key[2])]
        assert set(own.family_id)==set(families) and not own.duplicated(['family_id','year']).any()
        compare(own.net_equity_contribution.sum(),s['ending_equity']-1000000.,'all12 family cash totals',1e-6,1e-11)
    write(out/'all_books_phase.json',dict(new_books=8,A_own_daily_only=4,accounts=counts,source_model_argmax_not_recertified_here=True))
    summaries=r.path_table(root/'account_summaries.csv.gz');assert len(summaries)==12
    for key,s in all_summaries.items():
        saved=summaries.loc[summaries.arm.eq(key[0])&summaries.window.eq(key[1])&summaries.cost.eq(key[2])];assert len(saved)==1
        for col in ['ending_equity','total_return_pct','max_drawdown_pct','sharpe','total_fees','total_slippage','fills','closed_trades','open_positions','closed_net_win_rate']:
            if s.get(col) is None:assert saved.iloc[0][col]==''
            else:compare(float(saved.iloc[0][col]),s[col],'all12 summaries '+col)
    annual=r.path_table(root/'annual_slices.csv.gz');paired_annual=r.path_table(root/'paired_annual.csv.gz')
    for key,s in all_summaries.items():
        expected=all_reports[s['account_id']]['annual_slices'];saved=annual.loc[annual.account_id.eq(s['account_id'])].sort_values('year');assert len(saved)==len(expected)
        for actual,expected_row in zip(saved.to_dict('records'),expected):
            for col,val in expected_row.items():
                if val is None:assert actual[col]==''
                elif isinstance(val,(bool,str)):assert str(actual[col]).lower()==str(val).lower()
                else:compare(float(actual[col]),val,'annual '+col)
    economic_equivalence=[]
    for window in WINDOWS:
        for cost in COSTS:
            left,right=(ARMS[0],window,cost),(ARMS[1],window,cost)
            da,db=all_daily[left],all_daily[right]
            assert da.date.tolist()==db.date.tolist()
            fa=r.path_table(root/f'NARROW_{ARMS[0]}_{window}_{cost}'/'fills.csv.gz')
            fb=r.path_table(root/f'NARROW_{ARMS[1]}_{window}_{cost}'/'fills.csv.gz')
            ids=['event_id','epoch','date','side','reason']
            def ordered(frame):
                frame=frame.copy();frame['_occurrence']=frame.groupby(ids,sort=False).cumcount()
                return frame.set_index(ids+['_occurrence']).sort_index()
            fa,fb=ordered(fa),ordered(fb);identity=fa.index.tolist()==fb.index.tolist();differences={};qty_exact=False
            if identity:
                qty_exact=np.array_equal(pd.to_numeric(fa.qty).to_numpy(float),pd.to_numeric(fb.qty).to_numpy(float))
                for col in ['reference_price','fill_price','fee','slippage','realized_gross']:
                    delta=np.abs(pd.to_numeric(fa[col]).to_numpy(float)-pd.to_numeric(fb[col]).to_numpy(float))
                    differences[col]=float(delta.max()) if len(delta) else 0.
            daily_diff=float(np.max(np.abs(da.equity.to_numpy(float)-db.equity.to_numpy(float))))
            daily_return_diff=float(np.max(np.abs(np.diff(np.r_[1000000.,da.equity.to_numpy(float)])-np.diff(np.r_[1000000.,db.equity.to_numpy(float)]))))
            economic_equivalence.append(dict(window=window,cost=cost,fill_identity_order_ignored_equal=identity,
                identical_fill_identity_fields=ids+['_occurrence'],fill_counts=[len(fa),len(fb)],filled_qty_exact_equal=bool(qty_exact),
                max_abs_fill_money_differences=differences,max_daily_equity_abs_difference=daily_diff,
                max_daily_equity_growth_amount_abs_difference=daily_return_diff,
                economic_equivalent_at_RMB_1e_8=bool(identity and qty_exact and all(v<=1e-8 for v in differences.values()) and daily_diff<=1e-8),
                float_lastbit_not_alpha=True,account_root_and_budget_prefixes_not_compared_as_economic_ids=True))
    write(out/'C_minus_B_economic_equivalence.json',economic_equivalence)
    changed=choices[ARMS[0]].chosen_action_id.ne(choices[ARMS[1]].chosen_action_id)
    choice_cash=[]
    for pos in np.flatnonzero(changed.to_numpy()):
        bx,cx=choices[ARMS[0]].iloc[pos],choices[ARMS[1]].iloc[pos]
        assert bx.event_id==cx.event_id
        event=dict(mother_event_id=bx.event_id,u_date=bx.u_date,product_id=bx.product_id,
            B_chosen_action_id=bx.chosen_action_id,C_chosen_action_id=cx.chosen_action_id,
            B_chosen_epoch=bx.chosen_epoch,C_chosen_epoch=cx.chosen_epoch,accounts=[])
        for window in WINDOWS:
            for cost in COSTS:
                for arm,choice in [(ARMS[0],bx),(ARMS[1],cx)]:
                    folder=root/f'NARROW_{arm}_{window}_{cost}'
                    budgets=r.path_table(folder/'reservations.csv.gz');fills=r.path_table(folder/'fills.csv.gz')
                    budgets=budgets.loc[budgets.event_id.eq(choice.chosen_action_id)]
                    fills=fills.loc[fills.event_id.eq(choice.chosen_action_id)]
                    event['accounts'].append(dict(arm=arm,window=window,cost=cost,choice_action_id=choice.chosen_action_id,
                        budgets=budgets[[col for col in ['budget_id','budget_kind','budget_state','D_state','D_qty','qty_cap','u_date','execution_date'] if col in budgets]].to_dict('records'),
                        filled_rows=len(fills),filled_qty=float(pd.to_numeric(fills.qty).sum())))
        choice_cash.append(event)
    write(out/'C_minus_B_choice_cash_link.json',dict(changed_main_choices=int(changed.sum()),rows=choice_cash,
        choice_argmax_not_recomputed=True,source_model_argmax_validation_separate498=True,only_existing_in_memory_new_choices_and_ledgers=True))
    indices={w:np.load(io.BytesIO(r.read(b)),allow_pickle=False) for w,b in p['statistics']['bootstrap_indices'].items()}
    comp=r.path_table(root/'comparisons.csv.gz');distribution=r.path_table(root/'bootstrap_distributions.csv.gz');assert len(comp)==12 and len(distribution)==2000
    decision=r.path_doc(root/'decision.json');held=r.doc(h['held_gate_binding'])['contrasts'];points={};gates={}
    any_stale=any(x['stale_days']>0 for x in all_reports.values());unknown=any(x.get('execution_unknown',False) for x in all_summaries.values())
    wealth=all(diag._log(d,1000000.) is not None for d in all_daily.values())
    for contrast,(a,b) in CONTRASTS.items():
        points[contrast]=[]
        for window in WINDOWS:
            for cost in COSTS:
                sa,sb=all_summaries[a,window,cost],all_summaries[b,window,cost]
                stats,draw=paired(all_daily[a,window,cost],all_daily[b,window,cost],indices[window]);s=comp.loc[comp.contrast.eq(contrast)&comp.window.eq(window)&comp.cost.eq(cost)];assert len(s)==1;s=s.iloc[0]
                q=dict(contrast=contrast,window=window,cost=cost,active_total_return_pct=sa['total_return_pct'],reference_total_return_pct=sb['total_return_pct'],
                    ending_equity_difference=sa['ending_equity']-sb['ending_equity'],return_percentage_point_difference=sa['total_return_pct']-sb['total_return_pct'],
                    drawdown_percentage_point_difference=None if sb['fills']==0 else sa['max_drawdown_pct']-sb['max_drawdown_pct'],**(stats or dict(ci95_low=None,ci95_high=None,mean_daily_log_difference=None,cumulative_log_difference=None)))
                for col,val in q.items():
                    if col in ('contrast','window','cost'):assert s[col]==val
                    elif val is None:assert s[col]==''
                    else:compare(float(s[col]),val,'paired '+col,1e-10,1e-11)
                observed=pd.to_numeric(distribution[contrast+'_'+window+'_'+cost].replace('',np.nan));compare(observed,draw,'all2000 '+contrast+' '+window+' '+cost,1e-12,1e-10)
                points[contrast].append(q)
                ar={x['year']:x for x in all_reports[sa['account_id']]['annual_slices']};br={x['year']:x for x in all_reports[sb['account_id']]['annual_slices']}
                py=paired_annual.loc[paired_annual.contrast.eq(contrast)&paired_annual.window.eq(window)&paired_annual.cost.eq(cost)];assert len(py)==len(ar)
                for row in py.to_dict('records'):
                    aa,bb=ar[row['year']],br[row['year']]
                    for field,col in [('return_percentage_point_difference','return_pct'),('growth_amount_difference','cash_growth'),('drawdown_percentage_point_difference','max_drawdown_pct')]:compare(float(row[field]),aa[col]-bb[col],'paired annual '+field)
        gates[contrast]=gate(points[contrast],held[contrast],wealth=wealth,stale=any_stale,execution_unknown=unknown)
        for col in ('nominal_pass','cash_nominal_pass','held_known_nominal_pass'):assert decision['contrasts'][contrast][col]==gates[contrast][col],('decision',contrast,col)
        write(out/('CI_'+contrast+'_phase.json'),dict(points=points[contrast],gate=gates[contrast],draws_per_cell=2000,indices_reused=True))
    assert decision['nominal_pass']==(gates['C_minus_A']['nominal_pass'] and gates['C_minus_B']['nominal_pass'])
    for flag in ['alpha_proved','causal_identification','historical_first_seen_PIT_proved','full_market_mechanism_proved','member_is_end_investor_proved',
        'legal_member_identity_continuity_proved','increased_betting_qualified','production_qualified','goal_complete']:assert decision[flag] is False
    through=r.path_table(root/'same_book_through_2025.csv.gz');assert len(through)==12
    for row in through.to_dict('records'):
        d=all_daily[row['arm'],row['window'],row['cost']];d=d.loc[d.date.le('2025-12-31')];path=np.r_[1000000.,d.equity.to_numpy(float)]
        compare([float(row['ending_equity']),float(row['total_return_pct']),float(row['max_drawdown_pct'])],
            [path[-1],(path[-1]/1000000.-1)*100,(path/np.maximum.accumulate(path)-1).min()*100],'samebooks through2025')
        assert row['new_account'].lower()==row['capital_reset'].lower()==row['year_end_liquidation'].lower()=='false'
    # Exact family totals and all95 zero rows are additional exports, not new books.
    totals=r.path_table(root/'family_total_including_zero.csv.gz');keys=['arm','window','cost','family_id'];cols=['net_equity_contribution','fee','slippage','fill_count','filled_qty']
    number(totals,cols);expected=fy.groupby(keys)[cols].sum().sort_index();observed=totals.set_index(keys).sort_index();assert observed.index.tolist()==expected.index.tolist()
    for col in cols:compare(observed[col],expected[col],'all95 totals '+col)
    report=dict(schema='stage500_member_identity_cash_phase_v1',accounts_checked=8,reused_A_own_daily_accounts=4,
        fills_checked=sum(x['fills'] for x in counts),daily_rows_checked=sum(x['daily'] for x in counts),position_rows_checked=sum(x['positions'] for x in counts),
        budgets_checked=sum(x['budgets'] for x in counts),contrasts_checked=12,bootstrap_draws_per_contrast=2000,block_length_inherited=252,
        original_indices_no_regeneration=True,raw_checkpoint_exports_checked=8,account_checks=counts,comparisons=points,gates=gates,
        nominal_pass=decision['nominal_pass'],C_minus_B_economic_equivalence=economic_equivalence,
        unknowns_preserved=True,model_source_held_argmax_review_external=True,
        historical_adaptive_CI_not_blind=True,broker_member_not_end_investor=True,full_market_policy_98_products_95_families=True,
        SHFE_INE_feature_scope_not_full_market_mechanism=True,slippage_in_fill_not_double_deducted=True,
        numeric_error_namespaces=dict(stage500=ERRORS,independent132=old.ERRORS,independent102=cash.ERRORS),
        inherited_helper_currency_tolerances='102 default atol5e-6 rtol2e-11;132 default atol2e-7 rtol2e-10;diagnostics default atol1e-6 rtol1e-10;stage500 own atol1e-8 rtol1e-11',
        strategy_cash_replays=0,estimator_fits=0,native_SQL=0)
    write(out/'cash_phase.json',report);return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['protocol','handoff','cash-manifest','authorization']:
        parser.add_argument('--'+name,required=True);parser.add_argument('--'+name+'-sha256',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--prior-terminal');parser.add_argument('--prior-terminal-sha256')
    args=parser.parse_args(argv)
    out=Path(args.output).resolve();assert LINE/'outputs/stage500_member_identity_cash_review' in out.parents
    assert not out.exists(),'fresh unique review output required'
    r=Reader();docs={};bindings={}
    for key in ['protocol','handoff','cash_manifest','authorization']:
        b=binding(getattr(args,key));assert b['sha256']==getattr(args,key+'_sha256');bindings[key]=b;docs[key]=r.doc(b)
    p,h,cm,a=(docs[k] for k in ['protocol','handoff','cash_manifest','authorization'])
    assert bindings['protocol']['sha256']==PROTOCOL_SHA and p['schema']=='stage495_member_identity_residual_protocol_v1'
    bundle=source_bundle()
    expected=dict(schema='stage500_exact_root_review_authorization_v1',authorized_by='root',stage='cash_review',protocol_sha256=PROTOCOL_SHA,
        output=str(out),actual_run_limit=1,max_native_cache_reads=1,max_native_SQL=0,max_fit=0,max_strategy_cash_replays=0)
    assert all(a.get(k)==v for k,v in expected.items()),'exact root review authorization required'
    assert same(a['cash_manifest_binding'],bindings['cash_manifest']) and same(a['handoff_binding'],bindings['handoff'])
    assert sorted(a['source_bundle'],key=lambda b:b['path'])==bundle,'review bytes differ from root authorization'
    inherited=None
    if args.prior_terminal:
        prior_binding=binding(args.prior_terminal);assert prior_binding['sha256']==args.prior_terminal_sha256
        prior=r.doc(prior_binding)
        cache_path=p['cash_contract_inherited_exact']['market_dependencies_inherited']['native_cache']['path']
        inherited=recovery_contract(a,prior,prior_binding,cache_path)
    else:assert 'recovery' not in a,'recovery authorization requires exact prior terminal'
    assert same(h['protocol_binding'],bindings['protocol']) and same(cm['metadata']['protocol'],bindings['protocol'])
    assert same(cm['metadata']['handoff'],bindings['handoff']) and cm['status']=='completed' and cm['new_cash_accounts']==8 and cm['new_fit']==0
    assert set(cm['arms'])==set(ARMS) and same(cm['metadata']['fit_manifest'],h['fit_manifest_binding'])
    r.register(cm['artifacts']);r.register(h);r.register(p['cash_contract_inherited_exact']['market_dependencies_inherited'])
    terminal=r.doc(cm['terminal']);assert terminal['status']=='completed' and terminal['cash_accounts_started']==terminal['cash_accounts_completed']==8
    assert terminal['native_SQL']==terminal['old_control_replays']==terminal['new_fit']==0
    out.mkdir(parents=True);start=time.monotonic();status='failed';error=None
    write(out/'started.json',dict(started_at=datetime.now(timezone.utc).isoformat(),bindings=bindings,source_bundle=bundle,actual_run_limit=1))
    if inherited:write(out/'prior_failed_review_scope.json',inherited)
    try:
        report=review(r,p,h,cm,out)
        # Hash remaining new cash artifacts once; no original source/model/Y scans.
        for b in cm['artifacts'].values():r.read(b)
        for b in cm['metadata']['source_bundle']:r.read(b)
        assert source_bundle()==bundle,'review source drift'
        cache=p['cash_contract_inherited_exact']['market_dependencies_inherited']['native_cache']['path'];assert r.reads[cache]==1
        receipt=dict(schema='stage500_member_identity_cash_review_receipt_v1',completed_cash_scope=True,completed_model_source_scope=False,
            P0=0,P1=0,P2=0,cash=report,bindings=bindings,source_bundle=bundle,reads_by_path=dict(r.reads),max_abs_errors=ERRORS,
            native_cache_reads=1,native_SQL=0,predictive_fits=0,strategy_cash_replays=0,original129Y_COMMON_scores156_rescans=0,
            cash_helper_tolerances_inherited=True,root_comparisons_atol=1e-8,root_comparisons_rtol=1e-11,
            source_model_held_argmax_reviews_must_be_combined_separately=True,alpha_proved=False,production_qualified=False,increased_betting_qualified=False,goal_complete=False)
        if inherited:
            prior_reads=inherited['prior_read_files'];repeated=sorted(set(prior_reads)&set(r.reads))
            receipt.update(explicit_dtype_recovery=inherited,cumulative_native_cache_reads=2,
                current_derived_paths_reread_from_prior_failed_process=repeated,
                cumulative_reads_by_path=dict(Counter(prior_reads)+r.reads))
        write(out/'review_receipt.json',receipt);status='completed';print(json.dumps(dict(status=status,output=str(out),P0=0,P1=0,P2=0)),flush=True)
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());write(out/'failure.json',error);raise
    finally:write(out/'terminal.json',dict(status=status,elapsed_seconds=time.monotonic()-start,error=error,reads_by_path=dict(r.reads),automatic_retry=False,predictive_fits=0,strategy_cash_replays=0,native_SQL=0))


if __name__=='__main__':main()
