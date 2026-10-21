"""Isolated Stage069 two-policy kernel, pure until explicitly invoked.

Uses accepted042 cost/array/ledger definitions, never its financial entrypoints.
Policy-specific reservation, D execution and account replay are local functions;
no module global patching. All N are accepted Wilder20, stops use raw D.open.
"""
from __future__ import annotations
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL_SHA='0418566cd9b624fb5a985448b3b0d4c94dbef56280feffd49bce09e1c5bf2dde'
ACCEPTED042_SHA='ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d'
_path=TOOLS/'stage042_cross_session_experiment.py'
if hashlib.sha256(_path.read_bytes()).hexdigest()!=ACCEPTED042_SHA:
    raise ValueError('accepted042 pure dependency changed')
_spec=importlib.util.spec_from_file_location('stage070_accepted042_definitions',_path)
ref=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(ref)
for _name in ('INITIAL','SINGLE_RISK','TOTAL_RISK','MARGIN_CAP','MARGIN_BUFFER',
              'finite','positive','family','floor_lot','insolvency_flag','next_boundary',
              'price_exit_reference','close_exit_request','qualified_economics',
              'select_family_candidates','margin_rate','fee_at','adverse_quote',
              'CashLedger','organize','summary_metrics'):
    globals()[_name]=getattr(ref,_name)
POLICIES={'WIDE':2.,'NARROW':.25}


def policy_k(policy):
    if policy not in POLICIES:
        raise ValueError('policy must be WIDE or NARROW')
    return POLICIES[policy]


def unit_estimate(reference,N_u,econ,scenario,policy):
    if not positive(N_u):
        raise ValueError('N must be positive')
    buy=adverse_quote(reference,'BUY',econ,scenario)
    sell=adverse_quote(reference,'SELL',econ,scenario)
    rtfee=2.*fee_at(reference,econ,scenario)
    risk=policy_k(policy)*N_u*float(econ['contract_multiplier'])
    return dict(risk_per_lot=risk+rtfee+buy['slippage_per_lot']+sell['slippage_per_lot'],
                fee_roundtrip_per_lot=rtfee,
                buffered_margin_per_lot=MARGIN_BUFFER*reference*float(econ['contract_multiplier'])*margin_rate(econ,scenario),
                buy=buy,sell=sell)


def reserve_batch(candidates,equity,existing_risk,existing_margin,economics,scenario,policy):
    proposals=[]
    for c in candidates:
        e=economics[c['reference_epoch']];unit=unit_estimate(c['u_close'],c['N_u'],e,scenario,policy)
        real=max(0.,SINGLE_RISK*equity/unit['risk_per_lot']) if equity>0 else 0.
        proposals.append((c,e,unit,real))
    totalrisk=sum(x[2]['risk_per_lot']*x[3] for x in proposals);totalmargin=sum(x[2]['buffered_margin_per_lot']*x[3] for x in proposals)
    available_risk=max(0.,TOTAL_RISK*equity-existing_risk);available_margin=max(0.,MARGIN_CAP*equity-existing_margin)
    scale=min(1.,available_risk/totalrisk if totalrisk else 1.,available_margin/totalmargin if totalmargin else 1.) if equity>0 else 0.
    reservations=[]
    for c,e,unit,real in proposals:
        target=real*scale;lot=int(e['round_lot'])
        reservations.append(dict(c,u_equity=equity,existing_risk=existing_risk,existing_buffered_margin=existing_margin,
            unit_risk_u=unit['risk_per_lot'],unit_margin_u=unit['buffered_margin_per_lot'],unit_fee_reserve_u=unit['fee_roundtrip_per_lot'],
            target_qty_unscaled=real,joint_scale=scale,target_qty_prefloor=target,qty_cap=floor_lot(target,lot),round_lot=lot,
            allocated_risk=target*unit['risk_per_lot'],allocated_buffered_margin=target*unit['buffered_margin_per_lot'],
            allocated_fee=target*unit['fee_roundtrip_per_lot'],budget_state='reserved' if floor_lot(target,lot)>0 else 'risk_margin_or_one_lot_rejected'))
    return reservations
def execution_quantity(reservation,reference,econ,scenario,policy):
    unit=unit_estimate(reference,reservation['N_u'],econ,scenario,policy);buy=unit['buy'];mult=float(econ['contract_multiplier']);lot=int(econ['round_lot'])
    cashunit=buy['fill_price']*mult*margin_rate(econ,scenario)+buy['fee_per_lot']
    q=min(reservation['qty_cap'],floor_lot(reservation['allocated_risk']/unit['risk_per_lot'],lot),
        floor_lot((reservation['allocated_buffered_margin']+reservation['allocated_fee'])/cashunit,lot))
    return q,dict(unit,actual_margin_plus_entry_fee_per_lot=cashunit)
def reduction_targets(positions,equity):
    risk=sum(p['qty']*p['risk_per_lot'] for p in positions)
    margin=sum(MARGIN_BUFFER*p['qty']*p['last_mark']*p['multiplier']*p['margin_rate'] for p in positions)
    factor=min(1.,TOTAL_RISK*equity/risk if risk else 1.,MARGIN_CAP*equity/margin if margin else 1.) if equity>0 else 0.
    return [floor_lot(p['qty']*factor,p['round_lot']) for p in positions]


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


