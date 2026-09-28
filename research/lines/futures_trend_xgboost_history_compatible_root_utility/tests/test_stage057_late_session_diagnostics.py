import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tool():
    path = ROOT / 'tools/stage057_late_session_diagnostics.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('test_late_diagnostic057', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def points():
    return pd.DataFrame({
        'observation_id': ['a', 'b', 'c', 'd', 'e'],
        'root_id': ['r', 'r', 's', 't', 'u'],
        'date': ['2021-09-02', '2021-09-03', '2021-09-02', '2021-09-02', '2020-01-02'],
        'product_vt_symbol': ['p.X'] * 5, 'vt_symbol': ['p1.X'] * 5,
        'label_end_date': ['2021-09-09'] * 4 + ['2020-01-09'],
        'label_status': ['verified'] * 5, 'label_source_stage': ['stage042_holding_labels'] * 5,
        'return_marginal': [2., -1., -1., -1., 1.],
        'drawdown_marginal': [-1., -1., 0., -1., -1.],
        'cutoff': ['2021-09-01'] * 4 + ['2020-01-01'],
        'evaluable': [True] * 4 + [False], 'status': ['predicted'] * 4 + ['untrained'],
        'exit': [True, False, False, True, False],
        'pred_return_marginal': [-.1, .1, .1, -.1, np.nan],
        'pred_drawdown_marginal': [-.1] * 4 + [np.nan],
        'baseline_return_marginal': [0.] * 4 + [np.nan],
        'baseline_drawdown_marginal': [0.] * 4 + [np.nan],
    })


def with_features(tool, frame):
    frame = frame.copy()
    for name in tool.BASE_FEATURES:
        frame[name] = 1.
    return frame


def newer(old):
    result = old.copy()
    result['exit'] = [False, True, True, True, False]
    result['pred_return_marginal'] = [.1, -.1, -.1, -.1, np.nan]
    return result


def test_exact_pairs_keep_untrained_and_strict_zero_truth(tool):
    assert tool is not None, 'stage057 incremental diagnostic implementation missing'
    old = with_features(tool, points())
    paired = tool.pair_points(old, newer(old).iloc[::-1])
    assert len(paired) == 5
    assert paired.transition.tolist() == ['cancelled_exit', 'added_exit', 'added_exit', 'both_exit', 'untrained']
    counts = tool.transition_metrics(paired)
    assert counts['cancelled_exit']['false_exit_labels'] == 1
    assert counts['added_exit']['true_exit_labels'] == 1
    assert counts['added_exit']['false_exit_labels'] == 1
    assert counts['untrained']['count'] == 1
    assert counts['both_hold']['count'] == 0


@pytest.mark.parametrize('column,value', [
    ('root_id', 'wrong'), ('return_marginal', 99.), ('label_end_date', '2030-01-01'),
    ('baseline_return_marginal', 99.), ('directional_day_return', 99.),
    ('evaluable', False), ('status', 'untrained'), ('cutoff', '2021-10-01'),
])
def test_pair_rejects_changed_domain_or_baseline(tool, column, value):
    old = with_features(tool, points()); new = newer(old)
    new.loc[0, column] = value
    with pytest.raises(RuntimeError, match='pair'):
        tool.pair_points(old, new)


@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'action', 'nonfinite', 'untrained_exit'])
def test_pair_rejects_bad_inventory_and_actions(tool, kind):
    old = with_features(tool, points()); new = newer(old)
    if kind == 'missing':
        new = new.iloc[1:]
    elif kind == 'duplicate':
        new = pd.concat([new, new.iloc[:1]])
    elif kind == 'action':
        new.loc[0, 'exit'] = True
    elif kind == 'nonfinite':
        new.loc[0, 'pred_return_marginal'] = np.nan
    else:
        new.loc[4, 'exit'] = True
    with pytest.raises(RuntimeError, match='pair'):
        tool.pair_points(old, new)


def test_first_exit_comparison_not_best_label_selection(tool):
    old = with_features(tool, points()); new = newer(old)
    table, counts = tool.first_exit_comparison(old, new)
    row = table.set_index('root_id').loc['r']
    assert row['observation_id_old'] == 'a'
    assert row['return_marginal_old'] == 2.
    assert row['observation_id_new'] == 'b'
    assert counts == {'same_observation': 1, 'new_earlier': 0, 'new_later': 1, 'new_only': 1, 'old_only': 0}
    assert not any('recall' in name for name in counts)


def path_frame():
    return pd.DataFrame({'date': ['2021-01-01', '2021-01-02'],
        'product_vt_symbol': ['p.X', 'p.X'], 'vt_symbol': ['p1.X', 'p1.X'],
        'f': [1., 2.], 'exit': [False, True], 'return_marginal': [123., 456.]})


def test_path_crosswalk_excludes_labels_and_keeps_unmatched(tool):
    old = path_frame(); new = old.copy()
    new.loc[0, 'exit'] = True
    new.loc[1, 'date'] = '2021-01-03'
    table, stats = tool.path_crosswalk(old, new, ['f'])
    assert not any('marginal' in name for name in table)
    assert stats['common'] == 1 and stats['old_only'] == stats['new_only'] == 1
    assert stats['same_features_changed_action'] == 1
    assert stats['first_common_action_change']['date'] == '2021-01-01'
    assert stats['label_transfer_count'] == 0


@pytest.mark.parametrize('kind', ['duplicate', 'missing_feature', 'nonfinite', 'string_bool'])
def test_path_crosswalk_fail_closed(tool, kind):
    old = path_frame(); new = old.copy()
    if kind == 'duplicate':
        new = pd.concat([new, new.iloc[:1]])
    elif kind == 'missing_feature':
        new = new.drop(columns='f')
    elif kind == 'nonfinite':
        new.loc[0, 'f'] = np.nan
    else:
        new['exit'] = new['exit'].astype(str)
    with pytest.raises(RuntimeError, match='path'):
        tool.path_crosswalk(old, new, ['f'])


def ledgers():
    dates = ['2020-01-02', '2020-01-03']
    a = pd.DataFrame({'date': dates, 'total_net_pnl': [10., -5.], 'account_equity': [150010., 150005.]})
    c = pd.DataFrame({'date': dates, 'total_net_pnl': [10., -2.], 'account_equity': [150010., 150008.]})
    am = pd.DataFrame({'p.X': [10., -5.]}, index=dates)
    cm = pd.DataFrame({'p.X': [10., -2.]}, index=dates)
    return {'A': a, 'C9': a.copy(), 'C11': c}, {'A': am, 'C9': am.copy(), 'C11': cm}


def test_cash_conservation_and_first_difference(tool):
    daily, matrices = ledgers()
    products, years, stats = tool.compare_ledgers(daily, matrices)
    assert stats['C11_minus_A'] == 3.
    assert stats['C11_minus_C9'] == 3.
    assert stats['first_equity_difference_C11_C9'] == '2020-01-03'
    assert products.C11_minus_C9.sum() == years.C11_minus_C9.sum() == 3.


@pytest.mark.parametrize('kind', ['equity', 'calendar', 'product'])
def test_cash_conservation_fail_closed(tool, kind):
    daily, matrices = ledgers()
    if kind == 'equity':
        daily['C11'].loc[1, 'account_equity'] += 1
    elif kind == 'calendar':
        daily['C11'].loc[1, 'date'] = '2020-01-04'
    else:
        matrices['C11'].loc['2020-01-03', 'p.X'] += 1
    with pytest.raises(RuntimeError, match='ledger'):
        tool.compare_ledgers(daily, matrices)
