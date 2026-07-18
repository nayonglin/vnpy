from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as stage659
import export_qmt_roll_stage372_official_shadow_events as pending_audit
from qmt_roll_official_execution_profile import STAGE372_20W_PROFILE
import run_qmt_roll_stage909_official_live_shadow_refresh_gate as stage909


class Stage372ShadowPrecomputeTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
