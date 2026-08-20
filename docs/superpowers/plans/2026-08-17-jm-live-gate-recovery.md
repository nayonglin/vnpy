# jm Live Gate Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the authorized `jm2609.DCE` initial-open path without weakening stale account or stale candidate-tick protection.

**Architecture:** Stage260 will accept both legacy and timezone-bearing ISO timestamps and normalize timezone awareness before computing snapshot age. Stage930 will retain account-wide tick diagnostics but evaluate the final new-risk tick blocker against the exact durable spool candidate symbol and transport state.

**Tech Stack:** Python 3.11 standard library, unittest, pandas, existing Stage260/Stage930/Stage931 production pipeline, Stage948 atomic installer.

## Global Constraints

- Work directly in `/Users/bytedance/Desktop/person/vnpy_production_live`; do not create a worktree.
- Use `.py311/bin/python` for every Python test or command.
- Do not call `send_order` or `cancel_order` during implementation or qualification.
- Do not bypass Stage260, Stage902, Stage905, Stage927, Stage931, broker snapshot, active-order, or final-price gates.
- Keep C9 alpha, AI pool, sizing, 0.5R stop, and retry-once behavior unchanged.
- Do not run two production Stage930/Stage931 executors concurrently.

---

### Task 1: Accept the production Stage174 ISO timestamp

**Files:**
- Modify: `tests/test_stage179_stage260_execution_profile.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py:82-88,535-560`

**Interfaces:**
- Consumes: `readonly_summary["generated_at"]: str`, `now: datetime`.
- Produces: `_parse_generated_at(value: str) -> datetime | None` and a finite `readonly_gate["snapshot_age_seconds"]` for valid legacy or ISO input.

- [ ] **Step 1: Write the failing regression test**

Add a test that calls `run_daily_execution_gate` with:

```python
readonly_summary={
    "status": "readonly_snapshots_received",
    "generated_at": "2026-08-17T21:06:18.283886+08:00",
    "broker_snapshot": {"position_snapshot_state": "confirmed_flat"},
}
now=datetime(2026, 8, 17, 21, 6, 20)
```

Assert literal behavior:

```python
self.assertEqual(result.summary["readonly_gate"]["snapshot_age_seconds"], 1.716)
self.assertTrue(result.summary["readonly_gate"]["passed"])
```

- [ ] **Step 2: Run the focused test and observe RED**

Run:

```bash
.py311/bin/python -m unittest tests.test_stage179_stage260_execution_profile.Stage260ExecutionProfileTest.test_iso_timezone_snapshot_timestamp_is_fresh
```

Expected: FAIL because old `_parse_generated_at` returns `None`.

- [ ] **Step 3: Implement timezone-safe parsing and age normalization**

Use `datetime.fromisoformat(value)` first, retain legacy `strptime` fallback, and add:

```python
def _snapshot_age_seconds(observed_now: datetime, generated_at: datetime) -> float:
    if generated_at.tzinfo is not None and observed_now.tzinfo is None:
        observed_now = observed_now.replace(tzinfo=generated_at.tzinfo)
    elif generated_at.tzinfo is None and observed_now.tzinfo is not None:
        generated_at = generated_at.replace(tzinfo=observed_now.tzinfo)
    elif generated_at.tzinfo is not None and observed_now.tzinfo is not None:
        observed_now = observed_now.astimezone(generated_at.tzinfo)
    return round((observed_now - generated_at).total_seconds(), 3)
```

Call the helper only when parsing succeeds. Preserve the existing `0 <= age <= max_snapshot_age_seconds` fail-closed condition.

- [ ] **Step 4: Run Stage260 tests and observe GREEN**

Run:

```bash
.py311/bin/python -m unittest tests.test_stage179_stage260_execution_profile
```

Expected: all tests PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add tests/test_stage179_stage260_execution_profile.py examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py
git commit -m "fix: accept timezone live snapshot timestamps"
```

### Task 2: Scope the new-risk tick blocker to the durable candidate

**Files:**
- Modify: `tests/test_stage930_fast_lane.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py:4276-4320`

**Interfaces:**
- Consumes: `AuthorizableIntentSnapshot.candidate.vt_symbol`, `tick_result.transport_ready`, and `tick_result.symbol_tick_freshness.blocked_new_risk_symbols`.
- Produces: Stage931 blockers that reject an unready transport or stale current candidate but ignore stale unrelated symbols.

- [ ] **Step 1: Write failing candidate-scoped tests**

Add three cases around `_stage931_submit_blockers`:

```python
# candidate JM, blocked AP/SI, transport ready => no tick blocker
# candidate SI, blocked AP/SI, transport ready => tick blocker names SI
# candidate JM, transport not ready => tick blocker remains
```

Use the existing real `spool_candidate`/`spool_snapshot` fixtures, extending `spool_candidate(vt_symbol="...")` so the candidate identity is explicit.

- [ ] **Step 2: Run the focused tests and observe RED**

Run:

```bash
.py311/bin/python -m unittest \
  tests.test_stage930_fast_lane.Stage930FastLaneTest.test_unrelated_stale_symbols_do_not_block_fresh_open_candidate \
  tests.test_stage930_fast_lane.Stage930FastLaneTest.test_stale_open_candidate_remains_blocked \
  tests.test_stage930_fast_lane.Stage930FastLaneTest.test_unready_transport_blocks_open_candidate
