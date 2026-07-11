# Stage133 C9 2022 Extracted Event Market Data Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不产生策略收益结论的前提下，验证四个冻结的 2022 C9 真实事件能否读取机械选定期权的分钟 premium、tick 双边盘口、成交量、持仓量和时间字段。

**Architecture:** 单一研究工具负责冻结输入、纯函数机械选券、每事件独立 TqBacktest 采集、原子 attempt 发布和根级汇总。网络层通过注入 fetcher 测试；先 plan-only，再只跑固定 canary，独立审查清零 P0/P1 后才允许剩余三条。

**Tech Stack:** Python 3.11、pandas、numpy、tqsdk 3.9.4、unittest、SHA256/CSV/JSON 原子 manifest。

## Global Constraints

- 解释器固定 `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`。
- 预声明固定为 `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260711_1611_stage133_c9_2022_extracted_event_market_data_readiness_predecl.md`。
- 固定四事件与预期 option symbol；任何输入、metadata 或选择漂移均在联网前 fail-close。
- raw DataFrame 全列保留；规范化只增加时间和 session 标识。
- 禁止策略 PnL、strike/DTE/比例扫描、订单/持仓/CTP/邮件/launchd/live 调用。
- 固定 `ready_for_full_premium_acquisition=false`、`ready_for_option_strategy_ab=false`、`ready_for_live=false`。
- 每次网络阶段后必须由独立 agent 审查数据、代码、口径、置信度和 bug。

---

## File Structure

- Create `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage133_c9_2022_extracted_event_market_data_readiness.py`: 输入冻结、机械选券、行情规范化与审计、网络采集、原子 attempt、汇总和 CLI。
- Create `tests/test_rebuilt_c9_v2_stage133_c9_2022_extracted_event_market_data_readiness.py`: 纯函数、负例、原子缓存和 injected fetcher 测试。
- Modify `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260711_1611_stage133_c9_2022_extracted_event_market_data_readiness_predecl.md`: 仅勾选已完成执行步骤和追加 review 注记，不改变冻结样本/规则。
- Create after results `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/<time>_stage133_c9_2022_extracted_event_market_data_readiness_result.md`: 中文结果、审查和停止裁决。
- Modify after completion `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/LINE.md`, `research/registry.md`, and only if materially important `back_log.md`.

### Task 1: Frozen Input and Mechanical Option Selection

**Interfaces:**
- Produces `load_frozen_probe_plan() -> pd.DataFrame` with one row per event.
- Produces `select_probe_option(metadata: pd.DataFrame, option_class: str, entry_price: float, entry_date: pd.Timestamp) -> dict[str, Any]`.
- Produces `audit_probe_plan(plan: pd.DataFrame) -> dict[str, Any]`.

- [ ] **Step 1: Write failing input and selection tests**

```python
def test_load_frozen_probe_plan_has_exact_four_events_and_symbols(self):
    plan = MODULE.load_frozen_probe_plan()
    self.assertEqual(plan["event_id"].tolist(), EXPECTED_EVENT_IDS)
    self.assertEqual(plan["option_symbol"].tolist(), EXPECTED_OPTION_SYMBOLS)
    self.assertTrue(MODULE.audit_probe_plan(plan)["probe_plan_audit_pass"])

def test_select_probe_option_fails_on_tied_direction_or_expired_chain(self):
    with self.assertRaises(MODULE.IntegrityError):
        MODULE.select_probe_option(expired_metadata, "CALL", 2700.0, pd.Timestamp("2022-04-26"))

def test_input_hash_drift_fails_before_network(self):
    with self.assertRaises(MODULE.IntegrityError):
        MODULE.load_frozen_probe_plan(expected_terminal_sha256="0" * 64)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `.py311/bin/python -m unittest tests.test_rebuilt_c9_v2_stage133_c9_2022_extracted_event_market_data_readiness -v`

Expected: import or missing function failures; no network access.

- [ ] **Step 3: Implement minimal frozen loader and selector**

```python
def select_probe_option(metadata, option_class, entry_price, entry_date):
    data = metadata.copy()
    expiry = pd.to_datetime(data["expire_datetime"], errors="coerce")
    cutoff = pd.Timestamp(entry_date).normalize() + pd.Timedelta(days=1)
    data = data[(data["option_class"] == option_class) & expiry.ge(cutoff)].copy()
    if data.empty:
        raise IntegrityError("no eligible option")
    data["_expiry"] = pd.to_datetime(data["expire_datetime"])
    data = data[data["_expiry"].eq(data["_expiry"].min())]
    data["_distance"] = (pd.to_numeric(data["strike_price"]) - float(entry_price)).abs()
    selected = data.sort_values(["_distance", "strike_price", "option_symbol"]).iloc[0]
    return selected.drop(labels=["_expiry", "_distance"]).to_dict()
