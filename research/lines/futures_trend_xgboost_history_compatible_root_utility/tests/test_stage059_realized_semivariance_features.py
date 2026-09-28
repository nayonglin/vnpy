import copy
import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    path = ROOT / 'tools' / (name + '.py')
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('test_rsv059_' + name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
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


def test_formula_exists_and_has_exact_sign_decomposition():
    m = load('stage059_realized_semivariance_features')
    assert m is not None, 'semivariance implementation missing'
    bars, expected, job, reference = inputs()
    values, samples = m.features_for_day(bars, expected, job, reference, set())
    assert values[m.FEATURES[0]] == pytest.approx(math.log(1.1) ** 2)
    assert values[m.FEATURES[1]] == 0
    assert values['sample_count'] == len(samples) == 12
    assert values['asof_close'] == '2020-01-06T15:00:00'
    assert samples[-1]['sample_end'] == '2020-01-06T15:00:00'


def test_same_daily_tail_and_total_variance_still_different_semivariances():
    m = load('stage059_realized_semivariance_features'); late = load('stage052_late_session_features')
    bars, expected, job, reference = inputs()
    a = bars.copy(); a.loc[4, 'close'] = 110.; a.loc[9, 'close'] = 90.
    b = bars.copy(); b.loc[4, 'close'] = 90.; b.loc[9, 'close'] = 110.
    av, _ = m.features_for_day(a, expected, job, reference, set())
    bv, _ = m.features_for_day(b, expected, job, reference, set())
    assert late.features_for_day(a, expected, job, reference, set()) == late.features_for_day(b, expected, job, reference, set())
    assert av['realized_variance_5m'] == pytest.approx(bv['realized_variance_5m'], abs=1e-14)
    assert abs(av[m.FEATURES[0]] - bv[m.FEATURES[0]]) > .001
    assert abs(av[m.FEATURES[1]] - bv[m.FEATURES[1]]) > .001


def test_short_swaps_components_and_price_scale_invariant_without_mutation():
    m = load('stage059_realized_semivariance_features')
    bars, expected, job, reference = inputs(); before = bars.copy(deep=True)
    long, _ = m.features_for_day(bars, expected, job, reference, set())
    job['snapshot']['actual_positions']['aa2005.X'] = -2.
    short, _ = m.features_for_day(bars, expected, job, reference, set())
    assert short[m.FEATURES[0]] == long[m.FEATURES[1]]
    assert short[m.FEATURES[1]] == long[m.FEATURES[0]]
    scaled = bars.copy()
    for name in ['open', 'high', 'low', 'close']:
        scaled[name] *= 17
        reference[name] *= 17
        job['snapshot']['bar'][name + '_price'] *= 17
    out, _ = m.features_for_day(scaled, expected, job, reference, set())
    for name in m.FEATURES:
        assert out[name] == pytest.approx(short[name], abs=1e-14)
    pd.testing.assert_frame_equal(bars, before)


def test_explicit_zero_volume_grid_uses_only_previously_observed_trade():
    m = load('stage059_realized_semivariance_features'); bars, expected, job, reference = inputs()
    bars.loc[5:9, 'volume'] = 0
    bars.loc[4, 'close'] = 105.
    bars.loc[5:9, ['open', 'high', 'low', 'close']] = 105.
    reference['volume'] = job['snapshot']['bar']['volume'] = 55.
    values, samples = m.features_for_day(bars, expected, job, reference, set())
    assert values['zero_trade_grid_count'] == 1
    assert samples[1]['close'] == 105.
    assert samples[1]['source_end'] == '2020-01-06T14:05:00'
    assert samples[1]['log_return'] == 0.


def test_night_and_reopening_gap_kept_but_future_day_ignored():
    m = load('stage059_realized_semivariance_features'); bars, expected, job, reference = inputs()
    night = bars.iloc[:5].copy(); night['bar_datetime'] = pd.date_range('2020-01-03 21:00', periods=5, freq='min')
    night['close'] = 95.
    allbars = pd.concat([night, bars]); clock = allbars[expected.columns].copy()
    reference['volume'] = job['snapshot']['bar']['volume'] = 65.
    values, samples = m.features_for_day(allbars, clock, job, reference, set())
    assert values['segment_count'] == 2 and values['sample_count'] == 13
    assert samples[1]['log_return'] == pytest.approx(math.log(100 / 95))
    assert samples[0]['sample_end'] == '2020-01-03T21:05:00'
    future = bars.copy(); future['bar_date'] = '2020-01-07'; future['bar_datetime'] += pd.Timedelta(days=1)
    future[['open', 'high', 'low', 'close', 'volume']] = 'not_numeric_future'
    out = m.features_for_day(pd.concat([allbars, future]), pd.concat([clock, future[expected.columns]]), job, reference, set())
    assert out == (values, samples)


@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'off_grid', 'after_close', 'wrong_symbol', 'wrong_day',
    'guard', 'bad_ohlc', 'nonfinite', 'negative_volume', 'leading_zero_volume', 'daily_volume', 'daily_close',
    'supplier', 'phase', 'zero_position', 'fractional_position', 'multiple_positions',
    'incomplete_expected', 'not_five_minute_segment', 'first_open'])
