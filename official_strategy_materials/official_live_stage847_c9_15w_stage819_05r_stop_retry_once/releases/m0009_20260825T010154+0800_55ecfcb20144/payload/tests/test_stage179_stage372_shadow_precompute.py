from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd


os.environ.setdefault("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR", "1")
PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as stage659
import export_qmt_roll_stage372_official_shadow_events as pending_audit
from qmt_roll_official_execution_profile import STAGE372_20W_PROFILE
from qmt_roll_official_pending_artifact import (
    artifact_hashes_for_profile,
    validate_pending_artifact_cohort,
)
import run_qmt_roll_stage902_official_live_phase_d_readiness_gate as stage902
import run_qmt_roll_stage909_official_live_shadow_refresh_gate as stage909


class Stage372ShadowPrecomputeTest(unittest.TestCase):
    def test_stage909_latest_completed_refresh_advances_before_authoritative_verify(
        self,
    ) -> None:
        candidate, evidence = stage909._resolve_postclose_refresh_candidate(
            stage909.datetime.fromisoformat("2026-07-23T16:35:00"),
            "16:30",
        )
        self.assertEqual("2026-07-23", candidate)
        self.assertEqual(
            "postclose_refresh_candidate_not_execution_authority",
            evidence["target_kind"],
        )
        specs = stage909._command_specs(
            candidate,
            "2026-07-01",
            candidate,
            "2026-07-23",
            stage909.resolve_execution_profile("c9-15w"),
        )
        rows = [
            {"name": name, "exit_code": 0}
            for name, _command in specs
        ]
        with (
            patch.object(stage909, "_run_command", side_effect=rows) as run,
            patch.object(
                stage909,
                "_resolve_latest_completed",
                return_value=(
                    "2026-07-23",
                    {
                        "trading_calendar_source": (
                            "main_contract_mapping_trading_calendar"
                        )
                    },
                ),
            ),
        ):
            commands, post_update = stage909._run_refresh_pipeline(
                specs=specs,
                log_path=Path("unused.log"),
                target_date_mode="latest-completed",
                refresh_candidate_date=candidate,
                data_ready_time="16:30",
                as_of_after_update=stage909.datetime.fromisoformat(
                    "2026-07-23T16:36:00"
                ),
            )

        self.assertEqual(["stage173_data_update", "official_live_shadow"], [row["name"] for row in commands])
        self.assertEqual(2, run.call_count)
        stage173_command = run.call_args_list[0].args[1]
        shadow_command = run.call_args_list[1].args[1]
        self.assertEqual("2026-07-23", stage173_command[stage173_command.index("--end") + 1])
        self.assertEqual("2026-07-23", shadow_command[shadow_command.index("--target-date") + 1])
        self.assertEqual(
            "main_contract_mapping_trading_calendar",
            post_update["trading_calendar_source"],
        )

    def test_stage909_stale_post_update_mapping_stops_before_shadow(self) -> None:
        specs = stage909._command_specs(
            "2026-07-23",
            "2026-07-01",
            "2026-07-23",
            "2026-07-23",
            stage909.resolve_execution_profile("c9-15w"),
        )
        with (
            patch.object(
                stage909,
                "_run_command",
                return_value={"name": "stage173_data_update", "exit_code": 0},
            ) as run,
            patch.object(
                stage909,
                "_resolve_latest_completed",
                return_value=(
                    "2026-07-22",
                    {
                        "trading_calendar_source": (
                            "main_contract_mapping_trading_calendar"
                        )
                    },
                ),
            ),
        ):
            commands, _post_update = stage909._run_refresh_pipeline(
                specs=specs,
                log_path=Path("unused.log"),
                target_date_mode="latest-completed",
                refresh_candidate_date="2026-07-23",
                data_ready_time="16:30",
            )

        self.assertEqual(1, run.call_count)
        self.assertEqual(
            ["stage173_data_update", "post_update_authoritative_target_verification"],
            [row["name"] for row in commands],
        )
        self.assertEqual(2, commands[-1]["exit_code"])

    def test_stage659_explicit_stage372_profile_ignores_c9_global_default(self) -> None:
        identity = stage659._configure_execution_profile("stage372-20w")

        self.assertEqual(identity["execution_profile"], "stage372-20w")
        self.assertEqual(
            identity["official_live_version"],
            "official_live_stage372_20w_recovery_sleeve",
        )
        self.assertEqual(identity["capital"], 200_000.0)
        self.assertEqual(identity["capital_label"], "20w")
        self.assertIn("stage659_stage372", identity["output_prefix"])
        self.assertIn("stage659_stage372", stage659.DECISION_PATH.name)

    def test_pending_audit_exports_active_engine_orders(self) -> None:
        order = SimpleNamespace(
            orderid="42",
            vt_symbol="jm2609.DCE",
            direction=SimpleNamespace(value="short"),
            offset=SimpleNamespace(value="close"),
            price=1360.0,
            volume=2,
            traded=0,
            datetime="2026-07-17 15:00:00",
            status=SimpleNamespace(value="submitting"),
        )
        engine = SimpleNamespace(active_limit_orders={"BACKTEST.42": order})

        rows = pending_audit._pending_order_rows(engine)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vt_symbol"], "jm2609.DCE")
        self.assertEqual(rows[0]["direction"], "short")
        self.assertEqual(rows[0]["offset"], "close")
        self.assertEqual(rows[0]["volume"], 2)

    def test_pending_output_uses_stage372_canonical_artifact_name(self) -> None:
        paths = pending_audit._output_paths("2026-07-17")

        self.assertIn("stage659_stage372", paths["pending_orders"].name)
        self.assertIn("pending_orders", paths["pending_orders"].name)

    def test_stage909_precomputes_pending_orders_before_execution(self) -> None:
        specs = stage909._command_specs(
            "2026-07-17",
            "2026-07-01",
            "2026-07-17",
            "2026-01-01",
            STAGE372_20W_PROFILE,
        )

        self.assertEqual(
            [name for name, _command in specs],
            [
                "stage173_data_update",
                "official_live_shadow",
                "stage372_pending_order_audit",
            ],
        )
        shadow_command = specs[1][1]
        self.assertEqual(
            Path(shadow_command[0]).resolve(),
            Path(sys.executable).resolve(),
        )
        self.assertEqual(
            shadow_command[shadow_command.index("--execution-profile") + 1],
            "stage372-20w",
        )

    def test_pending_cohort_binds_all_execution_inputs_and_publishes_audit_last(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            profile = replace(
                STAGE372_20W_PROFILE,
                summary_path=root / "summary.json",
                signal_plan_path=root / "signal.csv",
                current_positions_path=root / "positions.csv",
                pending_orders_path=root / "pending.csv",
                pending_orders_audit_path=root / "pending-audit.json",
            )
            profile.summary_path.write_text(
                json.dumps(
                    {
                        "analysis_end": "2026-07-17",
                        "execution_profile": profile.profile_key,
                        "official_live_version": profile.official_version,
                        "capital": profile.capital,
                        "capital_label": profile.capital_label,
                    }
                ),
                encoding="utf-8",
            )
            pd.DataFrame([{"vt_symbol": "jm2609.DCE"}]).to_csv(
                profile.signal_plan_path,
                index=False,
            )
            pd.DataFrame(columns=["vt_symbol", "direction", "end_pos"]).to_csv(
                profile.current_positions_path,
                index=False,
            )
            pending, audit = pending_audit._publish_pending_cohort(
                profile=profile,
                target_date="2026-07-17",
                pending_orders=pd.DataFrame(
                    [
                        {
                            "vt_orderid": "BACKTEST.42",
                            "orderid": "42",
                            "vt_symbol": "jm2609.DCE",
                            "direction": "short",
                            "offset": "close",
                            "price": 1360.0,
                            "volume": 2,
                            "traded": 0,
                            "datetime": "2026-07-17 15:00:00",
                            "status": "submitting",
                        }
                    ]
                ),
                generated_at="2026-07-17 16:35:00",
                pending_orders_path=profile.pending_orders_path,
                audit_path=profile.pending_orders_audit_path,
            )

            validated = validate_pending_artifact_cohort(
                profile,
                target_date="2026-07-17",
                pending_orders=pd.read_csv(profile.pending_orders_path),
                audit=json.loads(profile.pending_orders_audit_path.read_text()),
                artifact_hashes=artifact_hashes_for_profile(profile),
            )
            self.assertEqual(validated["cohort_id"], audit["cohort_id"])
            self.assertEqual(pending.iloc[0]["target_date"], "2026-07-17")
            self.assertEqual(
                pending.iloc[0]["execution_profile"],
                "stage372-20w",
            )
            self.assertFalse(list(root.glob(".*.tmp")))

    def test_stage902_rejects_stage260_summary_from_another_cohort(self) -> None:
        error = stage902._stage260_binding_error(
            {
                "execution_profile": STAGE372_20W_PROFILE.profile_key,
                "official_live_version": STAGE372_20W_PROFILE.official_version,
                "capital": STAGE372_20W_PROFILE.capital,
                "capital_label": STAGE372_20W_PROFILE.capital_label,
                "trade_date": "2026-07-17",
                "pending_cohort_id": "d" * 64,
                "order_api_called_count": 0,
            },
            profile=STAGE372_20W_PROFILE,
            target_date="2026-07-17",
            pending_cohort_id="c" * 64,
        )

        self.assertEqual(error, "stage260_pending_cohort_mismatch")


if __name__ == "__main__":
    unittest.main()
