"""Pure dual-bucket accounting. Internal reserve transfers never create PnL."""
import math
import numpy as np
import pandas as pd

TRADING_INITIAL=150000.
RESERVE_INITIAL=150000.
TOTAL_INITIAL=300000.


def require(value,label):
    if not value:raise ValueError('stage009_accounting:'+label)


def close(a,b):
    return math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6)


def bucket_curve(raw,events,arm):
    require(arm in {'A','C'},'unknown_arm')
    d=raw.copy();d['date']=d.date.astype(str).str[:10]
    require(not d.empty and not d.date.duplicated().any() and d.date.is_monotonic_increasing,'ordered_nonempty_daily')
    for key in ['account_equity','net_pnl','slippage','commission','trade_count']:
        require(key in d and np.isfinite(d[key].to_numpy(float)).all(),'finite_'+key)
    require(np.allclose(d.account_equity,TRADING_INITIAL+d.net_pnl.cumsum(),rtol=1e-10,atol=1e-6),'raw_equity_PnL_bridge')
    require(close(d.account_equity.iloc[0],TRADING_INITIAL) and close(d.net_pnl.iloc[0],0),'fresh_trading_start')
    day_raw=d.set_index('date').account_equity.to_dict()
    ids=set();candidates=set();remaining=RESERVE_INITIAL;cum=0.;previous_date='';transfers={}
    for e in events:
        date=str(e['date'])[:10];amount=float(e['transfer_amount']);before=float(e['trading_equity_before'])
        require(date in set(d.date) and date>=previous_date,'event_date_order_or_scope');previous_date=date
        # Frozen Stage502/827 queue drains all same-day fills before on_bars;
        # no same-day fill can follow a signal. Runner independently certifies
        # this phase. A self-consistent fabricated funding event is not enough.
        require(close(e['raw_account_equity'],day_raw[date]),'event_raw_day_anchor')
        require(str(e['event_id']) not in ids and e['candidate_key'] not in candidates,'duplicate_transfer')
        ids.add(str(e['event_id']));candidates.add(e['candidate_key'])
        require(e['phase']=='before_parent_sizing' and e['entry_context'] in {'flat_entry','reverse_entry'},'invalid_transfer_context')
        expected_direction={'long_case1a':'long','long_case2':'long','short_case1a':'short'}.get(e['signal'])
        require(expected_direction is not None and e['direction']==expected_direction,'invalid_native_signal')
        require(e['weekly_stop_valid'] is True,'invalid_weekly_stop')
        if arm=='C' and e['direction']=='short':
            require(e['range_checked'] is True and e['range_would_block'] is False,'C_blocked_short_cannot_fund')
        require(close(e['reserve_before'],remaining),'reserve_event_chain')
        require(before<TRADING_INITIAL and math.isfinite(before) and amount>0 and close(amount,min(TRADING_INITIAL-before,remaining)),'topup_exact_deficit_bounded_reserve')
        require(close(e['trading_equity_after'],before+amount) and close(e['reserve_after'],remaining-amount),'internal_transfer_bridge')
        require(close(e['raw_account_equity'],before-cum) and close(e['total_account_equity'],before+remaining),'event_total_conservation')
        cum+=amount;remaining-=amount
        require(close(e['cumulative_transfer'],cum) and remaining>=-1e-6,'event_cumulative_and_nonnegative_reserve')
        transfers[date]=transfers.get(date,0.)+amount
    d['transfer_amount']=d.date.map(transfers).fillna(0.)
    d['raw_account_equity']=d.account_equity
    d['cumulative_transfer']=d.transfer_amount.cumsum()
    d['trading_account_equity']=d.raw_account_equity+d.cumulative_transfer
    d['reserve_balance']=RESERVE_INITIAL-d.cumulative_transfer
    d['total_account_equity']=d.trading_account_equity+d.reserve_balance
    require(np.allclose(d.total_account_equity,TOTAL_INITIAL+d.net_pnl.cumsum(),rtol=1e-10,atol=1e-6),'total_wealth_PnL_bridge')
    require((d.reserve_balance>=-1e-6).all() and (d.reserve_balance.diff().fillna(0)<=1e-6).all(),'reserve_only_decreases')
    d['nav']=d.total_account_equity/TOTAL_INITIAL
    d['drawdown_pct']=(d.total_account_equity/np.maximum.accumulate(np.r_[TOTAL_INITIAL,d.total_account_equity])[1:]-1)*100
    return d


def curve_metrics(d):
    e=d.total_account_equity.to_numpy(float);previous=np.r_[TOTAL_INITIAL,e[:-1]]
    require(len(e)>0 and np.isfinite(e).all(),'finite_total_curve')
    returns=np.divide(e-previous,previous,out=np.full_like(e,np.nan),where=previous!=0)
    finite_returns=np.isfinite(returns).all();std=float(np.std(returns,ddof=1)) if len(returns)>1 and finite_returns else 0.
    sharpe=float(np.mean(returns)/std*np.sqrt(252)) if std>0 and finite_returns else 0.
    return dict(initial_capital=TOTAL_INITIAL,end_equity=float(e[-1]),net_pnl=float(d.net_pnl.sum()),
        total_return_pct=float((e[-1]/TOTAL_INITIAL-1)*100),max_dd_pct=float(((e/np.maximum.accumulate(np.r_[TOTAL_INITIAL,e])[1:]-1)*100).min()),
        sharpe=sharpe,sharpe_returns_defined=bool(finite_returns),total_slippage=float(d.slippage.sum()),
        total_commission=float(d.commission.sum()),modeled_fill_count=int(d.trade_count.sum()),
        actual_start=str(d.date.iloc[0])[:10],actual_end=str(d.date.iloc[-1])[:10],trading_days=len(d),
        nonpositive_total_equity_days=int((e<=0).sum()),nonpositive_trading_equity_days=int(d.trading_account_equity.le(0).sum()),
        trading_end_equity=float(d.trading_account_equity.iloc[-1]),reserve_end_balance=float(d.reserve_balance.iloc[-1]),
        total_transferred=float(d.cumulative_transfer.iloc[-1]),transfer_event_days=int(d.transfer_amount.gt(0).sum()))


def compare_pair(control,candidate,start,end):
    require(control['initial_capital']==candidate['initial_capital']==TOTAL_INITIAL,'same_total_capital_required')
    comparisons={}
    for key in ['end_equity','max_dd_pct','sharpe']:
        a,b=control[key],candidate[key]
        require(math.isfinite(a) and math.isfinite(b),'finite_paired_metric')
        comparisons[key]=0 if close(a,b) else (1 if b>a else -1)
    gates=dict(equity_gate=comparisons['end_equity']>0,dd_gate=comparisons['max_dd_pct']>=0,sharpe_gate=comparisons['sharpe']>=0)
    mature=pd.Timestamp(end)>=pd.Timestamp(start)+pd.DateOffset(years=1)
    return dict(start=start,end=end,vote_eligible=bool(mature),observation_only=not mature,
        **gates,three_gate_pass=all(gates.values()),return_comparison=comparisons['end_equity'],
        dd_comparison=comparisons['max_dd_pct'],sharpe_comparison=comparisons['sharpe'])
