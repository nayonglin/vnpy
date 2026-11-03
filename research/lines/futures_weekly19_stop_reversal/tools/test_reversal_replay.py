"""Regression check for causal accounting at the separate-day open proxy."""
from reversal_replay import open_equity


def test_open_equity_marks_old_inventory_and_books_preceding_fills_once():
    fills = [
        dict(symbol="x", side="short", volume=2, price=106, commission=3, slippage=5),
        dict(symbol="y", side="long", volume=1, price=208, commission=2, slippage=7),
    ]
    # Old x contributes +200, closing x contributes -80, opening y
    # contributes +40, and the two fills cost 17. No closing marks enter.
    assert open_equity(
        150_000, {"x": 2}, {"x": 100},
        {"x": 110, "y": 210}, fills, {"x": 10, "y": 20},
    ) == 150_143


def test_bind_only_the_current_unique_full_flat_close_order():
    from datetime import datetime
    from types import SimpleNamespace

    from vnpy.trader.constant import Direction, Offset

    from reversal_replay import bind_stop_order

    def order(i, day, volume, side=Direction.LONG):
        return SimpleNamespace(vt_orderid=i, vt_symbol="x", datetime=datetime.fromisoformat(day),
                               offset=Offset.CLOSE, direction=side, volume=volume)

    date = "2018-01-12"
    stale = order("stale", "2018-01-05", 4)
    current = order("current", date, 4)
    partial = order("partial", date, 2)
    wrong_side = order("wrong", date, 4, Direction.SHORT)
    assert bind_stop_order([stale, partial, wrong_side, current], "x", date, "short", 4, 0) == "current"
    assert bind_stop_order([current], "x", date, "short", 4, -2) is None
    assert bind_stop_order([current, order("duplicate", date, 4)], "x", date, "short", 4, 0) is None


def test_loss_gate_uses_whole_flat_cycle_with_fills_costs_and_partial_closes():
    from reversal_replay import ClosedPositionPnL

    ledger = ClosedPositionPnL()

    def fill(side, offset, price, volume, position, slippage=0):
        return ledger.apply(
            dict(symbol="x", side=side, offset=offset, price=price, volume=volume,
                 slippage=slippage, commission=0),
            size=10, position=position,
        )

    assert fill("long", "open", 100, 3, 3, 2) is None
    assert fill("short", "close", 120, 1, 2, 3) is None
    assert fill("short", "close", 95, 2, 0, 5) == 90
    assert fill("short", "open", 100, 1, -1, 2) is None
    assert fill("long", "close", 100, 1, 0, 2) == -4
    assert fill("long", "open", 100, 1, 1) is None
    assert fill("short", "close", 100, 1, 0) == 0
