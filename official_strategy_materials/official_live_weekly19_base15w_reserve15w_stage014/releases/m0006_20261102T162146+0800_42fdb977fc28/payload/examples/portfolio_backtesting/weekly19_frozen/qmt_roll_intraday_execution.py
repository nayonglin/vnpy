"""Deterministic minute execution semantics (no alpha or parameter selection).

Minute bars are left-labelled Shanghai local time.  Stop/progress levels stay
continuous; executable prices use the adverse tick, with gap fills at the open.
OHLC does not prove an intraminute path: open is first, then adverse wins ties.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Any, Iterable
import re

import numpy as np
import pandas as pd

NIGHT_TO_23 = {'rb', 'hc', 'fu', 'ru', 'sp', 'jm', 'MA', 'OI', 'CF', 'FG', 'SA', 'SH'}
NIGHT_TO_01 = {'cu'}
NIGHT_TO_0230 = {'au'}
DAY_ONLY = {'AP', 'SM', 'si', 'lc', 'lh'}
EXECUTION_POLICY = 'session_v1_open_first_adverse_ties_retry_same_bar_stop_adverse_tick'


def local_timestamp(value: Any) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert('Asia/Shanghai').tz_localize(None)
    return stamp


def session_minutes(vt_symbol: str, trading_date: Any, calendar: Iterable[Any]) -> pd.DatetimeIndex:
    """The frozen 2020+ commodity schedule; holiday eves and COVID pause excluded.

    Calendar must include the preceding exchange trading day.  It is the actual
    daily mapping calendar, never a weekday calendar.  Friday night/Saturday
    early morning therefore belong to Monday, not their natural dates.
    """
    day = local_timestamp(trading_date).normalize()
    dates = sorted({local_timestamp(value).normalize() for value in calendar})
    if day not in dates:
        raise ValueError(f'intraday_calendar_missing:{vt_symbol}:{day.date()}')
    match = re.fullmatch(r'([A-Za-z]+)[0-9]+\.[A-Z]+', vt_symbol)
    product = match.group(1) if match else ''
    if product not in NIGHT_TO_23 | NIGHT_TO_01 | NIGHT_TO_0230 | DAY_ONLY:
        raise ValueError(f'intraday_unsupported_session:{vt_symbol}')
    parts = [pd.date_range(day + pd.Timedelta(minutes=first), periods=count, freq='min')
             for first, count in [(9*60,75), (10*60+30,60), (13*60+30,90)]]
    if product not in DAY_ONLY:
        earlier = [value for value in dates if value < day]
        if not earlier:
            raise ValueError(f'intraday_previous_trading_date_missing:{vt_symbol}:{day.date()}')
        previous = earlier[-1]
        gap = (day - previous).days
        active = gap == 1 or (previous.weekday() == 4 and day.weekday() == 0 and gap == 3)
        active = active and not (pd.Timestamp('2020-02-03') <= previous < pd.Timestamp('2020-05-06'))
        if active:
            count = 120 if product in NIGHT_TO_23 else 240 if product in NIGHT_TO_01 else 330
            parts.insert(0, pd.date_range(previous + pd.Timedelta(hours=21), periods=count, freq='min'))
    return pd.DatetimeIndex(np.concatenate([part.values for part in parts])).sort_values()


LC_TICK_CHANGE_DATE = pd.Timestamp('2024-12-18')
LC_TICK_SOURCE = 'GFEX_2024_337:2024-12-17_settlement:50_to_20'
LC_TICK_SOURCE_URL = 'https://www.ciccwmf.cn/gsgg/89279.jhtml'


def effective_pricetick(vt_symbol: str, trading_date: Any, configured_tick: float) -> float:
    """Execution-only historical specification; sizing/cost metadata is unchanged."""
    if re.fullmatch(r'lc[0-9]+\.GFEX', str(vt_symbol)) and local_timestamp(trading_date).normalize() < LC_TICK_CHANGE_DATE:
        return 50.0
    return float(configured_tick)


def pricetick_basis(vt_symbol: str) -> str:
    return LC_TICK_SOURCE if re.fullmatch(r'lc[0-9]+\.GFEX', str(vt_symbol)) else 'configured_contract_metadata'


def entry_session(strategy: Any, trade: Any) -> pd.DataFrame:
    day = local_timestamp(getattr(trade, 'trading_date', trade.datetime)).normalize()
    expected = session_minutes(str(trade.vt_symbol), day, strategy.available_trade_dates)
    actual_entry = getattr(trade, 'execution_datetime', None)
    if actual_entry is None:
        raise ValueError(f'intraday_execution_time_missing:{trade.vt_symbol}:{day.date()}')
    entry = local_timestamp(actual_entry)
    if entry not in expected:
        raise ValueError(f'intraday_execution_outside_session:{trade.vt_symbol}:{day.date()}:{entry}')
    requested = expected[expected >= entry]
    frame = strategy.stage827_minute_by_symbol.get(str(trade.vt_symbol), pd.DataFrame())
    if not frame.empty:
        moments = pd.to_datetime(frame['bar_datetime'])
        if moments.dt.tz is not None:
            moments = moments.dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
        frame = frame.loc[moments.isin(requested)].copy()
        frame['bar_datetime'] = moments.loc[frame.index]
        frame = frame.sort_values('bar_datetime')
        if frame['bar_datetime'].duplicated().any():
            raise ValueError(f'intraday_duplicate_minute:{trade.vt_symbol}:{day.date()}')
    observed = set(frame['bar_datetime']) if not frame.empty else set()
    missing = [stamp for stamp in requested if stamp not in observed]
    request = {
        'vt_symbol': str(trade.vt_symbol), 'trading_date': day.date().isoformat(),
        'execution_datetime': entry.isoformat(), 'session_start': expected[0].isoformat(),
        'session_end_exclusive': (expected[-1] + pd.Timedelta(minutes=1)).isoformat(),
        'requested_start': entry.isoformat(), 'expected_bar_count': len(requested),
        'actual_bar_count': len(frame), 'missing_bar_count': len(missing),
        'actual_first_time': frame['bar_datetime'].iloc[0].isoformat() if not frame.empty else '',
        'actual_last_time': frame['bar_datetime'].iloc[-1].isoformat() if not frame.empty else '',
        'coverage_status': 'complete' if not missing else 'incomplete',
        'execution_policy': EXECUTION_POLICY,
    }
    if not hasattr(strategy, 'minute_scan_requests'):
        strategy.minute_scan_requests = []
    strategy.minute_scan_requests.append(request)
    if missing and getattr(strategy, 'stage827_require_complete_minutes', True):
        raise ValueError(f'intraday_minute_coverage:{trade.vt_symbol}:{day.date()}:missing={len(missing)}')
    if not frame.empty:
        prices = frame[['open', 'high', 'low', 'close']].to_numpy(dtype=float)
        valid = np.isfinite(prices).all() and (prices > 0).all()
        valid = valid and bool((frame['low'] <= frame[['open', 'close']].min(axis=1)).all())
        valid = valid and bool((frame['high'] >= frame[['open', 'close']].max(axis=1)).all())
        if not valid:
            raise ValueError(f'intraday_invalid_ohlc:{trade.vt_symbol}:{day.date()}')
    return frame.reset_index(drop=True)


def adverse_tick(price: float, tick: float, *, buy: bool) -> float:
    if not np.isfinite(price) or not np.isfinite(tick) or price <= 0 or tick <= 0:
        raise ValueError('intraday_invalid_price_or_tick')
    units = Decimal(str(price)) / Decimal(str(tick))
    nearest = units.to_integral_value()
    if abs(units - nearest) <= Decimal('0.000000001'):
        units = nearest
    rounded = units.to_integral_value(rounding=ROUND_CEILING if buy else ROUND_FLOOR)
    return float(rounded * Decimal(str(tick)))


def stop_fill(item: Any, threshold: float, tick: float, *, buy: bool, use_open: bool = True) -> tuple[float, str]:
    opening, high, low = float(item['open']), float(item['high']), float(item['low'])
    crossed_at_open = opening >= threshold if buy else opening <= threshold
    price = opening if use_open and crossed_at_open else threshold
    price = adverse_tick(price, tick, buy=buy)
    tolerance = max(tick * 1e-7, 1e-8)
    if not all(np.isfinite(value) for value in [opening, high, low]) or low > high or price < low-tolerance or price > high+tolerance:
        raise ValueError(f'intraday_unreachable_fill:{price}:{low}:{high}')
    return price, 'gap_open' if use_open and crossed_at_open else 'threshold_adverse_tick'


def first_stop(frame: pd.DataFrame, stop: float, progress: float, *, long: bool) -> tuple[int, str]:
    for index, item in frame.iterrows():
        opening = float(item['open'])
        stop_at_open = opening <= stop if long else opening >= stop
        progress_at_open = opening >= progress if long else opening <= progress
        if stop_at_open:
            return index, 'stop_at_open'
        if progress_at_open:
            return -1, 'progress_at_open_before_intrabar_stop'
        adverse = float(item['low']) <= stop if long else float(item['high']) >= stop
        advanced = float(item['high']) >= progress if long else float(item['low']) <= progress
        if adverse:
            return index, 'same_bar_conservative_stop_first' if advanced else 'adverse_before_progress'
        if advanced:
            return -1, 'progress_before_stop'
    return -1, 'no_trigger'
