"""Long-only completed causal-main weekly MA gate; inherited budget and shorts stay intact."""
from dataclasses import dataclass,asdict,is_dataclass
import json,math
import pandas as pd
from vnpy.trader.constant import Direction,Offset
from stage039_risk_budget_candidate import FullMarketNativeRiskBudgetOneLot


def date_string(value):
    return pd.Timestamp(value).date().isoformat()


def snapshot_valid(value,product,asof,phase):
    try:
        ma=[float(value[key]) for key in ('ma5','ma10','ma20','ma40')]
        last=pd.Timestamp(value['week_last_session']).date();current=pd.Timestamp(asof).date()
        return (value.get('allowed') is True and value.get('product_vt_symbol')==product
                and value.get('phase')==phase and value.get('asof_date')==current.isoformat()
                and bool(value.get('evidence_id')) and int(value['history_weeks'])>=40
                and int(value['valid_weeks'])==40 and all(math.isfinite(x) and x>0 for x in ma)
                and ma[0]>ma[1]>ma[2]>ma[3]
                and (last<=current if phase=='signal_close' else last<current))
    except (KeyError,TypeError,ValueError,OverflowError):return False


def weekly_snapshot(engine,product,asof,phase):
    provider=getattr(engine,'weekly_main',None)
    value=(dict(provider.lookup(product,asof,phase=phase)) if provider is not None else
           dict(product_vt_symbol=product,asof_date=date_string(asof),phase=phase,allowed=False,
                reason='weekly_provider_missing',evidence_id='',week_last_session=None,
                ma5=None,ma10=None,ma20=None,ma40=None,history_weeks=0,valid_weeks=0))
    if not snapshot_valid(value,product,asof,phase):
        value['allowed']=False
        if value.get('reason') in ('bullish','ready') or not value.get('reason'):value['reason']='invalid_weekly_evidence'
    return value


@dataclass(frozen=True)
class WeeklyEntryAuthorization:
    contract_vt_symbol:str
    product_vt_symbol:str
    direction:str
    signal:str
    signal_date:str
    snapshot_json:str


class WeeklyLongEntryMixin:
    def _calculate_entry_sizing(self,vt_symbol,direction,bar,history,signal_data,
            risk_mode_override=None,entry_context='flat_entry',apply_env_gate=True,
            active_positions_before=None,correlation_snapshot=None):
        sizing=super()._calculate_entry_sizing(vt_symbol,direction,bar,history,signal_data,
            risk_mode_override=risk_mode_override,entry_context=entry_context,apply_env_gate=apply_env_gate,
            active_positions_before=active_positions_before,correlation_snapshot=correlation_snapshot)
        # env_probe contributes to the shared environment of both sides. Keep it
        # exactly native: this policy applies only to actual long entry sizing.
        if direction!='long' or entry_context=='env_probe':return sizing
        value=dict(sizing);before=int(value.get('selected_volume') or 0)
        product=self.source_symbol_by_contract[vt_symbol]
        snap=weekly_snapshot(self.strategy_engine,product,bar.datetime,'signal_close')
        value.update(weekly_long_gate_enabled=1,weekly_long_gate_passed=int(snap['allowed']),
                     weekly_long_snapshot_json=json.dumps(snap,sort_keys=True,allow_nan=False))
        if not snap['allowed']:value['selected_volume']=0
        if not hasattr(self,'weekly_signal_audit'):self.weekly_signal_audit=[]
        self.weekly_signal_audit.append(dict(date=date_string(bar.datetime),vt_symbol=vt_symbol,product_vt_symbol=product,
            direction=direction,entry_context=entry_context,native_selected_volume=before,
            selected_volume=int(value.get('selected_volume') or 0),weekly_allowed=snap['allowed'],snapshot_json=value['weekly_long_snapshot_json']))
        return value

    def _open_position(self,state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=None):
        if direction!='long':return super()._open_position(state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=sizing_snapshot)
        snap=weekly_snapshot(self.strategy_engine,state.product_vt_symbol,bar.datetime,'signal_close')
        if not snap['allowed'] or volume!=1:return
        old={id(x) for x in state.layers}
        result=super()._open_position(state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=sizing_snapshot)
        created=[x for x in state.layers if id(x) not in old]
        if not created:return result  # An inherited budget/margin gate rejected it.
        if len(created)!=1:raise RuntimeError('weekly_pending_layer_identity_ambiguous')
        created[0].stage051_weekly_authorization=WeeklyEntryAuthorization(contract_vt_symbol,state.product_vt_symbol,
            direction,signal,date_string(bar.datetime),json.dumps(snap,sort_keys=True,allow_nan=False))
        return result


class FullMarketWeeklyLong(WeeklyLongEntryMixin,FullMarketNativeRiskBudgetOneLot):pass


class WeeklyLongExecutionMixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.weekly_execution_audit=[]

    def _fill_order(self,order,bar):
        if order.offset!=Offset.OPEN or order.direction!=Direction.LONG:return super()._fill_order(order,bar)
        s=self.strategy;vt=order.vt_symbol;product=s.source_symbol_by_contract[vt]
        state=s._find_state_by_contract(vt)
        layers=[] if state is None or state.direction!='long' else [x for x in state.layers if x.direction=='long' and not x.entry_price_synced and int(x.volume)==1]
        layer=layers[0] if len(layers)==1 else None
        authorization=getattr(layer,'stage051_weekly_authorization',None)
        signal={};bound=False
        if isinstance(authorization,WeeklyEntryAuthorization):
            signal=json.loads(authorization.snapshot_json)
            bound=(authorization.contract_vt_symbol==vt and authorization.product_vt_symbol==product
                and authorization.direction=='long' and authorization.signal==layer.signal
                and authorization.signal_date==date_string(layer.entry_date)
                and snapshot_valid(signal,product,authorization.signal_date,'signal_close'))
        current=weekly_snapshot(self,product,self.datetime,'open')
        allowed=bound and current['allowed'];reason='' if allowed else ('weekly_signal_authorization_missing' if not bound else 'weekly_not_bullish_before_open')
        row=dict(date=date_string(self.datetime),vt_symbol=vt,order_id=order.vt_orderid,direction='long',
            original_signal_date=authorization.signal_date if isinstance(authorization,WeeklyEntryAuthorization) else '',
            signal_snapshot_json=json.dumps(signal,sort_keys=True,allow_nan=False),
            open_snapshot_json=json.dumps(current,sort_keys=True,allow_nan=False),weekly_allowed=allowed,reason=reason,filled=False)
        self.weekly_execution_audit.append(row)
        if not allowed:
            self._cancel_budget_open(order,layer,reason);return
        before=set(self.trades);result=super()._fill_order(order,bar);added=set(self.trades)-before
        row['filled']=bool(added)
        if added:
            if len(added)!=1:raise RuntimeError('multiple_weekly_authorized_fills')
            trade=self.trades[next(iter(added))];row['trade_id']=trade.vt_tradeid
            trade.stage051_weekly_signal_snapshot=signal
            trade.stage051_weekly_open_snapshot=current
        return result
