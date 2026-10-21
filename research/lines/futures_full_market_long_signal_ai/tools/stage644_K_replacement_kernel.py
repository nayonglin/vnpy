"""Frozen643 local131 adapter: one exclusive old slot, independent new K root.

No actual I/O on import. Ordinary131 arithmetic and old-position loop stay local
and unchanged; replacements never use D ledger equity or redistribute budgets.
"""
from pathlib import Path
import importlib.util
import math

P=Path(__file__).resolve().parent/'stage131_contract_choice_kernel.py'
spec=importlib.util.spec_from_file_location('stage644_accepted131',P)
accepted=importlib.util.module_from_spec(spec);spec.loader.exec_module(accepted)
original=accepted.original
ref=accepted.ref
for name in ('INITIAL','SINGLE_RISK','TOTAL_RISK','MARGIN_CAP','MARGIN_BUFFER','finite','positive',
             'floor_lot','insolvency_flag','select_family_candidates','next_boundary','price_exit_reference',
             'adverse_quote','margin_rate','execution_quantity','policy_k','reduction_targets','organize',
             'summary_metrics','reserve_capped','CapacityLedger','anchor_request'):
    globals()[name]=getattr(accepted,name)

LINEAGE=('source_lifecycle_index','voluntary_boundary_index','effective_lifecycle_index',
    'effective_boundary_origin','K_state','K_target_date','K_date')

def source_metadata(row):return {k:row.get(k) for k in LINEAGE}

def integer(x):
    try:return not isinstance(x,bool) and math.isfinite(float(x)) and int(float(x))==float(x)
    except (TypeError,ValueError,OverflowError):return False

def replacement_reason(p,c,u,references,economics,t,dates=None):
    """Only completed u information; known false and unknown remain distinct."""
    origin=p.get('effective_boundary_origin')
    if origin in ('source_lifecycle','same_source_and_voluntary'):return 'old_boundary_not_strict_pure_K',False
    if origin!='voluntary_calendar':return 'old_K_lineage_unknown',True
    source,K,eff=(p.get(k) for k in LINEAGE[:3])
    if not all(integer(v) for v in (source,K,eff)):return 'old_K_lineage_unknown',True
    D=u+1
    if not (int(K)==D<int(source) and int(eff)==D and p['expiry']==D and
            p.get('effective_boundary_origin')=='voluntary_calendar'):
        return 'old_boundary_not_strict_pure_K',False
    if p.get('stale') or p.get('deferred') or p.get('stale_days',0):return 'old_stale_or_deferred',True
    if p.get('force_reason')!='lifecycle_exit':return 'old_other_force',False
    if p.get('reduce_to') is not None or p.get('reduction_record'):return 'old_reduction_pending',False
    if t['equity']<=0 or t['initial_risk']>TOTAL_RISK*t['equity'] or t['buffered_margin']>MARGIN_CAP*t['equity']:
        return 'u_original_account_blocked',False
    canonical=references.get(u,{}).get(p['product_id'])
    if not canonical:return 'old_canonical_unknown',True
    if canonical!=p['anchor_epoch']:return 'old_canonical_changed',False
    if c is None:return 'no_original_same_u_winner',False
    if c['family_id']!=p['family_id'] or int(c['u_index'])!=u or int(c['D_index'])!=D:
        return 'original_intent_identity_conflict',True
    if c['reference_epoch']==p['epoch']:return 'same_actual_epoch',False
    if not ref.qualified_economics(economics.get(c['reference_epoch'],{})):return 'new_economics_unknown',True
    ns,nk,ne=(c.get(k) for k in LINEAGE[:3])
    if not all(integer(v) for v in (ns,ne)):return 'new_K_lineage_unknown',True
    if D>=int(ns) or D>=int(ne) or int(c['lifecycle_index'])!=int(ne):return 'new_lifecycle_entry_rejected',False
    if integer(nk):
        if D>=int(nk) or int(ne)!=min(int(ns),int(nk)):return 'new_K_entry_rejected',False
        expected='same_source_and_voluntary' if int(ns)==int(nk) else 'source_lifecycle' if int(ns)<int(nk) else 'voluntary_calendar'
        if c.get('effective_boundary_origin')!=expected:return 'new_K_origin_conflict',True
    elif not (c.get('K_state')=='after_calendar_pending' and c.get('effective_boundary_origin')=='source_lifecycle'
              and int(ne)==int(ns) and c.get('K_target_date') and
              (dates is None or c['K_target_date']>dates[D])):
        return 'new_K_pending_unknown',True
    if not (positive(c.get('score')) and positive(c.get('N_u')) and positive(c.get('u_close')) and
            finite(c.get('low20_u')) and c.get('label_history_ready20')==1 and
            c.get('history_run',0)>=20 and c.get('potential')==1 and
            integer(c.get('entry_capacity_qty')) and c['entry_capacity_qty']>=1):
        return 'new_original_u_eligibility_unknown',True
    e=economics[c['reference_epoch']]
    if dates is not None and e.get('listed_date') and dates[D]<e['listed_date']:return 'new_not_listed',False
    return '',False

