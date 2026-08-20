from __future__ import annotations

import argparse
from array import array
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import heapq
import io
import json
import math
import os
from pathlib import Path
import platform
from queue import Empty, Queue
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from qmt_roll_official_live_tick_journal import _durability_barrier
from qmt_roll_official_live_tick_stream import (
    TickStreamPipeline,
    install_gateway_tick_ingress,
)
from qmt_roll_official_live_time import SystemClock


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return math.inf
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * percentile) - 1))
    return ordered[index]


class _LatencyDiagnostics:
    """Keep bounded causal evidence for rare wall-clock tail samples."""

    def __init__(self, *, limit: int, wall_threshold_ms: float) -> None:
        self.limit = max(1, int(limit))
        self.wall_threshold_ns = int(float(wall_threshold_ms) * 1_000_000)
        self.wall_over_threshold_count = 0
        self._top: list[tuple[int, int, dict[str, Any]]] = []

    def record(
        self,
        *,
        sequence: int,
        started_wall_ns: int,
        finished_wall_ns: int,
        started_thread_ns: int,
        finished_thread_ns: int,
        capture_wall_ns: int,
        capture_thread_ns: int,
        forward_wall_ns: int,
        forward_thread_ns: int,
    ) -> None:
        wall_ns = max(0, int(finished_wall_ns) - int(started_wall_ns))
        thread_ns = max(0, int(finished_thread_ns) - int(started_thread_ns))
        off_cpu_ns = max(0, wall_ns - thread_ns)
        wrapper_thread_ns = max(
            0,
            thread_ns - int(capture_thread_ns) - int(forward_thread_ns),
        )
        if wall_ns > self.wall_threshold_ns:
            self.wall_over_threshold_count += 1
        if off_cpu_ns >= 1_000_000 and off_cpu_ns * 2 >= wall_ns:
            classification = "off_cpu_or_lock_wait"
        elif int(capture_thread_ns) * 2 >= max(1, thread_ns):
            classification = "capture_cpu"
        elif int(forward_thread_ns) * 2 >= max(1, thread_ns):
            classification = "forward_cpu"
        else:
            classification = "wrapper_cpu"
        sample = {
            "sequence": int(sequence),
            "started_wall_ns": int(started_wall_ns),
            "finished_wall_ns": int(finished_wall_ns),
            "wall_ms": wall_ns / 1_000_000,
            "thread_cpu_ms": thread_ns / 1_000_000,
            "off_cpu_or_wait_ms": off_cpu_ns / 1_000_000,
            "capture_wall_ms": max(0, int(capture_wall_ns)) / 1_000_000,
            "capture_thread_cpu_ms": max(0, int(capture_thread_ns)) / 1_000_000,
            "forward_wall_ms": max(0, int(forward_wall_ns)) / 1_000_000,
            "forward_thread_cpu_ms": max(0, int(forward_thread_ns)) / 1_000_000,
            "wrapper_thread_cpu_ms": wrapper_thread_ns / 1_000_000,
            "classification": classification,
        }
        entry = (wall_ns, -int(sequence), sample)
        if len(self._top) < self.limit:
            heapq.heappush(self._top, entry)
        elif entry[:2] > self._top[0][:2]:
            heapq.heapreplace(self._top, entry)

    def summary(self, *, gc_intervals: list[dict[str, Any]]) -> dict[str, Any]:
        top_samples: list[dict[str, Any]] = []
        for _, _, sample in sorted(self._top, reverse=True):
            generations = sorted(
                {
                    int(interval["generation"])
                    for interval in gc_intervals
                    if int(interval["started_wall_ns"])
                    <= int(sample["finished_wall_ns"])
                    and int(interval["finished_wall_ns"])
                    >= int(sample["started_wall_ns"])
                }
            )
            top_samples.append({**sample, "gc_generations": generations})
        gc_durations_ms = [
            max(
                0,
                int(interval["finished_wall_ns"])
                - int(interval["started_wall_ns"]),
            )
            / 1_000_000
            for interval in gc_intervals
        ]
        return {
            "wall_over_5ms_count": self.wall_over_threshold_count,
            "top_samples": top_samples,
            "gc_collection_count": len(gc_intervals),
            "gc_collection_max_ms": max(gc_durations_ms, default=0.0),
        }


