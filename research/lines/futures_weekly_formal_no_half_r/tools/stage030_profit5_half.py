"""Fixed 5% PRICE-profit, once-per-native-episode half exit for Stage030.

This wraps frozen Stage029 v2. The old partial-exit dispatch slot is borrowed;
RSI flags/state, weekly technical stops and the next-bar fill engine stay intact.
"""
from decimal import Decimal
import hashlib
import math
from pathlib import Path
import pandas as pd
from stage029_week_close_exits_v2 import week_close_exit_strategy_class, audit_week_close_exits, _direction
from stage029_week_close_exits import _day


def _integer(value):
    number=float(value)
    if not math.isfinite(number) or number!=int(number):
        raise ValueError('profit_half_noninteger_volume')
    return int(number)


def _positive(value):
    number=float(value)
    if not math.isfinite(number) or number<=0:
        raise ValueError('profit_half_invalid_positive_price')
    return number


def _above(close, cost, direction):
    # Decimal(str()) preserves literal 5% equality at ordinary decimal prices.
    close,cost=Decimal(str(close)),Decimal(str(cost))
    return close>cost*Decimal('1.05') if direction=='long' else close<cost*Decimal('.95')


def profit_half_strategy_class(base, weeks, frequency, enabled=True):
    if frequency not in {'daily','weekly'}:
        raise ValueError('profit_half_frequency_must_be_daily_or_weekly')
    wrapped=week_close_exit_strategy_class(base,weeks)

    class ProfitHalfStrategy(wrapped):
        research_profit_half_enabled=bool(enabled)
        research_profit_half_frequency=frequency
        research_profit_half_threshold=.05
        research_profit_half_ratio=.5

        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.profit_half_decisions=[]
            self.profit_half_triggers=[]
            self.profit_half_episodes=[]
            self.profit_half_guard_failures=[]
            self._profit_half_episode_sequence=0
            self._profit_half_native_episodes={}

        def _profit_half_fail(self,reason,**details):
            self.profit_half_guard_failures.append(dict(reason=reason,**details))
            raise ValueError(reason+':'+str(details.get('vt_symbol','')))

        def _require_profit_half_contract(self):
            if (self.research_profit_half_enabled!=bool(enabled) or
                    self.research_profit_half_frequency!=frequency or
                    self.research_profit_half_threshold!=.05 or self.research_profit_half_ratio!=.5):
                self._profit_half_fail('profit_half_locked_contract_changed')
            self._require_week_stop_contract()

        def _open_position(self,state,contract_vt_symbol,direction,volume,bar,signal,history,
                           signal_data,sizing_snapshot=None):
            result=super()._open_position(state,contract_vt_symbol,direction,volume,bar,signal,
                history,signal_data,sizing_snapshot=sizing_snapshot)
            if self.research_profit_half_enabled and state.layers:
                self._profit_half_episode_sequence+=1
                row=dict(episode_id=self._profit_half_episode_sequence,
                    product_vt_symbol=state.product_vt_symbol,vt_symbol=str(contract_vt_symbol),
                    direction=direction,entry_signal_date=_day(state.entry_date),
                    initial_volume=_integer(state.active_volume()),done=False,basis_recorded=False,
                    inner=self.ams[str(contract_vt_symbol)].inner,state=state)
                self._profit_half_native_episodes[state.product_vt_symbol]=row
                self.profit_half_episodes.append({key:value for key,value in row.items()
                    if key not in {'inner','state','basis_recorded'}}|dict(action='created',
                    date=_day(bar.datetime),frequency=frequency,cost=None,entry_price_synced=False))
            return result

        def _process_rsi_partial_exit(self,state,bar,rsi_value):
            # The frozen loop invokes this after every prior full-stop and daily
            # safety consumer. This does not call RSI or use its done flag.
            self._require_profit_half_contract()
            if not self.research_profit_half_enabled:
                return super()._process_rsi_partial_exit(state,bar,rsi_value)
            return self._process_profit_half_exit(state,bar)

        def _profit_half_ma_stop_due(self,state,weekly,am):
            if not self.enable_ma_trend_stop:
                return False,float('nan')
            # Exactly the observed-history MA20 previous value used by the
            # frozen _generate_signal; no indicator/log/entry-filter side effects.
            history=self._build_history_df(am)
            period=_integer(self.ma_long)
            if period<=0:self._profit_half_fail('profit_half_invalid_ma_period')
            if len(history)<period+1:
                return False,float('nan')
            ma=float(pd.Series(history['close'].to_numpy(dtype='float64')).rolling(period).mean().iloc[-2])
            if not math.isfinite(ma) or ma<=0:return False,ma
            close=float(weekly.close_price)
            return (close<=ma if state.direction=='long' else close>=ma),ma

        def _process_profit_half_exit(self,state,bar):
            row=dict(date=_day(bar.datetime),signal_date=_day(bar.datetime),
                vt_symbol=str(bar.vt_symbol),product_vt_symbol=state.product_vt_symbol,
                direction=state.direction,frequency=frequency,threshold=.05,exit_ratio=.5,
                action='evaluating',episode_id=None,week_end='',fresh=False,cost=None,
                close=None,pre_volume=None,close_volume=0,remaining_volume=None,done=False)
            self.profit_half_decisions.append(row)
            guard_count=len(self.profit_half_guard_failures)
            try:
                symbol=str(state.contract_vt_symbol)
                if not state.layers:
                    if symbol and _integer(self.get_pos(symbol)):
                        self._profit_half_fail('profit_half_missing_layers',vt_symbol=symbol)
                    row['action']='no_position';return ''
                if str(bar.vt_symbol)!=symbol:
                    self._profit_half_fail('profit_half_contract_mismatch',vt_symbol=symbol)
                if state.direction not in {'long','short'}:
                    self._profit_half_fail('profit_half_unknown_direction',vt_symbol=symbol)
                episode=self._profit_half_native_episodes.get(state.product_vt_symbol)
                if (episode is None or episode['state'] is not state or episode['vt_symbol']!=symbol or
                        episode['direction']!=state.direction or episode['entry_signal_date']!=_day(state.entry_date)):
                    self._profit_half_fail('profit_half_episode_mismatch',vt_symbol=symbol)
                row.update(episode_id=episode['episode_id'],done=bool(episode['done']))
                am=self.ams.get(symbol)
                if am is None or am.inner is not episode['inner'] or _integer(am.inner.count)<=0:
                    self._profit_half_fail('profit_half_contract_epoch_mismatch',vt_symbol=symbol)
                weekly,am,context=self._completed_week_context(bar,'profit_half_basis')
                daily_close=_positive(bar.close_price)
                row.update(week_end=context['week_end'],fresh=bool(context['fresh']))
                actual=_integer(self.get_pos(symbol));volume=_integer(state.active_volume())
                if volume<=0 or abs(actual)!=volume or (actual>0)!=(state.direction=='long'):
                    self._profit_half_fail('profit_half_actual_layer_volume_mismatch',vt_symbol=symbol)
                weighted=Decimal('0');layer_basis=[]
                for layer in state.layers:
                    quantity=_integer(layer.volume)
                    if (quantity<=0 or layer.direction!=state.direction or not layer.entry_price_synced or
                            _day(layer.entry_date)!=episode['entry_signal_date']):
                        self._profit_half_fail('profit_half_unsynced_or_mismatched_layer',vt_symbol=symbol)
                    price=_positive(layer.entry_price)
                    weighted+=Decimal(str(price))*quantity
                    layer_basis.append(dict(volume=quantity,entry_price=price,direction=layer.direction,
                        entry_date=_day(layer.entry_date),entry_price_synced=bool(layer.entry_price_synced),
                        stop_price=float(layer.stop_price),highest_price=float(layer.highest_price),
                        lowest_price=float(layer.lowest_price)))
                cost=weighted/volume
                if not episode['basis_recorded']:
                    self.profit_half_episodes.append(dict(episode_id=episode['episode_id'],
                        product_vt_symbol=state.product_vt_symbol,vt_symbol=symbol,direction=state.direction,
                        entry_signal_date=episode['entry_signal_date'],date=row['date'],action='actual_basis',
                        frequency=frequency,cost=float(cost),volume=volume,entry_price_synced=True,layer_basis=layer_basis))
                    episode['basis_recorded']=True
                close=_positive(weekly.close_price) if frequency=='weekly' else daily_close
                row.update(cost=float(cost),cost_decimal=str(cost),close=close,pre_volume=volume,
                    remaining_volume=volume,layer_basis=layer_basis,price_profit_pct=float((Decimal(str(close))-cost)/cost)*
                    (1 if state.direction=='long' else -1),entry_price_synced=True)
                if episode['done']:row['action']='already_done';return ''
                if frequency=='weekly' and not context['fresh']:
                    row['action']='skip_not_fresh_week';return ''
                due,ma=self._profit_half_ma_stop_due(state,weekly,am) if context['fresh'] else (False,float('nan'))
                row['ma20_prev']=ma
                if due:row['action']='defer_ma_full_stop';return ''
                if not _above(close,cost,state.direction):row['action']='below_or_equal_threshold';return ''
                reduce=volume//2
                if reduce<=0:row['action']='one_lot_skip';return ''
                remaining=volume-reduce
                if remaining<1:self._profit_half_fail('profit_half_invalid_remainder',vt_symbol=symbol)
                reason=state.direction+'_profit5_half'
                self._record_trade_event(bar=bar,contract_vt_symbol=symbol,
                    product_vt_symbol=state.product_vt_symbol,position_direction=state.direction,
                    offset='Close',reason=reason,volume=reduce,price=close)
                self._reduce_position_to_target(state,remaining,close)
                self._apply_state_target(state)
                episode['done']=True
                row.update(action='target_generated',close_volume=reduce,remaining_volume=remaining,done=True,
                    reason=reason,target=(-remaining if state.direction=='short' else remaining))
                self.profit_half_triggers.append(dict(row))
                return reason
            except Exception as exc:
                row['action']='guard_failure';row['guard_error']=str(exc)
                if len(self.profit_half_guard_failures)==guard_count:
                    self.profit_half_guard_failures.append(dict(reason='profit_half_basis_error',
                        vt_symbol=row['vt_symbol'],date=row['date'],error=repr(exc)))
                raise

    return ProfitHalfStrategy


