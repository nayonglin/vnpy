# 第328阶段：高弹性尾部控制探针

- 记录时间：2026-04-29 21:25 CST
- 当前模式：day
- 当前研究线：`stock_range_30w_industry_resid_core`
- 本阶段性质：保留高弹性接刀子样本，测试温和降权/暴露上限是否改善尾部。
- 是否重要突破版本：否。
- 账户规模：`300,000`元。
- 交易约束：100股整手，最小佣金5元压力；控制释放现金不重分配。
- 特征时间对齐：接刀子旗标使用上一交易日收盘后已知信息。
- A/B判断：独立股票震荡研究线探针，不接入第78，不触发正式A/B。

## 外部调研和判断

- 短期反转更像流动性供给补偿，高波动样本不能简单删除。
- 业界风险控制常用暴露上限、波动缩放、尾部预算；这比硬过滤更符合第327阶段发现。
- 但风险预算如果作用在alpha来源上，很容易“看似风控、实则砍掉收益”，必须用回放和滚动验证。

参考资料：

- [Short-term reversals, returns to liquidity provision and immediacy costs](https://www.sciencedirect.com/science/article/pii/S0378426622000309)
- [Short-term residual reversal](https://www.sciencedirect.com/science/article/pii/S1386418112000468)
- [Volatility-adjusted position sizing discussion](https://breakingalpha.io/insights/volatility-adjusted-position-sizing)
- [Trade sizing techniques for drawdown and tail risk control](https://libertyroadcapital.com/trade-sizing-techniques-for-drawdown-and-tail-risk-control/)
- [GitHub mean-reversion-trading topic](https://github.com/topics/mean-reversion-trading)

## 新增脚本

- `examples/alpha_research/analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe.py`

## 新增参数/探针

- `soft_knife_any_90`：至少1个接刀子旗标权重乘以`0.90`。
- `soft_knife2plus_75`：至少2个接刀子旗标权重乘以`0.75`。
- `soft_limitdown_50`：上一交易日跌停/一字跌停权重乘以`0.50`。
- `cap_knife2plus_daily_20pct`：每日`knife_2plus`目标总权重上限`20%`。
- `cap_knife2plus_daily_15pct`：每日`knife_2plus`目标总权重上限`15%`。
- `cap_limitdown_daily_5pct`：每日跌停/一字跌停目标总权重上限`5%`。
- `cap_high_volume_daily_8pct`：每日放量下跌目标总权重上限`8%`。
- `hybrid_elastic_tail_budget`：`knife_2plus`日上限`20%`，跌停日上限`5%`，放量下跌目标乘以`0.85`。

## 质量检查

- fail：`0`
- warn：`3`
- 全样本收益和回撤同时改善：`1/32`
- 回撤改善且收益不低于基准一半：`8/32`
- 高收益且20%以内回撤：`0/32`
- 年度多数同向改善：`7/32`
- 主场景252日滚动多数同向改善：`0/8`

## 关键结果

- 唯一全样本收益和回撤同向改善：
  - `industry_resid_core_h10_top5_gross100_ind1_cap_high_volume_daily_8pct`
  - 总收益`52.87%`，最大回撤`-40.60%`，Sharpe `0.358`
  - 相比基准收益提升`+3.72pp`，回撤改善`+0.04pp`
  - 解释：改善很小，且发生在高回撤`gross100`形状，不构成30万目标候选。
- 主低回撤形状`industry_resid_core_h10_top8_gross70_ind2`：
  - 基准：总收益`37.04%`，最大回撤`-26.39%`，Sharpe `0.349`
  - `cap_high_volume_daily_8pct`：总收益`38.94%`，最大回撤`-26.47%`，Sharpe `0.361`
    - 收益提升`+1.89pp`，回撤恶化`-0.08pp`
    - 说明放量下跌上限有一点收益线索，但不解决回撤。
  - `cap_limitdown_daily_5pct`：总收益`33.08%`，最大回撤`-26.08%`，Sharpe `0.326`
    - 回撤改善`+0.31pp`，但收益下降`-3.97pp`
    - 说明跌停预算能微削回撤，但会误伤弹性。
  - `soft_knife_any_90`、`soft_knife2plus_75`、`cap_knife2plus_daily_*`和`hybrid_elastic_tail_budget`均显著伤害收益，并且多数还恶化回撤。

## 滚动/分段结论

- 主低回撤形状252日滚动没有任何探针同向改善率过半。
- 主低回撤形状中：
  - `cap_limitdown_daily_5pct`滚动同向改善率`36.95%`，平均收益差`-0.62pp`，平均回撤改善`+0.14pp`。
  - `soft_limitdown_50`滚动同向改善率`34.10%`，平均收益差`-0.51pp`，平均回撤改善`+0.21pp`。
  - `cap_high_volume_daily_8pct`滚动同向改善率`18.24%`，平均收益差`+0.26pp`，平均回撤改善约`0.00pp`。
- 解释：目前没有稳健的“保收益又降回撤”的尾部预算。

## 结论

- 否定对`knife_any/knife_2plus`做统一降权或日度上限。
- `knife_2plus`是收益来源的一部分，预算化压得越多，越像砍掉alpha，而不是控制风险。
- `limitdown`控制有轻微回撤价值，但收益损失更大，不能升级。
- `high_volume_daily_8pct`有很小的收益线索，但不解决主目标回撤，也不够稳健。
- 下一步应转向持有路径归因：判断亏损来自开盘后首日、持有中段还是退出前，而不是继续围绕入场前接刀子预算扫参。

## 过拟合反思

- 运行前判断：中等。
- 原因：控制规则来自第327机制发现和外部风险预算思想，且数量少；但仍在同一历史样本上测试。
- 运行后判断：否，不升级候选，且主动否定多数探针。
- 原因：`0/32`达到30万高收益且20%以内回撤，主场景252日滚动`0/8`过半同向改善，没有继续调阈值。

## 继续价值反思

- 运行前判断：有价值。
- 原因：第327证明高弹性样本是收益来源，风险控制必须从硬过滤转向预算化。
- 运行后判断：继续有价值，但不沿入场前尾部预算继续扫。
- 原因：尾部预算容易误伤alpha；更有价值的是持有路径归因，找到亏损发生在路径哪一段。

## 决策

- 不接入第78。
- 不升级正式股票候选。
- 不把任何尾部控制探针策略化。
- 不继续围绕`knife_any/knife_2plus`做统一降权或日度上限。
- 下一阶段转向持有路径归因。

## 输出文件

- 报告：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_v1_report.md`
- 汇总：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_v1_summary.csv`
- 控制日统计：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_v1_scale_daily.csv`
- 回放日收益：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_v1_daily.csv`
- 回放订单：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_v1_orders.csv`
- 年度记分：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_v1_year_scorecard.csv`
- 滚动记分：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_v1_rolling_scorecard.csv`
- 质量检查：`examples/alpha_research/native_results/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_2018_2026/stock_range_reversion_liquid_q3_industry_resid_core_30w_high_elastic_tail_control_probe_v1_quality_checkpoints.csv`
