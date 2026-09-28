# Stage001 全市场PIT单槽替换覆盖审计

- 决策：`stage001_full_market_coverage_fail_close_shape_no_labels`。
- 评估月：`54`；覆盖行/合格行/池外挑战行：`4097/2968/2066`。
- 每月合格品种最小/中位/最大：`4` / `57.0` / `66`。
- A-rank10合格月/动作就绪月：`48` / `46`；合格月池外挑战者最小值：`0`。
- 拒绝原因：`{"activity_ratio_below_minimum": 77, "curve_contract_count_below_minimum": 73, "eval_date_close_missing": 26, "exchange_not_allowed": 395, "mapping_days_below_minimum": 169, "one_lot_margin_above_capital": 4, "valid_close_days_below_minimum": 385}`。
- 本阶段未读取收益标签、未fit/predict、未回测、未连接CTP、未调用订单API。
- 通过仅允许下一阶段特征预注册，不授权标签、模型或真实引擎。
