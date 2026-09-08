from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
TESTS_DIR = ROOT / "tests"
for entry in (PORTFOLIO_DIR, TESTS_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from stage179_performance_gate import (  # noqa: E402
    _CompactThreadCpuSamples,
    _LatencyDiagnostics,
    _latency_hard_checks,
    _latency_segment_rows,
    _thread_cpu_gate_diagnostics,
    run_gate,
)


def _compact_samples(
    rows: list[dict[str, int | float]],
) -> _CompactThreadCpuSamples:
    samples = _CompactThreadCpuSamples()
    for row in rows:
        samples.append(
            sequence=int(row["sequence"]),
            thread_id=int(row["thread_id"]),
            started_wall_ns=int(row["started_wall_ns"]),
            finished_wall_ns=int(row["finished_wall_ns"]),
            started_thread_ns=int(row["started_thread_ns"]),
            finished_thread_ns=int(row["finished_thread_ns"]),
        )
    return samples


class Stage179PerformanceGateDiagnosticsTest(unittest.TestCase):
    def test_short_gate_emits_phase_and_gc_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_gate(
                symbols=1,
                ticks_per_second=100,
                duration_seconds=1,
                writer_delay_ms=0.0,
                output_dir=Path(directory),
            )
            for name in (
                "summary.json",
                "stage179_ingress_top_samples.csv",
                "stage179_latency_segments.csv",
                "runtime_versions.json",
                "sha256.json",
            ):
                self.assertTrue((Path(directory) / name).exists(), name)
            hashes = json.loads(
                (Path(directory) / "sha256.json").read_text(encoding="utf-8")
            )
            for name, expected in hashes["files"].items():
                actual = hashlib.sha256(
                    (Path(directory) / name).read_bytes()
                ).hexdigest()
                self.assertEqual(expected, actual, name)

        diagnostics = result["metrics"]["ingress_diagnostics"]
        self.assertGreaterEqual(len(diagnostics["top_samples"]), 1)
        top = diagnostics["top_samples"][0]
        self.assertIn("capture_wall_ms", top)
        self.assertIn("forward_wall_ms", top)
        self.assertIn("off_cpu_or_wait_ms", top)
        self.assertIn("gc_collection_count", diagnostics)

    def test_latency_segments_preserve_sequential_wall_and_cpu_tails(self) -> None:
        rows = _latency_segment_rows(
            total_ms=[0.1, 0.2, 6.0, 0.4],
            capture_ms=[0.05, 0.1, 5.8, 0.2],
            forward_ms=[0.01, 0.02, 0.03, 0.04],
            thread_cpu_ms=[0.08, 0.15, 0.2, 0.3],
            ticks_per_segment=2,
            wall_threshold_ms=5.0,
        )

        self.assertEqual(2, len(rows))
        self.assertEqual((1, 2), (rows[0]["sequence_start"], rows[0]["sequence_end"]))
        self.assertEqual((3, 4), (rows[1]["sequence_start"], rows[1]["sequence_end"]))
        self.assertEqual(1, rows[1]["wall_over_threshold_count"])
        self.assertEqual(6.0, rows[1]["ingress_max_ms"])
        self.assertEqual(5.8, rows[1]["capture_max_ms"])

    def test_top_samples_distinguish_off_cpu_from_callback_cpu(self) -> None:
        diagnostics = _LatencyDiagnostics(limit=2, wall_threshold_ms=5.0)
        diagnostics.record(
            sequence=1,
            started_wall_ns=1_000_000_000,
            finished_wall_ns=1_008_000_000,
            started_thread_ns=100_000_000,
            finished_thread_ns=100_200_000,
            capture_wall_ns=100_000,
            capture_thread_ns=80_000,
            forward_wall_ns=100_000,
            forward_thread_ns=80_000,
        )
        diagnostics.record(
            sequence=2,
            started_wall_ns=2_000_000_000,
            finished_wall_ns=2_006_000_000,
            started_thread_ns=200_000_000,
            finished_thread_ns=205_500_000,
            capture_wall_ns=5_300_000,
            capture_thread_ns=5_200_000,
            forward_wall_ns=100_000,
            forward_thread_ns=80_000,
        )
        diagnostics.record(
            sequence=3,
            started_wall_ns=3_000_000_000,
            finished_wall_ns=3_001_000_000,
            started_thread_ns=300_000_000,
            finished_thread_ns=300_500_000,
            capture_wall_ns=300_000,
            capture_thread_ns=200_000,
            forward_wall_ns=200_000,
            forward_thread_ns=100_000,
        )

        summary = diagnostics.summary(gc_intervals=[])

        self.assertEqual(2, summary["wall_over_5ms_count"])
        self.assertEqual([1, 2], [row["sequence"] for row in summary["top_samples"]])
        self.assertEqual("off_cpu_or_lock_wait", summary["top_samples"][0]["classification"])
        self.assertEqual("capture_cpu", summary["top_samples"][1]["classification"])

    def test_gc_interval_overlap_is_attached_to_top_sample(self) -> None:
        diagnostics = _LatencyDiagnostics(limit=1, wall_threshold_ms=5.0)
        diagnostics.record(
            sequence=7,
            started_wall_ns=10_000,
            finished_wall_ns=20_000,
            started_thread_ns=1_000,
            finished_thread_ns=9_000,
            capture_wall_ns=7_000,
            capture_thread_ns=7_000,
            forward_wall_ns=1_000,
            forward_thread_ns=500,
        )

        summary = diagnostics.summary(
            gc_intervals=[
                {
                    "generation": 1,
                    "started_wall_ns": 15_000,
                    "finished_wall_ns": 18_000,
                }
            ]
        )

        self.assertEqual([1], summary["top_samples"][0]["gc_generations"])

    def test_compact_sample_columns_stay_aligned_and_preserve_cpu_math(self) -> None:
        samples = _compact_samples(
            [
                {
                    "sequence": 1,
                    "thread_id": 11,
                    "started_wall_ns": 0,
                    "finished_wall_ns": 8_000_000,
                    "started_thread_ns": 0,
                    "finished_thread_ns": 6_000_000,
                },
                {
                    "sequence": 2,
                    "thread_id": 11,
                    "started_wall_ns": 8_000_000,
                    "finished_wall_ns": 9_000_000,
                    "started_thread_ns": 6_000_000,
                    "finished_thread_ns": 6_500_000,
                },
            ]
        )

        self.assertEqual((2, 2, 2, 2, 2, 2), samples.column_lengths())
        diagnostics = _thread_cpu_gate_diagnostics(
            samples=samples,
            gc_intervals=[],
        )
        self.assertEqual(2, diagnostics["sample_count"])
        self.assertEqual(6.0, diagnostics["non_gc_overlap_thread_cpu_max_ms"])

        samples.finished_thread_ns.pop()
        with self.assertRaisesRegex(ValueError, "length_mismatch"):
            _thread_cpu_gate_diagnostics(samples=samples, gc_intervals=[])

    def test_6ms_cpu_is_not_exempted_by_1ns_endpoint_or_other_thread(self) -> None:
        diagnostics = _thread_cpu_gate_diagnostics(
            samples=_compact_samples([
                {
                    "sequence": 1,
                    "thread_id": 11,
                    "started_wall_ns": 0,
                    "finished_wall_ns": 10_000_000,
                    "started_thread_ns": 0,
                    "finished_thread_ns": 6_000_000,
                    "wall_ms": 10.0,
                    "thread_cpu_ms": 6.0,
                }
            ]),
            gc_intervals=[
                {
                    "generation": 0,
                    "thread_id": 11,
                    "started_wall_ns": 1,
                    "finished_wall_ns": 2,
                    "started_thread_ns": 1,
                    "finished_thread_ns": 2,
                },
                {
                    "generation": 1,
                    "thread_id": 11,
                    "started_wall_ns": 10_000_000,
                    "finished_wall_ns": 11_000_000,
                    "started_thread_ns": 0,
                    "finished_thread_ns": 6_000_000,
                },
                {
                    "generation": 2,
                    "thread_id": 22,
                    "started_wall_ns": 1,
                    "finished_wall_ns": 9_000_000,
                    "started_thread_ns": 0,
                    "finished_thread_ns": 6_000_000,
                },
            ],
        )
        checks = _latency_hard_checks(
            ingress_p99_ms=0.5,
            ingress_max_ms=10.0,
            non_gc_overlap_thread_cpu_max_ms=diagnostics[
                "non_gc_overlap_thread_cpu_max_ms"
            ],
        )

        self.assertFalse(checks["ingress_non_gc_thread_cpu_max_le_5ms"])
        self.assertEqual(1, diagnostics["thread_cpu_over_5ms_count"])
        slow = diagnostics["slow_samples"][0]
        self.assertEqual([0], slow["gc_generations"])
        self.assertEqual(0.000001, slow["gc_thread_cpu_overlap_ms"])
        self.assertEqual(5.999999, slow["non_gc_thread_cpu_ms"])

    def test_same_thread_gc_subtraction_can_still_leave_cpu_over_5ms(self) -> None:
        diagnostics = _thread_cpu_gate_diagnostics(
            samples=_compact_samples([
                {
                    "sequence": 1,
                    "thread_id": 11,
                    "started_wall_ns": 0,
                    "finished_wall_ns": 10_000_000,
                    "started_thread_ns": 0,
                    "finished_thread_ns": 8_000_000,
                    "wall_ms": 10.0,
                    "thread_cpu_ms": 8.0,
                }
            ]),
            gc_intervals=[
                {
                    "generation": 2,
                    "thread_id": 11,
                    "started_wall_ns": 1_000_000,
                    "finished_wall_ns": 5_000_000,
                    "started_thread_ns": 1_000_000,
                    "finished_thread_ns": 3_000_000,
                }
            ],
        )
        checks = _latency_hard_checks(
            ingress_p99_ms=0.5,
            ingress_max_ms=10.0,
            non_gc_overlap_thread_cpu_max_ms=diagnostics[
                "non_gc_overlap_thread_cpu_max_ms"
            ],
        )

        self.assertTrue(checks["ingress_max_le_100ms"])
        self.assertFalse(checks["ingress_non_gc_thread_cpu_max_le_5ms"])
        self.assertEqual([2], diagnostics["slow_samples"][0]["gc_generations"])
        self.assertEqual(
            2.0,
            diagnostics["slow_samples"][0]["gc_thread_cpu_overlap_ms"],
        )
        self.assertEqual(
            6.0,
            diagnostics["slow_samples"][0]["non_gc_thread_cpu_ms"],
        )

    def test_same_thread_gc_subtraction_at_5ms_passes_without_double_count(self) -> None:
        diagnostics = _thread_cpu_gate_diagnostics(
            samples=_compact_samples([
                {
                    "sequence": 1,
                    "thread_id": 11,
                    "started_wall_ns": 0,
                    "finished_wall_ns": 10_000_000,
                    "started_thread_ns": 0,
                    "finished_thread_ns": 8_000_000,
                    "wall_ms": 10.0,
                    "thread_cpu_ms": 8.0,
                }
            ]),
            gc_intervals=[
                {
                    "generation": 1,
                    "thread_id": 11,
                    "started_wall_ns": 1_000_000,
                    "finished_wall_ns": 4_000_000,
                    "started_thread_ns": 1_000_000,
                    "finished_thread_ns": 3_000_000,
                },
                {
                    "generation": 2,
                    "thread_id": 11,
                    "started_wall_ns": 2_000_000,
                    "finished_wall_ns": 5_000_000,
                    "started_thread_ns": 2_000_000,
                    "finished_thread_ns": 4_000_000,
                },
            ],
        )
        checks = _latency_hard_checks(
            ingress_p99_ms=0.5,
            ingress_max_ms=10.0,
            non_gc_overlap_thread_cpu_max_ms=diagnostics[
                "non_gc_overlap_thread_cpu_max_ms"
            ],
        )

        self.assertTrue(checks["ingress_non_gc_thread_cpu_max_le_5ms"])
        self.assertEqual(5.0, diagnostics["non_gc_overlap_thread_cpu_max_ms"])
        self.assertEqual(
            3.0,
            diagnostics["slow_samples"][0]["gc_thread_cpu_overlap_ms"],
        )
        self.assertEqual(
            5.0,
            diagnostics["slow_samples"][0]["non_gc_thread_cpu_ms"],
        )

    def test_wall_101ms_fails_absolute_wall_gate(self) -> None:
        checks = _latency_hard_checks(
            ingress_p99_ms=0.5,
            ingress_max_ms=101.0,
            non_gc_overlap_thread_cpu_max_ms=0.5,
        )

        self.assertFalse(checks["ingress_max_le_100ms"])


if __name__ == "__main__":
    unittest.main()
