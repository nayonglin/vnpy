"""Frozen611: original131 old-position bookkeeping plus one new entry plan.

No source mutation/monkeypatch, no phase split/add/D budget redistribution. Price
crossing is an ideal first-touch-full-fill conditional model, not queue evidence.
"""
import math
from decimal import Decimal,localcontext,ROUND_FLOOR
from stage131_contract_choice_kernel import *
import stage131_contract_choice_kernel as accepted


def resolve_limit(L,O,low,econ,scenario):
    s=original.ref.SCENARIOS[scenario]
    plan=dict(filled=False,state='numeric_inverse_unknown',T=None,F=None,adjusted=False,Qopen=None,Qfill=None,
        tick=econ.get('tick_size'),tickized=positive(econ.get('tick_size')),b=s['slip_bps'],n=s['slip_ticks'])
    try:
        if not all(positive(v) for v in (L,O,low)):return plan
        limit=Decimal(str(L));qo=adverse_quote(O,'BUY',econ,scenario);plan['Qopen']=qo['fill_price']
        if not positive(qo['fill_price']):return plan
        if Decimal(str(qo['fill_price']))<=limit:
            plan.update(filled=True,state='open_marketable',F=O,Qfill=qo['fill_price']);return plan
        with localcontext() as ctx:
            ctx.prec=50;ctx.rounding=ROUND_FLOOR;b=Decimal(str(s['slip_bps']))
            if plan['tickized']:
                t=Decimal(str(econ['tick_size']));j=(limit/t).to_integral_value(rounding=ROUND_FLOOR)
                ticks=min((j/(1+b)).to_integral_value(rounding=ROUND_FLOOR),j-s['slip_ticks']);T=ticks*t
            else:T=limit/(1+b)
        plan['T']=str(T)
        if T<=0:plan['state']='nonpositive_trigger_cancel';return plan
        F=float(T)
        if math.isfinite(F) and Decimal(str(F))>T:F=math.nextafter(F,-math.inf);plan['adjusted']=True
        plan['F']=F
        if not math.isfinite(F) or F<=0 or Decimal(str(F))>T:return plan
        q=adverse_quote(F,'BUY',econ,scenario);plan['Qfill']=q['fill_price']
        if not positive(q['fill_price']) or Decimal(str(q['fill_price']))>limit:return plan
        if Decimal(str(low))>T:plan['state']='not_touched_expired';return plan
        plan.update(filled=True,state='intraday_first_touch');return plan
    except (ArithmeticError,ValueError,OverflowError):return plan


