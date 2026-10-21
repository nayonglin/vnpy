"""Independent saved-fill cash arithmetic adapted from Stage043; no author imports."""
SCENARIOS={'base':dict(fee_min=2.,fee_bps=.0001,slip_bps=.0001,slip_ticks=1,margin_floor=.20),
           'stress':dict(fee_min=6.,fee_bps=.0003,slip_bps=.0003,slip_ticks=3,margin_floor=.40)}
ERRORS={}

import argparse

from datetime import datetime

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

import gzip

import hashlib

import io

import json

import math

from pathlib import Path

import time

import numpy as np

import pandas as pd

from cash_review_core import replay_fill_cash,fill_days_to_daily,verify_saved_quantities,position_totals,summary_metrics

def sha(raw):return hashlib.sha256(raw).hexdigest()

def bound(item):
    raw=Path(item['path']).read_bytes();assert sha(raw)==item['sha256'],item['path']
    if 'bytes' in item:assert len(raw)==item['bytes'],item['path']
    return raw

def csv(path):
    frame=pd.read_csv(path,dtype=str,keep_default_na=False)
    if frame.empty:
        required={
          'fills.csv.gz':['root_id','event_id','family_id','product_id','epoch','date','side','qty','reference_price','fill_price','entry_fill','multiplier','fee','slippage','realized_gross','margin_rate','risk_per_lot','budget_id'],
          'position_days.csv.gz':['root_id','date','family_id','epoch','qty','entry_fill','entry_reference','mark','multiplier','margin_rate','risk_per_lot','SL0','boundary_next','unrealized','notional','stale_days','mark_state'],
          'closed_episodes.csv.gz':['root_id','net_pnl','exit_date','entry_date'],
          'open_episodes.csv.gz':['root_id','qty','state']}
        for c in required.get(Path(path).name,[]):
            if c not in frame:frame[c]=pd.Series(dtype=str)
    return frame

def number(series):return np.asarray([float(v) if str(v)!='' else np.nan for v in series],dtype=float)

def numeric(frame,columns):
    for c in columns:
        if c in frame:frame[c]=number(frame[c])
    return frame

def compare(actual,expected,key,atol=5e-6,rtol=2e-11):
    a=np.asarray(actual,dtype=float);b=np.asarray(expected,dtype=float);assert a.shape==b.shape,(key,a.shape,b.shape)
    assert np.array_equal(np.isnan(a),np.isnan(b)),key
    finite=np.isfinite(a)&np.isfinite(b);error=np.abs(a[finite]-b[finite])
    ERRORS[key]=max(ERRORS.get(key,0.),float(error.max()) if len(error) else 0.)
    assert np.all(error<=atol+rtol*np.abs(b[finite])),(key,ERRORS[key])

def positive(x):return x is not None and np.isfinite(x) and x>0

def econ_rate(e,s):return max(float(e.get('vendor_margin_rate') or 0.),SCENARIOS[s]['margin_floor'])

def fee(price,e,s):return max(SCENARIOS[s]['fee_min'],abs(price)*float(e['contract_multiplier'])*SCENARIOS[s]['fee_bps'])

def floorlot(q,lot):return math.floor(max(0.,q)/lot)*int(lot)

def quote(reference,side,e,s):
    rule=SCENARIOS[s];p=Decimal(str(reference));tick=e.get('tick_size')
    tick=float(tick) if positive(tick) else None
    delta=abs(p)*Decimal(str(rule['slip_bps']))
    if tick:delta=max(delta,Decimal(str(tick))*rule['slip_ticks'])
    price=p+delta if side=='BUY' else p-delta
    if tick:
        unit=Decimal(str(tick));rounding=ROUND_CEILING if side=='BUY' else ROUND_FLOOR
        price=(price/unit).to_integral_value(rounding=rounding)*unit
    value=float(price);assert value>0
    return value,fee(value,e,s),abs(value-reference)*float(e['contract_multiplier'])

def estimate(reference,N,e,s):
    buy=quote(reference,'BUY',e,s);sell=quote(reference,'SELL',e,s);mult=float(e['contract_multiplier'])
    r=2*N*mult+2*fee(reference,e,s)+buy[2]+sell[2]
    return r,1.10*reference*mult*econ_rate(e,s),2*fee(reference,e,s),buy

