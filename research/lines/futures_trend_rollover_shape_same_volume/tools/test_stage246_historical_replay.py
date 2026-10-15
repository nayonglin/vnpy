"""研究适配器的历史 AI 边界与分钟覆盖回归。"""

from __future__ import annotations

import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[4]
PROJECT = ROOT / "examples/portfolio_backtesting"
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stage246_historical_replay import audit_historical_ai_pool, opening_minute_coverage  # noqa: E402


MATERIAL = ROOT / (
    "official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases/"
    "m0008_20261008T204054+0800_2a7420a9f955/payload/ai/stage182/combined_eligibility.csv"
)
REQUIRED = ["2019-12-31", "2020-01-31", "2021-12-31", "2022-01-28", "2022-02-28"]


class HistoricalPoolAuditTests(unittest.TestCase):
    def test_static_boundary_is_valid_until_first_oos_month(self) -> None:
        result = audit_historical_ai_pool(MATERIAL, REQUIRED)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["first_oos_eval_date"], "2022-01-28")
        self.assertEqual(result["validated_snapshot_count"], 58)
        self.assertEqual(result["pre_ai_required_dates"], REQUIRED[:3])

    def test_missing_trading_calendar_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "trading_calendar_unavailable"):
            audit_historical_ai_pool(MATERIAL, [])

    def test_original_live_gate_rejects_legal_static_boundary(self) -> None:
        mapping = Path("/Users/mac/.codex/worktrees/formal-2020-replay/fian/examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv")
        if not mapping.exists():
            self.skipTest("restored trading calendar unavailable")
        code = (
            "import pandas as pd; "
            "import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s; "
            "from pathlib import Path; "
            f"s.ALL_FUTURES_MAPPING_PATH=Path({str(mapping)!r}); "
            f"audit=s._ai_pool_audit(Path({str(MATERIAL)!r}), "
            "pd.Timestamp('2020-01-01'),pd.Timestamp('2022-03-31')); "
            "s._assert_ai_pool_contract_valid(audit)"
        )
        env = os.environ.copy()
        bundle = Path("/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014")
        env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(bundle / "vendor"), str(PROJECT)])
        env["QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR"] = "1"
        env["MPLCONFIGDIR"] = "/private/tmp"
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            (Path(temporary) / ".vntrader").mkdir()
            result = subprocess.run([sys.executable, "-c", code], cwd=temporary, env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("official_ai_pool_contract_invalid", result.stderr)
        self.assertIn("2020-01-23", result.stderr)

    def test_missing_post_oos_month_fails(self) -> None:
        with self._edited_material(lambda rows: [r for r in rows if r["eval_date"] != "2022-02-28"]) as path:
            with self.assertRaisesRegex(ValueError, "missing_required_eval_date:2022-02-28"):
                audit_historical_ai_pool(path, REQUIRED)

    def test_fixed_fu_rank_tamper_fails_even_outside_requested_dates(self) -> None:
        def tamper(rows: list[dict[str, str]]) -> list[dict[str, str]]:
            for row in rows:
                if row["eval_date"] == "2025-05-30" and row["product_vt_symbol"] == "fu.SHFE":
                    row["score_rank"] = "10"
                    break
            return rows

        with self._edited_material(tamper) as path:
            with self.assertRaisesRegex(ValueError, "invalid_snapshot:2025-05-30"):
                audit_historical_ai_pool(path, REQUIRED)

    def test_duplicate_rank_fails(self) -> None:
        def tamper(rows: list[dict[str, str]]) -> list[dict[str, str]]:
            for row in rows:
                if row["eval_date"] == "2022-02-28" and row["score_rank"] == "2":
                    row["score_rank"] = "1"
                    break
            return rows

        with self._edited_material(tamper) as path:
            with self.assertRaisesRegex(ValueError, "invalid_snapshot:2022-02-28"):
                audit_historical_ai_pool(path, REQUIRED)

    from contextlib import contextmanager

    @contextmanager
    def _edited_material(self, edit):
        with MATERIAL.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        with tempfile.TemporaryDirectory(dir="/private/tmp") as temporary:
            path = Path(temporary) / "combined.csv"
            with path.open("w", newline="", encoding="utf-8-sig") as output:
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(edit(rows))
            yield path


class MinuteCoverageTests(unittest.TestCase):
    def test_opening_trade_coverage_separates_present_and_missing_days(self) -> None:
        import pandas as pd

        trades = pd.DataFrame(
            [
                {"trade_id": "open1", "datetime": "2026-10-14 09:01:00+08:00", "vt_symbol": "fu2611.SHFE", "offset": "开"},
                {"trade_id": "open2", "datetime": "2026-10-15 09:01:00+08:00", "vt_symbol": "fu2611.SHFE", "offset": "开"},
                {"trade_id": "close1", "datetime": "2026-10-14 14:01:00+08:00", "vt_symbol": "fu2611.SHFE", "offset": "平"},
            ]
        )
        minutes = pd.DataFrame(
            [
                {"vt_symbol": "fu2611.SHFE", "bar_date": pd.Timestamp("2026-10-14"), "bar_datetime": pd.Timestamp("2026-10-14 09:00:00")},
                {"vt_symbol": "fu2611.SHFE", "bar_date": pd.Timestamp("2026-10-14"), "bar_datetime": pd.Timestamp("2026-10-14 09:01:00")},
            ]
        )
        coverage = opening_minute_coverage(trades, minutes)
        self.assertEqual(coverage["minute_row_count"].tolist(), [2, 0])
        self.assertEqual(coverage["coverage_status"].tolist(), ["present_unverified", "missing"])
        self.assertEqual(coverage["trade_id"].tolist(), ["open1", "open2"])


if __name__ == "__main__":
    unittest.main()
