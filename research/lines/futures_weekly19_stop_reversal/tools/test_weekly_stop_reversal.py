from datetime import date, datetime
from decimal import Decimal

import pytest

from weekly_stop_reversal import (
    CloseFill,
    EntryAnchor,
    ReversePosition,
    StopSignal,
    WeeklyBar,
    advance_protection,
    plan_reversal,
)


def time(value):
    return datetime.fromisoformat(value + "+08:00")


def week(day, high, low, close):
    return WeeklyBar(date.fromisoformat(day), high, low, close)


@pytest.mark.parametrize("reason", ["prev2day_stop", "base_stop", "ma_stop"])
@pytest.mark.parametrize(
    "original,expected,price,stop,lots",
    [("long", "short", 90, 110, 9), ("short", "long", 105, 80, 7)],
)
def test_all_original_weekly_stops_reverse_at_signal_week_extreme(
    reason, original, expected, price, stop, lots
):
    signal = StopSignal(
        "p1", "au2612.SHFE", "epoch", original, f"{original}_{reason}",
        week("2026-10-30", 110, 80, 90), date(2026, 11, 2), Decimal(".018"),
    )
    fill = CloseFill("p1", time("2026-11-02T09:00:00"), date(2026, 11, 2), 0)
    anchor = EntryAnchor(
        "au2612.SHFE", "epoch", time("2026-11-02T09:01:00"), date(2026, 11, 2),
        price, 100_000, 1, 10, 30, 1,
    )
    plan = plan_reversal(signal, fill, anchor)
    assert (plan.direction, plan.initial_stop, plan.volume) == (expected, stop, lots)
    assert plan.risk_budget == 1800


def sample():
    signal = StopSignal(
        "p1", "au2612.SHFE", "epoch", "long", "long_ma_stop",
        week("2026-10-30", 110, 80, 90), date(2026, 11, 2), Decimal(".018"),
    )
    fill = CloseFill("p1", time("2026-11-02T09:00:00"), date(2026, 11, 2), 0)
    anchor = EntryAnchor(
        "au2612.SHFE", "epoch", time("2026-11-02T09:01:00"), date(2026, 11, 2),
        90, 100_000, 1, 10, 30, 1,
    )
    return signal, fill, anchor


@pytest.mark.parametrize(
    "field,changes",
    [
        (0, {"reason": "reverse_to_short"}),
        (0, {"is_reverse_position": True}),
        (1, {"remaining_volume": 1}),
        (1, {"position_id": "other"}),
        (1, {"trading_day": date(2026, 11, 9)}),
        (2, {"timestamp": time("2026-11-02T09:00:00")}),
        (2, {"timestamp": time("2026-11-09T09:00:00"), "trading_day": date(2026, 11, 9)}),
        (2, {"epoch": "rollover"}),
        (2, {"price": 110}),
        (2, {"price": 111}),
        (2, {"equity": 0}),
        (2, {"volume_cap": 0}),
    ],
)
def test_reversal_is_ineligible_without_flat_current_week_and_valid_risk(field, changes):
    from dataclasses import replace

    args = list(sample())
    args[field] = replace(args[field], **changes)
    assert plan_reversal(*args) is None


def test_current_cap_and_risk_multiplier_reduce_size():
    from dataclasses import replace

    signal, fill, anchor = sample()
    assert plan_reversal(signal, fill, replace(anchor, volume_cap=2)).volume == 2
    adjusted = plan_reversal(signal, fill, replace(anchor, risk_multiplier=Decimal(".5")))
    assert (adjusted.risk_budget, adjusted.volume) == (900, 4)


def test_short_initial_stop_then_ratchet_uses_prior_weeks_and_cannot_loosen():
    position = ReversePosition("short", 110, date(2026, 11, 2))
    signal = week("2026-10-30", 108, 75, 80)
    first = week("2026-11-06", 100, 72, 89)
    second = week("2026-11-13", 130, 69, 90)
    third = week("2026-11-20", 131, 68, 109)
    assert advance_protection(position, (signal, first)) == (110, False)
    stop, triggered = advance_protection(position, (signal, first, second))
    assert (stop, triggered) == (108, False)
    assert advance_protection(
        ReversePosition("short", stop, position.entry_day), (first, second, third)
    ) == (108, True)


def test_long_mirror_ratchets_and_initial_stop_applies_during_warmup():
    position = ReversePosition("long", 80, date(2026, 11, 2))
    signal = week("2026-10-30", 120, 84, 90)
    first = week("2026-11-06", 130, 85, 100)
    second = week("2026-11-13", 135, 77, 83)
    assert advance_protection(position, (signal, first, second)) == (84, True)
    assert advance_protection(position, (signal, week("2026-11-06", 100, 70, 80))) == (80, True)


def test_risk_per_lot_uses_at_least_one_tick():
    from dataclasses import replace

    signal, fill, anchor = sample()
    assert plan_reversal(signal, fill, replace(anchor, price_tick=30)).volume == 6


def test_initial_stop_can_trigger_at_completed_close_on_entry_day():
    position = ReversePosition("long", 80, date(2026, 11, 6))
    assert advance_protection(position, (week("2026-11-06", 100, 75, 79),)) == (80, True)
