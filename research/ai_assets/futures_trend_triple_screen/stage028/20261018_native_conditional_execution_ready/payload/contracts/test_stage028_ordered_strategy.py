"""Behavioral boundaries for the conditional strategy adapter (no backtest)."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest

try:
    from stage028_ordered_strategy import build_ordered_strategy
except ImportError:
    build_ordered_strategy = None


PRODUCT = "rb.SHFE"
CONTRACT = "rb2005.SHFE"
DAYS = {"2019-12-31": "2020-01-02", "2020-01-02": "2020-01-03",
        "2020-01-03": "2020-01-06", "2020-01-06": "2020-01-07",
        "2020-01-07": "2020-01-08", "2020-01-08": "2020-01-09"}


def bar(day, high=110., low=90., close=100.):
    return SimpleNamespace(datetime=datetime.fromisoformat(day), high_price=high,
                           low_price=low, close_price=close, open_price=100.)


class State:
    def __init__(self, product):
        self.product_vt_symbol = product
        self.contract_vt_symbol = ""
        self.layers = []

    def __deepcopy__(self, memo):
        raise AssertionError("mutable account state must never be frozen")


class Weekly:
    def __init__(self):
        self.changes = {}
        self.requests = []

    def get(self, day, product):
        self.requests.append((day, product))
        asof = "2019-12-27" if day <= "2020-01-03" else "2020-01-03"
        return {"ready": True, "direction": 1, "weekly_asof": asof, **self.changes}


class Base:
    """A small account consumer; external sizing and the market are excluded."""
    def __init__(self):
        self.product_symbols = [PRODUCT]
        self.states = {PRODUCT: State(PRODUCT)}
        self.daily_mapping = {day: {PRODUCT: CONTRACT} for day in DAYS}
        self.source_symbol_by_contract = {CONTRACT: PRODUCT}
        self.positions = {}
        self.plans = {}
        self.contexts = []
        self.gate = True
        self.ai_allowed = True
        self.ai_days = []
        self.events = []
        self.targets = {}
        self.am_updates = 0
        self.stage827_minute_by_symbol = {}
        self.hook_error = False

    def on_bars(self, bars):
        if not bars:
            return
        self.am_updates += 1
        plans = self._plan_flat_entry_candidates(self.contexts) if self.gate else {}
        self.last_plans = plans
        for context in self.contexts:
            plan = plans.get(context.product_vt_symbol)
            if plan is None:
                self.events.append(("old_add", context.product_vt_symbol))
                continue
            self._record_entry_candidate_snapshot(
                product_vt_symbol=context.product_vt_symbol,
                contract_vt_symbol=context.target_contract,
                direction=plan["direction"], bar=context.target_bar,
                signal=plan["signal"], entry_context="flat_entry",
                candidate_status=plan["candidate_status"],
                skip_reason=plan["skip_reason"], signal_data=context.signal_data,
                sizing_snapshot=plan["sizing"], active_positions_before=0)
            if plan["candidate_status"] == "opened":
                self._open_position(self.states[context.product_vt_symbol], context.target_contract,
                                    plan["direction"], plan["volume"], context.target_bar,
                                    plan["signal"], context.history, context.signal_data,
                                    sizing_snapshot=plan["sizing"])
                self._reserve_intrabar_entry(context.product_vt_symbol, plan["sizing"],
                                             plan["volume"], count_active_position=True)
                self._apply_state_target(self.states[context.product_vt_symbol])

    def _plan_flat_entry_candidates(self, contexts):
        self.events.append(("native_planner", len(contexts)))
        return {product: deepcopy(plan) for product, plan in self.plans.items()}

    def _record_entry_candidate_snapshot(self, **fields):
        self.events.append(("snapshot", fields["product_vt_symbol"], fields["candidate_status"]))

    def _reserve_intrabar_entry(self, product, sizing, volume, *, count_active_position):
        self.events.append(("reserve", product, volume, count_active_position))

    def _ai_product_pool_entry_allowed(self, product, trade_date):
        self.ai_days.append((product, trade_date.date().isoformat()))
        return self.ai_allowed, {}

    def _resolve_actual_position(self, state, target_contract, bars):
        for symbol in [state.contract_vt_symbol, target_contract, *bars]:
            if symbol and self.source_symbol_by_contract.get(symbol) == state.product_vt_symbol:
                if self.get_pos(symbol):
                    return symbol, self.get_pos(symbol), bars.get(symbol)
        return target_contract, 0, bars.get(target_contract)

    def get_pos(self, contract):
        return self.positions.get(contract, 0)

    def get_pricetick(self, contract):
        return 1.

    def _open_position(self, state, contract, direction, volume, target_bar,
                       signal, history, signal_data, sizing_snapshot=None):
        self.events.append(("open", state, contract, direction, volume, target_bar,
                            signal, history, signal_data, sizing_snapshot))
        state.contract_vt_symbol = contract
        state.entry_date = target_bar.datetime.date().isoformat()
        state.layers = [SimpleNamespace(volume=volume, highest_price=target_bar.high_price,
            lowest_price=target_bar.low_price, stop_price=sizing_snapshot["stop_price"])]

    def _apply_state_target(self, state):
        self.targets[state.contract_vt_symbol] = state.layers[0].volume

    def stage827_intraday_exit_after_open_trade(self, trade):
        frame = self.stage827_minute_by_symbol[trade.vt_symbol]
        self.hook_view = frame
        if self.hook_error:
            raise RuntimeError("downstream_error")
        return frame["open"].tolist()


def context(strategy, day, product=PRODUCT, contract=CONTRACT):
    return SimpleNamespace(product_vt_symbol=product, state=strategy.states[product],
        target_contract=contract, target_bar=bar(day), current_pos=0,
        history={"prior": [95.]}, signal_data={"signal": "long_case1a", "nested": [7]})


def plan(volume=3, status="opened", rank=1):
    return dict(product_vt_symbol=PRODUCT, direction="long", signal="long_case1a",
        native_openable=True, candidate_status=status, skip_reason="" if status == "opened" else "concurrent_limit",
        volume=volume, selection_pairwise_rank=rank,
        sizing={"selected_volume": volume, "stop_price": 85., "margin_per_contract": 100.})


class OrderedStrategyTests(unittest.TestCase):
    def strategy(self):
        self.assertIsNotNone(build_ordered_strategy, "conditional adapter is not implemented")
        weekly = Weekly()
        fi = {(day, CONTRACT): dict(ready=True, fi2=-1.) for day in DAYS}
        strategy = build_ordered_strategy(Base, weekly, fi, DAYS)()
        return strategy, weekly, fi

    def observe(self, strategy, day, native=False):
        strategy.contexts = [context(strategy, day)]
        strategy.plans = {PRODUCT: plan()} if native else {}
        strategy.on_bars({CONTRACT: strategy.contexts[0].target_bar})

    def prepared(self):
        strategy, weekly, fi = self.strategy()
        self.observe(strategy, "2020-01-02")
        self.observe(strategy, "2020-01-03", native=True)
        return strategy, weekly, fi

    def test_setup_without_native_then_selected_plan_is_pending_without_layer(self):
        strategy, weekly, _ = self.prepared()
        item = strategy.ts_pending_intents[0]
        self.assertEqual((item["setup_day"], item["signal_day"], item["execution_day"]),
                         ("2020-01-02", "2020-01-03", "2020-01-06"))
        self.assertEqual(item["trigger"], 111.)
        self.assertEqual(item["rank"], 1)
        self.assertEqual(item["plan"]["volume"], 3)
        self.assertEqual(strategy.last_plans[PRODUCT]["candidate_status"], "conditional_pending")
        self.assertEqual(strategy.states[PRODUCT].layers, [])
        self.assertEqual(strategy.targets, {})
        self.assertEqual(strategy.events[-2:], [("snapshot", PRODUCT, "conditional_pending"),
                                                ("reserve", PRODUCT, 3, True)])
        self.assertEqual(strategy.am_updates, 2)
        self.assertEqual(weekly.requests, [("2020-01-02", "SHFE.RB"), ("2020-01-03", "SHFE.RB")])

    def test_gate_false_and_am_missing_context_observe_once_but_never_emit(self):
        strategy, _, _ = self.strategy()
        strategy.gate = False
        self.observe(strategy, "2019-12-31", native=True)
        self.assertEqual(strategy.ts_decision_audit, [])
        self.observe(strategy, "2020-01-02", native=True)
        self.assertEqual(strategy.ts_pending_intents, [])
        strategy.gate = True
        self.observe(strategy, "2020-01-03", native=True)
        self.assertEqual(strategy.ts_pending_intents[0]["setup_day"], "2020-01-02")
        strategy.contexts = []
        strategy.plans = {}
        strategy.on_bars({CONTRACT: bar("2020-01-06")})
        self.assertEqual(len(strategy.ts_decision_audit), 3)
        self.assertEqual(strategy.ts_pending_intents, [])
        self.assertEqual(strategy.am_updates, 4)

    def test_unknown_fallback_retains_native_open_and_blocked_status(self):
        strategy, weekly, fi = self.strategy()
        fi[("2020-01-02", CONTRACT)] = dict(ready=False, fi2=None)
        self.observe(strategy, "2020-01-02", native=True)
        self.assertEqual(strategy.last_plans[PRODUCT]["candidate_status"], "opened")
        self.assertEqual(len(strategy.states[PRODUCT].layers), 1)
        self.assertEqual(strategy.ts_pending_intents, [])
        strategy.states[PRODUCT].layers = []
        strategy.plans = {PRODUCT: plan(status="skipped")}
        strategy.contexts = [context(strategy, "2020-01-03")]
        fi[("2020-01-03", CONTRACT)] = dict(ready=False, fi2=None)
        strategy.on_bars({CONTRACT: bar("2020-01-03")})
        self.assertEqual(strategy.last_plans[PRODUCT]["candidate_status"], "skipped")
        self.assertEqual(strategy.last_plans[PRODUCT]["skip_reason"], "concurrent_limit")

    def test_known_position_or_ai_block_dominates_unknown_fallback(self):
        for hard in ["position", "ai"]:
            with self.subTest(hard=hard):
                strategy, _, fi = self.strategy()
                fi[("2020-01-02", CONTRACT)] = dict(ready=False, fi2=None)
                if hard == "position":
                    strategy.positions[CONTRACT] = 1
                else:
                    strategy.ai_allowed = False
                self.observe(strategy, "2020-01-02", native=True)
                self.assertEqual(strategy.last_plans[PRODUCT]["candidate_status"], "filtered")
                self.assertFalse(strategy.ts_pending_intents)
                self.assertFalse(any(event[0] == "open" for event in strategy.events))
                self.assertEqual(strategy.ts_decision_audit[-1]["decision"], "blocked")
                self.assertEqual(strategy.ai_days[-1], (PRODUCT, "2020-01-02"))

    def test_missing_real_bar_cancels_setup_without_unknown_fallback(self):
        strategy, _, _ = self.strategy()
        self.observe(strategy, "2020-01-02")
        strategy.contexts = []
        strategy.on_bars({"other2005.SHFE": bar("2020-01-03")})
        self.assertEqual(strategy.ts_decision_audit[-1]["cancel_reason"], "target_real_bar_missing")
        self.observe(strategy, "2020-01-06", native=True)
        self.assertEqual(strategy.ts_pending_intents, [])
        self.assertEqual(strategy.last_plans[PRODUCT]["candidate_status"], "filtered")

    def test_frozen_plan_uses_true_state_and_signal_day_despite_late_fill(self):
        strategy, _, _ = self.prepared()
        item = strategy.ts_pending_intents[0]
        source = strategy.contexts[0]
        source.history["prior"][0] = -900
        source.signal_data["nested"][0] = -900
        source.target_bar.high_price = 99999
        strategy.last_plans[PRODUCT]["sizing"]["stop_price"] = -900
        strategy.estimated_equity = -999999
        true_state = strategy.states[PRODUCT]
        strategy.ts_activate_intent(item, 115.)
        opened = [event for event in strategy.events if event[0] == "open"][-1]
        self.assertIs(opened[1], true_state)
        self.assertEqual((opened[4], opened[5].datetime.date().isoformat(), opened[9]["stop_price"]),
                         (3, "2020-01-03", 85.))
        self.assertEqual(opened[7], {"prior": [95.]})
        self.assertEqual(opened[8]["nested"], [7])
        self.assertEqual((true_state.layers[0].highest_price, true_state.layers[0].lowest_price), (115., 115.))
        self.assertEqual(true_state.entry_date, "2020-01-03")
        strategy.ts_commit_fill(item, "2020-01-06", "BACKTEST.1",
                                dict(fill_price=115., execution_datetime="2020-01-03T21:12:00"))
        self.assertEqual(strategy.ts_fill_audit[0]["signal_day"], "2020-01-03")
        with self.assertRaises(ValueError):
            strategy.ts_commit_fill(item, "2020-01-06", "BACKTEST.1", {})

    def test_zero_quantity_or_actual_nonflat_cannot_activate(self):
        strategy, _, _ = self.prepared()
        item = strategy.ts_pending_intents[0]
        for bad in [0, -1]:
            invalid = {**item, "plan": {**item["plan"], "volume": bad}}
            with self.assertRaises(ValueError):
                strategy.ts_activate_intent(invalid, 115.)
        strategy.positions[CONTRACT] = 1
        with self.assertRaises(ValueError):
            strategy.ts_activate_intent(item, 115.)
        self.assertEqual(strategy.targets, {})
        strategy.positions.clear()
        strategy.source_symbol_by_contract["rb1910.SHFE"] = PRODUCT
        strategy.positions["rb1910.SHFE"] = -1
        with self.assertRaises(ValueError):
            strategy.ts_activate_intent(item, 115.)

    def test_filtered_slot_is_not_reallocated_and_reservation_keeps_product_order(self):
        strategy, _, fi = self.strategy()
        self.observe(strategy, "2020-01-02")
        other_product, other_contract = "cu.SHFE", "cu2005.SHFE"
        strategy.product_symbols.insert(0, other_product)
        strategy.states[other_product] = State(other_product)
        strategy.source_symbol_by_contract[other_contract] = other_product
        strategy.daily_mapping["2020-01-03"][other_product] = other_contract
        strategy.contexts = [context(strategy, "2020-01-03", other_product, other_contract),
                             context(strategy, "2020-01-03")]
        strategy.plans = {PRODUCT: plan()}
        strategy.events.clear()
        strategy.on_bars({other_contract: bar("2020-01-03"), CONTRACT: bar("2020-01-03")})
        self.assertEqual(strategy.events[:4], [("native_planner", 2), ("old_add", other_product),
            ("snapshot", PRODUCT, "conditional_pending"), ("reserve", PRODUCT, 3, True)])
        # A new account has no earlier preparation: filtering native winner rb
        # must not allocate its old slot to native concurrent-limit loser cu.
        strategy, _, fi = self.strategy()
        strategy.product_symbols.append(other_product)
        strategy.states[other_product] = State(other_product)
        strategy.source_symbol_by_contract[other_contract] = other_product
        strategy.daily_mapping["2020-01-02"][other_product] = other_contract
        fi[("2020-01-02", other_contract)] = dict(ready=True, fi2=-1.)
        strategy.contexts = [context(strategy, "2020-01-02"),
                            context(strategy, "2020-01-02", other_product, other_contract)]
        strategy.plans = {PRODUCT: plan(), other_product: plan(status="skipped", rank=2)}
        strategy.on_bars({CONTRACT: bar("2020-01-02"), other_contract: bar("2020-01-02")})
        self.assertEqual(strategy.last_plans[PRODUCT]["candidate_status"], "filtered")
        self.assertEqual(strategy.last_plans[other_product]["candidate_status"], "skipped")
        self.assertEqual(strategy.ts_pending_intents, [])
        self.assertEqual(strategy.targets, {})

    def test_conditional_intrabar_view_changes_only_fill_minute_open_and_restores(self):
        # A wrong symbol, earlier minute, entire-frame mutation or missing finally
        # would all change these independently specified visible observations.
        strategy, _, _ = self.strategy()
        frame = Frame(["2020-01-03T21:11:00", "2020-01-03T21:12:00"], [98., 100.])
        other = Frame(["2020-01-03T21:12:00"], [80.])
        original = {CONTRACT: frame, "cu2005.SHFE": other}
        strategy.stage827_minute_by_symbol = original
        trade = SimpleNamespace(vt_orderid="BACKTEST.1", orderid="1", vt_symbol=CONTRACT)
        strategy.ts_conditional_orders["BACKTEST.1"] = dict(intrabar=True,
            execution_datetime="2020-01-03T21:12:00", fill_price=111.)
        self.assertEqual(strategy.stage827_intraday_exit_after_open_trade(trade), [98., 111.])
        self.assertIs(strategy.stage827_minute_by_symbol, original)
        self.assertEqual(frame["open"].tolist(), [98., 100.])
        self.assertIs(original["cu2005.SHFE"], other)
        strategy.hook_error = True
        with self.assertRaisesRegex(RuntimeError, "downstream_error"):
            strategy.stage827_intraday_exit_after_open_trade(trade)
        self.assertIs(strategy.stage827_minute_by_symbol, original)

    def test_ordinary_and_gap_open_keep_original_minute_view(self):
        strategy, _, _ = self.strategy()
        frame = Frame(["2020-01-03T21:12:00"], [115.])
        original = {CONTRACT: frame}
        strategy.stage827_minute_by_symbol = original
        trade = SimpleNamespace(vt_orderid="BACKTEST.1", orderid="1", vt_symbol=CONTRACT)
        for metadata in [None, dict(intrabar=False, execution_datetime="2020-01-03T21:12:00", fill_price=116.)]:
            strategy.ts_conditional_orders = {} if metadata is None else {"BACKTEST.1": metadata}
            self.assertEqual(strategy.stage827_intraday_exit_after_open_trade(trade), [115.])
            self.assertIs(strategy.hook_view, frame)

    def test_actual_847_both_directions_adverse_first_retry_and_c2_fallback(self):
        # Exercise the actual 847 -> 827 -> execution chain in the accepted
        # numerical runtime.  No market replay, model inference, or engine run.
        script = r'''
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys
sys.path.insert(0, str(Path.cwd()))
import stage022_run_c0_qualified_wait as runner
with tempfile.TemporaryDirectory() as temporary:
    runner.OUTPUT = Path(temporary)/"outputs"
    runner.configure_runtime(Path(temporary)/"shared")
    import pandas as pd
    import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as upstream
    from qmt_roll_portfolio_strategy import ProductState, PositionLayer
    from stage028_ordered_strategy import build_ordered_strategy
    Strategy = build_ordered_strategy(upstream.QmtRollPortfolioStrategyStage847C9StopRetry, None, {}, {})
    for direction, fill, stop, first, second, wanted in [
        ("long", 110., 90., [95., 125., 94., 110.], [100., 111., 99., 105.], [100., 110., 100.]),
        ("short", 90., 110., [105., 106., 75., 90.], [100., 101., 89., 95.], [100., 90., 100.])]:
        strategy = Strategy.__new__(Strategy)
        strategy.enable_stage847_half_r_stop_retry = True
        strategy.enable_stage827_intraday_c2_stop = True
        strategy.stage847_stop_retry_r = .5
        strategy.stage847_max_retries = 1
        strategy.stage847_stop_retry_event_count = 0
        strategy.stage847_stop_retry_events = []
        strategy.available_trade_dates = [pd.Timestamp("2020-01-03"), pd.Timestamp("2020-01-06")]
        strategy.strategy_engine = SimpleNamespace(get_pricetick=lambda strategy, symbol: 1.)
        layer = PositionLayer("base", direction, 3, fill, stop, fill, fill, direction+"_case1a", "2020-01-03")
        strategy.states = {"rb.SHFE": ProductState("rb.SHFE", "rb2005.SHFE", direction, layers=[layer])}
        times = pd.to_datetime(["2020-01-06T14:58:00", "2020-01-06T14:59:00"])
        frame = pd.DataFrame([first, second], columns=["open", "high", "low", "close"])
        frame["bar_datetime"] = times
        original = {"rb2005.SHFE": frame}
        strategy.stage827_minute_by_symbol = original
        strategy.ts_conditional_orders = {"BACKTEST.1": dict(intrabar=True, execution_datetime=times[0], fill_price=fill)}
        trade = SimpleNamespace(vt_orderid="BACKTEST.1", orderid="1", vt_symbol="rb2005.SHFE", vt_tradeid="BACKTEST.1",
            direction=upstream.s827.Direction.LONG if direction == "long" else upstream.s827.Direction.SHORT,
            price=fill, datetime=pd.Timestamp("2020-01-06"), trading_date="2020-01-06", execution_datetime=times[0])
        event = strategy.stage827_intraday_exit_after_open_trade(trade)
        assert [item["price"] for item in event["synthetic_trades"]] == wanted, event
        assert event["first_stop_bar_index"] == 0 and event["reentry_bar_index"] == 1, event
        assert event["note"] == "same_bar_conservative_stop_first", event
        assert strategy.stage827_minute_by_symbol is original
        assert frame["open"].tolist() == [first[0], second[0]]
        # Disable only 0.5R: the same adapter view must wrap the inherited C2
        # implementation too.  Its original S is reached on the first minute.
        strategy.enable_stage847_half_r_stop_retry = False
        strategy.stage827_intraday_c2_stop_count = 0
        strategy.stage827_intraday_c2_events = []
        frame.loc[0, "open"] = 85. if direction == "long" else 115.
        frame.loc[0, "low"] = 84. if direction == "long" else 65.
        frame.loc[0, "high"] = 135. if direction == "long" else 116.
        fallback = strategy.stage827_intraday_exit_after_open_trade(trade)
        assert fallback["fill_price"] == stop, fallback
        assert fallback["note"] == "same_bar_conservative_stop_first", fallback
        assert strategy.stage827_minute_by_symbol is original
    # D's earlier low must remain available to AM/history/env, while daily
    # management of a still-open conditional lot sees only its actual lifetime.
    class HoldingBase:
        def _build_daily_env_gate_snapshot(self, contexts):
            return {"full_daily_low": contexts[0].target_bar.low_price}
    Holding = build_ordered_strategy(HoldingBase, None, {}, {})
    held = Holding()
    for day, next_day, native in [("2020-01-02", "2020-01-03", None),
                                  ("2020-01-03", "2020-01-06", "long_case1a")]:
        observation = held.ts_machine.on_close(product="rb.SHFE", contract="rb2005.SHFE", day=day,
            next_day=next_day, high=110., low=90., tick=1., weekly_ready=True,
            weekly_direction=1, weekly_asof="2019-12-27", fi_ready=True, fi2=-1.,
            eligible=True, position_open=False, native_signal=native)
    item = {**observation["intent"], "rank": 1, "plan": {"volume": 3, "sizing": {"stop_price": 85.}}}
    held.ts_commit_fill(item, "2020-01-06", "BACKTEST.2", {"execution_datetime": "2020-01-06T11:00:00", "fill_price": 111.})
    held.available_trade_dates = [pd.Timestamp("2020-01-03"), pd.Timestamp("2020-01-06")]
    expected = upstream.s827.execution.session_minutes("rb2005.SHFE", "2020-01-06", held.available_trade_dates)
    minutes = pd.DataFrame({"bar_datetime": expected, "open": 110., "high": 114., "low": 108., "close": 110.})
    minutes.loc[minutes["bar_datetime"] < pd.Timestamp("2020-01-06T11:00:00"), "low"] = 80.
    held.stage827_minute_by_symbol = {"rb2005.SHFE": minutes}
    raw_bar = SimpleNamespace(datetime=pd.Timestamp("2020-01-06"), vt_symbol="rb2005.SHFE",
        open_price=100., high_price=130., low_price=80., close_price=110., volume=99, open_interest=12)
    management = SimpleNamespace(product_vt_symbol="rb.SHFE", target_contract="rb2005.SHFE", current_pos=3,
        target_bar=raw_bar, actual_bar=raw_bar, history={"low": 80.}, signal_data={"day_low": 80.})
    env = held._build_daily_env_gate_snapshot([management])
    assert management.target_bar.low_price == 108., management.target_bar
    assert management.actual_bar.low_price == 108.
    assert management.target_bar.open_price == 111.
    assert management.target_bar.close_price == 110. and management.target_bar.volume == 99
    assert management.target_bar.open_interest == 12
    assert raw_bar.low_price == 80. and management.history["low"] == 80.
    assert management.signal_data["day_low"] == 80. and env["full_daily_low"] == 80.
    assert minutes["low"].min() == 80.
    management.target_bar = raw_bar
    management.actual_bar = raw_bar
    held.stage827_minute_by_symbol = {"rb2005.SHFE": minutes.drop(minutes.index[-1])}
    held.stage827_require_complete_minutes = False
    try:
        held._build_daily_env_gate_snapshot([management])
    except ValueError as error:
        assert "intraday_minute_coverage" in str(error), error
    else:
        raise AssertionError("conditional holding management accepted a missing post-entry minute")
    # No view is carried into the next day or into an ordinary account.
    next_bar = SimpleNamespace(**{**raw_bar.__dict__, "datetime": pd.Timestamp("2020-01-07")})
    management.target_bar = management.actual_bar = next_bar
    held._build_daily_env_gate_snapshot([management])
    assert management.target_bar is next_bar and next_bar.low_price == 80.
    ordinary = Holding()
    management.target_bar = management.actual_bar = raw_bar
    ordinary._build_daily_env_gate_snapshot([management])
    assert management.target_bar is raw_bar
    print("actual_847_long_short_and_c2_passed")
'''
        directory = Path(__file__).resolve().parent
        result = subprocess.run([sys.executable, "-c", script], cwd=directory,
                                text=True, capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("actual_847_long_short_and_c2_passed", result.stdout)


class Column(list):
    def tolist(self):
        return list(self)

    def __eq__(self, value):
        return [item == value for item in self]


class Loc:
    def __init__(self, frame): self.frame = frame
    def __setitem__(self, key, value):
        selector, column = key
        for index, match in enumerate(selector):
            if match: self.frame.columns[column][index] = value


class Frame:
    """Only the pandas boundary used by this adapter; no numerical emulation."""
    def __init__(self, times, opens):
        self.columns = {"bar_datetime": Column(datetime.fromisoformat(t) for t in times),
                        "open": Column(opens), "high": Column([120.] * len(opens)),
                        "low": Column([90.] * len(opens)), "close": Column([110.] * len(opens))}
        self.loc = Loc(self)
    def __getitem__(self, name): return self.columns[name]
    def copy(self, deep=True): return deepcopy(self)


if __name__ == "__main__":
    unittest.main()
