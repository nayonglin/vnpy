# Stage372 Stage179 Execution Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Stage179 可靠性底座安全接到 Stage372 20万官方日线执行路径，同时保证 C9 实时止损/重进场逻辑在该 profile 下不可启动、不可进入 spool、不可到达报单边界。

**Architecture:** 新增不可变 execution profile 作为身份事实源；Stage260 将 Stage372 signal 与 fresh broker state 转为已闸门化 decision，Stage905 把 decision 归一化为确定性 daily intent。Stage903/930 根据 profile 选择 daily-only 或历史 C9 路径，Stage931/manifest 对 profile、版本、资金和 source 做端到端复核。

**Tech Stack:** Python 3.11、pandas、SQLite WAL、vn.py EventEngine/MainEngine/CTP Gateway、unittest、launchd plist。

## Global Constraints

- 使用 `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`。
- Stage372 固定为 `official_live_stage372_20w_recovery_sleeve`、`200000`、`20w`。
- Stage372 不得启用 Stage904/941，不得生成 C9 `0.5R` stop/retry intent。
- `production-readonly` 必须保持 `send_order=0`、`cancel_order=0`。
- 不修改 Stage372 alpha、AI 池阈值、仓位或 recovery-sleeve 参数。
- 不安装、不 load、不 kickstart 新 LaunchAgent；不停止或替换当前线上进程。
- `.superpowers/` 属于用户未跟踪内容，不得 stage、删除或修改。
- 每个实现任务遵循 RED → GREEN → REFACTOR，并单独提交。

---

### Task 1: 不可变 Execution Profile

**Files:**
- Create: `examples/portfolio_backtesting/qmt_roll_official_execution_profile.py`
- Create: `tests/test_stage179_official_execution_profile.py`

**Interfaces:**
- Produces: `ExecutionStrategyMode`、`OfficialExecutionProfile`、`resolve_execution_profile(value: str | ExecutionStrategyMode) -> OfficialExecutionProfile`、`assert_profile_identity(...) -> None`。
- Consumes: `run_qmt_alignment_backtest.OUTPUT_DIR`。

- [ ] **Step 1: 写失败测试**

```python
def test_stage372_profile_is_official_daily_only_default(self):
    profile = resolve_execution_profile("stage372-20w")
    self.assertEqual(profile.official_version, "official_live_stage372_20w_recovery_sleeve")
    self.assertEqual(profile.capital, 200_000.0)
    self.assertFalse(profile.intraday_stop_retry_enabled)
    self.assertEqual(profile.allowed_intent_sources, ("stage260_stage372_daily",))

def test_profile_identity_mismatch_fails_closed(self):
    with self.assertRaisesRegex(ValueError, "execution_profile_version_mismatch"):
        assert_profile_identity(STAGE372_PROFILE, official_version="c9", capital=200_000, capital_label="20w")
```

- [ ] **Step 2: 确认 RED**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_official_execution_profile -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 最小实现**

```python
class ExecutionStrategyMode(str, Enum):
    STAGE372_20W = "stage372-20w"
    C9_15W_HISTORICAL = "c9-15w-historical"

@dataclass(frozen=True)
class OfficialExecutionProfile:
    profile_key: str
    official_version: str
    alias: str
    source_stage: str
    capital: float
    capital_label: str
    summary_path: Path
    signal_plan_path: Path
    current_positions_path: Path
    allowed_intent_sources: tuple[str, ...]
    intraday_stop_retry_enabled: bool
```

Stage372 路径必须精确使用历史 Stage659 artifact 名称；C9 历史 profile 从当前 `qmt_roll_official_live_config` 延迟构建，避免导入时改变默认身份。

- [ ] **Step 4: 确认 GREEN 并回归当前 config import**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_official_execution_profile tests.test_official_live_config_import -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add examples/portfolio_backtesting/qmt_roll_official_execution_profile.py tests/test_stage179_official_execution_profile.py
git commit -m "feat(stage179): add isolated stage372 execution profile"
```

### Task 2: Stage260 Profile 注入与日线 Decision 契约

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py`
- Create: `tests/test_stage179_stage260_execution_profile.py`

**Interfaces:**
- Consumes: `OfficialExecutionProfile`。
- Produces: `run_daily_execution_gate(profile, ..., write_outputs=False) -> Stage260RunResult`；每行 decision 带 `execution_profile`、`official_live_version`、`capital`、`capital_label`、`decision_id`。

- [ ] **Step 1: 写失败测试**