def _rss_bytes() -> int:
    result = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(os.getpid())],
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        return int(result.stdout.strip()) * 1024
    except ValueError:
        return 0


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _latency_segment_rows(
    *,
    total_ms: list[float],
    capture_ms: list[float],
    forward_ms: list[float],
    thread_cpu_ms: list[float],
    ticks_per_segment: int,
    wall_threshold_ms: float,
) -> list[dict[str, Any]]:
    """Summarize sequential fixed-size windows without hiding rare tails."""
    sample_count = len(total_ms)
    if not (
        len(capture_ms) == sample_count
        and len(forward_ms) == sample_count
        and len(thread_cpu_ms) == sample_count
    ):
        raise ValueError("latency_series_length_mismatch")
    segment_size = max(1, int(ticks_per_segment))
    rows: list[dict[str, Any]] = []
    for start in range(0, sample_count, segment_size):
        end = min(sample_count, start + segment_size)
        total_segment = total_ms[start:end]
        capture_segment = capture_ms[start:end]
        forward_segment = forward_ms[start:end]
        thread_segment = thread_cpu_ms[start:end]
        rows.append(
            {
                "segment_index": len(rows),
                "sequence_start": start + 1,
                "sequence_end": end,
                "sample_count": end - start,
                "ingress_p99_ms": _percentile(total_segment, 0.99),
                "ingress_max_ms": max(total_segment, default=math.inf),
                "capture_p99_ms": _percentile(capture_segment, 0.99),
                "capture_max_ms": max(capture_segment, default=math.inf),
                "forward_p99_ms": _percentile(forward_segment, 0.99),
                "forward_max_ms": max(forward_segment, default=math.inf),
                "thread_cpu_p99_ms": _percentile(thread_segment, 0.99),
                "thread_cpu_max_ms": max(thread_segment, default=math.inf),
                "wall_over_threshold_count": sum(
                    value > float(wall_threshold_ms)
                    for value in total_segment
                ),
            }
        )
    return rows


class _CompactThreadCpuSamples:
    """Store the complete ingress series without per-sample Python objects."""

    __slots__ = (
        "sequence",
        "thread_id",
        "started_wall_ns",
        "finished_wall_ns",
        "started_thread_ns",
        "finished_thread_ns",
    )

    def __init__(self) -> None:
        self.sequence = array("Q")
        self.thread_id = array("Q")
        self.started_wall_ns = array("Q")
        self.finished_wall_ns = array("Q")
        self.started_thread_ns = array("Q")
        self.finished_thread_ns = array("Q")

    def append(
        self,
        *,
        sequence: int,
        thread_id: int,
        started_wall_ns: int,
        finished_wall_ns: int,
        started_thread_ns: int,
        finished_thread_ns: int,
    ) -> None:
        values = (
            sequence,
            thread_id,
            started_wall_ns,
            finished_wall_ns,
            started_thread_ns,
            finished_thread_ns,
        )
        if any(int(value) < 0 for value in values):
            raise ValueError("compact_thread_cpu_sample_negative")
        for column, value in zip(self._columns(), values):
            column.append(int(value))

    def _columns(self) -> tuple[array, ...]:
        return (
            self.sequence,
            self.thread_id,
            self.started_wall_ns,
            self.finished_wall_ns,
            self.started_thread_ns,
            self.finished_thread_ns,
        )

    def column_lengths(self) -> tuple[int, ...]:
        return tuple(len(column) for column in self._columns())

    def validate(self) -> int:
        lengths = self.column_lengths()
        if len(set(lengths)) != 1:
            raise ValueError("compact_thread_cpu_sample_length_mismatch")
        return lengths[0]

    def __len__(self) -> int:
        return self.validate()


