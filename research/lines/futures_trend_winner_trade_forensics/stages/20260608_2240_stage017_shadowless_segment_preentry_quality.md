# Stage017 入场前一段时间短影线质量特征审计

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：day
- 记录时间：2026-06-08 22:40 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读特征审计，修正 Stage016 “只看前一根 K 线”口径
- 是否重要突破：否
- 是否触发A/B：已读取 `skills/version-ab-experiment/SKILL.md`；本想法属于可能影响正式风险 sizing 的候选，但只读闸门未通过，所以未进入 A/C 回测。

## 外部调研与判断

- 参考资料：
  - https://therobusttrader.com/marubozu-candlestick-pattern/
  - https://hmarkets.com/blog/candlestick-basics-12-candlestick-patterns/
  - https://learn.bybit.com/en/candlestick/trading-crypto-with-marubozu-candle-pattern
  - https://wrtrading.com/technical-analysis/charts/candlestick/pattern/long-wicks/
- 我的判断：外部资料支持 Marubozu/短影线代表单边控制、长影线代表反向试探或拒绝，但都强调必须结合趋势上下文。用户澄清不是“前一根 K 线”，而是“前一段时间”，所以本阶段改为窗口级特征：前 `10/20/40` 个交易日短影线比例、长影线比例、平均总影线、平均不利影线、实体占比和方向性收盘强度。运行前判断：该思路有第一性原理价值，但容易把少数历史赢家的视觉印象误当作普遍规律；必须先只读审计。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage734_shadowless_segment_preentry_quality.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增只读窗口：
  - `WINDOWS=[10,20,40]`
  - `short30_ratio`：窗口内 `total_wick_pct_of_range<=30%` 的比例
  - `long60_ratio`：窗口内 `total_wick_pct_of_range>=60%` 的比例
  - `body60_ratio`：窗口内 `body_pct_of_range>=60%` 的比例
  - `avg_adverse_wick_pct`
  - `avg_directional_close_strength`
  - `pre20/pre40_clean_segment_combo`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage719 当前正式 Stage372/20万 closed lots，全周期 `2020-01-03` 至 `2026-04-30` 附近。
- 账户规模：正式版参考 `200,000`。
- 成本口径：本阶段不是权益回测，使用 Stage719 已成交 closed lots 的 realized PnL/R。
- 样本过滤：Stage719 正式 closed lots `320` 笔；窗口特征可计算 `320` 笔；R 倍数有效 `313` 笔。
- 策略/归因口径：每笔实际入场只使用 `entry_date` 之前已完成的合约日线，窗口固定 `10/20/40`，不做小数阈值扫描；可靠性闸门沿用 Stage016：样本 `>=30`、年份 `>=5`、品种 `>=8`、最大单品种占比 `<=30%`、方向数 `>=2`、avg R lift `>=0.50`、big winner rate lift `>=5pp`、正 R 年份 `>=5`、bad rate `<=55%`。

## 结果

- 期末权益：不适用，本阶段不是权益回测；正式版参考仍为 `8,728,285`
- 总收益：不适用；正式版参考仍为 `4264.1425%`
- 最大回撤：不适用；正式版参考仍为 `-38.6713%`
- Sharpe：不适用；正式版参考仍为 `1.6279`
- 总滑点：不适用；正式版参考仍为 `506,220`
- 总交易次数：正式版 raw trades 参考 `633`；本阶段 closed lots `320`
- 胜率：baseline 有效样本胜率 `44.7284%`
- 其他关键指标：
  - baseline：有效样本 `313`，avg R `0.4971`，median R `-0.1818`，big winner rate `8.9457%`，quality winner rate `20.1278%`，bad rate `23.6422%`。
  - 通过完整可靠性闸门特征数：`0`。
  - `pre10_directional_close_strength_ge60`：`80` 笔，avg R `1.2294`，avg R lift `+0.7323`，big winner rate `11.2500%`，big winner lift `+2.3043pp`，positive R years `6`，但大赢家提升不足 `+5pp`，未通过闸门。
  - `pre10_body60_ratio_ge50`：`61` 笔，avg R `1.0091`，avg R lift `+0.5120`，big winner rate `9.8361%`，big winner lift 仅 `+0.8904pp`，未通过闸门。
  - `pre10_avg_adverse_wick_le25`：`108` 笔，avg R `0.8730`，avg R lift `+0.3759`，big winner rate `7.4074%`，低于 baseline。
  - 严格“一段时间短影线”类：`pre10_short30_ratio_ge50` 仅 `11` 笔且 big winner `0`；`pre20_short30_ratio_ge50` 仅 `2` 笔；`pre20_clean_segment_combo`、`pre40_clean_segment_combo` 没有覆盖任何大赢家。
  - 28 笔 big winner 中：`pre10_directional_close_strength_ge60` 覆盖 `9` 笔，占 `32.1429%`；`pre10_body60_ratio_ge50` 覆盖 `6` 笔，占 `21.4286%`；`pre10_short30_ratio_ge50` 覆盖 `0` 笔；`pre20/pre40_clean_segment_combo` 覆盖 `0` 笔。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage734_shadowless_segment_preentry_quality_report_stage734_shadowless_segment_preentry_quality_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage734_shadowless_segment_preentry_quality_feature_metrics_stage734_shadowless_segment_preentry_quality_v1.csv`
- orders：不适用
- daily：不适用
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage734_shadowless_segment_preentry_quality_enriched_closed_lots_stage734_shadowless_segment_preentry_quality_v1.csv`
- 其他：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage734_shadowless_segment_preentry_quality_year_detail_stage734_shadowless_segment_preentry_quality_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage734_shadowless_segment_preentry_quality_decision_stage734_shadowless_segment_preentry_quality_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage734_shadowless_segment_preentry_quality_chart_stage734_shadowless_segment_preentry_quality_v1.png`

## 结论

- 本阶段结论：用户澄清后的“一段时间影线短”口径下，严格短影线段特征仍不能作为所有交易扩大风险资金的可靠开关。更有信息的是“前10日方向性收盘强度”和“前10日实体占比”，但它们不是纯短影线特征，且大赢家捕获提升不够，不应直接进入风险放大。
- 是否进入下一步：不进入 A/C 风险放大回测，不改正式版。
- 下一步：如果继续，只能把 `pre10_directional_close_strength_ge60` / `pre10_body60_ratio_ge50` 作为 watch 特征，或者做“入场后前几根 K 线顺畅程度”对锁盈/减仓的解释；不要扫 `10/15/20/30/40` 窗口和 `0.25/0.35/0.45` 阈值。

## 过拟合反思

- 运行前判断：有过拟合风险，因为这是从历史优质交易图形观察出发的特征。
- 运行后判断：严格短影线段被反证；继续通过微调窗口/阈值或叠品种、年份、方向救援会过拟合。
- 原因：大赢家并不集中在“前一段时间影线很短”的窗口里，真正有一点信息的是方向/实体控制，而不是“几乎无影线”。

## 继续价值反思

- 运行前判断：有价值，因为它修正了 Stage016 误解用户口径的问题。
- 运行后判断：作为风险放大规则价值低；作为价格行为 watch 特征仍有有限价值。
- 原因：`pre10_directional_close_strength_ge60` 有 avg R 线索，但未达到大赢家捕获门槛；需要 OOS/forward watch，而不是直接交易化。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为用户澄清后对“前一段时间影线短”的最终只读审计。