```python
def test_stage372_gate_emits_bound_identity_and_zero_order_api(self):
    result = run_daily_execution_gate(
        STAGE372_PROFILE,
        official_summary=summary,
        signal_plan=signal,
        current_positions=pd.DataFrame(),
        readonly_summary=readonly,
        positions=pd.DataFrame(),
        orders=pd.DataFrame(),
        write_outputs=False,
    )
    self.assertEqual(result.summary["execution_profile"], "stage372-20w")
    self.assertEqual(result.summary["order_api_called_count"], 0)
    self.assertEqual(set(result.decisions["intent_source"]), {"stage260_stage372_daily"})
```

- [ ] **Step 2: 确认 RED**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_stage260_execution_profile -v`

Expected: FAIL，`run_daily_execution_gate` 不存在。

- [ ] **Step 3: 提取纯函数并保持 CLI 兼容**

实现 `Stage260RunResult`，把当前 `main()` 的读取、决策与输出拆开。`decision_id` 对以下 canonical JSON 做 SHA-256：

```python
{
    "execution_profile": profile.profile_key,
    "official_live_version": profile.official_version,
    "trade_date": trade_date,
    "vt_symbol": vt_symbol,
    "direction": direction,
    "offset": offset,
    "volume": volume,
    "theoretical_price": theoretical_price,
}
```

CLI 新增 `--execution-profile`，默认 `stage372-20w`；路径全部从 profile 读取。任何 artifact 内显式版本/资金与 profile 冲突时输出 blocked summary，不能回退 C9 全局常量。

- [ ] **Step 4: 确认 GREEN 与旧决策回归**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_stage260_execution_profile tests.test_stage905_c9_cycle_intents -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py tests/test_stage179_stage260_execution_profile.py
git commit -m "feat(stage179): bind stage260 decisions to execution profile"
```

### Task 3: Stage905 Stage372 Daily Intent Adapter

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py`
- Create: `tests/test_stage179_stage372_daily_intents.py`

**Interfaces:**
- Consumes: `OfficialExecutionProfile` 与 Stage260 decisions/summary。
- Produces: `_stage260_daily_intents(...) -> list[dict[str, Any]]`；`run_executor_dry_run(..., execution_profile=..., stage260_decisions=...)`。

- [ ] **Step 1: 写失败测试**

```python
def test_stage372_replay_is_deterministic_and_never_reads_stage904(self):
    first = run_executor_dry_run(..., execution_profile=STAGE372_PROFILE, stage260_decisions=decisions)
    second = run_executor_dry_run(..., execution_profile=STAGE372_PROFILE, stage260_decisions=decisions)
    self.assertEqual(first.intents.iloc[0].intent_id, second.intents.iloc[0].intent_id)
    self.assertEqual(first.intents.iloc[0].source, "stage260_stage372_daily")

def test_stage372_rejects_any_c9_action_or_role(self):
    with self.assertRaisesRegex(ValueError, "stage372_intraday_input_forbidden"):
        run_executor_dry_run(..., execution_profile=STAGE372_PROFILE, stage904_actions=c9_actions, stage904_summary=c9_summary)
```

- [ ] **Step 2: 确认 RED**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_stage372_daily_intents -v`

Expected: FAIL，profile/decision 参数不存在。

- [ ] **Step 3: 最小适配实现**

Stage372 路径必须：

```python
if not profile.intraday_stop_retry_enabled:
    if stage904_actions is not None or stage904_summary is not None:
        raise ValueError("stage372_intraday_input_forbidden")
    stage904_actions = pd.DataFrame(columns=["monitor_action"])
    stage904_summary_data = {"monitor_status": "intraday_not_applicable_profile_disabled"}
```

只转换 `execution_action=simnow_executable` 且 identity 完全匹配的 Stage260 rows。payload 绑定 profile/version/capital/source/decision id，intent id 使用现有 canonical fingerprint。Stage372 source allowlist 之外的 row 整批 blocked；不得读取 `_stage904_actions_path()`。