def reserve_slot(c,p,t,economics,scenario,ordinary):
    e=economics[c['reference_epoch']];unit=original.unit_estimate(c['u_close'],c['N_u'],e,scenario,'NARROW')
    h=p['qty'];Rold=h*p['risk_per_lot'];Bold=MARGIN_BUFFER*h*p['last_mark']*p['multiplier']*p['margin_rate']
    oldfee=h*ref.fee_at(p['last_mark'],economics[p['epoch']],scenario)
    Rslot=min(Rold,SINGLE_RISK*t['equity']);fundunit=unit['buffered_margin_per_lot']+unit['fee_roundtrip_per_lot']
    target=max(0.,min(c['entry_capacity_qty'],Rslot/unit['risk_per_lot'],max(0.,Bold-oldfee)/fundunit))
    q=floor_lot(target,int(e['round_lot']))
    return dict(c,entry_kind='K_replacement',old_root_id=p['root_id'],old_event_id=p['event_id'],old_epoch=p['epoch'],
        old_qty=h,old_mark_u=p['last_mark'],old_multiplier=p['multiplier'],old_margin_rate=p['margin_rate'],
        old_anchor=p['anchor_epoch'],old_risk=Rold,old_buffered_margin=Bold,old_buffered_margin_slot=Bold,
        old_sell_fee_u=oldfee,old_source_index=p.get('source_lifecycle_index'),old_K_index=p.get('voluntary_boundary_index'),
        u_equity=t['equity'],u_total_risk=t['initial_risk'],u_total_margin=t['buffered_margin'],R_slot=Rslot,
        unit_risk_u=unit['risk_per_lot'],unit_margin_u=unit['buffered_margin_per_lot'],unit_fee_reserve_u=unit['fee_roundtrip_per_lot'],
        ordinary_allocated_risk=sum(r['allocated_risk'] for r in ordinary),
        ordinary_allocated_funds=sum(r['allocated_buffered_margin']+r['allocated_fee'] for r in ordinary),
        ordinary_pending_risk=sum(r['allocated_risk'] for r in ordinary if r['qty_cap']>0),
        ordinary_pending_funds=sum(r['allocated_buffered_margin']+r['allocated_fee'] for r in ordinary if r['qty_cap']>0),
        round_lot=int(e['round_lot']),target_qty_prefloor=target,qty_cap=q,allocated_risk=target*unit['risk_per_lot'],
        allocated_buffered_margin=target*unit['buffered_margin_per_lot'],allocated_fee=target*unit['fee_roundtrip_per_lot'],
        allocated_funds=target*fundunit,D_qty=0,D_state='replacement_pending' if q else 'old_slot_below_one_lot',unknown=False)

def confirm_old(t,fills,positions,day):
    selected=[f for f in fills if f['root_id']==t['old_root_id'] and f['date']==day]
    base=dict(confirmed=False,unknown=True,reason='old_full_K_open_unconfirmed',ell=None)
    if (len(selected)!=1 or t['old_root_id'] in positions or selected[0]['side']!='SELL' or
            selected[0]['qty']!=t['old_qty'] or selected[0]['epoch']!=t['old_epoch']):return base
    f=selected[0]
    if f['reason']!='lifecycle_exit':return dict(base,unknown=False,reason='old_exit_not_pure_K_open')
    if f.get('capacity_state')!='within_fixed_daily_capacity':return dict(base,reason='old_capacity_unknown')
    if not positive(f.get('fill_price')) or not finite(f.get('fee')):return dict(base,reason='old_quote_unknown')
    ell=max(0.,t['old_qty']*t['old_multiplier']*(t['old_mark_u']-f['fill_price'])+f['fee'])
    return dict(confirmed=True,unknown=False,reason='confirmed_full_K_open',ell=ell,
        old_sell_fill_D=f['fill_price'],old_sell_fee_D=f['fee'],old_capacity_state=f['capacity_state'])

