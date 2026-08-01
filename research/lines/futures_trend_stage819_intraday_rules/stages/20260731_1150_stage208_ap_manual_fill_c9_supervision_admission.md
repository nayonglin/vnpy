# Stage208 AP 手工成交接入 C9 盘中监管审计

## 基本信息

- 时间：2026-07-31 11:50（Asia/Shanghai）
- 研究线：`futures_trend_stage819_intraday_rules`
- 是否重要突破版本：否
- 当前正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 目标：判断并修复 AP610 手工成交接入“入场日 0.5R 止损 + 一次重试”监管链的确定性阻断。

## 开始前反思

- 是否过拟合：否。本阶段不修改 0.5R、重试次数、品种、方向、时段或任何 alpha 参数，只修复生产证据 schema 契约漂移并核验一笔真实成交能否按冻结规则重建。
- 是否有价值继续：是。券商真实仓位、策略影子仓位和盘中状态机必须使用同一成交身份与价格，否则止损价和重试状态都不具备执行意义。

## 外部调研与判断

- 检查 vn.py 官方 GitHub 仓库、README、CHANGELOG 和 releases。
- 判断：vn.py 提供事件驱动交易网关和 CTP 接口基础设施，但不提供“将人工成交安全纳入某个自定义策略状态机”的通用业务语义；本仓库仍需用不可变券商查询证据、当前策略风险行和本地状态机完成绑定，不能从上游直接复制一个接管实现。

## 真实证据

- 券商成交：`AP610.CZCE` 多开 4 手，4 条稳定成交身份，均为 `7738 × 1手`，时间 `2026-07-31 09:03:44`。
- 券商持仓：`AP610.CZCE` 多仓 4 手。
- Stage901 风险行：计划价 `7740`，原始止损价 `7672`，计划手数 `4`。
- 以真实成交价重算：`R = 7738 - 7672 = 66`，0.5R adverse 线为 `7705`，+0.5R progress 线为 `7771`，重试触发价为原成交价 `7738`。
- 从 08:55 干净、已提交的 Stage608 journal 回放入场后的 `11,400` 条 AP tick：
  - 最低成交价 `7737`；
  - 最高成交价 `7880`；
  - 未触及 `7705`；
  - `09:07:04` 首次触及 progress，成交价 `7772`。
- 按冻结 C9 语义，本笔路径是 `progress first`，应进入 `watch_progress_hit_no_initial_stop`；它不是先止损后等待重试。若要在 progress 后仍永久保留 7705 止损，属于策略语义变更，不是本阶段接管。

## 底层阻断

1. Stage174 当前正式只读快照已输出 `broker_query_bundle.schema_version=2`，但 Stage904 依赖的 `validate_readonly_query_bundle` 只接受 schema v1，导致完整的 4 手真实成交被错误拒绝，成交价退化为缺失。
2. 2026-07-30 21:22 磁盘写满留下历史未提交 gap。Stage608 按当前设计永久保留 gap lineage，因此即使 2026-07-31 新流已经持续写入且当前无丢包，仍保持 `stream_ready=false`；Stage941 因此不消费 tick。
3. Stage927 当前仍有 9 个生产提交证据 blocker，所以不能绕过 Stage927/931 直接让补丁对真实账户下单。

## 本次改动

- 修改 `qmt_roll_official_live_late_retry_fill.py`：
  - 同时接受 schema v1 与 v2，拒绝 manifest/summary schema 混用；
  - v2 强制校验 account/contracts 查询、5 个查询 reqid 唯一性和顺序；
  - v2 强制校验 settlement/account/contracts/orders/trades/positions 全部来自同一 CTP connection generation；
  - v2 强制校验 lifecycle 当前代次、readiness 代次、查询代次与 snapshot 代次一致；
  - 保留 v1 兼容，不降低原有 hash、行数、账户、成交身份和订单映射校验。
- 修改 `test_official_live_late_retry_fill.py`：
  - 新增 v2 同代次通过用例；
  - 新增 v2 混入旧连接代次 fail-closed 用例。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 验证结果

- 定向测试：
  - `tests/test_official_live_late_retry_fill.py`
  - `tests/test_stage174_query_bundle.py`
  - `tests/test_stage904_durable_state_integration.py`
  - 结果：`109 passed, 40 subtests passed`。
- 使用今天真实 Stage174 v2 快照做隔离函数验证：
  - `fill_price=7738`
  - `fill_price_source=readonly_broker_current_epoch_fifo_weighted_avg`
  - `broker_open_trade_count=4`
  - `broker_open_trade_volume=4`
  - `broker_epoch_reconstruction_complete=1`
  - `monitor_action=watch_progress_hit_no_initial_stop`
- 本次未连接新的 CTP 会话、未提交、未撤单，订单 API 调用为 `0`。
- 本阶段未跑回测，因此期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率均为“不适用”；本次没有新增、修改或删除回测结果。

## 发布与风险结论

- 补丁只存在隔离 worktree `codex/ap-manual-position-adoption`，没有写入稳定生产根、没有生成新 qualification/activation，也没有热改当前运行进程。
- 当前真实自动监管仍未恢复；生产事实仍是 Stage608/941 feed unready 且 Stage927 fail-closed。
- 不应为了今天这笔仓位删除 gap、改 detector cursor、直接补账本或绕过 Stage927/931。若恢复无人值守自动执行，必须把 schema 修复与“仅对入场前 gap 做有证据的 position-epoch recovery”作为新版本完成测试、资格包和 Stage948 激活。

## 结束反思

- 是否过拟合：否。改动仅恢复生产者 schema v2 与消费者的证据契约，并增加更严格的连接代次校验；真实 AP 回放仅用于验证，不参与阈值选择。
- 是否有价值继续：是，但下一步价值在执行基础设施而非策略救参。应实现 position-epoch 有界恢复，确保 gap 发生在入场前且入场后 tick 全覆盖时才允许监管恢复；不能把全局 gap 无条件清空。

## TODO

1. 为 Stage941 设计并测试 position-epoch 有界 gap recovery receipt，绑定券商成交身份、入场时间、历史 journal 游标和 gap lineage。
2. 通过完整资格包和 Stage948 激活发布，禁止在稳定生产根热补丁。
3. 激活前重跑真实只读快照和隔离 journal 回放，确认 AP 状态为 `progress_latched`，避免把已经 progress-first 的仓位误设为仍等待 7705 初始止损。
4. 单独补齐 Stage927 当前缺失的生产证据链；未清零前保持订单 API 为 0。
