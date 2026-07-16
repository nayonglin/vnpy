# Stage179 Live Execution Latency and Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a default-off Stage179 candidate that fixes gateway-ingress causality, removes EventEngine disk I/O, enforces a 25-second ingress-to-send deadline, adds a durable close-priority intent path and warm executor, and remains non-activatable until offline, read-only CTP, SimNow, policy, and independent-review gates pass.

**Architecture:** Keep market data, deterministic detection, and TD execution in separate Stage930-owned child-process fault domains. Stage608 publishes only fsynced tick cursors; a persistent Stage941 detector commits Stage904 state before an SQLite WAL intent spool; a generation-bound Stage931 service reuses one CTP connection while retaining fresh O-P-O, Q2 tick, watermark, execution-ledger lease, and batch API-slot gates for every intent.

**Tech Stack:** Python 3.11 via `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`, vn.py/vnpy_ctp, standard-library `queue`, `threading`, `sqlite3`, NDJSON with `flock/fsync`, Unix datagram sockets, Bash, macOS launchd, and `unittest`/`pytest`.

## Global Constraints

- Work only in `/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability` on `codex/stage179-live-execution-reliability`; preserve the dirty main checkout.
- Use research line `futures_trend_stage819_intraday_rules`; update only its unique Stage179 stage record during implementation, not `LINE.md`, `research/registry.md`, root `memory.md`, or root `back_log.md`.
- Do not modify C9/Stage847 Alpha, AI pool, product pool, stop threshold, retry count, position sizing, capital, or strategy parameters.
- P0 must not source any `*.local.env`, connect native CTP, invoke `launchctl`, or call a real order adapter; send/cancel API counts remain `0/0`.
- Keep existing Stage608/904/905/930/931 CLI flags and compatibility artifacts unless this plan explicitly adds an optional flag; new behavior defaults off.
- Gateway freshness is based only on pre-EventEngine ingress time. Handler time is diagnostic and must never replace ingress time.
- Queue overflow, writer/fsync failure, sequence gap, time rollback, state corruption, runtime-profile conflict, release-manifest mismatch, or unknown broker side effect must fail closed.
- Protective close has priority over open. Open backlog cannot block close, but uncertain broker state cannot authorize a blind close.
- `send_order` empty return, exception, or ack timeout is an unknown side effect and must never be automatically retried.
- Preserve execution-ledger lease/CAS and V1 compatibility; any API-slot/send/cancel/fill/unknown V2 evidence requires a V2-capable reader during rollback.
- The current Stage372/20w versus Stage847-C9/15w policy conflict remains a production-live blocker. This implementation does not choose the official capital/profile on the operator's behalf.
- Initial hard limits are exact: ingress→durable `1s`, durable→Stage904 `1s`, Stage904→spool `0.5s`, spool→dequeue `0.5s`, dequeue→send `20s`, ingress→send `25s`, send→ack `3s`, cancel→terminal `10s`, fill→ledger `2s`. At the deadline boundary (`now >= deadline`) the intent is late.
- Do not shorten or delete double O-P-O, Q2 causal tick, or order/trade/position watermark gates to meet latency.
- Use TDD for every behavior change: record the focused RED command/output, make the minimum GREEN change, run the focused suite, then commit.
- After every implementation task, run an independent task-scoped review for both spec compliance and code quality. Fix all Critical/Important findings before advancing.

---

### Task 0: Freeze the Existing Stage179 Candidate as a Reviewable Baseline

**Files:**
- Commit: the existing 13 modified production files, 3 new production helpers, 11 new tests, and `research/lines/futures_trend_stage819_intraday_rules/stages/20260713_2220_stage179_c9_live_execution_reliability_hardening.md`
- Exclude: `.superpowers/`, local env files, output artifacts, and the main checkout

**Interfaces:**
- Consumes: current uncommitted Stage179 candidate based on `533fa961c`
- Produces: one immutable checkpoint commit that later task diffs can use as their base

- [ ] **Step 1: Capture the candidate inventory and verify no unexpected path is included**

```bash
git status --short
git diff --check
```

Expected: only the known Stage179 paths are present; `git diff --check` exits 0.

- [ ] **Step 2: Re-run the existing candidate baseline**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m pytest -q \
  tests/test_official_live_c9_intraday_state.py \
  tests/test_official_live_execution_ledger_cycles.py \
  tests/test_official_live_late_retry_fill.py \
  tests/test_stage174_query_bundle.py \
  tests/test_stage608_continuous_tick_stream.py \
  tests/test_stage904_durable_state_integration.py \
  tests/test_stage905_c9_cycle_intents.py \
  tests/test_stage930_fast_lane.py \
  tests/test_stage931_ctp_readiness.py \
  tests/test_stage931_post_reprice_final_gate.py \
  tests/test_stage931_trade_fill_accounting.py
```

Expected: `249 passed, 48 subtests passed`; no CTP/env/order activity.

- [ ] **Step 3: Commit only the existing candidate**

```bash
git add \
  examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-day-session.plist \
  examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-night-session.plist \
  examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py \
  examples/portfolio_backtesting/qmt_roll_official_live_phase_d_config.py \
  examples/portfolio_backtesting/qmt_roll_official_live_c9_intraday_state.py \
  examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py \
  examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py \
  examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.py \
  examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py \
  examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py \
  examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py \
  examples/portfolio_backtesting/run_qmt_roll_stage929_official_live_15w_timed_cycle.py \
  examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py \
  examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_supervisor.sh \
  examples/portfolio_backtesting/run_qmt_roll_stage930_owned_child_guard.py \
  examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py \
  research/lines/futures_trend_stage819_intraday_rules/stages/20260713_2220_stage179_c9_live_execution_reliability_hardening.md \
  tests/test_official_live_c9_intraday_state.py \
  tests/test_official_live_execution_ledger_cycles.py \
  tests/test_official_live_late_retry_fill.py \
  tests/test_stage174_query_bundle.py \
  tests/test_stage608_continuous_tick_stream.py \
  tests/test_stage904_durable_state_integration.py \
  tests/test_stage905_c9_cycle_intents.py \
  tests/test_stage930_fast_lane.py \
  tests/test_stage931_ctp_readiness.py \
  tests/test_stage931_post_reprice_final_gate.py \
  tests/test_stage931_trade_fill_accounting.py
git commit -m "feat(stage179): checkpoint live execution reliability candidate"
```

Expected: a commit is created and the worktree is clean apart from ignored `.superpowers` scratch files.

---

### Task 1: Add the Gateway-Ingress Clock, Bounded Queue, and Fault Latch

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_time.py`
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_tick_stream.py`
- Modify: `tests/test_stage608_continuous_tick_stream.py`

**Interfaces:**
- Consumes: a vn.py gateway instance and immutable tick field copies
- Produces: `Clock`, `SystemClock`, `DurableTickCursor`, `TickIngressEnvelope`, `TickStreamGap`, `TickStreamFault`, and `TickStreamPipeline.capture_ingress()`

- [ ] **Step 1: Write RED tests for causal stamping, nonblocking overflow, and gateway forwarding**

Add tests named:

```python
def test_gateway_ingress_stamp_precedes_event_engine_backlog(self):
    self.assertLess(envelope.ingress_monotonic_ns, cutoff_ns)
    self.assertGreater(observation.handler_received_monotonic_ns, cutoff_ns)
    self.assertEqual(envelope.received_at_utc, envelope.tick_row["received_at"])

def test_queue_overflow_latches_exact_gap_and_never_auto_recovers(self):
    self.assertEqual(snapshot.dropped_tick_count, 2)
    self.assertEqual((snapshot.gap.start_ingress_sequence, snapshot.gap.end_ingress_sequence), (2, 3))
    self.assertFalse(snapshot.stream_ready)
    self.assertEqual(forwarded_sequences, [1, 2, 3])

def test_event_handler_observation_is_diagnostic_only(self):
    self.assertEqual(after.tick_row["ingress_epoch_ns"], before.tick_row["ingress_epoch_ns"])
    self.assertNotIn("handler_received_monotonic_ns", after.tick_row)
```

- [ ] **Step 2: Run the focused tests and confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage608_continuous_tick_stream
```

Expected: new imports/APIs are missing; existing tests remain green.

- [ ] **Step 3: Implement the exact clock and ingress contracts**

Use these production values and fields:

```python
DEFAULT_INGRESS_QUEUE_CAPACITY = 8192
DEFAULT_WRITER_BATCH_SIZE = 256
DEFAULT_WRITER_FLUSH_SECONDS = 0.050
DEFAULT_SHUTDOWN_DRAIN_SECONDS = 2.0

@dataclass(frozen=True, slots=True)
class DurableTickCursor:
    feed_session_id: str
    ingress_sequence: int

@dataclass(frozen=True, slots=True)
class TickIngressEnvelope:
    feed_session_id: str
    ingress_sequence: int
    symbol_sequence: int
    received_at_utc: str
    ingress_epoch_ns: int
    ingress_monotonic_ns: int
    trace_id: str
    tick_row: Mapping[str, Any]

@dataclass(frozen=True, slots=True)
class TickStreamGap:
    feed_session_id: str
    start_ingress_sequence: int
    end_ingress_sequence: int
    reason: str
```

`SystemClock.epoch_ns()` returns `time.time_ns()`, `monotonic_ns()` returns `time.monotonic_ns()`, and `sleep()` calls `time.sleep()`. `utc_iso_from_epoch_ns()` derives aware UTC from the same epoch value. `capture_ingress()` copies the tick fields before one `queue.put_nowait`; the first `Full` latches a permanent suffix gap and stops journal acceptance for that session. `install_gateway_tick_ingress()` always forwards the tick to the original gateway method and returns an idempotent restore callable. The supported CPython 3.11 wrapper uses an Event flag plus GIL-serialized token add/discard for its short capture lease, not a blocking mutex/Condition; restore disables new captures and polls at most `2s` for already leased captures. The callback still performs no filesystem/flock/JSON/network I/O, mutex wait, or durability wait.

- [ ] **Step 4: Run GREEN and the existing Stage931 backlog control**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage608_continuous_tick_stream \
  tests.test_stage931_trade_fill_accounting.Stage931TradeFillAccountingTest.test_event_engine_backlog_cannot_redate_pre_q2_tick_for_retry_or_close
```

Expected: all selected tests pass; no real sleep/network/order call.

- [x] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/qmt_roll_official_live_time.py \
  examples/portfolio_backtesting/qmt_roll_official_live_tick_stream.py \
  tests/test_stage608_continuous_tick_stream.py
git commit -m "feat(stage608): add bounded gateway tick ingress"
```

---

### Task 2: Add the Async Fsync Writer, Durable Cursor, Recovery, and Stage608 Wiring

**Files:**
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_tick_journal.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_tick_stream.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_tick_types.py`
- Modify: `examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.py`
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_tick_reader.py`
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_tick_recovery.py`
- Modify: `tests/test_stage608_continuous_tick_stream.py`
- Create: `research/lines/futures_trend_stage819_intraday_rules/stages/20260715_1653_stage180_stage179_task2_durable_ingress_candidate.md`

**Interfaces:**
- Consumes: Task 1 envelopes
- Produces: `DurableTickCursor`, `DurableTickSnapshot`, `DurableTickBatch`, `ShutdownReport`, `JournalRecoveryResult`, `AsyncTickJournalWriter`, `TickStreamJournalReader`, `recover_or_isolate_dirty_tail()`, and a Stage608 heartbeat whose old aliases reflect only fsynced rows

- [x] **Step 1: Write RED tests for fsync ordering, writer faults, drain, dirty-tail recovery, and reader bounds**

Add tests named:

```python
def test_fsync_precedes_durable_watermark_and_snapshot_publish(self):
    self.assertEqual(before.durable_ingress_sequence, 0)
    self.assertEqual(before.rows, ())
    self.assertEqual(after.durable_ingress_sequence, 1)

def test_writer_error_latches_fault_and_rejects_ready_heartbeat(self):
    self.assertEqual(snapshot.durable_ingress_sequence, 0)
    self.assertIsNotNone(snapshot.writer_fault)
    self.assertFalse(snapshot.stream_ready)

def test_graceful_shutdown_drains_all_enqueued_ticks_within_two_seconds(self):
    self.assertTrue(report.drained)
    self.assertEqual(report.remaining_queue_depth, 0)
    self.assertEqual(report.durable_through.ingress_sequence, expected_count)

def test_dirty_tail_recovery_isolates_partial_line_and_discloses_gap(self):
    self.assertEqual(result.previous_durable_cursor.ingress_sequence, 7)
    self.assertEqual((result.disclosed_gap.start_ingress_sequence, result.disclosed_gap.end_ingress_sequence), (8, 10))

def test_reader_rejects_cross_session_cursor_and_undurable_tail(self):
    self.assertEqual([row["ingress_sequence"] for row in batch.records], [1, 2])
    self.assertTrue(cross_session.gap is not None)
```

- [x] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage608_continuous_tick_stream
```

Expected: durable writer/recovery APIs are absent.

- [x] **Step 3: Implement commit ordering and Stage608 integration**

The writer owns one journal file descriptor. It batches at `256` rows or `50ms`, writes complete NDJSON, then calls `flush()` and `os.fsync()` before updating the immutable durable snapshot. A failed write/fsync leaves the cursor unchanged, latches a suffix gap from `durable+1`, and permanently revokes readiness for that feed session. `feed_session_id` must be non-empty, valid UTF-8, and at most `256 bytes`; serialized header/commit control records share the `4MiB` single-line ceiling. `journal_write_error` is a soft durability ambiguity rather than proof of permanent data loss: a new feed may clear only that gap after taking the same exclusive segment lock, validating a complete commit frame/hash/sequence, and completing a new durability barrier before exposing the recovered cursor. Queue overflow, shutdown revocation, and partial/corrupt frames remain hard gaps. A failed recovery barrier blocks that attempt without exposing a cursor; a later attempt may retry only by retaking the lock, replaying all validation, and completing a new successful barrier. The framed reader returns only rows `<= durable_through`, rejects cross-session cursors, and treats external cursors as untrusted: it scans from the same descriptor's header through every bounded batch and proves the cursor's complete commit ancestry before resume. This uses bounded `O(batch)` memory but `O(cursor offset)` time; a future constant-time resume needs a new trusted checkpoint/hash-chain schema and Task13 SLA evidence. Atomic tick/heartbeat publication treats opening or fsyncing the parent directory as part of the commit; either failure propagates and must not be reported as a durable success. If the post-replace directory barrier fails, both still-open candidates—the replacement inode and the pre-replace inode that a crash rollback could make visible again—must be truncated and fsynced before propagating the barrier error. This Task 2 contract is process-crash and OS-visible `fsync` consistency, not a macOS sudden-power-loss guarantee: Apple documents that ordinary `fsync` may leave drive caches unordered. Task 13 must benchmark and fault-test `F_BARRIERFSYNC`/`F_FULLFSYNC` on the production filesystem before any stronger durability claim; do not silently switch the hot path primitive without latency evidence.

Dirty-tail isolation uses one immutable redo manifest at `.<journal>.stage179.recovery.json`. The implementation must durably commit the deterministic sidecar and manifest before truncating the source, then revalidate the source inode/size and prefix/tail hashes before `ftruncate + fsync(source) + fsync(parent)`. Restart replays the manifest before ordinary heartbeat/path-size validation and accepts only the same inode at either original size or trusted size. The manifest contains the deterministic transaction id, source identity/hashes, sidecar, previous authority projection, exact recovery result, and complete gap lineage. Replay requires the exact prior authority projection, except that an initialization failure may monotonically revoke `starting/running` to `fault_stopped` only when stopped/unready, writer-dead, and recovery-blocked evidence is present and every non-lifecycle authority field is unchanged. Direct ACK and restart ACK must both reconstruct the recovery result from the manifest and prove that its outer projection exactly equals the result inside the transaction-id core before evaluating successor-heartbeat gap coverage or deleting redo authority. The manifest remains active until either a new `starting/unready` H1 or its durably committed monotonic `fault_stopped`/`recovery_required_stopped` successor proves the same transaction id, manifest path, and complete gaps from disk; a stopped successor must also be unready, non-clean, and writer-dead. Under the journal lock, ACK must re-prove sidecar/manifest bytes and identity, require the source to be the same inode already truncated to `trusted_end` with its trusted prefix hash intact, byte-recheck the heartbeat across its barrier, and re-read the same heartbeat and manifest identity immediately before unlink. Only replay may accept `original_size`; only after these ACK proofs may the manifest be unlinked and its parent fsynced. The dirty sidecar remains as audit evidence.

In Stage608:

```python
ctp_gateway = main_engine.add_gateway(CtpGateway)
pipeline = TickStreamPipeline(
    feed_session_id=feed_session_id,
    journal_segment_path=journal_segment_path,
    clock=SYSTEM_CLOCK,
    queue_capacity=8192,
    max_buffer_ticks=max_buffer_ticks,
    writer_batch_size=256,
    writer_flush_seconds=0.050,
)
restore_gateway = install_gateway_tick_ingress(ctp_gateway, pipeline)
```

The EVENT_TICK handler calls only `pipeline.observe_handler(event.data)`. Heartbeat publication reads `pipeline.durable_snapshot()`. Both the one-shot snapshot probe and stream place every pre-authority initialization step—module import/callback patch, EventEngine, MainEngine, gateway, guards, pipeline, event handlers, and signal handlers—inside one rollback boundary; any failure revokes heartbeat readiness and closes all resources created so far. Stream lifecycle uses a `startup_handoff` guard before H1 and clears it only after the on-disk `starting/unready` heartbeat has been reread, any recovery manifest has been ACKed, and before CTP connect. It durably writes `terminal_commit` before any teardown, then monotonically refreshes `capture_quiesced`, `writer_quiesced`, and `pipeline_quiesced`; clearing requires all three, stopped/unready durability, and signal restoration. If no valid terminal fence can be persisted while any resource remains unquiesced, the process calls `os._exit(2)` while still holding the owner lock instead of unwinding it. A new owner may reconcile an identity-consistent dead-owner guard under the owner lock, but before clearing it must durably rewrite every starting/running, stale clean, ready/transport-ready, writer-alive, accepting, or otherwise not-safely-fault-stopped authority as fault-stopped, unready, stopped, writer-dead, non-accepting, and recovery-blocked. Only an already consistent fault/recovery-required stop may be consumed without another rewrite; corrupt or mismatched guards remain blocking. Any unproved quiescence field requires the old PID to be definitely gone. Even with no guard, a stale running/ready authority from an ordinary process crash is fenced and durably revoked before journal recovery, initialization, or CTP connect; that revoke guard is bound to the prior authority's feed/session and revision so a crash after the fault heartbeat but before guard deletion is reconcilable on restart. A revoke-write or guard-clear failure remains restart-recoverable and cannot advance to recovery/connect. Atomic publication preopens the parent directory before replace; barrier plus invalidation double failure is reported as authority unsafe and preserves the guard. The one-shot snapshot probe wraps both TD and MD close with at-most-once entered/completed fences. Stream shutdown keeps both ingress and order guards installed while it stops acceptance, directly closes the non-idempotent MD API once, makes any second native MD close inert through connection state and method replacement, wraps TD close with an at-most-once entered/completed fence, and then runs aggregate `main_engine.close()` so any late gateway callback is still captured or rejected. If aggregate close short-circuits before the gateway, fallback continues EventEngine/engine/TD/MD teardown and invokes each native close at most once; a partial native close failure is recorded and never retried. Restore the order guard only after aggregate close and a successful gateway capture fence; timeout keeps both order and lifecycle guards, records fault, and exits `2`. Then drain the writer for up to `2s` and complete the final fsync. The final `clean_stopped` decision and heartbeat must come from the same durable terminal snapshot and prove committed authority, framed schema/byte cursor consistency, no gap/fault/drop, an empty queue, a stopped writer, disabled acceptance, and `last_ingress_sequence == durable_ingress_sequence`; any contradiction downgrades to `fault_stopped` and exit code `2`. Publish stopped/unready durably before restoring the original SIGTERM/SIGINT handlers. A signal-restore error republishes `fault_stopped`; restoring defaults must never reopen a ready/running termination window. If the first MD close or its fence is uncertain, skip the unsafe aggregate gateway retry, close the remaining Python/EventEngine/TD resources separately, and remain fault-stopped.

Task 2 may publish additive per-symbol durable/first-buffered/evicted-through watermarks, but they are producer-side prewiring only. They do not authorize or block trading until Task 3 adds and verifies the Stage904 consumer gate. Preserve `_run_stream` signature, old paths, model tag, schema-v1 snapshot commit, and aliases `stream_sequence`, `symbol_stream_sequence`, and `received_at`.

- [x] **Step 4: Run GREEN**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage608_continuous_tick_stream
```

Expected: existing and new Stage608 tests pass; send/cancel counters remain 0.

- [x] **Step 5: Commit after the reopened exact-diff review reports `P0=0, P1=0`**

```bash
git add docs/superpowers/plans/2026-07-14-stage179-live-execution-latency-reliability.md \
  docs/superpowers/specs/2026-07-14-stage179-live-execution-latency-reliability-design.md \
  examples/portfolio_backtesting/qmt_roll_official_live_tick_journal.py \
  examples/portfolio_backtesting/qmt_roll_official_live_tick_reader.py \
  examples/portfolio_backtesting/qmt_roll_official_live_tick_recovery.py \
  examples/portfolio_backtesting/qmt_roll_official_live_tick_stream.py \
  examples/portfolio_backtesting/qmt_roll_official_live_tick_types.py \
  examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.py \
  tests/test_stage608_continuous_tick_stream.py \
  research/lines/futures_trend_stage819_intraday_rules/stages/20260715_1813_stage181_stage179_task2_followup_crash_consistency.md
git commit -m "fix(stage608): harden durable readonly lifecycle"
```

---

### Task 3: Consume Target-Symbol Eviction Even When Its Ring Frame Is Empty

**Files:**
- Read/verify only: `examples/portfolio_backtesting/qmt_roll_official_live_tick_stream.py`
- Read/verify only: `examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`
- Read/verify only: `tests/test_stage608_continuous_tick_stream.py`
- Modify: `tests/test_stage904_durable_state_integration.py`

**Interfaces:**
- Consumes: per-symbol durable and eviction watermarks
- Produces: exact `tick_target_symbol_evicted_before_consume` fail-close evidence

- [x] **Step 1: Verify the Task 2 producer contract, then write the Stage904 RED test**

Task 2 already owns and verifies the producer-side contract:

```python
def test_durable_ring_capacity_records_per_symbol_eviction(self):
    self.assertEqual(watermark.evicted_through_symbol_sequence, 1)
    self.assertEqual(watermark.first_buffered_symbol_sequence, 0)
    self.assertEqual(watermark.durable_symbol_sequence, 1)

# New Task 3 RED test:
def test_target_symbol_evicted_from_global_ring_latches_feed_gap_even_when_target_frame_empty(self):
    self.assertEqual(result["feed_gap_latched"], 1)
    self.assertIn("tick_target_symbol_evicted_before_consume", result["feed_gap_reason"])
```

- [x] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage608_continuous_tick_stream \
  tests.test_stage904_durable_state_integration.Stage904DurableStateIntegrationTest.test_target_symbol_evicted_from_global_ring_latches_feed_gap_even_when_target_frame_empty
```

Expected: the existing Stage608 producer watermark test is GREEN; only the Stage904 consumer test is RED because the gate is missing.

- [x] **Step 3: Implement only the Stage904 consumer gate**

Read Task 2's existing `durable_symbol_sequence`, `first_buffered_symbol_sequence`, and `evicted_through_symbol_sequence` fields without changing their producer semantics. Before generic missing-row handling, Stage904 compares `evicted_through` with the state's last consumed sequence and returns:

```python
return (
    f"tick_target_symbol_evicted_before_consume:{vt_symbol};"
    f"feed={feed_session_id};last_consumed={last_consumed};"
    f"evicted_through={evicted_through}"
)
```

- [x] **Step 4: Run GREEN including interleaving controls**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage608_continuous_tick_stream \
  tests.test_stage904_durable_state_integration
```

Expected: target eviction fails closed; existing JM/RB/JM interleaving does not create a false gap.

- [x] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py \
  tests/test_stage904_durable_state_integration.py
git commit -m "fix(stage904): latch evicted target tick gaps"
```

- [x] **Step 6: Close the reviewer-discovered implicit-legacy downgrade**

The first Task 3 review reproduced a wall-clock rollback counterexample: with the adverse target tick already evicted, a retained pre-entry tick followed by a favorable tick could pass because all three eviction fields being absent implicitly selected the legacy fallback. Add a producer-declared exact-integer `symbol_eviction_watermark_schema_version=1`; make the official Stage904 path require it by default; fail closed on missing, invalid, unsupported, partial, or incoherent evidence. The only compatibility bypass is an internal offline argument defaulting to `False`; Stage930 and the official CLI expose no switch. Keep the counterexample, exact-boundary, interleaving, producer declaration, and validation-matrix tests. Commit the correction separately as `fix(stage904): require eviction watermark capability` after independent review.

