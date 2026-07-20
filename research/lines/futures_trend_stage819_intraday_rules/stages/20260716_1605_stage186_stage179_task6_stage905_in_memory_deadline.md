# Stage186 Stage179 Task6 Stage905 内存构建与绝对截止时间

- line_id：`futures_trend_stage819_intraday_rules`
- 记录时间：`2026-07-16 16:05 CST`
- 当前模式：隔离 worktree 离线 TDD + 独立只读对抗终审；未加载实盘 env、未连接真实 CTP、未操作 launchctl
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability` / `codex/stage179-live-execution-reliability`
- 基线提交：`3a12ee988`（Stage185 Task5 记录）
- Task6 代码提交：`8099fc04367bb4557e8371edbaad46632ce66d7a`
- 阶段性质：Stage179 Spec Task6；提取 Stage905 callable，把 Stage904 durable action 在内存中转换为可审计 intent，并强制入口起算 25 秒绝对 deadline，不改 alpha
- 是否重要突破：否；这是执行一致性和幂等基础设施，不是收益突破
- 是否触发 A/B：否；没有修改信号、AI 池、止损/重进场阈值、方向、手数或资金参数
- 是否连接 CTP：否；订单/撤单 API 次数 `0/0`

## 外部调研与判断

- Python `time` 官方文档：<https://docs.python.org/3/library/time.html#time.monotonic_ns>。单调钟适合同一 boot/domain 内的 elapsed/deadline 判断，墙钟用于跨域审计；不能在 Stage904/905 每一段重新起算 25 秒。
- Python `dataclasses` 官方文档：<https://docs.python.org/3/library/dataclasses.html>。`frozen=True` 只约束结果对象字段重新赋值，不会深冻结 DataFrame/dict，因此 lineage 可信性仍来自严格 trace/cursor/generation 校验。
- vn.py 官方代码：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py>。`OrderRequest` 是请求载体，不承担业务 deadline；必须在构造可发送 payload 前由 Stage905 显式 fail-close。
- 我的判断：Stage905 不能只复制 action 字段。它必须把 trace 与 outer fields、state generation、Stage904 summary counts 和 durable cursor 交叉绑定；但 summary cursor 应“覆盖”原 trigger cursor，而不是强制相等，否则重启后保留原触发 cursor 的合法 pending action 会被误杀。

## 本次版本变更

- 新增 frozen `Stage905SnapshotInputs`、`Stage905RunResult` 与 `run_executor_dry_run(...)`；CLI 保留原参数、输出名、fail-closed 预清空和 stdout JSON。
- 直接接受 `Stage904RunResult`，或成对接受 actions/summary；只传一侧、target date 或 monitor run identity 冲突均在构建前拒绝。
- in-memory Stage904 + snapshots 路径不读取 Stage904/Stage901/broker snapshot/ledger 文件；`write_compat_outputs=False` 不 mkdir、不清理、不写兼容产物。
- `_stage904_intents` 原样传播 trace JSON/ID、feed/global ingress/symbol sequence、ingress epoch/monotonic、deadline、完整 durable cursor 与 state generation。
- strict trace 校验交叉绑定 trace/outer/vt_symbol/deadline；state generation 必须是当前 `position_epoch_id:<canonical exact revision>`。
- Stage904 summary 的 action/close/retry/watch/block/order-api 计数与 actions 原子绑定；非空 cursor 必须是 exact 四字段、framed-v1、exact int，且覆盖 action 的持久化 trigger cursor。空 action batch 只允许合法空 cursor 或合法完整 cursor。
- 整个 batch 只采样一次注入 `ClockStamp`。在 `now == deadline` 边界，open=`expired`、close=`blocked` 且标记 critical，二者 payload 均为空；deadline 前 1ns 仍可 ready。
- stable payload hash 纳入 resolved status/order/price/tick/position evidence，排除 monitor run/generated/checked 等 volatile 字段，并把含实时 age 的诊断归一为 reason code；同一 expired action 在 +31s/+32s 重放 hash 相同。
- mixed Stage901/904 intent DataFrame 从原始结果重建 exact-int object 列，`>2^53` 的纳秒和 journal offset 不经 float64。
- invalid exchange 从异常崩溃改为明确 blocked；全路径 `send_order/cancel_order` 计数保持 `0/0`。
- 新增参数：`stage904_actions`、`stage904_summary`、`snapshots`、`include_stage901_pending`、`clock`、`write_compat_outputs`，均为 callable 注入参数。
- 修改参数：无生产策略参数修改。
- 删除参数：无。

## TDD、验证与独立终审

- RED：callable/dataclass 缺失；trace/cursor/generation 不传播；内存输入仍回读文件；25 秒边界无语义；mixed rows 把 exact int 转 float；summary cursor/count 和错误 generation 可伪造 ready；hash 随 observed age 漂移；invalid exchange 抛异常。
- GREEN：Stage905 `26/26`；Stage905 + Stage904 integration `83/83`；trace/Stage904/Stage905/Stage930/Stage931 相关最终联合 `264/264`，用例耗时 `13.659s`、墙钟 `15.25s`。
- 静态验证：2 个文件 `py_compile` 与 `git diff --check` 通过。
- 冻结 SHA-256：
  - Stage905 implementation：`d112cbd48a5a61f0c1651244a6e761ed108a7526a8114eb280c877d69192f679`
  - Stage905 tests：`1d7acacae1ee2c2c5050ae1d7339544704d034c8d9c4bd300821bd08290f4786`
- 独立终审：最终冻结对象 `P0=0、P1=0、P2=0`；独立重跑 Stage905 + Stage904 integration `83/83`，源码审计确认没有 env/CTP/报撤单能力。
- 终审前发现并关闭：summary/action cursor 与 generation 未绑定、hash 含 observed age、空 action malformed cursor 未阻断三类问题。

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

- 当前结论：Task6 代码具备合入条件；不代表已部署、已激活或已解决今晚实盘端到端延迟。
- 仍需 Task7 SQLite WAL close-priority spool、Task8 persistent detector 与 batch/heartbeat 同代 CAS、Task9-13 runtime/release/故障/灰度/只读 CTP/SimNow 验收。
- Task5 独立审查遗留的 batch 与 heartbeat generation P2 必须在 Task8 关闭；Task6 没有扩大激活范围。
- 资金口径：未修改资金/策略配置；SOP Stage372 20万与当前 Stage847-C9 15万冲突仍必须由 deployment preflight 阻断，禁止自动选边。
- Task7-13 全部通过前禁止真实报单。

## 过拟合反思

- 运行前：否。
- 运行后：否。
- 原因：本阶段只约束时钟、cursor、generation、幂等 hash 与 fail-close，不使用 JM 当晚单样本或收益结果调参，可跨品种和周期复用。

## 继续价值反思

- 运行前：是。
- 运行后：是。
- 原因：Task6 已把 Stage904 durable action 无文件往返地转换为 deadline-aware intent；只有继续完成 Task7/8，才能在崩溃、重放和并发条件下保证 intent 一次入队、close 优先和 detector cursor 原子推进。

## 记录归属

- 是否更新 `LINE.md`：否；同线并行阶段只写唯一 stage 文件，合入时统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未达到正式候选激活门槛。
