from __future__ import annotations

import copy
from datetime import date
from functools import lru_cache
import importlib.util
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'stages/20260906_1440_stage047_current_holding_policy_contract.md'


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('policy047_' + name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('holding_policy_nonfinite_number')
    return value


def key(row):
    day, product = row['date'], row['product_vt_symbol']
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day or not isinstance(product, str) or not product:
        raise ValueError('holding_policy_identity')
    return day, product


def validate_prediction(value, day):
    if (set(value) != {'cutoff', 'status', 'exit', 'return_marginal', 'drawdown_marginal'}
            or value['cutoff'] != day[:8] + '01' or type(value['exit']) is not bool):
        raise ValueError('holding_policy_prediction_contract')
    if value['status'] == 'untrained':
        if value['exit'] or value['return_marginal'] is not None or value['drawdown_marginal'] is not None:
            raise ValueError('holding_policy_untrained_prediction')
    elif value['status'] == 'predicted':
        return_value, drawdown_value = [finite(value[name]) for name in ('return_marginal', 'drawdown_marginal')]
        expected = return_value < 0 and drawdown_value < 0
        if value['exit'] != expected:
            raise ValueError('holding_policy_exit_threshold')
    else:
        raise ValueError('holding_policy_prediction_status')


def decision(row, book, peak, predict):
    day, product = key(row)
    observer, cost, panel = [load(name) for name in
        ('stage033_holding_observer', 'stage034_fill_inventory', 'stage040_holding_panel')]
    if row['phase'] != 'after_strategy_on_bars' or observer.classify(row) != row['state_status']:
        raise ValueError('holding_policy_state_classification')
    if cost.cost_state(row, book) != 'inventory_reconciled_holding':
        return None
    features = panel.visible_features(row, book, peak)
    prediction = predict(day, product, copy.deepcopy(features))
    validate_prediction(prediction, day)
    return copy.deepcopy({'date': day, 'product_vt_symbol': product, 'snapshot': row,
        'inventory': book, 'equity_peak': peak, 'features': features, 'prediction': prediction})


class HoldingPolicy:
    def __init__(self, guard):
        self.guard = guard
        self.states, self.decisions = [], []
        self.equity_peak, self.last_day, self.products = 150000., None, None

    def __call__(self, strategy, bars):
        observer = load('stage033_holding_observer')
        initial = observer.snapshot(strategy, bars)
        if not initial:
            return
        keys = [key(row) for row in initial]
        days, products = {day for day, _ in keys}, [product for _, product in keys]
        day = keys[0][0]
        if (len(days) != 1 or products != sorted(set(products))
                or (self.last_day is not None and day <= self.last_day)
                or (self.products is not None and products != self.products)):
            raise ValueError('holding_policy_runtime_order')
        self.last_day, self.products = day, products
        self.equity_peak = max(self.equity_peak, finite(strategy.estimated_equity))
        for product in products:
            # A previous yielded CLOSE can change the next product's visible budget state.
            current = observer.snapshot(strategy, bars)
            if [key(row) for row in current] != keys:
                raise ValueError('holding_policy_mid_bar_inventory')
            row = next(row for row in current if row['product_vt_symbol'] == product)
            if finite(row['estimated_equity']) != finite(strategy.estimated_equity):
                raise ValueError('holding_policy_budget_snapshot_mismatch')
            self.equity_peak = max(self.equity_peak, row['estimated_equity'])
            inventory = load('stage042_canonical_inventory').current_inventory(strategy)
            book = {symbol: inventory[symbol] for symbol in row['actual_positions'] if symbol in inventory}
            value = decision(row, book, self.equity_peak, self.guard.predict_holding)
            self.states.append(copy.deepcopy(row))
            if value is not None:
                self.decisions.append(value)
                if value['prediction']['exit']:
                    yield copy.deepcopy(row), copy.deepcopy(book)


def validate_transcript(states, decisions, daily_inventory, predict):
    keys = [key(row) for row in states]
    if not keys or keys != sorted(set(keys)):
        raise ValueError('holding_policy_transcript_order')
    days = sorted({day for day, _ in keys})
    if set(daily_inventory) != set(days):
        raise ValueError('holding_policy_inventory_calendar')
    products = [product for day, product in keys if day == days[0]]
    if any([product for item_day, product in keys if item_day == day] != products for day in days):
        raise ValueError('holding_policy_transcript_products')
    peak, expected, used = 150000., [], {day: set() for day in days}
    for row in states:
        day, product = key(row)
        peak = max(peak, finite(row['estimated_equity']))
        inventory = daily_inventory[day]
        symbols = set(row['actual_positions'])
        if used[day] & symbols:
            raise ValueError('holding_policy_duplicate_contract')
        used[day].update(symbols)
        book = {symbol: inventory[symbol] for symbol in symbols if symbol in inventory}
        value = decision(row, book, peak, predict)
        if value is not None:
            expected.append(value)
    if any(used[day] != set(daily_inventory[day]) for day in days):
        raise ValueError('holding_policy_inventory_coverage')
    if expected != decisions:
        raise ValueError('holding_policy_decision_transcript_mismatch')
    return {'state_count': len(states), 'decision_count': len(decisions),
            'exit_count': sum(item['prediction']['exit'] for item in decisions), 'day_count': len(days)}
