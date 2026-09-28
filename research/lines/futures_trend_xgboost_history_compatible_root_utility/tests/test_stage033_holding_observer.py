import copy
import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT/'tools/stage033_holding_observer.py'


def module():
    assert TOOL.exists(), 'holding observer missing'
    spec = importlib.util.spec_from_file_location('test_observer033', TOOL)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fixture(direction='long'):
    sign = 1 if direction=='long' else -1
    layer = NS(kind='base',direction=direction,volume=2,entry_price=100.,stop_price=95.,
        highest_price=106.,lowest_price=99.,entry_date='2021-01-04',max_profit_pct=.06,
        entry_price_synced=True,profit_giveback_stop_active=False)
    state = NS(product_vt_symbol='rb.SHFE',contract_vt_symbol='rb2105.SHFE',direction=direction,
        entry_date='2021-01-04',bars_since_entry=5,prev2day_stop_price=None,rollover_pending_target_contract='',
        rsi_partial_exit_done=False,layers=[layer])
    bar = NS(datetime=datetime(2021,1,11),open_price=104.,high_price=106.,low_price=103.,close_price=105.,
        volume=100.,open_interest=200.,interval='DAILY')
    engine = NS(datetime=bar.datetime,active_limit_orders={})
    strategy = NS(states={'rb.SHFE':state},pos_data={'rb2105.SHFE':2*sign},target_data={'rb2105.SHFE':2*sign},
        source_symbol_by_contract={'rb2105.SHFE':'rb.SHFE','rb2110.SHFE':'rb.SHFE'},strategy_engine=engine,
        pending_close_lots={},pending_close_reasons={},estimated_equity=200000.,total_margin_in_use=20000.,loss_streak=1)
    return strategy,{'rb2105.SHFE':bar}


@pytest.mark.parametrize('direction',['long','short'])
def test_stable_state_snapshot_is_readonly_and_retains_real_positions(direction):
    m=module();strategy,bars=fixture(direction);before=copy.deepcopy(strategy)
    row=m.snapshot(strategy,bars)[0]
    assert strategy==before
    assert row['state_status']=='stable_holding'
    assert row['actual_positions']['rb2105.SHFE']==(2 if direction=='long' else -2)
    assert row['layers'][0]['entry_price_synced'] is True
    assert row['bar']['close_price']==105.
    json.dumps(row,allow_nan=False)


@pytest.mark.parametrize('kind,expected',[
    ('order','pending_orders_or_close_inventory'),('close_lot','pending_orders_or_close_inventory'),
    ('target','target_position_mismatch'),('multi','multiple_actual_contracts'),
    ('missing_bar','missing_current_bar'),('state_contract','state_contract_or_direction_mismatch'),
    ('layer_volume','layer_position_mismatch'),('unsynced','layer_not_synchronized'),
    ('future_bar','missing_current_bar'),('roll','rollover_pending'),('flat','flat')])
def test_unready_states_are_retained_not_zero_filled(kind,expected):
    m=module();s,bars=fixture();state=s.states['rb.SHFE']
    if kind=='order':
        s.strategy_engine.active_limit_orders['o']=NS(vt_symbol='rb2105.SHFE',direction='SHORT',offset='CLOSE',volume=2,traded=0,status='NOTTRADED',price=105.,datetime=datetime(2021,1,11))
    elif kind=='close_lot':s.pending_close_lots['rb2105.SHFE']=[{'volume':2}]
    elif kind=='target':s.target_data['rb2105.SHFE']=0
    elif kind=='multi':s.pos_data['rb2110.SHFE']=1
    elif kind=='missing_bar':bars={}
    elif kind=='state_contract':state.contract_vt_symbol='rb2110.SHFE'
    elif kind=='layer_volume':state.layers[0].volume=1
    elif kind=='unsynced':state.layers[0].entry_price_synced=False
    elif kind=='future_bar':bars['rb2105.SHFE'].datetime=datetime(2021,1,12)
    elif kind=='roll':state.rollover_pending_target_contract='rb2110.SHFE'
    else:s.pos_data={};s.target_data={};state.layers=[];state.contract_vt_symbol='';state.direction=''
    row=m.snapshot(s,bars)[0]
    assert row['state_status']==expected
    if kind in ('missing_bar','future_bar'):assert row['bar'] is None


