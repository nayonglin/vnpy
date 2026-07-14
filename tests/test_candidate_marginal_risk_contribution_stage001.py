from __future__ import annotations

import importlib
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_candidate_marginal_risk_contribution" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def module():
    return importlib.import_module("stage001_candidate_marginal_risk_contribution_engine")


class Stage001CandidateMRCTest(unittest.TestCase):
    def test_component_risk_is_additive_and_diagonal_does_not_shrink(self) -> None:
        m = module()
        covariance = np.diag([0.04, 0.09])
        rows, sigma = m.component_risk_contributions(covariance, np.array([2.0, 1.0]), ["a", "b"])
        self.assertAlmostEqual(float(rows["component_risk"].sum()), sigma)
        self.assertTrue(np.allclose(rows["component_risk"], rows["inherent_risk"]))
        self.assertTrue(rows["scale"].eq(1.0).all())

    def test_positive_correlation_shrinks_and_negative_direction_does_not(self) -> None:
        m = module()
        covariance = np.array([[0.04, 0.03], [0.03, 0.04]])
        same, _ = m.component_risk_contributions(covariance, np.array([1.0, 1.0]), ["a", "b"])
        opposite, _ = m.component_risk_contributions(covariance, np.array([1.0, -1.0]), ["a", "b"])
        self.assertTrue((same["scale"] < 1.0).all())
        self.assertTrue(opposite["scale"].eq(1.0).all())
        self.assertTrue((opposite["correlation_risk"] < 0.0).all())

    def test_component_risk_rejects_invalid_covariance(self) -> None:
        m = module()
        with self.assertRaisesRegex(ValueError, "symmetric"):
            m.component_risk_contributions(np.array([[1.0, 0.5], [0.0, 1.0]]), np.ones(2), ["a", "b"])
        with self.assertRaisesRegex(ValueError, "positive semidefinite"):
            m.component_risk_contributions(np.array([[1.0, 2.0], [2.0, 1.0]]), np.ones(2), ["a", "b"])
        with self.assertRaisesRegex(ValueError, "variance"):
            m.component_risk_contributions(np.eye(2), np.zeros(2), ["a", "b"])

    def test_integer_volume_only_reduces_and_preserves_one(self) -> None:
        m = module()
        self.assertEqual(m.reduced_integer_volume(10, 0.61), 6)
        self.assertEqual(m.reduced_integer_volume(2, 0.49), 1)
        self.assertEqual(m.reduced_integer_volume(1, 0.01), 1)
        self.assertEqual(m.reduced_integer_volume(0, 0.5), 0)
        with self.assertRaises(ValueError):
            m.reduced_integer_volume(2, 1.01)

    def test_t1_selector_requires_exact_common_history_and_excludes_cutoff(self) -> None:
        m = module()
        dates = pd.bdate_range("2020-01-01", periods=70)
        rows = []
        for date in dates:
            for contract, value in (("a.X", 0.01), ("b.X", -0.01)):
                rows.append(
                    {
                        "date": date,
                        "contract_vt_symbol": contract,
                        "contract_return": value,
                        "return_valid": 1,
                    }
                )
        panel = pd.DataFrame(rows)
        cutoff = dates[65]
        matrix, audit = m.select_t1_common_returns(panel, ["b.X", "a.X"], cutoff_date=cutoff)
        self.assertEqual(matrix.shape, (63, 2))
        self.assertLess(matrix.index.max(), cutoff)
        self.assertEqual(audit["available"], 1)
        self.assertEqual(audit["current_or_future_row_count"], 10)
        self.assertEqual(audit["eligible_current_or_future_rows_ignored"], 10)
        short, short_audit = m.select_t1_common_returns(panel, ["a.X", "b.X"], cutoff_date=dates[40])
        self.assertTrue(short.empty)
        self.assertEqual(short_audit["reason"], "insufficient_common_history")

    def test_t1_selector_rejects_duplicate_key_and_missing_contract(self) -> None:
        m = module()
        panel = pd.DataFrame(
            [
                {"date": "2020-01-01", "contract_vt_symbol": "a.X", "contract_return": 0.1, "return_valid": 1},
                {"date": "2020-01-01", "contract_vt_symbol": "a.X", "contract_return": 0.1, "return_valid": 1},
            ]
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            m.select_t1_common_returns(panel, ["a.X"], cutoff_date=pd.Timestamp("2021-01-01"))
        clean = panel.iloc[:1].copy()
        matrix, audit = m.select_t1_common_returns(clean, ["b.X"], cutoff_date=pd.Timestamp("2021-01-01"))
        self.assertTrue(matrix.empty)
        self.assertEqual(audit["reason"], "missing_contract")

    def test_stage462_aggregation_uses_last_day_session_bar_not_night(self) -> None:
        m = module()
        source = pd.DataFrame(
            {
                "vt_symbol": ["fu2005.SHFE"] * 4,
                "bar_datetime": [
                    "2020-01-02 14:58:00",
                    "2020-01-02 21:00:00",
                    "2020-01-03 14:57:00",
                    "2020-01-03 14:59:00",
                ],
                "close": [100.0, 999.0, 101.0, 102.0],
            }
        )
        daily = m.aggregate_stage462_day_closes(source, contract_vt_symbol="fu2005.SHFE")
        self.assertEqual(daily["close"].tolist(), [100.0, 102.0])
        self.assertTrue(daily["source"].eq("stage462_day_close").all())

    def test_contract_return_panel_marks_first_and_gap_invalid(self) -> None:
        m = module()
        dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
        frame = pd.DataFrame(
            {
                "date": [dates[0], dates[1], dates[2], dates[0], dates[2]],
                "contract_vt_symbol": ["a.X", "a.X", "a.X", "b.X", "b.X"],
                "close": [100.0, 101.0, 102.0, 200.0, 202.0],
                "source": ["sqlite_daily"] * 5,
            }
        )
        panel = m.build_contract_return_panel(frame)
        a = panel[panel["contract_vt_symbol"].eq("a.X")]
        b = panel[panel["contract_vt_symbol"].eq("b.X")]
        self.assertEqual(a["return_valid"].tolist(), [0, 1, 1])
        self.assertEqual(b["return_valid"].tolist(), [0, 0])
        self.assertEqual(b.iloc[-1]["invalid_reason"], "trading_date_gap")
        self.assertTrue(panel["source"].eq("sqlite_daily").all())

    def test_batch_adjustment_is_permutation_invariant_and_never_amplifies(self) -> None:
        m = module()
        rng = np.random.default_rng(7)
        base = rng.normal(size=63)
        returns = pd.DataFrame(
            {
                "a.X": base * 0.01,
                "b.X": base * 0.009 + rng.normal(scale=0.001, size=63),
                "c.X": -base * 0.008 + rng.normal(scale=0.001, size=63),
            }
        )
        exposures = pd.DataFrame(
            [
                {"role": "active", "contract_vt_symbol": "a.X", "cash_exposure": 100_000.0, "baseline_volume": 5},
                {"role": "candidate", "contract_vt_symbol": "b.X", "cash_exposure": 80_000.0, "baseline_volume": 8},
                {"role": "candidate", "contract_vt_symbol": "c.X", "cash_exposure": 60_000.0, "baseline_volume": 6},
            ]
        )
        first, first_audit = m.compute_batch_adjustments(exposures, returns)
        second, second_audit = m.compute_batch_adjustments(
            exposures.sample(frac=1.0, random_state=3).reset_index(drop=True),
            returns[["c.X", "a.X", "b.X"]],
        )
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(first_audit["matrix_sha256"], second_audit["matrix_sha256"])
        self.assertTrue((first["selected_volume_after"] <= first["baseline_volume"]).all())
        self.assertTrue((first["selected_volume_after"] > 0).all())

    def test_batch_rejects_candidate_already_active(self) -> None:
        m = module()
        returns = pd.DataFrame({"a.X": np.linspace(-0.01, 0.01, 63)})
        exposures = pd.DataFrame(
            [
                {"role": "active", "contract_vt_symbol": "a.X", "cash_exposure": 10.0, "baseline_volume": 1},
                {"role": "candidate", "contract_vt_symbol": "a.X", "cash_exposure": 10.0, "baseline_volume": 1},
            ]
        )
        with self.assertRaisesRegex(ValueError, "already active"):
            m.compute_batch_adjustments(exposures, returns)

    def test_default_fields_preserve_baseline_volume(self) -> None:
        m = module()
        fields = m._default_mrc_fields(before=3, reason="insufficient_common_history")
        self.assertEqual(fields["mrc_selected_volume_before"], 3)
        self.assertEqual(fields["mrc_selected_volume_after"], 3)
        self.assertEqual(fields["mrc_scale"], 1.0)
        self.assertEqual(fields["mrc_reason"], "insufficient_common_history")

    def test_post_planner_hook_reduces_final_opened_plan(self) -> None:
        m = module()
        strategy = m.QmtRollPortfolioStrategyCandidateMRC.__new__(m.QmtRollPortfolioStrategyCandidateMRC)
        strategy.enable_candidate_mrc = True
        strategy.candidate_mrc_lookback_days = 63
        strategy._candidate_mrc_panel_sha256 = "p" * 64
        strategy.candidate_mrc_batch_count = 0
        strategy.candidate_mrc_available_batch_count = 0
        strategy.candidate_mrc_unavailable_batch_count = 0
        strategy.candidate_mrc_reduced_count = 0
        cutoff = pd.Timestamp("2022-05-02")
        dates = pd.bdate_range(end=cutoff - pd.Timedelta(days=1), periods=70)
        common = np.linspace(-0.02, 0.02, len(dates))
        rows = []
        for date, value in zip(dates, common, strict=True):
            for contract, ret in (("a.X", value), ("b.X", value * 0.98)):
                rows.append(
                    {
                        "date": date,
                        "contract_vt_symbol": contract,
                        "contract_return": ret,
                        "return_valid": 1,
                    }
                )
        strategy._candidate_mrc_panel = pd.DataFrame(rows)
        active_state = SimpleNamespace(contract_vt_symbol="a.X")
        strategy.states = {"a": active_state}
        strategy.get_pos = lambda contract: 2 if contract == "a.X" else 0
        strategy.get_size = lambda contract: 10
        bar_a = SimpleNamespace(datetime=cutoff, close_price=100.0)
        bar_b = SimpleNamespace(datetime=cutoff, close_price=100.0)
        context = SimpleNamespace(
            current_pos=2,
            state=active_state,
            target_contract="a.X",
            actual_bar=bar_a,
            target_bar=bar_a,
        )
        base_plans = {
            "b": {
                "candidate_status": "opened",
                "target_contract": "b.X",
                "target_bar": bar_b,
                "direction": "long",
                "volume": 8,
                "sizing": {"selected_volume": 8},
            }
        }
        base_cls = m.s006.base.s847.QmtRollPortfolioStrategyStage847C9StopRetry
        with mock.patch.object(base_cls, "_plan_flat_entry_candidates", return_value=base_plans):
            result = strategy._plan_flat_entry_candidates([context])
        plan = result["b"]
        self.assertLess(plan["volume"], 8)
        self.assertEqual(plan["volume"], plan["sizing"]["selected_volume"])
        self.assertEqual(plan["sizing"]["mrc_available"], 1)
        self.assertEqual(strategy.candidate_mrc_available_batch_count, 1)

    def test_post_planner_hook_is_noop_when_history_is_short(self) -> None:
        m = module()
        strategy = m.QmtRollPortfolioStrategyCandidateMRC.__new__(m.QmtRollPortfolioStrategyCandidateMRC)
        strategy.enable_candidate_mrc = True
        strategy.candidate_mrc_lookback_days = 63
        strategy._candidate_mrc_panel_sha256 = "p" * 64
        strategy.candidate_mrc_batch_count = 0
        strategy.candidate_mrc_available_batch_count = 0
        strategy.candidate_mrc_unavailable_batch_count = 0
        strategy.candidate_mrc_reduced_count = 0
        cutoff = pd.Timestamp("2021-04-09")
        dates = pd.bdate_range(end=cutoff - pd.Timedelta(days=1), periods=58)
        strategy._candidate_mrc_panel = pd.DataFrame(
            {
                "date": dates,
                "contract_vt_symbol": "lh2109.DCE",
                "contract_return": np.linspace(-0.01, 0.01, len(dates)),
                "return_valid": 1,
            }
        )
        strategy.states = {}
        strategy.get_pos = lambda contract: 0
        strategy.get_size = lambda contract: 16
        bar = SimpleNamespace(datetime=cutoff, close_price=8_000.0)
        base_plans = {
            "lh": {
                "candidate_status": "opened",
                "target_contract": "lh2109.DCE",
                "target_bar": bar,
                "direction": "long",
                "volume": 1,
                "sizing": {"selected_volume": 1},
            }
        }
        base_cls = m.s006.base.s847.QmtRollPortfolioStrategyStage847C9StopRetry
        with mock.patch.object(base_cls, "_plan_flat_entry_candidates", return_value=base_plans):
            result = strategy._plan_flat_entry_candidates([])
        plan = result["lh"]
        self.assertEqual(plan["volume"], 1)
        self.assertEqual(plan["sizing"]["selected_volume"], 1)
        self.assertEqual(plan["sizing"]["mrc_available"], 0)
        self.assertEqual(plan["sizing"]["mrc_reason"], "insufficient_common_history")
        self.assertEqual(strategy.candidate_mrc_unavailable_batch_count, 1)

    def test_active_exposure_uses_negative_current_position_sign(self) -> None:
        m = module()
        strategy = m.QmtRollPortfolioStrategyCandidateMRC.__new__(m.QmtRollPortfolioStrategyCandidateMRC)
        cutoff = pd.Timestamp("2022-05-02")
        active_state = SimpleNamespace(contract_vt_symbol="a.X")
        strategy.states = {"a": active_state}
        strategy.get_pos = lambda contract: -2 if contract == "a.X" else 0
        strategy.get_size = lambda contract: 10
        bar = SimpleNamespace(datetime=cutoff, close_price=100.0)
        context = SimpleNamespace(
            current_pos=-2,
            state=active_state,
            target_contract="a.X",
            actual_bar=bar,
            target_bar=bar,
        )
        opened = [
            {
                "target_contract": "b.X",
                "target_bar": bar,
                "direction": "long",
                "volume": 3,
            }
        ]
        exposures = strategy._build_batch_exposures([context], opened, cutoff)
        active = exposures.loc[exposures["role"].eq("active")].iloc[0]
        self.assertEqual(active["cash_exposure"], -2_000.0)
        self.assertEqual(active["baseline_volume"], 2)

    def test_post_planner_hook_is_noop_on_covariance_failure(self) -> None:
        m = module()
        strategy = m.QmtRollPortfolioStrategyCandidateMRC.__new__(m.QmtRollPortfolioStrategyCandidateMRC)
        strategy.enable_candidate_mrc = True
        strategy.candidate_mrc_lookback_days = 63
        strategy._candidate_mrc_panel_sha256 = "p" * 64
        strategy.candidate_mrc_batch_count = 0
        strategy.candidate_mrc_available_batch_count = 0
        strategy.candidate_mrc_unavailable_batch_count = 0
        strategy.candidate_mrc_reduced_count = 0
        cutoff = pd.Timestamp("2022-05-02")
        dates = pd.bdate_range(end=cutoff - pd.Timedelta(days=1), periods=63)
        strategy._candidate_mrc_panel = pd.DataFrame(
            {
                "date": dates,
                "contract_vt_symbol": "a.X",
                "contract_return": 0.0,
                "return_valid": 1,
            }
        )
        strategy.states = {}
        strategy.get_pos = lambda contract: 0
        strategy.get_size = lambda contract: 10
        bar = SimpleNamespace(datetime=cutoff, close_price=100.0)
        base_plans = {
            "a": {
                "candidate_status": "opened",
                "target_contract": "a.X",
                "target_bar": bar,
                "direction": "long",
                "volume": 4,
                "sizing": {"selected_volume": 4},
            }
        }
        base_cls = m.s006.base.s847.QmtRollPortfolioStrategyStage847C9StopRetry
        with (
            mock.patch.object(base_cls, "_plan_flat_entry_candidates", return_value=base_plans),
        ):
            result = strategy._plan_flat_entry_candidates([])
        plan = result["a"]
        self.assertEqual(plan["volume"], 4)
        self.assertEqual(plan["sizing"]["selected_volume"], 4)
        self.assertEqual(plan["sizing"]["mrc_available"], 0)
        self.assertTrue(plan["sizing"]["mrc_reason"].startswith("risk_compute_error:ValueError"))
        self.assertEqual(strategy.candidate_mrc_unavailable_batch_count, 1)

    def test_baseline_readiness_reconstructs_positions_before_batch(self) -> None:
        m = module()
        dates = pd.bdate_range("2020-01-01", periods=70)
        rows = []
        for date in dates:
            for contract in ("a.X", "b.X"):
                rows.append(
                    {
                        "date": date,
                        "contract_vt_symbol": contract,
                        "contract_return": 0.01,
                        "return_valid": 1,
                    }
                )
        candidates = pd.DataFrame(
            [
                {
                    "datetime": "2020-04-07 00:00:00+08:00",
                    "candidate_status": "opened",
                    "contract_vt_symbol": "b.X",
                    "selected_volume": 2,
                }
            ]
        )
        trades = pd.DataFrame(
            [
                {
                    "datetime": "2020-04-06 00:00:00+08:00",
                    "vt_symbol": "a.X",
                    "signed_volume": 1,
                }
            ]
        )
        audit = m.audit_baseline_batch_readiness(pd.DataFrame(rows), candidates, trades)
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit.iloc[0]["active_contracts"], "a.X")
        self.assertEqual(audit.iloc[0]["candidate_contracts"], "b.X")
        self.assertEqual(audit.iloc[0]["available"], 1)

    def test_golden_reproduction_audit_passes_exact_control(self) -> None:
        m = module()
        rows = []
        for start, values in m.GOLDEN_A.items():
            rows.append({"requested_start_month": start, "version": m.A_VERSION, **values})
        audit = m.golden_reproduction_audit(pd.DataFrame(rows))
        self.assertEqual(len(audit), 32)
        self.assertTrue(audit["pass"].eq(1).all())

    def _valid_canary_inputs(self, m):
        rows = []
        for start in m.CANARY_STARTS:
            a = {
                "requested_start_month": start,
                "version": m.A_VERSION,
                "total_return_pct": 100.0,
                "max_drawdown_pct": -40.0 if start != "2026-01" else -10.0,
                "longest_underwater_days": 200,
                "max_broker10_margin_to_equity_pct": 80.0,
                "bankrupt_count": 0,
                "account_identity_max_error": 0.0,
                "pending_order_count": 0,
                "pending_order_invalid_count": 0,
                "pending_order_duplicate_count": 0,
                "position_duplicate_key_count": 0,
                "trade_duplicate_id_count": 0,
                "position_continuity_max_error": 0.0,
                "position_row_identity_max_error": 0.0,
                "daily_position_change_reconciliation_max_error": 0.0,
                "terminal_position_reconciliation_max_error": 0.0,
                "margin_identity_max_error": 0.0,
                "position_margin_recalculation_max_error": 0.0,
                "broker10_ratio_identity_max_error": 0.0,
                "broker10_multiplier_max_error": 0.0,
            }
            c = dict(a)
            c.update(
                {
                    "version": m.C_VERSION,
                    "total_return_pct": 80.0,
                    "max_drawdown_pct": -35.0 if start != "2026-01" else -10.5,
                    "longest_underwater_days": 190,
                    "max_broker10_margin_to_equity_pct": 79.0,
                }
            )
            rows.extend([a, c])
        runtime = pd.DataFrame(
            [
                {
                    "requested_start_month": start,
                    "runtime_evidence_missing_count": 0,
                    "runtime_schema_error_count": 0,
                    "opened_rows": 3,
                    "batch_count": 2,
                    "available_batch_count": 2,
                    "unavailable_batch_count": 0,
                    "batch_id_missing_count": 0,
                    "batch_partition_mismatch_count": 0,
                    "mrc_available_invalid_count": 0,
                    "after_gt_before_count": 0,
                    "zeroed_count": 0,
                    "final_selected_mismatch_count": 0,
                    "available_non63_count": 0,
                    "t1_violation_count": 0,
                    "panel_sha_mismatch_count": 0,
                }
                for start in m.CANARY_STARTS
            ]
        )
        golden_count = sum(len(values) for values in m.GOLDEN_A.values())
        return rows, runtime, pd.DataFrame({"pass": [1] * golden_count})

    def test_canary_decision_uses_each_anchor_not_aggregate(self) -> None:
        m = module()
        rows, runtime, golden = self._valid_canary_inputs(m)
        passed = m.evaluate_canary(pd.DataFrame(rows), runtime, golden, source_pass=True)
        self.assertTrue(passed["canary_pass"])
        rows[-1]["total_return_pct"] = 69.0
        failed = m.evaluate_canary(pd.DataFrame(rows), runtime, golden, source_pass=True)
        self.assertFalse(failed["canary_pass"])
        self.assertIn("return_retention_below_70:2026-01", failed["failed_checks"])

    def test_canary_decision_fails_closed_on_pending_terminal_and_nonfinite_broker(self) -> None:
        m = module()
        rows, runtime, golden = self._valid_canary_inputs(m)
        rows[0]["pending_order_count"] = 2
        pending = m.evaluate_canary(pd.DataFrame(rows), runtime, golden, source_pass=True)
        self.assertFalse(pending["canary_pass"])
        self.assertIn("pending_orders_not_closed", pending["failed_checks"])

        rows, runtime, golden = self._valid_canary_inputs(m)
        rows[1]["terminal_position_reconciliation_max_error"] = 999.0
        terminal = m.evaluate_canary(pd.DataFrame(rows), runtime, golden, source_pass=True)
        self.assertFalse(terminal["canary_pass"])
        self.assertIn("terminal_position_reconciliation_failed", terminal["failed_checks"])

        rows, runtime, golden = self._valid_canary_inputs(m)
        rows[1]["max_broker10_margin_to_equity_pct"] = math.nan
        nonfinite = m.evaluate_canary(pd.DataFrame(rows), runtime, golden, source_pass=True)
        self.assertFalse(nonfinite["canary_pass"])
        self.assertIn("summary_nonfinite", nonfinite["failed_checks"])

    def test_canary_decision_fails_closed_on_missing_schema(self) -> None:
        m = module()
        rows, runtime, golden = self._valid_canary_inputs(m)
        summary = pd.DataFrame(rows).drop(columns=["margin_identity_max_error"])
        decision = m.evaluate_canary(summary, runtime, golden, source_pass=True)
        self.assertFalse(decision["canary_pass"])
        self.assertIn("summary_schema_missing", decision["failed_checks"])

        rows, runtime, golden = self._valid_canary_inputs(m)
        runtime_missing = runtime.drop(columns=["opened_rows"])
        decision = m.evaluate_canary(pd.DataFrame(rows), runtime_missing, golden, source_pass=True)
        self.assertFalse(decision["canary_pass"])
        self.assertIn("runtime_schema_missing", decision["failed_checks"])

        rows, runtime, golden = self._valid_canary_inputs(m)
        runtime_duplicate = pd.concat([runtime, runtime.iloc[[0]]], ignore_index=True)
        decision = m.evaluate_canary(pd.DataFrame(rows), runtime_duplicate, golden, source_pass=True)
        self.assertFalse(decision["canary_pass"])
        self.assertIn("runtime_anchor_coverage_failed", decision["failed_checks"])

        rows, runtime, golden = self._valid_canary_inputs(m)
        summary_missing = pd.DataFrame(rows[:-1])
        decision = m.evaluate_canary(summary_missing, runtime, golden, source_pass=True)
        self.assertFalse(decision["canary_pass"])
        self.assertIn("summary_arm_coverage_failed", decision["failed_checks"])

        rows, runtime, golden = self._valid_canary_inputs(m)
        summary = pd.DataFrame(rows)
        summary_duplicate = pd.concat([summary, summary.iloc[[0]]], ignore_index=True)
        decision = m.evaluate_canary(summary_duplicate, runtime, golden, source_pass=True)
        self.assertFalse(decision["canary_pass"])
        self.assertIn("summary_arm_coverage_failed", decision["failed_checks"])

    def test_canary_decision_rejects_empty_runtime_evidence(self) -> None:
        m = module()
        rows, runtime, golden = self._valid_canary_inputs(m)
        runtime.loc[0, "runtime_evidence_missing_count"] = 1
        runtime.loc[0, "opened_rows"] = 0
        runtime.loc[0, "batch_count"] = 0
        decision = m.evaluate_canary(pd.DataFrame(rows), runtime, golden, source_pass=True)
        self.assertFalse(decision["canary_pass"])
        self.assertIn("mrc_runtime_evidence_missing", decision["failed_checks"])

    def test_runtime_mrc_audit_marks_empty_and_missing_schema_as_invalid(self) -> None:
        m = module()
        empty = m.runtime_mrc_audit(pd.DataFrame(), start_month="2022-01")
        self.assertEqual(empty["runtime_evidence_missing_count"], 1)
        self.assertEqual(empty["runtime_schema_error_count"], 0)
        missing = m.runtime_mrc_audit(pd.DataFrame({"candidate_status": ["opened"]}), start_month="2022-01")
        self.assertEqual(missing["runtime_schema_error_count"], 1)

    def test_runtime_mrc_audit_requires_real_opened_batch_evidence(self) -> None:
        m = module()
        candidates = pd.DataFrame(
            {
                "candidate_status": ["opened"],
                "datetime": ["2022-01-03 00:00:00+08:00"],
                "selected_volume": [2],
                "mrc_available": [1],
                "mrc_batch_id": ["2022-01-03|a.X"],
                "mrc_panel_sha256": [m.sha256_file(m.PANEL_PATH)],
                "mrc_observation_count": [63],
                "mrc_observation_end": ["2021-12-31"],
                "mrc_selected_volume_before": [2],
                "mrc_selected_volume_after": [2],
                "mrc_volume_reduced": [0],
                "mrc_scale": [1.0],
            }
        )
        audit = m.runtime_mrc_audit(candidates, start_month="2022-01")
        self.assertEqual(audit["runtime_evidence_missing_count"], 0)
        self.assertEqual(audit["runtime_schema_error_count"], 0)
        self.assertEqual(audit["opened_rows"], 1)
        self.assertEqual(audit["batch_count"], 1)
        self.assertEqual(audit["available_batch_count"], 1)
        self.assertEqual(audit["batch_partition_mismatch_count"], 0)

    def test_arm_integrity_audit_reconciles_positions_trades_and_margin(self) -> None:
        m = module()
        daily = pd.DataFrame(
            {
                "date": pd.to_datetime(["2022-01-03", "2022-01-04"]),
                "account_equity": [100_010.0, 100_020.0],
                "c3_margin_exact": [200.0, 100.0],
                "total_margin_exact": [200.0, 100.0],
                "broker10_total_margin_exact": [220.0, 110.0],
                "broker10_margin_to_equity_pct": [220.0 / 100_010.0 * 100.0, 110.0 / 100_020.0 * 100.0],
            }
        )
        positions = pd.DataFrame(
            {
                "date": pd.to_datetime(["2022-01-03", "2022-01-04"]),
                "vt_symbol": ["a.X", "a.X"],
                "start_pos": [0.0, 2.0],
                "end_pos": [2.0, 1.0],
                "pos_change": [2.0, -1.0],
                "close_price": [100.0, 100.0],
            }
        )
        trades = pd.DataFrame(
            {
                "trade_id": ["t1", "t2"],
                "date": pd.to_datetime(["2022-01-03", "2022-01-04"]),
                "vt_symbol": ["a.X", "a.X"],
                "signed_volume": [2.0, -1.0],
            }
        )
        metadata = {"sizes": {"a.X": 10.0}, "margin_ratios": {"a.X": 0.1}}
        audit = m.arm_integrity_audit(
            daily,
            {"positions": positions, "trades": trades, "pending_orders": pd.DataFrame()},
            metadata,
        )
        for key in (
            "position_continuity_max_error",
            "position_row_identity_max_error",
            "daily_position_change_reconciliation_max_error",
            "terminal_position_reconciliation_max_error",
            "margin_identity_max_error",
            "position_margin_recalculation_max_error",
            "broker10_ratio_identity_max_error",
            "broker10_multiplier_max_error",
        ):
            self.assertAlmostEqual(audit[key], 0.0, places=10)
        self.assertEqual(audit["pending_order_count"], 0)

        bad_positions = positions.copy()
        bad_positions.loc[1, "start_pos"] = 99.0
        bad = m.arm_integrity_audit(
            daily,
            {"positions": bad_positions, "trades": trades, "pending_orders": pd.DataFrame()},
            metadata,
        )
        self.assertGreater(bad["position_continuity_max_error"], 0.0)

        bad_identity = positions.copy()
        bad_identity.loc[0, "pos_change"] = -2.0
        identity = m.arm_integrity_audit(
            daily,
            {"positions": bad_identity, "trades": trades, "pending_orders": pd.DataFrame()},
            metadata,
        )
        self.assertEqual(identity["position_row_identity_max_error"], 4.0)

        bad_margin = daily.copy()
        bad_margin.loc[0, "c3_margin_exact"] = 999.0
        margin = m.arm_integrity_audit(
            bad_margin,
            {"positions": positions, "trades": trades, "pending_orders": pd.DataFrame()},
            metadata,
        )
        self.assertGreater(margin["position_margin_recalculation_max_error"], 0.0)

        bad_multiplier = daily.copy()
        bad_multiplier.loc[0, "broker10_total_margin_exact"] = 999.0
        bad_multiplier.loc[0, "broker10_margin_to_equity_pct"] = 999.0 / 100_010.0 * 100.0
        multiplier = m.arm_integrity_audit(
            bad_multiplier,
            {"positions": positions, "trades": trades, "pending_orders": pd.DataFrame()},
            metadata,
        )
        self.assertGreater(multiplier["broker10_multiplier_max_error"], 0.0)

    def test_review_manifest_freezes_manifest_and_source_bytes(self) -> None:
        m = module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.py"
            source.write_text("value = 1\n", encoding="utf-8")
            snapshot = m.file_snapshot(source)
            manifest = root / "review_manifest.csv"
            pd.DataFrame([snapshot])[["path", "size", "sha256"]].to_csv(manifest, index=False)
            manifest_sha = m.sha256_file(manifest)
            audit = m.validate_review_manifest(
                manifest,
                expected_manifest_sha256=manifest_sha,
                required_paths=[source],
            )
            self.assertTrue(audit[["size_match", "sha256_match"]].eq(1).all().all())
            with self.assertRaisesRegex(RuntimeError, "manifest SHA"):
                m.validate_review_manifest(
                    manifest,
                    expected_manifest_sha256="0" * 64,
                    required_paths=[source],
                )
            source.write_text("value = 2\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "reviewed source drift"):
                m.validate_review_manifest(
                    manifest,
                    expected_manifest_sha256=manifest_sha,
                    required_paths=[source],
                )

    def test_empty_gzip_output_remains_readable(self) -> None:
        m = module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.csv.gz"
            m.write_gzip_frame(pd.DataFrame(), path)
            loaded = pd.read_csv(path)
            self.assertEqual(loaded.columns.tolist(), ["_empty"])
            self.assertTrue(loaded.empty)


if __name__ == "__main__":
    unittest.main()