```

Expected: the unrelated-symbol case FAILS under the old global `all_symbols_ready` rule.

- [ ] **Step 3: Implement the exact-candidate blocker**

Capture the candidate from the already-read spool snapshot. For non-close new risk:

```python
candidate_symbol = _clean(getattr(candidate, "vt_symbol", ""))
blocked_symbols = sorted({_clean(item) for item in ... if _clean(item)})
transport_ready = _to_int(tick_result.get("transport_ready"), 0) == 1
if not transport_ready:
    blockers.append("tick_stream_transport_not_ready_for_new_risk")
elif not candidate_symbol:
    blockers.append("tick_stream_candidate_symbol_missing_for_new_risk")
elif candidate_symbol in blocked_symbols:
    blockers.append(f"tick_stream_candidate_not_fresh_for_new_risk:{candidate_symbol}")
```

Keep the existing reduce-close exception and all downstream gates.

- [ ] **Step 4: Run Stage930 tests and observe GREEN**

Run:

```bash
.py311/bin/python -m unittest tests.test_stage930_fast_lane tests.test_stage930_persistent_authorization
```

Expected: all tests PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add tests/test_stage930_fast_lane.py examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py
git commit -m "fix: scope live tick gate to current candidate"
```

### Task 3: Verify pricing and release qualification without order APIs

**Files:**
- Verify: `tests/test_stage931_post_reprice_final_gate.py`
- Verify: `tests/test_stage931_trade_fill_accounting.py`
- Verify: `tests/test_stage948_production_installer.py`
- Create: `research/lines/futures_trend_stage819_intraday_rules/stages/20260817_2120_stage223_live_jm_gate_recovery.md`

**Interfaces:**
- Consumes: Task 1 and Task 2 commits.
- Produces: a tested candidate commit and a Chinese production incident record.

- [ ] **Step 1: Run pricing and production-installer regression tests**

```bash
.py311/bin/python -m unittest \
  tests.test_stage179_stage260_execution_profile \
  tests.test_stage930_fast_lane \
  tests.test_stage930_persistent_authorization \
  tests.test_stage931_post_reprice_final_gate \
  tests.test_stage931_trade_fill_accounting \
  tests.test_stage945_production_launcher \
  tests.test_stage948_production_installer
```

Expected: all tests PASS and no real CTP connection occurs.

- [ ] **Step 2: Record the incident and verification**

Create a Chinese stage record with exact minute, production base commit `9c0df9d86d4851cd78843334f274b7c28d73f899`, defect chain, changed files, test counts, zero order APIs, overfitting judgment `否`, and continued-value judgment `是`.

- [ ] **Step 3: Commit the evidence record**

```bash
git add research/lines/futures_trend_stage819_intraday_rules/stages/20260817_2120_stage223_live_jm_gate_recovery.md
git commit -m "docs: record jm live gate recovery"
```

### Task 4: Activate safely and reconcile the authorized jm order

**Files:**
- Use: `examples/portfolio_backtesting/install_qmt_roll_stage948_official_live_production.py`
- Verify: `/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/`

**Interfaces:**
- Consumes: clean tested candidate HEAD and user authority for any required production process restart.
- Produces: Stage948 activation evidence, one unique production session, and broker-side jm order/fill/reconciliation evidence.

- [ ] **Step 1: Recheck all seven launchd jobs and descendant PIDs read-only**

If any production daemon or warm executor remains alive, do not activate or start another session without explicit restart authority.

- [ ] **Step 2: Refresh read-only broker account state**

Using `ctp_live.local.env` and formal `vnpy_ctp/api/libs`, require fresh account, positions, active orders, trades, exact zero order API counters, and no existing jm open/order.

- [ ] **Step 3: Run Stage948 prepare then activate**

Use only the installer's documented `prepare` and `activate` commands. Require matching stable HEAD, manifest, qualification, activation receipt, data receipt, seven exact labels, and zero order APIs before session launch.

- [ ] **Step 4: Start exactly one production night session through Stage945**

Do not invoke Stage930 or Stage931 directly. Confirm one daemon and one warm executor generation.

- [ ] **Step 5: Reconcile the jm submit**

Require the exact `jm2609.DCE` C9 initial-open intent, volume 2, latest executable ask-based Stage931 final reprice, one send-order side effect, broker order callback, trades/fill quantity, average fill price, remaining order state, and final broker position. Do not retry outside the existing durable state machine.
