"""Stage517 local cash kernel: frozen131 plus next-open continuation exit.

The old kernel and its constants are imported unchanged.  The copied cash loop
adds an explicit pure close-state scoring hook.  Disabled hooks have exact
synthetic ledger parity.  No source arrays, model, database or cash runs on import.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import math

TOOLS=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('stage517_accepted131',TOOLS/'stage131_contract_choice_kernel.py')
old=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(old)
for _name in ('INITIAL','SINGLE_RISK','TOTAL_RISK','MARGIN_CAP','MARGIN_BUFFER','finite','positive',
 'floor_lot','insolvency_flag','select_family_candidates','next_boundary','price_exit_reference',
 'adverse_quote','margin_rate','execution_quantity','policy_k','reduction_targets','organize',
 'summary_metrics','reserve_capped','CapacityLedger','anchor_request'):
    globals()[_name]=getattr(old,_name)


def close_state(position, market, dates, k):
    """Only current/past fields from the actual cash position, never path terminal."""
    bar=market.bar(position['epoch'],k)
    previous=market.bar(position['epoch'],k-1) if k>0 else None
    indicator=market.indicator(position['epoch'],k)
    return dict(mark=position['last_mark'],SL0=position['SL0'],boundary_next=position['boundary'],
        close=bar['close'] if bar else None,previous_close=previous['close'] if previous else None,
        N_t=indicator['N'],R0=position['R0'],age_source_days=k-position['entry_index']+1,
        source_lifecycle_target_date=position.get('source_lifecycle_target_date'),
        K_target_date=position.get('K_target_date'),t_date=dates[k])


def discretionary_close(position):
    target=position.get('reduce_to')
    return bool(not position['stale'] and not position.get('force_reason') and
        not position.get('voluntary_requested') and
        not (target is not None and target<position['qty']))


def latch_decision(position,decision,day):
    prediction=decision.get('prediction')
    requested=bool(finite(prediction) and float(prediction)<0)
    if requested:
        position['voluntary_requested']=True
        position['voluntary_request_date']=day
        position['voluntary_prediction']=float(prediction)
        position['voluntary_model_cutoff']=decision.get('cutoff')
    return requested


def run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial=INITIAL,prepared=None,*,policy='NARROW',continuation=None):
    potential,references=prepared if prepared is not None else organize(signals);ledger=CapacityLedger(initial,market,dates,economics,account_id);daily=[];budgets=[];position_days=[];insolvent=False;pending=[];entry_unknown=[];continuation_audit=[]
    if policy != 'NARROW':raise ValueError('Stage131 is fixed NARROW')
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
        rows=reserve_capped(accepted,t['equity'],t['initial_risk'],t['buffered_margin'],economics,scenario,policy)
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
            if p.get('voluntary_requested'):
                quote=adverse_quote(bar['open'],'SELL',economics[p['epoch']],scenario)
                ledger.exit(root_id,p['qty'],bar['open'],quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot'],day,'ai_continuation_next_open_exit')
                closed_today.add(p['family_id']);continue
            reference,reason=price_exit_reference(bar['open'],bar['low'],p['boundary'],None)
            if reference is not None:
                quote=adverse_quote(reference,'SELL',economics[p['epoch']],scenario);ledger.exit(root_id,p['qty'],reference,quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot'],day,reason);closed_today.add(p['family_id'])
            else:ledger.mark(root_id,bar['close'],False)
        for intent in pending:
            epoch=intent['reference_epoch'];e=economics[epoch];bar=market.bar(epoch,k);fam=intent['family_id']
            if bar is None:
                intent['D_state']='entry_execution_unknown';entry_unknown.append(dict(intent,state='entry_execution_unknown',date=day));continue
            if fam in closed_today or any(p['family_id']==fam for p in ledger.positions.values()):intent['D_state']='same_day_or_occupied_entry_cancel';continue
            if k>=intent['lifecycle_index']:intent['D_state']='lifecycle_entry_rejected';continue
            F=bar['open'];SL0=F-policy_k(policy)*intent['N_u']
            if F<=intent['low20_u']:intent['D_state']='stale_breakout_cancel_at_open';continue
            if SL0<=0 or not positive(intent['N_u']):intent['D_state']='invalid_initial_risk_cancel';continue
            qty,unit=execution_quantity(intent,F,e,scenario,policy);intent['D_unit_risk']=unit['risk_per_lot'];intent['D_unit_margin_plus_fee']=unit['actual_margin_plus_entry_fee_per_lot'];intent['D_qty']=qty
            if qty==0:intent['D_state']='own_open_allocation_insufficient';continue
            quote=unit['buy'];root=dict(root_id=account_id+'_'+intent['event_id'],event_id=intent['event_id'],family_id=fam,product_id=intent['product_id'],epoch=epoch,
                mother_event_id=intent.get('mother_event_id',''),anchor_epoch=intent['anchor_epoch'],entry_capacity_qty=intent['entry_capacity_qty'],entry_date=day,entry_index=k,u_date=intent['u_date'],budget_id=intent['budget_id'],multiplier=float(e['contract_multiplier']),round_lot=int(e['round_lot']),
                margin_rate=margin_rate(e,scenario),risk_per_lot=unit['risk_per_lot'],SL0=SL0,boundary=next_boundary(SL0,intent['low20_u']),R0=policy_k(policy)*intent['N_u'],expiry=intent['lifecycle_index'],
                tickized=quote['tickized'],future_info_scope=e.get('future_info_scope',''),economics_status=e['economics_status'])
            if continuation is not None:
                root.update(source_lifecycle_target_date=intent.get('source_lifecycle_target_date'),K_target_date=intent.get('K_target_date'))
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
                p['force_reason']=anchor_request(p,references.get(k,{}).get(p['product_id']),k+1)
                if p['force_reason'] and not p.get('anchor_request_date'):p['anchor_request_date']=day;p['anchor_request_reason']=p['force_reason']
            position_days.append(dict(account_id=account_id,scenario=scenario,date=day,root_id=root_id,event_id=p['event_id'],family_id=p['family_id'],product_id=p['product_id'],epoch=p['epoch'],qty=p['qty'],entry_fill=p['entry_fill'],entry_reference=p['entry_reference'],
                multiplier=p['multiplier'],margin_rate=p['margin_rate'],risk_per_lot=p['risk_per_lot'],mark=p['last_mark'],mark_state='stale' if p['stale'] else 'native_close',stale_days=p['stale_days'],
                SL0=p['SL0'],boundary_next=p['boundary'],force_next=p['force_reason'],unrealized=p['qty']*p['multiplier']*(p['last_mark']-p['entry_fill']),notional=p['qty']*p['multiplier']*p['last_mark']))
        t=ledger.totals();insolvent=insolvency_flag(insolvent,t['equity'])
        pending=prepare(k) if k<end else []
        reservation=sum(r['allocated_buffered_margin']+r['allocated_fee'] for r in pending)
        for row in position_days[position_day_start:]:row['reduce_to_next']=ledger.positions[row['root_id']].get('reduce_to')
        if continuation is not None:
            for root_id,p in ledger.positions.items():
                free=discretionary_close(p)
                audit=dict(account_id=account_id,scenario=scenario,date=day,t_index=k,
                    root_id=root_id,event_id=p['event_id'],family_id=p['family_id'],epoch=p['epoch'],
                    discretionary=int(free),force_next=p.get('force_reason'),stale=int(p['stale']),
                    reduce_to_next=p.get('reduce_to'),qty=p['qty'],requested=0,
                    latched_prior=int(bool(p.get('voluntary_requested'))),prediction=None,cutoff=None,
                    status='not_discretionary',planned_execution_date=dates[k+1] if k+1<len(dates) else None)
                if free:
                    current=close_state(p,market,dates,k)
                    decision=continuation(day,current)
                    if not isinstance(decision,dict):raise TypeError('continuation hook requires decision dict')
                    audit.update(current,**{key:decision.get(key) for key in ('prediction','cutoff','status')})
                    audit['requested']=int(latch_decision(p,decision,day))
                continuation_audit.append(audit)
            for row in position_days[position_day_start:]:
                p=ledger.positions[row['root_id']]
                row['voluntary_requested_next']=int(bool(p.get('voluntary_requested')))
                row['voluntary_request_date']=p.get('voluntary_request_date')

        daily.append(dict(account_id=account_id,scenario=scenario,date=day,**t,new_order_reserve=reservation,total_reserve=t['buffered_margin']+reservation,
            new_order_risk_reserve=sum(r['allocated_risk'] for r in pending),new_order_margin_reserve=sum(r['allocated_buffered_margin'] for r in pending),new_order_fee_reserve=sum(r['allocated_fee'] for r in pending),
            ever_insolvent=insolvent,equity_identity_error=t['equity']-(initial+t['cumulative_realized_gross']-t['cumulative_fees']+t['unrealized'])))
        if abs(daily[-1]['equity_identity_error'])>1e-6:raise AssertionError('daily equity identity broken')
    for fill in ledger.fills:fill.update(account_id=account_id,scenario=scenario)
    for p in ledger.closed+list(ledger.positions.values()):p['execution_capacity_unknown']=p['root_id'] in ledger.capacity_unknown_roots
    opens=[dict(p,state='stale_open_unresolved' if p['stale'] else 'open_right_censored',unrealized=p['qty']*p['multiplier']*(p['last_mark']-p['entry_fill'])) for p in ledger.positions.values()]
    result=dict(fills=ledger.fills,daily=daily,budgets=budgets,position_days=position_days,closed_episodes=ledger.closed,open_episodes=opens,summary=summary_metrics(daily,ledger,insolvent),capacity_audit=ledger.capacity_audit,entry_execution_unknown=entry_unknown,execution_unknown=bool(entry_unknown or ledger.capacity_unknown_roots),capacity_unknown_roots=sorted(ledger.capacity_unknown_roots))
    if continuation is not None:result['continuation_audit']=continuation_audit
    return result

