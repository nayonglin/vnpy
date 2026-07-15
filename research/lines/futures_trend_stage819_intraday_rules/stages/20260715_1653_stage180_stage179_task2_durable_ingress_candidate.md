# Stage180 Stage179 Task2 耐久行情入口候选收口

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：隔离 worktree 离线实现、故障注入与只读代码审查；未加载实盘 env、未连接 CTP、未操作 launchctl
- 记录时间：`2026-07-15 16:53 CST`
- 完成时间：`2026-07-15 16:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability` / `codex/stage179-live-execution-reliability`
- 基线提交：`0d4af88d9`
- Task2 代码/测试/Spec 冻结指纹：`3e9df85a98bbdaf621e6f771c8011c097f300fe03bfa68413526d1ed0b7f3da2`
- 阶段性质：Stage179 计划 Task2 的耐久行情入口、恢复与只读生命周期收口，不改 alpha
- 是否重要突破：否；具备代码合入条件，但尚未完成 Task3、端到端 SLA、0/0 CTP 与 SimNow 验收
- 是否触发A/B：否；没有修改信号、AI 池、止损、重进场、品种、方向、手数或资金参数
- 是否连接 CTP：否
- 下单/撤单 API 次数：`0/0`

## 外部调研与判断

- 参考资料：
  - VeighNa `EventEngine` 官方实现：<https://github.com/vnpy/vnpy/blob/master/vnpy/event/engine.py>。事件由单消费者线程出队，行情因果时间必须在 gateway 入队前采集，handler 时间只能用于排队诊断。
  - VeighNa `BaseGateway` 官方实现：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py>。`on_tick` 是进入 EventEngine 前的 gateway ingress 边界。
  - VeighNa `vnpy_ctp` 官方网关：<https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py>。TD/MD native close 与异步连接状态不能假设可安全重复调用。
  - Python 内置类型官方文档：<https://docs.python.org/3/library/stdtypes.html>。`bool` 是 `int` 的子类，因此 journal 身份字段必须使用 exact type，而不能依赖宽松相等。
- 我的判断：
  - 本次修复针对通用事件因果、耐久提交、崩溃恢复和进程生命周期，不应通过增加固定等待秒数或为 JM 放宽策略门禁解决。
  - 只有 fsync 后的 commit frame/cursor 能成为下游事实；任何队列溢出、半写、hash/offset/sequence 矛盾、owner 竞争或 cleanup 不确定都必须永久撤销本 session readiness。
  - producer 现在发布 per-symbol durable/first-buffered/evicted-through 三元水位，但 Stage904 尚未消费；Task3 完成前不得把它解释为新的交易授权。

## 本次变更

- 新增脚本：
  - `qmt_roll_official_live_tick_reader.py`：按 durable commit 边界分页读取，验证物理 cursor、batch hash、大小上限、session 与 exact-int row identity。
  - `qmt_roll_official_live_tick_recovery.py`：在 owner fence 下重验 heartbeat/journal inode，隔离或截断坏尾并披露不可证明 gap。
- 修改脚本：
  - `qmt_roll_official_live_tick_journal.py`：framed header/commit/hash、完整写、文件及父目录 fsync、批次上限和共享 replay identity validator。
  - `qmt_roll_official_live_tick_stream.py`：异步唯一 writer、durable cursor/ring、writer fault/overflow gap、per-symbol 三元水位与 exact-int envelope 验证。
  - `qmt_roll_official_live_tick_types.py`：补齐 durable batch/cursor/snapshot、shutdown、recovery 与 symbol watermark 类型。
  - `run_ctp_stage608_readonly_tick_snapshot_probe.py`：singleton/heartbeat authority、所有 pre-authority 初始化回滚、TD/MD at-most-once teardown、严格只读 exit gate 和 fail-closed 终态。
  - `tests/test_stage608_continuous_tick_stream.py`：新增 crash consistency、恢复、reader bounds、生命周期、exit gate、整数别名、eviction 三元合同等故障回归。
  - Stage179 Spec/Plan：区分 one-shot probe 与 stream 的 MD close 语义，并明确 Task2/Task3 边界。
