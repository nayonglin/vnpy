from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
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

    class Gateway:
        def on_tick(self, tick: Any) -> None:
            event_queue.put_nowait(("tick", tick))

    gateway = Gateway()
    restore_gateway = install_gateway_tick_ingress(gateway, pipeline)

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
                    gateway.on_tick(tick)
                    finished_ns = time.perf_counter_ns()
                    ingress_latencies_ms.append((finished_ns - started_ns) / 1_000_000)
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
        restore_gateway()
        consumer_stop.set()
        consumer.join(timeout=2.0)

    rss_after = _rss_bytes()
    overflow = _overflow_probe(output_dir)
    metrics = {
        "symbols": symbols,
        "ticks_per_second": ticks_per_second,
        "duration_seconds": duration_seconds,
        "writer_delay_ms": writer_delay_ms,
        "total_ticks": total_ticks,
        "injection_elapsed_seconds": injection_elapsed,
        "ingress_p99_ms": _percentile(ingress_latencies_ms, 0.99),
        "ingress_max_ms": max(ingress_latencies_ms, default=math.inf),
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
        "ingress_p99_le_1ms": metrics["ingress_p99_ms"] <= 1.0,
        "ingress_max_le_5ms": metrics["ingress_max_ms"] <= 5.0,
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
        "checks": checks,
        "failures": [name for name, passed in checks.items() if not passed],
    }
    (output_dir / "stage179_performance_gate.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
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
