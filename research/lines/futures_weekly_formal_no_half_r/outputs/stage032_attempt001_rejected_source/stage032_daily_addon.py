"""One fixed daily addon sleeve on frozen Stage029v2; real net orders and fills.

The tagged planned layer is visible to all portfolio risk consumers. Technical
weekly consumers temporarily see base layers only. The independent fill ledger
keeps sleeve ownership after planned layers have been removed by a close signal.
"""
from contextlib import contextmanager
from copy import copy
import math
import pandas as pd
from vnpy.trader.constant import Offset, Direction
from qmt_roll_portfolio_strategy import PositionLayer
from stage029_week_close_exits_v2 import week_close_exit_strategy_class
from stage029_week_close_exits import _day
KIND='stage032_daily_addon'

def daily_addon_strategy_class(base, weeks, calendar, epoch_lookup, enabled=True):
    wrapped=week_close_exit_strategy_class(base,weeks)
    if not enabled:
        wrapped.research_daily_addon_enabled=False
        return wrapped
    dates=sorted({_day(d) for d in calendar}); previous=dict(zip(dates[1:],dates[:-1]))

    class DailyAddonStrategy(wrapped):
        research_daily_addon_enabled=True
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            for name in ('events','decisions','rounds','allocations','snapshots','guard_failures'):
                setattr(self,'daily_addon_'+name,[])
            self._daily_addon_epoch_lookup=dict(epoch_lookup)
            self._da_daily={};self._da_rounds={};self._da_active={};self._da_close_queue={}
            self._da_hidden={};self._da_rolling=False;self._da_stop_override=None
            self._da_last_processed='';self._da_closing_reason='';self._da_last_close_reason={};self._da_open_batch=None

        def _da_fail(self,reason,**kw):
            self.daily_addon_guard_failures.append(dict(reason=reason,**kw))
            raise ValueError(reason+':'+str(kw))

        def _da_event(self,action,**kw):
            row=dict(action=action,date=_day(kw.get('trading_date') or self.current_bar_date),**kw)
            self.daily_addon_events.append(row);return row

        def _da_new_round(self,state,day):
            r=dict(round_id=len(self.daily_addon_rounds)+1,product_vt_symbol=state.product_vt_symbol,
                start_date=_day(day),entry_contract=state.contract_vt_symbol,actual_add_count=0,status='active')
            self.daily_addon_rounds.append(r);self._da_rounds[state.product_vt_symbol]=r
            return r

        def _open_position(self,state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=None):
            result=super()._open_position(state,contract_vt_symbol,direction,volume,bar,signal,history,signal_data,sizing_snapshot=sizing_snapshot)
            if state.layers and direction=='long' and not self._da_rolling:
                self._da_new_round(state,bar.datetime)
            return result

        @contextmanager
        def _da_base_only(self,state):
            hidden=[l for l in state.layers if l.kind==KIND]
            if not hidden:yield;return
            symbol=state.contract_vt_symbol
            state.layers=[l for l in state.layers if l.kind!=KIND];self._da_hidden[id(state)]=hidden
            try:yield
            finally:
                hidden=self._da_hidden.pop(id(state),[])
                if state.contract_vt_symbol==symbol and state.layers:
                    state.layers.extend(l for l in hidden if all(l is not x for x in state.layers))

        def _da_restore(self,state):
            state.layers.extend(self._da_hidden.pop(id(state),[]))

        def _update_dynamic_stops(self,state,bar,history):
            with self._da_base_only(state):return super()._update_dynamic_stops(state,bar,history)
        def _process_prev2day_stop(self,state,bar,history):
            with self._da_base_only(state):return super()._process_prev2day_stop(state,bar,history)
        def _process_layer_stops(self,state,bar):
            with self._da_base_only(state):return super()._process_layer_stops(state,bar)
        def _apply_state_target(self,state,execution_price_override=None):
            # A technical partial close must retain the hidden addon in net target.
            hidden=self._da_hidden.get(id(state),[])
            if hidden:
                state.layers.extend(hidden)
                try:return super()._apply_state_target(state,execution_price_override)
                finally:state.layers=[l for l in state.layers if all(l is not x for x in hidden)]
            return super()._apply_state_target(state,execution_price_override)
        def _close_all_layers_and_set_flat_target(self,state,*args,**kwargs):
            self._da_restore(state)
            return super()._close_all_layers_and_set_flat_target(state,*args,**kwargs)
        def _close_all_layers(self,state,*args,**kwargs):
            self._da_restore(state)
            product=state.product_vt_symbol
            result=super()._close_all_layers(state,*args,**kwargs)
            if not self._da_rolling and product in self._da_rounds:
                self._da_rounds[product]['status']='parent_exit_pending'
            return result
        def _record_trade_event(self,**kw):
            if kw.get('offset')=='Close':self._da_last_close_reason[kw['contract_vt_symbol']]=kw['reason']
            return super()._record_trade_event(**kw)

        def _queue_pending_close_lot(self,symbol,layer,exit_price,volume):
            addon=self._da_active.get(symbol) if layer.kind==KIND else None
            item=dict(sleeve='daily_addon' if addon else 'base',volume=int(volume),
                entry_price=float(layer.entry_price),stop_price=float(layer.stop_price),
                round_id=addon['round_id'] if addon else 0,addon_id=addon['addon_id'] if addon else '',
                product_vt_symbol=addon['product_vt_symbol'] if addon else self._product_vt_symbol(symbol),
                reason=self._da_closing_reason or self._da_last_close_reason.get(symbol,'parent_close'))
            self._da_close_queue.setdefault(symbol,[]).append(item)
            if addon:
                if addon['status']!='active':self._da_fail('addon_close_without_active_fill',vt_symbol=symbol)
                addon['status']='pending_close';addon['close_reason']=item['reason']
                self._da_event('close_signal',**item,vt_symbol=symbol)
            return super()._queue_pending_close_lot(symbol,layer,exit_price,volume)

        def _da_close_layer(self,state,layer,price,reason):
            if not layer.entry_price_synced:
                return self._da_cancel(state.contract_vt_symbol,'cancelled_by_'+reason)
            old=self._da_closing_reason;self._da_closing_reason=reason
            try:self._queue_pending_close_lot(state.contract_vt_symbol,layer,price,layer.volume)
            finally:self._da_closing_reason=old
            self.realized_pnl+=self._layer_realized_pnl(layer,price,self.get_size(state.contract_vt_symbol))
            state.layers.remove(layer)
            # Do not feed addon outcome into parent's win/loss streak or product alpha memory.

        def _close_layers(self,state,indexes,exit_price,*,exit_reason=None,profit_giveback_context=False):
            selected=[state.layers[i] for i in indexes]
            for layer in selected:
                if layer.kind==KIND:self._da_close_layer(state,layer,exit_price,exit_reason or self._da_last_close_reason.get(state.contract_vt_symbol,'parent_exit'))
            remaining=[i for i,l in enumerate(state.layers) if any(l is x for x in selected) and l.kind!=KIND]
            if remaining:
                old=self._da_closing_reason;self._da_closing_reason=exit_reason or old
                try:return super()._close_layers(state,remaining,exit_price,exit_reason=exit_reason,profit_giveback_context=profit_giveback_context)
                finally:self._da_closing_reason=old

        def _reduce_position_to_target(self,state,target_volume,exit_price):
            reduction=state.active_volume()-target_volume
            if reduction<=0:return
            for layer in list(state.layers):
                if reduction>0 and layer.kind==KIND:
                    self._da_close_layer(state,layer,exit_price,self._da_last_close_reason.get(state.contract_vt_symbol,'safety_deleverage'))
                    reduction-=1
            if state.active_volume()>target_volume:
                return super()._reduce_position_to_target(state,target_volume,exit_price)

        def _risk_cluster_heat_deleverage_layer_kind_set(self):
            return super()._risk_cluster_heat_deleverage_layer_kind_set()|{KIND}
        def _portfolio_margin_deleverage_layer_kind_set(self):
            return super()._portfolio_margin_deleverage_layer_kind_set()|{KIND}

        def _handle_rollover(self,state,target_contract,bars):
            symbol=state.contract_vt_symbol;bar=bars.get(symbol)
            if bar is None:return super()._handle_rollover(state,target_contract,bars)
            for layer in list(state.layers):
                if layer.kind==KIND:
                    self._record_trade_event(bar=bar,contract_vt_symbol=symbol,product_vt_symbol=state.product_vt_symbol,
                        position_direction='long',offset='Close',reason='daily_addon_rollover',volume=layer.volume,price=bar.close_price)
                    self._da_close_layer(state,layer,float(bar.close_price),'rollover')
            r=self._da_rounds.get(state.product_vt_symbol)
            if r:r['up_days']=[]
            self._da_rolling=True
            try:result=super()._handle_rollover(state,target_contract,bars)
            finally:self._da_rolling=False
            if r:
                r['status']='active' if state.layers and state.direction=='long' else 'parent_exit_pending'
                r['current_contract']=state.contract_vt_symbol
                self._da_event('roll',round_id=r['round_id'],vt_symbol=symbol,target_contract=target_contract,actual_add_count=r['actual_add_count'])
            return result

        def _entry_stop_price(self,*args,**kwargs):
            if self._da_stop_override is not None:return self._da_stop_override
            return super()._entry_stop_price(*args,**kwargs)

        def _daily_addon_admission(self,state,bar,stop,price=None):
            symbol=state.contract_vt_symbol;price=float(bar.close_price if price is None else price)
            if not math.isfinite(price) or price<=stop:return dict(accepted=False,reason='open_at_or_below_stop')
            am=self.ams[symbol];history=self._build_history_df(am);sizing_bar=copy(bar);sizing_bar.close_price=price
            self._da_stop_override=float(stop)
            try:
                # The original formal sizing chain retains every active risk gate;
                # only this sleeve's stop and incremental context are supplied.
                sizing=base._calculate_entry_sizing(self,symbol,'long',sizing_bar,history,
                    {'signal':'daily_addon','risk_mode':state.risk_mode,'rsi_value':float('nan')},
                    risk_mode_override=state.risk_mode,entry_context='regular_add')
            finally:self._da_stop_override=None
            quantity=min(1,int(sizing.get('selected_volume',0)))
            heat=self._apply_risk_cluster_heat_gate_to_volume(symbol,quantity,price*self.get_size(symbol)*self._margin_ratio_for_symbol(symbol),'regular_add')
            quantity=int(heat['risk_cluster_heat_gate_selected_volume'])
            for method in ('_portfolio_drawdown_gate_adjust_volume','_portfolio_volatility_budget_adjust_volume','_portfolio_overheat_cooldown_adjust_volume'):
                quantity=getattr(self,method)(quantity,'regular_add')
            accepted=quantity==1 and self._can_allocate_margin(symbol,1,price)
            margin=price*self.get_size(symbol)*self._margin_ratio_for_symbol(symbol)
            if self.enable_forced_margin_deleverage:
                ratio=(self._reserved_margin_in_use()+margin)*float(self.forced_margin_deleverage_broker_multiplier)/max(float(self.estimated_equity),1e-9)
                if ratio>float(self.forced_margin_deleverage_trigger_ratio)+1e-12:accepted=False
                sizing['projected_forced_margin_ratio']=ratio
            return {**sizing,'accepted':accepted,'reason':'accepted' if accepted else 'budget_rejected','margin_per_contract':margin,
                'reserved_margin_before':self._reserved_margin_in_use(),'allowed_capital':self._allowed_capital(),
                'heat_margin_capacity':(self._sizing_equity()*float(self.risk_cluster_heat_gate_margin_start_ratio)-self._reserved_cluster_margin(heat['risk_cluster_heat_gate_cluster'])) if heat['risk_cluster_heat_gate_enabled'] and float(heat['risk_cluster_heat_gate_drawdown_pressure'])>0 and float(self.risk_cluster_heat_gate_weight_floor)<1 else None,
                'broker_margin_capacity':(float(self.estimated_equity)*float(self.stage830_projected_broker10_margin_to_equity_cap)/float(self.stage830_broker_margin_multiplier)-self._reserved_margin_in_use()) if getattr(self,'enable_stage830_broker10_margin_cap',False) else None,
                'incremental_margin_capacity':sizing.get('incremental_margin_budget_gate_remaining_budget') if sizing.get('incremental_margin_budget_gate_enabled') else None,
                'forced_margin_capacity':(float(self.estimated_equity)*float(self.forced_margin_deleverage_trigger_ratio)/float(self.forced_margin_deleverage_broker_multiplier)-self._reserved_margin_in_use()) if self.enable_forced_margin_deleverage else None}

        def _da_cancel(self,symbol,reason,trading_date=None):
            addon=self._da_active.get(symbol)
            if not addon or addon['status']!='pending_open':return
            state=self._find_state_by_contract(symbol)
            if state:
                state.layers=[l for l in state.layers if l.kind!=KIND];self._apply_state_target(state)
            self._da_event('cancel',vt_symbol=symbol,round_id=addon['round_id'],addon_id=addon['addon_id'],reason=reason,trading_date=trading_date or _day(self.current_bar_date))
            if self._da_open_batch:
                item=self._da_open_batch['items'].get(symbol)
                if item and item['addon_id']==addon['addon_id']:item['status']='cancelled'
            del self._da_active[symbol]

        def _da_begin_open_batch(self,day):
            day=_day(day)
            if self._da_open_batch and self._da_open_batch['date']==day:return
            items={}
            for symbol,addon in self._da_active.items():
                if addon['status']!='pending_open':continue
                items[symbol]=dict(rank=len(items),addon_id=addon['addon_id'],
                    planned=float(addon['admission'].get('margin_per_contract',0.)),
                    cluster=self._risk_cluster_for_symbol(symbol),status='pending',actual=None)
            self._da_open_batch=dict(date=day,items=items,parent_gaps={})

        def _da_record_parent_open_gap(self,order_id,cluster,delta):
            self._da_open_batch['parent_gaps'].setdefault(str(order_id),dict(cluster=cluster,delta=float(delta)))

        def _da_batch_adjustment(self,symbol,cluster_only=False):
            batch=self._da_open_batch;current=batch['items'][symbol];cluster=current['cluster']
            adjustment=0.
            for key,item in batch['items'].items():
                if cluster_only and item['cluster']!=cluster:continue
                if item['rank']>current['rank']:adjustment+=item['planned']
                if item['status']=='cancelled':adjustment-=item['planned']
                elif item['status']=='approved':adjustment+=item['actual']-item['planned']
            adjustment+=sum(x['delta'] for x in batch['parent_gaps'].values() if not cluster_only or x['cluster']==cluster)
            return adjustment

        def _daily_addon_before_fill(self,order,bar):
            addon=self._da_active.get(order.vt_symbol)
            if not addon or addon['status']!='pending_open' or order.offset!=Offset.OPEN:return True
            if int(order.volume)!=1:self._da_fail('addon_order_mixed_with_base',vt_symbol=order.vt_symbol)
            symbol=order.vt_symbol;day=_day(bar.datetime);self._da_begin_open_batch(day)
            batch_item=self._da_open_batch['items'][symbol]
            if batch_item['status']=='approved':return True
            if (previous.get(day)!=addon['signal_date'] or float(bar.volume)<=0 or
                    self._daily_addon_epoch_lookup.get((symbol,day))!=addon['epoch']):
                reason='missing_next_same_epoch_open'
            elif float(bar.open_price)<=addon['stop_price']:reason='open_at_or_below_stop'
            else:
                # Freeze all capacities at the completed signal day. Other
                # pending entries were already reserved then. Re-evaluate only
                # risk/margin at the real open, without reading future OHLC or
                # double counting this addon's own pending reservation.
                budget=addon['admission'];price=float(bar.open_price)
                prior=self._da_daily.get(symbol)
                if prior and prior['date']==addon['signal_date']:
                    held_gap=(price-float(prior['close']))*abs(int(self.get_pos(symbol)))*self.get_size(symbol)*self._margin_ratio_for_symbol(symbol)
                    self._da_record_parent_open_gap('held:'+symbol,self._risk_cluster_for_symbol(symbol),held_gap)
                risk=max((price-addon['stop_price'])*self.get_size(symbol),max(self.get_pricetick(symbol)*self.get_size(symbol),1.))
                margin=price*self.get_size(symbol)*self._margin_ratio_for_symbol(symbol)
                adjustment=self._da_batch_adjustment(symbol);cluster_adjustment=self._da_batch_adjustment(symbol,True)
                capacities=[budget.get('single_trade_capital_limit')]
                capacities.extend(float(budget[k])-adjustment for k in ('limited_balance','free_capital','forced_margin_capacity','broker_margin_capacity','incremental_margin_capacity') if budget.get(k) is not None)
                if budget.get('heat_margin_capacity') is not None:capacities.append(float(budget['heat_margin_capacity'])-cluster_adjustment)
                if budget.get('allowed_capital') is not None:
                    capacities.append(budget['allowed_capital']-budget.get('reserved_margin_before',0.)-adjustment)
                if budget.get('risk_cluster_cap_enabled'):
                    capacities.append(budget['risk_cluster_cap_amount']-budget['risk_cluster_reserved_margin_before']-cluster_adjustment)
                reason=''
                if budget.get('risk_amount') is not None and risk>float(budget['risk_amount'])+1e-9:reason='open_risk_budget_rejected'
                if any(margin>float(cap)+1e-9 for cap in capacities if cap is not None):reason='open_margin_budget_rejected'
                self.daily_addon_decisions.append(dict(date=day,vt_symbol=symbol,round_id=addon['round_id'],
                    action='open_admission',accepted=not bool(reason),reason=reason or 'accepted',price=price,
                    risk_per_contract=risk,margin_per_contract=margin,shared_budget_adjustment=adjustment,shared_cluster_adjustment=cluster_adjustment,signal_date=addon['signal_date']))
            if reason:self._da_cancel(symbol,reason,trading_date=day);return False
            batch_item.update(status='approved',actual=margin)
            return True

        def _sync_open_trade(self,trade):
            addon=self._da_active.get(trade.vt_symbol)
            if not addon or addon['status']!='pending_open':return super()._sync_open_trade(trade)
            state=self._find_state_by_contract(trade.vt_symbol)
            layers=[l for l in state.layers if l.kind==KIND and not l.entry_price_synced]
            if int(trade.volume)!=1 or len(layers)!=1:self._da_fail('addon_fill_layer_mismatch',vt_symbol=trade.vt_symbol)
            layers[0].entry_price=float(trade.price);layers[0].entry_price_synced=True
            layers[0]._stage827_signal_order_id=str(getattr(trade,'signal_order_id',trade.vt_orderid))
            addon.update(status='active',entry_price=float(trade.price),entry_date=_day(getattr(trade,'trading_date',trade.datetime)))
            r=self._da_rounds[addon['product_vt_symbol']];r['actual_add_count']+=1;r['up_days']=[]
            if r['actual_add_count']>2:self._da_fail('addon_round_count_exceeded')
            self._da_event('open_fill',vt_symbol=trade.vt_symbol,round_id=addon['round_id'],addon_id=addon['addon_id'],entry_price=float(trade.price),stop_price=addon['stop_price'],trading_date=addon['entry_date'])

        def _da_allocation(self,trade,owner,volume):
            return dict(trade_id=str(trade.vt_tradeid),order_id=str(trade.vt_orderid),vt_symbol=trade.vt_symbol,
                product_vt_symbol=owner.get('product_vt_symbol',self._product_vt_symbol(trade.vt_symbol)),
                trading_date=_day(getattr(trade,'trading_date',trade.datetime)),datetime=str(trade.datetime),
                direction='long' if trade.direction==Direction.LONG else 'short',
                offset='open' if trade.offset==Offset.OPEN else 'close',volume=int(volume),price=float(trade.price),
                sleeve=owner.get('sleeve','base'),round_id=owner.get('round_id',0),addon_id=owner.get('addon_id',''),
                reason=owner.get('reason','parent'),entry_price=float(owner.get('entry_price',trade.price)),
                stop_price=owner.get('stop_price'))

        def update_trade(self,trade):
            rows=[];addon=self._da_active.get(trade.vt_symbol)
            if trade.offset==Offset.OPEN:
                owner=dict(addon,sleeve='daily_addon',entry_price=float(trade.price),reason='daily_addon') if addon and addon['status']=='pending_open' else {}
                rows=[self._da_allocation(trade,owner,trade.volume)]
            elif trade.offset==Offset.CLOSE:
                remaining=int(trade.volume);queue=self._da_close_queue.get(trade.vt_symbol,[])
                while remaining and queue:
                    owner=queue[0];n=min(remaining,owner['volume']);rows.append(self._da_allocation(trade,owner,n))
                    owner['volume']-=n;remaining-=n
                    if not owner['volume']:queue.pop(0)
                if remaining:self._da_fail('unallocated_close_fill',vt_symbol=trade.vt_symbol,remaining=remaining)
            result=super().update_trade(trade)
            self.daily_addon_allocations.extend(rows)
            for row in rows:
                if row['sleeve']=='daily_addon' and row['offset']=='close':
                    item=self._da_active.pop(trade.vt_symbol,None)
                    if item is None:self._da_fail('addon_close_missing_owner')
                    self._da_rounds[item['product_vt_symbol']]['up_days']=[]
                    self._da_event('close_fill',**{k:v for k,v in row.items() if k!='date'})
            if trade.offset==Offset.CLOSE and int(self.get_pos(trade.vt_symbol))==0:
                product=self._product_vt_symbol(trade.vt_symbol);r=self._da_rounds.get(product)
                if r and r['status']=='parent_exit_pending':r['status']='closed'
            return result

        def _daily_addon_after_bars(self,bars):
            if not bars:return False
            day=_day(next(iter(bars.values())).datetime)
            if day==self._da_last_processed:return False
            self._da_last_processed=day;changed=False
            # Cache all actual contracts, including D0 before the base entry.
            current={}
            for symbol,b in bars.items():
                epoch=self._daily_addon_epoch_lookup.get((symbol,day))
                vals=[float(b.close_price),float(b.low_price),float(b.volume)]
                if _day(b.datetime)!=day or not epoch or not all(math.isfinite(v) and v>0 for v in vals):continue
                current[symbol]=dict(date=day,close=vals[0],low=vals[1],epoch=epoch)
            for product,state in self.states.items():
                symbol=state.contract_vt_symbol;r=self._da_rounds.get(product)
                if not state.layers or state.direction!='long':
                    if r:r['up_days']=[]
                    continue
                if r is None or r['status']=='closed':r=self._da_new_round(state,day)
                r.setdefault('up_days',[])
                if r.get('current_contract',symbol)!=symbol:r['up_days']=[]
                r['current_contract']=symbol
                actual=int(self.get_pos(symbol));addon=self._da_active.get(symbol);now=current.get(symbol);prior=self._da_daily.get(symbol)
                if addon:
                    r['up_days']=[]
                    if addon['status']=='active' and now and now['epoch']==addon['epoch'] and now['close']<addon['stop_price']:
                        layer=next((l for l in state.layers if l.kind==KIND),None)
                        if layer is None:self._da_fail('active_addon_layer_missing',vt_symbol=symbol)
                        self._record_trade_event(bar=bars[symbol],contract_vt_symbol=symbol,product_vt_symbol=product,
                            position_direction='long',offset='Close',reason='daily_addon_fixed_stop',volume=1,price=now['close'])
                        self._da_close_layer(state,layer,now['close'],'daily_addon_fixed_stop');self._apply_state_target(state);changed=True
                    continue
                # Parent must be really held and still targeted, not just planned.
                if actual<=0 or self.get_target(symbol)<actual or any(not l.entry_price_synced for l in state.layers):r['up_days']=[];continue
                continuous=bool(now and prior and previous.get(day)==prior['date'] and now['epoch']==prior['epoch'])
                if not continuous or now['close']<=prior['close']:r['up_days']=[];continue
                if r['up_days'] and previous.get(day)!=r['up_days'][-1]['date']:r['up_days']=[]
                r['up_days']=(r['up_days']+[dict(now,previous_close=prior['close'])])[-2:]
                if len(r['up_days'])<2 or r['actual_add_count']>=2:continue
                stop=min(x['low'] for x in r['up_days']);decision=self._daily_addon_admission(state,bars[symbol],stop)
                self.daily_addon_decisions.append({**decision,'date':day,'vt_symbol':symbol,'product_vt_symbol':product,'round_id':r['round_id'],
                    'signal_days':[dict(x) for x in r['up_days']],'stop_price':stop})
                if not decision['accepted']:continue
                addonid=f"{r['round_id']}:{r['actual_add_count']+1}"
                addon=dict(addon_id=addonid,round_id=r['round_id'],product_vt_symbol=product,vt_symbol=symbol,
                    status='pending_open',signal_date=day,stop_price=stop,epoch=now['epoch'],admission=dict(decision),signal_days=[dict(x) for x in r['up_days']])
                self._da_active[symbol]=addon
                state.layers.append(PositionLayer(KIND,'long',1,now['close'],stop,now['close'],now['low'],'daily_addon',day,
                    margin_ratio=self._margin_ratio_for_symbol(symbol)))
                self._reserve_intrabar_margin(symbol,1,now['close']);self._apply_state_target(state)
                self._record_trade_event(bar=bars[symbol],contract_vt_symbol=symbol,product_vt_symbol=product,
                    position_direction='long',offset='Open',reason='daily_addon',volume=1,price=now['close'])
                self._da_event('signal',**addon);changed=True
            self._da_daily.update(current)
            for product,state in self.states.items():
                symbol=state.contract_vt_symbol
                if not symbol:continue
                addon=self._da_active.get(symbol);av=int(bool(addon and addon['status'] in {'active','pending_close'}))
                actual=int(self.get_pos(symbol))
                self.daily_addon_snapshots.append(dict(date=day,product_vt_symbol=product,vt_symbol=symbol,
                    actual_position=actual,base_volume=abs(actual)-av,addon_volume=av,planned_volume=state.active_volume(),
                    target=self.get_target(symbol),addon_status=addon['status'] if addon else 'none'))
                if av and actual<av:self._da_fail('addon_actual_position_mismatch',vt_symbol=symbol)
            return changed

        def on_bars(self,bars):
            try:
                result=super().on_bars(bars)
                if self._daily_addon_after_bars(bars):self.rebalance_portfolio(bars)
                return result
            except Exception as exc:
                self.strategy_engine.intraday_execution_failure=f'{type(exc).__name__}: {exc!r}'
                raise
    return DailyAddonStrategy


