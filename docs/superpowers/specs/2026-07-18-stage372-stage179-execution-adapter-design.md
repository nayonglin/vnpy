# Stage372 接入 Stage179 实盘可靠性底座设计

**状态：** 2026-07-18 用户批准按既有 Stage179 Spec 继续执行；本设计固化 Stage372 官方口径的接入边界。代码合入不等于实盘激活。

**目标：** 让 `official_live_stage372_20w_recovery_sleeve` 在不引入 C9 `0.5R` 实时止损/重进场语义的前提下，复用 Stage179 的行情时间因果、耐久 intent、执行账本、cycle authorization、预热 CTP 和分段延迟证据。

## 1. 第一性原则与结论

执行可靠性和策略语义是两个不同的变化轴。可靠性层可以决定一条已批准指令怎样被准时、唯一、可追溯地送达；它不能决定何时交易、交易什么或是否重进场。

因此采用“显式 execution profile + 归一化 daily intent + 单一 broker boundary”的方案：

```text
Stage372 官方 signal/current-position artifacts
  -> Stage260 broker-state daily gate
  -> Stage372 daily-intent adapter
  -> Stage179 SQLite spool / execution ledger / cycle authorization
  -> Stage931 warm MainEngine.send_order boundary
```

Stage608 的 tick ingress、runtime profile、release manifest、LaunchAgent 生命周期和 Stage931 预热执行器继续复用。Stage904、Stage941 及其 C9 状态库不在 Stage372 profile 的依赖图中。

## 2. 方案比较

### 2.1 采用：显式 profile 隔离

- 建立不可变 `OfficialExecutionProfile`，同时绑定版本、资金、artifact 路径和允许的 intent source。
- Stage372 profile 只允许 `stage260_stage372_daily`，并声明 `intraday_stop_retry_enabled=false`。
- C9 profile 保留历史兼容，但必须显式选择；不能成为生产入口默认值。
- Stage260 输出经独立 adapter 归一化后进入 Stage905/Stage179 spool；Stage931 继续是唯一 `MainEngine.send_order` 边界。

优点是语义边界可测试、manifest 可绑定、Stage372/C9 不共享隐式全局身份。代价是 Stage260/903/905/930/931 需要少量 profile 注入。

### 2.2 否决：直接把当前全局 config 改回 Stage372

当前 Stage904/905/930/931 同时导入 C9 状态机。只替换常量会让 C9 intent 可能以 Stage372 身份进入账本，或者导致旧 artifact 被误读。该方案不能证明策略语义未变化。

### 2.3 否决：复制一套 Stage372 broker adapter

复制 Stage931 会形成两个报单边界，去重、回调、late fill 和回滚能力容易漂移。官方 vn.py 架构已经提供统一 `MainEngine.send_order -> Gateway` 边界，策略差异应在上游 intent 归一化完成。

## 3. Profile 与身份契约

`OfficialExecutionProfile` 至少包含：

- `profile_key`
- `official_version`
- `alias`
- `source_stage`
- `capital` / `capital_label`
- `summary_path` / `signal_plan_path` / `current_positions_path`
- `allowed_intent_sources`
- `intraday_stop_retry_enabled`

Stage372 固定值：

- profile：`stage372-20w`
- version：`official_live_stage372_20w_recovery_sleeve`
- capital：`200000` / `20w`
- source：`Stage372`
- allowed source：`stage260_stage372_daily`
- intraday：`false`

profile 必须由 CLI、Stage260 summary、Stage905 intent、spool payload、submit authorization、release manifest 和 Stage931 启动参数端到端一致绑定。任一缺失、版本/资金不一致或 profile 不支持都失败关闭。

## 4. Stage260 到 Stage905 的日线适配

Stage260 继续以 fresh broker account/position/order snapshot 为事实源。adapter 只接受 `execution_action=simnow_executable` 的行，并重新验证：

