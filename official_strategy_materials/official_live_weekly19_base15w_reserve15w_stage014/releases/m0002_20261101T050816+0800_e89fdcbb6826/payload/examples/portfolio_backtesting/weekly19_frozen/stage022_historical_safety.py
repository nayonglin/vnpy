"""Isolated historical authorization and physical-epoch safety.

No alpha, AM, risk, execution price or timing method is replaced. The engine
wrapper checks identities before the original delayed-fill queue; no orders,
positions or layers are repaired to make an epoch transition pass.
"""
from copy import deepcopy
import math
import pandas as pd


def _day(value):
    stamp=pd.Timestamp(value)
    if pd.isna(stamp):raise ValueError('historical_day_required')
    if stamp.tzinfo:stamp=stamp.tz_convert('Asia/Shanghai').tz_localize(None)
    return stamp.normalize().strftime('%Y-%m-%d')


def clear_unowned_targets(strategy):
    """A target without a current planned layer may only authorize close-to-flat.

    Retain legitimate pending plans even while actual position is still zero.
    This is native-symbol ownership, complemented by the pre-fill epoch guard.
    Actual positions and state/layers are never changed here.
    """
    owned={state.contract_vt_symbol for state in strategy.states.values()
        if state.contract_vt_symbol and state.layers and state.direction in {'long','short'}}
    if not hasattr(strategy,'historical_target_cleanup'):strategy.historical_target_cleanup=[]
    events=[]
    for symbol,target in list(strategy.target_data.items()):
        if target and symbol not in owned:
            event=dict(date=str(getattr(strategy,'current_bar_date','')),vt_symbol=symbol,
                previous_target=target,actual_position=strategy.get_pos(symbol),new_target=0,
                reason='no_current_planned_layer_close_only')
            strategy.set_target(symbol,0)
            strategy.historical_target_cleanup.append(event);events.append(event)
    return events


def historical_strategy_class(base,account_start):
    """Wrap an already-M strategy once; record all requested-window readiness."""
    start=_day(account_start)
    class HistoricalSafetyStrategy(base):
        research_historical_safety_enabled=True
        historical_account_start=start
        def on_bars(self,bars):
            if not hasattr(self,'historical_weekly_readiness'):self.historical_weekly_readiness=[]
            result=super().on_bars(bars)
            if bars:
                day=_day(next(iter(bars.values())).datetime)
                if day>=start:
                    targets=self.daily_mapping.get(day,{})
                    self.historical_weekly_readiness.append(dict(date=day,mapped_products=len(targets),
                        ready_target_contracts=sum(bool(self.ams.get(symbol) and self.ams[symbol].inited) for symbol in targets.values()),
                        newly_completed_targets=sum(bool(self.ams.get(symbol) and self.ams[symbol].fresh) for symbol in targets.values())))
            return result
        def rebalance_portfolio(self,bars):
            clear_unowned_targets(self)
            return super().rebalance_portfolio(bars)
    return HistoricalSafetyStrategy


class HistoricalEpochError(ValueError):
    def __init__(self,reason,details):
        super().__init__(reason+':'+str(details.get('vt_symbol',''))+':'+str(details.get('date','')))
        self.reason=reason;self.details={**details,'reason':reason}


def _reject(engine,reason,details):
    failure=HistoricalEpochError(reason,details)
    engine.historical_epoch_failures.append(failure.details)
    engine.intraday_execution_failure=f'{type(failure).__name__}: {failure!r}'
    raise failure