- [x] **Step 7: Close the persisted-state capability laundering gap**

The second adversarial review proved that a current v1 heartbeat did not invalidate an old `initial_progress_latched` or `retry_reclaim_latched` state. Persist auditable transition provenance atomically with every progress/reclaim risk authorization; bind it to the exact state identity, transition row, feed, committed snapshot generation, heartbeat revision, target-symbol cursor range, and triggering symbol sequence. The checksum is an internal consistency/tamper cross-link, not source authentication. In production, missing/legacy/tampered provenance must emit a P1 manual migration blocker with no risk-increasing identity. Stage904 must emit canonical numeric `manual_intervention_required=0/1` on every action. Stage905 must propagate the manual/migration/P0/P1 evidence, require canonical flags plus the exact existing role/action identity and exact retry-open monitor state, bind source/target/run/identity into the order payload, and fail closed on every abnormal open. Stage931 live-real must cross-bind every ready row to the payload before any close-only or Stage927 override, independently re-read a fresh same-run Stage904 summary both at selection and immediately before every retry-open child `send_order`, and revalidate canonical flags, exact action identity, and actual broker-request offset instead of trusting a stale or relabelled Stage905/Stage927 snapshot across CTP/O-P-O/reprice waits. Once the selected set itself strictly proves close-only, artifact corruption in unrelated opens must not starve that risk-reducing cycle; normal/open cycles still validate the full artifact. Preserve close-only handling for an already exposed unproven `retry_open`, and never block the existing risk-reducing close phases. Add realistic old-feed-to-new-feed, same-feed laundering, restart round-trip, transition/copy/tamper matrix, retained-range, snapshot-generation, producer-consumer schema, row-payload masquerade, Stage931 rebind/TOCTOU, and close-only isolation regressions. Do not mark this step complete until the frozen current diff receives an independent P0/P1 review and the activation preflight requirement is carried into the deployment gate.

---

### Task 4: Add the Deterministic Trace Schema and Virtual-Clock SLA Evaluator

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_trace.py`
- Create: `tests/test_official_live_trace.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_time.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_tick_types.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_tick_stream.py`
- Modify: `tests/test_stage608_continuous_tick_stream.py`

**Interfaces:**
- Consumes: canonical ingress rows and `Clock`
- Produces: `TraceStage`, `ClockStamp`, `LatencyTrace`, `SlaBudget`, `SlaEvaluation`, deterministic trace IDs, serialization, and exact deadline disposition

- [x] **Step 1: Write the complete RED contract**

```python
def test_virtual_clock_expires_at_exact_25_second_boundary(self):
    self.assertEqual(disposition_at(24_999_999_999, "open"), "ready")
    self.assertEqual(disposition_at(25_000_000_000, "open"), "expired")
    self.assertEqual(disposition_at(25_000_000_000, "close"), "blocked")

def test_missing_required_stamp_is_ineligible_not_pass(self):
    self.assertEqual(result.status, "missing_timestamp")
    self.assertFalse(result.eligible)
    self.assertFalse(result.passed)

def test_trace_round_trip_preserves_integer_nanoseconds(self):
    self.assertIsInstance(restored.stamps["gateway_ingress"].epoch_ns, int)
    self.assertEqual(restored, original)

def test_clock_domain_change_fails_closed(self):
    self.assertEqual(open_disposition, "expired")
    self.assertEqual(close_disposition, "blocked")
```

- [x] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_official_live_trace
```

Expected: module/API missing.

- [x] **Step 3: Implement the schema and exact budgets**

Define stages `gateway_ingress`, `journal_durable`, `stage904_detected`, `stage905_intent_ready`, `spool_committed`, `executor_dequeued`, `broker_bundle_ready`, `send_order_called`, `first_broker_ack`, `first_fill`, `cancel_requested`, `cancel_terminal`, `ledger_durable`, and diagnostic `event_handler_observed`. `trace_id` is UUIDv5 over `feed_session_id:ingress_sequence`; `deadline_epoch_ns` and same-domain monotonic deadline equal ingress plus `25_000_000_000` ns. A repeated identical stamp is idempotent; a different repeated stamp, negative cursor, naïve UTC, tampered deadline, or monotonic rollback raises `TraceValidationError`.

Install the exact approved `SLA_BUDGETS`; missing required endpoints are ineligible failures, and conditional fill/cancel segments are not applicable when the event never occurred.

Stage608 must persist the boot-stable `clock_domain_id` in the canonical ingress envelope and row. Before any tick bytes are written, the writer cross-binds the pipeline, envelope, and row domain with exact type/value checks. The Task 4 trace is an internal-consistency and audit-latency schema, not source authentication: a cross-domain stamp is always live-ineligible. Task 5 must persist the complete trigger cursor and state generation; Task 8 must validate producer generation, heartbeat/commit lineage, and the durable cursor before accepting downstream stamps. The adversarial forward-domain sample remains a mandatory Task 5/8 regression, and Stage179 cannot activate until that Spec 5.5 lineage is closed.

- [x] **Step 4: Run GREEN**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_official_live_trace
```

Expected: all trace tests pass without real sleep.

- [x] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/qmt_roll_official_live_time.py \
  examples/portfolio_backtesting/qmt_roll_official_live_trace.py \
  tests/test_official_live_trace.py
git commit -m "feat(stage179): add auditable trace and SLA schema"
```

Implemented as `c17a3b897acf944c358d12118071557789ac9d9e`; final relevant verification was `171/171`, with independent review `P0=0`, `P1=0` and conservative aggregate `P2=2`. This commit is merge eligible only; it does not authorize deployment or activation.

---

### Task 5: Persist the Trigger Cursor and Expose Stage904 as a Deterministic Callable

**Files:**
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_c9_intraday_state.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`
- Modify: `tests/test_official_live_c9_intraday_state.py`
- Modify: `tests/test_stage904_durable_state_integration.py`

**Interfaces:**
- Consumes: `DurableTickBatch`, canonical trace/cursor fields, and existing Stage904 state WAL
- Produces: `Stage904RunResult` and a `run_intraday_monitor` callable, while the original CLI writes the same outputs

- [x] **Step 1: Write RED tests for first-trigger identity, durable-batch input, and state-before-return ordering**

```python
def test_trigger_action_preserves_gateway_cursor_and_deadline_across_replay(self):
    self.assertEqual(replayed["action_id"], first["action_id"])
    self.assertEqual(replayed["trace_id"], first["trace_id"])
    self.assertEqual(replayed["source_ingress_sequence"], trigger_sequence)
    self.assertEqual(replayed["deadline_epoch_ns"], trigger_epoch_ns + 25_000_000_000)

def test_durable_batch_path_never_reads_compat_tick_csv(self):
    self.assertEqual(result.summary["order_api_called_count"], 0)
    self.assertGreaterEqual(len(result.actions), 1)

def test_state_wal_is_committed_before_callable_returns_action(self):
    self.assertEqual(recovered_pending_action["action_id"], result.actions.iloc[0]["action_id"])
```

- [x] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_official_live_c9_intraday_state \
  tests.test_stage904_durable_state_integration
```

Expected: cursor/trace fields and callable are absent.

- [x] **Step 3: Implement the callable without duplicating the reducer**

Add immutable result type:

```python
@dataclass(frozen=True)
class Stage904RunResult:
    target_date: str
    monitor_run_id: str
    actions: pd.DataFrame
    summary: dict[str, Any]
    paths: Mapping[str, Path]
```

`run_intraday_monitor(target_date="", max_tick_age_seconds=10, require_broker_fill_price=False, durable_batch=None, clock=SYSTEM_CLOCK, write_compat_outputs=True)` owns the former `main()` body. When `durable_batch` is present it never calls `_read_committed_tick_snapshot`; otherwise it preserves the H1/bytes/H2 compatibility path. State transition/pending-action data retain `trace_json`, `trace_id`, source feed/ingress/symbol sequences, ingress epoch/monotonic times, the original 25-second deadline, and `state_generation=position_epoch_id:state_revision`. Later ticks and a new monitor run ID cannot overwrite those trigger fields. The state journal/snapshot commit completes before returning a ready action.

The durable path additionally requires `caught_up=True` and `next_cursor == durable_through`, retains the complete framed-v1 batch commit cursor separately from the trigger row identity, and uses strict `LatencyTrace` parsing plus state-transition cross-binding before any retry-open pending action exists. Missing or legacy trigger provenance never blocks a risk-reducing close, but it produces no retry open and emits a P1 migration blocker. Exact integer nanoseconds and byte offsets are rebuilt as object columns from the original action rows so mixed traced/watch results cannot pass through float64.

