# Stage184 Stage179 Task4 trace 与虚拟时钟 SLA schema

- line_id：`futures_trend_stage819_intraday_rules`
- 记录时间：`2026-07-16 15:14 CST`
- 当前模式：隔离 worktree 离线 TDD + 两位独立只读终审；未加载实盘 env、未连接真实 CTP、未操作 launchctl
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability` / `codex/stage179-live-execution-reliability`
- 基线提交：`3d3390c294b98c97764d9881035890f0db9f9154`
- Task4 代码提交：`c17a3b897acf944c358d12118071557789ac9d9e`
- 阶段性质：Stage179 Spec Task4；建立确定性 trace、虚拟时钟 SLA 与写盘前 clock-domain 身份门禁，不改 alpha
- 是否重要突破：否；这是实盘执行可观测性和 fail-close 基础设施，不是策略收益突破
- 是否触发 A/B：否；没有修改信号、AI 池、止损/重进场阈值、方向、手数或资金参数
- 是否连接 CTP：否；测试输出中的 CTP 登录/订阅来自 fake gateway
- 下单/撤单 API 次数：`0/0`

## 外部调研与判断

- Python `time`：<https://docs.python.org/3/library/time.html>。`monotonic_ns()` 适合同一 clock domain 内的因果时延；UTC epoch 用于跨启动周期审计，但不能替代 durable lineage。
- vn.py `BaseGateway`：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py>。官方调用链先在 `BaseGateway.on_tick()` 构造并入队 EVENT_TICK，因此 gateway 入队前采集 ingress 是正确的底层时间边界。
- vn.py `EventEngine`：<https://github.com/vnpy/vnpy/blob/master/vnpy/event/engine.py>。handler 观察与异步 journal durable 是从 ingress 分叉的并发支路，不能伪造 `handler -> journal` 因果边。
- RFC 9562：<https://www.rfc-editor.org/rfc/rfc9562>。UUIDv5 是确定性的 name-based 标识，不是来源认证或签名。
- RFC 8259：<https://www.rfc-editor.org/rfc/rfc8259>。跨语言 JSON number 互操作精度需要单独约束；当前 Python-only 链路可保持整数纳秒，未来 JavaScript consumer 前必须迁移为十进制字符串或声明边界。
- 我的判断：Task4 应负责 deterministic identity、不可变 trace、精确 SLA 与跨 domain live fail-close；完整 producer generation、heartbeat/commit lineage 和 durable cursor 认证必须由 Task5/8 组合闭合。不能把一个 forward UTC stamp 当成可信的跨重启 provenance。

## 本次版本变更

- `qmt_roll_official_live_time.py`：SystemClock 公开跨 exec 一致、跨 reboot 变化的 boot-stable domain；Linux 读取 boot ID，macOS 读取 boot session UUID；不可取得时 fail-close。
- `qmt_roll_official_live_trace.py`：新增不可变 `ClockStamp/LatencyTrace`、完整 `TraceStage`、UUIDv5 trace ID、严格 JSON round-trip、25 秒绝对 deadline、精确整数纳秒 SLA budgets/evaluator。
- trace 校验拒绝重复 JSON member、NaN/Infinity、超大/越界 epoch、未知字段、bool/float 纳秒、UTC 不一致、同 domain monotonic rollback 与跨 domain epoch rollback。
- 同 domain 使用 monotonic SLA；跨 domain 仅输出 UTC audit latency，始终 `eligible=False/passed=False`；open 到期、close 阻断。
- Stage608 canonical envelope/row 持久化 `clock_domain_id`；writer 在任何 tick bytes 前绑定 pipeline/envelope/row 三者 exact type/value，阻断 row-only 与 envelope+row 联合篡改。
- `SlaBudget.required_intermediate_stages` 复制为 tuple；SLO 超标明确 `passed=False`，硬截止与条件性 fill/cancel 语义按 Spec 固化。
- 新增参数：无生产参数。
- 修改参数：无。
- 删除参数：无。
- 删除行为：删除“跨 clock domain 仍可作为 live deadline/SLA 证据”和“domain 篡改可先落盘”的路径。

## TDD 与验证

- RED：trace 模块/API 缺失；真实 Stage608 row 缺 clock domain；重复 JSON、cross-domain rollback、SLO passed、mutable budget 与 writer domain tamper 对抗用例均先复现失败。
- GREEN：`tests.test_official_live_trace` 为 `25/25`；Task4 + Stage608 联合 `171/171`，用例耗时 `25.489s`、墙钟 `26.79s`。
- 静态验证：6 个文件 `py_compile` 与 `git diff --check` 通过。
- 冻结 SHA-256：
  - time：`ce66363cbc1838a0c7fb684d97e157ee66b652b007e617ac6a442d8fbc55a711`
  - tick types：`aa7143b86fd62ae69a57749848d1e104337f75569a635f826039ef179ca67345`
  - tick stream：`7bf2ca5d90fd01445253f494bdf30d7d435125bdaa59955a3e8dfcd45534ac1d`
  - trace：`6b17a1965d7afbf9116d2db20237ea88539ccce4f3aa762a1a4d8afc35146e5b`
  - trace tests：`c2b13d7b2589cbe0269137f0f46fc1360b739180181d716988e935850fb9a4a2`
  - Stage608 tests：`dc9627271bfe50a67d8a654481d673715bae01852246c3969869dc5dfe87b65e`
- 两位独立终审均确认 `P0=0、P1=0`、代码层 merge eligible；一位给 `P2=0`，另一位给 `P2=2`，本记录采用保守聚合 `P2=2`：
  1. epoch 纳秒仍是超过 JavaScript 安全整数范围的 JSON number；当前 Python-only 链路精确，增加非 Python consumer 前必须迁移或显式阻断。
  2. Stage608 对缺少 `clock_domain_id()` 的 legacy/injected clock 生成 process-local fallback，而 trace consumer 严格拒绝；生产 SystemClock 不受影响，后续应统一离线契约。

## 回测结果

- 本阶段未运行策略回测；以下指标均不适用：
  - 期末权益：不适用
  - 总收益：不适用
  - 最大回撤：不适用
  - Sharpe：不适用
  - 总滑点：不适用
  - 总交易次数：不适用；验证期间订单/撤单 API `0/0`
  - 胜率：不适用
- 没有新增、修改或删除任何 alpha 回测结果。

## 当前结论与后续

- 当前结论：Task4 冻结代码具备合入条件；这只表示 schema 与离线门禁关闭，不代表已部署、已激活或已取得端到端延迟证据。
- Spec 5.5 硬边界：Task4 trace 是 internal-consistency cross-link，不是 source authentication。Task5 必须把完整 trigger `DurableTickCursor` 与 state generation 固化到 state/action；Task8 必须在追加 downstream stamp 前验证 producer generation、heartbeat/commit lineage 与 cursor ancestry。
- 必测反例：合法 ingress trace 后追加任意新 domain、forward UTC 的伪造 `journal_durable` stamp，只能得到 audit-only/ineligible；不得仅凭它恢复 live eligibility。
- 后续：进入 Task5，完成 trigger cursor 和 Stage904 deterministic callable；Task5-13、LaunchAgent/runtime、官方资金口径、严格 `0/0` 只读 CTP、SimNow 未全部通过前禁止真实报单。

## 过拟合反思

- 运行前：否。
- 运行后：否。
- 原因：约束来自时钟域、序列化、持久化身份和执行截止，不使用 JM 当晚单样本或任何收益结果调参，可跨品种和周期复用。

## 继续价值反思

- 运行前：是。
- 运行后：是。
- 原因：没有可信的分段时间证据，就无法区分策略逻辑拦截、行情/写盘延迟和下单链路阻塞；但只有 schema 还不能解决实盘延迟，必须继续完成 Task5/8 接线和 Task13 实测。

## 记录归属

- 是否更新 `LINE.md`：否；同线并行阶段只写唯一 stage 文件，合入时统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未达到正式候选激活门槛。
