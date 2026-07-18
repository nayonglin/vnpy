# Stage179 C9 实盘执行可靠性加固

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：隔离 worktree 实现与无连接验证；未部署、未重启实盘进程
- 记录时间：`2026-07-13 22:20 CST`
- 完成时间：`2026-07-14 02:47 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability` / `codex/stage179-live-execution-reliability`
- 基线提交：`533fa961c`
- 独立终审代码冻结指纹：`98ee0c5620e479f206a973f30976f639d2650dbfe534a625d7d60f66b6b33368`
- 当前正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 阶段性质：Stage178 事故后的跨品种执行可靠性修复，不改 alpha
- 是否重要突破：否；这是高优先级候选修复，尚未经过 SimNow/券商测试和受控实盘激活验收
- 是否触发A/B：否；不改信号、AI 排名、0.5R、重试次数、品种、方向、手数或资金口径
- 是否连接 CTP：否
- 下单/撤单 API 次数：`0/0`

## 外部调研与判断

- 参考资料：
  - VeighNa `vnpy_ctp` 官方网关实现：<https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py>。交易连接、结算确认、合约初始化和账户/持仓查询均由异步回调推进，不能把固定睡眠结束或登录日志等同于完整可提交状态。
  - VeighNa `EventEngine` 官方实现：<https://github.com/vnpy/vnpy/blob/master/vnpy/event/engine.py>。行情与交易事件本质上是持续事件流，开仓日止损不能依赖每轮重建连接和覆盖式快照。
  - VeighNa `BaseGateway` 官方实现：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py>。网关回调在写入 `EventEngine` 队列前仍处于真实 ingress 边界，因此单调时钟应在 gateway ingress 处采集，而不是在消费者出队时补写。
