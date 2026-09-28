from __future__ import annotations

import copy
from contextlib import contextmanager
from datetime import datetime, time
import importlib.util
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REASON = 'research_holding_exit'


def load(name):
    spec = importlib.util.spec_from_file_location('exit039_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def observer():
    return load('stage033_holding_observer')


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('exit_nonfinite')
    return result


def pending_volume(strategy, symbol):
    return sum(number(item['volume']) for item in strategy.pending_close_lots.get(symbol, []))


def current_inventory(strategy):
    inventory = load('stage034_fill_inventory')
    book = {}
    trades = sorted(strategy.strategy_engine.trades.values(), key=lambda item: int(item.tradeid))
    if [int(trade.tradeid) for trade in trades] != list(range(1, len(trades) + 1)):
        raise ValueError('exit_trade_sequence_incomplete')
    for trade in trades:
        direction = trade.direction.name.lower()
        book.setdefault(trade.vt_symbol, inventory.Inventory()).apply({
            'direction': direction, 'offset': trade.offset.name.lower(), 'price': trade.price,
            'volume': trade.volume, 'signed_volume': trade.volume * (1 if direction == 'long' else -1),
            'trade_id': trade.vt_tradeid})
    result = {symbol: {'quantity': str(item.quantity), 'average_entry_price': str(item.average),
                      'source_trade_ids': list(item.source_ids)} for symbol, item in book.items() if item.quantity}
    actual = {symbol: number(value) for symbol, value in strategy.pos_data.items() if number(value)}
    if actual != {symbol: number(item['quantity']) for symbol, item in result.items()}:
        raise ValueError('exit_inventory_actual_mismatch')
    return result


def submit_exit(strategy, row, inventory):
    from vnpy.trader.constant import Direction, Offset

    engine = strategy.strategy_engine
    if engine.gateway_name != 'BACKTESTING' or not strategy.trading:
        raise ValueError('exit_requires_research_engine')
    source = observer()
    if row['state_status'] != source.classify(row):
        raise ValueError('exit_observation_classification_mismatch')
    current = [item for item in source.snapshot(strategy, engine.bars)
               if item['product_vt_symbol'] == row['product_vt_symbol']]
    if len(current) != 1 or current[0] != row:
        raise ValueError('exit_stale_observation')
    if load('stage034_fill_inventory').cost_state(row, inventory) != 'inventory_reconciled_holding':
        raise ValueError('exit_unqualified_holding')
    symbol, quantity = next(iter(row['actual_positions'].items()))
    quantity = number(quantity)
    if not quantity or not quantity.is_integer():
        raise ValueError('exit_invalid_quantity')
    direction = Direction.SHORT if quantity > 0 else Direction.LONG
    reference = number(row['bar']['close_price'])
    order_price = number(strategy.calculate_price(symbol, direction, reference))
    if reference <= 0 or order_price <= 0:
        raise ValueError('exit_invalid_order_price')
    orders_before = {key: (order, copy.deepcopy(vars(order))) for key, order in engine.active_limit_orders.items()}
    actual_before = dict(strategy.pos_data)
    balance_before = (strategy.settled_balance, strategy.estimated_equity)
    strategy._close_all_layers_and_set_flat_target(strategy.states[row['product_vt_symbol']], reference, exit_reason=REASON)
    ids = (strategy.sell if quantity > 0 else strategy.cover)(symbol, order_price, abs(quantity))
    if not isinstance(ids, list) or len(ids) != 1 or ids[0] in orders_before:
        raise ValueError('exit_expected_one_new_order')
    order = engine.active_limit_orders.get(ids[0])
    if (order is None or order.vt_symbol != symbol or order.direction != direction or order.offset != Offset.CLOSE
            or number(order.volume) != abs(quantity) or number(order.traded) != 0
            or strategy.get_target(symbol) != 0 or pending_volume(strategy, symbol) != abs(quantity)):
        raise ValueError('exit_submitted_order_mismatch')
    if set(engine.active_limit_orders) != set(orders_before) | set(ids):
        raise ValueError('exit_other_orders_changed')
    for key, (original, values) in orders_before.items():
        if engine.active_limit_orders[key] is not original or vars(original) != values:
            raise ValueError('exit_other_orders_changed')
    if dict(strategy.pos_data) != actual_before or balance_before != (strategy.settled_balance, strategy.estimated_equity):
        raise ValueError('exit_submission_changed_actual_account')
    return {'order_id': ids[0], 'decision_date': row['date'], 'product_vt_symbol': row['product_vt_symbol'],
            'vt_symbol': symbol, 'position_before': quantity, 'volume': abs(quantity), 'order_price': order_price,
            'direction': direction.name, 'other_order_ids': list(orders_before),
            'inventory': copy.deepcopy(inventory), 'submitted_without_fill': True}


def validate_close(strategy, order, intent):
    from vnpy.trader.constant import Offset

    symbol = intent['vt_symbol']
    if (order.vt_symbol != symbol or order.offset != Offset.CLOSE or order.direction.name != intent['direction']
            or number(order.volume) != intent['volume'] or strategy.get_pos(symbol) != intent['position_before']
            or strategy.get_target(symbol) != 0 or pending_volume(strategy, symbol) != intent['volume']):
        raise ValueError('exit_fill_state_mismatch_or_partial')


@contextmanager
def install_gate(strategy_class, engine_class, selector, price_provider):
    names = [(strategy_class, 'on_bars'), (strategy_class, 'update_trade'), (engine_class, '_resolve_trade_price')]
    missing = object()
    local = [(cls, name, cls.__dict__.get(name, missing)) for cls, name in names]
    original_bars, original_trade, original_price = [getattr(cls, name) for cls, name in names]
    audit = {'intents': [], 'fills': [], 'resolutions': []}
    intents, resolved, completed = {}, {}, set()

    def on_bars(self, bars):
        result = original_bars(self, bars)
        if selector is not None:
            for row, inventory in selector(self, bars):
                intent = submit_exit(self, row, inventory)
                if intent['order_id'] in intents:
                    raise ValueError('exit_duplicate_intent')
                intents[intent['order_id']] = intent
                audit['intents'].append(intent)
        return result

    def price(self, order, bar):
        key = order.vt_orderid
        if key not in intents:
            return original_price(self, order, bar)
        if key in resolved:
            raise ValueError('exit_duplicate_resolution')
        intent = intents[key]
        validate_close(self.strategy, order, intent)
        fill_date = self.datetime.strftime('%Y-%m-%d')
        if fill_date <= intent['decision_date']:
            raise ValueError('exit_same_day_fill')
        value = price_provider(copy.deepcopy(intent), fill_date)
        first = datetime.fromisoformat(value['first_time']).replace(tzinfo=None)
        lower = datetime.combine(datetime.fromisoformat(intent['decision_date']).date(), time(15))
        if (value['fill_date'] != fill_date or first <= lower or first.date() > self.datetime.date()
                or number(value['price']) <= 0 or not value['source']):
            raise ValueError('exit_execution_source_invalid')
        resolved[key] = dict(value)
        audit['resolutions'].append({'order_id': key, **value})
        return number(value['price']), 'research_holding_exit_' + value['source'], {
            'proxy_price': number(value['price']), 'proxy_first_time': value['first_time'],
            'proxy_last_time': value['first_time'], 'proxy_bar_count': 1}

    def update_trade(self, trade):
        key = trade.vt_orderid
        if key not in intents:
            return original_trade(self, trade)
        if key in completed:
            raise ValueError('exit_duplicate_fill')
        intent = intents[key]
        validate_close(self, trade, intent)
        value = resolved.get(key)
        if (value is None or number(trade.price) != number(value['price'])
                or trade.datetime.strftime('%Y-%m-%d') != value['fill_date']):
            raise ValueError('exit_fill_without_matching_resolution')
        result = original_trade(self, trade)
        if self.get_pos(intent['vt_symbol']) != 0 or pending_volume(self, intent['vt_symbol']) != 0:
            raise ValueError('exit_callback_inventory_not_flat')
        if self.pending_close_reasons.get(intent['vt_symbol']):
            raise ValueError('exit_callback_reason_not_consumed')
        completed.add(key)
        audit['fills'].append({'order_id': key, 'trade_id': trade.vt_tradeid, 'fill_date': value['fill_date'],
                              'price': number(trade.price), 'volume': number(trade.volume),
                              'cost': number(self._trade_cost(trade)), 'position_after': self.get_pos(intent['vt_symbol'])})
        return result

    strategy_class.on_bars = on_bars
    strategy_class.update_trade = update_trade
    engine_class._resolve_trade_price = price
    try:
        yield audit
    finally:
        audit['unfilled_order_ids'] = sorted(set(intents) - completed)
        for cls, name, value in reversed(local):
            if value is missing:
                delattr(cls, name)
            else:
                setattr(cls, name, value)
