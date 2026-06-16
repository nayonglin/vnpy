# Stage442 当前官方 C9 默认影子盘 pending 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-15 22:00 CST
- 阶段性质：官方 shadow 技能兼容记录
- 是否重要突破：是。官方 live default 已不是 Stage372，而是 C9。
- 是否触发A/B：否，本阶段只做执行检查。

## 外部调研与判断

- 参考资料：`futures-official-shadow` 技能要求不能只看 `signal_plan`，必须检查 target-date 后 `active_limit_orders`，避免最终交易日 pending order 被漏掉。
- 我的判断：该要求成立。C9 切为 live default 后，旧技能脚本仍绑定 Stage659/Stage372 `_official_live_spec`，会报 `official live base profile not found: stage847_c9_30w_stage819_05r_stop_retry`。因此已在 Stage847/C9 引擎和 Stage901 runner 中直接导出 `active_limit_orders`，作为 C9 当前 pending 审计来源。

## 结果

- 区间：`2026-01-01 -> 2026-06-12`
- 当前 live default：`official_live_stage847_c9_30w_stage819_05r_stop_retry_once`
- 期末权益：`265,860`
- 总收益：`-11.38%`
- 最大回撤：`-14.8955%`
- Sharpe：`-1.1331`
- 总滑点：`3,860`
- 总交易次数：`27`
- 胜率：`45.7143%`（非零日）
- target-date 后 pending：`1`
- pending 明细：`MA609.CZCE` `Short Close` `12` 手，理论价 `3010`，状态 `Submitting`
- target-date close reason：`long_risk_cluster_heat_deleverage`
- target-date entry candidates：`0`
- order API：`order_api_called=false`

## 结论

- 本阶段结论：下一交易时段的理论动作不是新开仓，而是 C9 影子盘 `MA609.CZCE` 多头 `12` 手的平仓 pending。真实执行前必须确认券商/SimNow/实盘账户确有匹配多头；若无匹配持仓，必须 fail-closed。
- 下一步：如用户要求真实处理，先走 CTP/SimNow SOP 的 read-only 账户/持仓/前置 runtime gate，再 dry-run 和显式确认。

## 反思

- 过拟合反思：否。本阶段是固定 live default 的执行审计，没有新增参数。
- 继续价值反思：是。pending 审计能避免把历史成交信号误判为下一时段开仓，或漏掉最终交易日平仓 pending。
