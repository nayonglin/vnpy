# Stage081 C9 剔除 2026-06-12 MA609 影子交易反事实

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 22:13 CST
- 阶段性质：只读执行账本反事实
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：通用 backtesting 资料和 `futures-official-shadow` 技能都强调区分成交记录、当前持仓和 pending orders；但本次数值必须以本仓库 C9 引擎输出为准。
- 我的判断：本阶段不重跑策略、不改参数，只回答“如果不包含最后一天 MA609 这笔影子交易，当前账本指标是什么”。由于该交易发生在最新完成交易日 `2026-06-12`，剔除它等价于把 6/12 的 MA609 开仓、当日浮亏、滑点、持仓保证金和 pending 平仓从账本中拿掉。

## 剔除对象

- 成交：`MA609.CZCE` `Long Open` `12` 手，成交价 `3029`
- target-date pending：`MA609.CZCE` `Short Close` `12` 手，理论价 `3010`
- trade event：`long_risk_cluster_heat_deleverage`
- 当日影响：
  - trading_pnl：`-2,280`
  - slippage：`120`
  - net_pnl：`-2,400`
  - margin_exact：`43,344`
  - broker10_margin_exact：`47,678.4`

## 结果对比

| 指标 | 原 C9 shadow | 剔除 MA609 后 |
| --- | ---: | ---: |
| 期末权益 | 265,860 | 268,260 |
| 总收益 | -11.3800% | -10.5800% |
| CAGR | -24.3675% | -22.7798% |
| 最大回撤 | -14.8955% | -14.8955% |
| Sharpe | -1.1331 | -1.0420 |
| 最低权益 | 265,560 | 265,560 |
| max broker10 | 54.8506% | 54.8506% |
| p95 broker10 | 31.8104% | 31.8104% |
| 总滑点 | 3,860 | 3,740 |
| 总交易次数 | 27 | 26 |
| 非零日胜率 | 45.7143% | 47.0588% |
| deployable_pass | 1 | 1 |

## 6 月结果对比

| 指标 | 原 6 月 | 剔除 MA609 后 |
| --- | ---: | ---: |
| 期初权益 | 265,800 | 265,800 |
| 期末权益 | 265,860 | 268,260 |
| 月收益 | 0.0226% | 0.9255% |
| 最大回撤 | -4.6687% | -3.9049% |
| 交易数 | 3 | 2 |
| 滑点 | 180 | 60 |
| max broker10 | 17.9336% | 14.7619% |

## 当前执行状态

- 当前持仓：空
- pending orders：空
- target-date entry candidates：`0`
- order API：未调用

## 输出文件

- counterfactual JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_without_ma609_20260612_counterfactual.json`

## 结论

- 如果不包含这笔 MA609 交易，当前 C9 影子盘权益应为 `268,260`，总收益 `-10.58%`，交易次数 `26`，总滑点 `3,740`。
- 更重要的是，当前不会有 `MA609.CZCE` 持仓，也不会有 `MA609.CZCE Short Close 12 @3010` 的 pending 平仓。
- 如果真实账户本来没有这笔 MA 多头，就不应该追这个影子 pending close；应视为 shadow 与真实账户状态不一致，真实执行 fail-closed。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：这只是最后一天单笔成交的账本剔除，不改变 C9 规则、不改变未来选品/开平仓逻辑，也不据此优化参数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：它能明确真实账户若没有 MA 多头时的执行纪律，避免把影子盘 pending close 误当成必须追单。
