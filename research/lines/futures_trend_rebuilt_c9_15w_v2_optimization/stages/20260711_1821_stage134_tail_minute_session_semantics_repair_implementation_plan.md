# Stage134 Tail Minute Session Semantics Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用真实交易日集合和 Stage208 成交窗口语义修复固定 6 个尾部分钟文件，并在严格验收后安全发布。

**Architecture:** 新建 Stage134 独立工具，不改 Stage120 历史产物。工具从 Stage020 生成每个合约的预期交易日和 signal-date 映射，复用 Stage052 的 TqSdk 下载函数，但使用 session-aware 时间边界；新审计器完成字段、日期和成交窗口门槛，再备份旧文件并同盘原子替换。

**Tech Stack:** Python 3.11、pandas、numpy、TqSdk、unittest、SHA256、CSV/JSON、`os.replace`。

## Global Constraints

- 解释器固定 `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`。
- 预声明固定为 `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260711_1820_stage134_tail_minute_session_semantics_repair_predecl.md`。
- 固定 6 个合约、Stage020 交易日、`20:55 -> 15:15` 下载边界和 Stage208 `21:00-21:05 / 09:00-09:05` 成交窗口。
- 禁止策略收益、参数扫描、fallback 成交、订单/持仓/CTP/邮件/launchd/live 调用。
- 发布前必须备份旧文件；失败文件不得覆盖正式目录。
- 结果完成后必须由独立 agent 复核数据、代码、口径、置信度和 bug。

---

### Task 1: Trading-Day Contract and Session-Aware Plan

**Files:**
- Create: `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage134_tail_minute_session_semantics_repair.py`
- Test: `tests/test_rebuilt_c9_v2_stage134_tail_minute_session_semantics_repair.py`

**Interfaces:**
- Produces `load_expected_trade_dates() -> tuple[dict[str, pd.DatetimeIndex], pd.DatetimeIndex]`.
- Produces `build_session_plan(before_manifest: pd.DataFrame, expected_by_contract: Mapping[str, pd.DatetimeIndex], global_dates: pd.DatetimeIndex) -> pd.DataFrame`.

- [x] Write tests that freeze the six contracts and assert Monday starts use the previous global trading day rather than the previous calendar day.
- [x] Run `.py311/bin/python -m unittest tests.test_rebuilt_c9_v2_stage134_tail_minute_session_semantics_repair -v` and verify missing-module/function RED.
- [x] Implement the minimal loader and plan builder with exact `20:55` start and `15:15` end.
- [x] Re-run focused tests and verify GREEN.

### Task 2: Session-Aware Strict Audit

**Interfaces:**
- Produces `audit_session_file(row: Any, path: Path, expected_dates: pd.DatetimeIndex, global_dates: pd.DatetimeIndex) -> dict[str, Any]`.
- Produces `audit_downloads(plan: pd.DataFrame, status: pd.DataFrame, expected_by_contract, global_dates) -> pd.DataFrame`.

- [x] Add synthetic tests with SHFE bars crossing midnight; assert natural-day count may exceed expected while exact day-session dates and fill-window coverage pass.
- [x] Add negative tests for missing first night and missing same-day 09:00 window, extra/missing day-session dates, duplicate timestamps, invalid OHLC, negative volume/OI, and out-of-bound rows.
- [x] Run focused tests and verify RED for missing audit behavior.
- [x] Implement only the frozen checks; do not add exchange-specific performance rules.
- [x] Re-run focused tests and verify GREEN.

### Task 3: Backup and Atomic Publication

**Interfaces:**
- Produces `publish_verified(audit: pd.DataFrame, quarantine_root: Path) -> pd.DataFrame`.

- [x] Add temporary-directory tests proving a failed candidate preserves the old final file and a passing candidate backs up old bytes before same-device `os.replace`.
- [x] Run focused tests and verify RED.
- [x] Implement backup hash verification, same-device check, atomic replacement, and rejected-temp quarantine.
- [x] Re-run focused tests and Stage052/130-133 regression suites.

### Task 4: Fixed Network Run and Final Gate

**Interfaces:**
- Produces `run(enable_download: bool) -> dict[str, Any]` and CSV/JSON/report/stage artifacts under `outputs/stage134_tail_minute_session_semantics_repair/`.

- [x] Run plan-only and verify exact six rows and zero network calls.
- [x] Run the fixed six-contract download once with `STAGE134_ENABLE_DOWNLOAD=1` and bounded per-symbol timeout.
- [x] Require `strict_ready_count=6`, `published_or_replaced_count=6`, and post-publish discoverable strict coverage `39/39`; otherwise fail close.
- [x] Dispatch an independent reviewer and resolve all P0/P1 findings before advancing.
- [x] Write the Chinese result record and update this line's `LINE.md`; do not claim strategy improvement.
