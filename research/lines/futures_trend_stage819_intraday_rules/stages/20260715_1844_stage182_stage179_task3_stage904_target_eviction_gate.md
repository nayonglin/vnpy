# Stage182 Stage179 Task3 Stage904 目标合约淘汰门禁

- line_id：`futures_trend_stage819_intraday_rules`
- 记录时间：`2026-07-15 18:44 CST`
- 当前模式：隔离 worktree 离线 TDD 与只读独立审查；未加载实盘 env、未连接 CTP、未操作 launchctl
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability` / `codex/stage179-live-execution-reliability`
- 基线提交：`de1941d1a`
- Task3 冻结提交：`c2d82a2d48e2f4e5dc3b7952e77252ca10a35dac`
- 代码/测试 diff 与完整 binary show 指纹：`d6bde827a7acc397ae5e7433bd47490b0aa99d4fffa949eec0a2dce36b852f87`
- 阶段性质：Stage179 Spec Task3；只补 Stage904 对 Stage608 per-symbol eviction watermark 的消费门禁，不改 alpha
- 是否重要突破：否；关闭一个会把“目标 tick 已淘汰”误解释成普通空帧的执行数据完整性缺口
- 是否触发 A/B：否；没有修改信号、AI 池、止损、重进场、方向、手数或资金参数
- 是否连接 CTP：否；全部为离线单元测试
- 下单/撤单 API 次数：`0/0`

## 外部调研与判断

- 参考资料：
  - Apache Kafka Log：<https://kafka.apache.org/26/implementation/log/>。消费者请求的 offset 已不在保留范围时返回 OutOfRange，不能把空读取当成“没有消息”。
  - Apache Kafka Protocol：<https://kafka.apache.org/35/design/protocol/>。`OFFSET_OUT_OF_RANGE` 是明确的非重试型范围错误，由业务决定 reset 或失败。
  - Python `collections.deque`：<https://docs.python.org/3/library/collections.html#collections.deque>。有界 deque 满后追加会从另一端淘汰旧项，与 Stage608 显式 `popleft()` 后缀保留语义一致。
- 我的判断：
  - Stage608 全局 ring 中只保留 RB 等其他合约时，JM frame 为空并不能证明 JM 没有 tick；若 JM 的 `evicted_through_symbol_sequence` 已越过该 position state 的最后消费序列，唯一安全结论是覆盖缺口。
  - 交易执行不能像通用消息消费者一样自动 reset 到 latest，否则可能跳过止损触发；因此 Stage904 必须永久锁存 exact feed gap，并继续维持 stop/retry-open 的 fail-close 语义。
  - 判断必须使用 per-symbol sequence，不能拿 global ring sequence 比较 JM state，避免 JM/RB/JM 交错产生假缺口。

## 本次变更

- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 修改实现：
  - Stage904 `_feed_gap_reason()` 在普通 `continuous_tick_rows_missing` 之前读取目标合约 watermark。
  - 当 `evicted_through_symbol_sequence > last_seq_by_feed[current_feed]` 时返回 `tick_target_symbol_evicted_before_consume:<vt_symbol>;feed=<feed>;last_consumed=<n>;evicted_through=<n>`。
  - 新三元字段必须同时存在、为精确非负整数并满足 producer 后缀不变量；三元全部缺失时保留旧 Stage608 heartbeat 的兼容路径，部分缺失、类型错误或相互矛盾均 fail-close。
  - 未改 Stage608 producer、状态 reducer、策略阈值或报单路径。
- 修改测试：
  - 新增“JM 已被全局 ring 淘汰、frame 仅保留 RB”回归，要求锁存 exact JM eviction gap。
  - 新增 `evicted_through == last_consumed` 等号边界，证明已消费的淘汰前缀不会误报且下一序号可继续消费。
  - JM/RB/JM per-symbol interleaving 补齐新三元 watermark，确保控制用例真实经过 Task3 gate；同时保留旧 heartbeat 全缺失兼容回归。
- 删除实现：无。

## 回测/验证参数

- 数据区间：不适用；本阶段未运行策略回测。
- 账户规模：不适用；未加载账户环境。Stage372/20万与 Stage847-C9/15万的运行口径冲突未在本阶段处理。
- 成本口径：不适用。
- 样本过滤：target frame 为空、global ring 仍含其他合约、目标 watermark 已淘汰、JM/RB/JM 交错、真实 per-symbol sequence gap。
- 策略/归因口径：仅执行数据覆盖门禁，不改正式策略 alpha。

## 结果

- 期末权益：不适用；未跑回测。
- 总收益：不适用；未跑回测。
- 最大回撤：不适用；未跑回测。
- Sharpe：不适用；未跑回测。
- 总滑点：不适用；未跑回测。
- 总交易次数：不适用；验证期间订单/撤单 API `0/0`。
- 胜率：不适用；未跑回测。
- 其他关键指标：
  - RED：目标 JM 已淘汰时旧逻辑返回 `continuous_tick_rows_missing`，定向用例 `1/1` 按预期失败。
  - GREEN：目标淘汰、等号边界、JM/RB/JM 完整新 watermark 交错三项 `3/3`。
  - Stage608 + Stage904 全量 `189/189`，测试耗时 `25.373s`、墙钟 `27.07s`，退出码 `0`。
  - `git diff --check` 通过。
  - 独立最终审查：审查当前收紧后的三元 gate，并独立重跑定向 `3/3`、`py_compile` 与 `git diff --check`；结论 `P0=0、P1=0、P2=2`，Task3 可冻结提交。
  - 提交对象级确认：`c2d82a2d48e2f4e5dc3b7952e77252ca10a35dac` 仅含两文件，tree `f98a4a7df8bcfed41fdae0cdf880c5da87785502`，binary show 指纹精确匹配；冻结 HEAD 定向 `3/3`，结论 `P0=0、P1=0`。

## 输出文件

- report：本 Stage182 记录。
- summary：离线 unittest 与独立审查输出；未生成实盘 summary。
- orders：无。
- daily：无。
- quality：`tests/test_stage904_durable_state_integration.py`、Stage608 producer control、全量 unittest、diff check。

## 结论与 TODO

- 当前结论：Task3 行为已通过离线全量回归和独立终审，达到代码提交条件；不是部署或实盘激活证据。
- 下一步：核对精确提交对象 → 进入 Task4 deterministic trace/SLA schema。
- 后续闸门：Task4-13、LaunchAgent/runtime、官方资金/版本口径、严格 `0/0` 只读 CTP、SimNow 报撤验收；通过前禁止真实报单。
- 激活前置：必须从线上 heartbeat 证明 Stage608 已发布 Task2 三元 watermark；三元全部缺失只表示旧版兼容，不能宣称已有 Task3 淘汰保护。
- 代际前置：旧版 global sequence cursor 不得原地解释为新版 per-symbol cursor；部署切换必须使用新 `feed_session_id` 并按 session-change fail-close 收敛。
- 已知 P2：新增 incomplete/invalid/incoherent/invalid-state-cursor 分支尚缺专门表驱动故障测试；逻辑已由独立 agent 逐项核对，后续纳入 Task13 fault suite。新 position 建立前若已有目标 tick 淘汰，会保守锁存 gap，属于可用性收紧而非风险放大。
- 是否更新本线 `LINE.md`：否；同线并行先保留唯一 Stage182 文件，合入时统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未成为正式候选或完成外部验收。

## 过拟合反思

- 运行前判断：否。
- 当前判断：否。
- 原因：使用的是通用消费 offset 与保留窗口不变量，没有根据今晚 JM 价格、盈亏或单一事件调参。

## 继续价值反思

- 运行前判断：是。
- 当前判断：是。
- 原因：空 frame 若被误判成无事件，会直接污染开仓、实时止损和重进场的因果解释；该门禁成本小、覆盖面清晰，值得继续。