- [ ] **Step 4: 确认 GREEN，并运行 Stage905/C9 兼容回归**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_stage372_daily_intents tests.test_stage905_c9_cycle_intents -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add examples/portfolio_backtesting/run_qmt_roll_stage905_official_live_executor_dry_run.py tests/test_stage179_stage372_daily_intents.py
git commit -m "feat(stage179): adapt stage372 daily decisions into durable intents"
```

### Task 4: Stage903/930 禁用 C9 子图

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py`
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py`
- Create: `tests/test_stage179_stage372_daemon_boundary.py`

**Interfaces:**
- Consumes: CLI `--execution-profile`。
- Produces: Stage372 cycle summary 的 `intraday_status=intraday_not_applicable_profile_disabled`；Stage930 不创建 Stage904/941 子进程、不调用 fast intraday lane。

- [ ] **Step 1: 写失败测试**

```python
def test_stage372_controller_never_runs_stage904(self):
    with patch.object(stage903, "_run_stage904") as run_stage904:
        result = stage903.run_controller_cycle(args_for("stage372-20w"), fixtures)
    run_stage904.assert_not_called()
    self.assertEqual(result["stage904"]["summary"]["monitor_status"], "intraday_not_applicable_profile_disabled")

def test_stage372_daemon_never_starts_detector_or_fast_lane(self):
    self.assertFalse(stage930._profile_uses_intraday_detector(args_for("stage372-20w")))
```

- [ ] **Step 2: 确认 RED**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_stage372_daemon_boundary -v`

Expected: FAIL，profile 分支不存在。

- [ ] **Step 3: 实现 profile 分支**

- Stage903 将 profile 传给 Stage260/905。
- Stage372 生成显式 not-applicable Stage904 result，计划行不能把 C9 gate 标记为 passed。
- Stage930 的 `_initialize_detector_supervisor`、`_run_fast_intraday_lane`、`_run_idle_fast_lane` 在 Stage372 下返回 `profile_disabled_no_order_api`，不得 spawn Stage941 或 Stage904。
- persistent detector 与 Stage372 同时选择时 startup fail-close，而不是静默切换。

- [ ] **Step 4: 确认 GREEN 与 daemon 回归**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_stage372_daemon_boundary tests.test_stage930_fast_lane -v`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add examples/portfolio_backtesting/run_qmt_roll_stage903_official_live_phase_d_controller.py examples/portfolio_backtesting/run_qmt_roll_stage930_official_live_c9_session_daemon.py tests/test_stage179_stage372_daemon_boundary.py
git commit -m "fix(stage179): keep c9 detector dormant for stage372"
```

### Task 5: Stage931/Manifest 端到端身份复核

**Files:**
- Modify: `examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`
- Modify: `examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py`
- Modify: `examples/portfolio_backtesting/qmt_roll_official_live_submit_authorization.py`
- Create: `tests/test_stage179_stage372_submit_boundary.py`

**Interfaces:**
- Consumes: explicit profile、manifest、Stage905/spool/authorization identity。
- Produces: API-slot 前 source/profile/version/capital allowlist gate。

- [ ] **Step 1: 写失败测试**

```python
def test_stage372_c9_source_is_rejected_before_api_slot(self):
    reserve = Mock()
    blockers = pre_api_slot_blockers(stage372_runtime, c9_retry_intent)
    self.assertIn("intent_source_not_allowed_for_execution_profile", blockers)
    reserve.assert_not_called()

def test_stage372_manifest_must_bind_20w_identity(self):
    with self.assertRaisesRegex(ReleaseManifestError, "official_version_mismatch"):
        validate_stage372_manifest(c9_manifest)
```

- [ ] **Step 2: 确认 RED**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_stage372_submit_boundary -v`

Expected: FAIL。

- [ ] **Step 3: 实现身份透传和复核**

- Stage931 `run_once/run_serve` 解析 `--execution-profile`，release gate 期望值来自 profile。
- Stage905 row、spool row、authorization authorized-intent 与 lease 必须一致绑定 `execution_profile`。
- Stage372 allowlist 只含 `stage260_stage372_daily`；任何 C9 role/source/position-cycle metadata 阻断。
- manifest critical files 加入 execution profile 和 Stage372 tests；builder CLI 要求显式 profile，避免导入 C9 全局默认。

- [ ] **Step 4: 确认 GREEN 与竞争/账本回归**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_stage372_submit_boundary tests.test_stage179_submit_authorization tests.test_stage179_two_executor_process_race tests.test_official_live_execution_ledger_cycles tests.test_stage931_trade_fill_accounting -v`

Expected: PASS，所有 fake order-api duplicate count 为 0。

- [ ] **Step 5: 提交**

```bash
git add examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py examples/portfolio_backtesting/qmt_roll_official_live_submit_authorization.py tests/test_stage179_stage372_submit_boundary.py
git commit -m "fix(stage179): bind stage372 identity at submit boundary"
```