- 我的判断：
  - Stage178 的根因不是 JM 或当晚行情特例，而是“重型串行循环 + 冷启动行情快照 + 固定 CTP 等待 + 无跨轮状态”的系统性执行缺陷。
  - 正确修复不是把 `8s` 调成另一个经验秒数，也不是为 JM 放宽风控；应把风险判定改成有序事件流上的耐久状态机，把 CTP 提交改成带单调时限的回调就绪状态机。
  - AI 池只应治理新风险；月更/校验失败不应杀死持仓止损通道。风险减少动作和风险增加动作必须采用不同 fail-close 边界。
  - 本阶段仍不宣称毫秒级实时。行情监控目标是秒级快速通道；Stage931 在有动作时仍会建立独立 CTP 提交通道，受登录、结算、查询和交易所回报时延约束。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_live_c9_intraday_state.py`：纯函数耐久状态机，覆盖初次持仓、0.5R 止损、进展锁、平仓确认、一次重进场和重进场后再次止损。
  - `examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py`：持久记录撤单后迟到成交、未定价成交和跨轮补价，避免已发生的平仓副作用在下一轮被当成零成交。
  - `examples/portfolio_backtesting/run_qmt_roll_stage930_owned_child_guard.py`：守护 Stage930 拥有的子进程；父进程死亡时清理进程组并撤销行情提交证明。
- 修改脚本：
  - `qmt_roll_official_live_execution_ledger.py`：增加完整身份才启用的 v2 指纹；按 root/cycle/role 隔离初始开仓、重进场和第二次止损；成交按 trade id 去重；所有 close attempt 均使用 UUID lease token；attempt1/attempt2 的租约、冷却、takeover 与多子单 API-slot CAS 在同一 ledger `flock` 中线性化；旧 token、缺 token、错 attempt 和脏账本均 fail-close。
  - `run_ctp_stage174_readonly_probe.py`：订单、持仓、成交查询改为 reqid-bound 完整 query bundle，避免把固定等待期内的不完整回调当成权威账户快照。
  - `run_ctp_stage608_readonly_tick_snapshot_probe.py`：增加单连接持续 `EVENT_TICK` 流、NDJSON 日志、原子心跳、动态订阅清单、父进程守护和断连后 readiness 撤销；tick bytes 先耐久落盘，再提交包含 generation/revision UUID、hash、行数的 heartbeat；保持订单 API 为零。
  - `run_qmt_roll_stage903_official_live_phase_d_controller.py`：增加 external intraday 模式，由 Stage930 单独拥有 Stage904/905 快速通道，避免重复冷刷新。
  - `run_qmt_roll_stage904_official_live_c9_intraday_monitor.py`：接入持久状态、原子输出、文件锁、WAL 和 transition journal；采用 H1/bytes/H2、整份 heartbeat、hash、行数与 generation/revision 双检验证 Stage608 快照；同 tick 双穿时 stop-first；progress 先到后永久取消初次止损；feed gap 允许风险减少平仓但禁止进展/重开仓；重开仓必须同时看到真实止损成交、fresh broker flat 和 fresh favorable tick；支持迟到未定价 close fill 的跨轮对账。
  - `run_qmt_roll_stage905_official_live_executor_dry_run.py`：透传 root/cycle/role/action 身份；按标的/方向/开平去重，优先最新保护性平仓；止损平仓和重进场均生成可成交保护价；启动即清空旧可执行输出。
  - `run_qmt_roll_stage930_official_live_c9_session_daemon.py`：默认使用持久 tick stream；慢控制器运行期间和原 30 秒轮询空档均持续运行快速风控；增加 daemon singleton、owned-child/process-group guard、heartbeat revoke 和 H1/H2 间撤销保护；只保留最近 20 次详细结果并逐次落事件日志；AI 池默认只做 `check`，且先建立行情流，失败时只拦新风险、继续允许 reduce-close。
  - `run_qmt_roll_stage931_official_live_ctp_submit_adapter.py`：固定 `sleep(8)` 改为最多 30 秒的登录/结算/合约/账户/持仓回调状态机；close-only 无需账户资产回调但仍要求持仓快照；tick 在 gateway 入队前记录 monotonic ingress，授权条件严格为 `received > Q2 cutoff`；有动作时执行两套 reqid-bound order-position-order、完整仓位比较、active-order/transport/精确开平条件复验和 API-slot 前 ingress watermark 检查；query echo 不计入异步人工订单水位；SHFE/INE 拆单后以 batch CAS 保证同一 close lease 只有一个发送者；close terminal 分区仅限显式 reduce-close-only 的 Stage904 保护性平仓队列；真实成交回报去重并补记撤单后 late fill。
- 新增测试：
  - `tests/test_official_live_c9_intraday_state.py`
  - `tests/test_official_live_execution_ledger_cycles.py`
  - `tests/test_official_live_late_retry_fill.py`
  - `tests/test_stage174_query_bundle.py`
  - `tests/test_stage608_continuous_tick_stream.py`
  - `tests/test_stage904_durable_state_integration.py`
  - `tests/test_stage905_c9_cycle_intents.py`
  - `tests/test_stage930_fast_lane.py`
  - `tests/test_stage931_ctp_readiness.py`
  - `tests/test_stage931_post_reprice_final_gate.py`
  - `tests/test_stage931_trade_fill_accounting.py`
- 删除脚本：无。
- 新增参数：
  - Stage608：`--stream`、`--watch-manifest`、`--journal-path`、`--heartbeat-path`、`--duration-seconds`、`--heartbeat-seconds`、`--max-buffer-ticks`、`--parent-pid`。
  - Stage903：`--intraday-execution-mode integrated|external`。
  - Stage930：`--fast-poll-seconds=1.0`、`--fast-tick-age-seconds=10`、`--fast-step-timeout-seconds=20`、`--stop-all-on-ai-pool-failure`。
  - Stage931：`--reduce-close-only`、`--trade-detail-wait-seconds=2.0`、`--final-reprice-tick-wait-seconds=2`、`--final-order-query-wait-seconds=8.0`。
- 修改参数：
  - Stage930 `--tick-refresh-mode` 默认从 `refresh` 改为 `stream`。
  - Stage930 `--ai-pool-preflight-mode` 默认从 `run` 改为 `check`；显式 `run` 才执行慢月更。
  - Stage931 `--connect-wait-seconds` 从固定 `8` 秒改为状态驱动、上限 `30` 秒。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不适用；本阶段不跑策略回测，只做执行状态机与集成测试。
- 账户规模：正式配置仍为 `150,000`，测试不连接账户。
- 成本口径：不适用。
- 样本过滤：JM 精确阈值场景、同 tick 双穿、progress-first、跨进程恢复、feed gap、buffer overrun、初次/重试分周期账本、CTP 回调延迟/错误/断连、撤单后 late fill、AI 池异常下 reduce-close。
- 策略/归因口径：保留 Stage847-C9 的原始入场价、原始全 R 初始止损、`0.5R` 日内止损和最多一次重进场规则。

## 结果

- 期末权益：不适用；未跑回测。
- 总收益：不适用；未跑回测。
- 最大回撤：不适用；未跑回测。
- Sharpe：不适用；未跑回测。
- 总滑点：不适用；未跑回测。
- 总交易次数：不适用；测试期间下单/撤单 API `0/0`。
- 胜率：不适用；未跑回测。
- 其他关键指标：
  - 11 个针对性单元/集成模块共 `249/249` 通过：state 20、ledger 40、late retry 21、Stage174 8、Stage608 7、Stage904 42、Stage905 4、Stage930 25、Stage931 readiness 27、post-reprice 10、fill accounting 45。
  - ledger 的 4 个并发用例额外重复 20 轮，共 `80/80`；独立 reviewer 又用真实 fork 对 attempt1 takeover/旧 token CAS 压力运行 100 轮，均恰好一个赢家。
  - Stage931 三模块联合 `82/82`；真实 EventEngine backlog、严格 Q2 后 tick、Q2 callback 到 watermark 的人工订单 ingress、query echo 排除和 API-slot 前最终水位均有离线回归。
  - JM 示例验证：初始成交 `1245.5`、原始止损 `1258` 时，C9 止损保持 `1251.75`、进展价保持 `1239.25`；重进场成交价变化不会漂移第二次止损阈值。
  - 初次止损与重进场后止损使用不同 `position_cycle_id + intent_role`，不会再因旧指纹碰撞而拒绝第二次平仓。
  - Stage608/Stage904 无 `send_order`/`cancel_order` 调用路径；整个验证未加载实盘 env、未连接 CTP、未提交订单。
  - `py_compile`、`git diff --check`、supervisor `bash -n`、两份 launchd plist `plutil -lint`、配置断言和 CLI `--help` 全部通过。早期测试 stub 曾移除已加载的 pandas/numpy 模块，已修正为只安装并恢复 config stub；最终 249 项在同一解释器进程完整通过，不再依赖拆进程规避。
  - 独立终审开始与结束的代码冻结指纹一致：`98ee0c5620e479f206a973f30976f639d2650dbfe534a625d7d60f66b6b33368`；审查期间工作树状态未变化。

## 输出文件

- report：本 Stage179 记录。
- summary：针对性测试控制台结果；未生成实盘 summary。
- orders：无。
- daily：无。
- quality：11 组测试文件、并发/fork 压力、静态编译、diff check、shell/plist lint、配置断言、无订单 API 扫描和独立 agent 冻结整包复审。

## 独立终审

- reviewer 结论：代码冻结包 `P0=0、P1=0、P2=7`；合并 `GO`，严格无报单 CTP 只读验证条件 `GO`，SimNow 报单 `NO-GO`，直接实盘 `NO-GO`。
- 已关闭的阻断项：
  - Q2 前已入队 tick 不再因 EventEngine backlog 被重写为 Q2 后行情。
  - Stage608 heartbeat revoke 不再复用旧 commit/generation，Stage904 可在 H1/H2 之间可靠识别撤销或元数据变化。
  - attempt1/attempt2 全部纳入 UUID lease + ledger flock + batch API-slot CAS，旧 worker takeover 后无法再发送。
  - 永久阻断的保护性平仓不会饿死后续品种，同时也不能在普通混合开平队列中释放新开仓。
  - Q2 后等待行情不再复用过时账户证明；第二套 O-P-O 和 gateway ingress watermark 把人工订单竞态由秒级窗口压缩到本地发送前微窗口。
- P2 残余：
  1. 最终 watermark、ledger API-slot 落盘与 broker send 无法跨系统原子化，另一客户端人工单仍有毫秒级 TOCTOU 微窗口。
  2. 两轮 O-P-O 只跨 epoch 比较完整仓位；另一会话若在等待期间完成零成交撤单或净仓恢复 roundtrip，理论上可能不留最终差异。
  3. 单槽 `reserve_execution_api_slot(send_order)` 没有 close lease CAS；当前 Stage931 发送只走 batch，单槽路径当前不可达但有未来误用风险。
  4. batch close 判定依赖 child attempt/token/offset 元数据；当前 Stage931 强制补齐，非标准未来 caller 若省略字段存在误用风险。
  5. 带 token 但缺持久 cooldown 的迁移/手工畸形 reservation 会回退新 caller 参数；v9 正常生成记录不受影响。
  6. Stage608 发布函数本身没有第二层 publisher singleton；正常 Stage930 有 daemon/owner guard，手工启动第二发布者会造成 heartbeat/commit 抖动并瞬时 fail-close。
  7. native CTP query echo、另一会话私有流、thread-local suppression、磁盘写满、真实 native crash/断线尚未端到端验证。
- 独立运行政策阻断：`AGENTS.md` 仍规定默认只认 `official_live_stage372_20w_recovery_sleeve`，但当前 SOP 和 `qmt_roll_official_live_config.py` 指向 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。该冲突不是本次 diff 引入；在用户明确口径前不得做 SimNow 报单或直接实盘部署。

## 结论

- 本阶段结论：实现层已消除 Stage178 暴露的监控轮询空档、跨轮状态丢失、CTP 固定等待误判、初次/重试账本冲突，以及首轮 reviewer 发现的 EventEngine 因果重写、commit revoke、attempt1/2 并发重复平仓、混合队列开仓穿透和 Q2 后人工单秒级竞态。AI 池与持仓风险减少通道保持解耦。当前结论仅为“隔离分支通过独立冻结终审并允许合并”，不是“当前线上已经恢复正常”。
- 是否进入下一步：是，但先只做无报单验证。
- 下一步：先由用户明确 Stage372 20万与 Stage847-C9 15万的官方运行口径；随后用正确 env/runtime 做严格 `0/0` 报撤单的只读 CTP 验证。只有只读链路稳定后，才在 SimNow/券商测试环境做双会话人工单、断线重连、native crash、磁盘故障、低流动性和 close-only/重进场全链验收；不得直接热更新实盘。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有根据 JM 当晚盈亏调整任何策略参数；修复对象是跨品种、跨方向、跨会话通用的事件顺序、身份、幂等、持久化和连接状态。测试同时覆盖 long/short、顺序反转、重启、断流、线程与真实 fork 竞争，不以单一样本“恰好通过”为目标。

## 继续价值反思

- 运行前判断：是，优先级高。
- 运行后判断：是，但下一步价值已从继续堆静态分支转为口径澄清、只读 CTP 和 SimNow 双会话受控验收。
- 原因：该链路直接决定已有信号能否准时执行、已有持仓能否自动减险；继续调 alpha 无法弥补执行层不确定性。P0/P1 已清零后，真实 native 回调、跨客户端竞态和故障注入的信息增益显著高于继续增加离线规则。

## 合入建议

- 是否更新本线 `LINE.md`：否；同线并行只写唯一 Stage179 文件，待口径澄清和受控验收后由合入者统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未完成测试环境与实盘激活验收，不应提前写成正式突破。

---

## 2026-07-18 Stage179 P0 离线故障与延迟门收口

### 基本信息

- 开始时间：`2026-07-18 20:57 CST`
- 完成时间：`2026-07-18 21:12 CST`
- 代码提交：`43c61f7f3f275b53975d5535b355ff5325697fb6`
- manifest 完整 reader contract 补写提交：`fa3f0f0e0f23f4faa88462a1aba5fefb5ab19612`
- 代码提交 tree fingerprint：`4787b5ad84a75af9a0671bf1da4b34e4f434a368`
- 是否重要突破版本：否。P0 通过只允许代码集成且保持激活默认关闭；P1 只读 CTP、P2 SimNow/券商测试和 P3 一手生产 canary 均未完成。
- 实盘边界：未安装/加载 LaunchAgent，未加载真实 env，未连接 CTP/SimNow，真实 `send_order/cancel_order=0/0`。

### 外部调研与判断

- 复核 SQLite transaction/WAL、Python `sqlite3`、`subprocess`/`setsid`/process group、VeighNa CTP gateway/BaseGateway/EventEngine 的官方语义。
- 调研判断：不能用缩短固定 sleep、放宽 tick freshness 或针对 JM 单晚调参解决延迟；必须从 gateway ingress 因果、异步耐久化、持久 detector、close-priority spool、warm TD、ledger API-slot/CAS、LaunchAgent owner 和进程组回收形成端到端证据。
- 60 秒门第一次短测在原 50ms writer 聚合逻辑下得到 durable lag p99 `136.524ms`，超过 `100ms` 硬门。没有豁免；最终采用“仍保持最大 256 条/最迟 50ms，但高吞吐累计到 64 条且队列短暂清空就提前 flush”的自适应成批，避免用 5ms 固定窗口换取过高 fsync 频率。

### 版本改动

- 新增：`tests/test_stage179_fault_matrix.py`，覆盖 22 类断连、crash boundary、empty/exception/ack timeout、部分成交/撤单/late fill、generation/watermark/deadline/socket、spool/ledger/disk、kill switch/政策/profile 和双 executor 故障合同。
- 新增：100 轮真实 fork API-slot 竞争；每轮两个 executor 恰好一个 fake send winner，最大 winner `1`，真实订单 API `0/0`。
- 新增：`tests/stage179_performance_gate.py`，严格执行 20 合约、2,000 tick/s、60 秒、120,000 tick、25ms writer barrier 延迟与强制 overflow 门。
- 新增：release manifest 默认 critical files 扩展到 Stage179 tick/trace/spool/ledger/executor、Stage608/904/905/930/931/941、rollback guard、supervisor helper 和四份生产/canary plist，避免 manifest 只冻结部分代码。
- 修改：manifest reader capabilities 从仅 `intent_fingerprint_v2` 补齐为 ledger 当前完整能力集合，包括 `batch_api_slot_cas_v1` 与 `spool_crash_recovery_v1`；避免兼容回滚低估 reader 要求。
- 修改：`AsyncTickJournalWriter` 增加 64 条 eager flush 自适应门；最大 batch 256、最大等待 50ms、durability barrier 和 cursor 提交顺序不变。
- 修改：Stage930/Stage931/runtime profile 测试按 warm owner 新契约更新；默认仍为 `legacy-once`，production-live 激活仍失败关闭。
- 删除：无生产功能删除；无 alpha、AI 池、0.5R、重进场次数、资金、品种、方向、手数或仓位参数变化。

### 参数变化

- 新增参数：无策略参数。新增内部常量 `EAGER_FLUSH_BATCH_SIZE=64`。
- 修改参数：无用户可见 alpha/资金/风控参数；writer 的 256 条/50ms 上限未变。
- 删除参数：无。

### P0 故障矩阵

- 22/22 故障合同通过；每项记录 spool state、ledger evidence、recovery disposition、fake send/cancel 和真实 API `0/0`。
- 100/100 真实 fork 竞态通过；`max_send_winners_per_round=1`，ledger send slot 每轮为 `1`、cancel slot 为 `0`。
- evidence：`/tmp/stage179-p0-fault-matrix-20260718-2106/stage179_fault_matrix_cases.json`、`stage179_fault_matrix_process_races.json`。

### 60 秒性能门

- 参数：20 合约、2,000 tick/s、60 秒、writer delay 25ms、总 tick 120,000。
- 注入耗时：`59.999846s`；durable `120000/120000`；drop `0`、gap `0`、writer fault `0`。
- ingress：p99 `0.105083ms`、max `2.570208ms`，通过 `1ms/5ms` 门。
- EventEngine sentinel：1,183 样本，p99 `1.918834ms`、max `8.736875ms`，通过 `20ms/100ms` 门。
- durable lag：120,000 样本，p99 `83.560875ms`、max `120.077208ms`，通过 `100ms/500ms` 门。
- shutdown drain：`0.055693s`，通过 `2s` 门。
- RSS 增长：`31.921875MiB`，通过 `64MiB` 门。
- 强制 overflow：fault latch `0.082166ms`、readiness revoke `0.119291ms`；`drop=1 && stream_ready=false`。
- evidence：`/tmp/stage179-p0-performance-20260718-2106/stage179_performance_gate.json`；tick journal 仅为临时离线压力文件，不纳入 Git。

### 联合回归与静态门

- 第一次扩大回归：`597 passed, 1 failed, 238 subtests passed`。唯一失败为旧测试仍要求 Stage930 源码完全不出现 warm child 参数；不是运行时错误。按新 owner 契约修正后单项通过。
- 第二次扩大回归：`598 passed, 238 subtests passed`，耗时 `54.89s`。
- manifest critical files 补齐后最终冻结回归：`599 passed, 238 subtests passed`，耗时 `51.57s`。
- manifest 完整 reader contract 补齐后最终复验：`599 passed, 238 subtests passed`，耗时 `52.40s`。
- Task12 生命周期/manifest/Stage930：`56/56`。
- Task13 fault matrix：`2/2`，其中含 22 个合同 subcase 与 100 轮 fork。
- `py_compile`、新增/修改生产文件 `ruff check`、`git diff --check`、supervisor `bash -n`、8 份 plist `plutil -lint`：通过。
- 真实订单 API：send `0`、cancel `0`。

### 回测结果

本阶段未改变策略 alpha，未运行收益回测：

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A
- 新增/修改/删除回测结果：无

### 反思与发布边界

- 开始前是否过拟合：否。目标是跨品种执行因果、持久化、唯一副作用和 SLA，不使用 JM 单晚盈亏调参。
- 完成后是否过拟合：否。自适应 batch、spool/ledger 恢复、process group 和 runtime gates 不依赖品种、方向或收益曲线。
- 是否仍值得继续：是，但下一步不再是堆离线规则；最高价值是独立全分支终审、真实 `0/0` 只读 CTP 的至少五个完整会话与断线重连、随后在用户另行授权下做 P2 测试单。
- 合入与激活：P0 与独立终审通过后可合入代码，但 warm/production-live 激活保持默认关闭。合入绝不等于“开仓日实时止损重进场已在线上运行”。
- 口径阻断：`AGENTS.md` 的 Stage372/20万与当前配置 Stage847-C9/15万冲突仍未澄清；不得擅自修改资金/策略口径或生成 production activation receipt。