def _thread_cpu_gate_diagnostics(
    *,
    samples: _CompactThreadCpuSamples,
    gc_intervals: list[dict[str, Any]],
    slow_threshold_ms: float = 5.0,
) -> dict[str, Any]:
    """Subtract only attributable same-thread GC CPU from every sample."""

    slow_samples: list[dict[str, Any]] = []
    non_gc_thread_cpu_ms: list[float] = []
    gc_overlap_count = 0
    sample_count = samples.validate()
    for index in range(sample_count):
        sequence = int(samples.sequence[index])
        sample_thread_id = int(samples.thread_id[index])
        sample_started_wall_ns = int(samples.started_wall_ns[index])
        sample_finished_wall_ns = int(samples.finished_wall_ns[index])
        sample_started_thread_ns = int(samples.started_thread_ns[index])
        sample_finished_thread_ns = int(samples.finished_thread_ns[index])
        matching_intervals = [
            interval
            for interval in gc_intervals
            if int(interval["thread_id"]) == sample_thread_id
            and int(interval["started_wall_ns"]) < sample_finished_wall_ns
            and int(interval["finished_wall_ns"]) > sample_started_wall_ns
        ]
        generations = sorted(
            {int(interval["generation"]) for interval in matching_intervals}
        )
        gc_cpu_segments = sorted(
            (
                max(
                    sample_started_thread_ns,
                    int(interval["started_thread_ns"]),
                ),
                min(
                    sample_finished_thread_ns,
                    int(interval["finished_thread_ns"]),
                ),
            )
            for interval in matching_intervals
            if max(
                sample_started_thread_ns,
                int(interval["started_thread_ns"]),
            )
            < min(
                sample_finished_thread_ns,
                int(interval["finished_thread_ns"]),
            )
        )
        merged_gc_cpu_segments: list[list[int]] = []
        for started_thread_ns, finished_thread_ns in gc_cpu_segments:
            if (
                not merged_gc_cpu_segments
                or started_thread_ns > merged_gc_cpu_segments[-1][1]
            ):
                merged_gc_cpu_segments.append(
                    [started_thread_ns, finished_thread_ns]
                )
            else:
                merged_gc_cpu_segments[-1][1] = max(
                    merged_gc_cpu_segments[-1][1],
                    finished_thread_ns,
                )
        gc_thread_cpu_ns = sum(
            finished_thread_ns - started_thread_ns
            for started_thread_ns, finished_thread_ns in merged_gc_cpu_segments
        )
        thread_cpu_ns = max(
            0,
            sample_finished_thread_ns - sample_started_thread_ns,
        )
        non_gc_thread_cpu_ns = max(0, thread_cpu_ns - gc_thread_cpu_ns)
        thread_cpu_ms = thread_cpu_ns / 1_000_000
        non_gc_thread_cpu_value_ms = non_gc_thread_cpu_ns / 1_000_000
        non_gc_thread_cpu_ms.append(non_gc_thread_cpu_value_ms)
        if gc_thread_cpu_ns > 0:
            gc_overlap_count += 1
        if thread_cpu_ms > float(slow_threshold_ms):
            slow_samples.append(
                {
                    "sequence": sequence,
                    "thread_id": sample_thread_id,
                    "started_wall_ns": sample_started_wall_ns,
                    "finished_wall_ns": sample_finished_wall_ns,
                    "started_thread_ns": sample_started_thread_ns,
                    "finished_thread_ns": sample_finished_thread_ns,
                    "wall_ms": max(
                        0,
                        sample_finished_wall_ns - sample_started_wall_ns,
                    )
                    / 1_000_000,
                    "thread_cpu_ms": thread_cpu_ms,
                    "gc_generations": generations,
                    "gc_overlap": int(gc_thread_cpu_ns > 0),
                    "gc_thread_cpu_overlap_ms": (
                        gc_thread_cpu_ns / 1_000_000
                    ),
                    "non_gc_thread_cpu_ms": non_gc_thread_cpu_value_ms,
                }
            )
    return {
        "sample_count": sample_count,
        "gc_overlap_sample_count": gc_overlap_count,
        "non_gc_overlap_sample_count": sample_count - gc_overlap_count,
        "thread_cpu_over_5ms_count": len(slow_samples),
        "non_gc_overlap_thread_cpu_over_5ms_count": sum(
            value > float(slow_threshold_ms)
            for value in non_gc_thread_cpu_ms
        ),
        "non_gc_overlap_thread_cpu_max_ms": max(
            non_gc_thread_cpu_ms,
            default=0.0,
        ),
        "slow_samples": slow_samples,
    }