def test_invalid_source_is_not_filled_or_removed(kind):
    m = load('stage059_realized_semivariance_features'); bars, expected, job, reference = inputs(); guards = set()
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
    elif kind == 'leading_zero_volume':
        bars.loc[0, 'volume'] = 0.; reference['volume'] = job['snapshot']['bar']['volume'] = 59.
    elif kind == 'daily_volume': job['snapshot']['bar']['volume'] += 1
    elif kind == 'daily_close': job['snapshot']['bar']['close_price'] += 1
    elif kind == 'supplier': reference['close'] += 1
    elif kind == 'phase': job['snapshot']['phase'] = 'before_strategy_on_bars'
    elif kind == 'zero_position': job['snapshot']['actual_positions']['aa2005.X'] = 0.
    elif kind == 'fractional_position': job['snapshot']['actual_positions']['aa2005.X'] = .5
    elif kind == 'multiple_positions': job['snapshot']['actual_positions']['bb2005.X'] = 1.
    elif kind == 'incomplete_expected': expected = expected.drop(index=30); bars = bars.drop(index=30)
    elif kind == 'not_five_minute_segment':
        bars = bars.drop(index=0); expected = expected.drop(index=0)
        reference['volume'] = job['snapshot']['bar']['volume'] = 59.
    elif kind == 'first_open': bars.loc[0, 'volume'] = 0.; bars.loc[0, 'open'] = 99.
    with pytest.raises((RuntimeError, ValueError)):
        m.features_for_day(bars, expected, job, reference, guards)


def test_flat_observed_prices_are_valid_zero_not_missing():
    m = load('stage059_realized_semivariance_features'); bars, expected, job, reference = inputs()
    bars[['open', 'high', 'low', 'close']] = 100.
    for k in ['open', 'high', 'low', 'close']:
        reference[k] = job['snapshot']['bar'][k + '_price'] = 100.
    values, _ = m.features_for_day(bars, expected, job, reference, set())
    assert values['realized_variance_5m'] == 0.
    assert all(values[k] == 0. for k in m.FEATURES)


def test_spec_appends_only_signed_components_to_original_nine():
    m = load('stage059_realized_semivariance_features')
    base = {'features': list(m.BASE_FEATURES), 'minimum_mature_roots': 60, 'estimator': {'max_depth': 2},
        'targets': ['return_marginal', 'drawdown_marginal']}
    before = copy.deepcopy(base); result = m.candidate_spec(base)
    assert result == {**base, 'features': [*base['features'], *m.FEATURES]}
    assert before == base
    with pytest.raises(RuntimeError): m.candidate_spec(result)
