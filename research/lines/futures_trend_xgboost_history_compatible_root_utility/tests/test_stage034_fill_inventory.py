import copy
import importlib.util
from decimal import Decimal as D
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage034_fill_inventory.py'


def module():
    assert TOOL.exists(), 'fill inventory implementation missing'
    spec = importlib.util.spec_from_file_location('test_inventory034', TOOL)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def trade(i=1, direction='long', offset='open', price='100', volume='2', date='2020-01-02', symbol='rb.SHFE'):
    return dict(trade_id=f'BACKTESTING.{i}', datetime=date+' 00:00:00+08:00', date=date, vt_symbol=symbol,
        direction=direction, offset=offset, price=price, volume=volume,
        signed_volume=str(D(volume)*(1 if direction=='long' else -1)))


@pytest.mark.parametrize('direction',['long','short'])
def test_cost_average_reduce_flat_and_reopen(direction):
    m=module();p=m.Inventory();opposite='short' if direction=='long' else 'long'
    p.apply(trade(direction=direction));p.apply(trade(2,direction=direction,price='110',volume='2'))
    assert p.average==D('105') and abs(p.quantity)==4
    p.apply(trade(3,direction=opposite,offset='close',price='120',volume='1'))
    assert p.average==D('105') and abs(p.quantity)==3
    assert p.realized==D('15')*(1 if direction=='long' else -1)
    p.apply(trade(4,direction=opposite,offset='close',price='120',volume='3'))
    assert p.average==0 and p.quantity==0 and p.source_ids==[]
    p.apply(trade(5,direction=opposite,price='80',volume='1'))
    assert p.average==80 and p.source_ids==['BACKTESTING.5']


@pytest.mark.parametrize('change',['negative','nan','fraction','unknown_offset','unknown_direction','signed_mismatch','overclose','reverse_open'])
def test_invalid_fill_fails_closed(change):
    m=module();p=m.Inventory();p.apply(trade());bad=trade(2)
    if change=='negative':bad['price']='-1'
    elif change=='nan':bad['price']='NaN'
    elif change=='fraction':bad['volume']='0.5'
    elif change=='unknown_offset':bad['offset']='other'
    elif change=='unknown_direction':bad['direction']='other'
    elif change=='signed_mismatch':bad['signed_volume']='-2'
    elif change=='overclose':bad=trade(2,direction='short',offset='close',volume='3')
    else:bad=trade(2,direction='short')
    with pytest.raises(ValueError):p.apply(bad)


@pytest.mark.parametrize('change',['none','duplicate','gap','date_regression','wrong_id','datetime_day'])
def test_creation_sequence_not_export_clock_order(change):
    m=module();a,b=trade(),trade(2);a['datetime']='2020-01-02 10:00:00+08:00'
    values=[b,a]
    if change=='duplicate':values=[a,a]
    elif change=='gap':b['trade_id']='BACKTESTING.3'
    elif change=='date_regression':a['date']='2020-01-03';a['datetime']='2020-01-03 00:00:00+08:00'
    elif change=='wrong_id':b['trade_id']='untrusted.2'
    elif change=='datetime_day':b['datetime']='2020-01-03 00:00:00+08:00'
    if change=='none':assert [r['trade_id'] for r in m.ordered_trades(values)]==['BACKTESTING.1','BACKTESTING.2']
    else:
        with pytest.raises(ValueError):m.ordered_trades(values)


def positions():
    return [dict(date='2020-01-02',vt_symbol='rb.SHFE',start_pos='0',end_pos='2',close_price='105',
                 commission='0',slippage='2',net_pnl='98'),
            dict(date='2020-01-03',vt_symbol='rb.SHFE',start_pos='2',end_pos='0',close_price='110',
                 commission='0',slippage='2',net_pnl='98')]


def test_cashflow_and_inventory_reconcile_to_daily_ledger():
    m=module();t=[trade(),trade(2,direction='short',offset='close',price='110',date='2020-01-03')]
    records,days,quality=m.reconcile(t,positions(),{'rb.SHFE':10})
    assert records[0]['average_entry_price']=='100' and records[0]['quantity']=='2'
    assert records[0]['source_trade_ids']==['BACKTESTING.1']
    assert quality['max_pnl_error']==0 and quality['trade_count']==2
    assert days=={'2020-01-02':D(98),'2020-01-03':D(98)}


