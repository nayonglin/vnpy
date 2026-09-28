import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage041c_label_collection.py'
    assert path.exists(), 'holding label collector missing'
    spec = importlib.util.spec_from_file_location('collector041c_test', path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def jobs():
    return [{'observation_id': 'a', 'root_id': 'r1', 'date': '2020-01-10', 'end_date': '2020-02-01'},
            {'observation_id': 'b', 'root_id': 'r1', 'date': '2020-01-13', 'end_date': '2020-02-01'}]


def label():
    return {'observation_id': 'a', 'root_id': 'r1', 'date': '2020-01-10', 'end_date': '2020-02-01',
            'status': 'passed', 'marginal': {'return_marginal': 0., 'drawdown_marginal': -.1}}


def test_pending_is_not_zero_and_same_root_not_independent():
    m = module(); rows, ready = m.label_rows(jobs(), {'a': label()})
    assert not ready
    assert rows[0]['return_marginal'] == 0. and rows[0]['label_status'] == 'verified'
    assert rows[1]['return_marginal'] is None and rows[1]['drawdown_marginal'] is None
    assert rows[1]['label_status'] == 'pending' and rows[0]['root_id'] == rows[1]['root_id']


@pytest.mark.parametrize('field,value', [('root_id','wrong'), ('end_date','2020-02-02'), ('status','failed')])
def test_label_identity_rejected(field, value):
    m = module(); item = label(); item[field] = value
    with pytest.raises(ValueError):
        m.label_rows(jobs(), {'a': item})


def test_unknown_duplicate_and_nonfinite_labels_rejected():
    m = module()
    with pytest.raises(ValueError): m.label_rows(jobs(), {'x': label()})
    with pytest.raises(ValueError): m.label_rows([*jobs(), jobs()[0]], {})
    item = label(); item['marginal']['return_marginal'] = float('nan')
    with pytest.raises(ValueError): m.label_rows(jobs(), {'a': item})