def daily_addon_engine_class(base):
    class DailyAddonEngine(base):
        def _fill_order(self,order,bar):
            strategy=self.strategy
            if not getattr(strategy,'research_daily_addon_enabled',False):return super()._fill_order(order,bar)
            strategy._da_begin_open_batch(_day(bar.datetime))
            addon=strategy._da_active.get(order.vt_symbol)
            is_addon=bool(addon and addon['status']=='pending_open' and order.offset==Offset.OPEN)
            if not strategy._daily_addon_before_fill(order,bar):
                self.cancel_order(strategy,order.vt_orderid)
                return
            before=int(strategy.get_pos(order.vt_symbol))
            # Preserve ordinary base orders entirely; only their known fill
            # margin gap reduces subsequent addon admission capacity.
            planned=strategy._da_daily.get(order.vt_symbol,{}).get('close')
            if planned is None:
                state=strategy._find_state_by_contract(order.vt_symbol)
                planned=state.layers[0].entry_price if state and state.layers else float(bar.open_price)
            result=super()._fill_order(order,bar)
            after=int(strategy.get_pos(order.vt_symbol))
            if order.offset==Offset.OPEN and not is_addon and after!=before:
                delta=(float(bar.open_price)-float(planned))*abs(after-before)*strategy.get_size(order.vt_symbol)*strategy._margin_ratio_for_symbol(order.vt_symbol)
                strategy._da_record_parent_open_gap(order.vt_orderid,strategy._risk_cluster_for_symbol(order.vt_symbol),delta)
            return result
    return DailyAddonEngine


