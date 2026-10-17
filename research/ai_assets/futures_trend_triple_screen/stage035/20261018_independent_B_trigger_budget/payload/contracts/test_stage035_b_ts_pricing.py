"""Finite B trigger-price and allocator-budget checks; no market replay."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.dont_write_bytecode = True
import stage022_run_c0_qualified_wait as prior

_RUNTIME = tempfile.TemporaryDirectory(prefix="stage035_pricing_test_")
prior.OUTPUT = Path(_RUNTIME.name) / "outputs"
prior.configure_runtime(Path(_RUNTIME.name) / "shared")

import pandas as pd
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as native

try:
    from stage035_b_ts_pricing import build_trigger_priced_base, finalize_b_plan_batch
except ImportError:
    build_trigger_priced_base = finalize_b_plan_batch = None

DAY, CONTRACT = "2026-01-06", "rb2605.SHFE"


def sizing_fixture(cls):
    """Neutral pre-existing layers isolate genuine qmt/830 arithmetic and stop MRO."""
    strategy = cls.__new__(cls)
    strategy.fixed_size = 0
    strategy.stop_loss_pct = .02
    strategy.source_symbol_by_contract = {CONTRACT: "rb.SHFE"}
    strategy.ts_trigger_by_key = {}
    strategy.base_capital = strategy.estimated_equity = 100000.
    strategy.max_position_size, strategy.min_position_size = 500, 1
    strategy.stage830_broker_margin_multiplier = 1.65
    strategy.stage830_projected_broker10_margin_to_equity_cap = 1.
    strategy.enable_stage830_broker10_margin_cap = True
    strategy.stage830_margin_cap_events = []
    strategy.stage830_margin_cap_reduce_count = strategy.stage830_margin_cap_block_count = 0
    strategy.trade_event_diagnostics = []
    strategy.get_size = lambda symbol: 10
    strategy.get_pricetick = lambda symbol: 1.
    strategy._entry_structure_recovery_fields = lambda **kwargs: {}
    strategy._current_streak_multiplier = lambda: 1.
    strategy._failure_memory_micro_sizing_fields = lambda **kwargs: {}
    strategy._oi_price_confirm_risk_restore_fields = lambda **kwargs: {}
    strategy._portfolio_overheat_cooldown_fields = lambda context: {"portfolio_overheat_cooldown_scale": 1.}
    strategy._directional_30d_risk_boost_snapshot = lambda *args: {"directional_30d_risk_boost_multiplier": 1.}
    strategy._long_signal_atr_shock_snapshot = lambda *args: {}
    strategy._long_signal_range_atr_snapshot = lambda *args: {}
    strategy._sizing_equity_snapshot = lambda: {"sizing_equity": 100000.}
    strategy._limited_available_balance = lambda context: 100000.
    strategy._allowed_capital = lambda context: 100000.
    strategy._single_trade_capital_limit = lambda: 100000.
    strategy._free_capital_after_reservations = lambda: 100000.
    strategy._reserved_margin_in_use = lambda: 0.
    strategy._risk_amount_from_ratio = lambda *args, **kwargs: 1200.
    strategy._margin_ratio_for_symbol = lambda symbol: .1
    strategy._risk_cluster_cap_fields = lambda symbol, volume, margin: {
        "risk_cluster_cap_enabled": 0, "risk_cluster_name": "steel",
        "risk_cluster_cap_amount": 0., "risk_cluster_reserved_margin_before": 0.,
        "risk_cluster_selected_volume": volume}
    strategy._apply_risk_cluster_heat_gate_to_volume = lambda symbol, volume, margin, context: {
        "risk_cluster_heat_gate_selected_volume": volume}
    strategy._apply_env_gate_to_volume = lambda volume, **kwargs: {"selected_volume": volume}
    strategy._effective_capital_usage_ratio = lambda context: 1.
    strategy._effective_max_concurrent_positions = lambda context: 10
    strategy._recovery_sleeve_fields = lambda *args: {}
    strategy._apply_long_signal_atr_shock_to_sizing = lambda sizing, *args, **kwargs: sizing
    strategy._apply_long_signal_range_atr_to_sizing = lambda sizing, *args, **kwargs: sizing
    return strategy


def make_plan(product="rb.SHFE", rank=1, volume=12, *, margin=111., risk=1200., cluster="steel"):
    sizing = dict(selected_volume=volume, risk_amount=risk, risk_per_contract=120.,
        margin_per_contract=margin, margin_ratio=margin / 1110., limited_balance=100000.,
        single_trade_capital_limit=100000., reserved_margin_before=0., stop_price=99.,
        contracts_by_risk=int(risk // 120.), contracts_by_margin=int(100000. // margin),
        contracts_by_single_trade_cap=int(100000. // margin), b_ts_budget_equity_u=100000.,
        b_ts_trigger_price=111., b_ts_signal_day=DAY, b_ts_contract_size=10,
        b_ts_pricetick=1., b_ts_min_position_size=1, b_ts_max_position_size=500,
        stage830_broker10_margin_cap_enabled=1, stage830_broker10_margin_cap_ratio=1.,
        stage830_broker_margin_multiplier=1.65, risk_cluster_cap_enabled=0,
        risk_cluster_name=cluster, risk_cluster_cap_amount=0., risk_cluster_reserved_margin_before=0.,
        stage830_margin_cap_selected_volume_after=10, selection_pairwise_volume_tilt_volume_before=10)
    return dict(product_vt_symbol=product, target_contract=CONTRACT, direction="long",
        signal="long_triple_screen", candidate_status="opened", skip_reason="", volume=volume,
        selection_pairwise_rank=rank, selection_pairwise_score=.75, sizing=sizing)


class TriggerPricingTests(unittest.TestCase):
    def factory(self):
        self.assertIsNotNone(build_trigger_priced_base, "trigger pricing is not implemented")
        return build_trigger_priced_base(native.QmtRollPortfolioStrategyStage847C9StopRetry)

    def test_real_mro_long_and_short_keep_original_stop_and_bar(self):
        cls = self.factory()
        names = [item.__name__ for item in cls.__mro__]
        wanted = ["QmtRollPortfolioStrategyStage847C9StopRetry", "QmtRollPortfolioStrategyStage830C2Broker10MarginCap",
            "QmtRollPortfolioStrategyStage827C2", "QmtRollPortfolioStrategyLongTighterInitialStop",
            "QmtRollPortfolioStrategyExactAm", "PricingQmt", "QmtRollPortfolioStrategy"]
        self.assertEqual([name for name in names if name in wanted], wanted)
        for direction, high, low, trigger, stop, risk in [("long", 110., 99., 111., 99., 120.),
                ("short", 101., 90., 89., 101., 120.)]:
            with self.subTest(direction=direction):
                strategy = sizing_fixture(cls)
                bar = SimpleNamespace(datetime=datetime.fromisoformat(DAY), close_price=100., high_price=high, low_price=low)
                history = pd.DataFrame({"high": [high], "low": [low]})
                before = deepcopy(bar.__dict__), history.copy(deep=True)
                strategy.ts_trigger_by_key[(DAY, CONTRACT, direction)] = trigger
                result = strategy._calculate_entry_sizing(CONTRACT, direction, bar, history,
                    {"signal": direction + "_triple_screen", "risk_mode": "regular"})
                self.assertEqual((result["stop_price"], result["risk_per_contract"], result["contracts_by_risk"]), (stop, risk, 10))
                self.assertEqual(result["margin_per_contract"], trigger)
                self.assertEqual(result["b_ts_budget_equity_u"], 100000.)
                self.assertEqual(bar.__dict__, before[0])
                pd.testing.assert_frame_equal(history, before[1])

    def test_missing_or_invalid_trigger_fails_closed_non_b_and_nonflat_use_original(self):
        with self.assertRaisesRegex(ValueError, "b_ts_native_base_unsupported"):
            build_trigger_priced_base(type("UnsupportedNativeBase", (), {}))
        strategy = sizing_fixture(self.factory())
        bar = SimpleNamespace(datetime=datetime.fromisoformat(DAY), close_price=100., high_price=110., low_price=99.)
        history = pd.DataFrame({"high": [110.], "low": [99.]})
        for trigger in [None, float("nan"), -1.]:
            strategy.ts_trigger_by_key = {} if trigger is None else {(DAY, CONTRACT, "long"): trigger}
            with self.assertRaisesRegex(ValueError, "b_ts_trigger_"):
                strategy._calculate_entry_sizing(CONTRACT, "long", bar, history, {"signal": "long_triple_screen"})
        result = strategy._calculate_entry_sizing(CONTRACT, "long", bar, history, {"signal": "long_case1a"})
        self.assertEqual((result["risk_per_contract"], result["margin_per_contract"]), (10., 100.))
        result = strategy._calculate_entry_sizing(CONTRACT, "long", bar, history,
            {"signal": "long_triple_screen"}, entry_context="add")
        self.assertEqual((result["risk_per_contract"], result["margin_per_contract"]), (10., 100.))

    def test_final_tilt_twelve_is_clamped_to_original_risk_ten_and_other_caps_eight(self):
        self.assertIsNotNone(finalize_b_plan_batch, "final B budget is not implemented")
        strategy = SimpleNamespace(min_position_size=1, max_position_size=500)
        for cap in ["risk", "single", "broker", "cluster"]:
            with self.subTest(cap=cap):
                plan = make_plan()
                if cap == "single":
                    plan["sizing"].update(single_trade_capital_limit=888., contracts_by_single_trade_cap=8)
                elif cap == "broker":
                    plan["sizing"]["reserved_margin_before"] = 100000. / 1.65 - 888.
                elif cap == "cluster":
                    plan["sizing"].update(risk_cluster_cap_enabled=1, risk_cluster_cap_amount=888.)
                audit = finalize_b_plan_batch(strategy, {"rb.SHFE": plan})
                self.assertEqual(plan["volume"], 10 if cap == "risk" else 8)
                self.assertEqual(plan["sizing"]["selected_volume"], plan["volume"])
                self.assertEqual(plan["sizing"]["stage830_margin_cap_selected_volume_after"], 10)
                self.assertEqual(plan["selection_pairwise_score"], .75)
                self.assertEqual(audit[0]["b_ts_final_budget_predicted_risk_T"], plan["volume"] * 120.)

    def test_gross_prefix_does_not_recycle_risk_reduction_or_promote_skipped(self):
        self.assertIsNotNone(finalize_b_plan_batch, "final B budget is not implemented")
        strategy = SimpleNamespace(min_position_size=1, max_position_size=500)
        plans = {name: make_plan(name, rank, 2, margin=15000., risk=120. if rank == 1 else 1200., cluster=name)
                 for rank, name in enumerate(["a.SHFE", "b.SHFE", "c.SHFE"], 1)}
        for plan in plans.values():
            plan["sizing"].update(risk_cluster_cap_enabled=1, risk_cluster_cap_amount=30000.)
        loser = make_plan("d.SHFE", 4, 2, margin=15000.)
        loser.update(candidate_status="skipped", skip_reason="concurrent_limit")
        plans["d.SHFE"] = loser
        untouched = deepcopy(loser)
        audit = finalize_b_plan_batch(strategy, plans)
        self.assertEqual([plan["volume"] for plan in plans.values()], [1, 2, 0, 2])
        self.assertEqual(plans["c.SHFE"]["candidate_status"], "filtered")
        self.assertEqual(plans["c.SHFE"]["skip_reason"], "b_ts_final_budget_zero")
        self.assertEqual(audit[2]["b_ts_final_budget_gross_margin_before"], 60000.)
        self.assertEqual(loser, untouched)

    def test_invalid_budget_or_price_contract_count_is_not_silently_clamped(self):
        self.assertIsNotNone(finalize_b_plan_batch, "final B budget is not implemented")
        for field, value in [("risk_amount", None), ("margin_per_contract", float("nan")),
                ("b_ts_budget_equity_u", 0.), ("contracts_by_risk", 11)]:
            with self.subTest(field=field):
                plan = make_plan()
                plan["sizing"][field] = value
                with self.assertRaisesRegex(ValueError, "b_ts_budget_"):
                    finalize_b_plan_batch(SimpleNamespace(min_position_size=1, max_position_size=500), [plan])


if __name__ == "__main__":
    unittest.main()
