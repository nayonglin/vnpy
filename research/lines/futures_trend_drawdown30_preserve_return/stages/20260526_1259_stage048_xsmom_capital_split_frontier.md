# Stage048 横截面动量卫星资金拆分粗前沿

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-26 12:59 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：低相关收益源真实资金拆分粗前沿
- 是否重要突破：阶段性候选，但不是正式突破
- 是否触发A/B：是，C3 50万基准 vs C3+xsmom 真实资金拆分候选

## 外部调研与判断

- 参考资料：复用 Stage045 对商品横截面动量/相对强弱因子的调研结论，本阶段不新增外部资料。
- 我的判断：横截面动量有独立经济含义，但净值层权重不能直接等价为期货账户里的整数手数、保证金和资金占用；本阶段只验证承载方式是否可行。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage348_xsmom_capital_split_frontier.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 总资金固定 `500,000`
  - C3/卫星资金拆分：`50/0`、`45/5`、`40/10`、`35/15`、`30/20`、`25/25` 万
  - 卫星执行口径：`floor_per_leg_cap`、`min1_cheapest_cap`、`min1_all_if_cap_allows`、`min1_all_no_cap_diagnostic`
- 修改参数：无正式参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：沿用 C3 与 xsmom 卫星各自脚本的滑点/手续费口径
- 样本过滤：不新增品种黑名单，不按单一窗口筛选
- 策略/归因口径：复用 Stage325 C3 真实资金路径，只替换卫星腿为 Stage045 横截面动量整数手数执行

## 结果

- 期末权益：最佳候选 `26,147,995`
- 总收益：最佳候选 `5129.5990%`
- 最大回撤：最佳候选 `-27.9488%`
- Sharpe：最佳候选 `1.7013`
- 总滑点：最佳候选组合估算 `1,278,330`
- 总交易次数：最佳候选组合 `1199`
- 胜率：未输出逐笔胜率；日度正收益比例 `51.5666%`
- 其他关键指标：
  - 最佳候选：`c3_350_sat_150` / `min1_cheapest_cap`
  - 相对50万C3收益保留 `84.2973%`
  - 卫星独立收益 `417.3000%`
  - 卫星最大回撤 `-44.9116%`
  - 卫星总滑点 `10,030`
  - 卫星成交合约数 `448`
  - 最大卫星保证金 `149,729.4`
  - 最大组合保证金/权益 `91.3712%`
  - `review_days=7`，`reject_days=0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage348_xsmom_capital_split_frontier_report_stage348_xsmom_capital_split_frontier_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage348_xsmom_capital_split_frontier_summary_stage348_xsmom_capital_split_frontier_v1.csv`
- orders：无
- daily：本阶段未单独导出组合daily
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage348_xsmom_capital_split_frontier_decision_stage348_xsmom_capital_split_frontier_v1.json`

## 结论

- 本阶段结论：`c3_350_sat_150/min1_cheapest_cap` 在全样本粗前沿中同时满足回撤30以内、收益保留80%以上和保证金不拒绝，是研究候选。
- 是否进入下一步：进入多周期与滑点压力反证。
- 下一步：固定 `35万C3 + 15万xsmom卫星`，不调小数权重，做起始年份、弱窗口和滑点压力。

## 过拟合反思

- 运行前判断：不是过拟合，因为只做粗资金拆分和可交易执行约束，不看单品种黑名单或单窗口修补。
- 运行后判断：本阶段本身不是过拟合，但全样本候选有路径偶然性，必须马上进入反证。
- 原因：候选刚好处在收益保留边界附近，如果继续扫 `34/16`、`36/14` 或调整入选篮子数量，就会变成结果导向调参。

## 继续价值反思

- 运行前判断：有价值，因为 Stage046 反证了 `3.75万` 卫星资金太小，本阶段检验更现实的卫星资金承载能力。
- 运行后判断：有价值，但只限下一步反证；不能直接晋级。
- 原因：全样本结果过线，但没有证明多起点、弱窗口和成本压力仍稳。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要候选发现与后续反证链条的一部分
