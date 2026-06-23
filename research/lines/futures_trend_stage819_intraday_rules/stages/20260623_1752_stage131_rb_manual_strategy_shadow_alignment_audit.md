# Stage131 rb 手动开仓是否已进入策略 shadow 的只读审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-23 17:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：官方实盘账户状态解释与接管审计。
- 是否重要突破：否。属于账户/shadow 对齐状态确认，不改变策略 alpha、AI 池、手数、止损线或真实提交闸门。
- 是否触发A/B：否。

## 本次问题

用户问是否可以把当前已有的 `rb2610.SHFE` 持仓标记为策略开仓，因为策略本来预期要开仓，只是 2026-06-22 晚间自动化 bug 未自动开仓，用户才手动在手机 app 上开仓。

## 审计结果

- 最新 Stage901 shadow 已经把 `rb2610.SHFE` 识别为策略持仓：
  - `qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_current_positions_...csv`
  - `rb2610.SHFE`，direction `short`，`end_pos=-11`，date `2026-06-23`，close `3112.0`，策略保证金 `34232.0`。
- 最新 Stage901 trade 也包含该笔策略开仓：
  - `qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_trades_...csv`
  - `rb2610.SHFE`，direction `空`，offset `开`，volume `11`，price `3127.0`，date `2026-06-23`。
- 最新 Stage901 entry_risk 显示 2026-06-23 的 `FG609.CZCE` 新开仓 sizing 已经扣除了 rb 的策略保证金占用：
  - `total_margin_in_use_before=34232.0`
  - `estimated_equity=153190.0`
  - `free_capital=118958.0`
  - `limited_balance=103639.0`
  - `selected_volume=15`
- 结论：当前不是“rb 未标记为策略仓”的问题。策略 shadow 侧已经承认 rb 是策略仓，并且后续 FG 手数计算已经把 rb 占用资金纳入。

## 当前阻断点

- 最新 Stage903/930 post_close 仍显示：
  - `stage906_reconciliation_status=reconcile_fail_closed_broker_snapshot_unusable`
  - `stage907_effective_refresh_mode=plan-only`
  - `stage904_monitor_status=intraday_monitor_skipped_outside_market_session`
  - `order_api_called_count=0`
- 原因是当前处于 post_close，按 Stage130 新口径不在 16:35/盘后硬连 CTP，所以 broker 快照不可用或过期时不会在盘后直接验证对齐。
- 下一步要等 20:55/交易时段 fresh Stage907 重新读取 production-live broker snapshot。若 broker 侧确认 `rb2610.SHFE` 空单 11 手，Stage906 应从 `snapshot_unusable/divergent` 进入 `reconcile_aligned` 或至少产生明确差异。

## 处理原则

- 不新增绕过 Stage906/927 的手工标记。
- 不把所有 broker/shadow 差异都当作策略仓。
- 只允许当 Stage901 shadow 持仓与 broker fresh 持仓在合约、方向、手数上匹配时，进入正常 aligned 自动化。
- 如果 broker fresh 持仓与 Stage901 不一致，继续 fail-closed，并只允许已有仓位的降风险/止损通道按既有 close-only 规则处理。

## 过拟合反思

- 运行前判断：否。这是账户状态恢复和执行一致性审计，不涉及策略参数或收益样本选择。
- 运行后判断：否。没有因为 rb 这笔交易反向修改信号、手数或止损规则。

## 继续价值反思

- 运行前判断：是。若误以为 rb 没有进入策略账本，会错误新增绕过对账的特殊标记。
- 运行后判断：是。确认 rb 已在 Stage901 shadow，可避免不必要的代码分支；后续重点转为交易时段 fresh broker 对账。

## 后续 TODO

- 20:55 后检查 Stage907/Stage906 最新结果，确认 broker 是否 fresh 读到 `rb2610.SHFE short 11`。
- 如果 broker 与 shadow aligned，再观察 `FG609.CZCE` 是否仍因合约元数据、Stage260/905/927/931 闸门被阻断。
- 如果 broker 读不到或手数不一致，保持 fail-closed，不开新仓。
