from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
TESTS_DIR = ROOT / "tests"
for entry in (PORTFOLIO_DIR, TESTS_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from stage179_performance_gate import run_gate  # noqa: E402


class Stage179ProductionPerformanceGateTest(unittest.TestCase):
    def test_fixed_production_stress_gate_passes_from_raw_execution(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="stage179-production-performance-"
        ) as directory:
            output_dir = Path(directory)
            payload = run_gate(
                symbols=20,
                ticks_per_second=2_000,
                duration_seconds=60,
                writer_delay_ms=25.0,
                output_dir=output_dir,
            )
            raw_payload = json.loads(
                (output_dir / "stage179_performance_gate.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(payload, raw_payload)
        self.assertEqual(
            "passed",
            raw_payload["status"],
            json.dumps(
                {
                    "failures": raw_payload.get("failures"),
                    "metrics": raw_payload.get("metrics"),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        )
        self.assertEqual([], raw_payload["failures"])
        self.assertTrue(raw_payload["checks"])
        self.assertTrue(all(raw_payload["checks"].values()))
        metrics = raw_payload["metrics"]
        self.assertEqual(20, metrics["symbols"])
        self.assertEqual(2_000, metrics["ticks_per_second"])
        self.assertEqual(60, metrics["duration_seconds"])
        self.assertEqual(25.0, metrics["writer_delay_ms"])
        self.assertEqual(120_000, metrics["total_ticks"])
        self.assertEqual(0, metrics["send_order_api_called_count"])
        self.assertEqual(0, metrics["cancel_order_api_called_count"])


if __name__ == "__main__":
    unittest.main()
