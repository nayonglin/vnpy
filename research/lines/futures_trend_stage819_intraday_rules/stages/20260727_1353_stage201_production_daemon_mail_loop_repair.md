# Stage201 production-live 守护进程与邮件循环修复

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-07-27 13:53 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_production_live` / `codex/stage200-production-reliability-repair`
- 阶段性质：C9/15万 production-live 执行可靠性修复；不改 alpha、价格、手数、品种池或风险参数
- 是否重要突破：否；这是线上故障修复，不是策略突破
- 是否触发 A/B：否

## 外部调研与判断

- Python 官方 `sqlite3` 文档确认显式事务/SAVEPOINT 可用于固定一致读取视图；本次继续保留单事务授权快照，不伪造 cursor。
- Apple 官方 `launchd` 文档确认 `KeepAlive` 会维持任务运行；当前 Stage930 连续异常退出后被重新拉起符合 launchd 语义，不能只靠重启解决。
- 我的判断：根因是空 spool 冷启动语义、邮件事件键和 warm executor 环境接线三处确定性缺陷，不是策略信号或 AI 池问题。

## 线上故障证据

- 2026-07-27 09:05 创建的 production intent spool 中：
  - `detector_cursors=0`
  - `intents=0`
- Stage930 从 10:06 起反复出现：
  - `SpoolValidationError('spool_snapshot_stage941_cursor_count_invalid:0')`
  - 连续三轮异常后 `daemon_stopped_after_consecutive_cycle_errors`
- launchd 因非零退出重新拉起 Stage930；暂停前 `runs=42`。
- Stage930 邮件 key 原为 `cycle_exception_<cycle_at>`，每轮时间不同导致 30 分钟节流失效；暂停前当日异常邮件状态记录已增至 `42`。
- warm Stage931 stderr 反复出现：
  - `stage179_submit_arming_blocked:real_adapter_env_missing`
- 磁盘曾只剩约 `0.38 GiB`，用户清理后恢复到约 `2.29 GiB`，超过生产下限 `2 GiB`；磁盘是独立阻断，不是上述三处代码根因。
- 故障期间 send/cancel/order API 始终为 `0/0/0`。

## 本次变更

- `qmt_roll_official_live_intent_spool.py`
  - 仅当 `detector_cursors` 和 `intents` 同时为空时，允许生成 `candidate=None` 的不可报单授权快照。
  - 只要存在任一 intent，缺少 Stage941 cursor 仍严格抛出 `spool_snapshot_stage941_cursor_count_invalid:0`。
  - 不插入伪 cursor，不改变 cursor 约束、CAS、lease 或授权顺序。
- `run_qmt_roll_stage930_official_live_c9_session_daemon.py`
  - cycle exception 邮件改为按异常文本 SHA-256 指纹去重；同一异常跨轮次共用 key。
  - adapter exception 按稳定的 status/blockers/error/exception 结构指纹去重。
  - 邮件发送成功后才写 `last_sent_at` 并加入进程内 `sent_keys`；发送失败只写 `last_attempt_at`，按 5 分钟节流重试，避免“失败即永久已发送”和逐轮轰炸。
  - throttle 状态由文件锁串行化并通过原子替换写入；只保留 7 天内最新 512 条，避免崩溃损坏和无界增长。
  - warm Stage931 live-real 子进程显式获得 `OFFICIAL_LIVE_PHASE_D_REAL_ADAPTER_IMPLEMENTED=1`。
  - 在启动 Stage931 子进程之前按 `runtime.framework_path` 注入 `DYLD_FRAMEWORK_PATH`，保证 production-live 正式 CTP framework 在 `.py311/lib` 评测 framework 之前被 dyld 选择。
  - 不伪造 `OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED`；该开关仍只能从 production launchd 继承。
- 测试
  - 新增 fresh empty spool 不可报单快照测试。
  - 新增“已有 intent 但无 cursor”继续 fail-closed 测试。
  - 新增异常邮件跨时间稳定指纹测试。
  - 新增邮件失败后有限重试、成功后才持久去重、状态锁/原子写/条数上限测试。
  - 新增 Stage931 adapter flag 注入且不伪造 submit flag 测试。
  - 新增 Stage931 exec 环境 framework 顺序测试和 macOS 真实子进程 CTP 动态库加载路径测试。
- 新增策略参数：无。
- 修改策略参数：无。
- 删除策略参数：无。

## 回测与策略指标

- 本阶段未运行策略回测。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 离线验证

- `py_compile`：4 个变更 Python 文件通过。
- `git diff --check`：通过。
- 首轮聚焦回归：
  - `test_official_live_intent_spool`
  - `test_stage930_fast_lane`
  - `test_stage930_persistent_authorization`
  - 共 `131 tests`，全部通过。
- 最终修复后上述聚焦回归共 `135 tests`，全部通过。
- 最终修复后扩大回归：Stage179 executor/fault/runtime/authorization/race、Stage927、Stage931 四组、Stage945/946/947/948 共 `313 tests`，全部通过。
- 使用 production spool 的临时副本验证：
  - `candidate=None`
  - `total_intent_count=0`
  - `ready_open_count=0`
  - `ready_close_count=0`
  - snapshot/cursor digest 均为 64 位
- 使用当日真实异常摘要验证：修改 `cycle_at` 后异常 key 保持一致。
- production `ctp_live.local.env` 仅检查键名和完整性：文件存在、解析 20 个键、必需 CTP 键缺失 `0`；未打印任何值。
- 独立审查发现并阻断一个 P1：仅在 Stage931 Python 进程启动后写 `DYLD_FRAMEWORK_PATH` 会误载 `.py311/lib` 的评测 framework。
- P1 修复后的聚焦验证：`57 tests` 全部通过；真实 macOS 子进程加载的两个 `thost` framework 均位于正式 `vnpy_ctp/api/libs` 路径。
- 独立审查的两个 P2（失败邮件被误记为已发送、throttle 非原子且无界）已一并修复；新增 2 个聚焦测试通过。
- 独立复审发现 reserve 新 key 时会在发送完成前短暂持久化 513 条的 P3；已调整为新增前先裁到 511 条，保证任一持久时点均不超过 512 条。

## 当前边界

- 变更尚未 production qualification、签发新 release manifest 或激活。
- 当前 day-session 已临时 bootout，避免继续发送异常邮件。
- 在 exact commit 独立 review、正式 qualification、master fast-forward、Stage948 激活与零报单运行读回完成前，不得宣称实盘已恢复。

## 过拟合反思

- 运行前：否。
- 运行后：否。
- 原因：没有按日期、品种、方向、收益或信号结果调参；所有分支都由结构不变量约束，且保留“有 intent 无 cursor 必须失败”的安全边界。

## 继续价值反思

- 运行前：是。
- 运行后：是。
- 原因：当前故障会使守护进程退出、邮件循环和真实适配器无法启动；修复直接恢复生产可用性。下一步价值只在独立复核、正式资格与运行态验收，不在继续扩展规则。

## 2026-07-27 15:00 安装复验补充

- 用户释放磁盘后，production-live 可用空间恢复到约 13 GiB，Stage948 prepare/activate、正式 CTP 只读资格和 7 个 launchd label 均通过。
- 首次拉起时 Stage931 warm executor 已 `ready`，CTP 行情/交易连接、授权、登录、结算确认和合约查询成功，send/cancel/order API 为 `0/0/0`。
- 运行态发现 Stage608 因 `legacy_heartbeat_not_cleanly_stopped` 阻断行情流。旧 heartbeat 与 startup attempt 已原字节归档到 production runtime recovery audit；当时 spool `intents=0`、`detector_cursors=0`，未删除任何交易意图或 journal。
- 进一步定位到 Stage930 首次启动会先写缺少 Stage179 journal 契约的 supervisor tombstone，导致 Stage608 将其识别为不干净旧心跳。
- 新增修复：
  - 只有 heartbeat、startup/lifecycle guard 与 journal base/segment/dirty/lock/manifest 证据全部不存在时，才允许写不可报单的 non-authoritative Stage179 bootstrap。
  - heartbeat 已存在但为 `{}`、不可读，或存在任一 orphan journal/lifecycle guard 证据时，均在写入前 fail-closed 并保留原字节。
  - 已有 committed clean/running authority 时继续保留 feed、segment 和 committed lineage；running authority 交给 Stage608 转为 `fault_stopped` 后恢复，clean authority 保持 strictly stopped。
- 独立专项审查首轮发现“heartbeat 丢失但非空 journal 仍存在时可能被误判为 gap-free bootstrap”的 P1；已修复并补齐 missing heartbeat + journal、`{}` heartbeat、lifecycle guard、committed clean/running 五类回归。
- 最新验证：
  - Stage608 与 Stage930 主回归 `232 tests` 全部通过。
  - Stage930、detector、persistent authorization、Stage948 安装器扩大回归 `136 tests` 全部通过。
  - 新增 7 项 bootstrap/recovery 聚焦测试全部通过。
  - `py_compile`、`git diff --check` 通过。
- 独立最终复审：`P0=0、P1=0、P2=0、P3=0`，结论 `GO`；审查侧最新完整相关测试 `237 passed / 120 subtests passed`。
- 当前边界：该补充修复仍需形成 exact commit、完成独立最终 GO、重新 production qualification、重签 manifest/activation receipt 并重新激活；在运行态 tick stream 与健康检查通过前仍不得宣称实盘恢复。
- 过拟合反思：否；本次只修执行持久化和首次启动契约，不改 alpha、价格、手数、AI 池或风险阈值。
- 继续价值反思：是；该缺陷会让实时报价链 fail-closed，修复和重新资格是恢复自动止损/重进场的必要条件。