The existing `main()` parses the same flags, calls this function, and prints the same summary JSON. It does not add order capability.

- [x] **Step 4: Run GREEN**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_official_live_c9_intraday_state \
  tests.test_stage904_durable_state_integration
```

Expected: all selected tests pass and existing action IDs remain stable.

- [x] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/qmt_roll_official_live_c9_intraday_state.py \
  examples/portfolio_backtesting/run_qmt_roll_stage904_official_live_c9_intraday_monitor.py \
  tests/test_official_live_c9_intraday_state.py \
  tests/test_stage904_durable_state_integration.py
git commit -m "refactor(stage904): expose durable intraday monitor callable"
```

Implemented as `334349d7c4a7384102f1e202361850e67059f6d8`; final relevant verification was `221/221`, with independent review `P0=0`, `P1=0`, `P2=1`. Task 8 must still bind the durable batch and heartbeat generation as one detector-cycle input; until then this is merge eligible only and cannot activate Stage179.

---

### Task 6: Expose Stage905 as an In-Memory Builder and Enforce the Absolute Deadline

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py`
- Modify: `tests/test_stage905_c9_cycle_intents.py`

**Interfaces:**
- Consumes: an in-memory `Stage904RunResult`, snapshot inputs, Task 4 traces, and the injected clock
- Produces: `Stage905SnapshotInputs`, `Stage905RunResult`, and a `run_executor_dry_run` callable; CLI compatibility remains

- [ ] **Step 1: Write RED tests**

```python
def test_stage904_trace_deadline_and_state_generation_are_preserved(self):
    self.assertEqual(intent["trace_id"], action["trace_id"])
    self.assertEqual(intent["deadline_epoch_ns"], action["deadline_epoch_ns"])
    self.assertEqual(intent["state_generation"], action["state_generation"])

def test_virtual_deadline_marks_open_expired_and_close_blocked(self):
    self.assertEqual(open_intent["executor_status"], "expired")
    self.assertEqual(close_intent["executor_status"], "blocked")
    self.assertNotEqual(close_intent["executor_status"], "dry_run_order_request_payload_ready")

def test_in_memory_stage904_result_does_not_read_stage904_files(self):
    self.assertEqual(result.summary["send_order_api_called_count"], 0)
```

- [ ] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage905_c9_cycle_intents
```

Expected: callable/deadline behavior missing.

- [ ] **Step 3: Implement the deterministic builder**

Add:

```python
@dataclass(frozen=True)
class Stage905SnapshotInputs:
    pending_orders: pd.DataFrame
    contracts: pd.DataFrame
    positions: pd.DataFrame
    orders: pd.DataFrame
    stage902_summary: Mapping[str, Any]
    stage260_summary: Mapping[str, Any]
    execution_ledger_rows: Sequence[Mapping[str, Any]]

@dataclass(frozen=True)
class Stage905RunResult:
    intents: pd.DataFrame
    summary: dict[str, Any]
    paths: Mapping[str, Path]
```

`run_executor_dry_run(target_date, mode="dry-run", stage904_actions=None, stage904_summary=None, snapshots=None, include_stage901_pending=True, clock=SYSTEM_CLOCK, write_compat_outputs=True)` owns the former `main()` body. In-memory actions/summary prevent file reads. Detector callers use `include_stage901_pending=False`; initial opens stay on the legacy path until the warm executor task. `_stage904_intents` passes every trace/cursor/deadline field unchanged. At `now >= deadline`, open is expired and close is blocked/critical; neither is ready. Stable payload hashing excludes monitor-run/generated/check timestamps.

The CLI retains required `--target-date`, `--mode dry-run`, output names/model tag, fail-closed clearing, and stdout JSON.

- [ ] **Step 4: Run GREEN**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage905_c9_cycle_intents \
  tests.test_stage904_durable_state_integration
```

Expected: all selected tests pass; order counters are 0.

- [ ] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py \
  tests/test_stage905_c9_cycle_intents.py
git commit -m "refactor(stage905): build traced intents in memory"
```

---

### Task 7: Add the SQLite WAL Close-Priority Intent Spool

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_intent_spool.py`
- Create: `tests/test_official_live_intent_spool.py`

**Interfaces:**
- Consumes: stable Stage905 intent payloads and `DurableTickCursor`
- Produces: schema-v1 WAL/FULL spool, atomic detector cursor CAS, close-first leases, deadline transitions, and socket notification

- [ ] **Step 1: Write RED tests for schema, atomicity, conflict, priority, deadline, lease recovery, concurrency, and socket loss**

```python
def test_open_spool_enforces_wal_full_and_schema_v1(self):
    self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
    self.assertEqual(connection.execute("PRAGMA synchronous").fetchone()[0], 2)
    self.assertEqual(meta["schema_version"], "1")

def test_commit_batch_atomically_inserts_intents_and_advances_cursor(self):
    self.assertEqual(read_detector_cursor(connection, consumer_id="stage941"), next_cursor)
    self.assertEqual(spool_counts(connection)["ready"], 1)

def test_newer_close_is_leased_before_older_open(self):
    self.assertEqual(lease.intent.priority, 0)

def test_exact_deadline_expires_open_and_blocks_close_critical(self):
    self.assertEqual((expired_open_count, blocked_close_count), (1, 1))

def test_missing_socket_does_not_rollback_and_poll_scan_recovers(self):
    self.assertFalse(notified)
    self.assertEqual(reopened_counts["ready"], 1)
```

- [ ] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_official_live_intent_spool
```

Expected: spool module missing.

- [ ] **Step 3: Implement the exact schema and transaction rules**

Open each process/thread connection using `sqlite3.connect(path, timeout=0.1, isolation_level=None)`, then enforce `journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`, and `busy_timeout=100`. Create `spool_meta`, `detector_cursors`, and `intents`; intent states are `ready`, `leased`, `sending`, `side_effect_unknown`, `sent`, `reconciled`, `expired`, and `blocked`. Priority is exactly close `0`, open `1`.

Expose `open_spool`, `initialize_spool`, `read_detector_cursor`, `commit_detector_batch`, `lease_next`, `recover_expired_lease`, `transition_intent`, `expire_due_intents`, `spool_counts`, `wakeup_socket_path`, and `notify_executor`. Every write uses explicit `BEGIN IMMEDIATE`/commit/rollback. Insert and cursor CAS happen in one transaction. An identical `intent_id + payload_sha256 + trace_id` replay is idempotent; any same-ID mismatch raises `SpoolConflictError` and leaves the cursor unchanged. Any outstanding close in ready/leased/sending/unknown/blocked prevents leasing an open. Expired leases requeue only with explicit ledger disposition `no_side_effect`; unknown or side-effect evidence blocks. Socket notification never controls transaction success.

- [ ] **Step 4: Run GREEN and repeat the two-connection claim race**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_official_live_intent_spool
```

Expected: all spool tests pass; exactly one lease winner.

- [ ] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/qmt_roll_official_live_intent_spool.py \
  tests/test_official_live_intent_spool.py
git commit -m "feat(stage179): add WAL priority intent spool"
```

---

### Task 8: Add the Default-Off Persistent Stage941 Detector and Stage930 Ownership

**Files:**
- Create: `examples/portfolio_backtesting/run_qmt_roll_stage941_official_live_c9_detector.py`
- Create: `tests/test_official_live_c9_detector.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
- Modify: `tests/test_stage930_fast_lane.py`

**Interfaces:**
- Consumes: Task 2 durable reader, Task 5/6 callables, Task 7 spool
- Produces: `DetectorConfig`, `DetectorCycleResult`, `run_detector_once`, `serve_detector`, and a Stage930-owned child whose default mode remains legacy

- [ ] **Step 1: Write RED detector and supervisor tests**

```python
def test_state_commit_happens_before_spool_commit(self):
    self.assertLess(events.index("stage904_wal_fsync"), events.index("spool_begin"))
    self.assertLess(events.index("spool_begin"), events.index("spool_commit"))

def test_crash_after_state_commit_before_spool_replays_once(self):
    self.assertEqual(spool_counts(connection)["ready"], 1)
    self.assertEqual(read_detector_cursor(connection, consumer_id="stage941"), expected_cursor)

def test_gap_or_writer_fault_never_advances_cursor_or_ready_open(self):
    self.assertEqual(result.cursor_after, result.cursor_before)
    self.assertEqual(result.ready_count, 0)

