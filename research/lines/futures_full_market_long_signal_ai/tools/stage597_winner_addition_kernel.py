"""Stage596 isolated multi-root adapter; accepted131 costs and frozen per-root risk.

Pure synthetic/historical caller only: no file I/O, model, or entrypoint. Opening
SELLs, frozen opening BUYs, intraday stops, then closing marks are separate phases.
"""
from stage131_contract_choice_kernel import *
import stage131_contract_choice_kernel as accepted


def _integer(value):
    return finite(value) and value >= 0 and int(value) == value


def add_proposal(candidate,positions,totals,market,dates,u,economics,scenario):
    c=candidate;epoch=c['reference_epoch'];fam=c['family_id'];own=[p for p in positions if p['family_id']==fam]
    a=dict(event_id=c['event_id'],family_id=fam,product_id=c['product_id'],reference_epoch=epoch,
        u_date=dates[u],execution_date=dates[u+1] if u+1<len(dates) else None,
        parent_root_ids=[p['root_id'] for p in own],u_equity=totals['equity'],net_remaining_profit=None,
        old_family_F0=None,old_total_F0=totals['initial_risk'],family_headroom=None,
        total_headroom=None,margin_headroom=None,old_epoch_qty=None,gross_capacity_u=None,
        add_capacity_u=None,prebatch_qty_upper=None,target_qty_unscaled=None,joint_scale=None,
        qty_cap=0,D_qty=0,reason='add_unclassified',unknown=False)
    def stop(reason,unknown=False):
        a.update(reason=reason,unknown=unknown);return None,a
    if not own:return stop('add_no_parent')
    if any(p.get('stale') for p in positions):return stop('add_unknown_stale_equity',True)
    if any(p['epoch']!=epoch for p in own):return stop('add_selected_epoch_mismatch')
    if any(p.get('deferred') for p in own):return stop('add_unknown_deferred_parent',True)
    if any(p.get('force_reason') or p.get('reduce_to') is not None for p in own):return stop('add_parent_exit_pending')
    if not all(finite(totals.get(f)) for f in ('equity','initial_risk','buffered_margin')):return stop('add_unknown_equity_budget',True)
    if c.get('u_index')!=u or c.get('u_date')!=dates[u] or c.get('D_index')!=u+1:return stop('add_unknown_source_clock',True)
    bar=market.bar(epoch,u)
    if bar is None or not positive(bar.get('close')) or not positive(c.get('u_close')) or c['u_close']!=bar['close']:
        return stop('add_unknown_native_u_close',True)
    if not positive(c.get('N_u')) or not positive(c.get('low20_u')):return stop('add_unknown_source_indicator',True)
    if not _integer(c.get('lifecycle_index')):return stop('add_unknown_lifecycle',True)
    if u+1>=c['lifecycle_index']:return stop('add_lifecycle_entry_rejected')
    for p in own:
        if not (_integer(p.get('qty')) and p['qty']>0 and _integer(p.get('initial_qty')) and p['initial_qty']>=p['qty']
            and positive(p.get('entry_fill')) and finite(p.get('entry_fees')) and p['entry_fees']>=0
            and positive(p.get('risk_per_lot')) and _integer(p.get('expiry')) and positive(p.get('last_mark'))):
            return stop('add_unknown_parent_basis',True)
        if p['last_mark']!=bar['close']:return stop('add_unknown_parent_mark',True)
        if u+1>=p['expiry']:return stop('add_parent_lifecycle_exit')
    e=economics[epoch];lot=int(e['round_lot']);sell=adverse_quote(c['u_close'],'SELL',e,scenario)
    a['net_remaining_profit']=sum(p['qty']*(float(e['contract_multiplier'])*(sell['fill_price']-p['entry_fill'])
        -p['entry_fees']/p['initial_qty']-sell['fee_per_lot']) for p in own)
    a['old_family_F0']=sum(p['qty']*p['risk_per_lot'] for p in own)
    a['family_headroom']=max(0.,SINGLE_RISK*totals['equity']-a['old_family_F0'])
    a['total_headroom']=max(0.,TOTAL_RISK*totals['equity']-totals['initial_risk'])
    a['margin_headroom']=max(0.,MARGIN_CAP*totals['equity']-totals['buffered_margin'])
    if a['net_remaining_profit']<=0:return stop('add_net_remaining_profit_not_positive')
    unit=original.unit_estimate(c['u_close'],c['N_u'],e,scenario,'NARROW')
    a.update(unit_risk_u=unit['risk_per_lot'],unit_margin_u=unit['buffered_margin_per_lot'])
    limits=capacity_limits(bar.get('volume'),lot);G=c.get('u_gross_capacity_qty');cap=c.get('entry_capacity_qty')
    if limits is None or not _integer(G) or G!=limits[0] or not _integer(cap) or cap!=limits[1]:
        return stop('add_unknown_u_capacity',True)
    same_epoch=[p for p in positions if p['epoch']==epoch]
    if any(not _integer(p.get('qty')) for p in same_epoch):return stop('add_unknown_old_epoch_qty',True)
    S=sum(p['qty'] for p in same_epoch)
    addcap=min(int(cap),floor_lot(max(0.,G-S)/2,lot))
    upper=min(floor_lot(min(a['family_headroom']/unit['risk_per_lot'],a['total_headroom']/unit['risk_per_lot'],
        a['margin_headroom']/unit['buffered_margin_per_lot']),lot),addcap)
    a.update(old_epoch_qty=S,gross_capacity_u=int(G),add_capacity_u=addcap,prebatch_qty_upper=upper)
    if upper<lot:return stop('add_prebatch_below_one_lot')
    a['reason']='add_prebatch_eligible'
    return dict(c,entry_kind='add',parent_root_ids=a['parent_root_ids'],add_family_headroom=a['family_headroom'],
        add_capacity_u=addcap,gross_capacity_u=int(G),old_epoch_qty=S),a


