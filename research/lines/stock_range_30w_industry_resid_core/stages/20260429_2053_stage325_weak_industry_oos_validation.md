# 第325阶段：弱行业过滤OOS/滚动反证

- 记录时间：2026-04-29 20:53 CST
- 当前模式：day
- 当前研究线：`stock_range_30w_industry_resid_core`
- 本阶段性质：第324阶段弱行业过滤的年度、启动年份、滚动窗口、严格走前反证。
- 账户规模：`300,000`元
- 固定弱行业：`软件服务/建筑工程`
- walk-forward规则：每个OOS年份只用过去数据选择贡献最弱的`2`个行业，下一年剔除；释放现金不重分配。
- A/B判断：独立股票震荡研究线反证，不接入第78，不触发正式A/B。

## 外部调研和判断

- 残差/行业内反转的核心是剥离市场和行业暴露后的短期错价，不能把行业名单本身当成alpha。
- walk-forward验证要求过去样本选规则、未来样本检验；如果走前验证不支持，不能继续用OOS结果反过来调行业数量或行业名单。
- GitHub可参考的walk-forward项目多是教学或框架层实现，不能直接复制为A股实盘系统；本阶段只借用验证方法。

参考资料：

- [Short-term residual reversal](https://www.sciencedirect.com/science/article/pii/S1386418112000468)
- [Teddy Koker cross-sectional mean reversion backtest](https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/)
- [GitHub walk-forward validation topic](https://github.com/topics/walk-forward-validation)
- [Walk-forward validation in trading](https://breakorb.com/blog/walk-forward-validation-trading.html)
- [Walk-forward optimization definition](https://tradewink.com/glossary/walk-forward-optimization)

## 新增脚本

- `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation.py`

## 回测参数

- 固定验证基准形状：沿用第324阶段4个形状。
- 固定过滤：剔除`软件服务/建筑工程`，释放现金不重分配。
- 年度验证：2019-2026逐年。
- 启动年份验证：2019-2026逐起始年。
- 滚动窗口：`126`、`252`、`504`个交易日。
- walk-forward OOS年份：2020-2026。
- walk-forward训练集：所有OOS年份之前的数据。
- walk-forward行业选择：训练期行业目标贡献和最低的2个行业，且训练目标行数不少于`100`。
- 交易约束：100股整手，最小佣金5元压力，沿用30万整手回放口径。

## 质量检查

- fail：`0`
- warn：`3`
- 固定规则年度验证可用：pass
- 主低回撤形状固定规则年度收益+回撤同向改善率：`62.50%`
- 主低回撤形状固定规则252日滚动收益+回撤同向改善率：`77.26%`
- walk-forward折数：`28/28`
- walk-forward全部折中收益和回撤同时改善：`11/28`
- 主低回撤形状walk-forward收益+回撤同向改善率：`28.57%`

## 关键结果

### 固定弱行业规则

- 第320候选形状`industry_resid_core_h10_top5_gross70_ind1`：
  - 年度收益跑赢：`6/8`
  - 年度回撤改善：`6/8`
  - 年度收益+回撤同向改善：`5/8`
  - 年度平均收益差：`+1.31pp`
  - 年度平均回撤改善：`+1.82pp`
  - 252日滚动收益+回撤同向改善率：`75.21%`
  - 504日滚动收益+回撤同向改善率：`93.58%`
- 主低回撤形状`industry_resid_core_h10_top8_gross70_ind2`：
  - 年度收益跑赢：`6/8`
  - 年度回撤改善：`6/8`
  - 年度收益+回撤同向改善：`5/8`
  - 年度平均收益差：`+1.38pp`
  - 年度平均回撤改善：`+1.76pp`
  - 252日滚动收益+回撤同向改善率：`77.26%`
  - 504日滚动收益+回撤同向改善率：`92.23%`

### 严格walk-forward弱行业机制

- 全部4个形状、7个OOS年份，共`28`折，收益和回撤同时改善`11/28`。
- `top5_gross100_ind1`：
  - 收益+回撤同向改善：`4/7`
  - 平均收益差：`-0.33pp`
  - 平均回撤改善：`+3.45pp`
- `top5_gross70_ind1`：
  - 收益+回撤同向改善：`3/7`
  - 平均收益差：`-0.48pp`
  - 平均回撤改善：`+2.42pp`
- `top8_gross100_ind2`：
  - 收益+回撤同向改善：`2/7`
  - 平均收益差：`-0.54pp`
  - 平均回撤改善：`+2.70pp`
- `top8_gross70_ind2`：
  - 收益+回撤同向改善：`2/7`
  - 平均收益差：`-0.67pp`
  - 平均回撤改善：`+1.84pp`

## 解释

- 固定剔除`软件服务/建筑工程`的确能在年度、启动年份、滚动窗口上稳定改善回撤，并多数时候提升收益。
- 但严格walk-forward不支持“过去贡献最弱的行业，下一年继续剔除”这个机制。它更像稳定降风险/降暴露，而不是稳定保留收益的alpha机制。
- 因此不能把弱行业名单或过去弱行业选择器策略化。
- 更接近本质的结论是：亏损尾部来自“反转篮子里继续下跌的个股/行业簇”，行业名单只是外在表现，不是根因。

## 运行前过拟合反思

- 判断：固定行业规则有中等偏高过拟合风险，walk-forward风险较低。
- 原因：固定行业来自同样本归因；walk-forward只用过去样本选择下一年行业。

## 运行后过拟合反思

- 判断：不能升级候选。
- 原因：固定规则表现强，但walk-forward主低回撤形状只有`2/7`收益+回撤同向改善，说明行业名单/行业弱势机制不够泛化。

## 运行前继续价值反思

- 判断：有价值。
- 原因：Stage324显示信号层过滤比risk-on更接近亏损来源，必须用OOS反证决定去留。

## 运行后继续价值反思

- 判断：继续有价值，但方向要变。
- 原因：行业名单策略化价值不足；下一步应该转向“继续下跌/接刀子”特征反证，例如短期跌幅结构、开盘缺口、量价破坏、行业残差趋势、涨跌停/流动性冲击，而不是继续扫行业名单。

## 决策

- 不接入第78。
- 不升级正式股票候选。
- 不继续把`软件服务/建筑工程`当作硬策略过滤器扫参。
- 固定弱行业过滤仅保留为风险归因和监控线索。
- 下一阶段转向“继续下跌样本”的信号层反证，寻找能在walk-forward里保留收益同时削减尾部的个股状态变量。

## 输出文件

- 报告：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_v1_report.md`
- 年度记分：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_v1_fixed_year_scorecard.csv`
- 滚动记分：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_v1_rolling_scorecard.csv`
- walk-forward记分：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_v1_walk_forward_scorecard.csv`
- 质量检查：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_weak_industry_oos_validation_v1_quality_checkpoints.csv`
