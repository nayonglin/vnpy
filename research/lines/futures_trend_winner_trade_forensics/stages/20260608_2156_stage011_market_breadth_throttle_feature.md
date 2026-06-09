# Stage011 市场广度特征审计：0.1 档高质量机会豁免

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-08 21:56 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读特征审计，不做策略权益回放，不改正式版
- 是否重要突破：否，是负结论边界收束
- 是否触发A/B：否；无特征通过预声明可靠性门槛，不进入 A/C

## 外部调研与判断

- 参考资料：
  - `https://tradingstrategy.ai/docs/learn/trend-following.html`
  - `https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/`
  - `https://finlab.finance/docs/en/tools/us_sp500_regime_filter/`
- 我的判断：
  - 市场广度、趋势 regime、仓位 sizing overlay 是通用趋势系统里合理的研究方向；它们的第一性原理是区分“单品种孤立突破”和“横截面趋势扩散”。
  - 但这类特征只有在固定阈值、跨年、跨品种、足够样本下稳定抬高 good rate 且降低 bad rate，才有资格进入策略 A/C；不能因为某个红框窗口或小样本 watch 特征好看就接成豁免。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage729_market_breadth_throttle_feature.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无正式策略参数；审计内固定可靠性门槛为 rows `>=30`、years `>=4`、products `>=6`、dominant product share `<=35%`、good lift `>=10pp`、bad rate `<=60%`、good years `>=4`、positive-score years `>=4`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage716/Stage723 的当前正式 Stage372/20万候选与本地日线库，候选覆盖至 `2026-04-30`
- 账户规模：不适用；只读特征审计
- 成本口径：不适用；不跑策略权益，不产生交易成本曲线
- 样本过滤：Stage723 enriched 的基础 `0.1` 档 H40 可标注可行动候选 `73` 条；官方品种 universe `19` 个
- 策略/归因口径：
  - 对每个候选入场日，统计官方 universe 中同向 `60` 日区间极值广度、同向 `60` 日收益广度、net breadth、market regime、candidate 与 breadth alignment。
  - 不使用品种名、年份、红框窗口作为规则特征。
  - 只判断是否存在可进入 A/C 的初筛特征，不直接交易化。

## 结果

- 期末权益：不适用（只读特征审计）
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：baseline H40 `+2R` 先到率 `30.1370%`
- 其他关键指标：
  - H40 `-1R` 先到 bad rate：`68.4932%`
  - baseline path score：`9.9391R`
  - median available products：`15`
  - min available products：`14`
  - initial gate candidate count：`0`
  - decision：`no_market_breadth_reliable_exemption_feature_found`
  - top watch 1：`product_edge_without_ret_breadth`，rows `14`，good rate `57.1429%`，good lift `+27.0059pp`，失败原因 `rows<30`
  - top watch 2：`market_net_edge=net_support_pos`，rows `33`，good rate `36.3636%`，good lift `+6.2267pp`，失败原因 `good_lift<10pp; bad_rate>60%`
  - top watch 3：`product_edge_and_market_breadth`，rows `13`，good rate `46.1538%`，失败原因 `rows<30; dominant_product_share>35%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage729_market_breadth_throttle_feature_report_stage729_market_breadth_throttle_feature_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage729_market_breadth_throttle_feature_decision_stage729_market_breadth_throttle_feature_v1.json`
- orders：不适用
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage729_market_breadth_throttle_feature_enriched_candidates_stage729_market_breadth_throttle_feature_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage729_market_breadth_throttle_feature_feature_metrics_stage729_market_breadth_throttle_feature_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage729_market_breadth_throttle_feature_year_detail_stage729_market_breadth_throttle_feature_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage729_market_breadth_throttle_feature_chart_stage729_market_breadth_throttle_feature_v1.png`

## 结论

- 本阶段结论：没有找到可接入正式版或进入 A/C 回测的市场广度型高质量豁免特征。市场广度作为解释变量有合理性，但在当前 `73` 条样本中，要么样本太少，要么 good lift 不够，要么 bad rate 仍偏高。
- 是否进入下一步：本形状不进入策略回测，不接正式版。
- 下一步：停止围绕当前 market breadth 桶扫阈值；如果继续目标，只能转账户级 selector、真正独立外生数据或预声明 forward watch。

## 过拟合反思

- 运行前判断：不是过拟合。原因是市场广度来自趋势系统通用机制，不按红框、年份、品种定制，且先预声明了可靠性门槛。
- 运行后判断：继续把 watch 特征交易化会过拟合。原因是最强 watch 只有 `14` 条样本；唯一达到 `33` 条的 `net_support_pos` good lift 只有 `+6.2267pp` 且 bad rate 仍 `60.6061%`，不足以证明它能穿越周期。
- 原因：高质量机会豁免必须同时保护坏路径并恢复右尾参与权；当前日线广度只能部分解释右尾，不能稳定过滤坏机会。

## 继续价值反思

- 运行前判断：有价值。原因是前面内部字段、`directional_edge60`、账户近高水位和 sleeve bypass 都没有产生可靠豁免，需要测试一个更上游的横截面环境特征。
- 运行后判断：本形状没有继续价值；总目标仍有价值。
- 原因：市场广度审计没有通过初筛，继续扫 `20/30/40%`、`45/60%`、`50/80/100` 日等阈值会变成样本内救参。总目标仍可继续，但方向应更换为账户级 selector、真实外生状态，或先 forward watch 累积 OOS 样本。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage011 负结论。
- 是否更新 `research/registry.md`：是，当前法证线最新阶段更新为 Stage011。
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要负结论和未来边界。
