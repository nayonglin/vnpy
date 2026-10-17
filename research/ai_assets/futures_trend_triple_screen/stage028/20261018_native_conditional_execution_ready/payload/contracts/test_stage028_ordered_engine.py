"""Finite causal adapter checks using native Stage827 order/trade accounting."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
import stage022_run_c0_qualified_wait as prior

_RUNTIME = tempfile.TemporaryDirectory(prefix="stage028_engine_test_")
prior.configure_runtime(Path(_RUNTIME.name) / "shared")
os.environ["MPLCONFIGDIR"] = _RUNTIME.name

import pandas as pd
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as native
from vnpy.trader.constant import Direction, Exchange, Offset
from vnpy.trader.object import BarData
from vnpy_portfoliostrategy.template import StrategyTemplate

try:
    from stage028_ordered_engine import build_ordered_engine
except ImportError:
    build_ordered_engine = None

execution = native.s827.execution
DAY = "2026-01-07"
SIGNAL = "2026-01-06"


def bar(symbol="AP605.CZCE", day=DAY, price=100.0):
    code, exchange = symbol.split(".")
    return BarData(symbol=code, exchange=Exchange(exchange), datetime=datetime.fromisoformat(day),
                   gateway_name="TEST", open_price=price, high_price=price,
                   low_price=price, close_price=price)


def intent(symbol="AP605.CZCE", *, direction=1, rank=1, execution_day=DAY, name="one"):
    return dict(arm="C_TS", intent_id=name, product=symbol.split(".")[0][:2] + ".CZCE",
                contract=symbol, epoch_id="epoch", setup_id="setup-" + name,
                setup_day="2026-01-05", signal_day=SIGNAL, execution_day=execution_day,
                direction=direction, trigger=101.0 if direction == 1 else 99.0,
                weekly_asof="2026-01-02", native_signal="long_case1a" if direction == 1 else "short_case1a",
                rank=rank, plan=dict(sizing=dict(stop_price=95.0 if direction == 1 else 105.0,
                    risk_per_contract=50.0, margin_per_contract=100.0, margin_ratio=0.1),
                    volume=2, target_contract=symbol, target_bar=bar(symbol, SIGNAL),
                    history=pd.DataFrame(), signal_data={},
                    direction="long" if direction == 1 else "short", signal="native"))


def minutes(symbol, changed=None):
    grid = execution.session_minutes(symbol, DAY, [SIGNAL, DAY, "2026-01-08"])
    frame = pd.DataFrame(dict(bar_datetime=grid, open=100.0, high=100.0, low=100.0, close=100.0))
    for index, values in (changed or {}).items():
        for key, value in values.items():
            frame.loc[index, key] = value
    return frame


class ResearchStrategy(StrategyTemplate):
    """Only alpha/state activation is a stub; orders and fills are native."""
    def __init__(self, engine, symbols):
        super().__init__(engine, "stage028-test", symbols, {})
        self.trading = True
        self.available_trade_dates = pd.to_datetime([SIGNAL, DAY, "2026-01-08"])
        self.stage827_minute_by_symbol = {symbol: minutes(symbol) for symbol in symbols}
        self.stage827_require_complete_minutes = True
        self.ts_pending_intents = []
        self.ts_conditional_orders = {}
        self.layers = []
        self.activations = []
        self.commits = []
        self.observed = []
        self.synthetic_symbol = None
        self.estimated_equity = 150000.0

    def on_init(self):
        pass

    def on_bars(self, bars):
        pass

    def ts_activate_intent(self, item, fill_price):
        self.activations.append((item["intent_id"], fill_price, len(self.strategy_engine.trades)))
        self.layers.append((item["intent_id"], item["plan"]["volume"]))
        self.target_data[item["contract"]] = item["direction"] * item["plan"]["volume"]

    def ts_commit_fill(self, item, execution_day, order_id, context):
        self.commits.append((item["intent_id"], execution_day, order_id, deepcopy(context)))

    def update_trade(self, trade):
        super().update_trade(trade)
        self.observed.append((trade.vt_symbol, trade.offset.value, trade.price, trade.volume,
                              execution.local_timestamp(trade.datetime).isoformat(),
                              execution.local_timestamp(trade.signal_datetime).date().isoformat()))

    def stage827_intraday_exit_after_open_trade(self, trade):
        if trade.vt_symbol != self.synthetic_symbol:
            return None
        context = self.ts_conditional_orders.get(trade.vt_orderid)
        if context is None:
            return None
        return dict(trading_date=DAY, synthetic_trades=[dict(action="close", source="same_bar_stop",
                    price=99.0, trigger_price=99.0, volume=trade.volume,
                    time=execution.local_timestamp(trade.datetime).isoformat())])


def engine(qualify=lambda *args: None, symbols=("AP605.CZCE",)):
    cls = build_ordered_engine(native.s827.Stage827IntradayC2Engine, qualify)
    result = cls({})
    result.datetime = datetime.fromisoformat(DAY)
    result.priceticks = {symbol: 1.0 for symbol in symbols}
    result.sizes = {symbol: 10 for symbol in symbols}
    result.bars = {symbol: bar(symbol) for symbol in symbols}
    result.strategy = ResearchStrategy(result, list(symbols))
    return result


class OrderedEngineTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(build_ordered_engine, "Stage028 conditional adapter is not implemented")

    def test_factory_rejects_missing_qualification_callable(self):
        with self.assertRaises((TypeError, ValueError)):
            build_ordered_engine(native.s827.Stage827IntradayC2Engine, None)

    def test_untriggered_has_no_layer_target_order_trade_or_fee(self):
        qualified = []
        target = engine(lambda e, item, actual: qualified.append(item["intent_id"]))
        target.strategy.ts_pending_intents = [intent()]
        target.cross_delayed_orders()
        self.assertEqual(qualified, ["one"])
        self.assertEqual(target.strategy.layers, [])
        self.assertEqual(dict(target.strategy.target_data), {})
        self.assertEqual(target.limit_orders, {})
        self.assertEqual(target.trades, {})
        self.assertEqual(target.trade_usage_rows, [])
        self.assertEqual(target.strategy.commits, [])
        self.assertEqual(target.strategy.ts_pending_intents, [])
        self.assertEqual(target.ts_execution_audit[0]["status"], "expired_untriggered")
        self.assertTrue(target.ts_execution_audit[0]["untriggered"])
        self.assertEqual(target.ts_execution_audit[0].get("forecast_risk_amount"), 100.0)
        self.assertEqual(target.ts_execution_audit[0].get("forecast_margin_amount"), 200.0)
        self.assertIsNone(target.ts_execution_audit[0].get("actual_risk_amount"))
        json.dumps(target.ts_execution_audit, allow_nan=False)

    def test_frozen_quantity_ignores_future_daily_close_and_equity(self):
        class Poison:
            def __float__(self):
                raise AssertionError("future account/daily close was consulted")
        target = engine()
        target.strategy.ts_pending_intents = [intent()]
        target.strategy.estimated_equity = Poison()
        for name in ("close_price", "high_price", "low_price", "open_price"):
            setattr(target.bars["AP605.CZCE"], name, Poison())
        target.strategy.stage827_minute_by_symbol["AP605.CZCE"] = minutes("AP605.CZCE", {
            1: dict(open=100.0, high=102.0, low=99.0, close=100.0)})
        target.cross_delayed_orders()
        self.assertEqual(target.strategy.activations, [("one", 101.0, 0)])
        self.assertEqual([(t.price, t.volume) for t in target.trades.values()], [(101.0, 2)])
        self.assertEqual(target.strategy.pos_data["AP605.CZCE"], 2)
        self.assertEqual(target.strategy.target_data["AP605.CZCE"], 2)
        self.assertEqual(target.strategy.active_orderids, set())
        self.assertEqual(target.strategy.observed[0][4:], (DAY + "T09:01:00", SIGNAL))
        self.assertEqual(len(target.strategy.commits), 1)
        self.assertEqual(target.strategy.commits[0][1], DAY)
        audit = target.ts_execution_audit[0]
        self.assertEqual((audit["quantity"], audit["fill_price"], audit["actual_risk_amount"]), (2, 101.0, 120.0))
        self.assertEqual((audit["forecast_risk_amount"], audit["forecast_margin_amount"]), (100.0, 200.0))
        self.assertEqual(audit["actual_margin_amount"], 202.0)
        self.assertTrue(audit["intrabar"])
        json.dumps(target.ts_execution_audit, allow_nan=False)

    def test_long_and_short_gap_fill_at_open_without_reducing_frozen_quantity(self):
        for direction, opening, high, low, expected in [(1, 106.0, 107.0, 105.0, 106.0),
                                                      (-1, 94.0, 95.0, 93.0, 94.0)]:
            with self.subTest(direction=direction):
                target = engine()
                target.strategy.ts_pending_intents = [intent(direction=direction)]
                target.strategy.stage827_minute_by_symbol["AP605.CZCE"] = minutes("AP605.CZCE", {
                    0: dict(open=opening, high=high, low=low, close=opening)})
                target.cross_delayed_orders()
                self.assertEqual([(t.price, t.volume) for t in target.trades.values()], [(expected, 2)])
                self.assertEqual(target.strategy.pos_data["AP605.CZCE"], direction * 2)
                audit = target.ts_execution_audit[0]
                self.assertEqual(audit["actual_risk_amount"], 220.0)
                self.assertFalse(audit["intrabar"])
                self.assertEqual(audit["fill_note"], "gap_open")

    def test_qualification_runs_before_minute_mapping_is_read(self):
        qualified = False
        target = None
        class GuardedMapping(dict):
            def get(self, key, default=None):
                if not qualified:
                    raise AssertionError("scan preceded data qualification")
                return super().get(key, default)
        def qualify(e, item, actual):
            nonlocal qualified
            self.assertIs(actual, e.bars[item["contract"]])
            self.assertEqual(e.strategy.activations, [])
            self.assertEqual(e.limit_orders, {})
            qualified = True
        target = engine(qualify)
        target.strategy.ts_pending_intents = [intent()]
        target.strategy.stage827_minute_by_symbol = GuardedMapping(target.strategy.stage827_minute_by_symbol)
        target.cross_delayed_orders()
        self.assertTrue(qualified)
        self.assertEqual(target.strategy.minute_scan_requests[0]["expected_bar_count"], 225)

    def test_rejected_or_incomplete_qualification_fails_closed_and_cleans_queue(self):
        for returned, missing in [(False, False), ({"qualified": True}, False), (None, True)]:
            with self.subTest(returned=returned, missing=missing):
                target = engine(lambda *args: returned)
                target.strategy.ts_pending_intents = [intent()]
                if missing:
                    target.strategy.stage827_minute_by_symbol["AP605.CZCE"] = minutes("AP605.CZCE").iloc[:-1]
                with self.assertRaises(ValueError):
                    target.cross_delayed_orders()
                self.assertEqual(target.strategy.activations, [])
                self.assertEqual(target.trades, {})
                self.assertTrue(target.intraday_execution_failure)
                self.assertIsNone(target._stage827_execution_queue)
                self.assertEqual(target._stage827_order_contexts, {})

    def test_ordinary_conditional_synthetic_share_one_stable_queue(self):
        ap, sm = "AP605.CZCE", "SM605.CZCE"
        target = engine(symbols=(ap, sm))
        target.strategy.ts_pending_intents = [intent(ap, rank=2, name="AP"), intent(sm, rank=1, name="SM")]
        for symbol in (ap, sm):
            target.strategy.stage827_minute_by_symbol[symbol] = minutes(symbol, {
                1: dict(open=100.0, high=102.0, low=98.0, close=100.0)})
        target.strategy.synthetic_symbol = sm
        ordinary_id = target.strategy.buy(ap, 100.0, 1)[0]
        target.active_limit_orders[ordinary_id].datetime = datetime.fromisoformat(SIGNAL)
        target.open_proxy_map[(pd.Timestamp(SIGNAL), pd.Timestamp(DAY), ap)] = dict(
            proxy_price=100.0, price_source="test_proxy", proxy_first_time=DAY + "T09:00:00")
        target.cross_delayed_orders()
        self.assertEqual([(r[0], r[1], r[2], r[3]) for r in target.strategy.observed], [
            (ap, "Open", 100.0, 1), (sm, "Open", 101.0, 2), (ap, "Open", 101.0, 2), (sm, "Close", 99.0, 2)])
        self.assertEqual(target.strategy.activations, [("SM", 101.0, 1), ("AP", 101.0, 2)])
        self.assertEqual(target.strategy.pos_data[ap], 3)
        self.assertEqual(target.strategy.pos_data[sm], 0)
        self.assertEqual(len(target.strategy.commits), 2)
        self.assertEqual(target.source_counter["same_bar_stop"], 1)
        self.assertIsNone(target._stage827_execution_queue)
        self.assertEqual(target._stage827_order_contexts, {})

    def test_old_intent_expires_and_future_intent_never_fills_early(self):
        qualified = []
        target = engine(lambda e, item, actual: qualified.append(item["intent_id"]))
        future = intent(execution_day="2026-01-08", name="future")
        target.strategy.ts_pending_intents = [intent(execution_day=SIGNAL, name="old"), future]
        target.cross_delayed_orders()
        self.assertEqual(qualified, [])
        self.assertEqual(target.strategy.ts_pending_intents, [future])
        self.assertEqual(target.trades, {})
        self.assertEqual(target.ts_execution_audit[0]["status"], "expired_past_day")

    def test_without_pending_intent_ordinary_execution_is_native(self):
        target = engine(lambda *args: self.fail("conditional qualifier called for ordinary order"))
        symbol = "AP605.CZCE"
        order_id = target.strategy.buy(symbol, 100.0, 2)[0]
        target.active_limit_orders[order_id].datetime = datetime.fromisoformat(SIGNAL)
        target.open_proxy_map[(pd.Timestamp(SIGNAL), pd.Timestamp(DAY), symbol)] = dict(
            proxy_price=100.0, price_source="test_proxy", proxy_first_time=DAY + "T09:00:00")
        target.cross_delayed_orders()
        self.assertEqual(target.strategy.observed, [(symbol, "Open", 100.0, 2, DAY + "T09:00:00", SIGNAL)])
        self.assertEqual(target.source_counter["canonical_session_first_minute_open"], 1)


if __name__ == "__main__":
    unittest.main()
