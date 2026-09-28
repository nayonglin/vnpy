from __future__ import annotations

from functools import lru_cache
import importlib.util
import math
from pathlib import Path


@lru_cache(None)
def inventory_module():
    path = Path(__file__).resolve().parent / 'stage034_fill_inventory.py'
    spec = importlib.util.spec_from_file_location('canonical042_fill_inventory', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def csv_number(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('canonical_fill_nonfinite')
    return format(value, '.17g')


def current_inventory(strategy):
    module = inventory_module(); book = {}
    trades = sorted(strategy.strategy_engine.trades.values(), key=lambda trade: int(trade.tradeid))
    if [int(trade.tradeid) for trade in trades] != list(range(1, len(trades) + 1)):
        raise ValueError('canonical_fill_sequence_incomplete')
    for trade in trades:
        if trade.vt_tradeid != f'BACKTESTING.{trade.tradeid}':
            raise ValueError('canonical_fill_gateway_identity')
        direction = trade.direction.name.lower()
        book.setdefault(trade.vt_symbol, module.Inventory()).apply({
            'trade_id': trade.vt_tradeid, 'direction': direction, 'offset': trade.offset.name.lower(),
            'price': csv_number(trade.price), 'volume': csv_number(trade.volume),
            'signed_volume': csv_number(trade.volume * (1 if direction == 'long' else -1))})
    result = {symbol: {'quantity': str(item.quantity), 'average_entry_price': str(item.average),
                      'source_trade_ids': list(item.source_ids)} for symbol, item in book.items() if item.quantity}
    actual = {symbol: module.number(csv_number(value)) for symbol, value in strategy.pos_data.items()
              if module.number(csv_number(value))}
    if actual != {symbol: module.number(item['quantity']) for symbol, item in result.items()}:
        raise ValueError('canonical_fill_actual_position_mismatch')
    return result
