import copy
import importlib.util
import math
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage040_holding_panel.py'
    assert path.exists(), 'holding panel implementation missing'
    spec = importlib.util.spec_from_file_location('panel040_test', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sample(short=False):
    sign = -1 if short else 1
    row = {'date': '2020-01-10', 'product_vt_symbol': 'jm.DCE', 'phase': 'after_strategy_on_bars',
        'actual_positions': {'jm2005.DCE': 2 * sign}, 'targets': {'jm2005.DCE': 2 * sign},
        'active_orders': [], 'pending_close_lot_count': 0, 'pending_close_reason_count': 0,
        'rollover_pending_target_contract': '', 'state_contract': 'jm2005.DCE',
        'state_direction': 'short' if short else 'long', 'state_status': 'layer_not_synchronized',
        'layers': [{'direction': 'short' if short else 'long', 'volume': 2, 'entry_price': 99,
                    'entry_price_synced': False, 'stop_price': 110 if short else 90}],
        'bars_since_entry': 2, 'estimated_equity': 150000, 'total_margin_in_use': 30000, 'loss_streak': 1,
        'bar': {'vt_symbol': 'jm2005.DCE', 'datetime': '2020-01-10T00:00:00+08:00',
                'open_price': 100, 'high_price': 110, 'low_price': 90, 'close_price': 105}}
    inventory = {'jm2005.DCE': {'quantity': str(2 * sign), 'average_entry_price': '100',
                               'source_trade_ids': ['BACKTESTING.3']}}
    return row, inventory


def test_actual_cost_not_planned_price_and_nine_features():
    m = module(); row, book = sample()
    x = m.visible_features(row, book, 160000)
    assert tuple(x) == m.FEATURES and len(x) == 9
    assert x['directional_unrealized_return'] == pytest.approx(.05)
    assert x['directional_day_return'] == pytest.approx(.05)
    assert x['directional_close_location'] == .5
    assert x['layer_stop_buffer'] == pytest.approx(15 / 105)
    assert x['log_holding_bars'] == math.log1p(2)
    assert x['portfolio_drawdown'] == -.0625
    assert x['margin_to_equity'] == .2


def test_short_direction():
    m = module(); row, book = sample(True)
    x = m.visible_features(row, book, 150000)
    assert x['directional_unrealized_return'] == pytest.approx(-.05)
    assert x['directional_close_location'] == -.5
    assert x['layer_stop_buffer'] == pytest.approx(5 / 105)


def test_future_metadata_not_a_feature():
    m = module(); row, book = sample()
    original = m.visible_features(row, book, 150000)
    row.update(end_date='2099-01-01', future_return=1e12, first_open=0, first_volume=0)
    assert m.visible_features(row, book, 150000) == original


@pytest.mark.parametrize('field,value', [('estimated_equity', 0), ('loss_streak', -1),
    ('bars_since_entry', -1), ('total_margin_in_use', float('nan'))])
def test_invalid_current_fields_fail(field, value):
    m = module(); row, book = sample(); row[field] = value
    with pytest.raises(ValueError):
        m.visible_features(row, book, 150000)


def test_wrong_day_and_unqualified_state_fail():
    m = module(); row, book = sample()
    row['bar']['datetime'] = '2020-01-13T00:00:00+08:00'
    with pytest.raises(ValueError):
        m.visible_features(row, book, 150000)
    row, book = sample(); row['active_orders'] = [{}]
    with pytest.raises(ValueError):
        m.visible_features(row, book, 150000)


def test_flat_bar_has_zero_location():
    m = module(); row, book = sample()
    row['bar'].update(open_price=100, high_price=100, low_price=100, close_price=100)
    assert m.visible_features(row, book, 150000)['directional_close_location'] == 0


def jobs():
    return [{'observation_id': 'a', 'root_id': 'r1', 'date': '2020-01-10', 'end_date': '2020-02-01', 'status': 'mature'},
            {'observation_id': 'b', 'root_id': 'r1', 'date': '2020-01-13', 'end_date': '2020-02-01', 'status': 'mature'},
            {'observation_id': 'c', 'root_id': 'r2', 'date': '2020-01-10', 'end_date': '2020-01-31', 'status': 'mature'},
            {'observation_id': 'd', 'root_id': 'r3', 'date': '2020-01-10', 'end_date': '', 'status': 'right_censored_open'}]


def test_monthly_strict_maturity_and_equal_root_mass():
    m = module()
    assert m.training_selection(jobs(), '2020-02-01') == [('c', 1.0)]
    assert m.training_selection(jobs(), '2020-03-01') == [('a', .5), ('b', .5), ('c', 1.)]


def test_duplicate_and_inconsistent_roots_fail():
    m = module(); values = jobs()
    with pytest.raises(ValueError):
        m.training_selection(values + [values[0]], '2020-03-01')
    values = copy.deepcopy(values); values[1]['end_date'] = '2020-02-02'
    with pytest.raises(ValueError):
        m.training_selection(values, '2020-03-01')


def test_utility_observation_anchor_and_account_net_costs():
    m = module()
    a = [{'date': '2020-01-10', 'account_equity': 100}, {'date': '2020-01-13', 'account_equity': 90},
         {'date': '2020-01-14', 'account_equity': 110}]
    e = [dict(row) for row in a]; e[1]['account_equity'] = 99; e[2]['account_equity'] = 105
    result = m.holding_utility(a, e, '2020-01-10', '2020-01-14', 100)
    assert result['return_marginal'] == .05
    assert result['drawdown_marginal'] == pytest.approx(-.09)
    assert result['A_max_drawdown'] == pytest.approx(-.1)
    assert result['E_max_drawdown'] == pytest.approx(-.01)
    e[0]['account_equity'] = 99
    with pytest.raises(ValueError):
        m.holding_utility(a, e, '2020-01-10', '2020-01-14', 100)


def test_utility_missing_day_or_nonpositive_equity_fail():
    m = module(); rows = [{'date': '2020-01-10', 'account_equity': 100}, {'date': '2020-01-13', 'account_equity': 90}]
    with pytest.raises(ValueError):
        m.holding_utility(rows, rows[:1], '2020-01-10', '2020-01-13', 100)
    rows[1]['account_equity'] = 0
    with pytest.raises(ValueError):
        m.holding_utility(rows, rows, '2020-01-10', '2020-01-13', 100)


def test_strategy_budget_is_not_ledger_equity_anchor():
    m = module(); row, book = sample()
    cost = {'date': row['date'], 'product_vt_symbol': row['product_vt_symbol'],
            'inventory_state_status': 'inventory_reconciled_holding', 'contract_costs': book}
    root = {'event_id': 'r1', 'status': 'mature', 'decision_date': '2020-01-08',
            'first_fill_date': '2020-01-09', 'end_date': '2020-01-20',
            'product_vt_symbol': 'jm.DCE', 'direction': 'long'}
    features, planned = m.build_panel([row], [cost], [root], [{'date': row['date'], 'account_equity': 149000}])
    assert planned[0]['account_equity'] == 149000
    assert planned[0]['snapshot']['estimated_equity'] == 150000
    assert features[0]['margin_to_equity'] == .2
