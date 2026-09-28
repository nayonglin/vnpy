import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage017_label_path_decomposition.py'
    assert path.exists(), 'label decomposition implementation missing'
    spec = importlib.util.spec_from_file_location('test_label_decomposition', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def inputs():
    dates = ['2020-01-02','2020-01-03','2020-01-06']
    positions = pd.DataFrame({'date':np.repeat(dates,2), 'vt_symbol':['aa1.X','bb1.X']*3,
                              'net_pnl':[0.,0.,10.,-4.,-2.,1.]})
    daily = pd.DataFrame({'date':dates,'total_net_pnl':[0.,6.,-1.], 'account_equity':[100.,106.,105.]})
    mapping = {'aa1.X':'aa.X','bb1.X':'bb.X','cc1.X':'cc.X'}
    return positions,daily,mapping


def test_product_ledger_reconciles_cash_without_multiplier_or_double_costs():
    m = module()
    positions,daily,mapping = inputs()
    matrix,error = m.product_ledger(positions,daily,mapping)
    assert matrix.index.tolist()==daily.date.tolist()
    assert matrix.columns.tolist()==['aa.X','bb.X','cc.X']
    assert matrix['aa.X'].sum()==8 and matrix['bb.X'].sum()==-3
    assert matrix['cc.X'].eq(0).all() and error==0


@pytest.mark.parametrize('kind',['duplicate','missing_day','unmapped','nonfinite','account_mismatch'])
def test_product_ledger_rejects_invalid_source_or_nonconservation(kind):
    m = module()
    positions,daily,mapping = inputs()
    if kind=='duplicate':
        positions=pd.concat([positions,positions.iloc[:1]])
    elif kind=='missing_day':
        positions=positions.iloc[2:]
    elif kind=='unmapped':
        positions.loc[0,'vt_symbol']='xx1.X'
    elif kind=='nonfinite':
        positions.loc[0,'net_pnl']=np.nan
    else:
        daily.loc[1,'total_net_pnl']+=1
    with pytest.raises(RuntimeError):
        m.product_ledger(positions,daily,mapping)


def case(m,other=-12.):
    positions,a,mapping=inputs()
    positions['net_pnl']=[0.,0.,10.,other,-2.,0.]
    a['total_net_pnl']=[0.,10.+other,-2.]
    a['account_equity']=100.+a.total_net_pnl.cumsum()
    s=a.copy(); s['total_net_pnl']=0.; s['account_equity']=100.
    am,_=m.product_ledger(positions,a,mapping)
    sm=am*0.
    return am,sm,a,s


def test_decomposition_detects_other_product_sign_reversal_and_daily_conservation():
    m=module(); am,sm,a,s=case(m)
    result,days,products=m.decompose(am,sm,a,s,'aa.X','2020-01-03','2020-01-06',100.,-0.04)
    assert result['target_delta_cash']==8 and result['other_delta_cash']==-12
    assert result['total_delta_cash']==-4 and result['target_total_sign_flip']
    assert result['other_abs_net_share']==0.6 and result['other_dominates']
    assert result['horizon_days']==2
    np.testing.assert_array_equal(days.total_delta_net_pnl,[-2.,-2.])
    assert products.delta_net_pnl.sum()==-4


def test_zero_cancelled_case_has_undefined_share_not_fabricated_zero():
    m=module(); am,sm,a,s=case(m)
    result,_,_=m.decompose(sm,sm,s,s,'aa.X','2020-01-03','2020-01-06',100.,0.)
    assert result['other_abs_net_share'] is None
    assert result['total_delta_cash']==0 and not result['target_total_sign_flip']


@pytest.mark.parametrize('kind',['label','prefix','window','daily_path','capital'])
def test_decomposition_rejects_changed_label_prefix_calendar_or_path(kind):
    m=module(); am,sm,a,s=case(m)
    label,capital,end=-0.04,100.,'2020-01-06'
    if kind=='label': label=0.2
    elif kind=='prefix':
        sm.iloc[0,0]=1.; s.loc[0,'total_net_pnl']=1.; s['account_equity']+=1.
    elif kind=='window': end='2020-01-07'
    elif kind=='daily_path': a.loc[1,'account_equity']+=1.
    else: capital=0.
    with pytest.raises(RuntimeError):
        m.decompose(am,sm,a,s,'aa.X','2020-01-03',end,capital,label)


def test_existing_output_rejected_before_source_read(tmp_path,monkeypatch):
    m=module()
    monkeypatch.setattr(m,'OUTPUT',tmp_path)
    monkeypatch.setattr(m,'prepare_inputs',lambda: pytest.fail('source read'))
    with pytest.raises(RuntimeError,match='already_exists'):
        m.run()
