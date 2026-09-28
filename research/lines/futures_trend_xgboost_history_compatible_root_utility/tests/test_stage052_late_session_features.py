import copy
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/stage052_late_session_features.py'
    assert path.exists(), 'late session feature implementation missing'
    spec = importlib.util.spec_from_file_location('test_late052', path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def inputs():
    times = pd.date_range('2020-01-06 14:00', periods=60, freq='min')
    bars = pd.DataFrame({'vt_symbol': 'aa2005.X', 'bar_datetime': times,
        'bar_date': '2020-01-06', 'open': 100., 'high': 120., 'low': 90., 'close': 100., 'volume': 1.})
    bars.loc[59, 'close'] = 110.
    expected = bars[['vt_symbol', 'bar_datetime', 'bar_date']].copy()
    reference = {'open': 100., 'high': 120., 'low': 90., 'close': 110., 'volume': 60.}
    job = {'date': '2020-01-06', 'vt_symbol': 'aa2005.X', 'product_vt_symbol': 'aa.X',
        'snapshot': {'phase': 'after_strategy_on_bars', 'actual_positions': {'aa2005.X': 2.},
            'bar': {'vt_symbol': 'aa2005.X', 'datetime': '2020-01-06T00:00:00+08:00',
                **{k + '_price': v for k, v in reference.items() if k != 'volume'}, 'volume': 60.}}}
    return bars, expected, job, reference


def test_fixed_last_half_hour_and_short_symmetry_without_mutating_input():
    m = module(); bars, expected, job, reference = inputs()
    before = bars.copy(deep=True)
    values = m.features_for_day(bars, expected, job, reference, set())
    assert values['directional_late_return_30m'] == pytest.approx(.1)
    assert values['late_volume_fraction_30m'] == .5
    assert values['last_minute'] == '2020-01-06T14:59:00'
    assert values['late_minute_count'] == 30
    job['snapshot']['actual_positions']['aa2005.X'] = -2.
    short = m.features_for_day(bars, expected, job, reference, set())
    assert short['directional_late_return_30m'] == -values['directional_late_return_30m']
    assert short['late_volume_fraction_30m'] == values['late_volume_fraction_30m']
    pd.testing.assert_frame_equal(bars, before)


def test_same_daily_ohlcv_can_encode_different_late_information():
    m = module(); bars, expected, job, reference = inputs()
    first = m.features_for_day(bars, expected, job, reference, set())
    changed = bars.copy(); changed.loc[30, 'open'] = 105.
    changed.loc[1:29, 'volume'] = .5
    changed.loc[30:58, 'volume'] = 1.5
    second = m.features_for_day(changed, expected, job, reference, set())
    assert second['directional_late_return_30m'] != first['directional_late_return_30m']
    assert second['late_volume_fraction_30m'] != first['late_volume_fraction_30m']


def test_future_days_are_ignored_and_night_session_uses_trading_day_not_natural_day():
    m = module(); bars, expected, job, reference = inputs()
    baseline = m.features_for_day(bars, expected, job, reference, set())
    future = bars.copy(); future['bar_date'] = '2020-01-07'; future['bar_datetime'] += pd.Timedelta(days=1)
    future[['open','high','low','close','volume']] = np.nan
    assert m.features_for_day(pd.concat([bars, future]), pd.concat([expected, future[expected.columns]]), job, reference, set()) == baseline
    night = bars.iloc[:1].copy(); night['bar_datetime'] = pd.Timestamp('2020-01-03 21:00')
    reference['volume'] += 1; job['snapshot']['bar']['volume'] += 1
    out = m.features_for_day(pd.concat([night, bars]), pd.concat([night[expected.columns], expected]), job, reference, set())
    assert out['late_volume_fraction_30m'] == pytest.approx(30 / 61)
    assert out['day_minute_count'] == 61


@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'off_grid', 'after_close', 'wrong_symbol', 'wrong_day',
    'guard', 'bad_ohlc', 'nonfinite', 'negative_volume', 'zero_late', 'daily_volume', 'daily_close',
    'supplier', 'phase', 'zero_position', 'multiple_positions', 'incomplete_expected'])
def test_invalid_current_window_cannot_be_filled_or_silently_accepted(kind):
    m = module(); bars, expected, job, reference = inputs(); guards = set()
    if kind == 'missing': bars = bars.drop(index=30)
    elif kind == 'duplicate': bars = pd.concat([bars, bars.iloc[-1:]])
    elif kind == 'off_grid':
        bars.loc[30, 'bar_datetime'] += pd.Timedelta(seconds=1)
        expected.loc[30, 'bar_datetime'] += pd.Timedelta(seconds=1)
    elif kind == 'after_close':
        bars.loc[59, 'bar_datetime'] += pd.Timedelta(minutes=1)
        expected.loc[59, 'bar_datetime'] += pd.Timedelta(minutes=1)
    elif kind == 'wrong_symbol': bars.loc[0, 'vt_symbol'] = 'other.X'
    elif kind == 'wrong_day': bars.loc[30, 'bar_date'] = '2020-01-07'
    elif kind == 'guard': guards.add(('aa2005.X', '2020-01-06'))
    elif kind == 'bad_ohlc': bars.loc[3, 'low'] = 200.
    elif kind == 'nonfinite': bars.loc[3, 'close'] = np.nan
    elif kind == 'negative_volume': bars.loc[3, 'volume'] = -1.
    elif kind == 'zero_late': bars.loc[30:, 'volume'] = 0.; reference['volume'] = job['snapshot']['bar']['volume'] = 30.
    elif kind == 'daily_volume': job['snapshot']['bar']['volume'] += 1
    elif kind == 'daily_close': job['snapshot']['bar']['close_price'] += 1
    elif kind == 'supplier': reference['close'] += 1
    elif kind == 'phase': job['snapshot']['phase'] = 'before_strategy_on_bars'
    elif kind == 'zero_position': job['snapshot']['actual_positions']['aa2005.X'] = 0.
    elif kind == 'multiple_positions': job['snapshot']['actual_positions']['bb2005.X'] = 1.
    elif kind == 'incomplete_expected': expected = expected.drop(index=30); bars = bars.drop(index=30)
    with pytest.raises((RuntimeError, ValueError)):
        m.features_for_day(bars, expected, job, reference, guards)


def test_candidate_spec_only_appends_two_features():
    m = module()
    base = {'features': list(m.BASE_FEATURES), 'minimum_mature_roots': 60, 'estimator': {'max_depth': 2},
        'targets': ['return_marginal','drawdown_marginal'], 'threshold': 0}
    saved = copy.deepcopy(base); spec = m.candidate_spec(base)
    assert spec == {**base, 'features': [*base['features'], *m.FEATURES]}
    assert base == saved
    with pytest.raises(RuntimeError): m.candidate_spec(spec)
