# Stage016 入场前短影线质量特征审计

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：day
- 记录时间：2026-06-08 22:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读特征审计，风险放大前置验证
- 是否重要突破：否
- 是否触发A/B：已读取 `skills/version-ab-experiment/SKILL.md`；本想法属于可能影响正式风险 sizing 的候选，但本阶段未通过只读闸门，所以未进入 A/C 回测。

## 外部调研与判断

- 参考资料：
  - https://docs.tradingmetrics.com/en/technical-analysis/trading-patterns/candlestick-patterns/special-patterns/marubozu
  - https://therobusttrader.com/marubozu-candlestick-pattern/
  - https://www.litefinance.org/blog/for-beginners/how-to-read-candlestick-chart/what-is-marubozu-candlestick-pattern/
  - 仓库历史：`futures_swing_no_lower_shadow` 独立无影线波段线，Stage009 最好版本仅 `0.4770%` 收益、Sharpe `0.0481`，2倍滑点转负；Stage062 微观结构影子 AI 使用上下影线/有利不利影线等特征，测试集 AUC `0.4387`，不能接策略。
- 我的判断：短影线/Marubozu-like 的第一性原理是“单根 K 线几乎没有反向试探，单边控制更强”，它可以作为趋势延续质量的候选特征；但外部资料和仓库历史都说明不能单独当 alpha。用户这次不是要做独立无影线开仓，而是想把它作为正式趋势策略所有交易的风险放大特征，因此必须先证明它在正式成交中跨年、跨品种、跨方向稳定提升 R 分布和大赢家率。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage733_shadowless_preentry_quality.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增只读可靠性闸门：
  - `MIN_RELIABLE_ROWS=30`
  - `MIN_RELIABLE_YEARS=5`
  - `MIN_RELIABLE_PRODUCTS=8`
  - `MAX_DOMINANT_PRODUCT_SHARE=0.30`
  - `MIN_AVG_R_LIFT=0.50`
  - `MIN_BIG_WINNER_RATE_LIFT_PP=5.0`
  - `MIN_POSITIVE_R_YEARS=5`
  - `MAX_BAD_RATE_PCT=55.0`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage719 当前正式 Stage372/20万 closed lots，全周期 `2020-01-03` 至 `2026-04-30` 附近。
- 账户规模：正式版参考 `200,000`。
- 成本口径：本阶段不是权益回测，使用 Stage719 已成交 closed lots 的 realized PnL/R。
- 样本过滤：Stage719 正式 closed lots `320` 笔；可计算入场前影线特征 `320` 笔；R 倍数有效 `313` 笔。
- 策略/归因口径：每笔实际入场只使用 `entry_date` 之前已完成的合约日线，避免使用入场日后信息；不扫小数阈值，只看预声明短影线桶：
  - `pre1_total_wick_le20`
  - `pre1_total_wick_le30`
  - `pre1_both_wicks_le10`
  - `pre1_adverse_wick_le10`
  - `pre1_directional_close_strength_ge80`
  - `pre1_marubozu_directional`
  - `pre2/3/5_avg_total_wick_le30`
  - `pre3/5_short_wick_count`
  - `pre3/5_marubozu_count`

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
  - `pre1_total_wick_le20`：`55` 笔，avg R `-0.4873`，avg R lift `-0.9844`，big winner rate `3.6364%`，低于 baseline `5.3093pp`。
  - `pre1_total_wick_le30`：`85` 笔，avg R `0.0763`，avg R lift `-0.4208`，big winner rate `5.8824%`，低于 baseline `3.0633pp`。
  - `pre1_marubozu_directional`：`49` 笔，avg R `0.3969`，avg R lift `-0.1001`，big winner rate `4.0816%`，低于 baseline `4.8641pp`。
  - `pre3_avg_total_wick_le30`：`20` 笔，胜率 `70.0000%`，bad rate `10.0000%`，big winner rate `15.0000%`，但样本不足，avg R `0.2302` 仍低于 baseline，positive R years 仅 `3`，不能作为风险放大特征。
  - 28 笔 big winner 中，`pre1_total_wick_le20` 只有 `2` 笔，占 `7.1429%`；全体有效样本该特征占比 `17.5719%`。top20 R 赢家中，多数前一根完整日 K 并非短影线。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage733_shadowless_preentry_quality_report_stage733_shadowless_preentry_quality_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage733_shadowless_preentry_quality_feature_metrics_stage733_shadowless_preentry_quality_v1.csv`
- orders：不适用
- daily：不适用
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage733_shadowless_preentry_quality_enriched_closed_lots_stage733_shadowless_preentry_quality_v1.csv`
- 其他：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage733_shadowless_preentry_quality_year_detail_stage733_shadowless_preentry_quality_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage733_shadowless_preentry_quality_decision_stage733_shadowless_preentry_quality_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage733_shadowless_preentry_quality_chart_stage733_shadowless_preentry_quality_v1.png`

## 结论

- 本阶段结论：按“入场前已完成合约日线短影线/Marubozu-like”定义，没有找到可用于所有交易扩大风险资金的可靠特征。用户观察到的“很多优质交易之前影线很短”在正式 closed lots 统计里不成立，至少不是最后 1 根已完成日 K 的稳定规律；部分 `pre3` 平均短影线桶胜率较高，但样本过小且 avg R 不优，不能交易化。
- 是否进入下一步：不进入 A/C 风险放大回测，不改正式版。
- 下一步：如果继续沿这个方向，只能做两种更明确的只读审计：一是确认用户肉眼看到的是不是“入场后早期 K 线”而非入场前 K 线；二是把影线特征放入 forward watch，不调阈值、不叠品种/年份/方向。

## 过拟合反思

- 运行前判断：存在过拟合风险，因为“看到很多优质交易之前影线短”容易从历史赢家视觉复盘中产生幸存者偏差；但本阶段只读审计、低自由度阈值、不接仓位，风险可控。
- 运行后判断：不能继续为短影线扫 `0.15/0.18/0.25`、N日窗口或叠加品种/年份/方向条件，否则就是在已知赢家图形上过拟合。
- 原因：短影线特征未在全体正式成交中提升大赢家率和 avg R，且 top winner 的前1根 K 线多数并不短影线。

## 继续价值反思

- 运行前判断：有价值，因为该特征有明确价格行为解释，也与既有微观结构特征体系相关。
- 运行后判断：作为直接风险放大特征继续价值低；作为解释/forward watch 仍有有限价值。
- 原因：当前证据不支持扩大所有交易风险资金；但它能帮助澄清视觉观察到底发生在入场前、入场后早期，还是只存在于少数局部赢家。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为风险放大特征反证记录。
