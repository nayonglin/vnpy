# Stage137 Current C9 Quality One-Way Satellite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable one-way satellite ledger for the frozen current C9 PIT quality entries, then run the four-anchor canary without changing the core C9 path.

**Architecture:** Fresh C9 runs provide base daily/trades/positions/entry-risk/candidate frames. A pure selector groups matched closed lots by original open trade, a FIFO allocator creates floor-25% mirror orders, and a chronological ledger replays real trade prices, daily marks, costs and aggregate broker10 margin. The candidate only adds satellite cumulative PnL to frozen C9 equity.

**Tech Stack:** Python 3.11 via `.py311/bin/python`, pandas, numpy, matplotlib, unittest, existing Stage901/719/167 helpers.

## Global Constraints

- Write only the current research line, its dedicated test, and research outputs.
- Do not modify official strategy/configuration, CTP, email, launchd or order APIs.
- Use one selector: `flat_entry + base + AI allowed + rank1-8 + selected_volume>1`.
- Use one sizing rule: `floor(original open volume * 0.25)`; no ceil or min-one.
- Fail closed on missing/non-finite PIT fields, prices, specs, margin or identity.
- Run only four-anchor 1x canary first; expansion is mechanically gated.
- Current branch contains uncommitted Stage130-136 data assets, so do not create commits or move work to another worktree during this stage.

---

### Task 1: Pure selection and FIFO allocation

**Files:**
- Create: `tests/test_rebuilt_c9_v2_stage137_current_c9_quality_one_way_satellite.py`
- Create: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage137_current_c9_quality_one_way_satellite.py`

**Interfaces:**
- Consumes: Stage719-compatible closed lots and base trades.
- Produces:
  - `select_quality_open_groups(closed_lots: pd.DataFrame) -> pd.DataFrame`
  - `allocate_floor_mirror_orders(open_groups: pd.DataFrame, trades: pd.DataFrame, fraction: float = 0.25) -> tuple[pd.DataFrame, dict[str, Any]]`

- [x] **Step 1: Write failing selector tests**

```python
def test_quality_selector_groups_split_closes_by_original_open_trade(self):
    selected = s137.select_quality_open_groups(self.closed_lots)
    self.assertEqual(selected["open_trade_id"].tolist(), ["OPEN.1"])
    self.assertEqual(selected.loc[0, "base_open_volume"], 11)
    self.assertEqual(selected.loc[0, "satellite_open_volume"], 2)

def test_quality_selector_fails_closed_on_missing_rank(self):
    lots = self.closed_lots.copy()
    lots["ai_product_pool_rank"] = np.nan
    with self.assertRaisesRegex(ValueError, "ai_product_pool_rank"):
        s137.select_quality_open_groups(lots)
```

- [x] **Step 2: Verify RED**

Run:

```bash
.py311/bin/python -m unittest tests.test_rebuilt_c9_v2_stage137_current_c9_quality_one_way_satellite.Stage137QualitySatelliteTest.test_quality_selector_groups_split_closes_by_original_open_trade -v
```

Expected: import or missing-function failure for `select_quality_open_groups`.

- [x] **Step 3: Implement the minimal selector**

```python
def select_quality_open_groups(closed_lots: pd.DataFrame) -> pd.DataFrame:
    required = {"requested_start_month", "open_trade_id", "entry_context", "layer_kind",
                "ai_product_pool_allowed", "ai_product_pool_rank", "selected_volume", "volume"}
    _require_columns(closed_lots, required)
    data = closed_lots.copy()
    structural = data["entry_context"].eq("flat_entry") & data["layer_kind"].eq("base")
    eligible = data.loc[structural].copy()
    _require_finite(eligible, ["ai_product_pool_allowed", "ai_product_pool_rank", "selected_volume", "volume"])
    mask = (
        pd.to_numeric(eligible["ai_product_pool_allowed"]).eq(1)
        & pd.to_numeric(eligible["ai_product_pool_rank"]).between(1, 8)
        & pd.to_numeric(eligible["selected_volume"]).gt(1)
    )
    selected = eligible.loc[mask].copy()
    grouped = _group_open_trade_lifecycle(selected)
    grouped["satellite_open_volume"] = np.floor(grouped["base_open_volume"] * 0.25).astype(int)
    return grouped.loc[grouped["satellite_open_volume"].gt(0)].reset_index(drop=True)
