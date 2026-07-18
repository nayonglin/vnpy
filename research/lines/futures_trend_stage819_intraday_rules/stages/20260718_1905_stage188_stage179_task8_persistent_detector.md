# Stage188 Stage179 Task8 默认关闭的常驻 Detector

## 基本信息

- 改动时间：2026-07-18 19:05 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 工作区：`/Users/bytedance/Desktop/person/vnpy_stage179_live_reliability`
- 分支：`codex/stage179-live-execution-reliability`
- 基线提交：`d21e579043211ece771ad63e1e603f9df8606693`
- 代码提交：`698d39f33f9b2d260177b782f572ca3e6bdd5f84`
- 是否重要突破版本：否。Task8 已达到代码可提交条件，但仍是默认关闭、仅允许 `dry-run + submit-disabled` 的离线候选；Tasks9-13、只读 CTP、SimNow、部署和端到端延迟验收尚未完成，不能称为可部署或可激活的正式突破版本。
- 实盘边界：未加载实盘 env，未连接真实 CTP/SimNow，未修改 LaunchAgent/plist，未调用真实报单/撤单 API，审查和测试口径均为 `0/0`。

## 外部调研与判断

执行前和审查阶段复核了官方资料：

- Python `subprocess`：<https://docs.python.org/3.11/library/subprocess.html>
- Python `signal`：<https://docs.python.org/3.11/library/signal.html>
- SQLite transaction：<https://www.sqlite.org/lang_transaction.html>
- SQLite atomic commit：<https://www.sqlite.org/atomiccommit.html>
- SQLite WAL：<https://www.sqlite.org/wal.html>

判断结论：常驻 detector 的关键不是“少启动几个 Python 进程”，而是把行情权威、状态 WAL、意图 spool、游标 CAS、崩溃恢复和进程所有权组成同一条可证明的因果链。Python signal handler 只置停止事件，当前周期完成或回滚后再发布 stopped/unready；SQLite 只保证数据库事务原子性，外部兼容文件必须通过 durable outbox 做恢复，不能把多文件写入误称为数据库原子提交。

## 本次改动

### 新增

- 新增 Stage941 常驻 detector：从 Stage608 durable journal 分批读取，在内存中调用 Stage904/Stage905，按“Stage904 状态 WAL → 兼容 outbox fsync → H3 最终行情权威复核 → SQLite intents+cursor commit → trace stamp/socket notify → 兼容输出”顺序执行。
- 新增 Stage930 `--detector-mode legacy-subprocess|persistent`，默认保持 `legacy-subprocess`；persistent 在 Tasks10-11 前只允许 `mode=dry-run`、`submit-mode=disabled`、stream tick owner 和显式目标交易日。
- 新增 tick → detector → AI preflight 启动顺序、Stage930 进程组所有权、bounded restart、instance/owner/parent/target/consumer/spool 身份和 heartbeat 新鲜度校验。
- 新增 persistent fast lane；该路径不启动 Stage904/Stage905/Stage931 子进程，不触达订单 API。
- 新增 feed rollover 事务证据、lost-ack 证据哈希复核、旧 feed 排空后再重启、非清洁 feed 粘滞阻断。
- 新增 clean empty-feed lineage 折叠：支持 `A(有 tick) → B(清洁 0 tick) → C`，被跳过的空 feed ID 纳入 rollover evidence hash；Stage930 只有在 detector 明确观察到 B 的 `durable_through=0/0` 且 cursor 精确等于 A recovery cursor 时才允许启动 C。
- 新增 backlog 大于 batch limit 的 partial batch 推进、真实 SIGTERM、Stage904/Stage905/outbox-fsync 后 H1/H2/H3 撤权、崩溃前后重放、兼容 outbox 修复、游标和状态顺序等故障回归。

### 修改

- Stage904 durable callable 增加仅由 Stage941 显式启用的 partial batch 支持；默认仍要求 caught-up，legacy 行为不变。
- Stage608 heartbeat 增加前一权威 feed 的 revision/state/clean-shutdown 证据，并对连续 clean empty feeds 做严格折叠。
- intent spool 的 feed rollover 与 intents/cursor 在同一事务内提交；桥接空 feed 列表进入 canonical evidence 和 SHA256。
- Stage941 idle/unready 周期读取持久 spool counts，避免已有 ready/blocked/expired 意图在 heartbeat 中被错误归零。
- Stage930 legacy 空 target 继续交给 Stage903 `latest-completed` 解析；persistent 空 target 在任何 child 启动前 fail-close。
- Stage930 对 send/cancel 计数要求精确非负整数；字符串 `"0"`、布尔值或其他畸形值不能冒充可信 `0/0`。

### 删除

- 删除 Stage941 早期兼容输出直写的不可达代码。
- 未删除或调整任何 alpha、资金、止损、重进场、AI 池或选品逻辑。

