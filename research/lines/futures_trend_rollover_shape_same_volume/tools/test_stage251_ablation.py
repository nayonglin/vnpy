"""Stage251：既有 0.5R 模块消融与研究注入隔离，不运行历史回测。

路径 fixture 的 entry=100、原始 stop=90/110，故 0.5R=95/105、
1R=90/110；期望值手算。稀疏分钟仅用于窄测，不是数据验收。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "examples" / "portfolio_backtesting"))

import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as c9
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from vnpy.trader.constant import Direction, Exchange, Offset
from vnpy.trader.object import TradeData
from vnpy_portfoliostrategy.backtesting import BacktestingEngine
from vnpy_portfoliostrategy.template import StrategyTemplate


FLAG = "enable_stage847_half_r_stop_retry"
ADAPTER_PATH = Path(__file__).with_name("stage251_half_r_ablation.py")


def minute_frame(rows):
    frame = pd.DataFrame(rows, columns=["bar_datetime", "open", "high", "low", "close"])
    frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"])
    frame["bar_date"] = frame.bar_datetime.dt.normalize()
    return frame


def make_strategy(rows, *, short=False, enabled=False):
    obj = object.__new__(c9.QmtRollPortfolioStrategyStage847C9StopRetry)
    direction = "short" if short else "long"
    obj.state = SimpleNamespace(
        layers=[SimpleNamespace(direction=direction, stop_price=110.0 if short else 90.0,
                                entry_price=100.0, volume=1)],
        direction=direction, contract_vt_symbol="cu2611.SHFE", product_vt_symbol="cu.SHFE",
    )
    obj._find_state_by_contract = lambda symbol: obj.state
    obj.get_pricetick = lambda symbol: 1.0
    obj.strategy_engine = SimpleNamespace(bars={}, datetime=datetime(2026, 10, 14))
    obj.stage827_minute_by_symbol = {"cu2611.SHFE": minute_frame(rows)}
    obj.available_trade_dates = pd.to_datetime(["2026-10-13", "2026-10-14"])
    obj.stage827_require_complete_minutes = False
    obj.enable_stage827_intraday_c2_stop = True
    obj.enable_stage847_half_r_stop_retry = enabled
    obj.stage827_intraday_c2_events = []
    obj.stage827_intraday_c2_stop_count = 0
    obj.stage847_stop_retry_events = []
    obj.stage847_stop_retry_event_count = 0
    return obj


def opening_trade(*, short=False):
    trade = TradeData(
        symbol="cu2611", exchange=Exchange.SHFE, orderid="1", tradeid="1",
        direction=Direction.SHORT if short else Direction.LONG, offset=Offset.OPEN,
        price=100.0, volume=1, datetime=datetime(2026, 10, 14, 9), gateway_name="BACKTESTING",
    )
    trade.execution_datetime = datetime(2026, 10, 14, 9)
    trade.trading_date = datetime(2026, 10, 14).date()
    return trade


class ExistingSwitchSemanticsTests(unittest.TestCase):
    def event(self, rows, *, short=False, enabled=False):
        obj = make_strategy(rows, short=short, enabled=enabled)
        return obj, obj.stage827_intraday_exit_after_open_trade(opening_trade(short=short))

    def test_half_r_excursion_stops_a_but_not_c_in_both_directions(self):
        for short, high, low, expected in [(False, 104, 94, 95.0), (True, 106, 96, 105.0)]:
            with self.subTest(short=short):
                rows = [("2026-10-14 09:00", 100, high, low, 100)]
                _, enabled = self.event(rows, short=short, enabled=True)
                self.assertEqual(enabled["synthetic_trades"][0]["source"], "stage847_intraday_05r_initial_stop")
                self.assertEqual(enabled["synthetic_trades"][0]["price"], expected)
                obj, disabled = self.event(rows, short=short)
                self.assertIsNone(disabled)
                self.assertEqual(obj.stage847_stop_retry_events, [])

    def test_disabled_half_r_retains_one_r_c2_stop_in_both_directions(self):
        for short, high, low, expected in [(False, 104, 89, 90.0), (True, 111, 96, 110.0)]:
            with self.subTest(short=short):
                obj, event = self.event([("2026-10-14 09:00", 100, high, low, 100)], short=short)
                self.assertEqual(event["exit_reason"], "stage827_intraday_c2_1r_stop")
                self.assertEqual(event["fill_price"], expected)
                self.assertEqual(obj.stage827_intraday_c2_stop_count, 1)
                self.assertEqual(obj.stage847_stop_retry_event_count, 0)

    def test_one_r_favorable_confirmation_still_disarms_c2_in_both_directions(self):
        cases = [
            (False, [("2026-10-14 09:00", 100, 111, 99, 110),
                     ("2026-10-14 09:01", 100, 101, 89, 90)]),
            (True, [("2026-10-14 09:00", 100, 101, 89, 90),
                    ("2026-10-14 09:01", 100, 111, 99, 110)]),
        ]
        for short, rows in cases:
            with self.subTest(short=short):
                _, event = self.event(rows, short=short)
                self.assertIsNone(event)

    def test_half_r_favorable_progress_does_not_disarm_remaining_c2(self):
        cases = [
            (False, [("2026-10-14 09:00", 100, 106, 99, 105),
                     ("2026-10-14 09:01", 100, 101, 89, 90)], 90.0),
            (True, [("2026-10-14 09:00", 100, 101, 94, 95),
                    ("2026-10-14 09:01", 100, 111, 99, 110)], 110.0),
        ]
        for short, rows, expected in cases:
            with self.subTest(short=short):
                _, event = self.event(rows, short=short)
                self.assertEqual(event["exit_reason"], "stage827_intraday_c2_1r_stop")
                self.assertEqual(event["fill_price"], expected)

    def test_removing_initial_stop_also_removes_its_reclaim_retry(self):
        for short, rows in [
            (False, [("2026-10-14 09:00", 100, 104, 94, 96),
                     ("2026-10-14 09:01", 100, 104, 99, 102)]),
            (True, [("2026-10-14 09:00", 100, 106, 96, 104),
                    ("2026-10-14 09:01", 100, 101, 96, 98)]),
        ]:
            with self.subTest(short=short):
                _, enabled = self.event(rows, short=short, enabled=True)
                self.assertEqual([item["source"] for item in enabled["synthetic_trades"]], [
                    "stage847_intraday_05r_initial_stop", "stage847_intraday_reentry_at_original_entry"])
                obj, disabled = self.event(rows, short=short)
                self.assertIsNone(disabled)
                self.assertEqual(obj.stage847_stop_retry_event_count, 0)

    def test_disabled_switch_never_enters_the_847_event_builder(self):
        obj = make_strategy([("2026-10-14 09:00", 100, 101, 89, 100)])
        def forbidden(trade):
            raise AssertionError("disabled 0.5R event builder was entered")
        obj._stage847_stop_retry_event_after_open_trade = forbidden
        event = obj.stage827_intraday_exit_after_open_trade(opening_trade())
        self.assertEqual(event["exit_reason"], "stage827_intraday_c2_1r_stop")


class DeclaredAblationTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ADAPTER_PATH.is_file(), "Stage251 declared_ablation adapter is not implemented yet")
        spec = importlib.util.spec_from_file_location("stage251_ablation_under_test", ADAPTER_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.assertTrue(callable(getattr(module, "declared_ablation", None)), "declared_ablation API is missing")
        self.declared_ablation = module.declared_ablation
        self.original_builder = s901.build_official_live_strategy_overrides
        self.baseline = deepcopy(self.original_builder())
        self.addCleanup(setattr, s901, "build_official_live_strategy_overrides", self.original_builder)

    def assert_only_declared_delta(self, actual):
        self.assertEqual(set(actual), set(self.baseline))
        changes = {key: (self.baseline[key], actual[key]) for key in actual if self.baseline[key] != actual[key]}
        self.assertEqual(changes, {FLAG: (True, False)})
        self.assertIs(actual[FLAG], False)

    def test_a_preserves_the_complete_official_override_dictionary(self):
        with self.declared_ablation(s901, "A"):
            self.assertEqual(s901.build_official_live_strategy_overrides(), self.baseline)
        self.assertIs(s901.build_official_live_strategy_overrides, self.original_builder)

    def test_c_changes_exactly_one_boolean_and_preserves_all_other_parameters(self):
        with self.declared_ablation(s901, "C"):
            self.assert_only_declared_delta(s901.build_official_live_strategy_overrides())
        self.assertIs(s901.build_official_live_strategy_overrides, self.original_builder)
        self.assertEqual(self.original_builder(), self.baseline)

    def test_c_override_reaches_real_c2_behavior_through_the_901_alias(self):
        with self.declared_ablation(s901, "C"):
            settings = s901.build_official_live_strategy_overrides()
            obj = make_strategy([("2026-10-14 09:00", 100, 104, 89, 100)])
            for name in (FLAG, "enable_stage827_intraday_c2_stop", "stage827_intraday_c2_stop_r",
                         "stage827_intraday_c2_confirm_r", "stage847_stop_retry_r", "stage847_max_retries"):
                # As in strategy construction, omitted override keys retain
                # their inherited class defaults; do not invent extra knobs.
                if name in settings:
                    setattr(obj, name, settings[name])
            event = obj.stage827_intraday_exit_after_open_trade(opening_trade())
            self.assertEqual(event["exit_reason"], "stage827_intraday_c2_1r_stop")
            self.assertEqual(event["fill_price"], 90.0)
            self.assertEqual(obj.stage847_stop_retry_events, [])

    def test_exception_restores_alias_without_swallowing_the_original_failure(self):
        failure = RuntimeError("controlled replay failure")
        with self.assertRaises(RuntimeError) as raised:
            with self.declared_ablation(s901, "C"):
                self.assert_only_declared_delta(s901.build_official_live_strategy_overrides())
                raise failure
        self.assertIs(raised.exception, failure)
        self.assertIs(s901.build_official_live_strategy_overrides, self.original_builder)
        self.assertEqual(self.original_builder(), self.baseline)

    def test_a_c_a_sequence_does_not_leak_candidate_parameters(self):
        observed = []
        for arm in ("A", "C", "A"):
            with self.declared_ablation(s901, arm):
                observed.append(deepcopy(s901.build_official_live_strategy_overrides()))
            self.assertIs(s901.build_official_live_strategy_overrides, self.original_builder)
        self.assertEqual(observed[0], self.baseline)
        self.assert_only_declared_delta(observed[1])
        self.assertEqual(observed[2], self.baseline)

    def test_shared_builder_dictionary_is_never_mutated_in_place(self):
        shared = deepcopy(self.baseline)
        namespace = SimpleNamespace(build_official_live_strategy_overrides=lambda: shared)
        original = namespace.build_official_live_strategy_overrides
        with self.declared_ablation(namespace, "C"):
            self.assert_only_declared_delta(namespace.build_official_live_strategy_overrides())
            self.assertEqual(shared, self.baseline)
        self.assertIs(namespace.build_official_live_strategy_overrides, original)
        self.assertEqual(shared, self.baseline)

    def test_invalid_arm_is_rejected_before_alias_mutation(self):
        with self.assertRaises(ValueError):
            with self.declared_ablation(s901, "B"):
                self.fail("unsupported arm entered the research scope")
        self.assertIs(s901.build_official_live_strategy_overrides, self.original_builder)
        self.assertEqual(self.original_builder(), self.baseline)


class CaptureActualSettingsTests(unittest.TestCase):
    """Exercise the real vendor constructor boundary, without loading market data."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location("stage251_capture_under_test", ADAPTER_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.capture = module.capture_actual_settings

    def engine_and_strategy(self, *, local_method=False):
        class ProbeStrategy(StrategyTemplate):
            parameters = [FLAG, "enable_stage827_intraday_c2_stop", "capital_base"]
            enable_stage847_half_r_stop_retry = True
            enable_stage827_intraday_c2_stop = True
            capital_base = 0.0

            def on_init(self):
                pass

            def on_bars(self, bars):
                pass

        class ProbeEngine(BacktestingEngine):
            pass

        if local_method:
            def add_strategy(engine, strategy_class, setting):
                return BacktestingEngine.add_strategy(engine, strategy_class, setting)
            ProbeEngine.add_strategy = add_strategy
        engine = object.__new__(ProbeEngine)
        engine.vt_symbols = ["cu2611.SHFE"]
        engine.capital = 150000.0
        return engine, ProbeStrategy

    def setting(self, *, metadata=True):
        setting = {FLAG: False, "enable_stage827_intraday_c2_stop": True, "capital_base": 150000.0}
        if metadata:
            setting.update(account_capital=150000.0, c3_capital=150000.0)
        return setting

    def test_capital_metadata_is_validated_against_engine_not_strategy_attributes(self):
        engine, strategy = self.engine_and_strategy()
        cls = type(engine)
        original = cls.add_strategy
        setting = self.setting()
        with self.capture(cls) as rows:
            engine.add_strategy(strategy, setting)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["setting"], setting)
        self.assertEqual(rows[0]["actual"], self.setting(metadata=False))
        self.assertEqual(rows[0]["non_strategy_fields"], {"account_capital": 150000.0, "c3_capital": 150000.0})
        self.assertEqual(rows[0]["engine_capital"], 150000.0)
        self.assertIs(engine.strategy.enable_stage847_half_r_stop_retry, False)
        self.assertIs(cls.add_strategy, original)
        self.assertNotIn("add_strategy", cls.__dict__)

    def test_no_metadata_setting_still_captures_all_real_strategy_values(self):
        engine, strategy = self.engine_and_strategy()
        setting = self.setting(metadata=False)
        with self.capture(type(engine)) as rows:
            engine.add_strategy(strategy, setting)
        self.assertEqual(rows[0]["actual"], setting)
        self.assertEqual(rows[0]["non_strategy_fields"], {})

    def test_unknown_missing_setting_key_is_not_hidden_by_the_capital_exception(self):
        engine, strategy = self.engine_and_strategy()
        cls = type(engine)
        original = cls.add_strategy
        setting = self.setting()
        setting["misspelled_risk_ratio"] = 0.018
        with self.assertRaises(ValueError):
            with self.capture(cls):
                engine.add_strategy(strategy, setting)
        self.assertIs(cls.add_strategy, original)
        self.assertNotIn("add_strategy", cls.__dict__)

    def test_each_capital_metadata_field_must_equal_engine_capital(self):
        for field in ("account_capital", "c3_capital"):
            with self.subTest(field=field):
                engine, strategy = self.engine_and_strategy()
                setting = self.setting()
                setting[field] = 100000.0
                with self.assertRaises(ValueError):
                    with self.capture(type(engine)):
                        engine.add_strategy(strategy, setting)

    def test_ignored_false_ablation_flag_is_still_rejected(self):
        engine, base = self.engine_and_strategy()
        class IgnoredFlagStrategy(base):
            parameters = ["enable_stage827_intraday_c2_stop", "capital_base"]
        with self.assertRaises(ValueError):
            with self.capture(type(engine)):
                engine.add_strategy(IgnoredFlagStrategy, self.setting())
        self.assertIs(engine.strategy.enable_stage847_half_r_stop_retry, True)

    def test_constructor_value_changes_are_still_rejected(self):
        engine, base = self.engine_and_strategy()
        class ChangedRiskStrategy(base):
            def __init__(self, *args):
                super().__init__(*args)
                self.capital_base = 140000.0
        with self.assertRaises(ValueError):
            with self.capture(type(engine)):
                engine.add_strategy(ChangedRiskStrategy, self.setting())

    def test_constructor_exception_restores_local_method_and_propagates(self):
        engine, base = self.engine_and_strategy(local_method=True)
        cls = type(engine)
        original = cls.add_strategy
        failure = RuntimeError("controlled constructor failure")
        class FailingStrategy(base):
            def __init__(self, *args):
                raise failure
        with self.assertRaises(RuntimeError) as raised:
            with self.capture(cls):
                engine.add_strategy(FailingStrategy, self.setting())
        self.assertIs(raised.exception, failure)
        self.assertIs(cls.__dict__["add_strategy"], original)


class CanonicalTradeEnumsTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("stage251_enum_under_test", ADAPTER_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.canonicalize = module.canonical_trade_enums

    def test_english_and_chinese_exports_have_the_same_canonical_meaning(self):
        english = pd.DataFrame({
            "direction": ["Long", "Short", "Long", "Short"],
            "offset": ["Open", "Close", "Close Today", "Close Yesterday"],
            "trade_id": ["1", "2", "3", "4"],
        })
        expected = pd.DataFrame({
            "direction": ["多", "空", "多", "空"],
            "offset": ["开", "平", "平今", "平昨"],
            "trade_id": ["1", "2", "3", "4"],
        })
        pd.testing.assert_frame_equal(self.canonicalize(english), expected)
        pd.testing.assert_frame_equal(self.canonicalize(expected), expected)

    def test_normalization_does_not_mutate_input_or_other_columns(self):
        original = pd.DataFrame({"direction": ["Long"], "offset": ["Open"],
                                 "price": [100.0], "volume": [2]}, index=[7])
        snapshot = original.copy(deep=True)
        normalized = self.canonicalize(original)
        pd.testing.assert_frame_equal(original, snapshot)
        pd.testing.assert_frame_equal(normalized[["price", "volume"]], snapshot[["price", "volume"]])
        self.assertEqual(normalized.loc[7, "direction"], "多")
        self.assertEqual(normalized.loc[7, "offset"], "开")

    def test_unknown_direction_or_offset_is_rejected(self):
        for direction, offset in [("Net", "Open"), ("Long", "None"), (None, "Open"), ("Short", None)]:
            with self.subTest(direction=direction, offset=offset):
                frame = pd.DataFrame({"direction": [direction], "offset": [offset]})
                with self.assertRaises(ValueError):
                    self.canonicalize(frame)


if __name__ == "__main__":
    unittest.main()
