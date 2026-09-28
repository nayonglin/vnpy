import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage031_migration_training.py'
    assert path.exists(), 'migration training implementation missing'
    spec = importlib.util.spec_from_file_location('test_training031', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fixture(m):
    old = json.loads((ROOT / 'stages/stage004_model_spec.json').read_text())
    data = pd.DataFrame(dict(event_id=['a','b'], candidate_index=[1,2],
        decision_date=['2021-04-05','2021-04-06'], product_vt_symbol=['rb.SHFE','au.SHFE'],
        contract_vt_symbol=['rb2105.SHFE','au2106.SHFE'], direction=['long','short'],
        return_marginal=[np.nextafter(.1,1),np.nan], drawdown_marginal=[.2,np.nan],
        label_status=['verified','censored']))
    for name in old['features']:
        data[name] = [np.nextafter(.3,1),np.nextafter(.7,1)]
    features = data[m.ID_COLUMNS].copy()
    features['source_date'] = ['2021-04-02','2021-04-05']
    features['window_start'] = ['2021-03-26','2021-03-29']
    for name in m.migration().FEATURES:
        features[name] = [.1,-.2]
    return data, features, old, m.migration().candidate_spec(old)


def test_join_preserves_targets_precision_order_and_censoring():
    m = module()
    data, features, old, new = fixture(m)
    before = data.copy(deep=True)
    result = m.join_features(data, features.iloc[::-1], old, new)
    pd.testing.assert_frame_equal(data, before, check_exact=True)
    pd.testing.assert_frame_equal(result[data.columns], data, check_exact=True)
    np.testing.assert_array_equal(result[m.migration().FEATURES], features[m.migration().FEATURES])


@pytest.mark.parametrize('kind',['missing','duplicate','contract','same_day','window','bad_date','nan','target'])
def test_join_rejects_identity_time_or_data_tamper(kind):
    m = module()
    data, features, old, new = fixture(m)
    if kind == 'missing':
        features = features.iloc[:1]
    elif kind == 'duplicate':
        features = pd.concat([features,features.iloc[:1]])
    elif kind == 'contract':
        features.loc[0,'contract_vt_symbol'] = 'rb2110.SHFE'
    elif kind == 'same_day':
        features.loc[0,'source_date'] = features.loc[0,'decision_date']
    elif kind == 'window':
        features.loc[0,'window_start'] = features.loc[0,'source_date']
    elif kind == 'bad_date':
        features.loc[0,'window_start'] = '2021-02-30'
    elif kind == 'nan':
        features.loc[0,m.migration().FEATURES[0]] = np.nan
    else:
        features['return_marginal'] = 0
    with pytest.raises((ValueError,RuntimeError)):
        m.join_features(data, features, old, new)


@pytest.mark.parametrize('kind',['parameter','feature_order'])
def test_only_two_features_may_change_spec(kind):
    m = module()
    data, features, old, new = fixture(m)
    changed = copy.deepcopy(new)
    if kind == 'parameter':
        changed['estimator']['max_depth'] = 3
    else:
        changed['features'].reverse()
    with pytest.raises(RuntimeError,match='spec'):
        m.join_features(data,features,old,changed)


def test_existing_output_rejected_before_data_read(tmp_path,monkeypatch):
    m = module()
    monkeypatch.setattr(m,'OUTPUT',tmp_path)
    monkeypatch.setattr(m,'load_dataset',lambda: pytest.fail('unexpected dataset read'))
    with pytest.raises(RuntimeError,match='already_exists'):
        m.run()


def test_campaign_instance_isolated_and_frozen_parent_unchanged():
    m = module()
    parent = m.campaign()
    assert parent.STAGE == 'stage031_migration_training'
    assert parent.OUTPUT == ROOT/'artifacts/stage031_migration_training'
    assert parent.load_dataset is m.load_dataset
    assert m.load('stage015_macro_training').STAGE == 'stage015_macro_training'


def test_failed_catalog_rejected(tmp_path):
    m = module()
    (tmp_path/'failure.json').write_text('{}')
    with pytest.raises(RuntimeError,match='not_complete'):
        m.load_catalog(tmp_path,{})
