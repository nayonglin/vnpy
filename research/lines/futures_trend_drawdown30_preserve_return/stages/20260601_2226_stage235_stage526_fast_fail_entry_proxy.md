# Stage235 Stage526快失败入场前代理诊断

- 时间：2026-06-01 22:26 CST
- line_id：`futures_trend_drawdown30_preserve_return`
- 是否重要突破版本：否，是反证阶段。
- 阶段目标：把 Stage234 的事后 `fast_fail` 现象转成入场时可见代理，判断是否值得进入真实引擎 A/C。
- 运行前过拟合判断：否。固定 Stage234 事件集，只新增信号日可见历史收盘序列特征，不改交易规则、不扫参数、不做产品黑名单。
- 运行前继续价值判断：是。若入场前代理能解释快失败，才值得接入策略；若不能，应停止该形状。

## 外部调研和判断

- 调研参考：StockCharts 对 ADX 的说明强调 ADX 衡量趋势强弱，并提示 ADX 过滤也可能同时过滤好坏信号；ATR/Donchian 类公开实现和 GitHub topic 常把突破、ATR、趋势强度、波动扩张组合使用。
- 参考链接：
  - https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-directional-index-adx
  - https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr-and-average-true-range-percent-atrp
  - https://github.com/topics/breakout-strategy
- 我的判断：公开资料给的是“方向族”，不是可以直接复制的商品组合策略。Stage526 的问题带有保证金、成本压力和复利路径约束，必须先用本仓库事件账本证明特征有预测力。

## 本次改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage535_stage526_fast_fail_entry_proxy.py`
- 新增输入：
  - Stage234 事件特征：`qmt_roll_stage534_stage526_negative_event_state_diagnostic_event_features_stage534_stage526_negative_event_state_diagnostic_v1.csv`
  - Stage533 日度持仓收盘序列：`qmt_roll_stage533_stage526_corr_gate_event_attribution_positions_stage533_stage526_corr_gate_event_attribution_v1.csv`
- 新增特征：
  - `dir_ret_1d/3d/5d/10d/20d_pct`
  - `directional_efficiency_10d`
  - `close_breakout_margin_20d_pct`
  - `directional_range_position_20d`
  - `vol_expansion_1_over_10`
  - `entry_weak_stack_count`
- 新增规则探针：
  - `entry_large_delta_low_eff10`
  - `entry_large_delta_weak5_breakout`
  - `entry_low_corr_low_eff10`
  - `entry_low_corr_weak_breakout`
  - `entry_weak_stack_ge5`
  - `entry_large_lowcorr_stack_ge4`
  - `entry_large_stack_ge4`
  - `entry_low_eff_weak5_weak10`
  - `entry_focus_low_eff_weak5`
- 删除参数：无。
- 修改参数：无。

## 结果

- 决策：`entry_proxy_not_ready_keep_stage526`
- 事件数：`171`
- 有收盘特征事件数：`171`
- `fast_fail` 事件数：`72`
- 全部负 edge：`-610,515`
- 全部正 edge：`1,211,000`
- 最强可见代理仅为 `entry_focus_low_eff_weak5`，但只覆盖 `2` 个事件、`-920` edge、快失败覆盖率 `1.3889%`，没有实战价值。
- 能覆盖较多快失败的代理都明显误伤正 edge：
  - `entry_low_corr_weak_breakout`：46事件，负edge `-158,880`，但正edge `+428,825`，总edge `+269,945`。
  - `entry_weak_stack_ge5`：35事件，负edge `-105,680`，但正edge `+248,200`，总edge `+142,520`。
  - `entry_large_delta_low_eff10`：25事件，负edge `-163,615`，但正edge `+229,925`，总edge `+66,310`。

## 参考候选指标

本阶段不产生新权益曲线；参考 Stage526 control：

- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- Ulcer：`14.4691`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 胜率：`53.6330%`
- 3x成本最大回撤：`-42.0555%`

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage535_stage526_fast_fail_entry_proxy_chart_stage535_stage526_fast_fail_entry_proxy_v1.png`
- 左上散点：红色快失败点没有清楚堆在低 `directional_efficiency_10d` 区，很多正贡献也在同一效率区间。
- 右上箱线：快失败、其他负贡献、正贡献三组的 10日趋势效率中位数几乎重叠，不足以作为过滤规则。
- 左下规则探针：负edge红条存在，但多数探针的正edge绿条更大，说明过滤会少吃大波段。
- 右下突破幅度/5日延续：快失败在弱突破区略多，但和正贡献重叠严重，没有稳定分界。

## 结论

- 不能把 Stage234 的 `fast_fail` 直接转成开仓前可见的价格型过滤器。
- 不晋级任何入场前代理规则。
- 不继续扫 ADX/ATR/Donchian/RSI 小阈值；那会把当前 171 个事件拟合掉，但很可能误伤真正大波段。
- Stage526 control 仍保留为主研究候选。

## 后续规划和 TODO

- 停止“入场质量过滤救 Stage526”这条形状。
- 下一步转向 Stage526 的未完成核心风险：3x成本失败和长回撤路径中的交易成本/反复换手累积。
- 优先做只读成本脆弱性诊断：定位 2022 主坏窗口中哪些持仓段、哪些换手日、哪些开平仓簇在 3x 成本下把 DD 推过 40%，再判断是否存在实盘可执行、低自由度的 churn/cost guard。

## 运行后反思

- 是否过拟合：否。结果没有产生新规则，反而否定了最容易过拟合的入场过滤方向。
- 是否还有价值继续做：是，但不是继续救这一组入场代理。价值转移到成本脆弱性和路径管理，因为 Stage526 的 3x成本失败仍是主候选未关账的核心风险。

