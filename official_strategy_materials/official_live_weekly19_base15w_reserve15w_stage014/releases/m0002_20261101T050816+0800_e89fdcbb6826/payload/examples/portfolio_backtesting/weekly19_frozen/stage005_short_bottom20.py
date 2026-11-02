"""Causal same-physical-contract cached daily range; no MA slope gates."""
from copy import deepcopy
import math
import pandas as pd

class RangeHistory:
    def __init__(self,frame):
        cols=['vt_symbol','date','contract_epoch_id','open','high','low','close','volume']
        f=frame[cols].copy()
        if f.empty or f[['vt_symbol','date','contract_epoch_id']].isna().any().any():raise ValueError('range_source_missing')
        f['date']=f.date.astype(str)
        if f.duplicated(['vt_symbol','date']).any() or not f.date.map(lambda d:len(d)==10 and pd.Timestamp(d).strftime('%Y-%m-%d')==d).all():raise ValueError('range_source_duplicate_or_bad_date')
        for key in ['open','high','low','close','volume']:
            f[key]=pd.to_numeric(f[key],errors='raise')
            if not f[key].map(lambda x:math.isfinite(x) and x>0).all():raise ValueError('range_source_nonfinite_or_nonpositive')
        if (f.low>f[['open','close']].min(axis=1)).any() or (f.high<f[['open','close']].max(axis=1)).any():raise ValueError('range_source_invalid_OHLC')
        f=f.sort_values(['vt_symbol','date']).reset_index(drop=True)
        # Epoch IDs come from frozen admission, never from a reused display symbol.
        groups=f.groupby(['vt_symbol','contract_epoch_id'],sort=False)
        f['range_low']=groups.low.cummin();f['range_high']=groups.high.cummax()
        f['history_start']=groups.date.transform('first');f['history_bar_count']=groups.cumcount()+1
        self.table=f.set_index(['vt_symbol','date'])[['contract_epoch_id','close','range_low','range_high','history_start','history_bar_count']]
    def snapshot(self,vt_symbol,signal_date,signal_close):
        day=str(signal_date)[:10]
        try:row=self.table.loc[(vt_symbol,day)]
        except KeyError as exc:raise ValueError('range_signal_source_missing') from exc
        price=float(signal_close)
        if not math.isfinite(price) or not math.isclose(price,float(row['close']),rel_tol=0,abs_tol=1e-9):raise ValueError('range_signal_close_mismatch')
        low,high=float(row['range_low']),float(row['range_high']);width=high-low
        if width<0 or not low<=price<=high:raise ValueError('range_inconsistent_bounds')
        threshold=low+.2*width;flat=width==0
        return dict(vt_symbol=vt_symbol,signal_date=day,signal_close=price,contract_epoch_id=str(row['contract_epoch_id']),history_start=str(row['history_start']),history_end=day,history_bar_count=int(row['history_bar_count']),range_low=low,range_high=high,threshold_fraction=.2,threshold_price=threshold,range_position=None if flat else (price-low)/width,range_status='flat_range_reject' if flat else 'valid',would_block=bool(flat or price<=threshold),history_scope='all_available_same_physical_epoch_daily_through_signal')

def range_strategy_class(base,range_history,enabled=True):
    class ShortBottom20RangeStrategy(base):
        research_short_ma_slope_gate_enabled=False
        research_long_ma_slope_gate_enabled=False
        research_short_price_range_gate_enabled=bool(enabled)
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.short_ma_slope_decisions=[];self.long_ma_slope_decisions=[];self.short_price_range_decisions=[]
        def _calculate_entry_sizing(self,vt_symbol,direction,bar,history,signal_data,risk_mode_override=None,entry_context='flat_entry',apply_env_gate=True,active_positions_before=None,correlation_snapshot=None):
            result=super()._calculate_entry_sizing(vt_symbol,direction,bar,history,signal_data,risk_mode_override=risk_mode_override,entry_context=entry_context,apply_env_gate=apply_env_gate,active_positions_before=active_positions_before,correlation_snapshot=correlation_snapshot)
            if direction!='short' or entry_context not in {'flat_entry','env_probe','reverse_entry'} or signal_data.get('signal')!='short_case1a':return result
            row=range_history.snapshot(vt_symbol,pd.Timestamp(bar.datetime).strftime('%Y-%m-%d'),bar.close_price)
            before=int(result['selected_volume']);blocked=bool(enabled and row['would_block'] and before>0)
            row.update(enabled=bool(enabled),direction='short',entry_context=entry_context,signal=str(signal_data['signal']),selected_volume_before=before,selected_volume_after=0 if blocked else before,applied_block=blocked)
            self.short_price_range_decisions.append(row)
            if not blocked:return result
            gated=deepcopy(result);gated.update(selected_volume=0,rejection_reason='short_price_in_historical_bottom20' if row['range_status']=='valid' else 'short_historical_range_flat',short_price_range_gate_blocked=True)
            return gated
        def _open_position(self,state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=None):
            if enabled and direction=='short' and signal=='short_case1a':
                row=range_history.snapshot(contract_vt_symbol,pd.Timestamp(bar.datetime).strftime('%Y-%m-%d'),bar.close_price)
                if row['would_block']:raise ValueError('short_price_range_gate_bypassed')
            return super()._open_position(state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=sizing_snapshot)
    return ShortBottom20RangeStrategy