- 删除脚本：无。
- 新增参数：无策略或 CLI 参数；内部固定口径为 ingress queue `8192`、writer batch `256`、flush 上限 `50ms`、shutdown drain `2s`、reader page `16MiB`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不适用；本阶段未运行策略回测。
- 账户规模：不适用；未加载账户环境。仓库运行口径仍存在冲突：`AGENTS.md` 默认 Stage372/20万，而 SOP/官方配置当前指向 Stage847-C9/15万。
- 成本口径：不适用。
- 样本过滤：gateway backlog、writer/fsync 错误、queue overflow、脏尾、commit/hash/offset/sequence 矛盾、owner 竞争、初始化/handler/signal/close 异常及 bool/float 身份别名。
- 策略/归因口径：仅执行可靠性；不改 Stage847-C9 或 Stage372 的任何 alpha 语义。

## 结果

- 期末权益：不适用；未跑回测。
- 总收益：不适用；未跑回测。
- 最大回撤：不适用；未跑回测。
- Sharpe：不适用；未跑回测。
- 总滑点：不适用；未跑回测。
- 总交易次数：不适用；验证期间订单/撤单 API `0/0`。
- 胜率：不适用；未跑回测。
- 其他关键指标：
  - Stage608 全量与 Stage931 ingress 因果回归合计 `112/112`，最终耗时 `19.166s`，进程退出码 `0`。
  - 7 个相关 Python 文件 `py_compile` 通过，`git diff --check` 通过。
  - 独立 runner 终审：`P0=0、P1=0、P2=0`；122 个只读副作用/类型/cleanup 反例全部 fail-close。
  - 独立 journal/recovery 与 alias mutation 复核：最终 `P0=0、P1=0、P2=0`；六个物理身份字段的 bool/float 和两个整数 alias mismatch 均有回归。
  - 独立 Spec/eviction 复核：最终 `P0=0、P1=0、P2=0`；JM/I 的 durable/first-buffered/evicted 三元合同均被 mutation 测试锁定，Stage904 相对基线无 diff。

## 输出文件

- report：本 Stage180 记录。
- summary：离线 unittest 与独立审查输出；未生成实盘 summary。
- orders：无。
- daily：无。
- quality：`tests/test_stage608_continuous_tick_stream.py`、Stage931 因果回归、`py_compile`、`git diff --check`、多轮独立 agent 审查与 mutation 验证。

## 结论

- 本阶段结论：Task2 已达到代码合入条件；旧 tick 不再因 EventEngine backlog 被重写为新鲜行情，EventEngine handler 不再执行磁盘 I/O，只有完整 fsync 的 batch 才推进 durable state，崩溃/坏尾/生命周期异常均有 fail-closed 证据。该结论不等于线上已部署，也不等于实时止损重进场已在实盘运行。
- 是否进入下一步：是，进入 Task3 的 Stage904 target-symbol eviction 消费门禁。
- 下一步：先完成 Task3 和端到端 trace/SLA；随后继续常驻 detector/spool/warm executor、部署与激活隔离。官方资金/版本口径未统一、LaunchAgent/runtime 未验收、0/0 CTP 与 SimNow 未通过前，禁止真实报单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有使用当晚 JM 盈亏、具体价格或品种特例调参；测试覆盖跨 session、跨字段、进程与磁盘故障的通用不变量。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：行情因果与 durable authority 是所有开仓、止损、重进场的共同底座；Task2 清零后，Task3 eviction 消费与端到端 SLA 仍是实盘延迟问题能否真正闭环的必要条件。

## 合入建议

- 是否更新本线 `LINE.md`：否；同线并行阶段先保留唯一 Stage180 记录，待更高层任务合入时统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未完成外部运行验收和实盘激活，不应提前记为正式突破。
