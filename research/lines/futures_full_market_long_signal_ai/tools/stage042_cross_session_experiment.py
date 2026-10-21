"""Stage039 frozen 55/20/2N cross-session price reference and research cash.

Accrual cash is not a broker variation-settlement balance. Slippage is in fill
prices and is never subtracted twice. All budgets are frozen at u close; each
own D open can only reduce/cancel its own cap and may use only its own prefloor
fractional reservation. Actual execution requires an explicit root-authorized
CLI call after source/test handoff. No models/download/CTP/production actions.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict,deque
from datetime import datetime,timezone
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR
import gzip
import hashlib
import io
import json
import math
from itertools import groupby
from pathlib import Path
import sqlite3
import sys
import time
import numpy as np
import pandas as pd

SCENARIOS={
    'base':dict(fee_min=2.,fee_bps=.0001,slip_bps=.0001,slip_ticks=1,margin_floor=.20),
    'stress':dict(fee_min=6.,fee_bps=.0003,slip_bps=.0003,slip_ticks=3,margin_floor=.40)}
INITIAL=1_000_000.;SINGLE_RISK=.0025;TOTAL_RISK=.02;MARGIN_CAP=.25;MARGIN_BUFFER=1.10
DESIGN_SHA='09f4102162116f1ac844328455b7365f31e6f916345e8885ccb6129de953101d'
MACHINE_SHA='58fe0f80de248f1d3095ac9ef859c0cb9bd84e369809a466f2b554dd38195466'
NATIVE_QUERIES=0

def finite(v):return isinstance(v,(int,float,np.number)) and math.isfinite(float(v))
def positive(v):return finite(v) and float(v)>0
def family(product_id):return product_id.removesuffix('_F')
def floor_lot(q,lot):return int(math.floor(max(0.,q)/lot))*int(lot)
def insolvency_flag(previous,equity):return bool(previous or equity<=0)

class EpochSeries:
    def __init__(self,days,values,valid):
        self.days=np.asarray(days,dtype=np.int32);self.values=np.asarray(values,dtype=float);self.valid=np.asarray(valid,dtype=bool)
        n=len(days);self.N=np.full(n,np.nan);self.low20=np.full(n,np.nan);self.high55=np.full(n,np.nan);self.run=np.zeros(n,dtype=np.int32)
        run=0;previous_day=None;previous_close=None;N=math.nan;seed=0.;highs=deque();lows=deque()
        for j,d in enumerate(self.days):
            if not self.valid[j]:
                run=0;previous_day=None;previous_close=None;N=math.nan;seed=0.;highs.clear();lows.clear();continue
            O,H,L,C,V=self.values[j]
            if previous_day is None or d!=previous_day+1:
                run=0;previous_close=None;N=math.nan;seed=0.;highs.clear();lows.clear()
            TR=H-L if previous_close is None else max(H-L,abs(H-previous_close),abs(L-previous_close))
            run+=1
            if run<=20:
                seed+=TR
                if run==20:N=seed/20.
            else:N=(19.*N+TR)/20.
            while highs and highs[0][0]<d-55:highs.popleft()
            if run>=56:self.high55[j]=highs[0][1]
            while highs and highs[-1][1]<=H:highs.pop()
            highs.append((int(d),float(H)))
            while lows and lows[0][0]<d-19:lows.popleft()
            while lows and lows[-1][1]>=L:lows.pop()
            lows.append((int(d),float(L)))
            if run>=20:self.low20[j]=lows[0][1]
            self.N[j]=N;self.run[j]=run;previous_day=int(d);previous_close=float(C)

    def locate(self,k):
        j=int(np.searchsorted(self.days,k))
        return j if j<len(self.days) and self.days[j]==k else None

class Market:
    def __init__(self,series,dates):self.series=series;self.dates=dates
    @classmethod
    def from_records(cls,records,dates):
        lookup={d:i for i,d in enumerate(dates)};groups=defaultdict(list)
        for r in records:
            if r['trade_date'] not in lookup:raise ValueError('native date outside bound full calendar')
            vals=[r[x] for x in ('open','high','low','close','volume')]
            valid=(r.get('quality_status')=='accepted' and all(positive(v) for v in vals) and vals[2]<=min(vals[0],vals[3]) and vals[1]>=max(vals[0],vals[3]))
            groups[r['contract_epoch_id']].append((lookup[r['trade_date']],vals,valid))
        series={}
        for epoch,rows in groups.items():
            rows.sort(key=lambda r:r[0]);days=[r[0] for r in rows]
            if len(set(days))!=len(days):raise ValueError('duplicate native epoch/day')
            series[epoch]=EpochSeries(days,[r[1] for r in rows],[r[2] for r in rows])
        return cls(series,dates)
    def bar(self,epoch,k):
        s=self.series.get(epoch)
        if s is None:return None
        j=s.locate(k)
        if j is None or not s.valid[j]:return None
        O,H,L,C,V=s.values[j]
        return dict(open=float(O),high=float(H),low=float(L),close=float(C),volume=float(V))
    def indicator(self,epoch,k):
        s=self.series.get(epoch);j=s.locate(k) if s is not None else None
        if j is None or not s.valid[j]:return dict(N=math.nan,run_length=0,high55_before=math.nan,low20=math.nan)
        return dict(N=float(s.N[j]),run_length=int(s.run[j]),high55_before=float(s.high55[j]),low20=float(s.low20[j]))

def lifecycle_index(econ,epoch,dates):
    nominal=epoch.rsplit('.',1)[-1];nominal_date=nominal[:4]+'-'+nominal[4:]+'-01'
    candidates=[nominal_date]
    for field in ('known_lifecycle_exit_boundary','nominal_month_first_date','maturity_date','de_listed_date'):
        value=econ.get(field)
        if isinstance(value,str) and len(value)>=10 and value[:10]>='1900-01-01':candidates.append(value[:10])
    return int(np.searchsorted(dates,min(candidates)))

def build_signals(panel,market,dates,economics):
    required=['event_id','product_id','exchange','product','u_date','reference_epoch','status','planned_execution_date','direction']
    if panel.event_id.duplicated().any() or panel.duplicated(['product_id','u_date']).any():raise ValueError('duplicate panel identity')
    lookup={d:i for i,d in enumerate(dates)};rows=[]
    for original in panel[required].to_dict('records'):
        u=lookup[original['u_date']];epoch=original['reference_epoch'];bar=market.bar(epoch,u) if epoch else None
        indicator=market.indicator(epoch,u) if epoch else dict(N=math.nan,run_length=0,high55_before=math.nan,low20=math.nan)
        ready=bar is not None and indicator['run_length']>=56 and positive(indicator['N'])
        breakout=bool(ready and bar['close']>indicator['high55_before'])
        state='ready_breakout' if breakout else 'ready_no_breakout' if ready else 'insufficient_or_gap_history' if bar else original['status']
        economic=economics.get(epoch,{})
        rows.append(dict(original,family_id=family(original['product_id']),u_index=u,D_index=u+1,
            policy_ready55=int(ready),breakout=int(breakout),potential=int(breakout),signal_state=state,
            N_u=indicator['N'],low20_u=indicator['low20'],high55_before=indicator['high55_before'],history_run=indicator['run_length'],
            u_close=bar['close'] if bar else np.nan,economics_status=economic.get('economics_status','unresolved_exact_epoch_metadata'),
            lifecycle_index=lifecycle_index(economic,epoch,dates) if epoch else -1))
    return pd.DataFrame(rows)

def next_boundary(SL0,low20):return max(float(SL0),float(low20))
def price_exit_reference(O,L,boundary,force_reason):
    if force_reason:return float(O),force_reason
    if O<=boundary:return float(O),'gap_stop'
    if L<=boundary:return float(boundary),'stop_boundary'
    return None,None
def close_exit_request(epoch,current_reference,next_day,expiry):
    if next_day>=expiry:return 'lifecycle_exit'
    if not current_reference:return 'observation_exit_requested'
    if current_reference!=epoch:return 'liquidity_reference_changed'
    return None
def qualified_economics(e):
    return (e.get('economics_status')=='exact_epoch_metadata_snapshot' and positive(e.get('contract_multiplier')) and
            positive(e.get('round_lot')) and float(e['round_lot']).is_integer())
def select_family_candidates(candidates,occupied,economics,*,cash):
    groups=defaultdict(list);reasons={}
    for c in candidates:
        if c['family_id'] in occupied:reasons[c['event_id']]='family_occupied';continue
        if cash and not qualified_economics(economics.get(c['reference_epoch'],{})):
            reasons[c['event_id']]='instrument_economics_unqualified';continue
        groups[c['family_id']].append(c)
    chosen=[]
    for name,values in sorted(groups.items()):
        values.sort(key=lambda c:(c.get('product_id','').endswith('_F'),c.get('product_id',''),c['reference_epoch']))
        chosen.append(values[0])
        for c in values[1:]:reasons[c['event_id']]='same_family_priority_rejected'
    return chosen,reasons

def margin_rate(econ,scenario):
    v=econ.get('vendor_margin_rate');return max(float(v) if positive(v) else 0.,SCENARIOS[scenario]['margin_floor'])
def fee_at(price,econ,scenario):
    s=SCENARIOS[scenario];return max(s['fee_min'],abs(price)*float(econ['contract_multiplier'])*s['fee_bps'])
def adverse_quote(reference,side,econ,scenario):
    if not positive(reference):raise ValueError('nonpositive fill reference')
    s=SCENARIOS[scenario];ref=Decimal(str(reference));tick=econ.get('tick_size');tickized=positive(tick)
    slip=abs(ref)*Decimal(str(s['slip_bps']))
    if tickized:slip=max(slip,Decimal(str(tick))*s['slip_ticks'])
    raw=ref+slip if side=='BUY' else ref-slip
    if tickized:
        td=Decimal(str(tick));raw=(raw/td).to_integral_value(rounding=ROUND_CEILING if side=='BUY' else ROUND_FLOOR)*td
    fill=float(raw)
    if not positive(fill):raise ValueError('nonpositive adverse research fill')
    mult=float(econ['contract_multiplier'])
    return dict(fill_price=fill,fee_per_lot=fee_at(fill,econ,scenario),slippage_per_lot=abs(fill-reference)*mult,tickized=tickized)
def unit_estimate(reference,N_u,econ,scenario):
    buy=adverse_quote(reference,'BUY',econ,scenario);sell=adverse_quote(reference,'SELL',econ,scenario)
    rtfee=2.*fee_at(reference,econ,scenario);mult=float(econ['contract_multiplier'])
    return dict(risk_per_lot=2.*N_u*mult+rtfee+buy['slippage_per_lot']+sell['slippage_per_lot'],
        fee_roundtrip_per_lot=rtfee,buffered_margin_per_lot=MARGIN_BUFFER*reference*mult*margin_rate(econ,scenario),
        buy=buy,sell=sell)

def reserve_batch(candidates,equity,existing_risk,existing_margin,economics,scenario):
    proposals=[]
    for c in candidates:
        e=economics[c['reference_epoch']];unit=unit_estimate(c['u_close'],c['N_u'],e,scenario)
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
def execution_quantity(reservation,reference,econ,scenario):
    unit=unit_estimate(reference,reservation['N_u'],econ,scenario);buy=unit['buy'];mult=float(econ['contract_multiplier']);lot=int(econ['round_lot'])
    cashunit=buy['fill_price']*mult*margin_rate(econ,scenario)+buy['fee_per_lot']
    q=min(reservation['qty_cap'],floor_lot(reservation['allocated_risk']/unit['risk_per_lot'],lot),
        floor_lot((reservation['allocated_buffered_margin']+reservation['allocated_fee'])/cashunit,lot))
    return q,dict(unit,actual_margin_plus_entry_fee_per_lot=cashunit)
def reduction_targets(positions,equity):
    risk=sum(p['qty']*p['risk_per_lot'] for p in positions)
    margin=sum(MARGIN_BUFFER*p['qty']*p['last_mark']*p['multiplier']*p['margin_rate'] for p in positions)
    factor=min(1.,TOTAL_RISK*equity/risk if risk else 1.,MARGIN_CAP*equity/margin if margin else 1.) if equity>0 else 0.
    return [floor_lot(p['qty']*factor,p['round_lot']) for p in positions]

class CashLedger:
    def __init__(self,initial):
        self.initial=float(initial);self.realized=0.;self.fees=0.;self.slippage=0.;self.positions={};self.closed=[];self.fills=[]
    def enter(self,root,qty,reference,fill,fee_per_lot,slippage_per_lot):
        if root['root_id'] in self.positions or qty<=0:raise ValueError('duplicate/nonpositive entry')
        p=dict(root,qty=int(qty),initial_qty=int(qty),entry_fill=float(fill),entry_reference=float(reference),last_mark=float(reference),
            stale=False,stale_days=0,ever_stale=False,deferred=False,force_reason=None,reduce_to=None,entry_fees=qty*fee_per_lot,exit_fees=0.,realized_gross=0.)
        self.positions[p['root_id']]=p;self.fees+=qty*fee_per_lot;self.slippage+=qty*slippage_per_lot
        self.fills.append(dict(root_id=p['root_id'],event_id=p['event_id'],family_id=p['family_id'],product_id=p['product_id'],epoch=p['epoch'],date=p['entry_date'],side='BUY',qty=int(qty),
            reference_price=float(reference),fill_price=float(fill),entry_fill=float(fill),multiplier=p['multiplier'],fee=qty*fee_per_lot,slippage=qty*slippage_per_lot,
            realized_gross=0.,reason='new_entry',budget_id=p.get('budget_id',''),margin_rate=p['margin_rate'],risk_per_lot=p['risk_per_lot'],tickized=p.get('tickized',False),future_info_scope=p.get('future_info_scope','')))
    def mark(self,root_id,mark,stale):
        p=self.positions[root_id]
        if mark is not None:p['last_mark']=float(mark)
        p['stale']=bool(stale);p['stale_days']=p['stale_days']+1 if stale else 0
        p['ever_stale']=p['ever_stale'] or bool(stale)
    def exit(self,root_id,qty,reference,fill,fee_per_lot,slippage_per_lot,day,reason,budget_id=None):
        p=self.positions[root_id]
        if qty<=0 or qty>p['qty']:raise ValueError('invalid close quantity')
        gross=qty*p['multiplier']*(fill-p['entry_fill']);fee=qty*fee_per_lot
        p['realized_gross']+=gross;p['exit_fees']+=fee;p['qty']-=qty;self.realized+=gross;self.fees+=fee;self.slippage+=qty*slippage_per_lot
        self.fills.append(dict(root_id=root_id,event_id=p['event_id'],family_id=p['family_id'],product_id=p['product_id'],epoch=p['epoch'],date=day,side='SELL',qty=int(qty),reference_price=float(reference),fill_price=float(fill),entry_fill=p['entry_fill'],
            multiplier=p['multiplier'],fee=fee,slippage=qty*slippage_per_lot,realized_gross=gross,reason=reason,budget_id=budget_id or p.get('budget_id',''),margin_rate=p['margin_rate'],risk_per_lot=p['risk_per_lot'],tickized=p.get('tickized',False),future_info_scope=p.get('future_info_scope','')))
        if p['qty']==0:
            self.closed.append(dict(p,exit_date=day,exit_reason=reason,state='closed_research_model',label_evidence='unknown_original_path' if p['ever_stale'] else 'ideal_price_model_only',net_pnl=p['realized_gross']-p['entry_fees']-p['exit_fees']))
            del self.positions[root_id]
    def totals(self):
        unrealized=sum(p['qty']*p['multiplier']*(p['last_mark']-p['entry_fill']) for p in self.positions.values())
        cash=self.initial+self.realized-self.fees;equity=cash+unrealized
        margin=sum(p['qty']*p['multiplier']*p['last_mark']*p['margin_rate'] for p in self.positions.values())
        buffered=MARGIN_BUFFER*margin;risk=sum(p['qty']*p['risk_per_lot'] for p in self.positions.values())
        notional=sum(p['qty']*p['multiplier']*p['last_mark'] for p in self.positions.values())
        stale_notional=sum(p['qty']*p['multiplier']*p['last_mark'] for p in self.positions.values() if p['stale'])
        return dict(cash=cash,cumulative_realized_gross=self.realized,cumulative_fees=self.fees,cumulative_slippage=self.slippage,unrealized=unrealized,equity=equity,
            margin=margin,buffered_margin=buffered,initial_risk=risk,open_notional=notional,stale_notional=stale_notional,stale_zero_equity=equity-stale_notional,
            unresolved_zero_equity=equity-notional,open_positions=len(self.positions),stale_positions=sum(p['stale'] for p in self.positions.values()))

def organize(signals):
    potentials={};references={}
    for k,g in signals.groupby('u_index',sort=True):
        references[int(k)]=dict(zip(g.product_id,g.reference_epoch))
        potentials[int(k)]=g.loc[g.potential.eq(1)].to_dict('records')
    return potentials,references

def run_price_chain(signals,market,dates,economics,prepared=None):
    potential,references=prepared if prepared is not None else organize(signals);active={};pending=[];episodes=[];position_days=[];decisions=[]
    first=int(signals.u_index.min());last=int(signals.u_index.max())
    for k in range(first,last+1):
        day=dates[k]
        for fam,p in list(active.items()):
            bar=market.bar(p['epoch'],k)
            if p['state']=='path_or_execution_unknown':
                if bar:p['last_mark']=bar['close']
                position_days.append(dict(root_id=p['root_id'],family_id=fam,epoch=p['epoch'],date=day,state=p['state'],last_mark=p.get('last_mark'),boundary=p.get('boundary')));continue
            if bar is None:
                p.update(state='path_or_execution_unknown',unknown_date=day,unknown_reason='missing_held_old_epoch_bar')
            else:
                reference,reason=price_exit_reference(bar['open'],bar['low'],p['boundary'],p.get('force_reason'))
                if reference is not None:
                    p.update(state='closed_known_ideal',exit_date=day,exit_reference=reference,exit_reason=reason,label_known_date=day,
                        gross_points=reference-p['entry_reference'],gross_R=(reference-p['entry_reference'])/p['R0'])
                    episodes.append(p.copy());del active[fam];continue
                p['last_mark']=bar['close']
            position_days.append(dict(root_id=p['root_id'],family_id=fam,epoch=p['epoch'],date=day,state=p['state'],last_mark=p.get('last_mark'),boundary=p.get('boundary')))
        for c in pending:
            fam=c['family_id'];epoch=c['reference_epoch'];bar=market.bar(epoch,k)
            if fam in active:raise AssertionError('price pending family already occupied')
            if k>=c['lifecycle_index']:
                decisions.append(dict(event_id=c['event_id'],date=day,state='lifecycle_entry_rejected'));continue
            p=dict(root_id='price_'+c['event_id'],event_id=c['event_id'],family_id=fam,product_id=c['product_id'],epoch=epoch,u_date=c['u_date'],entry_date=day,state='open',label_known_date=None,R0=2*c['N_u'],expiry=c['lifecycle_index'],force_reason=None)
            if bar is None:
                p.update(state='path_or_execution_unknown',unknown_date=day,unknown_reason='entry_execution_unknown',entry_reference=None,SL0=None,boundary=None,last_mark=None);active[fam]=p
                decisions.append(dict(event_id=c['event_id'],date=day,state='entry_execution_unknown'));continue
            F=bar['open'];R0=p['R0'];SL0=F-R0
            if F<=c['low20_u'] or not positive(R0) or SL0<=0:
                decisions.append(dict(event_id=c['event_id'],date=day,state='stale_breakout_cancel_at_open' if F<=c['low20_u'] else 'invalid_initial_risk_cancel'));continue
            p.update(entry_reference=F,SL0=SL0,boundary=next_boundary(SL0,c['low20_u']),last_mark=bar['close'])
            reference,reason=price_exit_reference(F,bar['low'],p['boundary'],None)
            if reference is not None:
                p.update(state='closed_known_ideal',exit_date=day,exit_reference=reference,exit_reason=reason,label_known_date=day,gross_points=reference-F,gross_R=(reference-F)/R0);episodes.append(p)
            else:active[fam]=p;position_days.append(dict(root_id=p['root_id'],family_id=fam,epoch=epoch,date=day,state='open',last_mark=p['last_mark'],boundary=p['boundary']))
            decisions.append(dict(event_id=c['event_id'],date=day,state='entered_ideal_price'))
        pending=[]
        for fam,p in active.items():
            if p['state']=='path_or_execution_unknown':continue
            indicator=market.indicator(p['epoch'],k)
            p['boundary']=next_boundary(p['SL0'],indicator['low20'])
            p['force_reason']=close_exit_request(p['epoch'],references.get(k,{}).get(p['product_id']),k+1,p['expiry'])
        chosen,rejected=select_family_candidates(potential.get(k,[]),set(active),economics,cash=False)
        for event,reason in rejected.items():decisions.append(dict(event_id=event,date=day,state=reason))
        if k<last:pending=chosen
        else:
            for c in chosen:decisions.append(dict(event_id=c['event_id'],date=day,state='intent_right_censored'))
    for p in active.values():
        if p['state']!='path_or_execution_unknown':p.update(state='open_right_censored',terminal_mark=p['last_mark'])
        episodes.append(p.copy())
    return dict(episodes=episodes,position_days=position_days,intent_decisions=decisions)

def summary_metrics(daily,ledger,insolvent):
    eq=np.asarray([r['equity'] for r in daily],dtype=float);path=np.r_[ledger.initial,eq];peaks=np.maximum.accumulate(path);dd=(path/peaks-1.)
    returns=path[1:]/path[:-1]-1. if not insolvent and np.all(path>0) else None
    sharpe=None
    if returns is not None and len(returns)>1 and returns.std(ddof=1)>0:sharpe=float(returns.mean()/returns.std(ddof=1)*math.sqrt(252))
    totals=ledger.totals();wins=sum(p['net_pnl']>0 for p in ledger.closed)
    return dict(initial_capital=ledger.initial,ending_equity=totals['equity'],total_return_pct=(totals['equity']/ledger.initial-1)*100,
        max_drawdown_pct=float(dd.min()*100),sharpe=sharpe,closed_trades=len(ledger.closed),closed_net_win_rate=wins/len(ledger.closed) if ledger.closed else None,
        total_fees=ledger.fees,total_slippage=ledger.slippage,open_positions=len(ledger.positions),stale_positions=totals['stale_positions'],open_notional=totals['open_notional'],
        unrealized=totals['unrealized'],cumulative_realized_gross=ledger.realized,ever_insolvent=bool(insolvent),stale_zero_equity=totals['stale_zero_equity'],
        all_open_long_zero_scenario_equity=totals['unresolved_zero_equity'],valuation_stress_not_universal_lower_bound=True,financial_scope='research_accrual_cash_scenario_not_broker_settlement',production_qualified=False)

def run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,initial=INITIAL,prepared=None):
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
        rows=reserve_batch(accepted,t['equity'],t['initial_risk'],t['buffered_margin'],economics,scenario)
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
            F=bar['open'];SL0=F-2*intent['N_u']
            if F<=intent['low20_u']:intent['D_state']='stale_breakout_cancel_at_open';continue
            if SL0<=0 or not positive(intent['N_u']):intent['D_state']='invalid_initial_risk_cancel';continue
            qty,unit=execution_quantity(intent,F,e,scenario);intent['D_unit_risk']=unit['risk_per_lot'];intent['D_unit_margin_plus_fee']=unit['actual_margin_plus_entry_fee_per_lot'];intent['D_qty']=qty
            if qty==0:intent['D_state']='own_open_allocation_insufficient';continue
            quote=unit['buy'];root=dict(root_id=account_id+'_'+intent['event_id'],event_id=intent['event_id'],family_id=fam,product_id=intent['product_id'],epoch=epoch,
                entry_date=day,entry_index=k,u_date=intent['u_date'],budget_id=intent['budget_id'],multiplier=float(e['contract_multiplier']),round_lot=int(e['round_lot']),
                margin_rate=margin_rate(e,scenario),risk_per_lot=unit['risk_per_lot'],SL0=SL0,boundary=next_boundary(SL0,intent['low20_u']),R0=2*intent['N_u'],expiry=intent['lifecycle_index'],
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

# The runner binds accepted sources once and retains native arrays for the price
# mother plus all eighteen independently cold-started research accounts.
def file_binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
def read_bound(item):
    raw=Path(item['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=item['sha256'] or ('bytes' in item and len(raw)!=item['bytes']):raise ValueError('input SHA/size mismatch '+item['path'])
    return raw
def write_json(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as stream:json.dump(value,stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')
def db_state(path):
    p=Path(path);s=p.stat()
    return dict(path=str(p.resolve()),bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino,wal_present=Path(str(p)+'-wal').exists(),shm_present=Path(str(p)+'-shm').exists())
def assert_db_binding(expected):
    actual=db_state(expected['path'])
    for key in ('bytes','mtime_ns','inode','wal_present','shm_present'):
        if actual[key]!=expected[key]:raise ValueError('accepted native database stat changed '+key)
    return actual
def parse_calendar(raw):
    values=np.load(io.BytesIO(raw),allow_pickle=False);result=[]
    if values.ndim!=1:raise ValueError('calendar must be one dimensional')
    for value in values:
        if values.dtype.kind in 'iu':
            s=str(int(value));result.append(s[:4]+'-'+s[4:6]+'-'+s[6:8])
        elif values.dtype.kind=='M':result.append(str(value)[:10])
        else:raise ValueError('unexpected calendar dtype')
    if result!=sorted(set(result)):raise ValueError('calendar not unique ordered')
    return result
def load_native_once(database,dates,begin,end):
    global NATIVE_QUERIES
    before=assert_db_binding(database);lookup={d:i for i,d in enumerate(dates)};series={};count=0
    uri=Path(database['path']).resolve().as_uri()+'?mode=ro&immutable=1'
    with sqlite3.connect(uri,uri=True) as db:
        NATIVE_QUERIES+=1
        cursor=db.execute('SELECT contract_epoch_id,trade_date,open,high,low,close,volume,quality_status FROM daily_bars WHERE trade_date>=? AND trade_date<=? ORDER BY contract_epoch_id,trade_date',(begin,end))
        for epoch,rows in groupby(cursor,key=lambda r:r[0]):
            day_indices=[];values=[];valids=[]
            for row in rows:
                if row[1] not in lookup:raise ValueError('native bar outside bound calendar')
                v=[float(x) if x is not None else math.nan for x in row[2:7]]
                valid=(row[7]=='accepted' and all(positive(x) for x in v) and v[2]<=min(v[0],v[3]) and v[1]>=max(v[0],v[3]))
                day_indices.append(lookup[row[1]]);values.append(v);valids.append(valid);count+=1
            if len(set(day_indices))!=len(day_indices):raise ValueError('duplicate accepted epoch/day')
            series[epoch]=EpochSeries(day_indices,values,valids)
    after=assert_db_binding(database)
    if after!=before:raise ValueError('native database changed during source read')
    return Market(series,dates),dict(native_source_queries=1,native_contract_days=count,native_epochs=len(series),database_before=before,database_after=after,
        database_sha256_inherited=database['sha256'],database_rehashed=False,execution_bar_definition='accepted OHLC finite positive, legal ordering, positive volume; invalid/missing becomes unknown/stale')
def load_protocol(path,expected_sha):
    item=file_binding(path)
    if item['sha256']!=expected_sha or expected_sha!=MACHINE_SHA:raise ValueError('frozen039 machine protocol differs')
    p=json.loads(Path(path).read_bytes())
    if p['design_document']['sha256']!=DESIGN_SHA:raise ValueError('039 document binding differs')
    for key in ('design_document','source_bindings','accepted_panel_manifest','design_review','economic_source_review'):read_bound(p[key])
    if p['scope']['independent_cash_ledgers']!=18 or p['scope']['fallback_candidates_enabled'] or p['policy']['take_profit'] is not None:raise ValueError('unexpected frozen policy closure')
    expected={'initial_capital':INITIAL,'target_new_family_risk_fraction':SINGLE_RISK,'total_initial_risk_fraction':TOTAL_RISK,'margin_reserve_fraction':MARGIN_CAP,'margin_buffer':MARGIN_BUFFER}
    if any(p['cash'][k]!=v for k,v in expected.items()):raise ValueError('cash constants differ from039')
    for name,s in SCENARIOS.items():
        for k,source in [('fee_min','fee_min_per_lot_per_side'),('fee_bps','fee_notional_fraction'),('slip_bps','slip_price_fraction'),('slip_ticks','slip_ticks'),('margin_floor','vendor_margin_floor')]:
            if p['cash'][name][source]!=s[k]:raise ValueError('scenario constants differ')
    return p,item
def load_all_inputs(protocol):
    dates=parse_calendar(read_bound(protocol['calendar']))
    if len(dates)!=5587:raise ValueError('full source calendar count differs')
    panel_raw=read_bound(protocol['panel'])
    keep=['event_id','product_id','exchange','product','u_date','reference_epoch','status','planned_execution_date','direction']
    panel=pd.read_csv(io.BytesIO(gzip.decompress(panel_raw)),dtype=str,keep_default_na=False,usecols=keep)
    if len(panel)!=399252 or panel.product_id.nunique()!=98 or panel.exchange.nunique()!=6:raise ValueError('full mother scope changed')
    scope_dates=[d for d in dates if protocol['scope']['start']<=d<=protocol['scope']['end']]
    if len(scope_dates)!=4074 or not panel.u_date.isin(scope_dates).all():raise ValueError('report scope changed')
    successors=dict(zip(dates,dates[1:]))
    if not panel.planned_execution_date.eq(panel.u_date.map(successors).fillna('')).all():raise ValueError('original exact source successor differs')
    projection=json.loads(read_bound(protocol['economic_projection']));economics=projection['instruments']
    if len(economics)!=9520 or sum(e['economics_status']=='exact_epoch_metadata_snapshot' for e in economics.values())!=9502:raise ValueError('economic scope changed')
    market,receipt=load_native_once(protocol['database'],dates,protocol['scope']['start'],protocol['scope']['end'])
    if receipt['native_contract_days']!=1552456 or receipt['native_epochs']!=9520 or set(market.series)!=set(economics):raise ValueError('native/economics identity scope differs')
    return panel,market,dates,economics,scope_dates,receipt
def write_table(path,records,empty_columns):
    if isinstance(records,pd.DataFrame):frame=records
    else:frame=pd.DataFrame(records) if records else pd.DataFrame(columns=empty_columns)
    frame.to_csv(path,index=False,compression={'method':'gzip','mtime':0})
    return len(frame)

class FiniteRawAudit:
    """Selected first cases from already-loaded native arrays; not a second source scan."""
    def __init__(self,signals,market,dates):
        self.signals=signals.set_index('event_id');self.market=market;self.dates=dates;self.cases=[];self.seen=set()
    def slice(self,epoch,start,end):
        rows=[];series=self.market.series.get(epoch)
        for k in range(max(0,start),min(len(self.dates)-1,end)+1):
            j=series.locate(k) if series is not None else None
            if j is None:rows.append(dict(date=self.dates[k],native_missing=True));continue
            v=series.values[j]
            rows.append(dict(date=self.dates[k],native_missing=False,valid_positive_volume=bool(series.valid[j]),**{n:float(x) if finite(x) else None for n,x in zip(['open','high','low','close','volume'],v)}))
        return rows
    def add(self,kind,event_id,day_index=None):
        if kind in self.seen or event_id not in self.signals.index:return
        s=self.signals.loc[event_id];u=int(s.u_index);epoch=s.reference_epoch;run=int(s.history_run)
        case=dict(kind=kind,event_id=event_id,epoch=epoch,u_date=s.u_date,N_u=float(s.N_u),low20_u=float(s.low20_u),high55_before=float(s.high55_before),
            entry_history=self.slice(epoch,u-run+1,u+1))
        if day_index is not None:case['event_neighborhood']=self.slice(epoch,day_index-21,day_index+1)
        self.cases.append(case);self.seen.add(kind)
    def export(self,path):
        raw=json.dumps(dict(schema='stage042_finite_raw_audit_v1',raw_ohlc=True,reproducibility_required=False,sql_queries=0,selection='first case of predeclared cause only; not outcome tuning',cases=self.cases),ensure_ascii=False,allow_nan=False).encode()
        with gzip.GzipFile(filename=str(path),mode='xb',mtime=0) as stream:stream.write(raw)

def artifacts(out):
    result=[]
    for p in sorted(out.rglob('*')):
        if not p.is_file() or p.name=='manifest.json':continue
        if 'excluded_raw_audit' in p.parts:continue
        role='qualification_evidence' if p.name in ('actual_terminal.json','source_read_receipt.json') else 'feature_contract' if p.name in ('protocol.json','input_bindings.json') else 'decision_asset'
        result.append(dict(file_binding(p),role=role,reproducibility_required=True,raw_ohlc=False))
    return result
def execute(args):
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic();out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('refuse overwrite/automatic rerun '+str(out))
    out.mkdir(parents=True,exist_ok=False);started_cash=0;computed_cash=0;completed_cash=0;status='failed';error=None;summaries=[]
    try:
        protocol,protocol_binding=load_protocol(args.protocol,args.protocol_sha256)
        write_json(out/'protocol.json',protocol);write_json(out/'input_bindings.json',{k:protocol[k] for k in ['design_document','source_bindings','accepted_panel_manifest','panel','database','calendar','economic_projection','design_review','economic_source_review']})
        panel,market,dates,economics,scope_dates,source_receipt=load_all_inputs(protocol)
        write_json(out/'source_read_receipt.json',source_receipt)
        print(json.dumps(dict(phase='native_loaded_once',native_contract_days=source_receipt['native_contract_days'],native_epochs=source_receipt['native_epochs'],elapsed_seconds=time.monotonic()-clock)),flush=True)
        signals=build_signals(panel,market,dates,economics);prepared=organize(signals)
        write_table(out/'signals_all.csv.gz',signals,[])
        write_json(out/'signal_summary.json',dict(mother_rows=len(signals),products=int(signals.product_id.nunique()),ready55=int(signals.policy_ready55.sum()),potential_intents=int(signals.potential.sum()),states=dict(Counter(signals.signal_state)),economics_status=dict(Counter(signals.economics_status)),
            policy='close55_confirm_next_source_open_2N_stop_causal20low_no_PT',no_AI=True))
        print(json.dumps(dict(phase='all_mother_signals_complete',rows=len(signals),ready55=int(signals.policy_ready55.sum()),potentials=int(signals.potential.sum()),elapsed_seconds=time.monotonic()-clock)),flush=True)
        audit=FiniteRawAudit(signals,market,dates)
        for j,s in enumerate(signals.loc[signals.potential.eq(1)].sort_values(['u_index','event_id']).head(3).itertuples()):audit.add('first_signal_'+str(j),s.event_id)
        price=run_price_chain(signals,market,dates,economics,prepared)
        price_dir=out/'price_reference';price_dir.mkdir()
        write_table(price_dir/'episodes.csv.gz',price['episodes'],['root_id','event_id','state','entry_date','exit_date','label_known_date'])
        write_table(price_dir/'position_days.csv.gz',price['position_days'],['root_id','family_id','epoch','date','state','last_mark','boundary'])
        write_table(price_dir/'intent_decisions.csv.gz',price['intent_decisions'],['event_id','date','state'])
        for p in price['episodes']:
            if p.get('exit_reason') in ('gap_stop','liquidity_reference_changed','lifecycle_exit'):audit.add('price_'+p['exit_reason'],p['event_id'],dates.index(p['exit_date']))
            if p['state']=='path_or_execution_unknown':audit.add('price_unknown',p['event_id'],dates.index(p['unknown_date']))
        write_json(price_dir/'summary.json',dict(episodes=len(price['episodes']),states=dict(Counter(p['state'] for p in price['episodes'])),exit_reasons=dict(Counter(p.get('exit_reason','unresolved_or_open') for p in price['episodes'])),financial_runs=0,price_R_not_account_cash=True))
        del price
        for scenario in protocol['scope']['cash_scenarios']:
            for window in protocol['scope']['cash_windows']:
                start=int(np.searchsorted(dates,window['start']));end=int(np.searchsorted(dates,window['end'],side='right'))-1
                account_id=scenario+'__'+window['id'];started_cash+=1
                book=run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,INITIAL,prepared);computed_cash+=1
                directory=out/'cash'/account_id;directory.mkdir(parents=True)
                for name,columns in [('fills',['account_id','window_id','scenario','root_id','epoch','date','side','qty','reference_price','fill_price','multiplier','fee','slippage']),
                    ('daily',['account_id','window_id','scenario','date','cash','equity','unrealized']),('budgets',['account_id','window_id','scenario','budget_id','event_id','u_date','execution_date','qty_cap','D_qty','D_state']),
                    ('position_days',['account_id','window_id','scenario','root_id','date','qty','mark','entry_fill','multiplier','margin_rate','risk_per_lot']),
                    ('closed_episodes',['account_id','window_id','scenario','root_id','entry_date','exit_date','net_pnl']),('open_episodes',['account_id','window_id','scenario','root_id','state','qty','last_mark'])]:
                    for row in book[name]:row.update(account_id=account_id,window_id=window['id'],scenario=scenario)
                    write_table(directory/(name+'.csv.gz'),book[name],columns)
                summary=dict(book['summary'],account_id=account_id,scenario=scenario,window_id=window['id'],requested_start=window['start'],requested_end=window['end'],source_start=dates[start],source_end=dates[end],partial=window.get('partial',False),
                    source_dates=end-start+1,mark='native_close_research_not_settlement',fee_margin_specs='fixed_scenario_on_static_vendor_snapshot_not_historical_broker_parameters')
                write_json(directory/'summary.json',summary);summaries.append(summary);completed_cash+=1
                for f in book['fills']:
                    if f['side']=='SELL' and f['reason'] in ('research_deferred_liquidation','risk_margin_joint_reduction','gap_stop','liquidity_reference_changed','lifecycle_exit'):
                        audit.add('cash_'+f['reason'],f['event_id'],dates.index(f['date']))
                print(json.dumps(dict(phase='cash_window_complete',account_id=account_id,completed_cash_accounts=completed_cash,ending_equity=summary['ending_equity'],closed_trades=summary['closed_trades'],open_positions=summary['open_positions'],elapsed_seconds=time.monotonic()-clock)),flush=True)
                del book
        if completed_cash!=18:raise AssertionError('expected eighteen independent cash accounts')
        write_json(out/'cash_summary.json',dict(schema='stage042_eighteen_research_cash_summaries_v1',accounts=summaries,financial_scope='research_accrual_ledger; not broker exactness',parameters_searched=False,no_AI=True,production_qualified=False))
        pd.DataFrame(summaries).to_csv(out/'cash_summary.csv',index=False)
        (out/'excluded_raw_audit').mkdir();audit.export(out/'excluded_raw_audit/native_case_slices.json.gz')
        assert_db_binding(protocol['database']);status='completed'
    except BaseException as exc:error=f'{type(exc).__name__}: {exc}';raise
    finally:
        write_json(out/'actual_terminal.json',dict(status=status,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,exit_code=0 if status=='completed' else 1,error=error,
            actual_model_fit_calls=0,started_research_cash_accounts=started_cash,computed_research_cash_accounts=computed_cash,completed_research_cash_accounts=completed_cash,native_source_queries=NATIVE_QUERIES,network_calls=0,fixture=False,python=sys.executable,numpy=np.__version__,pandas=pd.__version__,source=file_binding(__file__)))
    write_json(out/'manifest.json',dict(schema='stage042_cross_session_reference_and_research_cash_v1',status=status,source=file_binding(__file__),tests=file_binding(Path(__file__).with_name('test_stage042_cross_session_experiment.py')),
        protocol=protocol_binding,source_read_receipt=file_binding(out/'source_read_receipt.json'),artifacts=artifacts(out),excluded_raw_audit=dict(file_binding(out/'excluded_raw_audit/native_case_slices.json.gz'),raw_ohlc=True,reproducibility_required=False,role='external_ignored_raw_audit'),
        actual_model_fit_calls=0,completed_research_cash_accounts=completed_cash,native_source_queries=1,research_cash_scenarios_computed=True,broker_historical_truth_qualified=False,production_qualified=False,goal_complete=False))
    return dict(status=status,output=str(out),completed_research_cash_accounts=completed_cash,native_source_queries=1,model_fits=0)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',required=True);p.add_argument('--protocol-sha256',required=True);p.add_argument('--output',required=True)
    print(json.dumps(execute(p.parse_args()),ensure_ascii=False))
if __name__=='__main__':main()
