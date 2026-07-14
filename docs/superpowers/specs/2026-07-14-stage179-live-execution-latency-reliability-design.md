# Stage179 实盘执行低延迟与可靠性设计

**状态：** 对话设计已于 2026-07-14 获得用户批准；本文等待用户书面复核后进入实施计划。

**目标：** 将现有 Stage179 执行可靠性候选推进为“可安全合入、默认不激活、可分阶段验证”的正式候选，并把行情进入系统到报单、回报和落账的延迟变成可证明、可故障注入、超限即失败关闭的工程指标。

## 1. 背景与根因

2026-07-14 JM 实时止损已经完成自动平仓，但现有证据只能确认 Stage904 产生止损动作、约 14:43:56 发单、约 14:43:57 成交，不能恢复精确的“阈值穿越 tick”。当次外层 Stage608 运行约 22.390 秒，Stage903 运行约 135.889 秒，说明分钟级延迟的主要来源是串行控制链路，而不是 CTP 单次报单本身。

候选代码的独立复核又发现更底层的 P1：Stage608 在 EventEngine 消费回调中生成 `received_at`，同一回调还同步执行 `open/flock/json/write/flush`。vn.py EventEngine 是单消费者线程，因此磁盘或其他 handler 积压时，旧 tick 会在出队时得到一个新的时间戳，既扩大积压，也可能绕过 Stage904 的 freshness 判断。

本设计同时处理两个层面：

1. 修正行情时间因果和同步 I/O 阻塞，保证旧 tick 不能伪装成新 tick。
2. 消除 Stage904/905 周期性冷启动和 Stage931 每单冷连 CTP 的结构性延迟，建立统一端到端 deadline。

## 2. 范围和非目标

### 2.1 本次范围

- Stage608 行情入口双时钟、序列、异步耐久写入、显式 gap 和 readiness。
- Stage904/905 常驻检测链路和耐久优先级 intent spool。
- Stage931 预热 TD 执行模式、fresh broker-state 复验和 at-most-once 发送语义。
- 全链路 trace、分段 SLA、故障注入和离线压力测试。
- runtime profile、代码合入与实盘激活隔离、LaunchAgent 生命周期和可兼容回滚。
- 阶段化的离线、只读 CTP、SimNow/券商测试和后续一手 canary 门禁。

### 2.2 非目标

- 不修改 C9/Stage847 的任何 Alpha、AI 池、产品池、止损阈值、重进场次数、仓位或资金参数。
- 不用回测收益证明执行层正确；本次不运行策略回测。
- 不承诺市场一定成交。系统只承诺检测、发送、首个 broker ack、撤单和对账的时限。
- 不在本设计批准或代码合入时自动发送真实订单。
- 不用本次代码修改替代“Stage372/20w 与 Stage847-C9/15w”运行口径的显式运营确认。

## 3. 方案选择

### 3.1 已选择方案：分故障域的常驻链路

采用以下数据流：

```text
CTP MD gateway ingress
  -> 有界非阻塞内存队列
  -> Stage608 异步单写者 / durable watermark
  -> 常驻 Stage904 检测器 + Stage905 确定性 intent builder
  -> SQLite WAL 高优先级 intent spool
  -> 预热 Stage931 TD executor
  -> broker callbacks / execution ledger / reconciliation
```

MD、检测器和 TD executor 保持独立故障域。任何一个故障都必须撤销相应 readiness；新开仓过期即丢弃，保护性平仓则耐久保留、阻断新风险并要求 fresh broker state 后重新验证，不能盲发也不能静默消失。

### 3.2 未选择方案

- **只补入口时间戳：** 能修正 freshness 因果，但同步磁盘 I/O、无界积压、子进程冷启动和冷 CTP 连接仍在，不能解决分钟级延迟。
- **只保留 Stage930 fast lane：** 能绕开慢 Stage903，但周期仍是 `Stage904 服务时间 + Stage905 服务时间 + 可选 Stage931 服务时间 + sleep`，没有统一 deadline，也不能证明秒级执行。
- **把所有逻辑放进一个进程：** 延迟最低，但 MD、策略检测和真实报单共享故障域；任何异常都可能同时破坏行情、状态和执行安全，不接受。

