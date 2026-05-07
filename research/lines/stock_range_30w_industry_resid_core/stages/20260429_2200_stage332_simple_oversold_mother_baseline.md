# 第332阶段 简单20日超跌30万母本体检

- line_id：`stock_range_30w_industry_resid_core`
- 当前模式：day
- 记录时间：2026-04-29 22:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：母本体检/架构分层基准，不新增交易参数，不触发A/B。
- 是否重要突破：否，但完成第331后续的架构基准落点。
- 是否触发A/B：否。没有正式候选。

## 外部调研与判断

- 参考资料：
  - Short-term residual reversal：残差短反方向强调剥离市场/因子暴露。
  - Decomposing Short-Term Return Reversal：短反的关键部分更接近残差/流动性冲击回归。
  - Short-term reversals and turnover：短反与换手/交易需求有关，成本和周转会显著影响可交易性。
  - Connors RSI(2)：业界模板强调顺长期趋势买短期回调，不是单票猜底。
- 我的判断：
  - 简单20日超跌不是最终策略，但少假设、透明、可复验，适合作为后续所有增强层的母本。
  - 30万账户的关键不是只看信号强度，还要同步看整手颗粒度、目标暴露捕获、回撤窗口和滚动稳定性。

## 本次变更

- 新增脚本：
  - `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。本阶段只读取既有简单20日超跌网格产物。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2018-04-20 到 2026-04-27。
- 账户规模：300,000 CNY。
- 成本口径：`min_fee`，沿用源网格的整手回放和最低佣金压力口径。
- 样本过滤：不新增过滤。
- 策略/归因口径：
  - 母本候选来自第331确认的`score_oversold_ret_20`简单超跌网格。
  - 重点关注：`top8_gross50_ind2`、`top5_gross50_ind2`、`top8_gross30_ind2`、`top8_gross70_ind2`、`top5_gross70_ind2`。
  - 额外生成年度、252日滚动、主要回撤段、暴露桶、市场状态、行业尾部画像。

## 结果

- 全简单网格正式目标命中数：`0`。
- 研究母本：
  - 场景：`top8_gross50_ind2`
  - 期末权益：`1.4958`
  - 总收益：`49.58%`
  - 最大回撤：`-23.28%`
  - Sharpe：`0.4480`
  - 零手目标比例：`26.52%`
  - 252日滚动正收益窗口比例：`84.77%`
  - 252日滚动最差收益：`-10.09%`
  - 252日滚动最差回撤：`-23.28%`
- 可交易性护栏：
  - 场景：`top5_gross50_ind2`
  - 期末权益：`1.4041`
  - 总收益：`40.41%`
  - 最大回撤：`-22.68%`
  - Sharpe：`0.3684`
  - 零手目标比例：`18.38%`
  - 252日滚动正收益窗口比例：`74.32%`
- 风险地板：
  - 场景：`top8_gross30_ind2`
  - 期末权益：`1.2583`
  - 总收益：`25.83%`
  - 最大回撤：`-13.62%`
  - Sharpe：`0.4468`
  - 252日滚动正收益窗口比例：`84.83%`
- 高暴露压力样本：
  - 场景：`top8_gross70_ind2`
  - 期末权益：`1.6115`
  - 总收益：`61.15%`
  - 最大回撤：`-31.66%`
  - Sharpe：`0.4028`
- 主要路径观察：
  - `top8_gross50_ind2`最大回撤段为2018-05-08到2018-10-18，回撤`-23.28%`，到2020-02-20恢复。
  - `top8_gross50_ind2`年度正收益`8/9`，最差年度为2018年，年度收益`-17.66%`。
  - 信号状态上，`market_down_20d`样本10日前瞻超额明显强于`market_up_20d`，说明该母本更像“市场短期下跌后的横截面反弹”，不是越热越好。
- 总滑点：本阶段未新跑回测，不新增滑点统计。
- 总交易次数：本阶段未新跑回测，源网格`top8_gross50_ind2`订单行数可从源summary读取，未新增交易次数统计。
- 胜率：本阶段未新跑回测，重点使用年度/滚动/日胜率画像。

## 输出文件

- report：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_2018_2026/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_v1_report.md`
- shape_frontier：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_2018_2026/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_v1_shape_frontier.csv`
- mother_decision：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_2018_2026/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_v1_mother_decision.csv`
- yearly：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_2018_2026/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_v1_yearly_aggregate.csv`
- rolling：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_2018_2026/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_v1_rolling_aggregate.csv`
- drawdown：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_2018_2026/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_v1_drawdown_windows.csv`
- quality：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_2018_2026/stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_v1_quality_checkpoints.csv`

## 结论

- 本阶段结论：
  - `top8_gross50_ind2`作为研究母本，而不是正式候选。
  - `top5_gross50_ind2`作为可交易性护栏，后续任何增强都必须同步报告。
  - `top8_gross30_ind2`作为风险地板，说明低暴露可以控回撤但收益不够。
  - 高暴露70%版本只适合做压力参照，不能靠单纯加仓达成目标。
  - 下一步应该做同形状残差增量验证：在同样topK/gross/行业上限下，用残差/行业内超跌排序替换或混合`score_oversold_ret_20`，验证相对母本的真实增益。
- 是否进入下一步：是。
- 下一步：
  1. 做`layer1_residual_increment`。
  2. 固定`top8_gross50_ind2`和`top5_gross50_ind2`两条形状。
  3. 比较简单20日超跌、行业残差、市场残差、混合排序。
  4. 评价必须包含收益、回撤、Sharpe、年度、252日滚动、零手比例、行业集中度。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有新增交易阈值，没有挑最佳参数上线，只是把母本、护栏、风险地板和压力样本固定下来，反而减少后续混乱试错。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：母本明确后，后续残差增强可以做干净的同形状对照，比继续修`industry_resid_core`更贴近30万高收益低回撤目标。

## 合入建议

- 是否更新本线`LINE.md`：是。
- 是否更新`research/registry.md`：否。研究线归属未变。
- 是否追加根目录`memory.md/back_log.md`：否。本阶段是线内基准体检，不是正式候选或跨线合并。