def review_budgets(budgets,daily,signals,economics,scenario,calendar,start):
    if budgets.empty:return {'rows':0,'new_allocations':0,'existing_reductions':0}
    assert not budgets.budget_id.duplicated().any()
    fields=['u_equity','existing_risk','existing_buffered_margin','unit_risk_u','unit_margin_u','unit_fee_reserve_u',
            'target_qty_unscaled','joint_scale','target_qty_prefloor','qty_cap','round_lot','allocated_risk',
            'allocated_buffered_margin','allocated_fee','D_qty','D_unit_risk','D_unit_margin_plus_fee','existing_qty','target_existing_qty']
    numeric(budgets,fields)
    for name in ['budget_kind','D_state','budget_state']:
        if name not in budgets:budgets[name]=''
    date_index={d:i for i,d in enumerate(calendar)};day=daily.set_index('date');new_count=0;reduce_count=0
    for u,group in budgets.groupby('u_date',sort=False):
        assert group.execution_date.eq(calendar[date_index[u]+1]).all()
        if u in day.index:
            eq=float(day.loc[u,'equity']);risk=float(day.loc[u,'initial_risk']);margin=float(day.loc[u,'buffered_margin'])
        else:
            assert date_index[u]==start-1;eq=1_000_000.;risk=0.;margin=0.
        compare(group.u_equity.to_numpy(),np.full(len(group),eq),'u_equity')
        compare(group.existing_risk.to_numpy(),np.full(len(group),risk),'u_existing_risk')
        compare(group.existing_buffered_margin.to_numpy(),np.full(len(group),margin),'u_existing_margin')
        new=group.loc[group.budget_kind.eq('new_entry')]
        expected=[]
        for row in new.to_dict('records'):
            signal=signals.loc[row['event_id']];assert signal.potential==1
            assert row['reference_epoch']==signal.reference_epoch and row['u_date']==signal.u_date
            e=economics[row['reference_epoch']];assert e['economics_status']=='exact_epoch_metadata_snapshot'
            r,m,f,buy=estimate(float(signal.u_close),float(signal.N_u),e,scenario)
            real=max(0.,.0025*eq/r) if eq>0 else 0.
            expected.append((row,r,m,f,real,e))
            compare([row['unit_risk_u'],row['unit_margin_u'],row['unit_fee_reserve_u'],row['target_qty_unscaled']],
                    [r,m,f,real],'u_unit_allocations')
        totalrisk=sum(r*real for _,r,m,f,real,e in expected);totalmargin=sum(m*real for _,r,m,f,real,e in expected)
        scale=min(1.,max(0.,.02*eq-risk)/totalrisk if totalrisk else 1.,max(0.,.25*eq-margin)/totalmargin if totalmargin else 1.) if eq>0 else 0.
        for row,r,m,f,real,e in expected:
            target=real*scale;lot=int(e['round_lot']);new_count+=1
            compare([row['joint_scale'],row['target_qty_prefloor'],row['allocated_risk'],row['allocated_buffered_margin'],row['allocated_fee']],
                    [scale,target,target*r,target*m,target*f],'prefloor_allocations')
            assert row['qty_cap']==floorlot(row['target_qty_prefloor'],lot)
            assert row['D_qty']<=row['qty_cap'] and row['D_qty']>=0
        reductions=group.loc[group.budget_kind.eq('existing_position_reduction')]
        if len(reductions):
            factor=min(1.,.02*eq/risk if risk else 1.,.25*eq/margin if margin else 1.) if eq>0 else 0.
            for row in reductions.to_dict('records'):
                e=economics[row['reference_epoch']];target=floorlot(row['existing_qty']*factor,int(e['round_lot']))
                compare(row['joint_scale'],factor,'reduction_scale')
                assert row['target_existing_qty']==target and row['qty_cap']==row['existing_qty']-target
                reduce_count+=1
    return {'rows':len(budgets),'new_allocations':new_count,'existing_reductions':reduce_count}