def test_persistent_mode_never_spawns_stage904_or_stage905_subprocess(self):
    self.assertEqual(run_command_calls, [])

def test_persistent_mode_with_live_submit_fails_closed_before_child_start(self):
    self.assertIn("persistent_detector_requires_warm_executor_and_runtime_profile", blockers)
    self.assertEqual(managed_popen_calls, 0)
```

- [ ] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_official_live_c9_detector \
  tests.test_stage930_fast_lane
```

Expected: Stage941 and new mode are absent.

- [ ] **Step 3: Implement the detector transaction order and Stage930 mode gate**

`run_detector_once` reads heartbeat/durable cursor, calls `TickStreamJournalReader.read_after`, validates each trace, runs Stage904 with `write_compat_outputs=False`, then Stage905 with in-memory inputs and `include_stage901_pending=False`. Only after Stage904 state WAL is durable does it atomically insert intents and advance the spool cursor. SQLite commit precedes `spool_committed` trace, socket wakeup, and compatibility output publication. A crash before spool commit leaves the old cursor for deterministic replay. Gap/writer fault leaves cursor unchanged and produces no ready open. SIGTERM completes or rolls back the current transaction, then publishes stopped/unready.

Stage930 adds `--detector-mode legacy-subprocess|persistent` defaulting to `legacy-subprocess`, plus poll/batch/restart settings. Persistent mode is permitted only with `mode=dry-run` and `submit-mode=disabled` until Tasks 10–11. Stage930 starts tick stream → detector → AI preflight, owns the process via `_managed_popen`, bounds restarts, rejects old heartbeat reuse, and terminates it in the common process-group shutdown. In persistent mode the fast lane reads detector heartbeat/spool counts and never spawns Stage904/905; legacy behavior remains unchanged. No plist changes occur in this task.

- [ ] **Step 4: Run GREEN and the related detector chain**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_official_live_trace \
  tests.test_official_live_c9_intraday_state \
  tests.test_stage904_durable_state_integration \
  tests.test_stage905_c9_cycle_intents \
  tests.test_official_live_intent_spool \
  tests.test_official_live_c9_detector \
  tests.test_stage930_fast_lane
```

Expected: all tests pass; persistent path remains no-submit.

- [ ] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/run_qmt_roll_stage941_official_live_c9_detector.py \
  examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py \
  tests/test_official_live_c9_detector.py \
  tests/test_stage930_fast_lane.py
git commit -m "feat(stage930): own default-off persistent detector"
```

---

### Task 9: Add Typed Runtime Profiles, Immutable Release Validation, and Default-Off Activation

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_runtime_profile.py`
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_release_manifest.py`
- Create: `examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py`
- Create: `tests/test_stage179_runtime_profile.py`
- Create: `tests/test_stage179_release_manifest.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_phase_d_config.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage914_official_live_ctp_runtime_preflight.py`

**Interfaces:**
- Consumes: requested runtime/order scope and a release manifest path
- Produces: `ExecutionRuntimeProfile`, `OrderScope`, `ResolvedRuntimeProfile`, profile/environment isolation, manifest validation, and a production-live blocker before any adapter import

- [ ] **Step 1: Write RED profile, manifest, and default-off tests**

```python
def test_production_live_default_off_stops_before_adapter_import(self):
    self.assertIn("stage179_activation_disabled", blockers)
    self.assertEqual(adapter_factory_calls, 0)

def test_policy_conflict_blocks_even_with_env_and_confirm(self):
    self.assertIn("operator_policy_conflict_unresolved", blockers)

def test_production_framework_order_requires_formal_vnpy_ctp_first(self):
    self.assertTrue(str(resolved.framework_path[0]).endswith("vnpy_ctp/api/libs"))

def test_runtime_roots_reject_resolved_alias_with_production_state(self):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        production_state = root / "production-state"
        production_state.mkdir()
        candidate_alias = root / "candidate-alias"
        candidate_alias.symlink_to(production_state, target_is_directory=True)
        with self.assertRaises(RuntimeProfileError):
            resolve_runtime_profile(
                profile=ExecutionRuntimeProfile.OFFLINE,
                order_scope=OrderScope.NONE,
                output_root=candidate_alias,
                protected_production_roots=(production_state,),
            )

def test_manifest_rejects_critical_file_digest_version_capital_or_capability_tamper(self):
    for mutation in mutations:
        with self.assertRaises(ReleaseManifestError):
            load_and_validate_release_manifest(mutation.path, **expected)
```

- [ ] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage179_runtime_profile \
  tests.test_stage179_release_manifest
```

Expected: runtime/manifest modules missing.

- [ ] **Step 3: Implement exact profile isolation and manifest validation**

Define profiles `offline`, `production-readonly`, `simnow`, `broker-test`, and `production-live`, with order scopes `none`, `readonly`, `test`, and `live`. `resolve_runtime_profile` accepts the requested `profile`, `order_scope`, optional `output_root`, and `protected_production_roots`; it resolves every path before checking isolation. Env mapping is exact: production profiles use `ctp_live.local.env`; SimNow uses `ctp_simnow.local.env`; broker-test uses `ctp_broker_test.local.env`; offline uses none. Production framework path puts `vnpy_ctp/api/libs` before `.py311/lib`. Every profile has distinct resolved output/state/spool/ledger/readiness paths; symlink or `..` aliasing into production state is rejected. No secret value is logged.

Release manifests include schema, release ID, official version, capital/label, source commit, sorted critical-file hashes, tree fingerprint, ledger schema/fingerprint versions/reader capabilities, allowed runtime profiles, UTC creation time, and a digest over all fields except the digest. Validation compares exact bytes, version, capital, profile, commit ancestry, and V2 reader capability. Builder requires a clean tree and refuses to overwrite different content.

Add exact gates:

```python
STAGE179_ACTIVATION_ENV = "OFFICIAL_LIVE_STAGE179_WARM_EXECUTOR_ENABLED"
STAGE179_ACTIVATION_CONFIRM_TEXT = (
    "I_UNDERSTAND_THIS_ACTIVATES_STAGE179_WARM_CTP_EXECUTION"
)
```

Production-live requires profile, valid manifest, env=1, exact CLI confirmation, original Phase-D real-submit gates, Stage927, kill switch, fresh broker gates, and a separate activation receipt pinned to manifest/version/capital/policy decision. Do not create that receipt. The current profile-policy conflict always adds `operator_policy_conflict_unresolved`. Offline, production-readonly, and submit-disabled canary paths do not require a receipt.

- [ ] **Step 4: Run GREEN and preflight-only checks**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage179_runtime_profile \
  tests.test_stage179_release_manifest
```

Expected: all tests pass before adapter import; no env is sourced.

- [ ] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/qmt_roll_official_live_runtime_profile.py \
  examples/portfolio_backtesting/qmt_roll_official_live_release_manifest.py \
  examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py \
  examples/portfolio_backtesting/qmt_roll_official_live_phase_d_config.py \
  examples/portfolio_backtesting/run_qmt_roll_stage914_official_live_ctp_runtime_preflight.py \
  tests/test_stage179_runtime_profile.py \
  tests/test_stage179_release_manifest.py
git commit -m "feat(stage179): add runtime and release activation gates"
```

---

### Task 10: Extract a Generation-Bound Warm Stage931 Session and Executor Service

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_live_execution_service.py`
- Create: `tests/test_stage179_executor_serve.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_phase_d_config.py`
- Modify: `tests/test_stage931_ctp_readiness.py`
- Modify: `tests/test_stage931_post_reprice_final_gate.py`
- Modify: `tests/test_stage931_trade_fill_accounting.py`

**Interfaces:**
- Consumes: Task 7 spool leases, Task 9 resolved runtime, existing Stage931 gates, and execution ledger
- Produces: `TdReadinessLease`, `CtpExecutionSession`, `ExecutorServicePaths`, `ExecutionResult`, atomic readiness publication, and a warm serve loop; one-shot is preserved

- [ ] **Step 1: Write RED tests for connection reuse, generation, deadlines, and compatibility**

