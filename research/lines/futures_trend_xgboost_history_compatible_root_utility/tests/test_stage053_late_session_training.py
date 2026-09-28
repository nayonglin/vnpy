import copy
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage053_late_session_training.py'
    assert path.exists(), 'late session training implementation missing'
    spec = importlib.util.spec_from_file_location('test_train053', path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def fixture(m):
    late = m.load('stage052_late_session_features')
    data = pd.DataFrame({'observation_id':['a','b'], 'root_id':['r','s'],
        'date':['2021-09-06','2021-09-07'], 'product_vt_symbol':['aa.X','bb.X'], 'vt_symbol':['aa1.X','bb1.X'],
        'return_marginal':[np.nextafter(.1,1),-.2], 'drawdown_marginal':[.01,-.02],
        'label_end_date':['2021-09-10','2021-09-11'], 'label_status':['verified','verified']})
    for name in late.BASE_FEATURES: data[name] = [np.nextafter(.3,1),.7]
    features = data[list(late.IDS)].copy()
    features['asof_close'] = features.date + 'T15:00:00'; features['last_minute'] = features.date + 'T14:59:00'
    features['late_minute_count'] = 30; features['status'] = 'qualified'
    features['directional_late_return_30m'] = [.001,-.002]; features['late_volume_fraction_30m'] = [.1,.2]
    base = {'features':list(late.BASE_FEATURES),'minimum_mature_roots':60,'estimator':{'max_depth':2}}
    return data,features,base,late.candidate_spec(base)


def test_exact_join_preserves_labels_original_features_and_order():
    m = module(); data,features,base,spec = fixture(m); before = data.copy(deep=True)
    result = m.join_features(data,features.iloc[::-1],base,spec)
    pd.testing.assert_frame_equal(result[data.columns],data,check_exact=True)
    pd.testing.assert_frame_equal(data,before,check_exact=True)
    assert result['directional_late_return_30m'].tolist() == [.001,-.002]


@pytest.mark.parametrize('kind',['missing','duplicate','root','contract','date','nan','asof','last_minute',
    'count','status','volume','target_column','parameter','feature_order'])
def test_join_rejects_identity_timing_or_spec_changes(kind):
    m = module(); data,features,base,spec = fixture(m)
    if kind == 'missing': features = features.iloc[:1]
    elif kind == 'duplicate': features = pd.concat([features,features.iloc[:1]])
    elif kind == 'root': features.loc[0,'root_id'] = 'wrong'
    elif kind == 'contract': features.loc[0,'vt_symbol'] = 'other.X'
    elif kind == 'date': features.loc[0,'date'] = '2021-09-08'
    elif kind == 'nan': features.loc[0,'directional_late_return_30m'] = np.nan
    elif kind == 'asof': features.loc[0,'asof_close'] = '2021-09-07T15:00:00'
    elif kind == 'last_minute': features.loc[0,'last_minute'] = '2021-09-06T15:00:00'
    elif kind == 'count': features.loc[0,'late_minute_count'] = 29
    elif kind == 'status': features.loc[0,'status'] = 'failed'
    elif kind == 'volume': features.loc[0,'late_volume_fraction_30m'] = 0.
    elif kind == 'target_column': features['return_marginal'] = 0.
    elif kind == 'parameter': spec['estimator']['max_depth'] = 3
    elif kind == 'feature_order': spec['features'].reverse()
    with pytest.raises(RuntimeError): m.join_features(data,features,base,spec)


def test_existing_output_rejected_before_any_snapshot_read(tmp_path,monkeypatch):
    m = module(); monkeypatch.setattr(m,'OUTPUT',tmp_path)
    monkeypatch.setattr(m,'load_dataset',lambda *_args: pytest.fail('unexpected label read'))
    with pytest.raises(RuntimeError,match='already_exists'): m.run()


def test_training_adapter_isolated_and_binds_parent_implementation():
    m = module(); parent = m.campaign()
    assert parent.OUTPUT == m.OUTPUT and parent.CONTRACT == m.CONTRACT
    assert parent.load_verified_snapshot is m.load_dataset
    assert Path(parent.__file__) == Path(m.__file__)
    original = m.load('stage044_holding_training')
    assert original.OUTPUT == ROOT/'artifacts/stage044_holding_training'
    assert original.load_verified_snapshot is not m.load_dataset


def test_summary_stage_is_relabelled_only_in_new_campaign(tmp_path,monkeypatch):
    m = module(); monkeypatch.setattr(m,'OUTPUT',tmp_path)
    parent = m.campaign(); batch = parent.load('stage004_label_batch')
    payload = {'stage':'stage044_holding_training','status':'passed'}
    before = copy.deepcopy(payload)
    batch.write_json(tmp_path/'summary.json',payload)
    import json
    assert json.loads((tmp_path/'summary.json').read_text())['stage'] == 'stage053_late_session_training'
    assert payload == before
