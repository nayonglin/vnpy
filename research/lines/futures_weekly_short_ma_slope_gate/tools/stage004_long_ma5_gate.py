"""Stage004: long MA5-only gate plus immutable Stage001 short MA5/10 gate."""
from copy import deepcopy
import pandas as pd
from stage001_slope_gate import slope_strategy_class,slope_snapshot

def long_ma5_strategy_class(base, enabled=True):
    short_wrapped=slope_strategy_class(base,enabled=True)
    class LongMA5SlopeStrategy(short_wrapped):
        research_long_ma_slope_gate_enabled=bool(enabled)
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);self.long_ma_slope_decisions=[]
        def _calculate_entry_sizing(self,vt_symbol,direction,bar,history,signal_data,risk_mode_override=None,entry_context='flat_entry',apply_env_gate=True,active_positions_before=None,correlation_snapshot=None):
            result=super()._calculate_entry_sizing(vt_symbol,direction,bar,history,signal_data,risk_mode_override=risk_mode_override,entry_context=entry_context,apply_env_gate=apply_env_gate,active_positions_before=active_positions_before,correlation_snapshot=correlation_snapshot)
            if direction!='long' or entry_context not in {'flat_entry','env_probe','reverse_entry'} or signal_data.get('signal') not in {'long_case1a','long_case2'}:return result
            row=slope_snapshot(self.ams[vt_symbol],history,pd.Timestamp(bar.datetime).strftime('%Y-%m-%d'),vt_symbol)
            row['would_block']=row['ma5_delta']<0
            before=int(result['selected_volume']);blocked=bool(enabled and row['would_block'] and before>0)
            row.update(enabled=bool(enabled),direction='long',entry_context=entry_context,signal=str(signal_data['signal']),selected_volume_before=before,selected_volume_after=0 if blocked else before,applied_block=blocked)
            self.long_ma_slope_decisions.append(row)
            if not blocked:return result
            gated=deepcopy(result);gated.update(selected_volume=0,rejection_reason='long_ma5_slope_negative',long_ma_slope_gate_blocked=True)
            return gated
        def _open_position(self,state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=None):
            if enabled and direction=='long' and signal in {'long_case1a','long_case2'}:
                row=slope_snapshot(self.ams[contract_vt_symbol],history,pd.Timestamp(bar.datetime).strftime('%Y-%m-%d'),contract_vt_symbol)
                if row['ma5_delta']<0:raise ValueError('long_ma_slope_gate_bypassed')
            return super()._open_position(state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=sizing_snapshot)
    return LongMA5SlopeStrategy
