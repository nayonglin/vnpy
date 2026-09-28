import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage033b_holding_population.py'


def module():
    assert TOOL.exists(), 'holding population audit missing'
    spec = importlib.util.spec_from_file_location('test_population033b', TOOL)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def event(identity='a', **changes):
    return dict(event_id=identity, product_vt_symbol='rb.SHFE', decision_date='2021-01-01',
        first_fill_date='2021-01-04', end_date='2021-01-08', status='mature', direction='long', **changes)


def row(day='2021-01-04', status='stable_holding', product='rb.SHFE'):
    return dict(date=day, product_vt_symbol=product, actual_positions={'rb2105.SHFE':2.}, state_status=status)


def test_correlated_days_count_as_one_root_and_censored_is_not_mature():
    m=module();closed=event();opened=event('b')
    opened.update(first_fill_date='2021-01-11',decision_date='2021-01-08',end_date='',status='right_censored_open')
    rows=[row(),row('2021-01-05'),row('2021-01-06','target_position_mismatch'),row('2021-01-11')]
    linked,roots=m.group_roots(rows,pd.DataFrame([closed,opened]))
    assert len(linked)==4 and len(roots)==2
    assert roots.set_index('event_id').stable_observation_days.to_dict()=={'a':2,'b':1}
    months=m.monthly_population(roots,['2021-01-08','2021-02-01'])
    assert months.eligible_independent_roots.tolist()==[0,1]
    assert months.eligible_observation_days.tolist()==[0,2]


def test_cancelled_and_intraday_closed_roots_preserved_with_zero_stable_days():
    m=module();cancelled=event('cancel');cancelled.update(first_fill_date='',status='mature_cancelled_unfilled')
    intraday=event('day');intraday['end_date']=intraday['first_fill_date']
    linked,roots=m.group_roots([],pd.DataFrame([cancelled,intraday]))
    assert linked.empty and len(roots)==2 and roots.stable_observation_days.eq(0).all()


@pytest.mark.parametrize('kind',['unmapped','overlap','duplicate_id','direction','endpoint','pending_fill','duplicate_day'])
def test_invalid_lifecycle_assignment_fails_closed(kind):
    m=module();events=[event()];rows=[row()]
    if kind=='unmapped':rows[0]['product_vt_symbol']='cu.SHFE'
    elif kind=='overlap':events.append(event('b'))
    elif kind=='duplicate_id':events.append(event())
    elif kind=='direction':rows[0]['actual_positions']['rb2105.SHFE']=-2.
    elif kind=='endpoint':rows[0]['date']='2021-01-08'
    elif kind=='pending_fill':events[0]['first_fill_date']=''
    else:rows.append(row())
    with pytest.raises(RuntimeError):m.group_roots(rows,pd.DataFrame(events))


def test_fu_and_flat_do_not_create_holding_training_roots():
    m=module();flat=row();flat['actual_positions']={};flat['state_status']='flat'
    linked,roots=m.group_roots([flat,row(product='fu.SHFE')],pd.DataFrame([event()]))
    assert linked.empty and roots.stable_observation_days.tolist()==[0]


def test_unready_observations_do_not_qualify_a_root():
    m=module();_,roots=m.group_roots([row(status='pending_orders_or_close_inventory')],pd.DataFrame([event()]))
    assert roots.actual_holding_days.tolist()==[1] and roots.stable_observation_days.tolist()==[0]
    assert m.monthly_population(roots,['2021-02-01']).eligible_independent_roots.tolist()==[0]
