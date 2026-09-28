import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage043_label_collection.py'
    assert path.exists(), 'mixed-source label collector missing'
    spec = importlib.util.spec_from_file_location('test_collection043', path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def fixture(m):
    jobs = [{'observation_id': k, 'root_id': 'r1', 'date': '2020-01-10', 'end_date': '2020-02-01'} for k in ['a','b','c']]
    values = {name: .1 for name in m.load('stage040_holding_panel').FEATURES}
    features = pd.DataFrame([{'observation_id': k, 'date': '2020-01-10', 'product_vt_symbol': 'jm.DCE',
        'vt_symbol': 'jm2005.DCE', **values} for k in ['a','b','c']])
    labels = {j['observation_id']: {**j, 'status': 'passed', 'marginal': {'return_marginal': .2, 'drawdown_marginal': -.1}}
              for j in jobs[:2]}
    return jobs, features, labels


def test_legacy_new_pending_have_explicit_sources_and_empty_targets():
    m = module(); jobs, features, labels = fixture(m)
    frame, ready = m.assemble(jobs, features, labels, {'a'})
    assert not ready
    assert frame.label_source_stage.tolist() == ['stage041b_holding_labels','stage042_holding_labels','']
    assert frame.label_status.tolist() == ['verified','verified','pending']
    assert pd.isna(frame.iloc[2].return_marginal)
    assert frame.root_id.tolist() == ['r1','r1','r1']


def test_duplicate_feature_and_unverified_inheritance_rejected():
    m = module(); jobs, features, labels = fixture(m)
    with pytest.raises(ValueError): m.assemble(jobs, pd.concat([features,features.iloc[:1]]),labels,{'a'})
    with pytest.raises(ValueError): m.assemble(jobs,features,labels,{'c'})


def test_feature_whitelist_and_identity_checked():
    m = module(); jobs, features, labels = fixture(m)
    features['future_price'] = 999
    with pytest.raises(ValueError): m.assemble(jobs,features,labels,{'a'})
    _, features, _ = fixture(m); features.loc[0,'observation_id'] = 'unknown'
    with pytest.raises(ValueError): m.assemble(jobs,features,labels,{'a'})