```

- [x] **Step 4: Write and verify RED tests for partial closes**

```python
def test_partial_close_allocation_tracks_floor_of_remaining_base_volume(self):
    orders, audit = s137.allocate_floor_mirror_orders(self.open_groups, self.trades)
    self.assertEqual(orders["satellite_delta"].tolist(), [2, -1, -1])
    self.assertEqual(audit["overclose_count"], 0)
    self.assertEqual(audit["nonflat_final_open_group_count"], 0)
```

Expected before implementation: missing-function failure for `allocate_floor_mirror_orders`.

- [x] **Step 5: Implement FIFO floor allocation and run focused tests**

```python
remaining_base = base_open_volume - cumulative_closed_volume
target_satellite = 0 if is_last_close else math.floor(remaining_base * fraction)
satellite_close = previous_satellite_target - target_satellite
```

Run:

```bash
.py311/bin/python -m unittest tests.test_rebuilt_c9_v2_stage137_current_c9_quality_one_way_satellite -q
```

Expected: selector/FIFO tests pass; ledger tests that reference unimplemented functions still fail.

---

### Task 2: Chronological MTM, cost and PIT margin ledger

**Files:**
- Modify: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage137_current_c9_quality_one_way_satellite.py`
- Modify: `tests/test_rebuilt_c9_v2_stage137_current_c9_quality_one_way_satellite.py`

**Interfaces:**
- Consumes: base daily, base positions price table, mirror candidate orders, metadata.
- Produces:
  - `apply_open_margin_gate(candidate_orders: pd.DataFrame, prior_combined_equity: float, broker_multiplier: float = 1.10) -> pd.DataFrame`
  - `replay_satellite_ledger(base_daily: pd.DataFrame, price_table: pd.DataFrame, candidate_orders: pd.DataFrame, specs: dict[str, dict[str, float]], cost_multiplier: float) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]`
- `apply_open_margin_gate` 只处理单个时点的一笔 open event（或同一时点按稳定顺序逐笔调用）；输入必须显式携带 `c9_projected_total_margin_after` 和基于当前全卫星持仓计算的 `satellite_margin_after_proposed`。实际账本不得先批量 gate 再重放。
- `prior_combined_equity` 固定为前一交易日 C 组合期末权益；首个 base date 使用 `150,000`。同日内不得用尚未完成的当日浮盈放宽后续开仓。
- 每个 `open_trade_id` 单独维护 executed sleeve position/blocked 状态，再按 `vt_symbol` 汇总 PnL 和 margin；一个 blocked 生命周期的 close 绝不能扣减同合约其他生命周期。
- `base_daily.date` 必须唯一；`price_table` 在 base date 内按 `(date, vt_symbol)` 唯一。每个 held-or-traded contract 的当日 `pre_close/close_price` 必须存在且为正，禁止邻日、相邻合约或 0 值 fallback；order 的本地交易日必须精确落在 base date。
- 每笔 open 还必须携带有限 `estimated_equity` 作为 PIT 完整性审计字段，虽不作为放宽 margin gate 的分母。

- [x] **Step 1: Write failing PIT margin test**

```python
def test_open_gate_uses_c9_projected_margin_after_and_previous_combined_equity(self):
    orders = pd.DataFrame([{
        "requested_satellite_delta": 1,
        "c9_projected_total_margin_after": 90_000,
        "satellite_margin_after_proposed": 1_000,
        "is_open_event": 1,
    }])
    gated = s137.apply_open_margin_gate(orders, prior_combined_equity=100_000)
    self.assertEqual(gated.loc[0, "executed_satellite_delta"], 0)
    self.assertAlmostEqual(gated.loc[0, "proposed_broker10_pct"], 100.1)

def test_skipped_open_trade_id_stays_blocked_and_later_close_executes_zero(self):
    daily, orders, audit = s137.replay_satellite_ledger(
        self.base_daily, self.price_table, self.margin_blocked_orders, self.specs, 1.0
    )
    lifecycle = orders.loc[orders["open_trade_id"].eq("BLOCKED.1")]
    self.assertTrue(lifecycle["executed_satellite_delta"].eq(0).all())
    self.assertEqual(audit["blocked_open_trade_id_count"], 1)

def test_blocked_close_cannot_reduce_another_lifecycle_on_same_contract(self):
    daily, orders, audit = s137.replay_satellite_ledger(
        self.base_daily, self.price_table, self.same_contract_allowed_and_blocked_orders, self.specs, 1.0
    )
    blocked = orders.loc[orders["open_trade_id"].eq("BLOCKED.1")]
    self.assertTrue(blocked["executed_satellite_delta"].eq(0).all())
    self.assertEqual(audit["overclose_count"], 0)
```

- [x] **Step 2: Verify RED, implement fail-closed gate, verify GREEN**