```

The loader must verify the three frozen source hashes, four metadata hashes, exact event set, unique direction/entry price per event, fixed class mapping, exact expected symbols, and no outcome columns.

- [ ] **Step 4: Run focused tests and verify GREEN**

Expected: exact four-event plan and all drift negative cases pass.

### Task 2: Time Normalization and Field-Level Readiness Audit

**Interfaces:**
- Produces `normalize_market_frame(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame`.
- Produces `audit_event_market_data(underlying_minute, option_minute, option_tick, start, end) -> dict[str, Any]`.

- [ ] **Step 1: Write failing semantic tests**

```python
def test_normalize_accepts_tqsdk_nanoseconds_without_second_overflow(self):
    out = MODULE.normalize_market_frame(ns_frame, START, END)
    self.assertEqual(out.loc[0, "datetime_beijing"], pd.Timestamp("2022-04-25 21:01:00+0800"))

def test_audit_separates_price_tick_spread_volume_and_oi(self):
    audit = MODULE.audit_event_market_data(underlying, option_bar, one_sided_ticks, START, END)
    self.assertTrue(audit["premium_observed"])
    self.assertTrue(audit["tick_price_observed"])
    self.assertFalse(audit["two_sided_spread_observed"])
    self.assertTrue(audit["oi_observed"])

def test_tick_cumulative_volume_is_not_summed(self):
    audit = MODULE.audit_event_market_data(underlying, option_bar, cumulative_ticks, START, END)
    self.assertEqual(audit["tick_volume_first"], 10.0)
    self.assertEqual(audit["tick_volume_last"], 13.0)
    self.assertEqual(audit["tick_volume_change"], 3.0)
    self.assertNotIn("tick_volume_sum", audit)
```

Add separate negative tests for duplicate timestamps, invalid OHLC, negative bar volume/OI, negative quote volume, crossed ask below bid, unparseable timestamps, and rows outside the session.

- [ ] **Step 2: Run tests and verify RED**

Expected: missing normalization/audit functions.

- [ ] **Step 3: Implement strict normalization and audit**

```python
def normalize_market_frame(frame, start, end):
    out = frame.copy()
    numeric = pd.to_numeric(out["datetime"], errors="coerce")
    parsed = pd.to_datetime(numeric, unit="ns", utc=True, errors="coerce").dt.tz_convert("Asia/Shanghai")
    out["datetime_beijing"] = parsed
    out["in_session_window"] = parsed.ge(start) & parsed.le(end)
    return out
```

The implementation must preserve every source column/value, audit only session rows, count finite positive option close, finite nonnegative OI, valid tick last price, valid two-sided spread, nonnegative volumes, and report tick cumulative volume as first/last/change rather than a sum.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: all field-separation and malformed-data tests pass.

### Task 3: Atomic Attempt Publisher and Cache Validator

**Interfaces:**
- Produces `publish_attempt(event: Mapping[str, Any], fetched: FetchPayload, attempts_root: Path, lineage: Mapping[str, str]) -> Path`.
- Produces `validate_attempt_dir(path: Path, event: Mapping[str, Any], lineage: Mapping[str, str]) -> dict[str, Any]`.
- `FetchPayload` contains terminal status, three untouched DataFrames, audit, redacted message, and elapsed seconds.

- [ ] **Step 1: Write failing atomicity and integrity tests**

```python
def test_valid_attempt_round_trips_with_detached_manifest(self):
    path = MODULE.publish_attempt(EVENT, PAYLOAD, self.root, LINEAGE)
    result = MODULE.validate_attempt_dir(path, EVENT, LINEAGE)
    self.assertTrue(result["attempt_integrity_pass"])

def test_mutated_raw_file_or_wrong_producer_sha_is_not_cacheable(self):
    path = MODULE.publish_attempt(EVENT, PAYLOAD, self.root, LINEAGE)
    (path / "raw_option_tick.csv").write_text("tampered\n")
    self.assertFalse(MODULE.validate_attempt_dir(path, EVENT, LINEAGE)["cacheable"])
```

Also assert manifest excludes itself/checksum, credentials never appear in request/status/raw outputs, normalized rows equal raw rows, and non-extracted terminal cannot contain raw market data.

- [ ] **Step 2: Run tests and verify RED**

- [ ] **Step 3: Implement same-filesystem temporary directory, detached SHA manifest, and validator**

Use `tempfile.mkdtemp(dir=event_dir)` and `os.replace(temp_dir, attempt_dir)` only after all files and detached checksums validate. Include `tool_sha256/test_sha256/predecl_sha256/plan_sha256` in request lineage.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: tamper, lineage drift, leaked secret, and malformed schema cases all fail closed.

### Task 4: Injected Network Runner and Plan-Only Gate

**Interfaces:**
- Produces `fetch_event_network(event: Mapping[str, Any], max_seconds: int) -> FetchPayload`.
- Produces `run(run_mode: str, enable_network: bool, fetcher=fetch_event_network) -> dict[str, Any]`.

- [ ] **Step 1: Write failing runner tests with a fake fetcher**

```python
def test_plan_mode_never_invokes_fetcher(self):
    MODULE.run("plan", False, fetcher=lambda *_: self.fail("network called"))

def test_canary_only_fetches_first_fixed_event(self):
    seen = []
    MODULE.run("canary", True, fetcher=lambda event, _: seen.append(event["event_id"]) or PAYLOAD)
    self.assertEqual(seen, [EXPECTED_EVENT_IDS[0]])

def test_remaining_refuses_until_canary_cache_is_valid(self):
    with self.assertRaises(MODULE.IntegrityError):
        MODULE.run("remaining", True, fetcher=fake_fetcher)
```

- [ ] **Step 2: Run tests and verify RED**

- [ ] **Step 3: Implement the network fetcher and bounded runner**

```python
api = TqApi(TqSim(), backtest=TqBacktest(start_dt=start, end_dt=end), auth=TqAuth(user, password), disable_print=True)
underlying_minute = api.get_kline_serial(underlying, 60, data_length=2000)
option_minute = api.get_kline_serial(option_symbol, 60, data_length=2000)
option_tick = api.get_tick_serial(option_symbol, data_length=5000)
while True:
    try:
        api.wait_update(deadline=time.time() + 1.0)
    except BacktestFinished:
        break
```

Wrap construction, serial initialization, loop, frame copy, and `api.close()` in the same 180-second wall-clock timeout. Classify auth/timeout/query/integrity separately, redact username/password, and never call trading/account APIs.

- [ ] **Step 4: Run the focused suite and Stage130-133 regression suite**

Run:

```bash
.py311/bin/python -m unittest \
  tests.test_rebuilt_c9_v2_stage130_tqsdk_expired_option_chain_probe \
  tests.test_rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest \
  tests.test_rebuilt_c9_v2_stage132_c9_event_option_metadata_batches \
  tests.test_rebuilt_c9_v2_stage133_c9_2022_extracted_event_market_data_readiness -v
```

Expected: all tests pass; no network in tests.

- [ ] **Step 5: Run plan-only and audit outputs**

Run: `STAGE133_RUN_MODE=plan .py311/bin/python research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage133_c9_2022_extracted_event_market_data_readiness.py`

Expected: four fixed events/options, network disabled, zero attempts, static order/CTP/live scan zero, all input hashes match.

### Task 5: Canary, Independent Review, Remaining Events, and Record

- [ ] **Step 1: Run only the fixed first canary**

Run: `STAGE133_RUN_MODE=canary STAGE133_ENABLE_NETWORK=1 .py311/bin/python research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage133_c9_2022_extracted_event_market_data_readiness.py`

Expected: exactly one new event attempt; no remaining events touched.

- [ ] **Step 2: Dispatch an independent agent review**

Reviewer must independently recompute selection, raw/normalized equality, nanosecond timestamps, field-level readiness, manifest hashes, credential/order isolation, timeout scope, and whether conclusions remain data-readiness only. P0/P1 must be zero before continuing.

- [ ] **Step 3: If review finds issues, add one-variable RED tests, fix, rerun the same canary, and re-review**

Never delete old attempts, change the event, option, window, lengths, or readiness definitions.

- [ ] **Step 4: Run only the remaining three events after approval**

Run: `STAGE133_RUN_MODE=remaining STAGE133_ENABLE_NETWORK=1 .py311/bin/python research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage133_c9_2022_extracted_event_market_data_readiness.py`

- [ ] **Step 5: Dispatch full independent review and write result record**

The result must list per-event observed fields and row/time coverage, P0/P1/P2, numeric/semantic confidence, no-strategy decision, N/A backtest metrics, overfit/value reflection, and the unchanged Stage132 coverage hard fail.

- [ ] **Step 6: Update line records only after full review**

Update `LINE.md` and `research/registry.md`; append `back_log.md` only if the data-readiness result materially changes the vendor decision. Do not update root `memory.md`.

## Self-Review

- Spec coverage: frozen hashes/events/options, minute/tick fields, atomic attempts, timeout, canary gate, independent review, and no-A/B boundaries all map to Tasks 1-5.
- Placeholder scan: no TBD/TODO/implementation-later placeholders; unchecked boxes are execution tracking.
- Type consistency: loader returns plan DataFrame; selector returns one row dict; fetcher returns FetchPayload; publisher and validator share event/lineage contracts; runner accepts injected fetcher.
- Scope: one isolated data-readiness subsystem; no strategy logic or live execution changes.
