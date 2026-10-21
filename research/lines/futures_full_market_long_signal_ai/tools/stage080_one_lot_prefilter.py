"""Stage079 one-lot feasibility prefilter, isolated fixed NARROW/COMMON cash.

Only the local reserve_batch changes. The account loop is copied verbatim from
accepted070; quotes/ledger/markets/diagnostics are pure bound dependencies. Import
and synthetic tests perform no native SQL, fit, labels or cash replay. Actual CLI
requires exact root source/protocol authorization and a fresh output directory.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='421722dd73ba0b4c43656b9439766afcf80c723b095160ace4742114050afce3'
DEPENDENCIES={
 'stage070_policy_kernel.py':'ad000624bd9722b3f1c580d622df2fc190330bac9e3c04011856085d56abcffe',
 'stage070_narrow_policy_cash.py':'5ed1461fb137854f5a6d7c20d1f3ea25306cd3fc9b8b1646fbc767e786387ecb',
 'stage042_cross_session_experiment.py':'ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d',
 'stage054_maturity_cash_compare.py':'f5f73732747b64b812e48c09202f5d52dcf3f59726e20e05e21ba616453884bd'}
for _name,_sha in DEPENDENCIES.items():
 if hashlib.sha256((TOOLS/_name).read_bytes()).hexdigest()!=_sha:
  raise ValueError('accepted pure dependency changed '+_name)
_spec=importlib.util.spec_from_file_location('stage080_accepted070_cash_helpers',TOOLS/'stage070_narrow_policy_cash.py')
helpers=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(helpers)
kernel=helpers.kernel
ref=kernel.ref
for _name in ('INITIAL','SINGLE_RISK','TOTAL_RISK','MARGIN_CAP','MARGIN_BUFFER','floor_lot','positive',
 'insolvency_flag','reduction_targets','select_family_candidates','CashLedger','organize','adverse_quote',
 'price_exit_reference','execution_quantity','policy_k','margin_rate','next_boundary','close_exit_request','summary_metrics'):
 globals()[_name]=getattr(kernel,_name)


def reserve_batch(candidates,equity,existing_risk,existing_margin,economics,scenario,policy):
    """Keep every candidate, but impossible one-lot requests consume no scale."""
    if policy!='NARROW':raise ValueError('Stage079 only permits fixed NARROW policy')
    single=max(0.,SINGLE_RISK*equity)
    available_risk=max(0.,TOTAL_RISK*equity-existing_risk)
    available_margin=max(0.,MARGIN_CAP*equity-existing_margin)
    proposals=[]
    for candidate in candidates:
        e=economics[candidate['reference_epoch']]
        unit=kernel.unit_estimate(candidate['u_close'],candidate['N_u'],e,scenario,policy)
        lot=int(e['round_lot']);r=unit['risk_per_lot'];m=unit['buffered_margin_per_lot']
        raw=single/r if equity>0 else 0.
        reasons=[]
        if lot*r>single:reasons.append('single_risk')
        if lot*r>available_risk:reasons.append('remaining_total_risk')
        if lot*m>available_margin:reasons.append('remaining_margin')
        joint_input=raw if not reasons and equity>0 else 0.
        proposals.append((candidate,e,unit,raw,joint_input,reasons))
    totalrisk=sum(x[2]['risk_per_lot']*x[4] for x in proposals)
    totalmargin=sum(x[2]['buffered_margin_per_lot']*x[4] for x in proposals)
    scale=min(1.,available_risk/totalrisk if totalrisk else 1.,available_margin/totalmargin if totalmargin else 1.) if equity>0 else 0.
    # Same-current-u arithmetic reference only; never a baseline cash replay.
    oldrisk=sum(x[2]['risk_per_lot']*x[3] for x in proposals)
    oldmargin=sum(x[2]['buffered_margin_per_lot']*x[3] for x in proposals)
    oldscale=min(1.,available_risk/oldrisk if oldrisk else 1.,available_margin/oldmargin if oldmargin else 1.) if equity>0 else 0.
    result=[]
    for c,e,unit,raw,joint_input,reasons in proposals:
        target=joint_input*scale;lot=int(e['round_lot']);qty=floor_lot(target,lot)
        state='one_lot_prefilter_'+'+'.join(reasons) if reasons else 'reserved' if qty>0 else 'risk_margin_or_one_lot_rejected'
        oldcap=floor_lot(raw*oldscale,lot)
        result.append(dict(c,u_equity=equity,existing_risk=existing_risk,existing_buffered_margin=existing_margin,
            unit_risk_u=unit['risk_per_lot'],unit_margin_u=unit['buffered_margin_per_lot'],unit_fee_reserve_u=unit['fee_roundtrip_per_lot'],
            raw_target_qty_unscaled=raw,joint_input_qty_unscaled=joint_input,target_qty_unscaled=joint_input,
            joint_scale=scale,target_qty_prefloor=target,qty_cap=qty,round_lot=lot,
            allocated_risk=target*unit['risk_per_lot'],allocated_buffered_margin=target*unit['buffered_margin_per_lot'],
            allocated_fee=target*unit['fee_roundtrip_per_lot'],budget_state=state,
            prefilter_eligible=int(not reasons and equity>0),prefilter_reasons='|'.join(reasons),
            single_risk_limit_u=single,remaining_total_risk_u=available_risk,remaining_buffered_margin_u=available_margin,
            one_lot_risk_u=lot*unit['risk_per_lot'],one_lot_buffered_margin_u=lot*unit['buffered_margin_per_lot'],
            joint_scale_original_same_u=oldscale,qty_cap_original_same_u=oldcap,qty_cap_delta_same_u=qty-oldcap))
    return result


def run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial=INITIAL,prepared=None,*,policy):
    potential,references=prepared if prepared is not None else organize(signals);ledger=CashLedger(initial);daily=[];budgets=[];position_days=[];insolvent=False;pending=[]
    def prepare(u,pre_window=False):
        nonlocal insolvent
        t=ledger.totals();insolvent=insolvency_flag(insolvent,t['equity']);positions=list(ledger.positions.values());over=t['initial_risk']>TOTAL_RISK*t['equity'] or t['buffered_margin']>MARGIN_CAP*t['equity']
        if insolvent or over:
            factor=min(1.,TOTAL_RISK*t['equity']/t['initial_risk'] if t['initial_risk'] else 1.,MARGIN_CAP*t['equity']/t['buffered_margin'] if t['buffered_margin'] else 1.) if not insolvent else 0.
            for p,target in zip(positions,reduction_targets(positions,0. if insolvent else t['equity'])):
                reduction=dict(budget_id=account_id+'_reduce_'+p['root_id']+'_'+dates[u],budget_kind='existing_position_reduction',root_id=p['root_id'],event_id=p['event_id'],reference_epoch=p['epoch'],family_id=p['family_id'],
                    account_id=account_id,scenario=scenario,u_date=dates[u],execution_date=dates[u+1] if u+1<len(dates) else None,u_equity=t['equity'],existing_risk=t['initial_risk'],existing_buffered_margin=t['buffered_margin'],
                    joint_scale=factor,existing_qty=p['qty'],target_existing_qty=target,qty_cap=p['qty']-target,D_qty=0,D_state='scheduled_reduction',pre_window_reservation=pre_window)
                budgets.append(reduction);p['reduce_to']=target;p['reduction_record']=reduction
        occupied={p['family_id'] for p in positions};chosen,rejected=select_family_candidates(potential.get(u,[]),occupied,economics,cash=True)
        if insolvent or over:
            for c in chosen:rejected[c['event_id']]='insolvent_permanent_pause' if insolvent else 'existing_risk_margin_over_cap'
            chosen=[]
        accepted=[]
        for c in chosen:
            e=economics[c['reference_epoch']];D=u+1
            if D>=c['lifecycle_index'] or (e.get('listed_date') and dates[D]<e['listed_date']):rejected[c['event_id']]='lifecycle_entry_rejected';continue
            if D>end:rejected[c['event_id']]='window_end_no_execution';continue
            accepted.append(c)
        rows=reserve_batch(accepted,t['equity'],t['initial_risk'],t['buffered_margin'],economics,scenario,policy)
        for j,r in enumerate(rows):
            r.update(budget_id=account_id+'_'+r['event_id'],budget_kind='new_entry',account_id=account_id,scenario=scenario,u_date=dates[u],execution_date=dates[u+1],pre_window_reservation=pre_window,
                D_qty=0,D_state='pending' if r['qty_cap']>0 else r['budget_state'])
            budgets.append(r)
        for event,reason in rejected.items():budgets.append(dict(budget_id=account_id+'_'+event,event_id=event,account_id=account_id,scenario=scenario,u_date=dates[u],execution_date=dates[u+1] if u+1<len(dates) else None,
            pre_window_reservation=pre_window,u_equity=t['equity'],existing_risk=t['initial_risk'],existing_buffered_margin=t['buffered_margin'],qty_cap=0,D_qty=0,budget_state=reason,D_state=reason))
        return [r for r in rows if r['qty_cap']>0]
    if start>0:pending=prepare(start-1,True)
    for k in range(start,end+1):
        day=dates[k];closed_today=set()
        for root_id,p in list(ledger.positions.items()):
            bar=market.bar(p['epoch'],k)
            if bar is None:
                if p.get('reduction_record'):p['reduction_record']['D_state']='missing_quote_deferred_exit'
                p['deferred']=True;p['force_reason']='research_deferred_liquidation';ledger.mark(root_id,None,True);continue
            force='research_deferred_liquidation' if p['deferred'] else p.get('force_reason')
            if force:
                if p.get('reduction_record'):p['reduction_record'].update(D_state='forced_full_exit_priority',D_qty=p['qty'])
                quote=adverse_quote(bar['open'],'SELL',economics[p['epoch']],scenario)
                ledger.exit(root_id,p['qty'],bar['open'],quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot'],day,force);closed_today.add(p['family_id']);continue
            target=p.get('reduce_to')
            if target is not None and target<p['qty']:
                quote=adverse_quote(bar['open'],'SELL',economics[p['epoch']],scenario);qty=p['qty']-target
                reduction=p.get('reduction_record');reduction_id=reduction['budget_id'] if reduction else None
                if reduction:reduction.update(D_state='executed_reduction',D_qty=qty)
                ledger.exit(root_id,qty,bar['open'],quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot'],day,'risk_margin_joint_reduction',reduction_id)
                if root_id not in ledger.positions:closed_today.add(p['family_id']);continue
                p['reduce_to']=None;p['reduction_record']=None
            reference,reason=price_exit_reference(bar['open'],bar['low'],p['boundary'],None)
            if reference is not None:
                quote=adverse_quote(reference,'SELL',economics[p['epoch']],scenario);ledger.exit(root_id,p['qty'],reference,quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot'],day,reason);closed_today.add(p['family_id'])
            else:ledger.mark(root_id,bar['close'],False)
        for intent in pending:
            epoch=intent['reference_epoch'];e=economics[epoch];bar=market.bar(epoch,k);fam=intent['family_id']
            if bar is None:intent['D_state']='research_no_quote_entry_cancel';continue
            if fam in closed_today or any(p['family_id']==fam for p in ledger.positions.values()):intent['D_state']='same_day_or_occupied_entry_cancel';continue
            if k>=intent['lifecycle_index']:intent['D_state']='lifecycle_entry_rejected';continue
            F=bar['open'];SL0=F-policy_k(policy)*intent['N_u']
            if F<=intent['low20_u']:intent['D_state']='stale_breakout_cancel_at_open';continue
            if SL0<=0 or not positive(intent['N_u']):intent['D_state']='invalid_initial_risk_cancel';continue
            qty,unit=execution_quantity(intent,F,e,scenario,policy);intent['D_unit_risk']=unit['risk_per_lot'];intent['D_unit_margin_plus_fee']=unit['actual_margin_plus_entry_fee_per_lot'];intent['D_qty']=qty
            if qty==0:intent['D_state']='own_open_allocation_insufficient';continue
            quote=unit['buy'];root=dict(root_id=account_id+'_'+intent['event_id'],event_id=intent['event_id'],family_id=fam,product_id=intent['product_id'],epoch=epoch,
                entry_date=day,entry_index=k,u_date=intent['u_date'],budget_id=intent['budget_id'],multiplier=float(e['contract_multiplier']),round_lot=int(e['round_lot']),
                margin_rate=margin_rate(e,scenario),risk_per_lot=unit['risk_per_lot'],SL0=SL0,boundary=next_boundary(SL0,intent['low20_u']),R0=policy_k(policy)*intent['N_u'],expiry=intent['lifecycle_index'],
                tickized=quote['tickized'],future_info_scope=e.get('future_info_scope',''),economics_status=e['economics_status'])
            ledger.enter(root,qty,F,quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot']);intent['D_state']='entered' if qty==intent['qty_cap'] else 'entered_reduced_own_allocation'
            reference,reason=price_exit_reference(F,bar['low'],root['boundary'],None)
            if reference is not None:
                sell=adverse_quote(reference,'SELL',e,scenario);ledger.exit(root['root_id'],qty,reference,sell['fill_price'],sell['fee_per_lot'],sell['slippage_per_lot'],day,reason);closed_today.add(fam)
            else:ledger.mark(root['root_id'],bar['close'],False)
        pending=[]
        position_day_start=len(position_days)
        for root_id,p in ledger.positions.items():
            if not p['stale']:
                indicator=market.indicator(p['epoch'],k);p['boundary']=next_boundary(p['SL0'],indicator['low20'])
                p['force_reason']=close_exit_request(p['epoch'],references.get(k,{}).get(p['product_id']),k+1,p['expiry'])
            position_days.append(dict(account_id=account_id,scenario=scenario,date=day,root_id=root_id,event_id=p['event_id'],family_id=p['family_id'],product_id=p['product_id'],epoch=p['epoch'],qty=p['qty'],entry_fill=p['entry_fill'],entry_reference=p['entry_reference'],
                multiplier=p['multiplier'],margin_rate=p['margin_rate'],risk_per_lot=p['risk_per_lot'],mark=p['last_mark'],mark_state='stale' if p['stale'] else 'native_close',stale_days=p['stale_days'],
                SL0=p['SL0'],boundary_next=p['boundary'],force_next=p['force_reason'],unrealized=p['qty']*p['multiplier']*(p['last_mark']-p['entry_fill']),notional=p['qty']*p['multiplier']*p['last_mark']))
        t=ledger.totals();insolvent=insolvency_flag(insolvent,t['equity'])
        pending=prepare(k) if k<end else []
        reservation=sum(r['allocated_buffered_margin']+r['allocated_fee'] for r in pending)
        for row in position_days[position_day_start:]:row['reduce_to_next']=ledger.positions[row['root_id']].get('reduce_to')
        daily.append(dict(account_id=account_id,scenario=scenario,date=day,**t,new_order_reserve=reservation,total_reserve=t['buffered_margin']+reservation,
            new_order_risk_reserve=sum(r['allocated_risk'] for r in pending),new_order_margin_reserve=sum(r['allocated_buffered_margin'] for r in pending),new_order_fee_reserve=sum(r['allocated_fee'] for r in pending),
            ever_insolvent=insolvent,equity_identity_error=t['equity']-(initial+t['cumulative_realized_gross']-t['cumulative_fees']+t['unrealized'])))
        if abs(daily[-1]['equity_identity_error'])>1e-6:raise AssertionError('daily equity identity broken')
    for fill in ledger.fills:fill.update(account_id=account_id,scenario=scenario)
    opens=[dict(p,state='stale_open_unresolved' if p['stale'] else 'open_right_censored',unrealized=p['qty']*p['multiplier']*(p['last_mark']-p['entry_fill'])) for p in ledger.positions.values()]
    return dict(fills=ledger.fills,daily=daily,budgets=budgets,position_days=position_days,closed_episodes=ledger.closed,open_episodes=opens,summary=summary_metrics(daily,ledger,insolvent))


def source_bundle():
    names=list(DEPENDENCIES)+['stage080_one_lot_prefilter.py','test_stage080_one_lot_prefilter.py']
    return sorted([ref.file_binding(TOOLS/name) for name in names],key=lambda b:b['path'])


def authorize(args):
    output=Path(args.output).resolve()
    if output.exists():raise FileExistsError('fresh output required; no retry/overwrite '+str(output))
    protocol_binding=ref.file_binding(args.protocol)
    if args.protocol_sha256!=PROTOCOL_SHA or protocol_binding['sha256']!=PROTOCOL_SHA:
        raise ValueError('exact Stage079 protocol SHA required')
    protocol=json.loads(ref.read_bound(protocol_binding))
    if protocol.get('schema')!='stage079_one_lot_prefilter_protocol_v1':raise ValueError('wrong079 protocol')
    auth=json.loads(Path(args.authorization).read_bytes())
    required=dict(schema='stage079_exact_root_authorization_v1',authorized_by='root',stage='cash',
                  exact_source_authorized=True,protocol_sha256=PROTOCOL_SHA,output=str(output))
    if any(auth.get(k)!=v for k,v in required.items()):raise ValueError('missing exact root authorization')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():
        raise ValueError('root exact source/test bundle changed')
    ref.read_bound(protocol['plan']);ref.read_bound(protocol['support_manifest']);ref.read_bound(protocol['support_review'])
    return protocol,protocol_binding,auth,ref.file_binding(args.authorization)


def continuation_gate(pairs):
    by={(p['window'],p['cost']):p for p in pairs}
    primary=by[('primary_2020','stress')]
    all_empty=all(p['identification']=='all_empty_unidentified' for p in pairs)
    returns=(primary['return_percentage_point_difference']>0 and by[('primary_2020','base')]['return_percentage_point_difference']>0
             and all(by[('cold_2023',c)]['return_percentage_point_difference']>=0 for c in ('base','stress')))
    identified=all(p['drawdown_percentage_point_difference'] is not None for p in pairs)
    dd=all(p['drawdown_percentage_point_difference']>=0 for p in pairs if p['drawdown_percentage_point_difference'] is not None)
    ci=primary.get('ci95_low') is not None and primary['ci95_low']>0
    nominal=bool(returns and identified and dd and ci)
    unknown=any(p['differential_historical_stale'] or p['zero_scenario_reverses_positive_return_delta'] for p in pairs)
    status=('all_empty_unidentified' if all_empty else 'unknown_empty_reference_DD' if returns and dd and ci and not identified
            else 'unknown_differential_unidentified' if nominal and unknown else 'supported_research_model_only' if nominal else 'unsupported')
    return dict(nominal_pass=nominal,status=status,qualification='unknown_differential_unidentified' if unknown else 'research_model_only',
                primary_return_higher=bool(primary['return_percentage_point_difference']>0),drawdown_not_deeper=bool(dd),
                primary_paired_CI_low_positive=bool(ci),base_and_cold_consistent=bool(returns),
                goal_complete=False,no_automatic_promotion=True,independent_full_actual_review_required=True)


def execute(args):
    protocol,protocol_binding,auth,auth_binding=authorize(args)
    inputs=protocol['inputs']
    fit=json.loads(ref.read_bound(inputs['fit_manifest']))
    narrow=json.loads(ref.read_bound(inputs['narrow_manifest']))
    baseline_manifest=json.loads(ref.read_bound(inputs['baseline_cash_manifest']))
    if (fit.get('status')!='completed' or fit.get('actual_fit_calls_completed')!=12 or narrow.get('status')!='completed'
        or narrow.get('mother_rows')!=399252 or baseline_manifest.get('status')!='completed' or baseline_manifest.get('new_cash_accounts')!=24):
        raise ValueError('frozen completed071/070 inputs required')
    for actual,expected in ((fit['predictions'],inputs['predictions']),(fit['input_bindings']['narrow_labels'],inputs['narrow_labels']),
                            (narrow['labels_narrow'],inputs['narrow_labels'])):
        if any(actual[k]!=expected[k] for k in ('path','bytes','sha256')):raise ValueError('frozen input chain differs')
    labels=helpers.read_table(inputs['narrow_labels'])
    chunks=pd.read_csv(io.BytesIO(ref.read_bound(inputs['predictions'])),compression='gzip',chunksize=200000)
    predictions=pd.concat([g.loc[g.policy.eq('NARROW')&g.arm.eq('COMMON')] for g in chunks],ignore_index=True)
    if len(labels)!=399252 or len(predictions)!=161014:raise ValueError('full mother/fixed161014 scores required')
    signals=helpers.make_signals(labels,predictions,'NARROW','COMMON')
    baselines={name:dict(daily=helpers.read_table(b['daily']),summary=json.loads(ref.read_bound(b['summary'])))
               for name,b in protocol['baselines'].items()}
    indices={w:np.load(io.BytesIO(ref.read_bound(b)),allow_pickle=False) for w,b in protocol['bootstrap_indices'].items()}
    if ref.NATIVE_QUERIES:raise ValueError('native input already consumed')
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    source_before=source_bundle();started=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
    status,error,accounts_started,accounts_completed='failed',None,0,0
    ref.write_json(out/'actual_started.json',dict(status='started',started_at=started,source_bundle=source_before,
                   protocol=protocol_binding,authorization=auth_binding,new_cash_limit=4,native_query_limit=1,fixture=False))
    try:
        panel,market,dates,economics,_,native_receipt,market_protocol=kernel.load_market_bridge(dict(input_bindings=inputs))
        ref.write_json(out/'source_read_receipt.json',native_receipt)
        prepared=ref.organize(signals);families=sorted(panel.product_id.map(ref.family).unique())
        pairs=[];summary_rows=[];annual=[];family_tables=[];reports={};prefilter_rows=[];distributions={};selections={}
        for window in protocol['finance']['windows']:
            w=window['id'];start=int(np.searchsorted(dates,window['start']));end=int(np.searchsorted(dates,window['end']))
            if dates[end]!=window['end']:raise ValueError('source end missing')
            for cost in protocol['finance']['costs']:
                name=f'NARROW_COMMON_{w}_{cost}';account='ONE_LOT_PREFILTER_'+name
                accounts_started+=1
                book=run_cash_account(signals,market,dates,economics,cost,account,start,end,prepared=prepared,policy='NARROW')
                accounts_completed+=1
                directory=out/name;directory.mkdir()
                for file,key in [('fills','fills'),('reservations','budgets'),('daily','daily'),('positions','position_days'),('closed','closed_episodes'),('open','open_episodes')]:
                    ref.write_table(directory/(file+'.csv.gz'),book[key],helpers.EMPTY_COLUMNS.get(key,[]))
                ref.write_table(directory/'rejections.csv.gz',[r for r in book['budgets'] if r.get('D_qty',0)==0],helpers.EMPTY_COLUMNS['budgets'])
                summary,report,family_year=helpers.cash_report(book,families,ref.INITIAL)
                reference=baselines[name];new_daily=pd.DataFrame(book['daily']);old_daily=reference['daily']
                if indices[w].shape!=(2000,len(new_daily)):raise ValueError('frozen bootstrap index shape changed')
                point=helpers.compare_points(summary,reference['summary'])
                stats,distribution=helpers.paired_statistics(new_daily,old_daily,indices[w])
                zero_delta=summary['all_open_long_zero_scenario_equity']-reference['summary']['all_open_long_zero_scenario_equity']
                stale_diff=not new_daily.stale_notional.eq(old_daily.stale_notional).all()
                point.update(window=w,cost=cost,**stats,differential_historical_stale=bool(stale_diff),
                             all_open_zero_ending_equity_difference=zero_delta,
                             zero_scenario_reverses_positive_return_delta=bool(point['return_percentage_point_difference']>0 and zero_delta<=0),
                             actual_total_filled_qty_difference=summary['total_filled_qty']-reference['summary']['total_filled_qty'])
                pairs.append(point);distributions[name]=distribution
                for variant,value in [('ONE_LOT_PREFILTER',summary),('ACCEPTED070',reference['summary'])]:
                    summary_rows.append(dict(window=w,cost=cost,variant=variant,**value))
                report['baseline_daily_and_summary_only']=True;reports[name]=report
                annual.extend(dict(account=name,variant='ONE_LOT_PREFILTER',**row) for row in report['annual_slices'])
                # Baseline year slices come directly from the accepted saved curve.
                old_previous=ref.INITIAL
                for year,group in old_daily.groupby(old_daily.date.str[:4],sort=True):
                    path=np.r_[old_previous,group.equity.to_numpy(float)]
                    annual.append(dict(account=name,variant='ACCEPTED070',year=year,source_days=len(group),
                                       starting_equity=old_previous,ending_equity=float(path[-1]),
                                       return_pct=(float(path[-1])/old_previous-1)*100 if old_previous>0 else None,
                                       max_drawdown_pct=float((path/np.maximum.accumulate(path)-1).min()*100),
                                       continuous_account_slice=True,independent_cold_start=False))
                    old_previous=float(path[-1])
                family_tables.append(family_year.assign(window=w,cost=cost,variant='ONE_LOT_PREFILTER'))
                new_entries=[r for r in book['budgets'] if r.get('budget_kind')=='new_entry']
                budget_frame=pd.DataFrame(new_entries)
                if new_entries:
                    for u,batch in budget_frame.groupby('u_date',sort=True):
                        rejected=batch.prefilter_eligible.eq(0)
                        prefilter_rows.append(dict(window=w,cost=cost,u_date=u,candidates=len(batch),
                            prefiltered_candidates=int(rejected.sum()),same_u_qty_cap_gain=float(batch.qty_cap_delta_same_u.sum()),
                            actual_entry_qty=float(batch.D_qty.sum()),new_u_qty_cap=float(batch.qty_cap.sum()),
                            original_same_u_qty_cap=float(batch.qty_cap_original_same_u.sum())))
                    for kind,mask in [('prefilter_single_risk',budget_frame.prefilter_reasons.str.contains('single_risk')),
                                      ('prefilter_remaining_risk',budget_frame.prefilter_reasons.str.contains('remaining_total_risk')),
                                      ('prefilter_remaining_margin',budget_frame.prefilter_reasons.str.contains('remaining_margin')),
                                      ('new_u_qty_gain',budget_frame.qty_cap_delta_same_u.gt(0))]:
                        matches=budget_frame.loc[mask]
                        if len(matches) and kind not in selections:
                            row=matches.iloc[0];batch=budget_frame.loc[budget_frame.u_date.eq(row.u_date)].to_dict('records')
                            selections[kind]=dict(kind=kind,policy='NARROW',event_id=row.event_id,
                                date=row.execution_date if kind=='new_u_qty_gain' else row.u_date,account=account,budget=row.to_dict(),
                                u_batch=batch,u_batch_economics={r['reference_epoch']:economics[r['reference_epoch']] for r in batch})
                audit_roots={r['root_id']:r for r in book['closed_episodes']+book['open_episodes']}
                for fill in book['fills']:
                    if fill['side']!='SELL':continue
                    root=audit_roots[fill['root_id']];reason=fill['reason']
                    kind=('entry_day_stop' if reason in ('stop_boundary','gap_stop') and fill['date']==root['entry_date']
                          else 'later_boundary' if reason=='stop_boundary' else 'gap_stop' if reason=='gap_stop'
                          else 'old_epoch_exit' if reason=='liquidity_reference_changed' else 'lifecycle_exit' if reason=='lifecycle_exit'
                          else 'deferred_exit' if reason=='research_deferred_liquidation' else None)
                    if kind is not None:selections.setdefault(kind,dict(kind=kind,policy='NARROW',event_id=fill['event_id'],date=fill['date'],account=account,fill=fill))
                for position in book['position_days']:
                    if position['mark_state']=='stale':selections.setdefault('missing',dict(kind='missing',policy='NARROW',event_id=position['event_id'],date=position['date'],account=account,position=position))
                ref.write_json(directory/'summary.json',kernel.safe(summary))
                print(json.dumps(dict(phase='account_complete',account=account,completed=accounts_completed,elapsed_seconds=time.monotonic()-clock)),flush=True)
        if accounts_started!=4 or accounts_completed!=4 or ref.NATIVE_QUERIES!=1:raise AssertionError('finite4cash/1SQL budget changed')
        ref.write_table(out/'new_and_accepted_summary.csv.gz',pd.DataFrame(summary_rows),[])
        ref.write_table(out/'comparisons.csv.gz',pd.DataFrame(pairs),[])
        ref.write_table(out/'bootstrap_distributions.csv.gz',pd.DataFrame(distributions),[])
        ref.write_table(out/'annual_slices.csv.gz',annual,[])
        ref.write_table(out/'family_year_including_zero.csv.gz',pd.concat(family_tables,ignore_index=True),[])
        ref.write_table(out/'prefilter_by_u.csv.gz',prefilter_rows,[])
        prefilter=pd.DataFrame(prefilter_rows)
        ref.write_json(out/'prefilter_summary.json',kernel.safe(dict(account_rows=len(prefilter_rows),
            candidate_total=int(prefilter.candidates.sum()) if len(prefilter) else 0,
            prefiltered_candidate_total=int(prefilter.prefiltered_candidates.sum()) if len(prefilter) else 0,
            account_u_with_prefilter=int(prefilter.prefiltered_candidates.gt(0).sum()) if len(prefilter) else 0,
            same_u_qty_cap_gain=float(prefilter.same_u_qty_cap_gain.sum()) if len(prefilter) else 0.,
            actual_quantity_comparison='aggregate new/accepted070 total_filled_qty; per-new-u caps compare identical current state, not baseline account state',
            no_baseline_cash_replay=True,no_reallocation_or_score_ordering=True)))
        kernel.export_native_cases(out/'finite_native_cases.json.gz',list(selections.values()),{'NARROW':labels},panel,market,dates,economics)
        ref.write_json(out/'diagnostics.json',kernel.safe(reports))
        ref.write_json(out/'continuation_gate.json',kernel.safe(continuation_gate(pairs)))
        ref.assert_db_binding(market_protocol['database'])
        if source_bundle()!=source_before:raise ValueError('source changed during actual')
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        ref.write_json(out/'actual_terminal.json',dict(status=status,started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-clock,exit_code=0 if status=='completed' else 1,error=error,fixture=False,python=sys.executable,
            native_source_queries=ref.NATIVE_QUERIES,cash_accounts_started=accounts_started,new_cash_accounts=accounts_completed,
            actual_model_fit_calls=0,new_labels=0,downloads=0,whole_database_hashes=0,baseline_cash_replays=0))
    artifacts=[dict(ref.file_binding(p),raw_ohlc=p.name=='finite_native_cases.json.gz',reproducibility_required=p.name!='finite_native_cases.json.gz') for p in sorted(out.rglob('*')) if p.is_file()]
    ref.write_json(out/'manifest.json',dict(schema='stage080_one_lot_prefilter_cash_v1',status=status,mode='actual',protocol=protocol_binding,
        authorization=auth_binding,source_bundle=source_before,input_bindings=inputs,baselines=protocol['baselines'],bootstrap_indices=protocol['bootstrap_indices'],
        terminal=ref.file_binding(out/'actual_terminal.json'),artifacts=artifacts,native_source_queries=ref.NATIVE_QUERIES,
        new_cash_accounts=accounts_completed,actual_model_fit_calls=0,new_labels=0,baseline_cash_replays=0,goal_complete=False,production_qualified=False))
    return dict(status=status,output=str(out),new_cash_accounts=accounts_completed,native_source_queries=ref.NATIVE_QUERIES)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','protocol-sha256','authorization','output'):parser.add_argument('--'+name,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