def size_batch(tokens,proofs,opening,economics,scenario):
    """Pure643 D allocation: no ledger equity, high, low, close or free cash."""
    if not tokens:return
    confirmed=[t for t in tokens if proofs[t['old_root_id']]['confirmed']]
    Evirt=max(0.,tokens[0]['u_equity']-sum(proofs[t['old_root_id']]['ell'] for t in confirmed))
    for t in tokens:
        proof=proofs[t['old_root_id']];t.update(old_confirmed=proof['confirmed'],old_confirmation_reason=proof['reason'],
            ell=proof.get('ell'),E_virtual=Evirt,D_qty=None if proof['unknown'] else 0,q_self=0,unknown=proof['unknown'])
        t.update({k:v for k,v in proof.items() if k.startswith('old_sell_') or k=='old_capacity_state'})
        if not proof['confirmed']:t['D_state']=proof['reason'];continue
        F=opening.get(t['event_id']);t['D_raw_open']=F
        if F is None or not positive(F):t.update(D_state='new_open_unknown',unknown=True,D_qty=None);continue
        if F<=t['low20_u']:t.update(D_state='stale_breakout_cancel_at_open',D_qty=0);continue
        if F-policy_k('NARROW')*t['N_u']<=0:t.update(D_state='invalid_initial_risk_cancel',D_qty=0);continue
        e=economics[t['reference_epoch']]
        try:unit=original.unit_estimate(F,t['N_u'],e,scenario,'NARROW')
        except (ValueError,ArithmeticError):t.update(D_state='new_quote_unknown',unknown=True,D_qty=None);continue
        cash=unit['buy']['fill_price']*float(e['contract_multiplier'])*margin_rate(e,scenario)+unit['buy']['fee_per_lot']
        fund=max(unit['buffered_margin_per_lot']+unit['fee_roundtrip_per_lot'],cash)
        rd=min(t['allocated_risk'],SINGLE_RISK*Evirt);bd=min(t['allocated_funds'],max(0.,t['old_buffered_margin_slot']-proof['ell']))
        q=floor_lot(max(0.,min(t['qty_cap'],rd/unit['risk_per_lot'],bd/fund)),t['round_lot'])
        t.update(R_D=rd,B_D=bd,unit_risk_D=unit['risk_per_lot'],unit_margin_D=unit['buffered_margin_per_lot'],
            unit_fee_RT_D=unit['fee_roundtrip_per_lot'],original_actual_margin_plus_BUYfee_D=cash,fund_unit_D=fund,
            candidate_BUYfill=unit['buy']['fill_price'],candidate_BUYfee=unit['buy']['fee_per_lot'],
            candidate_BUYslip=unit['buy']['slippage_per_lot'],q_self=q,D_qty=0,D_state='replacement_self_zero' if not q else 'replacement_batch_pending')
    active=[t for t in tokens if t['q_self']>0]
    rOther=tokens[0]['u_total_risk']-sum(t['old_risk'] for t in active)+tokens[0]['ordinary_allocated_risk']
    bOther=tokens[0]['u_total_margin']-sum(t['old_buffered_margin'] for t in active)+tokens[0]['ordinary_allocated_funds']
    rf=max(0.,TOTAL_RISK*Evirt-rOther);bf=max(0.,MARGIN_CAP*Evirt-bOther)
    rSum=sum(t['q_self']*t['unit_risk_D'] for t in active);bSum=sum(t['q_self']*t['fund_unit_D'] for t in active)
    scale=min(1.,rf/rSum if rSum else 1.,bf/bSum if bSum else 1.)
    for t in tokens:
        t.update(R_other=rOther,B_other=bOther,R_free=rf,B_free=bf,batch_risk_sum=rSum,batch_funds_sum=bSum,common_scale=scale)
        if t['q_self']>0:
            t['D_qty']=floor_lot(scale*t['q_self'],t['round_lot'])
            t['D_state']='replacement_ready' if t['D_qty'] else 'replacement_common_scale_zero'


