"""Causal non-delivery research lifecycle. No last-bar hindsight or synthetic settlement."""
from bisect import bisect_left,bisect_right
from datetime import date,datetime
import json,re


def day(value):
    text=str(value)[:10]
    try:return date.fromisoformat(text).isoformat()
    except ValueError as exc:raise ValueError('invalid_lifecycle_date:'+text) from exc


class LifecyclePolicy:
    def __init__(self,metadata,calendar):
        self.sessions=[day(x) for x in calendar]
        if not self.sessions or self.sessions!=sorted(set(self.sessions)):
            raise ValueError('invalid_lifecycle_calendar')
        self.rows={}
        for vt,meta in metadata.items():
            maturity=day(meta.get('maturity_date',''))
            month=str(meta.get('contract_yyyymm',''))
            if not re.fullmatch(r'\d{6}',month):raise ValueError('missing_delivery_month:'+vt)
            first=date(int(month[:4]),int(month[4:]),1).isoformat()
            kind=meta.get('product_class')
            if kind not in {'Index','Commodity','Government'}:raise ValueError('unknown_product_class:'+vt)
            expiry_index=bisect_left(self.sessions,maturity)
            if expiry_index>=len(self.sessions) or self.sessions[expiry_index]!=maturity:
                raise ValueError('maturity_outside_calendar:'+vt)
            if kind=='Index':
                if not re.fullmatch(r'(IF|IH|IC|IM)\d{6}\.CFFEX',vt):raise ValueError('unqualified_index:'+vt)
                expected_code=vt.split('.')[0][:-6]
                if meta.get('product',expected_code)!=expected_code:raise ValueError('index_metadata_mismatch:'+vt)
                cutoff_index=expiry_index-1;bucket='index_before_last_trade'
            else:
                first_index=bisect_left(self.sessions,first)
                if first_index>=len(self.sessions):raise ValueError('delivery_month_outside_calendar:'+vt)
                cutoff_index=min(first_index-2,expiry_index-10)
                bucket='non_index_early_non_delivery_operation'
            if cutoff_index<1:raise ValueError('insufficient_lifecycle_calendar:'+vt)
            self.rows[vt]=dict(vt_symbol=vt,product_class=kind,contract_yyyymm=month,
                maturity_date=maturity,deadline=self.sessions[cutoff_index],
                exit_signal_date=self.sessions[cutoff_index-1],policy_bucket=bucket)

    def deadline(self,vt):return self.rows[vt]['deadline']

    def next_session(self,signal_day):
        d=day(signal_day);idx=bisect_right(self.sessions,d)
        if idx>=len(self.sessions):raise ValueError('next_session_unknown:'+d)
        return self.sessions[idx]

    def entry_allowed(self,vt,fill_day):return day(fill_day)<self.deadline(vt)

    def exit_due(self,vt,signal_day):return self.next_session(signal_day)>=self.deadline(vt)

    def assert_flat_by_deadline(self,positions,at_day):
        d=day(at_day)
        overdue={vt:int(qty) for vt,qty in positions.items() if qty and d>=self.deadline(vt)}
        if overdue:raise RuntimeError('unresolved_lifecycle_position:'+json.dumps(overdue,sort_keys=True))


class LifecycleStrategyMixin:
    def _effective_max_concurrent_positions(self,entry_context):
        # With one lot/product, universe size is physical capacity, not a count-risk cap.
        return len(self.product_symbols)

    def apply_lifecycle_targets(self,bars):
        if not bars:return
        engine=self.strategy_engine;policy=engine.lifecycle_policy
        today=day(next(iter(bars.values())).datetime)
        forced=set()
        for vt,qty in list(self.pos_data.items()):
            if not qty or not policy.exit_due(vt,today):continue
            product=self.source_symbol_by_contract[vt];forced.add(product)
            state=self.states[product]
            self._clear_rollover_delay_state(state)
            self._close_position_when_target_unavailable(product,state=state,target_contract='',bars=bars,
                                                       reason='contract_lifecycle_exit')
            self.set_target(vt,0)
            engine.lifecycle_events.append(dict(date=today,vt_symbol=vt,event='close_target_zero',
                actual_position=int(qty),deadline=policy.deadline(vt)))
        # An old OPEN may have been postponed by sparse data; cancel it causally.
        for key,order in list(engine.active_limit_orders.items()):
            if str(order.offset.value) in {'开','open'} and not policy.entry_allowed(order.vt_symbol,policy.next_session(today)):
                engine.cancel_lifecycle_open(order)
                engine.lifecycle_events.append(dict(date=today,vt_symbol=order.vt_symbol,event='cancel_pending_open',
                    actual_position=int(self.get_pos(order.vt_symbol)),deadline=policy.deadline(order.vt_symbol)))
        return today,forced

    def on_bars(self,bars):
        result=self.apply_lifecycle_targets(bars)
        if result is None:return super().on_bars(bars)
        today,forced=result;original=self.daily_mapping.get(today,{})
        policy=self.strategy_engine.lifecycle_policy;next_day=policy.next_session(today)
        self.daily_mapping[today]={p:vt for p,vt in original.items()
                                   if p not in forced and policy.entry_allowed(vt,next_day)}
        try:return super().on_bars(bars)
        finally:self.daily_mapping[today]=original


class LifecycleEngineMixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.lifecycle_events=[]

    def cancel_lifecycle_open(self,order):
        strategy=self.strategy;vt=order.vt_symbol
        strategy.set_target(vt,0)
        self.cancel_order(strategy,order.vt_orderid)
        if strategy.get_pos(vt):return
        finder=getattr(strategy,'_find_state_by_contract',None)
        state=finder(vt) if finder is not None else None
        if state is not None and state.contract_vt_symbol==vt and all(not layer.entry_price_synced for layer in state.layers):
            product=state.product_vt_symbol
            state.reset()
            strategy.pending_active_products.discard(product)

    def check_lifecycle_positions(self,dt,after_fills=True):
        if not after_fills:return
        try:self.lifecycle_policy.assert_flat_by_deadline(self.strategy.pos_data,dt)
        except RuntimeError as exc:
            self.failure_snapshot=dict(date=day(dt),error=str(exc),
                positions={vt:int(q) for vt,q in self.strategy.pos_data.items() if q},
                deadlines={vt:self.lifecycle_policy.deadline(vt) for vt,q in self.strategy.pos_data.items() if q},
                financial_metrics_valid=False)
            raise

    def _fill_order(self,order,bar):
        from vnpy.trader.constant import Offset
        if order.offset==Offset.OPEN and not self.lifecycle_policy.entry_allowed(order.vt_symbol,self.datetime):
            self.blocked_open_orders.append(dict(date=day(self.datetime),order_id=order.vt_orderid,
                vt_symbol=order.vt_symbol,reason='lifecycle_new_open_cutoff'))
            self.cancel_lifecycle_open(order)
            return
        return super()._fill_order(order,bar)

    def new_bars(self,dt):
        super().new_bars(dt)
        self.check_lifecycle_positions(dt,after_fills=True)