def audit_daily_addon(strategy,frames=None):
    if not getattr(strategy,'research_daily_addon_enabled',False):
        return dict(accepted=True,enabled=False,implementation='original_Stage029v2_class',actual_add_count=0)
    if strategy.daily_addon_guard_failures:raise ValueError('daily_addon_guard_failures')
    if any(r['actual_add_count']>2 for r in strategy.daily_addon_rounds):raise ValueError('daily_addon_round_count_exceeded')
    rows=strategy.daily_addon_allocations
    addon_open=[r for r in rows if r['sleeve']=='daily_addon' and r['offset']=='open']
    addon_close=[r for r in rows if r['sleeve']=='daily_addon' and r['offset']=='close']
    if any(r['volume']!=1 or r['direction']!='long' or r['price']<=r['stop_price'] for r in addon_open):raise ValueError('daily_addon_invalid_fill')
    if sum(r['actual_add_count'] for r in strategy.daily_addon_rounds)!=len(addon_open):raise ValueError('daily_addon_fill_count_mismatch')
    if frames is not None and 'trades' in frames:
        trades=frames['trades'];key='trade_id' if 'trade_id' in trades else 'vt_tradeid'
        if key not in trades:raise ValueError('daily_addon_trade_id_missing')
        quantities={}
        for r in rows:quantities[r['trade_id']]=quantities.get(r['trade_id'],0)+r['volume']
        expected={str(r[key]):int(r['volume']) for r in trades.to_dict('records')}
        if quantities!=expected:raise ValueError('daily_addon_fill_allocation_not_conserved')
    return dict(accepted=True,enabled=True,round_count=len(strategy.daily_addon_rounds),actual_add_count=len(addon_open),
        addon_close_count=len(addon_close),guard_failure_count=0,allocation_rows=len(rows),
        terminal_addons=[dict(v) for v in strategy._da_active.values()],decision_rows=len(strategy.daily_addon_decisions))
