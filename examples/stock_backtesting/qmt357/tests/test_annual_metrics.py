import pandas as pd
import pytest


def test_annual_slices_carry_equity_and_seed_drawdown_at_year_open():
    from examples.stock_backtesting.qmt357.annual_metrics import annual_statistics

    daily = pd.DataFrame({
        'equity': [90., 110., 99., 121.],
        'trade_count': [1, 2, 3, 4],
        'commission': [1., 2., 3., 4.],
        'slippage': [.1, .2, .3, .4],
        'position_count': [1, 1, 2, 0],
    }, index=pd.to_datetime(['2020-01-02', '2020-12-31', '2021-01-04', '2021-09-24']))
    trips = [dict(exit_date='2020-12-31', net_pnl=10),
             dict(exit_date='2021-01-04', net_pnl=-2),
             dict(exit_date='2021-09-24', net_pnl=3)]
    rows = annual_statistics(daily, trips, capital=100.)
    assert [r['year'] for r in rows] == [2020, 2021]
    assert [r['start_equity'] for r in rows] == [100., 110.]
    assert [r['end_equity'] for r in rows] == [110., 121.]
    assert [r['return_pct'] for r in rows] == pytest.approx([10., 10.])
    assert [r['max_drawdown_pct'] for r in rows] == pytest.approx([-10., -10.])
    assert [r['total_trade_count'] for r in rows] == [3, 7]
    assert [r['win_rate_pct'] for r in rows] == [100., 50.]
    assert rows[1]['total_commission'] == 7
    assert rows[1]['total_slippage'] == pytest.approx(.7)
    assert rows[1]['end_date'] == '2021-09-24'
    assert rows[0]['sharpe'] == pytest.approx(rows[1]['sharpe'])
    assert (1 + rows[0]['return_pct']/100) * (1 + rows[1]['return_pct']/100) == pytest.approx(1.21)


def test_flat_no_closed_trades_has_zero_sharpe_and_null_win_rate():
    from examples.stock_backtesting.qmt357.annual_metrics import annual_statistics

    daily = pd.DataFrame(dict(equity=[100., 100.], trade_count=[0, 0],
        commission=[0., 0.], slippage=[0., 0.], position_count=[0, 0]),
        index=pd.to_datetime(['2026-09-23', '2026-09-24']))
    row, = annual_statistics(daily, [], capital=100.)
    assert row['sharpe'] == 0
    assert row['win_rate_pct'] is None
    assert row['closed_round_trips'] == 0
    assert row['trading_days'] == 2


def test_annual_statistics_rejects_unsorted_dates():
    from examples.stock_backtesting.qmt357.annual_metrics import annual_statistics

    daily = pd.DataFrame(dict(equity=[100., 90.]), index=pd.to_datetime(['2021-01-04', '2020-12-31']))
    with pytest.raises(ValueError, match='sorted'):
        annual_statistics(daily, [], capital=100.)