1. summary profile/version/capital 与当前 profile 完全一致；
2. Stage260 `order_api_called_count=0`；
3. decision 的交易日、方向、offset、数量和价格字段完整；
4. open 在 `review` 风险下阻断；close 必须有足够 broker 持仓；
5. 同一规范化 payload 生成确定性 `intent_id`；
6. intent source 固定为 `stage260_stage372_daily`。

adapter 不读取 Stage904 artifact，不推导止损价，不生成 retry open，也不修改 Stage372 signal plan。Stage905 在 Stage372 profile 下必须显式收到“intraday disabled”输入；若发现 Stage904 action、C9 source、C9 role 或 C9 position-cycle 字段，整批失败关闭。

## 5. Stage903/930 运行模式

Stage903 增加显式 `--execution-profile`。Stage372 模式：

- 运行 shadow/readonly/Stage260/Stage905/reconciliation；
- 不运行 Stage904；计划中记录 `intraday_not_applicable_profile_disabled`，不能把它当作通过的 C9 gate；
- Stage905 只消费 Stage260 daily adapter 输出。

Stage930 的 Stage372 模式：

- 不启动 Stage941 persistent detector；
- 不运行 fast intraday lane；
- 保留 Stage608 stream、warm Stage931、cycle authorization 和 deadline；
- watched symbols 来自 Stage372 当前 signal/position universe；
- AI pool stale 仍阻断新开仓，但不能阻断合法风险降低 close。

C9 模式维持现有行为，但不得由 Stage372 LaunchAgent 或 manifest 选择。

## 6. Stage931 与 manifest

Stage931 不再只信模块级 `OFFICIAL_LIVE_*`。它从显式 profile 得到预期版本/资金，并逐层校验：

- release manifest；
- Stage905 summary 与 ready intent；
- spool row；
- cycle authorization；
- execution ledger reservation。

Stage372 profile 对 source 使用 allowlist。任何 `stage904_c9_intraday_close`、`stage904_c9_intraday_retry_open` 或 C9 role 均在 API slot 预留前阻断。`production-readonly` 仍保持 `send/cancel=0/0`，且不加载 spool 或 submit adapter。

## 7. 部署隔离

- 新增 Stage372 day/night LaunchAgent 模板，label、日志、runtime root、spool、ledger、readiness 与现有 C9 全部分离。
- 新 plist 和代码可以合入，但默认不安装、不 load、不 kickstart。
- 当前 C9 线上进程不在代码验收阶段停止或替换。
- 只有不可变 Stage372 manifest、独立终审、真实 `production-readonly` 0/0 CTP、SimNow/券商测试验收全部通过后，才允许提出 production-live 激活方案；真实报单仍需用户另行明确授权。

## 8. 测试与验收

必须覆盖：

1. Stage372 profile 的历史官方常量和路径精确一致；默认生产 profile 为 Stage372。
2. Stage372 只接受 Stage260 daily intents；任意 C9 action/source/role 失败关闭。
3. Stage905 不会在 Stage372 模式回退读取磁盘 Stage904 artifact。
4. Stage903/930 在 Stage372 模式不创建 Stage904/941 子进程，且不运行 fast intraday lane。
5. profile/version/capital/path/manifest 任一错配均在 spool/API slot 前阻断。
6. 同一 Stage260 decision 重放得到同一 intent id；多进程竞争仍只有一个发送赢家。
7. Stage372 no-submit LaunchAgent 静态检查、TERM/KILL 生命周期和独立 runtime root 通过。
8. 全部 Stage179 回归、性能门和 fault matrix 继续通过。
9. 实际 `production-readonly` CTP 验收严格 `send_order=0`、`cancel_order=0`；无此证据不得宣称已在实盘运行。

## 9. 非目标

- 不新增或调整 Stage372 alpha、产品池、AI 池阈值、仓位、资金、recovery sleeve 参数。
- 不给 Stage372 增加实时止损或重进场；如未来需要，必须另建策略研究线、回测、A/B 与独立批准。
- 不在本设计实施期间发送 SimNow、券商测试或真实订单。
- 不自动部署或替换当前 LaunchAgent。
