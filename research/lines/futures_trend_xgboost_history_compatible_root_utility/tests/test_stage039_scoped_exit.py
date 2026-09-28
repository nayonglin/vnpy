import copy
from datetime import datetime
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from vnpy.trader.constant import Direction, Offset


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage039_scoped_exit.py'


def module():
    assert TOOL.exists(), 'scoped exit implementation missing'
    spec = importlib.util.spec_from_file_location('test_exit039', TOOL)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Engine:
    gateway_name = 'BACKTESTING'

    def __init__(self):
        self.datetime = datetime(2020, 1, 10)
        self.active_limit_orders = {}
        self.trades = {}
        self.bars = {}
        self.trade_count = 0

    def _resolve_trade_price(self, order, bar):
        return 999., 'original', {}


class Strategy:
    def __init__(self, quantity=2):
        self.strategy_engine = Engine()
        self.strategy_engine.strategy = self
        symbol = 'jm2005.DCE'
        direction = 'long' if quantity > 0 else 'short'
        self.trading = True
        self.pos_data = {symbol: quantity}
        self.target_data = {symbol: quantity}
        self.source_symbol_by_contract = {symbol: 'jm.DCE', 'rb2005.SHFE': 'rb.SHFE'}
        layer = NS(kind='base', direction=direction, volume=abs(quantity), entry_price=100., stop_price=95.,
                   highest_price=110., lowest_price=95., entry_date='20200109', max_profit_pct=0.,
                   entry_price_synced=False, profit_giveback_stop_active=False)
        self.states = {'jm.DCE': NS(contract_vt_symbol=symbol, direction=direction, layers=[layer], entry_date='20200109',
                       bars_since_entry=1, prev2day_stop_price=95., rollover_pending_target_contract='', rsi_partial_exit_done=False)}
        self.pending_close_lots = {}
        self.pending_close_reasons = {}
        self.estimated_equity = self.settled_balance = 150000.
        self.total_margin_in_use = 1000.
        self.loss_streak = 0
        self.execution_price_overrides = {}
        self.calls = []
        bar = NS(datetime=self.strategy_engine.datetime, interval='Interval.DAILY', open_price=101.,
                 high_price=111., low_price=99., close_price=110., volume=100., open_interest=1000.)
        self.strategy_engine.bars[symbol] = bar

    def on_bars(self, bars):
        self.calls.append('original_risk_complete')
        return 'original_result'

    def get_pos(self, symbol):
        return self.pos_data.get(symbol, 0)

    def get_target(self, symbol):
        return self.target_data.get(symbol, 0)

    def calculate_price(self, symbol, direction, reference):
        return reference

    def _close_all_layers_and_set_flat_target(self, state, price, exit_reason):
        symbol = state.contract_vt_symbol
        self.pending_close_lots[symbol] = [{'volume': x.volume} for x in state.layers]
        self.pending_close_reasons[symbol] = [{'volume': sum(x.volume for x in state.layers), 'reason': exit_reason}]
        state.layers = []
        state.contract_vt_symbol = ''
        state.direction = ''
        self.target_data[symbol] = 0

    def sell(self, symbol, price, volume):
        return self.send(symbol, Direction.SHORT, price, volume)

    def cover(self, symbol, price, volume):
        return self.send(symbol, Direction.LONG, price, volume)

    def send(self, symbol, direction, price, volume):
        key = 'BACKTESTING.40'
        self.strategy_engine.active_limit_orders[key] = NS(vt_orderid=key, vt_symbol=symbol, direction=direction,
            offset=Offset.CLOSE, status='SUBMITTING', datetime=self.strategy_engine.datetime, price=price, volume=volume, traded=0)
        return [key]

    def update_trade(self, trade):
        self.calls.append('original_update_trade')
        self.pos_data[trade.vt_symbol] += trade.volume * (1 if trade.direction == Direction.LONG else -1)
        self.pending_close_lots.pop(trade.vt_symbol)
        self.pending_close_reasons.pop(trade.vt_symbol)

    def _trade_cost(self, trade):
        return trade.volume * 10.

    def rebalance_portfolio(self, bars):
        raise AssertionError('must not rebalance')


def prepared(m, quantity=2):
    strategy = Strategy(quantity)
    row = m.observer().snapshot(strategy, strategy.strategy_engine.bars)[0]
    inventory = {'jm2005.DCE': {'quantity': str(quantity), 'average_entry_price': '100', 'source_trade_ids': ['BACKTESTING.1']}}
    return strategy, row, inventory


@pytest.mark.parametrize('quantity,direction', [(2, Direction.SHORT), (-3, Direction.LONG)])
def test_submit_only_reduces_target_not_actual_position_or_equity(quantity, direction):
    m = module(); strategy, row, inventory = prepared(m, quantity)
    old_position = dict(strategy.pos_data)
    intent = m.submit_exit(strategy, row, inventory)
    order = strategy.strategy_engine.active_limit_orders[intent['order_id']]
    assert order.offset == Offset.CLOSE and order.direction == direction and order.volume == abs(quantity)
    assert strategy.get_target(row['state_contract']) == 0
    assert strategy.pos_data == old_position and strategy.settled_balance == strategy.estimated_equity == 150000.


def test_other_product_order_is_preserved():
    m = module(); strategy, row, inventory = prepared(m)
    other = NS(vt_symbol='rb2005.SHFE', price=555.)
    strategy.strategy_engine.active_limit_orders['BACKTESTING.7'] = other
    m.submit_exit(strategy, row, inventory)
    assert strategy.strategy_engine.active_limit_orders['BACKTESTING.7'] is other and other.price == 555.