```python
def test_serve_reuses_one_ctp_connection_for_two_intents_but_runs_two_fresh_bundles(self):
    self.assertEqual(fake_backend.connect_calls, 1)
    self.assertEqual(fake_backend.fresh_bundle_calls, 2)

def test_old_connection_generation_lease_cannot_authorize_send_after_reconnect(self):
    self.assertIn("connection_generation_mismatch", result.blockers)
    self.assertEqual(result.send_order_call_count, 0)

def test_absolute_25s_intent_deadline_blocks_before_api_slot_and_send(self):
    self.assertIn("stage179_execution_deadline_exceeded", result.blockers[0])
    self.assertEqual((ledger_api_slot_count, result.send_order_call_count), (0, 0))

def test_existing_one_shot_cli_remains_backward_compatible_without_command_flag(self):
    self.assertEqual(parsed.command, "once")
    self.assertEqual(parsed.target_date, "2026-07-14")
```

- [ ] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage179_executor_serve \
  tests.test_stage931_ctp_readiness \
  tests.test_stage931_post_reprice_final_gate
```

Expected: warm service APIs missing; existing tests remain green.

- [ ] **Step 3: Extract the session and serve loop without weakening final gates**

`TdReadinessLease` contains service generation, connection generation, runtime profile, official version/capital, issue/expiry epoch ns, and last complete startup-bundle epoch. `CtpExecutionSession.connect` completes authentication/login/settlement/contract/account/position setup. Disconnect revokes memory and disk readiness immediately; reconnect creates a new generation and invalidates every old lease.

Every leased intent still runs fresh `_final_pre_send_snapshot_epoch`, Q2 causal tick, `_post_reprice_final_state_gate`, and `_post_final_gate_pre_api_slot_blockers`. All waits accept one shared monotonic hard deadline derived from the earlier absolute 25-second ingress deadline and the 20-second dequeue budget. If any phase reaches the boundary, it returns `stage179_execution_deadline_exceeded:<phase>` before API-slot reservation.

The service holds a singleton lock, atomically publishes readiness using temp+fsync+replace+parent-fsync, listens to the socket, and also polls every `0.1s`. State progression is ready→leased→sending→sent→reconciled. Late open becomes expired; late close becomes blocked/critical. It does not invent a late successor. `parse_args` adds `--command once|serve` default `once`; old one-shot flags and output behavior remain.

- [ ] **Step 4: Run GREEN across the original Stage931 gates**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage179_executor_serve \
  tests.test_stage931_ctp_readiness \
  tests.test_stage931_post_reprice_final_gate \
  tests.test_stage931_trade_fill_accounting
```

Expected: warm fake connection is reused, every intent gets fresh gates, and original accounting tests pass.

- [ ] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/qmt_roll_official_live_execution_service.py \
  examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py \
  examples/portfolio_backtesting/qmt_roll_official_live_phase_d_config.py \
  tests/test_stage179_executor_serve.py \
  tests/test_stage931_ctp_readiness.py \
  tests/test_stage931_post_reprice_final_gate.py \
  tests/test_stage931_trade_fill_accounting.py
git commit -m "refactor(stage931): add generation-bound warm executor"
```

---

### Task 11: Make Spool/Ledger Crash Recovery Atomic and Let Stage930 Own Warm Stage931

**Files:**
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_execution_service.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
- Modify: `tests/test_official_live_execution_ledger_cycles.py`
- Modify: `tests/test_stage179_executor_serve.py`
- Modify: `tests/test_stage930_fast_lane.py`

**Interfaces:**
- Consumes: spool lease owner/token, Stage931 service/connection generations, existing ledger reservation/API-slot evidence
- Produces: `LedgerRecoveryDecision`, `recover_expired_spool_lease`, at-most-once recovery, and Stage930 warm/legacy execution modes

- [ ] **Step 1: Write RED crash-boundary and Stage930 ownership tests**

```python
def test_crash_after_reservation_before_api_slot_appends_safe_terminal_once(self):
    self.assertEqual(decision.disposition, "requeue_pre_send")
    self.assertEqual(event_types.count("spool_crash_recovery_pre_send_safe_terminal"), 1)

def test_api_slot_without_send_is_reconcile_only_unknown(self):
    self.assertEqual(decision.disposition, "reconcile_only_side_effect_unknown")

def test_two_executor_processes_and_ledger_cas_create_one_child_winner(self):
    self.assertEqual(sum(send_results), 1)

def test_warm_mode_reuses_one_stage931_child_across_cycles(self):
    self.assertEqual(stage931_child_starts, 1)
    self.assertEqual(legacy_stage931_runs, 0)
```

- [ ] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_official_live_execution_ledger_cycles \
  tests.test_stage179_executor_serve \
  tests.test_stage930_fast_lane
```

Expected: spool recovery and warm owner modes missing.

- [ ] **Step 3: Implement one-lock recovery and Stage930 mode selection**

Add ledger capability `spool_crash_recovery_v1`. Under one `LOCK_EX`, parse and integrity-check the ledger, derive V1/V2 aliases/fingerprint, classify evidence, and append any safe terminal. No evidence permits pre-send requeue; a matching reservation without API evidence appends the safe terminal once and permits fresh revalidation; any API slot/send/empty/exception/ack-timeout/unknown evidence is reconcile-only and never requeued; a complete terminal fill is reconciled; corrupt data is blocked.

Reservation rows carry spool lease owner/token plus service/connection generation. Required order is durable ledger batch API-slot → spool leased-to-sending CAS → exactly one broker call. If the spool CAS loses after API-slot durability, mark unknown and do not call broker.

Stage930 adds `--stage179-execution-mode legacy-once|warm` default `legacy-once`, plus runtime/manifest/activation/runtime-root args. Legacy continues `_run_stage931`. Warm starts one Stage931 child through `_managed_popen`, checks readiness, and wakes it after detector/spool commit; it never spawns one-shot Stage931. Shutdown revokes feed/detector/executor readiness before the common TERM/KILL cleanup. Runtime/activation gates from Task 9 apply before the child imports the adapter.

- [ ] **Step 4: Run GREEN and repeat process races 20 times**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_official_live_execution_ledger_cycles \
  tests.test_stage179_executor_serve \
  tests.test_stage930_fast_lane
```

Expected: no intent/child has more than one send winner; default remains legacy.

- [ ] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/qmt_roll_official_live_execution_ledger.py \
  examples/portfolio_backtesting/qmt_roll_official_live_execution_service.py \
  examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py \
  tests/test_official_live_execution_ledger_cycles.py \
  tests/test_stage179_executor_serve.py \
  tests/test_stage930_fast_lane.py
git commit -m "feat(stage179): recover warm executor crashes at most once"
```

---

### Task 12: Isolate Launchd Canary, Bound Supervisor Shutdown, and Guard V1/V2 Rollback

**Files:**
- Modify: `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-day-session.plist`
- Modify: `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-night-session.plist`
- Create: `examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-direct.plist`
- Create: `examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-supervisor.plist`
- Create: `examples/portfolio_backtesting/run_qmt_roll_stage930_supervisor_child.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_supervisor.sh`
- Create: `examples/portfolio_backtesting/build_qmt_roll_stage179_rollback_guard.py`
- Create: `tests/test_stage179_launchd_lifecycle.py`
- Modify: `tests/test_stage930_fast_lane.py`
- Modify: `tests/test_stage179_release_manifest.py`

**Interfaces:**
- Consumes: direct Python production jobs, independent canary roots, supervisor process group, ledger rows
- Produces: no-submit canary plists, finite TERM→KILL, and `LedgerRollbackSafety`

- [ ] **Step 1: Write RED lifecycle and rollback tests**

```python
def test_production_session_jobs_keep_direct_python_owner(self):
    self.assertTrue(arguments[0].endswith("/.py311/bin/python"))
    self.assertTrue(arguments[1].endswith("run_qmt_roll_stage930_official_live_c9_session_daemon.py"))

def test_canary_paths_are_independent_and_have_no_live_submit(self):
    self.assertFalse(set(canary_state_paths) & set(production_state_paths))
    self.assertNotIn("live-real", canary_program_arguments)

def test_term_ignoring_child_and_grandchild_are_killed_without_restart(self):
    self.assertFalse(child_alive)
    self.assertFalse(grandchild_alive)
    self.assertEqual(restart_count, 0)

def test_side_effect_v2_ledger_requires_roll_forward_reader(self):
    self.assertEqual(safety.disposition, "v2_reader_required_reconcile_and_roll_forward")
```

- [ ] **Step 2: Confirm RED**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage179_launchd_lifecycle \
  tests.test_stage179_release_manifest \
  tests.test_stage930_fast_lane