## 4. 全局安全不变量

1. 所有真实报单能力默认关闭；没有显式 runtime profile、激活门、官方版本 manifest 和原有 real-submit 门禁时，order adapter 不得实例化。
2. `review` 风险状态只能平仓、减仓或对账，不能新开仓；未知风险状态失败关闭。
3. CTP broker/SimNow fresh snapshot 是执行账户事实源，历史 shadow 持仓不是。
4. 行情 freshness 只允许使用 gateway ingress 时间；EventEngine handler 时间只作排队诊断。
5. sequence gap、队列溢出、journal 写盘失败、时钟回退、generation 不一致或 durable watermark 超龄时，feed readiness 必须撤销。
6. `send_order` 抛错、返回空值或 ack 超时一律视为“副作用未知”，禁止自动重发。
7. intent spool 负责耐久传输，execution ledger 继续负责 lease/CAS、发送副作用和去重；spool 不能绕开 ledger。
8. 保护性 close 的优先级高于 open，open backlog 不得阻塞 close。
9. 代码合入与 LaunchAgent 激活是两个独立动作。候选代码即使合入主分支，新增路径也必须保持默认关闭。
10. 若生产 ledger 已出现 V2 reservation、API slot、send、cancel、fill 或 unknown-side-effect 记录，禁止回退到只理解 V1 的旧 reader。

## 5. 组件设计

### 5.1 Stage608 gateway ingress 与异步单写者

Stage608 包装实际 gateway 实例的 `on_tick`。在调用原始 `BaseGateway.on_tick`、进入 EventEngine 队列之前，构造不可变 tick row，并写入：

- `feed_session_id`
- `ingress_sequence`（会话全局严格递增）
- `symbol_sequence`（单合约严格递增）
- `received_at_utc`
- `ingress_epoch_ns`
- `ingress_monotonic_ns`
- `handler_received_monotonic_ns`（仅在 EventEngine handler 观测时补充，不能用于 freshness）

入口只允许字段复制、序列分配和 `put_nowait`，不得做文件、锁、JSON 编码、网络或等待操作。默认队列容量为 `8192`。异步唯一 writer 按最多 `256` 条或最多等待 `50ms` 成批写 NDJSON，执行 `flush + os.fsync` 后才推进 durable watermark、ring snapshot 和 heartbeat。

队列满时 callback 必须立即返回，同时锁存 overflow、记录首尾缺口序列并撤销 readiness；不得静默丢 tick 后重新变绿。writer 错误同样锁存 fault，只有新 `feed_session_id` 完整启动后才能恢复。

启动时先发布 `starting/unready`。优雅停止顺序为：禁止新 ingress、关闭 MD、最多等待 `2s` drain、fsync、发布 `stopped`。若上次 segment 存在半行或未校验尾部，新进程隔离或截断坏尾、创建新 session，并在 heartbeat 披露上个 session 的未提交区间。

### 5.2 常驻 Stage904/905 检测器

Stage904 的 reducer 和 Stage905 的 intent builder 被提取为可重复调用的确定性模块，现有 CLI 继续作为离线/回滚入口。Stage930 启动一个常驻 detector worker：

1. 只消费 Stage608 已 fsync 的 durable cursor。
2. 按 `(feed_session_id, ingress_sequence)` 增量处理，不重复读取整份 CSV。
3. 先提交 Stage904 状态/WAL，再构造 Stage905 ready intent。
4. 对相同输入和状态必须产生相同 `intent_id`。
5. 每个 intent 带统一 `trace_id`、官方版本、资金口径、风险状态、源 tick cursor、state generation 和绝对 deadline。

检测器发生 backlog、WAL 错误、cursor gap 或 deadline 超限时：open 直接过期；close 写入 blocked/critical 状态、停止全部新风险，并等待 fresh broker state 后重新验证。

