import importlib.util
from pathlib import Path

import pandas as pd
import pytest


ROOT=Path(__file__).resolve().parents[1]
TOOL=ROOT/'tools/stage035_next_window.py'


def module():
    assert TOOL.exists(),'next window audit missing'
    spec=importlib.util.spec_from_file_location('test_window035',TOOL)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def bars(time='2021-01-08 21:00:00',volume=10):
    return pd.DataFrame([dict(bar_datetime=pd.Timestamp(time),open=100.,high=101.,low=99.,close=100.,volume=volume)])


def test_night_window_precedes_monday_calendar_day_and_excludes_previous_close():
    m=module();frame=pd.concat([bars('2021-01-08 14:59:00'),bars(),bars('2021-01-11 09:00:00')])
    result=m.evaluate(frame,'2021-01-08','2021-01-11',True,2)
    assert result['status']=='proxy_supported' and result['window']=='night'
    assert result['first_time']=='2021-01-08T21:00:00'


def test_no_night_record_allows_next_day_but_zero_volume_does_not():
    m=module();day=bars('2021-01-11 09:00:00')
    assert m.evaluate(day,'2021-01-08','2021-01-11',True,2)['window']=='day'
    frame=pd.concat([bars(volume=0),day])
    result=m.evaluate(frame,'2021-01-08','2021-01-11',True,2)
    assert result['status']=='first_bar_volume_insufficient' and result['window']=='night'


@pytest.mark.parametrize('kind',['nan','ohlc','volume','same_time_conflict'])
def test_bad_first_bar_not_replaced_by_later_good_prices(kind):
    m=module();frame=bars()
    if kind=='nan':frame.loc[0,'open']=float('nan')
    elif kind=='ohlc':frame.loc[0,'high']=90.
    elif kind=='volume':frame.loc[0,'volume']=-1.
    else:frame=pd.concat([frame,frame.assign(open=100.5)])
    frame=pd.concat([frame,bars('2021-01-08 21:01:00')])
    assert m.evaluate(frame,'2021-01-08','2021-01-11',True,2)['status']!='proxy_supported'


def test_identical_duplicates_are_not_more_capacity():
    m=module();frame=pd.concat([bars(volume=1),bars(volume=1)])
    result=m.evaluate(frame,'2021-01-08','2021-01-11',True,2)
    assert result['status']=='first_bar_volume_insufficient' and result['bar_count']==1


def test_missing_windows_are_explicit_and_do_not_use_observation_day_open():
    m=module();frame=bars('2021-01-08 09:00:00')
    assert m.evaluate(frame,'2021-01-08','2021-01-11',False,2)['status']=='window_missing'
    assert m.evaluate(frame,'2021-01-08',None,False,2)['status']=='no_next_calendar_day'


def test_five_minute_end_is_exclusive():
    m=module();frame=bars('2021-01-11 09:05:00')
    assert m.evaluate(frame,'2021-01-08','2021-01-11',False,2)['status']=='window_missing'


@pytest.mark.parametrize('value',[None,'not-a-time'])
def test_unlocatable_timestamp_fails_instead_of_silently_disappearing(value):
    m=module()
    with pytest.raises(ValueError):m.parse_clock(pd.Series([value]))


def test_explicit_utc_clock_is_converted_to_local_session():
    m=module();result=m.parse_clock(pd.Series(['2021-01-08T13:00:00+00:00']))
    assert result.iloc[0]==pd.Timestamp('2021-01-08 21:00:00') and result.dt.tz is None