def reserve_mixed(candidates,equity,existing_risk,existing_margin,economics,scenario):
    # Identical070 real allocation; add differs only in remaining family budget.
    proposals=[]
    for c in candidates:
        e=economics[c['reference_epoch']];unit=original.unit_estimate(c['u_close'],c['N_u'],e,scenario,'NARROW')
        budget=c['add_family_headroom'] if c.get('entry_kind')=='add' else SINGLE_RISK*equity
        real=max(0.,budget/unit['risk_per_lot']) if equity>0 else 0.
        proposals.append((c,e,unit,real))
    totalrisk=sum(x[2]['risk_per_lot']*x[3] for x in proposals);totalmargin=sum(x[2]['buffered_margin_per_lot']*x[3] for x in proposals)
    available_risk=max(0.,TOTAL_RISK*equity-existing_risk);available_margin=max(0.,MARGIN_CAP*equity-existing_margin)
    scale=min(1.,available_risk/totalrisk if totalrisk else 1.,available_margin/totalmargin if totalmargin else 1.) if equity>0 else 0.
    rows=[]
    for c,e,unit,real in proposals:
        target=real*scale;lot=int(e['round_lot']);q=floor_lot(target,lot);cap=c['entry_capacity_qty']
        if not _integer(cap):raise ValueError('known integer u entry capacity required')
        if c.get('entry_kind')=='add':cap=min(cap,c['add_capacity_u'])
        row=dict(c,u_equity=equity,existing_risk=existing_risk,existing_buffered_margin=existing_margin,
            unit_risk_u=unit['risk_per_lot'],unit_margin_u=unit['buffered_margin_per_lot'],unit_fee_reserve_u=unit['fee_roundtrip_per_lot'],
            target_qty_unscaled=real,joint_scale=scale,target_qty_prefloor=target,qty_cap=min(q,int(cap)),round_lot=lot,
            original_qty_cap=q,capacity_entry_qty_u=int(cap),allocated_risk=target*unit['risk_per_lot'],
            allocated_buffered_margin=target*unit['buffered_margin_per_lot'],allocated_fee=target*unit['fee_roundtrip_per_lot'],
            budget_state='reserved' if q>0 else 'risk_margin_or_one_lot_rejected')
        if row['qty_cap']==0 and q>0:row['budget_state']='capacity_below_one_roundtrip'
        rows.append(row)
    return rows


