"""Bounded fixture checks for the fixed Stage124 minute limit approximation."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
import stage022_run_c0_qualified_wait as runtime

_RUNTIME = tempfile.TemporaryDirectory(prefix="stage130_limit_scan_")
_OLD_OUTPUT = runtime.OUTPUT
try:
    runtime.OUTPUT = Path(_RUNTIME.name)
    runtime.configure_runtime(Path(_RUNTIME.name) / "shared")
finally:
    runtime.OUTPUT = _OLD_OUTPUT

import pandas as pd

try:
    from stage127_ema_limit_engine import build_ema_engine, entry_minute_view, limit_context
except ImportError:
    build_ema_engine = entry_minute_view = limit_context = None


def frozen_intent(direction=1):
    return dict(mechanism_id="stage124_ema_limit_v1", intent_id="ema-one", setup_id="ema-setup",
                epoch_id="ema-epoch", product="AP.CZCE", contract="AP605.CZCE",
                signal_day="2026-01-06", execution_day="2026-01-07", direction=direction,
                limit_price=100.0, trigger=100.0, execution_tick=1.0, order_type="limit", rank=1,
                plan=dict(volume=2, target_contract="AP605.CZCE",
                          direction="long" if direction == 1 else "short",
                          sizing=dict(stop_price=95.0 if direction == 1 else 105.0,
                                      risk_per_contract=50.0, margin_per_contract=100.0,
                                      margin_ratio=0.1)))


def minute_frame(rows, *, start="2026-01-07T09:00:00"):
    result = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])
    result.insert(0, "bar_datetime", pd.date_range(start, periods=len(rows), freq="min"))
    return result


class EmaLimitEngineTests(unittest.TestCase):
    def test_limit_scan_volume_day_end_and_private_view(self):
        # Catches touch fills, quantity bypass, later confirmation rescue,
        # cross-D fills, unreachable ticks, and first-minute favorable leakage.
        self.assertIsNotNone(limit_context, "Stage127 EMA limit scan is not implemented")
        item = frozen_intent()
        raw = minute_frame([(101, 102, 100, 101, 20),  # Touch only.
                            (101, 102, 99, 100, 1),    # Penetrates, insufficient V.
                            (103, 105, 99, 104, 2),    # First eligible; F=L.
                            (98.2, 100, 97, 99, 20)])
        before = raw.copy(deep=True)
        frozen = deepcopy(item)
        primary = limit_context(item, raw, tick=1)
        self.assertEqual((primary["fill_price"], primary["quantity"], primary["intrabar"]), (100, 2, True))
        self.assertEqual(primary["execution_datetime"], pd.Timestamp("2026-01-07T09:02:00"))
        self.assertEqual(primary["trading_date"].isoformat(), "2026-01-07")
        self.assertEqual(primary["raw_minute_close"], 104)
        self.assertEqual(primary["entry_minute"]["high"], 105)
        self.assertIsNone(limit_context(item, raw.iloc[:2], tick=1))
        for invalid in (float("nan"), float("inf"), -1, None, True):
            bad = raw.copy(deep=True)
            bad["volume"] = bad["volume"].astype(object)
            bad.loc[3, "volume"] = invalid  # Full D validation even after an early fill.
            with self.subTest(invalid_volume=str(invalid)), self.assertRaises(ValueError):
                limit_context(item, bad, tick=1)

        for direction, rows, want in [
            (1, [(98.2, 100, 97, 99, 2)], 99),
            (-1, [(101.8, 103, 100, 102, 2)], 101),
        ]:
            context = limit_context(frozen_intent(direction), minute_frame(rows), tick=1)
            self.assertEqual(context["fill_price"], want)
            self.assertFalse(context["intrabar"])
            self.assertLessEqual(direction * (want - 100), 0)
        with self.assertRaises(ValueError):
            limit_context(item, minute_frame([(98.2, 98.8, 98.1, 98.4, 2)]), tick=1)
        decimal_item = frozen_intent()
        decimal_item.update(limit_price=100.3, trigger=100.3, execution_tick=0.1)
        decimal_context = limit_context(decimal_item, minute_frame([(100.4, 100.5, 100.2, 100.3, 2)]), tick=0.1)
        self.assertEqual(decimal_context["fill_price"], 100.3)

        stress = limit_context(item, raw, tick=1, policy="pessimistic")
        self.assertEqual((stress["fill_price"], stress["execution_datetime"], stress["intrabar"]),
                         (100, pd.Timestamp("2026-01-07T09:03:00"), True))
        failed_confirmation = minute_frame([(103, 104, 99, 101, 2), (102, 103, 100, 101, 2),
                                             (102, 103, 99, 100, 2), (102, 103, 99, 100, 2)])
        self.assertIsNone(limit_context(item, failed_confirmation, tick=1, policy="pessimistic"))
        day_end = minute_frame([(103, 104, 99, 101, 2), (102, 103, 99, 100, 2)], start="2026-01-07T14:59:00")
        day_end.loc[1, "bar_datetime"] = pd.Timestamp("2026-01-08T09:00:00")
        self.assertIsNone(limit_context(item, day_end, tick=1, policy="pessimistic"))
        self.assertIsNone(limit_context(item, day_end.iloc[:1], tick=1, policy="pessimistic"))
        stress_improved = minute_frame([(103, 104, 99, 101, 2), (98.2, 99.8, 97, 98.4, 2)])
        self.assertEqual(limit_context(item, stress_improved, tick=1, policy="pessimistic")["fill_price"], 99)
        short_stress = minute_frame([(97, 101, 96, 98, 2), (101.2, 103, 100.2, 102, 2)])
        self.assertEqual(limit_context(frozen_intent(-1), short_stress, tick=1, policy="pessimistic")["fill_price"], 101)
        with self.assertRaises(ValueError):
            limit_context(item, raw, tick=1, policy="later_rescue")
        with self.assertRaises((ValueError, TypeError)):
            build_ema_engine(object, qualify=None)

        view = entry_minute_view(raw, entry_time=primary["execution_datetime"], fill_price=100,
                                 direction=1, intrabar=True)
        self.assertEqual(view.iloc[2][["open", "high", "low", "close"]].tolist(), [100, 100, 99, 100])
        pd.testing.assert_frame_equal(view.iloc[:2], before.iloc[:2])
        pd.testing.assert_frame_equal(view.iloc[3:], before.iloc[3:])
        short_raw = minute_frame([(97, 101, 95, 96, 2)])
        short_before = short_raw.copy(deep=True)
        short_view = entry_minute_view(short_raw, entry_time=short_raw.iloc[0]["bar_datetime"],
                                       fill_price=100, direction=-1, intrabar=True)
        self.assertEqual(short_view.iloc[0][["open", "high", "low", "close"]].tolist(), [100, 101, 100, 100])
        open_view = entry_minute_view(raw, entry_time=raw.iloc[3]["bar_datetime"], fill_price=99,
                                     direction=1, intrabar=False)
        pd.testing.assert_frame_equal(open_view, raw)
        pd.testing.assert_frame_equal(raw, before)
        pd.testing.assert_frame_equal(short_raw, short_before)
        self.assertEqual(item, frozen)


class EmaLimitNativeIntegrationTests(unittest.TestCase):
    def test_real_gap_invalid_side_mother_and_cost(self):
        # Break caught: wrong-side abs risk, erased initial fill, virtual close,
        # cost omission/duplication, or retry on an invalid signed-R episode.
        from contextlib import ExitStack
        from unittest.mock import patch
        import test_stage127_ema_limit_strategy as fixtures
        native=fixtures.native
        for direction,stop,raw,wanted in [
                (1,95.,[(90.,92.,88.,90.,1000.)],[90.,88.]),
                (-1,105.,[(110.,112.,108.,110.,1000.)],[110.,112.])]:
            with self.subTest(direction=direction), tempfile.TemporaryDirectory() as folder:
                strategy,engine=fixtures.native_fixture(Path(folder),direction=direction,stop=stop)
                self.assertEqual(len(strategy.ts_pending_intents),1)
                item=deepcopy(strategy.ts_pending_intents[0])
                cash_before=strategy.settled_balance
                raw_frames=fixtures.install_minutes(strategy,engine,raw)
                with ExitStack() as stack:
                    stack.enter_context(patch.object(native.s827.QmtRollPortfolioStrategyStage827C2,
                        "_sync_entry_risk_diagnostic",side_effect=AssertionError("wrong-side diagnostic abs reached")))
                    stack.enter_context(patch.object(native.QmtRollPortfolioStrategyStage847C9StopRetry,
                        "_stage847_stop_retry_event_after_open_trade",side_effect=AssertionError("wrong-side R branch reached")))
                    stack.enter_context(patch.object(native.s827.QmtRollPortfolioStrategyStage827C2,
                        "stage827_intraday_exit_after_open_trade",side_effect=AssertionError("wrong-side fallback R reached")))
                    try:
                        engine.cross_delayed_orders()
                    except AssertionError as exc:
                        self.fail(str(exc))
                trades=engine.get_all_trades()
                self.assertEqual([t.price for t in trades],wanted)
                self.assertEqual([t.volume for t in trades],[item["plan"]["volume"]]*2)
                self.assertEqual(strategy.get_pos(item["contract"]),0)
                self.assertEqual(strategy.stage847_stop_retry_events,[])
                self.assertEqual(len(strategy.ts_fill_audit),1)
                self.assertEqual(len({t.economic_mother_id for t in trades}),1)
                for trade in trades:
                    self.assertEqual(trade.research_mechanism,fixtures.adapter().MECHANISM_ID)
                    self.assertEqual(trade.signal_datetime.date().isoformat(),fixtures.DAY)
                    self.assertIn(item["intent_id"],trade.economic_mother_id)
                diagnostic=strategy.entry_risk_diagnostics[-1]
                self.assertIsNone(diagnostic["risk_per_contract"])
                self.assertIsNone(diagnostic["actual_risk_amount"])
                self.assertEqual(diagnostic["ema_limit_signed_risk_price"],-5.)
                with self.assertRaises(ValueError):
                    strategy.ts_machine.on_fill(item["intent_id"],fixtures.NEXT)
                engine.update_daily_close(engine.bars,engine.datetime)
                daily=engine.calculate_result()
                cost=sum(t.volume*10*(t.price*.001+1.) for t in trades)
                self.assertAlmostEqual(strategy.trade_costs_total,cost)
                self.assertAlmostEqual(float(daily.commission.sum()+daily.slippage.sum()),cost)
                gross=sum((-t.price if t.direction==native.s827.Direction.LONG else t.price)*t.volume*10 for t in trades)
                self.assertAlmostEqual(float(daily.net_pnl.sum()),gross-cost)
                self.assertAlmostEqual(strategy.settled_balance,cash_before+gross-cost)
                self.assertIs(strategy.stage827_minute_by_symbol,raw_frames)

    def test_real_dual_consumer_retry_and_unfilled_resource(self):
        # Break caught: pre-entry high enters either consumer, retry is clamped
        # to L, q/R is recomputed on D, or an unfilled candidate frees resources.
        from copy import copy
        from types import SimpleNamespace
        import test_stage127_ema_limit_strategy as fixtures
        first=(103.,105.,99.,104.,1000.)
        with tempfile.TemporaryDirectory() as folder:
            strategy,engine=fixtures.native_fixture(Path(folder),stop=96.)
            item=deepcopy(strategy.ts_pending_intents[0])
            raw=fixtures.install_minutes(strategy,engine,[first])
            engine.cross_delayed_orders()
            self.assertEqual([t.price for t in engine.get_all_trades()],[100.])
            self.assertEqual(strategy.stage847_stop_retry_events,[])
            symbol=item["contract"]
            context=SimpleNamespace(current_pos=strategy.get_pos(symbol),product_vt_symbol=item["product"],
                target_contract=symbol,target_bar=copy(engine.bars[symbol]),actual_bar=copy(engine.bars[symbol]))
            strategy._build_daily_env_gate_snapshot([context])
            self.assertEqual((context.target_bar.open_price,context.target_bar.high_price,
                              context.target_bar.low_price),(100.,100.,99.))
            self.assertEqual(raw[symbol].iloc[0][["open","high","low","close"]].tolist(),[103.,105.,99.,104.])
            ordinary=SimpleNamespace(current_pos=1,product_vt_symbol=item["product"],
                target_contract="AP609.CZCE",target_bar=fixtures.bar("AP609.CZCE",fixtures.NEXT,high=120.),
                actual_bar=copy(engine.bars[symbol]))
            raw_bar=ordinary.target_bar
            strategy._build_daily_env_gate_snapshot([ordinary])
            self.assertIs(ordinary.target_bar,raw_bar)
            self.assertEqual(ordinary.target_bar.high_price,120.)
        with tempfile.TemporaryDirectory() as folder:
            strategy,engine=fixtures.native_fixture(Path(folder),stop=96.,multiple=True)
            frozen=deepcopy(strategy.ts_pending_intents)
            cash_before=strategy.settled_balance
            reservation=strategy.pending_margin_reservation
            raw=fixtures.install_minutes(strategy,engine,[first,(100.,100.,98.,99.,1000.),
                (103.,104.,97.,99.,1000.)],unfilled=True)
            # Poison D's final daily close and account estimate; prehung q/L/S
            # were frozen at u and the engine must not rebuild them.
            strategy.estimated_equity=1.
            for daily_bar in engine.bars.values():
                daily_bar.close_price=1e6
                daily_bar.high_price=1e6
            engine.cross_delayed_orders()
            trades=engine.get_all_trades()
            self.assertEqual([t.price for t in trades],[100.,98.,103.,98.])
            self.assertEqual([t.volume for t in trades],[frozen[0]["plan"]["volume"]]*4)
            self.assertEqual(strategy.stage847_stop_retry_events[0]["risk_price"],4.)
            self.assertEqual(strategy.stage847_stop_retry_events[0]["stop_price"],98.)
            self.assertEqual(strategy.pending_margin_reservation,reservation)
            self.assertEqual([x["status"] for x in engine.ema_limit_execution_audit].count("expired_unfilled"),2)
            self.assertEqual(strategy.get_pos(frozen[0]["contract"]),0)
            self.assertEqual(len({t.economic_mother_id for t in trades}),1)
            self.assertEqual(len(strategy.ts_fill_audit),1)
            cost=sum(t.volume*10*(t.price*.001+1.) for t in trades)
            self.assertAlmostEqual(strategy.trade_costs_total,cost)
            engine.update_daily_close(engine.bars,engine.datetime)
            daily=engine.calculate_result()
            self.assertAlmostEqual(float(daily.commission.sum()+daily.slippage.sum()),cost)
            # 100->98 loses2, then103->98 loses5: two native legs total-7.
            expected=(-7.*10*frozen[0]["plan"]["volume"])-cost
            self.assertAlmostEqual(float(daily.net_pnl.sum()),expected)
            self.assertAlmostEqual(strategy.settled_balance,cash_before+expected)
            self.assertIs(strategy.stage827_minute_by_symbol,raw)


if __name__ == "__main__":
    unittest.main()
