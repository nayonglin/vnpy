import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace as NS

import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage042_canonical_inventory.py'
    assert path.exists(), 'canonical inventory implementation missing'
    spec = importlib.util.spec_from_file_location('test_canonical042', path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def trade(index=1, price=352.3, volume=2, direction='LONG', offset='OPEN'):
    return NS(tradeid=str(index), vt_tradeid=f'BACKTESTING.{index}', vt_symbol='au2006.SHFE', price=price,
              volume=volume, direction=NS(name=direction), offset=NS(name=offset))


def strategy(trades, quantity):
    return NS(strategy_engine=NS(trades={t.vt_tradeid: t for t in trades}), pos_data={'au2006.SHFE': quantity})


def test_gold_matches_csv_17g_not_short_string():
    m = module(); result = m.current_inventory(strategy([trade()], 2))['au2006.SHFE']
    assert result == {'quantity': '2', 'average_entry_price': '352.30000000000001', 'source_trade_ids': ['BACKTESTING.1']}


def test_neighbouring_binary_float_not_rounded_to_same_value():
    m = module()
    a = m.current_inventory(strategy([trade()], 2))
    b = m.current_inventory(strategy([trade(price=math.nextafter(352.3, math.inf))], 2))
    assert a != b


def test_partial_close_keeps_cost_and_ids_then_full_close_clears():
    m = module(); fills = [trade(), trade(2, 355.5, 1, 'SHORT', 'CLOSE')]
    result = m.current_inventory(strategy(fills, 1))['au2006.SHFE']
    assert result['average_entry_price'] == '352.30000000000001'
    assert result['quantity'] == '1' and result['source_trade_ids'] == ['BACKTESTING.1', 'BACKTESTING.2']
    fills.append(trade(3, 353.1, 1, 'SHORT', 'CLOSE'))
    assert m.current_inventory(strategy(fills, 0)) == {}


def test_short_and_weighted_average():
    m = module(); fills = [trade(price=352.3, volume=1, direction='SHORT'), trade(2, 352.4, 1, 'SHORT')]
    result = m.current_inventory(strategy(fills, -2))['au2006.SHFE']
    assert result['quantity'] == '-2'
    assert result['average_entry_price'] == '352.349999999999995'


@pytest.mark.parametrize('fills,quantity', [([trade(index=2)],2), ([trade()],1), ([trade(volume=1.5)],1.5),
    ([trade(price=float('nan'))],2), ([trade(offset='CLOSE')],-2)])
def test_invalid_trade_or_quantity_fails(fills, quantity):
    with pytest.raises(ValueError): module().current_inventory(strategy(fills,quantity))