def shared_add_quantity(qty,lot,G,gross,old_sell_reserve):
    return min(qty,floor_lot(max(0.,G-gross-old_sell_reserve)/2,lot))


class MultiRootLedger(CapacityLedger):
    def enter(self,root,*args,**kwargs):
        super().enter(root,*args,**kwargs)
        self.fills[-1].update(entry_kind=root.get('entry_kind','fresh'),parent_root_ids=root.get('parent_root_ids',[]))
    def exit(self,root_id,*args,**kwargs):
        p=self.positions[root_id];kind=p.get('entry_kind','fresh');parents=p.get('parent_root_ids',[])
        super().exit(root_id,*args,**kwargs)
        self.fills[-1].update(entry_kind=kind,parent_root_ids=parents)


def run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial=INITIAL,prepared=None,policy='NARROW'):
    potential,references=prepared if prepared is not None else organize(signals)
    ledger=MultiRootLedger(initial,market,dates,economics,account_id);daily=[];budgets=[];position_days=[]
    insolvent=False;pending=[];entry_unknown=[];add_audit=[];add_by_event={};add_root_ids=[]
    if policy!='NARROW':raise ValueError('Stage596 is fixed NARROW')
    def sync(intent,reason=None,unknown=False):
        if intent.get('entry_kind')!='add':return
        a=add_by_event[intent['event_id']]
        for key in ('target_qty_unscaled','joint_scale','qty_cap','D_qty','D_state','D_unit_risk','D_unit_margin_plus_fee'):
            if key in intent:a[key]=intent[key]
        if reason:a['reason']=reason
        a['unknown']=bool(a['unknown'] or unknown)
    def prepare(u,pre_window=False):
        nonlocal insolvent
        t=ledger.totals();insolvent=insolvency_flag(insolvent,t['equity']);positions=list(ledger.positions.values())
        over=t['initial_risk']>TOTAL_RISK*t['equity'] or t['buffered_margin']>MARGIN_CAP*t['equity']
        if insolvent or over:
            factor=min(1.,TOTAL_RISK*t['equity']/t['initial_risk'] if t['initial_risk'] else 1.,MARGIN_CAP*t['equity']/t['buffered_margin'] if t['buffered_margin'] else 1.) if not insolvent else 0.
            for p,target in zip(positions,reduction_targets(positions,0. if insolvent else t['equity'])):
                reduction=dict(budget_id=account_id+'_reduce_'+p['root_id']+'_'+dates[u],budget_kind='existing_position_reduction',root_id=p['root_id'],event_id=p['event_id'],reference_epoch=p['epoch'],family_id=p['family_id'],
                    account_id=account_id,scenario=scenario,u_date=dates[u],execution_date=dates[u+1] if u+1<len(dates) else None,u_equity=t['equity'],existing_risk=t['initial_risk'],existing_buffered_margin=t['buffered_margin'],
                    joint_scale=factor,existing_qty=p['qty'],target_existing_qty=target,qty_cap=p['qty']-target,D_qty=0,D_state='scheduled_reduction',pre_window_reservation=pre_window)
                budgets.append(reduction);p['reduce_to']=target;p['reduction_record']=reduction
        occupied={p['family_id'] for p in positions};chosen,rejected=select_family_candidates(potential.get(u,[]),occupied,economics,cash=True)
        chosen=[dict(c,entry_kind='fresh',parent_root_ids=[]) for c in chosen]
        winners,_=select_family_candidates(potential.get(u,[]),set(),economics,cash=True)
        for c in winners:
            if c['family_id'] not in occupied:continue
            proposal,a=add_proposal(c,positions,t,market,dates,u,economics,scenario)
            if c['event_id'] in add_by_event:raise ValueError('duplicate add event identity')
            add_audit.append(a);add_by_event[c['event_id']]=a
            if proposal is not None:
                chosen.append(proposal);rejected.pop(c['event_id'],None)
            else:rejected[c['event_id']]=a['reason']
        if insolvent or over:
            for c in chosen:
                reason='insolvent_permanent_pause' if insolvent else 'existing_risk_margin_over_cap'
                rejected[c['event_id']]=reason;sync(c,reason)
            chosen=[]
        executable=[]
        for c in chosen:
            e=economics[c['reference_epoch']];D=u+1
            if D>=c['lifecycle_index'] or (e.get('listed_date') and dates[D]<e['listed_date']):
                rejected[c['event_id']]='lifecycle_entry_rejected';sync(c,'lifecycle_entry_rejected');continue
            if D>end:
                rejected[c['event_id']]='window_end_no_execution';sync(c,'window_end_no_execution');continue
            executable.append(c)
        rows=reserve_mixed(executable,t['equity'],t['initial_risk'],t['buffered_margin'],economics,scenario)
        for r in rows:
            r.update(budget_id=account_id+'_'+r['event_id'],budget_kind='new_entry',account_id=account_id,scenario=scenario,u_date=dates[u],execution_date=dates[u+1],pre_window_reservation=pre_window,
                D_qty=0,D_state='pending' if r['qty_cap']>0 else r['budget_state'])
            budgets.append(r);sync(r,r['D_state'])
        for event,reason in rejected.items():
            budgets.append(dict(budget_id=account_id+'_'+event,event_id=event,account_id=account_id,scenario=scenario,u_date=dates[u],execution_date=dates[u+1] if u+1<len(dates) else None,
                pre_window_reservation=pre_window,u_equity=t['equity'],existing_risk=t['initial_risk'],existing_buffered_margin=t['buffered_margin'],qty_cap=0,D_qty=0,budget_state=reason,D_state=reason,
                entry_kind='add' if event in add_by_event else 'fresh'))
        return [r for r in rows if r['qty_cap']>0]
    if start>0:pending=prepare(start-1,True)
    for k in range(start,end+1):
        day=dates[k];opening_sells=set()
        # Phase1: only opening-known exits/reductions; protective SELLs are never capped.
        for root_id,p in list(ledger.positions.items()):
            bar=market.bar(p['epoch'],k)
            if bar is None:
                if p.get('reduction_record'):p['reduction_record']['D_state']='missing_quote_deferred_exit'
                p['deferred']=True;p['force_reason']='research_deferred_liquidation';ledger.mark(root_id,None,True);continue
            force='research_deferred_liquidation' if p['deferred'] else p.get('force_reason')
            if force:
                if p.get('reduction_record'):p['reduction_record'].update(D_state='forced_full_exit_priority',D_qty=p['qty'])
                quote=adverse_quote(bar['open'],'SELL',economics[p['epoch']],scenario)
                ledger.exit(root_id,p['qty'],bar['open'],quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot'],day,force);opening_sells.add(p['family_id']);continue
            target=p.get('reduce_to')
            if target is not None and target<p['qty']:
                quote=adverse_quote(bar['open'],'SELL',economics[p['epoch']],scenario);qty=p['qty']-target
                reduction=p.get('reduction_record');reduction_id=reduction['budget_id'] if reduction else None
                if reduction:reduction.update(D_state='executed_reduction',D_qty=qty)
                ledger.exit(root_id,qty,bar['open'],quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot'],day,'risk_margin_joint_reduction',reduction_id)
                opening_sells.add(p['family_id'])
                if root_id not in ledger.positions:continue
                p['reduce_to']=None;p['reduction_record']=None
            if bar['open']<=p['boundary']:
                quote=adverse_quote(bar['open'],'SELL',economics[p['epoch']],scenario)
                ledger.exit(root_id,p['qty'],bar['open'],quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot'],day,'gap_stop');opening_sells.add(p['family_id'])
        # Phase2: frozen u orders; no D low/close, no cancellation money recycling.
        old_roots=set(ledger.positions)
        for intent in pending:
            epoch=intent['reference_epoch'];e=economics[epoch];bar=market.bar(epoch,k);fam=intent['family_id'];isadd=intent.get('entry_kind')=='add'
            if bar is None:
                intent['D_state']='entry_execution_unknown';entry_unknown.append(dict(intent,state='entry_execution_unknown',date=day));sync(intent,intent['D_state'],True);continue
            own=[p for p in ledger.positions.values() if p['family_id']==fam]
            if isadd:
                if fam in opening_sells:
                    intent['D_state']='add_opening_family_sell';sync(intent,intent['D_state']);continue
                if not own or any(p['epoch']!=epoch or p.get('stale') or p.get('deferred') or p.get('force_reason') for p in own):
                    intent['D_state']='add_parent_state_unavailable';sync(intent,intent['D_state'],True);continue
            elif fam in opening_sells or own:
                intent['D_state']='same_day_or_occupied_entry_cancel';continue
            if k>=intent['lifecycle_index']:
                intent['D_state']='lifecycle_entry_rejected';sync(intent,intent['D_state']);continue
            F=bar['open'];SL0=F-policy_k(policy)*intent['N_u']
            if F<=intent['low20_u']:
                intent['D_state']='stale_breakout_cancel_at_open';sync(intent,intent['D_state']);continue
            if SL0<=0 or not positive(intent['N_u']):
                intent['D_state']='invalid_initial_risk_cancel';sync(intent,intent['D_state']);continue
            qty,unit=execution_quantity(intent,F,e,scenario,policy)
            intent.update(D_unit_risk=unit['risk_per_lot'],D_unit_margin_plus_fee=unit['actual_margin_plus_entry_fee_per_lot'],D_qty=qty)
            if qty==0:
                intent['D_state']='own_open_allocation_insufficient';sync(intent,intent['D_state']);continue
            if isadd:
                gross=ledger.capacity_gross.get((epoch,k),0);S=sum(p['qty'] for rid,p in ledger.positions.items() if rid in old_roots and p['epoch']==epoch)
                qty=shared_add_quantity(qty,int(e['round_lot']),intent['gross_capacity_u'],gross,S);intent['D_qty']=qty
                add_by_event[intent['event_id']].update(D_prior_gross=gross,D_old_sell_reserve=S,D_frozen_gross=intent['gross_capacity_u'])
                if qty==0:
                    intent['D_state']='add_shared_capacity_below_one_lot';sync(intent,intent['D_state']);continue
            quote=unit['buy'];root=dict(root_id=account_id+'_'+intent['event_id'],event_id=intent['event_id'],family_id=fam,product_id=intent['product_id'],epoch=epoch,
                mother_event_id=intent.get('mother_event_id',''),anchor_epoch=intent['anchor_epoch'],entry_capacity_qty=intent['entry_capacity_qty'],entry_date=day,entry_index=k,u_date=intent['u_date'],budget_id=intent['budget_id'],multiplier=float(e['contract_multiplier']),round_lot=int(e['round_lot']),
                margin_rate=margin_rate(e,scenario),risk_per_lot=unit['risk_per_lot'],SL0=SL0,boundary=next_boundary(SL0,intent['low20_u']),R0=policy_k(policy)*intent['N_u'],expiry=intent['lifecycle_index'],
                tickized=quote['tickized'],future_info_scope=e.get('future_info_scope',''),economics_status=e['economics_status'],entry_kind=intent['entry_kind'],parent_root_ids=intent.get('parent_root_ids',[]))
            ledger.enter(root,qty,F,quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot'])
            intent['D_state']='entered' if qty==intent['qty_cap'] else 'entered_reduced_own_allocation';sync(intent,intent['D_state'])
            if isadd:
                add_root_ids.append(root['root_id']);add_by_event[intent['event_id']]['root_id']=root['root_id']
        pending=[]
        # Phase3: old and new roots independently meet their own frozen boundary.
        for root_id,p in list(ledger.positions.items()):
            bar=market.bar(p['epoch'],k)
            if bar is None:continue
            reference,reason=price_exit_reference(bar['open'],bar['low'],p['boundary'],None)
            if reference is not None:
                quote=adverse_quote(reference,'SELL',economics[p['epoch']],scenario)
                ledger.exit(root_id,p['qty'],reference,quote['fill_price'],quote['fee_per_lot'],quote['slippage_per_lot'],day,reason)
        # Phase4: only now close marks and the next u boundary/anchor request.
        for root_id,p in ledger.positions.items():
            bar=market.bar(p['epoch'],k)
            if bar is not None:ledger.mark(root_id,bar['close'],False)
        position_day_start=len(position_days)
        for root_id,p in ledger.positions.items():
            if not p['stale']:
                indicator=market.indicator(p['epoch'],k);p['boundary']=next_boundary(p['SL0'],indicator['low20'])
                p['force_reason']=anchor_request(p,references.get(k,{}).get(p['product_id']),k+1)
                if p['force_reason'] and not p.get('anchor_request_date'):p['anchor_request_date']=day;p['anchor_request_reason']=p['force_reason']
            position_days.append(dict(account_id=account_id,scenario=scenario,date=day,root_id=root_id,event_id=p['event_id'],family_id=p['family_id'],product_id=p['product_id'],epoch=p['epoch'],qty=p['qty'],entry_fill=p['entry_fill'],entry_reference=p['entry_reference'],
                multiplier=p['multiplier'],margin_rate=p['margin_rate'],risk_per_lot=p['risk_per_lot'],mark=p['last_mark'],mark_state='stale' if p['stale'] else 'native_close',stale_days=p['stale_days'],
                SL0=p['SL0'],boundary_next=p['boundary'],force_next=p['force_reason'],unrealized=p['qty']*p['multiplier']*(p['last_mark']-p['entry_fill']),notional=p['qty']*p['multiplier']*p['last_mark'],entry_kind=p['entry_kind'],parent_root_ids=p.get('parent_root_ids',[])))
        t=ledger.totals();insolvent=insolvency_flag(insolvent,t['equity']);pending=prepare(k) if k<end else []
        reservation=sum(r['allocated_buffered_margin']+r['allocated_fee'] for r in pending)
        for row in position_days[position_day_start:]:row['reduce_to_next']=ledger.positions[row['root_id']].get('reduce_to')
        daily.append(dict(account_id=account_id,scenario=scenario,date=day,**t,new_order_reserve=reservation,total_reserve=t['buffered_margin']+reservation,
            new_order_risk_reserve=sum(r['allocated_risk'] for r in pending),new_order_margin_reserve=sum(r['allocated_buffered_margin'] for r in pending),new_order_fee_reserve=sum(r['allocated_fee'] for r in pending),
            ever_insolvent=insolvent,equity_identity_error=t['equity']-(initial+t['cumulative_realized_gross']-t['cumulative_fees']+t['unrealized'])))
        if abs(daily[-1]['equity_identity_error'])>1e-6:raise AssertionError('daily equity identity broken')
    for fill in ledger.fills:fill.update(account_id=account_id,scenario=scenario)
    # A shared epoch/day overflow affects all involved roots; exits remain untruncated.
    bad={(a['epoch'],a['fill_date']) for a in ledger.capacity_audit if a['capacity_state']=='execution_capacity_unknown'}
    ledger.capacity_unknown_roots.update(a['root_id'] for a in ledger.capacity_audit if (a['epoch'],a['fill_date']) in bad)
    for p in ledger.closed+list(ledger.positions.values()):p['execution_capacity_unknown']=p['root_id'] in ledger.capacity_unknown_roots
    opens=[dict(p,state='stale_open_unresolved' if p['stale'] else 'open_right_censored',unrealized=p['qty']*p['multiplier']*(p['last_mark']-p['entry_fill'])) for p in ledger.positions.values()]
    return dict(fills=ledger.fills,daily=daily,budgets=budgets,position_days=position_days,closed_episodes=ledger.closed,open_episodes=opens,
        summary=summary_metrics(daily,ledger,insolvent),capacity_audit=ledger.capacity_audit,entry_execution_unknown=entry_unknown,
        execution_unknown=bool(entry_unknown or ledger.capacity_unknown_roots or any(a['unknown'] for a in add_audit)),
        capacity_unknown_roots=sorted(ledger.capacity_unknown_roots),add_audit=add_audit,add_root_ids=add_root_ids)