@pytest.mark.parametrize('field,value', [('state_status', 'pending_orders_or_close_inventory'),
                                      ('product_vt_symbol', 'fu.SHFE'), ('date', '2020-01-09')])
def test_unqualified_or_stale_observation_is_rejected(field, value):
    m = module(); strategy, row, inventory = prepared(m); row[field] = value
    with pytest.raises(ValueError):
        m.submit_exit(strategy, row, inventory)
    assert not strategy.strategy_engine.active_limit_orders and strategy.get_target('jm2005.DCE') == 2


def test_cost_inventory_mismatch_is_rejected_before_mutation():
    m = module(); strategy, row, inventory = prepared(m); inventory['jm2005.DCE']['quantity'] = '3'
    with pytest.raises(ValueError):
        m.submit_exit(strategy, row, inventory)
    assert strategy.states['jm.DCE'].layers


def test_live_gateway_is_not_allowed():
    m = module(); strategy, row, inventory = prepared(m); strategy.strategy_engine.gateway_name = 'CTP'
    with pytest.raises(ValueError, match='research_engine'):
        m.submit_exit(strategy, row, inventory)


def test_second_submission_cannot_duplicate_close():
    m = module(); strategy, row, inventory = prepared(m); m.submit_exit(strategy, row, inventory)
    with pytest.raises(ValueError):
        m.submit_exit(strategy, row, inventory)
    assert len(strategy.strategy_engine.active_limit_orders) == 1


def test_disabled_gate_delegates_and_restores_inherited_methods():
    m = module()
    class Child(Strategy):
        pass
    class ChildEngine(Engine):
        pass
    strategy = Child(); strategy.strategy_engine = ChildEngine(); strategy.strategy_engine.strategy = strategy
    with m.install_gate(Child, ChildEngine, None, lambda *_: pytest.fail('future source queried')) as audit:
        assert strategy.on_bars({}) == 'original_result'
        assert strategy.strategy_engine._resolve_trade_price(NS(vt_orderid='original'), None) == (999., 'original', {})
        assert audit['intents'] == [] and audit['fills'] == []
    assert 'on_bars' not in Child.__dict__ and 'update_trade' not in Child.__dict__
    assert '_resolve_trade_price' not in ChildEngine.__dict__


def test_future_price_only_read_during_fill_and_original_callback_owns_position():
    m = module(); strategy, row, inventory = prepared(m); queried = []
    def choose(self, bars):
        assert self.calls == ['original_risk_complete']
        return [(row, inventory)]
    def price(intent, day):
        queried.append(day)
        return {'price': 112., 'first_time': '2020-01-10T21:00:00', 'fill_date': '2020-01-13', 'source': 'fixture'}
    with m.install_gate(Strategy, Engine, choose, price) as audit:
        strategy.on_bars(strategy.strategy_engine.bars)
        assert queried == [] and strategy.get_pos('jm2005.DCE') == 2
        order = strategy.strategy_engine.active_limit_orders['BACKTESTING.40']
        strategy.strategy_engine.datetime = datetime(2020, 1, 13)
        resolved = strategy.strategy_engine._resolve_trade_price(order, None)
        assert resolved[0] == 112. and len(queried) == 1
        trade = NS(vt_orderid=order.vt_orderid, vt_tradeid='BACKTESTING.4', vt_symbol=order.vt_symbol,
                   volume=2, direction=Direction.SHORT, offset=Offset.CLOSE, price=112., datetime=datetime(2020, 1, 13))
        strategy.update_trade(trade)
        assert strategy.get_pos('jm2005.DCE') == 0 and strategy.calls[-1] == 'original_update_trade'
        assert len(audit['fills']) == 1 and audit['fills'][0]['cost'] == 20.
        with pytest.raises(ValueError, match='duplicate'):
            strategy.update_trade(trade)


@pytest.mark.parametrize('case', ['same_day', 'wrong_offset', 'partial'])
def test_invalid_fill_is_rejected_before_original_callback(case):
    m = module(); strategy, row, inventory = prepared(m)
    provider = lambda *_: {'price': 112., 'first_time': '2020-01-10T21:00:00', 'fill_date': '2020-01-13', 'source': 'fixture'}
    with m.install_gate(Strategy, Engine, lambda *_: [(row, inventory)], provider):
        strategy.on_bars(strategy.strategy_engine.bars)
        order = strategy.strategy_engine.active_limit_orders['BACKTESTING.40']
        strategy.strategy_engine.datetime = datetime(2020, 1, 13)
        if case == 'same_day':
            strategy.strategy_engine.datetime = datetime(2020, 1, 10)
            with pytest.raises(ValueError): strategy.strategy_engine._resolve_trade_price(order, None)
        else:
            strategy.strategy_engine._resolve_trade_price(order, None)
            trade = NS(vt_orderid=order.vt_orderid, vt_tradeid='BACKTESTING.4', vt_symbol=order.vt_symbol,
                       volume=1 if case == 'partial' else 2, direction=Direction.SHORT,
                       offset=Offset.OPEN if case == 'wrong_offset' else Offset.CLOSE, price=112., datetime=datetime(2020, 1, 13))
            with pytest.raises(ValueError): strategy.update_trade(trade)
        assert strategy.get_pos('jm2005.DCE') == 2 and 'original_update_trade' not in strategy.calls
