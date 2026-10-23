"""Declared daily-K open execution model, with a calendar-only physical clock.

Completed weekly entries arrive on the next trading day's daily K, the first
K of the next trading week; daily risk exits arrive on the next daily K. The
price is exactly that real daily BarData.open_price. No minute quote, proxy or
original order-context method is read. The clock is a modeling convention,
not evidence that a minute quote, spread, queue or capacity was confirmed.
"""
from __future__ import annotations
import math
import pandas as pd
from stage005_sessions import canonical_open_timestamp

MODEL='declared_daily_bar_open_model'


def _local_stamp(value):
    stamp=pd.Timestamp(value)
    if pd.isna(stamp):raise ValueError('missing_bar_open_model_timestamp')
    return stamp.tz_convert('Asia/Shanghai').tz_localize(None) if stamp.tzinfo else stamp


def bar_open_order_context(engine,order,bar,calendar):
    """Build Stage827-compatible context and append a declared-model receipt.

    Caller must supply the immutable daily data calendar and a real daily bar.
    All validation happens before recording a request. No signals, indicators,
    sizing, stop conditions, commission or slippage are changed here.
    """
    trading_day=_local_stamp(engine.datetime).normalize()
    signal_day=_local_stamp(order.datetime).normalize()
    bar_day=_local_stamp(bar.datetime).normalize()
    symbol=str(order.vt_symbol)
    if str(bar.vt_symbol)!=symbol:raise ValueError('daily_bar_symbol_mismatch:'+symbol)
    interval=getattr(bar.interval,'value',bar.interval)
    if interval!='d':raise ValueError('daily_bar_interval_required:'+symbol)
    if bar_day!=trading_day:raise ValueError('stale_daily_bar:'+symbol)
    dates=sorted({_local_stamp(day).normalize() for day in calendar})
    if trading_day not in dates or signal_day not in dates:
        raise ValueError('bar_open_calendar_day_missing:'+symbol)
    next_dates=[day for day in dates if day>signal_day]
    if not next_dates or trading_day!=next_dates[0]:
        raise ValueError('next_trading_day_required:'+symbol)
    try:
        opening,high,low,close=[float(getattr(bar,name)) for name in ['open_price','high_price','low_price','close_price']]
    except (ValueError,TypeError,AttributeError) as exc:
        raise ValueError('invalid_daily_bar_ohlc:'+symbol) from exc
    if not all(math.isfinite(value) and value>0 for value in [opening,high,low,close]) or low>min(opening,close) or high<max(opening,close) or low>high:
        raise ValueError('invalid_daily_bar_ohlc:'+symbol)
    try:volume=float(bar.volume)
    except (ValueError,TypeError,AttributeError) as exc:
        raise ValueError('invalid_daily_bar_volume:'+symbol) from exc
    if not math.isfinite(volume) or volume<=0:raise ValueError('invalid_daily_bar_volume:'+symbol)
    # This helper computes calendar convention only; it loads no minute rows.
    timestamp=canonical_open_timestamp(symbol,trading_day,dates)
    offset=getattr(order.offset,'value',order.offset)
    request=dict(vt_symbol=symbol,trading_date=trading_day.date().isoformat(),signal_date=signal_day.date().isoformat(),
        expected_start=timestamp.isoformat(),actual_time=timestamp.isoformat(),source=MODEL,price=opening,
        execution_model=MODEL,minute_quote_confirmed=False,minute_rows_read=0,anchor_present=False,
        daily_bar_present=True,daily_bar_datetime=_local_stamp(bar.datetime).isoformat(),daily_volume=volume,
        daily_open=opening,daily_high=high,daily_low=low,daily_close=close,
        clock_basis='calendar_session_open_model_only_not_minute_quote_confirmed',coverage_status=MODEL,
        order_id=str(order.vt_orderid),offset=str(offset),corrected_legacy_proxy=False,
        legacy_time='',legacy_price=None,legacy_source='not_consulted')
    if not hasattr(engine,'execution_anchor_requests'):engine.execution_anchor_requests=[]
    engine.execution_anchor_requests.append(request)
    proxy=dict(proxy_price=opening,proxy_bar_count=0,proxy_first_time='',proxy_last_time='',
        execution_model=MODEL,minute_quote_confirmed=False,daily_bar_count=1)
    return dict(price=opening,source=MODEL,proxy=proxy,execution_datetime=timestamp,trading_date=trading_day.date(),
        execution_time_source='calendar_session_open_model_clock',anchor_coverage_status=MODEL,
        expected_session_start=timestamp.isoformat(),corrected_legacy_proxy=False,legacy_proxy_time='',legacy_proxy_price=None,
        execution_model=MODEL,execution_policy=MODEL,minute_quote_confirmed=False,minute_rows_read=0)