### 5.3 耐久优先级 intent spool

使用 Python 标准库 SQLite，启用 WAL 和 `PRAGMA synchronous=FULL`。spool 是独立状态目录中的单数据库，至少包含：

- `intent_id TEXT PRIMARY KEY`
- `trace_id TEXT NOT NULL`
- `priority INTEGER NOT NULL`，close 为 `0`，open 为 `1`
- `intent_kind TEXT NOT NULL`
- `payload_json TEXT NOT NULL`
- `created_epoch_ns`、`deadline_epoch_ns`
- `state`：`ready/leased/sending/side_effect_unknown/sent/reconciled/expired/blocked`
- `lease_owner`、`lease_expires_epoch_ns`
- `official_version`、`capital`、`runtime_profile`

ready intent 必须先事务提交，再通过本机 Unix socket 唤醒 Stage931。socket 只是低延迟提示，SQLite 才是事实源；socket 消息丢失时 executor 仍按短周期扫表恢复。close 按优先级和创建时间出队；open 不得占用 close 的唯一执行槽。

### 5.4 Stage931 预热 TD executor

Stage931 增加常驻 `serve` 模式，启动后建立 CTP 连接、完成认证/登录/结算/合约/账户/持仓准备，并持续维护只读 readiness lease。现有一次性模式保留为离线/兼容入口，但不作为低延迟正式路径。

收到 intent 后必须依次：

1. 校验 runtime profile、官方版本 manifest、deadline、risk、kill switch 和 TD readiness lease。
2. 在 execution ledger 取得 intent lease/CAS。
3. 获得 fresh 的 order-position-order 查询 bundle。
4. 取得 Q2 后 causal tick，并再次检查 broker order/trade/position watermark。
5. 原子预留 batch API slot。
6. 将 spool 标为 `sending`，调用一次 `send_order`，并立即把结果或 unknown side effect 写入 ledger。
7. 通过 order/trade callback 更新 ack、fill、cancel、late-fill 和 reconciliation 状态。

断线立即撤销 readiness。重连后必须重新完成结算、合约、账户、持仓和 active order/trade 全量查询，旧 lease 不得跨 connection generation 使用。

### 5.5 全链路 trace 与 SLA

每个阶段记录同一 `trace_id/intent_id`，同时保存 UTC epoch 和 monotonic 时间：

- gateway ingress
- journal durable
- Stage904 detected
- Stage905 intent ready
- spool committed
- executor dequeued
- broker bundle ready
- `send_order` called
- first broker order ack
- first fill
- cancel terminal
- ledger durable

monotonic 时间只在同一主机启动周期内比较；跨重启审计使用 UTC epoch、session/generation 和 durable cursor。任何 required timestamp 缺失都使该样本不能计入 SLA 通过率。

初始上线 SLO 与硬截止如下：

| 分段 | p99 SLO | 硬截止与动作 |
| --- | ---: | --- |
| ingress → durable tick | 0.5s | 1s，撤销 feed readiness |
| durable tick → Stage904 intent | 0.5s | 1s，阻断并报警 |
| Stage904 intent → Stage905/spool durable | 0.25s | 0.5s |
| spool ready → executor dequeue | 0.1s | 0.5s；close backlog 为 critical |
| dequeue → `send_order`（保留双 O-P-O） | 15s | 20s；intent 过期，不补发 |
| ingress → `send_order` | 17s | 25s；不得在一分钟后补发 |
| send → first broker ack | 2s | 3s；超时标记 side-effect unknown |
| send → first fill | 条件性 p99 5s | 不承诺成交；8s 后处理残单 |
| cancel → terminal/reconcile | 8s | 10s |
| fill → durable ledger | 0.5s | 2s |

只有在单写者账户约束和足够 SimNow/实盘证据成立后，才允许把 `dequeue → send` 收紧到 p99 `3s`、硬截止 `5s`；本次不通过减少安全查询来追求该目标。