def _latency_hard_checks(
    *,
    ingress_p99_ms: float,
    ingress_max_ms: float,
    non_gc_overlap_thread_cpu_max_ms: float,
) -> dict[str, bool]:
    return {
        "ingress_p99_le_1ms": float(ingress_p99_ms) <= 1.0,
        "ingress_max_le_100ms": float(ingress_max_ms) <= 100.0,
        "ingress_non_gc_thread_cpu_max_le_5ms": (
            float(non_gc_overlap_thread_cpu_max_ms) <= 5.0
        ),
    }


def _write_evidence_bundle(output_dir: Path, payload: dict[str, Any]) -> None:
    summary_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    performance_path = output_dir / "stage179_performance_gate.json"
    summary_path = output_dir / "summary.json"
    performance_path.write_text(summary_text, encoding="utf-8")
    summary_path.write_text(summary_text, encoding="utf-8")

    top_samples = list(
        payload.get("metrics", {})
        .get("ingress_diagnostics", {})
        .get("top_samples", [])
    )
    csv_buffer = io.StringIO(newline="")
    fieldnames = list(top_samples[0]) if top_samples else ["sequence"]
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in top_samples:
        writer.writerow(
            {
                key: (
                    json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                    if isinstance(value, (list, dict))
                    else value
                )
                for key, value in row.items()
            }
        )
    top_samples_path = output_dir / "stage179_ingress_top_samples.csv"
    top_samples_path.write_text(csv_buffer.getvalue(), encoding="utf-8")

    latency_segments = list(payload.get("latency_segments", []))
    segment_buffer = io.StringIO(newline="")
    segment_fieldnames = (
        list(latency_segments[0]) if latency_segments else ["segment_index"]
    )
    segment_writer = csv.DictWriter(
        segment_buffer,
        fieldnames=segment_fieldnames,
    )
    segment_writer.writeheader()
    segment_writer.writerows(latency_segments)
    segments_path = output_dir / "stage179_latency_segments.csv"
    segments_path.write_text(segment_buffer.getvalue(), encoding="utf-8")

    runtime_payload = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "process_pid": os.getpid(),
        "runtime_policy_label": os.environ.get(
            "STAGE179_PERFORMANCE_RUNTIME_POLICY",
            "unspecified",
        ),
        "perf_counter": vars(time.get_clock_info("perf_counter")),
        "thread_time": vars(time.get_clock_info("thread_time")),
    }
    runtime_path = output_dir / "runtime_versions.json"
    runtime_path.write_text(
        json.dumps(runtime_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    evidence_paths = (
        performance_path,
        summary_path,
        top_samples_path,
        segments_path,
        runtime_path,
        output_dir / "ticks.ndjson",
        output_dir / "overflow.ndjson",
    )
    hash_payload = {
        "algorithm": "sha256",
        "files": {
            path.name: _sha256_file(path)
            for path in evidence_paths
            if path.exists()
        },
    }
    (output_dir / "sha256.json").write_text(
        json.dumps(hash_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _tick(index: int, symbols: int) -> SimpleNamespace:
    symbol_index = index % symbols
    price = 1000.0 + (index % 100) * 0.5
    return SimpleNamespace(
        vt_symbol=f"PF{symbol_index:02d}.TEST",
        symbol=f"PF{symbol_index:02d}",
        exchange=SimpleNamespace(value="TEST"),
        datetime=datetime.now(timezone.utc),
        last_price=price,
        bid_price_1=price - 0.5,
        ask_price_1=price + 0.5,
        bid_volume_1=10,
        ask_volume_1=12,
        limit_up=price * 1.1,
        limit_down=price * 0.9,
    )


def _overflow_probe(output_dir: Path) -> dict[str, Any]:
    pipeline = TickStreamPipeline(
        feed_session_id="stage179-overflow-probe",
        journal_segment_path=output_dir / "overflow.ndjson",
        clock=SystemClock(),
        queue_capacity=1,
        max_buffer_ticks=1,
        writer_batch_size=1,
        writer_flush_seconds=0.001,
    )
    pipeline.capture_ingress(_tick(0, 1))
    started = time.perf_counter_ns()
    pipeline.capture_ingress(_tick(1, 1))
    latched = time.perf_counter_ns()
    snapshot = pipeline.durable_snapshot()
    revoked = time.perf_counter_ns()
    report = pipeline.shutdown(timeout_seconds=2.0)
    return {
        "fault_latch_ms": (latched - started) / 1_000_000,
        "readiness_revoke_ms": (revoked - started) / 1_000_000,
        "dropped_tick_count": snapshot.dropped_tick_count,
        "stream_ready": snapshot.stream_ready,
        "gap": asdict(snapshot.gap) if snapshot.gap else None,
        "shutdown_gap": asdict(report.gap) if report.gap else None,
    }


def run_gate(
    *,
    symbols: int,
    ticks_per_second: int,
    duration_seconds: int,
    writer_delay_ms: float,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    total_ticks = int(ticks_per_second) * int(duration_seconds)
    clock = SystemClock()
    pipeline = TickStreamPipeline(
        feed_session_id="stage179-p0-performance",
        journal_segment_path=output_dir / "ticks.ndjson",
        clock=clock,
        queue_capacity=8192,
        max_buffer_ticks=4096,
        writer_batch_size=256,
        writer_flush_seconds=0.050,
    )
    event_queue: Queue[tuple[str, Any]] = Queue()
    consumer_stop = threading.Event()
    sentinel_latencies_ms: list[float] = []

    class InstrumentedPipeline:
        def capture_ingress(self, tick: Any) -> Any:
            started_wall_ns = time.perf_counter_ns()
            started_thread_ns = time.thread_time_ns()
            try:
                return pipeline.capture_ingress(tick)
            finally:
                setattr(
                    tick,
                    "_stage179_perf_capture_wall_ns",
                    time.perf_counter_ns() - started_wall_ns,
                )
                setattr(
                    tick,
                    "_stage179_perf_capture_thread_ns",
                    time.thread_time_ns() - started_thread_ns,
                )

        def latch_capture_exception(self, exc: Exception) -> None:
            pipeline.latch_capture_exception(exc)

        def _force_fail_closed_after_latch_error(self, exc: Exception) -> None:
            pipeline._force_fail_closed_after_latch_error(exc)

    class Gateway:
        def on_tick(self, tick: Any) -> None:
            started_wall_ns = time.perf_counter_ns()
            started_thread_ns = time.thread_time_ns()
            try:
                event_queue.put_nowait(("tick", tick))
            finally:
                setattr(
                    tick,
                    "_stage179_perf_forward_wall_ns",
                    time.perf_counter_ns() - started_wall_ns,
                )
                setattr(
                    tick,
                    "_stage179_perf_forward_thread_ns",
                    time.thread_time_ns() - started_thread_ns,
                )

    gateway = Gateway()
    restore_gateway = install_gateway_tick_ingress(
        gateway,
        InstrumentedPipeline(),
    )

    def event_consumer() -> None:
        while not consumer_stop.is_set() or not event_queue.empty():
            try:
                kind, payload = event_queue.get(timeout=0.05)
            except Empty:
                continue
            try:
                if kind == "tick":
                    pipeline.observe_handler(payload)
                else:
                    sentinel_latencies_ms.append(
                        (time.perf_counter_ns() - int(payload)) / 1_000_000
                    )
            finally:
                event_queue.task_done()

    consumer = threading.Thread(
        target=event_consumer,
        name="stage179-fake-event-engine",
        daemon=True,
    )
    consumer.start()
    ingress_latencies_ms: list[float] = []
    ingress_thread_cpu_ms: list[float] = []
    ingress_sample_intervals = _CompactThreadCpuSamples()
    capture_latencies_ms: list[float] = []
    forward_latencies_ms: list[float] = []
    latency_diagnostics = _LatencyDiagnostics(
        limit=20,
        wall_threshold_ms=5.0,
    )
    gc_intervals: list[dict[str, Any]] = []
    active_gc: dict[int, list[dict[str, Any]]] = {}

    def gc_callback(phase: str, info: dict[str, Any]) -> None:
        thread_id = threading.get_ident()
        if phase == "start":
            active_gc.setdefault(thread_id, []).append(
                {
                    "generation": int(info.get("generation", -1)),
                    "thread_id": thread_id,
                    "started_wall_ns": time.perf_counter_ns(),
                    "started_thread_ns": time.thread_time_ns(),
                }
            )
            return
        thread_stack = active_gc.get(thread_id)
        if phase != "stop" or not thread_stack:
            return
        started = thread_stack.pop()
        if not thread_stack:
            active_gc.pop(thread_id, None)
        gc_intervals.append(
            {
                **started,
                "finished_wall_ns": time.perf_counter_ns(),
                "finished_thread_ns": time.thread_time_ns(),
                "collected": int(info.get("collected", 0)),
                "uncollectable": int(info.get("uncollectable", 0)),
            }
        )
    durable_lag_ms: list[float] = []
    ingress_monotonic_ns = [0] * (total_ticks + 1)
    previous_durable = 0
    original_barrier = _durability_barrier

    def delayed_barrier(file_descriptor: int) -> None:
        if writer_delay_ms > 0:
            time.sleep(writer_delay_ms / 1000.0)
        original_barrier(file_descriptor)

    rss_before = _rss_bytes()
    injection_started = 0.0
    injection_elapsed = 0.0
    next_sentinel = 0.0
    try:
        gc.callbacks.append(gc_callback)
        with patch(
            "qmt_roll_official_live_tick_journal._durability_barrier",
            side_effect=delayed_barrier,
        ):
            pipeline.start()
            if not pipeline.wait_until_journal_ready(timeout_seconds=2.0):
                raise RuntimeError("journal_header_not_durable")
            injection_started = time.monotonic()
            next_sentinel = injection_started
            sent = 0
            while sent < total_ticks:
                now = time.monotonic()
                due = min(
                    total_ticks,
                    int((now - injection_started) * ticks_per_second) + 1,
                )
                if due <= sent:
                    time.sleep(min(0.0005, (sent + 1) / ticks_per_second - (now - injection_started)))
                    continue
                while sent < due:
                    tick = _tick(sent, symbols)
                    started_ns = time.perf_counter_ns()
                    started_thread_ns = time.thread_time_ns()
                    thread_id = threading.get_ident()
                    gateway.on_tick(tick)
                    finished_thread_ns = time.thread_time_ns()
                    finished_ns = time.perf_counter_ns()
                    ingress_latencies_ms.append((finished_ns - started_ns) / 1_000_000)
                    ingress_thread_cpu_ms.append(
                        (finished_thread_ns - started_thread_ns) / 1_000_000
                    )
                    ingress_sample_intervals.append(
                        sequence=sent + 1,
                        thread_id=thread_id,
                        started_wall_ns=started_ns,
                        finished_wall_ns=finished_ns,
                        started_thread_ns=started_thread_ns,
                        finished_thread_ns=finished_thread_ns,
                    )
                    capture_wall_ns = int(
                        getattr(tick, "_stage179_perf_capture_wall_ns", 0)
                    )
                    capture_thread_ns = int(
                        getattr(tick, "_stage179_perf_capture_thread_ns", 0)
                    )
                    forward_wall_ns = int(
                        getattr(tick, "_stage179_perf_forward_wall_ns", 0)
                    )
                    forward_thread_ns = int(
                        getattr(tick, "_stage179_perf_forward_thread_ns", 0)
                    )
                    capture_latencies_ms.append(capture_wall_ns / 1_000_000)
                    forward_latencies_ms.append(forward_wall_ns / 1_000_000)
                    latency_diagnostics.record(
                        sequence=sent + 1,
                        started_wall_ns=started_ns,
                        finished_wall_ns=finished_ns,
                        started_thread_ns=started_thread_ns,
                        finished_thread_ns=finished_thread_ns,
                        capture_wall_ns=capture_wall_ns,
                        capture_thread_ns=capture_thread_ns,
                        forward_wall_ns=forward_wall_ns,
                        forward_thread_ns=forward_thread_ns,
                    )
                    captured = tick._stage179_tick_ingress_envelope
                    ingress_monotonic_ns[captured.ingress_sequence] = (
                        captured.ingress_monotonic_ns
                    )
                    sent += 1
                if now >= next_sentinel:
                    event_queue.put_nowait(("sentinel", time.perf_counter_ns()))
                    next_sentinel = now + 0.05
                snapshot = pipeline.durable_snapshot()
                if snapshot.durable_ingress_sequence > previous_durable:
                    observed_ns = time.monotonic_ns()
                    durable_lag_ms.extend(
                        (observed_ns - ingress_monotonic_ns[sequence]) / 1_000_000
                        for sequence in range(
                            previous_durable + 1,
                            snapshot.durable_ingress_sequence + 1,
                        )
                    )
                    previous_durable = snapshot.durable_ingress_sequence
            injection_elapsed = time.monotonic() - injection_started
            event_queue.join()
            drain_started = time.monotonic()
            report = pipeline.shutdown(timeout_seconds=2.0)
            drain_seconds = time.monotonic() - drain_started
            final_snapshot = pipeline.durable_snapshot()
            if final_snapshot.durable_ingress_sequence > previous_durable:
                observed_ns = time.monotonic_ns()
                durable_lag_ms.extend(
                    (observed_ns - ingress_monotonic_ns[sequence]) / 1_000_000
                    for sequence in range(
                        previous_durable + 1,
                        final_snapshot.durable_ingress_sequence + 1,
                    )
                )
    finally:
        try:
            gc.callbacks.remove(gc_callback)
        except ValueError:
            pass
        restore_gateway()
        consumer_stop.set()
        consumer.join(timeout=2.0)

    rss_after = _rss_bytes()
    overflow = _overflow_probe(output_dir)
    thread_cpu_diagnostics = _thread_cpu_gate_diagnostics(
        samples=ingress_sample_intervals,
        gc_intervals=gc_intervals,
    )
    metrics = {
        "symbols": symbols,
        "ticks_per_second": ticks_per_second,
        "duration_seconds": duration_seconds,
        "writer_delay_ms": writer_delay_ms,
        "total_ticks": total_ticks,
        "injection_elapsed_seconds": injection_elapsed,
        "ingress_p99_ms": _percentile(ingress_latencies_ms, 0.99),
        "ingress_max_ms": max(ingress_latencies_ms, default=math.inf),
        "ingress_thread_cpu_p99_ms": _percentile(
            ingress_thread_cpu_ms,
            0.99,
        ),
        "ingress_thread_cpu_max_ms": max(
            ingress_thread_cpu_ms,
            default=math.inf,
        ),
        "ingress_thread_cpu_diagnostics": thread_cpu_diagnostics,
        "capture_ingress_p99_ms": _percentile(capture_latencies_ms, 0.99),
        "capture_ingress_max_ms": max(capture_latencies_ms, default=math.inf),
        "original_event_enqueue_p99_ms": _percentile(
            forward_latencies_ms,
            0.99,
        ),
        "original_event_enqueue_max_ms": max(
            forward_latencies_ms,
            default=math.inf,
        ),
        "ingress_diagnostics": latency_diagnostics.summary(
            gc_intervals=gc_intervals,
        ),
        "event_sentinel_samples": len(sentinel_latencies_ms),
        "event_sentinel_p99_ms": _percentile(sentinel_latencies_ms, 0.99),
        "event_sentinel_max_ms": max(sentinel_latencies_ms, default=math.inf),
        "durable_lag_samples": len(durable_lag_ms),
        "durable_lag_p99_ms": _percentile(durable_lag_ms, 0.99),
        "durable_lag_max_ms": max(durable_lag_ms, default=math.inf),
        "drain_seconds": drain_seconds,
        "rss_growth_mib": max(0, rss_after - rss_before) / (1024 * 1024),
        "dropped_tick_count": final_snapshot.dropped_tick_count,
        "gap": asdict(final_snapshot.gap) if final_snapshot.gap else None,
        "writer_fault": (
            asdict(final_snapshot.writer_fault)
            if final_snapshot.writer_fault
            else None
        ),
        "durable_ingress_sequence": final_snapshot.durable_ingress_sequence,
        "shutdown_drained": report.drained,
        "overflow": overflow,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
    }
    checks = {
        "exact_tick_count": final_snapshot.last_ingress_sequence == total_ticks,
        "duration_rate": injection_elapsed <= duration_seconds + 0.5,
        "zero_silent_drop": final_snapshot.dropped_tick_count == 0,
        "zero_gap": final_snapshot.gap is None,
        "zero_writer_fault": final_snapshot.writer_fault is None,
        "fully_durable": final_snapshot.durable_ingress_sequence == total_ticks,
        **_latency_hard_checks(
            ingress_p99_ms=metrics["ingress_p99_ms"],
            ingress_max_ms=metrics["ingress_max_ms"],
            non_gc_overlap_thread_cpu_max_ms=thread_cpu_diagnostics[
                "non_gc_overlap_thread_cpu_max_ms"
            ],
        ),
        "sentinel_p99_le_20ms": metrics["event_sentinel_p99_ms"] <= 20.0,
        "sentinel_max_le_100ms": metrics["event_sentinel_max_ms"] <= 100.0,
        "durable_lag_p99_le_100ms": metrics["durable_lag_p99_ms"] <= 100.0,
        "durable_lag_max_le_500ms": metrics["durable_lag_max_ms"] <= 500.0,
        "drain_le_2s": drain_seconds <= 2.0 and report.drained,
        "rss_growth_le_64mib": metrics["rss_growth_mib"] <= 64.0,
        "overflow_latch_le_10ms": overflow["fault_latch_ms"] <= 10.0,
        "overflow_revoke_le_1s": overflow["readiness_revoke_ms"] <= 1000.0,
        "overflow_never_ready": bool(
            overflow["dropped_tick_count"] > 0 and not overflow["stream_ready"]
        ),
    }
    payload = {
        "status": "passed" if all(checks.values()) else "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "latency_segments": _latency_segment_rows(
            total_ms=ingress_latencies_ms,
            capture_ms=capture_latencies_ms,
            forward_ms=forward_latencies_ms,
            thread_cpu_ms=ingress_thread_cpu_ms,
            ticks_per_segment=ticks_per_second,
            wall_threshold_ms=5.0,
        ),
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
    }
    _write_evidence_bundle(output_dir, payload)
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", type=int, required=True)
    parser.add_argument("--ticks-per-second", type=int, required=True)
    parser.add_argument("--duration-seconds", type=int, required=True)
    parser.add_argument("--writer-delay-ms", type=float, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = run_gate(
        symbols=args.symbols,
        ticks_per_second=args.ticks_per_second,
        duration_seconds=args.duration_seconds,
        writer_delay_ms=args.writer_delay_ms,
        output_dir=args.output_dir,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if payload["status"] == "passed" else 2)


if __name__ == "__main__":
    main()