```

Expected: direct/canary/lifecycle/rollback contracts not implemented.

- [ ] **Step 3: Implement deployment isolation and rollback classification**

Restore day/night repo plists to direct Python Stage930 ownership, retain `AbandonProcessGroup=false`, add `ExitTimeOut=15`, and do not add warm/activation env. Direct canary uses production-readonly, submit disabled, independent output/state/spool/ledger/readiness/log paths, and no auto schedule. Supervisor canary uses offline + submit disabled and only tests lifecycle. Neither plist is installed in P0.

The helper calls `os.setsid()` then `os.execv()` so PID equals daemon PGID. Supervisor defaults TERM timeout `5s` and KILL wait `5s`; TERM/INT latches termination, signals the negative PGID, polls every 50ms, escalates to SIGKILL, reaps, exits 143/130, and never restarts. Restart sleep and spawn gap are interruptible. Unknown PGID identity fails closed.

`inspect_ledger_rollback_safety(rows)` returns: no V2 → `v1_code_and_plist_rollback_allowed`; only V2 reservation/safe-terminal with no side effect → `broker_snapshot_required_keep_v2_reader`; any API slot/send/cancel/fill/unknown → `v2_reader_required_reconcile_and_roll_forward`. The CLI is read-only and outputs JSON/Markdown without changing ledger bytes.

- [ ] **Step 4: Run GREEN and lint**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage179_launchd_lifecycle \
  tests.test_stage179_release_manifest \
  tests.test_stage930_fast_lane
bash -n examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_supervisor.sh
plutil -lint examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-day-session.plist
plutil -lint examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.15w.c9-night-session.plist
plutil -lint examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-direct.plist
plutil -lint examples/portfolio_backtesting/launchd/local.qmt-roll.stage179.no-submit-supervisor.plist
```

Expected: all pass; no LaunchAgent is installed or loaded.

- [ ] **Step 5: Commit**

```bash
git add examples/portfolio_backtesting/launchd \
  examples/portfolio_backtesting/run_qmt_roll_stage930_supervisor_child.py \
  examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_supervisor.sh \
  examples/portfolio_backtesting/build_qmt_roll_stage179_rollback_guard.py \
  tests/test_stage179_launchd_lifecycle.py \
  tests/test_stage179_release_manifest.py \
  tests/test_stage930_fast_lane.py
git commit -m "fix(stage179): isolate activation and bound supervisor shutdown"
```

---

### Task 13: Run the P0 Fault/Performance Matrix, Freeze the Release, Record Evidence, and Obtain Independent Final Review

**Files:**
- Create: `tests/test_stage179_fault_matrix.py`
- Create: `tests/stage179_performance_gate.py`
- Create after clean code commit: `examples/portfolio_backtesting/release_manifests/stage179/candidate.json`
- Modify: `research/lines/futures_trend_stage819_intraday_rules/stages/20260713_2220_stage179_c9_live_execution_reliability_hardening.md`

**Interfaces:**
- Consumes: complete Tasks 1–12 implementation
- Produces: fault evidence, 60-second performance artifacts, immutable manifest, updated Chinese stage record, and independent merge/activation verdicts

- [ ] **Step 1: Add and run the RED-to-GREEN fault matrix**

Cover disconnect before lease; crashes before reservation, after reservation, after API slot, and during broker call; empty/exception/ack timeout; partial fill/cancel/late fill; connection-generation change; watermark race; open/close deadline; socket loss; spool busy/integrity/disk-full; ledger checksum/fsync; kill switch/review/profile mismatch; and two executors. Each case records spool state, ledger evidence, send/cancel counts, and recovery disposition. Repeat the process race 100 times and require `send_winners_per_child <= 1`.

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest -v \
  tests.test_stage179_fault_matrix
```

Expected: every fault closes safely; no duplicate send.

- [ ] **Step 2: Run the exact 60-second offline performance gate**

```bash
PYTHONPATH=.:examples/portfolio_backtesting \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -B \
  tests/stage179_performance_gate.py \
  --symbols 20 --ticks-per-second 2000 --duration-seconds 60 \
  --writer-delay-ms 25 --output-dir /tmp/stage179-p0-performance
```

Expected: normal zero silent drop/gap; ingress p99≤1ms/max≤5ms; with 25ms writer delay EventEngine sentinel p99≤20ms/max≤100ms; durable lag p99≤100ms/max≤500ms; drain≤2s; RSS growth≤64MiB; forced overflow latch≤10ms/readiness revoke≤1s; never `drop>0 && stream_ready=true`. Failure exits nonzero and is not waived.

- [ ] **Step 3: Run the complete regression and static gates**

```bash
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m pytest -q \
  tests/test_official_live_c9_intraday_state.py \
  tests/test_official_live_execution_ledger_cycles.py \
  tests/test_official_live_late_retry_fill.py \
  tests/test_stage174_query_bundle.py \
  tests/test_stage608_continuous_tick_stream.py \
  tests/test_stage904_durable_state_integration.py \
  tests/test_stage905_c9_cycle_intents.py \
  tests/test_stage930_fast_lane.py \
  tests/test_stage931_ctp_readiness.py \
  tests/test_stage931_post_reprice_final_gate.py \
  tests/test_stage931_trade_fill_accounting.py \
  tests/test_official_live_trace.py \
  tests/test_official_live_intent_spool.py \
  tests/test_official_live_c9_detector.py \
  tests/test_stage179_executor_serve.py \
  tests/test_stage179_runtime_profile.py \
  tests/test_stage179_release_manifest.py \
  tests/test_stage179_launchd_lifecycle.py \
  tests/test_stage179_fault_matrix.py
git diff --check
bash -n examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_supervisor.sh
plutil -lint examples/portfolio_backtesting/launchd/*.plist
```

Expected: all tests/static gates pass; no env, CTP, launchctl, or real order call.

- [ ] **Step 4: Commit code/evidence record, then generate and commit the immutable manifest**

Append a Chinese P0 section to the existing Stage179 record with minute-level start/end, commits, added/changed/removed parameters, test counts, fault/performance results, tree fingerprint, `send/cancel=0/0`, and P1/P2 not run. Mark equity/return/drawdown/Sharpe/slippage/trade count/win rate as not applicable because no backtest ran. State explicitly that merge does not mean live activation.

```bash
git add tests/test_stage179_fault_matrix.py tests/stage179_performance_gate.py \
  research/lines/futures_trend_stage819_intraday_rules/stages/20260713_2220_stage179_c9_live_execution_reliability_hardening.md
git commit -m "test(stage179): close offline fault and latency gates"
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python \
  examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py \
  --output examples/portfolio_backtesting/release_manifests/stage179/candidate.json
git add examples/portfolio_backtesting/release_manifests/stage179/candidate.json
git commit -m "build(stage179): freeze release manifest"
```

Expected: manifest source commit is an ancestor, every critical hash/digest validates, and the tree is clean.

- [ ] **Step 5: Dispatch an independent whole-branch review and fix every P0/P1 finding**

The reviewer receives the approved spec, this plan, immutable manifest, full diff package, test/fault/performance outputs, production-ledger read-only rollback classification, and launchd diff. It must report P0/P1/P2 counts, code/data/logic/confidence, latency evidence, at-most-once evidence, rollback safety, and separate verdicts for code merge, P1 read-only CTP, P2 test orders, and production activation. Any P0/P1 requires one fix wave, rerun of the full gates, manifest rebuild, and re-review.

- [ ] **Step 6: Stop at the environment boundary**

P0 completion permits code integration only with activation default off. P1 requires at least five complete day/night read-only CTP sessions plus one disconnect/reconnect with `send/cancel=0/0`. P2 requires separate explicit test-environment order authorization and at least 30 reconciled cases. P3 one-lot production canary requires another explicit live authorization and is not granted by this plan.

---

## Plan Self-Review

- Spec coverage: Tasks 1–4 cover ingress causality, fsync/gap/recovery, target eviction, trace/SLA; Tasks 5–8 cover persistent detection/spool; Tasks 9–12 cover runtime, warm execution, crash recovery, deployment, supervisor, and rollback; Task 13 covers fault/performance/record/review.
- Compatibility: legacy CLI/output paths and one-shot/legacy modes remain; all new persistent/warm/live behavior defaults off.
- Type consistency: all tasks reuse `DurableTickCursor`, integer nanoseconds, trace ID, 25-second absolute deadline, spool lease token, connection generation, and execution-ledger evidence.
- Safety consistency: spool transports intents but never replaces the ledger; socket only wakes; code merge never activates production.
- Scope: no strategy/backtest parameter changes and no production activation receipt are included.
- Execution choice: the user has already authorized execution and requested an independent Agent review, so use subagent-driven development continuously without another handoff question.