### 5.6 Runtime profile 与激活隔离

引入强类型 `ExecutionRuntimeProfile`：

- `offline`
- `production-readonly`
- `simnow`
- `broker-test`
- `production-live`

每个 profile 固定 env 来源、Mac framework 优先级、允许的 order scope、确认字符串和独立输出目录。profile 冲突、env 来源混用或输出目录指向生产状态时直接退出。

`production-live` 在原有 real-submit 开关之外，再要求默认关闭的 Stage179 激活门和不可变 release manifest。manifest 必须包含官方版本、资金、源 commit、代码树 fingerprint、ledger schema/reader capability 和 runtime profile；启动时逐项一致才可继续。

当前 `AGENTS.md` 的 Stage372/20w 默认与 registry、SOP、`qmt_roll_official_live_config.py` 的 Stage847-C9/15w 存在口径冲突。本次代码不得擅自改资金或策略；在运营方明确并使规范一致前，`production-live` 激活失败关闭。`offline`、独立输出的 no-submit canary 和严格 `0/0` 的只读 CTP 验收不受影响。

首次发布继续使用已验证的直接 Python LaunchAgent，让 Stage930 内部拥有并监管子进程。候选 shell supervisor 必须补 TERM 超时和进程组 KILL，但在独立 no-submit launchd canary 通过前不得替换生产 plist。

## 6. 故障与恢复语义

- **正常重启：** 停 ingress、drain/fsync、撤销 readiness；detector 和 executor 从 durable cursor/spool/ledger 恢复。
- **SIGKILL/主机故障：** 只保证已 fsync 行和已提交 SQLite 事务；queued 或当前未 fsync batch 允许丢失，但下一次启动必须披露 sequence gap 并保持 unready。
- **磁盘满或 fsync 失败：** MD feed、detector 和新风险全部失败关闭；不得降级为仅 flush。
- **spool lease 超时：** 先查 execution ledger。若存在 API slot/send/unknown evidence，不得重新 lease 给另一个 sender；只允许对账。
- **broker ack 超时：** 标记 side-effect unknown，停止该 intent 自动重试，查询 active order/trade/position 后人工或确定性收敛。
- **人工下单竞态：** Q2 后任何 order/trade watermark 变化使 intent 失效；重新获得 fresh bundle 前不得发送。
- **版本或资金不一致：** startup fail-close；不允许从旧历史 profile 自动 fallback。

## 7. 测试与验收

### 7.1 TDD 必测回归

1. gateway 已入队、EventEngine 被阻塞时，ingress 时间保持入队前值，handler 时间晚于阻塞边界。
2. journal writer 被人为阻塞时，EventEngine sentinel 仍能及时消费。
3. 容量为 1 的队列溢出时 callback 非阻塞、gap 范围准确、readiness 不会自动恢复。
4. fsync 完成前 durable watermark 不得前移。
5. 优雅停止零丢失；半行尾部重启时隔离坏尾、创建新 session 并披露 gap。
6. 全局队列淘汰目标合约时，单合约 sequence/gap 能阻断 Stage904，不能因空 frame 漏检。
7. 虚拟时钟覆盖 Stage904/905 backlog、intent 过期和 25 秒端到端 hard deadline。
8. SQLite spool close 优先、去重、lease 回收和 socket 消息丢失恢复。
9. Stage931 覆盖断线、乱序 callback、部分成交、撤单后 late fill、send 返回空、ack 超时和 crash/restart；同一 intent 最多一次 `send_order`。
10. runtime profile 混用、manifest 不一致和默认激活门均拒绝加载 order adapter。
11. supervisor 收到 TERM 后在有限时间内退出；超时必须升级到进程组 KILL。

### 7.2 离线性能门

使用 fake gateway，不连接 CTP：20 个合约、`2,000 tick/s`、持续 `60s`。

