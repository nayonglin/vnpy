"""Long prior-history top20 veto with strict record-high exemption.

Short bottom20 remains the byte-frozen Stage005 implementation, including its
signal day. Prior long bounds deliberately exclude the complete signal day.
"""
from copy import deepcopy
import math
import pandas as pd
from stage005_short_bottom20 import range_strategy_class

class PriorRangeHistory:
    def __init__(self,current_history):
        f=current_history.table.reset_index().copy()
        g=f.groupby(['vt_symbol','contract_epoch_id'],sort=False)
        f['prior_range_low']=g.range_low.shift(1);f['prior_range_high']=g.range_high.shift(1)
        f['history_end']=g.date.shift(1);f['history_bar_count']=f.history_bar_count-1
        self.table=f.set_index(['vt_symbol','date'])[['contract_epoch_id','close','prior_range_low','prior_range_high','history_start','history_end','history_bar_count']]
    def snapshot(self,vt_symbol,signal_date,signal_close):
        day=str(signal_date)[:10]
        try:r=self.table.loc[(vt_symbol,day)]
        except KeyError as exc:raise ValueError('long_prior_signal_source_missing') from exc
        price=float(signal_close)
        if not math.isfinite(price) or price<=0 or not math.isclose(price,float(r['close']),rel_tol=0,abs_tol=1e-9):raise ValueError('long_prior_signal_close_mismatch')
        count=int(r['history_bar_count']);last=str(r['history_end']);first=str(r['history_start'])
        if count<1 or not first<=last<day:raise ValueError('long_prior_history_missing_or_future')
        low,high=float(r['prior_range_low']),float(r['prior_range_high'])
        if not all(math.isfinite(x) and x>0 for x in [low,high]) or low>high:raise ValueError('long_prior_invalid_range')
        width=high-low;threshold=low+.8*width;breakout=price>high
        return dict(vt_symbol=vt_symbol,signal_date=day,signal_close=price,contract_epoch_id=str(r['contract_epoch_id']),history_start=first,history_end=last,history_bar_count=count,prior_range_low=low,prior_range_high=high,top20_threshold_price=threshold,prior_range_position=None if width==0 else (price-low)/width,range_status='flat_prior_range' if width==0 else 'valid',breakout_exempt=bool(breakout),would_block=bool(threshold<=price<=high),history_scope='all_available_same_physical_epoch_daily_strictly_before_signal')

def long_top20_strategy_class(base,short_history,prior_history,enabled=True):
    short_wrapped=range_strategy_class(base,short_history,enabled=True)
    class LongTop20WithShortBottom20Strategy(short_wrapped):
        research_long_price_range_gate_enabled=bool(enabled)
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);self.long_price_range_decisions=[]
        def _calculate_entry_sizing(self,vt_symbol,direction,bar,history,signal_data,risk_mode_override=None,entry_context='flat_entry',apply_env_gate=True,active_positions_before=None,correlation_snapshot=None):
            result=super()._calculate_entry_sizing(vt_symbol,direction,bar,history,signal_data,risk_mode_override=risk_mode_override,entry_context=entry_context,apply_env_gate=apply_env_gate,active_positions_before=active_positions_before,correlation_snapshot=correlation_snapshot)
            if direction!='long' or entry_context not in {'flat_entry','env_probe','reverse_entry'} or signal_data.get('signal') not in {'long_case1a','long_case2'}:return result
            row=prior_history.snapshot(vt_symbol,pd.Timestamp(bar.datetime).strftime('%Y-%m-%d'),bar.close_price)
            before=int(result['selected_volume']);blocked=bool(enabled and row['would_block'] and before>0)
            row.update(enabled=bool(enabled),direction='long',entry_context=entry_context,signal=str(signal_data['signal']),selected_volume_before=before,selected_volume_after=0 if blocked else before,applied_block=blocked)
            self.long_price_range_decisions.append(row)
            if not blocked:return result
            gated=deepcopy(result);gated.update(selected_volume=0,rejection_reason='long_price_in_prior_historical_top20',long_price_range_gate_blocked=True)
            return gated
        def _open_position(self,state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=None):
            if enabled and direction=='long' and signal in {'long_case1a','long_case2'}:
                row=prior_history.snapshot(contract_vt_symbol,pd.Timestamp(bar.datetime).strftime('%Y-%m-%d'),bar.close_price)
                if row['would_block']:raise ValueError('long_top20_gate_bypassed')
            return super()._open_position(state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=sizing_snapshot)
    return LongTop20WithShortBottom20Strategy
