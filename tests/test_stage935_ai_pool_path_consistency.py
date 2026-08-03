from __future__ import annotations

import inspect
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import build_qmt_roll_stage182_ai_product_pool_live_inference_runner as stage182  # noqa: E402
import build_qmt_roll_stage183_ai_product_pool_source_refresh as stage183  # noqa: E402


class Stage935AiPoolPathConsistencyTest(unittest.TestCase):
    SOURCE_PREFIX = "qmt_roll_stage183_ai_source_floor35"

    def _write_stage182_sources(self, root: Path, max_date: str) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{self.SOURCE_PREFIX}_position_changes_2020_2026_04.csv").write_text(
            "date,vt_symbol,start_pos,end_pos,pos_change\n"
            f"{max_date},rb2610.SHFE,0,0,0\n",
            encoding="utf-8",
        )
        (root / f"{self.SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv").write_text(
            "date,product_vt_symbol,candidate_status\n"
            f"{max_date},rb.SHFE,rejected\n",
            encoding="utf-8",
        )

    def test_stage183_artifact_paths_use_real_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control_root = Path(directory).resolve() / "control"
            control_root.mkdir()

            build_paths = getattr(stage183, "_build_artifact_paths", None)
            self.assertTrue(
                callable(build_paths),
                "Stage183 must expose runtime-root artifact path construction",
            )
            paths = build_paths(
                source_prefix=self.SOURCE_PREFIX,
                artifact_root=control_root,
            )

        self.assertEqual(
            control_root,
            paths["position_changes"].resolve().parent,
        )
        self.assertEqual(
            control_root,
            paths["entry_candidate_snapshots"].resolve().parent,
        )

    def test_stage182_source_dir_does_not_fall_back_to_stale_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            stale_data_root = root / "data"
            control_root = root / "control"
            self._write_stage182_sources(stale_data_root, "2026-07-21")
            self._write_stage182_sources(control_root, "2026-08-03")

            self.assertIn(
                "source_dir",
                inspect.signature(stage182._configure_source_paths).parameters,
                "Stage182 source configuration must require an explicit source root",
            )
            source_paths = stage182._configure_source_paths(
                self.SOURCE_PREFIX,
                source_dir=control_root,
            )

        self.assertEqual(
            control_root,
            Path(source_paths["position_changes"]).resolve().parent,
        )
        self.assertEqual(
            control_root,
            stage182.suitability.POSITION_CHANGES_PATH.resolve().parent,
        )


if __name__ == "__main__":
    unittest.main()