def test_unfilled_plan_is_not_flat_or_a_real_position():
    m=module();s,bars=fixture();s.pos_data={}
    row=m.snapshot(s,bars)[0]
    assert row['state_status']=='unfilled_or_inconsistent_plan'
    assert row['actual_positions']=={} and row['targets']=={'rb2105.SHFE':2.}


def test_nonfinite_position_fails_instead_of_imputation():
    m=module();s,bars=fixture();s.pos_data['rb2105.SHFE']=float('nan')
    with pytest.raises(ValueError,match='nonfinite'):m.snapshot(s,bars)


def test_unknown_nonzero_contract_is_not_silently_lost():
    m=module();s,bars=fixture();s.pos_data['bad.SHF']=1
    with pytest.raises(ValueError,match='unknown_contract'):m.snapshot(s,bars)


def test_observer_calls_parent_once_preserves_return_and_restores_inherited_method():
    m=module();s,bars=fixture();rows=[];calls=[]
    class Parent:
        def on_bars(self,bars):calls.append('call');return 19
    class Child(Parent):pass
    instance=Child();instance.__dict__.update(s.__dict__)
    restore=m.install_observer(Child,rows)
    try:
        assert instance.on_bars(bars)==19
        assert calls==['call'] and len(rows)==1
    finally:restore()
    assert 'on_bars' not in Child.__dict__ and Child.on_bars is Parent.on_bars


def test_failed_parent_does_not_emit_completed_snapshot():
    m=module();s,bars=fixture();rows=[]
    class Strategy:
        def on_bars(self,bars):raise RuntimeError('parent_failed')
    instance=Strategy();instance.__dict__.update(s.__dict__)
    restore=m.install_observer(Strategy,rows)
    try:
        with pytest.raises(RuntimeError,match='parent_failed'):instance.on_bars(bars)
        assert rows==[]
    finally:restore()


def test_bootstrap_has_no_site_imports():
    module()
    code='import runpy,sys; m=runpy.run_path('+repr(str(TOOL))+ "); m['configured'](input_count=123); assert 'numpy' not in sys.modules and 'xgboost' not in sys.modules"
    result=subprocess.run([sys.executable,'-I','-S','-B','-c',code],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_existing_campaign_rejected_before_preflight(tmp_path,monkeypatch):
    m=module();monkeypatch.setattr(m,'OUTPUT',tmp_path)
    monkeypatch.setattr(m,'configured',lambda **kw:pytest.fail('preflight unexpectedly called'))
    with pytest.raises(RuntimeError,match='already_exists'):m.run_parent()


def test_observation_uses_plain_a_worker_without_entry_gate():
    m=module()
    base,_=m.configured(input_count=123)
    assert base.intervention.__module__=='batch_worker_base'
    assert m.WORKER_ARM=='A'
    result=subprocess.run([sys.executable,'-I','-S','-B',str(TOOL),'--worker','--arm','A0'],capture_output=True,text=True)
    assert result.returncode==2 and 'invalid choice' in result.stderr


@pytest.mark.parametrize('change',['none','classification','duplicate','position','calendar','phase'])
def test_trace_qualification_checks_raw_state_and_ledger(change):
    import pandas as pd
    m=module();s,bars=fixture();rows=m.snapshot(s,bars)
    daily=pd.DataFrame({'date':['2021-01-11']})
    positions=pd.DataFrame({'date':['2021-01-11'],'vt_symbol':['rb2105.SHFE'],'end_pos':[2.]})
    if change=='classification':rows[0]['state_status']='flat'
    elif change=='duplicate':rows.append(copy.deepcopy(rows[0]))
    elif change=='position':positions.loc[0,'end_pos']=3.
    elif change=='calendar':daily.loc[0,'date']='2021-01-12'
    elif change=='phase':rows[0]['phase']='before_strategy_on_bars'
    if change=='none':
        result=m.qualify_trace(rows,daily,positions)
        assert result['actual_positions_exact'] and result['state_status_counts']=={'stable_holding':1}
    else:
        with pytest.raises(RuntimeError,match='observer_'):m.qualify_trace(rows,daily,positions)