## 参数变化

- 新增 `detector_mode`：默认 `legacy-subprocess`，候选值 `persistent`。
- 新增 detector poll：默认 `0.05s`。
- 新增 detector batch size：默认 `1024`。
- 新增 detector bounded restart：默认最多 `3` 次，backoff `2.0s`。
- 新增 heartbeat 最大年龄：`max(1.0s, detector_poll_seconds × 10)`；未来时钟偏差上限 `2.0s`。
- 新增 persistent 启动门禁：显式 target date、stream tick owner、dry-run、submit-disabled。
- 修改参数：无 alpha、资金、止损或重进场参数修改。
- 删除参数：无。

## 验证结果

- Task8 完整相关链：`223/223`，耗时 `21.789s`。
- Stage608 continuous tick/recovery：`148/148`，耗时 `26.753s`；日志中的“连接登录/订阅行情”来自测试 fake gateway，未加载真实 env 或网络连接。
- 最终 Stage930 supervisor 定向复核：`3/3`，覆盖 clean-empty restart、普通非空 drain、unclean sticky blocker。
- `py_compile`、`git diff --check`：通过。
- 最终冻结 SHA256：
  - Stage941：`8aa1dfc6cddfce81d9c84dd09721754b9d882f50acf0eec542806d757b695e72`
  - Stage930：`bd4311cfcb2b2711e9e46504c337c8e9841d5fec01c74f16bdae9820d2ee27e6`
  - intent spool：`0fd2b3e87319b0327e3ad1a0f1595db7a503943750d1f4cf147b9d04c71bd58b`
  - Stage904：`d7498f0ffbf8a6fd49836cdb8be46622c20229d7505dd7ac6487b7ea7de94cd3`
  - Stage608：`7cc317d72e4598ef8239b0ac921230ad27b55247531dc5e2d3fa8d89771c8c7d`
  - detector tests：`300703db6865933c27777a547c7d227d1e3818aa543c9d9e8191968dfd60887c`
  - Stage930 tests：`0ba01b87063b5c4c635ff777a564dcc0c4bdb5635763029d97a6db62daecfc08`
  - Stage608 tests：`187d4fe802110522178a48d95ba69992aac58e1f4cafbbeb0487f2835f3a2f9f`

## 独立审查

- 第一轮：`P0=0, P1=3, P2=4`，发现 unclean feed 阻断不粘滞、detector heartbeat 无新鲜度校验、legacy target 语义漂移；全部修复。
- 第二轮：`P0=0, P1=2, P2=3`，发现 H3 校验早于 outbox fsync、clean empty feed 无法连续 rollover；全部修复。
- 第三轮：初审 `P0=0, P1=1, P2=2`，发现 Stage930 supervisor 尚不能认可已经被 detector 处理的 clean empty feed；修复并补 supervisor 级回归。
- 最终增量复核：`P0=0, P1=0, P2=2`，结论为 Task8 代码可提交、实盘不可激活。
- 接受延期的 P2：六个兼容文件只逐文件原子替换、不具备集合级原子可见；`detector_feed_rollovers` 尚未纳入核心 schema fingerprint/version contract。前者不被 persistent 执行路径消费，后者必须在 Tasks9-11 的 release/schema capability 设计中正式收敛。

## 回测结果

本阶段没有改变策略 alpha，也没有运行回测；以下指标均为不适用，不得沿用历史结果冒充本阶段结果：

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A
- 新增/修改/删除回测结果：无

## 反思与后续

- 开始前是否过拟合：否。目标是消除进程启动、阻塞 I/O、游标/状态事务和 feed 生命周期中的执行不确定性，不依据某天、某品种或收益曲线调参。
- 完成后是否过拟合：否。新增约束均为时间因果、持久化、崩溃恢复、进程所有权和 fail-close 不变量，具有跨品种、跨交易日意义。
- 是否仍值得继续：是。Task8 只消除了 detector 冷启动和跨 feed 的一类延迟/失效模式；要回答“能否解决实盘 21:00 延迟”，还必须在 Tasks9-13 建立 runtime profile、release manifest、warm executor、单锁账本、分段 SLA、只读 CTP/SimNow 和部署后端到端证据。
- 下一步：按 Spec 执行 Task9，新增 typed runtime profiles、immutable release manifest 和默认关闭的 activation gate；同时把两个 P2 纳入后续 schema/consumer capability 门禁。
- 硬门禁：Tasks9-13、独立终审、`0/0` 只读 CTP、SimNow、LaunchAgent/官方口径和端到端延迟验收全部通过前，禁止真实报单。
- 记录隔离：本工作区只新增唯一 Stage188 文件，未修改同线 `LINE.md`、`research/registry.md`、根目录 `memory.md` 或 `back_log.md`。
