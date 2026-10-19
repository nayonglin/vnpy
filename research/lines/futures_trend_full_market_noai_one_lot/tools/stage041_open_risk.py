"""Causal next-open budget guard, using the native signal budget as an immutable ceiling."""
from dataclasses import asdict,is_dataclass
import math
from vnpy.trader.constant import Direction,Offset


def number(value):
    try:return float(value)
    except (TypeError,ValueError):return float('nan')


def opening_budget(snapshot,*,opening_equity,reserved_margin):
    """Reapply only native currency-budget arithmetic to causal opening resources.

    Freeze the signal's sizing cap and risk factors. Current resources may shrink
    authorization, never enlarge it. This does not re-evaluate a daily indicator.
    """
    keys=['target_risk_amount','risk_ratio','risk_multiplier','portfolio_overheat_cooldown_scale',
          'directional_30d_risk_boost_multiplier','min_risk_per_trade','max_risk_per_trade',
          'effective_capital_usage_ratio','sizing_equity']
    values={k:number(snapshot.get(k)) for k in keys}
    eq=number(opening_equity);reserved=number(reserved_margin)
    if not all(math.isfinite(x) for x in [eq,reserved,*values.values()]):return 0.
    if eq<=0 or reserved<0 or any(values[k]<0 for k in keys):return 0.
    if values['max_risk_per_trade']<values['min_risk_per_trade']:return 0.
    cap=min(values['sizing_equity'],eq)
    limited=max(0.,min(cap-reserved,cap*values['effective_capital_usage_ratio']-reserved))
    base=min(values['max_risk_per_trade'],max(values['min_risk_per_trade'],limited*values['risk_ratio']))
    budget=base*values['risk_multiplier']*values['portfolio_overheat_cooldown_scale']*values['directional_30d_risk_boost_multiplier']
    return max(0.,min(values['target_risk_amount'],budget))


def assess_open_risk(*,direction,open_price,stop_price,size,tick,snapshot,opening_equity,reserved_margin):
    p,stop,mult,t=map(number,[open_price,stop_price,size,tick])
    budget=opening_budget(snapshot,opening_equity=opening_equity,reserved_margin=reserved_margin)
    reason='';risk=float('nan')
    if direction not in ('long','short') or not all(math.isfinite(x) and x>0 for x in [p,stop,mult,t]):reason='invalid_open_or_stop'
    elif (direction=='long' and p<=stop) or (direction=='short' and p>=stop):reason='stop_already_crossed_at_open'
    else:
        risk=max(abs(p-stop)*mult,t*mult,1.)
        if budget<=0:reason='missing_or_zero_native_risk_budget'
        elif risk>budget:reason='one_lot_exceeds_native_risk_budget_at_open'
    return dict(allowed=not reason,reason=reason,one_lot_risk=risk,opening_budget=budget,
                opening_equity=number(opening_equity),reserved_margin=number(reserved_margin),
                open_price=p,stop_price=stop,size=mult,pricetick=t)


class OpeningRiskBudgetMixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.open_budget_audit=[]

    def _opening_reserved_margin(self,own_layer):
        s=self.strategy;reserved=0.
        for vt,qty in s.pos_data.items():
            if qty:
                m=self.research_metadata[vt]
                reserved+=abs(qty)*self.open_risk_prices[vt]*m['size']*m['margin_ratio']
        for state in s.states.values():
            vt=state.contract_vt_symbol
            if not vt:continue
            for layer in state.layers:
                if layer is own_layer or layer.entry_price_synced:continue
                raw=self.history_data.get((self.datetime,vt))
                mark=float(raw.open_price) if raw is not None and float(raw.volume)>0 else float(layer.entry_price)
                if not math.isfinite(mark) or mark<=0:return float('nan')
                m=self.research_metadata[vt]
                reserved+=abs(layer.volume)*mark*m['size']*m['margin_ratio']
        return reserved

    def _cancel_budget_open(self,order,layer,reason):
        s=self.strategy;vt=order.vt_symbol
        self.cancel_order(s,order.vt_orderid)
        # Rejection removes only this unfilled intent, never broker-style facts.
        state=s._find_state_by_contract(vt)
        if state is not None and not s.get_pos(vt) and all(not x.entry_price_synced for x in state.layers):
            # Under max-one policy all ambiguous same-contract unfilled intents
            # are invalid authorizations, not additional legitimate positions.
            product=state.product_vt_symbol;state.reset();s.pending_active_products.discard(product)
        elif state is not None and layer is not None and not layer.entry_price_synced:
            state.layers[:]=[x for x in state.layers if x is not layer]
        s.set_target(vt,int(s.get_pos(vt)))
        direction='long' if order.direction==Direction.LONG else 'short'
        key=(vt,direction)
        for idx in s.pending_entry_diagnostics.pop(key,[]):
            s.entry_risk_diagnostics[idx]['stage041_open_rejected_reason']=reason
        self.blocked_open_orders.append(dict(date=str(self.datetime.date()),order_id=order.vt_orderid,vt_symbol=vt,reason=reason))

    def _fill_order(self,order,bar):
        if order.offset!=Offset.OPEN:return super()._fill_order(order,bar)
        s=self.strategy;direction='long' if order.direction==Direction.LONG else 'short'
        state=s._find_state_by_contract(order.vt_symbol)
        layers=[] if state is None or state.direction!=direction else [x for x in state.layers if not x.entry_price_synced and x.direction==direction and int(x.volume)==1]
        layer=layers[0] if len(layers)==1 else None
        snapshot=getattr(layer,'stage039_signal_risk_budget',{})
        snapshot=asdict(snapshot) if is_dataclass(snapshot) else dict(snapshot)
        meta=self.research_metadata[order.vt_symbol]
        eq=float(self.opening_equity)-float(self.open_execution_costs)
        reserved=self._opening_reserved_margin(layer)
        assessment=assess_open_risk(direction=direction,open_price=bar.open_price,
            stop_price=getattr(layer,'stop_price',None),size=meta['size'],tick=meta['pricetick'],
            snapshot=snapshot,opening_equity=eq,reserved_margin=reserved)
        row=dict(date=str(self.datetime.date()),order_id=order.vt_orderid,vt_symbol=order.vt_symbol,
                 direction=direction,volume=int(order.volume),signal_snapshot=__import__('json').dumps(snapshot,sort_keys=True),**assessment)
        self.open_budget_audit.append(row)
        import pandas as pd
        try:
            bound=(layer is not None and bool(snapshot.get('snapshot_id'))
                   and snapshot.get('contract_vt_symbol')==order.vt_symbol
                   and snapshot.get('product_vt_symbol')==state.product_vt_symbol
                   and snapshot.get('direction')==direction
                   and snapshot.get('signal')==layer.signal
                   and pd.Timestamp(snapshot.get('signal_datetime')).date()==pd.Timestamp(layer.entry_date).date())
        except (ValueError,TypeError):bound=False
        if not bound:row.update(allowed=False,reason='unbound_signal_risk_budget')
        if int(order.volume)!=1:row.update(allowed=False,reason='non_one_lot_open')
        if not row['allowed']:
            self._cancel_budget_open(order,layer,row['reason']);row['filled']=False;return
        before=set(self.trades)
        result=super()._fill_order(order,bar)
        added=set(self.trades)-before;row['filled']=bool(added)
        if not added:
            row['allowed']=False;row['reason']='rejected_by_remaining_execution_gate'
            self._cancel_budget_open(order,layer,row['reason'])
        else:
            if len(added)!=1:raise RuntimeError('multiple_fills_for_one_budget_authorization')
            trade=self.trades[next(iter(added))];row['trade_id']=trade.vt_tradeid
            if float(trade.price)!=float(bar.open_price):raise RuntimeError('budget_price_differs_from_actual_fill')
            trade.stage041_budget=row['opening_budget'];trade.stage041_entry_risk=row['one_lot_risk']
            trade.stage041_signal_snapshot=snapshot
        return result
