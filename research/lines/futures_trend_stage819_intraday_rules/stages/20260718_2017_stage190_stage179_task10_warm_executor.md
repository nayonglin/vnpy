# Stage190 Stage179 Task10 generation-bound warm executor 与 readiness lease

## 基本信息

- 改动时间：2026-07-18 20:17 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 工作区：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability`
- 分支：`codex/stage179-live-execution-reliability`
- 基线提交：`7a1ce0e`
- 代码提交：`9cead40566b15ae4ed334263d0ebbd0e45062b58`
- 是否重要突破版本：否。Task10 已达到代码可提交条件，但仍是默认关闭的执行基础设施；Task11-13、官方口径冲突、真实只读 CTP、SimNow、LaunchAgent 和端到端 SLA 验收尚未完成，不能称为线上实盘版本。
- 实盘边界：没有加载真实 env，没有导入或连接 CTP/SimNow，没有调用真实报单或撤单 API；全部验证为离线 `send=0/cancel=0`。

## 外部调研与判断

执行前复核了官方资料：

- Python `time.monotonic_ns`：<https://docs.python.org/3/library/time.html#time.monotonic_ns>
- Python socket timeout：<https://docs.python.org/3/library/socket.html#socket.socket.settimeout>
- Python threading/Lock：<https://docs.python.org/3/library/threading.html#lock-objects>
- vn.py MainEngine：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/engine.py>
- vn.py CTP gateway：<https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py>

判断结论：warm executor 必须由单一服务持有一条 CTP 连接，但每个 intent 必须重新查询 fresh bundle；连接可复用不代表 readiness 可永久复用。授权应绑定 service/connection generation，断连先撤销内存和磁盘 lease，再重连生成新 generation。所有等待与查询共享一个 monotonic 绝对 deadline，socket 只负责低延迟唤醒，SQLite spool 才是事实源。该设计不依赖 JM 当晚样本，也不修改策略 alpha。

## 本次改动

### 新增

- 新增 `qmt_roll_official_live_execution_service.py`：提供 singleton `flock`、Unix datagram 唤醒、0.1 秒轮询兜底、SQLite intent spool lease、readiness 原子发布/撤销和 warm serve loop。
- 新增 `TdReadinessLease`、`ExecutorServicePaths`、`ExecutionResult`，readiness 绑定 service generation、connection generation、runtime profile、官方版本、资金和有效期。
- 新增 `CtpExecutionSession`：单连接复用、startup bundle、断连 sticky generation invalidation、重连新 UUID、每 intent fresh bundle、Q2 tick/watermark、最终状态与 pre-API-slot gate。
- 新增 absolute deadline：ingress→send 25 秒、dequeue→send 20 秒；各 query/wait 共享同一 hard deadline，耗尽时在 API slot/send 前 fail-close。
- 新增行为级 CLI/serve 测试，覆盖 one-shot 向后兼容、warm profile/submit 明确授权、单连接双 intent、两次 fresh bundle、旧 generation 失效、断连撤销、deadline、dequeue SLA、socket 丢失、close priority、readiness replace 失败和 singleton 拒绝。

### 修改

- Stage931 增加 `--command {once,serve}`，默认 `once`；legacy one-shot 保持原行为，serve 的交易日期从 spool intent 读取。
- CTP gateway 继续延迟动态导入；runtime/release/activation/submit/env/policy gate 全部通过前不得导入或连接。
- SimNow、broker-test 和 production submit 都要求 Phase-D real adapter/submit env、精确 `--confirm-live-real` 和完整 CTP env，不再允许测试 profile 隐式进入提交态。
- final readiness/query/snapshot/post-reprice helper 接受共享 hard deadline，并在每个阻塞 I/O 前检查预算。
- tick/order/trade/log buffer 改为有界；每个 intent 完成后清理 context，避免常驻服务内存无界增长。
- Stage905 canonical nested `order_request` 在 Stage931 lease 入口物化为 legacy validator 所需字段，防止合法官方 intent 被误阻断。
- release manifest 默认 critical closure 纳入新增 execution service。
- 测试临时 Git 仓库使用 `TemporaryDirectory(ignore_cleanup_errors=True)`，只容忍 macOS teardown 的外部目录清理竞态，不吞测试主体断言或 Git/manifest 失败。

### 删除

- 未删除或修改任何 alpha、AI 池、资金、止损、重进场或选品规则。
- 未删除 legacy one-shot 路径。
- 未生成 activation receipt，未修改真实 env、LaunchAgent 或线上进程。

## 参数变化

- 新增 `--command {once,serve}`，默认 `once`。
- 新增 hard limits：dequeue `0.5s`、dequeue→send `20s`、ingress→send `25s`、readiness heartbeat `1s`、readiness TTL `3s`、spool poll `0.1s`。
- 修改参数：无 alpha、资金、止损、重进场或选品参数修改。
- 删除参数：无。

## 验证结果

- Task10 定向测试：`21/21`，耗时 `0.128s`。
- 最终关联联合回归：`290/290`，耗时 `18.236s`。
- macOS 临时 Git teardown 竞态修复：隔离重复 `5/5`，联合回归同步通过。
- `py_compile`：通过。
- 新增执行核心 `ruff --ignore B905`：通过。
- `git diff --check`：通过。
- 初次联合回归使用共享解释器时被 trader-dir startup guard 拒绝，未收集测试；按仓库已有测试豁免 `QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1` 重跑。该豁免只用于纯内存 fake 测试，未访问真实数据库、env 或 CTP。
- 订单 API：send `0`、cancel `0`。
- 代码提交：`9cead40566b15ae4ed334263d0ebbd0e45062b58`。

## 独立审查

- 初审发现并关闭 3 个 P1：Stage905 canonical spool payload 与 Stage931 legacy validator 不兼容；常驻 tick/log/order/trade buffer 无界；SimNow/broker-test serve 缺少与 production 等价的显式 submit/env 授权。
- 同步关闭 close attempt token/API-slot CAS 和 0.5 秒 dequeue SLA 接线缺口。
- 最终冻结结论：`P0=0, P1=0, P2=2`；code-submit eligible，live-activation not eligible。
- 剩余 P2-1：SHFE/INE 混合今昨仓会产生多个 physical child，warm 路径当前对多 child 明确 fail-close；Task11 必须完成 multi-child batch API-slot CAS 后才可讨论全量激活。
- 剩余 P2-2：3 秒 readiness TTL 定义为外部 heartbeat lease；intent 已在有效 lease 下开始后，内部以 connection generation 与 transport 重验保护，不用 TTL 中断最长 20 秒 fresh bundle。该语义必须写入运行契约，并通过真实断连与延迟验收。
- 原测试夹具 teardown P2 已由 `ignore_cleanup_errors=True` 关闭；独立复核确认不放宽产品断言。

## 回测结果

本阶段没有改变策略 alpha，也没有运行回测；以下指标均为不适用：

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A
- 新增/修改/删除回测结果：无

## 反思与后续

- 开始前是否过拟合：否。目标是连接代际、绝对 deadline、持久队列与 fail-close 的跨周期执行不变量，不根据单日延迟、单品种或收益曲线调参。
- 完成后是否过拟合：否。所有改动停留在执行可靠性、资源边界和授权链，没有反馈到 alpha、AI 池或仓位参数。
- 是否仍值得继续：是。Task10 消除了每 intent 冷连接和无界阻塞的一类结构性风险，但还没有真实运行证据，也没有完成 API-slot 后的单锁 crash recovery。
- 下一步：按 Spec 执行 Task11，把 spool lease、ledger batch API-slot、sending/sent/unknown/reconciled 和 multi-child close recovery 归并到同一持久锁与恢复决策中。
- 硬门禁：Stage372/20万与 Stage847-C9/15万口径冲突、Stage927/broker freshness、Tasks11-13、真实 `0/0` 只读 CTP、SimNow、LaunchAgent 和端到端 SLA 验收全部完成前，Stage179 warm production-live 禁止激活。
- 对“能否解决今晚 21:00 延迟”的结论：代码层已消除冷连接、轮询迟滞和分散 deadline 的主要结构性来源，但在真实部署和 SimNow/CTP SLA 证据完成前，只能说“具备解决条件”，不能说“已经解决线上延迟”。
- 记录隔离：本工作区只新增唯一 Stage190 文件，未修改同线 `LINE.md`、`research/registry.md`、根目录 `memory.md` 或 `back_log.md`。
