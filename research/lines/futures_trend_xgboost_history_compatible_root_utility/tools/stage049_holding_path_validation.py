from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache
import importlib.util
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('validate049_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def calendar_days(values):
    values = list(values)
    if (not values or values != sorted(set(values))
            or any(not isinstance(day, str) or date.fromisoformat(day).isoformat() != day for day in values)):
        raise ValueError('holding_path_calendar')
    return values


def number(value):
    if isinstance(value, bool):
        raise ValueError('holding_path_nonfinite')
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('holding_path_nonfinite')
    return value


def indexed(rows, field):
    result = {row[field]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError('holding_path_duplicate:' + field)
    return result


def reconcile_account(daily, positions, trades, sizes):
    inventory = load('stage034_fill_inventory')
    days = calendar_days(row['date'] for row in daily)
    if any(row['date'] not in days for row in trades) or any(row['date'] > days[-1] for row in positions):
        raise ValueError('holding_path_outside_period_activity')
    records, net, quality = inventory.reconcile(trades, sorted(positions, key=lambda row: (row['date'], row['vt_symbol'])), sizes)
    if set(days) - set(net) or any(value for day, value in net.items() if day not in days):
        raise ValueError('holding_path_ledger_calendar')
    books = {day: {} for day in days}
    for item in records:
        if item['date'] not in books:
            raise ValueError('holding_path_outside_period_inventory')
        books[item['date']][item['vt_symbol']] = {key: item[key] for key in ('quantity', 'average_entry_price', 'source_trade_ids')}
    previous, max_net, max_balance = Decimal(150000), Decimal(0), Decimal(0)
    for row in daily:
        pnl, total, equity = [inventory.number(row[key]) for key in ('net_pnl', 'total_net_pnl', 'account_equity')]
        error = max(abs(net[row['date']] - pnl), abs(pnl - total))
        conservation = abs(equity - previous - total)
        if error > Decimal('0.0000001') or conservation > Decimal('0.000001'):
            raise ValueError('holding_path_account_conservation')
        max_net, max_balance, previous = max(max_net, error), max(max_balance, conservation), equity
    return books, {**quality, 'max_account_daily_error': float(max_net), 'max_equity_conservation_error': float(max_balance)}


def validate_actions(decisions, gate, trades, provider, calendar, states, terminal):
    days = calendar_days(calendar); next_day = dict(zip(days, days[1:]))
    expected = [item for item in decisions if item['prediction']['exit']]
    intents = gate['intents']; by_order = indexed(intents, 'order_id')
    fills = indexed(gate['fills'], 'order_id'); resolutions = indexed(gate['resolutions'], 'order_id')
    unfilled = gate['unfilled_order_ids']
    if (len(expected) != len(intents) or unfilled != sorted(set(unfilled))
            or set(fills) != set(resolutions) or set(fills) & set(unfilled)
            or set(fills) | set(unfilled) != set(by_order)):
        raise ValueError('holding_path_action_inventory')
    by_trade = indexed(trades, 'trade_id')
    if ({row['trade_id'] for row in trades if row.get('exit_reason') == 'research_holding_exit'}
            != {fill['trade_id'] for fill in fills.values()}):
        raise ValueError('holding_path_untracked_research_trade')
    final_rows = indexed(terminal['states'], 'product_vt_symbol')
    before = indexed([row for row in states if row['date'] == days[-1]], 'product_vt_symbol')
    if not before or set(final_rows) != set(before):
        raise ValueError('holding_path_terminal_inventory')
    observer = load('stage033_holding_observer')
    for product, row in final_rows.items():
        if (row['date'] != days[-1] or row['phase'] != 'after_strategy_on_bars'
                or row['state_status'] != observer.classify(row)
                or row['actual_positions'] != before[product]['actual_positions']):
            raise ValueError('holding_path_terminal_state')
    seen = set()
    for item, intent in zip(expected, intents):
        key = item['date'], item['product_vt_symbol']
        snapshot = item['snapshot']; symbol, position = next(iter(snapshot['actual_positions'].items()))
        position = number(position); volume = abs(position)
        direction = 'SHORT' if position > 0 else 'LONG'
        if (key in seen or key[0] not in days or key[1] == 'fu.SHFE' or not volume or not volume.is_integer()
                or (intent['decision_date'], intent['product_vt_symbol']) != key
                or intent['vt_symbol'] != symbol or number(intent['position_before']) != position
                or number(intent['volume']) != volume or number(intent['order_price']) <= 0
                or intent['direction'] != direction or intent['inventory'] != item['inventory']
                or intent['submitted_without_fill'] is not True):
            raise ValueError('holding_path_intent_prediction_mismatch')
        seen.add(key); order = intent['order_id']
        matches = [row for row in trades if row['order_id'] == order]
        if order in unfilled:
            row = final_rows[key[1]]
            active = [value for value in row['active_orders'] if value['order_id'] == order]
            if (key[0] != days[-1] or matches or len(active) != 1 or row['targets']
                    or row['actual_positions'] != {symbol: position}
                    or row['pending_close_lot_count'] < 1 or row['pending_close_reason_count'] < 1
                    or number(terminal['pending_close_volumes'].get(symbol, 0)) != volume):
                raise ValueError('holding_path_unfilled_not_terminal')
            pending = active[0]
            if (pending['vt_symbol'] != symbol or number(pending['volume']) != volume
                    or number(pending['traded']) != 0 or number(pending['price']) != number(intent['order_price'])
                    or pending['direction'] != 'Direction.' + direction or pending['offset'] != 'Offset.CLOSE'):
                raise ValueError('holding_path_terminal_order_changed')
            continue
        fill = fills[order]
        if (len(matches) != 1 or fill['trade_id'] not in by_trade or matches[0] != by_trade[fill['trade_id']]
                or next_day.get(key[0]) != fill['fill_date'] or number(fill['position_after']) != 0
                or number(fill['volume']) != volume or number(fill['cost']) < 0):
            raise ValueError('holding_path_fill_inventory')
        quote = provider(intent, fill['fill_date'])
        if resolutions[order] != {'order_id': order, **quote} or number(fill['price']) != number(quote['price']):
            raise ValueError('holding_path_price_recalculation')
        trade = matches[0]
        expected_direction = {'SHORT': {'short', '\u7a7a'}, 'LONG': {'long', '\u591a'}}[direction]
        if (trade['vt_symbol'] != symbol or trade['date'] != fill['fill_date'] or trade['datetime'][:10] != fill['fill_date']
                or trade['offset'] not in {'close', '\u5e73'} or trade['direction'] not in expected_direction
                or trade['gateway_name'] != 'BACKTESTING' or trade.get('exit_reason') != 'research_holding_exit'
                or number(trade['volume']) != volume or number(trade['signed_volume']) != -position
                or number(trade['price']) != number(quote['price'])):
            raise ValueError('holding_path_actual_close_mismatch')
    return {'exit_count': len(intents), 'filled_exit_count': len(fills), 'terminal_unfilled_count': len(unfilled),
            'first_exit_date': expected[0]['date'] if expected else None}