def review_account(directory,scenario,window,protocol,signals,economics,calendar):
    dates=[d for d in calendar if window['start']<=d<=window['end']]
    daily=csv(directory/'daily.csv.gz')
    numeric(daily,[c for c in daily if c not in ['account_id','window_id','scenario','arm','date','ever_insolvent']])
    assert daily.date.tolist()==dates and not daily.date.duplicated().any()
    fills=csv(directory/'fills.csv.gz').rename(columns={'root_id':'root','fill_price':'fill','entry_fill':'entryfill','risk_per_lot':'risk_perlot'})
    numeric(fills,['qty','reference_price','fill','entryfill','multiplier','fee','slippage','realized_gross','margin_rate','risk_perlot'])
    positions=csv(directory/'position_days.csv.gz').rename(columns={'root_id':'root','entry_fill':'entryfill','risk_per_lot':'risk_perlot'})
    numeric(positions,['qty','entryfill','entry_reference','mark','multiplier','margin_rate','risk_perlot','SL0','boundary_next','unrealized','notional','stale_days'])
    if 'mark_state' not in positions:positions['mark_state']=pd.Series(dtype=str)
    budgets=csv(directory/'budgets.csv.gz');summary=json.loads((directory/'summary.json').read_text())
    fill_daily,roots,remaining=replay_fill_cash(fills);expected_cash=fill_days_to_daily(fill_daily,dates)
    quantity_checks=verify_saved_quantities(fills,positions,dates,roots)
    for observed,expected in [('cash','cash'),('cumulative_realized_gross','cum_realized_gross'),('cumulative_fees','cum_fees'),('cumulative_slippage','cum_slippage')]:
        compare(daily[observed],expected_cash[expected],'daily_'+observed)
    valuation=position_totals(positions,dates)
    for observed,expected in [('unrealized','unrealized'),('margin','margin'),('buffered_margin','buffered_reserve'),('initial_risk','initial_risk')]:
        compare(daily[observed],valuation[expected],'daily_'+observed)
    equity=expected_cash.cash.to_numpy()+valuation.unrealized.to_numpy()
    compare(daily.equity,equity,'daily_equity')
    compare(daily.stale_zero_equity,equity+valuation.stale_zero_adjustment.to_numpy(),'daily_stale_zero')
    if positions.empty:
        notionals=np.zeros(len(dates));stale=np.zeros(len(dates));counts=np.zeros(len(dates));stalecount=np.zeros(len(dates))
    else:
        notionals=(positions.qty*positions.multiplier*positions.mark).groupby(positions.date).sum().reindex(dates).fillna(0.).to_numpy()
        stale=(positions.qty*positions.multiplier*positions.mark*positions.mark_state.eq('stale')).groupby(positions.date).sum().reindex(dates).fillna(0.).to_numpy()
        counts=positions.groupby('date').size().reindex(dates).fillna(0.).to_numpy()
        stalecount=positions.loc[positions.mark_state.eq('stale')].groupby('date').size().reindex(dates).fillna(0.).to_numpy()
    compare(daily.open_notional,notionals,'daily_notional');compare(daily.stale_notional,stale,'daily_stale_notional')
    compare(daily.unresolved_zero_equity,equity-notionals,'daily_all_open_zero')
    compare(daily.open_positions,counts,'daily_open_count');compare(daily.stale_positions,stalecount,'daily_stale_count')
    assert np.array_equal(daily.ever_insolvent.eq('True').to_numpy(),np.maximum.accumulate(equity<=0))
    checked_budget=review_budgets(budgets,daily,signals,economics,scenario,calendar,calendar.index(dates[0]))
    lookup=budgets.set_index('budget_id') if len(budgets) else pd.DataFrame()
    if len(positions):
        assert not positions.duplicated(['date','family_id']).any()
        compare(positions.unrealized,positions.qty*positions.multiplier*(positions.mark-positions.entryfill),'position_unrealized')
        compare(positions.notional,positions.qty*positions.multiplier*positions.mark,'position_notional')
        for epoch,rows in positions.groupby('epoch',sort=False):
            e=economics[epoch];compare(rows.multiplier,np.full(len(rows),e['contract_multiplier']),'position_multiplier')
            compare(rows.margin_rate,np.full(len(rows),econ_rate(e,scenario)),'position_margin_rate')
    for row in fills.to_dict('records'):
        e=economics[row['epoch']];assert e['economics_status']=='exact_epoch_metadata_snapshot'
        assert row['multiplier']==e['contract_multiplier'] and row['qty']%int(e['round_lot'])==0
        price,unitfee,unitslip=quote(row['reference_price'],row['side'],e,scenario)
        compare([row['fill'],row['fee'],row['slippage']],[price,row['qty']*unitfee,row['qty']*unitslip],'all_fill_prices_fees_slippage')
        signal=signals.loc[row['event_id']];assert row['epoch']==signal.reference_epoch
        assert row['family_id']==signal.family_id and row['product_id']==signal.product_id
        assert row['date']>=signal.planned_execution_date
        if row['side']=='BUY':
            assert row['date']==signal.planned_execution_date and row['budget_id'] in lookup.index
            b=lookup.loc[row['budget_id']];assert b['budget_kind']=='new_entry' and b['u_date']==signal.u_date
            r,m,f,buy=estimate(row['reference_price'],signal.N_u,e,scenario)
            cashunit=buy[0]*e['contract_multiplier']*econ_rate(e,scenario)+buy[1]
            cap=min(float(b['qty_cap']),floorlot(float(b['allocated_risk'])/r,int(e['round_lot'])),
                    floorlot((float(b['allocated_buffered_margin'])+float(b['allocated_fee']))/cashunit,int(e['round_lot'])))
            assert row['qty']==cap and float(b['D_qty'])==cap
            compare(row['risk_perlot'],r,'entry_risk_perlot')
            assert b['D_state'] in ['entered','entered_reduced_own_allocation']
    # Pending reserves are the frozen prefloor allocations of positive-cap intents only.
    if len(budgets) and 'budget_kind' in budgets:
        new=budgets.loc[budgets.budget_kind.eq('new_entry')&budgets.qty_cap.gt(0)]
    else:new=pd.DataFrame(columns=['u_date','allocated_risk','allocated_buffered_margin','allocated_fee'])
    for field,allocation in [('new_order_risk_reserve','allocated_risk'),('new_order_margin_reserve','allocated_buffered_margin'),('new_order_fee_reserve','allocated_fee')]:
        sums=new.groupby('u_date')[allocation].sum().reindex(dates).fillna(0.) if len(new) else np.zeros(len(dates))
        compare(daily[field],sums,'daily_'+field)
    compare(daily.new_order_reserve,daily.new_order_margin_reserve+daily.new_order_fee_reserve,'daily_new_reserve')
    compare(daily.total_reserve,daily.buffered_margin+daily.new_order_reserve,'daily_total_reserve')
    closed=csv(directory/'closed_episodes.csv.gz');opens=csv(directory/'open_episodes.csv.gz')
    assert set(closed.root_id)=={k for k,v in roots.items() if v['closed']}
    assert set(opens.root_id)==set(remaining)
    for row in closed.to_dict('records'):
        r=roots[row['root_id']];compare(float(row['net_pnl']),r['net'],'closed_root_net')
        assert row['exit_date']==r['exit_date'] and row['entry_date']==r['entry_date']
    for row in opens.to_dict('records'):
        assert float(row['qty'])==remaining[row['root_id']]['qty']
        assert row['state'] in ['stale_open_unresolved','open_right_censored']
    insolvent=bool(np.any(equity<=0));computed=summary_metrics(equity,roots,insolvent=insolvent)
    mapping={'ending_equity':'ending_equity','closed_trades':'closed_trades','open_positions':'open_roots','closed_net_win_rate':'win_rate','sharpe':'sharpe'}
    for actual,expected in mapping.items():
        if computed[expected] is None:assert summary[actual] is None
        else:compare(summary[actual],computed[expected],'summary_'+actual)
    compare(summary['total_return_pct'],computed['total_return']*100,'summary_return')
    compare(summary['max_drawdown_pct'],computed['max_drawdown']*100,'summary_drawdown')
    compare(summary['total_fees'],expected_cash.cum_fees.iloc[-1],'summary_fee')
    compare(summary['total_slippage'],expected_cash.cum_slippage.iloc[-1],'summary_slippage')
    compare(summary['unrealized'],valuation.unrealized.iloc[-1],'summary_unrealized')
    compare(summary['cumulative_realized_gross'],expected_cash.cum_realized_gross.iloc[-1],'summary_realized')
    compare(summary['stale_zero_equity'],equity[-1]-stale[-1],'summary_stale_zero')
    compare(summary['all_open_long_zero_scenario_equity'],equity[-1]-notionals[-1],'summary_open_zero')
    assert summary['ever_insolvent']==insolvent and summary['source_dates']==len(dates)
    assert summary['source_start']==dates[0] and summary['source_end']==dates[-1]
    assert summary['initial_capital']==1_000_000. and summary.get('partial',False)==window.get('partial',False)
    return {'account_id':directory.name,'fills_checked':len(fills),'daily_rows_checked':len(daily),
            'position_rows_checked':quantity_checks,'budgets_checked':checked_budget,'closed_roots_checked':len(closed),
            'open_roots_checked':len(opens),'metrics':computed,'summary':summary}