@pytest.mark.parametrize('change',['position','pnl','size','duplicate','missing_date'])
def test_reconciliation_rejects_ledger_or_unit_errors(change):
    m=module();p=positions();sizes={'rb.SHFE':10};t=[trade(),trade(2,direction='short',offset='close',price='110',date='2020-01-03')]
    if change=='position':p[0]['end_pos']='3'
    elif change=='pnl':p[1]['net_pnl']='99'
    elif change=='size':sizes={}
    elif change=='duplicate':p.append(copy.deepcopy(p[-1]))
    else:p=p[:1]
    with pytest.raises(ValueError):m.reconcile(t,p,sizes)


def test_future_fills_do_not_change_past_cost_snapshot():
    m=module();t=[trade(),trade(2,direction='short',offset='close',price='110',date='2020-01-03')]
    full=m.reconcile(t,positions(),{'rb.SHFE':10})[0]
    prefix=m.reconcile(t[:1],positions()[:1],{'rb.SHFE':10})[0]
    assert full[:1]==prefix


def test_snapshot_cost_evidence_is_external_and_original_marker_unchanged():
    m=module();observer=m.load('stage033_holding_observer')
    spec=importlib.util.spec_from_file_location('inventory_observer_fixture',ROOT/'tests/test_stage033_holding_observer.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    s,bars=fixture.fixture();s.states['rb.SHFE'].layers[0].entry_price_synced=False
    row=observer.snapshot(s,bars)[0];before=copy.deepcopy(row)
    inventory={'quantity':'2','average_entry_price':'101','source_trade_ids':['BACKTESTING.1']}
    assert m.cost_state(row,{'rb2105.SHFE':inventory})=='inventory_reconciled_holding'
    assert row==before and row['layers'][0]['entry_price']==100.
    row['active_orders']=[{}];row['state_status']='pending_orders_or_close_inventory'
    assert m.cost_state(row,{'rb2105.SHFE':inventory})=='pending_orders_or_close_inventory'
    with pytest.raises(ValueError):m.cost_state(before,{})


def test_short_partial_close_and_roll_keep_contract_costs_separate():
    m=module()
    fills=[trade(1,direction='short'),
        trade(2,offset='close',price='90',volume='1',date='2020-01-03'),
        trade(3,offset='close',price='85',volume='1',date='2020-01-06'),
        trade(4,direction='short',price='200',volume='1',date='2020-01-06',symbol='rb2.SHFE')]
    def pos(day,symbol,start,end,close,cost,pnl):
        return dict(date=day,vt_symbol=symbol,start_pos=start,end_pos=end,close_price=close,
            slippage=cost,commission='0',net_pnl=pnl)
    ledger=[pos('2020-01-02','rb.SHFE','0','-2','95','2','98'),
        pos('2020-01-03','rb.SHFE','-2','-1','90','1','99'),
        pos('2020-01-06','rb.SHFE','-1','0','85','1','49'),
        pos('2020-01-06','rb2.SHFE','0','-1','195','1','49')]
    records,days,quality=m.reconcile(fills,ledger,{'rb.SHFE':10,'rb2.SHFE':10})
    assert records[1]['average_entry_price']=='100' and records[-1]['average_entry_price']=='200'
    assert records[-1]['source_trade_ids']==['BACKTESTING.4']
    assert days['2020-01-06']==98 and quality['max_pnl_error']==0


def test_same_day_stop_and_retry_reset_cost_to_reentry_fill():
    m=module()
    fills=[trade(1),trade(2,direction='short',offset='close',price='95'),trade(3,price='101')]
    ledger=positions()[:1];ledger[0]['net_pnl']='-22'
    records,days,_=m.reconcile(fills,ledger,{'rb.SHFE':10})
    assert records[0]['source_trade_ids']==['BACKTESTING.3']
    assert records[0]['average_entry_price']=='101' and days['2020-01-02']==-22
