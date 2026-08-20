# Stage226：干净监管 epoch 与 entry_risk 生产证据契约

## 基本信息

- 修改时间：2026-08-18 14:10（Asia/Shanghai）
- line_id：`futures_trend_stage819_intraday_rules`
- 是否重要突破：否；这是实盘执行与风控证据链修复，不修改 alpha、品种选择、入场方向、手数或参数。
- 当前正式策略：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，资金 `150000`。
- 用户边界：不追溯今天已经错过的 0.5R；以后自动开仓必须正常启用入场日 0.5R 止损/一次重试；当前手动成交的 JM、SI 不得重复开仓，并应在后续进入正式策略的正常平仓链路。

## 根因与运行态恢复

- 旧 Stage608 durable journal 带有无法补齐的历史 gap，Stage941 cursor 停在旧 feed，导致 `stream_ready=false`。旧 heartbeat、spool、64 份 journal/lock 已移动到可恢复审计目录，没有删除：
  - `/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/runtime/recovery-audit/20260818_1345-stage226-clean-supervision-epoch`
- 同一 manifest 重复 Stage948 激活暴露 quarantine 目录重用问题；已逐项核对 rollback manifest 和 7 个 plist 哈希后，将已完成 quarantine 移入上述审计目录，再用 Stage948 同一 HEAD 原子恢复。该次恢复没有报单，API 计数为 0。
- 干净 epoch 曾验证 Stage608 `stream_ready=true`、Stage941 `detector_running_ready`、Stage904 `intraday_monitor_ready`；随后发现 Stage904 的 AP/JM/SI 行虽能重建实际成交，但 `initial_stop_price/risk_price/0.5R` 全为 0。
- 最终根因：Stage901 的 `entry_risk` 只写研究 `backtest_outputs`，没有作为 production `signal-input` cohort 成员发布；Stage904 因此能识别手动仓位和成交价，却不能获得策略原始止损，无法计算 0.5R。

## 本次代码改动

- `OfficialExecutionProfile` 为 C9 增加 `entry_risk_path`；Stage372 保持无日内 stop/retry 的 `None` 语义。
- Stage901 将 `entry_risk` 作为第五个原子 artifact，先写五份文件、最后写 audit seal；cohort seed 和 audit 均绑定其 SHA256。
- pending artifact schema 从 v1 升为 v2；validated snapshot 原子读取并物化 `entry_risk`，缺失、篡改、错路径或 audit 代际变化均 fail-closed。
- production daily receipt 将 `entry_risk` 纳入 `signal_bundle.assets` 与 bundle SHA；旧 receipt 不能在 entry_risk 变化后复用。
- Stage904 不再旁路读取独立 current_positions/entry_risk 文件，而是只消费同一份 validated Stage901 snapshot；请求 target date 与 cohort 不一致时拒绝。
- 独立复审在候选 `fb43834ae9d07005d5a37cb75bf55303ab2b7fb5` 发现 1 个 P1：Stage901 snapshot 失效时，Stage904 会清空候选并跳过 durable state，使已经锁存的保护性 close intent 消失，同时摘要误报 `intraday_monitor_ready`。
- P1 修复遵循 close-only fail-closed：snapshot 失效时禁止创建新状态、禁止推进 retry open，但从未修改的 durable state 重放已经锁存的初始/重试止损 close intent；没有 durable state 时仍明确 blocked。摘要新增 `signal_snapshot_error`，任何 snapshot 错误都令 monitor 状态为 blocked。
- 第二次独立复审在 `cdfcf1aab3ecead82e35ddbb609e1715325e38ae` 发现跨阶段 P1：Stage941 刷新 close delivery provenance 时会把 blocked 改写成 close-ready，Stage905 随后仍读取 Stage901 pending open，导致坏/混代 cohort 下保护 close 与错误 initial open 同时进入候选。
- 跨阶段修复为三层 fail-closed：Stage941 有 `signal_snapshot_error` 时保持 blocked；调用 Stage905 时关闭 Stage901 pending；Stage905 自身既不物化 pending initial open，也对任何注入的 open（含 retry）追加 `stage904_signal_snapshot_invalid_for_open` blocker。已锁存 close 仍可凭 fresh exact-symbol durable tick 进入后续 close-only 门禁。
- Stage905 原有语义保持：与 Stage901 计划同向且手数已存在的手动仓位标记 `skipped_existing_broker_position`，不会重复开仓；后续 Stage901 正常 close 仍按真实 broker 持仓生成平仓请求。

