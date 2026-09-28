import copy
from datetime import datetime
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


def module(name='stage047_current_holding_policy', folder='tools'):
    path = ROOT / folder / (name + '.py')
    assert path.exists(), 'current holding policy is not implemented'
    spec = importlib.util.spec_from_file_location('policy047_test_' + name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def sample(product='jm.DCE', day='2020-01-10'):
    row, book = module('test_stage040_holding_panel', 'tests').sample()
    symbol = product.replace('.', '2005.')
    row.update(date=day, product_vt_symbol=product, state_contract=symbol)
    row['actual_positions'] = {symbol: 2}; row['targets'] = {symbol: 2}
    row['bar'].update(vt_symbol=symbol, datetime=day + 'T00:00:00+08:00')
    return row, {symbol: next(iter(book.values()))}


def prediction(day, exit=True):
    return {'cutoff': day[:8] + '01', 'status': 'predicted', 'exit': exit,
            'return_marginal': -.1 if exit else .1, 'drawdown_marginal': -.2}


def setup(monkeypatch, rows=None):
    m = module(); row, book = sample()
    rows = rows or [row]
    observer = m.load('stage033_holding_observer')
    monkeypatch.setattr(observer, 'snapshot', lambda strategy, bars: copy.deepcopy(rows))
    canonical = m.load('stage042_canonical_inventory')
    all_books = {symbol: value for r in rows for symbol, value in sample(r['product_vt_symbol'])[1].items()
                 if symbol in r['actual_positions']}
    monkeypatch.setattr(canonical, 'current_inventory', lambda strategy: copy.deepcopy(all_books))
    guard = SimpleNamespace(predict_holding=lambda day, product, features: prediction(day))
    strategy = SimpleNamespace(estimated_equity=150000)
    return m, m.HoldingPolicy(guard), strategy, rows, all_books


def test_current_cost_nine_features_and_all_decisions(monkeypatch):
    m, policy, strategy, rows, books = setup(monkeypatch)
    result = list(policy(strategy, {}))
    assert result == [(rows[0], books)]
    item = policy.decisions[0]
    assert item['features']['directional_unrealized_return'] == pytest.approx(.05)
    assert len(item['features']) == 9 and item['equity_peak'] == 150000
    assert policy.states == rows and 'observation_id' not in item and 'root_id' not in item
    receipt = m.validate_transcript(policy.states, policy.decisions, {'2020-01-10': books}, policy.guard.predict_holding)
    assert receipt == {'state_count': 1, 'decision_count': 1, 'exit_count': 1, 'day_count': 1}


def test_refresh_after_prior_submission_changes_margin(monkeypatch):
    rows = [sample('au.SHFE')[0], sample()[0]]
    m, policy, strategy, rows, books = setup(monkeypatch, rows)
    iterator = policy(strategy, {})
    assert next(iterator)[0]['product_vt_symbol'] == 'au.SHFE'
    rows[1]['total_margin_in_use'] = 10000
    assert next(iterator)[0]['total_margin_in_use'] == 10000
    with pytest.raises(StopIteration):
        next(iterator)
    assert policy.decisions[1]['features']['margin_to_equity'] == pytest.approx(1 / 15)


def test_peak_uses_c_budget_not_ledger_or_A_peak(monkeypatch):
    m, policy, strategy, rows, books = setup(monkeypatch)
    rows[0]['estimated_equity'] = 160000; strategy.estimated_equity = 160000
    list(policy(strategy, {}))
    rows[0]['date'] = '2020-01-13'; rows[0]['bar']['datetime'] = '2020-01-13T00:00:00+08:00'
    rows[0]['estimated_equity'] = 152000; strategy.estimated_equity = 152000
    list(policy(strategy, {}))
    assert policy.decisions[-1]['features']['portfolio_drawdown'] == pytest.approx(-.05)
    m.validate_transcript(policy.states, policy.decisions,
        {'2020-01-10': books, '2020-01-13': books}, policy.guard.predict_holding)


@pytest.mark.parametrize('kind', ['flat', 'fixed_fu', 'pending', 'invalid_price', 'untrained', 'hold', 'stable'])
def test_original_eligibility_and_no_exit_states(monkeypatch, kind):
    row, book = sample('fu.SHFE' if kind == 'fixed_fu' else 'jm.DCE')
    if kind == 'flat':
        row.update(actual_positions={}, targets={}, layers=[])
    if kind == 'pending':
        row['active_orders'] = [{}]
    if kind == 'invalid_price':
        row['layers'][0]['entry_price'] = 0
    if kind == 'stable':
        row['layers'][0]['entry_price_synced'] = True
    m, policy, strategy, rows, books = setup(monkeypatch, [row])
    row['state_status'] = m.load('stage033_holding_observer').classify(row)
    if kind in {'untrained', 'hold'}:
        policy.guard.predict_holding = lambda day, product, features: (
            {'cutoff': '2020-01-01', 'status': 'untrained', 'exit': False,
             'return_marginal': None, 'drawdown_marginal': None} if kind == 'untrained' else prediction(day, False))
    result = list(policy(strategy, {}))
    assert len(result) == (1 if kind == 'stable' else 0)
    assert len(policy.decisions) == (1 if kind in {'stable', 'untrained', 'hold'} else 0)
    m.validate_transcript(policy.states, policy.decisions, {'2020-01-10': books}, policy.guard.predict_holding)


@pytest.mark.parametrize('mutation', ['duplicate_day', 'wrong_status', 'wrong_quantity', 'bad_date', 'out_of_order', 'budget_mismatch'])
def test_invalid_runtime_state_fails(monkeypatch, mutation):
    m, policy, strategy, rows, books = setup(monkeypatch)
    if mutation == 'duplicate_day':
        list(policy(strategy, {}))
    elif mutation == 'wrong_status':
        rows[0]['state_status'] = 'stable_holding'
    elif mutation == 'wrong_quantity':
        books[next(iter(books))]['quantity'] = '1'
    elif mutation == 'bad_date':
        rows[0]['date'] = '2020-1-10'
    elif mutation == 'out_of_order':
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == 'budget_mismatch':
        rows[0]['estimated_equity'] = 149999
    with pytest.raises(ValueError):
        list(policy(strategy, {}))


@pytest.mark.parametrize('field,value', [('cutoff', '2020-02-01'), ('status', 'fixed_fu'), ('exit', 1),
    ('exit', False), ('return_marginal', float('nan')), ('return_marginal', None), ('return_marginal', True)])
def test_invalid_prediction_fails(monkeypatch, field, value):
    m, policy, strategy, rows, books = setup(monkeypatch)
    policy.guard.predict_holding = lambda day, product, features: {**prediction(day), field: value}
    with pytest.raises(ValueError):
        list(policy(strategy, {}))


@pytest.mark.parametrize('mutation', ['missing_decision', 'duplicate_decision', 'wrong_feature', 'wrong_book',
    'wrong_snapshot', 'wrong_prediction', 'wrong_peak', 'missing_inventory_day', 'extra_inventory_symbol', 'missing_state'])
def test_parent_transcript_tampering_fails(monkeypatch, mutation):
    m, policy, strategy, rows, books = setup(monkeypatch)
    list(policy(strategy, {})); inventory = {'2020-01-10': books}
    if mutation == 'missing_decision': policy.decisions.clear()
    elif mutation == 'duplicate_decision': policy.decisions.append(copy.deepcopy(policy.decisions[0]))
    elif mutation == 'wrong_feature': policy.decisions[0]['features']['loss_streak'] = 99
    elif mutation == 'wrong_book': policy.decisions[0]['inventory'][next(iter(books))]['average_entry_price'] = '99'
    elif mutation == 'wrong_snapshot': policy.decisions[0]['snapshot']['loss_streak'] = 99
    elif mutation == 'wrong_prediction': policy.decisions[0]['prediction'] = prediction('2020-01-10', False)
    elif mutation == 'wrong_peak': policy.decisions[0]['equity_peak'] = 999999
    elif mutation == 'missing_inventory_day': inventory.clear()
    elif mutation == 'extra_inventory_symbol': books['unknown.DCE'] = copy.deepcopy(next(iter(books.values())))
    elif mutation == 'missing_state': policy.states.clear()
    with pytest.raises(ValueError):
        m.validate_transcript(policy.states, policy.decisions, inventory, policy.guard.predict_holding)


@pytest.mark.parametrize('quantity', [2, -3])
def test_original_gate_fill_callback_and_canonical_inventory_integration(quantity):
    from vnpy.trader.constant import Direction, Offset

    m = module(); fixture = module('test_stage039_scoped_exit', 'tests'); gate = fixture.module()
    strategy = fixture.Strategy(quantity); engine = strategy.strategy_engine
    symbol = 'jm2005.DCE'
    engine.trades['BACKTESTING.1'] = SimpleNamespace(tradeid='1', vt_tradeid='BACKTESTING.1',
        vt_symbol=symbol, direction=Direction.LONG if quantity > 0 else Direction.SHORT,
        offset=Offset.OPEN, price=100.12345678901235, volume=abs(quantity))
    calls = []
    def predict(day, product, features):
        assert strategy.calls == ['original_risk_complete']
        assert set(features) == set(m.load('stage040_holding_panel').FEATURES)
        calls.append((day, product, features))
        return prediction(day)
    policy = m.HoldingPolicy(SimpleNamespace(predict_holding=predict))
    price_calls = []
    def provider(intent, day):
        price_calls.append((intent, day))
        return {'price': 112., 'first_time': '2020-01-10T21:00:00', 'fill_date': day, 'source': 'fixture'}
    before = (fixture.Strategy.on_bars, fixture.Strategy.update_trade, fixture.Engine._resolve_trade_price)
    with gate.install_gate(fixture.Strategy, fixture.Engine, policy, provider) as audit:
        assert strategy.on_bars(engine.bars) == 'original_result'
        assert len(calls) == 1 and not price_calls and strategy.get_pos(symbol) == quantity
        assert policy.decisions[0]['inventory'][symbol]['average_entry_price'] == format(100.12345678901235, '.17g')
        order = engine.active_limit_orders['BACKTESTING.40']
        engine.datetime = datetime(2020, 1, 13)
        assert engine._resolve_trade_price(order, None)[0] == 112.
        trade = SimpleNamespace(tradeid='2', vt_tradeid='BACKTESTING.2', vt_orderid=order.vt_orderid,
            vt_symbol=symbol, direction=order.direction, offset=Offset.CLOSE,
            volume=abs(quantity), price=112., datetime=engine.datetime)
        strategy.update_trade(trade); engine.trades[trade.vt_tradeid] = trade
        engine.active_limit_orders.pop(order.vt_orderid)
        engine.bars[symbol].datetime = engine.datetime
        strategy.on_bars(engine.bars)
        assert strategy.get_pos(symbol) == 0 and m.load('stage042_canonical_inventory').current_inventory(strategy) == {}
        assert len(calls) == len(price_calls) == 1 and len(policy.states) == 2
        assert policy.states[-1]['state_status'] == 'flat'
    assert audit['unfilled_order_ids'] == [] and len(audit['fills']) == 1
    assert before == (fixture.Strategy.on_bars, fixture.Strategy.update_trade, fixture.Engine._resolve_trade_price)


def test_parent_requires_same_products_every_day(monkeypatch):
    m, policy, strategy, rows, books = setup(monkeypatch, [sample('au.SHFE')[0], sample()[0]])
    list(policy(strategy, {}))
    for row in rows:
        row['date'] = '2020-01-13'; row['bar']['datetime'] = '2020-01-13T00:00:00+08:00'
    list(policy(strategy, {}))
    policy.states.pop()
    with pytest.raises(ValueError, match='products'):
        m.validate_transcript(policy.states, policy.decisions,
            {'2020-01-10': books, '2020-01-13': books}, policy.guard.predict_holding)


def test_module_load_is_cold_bootstrap_safe():
    import subprocess
    import sys

    code = 'import runpy,sys; runpy.run_path(' + repr(str(ROOT / 'tools/stage047_current_holding_policy.py')) + '); assert not ({"numpy", "xgboost", "vnpy", "pandas"} & set(sys.modules))'
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
