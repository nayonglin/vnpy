"""New B signal/consumer boundaries only; no market replay or model loading."""
from copy import deepcopy
from datetime import datetime
import unittest
from unittest.mock import patch

from test_stage028_ordered_strategy import Base, Weekly, State, bar, context, PRODUCT, CONTRACT, DAYS

try:
    from stage035_b_ts_strategy import build_b_strategy
except ImportError:
    build_b_strategy = None


class NativeConsumer(Base):
    """Reuse 028's small product loop, replacing only native candidate creation."""
    def __init__(self):
        super().__init__()
        self.filter_allowed = True
        self.filter_calls = []
        self.oi_calls = []
        self.volume_oi = "volume_oi"
        self.oi = "oi"
        self.quantity = 12
        self.risk_amount = 1200.
        self.min_position_size, self.max_position_size = 1, 500
        self.entry_candidate_snapshots = []

    def _passes_entry_filters(self, signal, history):
        self.filter_calls.append((signal, history))
        return self.filter_allowed

    def _volume_open_interest_risk_mode(self, history):
        self.oi_calls.append(("volume_oi", history))
        return self.volume_oi

    def _open_interest_risk_mode(self, history):
        self.oi_calls.append(("oi", history))
        return self.oi

    def _can_open_short_signal(self, signal):
        return signal == "short_case1a"

    def _plan_flat_entry_candidates(self, contexts):
        self.events.append(("native_planner", len(contexts)))
        self.native_contexts = list(contexts)
        plans = {}
        for candidate in contexts:
            signal = candidate.signal_data.get("signal", "")
            if candidate.current_pos or not signal:
                continue
            direction = "long" if signal.startswith("long") else "short"
            if direction == "short" and not self._can_open_short_signal(signal):
                continue
            # Literal hand budget: long T111,S99,size10 => rho120/m111.
            # Short mirror T89,S101 => rho120/m89.
            trigger, stop = (111., 99.) if direction == "long" else (89., 101.)
            margin = trigger
            sizing = dict(selected_volume=self.quantity, stop_price=stop,
                risk_per_contract=120., margin_per_contract=margin,
                risk_amount=self.risk_amount, limited_balance=100000.,
                single_trade_capital_limit=100000., reserved_margin_before=0.,
                contracts_by_risk=int(self.risk_amount // 120.),
                contracts_by_margin=int(100000. // margin),
                contracts_by_single_trade_cap=int(100000. // margin),
                b_ts_budget_equity_u=100000., b_ts_trigger=trigger,
                b_ts_trigger_price=trigger, b_ts_signal_close=100.,
                b_ts_signal_day=candidate.target_bar.datetime.date().isoformat(),
                b_ts_contract_size=10, b_ts_pricetick=1.,
                b_ts_min_position_size=1, b_ts_max_position_size=500,
                size=10, pricetick=1., margin_ratio=.1,
                stage830_broker10_margin_cap_enabled=0,
                risk_cluster_cap_enabled=0,
                risk_mode=candidate.signal_data["risk_mode"])
            plans[candidate.product_vt_symbol] = dict(
                product_vt_symbol=candidate.product_vt_symbol,
                contract_vt_symbol=candidate.target_contract,
                target_contract=candidate.target_contract,
                signal_day=candidate.target_bar.datetime.date().isoformat(),
                signal=signal, direction=direction, native_openable=True,
                volume=self.quantity, sizing=sizing, candidate_status="opened",
                selection_pairwise_rank=len(plans)+1, skip_reason="")
        return plans

    def _record_entry_candidate_snapshot(self, **fields):
        super()._record_entry_candidate_snapshot(**fields)
        self.entry_candidate_snapshots.append(dict(
            planned_entry_price=fields["bar"].close_price,
            stop_distance=abs(fields["bar"].close_price-fields["sizing_snapshot"]["stop_price"]),
            signal=fields["signal"], selected_volume=fields["sizing_snapshot"]["selected_volume"]))


class BStrategyTests(unittest.TestCase):
    def strategy(self, direction=1):
        self.assertIsNotNone(build_b_strategy, "independent B adapter is missing")
        weekly = Weekly()
        weekly.changes["direction"] = direction
        fi = {(day, CONTRACT): dict(ready=True, fi2=-direction) for day in DAYS}
        # This suite isolates B planning. Real trigger pricing/MRO is exercised
        # by Task1's native fixture and Task4's full native combination.
        with patch("stage035_b_ts_strategy.build_trigger_priced_base", side_effect=lambda base: base):
            strategy = build_b_strategy(NativeConsumer, weekly, fi, DAYS)()
        return strategy, weekly, fi

    def observe(self, strategy, day="2020-01-02", native=""):
        candidate = context(strategy, day)
        candidate.target_bar.low_price = 99. if strategy.ts_machine.arm == "B_TS" else 90.
        candidate.signal_data["signal"] = native
        strategy.contexts = [candidate]
        strategy.on_bars({CONTRACT: candidate.target_bar})
        return candidate

    def test_independent_labels_use_same_context_one_observation_and_generic_oi(self):
        # Break caught: retaining native absence, using a new context, observing
        # after planner, or letting old C label/short whitelist determine B.
        for direction, label, trigger in [(1, "long_triple_screen", 111.),
                                          (-1, "short_triple_screen", 89.)]:
            with self.subTest(direction=direction):
                strategy, weekly, _ = self.strategy(direction)
                candidate = context(strategy, "2020-01-02")
                candidate.signal_data["signal"] = ""
                original = candidate.signal_data
                strategy.contexts = [candidate]
                strategy.on_bars({CONTRACT: candidate.target_bar})
                self.assertIs(strategy.native_contexts[0], candidate)
                self.assertIsNot(candidate.signal_data, original)
                self.assertEqual(original["signal"], "")
                self.assertEqual(candidate.signal_data["signal"], label)
                self.assertEqual(candidate.signal_data["risk_mode"], "volume_oi")
                self.assertEqual(strategy.filter_calls, [(label, candidate.history)])
                self.assertEqual(strategy.oi_calls, [("volume_oi", candidate.history)])
                self.assertEqual(weekly.requests, [("2020-01-02", "SHFE.RB")])
                self.assertEqual(len(strategy.ts_decision_audit), 1)
                self.assertEqual((strategy.ts_pending_intents[0]["arm"],
                                  strategy.ts_pending_intents[0]["trigger"]), ("B_TS", trigger))
                self.assertFalse(strategy._can_open_short_signal("short_other"))
                self.assertTrue(strategy._can_open_short_signal("short_triple_screen"))
                self.assertEqual(strategy.states[PRODUCT].layers, [])
                self.assertEqual(strategy.targets, {})
        strategy, _, _ = self.strategy()
        strategy.volume_oi = ""
        self.observe(strategy)
        self.assertEqual(strategy.contexts[0].signal_data["risk_mode"], "oi")

    def test_unknown_filter_ai_missing_context_and_held_never_fallback_or_double_observe(self):
        # Break caught: stale native fallback, filter bypass, AM/context fallback,
        # held-context signal mutation, or 2019 preparation leakage.
        for blocked in ("unknown", "filter", "ai", "no_context", "no_bar", "entry_day"):
            with self.subTest(blocked=blocked):
                strategy, weekly, fi = self.strategy()
                candidate = context(strategy, "2020-01-02")
                strategy.contexts = [candidate]
                bars = {CONTRACT: candidate.target_bar}
                if blocked == "unknown": fi[("2020-01-02", CONTRACT)] = dict(ready=False, fi2=None)
                if blocked == "filter": strategy.filter_allowed = False
                if blocked == "ai": strategy.ai_allowed = False
                if blocked == "no_context": strategy.contexts = []
                if blocked == "no_bar": strategy.contexts = []; bars = {"other": bar("2020-01-02")}
                if blocked == "entry_day": strategy.gate = False
                strategy.on_bars(bars)
                self.assertEqual(strategy.ts_pending_intents, [])
                self.assertFalse(any(event[0] == "open" for event in strategy.events))
                self.assertFalse(strategy.ts_decision_audit[-1]["baseline_fallback"])
                self.assertEqual(len(strategy.ts_decision_audit), 1)
                if blocked in ("unknown", "filter", "ai"):
                    self.assertEqual(candidate.signal_data["signal"], "")
        strategy, weekly, _ = self.strategy()
        strategy.positions[CONTRACT] = 3
        candidate = context(strategy, "2020-01-02")
        candidate.current_pos = 3
        signal_data = candidate.signal_data
        strategy.contexts = [candidate]
        strategy.on_bars({CONTRACT: candidate.target_bar})
        self.assertIs(candidate.signal_data, signal_data)
        self.assertEqual(signal_data["signal"], "long_case1a")
        self.assertEqual(strategy.ts_decision_audit[-1]["cancel_reason"], "position_open")
        self.assertEqual(weekly.requests, [("2020-01-02", "SHFE.RB")])
        strategy, _, _ = self.strategy()
        self.observe(strategy, "2019-12-31", native="long_case1a")
        self.assertEqual(strategy.ts_decision_audit, [])
        self.assertEqual(strategy.ts_machine._products, {})

    def test_final_volume_is_frozen_once_and_reserved_only_at_product_snapshot(self):
        # Break caught: freezing before final cap, reserving in planner, duplicate
        # snapshot reserve, q0 consuming setup or close incorrectly labelled T.
        strategy, _, _ = self.strategy()
        candidate = self.observe(strategy)
        item = strategy.ts_pending_intents[0]
        self.assertEqual(item["plan"]["volume"], 10)
        self.assertEqual(item["plan"]["sizing"]["selected_volume"], 10)
        self.assertEqual(strategy.events, [("native_planner", 1),
            ("snapshot", PRODUCT, "conditional_pending"), ("reserve", PRODUCT, 10, True)])
        self.assertEqual(strategy.ts_decision_audit[-1]["b_ts_final_budget_volume_after"], 10)
        snapshot = strategy.entry_candidate_snapshots[-1]
        self.assertEqual((snapshot["signal_close"], snapshot["b_ts_trigger"],
            snapshot["planned_entry_price"], snapshot["stop_distance"]), (100., 111., 111., 12.))
        candidate.signal_data["nested"][0] = -1000
        strategy.last_plans[PRODUCT]["sizing"]["stop_price"] = -1000
        self.assertEqual(item["plan"]["signal_data"]["nested"], [7])
        self.assertEqual(item["plan"]["sizing"]["stop_price"], 99.)
        strategy, _, _ = self.strategy()
        strategy.risk_amount = 60.
        self.observe(strategy)
        self.assertEqual(strategy.ts_pending_intents, [])
        self.assertEqual(strategy.last_plans[PRODUCT]["candidate_status"], "filtered")
        self.assertEqual(strategy.last_plans[PRODUCT]["skip_reason"], "b_ts_final_budget_zero")
        self.assertFalse(any(event[0] == "reserve" for event in strategy.events))
        self.assertIsNotNone(strategy.ts_machine._products[PRODUCT].setup)

    def test_shared_activation_consumes_once_and_fill_audit_is_real_b(self):
        # Break caught: closure's C audit leaking into B, two on_fill calls, or
        # freeze accidentally replacing the real mutable account state.
        strategy, _, _ = self.strategy()
        self.observe(strategy)
        item = strategy.ts_pending_intents[0]
        strategy.ts_activate_intent(item, 130.)
        self.assertEqual(strategy.events[-1][6], "long_triple_screen")
        strategy.ts_commit_fill(item, "2020-01-03", "BACKTEST.1", dict(
            execution_datetime="2020-01-02T21:12:00", fill_price=130.,
            forecast_risk_amount=1200., actual_risk_amount=3100.,
            forecast_margin_amount=1110., actual_margin_amount=1300.))
        self.assertEqual(strategy.ts_fill_audit[-1]["arm"], "B_TS")
        self.assertEqual(strategy.ts_fill_audit[-1]["trigger"], 111.)
        self.assertEqual(strategy.ts_fill_audit[-1]["b_ts_final_budget_volume_after"], 10)
        self.assertIsNone(strategy.ts_machine._products[PRODUCT].setup)
        self.assertEqual(strategy._ts_conditional_entries[(PRODUCT, "2020-01-03")]["fill_price"], 130.)
        with self.assertRaises(ValueError):
            strategy.ts_commit_fill(item, "2020-01-03", "BACKTEST.1", {})


if __name__ == "__main__":
    unittest.main()
