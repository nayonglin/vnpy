import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage050_holding_failure_diagnostics.py'
    assert path.exists(), 'holding failure diagnostic implementation missing'
    spec = importlib.util.spec_from_file_location('test_holding_failure', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def inputs(m):
    a = pd.DataFrame({'observation_id': ['a', 'b', 'c'], 'root_id': ['r', 'r', 's'],
        'date': ['2021-09-01', '2021-09-02', '2021-09-03'],
        'product_vt_symbol': ['aa.X'] * 3, 'vt_symbol': ['aa1.X'] * 3,
        'label_end_date': ['2021-10-01'] * 3, 'label_status': ['verified'] * 3,
        'return_marginal': [2., -1., -1.], 'drawdown_marginal': [-1., -1., 0.]})
    for name in m.FEATURES:
        a[name] = 0.
    p = a[m.KEYS].copy()
    p['cutoff'] = '2021-09-01'; p['status'] = 'predicted'; p['exit'] = True
    for target in m.TARGETS:
        p[target] = -1.
    metadata = {'2021-09-01': {'status': 'trained', 'heads': {
        target: {'mean': 0., 'std': 1.} for target in m.TARGETS}}}
    return a, p, metadata


def test_join_and_first_exit_do_not_select_by_realized_utility():
    m = module(); a, p, meta = inputs(m)
    joined = m.join_predictions(a, p.iloc[::-1], meta)
    first = m.first_exits(joined.iloc[::-1])
    assert first.observation_id.tolist() == ['a', 'c']
    assert first.return_marginal.tolist() == [2., -1.]
    counts = m.action_metrics(joined)
    assert counts['tp'] == 1 and counts['fp'] == 2
    assert counts['exit_return_positive'] == 1
    assert counts['precision'] == pytest.approx(1 / 3)


@pytest.mark.parametrize('kind', ['duplicate', 'missing', 'root', 'date', 'cutoff', 'nan_prediction', 'wrong_action', 'invalid_bool'])
def test_join_rejects_inventory_identity_or_action_corruption(kind):
    m = module(); a, p, meta = inputs(m)
    if kind == 'duplicate': p = pd.concat([p, p.iloc[:1]])
    elif kind == 'missing': p = p.iloc[:2]
    elif kind == 'root': p.loc[0, 'root_id'] = 'other'
    elif kind == 'date': p.loc[0, 'date'] = '2021-09-09'
    elif kind == 'cutoff': p.loc[0, 'cutoff'] = '2021-08-01'
    elif kind == 'nan_prediction': p.loc[0, 'return_marginal'] = np.nan
    elif kind == 'wrong_action': p.loc[0, 'return_marginal'] = 0.
    else: p['exit'] = 'False'
    with pytest.raises(RuntimeError):
        m.join_predictions(a, p, meta)


def test_untrained_rows_are_preserved_but_never_evaluated_or_exited():
    m = module(); a, p, meta = inputs(m)
    p['status'] = 'untrained'; p['exit'] = False; p[m.TARGETS] = np.nan
    meta['2021-09-01'] = {'status': 'untrained', 'heads': {}}
    joined = m.join_predictions(a, p, meta)
    assert len(joined) == 3 and not joined.evaluable.any()
    assert m.first_exits(joined).empty
    assert m.action_metrics(joined)['precision'] is None
    p.loc[0, 'return_marginal'] = 0.
    with pytest.raises(RuntimeError): m.join_predictions(a, p, meta)


def test_root_weighting_and_weighted_error_use_all_roots_equally():
    m = module()
    weights = m.root_weights(pd.Series(['r', 'r', 's']))
    np.testing.assert_array_equal(weights, [.5, .5, 1.])
    metrics = m.regression_metrics([2., 2., 0.], [0., 0., 0.], [1., 1., 1.], weights)
    assert metrics['mse'] == 2. and metrics['mae'] == 1.
    assert metrics['baseline_mse'] == 1. and metrics['mse_skill'] == -1.
    assert m.regression_metrics([], [], [], [])['mse_skill'] is None
    assert m.regression_metrics([0.], [1.], [0.], [1.])['mse_skill'] is None


@pytest.mark.parametrize('weights', [[1., -1.], [0., 0.], [1., np.nan], [1.]])
def test_weighted_error_rejects_invalid_weights(weights):
    m = module()
    with pytest.raises(RuntimeError): m.regression_metrics([1., 2.], [1., 2.], [1., 2.], weights)


def test_crosswalk_never_transfers_labels_to_candidate_path():
    m = module(); a, p, meta = inputs(m); a = m.join_predictions(a, p, meta)
    c = a.iloc[[0, 2]][['date', 'product_vt_symbol', 'vt_symbol', *m.FEATURES, 'exit']].copy()
    c.loc[2, 'date'] = '2021-09-04'; c.loc[0, 'portfolio_drawdown'] = -.2
    pairs, summary = m.crosswalk(a, c)
    assert summary['common'] == 1 and summary['A_only'] == 2 and summary['C_only'] == 1
    assert summary['feature_changed']['portfolio_drawdown'] == 1
    assert summary['C_label_transfer_count'] == 0
    assert not any('marginal' in key or 'label' in key for key in pairs.columns)
    with pytest.raises(RuntimeError): m.crosswalk(a, pd.concat([c, c.iloc[:1]]))


def test_holding_decomposition_checks_inclusive_observation_prefix_and_ledger_anchor():
    m = module()
    dates = ['2020-01-02', '2020-01-03', '2020-01-06']
    am = pd.DataFrame({'aa.X': [0., 0., 8.], 'bb.X': [0., 0., -12.]}, index=dates)
    em = am * 0.
    a = pd.DataFrame({'date': dates, 'total_net_pnl': [0., 0., -4.], 'account_equity': [100., 100., 96.]})
    e = a.copy(); e['total_net_pnl'] = 0.; e['account_equity'] = 100.
    result, _, _ = m.holding_decomposition(am, em, a, e, 'aa.X', dates[1], dates[2], 100., -.04)
    assert result['target_delta_cash'] == 8 and result['other_delta_cash'] == -12
    assert result['target_total_sign_flip']
    with pytest.raises(RuntimeError): m.holding_decomposition(am, em, a, e, 'aa.X', dates[1], dates[2], 99., -.04)
    am.iloc[1, 0] = 1.; am.iloc[1, 1] = -1.
    with pytest.raises(RuntimeError): m.holding_decomposition(am, em, a, e, 'aa.X', dates[1], dates[2], 100., -.04)


def test_saved_training_statistics_reject_current_month_maturity_and_transform_change():
    m = module(); a, _, _ = inputs(m)
    a['date'] = ['2021-08-01', '2021-08-02', '2021-08-03']
    a['label_end_date'] = ['2021-08-30', '2021-08-30', '2021-09-01']
    models = m.load('stage044_holding_models')
    spec = {'features': m.FEATURES, 'targets': m.TARGETS, 'minimum_mature_roots': 60}
    bundle = models.fit_month(a, '2021-09-01', spec)
    assert bundle['train_observation_ids'] == ['a', 'b']
    assert m.validate_training(a, {'2021-09-01': bundle}, spec) == 1
    bundle['train_weights'][0] = 1.
    with pytest.raises(RuntimeError): m.validate_training(a, {'2021-09-01': bundle}, spec)


def test_source_pin_rejects_modified_bytes(tmp_path):
    m = module(); path = tmp_path / 'input'; path.write_bytes(b'original')
    identity = m.file_identity(path); sources = {}
    m.bind(path, identity, sources)
    path.write_bytes(b'corrupt!')
    with pytest.raises(RuntimeError): m.bind(path, identity, sources)


def test_label_owner_uses_full_frozen_stage_enum_without_path_escape():
    m = module()
    for stage in ('stage041b_holding_labels', 'stage042_holding_labels'):
        assert m.label_folder(stage, 'abc') == ROOT / 'artifacts' / stage / 'jobs/abc'
    for stage, identifier in [('stage041b', 'abc'), ('../other', 'abc'), ('stage042_holding_labels', '../abc')]:
        with pytest.raises(RuntimeError): m.label_folder(stage, identifier)


def test_trained_constant_head_transform_is_recomputed_without_fitting():
    m = module(); a, _, _ = inputs(m)
    a['date'] = ['2021-08-01', '2021-08-02', '2021-08-03']
    a['label_end_date'] = '2021-08-30'; a[m.TARGETS] = 2.
    models = m.load('stage044_holding_models')
    spec = {'features': m.FEATURES, 'targets': m.TARGETS, 'minimum_mature_roots': 1}
    bundle = models.fit_month(a, '2021-09-01', spec)
    assert bundle['fit_count'] == 0
    assert m.validate_training(a, {'2021-09-01': bundle}, spec) == 1
    bundle['heads']['return_marginal']['mean'] += .001
    with pytest.raises(RuntimeError): m.validate_training(a, {'2021-09-01': bundle}, spec)
