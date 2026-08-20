# Stage224：实盘常驻链路订单 API 证据闭环

- 改动时间：2026-08-18 00:42（Asia/Shanghai）
- 是否重要突破：否；这是生产执行证据契约修复，不改变 C9 alpha、信号、品种、方向、手数、0.5R 或一次重试参数。
- 背景：Stage223 激活后，实盘常驻链路能够启动，但 Stage905 缺总订单 API 计数、Stage903 未透传 native API 计数、Stage931 warm readiness 未发布累计订单 API 计数。Stage930 因证据不完整按 fail-closed 阻断 AP/Si 和日内止损授权。
- 账户事实：`jm2609.DCE` 多头 2 手为用户人工成交；Stage905 既有 `skipped_existing_broker_position` 规则负责避免同方向重复开仓。本阶段不修改或伪造影子持仓，不补发 JM。

## 代码改动

- Stage905 summary 新增 `order_api_called_count = send + cancel`。
- Stage903 summary 显式透传 `native_mutation_api_attempted_count`、`native_mutation_api_called_count`、`order_api_attempted_count`。
- Stage931 warm readiness 新增 `service_kind=warm_live_executor` 与累计 send/cancel/total API 计数；计数来自唯一 CTP session owner 内、同一 ingress RLock 保护的原生 `reqOrderInsert` / `reqOrderAction` 调用边界。即使原生调用返回非零或抛异常，只要调用已越过边界就计数；计数源缺失或非法则 evidence fail-closed。
- Stage930 对 live warm readiness 做严格类型、非负、总数一致性和 evidence-complete 校验；任一缺失或不一致继续 fail-closed。
- Stage930 明确区分 `warm` 进程生命周期累计值与 `legacy-once` 单次增量：warm 在 slow-command fast lane、idle fast lane、单轮和 daemon 多轮均取单调累计最大值，避免把同一个 Stage931 计数重复相加；legacy-once 继续求和。
- Stage931 的 `_readiness_blockers` 在 fresh bundle、API slot 和最终 send 前均验证 `service_kind`、evidence complete、非负整数与 `total=send+cancel`；计数证据异常不能只等 Stage930 下一轮发现，而是执行器自身立即阻断。
- Stage930 warm 汇总绑定 `service_generation`：同一 generation 取累计最大值，不同 Stage931 重启 generation 分组求和；cycle 保存 generation 明细，daemon 最终再次检查 `total=send+cancel`。这样既不重复计数，也不漏掉重启前的调用。
- 没有新增、删除或移动任何 `send_order` / `cancel_order` 调用。

## 验证

- TDD 第一轮红灯：新增测试最初因缺少 `_live_warm_order_evidence` 和 readiness 字段失败。
- 独立复审第一轮发现：撤单计数被写死为 0，且 Stage930 把 warm 生命周期累计值按循环重复求和；结论 `P0=0/P1=1/P2=1, NOT READY`，未据此激活。
- TDD 第二轮红灯：原生 send+cancel 快照 helper 缺失、readiness 不接受原生计数源、warm 单轮把 `1/1/2` 重复累计为 `3/3/6`、daemon 累计 helper 缺失；四项均按预期失败。
- 独立复审第二轮发现：Stage931 自身发送前还未消费 evidence-complete，且不同 `service_generation` 不能只取全局 max；结论 `P0=0/P1=2/P2=0, NOT READY`，继续未激活。
- TDD 第三轮红灯：不完整 readiness 实际 disposition 为 `sent`；跨 generation `5/0/5 + 1/1/2` 被错误聚合为 `5/1/5`。修复后分别变为发送前 `blocked` 与正确 `6/1/7`。
- 第三轮定向回归：5/5 通过；Stage931 readiness / executor service / Stage930 fast lane 完整相关回归：193/193 通过。
- 正式候选 32 个生产测试套件：844/844 通过，另有 692 个 subtests 通过；失败 0、错误 0、跳过 0。
- `py_compile`、5 模块 import smoke、`git diff --check` 通过；新增订单 API 调用 diff 扫描无命中。
- 本阶段未连接 CTP、未报单；修改前已精确 bootout night-session，Stage930/931/tick/detector 子进程全部归零。
- 第三轮独立复审结论：`P0=0/P1=0/P2=0, READY`；独立相关测试 `274/274` 通过，确认 Stage931 fail-closed、Stage930 generation-aware 聚合、JM skip、AP/SI 与 0.5R/一次重试路径均闭环，且无新增生产订单 API 调用点。
- 在提交新候选、两次正式只读 qualification 和 Stage948 原子激活前，实盘仍保持停止。

## 运行预期

- 2026-08-18 日盘 09:00–09:05：Si 初始开仓仅在 fresh tick、fresh readonly、Stage902/927、exact authorization 和最终 broker/tick gate 全部通过时提交。
- AP 平仓与后续 0.5R 实时止损走 reduce-close scope；不依赖 broker-shadow 全局一致才能降风险，但仍要求当前账户、持仓、订单、tick 和订单 API 证据完整。
- 已存在的人工 JM 2 手会使对应 Stage901 pending open 被 Stage905 标为 `skipped_existing_broker_position`，不得重复开仓。

## 反思

- 是否过拟合：否。只修执行证据完整性，不根据单日盈亏或单品种表现调整策略。
- 是否值得继续：是。没有该闭环，系统虽安全但无法自动交易；完成独立复审、两次正式只读 qualification 和 Stage948 原子激活后，才有资格恢复实盘。