def check_epoch_transition(engine,day,real_bars,epoch_lookup):
    """Validate a complete current real-bar batch before any fill can run.

    Lookup keys are (native_vt_symbol, YYYY-MM-DD) and values frozen physical
    epoch IDs. Zero-volume bars do not establish identity or advance AM epochs.
    All transitions require a >366-day real-bar gap (the inherited AM reset
    condition), zero old position/target and no old active order/planned layer.
    Validation commits epoch state atomically for the batch; failed validation
    only appends a failure receipt. It never mutates AM, orders or positions.
    """
    day=_day(day)
    for attr,empty in [('historical_epoch_state',{}),('historical_epoch_transitions',[]),('historical_epoch_failures',[])]:
        if not hasattr(engine,attr):setattr(engine,attr,empty)
    if _day(engine.datetime)!=day:_reject(engine,'epoch_engine_day_mismatch',dict(date=day))
    pending=deepcopy(engine.historical_epoch_state);events=[];initialized=positive=0
    for symbol,bar in real_bars.items():
        detail=dict(vt_symbol=str(symbol),date=day)
        if str(bar.vt_symbol)!=str(symbol):_reject(engine,'epoch_bar_symbol_mismatch',detail)
        if _day(bar.datetime)!=day:_reject(engine,'epoch_bar_day_mismatch',detail)
        try:volume=float(bar.volume)
        except (AttributeError,TypeError,ValueError):_reject(engine,'invalid_epoch_bar_volume',detail)
        if not math.isfinite(volume) or volume<0:_reject(engine,'invalid_epoch_bar_volume',detail)
        if volume==0:continue
        positive+=1;epoch=epoch_lookup.get((str(symbol),day))
        if not isinstance(epoch,str) or not epoch.strip():_reject(engine,'physical_epoch_missing',detail)
        prior=pending.get(str(symbol))
        if prior is None:
            pending[str(symbol)]=dict(epoch=epoch,first_real_day=day,last_real_day=day)
            initialized+=1;continue
        if day<prior['last_real_day']:_reject(engine,'epoch_time_reversal',detail)
        if epoch!=prior['epoch']:
            strategy=engine.strategy
            old_pos=strategy.get_pos(symbol);old_target=strategy.get_target(symbol)
            orders=[str(getattr(order,'vt_orderid',key)) for key,order in engine.active_limit_orders.items()
                if str(getattr(order,'vt_symbol',''))==str(symbol)]
            layers=sum(len(state.layers or []) for state in strategy.states.values()
                if str(state.contract_vt_symbol)==str(symbol))
            gap=(pd.Timestamp(day)-pd.Timestamp(prior['last_real_day'])).days
            am=getattr(strategy,'ams',{}).get(symbol)
            detail.update(old_epoch=prior['epoch'],new_epoch=epoch,last_old_real_day=prior['last_real_day'],
                first_new_real_day=day,gap_days=gap,old_position=old_pos,old_target=old_target,
                old_active_order_ids=orders,old_layer_count=layers,
                old_week_count=int(getattr(am,'count',0)) if am is not None else None)
            if old_pos!=0 or old_target!=0 or orders or layers:_reject(engine,'epoch_transition_not_flat',detail)
            if gap<=366:_reject(engine,'epoch_gap_not_safely_reset',detail)
            events.append({**detail,'accepted':True,'action':'flat_physical_epoch_transition',
                'AM_reset_owner':'inherited WeeklyArrayManager.update_bar after original fill queue',
                'AM_reset_required':True})
            pending[str(symbol)]=dict(epoch=epoch,first_real_day=day,last_real_day=day)
        else:prior['last_real_day']=day
    engine.historical_epoch_state=pending
    engine.historical_epoch_transitions.extend(events)
    return dict(accepted=True,positive_real_bars=positive,initialized_epochs=initialized,
        transitions=len(events),tracked_native_symbols=len(pending))


def historical_engine_class(base,epoch_lookup):
    """Only insert a pre-fill identity check; preserve original strict queue."""
    class HistoricalSafetyEngine(base):
        def cross_delayed_orders(self):
            try:
                real_bars={symbol:bar for symbol in self.vt_symbols
                    if (bar:=self.history_data.get((self.datetime,symbol))) is not None}
                check_epoch_transition(self,self.datetime,real_bars,epoch_lookup)
                return super().cross_delayed_orders()
            except Exception as exc:
                # vn.py's outer daily loop catches exceptions; Stage827's
                # run_backtesting checks this flag and re-raises after that loop.
                self.intraday_execution_failure=f'{type(exc).__name__}: {exc!r}'
                raise
    return HistoricalSafetyEngine
