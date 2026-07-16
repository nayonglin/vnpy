# Stage187 Stage179 Task7 WAL 优先级意图队列

## 基本信息

- 改动时间：2026-07-16 16:58 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 工作区：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability`
- 分支：`codex/stage179-live-execution-reliability`
- 基线提交：`b6a022e0748b4da9a6318cec74dad8083a19993d`
- 代码提交：`927caee717b2a5562a0498cb00a5c4075c9b1dd1`
- 是否重要突破版本：否。这是 Stage179 实盘执行可靠性的关键基础设施里程碑，但尚未完成 Task8-13、只读 CTP 与 SimNow 验收，不能称为可部署或可激活的正式突破版本。
- 实盘边界：未加载实盘 env，未连接 CTP，报单/撤单 API 为 `0/0`，未修改 LaunchAgent 或正式激活配置。

## 外部调研与判断

执行前复核了 SQLite 与 Python 官方资料：

- SQLite WAL：<https://www.sqlite.org/wal.html>
- SQLite PRAGMA，重点是 `synchronous`、`journal_mode` 与 `busy_timeout`：<https://www.sqlite.org/pragma.html#pragma_synchronous>
- SQLite transaction：<https://www.sqlite.org/lang_transaction.html>
- Python `sqlite3`：<https://docs.python.org/3/library/sqlite3.html>

判断结论：本地单机执行队列使用 SQLite WAL 是合适的，但可靠性来自显式事务、唯一业务身份、游标 CAS、租约状态机和账本证据的共同约束，不来自 WAL 名称本身。写路径统一使用 `BEGIN IMMEDIATE`，连接强制 `journal_mode=WAL`、`synchronous=FULL`、`foreign_keys=ON`、`busy_timeout=100`；写锁冲突必须显式失败，不能静默推进 detector cursor。

## 本次改动

### 新增

- 新增 schema-v1 SQLite intent spool：`qmt_roll_official_live_intent_spool.py`。
- 新增精确 schema fingerprint 与 metadata 校验，阻止同版本 schema 漂移。
- 新增 detector cursor CAS、完整 batch manifest 与 lost-ack 全批次幂等回放。
- 新增 close-first 租赁；存在 ready/leased/sending/unknown/blocked close 时禁止租赁 open。
- 新增绝对 deadline、clock-domain 与 monotonic rollback 的 fail-close 校验；发送前再次校验，过期 open 转 `expired`，关键 close 转 `blocked`。
- 新增 lease owner/token CAS、`leased -> sending -> sent/reconciled` 状态机及结构化恢复证据。
- 新增 sending/leased 过期恢复：只有明确 `no_side_effect` 可重新 ready；`unknown` 或 `side_effect_present` 均转不可重发的 `side_effect_unknown` 并保留原 owner/token，待账本确认后才能 CAS 对账。
- 新增 Stage904/Stage905/spool/executor 分段 trace observation；未持久化 `spool_committed` 的 intent 不可租赁。
- 新增业务 payload、trace 与数据库冗余列三方绑定，覆盖合约、feed/session sequence、symbol sequence、双 deadline、gateway ingress monotonic、clock domain、durable cursor、kind/priority 与 seed observation。
- 新增 socket wakeup；socket 丢失只影响唤醒，不影响已提交事务，轮询可恢复。
- 新增 33 项 spool 单元测试及 Stage905 真实产物写入真实 spool 的离线集成测试。

### 修改

- Stage905 输出增加稳定、canonical 的 `spool_payload_json` 与 `payload_sha256`；演进中的 trace observation 不参与业务身份 hash。
- Stage905 的 `stage905_intent_ready` 使用批次内同一个真实 stamp，回放保持 first-wins。
- Stage905 单测增加 canonical payload/hash、真实 spool 接入及重放边界。

### 删除

- 删除不可达且会误导调用方的 `blocked -> reconciled` 普通租约转换承诺；blocked 的单锁账本对账由 Task11 专用 API 接管。
- 未删除或调整任何 alpha、资金、止损、重进场、AI 池或选品参数。

## 参数变化

- 新增连接参数：SQLite `timeout=0.1s`、`busy_timeout=100ms`、`journal_mode=WAL`、`synchronous=FULL`、`foreign_keys=ON`。
- 新增执行状态：`ready`、`leased`、`sending`、`side_effect_unknown`、`sent`、`reconciled`、`expired`、`blocked`。
- 新增优先级：close=`0`，open=`1`。
- 修改参数：无 alpha 或资金参数修改。
- 删除参数：无。

## 验证结果

- spool 定向测试：`33/33`。
- Stage905 定向测试：`28/28`。
- Task7 + Stage905 独立终审定向测试：`61/61`。
- 相关执行链联合回归：`254/254`，耗时 `13.088s`。
- 双连接 lease 竞争：`100/100` 轮均恰好一个赢家。
- 独立终审额外篡改矩阵：9 个 payload/trace/冗余列/seed observation 篡改均 fail-close 并回滚 lease claim。
- `py_compile`、`git diff --check`：通过。
- 冻结文件 SHA256：
  - spool 实现：`6692945e102f8d8c0c8a35ebcca61e11a2a82b14acc451309ff6d0aec0d68893`
  - Stage905 实现：`af11f3d5011b51e491a8ffa94b88a3128b99987a2e5500f1b30d609bd5f984ed`
  - spool 测试：`4cfbaacc7e98a871c9a4d00a0c3ae74d394a45caa804936ddb997f647b1b21e8`
  - Stage905 测试：`a711872d085084a2a2116ee0d7d8ffc55fd4c39f7e6a09a9ede145e95f90d0bc`

## 独立审查

- 第一轮发现：`P0=0, P1=6, P2=3`，Task7 被阻断；问题包括发送前 deadline、leased open 与后到 close 竞争、trace 因果、sending recovery、NaN 外层输入、冗余列绑定、schema/游标/manifest 边界。
- 第二轮发现：`P0=0, P1=2, P2=0`，继续阻断；问题为 `side_effect_present` 后续对账不可达，以及持久化 trace 三方绑定不完整。
- 修复后第三轮终审：`P0=0, P1=0, P2=0`，允许提交 Task7。
- 终审只证明 Task7 可提交，不证明可部署、可激活或可真实报单。

## 回测结果

本阶段没有改变策略 alpha，也没有运行回测；因此以下指标均为不适用，不得沿用历史结果冒充本阶段结果：

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A
- 新增/修改/删除回测结果：无

## 反思与后续

- 是否过拟合：否。实现约束的是持久化、并发、时钟、幂等、截止时间和恢复不变量，不按日期、品种、方向或收益结果调参，具有跨周期意义。
- 是否仍值得继续：是。该层直接降低重复报单、过期报单、close 被 open 阻塞、崩溃恢复误判和审计证据断裂风险；但只有接入持久 detector、warm executor、单锁账本与故障注入后才形成端到端闭环。
- 下一步：按 Spec 执行 Task8，新增默认关闭的 Stage941 persistent detector 与 Stage930 进程所有权；persistent 模式在 Tasks10-11 前只允许 `dry-run + submit-disabled`。
- 硬门禁：继续完成 Task8-13、官方口径澄清、LaunchAgent/环境修复、独立终审、`0/0` 只读 CTP 与 SimNow 验收；全部通过前禁止真实报单。
- 记录隔离：本工作区只新增唯一 Stage187 文件，未修改同线 `LINE.md`、`research/registry.md`、根目录 `memory.md` 或 `back_log.md`。
