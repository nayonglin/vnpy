#!/usr/bin/env python3
"""Focused tests for Stage013 guarded-quality authoritative sizing."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class Stage013GuardedQualityAuthoritativeSizingTest(unittest.TestCase):
    @staticmethod
    def _module():
        return importlib.import_module(
            "stage013_guarded_quality_authoritative_sizing_engine"
        )

    def test_guarded_quality_adds_floor_25pct_for_frozen_selector(self) -> None:
        module = self._module()

        selected, fields = module._guarded_quality_floor25(
            sizing={
                "selected_volume": 8,
                "ai_product_pool_rank": 8,
                "risk_multiplier": 1.5,
            },
            entry_context="flat_entry",
            enabled=True,
        )

        self.assertEqual(selected, 10)
        self.assertEqual(fields["stage013_quality_applied"], 1)
        self.assertEqual(fields["stage013_quality_added_volume"], 2)
        self.assertEqual(fields["stage013_quality_reason"], "guarded_quality_floor25")

    def test_guarded_quality_preserves_all_frozen_negative_cases(self) -> None:
        module = self._module()
        cases = [
            (
                {"selected_volume": 8, "ai_product_pool_rank": 9, "risk_multiplier": 1.0},
                "flat_entry",
                True,
                "ai_rank_outside_1_8",
            ),
            (
                {"selected_volume": 8, "ai_product_pool_rank": 3, "risk_multiplier": 2.0},
                "flat_entry",
                True,
                "risk_multiplier_not_below_2",
            ),
            (
                {"selected_volume": 3, "ai_product_pool_rank": 3, "risk_multiplier": 1.0},
                "flat_entry",
                True,
                "floor25_no_integer_increment",
            ),
            (
                {"selected_volume": 8, "ai_product_pool_rank": 3, "risk_multiplier": 1.0},
                "regular_add",
                True,
                "non_flat_entry_context",
            ),
            (
                {"selected_volume": 8, "ai_product_pool_rank": 3, "risk_multiplier": 1.0},
                "flat_entry",
                False,
                "disabled",
            ),
        ]

        for sizing, context, enabled, reason in cases:
            with self.subTest(reason=reason):
                selected, fields = module._guarded_quality_floor25(
                    sizing=sizing,
                    entry_context=context,
                    enabled=enabled,
                )
                self.assertEqual(selected, int(sizing["selected_volume"]))
                self.assertEqual(fields["stage013_quality_applied"], 0)
                self.assertEqual(fields["stage013_quality_reason"], reason)

    def test_guarded_quality_request_is_broker10_capped_before_incremental_gate(self) -> None:
        module = self._module()

        selected, fields = module._guarded_quality_before_final_risk_gates(
            sizing={
                "selected_volume": 8,
                "ai_product_pool_rank": 3,
                "risk_multiplier": 1.0,
                "stage830_broker10_margin_cap_enabled": 1,
                "stage830_margin_cap_max_affordable_volume": 9,
                "reserved_margin_before": 0.0,
                "margin_per_contract": 3_200.0,
                "sizing_equity": 50_000.0,
                "stage830_broker_margin_multiplier": 1.65,
                "stage830_margin_cap_ratio": 1.0,
            },
            entry_context="flat_entry",
            enabled=True,
        )

        self.assertEqual(fields["stage013_quality_requested_after"], 10)
        self.assertEqual(selected, 9)
        self.assertEqual(fields["stage013_quality_pre_incremental_gate_after"], 9)
        self.assertEqual(fields["stage013_quality_broker10_clamped"], 1)
        self.assertLessEqual(
            fields["stage013_quality_projected_broker10_after"],
            fields["stage013_quality_broker10_cap_ratio"],
        )

    def test_strategy_applies_quality_in_pre_incremental_volume_tilt_hook(self) -> None:
        module = self._module()
        strategy_class = (
            module.QmtRollPortfolioStrategyStage013GuardedQualityAuthoritativeSizing
        )
        parent_owner = next(
            owner
            for owner in strategy_class.__mro__[1:]
            if "_apply_selection_pairwise_volume_tilt" in owner.__dict__
        )
        strategy = object.__new__(strategy_class)
        strategy.enable_stage013_guarded_quality_authoritative_sizing = True
        strategy.stage830_projected_broker10_margin_to_equity_cap = 1.0
        plans = [
            {
                "candidate_status": "opened",
                "volume": 8,
                "sizing": {
                    "selected_volume": 8,
                    "ai_product_pool_rank": 3,
                    "risk_multiplier": 1.0,
                    "stage830_broker10_margin_cap_enabled": 1,
                    "stage830_margin_cap_max_affordable_volume": 9,
                    "reserved_margin_before": 0.0,
                    "margin_per_contract": 3_200.0,
                    "sizing_equity": 50_000.0,
                    "stage830_broker_margin_multiplier": 1.65,
                },
            }
        ]

        with patch.object(
            parent_owner,
            "_apply_selection_pairwise_volume_tilt",
            autospec=True,
            return_value=None,
        ) as parent:
            strategy._apply_selection_pairwise_volume_tilt(plans)

        parent.assert_called_once_with(strategy, plans)
        self.assertEqual(plans[0]["volume"], 9)
        self.assertEqual(plans[0]["sizing"]["selected_volume"], 9)
        self.assertEqual(
            plans[0]["sizing"]["stage013_quality_requested_after"], 10
        )
        self.assertEqual(
            plans[0]["sizing"]["stage013_quality_broker10_cap_ratio"], 1.0
        )

    def test_final_risk_gate_can_consume_quality_increment(self) -> None:
        module = self._module()
        _, request_fields = module._guarded_quality_before_final_risk_gates(
            sizing={
                "selected_volume": 8,
                "ai_product_pool_rank": 3,
                "risk_multiplier": 1.0,
                "stage830_broker10_margin_cap_enabled": 0,
            },
            entry_context="flat_entry",
            enabled=True,
        )

        blocked = module._finalize_guarded_quality_after_final_risk_gates(
            sizing={**request_fields, "selected_volume": 8},
            candidate_status="opened",
        )
        self.assertEqual(blocked["stage013_quality_applied"], 0)
        self.assertEqual(blocked["stage013_quality_selected_after"], 8)
        self.assertEqual(blocked["stage013_quality_added_volume"], 0)
        self.assertEqual(
            blocked["stage013_quality_reason"],
            "final_risk_gate_no_increment",
        )

        survived = module._finalize_guarded_quality_after_final_risk_gates(
            sizing={**request_fields, "selected_volume": 10},
            candidate_status="opened",
        )
        self.assertEqual(survived["stage013_quality_applied"], 1)
        self.assertEqual(survived["stage013_quality_selected_after"], 10)
        self.assertEqual(survived["stage013_quality_added_volume"], 2)

    def test_plan_finalization_does_not_apply_quality_twice(self) -> None:
        module = self._module()
        strategy_class = (
            module.QmtRollPortfolioStrategyStage013GuardedQualityAuthoritativeSizing
        )
        parent_owner = next(
            owner
            for owner in strategy_class.__mro__[1:]
            if "_plan_flat_entry_candidates" in owner.__dict__
        )
        _, request_fields = module._guarded_quality_before_final_risk_gates(
            sizing={
                "selected_volume": 8,
                "ai_product_pool_rank": 3,
                "risk_multiplier": 1.0,
                "stage830_broker10_margin_cap_enabled": 1,
                "stage830_margin_cap_max_affordable_volume": 9,
                "reserved_margin_before": 0.0,
                "margin_per_contract": 3_200.0,
                "sizing_equity": 50_000.0,
                "stage830_broker_margin_multiplier": 1.65,
                "stage830_margin_cap_ratio": 1.0,
            },
            entry_context="flat_entry",
            enabled=True,
        )
        plans = {
            "rb.SHFE": {
                "candidate_status": "opened",
                "volume": 9,
                "sizing": {
                    **request_fields,
                    "selected_volume": 9,
                    "ai_product_pool_rank": 3,
                    "ai_product_pool_signal_date": "2022-02-25",
                    "risk_multiplier": 1.0,
                },
                "target_contract": "rb9999.SHFE",
                "target_bar": SimpleNamespace(
                    datetime=pd.Timestamp("2022-03-01"),
                    close_price=4_000.0,
                ),
                "direction": "long",
                "signal": "entry",
            }
        }
        strategy = object.__new__(strategy_class)
        strategy.enable_stage013_guarded_quality_authoritative_sizing = True
        strategy.stage013_quality_event_count = 0
        strategy.stage013_quality_added_volume = 0
        strategy.trade_event_diagnostics = []

        with patch.object(
            parent_owner,
            "_plan_flat_entry_candidates",
            autospec=True,
            return_value=plans,
        ):
            result = strategy._plan_flat_entry_candidates([])

        self.assertEqual(result["rb.SHFE"]["volume"], 9)
        self.assertEqual(strategy.stage013_quality_event_count, 1)
        self.assertEqual(strategy.stage013_quality_added_volume, 1)
        event = strategy.trade_event_diagnostics[0]
        self.assertEqual(event["stage013_quality_selected_before"], 8)
        self.assertEqual(event["stage013_quality_selected_after"], 9)
        self.assertEqual(event["stage013_quality_added_volume"], 1)
        self.assertEqual(event["contract_vt_symbol"], "rb9999.SHFE")
        self.assertEqual(event["ai_product_pool_signal_date"], "2022-02-25")

    def test_quality_event_audit_fails_closed_on_formula_or_anchor_gap(self) -> None:
        module = self._module()
        clean = pd.DataFrame(
            {
                "requested_start_month": ["2020-01", "2021-01", "2022-01"],
                "stage013_quality_enabled": [1, 1, 1],
                "stage013_quality_applied": [1, 1, 1],
                "stage013_quality_selected_before": [8, 12, 4],
                "stage013_quality_requested_after": [10, 15, 5],
                "stage013_quality_pre_incremental_gate_after": [9, 15, 5],
                "stage013_quality_selected_after": [9, 15, 5],
                "stage013_quality_added_volume": [1, 3, 1],
                "stage013_quality_broker10_cap_enabled": [1, 1, 1],
                "stage013_quality_projected_broker10_after": [0.95, 0.90, 0.80],
                "stage013_quality_broker10_cap_ratio": [1.0, 1.0, 1.0],
                "stage013_quality_ai_rank": [1, 8, 4],
                "stage013_quality_risk_multiplier": [1.0, 1.5, 0.5],
                "entry_context": ["flat_entry"] * 3,
                "candidate_status_after": ["opened"] * 3,
            }
        )
        expected = {"2020-01", "2021-01", "2022-01"}

        self.assertTrue(module._quality_event_audit_pass(clean, expected_starts=expected))
        dirty = clean.copy()
        dirty.loc[1, "stage013_quality_requested_after"] = 16
        self.assertFalse(module._quality_event_audit_pass(dirty, expected_starts=expected))
        broker_breach = clean.copy()
        broker_breach.loc[0, "stage013_quality_projected_broker10_after"] = 1.01
        self.assertFalse(
            module._quality_event_audit_pass(
                broker_breach,
                expected_starts=expected,
            )
        )
        self.assertFalse(
            module._quality_event_audit_pass(
                clean[clean["requested_start_month"].ne("2022-01")],
                expected_starts=expected,
            )
        )

    def test_output_directory_is_inside_current_repository_line(self) -> None:
        module = self._module()

        self.assertEqual(
            module.OUT,
            TOOLS_DIR.parent / "outputs" / module.STAGE_ID,
        )

    def test_ai_future_signal_date_audit_fails_closed(self) -> None:
        module = self._module()
        candidates = pd.DataFrame(
            {
                "date": ["2022-03-01", "2022-03-02", "2022-03-03"],
                "ai_product_pool_signal_date": [
                    "2022-02-25",
                    "2022-03-02",
                    "2022-03-04",
                ],
            }
        )

        self.assertEqual(module._ai_future_signal_violation_count(candidates), 1)


if __name__ == "__main__":
    unittest.main()
