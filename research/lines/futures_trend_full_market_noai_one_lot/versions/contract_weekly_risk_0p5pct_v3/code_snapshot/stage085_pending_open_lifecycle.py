"""Retain a real deferred OPEN's original authorization, never reauthorize it.

Only zero-actual, one-layer, one-active-OPEN intentions with bound original
receipts are protected.  Native actual-position/CLOSE handling remains below
this mixin; cached quotes can dispatch orders but cannot become execution data.
"""
from dataclasses import asdict, is_dataclass
import json
import math

import pandas as pd
from vnpy.trader.constant import Direction, Offset
from stage068_fractional_risk import FractionalSignalRiskReceipt, _positive_integer, _valid_receipt
from stage075_fractional_weekly import WeeklyEntryAuthorization, snapshot_valid


def _plain(value):
    if is_dataclass(value):value=asdict(value)
    if isinstance(value,dict):return {str(k):_plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_plain(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):return str(value)
    return value


class PendingOpenLifecycleMixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.stage085_pending_open_events=[]

    def _stage085_orders(self,vt):
        return [order for order in self.strategy_engine.active_limit_orders.values()
                if order.vt_symbol==vt and order.offset==Offset.OPEN]

    def _stage085_status(self,state,*,allow_fresh=False):
        vt=state.contract_vt_symbol
        if not vt or self.get_pos(vt):return False,'not_zero_actual_open_intent'
        layers=state.layers
        if len(layers)!=1 or layers[0].entry_price_synced:return False,'missing_or_ambiguous_unfilled_layer'
        layer=layers[0];receipt=getattr(layer,'stage068_signal_risk_budget',None)
        fresh_record=getattr(self,'_stage085_fresh_layers',{}).get(vt)
        fresh=(allow_fresh and fresh_record is not None and fresh_record[0] is layer and fresh_record[1] is receipt)
        now=pd.Timestamp(self.strategy_engine.datetime).date()
        orders=self._stage085_orders(vt)
        try:
            snapshot=asdict(receipt) if isinstance(receipt,FractionalSignalRiskReceipt) else {}
            if not _valid_receipt(snapshot):return False,'invalid_original_fractional_receipt'
            direction=state.direction
            if not (direction in ('long','short') and layer.direction==direction
                    and snapshot['contract_vt_symbol']==vt
                    and snapshot['product_vt_symbol']==state.product_vt_symbol==self.source_symbol_by_contract[vt]
                    and snapshot['direction']==direction and snapshot['signal']==layer.signal
                    and pd.Timestamp(snapshot['signal_datetime']).date()==pd.Timestamp(layer.entry_date).date()<=now
                    and _positive_integer(layer.volume) and layer.volume==snapshot['authorized_volume']
                    and float(layer.stop_price)==snapshot['stop_price']):
                return False,'original_fractional_binding_mismatch'
            signed=int(layer.volume)*(1 if direction=='long' else -1)
            if self.get_target(vt)!=signed and not fresh:return False,'original_target_changed'
            if not (fresh and not orders) and (len(orders)!=1 or not orders[0].is_active() or not _positive_integer(orders[0].volume) or orders[0].volume!=layer.volume
                    or orders[0].direction!=(Direction.LONG if direction=='long' else Direction.SHORT)
                    or not pd.Timestamp(layer.entry_date).date()<=pd.Timestamp(orders[0].datetime).date()<=now):
                return False,'missing_or_mismatched_active_open_order'
            if self.daily_mapping.get(now.isoformat(),{}).get(state.product_vt_symbol)!=vt:
                return False,'mapping_changed_or_missing'
            if not fresh and any(qty and self.source_symbol_by_contract.get(other)==state.product_vt_symbol
                   for other,qty in self.pos_data.items()):
                return False,'actual_product_position_exists'
            if self.pending_close_lots.get(vt):return False,'pending_close_conflicts_with_zero_actual_open'
            if direction=='long':
                authorization=getattr(layer,'stage059_weekly_authorization',None)
                if not isinstance(authorization,WeeklyEntryAuthorization):return False,'original_weekly_authorization_missing'
                signal=json.loads(authorization.snapshot_json)
                if not (authorization.contract_vt_symbol==vt and authorization.product_vt_symbol==state.product_vt_symbol
                        and authorization.direction==direction and authorization.signal==layer.signal
                        and authorization.signal_date==pd.Timestamp(layer.entry_date).date().isoformat()
                        and snapshot_valid(signal,state.product_vt_symbol,vt,authorization.signal_date,'signal_close')):
                    return False,'original_weekly_authorization_invalid'
        except (KeyError,TypeError,ValueError,OverflowError):
            return False,'malformed_original_authorization'
        return True,'original_pending_open_preserved'

    def _stage085_funding_by_cluster(self,bars):
        usage={}
        for vt,quantity in self.pos_data.items():
            if not quantity:continue
            actual,_=self._pending_close_quantity(vt)
            _,margin_per_contract=self._stage078_mark(vt,bars)
            cluster=self._risk_cluster_for_symbol(self.source_symbol_by_contract[vt])
            usage[cluster]=usage.get(cluster,0.)+abs(actual)*margin_per_contract
        for state in self.states.values():
            if not self._stage085_status(state,allow_fresh=True)[0]:continue
            vt=state.contract_vt_symbol
            _,margin_per_contract=self._stage078_mark(vt,bars)
            cluster=self._risk_cluster_for_symbol(state.product_vt_symbol)
            usage[cluster]=usage.get(cluster,0.)+int(state.layers[0].volume)*margin_per_contract
        return usage

    def _estimate_margin_usage(self,bars):
        if getattr(self,'_stage078_forced_planning_active',False):return super()._estimate_margin_usage(bars)
        return sum(self._stage085_funding_by_cluster(bars).values())

    def _estimate_margin_usage_by_cluster(self,bars):
        if getattr(self,'_stage078_forced_planning_active',False):return super()._estimate_margin_usage_by_cluster(bars)
        return self._stage085_funding_by_cluster(bars)

    def _reserved_margin_in_use(self):
        witnessed=sum(row['margin'] for row in getattr(self,'_stage078_intent_reservations',{}).values())
        extra=max(0.,float(self.pending_margin_reservation)-witnessed)
        return sum(self._stage085_funding_by_cluster({}).values())+extra

    def _reserved_cluster_margin(self,cluster):
        witnessed=sum(row['cluster_margin'] for row in getattr(self,'_stage078_intent_reservations',{}).values() if row['cluster']==cluster)
        extra=max(0.,float(self.pending_cluster_margin_reservation.get(cluster,0.))-witnessed)
        return self._stage085_funding_by_cluster({}).get(cluster,0.)+extra

    def _estimate_unrealized_pnl_by_cluster(self,bars):
        result={}
        for vt,quantity in self.pos_data.items():
            if not quantity:continue
            actual,pending=self._pending_close_quantity(vt)
            bar,_=self._stage078_mark(vt,bars)
            direction='long' if actual>0 else 'short'
            state=self._find_state_by_contract(vt)
            layers=[] if state is None else [x for x in state.layers if x.entry_price_synced]
            lots=self.pending_close_lots.get(vt,[])
            if (sum(int(x.volume) for x in layers)+pending!=abs(actual)
                    or any(x.direction!=direction for x in layers)):
                raise RuntimeError('stage085_actual_entry_quantity_unknown:'+vt)
            entries=[(int(x.volume),float(x.entry_price)) for x in layers]+[(int(x['volume']),float(x['entry_price'])) for x in lots]
            pnl=sum(volume*(float(bar.close_price)-entry)*self.get_size(vt)*(1 if actual>0 else -1) for volume,entry in entries)
            cluster=self._risk_cluster_for_symbol(self.source_symbol_by_contract[vt])
            result[cluster]=result.get(cluster,0.)+pnl
        return result

    def _stage085_event(self,event,vt,state,reason,**fields):
        if not hasattr(self,'stage085_pending_open_events'):self.stage085_pending_open_events=[]
        self.stage085_pending_open_events.append(dict(date=pd.Timestamp(self.strategy_engine.datetime).date().isoformat(),
            vt_symbol=vt,product_vt_symbol=state.product_vt_symbol if state is not None else self.source_symbol_by_contract.get(vt,''),
            event=event,reason=reason,**fields))

    def _stage085_track_deferred_receipt(self,layer):
        receipt=getattr(layer,'stage068_signal_risk_budget',None)
        if isinstance(receipt,FractionalSignalRiskReceipt):
            if not hasattr(self,'_stage085_deferred_receipts'):self._stage085_deferred_receipts={}
            self._stage085_deferred_receipts[receipt.snapshot_id]=receipt

    def _stage085_cancel(self,vt,state,reason):
        # This helper is exclusively for unfilled intent; factual positions and
        # real CLOSE orders/lots must never be erased by cleanup.
        if self.get_pos(vt):raise RuntimeError('stage085_cannot_cancel_actual_position')
        layers=[] if state is None or state.contract_vt_symbol!=vt else [x for x in state.layers if not x.entry_price_synced]
        receipts=[_plain(getattr(x,'stage068_signal_risk_budget',None)) for x in layers]
        weekly=[_plain(getattr(x,'stage059_weekly_authorization',None)) for x in layers]
        orders=self._stage085_orders(vt)
        for order in orders:self.cancel_order(order.vt_orderid)
        directions={x.direction for x in layers}|{'long' if x.direction==Direction.LONG else 'short' for x in orders}
        directions.update(direction for contract,direction in self.pending_entry_diagnostics if contract==vt)
        for direction in directions:
            for index in self.pending_entry_diagnostics.pop((vt,direction),[]):
                self.entry_risk_diagnostics[index]['stage085_open_cancelled_reason']=reason
        if state is not None and state.contract_vt_symbol==vt:
            state.layers[:]=[x for x in state.layers if x.entry_price_synced]
            if not state.layers:state.reset()
            self.pending_active_products.discard(state.product_vt_symbol)
        self.set_target(vt,0)
        getattr(self,'_stage085_fresh_layers',{}).pop(vt,None)
        self.execution_price_overrides.pop(vt,None)
        reservation=getattr(self,'_stage078_intent_reservations',{}).pop(vt,None)
        if reservation is not None:
            self.pending_margin_reservation=max(0.,self.pending_margin_reservation-reservation['margin'])
            cluster=reservation['cluster']
            self.pending_cluster_margin_reservation[cluster]=max(0.,self.pending_cluster_margin_reservation.get(cluster,0.)-reservation['cluster_margin'])
        self._stage085_event('cancel',vt,state,reason,
            volume=sum(int(x.volume) for x in layers) if all(_positive_integer(x.volume) for x in layers) else 0,
            original_layer_quantities_json=json.dumps(_plain([x.volume for x in layers]),allow_nan=False,default=str),
            order_ids=[x.vt_orderid for x in orders],receipt_json=json.dumps(receipts,sort_keys=True,allow_nan=False,default=str),
            weekly_authorization_json=json.dumps(weekly,sort_keys=True,allow_nan=False,default=str))

    def _reset_intrabar_reservations(self):
        result=super()._reset_intrabar_reservations()
        self._stage085_fresh_layers={}
        for state in list(self.states.values()):
            vt=state.contract_vt_symbol
            if not vt or self.get_pos(vt) or not any(not x.entry_price_synced for x in state.layers):continue
            valid,reason=self._stage085_status(state)
            if valid:
                self.pending_active_products.add(state.product_vt_symbol)
                layer=state.layers[0]
                self._stage085_track_deferred_receipt(layer)
                self._stage085_event('preserve',vt,state,reason,volume=layer.volume,target=self.get_target(vt),
                    order_ids=[order.vt_orderid for order in self._stage085_orders(vt)],
                    receipt_json=json.dumps(asdict(layer.stage068_signal_risk_budget),sort_keys=True,allow_nan=False),
                    weekly_authorization_json=json.dumps(_plain(getattr(layer,'stage059_weekly_authorization',None)),sort_keys=True,allow_nan=False))
            else:self._stage085_cancel(vt,state,reason)
        # A target or order without its bound layer is never an authorization.
        symbols={o.vt_symbol for o in self.strategy_engine.active_limit_orders.values() if o.offset==Offset.OPEN}
        symbols.update(vt for vt,target in self.target_data.items() if target and not self.get_pos(vt))
        for vt in symbols:
            if self.get_pos(vt):continue
            state=self._find_state_by_contract(vt)
            if state is None or not self._stage085_status(state)[0]:
                self._stage085_cancel(vt,state,'orphan_open_order_or_target')
        return result

    def _plan_flat_entry_candidates(self,day_contexts):
        contexts=[context for context in day_contexts if not self._stage085_status(context.state)[0]]
        return super()._plan_flat_entry_candidates(contexts)

    def _reconcile_state_with_position(self,state,current_pos,bar):
        if current_pos==0:
            valid,reason=self._stage085_status(state)
            if valid:
                return
            vt=state.contract_vt_symbol
            if vt and (any(not x.entry_price_synced for x in state.layers) or self._stage085_orders(vt) or self.get_target(vt)):
                self._stage085_cancel(vt,state,reason)
        return super()._reconcile_state_with_position(state,current_pos,bar)

    def _close_position_when_target_unavailable(self,product_vt,*,state,target_contract,bars,reason):
        vt=state.contract_vt_symbol
        if vt and not self.get_pos(vt) and any(not x.entry_price_synced for x in state.layers):
            valid,rejection=self._stage085_status(state)
            if valid:return  # Same mapping, sparse signal data: wait with original authorization.
            self._stage085_cancel(vt,state,rejection)
            if not any(qty and self.source_symbol_by_contract.get(other)==product_vt for other,qty in self.pos_data.items()):return
        return super()._close_position_when_target_unavailable(product_vt,state=state,target_contract=target_contract,bars=bars,reason=reason)

    def _handle_rollover(self,state,target_contract,bars):
        vt=state.contract_vt_symbol
        if vt and not self.get_pos(vt) and any(not x.entry_price_synced for x in state.layers):
            self._stage085_cancel(vt,state,'unfilled_open_mapping_rollover')
            return
        return super()._handle_rollover(state,target_contract,bars)

    def _open_position(self,state,*args,**kwargs):
        if self._stage085_status(state)[0]:raise RuntimeError('stage085_cannot_overwrite_original_pending_open')
        old_layers=tuple(state.layers)
        result=super()._open_position(state,*args,**kwargs)
        if (len(state.layers)==1 and all(state.layers[0] is not old for old in old_layers)
                and not state.layers[0].entry_price_synced
                and isinstance(getattr(state.layers[0],'stage068_signal_risk_budget',None),FractionalSignalRiskReceipt)):
            if not hasattr(self,'_stage085_fresh_layers'):self._stage085_fresh_layers={}
            self._stage085_fresh_layers[state.contract_vt_symbol]=(state.layers[0],state.layers[0].stage068_signal_risk_budget)
        return result

    def rebalance_portfolio(self,bars):
        dispatch=dict(bars)
        for state in self.states.values():
            if not self._stage085_status(state)[0]:continue
            vt=state.contract_vt_symbol
            if vt not in dispatch:
                cached=getattr(self.strategy_engine,'bars',{}).get(vt)
                if cached is None:raise RuntimeError('stage085_pending_dispatch_quote_missing:'+vt)
                if pd.Timestamp(cached.datetime).date()>pd.Timestamp(self.strategy_engine.datetime).date():
                    raise RuntimeError('stage085_future_dispatch_quote:'+vt)
                dispatch[vt]=cached
                self._stage085_event('cached_order_dispatch',vt,state,'causal_cached_quote_order_only_no_execution_eligibility',
                                    order_quote=float(cached.close_price),cached_quote_datetime=str(cached.datetime))
        return super().rebalance_portfolio(dispatch)


class PendingOpenLifecycleEngineMixin:
    def cross_delayed_orders(self):
        # Witness the existing whole-order deferral decision without changing
        # the raw history map, quantity gate, or any authorization object.
        strategy=self.strategy
        for order in list(self.active_limit_orders.values()):
            if order.offset!=Offset.OPEN:continue
            raw=self.history_data.get((self.datetime,order.vt_symbol))
            if raw is not None and float(raw.volume)>=float(order.volume):continue
            state=strategy._find_state_by_contract(order.vt_symbol)
            if state is not None and strategy._stage085_status(state)[0]:
                strategy._stage085_track_deferred_receipt(state.layers[0])
        return super().cross_delayed_orders()

    def _fill_order(self,order,bar):
        if order.offset==Offset.OPEN:
            strategy=self.strategy
            state=strategy._find_state_by_contract(order.vt_symbol)
            layer=state.layers[0] if state is not None and len(state.layers)==1 else None
            receipt=getattr(layer,'stage068_signal_risk_budget',None)
            protected=(isinstance(receipt,FractionalSignalRiskReceipt)
                and getattr(strategy,'_stage085_deferred_receipts',{}).get(receipt.snapshot_id) is receipt)
            if protected:
                valid,reason=strategy._stage085_status(state)
                if not valid:
                    strategy._stage085_cancel(order.vt_symbol,state,'deferred_open_pre_fill_'+reason)
                    return
        return super()._fill_order(order,bar)

    def cancel_lifecycle_open(self,order):
        strategy=self.strategy
        state=strategy._find_state_by_contract(order.vt_symbol)
        if not strategy.get_pos(order.vt_symbol) and hasattr(strategy,'_stage085_cancel'):
            strategy._stage085_cancel(order.vt_symbol,state,'existing_lifecycle_new_open_cutoff')
            return
        return super().cancel_lifecycle_open(order)
