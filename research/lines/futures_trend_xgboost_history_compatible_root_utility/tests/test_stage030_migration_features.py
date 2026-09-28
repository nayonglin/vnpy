import copy
import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT=Path(__file__).resolve().parents[1]
DAYS=pd.bdate_range('2020-01-02',periods=9).strftime('%Y-%m-%d').tolist()


def module():
    path=ROOT/'tools/stage030_migration_features.py'
    assert path.exists(),'migration features missing'
    spec=importlib.util.spec_from_file_location('migration_test030',path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def inputs():
    catalog=pd.DataFrame([dict(tq_symbol='SHFE.rb2005',vt_symbol='rb2005.SHFE',product_vt_symbol='rb.SHFE',delivery_year=2020,delivery_month=5),
        dict(tq_symbol='SHFE.rb2010',vt_symbol='rb2010.SHFE',product_vt_symbol='rb.SHFE',delivery_year=2020,delivery_month=10)])
    bars=pd.DataFrame([dict(tq_symbol=s,trade_date=d,close_oi=(50-6*i if s.endswith('2005') else 50+6*i))
        for s in catalog.tq_symbol for i,d in enumerate(DAYS)])
    windows=pd.DataFrame([dict(decision_date=d,product_vt_symbol='rb.SHFE',source_date=DAYS[i-1],
        window_start=DAYS[max(0,i-6)],coverage_status='available' if i>=6 else 'insufficient_history')
        for i,d in enumerate(DAYS) if i>0])
    return bars,catalog,windows


def test_fixed_five_session_changes_are_exact_and_direction_neutral():
    m=module();b,c,w=inputs();context,inventory=m.contexts(b,c,w,DAYS)
    row=m.features_for_decision(context,DAYS[6],'rb2005.SHFE','rb.SHFE')
    assert row[m.FEATURES[0]]==pytest.approx(-0.3)
    assert row[m.FEATURES[1]]==pytest.approx(0.3)
    assert len(inventory)==16 and len(context)==6


def test_actual_contract_reference_not_borrowed_from_main_contract():
    m=module();b,c,w=inputs();context,_=m.contexts(b,c,w,DAYS)
    row=m.features_for_decision(context,DAYS[6],'rb2010.SHFE','rb.SHFE')
    assert row[m.FEATURES[0]]==pytest.approx(0.3) and row[m.FEATURES[1]]==0


def test_same_day_and_future_values_cannot_change_current_features():
    m=module();b,c,w=inputs();old,_=m.contexts(b,c,w,DAYS)
    b.loc[b.trade_date.ge(DAYS[6]) & b.tq_symbol.eq('SHFE.rb2005'),'close_oi']*=7
    new,_=m.contexts(b,c,w,DAYS)
    assert m.features_for_decision(old,DAYS[6],'rb2005.SHFE','rb.SHFE')==m.features_for_decision(new,DAYS[6],'rb2005.SHFE','rb.SHFE')


def test_common_oi_scale_does_not_change_features():
    m=module();b,c,w=inputs();old,_=m.contexts(b,c,w,DAYS);b['close_oi']*=2
    new,_=m.contexts(b,c,w,DAYS)
    pd.testing.assert_frame_equal(old,new)


def test_missing_lag_contract_is_not_replaced_with_previous_observation():
    m=module();b,c,w=inputs();b=b[~(b.tq_symbol.eq('SHFE.rb2005')&b.trade_date.eq(DAYS[0]))]
    context,inventory=m.contexts(b,c,w,DAYS)
    with pytest.raises(ValueError):m.features_for_decision(context,DAYS[6],'rb2005.SHFE','rb.SHFE')
    assert inventory.coverage_status.eq('actual_contract_window_missing').any()


def test_interior_missing_contract_day_also_blocks_window():
    m=module();b,c,w=inputs();b=b[~(b.tq_symbol.eq('SHFE.rb2005')&b.trade_date.eq(DAYS[3]))]
    context,_=m.contexts(b,c,w,DAYS)
    with pytest.raises(ValueError):m.features_for_decision(context,DAYS[6],'rb2005.SHFE','rb.SHFE')


def test_bad_chain_window_is_not_accepted():
    m=module();b,c,w=inputs();w.loc[w.decision_date.eq(DAYS[6]),'coverage_status']='incomplete_chain_window'
    context,_=m.contexts(b,c,w,DAYS)
    with pytest.raises(ValueError):m.features_for_decision(context,DAYS[6],'rb2005.SHFE','rb.SHFE')


@pytest.mark.parametrize('case',['duplicate','negative','nonfinite','zero_total','same_maturity'])
def test_bad_inputs_fail(case):
    b,c,w=inputs()
    if case=='duplicate': b=pd.concat([b,b.iloc[:1]],ignore_index=True)
    elif case=='negative': b.loc[0,'close_oi']=-1
    elif case=='nonfinite':b.loc[0,'close_oi']=float('nan')
    elif case=='zero_total':b.loc[b.trade_date.eq(DAYS[0]),'close_oi']=0
    else:c['delivery_month']=5
    with pytest.raises(ValueError):module().contexts(b,c,w,DAYS)


def test_lookup_rejects_wrong_product():
    m=module();b,c,w=inputs();context,_=m.contexts(b,c,w,DAYS)
    with pytest.raises(ValueError):m.features_for_decision(context,DAYS[6],'rb2005.SHFE','cu.SHFE')


def test_spec_only_appends_features():
    m=module();old={'features':['old'], 'estimator':{'max_depth':2},'action':'both_negative'};before=copy.deepcopy(old)
    new=m.candidate_spec(old)
    assert old==before and new=={**old,'features':['old',*m.FEATURES]}
