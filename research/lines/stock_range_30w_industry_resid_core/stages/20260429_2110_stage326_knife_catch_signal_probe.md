# 第326阶段：接刀子信号探针

- 记录时间：2026-04-29 21:10 CST
- 当前模式：day
- 当前研究线：`stock_range_30w_industry_resid_core`
- 本阶段性质：继续下跌/接刀子风险旗标归因与少量预注册过滤探针。
- 账户规模：`300,000`元
- 交易约束：100股整手，最小佣金5元压力，过滤释放现金不重分配。
- 特征时间对齐：所有个股技术旗标只使用上一交易日收盘后已知信息，映射到下一交易日开盘目标。
- A/B判断：独立股票震荡研究线探针，不接入第78，不触发正式A/B。

## 外部调研和判断

- 短期反转可以理解为流动性供给补偿，但不是所有下跌都应该买；趋势性继续下跌是均值回归尾部风险。
- 外部资料常提到成交量、缺口、是否仍在下跌、是否有承接；本阶段把这些翻译成少量事前可识别旗标。
- GitHub和博客示例可参考流程，但不能替代A股整手、涨跌停、交易成本和本地股票池约束。

参考资料：

- [Short-term reversals, returns to liquidity provision and immediacy costs](https://www.sciencedirect.com/science/article/pii/S0378426622000309)
- [Quantpedia short-term reversal summary](https://quantpedia.com/strategies/short-term-reversal-in-stocks/)
- [Teddy Koker cross-sectional mean reversion backtest](https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/)
- [Mean-reversion failure discussion: avoid falling knives](https://setupalpha.com/blogs/articles/mean-reversion-strategy-failures-complete-fix-guide)
- [GitHub mean-reversion-trading topic](https://github.com/topics/mean-reversion-trading)

## 新增脚本

- `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe.py`

## 重要纠偏

- 初次运行时发现同日特征对齐风险：若用`target_date`当天收盘/盘中信息过滤当天开盘交易，会形成前视偏差。
- 已修正为上一交易日特征映射到下一交易日开盘目标，修正前结果全部作废。
- 下面记录的是修正后的可用结果。

## 预注册旗标

- `flag_gap_down`：上一交易日向下跳空超过`3%`。
- `flag_intraday_selloff`：上一交易日开盘到收盘下跌超过`3%`。
- `flag_close_near_low`：上一交易日IBS小于等于`0.15`。
- `flag_high_volume_selloff`：上一交易日放量且价格继续下跌。
- `flag_short_crash`：上一交易日5日跌幅超过`10%`或20日跌幅超过`20%`。
- `flag_broken_mid_trend`：上一交易日跌破60日均线较深且远离252日高点。
- `flag_limit_down_signal`：上一交易日跌停或一字跌停。
- 组合旗标：`drop_knife_2plus`、`drop_knife_3plus`。

## 质量检查

- fail：`0`
- warn：`4`
- 全样本收益和回撤同时改善：`0/28`
- 高收益且20%以内回撤：`0/28`
- 年度多数同向改善：`1/28`
- 主场景252日滚动多数同向改善：`0/7`
- 前视检查：pass，使用上一交易日特征。

## 关键结果

- 全部7个探针、4个代表形状，修正前视后没有一个能在全样本同时改善收益和回撤。
- 第320候选形状`top5_gross70_ind1`：
  - 基准：总收益`34.60%`，最大回撤`-26.88%`，Sharpe `0.323`。
  - 最接近可用的是`drop_high_volume_selloff`：总收益`32.85%`，最大回撤`-25.67%`，Sharpe `0.315`。
  - 解释：回撤改善约`+1.21pp`，但收益下降约`-1.75pp`，不是同向改善。
  - `drop_short_crash`、`drop_knife_2plus`、`drop_knife_3plus`明显破坏收益和回撤。
- 主低回撤形状`top8_gross70_ind2`：
  - 基准：总收益`37.04%`，最大回撤`-26.39%`，Sharpe `0.349`。
  - `drop_high_volume_selloff`：总收益`35.23%`，最大回撤`-25.27%`，Sharpe `0.340`。
  - 解释：回撤改善约`+1.12pp`，但收益下降约`-1.82pp`。
  - 主场景252日滚动最佳同向改善率也不过`39.26%`，没有过半。

## 信号尾部画像

- 底部10%次开盘信号平均收益约`-6.05%`到`-6.13%`，顶部10%约`+7.25%`到`+7.36%`。
- 简单接刀子旗标不是纯坏信号：
  - `knife_flag_count`在顶部10%反弹样本中反而高于底部10%亏损样本。
  - `flag_short_crash`、`flag_intraday_selloff`、`flag_close_near_low`在强反弹样本里同样常见。
- 这说明这些旗标更像“高波动/弹性来源”，不是稳定坏样本。硬过滤会同时删掉亏损尾部和收益来源。

## 结论

- 本阶段否定了“简单技术接刀子旗标硬过滤”。
- 放量下跌过滤可以小幅削回撤，但会牺牲收益，不符合30万高收益目标。
- 组合风险旗标会严重误杀均值回归收益来源。
- 下一步不能继续扫这些阈值；应该转向更细的“坏反转 vs 好反转”区分，例如：
  - 同样有接刀子旗标时，哪些样本次日继续跌，哪些样本强反弹；
  - 引入相对行业/市场状态，而不是只看单票绝对技术形态；
  - 检查开盘执行后的持有路径，而不是只看次开盘。

## 过拟合反思

- 运行前判断：中等。
- 原因：旗标阈值来自第一性原理和外部调研，但一次测试多个探针仍有选择偏差。
- 运行后判断：不升级候选，且本方向降级。
- 原因：修正前视后`0/28`全样本同向改善，主场景252日滚动也没有任何探针过半同向改善。

## 继续价值反思

- 运行前判断：有价值。
- 原因：第325阶段说明行业名单不是根因，应该回到个股是否继续下跌的可识别状态。
- 运行后判断：继续有价值，但不是继续硬过滤这些旗标。
- 原因：旗标能标识高波动区域，却不能区分坏反转和好反转；下一步应该研究同一旗标内部的条件分化。

## 决策

- 不接入第78。
- 不升级正式股票候选。
- 不把`drop_high_volume_selloff`、`drop_limit_down_signal`等作为正式过滤器。
- 不继续围绕这些固定阈值扫参。
- 下一阶段转向“同样是高波动超跌，为什么有些强反弹、有些继续跌”的二阶归因。

## 输出文件

- 报告：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_v1_report.md`
- 汇总：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_v1_summary.csv`
- 年度记分：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_v1_year_scorecard.csv`
- 滚动记分：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_v1_rolling_scorecard.csv`
- 质量检查：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_knife_catch_signal_probe_v1_quality_checkpoints.csv`
