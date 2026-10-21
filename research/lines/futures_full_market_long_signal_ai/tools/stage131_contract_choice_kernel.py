"""Stage131 local adapter: accepted070 arithmetic; immutable anchor and capacity only.

Pure synthetic callers supply all arrays. No import-time database/model/financial
entrypoint. Accepted sources are not modified or monkeypatched.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_FLOOR
import hashlib
import importlib.util
from pathlib import Path

TOOLS=Path(__file__).resolve().parent
P=TOOLS/'stage070_policy_kernel.py'
if hashlib.sha256(P.read_bytes()).hexdigest()!='ad000624bd9722b3f1c580d622df2fc190330bac9e3c04011856085d56abcffe':
    raise ValueError('accepted070 kernel changed')
spec=importlib.util.spec_from_file_location('stage131_original070',P)
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
ref=original.ref
for name in ('INITIAL','SINGLE_RISK','TOTAL_RISK','MARGIN_CAP','MARGIN_BUFFER','finite','positive',
             'floor_lot','insolvency_flag','select_family_candidates','next_boundary','price_exit_reference',
             'adverse_quote','margin_rate','execution_quantity','policy_k','reduction_targets','organize','summary_metrics'):
    globals()[name]=getattr(original,name)


def capacity_limits(volume,round_lot):
    if not finite(volume) or volume<0 or not positive(round_lot) or int(round_lot)!=round_lot:
        return None
    lot=int(round_lot)
    gross=int((Decimal(str(volume))/Decimal(100)/Decimal(lot)).to_integral_value(rounding=ROUND_FLOOR))*lot
    return gross,(gross//(2*lot))*lot


def capacity_at(market,epoch,k,round_lot):
    if k<0:return None
    bar=market.bar(epoch,k)
    return None if bar is None else capacity_limits(bar['volume'],round_lot)


def anchor_request(position,current_reference,next_day):
    if next_day>=position['expiry']:return 'lifecycle_exit'
    if position.get('force_reason'):return position['force_reason']
    if not current_reference:return 'observation_exit_requested'
    if current_reference!=position['anchor_epoch']:return 'liquidity_reference_changed'
    return None


def reserve_capped(candidates,equity,existing_risk,existing_margin,economics,scenario,policy='NARROW'):
    rows=original.reserve_batch(candidates,equity,existing_risk,existing_margin,economics,scenario,policy)
    for row in rows:
        row['original_qty_cap']=row['qty_cap']
        cap=row['entry_capacity_qty']
        if not finite(cap) or int(cap)!=cap or cap<0:raise ValueError('known integer u entry capacity required')
        row['qty_cap']=min(row['qty_cap'],int(cap))
        row['capacity_entry_qty_u']=int(cap)
        if row['qty_cap']==0 and row['original_qty_cap']>0:row['budget_state']='capacity_below_one_roundtrip'
    return rows


class CapacityLedger(ref.CashLedger):
    def __init__(self,initial,market,dates,economics,account_id):
        super().__init__(initial)
        self.market=market;self.dates=dates;self.economics=economics;self.account_id=account_id
        self.date_index={d:k for k,d in enumerate(dates)}
        self.capacity_audit=[];self.capacity_gross={};self.capacity_unknown_roots=set()

    def audit(self,fill):
        k=self.date_index[fill['date']];epoch=fill['epoch'];lot=int(self.economics[epoch]['round_lot'])
        bar=self.market.bar(epoch,k-1) if k>0 else None
        limits=None if bar is None else capacity_limits(bar['volume'],lot)
        cap=None if limits is None else limits[0]
        key=(epoch,k);prior=self.capacity_gross.get(key,0);total=prior+int(fill['qty']);self.capacity_gross[key]=total
        unknown=cap is None or total>cap
        state='execution_capacity_unknown' if unknown else 'within_fixed_daily_capacity'
        if unknown:self.capacity_unknown_roots.add(fill['root_id'])
        row=dict(account_id=self.account_id,root_id=fill['root_id'],fill_sequence=len(self.capacity_audit),
            epoch=epoch,fill_date=fill['date'],capacity_reference_date=self.dates[k-1] if k>0 else None,
            capacity_reference_volume=None if bar is None else bar['volume'],capacity_cap_qty=cap,
            prior_same_epoch_day_gross_qty=prior,fill_qty=int(fill['qty']),
            cumulative_same_epoch_day_gross_qty=total,capacity_state=state,
            side=fill['side'],reason=fill['reason'],lot=lot)
        self.capacity_audit.append(row);fill['capacity_state']=state

    def enter(self,*args,**kwargs):
        super().enter(*args,**kwargs);self.audit(self.fills[-1])

    def exit(self,*args,**kwargs):
        super().exit(*args,**kwargs);self.audit(self.fills[-1])


def run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial=INITIAL,prepared=None,*,policy='NARROW'):
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