- 正常盘 zero silent drop、zero sequence gap。
- ingress wrapper p99 `<=1ms`，max `<=5ms`。
- 每批注入 `25ms` 写盘延迟时，EventEngine sentinel p99 `<=20ms`，max `<=100ms`。
- durable lag p99 `<=100ms`，max `<=500ms`。
- 结束后 `2s` 内 drain 完成。
- RSS 增长 `<=64MiB`。
- 故意溢出时 fault latch `<=10ms`，readiness 撤销 `<=1s`，且绝不出现 `drop>0 && stream_ready=true`。

### 7.3 分阶段发布门

- **P0 离线：** 所有 TDD、故障注入、压力、静态和原 Stage179 回归通过；duplicate send 为 0。
- **P1 只读 CTP：** 至少 5 个完整日/夜盘会话和一次断线重连；order API 严格 `send/cancel=0/0`；callback、readiness、队列和 SLA 可观测。
- **P2 SimNow/券商测试：** 只有用户另行明确测试环境和测试下单授权后才执行；至少 30 个受控案例，零重复、零未解释残仓、100% 对账。
- **P3 真实一手 canary：** 不由本次批准自动授权。需要独立实盘激活审查和明确授权；连续 10 个交易会话零安全违规、100% 对账后才讨论放量。

代码在 P0 和独立终审通过后可以合入，但激活门保持关闭。P1/P2 未通过前不得把“已合入”表述为“实盘正在运行”。

## 8. 部署与回滚

1. 在隔离 worktree 形成不可变 commit，并在基于主仓库当前 HEAD 的干净 integration worktree 验证；不得在脏主工作树直接覆盖文件。
2. no-submit canary 使用独立 label、输出目录、state、spool 和 ledger；不得读取或修改生产 ledger。
3. 切换生产前维护窗口必须 unload/disable day 与 night 两个 job，确认 Stage930/608/931 进程为 0，并快照 ledger 原始字节/哈希、Stage904 state/WAL、installed plist 和 release manifest。
4. 第一阶段只启 day，night 保持 unloaded，操作人员在线观察。
5. 若生产 ledger 未变化且无 V2 行，可同步回滚代码和 plist。
6. 若只有 reservation/safe-terminal 且无 API slot/send/cancel/fill，须先用 fresh broker 全量快照证明无副作用。
7. 若出现 API slot、send、cancel、fill 或 unknown side effect，禁止恢复旧 V1 ledger；保留 V2-compatible reader、卸载 submit job、完成 broker 对账，只能 roll-forward 或使用兼容回滚版本。

## 9. 实施拆分

为降低并发与状态机风险，按以下顺序实施，每个任务都先红后绿并独立审查：

1. Stage608 ingress 双时钟、有界队列、异步 writer、durable watermark 和 shutdown recovery。
2. 全链路 trace schema、虚拟时钟和 SLA 断言。
3. Stage904/905 常驻 detector 和 SQLite priority spool。
4. Stage931 预热 serve 模式、readiness lease、spool/ledger crash recovery。
5. Runtime profile、release manifest、激活门和 LaunchAgent/supervisor 生命周期。
6. 全量故障矩阵、60 秒压力测试、Stage179 原回归、阶段记录和独立终审。

任务 1、2 完成后只能说明“行情因果与延迟证据已补齐”；任务 3、4 完成并通过 P0 后，才有资格说明“结构上消除了今天 70–136 秒慢路径”；任务 5、6 和 P1/P2 通过前，仍不能说明“线上实盘已启用”。

## 10. 设计判断

这不是过拟合：所有改动针对跨品种通用的时间因果、背压、耐久、故障域和执行幂等，不使用 JM 当天价格去调整策略参数。

继续推进有价值：现有候选虽然修复了大量状态和竞态问题，但 Stage608 P1、冷启动执行路径和缺失的端到端 SLA 仍足以造成旧 tick 误判或分钟级迟发。只有完成本设计并按阶段验收，才能把“代码看起来更快”提升为“延迟有证据、超时不迟发、可安全灰度”。