Run the named test and expect a missing-function failure, then implement:

```python
proposed = (c9_projected_margin_after + satellite_margin_after_proposed) * broker_multiplier
if not np.isfinite(proposed) or not np.isfinite(prior_combined_equity) or prior_combined_equity <= 0:
    raise ValueError("non-finite PIT margin input")
executed_delta = 0 if proposed / prior_combined_equity > 1.0 else requested_delta
```

开仓跳过后把 `open_trade_id` 永久加入 blocked set；该生命周期后续 close event 的执行量必须为 0。平仓事件本身永远不受 margin gate 阻断。

- [x] **Step 3: Write failing long/short multi-trade MTM tests**

```python
def test_replay_marks_previous_close_to_trade_to_close_and_charges_each_order(self):
    daily, orders, audit = s137.replay_satellite_ledger(
        self.base_daily, self.price_table, self.candidate_orders, self.specs, 1.0
    )
    # 期望值必须在 fixture 中按 pre_close -> 每笔 trade -> close 的逐段公式手算，
    # 分日断言 gross、slippage、commission 和 net；禁止复制生产函数或使用来源不明常数。
    self.assertAlmostEqual(daily.loc[0, "satellite_gross_pnl"], self.expected_day1_gross)
    self.assertAlmostEqual(daily.loc[1, "satellite_net_pnl"], self.expected_day2_net)
    self.assertEqual(audit["missing_price_count"], 0)
    self.assertLessEqual(audit["max_reconciliation_error"], 1e-9)

def test_cost_multiplier_scales_slippage_only_not_commission_or_gross(self):
    one, _, _ = s137.replay_satellite_ledger(
        self.base_daily, self.price_table, self.candidate_orders, self.specs, 1.0
    )
    two, _, _ = s137.replay_satellite_ledger(
        self.base_daily, self.price_table, self.candidate_orders, self.specs, 2.0
    )
    self.assertTrue(one["satellite_gross_pnl"].equals(two["satellite_gross_pnl"]))
    self.assertTrue(one["satellite_commission"].equals(two["satellite_commission"]))
    self.assertAlmostEqual(two["satellite_slippage"].sum(), one["satellite_slippage"].sum() * 2)
```

- [x] **Step 4: Implement chronological ledger**

```python
for date in base_dates:
    # 每个合约从当日 price_table.pre_close 起步；跨合约事件按 datetime、trade_id、open_trade_id 稳定排序。
    marks = pre_close_by_contract.copy()
    prior_combined_equity = previous_day_c_equity if not first_day else 150_000.0
    for order in all_orders_for_date_sorted:
        contract = order.vt_symbol
        gross += signed_position[contract] * (order.trade_price - marks[contract]) * spec[contract].size
        marks[contract] = order.trade_price
        if order_is_open:
            satellite_margin_after_proposed = portfolio_margin_at_current_marks_after(order)
            order = apply_open_margin_gate_one_event(order, prior_combined_equity)
        # close 永远执行；blocked open_trade_id 的派生 close 执行量为 0。
        charge_slippage_and_commission_for_executed_delta(order)
        signed_position[contract] += order.executed_satellite_delta
    for contract in held_or_traded_contracts:
        gross += signed_position[contract] * (close_price[contract] - marks[contract]) * spec[contract].size
```

`specs` 必须显式提供每个相关合约的 `size / margin_ratio / slippage / rate`；commission 固定为 `abs(executed_delta) * trade_price * size * rate`，slippage 固定为 `abs(executed_delta) * slippage * size * cost_multiplier`。禁止默认 `size=1`、`margin_ratio=0.15` 或缺失 rate/slippage 归零。

Record daily satellite gross/cost/commission/net PnL, cumulative PnL, B/C equity, satellite margin, aggregate broker10, held contracts and order counts. `B = 150,000 + satellite_cumulative_net_pnl`；`C = base account_equity + satellite_cumulative_net_pnl`；两条恒等式及逐日 `net = gross - slippage - commission` 的最大误差都必须 `<=1e-9`。EOD aggregate broker10 同时输出两个分母口径：前一交易日 C 组合权益（与 open gate 同口径）和当日 C 期末权益（捕获当日亏损后的实际风险）；canary 要求两者都不超过 100%。任一 proposed 或 EOD 值超过 100% 只记录并由 canary fail，不事后强平。Raise on missing price/spec, duplicate date/price key, order outside base dates, overclose, non-finite values or nonflat final holdings.

- [x] **Step 5: Verify GREEN and run regression tests**

