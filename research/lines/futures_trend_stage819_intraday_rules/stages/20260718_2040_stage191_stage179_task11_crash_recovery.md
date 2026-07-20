# Stage191 Stage179 Task11 spool/ledger 单锁恢复与多子单原子 API-slot

## 基本信息

- 改动时间：2026-07-18 20:40 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 工作区：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability`
- 分支：`codex/stage179-live-execution-reliability`
- 基线提交：`8979aea22`
- 代码提交：`dc84359cd047eefe13564153e1b4c90d6a4b5e24`
- 是否重要突破版本：否。Task11 关闭了 warm executor 的 crash-recovery 与 SHFE/INE 多子单防重缺口，但仍无真实只读 CTP、SimNow、LaunchAgent 或端到端 SLA 证据，不能视为线上实盘版本。
- 实盘边界：未加载真实 env，未导入或连接 CTP/SimNow，未调用真实报单或撤单 API；验证全部为离线 `send=0/cancel=0`。

## 外部调研与判断

执行前复核了官方资料：

- SQLite transaction/`BEGIN IMMEDIATE`：<https://www.sqlite.org/lang_transaction.html>
- Python 3.11 `sqlite3` transaction control：<https://docs.python.org/3.11/library/sqlite3.html#transaction-control>
- SQLite WAL：<https://www.sqlite.org/wal.html>

判断结论：API-slot 是外部副作用的不可逆分界。slot 前只在有精确 reservation/lease 证据且没有任何 API/broker 证据时允许重排；slot 后即使 `send_order` 没有返回、spool CAS 失败或审计落盘失败，也只能进入 reconciliation-only。ledger 的 parse、integrity、fingerprint/alias、分类和 safe-terminal append 必须在同一个 `LOCK_EX` 中完成；expired spool scan 只需 SQLite 单条只读快照，真正变更仍由 owner/token/state CAS 完成。

## 本次改动

### 新增

- 新增 `EXECUTION_LEDGER_READER_CAPABILITIES`，包含 schema、V1/V2 fingerprint、close UUID lease、batch API-slot CAS 和 spool crash recovery 能力。
- 新增 `LedgerRecoveryDecision` 与 `recover_expired_spool_lease`：区分 `requeue_pre_send`、`reconcile_only_side_effect_unknown`、`reconciled` 和 `blocked_ledger_integrity`。
- matching reservation 且无 API 证据时 append-once `spool_crash_recovery_pre_send_safe_terminal`；并发恢复只能有一个写入赢家。
- 新增 expired inflight 只读扫描，close 优先、spool sequence 稳定排序；恢复证据包含 fingerprint、ledger watermark、checksum、owner/token 和 clock stamp。
- 新增 `BrokerSendBatchResult`/`BrokerSendBatchError`，精确记录多子单实际 broker 调用次数，空返回、发送异常、发送后审计异常均为 side-effect unknown。

### 修改

- warm executor 顺序固定为：ledger batch API-slot durable → spool `leased→sending` CAS → broker calls。CAS 返回非 sending 或抛错时禁止 send，服务保留运行并交由过期 lease 恢复。
- Stage931 支持 SHFE/INE close-today/close-yesterday 多 physical child：一次性全量 quota CAS，每 child 带稳定 index/count/id/offset/volume，逐 child 最多调用一次。
- reservation、API-slot、成功返回和异常审计绑定 service generation、connection generation、spool lease owner/token。
- 完整成交恢复按具名 trade identity 去重；匿名 fill 只采用单行最大量，禁止多行匿名或匿名/具名混合累加成虚假全成。
- V1 只接受无歧义 alias；retry-stop 等歧义 fingerprint 即便 owner/token 相同也进入 unknown，禁止重排。
- safe-terminal 后若出现更晚 API-slot/broker 证据，后者优先，恢复结果必须为 unknown/reconciled。
- 所有 expired intent 分类完成后只读取一次最终 ledger evidence snapshot，再逐 lease 做 spool CAS，避免每 intent 额外整表读取。

### 删除

- 删除 warm executor 对“只能一个 physical order”的限制。
- 删除 expired inflight scan 的 `BEGIN IMMEDIATE`，改为单条只读 SELECT，减少 10Hz 空轮询 writer 竞争。
- 未删除或修改任何 alpha、AI 池、资金、止损、重进场或选品规则；legacy one-shot 主流程保持不变。

## 参数变化

- 新增参数：无用户可见策略参数。
- 修改参数：无 alpha、资金、止损、重进场或选品参数修改。
- 删除参数：无。

## 验证结果

- Task11 ledger recovery 定向：覆盖无证据、matching reservation、并发 safe-terminal、batch API-slot、所有 post-slot evidence、terminal fill、checksum/decode 错、V1 alias、歧义 retry-stop、重复具名/匿名 fill 和 side-effect precedence。
- Task11 关联账本/队列/执行/Stage931 回归：`200/200`，耗时 `1.918s`。
- 扩大联合回归：`343/343`，耗时 `19.804s`。
- `py_compile`：通过。
- `ruff --ignore B905,UP035`：通过；`UP035` 是既有 intent spool import 风格，不是本阶段新增问题。
- `git diff --check`：通过。
- 订单 API：send `0`、cancel `0`。
- 代码提交：`dc84359cd047eefe13564153e1b4c90d6a4b5e24`。

## 独立审查

- 第一轮发现 2 个 P1：重复 `vt_tradeid` fill 被累加为全成；歧义 V1 retry-stop alias 在存在同 lease 证据时仍可能重排。两项均修复并增加最小复现回归。
- 第二轮发现匿名 fill 无 identity 时仍可逐行累加；改为具名 identity 去重求和、匿名只取单行最大量，并禁止混合相加。
- 同步关闭 3 类 P2：API-slot 后真实 spool CAS mismatch 杀死服务；send/append 异常调用数丢失或缺 generation；expired scan writer 竞争与每 intent 额外 ledger reread。
- 最终冻结结论：`P0=0, P1=0, P2=0`；code-submit eligible，live-activation not eligible。

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

- 开始前是否过拟合：否。目标是事务边界、唯一 identity、幂等恢复和副作用不可逆性，不使用 JM 单晚样本或收益曲线调参。
- 完成后是否过拟合：否。实现适用于所有品种、方向和 close-today/close-yesterday 组合，没有改变 alpha 或仓位参数。
- 是否仍值得继续：是。Task11 已把 crash 微窗从“可能重发”收敛为“slot 后只对账”，但离线状态机正确不等于真实 CTP 时序正确。
- 下一步：按 Spec 执行 Task12，接入 Stage930 常驻 executor owner、LaunchAgent/supervisor 生命周期、分段 SLA 与故障注入，保留 legacy-once 回滚入口。
- 硬门禁：Stage372/20万与 Stage847-C9/15万口径冲突、Stage927/broker freshness、Tasks12-13、真实 `0/0` 只读 CTP、SimNow、多子单真实回报、LaunchAgent 和端到端 SLA 验收全部完成前，Stage179 warm production-live 禁止激活。
- 对“能否解决今晚 21:00 延迟”的结论：Task10-11 已消除冷连接、分散 deadline、slot/CAS 崩溃重发和多子单阻断等结构性原因；但真实部署与 CTP/SimNow 证据未完成，因此仍只能说“代码具备解决条件”，不能说“线上已经解决”。
- 记录隔离：本工作区只新增唯一 Stage191 文件，未修改同线 `LINE.md`、`research/registry.md`、根目录 `memory.md` 或 `back_log.md`。
