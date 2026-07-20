# Stage185 Stage179 Task5 Stage904 durable callable

- line_id：`futures_trend_stage819_intraday_rules`
- 记录时间：`2026-07-16 15:42 CST`
- 当前模式：隔离 worktree 离线 TDD + 独立只读对抗终审；未加载实盘 env、未连接真实 CTP、未操作 launchctl
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability` / `codex/stage179-live-execution-reliability`
- 基线提交：`6ac0db6ec`（Stage184 Task4 记录）
- Task5 代码提交：`334349d7c4a7384102f1e202361850e67059f6d8`
- 阶段性质：Stage179 Spec Task5；固化触发行、完整 durable cursor、trace/deadline/state generation，并提取 Stage904 callable，不改 alpha
- 是否重要突破：否；这是确定性状态与执行 provenance 基础设施，不是收益突破
- 是否触发 A/B：否；没有修改信号、AI 池、止损/重进场阈值、方向、手数或资金参数
- 是否连接 CTP：否；订单/撤单 API 次数 `0/0`

## 外部调研与判断

- pandas nullable integer：<https://pandas.pydata.org/docs/user_guide/integer_na.html>。整数列混入缺失值会被默认推断成浮点，标识符或大整数可能无法精确表示；因此 exact ns/cursor offset 必须显式保持非 float dtype。
- Python dataclasses：<https://docs.python.org/3/library/dataclasses.html>。`frozen=True` 提供结果对象字段的只读赋值边界，但不会自动深冻结 DataFrame/dict；本阶段只把它作为 callable 结果接口，不把它误称为来源认证。
- RFC 9562：<https://www.rfc-editor.org/rfc/rfc9562>。UUIDv5 仍只是确定性 identity；真正的跨重启可信性依赖 cursor、generation 和 commit lineage 的组合验证。
- 我的判断：触发行 `source_ingress_sequence` 与包含它的 batch commit cursor 不是同一个概念。批量 fsync 下可由第 11 条触发、cursor durable through 第 12 条；必须分别保存并交叉验证。任何缺完整 trace/cursor 的 legacy retry open 都应 fail-close，但保护性 close 不能被迁移门禁饿死。

## 本次版本变更

- 新增 frozen `Stage904RunResult` 与 `run_intraday_monitor(...)`；CLI 保留原参数与兼容输出，`write_compat_outputs=False` 不写 actions/summary/report 文件。
- durable batch 路径不调用 `_read_committed_tick_snapshot`，只接受 `caught_up=True`、无 gap、`next_cursor == durable_through` 的完整 framed-v1 页面。
- 每条 canonical row 构造 Task4 `LatencyTrace`，状态与 action 锁存 trace JSON/ID、source feed/global ingress/symbol sequence、ingress epoch/monotonic、25 秒 deadline 和完整 commit cursor。
- `state_generation=position_epoch_id:trigger_revision` 在第一次状态转移时锁存；后续 tick、monitor run、重启、broker volume refresh 和 feed gap 均不得漂移。
- legacy pending 通过统一 state copy/load 迁移入口一次性锁定 generation；缺完整 trigger provenance 的 retry reclaim 不生成 pending open，并输出 P1 migration blocker；initial/retry protective close 继续可达。
- retry open 通过 strict `LatencyTrace.from_json` 校验，并交叉绑定 trace/feed/global ingress/symbol sequence/vt_symbol/ingress stamp/deadline、framed cursor schema，以及 state transition feed/seq/at。
- 删除有歧义的 per-trigger `source_journal_offset` 概念；只保留语义准确的 batch `durable_cursor_*`。
- mixed traced/watch action rows 从原始 dict 以 object dtype 重建 exact-int 列，避免 `>2^53` 纳秒或 offset 经 float64 静默损失。
- state journal append/fsync、snapshot commit 和 checkpoint 完成后才返回 ready action；恢复出的 pending action ID/state generation 与返回值一致。
- 新增参数：`durable_batch`、`clock`、`write_compat_outputs`，均为 callable 注入参数；没有新增生产策略参数。
- 修改参数：无。
- 删除参数：无。

## TDD、验证与独立终审

- RED：callable 缺失；trigger trace/cursor 未持久化；state generation 随后续 tick/legacy mutator 漂移；partial batch 可进入 reducer；legacy retry 缺 provenance 可重新 ready；trace 外层与 transition 可矛盾；mixed int/None 被 pandas 转成 float64。
- GREEN：state `24/24`、Stage904 integration `57/57`；Stage904/state/late-fill/Stage930/Stage905/Stage931 相关联合 `221/221`，用例耗时 `14.143s`、墙钟 `15.29s`。
- 静态验证：4 个文件 `py_compile` 与 `git diff --check` 通过。
- 冻结 SHA-256：
  - C9 state：`b8d4cff19af95345d71d2be95c32403e66e84094bf1859bcfb977525814c3e3b`
  - Stage904 monitor：`1e04bff089499de4b3cb57c34ddaee23b8e024589563dcc65c5daf5e08037714`
  - state tests：`cab49e96a94f013fcdc67935ade7eef9522d665650fd6f45d5e4545bd433594c`
  - integration tests：`f3c47350f29c694f6fa8a5fd8eae2dae5c1aefa83abb62d312c6c5263aa1d7c1`
- 独立终审：最终冻结对象 `P0=0、P1=0、P2=1`，独立重跑 state+integration `81/81`，此前发现的 partial cursor、legacy open、float precision、cross-field/transition tamper 均已关闭。
- 剩余 P2：durable-batch 模式仍单独重读 heartbeat；若 H1 batch 后仅其他品种更新为 H2，目标水位可能不变，Task5 还不能单体证明 H1 batch 与 H2 generation 同代。Task8 必须把 batch+heartbeat 作为一个 detector-cycle 输入，并在 spool commit 前做 exact generation/cursor CAS。

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

- 当前结论：Task5 代码具备合入条件；不代表已部署、已激活或能解决今晚端到端延迟。
- 资金口径：本阶段未修改资金/策略配置；SOP 的 Stage372 20万默认口径与当前官方配置中出现的 Stage847-C9 15万冲突仍未解决，必须在 Task8 deployment preflight 显式阻断而不是自动选边。
- 后续：进入 Task6，把 Stage904 in-memory 结果传给 Stage905，并在 Stage905 强制 25 秒绝对 deadline；Task8 再闭合 batch/heartbeat generation 与完整 cursor lineage。
- Task6-13、LaunchAgent/runtime、官方资金口径、严格 `0/0` 只读 CTP、SimNow 未全部通过前禁止真实报单。

## 过拟合反思

- 运行前：否。
- 运行后：否。
- 原因：所有约束来自状态版本、消息顺序、持久化 cursor 与数值精度，不使用 JM 当晚单样本或收益结果调参，可跨品种和周期复用。

## 继续价值反思

- 运行前：是。
- 运行后：是。
- 原因：Task5 已让“哪条 durable tick 触发了什么动作”可恢复，但尚未把同一证据安全传过 Stage905/spool/executor；继续做 Task6/8 才能把延迟归因和实时执行真正接通。

## 记录归属

- 是否更新 `LINE.md`：否；同线并行阶段只写唯一 stage 文件，合入时统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未达到正式候选激活门槛。
