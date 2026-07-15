# Stage181 Stage179 Task2 崩溃一致性复审修正

- line_id：`futures_trend_stage819_intraday_rules`
- 记录时间：`2026-07-15 18:13 CST`
- 候选冻结时间：`2026-07-15 18:23 CST`
- 当前模式：隔离 worktree 离线修复、故障注入与独立只读审查；未加载实盘 env、未连接 CTP、未操作 launchctl
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability` / `codex/stage179-live-execution-reliability`
- 基线提交：`a89141c9c`
- 代码/测试七文件候选指纹：`551368da2cf089fc17dba92a543ec2dcb04e5c24a56d07e4b3fada43ea7305ca`
- 代码/测试/Spec 九文件候选指纹：`d2d9c0eee9d382fa7012946d9ebeec0d78c1332dfe5517de41ac645550979894`
- 阶段性质：Stage180 后续精确审查驱动的 Task2 crash consistency 与 lifecycle fail-close 修正；不改 alpha
- 是否重要突破：否；修复真实执行底座缺陷，但 Task3、端到端 SLA、LaunchAgent、0/0 只读 CTP 与 SimNow 仍未验收
- 是否触发 A/B：否；没有修改信号、AI 池、止损、重进场、品种、方向、手数或资金参数
- 是否连接 CTP：否；测试日志中的连接/订阅文案来自 fake gateway
- 下单/撤单 API 次数：`0/0`

## 外部调研与判断

- 参考资料：
  - VeighNa `EventEngine`：<https://github.com/vnpy/vnpy/blob/master/vnpy/event/engine.py>。单消费者事件队列决定行情因果时间必须在 gateway 入队前采集。
  - VeighNa `BaseGateway`：<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py>。`on_tick` 是 EventEngine 前的 ingress 边界，原始 forwarding 语义必须保留。
  - VeighNa `vnpy_ctp` gateway：<https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py>。TD/MD native close 与异步连接状态不能假设可安全重复调用。
  - Linux `fsync(2)`：<https://man7.org/linux/man-pages/man2/fsync.2.html>；POSIX `rename(3p)`：<https://man7.org/linux/man-pages/man3/rename.3p.html>。文件 fsync、rename 原子可见性与父目录耐久是不同边界。
  - Apple `fsync(2)`：<https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsync.2.html>；Apple 磁盘写入建议：<https://developer.apple.com/documentation/xcode/reducing-disk-writes>。普通 macOS `fsync` 不证明驱动器缓存已按序物理落盘；`F_BARRIERFSYNC`/`F_FULLFSYNC` 也需要结合正式文件系统和延迟预算验证。
- 我的判断：
  - 本轮问题来自通用磁盘提交、进程接管与不可信持久化证据，不应靠增加固定等待时间或为 JM 放宽策略门禁规避。
  - authority 的本质不是“JSON 看起来完整”，而是文件内容、inode、父目录项、manifest transaction core、source 应用状态与 successor heartbeat 必须形成同一条可重放因果链。
  - framed reader 的完整 ancestry 验证当前为 bounded-memory、`O(cursor offset)`；安全性成立，但重复分页可能形成近似二次累计耗时。该 P2 必须由后续可信 checkpoint/hash-chain schema 与 Task13 SLA 解决，不能退回局部 commit 检查。

## 本次变更

- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 修改实现：
  - gateway capture 使用 CPython 3.11 Event + GIL 串行 token lease，callback 不进入 mutex/Condition、文件、JSON、网络或耐久等待；restore 先禁止新 capture，再等待在途 forwarding 完成。
  - dirty-tail 使用不可变 redo manifest；sidecar、manifest、source truncate、父目录 barrier、H1/successor ACK 分别验证 inode、大小、hash 与完整 transaction/gap lineage。
  - direct/restart ACK 均绑定外层 result 与 transaction-id core，证明 source 已 truncate 到 trusted end，并在锁内重读 heartbeat 字节、manifest identity 后才删除 redo authority。
  - heartbeat 原子 replace 的父目录 barrier 失败时，同时 truncate/fsync replacement inode 与 crash rollback 可能恢复的 pre-replace inode；任一撤权失败都抛出复合 authority-unsafe 错误。
  - dead-owner lifecycle guard 接管前，把 running/starting、旧 clean、任何 ready/transport-ready、writer-alive 或 accepting authority 持久降级为 `fault_stopped + stopped/unready + writer-dead + accepting=false + recovery_blocked`，再清 guard；没有 guard 的普通崩溃也在 recovery/connect 前通过绑定旧 feed、segment 和 revision 的可恢复 guard 完成同一撤权。
  - terminal guard 在任何 teardown 前落盘，shutdown 后单调刷新 capture/writer/pipeline 三项 quiescence；guard 两次落盘失败且资源未静默时，在 owner lock 内进程级 fail-stop，禁止 Python 栈展开释放执行权。
  - terminal clean 判定要求同一 durable snapshot 同时证明 committed authority、framed cursor、无 gap/fault/drop、queue 空、writer 停止、accepting=false、last sequence 等于 durable sequence。
- 修改测试：
  - 新增 post-replace parent-fsync crash rollback 双 inode 撤权回归。
  - 新增 manifest outer/core result 不一致时 direct/restart ACK 均拒绝且保留 manifest。
  - 新增 manifest 已准备但 source 未 truncate、heartbeat 同 inode 同大小字节突变、dead-owner running-ready authority 等 fail-close 回归。
  - 新增无 guard running authority 的 recovery 前撤权、撤权写失败保留 guard、撤权后 clear 失败可由 dead owner 安全接管，以及 capture timeout 与 terminal-guard 双失败的 owner-lock 内 fail-stop 回归。
- 修改 Spec/Plan：同步 redo ACK successor、双 inode 撤权、两段 lifecycle guard、完整 reader ancestry 与已知复杂度边界。
- 删除实现：无。

## 回测/验证参数

- 数据区间：不适用；本阶段未运行策略回测。
- 账户规模：不适用；未加载账户环境。Stage372/20万与 Stage847-C9/15万的运行口径冲突仍需在真实只读链路前明确，当前不擅自改配置。
- 成本口径：不适用。
- 样本过滤：gateway backlog、capture/restore 竞态、queue overflow、writer/fsync 故障、partial frame、hash/offset/sequence 矛盾、dirty-tail replay、manifest/heartbeat/source 同 inode 竞态、owner 接管、signal/close/cleanup 异常、exact-int 别名。
- 策略/归因口径：仅执行可靠性，不改正式策略 alpha。

## 结果

- 期末权益：不适用；未跑回测。
- 总收益：不适用；未跑回测。
- 最大回撤：不适用；未跑回测。
- Sharpe：不适用；未跑回测。
- 总滑点：不适用；未跑回测。
- 总交易次数：不适用；验证期间订单/撤单 API `0/0`。
- 胜率：不适用；未跑回测。
- 其他关键指标：
  - Stage608 全量 `145/145`，耗时 `24.090s`；Stage931 EventEngine backlog 因果控制 `1/1`，耗时 `1.006s`；合计 `146/146`，退出码 `0`。
  - 7 个相关 Python 文件 `py_compile` 通过；`git diff --check` 通过。
  - 本轮所有新增缺陷均先得到可复现 RED，再修至 GREEN。
  - 独立最终审查：冻结 code/test 与九文件指纹均精确匹配，18 条关键故障注入 `18/18` 通过；结论 `P0=0、P1=0、P2=4`，Task2 可提交但不能据此部署。

## 输出文件

- report：本 Stage181 记录。
- summary：离线 unittest、静态检查与独立审查输出；未生成实盘 summary。
- orders：无。
- daily：无。
- quality：`tests/test_stage608_continuous_tick_stream.py`、Stage931 因果回归、`py_compile`、`git diff --check`、精确哈希独立审查。

## 结论与 TODO

- 当前结论：Task2 修正已通过离线回归与冻结指纹独立终审，达到代码提交条件；这不等于部署条件，更不等于实盘激活条件。
- 下一步：amend Task2 提交并做提交对象级只读审查，然后进入 Task3 Stage904 eviction 消费门禁和分段延迟 SLA。
- 后续必须完成：代码部署与实盘激活隔离、LaunchAgent/supervisor/runtime 修复、官方资金/版本口径统一、严格 `0/0` 只读 CTP、SimNow 报撤验收；这些闸门通过前禁止真实报单。
- 已知 P2：
  - framed reader 每次带 cursor 分页均从 header 验证完整 ancestry，单次 `O(cursor offset)`、累计可能近似 `O(N²/page)`；Task13 必须给出延迟证据与新 schema 方案。
  - lifecycle guard 只有 PID liveness，没有 boot/process-start identity；PID reuse 会保守阻断而不是错误放行，后续补强可用进程启动身份消除长期假阻断。
  - terminal exit gate 已校验 schema/offset/零值关系，但仍缺“返回 cursor、落盘 final heartbeat、segment 实际 commit boundary”三者的独立故障注入绑定测试。
  - atomic parent-open 时序和 capture token 的 first-check/clear/second-check 交错仍可增加 caller 层确定性 RED；当前实现与静态审查未发现错误放行。
  - 当前普通 `fsync + parent fsync` 只形成进程崩溃/OS 可见一致性口径，不证明 macOS 突然断电后的驱动器缓存顺序；Task13 需在正式文件系统基准测试 `F_BARRIERFSYNC`/`F_FULLFSYNC` 后再决定是否升级原语，不能无延迟证据直接替换热路径。
- 是否更新本线 `LINE.md`：否；同线并行先保留唯一 Stage181 文件，合入时统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未成为正式候选或完成外部验收。

## 过拟合反思

- 运行前判断：否。
- 当前判断：否。
- 原因：没有使用当晚 JM 盈亏、价格或品种特例调参；修复的是跨 session、跨文件系统故障与进程生命周期通用不变量。

## 继续价值反思

- 运行前判断：是。
- 当前判断：是。
- 原因：行情入口因果、durable authority、恢复和接管是开仓、实时止损与重进场共同底座；Task2 收口后仍需 Task3 与端到端 SLA 才能证明今天的延迟问题在线闭环。