def run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial=INITIAL,prepared=None,*,policy='NARROW'):
    potential,references=prepared if prepared is not None else organize(signals);ledger=CapacityLedger(initial,market,dates,economics,account_id);daily=[];budgets=[];position_days=[];insolvent=False;pending=[];entry_unknown=[]
    replacement_audit=[];replacement_root_ids=[];pending_swaps=[];replacement_unknown=False
    if policy != 'NARROW':raise ValueError('Stage131 is fixed NARROW')
    def prepare(u,pre_window=False):
        nonlocal insolvent,pending_swaps,replacement_unknown
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
        # BEGIN644_U: ordinary rows above remain original and keep all old slots.
        pending_swaps=[]
        for p in positions:
            if p['expiry']!=u+1:continue
            matches=[c for c in potential.get(u,[]) if c['family_id']==p['family_id']]
            if not matches:continue
            if len(matches)!=1:raise ValueError('unchanged157 unique family/u winner required')
            c=matches[0]
            reason,unknown=replacement_reason(p,c,u,references,economics,t,dates)
            if insolvent:reason,unknown='insolvent_permanent_pause',False
            if u+1>end:reason,unknown='window_end_no_execution',False
            if reason:
                r=dict(c,old_root_id=p['root_id'],old_event_id=p['event_id'],old_epoch=p['epoch'],
                    D_state=reason,D_qty=None if unknown else 0,qty_cap=None if unknown else 0,unknown=unknown)
            else:r=reserve_slot(c,p,t,economics,scenario,rows)
            r.update(account_id=account_id,scenario=scenario,u_date=dates[u],execution_date=dates[u+1],
                budget_id=account_id+'_swap_'+c['event_id'],budget_kind='conditional_K_replacement',pre_window_reservation=pre_window)
            replacement_audit.append(r);replacement_unknown=replacement_unknown or unknown
            if not reason and r['qty_cap']>0:pending_swaps.append(r)
        # END644_U
        return [r for r in rows if r['qty_cap']>0]
    if start>0:pending=prepare(start-1,True)
    for k in range(start,end+1):
        day=dates[k];closed_today=set();old_fill_start=len(ledger.fills)
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
        # BEGIN644_D: exact full K-open token, u snapshot and own D opens only.
        proofs={t['old_root_id']:confirm_old(t,ledger.fills[old_fill_start:],ledger.positions,day) for t in pending_swaps}
        opening={}
        for t in pending_swaps:
            b=market.bar(t['reference_epoch'],k);opening[t['event_id']]=None if b is None else b['open']
        size_batch(pending_swaps,proofs,opening,economics,scenario)
        for t in pending_swaps:
            replacement_unknown=replacement_unknown or t['unknown']
        execution_pending=pending+[t for t in pending_swaps if t.get('D_qty',0) is not None and t['D_qty']>0]
        # END644_D
        for intent in execution_pending:
            is_swap=intent.get('entry_kind')=='K_replacement'
            planned_swap_qty=intent['D_qty'] if is_swap else None
            epoch=intent['reference_epoch'];e=economics[epoch];bar=market.bar(epoch,k);fam=intent['family_id']
            if bar is None:
                intent['D_state']='entry_execution_unknown';entry_unknown.append(dict(intent,state='entry_execution_unknown',date=day));continue
            if (fam in closed_today and not is_swap) or any(p['family_id']==fam for p in ledger.positions.values()):intent['D_state']='same_day_or_occupied_entry_cancel';intent['D_qty']=0;continue
            if k>=intent['lifecycle_index']:intent['D_state']='lifecycle_entry_rejected';continue
            F=bar['open'];SL0=F-policy_k(policy)*intent['N_u']
            if F<=intent['low20_u']:intent['D_state']='stale_breakout_cancel_at_open';continue
            if SL0<=0 or not positive(intent['N_u']):intent['D_state']='invalid_initial_risk_cancel';continue
            qty,unit=execution_quantity(intent,F,e,scenario,policy)
            if is_swap:qty=min(qty,planned_swap_qty)
            intent['D_unit_risk']=unit['risk_per_lot'];intent['D_unit_margin_plus_fee']=unit['actual_margin_plus_entry_fee_per_lot'];intent['D_qty']=qty
            if qty==0:intent['D_state']='own_open_allocation_insufficient';continue
            quote=unit['buy'];root=dict(root_id=account_id+'_'+intent['event_id'],event_id=intent['event_id'],family_id=fam,product_id=intent['product_id'],epoch=epoch,
                mother_event_id=intent.get('mother_event_id',''),anchor_epoch=intent['anchor_epoch'],entry_capacity_qty=intent['entry_capacity_qty'],entry_date=day,entry_index=k,u_date=intent['u_date'],budget_id=intent['budget_id'],multiplier=float(e['contract_multiplier']),round_lot=int(e['round_lot']),
                margin_rate=margin_rate(e,scenario),risk_per_lot=unit['risk_per_lot'],SL0=SL0,boundary=next_boundary(SL0,intent['low20_u']),R0=policy_k(policy)*intent['N_u'],expiry=intent['lifecycle_index'],
                tickized=quote['tickized'],future_info_scope=e.get('future_info_scope',''),economics_status=e['economics_status'])
            root.update(source_metadata(intent),entry_kind='K_replacement' if is_swap else 'fresh',parent_root_id=intent.get('old_root_id',''))
            ledger.enter(root,qty,F,quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot']);intent['D_state']='entered' if qty==intent['qty_cap'] else 'entered_reduced_own_allocation'
            if is_swap:replacement_root_ids.append(root['root_id'])
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
                SL0=p['SL0'],boundary_next=p['boundary'],force_next=p['force_reason'],unrealized=p['qty']*p['multiplier']*(p['last_mark']-p['entry_fill']),notional=p['qty']*p['multiplier']*p['last_mark'],**source_metadata(p),entry_kind=p['entry_kind'],parent_root_id=p['parent_root_id']))
        t=ledger.totals();insolvent=insolvency_flag(insolvent,t['equity'])
        pending=prepare(k) if k<end else []
        reservation=sum(r['allocated_buffered_margin']+r['allocated_fee'] for r in pending)
        for row in position_days[position_day_start:]:row['reduce_to_next']=ledger.positions[row['root_id']].get('reduce_to')
        daily.append(dict(account_id=account_id,scenario=scenario,date=day,**t,new_order_reserve=reservation,total_reserve=t['buffered_margin']+reservation,
            new_order_risk_reserve=sum(r['allocated_risk'] for r in pending),new_order_margin_reserve=sum(r['allocated_buffered_margin'] for r in pending),new_order_fee_reserve=sum(r['allocated_fee'] for r in pending),
            replacement_contingent_funds=sum(r['allocated_funds'] for r in pending_swaps),replacement_contingent_risk=sum(r['allocated_risk'] for r in pending_swaps),
            ever_insolvent=insolvent,equity_identity_error=t['equity']-(initial+t['cumulative_realized_gross']-t['cumulative_fees']+t['unrealized'])))
        if abs(daily[-1]['equity_identity_error'])>1e-6:raise AssertionError('daily equity identity broken')
    for fill in ledger.fills:fill.update(account_id=account_id,scenario=scenario)
    for p in ledger.closed+list(ledger.positions.values()):p['execution_capacity_unknown']=p['root_id'] in ledger.capacity_unknown_roots
    opens=[dict(p,state='stale_open_unresolved' if p['stale'] else 'open_right_censored',unrealized=p['qty']*p['multiplier']*(p['last_mark']-p['entry_fill'])) for p in ledger.positions.values()]
    return dict(fills=ledger.fills,daily=daily,budgets=budgets,position_days=position_days,closed_episodes=ledger.closed,open_episodes=opens,summary=summary_metrics(daily,ledger,insolvent),capacity_audit=ledger.capacity_audit,entry_execution_unknown=entry_unknown,replacement_audit=replacement_audit,replacement_root_ids=replacement_root_ids,replacement_unknown=replacement_unknown,execution_unknown=bool(entry_unknown or ledger.capacity_unknown_roots or replacement_unknown),capacity_unknown_roots=sorted(ledger.capacity_unknown_roots))