### Task 6: 独立 Stage372 LaunchAgent 与不可变候选

**Files:**
- Create: `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.20w.stage372-day-session.plist`
- Create: `examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.20w.stage372-night-session.plist`
- Modify: `tests/test_stage179_launchd_lifecycle.py`
- Modify: `examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py`

**Interfaces:**
- Produces: 默认 `dry-run + submit disabled + production-readonly` 的独立 Stage372 plist；不可变 Stage372 manifest。

- [ ] **Step 1: 写失败 plist 契约测试**

断言：label/path/runtime root 与 C9 不同；包含 `--execution-profile stage372-20w`；不包含 real-submit env/confirm；`ProcessType=Interactive`；day/night session 名称互斥；stdout/stderr 不与 C9 共用。

- [ ] **Step 2: 确认 RED**

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_launchd_lifecycle -v`

Expected: FAIL，新 plist 不存在。

- [ ] **Step 3: 新增 no-submit plist 与 manifest critical list**

ProgramArguments 固定 Stage372 profile、warm executor、stream tick、production-readonly 和独立 runtime root；不加入 `--mode live-real`、`--submit-mode live-real` 或任何真实报单确认文本。

- [ ] **Step 4: 静态验证**

Run: `plutil -lint examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.20w.stage372-day-session.plist examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.20w.stage372-night-session.plist`

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m unittest tests.test_stage179_launchd_lifecycle tests.test_stage179_release_manifest -v`

Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
git add examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.20w.stage372-day-session.plist examples/portfolio_backtesting/launchd/local.qmt-roll.official-live.20w.stage372-night-session.plist tests/test_stage179_launchd_lifecycle.py examples/portfolio_backtesting/build_qmt_roll_stage179_release_manifest.py
git commit -m "build(stage179): add dormant stage372 readonly launch agents"
```

### Task 7: 全量回归、性能证据、记录与独立 Review

**Files:**
- Modify: `research/lines/futures_trend_stage819_intraday_rules/stages/20260713_2220_stage179_c9_live_execution_reliability_hardening.md`
- Create after clean commit: `examples/portfolio_backtesting/release_manifests/stage179/stage372-candidate.json`

- [ ] **Step 1: 全量验证**

Run: `git diff --check`

Run: `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m compileall -q examples/portfolio_backtesting tests`

Run: Stage179/260/903/905/930/931 相关 unittest 全集；随后运行 `tests/stage179_performance_gate.py` 的 120k tick、故障注入、并发 sender 和 lifecycle 检查。

Expected: unit 0 failure；性能 SLA 全通过；fake/readonly `send/cancel=0/0`；并发唯一赢家。

- [ ] **Step 2: 记录中文阶段证据并提交**

记录分钟级时间、代码指纹、profile、测试数、性能分位数、0/0、未完成环境门和“否过拟合/是继续有价值”。不追加根目录 `memory.md/back_log.md`。

- [ ] **Step 3: 干净树生成不可变 Stage372 manifest**

先提交全部代码，再用 builder 显式传 `stage372-20w` 生成 manifest；验证 source commit、critical file hashes、20w identity 和 allowed runtime profiles。manifest 本身再单独提交。

- [ ] **Step 4: 拉起独立 agent 全面 review**

Reviewer 必须检查：策略语义隔离、C9 dormant 证明、Stage260→905 映射、profile 端到端身份、duplicate/unknown side effect、LaunchAgent 隔离、测试与性能数据可信度、P0/P1/P2 分级。P0/P1 修复后重新完整验证和复审；不影响结果的 P2 写入 stage record。

- [ ] **Step 5: 只读 CTP 环境门**

仅使用 `ctp_live.local.env`，正式 `vnpy_ctp/api/libs` framework 在 `.py311/lib` 前。以新 Stage372 独立 runtime 执行 `production-readonly`；不得 load 新 plist，不得打开 spool/submit adapter。验收 summary 必须证明 `front_connected=true`、账户/持仓快照状态明确、`send_order_api_called_count=0`、`cancel_order_api_called_count=0`。

若非交易时段、env 缺失、runtime guard 失败或 CTP 不可达，记录为环境阻断，不得把离线通过表述为实盘通过。

- [ ] **Step 6: 结束反思**

明确报告：是否过拟合、是否仍值得继续、代码可否合入、是否具备部署条件、是否具备真实报单条件。没有 SimNow/券商测试另行授权与验收时，真实报单结论必须为 NO-GO。