## 参数变化

- 新增参数：无交易参数；仅新增 `OfficialExecutionProfile.entry_risk_path` 证据字段。
- 修改参数：`PENDING_ARTIFACT_SCHEMA_VERSION 1 -> 2`。
- 删除参数：无。
- C9 规则仍为入场日 `0.5R` 止损、止损成交且 broker flat 后最多重试一次、先触达有利 `+0.5R` 后解除初始 0.5R；没有调整 R 倍数。

## TDD 与验证

- RED：Stage901 测试先因 profile 无 `entry_risk_path` 失败；daily receipt 测试先因 `pending_artifact_entry_risk_sha256_invalid` 失败；Stage904 测试先因无 validated snapshot loader 失败；target-date mismatch 测试先因 helper 不接受 expected target 失败。
- GREEN：相关 5 个模块共 `155 tests` 通过。
- 独立复审 P1 的 TDD：两条 callable 测试先复现 `monitor_status=intraday_monitor_ready`；修复后验证已有 close 保持原 `action_id/intent_role`、状态文件不变、无 retry，空状态也明确 blocked，订单 API 均为 0。
- P1 修复定向回归：Stage904 durable state、冻结状态机、Stage905 cycle intents 共 `133 passed, 51 subtests passed`。
- 跨阶段 P1 的 4 条 TDD 覆盖先复现：blocked 被改写、detector 仍传 `include_stage901_pending=True`、Stage905 同时产出 close+initial open；修复后验证 spool 候选只剩 protective close、注入 retry open 明确 blocked。Stage904/905/941 联合回归 `133 passed, 51 subtests passed`。
- 生产资格规定的 31 个离线 pytest suite：`834 passed, 689 subtests passed, 0 failed`，耗时 `162.06s`。
- `py_compile`：5 个修改的生产 Python 文件通过。
- `git diff --check`：通过。
- 新增订单 API diff 扫描：没有新增 `send_order/cancel_order/ReqOrderInsert/ReqOrderAction` 调用。
- 精确手动成交阈值回归：
  - JM long 2，fill `1367.5`、策略原止损 `1354.5`：0.5R stop `1361.0`，progress `1374.0`。
  - SI long 6，fill `8590.0`、策略原止损 `8615.0`：按冻结的绝对风险距离 25，0.5R stop `8577.5`，progress `8602.5`。
- 手动 SI 6 手与计划 open 同向时跳过重复开仓；后续正常 Stage901 close 对同一 broker long 6 手可生成 close request。
- 本阶段没有连接 CTP、没有运行报单、订单 API 计数为 0。

## 回测指标

- 本阶段未运行新回测，不改变正式策略历史结果。
- 期末权益：不适用（沿用正式 C9/15w，未重算）。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 当前状态与 TODO

- 当前 production day/night job 均保持停用；带 P1 的 `fb43834` 和 `cdfcf1aab` 均未安装到实盘。
- TODO：提交跨阶段 P1 修复后的新 clean HEAD；对新 HEAD 做同一独立复审；重新运行两次正式只读 CTP qualification；生成新 manifest/qualification/activation receipt；只通过 Stage948 prepare/activate 安装；启动后核验 7 labels、Stage608/941、Stage904 阈值、JM/SI 监管和 API 计数。

## 反思

- 是否过拟合：否。没有根据今天 JM/SI 的价格路径修改规则，只修复所有 C9 生产 cohort 都必须具备的通用 entry-risk 证据契约。
- 是否值得继续：是。没有该证据，未来任何自动开仓都无法可靠计算入场日 0.5R；完成资格和原子激活后才算闭环。
- 外部调研判断：官方 vn.py/CTP 上游提供订单、成交和持仓原语，但没有可直接复用的“手动仓位绑定策略 entry-risk cohort”实现；本次应在本仓库的 Stage901/904/receipt 证据边界解决，而不是改底层 CTP API 或复制外部策略。
