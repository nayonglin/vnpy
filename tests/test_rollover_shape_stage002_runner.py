from __future__ import annotations

import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rollover_shape_same_volume"
    / "tools"
)
sys.path.insert(0, str(TOOLS_DIR))

import stage002_rollover_shape_shrink_to_allowed_abc as stage002


class Stage002RunnerTest(unittest.TestCase):
    def test_empty_official_arm_has_zero_candidate_counts(self) -> None:
        row, diagnostics = stage002._event_summary(
            "official",
            {
                "rollover_shape_same_volume": pd.DataFrame(),
                "trades": pd.DataFrame(),
                "trade_events": pd.DataFrame(),
            },
            expected_policy=None,
        )

        self.assertTrue(diagnostics.empty)
        self.assertEqual(0, row["candidate_diagnostic_count"])
        self.assertEqual(0, row["targeted_count"])
        self.assertEqual(0, row["volume_contract_pass"])

    @staticmethod
    def _reduced_diagnostic(**overrides: object) -> pd.DataFrame:
        row: dict[str, object] = {
            "previous_volume": 10,
            "selected_volume_before_exact_gate": 7,
            "final_volume": 7,
            "volume_policy": "shrink_to_allowed",
            "volume_outcome": "reduced",
            "was_reduced": 1,
            "status": "targeted",
            "reason": "reduced_to_allowed_volume",
            "fill_status": "filled",
            "fill_volume": 7,
        }
        row.update(overrides)
        return pd.DataFrame([row])

    def test_candidate_contract_requires_exact_minimum_formula(self) -> None:
        diagnostics = self._reduced_diagnostic(final_volume=1, fill_volume=1)

        self.assertFalse(
            stage002._candidate_contract_pass(
                diagnostics,
                expected_policy="shrink_to_allowed",
                rollover_close_count=1,
            )
        )

    def test_candidate_contract_rejects_wrong_policy_or_outcome(self) -> None:
        wrong_policy = self._reduced_diagnostic(volume_policy="exact_or_skip")
        wrong_outcome = self._reduced_diagnostic(volume_outcome="full", was_reduced=0)

        for diagnostics in [wrong_policy, wrong_outcome]:
            with self.subTest(diagnostics=diagnostics.to_dict(orient="records")):
                self.assertFalse(
                    stage002._candidate_contract_pass(
                        diagnostics,
                        expected_policy="shrink_to_allowed",
                        rollover_close_count=1,
                    )
                )

    def test_candidate_contract_rejects_unfilled_target(self) -> None:
        diagnostics = self._reduced_diagnostic(fill_status="unfilled", fill_volume=0)

        self.assertFalse(
            stage002._candidate_contract_pass(
                diagnostics,
                expected_policy="shrink_to_allowed",
                rollover_close_count=1,
            )
        )

    def test_candidate_contract_survives_csv_round_trip_with_skipped_fill_status(self) -> None:
        targeted = self._reduced_diagnostic()
        skipped = self._reduced_diagnostic(
            selected_volume_before_exact_gate=0,
            final_volume=0,
            volume_outcome="skipped",
            was_reduced=0,
            status="skipped",
            reason="shape_or_macd_not_aligned",
            fill_status="",
            fill_volume=0,
        )
        serialized = StringIO()
        pd.concat([targeted, skipped], ignore_index=True).to_csv(serialized, index=False)
        serialized.seek(0)
        restored = pd.read_csv(serialized)

        self.assertTrue(
            stage002._candidate_contract_pass(
                restored,
                expected_policy="shrink_to_allowed",
                rollover_close_count=2,
            )
        )

    def test_atomic_publish_preserves_previous_output_when_staging_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            output_dir = Path(temporary_root) / "stage002"
            output_dir.mkdir()
            sentinel = output_dir / "verified.txt"
            sentinel.write_text("verified\n", encoding="utf-8")

            with patch.object(pd.DataFrame, "to_csv", side_effect=RuntimeError("write failed")):
                with self.assertRaisesRegex(RuntimeError, "write failed"):
                    stage002._publish_outputs_atomically(
                        output_dir,
                        {"result.csv": pd.DataFrame([{"value": 1}])},
                        {"status": "valid"},
                    )

            self.assertEqual("verified\n", sentinel.read_text(encoding="utf-8"))
            self.assertEqual(["verified.txt"], sorted(path.name for path in output_dir.iterdir()))


if __name__ == "__main__":
    unittest.main()