def _run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial=INITIAL,prepared=None,*,policy='NARROW'):
    potential,references=prepared if prepared is not None else organize(signals);ledger=CapacityLedger(initial,market,dates,economics,account_id);daily=[];budgets=[];position_days=[];insolvent=False;pending=[];entry_unknown=[]
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
        # BEGIN613_DISJOINT
        if {r['family_id'] for r in pending}&{p['family_id'] for p in ledger.positions.values()}:
            raise AssertionError('u pending and held family must be disjoint')
        # END613_DISJOINT
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
            # BEGIN613_AUDIT
            intent.update(limit_pending=True,limit_L=intent['u_close'],limit_native_open=None if bar is None else bar['open'],limit_native_low=None if bar is None else bar['low'])
            # END613_AUDIT
            if bar is None:
                intent['D_state']='entry_execution_unknown';entry_unknown.append(dict(intent,state='entry_execution_unknown',date=day));continue
            if fam in closed_today or any(p['family_id']==fam for p in ledger.positions.values()):intent['D_state']='same_day_or_occupied_entry_cancel';continue
            if k>=intent['lifecycle_index']:intent['D_state']='lifecycle_entry_rejected';continue
            # BEGIN613_ENTRY
            plan=resolve_limit(intent['u_close'],bar['open'],bar['low'],e,scenario)
            intent.update({'limit_'+name:value for name,value in plan.items()})
            if not plan['filled']:
                intent['D_state']=plan['state']
                if plan['state']=='numeric_inverse_unknown':entry_unknown.append(dict(intent,state='numeric_inverse_unknown',date=day))
                continue
            F=plan['F'];SL0=F-policy_k(policy)*intent['N_u'];intent['limit_SL0']=SL0
            # END613_ENTRY
            if F<=intent['low20_u']:intent['D_state']='stale_breakout_cancel_at_open';continue
            if SL0<=0 or not positive(intent['N_u']):intent['D_state']='invalid_initial_risk_cancel';continue
            qty,unit=execution_quantity(intent,F,e,scenario,policy);intent['D_unit_risk']=unit['risk_per_lot'];intent['D_unit_margin_plus_fee']=unit['actual_margin_plus_entry_fee_per_lot'];intent['D_qty']=qty
            # BEGIN613_QUOTE
            if Decimal(str(unit['buy']['fill_price']))>Decimal(str(intent['u_close'])):raise AssertionError('actual BUY quote exceeds limit')
            intent.update(limit_final_fill=unit['buy']['fill_price'],limit_final_fee_per_lot=unit['buy']['fee_per_lot'],limit_final_slippage_per_lot=unit['buy']['slippage_per_lot'])
            # END613_QUOTE
            if qty==0:intent['D_state']='own_open_allocation_insufficient';continue
            quote=unit['buy'];root=dict(root_id=account_id+'_'+intent['event_id'],event_id=intent['event_id'],family_id=fam,product_id=intent['product_id'],epoch=epoch,
                mother_event_id=intent.get('mother_event_id',''),anchor_epoch=intent['anchor_epoch'],entry_capacity_qty=intent['entry_capacity_qty'],entry_date=day,entry_index=k,u_date=intent['u_date'],budget_id=intent['budget_id'],multiplier=float(e['contract_multiplier']),round_lot=int(e['round_lot']),
                margin_rate=margin_rate(e,scenario),risk_per_lot=unit['risk_per_lot'],SL0=SL0,boundary=next_boundary(SL0,intent['low20_u']),R0=policy_k(policy)*intent['N_u'],expiry=intent['lifecycle_index'],
                tickized=quote['tickized'],future_info_scope=e.get('future_info_scope',''),economics_status=e['economics_status'])
            # BEGIN613_ROOT
            root.update(limit_entry_kind=intent['limit_state'],limit_L=intent['u_close'],limit_F=F,limit_T=intent.get('limit_T'))
            # END613_ROOT
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
        daily.append(dict(account_id=account_id,scenario=scenario,date=day,**t,new_order_reserve=reservation,total_reserve=t['buffered_margin']+reservation,
            new_order_risk_reserve=sum(r['allocated_risk'] for r in pending),new_order_margin_reserve=sum(r['allocated_buffered_margin'] for r in pending),new_order_fee_reserve=sum(r['allocated_fee'] for r in pending),
            ever_insolvent=insolvent,equity_identity_error=t['equity']-(initial+t['cumulative_realized_gross']-t['cumulative_fees']+t['unrealized'])))
        if abs(daily[-1]['equity_identity_error'])>1e-6:raise AssertionError('daily equity identity broken')
    for fill in ledger.fills:fill.update(account_id=account_id,scenario=scenario)
    for p in ledger.closed+list(ledger.positions.values()):p['execution_capacity_unknown']=p['root_id'] in ledger.capacity_unknown_roots
    opens=[dict(p,state='stale_open_unresolved' if p['stale'] else 'open_right_censored',unrealized=p['qty']*p['multiplier']*(p['last_mark']-p['entry_fill'])) for p in ledger.positions.values()]
    return dict(fills=ledger.fills,daily=daily,budgets=budgets,position_days=position_days,closed_episodes=ledger.closed,open_episodes=opens,summary=summary_metrics(daily,ledger,insolvent),capacity_audit=ledger.capacity_audit,entry_execution_unknown=entry_unknown,execution_unknown=bool(entry_unknown or ledger.capacity_unknown_roots),capacity_unknown_roots=sorted(ledger.capacity_unknown_roots))


def run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial=INITIAL,prepared=None,*,policy='NARROW'):
    book=_run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial,prepared,policy=policy)
    audit=[];roots={f['budget_id']:f['root_id'] for f in book['fills'] if f['side']=='BUY'}
    exits={}
    for f in book['fills']:
        if f['side']=='SELL':exits.setdefault(f['root_id'],[]).append(f['reason'])
    keys=('budget_id','event_id','mother_event_id','family_id','product_id','reference_epoch','u_date','execution_date',
        'qty_cap','allocated_risk','allocated_buffered_margin','allocated_fee','D_qty','D_state','D_unit_risk','D_unit_margin_plus_fee')
    for r in book['budgets']:
        if r.get('budget_kind')!='new_entry' or r['qty_cap']<=0:continue
        if not r.get('limit_pending') or r['D_state']=='pending':raise AssertionError('unclosed pending limit audit')
        row={key:r.get(key) for key in keys};row.update({key:value for key,value in r.items() if key.startswith('limit_')})
        row['root_id']=roots.get(r['budget_id']);row['exit_reasons']=';'.join(exits.get(row['root_id'],[]));audit.append(row)
    by_budget={r['budget_id']:r for r in audit}
    for f in book['fills']:
        if f['side']=='BUY' and Decimal(str(f['fill_price']))>Decimal(str(by_budget[f['budget_id']]['limit_L'])):
            raise AssertionError('final ledger BUY exceeds limit')
    book['limit_audit']=audit;book['numeric_inverse_unknown']=sum(r['D_state']=='numeric_inverse_unknown' for r in audit)
    return book
