"""Stage009 isolated internal reserve; no engine, broker or external cash flow.

Wrap the complete Stage008 strategy class. Only an admitted native new-entry
candidate can fund its trading account, immediately before the unchanged parent
sizing chain. The original next-open engine retains its execution limitations.
"""
import math
import pandas as pd

TRADING_INITIAL=150000.0
RESERVE_INITIAL=50000.0
NEW_ENTRY_CONTEXTS=frozenset({'flat_entry','reverse_entry'})
NATIVE_SIGNALS={'long':frozenset({'long_case1a','long_case2'}),
                'short':frozenset({'short_case1a'})}

def _day(value):
 stamp=pd.Timestamp(value)
 if pd.isna(stamp):raise ValueError('reserve_missing_date')
 if stamp.tzinfo:stamp=stamp.tz_convert('Asia/Shanghai').tz_localize(None)
 return stamp.strftime('%Y-%m-%d')

def _finite(value,name):
 value=float(value)
 if not math.isfinite(value):raise ValueError('reserve_nonfinite_'+name)
 return value

def reserve_strategy_class(base,range_history,range_enabled,account_start,enabled=True):
 """Return an outer wrapper for the frozen, complete Stage008 final class.

 Public ledgers are lists of JSON-safe dicts. Snapshots are ordered by sequence;
 select the last sequence for each date for a day-end account bridge. Inherited
 post-on_bars fills can follow after_on_bars_settlement and have their own
 after_update_trade snapshots. No snapshot or probe can transfer reserve cash.
 """
 start=_day(account_start)
 class ReserveTopupStrategy(base):
  research_reserve_enabled=bool(enabled)
  research_reserve_initial=RESERVE_INITIAL
  research_reserve_floor=TRADING_INITIAL
  research_reserve_account_start=start
  def __init__(self,*args,**kwargs):
   super().__init__(*args,**kwargs)
   if float(self.base_capital)!=TRADING_INITIAL:raise ValueError('reserve_trading_initial_must_be150000')
   self.reserve_balance=RESERVE_INITIAL
   self.reserve_cumulative_transfer=0.0
   self.reserve_transfer_events=[]
   self.reserve_signal_checks=[]
   self.reserve_daily_snapshots=[]
   self._reserve_seen_candidates=set()

  def _reserve_marked_equity(self):
   bars=getattr(self.strategy_engine,'bars',{})
   # The original account estimator includes every inherited holding, current
   # daily marks, and fills/costs already applied to settled_balance.
   value=self._estimate_equity(bars) if bars else self.estimated_equity
   return _finite(value,'trading_equity')

  def _reserve_refresh_funding_caches(self):
   # These methods update current ratios only. Never call _refresh_risk_state:
   # it also advances volatility/overheat time-series state and daily records.
   self._refresh_portfolio_drawdown_state()
   self._refresh_portfolio_margin_deleverage_state()
   self._refresh_risk_cluster_heat_pressure_snapshot()
   self.risk_cluster_heat_gate_weight=self._current_min_risk_cluster_heat_gate_weight()
   self.current_risk_per_trade=self._risk_amount_from_ratio(
    self.risk_ratio_of_total_assets,self._limited_available_balance())

  def _sizing_equity_snapshot(self):
   result=super()._sizing_equity_snapshot()
   if _finite(self.estimated_equity,'estimated_equity')<=0:
    # Parent uses ``estimated_equity or base_capital``. A zero trading bucket
    # must not regain purchasing power through that fallback.
    result=dict(result,sizing_equity=0.0,effective_sizing_equity_cap=0.0,
     reserve_nonpositive_sizing_equity_guard=True)
   return result

  def _calculate_entry_sizing(self,vt_symbol,direction,bar,history,signal_data,
    risk_mode_override=None,entry_context='flat_entry',apply_env_gate=True,
    active_positions_before=None,correlation_snapshot=None):
   date=_day(bar.datetime);signal=str(signal_data.get('signal',''))
   before=self._reserve_marked_equity();self.estimated_equity=before
   reserve_before=_finite(self.reserve_balance,'balance')
   if not 0<=reserve_before<=RESERVE_INITIAL:raise ValueError('reserve_balance_out_of_bounds')
   key='|'.join([date,str(vt_symbol),str(direction),signal,str(entry_context)])
   check=dict(date=date,vt_symbol=str(vt_symbol),direction=str(direction),signal=signal,
    entry_context=str(entry_context),candidate_key=key,phase='before_parent_sizing',
    trading_equity_before=before,trading_equity_after=before,
    reserve_before=reserve_before,reserve_after=reserve_before,transfer_amount=0.0,
    cumulative_transfer=self.reserve_cumulative_transfer,
    raw_account_equity=before-self.reserve_cumulative_transfer,
    total_account_equity=before+reserve_before,enabled=bool(enabled),
    eligible=False,duplicate=False,reason='',weekly_stop_valid=None,
    weekly_stop_price=None,weekly_stop_week_end=None,range_checked=False,
    range_would_block=None,range_contract_epoch_id=None,range_low=None,
    range_high=None,range_history_end=None,selected_volume_after_parent=None)
   self.reserve_signal_checks.append(check)
   if not enabled:check['reason']='disabled'
   elif date<start:check['reason']='before_account_start'
   elif entry_context not in NEW_ENTRY_CONTEXTS:check['reason']='not_new_entry_context'
   elif signal not in NATIVE_SIGNALS.get(direction,frozenset()) or not self._is_native_openable_candidate(signal,direction,1):check['reason']='not_native_allowed_signal'
   else:
    try:
     stop,valid,context=self._weekly_initial_stop_qualification(vt_symbol,direction,bar)
     check.update(weekly_stop_price=_finite(stop,'weekly_stop'),weekly_stop_valid=bool(valid),weekly_stop_week_end=str(context['week_end']))
     if not valid:check['reason']='invalid_weekly_stop_direction'
     else:
      if range_enabled and direction=='short' and signal=='short_case1a':
       row=range_history.snapshot(vt_symbol,date,bar.close_price)
       check.update(range_checked=True,range_would_block=bool(row['would_block']),
        range_contract_epoch_id=str(row['contract_epoch_id']),range_low=float(row['range_low']),
        range_high=float(row['range_high']),range_history_end=str(row['history_end']))
      if check['range_would_block'] is True:check['reason']='short_bottom20'
      else:
       check['eligible']=True
       if key in self._reserve_seen_candidates:check.update(duplicate=True,reason='duplicate_candidate')
       else:
        self._reserve_seen_candidates.add(key)
        transfer=min(max(TRADING_INITIAL-before,0.0),reserve_before)
        if transfer>0:
         self.settled_balance=_finite(self.settled_balance,'settled_balance')+transfer
         self.reserve_balance=reserve_before-transfer
         self.reserve_cumulative_transfer+=transfer
         self.estimated_equity=self._reserve_marked_equity()
         if not math.isclose(self.estimated_equity,before+transfer,rel_tol=1e-12,abs_tol=1e-7):raise ValueError('reserve_transfer_equity_bridge_failed')
         self._reserve_refresh_funding_caches()
         check.update(reason='transferred',transfer_amount=transfer,
          trading_equity_after=self.estimated_equity,reserve_after=self.reserve_balance,
          cumulative_transfer=self.reserve_cumulative_transfer,
          raw_account_equity=self.estimated_equity-self.reserve_cumulative_transfer,
          total_account_equity=self.estimated_equity+self.reserve_balance)
         event={k:v for k,v in check.items() if k not in {'eligible','duplicate','reason','selected_volume_after_parent','enabled'}}
         event['event_id']=len(self.reserve_transfer_events)+1
         self.reserve_transfer_events.append(event)
        else:check['reason']='equity_at_or_above_floor' if before>=TRADING_INITIAL else 'reserve_exhausted'
    except Exception:
     if not check['reason']:check['reason']='admission_or_funding_error'
     raise
   result=super()._calculate_entry_sizing(vt_symbol,direction,bar,history,signal_data,
    risk_mode_override=risk_mode_override,entry_context=entry_context,
    apply_env_gate=apply_env_gate,active_positions_before=active_positions_before,
    correlation_snapshot=correlation_snapshot)
   if self.estimated_equity<=0:
    result=dict(result,selected_volume=0,reserve_nonpositive_trading_equity=True,
     rejection_reason='reserve_nonpositive_trading_equity',risk_amount=0.0,
     limited_balance=0.0,allowed_capital=0.0,single_trade_capital_limit=0.0,free_capital=0.0)
   check['selected_volume_after_parent']=int(result['selected_volume'])
   return result

  def reserve_snapshot(self,date,phase):
   date=_day(date)
   if date<start:return None
   equity=self._reserve_marked_equity();raw=equity-self.reserve_cumulative_transfer
   row=dict(date=date,phase=str(phase),sequence=len(self.reserve_daily_snapshots)+1,
    raw_account_equity=raw,cumulative_transfer=self.reserve_cumulative_transfer,
    trading_account_equity=equity,reserve_balance=self.reserve_balance,
    total_account_equity=equity+self.reserve_balance,
    transfer_event_count=len(self.reserve_transfer_events),
    trade_costs_total=_finite(getattr(self,'trade_costs_total',0.0),'trade_costs_total'))
   if not math.isclose(row['total_account_equity'],raw+RESERVE_INITIAL,rel_tol=1e-12,abs_tol=1e-7):raise ValueError('reserve_total_wealth_bridge_failed')
   self.reserve_daily_snapshots.append(row)
   return row

  def on_bars(self,bars):
   try:
    result=super().on_bars(bars)
    if bars:self.reserve_snapshot(next(iter(bars.values())).datetime,'after_on_bars_settlement')
    return result
   except Exception as exc:
    self.strategy_engine.intraday_execution_failure=f'{type(exc).__name__}: {exc!r}'
    raise

  def update_trade(self,trade):
   try:
    result=super().update_trade(trade)
    date=getattr(trade,'trading_date',None)
    if date is None:date=getattr(self.strategy_engine,'datetime',None)
    if date is None:raise ValueError('reserve_trade_accounting_date_missing')
    self.reserve_snapshot(date,'after_update_trade')
    return result
   except Exception as exc:
    self.strategy_engine.intraday_execution_failure=f'{type(exc).__name__}: {exc!r}'
    raise
 return ReserveTopupStrategy
