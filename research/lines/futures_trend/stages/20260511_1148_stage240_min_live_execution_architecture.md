# Stage240 最小可上线真实执行架构设计

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-11 11:48 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：执行架构设计
- 是否重要突破：是，明确“如何从影子盘走到自动真实开仓”
- 是否触发A/B：否，不修改 `78-1` 策略逻辑

## 外部调研与判断

- 参考资料与仓库内先验：
  - `Stage148` 已有 `go/no-go` 审计，证明仓库早就认识到“策略有效”不等于“可以实盘”。
  - `Stage154/155` 已有影子盘 `signal_intent / order_event / fill_event / reconcile` schema，可直接复用为执行链路的数据面。
  - `Stage237/238` 已有 `balanced_tranche_v1` 三账户账本和部署日报，可直接复用为部署面。
- 我的判断：
  - 真实执行不能从“回测脚本 + 发单开关”开始。
  - 必须拆成 `信号层 / 部署层 / 执行层 / 对账层 / 守护层` 五段。
  - 当前最合理的目标不是“马上自动开真实仓”，而是先把最小可上线执行架构设计清楚，后续按模块建设。

## 目标问题

- 用户问题1：真实转实盘后，是否需要一个持久服务一直运行？
- 用户问题2：怎么做到自动开真实仓？

## 核心结论

- 需要持久运行能力，但不必是一整个巨型单体服务。
- 推荐采用：
  - `1 个 supervisor 常驻进程`
  - `1 个 broker_adapter/executor 常驻进程`
  - `1 个 signal_scheduler 时段触发 worker`
  - `1 个 reconcile/report worker`
- 自动开真实仓的本质不是“自动调用下单API”，而是：
  - 有唯一意图
  - 有幂等执行
  - 有状态恢复
  - 有前置风控
  - 有事后对账
  - 有人工接管

## 最小可上线架构

### 1. Signal Scheduler

- 作用：
  - 到交易触发时点运行 `78-1` 信号生成。
  - 输出冻结后的 `signal_intent ledger`，不直接发单。
- 输入：
  - 最新主力映射
  - 最新 AI 品种池
  - `78-1` 正式配置
- 输出：
  - `signal_intent`
  - `target_position_snapshot`
  - `strategy_run_manifest`
- 复用基础：
  - `build_qmt_roll_stage78_1_shadow_daily_runner.py`
  - `build_qmt_roll_stage155_stage78_shadow_daily_protocol.py`

### 2. Deployment Gate

- 作用：
  - 判断今天账户是否允许真实新增单。
  - 判断当前属于生产账户/锁盈账户/扩张储备哪个部署阶段。
- 输入：
  - 账户权益
  - `balanced_tranche_v1` 账本状态
  - 风险日报状态
- 输出：
  - `allow_real_new_orders`
  - `deployment_status`
  - `account_budget_snapshot`
- 复用基础：
  - `build_qmt_roll_stage237_balanced_tranche_shadow_ledger.py`
  - `build_qmt_roll_stage238_balanced_tranche_shadow_daily_bundle.py`

### 3. Broker Adapter / Executor

- 作用：
  - 连接 CTP / QMT
  - 拉取真实账户、真实持仓、真实委托、真实成交
  - 将 `signal_intent` 翻译成真实委托
- 输入：
  - `signal_intent`
  - `deployment_status`
  - `account_state`
  - `position_state`
- 输出：
  - `order_event`
  - `fill_event`
  - `execution_exception`
- 强要求：
  - 所有真实订单必须带 `intent_id / order_group_id / strategy_run_id`
  - 发单前必须检查是否已有同组未完成委托
  - 重启后必须先恢复状态，再允许新单

### 4. Reconcile Worker

- 作用：
  - 每个交易窗口结束后做三方对账：
    - `signal_intent`
    - `broker_position / broker_order / broker_fill`
    - `deployment_ledger`
- 输出：
  - `position_reconcile`
  - `account_reconcile`
  - `reconcile_exception`
  - 部署日报 / 事故日报
- 复用基础：
  - `Stage154/155` schema
  - `Stage238` 部署日报格式