def _is_close(value):
    return str(getattr(value,'value',value)).lower() in {'close','offset.close','平','closetoday','closeyesterday','平今','平昨'}


def _pending_orders(strategy):
    result=[]
    active=getattr(strategy.strategy_engine,'active_limit_orders',{})
    for order in active.values():
        result.append(dict(order_id=str(order.vt_orderid),vt_symbol=str(order.vt_symbol),
            signal_date=_day(order.datetime),direction=_direction(order.direction),
            offset=str(getattr(order.offset,'value',order.offset)),volume=float(order.volume),
            traded=float(order.traded),remaining_volume=float(order.volume)-float(order.traded)))
    return result


def audit_profit_half(strategy,frames=None):
    """Check declarations, trigger math, and anchor/order/fill or terminal evidence."""
    parent=audit_week_close_exits(strategy,frames)
    strategy._require_profit_half_contract()
    if strategy.profit_half_guard_failures:raise ValueError('profit_half_guard_failures')
    frames={} if frames is None else frames
    triggers=strategy.profit_half_triggers
    seen=set();executed=0;pending=[];allocations=[]
    if triggers:
        trades,anchors=frames.get('trades'),frames.get('execution_anchor_requests')
        if (not isinstance(trades,pd.DataFrame) or not isinstance(anchors,pd.DataFrame) or
                not {'order_id','vt_symbol','direction','offset','volume'}.issubset(trades.columns) or
                not {'order_id','signal_date','vt_symbol','offset'}.issubset(anchors.columns)):
            raise ValueError('profit_half_execution_evidence_missing')
        event_frame=frames.get('trade_events')
        if not isinstance(event_frame,pd.DataFrame) or not {'date','vt_symbol','offset','direction','reason','volume','price'}.issubset(event_frame.columns):
            raise ValueError('profit_half_event_evidence_missing')
        active=_pending_orders(strategy)
        terminal=_day(strategy.current_bar_date)
        for row in triggers:
            episode=row['episode_id']
            if episode in seen:raise ValueError('profit_half_duplicate_episode_trigger')
            seen.add(episode)
            volume=_integer(row['pre_volume']);quantity=_integer(row['close_volume'])
            if (row['direction'] not in {'long','short'} or quantity!=volume//2 or quantity<1 or
                    _integer(row['remaining_volume'])!=volume-quantity or row['remaining_volume']<1 or
                    not _above(_positive(row['close']),Decimal(str(row.get('cost_decimal',row['cost']))),row['direction']) or
                    row['frequency']!=strategy.research_profit_half_frequency or not row['entry_price_synced'] or
                    row['action']!='target_generated' or not row['done'] or row['week_end']>row['date']):
                raise ValueError('profit_half_invalid_trigger_receipt')
            if row['frequency']=='weekly' and (not row['fresh'] or row['week_end']!=row['date']):
                raise ValueError('profit_half_weekly_trigger_not_fresh')
            layers=row.get('layer_basis',[])
            if not layers or sum(_integer(item['volume']) for item in layers)!=volume:
                raise ValueError('profit_half_layer_basis_evidence_missing')
            raw_cost=sum((Decimal(str(_positive(item['entry_price'])))*_integer(item['volume']) for item in layers),Decimal('0'))/volume
            if (Decimal(str(row.get('cost_decimal',row['cost'])))!=raw_cost or float(raw_cost)!=row['cost'] or
                    any(not item['entry_price_synced'] or item['direction']!=row['direction'] for item in layers)):
                raise ValueError('profit_half_layer_basis_cost_mismatch')
            events=[item for item in strategy.profit_half_decisions if item.get('episode_id')==episode and
                item.get('action')=='target_generated' and item.get('date')==row['date']]
            basis=[item for item in strategy.profit_half_episodes if item['episode_id']==episode and item['action']=='actual_basis']
            if len(events)!=1 or len(basis)!=1 or basis[0]['vt_symbol']!=row['vt_symbol']:
                raise ValueError('profit_half_episode_basis_evidence_missing')
            matched=anchors.loc[anchors['signal_date'].map(_day).eq(row['date']) &
                anchors['vt_symbol'].astype(str).eq(row['vt_symbol']) & anchors['offset'].map(_is_close)]
            expected='short' if row['direction']=='long' else 'long'
            event_matches=event_frame.loc[event_frame['date'].map(_day).eq(row['date']) &
                event_frame['vt_symbol'].astype(str).eq(row['vt_symbol']) &
                event_frame['reason'].astype(str).eq(row['reason']) & event_frame['offset'].map(_is_close)]
            if (len(event_matches)!=1 or _integer(event_matches.iloc[0]['volume'])!=quantity or
                    _direction(event_matches.iloc[0]['direction'])!=expected or
                    _positive(event_matches.iloc[0]['price'])!=row['close']):
                raise ValueError('profit_half_event_mismatch')
            same_day_closes=event_frame.loc[event_frame['date'].map(_day).eq(row['date']) &
                event_frame['vt_symbol'].astype(str).eq(row['vt_symbol']) & event_frame['offset'].map(_is_close)]
            forced=same_day_closes.loc[same_day_closes['reason'].astype(str).eq('forced_margin_deleverage')]
            if (len(same_day_closes)!=len(forced)+1 or
                    any(forced['direction'].map(_direction)!=expected) or
                    any(pd.to_numeric(forced['price'],errors='raise')!=row['close'])):
                raise ValueError('profit_half_ambiguous_same_day_close_reasons')
            forced_volume=sum(_integer(value) for value in forced['volume'])
            if any(_integer(value)<=0 for value in forced['volume']) or forced_volume>volume-quantity:
                raise ValueError('profit_half_invalid_forced_close_quantity')
            net_quantity=quantity+forced_volume
            allocation=dict(episode_id=episode,signal_date=row['date'],vt_symbol=row['vt_symbol'],
                profit_half_volume=quantity,forced_margin_deleverage_volume=forced_volume,net_close_volume=net_quantity,
                reason_volumes={row['reason']:quantity,'forced_margin_deleverage':forced_volume})
            if matched.empty:
                orders=[item for item in active if item['signal_date']==row['date'] and
                    item['vt_symbol']==row['vt_symbol'] and _is_close(item['offset']) and item['direction']==expected]
                if (row['date']!=terminal or len(orders)!=1 or orders[0]['traded']!=0 or
                        _integer(orders[0]['remaining_volume'])!=net_quantity):
                    raise ValueError('profit_half_fill_or_terminal_pending_evidence_missing')
                pending.append({**orders[0],**allocation,'status':'terminal_pending','date_end':terminal})
                allocations.append({**allocation,'status':'terminal_pending','order_ids':[orders[0]['order_id']]})
                continue
            order_ids=set(matched['order_id'].astype(str))
            fills=trades.loc[trades['order_id'].astype(str).isin(order_ids) &
                trades['vt_symbol'].astype(str).eq(row['vt_symbol']) & trades['offset'].map(_is_close)]
            if (fills.empty or any(fills['direction'].map(_direction)!=expected) or
                    sum(_integer(v) for v in fills['volume'])!=net_quantity):
                raise ValueError('profit_half_close_fill_mismatch')
            required_anchor={'trading_date','daily_open','price','source','execution_model','daily_bar_present','daily_volume'}
            if not required_anchor.issubset(matched.columns):
                raise ValueError('profit_half_anchor_source_evidence_missing')
            if 'price' not in fills:raise ValueError('profit_half_fill_price_evidence_missing')
            for record in matched.to_dict('records'):
                if (record['source']!='declared_daily_bar_open_model' or
                        record['execution_model']!='declared_daily_bar_open_model' or
                        record['daily_bar_present'] not in {True,1,'True','true'} or
                        _positive(record['daily_volume'])<=0 or
                        _positive(record['daily_open'])!=_positive(record['price'])):
                    raise ValueError('profit_half_invalid_anchor_source')
                order_fills=fills.loc[fills['order_id'].astype(str).eq(str(record['order_id']))]
                if order_fills.empty or any(pd.to_numeric(order_fills['price'],errors='raise')!=record['daily_open']):
                    raise ValueError('profit_half_anchor_fill_price_mismatch')
                if 'trading_date' not in record or _day(record['trading_date'])<=row['date']:
                    raise ValueError('profit_half_next_bar_anchor_evidence_missing')
            if 'trading_date' not in fills or any(fills['trading_date'].map(_day)<=row['date']):
                raise ValueError('profit_half_next_bar_fill_evidence_missing')
            if len(set(matched['trading_date'].map(_day)))!=1:
                raise ValueError('profit_half_multiple_execution_dates')
            if set(fills['trading_date'].map(_day))!=set(matched['trading_date'].map(_day)):
                raise ValueError('profit_half_anchor_fill_date_mismatch')
            allocations.append({**allocation,'status':'executed','order_ids':sorted(order_ids),
                'trading_date':next(iter(set(matched['trading_date'].map(_day))))})
            executed+=1
    paths=[Path(__file__),Path(__file__).with_name('test_stage030_profit5_half.py')]
    sources={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    return {**parent,'schema':'stage030_profit_half_acceptance_v1','accepted':True,
        'frequency':strategy.research_profit_half_frequency,'threshold':.05,'exit_ratio':.5,
        'threshold_comparison':'strict_gt','profit_basis':'actual_synced_native_contract_weighted_entry_price',
        'quantity_rule':'floor_half_keep_at_least_one','once_per_native_contract_round':True,
        'technical_exits_frequency':'weekly','execution_model':'declared_daily_bar_open_next_bar_v1',
        'trigger_count':len(triggers),'executed_trigger_count':executed,'filled_trigger_count':executed,
        'terminal_pending_trigger_count':len(pending),'one_lot_skipped_count':sum(
            row['action']=='one_lot_skip' for row in strategy.profit_half_decisions),
        'invariant_failures':[],'source_files_sha256':sources,'pending_orders':pending,
        'execution_allocations':allocations,
        'trade_reason_label_scope':'first_reason_only_for_net_fill_use_execution_allocations',
        'decision_count':len(strategy.profit_half_decisions),'episode_count':strategy._profit_half_episode_sequence}
