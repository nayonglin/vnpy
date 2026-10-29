"""One fixed short-entry gate on frozen Stage033 A; no rollover or exit changes."""
from copy import deepcopy
import math
import pandas as pd

def slope_snapshot(am, history, signal_date, vt_symbol):
    count=int(am.inner.count)
    if count<11 or len(history)<11 or len(am.completed)<11:
        raise ValueError('slope_completed_history_missing')
    close=pd.Series(history.tail(min(count,len(history)))['close'].to_numpy(dtype='float64'))
    tail=am.completed[-11:]
    dates=[str(r['week_end'])[:10] for r in tail]
    if dates!=sorted(set(dates)) or dates[-1]>str(signal_date)[:10]:
        raise ValueError('slope_future_or_invalid_week_dates')
    values=close.tail(11).tolist()
    if any(not math.isfinite(x) or x<=0 for x in values) or any(float(r['close'])!=x for r,x in zip(tail,values)):
        raise ValueError('slope_completed_source_mismatch')
    result=dict(vt_symbol=vt_symbol,signal_date=str(signal_date)[:10],week_end=dates[-1],previous_week_end=dates[-2],source_week_ends=dates,source_week_closes=values,observed_count=count)
    for n in [5,10]:
        ma=close.rolling(n).mean();current,previous=map(float,[ma.iloc[-1],ma.iloc[-2]])
        if not all(math.isfinite(x) for x in [current,previous]):raise ValueError('slope_nonfinite_ma')
        result.update({f'ma{n}_current':current,f'ma{n}_previous':previous,f'ma{n}_delta':current-previous})
    result['would_block']=result['ma5_delta']>0 or result['ma10_delta']>0
    return result

def slope_strategy_class(base, enabled):
    class ShortMaSlopeStrategy(base):
        research_short_ma_slope_gate_enabled=bool(enabled)
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);self.short_ma_slope_decisions=[]
        def _calculate_entry_sizing(self,vt_symbol,direction,bar,history,signal_data,risk_mode_override=None,entry_context='flat_entry',apply_env_gate=True,active_positions_before=None,correlation_snapshot=None):
            result=super()._calculate_entry_sizing(vt_symbol,direction,bar,history,signal_data,risk_mode_override=risk_mode_override,entry_context=entry_context,apply_env_gate=apply_env_gate,active_positions_before=active_positions_before,correlation_snapshot=correlation_snapshot)
            if direction!='short' or entry_context not in {'flat_entry','env_probe','reverse_entry'} or signal_data.get('signal')!='short_case1a':return result
            row=slope_snapshot(self.ams[vt_symbol],history,pd.Timestamp(bar.datetime).strftime('%Y-%m-%d'),vt_symbol)
            before=int(result['selected_volume']);blocked=bool(enabled and row['would_block'] and before>0)
            row.update(enabled=bool(enabled),entry_context=entry_context,signal=str(signal_data['signal']),selected_volume_before=before,selected_volume_after=0 if blocked else before,applied_block=blocked)
            self.short_ma_slope_decisions.append(row)
            if not blocked:return result
            gated=deepcopy(result);gated.update(selected_volume=0,rejection_reason='short_ma5_or_ma10_slope_positive',short_ma_slope_gate_blocked=True)
            return gated
        def _open_position(self,state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=None):
            if enabled and direction=='short' and signal=='short_case1a':
                row=slope_snapshot(self.ams[contract_vt_symbol],history,pd.Timestamp(bar.datetime).strftime('%Y-%m-%d'),contract_vt_symbol)
                if row['would_block']:raise ValueError('short_ma_slope_gate_bypassed')
            return super()._open_position(state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=sizing_snapshot)
    return ShortMaSlopeStrategy
