import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DAYS = ['2020-01-02', '2020-01-03']
SYMBOL, PRODUCT = 'jm2005.DCE', 'jm.DCE'


def module(name='stage049_holding_path_validation', folder='tools'):
    path = ROOT / folder / (name + '.py')
    assert path.exists(), 'full holding validation is not implemented'
    spec = importlib.util.spec_from_file_location('validation049_test_' + name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def sample():
    row, book = module('test_stage047_current_holding_policy', 'tests').sample(day=DAYS[0])
    book[SYMBOL]['source_trade_ids'] = ['BACKTESTING.1']
    return row, book


def pred(day, product, features):
    return {'cutoff': '2020-01-01', 'status': 'predicted', 'exit': True,
            'return_marginal': -.1, 'drawdown_marginal': -.1}


def fixture(terminal=False):
    row, book = sample()
    policy = module('stage047_current_holding_policy')
    decision = policy.decision(row, book, 150000., pred)
    intent = {'order_id': 'BACKTESTING.2', 'decision_date': DAYS[0], 'product_vt_symbol': PRODUCT,
        'vt_symbol': SYMBOL, 'position_before': 2., 'volume': 2., 'order_price': 105., 'direction': 'SHORT',
        'other_order_ids': [], 'inventory': copy.deepcopy(book), 'submitted_without_fill': True}
    def provider(intent, day):
        return {'price': 108., 'first_time': DAYS[0] + 'T21:00:00', 'fill_date': day,
                'source': 'stage046_dynamic_full_minute',
                'qualification': {'status': 'source_proxy_qualified_not_execution'}}
    fill = {'order_id': intent['order_id'], 'trade_id': 'BACKTESTING.2', 'fill_date': DAYS[1],
            'price': 108., 'volume': 2., 'cost': 20., 'position_after': 0.}
    trade = {'trade_id': 'BACKTESTING.2', 'order_id': intent['order_id'], 'vt_symbol': SYMBOL,
        'date': DAYS[1], 'datetime': DAYS[1] + ' 00:00:00+08:00', 'price': '108', 'volume': '2',
        'signed_volume': '-2', 'direction': '\u7a7a', 'offset': '\u5e73', 'gateway_name': 'BACKTESTING',
        'exit_reason': 'research_holding_exit'}
    final = copy.deepcopy(row)
    final.update(targets={}, layers=[], state_contract='', state_direction='', active_orders=[])
    gate = {'intents': [intent], 'fills': [], 'resolutions': [], 'unfilled_order_ids': [intent['order_id']]}
    if terminal:
        final.update(pending_close_lot_count=1, pending_close_reason_count=1)
        final['active_orders'] = [{'order_id': intent['order_id'], 'vt_symbol': SYMBOL, 'volume': 2.,
            'traded': 0., 'price': 105., 'direction': 'Direction.SHORT', 'offset': 'Offset.CLOSE'}]
        states, trades, days = [row], [], DAYS[:1]
        pending = {SYMBOL: 2.}
    else:
        final.update(date=DAYS[1], actual_positions={}, estimated_equity=150120.)
        final['bar']['datetime'] = DAYS[1] + 'T00:00:00+08:00'
        gate.update(fills=[fill], resolutions=[{'order_id': intent['order_id'], **provider(intent, DAYS[1])}],
                    unfilled_order_ids=[])
        states, trades, days, pending = [row, final], [trade], DAYS, {}
    final['state_status'] = policy.load('stage033_holding_observer').classify(final)
    terminal_state = {'states': [copy.deepcopy(final)], 'pending_close_volumes': pending}
    return [decision], gate, trades, provider, days, states, terminal_state


def test_fill_audit_binds_predictions_actual_close_and_independent_price():
    m = module(); values = fixture(); result = m.validate_actions(*values)
    assert result == {'exit_count': 1, 'filled_exit_count': 1, 'terminal_unfilled_count': 0,
        'first_exit_date': DAYS[0]}


def test_terminal_order_is_unfilled_not_forced_or_silently_skipped():
    m = module(); decisions, gate, trades, provider, days, states, terminal = fixture(True)
    def forbidden(*args):
        pytest.fail('terminal unfilled order must not read a future execution price')
    result = m.validate_actions(decisions, gate, trades, forbidden, days, states, terminal)
    assert result['terminal_unfilled_count'] == 1 and result['filled_exit_count'] == 0


@pytest.mark.parametrize('mutation', ['missing_intent', 'duplicate_intent', 'missing_fill', 'duplicate_fill',
    'missing_resolution', 'wrong_price', 'wrong_volume', 'wrong_direction', 'wrong_offset', 'wrong_reason',
    'late_fill', 'wrong_inventory', 'wrong_decision_day', 'not_an_exit', 'untracked_research_trade',
    'nonzero_position_after', 'nonfinite_cost', 'wrong_gateway', 'extra_trade_same_order'])
def test_corrupt_actual_action_is_rejected(mutation):
    m = module(); decisions, gate, trades, provider, days, states, terminal = fixture()
    if mutation == 'missing_intent': gate['intents'].clear()
    elif mutation == 'duplicate_intent': gate['intents'].append(copy.deepcopy(gate['intents'][0]))
    elif mutation == 'missing_fill': gate['fills'].clear()
    elif mutation == 'duplicate_fill': gate['fills'].append(copy.deepcopy(gate['fills'][0]))
    elif mutation == 'missing_resolution': gate['resolutions'].clear()
    elif mutation == 'wrong_price': trades[0]['price'] = '109'
    elif mutation == 'wrong_volume': trades[0]['volume'] = '1'
    elif mutation == 'wrong_direction': trades[0]['direction'] = '\u591a'
    elif mutation == 'wrong_offset': trades[0]['offset'] = '\u5f00'
    elif mutation == 'wrong_reason': trades[0]['exit_reason'] = ''
    elif mutation == 'late_fill': gate['fills'][0]['fill_date'] = '2020-01-06'
    elif mutation == 'wrong_inventory': gate['intents'][0]['inventory'][SYMBOL]['average_entry_price'] = '99'
    elif mutation == 'wrong_decision_day': gate['intents'][0]['decision_date'] = DAYS[1]
    elif mutation == 'not_an_exit': decisions[0]['prediction']['exit'] = False
    elif mutation == 'untracked_research_trade': trades.append({**trades[0], 'trade_id': 'BACKTESTING.3', 'order_id': 'BACKTESTING.3'})
    elif mutation == 'nonzero_position_after': gate['fills'][0]['position_after'] = 1.
    elif mutation == 'nonfinite_cost': gate['fills'][0]['cost'] = float('nan')
    elif mutation == 'wrong_gateway': trades[0]['gateway_name'] = 'CTP'
    elif mutation == 'extra_trade_same_order': trades.append({**trades[0], 'trade_id': 'BACKTESTING.3', 'exit_reason': ''})
    with pytest.raises(ValueError):
        m.validate_actions(decisions, gate, trades, provider, days, states, terminal)


@pytest.mark.parametrize('mutation', ['nonterminal', 'missing_active', 'partially_filled', 'wrong_pending',
    'wrong_target', 'wrong_actual', 'wrong_order_direction', 'missing_reason', 'missing_terminal_state', 'duplicate_unfilled'])
def test_invalid_unfilled_order_cannot_become_terminal_censor(mutation):
    m = module(); decisions, gate, trades, provider, days, states, terminal = fixture(True)
    row = terminal['states'][0]
    if mutation == 'nonterminal': days = DAYS
    elif mutation == 'missing_active': row['active_orders'].clear()
    elif mutation == 'partially_filled': row['active_orders'][0]['traded'] = 1.
    elif mutation == 'wrong_pending': terminal['pending_close_volumes'][SYMBOL] = 1.
    elif mutation == 'wrong_target': row['targets'] = {SYMBOL: 2.}
    elif mutation == 'wrong_actual': row['actual_positions'][SYMBOL] = 1.
    elif mutation == 'wrong_order_direction': row['active_orders'][0]['direction'] = 'Direction.LONG'
    elif mutation == 'missing_reason': row['pending_close_reason_count'] = 0
    elif mutation == 'missing_terminal_state': terminal['states'].clear()
    elif mutation == 'duplicate_unfilled': gate['unfilled_order_ids'] *= 2
    with pytest.raises(ValueError):
        m.validate_actions(decisions, gate, trades, provider, days, states, terminal)


def account():
    _, _, closing, _, _, _, _ = fixture()
    opening = {**closing[0], 'trade_id': 'BACKTESTING.1', 'order_id': 'BACKTESTING.1', 'date': DAYS[0],
        'datetime': DAYS[0] + ' 00:00:00+08:00', 'direction': '\u591a', 'offset': '\u5f00',
        'price': '100', 'signed_volume': '2', 'exit_reason': ''}
    positions = [dict(date=DAYS[0], vt_symbol=SYMBOL, start_pos='0', end_pos='2', close_price='105',
                      commission='0', slippage='20', net_pnl='80'),
                 dict(date=DAYS[1], vt_symbol=SYMBOL, start_pos='2', end_pos='0', close_price='110',
                      commission='0', slippage='20', net_pnl='40')]
    daily = [dict(date=DAYS[0], net_pnl='80', total_net_pnl='80', account_equity='150080'),
             dict(date=DAYS[1], net_pnl='40', total_net_pnl='40', account_equity='150120')]
    return daily, positions, [opening, *closing], {SYMBOL: 10}


def test_account_uses_lexical_actual_fills_and_costs():
    m = module(); books, quality = m.reconcile_account(*account())
    assert books[DAYS[0]][SYMBOL] == {'quantity': '2', 'average_entry_price': '100', 'source_trade_ids': ['BACKTESTING.1']}
    assert books[DAYS[1]] == {} and quality['trade_count'] == 2
    assert quality['max_account_daily_error'] == quality['max_equity_conservation_error'] == 0


def test_zero_warmup_is_allowed_but_not_outside_period_exposure():
    m = module(); daily, positions, trades, sizes = account()
    warmup = {**positions[0], 'date': '2019-12-31', 'end_pos': '0', 'slippage': '0', 'net_pnl': '0'}
    m.reconcile_account(daily, [warmup, *positions], trades, sizes)
    warmup['net_pnl'] = '1'
    with pytest.raises(ValueError):
        m.reconcile_account(daily, [warmup, *positions], trades, sizes)


@pytest.mark.parametrize('mutation', ['equity', 'pnl', 'net_alias', 'duplicate_day', 'missing_day', 'overclose', 'unit', 'warmup_trade'])
def test_account_mismatch_fails(mutation):
    m = module(); daily, positions, trades, sizes = account()
    if mutation == 'equity': daily[1]['account_equity'] = '150121'
    elif mutation == 'pnl': daily[1]['net_pnl'] = '41'
    elif mutation == 'net_alias': daily[1]['total_net_pnl'] = '41'
    elif mutation == 'duplicate_day': daily.append(copy.deepcopy(daily[-1]))
    elif mutation == 'missing_day': daily.pop()
    elif mutation == 'overclose': trades[-1]['volume'] = '3'; trades[-1]['signed_volume'] = '-3'
    elif mutation == 'unit': sizes[SYMBOL] = 0
    elif mutation == 'warmup_trade': trades[0].update(date='2019-12-31', datetime='2019-12-31 00:00:00')
    with pytest.raises(ValueError):
        m.reconcile_account(daily, positions, trades, sizes)
