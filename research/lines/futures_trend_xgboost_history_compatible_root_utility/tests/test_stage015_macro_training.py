import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage015_macro_training.py'
    assert path.exists(), 'macro training implementation missing'
    spec = importlib.util.spec_from_file_location('test_macro_training', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def fixture(m):
    oldspec = json.loads((ROOT / 'stages/stage004_model_spec.json').read_text())
    data = pd.DataFrame({'event_id':['a','b'], 'candidate_index':[7,8], 'decision_date':['2021-04-05','2021-04-06'],
                         'product_vt_symbol':['rb.SHFE','au.SHFE'], 'contract_vt_symbol':['rb2105.SHFE','au2106.SHFE'],
                         'direction':['long','short'], 'return_marginal':[np.nextafter(0.1, 1),np.nan],
                         'drawdown_marginal':[0.2,np.nan], 'label_status':['verified','censored']})
    for name in oldspec['features']:
        data[name] = [np.nextafter(0.3, 1),np.nextafter(0.7, 1)]
    features = data[m.ID_COLUMNS].copy()
    features['source_date'] = ['2021-04-02','2021-04-05']
    for i, name in enumerate(m.macro().FEATURES):
        features[name] = [0.1+i,0.2+i]
    newspec = m.macro().candidate_spec(oldspec)
    return data, features, oldspec, newspec


def test_join_keeps_original_precision_order_and_censored_targets():
    m = module()
    data, features, oldspec, newspec = fixture(m)
    original = data.copy(deep=True)
    result = m.join_features(data, features.iloc[::-1], oldspec, newspec)
    pd.testing.assert_frame_equal(result[data.columns], data, check_exact=True)
    pd.testing.assert_frame_equal(data, original, check_exact=True)
    np.testing.assert_array_equal(result[m.macro().FEATURES], features[m.macro().FEATURES])


@pytest.mark.parametrize('kind', ['missing','duplicate','direction','same_day','nonfinite','extra_target'])
def test_join_rejects_invalid_macro_identity_or_values(kind):
    m = module()
    data, features, oldspec, newspec = fixture(m)
    if kind == 'missing':
        features = features.iloc[:1]
    elif kind == 'duplicate':
        features = pd.concat([features,features.iloc[:1]])
    elif kind == 'direction':
        features.loc[0,'direction'] = 'short'
    elif kind == 'same_day':
        features.loc[0,'source_date'] = features.loc[0,'decision_date']
    elif kind == 'nonfinite':
        features.loc[0,m.macro().FEATURES[0]] = np.inf
    else:
        features['return_marginal'] = 0.0
    with pytest.raises(RuntimeError):
        m.join_features(data, features, oldspec, newspec)


def test_join_rejects_parameter_or_feature_order_changes():
    m = module()
    data, features, oldspec, newspec = fixture(m)
    altered = copy.deepcopy(newspec)
    altered['estimator']['max_depth'] = 3
    with pytest.raises(RuntimeError, match='spec'):
        m.join_features(data, features, oldspec, altered)
    altered = copy.deepcopy(newspec)
    altered['features'].reverse()
    with pytest.raises(RuntimeError, match='spec'):
        m.join_features(data, features, oldspec, altered)


def test_existing_campaign_rejected_before_dataset_read(tmp_path, monkeypatch):
    m = module()
    monkeypatch.setattr(m,'OUTPUT',tmp_path)
    monkeypatch.setattr(m,'load_dataset', lambda: pytest.fail('dataset read'))
    with pytest.raises(RuntimeError, match='already_exists'):
        m.run()


def test_catalog_rejects_failed_campaign_before_loading_models(tmp_path):
    m = module()
    (tmp_path/'failure.json').write_text('{}')
    with pytest.raises(RuntimeError, match='not_complete'):
        m.load_catalog(tmp_path, {})