def safe(value):
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [safe(v) for v in value]
    if isinstance(value,np.integer):return int(value)
    if isinstance(value,np.bool_):return bool(value)
    if isinstance(value,(float,np.floating)):return float(value) if math.isfinite(value) else None
    return value


def export_native_cases(path,selections,label_frames,panel,market,dates,economics):
    """Finite first-cause evidence from arrays already loaded, no new source I/O.

    Each selected old epoch includes every calendar slot from its complete
    contiguous Wilder warmup through the decision, including explicit missing
    slots and the corresponding u reference schedule. Never select by PnL.
    """
    indexed={policy:frame.set_index('event_id') for policy,frame in label_frames.items()}
    cases=[]
    for selection in selections:
        policy,event=selection['policy'],selection['event_id']
        row=indexed[policy].loc[event]
        u=int(row.u_index);run=int(row.history_run);epoch=row.reference_epoch
        decision=int(np.searchsorted(dates,selection['date']))
        if decision>=len(dates) or dates[decision]!=selection['date']:
            raise ValueError('finite native decision outside source calendar')
        begin=max(0,u-run+1)
        bars=[];series=market.series.get(epoch)
        for k in range(begin,decision+1):
            j=series.locate(k) if series is not None else None
            bar=dict(source_index=k,date=dates[k],native_missing=j is None)
            if j is not None:
                bar.update(valid=bool(series.valid[j]),**dict(zip(('open','high','low','close','volume'),series.values[j].tolist())))
            bars.append(bar)
        schedule=panel.loc[panel.product_id.eq(row.product_id)&panel.u_date.between(dates[begin],dates[decision]),
                           ['u_date','reference_epoch','status']].to_dict('records')
        cases.append(dict(selection=selection,policy_k=policy_k(policy),event=row.to_dict(),
                          economics=economics.get(epoch),bars=bars,reference_schedule=schedule,
                          complete_calendar_slice=True,complete_contiguous_Wilder_warmup=True))
    payload=safe(dict(schema='stage070_finite_first_native_cases_v1',raw_ohlc=True,reproducibility_required=False,
                      selection='first event/root per predeclared cause in fixed iteration; never PnL selection',
                      native_source_queries=0,cases=cases))
    with gzip.GzipFile(filename=str(path),mode='xb',mtime=0) as stream:
        stream.write(json.dumps(payload,ensure_ascii=False,allow_nan=False).encode())
    return len(cases)


def source_bundle(stage):
    names=['stage070_policy_kernel.py','test_stage070_narrow_policy_cash.py','stage042_cross_session_experiment.py']
    if stage=='labels':names+=['stage070_narrow_labels.py']
    elif stage=='cash':names+=['stage070_narrow_policy_cash.py','stage070_narrow_labels.py','stage054_maturity_cash_compare.py']
    else:raise ValueError('unsupported stage')
    return sorted([ref.file_binding(TOOLS/name) for name in names],key=lambda x:x['path'])


def authorize(args,stage):
    """Reject before output creation and before opening native data."""
    output=Path(args.output).resolve()
    if output.exists():raise FileExistsError('fresh output required; no overwrite/retry '+str(output))
    binding=ref.file_binding(args.protocol)
    if binding['sha256']!=PROTOCOL_SHA or args.protocol_sha256!=PROTOCOL_SHA:
        raise ValueError('exact Stage069 protocol SHA required')
    protocol=json.loads(ref.read_bound(binding))
    if protocol.get('schema')!='stage069_settlement_narrow_joint_protocol_v1':
        raise ValueError('Stage069 protocol identity mismatch')
    authorization=json.loads(Path(args.authorization).read_bytes())
    required={'schema':'stage069_exact_root_authorization_v1','authorized_by':'root','stage':stage,
              'exact_source_authorized':True,'protocol_sha256':PROTOCOL_SHA,'output':str(output)}
    if any(authorization.get(k)!=v for k,v in required.items()):
        raise ValueError('missing exact root source/protocol/output authorization')
    if sorted(authorization.get('source_bundle',[]),key=lambda x:x['path'])!=source_bundle(stage):
        raise ValueError('root authorization source_bundle differs from current source/tests')
    if not isinstance(authorization.get('input_bindings'),dict):
        raise ValueError('root authorization must bind necessary actual inputs')
    for item in authorization['input_bindings'].values():
        # The native database is inherited stat/SHA only. Never whole-file hash.
        if item.get('kind')=='native_database_stat':ref.assert_db_binding(item)
        else:ref.read_bound(item)
    return protocol,binding,authorization,ref.file_binding(args.authorization)


def load_market_bridge(authorization):
    item=authorization['input_bindings']['market_protocol']
    protocol=json.loads(ref.read_bound(item))
    if protocol['accepted_kernel']['sha256']!=ACCEPTED042_SHA:
        raise ValueError('market bridge accepted042 binding differs')
    # This old protocol is a source bridge only, never an old financial run.
    panel,market,dates,economics,scope_dates,receipt=ref.load_all_inputs(protocol)
    if ref.NATIVE_QUERIES!=1:raise ValueError('exactly one shared native read required')
    return panel,market,dates,economics,scope_dates,receipt,protocol