### 5. Supervisor / Safety Controller

- 作用：
  - 守护子进程存活
  - 检查交易时段
  - 下发全局模式：`readonly / simulate / paper_send / real_send`
  - 在异常时熔断到 `readonly`
- 异常触发：
  - 连接断开
  - 对账失败
  - 账户权益异常跳变
  - 未知成交
  - 未知持仓
  - 日内连续报错超阈值

## 持久服务应该怎么运行

- 推荐模式：`常驻 supervisor + 时段内激活 worker`
- 不建议：
  - 用一个 cron 脚本在某分钟跑一下就直接发单
  - 让回测脚本直接负责发单
  - 把部署账本、信号生成、发单、对账写成一个大脚本
- 建议时序：
  - 盘前：
    - 连接柜台
    - 恢复账户/持仓/委托状态
    - 生成部署日报
  - 开盘前或信号时点：
    - 冻结 `signal_intent`
    - 做 go/no-go
    - 仅当通过时生成真实委托
  - 盘中：
    - 跟踪回报
    - 撤单/重报
    - 断线重连
  - 收盘后：
    - 对账
    - 写日报
    - 写异常台账

## 自动开真实仓必须满足的安全闸门

1. `intent freeze`
   - 信号一旦冻结，不允许事后改手数、改方向、改合约。
2. `idempotency`
   - 同一个 `intent_id` 只能落成一组真实订单，不允许重复触发。
3. `broker-state-first`
   - 每次发单前，先读真实持仓和未完成委托，不以本地缓存为准。
4. `deployment gate`
   - 若部署层不允许新增真实单，即使有信号也只能记录，不得发单。
5. `position reconcile`
   - 若真实持仓与目标持仓偏差超阈值，自动降级到只读。
6. `kill switch`
   - 必须支持人工一键切换 `readonly`。

## 当前仓库可直接复用的资产

- 信号/影子盘协议：
  - `examples/portfolio_backtesting/build_qmt_roll_stage155_stage78_shadow_daily_protocol.py`
  - `examples/portfolio_backtesting/build_qmt_roll_stage154_stage78_shadow_execution_ledger.py`
- 正式信号入口：
  - `examples/portfolio_backtesting/build_qmt_roll_stage78_1_shadow_daily_runner.py`
- SimNow/CTP 只读探针：
  - `examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py`
  - `examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh`
- 部署账本/日报：
  - `examples/portfolio_backtesting/build_qmt_roll_stage237_balanced_tranche_shadow_ledger.py`
  - `examples/portfolio_backtesting/build_qmt_roll_stage238_balanced_tranche_shadow_daily_bundle.py`
- 实盘准入审计：
  - `examples/portfolio_backtesting/build_qmt_roll_stage148_stage78_live_go_no_go_audit.py`

## 当前还缺什么

- 真实 `broker_adapter` 的订单状态机
- `intent_id -> broker_order_id -> trade_id` 的持久映射
- 重启恢复逻辑
- `readonly / simulate / paper_send / real_send` 模式总开关
- 真实账户余额接线
- 异常和熔断 SOP

## 我建议的四阶段上线顺序

### Phase A 只读常驻

- 常驻连接柜台
- 自动拉账户、持仓、委托、成交
- 不发单

### Phase B 半自动执行

- 自动生成真实委托草案
- 人工确认后才真正提交
- 用于验证订单状态机和对账

### Phase C 受限自动开仓

- 只开放最小规模
- 只允许白名单品种
- 只允许开仓，不允许自动扩张
- 失败即降级只读

### Phase D 完整自动执行

- 支持重试、撤单、补单
- 支持夜盘
- 支持真实账户部署账本联动

## 当前结论

- 是否需要持久服务：是。
- 是否需要自动开真实仓：可以，但必须以执行架构为前提。
- 当前最合理下一步：先做 `Phase A/B`，不要直接跳 `Phase C/D`。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段是执行架构设计，不调策略参数、不追求收益最优。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：如果没有这套架构，后面所有“自动开真实仓”的讨论都会退化成危险的脚本发单。