```bash
.py311/bin/python -m unittest tests.test_rebuilt_c9_v2_stage137_current_c9_quality_one_way_satellite -q
.py311/bin/python -m unittest tests.test_qmt_entry_context_diagnostics tests.test_rebuilt_c9_v2_stage007_new_position_entry_state_audit tests.test_rebuilt_c9_v2_stage025_stage024_opened_entry_state_audit -q
```

Expected: all tests pass.

---

### Task 3: Fresh C9 runner, identity and canary outputs

**Files:**
- Modify: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage137_current_c9_quality_one_way_satellite.py`
- Modify: `tests/test_rebuilt_c9_v2_stage137_current_c9_quality_one_way_satellite.py`

**Interfaces:**
- Produces:
  - `run_base_start(start: pd.Timestamp, end: pd.Timestamp) -> dict[str, pd.DataFrame]`
  - `evaluate_canary(summary: pd.DataFrame, audits: pd.DataFrame) -> dict[str, Any]`
  - `main(mode: str = "canary") -> None`

- [x] **Step 1: Write failing identity and decision tests**

```python
def test_identity_rejects_base_curve_drift_over_one_micro_unit(self):
    with self.assertRaisesRegex(ValueError, "Stage167 identity"):
        s137.assert_stage167_identity(self.base_daily.assign(account_equity=lambda x: x.account_equity + 1e-4), self.frozen)

def test_canary_requires_both_2022_drawdowns_to_improve(self):
    decision = s137.evaluate_canary(self.summary, self.audits)
    self.assertFalse(decision["canary_pass"])
    self.assertIn("2022_drawdown_not_strictly_better", decision["failed_checks"])
