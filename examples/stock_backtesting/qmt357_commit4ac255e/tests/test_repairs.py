"""Frozen, evidence-bound corrections cannot silently mutate unrelated data."""
import importlib
from pathlib import Path
import pandas as pd
import pytest


def repair(frame, operations):
    assert (Path(__file__).resolve().parents[1] / 'repairs.py').exists(), 'Evidence repair utility is missing'
    module = importlib.import_module('examples.stock_backtesting.qmt357_commit4ac255e.repairs')
    return module.apply_repairs(frame, operations)


def frame():
    return pd.DataFrame(dict(date=pd.date_range('2020-01-01', periods=5),
        vt_symbol=['000001.SZSE']*5, adj_factor=[2., 4., 4., 4.4, 4.4],
        cash_dividend=[0.,0.,0.,.1,0.], split_ratio=[1.]*5, close=[10.]*5))


def step(**kw):
    return dict(kind='factor_step', vt_symbol='000001.SZSE', date='2020-01-02',
        previous_factor=2., current_factor=4., desired_ratio=1.,
        evidence=['cross-source-receipt'], reason='confirmed provider reset', **kw)


def test_factor_step_preserves_later_true_events_and_original():
    original = frame()
    corrected, changes = repair(original, [step()])
    assert original.adj_factor.tolist() == [2.,4.,4.,4.4,4.4]
    assert corrected.adj_factor.tolist() == [2.,2.,2.,2.2,2.2]
    pd.testing.assert_frame_equal(corrected.drop(columns='adj_factor'), original.drop(columns='adj_factor'))
    assert len(changes) == 4


def test_factor_step_fails_stale_input_or_missing_evidence():
    for field, value in [('current_factor',3.), ('evidence',[])]:
        operation = step()
        operation[field] = value
        with pytest.raises(ValueError):
            repair(frame(), [operation])


def test_move_factor_to_actual_ex_date_does_not_create_free_shares():
    data = frame()
    data['adj_factor'] = [2.,2.,2.,4.,4.]
    op = dict(kind='factor_move',vt_symbol='000001.SZSE',date='2020-01-04',
        actual_date='2020-01-02',previous_factor=2.,current_factor=4.,
        evidence=['exchange-ex-date'],reason='confirmed timestamp delay')
    corrected, _ = repair(data, [op])
    assert corrected.adj_factor.tolist() == [2.,4.,4.,4.,4.]
    assert corrected.split_ratio.eq(1).all()
    assert corrected.cash_dividend.tolist() == [0.,0.,0.,.1,0.]


def test_point_action_correction_requires_original_value_and_changes_no_factor():
    op = dict(kind='action',vt_symbol='000001.SZSE',date='2020-01-04',
        field='cash_dividend',old=.1,new=.5,evidence=['issuer-notice'],reason='special dividend')
    corrected, _ = repair(frame(), [op])
    assert corrected.cash_dividend.tolist() == [0.,0.,0.,.5,0.]
    assert corrected.adj_factor.tolist() == frame().adj_factor.tolist()
    op['field'] = 'close'
    with pytest.raises(ValueError):
        repair(frame(), [op])


def test_legacy_factor_bridge_is_backward_asof_only_and_bounded():
    op = dict(kind='factor_prefix',vt_symbol='000001.SZSE',before='2020-01-04',
        expected_old=2.,bridge_factor=4.4,
        factors=[['2019-12-01',3.],['2020-01-02',4.4]],
        evidence=['old-code-source','identity-announcement'],reason='verified code change')
    data = frame()
    data['adj_factor'] = [2.,2.,2.,4.4,4.4]
    corrected, _ = repair(data, [op])
    assert corrected.adj_factor.tolist() == [3.,4.4,4.4,4.4,4.4]
    op['factors'] = [['2020-01-02',4.4]]
    with pytest.raises(ValueError, match='coverage'):
        repair(data, [op])


def test_prefix_and_other_factor_repairs_cannot_overlap_in_either_order():
    data = frame()
    data['adj_factor'] = [2.,2.,2.,4.4,4.4]
    prefix = dict(kind='factor_prefix',vt_symbol='000001.SZSE',before='2020-01-04',
        expected_old=2.,bridge_factor=4.4,
        factors=[['2019-12-01',3.],['2020-01-02',4.4]],
        evidence=['old-source'],reason='code bridge')
    other = step()
    other.update(current_factor=2.,desired_ratio=1.1)
    for ops in ([prefix,other],[other,prefix]):
        with pytest.raises(ValueError, match='overlap'):
            repair(data, ops)
