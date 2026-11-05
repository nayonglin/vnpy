from datetime import date, timedelta
from decimal import Decimal

import pytest

from weekly_two_close_momentum import WeeklyBar, replay


def week(index, opening, high, low, close, contract="rb2610.SHFE"):
    first = date(2026, 4, 13) + timedelta(weeks=index)
    return WeeklyBar(contract, first, first + timedelta(days=4),
                     *map(Decimal, (opening, high, low, close)))


def test_two_rising_closes_enter_next_week_and_signal_week_sets_first_stop():
    bars = [
        week(0, 100, 105, 95, 100),
        week(1, 100, 109, 98, 105),
        week(2, 104, 115, 103, 110),
        week(3, 112, 114, 102, 103),
        week(4, 99, 104, 95, 99),
    ]
    events = list(replay(bars))
    assert [(row.event, row.action, row.trading_day, row.price, row.stop_price, row.volume)
            for row in events] == [
        ("signal", "open_long", bars[2].week_end, None, 103, 1),
        ("fill", "open_long", bars[3].first_day, 112, 103, 1),
        ("signal", "close_long", bars[3].week_end, None, 103, 1),
        ("fill", "close_long", bars[4].first_day, 99, 103, 1),
        ("signal", "open_short", bars[4].week_end, None, 104, 1),
    ]


def test_short_compares_close_to_prior_high_and_allows_a_wider_stop():
    bars = [
        week(0, 110, 114, 106, 110),
        week(1, 108, 112, 99, 105),
        week(2, 105, 106, 96, 100),
        week(3, 99, 112, 90, 104),
        week(4, 104, 114, 100, 110),
        week(5, 112, 116, 105, 114),
    ]
    events = list(replay(bars))
    assert [(row.event, row.action, row.stop_price) for row in events] == [
        ("signal", "open_short", 106),
        ("fill", "open_short", 106),
        ("signal", "close_short", 114),
    ]


def test_ties_do_not_open_and_mixed_contracts_are_rejected():
    bars = [week(0, 100, 110, 90, 100), week(1, 100, 110, 90, 100),
            week(2, 100, 110, 90, 105)]
    assert list(replay(bars)) == []
    with pytest.raises(ValueError, match="contract"):
        list(replay([bars[0], week(1, 100, 110, 90, 100, contract="rb2701.SHFE")]))


def test_ma_filter_uses_three_strict_slopes_and_preserves_short_history():
    from weekly_two_close_momentum import weekly_ma_slopes, blocks_entry

    rising = [week(i, close, close + 1, close - 1, close)
              for i, close in enumerate(range(100, 121))]
    falling = [week(i, close, close + 1, close - 1, close)
               for i, close in enumerate(range(120, 99, -1))]
    assert weekly_ma_slopes(rising) == (1, 1, 1)
    assert weekly_ma_slopes(falling) == (-1, -1, -1)
    assert blocks_entry("open_short", weekly_ma_slopes(rising))
    assert blocks_entry("open_long", weekly_ma_slopes(falling))
    assert not blocks_entry("close_long", weekly_ma_slopes(falling))
    assert not blocks_entry("open_long", (-1, 0, -1))
    assert not blocks_entry("open_short", weekly_ma_slopes(rising[1:]))
    assert not blocks_entry("open_short", weekly_ma_slopes([None, *rising[1:]]))
