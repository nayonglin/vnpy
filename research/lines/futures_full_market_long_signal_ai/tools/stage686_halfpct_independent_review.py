"""Independent Stage685 saved-output audit; no fit, solve or strategy replay.

Ready mode reads small metadata/source only. Actual mode requires root's exact
manifest/source authorization and reads each bound saved payload once. Only two
new books are audited; accepted675 controls are summary/day identity references.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import traceback
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
OUTPUT=LINE/'outputs/stage686_halfpct_review'
START='2015-01-01'; END='2026-10-16'; ARM='VOLUNTARY_RESELECT'
SINGLE=.005; TOTAL=.02; MARGIN=.25; BUFFER=1.1
PROTOCOL_SHA='51545297db2db5c729751acc23b2b045f2cc4808c0c463010e0a9b4b7b8d84d3'


def load(name, identity):
    spec=importlib.util.spec_from_file_location(identity,TOOLS/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


# These are independent saved-output arithmetic helpers, not author engines.
base=load('stage676_2015_independent_review.py','independent686_reader676')
binding=base.binding; payload=base.payload; document=base.document
table=base.table; numeric=base.numeric; write=base.write; safe=base.safe


def sources():
    names=('stage686_halfpct_independent_review.py','test_stage686_halfpct_independent_review.py',
        'stage676_2015_independent_review.py','stage132_contract_choice_review.py',
        'stage158_voluntary_review.py','stage102_cash_adapter.py','stage102_cash_core.py',
        'stage102_cash_diagnostics.py')
    return [binding(TOOLS/n) for n in names]


def independent_reservations(candidates, equity, existing_risk, existing_margin,
                             economics, scenario, cash):
    """Independent 0.5% raw demand, same-u joint scaling, floor, then fixed cap.

    Fees/slippage use independent102 decimal quotes; capacity never redistributes
    a clipped allocation. Existing positions keep their frozen original D risk.
    """
    proposed=[]
    for sig in candidates:
        e=economics[sig['reference_epoch']]
        R,M,F,_=cash.estimate(float(sig['u_close']),float(sig['N_u']),e,scenario,.25)
        raw=max(0.,SINGLE*equity/R) if equity>0 else 0.
        proposed.append((sig,e,R,M,F,raw))
    gross_risk=sum(R*q for sig,e,R,M,F,q in proposed)
    gross_margin=sum(M*q for sig,e,R,M,F,q in proposed)
    scale=min(1.,max(0.,TOTAL*equity-existing_risk)/gross_risk if gross_risk else 1.,
              max(0.,MARGIN*equity-existing_margin)/gross_margin if gross_margin else 1.) if equity>0 else 0.
    result=[]
    for sig,e,R,M,F,raw in proposed:
        prefloor=raw*scale;lot=int(e['round_lot']);original=cash.floorlot(prefloor,lot)
        cap=min(original,int(sig['entry_capacity_qty']))
        state='reserved' if original>0 else 'risk_margin_or_one_lot_rejected'
        if cap==0 and original>0:state='capacity_below_one_roundtrip'
        result.append(dict(event_id=sig['event_id'],unit_risk_u=R,unit_margin_u=M,
            unit_fee_reserve_u=F,target_qty_unscaled=raw,joint_scale=scale,
            target_qty_prefloor=prefloor,original_qty_cap=original,qty_cap=cap,
            round_lot=lot,allocated_risk=prefloor*R,allocated_buffered_margin=prefloor*M,
            allocated_fee=prefloor*F,budget_state=state))
    return result


def review_budgets(budgets,daily,signals,economics,scenario,calendar,start,k,*,positions,cash,compare):
    """Check all saved intents/rejections and reductions without replaying signals."""
    fields=['u_equity','existing_risk','existing_buffered_margin','unit_risk_u','unit_margin_u',
        'unit_fee_reserve_u','target_qty_unscaled','joint_scale','target_qty_prefloor','qty_cap',
        'original_qty_cap','round_lot','allocated_risk','allocated_buffered_margin','allocated_fee',
        'D_qty','D_unit_risk','D_unit_margin_plus_fee','existing_qty','target_existing_qty']
    cash.numeric(budgets,fields)
    expected=set(signals.loc[signals.u_index.ge(start-1)&signals.u_date.lt(daily.date.iloc[-1]),'event_id'])
    if budgets.empty:
        assert not expected,'selected events omitted from empty budget'
        return dict(rows=0,new_allocations=0,existing_reductions=0,selected_event_records=0)
    assert budgets.budget_id.is_unique
    for key in ('budget_kind','budget_state','D_state'):
        if key not in budgets:budgets[key]=''
    ordinary=budgets.loc[~budgets.budget_kind.eq('existing_position_reduction')]
    assert ordinary.event_id.is_unique and set(ordinary.event_id)==expected,'all selected decisions retained'
    index={d:i for i,d in enumerate(calendar)};by_day=daily.set_index('date');new_count=reductions_count=0
    constrained=0;unconstrained=0;capacity_clipped=0;maximum_ratio=0.
    for u,group in budgets.groupby('u_date',sort=False):
        assert group.execution_date.eq(calendar[index[u]+1]).all()
        if u in by_day.index:
            d=by_day.loc[u];eq=float(d.equity);risk=float(d.initial_risk);margin=float(d.buffered_margin)
            insolvent=str(d.ever_insolvent).lower() in ('true','1')
        else:
            assert index[u]==start-1;eq=1_000_000.;risk=margin=0.;insolvent=False
        for field,value in [('u_equity',eq),('existing_risk',risk),('existing_buffered_margin',margin)]:
            compare(group[field],np.full(len(group),value),'halfpct_same_prepare_'+field)
        occupied=set(positions.loc[positions.date.eq(u),'family_id'])
        over=risk>TOTAL*eq or margin>MARGIN*eq;expected_new=set()
        for row in group.loc[~group.budget_kind.eq('existing_position_reduction')].to_dict('records'):
            sig=signals.loc[row['event_id']];e=economics[sig.reference_epoch]
            reason=('family_occupied' if sig.family_id in occupied else
                'instrument_economics_unqualified' if e.get('economics_status')!='exact_epoch_metadata_snapshot' else
                'insolvent_permanent_pause' if insolvent else 'existing_risk_margin_over_cap' if over else
                'lifecycle_entry_rejected' if index[u]+1>=sig.lifecycle_index or
                    (e.get('listed_date') and calendar[index[u]+1]<e['listed_date']) else None)
            if reason:
                assert row['budget_kind']!='new_entry' and row['budget_state']==row['D_state']==reason,('rejection',row['event_id'],reason)
            else:expected_new.add(row['event_id'])
        new=group.loc[group.budget_kind.eq('new_entry')]
        assert set(new.event_id)==expected_new
        proposal=independent_reservations([signals.loc[event].to_dict() for event in new.event_id],eq,risk,margin,economics,scenario,cash)
        expected_rows={row['event_id']:row for row in proposal}
        for row in new.to_dict('records'):
            wanted=expected_rows[row['event_id']];sig=signals.loc[row['event_id']]
            assert row['reference_epoch']==sig.reference_epoch and row['anchor_epoch']==sig.anchor_epoch
            for field,value in wanted.items():
                if field=='event_id':continue
                if field=='budget_state':assert row[field]==value
                else:compare(row[field],value,'halfpct_'+field,atol=2e-7,rtol=2e-10)
            assert 0<=row['D_qty']<=row['qty_cap']<=row['original_qty_cap']
            if eq>0:maximum_ratio=max(maximum_ratio,row['target_qty_unscaled']*row['unit_risk_u']/eq)
            constrained+=wanted['joint_scale']<1.;unconstrained+=wanted['joint_scale']==1.
            capacity_clipped+=wanted['qty_cap']<wanted['original_qty_cap'];new_count+=1
        if proposal:
            assert sum(p['allocated_risk'] for p in proposal)<=max(0.,TOTAL*eq-risk)+1e-6
            assert sum(p['allocated_buffered_margin'] for p in proposal)<=max(0.,MARGIN*eq-margin)+1e-6
        reductions=group.loc[group.budget_kind.eq('existing_position_reduction')]
        expected_roots=set(positions.loc[positions.date.eq(u),'root_id']) if insolvent or over else set()
        assert (set(reductions.root_id) if 'root_id' in reductions else set())==expected_roots
        factor=min(1.,TOTAL*eq/risk if risk else 1.,MARGIN*eq/margin if margin else 1.) if eq>0 else 0.
        for row in reductions.to_dict('records'):
            lot=int(economics[row['reference_epoch']]['round_lot'])
            target=cash.floorlot(row['existing_qty']*factor,lot)
            compare(row['joint_scale'],factor,'halfpct_existing_reduction_scale')
            assert row['target_existing_qty']==target and row['qty_cap']==row['existing_qty']-target
            reductions_count+=1
    return dict(rows=len(budgets),new_allocations=new_count,existing_reductions=reductions_count,
        selected_event_records=len(expected),jointly_constrained_candidates=constrained,
        unconstrained_candidates=unconstrained,capacity_clipped_candidates=capacity_clipped,
        max_unscaled_single_risk_fraction=maximum_ratio,single_risk=SINGLE,total_risk=TOTAL,
        buffered_margin_cap=MARGIN,margin_buffer=BUFFER,no_post_cap_redistribution=True,
        next_day_quantity_cannot_increase=True)


@contextmanager
def account_context(r,cash,positions):
    # Only isolated reviewer module objects change; author/accepted sources never do.
    previous=(r.CASH_HELPER,r.ACTIVE_POSITIONS,cash.review_budgets)
    r.CASH_HELPER=r_cash=cash;r.ACTIVE_POSITIONS=positions
    cash.review_budgets=lambda *a,**kw:review_budgets(*a,**kw,positions=positions,cash=r_cash,compare=r.compare)
    try:yield
    finally:r.CASH_HELPER,r.ACTIVE_POSITIONS,cash.review_budgets=previous


def check_private_kernel(author):
    original=author.cash.kernel
    before070=dict(original.original.reserve_batch.__globals__)
    before131=dict(original.run_cash_account.__globals__)
    private=author.build_private_kernel()
    reserve=private.reserve_batch
    capped=private.reserve_capped
    run=private.run_cash_account
    assert reserve.__code__ is original.original.reserve_batch.__code__
    assert capped.__code__ is original.reserve_capped.__code__
    assert run.__code__ is original.run_cash_account.__code__
    assert reserve.__globals__ is not original.original.reserve_batch.__globals__
    assert reserve.__globals__['SINGLE_RISK']==SINGLE
    assert reserve.__globals__['TOTAL_RISK']==TOTAL
    assert reserve.__globals__['MARGIN_CAP']==MARGIN and reserve.__globals__['MARGIN_BUFFER']==BUFFER
    assert capped.__globals__['original'].reserve_batch is reserve
    assert run.__globals__['reserve_capped'] is capped
    for copied,source in ((reserve,original.original.reserve_batch),(capped,original.reserve_capped),(run,original.run_cash_account)):
        assert copied.__defaults__==source.__defaults__ and copied.__kwdefaults__==source.__kwdefaults__
    assert original.original.reserve_batch.__globals__==before070
    assert original.run_cash_account.__globals__==before131
    assert original.original.SINGLE_RISK==original.SINGLE_RISK==.0025
    return dict(private_three_function_graph=True,code_and_defaults_unchanged=True,
        original_globals_unchanged=True,original_single_risk=.0025,private_single_risk=SINGLE,
        total_risk=TOTAL,buffered_margin_cap=MARGIN,margin_buffer=BUFFER)


def effective_source_fixtures(author):
    """Exercise the actual private reservation functions on synthetic inputs only."""
    cash=base.pure_helpers()['cash'];private=author.build_private_kernel();original=author.cash.kernel
    before070=dict(original.original.reserve_batch.__globals__)
    before131=dict(original.run_cash_account.__globals__)
    scenarios=[('single_half_percent',1,0.,0.,1000.,100)]
    outcomes=[]
    for label,count,existing_risk,existing_margin,N,first_cap in scenarios:
        signals=[dict(event_id=str(i),reference_epoch=str(i),u_close=1000.,N_u=N,
            entry_capacity_qty=first_cap if i==0 else 100) for i in range(count)]
        economics={str(i):dict(contract_multiplier=10.,round_lot=1,tick_size=None,
            vendor_margin_rate=.2,economics_status='exact_epoch_metadata_snapshot') for i in range(count)}
        wanted=independent_reservations(signals,1e6,existing_risk,existing_margin,economics,'base',cash)
        observed=private.reserve_capped(signals,1e6,existing_risk,existing_margin,economics,'base','NARROW')
        for actual,expected in zip(observed,wanted):
            for key,value in expected.items():
                if isinstance(value,(str,bool)):assert actual[key]==value,(label,key)
                else:assert np.isclose(actual[key],value,rtol=2e-11,atol=2e-7),(label,key,actual[key],value)
        outcomes.append(dict(case=label,candidates=count,observed_raw_fraction=observed[0]['target_qty_unscaled']*
            observed[0]['unit_risk_u']/1e6,scale=observed[0]['joint_scale'],
            allocated_risk=sum(r['allocated_risk'] for r in observed),
            allocated_buffered_margin=sum(r['allocated_buffered_margin'] for r in observed),
            caps=[r['qty_cap'] for r in observed]))
    assert original.original.reserve_batch.__globals__==before070
    assert original.run_cash_account.__globals__==before131
    return dict(synthetic_only=True,actual_research_cash_runs=0,fixtures=outcomes,
        original_globals_unchanged_after_effective_calls=True)


def ready(args):
    target=Path(args.output).resolve();assert target==OUTPUT/'source_GO.json' and not target.exists()
    author=load('stage685_single_risk_halfpct.py','independent686_ready_author685')
    graph=check_private_kernel(author);effective=effective_source_fixtures(author)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    result=dict(schema='stage686_halfpct_source_ready_v1',status='source_ready',source_graph=graph,effective_fixtures=effective,
        reviewer_source_bundle=sources(),author_source_bundle=author.source_bundle(),
        new_fits=0,new_cash_runs=0,new_SQL=0,large_payload_reads=0,actual_books_reviewed=0,
        final_actual_review_required=True,production_qualified=False,increased_betting_qualified=False)
    if args.protocol:
        item=binding(args.protocol);result['protocol']=item
        if args.protocol_sha256:assert item['sha256']==args.protocol_sha256
        result['protocol_document']=document(item)
    write(target,result)
    return dict(status='source_ready',output=str(target),actual_books_reviewed=0)


def authorize(args):
    out=Path(args.output).resolve();assert OUTPUT in out.parents and not out.exists()
    mb=binding(args.manifest);assert mb['sha256']==args.manifest_sha256
    ab=binding(args.authorization);assert ab['sha256']==args.authorization_sha256
    auth=document(ab)
    expected=dict(schema='stage686_exact_root_review_authorization_v1',authorized_by='root',
        exact_source_authorized=True,output=str(out),manifest=mb,source_bundle=sources(),
        actual_review_max=1,new_fits=0,new_cash_runs=0,new_SQL=0,old_cash_reaudits=0)
    for key,value in expected.items():assert auth.get(key)==value,('root authority',key)
    return out,mb,ab


def annual_equivalence(actual,expected):
    """Preserve every identity cell; float text may differ only at exact value."""
    assert list(actual)==list(expected) and actual.shape==expected.shape,'annual shape/columns changed'
    numeric_columns={'starting_equity','ending_equity','cash_growth','return_pct','max_drawdown_pct'}
    changed=[]
    for i in range(len(expected)):
        for column in expected:
            a,b=str(actual.iloc[i][column]),str(expected.iloc[i][column])
            if a==b:continue
            assert column in numeric_columns,('annual identity changed',i,column,a,b)
            x,y=float(a),float(b)
            assert np.isfinite(x) and np.isfinite(y) and x==y and np.signbit(x)==np.signbit(y),(
                'annual numeric value changed',i,column,a,b)
            changed.append(dict(row=i,column=column,original=b,combined=a,numeric_difference=x-y))
    return dict(rows=len(expected),columns=list(expected),serialization_only_cells=len(changed),
        max_numeric_difference=0.,identity_cells_exact=True,float_values_exact=True,changes=changed)


def actual(args):
    out,mb,ab=authorize(args);out.mkdir(parents=True,exist_ok=False)
    clock=time.monotonic();completed=False
    write(out/'actual_started.json',dict(status='started',at=datetime.now(timezone.utc).isoformat(),
        manifest=mb,authorization=ab,source_bundle=sources(),new_fits=0,new_cash_runs=0,new_SQL=0))
    try:
        m=document(mb);terminal=document(m['terminal']);protocol=document(m['protocol'])
        assert m['protocol']['sha256']==PROTOCOL_SHA
        assert protocol['change']==dict(parameter='SINGLE_RISK',old=.0025,new=.005,other_parameters_changed=False)
        assert protocol['fixed']['TOTAL_RISK']==TOTAL and protocol['fixed']['MARGIN_CAP']==MARGIN
        assert protocol['fixed']['MARGIN_BUFFER']==BUFFER and protocol['fixed']['initial_stop_N']==.25
        assert protocol['limits']==dict(new_fit=0,new_cash=2,old_refit=0,old_cash_replay=0,SQL=0,
            downloads=0,new_labels=0,new_scores=0,bootstrap=0,risk_grid_scan=False)
        assert m['schema']=='stage685_single_risk_halfpct_v1' and m['status']==terminal['status']=='completed'
        assert terminal['exit_code']==0 and m['new_cash_accounts']==terminal['new_cash_accounts']==2
        assert m['actual_fit_calls_completed']==0 and m['native_source_queries']==0
        assert terminal['actual_fit_calls_attempted']==terminal['actual_fit_calls_completed']==0
        assert terminal['cash_accounts_started']==2 and terminal['native_source_queries']==0
        assert m['input_bindings']==protocol['inputs']
        for key in ('old_refits','old_cash_replays','new_labels','new_scores','downloads','bootstrap'):
            assert m[key]==terminal[key]==0,('forbidden work counter',key)
        source_reads=document(m['source_read_receipt'])
        assert len(source_reads['payloads'])==len(protocol['inputs'])==16
        assert {item['role'] for item in source_reads['payloads']}==set(protocol['inputs'])
        for item in source_reads['payloads']:
            assert item['passes']==1
            assert {key:item[key] for key in ('path','bytes','sha256')}==protocol['inputs'][item['role']]
        assert source_reads['native']['cache_restores']==1 and source_reads['native']['native_source_queries']==0
        assert source_reads['native']['database_before']==source_reads['native']['database_after']
        effectiveness=document(m['parameter_effectiveness_receipt'])
        assert effectiveness['effective']==dict(SINGLE_RISK=SINGLE,TOTAL_RISK=TOTAL,MARGIN_CAP=MARGIN,
            MARGIN_BUFFER=BUFFER,initial_stop_N=.25)
        assert effectiveness['old_globals_unchanged'] is effectiveness['three_private_call_sites_verified'] is True
        assert set(effectiveness['old_single_risk'].values())=={.0025}
        for item in m['source_bundle']:base.verify(item)
        old=document(m['baseline_manifest']);old_terminal=document(old['terminal'])
        assert m['baseline_manifest']==protocol['inputs']['baseline_manifest']
        assert old['terminal']==protocol['inputs']['baseline_terminal']
        for role in ('mothers','native_cache_manifest','native_cache','market_protocol'):
            assert old['input_bindings'][role]==protocol['inputs'][role]
        assert old['schema']=='stage675_common52_2015_extension_v1' and old['status']==old_terminal['status']=='completed'
        assert m['baseline_accounts']==old['accounts'] and m['signals']==old['signals']
        assert {a['cost'] for a in m['accounts']}=={'base','stress'} and len(m['accounts'])==2
        assert m['production_qualified'] is m['increased_betting_qualified'] is m['goal_complete'] is False
        h=base.pure_helpers();r,v,cash,diag=(h[k] for k in ('r','v','cash','diag'))
        base.install_ledger_cache(cash,diag)
        bridge=document(old['input_bindings']['market_protocol'])
        raw=np.load(io.BytesIO(payload(bridge['calendar'])),allow_pickle=False)
        calendar=([str(int(d))[:4]+'-'+str(int(d))[4:6]+'-'+str(int(d))[6:8] for d in raw]
            if raw.dtype.kind in 'iu' else raw.astype('datetime64[D]').astype(str).tolist())
        assert calendar==sorted(set(calendar))
        old['_calendar']=calendar;old['_bridge']=bridge
        store,economics=base.restore_store(old,r)
        mothers=numeric(table(old['input_bindings']['mothers']),['sequence_index','u_index'])
        assert len(mothers)==399252 and mothers.product_id.nunique()==98 and mothers.family_id.nunique()==95
        signals=numeric(table(m['signals']),base.NUMERIC+['D_index','lifecycle_index','entry_capacity_qty',
            'u_gross_capacity_qty','source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index','potential'])
        assert signals.event_id.is_unique and set(signals.arm)=={ARM} and set(signals.policy)=={'NARROW'}
        signals['planned_execution_date']=[calendar[int(u)+1] for u in signals.u_index]
        signals=signals.set_index('event_id',drop=False)
        summaries=table(m['account_summaries']);annual=table(m['annual_slices']);curve=table(m['curve_data'])
        reports=document(m['diagnostics']);family=table(m['family_year_including_zero'])
        comparison=document(m['comparison']);compares={row['cost']:row for row in comparison['per_cost']}
        assert set(compares)=={'base','stress'} and comparison['bootstrap_performed'] is comparison['CI_computed'] is False
        numeric(family,['net_equity_contribution','fee','slippage','fill_count','filled_qty'])
        families=sorted(mothers.family_id.unique());results=[];new_daily={};controls=[]
        assert len(summaries)==2 and len(annual)==48
        assert list(curve)==['date']+[prefix+'_'+cost+'_'+field for prefix in ('risk025','risk050')
            for cost in ('base','stress') for field in ('equity','drawdown_pct')]
        for a in m['accounts']:
            folder=Path(a['directory']);cost=a['cost'];name=a['account_id'];summary=document(a['summary'])
            assert name=='all_2015_halfpct_'+cost and a['arm']==ARM and a['window']=='all_2015'
            assert summary['cost']==cost and set(a['ledgers'])==set(v.LEDGERS)
            for role,item in a['ledgers'].items():
                assert Path(item['path'])==folder/(role+'.csv.gz');base._BINDINGS[str(Path(item['path']).resolve())]=item
            positions=cash.csv(folder/'positions.csv.gz')
            start=next(d for d in calendar if d>=START);schedule=dict(id=a['window'],start=start,end=END)
            with account_context(r,cash,positions):
                checked=cash.review_account(folder,cost,schedule,protocol,signals,economics,calendar,.25)
                native=r.account_native_and_capacity(folder,signals,mothers,store,economics,summary,cost)
            for role in ('closed','open'):
                for root in cash.csv(folder/(role+'.csv.gz')).to_dict('records'):v.check_root_boundary(root,signals.to_dict('index'))
            saved_family=family.loc[family.account.eq(name)]
            d,log,numbers,fy=diag._account(folder,summary,reports[name],saved_family,families)
            diag._daily_summary(d,summary,1_000_000.)
            row=summaries.loc[summaries.account.eq(name)];assert len(row)==1
            v.fields(row.iloc[0].to_dict(),{k:x for k,x in summary.items() if not isinstance(x,(dict,list))},'halfpct summary table')
            rows=annual.loc[annual.account.eq(name)].sort_values('year')
            assert len(rows)==len(reports[name]['annual_slices'])
            for x,y in zip(rows.to_dict('records'),reports[name]['annual_slices']):v.fields(x,y,'halfpct annual')
            assert curve.date.tolist()==d.date.tolist()
            r.compare(curve['risk050_'+cost+'_equity'].map(float),d.equity,'halfpct curve equity '+cost,atol=0,rtol=0)
            chain=np.r_[1_000_000.,d.equity.to_numpy(float)]
            r.compare(curve['risk050_'+cost+'_drawdown_pct'].map(float),
                (chain[1:]/np.maximum.accumulate(chain)[1:]-1)*100,'halfpct curve DD '+cost,atol=1e-12)
            assert summary['any_historical_stale']==bool(numbers['stale_days']>0)
            v.nested(compares[cost]['active_summary'],summary,'halfpct comparison active summary')
            result=dict(account_id=name,cost=cost,ledger=checked,native=native,diagnostics=numbers,curve_rows=len(d))
            base.progress(out,'book_'+cost,result);results.append(result);new_daily[cost]=d
        # Accepted675 controls: no fills/positions/budgets/models are read or rerun.
        old_annual=table(old['annual_slices']);annual_equivalence_checks=[]
        for a in old['accounts']:
            cost=a['cost'];summary=document(a['summary']);d=numeric(table(a['ledgers']['daily']),[
                'equity','cash','cumulative_realized_gross','cumulative_fees','unrealized'])
            assert curve.date.tolist()==d.date.tolist()
            r.compare(curve['risk025_'+cost+'_equity'].map(float),d.equity,'accepted675 daily equity '+cost,atol=0,rtol=0)
            chain=np.r_[1_000_000.,d.equity.to_numpy(float)]
            r.compare(curve['risk025_'+cost+'_drawdown_pct'].map(float),
                (chain[1:]/np.maximum.accumulate(chain)[1:]-1)*100,'accepted675 curve DD '+cost,atol=1e-12)
            v.nested(compares[cost]['baseline_summary'],summary,'accepted675 unchanged comparison summary')
            active=compares[cost]['active_summary']
            for key,value in compares[cost]['metric_differences'].items():
                r.compare(value,float(active[key])-float(summary[key]),'descriptive metric difference '+cost+' '+key)
            part=annual.loc[annual.account.eq(a['account_id'])].reset_index(drop=True)
            prior=old_annual.loc[old_annual.account.eq(a['account_id'])].reset_index(drop=True)
            annual_equivalence_checks.append(dict(cost=cost,**annual_equivalence(part,prior)))
            controls.append(dict(account_id=a['account_id'],summary=a['summary'],daily=a['ledgers']['daily'],
                old_ledger_reaudit=False,new_cash_run=False,curve_identical=True))
        assert set(reports)=={a['account_id'] for a in m['accounts']}
        dominance=all(all(r.finite(row['active_summary'].get(key)) and r.finite(row['baseline_summary'].get(key)) and
            row['active_summary'][key]>=row['baseline_summary'][key]
            for key in ('total_return_pct','max_drawdown_pct','sharpe')) and
            not row['active_summary']['ever_insolvent'] and not row['baseline_summary']['ever_insolvent']
            for row in compares.values())
        assert comparison['same_history_point_dominance']==dominance
        result=dict(schema='stage686_halfpct_independent_review_v1',completed=True,research_arithmetic_accepted=True,C=0,I=0,M=0,
            cash_accounts=results,controls=controls,curve_lines_checked=4,all_four_annual_rows=len(annual),
            baseline_annual_numeric_equivalence=annual_equivalence_checks,
            source_bundle=sources(),numeric_max_errors=dict(r.ERRORS,**{'cash_'+k:x for k,x in cash.ERRORS.items()}),
            execution=dict(review_startups=1,full_review_completions=1,new_fits=0,new_cash_runs=0,new_SQL=0,
                linear_solves=0,strategy_replays=0,old_cash_reaudits=0,old_model_reaudits=0),
            caveats=['固定风险敏感性不构成0.5%生产加注资格','历史非PIT与日线成交假设保持',
                '2%是u收盘计划风险预算，跳空与次日权益变化不受2%损失上限保护',
                '历史stale和execution_unknown必须保留，曲线不能证明真实可成交'],
            production_qualified=False,increased_betting_qualified=False,goal_complete=False)
        write(out/'review_receipt.json',result);completed=True
        return dict(completed=True,research_arithmetic_accepted=True,C=0,I=0,M=0,output=str(out),elapsed_seconds=time.monotonic()-clock)
    finally:
        write(out/'actual_terminal.json',dict(status='completed' if completed else 'failed',
            exit_code=0 if completed else 1,elapsed_seconds=time.monotonic()-clock,
            new_fits=0,new_cash_runs=0,new_SQL=0,linear_solves=0,strategy_replays=0,
            error=None if completed else traceback.format_exc()))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['ready','actual'],required=True)
    for name in ('protocol','protocol-sha256','manifest','manifest-sha256','authorization','authorization-sha256'):
        p.add_argument('--'+name)
    p.add_argument('--output',required=True);args=p.parse_args()
    if args.mode=='actual':
        for name in ('manifest','manifest_sha256','authorization','authorization_sha256'):assert getattr(args,name),name
    print(json.dumps(ready(args) if args.mode=='ready' else actual(args),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