```

- [x] **Step 2: Verify RED and implement identity/decision functions**

Identity must merge on `requested_start_month + date`, require exact date coverage, and reject max absolute equity/PnL/margin errors above `1e-6`. Decision logic must implement every predeclared conjunctive check without optional defaults.

Fresh C9 daily 先精确过滤到 `requested_start <= date <= 2026-06-30`；positions 只允许按该 base date 集合构造 `price_table`，preload rows 不得进入身份、PnL 或 margin。Identity 至少逐日比较 `account_equity / net_pnl / total_margin_exact`，并分别输出最大误差。

- [x] **Step 3: Implement fresh four-start orchestration**

```python
CANARY_STARTS = ("2020-01", "2022-01", "2022-07", "2026-01")
ANALYSIS_END = pd.Timestamp("2026-06-30")
COST_MULTIPLIERS = (1.0,)
```

For each start, run C9 once, extract trades/positions/entry-risk/candidates, build closed lots, create mirror orders, replay B/C, reconcile and append outputs. Write only after every input audit passes.

对每个 selected `open_trade_id`，除复用 Stage719 mapping 外还要生成 PIT binding audit：匹配候选数、entry index/candidate index、risk/candidate datetime、trade datetime、contract/direction/volume。要求 entry-risk 与 opened candidate 都是一对一、任何源行不复用、时间不晚于 open trade、字段与 closed-lot selector 完全一致；Stage719 的 5 日贪心 helper 返回映射本身不能代替唯一性审计。把同一 open 的 `projected_total_margin_after / estimated_equity` 显式挂到 open candidate order，缺失或非有限立即 fail-close。

运行前 22:10 数据合同修正后，selected open 全集必须从 `Open trades + PIT risk/candidate` 构造；closed-lot 只附着已发生 FIFO close。未平仓 terminal open 也必须生成开仓/已发生部分平仓订单，并由 ledger 接受“预期 terminal position”作末仓对账，不得因结束日后是否 close 而筛选。coverage 和 terminal reconciliation 字段按 predecl 修正逐项输出并进入 audit gate。

从 metadata 逐合约构造 `size / margin_ratio / slippage / rate` specs；任何相关合约缺 key 或非有限都阻断。fresh trades/order/base dates/price keys 的唯一性和时区由 input audit 明确输出，禁止 silent dedupe。

metadata audit 必须分别输出 zero-rate/zero-slippage/zero-margin-ratio count。当前官方 `783/783` contract rate 为显式 `0`，因此允许 `rate == 0` 并按公式得到 0 commission，但报告必须明确这是正式基线现有成本限制，不得声称已覆盖非零手续费；slippage 和 margin ratio 必须严格大于 0。若 replay 因 B/C 破产 fail-close，orchestration 必须把原因写入 canary audit/decision 并判失败，不能吞异常或误报为空样本。

PIT future audit 只检查当前 open 的五日匹配窗口和最终被选绑定；窗口外后续同身份事件不得误判当前 open。selector 文本字段规范化比较，数值字段按数值比较，并精确复现 Stage719 risk-first、缺失时 candidate fallback。entry-risk/candidate 在 fresh run 后按实际 base opens 的五日前序窗口裁剪并输出 excluded row count。

风险统计必须以 `150,000` 作为时间零点 peak/high，覆盖首日亏损。summary/report 对 A/B/C 输出期末权益、总收益、最大回撤、Sharpe、总滑点、总 commission、交易次数、非零日胜率和最长水下。source manifest 必须包含实际 `TRADER_DIR/database.db`、`vt_setting.json` 及其 SHA256。输出目录替换必须有 backup/失败恢复，不能先删除唯一完整旧结果。

- [x] **Step 4: Add source manifest and report/chart output**

Manifest must include Stage167 curve, Stage901/719 runners, official config, qmt universe/metadata source, this Stage137 producer and every persisted data input. Output daily/order/selection/margin/FIFO/reconciliation/summary/audit/decision/report/chart files under `outputs/stage137_current_c9_quality_one_way_satellite/`.

- [x] **Step 5: Run focused verification**

```bash
.py311/bin/python -m unittest tests.test_rebuilt_c9_v2_stage137_current_c9_quality_one_way_satellite -q
.py311/bin/python -m py_compile research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage137_current_c9_quality_one_way_satellite.py
git diff --check
```

Expected: all commands exit 0.

### Task 3 Review-3 corrections

Review record: `.superpowers/sdd/task-3-review-3.md`. These corrections were frozen before any Stage137 return run.

- [x] Replace eligible-only five-calendar-day mapping with complete PIT risk source -> next fresh base trading date -> non-retry actual Open mapping.
- [x] Exclude and classify synthetic retry before source consumption; map rollover/non-flat sources before selecting quality events.
- [x] Persist explicit PIT source and actual Open audit ledgers; require source/mapped/eligible/selected anti-joins to close without missing or unexpected actual Opens.
- [x] Record actual-volume drift without changing the quality selector; fail on ambiguous candidates, source/trade reuse, future bindings or unclassified non-retry Opens.
- [x] Expand manifest to the actually loaded local producer/strategy module graph and read-time data snapshots.
- [x] Make static audit output mode-aware so it does not fabricate terminal reconciliation or fail only because canary has not run.
- [x] Run dedicated tests, adjacent regressions, `py_compile` and whitespace checks, then obtain a fresh independent approval before Task 4.

---

### Task 4: Static audit, canary and independent review

**Files:**
- Generate: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage137_current_c9_quality_one_way_satellite/*`
- Create after review: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260711_2100_stage137_current_c9_quality_one_way_satellite_result.md`

- [ ] **Step 1: Run static input audit without return decisions**

```bash
.py311/bin/python research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage137_current_c9_quality_one_way_satellite.py --mode audit
```

Expected: four starts available, C9 identity pass, unique PIT binding, finite specs/margin and no live/order API calls.

- [ ] **Step 2: Run four-anchor 1x canary**

```bash
.py311/bin/python research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage137_current_c9_quality_one_way_satellite.py --mode canary
```

Expected: outputs generated and `decision.json` contains a complete pass/fail result. Do not run full from the same command.

- [ ] **Step 3: Dispatch independent reviewer**

Reviewer must independently recompute A/B/C equity, return, max drawdown, Sharpe, underwater, costs, trades, win rate, FIFO allocation, PIT timestamp ordering, margin gate, reconciliation, source identity and every canary check. Any P0/P1 requires a focused failing test, correction, rerun and a fresh reviewer.

- [ ] **Step 4: Apply mechanical expansion rule**

- If canary fails: record closure, mark 2x/3x and full as skipped by gate, and do not modify parameters.
- If canary passes: run the same four anchors at 2x/3x; only if both pass, amend the plan with the predeclared 13-start full command and run it.

- [ ] **Step 5: Final verification and records**

Run Stage137 tests, relevant Stage094/096/135 regressions, `py_compile`, `git diff --check`; then update Stage137 result, LINE, registry and important back_log summary in Chinese with all required metrics and before/after reflections.

## Plan Self-Review

- Spec coverage: selector, FIFO, daily MTM, cost, PIT margin, identity, canary, independent review and expansion gate all map to explicit tasks.
- Placeholder scan: no incomplete marker or deferred implementation text remains.
- Type consistency: Stage137 functions consistently consume and return pandas DataFrames plus JSON-safe audit dictionaries.
- Scope: one research tool, one test module and one output directory; no formal/live changes.
